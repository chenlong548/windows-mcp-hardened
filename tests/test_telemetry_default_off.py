"""Telemetry must be opt-in in the hardened fork.

Upstream initialized PostHogAnalytics unless ANONYMIZED_TELEMETRY=false and
bundled its own API key, so a default install reported tool usage to the
upstream project's PostHog instance. The hardened fork flips the default
(off unless explicitly enabled) and ships no API key. These tests pin both
halves of that contract.
"""

import pytest

import windows_mcp.__main__ as cli
from windows_mcp.infrastructure import PostHogAnalytics

_ENABLING = ["true", "TRUE", "True", "1", "on", "ON", "yes", "enabled", " true ", "\tyes\n"]
_DISABLING = [None, "false", "FALSE", "0", "off", "no", "disabled", "", "junk", "enabled=true"]


class TestTelemetryDefaultOff:
    def test_unset_env_disables_telemetry(self, monkeypatch):
        monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
        assert cli._telemetry_enabled() is False

    @pytest.mark.parametrize("value", _ENABLING)
    def test_explicit_opt_in_enables_telemetry(self, monkeypatch, value):
        monkeypatch.setenv("ANONYMIZED_TELEMETRY", value)
        assert cli._telemetry_enabled() is True

    @pytest.mark.parametrize("value", _DISABLING)
    def test_everything_else_disables_telemetry(self, monkeypatch, value):
        if value is None:
            monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
        else:
            monkeypatch.setenv("ANONYMIZED_TELEMETRY", value)
        assert cli._telemetry_enabled() is False


class TestNoBundledApiKey:
    def test_api_key_is_empty_without_env(self, monkeypatch):
        monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
        assert PostHogAnalytics.API_KEY == ""

    def test_no_upstream_key_string_anywhere_in_module(self):
        import inspect

        from windows_mcp.infrastructure import analytics as analytics_module

        source = inspect.getsource(analytics_module)
        assert "phc_uxdCItyVTjXNU0sMPr97dq3tcz39scQNt3qjTYw5vLV" not in source
        assert "POSTHOG_API_KEY" in source  # the env hook survives

    def test_empty_key_degrades_to_noop_client(self, monkeypatch, tmp_path):
        monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
        monkeypatch.setattr(PostHogAnalytics, "USER_DATA_DIR", tmp_path)
        analytics = PostHogAnalytics()
        assert analytics.client is None
