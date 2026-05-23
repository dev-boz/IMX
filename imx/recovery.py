"""Recovery policy enforcement per IMX spec §15.1."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RecoveryPolicy:
    max_retries_per_step: int = 2
    backoff_seconds: int = 30
    no_retry_on: list[str] = field(default_factory=lambda: ["infrastructure", "quota_exceeded"])
    fallback_chain: list[str] = field(default_factory=list)
    cooldown_seconds: int = 300  # node goes into cooldown after exhausting retries


class RecoveryLedger:
    """Tracks retry counts and cooldowns per node per task class."""

    def __init__(self, path: Path | None = None):
        self._path = path or (Path.home() / ".imx" / "state" / "recovery_ledger.json")
        self._data: dict = {}  # node_id -> {"retries": {task_class: N}, "cooldown_until": ISO8601|None}
        self._load()

    def increment_retry(self, node_id: str, task_class: str) -> int:
        """Increment retry count for node_id/task_class. Returns new count."""
        node = self._data.setdefault(node_id, {"retries": {}, "cooldown_until": None})
        node["retries"][task_class] = node["retries"].get(task_class, 0) + 1
        self.save()
        return node["retries"][task_class]

    def get_retry_count(self, node_id: str, task_class: str) -> int:
        """Return current retry count or 0 if not tracked."""
        node = self._data.get(node_id, {})
        return node.get("retries", {}).get(task_class, 0)

    def set_cooldown(self, node_id: str, cooldown_seconds: int) -> None:
        """Set cooldown_until for node_id to now + cooldown_seconds."""
        node = self._data.setdefault(node_id, {"retries": {}, "cooldown_until": None})
        until = datetime.now(timezone.utc).timestamp() + cooldown_seconds
        node["cooldown_until"] = datetime.fromtimestamp(until, tz=timezone.utc).isoformat()
        self.save()

    def is_in_cooldown(self, node_id: str) -> bool:
        """Return True if node is currently in cooldown."""
        node = self._data.get(node_id, {})
        cooldown_until = node.get("cooldown_until")
        if not cooldown_until:
            return False
        try:
            until_dt = datetime.fromisoformat(cooldown_until)
            return datetime.now(timezone.utc) < until_dt
        except (ValueError, TypeError):
            return False

    def reset_retries(self, node_id: str, task_class: str) -> None:
        """Reset retry count to 0 (call on success)."""
        node = self._data.setdefault(node_id, {"retries": {}, "cooldown_until": None})
        node["retries"][task_class] = 0
        self.save()

    def save(self) -> None:
        """Atomic write of ledger to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2) + "\n")
        os.replace(tmp, self._path)

    def _load(self) -> None:
        """Load ledger from disk if it exists."""
        if not self._path.exists():
            return
        try:
            self._data = json.loads(self._path.read_text())
        except Exception:
            self._data = {}


def should_retry(failure_type: str, retry_count: int, policy: RecoveryPolicy) -> bool:
    """Return True if the failure is eligible for retry under the given policy."""
    if failure_type in policy.no_retry_on:
        return False
    if retry_count >= policy.max_retries_per_step:
        return False
    return True


def select_fallback(
    failed_node_id: str,
    policy: RecoveryPolicy,
    ledger: RecoveryLedger,
) -> str | None:
    """Return first fallback node not in cooldown, or None if all are cooling or chain is empty."""
    for node_id in policy.fallback_chain:
        if not ledger.is_in_cooldown(node_id):
            return node_id
    return None


def apply_recovery(
    node_id: str,
    task_class: str,
    failure_type: str,
    policy: RecoveryPolicy,
    ledger: RecoveryLedger,
) -> dict:
    """Apply recovery logic and return an action dict.

    Returns one of:
      {"action": "retry", "node_id": ..., "backoff_seconds": ...}
      {"action": "fallback", "node_id": ...}
      {"action": "abort", "reason": ...}
    """
    new_count = ledger.increment_retry(node_id, task_class)
    if should_retry(failure_type, new_count, policy):
        return {
            "action": "retry",
            "node_id": node_id,
            "backoff_seconds": policy.backoff_seconds,
        }
    # Retries exhausted — put node in cooldown
    ledger.set_cooldown(node_id, policy.cooldown_seconds)
    fallback_id = select_fallback(node_id, policy, ledger)
    if fallback_id is not None:
        return {"action": "fallback", "node_id": fallback_id}
    return {"action": "abort", "reason": "retries exhausted, no fallback available"}


def load_recovery_policy(profile_dict: dict) -> RecoveryPolicy:
    """Parse a profile dict's retry_policy section into a RecoveryPolicy."""
    retry_policy = profile_dict.get("retry_policy", {})
    kwargs: dict = {}
    if "max_retries_per_step" in retry_policy:
        kwargs["max_retries_per_step"] = int(retry_policy["max_retries_per_step"])
    if "backoff_seconds" in retry_policy:
        kwargs["backoff_seconds"] = int(retry_policy["backoff_seconds"])
    if "no_retry_on" in retry_policy:
        kwargs["no_retry_on"] = list(retry_policy["no_retry_on"])
    if "fallback_chain" in retry_policy:
        kwargs["fallback_chain"] = list(retry_policy["fallback_chain"])
    if "cooldown_seconds" in retry_policy:
        kwargs["cooldown_seconds"] = int(retry_policy["cooldown_seconds"])
    return RecoveryPolicy(**kwargs)
