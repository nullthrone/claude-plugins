---
name: prisma-airs-setup
description: Guides a project from zero to a verified Prisma AIRS (AI Runtime Security) scan -- prerequisites, region choice, an explicit data-flow disclosure, a key-handling decision left to the user, security profile resolution, a positive and negative test call, and (opt-in) writing .prisma-airs.json plus enabling runtime hooks or the vendor MCP server. Use whenever someone asks to set up, onboard, configure or connect Prisma AIRS, AIRS, or Palo Alto AI Runtime Security in a project. Also trigger for "prisma-airs-setup", "set up AI security scanning", "onboard AIRS", "connect Strata Cloud Manager". Do NOT use this to actually scan content -- that is prisma-airs-runtime, the hooks, or /prisma-airs-gate.
---

# Prisma AIRS Setup

Takes a project from nothing to a verified call against
`POST /v1/scan/sync/request`. This is a conversation with real decisions in
it, not a script to run unattended -- two of the steps below (data-flow
disclosure, key handling) must be put to the human, not assumed.

## Before starting

State plainly, once, near the top of the conversation: **this plugin sends
prompt text, tool inputs, and tool outputs to an external Palo Alto Networks
service for scanning.** That is the entire point of it, and it is also a
data-flow decision the project's owner should make consciously, not discover
later in a log file. If they don't want that, stop here -- there's nothing
else this skill can offer them.

## 1. Prerequisites

Confirmed on
[pan.dev](https://pan.dev/prisma-airs/api/airuntimesecurity/airuntimesecurityapi/),
in order:

1. A Prisma AIRS AI Runtime API Intercept **deployment profile**, created in
   the Customer Support Portal. This is also where the **region** gets fixed
   -- it cannot be changed per request afterwards.
2. AIRS onboarded in **Strata Cloud Manager**.
3. In Strata Cloud Manager: **AI Security → API Applications → Manage**:
   - **API Keys** -- generate/copy the key (`x-pan-token`).
   - **Security Profiles** -- the profile name or ID that goes in
     `ai_profile`. This profile is where prompt-injection/DLP/toxic-content/
     etc. detectors and their block-vs-allow-vs-alert actions actually live;
     this plugin does not configure the profile itself, only calls it.
   - **Custom Topics**, if custom topic guardrails are wanted (out of scope
     for this skill; do in Strata Cloud Manager).

Ask the user to confirm they have a deployment profile and a security
profile name before continuing. If they don't, point them at the console
path above and stop -- there is nothing to test yet.

## 2. Region

Ask which region the deployment profile was created in.

| Region | Base URL |
|---|---|
| `us` (default) | `https://service.api.aisecurity.paloaltonetworks.com` |
| `de` (EU) | `https://service-de.api.aisecurity.paloaltonetworks.com` |
| `in` | `https://service-in.api.aisecurity.paloaltonetworks.com` |
| `sg` | `https://service-sg.api.aisecurity.paloaltonetworks.com` |

If the user cares about EU data residency for the scan traffic itself
(prompts and tool content leaving the project), `de` is the one that keeps
it in Germany -- surface that explicitly rather than defaulting silently to
`us`.

## 3. Key handling -- ask, don't decide

Do not pick this for the user. Lay out the options and their consequences,
then let them choose:

1. **Environment variable only (recommended default).** Nothing is written
   to disk by this skill. The user sets `PRISMA_AIRS_API_KEY` in their own
   shell profile or secret manager. `.prisma-airs.json` never contains a
   key. Safest, and the only option that guarantees the key can't end up in
   a commit.
2. **Local `.env` file.** This skill can write `PRISMA_AIRS_API_KEY=...` to
   a `.env` in the project root and add `.env` to `.gitignore` (creating
   `.gitignore` if absent, appending if present and not already covering
   it). More convenient, but the key sits in plaintext on disk.
3. **OS keychain / secret manager.** Point the user at their platform's tool
   (e.g. `security add-generic-password` on macOS, a password manager CLI,
   a cloud secret manager) and have them export the key into the shell
   environment from there before running Claude Code. This skill does not
   automate that step -- it varies too much by platform to script safely.

Whichever they choose, **never** write the key into `.prisma-airs.json`,
never echo it back in chat, and never let it reach the audit log (the hook
scripts already guarantee this; don't undo it here by printing the key
during setup for "confirmation" -- confirm via the test call instead).

## 4. Write `.prisma-airs.json`

Committable, contains no secret. Ask the profile name (or ID) and write:

```json
{
  "region": "<chosen region>",
  "profile_name": "<the security profile name>",
  "app_name": "claude-code",
  "hooks": {
    "user_prompt_submit": true,
    "pre_tool_use": true,
    "post_tool_use": true,
    "stop": false
  },
  "tool_matcher": "Bash|Write|Edit|WebFetch|WebSearch|mcp__.*",
  "on_unreachable": { "user_prompt_submit": "allow", "pre_tool_use": "ask" },
  "timeout_seconds": 5,
  "max_content_chars": 20000,
  "audit_log": ".prisma-airs/audit.jsonl"
}
```

Explain the two defaults worth calling out:

- **`stop: false`** -- the hook that would scan Claude's final response text
  is off by default. pan.dev documents no latency guarantee for the scan
  API, and this hook sits on the critical path of every turn ending. Offer
  to turn it on if the user wants response-content coverage and accepts the
  latency trade-off.
- **`on_unreachable`** -- what happens when AIRS *doesn't answer at all*
  (network error, timeout, 429, 5xx). pan.dev has no guidance here; these are
  this plugin's own defaults (allow-through-with-a-warning for prompts,
  human-confirm for tool calls), not a Palo Alto recommendation. Say so.

Also ensure `.prisma-airs/` (the audit log directory) is covered by
`.gitignore` -- it's a local operational log, not something to commit.

## 5. Verify with a real call, not just credential shape

Run both of these via the plugin's own client, `scan_once.py` (stdlib only,
no extra install):

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_once.py --content "hello, just checking connectivity"
```

Expect `"verdict": "allow"`. This confirms auth, region, and profile
resolution all work.

Then a **negative** test, using the exact string pan.dev's own Python SDK
usage example scans:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_once.py --content "This is a test prompt with urlfiltering.paloaltonetworks.com/test-malware url"
```

Expect `"action"` to be `"block"` or `"alert"`, not `"allow"` -- if the
security profile has malicious-URL detection enabled. If it still comes
back `allow`, say so plainly: either the profile doesn't have that detector
on, or something's misconfigured. Don't report success on the positive test
alone; an API key that authenticates but hits a profile with nothing
enabled would pass a connectivity check and still catch nothing at runtime.

If either call fails, diagnose from the status:

| Symptom | Likely cause |
|---|---|
| Connection error / timeout | Wrong region base URL, or a network egress block on this host |
| `401` | Missing/empty API key |
| `403` | Invalid, revoked, or expired API key |
| `400`, "profile name" | Profile name misspelled, or wrong TSG/tenant |

## 6. Optional: runtime hooks are already wired, just gated

The plugin's `hooks/hooks.json` is always installed once the plugin is
enabled -- but every hook script checks `.prisma-airs.json` + the API key
first and exits silently if either is missing (see
`docs/decisions/0002-inert-until-configured.md`). Writing the config file in
step 4 is what turns them on. Nothing further to do here except confirm the
user understands this, and mention `/prisma-airs-gate` for CI-time scanning
of prompt-shaped repository files (`CLAUDE.md`, skills, commands, agents) --
a different, always-fail-closed surface from the runtime hooks.

## 7. Optional: the vendor MCP server

Palo Alto Networks publishes an MCP server for AIRS (not documented on
pan.dev; only in their reference integrations repo). This plugin does not
ship it as a bundled `.mcp.json` -- see
`docs/decisions/0001-rest-not-vendor-mcp-in-hooks.md` for why. If the user
wants Claude to be able to invoke AIRS scanning as a tool during
conversation (rather than only via the always-on hooks), offer to add this
to the **project's** `.mcp.json` -- ask first, since it's a new outbound
connection carrying the API key in a header:

```json
{
  "mcpServers": {
    "prisma-airs": {
      "type": "http",
      "url": "https://service.api.aisecurity.paloaltonetworks.com/mcp",
      "headers": {
        "x-pan-token": "${PRISMA_AIRS_API_KEY}",
        "x-pan-profile": "${PRISMA_AIRS_PROFILE_NAME}"
      }
    }
  }
}
```

Swap the URL's host for the chosen region if not `us`. Note plainly to the
user: this specific integration point is sourced from Palo Alto's community
repository, not from pan.dev itself -- flag it as such rather than presenting
it with the same confidence as the REST endpoints above.

## 8. Summary

Close with a short recap: region, profile, which hooks are on, where the
audit log lives, and the one-line reminder that `/prisma-airs-gate` and
`/prisma-airs-mcp-audit` are separate, on-demand surfaces -- setup doesn't
run them automatically.
