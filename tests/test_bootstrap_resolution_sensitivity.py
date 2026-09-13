"""Tests for the bootstrap resolution sensitivity check."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from bootstrap_resolution_sensitivity import SELECTED  # noqa: E402
from bootstrap_coverage_simulation import SCENARIOS  # noqa: E402

CSV = REPO / "results/strengthening/bootstrap_resolution_sensitivity.csv"
BASE = REPO / "results/strengthening/bootstrap_coverage.csv"


def test_three_scenarios_selected():
    assert len(SELECTED) == 3


def test_selected_scenarios_exist_in_the_main_grid():
    names = {s.name for s in SCENARIOS}
    assert set(SELECTED) <= names


def test_selection_spans_all_heterogeneity_levels():
    by = {s.name: s for s in SCENARIOS}
    hs = sorted(by[n].heterogeneity for n in SELECTED)
    assert hs == [0.1, 0.175, 0.25]


def test_selection_includes_at_least_one_large_task_count():
    by = {s.name: s for s in SCENARIOS}
    assert any(by[n].n_tasks == 60 for n in SELECTED)


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_output_has_all_methods_for_all_scenarios():
    rows = list(csv.DictReader(CSV.open()))
    assert len(rows) == 9          # 3 scenarios x 3 methods
    assert len({r["scenario"] for r in rows}) == 3


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_high_resolution_settings_meet_the_specification():
    """At least 500 datasets and 1,000 bootstrap replicates were required."""
    for r in csv.DictReader(CSV.open()):
        assert int(r["hi_res_n_sim"]) >= 500
        assert int(r["hi_res_boot_reps"]) >= 1000
        assert int(r["base_boot_reps"]) == 200


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_coverage_change_is_within_monte_carlo_noise():
    """The headline: resolution does not explain the conservative coverage."""
    a = [r for r in csv.DictReader(CSV.open()) if r["method"].startswith("A")]
    assert a
    for r in a:
        assert abs(float(r["coverage_change"])) < 0.02


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_higher_resolution_does_not_shrink_intervals():
    """If coarse quantiles had inflated the intervals, finer ones would shrink
    them. They do not."""
    a = [r for r in csv.DictReader(CSV.open()) if r["method"].startswith("A")]
    for r in a:
        assert float(r["ci_width_ratio"]) > 0.99


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_method_a_remains_at_or_above_nominal_coverage():
    a = [r for r in csv.DictReader(CSV.open()) if r["method"].startswith("A")]
    assert all(float(r["hi_res_coverage"]) >= 0.94 for r in a)


@pytest.mark.skipif(not (CSV.exists() and BASE.exists()), reason="outputs absent")
def test_original_simulation_output_is_not_modified():
    """The sensitivity check must not touch the main results."""
    base_rows = list(csv.DictReader(BASE.open()))
    assert len(base_rows) == 54           # 18 scenarios x 3 methods
    assert all(int(r["n_sim"]) == 2000 for r in base_rows)


@pytest.mark.skipif(not CSV.exists(), reason="sensitivity output absent")
def test_baseline_values_match_the_original_file():
    """The recorded baseline column must come from the untouched original."""
    base = {(r["scenario"], r["method"]): r for r in csv.DictReader(BASE.open())}
    for r in csv.DictReader(CSV.open()):
        b = base[(r["scenario"], r["method"])]
        assert float(r["base_coverage"]) == pytest.approx(float(b["coverage_95"]))
        assert float(r["base_ci_width"]) == pytest.approx(float(b["mean_ci_width"]))
