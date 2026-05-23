"""Budget gate management per spec §7 and §13.2."""
import dataclasses
import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BUDGETS_DIR = Path.home() / ".imx" / "state" / "budgets"


@dataclass
class BudgetLedger:
    task_id: str
    max_cost_usd: float | None = None
    max_tokens: int | None = None
    gate_mode: str = "soft"  # soft | hard
    spent_usd: float = 0.0
    spent_tokens: int = 0
    status: str = "ok"  # ok | warning | exhausted

    def check(self) -> tuple[bool, str]:
        """Returns (allowed, reason). Hard gate blocks when exhausted."""
        if self.max_cost_usd and self.spent_usd >= self.max_cost_usd:
            if self.gate_mode == "hard":
                return False, f"budget exhausted: ${self.spent_usd:.4f} >= ${self.max_cost_usd:.4f}"
            return True, f"budget warning: ${self.spent_usd:.4f} >= ${self.max_cost_usd:.4f}"
        if self.max_tokens and self.spent_tokens >= self.max_tokens:
            if self.gate_mode == "hard":
                return False, f"token budget exhausted: {self.spent_tokens} >= {self.max_tokens}"
            return True, f"token budget warning: {self.spent_tokens} >= {self.max_tokens}"
        return True, "ok"

    def record_spend(self, *, cost_usd: float = 0.0, tokens: int = 0) -> None:
        self.spent_usd += cost_usd
        self.spent_tokens += tokens
        allowed, reason = self.check()
        self.status = "ok" if allowed and reason == "ok" else ("warning" if allowed else "exhausted")


def load_budget(task_id: str, budgets_dir: Path | None = None) -> BudgetLedger:
    d = budgets_dir or DEFAULT_BUDGETS_DIR
    path = d / f"{task_id}.json"
    if not path.exists():
        return BudgetLedger(task_id=task_id)
    data = json.loads(path.read_text())
    return BudgetLedger(**{k: v for k, v in data.items() if k in BudgetLedger.__dataclass_fields__})


def save_budget(ledger: BudgetLedger, budgets_dir: Path | None = None) -> None:
    d = budgets_dir or DEFAULT_BUDGETS_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{ledger.task_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dataclasses.asdict(ledger), indent=2) + "\n")
    os.replace(tmp, path)
