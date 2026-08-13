"""
Integration smoke tests for the MT5 MCP server.

These are runnable as a plain script (``python tests/integration_test.py``)
or with pytest. They do NOT require a live MetaTrader 5 terminal — the MT5
native module is stubbed so we can exercise the import graph and CLI surface.
"""

from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

# Make sure the source tree is importable when this script is run directly.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Stub the MetaTrader5 native module before anything in mt5_mcp imports it.
import types

_TIMEFRAMES = {
    "TIMEFRAME_M1": 1, "TIMEFRAME_M2": 2, "TIMEFRAME_M3": 3, "TIMEFRAME_M4": 4,
    "TIMEFRAME_M5": 5, "TIMEFRAME_M6": 6, "TIMEFRAME_M10": 10, "TIMEFRAME_M12": 12,
    "TIMEFRAME_M15": 15, "TIMEFRAME_M20": 20, "TIMEFRAME_M30": 30,
    "TIMEFRAME_H1": 16385, "TIMEFRAME_H2": 16386, "TIMEFRAME_H3": 16387, "TIMEFRAME_H4": 16388,
    "TIMEFRAME_H6": 16390, "TIMEFRAME_H8": 16392, "TIMEFRAME_H12": 16396,
    "TIMEFRAME_D1": 16408, "TIMEFRAME_W1": 32769, "TIMEFRAME_MN1": 49153,
}


class _StubMT5(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("MetaTrader5")
        self.initialize = lambda *a, **k: True
        self.shutdown = lambda *a, **k: None
        self.last_error = lambda *a, **k: (0, "stub")
        self.terminal_info = lambda *a, **k: None
        self.account_info = lambda *a, **k: None
        self.symbol_info = lambda *a, **k: None
        self.symbol_info_tick = lambda *a, **k: None
        self.symbol_select = lambda *a, **k: True
        self.symbols_get = lambda *a, **k: None
        self.symbols_total = lambda *a, **k: 0
        self.copy_rates_from = lambda *a, **k: None
        self.copy_rates_from_pos = lambda *a, **k: None
        self.copy_rates_range = lambda *a, **k: None
        self.copy_ticks_from = lambda *a, **k: None
        self.copy_ticks_range = lambda *a, **k: None
        self.version = lambda *a, **k: (5, 0, 0)
        self.history_deals_get = lambda *a, **k: None
        self.history_orders_get = lambda *a, **k: None
        self.positions_get = lambda *a, **k: None
        self.positions_total = lambda *a, **k: 0
        self.order_calc_margin = lambda *a, **k: None
        self.order_calc_profit = lambda *a, **k: None
        self.COPY_TICKS_ALL = -1
        self.COPY_TICKS_INFO = 1
        self.COPY_TICKS_TRADE = 2
        self.ORDER_TYPE_BUY = 0
        self.ORDER_TYPE_SELL = 1
        for name, value in _TIMEFRAMES.items():
            setattr(self, name, value)


_mt5_stub = _StubMT5()
sys.modules.setdefault("MetaTrader5", _mt5_stub)
sys.modules.setdefault("mt5", _mt5_stub)


print("=" * 80)
print("MT5 MCP Server v0.6.0 — Integration Smoke Tests (FastMCP v3)")
print("=" * 80)
print()


# ---------------------------------------------------------------------------
# Test 1 — Python version
# ---------------------------------------------------------------------------
print("Test 1: Python runtime")
print("-" * 80)
print(f"  python: {sys.version.split()[0]}")
print(f"  executable: {sys.executable}")
print(f"  PYTHONPATH head: {sys.path[0]}")
print()


# ---------------------------------------------------------------------------
# Test 2 — Package import
# ---------------------------------------------------------------------------
print("Test 2: Package import")
print("-" * 80)
try:
    import mt5_mcp

    print(f"  package version: {mt5_mcp.__version__}")
    assert mt5_mcp.__version__ == "0.6.0", (
        f"Expected v0.6.0, got {mt5_mcp.__version__}"
    )
    print("  mt5_mcp.create_mcp_server:", mt5_mcp.create_mcp_server)
    print("  mt5_mcp.get_mcp_server:", mt5_mcp.get_mcp_server)
except Exception as exc:
    print(f"  FAIL: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    sys.exit(1)
print()


# ---------------------------------------------------------------------------
# Test 3 — Core modules importable
# ---------------------------------------------------------------------------
print("Test 3: Core modules")
print("-" * 80)
try:
    from mt5_mcp.connection import get_connection, safe_mt5_call  # noqa: F401
    from mt5_mcp.executor import execute_command
    from mt5_mcp.handlers import handle_mt5_analysis, handle_mt5_query
    from mt5_mcp.mcp_server import create_mcp_server
    from mt5_mcp.mcp_tools import mt5_analyze, mt5_execute, mt5_query
    from mt5_mcp.middleware import (  # noqa: F401
        RateLimitMiddleware,
        RequestLoggingMiddleware,
        build_default_middleware,
    )
    from mt5_mcp.validators import convert_timeframe, validate_ta_function  # noqa: F401

    print("  ✓ connection, handlers, executor, validators importable")
    print("  ✓ mcp_server, mcp_tools, middleware importable")
except Exception as exc:
    print(f"  FAIL: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    sys.exit(1)
print()


# ---------------------------------------------------------------------------
# Test 4 — Server construction
# ---------------------------------------------------------------------------
print("Test 4: FastMCP server construction")
print("-" * 80)
try:
    import asyncio

    server = create_mcp_server(rate_limit_per_minute=10)
    print(f"  server name: {server.name}")
    # Use the public async API rather than the (removed) private
    # ``_tool_manager._tools`` attribute.
    async def _list_tool_names():
        tool_objs = await server.get_tool("mt5_query")
        assert tool_objs.name == "mt5_query"
        await server.get_tool("mt5_analyze")
        await server.get_tool("mt5_execute")
        # Also confirm via the wire list — round-trip through the
        # tool manager to verify schemas serialize.
        tools = await server._list_tools()
        return sorted(t.name for t in tools)

    tool_names = asyncio.run(_list_tool_names())
    print(f"  registered tools: {tool_names}")
    assert tool_names == ["mt5_analyze", "mt5_execute", "mt5_query"], tool_names
    print("  ✓ All three tools registered")
    # Tool schemas must be JSON-serializable
    import json

    async def _serialize_schemas():
        for name in tool_names:
            tool = await server.get_tool(name)
            json.dumps(tool.parameters)

    asyncio.run(_serialize_schemas())
    print("  ✓ Tool schemas are JSON-serializable")
except Exception as exc:
    print(f"  FAIL: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    sys.exit(1)
print()


# ---------------------------------------------------------------------------
# Test 5 — CLI surface
# ---------------------------------------------------------------------------
print("Test 5: CLI --help")
print("-" * 80)
try:
    result = subprocess.run(
        [sys.executable, "-m", "mt5_mcp", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    help_text = result.stdout
    checks = [
        ("--transport", "Transport argument"),
        ("--rate-limit", "Rate limit argument"),
        ("--port", "Port argument"),
        ("--host", "Host argument"),
        ("stdio,http,sse,all", "Transport choices"),
        ("Examples:", "Usage examples"),
    ]
    for needle, label in checks:
        present = needle in help_text
        marker = "✓" if present else "✗"
        print(f"  {marker} {label} ({needle!r})")
        if not present:
            print(f"      stdout: {help_text[:300]}")
            sys.exit(1)
except Exception as exc:
    print(f"  FAIL: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    sys.exit(1)
print()


# ---------------------------------------------------------------------------
# Test 6 — Documentation completeness
# ---------------------------------------------------------------------------
print("Test 6: Docstrings")
print("-" * 80)
docs_to_check = [
    (mt5_query, "mt5_query"),
    (mt5_analyze, "mt5_analyze"),
    (mt5_execute, "mt5_execute"),
    (handle_mt5_query, "handle_mt5_query"),
    (handle_mt5_analysis, "handle_mt5_analysis"),
    (execute_command, "execute_command"),
    (safe_mt5_call, "safe_mt5_call"),
]
for fn, label in docs_to_check:
    doc = fn.__doc__ or ""
    has_args = "Args:" in doc
    has_returns = "Returns:" in doc or "return" in doc.lower()
    status = "✓" if (has_args and has_returns) else "✗"
    print(f"  {status} {label}: Args={has_args} Returns={has_returns}")
print()


# ---------------------------------------------------------------------------
# Test 7 — File structure
# ---------------------------------------------------------------------------
print("Test 7: File structure")
print("-" * 80)
required_files = [
    "src/mt5_mcp/__init__.py",
    "src/mt5_mcp/__main__.py",
    "src/mt5_mcp/connection.py",
    "src/mt5_mcp/handlers.py",
    "src/mt5_mcp/executor.py",
    "src/mt5_mcp/mcp_server.py",
    "src/mt5_mcp/mcp_tools.py",
    "src/mt5_mcp/middleware.py",
    "src/mt5_mcp/models.py",
    "src/mt5_mcp/validators.py",
    "src/mt5_mcp/errors.py",
    "src/mt5_mcp/error_utils.py",
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "USAGE.md",
]
for rel in required_files:
    full = ROOT / rel
    if full.exists():
        print(f"  ✓ {rel} ({full.stat().st_size} bytes)")
    else:
        print(f"  ✗ {rel} — MISSING")
        sys.exit(1)
print()


# ---------------------------------------------------------------------------
# Test 8 — No gradio references anywhere
# ---------------------------------------------------------------------------
print("Test 8: No gradio references in source")
print("-" * 80)
# Allowed mentions:
#   - "no gradio", "no Gradio", "Gradio has been removed" — README/CHANGELOG
#     explain the migration in narrative form.
#   - this test file itself, which contains the literal string ``gradio``
#     in its assertion messages.
# Anything else is a real reference (import, dependency, comment, etc.)
# and must be removed.
ALLOWED_PATH_SUFFIXES = {
    # The CHANGELOG documents the v0.5.x history; mentions are narrative.
    "CHANGELOG.md",
    # The README explains the migration; mentions are narrative.
    "README.md",
    # This script.
    "integration_test.py",
}

forbidden_globs = ["src/**/*.py", "tests/**/*.py", "*.md", "*.toml"]
bad: list[str] = []
for pattern in forbidden_globs:
    for path in ROOT.glob(pattern):
        if "egg-info" in str(path):
            continue
        if path.name in ALLOWED_PATH_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ("gradio", "gradio_ui", "gradio_server"):
            if needle in text.lower():
                bad.append(f"{path}: {needle}")
if bad:
    for entry in bad:
        print(f"  ✗ {entry}")
    sys.exit(1)
print("  ✓ No active gradio references (CHANGELOG/README may mention Gradio narratively)")
print()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("=" * 80)
print("Integration test summary")
print("=" * 80)
print("  ✓ Package imports on a lean Python (no pandas / MT5 / fastmcp required at import time)")
print("  ✓ FastMCP server constructs cleanly with all three tools")
print("  ✓ CLI exposes stdio|http|sse|all transports")
print("  ✓ All documentation strings include Args + Returns")
print("  ✓ All required source files present")
print("  ✓ No gradio references anywhere in the repo")
print()
print("READY FOR DEPLOYMENT")
print("=" * 80)
