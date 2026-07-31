#!/usr/bin/env python3
"""Stop hook: scans Claude's final response text for the turn.

Closes a gap Palo Alto's own community reference integration names in its
own README ("no model response hook configured" -- generated text without
a tool call bypasses every other checkpoint). Disabled by default
(hooks.stop=false in .prisma-airs.json): pan.dev documents no per-request
latency bound for the scan API, and this hook sits on the critical path of
every turn ending.

Deliberately never uses `decision: block` to force Claude to keep going --
looping a turn based on a security scan is a footgun (a retry could easily
reproduce the same flagged content). A `block` verdict here surfaces as
loud, non-blocking context instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import airs
from hook_common import (
    audit, classify_action, emit, feature_summary, load_config_or_exit,
    read_stdin_event, truncate,
)


def main():
    event = read_stdin_event()
    config = load_config_or_exit("stop")

    text = event.get("last_assistant_message") or ""
    if not text:
        return 0

    text, was_truncated = truncate(text, config.max_content_chars)

    try:
        result = airs.sync_scan(config, [{"response": text}], session_id=event.get("session_id"))
    except airs.AirsUnreachable as exc:
        audit(config, "stop", {"status": "unreachable", "error": str(exc)})
        return 0
    except airs.AirsHTTPError as exc:
        audit(config, "stop", {"status": "http_error", "code": exc.status_code})
        return 0

    verdict = classify_action(result.get("action", "allow"))
    features = feature_summary(result)
    audit(config, "stop", {
        "status": "scanned", "action": result.get("action"), "verdict": verdict,
        "scan_id": result.get("scan_id"), "features": features, "truncated": was_truncated,
    })

    if verdict != "allow":
        emit({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext":
                "prisma-airs: the response just produced was flagged as {} ({}). "
                "This is informational only -- the turn was not blocked.".format(
                    verdict, ", ".join(features) or "no detail"),
        }})
    return 0


if __name__ == "__main__":
    sys.exit(main())
