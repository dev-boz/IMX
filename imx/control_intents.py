"""Control intent files for harness-controlling-harness topology per spec §10.6."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DEFAULT_INTENTS_BASE = Path.home() / ".imx" / "state" / "control-intents"
DEFAULT_TELEMETRY_DIR = Path.home() / ".imx" / "telemetry"

INTENT_KINDS: frozenset[str] = frozenset({
    "compact",
    "rewind",
    "switch_model",
    "clear",
    "pause",
    "resume",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ControlIntent:
    schema_version: str = "0.6"
    intent: str = ""            # one of the 6 kinds in INTENT_KINDS
    task_id: str = ""
    session_id: str = ""
    target_model_band: str = ""  # for switch_model
    reason: str = ""
    requested_by: str = ""      # node_id of controller
    ts: str = ""                # ISO8601


def write_control_intent(
    intent: ControlIntent,
    *,
    intents_dir: Path | None = None,
) -> Path:
    """Write a control intent file atomically. Returns path written."""
    if intents_dir is None:
        intents_dir = DEFAULT_INTENTS_BASE / intent.session_id
    intents_dir.mkdir(parents=True, exist_ok=True)

    task_part = intent.task_id or uuid4().hex[:8]
    filename = f"{intent.intent}-{task_part}.intent.json"
    out_path = intents_dir / filename

    # Stamp ts if not set
    data = dataclasses.asdict(intent)
    if not data.get("ts"):
        data["ts"] = _utc_now()

    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out_path)
    return out_path


def read_pending_intents(
    session_id: str,
    *,
    intents_dir: Path | None = None,
) -> list[ControlIntent]:
    """Read all *.intent.json files and return as list of ControlIntent sorted by ts."""
    if intents_dir is None:
        intents_dir = DEFAULT_INTENTS_BASE / session_id
    if not intents_dir.exists():
        return []

    valid_fields = {f.name for f in dataclasses.fields(ControlIntent)}
    intents: list[ControlIntent] = []
    for path in sorted(intents_dir.glob("*.intent.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            intents.append(ControlIntent(**{k: v for k, v in data.items() if k in valid_fields}))
        except Exception:
            continue

    intents.sort(key=lambda i: i.ts or "")
    return intents


def mark_intent_acked(intent_path: Path) -> None:
    """Rename foo.intent.json → foo.intent.acked.json."""
    # Replace the trailing .json with .acked.json
    new_name = intent_path.name.replace(".intent.json", ".intent.acked.json")
    acked_path = intent_path.parent / new_name
    os.replace(intent_path, acked_path)


def append_control_span(span: dict, *, telemetry_dir: Path | None = None) -> None:
    """Append a control span record to control_spans.jsonl (fsync)."""
    d = telemetry_dir or DEFAULT_TELEMETRY_DIR
    d.mkdir(parents=True, exist_ok=True)

    span = dict(span)
    span.setdefault("schema_version", "0.6")
    span.setdefault("ts", _utc_now())

    path = d / "control_spans.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(span, ensure_ascii=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def translate_intent_to_harness_command(intent: ControlIntent, harness: str) -> str | None:
    """Map an intent kind + harness to a harness-specific command string."""
    kind = intent.intent

    if kind == "compact":
        if harness == "claude-code":
            return "/compact"
        if harness == "gemini-cli":
            return "/compress"
        return None

    if kind == "rewind":
        if harness == "claude-code":
            return "/rewind"
        return None

    if kind == "switch_model":
        if harness == "claude-code":
            return f"/model {intent.target_model_band}"
        return None

    if kind == "clear":
        return "/clear"

    if kind in ("pause", "resume"):
        # Requires send-keys or no-op; no harness command string
        return None

    return None
