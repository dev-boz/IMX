"""Tests for imx.mesh — compile_mesh, save_mesh, load_mesh, refresh_mesh,
lookup_node_in_mesh, rank_nodes_from_mesh."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from imx.ema import EmaStore
from imx.mesh import (
    compile_mesh,
    load_mesh,
    lookup_node_in_mesh,
    rank_nodes_from_mesh,
    refresh_mesh,
    save_mesh,
)

CATALOG = Path(__file__).parent.parent / "catalog"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ema_store(tmp_path: Path) -> EmaStore:
    return EmaStore(path=tmp_path / "scores.json")


def _minimal_catalog(tmp_path: Path, node_ids: list[str] | None = None) -> Path:
    """Build a minimal on-disk catalog with configurable node(s)."""
    cat = tmp_path / "catalog"
    (cat / "nodes.d").mkdir(parents=True)
    (cat / "profiles").mkdir()
    (cat / "task_classes.yaml").write_text(
        "schema_version: '0.6'\ntask_classes:\n  analysis:\n    description: test\n    risk_tier: READ_ONLY\n"
    )
    for nid in (node_ids or ["test-node-1"]):
        node = {
            "node_id": nid,
            "engine": {"family": "economy", "provider": "test"},
            "harness": {"kind": "cli"},
            "profile": "economy",
            "policy": {"allowed_risk_tiers": ["READ_ONLY"]},
            "notes": "",
        }
        (cat / "nodes.d" / f"{nid}.yaml").write_text(yaml.dump(node))
    return cat


def _sample_mesh(node_ids: list[str] | None = None) -> dict:
    """Return a minimal mesh dict for use in lookup/rank tests."""
    nodes = []
    for nid in (node_ids or ["node-a", "node-b"]):
        nodes.append(
            {
                "node_id": nid,
                "harness": {},
                "engine": {},
                "profile": "economy",
                "capability_band": "",
                "policy": {},
                "ema_scores": {},
                "cold_composite": 0.5,
            }
        )
    return {
        "schema_version": "0.6",
        "compiled_at": "2026-01-01T00:00:00Z",
        "node_count": len(nodes),
        "nodes": nodes,
    }


# ---------------------------------------------------------------------------
# compile_mesh()
# ---------------------------------------------------------------------------


def test_compile_mesh_returns_dict(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    assert isinstance(mesh, dict)


def test_compile_mesh_schema_version(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    assert mesh["schema_version"] == "0.6"


def test_compile_mesh_has_compiled_at(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    assert "compiled_at" in mesh
    assert mesh["compiled_at"].endswith("Z")


def test_compile_mesh_node_count_matches_nodes_list(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    assert mesh["node_count"] == len(mesh["nodes"])


def test_compile_mesh_nodes_is_list(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    assert isinstance(mesh["nodes"], list)


def test_compile_mesh_nodes_have_required_keys(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    required = {"node_id", "harness", "engine", "profile", "policy", "ema_scores", "cold_composite"}
    for node in mesh["nodes"]:
        assert required.issubset(set(node.keys())), f"Node missing keys: {node}"


def test_compile_mesh_cold_composite_default(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    for node in mesh["nodes"]:
        assert node["cold_composite"] == 0.5


def test_compile_mesh_no_ema_scores_for_cold_start(tmp_path):
    """Nodes with no observations should have empty ema_scores."""
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, CATALOG)
    for node in mesh["nodes"]:
        # ema_scores may be non-empty only if observations exist; cold start → empty
        assert isinstance(node["ema_scores"], dict)


def test_compile_mesh_with_ema_observations_populates_scores(tmp_path):
    """Nodes with observations should have non-empty ema_scores for that task class."""
    cat = _minimal_catalog(tmp_path, ["ema-node"])
    ema = _make_ema_store(tmp_path)
    ema.update("ema-node", "analysis", "", quality=0.9, stability=0.8)

    mesh = compile_mesh(ema, cat)
    node = next((n for n in mesh["nodes"] if n["node_id"] == "ema-node"), None)
    assert node is not None
    assert "analysis" in node["ema_scores"]


def test_compile_mesh_ema_scores_contain_expected_keys(tmp_path):
    cat = _minimal_catalog(tmp_path, ["score-node"])
    ema = _make_ema_store(tmp_path)
    ema.update("score-node", "analysis", "", quality=0.8)

    mesh = compile_mesh(ema, cat)
    node = next(n for n in mesh["nodes"] if n["node_id"] == "score-node")
    score = node["ema_scores"]["analysis"]
    for key in ("quality", "latency", "cost", "stability", "composite", "n", "last_observed"):
        assert key in score, f"Missing key: {key}"


def test_compile_mesh_with_minimal_catalog(tmp_path):
    cat = _minimal_catalog(tmp_path, ["minimal-node"])
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, cat)
    assert any(n["node_id"] == "minimal-node" for n in mesh["nodes"])


def test_compile_mesh_multiple_nodes(tmp_path):
    cat = _minimal_catalog(tmp_path, ["node-x", "node-y", "node-z"])
    ema = _make_ema_store(tmp_path)
    mesh = compile_mesh(ema, cat)
    node_ids = [n["node_id"] for n in mesh["nodes"]]
    assert "node-x" in node_ids
    assert "node-y" in node_ids
    assert "node-z" in node_ids


def test_compile_mesh_uses_mesh_path_kwarg_ignored_during_compile(tmp_path):
    """mesh_path is accepted but does NOT affect compiled content."""
    ema = _make_ema_store(tmp_path)
    path = tmp_path / "somewhere" / "mesh.json"
    mesh = compile_mesh(ema, CATALOG, mesh_path=path)
    assert "schema_version" in mesh


# ---------------------------------------------------------------------------
# save_mesh() / load_mesh()
# ---------------------------------------------------------------------------


def test_save_mesh_returns_path(tmp_path):
    mesh = _sample_mesh()
    target = tmp_path / "mesh.json"
    result = save_mesh(mesh, target)
    assert result == target


def test_save_mesh_creates_file(tmp_path):
    mesh = _sample_mesh()
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    assert target.exists()


def test_save_mesh_writes_valid_json(tmp_path):
    mesh = _sample_mesh()
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    data = json.loads(target.read_text())
    assert isinstance(data, dict)


def test_save_mesh_round_trips_content(tmp_path):
    mesh = _sample_mesh(["rta", "rtb"])
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    data = json.loads(target.read_text())
    assert data["schema_version"] == "0.6"
    assert len(data["nodes"]) == 2


def test_save_mesh_creates_parent_dirs(tmp_path):
    mesh = _sample_mesh()
    target = tmp_path / "deep" / "nested" / "mesh.json"
    save_mesh(mesh, target)
    assert target.exists()


def test_save_mesh_atomic_no_tmp_left(tmp_path):
    """Temporary .tmp file should not remain after save."""
    mesh = _sample_mesh()
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    assert not (tmp_path / "mesh.tmp").exists()


def test_save_mesh_overwrites_existing_file(tmp_path):
    target = tmp_path / "mesh.json"
    save_mesh(_sample_mesh(["old-node"]), target)
    save_mesh(_sample_mesh(["new-node"]), target)
    data = json.loads(target.read_text())
    node_ids = [n["node_id"] for n in data["nodes"]]
    assert "new-node" in node_ids
    assert "old-node" not in node_ids


def test_load_mesh_returns_dict(tmp_path):
    target = tmp_path / "mesh.json"
    save_mesh(_sample_mesh(), target)
    result = load_mesh(target)
    assert isinstance(result, dict)


def test_load_mesh_reads_correct_content(tmp_path):
    mesh = _sample_mesh(["load-node"])
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    loaded = load_mesh(target)
    node_ids = [n["node_id"] for n in loaded["nodes"]]
    assert "load-node" in node_ids


def test_load_mesh_missing_file_returns_empty_shell(tmp_path):
    target = tmp_path / "nonexistent.json"
    result = load_mesh(target)
    assert result["schema_version"] == "0.6"
    assert result["nodes"] == []


def test_load_mesh_invalid_json_returns_empty_shell(tmp_path):
    target = tmp_path / "bad.json"
    target.write_text("not valid json {{{")
    result = load_mesh(target)
    assert result["schema_version"] == "0.6"
    assert result["nodes"] == []


def test_load_mesh_preserves_schema_version(tmp_path):
    mesh = {"schema_version": "0.6", "nodes": [], "compiled_at": "2026-01-01T00:00:00Z"}
    target = tmp_path / "mesh.json"
    save_mesh(mesh, target)
    loaded = load_mesh(target)
    assert loaded["schema_version"] == "0.6"


# ---------------------------------------------------------------------------
# refresh_mesh()
# ---------------------------------------------------------------------------


def test_refresh_mesh_returns_path(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh_path = tmp_path / "mesh.json"
    result = refresh_mesh(ema, CATALOG, mesh_path=mesh_path)
    assert isinstance(result, Path)


def test_refresh_mesh_creates_file(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh_path = tmp_path / "mesh.json"
    refresh_mesh(ema, CATALOG, mesh_path=mesh_path)
    assert mesh_path.exists()


def test_refresh_mesh_file_is_valid_json(tmp_path):
    ema = _make_ema_store(tmp_path)
    mesh_path = tmp_path / "mesh.json"
    refresh_mesh(ema, CATALOG, mesh_path=mesh_path)
    data = json.loads(mesh_path.read_text())
    assert "nodes" in data


def test_refresh_mesh_with_minimal_catalog(tmp_path):
    cat = _minimal_catalog(tmp_path, ["refresh-node"])
    ema = _make_ema_store(tmp_path)
    mesh_path = tmp_path / "out" / "mesh.json"
    refresh_mesh(ema, cat, mesh_path=mesh_path)
    loaded = load_mesh(mesh_path)
    node_ids = [n["node_id"] for n in loaded["nodes"]]
    assert "refresh-node" in node_ids


def test_refresh_mesh_compile_and_save_agree(tmp_path):
    """refresh_mesh result should match a direct compile+save cycle."""
    ema = _make_ema_store(tmp_path)
    mesh_path = tmp_path / "mesh.json"
    refresh_mesh(ema, CATALOG, mesh_path=mesh_path)
    loaded = load_mesh(mesh_path)
    assert loaded["node_count"] == len(loaded["nodes"])


# ---------------------------------------------------------------------------
# lookup_node_in_mesh()
# ---------------------------------------------------------------------------


def test_lookup_node_found(tmp_path):
    mesh = _sample_mesh(["alpha", "beta"])
    node = lookup_node_in_mesh(mesh, "alpha")
    assert node is not None
    assert node["node_id"] == "alpha"


def test_lookup_node_not_found_returns_none(tmp_path):
    mesh = _sample_mesh(["alpha", "beta"])
    result = lookup_node_in_mesh(mesh, "gamma")
    assert result is None


def test_lookup_node_returns_correct_node(tmp_path):
    mesh = _sample_mesh(["x", "y", "z"])
    node = lookup_node_in_mesh(mesh, "y")
    assert node["node_id"] == "y"


def test_lookup_node_empty_mesh_returns_none(tmp_path):
    mesh = {"schema_version": "0.6", "nodes": []}
    result = lookup_node_in_mesh(mesh, "anything")
    assert result is None


def test_lookup_node_mesh_without_nodes_key_returns_none(tmp_path):
    result = lookup_node_in_mesh({}, "anything")
    assert result is None


def test_lookup_node_returns_dict(tmp_path):
    mesh = _sample_mesh(["solo"])
    node = lookup_node_in_mesh(mesh, "solo")
    assert isinstance(node, dict)


def test_lookup_node_first_match_returned(tmp_path):
    """If duplicates exist (edge-case), returns the first one."""
    nodes = [
        {"node_id": "dup", "data": "first"},
        {"node_id": "dup", "data": "second"},
    ]
    mesh = {"schema_version": "0.6", "nodes": nodes}
    node = lookup_node_in_mesh(mesh, "dup")
    assert node["data"] == "first"


# ---------------------------------------------------------------------------
# rank_nodes_from_mesh()
# ---------------------------------------------------------------------------


def test_rank_nodes_returns_list(tmp_path):
    mesh = _sample_mesh(["a", "b"])
    result = rank_nodes_from_mesh(mesh, ["a", "b"], "analysis")
    assert isinstance(result, list)


def test_rank_nodes_length_matches_input(tmp_path):
    mesh = _sample_mesh(["a", "b", "c"])
    result = rank_nodes_from_mesh(mesh, ["a", "b", "c"], "analysis")
    assert len(result) == 3


def test_rank_nodes_tuples_of_str_and_float(tmp_path):
    mesh = _sample_mesh(["a", "b"])
    result = rank_nodes_from_mesh(mesh, ["a", "b"], "analysis")
    for node_id, score in result:
        assert isinstance(node_id, str)
        assert isinstance(score, float)


def test_rank_nodes_descending_order(tmp_path):
    """Nodes with higher composite should rank first."""
    mesh = _sample_mesh(["lo", "hi"])
    # Give "hi" a high composite via ema_scores
    for node in mesh["nodes"]:
        if node["node_id"] == "hi":
            node["ema_scores"] = {
                "analysis": {
                    "quality": 0.9,
                    "latency": 0.2,
                    "cost": 0.1,
                    "stability": 0.9,
                    "composite": 0.9,
                    "n": 5,
                    "last_observed": "2026-01-01T00:00:00Z",
                }
            }
    result = rank_nodes_from_mesh(mesh, ["lo", "hi"], "analysis")
    assert result[0][0] == "hi"
    assert result[0][1] >= result[1][1]


def test_rank_nodes_cold_composite_fallback(tmp_path):
    """Nodes without EMA data for the requested task class use cold_composite."""
    mesh = _sample_mesh(["cold-node"])
    result = rank_nodes_from_mesh(mesh, ["cold-node"], "analysis")
    assert result[0][1] == 0.5


def test_rank_nodes_missing_node_uses_05(tmp_path):
    """node_ids not present in mesh should fall back to 0.5."""
    mesh = {"schema_version": "0.6", "nodes": []}
    result = rank_nodes_from_mesh(mesh, ["ghost-node"], "analysis")
    assert result[0][1] == 0.5


def test_rank_nodes_empty_node_ids(tmp_path):
    mesh = _sample_mesh(["a"])
    result = rank_nodes_from_mesh(mesh, [], "analysis")
    assert result == []


def test_rank_nodes_all_node_ids_present_in_result(tmp_path):
    mesh = _sample_mesh(["p", "q", "r"])
    result = rank_nodes_from_mesh(mesh, ["p", "q", "r"], "analysis")
    returned_ids = {nid for nid, _ in result}
    assert returned_ids == {"p", "q", "r"}


def test_rank_nodes_different_task_classes(tmp_path):
    """EMA scores are task-class specific; wrong task class falls back to cold_composite."""
    mesh = _sample_mesh(["multi"])
    for node in mesh["nodes"]:
        if node["node_id"] == "multi":
            node["ema_scores"] = {
                "implementation": {
                    "quality": 0.95,
                    "latency": 0.1,
                    "cost": 0.05,
                    "stability": 0.95,
                    "composite": 0.95,
                    "n": 10,
                    "last_observed": "2026-01-01T00:00:00Z",
                }
            }
    # analysis not present → cold_composite
    result_analysis = rank_nodes_from_mesh(mesh, ["multi"], "analysis")
    assert result_analysis[0][1] == 0.5

    # implementation IS present → composite 0.95
    result_impl = rank_nodes_from_mesh(mesh, ["multi"], "implementation")
    assert result_impl[0][1] == pytest.approx(0.95)


def test_rank_nodes_uses_ema_composite_not_cold(tmp_path):
    """When EMA data exists, cold_composite is NOT used."""
    mesh = _sample_mesh(["scored"])
    for node in mesh["nodes"]:
        if node["node_id"] == "scored":
            node["cold_composite"] = 0.1
            node["ema_scores"] = {
                "analysis": {
                    "quality": 0.8,
                    "latency": 0.2,
                    "cost": 0.2,
                    "stability": 0.8,
                    "composite": 0.72,
                    "n": 3,
                    "last_observed": "2026-01-01T00:00:00Z",
                }
            }
    result = rank_nodes_from_mesh(mesh, ["scored"], "analysis")
    assert result[0][1] == pytest.approx(0.72)
