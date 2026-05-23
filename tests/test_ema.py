"""Tests for imx.ema — NodeTaskScore and EmaStore."""
import pytest
from imx.ema import NodeTaskScore, EmaStore, DEFAULT_ALPHA


# --- NodeTaskScore.update() ---

def test_update_applies_ema_formula_to_quality():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    initial_quality = score.quality  # 0.5
    obs = 1.0
    score.update(quality=obs)
    expected = DEFAULT_ALPHA * obs + (1 - DEFAULT_ALPHA) * initial_quality
    assert score.quality == pytest.approx(expected)


def test_update_applies_ema_formula_to_latency():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    initial = score.latency
    obs = 0.2
    score.update(latency=obs)
    expected = DEFAULT_ALPHA * obs + (1 - DEFAULT_ALPHA) * initial
    assert score.latency == pytest.approx(expected)


def test_update_applies_ema_formula_to_cost():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    initial = score.cost
    obs = 0.1
    score.update(cost=obs)
    expected = DEFAULT_ALPHA * obs + (1 - DEFAULT_ALPHA) * initial
    assert score.cost == pytest.approx(expected)


def test_update_applies_ema_formula_to_stability():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    initial = score.stability
    obs = 0.8
    score.update(stability=obs)
    expected = DEFAULT_ALPHA * obs + (1 - DEFAULT_ALPHA) * initial
    assert score.stability == pytest.approx(expected)


def test_update_increments_n():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    assert score.n == 0
    score.update(quality=1.0)
    assert score.n == 1
    score.update(quality=0.5)
    assert score.n == 2


def test_update_sets_last_observed():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    assert score.last_observed == ""
    score.update(quality=1.0)
    assert score.last_observed.endswith("Z")


def test_update_only_updates_specified_dimensions():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    score.update(quality=1.0)
    assert score.latency == 0.5
    assert score.cost == 0.5
    assert score.stability == 0.5


# --- NodeTaskScore.composite() ---

def test_composite_returns_float_in_0_1():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    c = score.composite()
    assert 0.0 <= c <= 1.0


def test_composite_cold_start_is_0_5():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    # quality=0.5, stability=0.5, cost=0.5, latency=0.5
    # composite = 0.5*0.5 + 0.5*0.3 + (1-0.5)*0.1 + (1-0.5)*0.1 = 0.25+0.15+0.05+0.05 = 0.5
    assert score.composite() == pytest.approx(0.5)


def test_composite_higher_after_quality_improvement():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1")
    baseline = score.composite()
    score.update(quality=1.0, stability=1.0)
    assert score.composite() > baseline


def test_composite_uses_weights():
    score = NodeTaskScore(
        node_id="n1", task_class="analysis", harness_fingerprint="fp1",
        quality=0.8, stability=0.6, cost=0.2, latency=0.3,
    )
    expected = 0.8 * 0.5 + 0.6 * 0.3 + (1 - 0.2) * 0.1 + (1 - 0.3) * 0.1
    assert score.composite() == pytest.approx(expected)


# --- NodeTaskScore.apply_drift_reset() ---

def test_apply_drift_reset_moves_quality_toward_0_5():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1",
                          quality=1.0, n=4)
    score.apply_drift_reset(reset_factor=0.5)
    # 0.5*0.5 + 1.0*0.5 = 0.75
    assert score.quality == pytest.approx(0.75)


def test_apply_drift_reset_moves_stability_toward_0_5():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1",
                          stability=1.0, n=4)
    score.apply_drift_reset(reset_factor=0.5)
    assert score.stability == pytest.approx(0.75)


def test_apply_drift_reset_reduces_n():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1", n=4)
    score.apply_drift_reset(reset_factor=0.5)
    # int(4 * 0.5) = 2
    assert score.n == 2


def test_apply_drift_reset_n_minimum_is_1():
    score = NodeTaskScore(node_id="n1", task_class="analysis", harness_fingerprint="fp1", n=1)
    score.apply_drift_reset(reset_factor=0.9)
    assert score.n >= 1


# --- EmaStore.get() ---

def test_ema_store_get_returns_cold_start_for_unknown_key(tmp_path):
    store = EmaStore(path=tmp_path / "scores.json")
    score = store.get("node-a", "analysis", "fp0")
    assert score.quality == 0.5
    assert score.latency == 0.5
    assert score.cost == 0.5
    assert score.stability == 0.5
    assert score.n == 0


def test_ema_store_get_returns_same_object_on_repeated_call(tmp_path):
    store = EmaStore(path=tmp_path / "scores.json")
    s1 = store.get("node-a", "analysis", "fp0")
    s2 = store.get("node-a", "analysis", "fp0")
    assert s1 is s2


# --- EmaStore.update() persists correctly ---

def test_ema_store_update_persists_and_reloads(tmp_path):
    path = tmp_path / "scores.json"
    store = EmaStore(path=path)
    store.update("node-a", "analysis", "fp0", quality=1.0)

    # Reload from disk
    store2 = EmaStore(path=path)
    reloaded = store2.get("node-a", "analysis", "fp0")
    # Should not be cold-start 0.5 quality
    assert reloaded.quality != pytest.approx(0.5)
    assert reloaded.n == 1


def test_ema_store_update_saves_file(tmp_path):
    path = tmp_path / "scores.json"
    store = EmaStore(path=path)
    store.update("node-a", "analysis", "fp0", quality=1.0)
    assert path.exists()


# --- EmaStore.rank_nodes() ---

def test_rank_nodes_returns_all_nodes(tmp_path):
    store = EmaStore(path=tmp_path / "scores.json")
    nodes = ["node-a", "node-b", "node-c"]
    ranked = store.rank_nodes(nodes, "analysis", "fp0")
    assert len(ranked) == 3
    assert {n for n, _ in ranked} == set(nodes)


def test_rank_nodes_descending_by_composite(tmp_path):
    path = tmp_path / "scores.json"
    store = EmaStore(path=path)
    # Give node-b a high quality score to distinguish
    store.update("node-b", "analysis", "fp0", quality=1.0, stability=1.0)
    store.update("node-b", "analysis", "fp0", quality=1.0, stability=1.0)
    ranked = store.rank_nodes(["node-a", "node-b"], "analysis", "fp0")
    # node-b should be first
    assert ranked[0][0] == "node-b"
    assert ranked[0][1] >= ranked[1][1]


def test_rank_nodes_scores_are_floats(tmp_path):
    store = EmaStore(path=tmp_path / "scores.json")
    ranked = store.rank_nodes(["node-a"], "analysis", "fp0")
    assert isinstance(ranked[0][1], float)
