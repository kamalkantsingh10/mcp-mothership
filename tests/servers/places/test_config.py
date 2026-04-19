"""Tests for Places MCP server config loading."""

import pytest

from servers.places.config import PlacesConfig


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")


def test_config_loads_api_key_from_env():
    cfg = PlacesConfig.from_yaml(config_path="nonexistent.yaml")
    assert cfg.google_places_api_key == "test-key"


def test_config_default_port_is_8102():
    cfg = PlacesConfig.from_yaml(config_path="nonexistent.yaml")
    assert cfg.port == 8102


def test_config_default_base_url():
    cfg = PlacesConfig.from_yaml(config_path="nonexistent.yaml")
    assert cfg.places_api_base_url == "https://places.googleapis.com/v1"


def test_config_default_timeout():
    cfg = PlacesConfig.from_yaml(config_path="nonexistent.yaml")
    assert cfg.places_http_timeout_seconds == 10.0


def test_config_yaml_places_section_merges(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("places:\n  places_http_timeout_seconds: 20\n")
    cfg = PlacesConfig.from_yaml(config_path=str(yaml_file))
    assert cfg.places_http_timeout_seconds == 20.0
