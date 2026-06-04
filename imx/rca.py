"""Root-cause analysis (RCA) record writing per IMX spec §13.1."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RCA_DIR: Path = Path.home() / ".imx" / "telemetry" / "rca"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class RcaRecord:
    schema_version: str = "0.6"
    task_id: str = ""
    node_id: str = ""
    task_class: str = ""
    failure_type: str = ""
    controllability: str = ""
    root_cause_hypothesis: str = ""
    contributing_factors: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    chain_depth: int = 0
    recorded_at: str = ""


def write_rca_record(record: RcaRecord, *, rca_dir: Path | None = None) -> Path:
    """Atomically write an RcaRecord to {rca_dir}/{task_id}.json. Returns the path."""
    d = rca_dir or DEFAULT_RCA_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record.task_id}.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dataclasses.asdict(record), f, ensure_ascii=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def read_rca_record(task_id: str, *, rca_dir: Path | None = None) -> RcaRecord | None:
    """Read an RcaRecord from disk. Returns None if missing."""
    d = rca_dir or DEFAULT_RCA_DIR
    path = d / f"{task_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return RcaRecord(**json.load(f))


def classify_failure(failure_type: str, error_message: str = "") -> dict:
    """Classify a failure into controllability, hypothesis, and factors.

    ``failure_type`` follows the IMX spec §12.5 taxonomy:
    ``context_exceeded``, ``capability_gap``, ``quality_failure``,
    ``refusal``, ``timeout``, ``infrastructure``, ``cascade``.
    """
    msg = error_message.lower()

    # infrastructure covers API down, quota, network, and tool-unavailable.
    if failure_type == "infrastructure" or any(
        kw in msg for kw in ("connection", "network", "quota", "503", "unavailable")
    ):
        return {
            "controllability": "uncontrollable",
            "hypothesis": "infrastructure, quota, or network failure",
            "factors": [],
        }
    if failure_type == "timeout" or "timeout" in msg or "timed out" in msg:
        return {
            "controllability": "uncontrollable",
            "hypothesis": "wall-clock or lease deadline exceeded",
            "factors": [],
        }
    if failure_type == "cascade":
        return {
            "controllability": "cascade",
            "hypothesis": "failure propagated from an upstream artifact",
            "factors": [],
        }
    if failure_type == "refusal":
        return {
            "controllability": "controllable",
            "hypothesis": "node refused or over-blocked the request",
            "factors": [],
        }
    if failure_type == "quality_failure":
        return {
            "controllability": "controllable",
            "hypothesis": "output completed but failed the rubric",
            "factors": [],
        }
    if failure_type == "capability_gap":
        return {
            "controllability": "controllable",
            "hypothesis": "node lacks the required skill for this task class",
            "factors": [],
        }
    if failure_type == "context_exceeded":
        return {
            "controllability": "controllable",
            "hypothesis": "node ran out of usable context",
            "factors": [],
        }
    return {
        "controllability": "unknown",
        "hypothesis": "unclassified failure",
        "factors": [],
    }


def create_rca(
    task_id: str,
    node_id: str,
    task_class: str,
    failure_type: str,
    error_message: str = "",
    chain_depth: int = 0,
    evidence: dict | None = None,
    *,
    rca_dir: Path | None = None,
) -> RcaRecord:
    """Classify, build, write, and return an RcaRecord."""
    classification = classify_failure(failure_type, error_message)
    record = RcaRecord(
        task_id=task_id,
        node_id=node_id,
        task_class=task_class,
        failure_type=failure_type,
        controllability=classification["controllability"],
        root_cause_hypothesis=classification["hypothesis"],
        contributing_factors=classification["factors"],
        evidence=evidence or {},
        chain_depth=chain_depth,
        recorded_at=_utc_now(),
    )
    write_rca_record(record, rca_dir=rca_dir)
    return record
