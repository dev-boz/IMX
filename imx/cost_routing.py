"""Cost-aware routing integration per IMX spec §13.2."""
from __future__ import annotations

import json
from pathlib import Path

from .catalog import load_rates, load_node_descriptors


def estimate_task_cost(
    node_id: str,
    task_class: str,
    estimated_tokens: int,
    catalog_root: Path | None = None,
) -> float | None:
    """Estimate the cost in USD for running estimated_tokens on node_id.

    Looks up the node descriptor to find provider and model, then looks up
    rates from the catalog. Assumes a 50/50 input/output token split.
    Returns None if the rate cannot be determined.
    """
    # Find the node descriptor matching this node_id
    nodes = load_node_descriptors(catalog_root)
    descriptor = next((n for n in nodes if n.node_id == node_id), None)
    if descriptor is None:
        return None

    provider = descriptor.engine.get("provider")
    model = descriptor.engine.get("model")
    if not provider or not model:
        return None

    rates = load_rates(catalog_root)
    model_rates = rates.get(provider, {}).get(model)
    if not model_rates:
        return None

    input_rate = model_rates.get("input_per_million_usd")
    output_rate = model_rates.get("output_per_million_usd")
    if input_rate is None or output_rate is None:
        return None

    # 50/50 input/output split, rates are per million tokens
    return estimated_tokens * (input_rate + output_rate) / 2 / 1_000_000


def cost_score(estimated_cost_usd: float, budget_max_usd: float) -> float:
    """Return a score in [0,1] where higher = cheaper relative to budget.

    Returns 0.5 when no budget constraint (budget_max_usd <= 0).
    """
    if budget_max_usd <= 0:
        return 0.5
    return 1.0 - min(1.0, estimated_cost_usd / budget_max_usd)


def rank_nodes_by_cost_adjusted_score(
    node_ids: list[str],
    task_class: str,
    ema_store,
    *,
    catalog_root: Path | None = None,
    estimated_tokens: int = 10000,
    budget_max_usd: float = 0.0,
    cost_weight: float = 0.15,
) -> list[tuple[str, float]]:
    """Rank nodes by a blended EMA composite + cost score.

    Returns list of (node_id, blended_score) sorted descending.
    Nodes with unknown cost receive a neutral cost_score of 0.5.
    """
    results: list[tuple[str, float]] = []
    for node_id in node_ids:
        ema_composite = ema_store.get(node_id, task_class, "").composite()

        cost_usd = estimate_task_cost(node_id, task_class, estimated_tokens, catalog_root)
        if cost_usd is not None:
            cost_score_val = cost_score(cost_usd, budget_max_usd)
        else:
            cost_score_val = 0.5  # neutral when rate unknown

        blended = (1 - cost_weight) * ema_composite + cost_weight * cost_score_val
        results.append((node_id, blended))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def aggregate_cost_by_task_class(telemetry_dir: Path | None = None) -> dict:
    """Aggregate estimated costs by task class from telemetry.

    Reads ~/.imx/telemetry/tasks.jsonl (or telemetry_dir/tasks.jsonl).
    Returns {task_class: {"total_cost_usd": float, "task_count": int, "avg_cost_usd": float}}.
    """
    if telemetry_dir is not None:
        tasks_path = telemetry_dir / "tasks.jsonl"
    else:
        tasks_path = Path.home() / ".imx" / "telemetry" / "tasks.jsonl"

    if not tasks_path.exists():
        return {}

    aggregated: dict[str, dict] = {}

    try:
        lines = tasks_path.read_text().splitlines()
    except Exception:
        return {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue

        task_class = record.get("task_class")
        if not task_class:
            continue

        estimated_cost = record.get("estimated_cost_usd")

        entry = aggregated.setdefault(task_class, {"total_cost_usd": 0.0, "task_count": 0, "_cost_count": 0})
        entry["task_count"] += 1
        if estimated_cost is not None:
            entry["total_cost_usd"] += float(estimated_cost)
            entry["_cost_count"] += 1

    # Compute averages and clean up internal tracking key
    result: dict = {}
    for task_class, entry in aggregated.items():
        cost_count = entry["_cost_count"]
        total = entry["total_cost_usd"]
        avg = total / cost_count if cost_count > 0 else 0.0
        result[task_class] = {
            "total_cost_usd": total,
            "task_count": entry["task_count"],
            "avg_cost_usd": avg,
        }

    return result
