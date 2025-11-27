# LLM Model Performance Analysis - MT5 MCP Server

## Test Query
"can you show me the trend for xauusd for the last 1 month?"

## Results Summary

| Model | Status | One-Shot Success | Issue |
|-------|--------|------------------|-------|
| Grok-Code-1-Fast | ❌ Failed | No | Called mt5.initialize()/shutdown() |
| Raptor mini | ❌ Failed | No | Called mt5.initialize()/shutdown() |
| GPT-5 mini | ❌ Failed | No | Called mt5.initialize()/shutdown() |
| GPT-5.1 | ❌ Failed | No | Called mt5.initialize()/shutdown() |
| Gemini 3 Pro | ✅ Success | Yes | - |
| GPT-4.1 | ✅ Success | Yes | - |
| GPT-4o | ✅ Success | Yes | - |
| Grok Code 1 Fast (BTCUSD) | ❌ Failed | No | Called mt5.initialize()/shutdown() |

**Success Rate: 37.5% (3/8 models)**

## Root Cause Analysis

### Primary Issue: MT5 Initialization Misunderstanding (62.5% of failures)

**Problem:** Models are generating standard MT5 Python code that includes connection management:

```python
# ❌ This pattern caused ALL failures:
if not mt5.initialize():
    raise Exception("MT5 initialization failed")

# ... MT5 queries ...

mt5.shutdown()
```

**Why This Fails:**
1. **Functions Don't Exist:** `mt5.initialize()` and `mt5.shutdown()` are **NOT** in the safe namespace
2. **Pre-Initialized Connection:** The MCP server pre-initializes MT5 on startup
3. **Security by Design:** Initialize/shutdown are intentionally excluded for safety
4. **Error Message:** `NoneType: None` - because `mt5.initialize` is `None` in the safe namespace

**Why Models Do This:**
- They're trained on standalone MT5 Python scripts that always start with `mt5.initialize()`
- Standard MT5 documentation and examples show this pattern
- Models don't recognize the **MCP execution context** where MT5 is already connected

### Secondary Issue: LLM Confusion (Solved by Design)

Some models might struggle with multiple tools vs. single tool approach, but the current design uses **one unified tool** (`execute_mt5`) which simplifies the decision-making process.

## Successful Models - What They Did Right

### ✅ Gemini 3 Pro
```python
# Directly used MT5 functions without initialization
rates = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_H4, 0, 300)
df = pd.DataFrame(rates)
# ... calculated indicators ...
plt.savefig('xauusd_trend.png')
```

**Key Success Factor:** Assumed MT5 was already connected

### ✅ GPT-4.1
```python
# Used datetime-based query without initialization
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, start, end)
df = pd.DataFrame(rates)
# ... trend analysis ...
```

**Key Success Factor:** Went straight to data fetching

### ✅ GPT-4o
```python
# One-liner approach, no initialization
rates = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_D1, 0, 30)
df = pd.DataFrame(rates)
# ... plotting ...
```

**Key Success Factor:** Minimal, direct approach

## Solution Implemented

### Updated Tool Description (server.py)

Added **prominent warning** at the top of the tool description:

```python
"⚠️ CRITICAL: MT5 IS ALREADY INITIALIZED ⚠️\n"
"• The MT5 connection is pre-initialized and managed by the MCP server\n"
"• DO NOT call mt5.initialize() - it will fail (function doesn't exist in safe namespace)\n"
"• DO NOT call mt5.shutdown() - it will fail (function doesn't exist in safe namespace)\n"
"• Just use mt5.copy_rates_*(), mt5.symbol_info(), etc. directly\n\n"
```

### Enhanced DON'TS Section

Added explicit prohibition:
```python
"✗ NEVER call mt5.initialize() or mt5.shutdown() - connection is pre-managed!\n"
```

## Expected Impact

### Before Fix:
- **37.5% success rate** on one-shot queries
- 5 out of 8 models failed due to initialization calls
- Error: `NoneType: None` (unhelpful error message)

### After Fix:
- **Expected: 75-100% success rate** on one-shot queries
- Models will see explicit warnings against initialization
- Clear guidance on pre-managed connection
- Should prevent the most common failure pattern

## Additional Observations

### Code Quality Comparison

**Failed Models:**
- More defensive programming (checking symbol availability, error handling)
- Longer, more verbose code
- Tried to be thorough with connection management

**Successful Models:**
- More concise code
- Assumed happy path
- Trusted the execution environment

**Lesson:** In MCP context, **trusting the pre-configured environment** leads to better results than defensive programming.

### Timeframe Choices

- Gemini 3 Pro: H4 (4-hour) - 300 bars for 1 month (smart for indicators)
- GPT-4.1: D1 (daily) with date range - clean 30-day approach
- GPT-4o: D1 (daily) - 30 bars (simple and effective)

**All successful models used appropriate timeframes for monthly trend analysis.**

## Recommendations

### For Users

1. **When models fail with `NoneType: None` error:**
   - Check if code contains `mt5.initialize()` or `mt5.shutdown()`
   - Provide explicit reminder: "MT5 is already initialized, don't call mt5.initialize()"

2. **For complex queries:**
   - Break down into steps
   - Verify intermediate results
   - Test with successful models first

### For Server Developers

1. ✅ **Implemented:** Add prominent warnings in tool description
2. **Future Enhancement:** Custom error handler that detects `mt5.initialize` in code and provides helpful error message
3. **Future Enhancement:** Add examples that explicitly show "no initialization needed"

## Testing Recommendations

Re-test the same query with updated tool description on failed models:
- Grok-Code-1-Fast
- Raptor mini  
- GPT-5 mini
- GPT-5.1

**Expected:** Success rate should improve to 75%+ as models will see the warning.

## Conclusion

**The problem is not that LLMs generate "false script"** - they generate valid standalone MT5 Python code.

**The issue is contextual mismatch:** Models don't inherently understand the **MCP execution model** where:
- MT5 is pre-initialized
- Connections are pre-managed
- Only safe functions are available

**Solution:** Explicit, prominent documentation in the tool description that clarifies the execution context and explicitly prohibits the problematic patterns.

The fix is **documentation-based** rather than code-based, which is appropriate for an LLM interface.
