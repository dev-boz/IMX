"""Tests for imx.control_intents — ControlIntent, write_control_intent,
read_pending_intents, mark_intent_acked, append_control_span,
translate_intent_to_harness_command."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from imx.control_intents import (
    INTENT_KINDS,
    ControlIntent,
    append_control_span,
    mark_intent_acked,
    read_pending_intents,
    translate_intent_to_harness_command,
    write_control_intent,
)


# ---------------------------------------------------------------------------
# ControlIntent dataclass
# ---------------------------------------------------------------------------


def test_control_intent_default_schema_version():
    """Default schema_version must be '0.6'."""
    ci = ControlIntent()
    assert ci.schema_version == "0.6"


def test_control_intent_fields_default_to_empty_string():
    """All non-schema-version fields must default to ''."""
    ci = ControlIntent()
    for field in ("intent", "task_id", "session_id", "target_model_band", "reason", "requested_by", "ts"):
        assert getattr(ci, field) == ""


def test_control_intent_custom_fields():
    """Fields passed at construction must be stored correctly."""
    ci = ControlIntent(intent="compact", task_id="t1", session_id="s1", requested_by="ctrl-node")
    assert ci.intent == "compact"
    assert ci.task_id == "t1"
    assert ci.session_id == "s1"
    assert ci.requested_by == "ctrl-node"


def test_intent_kinds_contains_all_six():
    """INTENT_KINDS must contain exactly the six spec-mandated kinds."""
    assert INTENT_KINDS == frozenset({"compact", "rewind", "switch_model", "clear", "pause", "resume"})


# ---------------------------------------------------------------------------
# write_control_intent
# ---------------------------------------------------------------------------


def test_write_control_intent_creates_file(tmp_path):
    """write_control_intent must create an .intent.json file."""
    ci = ControlIntent(intent="compact", task_id="t1", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".json"
    assert ".intent.json" in path.name


def test_write_control_intent_returns_correct_path(tmp_path):
    """Returned path must point to a file whose name encodes intent kind and task_id."""
    ci = ControlIntent(intent="clear", task_id="abc123", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    assert "clear" in path.name
    assert "abc123" in path.name


def test_write_control_intent_content_is_valid_json(tmp_path):
    """The written file must contain valid JSON."""
    ci = ControlIntent(intent="pause", task_id="t2", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_write_control_intent_stamps_ts_when_empty(tmp_path):
    """ts must be stamped automatically when not set."""
    ci = ControlIntent(intent="resume", task_id="t3", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ts"].endswith("Z")


def test_write_control_intent_preserves_existing_ts(tmp_path):
    """An explicit ts value must not be overwritten."""
    ci = ControlIntent(intent="rewind", task_id="t4", session_id="s1", ts="2025-01-01T00:00:00Z")
    path = write_control_intent(ci, intents_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ts"] == "2025-01-01T00:00:00Z"


def test_write_control_intent_creates_intents_dir(tmp_path):
    """intents_dir is created recursively when it does not exist."""
    nested = tmp_path / "deep" / "nested"
    ci = ControlIntent(intent="compact", task_id="t5", session_id="s1")
    write_control_intent(ci, intents_dir=nested)
    assert nested.is_dir()


def test_write_control_intent_uses_uuid_when_task_id_empty(tmp_path):
    """When task_id is empty, a random hex fragment is used in the filename."""
    ci = ControlIntent(intent="clear", task_id="", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    # Filename is clear-<8 hex chars>.intent.json
    name = path.name
    assert name.startswith("clear-")
    assert name.endswith(".intent.json")
    hex_part = name[len("clear-"):name.index(".intent.json")]
    assert len(hex_part) == 8
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_write_control_intent_schema_version_in_file(tmp_path):
    """schema_version must appear in the serialised file."""
    ci = ControlIntent(intent="compact", task_id="t6", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.6"


# ---------------------------------------------------------------------------
# read_pending_intents
# ---------------------------------------------------------------------------


def test_read_pending_intents_empty_when_dir_missing(tmp_path):
    """read_pending_intents must return [] when the directory does not exist."""
    result = read_pending_intents("no-such-session", intents_dir=tmp_path / "ghost")
    assert result == []


def test_read_pending_intents_empty_when_no_files(tmp_path):
    """read_pending_intents must return [] when the directory is empty."""
    intents_dir = tmp_path / "intents"
    intents_dir.mkdir()
    result = read_pending_intents("s1", intents_dir=intents_dir)
    assert result == []


def test_read_pending_intents_returns_written_intent(tmp_path):
    """An intent written with write_control_intent must be returned by read_pending_intents."""
    ci = ControlIntent(intent="compact", task_id="t1", session_id="s1")
    write_control_intent(ci, intents_dir=tmp_path)
    results = read_pending_intents("s1", intents_dir=tmp_path)
    assert len(results) == 1
    assert results[0].intent == "compact"
    assert results[0].task_id == "t1"


def test_read_pending_intents_returns_control_intent_objects(tmp_path):
    """All returned objects must be ControlIntent instances."""
    ci = ControlIntent(intent="clear", task_id="t2", session_id="s1")
    write_control_intent(ci, intents_dir=tmp_path)
    results = read_pending_intents("s1", intents_dir=tmp_path)
    for r in results:
        assert isinstance(r, ControlIntent)


def test_read_pending_intents_multiple_files(tmp_path):
    """All intent files in a directory must be returned."""
    for kind in ("compact", "clear", "pause"):
        ci = ControlIntent(intent=kind, task_id=kind, session_id="s1")
        write_control_intent(ci, intents_dir=tmp_path)
    results = read_pending_intents("s1", intents_dir=tmp_path)
    assert len(results) == 3


def test_read_pending_intents_sorted_by_ts(tmp_path):
    """Results must be sorted by ts ascending."""
    for ts, kind, tid in [
        ("2025-01-03T00:00:00Z", "clear", "c"),
        ("2025-01-01T00:00:00Z", "compact", "a"),
        ("2025-01-02T00:00:00Z", "pause", "b"),
    ]:
        ci = ControlIntent(intent=kind, task_id=tid, session_id="s1", ts=ts)
        write_control_intent(ci, intents_dir=tmp_path)
    results = read_pending_intents("s1", intents_dir=tmp_path)
    assert [r.ts for r in results] == [
        "2025-01-01T00:00:00Z",
        "2025-01-02T00:00:00Z",
        "2025-01-03T00:00:00Z",
    ]


def test_read_pending_intents_skips_acked_files(tmp_path):
    """Files ending in .intent.acked.json must NOT be returned."""
    ci = ControlIntent(intent="compact", task_id="t1", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    mark_intent_acked(path)
    results = read_pending_intents("s1", intents_dir=tmp_path)
    assert results == []


def test_read_pending_intents_ignores_malformed_files(tmp_path):
    """Corrupted / non-JSON files must be skipped without raising."""
    bad = tmp_path / "bad.intent.json"
    bad.write_text("not json at all", encoding="utf-8")
    # Should not raise and should return an empty list
    results = read_pending_intents("s1", intents_dir=tmp_path)
    assert results == []


# ---------------------------------------------------------------------------
# mark_intent_acked
# ---------------------------------------------------------------------------


def test_mark_intent_acked_renames_file(tmp_path):
    """mark_intent_acked must rename *.intent.json to *.intent.acked.json."""
    ci = ControlIntent(intent="compact", task_id="t1", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    mark_intent_acked(path)
    assert not path.exists()
    acked = path.parent / path.name.replace(".intent.json", ".intent.acked.json")
    assert acked.exists()


def test_mark_intent_acked_acked_file_contains_original_data(tmp_path):
    """The acked file must retain the original intent data."""
    ci = ControlIntent(intent="clear", task_id="t2", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    mark_intent_acked(path)
    acked = path.parent / path.name.replace(".intent.json", ".intent.acked.json")
    data = json.loads(acked.read_text(encoding="utf-8"))
    assert data["intent"] == "clear"
    assert data["task_id"] == "t2"


def test_mark_intent_acked_suffix_format(tmp_path):
    """Acked file name must end with .intent.acked.json."""
    ci = ControlIntent(intent="pause", task_id="t3", session_id="s1")
    path = write_control_intent(ci, intents_dir=tmp_path)
    mark_intent_acked(path)
    acked_files = list(path.parent.glob("*.acked.json"))
    assert len(acked_files) == 1
    assert acked_files[0].name.endswith(".intent.acked.json")


# ---------------------------------------------------------------------------
# append_control_span
# ---------------------------------------------------------------------------


def test_append_control_span_creates_file(tmp_path):
    """append_control_span must create control_spans.jsonl."""
    append_control_span({"intent": "compact", "session_id": "s1"}, telemetry_dir=tmp_path)
    assert (tmp_path / "control_spans.jsonl").exists()


def test_append_control_span_valid_json_line(tmp_path):
    """Each span must be written as a valid JSON line."""
    append_control_span({"intent": "clear"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert isinstance(record, dict)


def test_append_control_span_schema_version_defaulted(tmp_path):
    """schema_version must be added automatically if not supplied."""
    append_control_span({"intent": "pause"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["schema_version"] == "0.6"


def test_append_control_span_schema_version_not_overwritten(tmp_path):
    """An explicit schema_version must not be replaced."""
    append_control_span({"intent": "pause", "schema_version": "custom"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["schema_version"] == "custom"


def test_append_control_span_ts_defaulted(tmp_path):
    """ts must be added automatically and end with Z."""
    append_control_span({"intent": "resume"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "ts" in record
    assert record["ts"].endswith("Z")


def test_append_control_span_accumulates_lines(tmp_path):
    """Multiple calls must each append a new line."""
    append_control_span({"intent": "compact"}, telemetry_dir=tmp_path)
    append_control_span({"intent": "clear"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_append_control_span_preserves_custom_fields(tmp_path):
    """Custom fields must be preserved in the written record."""
    append_control_span({"intent": "rewind", "node_id": "ctrl-1", "latency_ms": 12}, telemetry_dir=tmp_path)
    lines = (tmp_path / "control_spans.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["node_id"] == "ctrl-1"
    assert record["latency_ms"] == 12


def test_append_control_span_creates_parent_dirs(tmp_path):
    """telemetry_dir is created recursively when it does not exist."""
    nested = tmp_path / "a" / "b"
    append_control_span({"intent": "clear"}, telemetry_dir=nested)
    assert (nested / "control_spans.jsonl").exists()


# ---------------------------------------------------------------------------
# translate_intent_to_harness_command
# ---------------------------------------------------------------------------


def test_translate_compact_claude_code():
    ci = ControlIntent(intent="compact")
    assert translate_intent_to_harness_command(ci, "claude-code") == "/compact"


def test_translate_compact_gemini_cli():
    ci = ControlIntent(intent="compact")
    assert translate_intent_to_harness_command(ci, "gemini-cli") == "/compress"


def test_translate_compact_unknown_harness():
    ci = ControlIntent(intent="compact")
    assert translate_intent_to_harness_command(ci, "unknown-harness") is None


def test_translate_rewind_claude_code():
    ci = ControlIntent(intent="rewind")
    assert translate_intent_to_harness_command(ci, "claude-code") == "/rewind"


def test_translate_rewind_unknown_harness():
    ci = ControlIntent(intent="rewind")
    assert translate_intent_to_harness_command(ci, "gemini-cli") is None


def test_translate_switch_model_claude_code():
    ci = ControlIntent(intent="switch_model", target_model_band="opus")
    assert translate_intent_to_harness_command(ci, "claude-code") == "/model opus"


def test_translate_switch_model_uses_target_model_band():
    ci = ControlIntent(intent="switch_model", target_model_band="haiku")
    result = translate_intent_to_harness_command(ci, "claude-code")
    assert result == "/model haiku"


def test_translate_switch_model_unknown_harness():
    ci = ControlIntent(intent="switch_model", target_model_band="sonnet")
    assert translate_intent_to_harness_command(ci, "gemini-cli") is None


def test_translate_clear_returns_slash_clear_for_any_harness():
    ci = ControlIntent(intent="clear")
    assert translate_intent_to_harness_command(ci, "claude-code") == "/clear"
    assert translate_intent_to_harness_command(ci, "gemini-cli") == "/clear"
    assert translate_intent_to_harness_command(ci, "anything") == "/clear"


def test_translate_pause_returns_none():
    ci = ControlIntent(intent="pause")
    assert translate_intent_to_harness_command(ci, "claude-code") is None


def test_translate_resume_returns_none():
    ci = ControlIntent(intent="resume")
    assert translate_intent_to_harness_command(ci, "claude-code") is None


def test_translate_unknown_intent_returns_none():
    ci = ControlIntent(intent="unknown_kind")
    assert translate_intent_to_harness_command(ci, "claude-code") is None
