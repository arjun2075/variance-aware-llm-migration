"""Corpus integrity tests.

The gold-leakage tests are the most important in the repository: if a gold label
or gold evidence span reaches a model at inference time, every correctness
result in the study is invalid and the failure would be invisible in the output.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from build_p2_corpus import LABELS, inference_view  # noqa: E402

P1 = REPO / "corpora/pipeline1"
P2 = REPO / "corpora/pipeline2"


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ---------------- Pipeline 1 ----------------

@pytest.mark.parametrize("name,n", [("primary", 60), ("stress", 20)])
def test_p1_counts(name, n):
    assert len(load(P1 / f"p1_{name}.jsonl")) == n


def test_p1_task_ids_unique_across_partitions():
    ids = [c["task_id"] for c in load(P1 / "p1_primary.jsonl")]
    ids += [c["task_id"] for c in load(P1 / "p1_stress.jsonl")]
    assert len(ids) == len(set(ids))


def test_p1_all_cases_marked_synthetic():
    for name in ("primary", "stress"):
        assert all(c["synthetic"] for c in load(P1 / f"p1_{name}.jsonl"))


def test_p1_axis_signatures_are_distinct():
    """Guards against 60 paraphrases of one template."""
    for name in ("primary", "stress"):
        cases = load(P1 / f"p1_{name}.jsonl")
        sigs = {tuple(sorted(c["axes"].items())) for c in cases}
        assert len(sigs) == len(cases)


def test_p1_primary_and_stress_do_not_overlap():
    a = {tuple(sorted(c["axes"].items())) for c in load(P1 / "p1_primary.jsonl")}
    b = {tuple(sorted(c["axes"].items())) for c in load(P1 / "p1_stress.jsonl")}
    assert not (a & b)


def test_p1_stress_is_actually_harder():
    """The stress set must occupy harder regions, or it is not a stress set."""
    def hard_frac(name):
        cs = load(P1 / f"p1_{name}.jsonl")
        return sum(c["axes"]["difficulty"] in ("hard", "very_hard")
                   for c in cs) / len(cs)
    assert hard_frac("stress") > hard_frac("primary") + 0.30


def test_p1_covers_all_archetypes():
    cases = load(P1 / "p1_primary.jsonl")
    assert len({c["axes"]["archetype"] for c in cases}) == 8


def test_p1_has_no_real_identifiers():
    """No email, URL, or company string anywhere in the corpus."""
    import re
    for name in ("primary", "stress"):
        blob = (P1 / f"p1_{name}.jsonl").read_text()
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", blob)
        assert not re.search(r"https?://", blob)
        assert "the managed execution path" not in blob.lower()


# ---------------- Pipeline 2 ----------------

@pytest.mark.parametrize("name,n", [("primary", 60), ("stress", 20)])
def test_p2_counts(name, n):
    assert len(load(P2 / f"p2_{name}.jsonl")) == n


def test_p2_sampled_at_document_level():
    """One instance per document: doc x hypothesis pairs are NOT independent."""
    for name in ("primary", "stress"):
        cases = load(P2 / f"p2_{name}.jsonl")
        assert len({c["document_id"] for c in cases}) == len(cases)


def test_p2_primary_and_stress_share_no_document():
    a = {c["document_id"] for c in load(P2 / "p2_primary.jsonl")}
    b = {c["document_id"] for c in load(P2 / "p2_stress.jsonl")}
    assert not (a & b)


def test_p2_gold_labels_present_for_scoring():
    for name in ("primary", "stress"):
        for c in load(P2 / f"p2_{name}.jsonl"):
            assert c["gold_label"] in LABELS
            assert "gold_spans" in c


def test_p2_label_distribution_is_balanced():
    cases = load(P2 / "p2_primary.jsonl")
    counts = {l: sum(c["gold_label"] == l for c in cases) for l in LABELS}
    assert max(counts.values()) - min(counts.values()) <= 2, counts


# ---------------- GOLD LEAKAGE (critical) ----------------

@pytest.mark.parametrize("name", ["primary", "stress"])
def test_inference_view_strips_every_gold_field(name):
    for c in load(P2 / f"p2_{name}.jsonl"):
        view = inference_view(c)
        for forbidden in ("gold_label", "gold_spans", "gold_span_indices"):
            assert forbidden not in view, f"{forbidden} leaked for {c['task_id']}"


@pytest.mark.parametrize("name", ["primary", "stress"])
def test_no_gold_label_string_reachable_in_inference_view(name):
    """The label must not be inferable from any serialized value.

    `label_options` legitimately lists all three labels; the test asserts the
    view does not single out the gold one.
    """
    for c in load(P2 / f"p2_{name}.jsonl"):
        view = inference_view(c)
        opts = view.pop("label_options")
        assert sorted(opts) == sorted(LABELS)      # all options, unordered
        blob = json.dumps(view)
        assert c["gold_label"] not in blob, c["task_id"]


#: Annotation-style markers. Deliberately NOT a bare "gold" substring: real
#: contracts contain surnames like "Goldberg" and words like "Goldman", and a
#: naive substring match fires on them. We look for markup patterns instead.
ANNOTATION_MARKERS = [
    re.compile(r"\[\s*(?:GOLD|ANSWER|LABEL|EVIDENCE)\b", re.I),
    re.compile(r"<<+\s*\w"),
    re.compile(r"\*\*\s*(?:GOLD|EVIDENCE|ANSWER|LABEL)\b", re.I),
    re.compile(r"(?:^|[^A-Za-z])(?:GOLD|CORRECT)[_\s-](?:LABEL|ANSWER|SPAN)", re.I),
    re.compile(r"<(?:/?)(?:gold|evidence|answer|label)\b", re.I),
]


@pytest.mark.parametrize("name", ["primary", "stress"])
def test_gold_spans_not_marked_up_in_document_text(name):
    """Gold spans must appear as ordinary contract text, never annotated.

    Matches annotation MARKUP, not the bare word "gold" -- real NDAs contain
    names like "Goldberg", and an earlier substring check false-positived on a
    signature block.
    """
    for c in load(P2 / f"p2_{name}.jsonl"):
        text = inference_view(c)["document_text"]
        for pat in ANNOTATION_MARKERS:
            m = pat.search(text)
            assert not m, (
                f"annotation markup {m.group(0)!r} in {c['task_id']}")


def test_inference_view_keys_are_exactly_the_allowlist():
    """A new field added to the corpus must not silently reach the model."""
    allowed = {"task_id", "document_id", "document_text", "hypothesis",
               "label_options"}
    for c in load(P2 / "p2_primary.jsonl"):
        assert set(inference_view(c)) == allowed


def test_gold_spans_are_substrings_of_the_document():
    """Scoring the verbatim-grounding invariant requires this to hold."""
    for c in load(P2 / "p2_primary.jsonl"):
        for span in c["gold_spans"]:
            assert span in c["document_text"], c["task_id"]


# ---------------- freeze safety ----------------

def test_synthetic_fixture_flag_is_visible_in_report():
    """The confirmatory freeze must be able to refuse synthetic fixtures."""
    report = json.loads((P2 / "p2_corpus_report.json").read_text())
    assert "is_synthetic_fixture" in report


def test_corpora_are_deterministic_for_a_given_seed(tmp_path):
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/build_p1_corpus.py"),
         "--out-dir", str(tmp_path), "--seed", "20260803"],
        capture_output=True, text=True, check=True)
    rebuilt = json.loads(r.stdout)
    original = json.loads((P1 / "p1_corpus_report.json").read_text())
    assert rebuilt["primary"]["sha256"] == original["primary"]["sha256"]
    assert rebuilt["stress"]["sha256"] == original["stress"]["sha256"]
