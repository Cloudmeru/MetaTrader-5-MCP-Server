# MetaTrader 5 MCP Server

MetaTrader 5 integration for Model Context Protocol (MCP). Provides read-only access to MT5 market data through Python commands, built on the [FastMCP v3](https://gofastmcp.com) framework. Optionally encodes responses in [TOON](https://github.com/toon-format/toon) for LLM token savings.

## ⚡ What's New in v0.6.3

- **Production packaging fix** – The wheel now depends on `fastmcp-slim[server]>=3.4,<4` directly instead of the empty `fastmcp` meta-package. This bypasses a [known FastMCP v3 packaging hazard](https://github.com/PrefectHQ/fastmcp/issues/4207) that could leave the `fastmcp` namespace empty after a pip upgrade. Also: `MetaTrader5` is now platform-gated to Windows, so the wheel installs cleanly on Linux/macOS too (with a runtime guard that explains why the tools can't run there).

## ⚡ What's New in v0.6.1

- **TOON output encoding** – tabular tool responses (50-bar `copy_rates_from_pos`, etc.) are automatically encoded in [TOON](https://github.com/toon-format/toon) format when it would save ≥10 % of tokens over compact JSON. The LLM never has to ask for it; the server detects the shape. Install with `pip install "mt5-mcp[toon]"`.

## ⚡ What's New in v0.6.0

- **FastMCP v3** – Pinned `fastmcp>=3.0,<4`. The framework derives JSON schemas from your Python type annotations; no more string-encoded JSON parameters.
- **No more Gradio** – the experimental `gradio_server.py` and the `[ui]` extra are gone. This release is FastMCP-only.
- **Three transports in one process** – `stdio` for Claude Desktop / VS Code, Streamable HTTP on `/mcp`, and legacy SSE. `--transport all` runs them concurrently.
- **ASGI deployment** – `--asgi` emits an `app:app` for `uvicorn`, `gunicorn`, or `hypercorn`.
- **First-class middleware** – rate limiting (per-IP sliding window) and request logging live in FastMCP middleware, not in function bodies.
- **CI** – `lint` (ruff) + cross-platform `pytest` jobs on every push.
- **61 tests** – unit + integration via `fastmcp.Client`; CI runs them on Windows + Linux.

```powershell
# Default: stdio (Claude Desktop, VS Code, etc.)
python -m mt5_mcp
# or:
mt5-mcp

# Streamable HTTP with rate limiting
python -m mt5_mcp --transport http --host 0.0.0.0 --port 8000 --rate-limit 30

# All transports at once
python -m mt5_mcp --transport all --port 8000

# ASGI app for production (mount behind Uvicorn / Gunicorn / Hypercorn)
python -m mt5_mcp --asgi
```

**📖 Documentation:**
- **[USAGE.md](USAGE.md)** — Comprehensive instructions, tool reference, troubleshooting.
- **[CHANGELOG.md](CHANGELOG.md)** — Release history and migration notes from v0.5.x.
- **[docs/v0.6.0-architecture.md](docs/v0.6.0-architecture.md)** — Architecture rationale.

## Key Capabilities

- **Read-only MT5 bridge** — Safe namespace exposes only data-retrieval APIs and blocks all trading calls.
- **Transaction history access** — `history_deals_get`, `history_orders_get`, `positions_get`.
- **Multiple interaction models** — Write Python (`mt5_execute`), submit structured MT5 queries (`mt5_query`), or run full analyses with indicators, charts, and forecasts (`mt5_analyze`).
- **Technical analysis toolkit** — `ta`, `numpy`, `matplotlib` ship in the namespace for RSI, MACD, Bollinger Bands, multi-panel charts, and more.
- **Forecasting + ML signals** — Prophet forecasting and optional XGBoost buy/sell predictions with confidence scoring.
- **LLM-friendly guardrails** — Clear tool descriptions, runtime validation, and result-assignment reminders keep assistant output predictable.

## Available Tools

### `mt5_query`

Structured JSON interface that maps directly to MT5 read-only operations with automatic validation, timeframe conversion, and friendly error messages.

```json
{
  "operation": "copy_rates_from_pos",
  "symbol": "BTCUSD",
  "parameters": {"timeframe": "H1", "count": 100}
}
```

> **Tip**: `parameters` is a real JSON object in v0.6.0 — no more string-encoded JSON like the v0.5.x `"parameters": "{\"timeframe\":\"H1\"}"` form.

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

### `mt5_execute`

Free-form Python execution inside a curated namespace. Ideal for quick calculations, prototyping, and bespoke formatting.

```python
rates = mt5.copy_rates_from_pos('BTCUSD', mt5.TIMEFRAME_H1, 0, 100)
df = pd.DataFrame(rates)
df['RSI'] = ta.momentum.rsi(df['close'], window=14)
result = df[['time', 'close', 'RSI']].tail(10)
```

## Prerequisites

- **Windows OS** (MetaTrader5 library is Windows-only)
- **MetaTrader 5 terminal** installed and running
- **Python 3.10+**

## Installation

```powershell
git clone <repository-url>
cd MT5-MCP
pip install -e .
```

Optional extras:

```powershell
# Token-efficient output for LLM agents (TOON encoding)
pip install -e .[toon]

# Everything
pip install -e .[all]
```

This installs:

- `fastmcp` — MCP server framework (built on the official `mcp` SDK)
- `MetaTrader5` — official MT5 Python library
- `pandas`, `numpy`, `matplotlib`, `ta` — data + charting
- `prophet`, `xgboost`, `scikit-learn` — forecasting + ML signals
- `uvicorn`, `starlette`, `httpx` — HTTP transport
- `pydantic` — request/response validation

## Configuration

### Claude Desktop (stdio)

Add to your Claude Desktop configuration file at `%APPDATA%\Claude\claude_desktop_config.json`:

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

Or, if `mt5-mcp` is on your PATH:

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

For logging:

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

### HTTP MCP Clients

```json
{
  "mcpServers": {
    "mt5-http": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

Works with MCP Inspector, Claude Desktop (HTTP mode), VS Code extensions, and any remote deployment.

### ASGI / Production

```bash
python -m mt5_mcp --asgi          # prints "app:app" hint
uvicorn mt5_mcp.__main__:app --host 0.0.0.0 --port 8000 --workers 2
```

The lifespan context is wired in, so FastMCP startup/shutdown runs correctly under multi-worker Uvicorn.

## CLI

```
python -m mt5_mcp [--transport stdio|http|sse|all] [--host HOST] [--port PORT]
                  [--path PATH] [--rate-limit N]
                  [--log-level LEVEL] [--log-file FILE]
                  [--asgi]
```

| Flag | Default | Description |
|---|---|---|
| `--transport` | `stdio` | One of `stdio`, `http`, `sse`, `all` |
| `--host` | `127.0.0.1` | Host for HTTP/SSE transports |
| `--port` | `8000` | Port for HTTP/SSE transports |
| `--path` | `/mcp` | URL path for the HTTP endpoint |
| `--rate-limit` | `10` | Requests per IP per minute (`0` disables) |
| `--log-level` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--log-file` | — | Write logs to this file in addition to stderr |
| `--asgi` | — | Emit ASGI app handle (don't actually run the server) |

## TOON Output Encoding (Token-Efficient for LLMs)

The server automatically encodes tabular tool responses in [TOON](https://github.com/toon-format/toon) — a line-oriented, indentation-based format designed for LLM contexts. TOON declares array shapes once (`[N]` count + `{field1,field2,...}` column list) and uses indentation instead of braces, so tabular payloads (MT5 rate bars, indicator values, transaction history) use 20–40 % fewer tokens than compact JSON.

**The LLM doesn't choose. The server detects the shape and applies TOON only when it helps.** There is no `output_format` or `wire_format` parameter on any tool.

### Enable TOON

```powershell
pip install "mt5-mcp[toon]"
```

This installs [`toon-format/toon-python`](https://github.com/toon-format/toon-python) — the canonical Python implementation of the TOON spec. The package's PyPI distribution is a stub; the `[toon]` extra pulls the real release directly from GitHub.

### What the LLM sees

When the response contains a uniform array of ≥5 dicts in the `data` field AND encoding it as TOON saves ≥10 % of tokens vs. compact JSON, the server replaces that array with a TOON string and adds a sibling marker:

```json
{
  "operation": "copy_rates_from_pos",
  "success": true,
  "metadata": {"symbol": "BTCUSD", "timeframe": "H1", "count": 50},
  "data_format": "toon",
  "data": "data[50]{time,close,vol}:\n  1700000000,63000.0,0\n  1700003600,63010.0,100\n  ..."
}
```

The `"data_format": "toon"` marker tells the LLM the `data` field is a TOON document (decode with any TOON library, or call back through `mt5_query` to round-trip).

When the heuristic doesn't fire — single dicts, small arrays, heterogeneous rows, error envelopes, non-tabular shapes — the response is unchanged compact JSON. No surprises.

`mt5_execute` is intentionally excluded from the TOON heuristic: its output is already a pre-formatted text string (markdown tables, JSON snippets, plain text) that is more universally parseable than TOON.

### Measured savings (o200k_base tokens)

| Response shape | JSON | TOON | Saved |
|---|---:|---:|---:|
| `copy_rates` 50 bars (embedded as TOON) | 3,171 | 2,391 | **24.6 %** |
| `copy_rates` 200 bars (embedded as TOON) | 12,585 | 9,405 | **25.3 %** |
| `mt5_analyze` 20 rows + indicators | 956 | 673 | **29.6 %** |
| `mt5_execute` 30 rows | 709 | 564 | **20.5 %** |
| **Representative total** | **17,656** | **13,295** | **24.7 %** |

Tiny responses (`symbol_info` lookups, error envelopes) cost 1–3 extra tokens because TOON's `[N]` array header is overhead on objects with one or two keys. The heuristic keeps those as JSON automatically.

## Architecture & Compliance

- Built on FastMCP v3 (a thin wrapper around the official `mcp` Python SDK).
- Safe execution namespace exposes vetted objects (`mt5`, `datetime`, `pd`, `ta`, `numpy`, `matplotlib`) while blocking trading calls and disallowed modules.
- Runtime validation catches `mt5.initialize()` / `mt5.shutdown()` attempts and highlights the correct workflow.
- Thread-safe MT5 connection management plus IP-scoped rate limiting (HTTP/SSE only).
- Three concerns live in dedicated layers:
  - **`mcp_server.py`** — the `FastMCP` instance and middleware wiring
  - **`mcp_tools.py`** — the three tool functions
  - **`middleware.py`** — cross-cutting rate-limit + logging

## Troubleshooting

### FastMCP Install Hazard (`cannot import name 'FastMCP' from 'fastmcp'`)

If you see `ImportError: cannot import name 'FastMCP' from 'fastmcp' (unknown location)`
when running `mt5-mcp`, the underlying `fastmcp` package directory is empty. This is a
[known packaging hazard in FastMCP v3](https://github.com/PrefectHQ/fastmcp/issues/4207)
caused by pip's install/upgrade sequence — the `fastmcp` meta-package can wipe
files written by its companion `fastmcp-slim` package, leaving an empty namespace.

Recovery (one-time):

```powershell
pip uninstall -y fastmcp fastmcp-slim
pip install mt5-mcp
```

Or, if you prefer to keep using the legacy `pip install --upgrade mcp` workflow
that triggered the issue:

```powershell
pip install --force-reinstall fastmcp-slim==3.4.7
```

`mt5-mcp` v0.6.3+ depends directly on `fastmcp-slim[server]>=3.4,<4`, so fresh
installs skip this path entirely.

### MT5 Connection Issues

1. **Ensure MT5 terminal is running** before starting the MCP server.
2. **Enable algo trading** in MT5: *Tools → Options → Expert Advisors → Allow automated trading*.
3. **Check MT5 terminal logs** for any errors.

### Enable Logging

```powershell
python -m mt5_mcp --log-file mt5_debug.log
```

Or configure it in the Claude Desktop config (see *Configuration* above).

### Common Errors

**"MT5 connection error: initialize() failed"**
- MT5 terminal is not running.
- MT5 is not installed.
- Algo trading is disabled in MT5.

**"Symbol not found"**
- Check symbol name spelling (case-sensitive).
- Symbol may not be available in your MT5 account.
- Use `mt5_query` with `operation: symbols_get` to list available symbols.

**"No data returned"**
- Symbol may not have historical data for the requested period.
- Check date range validity.
- Some symbols may have limited history.

**"Rate limit exceeded"**
- HTTP/SSE transport only. Increase `--rate-limit`, or set `0` to disable.
- Stdio transport is single-process and is never rate-limited.

## Security

This server provides **read-only** access to MT5 data. Trading functions are explicitly excluded from the safe namespace:

### Blocked Functions

- `order_send()` — Place orders
- `order_check()` — Check order
- `positions_get()` — Get positions (read-only but blocked to prevent confusion)
- `positions_total()` — Position count
- All order/position modification functions

Only market data and information retrieval functions are available.

## License

MIT License

## Contributing

Contributions are welcome! Please ensure:

1. All code follows the read-only philosophy
2. Tests pass (`pytest -q`)
3. Documentation is updated
4. CI lint passes (`ruff check src tests`)
