# XGBoost ML Signal - Quick Reference

## 🚀 Quick Start

```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "H1", "count": 168}
  },
  "indicators": [
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.sma_indicator", "params": {"window": 24}}
  ],
  "forecast": {
    "periods": 24,
    "enable_ml_prediction": true,
    "ml_lookback": 100
  }
}
```

## 📊 Signal Types

| Signal | Meaning | Confidence | Action |
|--------|---------|------------|--------|
| **BUY** | Upward movement expected | >60% | Consider long position |
| **SELL** | Downward movement expected | >60% | Consider short position |
| **NEUTRAL** | No clear direction | <60% | Avoid trading |
| **ERROR** | Prediction failed | 0% | Check logs |

## 🎯 Configuration

### Required Parameters
```json
"forecast": {
  "enable_ml_prediction": true  // Enable ML
}
```

### Optional Parameters
```json
"forecast": {
  "enable_ml_prediction": true,
  "ml_lookback": 100  // Default: 50, Range: 20-200
}
```

### Data Requirements
```json
"query": {
  "parameters": {
    "count": 168  // Min: 70, Recommended: 150+
  }
}
```

## 📈 Response Format

```json
{
  "forecast_summary": {
    "ml_trading_signal": {
      "signal": "BUY",
      "confidence": 0.73,
      "buy_probability": 0.73,
      "sell_probability": 0.27,
      "reasoning": "ML model predicts upward price movement...",
      "features_used": 15,
      "training_samples": 145
    }
  }
}
```

## 💡 Best Practices

### 1. Data Size
- **H1**: 150-200 bars (7-10 days)
- **H4**: 100-150 bars (2-3 weeks)
- **D1**: 100-150 bars (3-5 months)

### 2. Indicators
**Recommended combo:**
```json
[
  {"function": "ta.trend.sma_indicator", "params": {"window": 24}},
  {"function": "ta.trend.ema_indicator", "params": {"window": 12}},
  {"function": "ta.momentum.rsi", "params": {"window": 14}},
  {"function": "ta.trend.macd", "params": {}}
]
```

### 3. Lookback Values
- **Fast markets (H1)**: 50-100
- **Stable markets (H4, D1)**: 100-150
- **Higher = more data but slower**

### 4. Confidence Interpretation
- **>70%**: Strong signal, high confidence
- **60-70%**: Moderate signal, use caution
- **<60%**: NEUTRAL, avoid trading

## ⚠️ Common Issues

### "Insufficient data for ML prediction"
**Fix**: Increase `count` to at least `ml_lookback + 20`

### "No valid features available"
**Fix**: Add technical indicators to request

### Signal always NEUTRAL
**Causes**:
- Ranging market (no clear trend)
- Too few indicators
- Insufficient training data

**Fix**:
- Increase `ml_lookback` to 100+
- Add RSI, MACD, SMA indicators
- Try different timeframe (H4 instead of M15)

### Signal contradicts Prophet forecast
**Normal**: 
- Prophet: Long-term trend
- XGBoost: Short-term entry/exit

**Example**: Prophet says "bullish +5%", XGBoost says "SELL" = Short-term pullback expected before continued rise

## 🔧 Debugging

### Enable in Python
```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Check Signal Details
```python
ml_signal = response.metadata["forecast_summary"]["ml_trading_signal"]
print(f"Signal: {ml_signal['signal']}")
print(f"Confidence: {ml_signal['confidence']:.1%}")
print(f"Reasoning: {ml_signal['reasoning']}")
print(f"Features: {ml_signal['features_used']}")
print(f"Training samples: {ml_signal['training_samples']}")
```

## 📚 Complete Documentation

- **[XGBOOST_ML_SIGNAL.md](XGBOOST_ML_SIGNAL.md)** - Full guide
- **[QUICK_START_v0.4.0.md](../QUICK_START_v0.4.0.md)** - Quick start
- **[XGBOOST_IMPLEMENTATION_SUMMARY.md](XGBOOST_IMPLEMENTATION_SUMMARY.md)** - Technical details

## 🎓 Example Workflows

### Day Trading (H1)
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "H1", "count": 168}},
  "indicators": [
    {"function": "ta.trend.ema_indicator", "params": {"window": 12}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.macd", "params": {}}
  ],
  "forecast": {"periods": 24, "freq": "h", "enable_ml_prediction": true, "ml_lookback": 100}
}
```

### Swing Trading (H4)
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "EURUSD", "parameters": {"timeframe": "H4", "count": 200}},
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 50}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.volatility.bollinger_hband", "params": {"window": 20}},
    {"function": "ta.volatility.bollinger_lband", "params": {"window": 20}}
  ],
  "forecast": {"periods": 48, "freq": "h", "enable_ml_prediction": true, "ml_lookback": 150}
}
```

### Position Trading (D1)
```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "XAUUSD", "parameters": {"timeframe": "D1", "count": 180}},
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 50}},
    {"function": "ta.trend.sma_indicator", "params": {"window": 200}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}}
  ],
  "forecast": {"periods": 30, "freq": "D", "enable_ml_prediction": true, "ml_lookback": 120}
}
```

## ⏱️ Performance

- **Training**: ~1-2 seconds
- **Memory**: ~50MB per request
- **Features**: 10-20 (depends on indicators)
- **Samples**: 100-150 (depends on lookback)

## 🔒 Disclaimers

- ⚠️ **Not financial advice**
- ⚠️ **Past performance ≠ future results**
- ⚠️ **Always use risk management**
- ⚠️ **Combine with other analysis**
- ⚠️ **Paper trade first**

---

**Version**: MT5-MCP v0.4.0  
**Last Updated**: January 28, 2025
