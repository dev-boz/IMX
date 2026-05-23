---
prompt_id: attention-refresh
version: "0.6"
lifecycle: active
description: >
  Injects an attention refresh prompt for long sessions, multi-agent handoffs,
  or resumed worktrees. Counteracts drift and lost-in-the-middle failures.
applicable_task_classes: [implementation, deployment, bash_execution, architecture_decision]
applicable_risk_tiers: [LOCAL, EXTERNAL]
---

You are resuming or continuing a task after a context boundary (handoff, compaction, or long session). Before proceeding:

1. **Re-read the task packet** at `workspace/tasks/claimed/{task_id}.json`. Confirm your current task_class, risk_tier, and capability_profile match what was dispatched.

2. **Check the workflow state** at `workflow/state.json` (if present). Note the current step, attempt count, and any blocked reason.

3. **Review key artifacts**: scan `workspace/tasks/{task_id}/` for plan.yaml, pre-mortem.md, and any gate response files.

4. **Check your budget**: verify remaining budget in `~/.imx/state/budgets/{task_id}.json`. If budget is near exhausted, emit a progress event and escalate before continuing.

5. **Re-anchor on constraints**: re-read the nearest `AGENTS.md` or `CLAUDE.md` and the role card for your assigned role.

Only proceed with execution after completing these checks. If any check reveals a contradiction or blocker, emit a status event with `status: blocked` and describe the issue.
