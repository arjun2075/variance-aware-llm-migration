"""Tests for single-run regression-oracle instability."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from single_run_oracle_instability import (  # noqa: E402
    P2_TOL, all_rep_cross, oracle_curves, verdict_from_point,
)

CSV = REPO / "results/strengthening/single_run_oracle_instability.csv"


# ---------------- enumeration ----------------

def test_enumerates_one_oracle_per_incumbent_repetition():
    cross = {"t": np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])}
    out = oracle_curves(cross)
    assert out["n_oracles"] == 3
    assert out["per_oracle"] == pytest.approx([0.5, 0.5, 1.0])


def test_enumeration_is_exact_not_sampled():
    """Repeated calls give identical results — no randomness involved."""
    cross = {"t": np.random.default_rng(0).random((8, 5))}
    a = oracle_curves(cross)["per_oracle"]
    b = oracle_curves(cross)["per_oracle"]
    assert a == b


def test_oracle_mean_equals_flat_cross_when_fully_eligible():
    """The identity, exact with no ineligible comparisons."""
    rng = np.random.default_rng(3)
    cross = {f"t{i}": rng.random((8, 5)) for i in range(6)}
    per = oracle_curves(cross)["per_oracle"]
    assert float(np.mean(per)) == pytest.approx(all_rep_cross(cross), abs=1e-12)


def test_identity_degrades_only_with_ineligible_cells():
    """With NaNs the two weightings differ slightly — the documented caveat."""
    m = np.array([[1.0, 1.0], [0.0, np.nan]])
    cross = {"t": m}
    per = oracle_curves(cross)["per_oracle"]
    assert per == pytest.approx([1.0, 0.0])
    assert float(np.mean(per)) == pytest.approx(0.5)
    # flat mean over the 3 eligible cells is 2/3, not 1/2
    assert all_rep_cross(cross) == pytest.approx(2.0 / 3.0)


def test_range_is_zero_when_all_oracles_agree():
    cross = {"t": np.full((8, 5), 0.7)}
    per = oracle_curves(cross)["per_oracle"]
    assert max(per) - min(per) == pytest.approx(0.0)


def test_range_reflects_disagreeing_oracles():
    m = np.zeros((8, 5)); m[0, :] = 1.0
    per = oracle_curves({"t": m})["per_oracle"]
    assert max(per) == pytest.approx(1.0)
    assert min(per) == pytest.approx(0.0)


# ---------------- verdicts ----------------

@pytest.mark.parametrize("d,exp", [(-0.20, "worse_than_tolerance"),
                                   (0.00, "within_tolerance"),
                                   (0.20, "better_than_tolerance")])
def test_verdict_from_point(d, exp):
    assert verdict_from_point(d, P2_TOL) == exp


def test_no_tolerance_yields_no_verdict():
    assert verdict_from_point(-0.5, None) == "no_declared_tolerance"


def test_boundary_is_within_tolerance():
    assert verdict_from_point(-P2_TOL, P2_TOL) == "within_tolerance"
    assert verdict_from_point(-P2_TOL - 1e-9, P2_TOL) == "worse_than_tolerance"


# ---------------- generated output ----------------

@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_output_covers_all_cells():
    rows = list(csv.DictReader(CSV.open()))
    assert len(rows) == 56
    assert all(int(r["n_oracles"]) == 8 for r in rows)


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_identity_residual_is_small_everywhere():
    rows = list(csv.DictReader(CSV.open()))
    assert max(float(r["identity_residual"]) for r in rows) < 1e-3


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_identity_is_exact_where_nothing_is_ineligible():
    """At least some cells must achieve the identity exactly."""
    rows = list(csv.DictReader(CSV.open()))
    exact = [r for r in rows if float(r["identity_residual"]) < 1e-12]
    assert len(exact) > 0


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_oracle_mean_lies_between_min_and_max():
    for r in csv.DictReader(CSV.open()):
        assert float(r["oracle_min"]) <= float(r["oracle_mean"]) <= float(r["oracle_max"])


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_delta_range_equals_agreement_range():
    """Delta = C - W_A shifts by a constant, so the ranges must match."""
    for r in csv.DictReader(CSV.open()):
        assert float(r["delta_range"]) == pytest.approx(
            float(r["oracle_range"]), abs=1e-6)


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_verdict_fractions_sum_to_one():
    for r in csv.DictReader(CSV.open()):
        frac = json.loads(r["verdict_fractions"])
        assert sum(frac.values()) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_some_p2_cell_changes_verdict_with_oracle_choice():
    """The headline claim: a conclusion can flip on oracle choice alone."""
    rows = [r for r in csv.DictReader(CSV.open()) if r["pipeline"] == "P2"]
    assert any(int(r["distinct_verdicts"]) > 1 for r in rows)


@pytest.mark.skipif(not CSV.exists(), reason="analysis output absent")
def test_degenerate_properties_show_no_oracle_spread():
    """Exact-match metrics are 0 everywhere, so no oracle choice matters."""
    rows = [r for r in csv.DictReader(CSV.open())
            if "opportunity_multiset" in r["property"]]
    assert rows and all(float(r["oracle_range"]) == 0.0 for r in rows)
