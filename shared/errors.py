"""Error class hierarchy for Engagement Manager.

All project errors inherit from EngagementManagerError.
Credential values are never included in error messages.
"""


class EngagementManagerError(Exception):
    """Base error — all project errors inherit from this."""


class ConfigurationError(EngagementManagerError):
    """Missing or invalid configuration."""


class ApiUnavailableError(EngagementManagerError):
    """External API is unreachable or returning errors."""


class CredentialError(EngagementManagerError):
    """Authentication/authorization failure (never includes credential values).

    Accepts a credential *name* (e.g., "IMAGEN_API_KEY") but enforces
    that the actual credential value cannot appear in the error message.
    """

    def __init__(self, credential_name: str, reason: str = "is missing or invalid"):
        self.credential_name = credential_name
        super().__init__(f"Credential '{credential_name}' {reason}")


class GenerationError(EngagementManagerError):
    """Content generation failed (bad input, quota, model error)."""
