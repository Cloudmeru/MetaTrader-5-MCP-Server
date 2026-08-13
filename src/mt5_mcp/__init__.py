"""
MetaTrader 5 MCP Server — read-only MCP bridge for a running MT5 terminal.

Built on FastMCP v3 (https://gofastmcp.com). See ``mt5_mcp.mcp_server``
for the server factory and ``mt5_mcp.mcp_tools`` for the tool definitions.
"""

from .mcp_server import create_mcp_server, get_mcp_server

__version__ = "0.6.3"

__all__ = [
    "__version__",
    "create_mcp_server",
    "get_mcp_server",
]
