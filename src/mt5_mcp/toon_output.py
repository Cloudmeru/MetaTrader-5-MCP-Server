"""
TOON output encoding for the MT5 MCP server.

TOON ("Token-Oriented Object Notation") is a token-efficient serialization
format designed for LLM contexts. See https://github.com/toon-format/spec and
https://github.com/toon-format/toon-python for the canonical specification
and reference Python implementation.

Why TOON for this server?
=========================

We return *lots* of tabular data — MT5 rate bars, indicator values across
a window, transaction history, open positions. The TOON spec's "tabular
form" is purpose-built for arrays of uniform objects: the field list is
declared once on a header line and rows are delimiter-separated cells.
This is exactly the shape ``copy_rates_*`` produces.

But the shape heuristic matters. A single 80-key ``symbol_info`` response
or a 4-key error envelope costs more in TOON's array header than it
saves. So this module does **shape detection** rather than blanket TOON
encoding:

* If the response contains a uniform array of ≥5 dicts at the ``data``
  field AND encoding just that array as TOON saves ≥10 % of tokens,
  replace the array with a TOON string and tag the field with
  ``data_format: "toon"``. The envelope stays JSON so callers can
  ``json.loads`` the outer object without a TOON decoder.
* If the whole response encodes with ≥10 % savings, emit the entire
  response as TOON (a single document).
* Otherwise emit compact JSON as before.

The LLM never has to think about which encoding to ask for. There is no
``output_format`` parameter on the tools — the server picks, the LLM
consumes.

Measured against the actual MCP tool responses (see
``tests/test_toon_output.py``):

* ``copy_rates`` 50 bars → TOON sub-tree, **24 % fewer tokens**
* ``copy_rates`` 200 bars → TOON sub-tree, **25 % fewer tokens**
* ``symbol_info`` (single 80-key dict) → JSON (TOON would lose tokens)
* ``account_info`` (single small dict) → JSON
* Error envelopes → JSON (TOON overhead would dominate)
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Soft-import the official TOON encoder. The dependency is optional — when
# missing we degrade gracefully to plain JSON.
try:
    import toon_format  # type: ignore[import-not-found]

    _HAS_TOON = True
except ImportError:  # pragma: no cover - exercised via the test below
    toon_format = None  # type: ignore[assignment]
    _HAS_TOON = False


def toon_available() -> bool:
    """Return ``True`` iff the ``[toon]`` extra is installed."""
    return _HAS_TOON


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Minimum array length for the shape heuristic to consider applying TOON.
# Below this, the array-header overhead dominates the savings.
MIN_TABULAR_ROWS = 5

# Minimum token-savings percentage (vs. compact JSON) to apply TOON at all.
# This is a conservative floor; the heuristic measures both per-candidate
# sub-tree savings AND whole-response savings, and applies the smaller
# path only when each exceeds this threshold.
MIN_TOKEN_SAVINGS_PCT = 10.0


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def _approximate_tokens(s: str) -> int:
    """Quick token estimate.

    Real LLM tokenizers (cl100k_base, o200k_base) consistently tokenize
    English text at 3.5–4.5 characters per token for short strings.
    TOON output is whitespace-and-punctuation heavy, so 4 chars/token
    is a conservative upper bound; the heuristic slightly over-counts
    (predicts a few more tokens than tiktoken would) which biases the
    reported savings toward smaller numbers — i.e. we under-report
    savings rather than over-report them.
    """
    return max(1, len(s) // 4)


def _real_token_count(s: str, encoding: Any = None) -> int:
    """Authoritative token count via tiktoken, if available.

    Falls back to :func:`_approximate_tokens` when tiktoken isn't
    installed.
    """
    if encoding is None:
        try:
            import tiktoken

            encoding = tiktoken.get_encoding("o200k_base")
        except ImportError:
            return _approximate_tokens(s)
    return len(encoding.encode(s))


# ---------------------------------------------------------------------------
# Savings measurement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SavingsReport:
    """Measured byte/token delta between JSON and TOON output."""

    json_bytes: int
    toon_bytes: int
    json_tokens: int
    toon_tokens: int

    @property
    def byte_savings_pct(self) -> float:
        if self.json_bytes == 0:
            return 0.0
        return (1.0 - self.toon_bytes / self.json_bytes) * 100.0

    @property
    def token_savings_pct(self) -> float:
        if self.json_tokens == 0:
            return 0.0
        return (1.0 - self.toon_tokens / self.json_tokens) * 100.0

    def to_meta(self) -> dict[str, Any]:
        """Compact envelope suitable for embedding in a response body."""
        return {
            "json_bytes": self.json_bytes,
            "toon_bytes": self.toon_bytes,
            "json_tokens": self.json_tokens,
            "toon_tokens": self.toon_tokens,
            "byte_savings_pct": round(self.byte_savings_pct, 1),
            "token_savings_pct": round(self.token_savings_pct, 1),
        }


def measure_savings(data: Any) -> SavingsReport:
    """Render ``data`` as both JSON and TOON and report the size delta.

    Uses tiktoken for an authoritative token count when it's available;
    otherwise falls back to the ``len // 4`` heuristic.
    """
    json_str = json.dumps(data, separators=(",", ":"))
    toon_str = toon_format.encode(data) if _HAS_TOON else json_str

    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        json_tokens = len(enc.encode(json_str))
        toon_tokens = len(enc.encode(toon_str))
    except ImportError:
        json_tokens = _approximate_tokens(json_str)
        toon_tokens = _approximate_tokens(toon_str)

    return SavingsReport(
        json_bytes=len(json_str.encode("utf-8")),
        toon_bytes=len(toon_str.encode("utf-8")),
        json_tokens=json_tokens,
        toon_tokens=toon_tokens,
    )


# ---------------------------------------------------------------------------
# Shape detection — find the tabular candidate
# ---------------------------------------------------------------------------


def _is_uniform_dict_array(value: Any) -> bool:
    """Return ``True`` iff ``value`` is a non-empty list of dicts that
    all share the same key set (order-independent)."""
    if not isinstance(value, list) or len(value) < 2:
        return False
    if not all(isinstance(item, dict) and item for item in value):
        return False
    first_keys = set(value[0].keys())
    return all(set(item.keys()) == first_keys for item in value[1:])


def _find_tabular_candidate(response: dict[str, Any]) -> tuple[str, list[dict]] | None:
    """Locate the best TOON candidate inside ``response``.

    Current policy: only the top-level ``data`` field is considered.
    Nested candidates (e.g. ``data.rows`` on ``mt5_analyze``) are
    intentionally ignored in v1 — the marker path is cleaner when
    only one field is potentially TOON-encoded, and nested cases
    fall through to the whole-response measurement instead.

    Returns ``(field_name, rows)`` if the ``data`` field is a uniform
    array of dicts of at least :data:`MIN_TABULAR_ROWS`, else ``None``.
    """
    data = response.get("data") if isinstance(response, dict) else None
    if not _is_uniform_dict_array(data):
        return None
    if len(data) < MIN_TABULAR_ROWS:
        return None
    return "data", data


# ---------------------------------------------------------------------------
# Response formatter
# ---------------------------------------------------------------------------


def _embedded_toon_tokens(rows: list[dict]) -> int:
    """Token count of the TOON document as it would appear *embedded* as a
    JSON-quoted string. We round-trip through JSON encoding because the
    cost we care about is the bytes/tokens the LLM actually sees on the
    wire, including the surrounding quotes and JSON escapes.
    """
    if not _HAS_TOON:
        return 0
    toon_doc = toon_format.encode(rows)
    embedded = json.dumps(toon_doc, separators=(",", ":"))  # adds quotes + escapes
    return _real_token_count(embedded)


def _format_response_with_marker(
    response: dict[str, Any], field_name: str, toon_text: str
) -> dict[str, Any]:
    """Return a copy of ``response`` where ``field_name`` is replaced by
    a TOON string and a sibling ``data_format: "toon"`` marker is added."""
    out = copy.copy(response)
    out[field_name] = toon_text
    out["data_format"] = "toon"
    return out


def format_response(data: Any) -> dict[str, Any] | str:
    """Render a tool response using the best encoding for its shape.

    Decision tree:

    1. If ``data`` is not a dict (e.g. a plain string from
       ``mt5_execute``), pass it through unchanged.
    2. If TOON is not installed, return ``data`` unchanged.
    3. If ``data["data"]`` is a uniform array of ≥5 dicts AND
       encoding just that array as an embedded TOON document saves
       ≥10 % of tokens vs. encoding the whole array as compact JSON →
       return a copy of ``data`` with the array replaced by a TOON
       string and a sibling ``data_format: "toon"`` marker.
    4. Else, if encoding the whole response as TOON saves ≥10 % of
       tokens → return the TOON string directly (a single document).
    5. Else, return ``data`` unchanged (compact JSON).

    The LLM sees:

    * tabular case: a normal JSON envelope (``operation``, ``success``,
      ``metadata``), a ``"data_format": "toon"`` marker, and a ``data``
      field that is a TOON document as a string.
    * whole-response case: a TOON document as a string.
    * JSON case: the unchanged dict (which is JSON-serialisable).
    """
    # Step 1: passthrough for non-dict payloads (e.g. mt5_execute text).
    if not isinstance(data, dict):
        return data

    # Step 2: no TOON library → always JSON.
    if not _HAS_TOON:
        return data

    # Step 3: tabular sub-tree candidate.
    candidate = _find_tabular_candidate(data)
    if candidate is not None:
        field_name, rows = candidate
        toon_doc = toon_format.encode(rows)

        # Measure: how many tokens does the embedded TOON body cost
        # (as a JSON-quoted string) vs. the raw JSON array?
        json_array_str = json.dumps(rows, separators=(",", ":"))
        json_array_tokens = _real_token_count(json_array_str)
        toon_embedded_tokens = _embedded_toon_tokens(rows)

        if toon_embedded_tokens > 0 and (
            (json_array_tokens - toon_embedded_tokens) / json_array_tokens
            * 100.0
        ) >= MIN_TOKEN_SAVINGS_PCT:
            return _format_response_with_marker(data, field_name, toon_doc)
        # else fall through — the savings aren't enough to justify the
        # extra TOON marker overhead on this response.

    # Step 4: whole-response TOON.
    whole_report = measure_savings(data)
    if whole_report.token_savings_pct >= MIN_TOKEN_SAVINGS_PCT:
        return toon_format.encode(data)

    # Step 5: JSON.
    return data


__all__ = [
    "SavingsReport",
    "format_response",
    "measure_savings",
    "toon_available",
]
