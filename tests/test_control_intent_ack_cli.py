"""Tests for `imx control-intent ack` — wires mark_intent_acked + append_control_span.

Spec §10.6: a processed control intent is acked (renamed) and every control
action appends to control_spans.jsonl.
"""
import argparse
import json

from imx.cli import cmd_control_intent_ack
from imx.control_intents import ControlIntent, write_control_intent


def _ack_args(intent_path, telemetry_dir, acked_by="harness-a"):
    return argparse.Namespace(
        intent_path=str(intent_path),
        telemetry_dir=str(telemetry_dir),
        acked_by=acked_by,
    )


def test_ack_renames_intent_and_records_span(tmp_path, capsys):
    intents_dir = tmp_path / "intents"
    telemetry_dir = tmp_path / "telemetry"
    intent_path = write_control_intent(
        ControlIntent(intent="compact", task_id="task-7", session_id="s1",
                      requested_by="architect"),
        intents_dir=intents_dir,
    )

    exit_code = cmd_control_intent_ack(_ack_args(intent_path, telemetry_dir))

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["span_recorded"] is True

    # Intent file is renamed to .intent.acked.json
    assert not intent_path.exists()
    acked = intent_path.parent / intent_path.name.replace(".intent.json", ".intent.acked.json")
    assert acked.exists()

    # A control span is appended carrying the intent's identity.
    span_log = telemetry_dir / "control_spans.jsonl"
    assert span_log.exists()
    span = json.loads(span_log.read_text(encoding="utf-8").splitlines()[0])
    assert span["event"] == "intent_acked"
    assert span["intent"] == "compact"
    assert span["session_id"] == "s1"
    assert span["task_id"] == "task-7"
    assert span["acked_by"] == "harness-a"


def test_ack_missing_file_returns_error(tmp_path, capsys):
    exit_code = cmd_control_intent_ack(
        _ack_args(tmp_path / "nope.intent.json", tmp_path / "telemetry")
    )
    assert exit_code == 1
    assert not (tmp_path / "telemetry" / "control_spans.jsonl").exists()
