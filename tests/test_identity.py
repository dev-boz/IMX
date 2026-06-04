"""Tests for imx/identity.py — identity-hygiene consistency checks (§12.6)."""
from types import SimpleNamespace

from imx.identity import IdentityViolation, check_identity


def _packet(**overrides):
    packet = {
        "task_id": "t-1",
        "task_class": "analysis",
        "risk_tier": "READ_ONLY",
        "relationship": "subtask",
        "capability_profile": "balanced",
        "provenance": {"source_node": "node-a", "chain_depth": 1},
    }
    packet.update(overrides)
    return packet


def test_clean_packet_has_no_violations():
    profile = SimpleNamespace(allow=["read_file"], deny=["git_push"])
    violations = check_identity(
        _packet(),
        dispatched_profile_id="balanced",
        dispatched_node="node-a",
        profile=profile,
        expected_source_node="node-a",
    )
    assert violations == []


def test_profile_mismatch():
    violations = check_identity(_packet(), dispatched_profile_id="economy")
    kinds = {v.kind for v in violations}
    assert "profile_mismatch" in kinds


def test_source_node_mismatch():
    violations = check_identity(
        _packet(),
        dispatched_profile_id="balanced",
        expected_source_node="node-b",
    )
    assert any(v.kind == "source_node_mismatch" for v in violations)


def test_tool_not_permitted_via_deny():
    profile = SimpleNamespace(allow=[], deny=["git_push"])
    violations = check_identity(
        _packet(requested_tools=["git_push"]),
        dispatched_profile_id="balanced",
        profile=profile,
    )
    assert any(v.kind == "tool_not_permitted" for v in violations)


def test_tool_not_permitted_when_not_in_allow():
    profile = SimpleNamespace(allow=["read_file"], deny=[])
    violations = check_identity(
        _packet(tool_requests=["deploy"]),
        dispatched_profile_id="balanced",
        profile=profile,
    )
    assert any(v.kind == "tool_not_permitted" for v in violations)


def test_chain_depth_not_incremented_on_non_root():
    packet = _packet(provenance={"source_node": "node-a", "chain_depth": 0})
    violations = check_identity(packet, dispatched_profile_id="balanced")
    assert any(v.kind == "chain_depth_not_incremented" for v in violations)


def test_root_packet_chain_depth_zero_is_ok():
    packet = _packet(relationship="root", provenance={"chain_depth": 0})
    violations = check_identity(packet, dispatched_profile_id="balanced")
    assert all(v.kind != "chain_depth_not_incremented" for v in violations)
