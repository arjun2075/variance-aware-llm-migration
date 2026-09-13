#!/usr/bin/env python3
"""Mandatory zero-cost mocked end-to-end orchestration.

Runs the ACTUAL frozen corpora and ACTUAL prompt templates through the full wave
orchestrator with MockAdapter. No network call, no spend.

What this proves before a paid run:
  * every corpus record renders through every prompt template
  * wave dependencies sequence correctly across all four stages
  * identity survives shuffled, out-of-order batch-style results
  * the P2 inference view never carries a gold field into a prompt
  * pacing/provenance fields are populated
  * counts match the frozen design exactly

    python scripts/dry_run.py --out results/dry_run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from build_p2_corpus import inference_view  # noqa: E402
from vaml.adapters.base import MockAdapter  # noqa: E402
from vaml.models import MATRIX, repetitions_for  # noqa: E402
from vaml.orchestration.rate_limits import RateLimitPolicy  # noqa: E402
from vaml.orchestration.waves import (  # noqa: E402
    ExecutionPlan, WaveOrchestrator, WaveSpec, build_execution_order,
)
from vaml.types import Pipeline, RequestID, ServingMode  # noqa: E402

SEED = 20260803

P1_STAGES = [("pr_signal", "stage1_pr_signal.md"),
             ("review_signal", "stage2_review_signal.md"),
             ("synthesis", "stage3_synthesis.md"),
             ("deepen", "stage4_deepen.md")]
P2_STAGES = [("extract_evidence", "stage1_extract_evidence.md"),
             ("assess_evidence", "stage2_assess_evidence.md"),
             ("classify", "stage3_classify.md"),
             ("verify", "stage4_verify.md")]


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def split_prompt(md: str) -> tuple[str, str]:
    sys_m = re.search(r"^## System\s*\n(.*?)(?=^## User)", md, re.S | re.M)
    usr_m = re.search(r"^## User\s*\n(.*)$", md, re.S | re.M)
    if not sys_m or not usr_m:
        raise ValueError("prompt template missing '## System' or '## User'")
    return sys_m.group(1).strip(), usr_m.group(1).strip()


def make_waves(pipeline: Pipeline, stages, prompt_dir: Path):
    templates = {name: split_prompt((prompt_dir / f).read_text())
                 for name, f in stages}
    order = [name for name, _ in stages]

    def make(stage_name: str, prev: str | None):
        sys_p, usr_t = templates[stage_name]

        def build(task: dict, up: dict) -> tuple[str, str]:
            u = usr_t
            if pipeline is Pipeline.P2:
                view = inference_view(task)   # gold stripped here
                u = (u.replace("{{DOCUMENT_TEXT}}", view["document_text"])
                      .replace("{{HYPOTHESIS}}", view["hypothesis"]))
            else:
                u = u.replace("{{RECORD}}", json.dumps(
                    {k: v for k, v in task.items() if k != "partition"},
                    sort_keys=True))
                u = u.replace("{{SIGNALS}}", json.dumps(
                    task.get("narrative_signals", []), sort_keys=True))
            for i, s in enumerate(order):
                if s in up:
                    u = u.replace("{{STAGE%d}}" % (i + 1), up[s].text or "")
            return sys_p, u
        return WaveSpec(stage_name, build, 2048)

    return [make(name, order[i - 1] if i else None)
            for i, name in enumerate(order)]


def run_block(pipeline, stages, prompt_dir, cases, partition, mode, out, adapter):
    models = {m.key: (adapter, m.model_id, repetitions_for(m)) for m in MATRIX}
    plan = ExecutionPlan(pipeline, partition, cases, models,
                         make_waves(pipeline, stages, prompt_dir), mode,
                         build_execution_order(cases, models, seed=SEED))
    orch = WaveOrchestrator(plan, out / pipeline.value / partition)
    res = orch.run_all()
    expected = sum(len(cases) * r for _, _, r in models.values()) * len(stages)
    return {"pipeline": pipeline.value, "partition": partition,
            "serving_mode": mode.value, "tasks": len(cases),
            "results": len(res), "expected": expected,
            "pruned": len(orch.pruned),
            "match": len(res) == expected}, orch


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("results/dry_run"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    adapter = MockAdapter(seed=SEED)

    p1p = load_jsonl(REPO / "corpora/pipeline1/p1_primary.jsonl")
    p1s = load_jsonl(REPO / "corpora/pipeline1/p1_stress.jsonl")
    p2p = load_jsonl(REPO / "corpora/pipeline2/p2_primary.jsonl")
    p2s = load_jsonl(REPO / "corpora/pipeline2/p2_stress.jsonl")

    blocks, orchs = [], []
    for pipeline, stages, pdir, prim, stress in (
        (Pipeline.P1, P1_STAGES, REPO / "prompts/pipeline1", p1p, p1s),
        (Pipeline.P2, P2_STAGES, REPO / "prompts/pipeline2", p2p, p2s),
    ):
        for part, cases, mode in (
            ("primary", prim, ServingMode.BATCH),
            ("stress", stress, ServingMode.BATCH),
            ("sync_operational", prim[:10], ServingMode.SYNC),
        ):
            b, o = run_block(pipeline, stages, pdir, cases, part, mode,
                             args.out, adapter)
            blocks.append(b)
            orchs.append((pipeline, o))

    # ---- invariants -------------------------------------------------
    checks = {
        "all_blocks_complete": all(b["match"] for b in blocks),
        "no_unexpected_pruning": all(b["pruned"] == 0 for b in blocks),
    }

    ids_ok = True
    for f in args.out.rglob("*.jsonl"):
        for line in f.read_text().splitlines():
            rec = json.loads(line)
            try:
                if RequestID.parse(rec["rid"]).custom_id() != rec["rid"]:
                    ids_ok = False
            except ValueError:
                ids_ok = False
    checks["all_custom_ids_roundtrip"] = ids_ok

    checks["batch_has_no_latency"] = all(
        json.loads(l)["latency_ms"] is None
        for f in args.out.rglob("*.jsonl") if "sync" not in str(f)
        for l in f.read_text().splitlines())
    checks["sync_records_latency"] = all(
        json.loads(l)["latency_ms"] is not None
        for f in args.out.rglob("*sync_operational*.jsonl")
        for l in f.read_text().splitlines() if json.loads(l)["text"])
    checks["execution_order_recorded"] = all(
        json.loads(l)["execution_order_index"] is not None
        for f in args.out.rglob("*.jsonl")
        for l in f.read_text().splitlines())

    # gold leakage: rebuild every P2 prompt and scan it
    leaks = []
    for case in p2p + p2s:
        waves = make_waves(Pipeline.P2, P2_STAGES, REPO / "prompts/pipeline2")
        _, user = waves[0].build_prompt(case, {})
        if case["gold_label"] in user:
            leaks.append(case["task_id"])
        for span in case["gold_spans"]:
            # the span legitimately occurs inside the contract text; what must
            # never appear is a gold marker calling it out
            if f'"gold' in user.lower():
                leaks.append(case["task_id"])
                break
    checks["no_gold_leakage_in_rendered_prompts"] = not leaks

    policy = RateLimitPolicy()
    summary = {
        "dry_run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "paid_api_calls": 0,
        "adapter": "MockAdapter (no network)",
        "seed": SEED,
        "models": [m.model_id for m in MATRIX],
        "rate_limit_policy": {
            "max_concurrency": policy.max_concurrency,
            "min_interval_s": policy.min_interval_s,
            "bedrock_min_interval_s": policy.bedrock_min_interval_s,
        },
        "blocks": blocks,
        "checks": checks,
        "gold_leaks": leaks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    (args.out / "dry_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": summary["status"], "checks": checks,
                      "blocks": [{k: b[k] for k in
                                  ("pipeline", "partition", "results", "match")}
                                 for b in blocks]}, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
