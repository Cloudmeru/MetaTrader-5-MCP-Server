"""Pydantic models for universal MT5 operations."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class MT5Operation(str, Enum):
    """Available MT5 read-only operations."""

    # Market data operations
    COPY_RATES_FROM = "copy_rates_from"
    COPY_RATES_FROM_POS = "copy_rates_from_pos"
    COPY_RATES_RANGE = "copy_rates_range"
    COPY_TICKS_FROM = "copy_ticks_from"
    COPY_TICKS_RANGE = "copy_ticks_range"

    # Symbol operations
    SYMBOL_INFO = "symbol_info"
    SYMBOL_INFO_TICK = "symbol_info_tick"
    SYMBOL_SELECT = "symbol_select"
    SYMBOLS_TOTAL = "symbols_total"
    SYMBOLS_GET = "symbols_get"

    # Account/Terminal info
    ACCOUNT_INFO = "account_info"
    TERMINAL_INFO = "terminal_info"
    VERSION = "version"

    # Calculation operations
    ORDER_CALC_MARGIN = "order_calc_margin"
    ORDER_CALC_PROFIT = "order_calc_profit"


class TimeFrame(str, Enum):
    """MT5 timeframe constants."""

    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"
    M6 = "M6"
    M10 = "M10"
    M12 = "M12"
    M15 = "M15"
    M20 = "M20"
    M30 = "M30"
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    H4 = "H4"
    H6 = "H6"
    H8 = "H8"
    H12 = "H12"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


# ============================================================================
# REQUEST MODELS
# ============================================================================


class MT5QueryRequest(BaseModel):
    """Universal MT5 query request supporting all read-only operations."""

    operation: MT5Operation = Field(..., description="MT5 operation to execute")

    symbol: Optional[str] = Field(
        None,
        description="Trading symbol (required for symbol-specific operations)",
        min_length=3,
        max_length=20,
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters (e.g., timeframe, count, start_pos, dates)",
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize symbol."""
        if v:
            return v.strip().upper()
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "operation": "copy_rates_from_pos",
                    "symbol": "BTCUSD",
                    "parameters": {"timeframe": "H1", "start_pos": 0, "count": 100},
                },
                {"operation": "symbol_info", "symbol": "EURUSD", "parameters": {}},
                {"operation": "symbols_get", "parameters": {"group": "*USD*"}},
            ]
        }


class IndicatorSpec(BaseModel):
    """Specification for a technical indicator."""

    function: str = Field(
        ...,
        description="TA-Lib function path (e.g., 'ta.momentum.rsi', 'ta.trend.sma_indicator')",
        pattern=r"^ta\.\w+\.\w+$",
    )

    column_name: Optional[str] = Field(
        None, description="Output column name (auto-generated if not provided)"
    )

    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Indicator parameters (e.g., {'window': 14} for RSI)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"function": "ta.momentum.rsi", "params": {"window": 14}},
                {"function": "ta.trend.sma_indicator", "params": {"window": 20}},
                {"function": "ta.trend.ema_indicator", "params": {"window": 50}},
                {"function": "ta.volatility.bollinger_hband", "params": {"window": 20}},
                {"function": "ta.trend.macd", "params": {}},
            ]
        }


class ChartPanel(BaseModel):
    """Configuration for a chart panel."""

    columns: List[str] = Field(
        ..., description="Column names to plot in this panel", min_length=1
    )

    style: str = Field(
        default="line", description="Plot style: 'line', 'scatter', 'bar'"
    )

    y_label: Optional[str] = Field(None, description="Y-axis label")

    y_limits: Optional[List[float]] = Field(
        None, description="Y-axis limits [min, max]", min_length=2, max_length=2
    )

    reference_lines: Optional[List[float]] = Field(
        None, description="Horizontal reference lines (e.g., [30, 70] for RSI)"
    )


class ChartConfig(BaseModel):
    """Configuration for chart generation."""

    type: str = Field(
        default="single",
        description="Chart type: 'single' (one panel) or 'multi' (multiple panels)",
    )

    panels: List[ChartPanel] = Field(
        default_factory=lambda: [ChartPanel(columns=["close"])],
        description="Panel configurations (one for single, multiple for multi)",
        min_length=1,
        max_length=5,
    )

    title: Optional[str] = Field(
        None, description="Chart title (auto-generated if not provided)"
    )

    filename: str = Field(
        default="chart.png", description="Output filename", pattern=r"^[\w\-]+\.png$"
    )

    width: int = Field(default=14, ge=6, le=24, description="Width in inches")
    height: int = Field(default=8, ge=4, le=20, description="Height in inches")
    dpi: int = Field(default=120, ge=50, le=300, description="Resolution")


class ForecastConfig(BaseModel):
    """Configuration for Prophet time series forecasting."""

    periods: int = Field(
        default=30,
        description="Number of periods to forecast into the future",
        ge=1,
        le=365,
    )

    include_history: bool = Field(
        default=False, description="Include historical fitted values in forecast output"
    )

    freq: Optional[str] = Field(
        None,
        description=(
            "Forecast frequency (auto-detected from data if not specified): "
            "'D' (daily), 'h' (hourly), 'min' (minutely)"
        ),
    )

    uncertainty_samples: int = Field(
        default=1000,
        description="Number of samples for uncertainty intervals",
        ge=0,
        le=10000,
    )

    seasonality_mode: str = Field(
        default="additive",
        description="Seasonality mode: 'additive' or 'multiplicative'",
    )

    growth: str = Field(
        default="linear", description="Growth model: 'linear' or 'logistic'"
    )

    plot: bool = Field(
        default=True, description="Generate forecast visualization chart"
    )

    plot_components: bool = Field(
        default=False,
        description="Generate components plot (trend, seasonality, holidays)",
    )

    enable_ml_prediction: bool = Field(
        default=False,
        description="Enable XGBoost ML model for buy/sell signal prediction",
    )

    ml_lookback: int = Field(
        default=50,
        description="Number of bars to use for ML feature engineering",
        ge=20,
        le=200,
    )

    @field_validator("seasonality_mode")
    @classmethod
    def validate_seasonality_mode(cls, v: str) -> str:
        """Validate seasonality mode."""
        v = v.lower()
        if v not in ["additive", "multiplicative"]:
            raise ValueError("seasonality_mode must be 'additive' or 'multiplicative'")
        return v

    @field_validator("growth")
    @classmethod
    def validate_growth(cls, v: str) -> str:
        """Validate growth model."""
        v = v.lower()
        if v not in ["linear", "logistic"]:
            raise ValueError("growth must be 'linear' or 'logistic'")
        return v


class MT5AnalysisRequest(BaseModel):
    """Universal analysis request: query + analyze + visualize."""

    query: MT5QueryRequest = Field(..., description="MT5 data query configuration")

    indicators: Optional[List[IndicatorSpec]] = Field(
        None, description="Technical indicators to calculate", max_length=20
    )

    chart: Optional[ChartConfig] = Field(
        None, description="Chart generation configuration (omit for data-only response)"
    )

    forecast: Optional[ForecastConfig] = Field(
        None, description="Prophet forecast configuration (omit to skip forecasting)"
    )

    output_format: str = Field(
        default="markdown",
        description="Data output format: 'markdown', 'json', 'chart_only'",
    )

    tail: Optional[int] = Field(
        None,
        description="Return only last N rows of data (None = all rows)",
        ge=1,
        le=1000,
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format."""
        v = v.lower()
        if v not in ["markdown", "json", "chart_only"]:
            raise ValueError(
                "output_format must be 'markdown', 'json', or 'chart_only'"
            )
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "query": {
                        "operation": "copy_rates_from_pos",
                        "symbol": "BTCUSD",
                        "parameters": {"timeframe": "D1", "start_pos": 0, "count": 30},
                    },
                    "indicators": [
                        {"function": "ta.momentum.rsi", "params": {"window": 14}},
                        {
                            "function": "ta.trend.sma_indicator",
                            "params": {"window": 20},
                        },
                    ],
                    "chart": {
                        "type": "multi",
                        "panels": [
                            {"columns": ["close", "sma_indicator_20"], "style": "line"},
                            {
                                "columns": ["rsi"],
                                "style": "line",
                                "y_limits": [0, 100],
                                "reference_lines": [30, 70],
                            },
                        ],
                        "filename": "btcusd_trend.png",
                    },
                    "output_format": "chart_only",
                }
            ]
        }


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class MT5QueryResponse(BaseModel):
    """Universal query response."""

    operation: str
    success: bool
    data: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MT5AnalysisResponse(BaseModel):
    """Universal analysis response."""

    success: bool
    data: Optional[Any] = None
    chart_path: Optional[str] = None
    forecast_chart_path: Optional[str] = None
    indicators_calculated: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response with suggestions."""

    error: str
    error_type: str
    suggestion: Optional[str] = None
    corrected_params: Optional[Dict[str, Any]] = None
    example: Optional[Dict[str, Any]] = None
