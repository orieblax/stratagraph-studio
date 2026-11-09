"""PII and sensitive secret data scrubber with Luhn checksum validation."""

from __future__ import annotations

import re

from src.modules.security_guardrails.domain.interfaces import IPIIScrubber

_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
_PHONE_REGEX = re.compile(r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b")
_SSN_REGEX = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_API_KEY_REGEX = re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|dapi[a-f0-9]{32,}|ghp_[a-zA-Z0-9]{36,})\b")
_JWT_REGEX = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")
_CREDIT_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _is_luhn_valid(card_number_str: str) -> bool:
    """Validate numeric string using Luhn algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += digit

    return checksum % 10 == 0


class PIIScrubber(IPIIScrubber):
    """Scans and masks PII, national identifiers, and credentials."""

    def scrub_text(self, text: str) -> str:
        """Replace all detected PII entities and secrets with redaction placeholders."""
        if not text:
            return text

        scrubbed = text

        # 1. API Keys & Secrets
        scrubbed = _API_KEY_REGEX.sub("[REDACTED_API_KEY]", scrubbed)
        scrubbed = _JWT_REGEX.sub("[REDACTED_JWT]", scrubbed)

        # 2. Email addresses
        scrubbed = _EMAIL_REGEX.sub("[REDACTED_EMAIL]", scrubbed)

        # 3. Social Security Numbers
        scrubbed = _SSN_REGEX.sub("[REDACTED_SSN]", scrubbed)

        # 4. Phone numbers
        scrubbed = _PHONE_REGEX.sub("[REDACTED_PHONE]", scrubbed)

        # 5. Credit Cards (with Luhn check)
        def _replace_cc(match: re.Match[str]) -> str:
            raw = match.group(0)
            clean_digits = re.sub(r"\D", "", raw)
            if _is_luhn_valid(clean_digits):
                return "[REDACTED_CREDIT_CARD]"
            return raw

        scrubbed = _CREDIT_CARD_CANDIDATE.sub(_replace_cc, scrubbed)

        return scrubbed

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any recognizable PII or secret tokens."""
        if not text:
            return False

        if _EMAIL_REGEX.search(text) or _PHONE_REGEX.search(text) or _SSN_REGEX.search(text):
            return True

        if _API_KEY_REGEX.search(text) or _JWT_REGEX.search(text):
            return True

        for match in _CREDIT_CARD_CANDIDATE.finditer(text):
            clean_digits = re.sub(r"\D", "", match.group(0))
            if _is_luhn_valid(clean_digits):
                return True

        return False
