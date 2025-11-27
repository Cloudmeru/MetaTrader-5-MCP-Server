# MetaTrader 5 MCP Server - Usage Examples

## Basic Queries

### 1. Get Symbol Information
```python
mt5.symbol_info('BTCUSD')._asdict()
```

### 2. Get Latest Price
```python
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_M1, 0, 1)
result = rates[0] if rates is not None else None
```

### 3. Historical Data (Last 100 Bars)
```python
mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
```

### 4. Calculate Profit
```python
mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, 'BTCUSD', 0.02, 70000.0, 71000.0)
```

## Technical Analysis Examples

### 5. Simple Moving Average (SMA)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['SMA_20'] = df['close'].rolling(20).mean()
df['SMA_50'] = df['close'].rolling(50).mean()
result = df[['time', 'close', 'SMA_20', 'SMA_50']].tail(20)
```

### 6. Exponential Moving Average (EMA)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['EMA_12'] = df['close'].ewm(span=12).mean()
df['EMA_26'] = df['close'].ewm(span=26).mean()
result = df[['time', 'close', 'EMA_12', 'EMA_26']].tail(20)
```

### 7. RSI (Relative Strength Index)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
result = df[['time', 'close', 'RSI']].tail(20)
```

### 8. MACD Indicator
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['MACD'] = ta.trend.macd_diff(df['close'])
df['MACD_signal'] = ta.trend.macd_signal(df['close'])
result = df[['time', 'close', 'MACD', 'MACD_signal']].tail(20)
```

### 9. Bollinger Bands
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['BB_upper'] = ta.volatility.bollinger_hband(df['close'], window=20)
df['BB_middle'] = ta.volatility.bollinger_mavg(df['close'], window=20)
df['BB_lower'] = ta.volatility.bollinger_lband(df['close'], window=20)
result = df[['time', 'close', 'BB_upper', 'BB_middle', 'BB_lower']].tail(20)
```

### 10. ATR (Average True Range)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
result = df[['time', 'close', 'ATR']].tail(20)
```

## Chart Plotting Examples

### 11. Simple Price Chart
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['close'], label='BTCUSD Close', linewidth=2)
plt.title('BTCUSD Price Chart')
plt.xlabel('Index')
plt.ylabel('Price (USD)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('btcusd_simple.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_simple.png'
```

### 12. Price with Moving Averages
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['SMA_20'] = df['close'].rolling(20).mean()
df['SMA_50'] = df['close'].rolling(50).mean()

plt.figure(figsize=(12, 6))
plt.plot(df.index, df['close'], label='Close Price', linewidth=2)
plt.plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--', alpha=0.7)
plt.plot(df.index, df['SMA_50'], label='SMA 50', linestyle='--', alpha=0.7)
plt.title('BTCUSD with Moving Averages')
plt.xlabel('Bar Index')
plt.ylabel('Price (USD)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('btcusd_ma.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_ma.png'
```

### 13. Price with Bollinger Bands
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['BB_upper'] = ta.volatility.bollinger_hband(df['close'], window=20)
df['BB_middle'] = ta.volatility.bollinger_mavg(df['close'], window=20)
df['BB_lower'] = ta.volatility.bollinger_lband(df['close'], window=20)

plt.figure(figsize=(12, 6))
plt.plot(df.index, df['close'], label='Close', linewidth=2, color='blue')
plt.plot(df.index, df['BB_upper'], label='Upper BB', linestyle='--', color='red', alpha=0.7)
plt.plot(df.index, df['BB_middle'], label='Middle BB', linestyle='--', color='gray', alpha=0.7)
plt.plot(df.index, df['BB_lower'], label='Lower BB', linestyle='--', color='green', alpha=0.7)
plt.fill_between(df.index, df['BB_upper'], df['BB_lower'], alpha=0.1, color='gray')
plt.title('BTCUSD with Bollinger Bands')
plt.xlabel('Bar Index')
plt.ylabel('Price (USD)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('btcusd_bb.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_bb.png'
```

### 14. Multi-Panel Chart (Price + RSI)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))
df['RSI'] = ta.momentum.rsi(df['close'], window=14)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Price chart
ax1.plot(df.index, df['close'], label='Close Price', linewidth=2)
ax1.set_title('BTCUSD Price Chart')
ax1.set_ylabel('Price (USD)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# RSI chart
ax2.plot(df.index, df['RSI'], label='RSI(14)', color='orange', linewidth=2)
ax2.axhline(70, color='red', linestyle='--', alpha=0.5, label='Overbought (70)')
ax2.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
ax2.axhline(50, color='gray', linestyle=':', alpha=0.3)
ax2.set_title('RSI Indicator')
ax2.set_ylabel('RSI Value')
ax2.set_xlabel('Bar Index')
ax2.set_ylim(0, 100)
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('btcusd_rsi.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_rsi.png'
```

### 15. Candlestick Chart (with mplfinance alternative)
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100))

fig, ax = plt.subplots(figsize=(12, 6))

# Simple candlestick representation using lines
for i in range(len(df)):
    color = 'green' if df.iloc[i]['close'] >= df.iloc[i]['open'] else 'red'
    # High-Low line
    ax.plot([i, i], [df.iloc[i]['low'], df.iloc[i]['high']], color=color, linewidth=1)
    # Open-Close box
    box_height = abs(df.iloc[i]['close'] - df.iloc[i]['open'])
    box_bottom = min(df.iloc[i]['open'], df.iloc[i]['close'])
    ax.add_patch(plt.Rectangle((i-0.3, box_bottom), 0.6, box_height, 
                                facecolor=color, edgecolor=color, alpha=0.7))

ax.set_title('BTCUSD Candlestick Chart')
ax.set_xlabel('Bar Index')
ax.set_ylabel('Price (USD)')
ax.grid(True, alpha=0.3)
plt.savefig('btcusd_candles.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_candles.png'
```

### 16. Complete Analysis Dashboard
```python
df = pd.DataFrame(mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 200))
df['SMA_20'] = df['close'].rolling(20).mean()
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
df['MACD'] = ta.trend.macd_diff(df['close'])
df['volume_sma'] = df['tick_volume'].rolling(20).mean()

fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

# Price with SMA
axes[0].plot(df.index, df['close'], label='Close', linewidth=2)
axes[0].plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--', alpha=0.7)
axes[0].set_title('BTCUSD - Complete Technical Analysis')
axes[0].set_ylabel('Price')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# RSI
axes[1].plot(df.index, df['RSI'], color='orange', linewidth=2)
axes[1].axhline(70, color='red', linestyle='--', alpha=0.5)
axes[1].axhline(30, color='green', linestyle='--', alpha=0.5)
axes[1].set_ylabel('RSI(14)')
axes[1].set_ylim(0, 100)
axes[1].grid(True, alpha=0.3)

# MACD
axes[2].plot(df.index, df['MACD'], color='blue', linewidth=2)
axes[2].axhline(0, color='black', linestyle='-', alpha=0.3)
axes[2].set_ylabel('MACD')
axes[2].grid(True, alpha=0.3)

# Volume
axes[3].bar(df.index, df['tick_volume'], alpha=0.5, label='Volume')
axes[3].plot(df.index, df['volume_sma'], color='red', label='Volume SMA', linewidth=2)
axes[3].set_ylabel('Volume')
axes[3].set_xlabel('Bar Index')
axes[3].legend()
axes[3].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('btcusd_dashboard.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Complete analysis dashboard saved to: btcusd_dashboard.png'
```

## Available Technical Indicators

The `ta` library provides these indicators:

### Momentum
- `ta.momentum.rsi()` - Relative Strength Index
- `ta.momentum.stoch()` - Stochastic Oscillator
- `ta.momentum.stoch_signal()` - Stochastic Signal
- `ta.momentum.williams_r()` - Williams %R
- `ta.momentum.awesome_oscillator()` - Awesome Oscillator

### Trend
- `ta.trend.macd()` - MACD Line
- `ta.trend.macd_signal()` - MACD Signal Line
- `ta.trend.macd_diff()` - MACD Histogram
- `ta.trend.ema_indicator()` - Exponential Moving Average
- `ta.trend.sma_indicator()` - Simple Moving Average
- `ta.trend.adx()` - Average Directional Index

### Volatility
- `ta.volatility.bollinger_hband()` - Bollinger Upper Band
- `ta.volatility.bollinger_lband()` - Bollinger Lower Band
- `ta.volatility.bollinger_mavg()` - Bollinger Middle Band
- `ta.volatility.average_true_range()` - ATR
- `ta.volatility.keltner_channel_hband()` - Keltner Upper
- `ta.volatility.keltner_channel_lband()` - Keltner Lower

### Volume
- `ta.volume.on_balance_volume()` - OBV
- `ta.volume.volume_price_trend()` - VPT
- `ta.volume.force_index()` - Force Index

## Tips for Effective Analysis

1. **Always close plots**: Use `plt.close()` after `plt.savefig()` to free memory
2. **Use appropriate timeframes**: Higher timeframes for trend analysis, lower for scalping
3. **Combine indicators**: Use multiple indicators for confirmation (e.g., RSI + MACD)
4. **Set proper figure sizes**: `figsize=(12, 6)` for single charts, `(14, 12)` for multi-panel
5. **Add grid and labels**: Makes charts more readable
6. **Save with good DPI**: Use `dpi=100` or `dpi=150` for clarity
