"""serverInfo.version must report the app release, not fastmcp's version.

Upstream created FastMCP without ``version=``, so MCP ``initialize``
responses advertised the fastmcp library's own version in ``serverInfo``
(observed in the wild: fastmcp 4.1.3 alongside app 0.8.8). The hardened
fork passes the distribution version through. These tests pin the helper
and the plumbing into FastMCP.
"""

import importlib.metadata

import pytest

from fastmcp import FastMCP

import windows_mcp.__main__ as cli


class TestAppVersion:
    def test_returns_installed_distribution_version(self):
        # The test venv installs windows-mcp itself (editable), so the
        # metadata lookup must succeed and match pyproject's version.
        expected = importlib.metadata.version("windows-mcp")
        assert cli._app_version() == expected

    def test_falls_back_when_metadata_is_missing(self, monkeypatch):
        def boom(name):
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(importlib.metadata, "version", boom)
        assert cli._app_version() == "0.0.0"

    def test_version_is_a_clean_release_string(self):
        version = cli._app_version()
        assert version
        assert version.replace(".", "").isdigit()


class TestFastMCPPlumbing:
    def test_fastmcp_accepts_and_reports_version(self):
        mcp = FastMCP(name="plumbing-check", version="9.9.9")
        assert mcp.version == "9.9.9"

    def test_build_mcp_uses_app_version(self, monkeypatch):
        # _build_mcp() instantiates the real input controller and subscribes a
        # callback to it. That state lives in module globals and leaks into
        # later tests (control-gate / snapshot tests observed flaking in the
        # full-suite run), so a mock controller keeps this test scoped to what
        # it actually verifies: the FastMCP version wiring. The end-to-end
        # stdio probe documented in CHANGELOG covers the real wiring.
        from unittest.mock import MagicMock

        import windows_mcp.desktop.control as control_module

        monkeypatch.setattr(control_module, "get_controller", lambda: MagicMock())
        monkeypatch.setattr(cli, "_mcp", None)  # bypass the module-level cache

        mcp = cli._build_mcp()

        expected = importlib.metadata.version("windows-mcp")
        assert mcp.version == expected
        assert mcp.version != __import__("fastmcp").__version__
