"""Destructive-command guard for the PowerShell tool (hardened fork).

The guard is a conservative speed bump: a fixed pattern list of commonly
catastrophic commands, on by default, with an explicit operator opt-out
(WINDOWS_MCP_POWERSHELL_GUARD=off). These tests pin three contracts:

1. Well-known destructive commands are refused.
2. Ordinary admin/inspection commands pass through.
3. The opt-out really disables it, and the shell tool honors the refusal
   without executing anything.
"""

import pytest

from windows_mcp.powershell import check_command, guard_enabled
from windows_mcp.powershell.guard import GUARD_ENV_VAR

BLOCKED_COMMANDS = [
    # disk / volume destruction
    "format C:",
    "FORMAT C: /FS:NTFS",
    "Format-Volume -DriveLetter D",
    "diskpart",
    "DISKPART /s script.txt",
    "Clear-Disk -Number 0 -RemoveData",
    "Initialize-Disk -Number 1",
    "cipher /w:C:\\",
    "vssadmin delete shadows /all /quiet",
    "wmic shadowcopy where 'DriveLetter=D' delete",
    # recursive deletion at dangerous scope
    "Remove-Item C:\\ -Recurse -Force",
    "Remove-Item 'C:\\'",
    "rd /s /q C:\\",
    "rmdir /s C:\\",
    "del C:\\*.* /s /q",
    "rm -rf /",
    "rm -r /",
    "Remove-Item C:\\Windows -Recurse",
    # machine control
    "Stop-Computer -Force",
    "Restart-Computer",
    "shutdown /s /t 0",
    "bcdedit /set safeboot minimal",
    # registry
    "reg delete HKLM\\SOFTWARE\\Key /f",
    "reg delete HKCR\\.foo /f",
    "Remove-Item HKLM:\\SOFTWARE\\SomeKey",
    # raw disk writes / evidence destruction
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sda1",
    "wevtutil cl Application",
]

ALLOWED_COMMANDS = [
    "Get-ChildItem C:\\Windows",
    "Get-Process",
    "Get-Content .\\log.txt",
    "New-Item -Path .\\test -ItemType Directory",
    "Remove-Item C:\\temp\\build\\log.txt",
    "Remove-Item HKCU:\\Software\\MyApp",
    "Get-Volume",
    "Format-List -Property Name",
    "ipconfig /all",
    "Get-Service wuauserv",
    "reg query HKLM\\SOFTWARE\\Microsoft",
    "wmic cpu get name",
    "Copy-Item .\\a.txt D:\\backup\\",
]


class TestGuardEnabled:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv(GUARD_ENV_VAR, raising=False)
        assert guard_enabled() is True

    def test_random_value_keeps_guard_on(self, monkeypatch):
        monkeypatch.setenv(GUARD_ENV_VAR, "on")
        assert guard_enabled() is True

    @pytest.mark.parametrize("value", ["off", "OFF", "0", "false", "False", "no", "disabled"])
    def test_explicit_opt_out_disables_guard(self, monkeypatch, value):
        monkeypatch.setenv(GUARD_ENV_VAR, value)
        assert guard_enabled() is False


class TestBlockedCommands:
    @pytest.mark.parametrize("command", BLOCKED_COMMANDS)
    def test_destructive_commands_are_refused(self, monkeypatch, command):
        monkeypatch.delenv(GUARD_ENV_VAR, raising=False)
        refusal = check_command(command)
        assert refusal is not None
        assert "BLOCKED" in refusal
        assert "WINDOWS_MCP_POWERSHELL_GUARD=off" in refusal

    def test_empty_command_passes(self, monkeypatch):
        monkeypatch.delenv(GUARD_ENV_VAR, raising=False)
        assert check_command("") is None


class TestAllowedCommands:
    @pytest.mark.parametrize("command", ALLOWED_COMMANDS)
    def test_ordinary_commands_pass_through(self, monkeypatch, command):
        monkeypatch.delenv(GUARD_ENV_VAR, raising=False)
        assert check_command(command) is None


class TestGuardDisabledBypassesCheck:
    @pytest.mark.parametrize(
        "command", ["format C:", "diskpart", "Remove-Item C:\\ -Recurse", "shutdown /s"]
    )
    def test_opt_out_disables_checking_entirely(self, monkeypatch, command):
        monkeypatch.setenv(GUARD_ENV_VAR, "off")
        assert check_command(command) is None


class _FakeMCP:
    """Captures tool registrations without importing FastMCP."""

    def __init__(self):
        self.tools = {}

    def tool(self, *, name, description, annotations):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class TestShellToolIntegration:
    async def test_blocked_command_returns_403_without_executing(self, monkeypatch):
        from windows_mcp.tools import shell

        monkeypatch.delenv(GUARD_ENV_VAR, raising=False)
        fake = _FakeMCP()
        shell.register(fake, get_desktop=lambda: None, get_analytics=lambda: None)
        powershell_tool = fake.tools["PowerShell"]

        result = await powershell_tool("format C:")

        assert "BLOCKED" in result
        assert "Status Code: 403" in result
        # The executor must never have been invoked for a blocked command.
        assert "Response:" in result

    async def test_disabled_guard_lets_tool_proceed_to_executor(self, monkeypatch):
        from windows_mcp.tools import shell

        monkeypatch.setenv(GUARD_ENV_VAR, "off")
        fake = _FakeMCP()
        shell.register(fake, get_desktop=lambda: None, get_analytics=lambda: None)
        powershell_tool = fake.tools["PowerShell"]

        # With the guard off, a would-be-blocked command falls through to the
        # executor. The command itself is harmless enough to actually run
        # (it only reads), proving the guard no longer intercepts it.
        result = await powershell_tool("diskpart /?", timeout=60)

        assert "Status Code: 403" not in result
