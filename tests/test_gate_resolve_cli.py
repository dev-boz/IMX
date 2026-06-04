"""Tests for the gate-resolve CLI path, including TTL expiry wiring (spec §10.7)."""
import argparse
import json

from imx.cli import cmd_gate_resolve
from imx.gates import GateAnswer, GateFile, write_gate_file, write_gate_vote


def _resolve_args(task_id, stage, gates_dir):
    return argparse.Namespace(task_id=task_id, stage=stage, gates_dir=str(gates_dir))


def _write_gate(gates_dir, *, task_id, stage, requested_at, ttl_seconds):
    gate = GateFile(
        gate_id=f"{task_id}-{stage}",
        task_id=task_id,
        stage=stage,
        question="Approve?",
        requester="executor",
        requested_at=requested_at,
        ttl_seconds=ttl_seconds,
    )
    write_gate_file(gate, gates_dir)


def test_gate_resolve_reports_expired_when_no_votes(tmp_path, capsys):
    _write_gate(
        tmp_path,
        task_id="t1",
        stage="plan",
        requested_at="2000-01-01T00:00:00Z",
        ttl_seconds=300,
    )

    exit_code = cmd_gate_resolve(_resolve_args("t1", "plan", tmp_path))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "expired"
    assert payload["expired"] is True


def test_gate_resolve_reports_no_votes_for_fresh_gate(tmp_path, capsys):
    _write_gate(
        tmp_path,
        task_id="t2",
        stage="plan",
        requested_at="2999-01-01T00:00:00Z",
        ttl_seconds=300,
    )

    exit_code = cmd_gate_resolve(_resolve_args("t2", "plan", tmp_path))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "no_votes"


def test_gate_resolve_expiry_is_failsafe_even_with_votes(tmp_path, capsys):
    """An expired gate times out (fail-safe): votes do not silently resolve it."""
    _write_gate(
        tmp_path,
        task_id="t3",
        stage="plan",
        requested_at="2000-01-01T00:00:00Z",
        ttl_seconds=300,
    )
    write_gate_vote(
        GateAnswer(
            gate_id="t3-plan",
            task_id="t3",
            stage="plan",
            decision="approve",
            responder="model-a",
        ),
        tmp_path,
    )

    exit_code = cmd_gate_resolve(_resolve_args("t3", "plan", tmp_path))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "expired"
    assert payload["expired"] is True
    assert "outcome" not in payload


def test_gate_resolve_records_votes_for_fresh_gate(tmp_path, capsys):
    """A non-expired gate with votes resolves normally to a VoteRecord."""
    _write_gate(
        tmp_path,
        task_id="t4",
        stage="plan",
        requested_at="2999-01-01T00:00:00Z",
        ttl_seconds=300,
    )
    write_gate_vote(
        GateAnswer(
            gate_id="t4-plan",
            task_id="t4",
            stage="plan",
            decision="approve",
            responder="model-a",
        ),
        tmp_path,
    )

    exit_code = cmd_gate_resolve(_resolve_args("t4", "plan", tmp_path))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["outcome"] == "approve"
