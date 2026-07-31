---
id: 0001
title: Frameworks project onto an evidence-primitive layer
status: accepted
date: 2026-07-11
deciders: [thomas]
tags: [architecture, catalog]
---

## Context and Problem Statement

The auditor must support BSI IT-Grundschutz, the Cyber Resilience Act, GDPR and,
later, ISO 27001, NIS2, DORA. The obvious modularisation is one module per
framework. How should the framework catalogs be structured?

## Decision Drivers

- The technically checkable subsets of these frameworks overlap heavily.
- A verdict must be traceable to a single, reproducible check.
- New regulation arrives regularly and must not require re-implementation.

## Considered Options

1. One module per framework, each with its own checks.
2. A pivot framework (CIS Controls v8.1) that other frameworks map onto.
3. An own evidence-primitive layer; frameworks are n:m projections onto it.

## Decision Outcome

Option 3.

"TLS below 1.2 in transport config" satisfies BSI CON.1, ISO A.8.24, § 30 (2)
no. 8 BSIG, DORA RTS Art. 6 and Art. 32 (1)(a) GDPR at once. Option 1 implements
that check five times and produces five truths.

Option 2 was rejected on inspection: CIS *Controls* are programme-level
statements at the same abstraction as an ISO Annex A control, carrying the same
A/B/C split. As a pivot they move the problem up a level rather than solving it.
CIS publishes official mappings to NIS2, ISO 27001, SOC 2, NIST — but none to BSI
IT-Grundschutz, CRA, DORA or TISAX, which is precisely the part of the target
list that is hard. CIS *Benchmarks* are a different thing and are prüfobjekt-scoped,
but tools (trivy, prowler, kube-bench) emit their IDs anyway, so they are carried
as an optional `source_ref` on a finding and are not authoritative.

### Consequences

- Good: one implementation per check; a new framework is mapping work, not code.
- Good: a finding surfaces under every control it touches, visibly (see F-001 in
  the example run, which appears under both CON.1.A1 and Art. 32 (1)(a)).
- Bad: the mapping table is the thing that must be right, and it is the thing a
  model is most tempted to invent. Mitigated by 0002.

## Risk Assessment

| Option | Risk |
|---|---|
| 1 | Divergent verdicts across frameworks for the same underlying fact. High. |
| 2 | Pivot does not cover the frameworks that matter here. Wasted layer. |
| 3 | Mapping errors. Contained by the golden-run gate. |

## Audit

- Verified: CIS Controls Navigator lists mappings for NIS2, ISO 27001:2022,
  SOC 2, NIST CSF 2.0, PCI DSS, CMMC. No BSI, no CRA, no DORA, no TISAX.
- Verified: the example run demonstrates a single primitive serving two
  frameworks.
