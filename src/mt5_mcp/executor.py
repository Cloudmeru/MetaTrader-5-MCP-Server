"""
Command executor for MT5 MCP server.
Executes Python commands in a restricted namespace and formats results.
"""

import ast
import io
import sys
import traceback
import logging
import runpy
from typing import Any, Dict, Tuple
import pandas as pd
import json

from .errors import MT5ValidationError

logger = logging.getLogger(__name__)


def format_result(result: Any) -> str:
    """
    Format execution result for nice display.

    Args:
        result: The result to format

    Returns:
        Formatted string representation
    """
    if result is None:
        return ""

    # Handle pandas DataFrames
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return "Empty DataFrame"
        return result.to_markdown(index=True)

    # Handle pandas Series
    if isinstance(result, pd.Series):
        if result.empty:
            return "Empty Series"
        return result.to_markdown()

    # Handle dictionaries
    if isinstance(result, dict):
        return json.dumps(result, indent=2, default=str)

    # Handle lists and tuples
    if isinstance(result, (list, tuple)):
        if len(result) == 0:
            return "[]" if isinstance(result, list) else "()"
        # If list of dicts, try to format as table
        if all(isinstance(item, dict) for item in result):
            try:
                df = pd.DataFrame(result)
                return df.to_markdown(index=False)
            except (ValueError, TypeError):
                pass
        return json.dumps(result, indent=2, default=str)

    # Handle MT5 NamedTuples and similar objects
    if hasattr(result, "_asdict"):
        return json.dumps(result._asdict(), indent=2, default=str)

    # Default: convert to string
    return str(result)


def _prepare_code(command: str) -> Tuple[object, bool]:
    """Compile command and capture final expression if present."""

    try:
        tree = ast.parse(command, mode="exec")
    except SyntaxError as exc:
        raise MT5ValidationError(f"Syntax error: {exc}") from exc

    capture_expression = bool(tree.body and isinstance(tree.body[-1], ast.Expr))

    if capture_expression:
        last_expr = tree.body[-1].value
        assignment = ast.Assign(
            targets=[ast.Name(id="__mt5_exec_result", ctx=ast.Store())],
            value=last_expr,
        )
        tree.body[-1] = assignment
        ast.fix_missing_locations(tree)

    code_obj = compile(tree, "<mt5_command>", "exec")
    return code_obj, capture_expression


def execute_command(command: str, namespace: Dict[str, Any], show_traceback: bool = True) -> str:
    """
    Execute Python command in restricted namespace and return formatted result.

    This is a fallback tool for advanced users who need custom MT5 operations
    not covered by mt5_query or mt5_analyze. Use with caution as incorrect
    code can cause errors or unexpected behavior.

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
            libraries pre-imported. Assign final output to 'result' variable
            or use it as the last expression.
        namespace (Dict[str, Any]): Restricted namespace containing available
            functions and modules (mt5, pandas, numpy, etc.). Connection to
            MT5 is already initialized.
        show_traceback (bool): Show full Python traceback on errors (default: True).
            Set to False for cleaner error messages in production.

    Returns:
        str: Formatted execution result. DataFrames are rendered as markdown tables,
            dicts/lists as JSON, and other types as strings. Returns error message
            if execution fails.

    Raises:
        MT5ValidationError: Command has syntax errors
        Exception: Runtime errors during command execution (captured and formatted)

    Examples:
        Get symbol information:
        >>> execute_command(
        ...     "result = mt5.symbol_info('BTCUSD')._asdict()",
        ...     namespace
        ... )

        Calculate custom indicator:
        >>> command = '''
        ... rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
        ... df = pd.DataFrame(rates)
        ... df['custom_ma'] = df['close'].rolling(20).mean()
        ... df['volatility'] = (df['high'] - df['low']) / df['close']
        ... result = df[['close', 'custom_ma', 'volatility']].tail(10)
        ... '''
        >>> execute_command(command, namespace)

        Multi-step analysis:
        >>> command = '''
        ... # Get data
        ... rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H4, 0, 100)
        ... df = pd.DataFrame(rates)
        ...
        ... # Calculate RSI
        ... df['RSI'] = ta.momentum.rsi(df['close'], window=14)
        ...
        ... # Find overbought conditions
        ... overbought = df[df['RSI'] > 70]
        ... result = {
        ...     'current_rsi': df['RSI'].iloc[-1],
        ...     'overbought_count': len(overbought),
        ...     'last_overbought': (
        ...         overbought.tail(1)['time'].values[0]
        ...         if len(overbought) > 0
        ...         else None
        ...     )
        ... }
        ... '''
        >>> execute_command(command, namespace)
    """
    # Validate inputs
    if not command or not isinstance(command, str):
        raise MT5ValidationError(
            f"Command must be a non-empty string, got {type(command).__name__}"
        )

    if not namespace or not isinstance(namespace, dict):
        raise MT5ValidationError(f"Namespace must be a dictionary, got {type(namespace).__name__}")

    logger.info(f"Executing command: {command[:100]}...")

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    result = None
    error = None

    try:
        # Prepare and compile code with error handling
        try:
            code_obj, capture_expression = _prepare_code(command)
        except MT5ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to prepare code: {e}", exc_info=True)
            raise MT5ValidationError(f"Failed to compile command: {str(e)}") from e
        namespace.setdefault("__name__", "__main__")
        namespace.pop("__mt5_exec_result", None)
        runpy._run_code(
            code_obj,
            namespace,
            None,
            "mt5_exec",
            None,
            None,
            None,
        )
        if capture_expression:
            result = namespace.get("__mt5_exec_result")
        if result is None:
            for var_name in ["result", "data", "output", "res"]:
                value = namespace.get(var_name)
                if value is not None and not var_name.startswith("_"):
                    result = value
                    break
    except Exception as e:
        error = e
        logger.error(f"Command execution failed: {str(e)}", exc_info=True)
    finally:
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

    # Build response
    if error:
        if show_traceback:
            tb = traceback.format_exc()
            return f"Error executing command:\n\n{tb}"
        return f"Error: {type(error).__name__}: {str(error)}"

    # Combine output and result
    response_parts = []

    if output.strip():
        response_parts.append(output.strip())

    if result is not None:
        try:
            formatted_result = format_result(result)
            if formatted_result:
                response_parts.append(formatted_result)
        except Exception as e:
            logger.error(f"Failed to format result: {e}", exc_info=True)
            response_parts.append(f"Warning: Could not format result: {str(e)}")
            response_parts.append(f"Raw result type: {type(result).__name__}")

    if not response_parts:
        return "Command executed successfully (no output)"

    return "\n\n".join(response_parts)
