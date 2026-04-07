"""Tests for mothership/manager.py — process management, crash detection, shutdown."""

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mothership.discovery import McpServerConfig
from mothership.manager import ServerManager, ServerState, SHUTDOWN_GRACE_SECONDS
from shared.errors import ServerLifecycleError


def _make_config(name="test", port=8101):
    return McpServerConfig(
        name=name,
        description=f"{name} server",
        entry_point=f"servers.{name}.server",
        port=port,
    )


def _make_mock_process(pid=12345, returncode=None):
    proc = AsyncMock()
    proc.pid = pid
    proc.returncode = returncode
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"", b""))
    proc.wait = AsyncMock()
    return proc


class TestStartServer:

    @pytest.mark.asyncio
    async def test_start_server_launches_subprocess(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        mock_exec.assert_called_once()
        args = mock_exec.call_args
        # Verify entry_point is in the args
        assert "servers.test.server" in args[0]

    @pytest.mark.asyncio
    async def test_start_server_tracks_state(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=99999)

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        state = manager.servers["test"]
        assert state.status == "running"
        assert state.pid == 99999
        assert state.start_time is not None
        assert isinstance(state.start_time, datetime)

    @pytest.mark.asyncio
    async def test_start_already_running_raises_error(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        with pytest.raises(ServerLifecycleError, match="already running"):
            await manager.start_server("test")

    @pytest.mark.asyncio
    async def test_start_unknown_server_raises_error(self):
        manager = ServerManager([])
        with pytest.raises(ServerLifecycleError, match="not found"):
            await manager.start_server("nonexistent")


class TestStopServer:

    @pytest.mark.asyncio
    async def test_stop_server_sends_sigterm(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()
        mock_proc.returncode = None

        # Make wait() set returncode to simulate process exiting
        async def fake_wait():
            mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(side_effect=fake_wait)

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")
            await manager.stop_server("test")

        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server_updates_status(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()

        async def fake_wait():
            mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(side_effect=fake_wait)

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")
            await manager.stop_server("test")

        state = manager.servers["test"]
        assert state.status == "stopped"
        assert state.pid is None
        assert state.process is None

    @pytest.mark.asyncio
    async def test_stop_not_running_raises_error(self):
        config = _make_config()
        manager = ServerManager([config])
        with pytest.raises(ServerLifecycleError, match="not running"):
            await manager.stop_server("test")

    @pytest.mark.asyncio
    async def test_stop_unresponsive_sends_sigkill(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()
        killed = False

        # Process ignores SIGTERM but exits on SIGKILL
        async def slow_wait():
            if not killed:
                await asyncio.sleep(100)
        mock_proc.wait = AsyncMock(side_effect=slow_wait)

        def fake_kill():
            nonlocal killed
            killed = True
            mock_proc.returncode = -9
            mock_proc.wait = AsyncMock()
        mock_proc.kill = MagicMock(side_effect=fake_kill)

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

            with patch("mothership.manager.SHUTDOWN_GRACE_SECONDS", 0.1):
                await manager.stop_server("test")

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()


class TestCrashDetection:

    @pytest.mark.asyncio
    async def test_crash_detection(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=12345)
        mock_proc.returncode = None  # Initially running
        mock_proc.communicate = AsyncMock(return_value=(b"", b"segfault at 0x0"))

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        assert manager.servers["test"].status == "running"

        # Simulate crash: set returncode
        mock_proc.returncode = 1

        # Run one iteration of health check manually
        with patch("mothership.manager.HEALTH_CHECK_INTERVAL", 0):
            task = asyncio.create_task(manager._health_check_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        state = manager.servers["test"]
        assert state.status == "crashed"
        assert state.last_exit_code == 1
        assert state.last_stderr == "segfault at 0x0"
        assert state.pid is None


class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_stops_all_running(self):
        configs = [_make_config("a", 8101), _make_config("b", 8102)]
        manager = ServerManager(configs)

        procs = {}
        for cfg in configs:
            proc = _make_mock_process(pid=hash(cfg.name) % 99999)
            async def fake_wait(p=proc):
                p.returncode = 0
            proc.wait = AsyncMock(side_effect=fake_wait)
            procs[cfg.name] = proc

        call_count = 0
        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            name = configs[call_count].name
            call_count += 1
            return procs[name]

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec_fn:
            mock_exec_fn.side_effect = mock_exec
            await manager.start_server("a")
            await manager.start_server("b")
            await manager.shutdown()

        for proc in procs.values():
            proc.terminate.assert_called_once()

        for state in manager.servers.values():
            assert state.status == "stopped"

    @pytest.mark.asyncio
    async def test_shutdown_sigkill_after_grace(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process()
        killed = False

        # Process ignores SIGTERM but exits on SIGKILL
        async def slow_wait():
            if not killed:
                await asyncio.sleep(100)
        mock_proc.wait = AsyncMock(side_effect=slow_wait)

        def fake_kill():
            nonlocal killed
            killed = True
            mock_proc.returncode = -9
            mock_proc.wait = AsyncMock()
        mock_proc.kill = MagicMock(side_effect=fake_kill)

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

            with patch("mothership.manager.SHUTDOWN_GRACE_SECONDS", 0.1):
                await manager.shutdown()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()


class TestCrashLogging:

    @pytest.mark.asyncio
    async def test_crash_logged_with_exit_code_and_stderr(self, caplog):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=12345)
        mock_proc.returncode = None
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal error occurred"))

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        mock_proc.returncode = 137

        with caplog.at_level(logging.ERROR):
            with patch("mothership.manager.HEALTH_CHECK_INTERVAL", 0):
                task = asyncio.create_task(manager._health_check_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert "crashed with exit code 137" in caplog.text
        assert "fatal error occurred" in caplog.text

    @pytest.mark.asyncio
    async def test_crash_log_no_credentials(self, caplog):
        """Verify credential values never appear in crash log output."""
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=12345)
        mock_proc.returncode = None
        # Simulate stderr that mentions a credential name but not its value
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Credential 'IMAGEN_API_KEY' is missing or invalid")
        )

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        mock_proc.returncode = 1

        with caplog.at_level(logging.ERROR):
            with patch("mothership.manager.HEALTH_CHECK_INTERVAL", 0):
                task = asyncio.create_task(manager._health_check_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # The log should contain the credential name but not any actual secret value
        assert "IMAGEN_API_KEY" in caplog.text
        # A real API key would look like this — verify it's NOT in the logs
        assert "AIzaSy" not in caplog.text


class TestMetricsPolling:

    @pytest.mark.asyncio
    async def test_health_check_polls_metrics(self):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=12345)
        mock_proc.returncode = None  # Still running

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        metrics_data = {"request_count": 5, "error_count": 1, "last_request_time": "2026-04-07T12:00:00+00:00"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = metrics_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mothership.manager.httpx.AsyncClient", return_value=mock_client):
            with patch("mothership.manager.HEALTH_CHECK_INTERVAL", 0):
                task = asyncio.create_task(manager._health_check_loop())
                await asyncio.sleep(0.05)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        state = manager.servers["test"]
        assert state.request_count == 5
        assert state.error_count == 1
        assert state.last_request_time == "2026-04-07T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_health_check_metrics_unreachable(self, caplog):
        config = _make_config()
        manager = ServerManager([config])
        mock_proc = _make_mock_process(pid=12345)
        mock_proc.returncode = None  # Still running

        with patch("mothership.manager.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            await manager.start_server("test")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=OSError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with caplog.at_level(logging.WARNING):
            with patch("mothership.manager.httpx.AsyncClient", return_value=mock_client):
                with patch("mothership.manager.HEALTH_CHECK_INTERVAL", 0):
                    task = asyncio.create_task(manager._health_check_loop())
                    await asyncio.sleep(0.05)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        state = manager.servers["test"]
        assert state.status == "running"  # Still running despite metrics failure
        assert "Failed to poll metrics" in caplog.text


class TestGetServerStates:

    def test_get_server_states(self):
        configs = [_make_config("a", 8101), _make_config("b", 8102)]
        manager = ServerManager(configs)
        states = manager.servers
        assert "a" in states
        assert "b" in states
        assert isinstance(states["a"], ServerState)
        assert states["a"].config.name == "a"
        assert states["b"].status == "stopped"
