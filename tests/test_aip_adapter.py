from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from imx.aip_adapter import read_task_packet, route_aip_task


CATALOG = Path(__file__).parent.parent / "catalog"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _task_packet(**overrides) -> dict:
    payload = {
        "schema_version": "0.6",
        "task_id": "task-001",
        "task_class": "analysis",
        "risk_tier": "READ_ONLY",
        "relationship": "subtask",
        "capability_profile": "balanced",
        "worktree": {"path": ".worktrees/task-001", "cleanup_policy": "on_success"},
        "provenance": {
            "written_by": "architect",
            "written_at": "2026-05-22T00:00:00Z",
            "chain_depth": 2,
            "harness_fingerprint": "claude-code",
        },
    }
    payload.update(overrides)
    return payload


def test_route_aip_task_writes_route_decision_from_explicit_packet_ref(tmp_path):
    workspace = tmp_path / "workspace"
    packet_path = _write_json(workspace / "tasks" / "packets" / "task-001.json", _task_packet())
    _write_json(
        workspace / "route-requests" / "task-001.json",
        {
            "schema_version": "0.6",
            "task_id": "task-001",
            "task_class": "analysis",
            "risk_tier": "READ_ONLY",
            "requester": "architect",
            "task_packet_ref": packet_path.relative_to(workspace).as_posix(),
        },
    )

    outcome = route_aip_task(workspace, "task-001", catalog_root=CATALOG, telemetry_dir=tmp_path / "telemetry")

    assert outcome.decision_path is not None
    payload = json.loads(outcome.decision_path.read_text(encoding="utf-8"))
    assert payload["task_id"] == "task-001"
    assert payload["task_packet_ref"] == "tasks/packets/task-001.json"
    assert payload["capability_profile"] == "balanced"
    assert payload["worktree"]["path"] == ".worktrees/task-001"
    assert payload["chain_depth"] == 2
    assert outcome.result.decision is not None
    assert (tmp_path / "telemetry" / "route_decisions.jsonl").exists()


def test_route_aip_task_uses_default_packet_location_when_ref_missing(tmp_path):
    workspace = tmp_path / "workspace"
    _write_json(workspace / "tasks" / "packets" / "task-002.json", _task_packet(task_id="task-002"))
    _write_json(
        workspace / "route-requests" / "task-002.json",
        {
            "schema_version": "0.6",
            "task_id": "task-002",
            "task_class": "analysis",
            "risk_tier": "READ_ONLY",
            "requester": "planner",
        },
    )

    outcome = route_aip_task(workspace, "task-002", catalog_root=CATALOG, telemetry_dir=tmp_path / "telemetry")

    assert outcome.task_packet_path == workspace / "tasks" / "packets" / "task-002.json"
    assert outcome.task_packet_ref == "tasks/packets/task-002.json"
    assert outcome.decision_path is not None


def test_read_task_packet_rejects_invalid_schema(tmp_path):
    packet_path = _write_json(
        tmp_path / "task.json",
        {
            "schema_version": "0.6",
            "task_id": "task-invalid",
            "task_class": "analysis",
            "risk_tier": "READ_ONLY",
            "relationship": "bogus",
            "provenance": {
                "written_by": "architect",
                "written_at": "2026-05-22T00:00:00Z",
            },
        },
    )

    with pytest.raises(ValueError, match="schema validation"):
        read_task_packet(packet_path, catalog_root=CATALOG)


def test_cli_route_aip_writes_json_result(tmp_path, monkeypatch, capsys):
    from imx.cli import main

    workspace = tmp_path / "workspace"
    _write_json(workspace / "tasks" / "packets" / "task-003.json", _task_packet(task_id="task-003"))
    _write_json(
        workspace / "route-requests" / "task-003.json",
        {
            "schema_version": "0.6",
            "task_id": "task-003",
            "task_class": "analysis",
            "risk_tier": "READ_ONLY",
            "requester": "architect",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "imx",
            "--catalog",
            str(CATALOG),
            "route-aip",
            "--workspace",
            str(workspace),
            "--task-id",
            "task-003",
            "--telemetry-dir",
            str(tmp_path / "telemetry"),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    payload = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 0
    assert payload["task_packet_ref"] == "tasks/packets/task-003.json"
    assert payload["decision"]["task_id"] == "task-003"
