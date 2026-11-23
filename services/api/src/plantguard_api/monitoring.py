"""Low-cardinality metrics, request identifiers and structured access logs."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from threading import Lock
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("plantguard.access")


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status_counts: Counter[int] = Counter()
        self._duration_sum = 0.0

    def observe(self, status_code: int, duration_seconds: float) -> None:
        with self._lock:
            self._status_counts[status_code] += 1
            self._duration_sum += duration_seconds

    def render(self) -> str:
        with self._lock:
            counts = dict(self._status_counts)
            duration = self._duration_sum
        lines = [
            "# HELP plantguard_http_requests_total Completed HTTP requests.",
            "# TYPE plantguard_http_requests_total counter",
        ]
        lines.extend(
            f'plantguard_http_requests_total{{status="{status}"}} {count}'
            for status, count in sorted(counts.items())
        )
        lines.extend(
            (
                "# HELP plantguard_http_request_duration_seconds_sum Total request duration.",
                "# TYPE plantguard_http_request_duration_seconds_sum counter",
                f"plantguard_http_request_duration_seconds_sum {duration:.6f}",
            )
        )
        return "\n".join(lines) + "\n"


request_metrics = RequestMetrics()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started
            request_metrics.observe(500, duration)
            logger.exception(
                json.dumps(
                    {
                        "event": "request_failed",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration * 1000, 2),
                    },
                    ensure_ascii=False,
                )
            )
            raise
        duration = time.perf_counter() - started
        request_metrics.observe(response.status_code, duration)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        logger.info(
            json.dumps(
                {
                    "event": "request_completed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
                ensure_ascii=False,
            )
        )
        return response
