# IMX Evaluation Catalog

Templates for structured evaluations per IMX spec §12.4.

## Types

- `specs/chaos-*.yaml` — Chaos injection specs for stress-testing routing
- `specs/calibration-*.yaml` — Confidence calibration checks
- `specs/harness-survey-*.yaml` — Harness-as-variable comparisons
- `debates/*.md` — Adversarial review debate templates

## Usage

Reference these templates when designing evaluations for route cards, nodes, or procedures.
Eval results should be recorded to `~/.imx/telemetry/` and can trigger gitmem Dream pipeline
via `procedure_regression` or `policy_drift` dream triggers.
