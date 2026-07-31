#!/usr/bin/env python3
"""PreToolUse hook: scans a tool call's input before it runs.

Checkpoints 2+3 of the runtime protection surface. Genuine MCP tool calls
(`mcp__<server>__<tool>`) go through the schema's purpose-built `tool_event`
field, matching pan.dev's `contents[].tool_event` (`ecosystem: "mcp"`,
`method: "tools/call"`). Built-in tools (Bash, Write, Edit, WebFetch, ...)
are scanned as `code_prompt`/`prompt` content instead of stretching
`tool_event` past what pan.dev actually evidences for it.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import airs
from hook_common import (
    audit, classify_action, emit, feature_summary, load_config_or_exit,
    read_stdin_event, truncate,
)


def matches(tool_name, pattern):
    try:
        return re.fullmatch(pattern, tool_name) is not None
    except re.error:
        return False


def build_contents(tool_name, tool_input, max_chars):
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        server_name = parts[1] if len(parts) > 1 else tool_name
        tool_invoked = parts[2] if len(parts) > 2 else tool_name
        payload, was_truncated = truncate(json.dumps(tool_input, default=str), max_chars)
        return [{"tool_event": {
            "metadata": {
                "ecosystem": "mcp", "method": "tools/call",
                "server_name": server_name, "tool_invoked": tool_invoked,
            },
            "input": payload,
        }}], was_truncated
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        text, was_truncated = truncate(command, max_chars)
        return [{"code_prompt": text}], was_truncated
    text, was_truncated = truncate(json.dumps(tool_input, default=str), max_chars)
    return [{"prompt": text}], was_truncated


def main():
    event = read_stdin_event()
    config = load_config_or_exit("pre_tool_use")

    tool_name = event.get("tool_name", "")
    if not tool_name or not matches(tool_name, config.tool_matcher):
        return 0

    tool_input = event.get("tool_input") or {}
    contents, was_truncated = build_contents(tool_name, tool_input, config.max_content_chars)

    try:
        result = airs.sync_scan(config, contents, session_id=event.get("session_id"))
    except airs.AirsUnreachable as exc:
        policy = config.on_unreachable("pre_tool_use")
        audit(config, "pre_tool_use",
              {"status": "unreachable", "policy": policy, "tool": tool_name, "error": str(exc)})
        print("prisma-airs: scan unreachable for {}, policy={} ({})".format(
            tool_name, policy, exc), file=sys.stderr)
        if policy == "ask":
            emit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason":
                    "prisma-airs: security scan unreachable; confirm this tool call yourself.",
            }})
        elif policy in ("deny", "block"):
            emit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "prisma-airs: security scan unreachable.",
            }})
        return 0
    except airs.AirsHTTPError as exc:
        audit(config, "pre_tool_use",
              {"status": "http_error", "code": exc.status_code, "tool": tool_name})
        print("prisma-airs: scan HTTP {} for {} -- allowing".format(exc.status_code, tool_name),
              file=sys.stderr)
        return 0

    verdict = classify_action(result.get("action", "allow"))
    features = feature_summary(result)
    audit(config, "pre_tool_use", {
        "status": "scanned", "tool": tool_name, "action": result.get("action"),
        "verdict": verdict, "scan_id": result.get("scan_id"), "features": features,
        "truncated": was_truncated,
    })

    if verdict == "block":
        emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                "prisma-airs: blocked by AI security profile ({}).".format(
                    ", ".join(features) or "no detail"),
        }})
        return 0
    if verdict == "alert":
        emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason":
                "prisma-airs: flagged for review ({}) -- confirm before proceeding.".format(
                    ", ".join(features) or "no detail"),
        }})
    return 0


if __name__ == "__main__":
    sys.exit(main())
