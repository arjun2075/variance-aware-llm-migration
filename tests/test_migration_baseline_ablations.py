"""Tests for the baseline / ablation study."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from migration_baseline_ablations import (  # noqa: E402
    DETERMINISTIC_W_A, P2_TOL, build_rows, deterministic_delta,
    deterministic_gap, load_extended, load_pairwise, panel_pooled,
    qualitative_class, verdict,
)

PAIRWISE = REPO / "results/analysis/pairwise_results.json"
EXTENDED = REPO / "results/analysis/extended_analysis.json"


# ---------------- A2: deterministic-oracle algebra ----------------

def test_deterministic_assumes_w_a_of_one():
    assert DETERMINISTIC_W_A == 1.0
    assert deterministic_delta(0.75) == pytest.approx(-0.25)
    assert deterministic_delta(1.0) == pytest.approx(0.0)
    assert deterministic_delta(0.0) == pytest.approx(-1.0)


@pytest.mark.parametrize("w_a", [0.0, 0.04, 0.5, 0.9286, 1.0])
def test_gap_is_minus_one_minus_w_a(w_a):
    assert deterministic_gap(w_a) == pytest.approx(-(1.0 - w_a))


@pytest.mark.parametrize("w_a,c_ab", [(0.85, 0.70), (0.10, 0.05), (1.0, 1.0),
                                      (0.0, 0.0), (0.93, 0.86)])
def test_identity_delta_det_minus_delta_equals_gap(w_a, c_ab):
    """The theoretical identity, in exact arithmetic."""
    delta = c_ab - w_a
    assert (deterministic_delta(c_ab) - delta) == pytest.approx(deterministic_gap(w_a))


def test_gap_is_independent_of_cross_agreement():
    """The deterministic assumption shifts every candidate for a property by
    the same amount."""
    w_a = 0.80
    shifts = {round(deterministic_delta(c) - (c - w_a), 9) for c in
              (0.1, 0.4, 0.7, 0.95)}
    assert len(shifts) == 1


def test_gap_is_zero_only_for_a_perfectly_stable_incumbent():
    assert deterministic_gap(1.0) == pytest.approx(0.0)
    assert deterministic_gap(0.999) < 0.0


def test_deterministic_always_understates_the_effect():
    """Delta_det <= Delta whenever W_A <= 1, so the deterministic view makes
    every migration look worse than it is."""
    for w_a, c_ab in ((0.85, 0.70), (0.10, 0.09), (0.5, 0.5)):
        assert deterministic_delta(c_ab) <= (c_ab - w_a) + 1e-12


# ---------------- verdict / qualitative helpers ----------------

@pytest.mark.parametrize("lo,hi,tau,exp", [
    (-0.30, -0.20, 0.05, "rejected"),
    (-0.04, 0.04, 0.05, "demonstrated"),
    (-0.30, -0.01, 0.05, "inconclusive"),
])
def test_verdict_rule(lo, hi, tau, exp):
    assert verdict(lo, hi, tau) == exp


def test_verdict_without_tolerance():
    assert verdict(-0.3, -0.2, None) == "no_declared_tolerance"


@pytest.mark.parametrize("d,exp", [(-0.20, "worse_than_tolerance"),
                                   (0.0, "within_tolerance"),
                                   (0.20, "better_than_tolerance")])
def test_qualitative_class(d, exp):
    assert qualitative_class(d, 0.05) == exp


# ---------------- A3: pooled estimator ----------------

def test_pooled_averages_candidates():
    rows = [{"property": "p", "delta": -0.1}, {"property": "p", "delta": -0.3}]
    out = panel_pooled(rows)
    assert out["p"]["pooled_delta"] == pytest.approx(-0.2)
    assert out["p"]["candidate_spread"] == pytest.approx(0.2)
    assert out["p"]["n_candidates"] == 2


def test_pooled_conceals_a_sign_disagreement():
    """A pooled negative can hide a positive candidate."""
    rows = [{"property": "p", "delta": -0.12}, {"property": "p", "delta": +0.02}]
    out = panel_pooled(rows)
    assert out["p"]["pooled_delta"] < 0
    assert out["p"]["candidate_max"] > 0


def test_pooled_accepts_built_rows_too():
    rows = [{"pipeline": "P2", "property": "p", "A1_proposed_delta": -0.2}]
    out = panel_pooled(rows)
    assert out["P2·p"]["pooled_delta"] == pytest.approx(-0.2)


# ---------------- frozen-data integration ----------------

@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_builds_all_fifty_six_cells():
    rows = build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    assert len(rows) == 56          # 14 properties x 4 candidates


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_identity_holds_for_every_frozen_cell():
    """Residual is bounded by the 6dp storage rounding of the frozen inputs."""
    rows = build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    assert all(r["A2_identity_holds"] for r in rows)
    assert max(r["A2_identity_residual"] for r in rows) < 1e-5


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_proposed_deltas_match_the_frozen_values_exactly():
    """The ablation must not recompute the primary estimator."""
    pw = load_pairwise(PAIRWISE)
    rows = build_rows(pw, load_extended(EXTENDED))
    frozen = {(p, r["property"], r["candidate"]): r["delta"]
              for p in ("P1", "P2") for r in pw[p]}
    for r in rows:
        key = (r["pipeline"], r["property"], r["candidate"])
        assert r["A1_proposed_delta"] == pytest.approx(frozen[key])


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_deterministic_is_more_negative_on_every_frozen_cell():
    rows = build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    for r in rows:
        assert r["A2_deterministic_delta"] <= r["A1_proposed_delta"] + 1e-9


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_technical_execution_pooling_hides_a_sign_flip():
    """Documented A3 finding: the pooled value is negative while one candidate
    is positive."""
    rows = build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    pooled = panel_pooled([r for r in rows if r["pipeline"] == "P1"])
    te = pooled["P1·M1.technical_execution"]
    assert te["pooled_delta"] < 0
    assert te["candidate_max"] > 0


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_schema_only_would_miss_rejected_p2_cells():
    """Every P2 cell has perfect schema validity, yet most are rejected."""
    rows = build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    p2 = [r for r in rows if r["pipeline"] == "P2"]
    perfect = [r for r in p2 if r["A5_schema_valid_rate"] == 1.0]
    assert len(perfect) == len(p2)
    assert any(r["A1_verdict"] == "rejected" for r in perfect)


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_does_not_mutate_frozen_inputs():
    a, b = PAIRWISE.read_bytes(), EXTENDED.read_bytes()
    build_rows(load_pairwise(PAIRWISE), load_extended(EXTENDED))
    assert PAIRWISE.read_bytes() == a and EXTENDED.read_bytes() == b


@pytest.mark.skipif(not PAIRWISE.exists(), reason="frozen results absent")
def test_cli_deterministic(tmp_path):
    outs = []
    for _ in range(2):
        c = tmp_path / "a.csv"
        r = subprocess.run(
            [sys.executable, str(REPO / "analysis/migration_baseline_ablations.py"),
             "--csv", str(c), "--summary", str(tmp_path / "a.md"),
             "--pdf", str(tmp_path / "a.pdf"), "--png", str(tmp_path / "a.png")],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(c.read_text())
    assert outs[0] == outs[1]
    assert len(list(csv.DictReader((tmp_path / "a.csv").open()))) == 56
