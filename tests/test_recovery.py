"""Tests for imx/recovery.py."""
import json

import pytest

from imx.recovery import (
    RecoveryPolicy,
    RecoveryLedger,
    should_retry,
    apply_recovery,
)


def test_should_retry_controllable_failure():
    policy = RecoveryPolicy(max_retries_per_step=2)
    # "incorrect_output" is not in no_retry_on, count=0 < max
    assert should_retry("incorrect_output", retry_count=0, policy=policy) is True


def test_should_retry_no_retry_failure_type():
    policy = RecoveryPolicy(max_retries_per_step=2)
    # "infrastructure" is in no_retry_on by default
    assert should_retry("infrastructure", retry_count=0, policy=policy) is False


def test_should_retry_exhausted():
    policy = RecoveryPolicy(max_retries_per_step=2)
    # count >= max → False
    assert should_retry("incorrect_output", retry_count=2, policy=policy) is False


def test_recovery_ledger_increment_and_cooldown(tmp_path):
    ledger = RecoveryLedger(path=tmp_path / "ledger.json")
    count = ledger.increment_retry("node-x", "planning")
    assert count == 1

    assert ledger.is_in_cooldown("node-x") is False
    ledger.set_cooldown("node-x", cooldown_seconds=600)
    assert ledger.is_in_cooldown("node-x") is True


def test_recovery_ledger_persists_to_file(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    ledger = RecoveryLedger(path=ledger_path)
    ledger.increment_retry("node-y", "implementation")
    ledger.increment_retry("node-y", "implementation")

    # Reload from disk
    ledger2 = RecoveryLedger(path=ledger_path)
    assert ledger2.get_retry_count("node-y", "implementation") == 2


def test_apply_recovery_retry(tmp_path):
    policy = RecoveryPolicy(max_retries_per_step=3, backoff_seconds=10)
    ledger = RecoveryLedger(path=tmp_path / "ledger.json")

    # First call: count goes to 1, which is < max_retries_per_step=3 → retry
    result = apply_recovery("node-z", "planning", "incorrect_output", policy, ledger)
    assert result["action"] == "retry"
    assert result["node_id"] == "node-z"
    assert result["backoff_seconds"] == 10


def test_apply_recovery_abort(tmp_path):
    # "infrastructure" won't retry; fallback_chain empty → abort
    policy = RecoveryPolicy(
        max_retries_per_step=2,
        fallback_chain=[],
        no_retry_on=["infrastructure", "quota_exceeded"],
    )
    ledger = RecoveryLedger(path=tmp_path / "ledger.json")

    result = apply_recovery("node-w", "planning", "infrastructure", policy, ledger)
    assert result["action"] == "abort"
