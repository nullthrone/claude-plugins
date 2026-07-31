#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2>=3.1", "jsonschema>=4.23"]
# ///
"""
render.py — Validate an audit run against the schema and render the report from it.

Core rule: the agent produces the JSON. The report is rendered from it,
deterministically. Same input, byte-identical output. Nothing generates a report
and a JSON separately — after three iterations the numbers disagree and neither
artefact is usable.

PEP 723 header: `uv run` resolves the dependencies itself. A plugin ships no
venv, and requiring consumers to pip-install into their project is friction that
gets skipped.

Path resolution: when installed as a plugin, this file lives in the plugin cache
while the working directory is the audited project. ${CLAUDE_PLUGIN_ROOT} points
at the plugin; falling back to the file's own location keeps the repo checkout
working too.

Exit codes (CI semantics):
  0  no verdicts above threshold
  1  fail verdicts above threshold
  2  insufficient_evidence or a failed collector  -- NEVER green
  3  catalog, schema or configuration error
"""

import argparse
import json
import os
import sys
from pathlib import Path

import jsonschema
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_EVIDENCE = 2
EXIT_CONFIG = 3


def load_schema() -> dict:
    return json.loads((ROOT / "schema" / "audit-run.schema.json").read_text())


def validate(run: dict) -> None:
    jsonschema.validate(instance=run, schema=load_schema())


def check_consistency(run: dict) -> list[str]:
    """Konsistenzpruefungen, die JSON Schema nicht ausdruecken kann."""
    errors = []
    ids = {f["finding_id"] for f in run["findings"]}
    for ctl in run["controls"]:
        for ref in ctl["finding_refs"]:
            if ref not in ids:
                errors.append(f"{ctl['control_id']}: finding_ref {ref} existiert nicht")

    # Coverage muss mit den tatsaechlichen Controls uebereinstimmen.
    for cov in run["coverage"]:
        fid = cov["framework_id"]
        actual = [c for c in run["controls"] if c["framework_id"] == fid]
        for verdict, key in [
            ("pass", "passed"), ("fail", "failed"), ("partial", "partial"),
            ("not_applicable", "not_applicable"),
            ("out_of_technical_scope", "out_of_technical_scope"),
            ("insufficient_evidence", "insufficient_evidence"),
        ]:
            n = len([c for c in actual if c["verdict"] == verdict])
            if n != cov[key]:
                errors.append(
                    f"coverage[{fid}].{key} = {cov[key]}, tatsaechlich {n}"
                )
    return errors


def render(run: dict, locale: str = "de") -> str:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    tpl = env.get_template(f"report.{locale}.md.j2")
    return tpl.render(
        run=run,
        findings_by_id={f["finding_id"]: f for f in run["findings"]},
    )


def exit_code(run: dict, fail_on: set[str]) -> int:
    if any(c["status"] in ("failed",) for c in run["tooling"]["collectors"]):
        return EXIT_EVIDENCE
    if any(c["verdict"] == "insufficient_evidence" for c in run["controls"]):
        return EXIT_EVIDENCE
    if any(c["verdict"] in fail_on for c in run["controls"]):
        return EXIT_FAIL
    return EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_json", type=Path)
    ap.add_argument("--format", choices=["md", "json", "both"], default="md")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--locale", default="de",
                    help="report language. The JSON is language-neutral; only the rendering is localised.")
    ap.add_argument("--fail-on", default="fail",
                    help="Kommaliste aus fail,partial")
    args = ap.parse_args()

    try:
        run = json.loads(args.run_json.read_text())
        validate(run)
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        print(f"Schema-Fehler: {e}", file=sys.stderr)
        return EXIT_CONFIG

    errors = check_consistency(run)
    if errors:
        for e in errors:
            print(f"Konsistenzfehler: {e}", file=sys.stderr)
        return EXIT_CONFIG

    fail_on = set(args.fail_on.split(","))

    if args.format in ("md", "both"):
        md = render(run, args.locale)
        if args.out:
            args.out.write_text(md)
        else:
            print(md)

    if args.format in ("json", "both"):
        target = sys.stdout if not args.out else open(args.out.with_suffix(".json"), "w")
        json.dump(run, target, indent=2, ensure_ascii=False)
        if args.out:
            target.close()

    return exit_code(run, fail_on)


if __name__ == "__main__":
    sys.exit(main())
