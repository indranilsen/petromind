"""Bounded HTTP transport for Meta Responses, with sanitized failures.

No arbitrary endpoint, redirects, environment proxies, implicit SDK retries,
request/response-body logging, or credentials in diagnostics.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx


class MetaAPIError(RuntimeError):
    """Only static reason codes and numeric statuses may escape the transport."""
    def __init__(self, code: str, status: int | None = None):
        self.code = code
        self.status = status
        super().__init__(code)


class MetaResponsesClient:
    ENDPOINT = "https://api.meta.ai/v1/responses"

    def __init__(self, *, max_requests=24, max_output_budget=40960, timeout=60,
                 max_retries=2, transport=None, sleep=time.sleep, clock=time.monotonic):
        key = os.environ.get("MODEL_API_KEY", "").strip()
        if not key or not key.isascii() or any(c.isspace() for c in key):
            raise MetaAPIError("missing_or_invalid_api_key")
        if (type(max_requests) is not int or not 1 <= max_requests <= 100
                or type(max_output_budget) is not int or max_output_budget < 16
                or type(max_retries) is not int or not 0 <= max_retries <= 3
                or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                or not math.isfinite(timeout) or not 0 < timeout <= 60):
            raise ValueError("Invalid transport limits")
        self._client = httpx.Client(headers={"Authorization": f"Bearer {key}"},
                                    timeout=timeout, transport=transport,
                                    follow_redirects=False, trust_env=False)
        self._max_requests, self._max_output_budget = max_requests, max_output_budget
        self._timeout, self._max_retries = timeout, max_retries
        self._sleep, self._clock = sleep, clock
        self.requests = 0
        self.reserved_output_tokens = 0

    def close(self):
        self._client.close()

    @staticmethod
    def _retry_delay(header, attempt):
        if header is None:
            return 2 ** attempt + random.random()
        try:
            delay = float(header)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                raise MetaAPIError("invalid_retry_after") from None
        if not math.isfinite(delay) or delay > 30:
            # Fail rather than retrying sooner than requested or blocking indefinitely.
            raise MetaAPIError("retry_after_exceeds_limit")
        return max(0, delay)

    def create(self, payload: dict, *, deadline: float, on_retry=None) -> dict:
        cap = payload.get("max_output_tokens")
        if type(cap) is not int or not 16 <= cap <= 8192:
            raise ValueError("Explicit output token limit required")
        for attempt in range(self._max_retries + 1):
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise MetaAPIError("run_deadline_exceeded")
            if self.requests >= self._max_requests:
                raise MetaAPIError("request_budget_exhausted")
            if self.reserved_output_tokens + cap > self._max_output_budget:
                raise MetaAPIError("output_reservation_exhausted")
            # Reserve even failed/ambiguous attempts: retries may incur API charges.
            self.requests += 1
            self.reserved_output_tokens += cap
            try:
                with self._client.stream("POST", self.ENDPOINT, json=payload,
                                         timeout=min(self._timeout, remaining)) as response:
                    status = response.status_code
                    retry_after = response.headers.get("Retry-After")
                    body = bytearray()
                    if status == 200:
                        for chunk in response.iter_bytes():
                            if len(body) + len(chunk) > 2_000_000:
                                raise MetaAPIError("api_response_too_large")
                            if self._clock() >= deadline:
                                raise MetaAPIError("run_deadline_exceeded")
                            body.extend(chunk)
            except httpx.TimeoutException:
                raise MetaAPIError("api_timeout") from None
            except httpx.HTTPError:
                raise MetaAPIError("api_connection_error") from None
            if status in {429, 500, 502, 503} and attempt < self._max_retries:
                delay = self._retry_delay(retry_after, attempt)
                if self._clock() + delay >= deadline:
                    raise MetaAPIError("run_deadline_exceeded")
                if on_retry:
                    on_retry({"status": status, "delay_seconds": round(delay, 3),
                              "request_attempt": self.requests})
                self._sleep(delay)
                continue
            if status != 200:
                # Never propagate a vendor body, error message, headers or exception repr.
                raise MetaAPIError("api_http_error", status)
            try:
                data = json.loads(body)
            except (ValueError, RecursionError):
                raise MetaAPIError("invalid_api_json") from None
            if not isinstance(data, dict):
                raise MetaAPIError("invalid_api_response")
            return data
        raise MetaAPIError("api_retry_exhausted")
