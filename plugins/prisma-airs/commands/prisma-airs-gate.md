---
description: Scan prompt-shaped repository artifacts (or the staged diff) through Prisma AIRS and gate on the result -- always fails closed
argument-hint: "[--diff] [path ...]"
allowed-tools: Bash(python3:*), Read
---

Run `${CLAUDE_PLUGIN_ROOT}/scripts/gate.py` against the **current working
directory** (the project being gated, not the plugin) with the given
arguments: $ARGUMENTS

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate.py $ARGUMENTS
```

## What this scans

- **No arguments**: `CLAUDE.md`, `commands/**/*.md`, `skills/**/SKILL.md`,
  `agents/**/*.md` anywhere in the project -- the prompt-shaped files a
  poisoned contribution would edit to smuggle an instruction into every
  future session that loads this repo.
- **`--diff`**: `git diff --cached` -- catches secrets/PII/injection text
  about to be committed, using the same scan and `*_masked_data` the
  runtime hooks use.
- **Explicit paths**: exactly those files, nothing else.

## Reading the result

Exit code is the gate: `0` clean, `1` something was flagged (`alert` or
`block` from the AI security profile), `2` the scan itself could not be
completed (unreachable, HTTP error, misconfigured). This command is
**always fail-closed** regardless of the project's `.prisma-airs.json`
`on_unreachable` setting -- that setting only governs the runtime hooks. See
`${CLAUDE_PLUGIN_ROOT}/skills/prisma-airs-runtime/SKILL.md` for why the two
surfaces disagree on purpose.

Report the printed per-file verdicts to the user, don't just relay the exit
code. If exit code is `2` because the plugin isn't configured yet, point
them at `/prisma-airs-setup`.
