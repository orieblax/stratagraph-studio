"""Pytest fixtures and environment configuration."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Ensure src is on python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_minimum_32_characters_long_for_ci_suite"
os.environ["SAFE_UPLOAD_DIR"] = "/tmp/safe_uploads"


def _clear_shared_state() -> None:
    """Reset in-memory ephemeral secrets and L1 semantic cache between tests."""
    from src.modules.cost_optimization.infrastructure.semantic_cache import TwoTierPgVectorCache
    from src.shared.ephemeral_secrets import EphemeralSecretVault

    EphemeralSecretVault.clear()
    TwoTierPgVectorCache._shared_mem_cache.clear()


@pytest.fixture(autouse=True)
def clean_ephemeral_vault() -> Iterator[None]:
    """Ensure EphemeralSecretVault and in-memory L1 cache are pristine before/after each test."""
    _clear_shared_state()
    yield
    _clear_shared_state()
