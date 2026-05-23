"""AIP ↔ IMX event correlation per spec §13.1."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(ts: str) -> datetime | None:
    """Parse an ISO8601 timestamp string, returning None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def read_aip_events(events_path: Path, *, since: str | None = None) -> list[dict]:
    """Read workspace/events.jsonl and return parsed event dicts.

    Args:
        events_path: Path to the events.jsonl file.
        since: Optional ISO8601 string; if provided, only events with ts >= since are returned.

    Returns:
        List of event dicts (malformed lines silently skipped).
    """
    if not events_path.exists():
        return []

    events: list[dict] = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if since is not None:
                ts = record.get("ts", "")
                if not ts or ts < since:
                    continue
            events.append(record)

    return events


def _map_outcome(status: str, message: str) -> tuple[str, str]:
    """Map AIP status string to (outcome, outcome_class) tuple."""
    status_map = {
        "finished": "succeeded",
        "failed": "failed",
        "blocked": "partial",
    }
    outcome = status_map.get(status, "unknown")

    outcome_class = "controllable"
    if outcome == "failed":
        msg_lower = (message or "").lower()
        if any(kw in msg_lower for kw in ("infrastructure", "timeout", "network")):
            outcome_class = "uncontrollable"

    return outcome, outcome_class


def correlate_events(events: list[dict], route_decisions: list[dict]) -> list[dict]:
    """Match AIP events to route decisions and produce IMX telemetry records.

    Args:
        events: List of AIP event dicts from events.jsonl.
        route_decisions: List of route decision dicts.

    Returns:
        List of IMX telemetry record dicts.
    """
    # Index route decisions by task_id for fast lookup
    decisions_by_task: dict[str, dict] = {}
    for decision in route_decisions:
        tid = decision.get("task_id")
        if tid:
            decisions_by_task[tid] = decision

    # Group events by task_id
    events_by_task: dict[str, list[dict]] = {}
    unkeyed: list[dict] = []
    for event in events:
        tid = event.get("task")
        if tid:
            events_by_task.setdefault(tid, []).append(event)
        else:
            unkeyed.append(event)

    records: list[dict] = []

    # All task_ids seen either in events or decisions
    all_task_ids = set(events_by_task.keys()) | set(decisions_by_task.keys())

    for task_id in all_task_ids:
        task_events = events_by_task.get(task_id, [])
        decision = decisions_by_task.get(task_id)

        # Node/class info from route decision
        node_id = decision.get("node_id") if decision else None
        task_class = decision.get("task_class") if decision else None
        chain_depth = decision.get("chain_depth", 0) if decision else 0
        correlation_status = "full" if decision else "partial"

        # Agent from events
        agents = list({e.get("agent") for e in task_events if e.get("agent")})
        agent = agents[0] if len(agents) == 1 else (agents if agents else None)

        # Sort events by ts for started_at / completed_at
        def _ts_sort_key(e: dict) -> str:
            return e.get("ts", "")

        sorted_events = sorted(task_events, key=_ts_sort_key)
        started_at = sorted_events[0].get("ts") if sorted_events else None
        completed_at = sorted_events[-1].get("ts") if sorted_events else None

        # Duration
        duration_ms: int | None = None
        if started_at and completed_at:
            t_start = _parse_ts(started_at)
            t_end = _parse_ts(completed_at)
            if t_start is not None and t_end is not None:
                delta = (t_end - t_start).total_seconds()
                duration_ms = int(delta * 1000)

        # Outcome: use status of the last event with a known status
        outcome = "unknown"
        outcome_class = "controllable"
        for ev in reversed(sorted_events):
            status = ev.get("status", "")
            if status:
                message = ev.get("message", "")
                outcome, outcome_class = _map_outcome(status, message)
                break

        # summary_ref: file field from any export event
        summary_ref: str | None = None
        for ev in task_events:
            if ev.get("event") == "export" and ev.get("file"):
                summary_ref = ev["file"]
                break

        # missing_fields
        missing_fields: list[str] = []
        if node_id is None:
            missing_fields.append("node_id")
        if task_class is None:
            missing_fields.append("task_class")
        if not agent:
            missing_fields.append("agent")
        if not started_at:
            missing_fields.append("started_at")
        if not completed_at:
            missing_fields.append("completed_at")

        record = {
            "schema_version": "0.6",
            "task_id": task_id,
            "node_id": node_id,
            "task_class": task_class,
            "agent": agent,
            "outcome": outcome,
            "outcome_class": outcome_class,
            "chain_depth": chain_depth,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "summary_ref": summary_ref,
            "correlation_status": correlation_status,
            "missing_fields": missing_fields,
        }
        records.append(record)

    return records


def read_route_decisions(decisions_dir: Path) -> list[dict]:
    """Read all JSON files from a route-decisions directory.

    Args:
        decisions_dir: Directory containing JSON route-decision files.

    Returns:
        List of decision dicts (non-JSON files silently skipped).
    """
    if not decisions_dir.exists() or not decisions_dir.is_dir():
        return []

    decisions: list[dict] = []
    for json_file in decisions_dir.iterdir():
        if json_file.suffix != ".json":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                decisions.append(data)
        except (json.JSONDecodeError, OSError):
            continue

    return decisions


def correlate_workspace(
    workspace_root: Path,
    route_decisions_dir: Path | None = None,
    telemetry_dir: Path | None = None,
) -> int:
    """Correlate AIP events with route decisions and write telemetry records.

    Args:
        workspace_root: Root of the AIP workspace; reads workspace_root/events.jsonl.
        route_decisions_dir: Directory of JSON route decision files. Defaults to
            workspace_root/route-decisions/.
        telemetry_dir: Where to write task telemetry. Defaults to ~/.imx/telemetry/.

    Returns:
        Number of telemetry records written.
    """
    from .telemetry import append_task_record

    events_path = workspace_root / "events.jsonl"
    decisions_dir = route_decisions_dir or (workspace_root / "route-decisions")
    telem_dir = telemetry_dir or (Path.home() / ".imx" / "telemetry")

    events = read_aip_events(events_path)
    route_decisions = read_route_decisions(decisions_dir)
    records = correlate_events(events, route_decisions)

    for record in records:
        append_task_record(record, telemetry_dir=telem_dir)

    return len(records)
