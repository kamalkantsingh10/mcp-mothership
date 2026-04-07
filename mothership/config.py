"""Mothership manager configuration.

MothershipConfig holds the manager's own settings (dashboard port, log dir,
port auto-assignment range). Separate from per-MCP server configs.
"""

from shared.config import BaseServerConfig


class MothershipConfig(BaseServerConfig):
    """Configuration for the MCP Mothership manager."""

    port: int = 8080
    log_dir: str = "./logs"
    port_range_start: int = 8100
    port_range_end: int = 8199
    log_max_bytes: int = 5_242_880  # 5MB
    log_backup_count: int = 3
