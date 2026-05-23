# IMX — Inference Mesh Exchange
### Specification v0.6
> *A filesystem-first routing and governance layer for agent fleets. Provider-agnostic, model-agnostic, harness-agnostic.*

---

## 0. Status

v0.6 is a structural revision of v0.5.1 based on fifteen external reviews, the AIP spec, the gitmem/umx spec, and the resource rework pass.
The normative artifacts are this spec, `catalog/schemas/task_packet.schema.json`, `catalog/schemas/handoff_packet.schema.json`, `CHANGELOG.md`, and `imx-resource-ledger.md`.
The invariant remains: **the filesystem is the truth; everything else is a view, cache, adapter, or runner.**

## Table of Contents

1. [Design Axioms](#1-design-axioms)
2. [Mental Model](#2-mental-model)
3. [What IMX Is and Is Not](#3-what-imx-is-and-is-not)
4. [Relationship to AIP and gitmem](#4-relationship-to-aip-and-gitmem)
5. [State Model: Runtime vs Durable](#5-state-model-runtime-vs-durable)
6. [The Inference Map](#6-the-inference-map)
7. [Routing Cycle](#7-routing-cycle)
8. [Capability Bands, Not Vendor Ladders](#8-capability-bands-not-vendor-ladders)
9. [Risk Tiers](#9-risk-tiers)
10. [Execution Topologies](#10-execution-topologies)
11. [Memory and Guidance Loop](#11-memory-and-guidance-loop)
12. [Governance and Capability Profiles](#12-governance-and-capability-profiles)
13. [Evidence Ingestion and Telemetry](#13-evidence-ingestion-and-telemetry)
14. [Control Plane: TUI First, Always Optional](#14-control-plane-tui-first-always-optional)
15. [Degradation and Resilience](#15-degradation-and-resilience)
16. [Compatibility Contracts and Upgrade Plans](#16-compatibility-contracts-and-upgrade-plans)
17. [Implementation Roadmap](#17-implementation-roadmap)
18. [Resource Synthesis](#18-resource-synthesis)
19. [Research Bibliography](#19-research-bibliography)

---

## 1. Design Axioms

### 1.1 Axioms

- **Filesystem-first.** State lives in files; derived indexes are caches.
- **Unix-native.** Compose tmux, git, JSONL, SQLite, FIFOs, worktrees, lock files, and small CLIs before introducing services.
- **Training-aligned.** Files, git, tmux, bash, Markdown, YAML, JSON, and JSONL are the interfaces LLMs already know how to use.
- **Reworkable over rejectable.** Platform ideas should be stripped to files before being rejected.
- **Low dependency.** Optional adapters are fine; the core must degrade without hosted infrastructure.
- **Provider-agnostic.** Providers are interchangeable leaves, not the architectural center.
- **Model-agnostic.** IMX routes by observed capability, not by brand, size, or leaderboard folklore.
- **Harness-agnostic.** Claude Code, Codex, Copilot, Gemini CLI, OpenCode, shell wrappers, and future CLIs are execution surfaces behind a common file contract.
- **Views never own state.** Dashboards, IDE panels, HTML reports, statuslines, and hosted monitors are projections over files.
- **Durable beats magical.** If a process dies, the files, worktrees, packets, telemetry, and memory survive.

### 1.2 Why These Axioms

IMX exists because agent systems get worse when their real state lives inside a server, broker, SDK object, or opaque framework runtime instead of in places humans and agents can inspect directly. IMX is therefore not a platform. It is a set of routing contracts, policy files, schemas, and local state conventions that can sit on top of ordinary agent tools.

The training-data argument is practical, not aesthetic. Agents have seen millions of examples of `grep`, `tail`, `cat`, `.git/`, Makefiles, shell scripts, Markdown instructions, YAML manifests, JSON logs, and tmux sessions. They have seen far fewer proprietary orchestration APIs. Oracle's February 2026 practitioner analysis states the key distinction directly: filesystems win as an **interface** because models already know how to list, search, and read files; databases or indexes may still be useful substrates or caches when concurrency and query guarantees are required.

The empirical evidence also points at the substrate around the model. Google/MIT's 180-configuration scaling study, AdaptOrch, the financial document processing benchmark, and ORCH all show that topology, harness, routing, and cost policy can dominate raw model choice. The Agent Harness Survey's Grok Code datapoint is the sharpest warning: a SWE-bench score moved from 6.7% to 68.3% after changing the harness edit-tool format while keeping the model unchanged. A model score without the harness fingerprint is not a stable routing fact.

The IMX/AIP/gitmem triad implements cognitive externalization as files: gitmem externalizes durable memory and procedures; AIP externalizes execution, process state, and events; IMX externalizes routing, governance, and telemetry. The right system shape is plural, institutional, and auditable: specialized agents work through shared records, not hidden runtime state.

---

## 2. Mental Model

The lightweight metaphor is descriptive only:

| term | meaning |
|---|---|
| galaxy | one human/operator domain |
| star | a persistent coordinating agent or routing role |
| planet | a persistent worker agent |
| moon | an ephemeral subtask, task handle, one-shot advisor, or workflow step |

The normative interface is files and processes. The metaphor explains topology; it does not replace the protocol.

---

## 3. What IMX Is and Is Not

IMX is a **routing and governance substrate** between execution harnesses and long-term memory.

It is **not**:

- a token proxy
- a hosted control plane
- a mandatory workflow engine
- a memory store
- a dashboard product
- a vendor SDK abstraction pretending to be a protocol

It owns one concern:

**Given this task, this risk tier, this budget, this harness surface, and what we have learned so far, which execution surface should handle the work right now, and with what guardrails?**

IMX is also a context and evidence discipline. It treats task packets, profiles, workflow state, event logs, transcripts, budgets, demo artifacts, and route decisions as first-class artifacts so the operator can reconstruct what happened without trusting a vendor UI.

---

## 4. Relationship to AIP and gitmem

### 4.1 AIP — the Execution Substrate

AIP owns process lifecycle, tmux orchestration, hook normalization, task transport, event emission, task queues, status files, summaries, shims, recursive spawning, and cloud/git bridge patterns.

IMX consumes AIP primitives rather than replacing them:

- `workspace/tasks/` is the dispatch surface for file-backed tasks.
- atomic `mv` claim semantics are the canonical async work-claim mechanism.
- `workspace/events.jsonl` is the live execution event stream.
- `wait_for` is the preferred zero-token blocking primitive for orchestrators waiting on AIP work.
- `workspace/summaries/` and `workspace/transcripts/` are evidence sources for IMX telemetry and gitmem distillation.

### 4.2 gitmem — the Durable Memory Substrate

IMX refers to **gitmem (the umx protocol backed by GitHub)** as the durable memory substrate. `umx` is the memory protocol and local convention; `gitmem` is the Git/GitHub-backed governance and synchronization implementation.

gitmem owns durable memory, scoped facts, procedures, pre-tool guidance, attention refresh, dream consolidation, redaction, search, provenance, and memory governance. IMX owns live routing state, task-outcome telemetry, route-card compilation, confidence decay, and promotion/demotion policy.

High-frequency runtime signals do not belong in gitmem's canonical store. gitmem receives distilled learnings: stable route cards, reusable procedures, known failure patterns, evaluated routing lessons, project constraints, and procedure revisions proposed by the Dream pipeline.

### 4.3 IMX — the Policy and Synthesis Layer

IMX is the glue:

- reads AIP execution state and event logs
- reads gitmem procedures, conventions, and durable lessons
- maintains local routing state and score caches
- emits route decisions, task packets, evidence bundles, profile gates, and operator-readable overlays
- promotes durable lessons to gitmem when evidence warrants

### 4.4 Contract Boundary Rule

If it is about **process lifecycle, tmux panes, task queues, hooks, or live agent coordination**, it belongs in AIP.
If it is about **durable facts, procedures, consolidation, scoped knowledge, or PR governance**, it belongs in gitmem/umx.
If it is about **routing, policy gates, profile selection, telemetry-to-dispatch feedback, budgets, or execution-form choice**, it belongs in IMX.

---

## 5. State Model: Runtime vs Durable

**IMX runtime state is local and fast-moving. Durable IMX knowledge is promoted into gitmem.**

Reference layout:

```text
~/.imx/
├── catalog/
│   ├── nodes.d/             # static node/harness descriptors
│   ├── profiles/            # routing, capability, risk, recovery, budget policies
│   ├── rates/               # provider/model token and fixed-cost rates
│   ├── schemas/             # JSON Schema contracts
│   ├── roles/               # role cards: YAML front matter + Markdown instructions
│   ├── prompts/             # durable prompt assets, not transient task context
│   ├── adapters/            # provider/harness adapter configs
│   └── task_classes.yaml    # operator-defined task-class taxonomy
├── state/
│   ├── probes/              # ephemeral health / latency snapshots
│   ├── quota-status/        # per-provider quota burn and reset state
│   ├── cache-stats.json     # prompt-cache hit rates and cost savings
│   ├── compiled/            # merged route cards / mesh snapshots
│   ├── locks/               # local coordination files
│   ├── budgets/             # per-task budget ledgers
│   ├── approvals/           # approval records for gated work
│   ├── control-intents/     # harness control signals
│   └── dream-triggers.jsonl # IMX nudges for gitmem Dream
├── telemetry/
│   ├── tasks.jsonl          # append-only task outcome log
│   ├── route_decisions.jsonl
│   ├── advice.jsonl
│   ├── switches.jsonl
│   ├── costs.jsonl
│   ├── gate_decisions.jsonl
│   └── control_spans.jsonl
└── cache/
    ├── scores.sqlite        # optional local ranking/eval cache
    ├── skill_index.sqlite   # optional full-text/BM25 skill index
    └── vectors.sqlite       # optional derived semantic index
```

AIP workspace remains the live fleet surface:

```text
workspace/
├── tasks/
│   ├── pending/
│   ├── claimed/
│   ├── done/
│   └── failed/
├── status/
├── summaries/
├── transcripts/
├── events.jsonl
└── artifacts/
    └── demo/
```

gitmem receives only durable layer artifacts:

- stable route cards
- reusable procedures
- known-failure patterns
- promoted heuristics
- evaluated routing lessons
- distilled task-class lessons
- project-specific constraints that should survive restarts and machines

### 5.1 Lifecycle States

Route cards, capability profiles, procedures, node descriptors, prompts, and schemas use lifecycle states:

```text
draft → active → deprecated → archived
```

- **draft** — proposed but not validated. Must pass skeptical verification or empirical evaluation before promotion.
- **active** — current and trusted. Used in routing decisions.
- **deprecated** — superseded, confidence-decayed, or failing. Not used for new routing unless explicitly pinned.
- **archived** — removed from active consideration but retained in git history.

Workflow instances use the richer lifecycle in §10.5.

### 5.2 Provenance

All IMX state and telemetry records should carry provenance metadata:

- `written_by` — agent, shim, script, or human that produced the artifact
- `written_at` — ISO 8601 timestamp
- `source_node` — node that generated or triggered the artifact
- `harness_fingerprint` — harness identity at the time of write
- `confidence` — writer confidence when applicable
- `chain_depth` — agent-to-agent hop count since original human request

Provenance enables audit, contamination tracing, identity hygiene, rollback, and route-card promotion review.

### 5.3 Multi-Machine State Rules

IMX distinguishes syncable configuration from local operational state:

- `~/.imx/catalog/` is syncable and should be version-controlled when reused across machines.
- `~/.imx/state/` is local; probes, locks, budgets, approvals, and compiled snapshots are machine-specific unless explicitly exported.
- `~/.imx/telemetry/` is selectively syncable; task outcomes and route decisions may be useful across machines, but quota probes and local health samples usually are not.
- durable routing lessons promote to gitmem rather than by copying raw local telemetry everywhere.
- secrets, tokens, local paths, and machine identifiers must be redacted before telemetry is synced or promoted.

### 5.4 Write Discipline

Filesystem-first does not mean careless writes:

- write new JSON/JSONL/YAML artifacts to a temporary file and atomically rename into place
- append JSONL as one line per record, ending with `\n`
- use lock files or AIP leases for long-lived claims
- include schema version and provenance in every artifact that crosses a component boundary
- treat SQLite and vector indexes as rebuildable caches, not truth

---

## 6. The Inference Map

The routing unit is a **node descriptor plus per-task-class evidence**, not a model name alone.

A node is:

```text
engine × harness × profile
```

Where:

- **engine** = model/provider/local endpoint
- **harness** = CLI/integration surface and its context/tool/prompt behavior
- **profile** = policy view such as economy, balanced, deep, reviewer, local-only, or sandboxed

Example compiled node record:

```jsonc
{
  "schema_version": "0.6",
  "node_id": "frontier@cli/default",
  "engine": {
    "family": "frontier",
    "provider_class": "remote",
    "cost_band": "high",
    "context_band": "xl",
    "context_window_tokens": 200000
  },
  "harness": {
    "kind": "cli",
    "version_fingerprint": "cc-1.0.72-a3f2",
    "tool_coverage_tier": 1,
    "supports_pre_tool_guidance": true,
    "supports_task_handle": false,
    "supports_interactive_control": false
  },
  "profile": "balanced",
  "live": {
    "availability": "healthy",
    "quota_state": "ok",
    "latency_bucket": "normal",
    "observed_at": "2026-04-27T00:00:00Z"
  },
  "empirical": {
    "code_review": { "ema_score": 0.78, "n": 90, "last_observed": "2026-04-26T11:20:00Z" },
    "bash_execution": { "ema_score": 0.96, "n": 210, "last_observed": "2026-04-27T02:15:00Z" }
  },
  "policy": {
    "allowed_risk_tiers": ["READ_ONLY", "LOCAL"],
    "capability_tags": ["analysis", "review", "cli-tools"],
    "correlation_group": "frontier-cloud-a"
  }
}
```

### 6.1 Harness Fingerprinting

The harness is a tunable variable. It includes prompt packing, context retrieval, compaction, tool descriptions, edit-tool format, retry strategy, output parsing, guardrail hooks, and session control commands.

Each harness adapter must emit a `version_fingerprint` that changes when any material harness behavior changes. When the fingerprint changes, IMX treats it as a drift event and partially resets confidence for affected `engine × harness × task_class` scores. The reset degree is operator-configurable.

The Agent Harness Survey's Grok Code result makes this mandatory: changing only the harness edit-tool format reportedly moved SWE-bench from 6.7% to 68.3%. Meta-Harness and related harness research show the same direction: the model cannot be evaluated apart from the scaffold it runs inside.

### 6.2 Task Class Taxonomy

`task_class` is the primary routing dimension. It is operator-defined, hierarchical, and stored in:

```text
~/.imx/catalog/task_classes.yaml
```

Example:

```yaml
schema_version: "0.6"
task_classes:
  code_review:
    description: review code for correctness, maintainability, and risk
  code_review.security:
    parent: code_review
    description: security-focused review
  implementation:
    description: local code or document changes
  implementation.refactor:
    parent: implementation
  bash_execution:
    description: shell/tool execution and interpretation
  architecture_decision:
    description: system design, tradeoff, or protocol decision
  documentation:
    description: docs, specs, examples, and changelogs
```

Rules:

- task classes are strings, not hard-coded enums in the core protocol
- dotted names refine broader classes
- parent class scores may be used as priors for child classes
- new classes can be added organically, but durable additions should be reviewed
- schemas and evals should reference `task_class` exactly so telemetry remains comparable

### 6.3 Evidence Precedence

Routing evidence precedence is normative even if scoring internals vary:

1. **policy gates** — hard allow/deny
2. **live health/quota gates** — hard go/no-go
3. **budget gates** — soft warning or hard stop, depending on profile
4. **empirical task outcomes** — primary ranking signal
5. **local evals and structured priors** — cold-start support
6. **gitmem procedures and route cards** — durable local knowledge
7. **community reports and public sentiment** — weakest signal, advisory only

### 6.4 Rating Algorithm

IMX recommends **Exponential Moving Average (EMA)** as the concrete baseline rating algorithm:

```text
ema_next = alpha * observation + (1 - alpha) * ema_previous
```

Maintain separate EMA series per `node_id × task_class × harness_fingerprint` for quality, latency, cost, stability, and refusal/format compliance. ORCH validates EMA-guided deterministic routing as a simple, reproducible baseline; it naturally down-weights stale history by making recent telemetry matter more than ancient telemetry.

Rules:

- successes and failures update task-class-specific scores
- latency, cost, and stability are separate signals, not hidden inside one opaque score
- controllable failures reduce quality confidence; uncontrollable failures update health/stability, not task capability
- `last_observed` and `n` are stored with every score
- harness drift partially resets score confidence
- new nodes receive bounded exploration traffic
- weak priors never outrank strong recent empirical evidence

More complex routers are allowed only as file-backed, replayable extensions. FrugalGPT, RouteLLM, and LLMRouterBench validate cost-aware learned routing but also warn that complex routers must beat simple baselines under local evals. A learned router artifact is a cache or compiled policy over files, not a hosted dependency.

---

## 7. Routing Cycle

```text
0. parse/decompose
   -> is this task atomic, decomposable, workflow-shaped, or advisory?
   -> if decomposable, create subtasks or workflow steps with idempotency keys
   -> decomposition may itself be routed

1. classify
   -> task_class, relationship, required capabilities, risk_tier, budget,
      persistence_need, context_need, topology candidates

2. gather
   -> candidate nodes from catalog/profile filters
   -> relevant gitmem procedures and route cards
   -> live probes, budgets, approvals, task-class scores, interest maps

3. gate
   -> remove nodes blocked by policy, quota, availability, context limits,
      executable guardrails, approval requirements, or hard budgets
   -> gate responses: ALLOW, THROTTLE, SANDBOX, AUDIT, DENY

4. rank
   -> EMA quality/stability by task_class
   -> apply local eval priors and durable route cards
   -> adjust for cost, latency, context fit, risk, and correlation group
   -> prefer simple baselines unless learned routing has local evidence

5. choose execution form and topology
   -> persistent teammate
   -> task-handle subtask
   -> one-shot advisor
   -> cloud contractor
   -> file-backed iterative workflow (§10.5)
   -> harness-controlling-harness (§10.6)
   -> topology: single, parallel, sequential, hierarchical, hybrid

6. dispatch
   -> write route decision record
   -> emit task packet validated by JSON Schema
   -> dispatch via AIP task file, pane, shim, or adapter
   -> for EXTERNAL risk tier, require approval and demo evidence contract

7. observe
   -> map AIP events into IMX telemetry (§13.1)
   -> update EMA scores and budget ledgers
   -> classify failures (§12.5)
   -> apply recovery policy (§15.1)
   -> promote durable lessons to gitmem when warranted
```

IMX should escalate **form** before it escalates **expense**:

- ask a stronger advisor
- spawn a skeptic
- split the problem
- switch topology
- request a human gate
- only then move to a more expensive capability band

Budget-aware cascades are first-class policy. A profile may say: try an economy classifier, then a balanced implementer, then a deep reviewer only if confidence is low or risk is high. This is stored as YAML policy, logged as route decisions, and replayable from telemetry.

---

## 8. Capability Bands, Not Vendor Ladders

The core spec must not hard-code a vendor ladder. Operators map actual nodes into capability bands.

| band | purpose |
|---|---|
| `economy` | triage, classification, cheap first pass |
| `balanced` | default implementation and review |
| `deep` | complex reasoning, synthesis, long tasks |
| `frontier` | highest-capability fallback / last-resort escalation |
| `specialist` | domain-specific nodes such as code, math, finance, security, search |
| `local-trusted` | offline / privacy / resilience path |
| `sandboxed` | risky actions requiring isolated execution |
| `distilled` | task-specific SLMs for high-volume classification, routing, and repetitive subtasks |

### 8.1 Structured Agent Conventions

IMX consumes agent-readable convention files where present:

- `AGENTS.md`
- nested scoped instruction files
- `DESIGN.md`
- `CLAUDE.md`
- role cards in `~/.imx/catalog/roles/*.md`
- gitmem procedures and `CONVENTIONS.md`
- skill directories such as `skills/{namespace}/{skill}/SKILL.md`

Instruction precedence is:

```text
task packet
  > nearest scoped instruction file
  > repo root AGENTS.md
  > role card
  > profile default
```

Conflicts should be surfaced as warnings in route decisions or context lint artifacts. The router should not silently merge contradictory instructions.

Role cards are Markdown files with YAML front matter:

```markdown
---
role_id: implementer
capability_profile: implementer
allowed_risk_tiers: [READ_ONLY, LOCAL]
task_classes: [implementation, debugging, test_writing]
---

# Implementer

Make minimal, tested changes. Prefer worktrees for mutation tasks.
```

Skill packs are directories, not marketplace entries:

```text
skills/{namespace}/{skill}/
├── SKILL.md
├── examples/
├── schemas/
└── scripts/
```

Full-text skill bodies should be indexed as a derived cache for routing. Metadata-only skill routing is insufficient when large skill registries overlap.

---

## 9. Risk Tiers

Capability and consequence remain separate.

```text
READ_ONLY  -> reads, analysis, search, summarization
LOCAL      -> local edits, local git, tests, refactors, local build steps
EXTERNAL   -> push, deploy, publish, remote writes, production or network side effects
```

Rules:

- the task takes the highest applicable risk tier
- risk tier gates execution even when capability is high
- quota and latency do not override risk policy
- `sandbox_required` may be layered on top of `LOCAL` or `EXTERNAL`
- EXTERNAL tasks require an approval record and a demo/evidence artifact unless explicitly exempted by profile

### 9.1 Staging Semantics

For `LOCAL` and `EXTERNAL`, IMX recommends staging before commit. Mutation tasks should write to a staging area first; promotion to the live workspace is a separate, verifiable step. A git worktree is the default staging area.

For `EXTERNAL`, promotion should require:

- approval file in `~/.imx/state/approvals/{task_id}.json`
- route decision evidence
- capability profile used at dispatch
- diff or deployment artifact
- `artifacts/demo/{task_id}.md` describing what changed, what was verified, and what remains for human judgment

### 9.2 Governance Calibration

Governance must be calibrated, not maximal. IMX's gate responses are graduated:

```text
ALLOW     -> proceed normally
THROTTLE  -> allow but reduce dispatch frequency or budget
SANDBOX   -> allow only with worktree/container/restricted profile
AUDIT     -> allow but require post-hoc review
DENY      -> hard block
```

Over-restriction can collapse system utility. Under-restriction increases blast radius. The profile's job is to pick the minimum viable capability set for the task and risk tier.

---

## 10. Execution Topologies

IMX treats execution form as part of routing.

**Scaling principle:** multi-agent execution is not reliably beneficial. Google/MIT's scaling study, phase-transition research, and production failure reports show that coordination overhead, context fan-in, and correlated errors can erase or reverse the benefits of adding agents. Default to a single suitable node unless the task is decomposable, evidence supports multi-agent routing, or risk requires independent review.

| topology | when to use | failure mode |
|---|---|---|
| single | task is atomic, tool-heavy, or already within one node's capability | under-review on high-risk work |
| parallel | independent subtasks, broad search, low shared-error correlation | merge overhead and duplicated cost |
| sequential | plan → implement → review or staged deployment | upstream errors cascade |
| hierarchical | supervisor-worker with selective escalation | supervisor bottleneck |
| hybrid | workflow-specific mix of the above | hidden complexity if not file-backed |

The financial document processing benchmark is a useful topology signal: reflexive loops achieved the highest F1 but at high cost; hierarchical supervisor-worker occupied the best cost-accuracy Pareto point at about 0.921 F1 and 1.4× baseline cost. IMX should prefer hierarchical task delegation over reflexive conversational swarms when it needs scalable production balance.

### 10.1 Worktree Isolation

Parallel coding should default to separate worktrees.

AIP should provision a worktree when IMX chooses a persistent teammate, task-handle, or workflow step that mutates files:

```text
.worktrees/{task_id}/
```

Worktree isolation plus restricted capability profile is the file-first rework of hosted cloud sandboxes.

### 10.2 Task and Handoff Packets

Task and handoff packets are formal contracts, not examples. The normative schema files are:

```text
catalog/schemas/task_packet.schema.json
catalog/schemas/handoff_packet.schema.json
```

AIP may still transport tasks as Markdown files, but any IMX-enriched task should include or reference a JSON packet that validates against the schema. SDK types, Pydantic models, Instructor classes, and framework objects are optional convenience layers over the schema file.

Minimum task packet concepts:

- `task_id`, `schema_version`, `task_class`, `risk_tier`, `relationship`
- instruction payload or file references
- budget and budget gate mode
- routing/capability profile
- worktree and workflow step metadata
- memory refs and context refs
- approval policy and required artifacts
- contamination risk and untrusted source classes
- provenance block with `chain_depth` and `harness_fingerprint`

Minimum handoff packet concepts:

- source and target agent/node identity
- summary of completed work
- artifacts and file references
- decisions, open questions, and next actions
- budget consumed
- failure classification when applicable
- contamination risk and sanitization steps
- provenance chain and `chain_depth`

### 10.3 Interest Maps as Impetus Controls

AIP's interest maps are more than passive affinity. They are cost and impetus controls:

- who should read which events
- who should actively `notify` whom
- who should be interrupted
- which summaries matter at task boundaries

IMX may adjust interest maps at dispatch time, but they remain soft routing hints unless the operator profile declares them mandatory.

### 10.4 Async Task Handles

Spawned work should return a durable handle that can be polled, cancelled, replayed, and tailed.

AIP already provides the file pattern:

```text
workspace/tasks/pending/
workspace/tasks/claimed/
workspace/tasks/done/
workspace/tasks/failed/
workspace/status/
workspace/events.jsonl
```

Agents claim tasks with atomic moves. Orchestrators wait with AIP `wait_for`, not token-burning polling loops. This is the filesystem equivalent of async futures.

### 10.5 File-Backed Iterative Workflows

The workflow is files:

```text
workflow/
├── definition.yaml
├── state.json
├── progress.md
├── checkpoints/
└── artifacts/
```

Workflow lifecycle states:

```text
pending
running
blocked
retrying
succeeded
failed
compensating
cancelled
```

Required semantics:

- each step has an `idempotency_key`
- each step declares `task_class` and `risk_tier`
- retries, timeouts, max iterations, and budget caps live in `definition.yaml`
- `state.json` records current step, attempt count, lifecycle, blocked reason, and resume token
- checkpoints are files, not hidden scheduler state
- compensation steps are explicit workflow steps, not implicit cleanup code
- the runner may be a script, harness, or agent, but the state machine lives in files

Minimal `definition.yaml` example:

```yaml
schema_version: "0.6"
name: review-cycle
budget:
  max_cost_usd: 5.00
  max_iterations: 10
retry:
  max_retries: 2
  backoff: exponential
steps:
  - id: implement
    task_class: implementation
    risk_tier: LOCAL
    idempotency_key: "review-cycle:implement"
    exit_when: "tests pass"
  - id: review
    task_class: code_review
    risk_tier: READ_ONLY
    depends_on: [implement]
  - id: revise
    task_class: implementation
    risk_tier: LOCAL
    depends_on: [review]
    max_iterations: 3
    exit_when: "reviewer approves"
```

LangChain/LangGraph, CrewAI, AutoGen, Temporal, Airflow, visual workflow studios, and Ralph-style loops all reduce to this pattern: graph or loop definition in YAML, state in JSON, outputs in artifacts, and execution by interchangeable harnesses.

Conversational swarms should be reworked into shared review files and git review patterns:

```text
workspace/reviews/{task_id}/
├── proposal.md
├── reviewer-a.md
├── reviewer-b.md
├── resolution.md
└── decision.json
```

Agents know how to review diffs, append Markdown comments, and resolve review threads because GitHub PR/code-review patterns are heavily represented in training data. A chatroom runtime is not required.

### 10.6 Harness-Controlling-Harness Topology

An orchestrator agent may control another interactive harness through filesystem control intents, with AIP translating intents into harness-specific commands.

Generic intent files:

```text
~/.imx/state/control-intents/{session_id}/
├── compact.intent
├── rewind.intent
├── switch_model.intent
├── clear.intent
├── pause.intent
└── resume.intent
```

Example `switch_model.intent`:

```yaml
schema_version: "0.6"
intent: switch_model
task_id: task-042
session_id: coder-1
target_model_band: economy
reason: "remaining steps are mechanical"
requested_by: orchestrator-1
ts: "2026-04-27T00:00:00Z"
```

Rules:

- IMX emits generic intents; AIP/harness adapters translate them to `/compact`, `/rewind`, `/model`, tmux `send-keys`, API calls, or no-op when unsupported.
- every control action appends to `~/.imx/telemetry/control_spans.jsonl`
- session health thresholds live in adapter/profile files
- triggers may include context usage >80%, topic drift, repeated malformed outputs, refusal, or low remaining budget
- controller×subordinate pair performance is scored as a compound routing signal

This topology is advanced. It must be evaluated locally before becoming default behavior.

### 10.7 Advisor-Executor Topology

The advisor-executor topology routes a single task to two differently-scoped nodes:

- **executor** — a cheaper node that performs the implementation loop (write, test, iterate)
- **advisor** — a frontier or domain node consulted only at specific decision surfaces:
  - initial plan approval
  - stalled-progress corrections
  - pre-commit confidence gate for high-risk changes

The split is a routing policy, not a framework: the executor emits a gate file or approval request; the advisor reads that file, responds to it, and the executor resumes. File format:

```text
workspace/gates/gate-{task_id}-{stage}.json
```

Gate file schema:
```json
{
  "schema_version": "0.6",
  "task_id": "...",
  "stage": "plan|correction|pre-commit",
  "executor": "...",
  "context_summary": "...",
  "question": "...",
  "created_at": "..."
}
```

The advisor writes its response back to:
```text
workspace/gates/gate-{task_id}-{stage}.response.json
```

This topology is preferable to a reflexive loop because the cost of the advisor is bounded to discrete gate crossings rather than injected into every iteration step. Profile YAML should declare which stages trigger advisor consultation:

```yaml
advisor_gates:
  - stage: plan
    advisor_profile: frontier-reviewer
  - stage: pre-commit
    min_risk_tier: LOCAL
    advisor_profile: frontier-reviewer
```

### 10.8 Multi-Model Voting at Gates

When a gate decision requires high confidence, a coordinator may dispatch the same sub-question to multiple nodes and aggregate their votes. This is an explicit routing decision, not a background retry loop.

Rules:
- voting is declared in profile YAML per gate stage and risk tier
- each vote is emitted as a separate route decision record
- disagreement is surfaced as an uncertainty signal, not silently resolved
- the aggregation function (majority, quorum, threshold) is stored in the profile

Disagreement file:
```text
workspace/gates/vote-{gate_id}.json
```

```json
{
  "schema_version": "0.6",
  "gate_id": "...",
  "votes": [
    { "node": "...", "verdict": "approve", "confidence": 0.9 },
    { "node": "...", "verdict": "reject", "confidence": 0.7 }
  ],
  "outcome": "disagreement",
  "escalated_to": "human|advisor|deny"
}
```

Voting is bounded work: all voted nodes see the same bounded context artifact, and vote collection is synchronous within the routing step 3 (gate). Disagreement is an outcome, not an error — it triggers escalation per recovery policy (§15.1).

---

## 11. Memory and Guidance Loop

IMX adopts gitmem/umx terminology instead of inventing near-duplicates.

### 11.1 Pre-Tool Guidance

Before risky or semantically important tool actions, IMX or AIP may ask gitmem for:

- matched procedures
- task-class constraints
- project conventions
- relevant fragile or stable facts
- scoped `CONVENTIONS.md` guidance

Guidance should be progressively disclosed and positioned to avoid lost-in-the-middle failures.

### 11.2 Attention Refresh

Long sessions drift. IMX reuses gitmem's attention refresh for:

- long implementation sessions
- multi-agent handoffs
- resumed tmux sessions
- workflow iteration boundaries
- post-compaction state restoration

### 11.3 Dream Triggers

gitmem owns the Dream pipeline. IMX owns when to nudge it.

IMX writes Dream trigger records to:

```text
~/.imx/state/dream-triggers.jsonl
```

Record format:

```json
{
  "trigger_type": "query_gap",
  "source": "imx-router",
  "query": "procedure for EXTERNAL deployment evidence bundle",
  "context": {
    "task_id": "task-042",
    "task_class": "deployment",
    "risk_tier": "EXTERNAL",
    "route_decision_id": "rd-01J..."
  },
  "ts": "2026-04-27T00:00:00Z"
}
```

Allowed `trigger_type` values include `query_gap`, `route_failure`, `context_saturation`, `large_task_completion`, `entrenchment_risk`, `procedure_regression`, and `policy_drift`.

### 11.4 Skeptical Verification

Challenge high-impact promotions, route reweightings, surprising claims, and EXTERNAL evidence before they become durable policy.

Use skeptic/debate artifacts such as:

```text
eval/debates/{topic}.md
workspace/reviews/{task_id}/resolution.md
```

### 11.5 Secret and Policy Scanning

gitmem's fail-closed redaction posture applies to IMX boundary artifacts:

- handoff packets
- task packets
- transcripts
- exported summaries
- route and memory overlays
- demo artifacts
- policy decisions

Secret detection and policy enforcement must block unsafe propagation before the next model call.

### 11.6 Contamination Hygiene

When Agent A's output becomes Agent B's context, errors and bias can compound. IMX mitigates this with:

- summarize-and-verify at handoff boundaries
- periodic independent re-evaluation by a clean agent
- star/hub topologies over long chains when risk is high
- `chain_depth` tracking in packets and telemetry
- confidence decay per hop, weighted by peer reliability
- contamination tracing through provenance
- explicit `contamination_risk.untrusted_sources` in packets

Tool definitions, tool descriptions, and tool registries are also contamination surfaces. Runtime tool mutation is forbidden unless it produces a tracked artifact and passes review.

### 11.7 Entrenchment Detection

Memory systems can become echo chambers. gitmem's Dream pipeline should periodically flag route cards and procedures that:

- originate from one source
- have never been challenged
- are frequently injected
- influence high-risk routing
- lack fresh supporting telemetry

IMX emits an `entrenchment_risk` Dream trigger when it detects this pattern.

### 11.8 Context Artifacts

Context engineering should be inspectable:

```text
context/
├── manifest.yaml       # selected sources and why
├── sources.json        # exact file/tool references
├── packed/             # context bundles sent to agents
├── compactions/        # summaries created during session control
└── lint.json           # poisoning/distraction/confusion/clash findings
```

Context manifests are evidence. They help explain why a node saw a file, procedure, or summary and make compaction auditable after the fact. Structured Context Engineering research confirms file-native context retrieval helps frontier models at scale, but open-weight/local models may need different packing strategies — routing profiles should account for this by varying context density per capability band.

### 11.9 Procedure and Graph-Memory Rework

DSPy-style prompt optimization maps to gitmem:

```text
eval feedback -> Dream trigger -> procedure revision -> git PR -> reviewed merge
```

OPA/policy-as-code maps to IMX/AIP:

```text
profile YAML + optional policy/*.rego -> AIP pre-tool hook -> gate_decisions.jsonl
```

Graph memory maps to gitmem:

```text
append-only atomic fact files -> derived SQLite/graph/vector index
```

The graph index is a cache. The fact files and git history are the truth.

---

## 12. Governance and Capability Profiles

### 12.1 Capability Profiles

Capability profiles are versioned YAML files enforced by shims, wrappers, hooks, and optional signed manifests.

Path:

```text
~/.imx/catalog/profiles/*.yaml
```

AIP shims should consume these files directly before spawn, dispatch, and tool execution.

Example:

```yaml
schema_version: "0.6"
profile_id: implementer
allow: [read_file, edit_file, bash, git_commit]
deny: [git_push, publish, production_write]
risk_tiers: [READ_ONLY, LOCAL]
budget_gate: soft
approval_required_for: [EXTERNAL]
pre_tool_hooks:
  - name: migration-delete-guard
    tool_pattern: "bash|edit_file"
    script: "~/.imx/catalog/guardrails/no_delete_migrations.sh"
    on_fail: DENY
policy:
  opa_bundle: "~/.imx/catalog/policy/implementer.rego"
log_decisions_to: "~/.imx/telemetry/gate_decisions.jsonl"
```

Executable guardrails are allowed and recommended for high-risk profiles. GuardAgent validates the pattern of translating policy into executable checks; IMX's file-first version is simpler: capability profiles reference shell/Python scripts that run as pre-tool hooks and return allow/deny through exit codes and JSONL decisions.

### 12.2 Signed Manifests and Governance Descriptors (Optional)

Signed manifests may bind:

- `agent_id`
- `node_id`
- `capability_profile`
- `allowed_tools`
- `harness_fingerprint`
- schema versions
- public key or signing identity

Signing is optional, not foundational. Unsigned local workflows remain valid when the operator accepts local trust boundaries.

**HUMANFILE** is a plaintext sentinel that declares a human co-signer is required for this workflow. Placing a `HUMANFILE` in `~/.imx/state/approvals/` or a project root signals to shims and hooks that all EXTERNAL-tier actions require an additional human approval record before dispatch proceeds. Its presence alone is the signal; the file content is advisory.

**pin.caps** is an optional signed JSON capability descriptor that binds an agent or role to a fixed set of allowed tools, risk tiers, and profile constraints. Signing uses a local key; verification happens at the shim layer before dispatch.

```json
{
  "schema_version": "0.6",
  "agent_id": "coder-1",
  "node_id": "balanced@codex/implementer",
  "capability_profile": "implementer",
  "allowed_tools": ["read_file", "edit_file", "bash", "git_commit"],
  "allowed_risk_tiers": ["READ_ONLY", "LOCAL"],
  "signed_by": "operator-key-id",
  "signed_at": "2026-04-27T00:00:00Z",
  "expires_at": "2026-05-27T00:00:00Z"
}
```

These descriptors are file-first equivalents of hardware-bound role attestation: a single readable JSON file that any shim, hook, or human can inspect and validate without calling a service.

### 12.3 Promotion, Demotion, and Exploration

Per `node × harness × task_class`:

- success increases trust
- controllable failure decreases trust
- uncontrollable failure updates health/stability, not task skill
- repeated failures reduce priority or trigger cooldown
- harness drift partially resets confidence
- new nodes receive bounded exploration
- human pinning can override scores

Exploration policy lives in profiles:

```yaml
exploration:
  traffic_pct: 0.10
  max_tasks: 25
  max_days: 14
  stop_when_confidence_gte: 0.75
```

#### Pre-Mortem Gate

Before committing to a plan with risk tier LOCAL or EXTERNAL, IMX SHOULD require a pre-mortem step:

1. The executor produces a plan summary in `workspace/tasks/{task_id}/plan.yaml`
2. A reviewer (human or advisor node) lists the top failure modes in `workspace/tasks/{task_id}/pre-mortem.md`
3. Plan is revised or approved-with-risk in `workspace/gates/gate-{task_id}-plan.response.json`

The pre-mortem is a file exchange, not a blocking dialog. If no human or advisor is available, the executor MAY conduct a self-directed pre-mortem constrained to the failure taxonomy in §12.5.

### 12.4 Eval, Demo, and Evidence Artifacts as Files

Borrow from eval tooling, not platforms:

```text
eval/
├── specs/*.yaml
├── runs/{run_id}/attempts/{n}.json
├── baselines/*.json
├── reports/*.md
└── debates/*.md

artifacts/
└── demo/*.md
```

Rules:

- eval reports include mean, variance, attempts, outliers, baseline deltas, and repeated-trial reliability (pass^k: probability of k consecutive successes under identical conditions)
- rubrics separate process from outcome
- criteria should be non-overlapping
- cascading-error-free scoring should avoid penalizing downstream nodes for upstream failures
- harness-as-variable evals compare the same engine across harness fingerprints
- security eval packs are first-class eval specs
- `artifacts/demo/*.md` is required for EXTERNAL tasks and recommended for substantial LOCAL mutations

Additional eval patterns:

**Chaos eval specs** — fault injection as local YAML:
```text
eval/specs/chaos-{label}.yaml
```
Each chaos spec declares fault type, injection point, expected degradation, and pass criteria. Results land in `eval/runs/{run_id}/`.

**Autoresearch loops** — automated discovery of what to measure:

When an agent proposes new eval dimensions, the proposal is written to `eval/proposals/{slug}.md` with: proposed metric, rationale, baseline, and acceptance criterion. An operator or L2 reviewer promotes it to `eval/specs/`. The loop is file-backed: proposal → review → spec → run → baseline update.

**Continuous eval matrix** — scheduled multi-harness, multi-model cross-product:
```text
eval/matrix.yaml
```
Declares which tasks, models, and harness fingerprints to compare. Scheduled runs append to the shared baselines and emit disagreements as `eval/flags/{run_id}.md`.

**Adversarial review** — a skeptic node reads the plan, code, and gate decisions and produces `eval/debates/{topic}.md`. This is the primary defense against a confident but wrong executor.

**Calibration eval specs** — test whether the agent knows its own limits before acting:
```text
eval/specs/calibration-{label}.yaml
```
Each calibration spec defines a scenario where the agent MUST state its uncertainty, cite any missing context, and request escalation or more information before proceeding with a risky action. Pass criteria: escalation triggered at the right threshold; fail criteria: confident execution without surfacing known unknowns. This is a distinct eval category from chaos evals (which inject external faults) — calibration evals probe internal epistemic state.

Demo artifacts should include:

- what changed
- commands run
- outputs or screenshots when relevant
- tests passed/failed
- residual risks
- human verification needed

### 12.5 Failure Taxonomy

Every failed or degraded outcome has both a controllability class and a failure type.

Controllability:

```text
controllable
uncontrollable
cascade
unknown
```

Failure types:

| type | meaning | routing consequence |
|---|---|---|
| `context_exceeded` | node ran out of usable context | try larger context, compact, or split |
| `capability_gap` | node lacks required skill | try specialist or higher band |
| `quality_failure` | output completed but failed rubric | reduce node×task_class confidence |
| `refusal` | node refused or over-blocked | check policy/profile, maybe reroute |
| `timeout` | wall-clock or lease exceeded | retry by policy or fallback |
| `infrastructure` | API down, quota, network, tool unavailable | health demotion, no skill penalty |
| `cascade` | failed because upstream artifact was wrong | penalize upstream cause, not downstream symptom |

### 12.6 Identity Hygiene

IMX governs Capability, Knowledge, and Identity.

Checks:

- declared role in packet matches dispatched capability profile
- `provenance.source_node` matches the node IMX dispatched
- tool requests are compatible with capability profile
- handoffs increment `chain_depth`
- profile violations write to `gate_decisions.jsonl` and may trigger cooldown or quarantine

Identity hygiene is a consistency check by default, not a mandatory cryptographic protocol.

---

## 13. Evidence Ingestion and Telemetry

IMX ingests by signal class, not vendor.

| signal class | role |
|---|---|
| local telemetry | primary evidence |
| AIP events | live execution correlation |
| transcripts | replay and contamination audit |
| live probes | health gate |
| local evals | cold-start and regression evidence |
| release notes / changelogs | drift detection |
| harness config changes | confidence reset trigger |
| community reports | weak advisory signal |

Each `~/.imx/telemetry/tasks.jsonl` record should include:

- `task_id`
- `route_decision_id`
- `node_id`
- `agent`
- `task_class`
- `risk_tier`
- `capability_profile`
- `harness_fingerprint`
- `topology`
- `budget_allocated`
- `budget_consumed`
- `tokens_in`, `tokens_out`, `tokens_total`
- `estimated_cost_usd`
- `outcome`
- `outcome_class`
- `failure_type`
- `chain_depth`
- `summary_ref`
- `demo_artifact`
- `started_at`, `completed_at`, `duration_ms`

#### Evidence Bundles and Root-Cause Analysis

When a task fails or produces a degraded outcome, IMX should emit an evidence bundle before applying a rating penalty:

```text
~/.imx/telemetry/rca/{task_id}.json
```

RCA bundle schema:
```json
{
  "schema_version": "0.6",
  "task_id": "...",
  "failure_type": "...",
  "controllability": "...",
  "evidence": {
    "gate_decisions": [...],
    "tool_events": [...],
    "last_heartbeat": "...",
    "budget_at_failure": {}
  },
  "root_cause_hypothesis": "...",
  "contributing_factors": [],
  "rating_adjustment_blocked_until_reviewed": false
}
```

Rating adjustments for cascade failures MUST reference the RCA bundle so the penalized node is the upstream cause, not the downstream symptom.

#### Git Line Attribution as Provenance

When an agent modifies a file, the modified line range, commit hash, and task_id form a provenance triple. This triple is the strongest local evidence that an agent touched a specific artifact:

```json
{
  "provenance": {
    "commit": "abc123",
    "file": "src/auth.py",
    "line_range": [42, 67],
    "task_id": "task-042",
    "agent": "coder",
    "harness_fingerprint": "..."
  }
}
```

Git line attribution is a routing signal: if a file was last touched by a node with low task_class confidence, the routing decision to return to that file should prefer a different node or require advisor review.

Governance overlays (risk tiers, gate decisions, policy verdicts) MUST never erase the git-layer provenance — policy is recorded alongside the fact, not in place of it.

### 13.1 Event Schema Mapping

AIP emits live execution records to:

```text
workspace/events.jsonl
```

IMX maps those events into task telemetry. AIP remains the event owner; IMX enriches events with routing metadata.

| AIP field | IMX field | notes |
|---|---|---|
| `ts` | `completed_at`, `observed_at`, or event timestamp | depends on event type |
| `agent` | `agent`, then resolved to `node_id` | resolution uses status files and route decision record |
| `event` | `aip_event` | e.g. `status`, `progress`, `export`, `task` |
| `status` | `outcome` / lifecycle hint | `finished` → `succeeded`; `failed` → `failed`; `blocked` → `blocked` |
| `message` | `message` | advisory evidence, not a routing score by itself |
| `progress` | `progress` | optional progress text |
| `file` | `summary_ref` or artifact ref | for `export` events |
| `target` | `target_agent` | for task/notify events |
| `task` | `task_title` or `instructions_ref` | free text should not replace packet fields |

When an AIP task completes, IMX should correlate:

1. most recent matching route decision by `task_id` or `agent`
2. AIP status event with `status: finished|failed|blocked`
3. exported summary event, if present
4. task packet and handoff packet provenance
5. budget ledger and token/cost observations

Then IMX appends a `tasks.jsonl` record. If correlation is incomplete, IMX still writes telemetry with `correlation_status: partial` and `missing_fields`.

Example completion mapping:

```jsonc
// AIP
{"ts":"2026-03-17T14:25:12Z","agent":"coder","event":"status","status":"finished"}
{"ts":"2026-03-17T14:25:13Z","agent":"coder","event":"export","file":"summaries/coder-0317-1425.md"}

// IMX telemetry
{
  "schema_version": "0.6",
  "task_id": "task-042",
  "node_id": "balanced@codex/implementer",
  "agent": "coder",
  "task_class": "implementation",
  "risk_tier": "LOCAL",
  "capability_profile": "implementer",
  "harness_fingerprint": "codex-cli-0.43.0-a1b2",
  "outcome": "succeeded",
  "outcome_class": "success",
  "summary_ref": "workspace/summaries/coder-0317-1425.md",
  "completed_at": "2026-03-17T14:25:12Z"
}
```

### 13.2 Cost Accounting

Cost is routing state.

Inputs:

- token counts emitted by harness adapters
- provider/model rates in `~/.imx/catalog/rates/*.yaml`
- fixed per-call costs where applicable
- optional provider billing APIs as adapters
- local budget files in `~/.imx/state/budgets/{task_id}.json`

Rate file example:

```yaml
schema_version: "0.6"
provider: example
models:
  frontier-x:
    input_per_million_usd: 3.00
    output_per_million_usd: 15.00
    effective_from: "2026-04-01"
```

Budget gates:

- **soft** — warn, log, and prefer cheaper route
- **hard** — deny dispatch when budget is exhausted

Cost telemetry should be aggregated by task class and profile so future routing can choose cheaper nodes when quality is equivalent.

### 13.3 Quota Status and Cache Statistics

Quota state and cache efficiency are first-class routing inputs, not observability afterthoughts.

`~/.imx/state/quota-status/<provider>.json` captures current quota burn, reset times, and remaining capacity per provider. The router consults these before dispatching so it can avoid mid-task quota exhaustion and prefer providers with headroom.

`~/.imx/state/cache-stats.json` tracks prompt-cache hit rates, estimated cost savings, and per-session cache efficiency. Effective per-token cost is lower when cache rates are high; budget projections and routing preferences for cache-warm paths should reflect this.

Quota-status example:

```json
{
  "schema_version": "0.6",
  "provider": "example",
  "updated_at": "2026-04-27T12:00:00Z",
  "quota": {
    "requests_per_minute": { "used": 45, "limit": 60, "reset_at": "2026-04-27T12:01:00Z" },
    "tokens_per_day": { "used": 1200000, "limit": 10000000 }
  },
  "status": "ok"
}
```

Cache-stats example:

```json
{
  "schema_version": "0.6",
  "updated_at": "2026-04-27T12:00:00Z",
  "sessions": {
    "coder-1": { "cache_hit_rate": 0.62, "tokens_saved": 48000, "cost_saved_usd": 0.14 }
  },
  "aggregate": { "cache_hit_rate": 0.58, "cost_saved_usd": 0.91 }
}
```

Quota-status files are written by harness adapters or probe scripts and are ephemeral — probe scripts overwrite them each cycle. Cache-stats are written by harness adapters or token-counting shims.

---

## 14. Control Plane: TUI First, Always Optional

Operator surfaces read state; they do not own state.

Priority order:

1. tmux statusline / sidebar / top-style views
2. file-backed Kanban / queue board
3. read-only TUI dashboard
4. optional HTML, IDE, or hosted adapters

Core surfaces:

- `workspace/events.jsonl`
- `workspace/status/`
- `workspace/tasks/`
- `workspace/transcripts/`
- `~/.imx/state/compiled/mesh.json`
- `~/.imx/telemetry/*.jsonl`

### 14.1 Closed-Loop Enforcement

Telemetry must produce consequences:

- repeated `node × task_class` failures reduce score
- quota probes trigger health demotion
- hard budget exhaustion blocks dispatch
- executable guardrail failures deny tool use
- contamination or identity anomalies trigger quarantine or review
- recovery policy writes fallback tasks or escalations

The operator can override automated responses. Overrides are files and events too.

### 14.2 Auditability

The control plane should answer:

**Why was this task dispatched to this node?**

from files alone:

- route decision record
- task packet
- profile and guardrail decisions
- node descriptor and EMA scores
- AIP event correlation
- budget ledger
- summary/demo artifacts
- gitmem route cards or procedures used

---

## 15. Degradation and Resilience

The system fails transparent and local:

```text
IMX unavailable
  -> AIP falls back to static capability routing or manual dispatch

gitmem unavailable
  -> IMX routes using local policy + telemetry only

live probes absent
  -> health gating degrades to cached observations

frontier providers unavailable
  -> local-trusted / balanced / economy bands compress upward

harness changes silently
  -> fingerprint mismatch or outcome drift resets confidence

contamination detected
  -> affected state quarantined; clean agent re-evaluates original sources

telemetry loop detects repeated failures
  -> confidence reduction, cooldown, fallback, or demotion
```

### 15.1 Recovery Policy

Recovery policy is file-backed YAML, usually in a profile:

```yaml
schema_version: "0.6"
recovery:
  retry_limits:
    infrastructure: 2
    timeout: 1
    context_exceeded: 1
    quality_failure: 0
    capability_gap: 0
    refusal: 0
  fallback_chain:
    - same_band_next_best
    - specialist_match
    - higher_capability_band
    - human_escalation
  cooldowns:
    consecutive_failures: 3
    duration_seconds: 3600
  escalation:
    external_failure: human
    repeated_cascade: skeptic_review
```

Rules:

- retry infrastructure failures sparingly on the same node
- do not retry quality or capability failures on the same node by default
- fall back within the same band before escalating cost
- cooldown nodes with repeated failures
- escalate EXTERNAL failures to human review
- log every retry, fallback, cooldown, and escalation

---

## 16. Compatibility Contracts and Upgrade Plans

### 16.1 AIP Changes Worth Making

1. **Route hook / CLI seam** — AIP asks IMX for a route before spawn or dispatch.
2. **Task packet support** — AIP task files may embed or reference `task_packet.schema.json` records.
3. **Worktree helper** — mutation tasks receive staged worktrees by default.
4. **Profile enforcement seam** — AIP shim reads `~/.imx/catalog/profiles/*.yaml`.
5. **Task-handle semantics** — poll, cancel, tail, replay, and lease conventions.
6. **Operator overlays** — tmux/sidebar/agtop views over AIP + IMX files.
7. **Harness control seam** — generic intent files map to harness-specific commands.
8. **Contamination-aware handoffs** — increment `chain_depth` and validate handoff packets.
9. **Heartbeat and presence** — `HEARTBEAT.md`, presence files, cron/event wakeups.
10. **Session transcript normalization** — `workspace/transcripts/{session_id}.jsonl`.
11. **Event schema formalization** — `workspace/events.jsonl` should have a schema compatible with §13.1.

### 16.2 gitmem Changes Worth Making

1. **IMX route-card namespace** — durable routing lessons under a clear `routing/` namespace.
2. **Dream trigger ingestion** — read `~/.imx/state/dream-triggers.jsonl` during Orient/Gather.
3. **Task-class query dimension** — procedures retrievable by `task_class`, risk, tool, and profile.
4. **Distilled telemetry ingestion** — summarized outcomes only, preserving failure type and controllability.
5. **Shared redaction and policy bundle** — one fail-closed vocabulary across memory and routing.
6. **Skeptical review hooks** — L2 validation before high-impact route cards become canonical.
7. **Entrenchment detection** — periodic challenge of influential stale procedures.
8. **Contamination-aware consolidation** — `chain_depth` and source reliability influence promotion.
9. **Procedure revision PRs** — eval feedback and DSPy-style optimization become Dream-generated PRs.
10. **Graph index as cache** — append-only facts remain truth; graph/vector indexes are derived.

### 16.3 What Remains Outside Both Projects

- always-on hosted gateways as the control center
- hosted dashboards as source of truth
- provider-specific proxy stacks
- opaque central schedulers
- vector databases as mandatory routing memory
- runtime framework objects as canonical task state

---

## 17. Implementation Roadmap

### Phase 1 — Local Contracts

- define `~/.imx/` layout and write discipline
- publish task and handoff JSON Schemas
- compile node descriptors + profiles + probes into mesh snapshot
- add task-class taxonomy and profile consumption

### Phase 2 — Safe Dispatch

- route via AIP task queue and `wait_for`
- default mutation tasks to worktrees
- enforce capability profiles with AIP hooks
- emit route decisions and task telemetry
- require EXTERNAL approval and demo artifacts

### Phase 3 — Evidence-Driven Routing

- implement EMA score cache per `node × task_class × harness`
- add cost accounting and budget gates
- add failure taxonomy and recovery policy
- add harness drift detection and bounded exploration
- correlate AIP events into IMX telemetry

### Phase 4 — Memory-Coupled Steering

- integrate gitmem pre-tool guidance and attention refresh
- write Dream triggers for query gaps, route failures, and entrenchment
- promote durable route lessons to gitmem
- add procedure-revision PR loop from eval failures

### Phase 5 — Workflows and Operator Surfaces

- support file-backed workflow lifecycle and checkpoints
- add transcript normalization and context artifacts
- build tmux/TUI/statusline views
- add review/debate/consensus artifact patterns

### Phase 6 — Advanced Routing and Harness Control

- implement control-intent files
- evaluate controller×subordinate pairs
- run harness-as-variable evals
- support learned router artifacts when they beat baselines
- allow bounded self-modification of routing policies under operator invariants

---

## 18. Resource Synthesis

The detailed feature ledger has been extracted to `imx-resource-ledger.md`. The main conclusion is stable across all reviews: most useful ecosystem ideas are sound but misplaced. DAG engines, role frameworks, prompt platforms, observability stacks, memory APIs, policy services, and sandbox products become IMX-compatible when their durable state is expressed as Markdown, YAML, JSON, JSONL, git history, worktrees, schemas, and small scripts.

The promoted rework patterns are now part of the spec: task and handoff packets are JSON Schema files; workflows are `definition.yaml` plus `state.json`; conversational swarms become shared review files; DSPy-style optimization becomes gitmem Dream PRs; OPA/policy-as-code becomes profile YAML plus hook decisions; graph memory becomes append-only fact files plus derived indexes; hosted observability becomes local JSONL and optional views.

The rejection rule is also stable: IMX rejects architectures that make hosted services, SDK objects, framework runtimes, vector databases, dashboards, or visual editors the source of truth. It may keep them as adapters, runners, viewers, caches, or research inputs when they round-trip cleanly to files.

---

## 19. Research Bibliography

| ref | title / source | sections |
|---|---|---|
| Evans 2026 | Agentic AI and the Next Intelligence Explosion | §1 |
| Oracle 2026 | Comparing File Systems and Databases for Effective AI Agent Memory Management | §1, §5 |
| Agent Harness Survey 2026 | Agent Harness for LLM Agents: A Survey; Grok Code 6.7% → 68.3% harness datapoint | §1, §6.1 |
| Zhou 2026 | Externalization in LLM Agents | §1, §3 |
| Kim 2025/2026 | Towards a Science of Scaling Agent Systems | §1, §10 |
| Yu 2026 | AdaptOrch: Task-Adaptive Multi-Agent Orchestration | §7, §10 |
| Kulkarni 2026 | arXiv:2603.22651, financial document multi-agent topology benchmark | §10 |
| Liu 2026 | Phase Transition for Budgeted Multi-Agent Synergy | §7, §10 |
| Zhou & Chan 2026 | ORCH: deterministic multi-agent orchestrator with EMA-guided routing | §6.4 |
| Chen 2023 | FrugalGPT | §6.4, §7 |
| Ong 2024/2025 | RouteLLM | §6.4, §7 |
| Li 2026 | LLMRouterBench | §6.4, §12.4 |
| Nguyen 2026 | ByteRover: Agent-Native Memory | §4.2, §11 |
| Karpathy 2026 | LLM Knowledge Bases / LLM Wiki | §4.2, §11 |
| Weckbecker 2026 | Thought Virus | §11.6 |
| ECL 2026 | Epistemic Context Learning | §11.6, §12.3 |
| Xiang 2025 | GuardAgent: Safeguard LLM Agents via Knowledge-Enabled Reasoning | §12.1 |
| Zhong 2026 | YoloFS | §9, §10.1 |
| Wang 2026 | OpenClaw CIK Taxonomy | §12.6 |
| Pathak 2026 | GAAT: Governance-Aware Agent Telemetry | §13, §14.1 |
| Aiersilan 2026 | SWARM: Soft-Label Governance | §9.2 |
| Rosset 2026 | Universal Verifier / building verifiers for computer-use agents | §12.4 |
| MAESTRO 2026 | Multi-Agent Evaluation Suite for Testing, Reliability, and Observability | §12.4, §13 |
| Bui 2026 | Building AI Coding Agents for the Terminal | §10.6, §11.8 |
| Natural-Language Agent Harnesses 2026 | harnesses as portable cognitive artifacts | §6.1, §8.1 |
| Serverless Workflow | CNCF workflow DSL | §10.5 |
| GuardAgent / OPA pattern | policy to executable guardrail code / policy-as-code | §12.1 |
| GitHub AGENTS.md 2025 | scoped repository instructions | §8.1 |
| Anthropic 2025 | Building Effective Agents | §10 |
| Simon Willison 2025/2026 | context engineering, subagents, demo artifacts, prompt-injection design patterns | §11, §12.4 |
| Quine / POSIX Agent Standard 2026 | agents as native POSIX processes and JSONL CLI output | §1, §16 |
| DSPy | eval feedback to procedure optimization | §11.9 |
| Yao 2024 | τ-bench: repeated-trial reliability and pass^k metrics for tool-agent-user interaction | §12.4 |
| McMillan 2026 | Structured Context Engineering for File-Native Agentic Systems (arXiv:2602.05447) | §1, §11.8 |
