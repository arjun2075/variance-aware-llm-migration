"""Tests for reconstructing runs from the call ledger."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vaml.analysis.assemble import (P1_STAGES, P2_STAGES, acceptance_summary,  # noqa: E402
                                    assemble_runs)


def call(pipeline, task, model, rep, stage, partition="primary", *,
         text='{"ok": 1}', error=None, returned="gpt-4o-2024-11-20",
         mismatch=False, ptok=10, ctok=20, lat=100.0, retries=0):
    return {
        "rid": f"{pipeline}|{partition}|{task}|{model}|r{rep}|{stage}",
        "text": text, "error": error, "returned_model_id": returned,
        "prompt_tokens": ptok, "completion_tokens": ctok, "latency_ms": lat,
        "retry_count": retries,
        "extra": {"canonical_model_mismatch": mismatch},
    }


def p1_run(task="t1", model="m1", rep=1, **kw):
    good3 = ('{"ratings":{"technical_execution":"meets_expectations",'
             '"delivery_consistency":"meets_expectations",'
             '"collaboration":"meets_expectations","impact":"meets_expectations"},'
             '"strengths":["s"],"opportunities":["o"],"risks":["r"],'
             '"summary":"sum"}')
    good4 = '{"recommendations":[{"action":"a"}]}'
    texts = {"synthesis": good3, "deepen": good4}
    return [call("p1_assessment", task, model, rep, s,
                 text=texts.get(s, '{"x":1}'), **kw) for s in P1_STAGES]


def test_complete_run_is_accepted():
    runs = assemble_runs(p1_run())
    assert len(runs) == 1
    assert runs[0].accepted and runs[0].exclusion_reason is None
    assert runs[0].stages_present == 4


def test_incomplete_run_is_excluded():
    runs = assemble_runs(p1_run()[:2])
    assert not runs[0].accepted
    assert "incomplete_run_2_of_4" in runs[0].exclusion_reason


def test_transport_failure_excludes_run():
    calls = p1_run()
    calls[1]["error"] = "http_status_500"
    runs = assemble_runs(calls)
    assert not runs[0].accepted
    assert runs[0].exclusion_reason.startswith("transport_failure:")


def test_canonical_mismatch_excludes_run():
    calls = p1_run()
    calls[0]["extra"]["canonical_model_mismatch"] = True
    runs = assemble_runs(calls)
    assert not runs[0].accepted
    assert runs[0].exclusion_reason == "canonical_model_mismatch"
    assert runs[0].provenance_ok is False


def test_schema_violation_does_NOT_exclude():
    """Frozen rule: schema violations are DATA, not exclusion criteria."""
    calls = p1_run()
    calls[2]["text"] = '{"ratings":{"technical_execution":"bogus"}}'
    runs = assemble_runs(calls)
    assert runs[0].accepted is True
    assert runs[0].schema_valid is False
    assert runs[0].schema_violations


def test_parse_failure_does_NOT_exclude():
    calls = p1_run()
    calls[2]["text"] = "not json at all"
    runs = assemble_runs(calls)
    assert runs[0].accepted is True
    assert "synthesis" in runs[0].parse_failures


def test_runs_are_grouped_by_full_identity():
    calls = p1_run(task="t1", rep=1) + p1_run(task="t1", rep=2) + \
            p1_run(task="t2", rep=1) + p1_run(task="t1", model="m2", rep=1)
    runs = assemble_runs(calls)
    assert len(runs) == 4
    assert len({(r.task_id, r.model_key, r.repetition) for r in runs}) == 4


def test_partitions_do_not_merge():
    calls = p1_run() + [c | {"rid": c["rid"].replace("|primary|", "|stress|")}
                        for c in p1_run()]
    runs = assemble_runs(calls)
    assert {r.partition for r in runs} == {"primary", "stress"}
    assert len(runs) == 2


def test_operational_totals_are_summed_across_stages():
    runs = assemble_runs(p1_run())
    assert runs[0].total_prompt_tokens == 40      # 4 stages x 10
    assert runs[0].total_completion_tokens == 80
    assert runs[0].total_latency_ms == 400.0


def test_retries_are_summed():
    calls = p1_run()
    calls[0]["retry_count"] = 2
    calls[3]["retry_count"] = 1
    assert assemble_runs(calls)[0].total_retries == 3


# ---------------- P2 grounding ----------------

def p2_run(label="Entailment", cited=None, task="pt1"):
    cited = ["the quick brown fox"] if cited is None else cited
    texts = {
        "extract_evidence": '{"extracted_spans":[{"text":"the quick brown fox"}]}',
        "classify": '{"label":"%s","cited_spans":%s}' % (
            label, __import__("json").dumps(cited)),
        "verify": '{"internally_consistent":true}',
    }
    return [call("p2_contractnli", task, "m1", 1, s,
                 text=texts.get(s, '{"x":1}')) for s in P2_STAGES]


def test_p2_grounding_computed_against_corpus():
    corpus = {"pt1": {"document_text": "a b the quick brown fox c d"}}
    runs = assemble_runs(p2_run(), corpus)
    st = runs[0].structured
    assert st["spans_grounded"] == 1 and st["spans_cited"] == 1
    assert st["grounding_rate"] == 1.0


def test_p2_hallucinated_span_lowers_grounding():
    corpus = {"pt1": {"document_text": "a b c d"}}
    runs = assemble_runs(p2_run(cited=["not in the document"]), corpus)
    assert runs[0].structured["grounding_rate"] == 0.0


def test_p2_invalid_label_is_schema_violation_not_exclusion():
    corpus = {"pt1": {"document_text": "x"}}
    runs = assemble_runs(p2_run(label="Maybe"), corpus)
    assert runs[0].accepted is True
    assert runs[0].schema_valid is False
    assert runs[0].structured["label"] is None


# ---------------- summary ----------------

def test_acceptance_summary_counts():
    calls = p1_run(task="t1") + p1_run(task="t2")[:2]
    s = acceptance_summary(assemble_runs(calls))
    assert s["total_runs"] == 2 and s["accepted"] == 1 and s["excluded"] == 1


def test_summary_reports_rates_by_model():
    calls = p1_run(task="t1", model="mA")
    calls[2]["text"] = "garbage"
    calls += p1_run(task="t2", model="mB")
    s = acceptance_summary(assemble_runs(calls))
    assert "mA" in s["schema_violation_rate_by_model"]
    assert "mB" in s["parse_failure_rate_by_model"]
