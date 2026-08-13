"""
Command-line entry point for the MetaTrader 5 MCP server.

The CLI is a thin shim around :func:`mt5_mcp.mcp_server.create_mcp_server`.
The actual transport lifecycle is owned by FastMCP itself
(``mcp.run(transport=...)``), so this module only handles argument
parsing, logging setup, and the ASGI deployment option.

Production ASGI usage::

    uvicorn mt5_mcp.__main__:app
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any, NoReturn

logger = logging.getLogger(__name__)


def build_asgi_app(path: str = "/mcp", rate_limit_per_minute: int = 10):
    """Build the ASGI 3 application for the server.

    Exposed at module level so production deployments can use the standard
    ``uvicorn mt5_mcp.__main__:app`` form without going through the CLI.
    """
    from .mcp_server import create_mcp_server

    server = create_mcp_server(rate_limit_per_minute=rate_limit_per_minute)
    asgi_app = server.http_app(path=path)
    if isinstance(asgi_app, tuple):
        # ``http_app`` returns ``(StarletteApp, lifespan)`` in FastMCP v3.
        # Return a Starlette ``Lifespan`` wrapper that drives both. Uvicorn
        # with ``--lifespan on`` (the default for Starlette apps) will
        # enter the lifespan on startup and exit it on shutdown, which is
        # exactly what FastMCP needs for its own startup/shutdown hooks.
        return asgi_app
    return asgi_app


# Module-level ASGI app handle — Uvicorn / Gunicorn / Hypercorn can mount
# ``mt5_mcp.__main__:app`` directly. The factory is called lazily so
# importing this module is cheap and side-effect free.
app: Any = build_asgi_app()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="mt5-mcp",
        description=(
            "MetaTrader 5 MCP Server — read-only bridge between a running MT5 "
            "terminal and any MCP-compatible client (Claude Desktop, VS Code, "
            "remote HTTP clients)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local stdio (default — used by Claude Desktop)
  python -m mt5_mcp

  # HTTP transport for web / remote clients
  python -m mt5_mcp --transport http --host 0.0.0.0 --port 8000

  # Run both stdio and HTTP in one process (stdio on stdin/stdout,
  # HTTP on a separate port)
  python -m mt5_mcp --transport all --port 8000

  # ASGI app for production (mount behind Uvicorn / Hypercorn / Gunicorn)
  python -m mt5_mcp --asgi --path /mcp

MCP endpoints:
  stdio       stdin / stdout
  http        http://<host>:<port>/mcp  (Streamable HTTP)
  sse         http://<host>:<port>/sse   (legacy)
  health      http://<host>:<port>/health (built-in)
        """,
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "sse", "all"),
        default="stdio",
        help="Transport to expose (default: stdio). 'all' = stdio + http.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP/SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP/SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="URL path for the HTTP transport (default: /mcp)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="HTTP/SSE per-IP requests per minute (default: 10, 0=unlimited)",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Log file path (default: stderr only)",
    )
    parser.add_argument(
        "--asgi",
        action="store_true",
        help=(
            "Print the ASGI application object as a Python literal "
            "(e.g. 'app:app') and exit. Used by WSGI/ASGI servers such as "
            "uvicorn, gunicorn, or hypercorn to mount this server."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging(level: str, log_file: str | None) -> None:
    """Configure root logging once. Re-config is a no-op on repeated calls."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    # FastMCP has its own logger; surface its warnings through our root.
    logging.getLogger("fastmcp").setLevel(getattr(logging, level))


# ---------------------------------------------------------------------------
# Transport runners
# ---------------------------------------------------------------------------


def run_stdio(server) -> NoReturn:
    """Run the server on stdio. Blocks until the parent process closes stdin."""
    server.run(transport="stdio")


def run_http(
    server,
    *,
    host: str,
    port: int,
    path: str,
) -> NoReturn:
    """Run the server with the HTTP (streamable) transport."""
    server.run(transport="http", host=host, port=port, path=path)


def run_sse(
    server,
    *,
    host: str,
    port: int,
    path: str,
) -> NoReturn:
    """Run the server with the SSE (legacy) transport."""
    server.run(transport="sse", host=host, port=port, path=path)


def run_all(
    server,
    *,
    host: str,
    port: int,
    path: str,
) -> NoReturn:
    """Run stdio + HTTP concurrently.

    stdio runs on the asyncio loop the parent gave us. FastMCP exposes the
    HTTP transport via ``mcp.http_app()``; we run that under ``uvicorn`` in
    a background asyncio task and let stdio share the same loop.
    """
    import uvicorn
    from fastmcp import FastMCP

    assert isinstance(server, FastMCP)
    app = server.http_app(path=path)
    # ``http_app`` returns a tuple of (app, lifespan) in FastMCP v3.
    # The lifespan is wired through uvicorn's lifespan mechanism below,
    # so we only need the ASGI 3 callable here.
    if isinstance(app, tuple):
        asgi_app, _lifespan = app
    else:
        asgi_app = app

    config = uvicorn.Config(
        asgi_app,
        host=host,
        port=port,
        log_level="info",
        lifespan="on",
        # We don't want uvicorn's signal handlers to fight with stdio's.
        access_log=False,
    )
    http_server = uvicorn.Server(config)

    async def _serve() -> None:
        # ``lifespan`` is a context manager that uvicorn enters/exits for us,
        # so we don't manually drive it here.
        await http_server.serve()

    async def _main() -> None:
        http_task = asyncio.create_task(_serve(), name="mcp-http")
        try:
            # stdio is blocking in the FastMCP sync wrapper; run it in a
            # worker thread so the event loop can drive uvicorn.
            await asyncio.to_thread(server.run, "stdio")
        finally:
            http_server.should_exit = True
            await http_task

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("shutdown: keyboard interrupt")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level, args.log_file)

    # Lazy imports keep the package importable on lean environments.
    from .mcp_server import create_mcp_server

    logger.info(
        "mt5-mcp starting (transport=%s, host=%s, port=%d, rate_limit=%d/min)",
        args.transport,
        args.host,
        args.port,
        args.rate_limit,
    )

    if args.asgi:
        # Emit a hint that ``app`` is already wired up; nothing else to do.
        sys.stdout.write(
            "ASGI app is exposed at mt5_mcp.__main__:app\n"
            "Run: uvicorn mt5_mcp.__main__:app --host 0.0.0.0 --port 8000\n"
        )
        return 0

    server = create_mcp_server(rate_limit_per_minute=args.rate_limit)

    if args.transport == "stdio":
        run_stdio(server)
    elif args.transport == "http":
        run_http(server, host=args.host, port=args.port, path=args.path)
    elif args.transport == "sse":
        run_sse(server, host=args.host, port=args.port, path=args.path)
    elif args.transport == "all":
        run_all(server, host=args.host, port=args.port, path=args.path)
    else:  # pragma: no cover — argparse already constrains this
        raise SystemExit(f"unknown transport: {args.transport}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
