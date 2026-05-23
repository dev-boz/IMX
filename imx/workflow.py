"""File-backed iterative workflow lifecycle per spec §10.5."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class WorkflowStep:
    id: str
    task_class: str
    risk_tier: str
    idempotency_key: str = ""
    depends_on: list[str] = field(default_factory=list)
    max_iterations: int = 1
    exit_when: str = "succeeded"


@dataclass
class WorkflowDefinition:
    schema_version: str
    name: str
    description: str = ""
    budget_max_cost_usd: float = 10.0
    budget_max_iterations: int = 20
    retry_policy: dict = field(default_factory=dict)
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass
class WorkflowState:
    schema_version: str = "0.6"
    workflow_id: str = ""
    definition_ref: str = ""
    current_step: str = ""
    attempt_count: int = 0
    iteration_count: int = 0
    lifecycle: str = "pending"  # pending/running/blocked/retrying/succeeded/failed/compensating/cancelled
    blocked_reason: str = ""
    resume_token: str = ""
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    step_history: list[dict] = field(default_factory=list)


def load_definition(definition_path: Path) -> WorkflowDefinition:
    """Read YAML and parse into WorkflowDefinition with list of WorkflowStep."""
    data = yaml.safe_load(definition_path.read_text(encoding="utf-8"))

    budget = data.get("budget", {})
    retry_policy = data.get("retry_policy", {})

    raw_steps = data.get("steps", [])
    steps = []
    for s in raw_steps:
        steps.append(WorkflowStep(
            id=s["id"],
            task_class=s.get("task_class", ""),
            risk_tier=s.get("risk_tier", "READ_ONLY"),
            idempotency_key=s.get("idempotency_key", ""),
            depends_on=s.get("depends_on", []),
            max_iterations=s.get("max_iterations", 1),
            exit_when=s.get("exit_when", "succeeded"),
        ))

    return WorkflowDefinition(
        schema_version=str(data.get("schema_version", "0.6")),
        name=data.get("name", ""),
        description=data.get("description", ""),
        budget_max_cost_usd=float(budget.get("max_cost_usd", 10.0)),
        budget_max_iterations=int(budget.get("max_iterations", 20)),
        retry_policy=retry_policy,
        steps=steps,
    )


def load_state(state_path: Path) -> WorkflowState:
    """Read JSON and parse into WorkflowState; return default if file missing."""
    if not state_path.exists():
        return WorkflowState()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    valid_fields = {f.name for f in dataclasses.fields(WorkflowState)}
    return WorkflowState(**{k: v for k, v in data.items() if k in valid_fields})


def save_state(state: WorkflowState, state_path: Path) -> None:
    """Atomic write (tmp + os.replace) of workflow state as JSON."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dataclasses.asdict(state), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, state_path)


def advance_workflow(
    definition: WorkflowDefinition,
    state: WorkflowState,
    *,
    step_id: str,
    outcome: str,
    task_id: str = "",
) -> WorkflowState:
    """Record step outcome and advance lifecycle. Returns new state (does not mutate)."""
    now = _utc_now()

    # Copy step_history and add new entry
    new_history = list(state.step_history)
    new_history.append({
        "step_id": step_id,
        "outcome": outcome,
        "started_at": state.updated_at or now,
        "completed_at": now,
        "task_id": task_id,
    })

    # Determine succeeded steps
    succeeded_steps = {
        entry["step_id"]
        for entry in new_history
        if entry["outcome"] == "succeeded"
    }

    # Determine next step: first step whose depends_on are all in succeeded_steps
    # and which hasn't been completed yet (not in step_history)
    completed_step_ids = {entry["step_id"] for entry in new_history}
    next_step = ""
    for step in definition.steps:
        if step.id in completed_step_ids:
            continue
        if all(dep in succeeded_steps for dep in step.depends_on):
            next_step = step.id
            break

    # Determine new lifecycle
    all_step_ids = {step.id for step in definition.steps}
    new_lifecycle = state.lifecycle
    new_completed_at = state.completed_at

    total_iterations = state.iteration_count + 1

    new_next_step: str
    new_blocked_reason: str
    new_completed_at: str = state.completed_at

    if total_iterations > definition.budget_max_iterations:
        new_lifecycle = "failed"
        new_completed_at = now
        new_next_step = state.current_step
        new_blocked_reason = "max_iterations"
    elif outcome == "failed":
        new_lifecycle = "failed"
        new_completed_at = now
        new_next_step = step_id
        new_blocked_reason = f"step {step_id} failed"
    elif not next_step and all_step_ids <= succeeded_steps:
        # All steps succeeded
        new_lifecycle = "succeeded"
        new_completed_at = now
        new_next_step = ""
        new_blocked_reason = ""
    else:
        new_lifecycle = "running"
        new_next_step = next_step
        new_blocked_reason = ""

    return WorkflowState(
        schema_version=state.schema_version,
        workflow_id=state.workflow_id,
        definition_ref=state.definition_ref,
        current_step=new_next_step,
        attempt_count=state.attempt_count + 1,
        iteration_count=total_iterations,
        lifecycle=new_lifecycle,
        blocked_reason=new_blocked_reason,
        resume_token=state.resume_token,
        started_at=state.started_at or now,
        updated_at=now,
        completed_at=new_completed_at,
        step_history=new_history,
    )


def create_checkpoint(state: WorkflowState, checkpoints_dir: Path) -> Path:
    """Write state as JSON to checkpoints_dir/checkpoint-{updated_at}.json."""
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    # Sanitize timestamp for use in filename
    ts = (state.updated_at or "unknown").replace(":", "-")
    checkpoint_path = checkpoints_dir / f"checkpoint-{ts}.json"
    checkpoint_path.write_text(
        json.dumps(dataclasses.asdict(state), indent=2) + "\n",
        encoding="utf-8",
    )
    return checkpoint_path
