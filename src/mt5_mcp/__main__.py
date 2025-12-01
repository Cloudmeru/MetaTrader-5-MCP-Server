"""
Entry point for running the MT5 MCP server as a module.

Supports multiple transport methods:
- stdio: Local desktop clients (Claude Desktop, VS Code) - unlimited (default)
- http: Remote/web clients via Gradio - rate limited
- both: Run stdio and HTTP simultaneously when explicitly requested
"""

import argparse
import asyncio
import logging
from threading import Thread

logger = logging.getLogger(__name__)


async def run_stdio_server():
    """Run stdio MCP server (existing stdio implementation)."""
    from mcp.server.stdio import stdio_server
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions
    from .server import app
    from .connection import get_connection

    logger.info("Starting stdio MCP server...")

    # Initialize MT5 connection
    try:
        get_connection()
        logger.info("MT5 connection established successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MT5 connection: {e}")
        raise

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("stdio server initialized, waiting for requests...")
        init_options = InitializationOptions(
            server_name="metatrader5-mcp",
            server_version="0.5.0",
            capabilities=app.get_capabilities(
                notification_options=NotificationOptions(), experimental_capabilities={}
            ),
        )
        await app.run(read_stream, write_stream, init_options)


def run_gradio_server(server_host: str = "0.0.0.0", server_port: int = 7860, limit: int = 10):
    """Run Gradio HTTP MCP server."""
    try:
        from .gradio_server import launch_gradio_mcp

        logger.info(f"Starting Gradio HTTP MCP server on {server_host}:{server_port}...")
        launch_gradio_mcp(host=server_host, port=server_port, rate_limit=limit)
    except ImportError as exc:
        logger.error("Gradio not installed. Install with: pip install mt5-mcp[ui]")
        raise RuntimeError(
            "Gradio MCP server requires gradio[mcp] package. "
            "Install with: pip install mt5-mcp[ui]"
        ) from exc


def main():
    """Main entry point with multi-transport support."""
    parser = argparse.ArgumentParser(
        description="MT5 MCP Server v0.5 - Multi-Transport Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Default behavior (run only stdio like previous version)
    python -m mt5_mcp
  
    # Run both transports
    python -m mt5_mcp --transport both
  
    # Run only streamable HTTP
    python -m mt5_mcp --transport http --port 7860
  
    # Customize HTTP rate limit
    python -m mt5_mcp --transport http --rate-limit 30
  
    # Disable HTTP rate limiting (not recommended for public servers)
    python -m mt5_mcp --transport http --rate-limit 0

MCP Endpoints:
  - stdio: Standard input/output (for Claude Desktop, VS Code)
  - HTTP: http://localhost:7860/gradio_api/mcp/ (for web-based MCP clients)
        """,
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "both"],
        default="stdio",
        help=(
            "Transport method (default: stdio - matches previous releases). "
            "Use 'both' for dual-mode or 'http' for HTTP-only"
        ),
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port for HTTP server (default: 7860)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=10,
        help="HTTP rate limit (requests per minute per IP, 0=unlimited, default: 10)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        help="Log file path (default: stdout only)",
    )

    args = parser.parse_args()

    # Configure logging
    log_handlers = [logging.StreamHandler()]
    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=log_handlers,
    )

    logger.info(f"MT5 MCP Server v0.5 starting with transport: {args.transport}")

    # Run appropriate transport(s)
    if args.transport == "stdio":
        # Run stdio only
        asyncio.run(run_stdio_server())

    elif args.transport == "http":
        # Run HTTP only
        run_gradio_server(
            server_host=args.host,
            server_port=args.port,
            limit=args.rate_limit,
        )

    elif args.transport == "both":
        # Run both transports simultaneously
        logger.info("Running both stdio and HTTP transports")
        logger.info("stdio: Available on standard input/output (unlimited)")
        rate_limit_desc = (
            f"{args.rate_limit} req/min per IP" if args.rate_limit > 0 else "unlimited"
        )
        logger.info(
            "HTTP: http://%s:%s/gradio_api/mcp/ (rate limit: %s)",
            args.host,
            args.port,
            rate_limit_desc,
        )

        # Run stdio in background thread
        stdio_thread = Thread(
            target=lambda: asyncio.run(run_stdio_server()),
            daemon=True,
            name="stdio-server",
        )
        stdio_thread.start()
        logger.info("stdio server started in background thread")

        # Run Gradio in main thread (blocking)
        try:
            run_gradio_server(
                server_host=args.host,
                server_port=args.port,
                limit=args.rate_limit,
            )
        except KeyboardInterrupt:
            logger.info("Shutting down servers...")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    main()
