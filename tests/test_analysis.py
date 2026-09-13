"""Tests for the migration estimands and the correctness x behavior quadrants."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vaml.analysis.correctness import (  # noqa: E402
    Quadrant, MigrationOutcome, agreement_on_incumbent_errors,
    bootstrap_accuracy_delta, classify_quadrant,
)
from vaml.analysis.migration import (  # noqa: E402
    bootstrap_migration_delta, classify_against_tolerance,
    estimate_cross_agreement, estimate_within_variation,
    tolerance_sensitivity,
)


# ---------------- off-diagonal treatment ----------------

def test_within_variation_excludes_diagonal():
    """A perfect diagonal must not inflate W_A."""
    mat = [[1.0, 0.5, 0.5],
           [0.5, 1.0, 0.5],
           [0.5, 0.5, 1.0]]
    w, n = estimate_within_variation({"t1": mat})
    assert n == 3           # C(3,2), not 9
    assert w == pytest.approx(0.5)   # diagonal 1.0s excluded


def test_within_variation_pair_count_is_n_choose_2():
    mat = np.full((5, 5), 0.4)
    _, n = estimate_within_variation({"t": mat})
    assert n == 10


def test_cross_agreement_uses_full_product():
    """C_AB has no diagonal concept: all R_A x R_B cells count."""
    mat = np.full((8, 5), 0.3)
    c, n = estimate_cross_agreement({"t": mat})
    assert n == 40
    assert c == pytest.approx(0.3)


def test_within_ignores_nan():
    mat = [[1.0, np.nan, 0.6], [np.nan, 1.0, 0.8], [0.6, 0.8, 1.0]]
    w, n = estimate_within_variation({"t": mat})
    assert n == 2
    assert w == pytest.approx(0.7)


def test_delta_sign_convention():
    """Delta = C_AB - W_A; a candidate agreeing less than the incumbent
    agrees with itself gives a NEGATIVE delta."""
    within = {"t": np.full((5, 5), 0.9)}
    cross = {"t": np.full((5, 5), 0.4)}
    w, _ = estimate_within_variation(within)
    c, _ = estimate_cross_agreement(cross)
    assert c - w == pytest.approx(-0.5)


# ---------------- bootstrap ----------------

def test_bootstrap_drops_self_pairs():
    """Duplicate repetition draws must not inject 1.0 self-comparisons.

    With off-diagonal 0.5 and diagonal 1.0, a bootstrap that kept self pairs
    would pull W_A above 0.5 and push delta below the true value.
    """
    mat = np.full((5, 5), 0.5)
    np.fill_diagonal(mat, 1.0)
    within = {f"t{i}": mat for i in range(8)}
    cross = {f"t{i}": np.full((5, 5), 0.5) for i in range(8)}
    lo, hi, draws = bootstrap_migration_delta(within, cross, replicates=400, seed=1)
    # true delta is exactly 0.0; self-pair contamination would bias negative
    assert np.nanmean(draws) == pytest.approx(0.0, abs=0.02)
    assert lo <= 0.0 <= hi


def test_bootstrap_ci_is_ordered_and_contains_point():
    rng = np.random.default_rng(0)
    within = {f"t{i}": rng.uniform(0.6, 0.9, (5, 5)) for i in range(8)}
    cross = {f"t{i}": rng.uniform(0.3, 0.6, (5, 5)) for i in range(8)}
    lo, hi, draws = bootstrap_migration_delta(within, cross, replicates=500, seed=7)
    assert lo < hi
    assert lo <= np.nanmedian(draws) <= hi


def test_bootstrap_is_seed_deterministic():
    within = {f"t{i}": np.full((5, 5), 0.8) for i in range(8)}
    cross = {f"t{i}": np.full((5, 5), 0.5) for i in range(8)}
    a = bootstrap_migration_delta(within, cross, replicates=200, seed=42)[2]
    b = bootstrap_migration_delta(within, cross, replicates=200, seed=42)[2]
    assert np.array_equal(a, b)


# ---------------- tolerance ----------------

@pytest.mark.parametrize("lo,hi,tol,expected", [
    (-0.35, -0.11, 0.10, "rejected"),
    (-0.09, 0.09, 0.10, "demonstrated"),
    (-0.10, 0.10, 0.10, "demonstrated"),
    (-0.18, 0.01, 0.10, "inconclusive"),
    (0.11, 0.20, 0.10, "rejected"),
])
def test_classify_against_tolerance(lo, hi, tol, expected):
    assert classify_against_tolerance(lo, hi, tol) == expected


def test_no_declared_tolerance_yields_no_verdict():
    """Pipeline 1 policy: no application-grounded tolerance -> no verdict."""
    assert classify_against_tolerance(-0.2, -0.1, None) == "no_declared_tolerance"


def test_tolerance_sensitivity_can_flip_verdict():
    """The motivating pathology: one CI, different verdicts by tolerance."""
    curve = tolerance_sensitivity(-0.117, -0.072, [0.05, 0.10, 0.15])
    assert curve[0.05] == "rejected"
    assert curve[0.10] == "inconclusive"
    assert curve[0.15] == "demonstrated"


# ---------------- quadrants ----------------

def test_quadrant_A_changed_but_improved():
    q = classify_quadrant(False, 0.08, (0.03, 0.13), 0.80)
    assert q is Quadrant.A_CHANGED_IMPROVED


def test_quadrant_B_changed_and_worsened():
    q = classify_quadrant(False, -0.09, (-0.15, -0.03), 0.80)
    assert q is Quadrant.B_CHANGED_WORSENED


def test_quadrant_C_preserved_and_incumbent_perfect():
    q = classify_quadrant(True, 0.0, (-0.01, 0.01), 1.0)
    assert q is Quadrant.C_PRESERVED_CORRECT


def test_quadrant_D_preserved_error():
    """Behavior preserved while the incumbent is fallible -> preserved error."""
    q = classify_quadrant(True, 0.0, (-0.02, 0.02), 0.72)
    assert q is Quadrant.D_PRESERVED_ERROR


def test_quadrant_indeterminate_when_ci_straddles_zero():
    q = classify_quadrant(False, 0.01, (-0.05, 0.07), 0.80)
    assert q is Quadrant.INDETERMINATE


def _outcome(quadrant: Quadrant) -> MigrationOutcome:
    return MigrationOutcome(
        incumbent="A", candidate="B", property_name="label_accuracy",
        behavior_preserved=quadrant in (Quadrant.C_PRESERVED_CORRECT,
                                        Quadrant.D_PRESERVED_ERROR),
        behavioral_delta=0.0, incumbent_accuracy=0.8, candidate_accuracy=0.8,
        accuracy_delta=0.0, accuracy_ci=(-0.01, 0.01), quadrant=quadrant)


def test_quadrant_D_is_never_a_success():
    """The central guarantee: agreeing with a wrong incumbent is not success."""
    assert _outcome(Quadrant.D_PRESERVED_ERROR).is_success is False


def test_quadrant_A_counts_as_success_despite_failing_behavioral_test():
    assert _outcome(Quadrant.A_CHANGED_IMPROVED).is_success is True


def test_quadrant_C_is_success_and_B_is_not():
    assert _outcome(Quadrant.C_PRESERVED_CORRECT).is_success is True
    assert _outcome(Quadrant.B_CHANGED_WORSENED).is_success is False


def test_quadrant_D_headline_names_the_trap():
    text = _outcome(Quadrant.D_PRESERVED_ERROR).headline.lower()
    assert "not a successful migration" in text


# ---------------- accuracy delta / error subset ----------------

def test_bootstrap_accuracy_delta_detects_improvement():
    inc = [False] * 30 + [True] * 70
    cand = [True] * 100
    tids = [f"t{i}" for i in range(100)]
    point, lo, hi = bootstrap_accuracy_delta(inc, cand, tids, replicates=400, seed=3)
    assert point == pytest.approx(0.30, abs=1e-9)
    assert lo > 0


def test_bootstrap_accuracy_delta_zero_when_identical():
    inc = cand = [True, False, True, True, False]
    tids = [f"t{i}" for i in range(5)]
    point, lo, hi = bootstrap_accuracy_delta(inc, cand, tids, replicates=200, seed=5)
    assert point == pytest.approx(0.0)
    assert lo <= 0 <= hi


def test_bootstrap_accuracy_delta_rejects_misaligned_inputs():
    with pytest.raises(ValueError):
        bootstrap_accuracy_delta([True], [True, False], ["t1", "t2"])


def test_agreement_on_incumbent_errors_isolates_wrong_subset():
    inc_correct = [True, True, False, False]
    agreement = [0.10, 0.20, 0.90, 0.95]   # high agreement exactly where wrong
    val, n = agreement_on_incumbent_errors(inc_correct, agreement)
    assert n == 2
    assert val == pytest.approx(0.925)


def test_agreement_on_incumbent_errors_none_when_incumbent_perfect():
    val, n = agreement_on_incumbent_errors([True, True], [0.5, 0.5])
    assert val is None and n == 0


# ---------------- regression: falsy-zero in matrix construction ----------------

def test_zero_agreement_is_not_treated_as_ineligible():
    """A disagreement scores 0.0, which is FALSY.

    `pair_value(...) or np.nan` silently turns every disagreement into an
    ineligible pair, biasing W_A toward 1.0. This shipped in the first
    analysis run and produced W_A = 1.000 for a label metric where the
    incumbent actually disagreed with itself on 10 of 60 tasks.
    """
    import numpy as np
    # the buggy idiom
    assert (0.0 or np.nan) is not 0.0
    assert np.isnan(0.0 or np.nan)
    # the correct idiom
    v = 0.0
    assert (np.nan if v is None else v) == 0.0


def test_within_matrix_preserves_zero_scores():
    """End-to-end: a task where the incumbent disagrees with itself must
    produce W_A < 1.0, not W_A == 1.0."""
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).resolve().parents[1] / "scripts"))
    from run_analysis import build_matrices
    from vaml.analysis.migration import estimate_within_variation

    class R:
        def __init__(self, task, model, rep, label):
            self.task_id, self.model_key, self.repetition = task, model, rep
            self.accepted = True
            self.structured = {"label": label}

    # incumbent gives two different labels across 4 reps -> W_A must be < 1
    runs = [R("t1", "inc", 1, "A"), R("t1", "inc", 2, "A"),
            R("t1", "inc", 3, "B"), R("t1", "inc", 4, "B"),
            R("t1", "cand", 1, "A")]
    within, _ = build_matrices(runs, "inc", "cand", "exact", "label",
                               lambda x: None, 0.8)
    w, n = estimate_within_variation(within)
    assert n == 6, f"expected C(4,2)=6 within pairs, got {n}"
    assert w == pytest.approx(1 / 3), f"expected 2/6 agreements = 0.333, got {w}"
    assert w < 1.0
