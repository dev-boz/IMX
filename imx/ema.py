"""EMA scoring per node_id × task_class × harness_fingerprint.

Formula: ema_next = alpha * observation + (1 - alpha) * ema_previous
Per spec §6.4: maintain separate EMA series for quality, latency, cost, stability.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_ALPHA = 0.2
DEFAULT_SCORES_PATH = Path.home() / ".imx" / "state" / "scores.json"


@dataclass
class NodeTaskScore:
    node_id: str
    task_class: str
    harness_fingerprint: str
    quality: float = 0.5       # EMA quality score [0,1]
    latency: float = 0.5       # EMA latency score (lower=faster, normalized)
    cost: float = 0.5          # EMA cost score (lower=cheaper, normalized)
    stability: float = 0.5     # EMA stability score [0,1]
    n: int = 0                 # observation count
    last_observed: str = ""    # ISO8601
    alpha: float = DEFAULT_ALPHA

    def key(self) -> str:
        return f"{self.node_id}||{self.task_class}||{self.harness_fingerprint}"

    def update(self, *, quality: float | None = None, latency: float | None = None,
               cost: float | None = None, stability: float | None = None) -> None:
        """Apply EMA update for one or more dimensions."""
        if quality is not None:
            self.quality = self.alpha * quality + (1 - self.alpha) * self.quality
        if latency is not None:
            self.latency = self.alpha * latency + (1 - self.alpha) * self.latency
        if cost is not None:
            self.cost = self.alpha * cost + (1 - self.alpha) * self.cost
        if stability is not None:
            self.stability = self.alpha * stability + (1 - self.alpha) * self.stability
        self.n += 1
        import datetime
        self.last_observed = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def composite(self, *, quality_weight=0.5, stability_weight=0.3, cost_weight=0.1, latency_weight=0.1) -> float:
        """Weighted composite score for ranking."""
        return (self.quality * quality_weight + self.stability * stability_weight +
                (1 - self.cost) * cost_weight + (1 - self.latency) * latency_weight)

    def apply_drift_reset(self, reset_factor: float = 0.5) -> None:
        """Partially reset confidence after harness drift. Per spec §6.1."""
        self.quality = 0.5 * reset_factor + self.quality * (1 - reset_factor)
        self.stability = 0.5 * reset_factor + self.stability * (1 - reset_factor)
        self.n = max(1, int(self.n * (1 - reset_factor)))


class EmaStore:
    """In-memory EMA store with optional JSON persistence."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_SCORES_PATH
        self._scores: dict[str, NodeTaskScore] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for key, record in data.items():
                score = NodeTaskScore(**record)
                self._scores[key] = score
        except Exception:
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: asdict(v) for k, v in self._scores.items()}, indent=2))
        os.replace(tmp, self.path)

    def get(self, node_id: str, task_class: str, harness_fingerprint: str) -> NodeTaskScore:
        key = f"{node_id}||{task_class}||{harness_fingerprint}"
        if key not in self._scores:
            self._scores[key] = NodeTaskScore(node_id=node_id, task_class=task_class, harness_fingerprint=harness_fingerprint)
        return self._scores[key]

    def update(self, node_id: str, task_class: str, harness_fingerprint: str, **kwargs) -> NodeTaskScore:
        score = self.get(node_id, task_class, harness_fingerprint)
        score.update(**kwargs)
        self.save()
        return score

    def rank_nodes(self, node_ids: list[str], task_class: str, harness_fingerprint: str = "") -> list[tuple[str, float]]:
        """Return node_ids sorted by composite score descending."""
        ranked = []
        for node_id in node_ids:
            score = self.get(node_id, task_class, harness_fingerprint)
            ranked.append((node_id, score.composite()))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def apply_drift_reset(self, node_id: str, harness_fingerprint: str, reset_factor: float = 0.5) -> int:
        """Reset confidence for all task classes on a node after harness drift."""
        count = 0
        for key, score in self._scores.items():
            if score.node_id == node_id and score.harness_fingerprint == harness_fingerprint:
                score.apply_drift_reset(reset_factor)
                count += 1
        if count:
            self.save()
        return count
