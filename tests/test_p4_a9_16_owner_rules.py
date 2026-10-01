"""A9.16 step 1 - owner rules applied to the P4 anode / collector / filter materials package
(docs/experiments/hall_icp/p4_anode_materials/p4_a9_16_rules.py, a9_16_application.py): A9.12 P4-OQ-01..05
(S5.10..S5.14; OQ-A907-05 as context); A9.13 F2-OQ-04 (S6.6, APP-FILTER); A9.15 reviewed.

Every numeric input here is SYNTHETIC_TEST_DATA_NOT_EVIDENCE (rule checks, not results).
Run: python -m pytest -q tests/test_p4_a9_16_owner_rules.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p4_anode_materials"
OUT_JSON = LANE / "p4_anode_materials_v1.json"
OUT_MD = LANE / "P4_ANODE_MATERIALS.md"
SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def R():
    return _load("p4_a9_16_rules_under_test", LANE / "p4_a9_16_rules.py")


@pytest.fixture(scope="module")
def APP():
    return _load("p4_a9_16_app_under_test", LANE / "a9_16_application.py")


@pytest.fixture(scope="module")
def S():
    return _load("p4_screening_under_test_a916", LANE / "p4_screening.py")


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _code(R, fn, *a, **kw):
    with pytest.raises(R.RuleRefusal) as e:
        fn(*a, **kw)
    return e.value.code


def _s1(R, **over):
    rec = {"basis": R.STAGE_1, "material": "MAT-X", "source": SYN, "preregistered_acceptance": "LOCK2-SYN",
           "T_limit_K": 900.0, "criteria_met": True,
           "conditions": {c: "REG-" + c for c in R.STAGE_1_CONDITIONS},
           "metrics": {m: "REG-" + m for m in R.STAGE_1_METRICS},
           "preregistered_exposure_duration_h": 100.0, "exposure_duration_h": 100.0}
    rec.update(over)
    return rec


def _s2(R, s1, **over):
    rec = {"basis": R.STAGE_2, "material": "MAT-X", "source": SYN, "preregistered_acceptance": "LOCK2-SYN",
           "T_limit_K": 880.0, "criteria_met": True, "stage_1_record": s1, "down_selected": True,
           "configuration": "REPLACEABLE_ANODE", "article": "H-1",
           "environment": {e: "REG-" + e for e in R.STAGE_2_ENVIRONMENT},
           "at_intended_continuous_use_condition": True}
    rec.update(over)
    return rec


# ------------------------------------------------------------------------------------------------ decision pins / rows
def test_p4_a9_16_decision_pins_and_rows(APP, d):
    for k, (j, js, m, ms) in APP.DEC.items():
        assert hashlib.sha256((REPO / j).read_bytes()).hexdigest() == js, k
        assert hashlib.sha256((REPO / m).read_bytes()).hexdigest() == ms, k
        assert d["pins"][k.replace(".", "")]["sha256"] == js
        assert d["pins"][k.replace(".", "") + "_MD"]["sha256"] == ms
    rows = [o for o in d["owner_answers_applied"] if o.get("step") == "A9.16 step 1"]
    got = {(o["kind"], o["question_id"]) for o in rows}
    for q in ("P4-OQ-01", "P4-OQ-02", "P4-OQ-03", "P4-OQ-04", "P4-OQ-05"):
        assert ("A9.12", q) in got
    assert ("A9.13", "F2-OQ-04") in got and ("A9.15", "RFP-COMPLIANT PROPELLANT POLICY") in got
    for o in rows:
        assert o["sha256"] == APP.DEC[o["kind"]][1] and o["path"] == APP.DEC[o["kind"]][0]
        assert o["tests"] and o["how_applied"]


def test_p4_a9_16_decisions_match_json_codes(APP):
    for qid, (dk, seq, code) in APP.DECIDED_OWNER_QUESTIONS.items():
        dec = json.loads((REPO / APP.DEC[dk][0]).read_text(encoding="utf-8"))["decisions"][qid]
        assert dec["status"] == "OWNER_DECIDED" and dec["answer"] == code and dec["sequenced_no"] == seq
    f2 = json.loads((REPO / APP.DEC["A9.13"][0]).read_text(encoding="utf-8"))["decisions"]["F2-OQ-04"]
    assert f2["answer"] == "COMPRESSOR_INLET_PLUS_APP_FILTER"


def test_p4_a9_16_verbatim_sections_copied(APP, d):
    """The verbatim .md governs: every applied row carries the owner's own text, cut from the pinned verbatim file."""
    for o in d["owner_answers_applied"]:
        if o.get("step") != "A9.16 step 1":
            continue
        md = (REPO / o["verbatim_path"]).read_text(encoding="utf-8")
        assert o["owner_answer_verbatim"] in md and len(o["owner_answer_verbatim"]) > 200
        if o["kind"] != "A9.15":
            assert o["sequenced_no"] in o["owner_answer_verbatim"] and o["question_id"] in o["owner_answer_verbatim"]
            assert "Decision:" in o["owner_answer_verbatim"]


def test_p4_a9_16_every_listed_test_exists(APP):
    names = set(globals())
    for row in APP.APPLIED:
        for t in row[6]:
            assert t in names, t


def test_p4_a9_16_questions_decided(APP, d):
    qs = {q["id"]: q for q in d["open_owner_questions"]}
    assert set(qs) == set(APP.DECIDED_OWNER_QUESTIONS)
    for qid, q in qs.items():
        assert q["status"] == "OWNER_DECIDED" and q["answer"] == APP.DECIDED_OWNER_QUESTIONS[qid][2]


# ------------------------------------------------------------------------------------------------ P4-OQ-01 staged
def test_p4_a9_16_stage_1_is_screening_only(R):
    c = R.validation_stage_record(_s1(R))
    assert c["limit_class"] == "COUPON_SUPPORTED_PROVISIONAL_LIMIT" and c["usable_for"] == ["design_screening"]
    assert R.limit_use_check(c, "design_screening")["T_limit_K"] == 900.0
    assert _code(R, R.limit_use_check, c, "p3_lock1_material_temperature_closure") == \
        "LIMIT_STAGE_INSUFFICIENT_FOR_USE"
    assert _code(R, R.limit_use_check, c, "final_flight_life_claim") == "LIMIT_STAGE_INSUFFICIENT_FOR_USE"
    # pre-registered acceptance, conditions and metrics are registration slots
    assert _code(R, R.validation_stage_record, _s1(R, preregistered_acceptance="TBD")) == \
        "NOT_EVALUATED_ACCEPTANCE_NOT_PREREGISTERED"
    cond = {c_: "REG" for c_ in R.STAGE_1_CONDITIONS if c_ != "electrical_bias_current_condition"}
    assert _code(R, R.validation_stage_record, _s1(R, conditions=cond)) == "NOT_EVALUATED_STAGE_1_CONDITIONS_TBD"
    cond_nc = {c_: "REG" for c_ in R.STAGE_1_CONDITIONS}
    cond_nc["thermal_cycling"] = "NOT_APPLICABLE"   # "thermal cycling where applicable"
    assert R.validation_stage_record(_s1(R, conditions=cond_nc))["stage"] == R.STAGE_1
    assert _code(R, R.validation_stage_record, _s1(R, metrics={"electrical": "x"})) == \
        "NOT_EVALUATED_STAGE_1_CONDITIONS_TBD"
    assert _code(R, R.validation_stage_record, _s1(R, criteria_met=False)) == "NOT_EVALUATED_CRITERIA_NOT_MET"
    for bad in (None, float("nan"), "900", True):
        assert _code(R, R.validation_stage_record, _s1(R, T_limit_K=bad)) == "INCOMPLETE_EVIDENCE"


def test_p4_a9_16_stage_2_needs_stage_1_and_article(R):
    s1 = R.validation_stage_record(_s1(R))
    c = R.validation_stage_record(_s2(R, s1))
    assert c["limit_class"] == "T_VALIDATED_CONTINUOUS"
    assert R.limit_use_check(c, "p3_lock1_material_temperature_closure")["T_limit_K"] == 880.0
    assert _code(R, R.limit_use_check, c, "final_flight_life_claim") == "LIMIT_STAGE_INSUFFICIENT_FOR_USE"
    assert _code(R, R.validation_stage_record, _s2(R, None)) == "NOT_EVALUATED_STAGE_1_MISSING"
    assert _code(R, R.validation_stage_record, _s2(R, dict(s1, material="OTHER"))) == "INCOMPLETE_EVIDENCE"
    assert _code(R, R.validation_stage_record, _s2(R, s1, down_selected=False)) == "NOT_EVALUATED_NOT_DOWN_SELECTED"
    assert _code(R, R.validation_stage_record, _s2(R, s1, configuration="COUPON")) == "INCOMPLETE_EVIDENCE"
    assert _code(R, R.validation_stage_record, _s2(R, s1, article="bench")) == "INCOMPLETE_EVIDENCE"
    assert _code(R, R.validation_stage_record, _s2(R, s1, environment={"plasma_environment": "x"})) == \
        "INCOMPLETE_EVIDENCE"
    assert _code(R, R.validation_stage_record, _s2(R, s1, at_intended_continuous_use_condition=False)) == \
        "INCOMPLETE_EVIDENCE"
    assert R.validation_stage_record(_s2(R, s1, configuration="REPLACEABLE_COLLECTOR", article="H-1/ICP"))


def test_p4_a9_16_stage_3_life(R):
    s2 = R.validation_stage_record(_s2(R, R.validation_stage_record(_s1(R))))
    base = {"basis": R.STAGE_3, "material": "MAT-X", "source": SYN, "preregistered_acceptance": "LOCK2-SYN",
            "T_limit_K": 870.0, "criteria_met": True, "stage_2_record": s2}
    c = R.validation_stage_record(dict(base, life_basis="FULL_DURATION"))
    assert R.limit_use_check(c, "final_flight_life_claim")["T_limit_K"] == 870.0
    assert _code(R, R.validation_stage_record, dict(base, life_basis="JUSTIFIED_ACCELERATED")) == "INCOMPLETE_EVIDENCE"
    assert R.validation_stage_record(dict(base, life_basis="JUSTIFIED_ACCELERATED", justification=SYN))
    assert _code(R, R.validation_stage_record, dict(base, life_basis="FULL_DURATION", stage_2_record=None)) == \
        "NOT_EVALUATED_STAGE_2_MISSING"


def test_p4_a9_16_non_validation_bases_refused(R):
    for b in ("MELTING_POINT", "SHORT_VENDOR_EXPOSURE", "GENERIC_AIR_USE_TEMPERATURE", "BRIEF_COUPON_TEST",
              "SUPPLIER_CONTINUOUS_RATING"):
        assert _code(R, R.validation_stage_record, _s1(R, basis=b)) == "NOT_CONTINUOUS_USE_VALIDATION"
    # a coupon exposed for less than the pre-registered duration is a brief coupon test
    assert _code(R, R.validation_stage_record, _s1(R, exposure_duration_h=10.0)) == "NOT_CONTINUOUS_USE_VALIDATION"
    assert _code(R, R.limit_use_check, {"stage": None}, "design_screening") == "NOT_CONTINUOUS_USE_VALIDATION"


def test_p4_a9_16_cr01_gate_requires_stage_2(R, S):
    assert set(S.T_VALIDATED_GATE_STAGES) == {R.STAGE_2, R.STAGE_3}
    r = {"id": "RQ-T", "criterion": "CR-01", "application": "APP-ANODE", "property": "T_validated_continuous",
         "kind": "min_with_margin", "value": 50.0, "unit": "K", "status": "OWNER_GIVEN", "source": SYN,
         "domain": ["bulk_property"]}
    p = {"id": "PR-T", "candidate": "CAND-X", "property": "T_validated_continuous", "value_si": 1000.0,
         "unit_si": "K", "condition": {}, "domain": ["bulk_property"], "source_id": SYN, "locator": SYN,
         "quantity_type": "measured", "evidence_level": SYN, "admissible_for_gate": True, "synthetic": True}
    top = {"value_si": 900.0, "unit_si": "K", "evidence_class": "measured", "source": SYN}
    for st in (None, R.STAGE_1, "COUPON_SUPPORTED_PROVISIONAL_LIMIT"):
        q = dict(p, validation_stage=st) if st else p
        o, why = S.evaluate_gate(r, q, thermal_closure_status="CLOSED_BY_EVIDENCE", operating_temperature=top)
        assert o == "INCOMPLETE_EVIDENCE" and "stage" in why
    for st in (R.STAGE_2, R.STAGE_3):
        assert S.evaluate_gate(r, dict(p, validation_stage=st), thermal_closure_status="CLOSED_BY_EVIDENCE",
                               operating_temperature=top)[0] == "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN"
    assert R.gate_admissible_t_validated({"validation_stage": R.STAGE_1})[0] is False
    assert R.gate_admissible_t_validated({"validation_stage": R.STAGE_2})[0] is True


# ------------------------------------------------------------------------------------------------ P4-OQ-02 Q0 matrix
def test_p4_a9_16_q0_matrix_exact(R, d):
    m = {e[0]: e for e in R.Q0_MATRIX}
    assert {e[1] for e in R.Q0_MATRIX} == {f"R8-C0{i}" for i in range(1, 10)}
    assert m["Q0-C01"][3] == "ENGINEERING_REFERENCE_CONTROL_ONLY" and m["Q0-C01"][2] == "316L"
    assert {m[k][2] for k in ("Q0-C02-IN600", "Q0-C02-IN625", "Q0-C02-H230")} == \
        {"INCONEL alloy 600", "INCONEL alloy 625", "Haynes 230"}
    assert m["Q0-C02-X750"][3] == "ADDITIONAL_COMPARISON_IF_READILY_AVAILABLE"
    assert {m[k][2] for k in ("Q0-C03-IN601", "Q0-C03-H214")} == {"INCONEL alloy 601", "Haynes 214"}
    assert m["Q0-C03-FECRAL"][4] == "exact_grade"
    assert [m[k][5] for k in ("Q0-C04", "Q0-C05", "Q0-C06", "Q0-C07")] == [True] * 4
    assert m["Q0-C07"][4] == "coating_system_and_substrate"
    assert m["Q0-C08"][3] == "NEGATIVE_REFERENCE_CONTROL_ONLY"
    assert m["Q0-C09"][3] == "REFERENCE_CONTROL" and m["Q0-C09"][4] == "exact_grade"
    assert {r[1] for r in R.RESERVE} == {"titanium", "TiN / ZrN coatings", "bulk copper", "bulk iridium"}
    # artifact carries the same matrix and every candidate a disposition
    assert [e["q0_id"] for e in d["a9_16_owner_rules"]["q0_matrix"]["entries"]] == [e[0] for e in R.Q0_MATRIX]
    for c in d["candidates"]:
        assert c["q0_disposition"]["role"] and c["q0_disposition"]["admission"]
    c08 = R.q0_admission("Q0-C08")
    assert c08["is_control"] and c08["baseline_anode_candidate"] is False
    c01 = R.q0_admission("Q0-C01")
    assert c01["is_control"] and c01["baseline_anode_candidate"] is False


def test_p4_a9_16_q0_declarations_refused(R):
    assert _code(R, R.q0_entry, "Q0-C02-HASTELLOY") == "NOT_ADMITTED_EXACT_GRADE_REQUIRED"
    assert _code(R, R.q0_admission, "Q0-C03-FECRAL") == "NOT_ADMITTED_GRADE_TBD"
    assert _code(R, R.q0_admission, "Q0-C03-FECRAL", {"exact_grade": "TBD", "source": SYN}) == \
        "NOT_ADMITTED_GRADE_TBD"
    assert _code(R, R.q0_admission, "Q0-C03-FECRAL", {"exact_grade": "GRADE-SYN"}) == "INCOMPLETE_EVIDENCE"
    assert R.q0_admission("Q0-C03-FECRAL", {"exact_grade": "GRADE-SYN", "source": SYN})["status"] == "ADMITTED_TO_Q0"
    assert _code(R, R.q0_admission, "Q0-C09") == "NOT_ADMITTED_GRADE_TBD"
    assert _code(R, R.q0_admission, "Q0-C02-X750") == "NOT_ADMITTED_AVAILABILITY_TBD"
    assert R.q0_admission("Q0-C02-X750", {"availability": SYN, "source": SYN})["role"] == \
        "ADDITIONAL_COMPARISON_IF_READILY_AVAILABLE"
    assert R.q0_admission("Q0-C02-IN625")["status"] == "ADMITTED_TO_Q0"


def test_p4_a9_16_coating_record_required(R):
    full = {f: SYN for f in R.COATING_RECORD_FIELDS}
    for q in ("Q0-C04", "Q0-C05", "Q0-C06"):
        assert _code(R, R.q0_admission, q) == "NOT_ADMITTED_COATING_RECORD_INCOMPLETE"
        for f in R.COATING_RECORD_FIELDS:
            part = dict(full)
            del part[f]
            assert _code(R, R.q0_admission, q, part) == "NOT_ADMITTED_COATING_RECORD_INCOMPLETE", (q, f)
        assert R.q0_admission(q, full)["status"] == "ADMITTED_TO_Q0"
    assert _code(R, R.q0_admission, "Q0-C07", full) == "NOT_ADMITTED_COATING_SYSTEM_TBD"
    ok = dict(full, coating_system="SYS-SYN", source=SYN)
    assert R.q0_admission("Q0-C07", ok)["status"] == "ADMITTED_TO_Q0"


def test_p4_a9_16_reserve_and_not_listed(R, d):
    for rid, _m, _c in R.RESERVE:
        assert _code(R, R.q0_entry, rid) == "RESERVE_ONLY_NOT_IN_BASELINE_CAMPAIGN"
        assert _code(R, R.reserve_activation, rid) == "RESERVE_ONLY_NOT_IN_BASELINE_CAMPAIGN"
        a = R.reserve_activation(rid, {"hypothesis": SYN, "need": SYN, "source": SYN})
        assert a["status"] == "RESERVE_ACTIVATION_REQUESTED_OUTSIDE_BASELINE"
    assert _code(R, R.q0_entry, "Q0-MO-TZM") == "NOT_IN_OWNER_Q0_MATRIX"
    assert d["a9_16_owner_rules"]["q0_matrix"]["not_in_owner_matrix"] == ["CAND-10", "CAND-15", "CAND-16"]
    by = {c["id"]: c["q0_disposition"] for c in d["candidates"]}
    assert by["CAND-02E"]["admission"].startswith("NOT_ADMITTED_EXACT_GRADE_REQUIRED")
    for cid in ("CAND-11", "CAND-12", "CAND-13", "CAND-14"):
        assert by[cid]["role"] == "RESERVE"


def test_p4_a9_16_q1_only_q0_survivors(R):
    a = R.q0_admission("Q0-C02-IN600")
    ok = {"outcome": "MEETS_PREREGISTERED_SCREENING_CRITERIA", "lock2_registration": "LOCK2-SYN", "source": SYN}
    assert R.q1_admission(a, ok)["status"] == "ADMITTED_TO_Q1"
    assert _code(R, R.q1_admission, a, dict(ok, outcome="FAILS_PREREGISTERED_SCREENING_CRITERIA")) == \
        "NOT_A_Q0_SURVIVOR"
    assert _code(R, R.q1_admission, a, dict(ok, lock2_registration="TBD")) == "NOT_EVALUATED_LOCK2_TBD"
    assert _code(R, R.q1_admission, {"q0_id": "Q0-C03-FECRAL"}, ok) == "NOT_ADMITTED_TO_Q0"


# ------------------------------------------------------------------------------------------------ P4-OQ-03 LOCK-2
def _commission(R, **over):
    recs = {s: {"capability": 1e-3, "units": "1", "source": SYN, "articles": ["standard"]} for s in R.METROLOGY_SLOTS}
    recs["mass_change_detection_limit"] = {"capability": 1e-6, "units": "kg", "source": SYN, "articles": ["blank"]}
    recs["profilometry_recession_resolution"] = {"capability": 1e-7, "units": "m", "source": SYN,
                                                 "articles": ["sacrificial_commissioning_coupon"]}
    recs["ao_ion_exposure_dosimetry"] = {"capability": 1e18, "units": "atoms/m2", "source": SYN,
                                         "articles": ["control"]}
    recs.update(over)
    return recs


def _thresholds(**over):
    t = {"resistance_rise_threshold": {"value": 0.1, "units": "1", "source": SYN, "derived_from": ["requirement"]},
         "mass_loss_recession_limits": {"value": 1e-5, "units": "kg", "source": SYN},
         "sputtering_erosion_acceptance": {"value": 1e-5, "units": "m", "source": SYN},
         "exposure_duration_fluence": {"value": 1e22, "units": "atoms/m2", "source": SYN},
         "uncertainty_treatment": {"rule": SYN, "source": SYN},
         "acceptance_rejection_logic": {"rule": SYN, "source": SYN}}
    t.update(over)
    return t


def test_p4_a9_16_lock2_requires_commissioning(R):
    assert _code(R, R.metrology_commissioning, None) == "NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD"
    recs = _commission(R)
    del recs["coupon_to_coupon_process_repeatability"]
    assert _code(R, R.metrology_commissioning, recs) == "NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD"
    assert _code(R, R.metrology_commissioning, _commission(R, resistance_repeatability_resolution={
        "capability": 1e-3, "units": "1", "source": SYN, "articles": ["candidate_coupon"]})) == \
        "COMMISSIONING_ON_CANDIDATE_COUPON_REFUSED"
    c = R.metrology_commissioning(_commission(R, sem_xps_capability="NOT_APPLICABLE"))
    assert c["status"] == "COMMISSIONED"
    assert _code(R, R.lock2_freeze, None, _thresholds()) == "NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD"
    f = R.lock2_freeze(c, _thresholds())
    assert f["status"] == "LOCK2_FROZEN" and set(f["thresholds"]) == set(R.LOCK2_THRESHOLD_SLOTS)
    t = _thresholds()
    del t["uncertainty_treatment"]
    assert _code(R, R.lock2_freeze, c, t) == "NOT_EVALUATED_LOCK2_TBD"
    assert _code(R, R.lock2_freeze, c, _thresholds(resistance_rise_threshold={"value": "TBD", "units": "1",
                                                                              "source": SYN})) == "INCOMPLETE_EVIDENCE"


def test_p4_a9_16_lock2_refuses_candidate_derived_thresholds(R):
    c = R.metrology_commissioning(_commission(R))
    bad = _thresholds(resistance_rise_threshold={"value": 0.1, "units": "1", "source": SYN,
                                                 "derived_from": ["candidate coupon Q0-C02-IN600 performance"]})
    assert _code(R, R.lock2_freeze, c, bad) == "THRESHOLD_FROM_CANDIDATE_PERFORMANCE_REFUSED"


def test_p4_a9_16_lock2_metrology_never_widened(R):
    c = R.metrology_commissioning(_commission(R))
    # profilometry resolution 1e-7 m cannot resolve a 1e-8 m erosion criterion -> NOT_EVALUATED_METROLOGY
    assert _code(R, R.lock2_freeze, c, _thresholds(sputtering_erosion_acceptance={
        "value": 1e-8, "units": "m", "source": SYN})) == "NOT_EVALUATED_METROLOGY"
    assert _code(R, R.lock2_freeze, c, _thresholds(mass_loss_recession_limits={
        "value": 1e-5, "units": "g", "source": SYN})) == "NOT_EVALUATED_METROLOGY"
    f = R.lock2_freeze(c, _thresholds())
    for v in (1e-4, 1e-6):   # neither widening nor tightening after the freeze
        assert _code(R, R.threshold_revision, f, "sputtering_erosion_acceptance", v) == \
            "THRESHOLD_CHANGE_AFTER_LOCK2_REFUSED"
    assert _code(R, R.threshold_revision, None, "x", 1) == "NOT_EVALUATED_LOCK2_TBD"


def test_p4_a9_16_lock2_before_acceptance_exposure(R):
    c = R.metrology_commissioning(_commission(R))
    assert _code(R, R.lock2_freeze, c, _thresholds(), ["EXP-SYN-01"]) == "ACCEPTANCE_EXPOSURE_BEFORE_LOCK2_REFUSED"


# ------------------------------------------------------------------------------------------------ P4-OQ-04 sputter
def _sp(**over):
    r = {"origin": "LITERATURE_ACQUIRED", "route": "inter_library_loan", "species": "O+", "energy_eV": 100.0,
         "angle_deg": 0.0, "target_material": "W", "record_target_kind": "ELEMENTAL", "source": SYN}
    r.update(over)
    return r


def test_p4_a9_16_sputter_literature_uses_only(R):
    for u in R.LITERATURE_USES:
        assert R.sputter_record_use(_sp(), u, "ELEMENTAL")["status"] == "ADMISSIBLE_FOR_USE_CONDITIONAL"
    assert _code(R, R.sputter_record_use, _sp(), "candidate_specific_evidence", "ELEMENTAL") == \
        "LITERATURE_NOT_CANDIDATE_EVIDENCE"
    meas = _sp(origin="PROJECT_ION_BEAM_MEASUREMENT", route=None, target_material="IN601",
               record_target_kind="ALLOY")
    assert R.sputter_record_use(meas, "candidate_specific_evidence", "ALLOY")["origin"] == \
        "PROJECT_ION_BEAM_MEASUREMENT"
    assert _code(R, R.sputter_record_use, dict(meas, record_target_kind="COATING"), "candidate_specific_evidence",
                 "ALLOY") == "INCOMPLETE_EVIDENCE"


def test_p4_a9_16_sputter_elemental_substitution_refused(R):
    for kind in ("ALLOY", "COATING"):
        assert _code(R, R.sputter_record_use, _sp(), "prior_bounds", kind) == "ELEMENTAL_SUBSTITUTION_REFUSED"
    ma = {"verdict": "NOT_MATERIAL", "source": SYN}
    out = R.sputter_record_use(_sp(materiality_assessment=ma), "comparison", "ALLOY")
    assert "EXPLICIT_ELEMENTAL_PROXY" in out["labels"]
    assert _code(R, R.sputter_record_use, _sp(materiality_assessment={"verdict": "MATERIAL", "source": SYN}),
                 "comparison", "ALLOY") == "ELEMENTAL_SUBSTITUTION_REFUSED"
    meas_el = _sp(origin="PROJECT_ION_BEAM_MEASUREMENT", route=None, materiality_assessment=ma)
    assert _code(R, R.sputter_record_use, meas_el, "candidate_specific_evidence", "COATING") == \
        "LITERATURE_NOT_CANDIDATE_EVIDENCE"


def test_p4_a9_16_sputter_species_resolved_and_lawful(R):
    assert R.ACQUISITION_SPECIES == ("N+", "N2+", "O+", "O2+")
    assert _code(R, R.sputter_record_use, _sp(species="air plasma"), "prior_bounds", "ELEMENTAL") == \
        "NOT_SPECIES_RESOLVED"
    assert _code(R, R.sputter_record_use, _sp(species=None), "prior_bounds", "ELEMENTAL") == "NOT_SPECIES_RESOLVED"
    assert _code(R, R.sputter_record_use, _sp(angle_deg=None), "prior_bounds", "ELEMENTAL") == "INCOMPLETE_EVIDENCE"
    assert _code(R, R.sputter_record_use, _sp(route="unlicensed_mirror"), "prior_bounds", "ELEMENTAL") == \
        "ACQUISITION_ROUTE_NOT_LAWFUL"
    assert "ENGINEERING_ONLY_AR" in R.sputter_record_use(_sp(species="Ar+"), "comparison", "ELEMENTAL")["labels"]


# ------------------------------------------------------------------------------------------------ P4-OQ-05 collector
def test_p4_a9_16_collector_polarity_frozen(R):
    assert R.COLLECTOR_SETS == ("NEGATIVE_BIAS_ION_COLLECTING", "FLOATING_MATCHED_CONTROL")
    assert R.collector_coupon_exposure({"set": "FLOATING_MATCHED_CONTROL"})["classification"] == "MATCHED_CONTROL"
    for pol in ("POSITIVE", "ELECTRON_COLLECTING", None):
        assert _code(R, R.collector_coupon_exposure, {"set": "NEGATIVE_BIAS_ION_COLLECTING", "polarity": pol,
                                                       "p1_complete": True}) == "POLARITY_FROZEN"
    assert _code(R, R.collector_coupon_exposure, {"set": "FLOATING_MATCHED_CONTROL", "polarity": "NEGATIVE"}) == \
        "POLARITY_FROZEN"
    assert _code(R, R.collector_coupon_exposure, {"set": "ELECTRON_COLLECTING"}) == "INCOMPLETE_EVIDENCE"


def test_p4_a9_16_collector_bias_from_p1(R, d):
    neg = {"set": "NEGATIVE_BIAS_ION_COLLECTING", "polarity": "NEGATIVE"}
    pre = R.collector_coupon_exposure(dict(neg, p1_complete=False, acceptance_bearing=False))
    assert pre["classification"] == "ENGINEERING_ONLY_FIXTURE_PROCESS_VERIFICATION"
    assert _code(R, R.collector_coupon_exposure, dict(neg, p1_complete=False, acceptance_bearing=True)) == \
        "NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1"
    assert _code(R, R.collector_coupon_exposure, dict(neg, p1_complete=True, acceptance_bearing=True,
                                                      bias_magnitude_source={"p1_collector_envelope": "TBD"})) == \
        "NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1"
    ok = R.collector_coupon_exposure(dict(neg, p1_complete=True, acceptance_bearing=True, bias_magnitude_source={
        "p1_collector_envelope": "P1-SYN", "plasma_sheath_evidence": "P1-SYN"}))
    assert ok["classification"] == "ACCEPTANCE_BEARING_SERVICE_POLARITY_CONDITIONAL"
    assert d["a9_16_owner_rules"]["collector_coupons"]["registered_evaluation"]["status"] == \
        "NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1"
    it = {i["id"]: i for i in d["items"]}
    assert "NEGATIVE" in it["IT-14"]["value"] and it["IT-29"]["status"] == "OWNER_GIVEN"
    assert it["IT-19"]["status"] == "TBD_AFTER_EVIDENCE"


# ------------------------------------------------------------------------------------------------ A9.13 F2-OQ-04
def test_p4_a9_16_app_filter_present(R, d):
    app = d["applications"]["APP-FILTER"]
    assert "compressor inlet" in app["name"] and app["candidate_scope"].startswith("TBD_AFTER_EVIDENCE")
    crit = {c["id"]: c for c in d["criteria"]}
    fc = [c for c in d["criteria"] if c["applies_to"] == ["APP-FILTER"]]
    names = " ".join(c["name"] for c in fc).lower()
    for w in ("ao / o exposure", "erosion", "recombination", "particulate retention", "thermal cycling",
              "transmission", "conductance"):
        assert w in names, w
    assert "APP-FILTER" in crit["CR-09"]["applies_to"]
    assert [r["id"] for r in d["requirements"] if r["application"] == "APP-FILTER"] == \
        ["RQ-10-F", "RQ-11-F", "RQ-12-F", "RQ-13-F", "RQ-14-F", "RQ-15-F"]
    for r in d["requirements"]:
        if r["application"] == "APP-FILTER":
            assert r["value"] is None and r["status"] == "TBD" and "NOT_EVALUATED_FILTER_ACCEPTANCE_TBD" in r["tbd"]
    assert not [m for m in d["gate_matrix"] if m["application"] == "APP-FILTER"]
    assert d["final_material_status"]["APP-FILTER"] == "OPEN"
    assert d["fixed_statuses"]["FINAL_FILTER_MATERIAL"]["status"] == "OPEN"
    tps = {t["id"] for t in d["test_plan"]["tests"]}
    assert {"TP-10", "TP-11", "TP-12", "TP-13", "TP-14", "TP-15"} <= tps
    ifd = {i["id"]: i for i in d["interface_demands"]}
    assert "F2-IF-08" in ifd["ID-12"]["counterpart"]
    f2 = (REPO / "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json").read_text(encoding="utf-8")
    assert '"F2-IF-08"' in f2


def test_p4_a9_16_filter_baseline_inert_catalytic_variant(R):
    assert R.FILTER_PLACEMENT == "intake / channel array -> filter -> compressor inlet"
    b = R.filter_material_role({"recombination_intent": "INERT_LOW_RECOMBINATION"})
    assert b["role"] == "APP-FILTER_BASELINE_CANDIDATE" and set(b["tests"]) == set(R.FILTER_TESTS)
    assert _code(R, R.filter_material_role, {"recombination_intent": "INERT_LOW_RECOMBINATION",
                                             "placement": "upstream of intake"}) == "FILTER_PLACEMENT_NOT_BASELINE"
    v = R.filter_material_role({"recombination_intent": "CATALYTIC_O_TO_O2"})
    assert v["role"] == "CATALYTIC_O_TO_O2_RESEARCH_VARIANT" and v["baseline"] is False
    assert len(v["requires_own"]) == 4
    assert _code(R, R.filter_material_role, {"recombination_intent": "CATALYTIC_O_TO_O2", "baseline": True}) == \
        "CATALYTIC_FILTER_NOT_BASELINE"
    assert _code(R, R.filter_material_role, {}) == "INCOMPLETE_EVIDENCE"


def test_p4_a9_16_filter_acceptance_slots(R, d):
    assert _code(R, R.filter_acceptance, None) == "NOT_EVALUATED_FILTER_ACCEPTANCE_TBD"
    part = {s: SYN for s in R.FILTER_ACCEPTANCE_SLOTS[:-1]}
    assert _code(R, R.filter_acceptance, part) == "NOT_EVALUATED_FILTER_ACCEPTANCE_TBD"
    full = dict(part, ag12_feed_state_effect=SYN)
    assert R.filter_acceptance(full)["status"] == "FILTER_ACCEPTANCE_REGISTERED"
    assert d["a9_16_owner_rules"]["app_filter"]["registered_acceptance"]["status"] == \
        "NOT_EVALUATED_FILTER_ACCEPTANCE_TBD"


# ------------------------------------------------------------------------------------------------ A9.15 + artifact state
def test_p4_a9_16_no_xe_contingency_text(d):
    txt = OUT_JSON.read_text(encoding="utf-8") + OUT_MD.read_text(encoding="utf-8")
    for f in LANE.glob("*.py"):
        txt += f.read_text(encoding="utf-8")
    low = txt.lower()
    for bad in ("contingency-only for c1", "xe contingency only", "xe is contingency"):
        # the only occurrence allowed is the quoted A9.15 verbatim text that REMOVES the policy
        for m in re.finditer(re.escape(bad), low):
            ctx = low[max(0, m.start() - 300):m.end() + 50]
            assert "remove" in ctx or "not merely a contingency" in ctx or "not because" in ctx, ctx
    crit = {c["id"]: c for c in d["criteria"]}
    assert "Xe+" in crit["CR-04"]["rule"]


def test_p4_a9_16_registered_evaluations_refuse_and_no_pass(d):
    r = d["a9_16_owner_rules"]
    assert r["staged_validation"]["registered_evaluation"]["status"].startswith("NOT_EVALUATED")
    assert r["lock2"]["registered_commissioning"]["status"] == "NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD"
    assert r["lock2"]["registered_freeze"]["status"] == "NOT_EVALUATED_METROLOGY_COMMISSIONING_TBD"
    _S = _load("p4_screening_nopass_a916", LANE / "p4_screening.py")
    _S.assert_no_forbidden_status(d)
    assert set(d["final_material_status"].values()) == {"OPEN"}
    assert d["fixed_statuses"]["ANODE_THERMAL_CLOSURE"]["status"] == "UNRESOLVED"
    assert d["fixed_statuses"]["ICP_COUPLED_THERMAL"]["status"] == "UNRESOLVED"
    assert {m["outcome"] for m in d["gate_matrix"]} == {"INCOMPLETE_EVIDENCE"}


def test_p4_a9_16_items_and_stages(d):
    it = {i["id"]: i for i in d["items"]}
    assert it["IT-13"]["freeze_point"] == "LOCK-2" and "LOCK-2" in it["IT-13"]["value"]
    assert it["IT-17"]["status"] == "OWNER_GIVEN"
    for k in ("IT-26", "IT-27", "IT-28", "IT-31"):
        assert it[k]["status"] == "TBD" and it[k]["value"].startswith("TBD")
    vs = {v["id"]: v for v in d["test_plan"]["validation_stages"]}
    assert vs["ST-2"]["qual_stages"] == ["Q4"] and vs["ST-2"]["result"] == "T_VALIDATED_CONTINUOUS"
    assert vs["ST-1"]["usable_for"] == ["design_screening"]
    ifd = {i["id"]: i for i in d["interface_demands"]}
    assert "P1" in ifd["ID-06"]["a9_16_note"] and "XL-27" in ifd["ID-09"]["a9_16_note"]
