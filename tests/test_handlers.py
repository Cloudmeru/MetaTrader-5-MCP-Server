"""
Unit tests for handlers.py - MT5 query and analysis handlers.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import pandas as pd
import numpy as np

# Mock MT5
mock_mt5 = MagicMock()
mock_mt5.initialize.return_value = True
mock_mt5.TIMEFRAME_H1 = 16385
mock_mt5.TIMEFRAME_D1 = 16408
mock_mt5.COPY_TICKS_ALL = 0
sys.modules["MetaTrader5"] = mock_mt5


class TestHandleMT5Query(unittest.TestCase):
    """Test handle_mt5_query function."""

    def setUp(self):
        """Reset mocks before each test."""
        mock_mt5.reset_mock()

    @patch("mt5_mcp.handlers.safe_mt5_call")
    def test_query_symbol_info(self, mock_safe_call):
        """Test querying symbol information."""
        from mt5_mcp.handlers import handle_mt5_query
        from mt5_mcp.models import MT5QueryRequest, MT5Operation

        # Mock symbol info response
        mock_symbol_info = Mock()
        mock_symbol_info._asdict.return_value = {
            "name": "BTCUSD",
            "bid": 50000.0,
            "ask": 50001.0,
        }
        mock_safe_call.return_value = mock_symbol_info

        # Create request
        request = MT5QueryRequest(operation=MT5Operation.SYMBOL_INFO, symbol="BTCUSD")

        # Execute
        response = handle_mt5_query(request)

        # Verify
        self.assertTrue(response.success)
        self.assertEqual(response.operation, "symbol_info")
        self.assertIn("name", response.data)
        self.assertEqual(response.data["name"], "BTCUSD")

    @patch("mt5_mcp.handlers.safe_mt5_call")
    def test_query_copy_rates(self, mock_safe_call):
        """Test querying historical rates."""
        from mt5_mcp.handlers import handle_mt5_query
        from mt5_mcp.models import MT5QueryRequest, MT5Operation

        # Mock rates data
        mock_rates = np.array(
            [(1234567890, 1.1, 1.2, 1.0, 1.15, 100, 50, 1)],
            dtype=[
                ("time", "i8"),
                ("open", "f8"),
                ("high", "f8"),
                ("low", "f8"),
                ("close", "f8"),
                ("tick_volume", "i8"),
                ("spread", "i4"),
                ("real_volume", "i8"),
            ],
        )
        mock_safe_call.return_value = mock_rates

        # Create request
        request = MT5QueryRequest(
            operation=MT5Operation.COPY_RATES_FROM_POS,
            symbol="EURUSD",
            parameters={"timeframe": "H1", "start_pos": 0, "count": 100},
        )

        # Execute
        response = handle_mt5_query(request)

        # Verify
        self.assertTrue(response.success)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertIn("time", response.data[0])
        self.assertIn("close", response.data[0])

    @patch("mt5_mcp.handlers.safe_mt5_call")
    def test_query_account_info(self, mock_safe_call):
        """Test querying account information."""
        from mt5_mcp.handlers import handle_mt5_query
        from mt5_mcp.models import MT5QueryRequest, MT5Operation

        # Mock account info
        mock_account = Mock()
        mock_account._asdict.return_value = {
            "login": 12345,
            "balance": 10000.0,
            "equity": 10500.0,
        }
        mock_safe_call.return_value = mock_account

        # Create request
        request = MT5QueryRequest(operation=MT5Operation.ACCOUNT_INFO)

        # Execute
        response = handle_mt5_query(request)

        # Verify
        self.assertTrue(response.success)
        self.assertIn("balance", response.data)


class TestHandleMT5Analysis(unittest.TestCase):
    """Test handle_mt5_analysis function."""

    @patch("mt5_mcp.handlers.handle_mt5_query")
    def test_basic_analysis(self, mock_query):
        """Test basic analysis without indicators or charts."""
        from mt5_mcp.handlers import handle_mt5_analysis
        from mt5_mcp.models import (
            MT5AnalysisRequest,
            MT5QueryRequest,
            MT5Operation,
            MT5QueryResponse,
        )

        # Mock query response with OHLCV data
        mock_data = [
            {
                "time": 1234567890 + i,
                "open": 1.1 + i * 0.01,
                "high": 1.2 + i * 0.01,
                "low": 1.0 + i * 0.01,
                "close": 1.15 + i * 0.01,
                "tick_volume": 100,
            }
            for i in range(50)
        ]
        mock_query.return_value = MT5QueryResponse(
            success=True, operation="copy_rates_from_pos", data=mock_data, metadata={}
        )

        # Create request
        query_req = MT5QueryRequest(
            operation=MT5Operation.COPY_RATES_FROM_POS,
            symbol="BTCUSD",
            parameters={"timeframe": "H1", "count": 50},
        )
        request = MT5AnalysisRequest(query=query_req, output_format="json")

        # Execute
        response = handle_mt5_analysis(request)

        # Verify
        self.assertTrue(response.success)
        self.assertIsNotNone(response.data)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 50)

    @patch("mt5_mcp.handlers.handle_mt5_query")
    def test_analysis_with_indicators(self, mock_query):
        """Test analysis with technical indicators."""
        from mt5_mcp.handlers import handle_mt5_analysis
        from mt5_mcp.models import (
            MT5AnalysisRequest,
            MT5QueryRequest,
            MT5Operation,
            MT5QueryResponse,
            IndicatorSpec,
        )

        # Mock query response
        mock_data = [
            {
                "time": 1234567890 + i,
                "close": 50000.0 + i * 100,
                "high": 50100.0 + i * 100,
                "low": 49900.0 + i * 100,
                "open": 50000.0 + i * 100,
                "tick_volume": 100,
            }
            for i in range(100)
        ]
        mock_query.return_value = MT5QueryResponse(
            success=True, operation="copy_rates_from_pos", data=mock_data, metadata={}
        )

        # Create request with RSI indicator
        query_req = MT5QueryRequest(
            operation=MT5Operation.COPY_RATES_FROM_POS,
            symbol="BTCUSD",
            parameters={"timeframe": "H1", "count": 100},
        )
        request = MT5AnalysisRequest(
            query=query_req,
            indicators=[IndicatorSpec(function="ta.momentum.rsi", params={"window": 14})],
            output_format="json",
            tail=10,
        )

        # Execute
        response = handle_mt5_analysis(request)

        # Verify
        self.assertTrue(response.success)
        self.assertEqual(len(response.indicators_calculated), 1)
        self.assertIn("rsi", response.indicators_calculated[0].lower())
        self.assertIn("analysis_summary", response.metadata)


class TestAnalysisSummary(unittest.TestCase):
    """Test analysis summary generation."""

    def test_price_action_analysis(self):
        """Test price action analysis."""
        from mt5_mcp.handlers import _generate_analysis_summary

        # Create sample data
        df = pd.DataFrame(
            {
                "time": pd.date_range("2024-01-01", periods=100, freq="H"),
                "close": np.linspace(50000, 55000, 100),
                "high": np.linspace(50100, 55100, 100),
                "low": np.linspace(49900, 54900, 100),
            }
        )

        summary = _generate_analysis_summary(df, "BTCUSD", [])

        # Verify structure
        self.assertIn("symbol", summary)
        self.assertIn("period", summary)
        self.assertIn("data_characteristics", summary)
        self.assertIn("price", summary["data_characteristics"])
        self.assertIn("pattern_detection", summary)
        self.assertIn("trend", summary["pattern_detection"])

        # Verify trend detection (upward trend)
        trend = summary["pattern_detection"]["trend"]
        self.assertEqual(trend["direction"], "bullish")


if __name__ == "__main__":
    unittest.main()
