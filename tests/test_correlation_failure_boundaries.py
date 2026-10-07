"""Mixed-contract failure attribution without borrowing another attempt."""
import pytest

from imx.correlation import correlate_events


def queue(stage, **fields):
    return dict(event="task", task_id="t", stage=stage, ts="2026-10-07T00:00:00Z", **fields)


def status(message="network connection refused", **fields):
    return dict(event="status", task="t", status="failed", message=message,
                ts="2026-10-07T00:00:00Z", **fields)


def result(events):
    records = correlate_events(events, [])
    assert len(records) == 1
    return records[0]["outcome"], records[0]["outcome_class"]


@pytest.mark.parametrize("message", ["network connection refused", "provider timeout", "infrastructure outage"])
def test_same_attempt_failure_evidence(message):
    assert result([queue("claimed"), status(message), queue("failed")]) == ("failed", "uncontrollable")


@pytest.mark.parametrize("boundary", ["pending", "claimed", "done", "failed"])
def test_never_borrow_evidence_across_queue_transition(boundary):
    assert result([status(), queue(boundary), queue("failed")]) == ("failed", "controllable")


@pytest.mark.parametrize("stage,outcome", [("done", "succeeded"), ("pending", "unknown"), ("claimed", "unknown")])
def test_status_cannot_override_queue_outcome(stage, outcome):
    assert result([queue("claimed"), status(), queue(stage)]) == (outcome, "controllable")


def test_explicit_terminal_reason_wins():
    assert result([queue("claimed"), status(), queue("failed", reason="incorrect answer")]) == ("failed", "controllable")


def test_latest_status_message_wins():
    assert result([queue("claimed"), status(), status("incorrect answer"), queue("failed")]) == ("failed", "controllable")


def test_status_after_terminal_is_not_attributed():
    assert result([queue("claimed"), queue("failed"), status()]) == ("failed", "controllable")


def test_previous_owner_cannot_supply_current_failure():
    assert result([queue("claimed", claimed_by="new"), status(agent="old"), queue("failed", claimed_by="new", agent="supervisor")]) == ("failed", "controllable")


def test_owner_status_works_when_supervisor_marks_failed():
    assert result([queue("claimed", claimed_by="worker"), status(agent="worker"), queue("failed", claimed_by="worker", agent="supervisor")]) == ("failed", "uncontrollable")


def test_retry_can_supply_its_own_failure_reason():
    assert result([queue("claimed"), status("incorrect answer"), queue("pending"), queue("claimed"), status(), queue("failed")]) == ("failed", "uncontrollable")
