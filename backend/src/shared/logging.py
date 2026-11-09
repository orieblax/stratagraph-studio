"""Structured logging configuration with automatic PII, Secret and JWT redaction."""

from __future__ import annotations

import contextvars
import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# Context variables for tracing correlation
correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
langsmith_run_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "langsmith_run_id", default=None
)

# Common sensitive regex patterns
_SECRET_PATTERNS = [
    # OpenAI & generic API keys
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "[REDACTED_API_KEY]"),
    # Databricks personal access tokens
    (re.compile(r"dapi[a-f0-9]{32,}"), "[REDACTED_DATABRICKS_TOKEN]"),
    # JWT tokens
    (re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), "[REDACTED_JWT]"),
    # Credit Card Numbers (13-19 digits with spaces/dashes)
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CREDIT_CARD]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[REDACTED_EMAIL]"),
    # US Social Security Numbers
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
]


def _scrub_string(val: str) -> str:
    res = val
    for pattern, replacement in _SECRET_PATTERNS:
        res = pattern.sub(replacement, res)
    return res


def _recursive_scrub(data: Any) -> Any:
    if isinstance(data, str):
        return _scrub_string(data)
    elif isinstance(data, dict):
        scrubbed: dict[Any, Any] = {}
        for k, v in data.items():
            key_str = str(k).lower()
            if any(s in key_str for s in ("token", "secret", "password", "key", "auth")):
                scrubbed[k] = "[REDACTED_SENSITIVE_FIELD]"
            else:
                scrubbed[k] = _recursive_scrub(v)
        return scrubbed
    elif isinstance(data, list):
        return [_recursive_scrub(item) for item in data]
    return data


def redact_secrets_and_pii_processor(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Processor to scrub credentials, JWTs, and PII before outputting logs."""
    return _recursive_scrub(event_dict)  # type: ignore[no-any-return]


def inject_tracing_context_processor(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Processor to enrich every log entry with correlation_id and langsmith_run_id."""
    cid = correlation_id_ctx.get()
    if cid and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid

    l_run_id = langsmith_run_id_ctx.get()
    if l_run_id and "langsmith_run_id" not in event_dict:
        event_dict["langsmith_run_id"] = l_run_id

    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Initialize structured logging pipeline with redaction and context injection."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        inject_tracing_context_processor,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_secrets_and_pii_processor,
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance bound to module name."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
