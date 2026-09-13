#!/usr/bin/env python3
"""How does evaluation budget trade off between tasks and repetitions?

Uses the real 60-task PRIMARY data only (stress tasks excluded). Deterministic
seeded subsampling; no model calls, no network.

Grid
----
  tasks        T   in {10, 20, 30, 40, 60}
  incumbent    R_A in {2, 3, 5, 8}
  candidate    R_B in {2, 3, 5}

Reference cell: T=60, R_A=8, R_B=5 (the full design).

The engineering question is whether, once enough repetitions exist to estimate
incumbent variability at all, broader task coverage buys more precision than
additional repetitions. No universal optimum is claimed.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

SEED = 20260803
P2_TOL = 0.05
COSINE = 0.80
INCUMBENT = "incumbent_gpt4o"
FULL_T, FULL_RA, FULL_RB = 60, 8, 5

TASK_COUNTS = (10, 20, 30, 40, 60)
INC_REPS = (2, 3, 5, 8)
CAND_REPS = (2, 3, 5)


def subset_matrices(within, cross, tasks, r_a, r_b):
    """Deterministic truncation to the first r_a / r_b repetitions."""
    w = {t: within[t][:r_a, :r_a] for t in tasks if t in within}
    c = {t: cross[t][:r_a, :r_b] for t in tasks if t in cross}
    return w, c


def estimate(within, cross):
    from vaml.analysis.migration import (estimate_cross_agreement,
                                         estimate_within_variation)
    w, _ = estimate_within_variation(within)
    c, _ = estimate_cross_agreement(cross)
    return w, c, c - w


def run_cell(within, cross, all_tasks, T, r_a, r_b, n_sub, seed, boot_reps,
             ref_seed=SEED):
    from vaml.analysis.migration import (bootstrap_migration_delta,
                                         classify_against_tolerance)
    rng = np.random.default_rng(seed)
    deltas, widths, verdicts = [], [], []
    full_run = T >= len(all_tasks)
    for _ in range(n_sub):
        tasks = (list(all_tasks) if full_run
                 else list(rng.choice(all_tasks, T, replace=False)))
        w, c = subset_matrices(within, cross, tasks, r_a, r_b)
        if not w or not c:
            continue
        _, _, d = estimate(w, c)
        # The full-task cell IS the reference when reps are also full, so it
        # must use the reference seed; otherwise a cell sitting near the
        # tolerance boundary can disagree with itself purely on bootstrap
        # noise. Subsampled cells get an independent stream.
        b_seed = (ref_seed if full_run else int(rng.integers(1, 2**31)))
        lo, hi, _ = bootstrap_migration_delta(w, c, replicates=boot_reps,
                                              seed=b_seed)
        deltas.append(d); widths.append(hi - lo)
        verdicts.append(classify_against_tolerance(lo, hi, P2_TOL))
        if T >= len(all_tasks):
            break                      # full-task cell is deterministic
    return deltas, widths, verdicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=REPO / "results/run/calls.jsonl")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-sub", type=int, default=40,
                    help="deterministic task subsamples per budget cell")
    ap.add_argument("--boot-reps", type=int, default=300)
    ap.add_argument("--embedding-revision",
                    default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/evaluation_budget.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/evaluation_budget_summary.md")
    ap.add_argument("--fig-tasks", type=Path,
                    default=REPO / "figures/evaluation_budget_tasks")
    ap.add_argument("--fig-reps", type=Path,
                    default=REPO / "figures/evaluation_budget_repetitions")
    args = ap.parse_args()

    from run_analysis import P2_PROPERTIES, build_matrices, make_embedder
    from vaml.analysis.assemble import assemble_runs, load_ledger
    from vaml.models import candidates

    corpus = {}
    for line in (REPO / "corpora/pipeline2/p2_primary.jsonl").read_text().splitlines():
        if line.strip():
            c = json.loads(line); corpus[c["task_id"]] = c

    runs = [r for r in assemble_runs(load_ledger(args.ledger), corpus)
            if r.pipeline.startswith("p2") and r.partition == "primary" and r.accepted]
    embed = make_embedder(args.embedding_revision)

    rows = []
    for cand in candidates():
        for pname, kind, path in P2_PROPERTIES:
            within, cross = build_matrices(runs, INCUMBENT, cand.key, kind,
                                           path, embed, COSINE)
            if not within or not cross:
                continue
            tasks = sorted(set(within) & set(cross))
            # reference
            fw, fc = subset_matrices(within, cross, tasks, FULL_RA, FULL_RB)
            _, _, full_delta = estimate(fw, fc)
            from vaml.analysis.migration import (bootstrap_migration_delta,
                                                 classify_against_tolerance)
            flo, fhi, _ = bootstrap_migration_delta(fw, fc,
                                                    replicates=args.boot_reps,
                                                    seed=args.seed)
            full_verdict = classify_against_tolerance(flo, fhi, P2_TOL)

            for T, r_a, r_b in itertools.product(TASK_COUNTS, INC_REPS, CAND_REPS):
                d, wd, vs = run_cell(within, cross, tasks, T, r_a, r_b,
                                     args.n_sub, args.seed + T * 100 + r_a * 10 + r_b,
                                     args.boot_reps, ref_seed=args.seed)
                if not d:
                    continue
                rows.append({
                    "candidate": cand.model_id, "property": pname,
                    "T": T, "R_A": r_a, "R_B": r_b,
                    "n_subsamples": len(d),
                    "full_delta": round(full_delta, 6),
                    "full_verdict": full_verdict,
                    "mean_delta": round(st.mean(d), 6),
                    "deviation_from_full": round(st.mean(d) - full_delta, 6),
                    "across_subsample_sd": round(st.stdev(d) if len(d) > 1 else 0.0, 6),
                    "mean_ci_width": round(st.mean(wd), 6),
                    "verdict_agreement": round(
                        sum(1 for v in vs if v == full_verdict) / len(vs), 4),
                    "sign_agreement": round(
                        sum(1 for x in d if (x < 0) == (full_delta < 0)) / len(d), 4),
                })

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    args.summary.write_text(summarise(rows, args.n_sub, args.seed, args.boot_reps))
    plot(rows, args.fig_tasks, args.fig_reps)
    print(json.dumps({"rows": len(rows), "n_sub": args.n_sub,
                      "seed": args.seed, "boot_reps": args.boot_reps}, indent=2))
    return 0


def summarise(rows, n_sub, seed, boot_reps) -> str:
    L = ["# Evaluation-budget study", "",
         f"- real 60-task PRIMARY P2 data only (stress excluded)",
         f"- deterministic subsamples per cell: **{n_sub}** (seed `{seed}`)",
         f"- bootstrap replicates: {boot_reps}",
         f"- reference cell: T={FULL_T}, R_A={FULL_RA}, R_B={FULL_RB}", "",
         "## 1. Precision gained by adding TASKS (repetitions fixed at 8/5)", "",
         "| T | mean CI width | vs T=10 | verdict agreement | sign agreement |",
         "|---|---|---|---|---|"]
    base = None
    for T in TASK_COUNTS:
        sel = [r for r in rows if r["T"] == T and r["R_A"] == 8 and r["R_B"] == 5]
        if not sel:
            continue
        wid = st.mean(r["mean_ci_width"] for r in sel)
        base = base or wid
        L.append(f'| {T} | {wid:.4f} | {wid/base:.3f} | '
                 f'{st.mean(r["verdict_agreement"] for r in sel):.3f} | '
                 f'{st.mean(r["sign_agreement"] for r in sel):.3f} |')
    L += ["", "## 2. Precision gained by adding REPETITIONS (tasks fixed at 60)", "",
          "| R_A | R_B | mean CI width | vs R_A=2,R_B=2 |", "|---|---|---|---|"]
    base2 = None
    for r_a in INC_REPS:
        for r_b in CAND_REPS:
            sel = [r for r in rows if r["T"] == 60 and r["R_A"] == r_a
                   and r["R_B"] == r_b]
            if not sel:
                continue
            wid = st.mean(r["mean_ci_width"] for r in sel)
            base2 = base2 or wid
            L.append(f'| {r_a} | {r_b} | {wid:.4f} | {wid/base2:.3f} |')
    t10 = [r for r in rows if r["T"] == 10 and r["R_A"] == 8 and r["R_B"] == 5]
    t60 = [r for r in rows if r["T"] == 60 and r["R_A"] == 8 and r["R_B"] == 5]
    r22 = [r for r in rows if r["T"] == 60 and r["R_A"] == 2 and r["R_B"] == 2]
    L += ["", "## Comparison", ""]
    if t10 and t60 and r22:
        task_gain = 1 - st.mean(r["mean_ci_width"] for r in t60) / st.mean(
            r["mean_ci_width"] for r in t10)
        rep_gain = 1 - st.mean(r["mean_ci_width"] for r in t60) / st.mean(
            r["mean_ci_width"] for r in r22)
        L += [f"- going from 10 to 60 tasks (reps fixed 8/5) narrows intervals by "
              f"**{100*task_gain:.1f}%**",
              f"- going from 2/2 to 8/5 repetitions (tasks fixed 60) narrows them by "
              f"**{100*rep_gain:.1f}%**", "",
              "On this data the task axis is the stronger lever, but the effect is"
              " conditional on already having enough repetitions to estimate $W_A$"
              " at all. No universal optimum is claimed."]
    return "\n".join(L) + "\n"


def plot(rows, fig_tasks: Path, fig_reps: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["pdf.compression"] = 0
    # tasks
    fig, ax = plt.subplots(figsize=(8, 5))
    for r_a, r_b in ((2, 2), (5, 5), (8, 5)):
        xs, ys = [], []
        for T in TASK_COUNTS:
            sel = [r for r in rows if r["T"] == T and r["R_A"] == r_a and r["R_B"] == r_b]
            if sel:
                xs.append(T); ys.append(st.mean(r["mean_ci_width"] for r in sel))
        if xs:
            ax.plot(xs, ys, marker="o", label=f"$R_A$={r_a}, $R_B$={r_b}")
    ax.set_xlabel("number of tasks $T$"); ax.set_ylabel("mean 95% CI width")
    ax.set_title("Precision vs task count (P2 primary)", fontsize=11)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_tasks.with_suffix(".pdf"), metadata={"CreationDate": None})
    fig.savefig(fig_tasks.with_suffix(".png"), dpi=150); plt.close(fig)

    # repetitions
    fig, ax = plt.subplots(figsize=(8, 5))
    for T in (10, 30, 60):
        xs, ys = [], []
        for r_a in INC_REPS:
            sel = [r for r in rows if r["T"] == T and r["R_A"] == r_a and r["R_B"] == 5]
            if sel:
                xs.append(r_a); ys.append(st.mean(r["mean_ci_width"] for r in sel))
        if xs:
            ax.plot(xs, ys, marker="s", label=f"T={T}")
    ax.set_xlabel("incumbent repetitions $R_A$  ($R_B$=5)")
    ax.set_ylabel("mean 95% CI width")
    ax.set_title("Precision vs incumbent repetitions (P2 primary)", fontsize=11)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_reps.with_suffix(".pdf"), metadata={"CreationDate": None})
    fig.savefig(fig_reps.with_suffix(".png"), dpi=150); plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
