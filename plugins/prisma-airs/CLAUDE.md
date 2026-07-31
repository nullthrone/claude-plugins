# CLAUDE.md

Conventions and signposts for this plugin. **No architecture decisions live
here** -- those are smADRs in `docs/decisions/`. If while editing this file
you feel the urge to write down *why* something is built the way it is:
that is an ADR, not a CLAUDE.md entry.

## What this plugin will not do

It will not treat any `action` value other than exactly `"block"` as
anything but potentially significant. `hook_common.classify_action()`
collapses `"alert"` and any unrecognized future value into the same
non-silent bucket -- see `docs/decisions/0003`. Do not add a code path that
only checks `action == "block"` and ignores everything else; that's the
exact silent-allow failure mode ADR 0003 exists to prevent.

It will not fail closed in the runtime hooks when unconfigured, and will
not fail open in `/prisma-airs-gate` when the scan can't complete. These are
deliberately opposite defaults for deliberately different surfaces -- see
`docs/decisions/0002`. Do not "fix" one to match the other.

It will not gain a plugin-level `.mcp.json`. The vendor MCP server is
setup-time opt-in, written into the *project's* config by
`/prisma-airs-setup`, never shipped as a plugin dependency -- see
`docs/decisions/0001`.

## Non-negotiables

**No raw content in the audit log.** `hook_common.audit()` logs verdicts,
feature flags, `scan_id`/`report_id`, timestamps -- never the prompt, tool
input/output, or a DLP snippet. Any new logging call must follow this; a
leaked secret in `.prisma-airs/audit.jsonl` defeats the entire point of the
DLP detector that flagged it.

**No secret in a committable file.** `.prisma-airs.json` never contains an
API key. It comes from the environment only (`config.py`'s `api_key`
property).

**Stdlib only in `scripts/`.** `urllib`, `json`, `argparse`, `subprocess` --
nothing that needs `pip install` to run. These scripts must work in any
Claude Code environment with zero setup step. If a feature genuinely needs
a dependency, that's a signal it belongs in a runbook (a command `.md` that
tells Claude what to do) rather than a shipped script.

**Every pan.dev claim in `reference/` carries its URL.** Where pan.dev is
silent on something (fail-open/fail-closed guidance is the main example),
say so explicitly rather than leaving a gap that reads as an oversight. See
`reference/scan-api.md`'s "What pan.dev does *not* say" section for the
pattern.

## Layout

| Path | Purpose |
|---|---|
| `scripts/config.py` | `.prisma-airs.json` + env resolution, region table, the `is_configured()` gate |
| `scripts/airs.py` | Scan API client (`x-pan-token` auth) -- sync/async scan, results, reports |
| `scripts/hook_common.py` | shared hook plumbing: the inert gate, audit log, `classify_action()` |
| `scripts/hook_*.py` | the four runtime hooks, one per Claude Code event |
| `scripts/gate.py` | `/prisma-airs-gate`'s implementation -- always fail-closed |
| `scripts/scan_once.py` | one-shot scan CLI used by setup's test call and the MCP audit |
| `hooks/hooks.json` | wires the four hook scripts into Claude Code |
| `skills/prisma-airs-setup/` | the onboarding runbook -- conversational, asks real questions |
| `skills/prisma-airs-runtime/` | the API contract reference -- what to call, how to gate, why |
| `agents/airs-report-triage.md` | isolated-context reducer for deep threat-report structures |
| `reference/` | pan.dev-cited detail: endpoints, detections, error handling, upstream attribution |
| `docs/decisions/` | smADRs |
| `tests/` | offline hook/gate verification against a mock server -- not a shipped component |

## When to write an ADR

- Changing what a hook does when the scan is unreachable, or when `action`
  is `alert`/unrecognized.
- Adding a new hook event, or changing what content type it scans as
  (`prompt` vs `tool_event`, etc.).
- Anything that would make the plugin depend on the vendor MCP server
  rather than treat it as optional.
- Changing what `/prisma-airs-gate` scans by default, or its exit-code
  semantics.

Wording, new reference detail, a bug fix that doesn't change a decision:
no ADR. Just a PR.

## Signposts

- `/prisma-airs-setup` -- onboarding
- `/prisma-airs-gate` -- CI gate
- `/prisma-airs-mcp-audit` -- MCP tool-poisoning audit
- `skills/prisma-airs-runtime/SKILL.md` -- the API contract, read this first when debugging a hook
- `tests/test_hooks.py` -- run this after touching any hook or `gate.py`
