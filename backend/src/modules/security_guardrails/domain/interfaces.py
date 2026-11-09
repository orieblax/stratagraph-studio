"""Domain interfaces for security guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SQLValidationResult:
    """Result of SQL AST security analysis."""

    is_valid: bool
    sanitized_sql: str
    ast_type: str
    tables_accessed: list[str]
    has_mutations: bool
    error_message: str | None = None


@dataclass(frozen=True)
class SpotlightResult:
    """Result of wrapping untrusted context in cryptographic tags."""

    spotlighted_text: str
    nonce: str
    tainted: bool
    detected_jailbreaks: list[str]


@dataclass(frozen=True)
class FileValidationResult:
    """Result of file upload and header security validation."""

    is_valid: bool
    mime_type: str
    byte_size: int
    canonical_path: str
    error_message: str | None = None


class ISQLValidator(Protocol):
    """Protocol for AST-based SQL security verification."""

    def validate_and_rewrite(
        self,
        sql: str,
        *,
        dialect: str = "postgres",
        read_only: bool = True,
        allowed_tables: set[str] | None = None,
        max_limit: int = 100,
    ) -> SQLValidationResult: ...


class ISpotlighter(Protocol):
    """Protocol for cryptographic spotlighting and taint tracking."""

    def wrap_untrusted_content(self, raw_content: str, source_id: str = "") -> SpotlightResult: ...

    def verify_and_unwrap(self, wrapped_text: str, nonce: str) -> str: ...


class IPIIScrubber(Protocol):
    """Protocol for scanning and masking PII and credentials."""

    def scrub_text(self, text: str) -> str: ...

    def contains_pii(self, text: str) -> bool: ...


class IFileValidator(Protocol):
    """Protocol for file upload and path traversal security checks."""

    def validate_file(
        self,
        file_bytes: bytes,
        filename: str,
        destination_dir: str,
        max_bytes: int = 25 * 1024 * 1024,
    ) -> FileValidationResult: ...


class ISSRFValidator(Protocol):
    """Protocol for blocking SSRF and private network access."""

    def validate_url(self, url: str) -> tuple[bool, str | None]: ...
