# XGBoost ML Trading Signal Feature

## Overview

MT5-MCP v0.4.0 now includes **XGBoost machine learning** for buy/sell signal prediction alongside Prophet time series forecasting. This provides both price forecasting and actionable trading signals.

## How It Works

### 1. Feature Engineering
The ML model extracts features from price data and technical indicators:

**Price-based features:**
- Returns (price changes)
- High/Low ratio
- Close/Open ratio
- Rolling statistics (5, 10, 20 periods)
  - Mean returns
  - Standard deviation
  - Volume trends

**Technical indicator features** (if calculated):
- RSI
- MACD
- SMA/EMA
- Bollinger Bands
- ATR

### 2. Model Training
- XGBoost classifier trained on historical data
- Labels: Future price direction (3 bars ahead)
  - Up = BUY signal
  - Down = SELL signal
- 100 estimators, max_depth=5
- StandardScaler for feature normalization

### 3. Signal Generation
The model outputs:
- **Signal**: BUY, SELL, or NEUTRAL
- **Confidence**: Probability score (0-1)
- **Reasoning**: Key factors influencing prediction
- **Probabilities**: Separate buy/sell probabilities

### 4. Signal Interpretation
- **BUY**: Model predicts upward movement (>60% confidence)
- **SELL**: Model predicts downward movement (>60% confidence)
- **NEUTRAL**: Mixed signals or low confidence (<60%)

## Usage

### Basic Example

```python
from mt5_mcp.models import MT5AnalysisRequest, ForecastConfig

request = MT5AnalysisRequest(
    query={
        "operation": "copy_rates_from_pos",
        "symbol": "BTCUSD",
        "parameters": {
            "timeframe": "H1",
            "start_pos": 0,
            "count": 168  # 7 days for training
        }
    },
    forecast=ForecastConfig(
        periods=24,
        freq="h",
        enable_ml_prediction=True,  # Enable XGBoost
        ml_lookback=100  # Use 100 bars for features
    )
)
```

### With Technical Indicators

```python
request = MT5AnalysisRequest(
    query={
        "operation": "copy_rates_from_pos",
        "symbol": "EURUSD",
        "parameters": {"timeframe": "H4", "count": 200}
    },
    indicators=[
        {"function": "ta.trend.sma_indicator", "params": {"window": 20}},
        {"function": "ta.momentum.rsi", "params": {"window": 14}},
        {"function": "ta.trend.macd", "params": {}}
    ],
    forecast=ForecastConfig(
        periods=48,  # 48 hours
        enable_ml_prediction=True,
        ml_lookback=150
    )
)
```

### MCP Tool Usage

```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {
      "timeframe": "H1",
      "start_pos": 0,
      "count": 168
    }
  },
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 24}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}}
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

## Output Format

### ML Trading Signal Object

```json
{
  "signal": "BUY",
  "confidence": 0.73,
  "buy_probability": 0.73,
  "sell_probability": 0.27,
  "reasoning": "ML model predicts upward price movement with 73.0% confidence. Key factors: rsi_14, return_mean_10, sma_indicator_24",
  "features_used": 15,
  "training_samples": 145
}
```

### Complete Forecast Response

```json
{
  "forecast_summary": {
    "predictions": {
      "last_actual_price": 90942.0,
      "final_forecast_price": 95433.83,
      "predicted_change_pct": 4.94,
      "trend_direction": "bullish"
    },
    "ml_trading_signal": {
      "signal": "BUY",
      "confidence": 0.73,
      "reasoning": "ML model predicts upward price movement..."
    },
    "insights": [
      "Moderate bullish trend expected: +4.94%",
      "Moderate confidence in predictions",
      "ML Signal: BUY (73.0% confidence) - ML model predicts upward price movement..."
    ]
  }
}
```

## Configuration Parameters

### ForecastConfig.enable_ml_prediction
- **Type**: `bool`
- **Default**: `False`
- **Description**: Enable XGBoost ML model for trading signals

### ForecastConfig.ml_lookback
- **Type**: `int`
- **Default**: `50`
- **Range**: 20-200
- **Description**: Number of historical bars to use for feature engineering
- **Recommendation**: 
  - Use 50-100 for intraday (H1, H4)
  - Use 100-150 for daily timeframes
  - Higher values = more training data but slower

## Best Practices

### 1. Data Requirements
- **Minimum**: 70 bars (20 lookback + 50 for training)
- **Recommended**: 150-200 bars for stable predictions
- **Optimal**: 7+ days for H1, 30+ days for D1

### 2. Indicator Selection
Include complementary indicators:
- **Trend**: SMA, EMA (different periods)
- **Momentum**: RSI, MACD
- **Volatility**: Bollinger Bands, ATR

### 3. Signal Interpretation
- **Confidence >70%**: Strong signal, consider action
- **Confidence 60-70%**: Moderate signal, use with caution
- **Confidence <60%**: NEUTRAL, avoid trading
- **Always combine with**:
  - Prophet price forecast direction
  - Overall market analysis
  - Risk management rules

### 4. Timeframe Considerations
- **M1-M15**: Very noisy, use with extreme caution
- **H1-H4**: Good balance, recommended for ML
- **D1**: More stable but fewer training samples
- **W1+**: Not recommended (insufficient data)

## Technical Details

### Model Architecture
- **Algorithm**: XGBoost (Extreme Gradient Boosting)
- **Type**: Binary classification (BUY vs SELL)
- **Parameters**:
  - n_estimators: 100
  - max_depth: 5
  - learning_rate: 0.1
  - objective: binary:logistic
  - random_state: 42

### Feature Scaling
- StandardScaler (zero mean, unit variance)
- Applied to all features before training

### Labeling Strategy
- Future return calculated 3 bars ahead
- Positive return → BUY label (class 1)
- Negative return → SELL label (class 0)

### Confidence Thresholds
- BUY: buy_probability > 0.6
- SELL: sell_probability > 0.6
- NEUTRAL: max(probabilities) ≤ 0.6

## Examples

### Example 1: BTCUSD 24-Hour Forecast with ML

```python
request = MT5AnalysisRequest(
    query={
        "operation": "copy_rates_from_pos",
        "symbol": "BTCUSD",
        "parameters": {"timeframe": "H1", "count": 168}
    },
    indicators=[
        {"function": "ta.trend.sma_indicator", "params": {"window": 24}},
        {"function": "ta.trend.ema_indicator", "params": {"window": 12}},
        {"function": "ta.momentum.rsi", "params": {"window": 14}},
        {"function": "ta.trend.macd", "params": {}}
    ],
    forecast=ForecastConfig(
        periods=24,
        freq="h",
        enable_ml_prediction=True,
        ml_lookback=100,
        plot=True
    )
)

response = handle_mt5_analysis(request)
ml_signal = response.metadata["forecast_summary"]["ml_trading_signal"]

print(f"Signal: {ml_signal['signal']}")
print(f"Confidence: {ml_signal['confidence']:.1%}")
print(f"Reasoning: {ml_signal['reasoning']}")
```

### Example 2: EURUSD Daily Forecast

```python
request = MT5AnalysisRequest(
    query={
        "operation": "copy_rates_from_pos",
        "symbol": "EURUSD",
        "parameters": {"timeframe": "D1", "count": 90}
    },
    indicators=[
        {"function": "ta.trend.sma_indicator", "params": {"window": 20}},
        {"function": "ta.trend.sma_indicator", "params": {"window": 50}},
        {"function": "ta.momentum.rsi", "params": {"window": 14}}
    ],
    forecast=ForecastConfig(
        periods=7,
        freq="D",
        enable_ml_prediction=True,
        ml_lookback=60
    )
)
```

### Example 3: Error Handling

```python
try:
    response = handle_mt5_analysis(request)
    ml_signal = response.metadata["forecast_summary"].get("ml_trading_signal")
    
    if ml_signal:
        if ml_signal["signal"] == "ERROR":
            print(f"ML prediction failed: {ml_signal['reasoning']}")
        elif ml_signal["signal"] == "NEUTRAL":
            print("No clear signal - avoid trading")
        else:
            print(f"Action: {ml_signal['signal']} ({ml_signal['confidence']:.1%})")
    else:
        print("ML prediction not enabled")
        
except Exception as e:
    print(f"Analysis failed: {e}")
```

## Limitations & Warnings

### ⚠️ Important Disclaimers

1. **Not Financial Advice**: ML signals are predictions, not guarantees
2. **Past Performance**: Historical accuracy doesn't guarantee future results
3. **Market Changes**: Model trained on recent data may not adapt to regime changes
4. **Data Quality**: Garbage in, garbage out - ensure clean price data
5. **Overfitting Risk**: Model may memorize patterns that don't generalize

### Known Limitations

1. **Training Time**: ~1-2 seconds per request (acceptable for analysis)
2. **Memory Usage**: ~50-100MB for XGBoost model
3. **Feature Dependency**: Accuracy improves with more indicators
4. **Lookback Sensitivity**: Too low = noisy, too high = slow + overfitting
5. **Market Conditions**: Works best in trending markets

### When ML May Fail

- **Insufficient data**: <70 bars
- **Missing indicators**: No RSI/MACD/SMA features
- **High volatility**: News events, market gaps
- **Low liquidity**: Exotic pairs, off-hours
- **Regime changes**: Sudden policy changes, crises

## Comparison: Prophet vs XGBoost

| Feature | Prophet Forecast | XGBoost ML Signal |
|---------|-----------------|-------------------|
| **Purpose** | Price prediction | Direction classification |
| **Output** | Future prices | BUY/SELL/NEUTRAL |
| **Time Horizon** | Multi-period (1-365) | Short-term (1-5 bars) |
| **Uncertainty** | Confidence intervals | Probability scores |
| **Seasonality** | Detected automatically | Not considered |
| **Best For** | Trend analysis | Entry/exit timing |
| **Speed** | Fast (~0.5s) | Fast (~1s) |
| **Data Needs** | Min 10 bars | Min 70 bars |

**Recommendation**: Use both together
- Prophet: "Will price increase +4.9% in 24h?"
- XGBoost: "Should I BUY now? (73% confidence)"

## Troubleshooting

### Problem: "Insufficient data for ML prediction"
**Solution**: Increase `count` in query to at least `ml_lookback + 20`

### Problem: "No valid features available"
**Solution**: Add technical indicators to `indicators` list

### Problem: ML signal always NEUTRAL
**Possible causes**:
- Market is ranging (no clear trend)
- Insufficient training data
- Too many conflicting indicators
- High market noise

**Solution**: 
- Increase `ml_lookback` to 100-150
- Use clearer indicators (SMA, EMA, RSI)
- Try different timeframe (H4 instead of M15)

### Problem: Signal contradicts Prophet forecast
**Interpretation**: 
- Prophet: Long-term trend direction
- XGBoost: Short-term entry point
- Example: Prophet says "bullish +5%" (long-term), XGBoost says "SELL" (short-term pullback expected)

## Performance Metrics

Based on testing with BTCUSD H1 data:
- **Processing Time**: ~1-2 seconds
- **Features Generated**: 10-20 (depends on indicators)
- **Training Samples**: 100-150 (depends on lookback)
- **Memory Usage**: ~50MB per request
- **Accuracy**: Not disclosed (past performance ≠ future results)

## Dependencies

Added in v0.4.0:
```toml
"xgboost>=2.0.0",
"scikit-learn>=1.3.0"
```

## Version History

- **v0.4.0**: Initial XGBoost ML signal feature
  - Binary classification (BUY/SELL)
  - Automatic feature engineering
  - Integration with Prophet forecasting
  - Configurable lookback period

## Future Enhancements (Roadmap)

Potential improvements:
- [ ] Multi-class classification (STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL)
- [ ] Model persistence (save/load trained models)
- [ ] Feature importance visualization
- [ ] Backtesting framework
- [ ] Model performance metrics (precision, recall, F1)
- [ ] Ensemble methods (combine multiple models)
- [ ] LSTM/GRU integration for deep learning

## Related Documentation

- [FORECAST_EXAMPLES.md](FORECAST_EXAMPLES.md) - Prophet forecasting examples
- [QUICK_START_v0.4.0.md](QUICK_START_v0.4.0.md) - Getting started guide
- [IMPLEMENTATION_SUMMARY_v0.4.0.md](IMPLEMENTATION_SUMMARY_v0.4.0.md) - Technical implementation details

## Support

For issues or questions:
1. Check this documentation
2. Review example scripts
3. Enable debug logging
4. Check GitHub issues

---

**Disclaimer**: This ML feature is experimental. Always use proper risk management and combine ML signals with fundamental analysis, market conditions, and your trading strategy. Never risk more than you can afford to lose.
