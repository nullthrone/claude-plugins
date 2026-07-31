---
id: 0003
title: gate on the response's `action`, treating anything but exactly allow/block (including alert) as alert
status: accepted
date: 2026-07-31
deciders: [thomas]
tags: [architecture, api-contract, safety]
supersedes: []
---

## Context and Problem Statement

pan.dev's `ScanResponse.action` field is documented with exactly two
values: `"allow"` and `"block"`. Palo Alto's own community Claude Code
skill (`claude-code-skill/SKILL.md`, in the same reference-integrations
repo as ADR 0001's MCP server) documents a third value it actually
interprets, `"alert"` -- *"Review findings before proceeding."* Two primary
sources partially disagree on the contract. What should every caller in
this plugin (`hook_prompt.py`, `hook_pretool.py`, `hook_posttool.py`,
`hook_stop.py`, `gate.py`) do when `action` is something other than exactly
`"allow"` or `"block"`?

## Decision Drivers

- Silently treating an unrecognized `action` value as `"allow"` is the
  failure mode that matters most to avoid in a security-scanning plugin:
  if the API ever adds a fourth value, or if `"alert"` is in fact live in
  production tenants today (pan.dev's silence on it doesn't mean it can't
  occur), code that only checks `if action == "block"` would let it
  through with no signal at all.
- Every hook event Claude Code exposes already has a middle option between
  "let it through silently" and "block outright": `additionalContext` for
  the prompt/response-shaped events, and `permissionDecision: "ask"` for
  `PreToolUse` -- so there's no need to force a binary choice.
- `/prisma-airs-gate` is a CI gate; CI gates conventionally have binary
  exit semantics, but "something needs a human look" and "clean" are not
  the same outcome and shouldn't share an exit code either.

## Considered Options

1. Only branch on `action == "block"`; everything else (including
   `"alert"`, and any future value) is treated as allow.
2. Branch on exactly the two pan.dev-documented values; treat any other
   value, including `"alert"`, as an error condition (fail per
   `on_unreachable`, or fail the gate).
3. Introduce a third bucket -- `classify_action()` returns `allow`/
   `alert`/`block`, where `alert` covers pan.dev's undocumented value
   *and* anything else not exactly `"allow"` or `"block"` -- and give each
   event type its own non-silent, non-blocking treatment for `alert`.

## Decision Outcome

Option 3 (`hook_common.classify_action()`).

Option 1 is the exact silent-allow failure mode the first decision driver
names -- rejected outright regardless of whether `"alert"` is common in
practice.

Option 2 makes `/prisma-airs-gate` fail on `"alert"` in a way
indistinguishable from an actual outage on the results, which pan.dev's
own documented value set doesn't even predict will happen -- and would
mean this plugin can't handle Palo Alto's own currently-shipping community
skill's response value without an operator seeing it as a hard failure.

Decision, per event:

| `action` | UserPromptSubmit | PreToolUse | PostToolUse / Stop | `/prisma-airs-gate` |
|---|---|---|---|---|
| `allow` | through | `defer` | through | exit 0 |
| `alert` (or unrecognized) | through + `additionalContext` warning | `permissionDecision: ask` | `additionalContext`/log warning | exit 1 (reported, not silent) |
| `block` | `decision: block` | `permissionDecision: deny` | `decision: block` | exit 1 |

### Consequences

- Good: an unrecognized future `action` value degrades to the same
  handling as `"alert"` -- visible, not silently permissive -- everywhere
  in this plugin, in one function (`classify_action()`), rather than
  needing every hook to reimplement the same defensiveness.
- Good: `/prisma-airs-gate` reports `alert` and `block` both as non-zero
  (distinguished in its printed output, not its exit code), so a CI
  pipeline that just checks the exit code still stops for either.
- Bad: `alert` and `block` collapse to the same exit code in
  `/prisma-airs-gate`, so a CI system that wants to treat "needs review"
  differently from "hard stop" has to parse the printed text, not the
  exit code, to tell them apart. Accepted: CI gates conventionally have
  one bit of signal (pass/fail), and a human is expected to read the gate
  output either way once it's non-zero.
