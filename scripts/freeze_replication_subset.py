#!/usr/bin/env python3
"""Freeze the public-API replication subset BEFORE any results are seen.

The replication asks whether the qualitative findings reproduce outside the
managed execution path. That question is only meaningful if the subset was chosen without
knowledge of the results -- otherwise a "reproduces" verdict could be an
artifact of picking convenient tasks.

This script therefore runs NOW, while the confirmatory grid is still in
flight and no scientific result has been inspected. Selection is a seeded
draw stratified the same way the corpora were built. No model call is made.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = 20260803
N_PER_PIPELINE = 10


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=REPO / "protocol/replication_subset.json")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    rng = random.Random(args.seed + 9001)   # distinct stream from corpus build

    p1 = load(REPO / "corpora/pipeline1/p1_primary.jsonl")
    p2 = load(REPO / "corpora/pipeline2/p2_primary.jsonl")

    # P1: stratify across difficulty so the subset is not all easy cases.
    by_diff: dict[str, list[dict]] = {}
    for c in p1:
        by_diff.setdefault(c["axes"]["difficulty"], []).append(c)
    p1_pick: list[dict] = []
    diffs = sorted(by_diff)
    i = 0
    while len(p1_pick) < N_PER_PIPELINE:
        pool = [c for c in by_diff[diffs[i % len(diffs)]] if c not in p1_pick]
        if pool:
            p1_pick.append(rng.choice(pool))
        i += 1
        if i > 1000:
            break

    # P2: stratify across the three gold labels.
    by_label: dict[str, list[dict]] = {}
    for c in p2:
        by_label.setdefault(c["gold_label"], []).append(c)
    p2_pick: list[dict] = []
    labels = sorted(by_label)
    i = 0
    while len(p2_pick) < N_PER_PIPELINE:
        pool = [c for c in by_label[labels[i % len(labels)]] if c not in p2_pick]
        if pool:
            p2_pick.append(rng.choice(pool))
        i += 1
        if i > 1000:
            break

    doc = {
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "frozen_before_any_results_inspected": True,
        "note": ("Selected while the confirmatory grid was still running and "
                 "no agreement, correctness or equivalence result had been "
                 "computed or viewed. This ordering is what makes the "
                 "replication interpretable."),
        "seed": args.seed,
        "n_per_pipeline": N_PER_PIPELINE,
        "selection_rule": {
            "P1": "round-robin across difficulty strata, seeded choice within stratum",
            "P2": "round-robin across the three gold labels, seeded choice within label",
        },
        "P1_task_ids": [c["task_id"] for c in p1_pick],
        "P1_difficulty": {c["task_id"]: c["axes"]["difficulty"] for c in p1_pick},
        "P2_task_ids": [c["task_id"] for c in p2_pick],
        "P2_gold_labels": {c["task_id"]: c["gold_label"] for c in p2_pick},
    }
    doc["selection_sha256"] = hashlib.sha256(
        json.dumps({k: doc[k] for k in ("P1_task_ids", "P2_task_ids")},
                   sort_keys=True).encode()).hexdigest()

    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"P1": doc["P1_task_ids"], "P2": doc["P2_task_ids"],
                      "selection_sha256": doc["selection_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
