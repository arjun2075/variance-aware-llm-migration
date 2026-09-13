"""Tests for invalid-output sensitivity across three policies."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from invalid_output_sensitivity import (  # noqa: E402
    P2_LABELS, POLICIES, PROPERTY_STAGE, apply_policy, run_is_valid_for,
)

CSV = REPO / "results/strengthening/invalid_output_sensitivity.csv"


class FakeRun:
    def __init__(self, label=None, parse_failures=None):
        self.structured = {"label": label}
        self.parse_failures = parse_failures or {}


# ---------------- per-property validity ----------------

def test_label_validity_requires_a_declared_label():
    assert run_is_valid_for(FakeRun(label="Entailment"), "label_agreement")
    assert not run_is_valid_for(FakeRun(label=None), "label_agreement")
    assert not run_is_valid_for(FakeRun(label="Maybe"), "label_agreement")


def test_span_validity_depends_on_the_producing_stage():
    ok = FakeRun(label="Entailment")
    bad = FakeRun(label="Entailment", parse_failures={"extract_evidence": "x"})
    assert run_is_valid_for(ok, "extracted_span_set_agreement")
    assert not run_is_valid_for(bad, "extracted_span_set_agreement")
    # a failure in an unrelated stage must not invalidate this property
    assert run_is_valid_for(bad, "label_agreement")


def test_validity_is_judged_per_property_not_globally():
    """The spec forbids deleting a run because an unrelated stage is invalid."""
    r = FakeRun(label="Entailment", parse_failures={"extract_evidence": "x"})
    assert run_is_valid_for(r, "label_agreement")
    assert run_is_valid_for(r, "cited_span_set_agreement")
    assert not run_is_valid_for(r, "extracted_span_set_agreement")


def test_every_property_maps_to_a_stage():
    assert set(PROPERTY_STAGE) == {"label_agreement", "cited_span_set_agreement",
                                   "extracted_span_set_agreement"}


def test_declared_labels_are_the_frozen_three():
    assert P2_LABELS == {"Entailment", "Contradiction", "NotMentioned"}


# ---------------- policy mechanics ----------------

def _fixture():
    within = {"t": np.array([[np.nan, 1.0, 1.0],
                             [1.0, np.nan, 1.0],
                             [1.0, 1.0, np.nan]])}
    cross = {"t": np.ones((3, 2))}
    valid_a = {"t": np.array([True, True, False])}   # third incumbent invalid
    valid_b = {"t": np.array([True, True])}
    return within, cross, valid_a, valid_b


def test_policy_A_leaves_matrices_untouched():
    w, c, va, vb = _fixture()
    w2, c2 = apply_policy(w, c, va, vb, "A_frozen")
    assert w2 is w and c2 is c


def test_policy_B_scores_invalid_pairs_zero():
    w, c, va, vb = _fixture()
    w2, c2 = apply_policy(w, c, va, vb, "B_conservative_failure")
    assert w2["t"][2, 0] == 0.0 and w2["t"][0, 2] == 0.0
    assert np.all(c2["t"][2, :] == 0.0)


def test_policy_C_drops_invalid_pairs():
    w, c, va, vb = _fixture()
    w2, c2 = apply_policy(w, c, va, vb, "C_complete_case")
    assert np.isnan(w2["t"][2, 0]) and np.isnan(w2["t"][0, 2])
    assert np.all(np.isnan(c2["t"][2, :]))


def test_policy_B_and_C_differ_only_on_invalid_entries():
    w, c, va, vb = _fixture()
    b, _ = apply_policy(w, c, va, vb, "B_conservative_failure")
    cc, _ = apply_policy(w, c, va, vb, "C_complete_case")
    # valid pair is identical under both
    assert b["t"][0, 1] == cc["t"][0, 1] == 1.0
    # invalid pair differs: 0 vs dropped
    assert b["t"][2, 0] == 0.0 and np.isnan(cc["t"][2, 0])


def test_all_policies_keep_the_diagonal_excluded():
    w, c, va, vb = _fixture()
    for pol in ("B_conservative_failure", "C_complete_case"):
        w2, _ = apply_policy(w, c, va, vb, pol)
        assert np.all(np.isnan(np.diag(w2["t"])))


def test_policy_B_lowers_agreement_relative_to_C():
    """Scoring failures as 0 must not raise the agreement estimate."""
    w, c, va, vb = _fixture()
    b, _ = apply_policy(w, c, va, vb, "B_conservative_failure")
    cc, _ = apply_policy(w, c, va, vb, "C_complete_case")
    iu = np.triu_indices(3, k=1)
    mb, mc = b["t"][iu], cc["t"][iu]
    assert np.nanmean(mb) <= np.nanmean(mc)


def test_three_policies_declared():
    assert POLICIES == ("A_frozen", "B_conservative_failure", "C_complete_case")


# ---------------- generated output ----------------

@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_covers_twelve_cells_times_three_policies():
    assert len(list(csv.DictReader(CSV.open()))) == 36


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_policy_A_reproduces_the_frozen_primary_results():
    """The decisive precondition: the frozen policy must reproduce itself."""
    rows = [r for r in csv.DictReader(CSV.open()) if r["policy"] == "A_frozen"]
    assert len(rows) == 12
    for r in rows:
        assert float(r["delta"]) == pytest.approx(float(r["frozen_delta"]),
                                                  abs=1e-6)
        assert r["verdict"] == r["frozen_verdict"]


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_observed_invalid_rate_is_recorded():
    rows = list(csv.DictReader(CSV.open()))
    assert all("invalid_fraction" in r for r in rows)
    assert max(float(r["invalid_fraction"]) for r in rows) < 0.05


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_no_sign_changes_under_any_policy():
    for r in csv.DictReader(CSV.open()):
        assert r["sign_matches_frozen"] == "True"


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_span_label_asymmetry_survives_every_policy():
    import statistics as st
    rows = list(csv.DictReader(CSV.open()))
    for pol in POLICIES:
        sp = [abs(float(r["delta"])) for r in rows
              if r["policy"] == pol and "span" in r["property"]]
        lb = [abs(float(r["delta"])) for r in rows
              if r["policy"] == pol and r["property"] == "label_agreement"]
        assert st.mean(sp) > st.mean(lb)
