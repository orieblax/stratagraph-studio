"""Security guardrails domain models and exceptions."""

from src.modules.security_guardrails.domain.exceptions import (
    FileIngestionSecurityError,
    SecurityViolationError,
    SQLSecurityViolationError,
    SSRFViolationError,
    TaintViolationError,
)
from src.modules.security_guardrails.domain.interfaces import (
    FileValidationResult,
    IFileValidator,
    IPIIScrubber,
    ISpotlighter,
    ISQLValidator,
    ISSRFValidator,
    SpotlightResult,
    SQLValidationResult,
)

__all__ = [
    "SQLValidationResult",
    "SpotlightResult",
    "FileValidationResult",
    "ISQLValidator",
    "ISpotlighter",
    "IPIIScrubber",
    "IFileValidator",
    "ISSRFValidator",
    "SecurityViolationError",
    "SQLSecurityViolationError",
    "SSRFViolationError",
    "FileIngestionSecurityError",
    "TaintViolationError",
]
