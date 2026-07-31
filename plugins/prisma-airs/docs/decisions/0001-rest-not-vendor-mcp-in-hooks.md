---
id: 0001
title: hooks call the Scan API directly over REST; the vendor MCP server is setup-time opt-in, not a dependency
status: accepted
date: 2026-07-31
deciders: [thomas]
tags: [architecture, mcp, hooks]
supersedes: []
---

## Context and Problem Statement

Palo Alto Networks publishes an MCP server for Prisma AIRS
(`github.com/PaloAltoNetworks/prisma-airs-integrations`,
`Anthropic/claude-code-mcp/`): HTTP transport, `x-pan-token`/`x-pan-profile`
headers, tools `pan_inline_scan`/`pan_batch_scan`/`pan_get_scan_results`.
This isn't documented on pan.dev, only in that repository, but pan.dev's own
`ScanResponse.source` field lists `"AI-Runtime-MCP-Server"` as an example
value -- consistent with it being real. Given this, should the runtime hooks
(`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`) call AIRS through
that MCP server, or call the REST Scan API directly?

## Decision Drivers

- Claude Code hooks are shell commands invoked outside any conversation
  turn -- they have no MCP client and cannot call an MCP tool. Whatever
  scans a prompt before Claude sees it must speak REST or nothing.
- A plugin's own `.mcp.json` is active in every session the plugin is
  installed into, whether or not the user has configured credentials for
  it -- an unconditional MCP dependency would mean connection errors on
  every session start until `/prisma-airs-setup` runs.
- The MCP server is undocumented on pan.dev, our sole verified primary
  source; treating it as foundational would mean depending on a fact this
  plugin can't independently confirm stays true.

## Considered Options

1. Ship a plugin-level `.mcp.json` pointing at the vendor MCP server;
   hooks and any modeled-driven scanning go through it.
2. Hooks call the REST Scan API directly (stdlib HTTP client); the MCP
   server is offered, opt-in, only inside `/prisma-airs-setup`, written
   into the *project's* `.mcp.json` if the user wants it.
3. Reimplement an MCP client inside the hook scripts to talk to the
   vendor server over stdio/HTTP from a shell hook.

## Decision Outcome

Option 2.

Option 1 fails on the first driver alone -- hooks can't call MCP tools
regardless of what's configured -- and adds driver two's cost for the
cases (agentic tool-driven scanning) where it might otherwise help.

Option 3 solves nothing option 2 doesn't already solve more simply: it's
still a REST call under the hood (MCP-over-HTTP is JSON-RPC over HTTP), just
with an extra protocol layer and a dependency on an undocumented server
staying exactly as PAN's community repo describes it today.

### Consequences

- Good: the runtime hooks have exactly one dependency -- the documented
  Scan API -- verifiable against pan.dev.
- Good: no plugin-level `.mcp.json` means no connection-error noise for
  every user who installs the plugin but hasn't run setup yet.
- Good: the vendor MCP server remains available for the case it's actually
  suited to -- Claude invoking AIRS as a tool mid-conversation (UC-8-style
  ad hoc scanning) -- without being load-bearing for the always-on hooks.
- Bad: if the vendor MCP server disappears or changes shape, only the
  setup flow's optional offer is affected, not the hooks -- which is the
  point, but it does mean this plugin can't vouch for that server's
  long-term stability the way it can for the REST endpoints.
