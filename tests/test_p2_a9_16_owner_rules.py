"""Tests for A9.16 step 1 in the P2 impedance-map package: owner decisions of 2026-10-01 (A9.8 P2Q-02, A9.10 P1Q-24,
A9.11 P2Q-01/03/04/07/08/09, A9.14 ICPQ-11 / P2Q-10 / P2Q-06 / F6-OQ-02) applied to
docs/experiments/hall_icp/p2_impedance_map/ (rules module p2_a9_16_rules.py, data module a9_16_application.py,
reducer / framework changes). Every refusal path has an explicit test; synthetic data only (not evidence).
Run: python -m pytest -q tests/test_p2_a9_16_owner_rules.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p2_impedance_map"
OUT_JSON = LANE / "p2_impedance_prep_v1.json"
OUT_MD = LANE / "P2_IMPEDANCE_PREP.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _load("p2_builder_a916_under_test", LANE / "build_p2_impedance_prep.py")


@pytest.fixture(scope="module")
def rules():
    return _load("p2_a9_16_rules_under_test", LANE / "p2_a9_16_rules.py")


@pytest.fixture(scope="module")
def fw(mod):
    return mod.FW


@pytest.fixture(scope="module")
def app():
    return _load("p2_a9_16_application_under_test", LANE / "a9_16_application.py")


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


@pytest.fixture()
def case(mod):
    line, elements = mod._fwsyn_networks(50.0)
    match = mod.FW.ladder_abcd(elements)
    cal = mod.synthetic_cal(50.0, line, match, complex(0.01, -0.02), complex(0.03, 0.01), complex(0.98, 0.05),
                            (1 + 0j, complex(0.05, 3.0), 0j, 1 + 0j))
    rec = mod.synthetic_record(cal, complex(2.0, 80.0), 100.0)
    return cal, rec


def _sha(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


ZA = {"R_ohm": 1.0, "X_ohm": 80.0, "u_R_ohm": 0.1, "u_X_ohm": 1.0, "uncertainty_budget_id": "SYN-UB-A",
      "operating_point_id": "SYN-OP-1", "configuration_id": "SYN-CFG-1"}
# A9.16 repair COR-07: a ZM-B counts only with an explicit valid = True at the same operating point / configuration
ZB = dict(ZA, valid=True)


# ------------------------------------------------------------------------------------------------ pins / package
def test_p2_a9_16_decisions_pinned_and_cited(d, app):
    pins = {p["path"]: p["sha256"] for p in d["decision_pins"]}
    for k in app.ORDER:
        j, js, m, ms = app.DEC[k]
        assert _sha(j) == js and _sha(m) == ms, k
        assert pins[j] == js and pins[m] == ms, k
    rows = [o for o in d["owner_answers_applied"] if isinstance(o.get("ref"), dict)
            and o["ref"].get("kind") in app.DEC]
    got = {(o["ref"]["kind"], o["question_id"]) for o in rows}
    for dd, q, *_ in app.APPLIED:
        assert (dd, q) in got, (dd, q)
    for o in rows:
        assert o["ref"]["sha256"] == app.DEC[o["ref"]["kind"]][1] and o["ref"]["path"] == app.DEC[o["ref"]["kind"]][0]
    inc = d["a9_16_incorporation"]
    assert {x["question_id"] for x in inc["applied"]} == {"P2Q-01", "P2Q-02", "P2Q-03", "P2Q-04", "P2Q-06", "P2Q-07",
                                                           "P2Q-08", "P2Q-09", "P2Q-10", "P1Q-24", "ICPQ-11",
                                                           "F6-OQ-02", "ICPQ-10", "OQ-A910-06"}   # repair F1 / F5
    assert inc["owner_numbers_used"] == {"k_agreement": 2.0, "k_transition": 2.0, "k_loss": 2.0, "k_RF": 1.5,
                                         "continuous_RF_power_current_factor": 1.25,
                                         "thermal_dissipation_factor": 1.2}
    assert all(s["ok"] for s in inc["selfcheck"])
    assert any(x["decision"] == "A9.15" for x in inc["not_applicable"])


def test_p2_a9_16_every_listed_test_exists(d, app):
    src = Path(__file__).read_text(encoding="utf-8")
    names = set()
    for *_, tests in app.APPLIED:
        names |= {t for t in tests if t.startswith("test_p2_a9_16_")}
    names |= {t for _c, _o, t in app.FAIL_CLOSED}
    for n in names:
        assert re.search(r"^def %s\(" % re.escape(n), src, re.M), n


def test_p2_a9_16_questions_answered_and_items(d):
    # A9.16 repair COR-01: open_owner_questions keeps the as-raised record read back by the immutable state-v4
    # builder (text unchanged, no status); none is open now (updated test; step 1 emptied the list)
    assert d["owner_questions_open_now"] == []
    assert {q.get("status") for q in d["open_owner_questions"]} <= {None, "OPEN", "TBD_OWNER"}
    ans = {q["id"]: q for q in d["answered_owner_questions"]}
    assert set(ans) == {"P2Q-01", "P2Q-02", "P2Q-03", "P2Q-04", "P2Q-06", "P2Q-07", "P2Q-08", "P2Q-09", "P2Q-10"}
    assert ans["P2Q-02"]["answered_by"]["decision"] == "A9.8" and ans["P2Q-06"]["answered_by"]["decision"] == "A9.14"
    items = {i["id"]: i for i in d["items"]}
    for i in ("FW-09", "FW-10", "FW-12", "FW-17", "FW-18", "FW-20", "HM-F08", "HM-R05", "HM-R06", "HM-R07", "MS-P2-03"):
        assert items[i]["status"] == "OWNER_GIVEN", i
    assert items["FW-09"]["value"] == 2.0 and items["FW-18"]["value"] == 1.5
    assert "residual reflection" in items["HM-R07"]["value"]
    rec = d["z_antenna_recommendation"]
    assert rec["status"] == "OWNER_GIVEN" and "k_agreement = 2.0" in rec["transfer_rule"]
    roles = {m["id"]: m["role"] for m in d["z_antenna_methods"]}
    assert roles["ZM-A"].startswith("PRIMARY") and roles["ZM-B"].startswith("MANDATORY CROSS-CHECK")
    assert roles["ZM-C"].startswith("INDEPENDENT R")
    assert d["a9_2_statuses_carried"]["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert '"PASS"' not in json.dumps(d)
    md = OUT_MD.read_text(encoding="utf-8")
    assert "## A9.16 step 1" in md and "None open" in md


# ------------------------------------------------------------------------------------------------ P2Q-01 / P2Q-03
def test_p2_a9_16_zm_b_missing_never_verifies_zm_a(rules):
    for zb in (None, dict(ZA, valid=False), {k: v for k, v in ZA.items() if k != "u_R_ohm"}):
        r = rules.method_agreement(ZA, zb)
        assert r["status"] == rules.ZM_B_MISSING_OR_INVALID and r["zm_a_independently_verified"] is False
        assert r["blocks_zm_b_stand_qualification"] is True
    with pytest.raises(rules.RuleError):
        rules.method_agreement({k: v for k, v in ZA.items() if k != "uncertainty_budget_id"}, dict(ZB))


def test_p2_a9_16_cor07_zm_b_needs_valid_true_and_same_point(rules):
    """A9.16 repair COR-07: a ZM-B with no validity flag, or from a different operating point / configuration, never
    makes ZM-A independently verified; ZM-A itself must name its operating point and configuration."""
    for zb in (dict(ZA), dict(ZA, valid=None), dict(ZA, valid="yes"), dict(ZB, operating_point_id="SYN-OP-2"),
               dict(ZB, configuration_id="SYN-CFG-2"), {k: v for k, v in ZB.items() if k != "operating_point_id"}):
        r = rules.method_agreement(ZA, zb)
        assert r["status"] == rules.ZM_B_MISSING_OR_INVALID, zb
        assert r["zm_a_independently_verified"] is False and r["blocks_zm_b_stand_qualification"] is True
        assert "z_R" not in r
    assert "another operating_point_id" in rules.method_agreement(ZA, dict(ZB, operating_point_id="X"))["reason"]
    for k in ("operating_point_id", "configuration_id"):
        with pytest.raises(rules.RuleError):
            rules.method_agreement({x: v for x, v in ZA.items() if x != k}, dict(ZB))
    assert rules.method_agreement(ZA, dict(ZB))["status"] == rules.AGREEMENT


def test_p2_a9_16_method_agreement_k2(rules):
    ok = rules.method_agreement(ZA, dict(ZB, R_ohm=1.25, X_ohm=82.0, uncertainty_budget_id="B"))
    assert ok["status"] == rules.AGREEMENT and ok["zm_a_independently_verified"] is True
    assert ok["z_R"] == pytest.approx(0.25 / (0.1 * 2 ** 0.5)) and ok["k_agreement"] == 2.0
    bad = rules.method_agreement(ZA, dict(ZB, R_ohm=1.3, uncertainty_budget_id="B"))      # z_R = 2.12 > 2
    assert bad["status"] == rules.METHOD_DISAGREEMENT and bad["averaged_value"] is None
    assert bad["raw_zm_a"]["R_ohm"] == 1.0 and bad["raw_zm_b"]["R_ohm"] == 1.3
    assert bad["blocks_zm_b_stand_qualification"] is True and bad["zm_a_independently_verified"] is False
    badx = rules.method_agreement(ZA, dict(ZB, X_ohm=83.0, uncertainty_budget_id="B"))     # z_X = 2.12
    assert badx["status"] == rules.METHOD_DISAGREEMENT
    corr = rules.method_agreement(ZA, dict(ZB, R_ohm=1.25, uncertainty_budget_id="B"), r_R=0.9)
    assert corr["status"] == rules.METHOD_DISAGREEMENT                                   # covariance-aware
    with pytest.raises(rules.RuleError):
        rules.method_agreement(ZA, dict(ZB), r_R=1.5)


def test_p2_a9_16_reducer_zm_status(mod, case):
    cal, rec = case
    both = mod.RED.reduce_record(rec, {cal["calibration_set_id"]: cal})
    assert both["zm_cross_check_status"] == "PENDING_AGREEMENT_EVALUATION"
    assert both["zm_a_independently_verified"] is False and "k_agreement = 2.0" in both["method_difference"]["acceptance"]
    only_a = mod.RED.reduce_record(dict(rec, methods=["vi_probe"]), {cal["calibration_set_id"]: cal})
    assert only_a["zm_cross_check_status"] == "ZM_A_NOT_INDEPENDENTLY_VERIFIED_ZM_B_MISSING"
    assert only_a["zm_a_independently_verified"] is False and "method_difference" not in only_a
    only_b = mod.RED.reduce_record(dict(rec, methods=["deembed"]), {cal["calibration_set_id"]: cal})
    assert only_b["zm_cross_check_status"] == "ZM_B_ONLY_NO_ZM_A"


def test_p2_a9_16_zm_c_needs_verified_delivered_power(rules):
    for pd in ("REFUSED - loss unverified", {"min": 1.0, "max": 2.0}, None):
        assert rules.zm_c_resistance_crosscheck(2.0, 0.1, 5.0, 0.05, pd, 1.0)["status"] == \
            "NOT_EVALUATED_LOSS_UNVERIFIED"
    r = rules.zm_c_resistance_crosscheck(2.0, 0.1, 5.0, 0.05, 50.0, 1.0)
    assert r["status"] == "REPORTED_INDEPENDENT_R_CROSS_CHECK" and r["R_C_ohm"] == pytest.approx(2.0)
    assert r["z_R"] == pytest.approx(0.0)
    with pytest.raises(rules.RuleError):
        rules.zm_c_resistance_crosscheck(2.0, 0.1, 0.0, 0.05, 50.0, 1.0)


def test_p2_a9_16_updown_hysteresis_classes(rules):
    a = rules.updown_hysteresis(10.0, 0.3, 10.8, 0.3, quantity="R_ohm", factor_level_id="L1")   # z = 1.886
    b = rules.updown_hysteresis(10.0, 0.3, 10.9, 0.3, quantity="R_ohm", factor_level_id="L1")   # z = 2.12
    assert a["status"] == rules.NO_HYSTERESIS and b["status"] == rules.RESOLVED_HYSTERESIS
    assert "not a FAIL" in b["interpretation"] and "FAIL" != b["status"]
    assert rules.updown_hysteresis(1.0, 0.0, 2.0, 0.0, quantity="R", factor_level_id="L1")["status"] == \
        rules.NOT_EVALUATED_UNCERTAINTY
    with pytest.raises(rules.RuleError):
        rules.updown_hysteresis(1.0, 0.1, 2.0, 0.1, quantity="R", factor_level_id="TBD")


def test_p2_a9_16_hysteresis_bases_need_verified_delivered(rules, mod, case):
    cal, rec = case
    red = mod.RED
    good = red.reduce_record(rec, {cal["calibration_set_id"]: cal})
    assert good["loss_status"].startswith("VERIFIED")
    b = rules.hysteresis_power_bases(good, good)
    assert isinstance(b["P_delivered_W"], list) and len(b["P_forward_W"]) == 2
    c2 = copy.deepcopy(cal)
    c2["loss_verification"] = None
    unv = red.reduce_record(rec, {cal["calibration_set_id"]: c2})
    b2 = rules.hysteresis_power_bases(good, unv)
    assert b2["P_delivered_W"].startswith("NOT_EVALUATED_LOSS_UNVERIFIED") and len(b2["P_forward_W"]) == 2


# ------------------------------------------------------------------------------------------------ P1Q-24 k_loss
def test_p2_a9_16_k_loss_registry_refuses_other_k(mod, case):
    cal, rec = case
    red, fw = mod.RED, mod.FW
    assert red.K_LOSS == 2.0
    for k in (1.0, 2.5, 3.0):
        c2 = copy.deepcopy(cal)
        c2["loss_check_registrations"]["protocols"]["SYN-K-REG-01"]["k"] = k
        with pytest.raises(red.RecordError, match="k_loss"):
            red.loss_check_protocol(c2, "SYN-K-REG-01", red.LOSS_VERIFICATION_METHODS[0], "TS-SYN-1")
        ok, why = red.loss_verification_status(dict(cal["loss_verification"], k=k), c2, tuning_state_id="TS-SYN-1")
        assert not ok
    assert red.loss_check_protocol(cal, "SYN-K-REG-01", red.LOSS_VERIFICATION_METHODS[0], "TS-SYN-1")["k"] == 2.0
    lv = cal["loss_verification"]
    with pytest.raises(fw.CriteriaMissingError, match="k_loss"):
        fw.verify_line_match_loss(
            verification_id="X", method=lv["method"], cal=cal, model_ref={k: lv["model_ref"][k] for k in (
                "kind", "tuning_state_id", "Z_load_ohm", "Z_load_basis")}, u_eta_pred=0.01, P_net_W=100.0,
            u_P_net_W=1.0, P_ref_load_W=95.0, u_P_ref_load_W=1.0, k=1.0, k_registration_id="SYN-K-REG-01",
            evidence_record_ids=["SYN-1"], data_class="synthetic_test")


def test_p2_a9_16_upper_bound_until_verified(mod, case):
    cal, rec = case
    red = mod.RED
    good = red.reduce_record(rec, {cal["calibration_set_id"]: cal})
    assert isinstance(good["P_delivered_W"], float) and "P_delivered_upper_bound_W" not in good
    c2 = copy.deepcopy(cal)
    c2["loss_verification"] = None
    unv = red.reduce_record(rec, {cal["calibration_set_id"]: c2})
    assert unv["P_delivered_W"].startswith("REFUSED") and unv["loss_status"] == "UNVERIFIED"
    ub = unv["P_delivered_upper_bound_W"]
    assert ub["status"] == "UPPER_BOUND_UNVERIFIED_LOSS" and ub["value"] == unv["at_RP_CPL"]["P_net_W"]
    na = red.reduce_record(dict(rec, loss_method="not_available"), {cal["calibration_set_id"]: cal})
    assert na["P_delivered_upper_bound_W"]["status"] == "UPPER_BOUND_UNVERIFIED_LOSS"


# ------------------------------------------------------------------------------------------------ P2Q-04
def _pt(**kw):
    p = {"tuning_mode": "RETUNED_TO_MIN_REFLECTED_POWER", "matching_state_id": "TS-SYN-1",
         "encoder_values": {"C_series": "SYN", "C_shunt": "SYN"}, "tune_time_s": 3.0,
         "residual_reflection": {"gamma_mag": 0.02}}
    p.update(kw)
    return p


def test_p2_a9_16_retune_point_rules(rules, case):
    cal, _ = case
    assert rules.retune_point_check(_pt(), cal)["status"] == "RETUNED_CHARACTERIZED_STATE"
    for k in rules.RETUNE_FIELDS:
        p = _pt()
        p[k] = None
        assert rules.retune_point_check(p, cal)["status"] == "REFUSED_RETUNE_LOG_INCOMPLETE", k
    assert rules.retune_point_check(_pt(residual_reflection={"other": 1}), cal)["status"] == \
        "REFUSED_RETUNE_LOG_INCOMPLETE"
    assert rules.retune_point_check(_pt(tuning_mode="FIXED"), cal)["status"] == "REFUSED_NOT_RETUNED"
    off = _pt(encoder_values={"C_series": "OTHER", "C_shunt": "SYN"})
    assert rules.retune_point_check(off, cal)["status"] == "REFUSED_UNCHARACTERIZED_TUNING_STATE"
    reg = {"rule_id": "SYN-INTERP", "status": "VERIFIED", "calibration_steps": ["CAL-P2-03", "CAL-P2-04"],
           "verification_record_ids": ["SYN-V1"]}
    assert rules.retune_point_check(dict(off, interpolation_rule_id="SYN-INTERP"), cal, reg)["status"] == \
        "RETUNED_VERIFIED_INTERPOLATION"
    for bad in (dict(reg, status="PROPOSED"), dict(reg, calibration_steps=["CAL-P2-09"]),
                dict(reg, verification_record_ids=[])):
        assert rules.retune_point_check(dict(off, interpolation_rule_id="SYN-INTERP"), cal, bad)["status"] == \
            "REFUSED_UNCHARACTERIZED_TUNING_STATE"


def test_p2_a9_16_fixed_tune_selection_rule_frozen_first(rules):
    rule = {"rule_id": "SYN-SEL", "frozen_utc": "2026-11-01T00:00:00Z", "text": "SYN selection text",
            "region_classes": ["STABLE_NOMINAL_REGION", "OPERATING_ENVELOPE_EDGE"]}
    pts = [{"tuning_state_id": "TS-1", "tuning_mode": "FIXED_TUNE_SUB_SWEEP"} for _ in range(3)]
    sw = {"rule_id": "SYN-SEL", "region_class": "STABLE_NOMINAL_REGION", "first_interpretation_utc":
          "2026-11-02T00:00:00Z", "primary_map_id": "SYN-MAP", "points": pts}
    assert rules.fixed_tune_subsweep_check(rule, sw)["status"] == "FIXED_TUNE_SUPPLEMENT_ADMISSIBLE"
    assert rules.fixed_tune_subsweep_check(None, sw)["status"] == "NOT_EVALUATED_REGISTRATION"
    late = dict(sw, first_interpretation_utc="2026-10-31T00:00:00Z")
    assert rules.fixed_tune_subsweep_check(rule, late)["status"] == \
        "REFUSED_SELECTION_RULE_NOT_FROZEN_BEFORE_INTERPRETATION"
    assert rules.fixed_tune_subsweep_check(rule, dict(sw, region_class="FLIGHT_MATCH_DESIGN_REGION"))["status"] == \
        "REFUSED_NOT_A_REGISTERED_REPRESENTATIVE_REGION"
    assert rules.fixed_tune_subsweep_check(rule, dict(sw, replaces_primary_map=True))["status"] == \
        "REFUSED_FIXED_TUNE_REPLACES_PRIMARY"
    mixed = dict(sw, points=pts[:2] + [{"tuning_state_id": "TS-2", "tuning_mode": "FIXED_TUNE_SUB_SWEEP"}])
    assert rules.fixed_tune_subsweep_check(rule, mixed)["status"] == "REFUSED_NOT_FIXED_TUNE"
    with pytest.raises(rules.RuleError):
        rules.fixed_tune_subsweep_check(dict(rule, region_classes=["ANYWHERE"]), sw)


# ------------------------------------------------------------------------------------------------ P2Q-07
def _inhouse():
    c = {k: {"record_id": "SYN-" + k} for k in (
        "vna_and_cal_kit_certificates", "complex_vi_gain_13_56_MHz", "low_level_short_open_load_checks",
        "precision_50_ohm_reference", "reactive_reference_vna_characterized", "pre_post_calibration_checks",
        "probe_cable_temperature_phase_drift", "repeatability", "configuration_ids_raw_data_hashes")}
    c["rp_vi_to_rp_ant_fixture"] = {"form": "CHARACTERIZED", "record_id": "SYN-FIX"}
    c["uncertainty_propagation"] = {"record_id": "SYN-UP", "u_magnitude_rel": 0.01, "u_relative_phase_deg": 0.2,
                                    "relative_phase_basis": "reactive reference + VNA"}
    return {"route": "IN_HOUSE_VNA_TRACEABLE", "accredited_scope_unavailable_basis": "SYN no scope survey",
            "content": c, "cal_p2_15_at_power_validation": {"status": "VERIFIED", "record_ids": ["SYN-15"]}}


def test_p2_a9_16_vi_calibration_routes(rules):
    ok = rules.vi_calibration_check(_inhouse())
    assert ok["status"] == "CALIBRATION_ADMISSIBLE" and ok["label"] == rules.IN_HOUSE_LABEL
    assert "NOT_AN_ACCREDITED" in ok["label"]
    for k in rules.IN_HOUSE_REQUIRED:
        c = _inhouse()
        del c["content"][k]
        assert rules.vi_calibration_check(c)["status"] == "REFUSED_IN_HOUSE_CONTENT_INCOMPLETE", k
    na = _inhouse()
    na["content"]["low_level_short_open_load_checks"] = {"not_applicable_reason": "SYN fixture has no open"}
    assert rules.vi_calibration_check(na)["status"] == "CALIBRATION_ADMISSIBLE"
    ph = _inhouse()
    ph["content"]["uncertainty_propagation"]["relative_phase_basis"] = "magnitude_calibration"
    assert rules.vi_calibration_check(ph)["status"] == "REFUSED_IN_HOUSE_CONTENT_INCOMPLETE"
    fx = _inhouse()
    fx["content"]["rp_vi_to_rp_ant_fixture"] = {"form": "ASSUMED", "record_id": "SYN"}
    assert rules.vi_calibration_check(fx)["status"] == "REFUSED_IN_HOUSE_CONTENT_INCOMPLETE"
    nb = _inhouse()
    del nb["accredited_scope_unavailable_basis"]
    assert rules.vi_calibration_check(nb)["status"] == "REFUSED_IN_HOUSE_WITHOUT_SCOPE_UNAVAILABILITY_BASIS"
    n15 = _inhouse()
    n15["cal_p2_15_at_power_validation"] = {"status": "PLANNED", "record_ids": []}
    assert rules.vi_calibration_check(n15)["status"] == "NOT_EVALUATED_CAL_P2_15_AT_POWER_VALIDATION_MISSING"
    acc = {"route": "ACCREDITED_ISO_IEC_17025_OR_NABL", "laboratory_id": "SYN-LAB",
           "accredited_scope": {"covers_magnitude_13_56_MHz": True, "covers_relative_phase_13_56_MHz": False},
           "cal_p2_15_at_power_validation": {"status": "VERIFIED", "record_ids": ["SYN-15"]}}
    assert rules.vi_calibration_check(acc)["status"] == "REFUSED_ACCREDITED_SCOPE_NOT_DEMONSTRATED"
    acc["accredited_scope"]["covers_relative_phase_13_56_MHz"] = True
    assert rules.vi_calibration_check(acc)["status"] == "CALIBRATION_ADMISSIBLE"
    with pytest.raises(rules.RuleError):
        rules.vi_calibration_check({"route": "CERTIFICATE_ASSUMED"})


def test_p2_a9_16_vi_adequacy_registration_slot(rules):
    assert rules.vi_measurement_adequacy(0.1, 1.0, None)["status"] == "NOT_EVALUATED_REGISTRATION"
    reg = {"criterion_id": "SYN-DISC", "frozen_utc": "2026-11-01T00:00:00Z", "u_R_max_ohm": 0.05, "u_X_max_ohm": 2.0}
    assert rules.vi_measurement_adequacy(0.1, 1.0, reg)["status"] == "NOT_EVALUATED_INSTRUMENT"
    assert rules.vi_measurement_adequacy(0.04, 1.0, reg)["status"] == "ADEQUATE_FOR_REGISTERED_DISCRIMINATION"
    assert rules.vi_measurement_adequacy(0.04, 1.0, dict(reg, u_R_max_ohm=None))["status"] == \
        "NOT_EVALUATED_REGISTRATION"


# ------------------------------------------------------------------------------------------------ P2Q-08
def _path():
    return {"path_id": "ICP-34-SENSE", "bridges_isolated_potentials": True,
            "connects_to": ["grounded_pressure_transducer", "daq_instrument_chassis"],
            "isolating_section_id": "SYN-ISO-1",
            "qualification": {"scope": "COMPLETE_INSTALLED_PATH",
                              "items": {k: {"verified_id": "SYN-" + k} for k in (
                                  "isolator", "fittings", "tubing", "pressure_transducer_interface", "feedthroughs",
                                  "mounting", "representative_pressure_gas_condition",
                                  "electrical_configuration_floating_bias_state")},
                              "no_unintended_current_return_path_demonstrated": True,
                              "grounding_topology_id": "SYN-SPG", "electrical_configuration_id": "SYN-FLOAT-1"}}


def test_p2_a9_16_isolation_path_rules(rules):
    ok = rules.isolation_path_check(_path())
    assert ok["status"] == rules.ISOLATION_QUALIFIED and ok["admits_floating_or_biased_point"] is True
    p = _path()
    p["qualification"]["items"]["feedthroughs"] = {"not_applicable_reason": "SYN no feedthrough in this path"}
    assert rules.isolation_path_check(p)["status"] == rules.ISOLATION_QUALIFIED
    for mut in (lambda q: q["items"].pop("fittings"), lambda q: q.update(scope="NOMINAL_COMPONENT_ONLY"),
                lambda q: q.update(no_unintended_current_return_path_demonstrated=False),
                lambda q: q.pop("grounding_topology_id")):
        p = _path()
        mut(p["qualification"])
        r = rules.isolation_path_check(p)
        assert r["status"] == "NOT_EVALUATED_ISOLATION_NOT_QUALIFIED" and r["admits_floating_or_biased_point"] is False
    p = _path()
    del p["isolating_section_id"]
    assert rules.isolation_path_check(p)["status"] == "NOT_EVALUATED_ISOLATION_NOT_QUALIFIED"
    nb = {"path_id": "ICP-34-SENSE", "bridges_isolated_potentials": False,
          "non_bridging_documentation": {"document_id": "SYN-DOC", "basis": "non-conductive line, same potential"}}
    assert rules.isolation_path_check(nb)["status"] == rules.NON_BRIDGING_DOCUMENTED
    assert rules.isolation_path_check(dict(nb, non_bridging_documentation=None))["status"] == \
        "NOT_EVALUATED_NON_BRIDGING_UNDOCUMENTED"
    unk = rules.isolation_path_check({"path_id": "ICP-34-SENSE", "bridges_isolated_potentials": None})
    assert unk["status"] == "NOT_EVALUATED_BRIDGING_UNKNOWN" and unk["admits_floating_or_biased_point"] is False
    with pytest.raises(rules.RuleError):
        rules.isolation_path_check(dict(_path(), connects_to=["nowhere"]))


# ------------------------------------------------------------------------------------------------ P2Q-09
OBS = {"photodiode_line_of_sight_ok": True, "photodiode_saturated": False, "optical_signal_V": 0.1,
       "unlit_threshold_V": 0.5}


def _ind(name, ya, yb, u=0.1, **kw):
    return dict({"name": name, "applicable": True, "y_a": ya, "y_b": yb, "u_a": u, "u_b": u}, **kw)


def test_p2_a9_16_hm_r06_classification(rules):
    none = rules.classify_with_hm_r06(OBS, [_ind("pressure_step", 1.0, 1.25)])          # z = 1.77
    assert none["state"] == "UNLIT" and none["electrical_indicator_basis"] == []
    res = rules.classify_with_hm_r06(OBS, [_ind("pressure_step", 1.0, 1.3), _ind("antenna_rf_current_step", 2.0, 2.05),
                                           _ind("collector_or_current_path_step", 0.0, 0.5)])
    assert res["state"] == "UNCERTAIN"
    assert res["electrical_indicator_basis"] == ["pressure_step", "collector_or_current_path_step"]
    # reflected power only at fixed tuning; impedance only with valid impedance data
    refl = _ind("reflected_power_or_gamma_step_fixed_tuning", 1.0, 5.0)
    assert rules.classify_with_hm_r06(OBS, [refl])["state"] == "UNLIT"
    assert rules.classify_with_hm_r06(OBS, [dict(refl, fixed_tuning=True)])["state"] == "UNCERTAIN"
    imp = _ind("impedance_R_or_X_step", 1.0, 5.0)
    assert rules.classify_with_hm_r06(OBS, [imp])["state"] == "UNLIT"
    assert rules.classify_with_hm_r06(OBS, [dict(imp, valid_impedance_data=True)])["state"] == "UNCERTAIN"
    # correlation (covariance) enters the combined uncertainty
    cor = _ind("pressure_step", 1.0, 1.25, r=0.5)                                        # u_c = 0.1 -> z = 2.5
    assert rules.classify_with_hm_r06(OBS, [cor])["state"] == "UNCERTAIN"
    for o in (dict(OBS, photodiode_line_of_sight_ok=False), dict(OBS, photodiode_saturated=True),
              dict(OBS, unlit_threshold_V=None)):
        assert rules.classify_with_hm_r06(o, [])["state"] == "UNCERTAIN"
    with pytest.raises(rules.RuleError):
        rules.classify_with_hm_r06(OBS, [{"name": "pressure_step", "applicable": True, "y_a": 1.0, "y_b": 2.0}])
    with pytest.raises(rules.RuleError):
        rules.classify_with_hm_r06(OBS, [_ind("guess_step", 1.0, 2.0)])
    lit = dict(OBS, optical_signal_V=2.0, threshold_basis={"dark_background_record_id": "SYN-D",
                                                           "rf_powered_known_unlit_record_id": "SYN-U",
                                                           "known_lit_p1_record_id": "SYN-L",
                                                           "frozen_before_p2_map": True},
               lit_mode_assignment="H_MODE", mode_indicator_basis="SYN HM-R06 indicators")
    r = rules.classify_with_hm_r06(lit, [_ind("pressure_step", 1.0, 2.0)])
    assert r["state"] == "H_MODE"                                     # lit -> E/H rule, not overridden


def test_p2_a9_16_transition_criteria_frozen_before_first_reduction(rules):
    reg = {"criteria_id": "SYN-TC", "frozen_utc": "2026-11-01T00:00:00Z", "form": "k_times_uc", "k_transition": 2.0,
           "indicators": list(rules.HM_R06_INDICATORS)}
    assert rules.transition_criteria_registration_check(reg, "2026-11-02T00:00:00Z")["status"] == \
        "FROZEN_BEFORE_FIRST_HOT_MAP_REDUCTION"
    assert rules.transition_criteria_registration_check(reg, "2026-11-01T00:00:00Z")["status"] == \
        "NOT_EVALUATED_REGISTRATION"
    assert rules.transition_criteria_registration_check(None, "2026-11-02T00:00:00Z")["status"] == \
        "NOT_EVALUATED_REGISTRATION"
    for bad in (dict(reg, k_transition=3.0), dict(reg, form="absolute_step"), dict(reg, indicators=["pressure_step"])):
        with pytest.raises(rules.RuleError):
            rules.transition_criteria_registration_check(bad, "2026-11-02T00:00:00Z")


def test_p2_a9_16_framework_eh_form_fixed(mod):
    fw = mod.FW
    assert fw.K_TRANSITION == 2.0 and fw.EH_FORMS == ("k_times_uc",)
    sw = [{"index": i, "direction": "up", "photodiode_valid": True, "tuning_state_id": "T", "photodiode_V": v,
           "P_reflected_W": 1.0, "I_ant_rms_A": 1.0, "u_photodiode_V": 0.05, "u_P_reflected_W": 0.1,
           "u_I_ant_rms_A": 0.1} for i, v in enumerate((0.1, 2.0))]
    base = {"form": "k_times_uc", "basis": "SYN", "frozen_before_p2_map": True, "k": 2.0}
    assert fw.detect_eh_transitions(sw, base)["events"][0]["class"] == "TRANSITION_CANDIDATE_OPTICAL_ONLY"
    for bad in (dict(base, k=1.5), dict(base, k=None), {"form": "absolute_step", "basis": "SYN",
                                                       "frozen_before_p2_map": True, "step_photodiode_V": 0.5,
                                                       "step_P_reflected_W": 1.0, "step_I_ant_rms_A": 1.0}):
        with pytest.raises(fw.CriteriaMissingError):
            fw.detect_eh_transitions(sw, bad)


# ------------------------------------------------------------------------------------------------ P2Q-02
def test_p2_a9_16_rf_metrology_package(d):
    ins = {i["id"]: i for i in d["instrument_list"]}
    for i in ("INS-P2-01", "INS-P2-04", "INS-P2-05", "INS-P2-06", "INS-P2-09"):
        assert ins[i]["procurement_package_a9_8"].startswith("RF_METROLOGY_PACKAGE"), i
    assert "RF_METROLOGY_PACKAGE" in ins["INS-P2-07"]["procurement_package_a9_8"].split("(b)")[1]
    assert "RF_METROLOGY_PACKAGE" in ins["INS-P2-08"]["procurement_package_a9_8"]
    assert ins["INS-P2-12"]["procurement_package_a9_8"].startswith("RF power generation / matching")
    assert all("procurement_package_a9_8" in i for i in d["instrument_list"])
    assert "purchase order" not in json.dumps([i["procurement_package_a9_8"] for i in d["instrument_list"]]).lower()


# ------------------------------------------------------------------------------------------------ P2Q-10 / ICPQ-11
def _env(fw):
    return {"data_classes": ["measured"], "coverage": {"complete": True},
            "P_forward_W_at_RP_CPL": {"min": 10.0, "max": 400.0}, "line_V_peak_max_V": {"min": 1.0, "max": 300.0},
            "line_I_peak_max_A": {"min": 0.1, "max": 5.0}, "antenna_peaks_vi_measured": {"V_peak_V": {"max": 900.0}}}


def test_p2_a9_16_rating_policy_stress_classes(mod):
    fw = mod.FW
    assert (fw.K_RF, fw.K_CONTINUOUS_PI, fw.K_THERMAL) == (1.5, 1.25, 1.2)
    rs = fw.rating_structure(_env(fw), feedthrough_peaks={"feedthrough_V_peak_max_V": 320.0,
                                                          "feedthrough_I_peak_max_A": 6.0},
                             match_element_peaks={"V_peak_max_V": 1000.0, "I_peak_max_A": 8.0})
    rows = {r["id"]: r for r in rs["rows"]}
    assert rs["RF_COMPONENT_RATINGS"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert rows["RC-ANT-V"]["candidate_minimum"]["value"] == pytest.approx(1350.0)
    assert set(rows["RC-ANT-V"]["separate_qualifications"]) == {"Paschen", "creepage / clearance",
                                                                "combined RF + DC stress"}
    assert all(v.startswith("OPEN") for v in rows["RC-ANT-V"]["separate_qualifications"].values())
    assert rows["RC-CPL-V"]["candidate_minimum"]["value"] == pytest.approx(450.0)
    assert rows["RC-COAX-I"]["candidate_minimum"]["value"] == pytest.approx(6.25)
    assert rows["RC-GEN-PFWD"]["candidate_minimum"]["value"] == pytest.approx(500.0)
    assert rows["RC-FT-V"]["candidate_minimum"]["value"] == pytest.approx(480.0)
    assert rows["RC-FT-I"]["candidate_minimum"]["value"] == pytest.approx(7.5)
    assert rows["RC-MATCH-EL"]["candidate_minimum"] == {"V_peak_V": 1500.0, "I_peak_A": 10.0,
                                                         "status": fw.CANDIDATE_STATUS}
    assert rows["RC-HEAT"]["candidate_minimum"].startswith("TBD_AFTER_EVIDENCE")       # ICPQ-10 decided (repair F1)
    for r in rs["rows"]:
        assert r["rating_status"] == "TBD_AFTER_IMPEDANCE_MAP"
    # stricter supplier derating governs; never the product of two margins
    rs2 = fw.rating_structure(_env(fw), component_margins={"RC-CPL-V": 1.8, "RC-GEN-PFWD": 1.1})
    rows2 = {r["id"]: r for r in rs2["rows"]}
    assert rows2["RC-CPL-V"]["candidate_minimum"]["value"] == pytest.approx(540.0)
    assert rows2["RC-GEN-PFWD"]["candidate_minimum"]["value"] == pytest.approx(500.0)       # owner 1.25 governs
    with pytest.raises(fw.RatingInputError):
        fw.rating_structure(_env(fw), k_rf=2.0)
    with pytest.raises(fw.RatingInputError):
        fw.rating_structure(_env(fw), component_margins={"RC-UNKNOWN": 1.5})
    syn = dict(_env(fw), data_classes=["synthetic_test"])
    assert all(isinstance(r["candidate_minimum"], str) for r in fw.rating_structure(syn)["rows"])


def test_p2_a9_16_transient_below_manufacturer_rating(rules):
    assert rules.transient_stress_check(100.0, None)["status"] == "NOT_EVALUATED_NO_MANUFACTURER_TRANSIENT_RATING"
    assert rules.transient_stress_check(100.0, {"document_id": "TBD", "value": 200.0})["status"] == \
        "NOT_EVALUATED_NO_MANUFACTURER_TRANSIENT_RATING"
    r = {"document_id": "SYN-DATASHEET", "value": 200.0}
    assert rules.transient_stress_check(150.0, r)["status"] == rules.TRANSIENT_BELOW
    assert rules.transient_stress_check(200.0, r)["status"] == rules.TRANSIENT_EXCEEDS


# ------------------------------------------------------------------------------------------------ P2Q-06
def test_p2_a9_16_zm_b_stand_rules(rules):
    agree = rules.method_agreement(ZA, dict(ZB, R_ohm=1.1, uncertainty_budget_id="B"))
    dis = rules.method_agreement(ZA, dict(ZB, R_ohm=1.5, uncertainty_budget_id="B"))
    miss = rules.method_agreement(ZA, None)
    q = rules.zm_b_stand_qualification([agree, agree])
    assert q["status"] == rules.ZM_B_STAND_QUALIFIED
    assert rules.zm_b_stand_qualification([agree, dis])["status"] == rules.ZM_B_STAND_BLOCKED
    assert rules.zm_b_stand_qualification([agree, miss])["status"] == rules.ZM_B_STAND_NOT_QUALIFIED
    assert rules.zm_b_stand_qualification([])["status"] == rules.ZM_B_STAND_NOT_QUALIFIED
    reg = {"interval_id": "SYN-INT", "frozen_utc": "2026-11-01T00:00:00Z", "max_records_between_crosschecks": 20}
    x = [dict(agree, configuration_id="CFG-1", comparison_id="X1")]
    rec = {"configuration_id": "CFG-1", "records_since_crosscheck": 5}
    assert rules.stand_zm_b_record_check(rec, q, x, reg)["status"] == "ZM_B_STAND_RECORD_ADMISSIBLE"
    assert rules.stand_zm_b_record_check(rec, q, x, None)["status"] == "NOT_EVALUATED_REGISTRATION"
    assert rules.stand_zm_b_record_check(dict(rec, configuration_id="CFG-2"), q, x, reg)["status"] == \
        "NOT_EVALUATED_NO_ZM_A_CROSSCHECK_AFTER_CHANGE"
    assert rules.stand_zm_b_record_check(dict(rec, records_since_crosscheck=21), q, x, reg)["status"] == \
        "NOT_EVALUATED_PERIODIC_ZM_A_CROSSCHECK_DUE"
    assert rules.stand_zm_b_record_check(rec, {"status": rules.ZM_B_STAND_NOT_QUALIFIED}, x, reg)["status"] == \
        rules.ZM_B_STAND_NOT_QUALIFIED
    assert rules.stand_zm_b_record_check(rec, q, [dict(dis, configuration_id="CFG-1")], reg)["status"] == \
        rules.ZM_B_STAND_BLOCKED
    assert rules.stand_zm_b_record_check(dict(rec, vi_probe_line_across_stage=True), q, x, reg)["status"] == \
        "REFUSED_UNNECESSARY_VI_LINE_ACROSS_STAGE"


# ------------------------------------------------------------------------------------------------ F6-OQ-02
def test_p2_a9_16_geometry_inside_drawing_envelope(rules):
    env = {"drawing_id": "SYN-KC1", "revision": "B", "bounds": {"gap_mm": [1.0, 5.0], "turns": [2, 6]}}
    pt = {"geometry_id": "G1", "drawing_id": "SYN-KC1", "drawing_revision": "B", "variables": {"gap_mm": 3.0, "turns": 4}}
    assert rules.geometry_point_check(pt, env)["status"] == rules.INSIDE_ENVELOPE
    out = rules.geometry_point_check(dict(pt, variables={"gap_mm": 6.0, "turns": 4}), env)
    assert out["status"] == rules.OUTSIDE_ENVELOPE and out["variables"] == ["gap_mm"]
    assert rules.geometry_point_check(dict(pt, variables={"diameter_mm": 3.0}), env)["status"] == \
        "REFUSED_VARIABLE_NOT_BOUNDED_BY_DRAWING"
    assert rules.geometry_point_check(dict(pt, drawing_revision="C"), env)["status"] == \
        "REFUSED_DRAWING_REVISION_MISMATCH"
    assert rules.geometry_point_check(pt, None)["status"] == "NOT_EVALUATED_REGISTRATION"
    assert rules.geometry_point_check(pt, dict(env, bounds={}))["status"] == "NOT_EVALUATED_REGISTRATION"


# ------------------------------------------------------------------------------------------------ hygiene
def test_p2_a9_16_rules_hygiene():
    for name in ("p2_a9_16_rules.py", "a9_16_application.py"):
        src = (LANE / name).read_text(encoding="utf-8")
        imports = set(re.findall(r"^(?:from|import) ([\w.]+)", src, re.M))
        assert imports <= {"__future__", "importlib.util", "math", "pathlib", "copy"}, (name, imports)
        assert '"PASS"' not in src and "urllib" not in src and "subprocess" not in src
        assert not re.search(r"^\s*(?:from|import)\s+(?:abep_sim|archengine)", src, re.M)



# ------------------------------------------------------------------ A9.16 repair lane: F1 (ICPQ-10) / F5 (OQ-A910-06)
def test_p2_a9_16_icpq10_alternative_a_only(d, fw):
    """A9.12 S5.1 ICPQ-10: alternative A, Q_ICP,bound = 1.20 x (P_fwd,max + P_d,max); 'Do not use 1.20 x 1.5 kW'. P2
    records it OWNER_DECIDED, keeps B only as rejected history, RC-HEAT references the P3 bound rule and stays
    TBD_AFTER_EVIDENCE; any heat_load_option other than A is refused."""
    h = d["framework"]["heat_load_alternatives"]
    assert h["status"] == "OWNER_DECIDED" and h["selected_alternative"] == "A"
    assert h["decision"]["decision_json_sha256"] == "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d"
    assert h["bound_rule"] == "docs/experiments/hall_icp/p3_coupled_thermal/p3_a9_16_rules.py::icp43_total_module_bound"
    hist = {x["disposition"].split(" ")[0]: x["alternative"] for x in h["history_alternatives_as_raised"]}
    assert hist["OWNER_REJECTED"].startswith("B:") and "1.5 kW" in hist["OWNER_REJECTED"]
    items = {i["id"]: i for i in d["items"]}
    assert "1.20 x (P_fwd,max + P_d,max)" in items["FW-19"]["value"] and items["FW-19"]["evidence_class"] is None
    assert "TBD_OWNER" not in items["FW-19"]["value"]
    idp = {x["id"]: x for x in d["interface_demands"]}["IDP2-22"]
    assert idp["status"].startswith("ANSWERED: ICPQ-10 alternative A") and "except" not in idp["status"]
    txt = json.dumps(d)
    assert "neither selected" not in txt and "not applied by this lane" not in txt
    env = {"data_classes": ["measured"], "coverage": {"complete": True}, "P_forward_W_at_RP_CPL": {"max": 400.0}}
    for opt in (None, "A"):
        heat = next(r for r in fw.rating_structure(env, heat_load_option=opt)["rows"] if r["id"] == "RC-HEAT")
        assert heat["candidate_minimum"].startswith("TBD_AFTER_EVIDENCE") and "1.20 x 1.5 kW" in heat["owner_input_value"]
    for bad in ("B", "1.20 x 1.5 kW", 1800.0):
        with pytest.raises(fw.RatingInputError):
            fw.rating_structure(env, heat_load_option=bad)
    md = OUT_MD.read_text(encoding="utf-8")
    assert "ICPQ-10 heat-load bound (OWNER_DECIDED" in md


def test_p2_a9_16_oq_a910_06_owner_decided(d):
    """A9.12 S5.8 OQ-A910-06: 600 W kept temporarily (four labels), superseded by the P2-derived RF thermal envelope;
    P2 points to p3_a9_16_rules.rf_thermal_basis as the consumer of that envelope."""
    out = {o["id"]: o for o in d["p2_outputs_later"]}["OQ-A910-06"]
    assert out["status"].startswith("OWNER_DECIDED (A9.12 S5.8") and "rf_thermal_basis" in out["status"]
    assert out["source"] == "docs/decisions/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json"
    rows = {o["question_id"]: o for o in d["owner_answers_applied"] if o.get("question_id")}
    assert rows["OQ-A910-06"]["owner_answer"] == "YES_600W_TEMPORARY"
    assert rows["ICPQ-10"]["owner_answer"] == "A_1_20_X_PFWD_PLUS_PD"
