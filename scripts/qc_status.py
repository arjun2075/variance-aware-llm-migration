#!/usr/bin/env python3
"""Operational QC snapshot of an in-flight run.

Deliberately reports ONLY operational/QC information -- counts, errors,
provenance, tokens, pacing. It does not compute or display any scientific
result, so watching the run cannot influence the analysis.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path

TOTAL_PLANNED_CALLS = 20160


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=Path("results/run/calls.jsonl"))
    args = ap.parse_args()
    if not args.ledger.exists():
        print("no ledger yet")
        return 0

    rows = [json.loads(l) for l in args.ledger.read_text().splitlines() if l.strip()]
    if not rows:
        print("ledger empty")
        return 0

    ok = [r for r in rows if r["error"] is None]
    bad = [r for r in rows if r["error"]]
    t0 = min(r["submitted_at"] for r in rows)
    t1 = max(r["completed_at"] for r in rows)
    el = (dt.datetime.fromisoformat(t1.replace("Z", "+00:00"))
          - dt.datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds()
    rate = len(rows) / el if el > 0 else 0

    print(f"calls recorded : {len(rows)} / {TOTAL_PLANNED_CALLS} "
          f"({100*len(rows)/TOTAL_PLANNED_CALLS:.1f}%)")
    print(f"  ok           : {len(ok)}")
    print(f"  errors       : {len(bad)}")
    print(f"elapsed        : {el/3600:.2f} h")
    print(f"rate           : {rate:.3f} calls/s")
    if rate:
        rem = (TOTAL_PLANNED_CALLS - len(rows)) / rate / 3600
        print(f"projected left : {rem:.1f} h")

    print("\nby block:")
    for b, n in sorted(collections.Counter(r.get("block") for r in rows).items()):
        print(f"  block {b}: {n}")

    print("\ncanonical provenance:")
    mism = [r for r in rows if (r.get("extra") or {}).get("canonical_model_mismatch")]
    print(f"  mismatches FLAGGED: {len(mism)}")
    for k, n in sorted(collections.Counter(
            r["returned_model_id"] for r in ok if r["returned_model_id"]).items()):
        print(f"    {k}: {n}")

    if bad:
        print("\nerrors by category:")
        for k, n in sorted(collections.Counter(
                (r.get("extra") or {}).get("error_category") or r["error"][:40]
                for r in bad).items()):
            print(f"  {k}: {n}")

    retried = [r for r in rows if r.get("retry_count", 0) > 0]
    print(f"\nretries        : {len(retried)} calls retried")
    ptok = sum(r.get("prompt_tokens") or 0 for r in ok)
    ctok = sum(r.get("completion_tokens") or 0 for r in ok)
    print(f"tokens so far  : {ptok:,} in / {ctok:,} out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
