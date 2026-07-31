# What Came From Where

Two sources fed this plugin, and they don't carry equal weight. This file
exists so that distinction stays visible after the fact.

## pan.dev -- primary, verified

Everything in `reference/scan-api.md`, `reference/detections.md`, and
`reference/errors.md` was fetched directly from pan.dev pages and quoted or
paraphrased with a citation. Where a pan.dev page was checked and found to
say nothing on a topic (e.g. fail-open/fail-closed guidance), that absence
is stated explicitly rather than left ambiguous -- see
`reference/scan-api.md`'s "What pan.dev does *not* say" section.

## `PaloAltoNetworks/prisma-airs-integrations` (`Anthropic/` directory) --
secondary, MIT-licensed, explicitly "best effort"

That repository's own README states: *"The contents of this repository are
community examples and reference implementations, supported as best effort
by Palo Alto Networks."* Three things came from it that pan.dev does not
document at all:

1. **The three-valued `action`.** pan.dev's schema only documents
   `"allow"`/`"block"`. Their `claude-code-skill/SKILL.md` documents a
   third value, `"alert"`. `scripts/hook_common.py`'s `classify_action()`
   treats it as its own category (warn, don't hard-block, don't silently
   allow) precisely because it's undocumented on the primary source --
   see `skills/prisma-airs-runtime/SKILL.md`.
2. **The existence of a Palo Alto-published MCP server** for AIRS (HTTP
   transport, `x-pan-token`/`x-pan-profile` headers, tools
   `pan_inline_scan`/`pan_batch_scan`/`pan_get_scan_results`). Consistent
   with pan.dev's own `source: "AI-Runtime-MCP-Server"` hint in
   `ScanResponse`, but the server itself is not documented on pan.dev. This
   plugin does not ship it as a bundled `.mcp.json` -- see
   `docs/decisions/0001-rest-not-vendor-mcp-in-hooks.md`. `/prisma-airs-setup`
   offers to add it to the project's own config, on request, with this
   provenance noted to the user at that point.
3. **Env var naming** (`PRISMA_AIRS_API_KEY`, `PRISMA_AIRS_PROFILE_NAME`,
   `PRISMA_AIRS_URL`). `scripts/config.py` reads these first, falling back
   to pan.dev's own SDK convention (`PANW_AI_SEC_API_KEY`), so either
   lineage of existing environment setup works unmodified.

## Gaps that repo's own README and hook scripts named, and how this plugin
answers them

Read directly from their `claude-code-hooks/README.md` and
`hooks/scan-user-input.sh`:

| Their stated gap | This plugin's answer |
|---|---|
| "No model response hook configured" -- generated output without a tool call is never scanned | `hook_stop.py`, scanning `last_assistant_message` -- opt-in (`hooks.stop`), off by default given no documented latency bound |
| No curl timeout on the prompt scan | `config.timeout_seconds` (default 5s) is enforced on every request in `airs.py` |
| Fail-closed (`exit 2`) when unconfigured | Deliberately inverted here -- see `docs/decisions/0002-inert-until-configured.md`. Their design is a hand-installed, single-user, global hook set; a marketplace plugin installed by someone who hasn't configured it yet must not stop their session |
| Hard `jq` dependency | Stdlib-only Python throughout (`airs.py`, `config.py`, the hook scripts) |
| WebFetch/WebSearch scanned *after* Claude's own summarization, not the raw fetched content | Same limitation applies here for built-in web tools -- not solved, only reproduced; noted so it isn't silently inherited without comment |

## License

Their `claude-code-hooks/LICENSE` is MIT, copyright line "Claude Code
Security Hooks" (not Palo Alto Networks as an entity) -- reproduced as-is
in this plugin's own `NOTICE` file. No code was copied verbatim; the
design ideas above (checkpoints, env var names, the gaps table) were
re-implemented from scratch against this plugin's own conventions
(stdlib-only, inert-by-default, config-driven tool matching).
