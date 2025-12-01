# USAGE

Comprehensive instructions for installing, configuring, and operating the MT5 MCP Server with all available tools.

## 1. Install & Configure

1. **Prerequisites**
   - Windows with MetaTrader 5 installed and running.
   - Python 3.10 or later plus `pip`.
   - Enable algo trading inside MT5 (`Tools → Options → Expert Advisors`).
2. **Install the package**
   ```powershell
   cd C:\Git\MT5-MCP
   pip install -e .
   ```
   Need the HTTP transport? Install the optional extras: `pip install -e .[ui]` (or `pip install "mt5-mcp[ui]"` from PyPI).
   
   **Package naming:** Install with `mt5-mcp` (hyphen), import/run as `mt5_mcp` (underscore).
3. **Register the server with Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json`).
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
   
   Or use the CLI script directly (if in PATH):
   ```json
   {
     "mcpServers": {
       "mt5": {
         "command": "mt5-mcp",
         "args": []
       }
     }
   }
   ```
4. (Optional) Enable logging for diagnostics:
   ```json
   "args": ["-m", "mt5_mcp", "--log-file", "C:\\logs\\mt5_mcp.log"]
   ```

### Transport Modes

The server now defaults to stdio only so existing MCP configurations keep working. Switch transports as needed:

```powershell
# Default behavior (run only stdio like previous version)
python -m mt5_mcp
# or:
mt5-mcp

# Run both transports
python -m mt5_mcp --transport both
# or:
mt5-mcp --transport both

# Run only streamable HTTP
python -m mt5_mcp --transport http --port 7860
# or:
mt5-mcp --transport http --port 7860
```

Add `--rate-limit <value>` when using HTTP to tune per-IP request budgets (set to `0` to disable, which is unsafe on public hosts).

### HTTP MCP Server Quick Start

1. Install the extras: `pip install "mt5-mcp[ui]"`.
2. Launch HTTP mode: `python -m mt5_mcp --transport http --host 0.0.0.0 --port 7860 --rate-limit 10` (or `mt5-mcp --transport http`).
3. Point any MCP client to `http://<host>:7860/gradio_api/mcp/`:

```json
{
  "mcpServers": {
    "mt5-http": {
      "url": "http://localhost:7860/gradio_api/mcp/"
    }
  }
}
```

**CLI options:** Use `python -m mt5_mcp` (module) or `mt5-mcp` (CLI script) interchangeably.

The endpoint speaks streamable HTTP (current MCP standard), works with SSE-compatible tools, and can be deployed to Windows servers or Hugging Face Spaces.

### Dual-Transport Mode

Use `python -m mt5_mcp --transport both` (or `mt5-mcp --transport both`) when you want stdio and HTTP simultaneously. The CLI keeps stdio unlimited for local clients and rate-limits HTTP per IP. Override host/port/rate limit as needed:

```powershell
python -m mt5_mcp --transport both --host 0.0.0.0 --port 7860 --rate-limit 20
# or:
mt5-mcp --transport both --host 0.0.0.0 --port 7860 --rate-limit 20
```

### Deployment Recipes

- **Local stdio (default):** `python -m mt5_mcp` or `mt5-mcp`
- **Local HTTP:** `python -m mt5_mcp --transport http --port 7860` or `mt5-mcp --transport http --port 7860`
- **Windows VPS / HF Spaces:** install `"mt5-mcp[ui]"`, run HTTP mode, and place the MT5 terminal on the same machine (MT5 remains Windows-only).

## 2. Namespace Reference

| Object | Description |
| --- | --- |
| `mt5` | MetaTrader5 module (read-only operations only) |
| `datetime` / `timedelta` | Standard datetime utilities |
| `pd` / `pandas` | DataFrame manipulation |
| `np` / `numpy` | Numerical helpers |
| `ta` | Technical analysis indicators |
| `plt` / `matplotlib` | Charting APIs |

⚠️ **Guardrails**: The server already initializes MT5. Never call `mt5.initialize()` or `mt5.shutdown()`, and always assign your final output to `result` (or another documented variable) so responses are captured.

## 3. Tool Overview

| Tool | When to use | Highlights |
| --- | --- | --- |
| `execute_mt5` | Free-form Python snippets | Full pandas/matplotlib access, perfect for bespoke analysis |
| `mt5_query` | Structured MT5 calls | JSON schema validation, timeframe conversion, friendly errors |
| `mt5_analyze` | Query + indicators + charts/forecasts | Chains data retrieval, TA indicators, chart rendering, Prophet + ML forecasts |

## 4. `execute_mt5` Recipes

### Common Patterns

```python
# Symbol info
result = mt5.symbol_info('EURUSD')._asdict()

# Last 7 daily bars
result = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_D1, 0, 7)
```

```python
# DataFrame analytics
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['return'] = df['close'].pct_change()
result = df[['time', 'close', 'return']].tail(10)
```

```python
# Technical analysis + chart export
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 200)
df = pd.DataFrame(rates)
df['SMA_20'] = df['close'].rolling(20).mean()
df['RSI'] = ta.momentum.rsi(df['close'], window=14)

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
axes[0].plot(df.index, df['close'], label='Close')
axes[0].plot(df.index, df['SMA_20'], label='SMA 20', linestyle='--')
axes[0].grid(True, alpha=0.3)
axes[0].legend()
axes[1].plot(df.index, df['RSI'], color='orange')
axes[1].axhline(70, color='red', linestyle='--', alpha=0.5)
axes[1].axhline(30, color='green', linestyle='--', alpha=0.5)
axes[1].set_ylim(0, 100)
axes[1].grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('btcusd_dashboard.png', dpi=100, bbox_inches='tight')
plt.close()
result = '📊 Chart saved to: btcusd_dashboard.png'
```

### Multi-line Execution Template

```python
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=30)
rates = mt5.copy_rates_range('EURUSD', mt5.TIMEFRAME_D1, start_date, end_date)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df['return'] = df['close'].pct_change()
result = df[['time', 'close', 'return']].tail(10)
```

## 5. `mt5_query` (Structured MT5 Calls)

- Supports all read-only MT5 operations: `copy_rates_from_pos`, `copy_rates_from`, `copy_rates_range`, `symbol_info`, `symbol_info_tick`, `symbols_get`, `symbols_total`, `copy_ticks_*`, `account_info`, `terminal_info`, `order_calc_profit`, `order_calc_margin`.
- Validates symbol names, timeframe strings (`M1`, `H1`, `D1`, `W1`, `MN1`), and parameter types up-front.
- Returns actionable errors (e.g., symbol suggestions) when validation fails.

**Example – hourly bars**
```json
{
  "operation": "copy_rates_from_pos",
  "symbol": "BTCUSD",
  "parameters": {
    "timeframe": "H1",
    "start_pos": 0,
    "count": 168
  }
}
```

**Example – profit calculation**
```json
{
  "operation": "order_calc_profit",
  "symbol": "BTCUSD",
  "parameters": {
    "action": "ORDER_TYPE_BUY",
    "volume": 0.02,
    "price_open": 70000,
    "price_close": 71000
  }
}
```

## 6. `mt5_analyze` (Indicators, Charts, Forecasts)

- Accepts the same `query` block as `mt5_query`, plus optional `indicators`, `chart`, `forecast`, and formatting controls.
- Indicator functions mirror `ta` paths (e.g., `ta.momentum.rsi`, `ta.trend.sma_indicator`).
- Charts can be `single` or `multi` panel with reference lines and custom columns.
- Forecast block uses Prophet and can enable XGBoost ML trading signals.

**Example – multi-panel analysis + forecast**
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
  "chart": {
    "type": "multi",
    "panels": [
      {"columns": ["close", "sma_indicator_50"]},
      {"columns": ["rsi"], "reference_lines": [30, 70]}
    ]
  },
  "forecast": {
    "periods": 30,
    "freq": "D",
    "plot": true,
    "enable_ml_prediction": true,
    "ml_lookback": 100
  }
}
```

### Forecast Parameters

| Parameter | Description |
| --- | --- |
| `periods` | Forecast horizon (1–365) |
| `freq` | `D`, `h`, or `min` (defaults to the query timeframe) |
| `plot` / `plot_components` | Generate PNG outputs |
| `seasonality_mode` | `additive` or `multiplicative` |
| `growth` | `linear` or `logistic` |
| `enable_ml_prediction` | Toggle XGBoost signal generation |
| `ml_lookback` | Bars used for ML feature engineering (20–200) |

### Forecast & ML Best Practices

- Minimum 10 data points; aim for 60+ daily or 100+ hourly bars for stability.
- Typical horizons: intraday (H1, 24–48 periods), swing (D1, 7–30), position (D1/W1, 30–180).
- Use `uncertainty_samples` (e.g., 500) to balance speed vs. confidence interval fidelity.
- Disable `include_history` or `plot_components` when large payloads are unnecessary.

## 7. Complete MT5 Function Reference

The following read-only calls are supported in both `execute_mt5` and `mt5_query`:

- `copy_rates`, `copy_rates_from`, `copy_rates_from_pos`, `copy_rates_range`
- `copy_ticks_from`, `copy_ticks_range`
- `symbol_info`, `symbol_info_tick`, `symbol_select`, `symbols_get`, `symbols_total`
- `account_info`, `terminal_info`, `version`
- `order_calc_profit`, `order_calc_margin`
- Timeframe constants: `TIMEFRAME_M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`, `W1`, `MN1`

## 8. Troubleshooting & Logging

1. **Connection issues** – Start the MT5 terminal first, confirm algo trading is enabled, and ensure no other MT5 Python clients are running.
2. **Result missing** – Always assign to `result` (or the documented alias) before returning.
3. **Forbidden functions** – The server blocks `mt5.initialize()` / `mt5.shutdown()` and returns guidance; remove those calls and retry.
4. **View logs** – Launch with `python -m mt5_mcp --log-file mt5_debug.log` (or `mt5-mcp --log-file mt5_debug.log`) and inspect the generated log for stack traces or MT5 errors.
5. **Chart paths** – Generated PNGs are written to the working directory and surfaced in the tool response; ensure the directory is writable.

## 9. Tips for AI Assistants

- Prefer structured JSON (`mt5_query` / `mt5_analyze`) when a deterministic schema is easier for the LLM.
- Use descriptive chart filenames (e.g., `btcusd_trend.png`) and remember they are now ignored by `.gitignore`.
- Keep indicator windows proportional to the timeframe (larger windows for daily data, smaller for intraday).
- Chain operations thoughtfully: query → DataFrame cleanup → TA features → summarize/plot.
