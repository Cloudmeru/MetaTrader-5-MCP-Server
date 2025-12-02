"""Handlers for universal MT5 operations."""

import os
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ta
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from urllib.parse import quote

from .models import (
    MT5QueryRequest,
    MT5QueryResponse,
    MT5AnalysisRequest,
    MT5AnalysisResponse,
    IndicatorSpec,
    ChartConfig,
    ForecastConfig,
)
from .errors import (
    MT5ValidationError,
    MT5SymbolNotFoundError,
    MT5DataError,
    MT5CalculationError,
    MT5OperationError,
)
from .validators import (
    validate_symbol,
    convert_timeframe,
    convert_order_type,
    validate_and_adjust_volume,
    validate_ta_function,
)


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


def _get_chart_save_path(filename: str) -> Path:
    """Get absolute path for chart file in current working directory.

    Args:
        filename: Chart filename

    Returns:
        Absolute Path object in current working directory
    """
    cwd = os.getcwd()
    return Path(cwd) / filename


logger = logging.getLogger(__name__)

OSCILLATOR_KEYWORDS = ["rsi", "stoch", "cci", "willr", "mfi", "roc"]
MA_KEYWORDS = ["sma", "ema", "wma", "dema", "tema", "kama", "ma_"]


# ============================================================================
# OPERATION MAPPING
# ============================================================================

OPERATION_MAP = {
    "copy_rates_from": mt5.copy_rates_from,
    "copy_rates_from_pos": mt5.copy_rates_from_pos,
    "copy_rates_range": mt5.copy_rates_range,
    "copy_ticks_from": mt5.copy_ticks_from,
    "copy_ticks_range": mt5.copy_ticks_range,
    "symbol_info": mt5.symbol_info,
    "symbol_info_tick": mt5.symbol_info_tick,
    "symbol_select": mt5.symbol_select,
    "symbols_total": mt5.symbols_total,
    "symbols_get": mt5.symbols_get,
    "account_info": mt5.account_info,
    "terminal_info": mt5.terminal_info,
    "version": mt5.version,
    "order_calc_margin": mt5.order_calc_margin,
    "order_calc_profit": mt5.order_calc_profit,
}


def _prepare_operation_params(request: MT5QueryRequest) -> Dict[str, Any]:
    """Build and validate parameters for an MT5 operation."""

    # Validate request
    if not request:
        raise MT5ValidationError("Request cannot be None")

    # Validate parameters is dict or None
    if request.parameters is not None and not isinstance(request.parameters, dict):
        raise MT5ValidationError(
            f"Parameters must be a dictionary or None, got {type(request.parameters).__name__}"
        )

    params = request.parameters.copy() if request.parameters is not None else {}

    if request.symbol:
        is_valid, _symbol_msg, correction = validate_symbol(request.symbol)
        if not is_valid:
            similar_symbol = None
            if correction and isinstance(correction, dict):
                corrected_params = correction.get("corrected_params")
                if corrected_params and isinstance(corrected_params, dict):
                    similar_symbol = corrected_params.get("symbol")
            raise MT5SymbolNotFoundError(request.symbol, similar_symbol)
        params["symbol"] = request.symbol

    if "timeframe" in params:
        try:
            params["timeframe"] = convert_timeframe(params["timeframe"])
        except ValueError as exc:
            raise MT5ValidationError(str(exc)) from exc

    if "order_type" in params:
        try:
            params["order_type"] = convert_order_type(params["order_type"])
        except ValueError as exc:
            raise MT5ValidationError(str(exc)) from exc

    if "volume" in params and request.symbol:
        volume, warning = validate_and_adjust_volume(request.symbol, params["volume"])
        params["volume"] = volume
        if warning:
            logger.info(warning)

    return params


def _invoke_mt5_operation(
    operation_name: str, mt5_func: Callable[..., Any], params: Dict[str, Any]
) -> Any:
    """Execute the mapped MT5 function with validated parameters and thread safety."""
    from .connection import safe_mt5_call

    logger.info("Executing %s with params: %s", operation_name, params)

    # Validate params is a dictionary
    if not isinstance(params, dict):
        raise MT5ValidationError(f"Parameters must be a dictionary, got {type(params).__name__}")

    try:
        if operation_name == "copy_rates_from_pos":
            result = safe_mt5_call(
                mt5_func,
                params.get("symbol"),
                params.get("timeframe"),
                params.get("start_pos", 0),
                params.get("count", 0),
            )
        elif operation_name == "copy_rates_from":
            result = safe_mt5_call(
                mt5_func,
                params.get("symbol"),
                params.get("timeframe"),
                params.get("date_from"),
                params.get("count"),
            )
        elif operation_name == "copy_rates_range":
            result = safe_mt5_call(
                mt5_func,
                params.get("symbol"),
                params.get("timeframe"),
                params.get("date_from"),
                params.get("date_to"),
            )
        elif operation_name == "copy_ticks_from":
            result = safe_mt5_call(
                mt5_func,
                params.get("symbol"),
                params.get("date_from"),
                params.get("count"),
                params.get("flags", mt5.COPY_TICKS_ALL),
            )
        elif operation_name == "copy_ticks_range":
            result = safe_mt5_call(
                mt5_func,
                params.get("symbol"),
                params.get("date_from"),
                params.get("date_to"),
                params.get("flags", mt5.COPY_TICKS_ALL),
            )
        elif operation_name in ["symbol_info", "symbol_info_tick"]:
            result = safe_mt5_call(mt5_func, params.get("symbol"))
        elif operation_name == "symbol_select":
            result = safe_mt5_call(mt5_func, params.get("symbol"), params.get("enable", True))
        elif operation_name == "symbols_get":
            group = params.get("group")
            result = safe_mt5_call(mt5_func, group) if group else safe_mt5_call(mt5_func)
        elif operation_name in ["order_calc_margin", "order_calc_profit"]:
            extra_args: List[Any] = []
            if "sl" in params:
                extra_args.append(params["sl"])
            if "tp" in params:
                extra_args.append(params["tp"])

            result = safe_mt5_call(
                mt5_func,
                params.get("action") or params.get("order_type"),
                params.get("symbol"),
                params.get("volume"),
                params.get("price"),
                *extra_args,
            )
        else:
            result = safe_mt5_call(mt5_func, **params)
    except TypeError as exc:
        raise MT5ValidationError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - MT5 runtime errors
        raise MT5OperationError(
            operation_name,
            str(exc),
            "Check MT5 connection and parameters",
        ) from exc

    if result is None:
        error_code, error_msg = safe_mt5_call(mt5.last_error)
        raise MT5OperationError(
            operation_name,
            f"MT5 returned None. Error code {error_code}: {error_msg}",
            "Verify that the symbol exists and parameters are valid",
        )

    return _convert_result_to_dict(result)


def _convert_result_to_dict(result: Any) -> Any:
    """Convert MT5 responses into JSON-serializable structures."""

    if hasattr(result, "_asdict"):
        return result._asdict()

    if isinstance(result, np.ndarray):
        if result.dtype.names:
            return [dict(zip(result.dtype.names, row)) for row in result]
        return result.tolist()

    if isinstance(result, (list, tuple)):
        if result and hasattr(result[0], "_asdict"):
            return [item._asdict() for item in result]
        return list(result)

    return result


def handle_mt5_query(request: MT5QueryRequest) -> MT5QueryResponse:
    """
    Query MT5 data with structured parameters.

    This function executes MetaTrader 5 operations for retrieving market data,
    symbol information, account details, and performing calculations.

    Args:
        request (MT5QueryRequest): Query request containing operation, symbol, and parameters
            - operation: MT5 operation name (copy_rates_from_pos, symbol_info, etc.)
            - symbol: Trading symbol (e.g., BTCUSD, EURUSD) - required for symbol-specific ops
            - parameters: Operation-specific parameters (e.g., {"timeframe": "H1", "count": 100})

    Returns:
        MT5QueryResponse: Query results containing:
            - success: Boolean indicating operation success
            - data: Query results (list of dicts for rates, dict for info operations)
            - metadata: Request metadata including symbol and parameters
            - operation: Operation name that was executed

    Raises:
        MT5SymbolNotFoundError: Symbol does not exist or is not available
        MT5ValidationError: Invalid operation parameters or data types
        MT5OperationError: MT5 operation failed or returned None
        MT5DataError: MT5 returned unexpected data format

    Examples:
        Get symbol information:
        >>> from mt5_mcp.models import MT5QueryRequest, MT5Operation
        >>> request = MT5QueryRequest(operation=MT5Operation.SYMBOL_INFO, symbol="BTCUSD")
        >>> response = handle_mt5_query(request)
        >>> print(response.data)

        Get historical rates:
        >>> request = MT5QueryRequest(
        ...     operation=MT5Operation.COPY_RATES_FROM_POS,
        ...     symbol="EURUSD",
        ...     parameters={"timeframe": "H1", "start_pos": 0, "count": 100}
        ... )
        >>> response = handle_mt5_query(request)
        >>> print(len(response.data))

        Get account information:
        >>> request = MT5QueryRequest(operation=MT5Operation.ACCOUNT_INFO)
        >>> response = handle_mt5_query(request)
    """
    try:
        # Validate request object
        if not request:
            raise MT5ValidationError("Request cannot be None")

        if not hasattr(request, "operation") or not request.operation:
            raise MT5ValidationError("Request must have a valid operation")

        operation_name = request.operation.value
        params = _prepare_operation_params(request)

        mt5_func = OPERATION_MAP.get(operation_name)
    except (MT5ValidationError, MT5SymbolNotFoundError):
        # Re-raise custom errors
        raise
    except Exception as e:
        # Wrap unexpected errors
        logger.error(f"Error preparing query: {e}", exc_info=True)
        raise MT5ValidationError(f"Failed to prepare query: {str(e)}") from e
    if mt5_func is None:
        raise MT5OperationError(
            operation_name,
            "Operation not found or not allowed",
            f"Available: {', '.join(OPERATION_MAP.keys())}",
        )

    data = _invoke_mt5_operation(operation_name, mt5_func, params)

    return MT5QueryResponse(
        operation=operation_name,
        success=True,
        data=data,
        metadata={
            "symbol": request.symbol,
            "parameters": request.parameters,
        },
    )


def handle_mt5_analysis(request: MT5AnalysisRequest) -> MT5AnalysisResponse:
    """Run MT5 analysis including indicators, charts, and optional forecasting.

    Args:
        request (MT5AnalysisRequest): Includes:
            query: MT5QueryRequest describing the base data retrieval (required).
            indicators: Optional list of IndicatorSpec objects.
            chart: Optional ChartConfig for visualization generation.
            forecast: Optional ForecastConfig for Prophet forecasting.
            output_format: "markdown", "json", or "chart_only" (default: "markdown").
            tail: Optional row count limit for textual outputs.

    Returns:
        MT5AnalysisResponse: Success flag plus data, chart paths, indicators, and metadata.

    Raises:
        MT5DataError: Query returned no data or unsupported format.
        MT5CalculationError: Failed to calculate indicators, charts, or forecasts.
        ValueError: Invalid indicator function or parameters.

    Example:
        >>> from mt5_mcp.models import (
        ...     MT5AnalysisRequest,
        ...     MT5QueryRequest,
        ...     MT5Operation,
        ...     IndicatorSpec,
        ... )
        >>> request = MT5AnalysisRequest(
        ...     query=MT5QueryRequest(
        ...         operation=MT5Operation.COPY_RATES_FROM_POS,
        ...         symbol="BTCUSD",
        ...         parameters={"timeframe": "H1", "count": 100},
        ...     ),
        ...     indicators=[IndicatorSpec(function="ta.momentum.rsi", params={"window": 14})],
        ... )
        >>> handle_mt5_analysis(request)
    """
    try:
        # Validate request object
        if not request:
            raise MT5ValidationError("Request cannot be None")

        if not hasattr(request, "query") or not request.query:
            raise MT5ValidationError("Request must have a valid query")

        logger.info("Execute MT5 analysis: query + indicators + chart + optional forecast")

        query_response = handle_mt5_query(request.query)
    except (MT5ValidationError, MT5DataError, MT5CalculationError):
        # Re-raise custom errors
        raise
    except Exception as e:
        # Wrap unexpected errors
        logger.error(f"Error in analysis setup: {e}", exc_info=True)
        raise MT5CalculationError(
            f"Failed to initialize analysis: {str(e)}",
            "Check request parameters and MT5 connection",
        ) from e
    if isinstance(query_response.data, list):
        df = pd.DataFrame(query_response.data)
    elif isinstance(query_response.data, dict):
        df = pd.DataFrame([query_response.data])
    else:
        raise MT5DataError("Unsupported query response format", "Expected list or dict")

    if df.empty:
        raise MT5DataError("Query returned no data", "Adjust query parameters or timeframe")

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s", errors="coerce")
        df = df.sort_values("time").reset_index(drop=True)

    indicators_calculated: List[str] = []
    if request.indicators:
        for ind_spec in request.indicators:
            try:
                df, col_name = _calculate_indicator(df, ind_spec)
                indicators_calculated.append(col_name)
                logger.info("Calculated indicator: %s", col_name)
            except Exception as exc:
                raise MT5CalculationError(
                    f"Failed to calculate {ind_spec.function}: {exc}",
                    "Verify indicator parameters and data availability",
                ) from exc

    chart_path = None
    if request.chart:
        try:
            chart_path = _generate_chart(
                df,
                request.chart,
                request.query.symbol or "Unknown",
                (
                    request.query.parameters.get("timeframe", "Unknown")
                    if request.query.parameters
                    else "Unknown"
                ),
            )
            logger.info("Chart saved to: %s", chart_path)
        except Exception as exc:
            raise MT5CalculationError(
                f"Failed to generate chart: {exc}",
                "Check that specified columns exist in data",
            ) from exc

    forecast_summary = None
    forecast_chart_path = None
    if request.forecast:
        try:
            forecast_summary, forecast_chart_path = _generate_forecast(
                df,
                request.forecast,
                request.query.symbol or "Unknown",
                (
                    request.query.parameters.get("timeframe", "Unknown")
                    if request.query.parameters
                    else "Unknown"
                ),
            )
            logger.info("Forecast generated: %s periods", request.forecast.periods)
        except Exception as exc:
            logger.warning("Forecast generation failed: %s", exc)
            forecast_summary = {
                "error": str(exc),
                "note": "Forecast skipped due to error",
            }

    output_data = None
    if request.output_format != "chart_only":
        output_df = df.tail(request.tail) if request.tail else df

        if request.output_format == "markdown":
            output_data = output_df.to_markdown(index=False)
        else:
            output_data = output_df.to_dict(orient="records")

    analysis_summary = _generate_analysis_summary(df, request.query.symbol, indicators_calculated)

    return MT5AnalysisResponse(
        success=True,
        data=output_data,
        chart_path=chart_path,
        forecast_chart_path=forecast_chart_path,
        indicators_calculated=indicators_calculated,
        metadata={
            "rows_returned": len(df),
            "columns": list(df.columns),
            "symbol": request.query.symbol,
            "timeframe": (
                request.query.parameters.get("timeframe") if request.query.parameters else None
            ),
            "analysis_summary": analysis_summary,
            "forecast_summary": forecast_summary,
        },
    )


def _generate_analysis_summary(
    df: pd.DataFrame, symbol: str, indicators: List[str]
) -> Dict[str, Any]:
    """Generate dynamic analysis summary based on available data patterns."""

    summary = {
        "symbol": symbol,
        "period": {
            "start": str(df["time"].iloc[0]) if "time" in df.columns else None,
            "end": str(df["time"].iloc[-1]) if "time" in df.columns else None,
            "bars": len(df),
        },
        "data_characteristics": {},
        "statistical_analysis": {},
        "pattern_detection": {},
        "computed_metrics": [],
        "indicators_analyzed": indicators,
    }

    _add_price_action_analysis(df, summary)
    _add_oscillator_analysis(df, summary)
    ma_indicators = _add_moving_average_analysis(df, summary)
    volume_cols = _add_volume_analysis(df, summary)
    _add_band_analysis(df, summary)
    _add_custom_indicator_metrics(df, summary, volume_cols, ma_indicators)
    summary["key_insights"] = _build_analysis_insights(summary)

    return summary


def _add_price_action_analysis(df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    """Populate price-based analytics and volatility regime details."""
    from scipy import stats

    if "close" not in df.columns:
        return

    close_series = df["close"].dropna()
    summary["data_characteristics"]["price"] = {
        "current": float(close_series.iloc[-1]),
        "mean": float(close_series.mean()),
        "median": float(close_series.median()),
        "std_dev": float(close_series.std()),
        "min": float(close_series.min()),
        "max": float(close_series.max()),
        "range": float(close_series.max() - close_series.min()),
    }

    returns = close_series.pct_change().dropna()
    if len(returns) > 0:
        summary["statistical_analysis"]["returns"] = {
            "mean_return": float(returns.mean() * 100),
            "volatility": float(returns.std() * 100),
            "skewness": float(returns.skew()),
            "kurtosis": float(returns.kurtosis()),
            "sharpe_proxy": (float(returns.mean() / returns.std()) if returns.std() > 0 else 0),
        }

        if len(returns) >= 8:
            normality_test = stats.normaltest(returns)
            summary["statistical_analysis"]["distribution"] = {
                "is_normal": bool(normality_test.pvalue > 0.05),
                "p_value": float(normality_test.pvalue),
                "interpretation": (
                    "Returns follow normal distribution"
                    if normality_test.pvalue > 0.05
                    else "Returns show non-normal distribution (fat tails or skewness)"
                ),
            }

    x_axis = np.arange(len(close_series))
    slope, _intercept = np.polyfit(x_axis, close_series, 1)
    r_squared = np.corrcoef(x_axis, close_series)[0, 1] ** 2

    trend_direction = "Upward" if slope > 0 else "Downward"
    explanatory_power = f"{r_squared*100:.1f}%"
    trend_interpretation = f"{trend_direction} trend with {explanatory_power} explanatory power"

    summary["pattern_detection"]["trend"] = {
        "slope": float(slope),
        "strength": float(r_squared),
        "direction": "bullish" if slope > 0 else "bearish",
        "confidence": ("strong" if r_squared > 0.7 else "moderate" if r_squared > 0.4 else "weak"),
        "interpretation": trend_interpretation,
    }

    rolling_window = min(20, len(returns) // 2) if len(returns) > 2 else 1
    if rolling_window > 1:
        rolling_vol = returns.rolling(window=rolling_window).std()
        current_vol = rolling_vol.iloc[-1] if len(rolling_vol) > 0 else returns.std()
        avg_vol = rolling_vol.mean()
        vol_state = (
            "high"
            if current_vol > avg_vol * 1.5
            else "low" if current_vol < avg_vol * 0.5 else "normal"
        )
        vol_vs_avg = ((current_vol / avg_vol) - 1) * 100 if avg_vol else 0.0

        summary["pattern_detection"]["volatility_regime"] = {
            "current": float(current_vol * 100),
            "average": float(avg_vol * 100),
            "state": vol_state,
            "interpretation": f"Current volatility is {vol_vs_avg:+.1f}% vs average",
        }


def _add_oscillator_analysis(df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    """Inspect oscillator-style columns for overbought/oversold signals."""

    for col in df.columns:
        col_lower = col.lower()
        if not any(kw in col_lower for kw in OSCILLATOR_KEYWORDS):
            continue

        values = df[col].dropna()
        if len(values) == 0:
            continue

        current_value = float(values.iloc[-1])
        val_min, val_max = float(values.min()), float(values.max())
        oscillators = summary["pattern_detection"].setdefault("oscillators", [])

        if val_min >= 0 and val_max <= 100:
            state = (
                "overbought"
                if current_value > 70
                else "oversold" if current_value < 30 else "neutral"
            )
        elif val_min >= -100 and val_max <= 100:
            state = (
                "overbought"
                if current_value > 0
                else "oversold" if current_value < -50 else "neutral"
            )
        else:
            percentile = (
                (current_value - val_min) / (val_max - val_min) if val_max > val_min else 0.5
            )
            state = (
                "extreme_high"
                if percentile > 0.8
                else "extreme_low" if percentile < 0.2 else "neutral"
            )

        oscillators.append(
            {
                "indicator": col,
                "value": current_value,
                "state": state,
                "interpretation": f"{col} at {current_value:.2f} indicates {state} conditions",
            }
        )


def _add_moving_average_analysis(df: pd.DataFrame, summary: Dict[str, Any]) -> List[str]:
    """Analyze moving average columns for positioning and crossovers."""

    ma_indicators = [col for col in df.columns if any(kw in col.lower() for kw in MA_KEYWORDS)]
    if not ma_indicators or "close" not in df.columns:
        return ma_indicators

    current_price = df["close"].iloc[-1]
    ma_summary = summary["pattern_detection"].setdefault("moving_averages", [])

    for ma_col in ma_indicators:
        series = df[ma_col].dropna()
        if len(series) == 0:
            continue
        ma_value = series.iloc[-1]
        position = "above" if current_price > ma_value else "below"
        distance_pct = ((current_price / ma_value) - 1) * 100
        ma_summary.append(
            {
                "indicator": ma_col,
                "value": float(ma_value),
                "price_distance_pct": float(distance_pct),
                "position": position,
                "interpretation": f"Price is {abs(distance_pct):.2f}% {position} {ma_col}",
            }
        )

    if len(ma_indicators) >= 2:
        sorted_mas = sorted(
            ma_indicators,
            key=lambda name: (
                int("".join(filter(str.isdigit, name))) if any(c.isdigit() for c in name) else 999
            ),
        )
        crossovers = summary["pattern_detection"].setdefault("crossovers", [])

        for fast, slow in zip(sorted_mas, sorted_mas[1:]):
            if fast not in df.columns or slow not in df.columns or len(df) <= 1:
                continue

            fast_vals = df[fast].dropna()
            slow_vals = df[slow].dropna()
            if len(fast_vals) <= 1 or len(slow_vals) <= 1:
                continue

            crossover_detected = (fast_vals.iloc[-1] > slow_vals.iloc[-1]) != (
                fast_vals.iloc[-2] > slow_vals.iloc[-2]
            )
            if not crossover_detected:
                continue

            cross_type = "bullish" if fast_vals.iloc[-1] > slow_vals.iloc[-1] else "bearish"
            crossover_direction = "above" if cross_type == "bullish" else "below"
            interpretation = (
                f"{cross_type.title()} crossover: {fast} crossed " f"{crossover_direction} {slow}"
            )
            crossovers.append(
                {
                    "type": cross_type,
                    "fast_ma": fast,
                    "slow_ma": slow,
                    "interpretation": interpretation,
                }
            )

    return ma_indicators


def _add_volume_analysis(df: pd.DataFrame, summary: Dict[str, Any]) -> List[str]:
    """Capture insights from available volume columns."""

    volume_cols = [
        col for col in df.columns if "volume" in col.lower() and "real" not in col.lower()
    ]
    if not volume_cols:
        return volume_cols

    vol_col = volume_cols[0]
    volumes = df[vol_col].dropna()
    if len(volumes) == 0:
        return volume_cols

    avg_volume = volumes.mean()
    recent_volume = volumes.iloc[-1]
    volume_change_pct = (((recent_volume / avg_volume) - 1) * 100) if avg_volume else 0.0

    summary["data_characteristics"]["volume"] = {
        "current": float(recent_volume),
        "average": float(avg_volume),
        "relative_strength": float(recent_volume / avg_volume) if avg_volume > 0 else 1,
        "interpretation": f"Volume is {volume_change_pct:+.1f}% vs average",
    }

    return volume_cols


def _add_band_analysis(df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    """Evaluate band/envelope indicators like Bollinger or Keltner."""

    band_patterns = [
        ("bollinger", ["upper", "lower", "middle"]),
        ("keltner", ["upper", "lower", "middle"]),
        ("donchian", ["upper", "lower"]),
    ]

    for band_name, _band_components in band_patterns:
        matching_cols = [col for col in df.columns if band_name in col.lower()]
        if len(matching_cols) < 2 or "close" not in df.columns:
            continue

        upper_col = next((c for c in matching_cols if "upper" in c.lower()), None)
        lower_col = next((c for c in matching_cols if "lower" in c.lower()), None)
        if not upper_col or not lower_col:
            continue

        upper_values = df[upper_col].dropna()
        lower_values = df[lower_col].dropna()
        if len(upper_values) == 0 or len(lower_values) == 0:
            continue

        current_price = df["close"].iloc[-1]
        upper_val, lower_val = upper_values.iloc[-1], lower_values.iloc[-1]
        bandwidth = upper_val - lower_val
        if bandwidth <= 0:
            continue

        position_pct = ((current_price - lower_val) / bandwidth) * 100
        state = (
            "near_upper"
            if position_pct > 80
            else "near_lower" if position_pct < 20 else "middle_range"
        )

        bands = summary["pattern_detection"].setdefault("bands", [])
        band_interpretation = f"Price at {position_pct:.1f}% of {band_name} band range ({state})"
        bands.append(
            {
                "type": band_name.title(),
                "position_percentile": float(position_pct),
                "bandwidth": float(bandwidth),
                "state": state,
                "interpretation": band_interpretation,
            }
        )


def _add_custom_indicator_metrics(
    df: pd.DataFrame,
    summary: Dict[str, Any],
    volume_cols: List[str],
    ma_indicators: List[str],
) -> None:
    """Add summary metrics for columns not covered by other analyses."""

    analyzed_cols = set(["time", "open", "high", "low", "close"] + volume_cols + ma_indicators)
    custom_indicators = [
        col
        for col in df.columns
        if col not in analyzed_cols and not any(kw in col.lower() for kw in OSCILLATOR_KEYWORDS)
    ]

    for col in custom_indicators:
        values = df[col].dropna()
        if len(values) == 0:
            continue

        summary["computed_metrics"].append(
            {
                "name": col,
                "current": float(values.iloc[-1]),
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "max": float(values.max()),
            }
        )


def _build_analysis_insights(summary: Dict[str, Any]) -> List[str]:
    """Generate a concise list of human-readable insights."""

    insights: List[str] = []

    price_data = summary.get("data_characteristics", {}).get("price")
    if price_data:
        price_change_pct = ((price_data["current"] / price_data["mean"]) - 1) * 100
        if abs(price_change_pct) > 10:
            insights.append(f"Price deviation: {price_change_pct:+.1f}% from period average")

    distribution = summary.get("statistical_analysis", {}).get("distribution")
    if distribution and not distribution["is_normal"]:
        insights.append("Non-normal returns distribution detected - consider tail risk")

    trend = summary.get("pattern_detection", {}).get("trend")
    if trend and trend["confidence"] in ["strong", "moderate"]:
        trend_confidence = trend["confidence"].title()
        trend_strength = f"{trend['strength']:.2f}"
        insights.append(
            f"{trend_confidence} {trend['direction']} trend identified (R²={trend_strength})"
        )

    volatility = summary.get("pattern_detection", {}).get("volatility_regime")
    if volatility and volatility["state"] != "normal":
        insights.append(f"{volatility['state'].title()} volatility regime detected")

    oscillators = summary.get("pattern_detection", {}).get("oscillators", [])
    extreme_states = {"overbought", "oversold", "extreme_high", "extreme_low"}
    extreme_oscillators = [o for o in oscillators if o["state"] in extreme_states]
    if extreme_oscillators:
        insights.append(
            f"{len(extreme_oscillators)} momentum indicator(s) showing extreme conditions"
        )

    crossovers = summary.get("pattern_detection", {}).get("crossovers", [])
    for cross in crossovers:
        insights.append(f"Recent {cross['type']} crossover detected")

    return insights


def _calculate_indicator(df: pd.DataFrame, spec: IndicatorSpec) -> Tuple[pd.DataFrame, str]:
    """Calculate technical indicator and add to DataFrame."""

    # Validate TA function
    is_valid, error_msg = validate_ta_function(spec.function)
    if not is_valid:
        raise ValueError(error_msg)

    # Parse function path
    parts = spec.function.split(".")
    module_name = parts[1]  # e.g., 'momentum'
    func_name = parts[2]  # e.g., 'rsi'

    # Get function
    ta_module = getattr(ta, module_name)
    ta_func = getattr(ta_module, func_name)

    # Prepare parameters - most TA functions expect 'close' series
    params = spec.params.copy() if spec.params else {}

    # Common parameter: close series
    if "close" in df.columns:
        # Some functions take Series as first positional arg
        try:
            result = ta_func(df["close"], **params)
        except TypeError:
            # Try passing as 'close' kwarg
            params["close"] = df["close"]
            result = ta_func(**params)
    else:
        raise ValueError("DataFrame must have 'close' column for indicator calculation")

    # Generate column name
    if spec.column_name:
        col_name = spec.column_name
    else:
        # Auto-generate: e.g., "rsi_14"
        param_str = "_".join([str(v) for v in params.values() if isinstance(v, (int, float))])
        col_name = f"{func_name}_{param_str}" if param_str else func_name

    # Add to DataFrame
    df[col_name] = result

    return df, col_name


def _generate_chart(df: pd.DataFrame, config: ChartConfig, symbol: str, timeframe: str) -> str:
    """Generate chart and save to file."""

    num_panels = len(config.panels)

    # Create figure
    fig, axes = plt.subplots(num_panels, 1, figsize=(config.width, config.height), sharex=True)

    # Handle single panel case
    if num_panels == 1:
        axes = [axes]

    # Plot each panel
    for idx, panel in enumerate(config.panels):
        ax = axes[idx]

        # Plot columns
        for col in panel.columns:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in data. Available: {list(df.columns)}")

            if panel.style == "line":
                ax.plot(df.index, df[col], label=col, linewidth=2)
            elif panel.style == "scatter":
                ax.scatter(df.index, df[col], label=col, alpha=0.6)
            elif panel.style == "bar":
                ax.bar(df.index, df[col], label=col, alpha=0.7)

        # Add reference lines
        if panel.reference_lines:
            for ref_val in panel.reference_lines:
                ax.axhline(y=ref_val, color="gray", linestyle="--", alpha=0.5, linewidth=1)

        # Set y-limits
        if panel.y_limits:
            ax.set_ylim(panel.y_limits)

        # Labels and styling
        if panel.y_label:
            ax.set_ylabel(panel.y_label, fontsize=11)
        else:
            ax.set_ylabel(", ".join(panel.columns), fontsize=11)

        ax.legend(loc="best", fontsize=10)
        ax.grid(True, alpha=0.3, linestyle=":")

        # Title for first panel
        if idx == 0:
            title = config.title or f"{symbol} {timeframe} Analysis"
            ax.set_title(title, fontsize=14, fontweight="bold")

    # X-label for bottom panel
    axes[-1].set_xlabel("Bars", fontsize=11)

    fig.tight_layout()

    # Save chart to current working directory
    chart_path = _get_chart_save_path(config.filename)
    fig.savefig(str(chart_path), dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)

    # Return path with clickable hyperlink
    hyperlink = _format_file_hyperlink(str(chart_path))
    logger.info("Chart saved: %s", hyperlink)
    return str(chart_path)


def _prepare_ml_dataset(
    df: pd.DataFrame, lookback: int
) -> Tuple[pd.DataFrame, List[str]] | Dict[str, Any]:
    """Build feature DataFrame and feature list for ML signal inference."""

    required_bars = lookback + 10
    if len(df) < required_bars:
        reasoning = (
            "Insufficient data for ML prediction (need " f"{required_bars} bars, have {len(df)})"
        )
        return {"signal": "NEUTRAL", "confidence": 0.0, "reasoning": reasoning}

    features_df = df.copy()
    features_df["returns"] = features_df["close"].pct_change()
    features_df["high_low_ratio"] = features_df["high"] / features_df["low"]
    features_df["close_open_ratio"] = features_df["close"] / features_df["open"]

    for window in [5, 10, 20]:
        features_df[f"return_mean_{window}"] = features_df["returns"].rolling(window).mean()
        features_df[f"return_std_{window}"] = features_df["returns"].rolling(window).std()
        features_df[f"volume_mean_{window}"] = (
            features_df["tick_volume"].rolling(window).mean()
            if "tick_volume" in features_df.columns
            else 0
        )

    indicator_cols = []
    for col in features_df.columns:
        if any(ind in col.lower() for ind in ["rsi", "macd", "sma", "ema", "bb", "atr"]):
            indicator_cols.append(col)

    features_df["future_return"] = features_df["close"].shift(-3) / features_df["close"] - 1
    features_df["label"] = (features_df["future_return"] > 0).astype(int)
    features_df = features_df.dropna()

    if len(features_df) < lookback:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.0,
            "reasoning": "Insufficient valid data after feature engineering",
        }

    feature_cols = [
        col
        for col in features_df.columns
        if col.startswith(("return_", "high_low", "close_open", "volume_"))
    ]
    feature_cols.extend(indicator_cols)

    if not feature_cols:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.0,
            "reasoning": "No valid features available for ML model",
        }

    return features_df, feature_cols


def _train_ml_model(
    features_df: pd.DataFrame,
    feature_cols: List[str],
    xgb_module,
    scaler_cls,
) -> Dict[str, Any]:
    """Train XGBoost model and derive trading signal insights."""

    train_features = features_df[feature_cols].iloc[:-1].values
    train_labels = features_df["label"].iloc[:-1].values
    prediction_features = features_df[feature_cols].iloc[-1:].values

    scaler = scaler_cls()
    scaled_train = scaler.fit_transform(train_features)
    scaled_prediction = scaler.transform(prediction_features)

    model = xgb_module.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective="binary:logistic",
        random_state=42,
        eval_metric="logloss",
    )
    model.fit(scaled_train, train_labels, verbose=False)

    pred_proba = model.predict_proba(scaled_prediction)[0]
    buy_confidence = float(pred_proba[1])
    sell_confidence = float(pred_proba[0])

    if buy_confidence > 0.6:
        signal = "BUY"
        confidence = buy_confidence
        reasoning = "ML model predicts upward price movement with " f"{confidence:.1%} confidence"
    elif sell_confidence > 0.6:
        signal = "SELL"
        confidence = sell_confidence
        reasoning = "ML model predicts downward price movement with " f"{confidence:.1%} confidence"
    else:
        signal = "NEUTRAL"
        confidence = max(buy_confidence, sell_confidence)
        reasoning = (
            "ML model shows mixed signals "
            f"(BUY: {buy_confidence:.1%}, SELL: {sell_confidence:.1%})"
        )

    feature_importance = dict(zip(feature_cols, model.feature_importances_))
    top_features = sorted(feature_importance.items(), key=lambda item: item[1], reverse=True)[:3]
    top_feature_names = [feature for feature, _score in top_features]
    reasoning += f". Key factors: {', '.join(top_feature_names)}"

    return {
        "signal": signal,
        "confidence": confidence,
        "buy_probability": buy_confidence,
        "sell_probability": sell_confidence,
        "reasoning": reasoning,
        "features_used": len(feature_cols),
        "training_samples": len(train_features),
    }


def _generate_ml_signal(df: pd.DataFrame, lookback: int = 50) -> Dict[str, Any]:
    """
    Generate buy/sell signal using XGBoost ML model.

    Args:
        df: DataFrame with OHLCV data and technical indicators
        lookback: Number of bars to use for feature engineering

    Returns:
        Dictionary with signal, confidence, and reasoning
    """
    try:
        import xgboost as xgb
        from sklearn.preprocessing import StandardScaler

        dataset = _prepare_ml_dataset(df, lookback)
        if isinstance(dataset, dict):
            return dataset

        features_df, feature_cols = dataset
        return _train_ml_model(features_df, feature_cols, xgb, StandardScaler)

    except Exception as e:
        logger.warning("ML signal generation failed: %s", e)
        return {
            "signal": "ERROR",
            "confidence": 0.0,
            "reasoning": f"ML prediction error: {str(e)}",
        }


def _generate_forecast(
    df: pd.DataFrame, config: "ForecastConfig", symbol: str, timeframe: str
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Generate Prophet-based forecast with optional ML signal and charts."""

    from prophet import Prophet

    if "close" not in df.columns:
        raise ValueError("DataFrame must have 'close' column for forecasting")

    if len(df) < 10:
        raise ValueError(f"Insufficient data for forecasting: {len(df)} rows (minimum 10 required)")

    prophet_df = _build_prophet_dataframe(df)
    model = Prophet(
        growth=config.growth,
        seasonality_mode=config.seasonality_mode,
        uncertainty_samples=config.uncertainty_samples,
        daily_seasonality="auto",
        weekly_seasonality="auto",
        yearly_seasonality="auto",
    )

    logger.info("Training Prophet model on %s data points...", len(prophet_df))
    model.fit(prophet_df)

    freq = _resolve_forecast_frequency(df, config)
    future = model.make_future_dataframe(
        periods=config.periods,
        freq=freq,
        include_history=config.include_history,
    )

    logger.info("Generating %s-period forecast with frequency=%s...", config.periods, freq)
    forecast = model.predict(future)

    forecast_summary = _summarize_forecast_results(forecast, config, prophet_df, freq)

    if config.enable_ml_prediction:
        _add_ml_prediction_if_enabled(forecast_summary, df, config)

    chart_path = _maybe_generate_forecast_chart(model, forecast, symbol, timeframe, config)
    _maybe_generate_components_chart(model, forecast, symbol, timeframe, config, forecast_summary)

    return forecast_summary, chart_path


def _build_prophet_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Create Prophet-compatible dataframe with ds/y columns."""

    if "time" in df.columns:
        date_series = pd.to_datetime(df["time"], errors="coerce")
    else:
        date_series = pd.date_range(start="2024-01-01", periods=len(df), freq="D")

    return pd.DataFrame({"ds": date_series, "y": df["close"]})


def _resolve_forecast_frequency(df: pd.DataFrame, config: "ForecastConfig") -> str:
    """Determine forecast frequency, honoring config override when provided."""

    if config.freq:
        freq = config.freq
    elif "time" in df.columns and len(df) > 1:
        time_diff = (df["time"].iloc[-1] - df["time"].iloc[-2]).total_seconds()
        if time_diff <= 3600:
            freq = "h"
        elif time_diff <= 86400:
            freq = "D"
        else:
            freq = "W"
    else:
        freq = "D"

    freq_map = {"H": "h", "T": "min", "M": "min"}
    return freq_map.get(freq, freq)


def _summarize_forecast_results(
    forecast: pd.DataFrame,
    config: "ForecastConfig",
    prophet_df: pd.DataFrame,
    freq: str,
) -> Dict[str, Any]:
    """Convert raw Prophet output into structured summary and insights."""

    if config.include_history:
        forecast_data = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].to_dict(
            orient="records"
        )
    else:
        forecast_data = (
            forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
            .tail(config.periods)
            .to_dict(orient="records")
        )

    future_forecast = forecast.tail(config.periods)
    mean_forecast = future_forecast["yhat"].mean()
    trend_direction = (
        "bullish"
        if future_forecast["yhat"].iloc[-1] > future_forecast["yhat"].iloc[0]
        else "bearish"
    )
    confidence_range = (future_forecast["yhat_upper"] - future_forecast["yhat_lower"]).mean()

    last_actual = prophet_df["y"].iloc[-1]
    last_forecast = future_forecast["yhat"].iloc[-1]
    predicted_change_pct = ((last_forecast - last_actual) / last_actual) * 100

    summary = {
        "periods_forecasted": config.periods,
        "frequency": freq,
        "model": {
            "growth": config.growth,
            "seasonality_mode": config.seasonality_mode,
            "uncertainty_samples": config.uncertainty_samples,
        },
        "predictions": {
            "last_actual_price": float(last_actual),
            "final_forecast_price": float(last_forecast),
            "predicted_change_pct": float(predicted_change_pct),
            "mean_forecast": float(mean_forecast),
            "trend_direction": trend_direction,
        },
        "uncertainty": {
            "avg_confidence_range": float(confidence_range),
            "final_lower_bound": float(future_forecast["yhat_lower"].iloc[-1]),
            "final_upper_bound": float(future_forecast["yhat_upper"].iloc[-1]),
        },
        "forecast_data": forecast_data,
    }

    insights = []
    if abs(predicted_change_pct) > 5:
        insights.append(
            f"Significant {trend_direction} movement expected: {predicted_change_pct:+.2f}%"
        )
    elif abs(predicted_change_pct) < 1:
        insights.append(f"Price expected to remain relatively stable: {predicted_change_pct:+.2f}%")
    else:
        insights.append(f"Moderate {trend_direction} trend expected: {predicted_change_pct:+.2f}%")

    if confidence_range / last_actual > 0.1:
        insights.append("High uncertainty in predictions (wide confidence intervals)")
    else:
        insights.append("Moderate confidence in predictions")

    summary["insights"] = insights
    return summary


def _add_ml_prediction_if_enabled(
    forecast_summary: Dict[str, Any], df: pd.DataFrame, config: "ForecastConfig"
) -> None:
    """Append ML trading signal details to forecast summary when requested."""

    logger.info("Generating XGBoost ML trading signal with lookback=%s...", config.ml_lookback)
    ml_signal = _generate_ml_signal(df, lookback=config.ml_lookback)
    forecast_summary["ml_trading_signal"] = ml_signal

    if ml_signal["signal"] != "ERROR":
        ml_insight = (
            f"ML Signal: {ml_signal['signal']} "
            f"({ml_signal['confidence']:.1%} confidence) - "
            f"{ml_signal['reasoning']}"
        )
        forecast_summary.setdefault("insights", []).append(ml_insight)


def _maybe_generate_forecast_chart(
    model,
    forecast: pd.DataFrame,
    symbol: str,
    timeframe: str,
    config: "ForecastConfig",
) -> Optional[str]:
    """Create forecast chart if enabled, returning file path."""

    if not config.plot:
        return None

    try:
        fig = model.plot(forecast, figsize=(14, 6))
        ax = fig.gca()
        ax.set_title(
            f"{symbol} {timeframe} - Prophet Forecast ({config.periods} periods)",
            fontsize=14,
            fontweight="bold",
        )
        ax.set_xlabel("Date", fontsize=11)
        ax.set_ylabel("Price", fontsize=11)
        ax.grid(True, alpha=0.3, linestyle=":")

        chart_filename = f"forecast_{symbol}_{timeframe}.png"
        chart_path_obj = _get_chart_save_path(chart_filename)
        fig.savefig(str(chart_path_obj), dpi=120, bbox_inches="tight")
        plt.close(fig)

        chart_path = str(chart_path_obj)
        hyperlink = _format_file_hyperlink(chart_path)
        logger.info("Forecast chart saved: %s", hyperlink)
        return chart_path

    except Exception as exc:
        logger.warning("Failed to generate forecast chart: %s", exc)
        return None


def _maybe_generate_components_chart(
    model,
    forecast: pd.DataFrame,
    symbol: str,
    timeframe: str,
    config: "ForecastConfig",
    forecast_summary: Dict[str, Any],
) -> None:
    """Create forecast components chart if enabled."""

    if not config.plot_components:
        return

    try:
        fig = model.plot_components(forecast, figsize=(14, 8))
        components_filename = f"forecast_components_{symbol}_{timeframe}.png"
        components_path_obj = _get_chart_save_path(components_filename)
        fig.savefig(str(components_path_obj), dpi=120, bbox_inches="tight")
        plt.close(fig)

        forecast_summary["components_chart_path"] = str(components_path_obj)
        hyperlink = _format_file_hyperlink(str(components_path_obj))
        logger.info("Forecast components chart saved: %s", hyperlink)

    except Exception as exc:
        logger.warning("Failed to generate components chart: %s", exc)
