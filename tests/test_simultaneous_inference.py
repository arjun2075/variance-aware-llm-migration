"""Tests for simultaneous inference across the 12 P2 cells."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from simultaneous_inference import (  # noqa: E402
    CI_LEVEL, P2_TOL, SEED, _flat_mean, _offdiag_mean, joint_bootstrap,
    point_delta, simultaneous_band, verdict,
)

CSV = REPO / "results/strengthening/simultaneous_inference.csv"


# ---------------- estimator pieces ----------------

def test_offdiag_excludes_the_diagonal():
    m = np.array([[1.0, 0.4], [0.4, 1.0]])
    assert _offdiag_mean([m]) == pytest.approx(0.4)


def test_offdiag_ignores_nan():
    m = np.array([[1.0, np.nan, 0.6], [np.nan, 1.0, 0.8], [0.6, 0.8, 1.0]])
    assert _offdiag_mean([m]) == pytest.approx(0.7)


def test_flat_mean_uses_every_eligible_cell():
    assert _flat_mean([np.full((3, 4), 0.25)]) == pytest.approx(0.25)


def test_point_delta_is_cross_minus_within():
    w = {"t": np.full((4, 4), 0.8)}
    c = {"t": np.full((4, 3), 0.5)}
    assert point_delta(w, c, ["t"]) == pytest.approx(-0.3)


# ---------------- common resampling ----------------

def test_joint_bootstrap_uses_common_task_draws():
    """Two identical cells must produce identical bootstrap paths, which is
    only true if the same task resample is applied to both."""
    rng = np.random.default_rng(0)
    w = {f"t{i}": rng.random((4, 4)) for i in range(8)}
    c = {f"t{i}": rng.random((4, 3)) for i in range(8)}
    cells = [{"within": w, "cross": c}, {"within": w, "cross": c}]
    draws, point, _ = joint_bootstrap(cells, 60, SEED)
    assert np.allclose(draws[:, 0], draws[:, 1])
    assert point[0] == pytest.approx(point[1])


def test_correlated_cells_are_not_independent():
    """Bootstrap draws for two cells sharing tasks must correlate."""
    rng = np.random.default_rng(1)
    w = {f"t{i}": np.full((4, 4), rng.uniform(0.5, 0.9)) for i in range(20)}
    c1 = {t: np.full((4, 3), float(w[t][0, 1]) - 0.2) for t in w}
    c2 = {t: np.full((4, 3), float(w[t][0, 1]) - 0.1) for t in w}
    draws, _, _ = joint_bootstrap([{"within": w, "cross": c1},
                                   {"within": w, "cross": c2}], 200, SEED)
    r = np.corrcoef(draws[:, 0], draws[:, 1])[0, 1]
    assert r > 0.5


def test_joint_bootstrap_is_seed_deterministic():
    rng = np.random.default_rng(2)
    w = {f"t{i}": rng.random((4, 4)) for i in range(6)}
    c = {f"t{i}": rng.random((4, 3)) for i in range(6)}
    cells = [{"within": w, "cross": c}]
    a, _, _ = joint_bootstrap(cells, 50, 99)
    b, _, _ = joint_bootstrap(cells, 50, 99)
    assert np.array_equal(a, b)


# ---------------- the band ----------------

def test_simultaneous_band_is_wider_than_pointwise():
    rng = np.random.default_rng(3)
    draws = rng.normal(0, 0.05, (2000, 6))
    point = np.zeros(6)
    band = simultaneous_band(draws, point)
    sim_w = band["sim_upper"] - band["sim_lower"]
    pw_w = band["boot_pointwise_upper"] - band["boot_pointwise_lower"]
    assert np.all(sim_w > pw_w)


def test_critical_value_exceeds_the_pointwise_normal_quantile():
    rng = np.random.default_rng(4)
    band = simultaneous_band(rng.normal(0, 0.05, (3000, 12)), np.zeros(12))
    assert band["critical_value"] > 1.96


def test_critical_value_grows_with_more_cells():
    rng = np.random.default_rng(5)
    q2 = simultaneous_band(rng.normal(0, 1, (3000, 2)), np.zeros(2))["critical_value"]
    q20 = simultaneous_band(rng.normal(0, 1, (3000, 20)), np.zeros(20))["critical_value"]
    assert q20 > q2


def test_single_cell_band_approximates_pointwise():
    rng = np.random.default_rng(6)
    band = simultaneous_band(rng.normal(0, 1, (5000, 1)), np.zeros(1))
    assert band["critical_value"] == pytest.approx(1.96, abs=0.15)


def test_band_is_centred_on_the_point_estimate():
    rng = np.random.default_rng(7)
    point = np.array([-0.2, 0.1])
    band = simultaneous_band(rng.normal(0, 0.05, (1000, 2)) + point, point)
    for k in (0, 1):
        mid = (band["sim_lower"][k] + band["sim_upper"][k]) / 2
        assert mid == pytest.approx(point[k], abs=1e-9)


# ---------------- verdict (frozen definition) ----------------

@pytest.mark.parametrize("lo,hi,exp", [
    (-0.30, -0.20, "rejected"), (-0.04, 0.04, "demonstrated"),
    (-0.30, -0.01, "inconclusive"), (-0.05, 0.05, "demonstrated"),
])
def test_verdict_matches_the_frozen_rule(lo, hi, exp):
    assert verdict(lo, hi, P2_TOL) == exp


# ---------------- generated output ----------------

@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_covers_all_twelve_cells():
    assert len(list(csv.DictReader(CSV.open()))) == 12


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_simultaneous_intervals_contain_the_pointwise_ones():
    for r in csv.DictReader(CSV.open()):
        assert float(r["simultaneous_lower"]) <= float(r["frozen_ci_lower"]) + 1e-3
        assert float(r["simultaneous_upper"]) >= float(r["frozen_ci_upper"]) - 1e-3


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_all_widths_inflate():
    for r in csv.DictReader(CSV.open()):
        assert float(r["width_inflation_factor"]) > 1.0


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_a_single_critical_value_is_shared_by_all_cells():
    """A common q is what makes the band simultaneous."""
    qs = {r["critical_value"] for r in csv.DictReader(CSV.open())}
    assert len(qs) == 1


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_point_estimates_reproduce_the_frozen_deltas():
    for r in csv.DictReader(CSV.open()):
        assert float(r["delta"]) == pytest.approx(float(r["frozen_delta"]),
                                                  abs=1e-5)


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_every_span_cell_survives_simultaneous_correction():
    """The core span-vs-label conclusion must not depend on pointwise intervals."""
    rows = [r for r in csv.DictReader(CSV.open()) if "span" in r["property"]]
    assert len(rows) == 8
    assert all(r["simultaneous_verdict"] == "rejected" for r in rows)


@pytest.mark.skipif(not CSV.exists(), reason="output absent")
def test_only_boundary_label_cells_change_verdict():
    """The cells that lose significance are the ones already flagged as
    boundary-fragile by the leave-one-task-out analysis."""
    changed = [r for r in csv.DictReader(CSV.open())
               if r["verdict_changed"] == "True"]
    assert all(r["property"] == "label_agreement" for r in changed)
    assert all(r["simultaneous_verdict"] == "inconclusive" for r in changed)
