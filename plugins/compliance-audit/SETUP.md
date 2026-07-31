# Setup

## Auth

There is no CI wiring in this repo (see `docs/decisions/0004` — the original
design ran the curator via GitHub Actions with a GitHub App and repo secrets;
that was replaced by a locally-scheduled Claude Code session, both to avoid
putting a GitHub App plus three secrets on a public repository and because
GitHub disables scheduled workflows after ~60 days of repo inactivity).

`/catalog-watch` runs in an ordinary authenticated Claude Code session on the
machine it is scheduled on — desktop session auth, no `CLAUDE_CODE_OAUTH_TOKEN`,
no GitHub App. It opens PRs/issues via the local `gh` CLI, so `gh auth status`
must show a token with `write` access to this repo before the schedule is set
up (see `.claude/commands/catalog-watch.md` and its preflight check).

Never `ANTHROPIC_API_KEY`.

## Cloud credentials — read-only, always

The auditor needs to read runtime state. It never needs to write it.

GCP: `roles/viewer` plus `roles/iam.securityReviewer` and
`roles/orgpolicy.policyViewer` at organisation level. The last one is what makes
the state-versus-enforcement distinction possible; without it the auditor can see
that a resource is in the EU but not whether anything prevents it from leaving.

If the credentials available at run time are not read-only, the audit stops.

## First run

```bash
python -m venv <venv-dir>
<venv-dir>/Scripts/pip install -r .maintenance/requirements.txt   # Windows
# <venv-dir>/bin/pip install -r .maintenance/requirements.txt     # macOS/Linux
<venv-dir>/Scripts/python .maintenance/scripts/watch.py --write-state   # establish the source baseline
git add .maintenance/state/sources.json && git commit -m "chore: baseline watch state"
```

The first watch run reports `baseline_established` for every source. That is
expected and requires no action. This step is supervised and manual by design
— see `.claude/commands/catalog-watch.md` for why it is not part of the
scheduled run.

## Establishing the golden run

The golden run is meant to be the instrument that checks catalog changes. It
needs a real evidence bundle from a real target:

```bash
/compliance-audit --scope code,iac,runtime --format json > run.json
cp -r .compliance/evidence/<bundle> .maintenance/golden/bundle-ref
cp run.json .maintenance/golden/expected-run.json
```

From then on, every catalog PR is *meant to be* replayed against this bundle,
and any verdict that moves without the evidence moving explained. **As of
`docs/decisions/0004`, `replay.py` is a stub** that copies
`.maintenance/golden/expected-run.json` back out verbatim regardless of the
catalog under test — this check currently cannot fail. Fixing it requires
wiring the real auditor verdict phase into `replay.py`, which is tracked but
not yet done; until then, do not treat a passing golden gate as evidence of
anything.
