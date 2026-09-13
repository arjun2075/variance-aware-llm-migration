#!/usr/bin/env python3
"""Execute the pre-frozen direct-provider replication subset.

Subset, repetitions, prompts, corpora and metric definitions are all frozen and
unchanged. Only the transport differs: direct provider APIs instead of the
managed execution path.

Conditions are limited to those actually callable; unavailable ones are
recorded as gaps (see protocol/NOTE_002_gemini_unavailable.md), never
substituted.
"""
from __future__ import annotations

import argparse, datetime as dt, json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))

from _load_env import load_env  # noqa: E402
from run_experiment import (P1_STAGES, P2_STAGES, load_jsonl, render,  # noqa: E402
                            split_prompt)
from vaml.adapters.public import GeminiAdapter, OpenAIAdapter  # noqa: E402
from vaml.types import CallRequest, Pipeline, RequestID, ServingMode  # noqa: E402

SEED = 20260803
MAX_TOKENS = 8192            # frozen, post Amendment 001
INCUMBENT_REPS = 8           # frozen
CANDIDATE_REPS = 5           # frozen

#: Only conditions verified callable. Others are gaps, not substitutions.
CONDITIONS = [
    ("incumbent_gpt4o", "gpt-4o-2024-11-20", "openai", INCUMBENT_REPS),
    ("candidate_gpt54", "gpt-5.4-2026-03-05", "openai", CANDIDATE_REPS),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "results/replication")
    ap.add_argument("--env-file", default=str(REPO / ".replication.env"))
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    load_env(args.env_file)

    subset = json.loads((REPO / "protocol/replication_subset.json").read_text())
    p1_ids, p2_ids = set(subset["P1_task_ids"]), set(subset["P2_task_ids"])

    adapters = {"openai": OpenAIAdapter(), "gemini": GeminiAdapter()}
    ledger = args.out / "calls.jsonl"
    done = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if line.strip():
                d = json.loads(line); done[d["rid"]] = d
        print(f"resuming: {len(done)} calls recorded")
    fh = ledger.open("a")
    n_new = 0
    t0 = time.time()

    blocks = [
        (Pipeline.P1, P1_STAGES, "prompts/pipeline1",
         [t for t in load_jsonl(REPO / "corpora/pipeline1/p1_primary.jsonl")
          if t["task_id"] in p1_ids]),
        (Pipeline.P2, P2_STAGES, "prompts/pipeline2",
         [t for t in load_jsonl(REPO / "corpora/pipeline2/p2_primary.jsonl")
          if t["task_id"] in p2_ids]),
    ]

    for pipeline, stages, pdir, tasks in blocks:
        templates = {n: split_prompt((REPO / pdir / f).read_text()) for n, f in stages}
        by_id = {t["task_id"]: t for t in tasks}
        print(f"\n=== {pipeline.value}: {len(tasks)} tasks ===", flush=True)
        for task_id in sorted(by_id):
            for key, model_id, prov, reps in CONDITIONS:
                for rep in range(1, reps + 1):
                    upstream, pruned = {}, False
                    for si, (stage, _) in enumerate(stages):
                        rid = RequestID(pipeline, task_id, key, rep, stage, "replication")
                        cid = rid.custom_id()
                        if cid in done:
                            rec = done[cid]
                            if not rec.get("ok", rec.get("error") is None):
                                pruned = True; break
                            class _R: text = rec.get("text")
                            upstream[stage] = _R(); continue
                        if pruned: break
                        sysp, usrp = render(pipeline, si, templates, stages,
                                            by_id[task_id], upstream)
                        req = CallRequest(rid=rid, system_prompt=sysp,
                                          user_prompt=usrp, max_tokens=MAX_TOKENS)
                        # Direct provider APIs enforce per-account TPM limits
                        # (observed: 30k TPM on gpt-4o). Retry 429 with
                        # exponential backoff, matching the frozen retry budget
                        # of 3 attempts used on the managed execution path.
                        res = adapters[prov].call_sync(model_id, req)
                        for attempt in range(1, 4):
                            if res.ok or (res.extra or {}).get("http_status") != 429:
                                break
                            back = 20 * attempt
                            print(f"  429, backing off {back}s", flush=True)
                            time.sleep(back)
                            res = adapters[prov].call_sync(model_id, req)
                            res.retry_count = attempt
                        rec = json.loads(res.to_json())
                        fh.write(json.dumps(rec, sort_keys=True) + "\n"); fh.flush()
                        done[cid] = rec; n_new += 1
                        if not res.ok:
                            pruned = True; break
                        upstream[stage] = res
                        if args.limit and n_new >= args.limit:
                            fh.close(); print(f"limit {args.limit} reached"); return 0
                    if n_new and n_new % 40 == 0:
                        print(f"  {n_new} new calls, {(time.time()-t0)/60:.1f} min",
                              flush=True)
    fh.close()
    (args.out / "summary.json").write_text(json.dumps({
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "new_calls": n_new, "total_calls": len(done),
        "conditions": [{"key": k, "model_id": m, "reps": r} for k, m, _, r in CONDITIONS],
        "excluded_conditions": ["gemini-2.5-pro (withdrawn from new users)",
                                "amazon.nova-pro-v1:0 (AWS credentials expired)",
                                "meta.llama4-maverick-17b-instruct-v1:0 (AWS credentials expired)"],
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"new_calls": n_new, "total": len(done),
                      "minutes": round((time.time()-t0)/60, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
