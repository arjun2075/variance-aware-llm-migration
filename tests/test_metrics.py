"""Tests for output parsing and pairwise agreement metrics."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vaml.analysis.metrics import (  # noqa: E402
    cosine_similarity_text, exact_agreement, jaccard, mean_max_cosine,
    multiset_agreement, ordinal_agreement, semantic_set_overlap,
    sequence_agreement,
)
from vaml.analysis.parsing import (  # noqa: E402
    extract_json, p1_schema_valid, p1_structured, p2_schema_valid,
    p2_structured, verbatim_grounding,
)


# ---------------- parsing ----------------

def test_extract_plain_json():
    assert extract_json('{"a": 1}') == ({"a": 1}, None)


def test_extract_fenced_json():
    assert extract_json('```json\n{"a": 1}\n```')[0] == {"a": 1}


def test_extract_json_after_prose():
    assert extract_json('Sure, here:\n{"a": 1}')[0] == {"a": 1}


@pytest.mark.parametrize("bad,reason", [
    ("", "empty_response"),
    ("   ", "empty_response"),
    ("no json here", "no_json_object"),
    ('{"a": ', "truncated_json"),
    ("[1,2,3]", "no_json_object"),
])
def test_extract_failures_are_named_not_repaired(bad, reason):
    parsed, why = extract_json(bad)
    assert parsed is None and why == reason


def test_truncated_distinguished_from_invalid():
    """Truncation is an operational condition worth separating."""
    assert extract_json('{"a": {"b": 1}')[1] == "truncated_json"
    assert extract_json('{"a": 1,,}')[1] == "invalid_json"


# ---------------- P1 structure ----------------

def _p1_good():
    return {"ratings": {"technical_execution": "meets_expectations",
                        "delivery_consistency": "exceeds_expectations",
                        "collaboration": "meets_expectations",
                        "impact": "insufficient_data"},
            "strengths": ["s1"], "opportunities": ["o1"], "risks": ["r1"],
            "summary": "text"}


def test_p1_valid_schema():
    ok, v = p1_schema_valid(_p1_good(), {"recommendations": []})
    assert ok and not v


def test_p1_invalid_rating_flagged():
    d = _p1_good()
    d["ratings"]["impact"] = "amazing"
    ok, v = p1_schema_valid(d, {"recommendations": []})
    assert not ok and "rating_invalid:impact" in v


def test_p1_missing_stage_flagged():
    ok, v = p1_schema_valid(None, None)
    assert not ok and "stage3_missing" in v and "stage4_missing" in v


def test_p1_structured_nulls_invalid_rating_rather_than_guessing():
    d = _p1_good()
    d["ratings"]["impact"] = "???"
    s = p1_structured(d, None)
    assert s["ratings"]["impact"] is None
    assert s["ratings"]["technical_execution"] == "meets_expectations"


# ---------------- P2 structure ----------------

def test_p2_valid_label():
    ok, v = p2_schema_valid({"label": "Entailment", "cited_spans": []})
    assert ok and not v


def test_p2_label_outside_declared_set_flagged():
    ok, v = p2_schema_valid({"label": "Maybe", "cited_spans": []})
    assert not ok and "label_not_in_declared_set" in v


def test_p2_structured_extracts_span_text():
    s = p2_structured({"extracted_spans": [{"text": "x", "why_relevant": "y"}]},
                      {"label": "Entailment", "cited_spans": ["x"]}, None)
    assert s["extracted_spans"] == ["x"] and s["label"] == "Entailment"


# ---------------- verbatim grounding invariant ----------------

def test_grounding_exact_substring():
    assert verbatim_grounding(["quick brown"], "the quick brown fox") == (1, 1)


def test_grounding_normalises_whitespace_only():
    assert verbatim_grounding(["quick   brown"], "the quick brown fox") == (1, 1)


def test_grounding_rejects_hallucinated_span():
    assert verbatim_grounding(["purple elephant"], "the quick brown fox") == (0, 1)


def test_grounding_counts_partial():
    n, t = verbatim_grounding(["quick", "nonexistent"], "the quick brown fox")
    assert (n, t) == (1, 2)


def test_grounding_ignores_blank_spans():
    assert verbatim_grounding(["", "  "], "anything") == (0, 0)


# ---------------- agreement metrics ----------------

def test_ordinal_scale():
    assert ordinal_agreement("meets_expectations", "meets_expectations") == 1.0
    assert ordinal_agreement("below_expectations", "meets_expectations") == 0.5
    assert ordinal_agreement("below_expectations", "exceeds_expectations") == 0.0


def test_insufficient_data_is_nominal():
    """It agrees only with itself; it is not a point on the ordinal scale."""
    assert ordinal_agreement("insufficient_data", "insufficient_data") == 1.0
    assert ordinal_agreement("insufficient_data", "meets_expectations") == 0.0


def test_multiset_ignores_order_sequence_does_not():
    assert multiset_agreement(["a", "b"], ["b", "a"]) == 1.0
    assert sequence_agreement(["a", "b"], ["b", "a"]) == 0.0
    assert sequence_agreement(["a", "b"], ["a", "b"]) == 1.0


def test_multiset_respects_duplicates():
    assert multiset_agreement(["a", "a"], ["a"]) == 0.0


def test_jaccard_values():
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert jaccard(["a"], ["a"]) == 1.0
    assert jaccard([], []) == 1.0
    assert jaccard(["a"], []) == 0.0


def test_normalisation_is_case_and_whitespace_insensitive():
    assert jaccard(["  Alpha Beta "], ["alpha beta"]) == 1.0


@pytest.mark.parametrize("fn", [exact_agreement, jaccard, multiset_agreement,
                                sequence_agreement])
def test_none_input_is_ineligible_not_zero(fn):
    """Ineligible pairs must be None so they are EXCLUDED, not scored 0."""
    assert fn(None, ["a"]) is None
    assert fn(["a"], None) is None


# ---------------- semantic metrics ----------------

def _fake_embed(vocab):
    """Deterministic orthogonal-ish embeddings keyed by first token."""
    def embed(items):
        out = []
        for it in items:
            v = np.zeros(len(vocab))
            key = str(it).strip().lower().split()[0] if str(it).strip() else ""
            if key in vocab:
                v[vocab.index(key)] = 1.0
            out.append(v)
        return np.array(out)
    return embed


def test_semantic_overlap_matches_identical_items():
    e = _fake_embed(["alpha", "beta"])
    assert semantic_set_overlap(["alpha x"], ["alpha y"], e, 0.8) == 1.0


def test_semantic_overlap_rejects_dissimilar():
    e = _fake_embed(["alpha", "beta"])
    assert semantic_set_overlap(["alpha"], ["beta"], e, 0.8) == 0.0


def test_semantic_overlap_partial_matching():
    e = _fake_embed(["alpha", "beta", "gamma"])
    # one of two matches -> 1 / (2 + 2 - 1)
    v = semantic_set_overlap(["alpha", "beta"], ["alpha", "gamma"], e, 0.8)
    assert v == pytest.approx(1 / 3)


def test_semantic_matching_is_one_to_one():
    """Two identical items on one side must not both match a single item."""
    e = _fake_embed(["alpha"])
    v = semantic_set_overlap(["alpha", "alpha"], ["alpha"], e, 0.8)
    assert v == pytest.approx(1 / 2)   # 1 matched / (2 + 1 - 1)


def test_threshold_changes_result():
    e = _fake_embed(["alpha", "beta"])
    assert semantic_set_overlap(["alpha"], ["beta"], e, 0.0) == 1.0
    assert semantic_set_overlap(["alpha"], ["beta"], e, 0.8) == 0.0


def test_mean_max_cosine_is_threshold_free():
    e = _fake_embed(["alpha", "beta"])
    assert mean_max_cosine(["alpha"], ["alpha"], e) == pytest.approx(1.0)
    assert mean_max_cosine(["alpha"], ["beta"], e) == pytest.approx(0.0)


def test_cosine_text_identical_is_one():
    e = _fake_embed(["alpha"])
    assert cosine_similarity_text("alpha", "alpha", e) == pytest.approx(1.0)


def test_empty_both_sides_is_perfect_agreement():
    e = _fake_embed(["alpha"])
    assert semantic_set_overlap([], [], e) == 1.0
