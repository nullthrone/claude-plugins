"""Shared plumbing for prisma-airs hooks: the inert-by-default gate, the
audit log, and verdict classification. Every hook script imports this so
the fail-closed/fail-open decisions live in one place instead of five.
"""
import datetime
import json
import os
import sys

from config import Config


def read_stdin_event():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")


def load_config_or_exit(hook_key):
    """Config.load() plus the D3 inert gate, in one call every hook makes
    first: unconfigured or explicitly disabled means exit 0, no output, no
    network call. See docs/decisions/0002-inert-until-configured.md.
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    config = Config.load(project_dir)
    if not config.is_configured() or not config.hook_enabled(hook_key):
        sys.exit(0)
    return config


def audit(config, event, payload):
    """Append one JSON line to the project's audit log. Never raises --
    logging must not be why a hook crashes -- and never includes raw
    prompt/response/snippet content, only verdicts and identifiers (see
    docs/decisions -- D7, no raw content in the log).
    """
    path = config.audit_log_path
    try:
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        entry = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "event": event}
        entry.update(payload)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def truncate(text, max_chars):
    if text is None:
        return None, False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def classify_action(action):
    """Normalize a ScanResponse's `action` field into allow/alert/block.

    pan.dev's own docs only enumerate "allow"/"block". Palo Alto's own
    community Claude Code skill
    (github.com/PaloAltoNetworks/prisma-airs-integrations) additionally
    returns "alert". Any value that isn't exactly "allow" or "block" --
    including "alert" and anything not yet documented -- is treated as
    "alert": warn, don't silently allow, don't hard-block either. See the
    plan's D4.
    """
    if action == "block":
        return "block"
    if action == "allow":
        return "allow"
    return "alert"


def feature_summary(scan_response):
    """Flatten prompt_detected/response_detected/tool_detected into a short
    list of triggered flags for logging and human-readable warnings --
    deliberately without any raw snippet content (D7)."""
    features = []
    for key in ("prompt_detected", "response_detected"):
        block = (scan_response or {}).get(key)
        if isinstance(block, dict):
            for flag, value in block.items():
                if value:
                    features.append("{}.{}".format(key, flag))
    tool_detected = (scan_response or {}).get("tool_detected")
    if isinstance(tool_detected, dict):
        threats = ((tool_detected.get("summary") or {}).get("threats")) or []
        for threat in threats:
            features.append("tool_detected.{}".format(threat))
    return features
