#!/usr/bin/env python3
"""Execute the frozen confirmatory grid against the managed execution path.

Serial, paced, checkpointed. Resumable: already-completed calls are skipped on
restart, so a multi-day run survives interruption without re-spending.

Frozen behaviour, not tunable here:
  * execution order is the seeded interleaved permutation
  * retry policy matches the frozen rules (429 -> 15/30/60s + jitter)
  * a run whose upstream stage failed is pruned, not retried differently
  * canonical model provenance is checked against the frozen mapping and
    FLAGGED, never silently accepted
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from build_p2_corpus import inference_view  # noqa: E402
from vaml.adapters.shim import TransportAdapter  # noqa: E402
from vaml.models import MATRIX, repetitions_for  # noqa: E402
from vaml.orchestration.rate_limits import PacedExecutor, RateLimitPolicy  # noqa: E402
from vaml.orchestration.waves import build_execution_order  # noqa: E402
from vaml.types import CallRequest, Pipeline, RequestID, ServingMode  # noqa: E402

SEED = 20260803

#: Uniform output ceiling for ALL five model conditions. Deliberately NOT
#: per-model: a per-model ceiling would make the serving configuration
#: non-uniform across the comparison and undermine the migration claim.
#:
#: Amended 2026-09-09 from 2048 -> 8192 before the confirmatory run. See
#: protocol/AMENDMENT_001_max_tokens.md. 2048 was an implementation constant,
#: not a frozen scientific parameter; at that ceiling gemini-2.5-pro terminated
#: with finish_reason=length on 15/28 QC calls (54%) because it spends most of
#: its budget on internal reasoning tokens (~0.13 chars/token vs ~4.5 for
#: gpt-4o). That would have confounded model behaviour with an avoidable
#: output-budget artifact.
MAX_TOKENS = 8192

P1_STAGES = [("pr_signal", "stage1_pr_signal.md"),
             ("review_signal", "stage2_review_signal.md"),
             ("synthesis", "stage3_synthesis.md"),
             ("deepen", "stage4_deepen.md")]
P2_STAGES = [("extract_evidence", "stage1_extract_evidence.md"),
             ("assess_evidence", "stage2_assess_evidence.md"),
             ("classify", "stage3_classify.md"),
             ("verify", "stage4_verify.md")]

BLOCKS = [
    (Pipeline.P1, P1_STAGES, "prompts/pipeline1", "corpora/pipeline1/p1_primary.jsonl", "primary", None),
    (Pipeline.P2, P2_STAGES, "prompts/pipeline2", "corpora/pipeline2/p2_primary.jsonl", "primary", None),
    (Pipeline.P1, P1_STAGES, "prompts/pipeline1", "corpora/pipeline1/p1_stress.jsonl", "stress", None),
    (Pipeline.P2, P2_STAGES, "prompts/pipeline2", "corpora/pipeline2/p2_stress.jsonl", "stress", None),
    (Pipeline.P1, P1_STAGES, "prompts/pipeline1", "corpora/pipeline1/p1_primary.jsonl", "sync_operational", 10),
    (Pipeline.P2, P2_STAGES, "prompts/pipeline2", "corpora/pipeline2/p2_primary.jsonl", "sync_operational", 10),
]


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def split_prompt(md: str) -> tuple[str, str]:
    s = re.search(r"^## System\s*\n(.*?)(?=^## User)", md, re.S | re.M)
    u = re.search(r"^## User\s*\n(.*)$", md, re.S | re.M)
    return s.group(1).strip(), u.group(1).strip()


def render(pipeline, stage_i, templates, stages, task, upstream) -> tuple[str, str]:
    name = stages[stage_i][0]
    sys_p, usr_t = templates[name]
    u = usr_t
    if pipeline is Pipeline.P2:
        v = inference_view(task)          # gold stripped here
        u = u.replace("{{DOCUMENT_TEXT}}", v["document_text"]).replace(
            "{{HYPOTHESIS}}", v["hypothesis"])
    else:
        u = u.replace("{{RECORD}}", json.dumps(
            {k: v for k, v in task.items() if k != "partition"}, sort_keys=True))
        u = u.replace("{{SIGNALS}}", json.dumps(
            task.get("narrative_signals", []), sort_keys=True))
    for i, (sname, _) in enumerate(stages):
        if sname in upstream:
            u = u.replace("{{STAGE%d}}" % (i + 1), upstream[sname].text or "")
    return sys_p, u


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "results/run")
    ap.add_argument("--env-file", default=os.environ.get("VAML_ENV_FILE"),
                    help="credentials file; defaults to $VAML_ENV_FILE. "
                         "Values are never logged.")
    ap.add_argument("--limit", type=int, help="stop after N calls (rehearsal)")
    ap.add_argument("--only-block", type=int, help="run only this block index")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    adapter = TransportAdapter(env_file=args.env_file)
    policy = RateLimitPolicy()
    pacer = PacedExecutor(policy)
    rng = random.Random(SEED)
    fam = {m.key: m.provider_family for m in MATRIX}
    mid = {m.key: m.model_id for m in MATRIX}

    ledger = args.out / "calls.jsonl"
    done: dict[str, dict] = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                done[d["rid"]] = d
        print(f"resuming: {len(done)} calls already recorded")

    fh = ledger.open("a")
    n_new = 0
    t_start = time.time()

    for bi, (pipeline, stages, pdir, cpath, partition, cap) in enumerate(BLOCKS):
        if args.only_block is not None and bi != args.only_block:
            continue
        tasks = load_jsonl(REPO / cpath)
        if cap:
            tasks = tasks[:cap]
        templates = {n: split_prompt((REPO / pdir / f).read_text())
                     for n, f in stages}
        models = {m.key: (None, m.model_id, repetitions_for(m)) for m in MATRIX}
        order = build_execution_order(tasks, models, seed=SEED)
        by_id = {t["task_id"]: t for t in tasks}
        mode = (ServingMode.SYNC if partition == "sync_operational"
                else ServingMode.SYNC)  # no batch API; all calls are sync

        print(f"\n=== block {bi}: {pipeline.value} / {partition} "
              f"({len(tasks)} tasks, {len(order)} runs) ===", flush=True)

        for oi, (task_id, model_key, rep) in enumerate(order):
            upstream: dict = {}
            pruned = False
            for si, (stage_name, _) in enumerate(stages):
                rid = RequestID(pipeline, task_id, model_key, rep, stage_name,
                                partition)
                cid = rid.custom_id()
                if cid in done:
                    rec = done[cid]
                    if not rec.get("ok"):
                        pruned = True
                        break
                    class _R:  # minimal transport helper for downstream rendering
                        text = rec.get("text")
                    upstream[stage_name] = _R()
                    continue
                if pruned:
                    break
                sys_p, usr_p = render(pipeline, si, templates, stages,
                                      by_id[task_id], upstream)
                req = CallRequest(rid=rid, system_prompt=sys_p,
                                  user_prompt=usr_p, max_tokens=MAX_TOKENS)

                # frozen retry policy
                res = None
                for attempt in range(1, policy.max_retries + 1):
                    pacer.acquire(fam[model_key])
                    try:
                        res = adapter.call_sync(mid[model_key], req)
                    finally:
                        pacer.release()
                    st = (res.extra or {}).get("http_status")
                    # 401/403 across a long-lived process means stale auth
                    # state (typically after a suspend), not a rejected
                    # request. Restart the transport helper to re-fetch the IAM ticket and
                    # retry under the SAME frozen retry budget - no extra
                    # attempts, no changed backoff.
                    if not res.ok and st in (401, 403):
                        print(f"  auth {st}: restarting transport helper to refresh ticket",
                              flush=True)
                        adapter.restart()
                        time.sleep(2)
                        continue
                    if res.ok or st not in (429, 502, 503):
                        break
                    back = pacer.backoff_for_attempt(attempt, rng)
                    print(f"  retry {attempt} after {st} in {back:.0f}s",
                          flush=True)
                    time.sleep(back)
                res.retry_count = max(res.retry_count, attempt - 1)
                res.execution_order_index = oi

                rec = json.loads(res.to_json())
                rec["block"] = bi
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                fh.flush()
                done[cid] = rec
                n_new += 1

                if not res.ok:
                    pruned = True
                    break
                upstream[stage_name] = res

                if args.limit and n_new >= args.limit:
                    print(f"\nlimit {args.limit} reached")
                    fh.close()
                    adapter.close()
                    return 0

            if oi % 25 == 0:
                el = time.time() - t_start
                print(f"  run {oi+1}/{len(order)} · {n_new} new calls · "
                      f"{el/60:.1f} min elapsed", flush=True)

    fh.close()
    adapter.close()
    summary = {
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "new_calls_this_session": n_new,
        "total_calls_recorded": len(done),
        "elapsed_minutes": round((time.time() - t_start) / 60, 1),
        "pacing": {"max_concurrency": policy.max_concurrency,
                   "total_wait_s": round(pacer.total_wait_s, 1)},
    }
    (args.out / "run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
