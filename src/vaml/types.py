"""Core request/response types.

Identity discipline
-------------------
Every request carries a `RequestID` that is stable across batch submission,
provider response, retry, and analysis. Batch APIs return results ASYNCHRONOUSLY
AND OUT OF ORDER, so positional correspondence is never assumed anywhere in this
codebase: results are always rejoined by `custom_id`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ServingMode(str, Enum):
    """How a request was executed. Recorded on every record.

    Batch wall-clock time is NOT interactive latency; the two modes are analysed
    separately and never pooled for latency.
    """
    BATCH = "batch"
    SYNC = "sync"


class Pipeline(str, Enum):
    P1 = "p1_assessment"
    P2 = "p2_contractnli"


@dataclass(frozen=True)
class RequestID:
    """Stable identity for one pipeline call.

    Serialized to `custom_id` for batch APIs and used to rejoin responses.
    """
    pipeline: Pipeline
    task_id: str
    model_key: str
    repetition: int
    stage: str
    #: "primary" | "stress" | "sync_operational" | "batch_validation"
    partition: str = "primary"

    def custom_id(self) -> str:
        return (f"{self.pipeline.value}|{self.partition}|{self.task_id}"
                f"|{self.model_key}|r{self.repetition}|{self.stage}")

    @classmethod
    def parse(cls, custom_id: str) -> "RequestID":
        parts = custom_id.split("|")
        if len(parts) != 6:
            raise ValueError(f"malformed custom_id: {custom_id!r}")
        pipeline, partition, task_id, model_key, rep, stage = parts
        if not rep.startswith("r"):
            raise ValueError(f"malformed repetition in custom_id: {custom_id!r}")
        return cls(Pipeline(pipeline), task_id, model_key, int(rep[1:]), stage,
                   partition)


@dataclass
class CallRequest:
    rid: RequestID
    system_prompt: str
    user_prompt: str
    max_tokens: int
    #: Sampling params. None means provider default (the as-operated condition).
    temperature: float | None = None
    top_p: float | None = None

    def prompt_hash(self) -> str:
        return hashlib.sha256(
            (self.system_prompt + "\x00" + self.user_prompt).encode("utf-8")
        ).hexdigest()


@dataclass
class CallResult:
    rid: RequestID
    serving_mode: ServingMode
    #: Canonical model id the provider says it actually served.
    returned_model_id: str | None
    text: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    #: Wall-clock for SYNC only. None for BATCH — batch turnaround is not latency.
    latency_ms: float | None
    retry_count: int
    error: str | None = None
    submitted_at: str | None = None
    completed_at: str | None = None
    execution_order_index: int | None = None
    prompt_hash: str | None = None
    provider_request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.text is not None

    def to_json(self) -> str:
        d = asdict(self)
        d["rid"] = self.rid.custom_id()
        d["serving_mode"] = self.serving_mode.value
        return json.dumps(d, sort_keys=True)
