# 🪟 Windows-MCP — Hardened Fork

A security-hardened fork of [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP), based on upstream `main` at commit `556067c` (v0.8.8).

All 21 upstream tools and features are **unchanged**. This fork changes only security-relevant defaults and adds safeguards — the diff is deliberately minimal so each change can be proposed upstream.

> Tools reference, demos, and troubleshooting live in the upstream README: [`docs/UPSTREAM_README.md`](docs/UPSTREAM_README.md).

## Why this fork exists

Windows-MCP hands an AI agent direct control of a Windows machine: shell execution, UI automation, registry and process management. That power is exactly what makes three upstream defaults uncomfortable for unattended use (findings from an audit on 2026-11-05):

1. **Telemetry on by default, with a bundled API key.** Upstream ships a PostHog public key as the fallback for `POSTHOG_API_KEY` and enables telemetry unless `ANONYMIZED_TELEMETRY=false`. A default install therefore reports tool usage — tool names, durations, client name/version, and a persisted user id — to the upstream project's PostHog instance out of the box.
2. **The PowerShell tool inspects nothing.** `powershell_tool` executes any command. Upstream mitigations exist only at the tool level (`--exclude-tools` / `WINDOWS_MCP_EXCLUDE_TOOLS`) and in the desktop control policy — neither looks at command content.
3. **`serverInfo.version` reports the wrong product.** Upstream constructs `FastMCP` without `version=`, so MCP `initialize` responses advertise the fastmcp *library's* version (observed: `4.1.3`) instead of the app release (`0.8.8`), breaking client-side compatibility checks and support triage.

## What changed

| # | Change | Upstream | This fork | Escape hatch |
|---|--------|----------|-----------|--------------|
| 1 | Telemetry | ON, bundled PostHog key | **OFF** — opt-in requires `ANONYMIZED_TELEMETRY=true` *and* your own `POSTHOG_API_KEY` | — |
| 2 | PowerShell destructive-command guard | none | **ON** — refuses a conservative list of catastrophic commands | `WINDOWS_MCP_POWERSHELL_GUARD=off` |
| 3 | `serverInfo.version` | fastmcp's version (`4.1.3`) | app release (`0.8.8`) | — |

### 1. Telemetry is opt-in

- The bundled PostHog key is removed; `POSTHOG_API_KEY` has no default. An empty key already degrades gracefully to a no-op client.
- Telemetry initializes only when the operator sets `ANONYMIZED_TELEMETRY=true` (enabling values: `on`/`1`/`true`/`yes`/`enabled`) **and** provides their own `POSTHOG_API_KEY`.
- If you opt in, events go to *your* PostHog project (`POSTHOG_HOST` configurable), not to anyone else's.

### 2. Destructive-command guard (speed bump, not a sandbox)

Before executing, the PowerShell tool matches the command against a fixed, case-insensitive pattern list and refuses to run matches, keeping the tool's usual `Response:` / `Status Code:` shape with code `403` so calling agents can parse the refusal like any other failure.

What it blocks (25 patterns):

- **Volume/disk destruction:** `format X:`, `Format-Volume`, `diskpart`, `Clear-Disk`, `Initialize-Disk`, `cipher /w`, `vssadmin delete`, `wmic shadowcopy delete`
- **Deletion at dangerous scope:** `Remove-Item` on a drive root or under `C:\Windows`, `rd`/`rmdir`/`del` on drive roots, `rm -r` on the filesystem root
- **Machine control:** `Stop-Computer`, `Restart-Computer`, `shutdown`, `bcdedit`
- **Registry:** `reg delete HKLM/HKCR`, `Remove-Item HKLM:`
- **Raw writes / anti-forensics:** `dd if=`, `mkfs`, `wevtutil cl`

What it honestly cannot do:

- It matches a **fixed pattern list**. Obfuscated, encoded, or scripted constructs pass straight through. A passing command is *not* a safe command.
- There is no per-call override: `WINDOWS_MCP_POWERSHELL_GUARD=off` (or `0`/`false`/`no`/`disabled`) disables the guard for the whole server process — the operator's decision, not the MCP caller's.
- The list is kept conservative to avoid false positives on ordinary admin work.

### 3. Correct `serverInfo.version`

`FastMCP` is constructed with the installed `windows-mcp` distribution version. End-to-end stdio probe after the fix:

```json
{"serverInfo.name": "windows-mcp", "serverInfo.version": "0.8.8"}
```

## Verification

- **86 new tests** (pytest, upstream style): telemetry default-off + no bundled key (24), guard blocked/allowed/opt-out/tool-integration (57), version reporting (5).
- Guard tool-integration tests prove blocked commands never reach the executor.
- Full upstream test suite still passes (desktop-dependent tests excluded on headless machines).

## Measured upstream characteristics (2026-11, one machine)

Recorded during the audit, unchanged by this fork — useful when planning MCP host timeouts:

- stdio cold start **~16 s** before `initialize` answers
- 21 tools; combined tool descriptions **~10.7 KB** (Snapshot alone ~1.8 KB)
- `DisplayInventory` ~2.8 s / ~0.3 KB; `Snapshot` ~1.1 s / ~3.7 KB (ASCII table)

## Install

Requires Python 3.14+ on Windows 10/11.

```bash
pip install git+https://github.com/chenlong548/windows-mcp-hardened.git
# or, for the CLI server:
uvx --from git+https://github.com/chenlong548/windows-mcp-hardened.git windows-mcp serve
```

Claude Desktop / MCP host config (stdio):

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/chenlong548/windows-mcp-hardened.git", "windows-mcp", "serve"]
    }
  }
}
```

All upstream `serve` flags (`--auth-key`, `--ip-allowlist`, `--exclude-tools`, `--control-policy`, ...) work unchanged.

## Attribution & license

- Upstream project: [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP) — MIT License, Copyright (c) 2025 Jeomon George. [`LICENSE.md`](LICENSE.md) is preserved unmodified.
- Fork changes: © 2026 [chenlong548](https://github.com/chenlong548), same MIT license.
- Intent: keep the diff minimal and PR-able upstream. Each commit documents what upstream did and what changed.
