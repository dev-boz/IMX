"""Tests for imx.context_artifacts — ContextSource, ContextManifest, LintFinding,
write_context_manifest, write_context_sources, write_context_lint, lint_context_sources."""
from __future__ import annotations

import json

import pytest

from imx.context_artifacts import (
    ContextManifest,
    ContextSource,
    LintFinding,
    lint_context_sources,
    write_context_lint,
    write_context_manifest,
    write_context_sources,
)


# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------


def test_context_source_defaults():
    s = ContextSource(kind="role_card", ref="role.md")
    assert s.token_estimate == 0
    assert s.position == "top"
    assert s.reason == ""


def test_context_manifest_defaults():
    m = ContextManifest()
    assert m.schema_version == "0.6"
    assert m.budget_tokens == 16384
    assert m.sources == []
    assert m.total_tokens == 0


def test_lint_finding_defaults():
    f = LintFinding(kind="clash", source_ref="ref.md", message="dup")
    assert f.severity == "warning"


# ---------------------------------------------------------------------------
# write_context_manifest
# ---------------------------------------------------------------------------


def test_write_context_manifest_returns_path(tmp_path):
    manifest = ContextManifest(task_id="t1", agent="agent-a")
    path = write_context_manifest(manifest, tmp_path)
    assert path == tmp_path / "manifest.json"


def test_write_context_manifest_file_exists(tmp_path):
    manifest = ContextManifest(task_id="t2")
    write_context_manifest(manifest, tmp_path)
    assert (tmp_path / "manifest.json").exists()


def test_write_context_manifest_valid_json(tmp_path):
    manifest = ContextManifest(task_id="t3", agent="ag", total_tokens=500)
    write_context_manifest(manifest, tmp_path)
    data = json.loads((tmp_path / "manifest.json").read_text())
    assert data["task_id"] == "t3"
    assert data["agent"] == "ag"
    assert data["total_tokens"] == 500
    assert data["schema_version"] == "0.6"


def test_write_context_manifest_no_tmp_leftover(tmp_path):
    manifest = ContextManifest(task_id="t4")
    write_context_manifest(manifest, tmp_path)
    assert not (tmp_path / "manifest.tmp").exists()


def test_write_context_manifest_creates_parent_dirs(tmp_path):
    nested = tmp_path / "nested" / "ctx"
    manifest = ContextManifest(task_id="t5")
    path = write_context_manifest(manifest, nested)
    assert path.exists()


def test_write_context_manifest_round_trips_sources(tmp_path):
    src = ContextSource(kind="conventions", ref="conv.md", token_estimate=100)
    manifest = ContextManifest(task_id="t6", sources=[src])
    write_context_manifest(manifest, tmp_path)
    data = json.loads((tmp_path / "manifest.json").read_text())
    assert len(data["sources"]) == 1
    assert data["sources"][0]["kind"] == "conventions"


# ---------------------------------------------------------------------------
# write_context_sources
# ---------------------------------------------------------------------------


def test_write_context_sources_returns_path(tmp_path):
    path = write_context_sources([], tmp_path)
    assert path == tmp_path / "sources.json"


def test_write_context_sources_file_exists(tmp_path):
    sources = [ContextSource(kind="role_card", ref="role.md")]
    write_context_sources(sources, tmp_path)
    assert (tmp_path / "sources.json").exists()


def test_write_context_sources_schema_version(tmp_path):
    write_context_sources([], tmp_path)
    data = json.loads((tmp_path / "sources.json").read_text())
    assert data["schema_version"] == "0.6"


def test_write_context_sources_round_trips_data(tmp_path):
    sources = [
        ContextSource(kind="role_card", ref="role.md", token_estimate=200, position="top"),
        ContextSource(kind="conventions", ref="conv.md", token_estimate=50, position="bottom"),
    ]
    write_context_sources(sources, tmp_path)
    data = json.loads((tmp_path / "sources.json").read_text())
    assert len(data["sources"]) == 2
    assert data["sources"][0]["ref"] == "role.md"
    assert data["sources"][1]["position"] == "bottom"


def test_write_context_sources_empty_list(tmp_path):
    write_context_sources([], tmp_path)
    data = json.loads((tmp_path / "sources.json").read_text())
    assert data["sources"] == []


def test_write_context_sources_no_tmp_leftover(tmp_path):
    write_context_sources([], tmp_path)
    assert not (tmp_path / "sources.tmp").exists()


def test_write_context_sources_creates_parent_dirs(tmp_path):
    nested = tmp_path / "deep" / "output"
    path = write_context_sources([], nested)
    assert path.exists()


# ---------------------------------------------------------------------------
# write_context_lint
# ---------------------------------------------------------------------------


def test_write_context_lint_returns_path(tmp_path):
    path = write_context_lint([], tmp_path)
    assert path == tmp_path / "lint.json"


def test_write_context_lint_file_exists(tmp_path):
    write_context_lint([], tmp_path)
    assert (tmp_path / "lint.json").exists()


def test_write_context_lint_schema_version(tmp_path):
    write_context_lint([], tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    assert data["schema_version"] == "0.6"


def test_write_context_lint_empty_findings(tmp_path):
    write_context_lint([], tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    assert data["finding_count"] == 0
    assert data["has_errors"] is False
    assert data["findings"] == []


def test_write_context_lint_finding_count(tmp_path):
    findings = [
        LintFinding(kind="clash", source_ref="a.md", message="dup"),
        LintFinding(kind="distraction", source_ref="b.md", message="too big"),
    ]
    write_context_lint(findings, tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    assert data["finding_count"] == 2


def test_write_context_lint_has_errors_true(tmp_path):
    findings = [LintFinding(kind="confusion", source_ref="x", message="empty ref", severity="error")]
    write_context_lint(findings, tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    assert data["has_errors"] is True


def test_write_context_lint_has_errors_false_when_only_warnings(tmp_path):
    findings = [LintFinding(kind="clash", source_ref="x", message="dup", severity="warning")]
    write_context_lint(findings, tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    assert data["has_errors"] is False


def test_write_context_lint_round_trips_finding_fields(tmp_path):
    f = LintFinding(kind="distraction", source_ref="big.md", message="too large", severity="warning")
    write_context_lint([f], tmp_path)
    data = json.loads((tmp_path / "lint.json").read_text())
    entry = data["findings"][0]
    assert entry["kind"] == "distraction"
    assert entry["source_ref"] == "big.md"
    assert entry["message"] == "too large"
    assert entry["severity"] == "warning"


def test_write_context_lint_no_tmp_leftover(tmp_path):
    write_context_lint([], tmp_path)
    assert not (tmp_path / "lint.tmp").exists()


def test_write_context_lint_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    path = write_context_lint([], nested)
    assert path.exists()


# ---------------------------------------------------------------------------
# lint_context_sources
# ---------------------------------------------------------------------------


def test_lint_clean_sources_no_findings():
    sources = [
        ContextSource(kind="role_card", ref="role.md", token_estimate=100),
        ContextSource(kind="conventions", ref="conv.md", token_estimate=200),
    ]
    findings = lint_context_sources(sources)
    assert findings == []


def test_lint_empty_input_no_findings():
    assert lint_context_sources([]) == []


def test_lint_empty_ref_produces_confusion_error():
    sources = [ContextSource(kind="role_card", ref="")]
    findings = lint_context_sources(sources)
    assert len(findings) == 1
    assert findings[0].kind == "confusion"
    assert findings[0].severity == "error"
    assert "role_card" in findings[0].message


def test_lint_empty_ref_source_ref_is_kind():
    sources = [ContextSource(kind="attention_refresh", ref="")]
    findings = lint_context_sources(sources)
    assert findings[0].source_ref == "attention_refresh"


def test_lint_duplicate_kind_produces_clash_warning():
    sources = [
        ContextSource(kind="conventions", ref="conv1.md"),
        ContextSource(kind="conventions", ref="conv2.md"),
    ]
    findings = lint_context_sources(sources)
    clash = [f for f in findings if f.kind == "clash"]
    assert len(clash) == 1
    assert clash[0].severity == "warning"


def test_lint_duplicate_kind_references_first_seen_ref():
    sources = [
        ContextSource(kind="conventions", ref="first.md"),
        ContextSource(kind="conventions", ref="second.md"),
    ]
    findings = lint_context_sources(sources)
    clash = [f for f in findings if f.kind == "clash"]
    assert "first.md" in clash[0].message


def test_lint_duplicate_kind_source_ref_is_duplicate_ref():
    sources = [
        ContextSource(kind="conventions", ref="first.md"),
        ContextSource(kind="conventions", ref="second.md"),
    ]
    findings = lint_context_sources(sources)
    clash = [f for f in findings if f.kind == "clash"]
    assert clash[0].source_ref == "second.md"


def test_lint_token_over_budget_produces_distraction_warning():
    sources = [ContextSource(kind="big_doc", ref="big.md", token_estimate=16385)]
    findings = lint_context_sources(sources)
    assert len(findings) == 1
    assert findings[0].kind == "distraction"
    assert findings[0].severity == "warning"
    assert "big.md" in findings[0].message


def test_lint_token_exactly_at_budget_no_distraction():
    # Strict `>` means 16384 is NOT over budget
    sources = [ContextSource(kind="big_doc", ref="exact.md", token_estimate=16384)]
    findings = lint_context_sources(sources)
    distraction = [f for f in findings if f.kind == "distraction"]
    assert distraction == []


def test_lint_token_one_under_budget_no_distraction():
    sources = [ContextSource(kind="big_doc", ref="fine.md", token_estimate=16383)]
    findings = lint_context_sources(sources)
    assert findings == []


def test_lint_multiple_findings_on_one_source():
    # Empty ref + duplicate kind both fire on the same source
    sources = [
        ContextSource(kind="role_card", ref="first.md"),
        ContextSource(kind="role_card", ref=""),   # empty ref (confusion) + duplicate kind (clash)
    ]
    findings = lint_context_sources(sources)
    kinds = {f.kind for f in findings}
    assert "confusion" in kinds
    assert "clash" in kinds


def test_lint_multiple_duplicates():
    sources = [
        ContextSource(kind="conventions", ref="a.md"),
        ContextSource(kind="conventions", ref="b.md"),
        ContextSource(kind="conventions", ref="c.md"),
    ]
    findings = lint_context_sources(sources)
    clashes = [f for f in findings if f.kind == "clash"]
    assert len(clashes) == 2


def test_lint_returns_list_of_lint_finding_instances():
    sources = [ContextSource(kind="role_card", ref="")]
    findings = lint_context_sources(sources)
    for f in findings:
        assert isinstance(f, LintFinding)


def test_lint_distraction_message_contains_token_count():
    sources = [ContextSource(kind="big_doc", ref="huge.md", token_estimate=20000)]
    findings = lint_context_sources(sources)
    assert "20000" in findings[0].message


def test_lint_combined_empty_ref_and_over_budget():
    # A source can have both empty ref (confusion) and token over budget (distraction)
    # but empty ref uses kind as source_ref, not the empty ref string
    sources = [ContextSource(kind="bloated", ref="", token_estimate=99999)]
    findings = lint_context_sources(sources)
    kinds = {f.kind for f in findings}
    assert "confusion" in kinds
    # distraction fires on source.ref which is "" — still fires
    assert "distraction" in kinds
