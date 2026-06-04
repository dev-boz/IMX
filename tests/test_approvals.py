"""Tests for imx/approvals.py — EXTERNAL approval and demo-artifact checks."""
from dataclasses import dataclass

from imx.approvals import (
    check_external_approval,
    profile_exempts_external,
    read_approval,
    write_approval,
)


@dataclass
class _Profile:
    approval_required_for: list


def _demo(tmp_path, task_id):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / f"{task_id}.md").write_text("# demo\n")
    return demo_dir


def test_write_and_read_approval_roundtrip(tmp_path):
    write_approval("t-1", approver="byron", approvals_dir=tmp_path / "ap")
    record = read_approval("t-1", approvals_dir=tmp_path / "ap")
    assert record is not None
    assert record["approved"] is True
    assert record["approver"] == "byron"


def test_read_approval_missing_returns_none(tmp_path):
    assert read_approval("nope", approvals_dir=tmp_path / "ap") is None


def test_check_external_approval_missing_record(tmp_path):
    ok, reason = check_external_approval(
        "t-2", approvals_dir=tmp_path / "ap", demo_dir=tmp_path / "demo"
    )
    assert ok is False
    assert "approval record" in reason


def test_check_external_approval_not_approved(tmp_path):
    write_approval("t-3", approved=False, approvals_dir=tmp_path / "ap")
    _demo(tmp_path, "t-3")
    ok, reason = check_external_approval(
        "t-3", approvals_dir=tmp_path / "ap", demo_dir=tmp_path / "demo"
    )
    assert ok is False
    assert "not approved" in reason


def test_check_external_approval_missing_demo(tmp_path):
    write_approval("t-4", approvals_dir=tmp_path / "ap")
    ok, reason = check_external_approval(
        "t-4", approvals_dir=tmp_path / "ap", demo_dir=tmp_path / "demo"
    )
    assert ok is False
    assert "demo" in reason


def test_check_external_approval_ok(tmp_path):
    write_approval("t-5", approvals_dir=tmp_path / "ap")
    _demo(tmp_path, "t-5")
    ok, reason = check_external_approval(
        "t-5", approvals_dir=tmp_path / "ap", demo_dir=tmp_path / "demo"
    )
    assert ok is True


def test_profile_exempts_external():
    assert profile_exempts_external(_Profile(approval_required_for=[])) is True
    assert profile_exempts_external(_Profile(approval_required_for=["EXTERNAL"])) is False
    # A missing profile is never exempt (fail-safe).
    assert profile_exempts_external(None) is False
