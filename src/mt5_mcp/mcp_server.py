"""
FastMCP v3 server for the MetaTrader 5 MCP integration.

This module owns the FastMCP instance, registers every tool, and installs
the cross-cutting middleware (logging + rate limiting). The tool functions
themselves live in :mod:`mt5_mcp.mcp_tools` so they stay unit-testable
without a FastMCP context.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP instance (lazy — only built when ``create_mcp_server()`` is called)
# ---------------------------------------------------------------------------

_INSTANCE: FastMCP | None = None


def create_mcp_server(
    *,
    rate_limit_per_minute: int = 10,
) -> FastMCP:
    """Build and return the FastMCP server.

    Args:
        rate_limit_per_minute: HTTP transport rate limit in requests per
            IP per minute. ``0`` disables the limiter entirely. The limit
            is ignored for stdio transport (single-process clients).

    Returns:
        A configured :class:`fastmcp.FastMCP` instance.
    """
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE

    server = FastMCP(
        name="MetaTrader 5 MCP Server",
        version="0.6.0",
        instructions=(
            "Read-only access to a running MetaTrader 5 terminal. "
            "Use mt5_query for structured data retrieval, "
            "mt5_analyze for technical analysis with indicators and forecasting, "
            "and mt5_execute for ad-hoc Python against the safe MT5 namespace. "
            "All trading functions are blocked — this server is read-only."
        ),
        # Tools block-list of dangerous patterns is enforced inside the
        # ``mt5_execute`` tool body — see ``mcp_tools.py``. FastMCP itself
        # does not provide a sandbox.
        strict_input_validation=False,
    )

    # Install cross-cutting middleware (rate limiting + logging).
    from .middleware import build_default_middleware

    for mw in build_default_middleware(rate_limit_per_minute=rate_limit_per_minute):
        server.add_middleware(mw)

    # Register tools. Importing inside the function avoids the heavy
    # `pandas`/`MetaTrader5` import chain at module load time so the
    # package itself stays importable on lean CI environments.
    from .mcp_tools import (
        mt5_analyze,
        mt5_execute,
        mt5_query,
    )

    server.tool(
        mt5_query,
        name="mt5_query",
        title="MT5 Query",
        description=mt5_query.__doc__,
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    )
    server.tool(
        mt5_analyze,
        name="mt5_analyze",
        title="MT5 Analyze",
        description=mt5_analyze.__doc__,
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    )
    # mt5_execute runs user-supplied Python. It is "open world" but
    # sandboxed to a curated namespace — keep ``destructiveHint`` False
    # because it cannot place orders.
    server.tool(
        mt5_execute,
        name="mt5_execute",
        title="MT5 Execute (advanced)",
        description=mt5_execute.__doc__,
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    )

    _INSTANCE = server
    logger.info("FastMCP server created (rate_limit=%s req/min/IP)", rate_limit_per_minute)
    return server


def get_mcp_server() -> FastMCP:
    """Return the already-built singleton, or build it with defaults."""
    return _INSTANCE or create_mcp_server()


def reset_mcp_server() -> None:
    """Drop the cached singleton. Test-only helper."""
    global _INSTANCE
    _INSTANCE = None


__all__ = ["create_mcp_server", "get_mcp_server", "reset_mcp_server"]
