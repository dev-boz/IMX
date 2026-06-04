"""Tests for the quota write CLI path (set + record-cache), spec §13.3.

These commands are the write half of the quota/cache loop the router reads via
``is_provider_quota_ok`` / ``read_cache_stats``.
"""
import argparse
import json

from imx.cli import cmd_quota_record_cache, cmd_quota_set
from imx.quota import is_provider_quota_ok, read_cache_stats, read_quota_status


def _set_args(provider, quota_dir, **overrides):
    base = dict(
        provider=provider,
        status="ok",
        pct_used=0.0,
        requests_used=0,
        requests_limit=0,
        tokens_used=0,
        tokens_limit=0,
        reset_at=None,
        checked_at=None,
        quota_dir=str(quota_dir),
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_quota_set_writes_status_readable_by_router(tmp_path, capsys):
    exit_code = cmd_quota_set(
        _set_args("anthropic", tmp_path, status="exhausted", pct_used=100.0)
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["quota"]["status"] == "exhausted"

    status = read_quota_status("anthropic", quota_dir=tmp_path)
    assert status is not None
    assert status.status == "exhausted"

    # The router consults is_provider_quota_ok — an exhausted status must gate it out.
    ok, _reason = is_provider_quota_ok("anthropic", quota_dir=tmp_path)
    assert ok is False


def test_quota_set_ok_status_passes_router_gate(tmp_path):
    cmd_quota_set(_set_args("openai", tmp_path, status="ok"))

    ok, _reason = is_provider_quota_ok("openai", quota_dir=tmp_path)
    assert ok is True


def test_quota_record_cache_hit_then_miss(tmp_path, capsys):
    stats_path = tmp_path / "cache-stats.json"

    cmd_quota_record_cache(argparse.Namespace(
        provider="anthropic", miss=False, saved_usd=0.01,
        cache_stats_path=str(stats_path),
    ))
    capsys.readouterr()
    cmd_quota_record_cache(argparse.Namespace(
        provider="anthropic", miss=True, saved_usd=0.0,
        cache_stats_path=str(stats_path),
    ))
    payload = json.loads(capsys.readouterr().out)

    assert payload["providers"]["anthropic"]["hits"] == 1
    assert payload["providers"]["anthropic"]["misses"] == 1
    assert payload["providers"]["anthropic"]["hit_rate"] == 0.5

    persisted = read_cache_stats(path=stats_path)
    assert persisted.providers["anthropic"]["hits"] == 1
    assert persisted.total_saved_usd == 0.01
