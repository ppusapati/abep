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
SIGN = "POSITIVE_ELECTRONS_EXTRACTED_FROM_ICP_EQUALS_COLLECTOR_SUPPLY_TERMINAL_INTO_NETWORK"


def synth_op(**over):
    rec = {
        "schema": "p1_bench_record_v1", "record_kind": "icp_operating_point", "record_id": "SYNTH-OP-001",
        "run_id": "SYNTH-RUN-1", "stage_id": "P1-S4", "timestamp_utc": "2000-01-01T00:00:00Z", "synthetic": True,
        "labels": ["ENGINEERING_ONLY_NON_SCORING", "SYNTHETIC_TEST_FIXTURE"], "gas": "Ar", "gas_mode": "G-REUSE",
        "hall_discharge_state": "OFF", "hall_discharge_sustained": False,
        "h1_electrical": {"config_id": "SYNTH-H1E-OFF", "anode_state": "DISCONNECTED_FLOATING", "V_anode_V": 3.0,
                          "h1_body_state": "SYNTH-BODY-GROUNDED"},
        "rf": {"reference_plane": "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH", "P_fwd_W": 100.0, "P_refl_W": 4.0,
               "match_setting_id": "SYNTH-MATCH-A",
               "line_match_loss": {"status": "MEASURED", "value_W": 6.0, "source": "SYNTH-S1-CHAR",
                                   "match_setting_id": "SYNTH-MATCH-A", "valid_max_gamma_abs": 0.3}},
        "generator": {"generator_class": "GROUND_FACILITY_ONLY_MAINS", "P_generator_input_W": 200.0,
                      "input_boundary": "mains AC input of the lab generator", "instrument": "SYNTH-PA"},
        "collector": {"I_e_A": 0.5, "I_e_sign_convention": SIGN, "I_e_resolution_A": 0.001,
                      "V_collector_V": -40.0, "reference_potential": "FACILITY_GROUND"},
        "extraction": {"topology_id": "SYNTH-TOPO-B", "electron_collecting_electrode": "CHAMBER_WALL_FACILITY_GROUND"},
        "pressures": {"p_chamber_Pa": 0.01},
        "flows": {"mdot_Ar_H1_mg_s": 1.0, "mdot_icp_dedicated_mg_s": 0.0},
        "impedance": {"status": "NOT_MEASURED_PENDING_P2_CHAIN"},
        "terminals": {"collector_supply": {"I_A": 0.5, "basis": "MEASURED"},
                      "icp_body": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"},
                      "facility_ground": {"I_A": -0.49, "basis": "MEASURED"},
                      "hall_anode": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"}},
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
    assert op["properties"]["generator"]["properties"]["generator_class"]["enum"] == ["GROUND_FACILITY_ONLY_MAINS"]
    assert op["properties"]["extraction"]["required"] == list(red.EXTRACTION_REQUIRED)
    assert op["properties"]["rf"]["required"] == list(red.RF_REQUIRED)
    seq = sc["$defs"]["topology_control_sequence"]
    assert seq["required"] == list(red.SEQUENCE_REQUIRED)
    assert [s["text"] for s in seq["x-step-texts-verbatim"]] == [t for _, t in red.SEQUENCE_STEPS]
    assert "x-step-texts-verbatim" not in seq["properties"]
    assert op["properties"]["collector"]["properties"]["I_e_sign_convention"]["const"] == red.I_E_SIGN_CONVENTION
    assert op["properties"]["h1_electrical"]["required"] == list(red.H1_ELECTRICAL_REQUIRED)


_SUBSCHEMA_MAPS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
_SUBSCHEMA_ONE = ("additionalProperties", "items", "contains", "not", "if", "then", "else", "propertyNames",
                  "unevaluatedItems", "unevaluatedProperties", "additionalItems")
_SUBSCHEMA_LISTS = ("allOf", "anyOf", "oneOf", "prefixItems")


def _structural_metaschema_errors(node, path="#"):
    """Stdlib check of the Draft 2020-12 rule that every subschema is an object or a boolean."""
    errs = []
    if isinstance(node, bool):
        return errs
    if not isinstance(node, dict):
        return [path + ": subschema is %s, must be object or boolean" % type(node).__name__]
    for k in _SUBSCHEMA_MAPS:
        if k in node:
            if not isinstance(node[k], dict):
                errs.append(path + "/" + k + ": must be an object")
                continue
            for name, sub in node[k].items():
                errs += _structural_metaschema_errors(sub, path + "/" + k + "/" + name)
    for k in _SUBSCHEMA_ONE:
        if k in node:
            errs += _structural_metaschema_errors(node[k], path + "/" + k)
    for k in _SUBSCHEMA_LISTS:
        if k in node:
            if not isinstance(node[k], list) or not node[k]:
                errs.append(path + "/" + k + ": must be a non-empty array")
                continue
            for i, sub in enumerate(node[k]):
                errs += _structural_metaschema_errors(sub, "%s/%s/%d" % (path, k, i))
    if "required" in node and not (isinstance(node["required"], list)
                                   and all(isinstance(x, str) for x in node["required"])):
        errs.append(path + "/required: must be an array of strings")
    if "enum" in node and not isinstance(node["enum"], list):
        errs.append(path + "/enum: must be an array")
    return errs


def test_schema_is_valid_json_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    assert sc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert _structural_metaschema_errors(sc) == []
    # the check itself catches the reviewer's defect (an array placed under 'properties')
    bad = {"type": "object", "properties": {"x-step-texts-verbatim": [{"step": 1}]}}
    assert _structural_metaschema_errors(bad)
    try:
        import jsonschema  # optional: full metaschema validation when the library is installed
    except ImportError:
        return
    jsonschema.Draft202012Validator.check_schema(sc)


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
    rec = synth_s7(red, "SYNTH-S7-NOANODE", 0.5)
    del rec["terminals"]["hall_anode"]
    with pytest.raises(red.MissingInputError):          # Hall ON needs the hall_anode terminal
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["rf"]["P_refl_W"] = 150.0
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    with pytest.raises(red.P1RecordError):
        red.reduce_operating_points([synth_op(), synth_op()])


REG = {"registration_id": "SYNTH-R", "I_d_max_H1_A": 2.0, "basis": "MEASURED_REGISTERED_H1_OPERATION",
       "source": "synthetic", "registered_point_ids": ["SYNTH-H1-PT-1"]}
RULE = {"rule_id": "SYNTH-RULE", "k_one_sided": 1.645, "u_I_e_A": 0.05, "u_I_d_max_A": 0.05}
MATCH = {"criteria_id": "SYNTH-MATCH-RULE", "p_chamber_rel_tol": 0.05}


def synth_s7(red, rid, i_e, rf_on=True, **over):
    """Synthetic P1-S7 Hall-ON record (electrons sunk by the H-1 anode)."""
    rec = synth_op(record_id=rid, stage_id="P1-S7", hall_discharge_state="ON", h1_point_id="SYNTH-H1-PT-1",
                   extraction={"topology_id": "SYNTH-TOPO-S7", "electron_collecting_electrode": "H1_ANODE"})
    rec["hall_discharge_sustained"] = True
    rec["h1_electrical"] = {"config_id": "SYNTH-H1E-ON", "anode_state": "CONNECTED_TO_DISCHARGE_SUPPLY",
                            "V_anode_V": 150.0, "h1_body_state": "SYNTH-BODY-GROUNDED"}
    rec["collector"]["I_e_A"] = i_e
    rec["terminals"] = {"collector_supply": {"I_A": i_e, "basis": "MEASURED"},
                        "icp_body": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"},
                        "facility_ground": {"I_A": 0.0, "basis": "MEASURED"},
                        "hall_anode": {"I_A": -i_e, "basis": "MEASURED"}}
    if not rf_on:
        rec["rf"]["P_fwd_W"] = 0.0
        rec["rf"]["P_refl_W"] = 0.0
        rec["hall_discharge_sustained"] = False
    rec.update(over)
    return rec


def synth_cap(rid, i_e, rf_on=True, synthetic=True, stage="P1-S7", **over):
    """Synthetic CAPACITY record: registered extraction topology (dedicated target), discharge supply OFF, at the
    gas/magnet conditions of a registered H-1 point."""
    rec = synth_op(record_id=rid, stage_id=stage, h1_point_id="SYNTH-H1-PT-1", synthetic=synthetic,
                   extraction={"topology_id": "SYNTH-TOPO-A",
                               "electron_collecting_electrode": "DEDICATED_ELECTRON_COLLECTOR_TARGET"})
    rec["collector"]["I_e_A"] = i_e
    rec["terminals"] = {"collector_supply": {"I_A": i_e, "basis": "MEASURED"},
                        "icp_body": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"},
                        "facility_ground": {"I_A": 0.0, "basis": "MEASURED"},
                        "electron_collector": {"I_A": -i_e, "basis": "MEASURED"},
                        "hall_anode": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"}}
    if not rf_on:
        rec["rf"]["P_fwd_W"] = 0.0
        rec["rf"]["P_refl_W"] = 0.0
    rec.update(over)
    return rec


def test_icp45a_registration_rules(red):
    rec = synth_op()
    assert red.icp45a_evaluate([rec])["status"] == "NOT_EVALUATED"
    for basis in ("STAND_CEILING", "POWER_ENVELOPE_BOUND", "SUPPLY_RATING"):
        with pytest.raises(red.RegistrationError):
            red.icp45a_evaluate([rec], dict(REG, basis=basis, I_d_max_H1_A=8.33), RULE)
    with pytest.raises(red.RegistrationError):
        red.icp45a_evaluate([rec], REG, None)
    with pytest.raises(red.MissingInputError):
        red.icp45a_evaluate([rec], {k: v for k, v in REG.items() if k != "registered_point_ids"}, RULE)
    with pytest.raises(red.RegistrationError):
        red.icp45a_evaluate([rec], dict(REG, registered_point_ids=[]), RULE)
    m = red.icp45a_margin(3.0, 2.0, 1.645, 0.05, 0.05)
    assert m["M_n"] == pytest.approx(0.5)
    assert m["M_n_lower"] == pytest.approx(0.5 - 1.645 * math.sqrt((0.05 / 2) ** 2 + (3.0 * 0.05 / 4) ** 2))


def test_icp45a_never_credits_rf_off_or_diagnostic_feed(red):
    """Reviewer repro: an RF-OFF 50 A record or a dedicated-feed 9 A record must never become I_e,cap."""
    rf_off = synth_op(record_id="SYNTH-RFOFF-50A")
    rf_off["rf"]["P_fwd_W"] = 0.0
    rf_off["rf"]["P_refl_W"] = 0.0
    rf_off["collector"]["I_e_A"] = 50.0
    rf_off["terminals"]["collector_supply"]["I_A"] = 50.0
    rf_off["terminals"]["facility_ground"]["I_A"] = -50.0
    diag = synth_s7(red, "SYNTH-DIAG-9A", 9.0, gas_mode="DIAGNOSTIC_DEDICATED_FEED")
    diag["labels"].append("DIAGNOSTIC_VARIABLE_NOT_BASELINE")
    diag["flows"]["mdot_icp_dedicated_mg_s"] = 0.1
    diag["flows"]["ledger_booking_id"] = "SYNTH-BOOKING"
    out = red.reduce_operating_points([rf_off, diag], dict(REG, I_d_max_H1_A=5.0), RULE)
    ic = out["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
    reasons = {e["record_id"]: " ".join(e["reasons"]) for e in ic["excluded_records"]}
    assert "RF OFF" in reasons["SYNTH-RFOFF-50A"] and "not a registered H-1 point" in reasons["SYNTH-RFOFF-50A"]
    assert "DIAGNOSTIC_DEDICATED_FEED" in reasons["SYNTH-DIAG-9A"]
    assert out["summary"]["I_e_max_recorded_A"] == 50.0 and "NOT I_e,cap" in out["summary"]["I_e_max_recorded_note"]
    # Hall OFF / wrong stage / unregistered point / pickup not done are excluded too
    for bad in (synth_cap("SYNTH-X1", 3.0, h1_point_id="SYNTH-UNREGISTERED"),
                synth_cap("SYNTH-X2", 3.0, stage="P1-S5"),
                synth_cap("SYNTH-X3", 3.0, rf_pickup_check="NOT_DONE"),
                synth_s7(red, "SYNTH-X4", 3.0)):
        r = red.icp45a_evaluate([bad], REG, RULE, {})
        assert r["status"] == "NOT_EVALUATED"


def test_icp45a_needs_facility_correction_and_synthetic_is_not_evidence(red):
    on = synth_cap("SYNTH-CAP-ON", 3.0)
    off = synth_cap("SYNTH-CAP-OFF", 0.4, rf_on=False)
    r = red.reduce_operating_points([on, off], REG, RULE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED"
    assert any("facility-electron correction missing" in " ".join(e["reasons"]) for e in ic["excluded_records"])
    with pytest.raises(red.MissingInputError):
        red.reduce_operating_points([on, off], REG, RULE, [["SYNTH-CAP-ON", "SYNTH-CAP-OFF"]])
    r = red.reduce_operating_points([on, off], REG, RULE, [["SYNTH-CAP-ON", "SYNTH-CAP-OFF"]], MATCH)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE" and ic["condition_met"] is None
    assert ic["I_e_cap_A"] == pytest.approx(3.0 - 0.4) and ic["I_e_cap_record"] == "SYNTH-CAP-ON"
    assert ic["M_n"] == pytest.approx(2.6 / 2.0 - 1.0)
    assert "PROPOSED" in ic["i_e_cap_definition"]


def test_icp45a_hall_on_record_never_falsely_rejects(red):
    """Reviewer repro (fixture labelled synthetic in its ids but synthetic=False to exercise the evidence path):
    an ICP fully sustaining H-1 at I_d = I_d,max = 3.0 A must NOT yield condition_met False - Hall-ON records are
    consistency records only, so without a capacity record the status is NOT_EVALUATED."""
    reg = dict(REG, I_d_max_H1_A=3.0)
    rule = dict(RULE, u_I_e_A=0.03, u_I_d_max_A=0.03)
    on = synth_s7(red, "SYNTH-S7-ON", 3.0, synthetic=False)
    off = synth_s7(red, "SYNTH-S7-OFF", 0.0, rf_on=False, synthetic=False)
    r = red.reduce_operating_points([on, off], reg, rule, [["SYNTH-S7-ON", "SYNTH-S7-OFF"]], MATCH)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None and "never a FAIL" in ic["reason"]
    nc = [c for c in ic["neutralization_consistency"] if c["record_id"] == "SYNTH-S7-ON"][0]
    assert nc["status"] == "DESCRIPTIVE_CONSISTENCY_CHECK_NOT_A_GATE"
    assert nc["ratio_I_e_icp_to_I_d"] == pytest.approx(1.0) and nc["I_e_icp_basis"] == "FACILITY_CORRECTED"
    # a Hall-OFF capacity record in the registered extraction topology (P1-S4) IS eligible
    cap_on = synth_cap("SYNTH-S4-CAP-ON", 5.0, synthetic=False, stage="P1-S4")
    cap_off = synth_cap("SYNTH-S4-CAP-OFF", 0.0, rf_on=False, synthetic=False, stage="P1-S4")
    r = red.reduce_operating_points([on, off, cap_on, cap_off], reg, rule,
                                    [["SYNTH-S7-ON", "SYNTH-S7-OFF"], ["SYNTH-S4-CAP-ON", "SYNTH-S4-CAP-OFF"]], MATCH)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY" and ic["condition_met"] is True
    assert ic["I_e_cap_record"] == "SYNTH-S4-CAP-ON" and ic["I_e_cap_A"] == pytest.approx(5.0)
    assert "PASS" not in ic["status"]


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
    off["terminals"]["collector_supply"]["I_A"] = 0.01
    off["terminals"]["facility_ground"]["I_A"] = -0.01
    with pytest.raises(red.MissingInputError):
        red.facility_electron_check(on, off)
    fc = red.facility_electron_check(on, off, MATCH)
    assert fc["facility_fraction"] == pytest.approx(0.02)
    assert fc["I_e_icp_corrected_A"] == pytest.approx(0.49)
    out = red.reduce({"operating_points": [on, off], "facility_pairs": [["SYNTH-OP-001", "SYNTH-OP-OFF"]],
                      "dwells": [{"record_id": "SYNTH-OP-001", "dwell": dwell}],
                      "topology_control": [synth_seq(red)]}, facility_match=MATCH)
    assert out["dwells"][0]["stable_region"]["verdict"] == "NOT_EVALUATED"
    off_row = [r for r in out["operating_points"]["surface"] if r["record_id"] == "SYNTH-OP-OFF"][0]
    assert off_row["gamma_abs"] is None
    assert off_row["C_e_W_per_A"] is None and off_row["factors"]["P_delivered_W"] is None
    assert off_row["rf_state"] == "RF_OFF" and "RF OFF" in off_row["C_e_reason"]


def test_facility_pair_must_match_point(red):
    on = synth_op()
    base_off = synth_op(record_id="SYNTH-OP-OFF")
    base_off["rf"]["P_fwd_W"] = 0.0
    base_off["rf"]["P_refl_W"] = 0.0
    off = copy.deepcopy(base_off)
    off["pressures"]["p_chamber_Pa"] = 1.0              # 0.01 Pa vs 1.0 Pa
    with pytest.raises(red.P1RecordError):
        red.facility_electron_check(on, off, MATCH)
    off = copy.deepcopy(base_off)
    off["pressures"]["p_chamber_Pa"] = 0.0102            # within the synthetic 5 % tolerance
    red.facility_electron_check(on, off, MATCH)
    off = copy.deepcopy(base_off)
    off["extraction"]["topology_id"] = "SYNTH-TOPO-OTHER"
    with pytest.raises(red.P1RecordError):
        red.facility_electron_check(on, off, MATCH)
    off = copy.deepcopy(base_off)
    off["gas_mode"] = "DIAGNOSTIC_DEDICATED_FEED"
    off["labels"].append("DIAGNOSTIC_VARIABLE_NOT_BASELINE")
    off["flows"]["ledger_booking_id"] = "SYNTH-BOOKING"
    with pytest.raises(red.P1RecordError):
        red.facility_electron_check(on, off, MATCH)
    with pytest.raises(red.P1RecordError):                 # RF-ON record must have P_fwd > 0
        red.facility_electron_check(base_off, copy.deepcopy(base_off), MATCH)


def test_refuse_impossible_rf(red):
    rec = synth_op()
    rec["rf"]["line_match_loss"]["value_W"] = 1e6
    with pytest.raises(red.RFConsistencyError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["rf"]["P_fwd_W"] = 200.0
    rec["rf"]["P_refl_W"] = 8.0
    rec["rf"]["line_match_loss"]["value_W"] = 500.0
    with pytest.raises(red.RFConsistencyError):
        red.reduce_operating_points([rec])
    rec = synth_op()
    rec["rf"]["P_fwd_W"] = 0.0
    rec["rf"]["P_refl_W"] = 5.0
    with pytest.raises(red.RFConsistencyError):
        red.validate_operating_point(rec)


def test_refuse_flight_generator_and_flag_pickup(red):
    rec = synth_op()
    rec["generator"]["generator_class"] = "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE"
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    row = red.reduce_operating_points([synth_op(rf_pickup_check="NOT_DONE")])["surface"][0]
    assert any(f.startswith("RF_PICKUP_CHECK_NOT_DONE") for f in row["flags"])


def test_refuse_p_bus_spellings(red):
    for key in ("P_bus_mains_W", "Pbus_W", "p-BUS", "P_BUS_equivalent"):
        rec = synth_op()
        rec["generator"][key] = 1.0
        with pytest.raises(red.PMainsNotPBusError):
            red.validate_operating_point(rec)
        with pytest.raises(red.PMainsNotPBusError):
            red.validate_operating_point(synth_op(**{key: 1.0}))
    rec = synth_op()
    rec["temperatures"]["P_bus_W"] = 1.0
    with pytest.raises(red.PMainsNotPBusError):
        red.validate_operating_point(rec)


def test_extraction_topology_rules(red):
    rec = synth_op()
    del rec["extraction"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    rec = synth_op(extraction={"topology_id": "SYNTH-T", "electron_collecting_electrode": "H1_ANODE"})
    with pytest.raises(red.ExtractionTopologyError):              # H-1 anode as sink with Hall OFF
        red.validate_operating_point(rec)
    rec = synth_s7(red, "SYNTH-S7", 1.0,
                   extraction={"topology_id": "SYNTH-T", "electron_collecting_electrode": "CHAMBER_WALL_FACILITY_GROUND"})
    with pytest.raises(red.ExtractionTopologyError):
        red.validate_operating_point(rec)
    rec = synth_op(extraction={"topology_id": "", "electron_collecting_electrode": "CHAMBER_WALL_FACILITY_GROUND"})
    with pytest.raises(red.ExtractionTopologyError):
        red.validate_operating_point(rec)
    rec = synth_op(extraction={"topology_id": "SYNTH-T",
                               "electron_collecting_electrode": "DEDICATED_ELECTRON_COLLECTOR_TARGET"})
    with pytest.raises(red.MissingInputError):                    # electron_collector terminal required
        red.validate_operating_point(rec)
    rec["terminals"]["electron_collector"] = {"I_A": -0.49, "basis": "MEASURED"}
    rec["terminals"]["facility_ground"]["I_A"] = 0.0
    red.validate_operating_point(rec)
    rec = synth_op()
    rec["collector"]["reference_potential"] = "somewhere"
    with pytest.raises(red.ExtractionTopologyError):
        red.validate_operating_point(rec)


def test_plan_defines_extraction_topology_and_readiness(doc):
    items = {i["id"]: i for i in doc["items"]}
    assert "P1-G0" == items["P1-IT-36"]["p1_gate"] and "TBD" in items["P1-IT-36"]["value"]
    assert "PROPOSED" in items["P1-IT-38"]["status"]
    s0 = [s for s in doc["stage_map"] if s["id"] == "P1-S0"][0]
    assert any("extraction topology" in x for x in s0["exit"])
    hw = " ".join(h["item"] + " " + h["rfq_v1_package"] + " " + h["h2_or_h1_items"] for h in doc["hardware_readiness"])
    for needle in ("H-1 Hall thruster", "anode plenum", "C1 (hall_c1_reference)", "electron-collecting",
                   "RFQ-06 part (b)", "RFQ-08", "H2-2 C-1"):
        assert needle in hw, needle
    for mrow in doc["measurements"]:
        assert mrow["metrology_spec"], mrow["id"]
    ids = {a["id"]: a["how_applied"] for a in doc["owner_answers_applied"]}
    assert ids["A9.1 ICP-46"].startswith("NOT APPLICABLE") and ids["A9.1 OQ-A902-01"].startswith("NOT APPLICABLE")
    assert not any("ICP-33, ICP-34), so" in p for p in doc["scope"]["orificed_variant_provisions"])


# ------------------------------------------------------------------ repair round 2: new refusal / flag paths
def test_refuse_pattern_score_labels(red):
    for lab in ("SCORE_BEARING", "score-bearing", "SCORED_POINT", "HELD_OUT", "PASSED"):
        with pytest.raises(red.LabelError):
            red.validate_operating_point(synth_op(labels=["ENGINEERING_ONLY_NON_SCORING", lab]))
    red.validate_operating_point(synth_op(labels=["ENGINEERING_ONLY_NON_SCORING", "DIAGNOSTIC_VARIABLE_NOT_BASELINE"]))


def test_refuse_bus_keys_and_bus_input_boundary(red):
    rec = synth_op()
    rec["notes"] = {"bus_power_W": 1.0}
    with pytest.raises(red.PMainsNotPBusError):
        red.validate_operating_point(rec)
    for text in ("P_bus", "spacecraft DC bus input", "Pbus"):
        rec = synth_op()
        rec["generator"]["input_boundary"] = text
        with pytest.raises(red.PMainsNotPBusError):
            red.validate_operating_point(rec)


def test_sign_convention_and_collector_cross_check(red):
    rec = synth_op()
    rec["collector"]["I_e_sign_convention"] = "ION_CURRENT_POSITIVE"
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    rec = synth_op()
    del rec["collector"]["I_e_resolution_A"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["collector"]["I_e_A"] = 3.0                  # collector_supply terminal still 0.5 A
    with pytest.raises(red.P1RecordError, match="differ"):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["collector"]["I_e_A"] = -0.05
    rec["terminals"]["collector_supply"]["I_A"] = -0.05
    rec["terminals"]["facility_ground"]["I_A"] = 0.05
    row = red.reduce_operating_points([rec])["surface"][0]
    assert any(f.startswith("I_E_NEGATIVE") for f in row["flags"]) and row["C_e_W_per_A"] is None


def test_loss_tied_to_match_setting_and_gamma_validity(red):
    rec = synth_op()
    rec["rf"]["line_match_loss"]["match_setting_id"] = "SYNTH-MATCH-B"
    with pytest.raises(red.LineMatchLossError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["rf"]["line_match_loss"]["valid_max_gamma_abs"] = 0.1    # record |Gamma| = 0.2
    with pytest.raises(red.LineMatchLossError):
        red.validate_operating_point(rec)
    rec = synth_op()
    del rec["rf"]["line_match_loss"]["valid_max_gamma_abs"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)


def test_h1_electrical_configuration_rules(red):
    rec = synth_op()
    del rec["h1_electrical"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["h1_electrical"]["anode_state"] = "CONNECTED_TO_DISCHARGE_SUPPLY"     # OFF supply left connected
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    rec = synth_op()
    del rec["terminals"]["hall_anode"]                                       # Hall-OFF closure needs the anode
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    rec = synth_op()
    rec["h1_electrical"]["anode_state"] = "METERED_RETURN"                   # metered return needs MEASURED basis
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    rec["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "MEASURED"}
    red.validate_operating_point(rec)
    rec = synth_op(hall_discharge_sustained=True)                             # supply OFF cannot sustain
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(rec)
    rec = synth_op()
    del rec["hall_discharge_sustained"]
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(rec)
    row = red.reduce_operating_points([synth_op()])["surface"][0]
    assert row["h1_electrical"]["anode_state"] == "DISCONNECTED_FLOATING"


def test_plan_repairs_round2(doc):
    items = {i["id"]: i for i in doc["items"]}
    for k in ("P1-IT-39", "P1-IT-40", "P1-IT-41", "P1-IT-42"):
        assert k in items
    assert "CAPACITY" in items["P1-IT-38"]["value"] and "neutralization-consistency" in items["P1-IT-38"]["value"]
    assert "PROPOSED EXTENSION" in items["P1-IT-21"]["status"]
    meas = {m["id"]: m for m in doc["measurements"]}
    assert not any("UB-P-06" in u or "A9H-CAL-03" in u for u in meas["P1-M-05"]["uncertainty_sources"])
    assert meas["P1-M-15"]["stages"] == "S3-S7"
    assert "match_setting_id" in meas["P1-M-03"]["note"]
    si = {x["id"]: x for x in doc["safety_interlocks"]}
    assert "PROPOSED EXTENSION" in si["P1-SI-05"]["threshold"]
    s0 = [s for s in doc["stage_map"] if s["id"] == "P1-S0"][0]
    assert any("insulation-resistance / hipot" in x for x in s0["exit"])
    assert any("P1-IT-39" in x for x in s0["exit"])
    s7 = [s for s in doc["stage_map"] if s["id"] == "P1-S7"][0]
    assert any("P1-IT-31" in x for x in s7["entry"])
    qs = {q["id"] for q in doc["open_owner_questions"]}
    assert {"P1Q-13", "P1Q-14"} <= qs
