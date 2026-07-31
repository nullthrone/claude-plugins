#!/usr/bin/env python3
"""
golden_diff.py — CI gate. The one that catches a hallucinated requirement.

The evidence bundle is already a fixed, hashed snapshot. So a catalog change can
be replayed against it: same evidence, same code, only the catalog moved. Every
verdict that flips as a result is either intended (and must be explained in the
PR body) or is the catalog inventing a requirement that does not exist.

Without this gate, a curator PR that quietly rewrites thirty controls to `fail`
looks exactly like a curator PR that fixes a renumbering. With it, the diff is
on the table before anyone clicks merge.

Usage:  golden_diff.py <actual_run.json>
Exit:   0 no verdict drift, 1 drift (explain it), 3 config error
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = ROOT / ".maintenance" / "golden" / "expected-run.json"

FIELDS = ["verdict", "enforcement", "evidence_class", "evidence_origin"]


def index(run: dict) -> dict[tuple[str, str], dict]:
    return {(c["framework_id"], c["control_id"]): c for c in run["controls"]}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 3
    if not EXPECTED.exists():
        print("golden/expected-run.json missing. Establish a golden run first.", file=sys.stderr)
        return 3

    expected = index(json.loads(EXPECTED.read_text()))
    actual = index(json.loads(Path(sys.argv[1]).read_text()))

    drift: list[str] = []

    for key in sorted(set(expected) | set(actual)):
        label = f"{key[0]} · {key[1]}"
        if key not in actual:
            drift.append(f"[REMOVED] {label}: was {expected[key]['verdict']}, control gone from catalog")
            continue
        if key not in expected:
            drift.append(f"[ADDED]   {label}: new control, verdict {actual[key]['verdict']}")
            continue
        for f in FIELDS:
            if expected[key].get(f) != actual[key].get(f):
                drift.append(
                    f"[CHANGED] {label}: {f} {expected[key].get(f)} -> {actual[key].get(f)}"
                )

    if not drift:
        print("golden run: no verdict drift")
        return 0

    print("Verdict drift against the golden evidence bundle:\n")
    for d in drift:
        print(f"  {d}")
    print(
        "\nThe evidence did not change — only the catalog did. Every line above is\n"
        "either an intended consequence of this catalog change, or the catalog\n"
        "asserting a requirement that is not in the source. Explain each one in the\n"
        "PR body, or fix the catalog.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
