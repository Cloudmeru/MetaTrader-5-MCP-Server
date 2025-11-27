"""
MCP Server for MetaTrader 5 integration.
Provides read-only access to MT5 market data via Python commands.
"""
import logging
import argparse
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


def setup_logging(log_file: str = None):
    """
    Setup logging configuration.
    
    Args:
        log_file: Optional path to log file. If None, logging is disabled.
    """
    if log_file:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
            ]
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
                "🚨 STOP! READ THIS FIRST 🚨\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "❌ NEVER CALL mt5.initialize() - IT WILL FAIL!\n"
                "❌ NEVER CALL mt5.shutdown() - IT WILL FAIL!\n"
                "✅ MT5 is ALREADY connected and ready to use\n"
                "✅ Start directly with: mt5.copy_rates_from_pos(...)\n"
                "✅ ALWAYS assign final output to 'result' variable\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                "Execute Python commands to query MetaTrader 5 market data (read-only access).\n\n"
                
                "=== DO'S ===\n"
                "✓ DO use this tool for ALL MT5 queries\n"
                "✓ DO call mt5.symbol_info('SYMBOL')._asdict() for symbol details\n"
                "✓ DO use mt5.copy_rates_from_pos() for historical price data\n"
                "✓ DO use mt5.copy_rates_range() for date-based queries\n"
                "✓ DO use mt5.order_calc_profit() for profit calculations\n"
                "✓ DO use mt5.TIMEFRAME_M1, M5, M15, M30, H1, H4, D1, W1, MN1\n"
                "✓ DO assign final result to 'result' variable for clean output\n"
                "✓ DO use ._asdict() on NamedTuple objects for readable output\n\n"
                
                "=== DON'TS ===\n"
                "✗ NEVER call mt5.initialize() or mt5.shutdown() - connection is pre-managed!\n"
                "✗ DON'T send raw code without wrapping in this tool\n"
                "✗ DON'T use trading functions (order_send, positions_modify, etc.)\n"
                "✗ DON'T forget quotes around symbol names: 'BTCUSD' not BTCUSD\n"
                "✗ DON'T use undefined variables - all data must come from MT5\n"
                "✗ DON'T assume timeframe names - always use mt5.TIMEFRAME_X format\n\n"
                
                "=== COMMON QUERIES ===\n"
                "1. Symbol info (assign to result!):\n"
                "   result = mt5.symbol_info('BTCUSD')._asdict()\n\n"
                
                "2. Latest price (assign to result!):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_M1, 0, 1)\n"
                "   result = rates[0] if rates is not None else None\n\n"
                
                "3. Historical data (assign to result!):\n"
                "   result = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_M15, 0, 100)\n\n"
                
                "4. Profit calculation (assign to result!):\n"
                "   result = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, 'BTCUSD', 0.02, 70000.0, 71000.0)\n\n"
                
                "5. Account info (assign to result!):\n"
                "   result = mt5.account_info()._asdict()\n\n"
                
                "6. List all symbols:\n"
                "   result = [s.name for s in mt5.symbols_get()]\n\n"
                
                "=== TECHNICAL ANALYSIS & PLOTTING ===\n"
                "7. Moving Average analysis (DataFrame output):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['SMA_20'] = df['close'].rolling(20).mean()\n"
                "   df['EMA_50'] = df['close'].ewm(span=50).mean()\n"
                "   result = df[['time', 'close', 'SMA_20', 'EMA_50']].tail(10)\n\n"
                
                "8. RSI indicator (technical analysis):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['RSI'] = ta.momentum.rsi(df['close'], window=14)\n"
                "   result = df[['time', 'close', 'RSI']].tail(20)\n\n"
                
                "9. MACD indicator (technical analysis):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['MACD'] = ta.trend.macd_diff(df['close'])\n"
                "   result = df[['time', 'close', 'MACD']].tail(20)\n\n"
                
                "10. Bollinger Bands (technical analysis):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['BB_upper'] = ta.volatility.bollinger_hband(df['close'], window=20)\n"
                "   df['BB_lower'] = ta.volatility.bollinger_lband(df['close'], window=20)\n"
                "   result = df[['time', 'close', 'BB_upper', 'BB_lower']].tail(10)\n\n"
                
                "11. Plot price chart with indicators (MUST assign result!):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['SMA_20'] = df['close'].rolling(20).mean()\n"
                "   plt.figure(figsize=(12, 6))\n"
                "   plt.plot(df.index, df['close'], label='Close', linewidth=2)\n"
                "   plt.plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--')\n"
                "   plt.title('BTCUSD Price Chart')\n"
                "   plt.xlabel('Time')\n"
                "   plt.ylabel('Price')\n"
                "   plt.legend()\n"
                "   plt.grid(True, alpha=0.3)\n"
                "   plt.savefig('btcusd_chart.png', dpi=100, bbox_inches='tight')\n"
                "   plt.close()\n"
                "   result = '📊 Chart saved to: btcusd_chart.png'\n\n"
                
                "12. Multi-panel chart (Price + RSI) (MUST assign result!):\n"
                "   rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                "   df = pd.DataFrame(rates)\n"
                "   df['RSI'] = ta.momentum.rsi(df['close'], window=14)\n"
                "   fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)\n"
                "   ax1.plot(df.index, df['close'])\n"
                "   ax1.set_title('BTCUSD Price')\n"
                "   ax1.grid(True, alpha=0.3)\n"
                "   ax2.plot(df.index, df['RSI'], color='orange')\n"
                "   ax2.axhline(70, color='r', linestyle='--', alpha=0.5)\n"
                "   ax2.axhline(30, color='g', linestyle='--', alpha=0.5)\n"
                "   ax2.set_title('RSI(14)')\n"
                "   ax2.set_ylim(0, 100)\n"
                "   ax2.grid(True, alpha=0.3)\n"
                "   plt.savefig('btcusd_analysis.png', dpi=100, bbox_inches='tight')\n"
                "   plt.close()\n"
                "   result = '📊 Analysis chart saved to: btcusd_analysis.png'\n\n"
                
                "=== AVAILABLE LIBRARIES ===\n"
                "- mt5: MetaTrader5 module (all read-only functions)\n"
                "- pd/pandas: DataFrame operations and data manipulation\n"
                "- np/numpy: Numerical operations\n"
                "- plt/matplotlib: Chart plotting and visualization\n"
                "- ta: Technical analysis indicators (RSI, MACD, Bollinger, SMA, EMA, etc.)\n"
                "- datetime: Date/time handling\n\n"
                
                "=== TIMEFRAME CONSTANTS ===\n"
                "mt5.TIMEFRAME_M1 (1 min), M5, M15, M30, H1, H4, D1 (daily), W1 (weekly), MN1 (monthly)\n\n"
                
                "=== ORDER TYPES (for calc functions) ===\n"
                "mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL\n\n"
                
                "=== PLOTTING TIPS ===\n"
                "• Always use plt.savefig() to save charts\n"
                "• Use plt.close() after saving to free memory\n"
                "• Set figsize=(12, 6) for good readability\n"
                "• Use dpi=100 for decent quality\n"
                "• Return the filename in result variable"
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
                            "3. Start directly with mt5.copy_rates_from_pos() or mt5.symbol_info()\n\n"
                            "CORRECT examples:\n"
                            "• result = mt5.symbol_info('EURUSD')._asdict()\n"
                            "• result = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 24)\n"
                            "• rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)\n"
                            "  df = pd.DataFrame(rates)\n"
                            "  df['RSI'] = ta.momentum.rsi(df['close'], 14)\n"
                            "  result = df[['close', 'RSI']].tail(10)\n\n"
                            "INCORRECT - DON'T do this:\n"
                            "• mt5.initialize()  # ❌ CONNECTION ALREADY INITIALIZED!\n"
                            "• mt5.symbol_info('BTCUSD')  # ❌ Missing 'result =' assignment\n"
                            "• mt5.order_send(...)  # ❌ Trading functions blocked"
                        )
                    },
                    "show_traceback": {
                        "type": "boolean",
                        "description": "Show full Python traceback on errors (default: true)",
                        "default": True
                    }
                },
                "required": ["command"]
            }
        ),
        # NEW UNIVERSAL TOOLS - Structured Input System
        Tool(
            name="mt5_query",
            description=(
                "⚠️ DEPRECATED WARNING for execute_mt5 users ⚠️\n"
                "This is the NEW recommended way to query MT5 data with structured inputs.\n"
                "Provides better validation, error messages, and LLM compatibility.\n\n"
                
                "Execute any MT5 read-only operation with structured, validated parameters.\n"
                "No Python code needed - just specify operation and parameters as JSON.\n\n"
                
                "Available operations:\n"
                "• copy_rates_from_pos - Get N bars from position\n"
                "• copy_rates_from - Get bars from datetime\n"
                "• copy_rates_range - Get bars in date range\n"
                "• symbol_info - Get symbol specifications\n"
                "• symbol_info_tick - Get latest tick\n"
                "• symbols_get - List available symbols\n"
                "• account_info - Get account details\n"
                "• terminal_info - Get terminal info\n"
                "• order_calc_profit - Calculate theoretical profit\n\n"
                
                "Examples:\n"
                "1. Get 100 hourly bars for BTCUSD:\n"
                '   {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "H1", "start_pos": 0, "count": 100}}\n\n'
                
                "2. Get symbol info:\n"
                '   {"operation": "symbol_info", "symbol": "EURUSD"}\n\n'
                
                "3. List all USD pairs:\n"
                '   {"operation": "symbols_get", "parameters": {"group": "*USD*"}}\n\n'
                
                "Timeframes: M1, M5, M15, M30, H1, H4, D1, W1, MN1\n"
                "Automatic validation: symbol existence, timeframe, parameter types\n"
                "Helpful errors: suggestions for corrections, similar symbols"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["copy_rates_from", "copy_rates_from_pos", "copy_rates_range", 
                                "copy_ticks_from", "copy_ticks_range", "symbol_info", 
                                "symbol_info_tick", "symbol_select", "symbols_total", 
                                "symbols_get", "account_info", "terminal_info", "version",
                                "order_calc_margin", "order_calc_profit"],
                        "description": "MT5 operation to execute"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (required for symbol-specific operations)"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters",
                        "additionalProperties": True
                    }
                },
                "required": ["operation"]
            }
        ),
        Tool(
            name="mt5_analyze",
            description=(
                "⚠️ RECOMMENDED TOOL for analysis tasks ⚠️\n"
                "Query MT5 data + calculate indicators + generate charts in ONE request.\n"
                "Supports ALL TA-Lib indicators with automatic validation.\n\n"
                
                "Workflow: Query data → Calculate indicators → Generate chart\n\n"
                
                "Available TA indicators (use full path):\n"
                "• ta.momentum.rsi - RSI indicator\n"
                "• ta.trend.sma_indicator - Simple Moving Average\n"
                "• ta.trend.ema_indicator - Exponential Moving Average\n"
                "• ta.trend.macd - MACD indicator\n"
                "• ta.volatility.bollinger_hband - Bollinger Upper Band\n"
                "• ta.volatility.bollinger_lband - Bollinger Lower Band\n"
                "• ta.volatility.average_true_range - ATR\n"
                "• And 80+ more indicators from ta library!\n\n"
                
                "Example: BTCUSD trend with RSI:\n"
                '{\n'
                '  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "D1", "count": 30}},\n'
                '  "indicators": [{"function": "ta.momentum.rsi", "params": {"window": 14}}, {"function": "ta.trend.sma_indicator", "params": {"window": 20}}],\n'
                '  "chart": {"type": "multi", "panels": [{"columns": ["close", "sma_indicator_20"]}, {"columns": ["rsi"], "reference_lines": [30, 70]}], "filename": "btcusd_trend.png"},\n'
                '  "output_format": "chart_only"\n'
                '}\n\n'
                
                "Output formats: 'markdown' (table), 'json' (array), 'chart_only' (just image)\n"
                "Automatic validation: sufficient data for indicators, column existence\n"
                "Multi-panel charts: separate panels for price and indicators"
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
                            "parameters": {"type": "object"}
                        },
                        "required": ["operation"]
                    },
                    "indicators": {
                        "type": "array",
                        "description": "Technical indicators to calculate",
                        "items": {
                            "type": "object",
                            "properties": {
                                "function": {"type": "string", "description": "TA-Lib function path (e.g., 'ta.momentum.rsi')"},
                                "params": {"type": "object", "description": "Indicator parameters"}
                            },
                            "required": ["function"]
                        }
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
                                        "columns": {"type": "array", "items": {"type": "string"}},
                                        "style": {"type": "string"},
                                        "reference_lines": {"type": "array", "items": {"type": "number"}}
                                    }
                                }
                            },
                            "filename": {"type": "string"}
                        }
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "json", "chart_only"],
                        "default": "markdown"
                    },
                    "tail": {"type": "integer", "description": "Return only last N rows"}
                },
                "required": ["query"]
            }
        )
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
            field = " -> ".join(str(x) for x in err['loc'])
            error_text += f"• {field}: {err['msg']}\n"
        
        # Add suggestion
        error_text += "\nExample: {\"operation\": \"copy_rates_from_pos\", \"symbol\": \"BTCUSD\", \"parameters\": {\"timeframe\": \"H1\", \"start_pos\": 0, \"count\": 100}}"
        
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
        
        # Format response
        result_text = json.dumps(response.model_dump(), indent=2, default=str)
        return [TextContent(type="text", text=result_text)]
        
    except ValidationError as e:
        # Pydantic validation error
        error_details = e.errors()
        error_text = "Validation Error:\n\n"
        for err in error_details:
            field = " -> ".join(str(x) for x in err['loc'])
            error_text += f"• {field}: {err['msg']}\n"
        
        # Add example
        error_text += '\n\nExample:\n{\n  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "D1", "count": 30}},\n  "indicators": [{"function": "ta.momentum.rsi", "params": {"window": 14}}],\n  "output_format": "markdown"\n}'
        
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
    elif name == "mt5_analyze":
        return await handle_mt5_analyze_tool(arguments)
    elif name != "execute_mt5":
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
    if command_stripped and not command_stripped.startswith("mt5.") and "mt5." not in command_stripped:
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
        help="Path to log file for troubleshooting (disabled by default)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_file)
    
    logger.info("Starting MetaTrader 5 MCP Server...")
    
    # Initialize MT5 connection (import here to trigger initialization)
    from .connection import get_connection
    try:
        conn = get_connection()
        logger.info("MT5 connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MT5 connection: {e}")
        raise
    
    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Server initialized, waiting for requests...")
        init_options = InitializationOptions(
            server_name="metatrader5-mcp",
            server_version="0.3.0",
            capabilities=app.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        await app.run(
            read_stream,
            write_stream,
            init_options
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
