"""Places MCP server configuration.

PlacesConfig extends BaseServerConfig with Places-specific settings.
Loads from env vars (GOOGLE_PLACES_API_KEY, etc.), .env file, and config.yaml places: section.
"""

from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

import shared.config as _config_module
from shared.config import BaseServerConfig, YamlSettingsSource


class _PlacesYamlSource(YamlSettingsSource):
    """YAML source that merges top-level keys with the places: section."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_path: Any):
        super().__init__(settings_cls, yaml_path)
        places_section = self._yaml_data.get("places", {})
        if isinstance(places_section, dict):
            self._yaml_data = {**self._yaml_data, **places_section}


class PlacesConfig(BaseServerConfig):
    """Configuration for the Places MCP server.

    Field-to-env-var mapping (pydantic uppercases field names):
        google_places_api_key         -> GOOGLE_PLACES_API_KEY
        places_api_base_url           -> PLACES_API_BASE_URL
        places_http_timeout_seconds   -> PLACES_HTTP_TIMEOUT_SECONDS
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8102
    google_places_api_key: str | None = None
    places_api_base_url: str = "https://places.googleapis.com/v1"
    places_http_timeout_seconds: float = 10.0

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: init > env > .env > yaml (with places: section) > defaults."""
        yaml_source = _PlacesYamlSource(settings_cls, _config_module._yaml_config_path)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )
