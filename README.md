# IMX

**Filesystem-first routing, policy, and telemetry for agent fleets.**

IMX (Inference Mesh Exchange) is the policy and routing layer that sits beside AIP and gitmem. AIP owns process orchestration and workspace mechanics, gitmem owns long-term shared memory, and IMX decides where work should run, what gate response applies, and how those decisions are recorded as reconstructable files.

> **Status:** v0.6.0 with 331 passing tests. The repo ships the reference CLI, catalog schemas, routing logic, telemetry correlation, and file-backed workflow / gate primitives described in the IMX v0.6 spec.

## How it fits

| Concern | Project |
| --- | --- |
| Spawn agents, manage tmux/workspace, queue work | AIP |
| Route tasks, apply policy gates, and record operator-readable decisions | IMX |
| Capture shared memory, Dream cycles, and repo intelligence | gitmem |

## What ships today

- routing from catalog, profile, and telemetry inputs via `imx route`
- AIP workspace bridge via `imx route-aip`
- route observation and workspace correlation via `imx observe` and `imx correlate`
- file-backed workflows, advisor/executor gate files, and control-intent files
- mesh snapshots, quota/recovery inspection, and dream-trigger emission
- canonical schemas under `catalog/schemas/`

## Install

Requires **Python 3.11+**.

```bash
pip install -e .
```

## Quick start

```bash
# Route a task directly
imx route --task-id task-001 --task-class implementation.bugfix --risk-tier LOCAL --profile standard

# Consume an AIP route request/task packet pair
imx route-aip --workspace /path/to/workspace --task-id task-001

# Record an execution outcome for future routing
imx observe --task-id task-001 --node-id node-alpha --task-class implementation.bugfix --outcome succeeded --quality 0.92

# Correlate AIP workspace events with route decisions into IMX telemetry
imx correlate --workspace /path/to/workspace
```

Commands emit JSON to stdout so the CLI is easy to compose with other file-backed tools.

## AIP workspace bridge

`imx route-aip` keeps the AIP ↔ IMX boundary file-backed instead of RPC-coupled:

1. Reads `workspace/route-requests/{task_id}.json`
2. Resolves `task_packet_ref` or falls back to `workspace/tasks/packets/{task_id}.json`
3. Validates the task packet against `catalog/schemas/task_packet.schema.json`
4. Runs the router and writes `workspace/route-decisions/{task_id}.json`

Decision files preserve the gate response/reason plus packet-derived fields such as `capability_profile`, `worktree`, `workflow_step`, `memory_refs`, and `chain_depth` so operators can reconstruct why a route was chosen from files alone.

## Command surface

| Area | Commands |
| --- | --- |
| Routing | `route`, `route-aip`, `observe`, `correlate` |
| Catalog inspection | `nodes`, `profiles`, `scores` |
| Workflow and gates | `workflow ...`, `gate ...`, `control-intent ...` |
| Operations | `mesh refresh`, `recovery status`, `quota status`, `dream-trigger` |

## Docs

- [IMX v0.6 spec](imx-spec-v0_6.md)
- [Changelog](CHANGELOG.md)
- [Resource ledger](imx-resource-ledger.md)

## Development

```bash
pytest -q
```

## License

MIT
