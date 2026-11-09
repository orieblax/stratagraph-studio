"""Unit tests for EphemeralSecretVault and PIIScrubber."""

from pydantic import SecretStr

from src.modules.security_guardrails.infrastructure.pii_scrubber import PIIScrubber
from src.shared.ephemeral_secrets import EphemeralSecretVault


def test_ephemeral_secrets_storage_and_masking() -> None:
    EphemeralSecretVault.set_secrets(
        {
            "DATABRICKS_TOKEN": "dapi_secret_token_12345",
            "OPENAI_API_KEY": "sk-proj-testkey98765432101234567890",
        }
    )

    assert EphemeralSecretVault.has_secret("DATABRICKS_TOKEN") is True
    assert EphemeralSecretVault.has_secret("OPENAI_API_KEY") is True
    assert EphemeralSecretVault.has_secret("NON_EXISTENT") is False

    secret_obj = EphemeralSecretVault.get_secret("DATABRICKS_TOKEN")
    assert isinstance(secret_obj, SecretStr)
    # Ensure str() representation never exposes the plaintext token
    assert str(secret_obj) == "**********"

    # Only get_secret_value returns the raw decrypted token
    assert EphemeralSecretVault.get_secret_value("DATABRICKS_TOKEN") == "dapi_secret_token_12345"


def test_scoped_vault_context_isolation() -> None:
    EphemeralSecretVault.set_secrets({"TEST_KEY": "initial_value"})

    with EphemeralSecretVault.scoped_vault({"TEST_KEY": "scoped_override", "TEMP_KEY": "temp_val"}):
        assert EphemeralSecretVault.get_secret_value("TEST_KEY") == "scoped_override"
        assert EphemeralSecretVault.get_secret_value("TEMP_KEY") == "temp_val"

    # Restores original state upon exit
    assert EphemeralSecretVault.get_secret_value("TEST_KEY") == "initial_value"
    assert EphemeralSecretVault.has_secret("TEMP_KEY") is False


def test_pii_scrubber_masks_sensitive_data() -> None:
    scrubber = PIIScrubber()
    sample_text = (
        "User contact: alice.smith@enterprise.org, Phone: 415-555-2671, "
        "SSN: 000-12-3456, using OpenAI key sk-1234567890abcdef1234567890abcdef"
    )

    scrubbed = scrubber.scrub_text(sample_text)

    assert "[REDACTED_EMAIL]" in scrubbed
    assert "alice.smith@enterprise.org" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "415-555-2671" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed
    assert "sk-1234567890" not in scrubbed
