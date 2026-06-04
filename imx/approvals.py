"""EXTERNAL-tier approval and demo-artifact checks per spec §9 and §9.1.

EXTERNAL tasks (push, deploy, publish, remote/production writes) require an
approval record at ``~/.imx/state/approvals/{task_id}.json`` and a demo/evidence
artifact at ``artifacts/demo/{task_id}.md`` before dispatch, unless the governing
capability profile explicitly exempts EXTERNAL (``approval_required_for`` omits
it). The router consults these before allowing an EXTERNAL route to dispatch.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("imx.approvals")

DEFAULT_APPROVALS_DIR = Path.home() / ".imx" / "state" / "approvals"
DEFAULT_DEMO_DIR = Path.home() / ".imx" / "artifacts" / "demo"


def approval_path(task_id: str, approvals_dir: Path | None = None) -> Path:
    return (approvals_dir or DEFAULT_APPROVALS_DIR) / f"{task_id}.json"


def demo_artifact_path(task_id: str, demo_dir: Path | None = None) -> Path:
    return (demo_dir or DEFAULT_DEMO_DIR) / f"{task_id}.md"


def read_approval(task_id: str, approvals_dir: Path | None = None) -> dict | None:
    """Read the approval record for a task, or None if missing/unreadable."""
    path = approval_path(task_id, approvals_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read approval record %s: %s", path, exc)
        return None


def write_approval(
    task_id: str,
    *,
    approved: bool = True,
    approver: str = "operator",
    note: str = "",
    approvals_dir: Path | None = None,
) -> Path:
    """Write an approval record atomically. Returns the path written."""
    d = approvals_dir or DEFAULT_APPROVALS_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{task_id}.json"
    record = {
        "task_id": task_id,
        "approved": approved,
        "approver": approver,
        "note": note,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def profile_exempts_external(profile) -> bool:
    """True when a capability profile explicitly exempts EXTERNAL approval.

    A profile exempts EXTERNAL when ``EXTERNAL`` is not listed in its
    ``approval_required_for``. A missing profile is never exempt (fail-safe).
    """
    if profile is None:
        return False
    required = getattr(profile, "approval_required_for", None) or []
    return "EXTERNAL" not in required


def check_external_approval(
    task_id: str,
    *,
    approvals_dir: Path | None = None,
    demo_dir: Path | None = None,
) -> tuple[bool, str]:
    """Return (allowed, reason) for dispatching an EXTERNAL task.

    Requires an approval record with ``approved: true`` AND a demo artifact
    (spec §9, §9.1). Either missing blocks dispatch.
    """
    record = read_approval(task_id, approvals_dir)
    if record is None:
        return (False, f"missing approval record for EXTERNAL task {task_id}")
    if not record.get("approved", False):
        return (False, f"approval record for {task_id} is not approved")
    demo = demo_artifact_path(task_id, demo_dir)
    if not demo.exists():
        return (False, f"missing demo artifact {demo.name} for EXTERNAL task {task_id}")
    return (True, "approval record and demo artifact present")
