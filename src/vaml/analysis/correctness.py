"""Correctness x behavior decomposition (Pipeline 2).

A purely behavioral regression test cannot tell these apart:

  A. behavior changed + correctness IMPROVED   <- the candidate is BETTER, yet a
                                                  naive regression oracle FAILS it
  B. behavior changed + correctness WORSENED   <- genuine regression
  C. behavior preserved + incumbent was CORRECT <- clean low-risk migration
  D. behavior preserved + incumbent ERROR preserved
                                               <- outputs agree, and they agree on
                                                  being WRONG. NOT a success.

Quadrant D is the trap this study exists to expose: agreement with an incumbent
is only good news when the incumbent was right. `MigrationOutcome.is_success`
therefore refuses to call D a success, and the reporting helpers refuse to emit
behavioral preservation for P2 without the paired correctness change.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import numpy as np


class Quadrant(str, Enum):
    A_CHANGED_IMPROVED = "A_behavior_changed_correctness_improved"
    B_CHANGED_WORSENED = "B_behavior_changed_correctness_worsened"
    C_PRESERVED_CORRECT = "C_behavior_preserved_incumbent_correct"
    D_PRESERVED_ERROR = "D_behavior_preserved_incumbent_error_preserved"
    #: correctness change is not distinguishable from zero
    INDETERMINATE = "indeterminate_correctness_change"


@dataclass(frozen=True)
class MigrationOutcome:
    incumbent: str
    candidate: str
    property_name: str
    behavior_preserved: bool
    behavioral_delta: float
    incumbent_accuracy: float
    candidate_accuracy: float
    accuracy_delta: float
    accuracy_ci: tuple[float, float]
    quadrant: Quadrant
    #: Accuracy on the pre-registered subset the incumbent gets WRONG.
    agreement_on_incumbent_errors: float | None = None
    n_incumbent_errors: int = 0

    @property
    def is_success(self) -> bool:
        """Quadrant D is explicitly NOT a success.

        Preserving an incumbent error is a preserved defect, however
        reassuringly stable the behavioral metric looks.
        """
        return self.quadrant in (Quadrant.C_PRESERVED_CORRECT,
                                 Quadrant.A_CHANGED_IMPROVED)

    @property
    def headline(self) -> str:
        return {
            Quadrant.A_CHANGED_IMPROVED:
                "behavior changed, correctness IMPROVED - a naive regression "
                "oracle would wrongly block this migration",
            Quadrant.B_CHANGED_WORSENED:
                "behavior changed and correctness WORSENED - genuine regression",
            Quadrant.C_PRESERVED_CORRECT:
                "behavior preserved on correct incumbent outputs - low-risk",
            Quadrant.D_PRESERVED_ERROR:
                "behavior preserved INCLUDING incumbent errors - agreement here "
                "is agreement on being wrong; NOT a successful migration",
            Quadrant.INDETERMINATE:
                "correctness change not distinguishable from zero",
        }[self.quadrant]


def classify_quadrant(
    behavior_preserved: bool,
    accuracy_delta: float,
    accuracy_ci: tuple[float, float],
    incumbent_accuracy: float,
    incumbent_error_rate_threshold: float = 0.0,
) -> Quadrant:
    """Assign the joint quadrant.

    A correctness change whose CI straddles zero is INDETERMINATE rather than
    being forced into an improved/worsened bucket.
    """
    lo, hi = accuracy_ci
    improved = lo > 0
    worsened = hi < 0

    if not behavior_preserved:
        if improved:
            return Quadrant.A_CHANGED_IMPROVED
        if worsened:
            return Quadrant.B_CHANGED_WORSENED
        return Quadrant.INDETERMINATE

    # Behavior preserved: the question is what was preserved.
    if incumbent_accuracy < 1.0 - incumbent_error_rate_threshold:
        # The incumbent makes errors and the candidate mirrors its behavior,
        # so those errors are being carried forward.
        return Quadrant.D_PRESERVED_ERROR
    return Quadrant.C_PRESERVED_CORRECT


def bootstrap_accuracy_delta(
    incumbent_correct: Sequence[bool],
    candidate_correct: Sequence[bool],
    task_ids: Sequence[str],
    replicates: int = 10_000,
    seed: int = 20260803,
) -> tuple[float, float, float]:
    """Cluster bootstrap of (candidate - incumbent) accuracy, resampling tasks.

    Returns (point_estimate, ci_lower, ci_upper).
    """
    inc = np.asarray(incumbent_correct, dtype=float)
    cand = np.asarray(candidate_correct, dtype=float)
    tids = np.asarray(task_ids)
    if not (len(inc) == len(cand) == len(tids)):
        raise ValueError("incumbent, candidate and task_ids must align")

    uniq = np.unique(tids)
    by_task = {t: np.where(tids == t)[0] for t in uniq}
    point = float(cand.mean() - inc.mean())

    rng = np.random.default_rng(seed)
    draws = np.empty(replicates)
    n = len(uniq)
    for b in range(replicates):
        picks = rng.integers(0, n, n)
        idx = np.concatenate([by_task[uniq[i]] for i in picks])
        draws[b] = cand[idx].mean() - inc[idx].mean()
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def agreement_on_incumbent_errors(
    incumbent_correct: Sequence[bool],
    behavioral_agreement: Sequence[float],
) -> tuple[float | None, int]:
    """Behavioral agreement restricted to items the incumbent got WRONG.

    High agreement here is the quantitative signature of quadrant D. Reported
    separately and never folded into the headline behavioral metric.
    """
    inc = np.asarray(incumbent_correct, dtype=bool)
    agr = np.asarray(behavioral_agreement, dtype=float)
    mask = ~inc
    n = int(mask.sum())
    if n == 0:
        return None, 0
    vals = agr[mask]
    vals = vals[~np.isnan(vals)]
    return (float(vals.mean()) if vals.size else None), n


def format_report_row(o: MigrationOutcome) -> dict:
    """Reporting helper.

    Behavioral preservation is never emitted without the paired correctness
    change, so a reader cannot read one without the other.
    """
    return {
        "incumbent": o.incumbent,
        "candidate": o.candidate,
        "property": o.property_name,
        "behavioral_delta": round(o.behavioral_delta, 6),
        "behavior_preserved": o.behavior_preserved,
        "incumbent_accuracy": round(o.incumbent_accuracy, 6),
        "candidate_accuracy": round(o.candidate_accuracy, 6),
        "accuracy_delta": round(o.accuracy_delta, 6),
        "accuracy_ci_lower": round(o.accuracy_ci[0], 6),
        "accuracy_ci_upper": round(o.accuracy_ci[1], 6),
        "quadrant": o.quadrant.value,
        "is_success": o.is_success,
        "agreement_on_incumbent_errors": (
            None if o.agreement_on_incumbent_errors is None
            else round(o.agreement_on_incumbent_errors, 6)),
        "n_incumbent_errors": o.n_incumbent_errors,
        "interpretation": o.headline,
    }
