#!/usr/bin/env python3
"""QC check for Amendment 001: does max_tokens=8192 resolve the truncation?

Re-runs task/model/stage combinations ALREADY USED in the aborted QC run, so
the comparison is like-for-like. Reports ONLY operational properties --
finish_reason, parseability, token counts, provenance. It computes no
scientific metric, so this check cannot influence the analysis.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from _load_env import load_env  # noqa: E402
from build_p2_corpus import inference_view  # noqa: E402
from run_experiment import P1_STAGES, P2_STAGES, render, split_prompt  # noqa: E402
from vaml.adapters.shim import TransportAdapter  # noqa: E402
from vaml.models import MATRIX  # noqa: E402
from vaml.orchestration.rate_limits import PacedExecutor, RateLimitPolicy  # noqa: E402
from vaml.types import CallRequest, Pipeline, RequestID  # noqa: E402

MAX_TOKENS = 8192
GEMINI = "gemini-2.5-pro"


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
    ap.add_argument("--aborted", type=Path,
                    default=REPO / "results/aborted_qc_run/calls.jsonl")
    ap.add_argument("--out", type=Path,
                    default=REPO / "results/qc_ceiling_check.json")
    ap.add_argument("--per-model", type=int, default=4,
                    help="stage-1 combinations to re-run per model")
    args = ap.parse_args()

    envf = os.environ.get("VAML_ENV_FILE")
    if envf and os.path.exists(envf):
        load_env(envf)

    prior = [json.loads(l) for l in args.aborted.read_text().splitlines() if l.strip()]
    # pick previously-used (task, model) pairs, stage 1 only, gemini-heavy
    by_model: dict[str, list[dict]] = collections.defaultdict(list)
    for r in prior:
        rid = RequestID.parse(r["rid"])
        if rid.stage not in ("pr_signal", "extract_evidence"):
            continue
        by_model[r["returned_model_id"]].append(r)

    tasks_p1 = {json.loads(l)["task_id"]: json.loads(l)
                for l in (REPO / "corpora/pipeline1/p1_primary.jsonl").read_text().splitlines() if l.strip()}
    templates_p1 = {n: split_prompt((REPO / "prompts/pipeline1" / f).read_text())
                    for n, f in P1_STAGES}
    key_of = {m.model_id: m.key for m in MATRIX}
    fam_of = {m.model_id: m.provider_family for m in MATRIX}
    canon_to_req = {}
    cmap = json.loads((REPO / "protocol/canonical_model_map.json").read_text())["mapping"]
    for req, canon in cmap.items():
        canon_to_req[canon] = req

    adapter = TransportAdapter(env_file=envf)
    pacer = PacedExecutor(RateLimitPolicy())
    rows = []
    for canon, recs in sorted(by_model.items()):
        req_model = canon_to_req.get(canon)
        if req_model is None:
            continue
        n = args.per_model * (2 if canon == GEMINI else 1)
        for rec in recs[:n]:
            rid_old = RequestID.parse(rec["rid"])
            task = tasks_p1.get(rid_old.task_id)
            if task is None:
                continue
            rid = RequestID(Pipeline.P1, rid_old.task_id, key_of[req_model],
                            rid_old.repetition, "pr_signal", "qc_ceiling")
            sys_p, usr_p = render(Pipeline.P1, 0, templates_p1, P1_STAGES,
                                  task, {})
            creq = CallRequest(rid=rid, system_prompt=sys_p, user_prompt=usr_p,
                               max_tokens=MAX_TOKENS)
            pacer.acquire(fam_of[req_model])
            try:
                res = adapter.call_sync(req_model, creq)
            finally:
                pacer.release()
            ex = res.extra or {}
            rows.append({
                "requested_model": req_model,
                "returned_model": res.returned_model_id,
                "provenance_ok": not ex.get("canonical_model_mismatch"),
                "ok": res.ok,
                "finish_reason": ex.get("finish_reason"),
                "truncated": ex.get("finish_reason") == "length",
                "completion_tokens": res.completion_tokens,
                "text_chars": len(res.text or ""),
                "parses": parses(res.text),
                "prior_finish_reason": (rec.get("extra") or {}).get("finish_reason"),
                "prior_completion_tokens": rec.get("completion_tokens"),
            })
            print(f"  {req_model:42s} finish={ex.get('finish_reason'):7s} "
                  f"ctok={res.completion_tokens:<6} chars={len(res.text or ''):<6} "
                  f"parses={parses(res.text)}", flush=True)
    adapter.close()

    per = collections.defaultdict(lambda: {"n": 0, "trunc": 0, "parse": 0,
                                           "prov_ok": 0})
    for r in rows:
        d = per[r["requested_model"]]
        d["n"] += 1
        d["trunc"] += bool(r["truncated"])
        d["parse"] += bool(r["parses"])
        d["prov_ok"] += bool(r["provenance_ok"])

    gem = per.get(GEMINI, {"n": 0, "trunc": 0, "parse": 0})
    gem_trunc_rate = gem["trunc"] / gem["n"] if gem["n"] else 0.0
    others_trunc = sum(v["trunc"] for k, v in per.items() if k != GEMINI)
    all_parse = all(v["parse"] == v["n"] for v in per.values())
    all_prov = all(v["prov_ok"] == v["n"] for v in per.values())

    verdict = {
        "max_tokens": MAX_TOKENS,
        "gemini_truncation_rate_before": "15/28 (54%)",
        "gemini_truncation_rate_after": f"{gem['trunc']}/{gem['n']}",
        "gemini_material_truncation": gem_trunc_rate > 0.10,
        "other_models_truncated": others_trunc,
        "all_outputs_parse": all_parse,
        "all_provenance_correct": all_prov,
        "per_model": {k: dict(v) for k, v in per.items()},
        "rows": rows,
    }
    verdict["PASS"] = (not verdict["gemini_material_truncation"]
                       and others_trunc == 0 and all_parse and all_prov)
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print("\n" + json.dumps({k: verdict[k] for k in
                             ("max_tokens", "gemini_truncation_rate_before",
                              "gemini_truncation_rate_after",
                              "gemini_material_truncation",
                              "other_models_truncated", "all_outputs_parse",
                              "all_provenance_correct", "PASS")}, indent=2))
    return 0 if verdict["PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
