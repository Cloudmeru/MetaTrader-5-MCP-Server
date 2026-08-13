"""
Pytest configuration and shared fixtures for the MT5 MCP test suite.

The MetaTrader5 native module is Windows-only and not available on Linux CI.
Every test file imports ``mt5_mcp.*`` modules which transitively import
``MetaTrader5`` and read module-level timeframe constants. We stub the
module before any ``mt5_mcp`` import runs so the test suite can execute on
any platform.

The stub:

* Exposes every MT5 function with sensible no-op defaults.
* Exposes every timeframe constant (M1..MN1) so ``validators.py`` can build
  its lookup table at import time.
* Returns ``None`` from ``terminal_info`` so ``validate_connection`` reports
  "not connected" — the tool layer then returns a structured JSON error
  instead of crashing the test.

Tests that need to simulate a "connected" terminal can override
``stub_mt5.terminal_info.return_value`` to a truthy value.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator

import pytest

# ---------------------------------------------------------------------------
# MT5 stub
# ---------------------------------------------------------------------------


_TIMEFRAMES: dict[str, int] = {
    "TIMEFRAME_M1": 1,
    "TIMEFRAME_M2": 2,
    "TIMEFRAME_M3": 3,
    "TIMEFRAME_M4": 4,
    "TIMEFRAME_M5": 5,
    "TIMEFRAME_M6": 6,
    "TIMEFRAME_M10": 10,
    "TIMEFRAME_M12": 12,
    "TIMEFRAME_M15": 15,
    "TIMEFRAME_M20": 20,
    "TIMEFRAME_M30": 30,
    "TIMEFRAME_H1": 16385,
    "TIMEFRAME_H2": 16386,
    "TIMEFRAME_H3": 16387,
    "TIMEFRAME_H4": 16388,
    "TIMEFRAME_H6": 16390,
    "TIMEFRAME_H8": 16392,
    "TIMEFRAME_H12": 16396,
    "TIMEFRAME_D1": 16408,
    "TIMEFRAME_W1": 32769,
    "TIMEFRAME_MN1": 49153,
}


class _StubMT5(types.ModuleType):
    """Lightweight MetaTrader5 stand-in for tests."""

    def __init__(self) -> None:
        super().__init__("MetaTrader5")
        # Function call surface (no-ops; tests override as needed).
        self.initialize = lambda *a, **k: True
        self.shutdown = lambda *a, **k: None
        self.last_error = lambda *a, **k: (-1, "stub")
        self.terminal_info = lambda *a, **k: None
        self.account_info = lambda *a, **k: None
        self.version = lambda *a, **k: (5, 0, 0)
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
        self.history_deals_get = lambda *a, **k: None
        self.history_orders_get = lambda *a, **k: None
        self.positions_get = lambda *a, **k: None
        self.positions_total = lambda *a, **k: 0
        self.order_calc_margin = lambda *a, **k: None
        self.order_calc_profit = lambda *a, **k: None
        # Constants.
        for name, value in _TIMEFRAMES.items():
            setattr(self, name, value)
        self.COPY_TICKS_ALL = -1
        self.COPY_TICKS_INFO = 1
        self.COPY_TICKS_TRADE = 2
        self.ORDER_TYPE_BUY = 0
        self.ORDER_TYPE_SELL = 1


@pytest.fixture(scope="session", autouse=True)
def _install_mt5_stub() -> Iterator[None]:
    """Install the MT5 stub before any test module imports ``mt5_mcp``."""
    stub = _StubMT5()
    sys.modules.setdefault("MetaTrader5", stub)
    sys.modules.setdefault("mt5", stub)
    yield
    # Don't remove on teardown — once installed the import cache is happy.


@pytest.fixture
def mt5_stub() -> _StubMT5:
    """Return the live MT5 stub so a test can override return values."""
    return sys.modules["MetaTrader5"]


@pytest.fixture(autouse=True)
def _reset_mcp_singleton() -> Iterator[None]:
    """Reset the cached FastMCP singleton between tests so middleware
    state (rate-limit buckets) doesn't bleed between cases.
    """
    try:
        from mt5_mcp.mcp_server import reset_mcp_server  # noqa: WPS433
    except ImportError:
        yield
        return
    reset_mcp_server()
    yield
    reset_mcp_server()


@pytest.fixture
def adopt_mt5_stub(mt5_stub: _StubMT5):
    """Make every ``mt5_mcp.*`` module's ``mt5`` reference point at the
    conftest stub. Tests that import ``mt5_mcp.connection`` (or any other
    module) BEFORE the conftest stub is installed need this fixture to keep
    the ``mt5`` name resolution consistent across files.
    """
    import sys

    for mod_name in list(sys.modules):
        if not mod_name.startswith("mt5_mcp"):
            continue
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        if hasattr(mod, "mt5") and mod.mt5 is not mt5_stub:
            mod.mt5 = mt5_stub
    return mt5_stub
