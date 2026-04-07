"""Tests for mothership/api.py — Dashboard REST API endpoints."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mothership.api import create_app
from mothership.discovery import McpServerConfig
from mothership.manager import ServerManager, ServerState
from shared.errors import ServerLifecycleError
from shared.logging_config import LOG_DIR


def _make_config(name="imagen", port=8101):
    return McpServerConfig(
        name=name,
        description=f"{name} server",
        entry_point=f"servers.{name}.server",
        port=port,
    )


@pytest.fixture
def manager():
    configs = [_make_config("imagen", 8101), _make_config("chat", 8102)]
    return ServerManager(configs)


@pytest.fixture
def client(manager):
    app = create_app(manager)
    return TestClient(app)


class TestListServers:

    def test_list_servers_returns_all(self, client, manager):
        resp = client.get("/api/servers")
        assert resp.status_code == 200
        data = resp.json()
        assert "servers" in data
        names = {s["name"] for s in data["servers"]}
        assert names == {"imagen", "chat"}

    def test_list_servers_includes_fields(self, client, manager):
        resp = client.get("/api/servers")
        server = resp.json()["servers"][0]
        expected_fields = [
            "name", "description", "status", "port", "uptime",
            "request_count", "error_count", "last_request_time", "tools",
        ]
        for field in expected_fields:
            assert field in server, f"Missing field: {field}"

    def test_list_servers_stopped_has_null_uptime(self, client, manager):
        resp = client.get("/api/servers")
        for server in resp.json()["servers"]:
            assert server["uptime"] is None
            assert server["status"] == "stopped"

    def test_list_servers_running_has_uptime(self, client, manager):
        state = manager.servers["imagen"]
        state.status = "running"
        state.start_time = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
        state.request_count = 5
        state.error_count = 1
        state.last_request_time = "2026-04-07T14:00:00+00:00"

        resp = client.get("/api/servers")
        imagen = next(s for s in resp.json()["servers"] if s["name"] == "imagen")
        assert imagen["uptime"] is not None
        assert imagen["uptime"] > 0
        assert imagen["request_count"] == 5
        assert imagen["error_count"] == 1
        assert imagen["last_request_time"] == "2026-04-07T14:00:00+00:00"


class TestStartServer:

    def test_start_server_success(self, client, manager):
        with patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start:
            resp = client.post("/api/servers/imagen/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "imagen" in data["message"]
        mock_start.assert_called_once_with("imagen")

    def test_start_server_already_running(self, client, manager):
        with patch.object(
            manager, "start_server",
            new_callable=AsyncMock,
            side_effect=ServerLifecycleError("Server 'imagen' is already running"),
        ):
            resp = client.post("/api/servers/imagen/start")
        assert resp.status_code == 400
        data = resp.json()
        assert data["ok"] is False
        assert "already running" in data["error"]

    def test_start_server_not_found(self, client, manager):
        with patch.object(
            manager, "start_server",
            new_callable=AsyncMock,
            side_effect=ServerLifecycleError("Server 'nope' not found"),
        ):
            resp = client.post("/api/servers/nope/start")
        assert resp.status_code == 404
        data = resp.json()
        assert data["ok"] is False
        assert "not found" in data["error"]


class TestStopServer:

    def test_stop_server_success(self, client, manager):
        with patch.object(manager, "stop_server", new_callable=AsyncMock) as mock_stop:
            resp = client.post("/api/servers/imagen/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "imagen" in data["message"]
        mock_stop.assert_called_once_with("imagen")

    def test_stop_server_not_running(self, client, manager):
        with patch.object(
            manager, "stop_server",
            new_callable=AsyncMock,
            side_effect=ServerLifecycleError("Server 'imagen' is not running"),
        ):
            resp = client.post("/api/servers/imagen/stop")
        assert resp.status_code == 400
        data = resp.json()
        assert data["ok"] is False

    def test_stop_server_not_found(self, client, manager):
        with patch.object(
            manager, "stop_server",
            new_callable=AsyncMock,
            side_effect=ServerLifecycleError("Server 'nope' not found"),
        ):
            resp = client.post("/api/servers/nope/stop")
        assert resp.status_code == 404


class TestGetLogs:

    def test_get_logs_returns_lines(self, client, manager, tmp_path, monkeypatch):
        log_file = tmp_path / "imagen.log"
        log_file.write_text("line1\nline2\nline3\n")
        monkeypatch.setattr("mothership.api.LOG_DIR", str(tmp_path))

        resp = client.get("/api/servers/imagen/logs?lines=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "imagen"
        assert data["lines"] == ["line2", "line3"]

    def test_get_logs_missing_file(self, client, manager, tmp_path, monkeypatch):
        monkeypatch.setattr("mothership.api.LOG_DIR", str(tmp_path))

        resp = client.get("/api/servers/imagen/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "imagen"
        assert data["lines"] == []

    def test_get_logs_server_not_found(self, client, manager):
        resp = client.get("/api/servers/nonexistent/logs")
        assert resp.status_code == 404

    def test_get_logs_default_lines(self, client, manager, tmp_path, monkeypatch):
        lines = [f"line{i}" for i in range(200)]
        log_file = tmp_path / "imagen.log"
        log_file.write_text("\n".join(lines) + "\n")
        monkeypatch.setattr("mothership.api.LOG_DIR", str(tmp_path))

        resp = client.get("/api/servers/imagen/logs")
        data = resp.json()
        assert len(data["lines"]) == 100


class TestRescan:

    def test_rescan_discovers_new_servers(self, manager, tmp_path):
        app = create_app(
            manager,
            servers_dir=tmp_path,
            port_range_start=9000,
            port_range_end=9099,
        )
        client = TestClient(app)

        # Create a new server config
        new_dir = tmp_path / "newserver"
        new_dir.mkdir()
        (new_dir / "mothership.yaml").write_text(
            'name: newserver\ndescription: "New"\nentry_point: servers.newserver.server\nport: 9001\n'
        )

        resp = client.post("/api/rescan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "newserver" in manager.servers

    def test_rescan_keeps_existing_state(self, manager, tmp_path):
        app = create_app(
            manager,
            servers_dir=tmp_path,
            port_range_start=9000,
            port_range_end=9099,
        )
        client = TestClient(app)

        # Set some state on existing server
        manager.servers["imagen"].status = "running"
        manager.servers["imagen"].request_count = 42

        # Create config for existing server
        img_dir = tmp_path / "imagen"
        img_dir.mkdir()
        (img_dir / "mothership.yaml").write_text(
            'name: imagen\ndescription: "Updated"\nentry_point: servers.imagen.server\nport: 8101\n'
        )

        resp = client.post("/api/rescan")
        assert resp.status_code == 200

        # State preserved
        assert manager.servers["imagen"].status == "running"
        assert manager.servers["imagen"].request_count == 42
