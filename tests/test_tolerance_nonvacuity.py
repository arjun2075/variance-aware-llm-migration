"""Tests for the tolerance non-vacuity diagnostic."""
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from tolerance_nonvacuity import (  # noqa: E402
    PILOT_TAU, build_rows, delta_bounds, is_vacuous, load_frozen_w_a,
    min_acceptable_cross_agreement, vacuity_ratio,
)


# ---------------- algebraic bounds ----------------

@pytest.mark.parametrize("w_a", [0.0, 0.04, 0.5, 0.8533, 1.0])
def test_delta_bounds_are_minus_wa_to_one_minus_wa(w_a):
    lo, hi = delta_bounds(w_a)
    assert lo == pytest.approx(-w_a)
    assert hi == pytest.approx(1.0 - w_a)


def test_delta_lower_bound_attained_at_zero_cross_agreement():
    """Delta = C_AB - W_A, so C_AB = 0 gives exactly -W_A."""
    for w_a in (0.0, 0.25, 0.9286, 1.0):
        assert delta_bounds(w_a)[0] == pytest.approx(0.0 - w_a)


def test_delta_upper_bound_attained_at_perfect_cross_agreement():
    for w_a in (0.0, 0.25, 0.9286, 1.0):
        assert delta_bounds(w_a)[1] == pytest.approx(1.0 - w_a)


def test_bounds_width_is_always_one():
    for w_a in (0.0, 0.3, 0.77, 1.0):
        lo, hi = delta_bounds(w_a)
        assert hi - lo == pytest.approx(1.0)


# ---------------- required boundary cases ----------------

def test_boundary_w_a_zero():
    """W_A = 0: Delta is pinned at [0, 1]; ANY tau is vacuous."""
    assert delta_bounds(0.0) == (0.0, 1.0)
    assert math.isinf(vacuity_ratio(0.0, PILOT_TAU))
    assert is_vacuous(0.0, PILOT_TAU) is True
    assert is_vacuous(0.0, 0.0) is True          # even tau = 0
    assert min_acceptable_cross_agreement(0.0, PILOT_TAU) == 0.0


def test_boundary_w_a_below_tau():
    """W_A < tau: tolerance accepts complete disagreement."""
    w_a, tau = 0.04, 0.10
    assert vacuity_ratio(w_a, tau) == pytest.approx(2.5)
    assert vacuity_ratio(w_a, tau) > 1.0
    assert is_vacuous(w_a, tau) is True
    assert min_acceptable_cross_agreement(w_a, tau) == 0.0
    # the lower bound of Delta is inside the tolerance region
    assert delta_bounds(w_a)[0] >= -tau


def test_boundary_w_a_equals_tau():
    """W_A == tau: ratio exactly 1, and the case is vacuous (>= not >)."""
    w_a = tau = 0.10
    assert vacuity_ratio(w_a, tau) == pytest.approx(1.0)
    assert is_vacuous(w_a, tau) is True
    assert min_acceptable_cross_agreement(w_a, tau) == 0.0
    # Delta = -W_A = -tau sits exactly ON the boundary, which is accepted
    assert delta_bounds(w_a)[0] == pytest.approx(-tau)


def test_boundary_w_a_above_tau():
    """W_A > tau: complete disagreement is excluded by the tolerance."""
    w_a, tau = 0.8533, 0.10
    assert vacuity_ratio(w_a, tau) == pytest.approx(tau / w_a)
    assert vacuity_ratio(w_a, tau) < 1.0
    assert is_vacuous(w_a, tau) is False
    assert min_acceptable_cross_agreement(w_a, tau) == pytest.approx(0.7533)
    assert delta_bounds(w_a)[0] < -tau          # -0.8533 < -0.10


def test_boundary_w_a_one():
    """W_A = 1: Delta in [-1, 0]; a small tau is maximally informative."""
    assert delta_bounds(1.0) == (-1.0, 0.0)
    assert vacuity_ratio(1.0, PILOT_TAU) == pytest.approx(0.10)
    assert is_vacuous(1.0, PILOT_TAU) is False
    assert min_acceptable_cross_agreement(1.0, PILOT_TAU) == pytest.approx(0.9)


# ---------------- the vacuity equivalence ----------------

@pytest.mark.parametrize("w_a,tau", [(0.5, 0.1), (0.1, 0.5), (0.3, 0.3),
                                     (1.0, 0.0), (0.25, 0.25)])
def test_is_vacuous_agrees_with_ratio_ge_one(w_a, tau):
    """is_vacuous must equal (ratio >= 1) wherever the ratio is finite."""
    if w_a > 0:
        assert is_vacuous(w_a, tau) == (vacuity_ratio(w_a, tau) >= 1.0)


@pytest.mark.parametrize("w_a,tau", [(0.04, 0.10), (0.0, 0.10), (0.10, 0.10)])
def test_vacuous_means_zero_agreement_is_accepted(w_a, tau):
    """The operational meaning: C_AB = 0 satisfies Delta >= -tau."""
    assert is_vacuous(w_a, tau)
    delta_at_zero_agreement = 0.0 - w_a
    assert delta_at_zero_agreement >= -tau


@pytest.mark.parametrize("w_a,tau", [(0.8533, 0.10), (0.9286, 0.05), (1.0, 0.10)])
def test_informative_means_zero_agreement_is_rejected(w_a, tau):
    assert not is_vacuous(w_a, tau)
    delta_at_zero_agreement = 0.0 - w_a
    assert delta_at_zero_agreement < -tau


def test_min_acceptable_cross_agreement_is_clipped_at_zero():
    """Never negative: an agreement score cannot go below 0."""
    for w_a, tau in [(0.04, 0.10), (0.0, 0.5), (0.10, 0.99)]:
        assert min_acceptable_cross_agreement(w_a, tau) == 0.0


def test_min_acceptable_cross_agreement_recovers_the_tolerance():
    """For an informative tau, C_AB at the floor gives Delta exactly -tau."""
    w_a, tau = 0.80, 0.10
    c = min_acceptable_cross_agreement(w_a, tau)
    assert (c - w_a) == pytest.approx(-tau)


# ---------------- input validation ----------------

@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan")])
def test_w_a_outside_unit_interval_rejected(bad):
    with pytest.raises(ValueError):
        delta_bounds(bad)


def test_negative_tau_rejected():
    with pytest.raises(ValueError):
        vacuity_ratio(0.5, -0.01)


def test_bool_is_not_accepted_as_numeric():
    with pytest.raises(TypeError):
        delta_bounds(True)


# ---------------- frozen-data integration ----------------

FROZEN = REPO / "results/analysis/pairwise_results.json"


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_loads_all_fourteen_properties():
    recs = load_frozen_w_a(FROZEN)
    assert len(recs) == 14
    assert all(0.0 <= r["W_A"] <= 1.0 for r in recs)


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_identifies_the_four_vacuous_properties_at_pilot_tau():
    """The degenerate exact-match pair plus the two lowest-W_A list metrics."""
    rows = build_rows(load_frozen_w_a(FROZEN), PILOT_TAU)
    vac = {r["property"] for r in rows if r["tolerance_vacuous"]}
    assert vac == {"M1.opportunity_multiset", "M1.opportunity_sequence",
                   "M2.recommendations", "M2.risks"}


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_p2_properties_are_all_informative_at_pilot_tau():
    rows = build_rows(load_frozen_w_a(FROZEN), PILOT_TAU)
    p2 = [r for r in rows if r["pipeline"] == "P2"]
    assert len(p2) == 3
    assert not any(r["tolerance_vacuous"] for r in p2)


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_diagnostic_does_not_mutate_frozen_input():
    before = FROZEN.read_bytes()
    build_rows(load_frozen_w_a(FROZEN), PILOT_TAU)
    assert FROZEN.read_bytes() == before


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_cli_is_deterministic(tmp_path):
    outs = []
    for _ in range(2):
        c = tmp_path / "t.csv"
        r = subprocess.run(
            [sys.executable, str(REPO / "analysis/tolerance_nonvacuity.py"),
             "--csv", str(c), "--pdf", str(tmp_path / "t.pdf"),
             "--png", str(tmp_path / "t.png")],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(c.read_text())
    assert outs[0] == outs[1]


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_csv_columns_and_row_count(tmp_path):
    c = tmp_path / "t.csv"
    subprocess.run([sys.executable, str(REPO / "analysis/tolerance_nonvacuity.py"),
                    "--csv", str(c), "--pdf", str(tmp_path / "a.pdf"),
                    "--png", str(tmp_path / "a.png")], check=True,
                   capture_output=True)
    rows = list(csv.DictReader(c.open()))
    assert len(rows) == 14
    for col in ("pipeline", "property", "W_A", "tau", "delta_lower_bound",
                "delta_upper_bound", "min_acceptable_C_AB", "vacuity_ratio",
                "tolerance_vacuous"):
        assert col in rows[0]


@pytest.mark.skipif(not FROZEN.exists(), reason="frozen results absent")
def test_zero_w_a_serialises_as_inf_not_crash(tmp_path):
    c = tmp_path / "t.csv"
    subprocess.run([sys.executable, str(REPO / "analysis/tolerance_nonvacuity.py"),
                    "--csv", str(c), "--pdf", str(tmp_path / "a.pdf"),
                    "--png", str(tmp_path / "a.png")], check=True,
                   capture_output=True)
    rows = list(csv.DictReader(c.open()))
    degenerate = [r for r in rows if float(r["W_A"]) == 0.0]
    assert degenerate
    assert all(r["vacuity_ratio"] == "inf" for r in degenerate)
