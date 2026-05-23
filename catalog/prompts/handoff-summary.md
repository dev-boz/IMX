---
prompt_id: handoff-summary
version: "0.6"
lifecycle: active
description: >
  Instructs an agent to produce a valid IMX handoff packet when transferring
  work to another agent or closing a task.
applicable_task_classes: [implementation, deployment, bash_execution]
applicable_risk_tiers: [READ_ONLY, LOCAL, EXTERNAL]
---

When handing off work to the next agent or closing this task, emit a handoff packet to `workspace/tasks/done/{task_id}-handoff.json` (or `failed/` if the task failed).

The packet must validate against `catalog/schemas/handoff_packet.schema.json`.

Required fields:
- `schema_version`: "0.6"
- `handoff_id`: unique identifier
- `source_agent`: your agent identifier
- `target_agent`: the receiving agent (or "human" if returning to operator)
- `provenance.chain_depth`: increment the incoming task's chain_depth by 1

Include:
- `summary`: 2-4 sentences describing what was accomplished
- `artifacts`: list of files created or modified, with paths
- `decisions`: key choices made during execution and their rationale
- `open_questions`: anything unresolved that the next agent must handle
- `next_actions`: concrete next steps with suggested task_class and risk_tier
- `budget_consumed`: tokens and estimated cost if known
- `outcome`: one of succeeded, partial, failed, blocked, escalated
- `failure`: if outcome is not succeeded, include failure_type and controllability

For EXTERNAL tasks, also include:
- `contamination_risk.sanitization_steps`: list of redaction/review steps taken

Write the packet atomically (tmp → rename).
