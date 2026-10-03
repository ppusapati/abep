"""Owner-question state v5 (A9.16 step 1): v4 + A9.7 lane questions with the A9.8 .. A9.14 answers and A9.15 amendments."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "budgets" / "owner_decisions"
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402
import a9_later_lib as X  # noqa: E402


def _builder():
    spec = importlib.util.spec_from_file_location("state_v5", HERE / "build_owner_questions_state_v5.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()
DOC = B.build()
ROWS = DOC["rows"]
BY_ID = {}
for _r in ROWS:
    BY_ID.setdefault(_r["id"], []).append(_r)
V4 = json.loads((HERE / "owner_questions_state_v4.json").read_text(encoding="utf-8"))


def _answered(qid):
    sel = [r for r in BY_ID[qid] if r.get("v4_status") == "TBD_OWNER" or r.get("kind") == B.A97_KIND
           or r["status"] == "TBD_OWNER"]
    assert len(sel) == 1, qid
    return sel[0]


def test_outputs_are_current_and_parse():
    for path, text in B.outputs(DOC).items():
        assert path.read_text(encoding="utf-8") == text, path.name
    json.loads((HERE / "owner_questions_state_v5.json").read_text(encoding="utf-8"))


# A9.17 .. A9.21 overlay keys (the only keys a later owner decision adds to / changes on a copied row)
LATER_STATUS_KEYS = {"status", "status_detail", "pre_a9_17_status", "pre_a9_17_status_detail", "later_owner_decisions",
                     "later_governing_reading", "governing_reading_status", "rfp_registered_document"}
LATER_NOTE_KEYS = {"later_owner_decisions", "external_input_status"}


def test_v4_pinned_and_rows_copied():
    assert hashlib.sha256((HERE / "owner_questions_state_v4.json").read_bytes()).hexdigest() == B.V4_SHA
    for r4, r5 in zip(V4["rows"], ROWS):
        assert (r4["no"], r4["id"]) == (r5["no"], r5["id"])
        if r4["status"] != "TBD_OWNER":
            if r4["id"] in B.LATER_ROWS:          # A9.17 .. A9.21 status change; everything else identical
                assert r5["pre_a9_17_status"] == r4["status"] and r5["status"].startswith("AMENDED_BY_A9_"), r4["id"]
                assert {k: v for k, v in r5.items() if k not in LATER_STATUS_KEYS} == \
                       {k: v for k, v in r4.items() if k not in ("status", "status_detail")}, r4["id"]
            elif r4["id"] in B.LATER_NOTES:       # records only, status unchanged
                assert {k: v for k, v in r5.items() if k not in LATER_NOTE_KEYS} == r4, r4["id"]
            else:
                assert r5 == r4, r4["id"]
        else:
            assert r5["v4_status"] == "TBD_OWNER"
            new = ("status", "status_detail", "answer_pointer", "answer_excerpt", "answer_sha256")
            assert {k: v for k, v in r5.items() if k in r4 and k not in new} == \
                   {k: v for k, v in r4.items() if k not in new}
            assert all(not r4.get(k) for k in ("answer_pointer", "answer_excerpt", "answer_sha256"))
    assert [r["no"] for r in ROWS] == list(range(1, len(ROWS) + 1))


def test_v4_sha_mismatch_refused(monkeypatch):
    monkeypatch.setattr(B, "V4_SHA", "0" * 64)
    with pytest.raises(SystemExit):
        B.load_v4()


def test_decision_file_tamper_refused(monkeypatch):
    bad = dict(L.DECISIONS)
    jp, _, mp, msha, lab = bad["A9.14"]
    bad["A9.14"] = (jp, "f" * 64, mp, msha, lab)
    monkeypatch.setattr(L, "DECISIONS", bad)
    with pytest.raises(SystemExit):
        L._load()


def test_every_owner_answer_lands_on_exactly_one_row_with_pointer_and_verbatim():
    for key in L.ORDER:
        if key == "A9.15":
            continue
        d = L.LOADED[key]
        for qid in L.decision_ids(key):
            r = _answered(qid)
            assert r["answer_decision"] == key
            assert r["answer_sha256"] == d["json_sha256"] == hashlib.sha256((ROOT / d["json"]).read_bytes()).hexdigest()
            assert r["answer_verbatim_sha256"] == hashlib.sha256((ROOT / d["md"]).read_bytes()).hexdigest()
            assert r["answer_pointer"] == f"{d['json']}#/decisions/{qid}"
            assert r["answer_excerpt"] in d["md_text"]
            assert f"— {qid} —" in r["answer_excerpt"].splitlines()[0]
            assert r["decision_code"] == d["doc"]["decisions"][qid]["answer"]
            want = "AMENDED_BY_A9_15" if qid in L.A915_AMENDED else "ANSWERED_BY_" + key.replace(".", "_")
            if qid in B.LATER_ROWS:              # later owner decision A9.19 / A9.20 / A9.21 amends the answer
                assert r["pre_a9_17_status"] == want, qid
                want = "AMENDED_BY_" + B.LATER_ROWS[qid][0].replace(".", "_")
            assert r["status"] == want, qid


def test_a9_15_amendments_govern_and_no_contingency_reading():
    for qid in L.A915_AMENDED:
        r = _answered(qid)
        if qid in B.LATER_ROWS:                  # A9.19 amends / supersedes the A9.15 reading (kept as history)
            assert r["pre_a9_17_status"] == "AMENDED_BY_A9_15" and r["status"] == "AMENDED_BY_A9_19", qid
            assert r["governing_reading_status"] in ("SUPERSEDED_BY_A9_19", "AMENDED_IN_SCOPE_BY_A9_19"), qid
        else:
            assert r["status"] == "AMENDED_BY_A9_15"
        assert r["amended_by"]["decision"] == "A9.15"
        g = r["governing_reading"]["text"]
        assert g in L.LOADED["A9.15"]["md_text"] and f"/ {qid}:" in g
        assert not L.has_xe_contingency_wording(g)
        assert r["rfp_citation_status"] == "OWNER_STATED_PENDING_RFP_REGISTRATION"
    assert "NOT APPLICABLE" in _answered("XV2Q-01")["governing_reading"]["text"]
    assert "YES" in _answered("XA9Q-07")["governing_reading"]["text"]
    sup = {s["id"]: s for s in DOC["superseded_statements"]}
    assert L.has_xe_contingency_wording(sup["A9.13 owner_statements.xenon"]["text"])
    for s in sup.values():
        assert s["superseded_by"]["decision"] == "A9.15"
    assert DOC["a9_15_governing_statement"].startswith("The official RFP is the sole governing basis")
    assert "G-REUSE" in DOC["a9_15_scope_note"]
    assert not L.has_xe_contingency_wording("deferred until C1 is selected, but not because Xe is contingency-only")
    assert L.has_xe_contingency_wording("Xe stays contingency-only for C1")


def test_rfp_cited_answers_flagged_pending_registration():
    n = 0
    for r in ROWS:
        if "answer_excerpt" in r and r.get("answer_decision") in L.ORDER and "RFP(1)" in r["answer_excerpt"]:
            assert r["rfp_citation_status"] == "OWNER_STATED_PENDING_RFP_REGISTRATION", r["id"]
            n += 1
    assert n >= 5


def test_a9_7_lane_questions_rows():
    a97 = [r for r in ROWS if r.get("kind") == B.A97_KIND]
    assert len(a97) == 40
    assert {r["answer_decision"] for r in a97} == {"A9.9", "A9.13", "A9.14"}
    for r in a97:
        assert r["source_ref"]["path"]
    for r in a97:
        if r["answer_decision"] == "A9.9":
            assert r["application_status"].startswith("PENDING_STEP_2_MODEL_CHANGE")
    assert _answered("F9-OQ-03")["decision_code"] == "AG_01_15_APPROVED_DETERMINING_EVIDENCE"


def test_remaining_open_question_is_tbd_owner_without_answer():
    # A9.16 repair F11 (updated test): XV3Q-01 (Xe v3: does A9.15 change the A9.1 HIQ-06 ICP-feed 'contingency'
    # labels?) joins MPV3Q-01 as an open owner question - the A9.15 recorder flag is now tracked
    tbd = [r for r in ROWS if r["status"] == "TBD_OWNER"]
    assert [r["id"] for r in tbd] == DOC["open_owner_questions"] == ["MPV3Q-01", "XV3Q-01"]
    for r in tbd:
        assert "answer_pointer" not in r and r["blocks"] == ["BLOCKS_LOCK_1"]
    assert DOC["counts"]["TBD_OWNER"] == DOC["tbd_owner_count"] == 2
    xv3 = tbd[1]
    assert xv3["source_ref"]["path"] == "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"
    assert "separately declared contingency variants" in xv3["classification_basis"]


def test_no_pass_token_and_counts_consistent():
    txt = json.dumps(DOC)
    assert '"PASS"' not in txt
    assert sum(DOC["counts"].values()) == len(ROWS)
    assert DOC["answered_this_step_by_decision"] == {"A9.8": 16, "A9.9": 5, "A9.10": 10, "A9.11": 7, "A9.12": 14,
                                                     "A9.13": 22, "A9.14": 61}


def test_unanswered_v4_row_stays_tbd_owner(monkeypatch):
    # a v4 TBD_OWNER id that no owner decision answers stays TBD_OWNER (no answer is fabricated)
    real = L.decision_ids
    monkeypatch.setattr(L, "decision_ids", lambda k: [q for q in real(k) if q != "RVMQ-01"])
    doc = B.build()
    r = [x for x in doc["rows"] if x["id"] == "RVMQ-01"][0]
    assert r["status"] == "TBD_OWNER" and "answer_pointer" not in r
    assert "RVMQ-01" in doc["open_owner_questions"]


def test_missing_a9_7_answer_refused(monkeypatch):
    real = L.decision_ids
    monkeypatch.setattr(L, "decision_ids", lambda k: [q for q in real(k) if q != "F6-OQ-04"])
    with pytest.raises(SystemExit):
        B.build()


# ------------------------------------------------------------------------------------------- A9.17 .. A9.21
RVM_DOC = json.loads((ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "docs/requirements/rfp_official/rfp_registration_v1.json").read_text(encoding="utf-8"))


def _row(qid):
    sel = [r for r in ROWS if r["id"] == qid]
    assert len(sel) == 1, qid
    return sel[0]


def _norm(s):
    return " ".join(s.split())


def test_later_decisions_pinned_with_pointer_and_verbatim():
    n = 0
    for r in ROWS:
        for x in r.get("later_owner_decisions", []):
            d = X.LOADED[x["decision"]]
            assert x["decision_json_sha256"] == hashlib.sha256((ROOT / d["json"]).read_bytes()).hexdigest()
            assert x["decision_md_sha256"] == hashlib.sha256((ROOT / d["md"]).read_bytes()).hexdigest()
            assert x["pointer"].startswith(d["json"] + "#/")
            assert _norm(x["verbatim_excerpt"]) in _norm(d["md_text"]), (r["id"], x["decision"])
            assert x["relation"] in X.RELATIONS and x["scope"]
            n += 1
    assert n >= 30
    pins = {p["path"]: p["sha256"] for p in DOC["pins"]}
    for k in X.ORDER:
        assert pins[X.LOADED[k]["json"]] == X.LOADED[k]["json_sha256"]
        assert pins[X.LOADED[k]["md"]] == X.LOADED[k]["md_sha256"]


def test_later_decision_tamper_and_invented_excerpt_refused():
    bad = dict(X.DECISIONS)
    jp, _, mp, msha, lab = bad["A9.19"]
    bad["A9.19"] = (jp, "e" * 64, mp, msha, lab)
    with pytest.raises(SystemExit):
        X._load(bad)
    with pytest.raises(SystemExit):
        X.verbatim("A9.21", "the owner approved a 2 A ICP capacity margin")      # not in the record: refused
    with pytest.raises(SystemExit):
        X.record("A9.21", "ICP_GATE", "APPROVES", X.block("A9.21", "4. ICP go/no-go"), "x")   # unknown relation


def test_a9_19_a9_20_single_flight_configuration_and_c1_ground_only():
    want = {"OQ-A907-07": "AMENDED_BY_A9_19", "MPQ-01": "AMENDED_BY_A9_19", "XA9Q-07": "AMENDED_BY_A9_19",
            "XV2Q-01": "AMENDED_BY_A9_19", "OD6": "AMENDED_BY_A9_19", "OD5": "AMENDED_BY_A9_19",
            "OD-XE-5": "AMENDED_BY_A9_19", "R6-Q1": "AMENDED_BY_A9_19", "OD-M5": "AMENDED_BY_A9_19",
            "HWQ-09": "AMENDED_BY_A9_19", "OQ-A907-01": "AMENDED_BY_A9_20",
            "MQ-05": "AMENDED_BY_A9_21", "WEB-ACC-2": "AMENDED_BY_A9_21"}
    assert DOC["a9_17_21"]["rows_status_changed"] == want
    for qid, st in want.items():
        assert _row(qid)["status"] == st, qid
    for qid in ("OQ-A907-07", "MPQ-01"):                 # no C1 flight variant: the earlier reading is history
        r = _row(qid)
        assert r["governing_reading_status"] == "SUPERSEDED_BY_A9_19"
        assert {x["relation"] for x in r["later_owner_decisions"]} == {"SUPERSEDES"}
        assert "No conventional hollow cathode." in r["later_governing_reading"]["text"]
    for qid in ("XA9Q-07", "XV2Q-01", "OD6"):            # Xe ROLE only; the capability answer stands
        r = _row(qid)
        assert r["governing_reading_status"] == "AMENDED_IN_SCOPE_BY_A9_19"
        assert any("ROLE of Xe only" in x["scope"] for x in r["later_owner_decisions"])
        assert not L.has_xe_contingency_wording(r["later_governing_reading"]["text"])
    for qid in ("OD-XE-5", "R6-Q1", "OD-M5", "HWQ-09"):  # C1 'fallback' rows
        r = _row(qid)
        assert "fallback" in r["answer_excerpt"]                      # verbatim historical answer kept
        assert {x["decision"] for x in r["later_owner_decisions"]} == {"A9.19", "A9.20"}
    lt = DOC["a9_17_21"]
    assert lt["flight_configuration"] == "hall_icp_neutralizer"
    assert list(lt["ground_reference"]) == ["hall_c1_reference"]
    assert lt["ground_reference"]["hall_c1_reference"].startswith("GROUND_ONLY_LAB_REFERENCE")
    sup = DOC["superseded_statements_a9_19"]
    assert {s["superseded_by"]["decision"] for s in sup} == {"A9.19"}
    for s in sup:
        assert s["text"] in L.LOADED["A9.15"]["md_text"]
    # quoted historical question text stays verbatim (the v4 text is unchanged)
    v4q = {r["id"]: r["question"] for r in V4["rows"]}
    assert _row("OQ-A907-07")["question"] == v4q["OQ-A907-07"] and "hall_c1_reference" in v4q["OQ-A907-07"]


def test_a9_21_rows_and_recorder_proposal():
    mq = _row("MQ-05")
    assert "Keep 6.05 kg only as a provisional planning floor" in mq["later_owner_decisions"][0]["verbatim_excerpt"]
    assert mq["later_owner_decisions"][0]["decision_code"] == "KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08"
    web = _row("WEB-ACC-2")
    assert "05 October 2026 at 17:00" in web["later_owner_decisions"][0]["verbatim_excerpt"]
    assert web["rfp_registered_document"]["rfp_number"] == REG["document"]["rfp_number"]
    assert web["rfp_registered_document"]["pdf_sha256"] == REG["document"]["sha256"]
    rp = _row("RP-A919-01")
    prop = [p for p in RVM_DOC["recorder_proposals_open_for_owner"] if p["id"] == "RP-A919-01"][0]
    assert rp["status"] == "ANSWERED_BY_A9_21" and rp["decision_code"] == "ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1"
    assert rp["question"] == prop["proposal"] == rp["open_part"]["preserved_text"]
    assert rp["open_part"]["status"] == "NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"
    assert "`NOT_EVALUATED`, not GO" in rp["answer_excerpt"]
    assert rp["no"] == len(ROWS) and "RP-A919-01" not in DOC["open_owner_questions"]
    for qid, before in (("F1Q-03", "ANSWERED_BY_A9_13"), ("OQ-F78-04", "ANSWERED_BY_A9_13"),
                        ("OD3", "ANSWERED_BY_A9_14"), ("OQ-F4-05", "ANSWERED_BY_A9_13")):
        r = _row(qid)                                      # external inputs stay TBD: status unchanged
        assert r["status"] == before and r["external_input_status"].startswith("TBD_EXTERNAL_INPUT"), qid
        assert "pre_a9_17_status" not in r
    for qid in ("P1Q-07", "F5-OQ-01", "F5-OQ-02", "F9-OQ-02", "F0-OQ-02", "F9-OQ-03"):
        r = _row(qid)
        ok = {"CONFIRMS", "INPUT_STAYS_TBD"} | ({"PERFORMS_OWNER_ACT"} if qid == "F9-OQ-03" else set())
        assert {x["relation"] for x in r["later_owner_decisions"]} <= ok, qid
        assert "pre_a9_17_status" not in r
    assert DOC["counts"]["ANSWERED_BY_A9_21"] == 1 and DOC["counts"]["AMENDED_BY_A9_21"] == 2


def test_rfp_registration_now_and_ag15_closed_by_a9_22():
    now = DOC["rfp_registration_now"]
    assert now["registration"]["status"] == "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY"
    assert now["registration"]["pdf_sha256"] == REG["document"]["sha256"]
    assert now["registration"]["pdf_in_repository"] is False
    assert now["rvm_rebase"]["ag_15_status"].startswith("CLOSED") and now["rvm_rebase"]["requirements_snapshot"] == "FROZEN"
    g3 = DOC["a9_22_g3"]                                 # A9.22 G3 recorded with pointers + sha256
    assert g3["decision_code"] == "AG15_CLOSED_SNAPSHOT_FROZEN" and g3["decision_json_sha256"] == X.LOADED["A9.22"]["json_sha256"]
    assert g3["rvm_closure_record"]["frozen_rows"] == [r["id"] for r in RVM_DOC["rows"]
                                                      if r["requirement_origin"] == "RFP_CLAUSE"]
    assert g3["f9_gate"]["evidence_sufficient_for_freeze"] is True
    assert g3["f9_gate"]["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    f9oq3 = _row("F9-OQ-03")
    assert f9oq3["status"] == "ANSWERED_BY_A9_13"                     # the owner act changes no row status
    rec = [x for x in f9oq3["later_owner_decisions"] if x["decision"] == "A9.22"]
    assert len(rec) == 1 and rec[0]["relation"] == "PERFORMS_OWNER_ACT"
    assert "AG-15 is approved for closure." in rec[0]["verbatim_excerpt"]
    bad_rvm = copy.deepcopy(RVM_DOC)
    bad_rvm["rfp_rebase"]["ag15_closure"]["frozen_rows"] = bad_rvm["rfp_rebase"]["ag15_closure"]["frozen_rows"][1:]
    with pytest.raises(SystemExit):
        B.a922_g3(bad_rvm, REG, json.loads(B.F9.read_text(encoding="utf-8")))
    bad = copy.deepcopy(REG)
    bad["status"] = "DRAFT"
    with pytest.raises(SystemExit):
        B.rfp_registration_now(bad, RVM_DOC)


def test_unreviewed_later_target_refused(monkeypatch):
    monkeypatch.setitem(B.LATER_NOTES, "NOT-A-ROW", [("A9.21", "H2_6", "CONFIRMS",
                                                      ("3. H2-6 frozen builder", {}), "x")])
    with pytest.raises(SystemExit):
        B.build()
    monkeypatch.delitem(B.LATER_NOTES, "NOT-A-ROW")
    monkeypatch.setitem(B.LATER_NOTES, "P2Q-07", [("A9.21", "HW_PROGRAMME", "AMENDS",
                                                   ("9. P2 impedance map", {}), "x")])
    with pytest.raises(SystemExit):                        # a status-changing relation must be a reviewed LATER_ROWS entry
        B.build()


F9_REL = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"


def test_rp_a919_01_gate_location_pointer_only():
    """RP-A919-01 points to where GNG-ICP-01 lives (RVM owner_approved_gates + F9 pre_lock1_gates); semantics unchanged."""
    rp = _row("RP-A919-01")
    gl = rp["gate_location"]
    assert gl["gate_id"] == "GNG-ICP-01" and gl["defined_in"] == "docs/requirements/rvm_a9/a9_21_icp_gate.py"
    assert (ROOT / gl["defined_in"]).is_file()
    f9 = json.loads((ROOT / F9_REL).read_text(encoding="utf-8"))
    docs = {"docs/requirements/rvm_a9/rvm_a9_v1.json": RVM_DOC, F9_REL: f9}
    assert [x["locator"] for x in gl["records"]] == ["owner_approved_gates[id=GNG-ICP-01]",
                                                     "pre_lock1_gates[id=GNG-ICP-01]"]
    for x in gl["records"]:
        node = docs[x["path"]]
        for part in x["pointer"].strip("/").split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        assert node["id"] == "GNG-ICP-01" and node["placement"] == "BEFORE_LOCK-1"
    # pointer only: no gate status / criteria copied; the row's answer semantics are unchanged
    assert "status" not in gl and "criteria" not in json.dumps(gl["records"])
    assert rp["status"] == "ANSWERED_BY_A9_21" and rp["open_part"]["status"] == "NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"
    assert rp["status_detail"].startswith("ANSWERED IN PART (A9.21 ICP_GATE")
    assert DOC["a9_17_21"]["gate_location"]["row"] == "RP-A919-01"
    assert DOC["counts"]["ANSWERED_BY_A9_21"] == 1


def test_gate_location_fails_closed():
    rows = copy.deepcopy(ROWS)
    f9 = json.loads((ROOT / F9_REL).read_text(encoding="utf-8"))
    bad = copy.deepcopy(RVM_DOC)
    bad["owner_approved_gates"] = []
    with pytest.raises(SystemExit):
        B.icp_gate_location(rows, bad, f9)
    bad_f9 = copy.deepcopy(f9)
    bad_f9["pre_lock1_gates"][0]["placement"] = "AFTER_LOCK-1"
    with pytest.raises(SystemExit):
        B.icp_gate_location(rows, RVM_DOC, bad_f9)


def test_md_step1_rfp_rule_labelled_history():
    """Review 2026-10-03: the step-1 'document is not registered' rule is history once the RFP is registered by hash;
    the companion document must not state it as the current rule next to 'RFP now: REGISTERED_BY_HASH...'."""
    md = (ROOT / "docs/budgets/owner_decisions/OWNER_QUESTIONS_STATE_v5.md").read_text(encoding="utf-8")
    assert "\nRFP rule: " not in md
    assert "RFP rule (A9.16 step-1 application rule, history;" in md
    assert "RFP now: REGISTERED_BY_HASH" in md
