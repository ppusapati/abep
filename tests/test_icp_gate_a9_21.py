"""A9.21 ICP_GATE: the mandatory ICP go / no-go gate before LOCK-1 (GNG-ICP-01) in the RVM and the F9 gate machinery.

Owner decision A9.21 item 4 approves the EXISTENCE and PLACEMENT of the gate (before LOCK-1, fail closed: missing
evidence -> NOT_EVALUATED, never GO) and NO criterion; the recorder proposal RP-A919-01 (a) - (c) is preserved verbatim
for owner review and never evaluated.
Run: python -m pytest -q tests/test_icp_gate_a9_21.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RVM_DIR = ROOT / "docs" / "requirements" / "rvm_a9"
F9_DIR = ROOT / "docs" / "architecture" / "freeze_candidate"
RVM_JSON = RVM_DIR / "rvm_a9_v1.json"
F9_JSON = F9_DIR / "architecture_freeze_candidate_v1.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


for _d in (str(RVM_DIR), str(F9_DIR)):
    if _d not in sys.path:
        sys.path.insert(0, _d)
G = _load("a9_21_icp_gate_under_test", RVM_DIR / "a9_21_icp_gate.py")
F21 = _load("a9_21_f9_under_test", F9_DIR / "a9_21_f9.py")
RVM = json.loads(RVM_JSON.read_text(encoding="utf-8"))
F9 = json.loads(F9_JSON.read_text(encoding="utf-8"))
# synthetic test root: the cited owner decision and evidence files exist there with the pinned sha256 (TEST DATA ONLY)
TROOT = Path(tempfile.mkdtemp(prefix="icp_gate_test_"))


def _put(rel, text):
    f = TROOT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return hashlib.sha256(f.read_bytes()).hexdigest()


DEC_SHA = _put("docs/decisions/OD_future_owner_criteria.json", '{"test": "synthetic owner criteria"}')
SHA = _put("docs/evidence/x.json", '{"test": "synthetic evidence"}')
DEC = {"path": "docs/decisions/OD_future_owner_criteria.json", "sha256": DEC_SHA}
ACCEPTED = {"status": "OWNER_ACCEPTED", "owner_decision": DEC,
            "items": [{"id": "C1", "text": "owner criterion one"}, {"id": "C2", "text": "owner criterion two"}]}


def _evaluate(criteria, evidence):
    return G.evaluate(criteria, evidence, root=TROOT)


def _ev(cid, result="MET", sha=SHA):
    return {"criterion_id": cid, "result": result, "source": {"path": "docs/evidence/x.json", "sha256": sha}}


def _rvm_gate():
    gs = [g for g in RVM["owner_approved_gates"] if g["id"] == G.GATE_ID]
    assert len(gs) == 1
    return gs[0]


def _f9_gate():
    gs = [g for g in F9["pre_lock1_gates"] if g["id"] == G.GATE_ID]
    assert len(gs) == 1
    return gs[0]


# ------------------------------------------------------------------------------------------ registration / placement
def test_gate_registered_in_rvm_before_lock1_fail_closed():
    g = _rvm_gate()
    assert g["placement"] == "BEFORE_LOCK-1" and g["precedes"] == "LOCK-1" and g["mandatory"] is True
    assert g["status"] == "NOT_EVALUATED" and g["criteria"] == "PENDING_OWNER_ACCEPTANCE" and g["evidence"] == []
    assert g["lock1_release_reportable"] is False
    oa = g["owner_approved"]
    assert oa["decision"] == "A9.21" and oa["item"] == "ICP_GATE"
    assert oa["decision_code"] == "ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1"
    assert "existence and placement of a mandatory ICP go/no-go gate before LOCK-1" in oa["verbatim_excerpt"]
    assert "`NOT_EVALUATED`, not GO" in oa["verbatim_excerpt"]
    assert g == G.gate_record()
    # the gate is not a requirement row: rows, limits and the RFP mapping are unchanged
    for r in RVM["rows"]:
        assert G.GATE_ID not in json.dumps(r, ensure_ascii=False)
    app = RVM["a9_21_owner_answers_applied"]
    assert [a["question_id"] for a in app] == ["ICP_GATE"]


def test_gate_has_own_id_not_in_ag_series_and_ag_numbering_unchanged():
    assert not G.GATE_ID.startswith("AG-")
    ag = [g["id"] for g in F9["architecture_gates"]]
    assert ag == [f"AG-{i:02d}" for i in range(1, 16)]
    for g in F9["architecture_gates"]:                       # AG approval (A9.13 F9-OQ-03) covers only AG-01..15
        assert g["owner_approved"]["decision_code"] == "AG_01_15_APPROVED_DETERMINING_EVIDENCE"
    f = _f9_gate()
    assert f["owner_approved"]["decision_code"] == "ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1"
    assert "AG_01_15" not in json.dumps(f)
    assert f["kind"] == "OWNER_APPROVED_PRE_LOCK1_GATE" and f["placement"] == "BEFORE_LOCK-1"
    assert f["current_status"] == "NOT_EVALUATED" and f["evidence_sufficient_for_freeze"] is False
    assert f["criteria"] == "PENDING_OWNER_ACCEPTANCE"
    assert f["sources"][0]["path"] == "docs/requirements/rvm_a9/rvm_a9_v1.json"


def test_recorder_proposal_preserved_verbatim_and_disposition_recorded():
    prop = [p for p in RVM["recorder_proposals_open_for_owner"] if p["id"] == "RP-A919-01"][0]
    for g in (_rvm_gate(), _f9_gate()):
        pc = g["proposed_criteria_for_owner_review"]
        assert pc["text_verbatim"] == prop["proposal"]
        assert pc["status"] == "NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"
        assert pc["is_criteria"] is False and pc["evaluated"] is False
        assert g["criteria"] == "PENDING_OWNER_ACCEPTANCE"          # the proposal is never the criteria
    assert prop["status"] == "RECORDER_PROPOSAL_OPEN_FOR_OWNER" and prop["is_owner_decision"] is False
    d = prop["a9_21_disposition"]
    assert d["registered_gate"] == G.GATE_ID and d["criteria_status"] == "PENDING_OWNER_ACCEPTANCE"


# ------------------------------------------------------------------------------------------ evaluator (fail closed)
@pytest.mark.parametrize("criteria", [None, "PENDING_OWNER_ACCEPTANCE", {}, {"status": "PENDING_OWNER_ACCEPTANCE"}])
def test_never_go_without_accepted_criteria(criteria):
    full = [_ev("C1"), _ev("C2")]
    assert _evaluate(criteria, full)["status"] == "NOT_EVALUATED"
    assert _evaluate(criteria, [])["status"] == "NOT_EVALUATED"


def test_never_go_without_evidence():
    assert _evaluate(ACCEPTED, [])["status"] == "NOT_EVALUATED"
    assert _evaluate(ACCEPTED, None)["status"] == "NOT_EVALUATED"
    r = _evaluate(ACCEPTED, [_ev("C1")])
    assert r["status"] == "NOT_EVALUATED" and r["missing"] == ["C2"]
    assert _evaluate(ACCEPTED, [_ev("C1"), _ev("C2", sha="not-a-sha")])["status"] == "NOT_EVALUATED"
    assert _evaluate(ACCEPTED, [_ev("C1"), _ev("C2", result="PASS")])["status"] == "NOT_EVALUATED"
    nodec = dict(ACCEPTED, owner_decision={"path": "x.json"})
    assert _evaluate(nodec, [_ev("C1"), _ev("C2")])["status"] == "NOT_EVALUATED"
    # only owner-accepted criteria with registered evidence for every criterion decide
    assert _evaluate(ACCEPTED, [_ev("C1"), _ev("C2")])["status"] == "GO"
    assert _evaluate(ACCEPTED, [_ev("C1"), _ev("C2", "NOT_MET")])["status"] == "NO_GO"


def test_unverifiable_citations_never_go():
    """Review fix: a well-formed but unverifiable sha pin (file missing, sha mismatch, path outside the root) is
    missing evidence, never GO."""
    full = [_ev("C1"), _ev("C2")]
    outside = Path(tempfile.mkdtemp(prefix="icp_gate_outside_")) / "OD_outside.json"
    outside.write_text('{"test": "synthetic owner criteria"}', encoding="utf-8")
    for bad in ({"path": "docs/decisions/NO_SUCH.json", "sha256": DEC_SHA},          # file missing
                {"path": DEC["path"], "sha256": "b" * 64},                            # sha mismatch
                {"path": "../" + outside.parent.name + "/" + outside.name, "sha256": DEC_SHA},  # escapes the root
                {"path": str(outside), "sha256": DEC_SHA}):                           # absolute, outside the root
        r = _evaluate(dict(ACCEPTED, owner_decision=bad), full)
        assert r["status"] == "NOT_EVALUATED", bad
    for src in ({"path": "docs/evidence/missing.json", "sha256": SHA}, {"path": "docs/evidence/x.json",
                                                                         "sha256": "c" * 64}):
        ev = [_ev("C1"), dict(_ev("C2"), source=src)]
        r = _evaluate(ACCEPTED, ev)
        assert r["status"] == "NOT_EVALUATED" and r["missing"] == ["C2"], src
    # default root is the repository: the synthetic files do not exist there
    assert G.evaluate(ACCEPTED, full)["status"] == "NOT_EVALUATED"


def test_proposal_text_never_used_as_criteria():
    full = [_ev("a"), _ev("b"), _ev("c"), _ev("C1"), _ev("C2")]
    pc = _rvm_gate()["proposed_criteria_for_owner_review"]
    assert _evaluate(pc, full)["status"] == "NOT_EVALUATED"
    forged = dict(pc, status="OWNER_ACCEPTED", owner_decision=DEC,
                  items=[{"id": "C1", "text": "x"}, {"id": "C2", "text": "y"}])
    assert _evaluate(forged, full)["status"] == "NOT_EVALUATED"           # carries the RP-A919-01 source
    text = G.proposal()["proposal"]
    parts = [text.split("(a) ")[1].split("; (b)")[0], text.split("(b) ")[1].split("; (c)")[0],
             text.split("(c) ")[1].rstrip(".")]
    copied = {"status": "OWNER_ACCEPTED", "owner_decision": DEC,
              "items": [{"id": k, "text": t} for k, t in zip("abc", parts)]}
    assert _evaluate(copied, full)["status"] == "NOT_EVALUATED"           # proposal wording copied into items


# ------------------------------------------------------------------------------------------ LOCK-1
def test_lock1_cannot_be_reported_released_while_gate_not_go():
    assert F9["lock1_precondition"]["lock1_release_reportable"] is False
    assert F9["lock1_precondition"]["mandatory_pre_lock1_gates"] == [{"id": G.GATE_ID, "status": "NOT_EVALUATED"}]
    assert G.lock1_release_reportable([{"status": "NOT_EVALUATED", "mandatory": True}]) is False
    assert G.lock1_release_reportable([{"status": "NO_GO", "mandatory": True}]) is False
    assert G.lock1_release_reportable([]) is False
    assert G.lock1_release_reportable([{"status": "GO", "mandatory": True}]) is True
    # review fix: no mandatory gate in the list is not 'all mandatory gates GO' (all([]) is not a release)
    assert G.lock1_release_reportable([{"status": "NOT_EVALUATED", "mandatory": False}]) is False
    assert G.lock1_release_reportable([{"status": "GO", "mandatory": False}]) is False


def test_architecture_status_never_frozen_while_pre_lock1_gate_not_go():
    b = _load("f9_builder_icp_gate_test", F9_DIR / "build_freeze_candidate.py")
    ok = [{"evidence_sufficient_for_freeze": True}] * 15
    # build() passes the AG gates plus the pre-LOCK-1 gates; the ICP gate is sufficient only when GO
    assert b.architecture_status(ok + [_f9_gate()]) == "INVESTIGATION_HYPOTHESIS"
    assert _f9_gate()["evidence_sufficient_for_freeze"] is False
    built = b.build()
    assert built["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    assert built["pre_lock1_gates"] == F9["pre_lock1_gates"]
    assert F9["architecture_status"] == "INVESTIGATION_HYPOTHESIS"


# ------------------------------------------------------------------------------------------ F9 consumes the RVM record
def _ref(key, pointer=""):
    return {"path": key, "pointer": pointer}


def test_f9_refuses_missing_or_inconsistent_registration():
    good = copy.deepcopy(RVM["owner_approved_gates"])
    assert F21.pre_lock1_gates(good, _ref)[0]["current_status"] == "NOT_EVALUATED"
    with pytest.raises(SystemExit):
        F21.pre_lock1_gates([], _ref)
    with pytest.raises(SystemExit):
        F21.pre_lock1_gates(good + good, _ref)
    go = copy.deepcopy(good)
    go[0]["status"] = "GO"                                   # a GO claim without accepted criteria / evidence
    with pytest.raises(SystemExit):
        F21.pre_lock1_gates(go, _ref)
    crit = copy.deepcopy(good)
    crit[0]["criteria"] = crit[0]["proposed_criteria_for_owner_review"]["text_verbatim"]
    with pytest.raises(SystemExit):
        F21.pre_lock1_gates(crit, _ref)
    moved = copy.deepcopy(good)
    moved[0]["placement"] = "AFTER_LOCK-1"
    with pytest.raises(SystemExit):
        F21.pre_lock1_gates(moved, _ref)


def test_criterion_without_text_never_go():
    """Review follow-up 2026-10-03: an accepted criteria item without its own text (or not a dict) cannot be shown to
    differ from the recorder proposal; it is refused (NOT_EVALUATED), never GO."""
    full = [_ev("C1"), _ev("C2")]
    for items in ([{"id": "C1"}, {"id": "C2", "text": "y"}], [{"id": "C1", "text": "  "}, {"id": "C2", "text": "y"}],
                  ["C1", {"id": "C2", "text": "y"}]):
        assert G._uses_proposal(dict(ACCEPTED, items=items)) is True
        assert _evaluate(dict(ACCEPTED, items=items), full)["status"] != "GO"
