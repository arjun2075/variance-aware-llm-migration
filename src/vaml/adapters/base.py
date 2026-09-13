"""Provider adapter interface.

Credentials are read from the environment (or the provider's standard
credential chain) at call time. No adapter accepts, stores, logs, or prints a
key.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

from ..types import CallRequest, CallResult


@dataclass(frozen=True)
class BatchHandle:
    """Reference to a submitted provider batch job."""
    provider: str
    batch_id: str
    n_requests: int
    submitted_at: str


class ProviderAdapter(abc.ABC):
    """One public vendor API.

    Implementations must:
      * read credentials from the environment / standard chain only;
      * never log or echo credential material;
      * preserve `custom_id` end to end and rejoin by it, never by position;
      * record the canonical returned model id when the provider supplies it.
    """

    name: str

    @abc.abstractmethod
    def supports_batch(self, model_id: str) -> bool:
        """Whether a batch/async path exists for this exact model."""

    @abc.abstractmethod
    def call_sync(self, model_id: str, req: CallRequest) -> CallResult:
        """One synchronous call. Used for the operational-latency subset."""

    @abc.abstractmethod
    def submit_batch(self, model_id: str, reqs: list[CallRequest]) -> BatchHandle:
        """Submit a batch job. Returns immediately."""

    @abc.abstractmethod
    def poll_batch(self, handle: BatchHandle) -> str:
        """Provider status string: 'pending' | 'completed' | 'failed'."""

    @abc.abstractmethod
    def fetch_batch(self, handle: BatchHandle) -> list[CallResult]:
        """Fetch completed results, rejoined by custom_id.

        Results may arrive out of order and may be incomplete; callers must not
        assume 1:1 positional correspondence with the submitted list.
        """


class MockAdapter(ProviderAdapter):
    """Zero-cost adapter for the mandatory dry run.

    Exercises the full orchestration path — wave sequencing, identity
    preservation, batch submit/poll/fetch, persistence — while making no network
    call and incurring no spend. Deliberately returns results in SHUFFLED order
    so any code that assumes positional correspondence fails loudly in the dry
    run rather than silently mis-joining a paid run.
    """

    name = "mock"

    def __init__(self, seed: int = 20260803, fail_rate: float = 0.0):
        import random
        self._rng = random.Random(seed)
        self._fail_rate = fail_rate
        self._batches: dict[str, list[CallRequest]] = {}
        self._counter = 0

    def supports_batch(self, model_id: str) -> bool:
        return True

    def _synth(self, model_id: str, req: CallRequest,
               mode) -> CallResult:
        from ..types import ServingMode
        self._counter += 1
        failed = self._rng.random() < self._fail_rate
        return CallResult(
            rid=req.rid,
            serving_mode=mode,
            returned_model_id=model_id,
            text=None if failed else f'{{"mock": true, "stage": "{req.rid.stage}"}}',
            prompt_tokens=None if failed else len(req.user_prompt) // 4,
            completion_tokens=None if failed else 128,
            latency_ms=(self._rng.uniform(500, 3000)
                        if mode is ServingMode.SYNC and not failed else None),
            retry_count=0,
            error="mock injected failure" if failed else None,
            prompt_hash=req.prompt_hash(),
            provider_request_id=f"mock-{self._counter}",
        )

    def call_sync(self, model_id: str, req: CallRequest) -> CallResult:
        from ..types import ServingMode
        return self._synth(model_id, req, ServingMode.SYNC)

    def submit_batch(self, model_id: str, reqs: list[CallRequest]) -> BatchHandle:
        import datetime as dt
        bid = f"mock_batch_{len(self._batches) + 1}"
        self._batches[bid] = list(reqs)
        self._batch_model = getattr(self, "_batch_model", {})
        self._batch_model[bid] = model_id
        return BatchHandle("mock", bid, len(reqs),
                           dt.datetime.now(dt.timezone.utc).isoformat())

    def poll_batch(self, handle: BatchHandle) -> str:
        return "completed"

    def fetch_batch(self, handle: BatchHandle) -> list[CallResult]:
        from ..types import ServingMode
        reqs = list(self._batches[handle.batch_id])
        model_id = self._batch_model[handle.batch_id]
        out = [self._synth(model_id, r, ServingMode.BATCH) for r in reqs]
        self._rng.shuffle(out)  # batch results are unordered — prove we cope
        return out
