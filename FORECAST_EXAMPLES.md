# MT5-MCP v0.4.0 - Prophet Forecasting Examples

## Overview
Version 0.4.0 adds **Prophet time series forecasting** to the `mt5_analyze` tool. You can now predict future price movements based on historical data.

## Quick Start

### Basic Forecast Request
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {
      "timeframe": "D1",
      "start_pos": 0,
      "count": 90
    }
  },
  "forecast": {
    "periods": 30,
    "plot": true
  }
}
```

This will:
- Fetch 90 days of BTCUSD daily data
- Train Prophet model on the data
- Forecast 30 days into the future
- Generate a forecast visualization chart

## Forecast Parameters

### Required
- `periods` (int): Number of periods to forecast ahead (1-365)

### Optional
- `plot` (bool): Generate forecast chart (default: true)
- `plot_components` (bool): Generate components chart showing trend/seasonality (default: false)
- `freq` (string): Forecast frequency - "D" (daily), "H" (hourly), "T" (minutely). Auto-detected if not specified.
- `seasonality_mode` (string): "additive" or "multiplicative" (default: "additive")
- `growth` (string): "linear" or "logistic" (default: "linear")
- `uncertainty_samples` (int): Samples for confidence intervals (default: 1000)
- `include_history` (bool): Include historical fitted values in output (default: false)

## Examples

### Example 1: Daily Forecast with Trend Analysis
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "D1", "start_pos": 0, "count": 90}
  },
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 20}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}}
  ],
  "forecast": {
    "periods": 30,
    "seasonality_mode": "additive",
    "growth": "linear",
    "plot": true
  },
  "chart": {
    "type": "multi",
    "panels": [
      {"columns": ["close", "sma_indicator_20"]},
      {"columns": ["rsi_14"], "reference_lines": [30, 70]}
    ]
  },
  "output_format": "chart_only"
}
```

**Result**: Analysis chart + Forecast chart + Summary with predicted change

### Example 2: Hourly Forecast for Short-term Trading
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "ETHUSD",
    "parameters": {"timeframe": "H1", "start_pos": 0, "count": 168}
  },
  "forecast": {
    "periods": 24,
    "freq": "H",
    "seasonality_mode": "multiplicative",
    "plot": true,
    "plot_components": true
  }
}
```

**Result**: 24-hour ahead forecast with components breakdown

### Example 3: Multi-week Forecast with Confidence Intervals
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "XAUUSD",
    "parameters": {"timeframe": "D1", "start_pos": 0, "count": 180}
  },
  "forecast": {
    "periods": 60,
    "growth": "linear",
    "uncertainty_samples": 2000,
    "plot": true
  }
}
```

**Result**: 60-day forecast with wider confidence intervals (more samples)

## Response Format

The forecast is included in `metadata.forecast_summary`:

```json
{
  "success": true,
  "chart_path": "C:\\path\\to\\chart.png",
  "forecast_chart_path": "C:\\path\\to\\forecast_BTCUSD_D1.png",
  "metadata": {
    "forecast_summary": {
      "periods_forecasted": 30,
      "frequency": "D",
      "model": {
        "growth": "linear",
        "seasonality_mode": "additive",
        "uncertainty_samples": 1000
      },
      "predictions": {
        "last_actual_price": 91286.50,
        "final_forecast_price": 60623.37,
        "predicted_change_pct": -33.59,
        "mean_forecast": 75820.45,
        "trend_direction": "bearish"
      },
      "uncertainty": {
        "avg_confidence_range": 9104.50,
        "final_lower_bound": 56070.12,
        "final_upper_bound": 65176.62
      },
      "insights": [
        "Significant bearish movement expected: -33.59%",
        "Moderate confidence in predictions"
      ],
      "forecast_data": [
        {"ds": "2024-12-01T00:00:00", "yhat": 88432.12, "yhat_lower": 79233.45, "yhat_upper": 97630.78},
        ...
      ]
    }
  }
}
```

## Key Features

### Automatic Frequency Detection
If `freq` is not specified, the tool auto-detects based on data:
- <= 1 hour between bars → Hourly ("H")
- <= 1 day between bars → Daily ("D")
- > 1 day → Weekly ("W")

### Dynamic Insights
The forecast generates contextual insights:
- "Significant bullish/bearish movement expected" (>5% change)
- "Price expected to remain relatively stable" (<1% change)
- "High uncertainty in predictions" (wide confidence intervals)
- "Moderate confidence in predictions"

### Visualization
Two types of charts:
1. **Forecast Chart** (`plot=true`): Shows historical data + predictions with confidence intervals
2. **Components Chart** (`plot_components=true`): Breaks down trend, weekly/yearly seasonality

## Best Practices

### Data Requirements
- Minimum 10 data points required
- Recommended: 60+ points for daily forecasts, 100+ for hourly
- More data = better model training

### Choosing Seasonality Mode
- **Additive**: Use when seasonal variations are constant (most cases)
- **Multiplicative**: Use when seasonal variations grow with trend (percentage-based)

### Timeframe Selection
| Goal | Recommended Timeframe | Forecast Periods |
|------|----------------------|------------------|
| Intraday trading | H1 (hourly) | 24-168 hours |
| Swing trading | D1 (daily) | 7-30 days |
| Long-term investing | D1 or W1 | 30-180 days |

### Performance Tips
- Use `uncertainty_samples=500` for faster forecasts
- Use `uncertainty_samples=2000+` for more accurate confidence intervals
- Set `include_history=false` to reduce response size

## Integration with Claude Desktop

After running `pip install -e .`, restart Claude Desktop. The forecast parameter is now available in `mt5_analyze`:

**User**: "Can you forecast BTCUSD for the next 30 days?"

**Claude** will call:
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "D1", "count": 90}},
  "forecast": {"periods": 30, "plot": true}
}
```

## Technical Details

- **Library**: Facebook Prophet (v1.2.1)
- **Model**: Additive/multiplicative decomposition with trend + seasonality
- **Uncertainty**: Monte Carlo simulation for confidence intervals
- **Performance**: ~1-3 seconds for typical forecasts

## Changelog v0.4.0

### Added
- `ForecastConfig` model for forecast configuration
- `_generate_forecast()` function with Prophet integration
- `forecast` parameter in `mt5_analyze` tool
- `forecast_chart_path` in response
- `forecast_summary` in metadata with predictions and insights
- Auto-detection of time series frequency
- Dynamic insight generation

### Dependencies
- Added `prophet>=1.0.0` to requirements

## Troubleshooting

### "Insufficient data for forecasting"
- Increase `count` in query parameters (minimum 10 rows)

### "High uncertainty in predictions"
- Add more historical data
- Increase `uncertainty_samples`
- Check if data has unusual volatility

### Forecast seems unrealistic
- Try different `seasonality_mode` (additive vs multiplicative)
- Adjust `growth` model (linear vs logistic)
- Ensure sufficient training data

## Support

For issues or questions:
- GitHub: https://github.com/yourusername/mt5-mcp
- Open an issue with forecast request and error message
