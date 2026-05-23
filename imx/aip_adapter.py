"""AIP workspace adapter for IMX routing decisions."""
from __future__ import annotations

import dataclasses
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from .router import ImxRouter, RoutingRequest, RoutingResult

DEFAULT_ROUTE_REQUESTS_DIR = "route-requests"
DEFAULT_ROUTE_DECISIONS_DIR = "route-decisions"
DEFAULT_TASK_PACKETS_DIR = Path("tasks") / "packets"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return data


def _default_task_packet_schema_path(catalog_root: Path | None = None) -> Path:
    if catalog_root is not None:
        return catalog_root / "schemas" / "task_packet.schema.json"
    return Path(__file__).resolve().parent.parent / "catalog" / "schemas" / "task_packet.schema.json"


def _resolve_workspace_ref(workspace_root: Path, ref: str) -> Path:
    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve()
    workspace_resolved = workspace_root.resolve()
    if resolved != workspace_resolved and workspace_resolved not in resolved.parents:
        raise ValueError(f"workspace ref escapes workspace root: {ref}")
    return resolved


def read_task_packet(
    packet_path: Path,
    *,
    schema_path: Path | None = None,
    catalog_root: Path | None = None,
) -> dict[str, Any]:
    """Load and validate a task packet against the canonical IMX schema."""
    packet = _load_json_object(packet_path, label="task packet")
    resolved_schema = schema_path or _default_task_packet_schema_path(catalog_root)
    schema = _load_json_object(resolved_schema, label="task packet schema")
    try:
        validate(instance=packet, schema=schema)
    except ValidationError as exc:
        path = list(exc.absolute_path)
        location = ".".join(str(part) for part in path) if path else "<root>"
        raise ValueError(f"task packet failed schema validation at {location}: {exc.message}") from exc
    return packet


@dataclass(slots=True)
class AipRouteOutcome:
    route_request_path: Path
    decision_path: Path | None
    task_packet_path: Path | None
    task_packet_ref: str | None
    result: RoutingResult


def route_aip_task(
    workspace_root: Path,
    task_id: str,
    *,
    catalog_root: Path | None = None,
    telemetry_dir: Path | None = None,
    mesh_path: Path | None = None,
) -> AipRouteOutcome:
    """Read an AIP route request/task packet, route it, and write a route decision."""
    workspace_root = Path(workspace_root)
    route_request_path = workspace_root / DEFAULT_ROUTE_REQUESTS_DIR / f"{task_id}.json"
    route_request = _load_json_object(route_request_path, label="route request")

    task_packet_path: Path | None = None
    task_packet_ref = route_request.get("task_packet_ref")
    if isinstance(task_packet_ref, str) and task_packet_ref.strip():
        task_packet_path = _resolve_workspace_ref(workspace_root, task_packet_ref.strip())
    else:
        fallback = workspace_root / DEFAULT_TASK_PACKETS_DIR / f"{task_id}.json"
        if fallback.exists():
            task_packet_path = fallback
            task_packet_ref = fallback.relative_to(workspace_root).as_posix()
        else:
            task_packet_ref = None

    packet: dict[str, Any] | None = None
    if task_packet_path is not None:
        packet = read_task_packet(task_packet_path, catalog_root=catalog_root)

    provenance = packet.get("provenance", {}) if packet else {}
    if provenance and not isinstance(provenance, dict):
        raise ValueError("task packet provenance must be an object")
    budget = packet.get("budget") if packet else route_request.get("budget")
    if budget is not None and not isinstance(budget, dict):
        raise ValueError("budget must be an object when present")

    router = ImxRouter(catalog_root=catalog_root, telemetry_dir=telemetry_dir, mesh_path=mesh_path)
    result = router.route(
        RoutingRequest(
            task_id=task_id,
            task_class=(packet or route_request)["task_class"],
            risk_tier=(packet or route_request)["risk_tier"],
            capability_profile=(packet.get("capability_profile") if packet else None)
            or route_request.get("capability_profile"),
            budget_max_cost_usd=budget.get("max_cost_usd") if budget else None,
            budget_max_tokens=budget.get("max_tokens") if budget else None,
            budget_gate=budget.get("gate_mode", "soft") if budget else "soft",
            chain_depth=int(provenance.get("chain_depth", route_request.get("chain_depth", 0) or 0)),
            harness_preference=provenance.get("harness_fingerprint") if provenance else None,
            requester=str(route_request.get("requester") or provenance.get("written_by") or "operator"),
        )
    )

    decision_path: Path | None = None
    if result.decision is not None:
        payload = dataclasses.asdict(result.decision)
        payload["gate_response"] = result.gate_response.value
        payload["gate_reason"] = result.gate_reason
        if task_packet_ref:
            payload["task_packet_ref"] = task_packet_ref
        if provenance:
            payload["chain_depth"] = int(provenance.get("chain_depth", 0))
        if packet:
            for field_name in (
                "relationship",
                "capability_profile",
                "worktree",
                "workflow_step",
                "memory_refs",
                "context_refs",
                "approval_policy",
                "contamination_risk",
            ):
                if field_name in packet:
                    payload[field_name] = packet[field_name]
        decision_path = workspace_root / DEFAULT_ROUTE_DECISIONS_DIR / f"{task_id}.json"
        _atomic_write_json(decision_path, payload)

    return AipRouteOutcome(
        route_request_path=route_request_path,
        decision_path=decision_path,
        task_packet_path=task_packet_path,
        task_packet_ref=task_packet_ref,
        result=result,
    )
