"""Validators for MT5 operations and parameters."""

import MetaTrader5 as mt5
import inspect
import logging
from typing import Tuple, Optional, Dict, Any, List
from functools import lru_cache
import difflib

logger = logging.getLogger(__name__)


# ============================================================================
# CACHING
# ============================================================================


def get_symbol_info_cached(symbol: str) -> Optional[Any]:
    """Get symbol info with caching (doesn't cache None to avoid stale failures)."""
    # Check if already in cache
    cache_key = symbol
    if hasattr(get_symbol_info_cached, "_cache"):
        if cache_key in get_symbol_info_cached._cache:
            return get_symbol_info_cached._cache[cache_key]
    else:
        get_symbol_info_cached._cache = {}

    # Query MT5
    info = mt5.symbol_info(symbol)

    # Only cache successful results (not None)
    if info is not None:
        get_symbol_info_cached._cache[cache_key] = info

    return info


@lru_cache(maxsize=32)
def get_all_symbols_cached() -> List[str]:
    """Get all symbol names with caching."""
    symbols = mt5.symbols_get()
    if symbols:
        return [s.name for s in symbols]
    return []


def clear_symbol_cache():
    """Clear symbol cache (call if symbols updated)."""
    if hasattr(get_symbol_info_cached, "_cache"):
        get_symbol_info_cached._cache.clear()
    get_all_symbols_cached.cache_clear()


# ============================================================================
# SYMBOL VALIDATION
# ============================================================================


def validate_symbol(
    symbol: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate symbol exists in MT5.

    Returns:
        (is_valid, error_message, correction_dict)
    """
    symbol = symbol.strip().upper()

    # Check if symbol exists
    symbol_info = get_symbol_info_cached(symbol)
    if symbol_info is None:
        # Find similar symbols
        all_symbols = get_all_symbols_cached()
        similar = difflib.get_close_matches(symbol, all_symbols, n=3, cutoff=0.6)

        error_msg = f"Symbol '{symbol}' not found."
        if similar:
            suggestion = f"Did you mean: {', '.join(similar)}?"
            corrected = {"symbol": similar[0]}
        else:
            suggestion = "Use 'symbols_get' operation to list available symbols."
            corrected = None

        return (
            False,
            error_msg,
            {"suggestion": suggestion, "corrected_params": corrected},
        )

    return True, None, None


# ============================================================================
# PARAMETER VALIDATION
# ============================================================================


@lru_cache(maxsize=64)
def get_function_signature(operation_name: str) -> Optional[inspect.Signature]:
    """Get MT5 function signature with caching."""
    try:
        func = getattr(mt5, operation_name, None)
        if func and callable(func):
            return inspect.signature(func)
    except Exception as e:
        logger.warning(f"Failed to get signature for {operation_name}: {e}")
    return None


def validate_operation_parameters(
    operation_name: str, provided_params: Dict[str, Any]
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate parameters for MT5 operation.

    Returns:
        (is_valid, error_message, suggestion_dict)
    """
    sig = get_function_signature(operation_name)
    if sig is None:
        return True, None, None  # Can't validate, allow operation to fail naturally

    try:
        # Get required parameters
        required_params = []
        optional_params = []

        for param_name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty and param_name != "self":
                required_params.append(param_name)
            else:
                optional_params.append(param_name)

        # Check for missing required parameters
        missing = [p for p in required_params if p not in provided_params]
        if missing:
            error_msg = f"Missing required parameters: {', '.join(missing)}"
            suggestion = f"Add: {', '.join([f'{p}=<value>' for p in missing])}"
            return False, error_msg, {"suggestion": suggestion}

        # Check for unknown parameters
        all_params = required_params + optional_params
        unknown = [p for p in provided_params if p not in all_params]
        if unknown:
            error_msg = f"Unknown parameters: {', '.join(unknown)}"
            suggestion = f"Valid parameters: {', '.join(all_params)}"
            return False, error_msg, {"suggestion": suggestion}

        return True, None, None

    except Exception as e:
        logger.error(f"Parameter validation error for {operation_name}: {e}")
        return True, None, None  # Allow operation to proceed


# ============================================================================
# TIMEFRAME CONVERSION
# ============================================================================

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M2": mt5.TIMEFRAME_M2,
    "M3": mt5.TIMEFRAME_M3,
    "M4": mt5.TIMEFRAME_M4,
    "M5": mt5.TIMEFRAME_M5,
    "M6": mt5.TIMEFRAME_M6,
    "M10": mt5.TIMEFRAME_M10,
    "M12": mt5.TIMEFRAME_M12,
    "M15": mt5.TIMEFRAME_M15,
    "M20": mt5.TIMEFRAME_M20,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H3": mt5.TIMEFRAME_H3,
    "H4": mt5.TIMEFRAME_H4,
    "H6": mt5.TIMEFRAME_H6,
    "H8": mt5.TIMEFRAME_H8,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def convert_timeframe(timeframe_str: str) -> int:
    """Convert timeframe string to MT5 constant."""
    tf = timeframe_str.upper()
    if tf not in TIMEFRAME_MAP:
        raise ValueError(
            f"Invalid timeframe: '{timeframe_str}'. "
            f"Valid: {', '.join(TIMEFRAME_MAP.keys())}"
        )
    return TIMEFRAME_MAP[tf]


# ============================================================================
# ORDER TYPE CONVERSION
# ============================================================================

ORDER_TYPE_MAP = {
    "buy": mt5.ORDER_TYPE_BUY,
    "sell": mt5.ORDER_TYPE_SELL,
}


def convert_order_type(order_type_str: str) -> int:
    """Convert order type string to MT5 constant."""
    ot = order_type_str.lower()
    if ot not in ORDER_TYPE_MAP:
        raise ValueError(f"Invalid order_type: '{order_type_str}'. Valid: buy, sell")
    return ORDER_TYPE_MAP[ot]


# ============================================================================
# VOLUME VALIDATION
# ============================================================================


def validate_and_adjust_volume(
    symbol: str, volume: float
) -> Tuple[float, Optional[str]]:
    """
    Validate and adjust volume to symbol constraints.

    Returns:
        (adjusted_volume, warning_message)
    """
    symbol_info = get_symbol_info_cached(symbol)
    if symbol_info is None:
        return volume, None

    vol_min = symbol_info.volume_min
    vol_max = symbol_info.volume_max
    vol_step = symbol_info.volume_step

    original = volume

    # Clamp to min/max
    volume = max(vol_min, min(vol_max, volume))

    # Round to nearest step
    steps = round(volume / vol_step)
    volume = steps * vol_step
    volume = max(vol_min, min(vol_max, volume))

    warning = None
    if abs(volume - original) > 1e-9:
        warning = (
            "Volume adjusted from "
            f"{original} to {volume} (min={vol_min}, max={vol_max}, step={vol_step})"
        )

    return volume, warning


# ============================================================================
# INDICATOR VALIDATION
# ============================================================================


def validate_indicator_data_requirements(
    indicator_function: str, period: int, bar_count: int
) -> Tuple[bool, Optional[str]]:
    """
    Validate sufficient data for indicator calculation.

    Returns:
        (is_valid, error_message_with_suggestion)
    """
    # Extract indicator type from function path
    if "rsi" in indicator_function.lower():
        required = period + 10
    elif "macd" in indicator_function.lower():
        required = 35  # MACD typically needs 26 + buffer
    elif "bollinger" in indicator_function.lower():
        required = period + 10
    elif "sma" in indicator_function.lower() or "ema" in indicator_function.lower():
        required = period + 5
    elif "atr" in indicator_function.lower():
        required = period + 5
    else:
        required = max(50, period + 10)  # Conservative default

    if bar_count < required:
        message = (
            f"Need at least {required} bars for {indicator_function}, got {bar_count}. "
            f"Try: count={required}"
        )
        return (False, message)

    return True, None


# ============================================================================
# TA FUNCTION VALIDATION
# ============================================================================


def validate_ta_function(function_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate TA-Lib function path.

    Returns:
        (is_valid, error_message)
    """
    if not function_path.startswith("ta."):
        return False, f"Function path must start with 'ta.', got: '{function_path}'"

    parts = function_path.split(".")
    if len(parts) != 3:
        return False, (
            "Function path must be 'ta.<module>.<function>', got: " f"'{function_path}'"
        )

    try:
        import ta

        module_name = parts[1]
        func_name = parts[2]

        # Check if module exists
        if not hasattr(ta, module_name):
            available = "momentum, trend, volatility, volume, others"
            return (
                False,
                f"TA-Lib module '{module_name}' not found. Available: {available}",
            )

        module = getattr(ta, module_name)

        # Check if function exists
        if not hasattr(module, func_name):
            return False, f"Function '{func_name}' not found in ta.{module_name}"

        return True, None

    except Exception as e:
        return False, f"Error validating TA function: {str(e)}"
