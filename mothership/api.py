"""Dashboard REST API for MCP Mothership.

FastAPI app that exposes server state, controls, and logs.
Accepts a ServerManager instance via create_app() factory.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from mothership.discovery import McpServerConfig, discover_servers
from mothership.manager import ServerManager, ServerState
from shared.errors import ServerLifecycleError
from shared.logging_config import LOG_DIR

logger = logging.getLogger(__name__)


def create_app(
    manager: ServerManager,
    servers_dir: Path | None = None,
    port_range_start: int = 8100,
    port_range_end: int = 8199,
) -> FastAPI:
    """Create and return a FastAPI app wired to the given ServerManager.

    Args:
        manager: The ServerManager instance to control.
        servers_dir: Path to servers/ directory for rescan.
        port_range_start: Port range start for auto-assignment on rescan.
        port_range_end: Port range end for auto-assignment on rescan.
    """
    app = FastAPI(title="MCP Mothership")

    @app.get("/api/servers")
    async def list_servers():
        now = datetime.now(timezone.utc)
        servers = []
        for name, state in manager.servers.items():
            uptime = None
            if state.status == "running" and state.start_time is not None:
                uptime = (now - state.start_time).total_seconds()
            servers.append({
                "name": state.config.name,
                "description": state.config.description,
                "status": state.status,
                "port": state.config.port,
                "uptime": uptime,
                "request_count": state.request_count,
                "error_count": state.error_count,
                "last_request_time": state.last_request_time,
                "tools": [],
            })
        return {"servers": servers}

    @app.post("/api/servers/{name}/start")
    async def start_server(name: str):
        try:
            await manager.start_server(name)
        except ServerLifecycleError as e:
            status = 404 if "not found" in str(e) else 400
            return JSONResponse(
                {"ok": False, "error": str(e)},
                status_code=status,
            )
        return {"ok": True, "message": f"Server '{name}' started"}

    @app.post("/api/servers/{name}/stop")
    async def stop_server(name: str):
        try:
            await manager.stop_server(name)
        except ServerLifecycleError as e:
            status = 404 if "not found" in str(e) else 400
            return JSONResponse(
                {"ok": False, "error": str(e)},
                status_code=status,
            )
        return {"ok": True, "message": f"Server '{name}' stopped"}

    @app.get("/api/servers/{name}/logs")
    async def get_logs(name: str, lines: int = Query(default=100)):
        if name not in manager.servers:
            return JSONResponse(
                {"ok": False, "error": f"Server '{name}' not found"},
                status_code=404,
            )
        log_path = Path(LOG_DIR) / f"{name}.log"
        if not log_path.exists():
            return {"server": name, "lines": []}
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            all_lines = text.splitlines()
            return {"server": name, "lines": all_lines[-lines:]}
        except OSError:
            return {"server": name, "lines": []}

    @app.post("/api/rescan")
    async def rescan():
        if servers_dir is None:
            return JSONResponse(
                {"ok": False, "error": "Rescan not available — servers directory not configured"},
                status_code=500,
            )
        new_configs = discover_servers(
            servers_dir,
            port_range_start=port_range_start,
            port_range_end=port_range_end,
        )
        manager.rescan(new_configs)
        count = len(manager.servers)
        return {"ok": True, "message": f"Rescan complete — {count} servers registered"}

    # Mount static files last (catch-all)
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
