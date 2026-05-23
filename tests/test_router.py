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


# --- EXTERNAL risk tier returns AUDIT ---

def test_route_external_returns_audit(tmp_path):
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    req = RoutingRequest(
        task_id="task-ext-001",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    assert result.gate_response == GateResponse.AUDIT


def test_route_external_still_has_decision(tmp_path):
    cat = _external_catalog(tmp_path)
    router = _make_router(tmp_path, catalog_root=cat)
    req = RoutingRequest(
        task_id="task-ext-002",
        task_class="analysis",
        risk_tier="EXTERNAL",
    )
    result = router.route(req)
    # Decision is emitted even when AUDIT gate applies
    assert result.decision is not None


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
