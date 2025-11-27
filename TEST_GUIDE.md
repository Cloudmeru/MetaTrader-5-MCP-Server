# MT5 MCP Server Testing Guide

## Common LLM Failures & How to Fix Them

### Problem 1: Models calling `mt5.initialize()` or `mt5.shutdown()`

**Symptom:**
```
Error executing command:

NoneType: None
```

**Root Cause:**
- LLMs trained on standalone MT5 scripts try to initialize the connection
- These functions DON'T EXIST in the MCP server's safe namespace
- The connection is PRE-INITIALIZED and managed by the server

**Solution:**
The server now has:
1. **Prominent warning** at the top of tool description with emoji borders
2. **Runtime validation** that blocks `mt5.initialize()` calls before execution
3. **Helpful error message** explaining the correct approach

**Fixed Models:** This should now work for Grok Code 1 Fast, Raptor, and similar models.

---

### Problem 2: "Command executed successfully (no output)"

**Symptom:**
```
Command executed successfully (no output)

The trend data for BTCUSD over the last month has been retrieved successfully. 
However, there is no output to display.
```

**Root Cause:**
- Models execute code but don't assign the final output to `result` variable
- Example: `df[['time', 'close']]` instead of `result = df[['time', 'close']]`
- The executor looks for `result`, `data`, `output`, or `res` variables

**Solution:**
The server now has:
1. **"ALWAYS assign to result"** in the 🚨 STOP banner at the top
2. **"(assign to result!)"** reminder in every example
3. **"MUST assign result!"** warning in plot examples
4. **Updated command parameter description** with critical rules

**Fixed Models:** This should now work for gpt-4o, gpt-4.1, gpt-5 mini.

---

## Testing Checklist

### Basic Queries (Should always work)
```python
# 1. Symbol info with result assignment
result = mt5.symbol_info('BTCUSD')._asdict()

# 2. Latest price with result assignment
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_M1, 0, 1)
result = rates[0] if rates is not None else None

# 3. Historical data with result assignment
result = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 24)
```

### Technical Analysis (Should show data)
```python
# 4. Moving averages with DataFrame output
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['SMA_20'] = df['close'].rolling(20).mean()
df['EMA_50'] = df['close'].ewm(span=50).mean()
result = df[['time', 'close', 'SMA_20', 'EMA_50']].tail(10)

# 5. RSI indicator
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
result = df[['time', 'close', 'RSI']].tail(20)
```

### Chart Generation (Should create files)
```python
# 6. Simple price chart
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['SMA_20'] = df['close'].rolling(20).mean()
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['close'], label='Close', linewidth=2)
plt.plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--')
plt.title('BTCUSD Price Chart')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('test_chart.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: test_chart.png'
```

---

## What to Test With Different Models

### Test Query: "Show me the trend for BTCUSD for the last month"

**Expected Correct Behavior:**
1. ✅ Fetch data using `mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_D1, 0, 30)`
2. ✅ Calculate indicators (SMA, RSI, trend direction)
3. ✅ Assign final output to `result` variable
4. ✅ Optionally create a chart with `plt.savefig()`

**Common Mistakes (Now Blocked/Warned):**
1. ❌ Calling `mt5.initialize()` → **Blocked with helpful error**
2. ❌ Not assigning to `result` → **Warning in description, executor handles gracefully**
3. ❌ Calling `mt5.shutdown()` → **Blocked with helpful error**

---

## Expected Success Rate

### Before Fixes (v0.2.0):
- **37.5%** success rate (3/8 models)
- Failed models: Grok Code 1 Fast, Raptor, gpt-5 mini, gpt-4o, gpt-4.1

### After Fixes (v0.2.1):
- **Expected 87.5-100%** success rate (7-8/8 models)
- Should fix: Grok Code 1 Fast, Raptor (mt5.initialize blocks)
- Should fix: gpt-4o, gpt-4.1, gpt-5 mini (result assignment reminders)

---

## Debugging Failed Responses

If a model still fails:

1. **Check for mt5.initialize() calls:**
   - Should be blocked with error message
   - If not blocked, check server.py validation logic

2. **Check for result assignment:**
   - Look for `result =` in the generated code
   - If missing, the executor will return "no output"

3. **Check the command structure:**
   - Should start with `rates = mt5.copy_rates_from_pos(...)`
   - Should NOT start with conditional checks or imports

4. **Enable logging:**
   ```powershell
   # Edit .vscode/mcp.json to add log file
   "command": "python",
   "args": ["-m", "mt5_mcp", "--log-file", "C:/Git/MT5-MCP/mcp_server.log"]
   ```

---

## Server Restart After Changes

After modifying `server.py`:

1. **Close VS Code completely** (File → Exit)
2. **Reopen VS Code**
3. **Wait 2-3 seconds** for MCP server to initialize
4. **Test with:** "use #MetaTrader 5 MCP Server show me symbol info for BTCUSD"

Expected output should be a JSON dictionary with symbol details.

---

## Version History

### v0.2.1 (Current)
- Added 🚨 STOP banner with emoji borders at top of description
- Added runtime validation to block `mt5.initialize()` calls
- Added "assign to result!" reminders in ALL examples
- Updated command parameter with critical rules
- Expected to fix 4-5 previously failing models

### v0.2.0
- Added technical analysis capabilities (ta library)
- Added chart plotting (matplotlib)
- 12 comprehensive examples
- Success rate: 37.5% (3/8 models)

### v0.1.0
- Initial release
- Basic MT5 data access
- Safe namespace with read-only functions
