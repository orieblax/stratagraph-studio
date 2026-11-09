"""Pytest fixtures and environment configuration."""

import os
import sys
from pathlib import Path

import pytest

# Ensure src is on python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_minimum_32_characters_long_for_ci_suite"
os.environ["SAFE_UPLOAD_DIR"] = "/tmp/safe_uploads"


@pytest.fixture(autouse=True)
def clean_ephemeral_vault() -> None:
    """Ensure EphemeralSecretVault is pristine before and after every test."""
    from src.shared.ephemeral_secrets import EphemeralSecretVault

    EphemeralSecretVault.clear()
    yield
    EphemeralSecretVault.clear()
