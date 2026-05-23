"""Tests for imx/rca.py."""
import pytest

from imx.rca import (
    classify_failure,
    create_rca,
    read_rca_record,
    write_rca_record,
    RcaRecord,
)


def test_classify_failure_infrastructure():
    result = classify_failure("infrastructure")
    assert result["controllability"] == "uncontrollable"


def test_classify_failure_model_refusal():
    result = classify_failure("model_refusal")
    assert result["controllability"] == "controllable"


def test_classify_failure_default():
    result = classify_failure("weird_error")
    assert result["controllability"] == "unknown"


def test_create_rca_writes_file(tmp_path):
    rca_dir = tmp_path / "rca"
    record = create_rca(
        task_id="task-101",
        node_id="node-a",
        task_class="planning",
        failure_type="model_refusal",
        rca_dir=rca_dir,
    )
    expected_file = rca_dir / "task-101.json"
    assert expected_file.exists()
    assert record.task_id == "task-101"
    assert record.controllability == "controllable"


def test_read_rca_record_roundtrip(tmp_path):
    rca_dir = tmp_path / "rca"
    create_rca(
        task_id="task-202",
        node_id="node-b",
        task_class="implementation",
        failure_type="incorrect_output",
        error_message="bad JSON",
        rca_dir=rca_dir,
    )
    loaded = read_rca_record("task-202", rca_dir=rca_dir)
    assert loaded is not None
    assert loaded.task_id == "task-202"
    assert loaded.node_id == "node-b"
    assert loaded.task_class == "implementation"
    assert loaded.failure_type == "incorrect_output"
    assert loaded.controllability == "controllable"


def test_read_rca_record_missing_returns_none(tmp_path):
    rca_dir = tmp_path / "rca"
    rca_dir.mkdir()
    result = read_rca_record("nonexistent-task", rca_dir=rca_dir)
    assert result is None
