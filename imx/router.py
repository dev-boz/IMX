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
from .quota import is_provider_quota_ok
from .approvals import check_external_approval, profile_exempts_external
from .models import GateResponse, NodeDescriptor, RiskTier, RouteDecision, TaskTelemetry, TaskOutcome, FailureType, Controllability
from .telemetry import (
    append_task_record,
    append_route_decision,
    append_dream_trigger,
    append_gate_decision,
)
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
        quota_dir: Path | None = None,
        budgets_dir: Path | None = None,
        approvals_dir: Path | None = None,
        demo_dir: Path | None = None,
    ) -> None:
        self.catalog_root = catalog_root
        self.ema = ema_store or EmaStore()
        self.telemetry_dir = telemetry_dir
        self.mesh_path = mesh_path
        self.staleness_seconds = staleness_seconds
        # When None, the quota/budget/approval modules fall back to ~/.imx defaults.
        self.quota_dir = quota_dir
        self.budgets_dir = budgets_dir
        self.approvals_dir = approvals_dir
        self.demo_dir = demo_dir

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

    def _log_gate(
        self,
        req: RoutingRequest,
        *,
        decision_id: str | None,
        node_id: str | None,
        profile: str | None,
        gate_response: GateResponse,
        reason: str,
    ) -> None:
        """Append a gate decision to gate_decisions.jsonl (spec §12.1/§12.6/§14.2)."""
        append_gate_decision(
            {
                "route_decision_id": decision_id,
                "task_id": req.task_id,
                "node_id": node_id,
                "task_class": req.task_class,
                "risk_tier": req.risk_tier,
                "profile": profile or "balanced",
                "gate_response": gate_response.value,
                "reason": reason,
                "chain_depth": getattr(req, "chain_depth", 0),
                "decided_by": "imx-router",
            },
            self.telemetry_dir,
        )

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

        # Step 3b: live health/quota gate — drop nodes whose provider quota is
        # exhausted so we avoid mid-task quota exhaustion (spec §6.3, §13.3).
        # Ranks above budget, below policy in the precedence order.
        node_by_id = {n.node_id: n for n in nodes}
        quota_skipped: list[str] = []
        healthy: list[str] = []
        for node_id in candidates:
            node = node_by_id.get(node_id)
            provider = (node.engine.get("provider") if node else "") or ""
            if provider:
                ok, _msg = is_provider_quota_ok(provider, quota_dir=self.quota_dir)
                if not ok:
                    quota_skipped.append(node_id)
                    continue
            healthy.append(node_id)
        if healthy:
            candidates = healthy
        elif quota_skipped:
            # Every candidate provider is quota-exhausted — transient, so
            # THROTTLE rather than DENY (the policy gate already passed).
            self._log_gate(
                req, decision_id=None, node_id=None, profile=req.capability_profile,
                gate_response=GateResponse.THROTTLE,
                reason="all candidate providers quota-exhausted",
            )
            return RoutingResult(
                decision=None,
                gate_response=GateResponse.THROTTLE,
                gate_reason="all candidate providers quota-exhausted",
                candidate_nodes=quota_skipped,
                errors=errors,
            )

        # Step 3c: budget hard gate — deny dispatch when a hard budget is
        # already exhausted (spec §6.3, §13.2). Soft budgets fall through to
        # cost-adjusted ranking, which biases toward cheaper nodes.
        ledger = load_budget(req.task_id, self.budgets_dir)
        if req.budget_max_cost_usd is not None:
            ledger.max_cost_usd = req.budget_max_cost_usd
        if req.budget_max_tokens is not None:
            ledger.max_tokens = req.budget_max_tokens
        ledger.gate_mode = req.budget_gate or ledger.gate_mode
        budget_allowed, budget_reason = ledger.check()
        if not budget_allowed:
            self._log_gate(
                req, decision_id=None, node_id=None, profile=req.capability_profile,
                gate_response=GateResponse.DENY, reason=budget_reason,
            )
            return RoutingResult(
                decision=None,
                gate_response=GateResponse.DENY,
                gate_reason=budget_reason,
                candidate_nodes=candidates,
                errors=errors,
            )

        # Step 3d: EXTERNAL approval gate — require an approval record + demo
        # artifact before dispatch unless the governing profile exempts EXTERNAL
        # (spec §9, §9.1). Risk policy is not overridden by quota or budget.
        if req.risk_tier == "EXTERNAL":
            gov_profile = profiles.get(req.capability_profile or "balanced")
            if not profile_exempts_external(gov_profile):
                approved, approval_reason = check_external_approval(
                    req.task_id,
                    approvals_dir=self.approvals_dir,
                    demo_dir=self.demo_dir,
                )
                if not approved:
                    self._log_gate(
                        req, decision_id=None, node_id=None, profile=req.capability_profile,
                        gate_response=GateResponse.DENY, reason=approval_reason,
                    )
                    return RoutingResult(
                        decision=None,
                        gate_response=GateResponse.DENY,
                        gate_reason=approval_reason,
                        candidate_nodes=candidates,
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

        # EXTERNAL tier: by this point the approval gate (step 3d) has passed
        # (approved or profile-exempt), so dispatch is allowed but still flagged
        # for post-hoc review (spec §9.2 graduated gate responses).
        gate_response = GateResponse.ALLOW
        gate_reason = "ok"
        if req.risk_tier == "EXTERNAL":
            gate_response = GateResponse.AUDIT
            gate_reason = "EXTERNAL approved or profile-exempt; post-hoc audit required"

        # Persist the gate decision to the audit stream profiles point at via
        # `log_decisions_to` (spec §12.1/§12.6/§14.2).
        self._log_gate(
            req, decision_id=decision_id, node_id=best_node_id,
            profile=profile_used, gate_response=gate_response, reason=gate_reason,
        )

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

        # Accumulate spend into the task budget ledger so the budget hard gate
        # (route() step 3c) can see it on the next dispatch (spec §13.2).
        if cost_usd is not None or tokens_total is not None:
            ledger = load_budget(task_id, self.budgets_dir)
            ledger.record_spend(cost_usd=cost_usd or 0.0, tokens=tokens_total or 0)
            save_budget(ledger, self.budgets_dir)
