#!/usr/bin/env python3
"""Cost estimate from a frozen pricing manifest and the planned run matrix.

Refuses to produce a number from an incomplete manifest: a missing price is
reported as UNPRICED rather than silently treated as zero.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Planned grid: 2 pipelines x 60 primary tasks; incumbent 8 reps, candidates 5.
PRIMARY_TASKS = 60
STRESS_TASKS = 20
INCUMBENT_REPS = 8
CANDIDATE_REPS = 5
STAGES = 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pricing", type=Path, required=True)
    ap.add_argument("--token-profile", type=Path, required=True,
                    help="measured mean input/output tokens per stage per model")
    ap.add_argument("--include-stress", action="store_true")
    args = ap.parse_args()

    pricing = {e["model_id"]: e for e in json.loads(args.pricing.read_text())["entries"]}
    profile = json.loads(args.token_profile.read_text())

    tasks = PRIMARY_TASKS + (STRESS_TASKS if args.include_stress else 0)
    rows, unpriced, total = [], [], 0.0

    for model_id, prof in profile.items():
        entry = pricing.get(model_id)
        reps = INCUMBENT_REPS if prof.get("role") == "incumbent" else CANDIDATE_REPS
        runs = tasks * reps
        in_tok = runs * prof["input_tokens_per_run"]
        out_tok = runs * prof["output_tokens_per_run"]
        mode = prof.get("serving_mode", "batch")
        if entry is None:
            unpriced.append(model_id)
            continue
        ip = entry.get(f"{'batch' if mode == 'batch' else 'standard'}_input")
        op = entry.get(f"{'batch' if mode == 'batch' else 'standard'}_output")
        if ip is None or op is None:
            ip, op = entry.get("standard_input"), entry.get("standard_output")
            mode += " (no batch price; standard applied)"
        if ip is None or op is None:
            unpriced.append(model_id)
            continue
        cost = in_tok / 1e6 * ip + out_tok / 1e6 * op
        total += cost
        rows.append({"model_id": model_id, "serving_mode": mode, "runs": runs,
                     "calls": runs * STAGES, "input_tokens": in_tok,
                     "output_tokens": out_tok, "cost_usd": round(cost, 2)})

    print(json.dumps({
        "tasks_per_pipeline": tasks,
        "rows": rows,
        "total_cost_usd": round(total, 2) if not unpriced else None,
        "UNPRICED_MODELS": unpriced,
        "status": "INCOMPLETE - fill the pricing manifest" if unpriced else "OK",
    }, indent=2))
    return 1 if unpriced else 0


if __name__ == "__main__":
    raise SystemExit(main())
