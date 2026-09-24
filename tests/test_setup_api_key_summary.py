"""Tests for API key masking in the setup wizard summary."""

from cli.commands.setup import _format_api_key_summary


def test_format_api_key_summary_when_set_shows_last_four_only():
    assert _format_api_key_summary("super-secret-key-abcd") == "API key: set (….abcd)"
    assert "super-secret" not in _format_api_key_summary("super-secret-key-abcd")


def test_format_api_key_summary_when_empty_says_not_set():
    assert _format_api_key_summary("") == "API key: not set"
    assert _format_api_key_summary(None) == "API key: not set"
