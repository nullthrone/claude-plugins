#!/usr/bin/env python3
"""UserPromptSubmit hook: scans the raw user prompt before Claude sees it.

Checkpoint 1 of the runtime protection surface -- see
reference/detections.md. Inert (exit 0, no output, no network call) unless
`.prisma-airs.json` and an API key are both present; see
docs/decisions/0002-inert-until-configured.md.
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
    config = load_config_or_exit("user_prompt_submit")

    prompt = event.get("user_prompt", "")
    if not prompt:
        return 0

    text, was_truncated = truncate(prompt, config.max_content_chars)
    metadata = {"app_user": os.environ.get("USER") or os.environ.get("USERNAME")}

    try:
        result = airs.sync_scan(
            config, [{"prompt": text}],
            session_id=event.get("session_id"), metadata=metadata,
        )
    except airs.AirsUnreachable as exc:
        policy = config.on_unreachable("user_prompt_submit")
        audit(config, "user_prompt_submit",
              {"status": "unreachable", "policy": policy, "error": str(exc)})
        print("prisma-airs: scan unreachable, policy={} ({})".format(policy, exc),
              file=sys.stderr)
        if policy == "block":
            emit({"decision": "block",
                  "reason": "prisma-airs: security scan unreachable and "
                            "on_unreachable.user_prompt_submit is \"block\"."})
        return 0
    except airs.AirsHTTPError as exc:
        audit(config, "user_prompt_submit",
              {"status": "http_error", "code": exc.status_code})
        print("prisma-airs: scan HTTP {} -- allowing through".format(exc.status_code),
              file=sys.stderr)
        return 0

    verdict = classify_action(result.get("action", "allow"))
    features = feature_summary(result)
    audit(config, "user_prompt_submit", {
        "status": "scanned", "action": result.get("action"), "verdict": verdict,
        "scan_id": result.get("scan_id"), "features": features, "truncated": was_truncated,
    })

    if verdict == "block":
        emit({"decision": "block",
              "reason": "prisma-airs: prompt blocked by AI security profile ({}).".format(
                  ", ".join(features) or "no detail")})
        return 0
    if verdict == "alert":
        emit({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext":
                "prisma-airs: this prompt was flagged for review ({}). Proceeding, "
                "but treat the result with care.".format(", ".join(features) or "no detail"),
        }})
    return 0


if __name__ == "__main__":
    sys.exit(main())
