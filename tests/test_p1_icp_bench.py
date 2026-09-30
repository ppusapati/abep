"""Tests for the P1 ICP electron-source bench package (fo_a9_p1_icp_bench, owner A9.3).

File checks, the deterministic builder (--check) and the pure reducer exercised with CLEARLY SYNTHETIC records
(synthetic = true, ids 'SYNTH-*'); the synthetic numbers are test fixtures, never data or predictions.
No network, no Julia, fast. Run: python -m pytest -q tests/test_p1_icp_bench.py
"""
import copy
import importlib.util
import json
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "experiments", "hall_icp", "p1_icp_bench")
BUILDER = os.path.join(DIR, "build_p1_icp_bench.py")
REDUCER = os.path.join(DIR, "p1_reducer.py")
JSON_PATH = os.path.join(DIR, "p1_icp_bench_v1.json")
MD_PATH = os.path.join(DIR, "P1_ICP_BENCH.md")
SCHEMA_PATH = os.path.join(DIR, "p1_bench_record_schema_v1.json")
A93_MD = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md")
A92 = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_2_a907_followup_owner_decisions.json")
FREEZE = {"NOW", "LOCK-1", "LOCK-2", "after-evidence"}
EV = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation",
      "owner-stated", None}


def _load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def red():
    return _load_mod(REDUCER, "p1_reducer_under_test")


@pytest.fixture(scope="module")
def bld():
    return _load_mod(BUILDER, "build_p1_icp_bench_under_test")


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ synthetic fixtures (NOT data)
def synth_op(**over):
    rec = {
        "schema": "p1_bench_record_v1", "record_kind": "icp_operating_point", "record_id": "SYNTH-OP-001",
        "run_id": "SYNTH-RUN-1", "stage_id": "P1-S4", "timestamp_utc": "2000-01-01T00:00:00Z", "synthetic": True,
        "labels": ["ENGINEERING_ONLY_NON_SCORING", "SYNTHETIC_TEST_FIXTURE"], "gas": "Ar", "gas_mode": "G-REUSE",
        "hall_discharge_state": "OFF",
        "rf": {"reference_plane": "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH", "P_fwd_W": 100.0, "P_refl_W": 4.0,
               "match_setting_id": "SYNTH-MATCH-A",
               "line_match_loss": {"status": "MEASURED", "value_W": 6.0, "source": "SYNTH-S1-CHAR"}},
        "generator": {"generator_class": "GROUND_FACILITY_ONLY_MAINS", "P_generator_input_W": 200.0,
                      "input_boundary": "mains AC input of the lab generator", "instrument": "SYNTH-PA"},
        "collector": {"I_e_A": 0.5, "V_collector_V": 40.0, "reference_potential": "facility ground"},
        "pressures": {"p_chamber_Pa": 0.01},
        "flows": {"mdot_Ar_H1_mg_s": 1.0, "mdot_icp_dedicated_mg_s": 0.0},
        "impedance": {"status": "NOT_MEASURED_PENDING_P2_CHAIN"},
        "terminals": {"collector_supply": {"I_A": 0.5, "basis": "MEASURED"},
                      "icp_body": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"},
                      "facility_ground": {"I_A": -0.49, "basis": "MEASURED"}},
        "temperatures": {k: 25.0 for k in ("T_icp_dielectric_C", "T_antenna_C", "T_collector_C", "T_match_C",
                                           "T_rf_source_C", "T_h1_pole_inner_C", "T_h1_pole_outer_C", "T_sink_C")},
        "rf_pickup_check": "DONE",
    }
    rec.update(over)
    return rec


def synth_seq(red, icp_off=False, icp_on=True):
    sig = {k: [0.0, 1.0] for k in red.SEQUENCE_SIGNALS}
    sig["t_s"] = [0.0, 1.0]
    steps = []
    for n, text in red.SEQUENCE_STEPS:
        s = {"step": n, "text": text, "signals": copy.deepcopy(sig)}
        if n == 5:
            s["sustained_discharge_observed"] = icp_off
            s["sustainment_definition_id"] = "SYNTH-SUST-DEF"
        if n == 7:
            s["sustained_discharge_observed"] = icp_on
        steps.append(s)
    return {"schema": "p1_bench_record_v1", "record_kind": "topology_control_sequence", "record_id": "SYNTH-SEQ-1",
            "run_id": "SYNTH-RUN-2", "stage_id": "P1-S6", "synthetic": True,
            "labels": ["ENGINEERING_ONLY_NON_SCORING", "SYNTHETIC_TEST_FIXTURE"], "gas": "Ar",
            "classification": "REQUIRED_ENGINEERING_CONTROL_NON_SCORING", "c1_disconnected": True,
            "hall_start_registration_id": "SYNTH-HALL-START", "steps": steps}


# ------------------------------------------------------------------ builder / file checks
def test_builder_check_reproduces_and_pins(bld):
    assert bld.main(["--check"]) == 0


def test_required_sections(doc):
    for k in ("scope", "stage_map", "topology_control", "items", "measurements", "derived_quantities",
              "safety_interlocks", "run_matrix", "hardware_readiness", "interface_demands", "owner_answers_applied",
              "open_owner_questions", "historical_reuse", "m16_impact", "h3_h4_inputs", "anchor_check",
              "authority_pins"):
        assert doc[k], k
    assert doc["status"] == "ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING"


def test_items_have_source_class_freeze(doc):
    for it in doc["items"]:
        for k in ("id", "name", "value", "units", "basis", "source", "status", "freeze_point"):
            assert it.get(k) not in (None, ""), (it["id"], k)
        assert it["freeze_point"] in FREEZE, it["id"]
        assert it["evidence_class"] in EV, it["id"]
        if it["evidence_class"] is None:
            assert re.match(r"^(TBD|PENDING)", str(it["value"])), it["id"]
        assert "PASS" not in str(it["status"]).replace("BYPASS", ""), it["id"]


def test_interface_demands_both_directions(doc):
    dirs = {d["direction"] for d in doc["interface_demands"]}
    assert dirs == {"to", "from"}
    for d in doc["interface_demands"]:
        assert d["units"] and d["status"]


def test_pending_parallel_lanes_marked_not_read(doc, bld):
    txt = json.dumps(doc)
    assert "PENDING docs/experiments/hall_icp/p2_impedance_map/" in txt
    assert "PENDING docs/procurement/rfq_a9_v2/" in txt
    for h in doc["hardware_readiness"]:
        assert h["rfq_v2_package"] == "PENDING docs/procurement/rfq_a9_v2/"
    pinned = {p["path"] for p in doc["authority_pins"]}
    assert not any("p2_impedance_map" in p or "rfq_a9_v2" in p for p in pinned)
    src = open(BUILDER, encoding="utf-8").read()
    assert "_load(P2_PATH" not in src and "_load(RFQ_V2_PATH" not in src


def test_governance_not_pinned(doc):
    pinned = {p["path"] for p in doc["authority_pins"]}
    for g in ("lane_registry_v1.json", "trigger_registry_v1.json", "runtime_state.json", "fired_triggers.jsonl"):
        assert not any(g in p for p in pinned)


def test_topology_steps_verbatim(doc):
    md = open(A93_MD, encoding="utf-8").read()
    steps = doc["topology_control"]["steps"]
    assert [s["step"] for s in steps] == list(range(1, 8))
    for s in steps:
        assert "%d. %s" % (s["step"], s["text"]) in md
    assert doc["topology_control"]["classification"] == "REQUIRED_ENGINEERING_CONTROL_NON_SCORING"


def test_anchor_confirmed_against_extraction(doc):
    tk = {r["id"]: r for r in doc["anchor_check"]}
    assert tk["TK-31"]["reported_value"] == "70 sccm (2.1 mg/s)" and tk["TK-31"]["locator"] == "p. 3 text"
    assert "CONFIRMED" in tk["TK-31"]["finding"]
    assert "MISMATCH" in tk["TK-40"]["finding"]
    assert abs(doc["arithmetic"]["ar_anchor_check_mg_s"]["value"] - 2.079) < 1e-9
    assert abs(doc["arithmetic"]["stand_ceiling_A"]["value"] - 8.3333) < 1e-9


def test_statuses_unchanged_and_no_pass(doc):
    with open(A92, encoding="utf-8") as f:
        a92 = json.load(f)
    assert doc["a9_2_statuses_carried_unchanged"] == a92["decisions"]["a9_10_statuses"]
    for s in doc["safety_interlocks"]:
        assert "PASS" not in s["status"] or "never" in s["status"]


def test_open_questions_new_only(doc):
    ids = [q["id"] for q in doc["open_owner_questions"]]
    assert all(i.startswith("P1Q-") for i in ids) and len(ids) == len(set(ids))
    for q in doc["open_owner_questions"]:
        assert q["proposed_answer"] and q["needed_by"]


def test_md_sections(doc):
    md = open(MD_PATH, encoding="utf-8").read()
    for h in ("(a) Items", "(b) Interface demands", "(c) Owner answers applied", "(d) Open owner questions",
              "(e) Historical reuse", "(f) M16 v3 impact", "(g) H3 / H4 inputs"):
        assert h in md, h


def test_schema_matches_reducer(red):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    op = sc["$defs"]["icp_operating_point"]
    assert op["required"] == list(red.OPERATING_POINT_REQUIRED)
    assert op["properties"]["rf"]["required"] == list(red.RF_REQUIRED)
    seq = sc["$defs"]["topology_control_sequence"]
    assert seq["required"] == list(red.SEQUENCE_REQUIRED)
    assert [s["text"] for s in seq["properties"]["x-step-texts-verbatim"]] == [t for _, t in red.SEQUENCE_STEPS]


def test_code_hygiene():
    red_src = open(REDUCER, encoding="utf-8").read()
    imports = re.findall(r"^(?:import|from) (\S+)", red_src, re.M)
    assert set(imports) <= {"math", "numpy"}, imports
    for p in (REDUCER, BUILDER, os.path.abspath(__file__)):
        assert ("xe" + "_ledger") not in open(p, encoding="utf-8").read(), p
    for banned in ("archengine", "plasma_devices", "hall_map", "open(", "requests", "urllib"):
        assert banned not in red_src, banned


# ------------------------------------------------------------------ reducer: happy path (synthetic)
def test_reduce_valid_record(red):
    out = red.reduce({"operating_points": [synth_op()]})
    row = out["operating_points"]["surface"][0]
    assert out["any_synthetic"] is True
    assert row["factors"]["P_delivered_W"] == pytest.approx(100.0 - 4.0 - 6.0)
    assert row["factors"]["P_delivered_kind"] == "P_RF_DELIVERED"
    assert row["gamma_abs"] == pytest.approx(math.sqrt(0.04))
    assert row["VSWR"] == pytest.approx(1.2 / 0.8)
    assert row["C_e_W_per_A"] == pytest.approx(90.0 / 0.5)
    assert row["C_e_DC_W_per_A"] == pytest.approx(400.0)
    assert "NOT P_bus" in row["C_e_DC_boundary"]
    assert row["closure_residual_rel"] == pytest.approx(0.01 / 0.5)
    assert "UNRESOLVED" in row["thermal_status"]
    assert out["operating_points"]["summary"]["icp45a"]["status"] == "NOT_EVALUATED"


def test_reduce_is_deterministic(red):
    b = {"operating_points": [synth_op(), synth_op(record_id="SYNTH-OP-002")]}
    assert json.dumps(red.reduce(b), sort_keys=True) == json.dumps(red.reduce(copy.deepcopy(b)), sort_keys=True)


def test_flagged_loss_gives_upper_bound(red):
    rec = synth_op()
    rec["rf"]["line_match_loss"] = {"status": "FLAGGED_NOT_MEASURED"}
    row = red.reduce_operating_points([rec])["surface"][0]
    assert row["factors"]["P_delivered_kind"] == "P_RF_DELIVERED_UPPER_BOUND_LOSS_NOT_MEASURED"
    assert row["C_e_kind"] == "C_e_UPPER_BOUND"


# ------------------------------------------------------------------ reducer: every refusal path (synthetic)
def test_refuse_missing_inputs(red):
    for key in ("labels", "rf", "generator", "collector", "terminals", "temperatures", "flows", "impedance"):
        rec = synth_op()
        del rec[key]
        with pytest.raises(red.MissingInputError):
            red.validate_operating_point(rec)
    rec = synth_op()
    del rec["temperatures"]["T_h1_pole_inner_C"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["collector"]["I_e_A"] = None
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)


def test_refuse_ar_without_label(red):
    with pytest.raises(red.LabelError):
        red.validate_operating_point(synth_op(labels=["SYNTHETIC_TEST_FIXTURE"]))
    with pytest.raises(red.LabelError):
        red.validate_operating_point(synth_op(labels=["ENGINEERING_ONLY_NON_SCORING", "SCORE_BEARING_MEASURED"]))


def test_refuse_loss_term_missing(red):
    for bad in (None, {}, {"status": "ASSUMED_ZERO"}):
        rec = synth_op()
        rec["rf"]["line_match_loss"] = bad
        with pytest.raises((red.LineMatchLossError, red.MissingInputError)):
            red.validate_operating_point(rec)
    rec = synth_op()
    rec["rf"]["line_match_loss"] = {"status": "ASSUMED_ZERO"}
    with pytest.raises(red.LineMatchLossError):
        red.derive_rf(rec)
    rec = synth_op()
    rec["rf"]["line_match_loss"] = {"status": "MEASURED", "value_W": 6.0}
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)


def test_refuse_p_mains_as_p_bus(red):
    with pytest.raises(red.PMainsNotPBusError):
        red.validate_operating_point(synth_op(P_bus_W=200.0))
    rec = synth_op()
    rec["generator"]["P_bus_W"] = 200.0
    with pytest.raises(red.PMainsNotPBusError):
        red.validate_operating_point(rec)
    with pytest.raises(red.PMainsNotPBusError):
        red.p_bus_from_generator_input(synth_op())


def test_refuse_gas_mode_violations(red):
    rec = synth_op()
    rec["flows"]["mdot_icp_dedicated_mg_s"] = 0.01
    with pytest.raises(red.GasModeError):
        red.validate_operating_point(rec)
    rec = synth_op(gas_mode="DIAGNOSTIC_DEDICATED_FEED")
    rec["flows"]["mdot_icp_dedicated_mg_s"] = 0.01
    with pytest.raises(red.LabelError):
        red.validate_operating_point(rec)
    rec["labels"].append("DIAGNOSTIC_VARIABLE_NOT_BASELINE")
    with pytest.raises(red.GasModeError):
        red.validate_operating_point(rec)
    rec["flows"]["ledger_booking_id"] = "SYNTH-BOOKING"
    red.validate_operating_point(rec)


def test_refuse_plane_gas_terminals(red):
    rec = synth_op()
    rec["rf"]["reference_plane"] = "ANTENNA_SIDE"
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(synth_op(gas="N2"))
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(synth_op(hall_discharge_state="ON"))
    rec = synth_op()
    rec["rf"]["P_refl_W"] = 150.0
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    with pytest.raises(red.P1RecordError):
        red.reduce_operating_points([synth_op(), synth_op()])


def test_icp45a_registration_rules(red):
    assert red.icp45a_condition(1.0)["status"] == "NOT_EVALUATED"
    for basis in ("STAND_CEILING", "POWER_ENVELOPE_BOUND", "SUPPLY_RATING"):
        with pytest.raises(red.RegistrationError):
            red.icp45a_condition(9.0, {"registration_id": "SYNTH-R", "I_d_max_H1_A": 8.33, "basis": basis,
                                       "source": "synthetic"}, {"rule_id": "x", "k_one_sided": 1.0,
                                                                "u_I_e_A": 0.1, "u_I_d_max_A": 0.1})
    reg = {"registration_id": "SYNTH-R", "I_d_max_H1_A": 2.0, "basis": "MEASURED_REGISTERED_H1_OPERATION",
           "source": "synthetic"}
    with pytest.raises(red.RegistrationError):
        red.icp45a_condition(3.0, reg, None)
    rule = {"rule_id": "SYNTH-RULE", "k_one_sided": 1.645, "u_I_e_A": 0.05, "u_I_d_max_A": 0.05}
    ok = red.icp45a_condition(3.0, reg, rule)
    assert ok["status"] == "EVALUATED_ENGINEERING_ONLY" and ok["condition_met"] is True
    assert ok["M_n"] == pytest.approx(0.5)
    assert red.icp45a_condition(2.0, reg, rule)["condition_met"] is False


def test_topology_control_paths(red):
    assert red.reduce_topology_control(synth_seq(red))["observation"] == "TAKAHASHI_LIKE_OBSERVATION"
    r = red.reduce_topology_control(synth_seq(red, icp_off=True))
    assert r["observation"] == "UNEXPECTED_SUSTAINED_DISCHARGE_ICP_OFF" and "CURRENT_PATH_DIAGNOSIS" in r["branch"]
    assert "PASS" not in json.dumps(r).replace("PASS/FAIL", "")
    s = synth_seq(red)
    s["steps"] = s["steps"][::-1]
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    s["steps"][3]["text"] = "Apply a Hall start attempt."
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    s["hall_start_registration_id"] = ""
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    s["c1_disconnected"] = False
    with pytest.raises(red.SequenceError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    s["classification"] = "PASS_FAIL_GATE"
    with pytest.raises(red.LabelError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    del s["steps"][2]["signals"]["P_rf_refl_W"]
    with pytest.raises(red.MissingInputError):
        red.reduce_topology_control(s)
    s = synth_seq(red)
    s["labels"] = []
    with pytest.raises(red.LabelError):
        red.reduce_topology_control(s)


def test_stable_region_and_facility_check(red):
    dwell = {"t_s": [0.0, 10.0, 20.0, 30.0], "I_e_A": [0.50, 0.51, 0.50, 0.51], "P_refl_W": [4.0, 4.1, 4.0, 4.1]}
    m = red.dwell_metrics(dwell)
    assert red.classify_stable_region(m)["verdict"] == "NOT_EVALUATED"
    crit = {"criteria_id": "SYNTH-CRIT", "max_abs_drift_rel_I_e": 0.1, "max_abs_drift_rel_P_refl": 0.1,
            "max_step_over_std": 10.0, "min_duration_s": 10.0, "min_ignition_success_fraction": 0.5}
    with pytest.raises(red.MissingInputError):
        red.classify_stable_region(m, crit, None)
    v = red.classify_stable_region(m, crit, {"attempts": 3, "successes": 3})
    assert v["verdict"] == "WITHIN_OWNER_CRITERIA"
    with pytest.raises(red.MissingInputError):
        red.dwell_metrics({"t_s": [0.0, 1.0], "I_e_A": [1, 1], "P_refl_W": [1, 1]})
    on = synth_op()
    off = synth_op(record_id="SYNTH-OP-OFF")
    off["rf"]["P_fwd_W"] = 0.0
    off["rf"]["P_refl_W"] = 0.0
    off["collector"]["I_e_A"] = 0.01
    fc = red.facility_electron_check(on, off)
    assert fc["facility_fraction"] == pytest.approx(0.02)
    out = red.reduce({"operating_points": [on, off], "facility_pairs": [["SYNTH-OP-001", "SYNTH-OP-OFF"]],
                      "dwells": [{"record_id": "SYNTH-OP-001", "dwell": dwell}],
                      "topology_control": [synth_seq(red)]})
    assert out["dwells"][0]["stable_region"]["verdict"] == "NOT_EVALUATED"
    off_row = [r for r in out["operating_points"]["surface"] if r["record_id"] == "SYNTH-OP-OFF"][0]
    assert off_row["gamma_abs"] is None
