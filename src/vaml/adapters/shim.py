"""Adapter that executes calls through an external transport-helper binary.

WHY A TRANSPORT HELPER
----------------------
The confirmatory runs were executed through a managed execution path whose
transport layer rejected a plain HTTPS client (Python, curl) while an
equivalent Go client authenticated successfully with identical credentials and
headers. Rather than reimplement that transport-layer identity, the harness
delegated transport to a small Go binary built against the working client.

NOT INCLUDED IN THE PUBLIC ARTIFACT. The binary is specific to that managed
execution path and is omitted here; this module is retained only to document
how the recorded calls were transported. Re-executing model calls requires
supplying your own provider endpoint and credentials (see README).

EXECUTION INFRASTRUCTURE ONLY. No experimental condition changes: corpora,
prompts, model ids, repetition counts, estimands, tolerances, retry/exclusion
rules and the randomized schedule are untouched. Every analysis in this
artifact reads the persisted ledger and makes no model calls.

The helper speaks line-delimited JSON over stdin/stdout, one response per
request, in order. Its own debug output goes to stderr. Credentials never
cross this boundary: the helper loads them itself and never echoes them.
"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from ..types import CallRequest, CallResult, ServingMode
from .base import BatchHandle, ProviderAdapter

REPO = Path(__file__).resolve().parents[3]
DEFAULT_BINARY = REPO / "bin" / "transport-helper"
CANONICAL_MAP_PATH = REPO / "protocol" / "canonical_model_map.json"


def load_canonical_map(path: Path = CANONICAL_MAP_PATH) -> dict[str, str]:
    return json.loads(path.read_text())["mapping"]


class TransportAdapter(ProviderAdapter):
    name = "llm_execution_service_shim"

    def __init__(self, binary: Path | None = None,
                 canonical_map: dict[str, str] | None = None,
                 env_file: str | None = None):
        self.binary = Path(binary or DEFAULT_BINARY)
        if not self.binary.exists():
            raise FileNotFoundError(
                f"transport-helper binary not found at {self.binary}; build it with "
                f"`go build -o {self.binary} ./cmd/transport-helper` inside the "
                f"service module")
        self.canonical_map = (canonical_map if canonical_map is not None
                              else load_canonical_map())
        self.env_file = env_file
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        env = None
        if self.env_file:
            import os
            env = dict(os.environ, VAML_ENV_FILE=self.env_file)
        self._proc = subprocess.Popen(
            [str(self.binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        return self._proc

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                self._proc.kill()
            self._proc = None

    # ------------------------------------------------------------------
    def supports_batch(self, model_id: str) -> bool:
        """No batch API on this service."""
        return False

    def submit_batch(self, model_id, reqs):  # pragma: no cover
        raise NotImplementedError("no batch API; frozen plan uses paced sync")

    def poll_batch(self, handle: BatchHandle):  # pragma: no cover
        raise NotImplementedError

    def fetch_batch(self, handle: BatchHandle):  # pragma: no cover
        raise NotImplementedError

    # ------------------------------------------------------------------
    def restart(self) -> None:
        """Kill and relaunch the transport helper subprocess.

        the transport helper holds per-process auth/connection state. After a long
        suspend (laptop sleep or restart) that state can go stale while the
        process is still alive, producing 403s on every model at once. A
        fresh process re-fetches the IAM ticket and recovers.
        """
        self.close()
        self._ensure()

    def call_sync(self, model_id: str, req: CallRequest) -> CallResult:
        payload = {
            "custom_id": req.rid.custom_id(),
            "model": model_id,
            "system_prompt": req.system_prompt,
            "user_prompt": req.user_prompt,
            "max_tokens": req.max_tokens,
        }
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        if req.top_p is not None:
            payload["top_p"] = req.top_p

        with self._lock:
            proc = self._ensure()
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        if not line:
            raise RuntimeError("transport helper produced no response (process died?)")
        d = json.loads(line)

        if d.get("custom_id") != req.rid.custom_id():
            raise RuntimeError(
                f"transport helper response id mismatch: sent {req.rid.custom_id()!r}, "
                f"got {d.get('custom_id')!r}")

        expected = self.canonical_map.get(model_id)
        returned = d.get("returned_model_id")
        mismatch = bool(returned) and expected is not None and returned != expected

        return CallResult(
            rid=req.rid,
            serving_mode=ServingMode.SYNC,
            returned_model_id=returned,
            text=d.get("text") if d.get("ok") else None,
            prompt_tokens=d.get("prompt_tokens"),
            completion_tokens=d.get("completion_tokens"),
            latency_ms=d.get("latency_ms"),
            retry_count=d.get("retry_count", 0),
            error=d.get("error"),
            submitted_at=d.get("submitted_at"),
            completed_at=d.get("completed_at"),
            prompt_hash=req.prompt_hash(),
            provider_request_id=d.get("provider_request_id"),
            extra={
                "requested_model_id": model_id,
                "expected_canonical_model_id": expected,
                "canonical_model_mismatch": mismatch,
                "finish_reason": d.get("finish_reason"),
                "error_category": d.get("error_category"),
                "http_status": d.get("http_status"),
                "total_tokens": d.get("total_tokens"),
            },
        )
