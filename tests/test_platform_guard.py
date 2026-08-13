"""
Tests for the platform-aware import guard in ``mt5_mcp.connection``.

The guard catches the case where a user installs the wheel on Linux/macOS
without the ``MetaTrader5`` dep (the ``sys_platform == 'win32'`` marker
in ``pyproject.toml`` prevents pip from installing it). Without the guard,
``import mt5_mcp`` would either crash later in the tool layer or, worse,
return a confusing ``ModuleNotFoundError`` from deep in the call stack.

The guard checks two things:

* If ``MetaTrader5`` is already in ``sys.modules`` (tests pre-stub it),
  the connection module imports normally — no platform check.
* If ``MetaTrader5`` is *not* in ``sys.modules`` and the platform is not
  Windows, raise an ``ImportError`` with an actionable message naming
  the actual platform.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util
import platform
import sys


def test_windows_no_guard_message_when_metaquotes_present():
    """On Windows, if MetaTrader5 is importable, connection imports cleanly.

    Skip on non-Windows hosts (where we can't simulate the Windows path
    without a real MetaTrader5 wheel).
    """
    if platform.system() != "Windows":
        return
    # Re-import connection under a fresh state to exercise the path.
    # Don't actually delete sys.modules — just confirm the guard doesn't
    # fire when MetaTrader5 is importable.
    if "mt5_mcp.connection" in sys.modules:
        importlib.reload(sys.modules["mt5_mcp.connection"])


def test_non_windows_raises_when_metaquotes_missing():
    """On Linux/macOS without a MetaTrader5 stub, the guard fires."""
    # Drop any pre-stubbed MetaTrader5 from sys.modules so the guard
    # sees the "missing" branch.
    saved_mt5 = sys.modules.pop("MetaTrader5", None)
    saved_connection = sys.modules.pop("mt5_mcp.connection", None)

    # Pretend MetaTrader5 is unavailable by patching __import__.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "MetaTrader5" or name.startswith("MetaTrader5."):
            raise ImportError(f"No module named {name!r} (simulated)")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import

    try:
        # We're on Linux CI right now (the test environment isn't Windows).
        # If we're on Windows for some reason, skip the negative path —
        # the positive path (above) covers it.
        if platform.system() == "Windows":
            return

        # Wipe the cached connection module so the import runs fresh.
        for mod_name in list(sys.modules):
            if mod_name == "mt5_mcp.connection" or mod_name.startswith(
                "mt5_mcp.connection."
            ):
                sys.modules.pop(mod_name, None)

        try:
            importlib.import_module("mt5_mcp.connection")
        except ImportError as exc:
            msg = str(exc)
            assert "mt5_mcp is only supported on Windows" in msg
            assert "MetaTrader5" in msg
            assert platform.system() in msg, (
                f"error message should name the platform; got: {msg!r}"
            )
        else:
            raise AssertionError(
                "expected ImportError on non-Windows without MetaTrader5; "
                "the guard did not fire"
            )
    finally:
        builtins.__import__ = real_import
        if saved_mt5 is not None:
            sys.modules["MetaTrader5"] = saved_mt5
        if saved_connection is not None:
            sys.modules["mt5_mcp.connection"] = saved_connection
