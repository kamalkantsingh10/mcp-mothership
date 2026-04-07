"""MCP Mothership entry point.

Discovers MCP server configs, creates the ServerManager,
starts health monitoring and the dashboard API, and waits for shutdown signal.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

from mothership.api import create_app
from mothership.config import MothershipConfig
from mothership.discovery import discover_servers
from mothership.manager import ServerManager
from shared.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def _run() -> None:
    project_root = Path(__file__).resolve().parent.parent
    servers_dir = project_root / "servers"

    config = MothershipConfig.from_yaml(config_path=project_root / "config.yaml")
    setup_logging(
        config.log_level,
        log_name="mothership",
        max_bytes=config.log_max_bytes,
        backup_count=config.log_backup_count,
    )

    logger.info("MCP Mothership starting...")

    configs = discover_servers(
        servers_dir,
        port_range_start=config.port_range_start,
        port_range_end=config.port_range_end,
    )
    logger.info("Discovered %d server config(s)", len(configs))

    manager = ServerManager(configs, project_root=project_root)
    manager.start_health_monitoring()

    # Create and start the dashboard API
    app = create_app(
        manager,
        servers_dir=servers_dir,
        port_range_start=config.port_range_start,
        port_range_end=config.port_range_end,
    )
    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.port,
        log_level="info",
    )
    api_server = uvicorn.Server(uvicorn_config)

    logger.info("MCP Mothership ready — %d servers registered, API on port %d", len(configs), config.port)

    # Register signal handlers for clean shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()
        api_server.should_exit = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Run API server and wait for shutdown concurrently
    api_task = asyncio.create_task(api_server.serve())

    await shutdown_event.wait()

    logger.info("Shutting down...")
    api_server.should_exit = True
    await api_task
    await manager.shutdown()
    logger.info("MCP Mothership stopped")


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
