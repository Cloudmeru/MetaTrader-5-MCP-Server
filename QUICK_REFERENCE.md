# MT5 MCP Server - Quick Reference

## Running the Server

### Standard
```powershell
python -m mt5_mcp
```

### With Logging
```powershell
python -m mt5_mcp --log-file mt5_debug.log
```

## Common Commands

### Get Symbol Information
```python
# Basic symbol info
mt5.symbol_info('EURUSD')._asdict()

# Current tick
mt5.symbol_info_tick('GBPUSD')._asdict()

# List all symbols
symbols = mt5.symbols_get()
[s.name for s in symbols]

# List first 10 symbols
symbols = mt5.symbols_get()
[s.name for s in symbols[:10]]
```

### Get Historical Data

```python
# Last 7 daily bars
mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_D1, 0, 7)

# Last 24 hourly bars
mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H1, 0, 24)

# Last 100 M5 bars
mt5.copy_rates_from_pos('GBPUSD', mt5.TIMEFRAME_M5, 0, 100)

# Date range
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=30)
end = datetime.now()
mt5.copy_rates_range('EURUSD', mt5.TIMEFRAME_D1, start, end)
```

### DataFrame Operations

```python
# Get data as DataFrame
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_D1, 0, 30)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
result = df[['time', 'open', 'high', 'low', 'close']]
```

```python
# Calculate returns
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_D1, 0, 30)
df = pd.DataFrame(rates)
df['return'] = df['close'].pct_change()
result = df[['close', 'return']].tail(10)
```

```python
# Calculate volatility
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H1, 0, 168)
df = pd.DataFrame(rates)
df['return'] = df['close'].pct_change()
volatility = df['return'].std()
print(f"Volatility: {volatility}")
```

### Account & Terminal Info

```python
# Account information
mt5.account_info()._asdict()

# Terminal information
mt5.terminal_info()._asdict()

# MT5 version
mt5.version()
```

### Timeframe Constants

```python
# Minutes
mt5.TIMEFRAME_M1   # 1 minute
mt5.TIMEFRAME_M5   # 5 minutes
mt5.TIMEFRAME_M15  # 15 minutes
mt5.TIMEFRAME_M30  # 30 minutes

# Hours
mt5.TIMEFRAME_H1   # 1 hour
mt5.TIMEFRAME_H4   # 4 hours

# Days and above
mt5.TIMEFRAME_D1   # Daily
mt5.TIMEFRAME_W1   # Weekly
mt5.TIMEFRAME_MN1  # Monthly
```

## Natural Language Examples for Claude

When using with Claude Desktop, you can ask:

- "Get me BTCUSD last week data"
- "Show EURUSD symbol information"
- "What symbols are available?"
- "Calculate the volatility of GBPUSD over the last 30 days"
- "Show me the last 10 hourly bars for USDJPY"
- "What's my account balance?"
- "Get EURUSD data for the last month and calculate daily returns"

## Tips

1. **Multi-line commands:** Assign final result to `result`, `data`, `output`, or `res` variable
2. **DateTime:** Use `from datetime import datetime, timedelta` for date operations
3. **DataFrames:** Convert time column with `df['time'] = pd.to_datetime(df['time'], unit='s')`
4. **Position parameter:** In `copy_rates_from_pos`, position 0 = current bar, 1 = previous bar
5. **Symbol names:** Case-sensitive (usually uppercase like 'EURUSD', 'GBPUSD')

## Troubleshooting

### MT5 Connection Failed
1. Ensure MT5 terminal is running
2. Enable algo trading: Tools → Options → Expert Advisors → "Allow automated trading"
3. Check MT5 terminal logs

### Symbol Not Found
1. Check spelling (case-sensitive)
2. Use `mt5.symbols_get()` to see available symbols
3. Symbol might not be in your MT5 account

### No Data Returned
1. Symbol may not have data for the requested period
2. Check timeframe validity
3. Try a different date range

### Enable Logging
```powershell
python -m mt5_mcp --log-file C:\path\to\debug.log
```

## File Locations

- **Claude Desktop Config:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Project:** `c:\Git\MT5-MCP`
- **Package:** `c:\Git\MT5-MCP\src\mt5_mcp`

## Configuration for Claude Desktop

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
