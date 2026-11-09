"""Unit tests for FileSecurityValidator and SSRFValidator."""

import io
import zipfile

import pytest

from src.modules.security_guardrails.domain.exceptions import FileIngestionSecurityError
from src.modules.security_guardrails.infrastructure.file_ssrf_validator import (
    FileSecurityValidator,
    SSRFValidator,
)


@pytest.fixture
def file_validator() -> FileSecurityValidator:
    return FileSecurityValidator()


@pytest.fixture
def ssrf_validator() -> SSRFValidator:
    return SSRFValidator()


def test_file_validator_accepts_valid_text(
    file_validator: FileSecurityValidator, tmp_path: pytest.TempPathFactory
) -> None:
    safe_dir = str(tmp_path)
    content = b"# Architecture Overview\nThis is a valid markdown document."
    res = file_validator.validate_file(content, "docs.md", destination_dir=safe_dir)

    assert res.is_valid is True
    assert res.mime_type == "text/markdown"
    assert res.byte_size == len(content)
    assert res.canonical_path.startswith(safe_dir)


def test_file_validator_rejects_empty_file(
    file_validator: FileSecurityValidator, tmp_path: pytest.TempPathFactory
) -> None:
    with pytest.raises(FileIngestionSecurityError, match="Empty file upload"):
        file_validator.validate_file(b"", "empty.txt", destination_dir=str(tmp_path))


def test_file_validator_rejects_oversized_file(
    file_validator: FileSecurityValidator, tmp_path: pytest.TempPathFactory
) -> None:
    data = b"x" * 2000
    with pytest.raises(FileIngestionSecurityError, match="exceeds maximum allowable limit"):
        file_validator.validate_file(
            data, "large.txt", destination_dir=str(tmp_path), max_bytes=1000
        )


def test_file_validator_neutralizes_path_traversal(
    file_validator: FileSecurityValidator, tmp_path: pytest.TempPathFactory
) -> None:
    safe_dir = str(tmp_path)
    content = b"Safe text payload."
    # Attack payload trying to escape to parent directory
    malicious_filename = "../../../etc/passwd"
    res = file_validator.validate_file(content, malicious_filename, destination_dir=safe_dir)

    assert res.is_valid is True
    # The filename was sanitized and stays strictly inside safe_dir
    assert res.canonical_path.startswith(safe_dir)
    assert ".." not in res.canonical_path


def test_file_validator_detects_zip_bomb(
    file_validator: FileSecurityValidator, tmp_path: pytest.TempPathFactory
) -> None:
    # Construct a high-compression zip payload (e.g. 1MB of zeroes compressed to ~1KB)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 2 MB of zeroes compressed
        zf.writestr("huge_file.txt", b"0" * (2 * 1024 * 1024))

    zip_bytes = buf.getvalue()
    with pytest.raises(FileIngestionSecurityError, match="Potential Zip Bomb detected"):
        file_validator.validate_file(zip_bytes, "archive.docx", destination_dir=str(tmp_path))


def test_ssrf_validator_blocks_loopback_and_metadata(ssrf_validator: SSRFValidator) -> None:
    # Loopback IP
    valid, err = ssrf_validator.validate_url("http://127.0.0.1:8080/admin")
    assert valid is False
    assert "blocked" in str(err).lower()

    # Cloud Metadata IP
    valid, err = ssrf_validator.validate_url("http://169.254.169.254/latest/meta-data/")
    assert valid is False
    assert "blocked" in str(err).lower()

    # Cloud metadata hostname
    valid, err = ssrf_validator.validate_url("http://metadata.google.internal/computeMetadata/v1/")
    assert valid is False
    assert "blocked" in str(err).lower()


def test_ssrf_validator_blocks_private_networks(ssrf_validator: SSRFValidator) -> None:
    # 10.0.0.0/8
    valid, _ = ssrf_validator.validate_url("http://10.20.30.40/metrics")
    assert valid is False

    # 192.168.0.0/16
    valid, _ = ssrf_validator.validate_url("http://192.168.1.1/setup")
    assert valid is False


def test_ssrf_validator_blocks_forbidden_schemes(ssrf_validator: SSRFValidator) -> None:
    valid, err = ssrf_validator.validate_url("file:///etc/shadow")
    assert valid is False
    assert "forbidden" in str(err).lower()
