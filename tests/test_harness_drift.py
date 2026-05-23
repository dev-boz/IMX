"""Tests for imx/harness_drift.py."""
import json
from pathlib import Path

import pytest

from imx.ema import EmaStore
from imx.harness_drift import (
    detect_drift,
    apply_drift_reset,
    check_and_apply_drift,
    load_fingerprint_registry,
    save_fingerprint_registry,
)


def test_detect_drift_no_prior_registry_is_not_drift():
    registry = {}
    assert detect_drift("node-1", "fp-abc", registry=registry) is False


def test_detect_drift_same_fingerprint_is_not_drift():
    registry = {"node-1": "fp-abc"}
    assert detect_drift("node-1", "fp-abc", registry=registry) is False


def test_detect_drift_changed_fingerprint_is_drift():
    registry = {"node-1": "fp-abc"}
    assert detect_drift("node-1", "fp-xyz", registry=registry) is True


def test_apply_drift_reset_updates_registry(tmp_path):
    ema_store = EmaStore(path=tmp_path / "scores.json")
    # Seed a score so apply_drift_reset has something to reset
    ema_store.update("node-1", "planning", "fp-abc", quality=0.8)

    registry = {"node-1": "fp-abc"}
    record = apply_drift_reset(
        "node-1",
        "fp-xyz",
        ema_store,
        registry=registry,
    )

    # Registry must now store the new fingerprint
    assert registry["node-1"] == "fp-xyz"
    # A drift record is returned because the fingerprint changed
    assert record is not None
    assert record.reset_applied is True
    assert record.node_id == "node-1"
    assert record.old_fingerprint == "fp-abc"
    assert record.new_fingerprint == "fp-xyz"


def test_check_and_apply_drift_persists_to_file(tmp_path):
    registry_file = tmp_path / "harness_fingerprints.json"
    scores_file = tmp_path / "scores.json"

    ema_store = EmaStore(path=scores_file)
    ema_store.update("node-2", "planning", "fp-old", quality=0.9)

    # Register the old fingerprint first
    save_fingerprint_registry({"node-2": "fp-old"}, registry_file)

    # Now call with a new fingerprint — should detect drift and persist
    record = check_and_apply_drift(
        "node-2",
        "fp-new",
        ema_store,
        registry_path=registry_file,
    )

    assert record is not None
    assert record.old_fingerprint == "fp-old"
    assert record.new_fingerprint == "fp-new"

    # The JSON file must have been updated
    persisted = json.loads(registry_file.read_text())
    assert persisted["node-2"] == "fp-new"
