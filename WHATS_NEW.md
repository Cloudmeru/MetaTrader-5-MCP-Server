# What's New - Technical Analysis & Plotting Update

## 🎉 New Capabilities Added

Your MetaTrader 5 MCP Server now has **technical analysis and chart plotting capabilities**!

### ✨ Features Added

#### 1. **Technical Analysis Library (ta)**
   - 50+ technical indicators available
   - RSI, MACD, Bollinger Bands, SMA, EMA, ATR, and many more
   - Easy to use with pandas DataFrames

#### 2. **Chart Plotting (matplotlib)**
   - Create professional price charts
   - Multi-panel layouts (Price + Indicators)
   - Customizable styles and layouts
   - High-quality image output

#### 3. **Enhanced Data Analysis (numpy)**
   - Fast numerical operations
   - Statistical calculations
   - Array manipulations

### 📦 New Libraries in Namespace

The `execute_mt5` tool now has access to:
```python
- mt5        # MetaTrader 5 (existing)
- pd/pandas  # DataFrames (existing)
- datetime   # Date/time (existing)
- ta         # Technical analysis indicators (NEW)
- plt        # Matplotlib plotting (NEW)
- np/numpy   # Numerical operations (NEW)
- matplotlib # Full matplotlib library (NEW)
```

## 🚀 Quick Examples

### Example 1: Simple RSI Calculation
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
result = df[['time', 'close', 'RSI']].tail(10)
```

### Example 2: Price Chart with Moving Average
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['SMA_20'] = df['close'].rolling(20).mean()

plt.figure(figsize=(12, 6))
plt.plot(df.index, df['close'], label='Close', linewidth=2)
plt.plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--')
plt.title('BTCUSD Price Chart')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('btcusd.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd.png'
```

### Example 3: Complete Analysis Dashboard
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 200))
df['SMA_20'] = df['close'].rolling(20).mean()
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
df['MACD'] = ta.trend.macd_diff(df['close'])

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Price
axes[0].plot(df.index, df['close'], label='Close')
axes[0].plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--')
axes[0].legend()
axes[0].grid(True)

# RSI
axes[1].plot(df.index, df['RSI'], color='orange')
axes[1].axhline(70, color='red', linestyle='--')
axes[1].axhline(30, color='green', linestyle='--')
axes[1].set_ylim(0, 100)
axes[1].grid(True)

# MACD
axes[2].plot(df.index, df['MACD'], color='blue')
axes[2].axhline(0, color='black', linestyle='-')
axes[2].grid(True)

plt.tight_layout()
plt.savefig('analysis.png', dpi=100)
plt.close()
result = '📊 Complete analysis saved to: analysis.png'
```

## 🎯 How to Use in Copilot Chat

### Simple Queries
```
"Calculate RSI for BTCUSD last 100 bars"
"Show me BTCUSD with 20-period moving average"
"Create a price chart for EURUSD"
```

### Advanced Queries
```
"Analyze BTCUSD with RSI, MACD, and Bollinger Bands"
"Create a multi-panel chart showing price, RSI, and volume for BTCUSD"
"Calculate and plot support/resistance levels for GBPUSD"
```

## 📋 Available Technical Indicators

### Momentum Indicators
- RSI (Relative Strength Index)
- Stochastic Oscillator
- Williams %R
- Awesome Oscillator
- ROC (Rate of Change)

### Trend Indicators
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
- MACD (Moving Average Convergence Divergence)
- ADX (Average Directional Index)
- Parabolic SAR
- Ichimoku Cloud

### Volatility Indicators
- Bollinger Bands
- ATR (Average True Range)
- Keltner Channels
- Donchian Channels

### Volume Indicators
- OBV (On-Balance Volume)
- Volume Price Trend
- Force Index
- MFI (Money Flow Index)

## 🔧 How to Update

### If you already have the server running:

1. **Stop the server** in VS Code (Tools menu → MCP → Stop)
2. **Install new dependencies:**
   ```powershell
   pip install matplotlib ta numpy
   ```
3. **Start the server** again
4. **Test** with a new chat: "Calculate RSI for BTCUSD"

### Complete update steps:
See `UPDATE_GUIDE.md` for detailed instructions.

## 📚 Documentation

- **Full examples:** See `EXAMPLES.md` (16 complete examples)
- **Update guide:** See `UPDATE_GUIDE.md` (how to update and troubleshoot)
- **API reference:** Tool description includes all examples inline

## 🎨 Chart Output

Charts are saved as PNG files in the current directory:
- `btcusd_chart.png`
- `btcusd_analysis.png`
- `btcusd_dashboard.png`
- etc.

You can view them in VS Code or any image viewer.

## ⚡ Performance Tips

1. **Use appropriate timeframes:**
   - Lower timeframes (M1, M5) for short-term analysis
   - Higher timeframes (H4, D1) for trend analysis

2. **Limit data points:**
   - 100-200 bars is usually enough for most indicators
   - More data = slower calculations

3. **Close plots:**
   - Always use `plt.close()` after `plt.savefig()` to free memory

4. **Batch operations:**
   - Calculate multiple indicators in one command instead of separate calls

## 🐛 Troubleshooting

### Issue: "ta not found" or "plt not found"
**Solution:** Install dependencies:
```powershell
pip install matplotlib ta numpy
```

### Issue: Charts not displaying
**Solution:** Charts are saved as files, not displayed inline. Check the working directory for PNG files.

### Issue: Server won't start after update
**Solution:**
1. Close VS Code completely
2. Reopen VS Code
3. Start the server again

See `UPDATE_GUIDE.md` for more troubleshooting tips.

## 🎓 Learning Resources

### Technical Analysis Basics
- **RSI:** Overbought (>70), Oversold (<30)
- **MACD:** Bullish crossover (positive), Bearish crossover (negative)
- **Bollinger Bands:** Price breakout above upper band (overbought), below lower band (oversold)
- **SMA/EMA:** Price above MA (uptrend), below MA (downtrend)

### Matplotlib Basics
- `plt.figure(figsize=(width, height))` - Create figure
- `plt.plot(x, y, label='...')` - Line plot
- `plt.legend()` - Show legend
- `plt.grid(True)` - Add grid
- `plt.savefig('filename.png')` - Save chart
- `plt.close()` - Close figure

## 🚦 What's Next?

Potential future enhancements:
- [ ] Candlestick chart library (mplfinance)
- [ ] More advanced chart types (heatmaps, correlation matrices)
- [ ] Pattern recognition (head & shoulders, triangles, etc.)
- [ ] Backtesting capabilities
- [ ] Real-time data streaming
- [ ] Custom indicator creation

## 💡 Feedback

Found a bug or have a suggestion? The tool is designed to be flexible - you can:
- Combine any indicators you want
- Create any chart style you need
- Calculate custom metrics using numpy/pandas

The single `execute_mt5` tool handles everything!

---

**Version:** 0.2.0  
**Updated:** November 26, 2025  
**Dependencies:** MetaTrader5, pandas, matplotlib, ta, numpy
