"""Error class hierarchy for MCP Mothership.

All project errors inherit from MothershipError.
Credential values are never included in error messages.
"""


class MothershipError(Exception):
    """Base error — all project errors inherit from this."""


class ConfigurationError(MothershipError):
    """Missing or invalid configuration."""


class ApiUnavailableError(MothershipError):
    """External API is unreachable or returning errors."""


class CredentialError(MothershipError):
    """Authentication/authorization failure (never includes credential values).

    Accepts a credential *name* (e.g., "IMAGEN_API_KEY") but enforces
    that the actual credential value cannot appear in the error message.
    """

    def __init__(self, credential_name: str, reason: str = "is missing or invalid"):
        self.credential_name = credential_name
        super().__init__(f"Credential '{credential_name}' {reason}")


class GenerationError(MothershipError):
    """Content generation failed (bad input, quota, model error)."""


class ServerLifecycleError(MothershipError):
    """MCP server failed to start, stop, or encountered a lifecycle issue."""
