"""Tests for the P2 tolerance decision curves."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from plot_tolerance_decision_curves import (  # noqa: E402
    CLASSES, build_transition_rows, classify, load_p2_cells,
    transition_points, verify_against_frozen,
)

FROZEN = REPO / "results/analysis/pairwise_results.json"


# ---------------- classification rule ----------------

@pytest.mark.parametrize("lo,hi,tau,exp", [
    (-0.30, -0.20, 0.10, "rejected"),        # entirely below -tau
    (0.20, 0.30, 0.10, "rejected"),          # entirely above +tau
    (-0.08, 0.08, 0.10, "demonstrated"),     # entirely inside
    (-0.10, 0.10, 0.10, "demonstrated"),     # exactly on both boundaries
    (-0.30, -0.05, 0.10, "inconclusive"),    # straddles -tau
    (-0.05, 0.30, 0.10, "inconclusive"),     # straddles +tau
    (-0.50, 0.50, 0.10, "inconclusive"),     # straddles both
])
def test_classify(lo, hi, tau, exp):
    assert classify(lo, hi, exp and tau) == exp


def test_boundary_is_inclusive_for_demonstrated():
    assert classify(-0.10, 0.10, 0.10) == "demonstrated"
    assert classify(-0.1000001, 0.10, 0.10) == "inconclusive"


def test_rejection_requires_strict_exceedance():
    assert classify(-0.30, -0.10, 0.10) == "inconclusive"
    assert classify(-0.30, -0.1000001, 0.10) == "rejected"


def test_tau_zero_rejects_any_interval_excluding_zero():
    assert classify(-0.20, -0.05, 0.0) == "rejected"
    assert classify(-0.20, 0.05, 0.0) == "inconclusive"


def test_classification_is_monotone_in_tau():
    """As tau grows a cell may only move rejected -> inconclusive ->
    demonstrated, never backwards."""
    lo, hi = -0.30, -0.05
    rank = {c: i for i, c in enumerate(CLASSES)}
    seq = [rank[classify(lo, hi, t / 1000)] for t in range(0, 401)]
    assert seq == sorted(seq)


# ---------------- transition points ----------------

def test_transitions_for_interval_below_zero():
    """The common case: both endpoints negative."""
    tp = transition_points(-0.295, -0.125)
    assert tp["rejected_until_tau"] == pytest.approx(0.125)   # -ci_upper
    assert tp["demonstrated_from_tau"] == pytest.approx(0.295)  # |ci_lower|
    assert tp["inconclusive_window"] == pytest.approx(0.170)


def test_transitions_agree_with_classify_on_both_sides():
    lo, hi = -0.295, -0.125
    tp = transition_points(lo, hi)
    eps = 1e-6
    assert classify(lo, hi, tp["rejected_until_tau"] - eps) == "rejected"
    assert classify(lo, hi, tp["rejected_until_tau"] + eps) == "inconclusive"
    assert classify(lo, hi, tp["demonstrated_from_tau"] - eps) == "inconclusive"
    assert classify(lo, hi, tp["demonstrated_from_tau"] + eps) == "demonstrated"


def test_interval_straddling_zero_is_never_rejected():
    tp = transition_points(-0.10, 0.05)
    assert tp["rejected_until_tau"] == 0.0
    assert classify(-0.10, 0.05, 0.0) == "inconclusive"


def test_transitions_for_interval_above_zero():
    tp = transition_points(0.12, 0.30)
    assert tp["rejected_until_tau"] == pytest.approx(0.12)
    assert tp["demonstrated_from_tau"] == pytest.approx(0.30)


def test_demonstrated_threshold_is_the_larger_absolute_endpoint():
    assert transition_points(-0.40, 0.10)["demonstrated_from_tau"] == pytest.approx(0.40)
    assert transition_points(-0.10, 0.40)["demonstrated_from_tau"] == pytest.approx(0.40)


# ---------------- frozen-data integration ----------------

@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_loads_exactly_twelve_p2_cells():
    assert len(load_p2_cells(FROZEN)) == 12


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_derived_verdicts_match_the_frozen_verdicts():
    """The decisive integrity check: re-deriving at the declared tolerance must
    reproduce the confirmatory verdicts exactly."""
    assert verify_against_frozen(load_p2_cells(FROZEN), 0.05) == []


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_uses_frozen_endpoints_verbatim():
    cells = load_p2_cells(FROZEN)
    raw = json.loads(FROZEN.read_text())["P2"]
    for c, r in zip(cells, raw):
        assert c["ci_lower"] == r["ci_lower"]
        assert c["ci_upper"] == r["ci_upper"]
        assert c["delta"] == r["delta"]


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_does_not_mutate_frozen_input():
    before = FROZEN.read_bytes()
    build_transition_rows(load_p2_cells(FROZEN))
    assert FROZEN.read_bytes() == before


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_every_p2_interval_lies_below_zero():
    """All observed P2 deltas are negative, so every cell follows the
    rejected -> inconclusive -> demonstrated path."""
    for c in load_p2_cells(FROZEN):
        assert c["ci_upper"] < 0


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_transition_csv_shape_and_determinism(tmp_path):
    outs = []
    for _ in range(2):
        p = tmp_path / "t.csv"
        r = subprocess.run(
            [sys.executable, str(REPO / "analysis/plot_tolerance_decision_curves.py"),
             "--csv", str(p), "--pdf", str(tmp_path / "f.pdf"),
             "--png", str(tmp_path / "f.png")], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(p.read_text())
    assert outs[0] == outs[1]
    rows = list(csv.DictReader((tmp_path / "t.csv").open()))
    assert len(rows) == 12
    for col in ("property", "candidate", "delta", "ci_lower", "ci_upper",
                "rejected_until_tau", "demonstrated_from_tau",
                "inconclusive_window"):
        assert col in rows[0]


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_transition_ordering_holds_for_every_cell():
    """A cell must always pass rejected -> inconclusive -> demonstrated in that
    order, with a non-empty inconclusive window."""
    for r in build_transition_rows(load_p2_cells(FROZEN)):
        assert r["rejected_until_tau"] >= 0.0
        assert r["demonstrated_from_tau"] > r["rejected_until_tau"]
        assert r["inconclusive_window"] > 0.0


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_two_llama4_span_cells_stay_rejected_past_the_sweep():
    """The largest effects remain rejected beyond tau = 0.20 — these are the
    cells the tolerance-sensitivity analysis found stable across the sweep."""
    rows = build_transition_rows(load_p2_cells(FROZEN))
    beyond = [r for r in rows if r["rejected_until_tau"] > 0.20]
    assert len(beyond) == 2
    assert all("llama4" in r["candidate"] for r in beyond)
    assert all("span" in r["property"] for r in beyond)


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_only_two_label_cells_reach_demonstrated_within_the_sweep():
    """Exactly two cells become 'demonstrated' at some tau <= 0.20, and both are
    label_agreement — the smallest effects, consistent with their inconclusive
    verdicts at the declared 0.05 tolerance. Every span cell needs tau > 0.20.
    """
    rows = build_transition_rows(load_p2_cells(FROZEN))
    inside = [r for r in rows if r["demonstrated_from_tau"] <= 0.20]
    assert len(inside) == 2
    assert all(r["property"] == "label_agreement" for r in inside)
    spans = [r for r in rows if "span" in r["property"]]
    assert all(r["demonstrated_from_tau"] > 0.20 for r in spans)
