#!/usr/bin/env python3
"""Is the reported conservative coverage an artifact of only 200 bootstrap draws?

The main simulation used 2,000 datasets x 200 bootstrap replicates. A 200-draw
bootstrap estimates the 2.5%/97.5% quantiles from the 5th and 195th order
statistics, which is coarse: quantile noise widens intervals on average and
could by itself explain method A's over-coverage.

This reruns THREE representative scenarios at much higher bootstrap resolution
and compares. It does not rerun the full grid and does not modify the original
outputs.

Scenarios (one per heterogeneity level, including a T=60 case):
  low     T20_pw0.85_pc0.85_h0.1
  medium  T60_pw0.85_pc0.7_h0.175
  high    T60_pw0.85_pc0.85_h0.25

Deterministic given --seed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from bootstrap_coverage_simulation import (SCENARIOS, run_scenario)  # noqa: E402

SELECTED = ("T20_pw0.85_pc0.85_h0.1",      # low heterogeneity
            "T60_pw0.85_pc0.7_h0.175",     # medium, T=60
            "T60_pw0.85_pc0.85_h0.25")     # highest heterogeneity, T=60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260803)
    ap.add_argument("--n-sim", type=int, default=1000)
    ap.add_argument("--boot-reps", type=int, default=1000)
    ap.add_argument("--baseline", type=Path,
                    default=REPO / "results/strengthening/bootstrap_coverage.csv")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/bootstrap_resolution_sensitivity.csv")
    args = ap.parse_args()

    base = {(r["scenario"], r["method"]): r
            for r in csv.DictReader(args.baseline.open())}
    by_name = {s.name: s for s in SCENARIOS}
    missing = [n for n in SELECTED if n not in by_name]
    if missing:
        print(f"error: scenarios not found: {missing}", file=sys.stderr)
        return 2

    out, t0 = [], time.time()
    for i, name in enumerate(SELECTED):
        sc = by_name[name]
        rows = run_scenario(sc, args.n_sim, args.boot_reps, args.seed + 7000 * i)
        for r in rows:
            b = base.get((name, r["method"]))
            rec = {
                "scenario": name, "method": r["method"],
                "heterogeneity": sc.heterogeneity, "n_tasks": sc.n_tasks,
                "hi_res_n_sim": args.n_sim, "hi_res_boot_reps": args.boot_reps,
                "hi_res_bias": r["bias"], "hi_res_coverage": r["coverage_95"],
                "hi_res_ci_width": r["mean_ci_width"],
                "base_n_sim": int(b["n_sim"]) if b else None,
                "base_boot_reps": 200,
                "base_bias": float(b["bias"]) if b else None,
                "base_coverage": float(b["coverage_95"]) if b else None,
                "base_ci_width": float(b["mean_ci_width"]) if b else None,
            }
            if b:
                rec["coverage_change"] = round(
                    rec["hi_res_coverage"] - rec["base_coverage"], 4)
                rec["ci_width_ratio"] = round(
                    rec["hi_res_ci_width"] / rec["base_ci_width"], 4)
            out.append(rec)
        print(f"  {i+1}/{len(SELECTED)}: {name}", flush=True)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    a = [r for r in out if r["method"].startswith("A")]
    print(json.dumps({
        "scenarios": len(SELECTED), "rows": len(out),
        "runtime_s": round(time.time() - t0, 1),
        "method_A_coverage_change": [r["coverage_change"] for r in a],
        "method_A_width_ratio": [r["ci_width_ratio"] for r in a],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
