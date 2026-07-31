#!/usr/bin/env python3
"""
check_version_sync.py — CI gate.

The plugin version IS the catalog version. A consumer project reports
`catalog_version` in every audit run; if two projects on the same plugin version
could hold different catalogs, that field is a lie.

Therefore: any change under catalog/ requires .claude-plugin/plugin.json:version
to advance, and the report's catalog_version is taken from the plugin manifest.

Usage: check_version_sync.py <base_ref>
Exit:  0 ok, 1 missing bump, 3 usage error
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .maintenance/scripts/ -> plugin root


def git(*a: str) -> str:
    return subprocess.run(["git", *a], capture_output=True, text=True,
                          check=True, cwd=ROOT).stdout


def _prefix() -> str:
    """See check_catalog_bump.py's _prefix(): `git diff --name-only` reports
    repo-root-relative paths, so in the marketplace monorepo they carry a
    'plugins/compliance-audit/' prefix this plugin-relative script must
    account for -- otherwise `p.startswith("catalog/")` never matches and
    this gate silently always passes."""
    return git("rev-parse", "--show-prefix").strip()


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 3
    base = sys.argv[1]

    prefix = _prefix()
    changed = git("diff", "--name-only", f"{base}...HEAD").split()
    catalog_touched = [p for p in changed if p.startswith(f"{prefix}catalog/")]
    if not catalog_touched:
        print("no catalog changes")
        return 0

    new = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    try:
        old = json.loads(git("show", f"{base}:{prefix}.claude-plugin/plugin.json"))["version"]
    except subprocess.CalledProcessError:
        print(f"[ok] new manifest, version {new}")
        return 0

    for p in catalog_touched:
        print(f"  changed: {p}")

    if parse(new) <= parse(old):
        print(
            f"\n[FAIL] catalog changed but plugin version did not advance ({old} -> {new}).\n"
            f"The plugin version is the catalog version. Shipping a changed catalog under\n"
            f"an unchanged version makes `catalog_version` in every consumer's audit run\n"
            f"meaningless.",
            file=sys.stderr,
        )
        return 1

    print(f"[ok] plugin version {old} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
