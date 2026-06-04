"""Harness-drift confidence reset is triggered from the router observe path (spec §6.1)."""
import json
from pathlib import Path

from imx.ema import EmaStore
from imx.router import ImxRouter

CATALOG = Path(__file__).parent.parent / "catalog"


def _drift_router(tmp_path: Path) -> tuple[ImxRouter, EmaStore]:
    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=CATALOG,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
        quota_dir=tmp_path / "quota",
        budgets_dir=tmp_path / "budgets",
        approvals_dir=tmp_path / "approvals",
        demo_dir=tmp_path / "demo",
        fingerprint_registry_path=tmp_path / "harness_fingerprints.json",
    )
    return router, ema


def _observe(router, *, fp, task="t"):
    router.observe(
        task_id=task,
        node_id="ro-good",
        task_class="analysis",
        harness_fingerprint=fp,
        outcome="succeeded",
        quality_score=1.0,
    )


def test_fingerprint_change_triggers_drift_reset_and_telemetry(tmp_path):
    router, ema = _drift_router(tmp_path)
    drift_log = tmp_path / "telemetry" / "harness_drift.jsonl"

    # Build up confidence under the first fingerprint. No drift on first registration.
    for i in range(5):
        _observe(router, fp="cc-1.0.72-a3f2", task=f"t{i}")
    assert ema.get("ro-good", "analysis", "cc-1.0.72-a3f2").n == 5
    assert not drift_log.exists()

    # A changed fingerprint is a drift event: prior scores reset + record written.
    _observe(router, fp="cc-1.1.0-b9d1", task="t-new")

    assert drift_log.exists()
    record = json.loads(drift_log.read_text(encoding="utf-8").splitlines()[0])
    assert record["node_id"] == "ro-good"
    assert record["old_fingerprint"] == "cc-1.0.72-a3f2"
    assert record["new_fingerprint"] == "cc-1.1.0-b9d1"
    assert record["reset_applied"] is True
    assert record["scores_reset"] >= 1


def test_same_fingerprint_does_not_trigger_drift(tmp_path):
    router, _ema = _drift_router(tmp_path)
    drift_log = tmp_path / "telemetry" / "harness_drift.jsonl"

    _observe(router, fp="cc-1.0.72-a3f2", task="a")
    _observe(router, fp="cc-1.0.72-a3f2", task="b")

    assert not drift_log.exists()


def test_empty_fingerprint_skips_drift_machinery(tmp_path):
    router, _ema = _drift_router(tmp_path)

    router.observe(
        task_id="t",
        node_id="ro-good",
        task_class="analysis",
        outcome="succeeded",
        quality_score=1.0,
    )

    # No registry file is created when no fingerprint is supplied.
    assert not (tmp_path / "harness_fingerprints.json").exists()
