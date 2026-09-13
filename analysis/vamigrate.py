#!/usr/bin/env python3
"""vamigrate — reference implementation of the variance-aware migration test.

Consumes PRECOMPUTED outputs only. It never invokes a model and makes no
network call: given incumbent and candidate outputs that already exist, it
reports W_A, C_AB, Delta, an interval, and a verdict against a declared
tolerance.

    vamigrate compare --incumbent inc.jsonl --candidate cand.jsonl \
                      --metric exact [--tolerance 0.05] [--json]

Input format: JSONL, one record per line, with at least

    {"task_id": "t1", "repetition": 1, "value": <scoreable>}

`value` may be a scalar (compared with the `exact` metric) or a list (compared
with `jaccard` / `multiset` / `sequence`). Optional per-record fields
`correct` (bool) and `invariant_ok` (bool) are summarised when present.

All statistics reuse the tested implementations in `vaml.analysis`; no formula
is duplicated here.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from vaml.analysis.metrics import (exact_agreement, jaccard,  # noqa: E402
                                   multiset_agreement, ordinal_agreement,
                                   sequence_agreement)
from vaml.analysis.migration import (bootstrap_migration_delta,  # noqa: E402
                                     classify_against_tolerance,
                                     estimate_cross_agreement,
                                     estimate_within_variation)

METRICS = {
    "exact": exact_agreement,
    "ordinal": ordinal_agreement,
    "jaccard": jaccard,
    "multiset": multiset_agreement,
    "sequence": sequence_agreement,
}


class InputError(Exception):
    """Malformed or unusable input."""


def load_records(path: Path) -> dict[str, dict[int, dict]]:
    if not path.exists():
        raise InputError(f"file not found: {path}")
    out: dict[str, dict[int, dict]] = collections.defaultdict(dict)
    n = 0
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise InputError(f"{path}:{lineno}: invalid JSON ({e.msg})") from None
        if not isinstance(rec, dict):
            raise InputError(f"{path}:{lineno}: each line must be a JSON object")
        for field in ("task_id", "repetition", "value"):
            if field not in rec:
                raise InputError(f"{path}:{lineno}: missing required field '{field}'")
        try:
            rep = int(rec["repetition"])
        except (TypeError, ValueError):
            raise InputError(
                f"{path}:{lineno}: 'repetition' must be an integer") from None
        if rep in out[str(rec["task_id"])]:
            raise InputError(f"{path}:{lineno}: duplicate repetition {rep} "
                             f"for task {rec['task_id']}")
        out[str(rec["task_id"])][rep] = rec
        n += 1
    if not n:
        raise InputError(f"{path}: no records found")
    return dict(out)


def build_matrices(inc: dict, cand: dict, metric: str):
    if metric not in METRICS:
        raise InputError(f"unknown metric '{metric}'. "
                         f"choose from: {', '.join(sorted(METRICS))}")
    fn = METRICS[metric]
    shared = sorted(set(inc) & set(cand))
    if not shared:
        raise InputError("no task_id appears in both incumbent and candidate files")
    within, cross = {}, {}
    for t in shared:
        a = [inc[t][k]["value"] for k in sorted(inc[t])]
        b = [cand[t][k]["value"] for k in sorted(cand[t])]
        if len(a) >= 2:
            m = np.full((len(a), len(a)), np.nan)
            for i in range(len(a)):
                for j in range(len(a)):
                    if i != j:
                        v = fn(a[i], a[j])
                        m[i, j] = np.nan if v is None else v
            within[t] = m
        m = np.full((len(a), len(b)), np.nan)
        for i in range(len(a)):
            for j in range(len(b)):
                v = fn(a[i], b[j])
                m[i, j] = np.nan if v is None else v
        cross[t] = m
    if not within:
        raise InputError("incumbent needs at least 2 repetitions per task to "
                         "estimate W_A")
    return shared, within, cross


def optional_fields(recs: dict) -> dict:
    flat = [r for t in recs.values() for r in t.values()]
    out = {}
    corr = [r["correct"] for r in flat if "correct" in r]
    if corr:
        out["accuracy"] = round(sum(bool(c) for c in corr) / len(corr), 6)
    inv = [r["invariant_ok"] for r in flat if "invariant_ok" in r]
    if inv:
        out["invariant_rate"] = round(sum(bool(c) for c in inv) / len(inv), 6)
    return out


def compare(incumbent: Path, candidate: Path, metric: str,
            tolerance: float | None, replicates: int, seed: int) -> dict:
    inc, cand = load_records(incumbent), load_records(candidate)
    tasks, within, cross = build_matrices(inc, cand, metric)
    w_a, n_w = estimate_within_variation(within)
    c_ab, n_c = estimate_cross_agreement(cross)
    lo, hi, _ = bootstrap_migration_delta(within, cross, replicates=replicates,
                                          seed=seed)
    res = {
        "n_tasks": len(tasks),
        "incumbent_repetitions": max(len(v) for v in inc.values()),
        "candidate_repetitions": max(len(v) for v in cand.values()),
        "metric": metric,
        "W_A": round(w_a, 6), "C_AB": round(c_ab, 6),
        "Delta": round(c_ab - w_a, 6),
        "ci_lower": round(lo, 6), "ci_upper": round(hi, 6),
        "n_within_pairs": int(n_w), "n_cross_pairs": int(n_c),
        "replicates": replicates, "seed": seed,
        "warnings": [],
    }
    if tolerance is not None:
        res["tolerance"] = tolerance
        res["verdict"] = classify_against_tolerance(lo, hi, tolerance)
        if w_a > 0 and tolerance >= w_a:
            res["warnings"].append(
                f"tolerance {tolerance} >= W_A {w_a:.4f}: the test cannot exclude "
                f"C_AB = 0, so it is vacuous on the negative side")
        elif w_a == 0:
            res["warnings"].append(
                "W_A = 0: the incumbent never agrees with itself on this metric, "
                "so no migration verdict is meaningful")
    inc_extra, cand_extra = optional_fields(inc), optional_fields(cand)
    if inc_extra or cand_extra:
        res["incumbent_extra"] = inc_extra
        res["candidate_extra"] = cand_extra
        if "accuracy" in inc_extra and "accuracy" in cand_extra:
            res["accuracy_delta"] = round(
                cand_extra["accuracy"] - inc_extra["accuracy"], 6)
    return res


def render(res: dict) -> str:
    L = [f'tasks                 {res["n_tasks"]}',
         f'incumbent repetitions {res["incumbent_repetitions"]}',
         f'candidate repetitions {res["candidate_repetitions"]}',
         f'metric                {res["metric"]}',
         "",
         f'W_A                   {res["W_A"]:.4f}   ({res["n_within_pairs"]} pairs)',
         f'C_AB                  {res["C_AB"]:.4f}   ({res["n_cross_pairs"]} pairs)',
         f'Delta = C_AB - W_A    {res["Delta"]:+.4f}',
         f'95% CI                [{res["ci_lower"]:+.4f}, {res["ci_upper"]:+.4f}]']
    if "verdict" in res:
        L += ["", f'tolerance             {res["tolerance"]}',
              f'verdict               {res["verdict"].upper()}']
    for k in ("accuracy_delta",):
        if k in res:
            L.append(f'{k:<21} {res[k]:+.4f}')
    if res.get("incumbent_extra") or res.get("candidate_extra"):
        L.append("")
        for side in ("incumbent", "candidate"):
            e = res.get(f"{side}_extra") or {}
            for k, v in e.items():
                L.append(f'{side} {k:<11} {v:.4f}')
    for w in res["warnings"]:
        L += ["", f"WARNING: {w}"]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vamigrate",
                                 description="Variance-aware migration test "
                                             "over precomputed outputs.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="compare a candidate against an incumbent")
    c.add_argument("--incumbent", type=Path, required=True)
    c.add_argument("--candidate", type=Path, required=True)
    c.add_argument("--metric", default="exact",
                   help=f"one of: {', '.join(sorted(METRICS))}")
    c.add_argument("--tolerance", type=float)
    c.add_argument("--replicates", type=int, default=10000)
    c.add_argument("--seed", type=int, default=20260803)
    c.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        res = compare(args.incumbent, args.candidate, args.metric,
                      args.tolerance, args.replicates, args.seed)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2, sort_keys=True) if args.json else render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
