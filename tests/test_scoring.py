"""Tests for imx/scoring.py."""
import pytest

from imx.scoring import (
    ScoringWeights,
    RouteCardScore,
    compute_adjusted_score,
    resolve_conflict,
)


def test_scoring_weights_sum_to_one():
    weights = ScoringWeights()
    total = (
        weights.quality_weight
        + weights.stability_weight
        + weights.cost_weight
        + weights.latency_weight
    )
    assert abs(total - 1.0) < 1e-9


def test_compute_adjusted_score_cold_start_trusts_confidence():
    # n=0 → cold start: score = 0.3*ema + 0.7*confidence = 0.3*0.5 + 0.7*0.9 = 0.78
    result = compute_adjusted_score(raw_confidence=0.9, ema_composite=0.5, n=0)
    assert result == pytest.approx(0.78)
    # Biased toward raw_confidence (0.9), not ema (0.5)
    assert result > 0.7


def test_compute_adjusted_score_warm_trusts_ema():
    # n=20 → warm: score = 0.7*ema + 0.3*confidence = 0.7*0.9 + 0.3*0.3 = 0.72
    result = compute_adjusted_score(raw_confidence=0.3, ema_composite=0.9, n=20)
    assert result == pytest.approx(0.72)
    # Biased toward ema (0.9), not confidence (0.3)
    assert result > 0.5


def test_compute_adjusted_score_clamps_to_zero_one():
    # Extreme inputs should not exceed [0, 1]
    result_high = compute_adjusted_score(raw_confidence=2.0, ema_composite=2.0, n=0)
    assert result_high <= 1.0

    result_low = compute_adjusted_score(raw_confidence=-1.0, ema_composite=-1.0, n=20)
    assert result_low >= 0.0


def _make_score(route_card_id, adjusted_score, n_observations=0, raw_confidence=0.5):
    return RouteCardScore(
        route_card_id=route_card_id,
        node_id=f"node-{route_card_id}",
        task_class="code_review",
        raw_confidence=raw_confidence,
        ema_composite=0.5,
        adjusted_score=adjusted_score,
        n_observations=n_observations,
    )


def test_resolve_conflict_returns_clear_winner():
    # Top score > second by >= 0.1
    scores = [
        _make_score("a", adjusted_score=0.9),
        _make_score("b", adjusted_score=0.7),
    ]
    winner = resolve_conflict(scores)
    assert winner is not None
    assert winner.route_card_id == "a"


def test_resolve_conflict_tiebreak_by_observations():
    # Within 0.1 gap — the one with more observations wins.
    # Put higher-scored card first (fewer observations) to exercise the tiebreak.
    scores = [
        _make_score("a", adjusted_score=0.82, n_observations=5),
        _make_score("b", adjusted_score=0.80, n_observations=20),
    ]
    winner = resolve_conflict(scores)
    assert winner is not None
    assert winner.route_card_id == "b"


def test_resolve_conflict_empty_returns_none():
    result = resolve_conflict([])
    assert result is None
