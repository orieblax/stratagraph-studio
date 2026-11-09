"""Ephemeral Secrets Vault for runtime-provided credentials.

Enforces that sensitive credentials (DATABRICKS_TOKEN, SUPABASE_SERVICE_KEY,
OPENAI_API_KEY, SMTP_PASS) reside exclusively in ephemeral, request-scoped
memory via contextvars. Never persisted to AgentState, PostgresSaver checkpoints,
or serialized into LangSmith traces.
"""

from __future__ import annotations

import contextvars
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any

from pydantic import SecretStr

# Request-scoped ContextVar storing SecretStr mappings
_EPHEMERAL_SECRETS: contextvars.ContextVar[dict[str, SecretStr] | None] = contextvars.ContextVar(
    "ephemeral_secrets",
    default=None,
)


class EphemeralSecretVault:
    """Thread-safe and async-isolated vault for runtime credentials."""

    @classmethod
    def _get_map(cls) -> dict[str, SecretStr]:
        mapping = _EPHEMERAL_SECRETS.get()
        if mapping is None:
            mapping = {}
            _EPHEMERAL_SECRETS.set(mapping)
        return mapping

    @classmethod
    def set_secrets(cls, secrets: Mapping[str, str | SecretStr | None]) -> None:
        """Set ephemeral secrets for the current async task context."""
        current = dict(cls._get_map())
        for key, val in secrets.items():
            if val is None:
                continue
            if isinstance(val, SecretStr):
                current[key.upper()] = val
            elif isinstance(val, str) and val.strip():
                current[key.upper()] = SecretStr(val.strip())
        _EPHEMERAL_SECRETS.set(current)

    @classmethod
    def get_secret(cls, key: str) -> SecretStr | None:
        """Retrieve a SecretStr for a key, or None if not configured."""
        return cls._get_map().get(key.upper())

    @classmethod
    def get_secret_value(cls, key: str, fallback_env: str | None = None) -> str | None:
        """Retrieve the raw decrypted string for immediate client invocation only.

        Optional fallback_env allows falling back to an environment variable value
        if not supplied dynamically via the Studio UI ConfigPanel.
        """
        secret = cls.get_secret(key)
        if secret is not None:
            return secret.get_secret_value()
        return fallback_env

    @classmethod
    def has_secret(cls, key: str) -> bool:
        """Check if a secret key is present in the ephemeral context."""
        return key.upper() in cls._get_map()

    @classmethod
    def clear(cls) -> None:
        """Clear all ephemeral secrets in the current context."""
        _EPHEMERAL_SECRETS.set({})

    @classmethod
    def snapshot_redacted(cls) -> dict[str, str]:
        """Return safe redacted keys for observability/debugging."""
        return dict.fromkeys(cls._get_map(), "********")

    @classmethod
    @contextmanager
    def scoped_vault(cls, secrets: dict[str, Any]) -> Generator[EphemeralSecretVault, None, None]:
        """Context manager that scopes ephemeral secrets to an execution block."""
        token = _EPHEMERAL_SECRETS.set(dict(cls._get_map()))
        try:
            cls.set_secrets(secrets)
            yield cls()
        finally:
            _EPHEMERAL_SECRETS.reset(token)
