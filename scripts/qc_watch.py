#!/usr/bin/env python3
"""Operational QC watch for an in-flight run.

DELIBERATELY BLIND TO SCIENTIFIC RESULTS. This tool never reads response TEXT
content, never computes agreement, correctness or equivalence, and never
touches gold labels. It reports only:

  truncation rate · errors/retries · provenance mismatches · parse failures
  (as an infrastructure signal only) · ledger integrity · checkpoint health
  · rate-limit behaviour

Parse success is reported as a COUNT only, because a sudden collapse indicates
an infrastructure fault. Which model parses better is a scientific result and
is not surfaced per-model beyond what an infrastructure fault would require.

Exit code is non-zero when an operational alert fires.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
from pathlib import Path

TOTAL_PLANNED = 20160
# Operational alert thresholds. These gate INFRASTRUCTURE health only.
ALERT_ERROR_RATE = 0.02
ALERT_TRUNC_RATE = 0.10
ALERT_PARSE_FAIL_RATE = 0.35
ALERT_RETRY_RATE = 0.05


def parses(text: str | None) -> bool:
    if not text:
        return False
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    try:
        json.loads(s)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=Path("results/run/calls.jsonl"))
    args = ap.parse_args()
    if not args.ledger.exists():
        print("no ledger yet")
        return 0

    raw = args.ledger.read_text().splitlines()
    rows, malformed = [], 0
    for line in raw:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    if not rows:
        print("ledger empty")
        return 0

    ok = [r for r in rows if r["error"] is None]
    bad = [r for r in rows if r["error"]]
    trunc = [r for r in ok if (r.get("extra") or {}).get("finish_reason") == "length"]
    mism = [r for r in rows if (r.get("extra") or {}).get("canonical_model_mismatch")]
    retried = [r for r in rows if (r.get("retry_count") or 0) > 0]
    unparsed = [r for r in ok if not parses(r.get("text"))]

    t0 = min(r["submitted_at"] for r in rows)
    t1 = max(r["completed_at"] for r in rows)
    el = (dt.datetime.fromisoformat(t1.replace("Z", "+00:00"))
          - dt.datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds()
    rate = len(rows) / el if el else 0

    # ledger integrity: duplicate rids would corrupt the grid
    dupes = [k for k, n in collections.Counter(r["rid"] for r in rows).items() if n > 1]

    print(f"progress       : {len(rows)}/{TOTAL_PLANNED} "
          f"({100*len(rows)/TOTAL_PLANNED:.1f}%)  elapsed {el/3600:.1f} h")
    if rate:
        print(f"rate           : {rate:.3f} calls/s  "
              f"(~{(TOTAL_PLANNED-len(rows))/rate/3600:.0f} h left)")
    print(f"errors         : {len(bad)} ({100*len(bad)/len(rows):.2f}%)")
    print(f"retries        : {len(retried)} ({100*len(retried)/len(rows):.2f}%)")
    print(f"truncated      : {len(trunc)} ({100*len(trunc)/max(1,len(ok)):.2f}%)")
    print(f"parse failures : {len(unparsed)} ({100*len(unparsed)/max(1,len(ok)):.2f}%)"
          f"   [infrastructure signal only]")
    print(f"provenance     : {len(mism)} mismatch(es) FLAGGED")
    print(f"ledger         : {len(rows)} records, {malformed} malformed, "
          f"{len(dupes)} duplicate rid(s)")
    print(f"blocks         : {dict(sorted(collections.Counter(r.get('block') for r in rows).items()))}")

    if bad:
        print("\nerror categories:")
        for k, n in sorted(collections.Counter(
                (r.get("extra") or {}).get("error_category") or "unknown"
                for r in bad).items()):
            print(f"  {k}: {n}")
        print("http statuses:", dict(sorted(collections.Counter(
            (r.get("extra") or {}).get("http_status") for r in bad).items(),
            key=lambda kv: str(kv[0]))))

    if trunc:
        print("\ntruncation by model (ceiling health):")
        d = collections.defaultdict(lambda: [0, 0])
        for r in ok:
            d[r["returned_model_id"]][1] += 1
            if (r.get("extra") or {}).get("finish_reason") == "length":
                d[r["returned_model_id"]][0] += 1
        for m, (t, n) in sorted(d.items()):
            if t:
                print(f"  {m}: {t}/{n} ({100*t/n:.0f}%)")

    alerts = []
    if len(bad) / len(rows) > ALERT_ERROR_RATE:
        alerts.append(f"error rate {100*len(bad)/len(rows):.1f}% > {100*ALERT_ERROR_RATE:.0f}%")
    if len(trunc) / max(1, len(ok)) > ALERT_TRUNC_RATE:
        alerts.append(f"truncation {100*len(trunc)/len(ok):.1f}% > {100*ALERT_TRUNC_RATE:.0f}% "
                      f"- ceiling may be insufficient again")
    if len(unparsed) / max(1, len(ok)) > ALERT_PARSE_FAIL_RATE:
        alerts.append(f"parse failures {100*len(unparsed)/len(ok):.1f}% "
                      f"- possible infrastructure fault")
    if len(retried) / len(rows) > ALERT_RETRY_RATE:
        alerts.append(f"retry rate {100*len(retried)/len(rows):.1f}% - rate limiting?")
    if mism:
        alerts.append(f"{len(mism)} canonical model mismatch(es)")
    if malformed or dupes:
        alerts.append(f"ledger integrity: {malformed} malformed, {len(dupes)} duplicates")

    if alerts:
        print("\n*** OPERATIONAL ALERTS ***")
        for a in alerts:
            print(f"  ! {a}")
        return 1
    print("\nno operational alerts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
