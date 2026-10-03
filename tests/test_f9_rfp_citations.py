"""F9 RFP citations re-based onto the registered RFP clauses through the RVM re-base (rfp_citations_f9).

Every F9 record that carried rfp_citation_status OWNER_STATED_PENDING_RFP_REGISTRATION now carries the registered clause
ids of the RVM row(s) the re-base maps for the corresponding requirement (or an explicit UNMAPPED status with reason);
the REQUIREMENT_AS_RECORDED label no longer says the official RFP is absent.
Run: python -m pytest -q tests/test_f9_rfp_citations.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
F9_DIR = ROOT / "docs" / "architecture" / "freeze_candidate"
F9 = json.loads((F9_DIR / "architecture_freeze_candidate_v1.json").read_text(encoding="utf-8"))
RVM = json.loads((ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "docs/requirements/rfp_official/rfp_registration_v1.json").read_text(encoding="utf-8"))
PENDING = "OWNER_STATED_PENDING_RFP_REGISTRATION"
ROWS = {r["id"]: r for r in RVM["rows"]}

if str(ROOT / "docs" / "decisions" / "application") not in sys.path:
    sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


C = _load("rfp_citations_f9_under_test", F9_DIR / "rfp_citations_f9.py")
L = _load("a9_16_lib_rfp_cit_test", ROOT / "docs" / "decisions" / "application" / "a9_16_lib.py")

# record -> RVM rows (the expected mapping; clause ids are always derived from the RVM rows)
EXPECTED = {
    "parameters[id=AFC-SY-PPU-07].a9_16": ["RVM-19"],
    "parameters[id=AFC-SY-XE-01].a9_16": ["RVM-10"],
    "parameters[id=AFC-SY-PWR-01].rfp_citation": ["RVM-04"],
    "parameters[id=AFC-SY-MASS-WET].rfp_citation": ["RVM-06"],
    "architecture_gates[id=AG-12].blocking_evidence": ["RVM-01", "RVM-02"],
    "open_owner_questions[id=F9-OQ-02]": ["RVM-01", "RVM-02"],
    "a9_16_owner_answers_applied[question_id=F9-OQ-02]": ["RVM-01", "RVM-02"],
    "a9_16_owner_answers_applied[question_id=F2-OQ-01]": ["RVM-09"],
    "a9_16_owner_answers_applied[question_id=F2-OQ-03]": ["RVM-08"],
    "a9_16_owner_answers_applied[question_id=RVMQ-01]": ["RVM-19"],
    "a9_16_owner_answers_applied[question_id=OD12]": ["RVM-19"],
    "a9_16_owner_answers_applied[question_id=XA9Q-07]": ["RVM-10"],
    "a9_16_owner_answers_applied[question_id=OD6]": ["RVM-10"],
    "a9_16_owner_answers_applied[question_id=A9.15 governing_rule]": ["RVM-10"],
}


def _walk(o, out, path=""):
    if isinstance(o, dict):
        if "rfp_citation_status" in o:
            out.append((path, o))
        for k, v in o.items():
            _walk(v, out, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _walk(v, out, f"{path}/{i}")
    return out


def test_no_pending_rfp_label_survives_in_f9():
    recs = _walk(F9, [])
    assert recs
    for path, r in recs:
        assert r["rfp_citation_status"] != PENDING, path
        assert r["rfp_citation_status"] in (C.REGISTERED, C.UNMAPPED), path
        if r["rfp_citation_status"] == C.UNMAPPED:
            assert r["rfp_citation_unmapped_reason"], path


def test_mapping_table_matches_rvm_rebase():
    recs = {r["record"]: r for r in F9["rfp_citations"]["records"]}
    assert set(recs) == set(EXPECTED)
    reg_ids = {c["id"] for c in REG["clauses"]}
    for rec, rows in EXPECTED.items():
        r = recs[rec]
        assert r["status"] == C.REGISTERED and r["rvm_rows"] == rows, rec
        want = []
        for rid in rows:                                     # exactly the clause ids the RVM re-base gives the rows
            assert ROWS[rid]["requirement_origin"] == "RFP_CLAUSE"
            want += [c for c in ROWS[rid]["rfp_clauses"] if c not in want]
        assert r["rfp_clause_ids"] == want, rec
        assert set(want) <= reg_ids


def test_relabelled_records_keep_step1_label_as_history():
    p = {x["id"]: x for x in F9["parameters"]}
    for pid in ("AFC-SY-PPU-07", "AFC-SY-XE-01"):
        a = p[pid]["a9_16"]
        assert a["rfp_citation_status"] == "REGISTERED_CLAUSE"
        assert a["rfp_citation_status_as_applied"] == PENDING
        assert "pending registration" not in p[pid]["basis"]
    assert "official RFP registered (AG-15)" not in p["AFC-SY-PPU-07"]["evidence_to_advance"]
    g = {x["id"]: x for x in F9["architecture_gates"]}["AG-12"]["blocking_evidence"]
    assert g["rfp_clause_ids"] == ["RFP-P18-04", "RFP-P18-05", "RFP-P18-06"]
    for pid in ("AFC-SY-PWR-01", "AFC-SY-MASS-WET"):
        assert p[pid]["value_label"] == "REQUIREMENT_AS_RECORDED"
        assert p[pid]["rfp_citation"]["rfp_citation_status"] == "REGISTERED_CLAUSE"


def test_requirement_as_recorded_label_is_truthful():
    d = F9["value_labels"]["REQUIREMENT_AS_RECORDED"]
    assert "official RFP not in the repository" not in d
    assert "docs/requirements/rfp_official/rfp_registration_v1.json" in d and "registered by sha256" in d
    assert "requirement_frozen = false" in d


def test_unmapped_is_explicit_never_guessed():
    m = C.mapping("AFC-UP-FI-01", "NO-SUCH-Q", RVM, L.answer)
    assert m["status"] == C.UNMAPPED and m["reason"]
    assert "clauses" not in m


def test_correspondence_fails_closed(monkeypatch):
    bad = dict(C.CORRESPONDENCE)
    bad[("AG-12", "F9-OQ-02")] = [("RVM-01", "VERBATIM_FACT", "not in the owner text", "180-230 km")]
    monkeypatch.setattr(C, "CORRESPONDENCE", bad)
    with pytest.raises(SystemExit):
        C.mapping("AG-12", "F9-OQ-02", RVM, L.answer)
    bad[("AG-12", "F9-OQ-02")] = [("RVM-01", "RVM_REBASE_DECISION", None, None)]   # RVM-01 cites no F9-OQ-02
    with pytest.raises(SystemExit):
        C.mapping("AG-12", "F9-OQ-02", RVM, L.answer)
