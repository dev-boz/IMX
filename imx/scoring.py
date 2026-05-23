"""Composite scoring and conflict resolution for route cards per IMX spec §6."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ema import EmaStore


@dataclass
class ScoringWeights:
    quality_weight: float = 0.50
    stability_weight: float = 0.30
    cost_weight: float = 0.10
    latency_weight: float = 0.10

    def __post_init__(self) -> None:
        total = self.quality_weight + self.stability_weight + self.cost_weight + self.latency_weight
        assert abs(total - 1.0) < 1e-9, (
            f"ScoringWeights must sum to 1.0, got {total}"
        )


@dataclass
class RouteCardScore:
    route_card_id: str
    node_id: str
    task_class: str
    raw_confidence: float       # from route card
    ema_composite: float        # from EMA store
    adjusted_score: float       # final blended score
    n_observations: int = 0
    reasons: list[str] = field(default_factory=list)


def compute_adjusted_score(
    raw_confidence: float,
    ema_composite: float,
    n: int,
    *,
    alpha: float = 0.3,
) -> float:
    """Blend declarative confidence with empirical EMA score.

    Cold-start (n < 5): trust raw_confidence more.
    Warm-start (n >= 5): trust EMA more.
    Result is clamped to [0.0, 1.0].
    """
    if n < 5:
        # cold-start: declarative confidence carries more weight
        score = alpha * ema_composite + (1 - alpha) * raw_confidence
    else:
        # warm-start: empirical EMA carries more weight
        score = (1 - alpha) * ema_composite + alpha * raw_confidence
    return max(0.0, min(1.0, score))


def score_route_cards(
    cards: list[dict],
    ema_store,
    task_class: str,
    harness_fingerprint: str = "",
) -> list[RouteCardScore]:
    """Score a list of route card dicts against the EMA store.

    Each card dict must contain: route_card_id, node_id, task_class, confidence.
    Optionally: capability_band.

    Returns a list of RouteCardScore sorted by adjusted_score descending.
    """
    from .ema import EmaStore  # noqa: F401 — import for side-effect / type availability

    results: list[RouteCardScore] = []

    for card in cards:
        route_card_id = card["route_card_id"]
        node_id = card["node_id"]
        raw_confidence = float(card["confidence"])

        ema_score = ema_store.get(node_id, task_class, harness_fingerprint)
        ema_composite = ema_score.composite()
        n = ema_score.n

        adjusted = compute_adjusted_score(raw_confidence, ema_composite, n)

        reasons: list[str] = []
        if n < 5:
            reasons.append(f"cold-start: using declarative confidence (n={n})")
        else:
            reasons.append(f"warm-start: EMA n={n}")

        results.append(
            RouteCardScore(
                route_card_id=route_card_id,
                node_id=node_id,
                task_class=task_class,
                raw_confidence=raw_confidence,
                ema_composite=ema_composite,
                adjusted_score=adjusted,
                n_observations=n,
                reasons=reasons,
            )
        )

    results.sort(key=lambda s: s.adjusted_score, reverse=True)
    return results


def resolve_conflict(scores: list[RouteCardScore]) -> RouteCardScore | None:
    """Select the winning RouteCardScore from a ranked list.

    - Empty list → None.
    - Clear winner: top score is >= 0.1 higher than second → return top.
    - Within 0.1: return the one with higher n_observations.
    - Still tied: return the one with higher raw_confidence.
    """
    if not scores:
        return None

    if len(scores) == 1:
        return scores[0]

    top, second = scores[0], scores[1]

    if top.adjusted_score - second.adjusted_score >= 0.1:
        return top

    # within 0.1 — prefer more observations
    if top.n_observations != second.n_observations:
        return top if top.n_observations > second.n_observations else second

    # still tied — prefer higher raw_confidence
    return top if top.raw_confidence >= second.raw_confidence else second


def source_type_precedence(source_type: str) -> int:
    """Return integer precedence for a source type (higher = more trusted)."""
    _PRECEDENCE: dict[str, int] = {
        "ground_truth_code": 10,
        "empirical": 8,
        "peer_reviewed": 6,
        "operator_declared": 4,
        "self_reported": 2,
        "inferred": 1,
    }
    return _PRECEDENCE.get(source_type, 0)
