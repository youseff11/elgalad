"""
Client for the Bilingual Arabic-English Summarizer API (FastAPI model server).

Endpoints (from the Postman collection / OpenAPI spec):
    GET  /                          → service info
    GET  /health                    → {"status": "healthy", "model_loaded": true}
    POST /api/v1/summarize          → single document summary
    POST /api/v1/summarize/batch    → up to 32 documents
    POST /api/v1/detect-language    → ar / en / mixed + ratios
    POST /api/v1/clean-text         → normalized text
    POST /api/v1/tokenize           → statistics + sample subwords
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

from .models import AIConfig, ApiCallLog

# Parameter limits taken from the model's OpenAPI schema
PARAM_LIMITS = {
    "max_length": (16, 512, int),
    "min_length": (5, 128, int),
    "num_beams": (1, 8, int),
    "length_penalty": (0.1, 3.0, float),
    "repetition_penalty": (1.0, 2.0, float),
    "no_repeat_ngram_size": (0, 5, int),
}
BATCH_PARAMS = ("max_length", "min_length", "num_beams")
MAX_BATCH = 32


@dataclass
class APIResult:
    ok: bool
    status: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    latency_ms: float = 0.0


def clean_params(raw: dict | None, allowed=PARAM_LIMITS.keys(), defaults: dict | None = None) -> dict:
    """Coerce + clamp generation parameters to what the model accepts."""
    raw = raw or {}
    defaults = defaults or {}
    out = {}
    for key in allowed:
        lo, hi, cast = PARAM_LIMITS[key]
        val = raw.get(key, defaults.get(key))
        if val in (None, ""):
            continue
        try:
            val = cast(float(val)) if cast is int else cast(val)
        except (TypeError, ValueError):
            continue
        out[key] = min(hi, max(lo, val))
    if "min_length" in out and "max_length" in out and out["min_length"] >= out["max_length"]:
        out["min_length"] = max(5, min(out["max_length"] - 1, 128))
    return out


class SummarizerClient:
    def __init__(self, user=None):
        self.config = AIConfig.get()
        self.base_url = self.config.effective_url
        self.timeout = self.config.timeout or settings.AI_API_TIMEOUT
        self.user = user if (user is not None and getattr(user, "is_authenticated", False)) else None

    # ------------------------------------------------------------------ core
    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if settings.AI_API_KEY:
            h["X-API-Key"] = settings.AI_API_KEY
        return h

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: int | None = None,
                 log: bool = True) -> APIResult:
        url = f"{self.base_url}{path}"
        started = time.perf_counter()
        result = APIResult(ok=False)
        try:
            resp = requests.request(
                method, url, json=payload, headers=self._headers(), timeout=timeout or self.timeout
            )
            result.status = resp.status_code
            try:
                result.data = resp.json()
            except ValueError:
                result.data = {}
            if resp.ok:
                result.ok = True
            else:
                result.error = self._extract_error(result.data) or f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            result.error = "timeout"
        except requests.exceptions.ConnectionError:
            result.error = "connection"
        except requests.exceptions.RequestException as exc:  # pragma: no cover
            result.error = str(exc)[:300]
        result.latency_ms = round((time.perf_counter() - started) * 1000, 2)

        if log:
            try:
                ApiCallLog.objects.create(
                    user=self.user,
                    endpoint=path or "/",
                    method=method,
                    status_code=result.status,
                    ok=result.ok,
                    latency_ms=result.latency_ms,
                    error=result.error[:1000],
                )
            except Exception:  # logging must never break the request
                pass
        return result

    @staticmethod
    def _extract_error(data: dict) -> str:
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):  # FastAPI validation errors
            msgs = []
            for item in detail:
                loc = ".".join(str(p) for p in item.get("loc", [])[1:])
                msgs.append(f"{loc}: {item.get('msg')}" if loc else str(item.get("msg")))
            return "; ".join(msgs)
        return ""

    # ------------------------------------------------------------ endpoints
    # health/info are polled by the UI every minute → not written to the call log
    def info(self) -> APIResult:
        return self._request("GET", "/", timeout=15, log=False)

    def health(self) -> APIResult:
        return self._request("GET", "/health", timeout=15, log=False)

    def summarize(self, text: str, params: dict | None = None) -> APIResult:
        payload = {"text": text, **clean_params(params, defaults=self.config.default_params())}
        return self._request("POST", "/api/v1/summarize", payload)

    def summarize_batch(self, texts: list[str], params: dict | None = None) -> APIResult:
        payload = {
            "texts": texts[:MAX_BATCH],
            **clean_params(params, allowed=BATCH_PARAMS, defaults=self.config.default_params()),
        }
        return self._request("POST", "/api/v1/summarize/batch", payload, timeout=max(self.timeout, 300))

    def detect_language(self, text: str) -> APIResult:
        return self._request("POST", "/api/v1/detect-language", {"text": text})

    def clean_text(self, text: str, language: str | None = None) -> APIResult:
        payload = {"text": text}
        if language in ("ar", "en"):
            payload["language"] = language
        return self._request("POST", "/api/v1/clean-text", payload)

    def tokenize(self, text: str, language: str | None = None) -> APIResult:
        payload = {"text": text}
        if language in ("ar", "en"):
            payload["language"] = language
        return self._request("POST", "/api/v1/tokenize", payload)
