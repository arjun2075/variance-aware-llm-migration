"""Parse model outputs into the structured fields the metrics consume.

Deliberately tolerant of the wrappers models add around JSON (fenced code
blocks, leading prose) but NOT of malformed content: a response that cannot be
parsed is recorded as a parse failure, which is itself a reported metric, never
silently repaired into something scoreable.
"""
from __future__ import annotations

import json
import re
from typing import Any

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str | None) -> tuple[dict | None, str | None]:
    """Return (parsed, failure_reason). Exactly one is non-None."""
    if not text or not text.strip():
        return None, "empty_response"
    s = text.strip()
    m = FENCE.search(s)
    if m:
        s = m.group(1).strip()
    # tolerate leading prose before the first object
    if not s.startswith("{"):
        i = s.find("{")
        if i == -1:
            return None, "no_json_object"
        s = s[i:]
    try:
        d = json.loads(s)
    except json.JSONDecodeError as e:
        # a truncated response is a distinct operational condition
        return None, ("truncated_json" if "Expecting" in str(e)
                      and s.count("{") > s.count("}") else "invalid_json")
    if not isinstance(d, dict):
        return None, "json_not_object"
    return d, None


# ---------------- Pipeline 1 ----------------

P1_RATING_FIELDS = ["technical_execution", "delivery_consistency",
                    "collaboration", "impact"]
P1_RATINGS = {"below_expectations", "meets_expectations",
              "exceeds_expectations", "insufficient_data"}
P1_LIST_FIELDS = ["strengths", "opportunities", "risks"]


def p1_structured(stage3: dict | None, stage4: dict | None) -> dict:
    """Structured fields for P1 metrics. Missing/invalid -> None, not a guess."""
    out: dict[str, Any] = {"ratings": {}, "lists": {}, "summary": None,
                           "recommendations": []}
    if stage3:
        r = stage3.get("ratings") or {}
        for f in P1_RATING_FIELDS:
            v = r.get(f)
            out["ratings"][f] = v if v in P1_RATINGS else None
        for f in P1_LIST_FIELDS:
            v = stage3.get(f)
            out["lists"][f] = [str(x) for x in v] if isinstance(v, list) else None
        s = stage3.get("summary")
        out["summary"] = s if isinstance(s, str) and s.strip() else None
    if stage4:
        recs = stage4.get("recommendations")
        if isinstance(recs, list):
            out["recommendations"] = [
                str(x.get("action")) if isinstance(x, dict) else str(x)
                for x in recs]
    return out


def p1_schema_valid(stage3: dict | None, stage4: dict | None) -> tuple[bool, list[str]]:
    v: list[str] = []
    if stage3 is None:
        v.append("stage3_missing")
    else:
        r = stage3.get("ratings")
        if not isinstance(r, dict):
            v.append("ratings_missing")
        else:
            for f in P1_RATING_FIELDS:
                if r.get(f) not in P1_RATINGS:
                    v.append(f"rating_invalid:{f}")
        for f in P1_LIST_FIELDS:
            if not isinstance(stage3.get(f), list):
                v.append(f"list_missing:{f}")
        if not isinstance(stage3.get("summary"), str):
            v.append("summary_missing")
    if stage4 is None:
        v.append("stage4_missing")
    elif not isinstance(stage4.get("recommendations"), list):
        v.append("recommendations_missing")
    return (not v), v


# ---------------- Pipeline 2 ----------------

P2_LABELS = {"Entailment", "Contradiction", "NotMentioned"}


def p2_structured(stage1: dict | None, stage3: dict | None,
                  stage4: dict | None) -> dict:
    out: dict[str, Any] = {"label": None, "cited_spans": [],
                           "extracted_spans": [], "confidence": None,
                           "verified": None}
    if stage1:
        sp = stage1.get("extracted_spans")
        if isinstance(sp, list):
            out["extracted_spans"] = [
                str(x.get("text")) if isinstance(x, dict) else str(x)
                for x in sp]
    if stage3:
        lab = stage3.get("label")
        out["label"] = lab if lab in P2_LABELS else None
        cs = stage3.get("cited_spans")
        if isinstance(cs, list):
            out["cited_spans"] = [str(x) for x in cs]
        out["confidence"] = stage3.get("confidence")
    if stage4:
        out["verified"] = stage4.get("internally_consistent")
    return out


def p2_schema_valid(stage3: dict | None) -> tuple[bool, list[str]]:
    v: list[str] = []
    if stage3 is None:
        v.append("stage3_missing")
        return False, v
    if stage3.get("label") not in P2_LABELS:
        v.append("label_not_in_declared_set")
    if not isinstance(stage3.get("cited_spans"), list):
        v.append("cited_spans_missing")
    return (not v), v


def verbatim_grounding(cited: list[str], document: str) -> tuple[int, int]:
    """(n_grounded, n_cited). A span must appear verbatim after whitespace
    normalisation. Deterministic invariant; needs no gold annotation."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()
    doc = norm(document)
    n = sum(1 for c in cited if c.strip() and norm(c) in doc)
    return n, len([c for c in cited if c.strip()])
