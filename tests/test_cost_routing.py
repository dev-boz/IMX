"""Tests for imx/cost_routing.py."""
import json

import pytest

from imx.cost_routing import cost_score, aggregate_cost_by_task_class


def test_cost_score_under_budget():
    # cost=0.1, budget=1.0 → score = 1.0 - 0.1/1.0 = 0.9
    result = cost_score(estimated_cost_usd=0.1, budget_max_usd=1.0)
    assert result == pytest.approx(0.9)


def test_cost_score_at_budget():
    # cost=1.0, budget=1.0 → score = 1.0 - 1.0 = 0.0
    result = cost_score(estimated_cost_usd=1.0, budget_max_usd=1.0)
    assert result == pytest.approx(0.0)


def test_cost_score_no_budget_returns_half():
    # budget=0.0 → returns 0.5
    result = cost_score(estimated_cost_usd=0.5, budget_max_usd=0.0)
    assert result == pytest.approx(0.5)


def test_aggregate_cost_by_task_class_empty_file(tmp_path):
    tasks_file = tmp_path / "tasks.jsonl"
    tasks_file.write_text("")  # empty file
    result = aggregate_cost_by_task_class(telemetry_dir=tmp_path)
    assert result == {}


def test_aggregate_cost_by_task_class_single_record(tmp_path):
    tasks_file = tmp_path / "tasks.jsonl"
    record = {
        "task_id": "t-1",
        "task_class": "planning",
        "estimated_cost_usd": 0.05,
    }
    tasks_file.write_text(json.dumps(record) + "\n")

    result = aggregate_cost_by_task_class(telemetry_dir=tmp_path)
    assert "planning" in result
    assert result["planning"]["task_count"] == 1
    assert result["planning"]["total_cost_usd"] == pytest.approx(0.05)
    assert result["planning"]["avg_cost_usd"] == pytest.approx(0.05)
