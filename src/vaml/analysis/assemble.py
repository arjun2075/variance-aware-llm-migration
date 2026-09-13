"""Assemble the call ledger into per-run records for analysis.

A RUN is one (pipeline, task, model, repetition) executed through all four
stages. The ledger stores individual CALLS, so runs are reconstructed by
grouping on the RequestID and requiring every stage to be present and ok.

Acceptance follows the frozen rules: schema violations and parse failures are
DATA, not exclusion criteria. A run is excluded only for transport failure
after the retry budget, canonical model mismatch, or a missing stage.
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import RequestID
from .parsing import (extract_json, p1_schema_valid, p1_structured,
                      p2_schema_valid, p2_structured, verbatim_grounding)

P1_STAGES = ["pr_signal", "review_signal", "synthesis", "deepen"]
P2_STAGES = ["extract_evidence", "assess_evidence", "classify", "verify"]


@dataclass
class Run:
    pipeline: str
    partition: str
    task_id: str
    model_key: str
    repetition: int
    accepted: bool
    exclusion_reason: str | None
    #: parsed structured fields (None for excluded runs)
    structured: dict | None
    schema_valid: bool
    schema_violations: list[str]
    parse_failures: dict[str, str]
    returned_model_ids: set[str]
    provenance_ok: bool
    #: operational
    total_prompt_tokens: int
    total_completion_tokens: int
    total_latency_ms: float
    total_retries: int
    stages_present: int
    extra: dict[str, Any] = field(default_factory=dict)


def load_ledger(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def assemble_runs(ledger: list[dict], p2_corpus: dict[str, dict] | None = None
                  ) -> list[Run]:
    """Group calls into runs. p2_corpus maps task_id -> case (for grounding)."""
    groups: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for rec in ledger:
        rid = RequestID.parse(rec["rid"])
        key = (rid.pipeline.value, rid.partition, rid.task_id, rid.model_key,
               rid.repetition)
        groups[key][rid.stage] = rec

    runs: list[Run] = []
    for (pipeline, partition, task_id, model_key, rep), calls in sorted(groups.items()):
        stages = P1_STAGES if pipeline.startswith("p1") else P2_STAGES
        present = [s for s in stages if s in calls]

        ptok = sum(calls[s].get("prompt_tokens") or 0 for s in present)
        ctok = sum(calls[s].get("completion_tokens") or 0 for s in present)
        lat = sum(calls[s].get("latency_ms") or 0.0 for s in present)
        retries = sum(calls[s].get("retry_count") or 0 for s in present)
        returned = {calls[s].get("returned_model_id") for s in present
                    if calls[s].get("returned_model_id")}
        prov_ok = not any((calls[s].get("extra") or {}).get(
            "canonical_model_mismatch") for s in present)

        # --- exclusion (frozen rules only) ---
        reason = None
        if len(present) < len(stages):
            reason = f"incomplete_run_{len(present)}_of_{len(stages)}_stages"
        elif any(calls[s].get("error") for s in present):
            failed = [s for s in present if calls[s].get("error")]
            reason = f"transport_failure:{failed[0]}"
        elif not prov_ok:
            reason = "canonical_model_mismatch"

        if reason:
            runs.append(Run(pipeline, partition, task_id, model_key, rep,
                            False, reason, None, False, [], {}, returned,
                            prov_ok, ptok, ctok, lat, retries, len(present)))
            continue

        # --- parse (failures are DATA, run stays accepted) ---
        parsed: dict[str, dict | None] = {}
        pfail: dict[str, str] = {}
        for s in stages:
            d, why = extract_json(calls[s].get("text"))
            parsed[s] = d
            if why:
                pfail[s] = why

        if pipeline.startswith("p1"):
            structured = p1_structured(parsed["synthesis"], parsed["deepen"])
            ok, viol = p1_schema_valid(parsed["synthesis"], parsed["deepen"])
        else:
            structured = p2_structured(parsed["extract_evidence"],
                                       parsed["classify"], parsed["verify"])
            ok, viol = p2_schema_valid(parsed["classify"])
            if p2_corpus and task_id in p2_corpus:
                doc = p2_corpus[task_id]["document_text"]
                g, n = verbatim_grounding(structured["cited_spans"], doc)
                structured["spans_grounded"] = g
                structured["spans_cited"] = n
                structured["grounding_rate"] = (g / n) if n else None

        runs.append(Run(pipeline, partition, task_id, model_key, rep, True,
                        None, structured, ok, viol, pfail, returned, prov_ok,
                        ptok, ctok, lat, retries, len(present)))
    return runs


def acceptance_summary(runs: list[Run]) -> dict:
    acc = [r for r in runs if r.accepted]
    exc = [r for r in runs if not r.accepted]
    return {
        "total_runs": len(runs),
        "accepted": len(acc),
        "excluded": len(exc),
        "exclusion_reasons": dict(collections.Counter(
            r.exclusion_reason for r in exc)),
        "schema_valid": sum(1 for r in acc if r.schema_valid),
        "schema_violation_rate_by_model": _rate_by_model(
            acc, lambda r: not r.schema_valid),
        "parse_failure_rate_by_model": _rate_by_model(
            acc, lambda r: bool(r.parse_failures)),
        # string keys so the summary is JSON-serialisable
        "by_partition": {f"{p}/{part}": n for (p, part), n in sorted(
            collections.Counter((r.pipeline, r.partition) for r in acc).items())},
    }


def _rate_by_model(runs: list[Run], pred) -> dict[str, str]:
    d: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for r in runs:
        d[r.model_key][1] += 1
        if pred(r):
            d[r.model_key][0] += 1
    return {k: f"{n}/{t} ({100*n/t:.1f}%)" for k, (n, t) in sorted(d.items())}
