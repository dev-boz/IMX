"""Task outcome telemetry per spec §13."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TELEMETRY_DIR = Path.home() / ".imx" / "telemetry"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_task_record(record: dict, telemetry_dir: Path | None = None) -> None:
    """Atomically append a task outcome record to tasks.jsonl."""
    d = telemetry_dir or DEFAULT_TELEMETRY_DIR
    d.mkdir(parents=True, exist_ok=True)
    record.setdefault("schema_version", "0.6")
    record.setdefault("recorded_at", _utc_now())
    line = json.dumps(record, ensure_ascii=True) + "\n"
    path = d / "tasks.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def append_route_decision(decision_dict: dict, telemetry_dir: Path | None = None) -> None:
    """Append a route decision record to route_decisions.jsonl."""
    d = telemetry_dir or DEFAULT_TELEMETRY_DIR
    d.mkdir(parents=True, exist_ok=True)
    decision_dict.setdefault("schema_version", "0.6")
    decision_dict.setdefault("decided_at", _utc_now())
    line = json.dumps(decision_dict, ensure_ascii=True) + "\n"
    path = d / "route_decisions.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def append_dream_trigger(trigger_type: str, *, source: str = "imx-router",
                          query: str = "", context: dict | None = None,
                          telemetry_dir: Path | None = None) -> None:
    """Write a dream trigger record for gitmem per spec §11.3."""
    d = telemetry_dir or (Path.home() / ".imx" / "state")
    d.mkdir(parents=True, exist_ok=True)
    record = {
        "trigger_type": trigger_type,
        "source": source,
        "query": query,
        "context": context or {},
        "ts": _utc_now(),
    }
    path = d / "dream-triggers.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")
        f.flush()
