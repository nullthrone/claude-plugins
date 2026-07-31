---
description: Audit this repository against BSI IT-Grundschutz, CRA and GDPR
argument-hint: "[--framework bsi-grundschutz,cra,dsgvo] [--scope code,iac,runtime] [--format md|json|both]"
allowed-tools: Read, Grep, Glob, Bash(uv:*), Bash(python:*), Bash(gcloud:*), Bash(checkov:*), Bash(syft:*), Bash(grype:*), Bash(semgrep:*)
---

Run the `compliance-audit` skill against the **current working directory** — the
project being audited, not the plugin.

Arguments: $ARGUMENTS

## Paths

You are running from a plugin cache. The distinction matters:

- Catalog, schema, templates and the renderer: `${CLAUDE_PLUGIN_ROOT}/...`
- Target, evidence bundle, outputs: the current working directory, under
  `.compliance/`

Never write into `${CLAUDE_PLUGIN_ROOT}`. It is a cache and is overwritten on the
next `/plugin update`. Anything written there is silently lost, and the user will
believe it is still present.

## Procedure

1. Read `${CLAUDE_PLUGIN_ROOT}/catalog/mappings.yaml` — only the requested
   frameworks. The whole catalog does not belong in context.
2. **Phase 1 — collect.** Run collectors, write a frozen bundle to
   `.compliance/evidence/<id>/` with timestamp, query, raw response, hash.
   Read-only credentials. If the credentials are not read-only, stop and say so.
3. **Phase 2 — judge.** Against the bundle only. Do not re-query.
4. Emit JSON conforming to `${CLAUDE_PLUGIN_ROOT}/schema/audit-run.schema.json`.
   Set `tooling.catalog_version` from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`
   — the plugin version *is* the catalog version.
5. Render:
   ```
   uv run ${CLAUDE_PLUGIN_ROOT}/scripts/render.py .compliance/run.json \
       --format ${FORMAT:-md} --out .compliance/report
   ```
   Do not write a report by hand. Two artefacts drifting apart is worse than one.

## The five that get dropped

1. Coverage before results. How many controls were out of technical scope, then
   how many passed.
2. No conformity statement. The schema has no `compliant` field; do not invent
   one in prose either.
3. A failed collector is `insufficient_evidence` and exit 2. Never a pass.
4. State is not enforcement. A resource that happens to sit in the EU is not a
   policy preventing it from leaving.
5. A vendor certificate is not evidence until the specific service is on its
   product scope list.
