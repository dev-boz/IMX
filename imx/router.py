"""IMX routing cycle implementation per spec §7.

Steps:
  0. parse/decompose
  1. classify
  2. gather
  3. gate
  4. rank
  5. choose execution form
  6. dispatch (emit route decision)
  7. observe (update EMA)
"""
from __future__ import annotations

import dataclasses
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .catalog import load_node_descriptors, load_profiles, task_class_exists, _catalog_dir
from .ema import EmaStore
from .budget import load_budget, save_budget
from .models import GateResponse, NodeDescriptor, RiskTier, RouteDecision, TaskTelemetry, TaskOutcome, FailureType, Controllability
from .telemetry import append_task_record, append_route_decision, append_dream_trigger
from .cost_routing import rank_nodes_by_cost_adjusted_score
from .rca import create_rca


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class RoutingRequest:
    task_id: str
    task_class: str
    risk_tier: str          # READ_ONLY | LOCAL | EXTERNAL
    capability_profile: str | None = None
    required_capabilities: list[str] = field(default_factory=list)
    budget_max_cost_usd: float | None = None
    budget_max_tokens: int | None = None
    budget_gate: str = "soft"
    chain_depth: int = 0
    harness_preference: str | None = None
    requester: str = "operator"


@dataclass
class RoutingResult:
    decision: RouteDecision | None
    gate_response: GateResponse
    gate_reason: str
    candidate_nodes: list[str] = field(default_factory=list)
    ranked_nodes: list[tuple[str, float]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ImxRouter:
    def __init__(
        self,
        catalog_root: Path | None = None,
        ema_store: EmaStore | None = None,
        telemetry_dir: Path | None = None,
        mesh_path: Path | None = None,
        staleness_seconds: int = 300,
    ) -> None:
        self.catalog_root = catalog_root
        self.ema = ema_store or EmaStore()
        self.telemetry_dir = telemetry_dir
        self.mesh_path = mesh_path
        self.staleness_seconds = staleness_seconds

    def _load_candidates_from_mesh(self) -> list[NodeDescriptor] | None:
        """Return node descriptors from the compiled mesh, or None if unavailable/stale.

        Returns None if:
          - mesh_path is None
          - the mesh file does not exist
          - the file is older than staleness_seconds
        Otherwise reads mesh JSON and returns a list of NodeDescriptor objects
        (same type as load_node_descriptors()) so the normal gate/rank logic
        can operate on them unchanged.
        """
        if self.mesh_path is None:
            return None
        if not self.mesh_path.exists():
            return None
        age = time.time() - self.mesh_path.stat().st_mtime
        if age > self.staleness_seconds:
            return None
        try:
            mesh = json.loads(self.mesh_path.read_text())
        except Exception:
            return None
        nodes: list[NodeDescriptor] = []
        for entry in mesh.get("nodes", []):
            node_id = entry.get("node_id", "")
            if not node_id:
                continue
            node = NodeDescriptor(
                node_id=node_id,
                engine=entry.get("engine", {}),
                harness=entry.get("harness", {}),
                profile=entry.get("profile", ""),
                policy=entry.get("policy", {}),
                notes=entry.get("notes", ""),
            )
            nodes.append(node)
        return nodes if nodes else None

    def route(self, req: RoutingRequest) -> RoutingResult:
        """Execute the full 7-step routing cycle."""
        # Step 1: classify — validate task_class and risk_tier
        errors = []
        if not task_class_exists(req.task_class, self.catalog_root):
            errors.append(f"Unknown task_class: {req.task_class}")

        valid_tiers = {"READ_ONLY", "LOCAL", "EXTERNAL"}
        if req.risk_tier not in valid_tiers:
            errors.append(f"Invalid risk_tier: {req.risk_tier}")

        # Step 2: gather — candidate nodes from mesh fast-path or catalog
        nodes = self._load_candidates_from_mesh()
        if nodes is None:
            nodes = load_node_descriptors(self.catalog_root)
        profiles = load_profiles(self.catalog_root)

        # Step 3: gate — filter nodes by policy, risk tier, profile
        candidates = []
        for node in nodes:
            allowed_tiers = node.policy.get("allowed_risk_tiers", [])
            if req.risk_tier not in allowed_tiers:
                continue
            # Profile check
            profile_id = req.capability_profile or node.profile
            profile = profiles.get(profile_id)
            if profile and req.risk_tier not in profile.risk_tiers:
                continue
            candidates.append(node.node_id)

        if not candidates:
            return RoutingResult(
                decision=None,
                gate_response=GateResponse.DENY,
                gate_reason=f"No nodes satisfy risk_tier={req.risk_tier}",
                errors=errors,
            )

        # Step 4: rank — EMA + cost-adjusted scores
        harness_fp = req.harness_preference or ""
        budget_max = req.budget_max_cost_usd or 0.0
        if budget_max > 0:
            ranked = rank_nodes_by_cost_adjusted_score(
                candidates, req.task_class, self.ema,
                catalog_root=self.catalog_root,
                estimated_tokens=req.budget_max_tokens or 10000,
                budget_max_usd=budget_max,
            )
        else:
            ranked = self.ema.rank_nodes(candidates, req.task_class, harness_fp)

        # Step 5/6: choose best node, emit route decision
        best_node_id = ranked[0][0] if ranked else candidates[0]
        decision_id = f"rd-{req.task_id}-{uuid.uuid4().hex[:6]}"
        profile_used = req.capability_profile or "balanced"
        rank_method = "cost-adjusted" if budget_max > 0 else "ema"

        decision = RouteDecision(
            route_decision_id=decision_id,
            task_id=req.task_id,
            node_id=best_node_id,
            profile=profile_used,
            task_class=req.task_class,
            risk_tier=req.risk_tier,
            rationale=f"{rank_method} rank score {ranked[0][1]:.3f}" if ranked else "cold start",
            decided_at=_utc_now(),
            evidence={"candidates": candidates, "ranked": [(n, round(s, 3)) for n, s in ranked[:5]], "rank_method": rank_method},
        )

        # Emit telemetry
        append_route_decision(dataclasses.asdict(decision), self.telemetry_dir)

        # EXTERNAL tier: check approval requirement
        gate_response = GateResponse.ALLOW
        gate_reason = "ok"
        if req.risk_tier == "EXTERNAL":
            gate_response = GateResponse.AUDIT
            gate_reason = "EXTERNAL tier requires approval record before dispatch"

        return RoutingResult(
            decision=decision,
            gate_response=gate_response,
            gate_reason=gate_reason,
            candidate_nodes=candidates,
            ranked_nodes=ranked,
            errors=errors,
        )

    def observe(
        self,
        *,
        task_id: str,
        node_id: str,
        task_class: str,
        harness_fingerprint: str = "",
        outcome: str,
        failure_type: str | None = None,
        controllability: str | None = None,
        quality_score: float | None = None,
        cost_usd: float | None = None,
        tokens_total: int | None = None,
        duration_ms: int | None = None,
        chain_depth: int = 0,
        summary_ref: str | None = None,
    ) -> None:
        """Step 7: update EMA scores and record task outcome telemetry."""
        # Update EMA
        controllable = controllability in ("controllable", None)
        if outcome == "failed":
            create_rca(
                task_id=task_id,
                node_id=node_id,
                task_class=task_class,
                failure_type=failure_type or "unknown",
                chain_depth=chain_depth,
                evidence={"quality_score": quality_score},
            )
        if outcome == "succeeded":
            q = quality_score if quality_score is not None else 1.0
            self.ema.update(node_id, task_class, harness_fingerprint, quality=q, stability=1.0)
        elif outcome in ("failed", "partial") and controllable:
            q = quality_score if quality_score is not None else 0.0
            self.ema.update(node_id, task_class, harness_fingerprint, quality=q, stability=0.7)
        elif outcome in ("failed",) and not controllable:
            # Infrastructure/uncontrollable — update stability, not skill
            self.ema.update(node_id, task_class, harness_fingerprint, stability=0.5)

        # Emit dream triggers per spec §11.3
        if outcome == "failed":
            append_dream_trigger(
                "route_failure",
                source="imx-router",
                query=f"failure pattern for {task_class} on {node_id}",
                context={"task_id": task_id, "task_class": task_class, "failure_type": failure_type, "chain_depth": chain_depth},
                telemetry_dir=self.telemetry_dir,
            )
        if outcome == "succeeded" and summary_ref:
            append_dream_trigger(
                "large_task_completion",
                source="imx-router",
                query=f"lessons from {task_class} completion",
                context={"task_id": task_id, "task_class": task_class, "summary_ref": summary_ref, "node_id": node_id},
                telemetry_dir=self.telemetry_dir,
            )
        score = self.ema.get(node_id, task_class, harness_fingerprint)
        if score.n >= 10 and score.composite() < 0.3:
            append_dream_trigger(
                "procedure_regression",
                source="imx-router",
                query=f"persistent low performance for {task_class} on {node_id}",
                context={"task_id": task_id, "task_class": task_class, "composite": score.composite(), "n": score.n},
                telemetry_dir=self.telemetry_dir,
            )
        if chain_depth >= 3:
            append_dream_trigger(
                "entrenchment_risk",
                source="imx-router",
                query=f"deep chain ({chain_depth} hops) in {task_class}",
                context={"task_id": task_id, "task_class": task_class, "chain_depth": chain_depth},
                telemetry_dir=self.telemetry_dir,
            )

        # Record task telemetry
        record = {
            "schema_version": "0.6",
            "task_id": task_id,
            "node_id": node_id,
            "task_class": task_class,
            "harness_fingerprint": harness_fingerprint,
            "outcome": outcome,
            "failure_type": failure_type,
            "controllability": controllability,
            "chain_depth": chain_depth,
            "estimated_cost_usd": cost_usd,
            "tokens_total": tokens_total,
            "duration_ms": duration_ms,
            "summary_ref": summary_ref,
            "completed_at": _utc_now(),
        }
        append_task_record(record, self.telemetry_dir)
