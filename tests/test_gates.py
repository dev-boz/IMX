"""Tests for imx/gates.py."""
import json
from datetime import datetime, timezone, timedelta

import pytest

from imx.gates import (
    GateFile,
    GateAnswer,
    VoteRecord,
    write_gate_file,
    read_gate_file,
    write_gate_answer,
    read_gate_answer,
    is_gate_expired,
    aggregate_votes,
    create_gate,
)


def test_write_and_read_gate_file(tmp_path):
    gate = GateFile(
        gate_id="task1-plan",
        task_id="task1",
        stage="plan",
        question="Approve the plan?",
        requester="executor",
        requested_at="2024-01-01T00:00:00Z",
        ttl_seconds=300,
    )
    write_gate_file(gate, tmp_path)
    loaded = read_gate_file("task1", "plan", tmp_path)

    assert loaded is not None
    assert loaded.gate_id == "task1-plan"
    assert loaded.task_id == "task1"
    assert loaded.stage == "plan"
    assert loaded.question == "Approve the plan?"
    assert loaded.requester == "executor"
    assert loaded.ttl_seconds == 300


def test_write_and_read_gate_answer(tmp_path):
    answer = GateAnswer(
        gate_id="task2-plan",
        task_id="task2",
        stage="plan",
        decision="approve",
        rationale="Looks good.",
        responder="advisor",
        responded_at="2024-01-01T00:01:00Z",
    )
    write_gate_answer(answer, tmp_path)
    loaded = read_gate_answer("task2", "plan", tmp_path)

    assert loaded is not None
    assert loaded.gate_id == "task2-plan"
    assert loaded.decision == "approve"
    assert loaded.rationale == "Looks good."
    assert loaded.responder == "advisor"


def test_is_gate_expired_old_gate():
    # Gate requested 10 minutes ago with TTL 60 seconds
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).replace(microsecond=0)
    requested_at = old_time.isoformat().replace("+00:00", "Z")
    gate = GateFile(
        task_id="task3",
        stage="plan",
        requested_at=requested_at,
        ttl_seconds=60,
    )
    assert is_gate_expired(gate) is True


def test_is_gate_expired_fresh_gate():
    # Gate requested just now with TTL 300 seconds
    now_str = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    gate = GateFile(
        task_id="task4",
        stage="plan",
        requested_at=now_str,
        ttl_seconds=300,
    )
    assert is_gate_expired(gate) is False


def _make_answer(gate_id, decision, responder="advisor"):
    return GateAnswer(
        gate_id=gate_id,
        task_id="task5",
        stage="plan",
        decision=decision,
        responder=responder,
    )


def test_aggregate_votes_simple_majority():
    votes = [
        _make_answer("g1", "approve", "a1"),
        _make_answer("g1", "approve", "a2"),
        _make_answer("g1", "deny", "a3"),
    ]
    record = aggregate_votes(votes)
    assert record.outcome == "approve"
    assert record.tally["approve"] == 2
    assert record.tally["deny"] == 1


def test_aggregate_votes_tie_prefers_approve():
    votes = [
        _make_answer("g2", "approve", "a1"),
        _make_answer("g2", "deny", "a2"),
    ]
    record = aggregate_votes(votes)
    assert record.outcome == "approve"


def test_create_gate_writes_file(tmp_path):
    gate = create_gate(
        task_id="task6",
        stage="plan",
        question="Should we proceed?",
        requester="executor",
        gates_dir=tmp_path,
    )
    expected_path = tmp_path / "gate-task6-plan.json"
    assert expected_path.exists()

    data = json.loads(expected_path.read_text())
    assert data["task_id"] == "task6"
    assert data["stage"] == "plan"
    assert data["gate_id"] == "task6-plan"
