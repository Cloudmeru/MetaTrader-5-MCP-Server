# mt5_analyze Tool - Quick Reference

## Overview
The `mt5_analyze` tool is a **universal analysis tool** that combines MT5 data queries, technical indicators, chart generation, Prophet forecasting, and XGBoost ML trading signals in a single request.

---

## 🔮 Prophet Time Series Forecasting

### What it does
- Predicts future prices using Facebook's Prophet time series model
- Provides confidence intervals and trend analysis
- Generates forecast charts with historical data + predictions

### Basic Forecast (30 days)
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "D1", "count": 168}
  },
  "forecast": {
    "periods": 30,
    "plot": true
  }
}
```

### Returns
- `forecast_summary`: predicted prices, % change, confidence intervals
- `forecast_chart_path`: saved chart file with clickable link
- `forecast_data`: array of predicted values with dates

---

## 🤖 XGBoost ML Trading Signals

### What it does
- Trains XGBoost classifier on technical indicators
- Predicts BUY/SELL/HOLD signal with confidence score
- Provides reasoning and feature importance

### Enable ML Prediction
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "H1", "count": 168}
  },
  "forecast": {
    "periods": 24,
    "enable_ml_prediction": true,
    "ml_lookback": 50,
    "plot": true
  }
}
```

### ML Signal Output
```json
{
  "ml_trading_signal": {
    "signal": "BUY",
    "confidence": 87.3,
    "buy_probability": 0.873,
    "sell_probability": 0.127,
    "reasoning": "Strong upward momentum with RSI(14)=67.2, positive MACD, increasing volume",
    "features_used": ["rsi_14", "macd", "volume_change", "price_change_1h", "ema_20"],
    "training_samples": 50
  }
}
```

### Parameters
- `enable_ml_prediction`: `true` to enable ML signal (default: `false`)
- `ml_lookback`: bars to use for training (20-200, default: 50)

---

## 📊 Technical Indicators

### Available Indicators (80+)
Use full path notation: `ta.category.function_name`

**Momentum:**
- `ta.momentum.rsi` - RSI
- `ta.momentum.stoch` - Stochastic
- `ta.momentum.williams_r` - Williams %R

**Trend:**
- `ta.trend.sma_indicator` - Simple Moving Average
- `ta.trend.ema_indicator` - Exponential Moving Average
- `ta.trend.macd` - MACD
- `ta.trend.adx` - ADX

**Volatility:**
- `ta.volatility.bollinger_hband` - Bollinger Upper
- `ta.volatility.bollinger_lband` - Bollinger Lower
- `ta.volatility.average_true_range` - ATR

**Volume:**
- `ta.volume.on_balance_volume` - OBV
- `ta.volume.volume_price_trend` - VPT

### Example with Indicators
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "EURUSD",
    "parameters": {"timeframe": "H4", "count": 100}
  },
  "indicators": [
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.sma_indicator", "params": {"window": 20}},
    {"function": "ta.volatility.average_true_range", "params": {"window": 14}}
  ]
}
```

---

## 📈 Chart Generation

### Chart Types
- `single`: One panel with all columns
- `multi`: Separate panels for different indicators

### Multi-Panel Chart Example
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "GBPUSD",
    "parameters": {"timeframe": "D1", "count": 60}
  },
  "indicators": [
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.sma_indicator", "params": {"window": 20}}
  ],
  "chart": {
    "type": "multi",
    "panels": [
      {"columns": ["close", "sma_indicator_20"]},
      {"columns": ["rsi"], "reference_lines": [30, 70]}
    ],
    "filename": "gbpusd_analysis.png"
  }
}
```

### Chart Output
- Charts saved to **session working directory** (current terminal cwd)
- Returns **clickable file:// hyperlinks** for easy access
- Example: `[gbpusd_analysis.png](file:///C:/Git/MT5-MCP/gbpusd_analysis.png)`

---

## 🎯 Complete Example (All Features)

### Request
```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "H1", "count": 168}
  },
  "indicators": [
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.macd", "params": {}}
  ],
  "chart": {
    "type": "multi",
    "panels": [
      {"columns": ["close"]},
      {"columns": ["rsi"], "reference_lines": [30, 70]},
      {"columns": ["macd"]}
    ],
    "filename": "btcusd_full_analysis.png"
  },
  "forecast": {
    "periods": 24,
    "enable_ml_prediction": true,
    "ml_lookback": 50,
    "plot": true
  },
  "output_format": "markdown"
}
```

### Response Includes
1. **Data**: Historical bars with calculated indicators
2. **Chart**: Multi-panel visualization with clickable link
3. **Forecast Summary**: 
   - Current price
   - Final forecast price
   - Predicted % change
   - Confidence intervals (lower/upper)
   - Trend direction
4. **ML Trading Signal**:
   - BUY/SELL/HOLD recommendation
   - Confidence score (0-100%)
   - Probabilities
   - Reasoning
   - Features used

---

## ⚡ Common Use Cases

### 1. Quick Price Check + Forecast
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "EURUSD", "parameters": {"timeframe": "D1", "count": 30}},
  "forecast": {"periods": 7}
}
```

### 2. Technical Analysis + Chart
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "GBPUSD", "parameters": {"timeframe": "H1", "count": 100}},
  "indicators": [{"function": "ta.momentum.rsi", "params": {"window": 14}}],
  "chart": {"type": "multi", "panels": [{"columns": ["close"]}, {"columns": ["rsi"]}]}
}
```

### 3. ML Trading Signal (No Chart)
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "H4", "count": 168}},
  "forecast": {"periods": 12, "enable_ml_prediction": true, "plot": false},
  "output_format": "json"
}
```

### 4. Distribution Analysis (Custom Python)
For custom analysis like return distributions, use `execute_mt5` tool instead:
```python
rates = mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_H1, 0, 720)
df = pd.DataFrame(rates)
df['pct_change'] = df['close'].pct_change() * 100
result = {
    'mean': df['pct_change'].mean(),
    'std': df['pct_change'].std(),
    'q_5': df['pct_change'].quantile(0.05),
    'q_95': df['pct_change'].quantile(0.95)
}
```

---

## 📚 Documentation Links

- **Prophet Forecasting**: [FORECAST_EXAMPLES.md](../FORECAST_EXAMPLES.md)
- **XGBoost ML Signals**: [XGBOOST_ML_SIGNAL.md](./XGBOOST_ML_SIGNAL.md)
- **Chart Hyperlinks**: [CHART_HYPERLINKS.md](./CHART_HYPERLINKS.md)
- **Full Examples**: [QUICK_START_v0.4.0.md](../QUICK_START_v0.4.0.md)

---

## 🔑 Key Points for LLM Agents

1. **Use `mt5_analyze` for**: Price forecasting, ML trading signals, technical analysis with charts
2. **Use `execute_mt5` for**: Custom calculations, distribution analysis, raw data manipulation
3. **Forecast requires**: At least 168 bars (1 week of hourly data recommended)
4. **ML signal requires**: `enable_ml_prediction: true` + `ml_lookback` (20-200 bars)
5. **Charts are saved to**: Session working directory (current terminal cwd)
6. **Output includes**: Clickable `file://` hyperlinks for generated images

---

## ❓ FAQ

**Q: Why use `mt5_analyze` instead of `execute_mt5`?**
A: `mt5_analyze` provides structured input/output, automatic validation, and built-in Prophet + XGBoost ML capabilities. Use `execute_mt5` for custom Python code.

**Q: How accurate are ML signals?**
A: XGBoost model trains on-the-fly using recent bars. Confidence score indicates model certainty. Always combine with fundamental analysis.

**Q: Can I save ML models for reuse?**
A: Not yet. Models are trained per-request. Persistence planned for future versions.

**Q: What if I don't need forecasting?**
A: Omit the `forecast` parameter. Tool works for indicators + charts only.

**Q: How do I access generated charts?**
A: Charts are saved to your terminal's working directory. Output includes clickable `file://` links.

---

## 🚀 Pro Tips

1. **Start simple**: Query + forecast only, then add indicators/charts
2. **Use H1/H4/D1 timeframes**: Better for forecasting (more stable trends)
3. **Enable ML for 24h-7d forecasts**: Short-term signals work best
4. **Check confidence scores**: >80% = strong signal, <60% = uncertain
5. **Combine multiple symbols**: Run separate requests for correlation analysis
6. **Save important forecasts**: Copy chart links to external notes/docs

---

**Version**: MT5-MCP v0.4.0  
**Last Updated**: November 27, 2025
