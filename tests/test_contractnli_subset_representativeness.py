"""Tests for the ContractNLI subset representativeness check."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from contractnli_subset_representativeness import (  # noqa: E402
    MAX_DOC_CHARS, SMD_NEGLIGIBLE, SMD_SMALL, VALID_LABELS, categorical_rows,
    continuous_rows, eligible_pool, interpret, quantiles, selected_set, smd,
)

CSV = REPO / "results/strengthening/contractnli_subset_representativeness.csv"
SOURCE = REPO / "data/raw/contractnli/train.json"
SELECTED = REPO / "corpora/pipeline2/p2_primary.jsonl"


# ---------------- statistics ----------------

def test_smd_is_zero_for_identical_samples():
    assert smd([1.0, 2, 3, 4], [1.0, 2, 3, 4]) == pytest.approx(0.0)


def test_smd_sign_follows_selected_minus_pool():
    assert smd([5.0, 6, 7], [1.0, 2, 3]) > 0
    assert smd([1.0, 2, 3], [5.0, 6, 7]) < 0


def test_smd_scales_by_pooled_sd():
    """A one-SD shift gives |SMD| ~ 1."""
    a = [10.0, 11, 12, 13, 14]
    b = [x - 1.5811 for x in a]      # shift by ~1 pooled SD
    assert abs(smd(a, b)) == pytest.approx(1.0, abs=0.15)


def test_smd_handles_degenerate_input():
    import math
    assert math.isnan(smd([1.0], [1.0, 2.0]))


@pytest.mark.parametrize("d,exp", [
    (0.0, "negligible"), (0.05, "negligible"), (0.09, "negligible"),
    (0.10, "small"), (0.25, "small"), (0.30, "moderate_or_larger"),
    (-0.45, "moderate_or_larger"),
])
def test_interpret_thresholds(d, exp):
    assert interpret(d) == exp


def test_interpretation_is_sign_agnostic():
    assert interpret(0.25) == interpret(-0.25)


def test_quantiles_are_ordered():
    q = quantiles([float(x) for x in range(100)])
    assert q["p10"] <= q["p25"] <= q["p50"] <= q["p75"] <= q["p90"]


# ---------------- eligibility rules match the frozen sampler ----------------

def test_eligibility_constants_match_the_build_script():
    src = (REPO / "scripts/build_p2_corpus.py").read_text()
    assert f"MAX_DOC_CHARS = {MAX_DOC_CHARS:_}".replace("_", "_") in src \
        or "MAX_DOC_CHARS = 60_000" in src
    for lab in VALID_LABELS:
        assert lab in src


def test_pool_excludes_over_long_documents(tmp_path):
    data = {"documents": [
        {"id": "a", "text": "x" * 100, "spans": [[0, 10]],
         "annotation_sets": [{"annotations": {"h1": {"choice": "Entailment",
                                                     "spans": [0]}}}]},
        {"id": "b", "text": "x" * (MAX_DOC_CHARS + 1), "spans": [[0, 10]],
         "annotation_sets": [{"annotations": {"h1": {"choice": "Entailment",
                                                     "spans": [0]}}}]},
    ], "labels": {}}
    p = tmp_path / "s.json"; p.write_text(json.dumps(data))
    pool = eligible_pool(p)
    assert {r["document_id"] for r in pool} == {"a"}


def test_pool_excludes_invalid_labels(tmp_path):
    data = {"documents": [
        {"id": "a", "text": "abc", "spans": [],
         "annotation_sets": [{"annotations": {
             "h1": {"choice": "Maybe"}, "h2": {"choice": "Entailment"}}}]},
    ], "labels": {}}
    p = tmp_path / "s.json"; p.write_text(json.dumps(data))
    pool = eligible_pool(p)
    assert len(pool) == 1 and pool[0]["gold_label"] == "Entailment"


# ---------------- by-design flagging ----------------

def test_gold_label_rows_are_flagged_by_design():
    sel = [{"gold_label": "Entailment", "has_evidence": True}] * 3
    pool = [{"gold_label": "Entailment", "has_evidence": True}] * 10
    rows = categorical_rows(sel, pool)
    assert all(r["by_design"] for r in rows if r["variable"].startswith("gold_label"))
    assert not any(r["by_design"] for r in rows
                   if r["variable"].startswith("has_evidence"))


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_selected_labels_are_balanced_as_designed():
    rows = [r for r in csv.DictReader(CSV.open())
            if r["variable"].startswith("gold_label")]
    assert len(rows) == 3
    for r in rows:
        assert float(r["selected_proportion"]) == pytest.approx(1 / 3, abs=0.02)


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_label_difference_is_marked_by_design_not_flagged_as_a_problem():
    """The 20/20/20 balance necessarily diverges from the natural distribution."""
    rows = [r for r in csv.DictReader(CSV.open())
            if r["variable"].startswith("gold_label")]
    assert all(r["by_design"] == "True" for r in rows)
    assert any(float(r["absolute_pp_difference"]) > 10 for r in rows)


# ---------------- generated output ----------------

@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_reports_selected_sixty_against_a_large_pool():
    rows = list(csv.DictReader(CSV.open()))
    assert all(int(r["selected_n"]) == 60 for r in rows if r["selected_n"])
    assert all(int(r["pool_n"]) > 1000 for r in rows if r["pool_n"])


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_no_continuous_variable_differs_moderately():
    """Headline: aside from the intentional label balance, nothing is atypical."""
    cont = [r for r in csv.DictReader(CSV.open()) if r["type"] == "continuous"]
    assert cont
    for r in cont:
        assert abs(float(r["standardized_mean_difference"])) < SMD_SMALL


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_document_length_is_the_largest_non_design_difference():
    cont = [r for r in csv.DictReader(CSV.open()) if r["type"] == "continuous"]
    worst = max(cont, key=lambda r: abs(float(r["standardized_mean_difference"])))
    assert worst["variable"] == "n_doc_chars"
    assert worst["smd_interpretation"] == "small"


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_evidence_prevalence_difference_is_modest():
    rows = [r for r in csv.DictReader(CSV.open())
            if r["variable"].startswith("has_evidence")]
    assert rows
    assert all(float(r["absolute_pp_difference"]) < 10 for r in rows)


@pytest.mark.skipif(not SELECTED.exists(), reason="corpus absent")
def test_does_not_modify_the_frozen_corpus():
    before = SELECTED.read_bytes()
    selected_set(SELECTED)
    assert SELECTED.read_bytes() == before
