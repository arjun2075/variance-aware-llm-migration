"""Dependency-wave orchestration for sequential compound pipelines.

The pipelines are sequential: stage N+1 consumes stage N's output. Batch APIs
are asynchronous, so we cannot batch a whole pipeline run end to end. Instead we
execute in WAVES:

    Wave 1: every stage-1 call, batched across tasks x models x repetitions
    Wave 2: every stage-2 call, built from wave-1 outputs
    ...

This keeps batch economics (one large job per wave) while respecting the data
dependency. Within a wave, requests are independent by construction.

Identity discipline
-------------------
Batch results arrive out of order and may be incomplete. Every rejoin is by
`custom_id`. The orchestrator refuses to build the next wave if any upstream
result is missing, rather than silently dropping runs and producing a grid with
holes that later looks like data.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..adapters.base import ProviderAdapter
from ..types import CallRequest, CallResult, Pipeline, RequestID, ServingMode


@dataclass
class WaveSpec:
    """One stage of a compound pipeline."""
    stage: str
    #: (task, upstream_results_by_stage) -> (system_prompt, user_prompt)
    build_prompt: Callable[[dict, dict[str, CallResult]], tuple[str, str]]
    max_tokens: int


@dataclass
class ExecutionPlan:
    pipeline: Pipeline
    partition: str
    tasks: list[dict]
    #: model_key -> (adapter, model_id, repetitions)
    models: dict[str, tuple[ProviderAdapter, str, int]]
    waves: list[WaveSpec]
    serving_mode: ServingMode
    #: Seeded permutation of the (task, model, repetition) tuples.
    order: list[tuple[str, str, int]]


def build_execution_order(
    tasks: list[dict],
    models: dict[str, tuple[ProviderAdapter, str, int]],
    seed: int,
) -> list[tuple[str, str, int]]:
    """Seeded interleaved permutation across model x task x repetition.

    Model-major execution is prohibited: it confounds model with time-of-day and
    transient provider load. The permutation is generated and hashed BEFORE
    execution.
    """
    import random

    tuples = [
        (t["task_id"], mk, rep)
        for t in tasks
        for mk, (_, _, reps) in models.items()
        for rep in range(1, reps + 1)
    ]
    rng = random.Random(seed)
    rng.shuffle(tuples)
    return tuples


class WaveOrchestrator:
    """Executes an ExecutionPlan wave by wave, persisting after each wave."""

    def __init__(self, plan: ExecutionPlan, out_dir: Path):
        self.plan = plan
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        #: custom_id -> CallResult, accumulated across waves
        self.results: dict[str, CallResult] = {}
        #: (task_id, model_key, repetition) tuples pruned because an upstream
        #: stage failed. Distinguished from genuinely missing results so a
        #: legitimately-dead run does not look like a lost one.
        self.pruned: set[tuple[str, str, int]] = set()
        self._order_index = {
            (t, m, r): i for i, (t, m, r) in enumerate(plan.order)
        }

    # ------------------------------------------------------------------
    def _requests_for_wave(self, wave: WaveSpec) -> dict[str, list[CallRequest]]:
        """Build this wave's requests, grouped by model_key.

        Raises if an upstream dependency is missing, rather than silently
        producing a partial grid.
        """
        by_task = {t["task_id"]: t for t in self.plan.tasks}
        grouped: dict[str, list[CallRequest]] = {mk: [] for mk in self.plan.models}
        wave_i = [w.stage for w in self.plan.waves].index(wave.stage)
        upstream_stages = [w.stage for w in self.plan.waves[:wave_i]]

        for task_id, model_key, rep in self.plan.order:
            run_key = (task_id, model_key, rep)
            if run_key in self.pruned:
                # already dead from an earlier stage failure
                continue
            rid = RequestID(self.plan.pipeline, task_id, model_key, rep,
                            wave.stage, self.plan.partition)
            upstream: dict[str, CallResult] = {}
            for st in upstream_stages:
                up_id = RequestID(self.plan.pipeline, task_id, model_key, rep,
                                  st, self.plan.partition).custom_id()
                res = self.results.get(up_id)
                if res is None:
                    raise RuntimeError(
                        f"missing upstream result for {up_id}; refusing to "
                        f"build wave {wave.stage!r} with an incomplete grid"
                    )
                upstream[st] = res
            # A failed upstream call kills this run's later stages. Record the
            # prune explicitly so downstream waves treat it as a known-dead run
            # rather than an unexplained gap.
            if any(not r.ok for r in upstream.values()):
                self.pruned.add(run_key)
                continue
            sys_p, usr_p = wave.build_prompt(by_task[task_id], upstream)
            grouped[model_key].append(
                CallRequest(rid=rid, system_prompt=sys_p, user_prompt=usr_p,
                            max_tokens=wave.max_tokens)
            )
        return grouped

    # ------------------------------------------------------------------
    def run_wave(self, wave: WaveSpec) -> list[CallResult]:
        grouped = self._requests_for_wave(wave)
        collected: list[CallResult] = []

        for model_key, reqs in grouped.items():
            if not reqs:
                continue
            adapter, model_id, _ = self.plan.models[model_key]

            if self.plan.serving_mode is ServingMode.BATCH:
                if not adapter.supports_batch(model_id):
                    raise RuntimeError(
                        f"batch requested but {adapter.name}/{model_id} has no "
                        f"batch path; do not silently fall back to sync mid-run"
                    )
                handle = adapter.submit_batch(model_id, reqs)
                status = adapter.poll_batch(handle)
                if status != "completed":
                    raise RuntimeError(
                        f"batch {handle.batch_id} status={status}")
                got = adapter.fetch_batch(handle)
            else:
                got = [adapter.call_sync(model_id, r) for r in reqs]

            # Rejoin strictly by custom_id; never by position.
            sent = {r.rid.custom_id() for r in reqs}
            seen = {r.rid.custom_id() for r in got}
            missing = sent - seen
            unexpected = seen - sent
            if unexpected:
                raise RuntimeError(
                    f"provider returned unknown custom_ids: {sorted(unexpected)[:5]}")
            if missing:
                raise RuntimeError(
                    f"{len(missing)} results missing from {adapter.name} wave "
                    f"{wave.stage!r}, e.g. {sorted(missing)[:3]}")
            collected.extend(got)

        for r in collected:
            key = (r.rid.task_id, r.rid.model_key, r.rid.repetition)
            r.execution_order_index = self._order_index.get(key)
            self.results[r.rid.custom_id()] = r

        self._persist(wave.stage, collected)
        return collected

    # ------------------------------------------------------------------
    def run_all(self) -> dict[str, CallResult]:
        for wave in self.plan.waves:
            self.run_wave(wave)
        return self.results

    def _persist(self, stage: str, results: list[CallResult]) -> None:
        path = self.out_dir / f"{self.plan.pipeline.value}_{self.plan.partition}_{stage}.jsonl"
        with path.open("w") as fh:
            for r in sorted(results, key=lambda x: x.rid.custom_id()):
                fh.write(r.to_json() + "\n")
        meta = {
            "pipeline": self.plan.pipeline.value,
            "partition": self.plan.partition,
            "stage": stage,
            "serving_mode": self.plan.serving_mode.value,
            "n_results": len(results),
            "n_ok": sum(1 for r in results if r.ok),
            "written_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        (self.out_dir / f"{path.stem}_meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n")
