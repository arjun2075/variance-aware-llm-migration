"""Tests for the bootstrap coverage simulation."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from bootstrap_coverage_simulation import (  # noqa: E402
    CANDIDATE_REPS, INCUMBENT_REPS, METHODS, SCENARIOS, Scenario,
    _offdiag_mean, _withdiag_mean, ci_cluster_bootstrap, ci_naive_pairwise,
    delta_offdiag, delta_withdiag, run_scenario, simulate_dataset,
)


# ---------------- generator ----------------

def test_generator_shapes_match_frozen_design():
    w, c = simulate_dataset(np.random.default_rng(0), Scenario("s", 5, .85, .7, .1))
    assert len(w) == len(c) == 5
    assert all(m.shape == (INCUMBENT_REPS, INCUMBENT_REPS) for m in w)
    assert all(m.shape == (INCUMBENT_REPS, CANDIDATE_REPS) for m in c)
    assert INCUMBENT_REPS == 8 and CANDIDATE_REPS == 5


def test_within_matrices_are_symmetric_with_unit_diagonal():
    w, _ = simulate_dataset(np.random.default_rng(1), Scenario("s", 4, .8, .6, .1))
    for m in w:
        assert np.allclose(m, m.T)
        assert np.allclose(np.diag(m), 1.0)   # self-comparison scores 1.0


def test_outputs_are_binary():
    w, c = simulate_dataset(np.random.default_rng(2), Scenario("s", 4, .8, .6, .1))
    for m in list(w) + list(c):
        assert set(np.unique(m)).issubset({0.0, 1.0})


def test_generator_is_seed_deterministic():
    sc = Scenario("s", 6, .85, .7, .15)
    a = simulate_dataset(np.random.default_rng(42), sc)
    b = simulate_dataset(np.random.default_rng(42), sc)
    assert all(np.array_equal(x, y) for x, y in zip(a[0], b[0]))
    assert all(np.array_equal(x, y) for x, y in zip(a[1], b[1]))


@pytest.mark.parametrize("p_w,p_c", [(0.85, 0.85), (0.85, 0.70), (0.85, 0.50)])
def test_point_estimator_recovers_population_delta(p_w, p_c):
    """Off-diagonal Delta must be unbiased for p_c - p_w."""
    sc = Scenario("s", 200, p_w, p_c, 0.15)
    rng = np.random.default_rng(7)
    est = np.mean([delta_offdiag(*simulate_dataset(rng, sc)) for _ in range(40)])
    assert est == pytest.approx(p_c - p_w, abs=0.02)


# ---------------- the two failure modes ----------------

def test_diagonal_inclusion_inflates_W_A():
    """Self-pairs score 1.0, so including them pulls W_A upward."""
    w, _ = simulate_dataset(np.random.default_rng(3), Scenario("s", 50, .7, .7, .1))
    assert _withdiag_mean(w) > _offdiag_mean(w)


def test_diagonal_inclusion_biases_delta_downward():
    """Delta = C_AB - W_A, so an inflated W_A makes Delta too negative."""
    sc = Scenario("s", 60, .85, .85, .15)
    rng = np.random.default_rng(4)
    offs, dias = [], []
    for _ in range(30):
        w, c = simulate_dataset(rng, sc)
        offs.append(delta_offdiag(w, c)); dias.append(delta_withdiag(w, c))
    assert np.mean(dias) < np.mean(offs)
    assert np.mean(offs) == pytest.approx(0.0, abs=0.02)   # unbiased
    assert np.mean(dias) < -0.01                            # biased negative


def test_diagonal_bias_magnitude_matches_theory():
    """Bias ~= (1/R)(1 - W_A) for R incumbent repetitions."""
    sc = Scenario("s", 300, .70, .70, 0.0)
    w, c = simulate_dataset(np.random.default_rng(5), sc)
    observed = _withdiag_mean(w) - _offdiag_mean(w)
    n_off = INCUMBENT_REPS * (INCUMBENT_REPS - 1) / 2
    n_dia = INCUMBENT_REPS
    expected = (n_dia / (n_off + n_dia)) * (1 - _offdiag_mean(w))
    assert observed == pytest.approx(expected, abs=0.02)


def test_naive_intervals_are_narrower_than_clustered():
    """Ignoring within-task dependence understates the variance."""
    sc = Scenario("s", 20, .85, .85, .25)
    rng = np.random.default_rng(6)
    w, c = simulate_dataset(rng, sc)
    lo_a, hi_a = ci_cluster_bootstrap(w, c, rng, 300, delta_offdiag)
    lo_b, hi_b = ci_naive_pairwise(w, c, rng, 300)
    assert (hi_b - lo_b) < (hi_a - lo_a)


def test_cluster_bootstrap_is_two_stage_by_default():
    """Task-only resampling reuses fixed matrices and gives narrower intervals."""
    sc = Scenario("s", 20, .85, .85, .20)
    rng = np.random.default_rng(8)
    w, c = simulate_dataset(rng, sc)
    lo2, hi2 = ci_cluster_bootstrap(w, c, np.random.default_rng(9), 300,
                                    delta_offdiag, two_stage=True)
    lo1, hi1 = ci_cluster_bootstrap(w, c, np.random.default_rng(9), 300,
                                    delta_offdiag, two_stage=False)
    assert (hi2 - lo2) > (hi1 - lo1)


def test_offdiag_mean_drops_duplicate_resampled_repetitions():
    """A stage-2 duplicate draw is a self-comparison and must be excluded."""
    m = np.array([[1.0, 0.0], [0.0, 1.0]])
    keep_all = np.array([[False, True], [True, False]])
    assert _offdiag_mean([m], [keep_all]) == pytest.approx(0.0)
    keep_none = np.array([[False, False], [False, False]])
    assert np.isnan(_offdiag_mean([m], [keep_none]))


# ---------------- scenario grid ----------------

def test_scenario_grid_is_prespecified_and_complete():
    assert len(SCENARIOS) == 18          # 2 task counts x 3 effects x 3 heterogeneity
    assert {s.n_tasks for s in SCENARIOS} == {20, 60}
    assert {round(s.true_delta, 2) for s in SCENARIOS} == {0.0, -0.15, -0.35}


def test_no_scenario_has_zero_heterogeneity():
    """h = 0 is degenerate: with no within-task dependence, naive inference is
    correct by construction and the comparison would be vacuous."""
    assert all(s.heterogeneity > 0 for s in SCENARIOS)


def test_true_delta_is_pc_minus_pw():
    for s in SCENARIOS:
        assert s.true_delta == pytest.approx(s.p_c - s.p_w)


# ---------------- end to end ----------------

def test_run_scenario_emits_all_three_methods():
    rows = run_scenario(Scenario("s", 20, .85, .70, .15), n_sim=12,
                        boot_reps=60, seed=11)
    assert {r["method"] for r in rows} == set(METHODS)
    for r in rows:
        assert 0.0 <= r["coverage_95"] <= 1.0
        assert r["mean_ci_width"] > 0
        assert r["n_sim"] == 12


def test_run_scenario_is_seed_deterministic():
    sc = Scenario("s", 15, .85, .70, .15)
    a = run_scenario(sc, n_sim=8, boot_reps=50, seed=3)
    b = run_scenario(sc, n_sim=8, boot_reps=50, seed=3)
    assert a == b


def test_methods_ab_share_the_point_estimate():
    """A and B differ ONLY in interval construction, not in the estimator."""
    rows = run_scenario(Scenario("s", 20, .85, .70, .15), n_sim=10,
                        boot_reps=50, seed=13)
    a = next(r for r in rows if r["method"] == "A_proposed_offdiag_cluster")
    b = next(r for r in rows if r["method"] == "B_naive_offdiag_pairwise")
    assert a["bias"] == b["bias"]
    assert a["mean_estimate"] == b["mean_estimate"]


def test_method_c_point_estimate_differs_from_a():
    rows = run_scenario(Scenario("s", 25, .85, .85, .15), n_sim=12,
                        boot_reps=50, seed=17)
    a = next(r for r in rows if r["method"] == "A_proposed_offdiag_cluster")
    c = next(r for r in rows if r["method"] == "C_diagonal_contaminated_cluster")
    assert c["bias"] < a["bias"]


def test_cli_runs_and_is_deterministic(tmp_path):
    outs = []
    for _ in range(2):
        csv_p = tmp_path / "c.csv"
        r = subprocess.run(
            [sys.executable, str(REPO / "analysis/bootstrap_coverage_simulation.py"),
             "--n-sim", "6", "--boot-reps", "40", "--scenarios", "1",
             "--seed", "99", "--csv", str(csv_p),
             "--summary", str(tmp_path / "s.md"), "--pdf", str(tmp_path / "f.pdf"),
             "--png", str(tmp_path / "f.png")],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(csv_p.read_text())
    assert outs[0] == outs[1]


def test_cli_csv_has_required_columns(tmp_path):
    csv_p = tmp_path / "c.csv"
    subprocess.run([sys.executable,
                    str(REPO / "analysis/bootstrap_coverage_simulation.py"),
                    "--n-sim", "5", "--boot-reps", "30", "--scenarios", "1",
                    "--csv", str(csv_p), "--summary", str(tmp_path / "s.md"),
                    "--pdf", str(tmp_path / "f.pdf"), "--png", str(tmp_path / "f.png")],
                   check=True, capture_output=True)
    rows = list(csv.DictReader(csv_p.open()))
    for col in ("scenario", "method", "true_delta", "bias", "coverage_95",
                "noncoverage_rate", "mean_ci_width", "mc_se_coverage", "n_sim"):
        assert col in rows[0]
