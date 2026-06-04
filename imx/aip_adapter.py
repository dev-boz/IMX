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
from .catalog import load_profiles
from .identity import check_identity
from .models import GateResponse
from .secret_scan import SecretFoundError, assert_clean
from .telemetry import append_gate_decision

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
    scan: bool = True,
) -> dict[str, Any]:
    """Load and validate a task packet against the canonical IMX schema.

    Fail-closed (spec §11.5): unless ``scan`` is False, the packet is scanned
    for secrets and a SecretFoundError is raised if any are present, blocking
    propagation before the next model call.
    """
    packet = _load_json_object(packet_path, label="task packet")
    resolved_schema = schema_path or _default_task_packet_schema_path(catalog_root)
    schema = _load_json_object(resolved_schema, label="task packet schema")
    try:
        validate(instance=packet, schema=schema)
    except ValidationError as exc:
        path = list(exc.absolute_path)
        location = ".".join(str(part) for part in path) if path else "<root>"
        raise ValueError(f"task packet failed schema validation at {location}: {exc.message}") from exc
    if scan:
        assert_clean(packet, label="task_packet")
    return packet


@dataclass(slots=True)
class AipRouteOutcome:
    route_request_path: Path
    decision_path: Path | None
    task_packet_path: Path | None
    task_packet_ref: str | None
    result: RoutingResult


def _denied_for_secret(
    *,
    task_id: str,
    route_request_path: Path,
    task_packet_path: Path | None,
    task_packet_ref: str | None,
    risk_tier: str,
    reason: str,
    telemetry_dir: Path | None,
) -> AipRouteOutcome:
    """Build a DENY outcome and audit it when a boundary artifact carries a secret."""
    append_gate_decision(
        {
            "route_decision_id": None,
            "task_id": task_id,
            "node_id": None,
            "risk_tier": risk_tier,
            "gate_response": GateResponse.DENY.value,
            "reason": reason,
            "decided_by": "imx-secret-scan",
        },
        telemetry_dir,
    )
    return AipRouteOutcome(
        route_request_path=route_request_path,
        decision_path=None,
        task_packet_path=task_packet_path,
        task_packet_ref=task_packet_ref,
        result=RoutingResult(
            decision=None,
            gate_response=GateResponse.DENY,
            gate_reason=reason,
            errors=[reason],
        ),
    )


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

    # Fail-closed secret scan on the boundary artifacts (spec §11.5): a secret in
    # the route request or task packet blocks dispatch with an audited DENY
    # rather than propagating to the next model call.
    packet: dict[str, Any] | None = None
    try:
        assert_clean(route_request, label="route_request")
        if task_packet_path is not None:
            packet = read_task_packet(task_packet_path, catalog_root=catalog_root)
    except SecretFoundError as exc:
        return _denied_for_secret(
            task_id=task_id,
            route_request_path=route_request_path,
            task_packet_path=task_packet_path,
            task_packet_ref=task_packet_ref if isinstance(task_packet_ref, str) else None,
            risk_tier=str((route_request or {}).get("risk_tier", "")),
            reason=str(exc),
            telemetry_dir=telemetry_dir,
        )

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

    # Identity-hygiene consistency checks (spec §12.6): compare the packet's
    # declared identity against what IMX dispatched and audit any mismatches to
    # gate_decisions.jsonl. Non-blocking by default (a consistency check).
    identity_violations: list[dict[str, str]] = []
    if packet is not None and result.decision is not None:
        dispatched_profile_id = result.decision.profile
        profile_obj = load_profiles(catalog_root).get(dispatched_profile_id)
        for violation in check_identity(
            packet,
            dispatched_profile_id=dispatched_profile_id,
            dispatched_node=result.decision.node_id,
            profile=profile_obj,
        ):
            identity_violations.append({"kind": violation.kind, "detail": violation.detail})
            append_gate_decision(
                {
                    "route_decision_id": result.decision.route_decision_id,
                    "task_id": task_id,
                    "node_id": result.decision.node_id,
                    "risk_tier": result.decision.risk_tier,
                    "profile": dispatched_profile_id,
                    "gate_response": GateResponse.AUDIT.value,
                    "reason": f"identity:{violation.kind}: {violation.detail}",
                    "decided_by": "imx-identity",
                },
                telemetry_dir,
            )

    decision_path: Path | None = None
    if result.decision is not None:
        payload = dataclasses.asdict(result.decision)
        payload["gate_response"] = result.gate_response.value
        payload["gate_reason"] = result.gate_reason
        if identity_violations:
            payload["identity_violations"] = identity_violations
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
