"""
Unit tests for the FastMCP middleware (rate-limit + logging).

The middleware is tested without spinning up a full MCP transport: we
invoke the hooks directly with a fake ``MiddlewareContext`` and a no-op
``call_next``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mt5_mcp.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    build_default_middleware,
)


class FakeRequest:
    """Minimal stand-in for a starlette Request carrying the ASGI scope."""

    def __init__(self, client_host: str | None) -> None:
        self.scope: dict = {}
        if client_host is not None:
            self.scope["client"] = (client_host, 12345)


class FakeContext:
    """Minimal MiddlewareContext surface used by our hooks."""

    def __init__(
        self,
        method: str = "tools/call",
        *,
        client_host: str | None = "10.0.0.1",
        transport: str | None = "streamable-http",
    ) -> None:
        self.method = method
        self.transport = transport
        self.request = FakeRequest(client_host)


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_quota_exceeded():
    mw = RateLimitMiddleware(max_requests_per_minute=3)
    call_next = AsyncMock(return_value="ok")
    for _ in range(3):
        result = await mw.on_request(FakeContext(), call_next)
        assert result == "ok"
    assert call_next.await_count == 3

    # 4th request from same IP — must raise.
    from mcp import McpError

    with pytest.raises(McpError) as excinfo:
        await mw.on_request(FakeContext(), call_next)
    # mcp>=1.28 wraps the structured payload on ``.error``
    assert excinfo.value.error.code == -32000
    assert "Rate limit" in str(excinfo.value)


@pytest.mark.asyncio
async def test_rate_limit_is_per_ip():
    mw = RateLimitMiddleware(max_requests_per_minute=1)
    call_next = AsyncMock(return_value="ok")
    await mw.on_request(FakeContext(client_host="10.0.0.1"), call_next)
    await mw.on_request(FakeContext(client_host="10.0.0.2"), call_next)
    assert call_next.await_count == 2


@pytest.mark.asyncio
async def test_rate_limit_disabled_when_max_zero():
    mw = RateLimitMiddleware(max_requests_per_minute=0)
    call_next = AsyncMock(return_value="ok")
    for _ in range(50):
        await mw.on_request(FakeContext(), call_next)
    assert call_next.await_count == 50


@pytest.mark.asyncio
async def test_rate_limit_skips_exempt_methods():
    mw = RateLimitMiddleware(max_requests_per_minute=1)
    call_next = AsyncMock(return_value="ok")
    # Initialize / ping / notifications never count toward the bucket.
    for _ in range(20):
        await mw.on_request(FakeContext(method="initialize"), call_next)
        await mw.on_request(FakeContext(method="ping"), call_next)
    assert call_next.await_count == 40


@pytest.mark.asyncio
async def test_rate_limit_skips_stdio_transport():
    """Stdio traffic is single-process; the limiter should not enforce it."""
    mw = RateLimitMiddleware(max_requests_per_minute=1)
    call_next = AsyncMock(return_value="ok")
    for _ in range(20):
        await mw.on_request(FakeContext(transport="stdio"), call_next)
    assert call_next.await_count == 20


@pytest.mark.asyncio
async def test_logging_middleware_passes_through():
    mw = RequestLoggingMiddleware()
    call_next = AsyncMock(return_value={"ok": True})
    result = await mw.on_request(FakeContext(method="tools/call"), call_next)
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_logging_middleware_swallows_nothing_but_logs():
    """If the inner call raises, the middleware must re-raise."""
    mw = RequestLoggingMiddleware()
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        await mw.on_request(FakeContext(method="tools/call"), call_next)


def test_build_default_middleware_returns_expected_stack():
    stack = build_default_middleware(rate_limit_per_minute=5)
    assert len(stack) == 2
    assert isinstance(stack[0], RequestLoggingMiddleware)
    assert isinstance(stack[1], RateLimitMiddleware)
    # Logging first (outermost), rate-limit second (innermost)
    assert stack[1].max_requests == 5
