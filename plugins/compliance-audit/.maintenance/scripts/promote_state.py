#!/usr/bin/env python3
"""
promote_state.py — merge selected sources' state from a candidate baseline
into the committed one.

watch.py's --state-out always writes a full candidate state for every source,
regardless of whether any particular source's change has actually been acted
on. Promoting the whole candidate file the moment ONE source's PR merges
would silently advance every OTHER source's baseline too -- a real change to
a source whose own PR is still open would stop being detected on the next
run, without anyone deciding that. This script promotes exactly the named
source_id(s) and leaves every other source's committed state untouched.

Usage: promote_state.py <candidate.json> <source_id> [<source_id> ...] [--state <path>]
Exit:  0 ok, 1 a named source_id is not in the candidate, 3 usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .maintenance/scripts/ -> plugin root
DEFAULT_STATE = ROOT / ".maintenance" / "state" / "sources.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("candidate", type=Path, help="state file produced by watch.py --state-out")
    ap.add_argument("source_ids", nargs="+", help="source ids to promote")
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE,
                     help="committed state file to update (default: the live baseline)")
    args = ap.parse_args()

    if not args.candidate.exists():
        print(f"[FAIL] candidate not found: {args.candidate}", file=sys.stderr)
        return 3

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    committed = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {}

    missing = [sid for sid in args.source_ids if sid not in candidate]
    if missing:
        print(f"[FAIL] not present in candidate state: {', '.join(missing)}", file=sys.stderr)
        return 1

    for sid in args.source_ids:
        committed[sid] = candidate[sid]
        print(f"[ok] promoted {sid}")

    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(committed, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
