---
id: 0002
title: The catalog is never self-mutating
status: accepted
date: 2026-07-11
deciders: [thomas]
tags: [architecture, catalog, safety]
supersedes: []
---

## Context and Problem Statement

Regulatory content moves. Keeping the catalog current by hand is error-prone
busywork. Can the skill update its own catalog automatically?

## Decision Drivers

- `catalog_version` exists so that a verdict is reproducible. If a run said
  `pass` in March and `fail` in July, it must be recoverable whether the code
  changed or the catalog did.
- A model deriving a requirement from a PDF diff and writing it straight into
  the catalog will eventually invent a norm that does not exist — and then report
  it as `fail` against real code, with a citation and an evidence reference.
  That failure does not look like a bug. It looks like evidence.
- The GDPR's text has not moved since 2016; its interpretation moves constantly.
  A text-diff watcher is blind to a falling adequacy decision.

## Considered Options

1. Fully automatic: watcher writes the catalog, opens no PR.
2. No automation: humans re-read the sources periodically.
3. Split: deterministic detection, model-assisted proposal, human disposal.

## Decision Outcome

Option 3.

Detection (`scripts/watch.py`) is LLM-free: fetch, hash, diff at building-block
granularity. It establishes *that* something moved and *where*, never what it
means. The `catalog-curator` subagent interprets and may only open a pull
request. Two CI gates constrain it: a catalog change without a version bump is
rejected, and the catalog is replayed against a frozen evidence bundle so that
any verdict flipping without the evidence changing has to be explained in the PR.

The objection "that is just busywork again" does not hold: the human does not
receive a research task but a finished, source-cited diff with impact analysis
and a regression result. "Check whether BSI published something" versus "PR #47:
CON.1.A1 renumbered in the 2026 edition, verbatim diff attached, affects 2
primitives and 3 mappings, golden run shows 0 verdict changes — merge or close."

### Consequences

- Good: `catalog_version` stays meaningful; every past verdict stays defensible.
- Good: a hallucinated requirement is caught by the golden run before merge.
- Bad: catalog updates are not instantaneous. Accepted — a stale catalog is
  visible (`catalog_staleness_days`), an invented one is not.
- Bad: licensed frameworks (ISO 27001, VDA ISA) cannot be watched at all.
  Documented in `catalog/sources.yaml` under `excluded`.

## Risk Assessment

| Option | Risk |
|---|---|
| 1 | Model invents a requirement; it is reported as evidence. Catastrophic and silent. |
| 2 | Catalog drifts; findings become wrong quietly. High, but visible. |
| 3 | PR backlog if nobody reviews. Low; the staleness field surfaces it. |

## Audit

- Verified: golden-run gate catches a simulated catalog hallucination
  (`out_of_technical_scope` -> `pass` on an organisational control) and exits 1.
- Verified: watcher is idempotent across identical inputs, detects a
  building-block-level change, and emits the changed passage verbatim.
- Verified: an unreachable source exits 2 and opens an issue rather than being
  treated as "no changes".
