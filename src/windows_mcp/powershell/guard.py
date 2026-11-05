"""Destructive-command guard for the PowerShell tool (hardened fork addition).

This is a conservative *speed bump*, not a sandbox. It matches a fixed list of
command patterns that are commonly associated with irreversible data loss,
machine-wide disruption, or anti-forensic cleanup, and refuses to run them
unless the operator explicitly disables the guard.

Deliberate design trade-offs:

- **Conservative by list, not by analysis.** Only well-known, high-impact
  patterns are matched. Many dangerous commands (obfuscated ones, wildcarded
  paths, scripting constructs) will pass straight through. Do not treat a
  passing command as safe.
- **Block, don't sanitize.** There is no attempt to rewrite or scope a
  command; a blocked command returns a refusal the calling agent can act on.
- **Escape hatch is explicit.** ``WINDOWS_MCP_POWERSHELL_GUARD=off`` (or
  ``0``/``false``/``no``/``disabled``) disables the guard for the whole
  server process. There is no per-call override: an MCP caller cannot turn
  the guard off for its own convenience.
"""

import logging
import os
import re

__all__ = ["GUARD_ENV_VAR", "check_command", "guard_enabled"]

logger = logging.getLogger(__name__)

GUARD_ENV_VAR = "WINDOWS_MCP_POWERSHELL_GUARD"

_OPT_OUT_VALUES = {"off", "0", "false", "no", "disabled"}

# (pattern, human-readable reason) pairs. Case-insensitive; applied to the
# whole command string. Keep entries to high-confidence, high-impact actions:
# this list wants near-zero false positives on ordinary admin work.
_DESTRUCTIVE_PATTERNS: list[tuple[str, str]] = [
    # -- Disk / volume destruction -------------------------------------------
    (r"\bformat\s+[a-z]:", "formats a drive volume"),
    (r"\bformat-volume\b", "Format-Volume erases a volume"),
    (r"\bdiskpart\b", "diskpart can wipe or rewrite disk structures"),
    (r"\bclear-disk\b", "Clear-Disk deletes every partition on a disk"),
    (r"\binitialize-disk\b", "Initialize-Disk rewrites the disk partition table"),
    (r"\bcipher\s+/w\b", "cipher /w irreversibly wipes deleted-file data on a volume"),
    (r"\bvssadmin\b[^|;&]*\bdelete\b", "deletes volume shadow copies (restore points)"),
    (r"\bwmic\b[^|;&]*shadowcopy[^|;&]*\bdelete\b", "deletes volume shadow copies"),
    # -- Recursive deletion at dangerous scope --------------------------------
    # Drive root: a bare "X:\" NOT followed by a path character, so
    # "Remove-Item C:\ -Recurse" matches but "Remove-Item C:\Temp\logs" does not.
    (r"\bremove-item\b[^|;&]*['\"]?[a-z]:\\(?![\w.])", "Remove-Item targeting a drive root"),
    (r"\brd(\.exe)?\s+/s\b[^|;&]*[a-z]:\\\s*$", "rd /s on a drive root"),
    (r"\brmdir\s+/s\b[^|;&]*[a-z]:\\\s*$", "rmdir /s on a drive root"),
    (r"\bdel(\.exe)?\b[^|;&]*[a-z]:\\\*", "del against a drive root wildcard"),
    # rm with a recursive flag aimed at the filesystem root (Git Bash / busybox style):
    # flags must contain "r" and the target must be a bare "/".
    (r"\brm\s+(?:-\w+\s+)*-(?=[a-z]*r)[a-z]+\s+/(?:\s|$)", "rm -r against the filesystem root"),
    (r"\bremove-item\b[^|;&]*c:\\windows\b", "deletes files under C:\\Windows"),
    # -- Machine control -------------------------------------------------------
    (r"\bstop-computer\b", "shuts down the machine"),
    (r"\brestart-computer\b", "reboots the machine"),
    (r"\bshutdown(\.exe)?\b", "shuts down or reboots the machine"),
    (r"\bbcdedit\b", "edits the boot configuration data"),
    # -- Registry ---------------------------------------------------------------
    (r"\breg(\.exe)?\s+delete\s+hklm\b", "deletes HKEY_LOCAL_MACHINE registry keys"),
    (r"\breg(\.exe)?\s+delete\s+hkcr\b", "deletes HKEY_CLASSES_ROOT registry keys"),
    (r"\breg(\.exe)?\s+delete\s+hkey_classes_root\b", "deletes HKEY_CLASSES_ROOT registry keys"),
    (r"\bremove-item\b[^|;&]*hklm:", "deletes HKEY_LOCAL_MACHINE registry keys"),
    # -- Raw disk writes / evidence destruction ---------------------------------
    (r"\bdd\b\s+if=", "raw disk write"),
    (r"\bmkfs\b", "formats a filesystem"),
    (r"\bwevtutil\b[^|;&]*\bcl\b", "clears Windows event logs"),
]

_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), reason)
    for pattern, reason in _DESTRUCTIVE_PATTERNS
]

_REFUSAL_TEMPLATE = (
    "BLOCKED by windows-mcp-hardened destructive-command guard: this command {reason}.\n"
    "The guard is a conservative speed bump, not a sandbox. If this command is "
    "intentional, the operator can start the server with "
    "WINDOWS_MCP_POWERSHELL_GUARD=off, or you can narrow the command (e.g. target "
    "a specific subdirectory instead of a drive root)."
)


def guard_enabled() -> bool:
    """Whether the destructive-command guard should run. On by default.

    Reads the ``WINDOWS_MCP_POWERSHELL_GUARD`` environment variable.
    Disabling values (case-insensitive, whitespace-trimmed): ``off``, ``0``,
    ``false``, ``no``, ``disabled``. Unset, or any other value, keeps the
    guard on.

    Returns:
        ``True`` when commands should be checked, ``False`` to skip the guard.
    """
    value = os.getenv(GUARD_ENV_VAR)
    if value is None:
        return True
    return value.strip().lower() not in _OPT_OUT_VALUES


def check_command(command: str) -> str | None:
    """Check a command against the destructive-pattern list.

    Args:
        command: The raw PowerShell command string about to be executed.

    Returns:
        A refusal message when the guard is enabled and the command matches a
        destructive pattern; ``None`` when execution may proceed.
    """
    if not command:
        return None
    if not guard_enabled():
        return None

    for pattern, reason in _COMPILED_PATTERNS:
        if pattern.search(command):
            logger.warning("Guard blocked command (%s): %.200s", reason, command)
            return _REFUSAL_TEMPLATE.format(reason=reason)
    return None
