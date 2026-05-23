"""Tests for imx/workflow.py."""
import json
from pathlib import Path

import pytest

from imx.workflow import (
    WorkflowDefinition,
    WorkflowState,
    WorkflowStep,
    load_definition,
    load_state,
    save_state,
    advance_workflow,
    create_checkpoint,
)

DEFINITION_TEMPLATE = (
    Path(__file__).parent.parent / "catalog" / "workflows" / "definition.template.yaml"
)


def test_load_definition_parses_yaml():
    defn = load_definition(DEFINITION_TEMPLATE)
    assert isinstance(defn, WorkflowDefinition)
    assert defn.schema_version == "0.6"
    assert defn.name == "example-workflow"
    assert len(defn.steps) == 3
    step_ids = [s.id for s in defn.steps]
    assert "plan" in step_ids
    assert "implement" in step_ids
    assert "review" in step_ids


def test_load_state_missing_returns_default(tmp_path):
    state = load_state(tmp_path / "nonexistent.json")
    assert isinstance(state, WorkflowState)
    assert state.lifecycle == "pending"


def test_save_state_roundtrip(tmp_path):
    state_path = tmp_path / "state.json"
    original = WorkflowState(
        workflow_id="wf-42",
        lifecycle="running",
        current_step="plan",
        attempt_count=1,
        iteration_count=1,
    )
    save_state(original, state_path)
    loaded = load_state(state_path)

    assert loaded.workflow_id == original.workflow_id
    assert loaded.lifecycle == original.lifecycle
    assert loaded.current_step == original.current_step
    assert loaded.attempt_count == original.attempt_count
    assert loaded.iteration_count == original.iteration_count


def test_advance_workflow_records_step_history():
    defn = load_definition(DEFINITION_TEMPLATE)
    state = WorkflowState(workflow_id="wf-1")
    new_state = advance_workflow(defn, state, step_id="plan", outcome="succeeded")

    assert len(new_state.step_history) == 1
    assert new_state.step_history[0]["step_id"] == "plan"
    assert new_state.step_history[0]["outcome"] == "succeeded"


def test_advance_workflow_all_steps_done_sets_succeeded():
    defn = load_definition(DEFINITION_TEMPLATE)
    state = WorkflowState(workflow_id="wf-2")

    # Three steps: plan → implement → review (each with depends_on the previous)
    state = advance_workflow(defn, state, step_id="plan", outcome="succeeded")
    state = advance_workflow(defn, state, step_id="implement", outcome="succeeded")
    state = advance_workflow(defn, state, step_id="review", outcome="succeeded")

    assert state.lifecycle == "succeeded"
    assert len(state.step_history) == 3


def test_create_checkpoint_writes_file(tmp_path):
    checkpoints_dir = tmp_path / "checkpoints"
    state = WorkflowState(
        workflow_id="wf-3",
        lifecycle="running",
        updated_at="2024-01-01T00:00:00Z",
    )
    path = create_checkpoint(state, checkpoints_dir)

    assert path.exists()
    assert path.suffix == ".json"
    data = json.loads(path.read_text())
    assert data["workflow_id"] == "wf-3"
    assert data["lifecycle"] == "running"
