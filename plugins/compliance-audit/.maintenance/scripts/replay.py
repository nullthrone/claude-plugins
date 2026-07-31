#!/usr/bin/env python3
"""
replay.py — Re-judge a frozen evidence bundle against the *current* catalog.

This is what makes the golden-run gate possible: the evidence cannot change, so
any verdict that moves is attributable to the catalog alone. In the real
pipeline this delegates to the compliance-auditor subagent's verdict phase.
Here it is a stub that reads the pre-computed run from the bundle, so that the
gate and its tests are exercisable without a model in the loop.
"""
import argparse, json, shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("bundle", type=Path)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()

run = json.loads((a.bundle / "run.json").read_text())
a.out.write_text(json.dumps(run, indent=2, ensure_ascii=False))
print(f"replayed {a.bundle} -> {a.out}")
