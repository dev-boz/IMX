"""Catalog loaders for IMX node descriptors, profiles, rates, and task classes."""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import CapabilityProfile, NodeDescriptor

IMX_CATALOG_DEFAULT = Path.home() / ".imx" / "catalog"
PROJECT_CATALOG = Path(__file__).parent.parent / "catalog"


def _catalog_dir(catalog_root: Path | None = None) -> Path:
    """Return catalog directory, preferring project catalog if it exists."""
    if catalog_root:
        return catalog_root
    if PROJECT_CATALOG.exists():
        return PROJECT_CATALOG
    return IMX_CATALOG_DEFAULT


def load_task_classes(catalog_root: Path | None = None) -> dict:
    """Load task_classes.yaml. Returns dict of task_class -> metadata."""
    path = _catalog_dir(catalog_root) / "task_classes.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    return data.get("task_classes", {})


def load_profiles(catalog_root: Path | None = None) -> dict[str, CapabilityProfile]:
    """Load all profiles/*.yaml. Returns dict of profile_id -> CapabilityProfile."""
    profiles_dir = _catalog_dir(catalog_root) / "profiles"
    if not profiles_dir.exists():
        return {}
    result: dict[str, CapabilityProfile] = {}
    for path in sorted(profiles_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
            if not data or "profile_id" not in data:
                continue
            # Only pass fields that CapabilityProfile knows about
            fields = CapabilityProfile.__dataclass_fields__
            kwargs = {k: v for k, v in data.items() if k in fields}
            profile = CapabilityProfile(**kwargs)
            result[profile.profile_id] = profile
        except Exception:
            continue
    return result


def load_node_descriptors(catalog_root: Path | None = None) -> list[NodeDescriptor]:
    """Load all nodes.d/*.yaml. Returns list of NodeDescriptor."""
    nodes_dir = _catalog_dir(catalog_root) / "nodes.d"
    if not nodes_dir.exists():
        return []
    result: list[NodeDescriptor] = []
    for path in sorted(nodes_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
            if not data or "node_id" not in data:
                continue
            fields = NodeDescriptor.__dataclass_fields__
            kwargs = {k: v for k, v in data.items() if k in fields}
            node = NodeDescriptor(**kwargs)
            result.append(node)
        except Exception:
            continue
    return result


def load_rates(catalog_root: Path | None = None) -> dict:
    """Load all rates/*.yaml. Returns dict of provider -> model -> rates."""
    rates_dir = _catalog_dir(catalog_root) / "rates"
    if not rates_dir.exists():
        return {}
    result: dict = {}
    for path in sorted(rates_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
            if not data:
                continue
            provider = data.get("provider")
            models = data.get("models", {})
            if provider and isinstance(models, dict):
                result[provider] = models
        except Exception:
            continue
    return result


def task_class_exists(task_class: str, catalog_root: Path | None = None) -> bool:
    """Check if task_class exists (exact or dotted parent match)."""
    classes = load_task_classes(catalog_root)
    if task_class in classes:
        return True
    # parent match: "implementation.bugfix" matches "implementation"
    parts = task_class.split(".")
    for i in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:i])
        if parent in classes:
            return True
    return False
