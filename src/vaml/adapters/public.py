"""Direct-provider adapters for the frozen replication subset.

Credentials come from the environment only and are never logged or persisted.
Each adapter records the canonical model id the provider returns, so a
mismatch against the frozen replication map is detectable.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request

from ..types import CallRequest, CallResult, ServingMode
from .base import BatchHandle, ProviderAdapter


def _post(url: str, payload: dict, headers: dict, timeout: float = 300.0):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


class _Base(ProviderAdapter):
    def supports_batch(self, model_id): return False
    def submit_batch(self, m, r): raise NotImplementedError
    def poll_batch(self, h): raise NotImplementedError
    def fetch_batch(self, h): raise NotImplementedError

    def _result(self, req, *, text, returned, ptok, ctok, latency, err,
                submitted, status=None, finish=None, rid_extra=None):
        return CallResult(
            rid=req.rid, serving_mode=ServingMode.SYNC, returned_model_id=returned,
            text=text, prompt_tokens=ptok, completion_tokens=ctok,
            latency_ms=latency, retry_count=0, error=err,
            submitted_at=submitted,
            completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            prompt_hash=req.prompt_hash(),
            extra={"http_status": status, "finish_reason": finish,
                   **(rid_extra or {})})


class OpenAIAdapter(_Base):
    name = "openai"

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.environ["OPENAI_API_KEY"]

    def call_sync(self, model_id: str, req: CallRequest) -> CallResult:
        submitted = dt.datetime.now(dt.timezone.utc).isoformat()
        t0 = time.monotonic()
        payload = {"model": model_id,
                   "messages": [{"role": "system", "content": req.system_prompt},
                                {"role": "user", "content": req.user_prompt}],
                   "max_completion_tokens": req.max_tokens}
        try:
            st, raw = _post("https://api.openai.com/v1/chat/completions", payload,
                            {"Content-Type": "application/json",
                             "Authorization": f"Bearer {self._key}"})
            d = json.loads(raw)
            ch = (d.get("choices") or [{}])[0]
            u = d.get("usage") or {}
            return self._result(req, text=(ch.get("message") or {}).get("content"),
                                returned=d.get("model"),
                                ptok=u.get("prompt_tokens"), ctok=u.get("completion_tokens"),
                                latency=(time.monotonic()-t0)*1000, err=None,
                                submitted=submitted, status=st,
                                finish=ch.get("finish_reason"))
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            return self._result(req, text=None, returned=None, ptok=None, ctok=None,
                                latency=(time.monotonic()-t0)*1000,
                                err=f"http_status_{e.code}", submitted=submitted,
                                status=e.code, rid_extra={"error_body": body})
        except Exception as e:  # noqa: BLE001
            return self._result(req, text=None, returned=None, ptok=None, ctok=None,
                                latency=(time.monotonic()-t0)*1000,
                                err=type(e).__name__, submitted=submitted)


class GeminiAdapter(_Base):
    """Direct Gemini API (API-key auth), per protocol note 001."""
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.environ["GEMINI_API_KEY"]

    def call_sync(self, model_id: str, req: CallRequest) -> CallResult:
        submitted = dt.datetime.now(dt.timezone.utc).isoformat()
        t0 = time.monotonic()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model_id}:generateContent?key={self._key}")
        payload = {
            "systemInstruction": {"parts": [{"text": req.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": req.user_prompt}]}],
            "generationConfig": {"maxOutputTokens": req.max_tokens},
        }
        try:
            st, raw = _post(url, payload, {"Content-Type": "application/json"})
            d = json.loads(raw)
            cands = d.get("candidates") or [{}]
            parts = ((cands[0].get("content") or {}).get("parts") or [])
            text = "".join(p.get("text", "") for p in parts) or None
            um = d.get("usageMetadata") or {}
            return self._result(req, text=text,
                                returned=d.get("modelVersion") or model_id,
                                ptok=um.get("promptTokenCount"),
                                ctok=um.get("candidatesTokenCount"),
                                latency=(time.monotonic()-t0)*1000, err=None,
                                submitted=submitted, status=st,
                                finish=cands[0].get("finishReason"))
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            return self._result(req, text=None, returned=None, ptok=None, ctok=None,
                                latency=(time.monotonic()-t0)*1000,
                                err=f"http_status_{e.code}", submitted=submitted,
                                status=e.code, rid_extra={"error_body": body})
        except Exception as e:  # noqa: BLE001
            return self._result(req, text=None, returned=None, ptok=None, ctok=None,
                                latency=(time.monotonic()-t0)*1000,
                                err=type(e).__name__, submitted=submitted)
