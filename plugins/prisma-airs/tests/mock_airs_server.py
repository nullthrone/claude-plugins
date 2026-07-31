"""A minimal stand-in for the Prisma AIRS Scan API, used only by
test_hooks.py. Not shipped -- lives outside every auto-discovered plugin
component directory.

Verdict is driven by magic marker strings found in the scanned content, so
tests stay deterministic without needing to sequence responses:

    AIRS_TEST_BLOCK    -> action: "block"
    AIRS_TEST_ALERT    -> action: "alert"   (Palo Alto's own community skill
                                              documents this value; pan.dev
                                              itself only documents allow/block)
    AIRS_TEST_TIMEOUT  -> sleeps 2s past a 1s client timeout, to exercise
                          AirsUnreachable
    AIRS_TEST_429      -> HTTP 429
    AIRS_TEST_500      -> HTTP 500
    (anything else)    -> action: "allow"
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

SCANS = {}  # scan_id -> {req_id: result}
_scan_counter = [0]


def _verdict_for(text):
    if "AIRS_TEST_BLOCK" in text:
        return "block"
    if "AIRS_TEST_ALERT" in text:
        return "alert"
    return "allow"


def _content_text(contents):
    parts = []
    for item in contents or []:
        for key in ("prompt", "response", "code_prompt", "code_response"):
            if key in item:
                parts.append(item[key])
        tool_event = item.get("tool_event")
        if tool_event:
            parts.append(json.dumps(tool_event))
    return " ".join(parts)


def _result_for(contents):
    text = _content_text(contents)
    if "AIRS_TEST_429" in text or "AIRS_TEST_500" in text:
        return None  # handled by the caller as an HTTP error
    if "AIRS_TEST_TIMEOUT" in text:
        time.sleep(2)
    action = _verdict_for(text)
    result = {
        "scan_id": "test-scan-id", "report_id": "test-report-id",
        "category": "malicious" if action != "allow" else "benign",
        "action": action, "timeout": False, "error": False, "errors": [],
    }
    if action != "allow":
        result["prompt_detected"] = {"injection": True}
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # keep test output quiet

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw else None

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Expected for the AIRS_TEST_TIMEOUT case: the client already
            # hit its own timeout and closed the connection before this
            # handler's artificial sleep finished.
            pass

    def do_POST(self):
        body = self._read_body()
        if self.path == "/v1/scan/sync/request":
            text = _content_text(body.get("contents"))
            if "AIRS_TEST_429" in text:
                return self._send_json(429, {"error": {"message": "Too Many Requests"}})
            if "AIRS_TEST_500" in text:
                return self._send_json(500, {"error": {"message": "Internal Server Error"}})
            return self._send_json(200, _result_for(body.get("contents")))
        if self.path == "/v1/scan/async/request":
            _scan_counter[0] += 1
            scan_id = "test-scan-{}".format(_scan_counter[0])
            results = {}
            for item in body:
                req_id = item["req_id"]
                results[req_id] = _result_for(item["scan_req"]["contents"])
            SCANS[scan_id] = results
            return self._send_json(200, {
                "received": "2026-07-31T00:00:00Z", "scan_id": scan_id,
                "report_id": "test-report-{}".format(scan_id), "source": "AI-Runtime-API",
            })
        self._send_json(404, {"error": {"message": "not found"}})

    def do_GET(self):
        if self.path.startswith("/v1/scan/results"):
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            scan_ids = []
            for pair in query.split("&"):
                if pair.startswith("scan_ids="):
                    scan_ids = pair[len("scan_ids="):].split(",")
            entries = []
            for scan_id in scan_ids:
                for req_id, result in SCANS.get(scan_id, {}).items():
                    entries.append({
                        "source": "AI-Runtime-API", "req_id": req_id,
                        "status": "complete", "scan_id": scan_id, "result": result,
                    })
            return self._send_json(200, entries)
        self._send_json(404, {"error": {"message": "not found"}})


def start(port=0):
    server = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
