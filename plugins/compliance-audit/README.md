# compliance-audit

Audits code, IaC and runtime configuration against German and EU regulatory
frameworks (BSI IT-Grundschutz, Cyber Resilience Act, GDPR). Ships as a Claude Code
plugin.

**It makes no conformity statement, and cannot.** `schema/audit-run.schema.json`
has no `compliant` field; `assurance_level` is a schema constant. This is enforced
structurally rather than by disclaimer, because disclaimers get skipped and § 30
BSIG carries personal liability for management. Read [Limitations](#limitations)
before you rely on a run.

## Install

From the marketplace (recommended):

```
/plugin marketplace add nullthrone/claude-plugins
/plugin install compliance-audit@nullthrone
```

`nullthrone/claude-plugins` is the GitHub repository that hosts the marketplace;
`@nullthrone` is the marketplace name declared in `.claude-plugin/marketplace.json`.

Installing gives you three components:

- the `/compliance-audit` slash command,
- the `compliance-audit` skill (auto-invoked when you ask for a compliance audit),
- the `compliance-auditor` agent (runs the audit in an isolated context).

### Local / development install

To try a clone before it is published, add the checkout directory as a marketplace:

```
git clone https://github.com/nullthrone/claude-plugins
/plugin marketplace add ./claude-plugins
/plugin install compliance-audit@nullthrone
```

Validate the manifest and component frontmatter with:

```
claude plugin validate ./claude-plugins
```

### Pinning

Pin deliberately. `autoUpdate` should stay off: the plugin version *is* the catalog
version, and a catalog that changes silently between two runs breaks the
reproducibility of every verdict. See `docs/decisions/0003`.

## Usage

### Prerequisites

The audit shells out to external, read-only collectors. Install the ones you need
for your scope and make sure they are on `PATH`:

| Collector | Scope it covers |
|---|---|
| `checkov` | IaC misconfiguration (`--scope iac`) |
| `semgrep` | source code (`--scope code`) |
| `syft` | SBOM generation (`--scope code`) |
| `grype` | dependency vulnerabilities (`--scope code`) |
| `gcloud` | cloud runtime state (`--scope runtime`) |
| `uv` | runs `scripts/render.py` to render the report |

**Cloud credentials must be read-only.** GCP, for example, needs `roles/viewer` plus
`roles/iam.securityReviewer` and `roles/orgpolicy.policyViewer` at organisation
level (see `SETUP.md`). If the credentials available at run time are writable, the
audit stops rather than proceeding. The auditor only ever reads runtime state.

### Running an audit

Run the command from the root of the project you want to audit — not from the plugin:

```
/compliance-audit --framework bsi-grundschutz,cra,dsgvo --scope code,iac,runtime --format both
```

Flags (all optional):

| Flag | Values | Default |
|---|---|---|
| `--framework` | `bsi-grundschutz`, `cra`, `dsgvo` (comma-separated) | all three |
| `--scope` | `code`, `iac`, `runtime` (comma-separated) | all three |
| `--format` | `md`, `json`, `both` | `md` |

Examples:

```
# Just the code and IaC, BSI only, JSON out
/compliance-audit --framework bsi-grundschutz --scope code,iac --format json

# Full audit, rendered German report + canonical JSON
/compliance-audit --framework bsi-grundschutz,cra,dsgvo --scope code,iac,runtime --format both
```

### Two phases, always

1. **Collect.** Collectors run once and write a frozen, hashed evidence bundle to
   `.compliance/evidence/<id>/` — each entry carries a timestamp, the query, the raw
   response and a hash.
2. **Judge.** Verdicts are formed against that bundle only. The auditor does not
   re-query; a verdict must still be defensible against the same snapshot six months
   later.

### Output

Everything lands under `.compliance/` in the audited project:

```
.compliance/
├── run.json                 # canonical result — the single source of truth
├── evidence/<id>/           # frozen, hashed evidence bundle
└── report.md                # report, rendered deterministically from run.json
```

The report is **rendered** from `run.json` by `scripts/render.py`; it is never
written by hand. Same `run.json` in, byte-identical report out. See
`examples/example-run.json` and `examples/example-report.de.md` for a full sample.

### Reading a result

- **Coverage before results.** The report first states how many controls were out of
  technical scope, then how many passed or failed. A high pass rate over a small
  assessable surface is not a good result.
- **Evidence classes.** Every control is **A** deterministic, **B** interpretive
  (a model judges, with mandatory confidence and cited evidence), or **C**
  organisational (training, contracts, processes). Class C is always
  `out_of_technical_scope`, never `pass`.
- **Exit codes.** A run that completes is exit `0`. A failed or missing collector
  yields `insufficient_evidence` and exit `2` — never silently a pass.

## How it works

Frameworks do not carry their own checks. A single primitive — "TLS below 1.2 in
transport config" — satisfies BSI CON.1, ISO A.8.24, § 30 (2) no. 8 BSIG, DORA RTS
Art. 6 and Art. 32 (1)(a) GDPR at once. Frameworks are n:m projections onto that
layer (`catalog/`). See `docs/decisions/0001`.

## Limitations

What this plugin deliberately does **not** do. These are design constraints, not
gaps to be filled later.

- **No conformity statement, by construction.** `schema/audit-run.schema.json` has no
  `compliant` field and `assurance_level` is the schema constant
  `technical-evidence-only`. The tool reports technical evidence, not legal
  conformity. **A passing run is not a certificate** and must not be presented as one.
- **Organisational controls are out of scope.** Class **C** controls — training,
  contracts, processes — are marked `out_of_technical_scope`, never `pass`. The tool
  cannot see whether staff were trained or a data-processing agreement was signed.
- **State is not enforcement.** A resource that happens to sit in the EU is not the
  same as a policy that prevents it from leaving. A vendor certificate is not
  evidence until the specific service appears on that certificate's product-scope
  list. The tool records this distinction rather than papering over it.
- **Evidence-bounded.** Results are only as good as the collected bundle and the
  read-only scope you granted. A failed or absent collector is `insufficient_evidence`
  (exit 2), never an assumed pass.
- **Interpretive judgements are advisory.** Class **B** verdicts are produced by a
  model and carry a confidence score and cited evidence. They are input for a human
  reviewer, not authoritative legal findings.
- **Catalog currency and licensing.** The plugin version *is* the catalog version;
  keep `autoUpdate` off so verdicts stay reproducible. Frameworks whose text is
  licensed (ISO 27001, TISAX) cannot be watched and are projection-only or out of
  scope — see the table below.

## Catalog currency

`.maintenance/scripts/watch.py` detects changes deterministically (no model).
The `catalog-curator` proposes a PR. A human merges. Two gates constrain it: a
catalog change without a version bump is rejected, and the catalog is replayed
against a frozen evidence bundle so any verdict flipping without the evidence
changing must be explained. See `docs/decisions/0002`.

Nothing under `.maintenance/` is a shipped plugin component. A curator running
from a consumer's cache would patch a catalog that the next update overwrites.

## Frameworks

| Framework | Status |
|---|---|
| BSI IT-Grundschutz | catalog, watched |
| Cyber Resilience Act | catalog, watched (reporting duty 2026-09-11) |
| GDPR | catalog, watched (text) + publication triage (interpretation) |
| ISO 27001 | projection planned; text is licensed, cannot be watched |
| NIS2, DORA | mapping views planned |
| TISAX | out of scope; VDA-licensed catalogue |
