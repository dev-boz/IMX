"""Bounded exploration policy per spec §12.3."""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_PATH = Path.home() / ".imx" / "state" / "exploration.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(ts: str) -> datetime | None:
    """Parse an ISO8601 timestamp, returning None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@dataclass
class ExplorationPolicy:
    """Bounded exploration policy configuration per spec §12.3."""
    traffic_pct: float = 0.1                    # fraction of tasks to route to exploration candidates
    max_tasks: int = 20                          # stop exploring after this many tasks
    max_days: int = 14                           # stop exploring after this many days
    stop_when_confidence_gte: float = 0.8        # stop when composite score reaches this


@dataclass
class ExplorationState:
    """Per-node/task-class exploration tracking state."""
    node_id: str
    task_class: str
    tasks_explored: int = 0
    first_explored: str = ""    # ISO8601
    active: bool = True


class ExplorationTracker:
    """Tracks and gates exploration per node/task-class pair."""

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or DEFAULT_STATE_PATH
        self._states: dict[str, ExplorationState] = {}
        self._load()

    def _key(self, node_id: str, task_class: str) -> str:
        return f"{node_id}||{task_class}"

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for key, record in data.items():
                state = ExplorationState(**record)
                self._states[key] = state
        except Exception:
            pass

    def save(self) -> None:
        """Atomically persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({k: asdict(v) for k, v in self._states.items()}, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.state_path)

    def _get_or_create(self, node_id: str, task_class: str) -> ExplorationState:
        key = self._key(node_id, task_class)
        if key not in self._states:
            self._states[key] = ExplorationState(node_id=node_id, task_class=task_class)
        return self._states[key]

    def should_explore(
        self,
        node_id: str,
        task_class: str,
        policy: ExplorationPolicy,
        current_composite: float,
    ) -> bool:
        """Return True if this node/task_class should receive an exploration task this turn.

        Stop conditions are evaluated before the random traffic gate so inactive
        trackers do not needlessly roll.
        """
        state = self._get_or_create(node_id, task_class)

        # Already marked inactive — short-circuit
        if not state.active:
            return False

        # Stop condition: task count exhausted
        if state.tasks_explored >= policy.max_tasks:
            state.active = False
            self.save()
            return False

        # Stop condition: confidence reached threshold
        if current_composite >= policy.stop_when_confidence_gte:
            state.active = False
            self.save()
            return False

        # Stop condition: age limit
        if state.first_explored:
            t_first = _parse_ts(state.first_explored)
            if t_first is not None:
                t_now = datetime.now(timezone.utc)
                days_elapsed = (t_now - t_first).total_seconds() / 86400.0
                if days_elapsed > policy.max_days:
                    state.active = False
                    self.save()
                    return False

        # Traffic-pct gate (probabilistic)
        return random.random() < policy.traffic_pct

    def record_exploration(self, node_id: str, task_class: str) -> None:
        """Increment exploration count; set first_explored timestamp if not already set."""
        state = self._get_or_create(node_id, task_class)
        state.tasks_explored += 1
        if not state.first_explored:
            state.first_explored = _utc_now()
        self.save()


def select_exploration_candidates(
    node_ids: list[str],
    task_class: str,
    ema_store,
    policy: ExplorationPolicy,
) -> list[str]:
    """Return subset of node_ids eligible for exploration.

    Eligibility: composite score < policy.stop_when_confidence_gte AND observation count < 10.

    Args:
        node_ids: Candidate node IDs to evaluate.
        task_class: Task class being considered.
        ema_store: An EmaStore instance for composite score lookup.
        policy: The active ExplorationPolicy.

    Returns:
        List of node_ids that are eligible for exploration routing.
    """
    from .ema import EmaStore  # noqa: F401 — imported for type contract

    eligible: list[str] = []
    for node_id in node_ids:
        score = ema_store.get(node_id, task_class, "")
        if score.n < 10 and score.composite() < policy.stop_when_confidence_gte:
            eligible.append(node_id)
    return eligible
