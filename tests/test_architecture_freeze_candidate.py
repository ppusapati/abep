"""Tests for the A9.7 F9 architecture freeze candidate (docs/architecture/freeze_candidate/)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs" / "architecture" / "freeze_candidate"
BUILDER = LANE / "build_freeze_candidate.py"
JSON_PATH = LANE / "architecture_freeze_candidate_v1.json"
MD_PATH = LANE / "ARCHITECTURE_FREEZE_CANDIDATE.md"


def _load_builder():
    spec = importlib.util.spec_from_file_location("f9_freeze_candidate_builder_under_test", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def b():
    return _load_builder()


@pytest.fixture(scope="module")
def built(b):
    return b.build()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_committed_outputs_are_current(b, built):
    assert JSON_PATH.read_text(encoding="utf-8") == b.dumps(built)
    assert MD_PATH.read_text(encoding="utf-8") == b.render_md(built)


def test_architecture_stays_investigation_hypothesis(doc, b):
    assert doc["architecture_status"] == "INVESTIGATION_HYPOTHESIS"
    assert doc["frozen_reference_flight_architecture"] is False
    assert all(g["evidence_sufficient_for_freeze"] is False for g in doc["architecture_gates"])
    # the rule itself: one insufficient gate keeps the hypothesis status; all sufficient would freeze
    assert b.architecture_status([{"evidence_sufficient_for_freeze": True}]) == "FROZEN_REFERENCE_FLIGHT_ARCHITECTURE"
    assert b.architecture_status([{"evidence_sufficient_for_freeze": True},
                                  {"evidence_sufficient_for_freeze": False}]) == "INVESTIGATION_HYPOTHESIS"
    assert b.architecture_status([]) == "INVESTIGATION_HYPOTHESIS"


def test_required_gates_listed_with_blocking_evidence(doc):
    gates = {g["id"]: g for g in doc["architecture_gates"]}
    names = " ".join(g["gate"] for g in doc["architecture_gates"]).lower()
    for need in ("rvm rows", "hall credible", "icp-45", "coupled h-1 / icp thermal", "anode thermal",
                 "final anode material", "rf component ratings"):
        assert need in names, need
    plan_ids = {s["id"] for s in doc["evidence_plan"]}
    for g in gates.values():
        assert g["blocking_evidence"] and g["sources"] and g["evidence_plan_steps"]
        assert set(g["evidence_plan_steps"]) <= plan_ids
        assert "PASS" not in str(g["current_status"]).replace("'PASS': 0", "").replace("PASS 0", "")
    rvm = gates["AG-01"]["blocking_evidence"]["rows"]
    assert len(rvm) == len(_j("docs/requirements/rvm_a9/rvm_a9_v1.json")["rows"])
    assert all(r["status"]["hall_icp_neutralizer"] != "PASS" for r in rvm)
    assert {g for s in doc["evidence_plan"] for g in s["addresses_gates"]} == set(gates)


def test_parameter_row_contract(doc):
    fs_vocab = set(doc["freeze_status_vocabulary"])
    ecs = set(doc["evidence_classes"])
    ids = [r["id"] for r in doc["parameters"]]
    assert len(ids) == len(set(ids))
    for r in doc["parameters"]:
        for k in ("value", "tolerance", "evidence_class", "source", "freeze_status"):
            assert k in r, (r["id"], k)
        assert r["freeze_status"] in fs_vocab
        tbd = isinstance(r["value"], str) and r["value"].startswith("TBD")
        if tbd:
            assert r["evidence_class"] is None and r["freeze_status"] != "FREEZE_CANDIDATE", r["id"]
        else:
            assert r["evidence_class"] in ecs, r["id"]
        if r["freeze_status"] != "FREEZE_CANDIDATE":
            assert r["evidence_to_advance"], r["id"]
        if r.get("value_label") in ("PARAMETRIC_SENSITIVITY", "PARETO_SET"):
            assert r["freeze_status"] != "FREEZE_CANDIDATE", r["id"]
        assert r["source"]
        for s in r["source"]:
            assert (ROOT / s["path"]).is_file(), s["path"]
            assert len(s["sha256"]) == 64
            assert ("pointer" in s) or ("locator" in s)
    roll = doc["freeze_rollup"]
    assert roll["total"] == len(doc["parameters"]) == sum(roll["counts"].values())


def test_sections_cover_every_f9_bullet(doc, b):
    covered = {(r["section"], r["subsection"]) for r in doc["parameters"]}
    for sec, subs in b.SECTIONS.items():
        for sub in subs:
            assert (sec, sub) in covered, (sec, sub)
    directive = (ROOT / b.PINS["A97_MD"][0]).read_text(encoding="utf-8")
    for bullet in doc["a9_7_f9_coverage"]:
        assert bullet in directive


def test_a92_statuses_verbatim(doc):
    dec = _j("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json")
    assert doc["a9_2_statuses"]["statuses"] == dec["decisions"]["a9_10_statuses"]
    assert len(doc["a9_2_statuses"]["statuses"]) == 10
    assert doc["a9_2_statuses"]["statuses"]["Hall->ICP architecture"] == "INVESTIGATION_HYPOTHESIS"


def test_pareto_sets_carried_never_selected(doc):
    up = doc["upstream_pareto"]
    # A9.13 F9-OQ-01 (owner decision): the robust set is carried, representative selection deferred
    assert up["representative"]["status"] == "DEFERRED_BY_OWNER" and up["representative"]["selected"] is None
    assert up["representative"]["owner_question"] == "F9-OQ-01" and up["carried_to_lock1_as_set"] is True
    f78 = _j("docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json")
    want = sorted(m["design_id"] for blk in f78["robust"]["robust_pareto_by_P_set"].values() for m in blk["members"])
    assert sorted(m["design_id"] for m in up["robust_set"]["members"]) == want
    surv = {r["design_id"] for r in _j("docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json")["rows"]}
    assert up["nominal_pareto_union"]["n_members"] == len(surv)
    pareto_rows = [r for r in doc["parameters"] if isinstance(r["value"], dict) and r["value"].get("kind") ==
                   "PARETO_SET"]
    assert pareto_rows and all(r["freeze_status"] != "FREEZE_CANDIDATE" for r in pareto_rows)
    by_id = {r["id"]: r for r in doc["parameters"]}
    assert by_id["AFC-UP-IN-01"]["value"]["robust_set_values"] == sorted({m["area_m2"] for m in
                                                                         up["robust_set"]["members"]})


def test_f5_rows_imported_unchanged(doc):
    f5 = _j("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json")
    by_id = {r["id"]: r for r in doc["parameters"]}
    for p in f5["parameters"]:
        r = by_id["AFC-" + p["id"]]
        for k in ("value", "units", "tolerance", "evidence_class", "freeze_status"):
            assert r[k] == p[k], (p["id"], k)


def test_icp_geometry_all_tbd_until_p1_p2(doc):
    f6 = _j("docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json")
    by_id = {r["id"]: r for r in doc["parameters"]}
    for v in f6["design_vector"]["variables"]:
        r = by_id["AFC-" + v["id"]]
        assert r["value"].startswith("TBD") and r["freeze_status"] == "TBD_AFTER_EVIDENCE"


def test_owner_rollup_complete_and_unanswered(doc):
    ro = doc["owner_question_rollup"]
    v4 = _j("docs/budgets/owner_decisions/owner_questions_state_v4.json")
    want = sorted(r["no"] for r in v4["rows"] if r["status"] == "TBD_OWNER")
    assert sorted(q["no"] for q in ro["state_v4_tbd_owner"]) == want
    lane_files = ["docs/performance/PERFORMANCE_BASELINE_98fbbb9.json", "docs/performance/abep_core/parity_report_v1.json",
                  "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json",
                  "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json",
                  "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
                  "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json",
                  "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
                  "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json",
                  "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json"]
    lane_ids = {q["id"] for f in lane_files for q in _j(f)["open_owner_questions"]}
    assert {q["id"] for q in ro["a9_7_lane_questions"]} == lane_ids
    new = [q["id"] for q in doc["open_owner_questions"]]
    assert new == ro["new_f9_questions"] and all(i.startswith("F9-OQ-") for i in new)
    assert not set(new) & (lane_ids | {r["id"] for r in v4["rows"]})
    for q in doc["open_owner_questions"]:
        # A9.9 / A9.13 answered the four F9 questions (recorded, never answered by F9 itself)
        assert q["status_when_raised"] == "TBD_OWNER" and q["status"] == "OWNER_DECIDED"
        assert "answer" not in q and "owner_answer" not in q and q["answer_verbatim"]


def test_model_change_candidates_need_owner_and_history(doc):
    mcc = doc["model_change_candidates"]
    text = " ".join(m["finding"] for m in mcc)
    for need in ("F1-01", "F3-01", "F3-02", "G-05", "DIV-01", "DIV-02", "DIV-03"):
        assert need in text, need
    for m in mcc:
        # A9.9 F1Q-01 / UPSTREAM_ICD-Q7 / F9-OQ-04 (owner decisions) authorised all candidates; step 2 implements
        assert m["status"] == "OWNER_AUTHORISED_PENDING_STEP_2_MODEL_CHANGE" and m["implemented_here"] is False
        assert any("HISTORY" in x for x in m["required"]) and any("owner" in x for x in m["required"])
        assert m["owner_question"] and m["sources"]


def test_no_pass_no_winner_and_compliance(doc):
    for r in doc["parameters"]:
        assert r["freeze_status"] != "PASS"
    txt = json.dumps(doc).lower()
    for banned in ('"winner"', '"selected_design"', "best architecture", "recommended architecture"):
        assert banned not in txt, banned
    c = doc["compliance"]
    for k in ("existing_modules_modified", "frozen_data_modified", "decisions_modified", "wired_into_archengine",
              "tbd_converted_to_assumed_for_optimum", "single_optimum_or_winner_declared", "pass_declared",
              "owner_question_answered", "new_pytest_skips"):
        assert c[k] is False, k


def test_pins_verified_and_fail_closed(doc, b):
    for v in doc["pins"].values():
        assert hashlib.sha256((ROOT / v["path"]).read_bytes()).hexdigest() == v["sha256"]
    key = "A97_MD"
    saved = b.PINS[key]
    try:
        b.PINS[key] = (saved[0], "0" * 64)
        with pytest.raises(SystemExit):
            b.verify_pins()
    finally:
        b.PINS[key] = saved


def test_code_hygiene():
    for p in (BUILDER, Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in src, p.name
    bsrc = BUILDER.read_text(encoding="utf-8")
    assert "import abep_sim" not in bsrc and "from abep_sim" not in bsrc and "archengine import" not in bsrc


def test_no_freeze_candidate_depends_on_open_row(doc):
    """PHY-03: no FREEZE_CANDIDATE row names an OPEN (non-FREEZE_CANDIDATE) H1F / AFC row, and the Hall magnet supply
    count / trim slot (contingent on the OPEN coil arrangement H1F-MC-02) is not a freeze candidate."""
    import re
    rows = doc["parameters"]
    st = {r["id"]: r["freeze_status"] for r in rows}
    f5 = {p["id"]: p["freeze_status"] for p in _j("docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json")["parameters"]}
    for r in rows:
        if r["freeze_status"] != "FREEZE_CANDIDATE":
            continue
        txt = json.dumps([r["value"], r["basis"], r.get("evidence_note", "")])
        for d in set(re.findall(r"H1F-[A-Z]{2}-\d\d", txt)):
            assert f5.get(d) in (None, "FREEZE_CANDIDATE"), (r["id"], d)
        for d in set(re.findall(r"AFC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d\d", txt)) - {r["id"]}:
            assert st.get(d) in (None, "FREEZE_CANDIDATE"), (r["id"], d)
        srcs = json.dumps(r["source"])
        assert '"pointer": "/items/30' not in srcs, r["id"]          # A902-31 (H21-27, assumed (requirement))
    for pid in ("AFC-SY-PPU-03", "AFC-SY-PPU-04", "AFC-H1F-CO-14", "AFC-H1F-MC-02"):
        assert st[pid] != "FREEZE_CANDIDATE", pid
    ppu4 = next(r for r in rows if r["id"] == "AFC-SY-PPU-04")
    assert ppu4["evidence_class"] == "assumed"


def test_a9_19_a9_20_single_flight_configuration(doc, b):
    """A9.19: one Hall + one RF/ICP neutralizer for both supply modes (AIR_PRIMARY primary, XE_CONTINGENCY contingency
    / emergency), no hollow cathode; A9.20: hall_c1_reference only as a labelled GROUND_REFERENCE."""
    from abep_sim.design import a9_19_architecture as a919
    cfg = doc["configuration"]
    assert cfg["flight"] == "hall_icp_neutralizer" and cfg["flight_configurations"] == ["hall_icp_neutralizer"]
    assert "control_fallback" not in cfg and "primary" not in cfg
    assert cfg["ground_reference"] == {"configuration": "hall_c1_reference", "label": "GROUND_REFERENCE",
                                       "c1_status": "GROUND_ONLY_LAB_EQUIPMENT", "flight_candidate": False,
                                       "uses": a919.C1_ROLE["uses"]}
    fa = cfg["flight_architecture"]
    assert fa["hall_accelerators"] == 1 and fa["electron_source_neutralizer"]["count"] == 1
    assert fa["conventional_hollow_cathode"] == "NONE"
    assert fa["icp_feed_gas_baseline"]["primary"] == "G-REUSE"
    assert [(m["mode"], m["role"]) for m in fa["supply_modes"]] == [("AIR_PRIMARY", "PRIMARY"),
                                                                    ("XE_CONTINGENCY", "CONTINGENCY_EMERGENCY")]
    by = {r["id"]: r for r in doc["parameters"]}
    xe = by["AFC-SY-XE-01"]["value"]
    assert "XE_CONTINGENCY" in xe and "RFP-P17-05" in xe and "RFP-P18-08" in xe and "not a contingency" not in xe
    ctl = by["AFC-SY-CTL-01"]
    assert "C1-selected variant uses" not in ctl["evidence_note"] and "ground" in ctl["basis"]
    # AG-01: flight column always; any C1 column is labelled ground reference
    for r in doc["architecture_gates"][0]["blocking_evidence"]["rows"]:
        assert set(r["status"]) <= {"hall_icp_neutralizer", "ground_reference (hall_c1_reference)"}
        assert "hall_icp_neutralizer" in r["status"]
    rows = doc["a9_19_owner_answers_applied"]
    assert {r["decision"] for r in rows} == {"A9.19", "A9.20"}
    for r in rows:
        assert r["decision_json_sha256"] == a919.DECISIONS[r["decision"]]["json_sha256"]
        assert r["decision_md_sha256"] == a919.DECISIONS[r["decision"]]["md_sha256"]
    assert "PASS" not in json.dumps(rows)
    for k in ("A919", "A920", "A919_MD", "A920_MD"):
        assert k in b.PINS
