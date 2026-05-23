"""Tests for imx/quota.py."""
import pytest

from imx.quota import (
    QuotaStatus,
    CacheStats,
    write_quota_status,
    read_quota_status,
    record_cache_event,
    is_provider_quota_ok,
)


def test_write_and_read_quota_status(tmp_path):
    quota_dir = tmp_path / "quota"
    status = QuotaStatus(
        provider="anthropic",
        checked_at="2024-01-01T00:00:00Z",
        requests_used=500,
        requests_limit=1000,
        tokens_used=50000,
        tokens_limit=100000,
        status="ok",
        pct_used=0.5,
    )
    write_quota_status(status, quota_dir=quota_dir)
    loaded = read_quota_status("anthropic", quota_dir=quota_dir)

    assert loaded is not None
    assert loaded.provider == "anthropic"
    assert loaded.requests_used == 500
    assert loaded.requests_limit == 1000
    assert loaded.tokens_used == 50000
    assert loaded.pct_used == pytest.approx(0.5)
    assert loaded.status == "ok"


def test_read_missing_quota_returns_none(tmp_path):
    quota_dir = tmp_path / "quota"
    quota_dir.mkdir()
    result = read_quota_status("nonexistent-provider", quota_dir=quota_dir)
    assert result is None


def test_is_provider_quota_ok_no_data(tmp_path):
    quota_dir = tmp_path / "quota"
    quota_dir.mkdir()
    ok, message = is_provider_quota_ok("openai", quota_dir=quota_dir)
    assert ok is True
    assert "no quota data" in message


def test_is_provider_quota_ok_exhausted(tmp_path):
    quota_dir = tmp_path / "quota"
    status = QuotaStatus(
        provider="openai",
        pct_used=1.0,
        status="exhausted",
    )
    write_quota_status(status, quota_dir=quota_dir)

    ok, message = is_provider_quota_ok("openai", quota_dir=quota_dir)
    assert ok is False
    assert "exhausted" in message.lower() or "openai" in message


def test_record_cache_event_increments_hits(tmp_path):
    stats_path = tmp_path / "cache-stats.json"
    record_cache_event("anthropic", hit=True, path=stats_path)
    result = record_cache_event("anthropic", hit=True, path=stats_path)

    provider_stats = result.providers["anthropic"]
    assert provider_stats["hits"] == 2
    assert provider_stats["misses"] == 0
    assert provider_stats["hit_rate"] == pytest.approx(1.0)


def test_record_cache_event_mixed(tmp_path):
    stats_path = tmp_path / "cache-stats.json"
    record_cache_event("anthropic", hit=True, path=stats_path)
    record_cache_event("anthropic", hit=True, path=stats_path)
    record_cache_event("anthropic", hit=True, path=stats_path)
    result = record_cache_event("anthropic", hit=False, path=stats_path)

    provider_stats = result.providers["anthropic"]
    assert provider_stats["hits"] == 3
    assert provider_stats["misses"] == 1
    assert provider_stats["hit_rate"] == pytest.approx(0.75)
