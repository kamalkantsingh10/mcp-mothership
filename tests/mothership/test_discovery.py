"""Tests for mothership/discovery.py — config scanning, validation, and port assignment."""

import logging

import pytest

from mothership.discovery import McpServerConfig, discover_servers
from shared.errors import ConfigurationError


def _write_yaml(tmp_path, server_name, content):
    """Helper to create a servers/<name>/mothership.yaml file."""
    server_dir = tmp_path / server_name
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / "mothership.yaml").write_text(content)
    return server_dir


class TestMcpServerConfig:
    """Validate the McpServerConfig pydantic model."""

    def test_valid_config_all_fields(self):
        config = McpServerConfig(
            name="test",
            description="A test server",
            entry_point="servers.test.server",
            port=8101,
            env_vars=["API_KEY"],
        )
        assert config.name == "test"
        assert config.port == 8101
        assert config.env_vars == ["API_KEY"]

    def test_valid_config_defaults(self):
        config = McpServerConfig(
            name="test",
            description="A test server",
            entry_point="servers.test.server",
        )
        assert config.port is None
        assert config.env_vars == []

    def test_missing_name_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            McpServerConfig(
                description="A test server",
                entry_point="servers.test.server",
            )

    def test_missing_description_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            McpServerConfig(
                name="test",
                entry_point="servers.test.server",
            )

    def test_missing_entry_point_raises_validation_error(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            McpServerConfig(
                name="test",
                description="A test server",
            )


class TestDiscoverServers:
    """Tests for the discover_servers() function."""

    def test_discover_valid_config(self, tmp_path):
        _write_yaml(
            tmp_path,
            "imagen",
            'name: imagen\ndescription: "Image gen"\nentry_point: servers.imagen.server\nport: 8101\n',
        )
        configs = discover_servers(tmp_path)
        assert len(configs) == 1
        assert configs[0].name == "imagen"
        assert configs[0].port == 8101

    def test_discover_multiple_configs(self, tmp_path):
        _write_yaml(
            tmp_path,
            "imagen",
            'name: imagen\ndescription: "Image gen"\nentry_point: servers.imagen.server\nport: 8101\n',
        )
        _write_yaml(
            tmp_path,
            "chat",
            'name: chat\ndescription: "Chat server"\nentry_point: servers.chat.server\nport: 8102\n',
        )
        configs = discover_servers(tmp_path)
        assert len(configs) == 2

    def test_missing_required_field_logs_error(self, tmp_path, caplog):
        _write_yaml(
            tmp_path,
            "bad",
            'description: "Missing name"\nentry_point: servers.bad.server\n',
        )
        with caplog.at_level(logging.ERROR):
            configs = discover_servers(tmp_path)
        assert len(configs) == 0
        assert "Validation error" in caplog.text

    def test_malformed_yaml_logs_error(self, tmp_path, caplog):
        _write_yaml(tmp_path, "bad", "name: [invalid yaml\n  broken:")
        with caplog.at_level(logging.ERROR):
            configs = discover_servers(tmp_path)
        assert len(configs) == 0
        assert "Malformed YAML" in caplog.text

    def test_no_configs_returns_empty_list(self, tmp_path):
        configs = discover_servers(tmp_path)
        assert configs == []

    def test_port_auto_assignment(self, tmp_path):
        _write_yaml(
            tmp_path,
            "noport",
            'name: noport\ndescription: "No port"\nentry_point: servers.noport.server\n',
        )
        configs = discover_servers(tmp_path, port_range_start=9000, port_range_end=9099)
        assert len(configs) == 1
        assert configs[0].port == 9000

    def test_port_no_collision(self, tmp_path):
        _write_yaml(
            tmp_path,
            "a_explicit",
            'name: explicit\ndescription: "Has port"\nentry_point: servers.a.server\nport: 9000\n',
        )
        _write_yaml(
            tmp_path,
            "b_auto",
            'name: auto\ndescription: "No port"\nentry_point: servers.b.server\n',
        )
        configs = discover_servers(tmp_path, port_range_start=9000, port_range_end=9099)
        assert len(configs) == 2
        ports = {c.port for c in configs}
        assert 9000 in ports
        assert len(ports) == 2  # No collision
        # Auto-assigned port should skip 9000
        auto_config = next(c for c in configs if c.name == "auto")
        assert auto_config.port == 9001

    def test_port_range_exhaustion(self, tmp_path):
        # Range of 1 port, but 2 servers need auto-assignment
        _write_yaml(
            tmp_path,
            "a_server",
            'name: a\ndescription: "A"\nentry_point: servers.a.server\n',
        )
        _write_yaml(
            tmp_path,
            "b_server",
            'name: b\ndescription: "B"\nentry_point: servers.b.server\n',
        )
        with pytest.raises(ConfigurationError, match="exhausted"):
            discover_servers(tmp_path, port_range_start=9000, port_range_end=9000)

    def test_valid_and_invalid_mixed(self, tmp_path, caplog):
        _write_yaml(
            tmp_path,
            "a_good",
            'name: good\ndescription: "Good"\nentry_point: servers.good.server\nport: 8101\n',
        )
        _write_yaml(
            tmp_path,
            "b_bad",
            'description: "Missing name"\nentry_point: servers.bad.server\n',
        )
        _write_yaml(
            tmp_path,
            "c_also_good",
            'name: also_good\ndescription: "Also good"\nentry_point: servers.also.server\nport: 8102\n',
        )
        with caplog.at_level(logging.ERROR):
            configs = discover_servers(tmp_path)
        assert len(configs) == 2
        names = {c.name for c in configs}
        assert names == {"good", "also_good"}
        assert "Validation error" in caplog.text
