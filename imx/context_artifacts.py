"""Context artifact writing per IMX spec §14.2 (context/manifest.json + sources.json + lint.json)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ContextSource:
    kind: str            # gitmem_procedures, conventions, role_card, attention_refresh, etc.
    ref: str             # path or query string
    token_estimate: int = 0
    position: str = "top"  # top, system, bottom
    reason: str = ""


@dataclass
class ContextManifest:
    schema_version: str = "0.6"
    task_id: str = ""
    agent: str = ""
    selected_at: str = ""   # ISO8601
    sources: list = field(default_factory=list)
    total_tokens: int = 0
    budget_tokens: int = 16384


@dataclass
class LintFinding:
    kind: str        # "poisoning", "distraction", "confusion", "clash"
    source_ref: str
    message: str
    severity: str = "warning"  # "warning" or "error"


def _atomic_write(path: Path, data: dict) -> Path:
    """Atomically write a dict as JSON to path. Creates parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)
    return path


def write_context_manifest(manifest: ContextManifest, output_dir: Path) -> Path:
    """Write manifest as JSON to {output_dir}/manifest.json. Returns path."""
    data = asdict(manifest)
    return _atomic_write(output_dir / "manifest.json", data)


def write_context_sources(sources: list[ContextSource], output_dir: Path) -> Path:
    """Write sources list as JSON to {output_dir}/sources.json. Returns path."""
    data = {
        "schema_version": "0.6",
        "sources": [asdict(s) for s in sources],
    }
    return _atomic_write(output_dir / "sources.json", data)


def write_context_lint(findings: list[LintFinding], output_dir: Path) -> Path:
    """Write lint findings as JSON to {output_dir}/lint.json. Returns path."""
    data = {
        "schema_version": "0.6",
        "finding_count": len(findings),
        "has_errors": any(f.severity == "error" for f in findings),
        "findings": [asdict(f) for f in findings],
    }
    return _atomic_write(output_dir / "lint.json", data)


def lint_context_sources(sources: list[ContextSource]) -> list[LintFinding]:
    """Check sources for common context engineering problems.

    Checks:
    - Duplicate kinds → clash
    - Token estimate exceeds budget (16384) → distraction warning
    - Source with empty ref → confusion error
    """
    findings: list[LintFinding] = []
    seen_kinds: dict[str, str] = {}  # kind -> first ref

    budget = 16384

    for source in sources:
        # Empty ref check
        if not source.ref:
            findings.append(
                LintFinding(
                    kind="confusion",
                    source_ref=source.kind,
                    message=f"Source of kind '{source.kind}' has an empty ref.",
                    severity="error",
                )
            )

        # Duplicate kind check
        if source.kind in seen_kinds:
            findings.append(
                LintFinding(
                    kind="clash",
                    source_ref=source.ref,
                    message=(
                        f"Duplicate kind '{source.kind}': also seen at ref "
                        f"'{seen_kinds[source.kind]}'."
                    ),
                    severity="warning",
                )
            )
        else:
            seen_kinds[source.kind] = source.ref

        # Token budget check
        if source.token_estimate > budget:
            findings.append(
                LintFinding(
                    kind="distraction",
                    source_ref=source.ref,
                    message=(
                        f"Source '{source.ref}' token estimate {source.token_estimate} "
                        f"exceeds budget {budget}."
                    ),
                    severity="warning",
                )
            )

    return findings
