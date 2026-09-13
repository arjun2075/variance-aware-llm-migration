"""Tests for the launch-readiness gate and the ContractNLI validator.

The gate's job is to refuse a paid run on placeholder data. A gate that can be
satisfied by synthetic fixtures is worse than no gate, so the central test is
that it fails on them.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "scripts/validate_contractnli.py"
GATE = REPO / "scripts/check_launch_readiness.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


def _cnli(n_docs=150, n_hyps=17, label_cycle=("Entailment", "Contradiction",
                                              "NotMentioned")):
    docs = []
    for d in range(n_docs):
        clauses = [f"Section {i}: term {i} of agreement {d}." for i in range(1, 8)]
        text = "\n\n".join(clauses)
        spans, pos = [], 0
        for c in clauses:
            spans.append([pos, pos + len(c)])
            pos += len(c) + 2
        anns = {}
        for h in range(n_hyps):
            choice = label_cycle[(d + h) % len(label_cycle)]
            anns[f"nda-{h}"] = {"choice": choice,
                                "spans": [h % len(spans)] if choice != "NotMentioned" else []}
        docs.append({"id": f"doc_{d}", "text": text, "spans": spans,
                     "annotation_sets": [{"annotations": anns}]})
    return {"documents": docs,
            "labels": {f"nda-{h}": {"hypothesis": f"H{h}"} for h in range(n_hyps)}}


# ---------------- validator ----------------

def test_validator_passes_on_wellformed(tmp_path):
    src = tmp_path / "train.json"
    src.write_text(json.dumps(_cnli()))
    r = run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    assert r.returncode == 0, r.stdout
    assert json.loads((tmp_path / "v.json").read_text())["status"] == "PASS"


def test_validator_reports_missing_file_actionably(tmp_path):
    r = run(VALIDATOR, "--source", str(tmp_path / "nope.json"))
    assert r.returncode == 2
    assert "does not exist" in r.stdout
    assert "contract-nli" in r.stdout       # points at the official source


def test_validator_rejects_truncated_download(tmp_path):
    src = tmp_path / "t.json"
    src.write_text(json.dumps(_cnli())[:4000])
    assert run(VALIDATOR, "--source", str(src)).returncode == 2


def test_validator_rejects_unrecognised_structure(tmp_path):
    src = tmp_path / "w.json"
    src.write_text(json.dumps({"rows": [1, 2, 3]}))
    assert run(VALIDATOR, "--source", str(src)).returncode == 2


def test_validator_rejects_too_few_documents(tmp_path):
    """Fewer than 80 distinct documents cannot yield 60 primary + 20 stress."""
    src = tmp_path / "s.json"
    src.write_text(json.dumps(_cnli(n_docs=20)))
    r = run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    assert r.returncode == 1
    assert any("documents" in f for f in
               json.loads((tmp_path / "v.json").read_text())["hard_failures"])


def test_validator_rejects_invalid_label(tmp_path):
    data = _cnli()
    data["documents"][0]["annotation_sets"][0]["annotations"]["nda-0"]["choice"] = "Maybe"
    src = tmp_path / "b.json"
    src.write_text(json.dumps(data))
    r = run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    assert r.returncode == 1
    assert any("invalid label" in f for f in
               json.loads((tmp_path / "v.json").read_text())["hard_failures"])


def test_validator_rejects_out_of_range_span_index(tmp_path):
    data = _cnli()
    data["documents"][0]["annotation_sets"][0]["annotations"]["nda-0"]["spans"] = [9999]
    src = tmp_path / "o.json"
    src.write_text(json.dumps(data))
    r = run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    assert r.returncode == 1
    assert any("out of range" in f for f in
               json.loads((tmp_path / "v.json").read_text())["hard_failures"])


def test_validator_flags_wrong_hypothesis_count_softly(tmp_path):
    """A different hypothesis count is suspicious but not fatal."""
    src = tmp_path / "h.json"
    src.write_text(json.dumps(_cnli(n_hyps=5)))
    r = run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    rep = json.loads((tmp_path / "v.json").read_text())
    assert r.returncode == 0
    assert any("hypothes" in s for s in rep["soft_observations"])


def test_validator_records_source_hash(tmp_path):
    src = tmp_path / "train.json"
    src.write_text(json.dumps(_cnli()))
    run(VALIDATOR, "--source", str(src), "--out", str(tmp_path / "v.json"))
    assert len(json.loads((tmp_path / "v.json").read_text())["sha256"]) == 64


# ---------------- launch gate ----------------

def test_gate_blocks_on_synthetic_fixtures():
    """The single most important test here."""
    r = run(GATE)
    report = json.loads((REPO / "corpora/pipeline2/p2_corpus_report.json").read_text())
    if report.get("is_synthetic_fixture"):
        assert r.returncode != 0
        assert "SYNTHETIC FIXTURES" in r.stdout
        assert "NOT READY" in r.stdout


def test_gate_allows_synthetic_only_behind_explicit_flag():
    r = run(GATE, "--allow-synthetic")
    assert "SYNTHETIC" in r.stdout or "real ContractNLI" in r.stdout


def test_gate_checks_every_required_item():
    r = run(GATE, "--allow-synthetic")
    for item in ("p1_corpus", "p2_corpus", "contractnli_validation",
                 "protocol_lock", "git_clean", "mock_dry_run"):
        assert item in r.stdout


# ---------------- raw data hygiene ----------------

def test_raw_dataset_files_are_gitignored():
    for name in ("train.json", "dev.json", "test.json", "archive.zip"):
        rc = subprocess.run(
            ["git", "-C", str(REPO), "check-ignore",
             f"data/raw/contractnli/{name}"], capture_output=True)
        assert rc.returncode == 0, f"{name} would be committed"


def test_raw_data_readme_is_not_ignored():
    """The instructions must survive; only the data is excluded."""
    rc = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "data/raw/contractnli/README.md"],
        capture_output=True)
    assert rc.returncode != 0


def test_no_contractnli_source_file_is_tracked():
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                             capture_output=True, text=True).stdout.split("\n")
    assert not [f for f in tracked if f.startswith("data/raw/")
                and not f.endswith("README.md")]
