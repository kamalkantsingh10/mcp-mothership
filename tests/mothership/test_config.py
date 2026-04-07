"""Tests for mothership/config.py — MothershipConfig validation."""

from mothership.config import MothershipConfig


class TestMothershipConfig:
    """Verify MothershipConfig defaults and validation."""

    def test_default_values(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.delenv("LOG_DIR", raising=False)
        monkeypatch.delenv("PORT_RANGE_START", raising=False)
        monkeypatch.delenv("PORT_RANGE_END", raising=False)
        monkeypatch.delenv("LOG_MAX_BYTES", raising=False)
        monkeypatch.delenv("LOG_BACKUP_COUNT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        config = MothershipConfig()
        assert config.port == 8080
        assert config.log_dir == "./logs"
        assert config.port_range_start == 8100
        assert config.port_range_end == 8199
        assert config.log_max_bytes == 5_242_880
        assert config.log_backup_count == 3
        assert config.log_level == "INFO"

    def test_inherits_base_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = MothershipConfig()
        assert config.log_level == "DEBUG"

    def test_port_range_from_env(self, monkeypatch):
        monkeypatch.setenv("PORT_RANGE_START", "9000")
        monkeypatch.setenv("PORT_RANGE_END", "9099")
        config = MothershipConfig()
        assert config.port_range_start == 9000
        assert config.port_range_end == 9099

    def test_port_from_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "3000")
        config = MothershipConfig()
        assert config.port == 3000
