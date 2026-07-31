---
id: 0004
title: catalog-watch runs as a locally-scheduled Claude Code command, not GitHub Actions
status: accepted
date: 2026-07-31
deciders: [thomas]
tags: [distribution, catalog, automation]
supersedes: []
---

## Context and Problem Statement

This plugin was consolidated from its own repository (`t11z/compliance-auditor`)
into a plugin marketplace monorepo (`nullthrone/claude-plugins`,
`plugins/compliance-audit/`). Its three GitHub Actions workflows were deleted in
that move — a `.github/workflows/` directory nested under a subdirectory is
never executed by GitHub, wherever it lives in the tree.

One of them, `catalog-watch.yml`, was not decoration: a weekly detection run
against the BSI/CRA/GDPR sources, feeding the `catalog-curator` subagent
(ADR 0002), which could open a PR or an issue but never merge. Losing it
silently reintroduces the exact failure mode ADR 0002 exists to prevent — a
catalog that goes stale without anyone finding out. How does the weekly run
come back?

## Decision Drivers

- The deleted workflow's `curate` job needed a GitHub App plus three repo
  secrets (`CLAUDE_CODE_OAUTH_TOKEN`, `APP_ID`, `APP_PRIVATE_KEY`) on what is
  now a public marketplace repository, not a single-purpose one.
- GitHub disables scheduled workflows after roughly 60 days of repository
  inactivity, and only real commits reset that clock — a quiet marketplace
  repo with only a weekly bot commit would eventually trip it, silently.
- A live probe of `.maintenance/scripts/watch.py` against the real sources (not
  fixtures) surfaced two defects that had nothing to do with CI at all: no
  default TLS trust store on this machine (`CERTIFICATE_VERIFY_FAILED` on every
  HTTPS fetch), and the `eurlex_html` extractor never stripping HTML before
  regex-matching article headings, so `cra-regulation`/`gdpr-regulation`
  produced one unusable whole-document diff instead of per-article segments.
  Both are fixed regardless of where the run executes, but they had to be
  found by actually running it — the committed baseline could not have
  revealed them; see below.
- The committed `.maintenance/state/sources.json` turned out to be a
  `pytest` artifact, not a real baseline: `test_gates.py`'s watcher tests
  deleted and overwrote the live state file against fixtures, and the
  committed file's `fetched_at` timestamps match the test's `--today`
  argument to the millisecond across all seven sources. Whatever ran this
  repo's CI never actually established a baseline against the live sources.

## Considered Options

1. Restore the three workflows verbatim at the repository root, namespaced.
2. Detect-and-issue only in GitHub Actions (no secrets), full curation done
   by hand.
3. A Claude Code cloud routine (`/schedule`).
4. A versioned Claude Code command (`.claude/commands/catalog-watch.md`),
   invoked weekly by a local Windows Task Scheduler entry.

## Decision Outcome

Option 4.

Option 1 reintroduces the App-plus-three-secrets surface on a public
marketplace repo for a single plugin's maintenance job, and does not survive
the 60-day inactivity auto-disable on a repo that otherwise sees light
traffic.

Option 2 gives up the actual point of ADR 0002 — a finished, reviewable PR
instead of a research task — for sources whose whole value is that a human
gets "PR #47: CON.1.A1 renumbered, verbatim diff attached" rather than "go
check whether BSI published something."

Option 3 (cloud routines) cannot see this repository at all in its current
form: routines clone from GitHub at the start of each run and have no local
filesystem access, so anything that depends on the developer's local
checkout is out. It remains a reasonable *future* option once the repo is
the sole source of truth and no local state is involved.

**The command is versioned; the scheduler entry is not.** The whole weekly
procedure — preflight, detect, triage, curator dispatch, local gates, PR/issue
creation, per-source state promotion, heartbeat — lives in
`.claude/commands/catalog-watch.md` at the marketplace root (not inside the
plugin: a command under `plugins/compliance-audit/commands/` would ship to
every consumer via auto-discovery, which ADR 0003 exists to prevent for
maintenance tooling). The Task Scheduler entry that fires it weekly is the
only part that is not in git, and it does nothing but invoke the command.

**Gates move from CI to local, and run after the commit, not before.** With
no CI, `check_catalog_bump.py`, `check_version_sync.py`,
`check_not_shipped.py`, the golden regression, and `pytest` all run inside
`/catalog-watch`, on the curator's own commit, before it pushes. Both bump
gates diff `base...HEAD`; run against an uncommitted working tree that diff
is empty and both silently report "no catalog changes" — the same defect
class fixed below, reintroduced by the wrong ordering.

**Two defects fixed as a precondition, not a follow-up.** Both
`check_catalog_bump.py` and `check_version_sync.py` compared
`git diff --name-only` output (repo-root-relative:
`plugins/compliance-audit/catalog/...`) against plugin-relative literals
(`catalog/...`), so `touched` was always empty and both gates silently always
passed once this plugin moved into the monorepo — proven with negative tests
(a change without a bump must exit 1) run from three different working
directories, not by observing a green run once. Fixed via `git rev-parse
--show-prefix`. See the corrections in ADR 0002 and ADR 0003 for the related,
pre-existing false verification claims this also surfaced.

**A locally-run curator still only proposes.** Root `.claude/settings.json`
denies `gh pr merge`, `gh pr review`, `git merge`, `git push --force`,
`git rebase`, and any edit under `.maintenance/golden/**` — the prose rule in
`catalog-curator.md` ("never touch golden/", "you are never the disposer")
is backed by something the model cannot argue past, the same way ADR 0002's
CI gates were meant to. This is voided if the scheduled invocation ever runs
with `--dangerously-skip-permissions`; it must not.

**The golden gate cannot currently fail, and the PR body must say so.**
Independent of this decision, `.maintenance/scripts/replay.py` is a stub that
copies `.maintenance/golden/expected-run.json` to its output verbatim,
regardless of the catalog under test — see the corrections added to ADR 0002
and ADR 0003. `/catalog-watch` and `catalog-curator.md` state
`golden regression: NOT MEANINGFUL (replay.py is a stub)` in every PR body
rather than "no verdict drift," because a gate that cannot fail is worse than
no gate when it is reported as if it were meaningful.

### Consequences

- Good: no GitHub App, no repo secrets, on a public repository.
- Good: the automation logic is versioned and auditable (the command file),
  even though the scheduler trigger itself is not.
- Good: the two live-fetch defects (TLS trust store, HTML-unaware extractor)
  are fixed rather than papered over by CI having always run on a platform
  where they did not surface.
- Bad: the schedule only fires while the desktop machine is on. Mitigated
  with Task Scheduler's "run as soon as possible after a missed start" and
  "wake to run" options, plus a `last-run.json` heartbeat committed on every
  run (including failures) and a zero-secret root
  `.github/workflows/heartbeat.yml` that opens an issue if it goes stale —
  the only layer that survives the machine being off, itself bounded by the
  same ~60-day inactivity auto-disable.
- Bad: a desktop scheduler cannot detect its own total absence; only that a
  heartbeat commit stopped arriving, and only if something reads for it.
  Accepted — no option considered removes this class of risk entirely, and a
  detectable silence is strictly better than the alternative of no automation
  and no signal either way.
- Bad: full automation (Option 4) needs a dedupe ledger and per-source state
  promotion that detect-and-issue-only would not have required — the CRA
  deadline at 2026-09-11, with `lead_time_days: 90`, would otherwise reopen a
  PR every week for roughly six weeks starting now. Accepted as the cost of
  keeping the original design's actual proposer/disposer value instead of
  degrading to Option 2.

## Risk Assessment

| Option | Risk |
|---|---|
| 1 | App + 3 secrets on a public repo; 60-day auto-disable on a quiet repo. Medium-high. |
| 2 | Degrades ADR 0002's core value; curation reverts to manual research. Medium. |
| 3 | No local filesystem access from a cloud routine; not viable yet. High (blocking). |
| 4 | Availability depends on the desktop machine being on. Medium, mitigated by heartbeat + catch-up scheduling. |

## Audit

- Verified: a read-only live probe (`watch.py` with no `--write-state`)
  against the real sources succeeded for 4/7 network sources before any fix,
  narrowing the two defects to TLS trust store and HTML extraction rather
  than a wholesale site-migration failure.
- Verified: with both fixes, all previously-unreachable BSI sources fetch
  successfully (one surfaces a genuine stale-URL 404, unrelated to the fix,
  logged separately), and `cra-regulation`/`gdpr-regulation` segment into 79
  and 99 real per-article/annex entries respectively instead of one raw-HTML
  document.
- Verified: `test_gates.py`'s watcher tests no longer touch
  `.maintenance/state/sources.json` — MD5 of the live state file identical
  before and after a full `pytest` run.
- Verified: `check_catalog_bump.py` and `check_version_sync.py` each exit 1
  on an unbumped catalog change and 0 once bumped, from three different
  working directories (repo root, plugin root, elsewhere).
