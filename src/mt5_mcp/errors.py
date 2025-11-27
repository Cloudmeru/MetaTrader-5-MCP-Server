"""Custom error classes with LLM-friendly messages."""

from typing import Optional, Dict, Any


class MT5Error(Exception):
    """Base error class for MT5 operations."""

    def __init__(
        self,
        message: str,
        error_type: str,
        suggestion: Optional[str] = None,
        corrected_params: Optional[Dict[str, Any]] = None,
        example: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_type = error_type
        self.suggestion = suggestion
        self.corrected_params = corrected_params
        self.example = example
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {"error": self.message, "error_type": self.error_type}
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.corrected_params:
            result["corrected_params"] = self.corrected_params
        if self.example:
            result["example"] = self.example
        return result


class MT5ValidationError(MT5Error):
    """Input validation error."""

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        corrected_params: Optional[Dict[str, Any]] = None,
        example: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message, "VALIDATION_ERROR", suggestion, corrected_params, example
        )


class MT5SymbolNotFoundError(MT5Error):
    """Symbol not found error."""

    def __init__(self, symbol: str, similar_symbols: Optional[list] = None):
        message = f"Symbol '{symbol}' not found in MT5."
        suggestion = None
        corrected = None

        if similar_symbols:
            suggestion = f"Did you mean: {', '.join(similar_symbols[:3])}?"
            corrected = {"symbol": similar_symbols[0]}
        else:
            suggestion = "Use 'symbols_get' operation to list available symbols."

        super().__init__(message, "SYMBOL_NOT_FOUND", suggestion, corrected)


class MT5DataError(MT5Error):
    """Data retrieval/quality error."""

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        corrected_params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "DATA_ERROR", suggestion, corrected_params)


class MT5CalculationError(MT5Error):
    """Calculation error."""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(message, "CALCULATION_ERROR", suggestion)


class MT5OperationError(MT5Error):
    """Operation execution error."""

    def __init__(self, operation: str, message: str, suggestion: Optional[str] = None):
        full_message = f"Operation '{operation}' failed: {message}"
        super().__init__(full_message, "OPERATION_ERROR", suggestion)
