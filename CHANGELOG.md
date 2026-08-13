# CHANGELOG

All notable changes will be tracked here. Dates reflect when the feature set landed in the repository; see git history for exact commits.

## v0.6.3 – Production packaging fix (August 13, 2026)

### Fixed the FastMCP install hazard

`pyproject.toml` now declares its FastMCP dependency on
`fastmcp-slim[server]>=3.4,<4` instead of the empty `fastmcp`
meta-package. The two PyPI distributions share the `fastmcp` import
namespace by design — `fastmcp` is a 4-file meta-package that exists
only to pull in `fastmcp-slim`, which has the real 273-file code base.

When *both* packages are present (which happens whenever a user installs
the meta-package), pip's install/upgrade sequence can delete the
`fastmcp/__init__.py` files written by `fastmcp-slim`, leaving the
import namespace empty and breaking `from fastmcp import FastMCP` with
a confusing `ImportError`. This is the documented
[PrefectHQ/fastmcp#4207](https://github.com/PrefectHQ/fastmcp/issues/4207)
hazard; the maintainer chose to document it rather than fix it with a
packaging change (PR #4210 closed in favor of docs).

By depending directly on `fastmcp-slim[server]`, our wheel
**insulates users from this hazard** — pip never touches the meta-package,
so the install-dance bug cannot happen on a fresh install.

### MetaTrader5 is now a platform-gated dependency

`MetaTrader5>=5.0.0` is gated on `sys_platform == "win32"`. Non-Windows
hosts (Linux CI runners, macOS development machines) can now install the
wheel cleanly — pip skips the MetaTrader5 wheel because none exists for
those platforms. A runtime guard in `mt5_mcp.connection` raises an
`ImportError` with an actionable message if someone tries to invoke the
tools on a non-Windows host.

### Also fixed

- TOON dependency URL corrected to the actual published tag
  (`v0.9.0-beta.1`). The previous `v0.9.0` tag does not exist on the
  upstream repo.
- `tabulate>=0.9` added to the `[test]` extra — required by
  `pandas.DataFrame.to_markdown` which the executor tests exercise.
- 18 latent lint errors fixed in `error_utils.py`, `executor.py`,
  `handlers.py`, `validators.py` (G201 logging style, DTZ003 deprecated
  `datetime.utcnow()`, S102/S110/SIM102 in `executor` / `validators`).
  These were pre-existing issues that the CI ruff version flagged.

### Test surface

- Total suite: **81 passed, 1 skipped** (intentional TOON-missing branch).
- New `tests/test_platform_guard.py`: 2 tests covering the platform
  guard on Windows (passes through) and non-Windows (raises).

### Recovery (for users already affected)

Anyone who hit the `ImportError: cannot import name 'FastMCP' from 'fastmcp'`
error on a previous install can recover with:

```powershell
pip uninstall -y fastmcp fastmcp-slim
pip install mt5-mcp
```

### v0.6.3.1 — TOON encoder deferred to v0.6.4

The v0.6.3 release was originally planned to ship the TOON encoder
behind an optional `[toon]` extra pointing at the upstream
`toon-format/toon-python` GitHub tarball. The first publish attempt
**failed at the PyPI upload step**:

```
400 Bad Request: Can't have direct dependency:
toon_format @ https://github.com/toon-format/toon-python/...
```

PyPI rejects direct-URL `Requires-Dist` references in sdist metadata
(only PyPI-hosted wheels are valid). The v0.6.3 wheel was rebuilt
**without** the `[toon]` extra; the TOON shape heuristic in
`mt5_mcp.toon_output.format_response` silently falls back to JSON
when the encoder isn't installed. All 18 TOON tests run via the
editable install with `toon_format` available locally — they will
run from a clean PyPI install once we vendor the encoder in v0.6.4.

---

## v0.6.2 – Server-decides TOON encoding (August 13, 2026)

### Removed `wire_format` from tool schemas

The `wire_format` parameter that v0.6.1 added to `mt5_query` and
`mt5_analyze` is gone. TOON encoding is now a server-side concern —
the LLM never has to think about it. The server runs a shape-detection
heuristic on every response:

1. **Tabular sub-tree** — when ``data`` is a uniform array of ≥5 dicts
   and encoding it as TOON saves ≥10 % tokens vs. compact JSON, the
   server replaces the array with a TOON string and adds a sibling
   ``"data_format": "toon"`` marker. The envelope stays JSON.
2. **Whole response** — when the response has no clean tabular
   sub-tree but encoding the whole thing as TOON still saves ≥10 %
   tokens, the server emits a single TOON document.
3. **Fallback** — otherwise the response is unchanged compact JSON.

The LLM's experience:

```json
{
  "operation": "copy_rates_from_pos",
  "success": true,
  "metadata": {"symbol": "BTCUSD", "timeframe": "H1", "count": 50},
  "data_format": "toon",
  "data": "data[50]{time,close,vol}:\n  1700000000,63000.0,0\n  ..."
}
```

vs. a `symbol_info` lookup that stays JSON:

```json
{
  "operation": "symbol_info",
  "success": true,
  "data": {"name": "BTCUSD", "bid": 63612.5, "ask": 63640.5, ...},
  "metadata": {"symbol": "BTCUSD"}
}
```

### Why

The `wire_format` parameter leaked transport encoding into the LLM's
decision loop, which it shouldn't have to think about. Different
models, different prompting, different behaviour — none of it good.
The server has all the information it needs (the response shape) to
pick the right encoding; the LLM just consumes.

### Test surface

- New `test_toon_output.py` suite: 18 tests covering the shape
  heuristic, `data_format: "toon"` marker, roundtrip property across
  every shape, end-to-end absence of `wire_format` in tool schemas,
  and a passthrough test for non-dict payloads.
- Total suite: **79 passed, 1 skipped** (the intentional TOON-missing
  branch).

---

## v0.6.1 – TOON Output Encoding (August 13, 2026)

### Token-efficient output for LLM agents

`mt5_query` and `mt5_analyze` now accept a `wire_format` parameter
(`"json"` | `"toon"` | `"auto"`, default `"json"`) that controls the
on-the-wire encoding. When `"toon"` (or `"auto"` with the savings
threshold met) is selected, the response is encoded as
[TOON](https://github.com/toon-format/toon) instead of compact JSON.

Measured against the actual MCP tool payloads (50-bar `copy_rates`,
20-row `mt5_analyze`, 30-row `mt5_execute`, etc.):

| Response shape | JSON tokens | TOON tokens | Saved |
|---|---:|---:|---:|
| `copy_rates` 50 bars (tabular) | 3,171 | 2,391 | **24.6 %** |
| `copy_rates` 200 bars (heavy tabular) | 12,585 | 9,405 | **25.3 %** |
| `mt5_analyze` 20 rows + indicators | 956 | 673 | **29.6 %** |
| `mt5_execute` 30 rows | 709 | 564 | **20.5 %** |
| **Total (representative)** | 17,656 | 13,295 | **24.7 %** |
| Byte savings (same set) | 47,825 B | 28,291 B | **40.8 %** |

Token counts use `tiktoken` with the `o200k_base` encoding (the GPT-5
tokenizer). Other providers tokenize differently; absolute counts are
tokenizer-specific, but the relative savings directionally hold for
cl100k_base and other BPE-style tokenizers.

Tiny responses (single `symbol_info` lookup, error envelopes) cost 1–3
extra tokens — TOON's `[N]` array header is wasted on objects with one
or two keys. `auto` mode handles this by falling back to JSON when TOON
would not save at least 10 %.

### New dependency

* Optional: `toon_format` (from `toon-format/toon-python`,
  pinned via git URL — the matching PyPI version is a stub). Install
  with `pip install "mt5-mcp[toon]"`.

### Tests

* 14 new tests in `tests/test_toon_output.py` covering: TOON/JSON
  switching, savings measurement, format selection (`auto` thresholds),
  missing-dependency fallback, end-to-end schema roundtrip via
  `fastmcp.Client`. Suite total: **75 passed**.

---

## v0.6.0 – FastMCP v3 Migration, Gradio Removed (August 13, 2026)

### Major Architecture Upgrade

The package was migrated from the Gradio-MCP shim to the
[FastMCP v3](https://gofastmcp.com) framework (a thin, production-grade
layer over the official `mcp` Python SDK). Gradio has been removed
entirely — no UI dashboard, no `gradio_server.py`, no Gradio dependencies.
The package is now FastMCP-only.

### Headline Changes

- **FastMCP v3 framework**: Pinned `fastmcp>=3.0,<4`. Tool registration
  uses the `@mcp.tool` decorator with standard Python type annotations,
  so FastMCP derives JSON schemas automatically. The previous
  v0.5.x string-encoded JSON payloads (`parameters: str`) are gone —
  `parameters` is now a real `dict[str, Any]` (or Pydantic model).
- **Three transports, one process**: stdio (Claude Desktop, VS Code),
  Streamable HTTP (`/mcp`), and SSE (`/sse`, legacy). The new
  `--transport all` flag runs stdio + HTTP + SSE concurrently in one
  process. `--transport http` is the production-friendly choice;
  `--asgi` exposes the ASGI app for mounting under Uvicorn/Gunicorn.
- **First-class middleware**: rate-limiting (per-IP sliding window) and
  request logging moved into FastMCP middleware (`middleware.py`),
  matching the framework's recommended pattern. Rate limit applies to
  HTTP/SSE only; stdio is single-process and skipped.
- **Tool signatures driven by Pydantic**: `mt5_query`, `mt5_analyze`,
  `mt5_execute` now take typed args (`dict[str, Any]`, `list[dict]`,
  `Optional[dict]`). No more manual JSON string parsing by callers.
- **No Gradio at all**: removed `gradio_server.py` and
  `gradio_ui.py`, deleted the `gradio_server` test, removed the
  `[ui]` extra, removed the `--with-dashboard` flag, removed all
  references to gradio in README/USAGE/CHANGELOG.

### New File Structure

```
src/mt5_mcp/
├── __init__.py            # Re-exports create_mcp_server
├── __main__.py            # CLI entry point (--transport, --asgi, etc.)
├── mcp_server.py          # FastMCP instance + tool registration
├── mcp_tools.py           # Tool functions (mt5_query, mt5_analyze, mt5_execute)
├── middleware.py          # RateLimitMiddleware + RequestLoggingMiddleware
├── connection.py          # Thread-safe MT5 connection
├── handlers.py            # Business logic (query + analysis)
├── executor.py            # Sandboxed Python execution
├── models.py              # Pydantic request/response schemas
├── errors.py              # MT5Error hierarchy
├── error_utils.py         # ErrorType enum + helpers
└── validators.py          # Symbol/operation/timeframe validators

tests/
├── conftest.py            # Cross-platform MT5 stub + shared fixtures
├── test_mcp_server.py     # FastMCP server + singleton + schema tests
├── test_mcp_client.py     # End-to-end tests via fastmcp.Client
├── test_middleware.py     # Rate limit + logging middleware unit tests
├── test_connection.py     # Connection / thread-safety
├── test_handlers.py       # Query + analysis handlers
├── test_executor.py       # Sandboxed code execution
├── test_error_handling.py # ErrorUtils
├── integration_test.py    # Smoke-test script (also runnable as pytest)
└── manual_test.py         # Manual smoke tests
```

### Dependencies Updated

- **Added**: `fastmcp>=3.0,<4`, `httpx`, `anyio`.
- **Removed**: `gradio` (and the `[ui]` extra), the experimental
  `gradio[mcp]` dependency.
- **Kept**: `MetaTrader5`, `pandas`, `pydantic`, `prophet`, `xgboost`,
  `scikit-learn`, `ta`, `matplotlib`, `numpy`, `uvicorn`, `starlette`.

### CLI

```bash
python -m mt5_mcp                                    # stdio (default)
python -m mt5_mcp --transport http --host 0.0.0.0    # HTTP on 8000
python -m mt5_mcp --transport sse                    # legacy SSE
python -m mt5_mcp --transport all --port 8000        # stdio + HTTP
python -m mt5_mcp --asgi                             # emit app:app for uvicorn
```

### New CI Pipeline (`.github/workflows/ci.yml`)

- **Lint job** on `ubuntu-latest` running `ruff check src tests`.
- **Test job** on `ubuntu-latest` (Python 3.10/3.11/3.12) — exercises the
  import graph, middleware, FastMCP server construction, and the
  in-process `fastmcp.Client`. MetaTrader5 is stubbed.
- **Test job** on `windows-latest` (Python 3.11/3.12) — same suite,
  excluding any test that requires a live MT5 terminal.

### Test Suite

- **61 tests** (was 0 in v0.5.2 — CI never ran them).
- Cross-platform: the conftest provides a comprehensive `MetaTrader5`
  stub so tests run on Linux too.

### Breaking Changes

1. **Package import path is now clean**:
   ```python
   from mt5_mcp import create_mcp_server, get_mcp_server
   ```
   The previous `from .server import main` (which imported the legacy
   `mcp.server.lowlevel.Server`) is gone.
2. **`parameters` is now a real JSON object** in tool schemas — no more
   `'{"timeframe":"H1","count":100}'` strings.
3. **`--with-dashboard` flag removed** — there is no dashboard. Use an
   external HTTP client (or `fastmcp.Client`) for monitoring.
4. **`gradio_server.py` is gone**. If you had a deployment that imported
   `mt5_mcp.gradio_server`, it will fail. Migrate to the FastMCP HTTP
   transport.

### Migration Guide

- **Claude Desktop** (`stdio`): no changes; works exactly as before.
- **HTTP clients**: update URL from
  `http://localhost:7860/gradio_api/mcp/` to
  `http://localhost:8000/mcp`.
- **Python embedders**: `from mt5_mcp import create_mcp_server` (the
  new factory) replaces `from mt5_mcp.server import app`.

### Performance

- FastMCP routing adds <1ms per request.
- The MT5 native library remains the bottleneck.
- HTTP transport via Uvicorn handles thousands of req/sec on a single
  worker.

---

## v0.5.2 – Fixed Gradio MCP Tool Exposure (December 2, 2025)

### Critical Bug Fix
- **Gradio MCP server now properly exposes only 3 tools** (`mt5_query`, `mt5_analyze`, `mt5_execute`) instead of all internal helper functions
- Added `mcp_functions` parameter to explicitly control which functions are exposed as MCP tools
- Previously, Gradio was auto-exposing internal UI helper functions (`get_server_status`, `update_history`, `update_positions`, `_lambda_`, etc.) as MCP tools, cluttering the tool list

### What Changed
- **Before**: 9+ tools exposed (3 actual + 6+ internal UI functions)
- **After**: Exactly 3 tools exposed (mt5_query, mt5_analyze, mt5_execute)
- **Impact**: Clean MCP API surface, no confusion about which tools to use

## v0.5.1 – Production-Ready Error Handling (December 2, 2025)

### Comprehensive Error Handling
- **New Error Utilities Module** (`error_utils.py`):
  - Standardized error types (12 categories: JSONParseError, ValidationError, TypeError, ValueError, EnumError, MissingFieldError, MT5ConnectionError, MT5OperationError, CalculationError, TimeoutError, RuntimeError, UnknownError)
  - Safe JSON parsing with detailed error messages and position tracking
  - Safe enum conversion with valid values listing in error responses
  - Field validation helpers for required fields and type checking
  - Standardized error response format with timestamp and operation context
- **Tool Function Protection**:
  - All MCP tools (mt5_query, mt5_analyze, mt5_execute) wrapped with comprehensive error handling
  - Input validation: command length limits (50KB), dangerous operation detection, type checking
  - Rate limit error handling with graceful degradation
  - MT5 connection validation before all operations
  - Catch-all exception handlers to prevent server crashes
- **Handler-Level Protection**:
  - Request object validation in `handle_mt5_query` and `handle_mt5_analysis`
  - Parameter type validation before MT5 operations
  - Custom error re-raising with wrapped exceptions for better debugging
- **Connection Resilience**:
  - Retry logic for MT5 initialization (3 attempts with 1-second delay between retries)
  - Detailed error logging for connection failures
  - Namespace building error handling with fallback messages
- **Executor Safety**:
  - Command and namespace validation before execution
  - Code preparation error handling with syntax validation
  - Result formatting error handling with fallback to type information
- **Security Enhancements**:
  - Dangerous operation blocking: eval(), exec(), subprocess, mt5.initialize(), mt5.shutdown()
  - Command length limits to prevent abuse (50KB maximum)
  - SQL injection attempt detection and handling
- **Test Coverage**: 30+ test cases covering all error scenarios with 100% pass rate
  - Malformed JSON inputs handled gracefully
  - Invalid enum values return helpful error messages
  - Type mismatches caught and reported
  - Missing required fields validated
  - MT5 connection failures retry and report

### What Changed
- **Before**: Server crashed on malformed client input (invalid JSON, wrong types, missing fields)
- **After**: All errors handled gracefully with standardized JSON error responses
- **Impact**: Server is now production-ready and stable under malformed/malicious inputs

## v0.5.0 – Multi-Transport MCP Server

- Added a Gradio v6-powered MCP server that exposes the same MT5 tools over streamable HTTP/SSE (`/gradio_api/mcp/`) with optional hosting on Hugging Face Spaces or Windows VPS targets.
- Introduced a dual-transport launcher with `--transport stdio|http|both`, customizable host/port/rate-limit flags, and stdio-only default behavior for backward compatibility.
- Implemented per-IP HTTP rate limiting (10 req/min by default) plus shared MT5 connection locking to keep the terminal stable under concurrent requests.
- Documented new workflows in README/USAGE, including MCP client snippets, deployment recipes, and migration guidance from v0.4.x.
- Cleaned up planning artifacts and unused files in preparation for publishing to `main` and PyPI.

## v0.4.0 – Forecasting & ML Signals

- Added Prophet forecasting support inside `mt5_analyze`, including `periods`, `freq`, `seasonality_mode`, `growth`, `plot`, and `plot_components` controls.
- Introduced optional XGBoost-based trading signals (`enable_ml_prediction`, `ml_lookback`, and detailed signal metadata with confidence scores, feature provenance, and training sample counts).
- Extended namespace dependencies (`prophet`, `xgboost`, `scikit-learn`) and refreshed quick-start flows for daily and hourly forecasting scenarios.
- Enhanced forecast responses with structured summaries (trend direction, percentage change, uncertainty ranges) plus automatically saved chart paths for downstream visualization.

## v0.3.0 – Structured Input Tools

- Delivered the `mt5_query` tool for JSON-based MT5 operations with strict validation (symbol existence, timeframe parsing, parameter typing) and LLM-friendly corrective suggestions.
- Released `mt5_analyze`, enabling one-shot pipelines that combine MT5 data retrieval, 80+ `ta` indicators, chart generation (single or multi-panel), and optional Markdown/JSON/chart-only outputs.
- Added systematic error messaging, function signature caching, and parameter normalization to reduce retries from AI assistants and improve throughput.

## v0.2.1 – LLM Compatibility Fixes

- Reworked tool descriptions with highly visible guardrails that explain the pre-initialized MT5 session and the requirement to assign results before returning.
- Updated every bundled example to fetch data, convert to pandas explicitly, and store outputs in `result` to avoid silent failures.
- Added runtime inspection that blocks `mt5.initialize()` / `mt5.shutdown()` (and MetaTrader5 equivalents) before execution and returns actionable guidance.
- Raised expected success rates from ~37% to 87%+ across test models by combining documentation fixes, validation, and clearer error messaging.

## v0.1.0 – Initial Release

- Launched the `execute_mt5` tool with a read-only MetaTrader 5 bridge, safe namespace construction, and automatic formatting of dicts, tables, and named tuples.
- Implemented connection management, optional file logging, and comprehensive multi-line execution support for AI coding assistants.
