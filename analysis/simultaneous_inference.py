#!/usr/bin/env python3
"""Simultaneous 95% confidence intervals across the 12 P2 primary cells.

The reported pointwise intervals each cover their own Delta with 95%
probability. Across 12 cells that does not control the probability that ALL
intervals cover simultaneously. This constructs simultaneous bands by the
bootstrap max-statistic (max-|t|) method.

Method
------
For each bootstrap replicate b, the SAME resampled task set is used for every
cell, so the dependence between cells is preserved — the 12 estimates move
together because they share tasks and share the incumbent's runs. Then

    Z_b = max over cells of  |Delta_b(cell) - Delta_hat(cell)| / se(cell)

and the simultaneous band for each cell is

    Delta_hat(cell) +/- q_{0.95}(Z) * se(cell)

where se is the bootstrap standard deviation for that cell. Using a common
critical value q across cells is what makes the coverage simultaneous.

This is a ROBUSTNESS analysis. It does not replace the pointwise intervals as
the paper's primary inference, and introduces no new multiple-testing criterion.

Metric definitions, eligibility, the off-diagonal estimator, task set and seed
are all frozen and unchanged. No model calls, no network.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

SEED = 20260803          # frozen
REPLICATES = 10_000      # frozen convention
COSINE = 0.80            # frozen
P2_TOL = 0.05            # frozen declared tolerance
INCUMBENT = "incumbent_gpt4o"
CI_LEVEL = 95.0


def _offdiag_mean(mats: list[np.ndarray]) -> float:
    tot = n = 0.0
    for m in mats:
        iu = np.triu_indices(m.shape[0], k=1)
        v = m[iu]
        v = v[~np.isnan(v)]
        tot += float(v.sum()); n += v.size
    return tot / n if n else float("nan")


def _flat_mean(mats: list[np.ndarray]) -> float:
    tot = n = 0.0
    for m in mats:
        v = m[~np.isnan(m)]
        tot += float(v.sum()); n += v.size
    return tot / n if n else float("nan")


def point_delta(within: dict, cross: dict, tasks) -> float:
    return (_flat_mean([cross[t] for t in tasks if t in cross])
            - _offdiag_mean([within[t] for t in tasks if t in within]))


def joint_bootstrap(cells: list[dict], replicates: int, seed: int):
    """Bootstrap all cells on COMMON task resamples.

    cells: list of {"within": {...}, "cross": {...}} sharing a task universe.
    Returns (draws[replicates, n_cells], point[n_cells]).
    """
    tasks = sorted(set.intersection(*[set(c["within"]) & set(c["cross"])
                                      for c in cells]))
    n = len(tasks)
    point = np.array([point_delta(c["within"], c["cross"], tasks) for c in cells])
    draws = np.full((replicates, len(cells)), np.nan)
    rng = np.random.default_rng(seed)
    for b in range(replicates):
        idx = rng.integers(0, n, n)
        drawn = [tasks[i] for i in idx]
        # the SAME drawn task multiset is used for every cell
        for k, c in enumerate(cells):
            w = [c["within"][t] for t in drawn if t in c["within"]]
            x = [c["cross"][t] for t in drawn if t in c["cross"]]
            if w and x:
                draws[b, k] = _flat_mean(x) - _offdiag_mean(w)
    return draws, point, tasks


def simultaneous_band(draws: np.ndarray, point: np.ndarray,
                      level: float = CI_LEVEL):
    """Max-|t| simultaneous band plus the pointwise band for comparison."""
    se = np.nanstd(draws, axis=0, ddof=1)
    se_safe = np.where(se > 0, se, np.nan)
    t = np.abs(draws - point[None, :]) / se_safe[None, :]
    zmax = np.nanmax(t, axis=1)
    q = float(np.nanpercentile(zmax, level))
    sim_lo, sim_hi = point - q * se, point + q * se
    pw_lo = np.nanpercentile(draws, (100 - level) / 2, axis=0)
    pw_hi = np.nanpercentile(draws, 100 - (100 - level) / 2, axis=0)
    return {"critical_value": q, "se": se,
            "sim_lower": sim_lo, "sim_upper": sim_hi,
            "boot_pointwise_lower": pw_lo, "boot_pointwise_upper": pw_hi}


def verdict(lo: float, hi: float, tau: float) -> str:
    """Frozen verdict definition, unchanged."""
    if np.isnan(lo) or np.isnan(hi):
        return "uncomputable"
    if hi < -tau or lo > tau:
        return "rejected"
    if lo >= -tau and hi <= tau:
        return "demonstrated"
    return "inconclusive"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=REPO / "results/run/calls.jsonl")
    ap.add_argument("--pairwise", type=Path,
                    default=REPO / "results/analysis/pairwise_results.json")
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--embedding-revision",
                    default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/simultaneous_inference.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/simultaneous_inference_summary.md")
    args = ap.parse_args()

    from run_analysis import P2_PROPERTIES, build_matrices, make_embedder
    from vaml.analysis.assemble import assemble_runs, load_ledger
    from vaml.models import candidates

    corpus = {}
    for part in ("primary", "stress"):
        for line in (REPO / f"corpora/pipeline2/p2_{part}.jsonl").read_text().splitlines():
            if line.strip():
                c = json.loads(line); corpus[c["task_id"]] = c

    runs = [r for r in assemble_runs(load_ledger(args.ledger), corpus)
            if r.pipeline.startswith("p2") and r.partition == "primary" and r.accepted]
    embed = make_embedder(args.embedding_revision)
    frozen = {(r["property"], r["candidate"]): r
              for r in json.loads(args.pairwise.read_text())["P2"]}

    cells, labels = [], []
    for cand in candidates():
        for pname, kind, path in P2_PROPERTIES:
            w, c = build_matrices(runs, INCUMBENT, cand.key, kind, path,
                                  embed, COSINE)
            if w and c:
                cells.append({"within": w, "cross": c})
                labels.append((pname, cand.model_id))

    draws, point, tasks = joint_bootstrap(cells, args.replicates, args.seed)
    band = simultaneous_band(draws, point)

    rows = []
    for k, (pname, cand) in enumerate(labels):
        f = frozen[(pname, cand)]
        pw_lo, pw_hi = f["ci_lower"], f["ci_upper"]
        sl, sh = float(band["sim_lower"][k]), float(band["sim_upper"][k])
        rows.append({
            "property": pname, "candidate": cand,
            "delta": round(float(point[k]), 6),
            "frozen_delta": round(f["delta"], 6),
            "frozen_ci_lower": round(pw_lo, 6), "frozen_ci_upper": round(pw_hi, 6),
            "frozen_ci_width": round(pw_hi - pw_lo, 6),
            "frozen_verdict": f["verdict"],
            "simultaneous_lower": round(sl, 6),
            "simultaneous_upper": round(sh, 6),
            "simultaneous_width": round(sh - sl, 6),
            "width_inflation_factor": round((sh - sl) / (pw_hi - pw_lo), 4),
            "simultaneous_verdict": verdict(sl, sh, P2_TOL),
            "verdict_changed": verdict(sl, sh, P2_TOL) != f["verdict"],
            "critical_value": round(band["critical_value"], 4),
            "bootstrap_se": round(float(band["se"][k]), 6),
        })

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    args.summary.write_text(summarise(rows, band["critical_value"],
                                      args.replicates, args.seed, len(tasks)))
    print(json.dumps({
        "cells": len(rows), "tasks": len(tasks),
        "critical_value": round(band["critical_value"], 4),
        "mean_inflation": round(
            sum(r["width_inflation_factor"] for r in rows) / len(rows), 4),
        "verdicts_changed": sum(r["verdict_changed"] for r in rows),
    }, indent=2))
    return 0


def summarise(rows, q, replicates, seed, n_tasks) -> str:
    import statistics as st
    changed = [r for r in rows if r["verdict_changed"]]
    spans = [r for r in rows if "span" in r["property"]]
    labels_ = [r for r in rows if r["property"] == "label_agreement"]
    L = ["# Simultaneous inference across the 12 P2 primary cells", "",
         "Pointwise 95% intervals each cover their own Delta with 95%",
         "probability; across 12 cells that does not control simultaneous",
         "coverage. This constructs max-|t| simultaneous bands using **common**",
         "bootstrap task resamples, so the dependence between cells is",
         "preserved rather than assumed away.", "",
         f"- cells: **{len(rows)}**", f"- tasks: **{n_tasks}**",
         f"- bootstrap replicates: **{replicates}** (seed `{seed}`)",
         f"- simultaneous critical value: **{q:.4f}**  "
         f"(pointwise would be ~1.96)",
         f"- mean width inflation: "
         f"**{st.mean(r['width_inflation_factor'] for r in rows):.3f}x**", "",
         "This is a robustness analysis. It does not replace the pointwise",
         "intervals as the paper's primary inference.", "",
         "## Verdict changes", "",
         f"**{len(changed)} of {len(rows)} verdicts change** under simultaneous",
         "intervals at the frozen tolerance 0.05.", ""]
    if changed:
        L += ["| property | candidate | frozen | simultaneous | pointwise CI | simultaneous CI |",
              "|---|---|---|---|---|---|"]
        for r in changed:
            L.append(f'| {r["property"]} | {r["candidate"][:22]} | '
                     f'{r["frozen_verdict"]} | {r["simultaneous_verdict"]} | '
                     f'[{r["frozen_ci_lower"]:+.3f}, {r["frozen_ci_upper"]:+.3f}] | '
                     f'[{r["simultaneous_lower"]:+.3f}, {r["simultaneous_upper"]:+.3f}] |')
    L += ["", "## Does the span-vs-label conclusion survive?", "",
          f"- span cells rejected, pointwise: "
          f"**{sum(1 for r in spans if r['frozen_verdict'] == 'rejected')}/{len(spans)}**",
          f"- span cells rejected, simultaneous: "
          f"**{sum(1 for r in spans if r['simultaneous_verdict'] == 'rejected')}/{len(spans)}**",
          f"- mean |Delta| spans **{st.mean(abs(r['delta']) for r in spans):.4f}** "
          f"vs labels **{st.mean(abs(r['delta']) for r in labels_):.4f}**", "",
          "## All cells", "",
          "| property | candidate | Delta | pointwise CI | simultaneous CI | "
          "inflation | frozen | simultaneous |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f'| {r["property"][:24]} | {r["candidate"][:20]} | '
                 f'{r["delta"]:+.4f} | [{r["frozen_ci_lower"]:+.3f}, '
                 f'{r["frozen_ci_upper"]:+.3f}] | [{r["simultaneous_lower"]:+.3f}, '
                 f'{r["simultaneous_upper"]:+.3f}] | {r["width_inflation_factor"]:.3f}x '
                 f'| {r["frozen_verdict"]} | {r["simultaneous_verdict"]} |')
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
