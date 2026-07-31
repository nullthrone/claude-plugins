#!/usr/bin/env python3
"""prisma-airs gate: scans prompt-shaped repository artifacts (or the
staged diff) through the AIRS batch scan API and turns the verdict into an
exit code.

Always fail-closed, unlike the runtime hooks: this is the one place in the
plugin where "the API didn't answer" must still stop the pipeline. See the
plan's D5.

Usage:
    python3 gate.py                 # scan default prompt-artifact globs
    python3 gate.py --diff          # scan `git diff --cached`
    python3 gate.py path [path ...] # scan specific files
"""
import argparse
import glob
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import airs
from config import Config
from hook_common import classify_action, feature_summary, truncate

# Prompt-shaped artifacts in a Claude Code plugin/marketplace repo: the
# files a compromised contributor (or a poisoned upstream dependency) would
# edit to smuggle an instruction into every future session that loads this
# repo. See UC-4 in the plan.
DEFAULT_GLOBS = [
    "CLAUDE.md",
    "**/CLAUDE.md",
    "commands/**/*.md",
    "**/commands/**/*.md",
    "skills/**/SKILL.md",
    "**/skills/**/SKILL.md",
    "agents/**/*.md",
    "**/agents/**/*.md",
]

POLL_INTERVAL_SECONDS = 2
# ~12s total across attempts; pan.dev's Python SDK usage page says async
# scans "may take approximately 10 seconds to complete".
POLL_ATTEMPTS = 6


def collect_default_files(root):
    seen = set()
    files = []
    for pattern in DEFAULT_GLOBS:
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            real = os.path.realpath(path)
            if os.path.isfile(path) and real not in seen:
                seen.add(real)
                files.append(path)
    return sorted(files)


def read_staged_diff():
    result = subprocess.run(
        ["git", "diff", "--cached"], capture_output=True, text=True, check=False,
    )
    return result.stdout


def poll_for_results(config, scan_id, expected_count):
    if not scan_id:
        return None
    collected = {}
    for _ in range(POLL_ATTEMPTS):
        try:
            payload = airs.get_scan_results(config, [scan_id])
        except (airs.AirsUnreachable, airs.AirsHTTPError):
            return None
        entries = payload if isinstance(payload, list) else payload.get("results", [])
        for entry in entries:
            if entry.get("status") == "complete":
                collected[entry.get("req_id")] = entry.get("result")
        if len(collected) >= expected_count:
            return collected
        time.sleep(POLL_INTERVAL_SECONDS)
    return collected or None


def scan_files(config, files):
    """Chunk into MAX_ASYNC_BATCH_ITEMS-sized batches, submit async, poll,
    and correlate results back to file paths by req_id. Returns a list of
    (path, was_truncated, result) tuples, or None on a hard failure (the
    caller should fail closed)."""
    all_results = []
    for i in range(0, len(files), airs.MAX_ASYNC_BATCH_ITEMS):
        chunk = files[i:i + airs.MAX_ASYNC_BATCH_ITEMS]
        items = []
        chunk_meta = []
        for req_id, path in enumerate(chunk):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text, was_truncated = truncate(f.read(), config.max_content_chars)
            items.append((req_id, [{"prompt": text}]))
            chunk_meta.append((req_id, path, was_truncated))

        try:
            submitted = airs.async_scan(config, items)
        except airs.AirsUnreachable as exc:
            print("prisma-airs-gate: AIRS unreachable ({}) -- failing closed".format(exc),
                  file=sys.stderr)
            return None
        except airs.AirsHTTPError as exc:
            print("prisma-airs-gate: AIRS HTTP {} -- failing closed".format(exc.status_code),
                  file=sys.stderr)
            return None

        scan_id = submitted.get("scan_id")
        collected = poll_for_results(config, scan_id, len(chunk))
        if collected is None:
            print("prisma-airs-gate: no results for scan_id {} after {} attempts -- "
                  "failing closed".format(scan_id, POLL_ATTEMPTS), file=sys.stderr)
            return None

        for req_id, path, was_truncated in chunk_meta:
            result = collected.get(req_id)
            if result is None:
                print("prisma-airs-gate: {}: no result returned -- failing closed".format(path),
                      file=sys.stderr)
                return None
            all_results.append((path, was_truncated, result))
    return all_results


def scan_diff(config):
    diff_text = read_staged_diff()
    if not diff_text.strip():
        print("prisma-airs-gate: no staged changes.")
        return 0
    text, was_truncated = truncate(diff_text, config.max_content_chars)
    try:
        result = airs.sync_scan(config, [{"prompt": text}])
    except airs.AirsUnreachable as exc:
        print("prisma-airs-gate: AIRS unreachable ({}) -- failing closed".format(exc),
              file=sys.stderr)
        return 2
    except airs.AirsHTTPError as exc:
        print("prisma-airs-gate: AIRS HTTP {} -- failing closed".format(exc.status_code),
              file=sys.stderr)
        return 2

    verdict = classify_action(result.get("action", "allow"))
    note = " (diff truncated to {} chars)".format(config.max_content_chars) if was_truncated else ""
    if verdict != "allow":
        print("prisma-airs-gate: staged diff flagged as {}{}: {}".format(
            verdict, note, ", ".join(feature_summary(result)) or "no detail"))
        return 1
    print("prisma-airs-gate: staged diff clean{}.".format(note))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", action="store_true",
                         help="scan `git diff --cached` instead of the default file globs")
    parser.add_argument("paths", nargs="*", help="specific files to scan")
    args = parser.parse_args()

    config = Config.load(os.getcwd())
    if not config.is_configured():
        print("prisma-airs-gate: not configured -- run /prisma-airs-setup first. "
              "Failing closed.", file=sys.stderr)
        return 2

    if args.diff:
        return scan_diff(config)

    files = args.paths or collect_default_files(os.getcwd())
    if not files:
        print("prisma-airs-gate: no prompt-artifact files found.")
        return 0

    outcome = scan_files(config, files)
    if outcome is None:
        return 2

    exit_code = 0
    for path, was_truncated, result in outcome:
        verdict = classify_action(result.get("action", "allow"))
        note = " (truncated to {} chars)".format(config.max_content_chars) if was_truncated else ""
        detail = ", ".join(feature_summary(result)) or "no detail"
        if verdict == "block":
            print("prisma-airs-gate: BLOCK {}{}".format(path, note))
            print("  " + detail)
            exit_code = 1
        elif verdict == "alert":
            print("prisma-airs-gate: ALERT {}{}".format(path, note))
            print("  " + detail)
            exit_code = max(exit_code, 1)
        else:
            print("prisma-airs-gate: allow {}{}".format(path, note))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
