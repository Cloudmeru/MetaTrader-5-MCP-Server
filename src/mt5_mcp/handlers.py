"""Handlers for universal MT5 operations."""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ta
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from .models import (
    MT5QueryRequest, MT5QueryResponse,
    MT5AnalysisRequest, MT5AnalysisResponse,
    IndicatorSpec, ChartPanel, ChartConfig
)
from .errors import (
    MT5ValidationError, MT5SymbolNotFoundError,
    MT5DataError, MT5CalculationError, MT5OperationError
)
from .validators import (
    validate_symbol, validate_operation_parameters,
    convert_timeframe, convert_order_type,
    validate_and_adjust_volume, validate_indicator_data_requirements,
    validate_ta_function
)

logger = logging.getLogger(__name__)


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


# ============================================================================
# QUERY HANDLER
# ============================================================================

def handle_mt5_query(request: MT5QueryRequest) -> MT5QueryResponse:
    """Execute MT5 query operation."""
    
    operation_name = request.operation.value
    params = request.parameters.copy() if request.parameters else {}
    
    # Validate symbol if provided
    if request.symbol:
        is_valid, error_msg, correction = validate_symbol(request.symbol)
        if not is_valid:
            similar_symbol = None
            if correction and isinstance(correction, dict):
                corrected_params = correction.get("corrected_params")
                if corrected_params and isinstance(corrected_params, dict):
                    similar_symbol = corrected_params.get("symbol")
            raise MT5SymbolNotFoundError(request.symbol, similar_symbol)
        params["symbol"] = request.symbol
    
    # Convert timeframe if present
    if "timeframe" in params:
        try:
            params["timeframe"] = convert_timeframe(params["timeframe"])
        except ValueError as e:
            raise MT5ValidationError(str(e))
    
    # Convert order_type if present
    if "order_type" in params:
        try:
            params["order_type"] = convert_order_type(params["order_type"])
        except ValueError as e:
            raise MT5ValidationError(str(e))
    
    # Validate and adjust volume if present
    if "volume" in params and request.symbol:
        volume, warning = validate_and_adjust_volume(request.symbol, params["volume"])
        params["volume"] = volume
        if warning:
            logger.info(warning)
    
    # Get MT5 function
    mt5_func = OPERATION_MAP.get(operation_name)
    if mt5_func is None:
        raise MT5OperationError(
            operation_name,
            "Operation not found or not allowed",
            f"Available: {', '.join(OPERATION_MAP.keys())}"
        )
    
    # Execute operation
    try:
        logger.info(f"Executing {operation_name} with params: {params}")
        
        # Build args based on operation (MT5 functions use positional args)
        if operation_name in ["copy_rates_from_pos", "copy_rates_range", "copy_rates_from"]:
            # These take: symbol, timeframe, start_pos/start_time, count
            result = mt5_func(
                params.get("symbol"),
                params.get("timeframe"),
                params.get("start_pos") or params.get("date_from") or params.get("date_to", 0),
                params.get("count") or params.get("date_to")
            )
        elif operation_name in ["copy_ticks_from", "copy_ticks_range"]:
            # Ticks functions
            result = mt5_func(
                params.get("symbol"),
                params.get("date_from") or params.get("date_to"),
                params.get("count") or params.get("date_to"),
                params.get("flags", mt5.COPY_TICKS_ALL)
            )
        elif operation_name in ["symbol_info", "symbol_info_tick"]:
            result = mt5_func(params.get("symbol"))
        elif operation_name == "symbol_select":
            result = mt5_func(params.get("symbol"), params.get("enable", True))
        elif operation_name == "symbols_get":
            group = params.get("group", "")
            result = mt5_func(group) if group else mt5_func()
        elif operation_name in ["order_calc_margin", "order_calc_profit"]:
            result = mt5_func(
                params.get("action") or params.get("order_type"),
                params.get("symbol"),
                params.get("volume"),
                params.get("price"),
                *([params.get("sl")] if "sl" in params else []),
                *([params.get("tp")] if "tp" in params else [])
            )
        else:
            # Try keyword args for other functions
            result = mt5_func(**params)
        
        # Check for MT5 errors
        if result is None:
            error = mt5.last_error()
            raise MT5OperationError(
                operation_name,
                f"MT5 returned None. Error code: {error}",
                "Check if symbol exists and parameters are valid"
            )
        
        # Convert result to serializable format
        data = _convert_result_to_dict(result)
        
        return MT5QueryResponse(
            operation=operation_name,
            success=True,
            data=data,
            metadata={
                "symbol": request.symbol,
                "parameters": request.parameters
            }
        )
        
    except Exception as e:
        if isinstance(e, (MT5ValidationError, MT5OperationError)):
            raise
        raise MT5OperationError(
            operation_name,
            str(e),
            "Check parameters and MT5 connection"
        )


def _convert_result_to_dict(result: Any) -> Any:
    """Convert MT5 result to JSON-serializable format."""
    
    # Handle NamedTuple (symbol_info, account_info, etc.)
    if hasattr(result, '_asdict'):
        return result._asdict()
    
    # Handle numpy array (rates, ticks)
    if isinstance(result, np.ndarray):
        return [dict(zip(result.dtype.names, row)) for row in result]
    
    # Handle list/tuple of objects
    if isinstance(result, (list, tuple)):
        if len(result) > 0 and hasattr(result[0], '_asdict'):
            return [item._asdict() for item in result]
        return list(result)
    
    # Primitives
    return result


# ============================================================================
# ANALYSIS HANDLER
# ============================================================================

def handle_mt5_analysis(request: MT5AnalysisRequest) -> MT5AnalysisResponse:
    """Execute MT5 analysis: query + indicators + chart."""
    
    # Step 1: Query data
    query_response = handle_mt5_query(request.query)
    
    # Convert to DataFrame
    if isinstance(query_response.data, list):
        df = pd.DataFrame(query_response.data)
    else:
        raise MT5DataError(
            "Query did not return tabular data",
            "Use operations like copy_rates_from_pos for analysis"
        )
    
    if df.empty:
        raise MT5DataError(
            "Query returned no data",
            "Check if symbol exists and date range is valid"
        )
    
    logger.info(f"Query returned {len(df)} rows")
    
    # Convert time column if present
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], unit='s')
    
    indicators_calculated = []
    
    # Step 2: Calculate indicators
    if request.indicators:
        for ind_spec in request.indicators:
            try:
                df, col_name = _calculate_indicator(df, ind_spec)
                indicators_calculated.append(col_name)
                logger.info(f"Calculated indicator: {col_name}")
            except Exception as e:
                raise MT5CalculationError(
                    f"Failed to calculate {ind_spec.function}: {str(e)}",
                    f"Check that DataFrame has 'close' column and sufficient data"
                )
    
    # Step 3: Generate chart
    chart_path = None
    if request.chart:
        try:
            chart_path = _generate_chart(
                df,
                request.chart,
                request.query.symbol or "Chart",
                request.query.parameters.get("timeframe", "Unknown") if request.query.parameters else "Unknown"
            )
            logger.info(f"Chart saved to: {chart_path}")
        except Exception as e:
            raise MT5CalculationError(
                f"Failed to generate chart: {str(e)}",
                "Check that specified columns exist in data"
            )
    
    # Step 4: Format output
    output_data = None
    if request.output_format != "chart_only":
        # Apply tail if specified
        output_df = df.tail(request.tail) if request.tail else df
        
        if request.output_format == "markdown":
            output_data = output_df.to_markdown(index=False)
        else:  # json
            output_data = output_df.to_dict(orient='records')
    
    return MT5AnalysisResponse(
        success=True,
        data=output_data,
        chart_path=chart_path,
        indicators_calculated=indicators_calculated,
        metadata={
            "rows_returned": len(df),
            "columns": list(df.columns),
            "symbol": request.query.symbol,
            "timeframe": request.query.parameters.get("timeframe") if request.query.parameters else None
        }
    )


def _calculate_indicator(df: pd.DataFrame, spec: IndicatorSpec) -> Tuple[pd.DataFrame, str]:
    """Calculate technical indicator and add to DataFrame."""
    
    # Validate TA function
    is_valid, error_msg = validate_ta_function(spec.function)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Parse function path
    parts = spec.function.split('.')
    module_name = parts[1]  # e.g., 'momentum'
    func_name = parts[2]     # e.g., 'rsi'
    
    # Get function
    ta_module = getattr(ta, module_name)
    ta_func = getattr(ta_module, func_name)
    
    # Prepare parameters - most TA functions expect 'close' series
    params = spec.params.copy() if spec.params else {}
    
    # Common parameter: close series
    if 'close' in df.columns:
        # Some functions take Series as first positional arg
        try:
            result = ta_func(df['close'], **params)
        except TypeError:
            # Try passing as 'close' kwarg
            params['close'] = df['close']
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


def _generate_chart(
    df: pd.DataFrame,
    config: ChartConfig,
    symbol: str,
    timeframe: str
) -> str:
    """Generate chart and save to file."""
    
    num_panels = len(config.panels)
    
    # Create figure
    fig, axes = plt.subplots(
        num_panels, 1,
        figsize=(config.width, config.height),
        sharex=True
    )
    
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
                ax.axhline(y=ref_val, color='gray', linestyle='--', alpha=0.5, linewidth=1)
        
        # Set y-limits
        if panel.y_limits:
            ax.set_ylim(panel.y_limits)
        
        # Labels and styling
        if panel.y_label:
            ax.set_ylabel(panel.y_label, fontsize=11)
        else:
            ax.set_ylabel(', '.join(panel.columns), fontsize=11)
        
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle=':')
        
        # Title for first panel
        if idx == 0:
            title = config.title or f"{symbol} {timeframe} Analysis"
            ax.set_title(title, fontsize=14, fontweight='bold')
    
    # X-label for bottom panel
    axes[-1].set_xlabel('Bars', fontsize=11)
    
    plt.tight_layout()
    
    # Save chart
    chart_path = Path(config.filename).absolute()
    plt.savefig(str(chart_path), dpi=config.dpi, bbox_inches='tight')
    plt.close()
    
    return str(chart_path)
