---
description: Weekly compliance-audit catalog-watch runbook — detect regulatory drift, propose PRs/issues via the catalog-curator, gate locally, never merge
argument-hint: "[--fixtures <dir>] [--record <path>] [--today <iso>] [--dry-run]"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git:*), Bash(gh:*), Bash(python:*), Bash(*/venv/Scripts/python.exe:*)
---

This is the maintenance runbook for the `compliance-audit` plugin
(`plugins/compliance-audit/`). It replaces the `catalog-watch.yml` GitHub
Actions workflow deleted during consolidation into this marketplace — see
`plugins/compliance-audit/docs/decisions/0004-local-scheduled-catalog-watch.md`
for why this now runs as a scheduled local command instead of CI.

It lives at the marketplace root, not inside the plugin, deliberately: a
command under `plugins/compliance-audit/commands/` would ship to every
consumer via auto-discovery, which
`plugins/compliance-audit/docs/decisions/0003-ship-as-plugin-version-is-catalog-version.md`
exists to prevent for maintenance tooling. This file is the only place the
weekly procedure is written down — the scheduler entry that invokes it does
nothing but call `claude -p "/catalog-watch"`.

Arguments: $ARGUMENTS — pass-through flags for offline/manual runs:
- `--fixtures <dir>` — read sources from a fixture directory instead of the network (see Phase 2)
- `--record <path>` — skip detection and triage this pre-built change-record instead (for change kinds fixtures cannot produce, e.g. `edition_rollover`)
- `--today <iso>` — override the date used for deadline checks
- `--dry-run` — run Phases 0–3 and print what would happen; do not create branches, commits, PRs, or issues, and do not promote state or write the heartbeat

**You are the only thing standing between a curator mistake and a merged PR.**
You may open pull requests and issues. You may never merge, approve, rebase,
or force-push. This is also enforced by `deny` rules in the root
`.claude/settings.json` — if this session is ever invoked with
`--dangerously-skip-permissions`, that enforcement is void, so it must not be.

## Phase 0 — preflight

1. `PLUGIN_DIR = plugins/compliance-audit` (relative to the repo root).
   Determine the repo root with `git rev-parse --show-toplevel` and use
   **absolute paths** built from it throughout — do not assume the invocation
   cwd. `watch.py`'s `--out`, `--fixtures`, `--state-out` are all resolved
   against cwd, not against the plugin, and a scheduled headless invocation's
   cwd is not guaranteed.
2. Create a fresh scratch directory for this run under the OS temp directory
   (e.g. `mktemp -d`, or `%TEMP%\catalog-watch-<timestamp>` on Windows). All
   intermediate files (`record.json`, `candidate-state.json`) go there —
   never into the repo working tree, and never into `.compliance/` (that is
   the audited-project output path, unrelated to this).
3. Locate the venv at `%USERPROFILE%/.claude-tools/catalog-watch/venv`
   (`~/.claude-tools/catalog-watch/venv` on macOS/Linux). If
   `Scripts/python.exe` (or `bin/python`) does not exist, bootstrap it:
   ```
   python -m venv <venv-dir>
   <venv-dir>/Scripts/pip install -r plugins/compliance-audit/.maintenance/requirements.txt
   ```
   Do not re-run `pip install` on every invocation once the venv exists —
   check for the interpreter first.
4. **Import preflight.** Run
   `<venv-python> -c "import yaml, pdfplumber, jsonschema, jinja2, certifi"`.
   If this fails, stop and report a `preflight-failed` incident (see Phase 6)
   — do not let a broken venv masquerade as an unreachable regulatory source.
5. `gh auth status` must succeed with a token that has `write` access to this
   repo. `git fetch origin`. Assert a clean worktree
   (`git status --porcelain` empty) before doing anything else — a headless
   run in a tree with uncommitted local work must not sweep that work into a
   curator commit. If the worktree is dirty, stop and report an incident.

## Phase 1 — reconcile

Read `plugins/compliance-audit/.maintenance/state/handled.json` (create it as
`{}` if absent — first run). For every entry with `disposition: "open"`, check
its current state via `gh pr view <number>` / `gh issue view <number>` and
update `disposition` to `merged`, `closed` (treat as `rejected`), or leave
`open`. Write the file back. This is what makes Phase 3's dedupe possible —
without it, a human's deliberate "no, this doesn't affect us" close would be
re-proposed by the next run.

## Phase 2 — detect

Unless `--record` was given:

```
<venv-python> plugins/compliance-audit/.maintenance/scripts/watch.py \
    --out <scratch>/record.json \
    --state-out <scratch>/candidate-state.json \
    [--fixtures <dir>] [--today <iso>]
```

Do **not** pass `--write-state` here — the live baseline is only ever updated
by Phase 5's per-source promotion, never as a side effect of detection.

Exit code 2 means one or more sources were unreachable; the record is still
emitted (`unreachable` and `changes` are not exclusive — handle both in
Phase 3). Exit code 3 is a config error in `catalog/sources.yaml` itself —
treat as an incident, same as a preflight failure.

## Phase 3 — triage

Key on each change's `kind`, nothing else:

| `kind` | Artifact | Labels | Promote on |
|---|---|---|---|
| (any) `unreachable[]` entry | one issue for the whole run | `catalog`, `watch-failure` | — |
| `publication` | **issue, never PR** | `catalog`, `needs-domain-decision` | `main`, immediately |
| `edition_rollover` | PR (curator relocates URL + re-baselines) | `catalog` | the PR branch, on merge |
| `segment_modified` / `segment_added` / `segment_removed` | PR, one per source | `catalog` (+ `needs-domain-decision` if the curator sets `unclear`) | the PR branch, on merge |
| `deadline_approaching` / `deadline_passed` | PR (mechanical severity boost) | `catalog` | ledger only — no source state to promote |
| `baseline_established`, and the live baseline already exists | **error issue**, not a benign no-op | `catalog`, `watch-failure` | — |
| nothing changed, nothing unreachable | heartbeat only: `chore(watch): baseline unchanged <date>` | — | all reachable sources, on `main` |

An unexpected `baseline_established` (i.e. the committed
`.maintenance/state/sources.json` already has an entry for that source) means
the state file went missing or was overwritten out of band — this is exactly
the failure signature that produced the poisoned baseline this repo shipped
with before ADR-0004 (see its Context section). Treat it as an incident, not
as "no prior state, nothing to do."

For every change (except pure heartbeat), compute a fingerprint:
`sha256(source_id | kind | segment_id | hash_after-or-deadline-date)` and
check it against `handled.json` from Phase 1. Skip anything whose disposition
is `open`, `merged`, `rejected`, or `resolved` — it has already been acted on
or explicitly declined.

If `--dry-run`: print the full triage plan (what would be opened, for which
sources, against which fingerprints) and stop here.

## Phase 4 — propose

For each undeduped change requiring a PR:

1. Branch name: `catalog-watch/<source_id>`, deterministic — no searching. If
   the branch already exists on `origin` with an open PR, push updates to it
   instead of creating a duplicate.
2. Dispatch to the `catalog-curator` role exactly as documented in
   `plugins/compliance-audit/.maintenance/agents/catalog-curator.md` — read
   that file and follow it verbatim; do not paraphrase its rules. It is the
   single copy of those rules; nothing here overrides it.
3. The curator edits the catalog and **commits**. Only after the commit
   exists, run the gates, in order, from `plugins/compliance-audit/`:
   ```
   <venv-python> .maintenance/scripts/check_catalog_bump.py origin/main
   <venv-python> .maintenance/scripts/check_version_sync.py origin/main
   <venv-python> .maintenance/scripts/replay.py .maintenance/golden/bundle-ref --out <scratch>/actual-run.json
   <venv-python> .maintenance/scripts/golden_diff.py <scratch>/actual-run.json
   <venv-python> .maintenance/scripts/check_not_shipped.py
   <venv-python> -m pytest .maintenance/tests -q
   ```
   **Running the gates before the commit exists is a guaranteed silent
   pass** — both bump gates diff `base...HEAD`, which is empty against
   uncommitted changes. If any gate fails, do not push; fix and re-commit, or
   abandon the branch and report an incident.
4. State the golden result honestly in the PR body:
   `golden regression: NOT MEANINGFUL (replay.py is a stub, see docs/decisions/0004)`
   — never "no verdict drift." `replay.py` cannot currently detect a flip
   regardless of what changed; see the corrections in ADR-0002 and ADR-0003.
5. Push the branch, `gh pr create` with the curator's PR body, apply labels
   from the table above. Record the fingerprint → `{artifact: "pr", number,
   opened_at, disposition: "open"}` in `handled.json`.
6. For `publication` changes: `gh issue create` instead, body containing the
   **complete** evidence (URL, `doc_sha256` before/after, `triage_hint`,
   `relevant_controls`) — this issue is the durable record and closing it is
   the only act that disposes of it, so it must not depend on anything
   ephemeral. Record the fingerprint with `artifact: "issue"` and promote
   that source's state on `main` immediately (see Phase 5).
7. For `unreachable[]`: one issue for the whole run, labels
   `catalog`, `watch-failure`, listing every unreachable `source_id` and its
   error. Do not promote state for those sources.

## Phase 5 — promote

Per-source state promotion, never whole-file:

```
<venv-python> plugins/compliance-audit/.maintenance/scripts/promote_state.py \
    <scratch>/candidate-state.json <source_id> [<source_id> ...]
```

- `segment_modified`/`segment_added`/`segment_removed`/`edition_rollover`
  sources promote **only when their PR merges** — not now. Since you cannot
  merge, this means: do not promote these now. A separate, human-triggered
  step promotes them after merge (document this in the PR body: "after
  merging, promote with `promote_state.py <candidate> <source_id>`" — but
  note the candidate file lives in a scratch directory that will not exist by
  then, so in practice a human re-runs detection or uses the PR's recorded
  hashes; do not overpromise a one-command merge-time promotion this runbook
  cannot itself perform).
- `publication` sources promote immediately, on `main`, at issue-creation
  time — there is no PR branch to carry it, and the alternative is refiling
  the same issue every week.
- Sources with no change and no error: promote immediately, on `main` — only
  `fetched_at` moves, and this commit doubles as liveness evidence.
- `unreachable` sources: never promote.

Commit any `main`-branch promotions together:
`git commit -m "chore(watch): promote state for <source_ids>"`. This must be
a **direct commit to `main`**, not a PR — it is mechanical, and it is the one
kind of catalog-adjacent write this command performs directly (it touches
state, never `catalog/` content itself).

## Phase 6 — heartbeat

**Always runs, including after an incident in any earlier phase.** Write
`plugins/compliance-audit/.maintenance/state/last-run.json`:

```json
{
  "started_at": "<iso>",
  "finished_at": "<iso>",
  "trigger": "scheduled",
  "watch_exit_code": <int>,
  "status": "ok" | "incident",
  "unreachable": ["<source_id>", ...],
  "artifacts": [{"kind": "pr"|"issue", "number": <int>, "source_id": "<id>"}, ...],
  "gates": {"catalog_bump": "ok"|"fail"|"skipped", "version_sync": "...", "golden": "not_meaningful", "not_shipped": "...", "pytest": "..."}
}
```

Set `"trigger": "manual"` when this command was invoked interactively rather
than by the scheduler — without this distinction, a manual test run masks a
dead scheduler in the heartbeat history.

Commit and push `last-run.json` on `main` even if every other phase failed —
an outer step that always runs, not conditioned on the phases above
succeeding. If `--dry-run` was passed, skip this (and every other write) and
say so instead.

## Notes

- `unreachable` and `changes` are not mutually exclusive (Phase 2). A single
  run can legitimately open both a `watch-failure` issue and one or more
  curator PRs in the same pass.
- `regulatory-deadlines` has no state entry (`catalog/sources.yaml`: pure
  date arithmetic, no network). The CRA deadline at 2026-09-11 is inside the
  90-day `lead_time_days` window as of this writing — without the Phase 1/3
  dedupe ledger, that alone would reopen a PR every week for roughly six
  weeks. The ledger is not optional plumbing; it is what keeps this
  automation honest about what has already been decided.
