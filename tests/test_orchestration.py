"""Tests for identity preservation and wave sequencing.

The single most dangerous failure mode in a batch grid is a silent mis-join:
results arriving out of order and being matched positionally, producing a
plausible-looking dataset in which model A's outputs are attributed to model B.
These tests exist to make that impossible.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vaml.adapters.base import MockAdapter  # noqa: E402
from vaml.orchestration.waves import (  # noqa: E402
    ExecutionPlan, WaveOrchestrator, WaveSpec, build_execution_order,
)
from vaml.types import (  # noqa: E402
    CallRequest, Pipeline, RequestID, ServingMode,
)


# ---------------- RequestID identity ----------------

def test_request_id_roundtrip():
    rid = RequestID(Pipeline.P2, "task_007", "candidate_anthropic", 3,
                    "extract_spans", "primary")
    assert RequestID.parse(rid.custom_id()) == rid


def test_custom_id_is_unique_across_the_grid():
    ids = {
        RequestID(Pipeline.P2, t, m, r, s).custom_id()
        for t in ("t1", "t2")
        for m in ("incumbent_gpt4o", "candidate_anthropic")
        for r in (1, 2, 3)
        for s in ("extract_spans", "reason")
    }
    assert len(ids) == 2 * 2 * 3 * 2


def test_partition_separates_ids():
    a = RequestID(Pipeline.P2, "t1", "m", 1, "s", "primary")
    b = RequestID(Pipeline.P2, "t1", "m", 1, "s", "stress")
    assert a.custom_id() != b.custom_id()


@pytest.mark.parametrize("bad", ["too|few|parts", "a|b|c|d|e|f|g", "p|q|t|m|X1|s"])
def test_parse_rejects_malformed(bad):
    with pytest.raises(ValueError):
        RequestID.parse(bad)


def test_prompt_hash_changes_with_prompt():
    rid = RequestID(Pipeline.P1, "t", "m", 1, "s")
    a = CallRequest(rid, "sys", "user", 100)
    b = CallRequest(rid, "sys", "user2", 100)
    assert a.prompt_hash() != b.prompt_hash()


# ---------------- execution order ----------------

def test_execution_order_covers_full_grid():
    tasks = [{"task_id": f"t{i}"} for i in range(4)]
    models = {"inc": (None, "m1", 8), "cand": (None, "m2", 5)}
    order = build_execution_order(tasks, models, seed=1)
    assert len(order) == 4 * (8 + 5)
    assert len(set(order)) == len(order)


def test_execution_order_is_not_model_major():
    """Model-major execution confounds model with time; must be interleaved."""
    tasks = [{"task_id": f"t{i}"} for i in range(10)]
    models = {"inc": (None, "m1", 5), "cand": (None, "m2", 5)}
    order = build_execution_order(tasks, models, seed=20260803)
    first_half = [m for _, m, _ in order[: len(order) // 2]]
    # both models must appear in the first half of the schedule
    assert len(set(first_half)) == 2


def test_execution_order_is_seed_deterministic():
    tasks = [{"task_id": f"t{i}"} for i in range(5)]
    models = {"inc": (None, "m1", 3)}
    assert (build_execution_order(tasks, models, seed=9)
            == build_execution_order(tasks, models, seed=9))
    assert (build_execution_order(tasks, models, seed=9)
            != build_execution_order(tasks, models, seed=10))


# ---------------- wave orchestration ----------------

def _plan(tmp_path, mode=ServingMode.BATCH, n_tasks=3, adapter=None):
    adapter = adapter or MockAdapter(seed=1)
    tasks = [{"task_id": f"t{i}", "text": f"doc {i}"} for i in range(n_tasks)]
    models = {
        "incumbent_gpt4o": (adapter, "gpt-4o-2024-11-20", 8),
        "candidate_anthropic": (adapter, "claude-x", 5),
    }
    waves = [
        WaveSpec("extract", lambda t, up: ("sys", f"extract from {t['text']}"), 512),
        WaveSpec("reason",
                 lambda t, up: ("sys", f"reason over {up['extract'].text}"), 512),
        WaveSpec("classify",
                 lambda t, up: ("sys", f"classify {up['reason'].text}"), 256),
    ]
    order = build_execution_order(tasks, models, seed=20260803)
    return ExecutionPlan(Pipeline.P2, "primary", tasks, models, waves, mode, order)


def test_all_waves_produce_full_grid(tmp_path):
    plan = _plan(tmp_path)
    orch = WaveOrchestrator(plan, tmp_path)
    results = orch.run_all()
    expected = 3 * (8 + 5) * 3   # tasks x (reps) x waves
    assert len(results) == expected


def test_results_rejoin_by_custom_id_not_position(tmp_path):
    """MockAdapter deliberately shuffles batch results; identity must survive."""
    plan = _plan(tmp_path)
    orch = WaveOrchestrator(plan, tmp_path)
    orch.run_all()
    for cid, res in orch.results.items():
        assert res.rid.custom_id() == cid       # no cross-wiring
        assert RequestID.parse(cid).stage == res.rid.stage


def test_downstream_prompt_consumes_correct_upstream_result(tmp_path):
    """Wave N+1 must read the SAME run's wave-N output, not another run's."""
    seen: list[tuple[str, str]] = []
    adapter = MockAdapter(seed=2)
    tasks = [{"task_id": f"t{i}", "text": f"doc {i}"} for i in range(3)]
    models = {"inc": (adapter, "m1", 2)}

    def w2(task, up):
        # the upstream result handed to us must belong to this task
        seen.append((task["task_id"], up["extract"].rid.task_id))
        return ("sys", "u")

    waves = [WaveSpec("extract", lambda t, up: ("sys", "u"), 128),
             WaveSpec("reason", w2, 128)]
    plan = ExecutionPlan(Pipeline.P2, "primary", tasks, models, waves,
                         ServingMode.BATCH,
                         build_execution_order(tasks, models, seed=3))
    WaveOrchestrator(plan, tmp_path).run_all()
    assert seen and all(a == b for a, b in seen)


def test_missing_upstream_raises_rather_than_silently_skipping(tmp_path):
    plan = _plan(tmp_path)
    orch = WaveOrchestrator(plan, tmp_path)
    with pytest.raises(RuntimeError, match="missing upstream"):
        orch.run_wave(plan.waves[1])       # wave 2 before wave 1


def test_failed_upstream_stops_that_run_only(tmp_path):
    """A stage-1 failure drops that run's later stages but not the whole grid."""
    adapter = MockAdapter(seed=4, fail_rate=0.30)
    plan = _plan(tmp_path, adapter=adapter)
    orch = WaveOrchestrator(plan, tmp_path)
    orch.run_all()
    w1 = [r for r in orch.results.values() if r.rid.stage == "extract"]
    w3 = [r for r in orch.results.values() if r.rid.stage == "classify"]
    assert any(not r.ok for r in w1)     # failures did occur
    assert len(w3) < len(w1)             # and pruned downstream work
    assert len(w3) > 0                   # without killing the run


def test_sync_mode_records_latency_batch_does_not(tmp_path):
    """Batch turnaround is not interactive latency and must stay unset."""
    b = WaveOrchestrator(_plan(tmp_path / "b", ServingMode.BATCH), tmp_path / "b")
    b.run_all()
    assert all(r.latency_ms is None for r in b.results.values())

    s = WaveOrchestrator(_plan(tmp_path / "s", ServingMode.SYNC), tmp_path / "s")
    s.run_all()
    assert all(r.latency_ms is not None for r in s.results.values() if r.ok)


def test_batch_refused_when_adapter_lacks_batch_path(tmp_path):
    class NoBatch(MockAdapter):
        def supports_batch(self, model_id): return False

    plan = _plan(tmp_path, adapter=NoBatch(seed=6))
    with pytest.raises(RuntimeError, match="no batch path"):
        WaveOrchestrator(plan, tmp_path).run_all()


def test_unexpected_custom_id_is_rejected(tmp_path):
    """A provider returning an id we never sent must fail loudly."""
    class Rogue(MockAdapter):
        def fetch_batch(self, handle):
            out = super().fetch_batch(handle)
            out[0].rid = RequestID(Pipeline.P2, "GHOST", "inc", 1, "extract")
            return out

    plan = _plan(tmp_path, adapter=Rogue(seed=8))
    with pytest.raises(RuntimeError, match="unknown custom_ids"):
        WaveOrchestrator(plan, tmp_path).run_all()


def test_dropped_result_is_detected(tmp_path):
    class Lossy(MockAdapter):
        def fetch_batch(self, handle):
            return super().fetch_batch(handle)[:-1]

    plan = _plan(tmp_path, adapter=Lossy(seed=11))
    with pytest.raises(RuntimeError, match="missing from"):
        WaveOrchestrator(plan, tmp_path).run_all()


def test_execution_order_index_is_recorded(tmp_path):
    plan = _plan(tmp_path)
    orch = WaveOrchestrator(plan, tmp_path)
    orch.run_all()
    assert all(r.execution_order_index is not None for r in orch.results.values())


def test_results_persisted_per_wave(tmp_path):
    plan = _plan(tmp_path)
    WaveOrchestrator(plan, tmp_path).run_all()
    for stage in ("extract", "reason", "classify"):
        assert (tmp_path / f"p2_contractnli_primary_{stage}.jsonl").exists()
        assert (tmp_path / f"p2_contractnli_primary_{stage}_meta.json").exists()
