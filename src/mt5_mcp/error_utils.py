"""Error handling utilities for MT5 MCP Server.

Provides standardized error responses and validation helpers to prevent
server crashes from malformed client input.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Standardized error type categories."""

    JSON_PARSE_ERROR = "JSONParseError"
    VALIDATION_ERROR = "ValidationError"
    TYPE_ERROR = "TypeError"
    VALUE_ERROR = "ValueError"
    ENUM_ERROR = "EnumError"
    MISSING_FIELD = "MissingFieldError"
    MT5_CONNECTION = "MT5ConnectionError"
    MT5_OPERATION = "MT5OperationError"
    CALCULATION_ERROR = "CalculationError"
    TIMEOUT_ERROR = "TimeoutError"
    RUNTIME_ERROR = "RuntimeError"
    UNKNOWN_ERROR = "UnknownError"


def create_error_response(
    error_type: ErrorType,
    error_message: str,
    operation: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized error response dictionary.

    Args:
        error_type: ErrorType enum value
        error_message: Human-readable error description
        operation: Operation that failed (optional)
        details: Additional context about the error (optional)

    Returns:
        Dictionary with standardized error structure
    """
    response = {
        "success": False,
        "error": error_message,
        "error_type": error_type.value,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if operation:
        response["operation"] = operation

    if details:
        response["error_details"] = details

    return response


def create_success_response(
    data: Any,
    operation: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized success response dictionary.

    Args:
        data: Response data
        operation: Operation that succeeded (optional)
        metadata: Additional response metadata (optional)

    Returns:
        Dictionary with standardized success structure
    """
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if operation:
        response["operation"] = operation

    if metadata:
        response["metadata"] = metadata

    return response


def safe_json_parse(
    json_string: str,
    field_name: str = "input",
    default: Any = None,
) -> tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """
    Safely parse JSON string with error handling.

    Args:
        json_string: JSON string to parse
        field_name: Name of the field being parsed (for error messages)
        default: Default value to return on error

    Returns:
        Tuple of (parsed_value, error_dict). If successful, error_dict is None.
        If failed, parsed_value is default and error_dict contains error info.
    """
    if not json_string or not json_string.strip():
        return default, None

    try:
        parsed = json.loads(json_string)
        return parsed, None
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in {field_name}: {str(e)}"
        logger.warning(error_msg)
        error_dict = create_error_response(
            ErrorType.JSON_PARSE_ERROR,
            error_msg,
            details={
                "field": field_name,
                "input": json_string[:100] + "..." if len(json_string) > 100 else json_string,
                "position": getattr(e, "pos", None),
            },
        )
        return default, error_dict
    except Exception as e:
        error_msg = f"Unexpected error parsing {field_name}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        error_dict = create_error_response(
            ErrorType.UNKNOWN_ERROR, error_msg, details={"field": field_name}
        )
        return default, error_dict


def safe_enum_conversion(
    value: str,
    enum_class: type[Enum],
    field_name: str = "field",
) -> tuple[Optional[Enum], Optional[Dict[str, Any]]]:
    """
    Safely convert string to enum with error handling.

    Args:
        value: String value to convert
        enum_class: Enum class to convert to
        field_name: Name of the field being converted (for error messages)

    Returns:
        Tuple of (enum_value, error_dict). If successful, error_dict is None.
        If failed, enum_value is None and error_dict contains error info.
    """
    try:
        enum_value = enum_class(value)
        return enum_value, None
    except ValueError:
        valid_values = [e.value for e in enum_class]
        error_msg = f"Invalid {field_name} '{value}'. Valid values: {', '.join(valid_values)}"
        logger.warning(error_msg)
        error_dict = create_error_response(
            ErrorType.ENUM_ERROR,
            error_msg,
            details={
                "field": field_name,
                "invalid_value": value,
                "valid_values": valid_values,
            },
        )
        return None, error_dict
    except Exception as e:
        error_msg = f"Unexpected error converting {field_name}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        error_dict = create_error_response(
            ErrorType.UNKNOWN_ERROR, error_msg, details={"field": field_name}
        )
        return None, error_dict


def validate_required_field(
    value: Any,
    field_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Validate that a required field has a value.

    Args:
        value: Field value to check
        field_name: Name of the field

    Returns:
        Error dict if validation fails, None if successful
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        error_msg = f"Missing required field: {field_name}"
        logger.warning(error_msg)
        return create_error_response(
            ErrorType.MISSING_FIELD, error_msg, details={"field": field_name}
        )
    return None


def validate_type(
    value: Any,
    expected_type: type,
    field_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Validate that a value has the expected type.

    Args:
        value: Value to check
        expected_type: Expected type
        field_name: Name of the field

    Returns:
        Error dict if validation fails, None if successful
    """
    if not isinstance(value, expected_type):
        error_msg = (
            f"Invalid type for {field_name}: expected {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
        logger.warning(error_msg)
        return create_error_response(
            ErrorType.TYPE_ERROR,
            error_msg,
            details={
                "field": field_name,
                "expected_type": expected_type.__name__,
                "actual_type": type(value).__name__,
            },
        )
    return None


def safe_dict_get(
    dictionary: Dict[str, Any],
    key: str,
    default: Any = None,
    expected_type: Optional[type] = None,
) -> tuple[Any, Optional[Dict[str, Any]]]:
    """
    Safely get value from dictionary with type validation.

    Args:
        dictionary: Dictionary to get value from
        key: Key to retrieve
        default: Default value if key not found
        expected_type: Expected type for validation (optional)

    Returns:
        Tuple of (value, error_dict). If successful, error_dict is None.
    """
    value = dictionary.get(key, default)

    if expected_type and value is not None:
        error_dict = validate_type(value, expected_type, key)
        if error_dict:
            return default, error_dict

    return value, None


def wrap_with_error_handling(func):
    """
    Decorator to wrap functions with standardized error handling.

    Catches all exceptions and returns standardized error responses.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = func.__name__
            error_msg = f"Error in {func_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Determine error type
            if "json" in str(e).lower():
                error_type = ErrorType.JSON_PARSE_ERROR
            elif isinstance(e, ValueError):
                error_type = ErrorType.VALUE_ERROR
            elif isinstance(e, TypeError):
                error_type = ErrorType.TYPE_ERROR
            elif isinstance(e, TimeoutError):
                error_type = ErrorType.TIMEOUT_ERROR
            else:
                error_type = ErrorType.RUNTIME_ERROR

            return json.dumps(
                create_error_response(
                    error_type,
                    error_msg,
                    operation=func_name,
                    details={"exception": type(e).__name__},
                ),
                default=str,
            )

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def safe_operation_execution(
    operation_func,
    operation_name: str,
    error_type_map: Optional[Dict[type, ErrorType]] = None,
    **kwargs,
) -> tuple[Any, Optional[Dict[str, Any]]]:
    """
    Execute an operation with comprehensive error handling.

    Args:
        operation_func: Function to execute
        operation_name: Name of the operation (for error messages)
        error_type_map: Mapping of exception types to ErrorType enums
        **kwargs: Arguments to pass to operation_func

    Returns:
        Tuple of (result, error_dict). If successful, error_dict is None.
    """
    if error_type_map is None:
        error_type_map = {}

    try:
        result = operation_func(**kwargs)
        return result, None
    except Exception as e:
        # Map exception to error type
        error_type = error_type_map.get(type(e), ErrorType.RUNTIME_ERROR)

        error_msg = f"Operation '{operation_name}' failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        error_dict = create_error_response(
            error_type,
            error_msg,
            operation=operation_name,
            details={
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            },
        )
        return None, error_dict


def format_json_response(response_dict: Dict[str, Any]) -> str:
    """
    Format response dictionary as JSON string with safe serialization.

    Args:
        response_dict: Dictionary to serialize

    Returns:
        JSON string
    """
    try:
        return json.dumps(response_dict, default=str, indent=2)
    except Exception as e:
        logger.error(f"Failed to serialize response: {e}", exc_info=True)
        # Return basic error response
        fallback = create_error_response(
            ErrorType.RUNTIME_ERROR,
            "Failed to serialize response",
            details={"original_error": str(e)},
        )
        return json.dumps(fallback, default=str)
