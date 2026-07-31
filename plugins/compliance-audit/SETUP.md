# Setup

## Secrets

| Secret | Purpose | How |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | curator subagent in CI | `claude setup-token` |
| `APP_ID` | GitHub App, so the curator can open PRs | see below |
| `APP_PRIVATE_KEY` | GitHub App | see below |

Never `ANTHROPIC_API_KEY`. The OAuth token is CI-capable but finite — on auth
failures in CI, regenerate and update the secret.

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN
gh secret set APP_ID
gh secret set APP_PRIVATE_KEY < app-private-key.pem
```

## Cloud credentials — read-only, always

The auditor needs to read runtime state. It never needs to write it.

GCP: `roles/viewer` plus `roles/iam.securityReviewer` and
`roles/orgpolicy.policyViewer` at organisation level. The last one is what makes
the state-versus-enforcement distinction possible; without it the auditor can see
that a resource is in the EU but not whether anything prevents it from leaving.

If the credentials available at run time are not read-only, the audit stops.

## First run

```bash
pip install -r requirements.txt
python scripts/watch.py --write-state          # establish the source baseline
git add catalog/.state && git commit -m "chore: baseline watch state"
```

The first watch run reports `baseline_established` for every source. That is
expected and requires no action.

## Establishing the golden run

The golden run is the instrument that checks catalog changes. It needs a real
evidence bundle from a real target:

```bash
/compliance-audit --scope code,iac,runtime --format json > run.json
cp -r .compliance/evidence/<bundle> golden/bundle-ref
cp run.json golden/expected-run.json
```

From then on, every catalog PR is replayed against this bundle. Any verdict that
moves without the evidence moving must be explained.
