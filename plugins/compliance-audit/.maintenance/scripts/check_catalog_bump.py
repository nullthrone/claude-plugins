#!/usr/bin/env python3
"""
check_catalog_bump.py — CI gate.

A change to catalog/ without an increment of `version` in the changed file is
rejected. Without this, `catalog_version` in an audit run stops being a stable
reference, and the difference between "the code got worse" and "the catalog got
stricter" becomes unrecoverable after the fact. That difference is the only
reason the field exists.

Usage:  check_catalog_bump.py <base_ref>
Exit:   0 ok, 1 missing bump, 3 usage/config error
"""

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]  # .maintenance/scripts/ -> plugin root
WATCHED = ["catalog/mappings.yaml", "catalog/primitives.yaml", "catalog/sources.yaml"]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=ROOT,
    ).stdout


def _prefix() -> str:
    """Path from the git repo root to this plugin's root, e.g.
    'plugins/compliance-audit/' in the marketplace monorepo, '' if the plugin
    IS the repo root. `git diff --name-only` always reports repo-root-relative
    paths, so WATCHED (plugin-relative) must be prefixed to compare -- without
    this, `p in WATCHED` never matches in the monorepo layout and this gate
    silently always passes."""
    return git("rev-parse", "--show-prefix").strip()


def version_at(ref: str, prefix: str, path: str) -> str | None:
    try:
        blob = git("show", f"{ref}:{prefix}{path}")
    except subprocess.CalledProcessError:
        return None  # file did not exist at base -> new file, bump not required
    try:
        return yaml.safe_load(blob).get("version")
    except Exception:  # noqa: BLE001
        return None


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 3
    base = sys.argv[1]

    prefix = _prefix()
    changed = git("diff", "--name-only", f"{base}...HEAD").split()
    watched_repo_relative = {prefix + w for w in WATCHED}
    touched = [p[len(prefix):] for p in changed if p in watched_repo_relative]
    if not touched:
        print("no catalog changes")
        return 0

    failed = False
    for path in touched:
        old = version_at(base, prefix, path)
        new = yaml.safe_load((ROOT / path).read_text(encoding="utf-8")).get("version")
        if old is None:
            print(f"[ok]   {path}: new file, version {new}")
            continue
        if new is None:
            print(f"[FAIL] {path}: no `version` field")
            failed = True
        elif parse(new) <= parse(old):
            print(f"[FAIL] {path}: content changed but version did not advance ({old} -> {new})")
            failed = True
        else:
            print(f"[ok]   {path}: {old} -> {new}")

    if failed:
        print(
            "\nA catalog change without a version bump breaks reproducibility of every\n"
            "audit run that references it. Bump the version.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
