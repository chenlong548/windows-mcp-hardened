# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com). Versioning
follows the upstream release this fork is based on; fork revisions get an `-hN`
suffix and do not renumber upstream's files (a version-consistency test guards
pyproject.toml / manifest.json / server.json).

## 0.8.8-h1 — 2026-11-05

Based on upstream v0.8.8, `main` @ `556067c` (CursorTouch/Windows-MCP).

### Changed

- **Telemetry is opt-in.** Upstream enabled PostHog telemetry unless
  `ANONYMIZED_TELEMETRY=false`, with a bundled API key pointing at the upstream
  project's PostHog instance. The bundled key is removed and telemetry now
  initializes only when the operator sets `ANONYMIZED_TELEMETRY=true` and
  provides their own `POSTHOG_API_KEY`. An empty key degrades to a no-op
  client as before.

### Added

- **Destructive-command guard for the PowerShell tool**, on by default.
  A conservative fixed-pattern list (volume wipe, diskpart, shadow-copy
  deletion, drive-root/system-directory recursive deletion, machine power
  control, HKLM/HKCR registry deletion, raw disk writes, event-log clearing)
  is refused with the tool's usual `Response:`/`Status Code:` shape and code
  `403`. Operators disable it process-wide with
  `WINDOWS_MCP_POWERSHELL_GUARD=off`; there is no per-call override.
  Documented honestly as a speed bump, not a sandbox.

### Fixed

- **`serverInfo.version` reports the windows-mcp release (`0.8.8`)** instead
  of the fastmcp library's own version (`4.1.3`), by passing
  `version=_app_version()` to the FastMCP constructor. Verified end-to-end
  via a stdio `initialize` probe.

### Tests

- 86 new tests (telemetry 24, guard 57, version 5) in upstream pytest style.
- One upstream test adapted: the README moved to `docs/UPSTREAM_README.md`,
  so the Issue #506 documentation contract now checks the moved file.
- Three test-environment fixes so the suite is green outside a clean
  English CI box: the `_build_mcp()` version test now mocks the input
  controller (the real one leaked global state and flaked later tests in
  full-suite order); the CLIXML test skips on non-English Windows UI
  languages; the SSRF rebind test pins a proxy-less environment (both
  env-var and Windows-registry proxies are bypassed via `requests.utils.getproxies`).
- Full suite on the audit machine (zh-CN Windows 11, system proxy on):
  **1660 passed, 9 skipped, 0 failed**.

### Known upstream characteristics (unchanged, measured 2026-11)

- stdio cold start ~16 s before `initialize` answers
- 21 tools; combined tool descriptions ~10.7 KB
- `DisplayInventory` ~2.8 s; `Snapshot` ~1.1 s / ~3.7 KB

Deliberately **not** changed in this revision (too invasive for a minimal,
PR-able fork): compact JSON output mode for `Snapshot`, trimming tool
descriptions. See the upstream README for the unchanged behavior.
