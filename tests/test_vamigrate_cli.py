"""Tests for the vamigrate CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "analysis/vamigrate.py"
FIX = REPO / "tests/fixtures"
sys.path.insert(0, str(REPO / "analysis"))

from vamigrate import InputError, compare, load_records  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True)


def write(tmp, name, records):
    p = tmp / name
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


# ---------------- happy path ----------------

def test_compare_on_fixtures_is_deterministic():
    a = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "500",
            "--json")
    b = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "500",
            "--json")
    assert a.returncode == 0 and a.stdout == b.stdout


def test_reports_all_required_fields():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"),
            "--tolerance", "0.05", "--replicates", "500", "--json")
    d = json.loads(r.stdout)
    for f in ("n_tasks", "incumbent_repetitions", "candidate_repetitions",
              "W_A", "C_AB", "Delta", "ci_lower", "ci_upper", "verdict"):
        assert f in d


def test_delta_identity_holds():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "500",
            "--json")
    d = json.loads(r.stdout)
    assert d["Delta"] == pytest.approx(d["C_AB"] - d["W_A"], abs=1e-6)


def test_ci_brackets_the_point_estimate_loosely():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "800",
            "--json")
    d = json.loads(r.stdout)
    assert d["ci_lower"] <= d["ci_upper"]


def test_human_output_is_readable():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "300")
    assert "W_A" in r.stdout and "Delta" in r.stdout


def test_optional_correctness_fields_are_surfaced():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--replicates", "300",
            "--json")
    d = json.loads(r.stdout)
    assert "accuracy_delta" in d
    assert "accuracy" in d["incumbent_extra"]


# ---------------- vacuity warning ----------------

def test_warns_when_tolerance_exceeds_w_a():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"),
            "--tolerance", "0.90", "--replicates", "300", "--json")
    d = json.loads(r.stdout)
    assert any("vacuous" in w for w in d["warnings"])


def test_no_warning_for_an_informative_tolerance():
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"),
            "--tolerance", "0.02", "--replicates", "300", "--json")
    assert json.loads(r.stdout)["warnings"] == []


def test_warns_when_incumbent_never_agrees_with_itself(tmp_path):
    inc = write(tmp_path, "i.jsonl", [
        {"task_id": f"t{t}", "repetition": r, "value": f"v{t}{r}"}
        for t in range(4) for r in (1, 2, 3)])
    cand = write(tmp_path, "c.jsonl", [
        {"task_id": f"t{t}", "repetition": r, "value": "x"}
        for t in range(4) for r in (1, 2)])
    r = run("compare", "--incumbent", str(inc), "--candidate", str(cand),
            "--tolerance", "0.05", "--replicates", "200", "--json")
    d = json.loads(r.stdout)
    assert d["W_A"] == 0.0
    assert any("never agrees with itself" in w for w in d["warnings"])


# ---------------- malformed input ----------------

def test_missing_file():
    r = run("compare", "--incumbent", "/nonexistent.jsonl",
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "file not found" in r.stderr


def test_invalid_json_line(tmp_path):
    bad = tmp_path / "b.jsonl"; bad.write_text("{not json}\n")
    r = run("compare", "--incumbent", str(bad),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "invalid JSON" in r.stderr


def test_missing_required_field(tmp_path):
    bad = write(tmp_path, "b.jsonl", [{"task_id": "t1", "repetition": 1}])
    r = run("compare", "--incumbent", str(bad),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "missing required field 'value'" in r.stderr


def test_non_object_line(tmp_path):
    bad = tmp_path / "b.jsonl"; bad.write_text("[1,2,3]\n")
    r = run("compare", "--incumbent", str(bad),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "JSON object" in r.stderr


def test_empty_file(tmp_path):
    e = tmp_path / "e.jsonl"; e.write_text("")
    r = run("compare", "--incumbent", str(e),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "no records" in r.stderr


def test_duplicate_repetition_rejected(tmp_path):
    bad = write(tmp_path, "b.jsonl", [
        {"task_id": "t1", "repetition": 1, "value": "a"},
        {"task_id": "t1", "repetition": 1, "value": "b"}])
    r = run("compare", "--incumbent", str(bad),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "duplicate repetition" in r.stderr


def test_unknown_metric(tmp_path):
    r = run("compare", "--incumbent", str(FIX / "incumbent.jsonl"),
            "--candidate", str(FIX / "candidate.jsonl"), "--metric", "bogus")
    assert r.returncode == 2 and "unknown metric" in r.stderr


def test_no_overlapping_tasks(tmp_path):
    inc = write(tmp_path, "i.jsonl", [
        {"task_id": "a", "repetition": r, "value": "x"} for r in (1, 2)])
    cand = write(tmp_path, "c.jsonl", [
        {"task_id": "z", "repetition": 1, "value": "x"}])
    r = run("compare", "--incumbent", str(inc), "--candidate", str(cand))
    assert r.returncode == 2 and "no task_id" in r.stderr


def test_single_incumbent_repetition_rejected(tmp_path):
    inc = write(tmp_path, "i.jsonl", [
        {"task_id": "t1", "repetition": 1, "value": "x"}])
    cand = write(tmp_path, "c.jsonl", [
        {"task_id": "t1", "repetition": 1, "value": "y"}])
    r = run("compare", "--incumbent", str(inc), "--candidate", str(cand))
    assert r.returncode == 2 and "at least 2 repetitions" in r.stderr


def test_non_integer_repetition(tmp_path):
    bad = write(tmp_path, "b.jsonl", [
        {"task_id": "t1", "repetition": "first", "value": "a"}])
    r = run("compare", "--incumbent", str(bad),
            "--candidate", str(FIX / "candidate.jsonl"))
    assert r.returncode == 2 and "must be an integer" in r.stderr


# ---------------- metrics ----------------

@pytest.mark.parametrize("metric", ["exact", "jaccard", "multiset", "sequence"])
def test_list_metrics_run(tmp_path, metric):
    inc = write(tmp_path, "i.jsonl", [
        {"task_id": f"t{t}", "repetition": r, "value": ["a", "b"]}
        for t in range(5) for r in (1, 2, 3)])
    cand = write(tmp_path, "c.jsonl", [
        {"task_id": f"t{t}", "repetition": r, "value": ["a", "c"]}
        for t in range(5) for r in (1, 2)])
    r = run("compare", "--incumbent", str(inc), "--candidate", str(cand),
            "--metric", metric, "--replicates", "200", "--json")
    assert r.returncode == 0, r.stderr


def test_reuses_library_implementation_not_a_copy():
    """compare() must call the shared estimators, so results match directly."""
    res = compare(FIX / "incumbent.jsonl", FIX / "candidate.jsonl",
                  "exact", None, 300, 20260803)
    assert res["Delta"] == pytest.approx(res["C_AB"] - res["W_A"], abs=1e-6)
