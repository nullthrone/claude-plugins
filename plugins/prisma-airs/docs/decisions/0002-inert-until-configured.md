---
id: 0002
title: hooks are inert (exit 0, no network call) until .prisma-airs.json and an API key both exist
status: accepted
date: 2026-07-31
deciders: [thomas]
tags: [architecture, hooks, safety]
supersedes: []
---

## Context and Problem Statement

Palo Alto's own community reference hooks
(`claude-code-hooks/hooks/scan-user-input.sh`) fail closed when
unconfigured: *"All hooks block (exit 2) when `PRISMA_AIRS_API_KEY` or
profile is not set."* That's a defensible choice for a hand-installed,
single-user, global hook set someone deliberately wired into
`~/.claude/hooks/`. This plugin ships to a public marketplace and installs
its `hooks/hooks.json` unconditionally the moment the plugin is enabled --
before `/prisma-airs-setup` has necessarily run. Should an unconfigured
installation block every prompt and tool call, or let them through?

## Decision Drivers

- Someone can install a marketplace plugin out of curiosity, or because a
  teammate recommended it, without immediately running its setup flow.
  Blocking their session entirely on day one is a hostile first impression
  for a security tool, and likely to get the plugin uninstalled rather than
  configured.
- `docs/decisions/0001` already establishes that hooks call the Scan API
  directly with no MCP fallback -- there's no secondary path that could
  degrade gracefully; "can't reach AIRS" and "never configured AIRS" need
  different treatment, and this decision is specifically about the second.
- The hooks and `/prisma-airs-gate` do not need the same answer here: a CI
  gate that someone deliberately wires in has already opted in explicitly,
  the way PAN's reference hooks' installer does.

## Considered Options

1. Match PAN's reference: fail closed (exit 2 / deny) whenever
   `.prisma-airs.json` or the API key is missing.
2. Fail open silently: exit 0, no output, no network call, whenever
   unconfigured.
3. Fail open, but with a one-time, session-level warning the first time a
   hook fires unconfigured.

## Decision Outcome

Option 2 for the runtime hooks; option 1 (always fail closed) for
`/prisma-airs-gate`, since that command is invoked deliberately, not
installed passively.

Option 1 for the hooks would mean every Bash command, every prompt, every
Write blocks outright for anyone who installs this plugin without reading
the README first -- a correctness cost far larger than the security benefit
of "at least it's obviously broken," since the actual failure mode is
"nothing works," not "something insecure happens."

Option 3 was close, but a warning requires the hook to produce *some*
stdout/stderr on every single tool call and prompt for a project that has
simply chosen not to use this plugin's runtime protection (configured
`.prisma-airs.json` absent is also the steady state for anyone who only
wants `/prisma-airs-gate` in CI and none of the runtime hooks) -- that's
noise for a state that isn't actually a problem.

### Consequences

- Good: installing this plugin has zero behavioral effect until
  `/prisma-airs-setup` deliberately turns it on -- matches how the other
  marketplace plugin here (`compliance-audit`) behaves: present but
  passive until invoked.
- Good: `load_config_or_exit()` in `hook_common.py` is the single place
  this gate lives; every hook script calls it first, so the policy can't
  drift between the four hook scripts.
- Bad: a project that intends to run scanned but has a broken
  `.prisma-airs.json` (e.g. a typo making `is_configured()` false) fails
  the same way as "never configured" -- silently. Mitigated by
  `/prisma-airs-setup`'s explicit test-call step, which is the actual
  place this should be caught, not by the hooks trying to distinguish
  "misconfigured" from "not yet configured" at runtime.
