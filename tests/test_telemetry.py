"""Tests for imx.telemetry — append_task_record, append_route_decision, append_dream_trigger."""
import json
from pathlib import Path

import pytest

from imx.telemetry import append_dream_trigger, append_route_decision, append_task_record


# ---------------------------------------------------------------------------
# append_task_record
# ---------------------------------------------------------------------------


def test_append_task_record_creates_file(tmp_path):
    """append_task_record should create tasks.jsonl in the given directory."""
    append_task_record({"task_id": "t1", "outcome": "ok"}, telemetry_dir=tmp_path)
    assert (tmp_path / "tasks.jsonl").exists()


def test_append_task_record_content_is_valid_json_line(tmp_path):
    """Each appended record must be a valid JSON object on a single line."""
    append_task_record({"task_id": "t2", "outcome": "ok"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "tasks.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert isinstance(record, dict)


def test_append_task_record_schema_version_present(tmp_path):
    """schema_version must be set automatically on each record."""
    append_task_record({"task_id": "t3"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "tasks.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "schema_version" in record


def test_append_task_record_recorded_at_present(tmp_path):
    """recorded_at timestamp must be set automatically on each record."""
    append_task_record({"task_id": "t4"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "tasks.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "recorded_at" in record
    assert record["recorded_at"].endswith("Z")


def test_append_task_record_accumulates_lines(tmp_path):
    """Multiple calls should each append a new line to the JSONL file."""
    append_task_record({"task_id": "t5a"}, telemetry_dir=tmp_path)
    append_task_record({"task_id": "t5b"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "tasks.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_append_task_record_preserves_custom_fields(tmp_path):
    """Custom fields in the record dict must be preserved as-is."""
    append_task_record({"task_id": "t6", "node_id": "node-x", "latency": 0.42}, telemetry_dir=tmp_path)
    lines = (tmp_path / "tasks.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["node_id"] == "node-x"
    assert record["latency"] == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# append_route_decision
# ---------------------------------------------------------------------------


def test_append_route_decision_creates_file(tmp_path):
    """append_route_decision should create route_decisions.jsonl."""
    append_route_decision({"node_id": "n1", "task_class": "analysis"}, telemetry_dir=tmp_path)
    assert (tmp_path / "route_decisions.jsonl").exists()


def test_append_route_decision_content_is_valid_json(tmp_path):
    """Each record in route_decisions.jsonl must be a valid JSON object."""
    append_route_decision({"node_id": "n2"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "route_decisions.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert isinstance(record, dict)


def test_append_route_decision_schema_version_present(tmp_path):
    """schema_version must be added automatically."""
    append_route_decision({"node_id": "n3"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "route_decisions.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "schema_version" in record


def test_append_route_decision_decided_at_present(tmp_path):
    """decided_at timestamp must be set automatically."""
    append_route_decision({"node_id": "n4"}, telemetry_dir=tmp_path)
    lines = (tmp_path / "route_decisions.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "decided_at" in record
    assert record["decided_at"].endswith("Z")


# ---------------------------------------------------------------------------
# append_dream_trigger
# ---------------------------------------------------------------------------


def test_append_dream_trigger_creates_file(tmp_path):
    """append_dream_trigger should create dream-triggers.jsonl in the state dir."""
    append_dream_trigger("manual", telemetry_dir=tmp_path)
    assert (tmp_path / "dream-triggers.jsonl").exists()


def test_append_dream_trigger_content_is_valid_json(tmp_path):
    """Each dream trigger record must be valid JSON."""
    append_dream_trigger("scheduled", query="find gaps", telemetry_dir=tmp_path)
    lines = (tmp_path / "dream-triggers.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert isinstance(record, dict)


def test_append_dream_trigger_trigger_type_preserved(tmp_path):
    """trigger_type field must match the argument passed."""
    append_dream_trigger("manual_review", telemetry_dir=tmp_path)
    lines = (tmp_path / "dream-triggers.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["trigger_type"] == "manual_review"


def test_append_dream_trigger_ts_field_present(tmp_path):
    """ts timestamp field must be present and end with Z."""
    append_dream_trigger("check", telemetry_dir=tmp_path)
    lines = (tmp_path / "dream-triggers.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert "ts" in record
    assert record["ts"].endswith("Z")


def test_append_dream_trigger_context_stored(tmp_path):
    """context dict must be stored in the record."""
    ctx = {"pr": 42, "branch": "feat-x"}
    append_dream_trigger("pr_open", context=ctx, telemetry_dir=tmp_path)
    lines = (tmp_path / "dream-triggers.jsonl").read_text().splitlines()
    record = json.loads(lines[0])
    assert record["context"] == ctx
