"""Native AIP regression checks; optional unless AIP is installed."""
import json

import pytest

from imx.correlation import correlate_workspace


def test_real_queue_preserves_same_attempt_network_failure(tmp_path):
    pytest.importorskip("aip")
    from aip.tasks import TaskQueue
    from aip.workspace import AipWorkspace

    workspace = AipWorkspace(tmp_path / "workspace")
    queue = TaskQueue(workspace)
    task = queue.create_task(description="provider request", task_id="mixed-failure")
    queue.claim_task(task.task_id, "worker")
    workspace.append_event(
        "worker", "status", task=task.task_id, status="failed",
        message="network connection refused",
    )
    queue.fail_task(task.task_id, agent_name="worker")
    telemetry = tmp_path / "telemetry"
    assert correlate_workspace(workspace.root, telemetry_dir=telemetry) == 1
    record = json.loads((telemetry / "tasks.jsonl").read_text())
    assert record["task_id"] == task.task_id
    assert record["outcome"] == "failed"
    assert record["outcome_class"] == "uncontrollable"
