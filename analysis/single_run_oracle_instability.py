#!/usr/bin/env python3
"""How much does a migration conclusion move if you pick a different incumbent run?

Conventional regression testing captures ONE incumbent execution as the expected
output and compares candidates against it. This script enumerates all 8 possible
choices of incumbent oracle — exactly, not by sampling — and reports how far the
conclusion swings purely as a function of which run happened to be captured.

For each (pipeline, property, candidate):
  * mean / min / max / sd of single-oracle agreement across the 8 choices
  * the implied effect range
  * the verdict range where a tolerance is declared
  * the fraction of oracle choices yielding each verdict

Identity check: the mean over the 8 uniformly-chosen oracles equals the
all-repetition cross-agreement C_AB, because C_AB is the mean over the same
8 x R_B comparisons.

The identity is EXACT when every comparison is eligible, and holds "modulo
weighting conventions" otherwise. Where a metric marks some pairs ineligible
(NaN), the per-oracle mean drops NaNs row by row, so an oracle with fewer
eligible comparisons still contributes 1/8 of the average, whereas the flat
C_AB weights each surviving comparison equally. In this dataset ineligibility
is rare (e.g. 5 of 2,400 cells for M1.collaboration / gpt-5.4), and the
residual is correspondingly small — under 1e-3 on every cell, and exactly zero
on the 24 cells with no ineligible comparisons.

No model calls, no network. Deterministic.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

P2_TOL = 0.05           # frozen
COSINE = 0.80           # frozen
INCUMBENT = "incumbent_gpt4o"


def verdict_from_point(delta: float, tau: float | None) -> str:
    """Point-estimate verdict. A single-run oracle gives no interval, which is
    itself part of the problem being demonstrated."""
    if tau is None:
        return "no_declared_tolerance"
    if delta < -tau:
        return "worse_than_tolerance"
    if delta > tau:
        return "better_than_tolerance"
    return "within_tolerance"


def oracle_curves(cross_by_task: dict[str, np.ndarray]) -> dict:
    """Per-oracle cross-agreement, enumerating every incumbent repetition.

    cross_by_task maps task -> (R_A x R_B) matrix. Oracle i uses row i only.
    """
    n_a = next(iter(cross_by_task.values())).shape[0]
    per_oracle = []
    for i in range(n_a):
        vals = []
        for m in cross_by_task.values():
            row = m[i, :]
            row = row[~np.isnan(row)]
            if row.size:
                vals.append(float(row.mean()))
        per_oracle.append(float(np.mean(vals)) if vals else float("nan"))
    return {"per_oracle": per_oracle, "n_oracles": n_a}


def all_rep_cross(cross_by_task: dict[str, np.ndarray]) -> float:
    """Unweighted mean over every incumbent x candidate comparison."""
    vals = []
    for m in cross_by_task.values():
        f = m[~np.isnan(m)]
        if f.size:
            vals.append(float(f.mean()))
    return float(np.mean(vals)) if vals else float("nan")


def build_rows(runs, embed, properties, pipeline_tag, candidates_,
               w_a_lookup, tau) -> list[dict]:
    from run_analysis import build_matrices

    rows = []
    for cand in candidates_:
        for pname, kind, path in properties:
            _, cross = build_matrices(runs, INCUMBENT, cand.key, kind, path,
                                      embed, COSINE)
            if not cross:
                continue
            cur = oracle_curves(cross)
            per = [v for v in cur["per_oracle"] if not np.isnan(v)]
            if not per:
                continue
            w_a = w_a_lookup[(pipeline_tag, pname)]
            c_all = all_rep_cross(cross)
            deltas = [c - w_a for c in per]
            verdicts = [verdict_from_point(d, tau) for d in deltas]
            frac = {v: round(verdicts.count(v) / len(verdicts), 4)
                    for v in sorted(set(verdicts))}
            rows.append({
                "pipeline": pipeline_tag, "property": pname,
                "candidate": cand.model_id,
                "n_oracles": cur["n_oracles"],
                "W_A": round(w_a, 6),
                "C_AB_all_reps": round(c_all, 6),
                "oracle_mean": round(st.mean(per), 6),
                "oracle_min": round(min(per), 6),
                "oracle_max": round(max(per), 6),
                "oracle_range": round(max(per) - min(per), 6),
                "oracle_sd": round(st.stdev(per) if len(per) > 1 else 0.0, 6),
                "identity_residual": round(abs(st.mean(per) - c_all), 9),
                "delta_min": round(min(deltas), 6),
                "delta_max": round(max(deltas), 6),
                "delta_range": round(max(deltas) - min(deltas), 6),
                "distinct_verdicts": len(set(verdicts)),
                "verdict_fractions": json.dumps(frac),
            })
    return rows


def summarise(rows) -> str:
    p2 = [r for r in rows if r["pipeline"] == "P2"]
    worst = max(rows, key=lambda r: r["oracle_range"])
    unstable = [r for r in p2 if r["distinct_verdicts"] > 1]
    L = ["# Single-run regression-oracle instability", "",
         "Conventional regression testing captures one incumbent execution as",
         "the expected output. This enumerates all 8 possible choices exactly.",
         "",
         f"- cells analysed: **{len(rows)}**",
         f"- oracle choices per cell: **8** (exact enumeration, not sampling)",
         f"- mean agreement range across oracle choices: "
         f"**{st.mean(r['oracle_range'] for r in rows):.4f}**",
         f"- largest range: **{worst['oracle_range']:.4f}** "
         f"({worst['pipeline']}·{worst['property']} / {worst['candidate'][:24]})",
         "",
         "## Identity check", "",
         "The mean over uniformly-chosen single oracles must equal the",
         "all-repetition cross-agreement. Maximum residual across all cells: "
         f"**{max(r['identity_residual'] for r in rows):.2e}**.", "",
         "## Verdict instability (P2, declared tolerance 0.05)", "",
         f"**{len(unstable)} of {len(p2)} P2 cells** yield more than one verdict",
         "depending only on which incumbent run was chosen as the oracle.", ""]
    if unstable:
        L += ["| property | candidate | delta range | verdicts |", "|---|---|---|---|"]
        for r in sorted(unstable, key=lambda r: -r["delta_range"]):
            L.append(f'| {r["property"][:24]} | {r["candidate"][:22]} | '
                     f'[{r["delta_min"]:+.4f}, {r["delta_max"]:+.4f}] | '
                     f'{r["verdict_fractions"]} |')
    L += ["", "## All cells", "",
          "| pipeline | property | candidate | oracle mean | min | max | range | sd |",
          "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["oracle_range"]):
        L.append(f'| {r["pipeline"]} | {r["property"][:24]} | {r["candidate"][:22]} '
                 f'| {r["oracle_mean"]:.4f} | {r["oracle_min"]:.4f} | '
                 f'{r["oracle_max"]:.4f} | {r["oracle_range"]:.4f} | {r["oracle_sd"]:.4f} |')
    return "\n".join(L) + "\n"


def plot(rows, out_pdf: Path, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = sorted(rows, key=lambda r: r["oracle_range"])
    fig, ax = plt.subplots(figsize=(10, max(5, 0.22 * len(order))))
    for i, r in enumerate(order):
        colour = "#c0392b" if r["distinct_verdicts"] > 1 else "#2980b9"
        ax.plot([r["oracle_min"], r["oracle_max"]], [i, i], color=colour, lw=3,
                solid_capstyle="round")
        ax.plot([r["oracle_mean"]], [i], marker="D", color="black", markersize=4)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f'{r["pipeline"]}·{r["property"][:22]}·{r["candidate"][:18]}'
                        for r in order], fontsize=5.5)
    ax.set_xlabel("cross-model agreement under a single incumbent oracle")
    ax.set_title("How far a migration conclusion moves with the choice of\n"
                 "incumbent regression oracle (all 8 choices enumerated)",
                 fontsize=11)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#c0392b", label="verdict changes with oracle choice"),
                       Patch(color="#2980b9", label="verdict stable")],
              loc="lower right", fontsize=7)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams["pdf.compression"] = 0
    fig.savefig(out_pdf, metadata={"CreationDate": None})
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=REPO / "results/run/calls.jsonl")
    ap.add_argument("--pairwise", type=Path,
                    default=REPO / "results/analysis/pairwise_results.json")
    ap.add_argument("--embedding-revision",
                    default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/single_run_oracle_instability.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/single_run_oracle_summary.md")
    ap.add_argument("--pdf", type=Path,
                    default=REPO / "figures/single_run_oracle_instability.pdf")
    ap.add_argument("--png", type=Path,
                    default=REPO / "figures/single_run_oracle_instability.png")
    args = ap.parse_args()

    from run_analysis import (P1_PROPERTIES, P2_PROPERTIES, make_embedder)
    from vaml.analysis.assemble import assemble_runs, load_ledger
    from vaml.models import candidates

    corpus = {}
    for part in ("primary", "stress"):
        for line in (REPO / f"corpora/pipeline2/p2_{part}.jsonl").read_text().splitlines():
            if line.strip():
                c = json.loads(line); corpus[c["task_id"]] = c

    pw = json.loads(args.pairwise.read_text())
    w_a = {}
    for p in ("P1", "P2"):
        for r in pw[p]:
            w_a.setdefault((p, r["property"]), r["W_A"])

    runs = assemble_runs(load_ledger(args.ledger), corpus)
    embed = make_embedder(args.embedding_revision)
    cands = candidates()

    rows = []
    for tag, props, pref, tau in (("P1", P1_PROPERTIES, "p1", None),
                                  ("P2", P2_PROPERTIES, "p2", P2_TOL)):
        sel = [r for r in runs if r.pipeline.startswith(pref)
               and r.partition == "primary" and r.accepted]
        rows.extend(build_rows(sel, embed, props, tag, cands, w_a, tau))

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    args.summary.write_text(summarise(rows))
    plot(rows, args.pdf, args.png)
    print(json.dumps({
        "cells": len(rows),
        "max_identity_residual": max(r["identity_residual"] for r in rows),
        "mean_oracle_range": round(st.mean(r["oracle_range"] for r in rows), 6),
        "max_oracle_range": max(r["oracle_range"] for r in rows),
        "p2_cells_with_unstable_verdict": sum(
            1 for r in rows if r["pipeline"] == "P2" and r["distinct_verdicts"] > 1),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
