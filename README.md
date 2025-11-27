# MT5 MCP Server

MetaTrader 5 integration for Model Context Protocol (MCP). Provides read-only access to MT5 market data through Python commands.

## ⚡ What's New in v0.4.0

### 🔮 Prophet Time Series Forecasting
Predict future price movements based on historical data with confidence intervals.

### 🤖 XGBoost ML Trading Signals (NEW!)
Get buy/sell signal predictions with confidence scores using machine learning.

```json
{
  "query": {"operation": "copy_rates_from_pos", "symbol": "BTCUSD", "parameters": {"timeframe": "H1", "count": 168}},
  "indicators": [
    {"function": "ta.momentum.rsi", "params": {"window": 14}},
    {"function": "ta.trend.sma_indicator", "params": {"window": 24}}
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

**📖 Documentation:**
- **[QUICK_START_v0.4.0.md](QUICK_START_v0.4.0.md)** - Quick start guide with examples
- **[FORECAST_EXAMPLES.md](FORECAST_EXAMPLES.md)** - Comprehensive Prophet forecasting guide
- **[docs/XGBOOST_ML_SIGNAL.md](docs/XGBOOST_ML_SIGNAL.md)** - XGBoost ML signal documentation (NEW!)

## Prerequisites

- **Windows OS** (MetaTrader5 library is Windows-only)
- **MetaTrader 5 terminal** installed and running
- **Python 3.10+**

## Installation

1. Clone this repository:
```powershell
git clone <repository-url>
cd MT5-MCP
```

2. Install the package:
```powershell
pip install -e .
```

This will install all required dependencies:
- `mcp` - Model Context Protocol SDK
- `MetaTrader5` - Official MT5 Python library
- `pandas` - Data manipulation and formatting
- `prophet` - Time series forecasting
- `xgboost` - Machine learning for trading signals (NEW!)
- `scikit-learn` - ML utilities and preprocessing (NEW!)
- `ta` - Technical analysis indicators

## Configuration

### Claude Desktop

Add to your Claude Desktop configuration file:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mt5": {
      "command": "python",
      "args": ["-m", "mt5_mcp"]
    }
  }
}
```

### With Logging (for troubleshooting)

```json
{
  "mcpServers": {
    "mt5": {
      "command": "python",
      "args": ["-m", "mt5_mcp", "--log-file", "C:\\path\\to\\mt5_mcp.log"]
    }
  }
}
```

## Usage

The server provides a single tool: `execute_mt5`

### Available Objects

- `mt5` - MetaTrader5 module with read-only functions
- `datetime` - Python datetime module
- `pd` - pandas module (as `pd`)

### Example Queries

#### Get symbol information
```python
mt5.symbol_info('EURUSD')._asdict()
```

#### Get last week's BTCUSD daily data
```python
mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_D1, 0, 7)
```

#### Get last week's hourly data as DataFrame
```python
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 168)
pd.DataFrame(rates)
```

#### List all available symbols
```python
symbols = mt5.symbols_get()
[s.name for s in symbols]
```

#### Get account information
```python
mt5.account_info()._asdict()
```

#### Get terminal information
```python
mt5.terminal_info()._asdict()
```

### Multi-line Commands

You can execute complex multi-line Python code:

```python
from datetime import datetime, timedelta

# Get last 30 days of data
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

rates = mt5.copy_rates_range('EURUSD', mt5.TIMEFRAME_D1, start_date, end_date)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Calculate daily returns
df['return'] = df['close'].pct_change()

result = df[['time', 'close', 'return']].tail(10)
```

**Note:** For multi-line commands, assign your final result to a variable (like `result`, `data`, `output`, or `res`) to have it returned and formatted.

## Available MT5 Functions (Read-Only)

### Market Data
- `copy_rates()` - Get historical rates
- `copy_rates_from()` - Get rates from specific date
- `copy_rates_from_pos()` - Get rates from position
- `copy_rates_range()` - Get rates in date range
- `copy_ticks_from()` - Get tick data from specific date
- `copy_ticks_range()` - Get tick data in date range

### Symbol Information
- `symbol_info()` - Get symbol properties
- `symbol_info_tick()` - Get last tick
- `symbols_get()` - Get all symbols
- `symbols_total()` - Get symbol count

### Account/Terminal
- `account_info()` - Get account information
- `terminal_info()` - Get terminal information
- `version()` - Get MT5 version

### Timeframe Constants
- `TIMEFRAME_M1`, `TIMEFRAME_M5`, `TIMEFRAME_M15`, `TIMEFRAME_M30`
- `TIMEFRAME_H1`, `TIMEFRAME_H4`
- `TIMEFRAME_D1`, `TIMEFRAME_W1`, `TIMEFRAME_MN1`

## Troubleshooting

### MT5 Connection Issues

1. **Ensure MT5 terminal is running** before starting the MCP server
2. **Enable algo trading** in MT5: Tools → Options → Expert Advisors → Check "Allow automated trading"
3. **Check MT5 terminal logs** for any errors

### Enable Logging

Run the server with logging enabled:

```powershell
python -m mt5_mcp --log-file mt5_debug.log
```

Or configure it in Claude Desktop config (see Configuration section above).

### Common Errors

**"MT5 connection error: initialize() failed"**
- MT5 terminal is not running
- MT5 is not installed
- Algo trading is disabled in MT5

**"Symbol not found"**
- Check symbol name spelling (case-sensitive)
- Symbol may not be available in your MT5 account
- Use `mt5.symbols_get()` to see available symbols

**"No data returned"**
- Symbol may not have historical data for requested period
- Check date range validity
- Some symbols may have limited history

## Security

This server provides **read-only** access to MT5 data. Trading functions are explicitly excluded from the safe namespace:

### Blocked Functions
- `order_send()` - Place orders
- `order_check()` - Check order
- `positions_get()` - Get positions (read-only but blocked to prevent confusion)
- `positions_total()` - Position count
- All order/position modification functions

Only market data and information retrieval functions are available.

## License

MIT License

## Contributing

Contributions are welcome! Please ensure:
1. All code follows the read-only philosophy
2. Tests pass (when test suite is added)
3. Documentation is updated
