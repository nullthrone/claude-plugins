# prisma-airs

Guided setup and runtime protection for
[Prisma AIRS](https://pan.dev/prisma-airs/api/airuntimesecurity/) (Palo Alto
Networks AI Runtime Security) in Claude Code. Ships as a Claude Code plugin.

**This plugin sends prompt text, tool inputs, and tool outputs to an
external Palo Alto Networks service for scanning.** That's the entire
point of it -- say so plainly before anyone turns it on. Everything is
inert until `/prisma-airs-setup` runs; see [Limitations](#limitations).

## Install

From the marketplace (recommended):

```
/plugin marketplace add nullthrone/claude-plugins
/plugin install prisma-airs@nullthrone
```

### Local / development install

```
git clone https://github.com/nullthrone/claude-plugins
/plugin marketplace add ./claude-plugins
/plugin install prisma-airs@nullthrone
```

Validate with `claude plugin validate ./claude-plugins`.

## What you get

- `/prisma-airs-setup` -- guided onboarding: prerequisites, region, an
  explicit data-flow disclosure, a key-handling choice left to you, a
  positive **and** negative verified test scan, then (opt-in)
  `.prisma-airs.json` and the vendor MCP server.
- **Runtime hooks** (`hooks/hooks.json`) -- `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse`, and an opt-in `Stop` hook, each scanning
  through the Scan API. Inert (no network call at all) until
  `.prisma-airs.json` and an API key both exist.
- `/prisma-airs-gate` -- scans prompt-shaped repository artifacts
  (`CLAUDE.md`, commands, skills, agents) or `git diff --cached`, exit-code
  gated, **always fail-closed**.
- `/prisma-airs-mcp-audit` -- scans the *descriptions* of currently
  connected MCP tools for tool-poisoning before you trust them.
- `airs-report-triage` agent -- fetches and reduces deep threat-report
  structures in an isolated context.

## Quickstart

```
/prisma-airs-setup
```

This is a conversation, not a silent script -- it will ask about data flow,
region, and how you want the API key handled before writing anything.

## Usage

### Runtime hooks

Once `/prisma-airs-setup` writes `.prisma-airs.json`, every prompt and
(by default) `Bash`/`Write`/`Edit`/`WebFetch`/`WebSearch`/`mcp__*` tool call
is scanned. The result gates on the response's `action` field:

| `action` | Effect |
|---|---|
| `allow` | nothing happens |
| `alert` | you're warned, or (for tool calls) asked to confirm |
| `block` | the prompt/tool call is stopped |

The `Stop` hook (final response text) is off by default -- turn it on in
`.prisma-airs.json`'s `hooks.stop` if you want response-content coverage
and accept the added latency.

### CI gate

```
/prisma-airs-gate                 # scan CLAUDE.md, commands/, skills/, agents/
/prisma-airs-gate --diff          # scan the staged diff
/prisma-airs-gate path/to/file.md # scan specific files
```

Exit `0` clean, `1` flagged, `2` the scan itself failed (always treated as
a failure here, unlike the runtime hooks -- see `docs/decisions`).

### MCP tool audit

```
/prisma-airs-mcp-audit
```

Scans the tool descriptions of every currently connected MCP server for
signs of tool poisoning, before you act on anything they claim to do.

## Configuration

`.prisma-airs.json`, at the project root, committable, no secrets:

```json
{
  "region": "us",
  "profile_name": "your-security-profile",
  "hooks": { "user_prompt_submit": true, "pre_tool_use": true,
             "post_tool_use": true, "stop": false },
  "tool_matcher": "Bash|Write|Edit|WebFetch|WebSearch|mcp__.*",
  "on_unreachable": { "user_prompt_submit": "allow", "pre_tool_use": "ask" },
  "timeout_seconds": 5,
  "max_content_chars": 20000,
  "audit_log": ".prisma-airs/audit.jsonl"
}
```

The API key is **never** in this file. Set `PRISMA_AIRS_API_KEY` (or
`PANW_AI_SEC_API_KEY`, pan.dev's own SDK convention -- either works) in your
environment. `/prisma-airs-setup` walks through the options for where that
lives.

## How it works

Every scanning surface is a thin stdlib Python client
(`scripts/airs.py`, `scripts/config.py`) against
`POST /v1/scan/sync/request` (and the async/results/reports endpoints for
`/prisma-airs-gate`). No third-party dependencies, no vendor MCP server
required. See `skills/prisma-airs-runtime/SKILL.md` for the full API
contract and `reference/scan-api.md` for the pan.dev citations behind it.

## Limitations

- **No latency guarantee.** pan.dev documents no per-request latency bound
  for the scan API. Hooks enforce a client-side timeout (`timeout_seconds`,
  default 5s) and the `Stop` hook is off by default because of this.
- **Fail-open/fail-closed is our default, not Palo Alto's.** pan.dev gives
  no client-side guidance for what to do when the API doesn't answer at
  all. This plugin's defaults are documented in `docs/decisions/` and
  `reference/errors.md` -- read them before relying on this in a
  high-stakes environment.
- **Web content scanning inherits a known gap.** Built-in `WebFetch`/
  `WebSearch` tools are scanned on Claude's *summarized* output, not the
  raw fetched page -- an injection payload could be stripped before the
  scan ever sees it. Reproduced from Palo Alto's own community reference
  integration, not solved by this plugin.
- **The vendor MCP server is not on pan.dev.** Only in Palo Alto's
  community reference repo. Offered as an opt-in in `/prisma-airs-setup`,
  flagged as such, never load-bearing for the hooks. See
  `docs/decisions/0001`.

## License

MIT. See `LICENSE` and `NOTICE` (attribution for design ideas drawn from
Palo Alto's own community reference integrations, itself MIT-licensed).
