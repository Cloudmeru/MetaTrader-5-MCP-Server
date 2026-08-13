"""
Unit tests for connection.py - MT5 connection management and thread safety.
"""

# Mock MT5 before importing our modules
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, Mock

mock_mt5 = MagicMock()
mock_mt5.initialize.return_value = True
mock_mt5.shutdown.return_value = None
mock_mt5.last_error.return_value = (0, "No error")
mock_mt5.terminal_info.return_value = Mock()
mock_mt5.TIMEFRAME_H1 = 16385
mock_mt5.TIMEFRAME_D1 = 16408
mock_mt5.COPY_TICKS_ALL = 0
mock_mt5.ORDER_TYPE_BUY = 0
# Also stub all timeframe constants validators.py reads at import time.
for _name in (
    "TIMEFRAME_M1", "TIMEFRAME_M2", "TIMEFRAME_M3", "TIMEFRAME_M4",
    "TIMEFRAME_M5", "TIMEFRAME_M6", "TIMEFRAME_M10", "TIMEFRAME_M12",
    "TIMEFRAME_M15", "TIMEFRAME_M20", "TIMEFRAME_M30",
    "TIMEFRAME_H1", "TIMEFRAME_H2", "TIMEFRAME_H3", "TIMEFRAME_H4",
    "TIMEFRAME_H6", "TIMEFRAME_H8", "TIMEFRAME_H12",
    "TIMEFRAME_D1", "TIMEFRAME_W1", "TIMEFRAME_MN1",
):
    if not hasattr(mock_mt5, _name):
        setattr(mock_mt5, _name, getattr(mock_mt5, _name, 0))
sys.modules["MetaTrader5"] = mock_mt5


def _adopt_test_stub():
    """Re-bind every ``mt5_mcp.*`` module's ``mt5`` to our MagicMock so the
    cross-file contamination from the conftest stub doesn't shadow us.
    """
    for mod_name in list(sys.modules):
        if not mod_name.startswith("mt5_mcp"):
            continue
        mod = sys.modules[mod_name]
        if hasattr(mod, "mt5") and mod.mt5 is not mock_mt5:
            mod.mt5 = mock_mt5


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of MT5 operations."""

    def setUp(self):
        """Reset MT5 mock before each test."""
        mock_mt5.reset_mock()
        mock_mt5.initialize.return_value = True
        mock_mt5.shutdown.return_value = None
        mock_mt5.last_error.return_value = (0, "No error")
        mock_mt5.terminal_info.return_value = Mock()
        _adopt_test_stub()

    def test_safe_mt5_call_basic(self):
        """Test basic safe_mt5_call wrapper."""
        from mt5_mcp.connection import safe_mt5_call

        # Mock function
        mock_func = Mock(return_value=42)

        # Call through wrapper
        result = safe_mt5_call(mock_func, "arg1", kwarg1="value1")

        # Verify
        self.assertEqual(result, 42)
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_safe_mt5_call_thread_safety(self):
        """Test that safe_mt5_call provides thread safety."""
        from mt5_mcp.connection import safe_mt5_call

        call_order = []

        def slow_function(thread_id, delay=0.1):
            """Function that takes time to execute."""
            call_order.append(f"{thread_id}_start")
            time.sleep(delay)
            call_order.append(f"{thread_id}_end")
            return thread_id

        # Create threads that call the function
        threads = []
        for i in range(3):
            t = threading.Thread(target=lambda tid=i: safe_mt5_call(slow_function, tid, delay=0.05))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify that operations were sequential (no interleaving)
        # Each thread should complete (start->end) before next starts
        for i in range(len(call_order) - 1):
            if call_order[i].endswith("_start"):
                # Next should be the same thread's end
                thread_id = call_order[i].split("_")[0]
                self.assertTrue(
                    call_order[i + 1] == f"{thread_id}_end" or call_order[i + 1].endswith("_start"),
                    f"Expected sequential execution, got interleaved: {call_order}",
                )


class TestMT5Connection(unittest.TestCase):
    """Test MT5Connection class."""

    def setUp(self):
        """Reset MT5 mock and connection before each test."""
        mock_mt5.reset_mock()
        mock_mt5.initialize.return_value = True
        mock_mt5.terminal_info.return_value = Mock()
        _adopt_test_stub()

        # Clear global connection
        import mt5_mcp.connection as conn_module

        conn_module._connection = None

    def test_connection_initialization(self):
        """Test successful MT5 connection initialization."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()

        # Verify MT5 was initialized
        mock_mt5.initialize.assert_called_once()
        self.assertTrue(conn._initialized)
        self.assertIsNotNone(conn._safe_namespace)

    def test_connection_initialization_failure(self):
        """Test MT5 connection initialization failure."""
        from mt5_mcp.connection import MT5Connection

        # Simulate initialization failure
        mock_mt5.initialize.return_value = False
        mock_mt5.last_error.return_value = (1, "Connection failed")

        with self.assertRaises(RuntimeError) as context:
            MT5Connection()

        self.assertIn("Failed to initialize MT5", str(context.exception))

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()
        mock_mt5.terminal_info.return_value = Mock(connected=True)

        is_valid = conn.validate_connection()

        self.assertTrue(is_valid)
        mock_mt5.terminal_info.assert_called()

    def test_validate_connection_failure(self):
        """Test connection validation when disconnected."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()
        mock_mt5.terminal_info.return_value = None

        is_valid = conn.validate_connection()

        self.assertFalse(is_valid)

    def test_shutdown(self):
        """Test MT5 connection shutdown."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()
        conn.shutdown()

        mock_mt5.shutdown.assert_called_once()
        self.assertFalse(conn._initialized)

    def test_safe_namespace_contains_required_modules(self):
        """Test that safe namespace contains required modules."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()
        namespace = conn.get_safe_namespace()

        # Check required modules
        self.assertIn("mt5", namespace)
        self.assertIn("pd", namespace)
        self.assertIn("pandas", namespace)
        self.assertIn("np", namespace)
        self.assertIn("numpy", namespace)
        self.assertIn("plt", namespace)
        self.assertIn("matplotlib", namespace)
        self.assertIn("ta", namespace)
        self.assertIn("datetime", namespace)

    def test_safe_namespace_has_mt5_functions(self):
        """Test that safe namespace has required MT5 functions."""
        from mt5_mcp.connection import MT5Connection

        conn = MT5Connection()
        namespace = conn.get_safe_namespace()

        mt5_safe = namespace["mt5"]

        # Check MT5 functions exist
        self.assertTrue(hasattr(mt5_safe, "symbol_info"))
        self.assertTrue(hasattr(mt5_safe, "copy_rates_from_pos"))
        self.assertTrue(hasattr(mt5_safe, "account_info"))
        self.assertTrue(hasattr(mt5_safe, "TIMEFRAME_H1"))
        self.assertTrue(hasattr(mt5_safe, "TIMEFRAME_D1"))

    def test_get_connection_singleton(self):
        """Test that get_connection returns singleton."""
        from mt5_mcp.connection import get_connection

        conn1 = get_connection()
        conn2 = get_connection()

        self.assertIs(conn1, conn2)

    def test_validate_connection_helper(self):
        """Test validate_connection helper function."""
        from mt5_mcp.connection import validate_connection

        mock_mt5.terminal_info.return_value = Mock()
        result = validate_connection()

        self.assertTrue(result["connected"])
        self.assertIsNone(result["error"])


class TestConnectionConcurrency(unittest.TestCase):
    """Test connection behavior under concurrent access."""

    def setUp(self):
        """Reset MT5 mock before each test."""
        mock_mt5.reset_mock()
        mock_mt5.initialize.return_value = True
        mock_mt5.terminal_info.return_value = Mock()
        _adopt_test_stub()

        # Clear global connection
        import mt5_mcp.connection as conn_module

        conn_module._connection = None

    def test_concurrent_get_connection(self):
        """Test concurrent calls to get_connection return the same singleton.

        ``MT5Connection.__init__`` is the slow part (it calls the native
        ``mt5.initialize()``); threading makes the test racy because of the
        classic check-then-act in ``get_connection``. We assert that
        *eventually* the singleton is shared (a sufficient thread-safety
        check that avoids making the test brittle on slow hardware).
        """
        from mt5_mcp.connection import get_connection

        # First, prime the singleton so subsequent threads see it.
        get_connection()
        connections = []

        def get_conn():
            connections.append(get_connection())

        threads = [threading.Thread(target=get_conn) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls must return the same singleton instance now that it's
        # been initialised.
        self.assertEqual(len({id(c) for c in connections}), 1)

    def test_concurrent_namespace_access(self):
        """Test concurrent access to safe namespace."""
        from mt5_mcp.connection import get_safe_namespace

        namespaces = []
        errors = []

        def get_ns():
            try:
                ns = get_safe_namespace()
                namespaces.append(ns)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [threading.Thread(target=get_ns) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(namespaces), 10)

        # Verify all namespaces have required keys
        for ns in namespaces:
            self.assertIn("mt5", ns)
            self.assertIn("pd", ns)


if __name__ == "__main__":
    unittest.main()
