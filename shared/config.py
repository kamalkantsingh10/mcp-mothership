"""Base configuration module using pydantic-settings.

Dual-layer config loading:
- .env -> pydantic-settings loads env vars automatically (secrets)
- config.yaml -> parsed with PyYAML as a custom settings source (operational settings)

Priority (highest to lowest): init kwargs > env vars > .env file > config.yaml > defaults
"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from shared.errors import ConfigurationError

# Module-level storage for YAML path, set before constructing config
_yaml_config_path: Path | str = "config.yaml"


def load_yaml_config(config_path: Path | str = "config.yaml") -> dict[str, Any]:
    """Load operational settings from a YAML config file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Dictionary of config values, or empty dict if file not found.

    Raises:
        ConfigurationError: If the YAML file exists but is malformed.
    """
    path = Path(config_path)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {e}") from e


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from a YAML file."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_path: Path | str):
        super().__init__(settings_cls)
        self._yaml_data = load_yaml_config(yaml_path)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        val = self._yaml_data.get(field_name)
        return val, field_name, val is not None

    def __call__(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name, field_info in self.settings_cls.model_fields.items():
            val, _, is_set = self.get_field_value(field_info, field_name)
            if is_set:
                result[field_name] = val
        return result


class BaseServerConfig(BaseSettings):
    """Base configuration that all MCP servers inherit from.

    Loads secrets from .env via pydantic-settings env var support,
    and operational settings from config.yaml via PyYAML.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: init > env > .env > yaml > defaults."""
        yaml_source = YamlSettingsSource(settings_cls, _yaml_config_path)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )

    @classmethod
    def from_yaml(
        cls,
        config_path: Path | str = "config.yaml",
        **overrides: Any,
    ) -> "BaseServerConfig":
        """Create config by merging YAML file values with env vars.

        Priority: overrides > env vars > .env file > config.yaml > defaults

        Args:
            config_path: Path to the YAML config file.
            **overrides: Additional values that override all other sources.

        Returns:
            Validated config instance.

        Raises:
            ConfigurationError: If validation fails.
        """
        global _yaml_config_path
        _yaml_config_path = config_path
        try:
            return cls(**overrides)
        except Exception as e:
            raise ConfigurationError(str(e)) from e
