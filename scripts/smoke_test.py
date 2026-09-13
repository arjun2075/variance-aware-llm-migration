#!/usr/bin/env python3
"""ONE real call per model, to validate auth, response shape and provenance.

Cheap by construction: a trivial prompt with a small max_tokens. Its purpose is
to confirm the plumbing before committing to a multi-day serial grid, and in
particular to see what canonical model id each condition reports back.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _load_env import load_env  # noqa: E402

from vaml.adapters.provider_route_A import ProviderRouteAAdapter  # noqa: E402
from vaml.models import MATRIX  # noqa: E402
from vaml.orchestration.rate_limits import PacedExecutor, RateLimitPolicy  # noqa: E402
from vaml.types import CallRequest, Pipeline, RequestID  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="only this model_id")
    ap.add_argument("--out", type=Path, default=Path("results/smoke_test.json"))
    ap.add_argument("--env-file", default=os.environ.get("VAML_ENV_FILE"),
        help="credentials file; defaults to $VAML_ENV_FILE. Never printed.")
    args = ap.parse_args()
    if args.env_file and os.path.exists(args.env_file):
        load_env(args.env_file)

    adapter = ProviderRouteAAdapter()
    pacer = PacedExecutor(RateLimitPolicy())
    rows = []
    for m in MATRIX:
        if args.model and m.model_id != args.model:
            continue
        rid = RequestID(Pipeline.P1, "smoke", m.key, 1, "smoke", "smoke")
        req = CallRequest(
            rid=rid,
            system_prompt="Reply with valid JSON only.",
            user_prompt='Return exactly: {"ok": true}',
            max_tokens=64,
        )
        pacer.acquire(m.provider_family)
        try:
            res = adapter.call_sync(m.model_id, req)
        finally:
            pacer.release()
        row = {
            "requested_model_id": m.model_id,
            "provider_family": m.provider_family,
            "ok": res.ok,
            "returned_model_id": res.returned_model_id,
            "canonical_matches_requested": res.returned_model_id == m.model_id,
            "http_status": res.extra.get("http_status"),
            "latency_ms": round(res.latency_ms or 0, 1),
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "error": res.error,
            "error_body_preview": res.extra.get("error_body_preview"),
            "text_preview": (res.text or "")[:120],
        }
        rows.append(row)
        print(json.dumps(row, indent=2))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + "\n")
    n_ok = sum(1 for r in rows if r["ok"])
    print(f"\n{n_ok}/{len(rows)} models responded")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
