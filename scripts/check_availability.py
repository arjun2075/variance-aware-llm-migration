#!/usr/bin/env python3
"""Probe PUBLIC vendor APIs for model availability and batch support.

Writes a dated availability manifest consumed by the freeze. Uses list/metadata
endpoints where possible, which are free; any endpoint that would incur token
charges is gated behind --allow-paid-probe and off by default.

Credentials come from the environment only. Nothing is printed that could echo
a key.

    python scripts/check_availability.py --out protocol/availability_manifest.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vaml.models import INTENDED_MATRIX, Provider  # noqa: E402


def check_openai(models: list) -> dict:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return {"status": "SKIPPED", "reason": "OPENAI_API_KEY not set"}
    try:
        from openai import OpenAI
    except ImportError:
        return {"status": "SKIPPED", "reason": "openai package not installed"}
    client = OpenAI(api_key=key)
    try:
        available = {m.id for m in client.models.list()}
    except Exception as e:  # noqa: BLE001
        return {"status": "ERROR", "reason": type(e).__name__}
    return {
        "status": "OK",
        "n_models_visible": len(available),
        "checked": {m.model_id: (m.model_id in available)
                    for m in models if m.model_id},
        "candidate_snapshots_visible": sorted(
            x for x in available if x.startswith(("gpt-4o", "gpt-4.1", "gpt-5"))
        )[:60],
    }


def check_anthropic(models: list) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"status": "SKIPPED", "reason": "ANTHROPIC_API_KEY not set"}
    try:
        import anthropic
    except ImportError:
        return {"status": "SKIPPED", "reason": "anthropic package not installed"}
    client = anthropic.Anthropic(api_key=key)
    try:
        available = {m.id for m in client.models.list(limit=100).data}
    except Exception as e:  # noqa: BLE001
        return {"status": "ERROR", "reason": type(e).__name__}
    return {
        "status": "OK",
        "n_models_visible": len(available),
        "checked": {m.model_id: (m.model_id in available)
                    for m in models if m.model_id},
        "visible": sorted(available)[:60],
    }


def check_bedrock(models: list) -> dict:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return {"status": "SKIPPED", "reason": "boto3 not installed"}
    region = os.environ.get("AWS_REGION", "us-east-1")
    try:
        client = boto3.client("bedrock", region_name=region)
        listed = client.list_foundation_models()["modelSummaries"]
    except (BotoCoreError, ClientError, Exception) as e:  # noqa: BLE001
        return {"status": "ERROR", "reason": type(e).__name__, "region": region}
    ids = {m["modelId"] for m in listed}
    return {
        "status": "OK",
        "region": region,
        "n_models_visible": len(ids),
        "checked": {m.model_id: (m.model_id in ids) for m in models if m.model_id},
        "nova_or_llama_visible": sorted(
            x for x in ids if x.startswith(("amazon.nova", "meta.llama"))
        )[:40],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allow-paid-probe", action="store_true",
                    help="permit probes that consume tokens (default: off)")
    args = ap.parse_args()

    by_provider: dict[Provider, list] = {}
    for m in INTENDED_MATRIX:
        by_provider.setdefault(m.provider, []).append(m)

    manifest = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "paid_probes_enabled": args.allow_paid_probe,
        "note": (
            "Availability determined from provider list/metadata endpoints. "
            "Visibility in a list endpoint is necessary but not sufficient for "
            "batch support; confirm batch separately per model before freezing."
        ),
        "providers": {
            "openai": check_openai(by_provider.get(Provider.OPENAI, [])),
            "anthropic": check_anthropic(by_provider.get(Provider.ANTHROPIC, [])),
            "bedrock": check_bedrock(by_provider.get(Provider.BEDROCK, [])),
        },
        "intended_matrix": [
            {"key": m.key, "provider": m.provider.value, "model_id": m.model_id,
             "role": m.role.value, "pinned": m.pinned, "docs_url": m.docs_url}
            for m in INTENDED_MATRIX
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"wrote": str(args.out),
                      "providers": {k: v["status"]
                                    for k, v in manifest["providers"].items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
