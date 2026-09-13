"""Variance-aware migration estimands.

Primary estimand (pairwise, directional):

    Delta(A -> B) = C_AB - W_A

    W_A  = incumbent self-agreement, over DISTINCT-repetition pairs only
    C_AB = incumbent-candidate agreement, over the R_A x R_B product

Off-diagonal treatment
----------------------
W_A is formed only over pairs of DISTINCT repetitions. Comparing a repetition
with itself scores 1.0 by construction and biases the within-model baseline
upward by (self-pair fraction) x (1 - true agreement), which pushes Delta
spuriously negative — largest exactly for low-agreement content properties.
This is mandatory, not a tuning choice.

The panel-average symmetric statistic is provided for comparison only and is
never the headline result.
"""
from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MigrationEstimate:
    incumbent: str
    candidate: str
    property_name: str
    w_a: float
    c_ab: float
    delta: float
    ci_lower: float
    ci_upper: float
    n_within_pairs: int
    n_cross_pairs: int
    n_tasks: int
    replicates: int


def estimate_within_variation(
    values_by_task: dict[str, Sequence[Sequence[float]]],
) -> tuple[float, int]:
    """W_A over distinct-repetition incumbent pairs.

    values_by_task maps task_id -> a per-task square matrix of pairwise
    agreement between incumbent repetitions (diagonal ignored).
    """
    total, count = 0.0, 0
    for mat in values_by_task.values():
        arr = np.asarray(mat, dtype=float)
        n = arr.shape[0]
        for i, j in itertools.combinations(range(n), 2):  # strictly off-diagonal
            v = arr[i, j]
            if not np.isnan(v):
                total += v
                count += 1
    return (total / count if count else float("nan")), count


def estimate_cross_agreement(
    values_by_task: dict[str, Sequence[Sequence[float]]],
) -> tuple[float, int]:
    """C_AB over the full incumbent x candidate product (no diagonal concept)."""
    total, count = 0.0, 0
    for mat in values_by_task.values():
        arr = np.asarray(mat, dtype=float)
        finite = arr[~np.isnan(arr)]
        total += float(finite.sum())
        count += int(finite.size)
    return (total / count if count else float("nan")), count


def estimate_migration_delta(
    within_by_task: dict[str, Sequence[Sequence[float]]],
    cross_by_task: dict[str, Sequence[Sequence[float]]],
) -> tuple[float, float, float]:
    w, _ = estimate_within_variation(within_by_task)
    c, _ = estimate_cross_agreement(cross_by_task)
    return w, c, c - w


def bootstrap_migration_delta(
    within_by_task: dict[str, Sequence[Sequence[float]]],
    cross_by_task: dict[str, Sequence[Sequence[float]]],
    replicates: int = 10_000,
    seed: int = 20260803,
    ci: tuple[float, float] = (2.5, 97.5),
) -> tuple[float, float, np.ndarray]:
    """Two-level bootstrap: resample TASKS (clusters), then repetitions within.

    Preserves the off-diagonal treatment inside each replicate: duplicate
    repetition draws that would compare a repetition with itself are dropped
    from W_A.
    """
    rng = np.random.default_rng(seed)
    task_ids = sorted(set(within_by_task) & set(cross_by_task))
    if not task_ids:
        raise ValueError("no tasks common to within and cross inputs")
    n_tasks = len(task_ids)
    deltas = np.empty(replicates)

    within_arr = {t: np.asarray(within_by_task[t], float) for t in task_ids}
    cross_arr = {t: np.asarray(cross_by_task[t], float) for t in task_ids}

    for b in range(replicates):
        drawn = [task_ids[i] for i in rng.integers(0, n_tasks, n_tasks)]
        w_tot = w_n = c_tot = c_n = 0.0
        for t in drawn:
            wm = within_arr[t]
            n_a = wm.shape[0]
            idx = rng.integers(0, n_a, n_a)
            for i, j in itertools.combinations(range(n_a), 2):
                a, bb = idx[i], idx[j]
                if a == bb:            # duplicate draw -> self pair -> drop
                    continue
                v = wm[a, bb]
                if not np.isnan(v):
                    w_tot += v
                    w_n += 1
            cm = cross_arr[t]
            ra, rb = cm.shape
            ia = rng.integers(0, ra, ra)
            ib = rng.integers(0, rb, rb)
            sub = cm[np.ix_(ia, ib)]
            fin = sub[~np.isnan(sub)]
            c_tot += float(fin.sum())
            c_n += int(fin.size)
        deltas[b] = ((c_tot / c_n) if c_n else np.nan) - ((w_tot / w_n) if w_n else np.nan)

    lo, hi = np.nanpercentile(deltas, ci[0]), np.nanpercentile(deltas, ci[1])
    return float(lo), float(hi), deltas


def classify_against_tolerance(
    ci_lower: float, ci_upper: float, tolerance: float | None
) -> str:
    """Three-way equivalence classification.

    tolerance=None means no application-grounded tolerance was declared for this
    property (the Pipeline 1 policy): no verdict is issued, only curves.
    """
    if tolerance is None:
        return "no_declared_tolerance"
    if np.isnan(ci_lower) or np.isnan(ci_upper):
        return "uncomputable"
    if ci_upper < -tolerance or ci_lower > tolerance:
        return "rejected"
    if ci_lower >= -tolerance and ci_upper <= tolerance:
        return "demonstrated"
    return "inconclusive"


def tolerance_sensitivity(
    ci_lower: float, ci_upper: float, tolerances: Sequence[float]
) -> dict[float, str]:
    return {t: classify_against_tolerance(ci_lower, ci_upper, t)
            for t in tolerances}


def panel_average_delta(
    per_pair: dict[tuple[str, str], float]
) -> float:
    """SECONDARY / DESCRIPTIVE ONLY — the old symmetric panel statistic.

    Retained solely for comparison with the historical pilot. Never a headline
    result: it averages away exactly the directional, per-property structure the
    pairwise estimand exists to expose.
    """
    vals = [v for v in per_pair.values() if not np.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")
