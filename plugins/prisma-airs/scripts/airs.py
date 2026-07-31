"""Minimal stdlib HTTP client for the Prisma AIRS AI Runtime Scan API.

Deliberately dependency-free (urllib + json only): these hooks must run in
any Claude Code environment with no install step. Endpoints, headers, and
limits below are as documented at
https://pan.dev/prisma-airs/api/airuntimesecurity/ -- see
reference/scan-api.md for the exact citations.
"""
import json
import urllib.error
import urllib.request

SYNC_SCAN_PATH = "/v1/scan/sync/request"
ASYNC_SCAN_PATH = "/v1/scan/async/request"
RESULTS_PATH = "/v1/scan/results"
REPORTS_PATH = "/v1/scan/reports"

# pan.dev limitations: "2 MB maximum payload size per synchronous scan
# request" / "5 MB maximum payload size per asynchronous scan request".
MAX_SYNC_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ASYNC_PAYLOAD_BYTES = 5 * 1024 * 1024

# pan.dev's limitations page says "Asynchronous requests are limited to a
# maximum of 25 batched requests"; its own Python SDK usage page says
# "Batch (Asyncronous) Scan supports up to 5 Scan Request Objects". The two
# pan.dev pages contradict each other -- we take the smaller number so a
# caller here never submits more than either page allows.
MAX_ASYNC_BATCH_ITEMS = 5

# pan.dev: "up to a maximum of 5 scan IDs" / "5 report_ids" per results/reports call.
MAX_IDS_PER_QUERY = 5


class AirsError(Exception):
    """Base class for anything that stops a scan from producing a verdict."""


class AirsUnreachable(AirsError):
    """No HTTP response at all: DNS failure, connection refused, timeout.

    pan.dev documents no client-side guidance for this case (verified: not
    on the error-codes page, the API overview, or the use-cases page) --
    callers decide their own fail-open/fail-closed policy. See config.py's
    `on_unreachable` and docs/decisions.
    """


class AirsHTTPError(AirsError):
    """The service responded, but not with 2xx. See reference/errors.md
    for the documented meaning of each status code."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        super().__init__("AIRS returned HTTP {}: {}".format(status_code, body))


def _request(config, method, path, body=None, query=None):
    url = config.base_url + path
    if query:
        url += "?" + "&".join("{}={}".format(k, v) for k, v in query.items())
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    # pan.dev: API-key auth via the `x-pan-token` header.
    req.add_header("x-pan-token", config.api_key or "")
    try:
        with urllib.request.urlopen(req, timeout=config.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise AirsHTTPError(exc.code, raw) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AirsUnreachable(str(exc)) from exc


def sync_scan(config, contents, tr_id=None, session_id=None, metadata=None):
    """POST /v1/scan/sync/request -- one prompt/response/tool_event, one verdict."""
    body = {"ai_profile": config.ai_profile(), "contents": contents}
    if tr_id:
        body["tr_id"] = tr_id
    if session_id:
        body["session_id"] = session_id
    merged_metadata = {"app_name": config.app_name}
    if metadata:
        merged_metadata.update({k: v for k, v in metadata.items() if v})
    body["metadata"] = merged_metadata
    return _request(config, "POST", SYNC_SCAN_PATH, body=body)


def async_scan(config, items):
    """POST /v1/scan/async/request.

    `items` is a list of (req_id, contents) pairs. Returns the
    AsyncScanResponse: `{received, scan_id, report_id, source}` for the
    whole submitted batch -- per-item verdicts are fetched afterwards via
    `get_scan_results`, correlated by req_id.
    """
    if len(items) > MAX_ASYNC_BATCH_ITEMS:
        raise ValueError(
            "async_scan: {} items exceeds the {}-item batch limit "
            "(see reference/scan-api.md)".format(len(items), MAX_ASYNC_BATCH_ITEMS)
        )
    body = []
    for req_id, contents in items:
        scan_req = {
            "ai_profile": config.ai_profile(),
            "contents": contents,
            "metadata": {"app_name": config.app_name},
        }
        body.append({"req_id": req_id, "scan_req": scan_req})
    return _request(config, "POST", ASYNC_SCAN_PATH, body=body)


def get_scan_results(config, scan_ids):
    """GET /v1/scan/results?scan_ids=... -- up to 5 IDs, comma-separated.

    Returns a list of `{source, req_id, status, scan_id, result}` entries
    -- one per req_id submitted in the original async batch.
    """
    if len(scan_ids) > MAX_IDS_PER_QUERY:
        raise ValueError("get_scan_results: max {} scan_ids per call".format(MAX_IDS_PER_QUERY))
    return _request(config, "GET", RESULTS_PATH, query={"scan_ids": ",".join(scan_ids)})


def get_threat_reports(config, report_ids):
    """GET /v1/scan/reports?report_ids=... -- up to 5 IDs, comma-separated."""
    if len(report_ids) > MAX_IDS_PER_QUERY:
        raise ValueError("get_threat_reports: max {} report_ids per call".format(MAX_IDS_PER_QUERY))
    return _request(config, "GET", REPORTS_PATH, query={"report_ids": ",".join(report_ids)})
