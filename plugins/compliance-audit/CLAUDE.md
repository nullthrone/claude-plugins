# CLAUDE.md

Conventions and signposts for this repository. **No architecture decisions live
here** — those are smADRs in `docs/decisions/`. If while editing this file you
feel the urge to write down *why* something is built the way it is: that is an
ADR, not a CLAUDE.md entry.

## Language

Conversation follows the architect's language. Repository artifacts — code,
schemas, comments, ADRs, commit messages, PR bodies — are English throughout.

Two deliberate exceptions, both of which are content rather than convention:

- **Quoted legal text stays in its source language.** A translated citation is
  not a citation. `requirement_ref.citation` and any verbatim diff in a curator
  PR are German where the source is German.
- **The rendered report is localised.** `templates/report.de.md.j2` is German
  because its readers are. The canonical JSON is language-neutral; only the
  rendering carries a locale. `--locale` selects it.

## What this repository will not do

It does not state conformity. `schema/audit-run.schema.json` has no `compliant`
field and `assurance_level` is a schema constant. This is enforced structurally
rather than by disclaimer, because disclaimers get skipped and § 30 BSIG comes
with personal liability for management. Do not add such a field. Do not write
one in prose either.

## Non-negotiables

**One source of truth per run.** The agent produces JSON. `scripts/render.py`
renders the report from it. Nothing generates a report and a JSON separately —
after three iterations the numbers disagree and neither artefact is usable.

**A failed collector is never a pass.** Exit 2. This is the single most common
way a compliance gate turns into decoration.

**The catalog is never self-mutating.** `scripts/watch.py` detects, the
`catalog-curator` subagent proposes, a human disposes. Reasons in
`docs/decisions/0002`.

**Golden run is untouchable.** `golden/` is the instrument that checks the
curator. An agent that may edit it may launder its own mistakes.

## Layout

| Path | Purpose |
|---|---|
|  `catalog/primitives.yaml` | the actual checks — collector-bound, prüfobjekt-scoped |
| `catalog/mappings.yaml` | framework → control → primitive, n:m |
| `catalog/sources.yaml` | what the watcher observes, and what it deliberately does not |
| `schema/` | canonical run + change record |
| `templates/` | report renderings, one per locale |
| `scripts/` | render, watch, and the two CI gates |
| `golden/` | frozen evidence bundle + expected verdicts |
| `skills/`, `agents/`, `commands/` | the **shipped** plugin components |
| `.maintenance/` | curator, watcher, gates, golden run, tests — **never shipped** |
| `.claude-plugin/plugin.json` | manifest. Its `version` **is** the catalog version. |
| `docs/decisions/` | smADRs |

## The plugin cut

`components` in the manifest declares only `skills/`, `agents/`, `commands/`.
Everything under `.maintenance/` is copied into the consumer's plugin cache along
with the rest of the root, but is never *declared* — so Claude Code does not load
it. CI rejects any `components` entry pointing there.

The reason is not tidiness. A `catalog-curator` running from a consumer's cache
would patch a catalog that the next `/plugin update` overwrites: the change is
gone, the user believes it landed. See `docs/decisions/0003`.

Never write into `${CLAUDE_PLUGIN_ROOT}` at audit time. Read from it. Outputs go
to `.compliance/` in the audited project.

## When to write an ADR

- Adding or removing a framework from the catalog
- Changing the evidence class of an existing control
- Changing the verdict vocabulary or the exit-code semantics
- Anything that touches the proposer/disposer split around the catalog
- Changing what is shipped versus what stays in `.maintenance/`

Renumbering, wording, new primitives for existing controls: no ADR. Just a PR.

## Auth

`CLAUDE_CODE_OAUTH_TOKEN`, never `ANTHROPIC_API_KEY`. See `SETUP.md`.

## Signposts

- `/compliance-audit` — run an audit
- `.claude/agents/catalog-curator.md` — the rules the curator may not break
- `.maintenance/scripts/watch.py` — change detection against regulatory sources; run manually, no CI wiring in this repo
