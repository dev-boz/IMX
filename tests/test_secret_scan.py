"""Tests for imx/secret_scan.py — fail-closed boundary-artifact scanning (§11.5)."""
import pytest

from imx.secret_scan import (
    Finding,
    SecretFoundError,
    assert_clean,
    scan_object,
    scan_text,
)


def test_scan_text_detects_github_token():
    labels = scan_text("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 here")
    assert "github_token" in labels


def test_scan_text_detects_secret_assignment():
    assert "secret_assignment" in scan_text("PASSWORD=hunter2secret")


def test_scan_text_clean():
    assert scan_text("a perfectly ordinary task description") == []


def test_scan_object_recurses_and_reports_path():
    obj = {
        "task_id": "t-1",
        "instructions": "use ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "nested": {"items": ["fine", "AKIA1234567890ABCDEF"]},
    }
    findings = scan_object(obj, path="task_packet")
    locations = {f.location for f in findings}
    labels = {f.label for f in findings}
    assert "github_token" in labels
    assert "aws_access_key" in labels
    assert "task_packet.instructions" in locations
    assert "task_packet.nested.items[1]" in locations


def test_assert_clean_passes_on_benign():
    assert_clean({"task_id": "t-1", "task_class": "analysis"})  # no raise


def test_assert_clean_raises_on_secret():
    with pytest.raises(SecretFoundError) as exc:
        assert_clean({"creds": "Bearer abcdefghijklmnop"}, label="task_packet")
    assert exc.value.findings
    assert "task_packet.creds" in str(exc.value)
