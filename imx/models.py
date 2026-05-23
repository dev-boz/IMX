"""IMX data models — enums and dataclasses for routing and governance."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class CapabilityBand(str, enum.Enum):
    economy = "economy"
    balanced = "balanced"
    deep = "deep"
    frontier = "frontier"
    specialist = "specialist"
    local_trusted = "local_trusted"
    sandboxed = "sandboxed"
    distilled = "distilled"


class RiskTier(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL = "LOCAL"
    EXTERNAL = "EXTERNAL"


class GateResponse(str, enum.Enum):
    ALLOW = "ALLOW"
    THROTTLE = "THROTTLE"
    SANDBOX = "SANDBOX"
    AUDIT = "AUDIT"
    DENY = "DENY"


class TaskOutcome(str, enum.Enum):
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    blocked = "blocked"
    escalated = "escalated"


class FailureType(str, enum.Enum):
    context_exceeded = "context_exceeded"
    capability_gap = "capability_gap"
    quality_failure = "quality_failure"
    refusal = "refusal"
    timeout = "timeout"
    infrastructure = "infrastructure"
    cascade = "cascade"


class Controllability(str, enum.Enum):
    controllable = "controllable"
    uncontrollable = "uncontrollable"
    cascade = "cascade"
    unknown = "unknown"


@dataclass
class NodeDescriptor:
    node_id: str
    engine: dict = field(default_factory=dict)
    harness: dict = field(default_factory=dict)
    profile: str = ""
    policy: dict = field(default_factory=dict)
    notes: str = ""


@dataclass
class CapabilityProfile:
    profile_id: str
    allow: list = field(default_factory=list)
    deny: list = field(default_factory=list)
    risk_tiers: list = field(default_factory=list)
    budget_gate: str = "soft"
    budget: dict = field(default_factory=dict)
    approval_required_for: list = field(default_factory=list)
    task_classes: list = field(default_factory=list)


@dataclass
class EmaScore:
    ema_score: float
    n: int
    last_observed: str  # ISO8601
    alpha: float = 0.2


@dataclass
class RouteDecision:
    route_decision_id: str
    task_id: str
    node_id: str
    profile: str
    task_class: str
    risk_tier: str
    rationale: str
    decided_at: str
    decided_by: str = "imx-router"
    evidence: dict = field(default_factory=dict)


@dataclass
class TaskTelemetry:
    task_id: str
    node_id: str
    agent: str
    task_class: str
    risk_tier: str
    capability_profile: str
    harness_fingerprint: str
    topology: str
    outcome: str
    schema_version: str = "0.6"
    chain_depth: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    estimated_cost_usd: float | None = None
    failure_type: str | None = None
    controllability: str | None = None
    summary_ref: str | None = None
