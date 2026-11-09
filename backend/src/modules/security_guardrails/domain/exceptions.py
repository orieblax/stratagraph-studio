"""Security domain exceptions."""

from __future__ import annotations


class SecurityViolationError(Exception):
    """Base exception for all security guardrail violations."""

    pass


class SQLSecurityViolationError(SecurityViolationError):
    """Raised when an executed SQL query fails AST security verification."""

    def __init__(self, message: str, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class SSRFViolationError(SecurityViolationError):
    """Raised when a URL attempts to access private, loopback, or cloud metadata endpoints."""

    def __init__(self, message: str, target_host: str | None = None) -> None:
        super().__init__(message)
        self.target_host = target_host


class FileIngestionSecurityError(SecurityViolationError):
    """Raised when an uploaded file violates MIME type, size limit, or path containment."""

    def __init__(self, message: str, filename: str | None = None) -> None:
        super().__init__(message)
        self.filename = filename


class TaintViolationError(SecurityViolationError):
    """Raised when tainted context triggers an unauthorized side-effect without HITL approval."""

    def __init__(self, message: str, action: str | None = None) -> None:
        super().__init__(message)
        self.action = action
