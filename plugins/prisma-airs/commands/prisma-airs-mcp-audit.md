---
description: Scan the descriptions of currently-connected MCP tools for tool-poisoning / prompt-injection before trusting them
argument-hint: "[server-name ...]"
allowed-tools: Bash(python3:*), Write, Read
---

Audit MCP tool **descriptions**, not tool calls -- this is the
`method: "tools/list"` half of `tool_event` scanning, catching a poisoned
tool description before it ever reaches context as something you'd act on.
Scope: $ARGUMENTS (server names to check; all currently-connected MCP
servers if empty).

## Procedure

1. From your own current tool listing, identify every tool whose name
   matches `mcp__<server>__<tool>` (optionally filtered to the server names
   in `$ARGUMENTS`). For each one you have its full name, description, and
   parameter schema already -- that's the artifact being audited.
2. For each tool, write its description + parameter schema (as JSON) to a
   scratch file, then scan it:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_once.py \
     --server-name <server> --method tools/list --tool-invoked <tool> \
     --input-file <scratch-file>
   ```
3. Collect verdicts. Do not stop at the first `block`/`alert` -- a poisoned
   marketplace could plant more than one.

## Reporting

For every tool that came back `alert` or `block`, quote the specific
`features` the scan returned (e.g. `tool_detected.credential leakage`,
`tool_detected.context poisoning`) and the tool's full name. For a `block`,
recommend the user disconnect or reconfigure that MCP server before
continuing to use it -- this command only reports, it does not
disconnect anything itself. If everything scanned `allow`, say so plainly
with a count, not just silence.

If `/prisma-airs-setup` hasn't run yet, `scan_once.py` will print
`{"error": "not_configured", ...}` and exit 2 -- point the user there instead
of retrying.
