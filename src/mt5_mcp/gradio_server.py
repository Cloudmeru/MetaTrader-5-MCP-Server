"""Gradio MCP Server with HTTP/SSE support and rate limiting."""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import gradio as gr

from .handlers import handle_mt5_query, handle_mt5_analysis
from .executor import execute_command
from .connection import get_safe_namespace, get_connection
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
    # Apply rate limiting
    if request:
        check_rate_limit(request)

    # Ensure MT5 connection is initialized
    get_connection()

    try:
        # Parse JSON string parameters
        try:
            query_params_dict = json.loads(query_parameters) if query_parameters else {}
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON in query_parameters: {e}"})

        indicators_list = None
        if indicators and indicators.strip():
            try:
                indicators_list = json.loads(indicators)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON in indicators: {e}"})

        chart_panels_list = None
        if chart_panels and chart_panels.strip():
            try:
                chart_panels_list = json.loads(chart_panels)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON in chart_panels: {e}"})

        # Build query request
        query_operation_enum = MT5Operation(query_operation)
        query_request = MT5QueryRequest(
            operation=query_operation_enum,
            symbol=query_symbol,
            parameters=query_params_dict,
        )

        # Build indicator specs
        indicator_specs = None
        if indicators_list:
            indicator_specs = [
                IndicatorSpec(
                    function=ind.get("function"),
                    params=ind.get("params"),
                    column_name=ind.get("column_name"),
                )
                for ind in indicators_list
            ]

        # Build chart config
        chart_config = None
        if enable_chart and chart_panels_list:
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

        # Build forecast config
        forecast_config = None
        if enable_forecast:
            forecast_config = ForecastConfig(
                periods=forecast_periods,
                enable_ml_prediction=enable_ml_prediction,
                plot=True,
            )

        # Create analysis request
        analysis_request = MT5AnalysisRequest(
            query=query_request,
            indicators=indicator_specs,
            chart=chart_config,
            forecast=forecast_config,
            output_format=output_format,
            tail=tail,
        )

        # Execute analysis
        response = handle_mt5_analysis(analysis_request)

        # Return as JSON string
        return json.dumps(response.model_dump(), default=str)

    except Exception as e:
        logger.error(f"MT5 analysis failed: {str(e)}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }
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
    # Apply rate limiting
    if request:
        check_rate_limit(request)

    try:
        namespace = get_safe_namespace()
        result = execute_command(command, namespace, show_traceback)
        return result

    except Exception as e:
        logger.error(f"Code execution failed: {str(e)}", exc_info=True)
        if show_traceback:
            import traceback

            return f"Error executing code:\n\n{traceback.format_exc()}"
        return f"Error: {type(e).__name__}: {str(e)}"


# =============================================================================
# GRADIO INTERFACE
# =============================================================================


def create_gradio_interface():
    """Create Gradio interface with all MCP tools."""

    # Tool 1: Query Interface
    query_interface = gr.Interface(
        fn=mt5_query_tool,
        inputs=[
            gr.Textbox(
                label="Operation",
                placeholder="copy_rates_from_pos",
            ),
            gr.Textbox(
                label="Symbol",
                placeholder="BTCUSD",
            ),
            gr.Textbox(
                label="Parameters (JSON string)",
                placeholder='{"timeframe": "H1", "count": 100}',
            ),
        ],
        outputs=gr.Textbox(label="Results (JSON)", lines=20),
        title="MT5 Query",
        description="Query MT5 data (rates, symbol info, account info)",
        examples=[
            ["symbol_info", "BTCUSD", ""],
            [
                "copy_rates_from_pos",
                "EURUSD",
                '{"timeframe": "H1", "start_pos": 0, "count": 100}',
            ],
            ["account_info", "", ""],
        ],
    )

    # Tool 2: Analysis Interface
    analysis_interface = gr.Interface(
        fn=mt5_analyze_tool,
        inputs=[
            gr.Textbox(label="Query Operation", value="copy_rates_from_pos"),
            gr.Textbox(label="Query Symbol", value="BTCUSD"),
            gr.Textbox(
                label="Query Parameters (JSON)",
                value='{"timeframe": "H1", "count": 100}',
            ),
            gr.Textbox(
                label="Indicators (JSON array)",
                value="",
                placeholder='[{"function": "ta.momentum.rsi", "params": {"window": 14}}]',
            ),
            gr.Checkbox(label="Enable Chart", value=False),
            gr.Radio(["single", "multi"], label="Chart Type", value="multi"),
            gr.Textbox(
                label="Chart Panels (JSON array)",
                value="",
                placeholder='[{"columns": ["close", "rsi"]}]',
            ),
            gr.Checkbox(label="Enable Forecast", value=False),
            gr.Number(label="Forecast Periods", value=24),
            gr.Checkbox(label="Enable ML Prediction", value=False),
            gr.Radio(
                ["markdown", "json", "chart_only"],
                label="Output Format",
                value="markdown",
            ),
            gr.Number(label="Tail (rows to return)", value=None),
        ],
        outputs=gr.Textbox(label="Analysis Results (JSON)", lines=20),
        title="MT5 Analysis",
        description="Comprehensive analysis with indicators, charts, and forecasting",
    )

    # Tool 3: Execute Interface
    execute_interface = gr.Interface(
        fn=mt5_execute_tool,
        inputs=[
            gr.Code(
                label="Python Command",
                language="python",
                lines=10,
            ),
            gr.Checkbox(label="Show Traceback", value=True),
        ],
        outputs=gr.Textbox(label="Result", lines=20),
        title="MT5 Execute",
        description="Execute raw Python code (advanced users only)",
        examples=[
            ["result = mt5.symbol_info('BTCUSD')._asdict()", True],
            [
                (
                    "rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H1, 0, 50)\n"
                    "df = pd.DataFrame(rates)\n"
                    "result = df.tail(10)"
                ),
                True,
            ],
        ],
    )

    # Combine into tabbed interface
    demo = gr.TabbedInterface(
        [query_interface, analysis_interface, execute_interface],
        ["Query", "Analysis", "Execute"],
        title="MT5 MCP Server",
    )

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

    demo.launch(
        server_name=host,
        server_port=port,
        mcp_server=True,  # Enable MCP endpoint
        share=share,
        show_error=True,
    )


if __name__ == "__main__":
    # For testing: python -m mt5_mcp.gradio_server
    import sys

    cli_port = int(sys.argv[1]) if len(sys.argv) > 1 else 7860
    cli_rate_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    launch_gradio_mcp(port=cli_port, rate_limit=cli_rate_limit)
