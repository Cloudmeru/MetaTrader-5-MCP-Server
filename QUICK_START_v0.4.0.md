# MT5-MCP v0.4.0 - Quick Start Guide

## 🚀 What's New
- **Prophet Time Series Forecasting**: Integrated into `mt5_analyze` tool
- **XGBoost ML Trading Signals**: Buy/sell predictions with confidence scores (NEW!)

## ⚡ Quick Examples

### 1. Simple 30-Day Forecast
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "D1", "count": 90}
  },
  "forecast": {"periods": 30}
}
```

### 2. Hourly Forecast for Day Trading
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "ETHUSD",
    "parameters": {"timeframe": "H1", "count": 168}
  },
  "forecast": {"periods": 24, "freq": "H"}
}
```

### 3. Full Analysis + Forecast
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "XAUUSD",
    "parameters": {"timeframe": "D1", "count": 180}
  },
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 50}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}}
  ],
  "forecast": {
    "periods": 60,
    "plot": true,
    "plot_components": true
  },
  "chart": {
    "type": "multi",
    "panels": [
      {"columns": ["close", "sma_indicator_50"]},
      {"columns": ["rsi_14"], "reference_lines": [30, 70]}
    ]
  }
}
```

### 4. ML Trading Signal + Forecast (NEW!)
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "H1", "count": 168}
  },
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 24}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.macd", "params": {}}
  ],
  "forecast": {
    "periods": 24,
    "freq": "h",
    "enable_ml_prediction": true,
    "ml_lookback": 100,
    "plot": true
  }
}
```

## 📊 What You Get

### Response Structure (with ML Signal)
```json
{
  "forecast_chart_path": "C:\\path\\to\\forecast_BTCUSD_D1.png",
  "metadata": {
    "forecast_summary": {
      "predictions": {
        "last_actual_price": 91286.50,
        "final_forecast_price": 60623.37,
        "predicted_change_pct": -33.59,
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
      "ml_trading_signal": {
        "signal": "BUY",
        "confidence": 0.73,
        "buy_probability": 0.73,
        "sell_probability": 0.27,
        "reasoning": "ML model predicts upward price movement with 73.0% confidence. Key factors: rsi_14, return_mean_10, sma_indicator_24",
        "features_used": 15,
        "training_samples": 145
      }
    }
  }
}
```

## ⚙️ Key Parameters

### Forecast Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `periods` | int | 30 | How many periods to forecast (1-365) |
| `plot` | bool | true | Generate forecast chart |
| `freq` | string | auto | "D" (daily), "h" (hourly), "min" (minutely) |
| `seasonality_mode` | string | additive | "additive" or "multiplicative" |
| `growth` | string | linear | "linear" or "logistic" |

### ML Signal Parameters (NEW!)
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_ml_prediction` | bool | false | Enable XGBoost ML trading signal |
| `ml_lookback` | int | 50 | Bars for feature engineering (20-200) |

## 🎯 Best Practices

### Data Requirements
- **Minimum**: 10 data points
- **Recommended**: 60+ for daily, 100+ for hourly

### Timeframe Selection
| Trading Style | Timeframe | Forecast Periods |
|--------------|-----------|------------------|
| Scalping/Intraday | H1 | 24-48 hours |
| Swing Trading | D1 | 7-30 days |
| Position Trading | D1/W1 | 30-180 days |

### Performance Tips
- Use `uncertainty_samples=500` for faster forecasts
- Set `include_history=false` to reduce response size
- Enable `plot_components=true` only when needed

## 🔧 Installation

```powershell
cd C:\Git\MT5-MCP
pip install -e .
```

Then restart Claude Desktop.

## 📖 Documentation

- **Full Examples**: `FORECAST_EXAMPLES.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY_v0.4.0.md`
- **Test Script**: `test_forecast.py`

## ✅ Verification

Test the installation:
```powershell
python test_forecast.py
```

Expected output:
```
✓ Analysis completed successfully
✓ Forecast chart saved
📊 FORECAST SUMMARY:
   • Predicted change: X.XX%
   • Trend direction: BULLISH/BEARISH
💡 INSIGHTS:
   • Significant movement expected...
```

## 🎉 That's It!

You now have Prophet forecasting integrated into your MT5-MCP server. Start predicting market movements! 🚀
