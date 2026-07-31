---
id: 0003
title: Ship as a Claude Code plugin; the plugin version is the catalog version
status: accepted
date: 2026-07-11
deciders: [thomas]
tags: [distribution, catalog]
---

## Context and Problem Statement

The auditor is meant to run in several projects. How is it distributed, and what
happens to the catalog when it is?

## Decision Drivers

- The catalog is the assessment basis. `catalog_version` in an audit run only
  means something if two projects on the same version hold the same catalog.
- ADR 0002 established that the catalog may only change through a reviewed PR.
  That guarantee must survive distribution.
- Claude Code copies a plugin into a cache on install. Anything written there is
  overwritten by the next `/plugin update`.

## Considered Options

1. Copy `.claude/` into every consuming project.
2. Ship as a plugin, everything included.
3. Ship as a plugin with a deliberate delivery cut; plugin version == catalog version.

## Decision Outcome

Option 3.

Option 1 produces n copies of the catalog that drift apart. `catalog_version`
becomes project-local, and the watcher from ADR 0002 would have to run in every
consuming repository — or it affects only the repository it happens to sit in.

Option 2 ships the `catalog-curator` into consumer caches. A curator running
there patches a cached catalog which the next update overwrites: the change is
gone, but the user believes it landed. This is a silent failure mode and the
reason for the delivery cut.

**Delivery cut.** `components` in `plugin.json` declares only `skills/`,
`agents/` (auditor only) and `commands/`. Everything under `.maintenance/` —
curator, watcher, gates, golden run, tests — is copied into the cache along with
the rest of the plugin root but is never *declared*, so Claude Code does not load
it. CI enforces that no `.maintenance/` path appears in `components`.

**Version coupling.** Any change under `catalog/` requires
`.claude-plugin/plugin.json:version` to advance. The report takes
`tooling.catalog_version` from the manifest. A release tag is therefore a
statement about the assessment basis, not merely about code.

**autoUpdate off.** A catalog that changes silently between two runs breaks the
reproducibility that the whole proposer/disposer apparatus of ADR 0002 exists to
protect. Consumers pin to a ref and update deliberately.

### Consequences

- Good: one catalog, one version, comparable across projects.
- Good: the curator cannot run where its work would be discarded.
- Bad: a catalog fix requires a release and a deliberate update in each consumer.
  Accepted — that is the same discipline the catalog itself is held to.
- Bad: `render.py` runs in a consumer project without a venv. Solved with a PEP
  723 header; `uv run` resolves dependencies itself.

## Risk Assessment

| Option | Risk |
|---|---|
| 1 | Catalog drift across projects. High, and invisible. |
| 2 | Curator writes into a cache; change silently discarded. High. |
| 3 | Release friction. Low, and intentional. |

## Audit

- Verified: CI rejects a `components` entry pointing into `.maintenance/`.
- Verified: CI rejects a change under `catalog/` without a manifest version bump.
- Verified: `render.py` resolves `${CLAUDE_PLUGIN_ROOT}` and falls back to its own
  location in a repo checkout.

## Correction (2026-07-31, see ADR 0004)

Both "Verified" claims above turned out to be false as read today, for two
different reasons — recorded here rather than silently edited, because an ADR
asserting a verification that did not hold is the same class of defect this
whole design exists to prevent.

1. **The `components` check never exercised anything.** `plugin.json` has
   never actually had a `components` key — this manifest relies entirely on
   Claude Code's default auto-discovery of `skills/`, `agents/`, `commands/`.
   The old CI step read `m.get("components", {})`, which was always empty, so
   `bad = []` unconditionally and the step always printed ok. It checked a
   field that was never populated, from the day this ADR was accepted.
   Replaced by `.maintenance/scripts/check_not_shipped.py`, which checks the
   fields the manifest actually uses and additionally scans what actually
   ships for any reference into `.maintenance/`.

2. **The version-bump gate silently always passed after this plugin was
   consolidated into a marketplace monorepo** (`nullthrone/claude-plugins`,
   `plugins/compliance-audit/`). `git diff --name-only` reports paths
   relative to the repo root; both `check_catalog_bump.py` and
   `check_version_sync.py` compared that output against plugin-relative
   literals (`catalog/mappings.yaml`, not
   `plugins/compliance-audit/catalog/mappings.yaml`), so `touched`/
   `catalog_touched` was always empty and both gates printed "no catalog
   changes" regardless of what changed. Fixed via `git rev-parse
   --show-prefix`; the fix is proven with negative tests (a change without a
   bump must exit 1) run from three different working directories, not just
   a green run — a script whose failure mode is silently-always-pass is not
   verified by observing that it passed once.

Neither gate runs in CI any more; see ADR 0004. Both run locally, as part of
`/catalog-watch`'s own commit, before it pushes.
