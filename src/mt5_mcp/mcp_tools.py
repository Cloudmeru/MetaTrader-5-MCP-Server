"""
MCP tool implementations for the MetaTrader 5 integration.

Each tool is a regular Python function decorated by :func:`mcp_server.create_mcp_server`.
FastMCP derives the JSON schema from the Python type annotations, so callers
send native JSON objects (no string-encoded payloads).

Design notes:
- All three tools are **synchronous** (the MetaTrader5 Python package is a
  thin C extension that is not thread-safe and binds to the thread on which
  ``mt5.initialize()`` was first called). They are registered with
  ``run_in_thread=False`` so FastMCP runs them inline on the asyncio loop,
  keeping the MT5 connection on the same thread for every call.
- ``Context`` injection is used for logging back to the MCP client. It is
  stripped from the schema automatically by FastMCP.
- The safe namespace and connection lifecycle live in
  :mod:`mt5_mcp.connection`. Tool functions never touch MetaTrader5 globals
  directly.
- All return values flow through :func:`mt5_mcp.toon_output.format_response`,
  which applies the server-side TOON-encoding heuristic. The LLM never
  chooses the wire encoding — see the toon_output module docstring for the
  shape-detection rules.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context

from .connection import get_connection, get_safe_namespace
from .error_utils import (
    ErrorType,
    create_error_response,
    format_json_response,
    safe_enum_conversion,
    safe_json_parse,
)
from .handlers import handle_mt5_analysis, handle_mt5_query
from .models import (
    ChartConfig,
    ChartPanel,
    ForecastConfig,
    IndicatorSpec,
    MT5AnalysisRequest,
    MT5Operation,
    MT5QueryRequest,
)
from .toon_output import format_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum length of a user-supplied ``command`` blob for ``mt5_execute``.
# 50 KB is well over what a reasonable script needs and prevents abuse.
MAX_EXECUTE_COMMAND_BYTES = 50_000

# Substrings that we refuse to execute. This is *defense-in-depth*: the safe
# namespace does not actually expose these names, but a determined caller
# could reach for ``getattr(__builtins__, ...)`` tricks, so we also
# short-circuit at the source.
_DANGEROUS_PATTERNS: tuple[str, ...] = (
    "mt5.initialize",
    "mt5.shutdown",
    "MetaTrader5.initialize",
    "MetaTrader5.shutdown",
    "order_send",
    "order_check",
    "positions_get",  # blocked in README — read-only but excluded for clarity
    "positions_total",
    "os.system",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check",
    "shutil.rmtree",
    "__import__",
    "breakpoint(",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_connection() -> str | None:
    """Make sure the MT5 connection is live. Returns an error string if not."""
    try:
        get_connection()
        return None
    except Exception as exc:
        return f"MT5 connection failed: {exc}"


def _coerce_parameters_json(value: Any, field_name: str) -> tuple[dict | None, str | None]:
    """FastMCP delivers ``parameters`` as a JSON object thanks to Pydantic, but
    some callers (older MCP clients, hand-rolled JSON) may still pass a
    string. Accept both. Returns ``(dict_or_None, error_message_or_None)``.
    """
    if value is None or value == "":
        return None, None
    if isinstance(value, dict):
        return value, None
    if isinstance(value, str):
        parsed, err = safe_json_parse(value, field_name, default=None)
        if err is not None:
            return None, err.get("error", "invalid JSON")
        if parsed is not None and not isinstance(parsed, dict):
            return None, f"{field_name} must be a JSON object, got {type(parsed).__name__}"
        return parsed, None
    return None, f"{field_name} must be a JSON object or string, got {type(value).__name__}"


def _strip_terminal_quotes(raw: str) -> str:
    """Allow ``execute("mt5.foo()")`` — the literal final expression form."""
    return raw.strip()


# ---------------------------------------------------------------------------
# Shared error envelope
# ---------------------------------------------------------------------------


def _error(
    *,
    error_type: ErrorType,
    message: str,
    operation: str,
    details: dict[str, Any] | None = None,
) -> Any:
    """Build a structured error envelope and route it through the format
    heuristic. The LLM sees the same JSON / TOON-decision tree for errors
    as for success responses."""
    return format_response(
        format_json_response(
            create_error_response(
                error_type,
                message,
                operation=operation,
                details=details,
            )
        )
    )


# ---------------------------------------------------------------------------
# mt5_query — structured read-only data retrieval
# ---------------------------------------------------------------------------


def mt5_query(
    operation: str,
    symbol: str | None = None,
    parameters: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> Any:
    """Query MT5 market data, symbol info, account details, or perform a
    read-only calculation.

    Args:
        operation: One of the supported MT5 read-only operations (see the
            JSON schema's ``enum`` for the canonical list — e.g.
            ``copy_rates_from_pos``, ``symbol_info``, ``symbols_get``,
            ``account_info``, ``order_calc_profit``).
        symbol: Trading symbol (e.g. ``BTCUSD``). Required for
            symbol-specific operations; ignored otherwise.
        parameters: Operation-specific parameters as a JSON object, e.g.
            ``{"timeframe": "H1", "start_pos": 0, "count": 100}``. Optional;
            some operations (like ``symbol_info``) need none.
        ctx: FastMCP Context (injected automatically; do not pass).

    Returns:
        A JSON-serialisable dict on the success / error path. When the
        ``data`` field is a uniform array of dicts and TOON would save
        ≥10 % tokens, the response shape is:

        * For tabular arrays: a copy of the response dict where ``data``
          is replaced by a TOON string, with a sibling
          ``"data_format": "toon"`` marker.
        * For whole-response TOON fits: a TOON string.
        * Otherwise: compact JSON (unchanged from v0.6.0).

        The server picks; the LLM consumes. See
        :mod:`mt5_mcp.toon_output` for the heuristic.
    """
    err = _ensure_connection()
    if err is not None:
        return _error(
            error_type=ErrorType.MT5_CONNECTION,
            message=err,
            operation="mt5_query",
            details={"operation": operation, "symbol": symbol},
        )

    op_enum, enum_err = safe_enum_conversion(operation, MT5Operation, "operation")
    if enum_err is not None:
        return _error(
            error_type=ErrorType.VALIDATION_ERROR,
            message=enum_err.get("error", f"unknown operation: {operation!r}"),
            operation="mt5_query",
            details={**enum_err, "operation": "mt5_query", "raw_operation": operation},
        )

    params_dict, err_msg = _coerce_parameters_json(parameters, "parameters")
    if err_msg is not None:
        return _error(
            error_type=ErrorType.VALIDATION_ERROR,
            message=err_msg,
            operation="mt5_query",
            details={"received_type": type(parameters).__name__},
        )

    request = MT5QueryRequest(
        operation=op_enum,
        symbol=symbol or None,
        parameters=params_dict or {},
    )

    try:
        response = handle_mt5_query(request)
        return format_response(response.model_dump())
    except Exception as exc:
        logger.exception("mt5_query failed")
        if ctx is not None:
            pass  # ctx is sync-injected; nothing to await here
        return _error(
            error_type=ErrorType.OPERATION_ERROR,
            message=f"mt5_query failed: {exc}",
            operation="mt5_query",
            details={"exception_type": type(exc).__name__},
        )


# ---------------------------------------------------------------------------
# mt5_analyze — query + indicators + charts + forecast in one shot
# ---------------------------------------------------------------------------


def mt5_analyze(
    operation: str,
    symbol: str,
    parameters: dict[str, Any] | None = None,
    indicators: list[dict[str, Any]] | None = None,
    chart: dict[str, Any] | None = None,
    forecast: dict[str, Any] | None = None,
    output_format: str = "markdown",
    tail: int | None = None,
    ctx: Context | None = None,
) -> Any:
    """Run a full MT5 analysis pipeline: fetch data, compute indicators,
    render a chart, and optionally project a forecast.

    Args:
        operation: The MT5 operation used to fetch the underlying series
            (most commonly ``copy_rates_from_pos`` or ``copy_rates_range``).
        symbol: Trading symbol such as ``BTCUSD`` or ``EURUSD``.
        parameters: Operation parameters as a JSON object. Sensible default
            is ``{"timeframe": "H1", "count": 100}`` when omitted.
        indicators: List of indicator specs. Each item is a dict like
            ``{"function": "ta.momentum.rsi", "params": {"window": 14},
            "column_name": "rsi"}``.
        chart: Optional chart configuration. Schema:
            ``{"type": "single"|"multi", "panels": [...], "filename":
            "chart.png", "width": 14, "height": 8, "dpi": 120}``.
        forecast: Optional Prophet forecast configuration. Schema:
            ``{"periods": 24, "freq": "h", "seasonality_mode": "additive",
            "growth": "linear", "plot": true, "enable_ml_prediction": false,
            "ml_lookback": 50}``.
        output_format: ``markdown``, ``json``, or ``chart_only`` (controls
            the *analysis report shape*; markdown is the default).
        tail: Return only the last N rows of tabular data. ``None`` returns
            all rows.
        ctx: FastMCP Context (injected automatically; do not pass).

    Returns:
        Same shape contract as ``mt5_query`` — the server applies the
        TOON shape heuristic and decides whether to embed TOON, return
        a whole-response TOON document, or fall back to compact JSON.
    """
    err = _ensure_connection()
    if err is not None:
        return _error(
            error_type=ErrorType.MT5_CONNECTION,
            message=err,
            operation="mt5_analyze",
            details={"symbol": symbol, "operation": operation},
        )

    op_enum, enum_err = safe_enum_conversion(operation, MT5Operation, "operation")
    if enum_err is not None:
        return _error(
            error_type=ErrorType.VALIDATION_ERROR,
            message=enum_err.get("error", f"unknown operation: {operation!r}"),
            operation="mt5_analyze",
            details={**enum_err, "operation": "mt5_analyze", "raw_operation": operation},
        )

    params_dict, err_msg = _coerce_parameters_json(parameters, "parameters")
    if err_msg is not None:
        return _error(
            error_type=ErrorType.VALIDATION_ERROR,
            message=err_msg,
            operation="mt5_analyze",
            details={"received_type": type(parameters).__name__},
        )

    # Build indicator specs (Pydantic validates each entry).
    indicator_specs: list[IndicatorSpec] | None = None
    if indicators:
        try:
            indicator_specs = [
                IndicatorSpec(
                    function=item.get("function"),
                    params=item.get("params") or {},
                    column_name=item.get("column_name"),
                )
                for item in indicators
            ]
        except Exception as exc:
            return _error(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"Invalid indicator specification: {exc}",
                operation="mt5_analyze",
            )

    # Build chart config.
    chart_config: ChartConfig | None = None
    if chart:
        try:
            panels_in = chart.get("panels") or [{"columns": ["close"]}]
            panels = [
                ChartPanel(
                    columns=p["columns"],
                    style=p.get("style", "line"),
                    y_label=p.get("y_label"),
                    y_limits=p.get("y_limits"),
                    reference_lines=p.get("reference_lines"),
                )
                for p in panels_in
            ]
            chart_config = ChartConfig(
                type=chart.get("type", "single"),
                panels=panels,
                title=chart.get("title"),
                filename=chart.get("filename", "chart.png"),
                width=int(chart.get("width", 14)),
                height=int(chart.get("height", 8)),
                dpi=int(chart.get("dpi", 120)),
            )
        except Exception as exc:
            return _error(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"Invalid chart configuration: {exc}",
                operation="mt5_analyze",
            )

    # Build forecast config.
    forecast_config: ForecastConfig | None = None
    if forecast:
        try:
            forecast_config = ForecastConfig(
                periods=int(forecast.get("periods", 30)),
                include_history=bool(forecast.get("include_history", False)),
                freq=forecast.get("freq"),
                uncertainty_samples=int(forecast.get("uncertainty_samples", 1000)),
                seasonality_mode=forecast.get("seasonality_mode", "additive"),
                growth=forecast.get("growth", "linear"),
                plot=bool(forecast.get("plot", True)),
                plot_components=bool(forecast.get("plot_components", False)),
                enable_ml_prediction=bool(forecast.get("enable_ml_prediction", False)),
                ml_lookback=int(forecast.get("ml_lookback", 50)),
            )
        except Exception as exc:
            return _error(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"Invalid forecast configuration: {exc}",
                operation="mt5_analyze",
            )

    if output_format not in ("markdown", "json", "chart_only"):
        return _error(
            error_type=ErrorType.VALIDATION_ERROR,
            message=(
                f"output_format must be one of markdown|json|chart_only, got {output_format!r}"
            ),
            operation="mt5_analyze",
        )

    request = MT5AnalysisRequest(
        query=MT5QueryRequest(
            operation=op_enum,
            symbol=symbol,
            parameters=params_dict or {},
        ),
        indicators=indicator_specs,
        chart=chart_config,
        forecast=forecast_config,
        output_format=output_format,
        tail=tail,
    )

    try:
        response = handle_mt5_analysis(request)
        return format_response(response.model_dump())
    except Exception as exc:
        logger.exception("mt5_analyze failed")
        return _error(
            error_type=ErrorType.CALCULATION_ERROR,
            message=f"Analysis failed: {exc}",
            operation="mt5_analyze",
            details={"exception_type": type(exc).__name__, "symbol": symbol},
        )


# ---------------------------------------------------------------------------
# mt5_execute — ad-hoc Python in the curated namespace
# ---------------------------------------------------------------------------


def mt5_execute(
    command: str,
    show_traceback: bool = True,
    ctx: Context | None = None,
) -> str:
    """Execute a snippet of Python inside the curated MT5 namespace.

    This is the escape hatch for workflows that the structured tools don't
    cover. Use ``mt5_query`` or ``mt5_analyze`` first; only reach for
    ``mt5_execute`` when you need bespoke calculations.

    Critical rules (enforced by the safe namespace and the blocklist below):
        * The MT5 connection is pre-managed. **Never** call
          ``mt5.initialize()`` or ``mt5.shutdown()`` — those calls will be
          rejected.
        * Trading functions (``order_send``, ``order_check``, position
          mutation) are excluded from the namespace and blocked in the
          blocklist.
        * Assign the final value to a variable called ``result`` (or any of
          ``data`` / ``output`` / ``res``) so the executor returns it.

    Args:
        command: Python source to execute. Must parse with ``ast.parse``.
        show_traceback: When ``True`` (default), surface full Python
            tracebacks on error. Set to ``False`` for cleaner LLM-facing
            messages.
        ctx: FastMCP Context (injected automatically; do not pass).

    Returns:
        A pre-formatted text string. ``mt5_execute`` is excluded from the
        TOON shape heuristic — its output is already a human-readable
        string (markdown table, JSON snippet, or plain text) and TOON
        would only add encoding overhead.
    """
    if not isinstance(command, str) or not command.strip():
        return format_json_response(
            create_error_response(
                ErrorType.VALIDATION_ERROR,
                "command must be a non-empty string",
                operation="mt5_execute",
            )
        )

    if len(command) > MAX_EXECUTE_COMMAND_BYTES:
        return format_json_response(
            create_error_response(
                ErrorType.VALIDATION_ERROR,
                f"command too long: {len(command)} chars (max {MAX_EXECUTE_COMMAND_BYTES})",
                operation="mt5_execute",
            )
        )

    # Blocklist check — defense-in-depth on top of the curated namespace.
    for needle in _DANGEROUS_PATTERNS:
        if needle in command:
            return format_json_response(
                create_error_response(
                    ErrorType.VALIDATION_ERROR,
                    f"Disallowed operation: {needle!r}",
                    operation="mt5_execute",
                    details={"pattern": needle},
                )
            )

    # Make sure MT5 is up before we hand the snippet to the executor.
    err = _ensure_connection()
    if err is not None:
        return format_json_response(
            create_error_response(
                ErrorType.MT5_CONNECTION,
                err,
                operation="mt5_execute",
            )
        )

    try:
        namespace = get_safe_namespace()
    except Exception as exc:
        return format_json_response(
            create_error_response(
                ErrorType.MT5_CONNECTION,
                f"Failed to initialize execution namespace: {exc}",
                operation="mt5_execute",
            )
        )

    from .executor import execute_command

    try:
        return execute_command(command, namespace, show_traceback=show_traceback)
    except SyntaxError as exc:
        return format_json_response(
            create_error_response(
                ErrorType.VALIDATION_ERROR,
                f"Syntax error: {exc}",
                operation="mt5_execute",
            )
        )
    except Exception as exc:
        logger.exception("mt5_execute failed")
        if show_traceback:
            import traceback

            return (
                "Error executing mt5_execute command:\n\n" + traceback.format_exc()
            )
        return format_json_response(
            create_error_response(
                ErrorType.OPERATION_ERROR,
                f"{type(exc).__name__}: {exc}",
                operation="mt5_execute",
            )
        )


__all__ = ["mt5_analyze", "mt5_execute", "mt5_query"]
