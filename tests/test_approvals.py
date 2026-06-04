"""Tests for imx/approvals.py — EXTERNAL approval and demo-artifact checks."""
from dataclasses import dataclass

from imx.approvals import (
    check_external_approval,
    humanfile_present,
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


# --- HUMANFILE sentinel (spec §12.2) ---

def test_humanfile_not_present_by_default(tmp_path):
    """humanfile_present returns False when no HUMANFILE exists."""
    assert humanfile_present(approvals_dir=tmp_path / "ap") is False


def test_humanfile_present_when_sentinel_exists(tmp_path):
    """humanfile_present returns True when HUMANFILE sentinel file exists."""
    ap_dir = tmp_path / "ap"
    ap_dir.mkdir(parents=True)
    (ap_dir / "HUMANFILE").write_text("human co-signer required\n")
    assert humanfile_present(approvals_dir=ap_dir) is True


def test_humanfile_present_with_empty_sentinel(tmp_path):
    """Content of HUMANFILE is irrelevant — presence alone is the signal."""
    ap_dir = tmp_path / "ap"
    ap_dir.mkdir(parents=True)
    (ap_dir / "HUMANFILE").write_text("")
    assert humanfile_present(approvals_dir=ap_dir) is True


def test_check_external_approval_humanfile_blocks_without_cosigner(tmp_path):
    """HUMANFILE present + no human_cosigner → dispatch blocked."""
    ap_dir = tmp_path / "ap"
    ap_dir.mkdir(parents=True)
    (ap_dir / "HUMANFILE").write_text("required\n")
    # Normal approval without human_cosigner
    write_approval("t-hf-1", approvals_dir=ap_dir)
    _demo(tmp_path, "t-hf-1")
    ok, reason = check_external_approval(
        "t-hf-1", approvals_dir=ap_dir, demo_dir=tmp_path / "demo"
    )
    assert ok is False
    assert "HUMANFILE" in reason or "human_cosigner" in reason


def test_check_external_approval_humanfile_passes_with_cosigner(tmp_path):
    """HUMANFILE present + human_cosigner: true → dispatch allowed."""
    ap_dir = tmp_path / "ap"
    ap_dir.mkdir(parents=True)
    (ap_dir / "HUMANFILE").write_text("required\n")
    write_approval("t-hf-2", human_cosigner=True, approvals_dir=ap_dir)
    _demo(tmp_path, "t-hf-2")
    ok, reason = check_external_approval(
        "t-hf-2", approvals_dir=ap_dir, demo_dir=tmp_path / "demo"
    )
    assert ok is True


def test_check_external_approval_no_humanfile_still_ok_without_cosigner(tmp_path):
    """Without HUMANFILE, human_cosigner field is optional — existing tests unaffected."""
    write_approval("t-hf-3", approvals_dir=tmp_path / "ap")
    _demo(tmp_path, "t-hf-3")
    ok, _ = check_external_approval(
        "t-hf-3", approvals_dir=tmp_path / "ap", demo_dir=tmp_path / "demo"
    )
    assert ok is True


def test_write_approval_sets_human_cosigner_field(tmp_path):
    """write_approval includes human_cosigner field when True."""
    write_approval("t-hf-4", human_cosigner=True, approvals_dir=tmp_path / "ap")
    record = read_approval("t-hf-4", approvals_dir=tmp_path / "ap")
    assert record is not None
    assert record.get("human_cosigner") is True


def test_write_approval_omits_human_cosigner_when_false(tmp_path):
    """write_approval omits human_cosigner field when not True (cleaner records)."""
    write_approval("t-hf-5", approvals_dir=tmp_path / "ap")
    record = read_approval("t-hf-5", approvals_dir=tmp_path / "ap")
    assert record is not None
    assert "human_cosigner" not in record
