"""Focused tests for the owner decisions of 2026-10-01 applied to the P1 ICP bench (A9.16 step 1, lane P1 ICP BENCH):
A9.8 (P1Q-04, P1Q-09, P1Q-11, P1Q-18, P1Q-20, P1-IT-52, P1-IT-55, OQ-RFQV2-06, OQ-RFQV2-08), A9.10 (P1Q-02, P1Q-03,
P1Q-05, P1Q-06, P1Q-07, P1Q-08, P1Q-19, P1Q-24, OQ-RFQV2-09), A9.11 (P1Q-01), A9.14 (P1Q-17, P1Q-12, OD5, ICPQ-08,
F6-OQ-03). One test per rule, refusals included. Every number below is a SYNTHETIC fixture (never data); the owner
numbers asserted are exactly the owner's. Fast, no Julia. Run: python -m pytest -q tests/test_p1_a9_16_owner_rules.py
"""
import copy
import hashlib
import importlib.util
import json
import math
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "experiments", "hall_icp", "p1_icp_bench")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load(os.path.join(ROOT, "tests", "test_p1_icp_bench.py"), "p1_bench_fixtures_for_a9_16")   # shared fixtures


@pytest.fixture(scope="module")
def red():
    return _load(os.path.join(DIR, "p1_reducer.py"), "p1_reducer_a9_16")


@pytest.fixture(scope="module")
def camp():
    return _load(os.path.join(DIR, "p1_campaign.py"), "p1_campaign_a9_16")


@pytest.fixture(scope="module")
def rules():
    return _load(os.path.join(DIR, "p1_a9_16_rules.py"), "p1_a9_16_rules_test")


@pytest.fixture(scope="module")
def doc():
    with open(os.path.join(DIR, "p1_icp_bench_v1.json"), encoding="utf-8") as f:
        return json.load(f)


def _idx(rep):
    return {x["record_id"]: x for x in rep["raw_record_index"]}


def _outcome(rep, rid):
    return {o["record_id"]: o for o in rep["capacity"]["point_outcomes"]}[rid]


def _rec(b, rid):
    return [r for r in b["records"] if r["record_id"] == rid][0]


T2 = "2000-01-01T01:00:00Z"


# ------------------------------------------------------------------ provenance of the application
def test_p1_a9_16_decisions_cited_by_path_sha_and_question(doc):
    applied = [a for a in doc["owner_answers_applied"] if a["kind"].startswith("owner decision")]
    assert applied
    for a in applied:
        with open(os.path.join(ROOT, a["decision_file"]), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == a["decision_json_sha256"], a["id"]
        assert a["question_id"] and a["decision_json_sha256"] in a["how_applied"]
    ids = {a["id"] for a in applied}
    for k in ("A9.8 P1Q-04", "A9.8 P1Q-09", "A9.8 P1Q-11", "A9.8 P1Q-18", "A9.8 P1Q-20", "A9.8 P1-IT-52",
              "A9.8 P1-IT-55", "A9.8 OQ-RFQV2-06", "A9.8 OQ-RFQV2-08", "A9.10 P1Q-02", "A9.10 P1Q-03", "A9.10 P1Q-05",
              "A9.10 P1Q-06", "A9.10 P1Q-07", "A9.10 P1Q-08", "A9.10 P1Q-19", "A9.10 P1Q-24", "A9.10 OQ-RFQV2-09",
              "A9.11 P1Q-01", "A9.14 P1Q-17", "A9.14 P1Q-12", "A9.14 OD5", "A9.14 ICPQ-08", "A9.14 F6-OQ-03",
              "A9.15 RFP-COMPLIANT"):
        assert k in ids, k
    # every decision json / verbatim md is pinned and the pin verifies
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    for d in doc["a9_16_incorporation"]["decisions"]:
        assert pins[d["json"]] == d["json_sha256"] and pins[d["verbatim"]] == d["verbatim_sha256"]
    # A9.16 repair COR-01: the as-raised questions stay in open_owner_questions (state-v4 read-back); none is open now
    assert doc["owner_questions_open_now"] == []
    cur = {c["id"]: c for c in doc["owner_question_status_current"]}
    assert set(cur) == {q["id"] for q in doc["open_owner_questions"]}
    assert all(c["status_current"] == "OWNER_DECIDED" and c["decided_by"] for c in cur.values())
    # every cited test exists
    src = open(__file__, encoding="utf-8").read() + open(os.path.join(ROOT, "tests", "test_p1_icp_bench.py"),
                                                        encoding="utf-8").read()
    for a in doc["a9_16_incorporation"]["applied"]:
        for t in a["tests"]:
            assert "def " + t.split(" ")[0] + "(" in src, t
    for f in doc["a9_16_incorporation"]["fail_closed"]:
        assert "def " + f["test"].split("::")[1] + "(" in src, f["test"]


def test_p1_a9_16_xe_policy_not_contingency_wording(doc):
    """A9.15: no 'Xe contingency-only for C1' wording in the P1 package; the A9.1 ICP gas-mode baseline is unchanged."""
    hits = json.dumps(doc).lower().count("contingency-only")
    assert hits == 0, hits                                   # (count, not the text: keeps the failure report small)
    assert "G-REUSE" in doc["scope"]["gas_mode"]
    na = [x for x in doc["a9_16_incorporation"]["not_applicable"] if x["decision"] == "A9.15"]
    assert na and "does not remove the RFP-required system Xe capability" in na[0]["why"]


# ------------------------------------------------------------------ A9.8 P1Q-04 thermal abort / derate
def test_p1_a9_16_readiness_thermal_limits_required(red):
    rec = B.synth_readiness(red)
    assert red.reduce_readiness(rec)["g0_status"] == "G0_ENTRY_CONDITIONS_RECORDED"
    r2 = copy.deepcopy(rec)
    r2["thermal_limits"] = None
    out = red.reduce_readiness(r2)
    assert out["g0_status"] == "G0_NOT_EVALUATED_TBD" and any("P1Q-04" in t for t in out["tbd"])
    r3 = copy.deepcopy(rec)
    r3["thermal_limits"] = r3["thermal_limits"][1:]
    assert red.reduce_readiness(r3)["g0_status"] == "G0_NOT_EVALUATED_TBD"
    r4 = copy.deepcopy(rec)
    del r4["thermal_limits"]
    with pytest.raises(red.MissingInputError):
        red.reduce_readiness(r4)
    r5 = copy.deepcopy(rec)
    r5["thermal_limits"][0]["temperature_field"] = "T_sink_C"         # facility sink is not a component limit
    r5["thermal_limits"] = r5["thermal_limits"][:1]
    with pytest.raises(red.P1RecordError):
        red.reduce_readiness(r5)
    assert red.THERMAL_ABORT_MARGIN_K == 50.0


def test_p1_a9_16_thermal_abort_all_operation(red, camp):
    b = B.synth_bundle(red)
    surf = _rec(b, "SYNTH-OP-001")                                     # non-scoring ENGINEERING_SURFACE record
    surf["temperatures"]["T_antenna_C"] = 350.0                       # = synthetic limit 400 - 50 K
    rep = camp.run_campaign(b)
    x = _idx(rep)["SYNTH-OP-001"]
    assert x["disposition"] == "OUT_OF_DOMAIN" and any("UBQ-06 abort / derate" in r for r in x["reasons"])
    o = rep["owner_rules_a9_16"]
    assert o["thermal_status"] == "ABORT_DERATE_REQUIRED_RECORDED"
    assert any(t["status"] == "ABORT_DERATE_REQUIRED" and t["abort_derate_at_C"] == 350.0
               for t in o["thermal_protection"])
    surf["temperatures"]["T_antenna_C"] = 349.0
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-OP-001"]["disposition"] == "REDUCED"
    assert rep["owner_rules_a9_16"]["thermal_status"] == "NO_ABORT_DERATE_CONDITION_RECORDED"
    assert B._no_pass_anywhere(rep["owner_rules_a9_16"])


# ------------------------------------------------------------------ A9.8 P1Q-09 extraction topology
def test_p1_a9_16_chamber_wall_refused_surface_and_capacity(red):
    for rec in (B.synth_op(), B.synth_cap("SYNTH-W-CAP", 1.0, stage="P1-S4")):
        rec["extraction"]["electron_collecting_electrode"] = "CHAMBER_WALL_FACILITY_GROUND"
        with pytest.raises(red.ExtractionTopologyError, match="chamber wall"):
            red.validate_operating_point(rec)
    assert "CHAMBER_WALL_FACILITY_GROUND" not in red.EXTRACTION_ELECTRODES
    assert red.EXTRACTION_ELECTRODES_BY_HALL_STATE["OFF"] == ("DEDICATED_ELECTRON_COLLECTOR_TARGET",)
    assert set(red.REQUIRED_TERMINALS[("OFF", "DEDICATED_ELECTRON_COLLECTOR_TARGET")]) == {
        "collector_supply", "icp_body", "facility_ground", "electron_collector", "h1_body", "hall_anode"}


def test_p1_a9_16_target_bias_reference_and_geometry(red):
    red.validate_operating_point(B.synth_op())
    rec = B.synth_op()
    del rec["extraction"]["target_geometry_id"]
    with pytest.raises(red.ExtractionTopologyError, match="registered at P1-G0"):
        red.validate_operating_point(rec)
    rec = B.synth_op()
    rec["collector"]["reference_potential"] = "FACILITY_GROUND"
    with pytest.raises(red.ExtractionTopologyError, match="referenced"):
        red.validate_operating_point(rec)
    for v in (0.0, 5.0):
        rec = B.synth_op()
        rec["collector"]["V_collector_V"] = v
        with pytest.raises(red.ExtractionTopologyError, match="NEGATIVE"):
            red.validate_operating_point(rec)


def test_p1_a9_16_open_circuit_needs_physical_verification(red):
    for name in ("hall_anode", "icp_body"):
        rec = B.synth_op()
        del rec["terminals"][name]["physical_verification_id"]
        with pytest.raises(red.MissingInputError, match="physical"):
            red.validate_operating_point(rec)
    rec = B.synth_s7(red, "SYNTH-S7-PV", 0.5)                          # also on Hall-ON records
    rec["terminals"]["icp_body"]["physical_verification_id"] = ""
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)


# ------------------------------------------------------------------ A9.8 P1Q-18 confirmed
def test_p1_a9_16_p1q18_confirmed_reading(red):
    on, off = B._pair(tag="Q18", on_ie=3.0, off_ie=0.2)
    off["terminals"]["facility_ground"]["I_A"] = 0.005
    ev = red.kirchhoff_closure(off, B.CLOSE)
    assert ev["fractional_ok"] is False and ev["instrument_adequate_floored"] is False
    ic = B._ic(red, on, off)
    assert {"record_id": "SYNTH-Q18-ON", "outcome": "NOT_EVALUATED_INSTRUMENT"} in ic["capacity_point_outcomes"]
    assert red.CLOSURE_K_SIGMA == 3.0 and red.CLOSURE_FRACTION_MAX == 0.02


# ------------------------------------------------------------------ A9.8 P1Q-20 leakage term
def test_p1_a9_16_open_circuit_leakage_enters_u_R(red):
    on, off = B._pair(tag="LK")
    ev = red.kirchhoff_closure(on, B.CLOSE)
    meas = 4 * B.U1 ** 2                                               # four MEASURED channels of the fixture
    assert ev["u_R_A"] == pytest.approx(math.sqrt(meas + 2 * (1e-8) ** 2))
    assert ev["channels"]["hall_anode"]["u_basis"].startswith("LEAKAGE_ZERO_OFFSET_TERM")
    assert ev["channels"]["hall_anode"]["u_A"] == 1e-8
    big = copy.deepcopy(on)
    big["terminals"]["hall_anode"]["leakage"] = {"dwv_path_id": "SYNTH-PATH-1", "leakage_upper_bound_A": 1e-3,
                                                 "u_leakage_A": 1e-3}
    assert red.kirchhoff_closure(big, B.CLOSE)["u_R_A"] == pytest.approx(math.sqrt(meas + 1e-6 + 1e-16))
    for mutate, why in ((lambda t: t.pop("leakage"), "never u = 0"),
                        (lambda t: t["leakage"].update(dwv_path_id="SYNTH-PATH-X"), "not an accepted DWV path"),
                        (lambda t: t["leakage"].update(u_leakage_A=0.0), "not a valid leakage uncertainty")):
        bad = copy.deepcopy(on)
        mutate(bad["terminals"]["hall_anode"])
        ev = red.kirchhoff_closure(bad, B.CLOSE)
        assert ev["evaluable"] is False and any(why in r for r in ev["uncertainty_reasons"]), why
        ic = B._ic(red, bad, off)
        assert {"record_id": "SYNTH-LK-ON", "outcome": "NOT_EVALUATED_UNCERTAINTY"} in ic["capacity_point_outcomes"]
    low = dict(B.CLOSE, dwv_leakage_by_path={"SYNTH-PATH-1": 1e-7})       # bound below the measured DWV leakage
    ev = red.kirchhoff_closure(on, low)
    assert ev["evaluable"] is False and any("below the leakage" in r for r in ev["uncertainty_reasons"])


def test_p1_a9_16_leakage_negligible_only_registered(red):
    on, _ = B._pair(tag="NG")
    meas = 4 * B.U1 ** 2
    ev = red.kirchhoff_closure(on, dict(B.CLOSE, leakage_negligibility_ratio_max=0.1))
    assert ev["channels"]["hall_anode"]["u_A"] == 0.0
    assert ev["channels"]["hall_anode"]["u_basis"].startswith("DEMONSTRABLY_NEGLIGIBLE")
    assert ev["u_R_A"] == pytest.approx(math.sqrt(meas))
    big = copy.deepcopy(on)
    big["terminals"]["hall_anode"]["leakage"].update(leakage_upper_bound_A=1e-3, u_leakage_A=1e-3)
    ev = red.kirchhoff_closure(big, dict(B.CLOSE, leakage_negligibility_ratio_max=0.1))
    assert ev["channels"]["hall_anode"]["u_A"] == 1e-3                 # not negligible -> kept
    for bad in (0.0, -1.0):
        with pytest.raises(red.P1RecordError):
            red.kirchhoff_closure(on, dict(B.CLOSE, leakage_negligibility_ratio_max=bad))


def test_p1_a9_16_campaign_leakage_traced_to_accepted_dwv(red, camp):
    rep = camp.run_campaign(B.synth_bundle(red))
    assert _outcome(rep, "SYNTH-CAP-ON")["outcome"] == "CLOSURE_VALID_CANDIDATE"
    b = B.synth_bundle(red)
    b["records"][0]["dwv_tests"][0]["leakage_A"] = 5e-8                 # measured > the terminals' bound 1e-8
    rep = camp.run_campaign(b)
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "NOT_EVALUATED_UNCERTAINTY" and "below the leakage" in json.dumps(o)
    b = B.synth_bundle(red)
    b["registrations"]["closure_rule"]["dwv_leakage_by_path"] = {"SYNTH-PATH-1": 0.0}
    with pytest.raises(camp.CampaignInputError, match="derived from the governing P1-G0"):
        camp.run_campaign(b)


# ------------------------------------------------------------------ A9.8 P1Q-11 pressure-match registration
def test_p1_a9_16_pressure_match_registration(red, camp, rules):
    rep = camp.run_campaign(B.synth_bundle(red))
    assert rep["owner_rules_a9_16"]["pressure_match_registration"]["status"] == "REGISTERED"
    for mut, why in (({"frozen_utc": B.T1}, "not before the first P1-S4"),
                     ({"derived_from_record_ids": ["SYNTH-OP-001"]}, "not P1-S2 / P1-S3"),
                     ({"gauge_id": None}, "lacks gauge_id"),
                     ({"repeatability_basis": " "}, "repeatability_basis")):
        rep = camp.run_campaign(B.synth_bundle(red, facility_match=dict(B.MATCH_REG, **mut)))
        o = _outcome(rep, "SYNTH-CAP-ON")
        assert o["outcome"] == "NOT_EVALUATED_REGISTRATION", why
        assert why in json.dumps(rep["owner_rules_a9_16"]["pressure_match_registration"]), why
        assert rep["icp45_status"]["status"] != "EVALUATED_ENGINEERING_ONLY"
    assert rules.check_pressure_match_registration(None, [], []) != []


# ------------------------------------------------------------------ A9.8 P1-IT-52 stage domains
def test_p1_a9_16_domain_registration_unique_and_frozen(red, camp):
    b = B.synth_bundle(red)
    b["registrations"]["operating_domains"]["P1-S5"]["domain_id"] = "SYNTH-DOM-P1-S4"
    with pytest.raises(camp.CampaignInputError, match="unique domain_id"):
        camp.run_campaign(b)
    for key in ("frozen_utc", "basis"):
        b = B.synth_bundle(red)
        del b["registrations"]["operating_domains"]["P1-S4"][key]
        with pytest.raises(camp.CampaignInputError, match="P1-IT-52"):
            camp.run_campaign(b)
    b = B.synth_bundle(red)
    b["registrations"]["operating_domains"]["P1-S4"]["frozen_utc"] = B.T1      # not before the first P1-S4 record
    rep = camp.run_campaign(b)
    for rid in ("SYNTH-OP-001", "SYNTH-CAP-ON", "SYNTH-CAP-OFF"):
        x = _idx(rep)[rid]
        assert x["disposition"] == "OUT_OF_DOMAIN" and any("P1-IT-52" in r for r in x["reasons"]), rid
    assert _outcome(rep, "SYNTH-CAP-ON")["outcome"] == "OUT_OF_DOMAIN"
    assert "FAIL" not in json.dumps(rep["capacity"]["point_outcomes"])


# ------------------------------------------------------------------ A9.8 P1-IT-55 / OQ-RFQV2-06 / OQ-RFQV2-08 DWV
def test_p1_a9_16_dwv_per_path_limit_rules(red):
    base = B.synth_readiness(red)
    cases = [("basis_document_id", None, "G0_NOT_EVALUATED_TBD", "documented"),
             ("registered_utc", "1999-12-30T12:00:00Z", "G0_NOT_MET", "not before the test"),
             ("max_leakage_A", 1e-9, "G0_NOT_MET", "above registered per-path limit")]
    for k, v, status, why in cases:
        rec = copy.deepcopy(base)
        rec["dwv_tests"][0]["leakage_acceptance"][k] = v
        out = red.reduce_readiness(rec)
        assert out["g0_status"] == status and why in json.dumps(out), k
    rec = copy.deepcopy(base)
    rec["dwv_tests"][0]["leakage_acceptance"] = None
    out = red.reduce_readiness(rec)
    assert out["g0_status"] == "G0_NOT_EVALUATED_TBD" and "never a generic invented value" in json.dumps(out)
    for k in ("tracking_or_disruptive_discharge", "protective_trip", "breakdown_or_flashover"):
        rec = copy.deepcopy(base)
        rec["dwv_tests"][0][k] = True
        assert red.reduce_readiness(rec)["g0_status"] == "G0_NOT_MET", k
    rec = copy.deepcopy(base)
    del rec["dwv_tests"][0]["leakage_acceptance"]["u_measurement_A"]
    with pytest.raises(red.MissingInputError):
        red.reduce_readiness(rec)
    out = red.reduce_readiness(base)
    assert out["rows"]["dwv_leakage_by_path"] == {"SYNTH-PATH-1": 1e-8}      # feeds P1Q-20
    rec = copy.deepcopy(base)
    rec["dwv_tests"][0]["leakage_acceptance"]["basis_document_id"] = ""
    assert red.reduce_readiness(rec)["rows"]["dwv_leakage_by_path"] == {}   # not accepted -> not traceable


def test_p1_a9_16_dwv_path_classes_required(red):
    rec = B.synth_readiness(red)
    rec["dwv_tests"] = rec["dwv_tests"][:1]                              # no H-1 anode / discharge-supply path
    out = red.reduce_readiness(rec)
    assert out["g0_status"] == "G0_NOT_MET" and "OQ-RFQV2-06" in json.dumps(out["deficiencies"])
    rec = B.synth_readiness(red)
    rec["dwv_tests"][0]["path_class"] = "SOMETHING"
    with pytest.raises(red.P1RecordError):
        red.reduce_readiness(rec)
    assert red.DWV_V_TEST_V == 1050.0 and red.DWV_DURATION_S == 60.0 and red.ISOLATION_V_DESIGN_WITHSTAND_MIN_V == 525.0


def test_p1_a9_16_dwv_in_house_assembled_and_supplier(red):
    for k, v in (("test_configuration", "SUPPLIER_FACTORY_ONLY"), ("supplier_certificate", {}),
                 ("supplier_certificate", {"certificate_id": " "})):
        rec = B.synth_readiness(red)
        rec["dwv_tests"][0][k] = v
        out = red.reduce_readiness(rec)
        assert out["g0_status"] == "G0_NOT_MET" and "OQ-RFQV2-08" in json.dumps(out["deficiencies"]), (k, v)
    rec = B.synth_readiness(red)
    rec["dwv_tests"][0]["supplier_certificate"] = {"not_permitted_reason": "SYNTH rating below 1.05 kV"}
    assert red.reduce_readiness(rec)["g0_status"] == "G0_ENTRY_CONDITIONS_RECORDED"
    rec = B.synth_readiness(red)
    del rec["dwv_tests"][0]["configuration_id"]
    with pytest.raises(red.MissingInputError):
        red.reduce_readiness(rec)


def test_p1_a9_16_readiness_registrations(red):
    for k in ("ip_neu_interim_harness_drawing_id", "electron_collector_target_geometry_id"):
        rec = B.synth_readiness(red)
        rec["registrations"][k] = None
        out = red.reduce_readiness(rec)
        assert out["g0_status"] == "G0_NOT_EVALUATED_TBD" and any(k in t for t in out["tbd"]), k


# ------------------------------------------------------------------ A9.10 P1Q-02 / P1Q-03 / P1Q-08 / OQ-RFQV2-09
def test_p1_a9_16_start_limits_bounds(red):
    lim = red.check_start_attempt_limits(B.LIMITS)
    assert lim["I_limit_cap_A"] == 3.0
    big = dict(B.LIMITS, I_h1_safe_A=20.0, I_supply_capability_A=20.0)
    assert red.check_start_attempt_limits(dict(big, I_limit_A=8.0))["I_limit_cap_A"] == pytest.approx(1500.0 / 180.0)
    for bad in (dict(big, I_limit_A=9.0), dict(B.LIMITS, I_limit_A=3.5), dict(B.LIMITS, V_d_max_V=25.0)):
        with pytest.raises(red.RegistrationError):
            red.check_start_attempt_limits(bad)
    for bad in (dict(B.LIMITS, max_attempts=0), dict(B.LIMITS, max_attempts=2.0), dict(B.LIMITS, cooldown_condition=""),
                {k: v for k, v in B.LIMITS.items() if k != "frozen_utc"}):
        with pytest.raises(red.P1RecordError):
            red.check_start_attempt_limits(bad)


def test_p1_a9_16_start_limits_never_raised_after_failure(rules):
    r1 = dict(B.LIMITS, frozen_utc=B.T0)
    log = [{"timestamp_utc": B.T1, "sustained": False}]
    with pytest.raises(rules.RuleError, match="never increased"):
        rules.check_start_limit_revisions([r1, dict(B.LIMITS, frozen_utc=T2, V_d_max_V=12.0)], log)
    with pytest.raises(rules.RuleError):
        rules.check_start_limit_revisions([r1, dict(B.LIMITS, frozen_utc=T2, max_attempts=4)], log)
    assert len(rules.check_start_limit_revisions([r1, dict(B.LIMITS, frozen_utc=T2, V_d_max_V=8.0)], log)) == 2
    assert len(rules.check_start_limit_revisions([r1, dict(B.LIMITS, frozen_utc=T2, V_d_max_V=12.0)],
                                                 [{"timestamp_utc": B.T1, "sustained": True}])) == 2


def test_p1_a9_16_sustained_definition(red):
    sd = red.check_sustainment_definition(B.SUST)
    with pytest.raises(red.P1RecordError):
        red.check_sustainment_definition(dict(B.SUST, I_threshold_A=0.05))     # not above the pickup floor
    with pytest.raises(red.P1RecordError):
        red.check_sustainment_definition(dict(B.SUST, u_pickup_floor_A=0.0))
    step = {"signals": {"t_s": [0.0, 0.2, 0.4, 0.6], "I_d_A": [1.0, 1.0, 1.0, 1.0]}, "supply_enabled_connected": True,
            "artifact_or_transient_only": False, "interlock_invalidates": False}
    assert red.classify_sustained(step, sd)["sustained"] is True
    short = copy.deepcopy(step)
    short["signals"]["I_d_A"] = [1.0, 1.0, 0.0, 1.0]                      # 0.2 s continuous < 0.5 s registered
    assert red.classify_sustained(short, sd)["sustained"] is False
    for k, v in (("supply_enabled_connected", False), ("artifact_or_transient_only", True),
                 ("interlock_invalidates", True)):
        assert red.classify_sustained(dict(step, **{k: v}), sd)["sustained"] is False, k
    seq = B.synth_seq(red)
    seq["steps"][6]["signals"]["I_d_A"] = [0.0, 0.0]                      # recorded true contradicts the trace
    r = red.reduce_topology_control(seq, B.SUST, B.LIMITS)
    assert r["observation"] == "RECORDED_SUSTAINMENT_CONTRADICTS_REGISTERED_DEFINITION"
    seq = B.synth_seq(red)
    seq["steps"][3]["signals"]["V_d_V"] = [0.0, 50.0]                     # attempt above registered V_d,max
    assert red.reduce_topology_control(seq, B.SUST, B.LIMITS)["observation"] == "OUT_OF_DOMAIN_START_LIMITS_EXCEEDED"
    seq = B.synth_seq(red)
    seq["steps"][4]["sustainment_definition_id"] = "OTHER"
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(seq, B.SUST, B.LIMITS)
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(B.synth_seq(red), B.SUST, dict(B.LIMITS, registration_id="OTHER"))


def test_p1_a9_16_holdout_and_c1_absent(red):
    assert red.reduce_topology_control(B.synth_seq(red), B.SUST, B.LIMITS)["c1_configuration"] == "C1_NOT_INSTALLED"
    for k, v in (("hi_holdout_a_id", ""), ("c1_absence_record_id", None), ("c1_configuration", "C1_PRETEND"),
                 ("stage_id", "P1-S5")):
        seq = B.synth_seq(red)
        seq[k] = v
        with pytest.raises(red.SequenceError):
            red.reduce_topology_control(seq, B.SUST, B.LIMITS)
    seq = B.synth_seq(red)
    seq["c1_configuration"] = "C1_INSTALLED_DISCONNECTED"
    del seq["c1_absence_record_id"]
    assert red.reduce_topology_control(seq, B.SUST, B.LIMITS)["observation"] == "TAKAHASHI_LIKE_OBSERVATION"


def test_p1_a9_16_s6_entry_requires_registrations(red, camp):
    rep = camp.run_campaign(B.synth_bundle(red))
    assert _idx(rep)["SYNTH-SEQ-1"]["disposition"] == "REDUCED"
    assert rep["topology_control"][0]["observation"] == "TAKAHASHI_LIKE_OBSERVATION"
    for over in ({"start_attempt_limits": None}, {"sustainment_definition": None},
                 {"start_attempt_limits": dict(B.LIMITS, frozen_utc=B.T1)}):
        rep = camp.run_campaign(B.synth_bundle(red, **over))
        x = _idx(rep)["SYNTH-SEQ-1"]
        assert x["disposition"] == "OUT_OF_DOMAIN" and any("P1-S6 entry not met" in r for r in x["reasons"]), over
        assert rep["owner_rules_a9_16"]["p1_s6_entry"]["status"] == "NOT_MET"
    with pytest.raises(camp.CampaignInputError):
        camp.run_campaign(B.synth_bundle(red, start_attempt_limits=dict(B.LIMITS, I_limit_A=100.0)))


# ------------------------------------------------------------------ A9.10 P1Q-05 / P1Q-06
def test_p1_a9_16_reignition_minimum_three(red, camp):
    recs = [B.synth_ign("SYNTH-RI-%d" % i) for i in range(3)]
    recs[1]["start_state"] = "NOT_FROM_EXTINGUISHED_STATE"
    recs[2]["ignited"], recs[2]["ignition_delay_s"] = False, None
    pt = red.reduce_ignition(recs)["points"][0]
    assert pt["attempts"] == 3 and pt["successes"] == 2 and pt["independent_attempts"] == 2
    assert pt["reignition_evidence"] == "INSUFFICIENT_REIGNITION_EVIDENCE"
    m = red.dwell_metrics({"t_s": [0.0, 10.0, 20.0, 30.0], "I_e_A": [0.50, 0.51, 0.50, 0.51],
                           "P_refl_W": [4.0, 4.1, 4.0, 4.1]})
    v = red.classify_stable_region(m, B.CRIT, {"attempts": 3, "successes": 3, "independent_attempts": 2})
    assert v["verdict"] == "NOT_EVALUATED" and "INSUFFICIENT_REIGNITION_EVIDENCE" in v["reason"]
    with pytest.raises(red.P1RecordError):
        red.classify_stable_region(m, B.CRIT, {"attempts": 2, "successes": 2, "independent_attempts": 3})
    bad = B.synth_ign("SYNTH-RI-X")
    bad["start_state"] = "WARM"
    with pytest.raises(red.P1RecordError):
        red.validate_ignition(bad)
    bad = B.synth_ign("SYNTH-RI-Y")
    bad["restart_condition_met"] = "yes"
    with pytest.raises(red.MissingInputError):
        red.validate_ignition(bad)
    b = B.synth_bundle(red)
    _rec(b, "SYNTH-IGN-2")["restart_condition_met"] = False               # only 2 independent re-ignitions
    rep = camp.run_campaign(b)
    assert rep["stable_region"]["dwells"][0]["verdict"]["verdict"] == "NOT_EVALUATED"
    assert rep["stable_region"]["status"] != "REGION_OF_TESTED_POINTS_WITHIN_OWNER_CRITERIA"
    assert red.MIN_INDEPENDENT_REIGNITIONS == 3


def test_p1_a9_16_magnet_factor_f6(red, camp):
    for rec in (B.synth_ign("SYNTH-MG-1"), B.synth_op()):
        r = copy.deepcopy(rec)
        r["h1_magnet_state"] = "SYNTH-MAG-OFF"
        with pytest.raises(red.P1RecordError):
            (red.validate_ignition if r["record_kind"] == "ignition_attempt" else red.validate_operating_point)(r)
        r = copy.deepcopy(rec)
        r["h1_magnet_state"] = "REGISTERED_SETTING"
        with pytest.raises(red.MissingInputError):
            (red.validate_ignition if r["record_kind"] == "ignition_attempt" else red.validate_operating_point)(r)
        r.update(h1_magnet_field_setting_id="SYNTH-F6-SET", h1_coil_currents_A={})
        with pytest.raises(red.MissingInputError):
            (red.validate_ignition if r["record_kind"] == "ignition_attempt" else red.validate_operating_point)(r)
    b = B.synth_bundle(red)
    on = _rec(b, "SYNTH-IGN-0")
    on.update(h1_magnet_state="REGISTERED_SETTING", h1_magnet_field_setting_id="SYNTH-F6-SET",
              h1_coil_currents_A={"SYNTH-COIL-1": 1.0})
    for i in (1, 2):
        _rec(b, "SYNTH-IGN-%d" % i)["timestamp_utc"] = T2                # magnet-OFF baseline AFTER the magnet-on run
    rep = camp.run_campaign(b)
    x = _idx(rep)["SYNTH-IGN-0"]
    assert x["disposition"] == "OUT_OF_DOMAIN" and any("P1Q-06" in r for r in x["reasons"])
    on["timestamp_utc"] = "2000-01-01T02:00:00Z"                            # OFF first, then the registered setting
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-IGN-0"]["disposition"] == "REDUCED"
    row = [a for a in rep["ignition_map"]["attempts"] if a["record_id"] == "SYNTH-IGN-0"][0]
    assert row["h1_coil_currents_A"] == {"SYNTH-COIL-1": 1.0}


# ------------------------------------------------------------------ A9.10 P1Q-07 / P1Q-19 / P1Q-24
def test_p1_a9_16_i_d_max_ar_registration(red, camp):
    on, off = B._pair(tag="IDM")
    for k, v in (("electron_source", "ICP"), ("propellant", "N2"), ("envelope_id", "HI-ENG"),
                 ("scope", "FLIGHT_RELEVANT"), ("characterization_id", "")):
        with pytest.raises(red.RegistrationError):
            B._ic(red, on, off, reg=dict(B.REG, **{k: v}))
    with pytest.raises(red.MissingInputError):
        B._ic(red, on, off, reg=dict(B.REG, u_I_d_max_H1_A=0.0))
    with pytest.raises(red.RegistrationError):
        B._ic(red, on, off, reg=dict(B.REG, basis="STAND_CEILING"))
    b = B.synth_bundle(red)
    _rec(b, "SYNTH-CAP-ON")["stage_id"] = _rec(b, "SYNTH-CAP-OFF")["stage_id"] = "P1-S7"
    rep = camp.run_campaign(b)
    assert rep["owner_rules_a9_16"]["i_d_max_h1_ar_registration"]["status"] == "REGISTERED_BEFORE_P1_S7"
    b["registrations"]["i_d_max_registration"]["frozen_utc"] = B.T1      # not before the first P1-S7 record
    rep = camp.run_campaign(b)
    assert rep["owner_rules_a9_16"]["i_d_max_h1_ar_registration"]["status"] == "NOT_EVALUATED_REGISTRATION"
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "NOT_EVALUATED_REGISTRATION" and "P1Q-07" in json.dumps(o["reasons"])
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED"


def test_p1_a9_16_p1q19_owner_selected(red):
    assert red.P1Q19_OWNER_SELECTED == "REQUIRE_REGISTERED_GE_CHANNEL"
    assert "NOT_EVALUATED_REGISTRATION" in red.ICP45A_STATUSES
    on, off = B._pair(tag="S19")
    ic = B._ic(red, on, off, margin=dict(B.RULE, u_I_e_A=1e-4))
    assert ic["status"] == "NOT_EVALUATED_REGISTRATION" and ic["condition_met"] is None and "M_n_lower" not in ic
    assert "never replaced by the larger value" in " ".join(ic["flags"])


def test_p1_a9_16_k_loss_owner_constant(red):
    assert red.K_LOSS == 2.0
    v = dict(B.AT_POWER, k=None, k_registration_id=None)
    v["P_ref_load_W"] = 96.0 * (0.9375 + 2.5 * 0.0147)                  # ~2.5 sigma off: inconsistent at k = 2
    out = red.at_power_loss_check(v)
    assert out["k"] == 2.0 and out["status"] == "LOSS_MODEL_INCONSISTENT" and 2.0 < out["normalized_statistic"] < 3.0
    with pytest.raises(red.P1RecordError, match="k_loss"):
        red.at_power_loss_check(dict(v, k=3.0, k_registration_id="SYNTH-K"))
    # an inconsistent check leaves P_delivered / C_e as upper bounds (no relaxation)
    r = B.synth_cold("DUMMY_LOAD", "SYNTH-S1-1")
    r["loss_characterization"]["at_power_verification"] = v
    assert red.reduce_rf_cold_checkout([r])["verified_loss_ids"] == []


# ------------------------------------------------------------------ A9.11 P1Q-01
def test_p1_a9_16_stable_criteria_frozen_hashed(red, camp):
    rep = camp.run_campaign(B.synth_bundle(red))
    assert rep["stable_region"]["status"] == "REGION_OF_TESTED_POINTS_WITHIN_OWNER_CRITERIA"
    assert rep["owner_rules_a9_16"]["stable_criteria_registration"]["status"] == "FROZEN_AND_HASHED"
    assert B.CRIT["criteria_sha256"] in rep["stable_region"]["note"]
    assert "Z_stability" in rep["stable_region"]["dwells"][0]
    with pytest.raises(camp.CampaignInputError, match="freeze and hash"):          # edited after hashing
        camp.run_campaign(B.synth_bundle(red, stable_criteria=dict(B.CRIT, max_step_over_std=99.0)))
    for k in ("frozen_utc", "criteria_sha256", "derived_from_record_ids", "derivation_basis"):
        with pytest.raises(red.MissingInputError):
            red.check_stable_criteria({kk: vv for kk, vv in B.CRIT.items() if kk != k})
    late = B._frozen_crit(dict(B.CRIT, frozen_utc=B.T1))                          # at the dwell time
    rep = camp.run_campaign(B.synth_bundle(red, stable_criteria=late))
    assert rep["stable_region"]["status"] == "NOT_EVALUATED" and "P1Q-01" in rep["stable_region"]["note"]
    assert rep["stable_region"]["dwells"]                                           # raw dwells retained
    wrong = B._frozen_crit(dict(B.CRIT, derived_from_record_ids=["SYNTH-DWELL-1"]))
    rep = camp.run_campaign(B.synth_bundle(red, stable_criteria=wrong))
    assert rep["stable_region"]["status"] == "NOT_EVALUATED"
    assert rep["owner_rules_a9_16"]["stable_criteria_registration"]["status"] == "NOT_EVALUATED_REGISTRATION"


# ------------------------------------------------------------------ A9.14 P1Q-17 reverification
def _rev(**over):
    r = {"record_id": "SYNTH-REV-1", "path_id": "SYNTH-PATH-1", "trigger": "AFTER_REPAIR",
         "trigger_record_id": "SYNTH-NCR-1", "level_basis": "OWNER_DEVELOPMENT_ACCEPTANCE_LEVEL_A9_14_P1Q-17",
         "V_test_V": 700.0, "duration_s": 60.0, "current_limited": True,
         "pressure_gas_condition": "SYNTH representative Ar pressure", "sensitive_electronics_handling": "SYNTH "
         "disconnected", "leakage_A": 1e-8, "breakdown_or_flashover": False, "tracking_or_disruptive_discharge": False,
         "protective_trip": False, "test_utc": B.T1,
         "leakage_acceptance": {"criterion_id": "SYNTH-LEAK", "max_leakage_A": 1e-6, "basis_document_id": "SYNTH-SPEC",
                                "registered_utc": B.T0}}
    r.update(over)
    return r


def test_p1_a9_16_reverification_700v_triggered_only(rules):
    assert rules.reduce_dwv_reverification(_rev())["status"] == "REVERIFICATION_RECORDED"
    assert rules.REVERIFICATION_V_DC == 700.0 and rules.REVERIFICATION_DURATION_S == 60.0
    for over in ({"trigger": "ROUTINE_PRE_RUN"}, {"level_basis": "ECSS-E-ST-20C clause"},
                 {"pressure_gas_condition": ""}, {"trigger_record_id": None}):
        with pytest.raises(rules.RuleError):
            rules.reduce_dwv_reverification(_rev(**over))
    with pytest.raises(rules.RuleError, match="ECSS"):
        rules.reduce_dwv_reverification(_rev(sensitive_electronics_handling="per ECSS guidance"))
    for over in ({"V_test_V": 650.0}, {"duration_s": 30.0}, {"protective_trip": True}, {"leakage_A": 1e-5},
                 {"leakage_acceptance": dict(_rev()["leakage_acceptance"], registered_utc=T2)}):
        assert rules.reduce_dwv_reverification(_rev(**over))["status"] == "REVERIFICATION_DEFICIENT", over
    assert rules.reduce_dwv_reverification(_rev(leakage_acceptance=None))["status"] == \
        "REVERIFICATION_NOT_EVALUATED_TBD"


# ------------------------------------------------------------------ A9.14 OD5 / ICPQ-08 / F6-OQ-03
def test_p1_a9_16_od5_start_sequence(rules):
    full = list(rules.OD5_EVENTS)
    ok = {"sequence_id": "SYNTH-OD5", "variant": "ICP_NEUTRALIZER_BASELINE", "dwell_thermal_limits_id": "SYNTH-DTL",
          "attempts": [{"events": full[:5]}, {"events": full}]}
    assert rules.check_baseline_start_sequence(ok)["status"] == "OD5_SEQUENCE_CONFORMS"
    four = dict(ok, attempts=[{"events": full[:5]}] * 3 + [{"events": full}])
    assert rules.check_baseline_start_sequence(four)["status"] == "OD5_SEQUENCE_NONCONFORMING"
    hall_first = dict(ok, attempts=[{"events": [full[0], full[1], full[4], full[2]]}])
    assert rules.check_baseline_start_sequence(hall_first)["status"] == "OD5_SEQUENCE_NONCONFORMING"
    assert rules.check_baseline_start_sequence(dict(ok, dwell_thermal_limits_id=""))["status"] == \
        "NOT_EVALUATED_REGISTRATION"
    with pytest.raises(rules.RuleError):
        rules.check_baseline_start_sequence(dict(ok, variant="C1_SELECTED_VARIANT"))
    assert rules.check_baseline_start_sequence(dict(ok, variant="C1_SELECTED_VARIANT",
                                                    c1_qualified_sequence_id="SYNTH-C1-SEQ"))["status"] == \
        "C1_VARIANT_OWN_SEQUENCE"
    assert rules.OD5_MAX_ATTEMPTS == 3


def test_p1_a9_16_bz_mapping(rules):
    assert rules.check_bz_mapping({"map_id": "M1", "rf_state": "ENERGIZED"})["status"] == "NOT_EVALUATED_REGISTRATION"
    assert rules.check_bz_mapping({"map_id": "M1", "rf_state": "ENERGIZED",
                                   "gaussmeter_rf_immunity_record_id": "SYNTH-IMM"})["status"] == "BZ_MAP_ADMISSIBLE"
    reg = {"registration_id": "SYNTH-DELAY", "delay_s": 2.0, "delay_tolerance_s": 0.1,
           "decay_characterization_id": "SYNTH-DECAY", "frozen_utc": B.T0}
    assert rules.check_bz_mapping({"map_id": "M2", "rf_state": "RF_OFF", "rf_off_delay_s": 2.0})["status"] == \
        "NOT_EVALUATED_REGISTRATION"
    assert rules.check_bz_mapping({"map_id": "M2", "rf_state": "RF_OFF", "rf_off_delay_s": 2.05,
                                   "delay_registration": reg})["status"] == "BZ_MAP_ADMISSIBLE"
    assert rules.check_bz_mapping({"map_id": "M2", "rf_state": "RF_OFF", "rf_off_delay_s": 5.0,
                                   "delay_registration": reg})["status"] == "OUT_OF_DOMAIN"
    with pytest.raises(rules.RuleError):
        rules.check_bz_mapping({"map_id": "M3", "rf_state": "ON"})


def test_p1_a9_16_geometry_matrix(red, camp):
    mat = {"matrix_id": "SYNTH-GM", "frozen_utc": B.T0,
           "geometries": [{"geometry_id": "SYNTH-G1", "drawing_id": "SYNTH-DWG", "revision": "A",
                           "within_drawing_envelope": True},
                          {"geometry_id": "SYNTH-G2", "drawing_id": "SYNTH-DWG", "revision": "B",
                           "within_drawing_envelope": True}]}
    rep = camp.run_campaign(B.synth_bundle(red, icp_geometry_matrix=mat))
    assert _idx(rep)["SYNTH-OP-001"]["disposition"] == "OUT_OF_DOMAIN"            # no icp_geometry_id
    b = B.synth_bundle(red, icp_geometry_matrix=mat)
    for r in b["records"]:
        if r["record_kind"] == "icp_operating_point":
            r["icp_geometry_id"] = "SYNTH-G1"
    rep = camp.run_campaign(b)
    g = {x["geometry_id"]: x for x in rep["owner_rules_a9_16"]["geometry_matrix"]["geometries"]}
    assert g["SYNTH-G1"]["state"] == "MEASURED_GEOMETRY" and g["SYNTH-G2"]["state"] == "NOT_YET_MEASURED"
    assert rep["owner_rules_a9_16"]["geometry_matrix"]["surrogate"].startswith("NONE")
    bad = copy.deepcopy(mat)
    bad["geometries"][1]["within_drawing_envelope"] = False
    with pytest.raises(camp.CampaignInputError, match="drawing envelope"):
        camp.run_campaign(B.synth_bundle(red, icp_geometry_matrix=bad))
    assert camp.run_campaign(B.synth_bundle(red))["owner_rules_a9_16"]["geometry_matrix"]["status"] == "NOT_REGISTERED"


def test_p1_a9_16_campaign_report_schema_and_no_pass(red, camp):
    rep = camp.run_campaign(B.synth_bundle(red))
    with open(os.path.join(DIR, "p1_campaign_report_schema_v1.json"), encoding="utf-8") as f:
        sc = json.load(f)
    assert set(sc["required"]) == set(rep) and "owner_rules_a9_16" in sc["properties"]
    assert set(sc["properties"]["owner_rules_a9_16"]["required"]) == set(rep["owner_rules_a9_16"])
    reg_keys = sc["$defs"]["campaign_bundle"]["properties"]["registrations"]["required"]
    assert {"sustainment_definition", "start_attempt_limits", "icp_geometry_matrix"} <= set(reg_keys)
    assert B._no_pass_anywhere({k: v for k, v in rep.items() if k != "raw_records"})



# ------------------------------------------------------------------ A9.16 repair lane (F2, F9, COR-01 / COR-02)
def test_p1_a9_16_f2_langmuir_probe_required_and_capacity_exclusion(red, doc):
    """A9.8 S1.7 P3Q-01 option C: P1-M-30 is a REQUIRED Langmuir-probe diagnostic of the Ar P1 development campaign
    (cross-check of the primary calorimetric Q_collector, matched diagnostic runs); a probe never contaminates an
    ICP45_CAPACITY record unless its perturbation is shown negligible (undeclared state -> excluded too)."""
    m30 = {m["id"]: m for m in doc["measurements"]}["P1-M-30"]
    assert m30["status_a9_16"].startswith("REQUIRED (A9.8 P3Q-01 option C") and "Langmuir" in m30["quantity_a9_16"]
    assert "PRIMARY Q_collector evidence" in m30["instrument_class"] and "matched DIAGNOSTIC runs" in \
        m30["instrument_class"]
    assert "or none if the calorimetric" not in json.dumps(doc)       # the rejected 'or none' framing is gone
    xl = [p for p in doc["interface_demands"] if p["id"] in ("IF-P1-34", "IF-P1-36")]
    assert len(xl) == 2 and "TBD_OWNER (P3Q-01" not in json.dumps(xl)
    rec = B.synth_cap("SYN-PROBE", 0.5)
    assert red.capacity_structural_reasons(rec) == []                  # probe declared absent
    for cm in ({"langmuir_probe_present": True}, {"langmuir_probe_present": True,
                                                   "probe_perturbation_negligible_evidence_id": "TBD"}):
        r = copy.deepcopy(rec)
        r["capacity_monitoring"].update(cm)
        assert any("perturbation is negligible" in x for x in red.capacity_structural_reasons(r)), cm
    r = copy.deepcopy(rec)
    del r["capacity_monitoring"]["langmuir_probe_present"]
    assert any("Langmuir-probe state not declared" in x for x in red.capacity_structural_reasons(r))
    r = copy.deepcopy(rec)
    r["capacity_monitoring"].update(langmuir_probe_present=True,
                                    probe_perturbation_negligible_evidence_id="SYNTH-PROBE-PERTURBATION-STUDY")
    assert red.capacity_structural_reasons(r) == []
    applied = {a["id"] for a in doc["owner_answers_applied"]}
    assert "A9.8 P3Q-01" in applied


def test_p1_a9_16_repair_as_raised_readback_fields(doc):
    """A9.16 repair COR-01 / COR-02: the fields the immutable state-v4 / RFQ v2 builders read back keep their as-raised
    values; the current state is carried beside them and governs."""
    assert [q["id"] for q in doc["open_owner_questions"]][:2] == ["P1Q-01", "P1Q-02"]
    assert {q.get("status") for q in doc["open_owner_questions"]} <= {None, "OPEN", "TBD_OWNER"}
    res = {r["id"]: r for r in doc["a9_6_incorporation"]["derived_resolutions"]}
    assert {r["disposition"] for r in res.values()} <= {"DERIVED", "TBD_OWNER"}
    it36 = {i["id"]: i for i in doc["items"]}["P1-IT-36"]
    assert it36["status"].startswith("TBD (geometry / position / reference)")
    assert it36["status_a9_16"].startswith("OWNER_DECIDED (A9.8 P1Q-09") and "status_note" in it36
    md = open(os.path.join(DIR, "P1_ICP_BENCH.md"), encoding="utf-8").read()
    assert "Owner questions open now: 0." in md and "OWNER_DECIDED (A9.8 P1Q-09" in md
