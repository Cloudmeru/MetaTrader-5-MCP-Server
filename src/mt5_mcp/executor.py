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


def execute_command(
    command: str, namespace: Dict[str, Any], show_traceback: bool = True
) -> str:
    """
    Execute Python command in restricted namespace and return formatted result.

    Args:
        command: Python code to execute (single or multi-line)
        namespace: Restricted namespace containing available functions/modules
        show_traceback: Whether to include full traceback on errors

    Returns:
        Formatted result string or error message
    """
    logger.info(f"Executing command: {command[:100]}...")

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    result = None
    error = None

    try:
        code_obj, capture_expression = _prepare_code(command)
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
        formatted_result = format_result(result)
        if formatted_result:
            response_parts.append(formatted_result)

    if not response_parts:
        return "Command executed successfully (no output)"

    return "\n\n".join(response_parts)
