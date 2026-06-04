"""Tests for imx.router — ImxRouter routing cycle."""
import json
import time
import pytest
from pathlib import Path

from imx.router import ImxRouter, RoutingRequest, RoutingResult
from imx.ema import EmaStore
from imx.models import GateResponse


CATALOG = Path(__file__).parent.parent / "catalog"


def _make_router(tmp_path: Path, catalog_root: Path = CATALOG) -> ImxRouter:
    ema = EmaStore(path=tmp_path / "scores.json")
    return ImxRouter(
        catalog_root=catalog_root,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
        quota_dir=tmp_path / "quota",
        budgets_dir=tmp_path / "budgets",
        approvals_dir=tmp_path / "approvals",
        demo_dir=tmp_path / "demo",
    )


def _external_catalog(tmp_path: Path) -> Path:
    """Build a minimal catalog dir with one node that allows EXTERNAL tier.

    The node's profile is set to a name that does not exist in profiles/,
    so the profile filter is skipped (profiles.get returns None) and the
    node passes through to candidates.
    """
    import yaml

    cat = tmp_path / "ext_catalog"
    (cat / "nodes.d").mkdir(parents=True)
    (cat / "profiles").mkdir()
    (cat / "task_classes.yaml").write_text(
        "schema_version: '0.6'\ntask_classes:\n  analysis:\n    description: test\n    risk_tier: READ_ONLY\n"
    )
    node = {
        "node_id": "ext-node",
        "engine": {"family": "economy", "provider": "test"},
        "harness": {},
        "profile": "no_such_profile",  # no matching profile → profile check skipped
        "policy": {"allowed_risk_tiers": ["EXTERNAL"]},
        "notes": "",
    }
    (cat / "nodes.d" / "ext-node.yaml").write_text(yaml.dump(node))
    return cat


def _readonly_catalog(tmp_path: Path, nodes: list[tuple[str, str]]) -> Path:
    """Minimal READ_ONLY catalog with the given (node_id, provider) nodes.

    Profiles are intentionally absent so the profile filter is skipped.
    """
    import yaml

    cat = tmp_path / "ro_catalog"
    (cat / "nodes.d").mkdir(parents=True)
    (cat / "profiles").mkdir()
    (cat / "task_classes.yaml").write_text(
        "schema_version: '0.6'\ntask_classes:\n  analysis:\n    description: test\n    risk_tier: READ_ONLY\n"
    )
    for node_id, provider in nodes:
        node = {
            "node_id": node_id,
            "engine": {"family": "economy", "provider": provider},
            "harness": {},
            "profile": "no_such_profile",
            "policy": {"allowed_risk_tiers": ["READ_ONLY"]},
            "notes": "",
        }
        (cat / "nodes.d" / f"{node_id}.yaml").write_text(yaml.dump(node))
    return cat


# --- route() returns RoutingResult for valid request ---

def test_route_returns_routing_result(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-001",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert isinstance(result, RoutingResult)


def test_route_valid_request_has_decision(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-001",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert result.decision is not None


# --- READ_ONLY risk tier ---

def test_route_read_only_succeeds(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-002",
        task_class="code_review",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.ALLOW
    assert result.decision is not None


def test_route_read_only_has_candidate_nodes(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-002",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert len(result.candidate_nodes) >= 1


def test_route_read_only_no_errors(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-003",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert result.errors == []


# --- EXTERNAL approval gate (spec §9, §9.1) ---

def _approve(tmp_path: Path, task_id: str) -> None:
    """Write an approval record + demo artifact for an EXTERNAL task."""
    from imx.approvals import write_approval

    write_approval(task_id, approvals_dir=tmp_path / "approvals")
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / f"{task_id}.md").write_text("# demo\nverified\n")


def test_route_external_without_approval_denies(tmp_path):
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    req = RoutingRequest(
        task_id="task-ext-000",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.DENY
    assert "approval" in result.gate_reason.lower()
    assert result.decision is None


def test_route_external_with_approval_returns_audit(tmp_path):
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    _approve(tmp_path, "task-ext-001")
    req = RoutingRequest(
        task_id="task-ext-001",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.AUDIT


def test_route_external_missing_demo_denies(tmp_path):
    from imx.approvals import write_approval

    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    # Approval record present but no demo artifact → still denied.
    write_approval("task-ext-nodemo", approvals_dir=tmp_path / "approvals")
    req = RoutingRequest(
        task_id="task-ext-nodemo",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.DENY
    assert "demo" in result.gate_reason.lower()


def test_route_external_with_approval_still_has_decision(tmp_path):
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    _approve(tmp_path, "task-ext-002")
    req = RoutingRequest(
        task_id="task-ext-002",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    # Decision is emitted once the approval gate passes
    assert result.decision is not None


def test_route_writes_gate_decision(tmp_path):
    """Every route() emits a record to the gate_decisions.jsonl audit stream."""
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    _approve(tmp_path, "task-ext-003")
    req = RoutingRequest(
        task_id="task-ext-003",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    gate_log = tmp_path / "telemetry" / "gate_decisions.jsonl"
    assert gate_log.exists()
    record = json.loads(gate_log.read_text().splitlines()[-1])
    assert record["task_id"] == "task-ext-003"
    assert record["gate_response"] == "AUDIT"
    assert record["route_decision_id"] == result.decision.route_decision_id


# --- budget hard/soft gate (spec §6.3, §13.2) ---

def test_route_budget_hard_gate_denies(tmp_path):
    from imx.budget import BudgetLedger, save_budget

    router = _make_router(tmp_path)
    save_budget(
        BudgetLedger(task_id="task-bud-1", max_cost_usd=1.0, spent_usd=2.0, gate_mode="hard"),
        tmp_path / "budgets",
    )
    req = RoutingRequest(
        task_id="task-bud-1",
        task_class="analysis",
        risk_tier="READ_ONLY",
        budget_max_cost_usd=1.0,
        budget_gate="hard",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.DENY
    assert "budget" in result.gate_reason.lower()
    assert result.decision is None


def test_route_budget_soft_gate_allows(tmp_path):
    from imx.budget import BudgetLedger, save_budget

    router = _make_router(tmp_path)
    save_budget(
        BudgetLedger(task_id="task-bud-2", max_cost_usd=1.0, spent_usd=2.0, gate_mode="soft"),
        tmp_path / "budgets",
    )
    req = RoutingRequest(
        task_id="task-bud-2",
        task_class="analysis",
        risk_tier="READ_ONLY",
        budget_max_cost_usd=1.0,
        budget_gate="soft",
    )
    result = router.route(req)
    assert result.gate_response != GateResponse.DENY
    assert result.decision is not None


# --- quota/health gate (spec §6.3, §13.3) ---

def test_route_quota_exhausted_throttles(tmp_path):
    from imx.quota import QuotaStatus, write_quota_status

    cat = _readonly_catalog(tmp_path, [("ro-node", "prov-x")])
    router = _make_router(tmp_path, catalog_root=cat)
    write_quota_status(
        QuotaStatus(provider="prov-x", pct_used=1.0, status="exhausted"),
        quota_dir=tmp_path / "quota",
    )
    req = RoutingRequest(task_id="task-q-1", task_class="analysis", risk_tier="READ_ONLY")
    result = router.route(req)
    assert result.gate_response == GateResponse.THROTTLE
    assert result.decision is None


def test_route_quota_drops_exhausted_keeps_healthy(tmp_path):
    from imx.quota import QuotaStatus, write_quota_status

    cat = _readonly_catalog(tmp_path, [("ro-bad", "prov-bad"), ("ro-good", "prov-good")])
    router = _make_router(tmp_path, catalog_root=cat)
    write_quota_status(
        QuotaStatus(provider="prov-bad", pct_used=1.0, status="exhausted"),
        quota_dir=tmp_path / "quota",
    )
    req = RoutingRequest(task_id="task-q-2", task_class="analysis", risk_tier="READ_ONLY")
    result = router.route(req)
    assert result.gate_response != GateResponse.THROTTLE
    assert result.decision is not None
    assert result.decision.node_id == "ro-good"
    assert "ro-bad" not in result.candidate_nodes


def test_observe_accumulates_budget(tmp_path):
    from imx.budget import load_budget

    router = _make_router(tmp_path)
    router.observe(
        task_id="task-acc",
        node_id="ro-good",
        task_class="analysis",
        outcome="succeeded",
        cost_usd=0.5,
        tokens_total=100,
    )
    ledger = load_budget("task-acc", tmp_path / "budgets")
    assert ledger.spent_usd == 0.5
    assert ledger.spent_tokens == 100


# --- Unknown task_class ---

def test_route_unknown_task_class_has_error(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-004",
        task_class="nonexistent_class",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert len(result.errors) > 0
    assert any("nonexistent_class" in e for e in result.errors)


def test_route_unknown_task_class_still_routes_if_nodes_available(tmp_path):
    router = _make_router(tmp_path)
    req = RoutingRequest(
        task_id="task-005",
        task_class="nonexistent_class",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    # routing continues despite unknown class; candidates may still exist
    assert isinstance(result, RoutingResult)


# --- observe() updates EMA ---

def test_observe_updates_ema_quality(tmp_path):
    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=CATALOG,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
    )
    node_id = "deep@claude-code/implementer"
    task_class = "analysis"
    before = ema.get(node_id, task_class, "").quality

    router.observe(
        task_id="task-obs-001",
        node_id=node_id,
        task_class=task_class,
        harness_fingerprint="",
        outcome="succeeded",
        quality_score=1.0,
    )

    after = ema.get(node_id, task_class, "").quality
    assert after != before


def test_observe_increments_n(tmp_path):
    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=CATALOG,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
    )
    node_id = "deep@claude-code/implementer"
    task_class = "analysis"
    before_n = ema.get(node_id, task_class, "").n

    router.observe(
        task_id="task-obs-002",
        node_id=node_id,
        task_class=task_class,
        harness_fingerprint="",
        outcome="succeeded",
    )

    after_n = ema.get(node_id, task_class, "").n
    assert after_n == before_n + 1


def test_observe_failed_updates_ema(tmp_path):
    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=CATALOG,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
    )
    node_id = "deep@claude-code/implementer"
    task_class = "analysis"

    router.observe(
        task_id="task-obs-003",
        node_id=node_id,
        task_class=task_class,
        harness_fingerprint="",
        outcome="failed",
        controllability="controllable",
    )

    score = ema.get(node_id, task_class, "")
    assert score.n == 1


# --- mesh fast-path ---

def _write_mesh(path: Path, nodes: list[dict]) -> None:
    """Write a minimal mesh.json for testing."""
    mesh = {
        "schema_version": "0.6",
        "compiled_at": "2026-01-01T00:00:00Z",
        "node_count": len(nodes),
        "nodes": nodes,
    }
    path.write_text(json.dumps(mesh))


def _mesh_node(node_id: str, allowed_tiers: list[str], profile: str = "no_such_profile") -> dict:
    return {
        "node_id": node_id,
        "engine": {"family": "economy", "provider": "test"},
        "harness": {},
        "profile": profile,
        "policy": {"allowed_risk_tiers": allowed_tiers},
        "notes": "",
        "ema_scores": {},
        "cold_composite": 0.5,
    }


def test_mesh_fastpath_used_when_fresh(tmp_path):
    """Router uses mesh fast-path when mesh file is fresh."""
    mesh_file = tmp_path / "mesh.json"
    node_id = "mesh-node-fresh"
    _write_mesh(mesh_file, [_mesh_node(node_id, ["READ_ONLY"])])

    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=tmp_path / "empty_catalog",  # no catalog — forces reliance on mesh
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
        mesh_path=mesh_file,
        staleness_seconds=300,
    )
    req = RoutingRequest(
        task_id="mesh-task-001",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    assert node_id in result.candidate_nodes


def test_mesh_fastpath_bypassed_when_stale(tmp_path):
    """Router falls back to catalog when mesh file is stale."""
    import yaml

    mesh_file = tmp_path / "mesh.json"
    _write_mesh(mesh_file, [_mesh_node("stale-mesh-node", ["READ_ONLY"])])
    # Back-date the file by more than staleness_seconds
    stale_mtime = time.time() - 400
    import os
    os.utime(mesh_file, (stale_mtime, stale_mtime))

    # Minimal catalog with a different node
    cat = tmp_path / "cat"
    (cat / "nodes.d").mkdir(parents=True)
    (cat / "profiles").mkdir()
    (cat / "task_classes.yaml").write_text(
        "schema_version: '0.6'\ntask_classes:\n  analysis:\n    description: test\n    risk_tier: READ_ONLY\n"
    )
    catalog_node = {
        "node_id": "catalog-node-only",
        "engine": {"family": "economy", "provider": "test"},
        "harness": {},
        "profile": "no_such_profile",
        "policy": {"allowed_risk_tiers": ["READ_ONLY"]},
        "notes": "",
    }
    (cat / "nodes.d" / "catalog-node-only.yaml").write_text(yaml.dump(catalog_node))

    ema = EmaStore(path=tmp_path / "scores.json")
    router = ImxRouter(
        catalog_root=cat,
        ema_store=ema,
        telemetry_dir=tmp_path / "telemetry",
        mesh_path=mesh_file,
        staleness_seconds=300,
    )
    req = RoutingRequest(
        task_id="mesh-task-002",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    # Stale mesh is skipped; only catalog node should be a candidate
    assert "catalog-node-only" in result.candidate_nodes
    assert "stale-mesh-node" not in result.candidate_nodes


def test_mesh_fastpath_bypassed_when_mesh_path_is_none(tmp_path):
    """When mesh_path is None (default), router loads from catalog as before."""
    router = _make_router(tmp_path)
    assert router.mesh_path is None
    req = RoutingRequest(
        task_id="mesh-task-003",
        task_class="analysis",
        risk_tier="READ_ONLY",
    )
    result = router.route(req)
    # Normal catalog routing still works
    assert result.decision is not None
    assert len(result.candidate_nodes) >= 1
