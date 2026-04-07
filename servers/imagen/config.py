"""Imagen MCP server configuration.

ImagenConfig extends BaseServerConfig with Imagen-specific settings.
Loads from env vars (IMAGEN_GCP_PROJECT, etc.), .env file, and config.yaml imagen: section.
"""

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

import shared.config as _config_module
from shared.config import BaseServerConfig, YamlSettingsSource


class _ImagenYamlSource(YamlSettingsSource):
    """YAML source that merges top-level keys with the imagen: section."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_path: Any):
        super().__init__(settings_cls, yaml_path)
        imagen_section = self._yaml_data.get("imagen", {})
        if isinstance(imagen_section, dict):
            self._yaml_data = {**self._yaml_data, **imagen_section}


class ImagenConfig(BaseServerConfig):
    """Configuration for the Imagen MCP server.

    Supports two authentication modes:
        - AI Studio: set IMAGEN_API_KEY (no GCP project needed)
        - Vertex AI: set IMAGEN_GCP_PROJECT (requires gcloud auth)

    Field-to-env-var mapping (pydantic uppercases field names):
        imagen_api_key     -> IMAGEN_API_KEY
        imagen_gcp_project -> IMAGEN_GCP_PROJECT
        imagen_gcp_region  -> IMAGEN_GCP_REGION
        imagen_model       -> IMAGEN_MODEL
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = 8101
    imagen_api_key: str | None = None
    imagen_gcp_project: str | None = None
    imagen_gcp_region: str = "us-central1"
    imagen_model: str = "gemini-3-pro-image-preview"
    default_output_dir: str = "./output"
    default_width: int = 1024
    default_height: int = 1024

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: init > env > .env > yaml (with imagen: section) > defaults."""
        yaml_source = _ImagenYamlSource(settings_cls, _config_module._yaml_config_path)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )
