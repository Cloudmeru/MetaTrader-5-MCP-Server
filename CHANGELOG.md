# CHANGELOG

All notable changes will be tracked here. Dates reflect when the feature set landed in the repository; see git history for exact commits.

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
