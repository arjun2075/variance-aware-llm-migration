"""Execution pacing for the managed execution path.

TECHNICAL BLOCKER (documented, not designed around)
---------------------------------------------------
The brief asks for "controlled asynchronous concurrency: independent tasks may
run concurrently". **the managed execution path does not permit concurrent calls.** Calls must
be serialized with a minimum inter-call interval, and Bedrock-backed models add
their own 429 throttling on top of the managed execution path constraint.

Evidence:
  * confirmed operationally on 2026-05-09, when a 3s inter-call sleep still
    produced Bedrock 429s ("Too many connections, please wait before trying
    again") on rapid decoupled calls;
  * the production client's retry path treats 429 specially with a 15s/30s/60s
    exponential backoff plus jitter, which is the backoff profile of a service
    that throttles aggressively.

So `max_concurrency` defaults to 1. The knob exists, and the scheduler is
written so that raising it is a one-line change IF a limit is later confirmed
in writing — but the frozen configuration is serial. Setting it above 1 without
that confirmation risks 429 storms that would contaminate the latency and retry
metrics the study is trying to measure.

This does NOT change the study design; it changes only the execution schedule.
Randomized interleaving is preserved: the order is a seeded permutation, just
walked one call at a time.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class RateLimitPolicy:
    """Frozen pacing configuration.

    All values are conservative because the true published limits are UNKNOWN.
    `limits_source` records how each number was arrived at so a reader can tell
    a measured limit from a defensive default.
    """

    #: managed execution path does not allow concurrent calls. Do not raise without written
    #: confirmation of a supported concurrency limit.
    max_concurrency: int = 1

    #: Minimum seconds between the start of consecutive calls.
    min_interval_s: float = 2.0

    #: Bedrock-backed models throttle harder at short call latencies.
    bedrock_min_interval_s: float = 15.0

    #: 429 backoff schedule (seconds), matching the production client.
    backoff_schedule_s: tuple[float, ...] = (15.0, 30.0, 60.0)
    max_retries: int = 3
    jitter_s: float = 5.0

    #: Unknown. No RPM/TPM figure is published to the Experience, so the
    #: scheduler paces on inter-call interval instead of a token budget.
    rpm_limit: int | None = None
    tpm_limit: int | None = None

    limits_source: dict = field(default_factory=lambda: {
        "max_concurrency": (
            "OBSERVED CONSTRAINT: managed execution path does not allow concurrent calls "
            "(confirmed 2026-05-09). Not a published figure."),
        "min_interval_s": (
            "OBSERVED CONSTRAINT: >=2s between calls (confirmed 2026-05-09)."),
        "bedrock_min_interval_s": (
            "OBSERVED CONSTRAINT: 15s comfortable for Bedrock-backed models; "
            "3s produced 429s in practice."),
        "backoff_schedule_s": (
            "Mirrors the production client's 429 path: 15s/30s/60s with jitter."),
        "rpm_limit": "UNKNOWN - no published per-Experience RPM figure obtained.",
        "tpm_limit": "UNKNOWN - no published per-Experience TPM figure obtained.",
    })

    def interval_for(self, provider_family: str) -> float:
        """Bedrock-backed families get the longer interval."""
        return (self.bedrock_min_interval_s
                if provider_family in {"amazon", "meta"}
                else self.min_interval_s)


class PacedExecutor:
    """Serializes calls and enforces the minimum inter-call interval.

    Thread-safe so the concurrency knob is meaningful if it is ever raised, but
    defaults to strictly serial execution.
    """

    def __init__(self, policy: RateLimitPolicy, sleep=time.sleep,
                 clock=time.monotonic):
        self.policy = policy
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(policy.max_concurrency)
        self._last_start: float | None = None
        self.calls_made = 0
        self.total_wait_s = 0.0

    def acquire(self, provider_family: str) -> float:
        """Block until the next call may start. Returns seconds waited."""
        self._sem.acquire()
        with self._lock:
            need = self.policy.interval_for(provider_family)
            waited = 0.0
            if self._last_start is not None:
                elapsed = self._clock() - self._last_start
                if elapsed < need:
                    waited = need - elapsed
                    self._sleep(waited)
            self._last_start = self._clock()
            self.calls_made += 1
            self.total_wait_s += waited
            return waited

    def release(self) -> None:
        self._sem.release()

    def backoff_for_attempt(self, attempt: int, rng=None) -> float:
        """429 backoff for a 1-indexed attempt, with jitter."""
        sched = self.policy.backoff_schedule_s
        base = sched[min(attempt, len(sched)) - 1]
        if rng is not None and self.policy.jitter_s:
            base += rng.uniform(0, self.policy.jitter_s)
        return base


def estimate_wall_clock_s(
    calls_by_family: dict[str, int], policy: RateLimitPolicy,
    mean_latency_by_family: dict[str, float],
) -> dict:
    """Serial wall-clock estimate: sum over calls of max(interval, latency).

    With concurrency pinned to 1, throughput is governed by whichever is larger
    for each call: the pacing interval or the call's own latency.
    """
    total = 0.0
    per_family = {}
    for fam, n in calls_by_family.items():
        interval = policy.interval_for(fam)
        latency = mean_latency_by_family.get(fam, 0.0)
        secs = n * max(interval, latency)
        per_family[fam] = {
            "calls": n,
            "interval_s": interval,
            "mean_latency_s": latency,
            "binding_constraint": "latency" if latency > interval else "pacing",
            "seconds": round(secs, 1),
            "hours": round(secs / 3600, 2),
        }
        total += secs
    return {
        "per_family": per_family,
        "total_seconds": round(total, 1),
        "total_hours": round(total / 3600, 2),
        "total_days": round(total / 86400, 2),
        "assumes": "strictly serial execution (max_concurrency=1)",
    }
