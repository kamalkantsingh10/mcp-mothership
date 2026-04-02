"""Tests for servers/imagen/config.py — ImagenConfig validation and loading."""

import pytest

from shared.errors import ConfigurationError
from servers.imagen.config import ImagenConfig


class TestImagenConfigDefaults:
    """Verify default values for optional fields."""

    def test_defaults_with_api_key(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        config = ImagenConfig()
        assert config.imagen_api_key == "test-key"
        assert config.imagen_gcp_project is None
        assert config.imagen_gcp_region == "us-central1"
        assert config.imagen_model == "gemini-3-pro-image-preview"
        assert config.default_output_dir == "./output"
        assert config.default_width == 1024
        assert config.default_height == 1024
        assert config.log_level == "INFO"

    def test_defaults_with_gcp_project(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_GCP_PROJECT", "test-project")
        config = ImagenConfig()
        assert config.imagen_gcp_project == "test-project"
        assert config.imagen_api_key is None

    def test_inherits_base_log_level(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = ImagenConfig()
        assert config.log_level == "DEBUG"


class TestImagenConfigAuthModes:
    """Verify both auth modes work and neither is strictly required."""

    def test_no_credentials_still_creates_config(self, monkeypatch):
        monkeypatch.delenv("IMAGEN_GCP_PROJECT", raising=False)
        monkeypatch.delenv("IMAGEN_API_KEY", raising=False)
        config = ImagenConfig.from_yaml(config_path="nonexistent.yaml")
        assert config.imagen_api_key is None
        assert config.imagen_gcp_project is None

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "my-key")
        config = ImagenConfig.from_yaml(config_path="nonexistent.yaml")
        assert config.imagen_api_key == "my-key"

    def test_gcp_project_from_env(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_GCP_PROJECT", "my-project")
        config = ImagenConfig.from_yaml(config_path="nonexistent.yaml")
        assert config.imagen_gcp_project == "my-project"

    def test_both_set_api_key_and_gcp_project(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "my-key")
        monkeypatch.setenv("IMAGEN_GCP_PROJECT", "my-project")
        config = ImagenConfig()
        assert config.imagen_api_key == "my-key"
        assert config.imagen_gcp_project == "my-project"


class TestImagenConfigEnvVars:
    """Verify env var mapping (field name uppercased)."""

    def test_env_vars_map_correctly(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_GCP_PROJECT", "env-project")
        monkeypatch.setenv("IMAGEN_GCP_REGION", "europe-west1")
        monkeypatch.setenv("IMAGEN_MODEL", "imagen-4.0")
        config = ImagenConfig()
        assert config.imagen_gcp_project == "env-project"
        assert config.imagen_gcp_region == "europe-west1"
        assert config.imagen_model == "imagen-4.0"


class TestImagenConfigYaml:
    """Verify YAML loading from imagen: section."""

    def test_yaml_imagen_section_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "log_level: WARNING\n"
            "imagen:\n"
            "  default_output_dir: /custom/output\n"
            "  default_width: 512\n"
            "  default_height: 768\n"
        )
        config = ImagenConfig.from_yaml(config_path=config_file)
        assert config.log_level == "WARNING"
        assert config.default_output_dir == "/custom/output"
        assert config.default_width == 512
        assert config.default_height == 768

    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        monkeypatch.setenv("DEFAULT_OUTPUT_DIR", "/env/output")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "imagen:\n"
            "  default_output_dir: /yaml/output\n"
        )
        config = ImagenConfig.from_yaml(config_path=config_file)
        assert config.default_output_dir == "/env/output"

    def test_from_yaml_overrides_take_priority(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "imagen:\n"
            "  default_output_dir: /yaml/output\n"
        )
        config = ImagenConfig.from_yaml(
            config_path=config_file, default_output_dir="/override/output"
        )
        assert config.default_output_dir == "/override/output"

    def test_missing_yaml_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        config = ImagenConfig.from_yaml(config_path=tmp_path / "missing.yaml")
        assert config.default_output_dir == "./output"
        assert config.default_width == 1024


class TestImagenConfigExtra:
    """Verify extra fields are ignored."""

    def test_extra_fields_ignored(self, monkeypatch):
        monkeypatch.setenv("IMAGEN_API_KEY", "test-key")
        config = ImagenConfig(unknown_field="value")
        assert not hasattr(config, "unknown_field")
