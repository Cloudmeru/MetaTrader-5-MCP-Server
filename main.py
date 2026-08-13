"""
Top-level ASGI entry point for production deployments.

Re-exports the FastMCP ASGI application from :mod:`mt5_mcp.__main__` so
production tooling (``uvicorn main:app``, ``gunicorn main:app``, etc.)
can find it without needing to know the package layout.

Development and CLI workflows should still use ``python -m mt5_mcp``
directly — see :mod:`mt5_mcp.__main__` for all CLI flags.
"""

from mt5_mcp.__main__ import app

__all__ = ["app"]
