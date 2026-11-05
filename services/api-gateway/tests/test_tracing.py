import pytest
import sys
import os
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.tracing import (
    TraceContext,
    TraceSpan,
    inject_trace_headers,
    generate_trace_id,
    generate_span_id,
)
from gateway_app.main import app

def test_trace_context_root_and_child():
    root = TraceContext.create_root()
    assert len(root.trace_id) == 32
    assert len(root.span_id) == 16
    assert root.parent_span_id is None
    assert root.sampled is True

    # Test serialization
    tp = root.to_traceparent()
    assert tp.startswith("00-")
    assert tp.endswith("-01")

    # Test parsing
    parsed = TraceContext.from_traceparent(tp)
    assert parsed is not None
    assert parsed.trace_id == root.trace_id
    assert parsed.span_id == root.span_id
    assert parsed.sampled is True

    # Test child span derivation
    child = root.create_child()
    assert child.trace_id == root.trace_id
    assert child.parent_span_id == root.span_id
    assert child.span_id != root.span_id


def test_invalid_traceparent_handling():
    # All zeros prohibited by W3C specification
    invalid_zeros = "00-00000000000000000000000000000000-0000000000000000-01"
    assert TraceContext.from_traceparent(invalid_zeros) is None

    # Malformed length/dashes
    assert TraceContext.from_traceparent("invalid-trace-header") is None
    assert TraceContext.from_traceparent("") is None
    assert TraceContext.from_traceparent(None) is None


def test_trace_span_context_manager():
    ctx = TraceContext.create_root()
    with TraceSpan("test_compute_step", context=ctx) as span:
        span.set_tag("component", "inference_engine")
        span.set_tag("batch_size", 32)
        total = sum(i * i for i in range(1000))

    assert span.status == "OK"
    assert span.duration_ms is not None
    assert span.duration_ms >= 0.0
    assert span.tags["component"] == "inference_engine"
    assert span.tags["batch_size"] == 32


@pytest.mark.asyncio
async def test_api_gateway_tracing_middleware():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request without traceparent should generate a fresh traceparent
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "traceparent" in resp.headers
        assert "x-correlation-id" in resp.headers

        traceparent = resp.headers["traceparent"]
        correlation_id = resp.headers["x-correlation-id"]
        assert traceparent.startswith("00-")
        assert correlation_id in traceparent

        # Request WITH existing traceparent should propagate child span
        custom_trace_id = "11112222333344445555666677778888"
        custom_span_id = "aaaabbbbccccdddd"
        custom_header = f"00-{custom_trace_id}-{custom_span_id}-01"

        resp2 = await client.get("/health", headers={"traceparent": custom_header})
        assert resp2.status_code == 200
        resp2_tp = resp2.headers["traceparent"]
        assert custom_trace_id in resp2_tp
        assert resp2.headers["x-correlation-id"] == custom_trace_id
