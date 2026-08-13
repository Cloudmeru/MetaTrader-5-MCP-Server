"""
FastMCP v3 middleware for the MetaTrader 5 MCP server.

Cross-cutting concerns live here:

* ``RateLimitMiddleware`` — per-IP request quota for HTTP transport.
  Stdio traffic is single-process and skips the limiter.
* ``LoggingMiddleware`` — uniform request / response / error logging.

FastMCP middleware is documented at https://gofastmcp.com/servers/middleware.
The base class is :class:`fastmcp.server.middleware.Middleware`; every hook
follows ``async def hook(self, context, call_next) -> result``.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class RateLimitMiddleware(Middleware):
    """Sliding-window per-IP rate limit, enforced only for HTTP transport.

    Stdio and SSE-direct transports don't carry an IP address, so we let
    those through. The bucket is a 60-second sliding window: at most
    ``max_requests`` calls per IP within the last minute.

    Args:
        max_requests_per_minute: Quota per IP. ``0`` disables the limiter.
        exempt_methods: Method names that should never count toward the
            limit (defaults to handshake/notification traffic).
    """

    DEFAULT_EXEMPT_METHODS: frozenset[str] = frozenset(
        {
            "initialize",
            "notifications/initialized",
            "notifications/cancelled",
            "notifications/progress",
            "ping",
        }
    )

    def __init__(
        self,
        max_requests_per_minute: int = 10,
        *,
        exempt_methods: Iterable[str] | None = None,
    ) -> None:
        self.max_requests = int(max_requests_per_minute)
        self.exempt_methods: frozenset[str] = frozenset(
            exempt_methods if exempt_methods is not None else self.DEFAULT_EXEMPT_METHODS
        )
        # Per-IP deques of monotonic timestamps.
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _client_ip(context: MiddlewareContext) -> str:
        """Best-effort IP extraction. Falls back to 'unknown'."""
        try:
            # The internal request object is exposed under ``context.request``
            # in FastMCP v3; the ``client`` carries the peer name.
            request = getattr(context, "request", None)
            if request is None:
                return "unknown"
            # ASGI scope for HTTP transports.
            scope = getattr(request, "scope", None)
            if scope is not None:
                client = scope.get("client")
                if client and client[0]:
                    return str(client[0])
            # Fall back to the MCP session id (no real IP, but stable key).
            session = getattr(context, "session", None)
            if session is not None:
                sid = getattr(session, "session_id", None) or getattr(session, "id", None)
                if sid:
                    return f"session:{sid}"
        except Exception as exc:
            logger.debug("failed to extract client IP: %s", exc)
        return "unknown"

    def _allow(self, ip: str, now: float) -> bool:
        if self.max_requests <= 0:
            return True
        bucket = self._buckets[ip]
        # Drop entries older than 60 seconds.
        cutoff = now - 60.0
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True

    # -- hook --------------------------------------------------------------

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        if context.method in self.exempt_methods:
            return await call_next(context)

        # Only enforce on HTTP transports. ``context.transport`` is a string
        # or None; treat anything not "stdio" as HTTP-shaped.
        transport = getattr(context, "transport", None)
        if transport == "stdio":
            return await call_next(context)

        now = time.monotonic()
        ip = self._client_ip(context)
        if not self._allow(ip, now):
            logger.warning(
                "rate-limit: blocking %s on %s (limit=%d/min)",
                ip,
                context.method,
                self.max_requests,
            )
            # Raise a structured error that FastMCP turns into a JSON-RPC
            # error response. ``McpError`` in mcp>=1.28 takes a single
            # ``ErrorData`` argument.
            from mcp import McpError
            from mcp.types import ErrorData

            raise McpError(
                ErrorData(
                    code=-32000,
                    message=f"Rate limit exceeded: {self.max_requests} requests/min per IP",
                )
            )

        return await call_next(context)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(Middleware):
    """Per-request structured logging with timing and outcome.

    Logs at INFO for normal calls and ERROR for exceptions. The middleware
    is intentionally quiet on ``on_message`` (handshake traffic) and only
    fires on the typed hooks (``on_request``, ``on_call_tool``).
    """

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        method = context.method
        if method in RateLimitMiddleware.DEFAULT_EXEMPT_METHODS:
            return await call_next(context)

        start = time.perf_counter()
        logger.info("→ %s start", method)
        try:
            result = await call_next(context)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.exception(
                "← %s failed in %.1f ms (%s: %s)",
                method,
                elapsed_ms,
                type(exc).__name__,
                exc,
            )
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.info("← %s ok in %.1f ms", method, elapsed_ms)
            return result


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------


def build_default_middleware(
    *, rate_limit_per_minute: int = 10
) -> list[Middleware]:
    """Build the standard middleware stack in registration order.

    Order matters: errors raised later in the chain must surface through
    the logging middleware, so logging is registered *first* (outermost)
    and rate-limiting second (innermost). See the FastMCP middleware docs
    for the execution order semantics.
    """
    return [
        RequestLoggingMiddleware(),
        RateLimitMiddleware(rate_limit_per_minute),
    ]


__all__ = [
    "RateLimitMiddleware",
    "RequestLoggingMiddleware",
    "build_default_middleware",
]
