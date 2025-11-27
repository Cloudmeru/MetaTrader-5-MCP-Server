"""MT5 connection management and safe namespace setup."""

import logging
from typing import Dict, Any, Optional
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class MT5Connection:
    """Manages MetaTrader 5 connection and provides safe execution namespace."""
    
    def __init__(self):
        """Initialize MT5 connection at startup."""
        self._initialized = False
        self._safe_namespace: Optional[Dict[str, Any]] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize connection to MT5 terminal."""
        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            raise RuntimeError(f"Failed to initialize MT5: {error}")
        
        self._initialized = True
        logger.info("MT5 connection initialized successfully")
        
        # Build safe namespace with read-only functions
        self._safe_namespace = self._build_safe_namespace()
    
    def _build_safe_namespace(self) -> Dict[str, Any]:
        """Build namespace with only read-only MT5 functions and helpers."""
        import datetime
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend for server use
        import matplotlib.pyplot as plt
        import ta
        
        # Whitelist read-only MT5 functions
        safe_mt5_funcs = {
            # Symbol information
            'symbol_info': mt5.symbol_info,
            'symbol_info_tick': mt5.symbol_info_tick,
            'symbol_select': mt5.symbol_select,
            'symbols_total': mt5.symbols_total,
            'symbols_get': mt5.symbols_get,
            
            # Market data
            'copy_rates_from': mt5.copy_rates_from,
            'copy_rates_from_pos': mt5.copy_rates_from_pos,
            'copy_rates_range': mt5.copy_rates_range,
            'copy_ticks_from': mt5.copy_ticks_from,
            'copy_ticks_range': mt5.copy_ticks_range,
            
            # Account information (read-only)
            'account_info': mt5.account_info,
            'terminal_info': mt5.terminal_info,
            'version': mt5.version,
            
            # Timeframe constants
            'TIMEFRAME_M1': mt5.TIMEFRAME_M1,
            'TIMEFRAME_M2': mt5.TIMEFRAME_M2,
            'TIMEFRAME_M3': mt5.TIMEFRAME_M3,
            'TIMEFRAME_M4': mt5.TIMEFRAME_M4,
            'TIMEFRAME_M5': mt5.TIMEFRAME_M5,
            'TIMEFRAME_M6': mt5.TIMEFRAME_M6,
            'TIMEFRAME_M10': mt5.TIMEFRAME_M10,
            'TIMEFRAME_M12': mt5.TIMEFRAME_M12,
            'TIMEFRAME_M15': mt5.TIMEFRAME_M15,
            'TIMEFRAME_M20': mt5.TIMEFRAME_M20,
            'TIMEFRAME_M30': mt5.TIMEFRAME_M30,
            'TIMEFRAME_H1': mt5.TIMEFRAME_H1,
            'TIMEFRAME_H2': mt5.TIMEFRAME_H2,
            'TIMEFRAME_H3': mt5.TIMEFRAME_H3,
            'TIMEFRAME_H4': mt5.TIMEFRAME_H4,
            'TIMEFRAME_H6': mt5.TIMEFRAME_H6,
            'TIMEFRAME_H8': mt5.TIMEFRAME_H8,
            'TIMEFRAME_H12': mt5.TIMEFRAME_H12,
            'TIMEFRAME_D1': mt5.TIMEFRAME_D1,
            'TIMEFRAME_W1': mt5.TIMEFRAME_W1,
            'TIMEFRAME_MN1': mt5.TIMEFRAME_MN1,
            
            # Tick flags
            'COPY_TICKS_ALL': mt5.COPY_TICKS_ALL,
            'COPY_TICKS_INFO': mt5.COPY_TICKS_INFO,
            'COPY_TICKS_TRADE': mt5.COPY_TICKS_TRADE,
            
            # Order calculation functions (read-only)
            'order_calc_margin': mt5.order_calc_margin,
            'order_calc_profit': mt5.order_calc_profit,
            'ORDER_TYPE_BUY': mt5.ORDER_TYPE_BUY,
            'ORDER_TYPE_SELL': mt5.ORDER_TYPE_SELL,
        }
        
        # Create mt5 module-like object with only safe functions
        class SafeMT5:
            """Safe MT5 module proxy with only read-only functions."""
            def __init__(self, funcs):
                for name, func in funcs.items():
                    setattr(self, name, func)
        
        safe_mt5 = SafeMT5(safe_mt5_funcs)
        
        # Build complete namespace
        namespace = {
            'mt5': safe_mt5,
            'datetime': datetime,
            'pd': pd,
            'pandas': pd,
            'np': np,
            'numpy': np,
            'plt': plt,
            'matplotlib': matplotlib,
            'ta': ta,
        }
        
        return namespace
    
    def validate_connection(self) -> bool:
        """Validate MT5 connection is still active."""
        if not self._initialized:
            return False
        
        # Check if terminal is still connected
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            logger.warning("MT5 terminal connection lost")
            return False
        
        return True
    
    def get_safe_namespace(self) -> Dict[str, Any]:
        """Get the safe execution namespace."""
        if not self.validate_connection():
            raise RuntimeError("MT5 connection is not active. Ensure MT5 terminal is running.")
        
        return self._safe_namespace.copy()
    
    def shutdown(self):
        """Shutdown MT5 connection."""
        if self._initialized:
            mt5.shutdown()
            self._initialized = False
            logger.info("MT5 connection closed")


# Global connection instance
_connection: Optional[MT5Connection] = None


def get_connection() -> MT5Connection:
    """Get or create the global MT5 connection instance."""
    global _connection
    if _connection is None:
        _connection = MT5Connection()
    return _connection


def shutdown_connection():
    """Shutdown the global MT5 connection."""
    global _connection
    if _connection is not None:
        _connection.shutdown()
        _connection = None


def get_safe_namespace() -> Dict[str, Any]:
    """Get the safe execution namespace (convenience function)."""
    return get_connection().get_safe_namespace()


def validate_connection() -> Dict[str, Any]:
    """
    Validate MT5 connection and return status.
    
    Returns:
        Dictionary with 'connected' (bool) and 'error' (str) keys
    """
    try:
        conn = get_connection()
        is_connected = conn.validate_connection()
        return {
            "connected": is_connected,
            "error": None if is_connected else "Connection validation failed"
        }
    except Exception as e:
        logger.error(f"Connection validation error: {str(e)}")
        return {
            "connected": False,
            "error": str(e)
        }
