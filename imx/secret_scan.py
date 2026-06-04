"""Fail-closed secret and policy scanning for IMX boundary artifacts (spec §11.5).

gitmem's fail-closed redaction posture applies to IMX boundary artifacts —
handoff packets, task packets, transcripts, exported summaries, route/memory
overlays, demo artifacts, and policy decisions. Unlike a redactor, this scanner
is fail-closed: when a secret is detected, propagation is *blocked* before the
next model call rather than silently scrubbed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (label, pattern). High-confidence secret patterns only, to avoid blocking
# legitimate packets on false positives.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]{0,8192}?-----END [A-Z ]*PRIVATE KEY-----",
        ),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    ("github_token", re.compile(r"\b(?:gh[opsur]_|github_pat_)[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bx(?:ox[baprsce]|app)-[A-Za-z0-9-]{10,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{12,}")),
    ("authorization_header", re.compile(r"(?i)\bauthorization:\s*\S+")),
    (
        "secret_assignment",
        # Tolerate a quoted key (e.g. JSON `"api_key": "..."`) before the separator.
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?[^\s'\"]{6,}"
        ),
    ),
]

# Keys whose string value is treated as a secret regardless of value shape, so a
# packet field like {"api_key": "AbCd1234EfGh"} is caught even though the value
# alone carries no key=value context (scan_object scans values in isolation).
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|private[_-]?key)\b"
)


@dataclass(frozen=True)
class Finding:
    """A detected secret: its pattern label and the JSON path where it occurred."""

    label: str
    location: str


class SecretFoundError(ValueError):
    """Raised when a boundary artifact contains secrets (fail-closed block)."""

    def __init__(self, findings: list[Finding]) -> None:
        self.findings = findings
        labels = ", ".join(sorted({f.label for f in findings}))
        locations = ", ".join(f.location for f in findings)
        super().__init__(
            f"secret detected in boundary artifact: {labels} at {locations}"
        )


def scan_text(text: str) -> list[str]:
    """Return the labels of any secrets detected in ``text``."""
    found: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def scan_object(obj: object, *, path: str = "<root>") -> list[Finding]:
    """Recursively scan string values in a dict/list/str for secrets."""
    findings: list[Finding] = []
    if isinstance(obj, str):
        for label in scan_text(obj):
            findings.append(Finding(label=label, location=path))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            # Key-aware check: a secret-named key whose value is a contiguous
            # token (no whitespace, length >= 8) is treated as a secret even
            # though the value string carries no key=value context on its own.
            if (
                isinstance(value, str)
                and _SECRET_KEY_RE.search(str(key))
                and len(value.strip()) >= 8
                and not any(c.isspace() for c in value.strip())
            ):
                findings.append(Finding(label="secret_value", location=child))
            findings.extend(scan_object(value, path=child))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            findings.extend(scan_object(value, path=f"{path}[{i}]"))
    return findings


def assert_clean(obj: object, *, label: str = "<root>") -> None:
    """Raise SecretFoundError if ``obj`` contains any secrets (fail-closed)."""
    findings = scan_object(obj, path=label)
    if findings:
        raise SecretFoundError(findings)
