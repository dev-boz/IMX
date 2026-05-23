"""Compiled mesh snapshot per IMX spec §14.2."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from .catalog import load_node_descriptors, load_profiles, load_task_classes

DEFAULT_MESH_PATH: Path = Path.home() / ".imx" / "state" / "compiled" / "mesh.json"


def _utc_now_iso() -> str:
    """Return current UTC time as ISO8601 string (matching ema.py pattern)."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def compile_mesh(
    ema_store,
    catalog_root: Path | None = None,
    *,
    mesh_path: Path | None = None,
) -> dict:
    """Compile all node descriptors + empirical EMA scores into a mesh snapshot."""
    nodes = load_node_descriptors(catalog_root)
    # load_profiles called to trigger any side effects / validation, result unused directly
    load_profiles(catalog_root)
    task_classes = load_task_classes(catalog_root)

    node_list = []
    for node in nodes:
        ema_scores: dict[str, dict] = {}
        for task_class in task_classes:
            score = ema_store.get(node.node_id, task_class, "")
            if score.n > 0:
                ema_scores[task_class] = {
                    "quality": score.quality,
                    "latency": score.latency,
                    "cost": score.cost,
                    "stability": score.stability,
                    "composite": score.composite(),
                    "n": score.n,
                    "last_observed": score.last_observed,
                }

        node_dict = {
            "node_id": node.node_id,
            "harness": node.harness,
            "engine": node.engine,
            "profile": node.profile,
            "capability_band": getattr(node, "capability_band", ""),
            "policy": node.policy,
            "ema_scores": ema_scores,
            "cold_composite": 0.5,
        }
        node_list.append(node_dict)

    return {
        "schema_version": "0.6",
        "compiled_at": _utc_now_iso(),
        "node_count": len(node_list),
        "nodes": node_list,
    }


def save_mesh(mesh: dict, path: Path | None = None) -> Path:
    """Atomically write mesh dict to JSON. Returns path written."""
    target = path or DEFAULT_MESH_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(mesh, indent=2))
    os.replace(tmp, target)
    return target


def load_mesh(path: Path | None = None) -> dict:
    """Read mesh JSON from path (or DEFAULT_MESH_PATH). Returns empty shell if missing."""
    target = path or DEFAULT_MESH_PATH
    if not target.exists():
        return {"schema_version": "0.6", "nodes": []}
    try:
        return json.loads(target.read_text())
    except Exception:
        return {"schema_version": "0.6", "nodes": []}


def refresh_mesh(
    ema_store,
    catalog_root: Path | None = None,
    *,
    mesh_path: Path | None = None,
) -> Path:
    """Compile and save the mesh. Returns path written."""
    mesh = compile_mesh(ema_store, catalog_root, mesh_path=mesh_path)
    return save_mesh(mesh, mesh_path)


def lookup_node_in_mesh(mesh: dict, node_id: str) -> dict | None:
    """Find node by node_id in mesh['nodes']. Returns None if not found."""
    for node in mesh.get("nodes", []):
        if node.get("node_id") == node_id:
            return node
    return None


def rank_nodes_from_mesh(
    mesh: dict, node_ids: list[str], task_class: str
) -> list[tuple[str, float]]:
    """Rank node_ids by EMA composite for task_class, descending.

    Falls back to cold_composite (0.5) when no EMA data is present.
    """
    ranked: list[tuple[str, float]] = []
    for node_id in node_ids:
        node = lookup_node_in_mesh(mesh, node_id)
        if node is None:
            score = 0.5
        else:
            ema_scores = node.get("ema_scores", {})
            if task_class in ema_scores:
                score = ema_scores[task_class]["composite"]
            else:
                score = node.get("cold_composite", 0.5)
        ranked.append((node_id, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
