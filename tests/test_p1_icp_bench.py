"""Tests for the P1 ICP electron-source bench package (fo_a9_p1_icp_bench, owner A9.3; A9.4 incorporated by
fo_a9_4_incorporation; owner A9.5 P1Q-15 Kirchhoff closure rule / P1Q-16 capacity formula by fo_a9_5_closure_rule).

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
A94 = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_4_p1_p2_owner_decisions.json")
A94_MD = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md")
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
        "record_class": "ENGINEERING_SURFACE",
        "hall_discharge_state": "OFF", "hall_discharge_sustained": False,
        "h1_electrical": {"config_id": "SYNTH-H1E-OFF", "anode_state": "DISCONNECTED_FLOATING", "V_anode_V": 3.0,
                          "h1_body_state": "SYNTH-BODY-GROUNDED",
                          "discharge_supply_connection": "PHYSICALLY_DISCONNECTED"},
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


def test_merged_cross_references_replace_stale_pending(doc, bld):
    """A9.5 execution (carried A9.4 minor): no stale 'PENDING <path>' for the merged RFQ v2 / P2 lanes; every readiness
    row names RFQ v2 line ids or says explicitly that no line exists; cited ids exist in the merged files."""
    txt = json.dumps(doc) + open(MD_PATH, encoding="utf-8").read()
    assert "PENDING docs/experiments/hall_icp/p2_impedance_map/" not in txt
    assert "PENDING docs/procurement/rfq_a9_v2/" not in txt
    assert "pending_parallel_lanes" not in doc
    with open(os.path.join(ROOT, "docs", "procurement", "rfq_a9_v2", "rfq_a9_v2.json"), encoding="utf-8") as f:
        rfq2 = f.read()
    for h in doc["hardware_readiness"]:
        v = h["rfq_v2_package"]
        assert "PENDING" not in v and "docs/procurement/rfq_a9_v2/rfq_a9_v2.json" in v, h["id"]
        ids = re.findall(r"\b(?:RF|GAS|VAC|HE|ME|TH)-[LO]\d\d\b", v)
        assert ids or v.startswith("no RFQ v2 line"), h["id"]
        for i in ids:
            assert '"%s"' % i in rfq2, (h["id"], i)
    hw = {h["item"].split(" (")[0]: h["rfq_v2_package"] for h in doc["hardware_readiness"]}
    photo = [v for k, v in hw.items() if k.startswith("optical-emission photodiode")][0]
    assert "TH-L07" in photo and "TH-L08" in photo and "VAC-L07" in photo
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    assert pins["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"] == \
        "2d9fa0978f991674152371f4013cac64f05cddd1ac00523cfa7397b572119174"
    assert not any("p2_impedance_map" in p for p in pins)          # same follow-on lane: ids checked, not pinned
    refs = {r["path"]: r for r in doc["merged_cross_references"]}
    assert refs["docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"]["state"] == "MERGED"
    assert "IDP2-01" in refs["docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"]["ids_cited"]
    assert "TH-L07" in refs["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"]["ids_cited"]
    ifd = {d["id"]: d for d in doc["interface_demands"]}
    assert "IDP2-01" in ifd["IF-P1-01"]["counterpart"] and "IDP2-17" in ifd["IF-P1-23"]["counterpart"]


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
KSC = "CONVENTIONAL_CURRENT_INTO_THE_DEFINED_ISOLATED_ELECTRICAL_NETWORK_IS_POSITIVE"
CLOSE = {"rule_id": "SYNTH-CLOSURE", "sign_convention": KSC, "sign_convention_id": "SYNTH-SIGN",
         "I_scale_min_A": 0.01, "I_scale_min_basis": "SYNTH instrument-capability floor (fixture, not data)"}
# synthetic per-channel u(I_k) components (fixture numbers, never data): u = sqrt(1e-3^2 + 5e-4^2 + 1e-4^2) A
U_CH = {"u_calibration_A": 1e-3, "u_zero_offset_A": 5e-4, "u_resolution_A": 1e-4, "u_repeatability_A": "NOT_APPLICABLE",
        "u_rf_pickup_A": "NONE_REGISTERED"}
U1 = math.sqrt(1e-3 ** 2 + 5e-4 ** 2 + 1e-4 ** 2)


def _meas(i_a, sign="SYNTH-SIGN"):
    return {"I_A": i_a, "basis": "MEASURED", "sign_convention_id": sign, "uncertainty": dict(U_CH)}
RULE = {"rule_id": "SYNTH-RULE", "k_one_sided": 1.645, "u_I_e_A": 0.05, "u_I_d_max_A": 0.05}
MATCH = {"criteria_id": "SYNTH-MATCH-RULE", "p_chamber_rel_tol": 0.05}


def synth_s7(red, rid, i_e, rf_on=True, **over):
    """Synthetic P1-S7H Hall-ON follow-up record (electrons sunk by the H-1 anode; NEUTRALIZATION_CONSISTENCY)."""
    rec = synth_op(record_id=rid, stage_id="P1-S7H", hall_discharge_state="ON", h1_point_id="SYNTH-H1-PT-1",
                   record_class="NEUTRALIZATION_CONSISTENCY",
                   extraction={"topology_id": "SYNTH-TOPO-S7", "electron_collecting_electrode": "H1_ANODE"})
    rec["hall_discharge_sustained"] = True
    rec["h1_electrical"] = {"config_id": "SYNTH-H1E-ON", "anode_state": "CONNECTED_TO_DISCHARGE_SUPPLY",
                            "V_anode_V": 150.0, "h1_body_state": "SYNTH-BODY-GROUNDED",
                            "discharge_supply_connection": "CONNECTED"}
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
    """Synthetic ICP45_CAPACITY record (A9.4 P1Q-10 / P1Q-13): dedicated collector, discharge supply OFF and
    physically disconnected, anode floating, single-point metered H-1 body return, registered H-1 point."""
    rec = synth_op(record_id=rid, stage_id=stage, h1_point_id="SYNTH-H1-PT-1", synthetic=synthetic,
                   record_class="ICP45_CAPACITY",
                   extraction={"topology_id": "SYNTH-TOPO-A",
                               "electron_collecting_electrode": "DEDICATED_ELECTRON_COLLECTOR_TARGET"})
    rec["capacity_monitoring"] = {"h1_body_ground_config": "SINGLE_POINT_METERED_FACILITY_GROUND",
                                  "I_body_to_ground_continuous": True, "V_anode_channel": "HIGH_IMPEDANCE_ISOLATED",
                                  "V_icp_body_V": -5.0, "V_electron_collector_V": 20.0,
                                  "sign_convention_id": "SYNTH-SIGN", "unintended_ground_path_found": False,
                                  "ground_path_check_id": "SYNTH-GND-CHECK"}
    rec["collector"]["I_e_A"] = i_e
    rec["terminals"] = {"collector_supply": _meas(i_e),
                        "icp_body": {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"},
                        "facility_ground": _meas(0.0),
                        "electron_collector": _meas(-i_e),
                        "h1_body": _meas(0.0),
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
        r = red.icp45a_evaluate([bad], REG, RULE, {}, CLOSE)
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
    r = red.reduce_operating_points([on, off], REG, RULE, [["SYNTH-CAP-ON", "SYNTH-CAP-OFF"]], MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE" and ic["condition_met"] is None
    assert ic["I_e_cap_A"] == pytest.approx(3.0 - 0.4) and ic["I_e_cap_record"] == "SYNTH-CAP-ON"
    assert ic["M_n"] == pytest.approx(2.6 / 2.0 - 1.0)
    assert ic["i_e_cap_definition"].startswith("OWNER_DECIDED (A9.4 P1Q-10")
    assert "PROPOSED" not in ic["i_e_cap_definition"]
    assert all(c["label"] == "ICP45_CAPACITY" for c in ic["candidates"])


def test_icp45a_hall_on_record_never_falsely_rejects(red):
    """Reviewer repro (fixture labelled synthetic in its ids but synthetic=False to exercise the evidence path):
    an ICP fully sustaining H-1 at I_d = I_d,max = 3.0 A must NOT yield condition_met False - Hall-ON records are
    consistency records only, so without a capacity record the status is NOT_EVALUATED."""
    reg = dict(REG, I_d_max_H1_A=3.0)
    rule = dict(RULE, u_I_e_A=0.03, u_I_d_max_A=0.03)
    on = synth_s7(red, "SYNTH-S7-ON", 3.0, synthetic=False)
    off = synth_s7(red, "SYNTH-S7-OFF", 0.0, rf_on=False, synthetic=False)
    r = red.reduce_operating_points([on, off], reg, rule, [["SYNTH-S7-ON", "SYNTH-S7-OFF"]], MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None and "never a FAIL" in ic["reason"]
    nc = [c for c in ic["neutralization_consistency"] if c["record_id"] == "SYNTH-S7-ON"][0]
    assert nc["status"] == "DESCRIPTIVE_CONSISTENCY_CHECK_NOT_A_GATE"
    assert nc["label"] == "NEUTRALIZATION_CONSISTENCY"
    for k in ("hall_discharge_sustained", "closure_residual_rel", "V_collector_V", "V_anode_V", "P_fwd_W",
              "P_refl_W"):
        assert k in nc, k
    assert nc["ratio_I_e_icp_to_I_d"] == pytest.approx(1.0) and nc["I_e_icp_basis"] == "FACILITY_CORRECTED"
    # a Hall-OFF capacity record in the registered extraction topology (P1-S4) IS eligible
    cap_on = synth_cap("SYNTH-S4-CAP-ON", 5.0, synthetic=False, stage="P1-S4")
    cap_off = synth_cap("SYNTH-S4-CAP-OFF", 0.0, rf_on=False, synthetic=False, stage="P1-S4")
    r = red.reduce_operating_points([on, off, cap_on, cap_off], reg, rule,
                                    [["SYNTH-S7-ON", "SYNTH-S7-OFF"], ["SYNTH-S4-CAP-ON", "SYNTH-S4-CAP-OFF"]], MATCH,
                                    CLOSE)
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
    assert items["P1-IT-38"]["status"].startswith("OWNER_DECIDED (A9.4 P1Q-10")
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
    rec["h1_electrical"]["anode_state"] = "METERED_RETURN"                   # metered return: DIAGNOSTIC_VARIANT only
    rec["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "MEASURED"}
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(rec)
    rec["record_class"] = "DIAGNOSTIC_VARIANT"
    with pytest.raises(red.MissingInputError):                              # needs its separate registration id
        red.validate_operating_point(rec)
    rec["diagnostic_registration_id"] = "SYNTH-DIAG-REG"
    rec["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "OPEN_CIRCUIT_BY_CONSTRUCTION"}
    with pytest.raises(red.P1RecordError):                                  # metered return needs MEASURED basis
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
    assert "CAPACITY" in items["P1-IT-38"]["value"] and "NEUTRALIZATION_CONSISTENCY" in items["P1-IT-38"]["value"]
    assert "PROPOSED" not in items["P1-IT-21"]["status"] and "A9.4 P1Q-14" in items["P1-IT-21"]["status"]
    meas = {m["id"]: m for m in doc["measurements"]}
    assert not any("UB-P-06" in u or "A9H-CAL-03" in u for u in meas["P1-M-05"]["uncertainty_sources"])
    assert meas["P1-M-15"]["stages"] == "S3-S7"
    assert "match_setting_id" in meas["P1-M-03"]["note"]
    si = {x["id"]: x for x in doc["safety_interlocks"]}
    assert "PROPOSED EXTENSION" not in si["P1-SI-05"]["threshold"] and "1.05 kV DC / 60 s" in si["P1-SI-05"]["threshold"]
    s0 = [s for s in doc["stage_map"] if s["id"] == "P1-S0"][0]
    assert any("insulation-resistance / hipot" in x for x in s0["exit"])
    assert any("P1-IT-39" in x for x in s0["exit"])
    s7h = [s for s in doc["stage_map"] if s["id"] == "P1-S7H"][0]
    assert any("P1-IT-31" in x for x in s7h["entry"])
    qs = {q["id"] for q in doc["open_owner_questions"]}
    assert not ({"P1Q-10", "P1Q-13", "P1Q-14"} & qs)


# ------------------------------------------------------------------ A9.4 incorporation (fo_a9_4_incorporation)
def _a94():
    with open(A94, encoding="utf-8") as f:
        return json.load(f)


def test_a94_pinned_and_recorded(doc):
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"] == \
        "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d"
    assert pins["docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"] == \
        "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c"
    inc = doc["a9_4_incorporation"]
    assert inc["follow_on"] == "fo_a9_4_incorporation" and inc["trigger"] == "T_A9_4_INCORPORATION"
    assert inc["base_commit"] == "875ed6d0a87202bc92706b28551b0e22eda2014d"
    a94 = _a94()
    for q in ("P1Q-10", "P1Q-13", "P1Q-14"):
        assert inc["answered"][q] == a94["decisions"][q]["status"]


def test_a94_answered_questions_moved(doc):
    qs = {q["id"] for q in doc["open_owner_questions"]}
    assert not ({"P1Q-10", "P1Q-13", "P1Q-14", "P1Q-15", "P1Q-16"} & qs)          # P1Q-15/16 answered by A9.5
    assert {"P1Q-17", "P1Q-18", "P1Q-19", "P1Q-20"} <= qs
    applied = {a["id"]: a for a in doc["owner_answers_applied"]}
    for k in ("A9.4 P1Q-10", "A9.4 P1Q-13", "A9.4 P1Q-14", "A9.4 P2Q-05", "A9.4 execution_decisions.i_d_max_h1",
              "A9.4 execution_decisions.p1_needed_rfqs"):
        assert k in applied, k
        assert "OD_2026_09_30_A9_4_p1_p2_owner_decisions.json" in applied[k]["kind"], k
    for k in ("A9.4 P1Q-10", "A9.4 P1Q-13", "A9.4 P1Q-14"):
        assert applied[k]["how_applied"].startswith("ANSWERED"), k
    assert "recorder reading" in applied["A9.4 P1Q-10"]["how_applied"]


def test_a94_items_owner_decided(doc):
    items = {i["id"]: i for i in doc["items"]}
    assert "I_e,collector,RFON - I_e,collector,RFOFF" in items["P1-IT-38"]["value"]
    assert "recorder reading" in items["P1-IT-38"]["value"]
    assert items["P1-IT-39"]["status"].startswith("OWNER_DECIDED (A9.4 P1Q-13")
    assert "OPEN_CIRCUIT_BY_CONSTRUCTION" in items["P1-IT-39"]["value"]
    assert items["P1-IT-21"]["value"] == 350.0
    assert items["P1-IT-43"]["value"] == 525.0 and items["P1-IT-43"]["evidence_class"] == "owner-stated"
    assert items["P1-IT-44"]["value"] == {"V_test_V_DC": 1050.0, "duration_s": 60.0}
    assert "verify" in items["P1-IT-44"]["basis"] and "ICPQ-06" in items["P1-IT-44"]["note"]
    assert items["P1-IT-45"]["value"].startswith("TBD") and items["P1-IT-45"]["evidence_class"] is None
    assert items["P1-IT-46"]["value"].startswith("TBD") and "ICP-44" in items["P1-IT-46"]["name"]
    assert items["P1-IT-47"]["status"].startswith("OWNER_DECIDED (A9.5 P1Q-15")          # A9.5 answered P1Q-15
    assert items["P1-IT-47"]["value"]["k_sigma"] == 3.0 and items["P1-IT-47"]["value"]["fraction_max"] == 0.02
    assert "~1 kV DC" in items["P1-IT-20"]["value"]                      # ICPQ-06 gas-line rule kept distinct
    assert "8.33" not in str(items["P1-IT-07"]["value"]) and "NOT_EVALUATED" in items["P1-IT-07"]["note"]
    for it in doc["items"]:
        assert "PROPOSED EXTENSION" not in str(it["status"]), it["id"]


def test_a94_stage_map_and_measurements(doc):
    ids = [s["id"] for s in doc["stage_map"]]
    assert ids.index("P1-S7H") == ids.index("P1-S7") + 1
    s7h = [s for s in doc["stage_map"] if s["id"] == "P1-S7H"][0]
    work = " ".join(s7h["work"])
    for need in ("sustainment", "current closure", "neutralization behaviour", "stability",
                 "collector / reference potentials", "RF power", "NEUTRALIZATION_CONSISTENCY"):
        assert need in work, need
    s0 = [s for s in doc["stage_map"] if s["id"] == "P1-S0"][0]
    assert any("1.05 kV DC for 60 s" in x for x in s0["exit"])
    meas = {m["id"]: m for m in doc["measurements"]}
    assert meas["P1-M-28"]["status"].startswith("REQUIRED") and "INS-P2-10" in meas["P1-M-28"]["instrument_class"]
    assert "no numeric threshold" in meas["P1-M-28"]["note"]
    assert meas["P1-M-29"]["status"].startswith("REQUIRED") and "refuses" in meas["P1-M-29"]["note"]
    assert meas["P1-M-27"]["status"].startswith("REQUIRED")
    hw = " ".join(h["item"] for h in doc["hardware_readiness"])
    for need in ("photodiode", "optical access / window", "1.05 kV", "single-point metered"):
        assert need in hw, need
    assert doc["m16_impact"] and "none" in doc["a9_4_incorporation"]["m16_impact_change"]


def test_a94_schema_carries_record_class_and_capacity_monitoring(red):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    op = sc["$defs"]["icp_operating_point"]
    assert op["properties"]["record_class"]["enum"] == list(red.RECORD_CLASSES)
    assert "ICP45_CAPACITY" in red.RECORD_CLASSES and "NEUTRALIZATION_CONSISTENCY" in red.RECORD_CLASSES
    assert op["properties"]["capacity_monitoring"]["required"] == list(red.CAPACITY_MONITORING_REQUIRED)
    assert "discharge_supply_connection" in op["properties"]["h1_electrical"]["required"]


def test_a94_capacity_record_refusals(red):
    red.validate_operating_point(synth_cap("SYNTH-CAP-OK", 1.0))
    bad = synth_cap("SYNTH-CAP-MET", 1.0)
    bad["h1_electrical"]["anode_state"] = "METERED_RETURN"
    bad["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "MEASURED"}
    with pytest.raises(red.CapacityConfigurationError):              # refused, not merely flagged
        red.validate_operating_point(bad)
    bad = synth_cap("SYNTH-CAP-CONN", 1.0)
    bad["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)
    for k in ("h1_body_ground_config", "I_body_to_ground_continuous", "V_anode_channel", "V_icp_body_V",
              "V_electron_collector_V", "sign_convention_id"):
        bad = synth_cap("SYNTH-CAP-" + k, 1.0)
        del bad["capacity_monitoring"][k]
        with pytest.raises(red.CapacityConfigurationError):
            red.validate_operating_point(bad)
    for k, v in (("h1_body_ground_config", "TWO_GROUND_PATHS"), ("I_body_to_ground_continuous", False),
                 ("V_anode_channel", "SCOPE_PROBE")):
        bad = synth_cap("SYNTH-CAP-V-" + k, 1.0)
        bad["capacity_monitoring"][k] = v
        with pytest.raises(red.CapacityConfigurationError):
            red.validate_operating_point(bad)
    bad = synth_cap("SYNTH-CAP-NOMON", 1.0)
    del bad["capacity_monitoring"]
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)
    bad = synth_cap("SYNTH-CAP-NOBODY", 1.0)
    del bad["terminals"]["h1_body"]                                   # I_body->ground missing -> refuse
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)
    bad = synth_cap("SYNTH-CAP-WALL", 1.0, extraction={"topology_id": "SYNTH-TOPO-B",
                                                        "electron_collecting_electrode": "CHAMBER_WALL_FACILITY_GROUND"})
    del bad["terminals"]["electron_collector"]
    bad["terminals"]["facility_ground"]["I_A"] = -1.0
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)
    with pytest.raises(red.CapacityConfigurationError):              # Hall ON is never ICP45_CAPACITY
        red.validate_operating_point(synth_s7(red, "SYNTH-S7-CAP", 1.0, record_class="ICP45_CAPACITY"))
    with pytest.raises(red.CapacityConfigurationError):              # OFF supply left connected (any record)
        rec = synth_op()
        rec["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"
        red.validate_operating_point(rec)
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(synth_op(record_class="SOMETHING"))
    with pytest.raises(red.MissingInputError):
        rec = synth_op()
        del rec["record_class"]
        red.validate_operating_point(rec)


def test_a94_capacity_measurand_is_dedicated_collector_and_closure_gate(red):
    reg = dict(REG, I_d_max_H1_A=2.0)
    on = synth_cap("SYNTH-M-ON", 3.0, synthetic=False, stage="P1-S4")
    on["terminals"]["electron_collector"]["I_A"] = -2.5              # 0.5 A lost to the H-1 body: not capacity
    on["terminals"]["h1_body"]["I_A"] = -0.5
    off = synth_cap("SYNTH-M-OFF", 0.2, rf_on=False, synthetic=False, stage="P1-S4")
    pair = [["SYNTH-M-ON", "SYNTH-M-OFF"]]
    r = red.reduce_operating_points([on, off], reg, RULE, pair, MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert ic["I_e_cap_A"] == pytest.approx(2.5 - 0.2)              # collector current only, RF ON - RF OFF
    # no registered closure rule -> no capacity point admitted
    r = red.reduce_operating_points([on, off], reg, RULE, pair, MATCH)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
    assert any("closure rule not registered" in " ".join(e["reasons"]) for e in ic["excluded_records"])
    # an unexplained residual invalidates the point (owner rule A9.5: statistical and fractional closure)
    leak = copy.deepcopy(on)
    leak["terminals"]["h1_body"]["I_A"] = 0.0                         # 0.5 A unexplained
    r = red.reduce_operating_points([leak, off], reg, RULE, pair, MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED"
    assert any("statistical closure fails" in " ".join(e["reasons"]) for e in ic["excluded_records"])
    with pytest.raises(red.MissingInputError):
        red.reduce_operating_points([on, off], reg, RULE, pair, MATCH, {"rule_id": "X"})


def test_a94_not_evaluated_until_registration(red):
    on = synth_cap("SYNTH-N-ON", 9.0, synthetic=False)
    off = synth_cap("SYNTH-N-OFF", 0.0, rf_on=False, synthetic=False)
    r = red.reduce_operating_points([on, off], None, None, [["SYNTH-N-ON", "SYNTH-N-OFF"]], MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
    assert "8.33 A" in ic["reason"] and "not PASS or FAIL" in ic["reason"]
    assert ic["status_vocabulary"] == ["NOT_EVALUATED", "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE",
                                       "EVALUATED_ENGINEERING_ONLY"]
    assert ic["capacity_label"] == "ICP45_CAPACITY" and ic["consistency_label"] == "NEUTRALIZATION_CONSISTENCY"
    for st in ic["status_vocabulary"]:
        assert "PASS" not in st and "FAIL" not in st
    with pytest.raises(red.RegistrationError):                       # the 8.33 A supply rating is never I_d,max,H1
        red.icp45a_evaluate([on, off], dict(REG, basis="SUPPLY_RATING", I_d_max_H1_A=8.33), RULE, {}, CLOSE)


def test_a94_diagnostic_metered_return_never_feeds_cap(red):
    reg = dict(REG, I_d_max_H1_A=2.0)
    recs = []
    for rid, i_e, rf_on in (("SYNTH-D-ON", 50.0, True), ("SYNTH-D-OFF", 0.0, False)):
        r_ = synth_cap(rid, i_e, rf_on=rf_on, synthetic=False, stage="P1-S4")
        r_["record_class"] = "DIAGNOSTIC_VARIANT"
        r_["diagnostic_registration_id"] = "SYNTH-DIAG-METERED"
        r_["h1_electrical"]["anode_state"] = "METERED_RETURN"
        r_["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "MEASURED"}
        recs.append(r_)
    r = red.reduce_operating_points(recs, reg, RULE, [["SYNTH-D-ON", "SYNTH-D-OFF"]], MATCH, CLOSE)
    ic = r["summary"]["icp45a"]
    assert ic["status"] == "NOT_EVALUATED"
    reasons = {e["record_id"]: " ".join(e["reasons"]) for e in ic["excluded_records"]}
    assert "DIAGNOSTIC_VARIANT" in reasons["SYNTH-D-ON"] and "ICP45_CAPACITY" in reasons["SYNTH-D-ON"]


def test_a94_closure_requires_registered_sign_convention(red):
    """PR #34 review: a paired record under another sign convention is never closure-validated against the rule."""
    reg = dict(REG, I_d_max_H1_A=2.0)
    pair = [["SYNTH-SC-ON", "SYNTH-SC-OFF"]]
    for which in ("on", "off"):
        on = synth_cap("SYNTH-SC-ON", 3.0, synthetic=False, stage="P1-S4")
        off = synth_cap("SYNTH-SC-OFF", 0.2, rf_on=False, synthetic=False, stage="P1-S4")
        (on if which == "on" else off)["capacity_monitoring"]["sign_convention_id"] = "SYNTH-OTHER-SIGN"
        ic = red.reduce_operating_points([on, off], reg, RULE, pair, MATCH, CLOSE)["summary"]["icp45a"]
        assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
        assert any("differs from the closure rule" in " ".join(e["reasons"]) for e in ic["excluded_records"])


def test_a94_mixed_synthetic_and_measured_candidates_refused(red):
    """PR #34 review: a synthetic candidate must never suppress or substitute a measured evaluation."""
    reg = dict(REG, I_d_max_H1_A=2.0)
    recs = [synth_cap("SYNTH-MX-ON", 3.0, synthetic=False, stage="P1-S4"),
            synth_cap("SYNTH-MX-OFF", 0.2, rf_on=False, synthetic=False, stage="P1-S4"),
            synth_cap("SYNTH-MY-ON", 9.0, synthetic=True, stage="P1-S4"),
            synth_cap("SYNTH-MY-OFF", 0.0, rf_on=False, synthetic=True, stage="P1-S4")]
    pairs = [["SYNTH-MX-ON", "SYNTH-MX-OFF"], ["SYNTH-MY-ON", "SYNTH-MY-OFF"]]
    with pytest.raises(red.P1RecordError, match="mix synthetic"):
        red.reduce_operating_points(recs, reg, RULE, pairs, MATCH, CLOSE)
    ic = red.reduce_operating_points(recs[:2], reg, RULE, pairs[:1], MATCH, CLOSE)["summary"]["icp45a"]
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY" and ic["I_e_cap_A"] == pytest.approx(2.8)


# ------------------------------------------------------------------ A9.5 P1Q-15 / P1Q-16 (fo_a9_5_closure_rule)
A95 = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_5_p1_closure_owner_decisions.json")


def _pair(on_ie=3.0, off_ie=0.2, synthetic=False, tag="P"):
    on = synth_cap("SYNTH-%s-ON" % tag, on_ie, synthetic=synthetic, stage="P1-S4")
    off = synth_cap("SYNTH-%s-OFF" % tag, off_ie, rf_on=False, synthetic=synthetic, stage="P1-S4")
    return on, off


def _ic(red, on, off, rule=None, reg=None, margin=None):
    reg = reg or dict(REG, I_d_max_H1_A=2.0)
    rule = CLOSE if rule is None else rule
    return red.reduce_operating_points([on, off], reg, margin or RULE, [[on["record_id"], off["record_id"]]], MATCH,
                                       rule)["summary"]["icp45a"]


def _reasons(ic, rid):
    return " ".join([" ".join(e["reasons"]) for e in ic["excluded_records"] if e["record_id"] == rid])


def test_a95_pinned_and_recorded(doc):
    with open(A95, encoding="utf-8") as f:
        a95 = json.load(f)
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json"] == \
        "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3"
    assert pins["docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md"] == \
        "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3"
    inc = doc["a9_5_incorporation"]
    assert inc["follow_on"] == "fo_a9_5_closure_rule" and inc["trigger"] == "T_A9_5_CLOSURE_RULE"
    assert inc["base_commit"] == "71f31b2a254fe01059b130b554b97c7584ae6b30"
    for q in ("P1Q-15", "P1Q-16"):
        assert inc["answered"][q] == a95["decisions"][q]["status"]
    assert inc["reducer"]["owner_constants"] == {"CLOSURE_K_SIGMA": 3.0, "CLOSURE_FRACTION_MAX": 0.02}
    items = {i["id"]: i for i in doc["items"]}
    for k in ("P1-IT-48", "P1-IT-49", "P1-IT-50", "P1-IT-51"):
        assert k in items, k
    assert items["P1-IT-48"]["value"].startswith("TBD") and items["P1-IT-48"]["evidence_class"] is None
    assert "NOT_EVALUATED_INSTRUMENT" in items["P1-IT-50"]["value"]
    assert "CONFIRMED by owner A9.5 P1Q-16" in items["P1-IT-38"]["value"]
    assert "no zero-clipping" in items["P1-IT-38"]["value"]
    assert items["P1-IT-42"]["status"].startswith("OWNER_DECIDED network convention (A9.5 P1Q-15)")
    applied = {a["id"]: a for a in doc["owner_answers_applied"]}
    for k in ("A9.5 P1Q-15", "A9.5 P1Q-16"):
        assert applied[k]["how_applied"].startswith("ANSWERED"), k
        assert "OD_2026_09_30_A9_5_p1_closure_owner_decisions.json" in applied[k]["kind"]
    s4 = [s_ for s_ in doc["stage_map"] if s_["id"] == "P1-S4"][0]
    work = " ".join(s4["work"])
    assert "PROPOSED" not in work and "OWNER_DECIDED, A9.4 P1Q-10" in work       # carried A9.4 minor fixed
    assert "PROPOSED option A" not in json.dumps(items["P1-IT-36"])
    d13 = {d["id"]: d for d in doc["derived_quantities"]}
    assert "3 u_R" in d13["P1-D-13"]["formula"] and "P1-D-14" in d13 and "P1-D-15" in d13


def test_a95_closure_rule_constants_not_parameters(red):
    assert red.CLOSURE_K_SIGMA == 3.0 and red.CLOSURE_FRACTION_MAX == 0.02
    on, off = _pair()
    for widen in ({"residual_rel_tol": 0.05}, {"k_sigma": 5.0}, {"fraction_max": 0.05}, {"tolerance": 1.0}):
        with pytest.raises(red.ClosureRuleError):
            _ic(red, on, off, rule=dict(CLOSE, **widen))
    with pytest.raises(red.ClosureRuleError):
        _ic(red, on, off, rule=dict(CLOSE, sign_convention="ELECTRON_FLOW_POSITIVE"))
    for k in ("I_scale_min_A", "I_scale_min_basis", "sign_convention_id", "sign_convention", "rule_id"):
        rule = dict(CLOSE)
        del rule[k]
        with pytest.raises(red.MissingInputError):                   # I_scale,min has no default
            _ic(red, on, off, rule=rule)
    for bad in (0.0, -0.01, None):
        with pytest.raises((red.MissingInputError, red.P1RecordError)):
            _ic(red, on, off, rule=dict(CLOSE, I_scale_min_A=bad))
    ic = _ic(red, on, off)
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY" and ic["condition_met"] is True
    assert ic["closure_owner_rule"]["k_sigma"] == 3.0 and ic["closure_owner_rule"]["fraction_max"] == 0.02
    ev = ic["candidates"][0]["closure"]["SYNTH-P-ON"]
    assert ev["R_I_A"] == pytest.approx(0.0) and ev["u_R_A"] == pytest.approx(2.0 * U1)   # four measured channels
    assert ev["channels"]["hall_anode"]["basis"] == "OPEN_CIRCUIT_BY_CONSTRUCTION"
    assert ev["channels"]["hall_anode"]["I_A"] == 0.0 and ev["V_anode_V"] == 3.0          # potential still recorded


def test_a95_unavailable_channel_never_zeroed(red):
    on, off = _pair(tag="U")
    on["terminals"]["facility_ground"] = {"I_A": None, "basis": "NOT_MEASURED"}
    red.validate_operating_point(on)                                  # declared unavailable: valid record
    cl = red.current_closure(on)
    assert cl["sum_A"] is None and cl["closure_state"] == "NOT_EVALUABLE_UNMEASURED_CHANNEL"
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["evaluable"] is False and ev["R_I_A"] is None and ev["closure_valid"] is False
    assert "intentional return path unmeasured" in " ".join(ev["reasons"])
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
    assert "intentional return path unmeasured" in _reasons(ic, "SYNTH-U-ON")
    assert {"record_id": "SYNTH-U-ON", "outcome": "EXCLUDED"} in ic["capacity_point_outcomes"]
    row = [r for r in red.reduce_operating_points([on, off])["surface"] if r["record_id"] == "SYNTH-U-ON"][0]
    assert row["closure_sum_A"] is None and any(f.startswith("TERMINAL_NOT_MEASURED") for f in row["flags"])
    bad = copy.deepcopy(on)
    bad["terminals"]["facility_ground"] = {"I_A": 0.0, "basis": "NOT_MEASURED"}     # a silent zero is refused
    with pytest.raises(red.P1RecordError):
        red.validate_operating_point(bad)
    bad = copy.deepcopy(on)
    bad["terminals"]["collector_supply"] = {"I_A": None, "basis": "NOT_MEASURED"}
    with pytest.raises(red.MissingInputError):
        red.validate_operating_point(bad)
    # an all-zero record is never 'automatically closed': it is reported as such, and a capacity record with
    # all-zero currents still needs measured channels with their uncertainties
    zero = synth_cap("SYNTH-Z-OFF", 0.0, rf_on=False, synthetic=False, stage="P1-S4")
    assert red.current_closure(zero)["closure_state"] == "ALL_TERMINAL_CURRENTS_ZERO_NOT_A_CLOSURE_RESULT"
    for t in zero["terminals"].values():
        t.pop("uncertainty", None)
    ev = red.kirchhoff_closure(zero, CLOSE)
    assert ev["evaluable"] is False and ev["closure_valid"] is False and ev["uncertainties_available"] is False


def test_a95_missing_uncertainty_component_not_evaluable(red):
    for comp, val in (("u_calibration_A", None), ("u_zero_offset_A", "NOT_APPLICABLE"), ("u_resolution_A", 0.0),
                      ("u_repeatability_A", None), ("u_rf_pickup_A", "NA"), ("u_calibration_A", -1e-3)):
        on, off = _pair(tag="M")
        if val is None:
            del off["terminals"]["h1_body"]["uncertainty"][comp]
        else:
            off["terminals"]["h1_body"]["uncertainty"][comp] = val
        ic = _ic(red, on, off)
        assert ic["status"] == "NOT_EVALUATED", comp
        assert "u(I_k) unavailable for terminal 'h1_body'" in _reasons(ic, "SYNTH-M-ON"), comp
        ex = [e for e in ic["excluded_records"] if e["record_id"] == "SYNTH-M-ON"][0]
        assert ex["eligibility"]["3_required_channel_uncertainties_available"] is False
    on, off = _pair(tag="M2")
    del on["terminals"]["electron_collector"]["uncertainty"]
    assert "no uncertainty object" in _reasons(_ic(red, on, off), "SYNTH-M2-ON")
    on, off = _pair(tag="M3")                                          # explicit tokens and numbers are accepted
    on["terminals"]["h1_body"]["uncertainty"].update({"u_repeatability_A": 2e-4, "u_rf_pickup_A": 1e-4})
    assert _ic(red, on, off)["status"] == "EVALUATED_ENGINEERING_ONLY"


def test_a95_statistical_fail(red):
    on, off = _pair(tag="S")
    on["terminals"]["electron_collector"]["I_A"] = -2.99               # R_I = +0.01 A, 3 u_R = 3 * 2 U1 < 0.01 A
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["R_I_A"] == pytest.approx(0.01) and ev["statistical_ok"] is False
    assert ev["fractional_ok"] is True and ev["fraction"] == pytest.approx(0.01 / 2.99)
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED"
    r = _reasons(ic, "SYNTH-S-ON")
    assert "statistical closure fails" in r and "fractional closure" not in r
    ex = [e for e in ic["excluded_records"] if e["record_id"] == "SYNTH-S-ON"][0]
    assert ex["outcome"] == "EXCLUDED" and ex["eligibility"]["1_capacity_point_passes_current_closure"] is False
    assert ex["closure"]["SYNTH-S-ON"]["R_I_A"] == pytest.approx(0.01)       # excluded point keeps its closure record


def test_a95_fractional_fail(red):
    on, off = _pair(tag="F", off_ie=0.05)
    for t in off["terminals"].values():                                  # coarse channels on the RF-OFF record
        if t["basis"] == "MEASURED":
            t["uncertainty"]["u_calibration_A"] = 0.01
    off["terminals"]["h1_body"]["I_A"] = -0.005                          # R_I = -0.005 A on the RF-OFF record
    ev = red.kirchhoff_closure(off, CLOSE)
    assert ev["statistical_ok"] is True and ev["fractional_ok"] is False
    assert ev["denominator_A"] == pytest.approx(0.05) and ev["fraction"] == pytest.approx(0.1)
    ev_floor = red.kirchhoff_closure(off, dict(CLOSE, I_scale_min_A=1.0))    # floor only enters the denominator
    assert ev_floor["denominator_A"] == pytest.approx(1.0) and ev_floor["fractional_ok"] is True
    assert ev_floor["u_R_A"] == pytest.approx(ev["u_R_A"])
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED"
    r = _reasons(ic, "SYNTH-F-ON")
    assert "matched RF-OFF record 'SYNTH-F-OFF'" in r and "fractional closure exceeds 2 %" in r


def test_a95_not_evaluated_instrument(red):
    on, off = _pair(on_ie=0.2, off_ie=0.0, tag="I")                   # 3 u_R = 6 U1 ~ 6.7 mA > 0.02 * 0.2 A
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["closure_valid"] is True and ev["instrument_adequate"] is False
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED" and ic["condition_met"] is None
    assert "NOT_EVALUATED_INSTRUMENT" in ic["point_outcome_vocabulary"]
    assert "NOT_EVALUATED_INSTRUMENT" not in ic["status_vocabulary"]    # overall status stays NOT_EVALUATED
    ni = ic["not_evaluated_instrument_records"]
    assert [x["record_id"] for x in ni] == ["SYNTH-I-ON"] and ni[0]["outcome"] == "NOT_EVALUATED_INSTRUMENT"
    assert "never widened" in ni[0]["reasons"][0]
    assert {"record_id": "SYNTH-I-ON", "outcome": "NOT_EVALUATED_INSTRUMENT"} in ic["capacity_point_outcomes"]
    assert not any(e["record_id"] == "SYNTH-I-ON" for e in ic["excluded_records"])
    assert "NOT_EVALUATED_INSTRUMENT" in ic["reason"]
    on, off = _pair(on_ie=0.5, off_ie=0.0, tag="J")                   # 0.02 * 0.5 A = 10 mA >= 6.7 mA: adequate
    assert _ic(red, on, off)["status"] == "EVALUATED_ENGINEERING_ONLY"


def test_a95_covariance_form(red):
    on, off = _pair(tag="C")
    on["terminals"]["h1_body"]["I_A"] = -0.008                          # R_I = -0.008 A
    ind = red.kirchhoff_closure(on, CLOSE)
    assert ind["u_R_A"] == pytest.approx(2.0 * U1) and ind["statistical_ok"] is False
    names = ["collector_supply", "electron_collector", "facility_ground", "h1_body"]
    full = dict(CLOSE, covariance={"covariance_id": "SYNTH-COV-1", "terminals": names,
                                   "correlation": [[1.0] * 4 for _ in range(4)]})
    cov = red.kirchhoff_closure(on, full)
    assert cov["u_R_A"] == pytest.approx(4.0 * U1) and cov["statistical_ok"] is True
    assert cov["u_R_method"].startswith("FULL_COVARIANCE")
    rho = [[1.0, 0.5, 0.0, 0.0], [0.5, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, -0.3], [0.0, 0.0, -0.3, 1.0]]
    part = red.kirchhoff_closure(on, dict(CLOSE, covariance={"covariance_id": "SYNTH-COV-2", "terminals": names,
                                                               "correlation": rho}))
    assert part["u_R_A"] == pytest.approx(math.sqrt(sum(r for row in rho for r in row)) * U1)
    eye = red.kirchhoff_closure(on, dict(CLOSE, covariance={"covariance_id": "SYNTH-COV-3", "terminals": names,
                                                              "correlation": [[1.0 if i == j else 0.0 for j in range(4)]
                                                                              for i in range(4)]}))
    assert eye["u_R_A"] == pytest.approx(ind["u_R_A"])                 # identity correlation = independent form
    ic = _ic(red, on, off, rule=full)
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert _ic(red, on, off)["status"] == "NOT_EVALUATED"
    short = red.kirchhoff_closure(on, dict(CLOSE, covariance={"covariance_id": "SYNTH-COV-4", "terminals": names[:3],
                                                                "correlation": [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]}))
    assert short["evaluable"] is False and "does not cover" in " ".join(short["reasons"])
    for bad in ([[1.0, 0.2, 0, 0], [0.1, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]],        # not symmetric
                [[2.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]],          # diagonal != 1
                [[1.0, 0.9, 0.9, 0], [0.9, 1.0, -0.9, 0], [0.9, -0.9, 1.0, 0], [0, 0, 0, 1.0]],  # not PSD
                [[1.0, 0], [0, 1.0]]):                                                      # wrong size
        with pytest.raises(red.ClosureRuleError):
            red.kirchhoff_closure(on, dict(CLOSE, covariance={"covariance_id": "X", "terminals": names,
                                                                "correlation": bad}))


def test_a95_negative_capacity_kept_signed(red):
    on, off = _pair(on_ie=0.5, off_ie=0.9, tag="N")
    ic = _ic(red, on, off)
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert ic["I_e_cap_A"] == pytest.approx(-0.4)                        # no abs, no clipping
    assert ic["M_n"] == pytest.approx(-0.4 / 2.0 - 1.0) and ic["condition_met"] is False
    assert any(f.startswith("I_E_CAP_NEGATIVE") for f in ic["flags"])
    fc = red.facility_electron_check(on, off, MATCH)
    assert fc["I_e_collector_corrected_A"] == pytest.approx(-0.4) and fc["I_e_icp_corrected_A"] == pytest.approx(-0.4)
    assert red.i_e_cap_signed(0.1, 0.3) == pytest.approx(-0.2)
    import inspect
    body = inspect.getsource(red.i_e_cap_signed).split('"""')[-1]
    for banned in ("abs(", "max(", "min(", "clip", "fabs"):
        assert banned not in body, banned
    ev_src = inspect.getsource(red.icp45a_evaluate)
    for banned in ("abs(", "max(0", "clip(", "fabs("):
        assert banned not in ev_src, banned


def test_a95_eligibility_conditions(red):
    on, off = _pair(tag="E")
    ic = _ic(red, on, off)                                               # all four conditions met
    assert ic["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert ic["eligibility"] == {"1_capacity_point_passes_current_closure": True,
                                 "2_matched_rf_off_correction_valid": True,
                                 "3_required_channel_uncertainties_available": True, "4_I_d_max_H1_registered": True}
    assert ic["u_I_e_cap_from_channels_A"] == pytest.approx(math.sqrt(2.0) * U1)
    assert ic["u_I_e_cap_used_A"] == RULE["u_I_e_A"]
    # (1) closure fails
    bad_on = copy.deepcopy(on)
    bad_on["terminals"]["h1_body"]["I_A"] = -0.3
    ex = [e for e in _ic(red, bad_on, off)["excluded_records"] if e["record_id"] == "SYNTH-E-ON"][0]
    assert ex["eligibility"]["1_capacity_point_passes_current_closure"] is False
    # (2) no matched RF-OFF record
    reg = dict(REG, I_d_max_H1_A=2.0)
    ic2 = red.reduce_operating_points([on, off], reg, RULE, None, MATCH, CLOSE)["summary"]["icp45a"]
    assert ic2["status"] == "NOT_EVALUATED" and "pairing not matched" in _reasons(ic2, "SYNTH-E-ON")
    # (3) channel uncertainty missing; margin-rule uncertainty missing is refused (no hidden default)
    miss = copy.deepcopy(on)
    del miss["terminals"]["collector_supply"]["uncertainty"]
    assert _ic(red, miss, off)["status"] == "NOT_EVALUATED"
    for k in ("u_I_e_A", "u_I_d_max_A"):
        mr = dict(RULE)
        del mr[k]
        with pytest.raises(red.MissingInputError):
            _ic(red, on, off, margin=mr)
    # (4) I_d,max,H1 not registered
    ic4 = red.reduce_operating_points([on, off], None, None, [["SYNTH-E-ON", "SYNTH-E-OFF"]], MATCH,
                                      CLOSE)["summary"]["icp45a"]
    assert ic4["status"] == "NOT_EVALUATED" and ic4["eligibility"] == {"4_I_d_max_H1_registered": False}
    # a registered u_I_e_A below the channel propagation is flagged, never silently replaced
    small = dict(RULE, u_I_e_A=1e-4)
    ic5 = _ic(red, on, off, margin=small)
    assert any(f.startswith("REGISTERED_u_I_e_BELOW_CHANNEL_PROPAGATION") for f in ic5["flags"])
    assert ic5["u_I_e_cap_used_A"] == 1e-4


def test_a95_exclusions_ground_path_sign_and_mixed(red):
    on, off = _pair(tag="G")
    on["capacity_monitoring"]["unintended_ground_path_found"] = True
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED" and "unintended ground path found" in _reasons(ic, "SYNTH-G-ON")
    for k in ("unintended_ground_path_found", "ground_path_check_id"):
        bad, _ = _pair(tag="G2")
        del bad["capacity_monitoring"][k]
        with pytest.raises(red.CapacityConfigurationError):
            red.validate_operating_point(bad)
    bad, _ = _pair(tag="G3")
    bad["capacity_monitoring"]["unintended_ground_path_found"] = "no"
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)
    on, off = _pair(tag="SC")
    off["terminals"]["h1_body"]["sign_convention_id"] = "SYNTH-OTHER-SIGN"
    assert "current sign conventions differ between channels" in _reasons(_ic(red, on, off), "SYNTH-SC-ON")
    on, off = _pair(tag="SD")
    del on["terminals"]["facility_ground"]["sign_convention_id"]
    assert "declares no sign_convention_id" in _reasons(_ic(red, on, off), "SYNTH-SD-ON")
    on, off = _pair(tag="MX")
    off["synthetic"] = True
    assert "synthetic and measured evidence mixed" in _reasons(_ic(red, on, off), "SYNTH-MX-ON")
    # the anode rule stays a refusal for ICP45_CAPACITY records (A9.4 P1Q-13) and names the reason
    on, off = _pair(tag="AN")
    on["h1_electrical"]["anode_state"] = "METERED_RETURN"
    on["terminals"]["hall_anode"] = _meas(0.0)
    with pytest.raises(red.CapacityConfigurationError, match="anode"):
        _ic(red, on, off)


def test_a95_schema_and_hall_on(red):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    op = sc["$defs"]["icp_operating_point"]
    term = op["properties"]["terminals"]["additionalProperties"]
    assert "NOT_MEASURED" in term["properties"]["basis"]["enum"]
    assert term["properties"]["uncertainty"]["required"] == list(red.U_COMPONENTS)
    cm = op["properties"]["capacity_monitoring"]["properties"]
    assert cm["unintended_ground_path_found"] == {"type": "boolean"}
    x = sc["x-closure-rule-input"]
    assert x["owner_constants"] == {"k_sigma": 3.0, "fraction_max": 0.02}
    assert "residual_rel_tol" not in x["allowed"] and "I_scale_min_A" in x["required"]
    assert "never define I_e,cap" in red.I_E_CAP_DEFINITION and "OWNER_CONFIRMED by A9.5" in red.I_E_CAP_DEFINITION
