"""Quota status and cache-stats probes per IMX spec §13.3."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("imx.quota")

DEFAULT_QUOTA_DIR: Path = Path.home() / ".imx" / "state" / "quota-status"
DEFAULT_CACHE_STATS_PATH: Path = Path.home() / ".imx" / "state" / "cache-stats.json"


@dataclass
class QuotaStatus:
    """Quota status for a single provider."""

    provider: str
    schema_version: str = "0.6"
    checked_at: str = ""          # ISO8601
    requests_used: int = 0
    requests_limit: int = 0
    tokens_used: int = 0
    tokens_limit: int = 0
    reset_at: str = ""            # ISO8601 when quota resets
    status: str = "ok"           # "ok", "warning", "exhausted"
    pct_used: float = 0.0


@dataclass
class CacheStats:
    """Cache hit/miss statistics across providers."""

    schema_version: str = "0.6"
    updated_at: str = ""
    providers: dict = field(default_factory=dict)  # provider -> {hit_rate, hits, misses}
    total_saved_usd: float = 0.0


def _atomic_write(path: Path, text: str) -> None:
    """Write text to path atomically via a temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_quota_status(
    status: QuotaStatus, *, quota_dir: Path | None = None
) -> Path:
    """Write quota status to {quota_dir}/{provider}.json.

    Returns the path written.
    """
    directory = quota_dir or DEFAULT_QUOTA_DIR
    path = directory / f"{status.provider}.json"
    data = {
        "provider": status.provider,
        "schema_version": status.schema_version,
        "checked_at": status.checked_at,
        "requests_used": status.requests_used,
        "requests_limit": status.requests_limit,
        "tokens_used": status.tokens_used,
        "tokens_limit": status.tokens_limit,
        "reset_at": status.reset_at,
        "status": status.status,
        "pct_used": status.pct_used,
    }
    _atomic_write(path, json.dumps(data, indent=2))
    return path


def read_quota_status(
    provider: str, *, quota_dir: Path | None = None
) -> QuotaStatus | None:
    """Read quota status for a provider. Returns None if file is missing."""
    directory = quota_dir or DEFAULT_QUOTA_DIR
    path = directory / f"{provider}.json"

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read quota status from %s: %s", path, exc)
        return None

    return QuotaStatus(
        provider=data.get("provider", provider),
        schema_version=data.get("schema_version", "0.6"),
        checked_at=data.get("checked_at", ""),
        requests_used=data.get("requests_used", 0),
        requests_limit=data.get("requests_limit", 0),
        tokens_used=data.get("tokens_used", 0),
        tokens_limit=data.get("tokens_limit", 0),
        reset_at=data.get("reset_at", ""),
        status=data.get("status", "ok"),
        pct_used=data.get("pct_used", 0.0),
    )


def read_all_quota_statuses(
    *, quota_dir: Path | None = None
) -> list[QuotaStatus]:
    """Read all *.json files in quota_dir and return parsed QuotaStatus objects."""
    directory = quota_dir or DEFAULT_QUOTA_DIR

    if not directory.is_dir():
        return []

    results = []
    for json_file in directory.glob("*.json"):
        provider = json_file.stem
        status = read_quota_status(provider, quota_dir=directory)
        if status is not None:
            results.append(status)
    return results


def write_cache_stats(
    stats: CacheStats, *, path: Path | None = None
) -> Path:
    """Write cache stats atomically. Returns the path written."""
    target = path or DEFAULT_CACHE_STATS_PATH
    data = {
        "schema_version": stats.schema_version,
        "updated_at": stats.updated_at,
        "providers": stats.providers,
        "total_saved_usd": stats.total_saved_usd,
    }
    _atomic_write(target, json.dumps(data, indent=2))
    return target


def read_cache_stats(*, path: Path | None = None) -> CacheStats:
    """Read cache stats. Returns default CacheStats if file is missing."""
    target = path or DEFAULT_CACHE_STATS_PATH

    if not target.exists():
        return CacheStats()

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read cache stats from %s: %s", target, exc)
        return CacheStats()

    return CacheStats(
        schema_version=data.get("schema_version", "0.6"),
        updated_at=data.get("updated_at", ""),
        providers=data.get("providers", {}),
        total_saved_usd=data.get("total_saved_usd", 0.0),
    )


def record_cache_event(
    provider: str,
    hit: bool,
    saved_usd: float = 0.0,
    *,
    path: Path | None = None,
) -> CacheStats:
    """Record a cache hit or miss for a provider, update stats, and persist.

    Returns updated CacheStats.
    """
    stats = read_cache_stats(path=path)

    entry = stats.providers.get(provider, {"hits": 0, "misses": 0, "hit_rate": 0.0})
    hits = entry.get("hits", 0)
    misses = entry.get("misses", 0)

    if hit:
        hits += 1
    else:
        misses += 1

    total = hits + misses
    hit_rate = hits / total if total > 0 else 0.0

    stats.providers[provider] = {
        "hits": hits,
        "misses": misses,
        "hit_rate": hit_rate,
    }
    stats.total_saved_usd += saved_usd

    write_cache_stats(stats, path=path)
    return stats


def is_provider_quota_ok(
    provider: str,
    *,
    warn_pct: float = 0.8,
    quota_dir: Path | None = None,
) -> tuple[bool, str]:
    """Check whether a provider's quota is within acceptable limits.

    Returns (ok, message).
    """
    status = read_quota_status(provider, quota_dir=quota_dir)

    if status is None:
        return (True, "no quota data")

    if status.pct_used >= 1.0:
        return (False, f"provider {provider} quota exhausted")

    if status.pct_used >= warn_pct:
        return (True, f"provider {provider} quota warning: {status.pct_used:.0%} used")

    return (True, "ok")
