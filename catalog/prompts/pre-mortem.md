---
prompt_id: pre-mortem
version: "0.6"
lifecycle: active
description: >
  Instructs a reviewer or architect agent to conduct a pre-mortem before a
  LOCAL or EXTERNAL plan is approved.
applicable_task_classes: [planning.pre_mortem, architecture_decision, evaluation.debate]
applicable_risk_tiers: [LOCAL, EXTERNAL]
---

Before approving this plan, conduct a pre-mortem using the IMX failure taxonomy.

Write your findings to `workspace/tasks/{task_id}/pre-mortem.md`. Structure:

## Top Failure Modes

For each failure mode, record:
- **Type**: one of `context_exceeded`, `capability_gap`, `quality_failure`, `refusal`, `timeout`, `infrastructure`, `cascade`
- **Controllability**: `controllable`, `uncontrollable`, `cascade`, or `unknown`
- **Description**: what specifically could go wrong
- **Mitigation**: what the executor can do to reduce the risk

## Open Questions

List any information gaps that must be resolved before execution begins.

## Verdict

One of:
- `approved` — proceed with the plan as stated
- `approved_with_risk` — proceed, with noted residual risks
- `revise` — return to executor with specific requested changes
- `escalate` — requires human or higher-capability advisor review

Write your verdict to `workspace/gates/gate-{task_id}-plan.response.json`:
```json
{
  "schema_version": "0.6",
  "task_id": "{task_id}",
  "stage": "plan",
  "verdict": "{verdict}",
  "top_risks": [...],
  "reviewer": "{your_agent_id}",
  "reviewed_at": "{iso8601}"
}
```
