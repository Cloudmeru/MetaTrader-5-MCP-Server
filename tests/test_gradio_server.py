"""
Integration tests for gradio_server.py - Rate limiting and MCP tools.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys

# Mock MT5 and Gradio
mock_mt5 = MagicMock()
mock_mt5.initialize.return_value = True
sys.modules["MetaTrader5"] = mock_mt5

mock_gradio = MagicMock()
sys.modules["gradio"] = mock_gradio


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality."""

    def setUp(self):
        """Reset rate limit store before each test."""
        # Import and reset
        from mt5_mcp import gradio_server

        gradio_server._rate_limit_store.clear()
        gradio_server.HTTP_RATE_LIMIT = 10

    def test_rate_limit_disabled(self):
        """Test that rate limiting can be disabled."""
        from mt5_mcp.gradio_server import set_rate_limit, check_rate_limit

        # Disable rate limiting
        set_rate_limit(0)

        # Create mock request
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Should always pass
        for _ in range(20):
            result = check_rate_limit(mock_request)
            self.assertTrue(result)

    def test_rate_limit_enforced(self):
        """Test that rate limit is enforced."""
        from mt5_mcp.gradio_server import set_rate_limit, check_rate_limit

        # Set low rate limit
        set_rate_limit(3)

        # Create mock request
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # First 3 requests should pass
        for _ in range(3):
            result = check_rate_limit(mock_request)
            self.assertTrue(result)

        # 4th request should fail
        with self.assertRaises(Exception) as context:  # gr.Error
            check_rate_limit(mock_request)

        self.assertIn("Rate limit exceeded", str(context.exception))

    def test_rate_limit_per_ip(self):
        """Test that rate limit is per IP address."""
        from mt5_mcp.gradio_server import set_rate_limit, check_rate_limit

        set_rate_limit(3)

        # Create requests from different IPs
        request1 = Mock()
        request1.client.host = "192.168.1.1"

        request2 = Mock()
        request2.client.host = "192.168.1.2"

        # Each IP should have its own limit
        for _ in range(3):
            check_rate_limit(request1)
            check_rate_limit(request2)

        # Both IPs should now be at limit
        with self.assertRaises(Exception):
            check_rate_limit(request1)

        with self.assertRaises(Exception):
            check_rate_limit(request2)

    def test_rate_limit_window_expiry(self):
        """Test that rate limit window expires after 1 minute."""
        from mt5_mcp.gradio_server import set_rate_limit, check_rate_limit
        from mt5_mcp import gradio_server

        set_rate_limit(2)

        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Use 2 requests
        check_rate_limit(mock_request)
        check_rate_limit(mock_request)

        # Should be at limit
        with self.assertRaises(Exception):
            check_rate_limit(mock_request)

        # Manually expire old entries by setting timestamps to past
        old_time = datetime.now() - timedelta(minutes=2)
        gradio_server._rate_limit_store["127.0.0.1"] = [old_time, old_time]

        # Should now pass (old entries expired)
        result = check_rate_limit(mock_request)
        self.assertTrue(result)


class TestMT5QueryTool(unittest.TestCase):
    """Test mt5_query_tool function."""

    @patch("mt5_mcp.gradio_server.handle_mt5_query")
    def test_query_tool_success(self, mock_handle):
        """Test successful query tool execution."""
        from mt5_mcp.gradio_server import mt5_query_tool
        from mt5_mcp.models import MT5QueryResponse

        # Mock response
        mock_handle.return_value = MT5QueryResponse(
            success=True,
            operation="symbol_info",
            data={"name": "BTCUSD", "bid": 50000.0},
            metadata={},
        )

        # Execute without rate limiting (no request object)
        result = mt5_query_tool(
            operation="symbol_info", symbol="BTCUSD", parameters=None, request=None
        )

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "symbol_info")
        self.assertIn("name", result["data"])

    @patch("mt5_mcp.gradio_server.handle_mt5_query")
    def test_query_tool_with_rate_limit(self, mock_handle):
        """Test query tool with rate limiting."""
        from mt5_mcp.gradio_server import mt5_query_tool, set_rate_limit
        from mt5_mcp.models import MT5QueryResponse

        set_rate_limit(5)

        mock_handle.return_value = MT5QueryResponse(
            success=True, operation="symbol_info", data={}, metadata={}
        )

        # Create mock request
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"

        # Execute multiple times
        for _ in range(5):
            result = mt5_query_tool(operation="symbol_info", symbol="BTCUSD", request=mock_request)
            self.assertTrue(result["success"])

    @patch("mt5_mcp.gradio_server.handle_mt5_query")
    def test_query_tool_error_handling(self, mock_handle):
        """Test query tool error handling."""
        from mt5_mcp.gradio_server import mt5_query_tool

        # Mock error
        mock_handle.side_effect = ValueError("Invalid symbol")

        # Execute
        result = mt5_query_tool(operation="symbol_info", symbol="INVALID", request=None)

        # Verify error response
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Invalid symbol", result["error"])


class TestMT5AnalyzeTool(unittest.TestCase):
    """Test mt5_analyze_tool function."""

    @patch("mt5_mcp.gradio_server.handle_mt5_analysis")
    def test_analyze_tool_basic(self, mock_handle):
        """Test basic analysis tool execution."""
        from mt5_mcp.gradio_server import mt5_analyze_tool
        from mt5_mcp.models import MT5AnalysisResponse

        # Mock response
        mock_handle.return_value = MT5AnalysisResponse(
            success=True,
            data=[{"close": 50000.0}],
            indicators_calculated=["rsi"],
            metadata={"rows_returned": 1},
        )

        # Execute
        result = mt5_analyze_tool(
            query_operation="copy_rates_from_pos",
            query_symbol="BTCUSD",
            query_parameters={"timeframe": "H1", "count": 100},
            indicators=[{"function": "ta.momentum.rsi", "params": {"window": 14}}],
            request=None,
        )

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(len(result["indicators_calculated"]), 1)


class TestMT5ExecuteTool(unittest.TestCase):
    """Test mt5_execute_tool function."""

    @patch("mt5_mcp.gradio_server.get_safe_namespace")
    @patch("mt5_mcp.gradio_server.execute_command")
    def test_execute_tool_success(self, mock_execute, mock_namespace):
        """Test successful code execution."""
        from mt5_mcp.gradio_server import mt5_execute_tool

        mock_namespace.return_value = {"x": 10}
        mock_execute.return_value = "Result: 42"

        # Execute
        result = mt5_execute_tool(command="result = x * 4 + 2", show_traceback=True, request=None)

        # Verify
        self.assertEqual(result, "Result: 42")
        mock_execute.assert_called_once()

    @patch("mt5_mcp.gradio_server.get_safe_namespace")
    @patch("mt5_mcp.gradio_server.execute_command")
    def test_execute_tool_error(self, mock_execute, mock_namespace):
        """Test code execution with error."""
        from mt5_mcp.gradio_server import mt5_execute_tool

        mock_namespace.return_value = {}
        mock_execute.side_effect = Exception("Execution failed")

        # Execute
        result = mt5_execute_tool(command="invalid code", show_traceback=True, request=None)

        # Verify error message
        self.assertIn("Error", result)


class TestSetRateLimit(unittest.TestCase):
    """Test rate limit configuration."""

    def test_set_rate_limit_changes_global(self):
        """Test that set_rate_limit changes global variable."""
        from mt5_mcp import gradio_server

        initial_limit = gradio_server.HTTP_RATE_LIMIT

        gradio_server.set_rate_limit(50)
        self.assertEqual(gradio_server.HTTP_RATE_LIMIT, 50)

        # Reset
        gradio_server.set_rate_limit(initial_limit)


if __name__ == "__main__":
    unittest.main()
