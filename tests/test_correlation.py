"""Tests for imx.correlation — read_aip_events, read_route_decisions, correlate_events, correlate_workspace."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from imx.correlation import (
    correlate_events,
    correlate_workspace,
    read_aip_events,
    read_route_decisions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, records: list) -> None:
    """Write a list of objects (or raw strings) to a JSONL file."""
    lines = []
    for r in records:
        lines.append(r if isinstance(r, str) else json.dumps(r))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _by_task(records: list[dict]) -> dict[str, dict]:
    """Index a list of correlate_events records by task_id."""
    return {r["task_id"]: r for r in records}


# ---------------------------------------------------------------------------
# read_aip_events
# ---------------------------------------------------------------------------


def test_read_aip_events_missing_file_returns_empty(tmp_path):
    """Should return [] when the events file does not exist."""
    result = read_aip_events(tmp_path / "events.jsonl")
    assert result == []


def test_read_aip_events_empty_file_returns_empty(tmp_path):
    """Should return [] for a completely empty file."""
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("", encoding="utf-8")
    assert read_aip_events(events_path) == []


def test_read_aip_events_blank_lines_skipped(tmp_path):
    """Blank/whitespace-only lines must be skipped without error."""
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n   \n\n", encoding="utf-8")
    assert read_aip_events(events_path) == []


def test_read_aip_events_malformed_json_skipped(tmp_path):
    """Malformed JSON lines must be skipped; valid lines still returned."""
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        'not valid json\n{"task": "t1", "ts": "2024-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    result = read_aip_events(events_path)
    assert len(result) == 1
    assert result[0]["task"] == "t1"


def test_read_aip_events_non_dict_json_skipped(tmp_path):
    """Non-dict JSON values (arrays, strings) must be skipped."""
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        '[1, 2, 3]\n{"task": "t2", "ts": "2024-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    result = read_aip_events(events_path)
    assert len(result) == 1
    assert result[0]["task"] == "t2"


def test_read_aip_events_happy_path(tmp_path):
    """All valid dicts in the file should be returned."""
    events_path = tmp_path / "events.jsonl"
    _write_jsonl(
        events_path,
        [
            {"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"},
            {"task": "t2", "ts": "2024-01-02T00:00:00Z", "status": "failed"},
        ],
    )
    result = read_aip_events(events_path)
    assert len(result) == 2
    assert result[0]["task"] == "t1"
    assert result[1]["task"] == "t2"


def test_read_aip_events_since_filter_keeps_matching(tmp_path):
    """Events with ts >= since should be returned."""
    events_path = tmp_path / "events.jsonl"
    _write_jsonl(
        events_path,
        [
            {"task": "t1", "ts": "2024-01-05T00:00:00Z"},
            {"task": "t2", "ts": "2024-01-10T00:00:00Z"},
        ],
    )
    result = read_aip_events(events_path, since="2024-01-05T00:00:00Z")
    assert len(result) == 2


def test_read_aip_events_since_filter_drops_older(tmp_path):
    """Events with ts < since must be excluded."""
    events_path = tmp_path / "events.jsonl"
    _write_jsonl(
        events_path,
        [
            {"task": "t1", "ts": "2024-01-01T00:00:00Z"},
            {"task": "t2", "ts": "2024-01-10T00:00:00Z"},
        ],
    )
    result = read_aip_events(events_path, since="2024-01-05T00:00:00Z")
    assert len(result) == 1
    assert result[0]["task"] == "t2"


def test_read_aip_events_since_filter_drops_missing_ts(tmp_path):
    """Events without a ts field must be dropped when since is supplied."""
    events_path = tmp_path / "events.jsonl"
    _write_jsonl(
        events_path,
        [
            {"task": "t1"},
            {"task": "t2", "ts": "2024-01-10T00:00:00Z"},
        ],
    )
    result = read_aip_events(events_path, since="2024-01-01T00:00:00Z")
    assert len(result) == 1
    assert result[0]["task"] == "t2"


# ---------------------------------------------------------------------------
# read_route_decisions
# ---------------------------------------------------------------------------


def test_read_route_decisions_missing_dir_returns_empty(tmp_path):
    """Should return [] when the directory does not exist."""
    result = read_route_decisions(tmp_path / "nonexistent-dir")
    assert result == []


def test_read_route_decisions_path_is_file_returns_empty(tmp_path):
    """Should return [] when path points to a file, not a directory."""
    file_path = tmp_path / "not_a_dir.json"
    file_path.write_text("{}", encoding="utf-8")
    assert read_route_decisions(file_path) == []


def test_read_route_decisions_non_json_files_ignored(tmp_path):
    """Files without .json extension must be silently ignored."""
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    (decisions_dir / "ignore.txt").write_text('{"task_id": "t1"}', encoding="utf-8")
    (decisions_dir / "ignore.yaml").write_text("task_id: t1", encoding="utf-8")
    result = read_route_decisions(decisions_dir)
    assert result == []


def test_read_route_decisions_malformed_json_skipped(tmp_path):
    """Malformed JSON files must be skipped; valid ones still returned."""
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    (decisions_dir / "bad.json").write_text("not json", encoding="utf-8")
    (decisions_dir / "good.json").write_text(
        '{"task_id": "t1", "node_id": "n1"}', encoding="utf-8"
    )
    result = read_route_decisions(decisions_dir)
    assert len(result) == 1
    assert result[0]["task_id"] == "t1"


def test_read_route_decisions_non_dict_json_skipped(tmp_path):
    """Non-dict JSON (e.g. a list) must be skipped."""
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    (decisions_dir / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
    (decisions_dir / "dict.json").write_text('{"task_id": "t2"}', encoding="utf-8")
    result = read_route_decisions(decisions_dir)
    assert len(result) == 1
    assert result[0]["task_id"] == "t2"


def test_read_route_decisions_happy_path(tmp_path):
    """All valid dict JSON files should be returned."""
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    for i in range(3):
        (decisions_dir / f"task{i}.json").write_text(
            json.dumps({"task_id": f"t{i}", "node_id": f"n{i}"}), encoding="utf-8"
        )
    result = read_route_decisions(decisions_dir)
    assert len(result) == 3
    task_ids = {d["task_id"] for d in result}
    assert task_ids == {"t0", "t1", "t2"}


# ---------------------------------------------------------------------------
# correlate_events
# ---------------------------------------------------------------------------


def test_correlate_events_empty_inputs():
    """Empty inputs should produce an empty list of records."""
    assert correlate_events([], []) == []


def test_correlate_events_full_correlation_status():
    """correlation_status must be 'full' when both event and decision are present."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "agent": "agt", "status": "finished"}]
    decisions = [{"task_id": "t1", "node_id": "n1", "task_class": "analysis"}]
    records = _by_task(correlate_events(events, decisions))
    assert records["t1"]["correlation_status"] == "full"


def test_correlate_events_partial_correlation_status_no_decision():
    """correlation_status must be 'partial' when no matching decision exists."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["correlation_status"] == "partial"


def test_correlate_events_task_in_decision_only():
    """A task_id present only in route decisions still produces a record."""
    decisions = [{"task_id": "t99", "node_id": "n1", "task_class": "review"}]
    records = _by_task(correlate_events([], decisions))
    assert "t99" in records
    assert records["t99"]["node_id"] == "n1"
    assert records["t99"]["task_class"] == "review"


def test_correlate_events_outcome_finished_maps_to_succeeded():
    """AIP status 'finished' must map to outcome 'succeeded'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "succeeded"


def test_correlate_events_outcome_failed_maps_to_failed():
    """AIP status 'failed' must map to outcome 'failed'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "failed"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "failed"


def test_correlate_events_outcome_blocked_maps_to_partial():
    """AIP status 'blocked' must map to outcome 'partial'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "blocked"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "partial"


def test_correlate_events_unknown_status_maps_to_unknown():
    """An unrecognized status must map to outcome 'unknown'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "weird_status"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "unknown"


def test_correlate_events_outcome_class_uncontrollable_on_infrastructure(tmp_path):
    """outcome_class must be 'uncontrollable' when failed with 'infrastructure' in message."""
    events = [
        {
            "task": "t1",
            "ts": "2024-01-01T00:00:00Z",
            "status": "failed",
            "message": "infrastructure error occurred",
        }
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome_class"] == "uncontrollable"


def test_correlate_events_outcome_class_uncontrollable_on_timeout():
    """outcome_class must be 'uncontrollable' when failed with 'timeout' in message."""
    events = [
        {
            "task": "t1",
            "ts": "2024-01-01T00:00:00Z",
            "status": "failed",
            "message": "request timeout exceeded",
        }
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome_class"] == "uncontrollable"


def test_correlate_events_outcome_class_uncontrollable_on_network():
    """outcome_class must be 'uncontrollable' when failed with 'network' in message."""
    events = [
        {
            "task": "t1",
            "ts": "2024-01-01T00:00:00Z",
            "status": "failed",
            "message": "network connection refused",
        }
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome_class"] == "uncontrollable"


def test_correlate_events_outcome_class_controllable_for_plain_failure():
    """outcome_class must be 'controllable' for a failed outcome without uncontrollable keywords."""
    events = [
        {
            "task": "t1",
            "ts": "2024-01-01T00:00:00Z",
            "status": "failed",
            "message": "assertion error in step 3",
        }
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome_class"] == "controllable"


def test_correlate_events_last_event_status_wins():
    """The outcome must be taken from the last (latest ts) event that has a status."""
    events = [
        {"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"},
        {"task": "t1", "ts": "2024-01-02T00:00:00Z", "status": "failed"},
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "failed"


def test_correlate_events_no_status_event_yields_unknown():
    """A task with no events carrying a status field has outcome 'unknown'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["outcome"] == "unknown"


def test_correlate_events_single_agent_is_string():
    """A single unique agent name must be stored as a plain string."""
    events = [
        {"task": "t1", "ts": "2024-01-01T00:00:00Z", "agent": "agent-a"},
        {"task": "t1", "ts": "2024-01-02T00:00:00Z", "agent": "agent-a"},
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["agent"] == "agent-a"


def test_correlate_events_multiple_agents_is_list():
    """Multiple distinct agent names must be stored as a list."""
    events = [
        {"task": "t1", "ts": "2024-01-01T00:00:00Z", "agent": "agent-a"},
        {"task": "t1", "ts": "2024-01-02T00:00:00Z", "agent": "agent-b"},
    ]
    records = _by_task(correlate_events(events, []))
    agent = records["t1"]["agent"]
    assert isinstance(agent, list)
    assert set(agent) == {"agent-a", "agent-b"}


def test_correlate_events_no_agent_is_none():
    """When no event carries an agent field, agent must be None."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["agent"] is None


def test_correlate_events_duration_ms_computed():
    """duration_ms must be the millisecond difference between first and last ts."""
    events = [
        {"task": "t1", "ts": "2024-01-01T00:00:00Z"},
        {"task": "t1", "ts": "2024-01-01T00:00:02Z"},  # 2 seconds later
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["duration_ms"] == 2000


def test_correlate_events_duration_ms_none_when_single_event():
    """duration_ms must be 0 (start == end) when only one event exists."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    # start == end → delta 0 → 0 ms
    assert records["t1"]["duration_ms"] == 0


def test_correlate_events_duration_ms_none_when_no_events():
    """duration_ms must be None when there are no events (decision-only task)."""
    decisions = [{"task_id": "t1", "node_id": "n1"}]
    records = _by_task(correlate_events([], decisions))
    assert records["t1"]["duration_ms"] is None


def test_correlate_events_summary_ref_from_export_event():
    """summary_ref must be the 'file' field of the first export event."""
    events = [
        {"task": "t1", "ts": "2024-01-01T00:00:00Z", "event": "export", "file": "out/summary.md"},
    ]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["summary_ref"] == "out/summary.md"


def test_correlate_events_summary_ref_none_without_export():
    """summary_ref must be None when no export event is present."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["summary_ref"] is None


def test_correlate_events_missing_fields_when_no_decision_no_agent():
    """missing_fields must include node_id, task_class, agent when absent."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    mf = records["t1"]["missing_fields"]
    assert "node_id" in mf
    assert "task_class" in mf
    assert "agent" in mf


def test_correlate_events_no_missing_fields_when_complete():
    """missing_fields must be empty when all fields are supplied."""
    events = [
        {
            "task": "t1",
            "ts": "2024-01-01T00:00:00Z",
            "agent": "agent-a",
            "status": "finished",
        }
    ]
    decisions = [{"task_id": "t1", "node_id": "n1", "task_class": "analysis"}]
    records = _by_task(correlate_events(events, decisions))
    assert records["t1"]["missing_fields"] == []


def test_correlate_events_missing_fields_no_timestamps():
    """missing_fields must include started_at/completed_at when no events exist."""
    decisions = [{"task_id": "t1", "node_id": "n1", "task_class": "review"}]
    records = _by_task(correlate_events([], decisions))
    mf = records["t1"]["missing_fields"]
    assert "started_at" in mf
    assert "completed_at" in mf


def test_correlate_events_schema_version_is_0_6():
    """All records must carry schema_version == '0.6'."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = correlate_events(events, [])
    assert all(r["schema_version"] == "0.6" for r in records)


def test_correlate_events_unkeyed_events_not_in_output():
    """Events without a 'task' key must not appear in any output record."""
    events = [
        {"ts": "2024-01-01T00:00:00Z", "status": "finished"},  # no 'task' key
        {"task": "t1", "ts": "2024-01-01T00:00:00Z"},
    ]
    records = _by_task(correlate_events(events, []))
    assert list(records.keys()) == ["t1"]


def test_correlate_events_chain_depth_from_decision():
    """chain_depth must be taken from the route decision."""
    decisions = [{"task_id": "t1", "node_id": "n1", "chain_depth": 3}]
    records = _by_task(correlate_events([], decisions))
    assert records["t1"]["chain_depth"] == 3


def test_correlate_events_chain_depth_default_zero_without_decision():
    """chain_depth must default to 0 when no decision is present."""
    events = [{"task": "t1", "ts": "2024-01-01T00:00:00Z"}]
    records = _by_task(correlate_events(events, []))
    assert records["t1"]["chain_depth"] == 0


# ---------------------------------------------------------------------------
# correlate_workspace
# ---------------------------------------------------------------------------


def _setup_workspace(
    tmp_path: Path,
    events: list[dict],
    decisions: list[dict],
) -> tuple[Path, Path, Path]:
    """Create workspace_root/events.jsonl and route-decisions dir, return paths."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    decisions_dir = workspace / "route-decisions"
    decisions_dir.mkdir()
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    events_path = workspace / "events.jsonl"
    _write_jsonl(events_path, events)

    for i, d in enumerate(decisions):
        (decisions_dir / f"decision_{i}.json").write_text(
            json.dumps(d), encoding="utf-8"
        )

    return workspace, decisions_dir, telemetry_dir


def test_correlate_workspace_returns_record_count(tmp_path):
    """correlate_workspace must return the number of telemetry records written."""
    workspace, decisions_dir, telem_dir = _setup_workspace(
        tmp_path,
        events=[
            {"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"},
            {"task": "t2", "ts": "2024-01-01T00:00:00Z", "status": "failed"},
        ],
        decisions=[],
    )
    count = correlate_workspace(workspace, decisions_dir, telem_dir)
    assert count == 2


def test_correlate_workspace_writes_tasks_jsonl(tmp_path):
    """correlate_workspace must write records into telemetry_dir/tasks.jsonl."""
    workspace, decisions_dir, telem_dir = _setup_workspace(
        tmp_path,
        events=[{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"}],
        decisions=[],
    )
    correlate_workspace(workspace, decisions_dir, telem_dir)
    tasks_file = telem_dir / "tasks.jsonl"
    assert tasks_file.exists()
    lines = tasks_file.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["task_id"] == "t1"


def test_correlate_workspace_no_events_file_returns_zero(tmp_path):
    """correlate_workspace returns 0 when events.jsonl is absent."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    decisions_dir = workspace / "route-decisions"
    decisions_dir.mkdir()
    telem_dir = tmp_path / "telemetry"
    telem_dir.mkdir()
    count = correlate_workspace(workspace, decisions_dir, telem_dir)
    assert count == 0


def test_correlate_workspace_integrates_decisions(tmp_path):
    """correlate_workspace must read route-decisions and set correlation_status=full."""
    workspace, decisions_dir, telem_dir = _setup_workspace(
        tmp_path,
        events=[{"task": "t1", "ts": "2024-01-01T00:00:00Z", "status": "finished"}],
        decisions=[{"task_id": "t1", "node_id": "n1", "task_class": "analysis"}],
    )
    correlate_workspace(workspace, decisions_dir, telem_dir)
    tasks_file = telem_dir / "tasks.jsonl"
    record = json.loads(tasks_file.read_text().splitlines()[0])
    assert record["correlation_status"] == "full"
    assert record["node_id"] == "n1"
