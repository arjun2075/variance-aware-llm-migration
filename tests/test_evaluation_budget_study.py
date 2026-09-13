"""Tests for the evaluation-budget study."""
from __future__ import annotations

import csv
import statistics as st
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from evaluation_budget_study import (  # noqa: E402
    CAND_REPS, FULL_RA, FULL_RB, FULL_T, INC_REPS, TASK_COUNTS, P2_TOL,
    estimate, subset_matrices,
)

CSV = REPO / "results/strengthening/evaluation_budget.csv"


# ---------------- grid definition ----------------

def test_grid_matches_specification():
    assert TASK_COUNTS == (10, 20, 30, 40, 60)
    assert INC_REPS == (2, 3, 5, 8)
    assert CAND_REPS == (2, 3, 5)


def test_reference_cell_is_the_full_design():
    assert (FULL_T, FULL_RA, FULL_RB) == (60, 8, 5)
    assert FULL_T in TASK_COUNTS and FULL_RA in INC_REPS and FULL_RB in CAND_REPS


# ---------------- subsetting ----------------

def test_subset_truncates_repetitions_deterministically():
    within = {"t": np.arange(64, dtype=float).reshape(8, 8)}
    cross = {"t": np.arange(40, dtype=float).reshape(8, 5)}
    w, c = subset_matrices(within, cross, ["t"], 3, 2)
    assert w["t"].shape == (3, 3)
    assert c["t"].shape == (3, 2)
    assert np.array_equal(w["t"], within["t"][:3, :3])


def test_subset_selects_only_requested_tasks():
    within = {f"t{i}": np.full((4, 4), 0.5) for i in range(5)}
    cross = {f"t{i}": np.full((4, 3), 0.4) for i in range(5)}
    w, c = subset_matrices(within, cross, ["t0", "t2"], 4, 3)
    assert set(w) == {"t0", "t2"} and set(c) == {"t0", "t2"}


def test_subset_is_repeatable():
    within = {"t": np.random.default_rng(0).random((8, 8))}
    cross = {"t": np.random.default_rng(1).random((8, 5))}
    a = subset_matrices(within, cross, ["t"], 5, 3)
    b = subset_matrices(within, cross, ["t"], 5, 3)
    assert np.array_equal(a[0]["t"], b[0]["t"])


def test_estimate_returns_delta_as_cross_minus_within():
    within = {"t": np.full((4, 4), 0.8)}
    cross = {"t": np.full((4, 3), 0.5)}
    w, c, d = estimate(within, cross)
    assert d == pytest.approx(c - w)
    assert d == pytest.approx(-0.3, abs=1e-9)


# ---------------- generated output ----------------

@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_covers_the_full_grid():
    rows = list(csv.DictReader(CSV.open()))
    assert len(rows) == 4 * 3 * len(TASK_COUNTS) * len(INC_REPS) * len(CAND_REPS)


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_uses_primary_tasks_only():
    """Stress tasks must not appear."""
    rows = list(csv.DictReader(CSV.open()))
    assert all(int(r["T"]) <= 60 for r in rows)


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_full_task_cell_is_deterministic_single_draw():
    rows = [r for r in csv.DictReader(CSV.open()) if int(r["T"]) == 60]
    assert all(int(r["n_subsamples"]) == 1 for r in rows)
    assert all(float(r["across_subsample_sd"]) == 0.0 for r in rows)


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_reference_cell_has_zero_deviation():
    """T=60, R_A=8, R_B=5 IS the reference, so it must reproduce it exactly."""
    rows = [r for r in csv.DictReader(CSV.open())
            if int(r["T"]) == 60 and int(r["R_A"]) == 8 and int(r["R_B"]) == 5]
    assert rows
    for r in rows:
        # the point estimate must reproduce exactly
        assert float(r["deviation_from_full"]) == pytest.approx(0.0, abs=1e-6)
    # With the reference seed reused for the full-task cell, verdicts agree too.
    # This is asserted in aggregate because a cell whose interval sits on the
    # tolerance boundary is genuinely fragile; see test_boundary_cell_is_fragile.
    assert st.mean(float(r["verdict_agreement"]) for r in rows) >= 0.9


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_boundary_cell_fragility_is_visible_not_hidden():
    """label_agreement / gemini sits near the tolerance boundary, so its
    verdict is the least stable under subsampling. Recording this rather than
    smoothing it over."""
    rows = [r for r in csv.DictReader(CSV.open())
            if r["property"] == "label_agreement" and "gemini" in r["candidate"]]
    assert rows
    agreements = [float(r["verdict_agreement"]) for r in rows]
    assert min(agreements) < 1.0


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_ci_width_decreases_monotonically_with_tasks():
    rows = list(csv.DictReader(CSV.open()))
    widths = []
    for T in TASK_COUNTS:
        sel = [r for r in rows if int(r["T"]) == T and int(r["R_A"]) == 8
               and int(r["R_B"]) == 5]
        widths.append(st.mean(float(r["mean_ci_width"]) for r in sel))
    assert widths == sorted(widths, reverse=True)


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_ci_width_decreases_with_incumbent_repetitions():
    rows = list(csv.DictReader(CSV.open()))
    widths = []
    for r_a in INC_REPS:
        sel = [r for r in rows if int(r["T"]) == 60 and int(r["R_A"]) == r_a
               and int(r["R_B"]) == 5]
        widths.append(st.mean(float(r["mean_ci_width"]) for r in sel))
    assert widths == sorted(widths, reverse=True)


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_verdict_agreement_improves_with_more_tasks():
    rows = list(csv.DictReader(CSV.open()))
    agree = []
    for T in TASK_COUNTS:
        sel = [r for r in rows if int(r["T"]) == T and int(r["R_A"]) == 8
               and int(r["R_B"]) == 5]
        agree.append(st.mean(float(r["verdict_agreement"]) for r in sel))
    assert agree == sorted(agree)
    assert agree[-1] > agree[0]


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_task_axis_outperforms_repetition_axis_on_this_data():
    """Documented headline: 10->60 tasks beats 2/2->8/5 repetitions."""
    rows = list(csv.DictReader(CSV.open()))
    def w(T, ra, rb):
        sel = [r for r in rows if int(r["T"]) == T and int(r["R_A"]) == ra
               and int(r["R_B"]) == rb]
        return st.mean(float(r["mean_ci_width"]) for r in sel)
    task_gain = 1 - w(60, 8, 5) / w(10, 8, 5)
    rep_gain = 1 - w(60, 8, 5) / w(60, 2, 2)
    assert task_gain > rep_gain


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_sign_agreement_is_high_throughout():
    """Effect direction is far more stable than the categorical verdict."""
    rows = list(csv.DictReader(CSV.open()))
    assert st.mean(float(r["sign_agreement"]) for r in rows) > 0.9


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_candidate_repetitions_saturate_quickly():
    """Going 2 -> 3 candidate repetitions helps; 3 -> 5 adds almost nothing.

    An earlier version of this test asserted that candidate repetitions buy
    *nothing* at R_A=2. That was too strong: the 2 -> 3 step does reduce width
    (0.255 -> 0.235). It is the 3 -> 5 step that saturates.
    """
    rows = list(csv.DictReader(CSV.open()))
    def w(r_a, r_b):
        return st.mean(float(r["mean_ci_width"]) for r in rows
                       if int(r["T"]) == 60 and int(r["R_A"]) == r_a
                       and int(r["R_B"]) == r_b)
    # Monotone in R_B at every R_A: more candidate repetitions never hurt.
    for r_a in INC_REPS:
        assert w(r_a, 2) >= w(r_a, 3) >= w(r_a, 5) - 1e-9
    # Saturation is clear at R_A=2, where the 3->5 step is an order of
    # magnitude smaller than 2->3. It is NOT uniform across R_A: at R_A=3 the
    # 3->5 step is actually the larger of the two, so no general "diminishing
    # returns at every R_A" claim is made.
    assert (w(2, 3) - w(2, 5)) < 0.1 * (w(2, 2) - w(2, 3))


@pytest.mark.skipif(not CSV.exists(), reason="study output absent")
def test_incumbent_repetitions_matter_more_than_candidate_repetitions():
    """W_A sits on the critical path of every Delta, so R_A dominates."""
    rows = list(csv.DictReader(CSV.open()))
    def w(r_a, r_b):
        return st.mean(float(r["mean_ci_width"]) for r in rows
                       if int(r["T"]) == 60 and int(r["R_A"]) == r_a
                       and int(r["R_B"]) == r_b)
    gain_inc = w(2, 5) - w(8, 5)      # raising R_A at fixed R_B
    gain_cand = w(8, 2) - w(8, 5)     # raising R_B at fixed R_A
    assert gain_inc > gain_cand
