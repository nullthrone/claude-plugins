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
