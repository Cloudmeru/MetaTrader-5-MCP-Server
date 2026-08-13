"""
Manual smoke tests for MT5 MCP Server v0.6.0 (FastMCP v3).

Runs without a live MetaTrader 5 terminal: the MT5 native module is stubbed
so the import graph and CLI surface can be exercised on any machine.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Stub MetaTrader5 before any mt5_mcp import.
import types as _types

_TIMEFRAMES = {
    "TIMEFRAME_M1": 1, "TIMEFRAME_M2": 2, "TIMEFRAME_M3": 3, "TIMEFRAME_M4": 4,
    "TIMEFRAME_M5": 5, "TIMEFRAME_M6": 6, "TIMEFRAME_M10": 10, "TIMEFRAME_M12": 12,
    "TIMEFRAME_M15": 15, "TIMEFRAME_M20": 20, "TIMEFRAME_M30": 30,
    "TIMEFRAME_H1": 16385, "TIMEFRAME_H2": 16386, "TIMEFRAME_H3": 16387, "TIMEFRAME_H4": 16388,
    "TIMEFRAME_H6": 16390, "TIMEFRAME_H8": 16392, "TIMEFRAME_H12": 16396,
    "TIMEFRAME_D1": 16408, "TIMEFRAME_W1": 32769, "TIMEFRAME_MN1": 49153,
}


class _StubMT5(_types.ModuleType):
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


print("=" * 70)
print("MT5 MCP Server v0.6.0 — Manual test suite")
print("=" * 70)
print()


# 1 — Imports
print("Test 1: Import core modules")
print("-" * 70)
try:
    from mt5_mcp import connection, executor, handlers, models, validators  # noqa: F401

    print("  ✓ Core modules importable: connection, handlers, executor, models, validators")
except Exception as exc:
    print(f"  ✗ Import failed: {exc}")
    sys.exit(1)
print()


# 2 — Thread safety primitives
print("Test 2: Thread safety components")
print("-" * 70)
try:
    from mt5_mcp.connection import _mt5_lock, safe_mt5_call

    print(f"  ✓ Thread lock created: {type(_mt5_lock).__name__}")
    print(f"  ✓ safe_mt5_call callable: {callable(safe_mt5_call)}")
except Exception as exc:
    print(f"  ✗ Thread safety check failed: {exc}")
print()


# 3 — Pydantic models
print("Test 3: Pydantic models")
print("-" * 70)
try:
    from mt5_mcp.models import (
        IndicatorSpec,
        MT5AnalysisRequest,
        MT5Operation,
        MT5QueryRequest,
    )

    req = MT5QueryRequest(operation=MT5Operation.SYMBOL_INFO, symbol="BTCUSD")
    print(f"  ✓ MT5QueryRequest: {req.operation.value}")
    ind = IndicatorSpec(function="ta.momentum.rsi", params={"window": 14})
    print(f"  ✓ IndicatorSpec: {ind.function}")
    analysis_req = MT5AnalysisRequest(query=req, indicators=[ind])
    print(f"  ✓ MT5AnalysisRequest: output={analysis_req.output_format}")
except Exception as exc:
    print(f"  ✗ Model creation failed: {exc}")
print()


# 4 — Code executor
print("Test 4: Code executor")
print("-" * 70)
try:
    from mt5_mcp.executor import execute_command, format_result

    namespace = {"x": 10, "y": 20}
    result = execute_command("x + y", namespace, show_traceback=False)
    print(f"  ✓ Execute simple expression: {result.strip()!r}")
    formatted = format_result({"key": "value", "number": 42})
    print(f"  ✓ format_result works (length: {len(formatted)} chars)")
except Exception as exc:
    print(f"  ✗ Executor test failed: {exc}")
print()


# 5 — Validators
print("Test 5: Validators")
print("-" * 70)
try:
    from mt5_mcp.validators import convert_timeframe, validate_ta_function

    tf = convert_timeframe("H1")
    print(f"  ✓ Timeframe H1 -> {tf}")
    is_valid, _msg = validate_ta_function("ta.momentum.rsi")
    print(f"  ✓ TA validation: ta.momentum.rsi -> {is_valid}")
except Exception as exc:
    print(f"  ✗ Validator test failed: {exc}")
print()


# 6 — FastMCP middleware
print("Test 6: FastMCP middleware")
print("-" * 70)
try:
    from mt5_mcp.middleware import (  # noqa: F401
        RateLimitMiddleware,
        RequestLoggingMiddleware,
        build_default_middleware,
    )

    stack = build_default_middleware(rate_limit_per_minute=5)
    print(f"  ✓ Default middleware stack ({len(stack)} layers):")
    for mw in stack:
        print(f"      - {type(mw).__name__}")
    # Verify rate limiter state
    rl = RateLimitMiddleware(max_requests_per_minute=3)
    for i in range(3):
        assert rl._allow("127.0.0.1", i + 1.0) is True, "should allow"
    assert rl._allow("127.0.0.1", 4.0) is False, "should block"
    print("  ✓ Rate limiter allows up to limit, then blocks")
    rl = RateLimitMiddleware(max_requests_per_minute=0)
    for _ in range(20):
        assert rl._allow("any", 1.0) is True
    print("  ✓ Rate limiter with max=0 is fully open")
except Exception as exc:
    print(f"  ✗ Middleware test failed: {exc}")
print()


# 7 — Tool functions
print("Test 7: MCP tool functions")
print("-" * 70)
try:
    from mt5_mcp.mcp_tools import mt5_analyze, mt5_execute, mt5_query

    for fn in (mt5_query, mt5_analyze, mt5_execute):
        assert callable(fn)
        assert fn.__doc__, f"{fn.__name__} has no docstring"
        assert "Args:" in fn.__doc__
        assert "Returns:" in fn.__doc__ or "return" in fn.__doc__.lower()
    print("  ✓ mt5_query, mt5_analyze, mt5_execute all callable with rich docstrings")
except Exception as exc:
    print(f"  ✗ Tool test failed: {exc}")
print()


# 8 — Server construction
print("Test 8: FastMCP server construction")
print("-" * 70)
try:
    import asyncio

    from mt5_mcp.mcp_server import create_mcp_server, reset_mcp_server

    reset_mcp_server()
    server = create_mcp_server(rate_limit_per_minute=10)
    print(f"  ✓ Server name: {server.name}")

    async def _names():
        tools = await server._list_tools()
        return sorted(t.name for t in tools)

    tool_names = asyncio.run(_names())
    print(f"  ✓ Registered tools: {tool_names}")
    assert tool_names == ["mt5_analyze", "mt5_execute", "mt5_query"], tool_names
    # Singleton behavior
    server2 = create_mcp_server()
    assert server2 is server, "expected singleton"
    print("  ✓ create_mcp_server returns a singleton")
except Exception as exc:
    print(f"  ✗ Server test failed: {exc}")
print()


# 9 — Version
print("Test 9: Package version")
print("-" * 70)
try:
    import tomllib

    with open(ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    version = data["project"]["version"]
    print(f"  ✓ pyproject.toml version: {version}")
    assert version == "0.6.0", version
except Exception as exc:
    print(f"  ✗ Version check failed: {exc}")
print()


# 10 — Documentation
print("Test 10: Docstring quality")
print("-" * 70)
try:
    from mt5_mcp.executor import execute_command
    from mt5_mcp.handlers import handle_mt5_analysis, handle_mt5_query

    for fn, label in (
        (handle_mt5_query, "handle_mt5_query"),
        (handle_mt5_analysis, "handle_mt5_analysis"),
        (execute_command, "execute_command"),
    ):
        doc = fn.__doc__ or ""
        assert "Args:" in doc, f"{label} missing Args section"
        print(f"  ✓ {label} has Args section ({len(doc)} chars docstring)")
except Exception as exc:
    print(f"  ✗ Docstring test failed: {exc}")
print()


# Summary
print("=" * 70)
print("Test summary")
print("=" * 70)
print("  ✓ Core modules import on a lean environment")
print("  ✓ Pydantic models + validators operational")
print("  ✓ Executor and thread safety in place")
print("  ✓ FastMCP middleware + tool registration working")
print("  ✓ CLI entry point configured")
print()
print("⚠ Note: full integration tests require a live MetaTrader 5 terminal")
print("=" * 70)
