#!/usr/bin/env python3
"""Continuous tolerance-decision curves for the 12 frozen P2 primary cells.

Reads the frozen point estimates and bootstrap intervals and re-expresses the
three-way classification as a function of tau. Nothing is recomputed: the CI
endpoints are taken verbatim from results/analysis/pairwise_results.json.

Classification rule (unchanged from the confirmatory analysis):

    rejected      : ci_upper < -tau   or  ci_lower > +tau
    demonstrated  : -tau <= ci_lower  and ci_upper <= +tau
    inconclusive  : otherwise

For an interval lying entirely below zero — which is every P2 cell — the
transitions are exact functions of the endpoints:

    rejected      while  tau <  -ci_upper
    inconclusive  while  -ci_upper <= tau < -ci_lower
    demonstrated  once   tau >= -ci_lower

so the two transition points are tau = -ci_upper and tau = -ci_lower. The
general form below also handles intervals that straddle or sit above zero.

No network, no model calls, deterministic.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAU_MIN, TAU_MAX, TAU_STEP = 0.0, 0.20, 0.001
CLASSES = ("rejected", "inconclusive", "demonstrated")


def classify(ci_lower: float, ci_upper: float, tau: float) -> str:
    """Three-way verdict. Identical rule to the confirmatory analysis."""
    if ci_upper < -tau or ci_lower > tau:
        return "rejected"
    if ci_lower >= -tau and ci_upper <= tau:
        return "demonstrated"
    return "inconclusive"


def transition_points(ci_lower: float, ci_upper: float) -> dict:
    """Exact tau values where the classification changes.

    Derived analytically from the endpoints rather than found by scanning, so
    the reported values are exact rather than grid-resolution-limited.
    """
    # tau below which the interval is entirely outside [-tau, tau]
    if ci_upper < 0:
        rejected_until = -ci_upper       # rejected while tau < -ci_upper
    elif ci_lower > 0:
        rejected_until = ci_lower        # rejected while tau < ci_lower
    else:
        rejected_until = 0.0             # straddles zero: never rejected

    # tau at or above which the interval is entirely inside [-tau, tau]
    demonstrated_from = max(abs(ci_lower), abs(ci_upper))

    return {
        "rejected_until_tau": round(rejected_until, 6),
        "demonstrated_from_tau": round(demonstrated_from, 6),
        "inconclusive_window": round(max(0.0, demonstrated_from - rejected_until), 6),
    }


def load_p2_cells(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    out = []
    for r in data["P2"]:
        out.append({
            "pipeline": "P2", "property": r["property"], "candidate": r["candidate"],
            "delta": r["delta"], "ci_lower": r["ci_lower"], "ci_upper": r["ci_upper"],
            "frozen_verdict": r["verdict"],
        })
    return out


def build_transition_rows(cells: list[dict]) -> list[dict]:
    rows = []
    for c in cells:
        t = transition_points(c["ci_lower"], c["ci_upper"])
        rows.append({
            "property": c["property"], "candidate": c["candidate"],
            "delta": round(c["delta"], 6),
            "ci_lower": round(c["ci_lower"], 6),
            "ci_upper": round(c["ci_upper"], 6),
            **t,
            "verdict_at_tau_0.05": classify(c["ci_lower"], c["ci_upper"], 0.05),
            "verdict_at_tau_0.10": classify(c["ci_lower"], c["ci_upper"], 0.10),
            "verdict_at_tau_0.20": classify(c["ci_lower"], c["ci_upper"], 0.20),
            "frozen_verdict_at_declared_tol": c["frozen_verdict"],
        })
    return rows


def verify_against_frozen(cells: list[dict], declared_tau: float = 0.05) -> list[str]:
    """The re-derived verdict at the declared tolerance must match the frozen one."""
    bad = []
    for c in cells:
        got = classify(c["ci_lower"], c["ci_upper"], declared_tau)
        if got != c["frozen_verdict"]:
            bad.append(f'{c["property"]}/{c["candidate"]}: '
                       f'derived {got} != frozen {c["frozen_verdict"]}')
    return bad


def plot(cells: list[dict], out_pdf: Path, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    taus = np.arange(TAU_MIN, TAU_MAX + TAU_STEP / 2, TAU_STEP)
    colour = {"rejected": "#c0392b", "inconclusive": "#f0ad4e",
              "demonstrated": "#27ae60"}
    order = sorted(cells, key=lambda c: (c["property"], c["candidate"]))

    fig, ax = plt.subplots(figsize=(11, 6.5))
    for i, c in enumerate(order):
        for t in taus:
            ax.barh(i, TAU_STEP, left=t,
                    color=colour[classify(c["ci_lower"], c["ci_upper"], t)],
                    edgecolor="none")
        tp = transition_points(c["ci_lower"], c["ci_upper"])
        for x in (tp["rejected_until_tau"], tp["demonstrated_from_tau"]):
            if TAU_MIN < x <= TAU_MAX:
                ax.plot([x], [i], marker="|", color="black", markersize=12, mew=1.2)

    ax.axvline(0.05, color="black", linestyle="--", linewidth=1.4)
    ax.text(0.051, len(order) - 0.4, "declared τ = 0.05", fontsize=8, rotation=90,
            va="top")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f'{c["property"][:24]} · {c["candidate"][:20]}'
                        for c in order], fontsize=7)
    ax.set_xlabel("tolerance τ")
    ax.set_xlim(TAU_MIN, TAU_MAX)
    ax.set_title("Pipeline 2: verdict as a continuous function of tolerance\n"
                 "(derived from the frozen bootstrap interval endpoints)",
                 fontsize=11)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=colour[k], label=k) for k in CLASSES],
              loc="lower right", fontsize=8)
    fig.tight_layout()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams["pdf.compression"] = 0
    fig.savefig(out_pdf, metadata={"CreationDate": None})
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairwise", type=Path,
                    default=REPO / "results/analysis/pairwise_results.json")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/p2_tolerance_transition_points.csv")
    ap.add_argument("--pdf", type=Path,
                    default=REPO / "figures/p2_tolerance_decision_curves.pdf")
    ap.add_argument("--png", type=Path,
                    default=REPO / "figures/p2_tolerance_decision_curves.png")
    args = ap.parse_args()

    cells = load_p2_cells(args.pairwise)
    mismatches = verify_against_frozen(cells)
    if mismatches:
        print("ERROR: derived verdicts disagree with the frozen results:")
        for m in mismatches:
            print("  " + m)
        return 1

    rows = build_transition_rows(cells)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    plot(cells, args.pdf, args.png)

    flips = sum(1 for r in rows
                if len({r["verdict_at_tau_0.05"], r["verdict_at_tau_0.10"],
                        r["verdict_at_tau_0.20"]}) > 1)
    print(json.dumps({"cells": len(rows), "verdicts_match_frozen": True,
                      "cells_changing_verdict_over_sweep": flips,
                      "csv": str(args.csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
