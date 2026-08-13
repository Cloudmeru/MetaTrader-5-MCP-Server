"""
Unit tests for ``mt5_mcp.mcp_server`` — verifies the FastMCP instance is
constructed with the right tools, the singleton cache works, and the tool
schemas are LLM-friendly (no string-encoded JSON parameters).
"""

from __future__ import annotations

import json

import pytest
from fastmcp import FastMCP

from mt5_mcp import mcp_server  # noqa: F401  (smoke import)
from mt5_mcp.mcp_server import create_mcp_server


def _reset_singleton():
    """Drop the cached FastMCP singleton (test helper)."""
    from mt5_mcp.mcp_server import reset_mcp_server

    reset_mcp_server()


def test_package_init_exports_factory():
    import mt5_mcp

    assert mt5_mcp.__version__ == "0.6.3"
    assert mt5_mcp.create_mcp_server is create_mcp_server


def test_create_mcp_server_returns_fastmcp_instance():
    server = create_mcp_server()
    assert isinstance(server, FastMCP)
    assert server.name == "MetaTrader 5 MCP Server"


def test_create_mcp_server_is_singleton():
    a = create_mcp_server()
    b = create_mcp_server()
    assert a is b


@pytest.mark.asyncio
async def test_all_three_tools_registered():
    server = create_mcp_server()
    tools = await server.get_tool("mt5_query")
    assert tools.name == "mt5_query"
    tools = await server.get_tool("mt5_analyze")
    assert tools.name == "mt5_analyze"
    tools = await server.get_tool("mt5_execute")
    assert tools.name == "mt5_execute"


@pytest.mark.asyncio
async def test_tool_parameters_are_proper_json_schemas():
    """No 'parameters: str' regression — must be a JSON object in the schema."""
    server = create_mcp_server()
    for name in ("mt5_query", "mt5_analyze", "mt5_execute"):
        tool = await server.get_tool(name)
        schema = tool.parameters
        assert schema["type"] == "object", (
            f"{name} should declare an object schema, got {schema.get('type')}"
        )
        # Every property in the schema must be JSON-serialisable.
        json.dumps(schema)


@pytest.mark.asyncio
async def test_query_tool_schema_uses_object_for_parameters():
    server = create_mcp_server()
    tool = await server.get_tool("mt5_query")
    params = tool.parameters["properties"]["parameters"]
    # Must not be a string — the old regression. Pydantic turns
    # `Optional[dict[str, Any]]` into {"anyOf": [{"type":"object",...},
    # {"type":"null"}]} which is fine.
    assert "string" not in params.get("type", ""), (
        f"parameters should not be a string, got {params}"
    )


@pytest.mark.asyncio
async def test_analyze_tool_schema_lists_indicator_and_chart_fields():
    server = create_mcp_server()
    tool = await server.get_tool("mt5_analyze")
    props = tool.parameters["properties"]
    for field in ("operation", "symbol", "parameters", "indicators", "chart", "forecast"):
        assert field in props, f"mt5_analyze schema missing {field!r}"


def test_middleware_attached():
    """create_mcp_server installs logging + rate-limit middleware."""
    server = create_mcp_server()
    from mt5_mcp.middleware import RateLimitMiddleware, RequestLoggingMiddleware

    middleware_types = {type(mw) for mw in server.middleware}
    assert RequestLoggingMiddleware in middleware_types
    assert RateLimitMiddleware in middleware_types


def test_middleware_respects_rate_limit_config():
    server = create_mcp_server(rate_limit_per_minute=42)
    from mt5_mcp.middleware import RateLimitMiddleware

    rl = next(mw for mw in server.middleware if isinstance(mw, RateLimitMiddleware))
    assert rl.max_requests == 42


def test_reset_mcp_server_clears_singleton():
    from mt5_mcp.mcp_server import reset_mcp_server

    create_mcp_server()
    reset_mcp_server()
    a = create_mcp_server()
    reset_mcp_server()
    b = create_mcp_server()
    assert a is not b
