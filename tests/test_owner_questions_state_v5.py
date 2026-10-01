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


def test_v4_pinned_and_rows_copied():
    assert hashlib.sha256((HERE / "owner_questions_state_v4.json").read_bytes()).hexdigest() == B.V4_SHA
    for r4, r5 in zip(V4["rows"], ROWS):
        assert (r4["no"], r4["id"]) == (r5["no"], r5["id"])
        if r4["status"] != "TBD_OWNER":
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
            assert r["status"] == want, qid


def test_a9_15_amendments_govern_and_no_contingency_reading():
    for qid in L.A915_AMENDED:
        r = _answered(qid)
        assert r["status"] == "AMENDED_BY_A9_15"
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
    tbd = [r for r in ROWS if r["status"] == "TBD_OWNER"]
    assert [r["id"] for r in tbd] == DOC["open_owner_questions"] == ["MPV3Q-01"]
    assert "answer_pointer" not in tbd[0] and tbd[0]["blocks"] == ["BLOCKS_LOCK_1"]
    assert DOC["counts"]["TBD_OWNER"] == DOC["tbd_owner_count"] == 1


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
