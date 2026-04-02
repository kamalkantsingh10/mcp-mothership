# Deferred Work

## Deferred from: code review of story 2-2 (2026-04-01)

- **Global `_yaml_config_path` concurrency hazard** — `shared/config.py` uses a module-level global to pass YAML path to settings source. Concurrent `from_yaml()` calls with different paths will clobber each other. Refactor to thread-safe approach when adding multi-server process support.
- **Module-level config in `servers/imagen/server.py`** — Config loaded at import time. Makes module impossible to import without valid environment. Consider moving to a startup function for testability.
- **`.env` and `config.yaml` resolved relative to CWD** — If server launched from different directory, config files won't be found. Consider resolving relative to `__file__` or project root.
- **Unpinned dependency versions** — `pydantic-settings = "*"` and `pyyaml = "*"` in pyproject.toml. Mitigated by poetry.lock but could break on `poetry update`.
- **`config.yaml` missing optional field documentation** — `imagen_model` and `imagen_gcp_region` not listed in config.yaml, reducing discoverability.
