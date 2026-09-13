"""Frozen model matrix for the confirmatory study.

PRIMARY EXECUTION ENVIRONMENT: a managed execution path.
All five conditions were confirmed AVAILABLE in the Experience's model catalog
before the freeze.

Policy: do not request additional model access, and do not substitute newer
aliases unless a selected model becomes unavailable before execution. If one
does, the substitution and its date are recorded in the run manifest and the
protocol is re-frozen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    INCUMBENT = "incumbent"
    CANDIDATE = "candidate"


@dataclass(frozen=True)
class ModelCondition:
    key: str
    model_id: str
    role: Role
    #: Upstream provider family, recorded for the cross-provider analysis.
    provider_family: str
    #: True when model_id is an immutable dated/versioned identifier.
    pinned: bool
    notes: str = ""
    availability: dict = field(default_factory=dict)


#: FROZEN. Availability confirmed in the model catalog.
MATRIX: list[ModelCondition] = [
    ModelCondition(
        key="incumbent_gpt4o",
        model_id="gpt-4o-2024-11-20",
        role=Role.INCUMBENT,
        provider_family="openai",
        pinned=True,
        notes=("Incumbent. Same condition as the historical pilot, giving "
               "direct continuity of the migration story."),
    ),
    ModelCondition(
        key="candidate_gpt54",
        model_id="gpt-5.4-2026-03-05",
        role=Role.CANDIDATE,
        provider_family="openai",
        pinned=True,
        notes="Same-provider successor: the within-provider migration case.",
    ),
    ModelCondition(
        key="candidate_gemini25pro",
        model_id="gemini-2.5-pro",
        role=Role.CANDIDATE,
        provider_family="google",
        pinned=False,
        notes=("Cross-provider candidate. NOT a dated snapshot: '2.5-pro' is a "
               "mutable alias, so the served weights may change during or "
               "between runs. This limitation is recorded rather than hidden; "
               "the canonical returned model id is logged per call so any "
               "mid-study change is detectable after the fact."),
    ),
    ModelCondition(
        key="candidate_nova_pro",
        model_id="amazon.nova-pro-v1-0",
        role=Role.CANDIDATE,
        provider_family="amazon",
        pinned=True,
        notes="Cross-provider candidate.",
    ),
    ModelCondition(
        key="candidate_llama4_maverick",
        model_id="meta.llama4-maverick-17b-instruct-v1-0",
        role=Role.CANDIDATE,
        provider_family="meta",
        pinned=True,
        notes="Open-weight cross-provider candidate.",
    ),
]

INCUMBENT_REPS = 8
CANDIDATE_REPS = 5


def incumbent(matrix: list[ModelCondition] = None) -> ModelCondition:
    m = matrix if matrix is not None else MATRIX
    incs = [x for x in m if x.role is Role.INCUMBENT]
    if len(incs) != 1:
        raise ValueError(f"expected exactly one incumbent, found {len(incs)}")
    return incs[0]


def candidates(matrix: list[ModelCondition] = None) -> list[ModelCondition]:
    m = matrix if matrix is not None else MATRIX
    return [x for x in m if x.role is Role.CANDIDATE]


def repetitions_for(cond: ModelCondition) -> int:
    return INCUMBENT_REPS if cond.role is Role.INCUMBENT else CANDIDATE_REPS


def unpinned(matrix: list[ModelCondition] = None) -> list[str]:
    """Conditions that are not immutable snapshots.

    Non-empty is acceptable but must be disclosed as a reproducibility
    limitation in the manuscript, not silently ignored.
    """
    m = matrix if matrix is not None else MATRIX
    return [x.model_id for x in m if not x.pinned]
