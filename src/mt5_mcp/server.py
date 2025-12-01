""">
MCP Server for MetaTrader 5 integration.
Provides read-only access to MT5 market data via Python commands.
"""

import logging
import argparse
from pathlib import Path
from urllib.parse import quote
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from .connection import get_safe_namespace, validate_connection
from .executor import execute_command
from .models import MT5QueryRequest, MT5AnalysisRequest, ErrorResponse
from .handlers import handle_mt5_query, handle_mt5_analysis
from .errors import MT5Error
from pydantic import ValidationError
import json

# Configure logging
logger = logging.getLogger(__name__)


def _format_file_hyperlink(file_path: str) -> str:
    """Format file path as clickable file:// hyperlink.

    Args:
        file_path: Absolute path to file

    Returns:
        Markdown-formatted hyperlink: [filename](file:///path/to/file)
    """
    abs_path = Path(file_path).absolute()
    # Convert backslashes to forward slashes for file:// URLs
    url_path = str(abs_path).replace("\\", "/")
    # Encode spaces and special chars
    encoded_path = quote(url_path, safe="/:")
    filename = abs_path.name
    return f"[{filename}](file:///{encoded_path})"


def setup_logging(log_file: str = None):
    """
    Setup logging configuration.

    Args:
        log_file: Optional path to log file. If None, logging is disabled.
    """
    if log_file:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
            ],
        )
        logger.info(f"Logging enabled to {log_file}")
    else:
        # Disable logging to avoid interfering with stdio
        logging.basicConfig(level=logging.CRITICAL)


# Create MCP server instance
app = Server("metatrader5-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available MCP tools.

    Returns:
        List of tool definitions
    """
    return [
        Tool(
            name="execute_mt5",
            description=(
                "⚠️ FALLBACK TOOL - Use mt5_analyze or mt5_query first\n"
                "Execute raw Python code against MT5 when structured tools "
                "don't fit your needs.\n\n"
                "WHEN TO USE THIS:\n"
                "• Custom calculations not covered by mt5_analyze\n"
                "• Complex data transformations\n"
                "• Advanced plotting/visualization\n"
                "• Debugging or exploration\n\n"
                "CRITICAL RULES:\n"
                "❌ NEVER call mt5.initialize() or mt5.shutdown() - connection is pre-managed\n"
                "✅ MT5 is ALREADY connected - start with mt5.copy_rates_from_pos(...)\n"
                "✅ ALWAYS assign final output to 'result' variable\n\n"
                "Available: mt5, pd/pandas, np/numpy, plt/matplotlib, "
                "ta (indicators), datetime\n"
                "Timeframes: mt5.TIMEFRAME_M1, M5, M15, M30, H1, H4, D1, W1, "
                "MN1\n\n"
                "Example:\n"
                "rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "df = pd.DataFrame(rates)\n"
                "df['custom_indicator'] = (df['high'] - df['low']) / df['close']\n"
                "result = df[['time', 'close', 'custom_indicator']].tail(10)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "Python code to execute against MT5. Must be valid Python syntax.\n\n"
                            "⚠️ CRITICAL RULES:\n"
                            "1. NEVER call mt5.initialize() or mt5.shutdown()\n"
                            "2. ALWAYS assign final output to 'result' variable\n"
                            "3. Start directly with mt5.copy_rates_from_pos() or "
                            "mt5.symbol_info()\n\n"
                            "CORRECT examples:\n"
                            "• result = mt5.symbol_info('EURUSD')._asdict()\n"
                            "• result = mt5.copy_rates_from_pos('BTCUSD', "
                            "mt5.TIMEFRAME_H1, 0, 24)\n"
                            "• rates = mt5.copy_rates_from_pos('BTCUSD', "
                            "mt5.TIMEFRAME_H1, 0, 100)\n"
                            "  df = pd.DataFrame(rates)\n"
                            "  df['RSI'] = ta.momentum.rsi(df['close'], 14)\n"
                            "  result = df[['close', 'RSI']].tail(10)\n\n"
                            "INCORRECT - DON'T do this:\n"
                            "• mt5.initialize()  # ❌ CONNECTION ALREADY INITIALIZED!\n"
                            "• mt5.symbol_info('BTCUSD')  # ❌ Missing 'result =' assignment\n"
                            "• mt5.order_send(...)  # ❌ Trading functions blocked"
                        ),
                    },
                    "show_traceback": {
                        "type": "boolean",
                        "description": "Show full Python traceback on errors (default: true)",
                        "default": True,
                    },
                },
                "required": ["command"],
            },
        ),
        # NEW UNIVERSAL TOOLS - Structured Input System
        Tool(
            name="mt5_query",
            description=(
                "Query MT5 data with structured JSON parameters (no Python code needed).\n"
                "Use this for simple data queries. For analysis with "
                "indicators/charts/forecasts, use mt5_analyze.\n\n"
                "Operations: copy_rates_from_pos, copy_rates_from, copy_rates_range, "
                "symbol_info, symbol_info_tick, symbols_get, account_info, terminal_info, "
                "order_calc_profit\n\n"
                "Examples:\n"
                '{"operation": "copy_rates_from_pos", "symbol": "BTCUSD", '
                '"parameters": {"timeframe": "H1", "count": 100}}\n'
                '{"operation": "symbol_info", "symbol": "EURUSD"}\n'
                '{"operation": "symbols_get", "parameters": {"group": "*USD*"}}\n\n'
                "Timeframes: M1,M5,M15,M30,H1,H4,D1,W1,MN1 | Auto-validation with "
                "helpful error suggestions"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "copy_rates_from",
                            "copy_rates_from_pos",
                            "copy_rates_range",
                            "copy_ticks_from",
                            "copy_ticks_range",
                            "symbol_info",
                            "symbol_info_tick",
                            "symbol_select",
                            "symbols_total",
                            "symbols_get",
                            "account_info",
                            "terminal_info",
                            "version",
                            "order_calc_margin",
                            "order_calc_profit",
                        ],
                        "description": "MT5 operation to execute",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (required for symbol-specific operations)",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters",
                        "additionalProperties": True,
                    },
                },
                "required": ["operation"],
            },
        ),
        Tool(
            name="mt5_analyze",
            description=(
                "MT5 analysis with data query + technical indicators + charts + Prop"
                "het forecasting + XGBoost ML signals.\n\n"
                "KEY FEATURES:\n"
                "• Prophet time-series forecasting: predict future prices with "
                "confidence intervals\n"
                "• XGBoost ML signals: AI-powered BUY/SELL/HOLD recommendations "
                "with confidence scores\n"
                "• 80+ technical indicators from ta library (RSI, MACD, Bollinger, "
                "ATR, etc.)\n"
                "• Multi-panel charts saved to cwd with clickable file:// links\n\n"
                "PROPHET FORECAST - Add 'forecast' parameter:\n"
                '{"query": {...}, "forecast": {"periods": 24, "plot": true}}\n'
                "Returns: predicted prices, confidence intervals, trend analysis, "
                "forecast chart\n\n"
                "XGBOOST ML SIGNAL - Enable ML prediction in forecast:\n"
                '{"query": {...}, "forecast": {"periods": 24, "enable_ml_prediction": true, '
                '"ml_lookback": 50}}\n'
                "Returns ml_trading_signal with:\n"
                "  - signal: BUY/SELL/HOLD\n"
                "  - confidence: 0-100%\n"
                "  - buy_probability, sell_probability\n"
                "  - reasoning: explanation\n"
                "  - features_used: indicators driving the signal\n"
                "  - training_samples: bars used\n\n"
                "COMPLETE EXAMPLE (all features):\n"
                "{\n"
                '  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", '
                '"parameters": {"timeframe": "H1", "count": 168}},\n'
                '  "indicators": [{"function": "ta.momentum.rsi", "params": {"window": 14}}],\n'
                '  "chart": {"type": "multi", "panels": [{"columns": ["close"]}, '
                '{"columns": ["rsi"]}]},\n'
                '  "forecast": {"periods": 24, "enable_ml_prediction": true, "plot": true}\n'
                "}\n\n"
                "PARAMS:\n"
                "• query: MT5 data query (required)\n"
                "• indicators: array of {function: 'ta.momentum.rsi', params: {window: 14}}\n"
                "• chart: {type: 'multi', panels: [...], filename: 'chart.png'}\n"
                "• forecast: {periods: 1-365, enable_ml_prediction: bool, ml_lookback: "
                "20-200, plot: bool}\n"
                "• output_format: 'markdown'|'json'|'chart_only'\n"
                "• tail: return last N rows\n\n"
                "Timeframes: M1,M5,M15,M30,H1,H4,D1,W1,MN1 | Requires ≥30 bars for "
                "forecast (100+ recommended)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "object",
                        "description": "MT5 data query (same as mt5_query tool)",
                        "properties": {
                            "operation": {"type": "string"},
                            "symbol": {"type": "string"},
                            "parameters": {"type": "object"},
                        },
                        "required": ["operation"],
                    },
                    "indicators": {
                        "type": "array",
                        "description": "Technical indicators to calculate",
                        "items": {
                            "type": "object",
                            "properties": {
                                "function": {
                                    "type": "string",
                                    "description": "TA-Lib function path (e.g., 'ta.momentum.rsi')",
                                },
                                "params": {
                                    "type": "object",
                                    "description": "Indicator parameters",
                                },
                            },
                            "required": ["function"],
                        },
                    },
                    "chart": {
                        "type": "object",
                        "description": "Chart configuration",
                        "properties": {
                            "type": {"type": "string", "enum": ["single", "multi"]},
                            "panels": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "columns": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "style": {"type": "string"},
                                        "reference_lines": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                        },
                                    },
                                },
                            },
                            "filename": {"type": "string"},
                        },
                    },
                    "forecast": {
                        "type": "object",
                        "description": (
                            "Prophet forecast configuration with optional XGBoost ML "
                            "trading signal"
                        ),
                        "properties": {
                            "periods": {
                                "type": "integer",
                                "description": "Number of periods to forecast (1-365)",
                                "minimum": 1,
                                "maximum": 365,
                            },
                            "include_history": {
                                "type": "boolean",
                                "description": "Include historical fitted values",
                            },
                            "freq": {
                                "type": "string",
                                "description": (
                                    "Forecast frequency: 'D' (daily), 'h' (hourly), 'min' "
                                    "(minutely)"
                                ),
                            },
                            "uncertainty_samples": {
                                "type": "integer",
                                "description": "Samples for uncertainty intervals (0-10000)",
                                "minimum": 0,
                                "maximum": 10000,
                            },
                            "seasonality_mode": {
                                "type": "string",
                                "enum": ["additive", "multiplicative"],
                                "description": "Seasonality mode",
                            },
                            "growth": {
                                "type": "string",
                                "enum": ["linear", "logistic"],
                                "description": "Growth model",
                            },
                            "plot": {
                                "type": "boolean",
                                "description": "Generate forecast chart",
                            },
                            "plot_components": {
                                "type": "boolean",
                                "description": "Generate components plot",
                            },
                            "enable_ml_prediction": {
                                "type": "boolean",
                                "description": (
                                    "Enable XGBoost ML model for buy/sell signal prediction"
                                ),
                            },
                            "ml_lookback": {
                                "type": "integer",
                                "description": "Number of bars for ML feature engineering (20-200)",
                                "minimum": 20,
                                "maximum": 200,
                            },
                        },
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "json", "chart_only"],
                        "default": "markdown",
                    },
                    "tail": {
                        "type": "integer",
                        "description": "Return only last N rows",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


async def handle_mt5_query_tool(arguments: dict) -> list[TextContent]:
    """Handle mt5_query tool execution."""
    try:
        # Validate and parse request
        request = MT5QueryRequest(**arguments)

        # Execute query
        response = handle_mt5_query(request)

        # Format response
        result_text = json.dumps(response.model_dump(), indent=2, default=str)
        return [TextContent(type="text", text=result_text)]

    except ValidationError as e:
        # Pydantic validation error
        error_details = e.errors()
        error_text = "Validation Error:\n\n"
        for err in error_details:
            field = " -> ".join(str(x) for x in err["loc"])
            error_text += f"• {field}: {err['msg']}\n"

        # Add suggestion
        error_text += (
            '\nExample: {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", '
            '"parameters": {"timeframe": "H1", "start_pos": 0, "count": 100}}'
        )

        if logger.level <= logging.INFO:
            logger.error(f"Validation error: {error_details}")

        return [TextContent(type="text", text=error_text)]

    except MT5Error as e:
        # Custom MT5 error with suggestions
        error_response = ErrorResponse(**e.to_dict())
        result_text = json.dumps(error_response.model_dump(exclude_none=True), indent=2)

        if logger.level <= logging.INFO:
            logger.error(f"MT5 Error: {e.message}")

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        # Unexpected error
        error_text = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error in mt5_query: {e}", exc_info=True)
        return [TextContent(type="text", text=error_text)]


async def handle_mt5_analyze_tool(arguments: dict) -> list[TextContent]:
    """Handle mt5_analyze tool execution."""
    try:
        # Validate and parse request
        request = MT5AnalysisRequest(**arguments)

        # Execute analysis
        response = handle_mt5_analysis(request)

        # Format response with clickable chart links
        result_dict = response.model_dump()
        result_text = json.dumps(result_dict, indent=2, default=str)

        # Add clickable hyperlinks for charts if they exist
        chart_links = []
        if response.chart_path:
            chart_links.append(f"📊 Chart: {_format_file_hyperlink(response.chart_path)}")
        if response.forecast_chart_path:
            chart_links.append(
                f"🔮 Forecast: {_format_file_hyperlink(response.forecast_chart_path)}"
            )

        if chart_links:
            result_text += "\n\n---\n### 📁 Generated Files\n" + "\n".join(chart_links)

        return [TextContent(type="text", text=result_text)]

    except ValidationError as e:
        # Pydantic validation error
        error_details = e.errors()
        error_text = "Validation Error:\n\n"
        for err in error_details:
            field = " -> ".join(str(x) for x in err["loc"])
            error_text += f"• {field}: {err['msg']}\n"

        # Add example
        error_text += (
            '\n\nExample:\n{\n  "query": {"operation": "copy_rates_from_pos", "symbol": '
            '"BTCUSD", "parameters": {"timeframe": "D1", "count": 30}},\n  '
            '"indicators": [{"function": "ta.momentum.rsi", "params": {"window": 14}}],\n  '
            '"output_format": "markdown"\n}'
        )

        if logger.level <= logging.INFO:
            logger.error(f"Validation error: {error_details}")

        return [TextContent(type="text", text=error_text)]

    except MT5Error as e:
        # Custom MT5 error with suggestions
        error_response = ErrorResponse(**e.to_dict())
        result_text = json.dumps(error_response.model_dump(exclude_none=True), indent=2)

        if logger.level <= logging.INFO:
            logger.error(f"MT5 Error: {e.message}")

        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        # Unexpected error
        error_text = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error in mt5_analyze: {e}", exc_info=True)
        return [TextContent(type="text", text=error_text)]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle tool execution requests.

    Args:
        name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        List of text content responses
    """
    # Handle new universal tools
    if name == "mt5_query":
        return await handle_mt5_query_tool(arguments)
    if name == "mt5_analyze":
        return await handle_mt5_analyze_tool(arguments)
    if name != "execute_mt5":
        raise ValueError(f"Unknown tool: {name}")

    command = arguments.get("command")
    show_traceback = arguments.get("show_traceback", True)

    if not command:
        return [TextContent(type="text", text="Error: 'command' parameter is required")]

    # CRITICAL: Block mt5.initialize() and mt5.shutdown() calls
    forbidden_patterns = [
        ("mt5.initialize(", "mt5.initialize()"),
        ("mt5.shutdown(", "mt5.shutdown()"),
        ("MetaTrader5.initialize(", "MetaTrader5.initialize()"),
        ("MetaTrader5.shutdown(", "MetaTrader5.shutdown()"),
    ]

    for pattern, function_name in forbidden_patterns:
        if pattern in command:
            error_msg = (
                f"🚨 ERROR: Cannot call {function_name} 🚨\n\n"
                f"The MT5 connection is ALREADY INITIALIZED by the MCP server.\n"
                f"These functions don't exist in the safe namespace.\n\n"
                f"❌ Your code tried to call: {function_name}\n"
                f"✅ Correct approach: Start directly with mt5.copy_rates_from_pos(...)\n\n"
                f"Example:\n"
                f"rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                f"df = pd.DataFrame(rates)\n"
                f"result = df[['time', 'close']].tail(10)\n\n"
                f"The connection is ALWAYS ready - just use it!"
            )
            logger.warning(f"Blocked forbidden function call: {function_name}")
            return [TextContent(type="text", text=error_msg)]

    # Check if result variable is assigned (warn but don't block)
    if "result" not in command and "plt.savefig" not in command:
        logger.warning("Command may not assign to 'result' variable - output may be lost")

    # Validate command format to help LLMs
    command_stripped = command.strip()
    if (
        command_stripped
        and not command_stripped.startswith("mt5.")
        and "mt5." not in command_stripped
    ):
        warning_msg = (
            f"⚠️ WARNING: Command may be incorrect - missing 'mt5.' prefix.\n\n"
            f"Your command: {command[:200]}\n\n"
            f"Did you mean one of these?\n"
            f"• mt5.symbol_info('{command.strip()}')\n"
            f"• mt5.{command}\n\n"
            f"Available objects: mt5, pd, pandas, datetime\n"
            f"Example: mt5.symbol_info('BTCUSD')._asdict()"
        )
        logger.warning(f"Invalid command format: {command[:100]}")
        return [TextContent(type="text", text=warning_msg)]

    logger.info(f"Received command: {command[:100]}...")

    # Validate MT5 connection
    connection_status = validate_connection()
    if not connection_status["connected"]:
        error_msg = f"MT5 connection error: {connection_status['error']}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    # Get safe namespace
    namespace = get_safe_namespace()

    # Execute command
    result = execute_command(command, namespace, show_traceback)

    return [TextContent(type="text", text=result)]


async def main():
    """
    Main entry point for the MCP server.
    """
    parser = argparse.ArgumentParser(description="MetaTrader 5 MCP Server")
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file for troubleshooting (disabled by default)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_file)

    logger.info("Starting MetaTrader 5 MCP Server...")

    # Initialize MT5 connection (import here to trigger initialization)
    from .connection import get_connection

    try:
        get_connection()
        logger.info("MT5 connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MT5 connection: {e}")
        raise

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Server initialized, waiting for requests...")
        init_options = InitializationOptions(
            server_name="metatrader5-mcp",
            server_version="0.4.0",
            capabilities=app.get_capabilities(
                notification_options=NotificationOptions(), experimental_capabilities={}
            ),
        )
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
