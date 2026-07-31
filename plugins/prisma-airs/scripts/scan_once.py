#!/usr/bin/env python3
"""One-shot scan CLI for slash commands that need a single ad-hoc verdict
rather than the gate's batch/exit-code contract: the setup flow's test
call and the MCP tool-poisoning audit.

Usage:
    echo '{"prompt": "..."}' | python3 scan_once.py
    python3 scan_once.py --content "some prompt text"
    python3 scan_once.py --server-name my-mcp-server --method tools/list \\
        --tool-invoked get_file --input-file tool-schema.json

Prints a JSON verdict summary to stdout. Exit code is 0 for "allow", 1 for
"alert"/"block", 2 if the scan couldn't be completed at all.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import airs
from config import Config
from hook_common import classify_action, feature_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", help="plain prompt text; reads stdin if omitted "
                                           "and no --server-name is given")
    parser.add_argument("--as", dest="content_field", default="prompt",
                         choices=["prompt", "response", "code_prompt", "code_response"],
                         help="which ScanContent field --content/stdin fills (default: prompt)")
    parser.add_argument("--server-name", help="build a tool_event scan instead of a plain one")
    parser.add_argument("--method", choices=["tools/list", "tools/call"], default="tools/list")
    parser.add_argument("--ecosystem", default="mcp")
    parser.add_argument("--tool-invoked")
    parser.add_argument("--input-file", help="file whose contents become tool_event.input")
    parser.add_argument("--output-file", help="file whose contents become tool_event.output")
    args = parser.parse_args()

    config = Config.load(os.getcwd())
    if not config.is_configured():
        print(json.dumps({"error": "not_configured",
                           "message": "Run /prisma-airs-setup first."}))
        return 2

    if args.server_name:
        tool_event = {"metadata": {
            "ecosystem": args.ecosystem,
            "method": args.method,
            "server_name": args.server_name,
        }}
        if args.tool_invoked:
            tool_event["metadata"]["tool_invoked"] = args.tool_invoked
        if args.input_file:
            with open(args.input_file, "r", encoding="utf-8") as f:
                tool_event["input"] = f.read()
        if args.output_file:
            with open(args.output_file, "r", encoding="utf-8") as f:
                tool_event["output"] = f.read()
        if "input" not in tool_event and "output" not in tool_event:
            print(json.dumps({"error": "bad_args",
                               "message": "--server-name needs --input-file and/or --output-file."}))
            return 2
        contents = [{"tool_event": tool_event}]
    else:
        text = args.content if args.content is not None else sys.stdin.read()
        contents = [{args.content_field: text}]

    try:
        result = airs.sync_scan(config, contents)
    except airs.AirsUnreachable as exc:
        print(json.dumps({"error": "unreachable", "message": str(exc)}))
        return 2
    except airs.AirsHTTPError as exc:
        print(json.dumps({"error": "http_error", "status": exc.status_code, "body": exc.body}))
        return 2

    verdict = classify_action(result.get("action", "allow"))
    print(json.dumps({
        "action": result.get("action"),
        "verdict": verdict,
        "category": result.get("category"),
        "scan_id": result.get("scan_id"),
        "report_id": result.get("report_id"),
        "features": feature_summary(result),
    }, indent=2))
    return 0 if verdict == "allow" else 1


if __name__ == "__main__":
    sys.exit(main())
