"""Gradio MCP Server with HTTP/SSE support and rate limiting."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import gradio as gr

from .handlers import handle_mt5_query, handle_mt5_analysis
from .executor import execute_command
from .connection import get_safe_namespace, get_connection, safe_mt5_call
from .error_utils import (
    ErrorType,
    create_error_response,
    safe_json_parse,
    safe_enum_conversion,
    format_json_response,
)
from .models import (
    MT5QueryRequest,
    MT5AnalysisRequest,
    MT5Operation,
    IndicatorSpec,
    ChartConfig,
    ForecastConfig,
)

logger = logging.getLogger(__name__)

# Rate limiting configuration (requests per minute per IP)
HTTP_RATE_LIMIT = 10  # Default: 10 requests per minute
_rate_limit_store = defaultdict(list)


def set_rate_limit(limit: int):
    """Set HTTP rate limit (requests per minute per IP)."""
    global HTTP_RATE_LIMIT
    HTTP_RATE_LIMIT = limit
    logger.info(f"HTTP rate limit set to {limit} requests/minute per IP")


def check_rate_limit(request: gr.Request) -> bool:
    """
    Check if request exceeds rate limit.

    Args:
        request: Gradio request object with client information

    Returns:
        True if request is allowed

    Raises:
        gr.Error: If rate limit exceeded
    """
    if HTTP_RATE_LIMIT <= 0:  # Rate limiting disabled
        return True

    client_ip = request.client.host
    now = datetime.now()
    cutoff = now - timedelta(minutes=1)

    # Clean old entries (older than 1 minute)
    _rate_limit_store[client_ip] = [ts for ts in _rate_limit_store[client_ip] if ts > cutoff]

    # Check limit
    if len(_rate_limit_store[client_ip]) >= HTTP_RATE_LIMIT:
        logger.warning(
            f"Rate limit exceeded for {client_ip}: "
            f"{len(_rate_limit_store[client_ip])} requests in last minute"
        )
        raise gr.Error(
            f"Rate limit exceeded: {HTTP_RATE_LIMIT} requests per minute. "
            f"Please wait before trying again."
        )

    # Record this request
    _rate_limit_store[client_ip].append(now)
    logger.debug(
        f"Request from {client_ip} allowed "
        f"({len(_rate_limit_store[client_ip])}/{HTTP_RATE_LIMIT})"
    )
    return True


# =============================================================================
# MCP TOOL 1: MT5 Query
# =============================================================================


def mt5_query_tool(
    operation: str,
    symbol: str = "",
    parameters: str = "",
    request: gr.Request = None,
) -> str:
    """
    Query MT5 data with structured parameters.

    This tool retrieves market data, symbol information, account details, and
    performs calculations from MetaTrader 5 terminal.

    Args:
        operation (str): MT5 operation name. Available operations:
            - copy_rates_from_pos: Get historical rates from position
            - copy_rates_from: Get rates from specific date
            - copy_rates_range: Get rates in date range
            - symbol_info: Get symbol specifications
            - symbol_info_tick: Get current tick
            - symbols_get: List available symbols
            - account_info: Get account information
            - terminal_info: Get terminal information
            - order_calc_margin: Calculate required margin
            - order_calc_profit: Calculate potential profit
        symbol (str): Trading symbol (e.g., BTCUSD, EURUSD). Required for
            symbol-specific operations.
        parameters (str): Operation-specific parameters as JSON string. Examples:
            - For copy_rates_from_pos: '{"timeframe": "H1", "start_pos": 0, "count": 100}'
            - For copy_rates_from: '{"timeframe": "D1", "date_from": "2024-01-01", "count": 30}'
            - For symbols_get: '{"group": "*USD*"}'
        request (gr.Request): Gradio request object (automatically provided, used for rate limiting)

    Returns:
        str: JSON string with query results containing:
            - success (bool): Operation success status
            - operation (str): Operation that was executed
            - data (list|dict): Query results (rates as list, info as dict)
            - metadata (dict): Request metadata

    Examples:
        Get BTCUSD symbol information:
        >>> mt5_query_tool("symbol_info", "BTCUSD")

        Get last 100 hourly candles:
        >>> mt5_query_tool("copy_rates_from_pos", "EURUSD",
        ...                '{"timeframe": "H1", "start_pos": 0, "count": 100}')

        List all USD pairs:
        >>> mt5_query_tool("symbols_get", "", '{"group": "*USD*"}')
    """
    # Apply rate limiting
    if request:
        check_rate_limit(request)

    # Ensure MT5 connection is initialized
    get_connection()

    try:
        # Parse parameters JSON string
        params_dict = None
        if parameters and parameters.strip():
            try:
                params_dict = json.loads(parameters)
            except json.JSONDecodeError as e:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid JSON in parameters: {str(e)}",
                        "error_type": "JSONDecodeError",
                    }
                )

        # Convert operation string to enum
        operation_enum = MT5Operation(operation)

        # Create request object
        query_request = MT5QueryRequest(
            operation=operation_enum,
            symbol=symbol if symbol else None,
            parameters=params_dict,
        )

        # Execute query
        response = handle_mt5_query(query_request)

        # Return as JSON string
        return json.dumps(response.model_dump(), default=str)

    except Exception as e:
        logger.error(f"MT5 query failed: {str(e)}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "operation": operation,
                "error": str(e),
                "error_type": type(e).__name__,
            }
        )


# =============================================================================
# MCP TOOL 2: MT5 Analysis
# =============================================================================


def mt5_analyze_tool(  # pylint: disable=too-many-arguments, too-many-locals
    # Query parameters
    query_operation: str,
    query_symbol: str,
    query_parameters: str = '{"timeframe": "H1", "count": 100}',
    # Indicator parameters
    indicators: str = "",
    # Chart parameters
    enable_chart: bool = False,
    chart_type: str = "multi",
    chart_panels: str = "",
    # Forecast parameters
    enable_forecast: bool = False,
    forecast_periods: int = 24,
    enable_ml_prediction: bool = False,
    # Output parameters
    output_format: str = "markdown",
    tail: int = None,
    request: gr.Request = None,
) -> str:
    """Run MT5 analysis combining indicators, charts, and optional forecasting.

    The tool orchestrates one workflow: fetch MT5 data, calculate indicators, render
    charts, and (optionally) project forecasts with Prophet plus XGBoost signals.

    Args:
        query_operation (str): MT5 operation for data retrieval (e.g., "copy_rates_from_pos").
        query_symbol (str): Trading symbol such as "BTCUSD" or "EURUSD".
        query_parameters (str): Query parameters encoded as JSON, for example
            '{"timeframe": "H1", "count": 100}'.
        indicators (str): JSON array describing indicator specs, e.g.
            '[{"function": "ta.momentum.rsi", "params": {"window": 14}}]'.
        enable_chart (bool): Generate matplotlib chart output.
        chart_type (str): Chart layout name ("single" or "multi").
        chart_panels (str): JSON array describing chart panels such as
            '[{"columns": ["close", "rsi"], "reference_lines": [30, 70]}]'.
        enable_forecast (bool): Enable Prophet forecast workflow.
        forecast_periods (int): Number of forecast periods (default 24).
        enable_ml_prediction (bool): Include XGBoost ML signal flag.
        output_format (str): Return format "markdown", "json", or "chart_only".
        tail (int): Row count limit for textual outputs (None returns all rows).
        request (gr.Request): Gradio request object used for rate limiting.

    Returns:
        str: JSON payload with success flag, data, chart paths, and metadata.

    Examples:
        >>> mt5_analyze_tool(
        ...     query_operation="copy_rates_from_pos",
        ...     query_symbol="BTCUSD",
        ...     query_parameters='{"timeframe": "H1", "count": 100}',
        ...     indicators='[{"function": "ta.momentum.rsi", "params": {"window": 14}}]'
        ... )

        >>> mt5_analyze_tool(
        ...     query_operation="copy_rates_from_pos",
        ...     query_symbol="EURUSD",
        ...     query_parameters='{"timeframe": "H4", "count": 168}',
        ...     indicators=(
        ...         '[{"function": "ta.momentum.rsi", "params": {"window": 14}}, '
        ...         '{"function": "ta.trend.sma_indicator", "params": {"window": 20}}]'
        ...     ),
        ...     enable_chart=True,
        ...     chart_panels='[{"columns": ["close", "sma_20"]}, {"columns": ["rsi"]}]',
        ...     enable_forecast=True,
        ...     forecast_periods=24,
        ...     enable_ml_prediction=True
        ... )
    """
    try:
        # Apply rate limiting
        if request:
            try:
                check_rate_limit(request)
            except gr.Error:
                raise
            except Exception as e:
                logger.error(f"Rate limit check failed: {e}", exc_info=True)
                return format_json_response(
                    create_error_response(
                        ErrorType.RUNTIME_ERROR,
                        f"Rate limit check failed: {str(e)}",
                        operation="rate_limit_check",
                    )
                )

        # Validate required fields
        if not query_operation or not isinstance(query_operation, str):
            return format_json_response(
                create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    "query_operation must be a non-empty string",
                    operation="mt5_analyze",
                )
            )

        if not query_symbol or not isinstance(query_symbol, str):
            return format_json_response(
                create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    "query_symbol must be a non-empty string",
                    operation="mt5_analyze",
                )
            )

        # Ensure MT5 connection is initialized
        try:
            get_connection()
        except Exception as e:
            logger.error(f"MT5 connection failed: {e}", exc_info=True)
            return format_json_response(
                create_error_response(
                    ErrorType.MT5_CONNECTION,
                    f"Failed to connect to MT5: {str(e)}",
                    operation="mt5_analyze",
                )
            )

        # Parse JSON string parameters with safe parsing
        query_params_dict, parse_error = safe_json_parse(
            query_parameters, "query_parameters", default={}
        )
        if parse_error:
            return format_json_response(parse_error)

        indicators_list, parse_error = safe_json_parse(indicators, "indicators", default=None)
        if parse_error:
            return format_json_response(parse_error)

        chart_panels_list, parse_error = safe_json_parse(chart_panels, "chart_panels", default=None)
        if parse_error:
            return format_json_response(parse_error)

        # Validate parameter types
        if not isinstance(query_params_dict, dict):
            message = (
                "query_parameters must be a JSON object, got " f"{type(query_params_dict).__name__}"
            )
            return format_json_response(
                create_error_response(
                    ErrorType.TYPE_ERROR,
                    message,
                    operation="mt5_analyze",
                )
            )

        if indicators_list is not None and not isinstance(indicators_list, list):
            return format_json_response(
                create_error_response(
                    ErrorType.TYPE_ERROR,
                    f"indicators must be a JSON array, got {type(indicators_list).__name__}",
                    operation="mt5_analyze",
                )
            )

        if chart_panels_list is not None and not isinstance(chart_panels_list, list):
            return format_json_response(
                create_error_response(
                    ErrorType.TYPE_ERROR,
                    f"chart_panels must be a JSON array, got {type(chart_panels_list).__name__}",
                    operation="mt5_analyze",
                )
            )

        # Convert operation string to enum with safe conversion
        query_operation_enum, enum_error = safe_enum_conversion(
            query_operation, MT5Operation, "query_operation"
        )
        if enum_error:
            return format_json_response(enum_error)

        # Build query request
        try:
            query_request = MT5QueryRequest(
                operation=query_operation_enum,
                symbol=query_symbol,
                parameters=query_params_dict,
            )
        except Exception as e:
            logger.error(f"Failed to create query request: {e}", exc_info=True)
            return format_json_response(
                create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    f"Invalid query request: {str(e)}",
                    operation="mt5_analyze",
                )
            )

        # Build indicator specs
        indicator_specs = None
        if indicators_list:
            try:
                indicator_specs = [
                    IndicatorSpec(
                        function=ind.get("function"),
                        params=ind.get("params"),
                        column_name=ind.get("column_name"),
                    )
                    for ind in indicators_list
                ]
            except Exception as e:
                logger.error(f"Failed to build indicator specs: {e}", exc_info=True)
                return format_json_response(
                    create_error_response(
                        ErrorType.VALIDATION_ERROR,
                        f"Invalid indicator specification: {str(e)}",
                        operation="mt5_analyze",
                    )
                )

        # Build chart config
        chart_config = None
        if enable_chart and chart_panels_list:
            try:
                from .models import ChartPanel

                panels = [
                    ChartPanel(
                        columns=panel.get("columns", []),
                        style=panel.get("style", "line"),
                        reference_lines=panel.get("reference_lines"),
                        y_label=panel.get("y_label"),
                        y_limits=panel.get("y_limits"),
                    )
                    for panel in chart_panels_list
                ]
                chart_config = ChartConfig(type=chart_type, panels=panels)
            except Exception as e:
                logger.error(f"Failed to build chart config: {e}", exc_info=True)
                return format_json_response(
                    create_error_response(
                        ErrorType.VALIDATION_ERROR,
                        f"Invalid chart configuration: {str(e)}",
                        operation="mt5_analyze",
                    )
                )

        # Build forecast config
        forecast_config = None
        if enable_forecast:
            try:
                # Validate forecast_periods
                if not isinstance(forecast_periods, int) or forecast_periods <= 0:
                    return format_json_response(
                        create_error_response(
                            ErrorType.VALIDATION_ERROR,
                            f"forecast_periods must be a positive integer, got {forecast_periods}",
                            operation="mt5_analyze",
                        )
                    )

                forecast_config = ForecastConfig(
                    periods=forecast_periods,
                    enable_ml_prediction=enable_ml_prediction,
                    plot=True,
                )
            except Exception as e:
                logger.error(f"Failed to build forecast config: {e}", exc_info=True)
                return format_json_response(
                    create_error_response(
                        ErrorType.VALIDATION_ERROR,
                        f"Invalid forecast configuration: {str(e)}",
                        operation="mt5_analyze",
                    )
                )

        # Create analysis request
        try:
            analysis_request = MT5AnalysisRequest(
                query=query_request,
                indicators=indicator_specs,
                chart=chart_config,
                forecast=forecast_config,
                output_format=output_format,
                tail=tail,
            )
        except Exception as e:
            logger.error(f"Failed to create analysis request: {e}", exc_info=True)
            return format_json_response(
                create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    f"Invalid analysis request: {str(e)}",
                    operation="mt5_analyze",
                )
            )

        # Execute analysis with error handling
        try:
            response = handle_mt5_analysis(analysis_request)
            return json.dumps(response.model_dump(), default=str)
        except Exception as e:
            logger.error(f"MT5 analysis execution failed: {str(e)}", exc_info=True)
            return format_json_response(
                create_error_response(
                    ErrorType.CALCULATION_ERROR,
                    f"Analysis execution failed: {str(e)}",
                    operation="mt5_analyze",
                    details={"symbol": query_symbol, "operation": query_operation},
                )
            )

    except gr.Error:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in mt5_analyze_tool: {str(e)}", exc_info=True)
        return format_json_response(
            create_error_response(
                ErrorType.UNKNOWN_ERROR,
                f"Unexpected error: {str(e)}",
                operation="mt5_analyze",
                details={"exception_type": type(e).__name__},
            )
        )


# =============================================================================
# MCP TOOL 3: MT5 Execute
# =============================================================================


def mt5_execute_tool(
    command: str,
    show_traceback: bool = True,
    request: gr.Request = None,
) -> str:
    """
    Execute raw Python code against MT5 (fallback tool for advanced users).

    This is a fallback tool for custom MT5 operations not covered by mt5_query
    or mt5_analyze. Use with caution as incorrect code can cause errors.

    CRITICAL RULES:
    - NEVER call mt5.initialize() or mt5.shutdown() (connection pre-managed)
    - MT5 is ALREADY connected - start with mt5.copy_rates_from_pos(...)
    - ALWAYS assign final output to 'result' variable for automatic return

    Available modules: mt5 (MetaTrader5), pd/pandas, np/numpy, plt/matplotlib,
    ta (technical indicators), datetime

    Timeframes: mt5.TIMEFRAME_M1, M5, M15, M30, H1, H4, D1, W1, MN1

    Args:
        command (str): Python code to execute. Must be valid Python syntax.
            The code runs in a restricted namespace with MT5 and data science
            libraries pre-imported. Assign final output to 'result' variable.
        show_traceback (bool): Show full Python traceback on errors (default: True)
        request (gr.Request): Gradio request object (automatically provided)

    Returns:
        str: Formatted execution result. DataFrames are rendered as markdown tables,
            dicts/lists as JSON, and other types as strings.

    Examples:
        Get symbol information:
        >>> mt5_execute_tool("result = mt5.symbol_info('BTCUSD')._asdict()")

        Calculate custom indicator:
        >>> command = '''
        ... rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
        ... df = pd.DataFrame(rates)
        ... df['custom_ma'] = df['close'].rolling(20).mean()
        ... result = df[['close', 'custom_ma']].tail(10)
        ... '''
        >>> mt5_execute_tool(command)
    """
    try:
        # Apply rate limiting
        if request:
            try:
                check_rate_limit(request)
            except gr.Error:
                raise
            except Exception as e:
                logger.error(f"Rate limit check failed: {e}", exc_info=True)
                error_response = create_error_response(
                    ErrorType.RUNTIME_ERROR,
                    f"Rate limit check failed: {str(e)}",
                    operation="rate_limit_check",
                )
                return format_json_response(error_response)

        # Validate command
        if not command or not isinstance(command, str):
            error_response = create_error_response(
                ErrorType.VALIDATION_ERROR,
                "Command must be a non-empty string",
                operation="mt5_execute",
                details={"received_type": type(command).__name__},
            )
            return format_json_response(error_response)

        # Check command length to prevent abuse
        if len(command) > 50000:  # 50KB limit
            error_response = create_error_response(
                ErrorType.VALIDATION_ERROR,
                f"Command too long: {len(command)} characters (max 50000)",
                operation="mt5_execute",
            )
            return format_json_response(error_response)

        # Check for dangerous operations
        dangerous_patterns = [
            "mt5.initialize",
            "mt5.shutdown",
            "os.system",
            "subprocess",
            "eval(",
            "exec(",
            "__import__",
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                error_response = create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    f"Dangerous operation detected: {pattern}",
                    operation="mt5_execute",
                    details={"pattern": pattern},
                )
                return format_json_response(error_response)

        # Get safe namespace
        try:
            namespace = get_safe_namespace()
        except Exception as e:
            logger.error(f"Failed to get namespace: {e}", exc_info=True)
            error_response = create_error_response(
                ErrorType.MT5_CONNECTION,
                f"Failed to initialize execution environment: {str(e)}",
                operation="mt5_execute",
            )
            return format_json_response(error_response)

        # Execute command with error handling
        try:
            result = execute_command(command, namespace, show_traceback)
            return result
        except Exception as e:
            logger.error(f"Code execution failed: {str(e)}", exc_info=True)
            if show_traceback:
                import traceback

                return f"Error executing code:\n\n{traceback.format_exc()}"
            return f"Error: {type(e).__name__}: {str(e)}"

    except gr.Error:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in mt5_execute_tool: {str(e)}", exc_info=True)
        if show_traceback:
            import traceback

            return f"Unexpected error:\n\n{traceback.format_exc()}"
        return f"Unexpected error: {type(e).__name__}: {str(e)}"


# =============================================================================
# GRADIO INTERFACE
# =============================================================================


def create_gradio_interface():
    """
    Create Gradio interface with multiple pages: Status, Transaction History, and Open Positions.

    Returns:
        gr.Blocks: Gradio demo with tabbed interface
    """

    def get_server_status():
        """Get current server status and metrics."""
        try:
            # Try to get MT5 connection and validate it
            mt5_conn = get_connection()

            # Validate connection first
            if not mt5_conn.validate_connection():
                raise RuntimeError("MT5 terminal is not connected. Please ensure MT5 is running.")

            mt5_status = "✅ Connected"

            # Get terminal info using safe_mt5_call
            import MetaTrader5 as mt5

            terminal_info = safe_mt5_call(mt5.terminal_info)
            if terminal_info:
                terminal_data = terminal_info._asdict()
                company = terminal_data.get("company", "Unknown")
                build = terminal_data.get("build", "Unknown")
                terminal_details = f"{company} (Build {build})"
            else:
                terminal_details = "Unable to fetch details"

            # Get account info using safe_mt5_call
            account_info = safe_mt5_call(mt5.account_info)
            if account_info:
                acc_data = account_info._asdict()
                account_details = (
                    f"Account: {acc_data.get('login', 'N/A')}\n"
                    f"Balance: {acc_data.get('balance', 0):.2f} {acc_data.get('currency', 'USD')}\n"
                    f"Server: {acc_data.get('server', 'N/A')}"
                )
            else:
                account_details = "Unable to fetch account details"

            # Count available symbols using safe_mt5_call
            symbols = safe_mt5_call(mt5.symbols_total)
            symbol_count = f"{symbols} symbols available" if symbols else "Unable to count symbols"

        except Exception as e:
            mt5_status = f"❌ Disconnected: {str(e)}"
            terminal_details = "N/A"
            account_details = "N/A"
            symbol_count = "N/A"

        # Rate limit stats
        total_ips = len(_rate_limit_store)
        rate_limit_info = (
            f"Rate Limit: {HTTP_RATE_LIMIT} req/min per IP\n" f"Active IPs: {total_ips}"
        )

        # Build status report
        status_report = f"""## MetaTrader 5 MCP Server Status

### Connection Status
{mt5_status}

### Terminal Information
{terminal_details}

### Account Information
{account_details}

### Market Data
{symbol_count}

### Server Configuration
{rate_limit_info}

### MCP Endpoint
`/gradio_api/mcp/` (Streamable HTTP/SSE)

### Available Tools
- `mt5_query` - Structured MT5 data queries
- `mt5_analyze` - Technical analysis with indicators & forecasting
- `mt5_execute` - Raw Python execution (read-only namespace)

---
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return status_report

    def get_transaction_history(days=90):
        """Get transaction history with Plotly chart."""
        try:
            import MetaTrader5 as mt5
            import pandas as pd

            # Import plotly
            try:
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
            except ImportError:
                return None, "⚠️ Plotly not installed. Run: pip install plotly>=5.18.0"

            # Get MT5 connection
            mt5_conn = get_connection()
            if not mt5_conn.validate_connection():
                return None, "❌ MT5 not connected"

            # Get deals from selected time range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            deals = safe_mt5_call(mt5.history_deals_get, start_date, end_date)

            if not deals or len(deals) == 0:
                return None, f"📊 No transaction history found in the last {days} days"

            # Convert to DataFrame
            df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
            df["time"] = pd.to_datetime(df["time"], unit="s")

            # Identify deposit/withdrawal (entry = 2 for balance operations)
            df["is_balance_op"] = df["entry"] == 2
            df["type_name"] = df.apply(
                lambda row: (
                    "💵 Deposit"
                    if row["is_balance_op"] and row["profit"] > 0
                    else (
                        "💸 Withdrawal"
                        if row["is_balance_op"] and row["profit"] < 0
                        else "📈 Trade"
                    )
                ),
                axis=1,
            )

            # Calculate cumulative profit
            df["cumulative_profit"] = df["profit"].cumsum()

            # Create subplot figure
            fig = make_subplots(
                rows=2,
                cols=1,
                row_heights=[0.7, 0.3],
                subplot_titles=("Cumulative P&L", "Individual Transactions"),
                vertical_spacing=0.12,
            )

            # Add cumulative profit line
            fig.add_trace(
                go.Scatter(
                    x=df["time"],
                    y=df["cumulative_profit"],
                    mode="lines",
                    name="Cumulative P&L",
                    line={"color": "#2E86AB", "width": 2},
                    hovertemplate=("Date: %{x}<br>Cumulative: $%{y:.2f}<extra></extra>"),
                ),
                row=1,
                col=1,
            )

            # Add markers for trades (green/red)
            trades_df = df[~df["is_balance_op"]]
            if len(trades_df) > 0:
                colors_trades = ["#06D6A0" if p > 0 else "#EF476F" for p in trades_df["profit"]]
                fig.add_trace(
                    go.Scatter(
                        x=trades_df["time"],
                        y=trades_df["cumulative_profit"],
                        mode="markers",
                        name="Trades",
                        marker={
                            "size": 8,
                            "color": colors_trades,
                            "opacity": 0.7,
                            "line": {"width": 1, "color": "white"},
                        },
                        text=[
                            f"{row['symbol']}: ${row['profit']:.2f}"
                            for _, row in trades_df.iterrows()
                        ],
                        hovertemplate="%{text}<br>Time: %{x}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

            # Add markers for deposits/withdrawals (diamond shape)
            balance_df = df[df["is_balance_op"]]
            if len(balance_df) > 0:
                colors_balance = ["#118AB2" if p > 0 else "#FFD60A" for p in balance_df["profit"]]
                fig.add_trace(
                    go.Scatter(
                        x=balance_df["time"],
                        y=balance_df["cumulative_profit"],
                        mode="markers",
                        name="Deposits/Withdrawals",
                        marker={
                            "size": 12,
                            "color": colors_balance,
                            "opacity": 0.9,
                            "symbol": "diamond",
                            "line": {"width": 2, "color": "white"},
                        },
                        text=[
                            f"{row['type_name']}: ${row['profit']:.2f}"
                            for _, row in balance_df.iterrows()
                        ],
                        hovertemplate="%{text}<br>Time: %{x}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

            # Add bar chart for individual transactions
            colors_bar = [
                (
                    "#06D6A0"
                    if p > 0
                    else "#EF476F" if not is_bal else "#118AB2" if p > 0 else "#FFD60A"
                )
                for p, is_bal in zip(df["profit"], df["is_balance_op"])
            ]

            fig.add_trace(
                go.Bar(
                    x=df["time"],
                    y=df["profit"],
                    name="Profit/Loss",
                    marker={"color": colors_bar, "opacity": 0.8},
                    hovertemplate="%{x}<br>P&L: $%{y:.2f}<extra></extra>",
                    showlegend=False,
                ),
                row=2,
                col=1,
            )

            # Update layout - full width and auto-fit
            fig.update_layout(
                height=700,
                hovermode="x unified",
                template="plotly_white",
                legend={
                    "orientation": "h",
                    "yanchor": "bottom",
                    "y": 1.02,
                    "xanchor": "right",
                    "x": 1,
                },
                margin={"l": 50, "r": 50, "t": 80, "b": 50},
                autosize=True,
                xaxis={"automargin": True},
                xaxis2={"automargin": True},
            )

            fig.update_xaxes(title_text="Date", row=2, col=1)
            fig.update_yaxes(title_text="Cumulative P&L ($)", row=1, col=1)
            fig.update_yaxes(title_text="Transaction Amount ($)", row=2, col=1)

            # Summary stats
            total_profit = df["profit"].sum()
            total_trades = len(trades_df)
            total_deposits = (
                balance_df[balance_df["profit"] > 0]["profit"].sum() if len(balance_df) > 0 else 0
            )
            total_withdrawals = (
                abs(balance_df[balance_df["profit"] < 0]["profit"].sum())
                if len(balance_df) > 0
                else 0
            )
            win_rate = (
                (trades_df["profit"] > 0).sum() / len(trades_df) * 100 if len(trades_df) > 0 else 0
            )

            # Explanation of missing markers
            deposit_note = (
                f"💎 **{len(balance_df[balance_df['profit'] > 0])} Deposits** found"
                if len(balance_df[balance_df["profit"] > 0]) > 0
                else "⚠️ **No deposits** detected (entry type must be 2 with positive profit)"
            )
            withdrawal_note = (
                f"💎 **{len(balance_df[balance_df['profit'] < 0])} Withdrawals** found"
                if len(balance_df[balance_df["profit"] < 0]) > 0
                else "⚠️ **No withdrawals** detected (entry type must be 2 with negative profit)"
            )

            summary = f"""
**📊 Summary (Last {days} Days)**
- **Total Trades:** {total_trades} (🟢 Green = Profit, 🔴 Red = Loss)
- **Win Rate:** {win_rate:.1f}%
- **Total Trading P&L:** ${total_profit:.2f}
- {deposit_note}
    - Total: ${total_deposits:.2f}
- {withdrawal_note}
    - Total: ${total_withdrawals:.2f}

---
**📖 Chart Explanation:**
- **Top chart**: Cumulative P&L line shows your account growth over time
    - Dots on the line = individual trades
    - Diamond markers = deposits (blue) / withdrawals (yellow)
- **Bottom chart**: Individual transaction bars show each trade/deposit/withdrawal amount
    - Green bars = profitable trades
    - Red bars = losing trades
    - Blue bars = deposits
    - Yellow bars = withdrawals

⚠️ **Note:** MT5 marks deposits/withdrawals with `entry=2` deal type.
If you don't see diamond markers, your account may not have any
deposits/withdrawals in this period, or they're recorded differently
by your broker.

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

            return fig, summary

        except Exception as e:
            return None, f"❌ Error: {str(e)}"

    def get_open_positions():
        """Get open positions with real-time data."""
        try:
            import MetaTrader5 as mt5
            import pandas as pd

            # Get MT5 connection
            mt5_conn = get_connection()
            if not mt5_conn.validate_connection():
                return "❌ MT5 not connected", ""

            # Get open positions
            positions = safe_mt5_call(mt5.positions_get)
            total = safe_mt5_call(mt5.positions_total)

            if not positions or len(positions) == 0:
                message = (
                    "📊 **Open Positions: 0**\n\n*No open positions*\n\n*Last "
                    f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
                )
                return (message, "")

            # Convert to DataFrame
            df = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df["type_str"] = df["type"].apply(lambda x: "🟢 BUY" if x == 0 else "🔴 SELL")

            # Calculate current P&L
            total_profit = df["profit"].sum()
            total_volume = df["volume"].sum()

            # Create HTML table
            table_html = "<table style='width:100%; border-collapse: collapse;'>"
            table_html += "<tr style='background-color: #f0f0f0; font-weight: bold;'>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Symbol</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Type</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Volume</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Open Price</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Current Price</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>P&L</th>"
            table_html += "<th style='padding: 8px; border: 1px solid #ddd;'>Time</th>"
            table_html += "</tr>"

            for _, row in df.iterrows():
                profit_color = "#06D6A0" if row["profit"] >= 0 else "#EF476F"
                table_html += "<tr>"
                table_html += (
                    f"<td style='padding: 8px; border: 1px solid #ddd;'>{row['symbol']}</td>"
                )
                table_html += (
                    f"<td style='padding: 8px; border: 1px solid #ddd;'>{row['type_str']}</td>"
                )
                table_html += (
                    f"<td style='padding: 8px; border: 1px solid #ddd;'>{row['volume']:.2f}</td>"
                )
                table_html += (
                    "<td style='padding: 8px; border: 1px solid #ddd;'>"
                    f"{row['price_open']:.5f}</td>"
                )
                table_html += (
                    "<td style='padding: 8px; border: 1px solid #ddd;'>"
                    f"{row['price_current']:.5f}</td>"
                )
                table_html += (
                    "<td style='padding: 8px; border: 1px solid #ddd; color: "
                    f"{profit_color}; font-weight: bold;'>${row['profit']:.2f}</td>"
                )
                table_html += (
                    "<td style='padding: 8px; border: 1px solid #ddd;'>"
                    f"{row['time'].strftime('%Y-%m-%d %H:%M')}</td>"
                )
                table_html += "</tr>"

            table_html += "</table>"

            # Summary
            summary = f"""
## 📊 Open Positions: {total}

**Total Volume:** {total_volume:.2f} lots
**Total Unrealized P&L:** ${total_profit:.2f}

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

            return summary, table_html

        except Exception as e:
            return f"❌ Error: {str(e)}", ""

    # Build Gradio interface with tabs
    with gr.Blocks(title="MetaTrader 5 MCP Server") as demo:
        gr.Markdown("# MetaTrader 5 MCP Server")

        with gr.Tabs():
            # Tab 1: Status Dashboard
            with gr.Tab("📊 Status"):
                gr.Markdown(
                    "Real-time status dashboard for the MT5 MCP server. "
                    "Connect your MCP client to `/gradio_api/mcp/` to use the tools."
                )

                status_output = gr.Markdown(get_server_status())

                refresh_btn = gr.Button("🔄 Refresh Status", variant="primary")
                refresh_btn.click(fn=get_server_status, outputs=status_output)

                # Auto-refresh every 30 seconds
                status_timer = gr.Timer(30)
                status_timer.tick(fn=get_server_status, outputs=status_output)

            # Tab 2: Transaction History
            with gr.Tab("💰 Transaction History"):
                gr.Markdown("### Trading history with deposits/withdrawals")
                gr.Markdown(
                    "🔹 **Green/Red dots** = Trades | 💎 **Blue/Yellow diamonds** "
                    "= Deposits/Withdrawals"
                )

                with gr.Row():
                    date_range = gr.Radio(
                        choices=[7, 30, 90, 180, 365],
                        value=90,
                        label="Time Range (Days)",
                        info="Select how many days of history to display",
                    )
                    history_refresh_btn = gr.Button(
                        "🔄 Refresh History", variant="primary", scale=0
                    )

                history_plot = gr.Plot(label="Transaction History")
                history_summary = gr.Markdown()

                def update_history(days):
                    fig, summary = get_transaction_history(days)
                    return fig, summary

                # Update on button click or date range change
                history_refresh_btn.click(
                    fn=update_history, inputs=[date_range], outputs=[history_plot, history_summary]
                )
                date_range.change(
                    fn=update_history, inputs=[date_range], outputs=[history_plot, history_summary]
                )

                # Auto-refresh every 1 minute
                history_timer = gr.Timer(60)
                history_timer.tick(
                    fn=lambda: update_history(date_range.value),
                    outputs=[history_plot, history_summary],
                )

                # Load initial data
                demo.load(fn=lambda: update_history(90), outputs=[history_plot, history_summary])

            # Tab 3: Open Positions
            with gr.Tab("📈 Open Positions"):
                gr.Markdown("### Real-time open positions (Auto-refresh every 1 second)")

                positions_summary = gr.Markdown()
                positions_table = gr.HTML()

                positions_refresh_btn = gr.Button("🔄 Refresh Positions", variant="primary")

                def update_positions():
                    summary, table = get_open_positions()
                    return summary, table

                positions_refresh_btn.click(
                    fn=update_positions, outputs=[positions_summary, positions_table]
                )

                # Auto-refresh every 1 second
                positions_timer = gr.Timer(1)
                positions_timer.tick(
                    fn=update_positions, outputs=[positions_summary, positions_table]
                )

                # Load initial data
                demo.load(fn=update_positions, outputs=[positions_summary, positions_table])

    return demo


# =============================================================================
# LAUNCHER
# =============================================================================


def launch_gradio_mcp(
    host: str = "0.0.0.0",
    port: int = 7860,
    rate_limit: int = 10,
    share: bool = False,
):
    """
    Launch Gradio MCP server with HTTP/SSE support.

    Args:
        host: Host address (default: "0.0.0.0")
        port: Port number (default: 7860)
        rate_limit: Rate limit in requests per minute per IP (default: 10, 0 = unlimited)
        share: Create public share link (default: False)
    """
    # Set rate limit
    set_rate_limit(rate_limit)

    # Create interface
    demo = create_gradio_interface()

    # Launch with MCP server enabled
    rate_limit_desc = (
        f"{rate_limit} req/min per IP" if rate_limit > 0 else "unlimited req/min per IP"
    )
    logger.info(
        "Starting Gradio MCP server on %s:%s (rate limit: %s)",
        host,
        port,
        rate_limit_desc,
    )
    logger.info("MCP endpoint: http://%s:%s/gradio_api/mcp/", host, port)

    # Explicitly specify which functions should be exposed as MCP tools
    demo.launch(
        server_name=host,
        server_port=port,
        mcp_server=True,  # Enable MCP endpoint
        mcp_functions=[mt5_query_tool, mt5_analyze_tool, mt5_execute_tool],  # Only expose these 3 tools
        share=share,
        show_error=True,
    )


if __name__ == "__main__":
    # For testing: python -m mt5_mcp.gradio_server
    import sys

    cli_port = int(sys.argv[1]) if len(sys.argv) > 1 else 7860
    cli_rate_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    launch_gradio_mcp(port=cli_port, rate_limit=cli_rate_limit)
