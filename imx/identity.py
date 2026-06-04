"""Identity-hygiene consistency checks for dispatched tasks (spec §12.6).

IMX governs Capability, Knowledge, and Identity. These checks verify that a task
packet's declared identity is consistent with what IMX actually dispatched:

- the declared capability profile matches the dispatched profile
- ``provenance.source_node`` matches the node IMX dispatched upstream
- requested tools are permitted by the capability profile
- non-root packets carry an incremented ``chain_depth``

Identity hygiene is a consistency check by default (violations are logged to
gate_decisions.jsonl and may trigger cooldown or quarantine), not a mandatory
cryptographic protocol.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityViolation:
    kind: str
    detail: str


def check_identity(
    packet: dict,
    *,
    dispatched_profile_id: str | None,
    dispatched_node: str | None = None,
    profile=None,
    expected_source_node: str | None = None,
) -> list[IdentityViolation]:
    """Return identity-hygiene violations for a dispatched task packet."""
    violations: list[IdentityViolation] = []
    provenance = packet.get("provenance") or {}
    if not isinstance(provenance, dict):
        provenance = {}

    # Declared capability profile must match the dispatched profile.
    declared = packet.get("capability_profile")
    if declared and dispatched_profile_id and declared != dispatched_profile_id:
        violations.append(
            IdentityViolation(
                "profile_mismatch",
                f"packet declares profile {declared!r} but dispatched under {dispatched_profile_id!r}",
            )
        )

    # provenance.source_node must match the node IMX dispatched upstream
    # (only checked when the caller supplies the expected node).
    source_node = provenance.get("source_node")
    if source_node and expected_source_node and source_node != expected_source_node:
        violations.append(
            IdentityViolation(
                "source_node_mismatch",
                f"provenance.source_node {source_node!r} != dispatched node {expected_source_node!r}",
            )
        )

    # Requested tools must be compatible with the capability profile.
    requested = packet.get("requested_tools") or packet.get("tool_requests") or []
    if profile is not None and isinstance(requested, list):
        allow = set(getattr(profile, "allow", []) or [])
        deny = set(getattr(profile, "deny", []) or [])
        for tool in requested:
            if tool in deny or (allow and tool not in allow):
                violations.append(
                    IdentityViolation(
                        "tool_not_permitted",
                        f"requested tool {tool!r} not permitted by profile {dispatched_profile_id!r}",
                    )
                )

    # Non-root packets must carry an incremented chain_depth (handoff hop).
    relationship = packet.get("relationship", "root")
    try:
        chain_depth = int(provenance.get("chain_depth", 0))
    except (TypeError, ValueError):
        chain_depth = 0
    if relationship != "root" and chain_depth < 1:
        violations.append(
            IdentityViolation(
                "chain_depth_not_incremented",
                f"non-root packet (relationship={relationship}) has chain_depth {chain_depth}",
            )
        )

    return violations
