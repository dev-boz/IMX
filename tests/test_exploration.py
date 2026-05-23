"""Tests for imx/exploration.py — ExplorationPolicy, ExplorationTracker, select_exploration_candidates."""
from __future__ import annotations

import json

import pytest

from imx.ema import EmaStore
from imx.exploration import (
    ExplorationPolicy,
    ExplorationState,
    ExplorationTracker,
    select_exploration_candidates,
)


# ---------------------------------------------------------------------------
# ExplorationPolicy
# ---------------------------------------------------------------------------


def test_exploration_policy_defaults():
    """Default policy should have sensible spec-compliant values."""
    policy = ExplorationPolicy()
    assert policy.traffic_pct == pytest.approx(0.1)
    assert policy.max_tasks == 20
    assert policy.max_days == 14
    assert policy.stop_when_confidence_gte == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# ExplorationTracker — save / load round-trip
# ---------------------------------------------------------------------------


def test_tracker_save_and_reload_round_trip(tmp_path):
    """State persisted via save() should be fully restored by a new tracker instance."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    tracker.record_exploration("node-1", "code_review")
    tracker.record_exploration("node-1", "code_review")

    reloaded = ExplorationTracker(state_path=path)
    key = "node-1||code_review"
    assert key in reloaded._states
    state = reloaded._states[key]
    assert state.tasks_explored == 2
    assert state.first_explored != ""
    assert state.active is True


def test_tracker_save_no_tmp_file_left(tmp_path):
    """Atomic save should not leave a .tmp file behind."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    tracker.record_exploration("node-x", "qa")
    assert not path.with_suffix(".tmp").exists()
    assert path.exists()


def test_tracker_load_tolerates_missing_file(tmp_path):
    """Constructing a tracker with no existing file should not raise."""
    path = tmp_path / "nonexistent.json"
    tracker = ExplorationTracker(state_path=path)
    assert tracker._states == {}


# ---------------------------------------------------------------------------
# ExplorationTracker — record_exploration
# ---------------------------------------------------------------------------


def test_record_exploration_increments_count(tmp_path):
    """Each call to record_exploration should increment tasks_explored by 1."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    tracker.record_exploration("node-a", "summarise")
    tracker.record_exploration("node-a", "summarise")
    tracker.record_exploration("node-a", "summarise")
    state = tracker._states["node-a||summarise"]
    assert state.tasks_explored == 3


def test_record_exploration_sets_first_explored_once(tmp_path):
    """first_explored should be set on the first call and not overwritten on subsequent calls."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    tracker.record_exploration("node-b", "translate")
    first = tracker._states["node-b||translate"].first_explored
    assert first != ""
    tracker.record_exploration("node-b", "translate")
    second = tracker._states["node-b||translate"].first_explored
    assert second == first


# ---------------------------------------------------------------------------
# ExplorationTracker — should_explore stop conditions
# ---------------------------------------------------------------------------


def test_should_explore_false_when_already_inactive(tmp_path):
    """An already-inactive state should short-circuit and return False."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    state = tracker._get_or_create("node-c", "debug")
    state.active = False
    policy = ExplorationPolicy(traffic_pct=1.0)
    assert tracker.should_explore("node-c", "debug", policy, current_composite=0.0) is False


def test_should_explore_false_and_deactivates_when_max_tasks_reached(tmp_path):
    """Reaching max_tasks should deactivate the state and return False."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    state = tracker._get_or_create("node-d", "refactor")
    state.tasks_explored = 5
    policy = ExplorationPolicy(max_tasks=5, traffic_pct=1.0)
    result = tracker.should_explore("node-d", "refactor", policy, current_composite=0.0)
    assert result is False
    assert tracker._states["node-d||refactor"].active is False


def test_should_explore_false_and_deactivates_when_confidence_threshold_reached(tmp_path):
    """Meeting stop_when_confidence_gte should deactivate and return False."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    tracker._get_or_create("node-e", "classify")
    policy = ExplorationPolicy(stop_when_confidence_gte=0.8, traffic_pct=1.0)
    result = tracker.should_explore("node-e", "classify", policy, current_composite=0.9)
    assert result is False
    assert tracker._states["node-e||classify"].active is False


def test_should_explore_false_and_deactivates_when_age_limit_exceeded(tmp_path):
    """A state whose first_explored is beyond max_days should deactivate and return False."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    state = tracker._get_or_create("node-f", "generate")
    # Force first_explored to be a very old timestamp
    state.first_explored = "2000-01-01T00:00:00Z"
    policy = ExplorationPolicy(max_days=14, traffic_pct=1.0)
    result = tracker.should_explore("node-f", "generate", policy, current_composite=0.0)
    assert result is False
    assert tracker._states["node-f||generate"].active is False


def test_should_explore_true_when_all_gates_pass_traffic_pct_one(tmp_path):
    """With traffic_pct=1.0 and no stop conditions triggered, should_explore returns True."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    policy = ExplorationPolicy(
        max_tasks=100,
        max_days=365,
        stop_when_confidence_gte=1.0,
        traffic_pct=1.0,
    )
    result = tracker.should_explore("node-g", "extract", policy, current_composite=0.0)
    assert result is True


def test_should_explore_false_when_traffic_pct_zero(tmp_path):
    """With traffic_pct=0.0 the probabilistic gate should always return False."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    policy = ExplorationPolicy(
        max_tasks=100,
        max_days=365,
        stop_when_confidence_gte=1.0,
        traffic_pct=0.0,
    )
    result = tracker.should_explore("node-h", "extract", policy, current_composite=0.0)
    assert result is False


def test_should_explore_deactivation_persists_across_reload(tmp_path):
    """After a stop condition deactivates a state, a fresh tracker should also see it inactive."""
    path = tmp_path / "exploration.json"
    tracker = ExplorationTracker(state_path=path)
    state = tracker._get_or_create("node-i", "translate")
    state.tasks_explored = 20
    policy = ExplorationPolicy(max_tasks=20, traffic_pct=1.0)
    tracker.should_explore("node-i", "translate", policy, current_composite=0.0)

    reloaded = ExplorationTracker(state_path=path)
    assert reloaded._states["node-i||translate"].active is False


# ---------------------------------------------------------------------------
# select_exploration_candidates
# ---------------------------------------------------------------------------


def test_select_exploration_candidates_returns_low_n_nodes(tmp_path):
    """Nodes with n < 10 and composite < threshold should be returned."""
    ema_store = EmaStore(path=tmp_path / "scores.json")
    policy = ExplorationPolicy(stop_when_confidence_gte=0.8)
    candidates = select_exploration_candidates(
        ["node-1", "node-2"], "code_review", ema_store, policy
    )
    # Both are brand-new (n=0, composite≈0.5) → eligible
    assert "node-1" in candidates
    assert "node-2" in candidates


def test_select_exploration_candidates_excludes_high_n_nodes(tmp_path):
    """Nodes with n >= 10 should be excluded regardless of composite score."""
    ema_store = EmaStore(path=tmp_path / "scores.json")
    for _ in range(10):
        ema_store.update("node-warm", "code_review", "", quality=0.3)
    policy = ExplorationPolicy(stop_when_confidence_gte=0.8)
    candidates = select_exploration_candidates(
        ["node-warm", "node-cold"], "code_review", ema_store, policy
    )
    assert "node-warm" not in candidates
    assert "node-cold" in candidates


def test_select_exploration_candidates_excludes_high_composite_nodes(tmp_path):
    """Nodes whose composite score meets the confidence threshold should be excluded."""
    ema_store = EmaStore(path=tmp_path / "scores.json")
    # Drive composite close to 1.0 via repeated perfect scores
    for _ in range(5):
        ema_store.update("node-confident", "qa", "", quality=1.0, stability=1.0, cost=0.0, latency=0.0)
    # Verify composite is high enough
    score = ema_store.get("node-confident", "qa", "")
    assert score.composite() >= 0.8

    policy = ExplorationPolicy(stop_when_confidence_gte=0.8)
    candidates = select_exploration_candidates(
        ["node-confident", "node-unknown"], "qa", ema_store, policy
    )
    assert "node-confident" not in candidates
    assert "node-unknown" in candidates


def test_select_exploration_candidates_empty_input(tmp_path):
    """Empty node_ids list should return an empty list."""
    ema_store = EmaStore(path=tmp_path / "scores.json")
    policy = ExplorationPolicy()
    result = select_exploration_candidates([], "any_task", ema_store, policy)
    assert result == []
