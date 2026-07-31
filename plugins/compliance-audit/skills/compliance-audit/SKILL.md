---
name: compliance-audit
description: Audits a codebase, its IaC and its runtime configuration against German and EU regulatory frameworks (BSI IT-Grundschutz, Cyber Resilience Act, GDPR, and further frameworks as projections). Produces a canonical JSON run and a deterministically rendered report. Use whenever someone asks for a compliance audit, a gap analysis against BSI/CRA/DSGVO/NIS2/ISO 27001, a check whether a repository or a cloud environment meets a regulatory requirement, or wants to know what evidence exists for a given control. Also trigger for "compliance check", "audit gegen BSI", "CRA-Konformität prüfen", "DSGVO-Gap-Analyse", "sind wir NIS2-konform". Do NOT use for a plain security review of code quality — that is security-audit-md.
---

# Compliance Audit

Judges a target against regulatory frameworks using only evidence that can
actually be collected. Produces no conformity statement, and cannot: the schema
has no field for it.

## The one thing to get right

The frameworks are not the primitives. A single check — "TLS below 1.2 in
transport config" — satisfies BSI CON.1, ISO A.8.24, § 30 (2) no. 8 BSIG, DORA
RTS Art. 6 and Art. 32 (1)(a) GDPR simultaneously. Implement it once, in
`catalog/primitives.yaml`. Frameworks are projections onto that layer, defined in
`catalog/mappings.yaml`. Anyone who implements the same check per framework ends
up with five truths.

## Evidence classes

| Class | Meaning | Who judges |
|---|---|---|
| A | deterministically checkable from repo, IaC, runtime config | the collector |
| B | requires interpretation (PII classification, data flows, adequacy) | the model, with mandatory `confidence` and evidence citation |
| C | organisational — training, contracts, processes, BCM exercises | nobody. `out_of_technical_scope`. |

Class C is not a gap in the tool. It is the boundary of what code can say. A
report that marks a training obligation as `pass` is worse than no report,
because § 30 BSIG comes with personal liability for management.

## Two phases, never one

**Phase 1 — Collection.** Run the collectors, write a frozen evidence bundle
(timestamp, query, raw response, hash). Read-only credentials only.

**Phase 2 — Verdict.** Judge exclusively against the bundle. Never re-query.

The same agent may do both. The point is that a verdict must still be defensible
six months later against a fixed snapshot. An agent that queries and judges in
the same breath cannot produce that.

## State is not enforcement

"All resources are currently in europe-west3" is a snapshot. `gcp.resourceLocations`
in dry-run mode prevents nothing. Set `enforcement` on every control. A conformant
state without enforcement is `partial`, never `pass`.

## Inherited evidence

"GCP is ISO 27001 certified" is a claim about a vendor, not evidence. It becomes
evidence only when all three hold:

1. the *specific service* is on the attestation's product scope list,
2. the attestation is still valid,
3. the complementary user entity controls are met.

Intersect the live service list (`gcloud asset search-all-resources`) with the
scope list. The delta is a finding. This is the check a human auditor usually
skips for effort reasons, and it is where the module earns its keep.

## Output

The agent produces **only** `schema/audit-run.schema.json`-conformant JSON. The
report is rendered from it by `scripts/render.py` — Jinja, no model in the path.
Same input, byte-identical output. Prose lives in schema fields
(`executive_summary`, `rationale`, `remediation.summary`), never in a separately
generated document.

- `--format md` — default for the slash command
- `--format json` — default in CI
- exit 2 on `insufficient_evidence` or a failed collector. **Never green.**

## Reference material

Load only what the requested framework needs.

- `${CLAUDE_PLUGIN_ROOT}/catalog/primitives.yaml` — the checks
- `${CLAUDE_PLUGIN_ROOT}/catalog/mappings.yaml` — framework → control → primitive
- `${CLAUDE_PLUGIN_ROOT}/catalog/sources.yaml` — what the watcher observes, and what it deliberately does not
- `${CLAUDE_PLUGIN_ROOT}/schema/audit-run.schema.json` — the only artefact you produce

## You are running from a cache

When installed as a plugin, `${CLAUDE_PLUGIN_ROOT}` is a cache directory that
`/plugin update` overwrites. Read from it. Never write to it. Evidence bundles,
runs and reports belong in the audited project under `.compliance/`.

The catalog is maintained in the plugin's own repository — detected by
`watch.py`, proposed by the `catalog-curator`, disposed by a human. Editing the
catalog during an audit would be lost on the next update and would make
`catalog_version` a lie in the meantime. `tooling.catalog_version` comes from
`.claude-plugin/plugin.json`: the plugin version *is* the catalog version.
