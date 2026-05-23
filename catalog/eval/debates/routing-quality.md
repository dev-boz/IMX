---
schema_version: "0.6"
debate_id: routing-quality
topic: "Route card quality and entrenchment risk"
participants: [advocate, skeptic, arbitrator]
task_class: routing
---

# Debate: Route Card Quality Evaluation

## Purpose

Adversarial review of high-confidence route cards before they become canonical.
Prevents echo-chamber entrenchment where a single data source inflates confidence.

## Advocate Position

Present the strongest case FOR promoting this route card:
- Evidence from multiple independent sources
- Empirical telemetry backing the confidence score
- Task class specificity and scope clarity
- Past performance consistency

## Skeptic Position

Challenge the route card systematically:
- Is the evidence truly independent, or from the same agent lineage?
- Could the high confidence reflect confirmation bias rather than ground truth?
- What failure modes does this card NOT anticipate?
- Is the guidance too broad to be safely applied?

## Arbitrator Decision

Weigh both positions and decide:
- PROMOTE: Evidence is sufficient, issues addressed
- REVISE: Return for correction with specific requirements  
- HOLD: Insufficient evidence; require N more observations
- REJECT: Evidence is fundamentally flawed or misleading

## Entrenchment Risk Checklist

Before promoting, verify:
- [ ] Evidence from >= 2 independent sources
- [ ] Empirical backing (not just declarative confidence)
- [ ] Reviewed by a node different from the one that created it
- [ ] Confidence calibrated against actual success rate
- [ ] Guidance scoped appropriately (not too broad)
