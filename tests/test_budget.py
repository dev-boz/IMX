"""Tests for imx.budget — BudgetLedger, load_budget, save_budget."""
import json

import pytest

from imx.budget import BudgetLedger, load_budget, save_budget


# ---------------------------------------------------------------------------
# BudgetLedger.check()
# ---------------------------------------------------------------------------


def test_check_returns_true_under_budget():
    """check() should return (True, 'ok') when spend is below all limits."""
    ledger = BudgetLedger(task_id="t1", max_cost_usd=1.0, spent_usd=0.5)
    allowed, reason = ledger.check()
    assert allowed is True
    assert reason == "ok"


def test_check_returns_false_when_hard_gate_cost_exceeded():
    """Hard gate mode should block (return False) when cost budget is exhausted."""
    ledger = BudgetLedger(
        task_id="t2",
        max_cost_usd=1.0,
        gate_mode="hard",
        spent_usd=1.0,
    )
    allowed, reason = ledger.check()
    assert allowed is False
    assert "exhausted" in reason.lower()


def test_check_returns_true_with_warning_on_soft_gate_exceeded():
    """Soft gate mode should allow but warn when cost budget is exceeded."""
    ledger = BudgetLedger(
        task_id="t3",
        max_cost_usd=1.0,
        gate_mode="soft",
        spent_usd=1.0,
    )
    allowed, reason = ledger.check()
    assert allowed is True
    assert "warning" in reason.lower()


def test_check_returns_false_when_hard_gate_tokens_exceeded():
    """Hard gate mode should block when token budget is exhausted."""
    ledger = BudgetLedger(
        task_id="t4",
        max_tokens=100,
        gate_mode="hard",
        spent_tokens=100,
    )
    allowed, reason = ledger.check()
    assert allowed is False
    assert "token" in reason.lower()


def test_check_no_limits_always_ok():
    """When no limits are set, check() should always return (True, 'ok')."""
    ledger = BudgetLedger(task_id="t5", spent_usd=999.0, spent_tokens=999999)
    allowed, reason = ledger.check()
    assert allowed is True
    assert reason == "ok"


# ---------------------------------------------------------------------------
# BudgetLedger.record_spend()
# ---------------------------------------------------------------------------


def test_record_spend_accumulates_cost():
    """Multiple record_spend calls should accumulate spent_usd."""
    ledger = BudgetLedger(task_id="t6")
    ledger.record_spend(cost_usd=0.10)
    ledger.record_spend(cost_usd=0.05)
    assert ledger.spent_usd == pytest.approx(0.15)


def test_record_spend_accumulates_tokens():
    """Multiple record_spend calls should accumulate spent_tokens."""
    ledger = BudgetLedger(task_id="t7")
    ledger.record_spend(tokens=500)
    ledger.record_spend(tokens=300)
    assert ledger.spent_tokens == 800


def test_record_spend_sets_status_exhausted_on_hard_gate():
    """After exceeding a hard gate, status should become 'exhausted'."""
    ledger = BudgetLedger(task_id="t8", max_cost_usd=0.10, gate_mode="hard")
    ledger.record_spend(cost_usd=0.20)
    assert ledger.status == "exhausted"


def test_record_spend_sets_status_warning_on_soft_gate():
    """After exceeding a soft gate, status should become 'warning'."""
    ledger = BudgetLedger(task_id="t9", max_cost_usd=0.10, gate_mode="soft")
    ledger.record_spend(cost_usd=0.20)
    assert ledger.status == "warning"


def test_record_spend_status_ok_under_budget():
    """Status should remain 'ok' when spending is within limits."""
    ledger = BudgetLedger(task_id="t10", max_cost_usd=1.0)
    ledger.record_spend(cost_usd=0.10)
    assert ledger.status == "ok"


# ---------------------------------------------------------------------------
# load_budget / save_budget round-trip
# ---------------------------------------------------------------------------


def test_load_budget_returns_default_when_file_missing(tmp_path):
    """load_budget should return a fresh BudgetLedger when no file exists."""
    ledger = load_budget("no-such-task", budgets_dir=tmp_path)
    assert ledger.task_id == "no-such-task"
    assert ledger.spent_usd == 0.0
    assert ledger.spent_tokens == 0


def test_save_and_load_budget_round_trip(tmp_path):
    """save_budget then load_budget should restore all fields exactly."""
    ledger = BudgetLedger(
        task_id="round-trip",
        max_cost_usd=2.50,
        max_tokens=1000,
        gate_mode="hard",
        spent_usd=0.75,
        spent_tokens=300,
        status="ok",
    )
    save_budget(ledger, budgets_dir=tmp_path)
    reloaded = load_budget("round-trip", budgets_dir=tmp_path)
    assert reloaded.task_id == "round-trip"
    assert reloaded.max_cost_usd == pytest.approx(2.50)
    assert reloaded.max_tokens == 1000
    assert reloaded.gate_mode == "hard"
    assert reloaded.spent_usd == pytest.approx(0.75)
    assert reloaded.spent_tokens == 300
    assert reloaded.status == "ok"


def test_save_budget_creates_json_file(tmp_path):
    """save_budget should write a valid JSON file named {task_id}.json."""
    ledger = BudgetLedger(task_id="file-check", spent_usd=0.01)
    save_budget(ledger, budgets_dir=tmp_path)
    path = tmp_path / "file-check.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["task_id"] == "file-check"


def test_save_budget_atomic_write(tmp_path):
    """save_budget should not leave a .tmp file after completion."""
    ledger = BudgetLedger(task_id="atomic")
    save_budget(ledger, budgets_dir=tmp_path)
    tmp_file = tmp_path / "atomic.tmp"
    assert not tmp_file.exists()
    assert (tmp_path / "atomic.json").exists()
