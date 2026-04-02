"""Tests for shared/config.py — config validation and dual-source loading."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from shared.config import BaseServerConfig, load_yaml_config
from shared.errors import ConfigurationError


class TestLoadYamlConfig:
    """Verify YAML config loading."""

    def test_load_valid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: DEBUG\n")
        result = load_yaml_config(config_file)
        assert result == {"log_level": "DEBUG"}

    def test_load_nonexistent_returns_empty(self, tmp_path):
        result = load_yaml_config(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_malformed_yaml_raises(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(":\n  - :\n    bad: [unterminated")
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_yaml_config(config_file)

    def test_load_non_dict_yaml_returns_empty(self, tmp_path):
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n")
        result = load_yaml_config(config_file)
        assert result == {}

    def test_load_empty_yaml_returns_empty(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        result = load_yaml_config(config_file)
        assert result == {}


class TestBaseServerConfig:
    """Verify BaseServerConfig validation and defaults."""

    def test_default_log_level(self):
        config = BaseServerConfig()
        assert config.log_level == "INFO"

    def test_custom_log_level(self):
        config = BaseServerConfig(log_level="DEBUG")
        assert config.log_level == "DEBUG"

    def test_from_yaml_loads_values(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: WARNING\n")
        config = BaseServerConfig.from_yaml(config_path=config_file)
        assert config.log_level == "WARNING"

    def test_from_yaml_missing_file_uses_defaults(self, tmp_path):
        config = BaseServerConfig.from_yaml(config_path=tmp_path / "missing.yaml")
        assert config.log_level == "INFO"

    def test_from_yaml_with_overrides(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: WARNING\n")
        config = BaseServerConfig.from_yaml(config_path=config_file, log_level="ERROR")
        assert config.log_level == "ERROR"

    def test_extra_fields_ignored(self):
        config = BaseServerConfig(log_level="INFO", unknown_field="value")
        assert config.log_level == "INFO"
        assert not hasattr(config, "unknown_field")


class TestConfigValidation:
    """Verify validation produces clear error messages."""

    def test_subclass_missing_required_field(self, tmp_path, monkeypatch):
        """A subclass with a required field raises ConfigurationError when missing."""
        from pydantic_settings import BaseSettings

        class TestConfig(BaseServerConfig):
            required_field: str

        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: INFO\n")

        # Clear any env vars that might satisfy the field
        monkeypatch.delenv("REQUIRED_FIELD", raising=False)

        with pytest.raises(ConfigurationError, match="required_field"):
            TestConfig.from_yaml(config_path=config_file)

    def test_subclass_valid_with_required_field(self, tmp_path):
        """A subclass loads correctly when required fields are provided."""

        class TestConfig(BaseServerConfig):
            required_field: str

        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: DEBUG\nrequired_field: hello\n")

        config = TestConfig.from_yaml(config_path=config_file)
        assert config.required_field == "hello"
        assert config.log_level == "DEBUG"

    def test_env_var_overrides_yaml(self, tmp_path, monkeypatch):
        """Env vars take precedence over YAML values."""
        monkeypatch.setenv("LOG_LEVEL", "CRITICAL")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: DEBUG\n")

        config = BaseServerConfig.from_yaml(config_path=config_file)
        assert config.log_level == "CRITICAL"
