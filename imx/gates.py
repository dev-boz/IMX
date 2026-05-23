"""Advisor-executor gate file protocol per IMX spec §10.7-10.8."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GateStage:
    PLAN = "plan"
    CORRECTION = "correction"
    PRE_COMMIT = "pre_commit"
    REVIEW = "review"


@dataclass
class GateFile:
    schema_version: str = "0.6"
    gate_id: str = ""
    task_id: str = ""
    stage: str = ""
    question: str = ""
    context_ref: str = ""
    options: list[str] = field(default_factory=list)
    requester: str = ""
    requested_at: str = ""
    ttl_seconds: int = 300


@dataclass
class GateAnswer:
    schema_version: str = "0.6"
    gate_id: str = ""
    task_id: str = ""
    stage: str = ""
    decision: str = ""
    rationale: str = ""
    responder: str = ""
    responded_at: str = ""
    modifications: dict = field(default_factory=dict)


@dataclass
class VoteRecord:
    schema_version: str = "0.6"
    vote_id: str = ""
    gate_id: str = ""
    votes: list[dict] = field(default_factory=list)
    tally: dict = field(default_factory=dict)
    outcome: str = ""
    resolved_at: str = ""


def _atomic_write_json(data: dict, path: Path) -> None:
    """Write JSON atomically using tmp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_gate_file(gate: GateFile, gates_dir: Path) -> Path:
    """Write a GateFile to disk atomically. Returns the file path."""
    path = gates_dir / f"gate-{gate.task_id}-{gate.stage}.json"
    _atomic_write_json(dataclasses.asdict(gate), path)
    return path


def read_gate_file(task_id: str, stage: str, gates_dir: Path) -> GateFile | None:
    """Read a GateFile from disk. Returns None if missing."""
    path = gates_dir / f"gate-{task_id}-{stage}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return GateFile(**json.load(f))


def write_gate_answer(answer: GateAnswer, gates_dir: Path) -> Path:
    """Write a GateAnswer to disk atomically. Returns the file path."""
    path = gates_dir / f"gate-{answer.task_id}-{answer.stage}.response.json"
    _atomic_write_json(dataclasses.asdict(answer), path)
    return path


def read_gate_answer(task_id: str, stage: str, gates_dir: Path) -> GateAnswer | None:
    """Read a GateAnswer from disk. Returns None if missing."""
    path = gates_dir / f"gate-{task_id}-{stage}.response.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return GateAnswer(**json.load(f))


def is_gate_expired(gate: GateFile) -> bool:
    """Return True if the gate has passed its TTL."""
    if not gate.requested_at:
        return False
    requested = datetime.fromisoformat(gate.requested_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    elapsed = (now - requested).total_seconds()
    return elapsed > gate.ttl_seconds


def aggregate_votes(votes: list[GateAnswer]) -> VoteRecord:
    """Count decisions across all answers and return a VoteRecord."""
    tally: dict[str, int] = {}
    vote_entries: list[dict] = []
    for answer in votes:
        decision = answer.decision
        tally[decision] = tally.get(decision, 0) + 1
        vote_entries.append({
            "responder": answer.responder,
            "decision": decision,
            "confidence": 1.0,
        })

    # Determine outcome: highest count; tie-break: prefer "approve" over "deny"
    outcome = ""
    if tally:
        max_count = max(tally.values())
        winners = [d for d, c in tally.items() if c == max_count]
        if len(winners) == 1:
            outcome = winners[0]
        elif "approve" in winners:
            outcome = "approve"
        else:
            outcome = winners[0]

    gate_id = votes[0].gate_id if votes else ""
    return VoteRecord(
        gate_id=gate_id,
        votes=vote_entries,
        tally=tally,
        outcome=outcome,
        resolved_at=_utc_now(),
    )


def write_vote_record(vote: VoteRecord, gates_dir: Path) -> Path:
    """Write a VoteRecord to disk atomically. Returns the file path."""
    path = gates_dir / f"vote-{vote.gate_id}.json"
    _atomic_write_json(dataclasses.asdict(vote), path)
    return path


def write_gate_vote(answer: GateAnswer, gates_dir: Path) -> Path:
    """Write one voter's answer for multi-model voting.

    Filename: gate-{task_id}-{stage}-{responder}.vote.json
    Multiple voters can each write their own file; collect with collect_gate_votes().
    """
    responder_slug = answer.responder.replace("/", "-").replace("@", "_")
    path = gates_dir / f"gate-{answer.task_id}-{answer.stage}-{responder_slug}.vote.json"
    _atomic_write_json(dataclasses.asdict(answer), path)
    return path


def collect_gate_votes(task_id: str, stage: str, gates_dir: Path) -> list[GateAnswer]:
    """Collect all vote files for a gate across multiple responders."""
    pattern = f"gate-{task_id}-{stage}-*.vote.json"
    answers = []
    for path in sorted(gates_dir.glob(pattern)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            answers.append(GateAnswer(**{k: v for k, v in data.items() if k in GateAnswer.__dataclass_fields__}))
        except Exception:
            continue
    return answers


def run_vote_and_record(task_id: str, stage: str, gates_dir: Path) -> VoteRecord | None:
    """Collect all votes for a gate, aggregate, and write a VoteRecord.

    Returns None if no votes found.
    """
    votes = collect_gate_votes(task_id, stage, gates_dir)
    if not votes:
        return None
    record = aggregate_votes(votes)
    write_vote_record(record, gates_dir)
    return record


def create_gate(
    task_id: str,
    stage: str,
    question: str,
    requester: str,
    *,
    gates_dir: Path,
    context_ref: str = "",
    options: list[str] | None = None,
    ttl_seconds: int = 300,
) -> GateFile:
    """Build a GateFile, write it, and return it."""
    gate = GateFile(
        gate_id=f"{task_id}-{stage}",
        task_id=task_id,
        stage=stage,
        question=question,
        context_ref=context_ref,
        options=options or [],
        requester=requester,
        requested_at=_utc_now(),
        ttl_seconds=ttl_seconds,
    )
    write_gate_file(gate, gates_dir)
    return gate
