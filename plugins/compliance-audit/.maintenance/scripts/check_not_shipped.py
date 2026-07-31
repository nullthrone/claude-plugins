#!/usr/bin/env python3
"""
check_not_shipped.py — CI/local gate.

.maintenance/ (catalog-curator, watch.py, gates, golden fixtures, tests) must
never be part of what ships to a consumer. A curator running from a
consumer's installed plugin cache would patch a catalog that the next
`/plugin update` overwrites -- the change vanishes and the user believes it
landed. See docs/decisions/0003.

Two independent checks. plugin.json can declare shipped component paths
explicitly (a top-level field REPLACES the default scan for that component)
or leave them implicit (auto-discovery of the default skills/ agents/
commands/ hooks/ .mcp.json directories when no such field is present):

  (a) no explicit component path field in plugin.json points into .maintenance/
  (b) nothing under what actually ships -- explicit paths where declared, the
      auto-discovered defaults otherwise -- references .maintenance/ at all.
      A shipped command/skill/agent that shells out to
      .maintenance/scripts/watch.py works in this repo and silently breaks
      from a consumer's plugin cache, which only ever receives the shipped
      subset.

The previous CI step only checked a `components` object that plugin.json
does not actually use (this manifest relies entirely on auto-discovery) --
so it verified a field that was never populated. This replaces it.

Usage: check_not_shipped.py
Exit:  0 ok, 1 a leak found, 3 config error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .maintenance/scripts/ -> plugin root
COMPONENT_FIELDS = (
    "skills", "agents", "commands", "hooks", "mcpServers",
    "outputStyles", "lspServers", "workflows",
)
DEFAULT_DIRS = ("skills", "agents", "commands", "hooks")


def _declared_paths(manifest: dict) -> list[str]:
    paths: list[str] = []
    for key in COMPONENT_FIELDS:
        v = manifest.get(key)
        if isinstance(v, str):
            paths.append(v)
        elif isinstance(v, list):
            paths.extend(p for p in v if isinstance(p, str))
    for v in manifest.get("components", {}).values():  # legacy nested form
        paths.extend(v if isinstance(v, list) else [v])
    return paths


def _shipped_scan_dirs(manifest: dict) -> list[Path]:
    scan_dirs: list[Path] = []
    for key, default_dir in zip(("skills", "agents", "commands", "hooks"), DEFAULT_DIRS):
        v = manifest.get(key)
        if isinstance(v, str):
            scan_dirs.append(ROOT / v)
        elif isinstance(v, list):
            scan_dirs.extend(ROOT / p for p in v if isinstance(p, str))
        else:
            d = ROOT / default_dir
            if d.is_dir():
                scan_dirs.append(d)

    mcp = manifest.get("mcpServers")
    if isinstance(mcp, str):
        scan_dirs.append(ROOT / mcp)
    elif (ROOT / ".mcp.json").exists():
        scan_dirs.append(ROOT / ".mcp.json")
    return scan_dirs


def main() -> int:
    manifest_path = ROOT / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"config error: {e}", file=sys.stderr)
        return 3

    failed = False

    bad_declared = [p for p in _declared_paths(manifest) if ".maintenance" in p]
    if bad_declared:
        print(f"[FAIL] plugin.json declares a .maintenance path as a component: {bad_declared}",
              file=sys.stderr)
        failed = True
    else:
        print("[ok]   no declared component path points into .maintenance/")

    leaks: list[str] = []
    for d in _shipped_scan_dirs(manifest):
        files = [d] if d.is_file() else (sorted(d.rglob("*")) if d.is_dir() else [])
        for f in files:
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if ".maintenance" in text:
                leaks.append(str(f.relative_to(ROOT)))

    if leaks:
        print(f"[FAIL] shipped files reference .maintenance/: {leaks}", file=sys.stderr)
        failed = True
    else:
        print("[ok]   nothing shipped references .maintenance/")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
