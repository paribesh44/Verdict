"""PII redaction for local-only query processing."""

from __future__ import annotations

import re
from typing import List, Tuple


# Patterns for common PII and credentials (placeholders are non-reversible for safety).
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
SSN_PATTERN = re.compile(
    r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
)
# Generic API key / secret patterns (common prefixes and long hex/base64-like strings).
CREDENTIAL_PATTERN = re.compile(
    r"\b(?:api[_-]?key|apikey|secret|password|passwd|pwd|token|auth)[\s:=]+[\w\-./+=]{16,}\b",
    re.IGNORECASE
)
# Standalone long alphanumeric tokens that might be keys (e.g. sk-...).
STANDALONE_SECRET_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{20,}|[A-Za-z0-9+/]{32,}={0,2})\b"
)


class PIIRedactor:
    """Scrubs emails, SSNs, and credentials from text. Uses fixed placeholders."""

    PLACEHOLDER_EMAIL = "[EMAIL_REDACTED]"
    PLACEHOLDER_SSN = "[SSN_REDACTED]"
    PLACEHOLDER_CREDENTIAL = "[CREDENTIAL_REDACTED]"

    def __init__(self, allowlist: List[str] | None = None) -> None:
        self.allowlist = set(allowlist or [])

    def redact(self, text: str) -> str:
        if not text:
            return text
        out = text
        out = EMAIL_PATTERN.sub(self.PLACEHOLDER_EMAIL, out)
        out = SSN_PATTERN.sub(self.PLACEHOLDER_SSN, out)
        out = CREDENTIAL_PATTERN.sub(self.PLACEHOLDER_CREDENTIAL, out)
        # Optionally tone down standalone secret replacement to avoid over-redacting normal tokens
        out = STANDALONE_SECRET_PATTERN.sub(self.PLACEHOLDER_CREDENTIAL, out)
        return out

    def redact_with_spans(self, text: str) -> Tuple[str, List[Tuple[int, int, str]]]:
        """Returns redacted string and list of (start, end, replacement) for audit."""
        if not text:
            return text, []
        spans: List[Tuple[int, int, str]] = []
        out = text

        for m in EMAIL_PATTERN.finditer(text):
            spans.append((m.start(), m.end(), self.PLACEHOLDER_EMAIL))
        out = EMAIL_PATTERN.sub(self.PLACEHOLDER_EMAIL, out)

        for m in SSN_PATTERN.finditer(out):
            spans.append((m.start(), m.end(), self.PLACEHOLDER_SSN))
        out = SSN_PATTERN.sub(self.PLACEHOLDER_SSN, out)

        for m in CREDENTIAL_PATTERN.finditer(out):
            spans.append((m.start(), m.end(), self.PLACEHOLDER_CREDENTIAL))
        out = CREDENTIAL_PATTERN.sub(self.PLACEHOLDER_CREDENTIAL, out)

        for m in STANDALONE_SECRET_PATTERN.finditer(out):
            spans.append((m.start(), m.end(), self.PLACEHOLDER_CREDENTIAL))
        out = STANDALONE_SECRET_PATTERN.sub(self.PLACEHOLDER_CREDENTIAL, out)

        return out, spans
