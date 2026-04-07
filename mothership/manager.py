"""Process manager for MCP servers.

Launches, monitors, and shuts down MCP server subprocesses.
Each server runs as an independent process via asyncio.create_subprocess_exec.
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from mothership.discovery import McpServerConfig
from shared.errors import ServerLifecycleError

logger = logging.getLogger(__name__)

# Grace period before SIGKILL (seconds)
SHUTDOWN_GRACE_SECONDS = 5

# Health check polling interval (seconds) — within <=5s NFR
HEALTH_CHECK_INTERVAL = 3


@dataclass
class ServerState:
    """Runtime state for a managed MCP server."""

    config: McpServerConfig
    process: asyncio.subprocess.Process | None = None
    status: str = "stopped"  # stopped, running, crashed
    pid: int | None = None
    start_time: datetime | None = None
    last_exit_code: int | None = None
    last_stderr: str | None = None
    request_count: int = 0
    error_count: int = 0
    last_request_time: str | None = None  # ISO 8601


class ServerManager:
    """Manages MCP server subprocesses."""

    def __init__(
        self,
        configs: list[McpServerConfig],
        project_root: Path | None = None,
    ) -> None:
        self._servers: dict[str, ServerState] = {
            c.name: ServerState(config=c) for c in configs
        }
        self._project_root = project_root or Path.cwd()
        self._health_task: asyncio.Task | None = None

    @property
    def servers(self) -> dict[str, ServerState]:
        return self._servers

    async def start_server(self, name: str) -> None:
        """Start an MCP server subprocess.

        Raises:
            ServerLifecycleError: If server not found or already running.
        """
        state = self._servers.get(name)
        if state is None:
            raise ServerLifecycleError(f"Server '{name}' not found")
        if state.status == "running":
            raise ServerLifecycleError(f"Server '{name}' is already running")

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", state.config.entry_point,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_root),
        )
        state.process = process
        state.pid = process.pid
        state.status = "running"
        state.start_time = datetime.now(timezone.utc)
        state.last_exit_code = None
        state.last_stderr = None
        logger.info("Started server '%s' (PID %d)", name, process.pid)

    async def stop_server(self, name: str) -> None:
        """Stop a running MCP server subprocess.

        Sends SIGTERM, waits for grace period, then SIGKILL if needed.

        Raises:
            ServerLifecycleError: If server not found or not running.
        """
        state = self._servers.get(name)
        if state is None:
            raise ServerLifecycleError(f"Server '{name}' not found")
        if state.status != "running" or state.process is None:
            raise ServerLifecycleError(f"Server '{name}' is not running")

        process = state.process
        process.terminate()
        logger.info("Sent SIGTERM to server '%s' (PID %d)", name, state.pid)

        try:
            await asyncio.wait_for(process.wait(), timeout=SHUTDOWN_GRACE_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "Server '%s' (PID %d) did not exit after %ds, sending SIGKILL",
                name, state.pid, SHUTDOWN_GRACE_SECONDS,
            )
            process.kill()
            await process.wait()

        state.status = "stopped"
        state.pid = None
        state.process = None
        logger.info("Server '%s' stopped", name)

    def rescan(self, new_configs: list[McpServerConfig]) -> None:
        """Merge newly discovered configs into the server dict.

        Existing servers keep their runtime state. New servers are added as stopped.
        """
        for config in new_configs:
            if config.name not in self._servers:
                self._servers[config.name] = ServerState(config=config)
                logger.info("Rescan: added new server '%s'", config.name)
            else:
                self._servers[config.name].config = config

    async def _health_check_loop(self) -> None:
        """Poll running servers for crashes and metrics at regular intervals."""
        while True:
            for name, state in self._servers.items():
                if state.status != "running" or state.process is None:
                    continue
                if state.process.returncode is not None:
                    # Process exited unexpectedly — crash detected
                    stderr_bytes = b""
                    try:
                        _, stderr_bytes = await asyncio.wait_for(
                            state.process.communicate(), timeout=1.0,
                        )
                    except (asyncio.TimeoutError, ProcessLookupError):
                        pass

                    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                    state.status = "crashed"
                    state.last_exit_code = state.process.returncode
                    state.last_stderr = stderr_text or None
                    state.pid = None
                    state.process = None
                    logger.error(
                        "Server '%s' crashed with exit code %d: %s",
                        name, state.last_exit_code, stderr_text[:500] if stderr_text else "(no stderr)",
                    )
                    continue

                # Poll /metrics from running server
                if state.config.port is not None:
                    await self._poll_metrics(name, state)

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def _poll_metrics(self, name: str, state: ServerState) -> None:
        """Fetch /metrics from a running server and update state."""
        url = f"http://localhost:{state.config.port}/metrics"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=2.0)
                response.raise_for_status()
                data = response.json()
                state.request_count = data.get("request_count", 0)
                state.error_count = data.get("error_count", 0)
                state.last_request_time = data.get("last_request_time")
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
            logger.warning("Failed to poll metrics for '%s': %s", name, e)

    def start_health_monitoring(self) -> None:
        """Start the background health check loop."""
        if self._health_task is None or self._health_task.done():
            self._health_task = asyncio.get_event_loop().create_task(
                self._health_check_loop()
            )
            logger.info("Health monitoring started (interval=%ds)", HEALTH_CHECK_INTERVAL)

    def stop_health_monitoring(self) -> None:
        """Cancel the background health check loop."""
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            self._health_task = None

    async def shutdown(self) -> None:
        """Clean shutdown: SIGTERM all running servers, then SIGKILL stragglers."""
        self.stop_health_monitoring()

        running = [
            (name, state) for name, state in self._servers.items()
            if state.status == "running" and state.process is not None
        ]

        if not running:
            logger.info("No running servers to shut down")
            return

        # Send SIGTERM to all
        for name, state in running:
            state.process.terminate()
            logger.info("Shutdown: SIGTERM sent to '%s' (PID %d)", name, state.pid)

        # Wait for all to exit within grace period
        processes = [state.process for _, state in running]
        try:
            await asyncio.wait_for(
                asyncio.gather(*(p.wait() for p in processes), return_exceptions=True),
                timeout=SHUTDOWN_GRACE_SECONDS,
            )
        except asyncio.TimeoutError:
            pass

        # SIGKILL any still alive
        for name, state in running:
            if state.process and state.process.returncode is None:
                logger.warning("Shutdown: SIGKILL sent to '%s' (PID %d)", name, state.pid)
                state.process.kill()
                await state.process.wait()

        # Update all states
        for name, state in running:
            state.status = "stopped"
            state.pid = None
            state.process = None

        logger.info("Shutdown complete — %d servers stopped", len(running))
