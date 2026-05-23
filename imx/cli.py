"""IMX command-line interface."""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path


def _asdict_enum(obj):
    """JSON-serialisable representation of dataclasses with enum values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _asdict_enum(v) for k, v in dataclasses.asdict(obj).items()}
    if hasattr(obj, "value"):  # enum
        return obj.value
    return obj


def _json_out(obj) -> None:
    """Print JSON to stdout."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = dataclasses.asdict(obj)
    elif isinstance(obj, dict):
        data = obj
    elif isinstance(obj, list):
        data = obj
    else:
        data = obj
    # Enums inside nested structures
    print(json.dumps(data, default=str))


def cmd_route(args) -> int:
    from .router import ImxRouter, RoutingRequest

    catalog_root = Path(args.catalog) if args.catalog else None
    router = ImxRouter(catalog_root=catalog_root)
    req = RoutingRequest(
        task_id=args.task_id,
        task_class=args.task_class,
        risk_tier=args.risk_tier,
        capability_profile=args.profile or None,
        budget_max_cost_usd=args.budget_usd,
    )
    result = router.route(req)
    out = {
        "gate_response": result.gate_response.value,
        "gate_reason": result.gate_reason,
        "candidate_nodes": result.candidate_nodes,
        "errors": result.errors,
        "decision": dataclasses.asdict(result.decision) if result.decision else None,
        "ranked_nodes": [(n, round(s, 4)) for n, s in result.ranked_nodes],
    }
    _json_out(out)
    return 0 if result.decision is not None else 1


def cmd_route_aip(args) -> int:
    from .aip_adapter import route_aip_task

    catalog_root = Path(args.catalog) if args.catalog else None
    telemetry_dir = Path(args.telemetry_dir) if args.telemetry_dir else None
    outcome = route_aip_task(
        Path(args.workspace),
        args.task_id,
        catalog_root=catalog_root,
        telemetry_dir=telemetry_dir,
    )
    out = {
        "route_request_path": str(outcome.route_request_path),
        "decision_path": str(outcome.decision_path) if outcome.decision_path else None,
        "task_packet_path": str(outcome.task_packet_path) if outcome.task_packet_path else None,
        "task_packet_ref": outcome.task_packet_ref,
        "gate_response": outcome.result.gate_response.value,
        "gate_reason": outcome.result.gate_reason,
        "candidate_nodes": outcome.result.candidate_nodes,
        "errors": outcome.result.errors,
        "decision": dataclasses.asdict(outcome.result.decision) if outcome.result.decision else None,
    }
    _json_out(out)
    return 0 if outcome.result.decision is not None else 1


def cmd_observe(args) -> int:
    from .router import ImxRouter

    catalog_root = Path(args.catalog) if args.catalog else None
    router = ImxRouter(catalog_root=catalog_root)
    router.observe(
        task_id=args.task_id,
        node_id=args.node_id,
        task_class=args.task_class,
        harness_fingerprint=args.harness_fingerprint or "",
        outcome=args.outcome,
        quality_score=args.quality,
        cost_usd=args.cost_usd,
        tokens_total=args.tokens,
    )
    _json_out({"status": "ok", "task_id": args.task_id, "outcome": args.outcome})
    return 0


def cmd_nodes(args) -> int:
    from .catalog import load_node_descriptors

    catalog_root = Path(args.catalog) if args.catalog else None
    nodes = load_node_descriptors(catalog_root)
    _json_out([dataclasses.asdict(n) for n in nodes])
    return 0


def cmd_profiles(args) -> int:
    from .catalog import load_profiles

    catalog_root = Path(args.catalog) if args.catalog else None
    profiles = load_profiles(catalog_root)
    _json_out({pid: dataclasses.asdict(p) for pid, p in profiles.items()})
    return 0


def cmd_scores(args) -> int:
    from .ema import EmaStore

    path = Path(args.scores_path) if args.scores_path else None
    store = EmaStore(path=path)
    _json_out({k: dataclasses.asdict(v) for k, v in store._scores.items()})
    return 0


def cmd_workflow_init(args) -> int:
    from .workflow import load_definition, load_state, save_state
    import uuid

    definition_path = Path(args.definition)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    definition = load_definition(definition_path)
    state_path = output_dir / "state.json"

    state = load_state(state_path)
    if not state.workflow_id:
        state.workflow_id = uuid.uuid4().hex
    if not state.definition_ref:
        state.definition_ref = str(definition_path)
    if not state.current_step and definition.steps:
        state.current_step = definition.steps[0].id

    save_state(state, state_path)
    _json_out({"status": "ok", "state_path": str(state_path), "workflow_id": state.workflow_id})
    return 0


def cmd_workflow_advance(args) -> int:
    from .workflow import load_state, save_state, advance_workflow, load_definition
    import os

    state_path = Path(args.state)
    state = load_state(state_path)

    # Try to load definition for max_iterations check
    definition = None
    if state.definition_ref and Path(state.definition_ref).exists():
        try:
            definition = load_definition(Path(state.definition_ref))
        except Exception:
            pass

    if definition is None:
        # Build a minimal definition
        from .workflow import WorkflowDefinition
        definition = WorkflowDefinition(schema_version="0.6", name="unknown")

    new_state = advance_workflow(
        definition,
        state,
        step_id=args.step,
        outcome=args.outcome,
        task_id=args.task_id or "",
    )
    save_state(new_state, state_path)
    _json_out(dataclasses.asdict(new_state))
    return 0


def cmd_control_intent_write(args) -> int:
    from .control_intents import ControlIntent, write_control_intent

    intent = ControlIntent(
        intent=args.intent,
        session_id=args.session_id,
        task_id=args.task_id or "",
        requested_by=args.requested_by or "",
        reason=args.reason or "",
        target_model_band=args.target_model_band or "",
    )
    path = write_control_intent(intent)
    _json_out({"status": "ok", "path": str(path)})
    return 0


def cmd_correlate(args) -> int:
    from .correlation import correlate_workspace

    workspace = Path(args.workspace)
    decisions_dir = Path(args.decisions_dir) if args.decisions_dir else None
    telemetry_dir = Path(args.telemetry_dir) if args.telemetry_dir else None
    n = correlate_workspace(workspace, route_decisions_dir=decisions_dir, telemetry_dir=telemetry_dir)
    _json_out({"correlated": n})
    return 0


def cmd_dream_trigger(args) -> int:
    from .telemetry import append_dream_trigger

    context: dict = {}
    if args.task_id:
        context["task_id"] = args.task_id
    if args.task_class:
        context["task_class"] = args.task_class

    append_dream_trigger(
        args.type,
        source="imx-cli",
        query=args.query or "",
        context=context,
    )
    _json_out({"status": "ok", "trigger_type": args.type, "query": args.query or ""})
    return 0


def cmd_mesh_refresh(args) -> int:
    from .mesh import refresh_mesh
    from .ema import EmaStore

    catalog_root = Path(args.catalog) if args.catalog else None
    mesh_path = Path(args.mesh_path) if args.mesh_path else None
    ema_store = EmaStore()
    output_path = refresh_mesh(ema_store, catalog_root, mesh_path=mesh_path)
    _json_out({"status": "ok", "mesh_path": str(output_path)})
    return 0


def cmd_gate_create(args) -> int:
    from .gates import create_gate
    import dataclasses

    gates_dir = Path(args.gates_dir) if args.gates_dir else (Path.home() / ".imx" / "state" / "gates")
    options = args.options.split(",") if args.options else []
    gate = create_gate(
        task_id=args.task_id,
        stage=args.stage,
        question=args.question,
        requester=args.requester,
        gates_dir=gates_dir,
        context_ref=args.context_ref or "",
        options=options,
        ttl_seconds=args.ttl_seconds,
    )
    _json_out(dataclasses.asdict(gate))
    return 0


def cmd_gate_vote(args) -> int:
    from .gates import GateAnswer, write_gate_vote
    import dataclasses

    gates_dir = Path(args.gates_dir) if args.gates_dir else (Path.home() / ".imx" / "state" / "gates")
    answer = GateAnswer(
        gate_id=args.gate_id or f"{args.task_id}-{args.stage}",
        task_id=args.task_id,
        stage=args.stage,
        decision=args.decision,
        rationale=args.rationale or "",
        responder=args.responder,
        responded_at="",
        modifications={},
    )
    from .gates import _utc_now
    answer.responded_at = _utc_now()
    path = write_gate_vote(answer, gates_dir)
    _json_out({"status": "ok", "path": str(path)})
    return 0


def cmd_gate_resolve(args) -> int:
    from .gates import run_vote_and_record
    import dataclasses

    gates_dir = Path(args.gates_dir) if args.gates_dir else (Path.home() / ".imx" / "state" / "gates")
    record = run_vote_and_record(args.task_id, args.stage, gates_dir)
    if record is None:
        _json_out({"status": "no_votes", "task_id": args.task_id, "stage": args.stage})
        return 1
    _json_out(dataclasses.asdict(record))
    return 0


def cmd_recovery_status(args) -> int:
    from .recovery import RecoveryLedger

    ledger_path = Path(args.ledger_path) if args.ledger_path else None
    ledger = RecoveryLedger(path=ledger_path)
    _json_out(ledger._data)
    return 0


def cmd_quota_status(args) -> int:
    from .quota import read_all_quota_statuses, read_cache_stats
    import dataclasses

    quota_dir = Path(args.quota_dir) if args.quota_dir else None
    cache_stats_path = Path(args.cache_stats_path) if args.cache_stats_path else None

    statuses = read_all_quota_statuses(quota_dir=quota_dir)
    cache_stats = read_cache_stats(path=cache_stats_path)

    _json_out({
        "quota": [dataclasses.asdict(s) for s in statuses],
        "cache_stats": dataclasses.asdict(cache_stats),
    })
    return 0


def _dispatch_workflow(args) -> int:
    sub_handlers = {
        "init": cmd_workflow_init,
        "advance": cmd_workflow_advance,
    }
    handler = sub_handlers.get(args.workflow_command)
    if handler is None:
        print(f"Unknown workflow subcommand: {args.workflow_command}", file=sys.stderr)
        return 1
    return handler(args)


def _dispatch_control_intent(args) -> int:
    sub_handlers = {
        "write": cmd_control_intent_write,
    }
    handler = sub_handlers.get(args.ci_command)
    if handler is None:
        print(f"Unknown control-intent subcommand: {args.ci_command}", file=sys.stderr)
        return 1
    return handler(args)


def _dispatch_mesh(args) -> int:
    sub_handlers = {
        "refresh": cmd_mesh_refresh,
    }
    handler = sub_handlers.get(args.mesh_command)
    if handler is None:
        print(f"Unknown mesh subcommand: {args.mesh_command}", file=sys.stderr)
        return 1
    return handler(args)


def _dispatch_gate(args) -> int:
    sub_handlers = {
        "create": cmd_gate_create,
        "vote": cmd_gate_vote,
        "resolve": cmd_gate_resolve,
    }
    handler = sub_handlers.get(args.gate_command)
    if handler is None:
        print(f"Unknown gate subcommand: {args.gate_command}", file=sys.stderr)
        return 1
    return handler(args)


def _dispatch_recovery(args) -> int:
    sub_handlers = {
        "status": cmd_recovery_status,
    }
    handler = sub_handlers.get(args.recovery_command)
    if handler is None:
        print(f"Unknown recovery subcommand: {args.recovery_command}", file=sys.stderr)
        return 1
    return handler(args)


def _dispatch_quota(args) -> int:
    sub_handlers = {
        "status": cmd_quota_status,
    }
    handler = sub_handlers.get(args.quota_command)
    if handler is None:
        print(f"Unknown quota subcommand: {args.quota_command}", file=sys.stderr)
        return 1
    return handler(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imx",
        description="IMX — Inference Mesh Exchange CLI",
    )
    parser.add_argument("--catalog", metavar="DIR", default=None,
                        help="Override catalog directory path")
    sub = parser.add_subparsers(dest="command", required=True)

    # route
    p_route = sub.add_parser("route", help="Run routing cycle and print route decision as JSON")
    p_route.add_argument("--task-id", required=True, metavar="TASK_ID")
    p_route.add_argument("--task-class", required=True, metavar="CLASS")
    p_route.add_argument("--risk-tier", required=True, choices=["READ_ONLY", "LOCAL", "EXTERNAL"])
    p_route.add_argument("--profile", default=None, metavar="PROFILE")
    p_route.add_argument("--budget-usd", type=float, default=None, metavar="N")

    p_route_aip = sub.add_parser("route-aip", help="Consume an AIP route request/task packet and write a route decision")
    p_route_aip.add_argument("--workspace", required=True, metavar="DIR",
                             help="AIP workspace root directory")
    p_route_aip.add_argument("--task-id", required=True, metavar="TASK_ID",
                             help="Task ID to resolve from workspace/route-requests/")
    p_route_aip.add_argument("--telemetry-dir", default=None, metavar="DIR",
                             help="Directory to write IMX telemetry (default: ~/.imx/telemetry/)")

    # observe
    p_obs = sub.add_parser("observe", help="Record a task outcome observation")
    p_obs.add_argument("--task-id", required=True)
    p_obs.add_argument("--node-id", required=True)
    p_obs.add_argument("--task-class", required=True)
    p_obs.add_argument("--outcome", required=True, choices=["succeeded", "failed", "partial", "blocked", "escalated"])
    p_obs.add_argument("--quality", type=float, default=None, metavar="SCORE")
    p_obs.add_argument("--cost-usd", type=float, default=None)
    p_obs.add_argument("--tokens", type=int, default=None)
    p_obs.add_argument("--harness-fingerprint", default=None)

    # nodes
    sub.add_parser("nodes", help="List all loaded node descriptors as JSON")

    # profiles
    sub.add_parser("profiles", help="List all loaded capability profiles as JSON")

    # scores
    p_scores = sub.add_parser("scores", help="Show EMA scores from the store")
    p_scores.add_argument("--scores-path", default=None, metavar="PATH")

    # dream-trigger
    p_dt = sub.add_parser("dream-trigger", help="Manually emit a dream trigger record")
    p_dt.add_argument("--type", required=True, metavar="TYPE")
    p_dt.add_argument("--query", default="", metavar="TEXT")
    p_dt.add_argument("--task-id", default=None)
    p_dt.add_argument("--task-class", default=None)

    # workflow
    p_wf = sub.add_parser("workflow", help="Manage file-backed iterative workflows")
    wf_sub = p_wf.add_subparsers(dest="workflow_command", required=True)

    p_wf_init = wf_sub.add_parser("init", help="Initialise workflow state.json from a definition")
    p_wf_init.add_argument("--definition", required=True, metavar="PATH",
                           help="Path to workflow definition.yaml")
    p_wf_init.add_argument("--output-dir", required=True, metavar="DIR",
                           help="Directory to write state.json into")

    p_wf_adv = wf_sub.add_parser("advance", help="Advance workflow by recording a step outcome")
    p_wf_adv.add_argument("--state", required=True, metavar="PATH",
                          help="Path to workflow state.json")
    p_wf_adv.add_argument("--step", required=True, metavar="STEP_ID")
    p_wf_adv.add_argument("--outcome", required=True,
                          choices=["succeeded", "failed", "skipped", "compensated"])
    p_wf_adv.add_argument("--task-id", default=None, metavar="TASK_ID")

    # mesh
    p_mesh = sub.add_parser("mesh", help="Manage compiled mesh snapshots")
    mesh_sub = p_mesh.add_subparsers(dest="mesh_command", required=True)

    p_mesh_refresh = mesh_sub.add_parser("refresh", help="Compile and save a fresh mesh snapshot")
    p_mesh_refresh.add_argument("--mesh-path", default=None, metavar="PATH",
                                help="Override output path for mesh.json")

    # gate
    p_gate = sub.add_parser("gate", help="Manage advisor-executor gate files")
    gate_sub = p_gate.add_subparsers(dest="gate_command", required=True)

    _gate_dir_kwargs = dict(default=None, metavar="DIR",
                            help="Gates directory (default: ~/.imx/state/gates)")

    p_gate_create = gate_sub.add_parser("create", help="Create a new gate file")
    p_gate_create.add_argument("--task-id", required=True, metavar="TASK_ID")
    p_gate_create.add_argument("--stage", required=True,
                               choices=["plan", "correction", "pre_commit", "review"],
                               metavar="STAGE")
    p_gate_create.add_argument("--question", required=True, metavar="TEXT")
    p_gate_create.add_argument("--requester", required=True, metavar="NODE_ID")
    p_gate_create.add_argument("--context-ref", default="", metavar="REF")
    p_gate_create.add_argument("--options", default="", metavar="CSV",
                               help="Comma-separated list of vote options")
    p_gate_create.add_argument("--ttl-seconds", type=int, default=300, metavar="N")
    p_gate_create.add_argument("--gates-dir", **_gate_dir_kwargs)

    p_gate_vote = gate_sub.add_parser("vote", help="Write a vote for a gate")
    p_gate_vote.add_argument("--task-id", required=True, metavar="TASK_ID")
    p_gate_vote.add_argument("--stage", required=True,
                             choices=["plan", "correction", "pre_commit", "review"],
                             metavar="STAGE")
    p_gate_vote.add_argument("--decision", required=True, metavar="DECISION")
    p_gate_vote.add_argument("--responder", required=True, metavar="NODE_ID")
    p_gate_vote.add_argument("--gate-id", default=None, metavar="GATE_ID")
    p_gate_vote.add_argument("--rationale", default="", metavar="TEXT")
    p_gate_vote.add_argument("--gates-dir", **_gate_dir_kwargs)

    p_gate_resolve = gate_sub.add_parser("resolve", help="Collect votes and write a VoteRecord")
    p_gate_resolve.add_argument("--task-id", required=True, metavar="TASK_ID")
    p_gate_resolve.add_argument("--stage", required=True,
                                choices=["plan", "correction", "pre_commit", "review"],
                                metavar="STAGE")
    p_gate_resolve.add_argument("--gates-dir", **_gate_dir_kwargs)

    # recovery
    p_rec = sub.add_parser("recovery", help="Inspect recovery ledger state")
    rec_sub = p_rec.add_subparsers(dest="recovery_command", required=True)

    p_rec_status = rec_sub.add_parser("status", help="Show cooldown ledger and retry state")
    p_rec_status.add_argument("--ledger-path", default=None, metavar="PATH",
                              help="Override recovery ledger path")

    # quota
    p_quota = sub.add_parser("quota", help="Inspect provider quota and cache stats")
    quota_sub = p_quota.add_subparsers(dest="quota_command", required=True)

    p_quota_status = quota_sub.add_parser("status", help="Show provider quota and cache stats")
    p_quota_status.add_argument("--quota-dir", default=None, metavar="DIR",
                                help="Override quota status directory")
    p_quota_status.add_argument("--cache-stats-path", default=None, metavar="PATH",
                                help="Override cache stats file path")

    # correlate
    p_corr = sub.add_parser("correlate", help="Correlate AIP workspace events with route decisions")
    p_corr.add_argument("--workspace", required=True, metavar="DIR",
                        help="AIP workspace root directory (contains events.jsonl)")
    p_corr.add_argument("--decisions-dir", default=None, metavar="DIR",
                        help="Directory of JSON route decision files (default: WORKSPACE/route-decisions/)")
    p_corr.add_argument("--telemetry-dir", default=None, metavar="DIR",
                        help="Directory to write task telemetry (default: ~/.imx/telemetry/)")

    # control-intent
    p_ci = sub.add_parser("control-intent", help="Manage harness control intent files")
    ci_sub = p_ci.add_subparsers(dest="ci_command", required=True)

    p_ci_write = ci_sub.add_parser("write", help="Write a control intent file")
    p_ci_write.add_argument("--intent", required=True,
                            choices=["compact", "rewind", "switch_model", "clear", "pause", "resume"])
    p_ci_write.add_argument("--session-id", required=True, metavar="SID")
    p_ci_write.add_argument("--task-id", default=None, metavar="TASK_ID")
    p_ci_write.add_argument("--requested-by", default=None, metavar="NODE_ID")
    p_ci_write.add_argument("--reason", default=None, metavar="TEXT")
    p_ci_write.add_argument("--target-model-band", default=None, metavar="BAND")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "route": cmd_route,
        "route-aip": cmd_route_aip,
        "observe": cmd_observe,
        "nodes": cmd_nodes,
        "profiles": cmd_profiles,
        "scores": cmd_scores,
        "dream-trigger": cmd_dream_trigger,
        "correlate": cmd_correlate,
        "workflow": _dispatch_workflow,
        "control-intent": _dispatch_control_intent,
        "mesh": _dispatch_mesh,
        "gate": _dispatch_gate,
        "recovery": _dispatch_recovery,
        "quota": _dispatch_quota,
    }

    handler = handlers.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

    try:
        exit_code = handler(args)
        sys.exit(exit_code)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
