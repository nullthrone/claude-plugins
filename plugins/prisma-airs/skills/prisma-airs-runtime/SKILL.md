---
name: prisma-airs-runtime
description: The Prisma AIRS Scan API contract this plugin implements against -- endpoints, request/response shapes, the three-valued action (allow/alert/block), fail-open vs fail-closed policy, and limits. Use when writing or debugging anything that calls scripts/airs.py, reasoning about a hook's behavior, or explaining why a scan was or wasn't blocked. Do NOT use this to walk a user through onboarding -- that is prisma-airs-setup.
---

# Prisma AIRS Runtime Contract

What every hook, `/prisma-airs-gate`, `/prisma-airs-mcp-audit`, and the
`airs-report-triage` agent are actually calling. Primary source is
[pan.dev](https://pan.dev/prisma-airs/api/airuntimesecurity/) throughout;
where something comes from Palo Alto's community reference integrations
repo instead (not pan.dev), it's marked as such.

## The one call that matters

`POST {region-host}/v1/scan/sync/request`, header `x-pan-token: <key>`, body
`{ai_profile: {profile_name | profile_id}, contents: [...], metadata: {...}}`.
Each element of `contents` is one of `prompt` / `response` / `code_prompt` /
`code_response` / `tool_event`. The response's `action` field is what every
caller in this plugin gates on.

See `${CLAUDE_PLUGIN_ROOT}/reference/scan-api.md` for the full endpoint,
schema, and limits reference with pan.dev citations, and
`${CLAUDE_PLUGIN_ROOT}/scripts/airs.py` for the client implementation.

## Gate on `action`, never on `category`

`category` (`malicious`/`benign`/`error`/`timeout`) is the detector's raw
judgment. `action` (`allow`/`block`, per pan.dev; plus `alert`, per Palo
Alto's own community Claude Code skill -- not on pan.dev) is what the
tenant's **security profile** decided to do about it. Two profiles can see
identical `category: malicious` content and produce different `action`
values. Always act on `action`.

`classify_action()` in `scripts/hook_common.py` treats anything that isn't
exactly `"allow"` or `"block"` -- including `"alert"` and any future,
undocumented value -- as `"alert"`: warn, don't silently allow, don't hard
block either. That collapsing-to-alert is deliberate: a value this plugin
doesn't recognize should never be treated the same as an explicit `allow`.

| `action` | UserPromptSubmit | PreToolUse | PostToolUse / Stop |
|---|---|---|---|
| `allow` | through | `defer` (no hook opinion) | through |
| `alert` | through + warning context | `ask` (human decides) | warning context |
| `block` | `decision: block` | `permissionDecision: deny` | `decision: block` (already ran -- this surfaces as an error to react to, it can't undo the call) |

## Fail-open vs fail-closed: not a Palo Alto recommendation

Checked directly: the
[error codes page](https://pan.dev/prisma-airs/api/airuntimesecurity/errorcodes/),
the [API overview](https://pan.dev/prisma-airs/api/airuntimesecurity/airuntimesecurityapi/),
and the [use-cases page](https://pan.dev/prisma-airs/api/airuntimesecurity/usecases/)
contain **no** client-side guidance for what to do when the scan API doesn't
answer (network error, timeout, 429, 5xx). Palo Alto's structural answer is
that latency policy belongs in the **security profile** itself
(`model-configuration.latency.inline-timeout-action` +
`max-inline-latency`), not in the calling application.

This plugin's own default, set in `scripts/config.py` and overridable per
project via `.prisma-airs.json`'s `on_unreachable`:

- **Runtime hooks**: `user_prompt_submit` fails open (allow, loud warning,
  audit log entry); `pre_tool_use` defaults to `ask` -- a human decides
  rather than the hook silently choosing either extreme.
- **`/prisma-airs-gate`**: always fails closed (non-zero exit), regardless
  of `.prisma-airs.json`. A CI gate that goes green on "the scanner didn't
  answer" isn't a gate.

Say this plainly whenever explaining the behavior -- it's an engineering
default, not something pan.dev told us to do.

## Limits (all from pan.dev, some internally contradictory)

- 2 MB per sync request, 5 MB per async request, ≤100 URLs either way.
- Async batch size: the limitations page says 25; the SDK usage page's own
  example text says 5. `scripts/airs.py`'s `MAX_ASYNC_BATCH_ITEMS` takes the
  smaller number so nothing here ever exceeds either page's stated limit.
- `GET /v1/scan/results` and `/v1/scan/reports`: ≤5 IDs per call, and (per
  the error-codes page) capped at 10 requests/minute regardless of quota.
- Contextual grounding detector: context ≤100k chars, prompt ≤10k, response
  ≤20k -- separate from this plugin's own `max_content_chars` truncation,
  which exists to keep a hook fast, not to respect this API-side limit.

## Content types this plugin actually sends

- `prompt` / `response`: plain user input / model output.
- `code_prompt` / `code_response`: used for `Bash` tool input, since a shell
  command is code, not prose.
- `tool_event` (`ecosystem`, `method`: `tools/list`|`tools/call`,
  `server_name`, `tool_invoked`, `input`/`output`): used **only** for
  `mcp__*`-named tool calls, matching what pan.dev's schema actually
  evidences this field for. Built-in tools (`Write`, `Edit`, `WebFetch`,
  `WebSearch`) are scanned as plain `prompt`/`response` content instead of
  stretching `tool_event` past its documented MCP use case.

## No raw content in the audit log

`scripts/hook_common.py`'s `audit()` writes verdicts, feature flags,
`scan_id`/`report_id`, and timestamps -- never the scanned text itself, and
never the API key. The Scan API's threat-report response can contain up to
10 raw-text snippets per detector (`dlp_snippets`, etc.) -- if you're
extending this plugin to fetch `GET /v1/scan/reports` for deeper triage (see
the `airs-report-triage` agent), keep that same rule: snippets are for a
human to read in the moment, not for a log file.
