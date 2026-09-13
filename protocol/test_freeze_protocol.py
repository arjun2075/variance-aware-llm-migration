"""Tests for the protocol freeze/verify tool.

The freeze mechanism is the thing standing between a pre-registered protocol
and a silently-edited one, so it is tested for BOTH directions of error:
it must fail on real drift, and it must not fail on cosmetic churn.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
TOOL = HERE / "freeze_protocol.py"
REAL_SPEC = HERE / "protocol_spec.json"
REAL_PROTOCOL = HERE / "PROTOCOL.md"

sys.path.insert(0, str(HERE))
from freeze_protocol import canonical_json_hash, set_hash  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True)


@pytest.fixture
def frozen(tmp_path):
    """A frozen protocol in an isolated tmp dir."""
    spec = tmp_path / "spec.json"
    spec.write_text(REAL_SPEC.read_text())
    proto = tmp_path / "PROTOCOL.md"
    proto.write_text(REAL_PROTOCOL.read_text())
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "task_001.json").write_text('{"id": 1}')
    (corpus / "task_002.json").write_text('{"id": 2}')
    lock = tmp_path / "lock.json"
    r = run("freeze", "--protocol", str(proto), "--spec", str(spec),
            "--corpus", str(corpus), "--out", str(lock))
    assert r.returncode == 0, r.stderr
    return {"spec": spec, "proto": proto, "corpus": corpus, "lock": lock}


# ---------- canonical hashing ----------

def test_canonical_hash_is_key_order_insensitive():
    assert canonical_json_hash({"a": 1, "b": 2}) == canonical_json_hash({"b": 2, "a": 1})


def test_canonical_hash_is_value_sensitive():
    assert canonical_json_hash({"a": 1}) != canonical_json_hash({"a": 2})


def test_canonical_hash_distinguishes_types():
    assert canonical_json_hash({"a": 1}) != canonical_json_hash({"a": "1"})


def test_set_hash_is_order_independent():
    a = [{"path": "x", "sha256": "1"}, {"path": "y", "sha256": "2"}]
    assert set_hash(a) == set_hash(list(reversed(a)))


# ---------- freeze ----------

def test_freeze_rejects_spec_missing_required_sections(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"model_conditions": {}}))
    proto = tmp_path / "P.md"; proto.write_text("x")
    r = run("freeze", "--protocol", str(proto), "--spec", str(bad),
            "--out", str(tmp_path / "l.json"))
    assert r.returncode == 2
    assert "missing required sections" in r.stderr
    assert not (tmp_path / "l.json").exists()


def test_freeze_records_all_required_sections(frozen):
    lock = json.loads(frozen["lock"].read_text())
    for k in ["task_corpora", "public_research_prompts", "model_conditions",
              "repetition_counts", "pairwise_estimands", "primary_metrics",
              "property_tolerances", "tolerance_sensitivity_ranges",
              "semantic_matching", "retry_and_exclusion_rules",
              "randomization_procedure", "confirmatory_vs_exploratory"]:
        assert k in lock["protocol_spec"]["section_hashes"]


def test_freeze_hashes_corpus_files(frozen):
    lock = json.loads(frozen["lock"].read_text())
    assert len(lock["task_corpus_files"]) == 2
    assert lock["task_corpus_set_hash"]


# ---------- verify: must PASS ----------

def test_verify_passes_when_untouched(frozen):
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 0
    assert "PASS" in r.stdout


def test_verify_passes_on_cosmetic_reformat(frozen):
    """Reindenting the spec must NOT invalidate the freeze."""
    d = json.loads(frozen["spec"].read_text())
    frozen["spec"].write_text(json.dumps(d, indent=8))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 0, r.stdout
    assert "cosmetic reformat only" in r.stdout


def test_verify_passes_on_key_reorder(frozen):
    d = json.loads(frozen["spec"].read_text())
    frozen["spec"].write_text(json.dumps(dict(reversed(list(d.items()))), indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 0, r.stdout


# ---------- verify: must FAIL ----------

def test_verify_fails_on_changed_value(frozen):
    d = json.loads(frozen["spec"].read_text())
    d["repetition_counts"]["incumbent"] = 10
    frozen["spec"].write_text(json.dumps(d, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "spec section CHANGED: repetition_counts" in r.stdout


@pytest.mark.parametrize("section", [
    "property_tolerances", "pairwise_estimands", "semantic_matching",
    "randomization_procedure", "retry_and_exclusion_rules",
    "confirmatory_vs_exploratory",
])
def test_verify_fails_on_any_frozen_section_edit(frozen, section):
    d = json.loads(frozen["spec"].read_text())
    d[section]["__injected__"] = "drift"
    frozen["spec"].write_text(json.dumps(d, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert f"spec section CHANGED: {section}" in r.stdout


def test_verify_fails_on_added_section(frozen):
    d = json.loads(frozen["spec"].read_text())
    d["sneaky_new_section"] = {"added": "after freeze"}
    frozen["spec"].write_text(json.dumps(d, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "ADDED after freeze" in r.stdout


def test_verify_fails_on_removed_section(frozen):
    d = json.loads(frozen["spec"].read_text())
    del d["property_tolerances"]
    frozen["spec"].write_text(json.dumps(d, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "REMOVED" in r.stdout


def test_verify_fails_on_changed_protocol_document(frozen):
    frozen["proto"].write_text(REAL_PROTOCOL.read_text() + "\nsneaky edit\n")
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "protocol document CHANGED" in r.stdout


def test_verify_fails_on_changed_corpus_file(frozen):
    (frozen["corpus"] / "task_001.json").write_text('{"id": 999}')
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "task corpus file CHANGED" in r.stdout


def test_verify_fails_on_deleted_corpus_file(frozen):
    (frozen["corpus"] / "task_002.json").unlink()
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "task corpus file missing" in r.stdout


def test_verify_fails_on_tampered_lock_hash(frozen):
    lock = json.loads(frozen["lock"].read_text())
    lock["protocol_hash"] = "0" * 64
    frozen["lock"].write_text(json.dumps(lock, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "protocol_hash INCONSISTENT" in r.stdout


def test_verify_fails_when_lock_file_list_tampered(frozen):
    """Removing a file from the lock's list must break the set hash."""
    lock = json.loads(frozen["lock"].read_text())
    lock["task_corpus_files"] = lock["task_corpus_files"][:1]
    frozen["lock"].write_text(json.dumps(lock, indent=2))
    r = run("verify", "--lock", str(frozen["lock"]))
    assert r.returncode == 1
    assert "set hash INCONSISTENT" in r.stdout
