"""
Unit tests for the TOON output encoding layer.

These tests cover the server-side shape-detection heuristic in
:mod:`mt5_mcp.toon_output`. The decision tree is:

* If ``data`` is not a dict (e.g. ``mt5_execute`` text), pass through.
* If TOON isn't installed, always return the dict unchanged.
* If ``data["data"]`` is a uniform array of ≥5 dicts and encoding just
  that array as an embedded TOON document saves ≥10 % tokens vs.
  encoding it as JSON → replace the array with a TOON string and add
  a sibling ``data_format: "toon"`` marker.
* Else, if encoding the whole response as TOON saves ≥10 % tokens →
  return a single TOON string.
* Else → return the dict unchanged (compact JSON).

The conftest stub provides MetaTrader5 constants; this file just imports
the module under test.
"""

from __future__ import annotations

import pytest

from mt5_mcp.toon_output import (
    SavingsReport,
    format_response,
    measure_savings,
    toon_available,
)

# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------


def test_toon_available_returns_bool():
    """``toon_available()`` is callable and returns a bool — it should
    not raise regardless of whether the [toon] extra is installed."""
    assert isinstance(toon_available(), bool)


# ---------------------------------------------------------------------------
# Passthrough behaviour
# ---------------------------------------------------------------------------


def test_format_response_passthrough_non_dict():
    """Strings (e.g. ``mt5_execute`` output) pass through unchanged.

    No JSON parsing, no TOON encoding — the heuristic never touches them.
    """
    assert format_response("hello\nworld") == "hello\nworld"
    assert format_response("") == ""
    assert format_response(42) == 42
    assert format_response(None) is None
    assert format_response([1, 2, 3]) == [1, 2, 3]


def test_format_response_passthrough_when_toon_missing():
    """When TOON isn't installed, every dict returns unchanged."""
    if toon_available():
        pytest.skip("toon_format is installed — covered by a different test")
    data = {"a": 1, "data": [{"x": 1}, {"x": 2}]}
    assert format_response(data) == data


# ---------------------------------------------------------------------------
# Tabular sub-tree case (the headline use case)
# ---------------------------------------------------------------------------


def _tabular_response(n: int) -> dict:
    """Build a response shaped like a real ``copy_rates`` payload."""
    return {
        "operation": "copy_rates_from_pos",
        "success": True,
        "data": [
            {"time": 1700000000 + i * 3600, "close": 63000.0 + i, "vol": i * 100}
            for i in range(n)
        ],
        "metadata": {"symbol": "BTCUSD", "timeframe": "H1", "count": n},
    }


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_tabular_response_gets_toon_marker():
    """A 50-row uniform array response triggers the ``data_format: \"toon\"``
    marker and embeds the data as a TOON string."""
    response = _tabular_response(50)
    rendered = format_response(response)

    assert isinstance(rendered, dict), "should still be a dict (envelope is JSON)"
    assert rendered["data_format"] == "toon"
    assert isinstance(rendered["data"], str), "data should be a TOON string"
    assert rendered["operation"] == "copy_rates_from_pos"  # envelope preserved
    assert rendered["success"] is True  # envelope preserved
    assert rendered["metadata"] == response["metadata"]  # envelope preserved

    # The TOON body should round-trip back to the original rows.
    import toon_format

    decoded_body = toon_format.decode(rendered["data"])
    assert decoded_body == response["data"]

    # Stripping the marker (which is envelope metadata, not data) leaves
    # a dict whose ``data`` field is the TOON string. Decode that string
    # back to the original rows, then compare against the source response.
    import toon_format

    actual_minus_marker = rendered.copy()
    actual_minus_marker.pop("data_format")
    actual_minus_marker["data"] = toon_format.decode(actual_minus_marker["data"])
    assert actual_minus_marker == response


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_small_array_does_not_get_toon_marker():
    """Arrays below the threshold (5 rows) stay JSON — TOON's array
    header overhead would dominate the savings on tiny payloads."""
    response = _tabular_response(4)
    rendered = format_response(response)
    assert rendered == response  # unchanged, no marker
    assert "data_format" not in rendered


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_single_dict_response_stays_json():
    """``symbol_info`` returns a single dict (no tabular array). TOON would
    cost more in array-header overhead than it saves — must stay JSON."""
    response = {
        "operation": "symbol_info",
        "success": True,
        "data": {"name": "BTCUSD", "bid": 63612.5, "ask": 63640.5, "spread": 28},
        "metadata": {"symbol": "BTCUSD"},
    }
    rendered = format_response(response)
    assert rendered == response
    assert "data_format" not in rendered


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_heterogeneous_array_stays_json():
    """``symbols_get`` may return rows with different field sets across
    brokers. ``_is_uniform_dict_array`` rejects these and we stay JSON."""
    response = {
        "operation": "symbols_get",
        "success": True,
        "data": [
            {"name": "BTCUSD", "bid": 63612.5},
            {"name": "EURUSD", "bid": 1.085, "digits": 5},  # extra key
        ],
        "metadata": {},
    }
    rendered = format_response(response)
    # Heterogeneous arrays are NOT a uniform dict array, so no marker.
    # (The whole-response TOON check still runs; if it fails, JSON wins.)
    assert "data_format" not in rendered or rendered.get("data_format") != "toon"
    # Specifically: if TOON whole-response fires, that's the fallback, and
    # the original envelope is gone (replaced by a TOON doc). We just
    # check the roundtrip property — either path is acceptable.
    if isinstance(rendered, dict):
        # JSON path: data is a list of dicts.
        assert isinstance(rendered["data"], list)
    else:
        # Whole-response TOON path: a string. Just verify it parses.
        import toon_format

        toon_format.decode(rendered)  # raises on invalid


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_error_envelope_stays_json():
    """Error envelopes (4–5 keys, no tabular array) stay JSON — TOON
    overhead would dominate."""
    error = {
        "success": False,
        "operation": "mt5_query",
        "error": "MT5SymbolNotFoundError: Symbol 'XYZ' not found in MT5.",
        "error_type": "SymbolNotFoundError",
        "details": {"exception_type": "MT5SymbolNotFoundError"},
        "metadata": {"symbol": "XYZ"},
    }
    rendered = format_response(error)
    # Should be unchanged — too small for TOON to help.
    assert rendered == error
    assert "data_format" not in rendered


# ---------------------------------------------------------------------------
# Whole-response TOON fallback
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_whole_response_toon_when_no_tabular_subtree_but_still_worth_it():
    """When there's no clean tabular sub-tree but the whole response is
    uniform enough, the heuristic falls back to encoding the whole
    response as TOON. We construct a synthetic response that satisfies
    this path (no ``data`` array, but other keys with repetition savings).
    """
    # A response with many short uniform-keyed values. JSON wastes
    # characters on repeated keys; TOON's full-document form wins.
    response = {
        "operation": "config_dump",
        "success": True,
        "config": {
            f"setting_{i:03d}": f"value_{i:03d}" for i in range(50)
        },
    }
    rendered = format_response(response)
    # Either it goes whole-response TOON, or stays JSON if the heuristic
    # decides the savings aren't enough. Either is acceptable — we just
    # assert roundtrip property.
    if isinstance(rendered, dict):
        # JSON path.
        assert rendered == response
    else:
        # TOON path: must round-trip.
        import toon_format

        decoded = toon_format.decode(rendered)
        assert decoded == response


# ---------------------------------------------------------------------------
# measure_savings — direct measurement utility
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_measure_savings_returns_savings_report():
    data = {"a": 1, "b": [1, 2, 3]}
    report = measure_savings(data)
    assert isinstance(report, SavingsReport)
    assert report.json_bytes > 0
    assert report.toon_bytes > 0
    assert report.json_tokens > 0
    assert report.toon_tokens > 0
    meta = report.to_meta()
    assert set(meta.keys()) == {
        "json_bytes",
        "toon_bytes",
        "json_tokens",
        "toon_tokens",
        "byte_savings_pct",
        "token_savings_pct",
    }


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
def test_measure_savings_tabular_data_saves_tokens():
    """Documented baseline: a 50-bar tabular payload saves meaningful
    tokens when encoded as TOON vs. compact JSON. Synthetic test data
    is deterministic but the precise percentage drifts with the
    underlying tokenizer — we assert ≥15% to leave headroom for
    tokenizer changes while still proving the heuristic threshold (10%)
    is met with comfortable margin.
    """
    response = _tabular_response(50)
    report = measure_savings(response)
    assert report.token_savings_pct >= 15.0, (
        f"expected ≥15% token savings on 50-row tabular, got {report.token_savings_pct:.1f}%"
    )


# ---------------------------------------------------------------------------
# Roundtrip property test — every shape decodes back to itself
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not toon_available(), reason="toon_format not installed")
@pytest.mark.parametrize(
    "label,response",
    [
        ("tabular_50_rows", _tabular_response(50)),
        ("tabular_5_rows_min", _tabular_response(5)),
        ("empty_data", {"operation": "x", "success": True, "data": [], "metadata": {}}),
        (
            "scalar_data",
            {
                "operation": "x",
                "success": True,
                "data": {"value": 42},
                "metadata": {},
            },
        ),
        (
            "error",
            {
                "success": False,
                "operation": "x",
                "error": "boom",
                "error_type": "X",
                "details": {},
                "metadata": {},
            },
        ),
    ],
)
def test_roundtrip_preserves_meaning(label, response):
    """For every shape the tools can produce, the data the LLM receives
    must carry the same information — whether it came back as JSON or
    TOON or a hybrid envelope."""
    import toon_format

    rendered = format_response(response)

    if isinstance(rendered, dict) and rendered.get("data_format") == "toon":
        # Hybrid envelope: decode the TOON body and reassemble.
        decoded_body = toon_format.decode(rendered["data"])
        reassembled = rendered.copy()
        reassembled["data"] = decoded_body
        # Remove the marker before comparison (it's metadata, not data).
        reassembled.pop("data_format")
        assert reassembled == response, f"{label}: hybrid roundtrip failed"
    elif isinstance(rendered, str):
        # Whole-response TOON.
        decoded = toon_format.decode(rendered)
        assert decoded == response, f"{label}: whole-response TOON roundtrip failed"
    else:
        # JSON path: unchanged.
        assert rendered == response, f"{label}: JSON path roundtrip failed"


# ---------------------------------------------------------------------------
# Tools never expose wire_format / output_format (encoding decision is server-side)
# ---------------------------------------------------------------------------


def test_no_wire_format_or_output_format_in_tool_schemas():
    """None of the three tools expose a wire-encoding knob. The server
    picks automatically; the LLM just consumes."""
    from fastmcp import Client

    from mt5_mcp.mcp_server import create_mcp_server

    server = create_mcp_server(rate_limit_per_minute=0)
    client = Client(server)

    async def _list():
        async with client:
            return await client.list_tools()

    import asyncio

    tools = asyncio.run(_list())
    for tool in tools:
        props = tool.inputSchema.get("properties", {})
        # The new heuristic shouldn't be exposed; ``mt5_analyze`` keeps its
        # existing ``output_format`` parameter for report-shape selection
        # (markdown/json/chart_only), which is unrelated.
        assert "wire_format" not in props, (
            f"{tool.name} unexpectedly exposes wire_format: {list(props)}"
        )


# ---------------------------------------------------------------------------
# LLM-side guidance
# ---------------------------------------------------------------------------


def test_mcp_query_docstring_does_not_mention_wire_format():
    """The docstring should not promise a wire-encoding knob."""
    import inspect

    from mt5_mcp import mcp_tools

    src = inspect.getsource(mcp_tools.mt5_query)
    assert "wire_format" not in src


def test_mcp_analyze_docstring_does_not_mention_wire_format():
    import inspect

    from mt5_mcp import mcp_tools

    src = inspect.getsource(mcp_tools.mt5_analyze)
    assert "wire_format" not in src
