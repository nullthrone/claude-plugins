#!/usr/bin/env python3
"""
watch.py — Change detection against the sources in catalog/sources.yaml.

Deliberately LLM-free. Fetch, hash, diff. Nothing in this file interprets a
legal text; it only establishes *that* something moved and *where*. The
interpretation happens in the catalog-curator subagent, which can only open a
pull request. See docs/decisions/0002-proposer-disposer-catalog-updates.md.

Output: a change-record on stdout (schema/change-record.schema.json).
An empty `changes` array is the normal case and means the workflow does nothing.

Exit codes:
  0  ran successfully (with or without changes)
  2  one or more sources unreachable  -> the workflow must not treat this as "no changes"
  3  configuration error

Offline use:
  --fixtures <dir>   read source content from <dir>/<source_id>.txt instead of
                     the network. Used by the test suite; also the only way to
                     run this in a network-restricted sandbox.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]   # .maintenance/scripts/ -> repo root
STATE_PATH = ROOT / ".maintenance" / "state" / "sources.json"

EXIT_OK = 0
EXIT_UNREACHABLE = 2
EXIT_CONFIG = 3

MAX_DIFF_LINES = 400  # a curator prompt is useless if it is 800 pages long


# ---------------------------------------------------------------- extractors
#
# An extractor turns raw source content into an ordered mapping
# {segment_id: text}. This is the single most important design decision in the
# whole watcher: it determines whether a change surfaces as "CON.1 changed" or
# as "the PDF changed". The latter is worthless.


def extract_bsi_kompendium(text: str) -> dict[str, str]:
    """Split the IT-Grundschutz text layer into building blocks (CON.1, SYS.1.6, ...)."""
    pattern = re.compile(
        r"^(?P<id>(?:ISMS|ORP|CON|OPS|DER|APP|SYS|IND|NET|INF)\.[0-9]+(?:\.[0-9]+)*)\s+(?P<title>.+)$",
        re.MULTILINE,
    )
    return _split_on(text, pattern)


def extract_pdf_sections(text: str) -> dict[str, str]:
    """Numbered sections, e.g. '5.2 Component fields'."""
    pattern = re.compile(r"^(?P<id>[0-9]+(?:\.[0-9]+)*)\s+(?P<title>[A-Z].{3,80})$", re.MULTILINE)
    return _split_on(text, pattern)


def _html_to_text(markup: str) -> str:
    """Strip HTML to plain text, one line per block element.

    fetch() hands extractors the raw response body. For eur-lex that is HTML,
    not text -- "Article 1" lives inside `<p class="oj-ti-art">Article 1</p>`,
    never at the start of a source line the way the regex below assumes.
    Without this step, extract_eurlex_html's pattern never matches anything,
    _split_on falls back to a single `__document__` segment, and every diff is
    the entire raw markup. No external dependency: html.parser is stdlib, and
    this project is deliberately dependency-light on the watcher path.
    """
    from html.parser import HTMLParser
    import html as html_stdlib

    block_tags = {
        "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
        "table", "title", "article", "section",
    }

    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
            if tag in block_tags:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag in block_tags:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(markup)
    text = html_stdlib.unescape("".join(stripper.parts))
    # Trim each line so "^Article 1" anchors regardless of source indentation.
    return "\n".join(line.strip() for line in text.split("\n"))


def extract_eurlex_html(text: str) -> dict[str, str]:
    """Articles and annexes of an EUR-Lex document. Input is raw HTML."""
    pattern = re.compile(
        r"^(?P<id>(?:Article|Artikel|ANNEX|ANHANG)\s+[IVXLC0-9]+(?:\s*\([0-9a-z]+\))?)\b(?P<title>.*)$",
        re.MULTILINE,
    )
    return _split_on(_html_to_text(text), pattern)


def extract_whole(text: str) -> dict[str, str]:
    return {"__document__": text}


EXTRACTORS = {
    "bsi_kompendium": extract_bsi_kompendium,
    "pdf_sections": extract_pdf_sections,
    "eurlex_html": extract_eurlex_html,
    "edpb_listing": extract_whole,
    "bgbl_listing": extract_whole,
    "oj_l_series": extract_whole,
}


def _split_on(text: str, pattern: re.Pattern) -> dict[str, str]:
    marks = list(pattern.finditer(text))
    if not marks:
        return {"__document__": text}
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        seg_id = m.group("id").strip()
        body = text[m.start():end].strip()
        # Duplicate ids (e.g. table of contents + body) -> keep the longer one.
        if seg_id not in out or len(body) > len(out[seg_id]):
            out[seg_id] = body
    return out


def _norm(s: str) -> str:
    """Whitespace and page-furniture noise must not produce phantom diffs."""
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"Seite \d+ von \d+|Page \d+ of \d+", "", s)
    return s.strip()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------- fetching


def fetch(src: dict, fixtures: Path | None, timeout: int, ua: str) -> tuple[str | None, str | None]:
    """Return (content, error). content is None iff error is not None."""
    if fixtures is not None:
        f = fixtures / f"{src['id']}.txt"
        if not f.exists():
            return None, f"fixture missing: {f}"
        return f.read_text(encoding="utf-8"), None

    import ssl
    import urllib.error
    import urllib.request

    # The interpreter's own default trust store is not guaranteed to exist
    # (e.g. the Windows Store build of Python ships none at all --
    # ssl.get_default_verify_paths().cafile is None -- and every HTTPS fetch
    # fails with CERTIFICATE_VERIFY_FAILED). Prefer certifi's bundle when
    # present; fall back to the interpreter default otherwise.
    try:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None

    req = urllib.request.Request(src["url"], headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404 and src.get("expect_edition_bump"):
            # The URL carries the edition year. A 404 IS the signal.
            return None, "HTTP_404_EDITION_ROLLOVER"
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 - network layer, any failure is the same to us
        return None, f"{type(e).__name__}: {e}"

    if src["url"].lower().endswith(".pdf"):
        try:
            import pdfplumber  # noqa: PLC0415
            import io

            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages), None
        except ImportError:
            return None, "pdfplumber not installed"
    return raw.decode("utf-8", errors="replace"), None


# --------------------------------------------------------------------- deadlines


def check_deadlines(lead_days: int, today: date) -> list[dict]:
    mappings = yaml.safe_load((ROOT / "catalog" / "mappings.yaml").read_text(encoding="utf-8"))
    out = []
    for fw_id, fw in mappings["frameworks"].items():
        for ctl in fw.get("controls", []):
            dl = ctl.get("deadline")
            if not dl:
                continue
            days = (date.fromisoformat(dl) - today).days
            if days < 0:
                out.append({
                    "source_id": "regulatory-deadlines",
                    "framework": fw_id,
                    "kind": "deadline_passed",
                    "segment_id": ctl["control_id"],
                    "summary": f"Deadline {dl} has passed ({-days} days ago).",
                    "requires_decision": False,
                })
            elif days <= lead_days:
                out.append({
                    "source_id": "regulatory-deadlines",
                    "framework": fw_id,
                    "kind": "deadline_approaching",
                    "segment_id": ctl["control_id"],
                    "summary": f"Deadline {dl} in {days} days. Severity boost applies.",
                    "requires_decision": False,
                })
    return out


# ------------------------------------------------------------------------ main


def run(args) -> tuple[dict, int]:
    try:
        cfg = yaml.safe_load((ROOT / "catalog" / "sources.yaml").read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"config error: {e}", file=sys.stderr)
        return {}, EXIT_CONFIG

    # --state overrides where the baseline is read from AND written to (tests,
    # and any caller that wants to keep the live baseline untouched).
    state_path = Path(args.state) if getattr(args, "state", None) else STATE_PATH

    defaults = cfg.get("defaults", {})
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    new_state = dict(state)
    changes: list[dict] = []
    unreachable: list[dict] = []
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    fixtures = Path(args.fixtures) if args.fixtures else None

    for src in cfg["sources"]:
        sid = src["id"]

        if src["type"] == "deadline":
            changes.extend(check_deadlines(src.get("lead_time_days", 90), today))
            continue

        content, err = fetch(
            src,
            fixtures,
            src.get("timeout_seconds", defaults.get("timeout_seconds", 60)),
            defaults.get("user_agent", "compliance-audit"),
        )

        if err == "HTTP_404_EDITION_ROLLOVER":
            changes.append({
                "source_id": sid,
                "framework": src["framework"],
                "kind": "edition_rollover",
                "segment_id": None,
                "summary": (
                    f"URL for {sid} returns 404. The URL carries the edition year, so a "
                    f"new edition has most likely been published. The curator must locate "
                    f"the new URL and re-baseline. This is not an error."
                ),
                "requires_decision": True,
                "source_url": src["url"],
            })
            continue

        if err:
            unreachable.append({"source_id": sid, "error": err})
            continue

        extractor = EXTRACTORS[src.get("extractor", "whole")]
        segments = {k: _norm(v) for k, v in extractor(content).items()}
        hashes = {k: _sha(v) for k, v in segments.items()}
        prev = state.get(sid, {}).get("segments", {})

        new_state[sid] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "doc_sha256": _sha(_norm(content)),
            "segments": hashes,
        }

        if not prev:
            changes.append({
                "source_id": sid,
                "framework": src["framework"],
                "kind": "baseline_established",
                "segment_id": None,
                "summary": f"No prior state for {sid}. Baselined {len(hashes)} segments.",
                "requires_decision": False,
                "source_url": src["url"],
            })
            continue

        added = sorted(set(hashes) - set(prev))
        removed = sorted(set(prev) - set(hashes))
        modified = sorted(k for k in set(hashes) & set(prev) if hashes[k] != prev[k])

        # publication-type sources: any movement is a triage item, not a diff.
        if src["type"] == "publication":
            if modified or added:
                changes.append({
                    "source_id": sid,
                    "framework": src["framework"],
                    "kind": "publication",
                    "segment_id": None,
                    "summary": src.get("triage_hint", "Listing changed. Triage required."),
                    "requires_decision": True,
                    "source_url": src["url"],
                    "relevant_controls": src.get("relevant_controls", []),
                })
            continue

        for seg in modified:
            old_text = state[sid].get("text", {}).get(seg, "")
            diff = list(difflib.unified_diff(
                old_text.split(". "),
                segments[seg].split(". "),
                lineterm="",
                n=1,
            ))[:MAX_DIFF_LINES]
            changes.append({
                "source_id": sid,
                "framework": src["framework"],
                "kind": "segment_modified",
                "segment_id": seg,
                "summary": f"{seg} changed in {sid}.",
                "hash_before": prev[seg],
                "hash_after": hashes[seg],
                "verbatim_diff": "\n".join(diff) if diff else "(previous text not retained; re-baseline)",
                "requires_decision": True,
                "source_url": src["url"],
            })
        for seg in added:
            changes.append({
                "source_id": sid, "framework": src["framework"], "kind": "segment_added",
                "segment_id": seg, "summary": f"New segment {seg} in {sid}.",
                "hash_after": hashes[seg], "verbatim_diff": segments[seg][:4000],
                "requires_decision": True, "source_url": src["url"],
            })
        for seg in removed:
            changes.append({
                "source_id": sid, "framework": src["framework"], "kind": "segment_removed",
                "segment_id": seg, "summary": f"Segment {seg} no longer present in {sid}.",
                "hash_before": prev[seg], "requires_decision": True, "source_url": src["url"],
            })

        # Retain text of changed segments only -> state file stays small but the
        # next diff has something to diff against.
        new_state[sid]["text"] = {
            k: segments[k] for k in set(modified) | set(added)
        }

    record = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog_version": json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"],   # the plugin version IS the catalog version
        "changes": changes,
        "unreachable": unreachable,
    }

    if args.write_state and not unreachable:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(new_state, indent=2, sort_keys=True), encoding="utf-8")

    # --state-out always writes the candidate state, decoupled from the
    # unreachable gate above -- callers that promote per-source (rather than
    # all-or-nothing) need the candidate even when some sources failed.
    if getattr(args, "state_out", None):
        args.state_out.parent.mkdir(parents=True, exist_ok=True)
        args.state_out.write_text(json.dumps(new_state, indent=2, sort_keys=True), encoding="utf-8")

    # A source we could not reach is not "no change". Treating it as green is
    # exactly how a compliance gate becomes decorative.
    code = EXIT_UNREACHABLE if unreachable else EXIT_OK
    return record, code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="read sources from a directory instead of the network")
    ap.add_argument("--write-state", action="store_true")
    ap.add_argument(
        "--state",
        help="override the state file path (read+write); default is the live "
             ".maintenance/state/sources.json. Use this to keep test/scratch "
             "runs from touching the real baseline.",
    )
    ap.add_argument(
        "--state-out",
        type=Path,
        help="always write the candidate state here, regardless of --write-state "
             "or whether any source was unreachable.",
    )
    ap.add_argument("--today", help="override today's date (ISO), for deadline tests")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    record, code = run(args)
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
