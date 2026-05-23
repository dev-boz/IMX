"""Harness drift detection and confidence reset per IMX spec §6.1."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ema import EmaStore

FINGERPRINT_REGISTRY_PATH: Path = Path.home() / ".imx" / "state" / "harness_fingerprints.json"

DEFAULT_TELEMETRY_DIR: Path = Path.home() / ".imx" / "telemetry"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class HarnessDriftRecord:
    node_id: str
    old_fingerprint: str
    new_fingerprint: str
    detected_at: str            # ISO8601
    reset_applied: bool = False
    reset_factor: float = 0.5
    scores_reset: int = 0


def load_fingerprint_registry(path: Path | None = None) -> dict[str, str]:
    """Load node_id → fingerprint mapping from JSON file.

    Returns empty dict if the file does not exist.
    """
    p = path or FINGERPRINT_REGISTRY_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_fingerprint_registry(registry: dict[str, str], path: Path | None = None) -> None:
    """Atomically write the fingerprint registry to disk (tmp + os.replace)."""
    p = path or FINGERPRINT_REGISTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def detect_drift(node_id: str, new_fingerprint: str, *, registry: dict[str, str]) -> bool:
    """Return True if the registry records a *different* fingerprint for node_id.

    Returns False when the node is not yet registered (first registration) or
    when the fingerprint is unchanged.
    """
    existing = registry.get(node_id)
    if existing is None:
        return False
    return existing != new_fingerprint


def apply_drift_reset(
    node_id: str,
    new_fingerprint: str,
    ema_store,
    *,
    registry: dict[str, str],
    reset_factor: float = 0.5,
) -> HarnessDriftRecord | None:
    """Apply an EMA confidence reset if harness drift is detected for node_id.

    Mutates registry in-place to record the new fingerprint.

    Returns a HarnessDriftRecord if drift was detected and reset applied,
    None if no drift was detected (first registration or unchanged fingerprint).
    """
    if not detect_drift(node_id, new_fingerprint, registry=registry):
        # first registration or same fingerprint — just record it
        registry[node_id] = new_fingerprint
        return None

    old_fingerprint = registry[node_id]
    scores_reset = ema_store.apply_drift_reset(node_id, old_fingerprint, reset_factor)
    registry[node_id] = new_fingerprint

    return HarnessDriftRecord(
        node_id=node_id,
        old_fingerprint=old_fingerprint,
        new_fingerprint=new_fingerprint,
        detected_at=_utc_now(),
        reset_applied=True,
        reset_factor=reset_factor,
        scores_reset=scores_reset,
    )


def check_and_apply_drift(
    node_id: str,
    new_fingerprint: str,
    ema_store,
    *,
    registry_path: Path | None = None,
    reset_factor: float = 0.5,
) -> HarnessDriftRecord | None:
    """Convenience: load registry, detect+apply drift, save registry, return record."""
    registry = load_fingerprint_registry(registry_path)
    record = apply_drift_reset(
        node_id,
        new_fingerprint,
        ema_store,
        registry=registry,
        reset_factor=reset_factor,
    )
    save_fingerprint_registry(registry, registry_path)
    return record


def append_drift_record(
    record: HarnessDriftRecord,
    *,
    telemetry_dir: Path | None = None,
) -> None:
    """Append a HarnessDriftRecord to harness_drift.jsonl (fsync)."""
    d = telemetry_dir or DEFAULT_TELEMETRY_DIR
    d.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dataclasses.asdict(record), ensure_ascii=True) + "\n"
    path = d / "harness_drift.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
