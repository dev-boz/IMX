# IMX Changelog

## v0.6 (2026-05-21)

**Structural revision.** Based on fifteen external reviews, the AIP spec, the gitmem/umx spec v0.9, and the 668-finding resource rework pass.

### Added

- Table of contents (§0)
- §1.2 Why These Axioms — rationale with empirical citations
- §4 Relationship to AIP and gitmem — formal separation of concerns and contract boundary rule
- §4.3–4.4 IMX as policy/synthesis layer; contract boundary rule
- §5.1 Lifecycle states (draft → active → deprecated → archived)
- §5.2 Provenance block required on all state and telemetry artifacts
- §5.3 Multi-machine state rules (catalog = syncable, state = local, telemetry = selectively syncable)
- §5.4 Write discipline (atomic rename, append-only JSONL, lock files, schema versions)
- §6.1 Harness fingerprinting — fingerprint changes trigger confidence reset; Grok Code 6.7%→68.3% evidence
- §6.2 Task class taxonomy — operator-defined, hierarchical, stored in `task_classes.yaml`
- §6.3 Evidence precedence ordering (policy gates > live health > budget > empirical > evals > gitmem > community)
- §6.4 EMA rating algorithm with separate series per node × task_class × harness_fingerprint
- §7 Routing cycle step 0: parse/decompose before classify; 7-step full cycle
- §8 Specialist capability band
- §8.1 Structured agent conventions — DESIGN.md, CLAUDE.md, role cards, skill directories, instruction precedence
- §9.1 Staging semantics — worktree as default staging; EXTERNAL promotion requirements
- §9.2 Governance calibration — graduated gate responses (ALLOW/THROTTLE/SANDBOX/AUDIT/DENY)
- §10.1 Worktree isolation as file-first rework of cloud sandboxes
- §10.2 Task and handoff packets as formal JSON Schema contracts (normative schema files)
- §10.3 Interest maps as impetus controls
- §10.4 Async task handles — poll, cancel, replay, tail semantics via AIP file patterns
- §10.5 File-backed iterative workflows — definition.yaml + state.json + checkpoints; 8 lifecycle states; conversational swarms reworked as shared review files
- §10.6 Harness-controlling-harness topology — generic control-intent files
- §10.7 Advisor-Executor Topology — file-backed gate exchange, bounded advisor invocation, profile YAML `advisor_gates`
- §10.8 Multi-Model Voting at Gates — `workspace/gates/vote-{gate_id}.json`, disagreement as uncertainty signal, profile-declared aggregation
- §11.2 Attention refresh
- §11.3 Dream triggers — IMX writes `dream-triggers.jsonl`; 7 trigger types
- §11.4 Skeptical verification artifacts
- §11.5 Secret and policy scanning — fail-closed at boundary artifacts
- §11.6 Contamination hygiene — chain_depth tracking, confidence decay per hop
- §11.7 Entrenchment detection
- §11.8 Context artifacts — context/manifest.yaml, sources.json, packed/, compactions/, lint.json
- §11.9 Procedure and graph-memory rework patterns (DSPy→gitmem, OPA→AIP hooks, graph→append-only facts)
- §12.1 Executable guardrails — profile YAML referencing shell scripts
- §12.2 HUMANFILE and pin.caps — governance descriptors
- §12.3 Exploration policy in profile YAML; Pre-Mortem Gate — `workspace/tasks/{task_id}/pre-mortem.md`, file exchange before LOCAL/EXTERNAL plan commit
- §12.4 Eval and demo artifacts as files — baselines, debates, demo artifact requirements for EXTERNAL; chaos eval specs (`eval/specs/chaos-*.yaml`), autoresearch loop (`eval/proposals/`), continuous eval matrix (`eval/matrix.yaml`), adversarial review, calibration eval specs (`eval/specs/calibration-*.yaml`) for testing agent uncertainty and escalation behaviour
- §12.5 Failure taxonomy — 7 failure types with controllability classes and routing consequences
- §12.6 Identity hygiene — role, provenance, tool, chain_depth checks
- §13.1 Event schema mapping — AIP events.jsonl → IMX telemetry field mapping table
- §13.2 Cost accounting — token counts, rate files, soft/hard budget gates
- §13.3 Quota status and cache statistics — quota-status/<provider>.json, cache-stats.json
- §13 Evidence Ingestion extended — RCA bundles (`~/.imx/telemetry/rca/{task_id}.json`), git line attribution as provenance triple, governance-overlay non-erasure invariant
- §14.1 Closed-loop enforcement
- §14.2 Auditability — "why this node" answerable from files alone
- §15.1 Recovery policy — YAML-backed retry limits, fallback chain, cooldowns, escalation rules
- §16.1–16.2 Compatibility contracts — normative AIP and gitmem change lists
- §16.3 What remains outside both projects
- `catalog/schemas/task_packet.schema.json` — normative task packet JSON Schema
- `catalog/schemas/handoff_packet.schema.json` — normative handoff packet JSON Schema
- `imx-resource-ledger.md` — full feature/rework ledger extracted from §18
- `state/quota-status/` and `state/cache-stats.json` in reference layout (§5)

**AIP spec additions (branch spec-v2-unified-update):**

- Hook Guard Patterns — dangerous command interceptors, redaction hooks, human escalation shims
- Workflow Templates — `.aip/workflows/*.yaml`, DESIGN.md stable-interface concept, role prompts
- Compaction Hooks — dream-candidate emission at compaction boundaries, session transcript format
- Route-Request Seam — `workspace/route-requests/` and `workspace/route-decisions/` consultation seam with IMX
- Worktree Helper — `.worktrees/{task_id}/` provisioning standard, cleanup policies, task packet integration
- Harness Control Seam — `~/.imx/state/control-intents/` reading, intent types (compact/switch_model/pause/teardown), acknowledgment events
- Heartbeat and Presence — `workspace/status/HEARTBEAT-{agent}.md` liveness signals, presence files, staleness detection
- Contamination-Aware Handoffs — `chain_depth` increment enforcement, PreToolUse validation hook, rejection gate pattern
- Relation to IMX and gitmem — formal contract boundary table
- Workspace layout updated with dream-candidates/, route-requests/, route-decisions/, gates/ directories
- Runtime Bridge Adapter Templates — `.aip/bridges/*.yaml` per-CLI wiring, task-local sub-workspaces, per-task `audit.jsonl`
- Plan Files and DAG Decomposition — `workspace/tasks/{task_id}/plan.yaml` with nodes/depends_on/outputs
- CLI Leaf Tool Conformance — `.aip/tools/*.yaml` with exit codes, timeouts, output caps
- Derived Activity State — `workspace/status/{agent}-activity.json` (running/needs-input/stalled/idle/done)
- Read-Only Operator Views — `workspace/operator/` tmux layout for human observers
- Resource Locks — `workspace/locks/{resource}.lock` via atomic symlink creation
- Git/SSH Bridge Patterns — SSH remote execution bridge, worktree-branch-session mapping (`workspace/agent-map.json`)
- Memory Adapters — client-specific SQLite adapter pattern, zero cloud, gitmem sync on session end
- Context Adapters — `.aip/context/{task_class}.yaml` with token budgets, include/exclude rules, bounded context packs

**gitmem spec additions (branch spec-v0_10-unified-update):**

- §3b Codebase Memory and Repo Intelligence — codemap.json, onboarding/<path>.md, docs/registry.yaml, reasoning artifacts
- §9c Skill Invocation, Progressive Disclosure, and Promotion — `@skill:<name>` explicit invocation, `umx skill test` CLI, L0/L1/L2 progressive disclosure, skill artifact export/import format, draft→active→competing→retired promotion pipeline, Dream-proposed skills
- §16 Injection Architecture extended — context packs, briefings, injection-audit.jsonl, layered context blocks (MEMORY CHRONICLES pattern: numeric/temporal/narrative/digest layers per dream cycle)
- §20a Search/Retrieval extended — retrieval-fidelity tags (`exact`/`lexical`/`semantic`/`fallback`/`expired`) on every injected block; fallback tier degradation path
- §22 Failure Modes extended — 4 new failure modes including adversarial injection and memory poisoning
- §24 Comparison extended — canonical-markdown vs. derived-cache retrieval model; positioning against MCP memory servers, vector-memory systems, compiled knowledge artifacts
- §30 Relation to AIP extended — workspace/dream-candidates/ and transcripts/ integration
- §30a Relation to IMX — routing/ namespace, route-card governance, entrenchment detection, contract boundary table
- §30b /memories compatibility projection
- Architecture repo layout extended with routing/, codebase/, artifacts/ directories

### Changed

- §0 reduced to status block only; detailed notes moved to this CHANGELOG
- §1 split into §1.1 Axioms and §1.2 Why These Axioms
- §18 condensed to synthesis conclusions; detailed ledger extracted to `imx-resource-ledger.md`
- §19 compacted into bibliography table
- Added missing context from gitmem spec: umx naming, dream pipeline ingestion points, contamination-aware consolidation
- Renamed "galaxy/star/planet/moon" metaphor to §2 Mental Model; marked as descriptive-only

### Removed (from prior v0.5.1)

- §0 did not previously exist as a status block
- §18 was the full resource synthesis; now it points to the ledger file

---

## v0.5.1

Initial public draft. Single-file spec covering axioms, state model, inference map, routing cycle, capability bands, risk tiers, execution topologies, memory loop, governance, telemetry, control plane, degradation, compatibility, and roadmap. No formal JSON Schema files. AIP and gitmem integration described informally. No task class taxonomy. No harness fingerprinting. No failure taxonomy. No recovery policy.
