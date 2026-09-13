"""Guard: the aborted QC run must never enter the confirmatory dataset.

82 calls were made at max_tokens=2048 before Amendment 001. They are preserved
for auditability but are scientifically void. This guard makes accidental
merging a test failure rather than a silent contamination of the results.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ABORTED = REPO / "results/aborted_qc_run"
CONFIRMATORY = REPO / "results/run"

ABORTED_LEDGER_SHA256 = (
    "01c641f8db8735df5c0da9cb697b49e43cfea0028cd4b91ff159a97a135cccf4")


@pytest.mark.skipif(not ABORTED.exists(), reason="no aborted run present")
def test_aborted_run_is_clearly_labelled():
    notice = json.loads((ABORTED / "ABORTED_RUN_NOTICE.json").read_text())
    assert "EXCLUDED FROM ALL CONFIRMATORY ANALYSIS" in notice["status"]
    assert notice["max_tokens_used"] == 2048


@pytest.mark.skipif(not ABORTED.exists(), reason="no aborted run present")
def test_aborted_ledger_is_unmodified():
    """Its hash is recorded in the amendment; drift means it was edited."""
    digest = hashlib.sha256((ABORTED / "calls.jsonl").read_bytes()).hexdigest()
    assert digest == ABORTED_LEDGER_SHA256


@pytest.mark.skipif(not CONFIRMATORY.exists(), reason="confirmatory run not started")
def test_no_aborted_calls_in_confirmatory_ledger():
    """The decisive check: no aborted record may appear in the real ledger."""
    conf = CONFIRMATORY / "calls.jsonl"
    if not conf.exists():
        pytest.skip("confirmatory ledger not created yet")
    aborted_ids = {
        json.loads(l)["rid"] + "|" + (json.loads(l)["submitted_at"] or "")
        for l in (ABORTED / "calls.jsonl").read_text().splitlines() if l.strip()
    } if ABORTED.exists() else set()
    conf_ids = {
        json.loads(l)["rid"] + "|" + (json.loads(l)["submitted_at"] or "")
        for l in conf.read_text().splitlines() if l.strip()
    }
    overlap = aborted_ids & conf_ids
    assert not overlap, f"{len(overlap)} aborted calls present in the confirmatory ledger"


@pytest.mark.skipif(not CONFIRMATORY.exists(), reason="confirmatory run not started")
def test_confirmatory_calls_all_use_amended_ceiling():
    """Every confirmatory completion must be consistent with max_tokens=8192.

    A completion at exactly the old 2048 ceiling with finish_reason=length is
    the signature of a pre-amendment record.
    """
    conf = CONFIRMATORY / "calls.jsonl"
    if not conf.exists():
        pytest.skip("confirmatory ledger not created yet")
    suspects = []
    for line in conf.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        ctok = r.get("completion_tokens") or 0
        fr = (r.get("extra") or {}).get("finish_reason")
        if fr == "length" and 2040 <= ctok <= 2048:
            suspects.append(r["rid"])
    assert not suspects, (
        f"{len(suspects)} confirmatory calls truncated at the OLD 2048 ceiling: "
        f"{suspects[:3]}")


def test_runner_uses_uniform_amended_ceiling():
    src = (REPO / "scripts/run_experiment.py").read_text()
    assert "MAX_TOKENS = 8192" in src
    assert "MAX_TOKENS = 2048" not in src


def test_no_per_model_token_ceiling():
    """Per-model ceilings were explicitly rejected: they would make the serving
    configuration non-uniform across the comparison."""
    src = (REPO / "scripts/run_experiment.py").read_text()
    for bad in ("max_tokens_by_model", "MAX_TOKENS_BY_MODEL",
                "per_model_max_tokens"):
        assert bad not in src


def test_amendment_document_exists_and_records_both_values():
    doc = (REPO / "protocol/AMENDMENT_001_max_tokens.md").read_text()
    assert "2048" in doc and "8192" in doc
    assert "82 / 20,160" in doc
    assert ABORTED_LEDGER_SHA256 in doc
