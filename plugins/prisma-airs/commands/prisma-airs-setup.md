---
description: Guided onboarding for Prisma AIRS -- prerequisites, region, key handling, security profile, a verified test scan, and optional runtime hooks
argument-hint: "[--region us|de|in|sg] [--profile <name>] [--enable-hooks] [--mcp]"
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(git:*), AskUserQuestion
---

Run the `prisma-airs-setup` skill against the **current working directory** --
the project being protected, not the plugin.

Arguments: $ARGUMENTS

This is a guided conversation, not a script to run silently. Follow
`${CLAUDE_PLUGIN_ROOT}/skills/prisma-airs-setup/SKILL.md` step by step, asking
the user wherever it says to ask -- especially the data-flow disclosure and
the key-handling choice. Do not skip either just because arguments were given;
arguments pre-fill the answer, they don't remove the confirmation.
