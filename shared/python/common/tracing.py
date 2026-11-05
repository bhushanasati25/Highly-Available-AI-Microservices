"""
W3C Distributed Tracing (TraceContext) Implementation
Complies with W3C Recommendation: https://www.w3.org/TR/trace-context/
Provides standardized distributed context propagation across microservices via 'traceparent' headers.
Format: {version:2hex}-{trace_id:32hex}-{parent_id/span_id:16hex}-{trace_flags:02hex}
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)

TRACEPARENT_REGEX = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$",
    re.IGNORECASE,
)

def generate_trace_id() -> str:
    """Generates a random 16-byte (32 lowercase hex) trace identifier."""
    return os.urandom(16).hex()

def generate_span_id() -> str:
    """Generates a random 8-byte (16 lowercase hex) span identifier."""
    return os.urandom(8).hex()

@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    sampled: bool = True
    version: str = "00"

    def to_traceparent(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"{self.version}-{self.trace_id.lower()}-{self.span_id.lower()}-{flags}"

    @classmethod
    def create_root(cls, sampled: bool = True) -> TraceContext:
        return cls(
            trace_id=generate_trace_id(),
            span_id=generate_span_id(),
            parent_span_id=None,
            sampled=sampled,
        )

    def create_child(self) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self.span_id,
            sampled=self.sampled,
            version=self.version,
        )

    @classmethod
    def from_traceparent(cls, header: Optional[str]) -> Optional[TraceContext]:
        if not header:
            return None
        match = TRACEPARENT_REGEX.match(header.strip())
        if not match:
            return None
        ver, trace_id, parent_id, flags_hex = match.groups()
        # Invalid trace-id check (all zeros is prohibited by W3C specification)
        if trace_id == "0" * 32 or parent_id == "0" * 16:
            return None

        flags = int(flags_hex, 16)
        sampled = bool(flags & 0x01)
        return cls(
            version=ver,
            trace_id=trace_id.lower(),
            span_id=parent_id.lower(),
            parent_span_id=None,
            sampled=sampled,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "traceparent": self.to_traceparent(),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "sampled": self.sampled,
        }

@dataclass
class TraceSpan:
    name: str
    context: TraceContext
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"

    def __enter__(self) -> TraceSpan:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 3)
        if exc_type is not None:
            self.status = "ERROR"
            self.tags["error.type"] = exc_type.__name__
            self.tags["error.message"] = str(exc_val)
        return False

    def set_tag(self, key: str, value: Any) -> TraceSpan:
        self.tags[key] = value
        return self

class W3CTracingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware ensuring all inbound and outbound HTTP requests
    carry a valid W3C traceparent header and X-Correlation-ID.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        inbound_traceparent = request.headers.get("traceparent")
        ctx = TraceContext.from_traceparent(inbound_traceparent)

        if ctx is None:
            ctx = TraceContext.create_root()
        else:
            # Fork into server span for this hop
            ctx = ctx.create_child()

        request.state.trace_context = ctx
        request.state.correlation_id = ctx.trace_id

        # Wrap downstream handler
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        # Inject standard response tracing headers
        response.headers["traceparent"] = ctx.to_traceparent()
        response.headers["X-Correlation-ID"] = ctx.trace_id
        response.headers["X-Server-Timing"] = f"total;dur={duration_ms}"

        return response

def inject_trace_headers(headers: Optional[Dict[str, str]] = None, ctx: Optional[TraceContext] = None) -> Dict[str, str]:
    """
    Utility to propagate W3C TraceContext into outgoing HTTP or gRPC client request headers.
    """
    out = dict(headers or {})
    if ctx is not None:
        child_ctx = ctx.create_child()
        out["traceparent"] = child_ctx.to_traceparent()
        out["X-Correlation-ID"] = child_ctx.trace_id
    return out
