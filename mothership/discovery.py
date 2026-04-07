"""Config discovery and registration for MCP servers.

Scans servers/*/mothership.yaml to discover and register MCP servers.
Each server provides a mothership.yaml with its registration config.
"""

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from shared.errors import ConfigurationError

logger = logging.getLogger(__name__)


class McpServerConfig(BaseModel):
    """Registration config for a single MCP server.

    Loaded from a mothership.yaml file in each server's directory.
    """

    name: str
    description: str
    entry_point: str
    port: int | None = None
    env_vars: list[str] = []


def discover_servers(
    servers_dir: Path,
    port_range_start: int = 8100,
    port_range_end: int = 8199,
) -> list[McpServerConfig]:
    """Scan servers/*/mothership.yaml and return validated server configs.

    Malformed or invalid configs are logged and skipped. Servers without
    an explicit port get one auto-assigned from the configurable range.

    Args:
        servers_dir: Path to the servers/ directory to scan.
        port_range_start: Start of auto-assignment port range (inclusive).
        port_range_end: End of auto-assignment port range (inclusive).

    Returns:
        List of validated McpServerConfig instances.

    Raises:
        ConfigurationError: If the port range is exhausted.
    """
    configs: list[McpServerConfig] = []

    for yaml_path in sorted(servers_dir.glob("*/mothership.yaml")):
        try:
            raw = yaml.safe_load(yaml_path.read_text())
            if not isinstance(raw, dict):
                logger.error("Invalid config (not a mapping) in %s", yaml_path)
                continue
            config = McpServerConfig(**raw)
            configs.append(config)
        except yaml.YAMLError as e:
            logger.error("Malformed YAML in %s: %s", yaml_path, e)
        except ValidationError as e:
            logger.error("Validation error in %s: %s", yaml_path, e)

    # Auto-assign ports to configs that don't specify one
    claimed_ports = {c.port for c in configs if c.port is not None}
    next_port = port_range_start

    for config in configs:
        if config.port is None:
            while next_port in claimed_ports and next_port <= port_range_end:
                next_port += 1
            if next_port > port_range_end:
                raise ConfigurationError(
                    f"Port range {port_range_start}-{port_range_end} exhausted — "
                    f"cannot assign port to server '{config.name}'"
                )
            config.port = next_port
            claimed_ports.add(next_port)
            next_port += 1

    return configs
