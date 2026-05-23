---
prompt_id: task-packet-dispatch
version: "0.6"
lifecycle: active
description: >
  Instructs a routing agent to emit a valid IMX task packet before dispatching work.
  Inject before any task that crosses a node boundary.
applicable_task_classes: [routing, routing.decomposition, planning]
applicable_risk_tiers: [READ_ONLY, LOCAL, EXTERNAL]
---

Before dispatching this task, emit a task packet to `workspace/tasks/pending/` as a JSON file validated against `catalog/schemas/task_packet.schema.json`.

Required fields:
- `schema_version`: "0.6"
- `task_id`: a unique identifier (use `task-{slug}-{timestamp}` format)
- `task_class`: the most specific applicable class from `catalog/task_classes.yaml`
- `risk_tier`: READ_ONLY, LOCAL, or EXTERNAL — use the highest applicable tier
- `provenance.written_by`: your agent identifier
- `provenance.written_at`: current ISO 8601 timestamp
- `provenance.chain_depth`: the current hop count from the original human request

If `risk_tier` is EXTERNAL:
- `approval_policy.required`: true
- An approval record must exist at `~/.imx/state/approvals/{task_id}.json` before dispatch proceeds
- A demo artifact must be planned at `artifacts/demo/{task_id}.md`

Write the packet atomically: write to a `.tmp` file, then rename into place.
