"""The gates, as tests. Each one encodes a way the tool could quietly lie."""
import copy, json, subprocess, sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".maintenance" / "scripts"))
from render import exit_code, render, validate  # noqa: E402

BASE = json.loads((ROOT / "examples" / "example-run.json").read_text(encoding="utf-8"))


def mutate(**_):
    return copy.deepcopy(BASE)


# --- schema rails: the report structurally cannot make these claims -----------

@pytest.mark.parametrize("name,mut", [
    ("class C cannot pass",        lambda r: r["controls"][2].update(verdict="pass")),
    ("fail needs a finding",       lambda r: r["controls"][0].update(finding_refs=[])),
    ("fail needs remediation",     lambda r: r["controls"][0].pop("remediation")),
    ("class B needs confidence",   lambda r: r["controls"][5].pop("confidence")),
    ("inherited needs attestation", lambda r: r["controls"][5].pop("inherited_evidence")),
    ("no 'compliant' field",       lambda r: r.update(compliant=True)),
])
def test_schema_rejects(name, mut):
    r = mutate(); mut(r)
    with pytest.raises(jsonschema.ValidationError):
        validate(r)


def test_baseline_is_valid():
    validate(BASE)


# --- CI semantics: a broken collector is never green -------------------------

def test_fail_exits_1():
    assert exit_code(mutate(), {"fail"}) == 1


def test_partial_below_threshold_exits_0():
    r = mutate()
    for c in r["controls"]:
        if c["verdict"] == "fail":
            c["verdict"] = "pass"
    assert exit_code(r, {"fail"}) == 0


def test_broken_collector_never_green():
    r = mutate()
    r["tooling"]["collectors"][3]["status"] = "failed"
    assert exit_code(r, {"fail"}) == 2
    assert exit_code(r, {"fail", "partial"}) == 2


def test_insufficient_evidence_never_green():
    r = mutate()
    r["controls"][1]["verdict"] = "insufficient_evidence"
    assert exit_code(r, {"fail"}) == 2


# --- rendering is deterministic ----------------------------------------------

def test_render_is_byte_stable():
    assert render(BASE) == render(copy.deepcopy(BASE))


def test_report_states_out_of_scope():
    md = render(BASE)
    assert "Nicht technisch geprueft" in md
    assert "ORP.3.A1" in md


# --- watcher ------------------------------------------------------------------
#
# Every test below runs watch.py against a pytest tmp_path state file via
# --state, never against the live .maintenance/state/sources.json. Before this
# fix, _watch() deleted and overwrote the *real* baseline with fixture-derived
# hashes -- harmless in a throwaway CI checkout, but destructive against the
# live working tree a desktop scheduled run operates on. The committed
# sources.json in this repo's history is in fact a pytest artifact from that
# bug (its fetched_at timestamps are 2026-07-11T03:52:25, milliseconds apart
# across all seven sources -- the exact --today used here, not a real fetch).


def _watch(fixtures, today, state_path, state_reset=True):
    if state_reset and state_path.exists():
        state_path.unlink()
    out = subprocess.run(
        [sys.executable, ".maintenance/scripts/watch.py", "--fixtures",
         f".maintenance/tests/fixtures/{fixtures}",
         "--state", str(state_path),
         "--write-state", "--today", today],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return json.loads(out.stdout), out.returncode


def test_watch_baseline_then_idempotent(tmp_path):
    state_path = tmp_path / "sources.json"
    rec, _ = _watch("v1", "2026-07-11", state_path)
    assert any(c["kind"] == "baseline_established" for c in rec["changes"])
    rec2, _ = _watch("v1", "2026-07-11", state_path, state_reset=False)
    assert not any(c["source_id"] == "bsi-grundschutz-kompendium" for c in rec2["changes"])


def test_watch_detects_building_block_change(tmp_path):
    state_path = tmp_path / "sources.json"
    _watch("v1", "2026-07-11", state_path)
    rec, _ = _watch("v2", "2026-07-11", state_path, state_reset=False)
    mod = [c for c in rec["changes"] if c["kind"] == "segment_modified"]
    assert any(c["segment_id"] == "CON.1" for c in mod)
    # the diff must be verbatim, not paraphrased
    assert "TLS 1.3" in next(c for c in mod if c["segment_id"] == "CON.1")["verbatim_diff"]


def test_watch_deadline_boundary(tmp_path):
    state_path = tmp_path / "sources.json"
    rec, _ = _watch("v1", "2026-06-01", state_path)
    assert not [c for c in rec["changes"] if c["source_id"] == "regulatory-deadlines"]
    rec, _ = _watch("v1", "2026-07-11", state_path, state_reset=False)
    assert any(c["kind"] == "deadline_approaching" for c in rec["changes"])
    rec, _ = _watch("v1", "2026-09-20", state_path, state_reset=False)
    assert any(c["kind"] == "deadline_passed" for c in rec["changes"])


def test_watch_never_touches_live_state(tmp_path):
    """The isolation fix itself, as a regression test: whatever the test suite
    does, the real baseline file must not move."""
    live = ROOT / ".maintenance" / "state" / "sources.json"
    before = live.read_bytes() if live.exists() else None
    _watch("v1", "2026-07-11", tmp_path / "sources.json")
    after = live.read_bytes() if live.exists() else None
    assert before == after
