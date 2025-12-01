# MetaTrader 5 MCP Server

MetaTrader 5 integration for Model Context Protocol (MCP). Provides read-only access to MT5 market data through Python commands.

## ⚡ What's New in v0.5.0

- **Dual-transport launcher** – `python -m mt5_mcp` keeps the stdio-only default for desktop clients, while `--transport http` or `--transport both` enables the new streamable HTTP endpoint.
- **Gradio MCP server** – Install the optional `[ui]` extra to expose `/gradio_api/mcp/` with native MCP schemas, progress updates, and Hugging Face Spaces compatibility.
- **Built-in rate limiting** – HTTP requests are throttled per IP (10 req/min by default) with CLI overrides and the ability to disable caps for trusted networks.
- **Thread-safe MT5 access** – Shared connection management and locking prevent concurrent HTTP calls from colliding with stdio traffic.
- **Documentation refresh** – README/USAGE now cover HTTP setup, MCP client snippets, deployment tips, and migration guidance for v0.5.0.

```powershell
# Default behavior (stdio only, backward compatible)
python -m mt5_mcp
# or simply:
mt5-mcp

# Streamable HTTP with rate limiting and a custom port
python -m mt5_mcp --transport http --host 0.0.0.0 --port 7860 --rate-limit 30
# or:
mt5-mcp --transport http --host 0.0.0.0 --port 7860 --rate-limit 30

# Dual mode (stdio + HTTP)
python -m mt5_mcp --transport both
# or:
mt5-mcp --transport both
```

**📖 Documentation:**
- **[USAGE.md](USAGE.md)** - Comprehensive instructions, tool reference, and troubleshooting
- **[CHANGELOG.md](CHANGELOG.md)** - Release history and migration notes

## Key Capabilities

- **Read-only MT5 bridge** – Safe namespace exposes only data-retrieval APIs and blocks all trading calls.
- **Multiple interaction models** – Write Python (`execute_mt5`), submit structured MT5 queries (`mt5_query`), or run full analyses with indicators, charts, and forecasts (`mt5_analyze`).
- **Technical analysis toolkit** – `ta`, `numpy`, and `matplotlib` ship in the namespace for RSI, MACD, Bollinger Bands, multi-panel charts, and more.
- **Forecasting + ML signals** – Prophet forecasting and optional XGBoost buy/sell predictions with confidence scoring.
- **LLM-friendly guardrails** – Clear tool descriptions, runtime validation, and result-assignment reminders keep assistant output predictable.

## Available Tools

### `execute_mt5`
Free-form Python execution inside a curated namespace. Ideal for quick calculations, prototyping, and bespoke formatting.

```python
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
result = df[['time', 'close', 'RSI']].tail(10)
```

### `mt5_query`
Structured JSON interface that maps directly to MT5 read-only operations with automatic validation, timeframe conversion, and friendly error messages.

```json
{
  "operation": "copy_rates_from_pos",
  "symbol": "BTCUSD",
  "parameters": {"timeframe": "H1", "count": 100}
}
```

### `mt5_analyze`
Pipeline tool that chains a query → optional indicators → charts and/or Prophet forecasts (with optional ML signals) in one request.

```json
{
  "query": {
    "operation": "copy_rates_from_pos",
    "symbol": "BTCUSD",
    "parameters": {"timeframe": "D1", "count": 180}
  },
  "indicators": [
    {"function": "ta.trend.sma_indicator", "params": {"window": 50}},
    {"function": "ta.momentum.rsi", "params": {"window": 14}}
  ],
  "forecast": {"periods": 30, "plot": true, "enable_ml_prediction": true}
}
```

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

Need the HTTP transport? Include the extra Gradio dependency:

```powershell
pip install -e .[ui]
# or when installing from PyPI
pip install "mt5-mcp[ui]"
```

**Package naming:** The package is named `mt5-mcp` (with hyphen) on PyPI, but the Python module uses `mt5_mcp` (with underscore). This is standard Python convention.

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

Alternatively, if the `mt5-mcp` CLI script is in your PATH:

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

### Transport Modes (CLI)

Choose how the server exposes MCP transports directly from the command line:

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
python -m mt5_mcp --transport http --host 0.0.0.0 --port 7860
# or:
mt5-mcp --transport http --host 0.0.0.0 --port 7860
```

Additional flags:

- `--rate-limit <value>` – Requests per IP each minute (set to `0` to disable; keep enabled for public servers).
- `--log-level` / `--log-file` – Tailored diagnostics across transports.

### HTTP MCP Clients

1. Install the optional extras: `pip install "mt5-mcp[ui]"` (or `pip install -e .[ui]` while developing).
2. Launch the HTTP transport: `python -m mt5_mcp --transport http --host 0.0.0.0 --port 7860` (or `mt5-mcp --transport http`).
3. Point any MCP client to the new endpoint:

```json
{
  "mcpServers": {
    "mt5-http": {
      "url": "http://localhost:7860/gradio_api/mcp/"
    }
  }
}
```

**Note:** Use `python -m mt5_mcp` (module name with underscore) or the `mt5-mcp` CLI command (package name with hyphen) interchangeably.

This endpoint works with MCP Inspector, Claude Desktop (when configured for HTTP), VS Code extensions, or remote deployments (Hugging Face Spaces, Windows VPS, etc.).

## Usage Overview

Refer to **[USAGE.md](USAGE.md)** for a complete walkthrough that covers prerequisites, configuration screens, troubleshooting tips, and in-depth per-tool examples. Below is a quick multi-line example using `execute_mt5`:

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

**Note:** Always assign the final output to `result` (or another variable noted in USAGE.md) so the MCP response can be formatted correctly.

## Architecture & Compliance

- Built on `mcp.server.lowlevel.Server` for stdio clients and Gradio v6 for streamable HTTP/SSE, both sharing the same MT5-safe namespace.
- Safe execution namespace exposes vetted objects (`mt5`, `datetime`, `pd`, `ta`, `numpy`, `matplotlib`) while blocking trading calls and disallowed modules.
- Runtime validation catches `mt5.initialize()` / `mt5.shutdown()` attempts, highlights the correct workflow, and enforces result assignment.
- Thread-safe MT5 connection management plus IP-scoped rate limiting protect terminals from abusive HTTP workloads.
- Documentation, tool signatures, and CLI examples match MCP SDK and Gradio MCP guidance for predictable LLM behavior.

## Troubleshooting

### MT5 Connection Issues

1. **Ensure MT5 terminal is running** before starting the MCP server
2. **Enable algo trading** in MT5: Tools → Options → Expert Advisors → Check "Allow automated trading"
3. **Check MT5 terminal logs** for any errors

### Enable Logging

Run the server with logging enabled:

```powershell
python -m mt5_mcp --log-file mt5_debug.log
# or:
mt5-mcp --log-file mt5_debug.log
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
