"""Pairwise agreement metrics.

Every metric compares TWO runs of the same task and returns a value in [0,1],
or None when the pair is ineligible (either side unparseable or missing the
field). Eligibility is per-metric and explicit: the analysis must never assume
a uniform panel.
"""
from __future__ import annotations

import re
from typing import Sequence

import numpy as np

RATING_ORDER = ["below_expectations", "meets_expectations",
                "exceeds_expectations"]


def exact_agreement(a, b) -> float | None:
    if a is None or b is None:
        return None
    return 1.0 if a == b else 0.0


def ordinal_agreement(a: str | None, b: str | None) -> float | None:
    """1 - normalised ordinal distance. 'insufficient_data' is nominal, so it
    only agrees with itself."""
    if a is None or b is None:
        return None
    if a == b:
        return 1.0
    if a not in RATING_ORDER or b not in RATING_ORDER:
        return 0.0
    d = abs(RATING_ORDER.index(a) - RATING_ORDER.index(b))
    return 1.0 - d / (len(RATING_ORDER) - 1)


def multiset_agreement(a: Sequence[str] | None, b: Sequence[str] | None) -> float | None:
    """Exact match on the multiset of normalised items (order-insensitive)."""
    if a is None or b is None:
        return None
    import collections
    na = collections.Counter(_norm(x) for x in a)
    nb = collections.Counter(_norm(x) for x in b)
    return 1.0 if na == nb else 0.0


def sequence_agreement(a: Sequence[str] | None, b: Sequence[str] | None) -> float | None:
    """Exact match on the ordered sequence."""
    if a is None or b is None:
        return None
    return 1.0 if [_norm(x) for x in a] == [_norm(x) for x in b] else 0.0


def jaccard(a: Sequence[str] | None, b: Sequence[str] | None) -> float | None:
    if a is None or b is None:
        return None
    sa, sb = {_norm(x) for x in a}, {_norm(x) for x in b}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def semantic_set_overlap(a: Sequence[str] | None, b: Sequence[str] | None,
                         embed, threshold: float = 0.80) -> float | None:
    """Maximum-matching Jaccard over embedding cosine similarity.

    Two items match when cosine >= threshold; the score is |matched| /
    (|a| + |b| - |matched|), i.e. a Jaccard over the matching.
    """
    if a is None or b is None:
        return None
    la = [x for x in a if str(x).strip()]
    lb = [x for x in b if str(x).strip()]
    if not la and not lb:
        return 1.0
    if not la or not lb:
        return 0.0
    ea, eb = embed(list(la)), embed(list(lb))
    sim = _cosine_matrix(ea, eb)
    matched = _greedy_matching(sim, threshold)
    return matched / (len(la) + len(lb) - matched)


def cosine_similarity_text(a: str | None, b: str | None, embed) -> float | None:
    if not a or not b:
        return None
    ea, eb = embed([a])[0], embed([b])[0]
    d = float(np.linalg.norm(ea) * np.linalg.norm(eb))
    return float(np.dot(ea, eb) / d) if d else None


def mean_max_cosine(a: Sequence[str] | None, b: Sequence[str] | None,
                    embed) -> float | None:
    """Threshold-free aggregate, for the semantic-matching sensitivity analysis."""
    if a is None or b is None:
        return None
    la = [x for x in a if str(x).strip()]
    lb = [x for x in b if str(x).strip()]
    if not la and not lb:
        return 1.0
    if not la or not lb:
        return 0.0
    sim = _cosine_matrix(embed(list(la)), embed(list(lb)))
    return float((sim.max(axis=1).mean() + sim.max(axis=0).mean()) / 2)


# ---------------- helpers ----------------

def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _cosine_matrix(ea: np.ndarray, eb: np.ndarray) -> np.ndarray:
    ea = np.asarray(ea, dtype=float)
    eb = np.asarray(eb, dtype=float)
    na = np.linalg.norm(ea, axis=1, keepdims=True)
    nb = np.linalg.norm(eb, axis=1, keepdims=True)
    na[na == 0] = 1.0
    nb[nb == 0] = 1.0
    return (ea / na) @ (eb / nb).T


def _greedy_matching(sim: np.ndarray, threshold: float) -> int:
    """Greedy maximum matching on pairs at or above threshold."""
    pairs = [(sim[i, j], i, j)
             for i in range(sim.shape[0]) for j in range(sim.shape[1])
             if sim[i, j] >= threshold]
    pairs.sort(reverse=True)
    ua, ub, n = set(), set(), 0
    for _, i, j in pairs:
        if i in ua or j in ub:
            continue
        ua.add(i)
        ub.add(j)
        n += 1
    return n
