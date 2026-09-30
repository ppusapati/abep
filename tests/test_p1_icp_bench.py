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
    assert "docs/procurement/rfq_a9_v2/rfq_a9_v2.json" not in pins   # RFQ v2 reads P1: ids checked, a pin would be circular
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
    # A9.5 P1Q-15 turns a non-floating anode in an ICP45_CAPACITY record into an EXCLUSION of the point (kept with
    # its reason; test_a95_anode_not_floating_is_excluded_not_aborting): validation no longer raises for it
    bad = synth_cap("SYNTH-CAP-MET", 1.0)
    bad["h1_electrical"]["anode_state"] = "METERED_RETURN"
    bad["terminals"]["hall_anode"] = {"I_A": 0.0, "basis": "MEASURED"}
    red.validate_operating_point(bad)
    assert "not physically disconnected" in " ".join(red.capacity_structural_reasons(bad))
    bad = synth_cap("SYNTH-CAP-CONN", 1.0)
    bad["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"
    red.validate_operating_point(bad)
    assert "not physically disconnected" in " ".join(red.capacity_structural_reasons(bad))
    bad = synth_cap("SYNTH-CAP-NOSUPPLYSTATE", 1.0)
    bad["h1_electrical"]["discharge_supply_connection"] = "COMMANDED_ZERO"
    with pytest.raises(red.P1RecordError):                           # not a recorded connection state at all
        red.validate_operating_point(bad)
    for k in ("h1_body_ground_config", "I_body_to_ground_continuous", "V_anode_channel", "V_icp_body_V",
              "V_electron_collector_V", "sign_convention_id"):
        bad = synth_cap("SYNTH-CAP-" + k, 1.0)
        del bad["capacity_monitoring"][k]
        with pytest.raises(red.CapacityConfigurationError):
            red.validate_operating_point(bad)
    for k, v in (("h1_body_ground_config", "TWO_GROUND_PATHS"), ("I_body_to_ground_continuous", "yes"),
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
    lists = ic["excluded_records"] + ic.get("not_evaluated_uncertainty_records", []) + \
        ic.get("not_evaluated_instrument_records", [])
    return " ".join([" ".join(e["reasons"]) for e in lists if e["record_id"] == rid])


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
    assert "PROPOSED: (A)" not in items["P1-IT-36"]["value"] and "PROPOSED" not in items["P1-IT-36"]["value"]
    assert "Two cases are REFUSED" not in json.dumps(items["P1-IT-51"]) and "P1Q-21" in json.dumps(items["P1-IT-51"])
    qs = {q["id"] for q in doc["open_owner_questions"]}
    # A9.6 sec. 6: P1Q-21..P1Q-23 settled as DERIVED (fo_a9_6_p1_workflow_completion), no longer open
    assert not ({"P1Q-21", "P1Q-22", "P1Q-23"} & qs) and "P1Q-15" not in qs and "P1Q-16" not in qs
    dq = {d["id"]: d for d in doc["derived_quantities"]}
    assert "DERIVED" in dq["P1-D-14"]["basis"] and "DERIVED" in dq["P1-D-15"]["basis"]
    assert "LANE CHOICE" not in dq["P1-D-14"]["basis"] + dq["P1-D-15"]["basis"]
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
        # A9.6 sec. 14: missing uncertainty -> NOT_EVALUATED (point outcome NOT_EVALUATED_UNCERTAINTY, not EXCLUDED)
        ex = [e for e in ic["not_evaluated_uncertainty_records"] if e["record_id"] == "SYNTH-M-ON"][0]
        assert ex["outcome"] == "NOT_EVALUATED_UNCERTAINTY"
        assert ex["eligibility"]["3_required_channel_uncertainties_available"] is False
        assert not any(e["record_id"] == "SYNTH-M-ON" for e in ic["excluded_records"])
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
                                 "3_required_channel_uncertainties_available": True,
                                 "3_required_margin_rule_uncertainties_available": True,
                                 "4_I_d_max_H1_registered": True}
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
    # (3) channel uncertainty missing; margin-rule uncertainty missing / None / zero -> NOT_EVALUATED with condition
    # (3) false (A9.5 P1Q-16 'until all four exist: ICP45 = NOT_EVALUATED'; no hidden default, no raise)
    miss = copy.deepcopy(on)
    del miss["terminals"]["collector_supply"]["uncertainty"]
    assert _ic(red, miss, off)["status"] == "NOT_EVALUATED"
    for k in ("u_I_e_A", "u_I_d_max_A"):
        for how in ("del", None, 0.0):
            mr = dict(RULE)
            if how == "del":
                del mr[k]
            else:
                mr[k] = how
            icm = _ic(red, on, off, margin=mr)
            assert icm["status"] == "NOT_EVALUATED" and icm["condition_met"] is None, (k, how)
            assert icm["eligibility"]["3_required_margin_rule_uncertainties_available"] is False
            assert "condition (3)" in icm["reason"] and k in icm["reason"]
            assert "M_n" not in icm and "M_n_lower" not in icm
        with pytest.raises(red.P1RecordError):                         # a negative value is an input error
            _ic(red, on, off, margin=dict(RULE, **{k: -0.01}))
    # (4) I_d,max,H1 not registered
    ic4 = red.reduce_operating_points([on, off], None, None, [["SYNTH-E-ON", "SYNTH-E-OFF"]], MATCH,
                                      CLOSE)["summary"]["icp45a"]
    assert ic4["status"] == "NOT_EVALUATED" and ic4["eligibility"] == {"4_I_d_max_H1_registered": False}
    # a registered u_I_e_A below the channel propagation is flagged and never used as it stands (DERIVED P1Q-19);
    # the two admissible treatments disagree -> NOT_EVALUATED (TBD_OWNER P1Q-19)
    small = dict(RULE, u_I_e_A=1e-4)
    ic5 = _ic(red, on, off, margin=small)
    assert any(f.startswith("REGISTERED_u_I_e_BELOW_CHANNEL_PROPAGATION") for f in ic5["flags"])
    assert ic5["status"] == "NOT_EVALUATED" and ic5["condition_met"] is None and "u_I_e_cap_used_A" not in ic5
    assert ic5["u_I_e_cap_registered_A"] == 1e-4 and ic5["p1q19_alternatives"]["agree"] is False


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
    # the anode rule is an A9.5 exclusion of the capacity point (kept with reason), no longer an abort
    on, off = _pair(tag="AN")
    on["h1_electrical"]["anode_state"] = "METERED_RETURN"
    on["terminals"]["hall_anode"] = _meas(0.0)
    off["h1_electrical"]["anode_state"] = "METERED_RETURN"
    off["terminals"]["hall_anode"] = _meas(0.0)
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED" and "not physically disconnected / floating" in _reasons(ic, "SYNTH-AN-ON")
    assert {"record_id": "SYNTH-AN-ON", "outcome": "EXCLUDED"} in ic["capacity_point_outcomes"]


def _two_pairs(red, mutate_off):
    """One valid measured pair (A) next to a second measured pair (B) whose RF-OFF record is mutated."""
    on_a, off_a = _pair(tag="PA")
    on_b, off_b = _pair(on_ie=3.5, off_ie=0.2, tag="PB")
    mutate_off(on_b, off_b)
    reg = dict(REG, I_d_max_H1_A=2.0)
    pairs = [["SYNTH-PA-ON", "SYNTH-PA-OFF"], ["SYNTH-PB-ON", "SYNTH-PB-OFF"]]
    return red.reduce_operating_points([on_a, off_a, on_b, off_b], reg, RULE, pairs, MATCH, CLOSE)


def test_a95_pair_mismatch_is_excluded_not_aborting(red):
    """Reviewer repro: a registered pair that is not matched excludes its point with the mismatch reason; the other
    (valid) pair is still evaluated and the reduction does not abort."""
    def p10(on, off):
        off["pressures"]["p_chamber_Pa"] = 0.02                         # 0.02 vs 0.01 Pa: outside the 5 % rule

    def vcol(on, off):
        off["collector"]["V_collector_V"] = -30.0                       # -30 V vs -40 V: different V_collector

    for mut, needle in ((p10, "p_chamber differs by 0.5"), (vcol, "collector.V_collector_V differs")):
        out = _two_pairs(red, mut)
        ic = out["summary"]["icp45a"]
        assert ic["status"] == "EVALUATED_ENGINEERING_ONLY" and ic["I_e_cap_record"] == "SYNTH-PA-ON"
        assert [c["record_id"] for c in ic["candidates"]] == ["SYNTH-PA-ON"]
        r = _reasons(ic, "SYNTH-PB-ON")
        assert "RF-ON/RF-OFF pairing not matched" in r and needle in r and "SYNTH-MATCH-RULE" in r
        assert {"record_id": "SYNTH-PB-ON", "outcome": "EXCLUDED"} in ic["capacity_point_outcomes"]
        ex = [e for e in ic["excluded_records"] if e["record_id"] == "SYNTH-PB-ON"][0]
        assert ex["eligibility"]["2_matched_rf_off_correction_valid"] is False
        assert ex["rf_off_record_id"] == "SYNTH-PB-OFF"
        fcs = {tuple(f["records"]): f for f in out["facility_electron_checks"]}
        assert fcs[("SYNTH-PB-ON", "SYNTH-PB-OFF")]["pair_matched"] is False
        assert needle in " ".join(fcs[("SYNTH-PB-ON", "SYNTH-PB-OFF")]["mismatch_reasons"])
        assert fcs[("SYNTH-PA-ON", "SYNTH-PA-OFF")]["pair_matched"] is True
        assert len(out["surface"]) == 4                                 # raw records all kept
    # direct call on a mismatched pair still raises (no facility correction exists for it)
    on, off = _pair(tag="PD")
    off["pressures"]["p_chamber_Pa"] = 0.02
    with pytest.raises(red.P1RecordError, match="p_chamber differs"):
        red.facility_electron_check(on, off, MATCH)
    # a missing match rule is an input error, not a finding
    with pytest.raises(red.MissingInputError):
        red.reduce_operating_points([on, off], dict(REG, I_d_max_H1_A=2.0), RULE, [["SYNTH-PD-ON", "SYNTH-PD-OFF"]],
                                    None, CLOSE)


def test_a95_anode_not_floating_is_excluded_not_aborting(red):
    """Reviewer repro: discharge_supply_connection CONNECTED (or a non-floating anode) on an ICP45_CAPACITY record
    excludes that point with the reason; other points are still evaluated."""
    def conn(on, off):
        for r_ in (on, off):
            r_["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"

    def anode(on, off):
        for r_ in (on, off):
            r_["h1_electrical"]["anode_state"] = "CONNECTED_TO_DISCHARGE_SUPPLY"
            r_["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"
            r_["terminals"]["hall_anode"] = _meas(0.0)

    for mut in (conn, anode):
        ic = _two_pairs(red, mut)["summary"]["icp45a"]
        assert ic["status"] == "EVALUATED_ENGINEERING_ONLY" and ic["I_e_cap_record"] == "SYNTH-PA-ON"
        r = _reasons(ic, "SYNTH-PB-ON")
        assert "H-1 anode not physically disconnected / floating" in r
        ex = [e for e in ic["excluded_records"] if e["record_id"] == "SYNTH-PB-ON"][0]
        assert ex["outcome"] == "EXCLUDED" and ex["eligibility"]["1_capacity_point_passes_current_closure"] is False
    # without a closure rule the anode reason is still reported
    on, off = _pair(tag="AR")
    conn(on, off)
    ic = red.reduce_operating_points([on, off], dict(REG, I_d_max_H1_A=2.0), RULE, [["SYNTH-AR-ON", "SYNTH-AR-OFF"]],
                                     MATCH)["summary"]["icp45a"]
    assert "not physically disconnected / floating" in _reasons(ic, "SYNTH-AR-ON")
    # a non-capacity record keeps the A9.4 refusal (supply OFF left connected)
    rec = synth_op()
    rec["h1_electrical"]["discharge_supply_connection"] = "CONNECTED"
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(rec)


def test_a95_unmeasured_return_paths_excluded_uniformly(red):
    """h1_body / electron_collector / icp_body / facility_ground declared NOT_MEASURED, or I_body->ground not
    continuous: every case is excluded with 'intentional return path unmeasured' (never zeroed, never refused)."""
    for name in ("h1_body", "electron_collector", "facility_ground"):
        on, off = _pair(tag="R" + name[:2].upper())
        on["terminals"][name] = {"I_A": None, "basis": "NOT_MEASURED"}
        red.validate_operating_point(on)
        ic = _ic(red, on, off)
        assert ic["status"] == "NOT_EVALUATED", name
        assert "intentional return path unmeasured: terminal %r" % name in _reasons(ic, on["record_id"]), name
    on, off = _pair(tag="RIC")
    on["terminals"]["icp_body"] = {"I_A": None, "basis": "NOT_MEASURED"}
    assert "terminal 'icp_body' declared NOT_MEASURED" in _reasons(_ic(red, on, off), "SYNTH-RIC-ON")
    on, off = _pair(tag="RCT")
    on["capacity_monitoring"]["I_body_to_ground_continuous"] = False
    red.validate_operating_point(on)
    assert "I_body->ground not measured continuously" in _reasons(_ic(red, on, off), "SYNTH-RCT-ON")
    bad, _ = _pair(tag="RAB")
    del bad["terminals"]["h1_body"]                                    # absent from the record: incomplete -> refused
    with pytest.raises(red.CapacityConfigurationError):
        red.validate_operating_point(bad)


def test_a95_instrument_inadequacy_precedence(red):
    """DERIVED precedence (P1Q-22, A9.6 sec. 6): a fractional-only failure at an instrument-inadequate point ->
    NOT_EVALUATED_INSTRUMENT (not decisive); a STATISTICAL failure |R_I| > 3 u_R stays EXCLUDED even when the
    instrument is inadequate (normalised to u_R); a structural exclusion keeps precedence over inadequacy."""
    on, off = _pair(on_ie=0.2, off_ie=0.0, tag="IP")
    on["terminals"]["h1_body"]["I_A"] = -0.005                         # |R_I| 5 mA <= 3 u_R (6.7 mA), > 2 % of 0.2 A
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["statistical_ok"] is True and ev["fractional_ok"] is False and ev["instrument_adequate"] is False
    ic = _ic(red, on, off)
    assert ic["status"] == "NOT_EVALUATED"
    ni = ic["not_evaluated_instrument_records"]
    assert [x["record_id"] for x in ni] == ["SYNTH-IP-ON"]
    assert any("fractional closure" in x for x in ni[0]["closure_test_results_not_decisive"])
    assert "P1Q-22" in ni[0]["precedence"]
    assert not any(e["record_id"] == "SYNTH-IP-ON" for e in ic["excluded_records"])
    on, off = _pair(on_ie=0.2, off_ie=0.0, tag="IS")
    on["terminals"]["h1_body"]["I_A"] = -0.01                          # |R_I| 10 mA > 3 u_R: statistically significant
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["statistical_ok"] is False and ev["instrument_adequate"] is False
    ic = _ic(red, on, off)
    assert {"record_id": "SYNTH-IS-ON", "outcome": "EXCLUDED"} in ic["capacity_point_outcomes"]
    r = _reasons(ic, "SYNTH-IS-ON")
    assert "statistical closure fails" in r and "also instrument adequacy" in r
    on, off = _pair(on_ie=0.2, off_ie=0.0, tag="IQ")
    on["capacity_monitoring"]["unintended_ground_path_found"] = True     # structural: excluded
    ic = _ic(red, on, off)
    assert {"record_id": "SYNTH-IQ-ON", "outcome": "EXCLUDED"} in ic["capacity_point_outcomes"]


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


# ------------------------------------------------------------------ A9.6 P1 workflow completion (fo_a9_6_p1_workflow_completion)
CAMPAIGN = os.path.join(DIR, "p1_campaign.py")
CLI = os.path.join(DIR, "p1_campaign_cli.py")
REPORT_SCHEMA_PATH = os.path.join(DIR, "p1_campaign_report_schema_v1.json")
A96 = os.path.join(ROOT, "docs", "decisions", "OD_2026_09_30_A9_6_implementation_first_directive.json")
T0 = "1999-12-31T00:00:00Z"          # synthetic fixture time stamps (not data)
T1 = "2000-01-01T00:00:00Z"
CRIT = {"criteria_id": "SYNTH-CRIT", "max_abs_drift_rel_I_e": 0.1, "max_abs_drift_rel_P_refl": 0.1,
        "max_step_over_std": 10.0, "min_duration_s": 10.0, "min_ignition_success_fraction": 0.5}
DOMAIN = {"domain_id": "SYNTH-DOM", "P_fwd_W": [0.0, 500.0], "p_chamber_Pa": [0.0, 1.0],
          "mdot_Ar_H1_mg_s": [0.0, 5.0], "V_collector_V": [-100.0, 100.0]}


@pytest.fixture(scope="module")
def camp():
    return _load_mod(CAMPAIGN, "p1_campaign_under_test")


def _optical(signal=1.0, threshold=0.1, mode="H_MODE", los=True, sat=False, elec=False):
    o = {"photodiode_channel_id": "SYNTH-PD-1", "optical_signal_V": signal, "photodiode_line_of_sight_ok": los,
         "photodiode_saturated": sat, "electrical_ignition_or_mode_transition": elec,
         "unlit_threshold": None if threshold is None else {"threshold_id": "SYNTH-THR", "threshold_V": threshold},
         "lit_mode_assignment": mode}
    if mode is not None:
        o["mode_indicator_basis"] = "SYNTH E/H indicators"
    if elec:
        o["electrical_indicator_basis"] = "SYNTH reflected power step"
    return o


def _hdr(kind, rid, stage, synthetic=True, ts=T1):
    return {"schema": "p1_bench_record_v1", "record_kind": kind, "record_id": rid, "run_id": "SYNTH-RUN-C",
            "stage_id": stage, "timestamp_utc": ts, "synthetic": synthetic,
            "labels": ["ENGINEERING_ONLY_NON_SCORING", "SYNTHETIC_TEST_FIXTURE"]}


def synth_readiness(red, synthetic=True):
    rec = _hdr("p1_g0_readiness", "SYNTH-G0", "P1-S0", synthetic, T0)
    rec.update({
        "interlocks": [{"interlock_id": i, "functional_test_done": True, "functional": True, "log_id": "SYNTH-LOG"}
                       for i in red.READINESS_INTERLOCK_IDS],
        "isolation_class": {"V_operating_max_V": 350.0, "V_design_withstand_V": 525.0},
        "dwv_tests": [{"path_id": "SYNTH-PATH-1", "applicable": True, "V_test_V": 1050.0, "duration_s": 60.0,
                       "current_limited": True, "leakage_A": 1e-8, "breakdown_or_flashover": False,
                       "leakage_acceptance": {"criterion_id": "SYNTH-LEAK", "max_leakage_A": 1e-6}},
                      {"path_id": "SYNTH-PATH-2", "applicable": False,
                       "not_applicable_reason": "SYNTH component rating below 1.05 kV"}],
        "gas_lines": [{"line_id": "SYNTH-GL-BRIDGE", "bridges_isolated_potentials": True, "isolator_installed": True,
                       "qualification": {"qualification_id": "SYNTH-Q", "level_id": "SYNTH-LEVEL", "V_test_V": 1000.0,
                                         "gas": "Ar", "p_Pa": 10.0, "breakdown_or_flashover": False}},
                      {"line_id": "SYNTH-GL-SAME", "bridges_isolated_potentials": False, "isolator_installed": False,
                       "qualification": None}],
        "ar_mfcs": [{"mfc_id": "SYNTH-MFC-1", "range_min_mg_s": 0.0, "range_max_mg_s": 5.0}],
        "ar_sweep_bounds_mg_s": [0.5, 3.0], "second_mfc_necessity": None,
        "generator_class": "GROUND_FACILITY_ONLY_MAINS",
        "registrations": {k: "SYNTH-" + k for k in red.READINESS_REGISTRATIONS}})
    return rec


def synth_cold(kind, rid, synthetic=True, p_cal=98.0):
    stage = "P1-S1" if kind == "DUMMY_LOAD" else "P1-S2"
    rec = _hdr("rf_cold_checkout", rid, stage, synthetic)
    rec.update({"checkout_kind": kind, "rf_pickup_check": "DONE",
                "rf": {"reference_plane": "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH", "P_fwd_W": 100.0, "P_refl_W": 1.0,
                       "match_setting_id": "SYNTH-MATCH-A"},
                "generator": {"generator_class": "GROUND_FACILITY_ONLY_MAINS", "P_generator_input_W": 200.0,
                              "input_boundary": "mains AC input of the lab generator", "instrument": "SYNTH-PA"},
                "loss_characterization": None})
    if kind == "DUMMY_LOAD":
        rec["calorimetric_cross_check"] = {"method_id": "SYNTH-CAL", "P_cal_W": p_cal, "u_P_cal_W": 1.0,
                                           "u_P_coupler_W": 1.0}
        rec["loss_characterization"] = {"characterization_id": "SYNTH-LOSS-A", "method": "TWO_PORT_S_PARAMETER",
                                        "match_setting_id": "SYNTH-MATCH-A", "value_W": 6.0, "u_value_W": 0.5,
                                        "valid_max_gamma_abs": 0.3}
    else:
        rec["rf"]["P_fwd_W"], rec["rf"]["P_refl_W"] = 10.0, 1.0
        rec.update({"optical": _optical(signal=0.01, threshold=None, mode=None), "gas_flow_state": "OFF",
                    "unlit_procedure_id": "SYNTH-UNLIT-PROC"})
    return rec


def synth_ign(rid, synthetic=True, ignited=True, optical=None):
    rec = _hdr("ignition_attempt", rid, "P1-S3", synthetic)
    rec.update({"gas": "Ar", "gas_mode": "G-REUSE", "hall_discharge_state": "OFF",
                "ignition_procedure_id": "SYNTH-IGN-PROC", "point_id": "SYNTH-IGN-PT-1",
                "rf": {"reference_plane": "GENERATOR_50OHM_SIDE_OF_LOCAL_MATCH", "P_fwd_W": 100.0, "P_refl_W": 4.0,
                       "match_setting_id": "SYNTH-MATCH-A"},
                "flows": {"mdot_Ar_H1_mg_s": 1.0, "mdot_icp_dedicated_mg_s": 0.0},
                "pressures": {"p_chamber_Pa": 0.01}, "ignited": ignited,
                "ignition_delay_s": 0.5 if ignited else None, "extinguished": False,
                "optical": optical if optical is not None else _optical(), "h1_magnet_state": "SYNTH-MAG-OFF"})
    return rec


def synth_dwell(rid, op_id, synthetic=True):
    rec = _hdr("stability_dwell", rid, "P1-S5", synthetic)
    rec.update({"operating_point_record_id": op_id, "ignition_point_id": "SYNTH-IGN-PT-1",
                "dwell": {"t_s": [0.0, 10.0, 20.0, 30.0], "I_e_A": [0.50, 0.51, 0.50, 0.51],
                          "P_refl_W": [4.0, 4.1, 4.0, 4.1]}})
    return rec


def synth_bundle(red, synthetic=True, **reg_over):
    """A complete SYNTHETIC campaign (fixture numbers, never data): G0, S1/S2, 3 ignitions, a surface record, one
    ICP45_CAPACITY RF-ON / RF-OFF pair, a Hall-ON consistency record at the same registered point, a dwell and the
    topology-control sequence."""
    surf = synth_op(synthetic=synthetic, timestamp_utc=T1)
    surf["rf"]["line_match_loss"]["source"] = "SYNTH-LOSS-A"
    on = synth_cap("SYNTH-CAP-ON", 3.0, synthetic=synthetic, stage="P1-S4")
    off = synth_cap("SYNTH-CAP-OFF", 0.2, rf_on=False, synthetic=synthetic, stage="P1-S4")
    for r in (on, off):
        r["rf"]["line_match_loss"]["source"] = "SYNTH-LOSS-A"
    s7 = synth_s7(red, "SYNTH-S7H-1", 1.5)
    s7["synthetic"] = synthetic
    seq = synth_seq(red)
    seq["synthetic"] = synthetic
    seq["timestamp_utc"] = T1
    recs = [synth_readiness(red, synthetic), synth_cold("DUMMY_LOAD", "SYNTH-S1-1", synthetic),
            synth_cold("INSTALLED_UNLIT_ANTENNA_VIA_LOCAL_MATCH", "SYNTH-S2-1", synthetic)]
    recs += [synth_ign("SYNTH-IGN-%d" % i, synthetic) for i in range(3)]
    recs += [surf, on, off, s7, synth_dwell("SYNTH-DWELL-1", surf["record_id"], synthetic), seq]
    reg = {"registration_set_id": "SYNTH-REGSET", "operating_domains": {
        st: dict(DOMAIN) for st in ("P1-S1", "P1-S2", "P1-S3", "P1-S4", "P1-S5", "P1-S6", "P1-S7", "P1-S7H")},
        "facility_pairs": [["SYNTH-CAP-ON", "SYNTH-CAP-OFF"]], "facility_match": dict(MATCH),
        "closure_rule": dict(CLOSE), "i_d_max_registration": dict(REG, I_d_max_H1_A=2.0), "margin_rule": dict(RULE),
        "stable_criteria": dict(CRIT)}
    reg.update(reg_over)
    return {"schema": "p1_campaign_bundle_v1",
            "manifest": {"campaign_id": "SYNTH-CAMPAIGN", "description": "synthetic fixture, not data",
                         "evidence_kind": "SYNTHETIC_TEST_ONLY" if synthetic else "MEASURED"},
            "registrations": reg, "records": recs}


def _measured_bundle(red, **reg_over):
    b = synth_bundle(red, synthetic=False, **reg_over)
    for r in b["records"]:
        r["synthetic"] = False
    return b


def _idx(rep):
    return {x["record_id"]: x for x in rep["raw_record_index"]}


def _outcome(rep, rid):
    return {o["record_id"]: o for o in rep["capacity"]["point_outcomes"]}[rid]


def _check_every_raw_record_kept(rep, bundle):
    assert rep["raw_records"] == bundle["records"]
    assert [x["record_id"] for x in rep["raw_record_index"]] == [r["record_id"] for r in bundle["records"]]
    for x in rep["raw_record_index"]:
        assert x["disposition"] in ("REDUCED", "OUT_OF_DOMAIN", "REFUSED_INVALID_RECORD")
        if x["disposition"] != "REDUCED":
            assert x["reasons"] and any(e["record_id"] == x["record_id"] and e["reasons"] == x["reasons"]
                                        for e in rep["excluded_records"])


def _no_pass_anywhere(obj):
    if isinstance(obj, dict):
        return all(_no_pass_anywhere(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_pass_anywhere(v) for v in obj)
    return not (isinstance(obj, str) and obj.strip().upper() == "PASS")


def test_a96_pinned_and_recorded(doc):
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json"] == \
        "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327"
    assert pins["docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"] == \
        "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634"
    inc = doc["a9_6_incorporation"]
    assert inc["follow_on"] == "fo_a9_6_p1_workflow_completion"
    assert inc["base_commit"] == "1d67f99f88007982eff77670b64c6eb7c595bccd"
    with open(A96, encoding="utf-8") as f:
        a96 = json.load(f)
    assert inc["fixed_statuses"] == a96["summary"]["fixed_statuses"]
    assert inc["lane_scope"] == a96["implementation_lanes"]["fo_a9_6_p1_workflow_completion"]
    assert all(g["state"].startswith("CLOSED_IN_IMPLEMENTATION") for g in inc["gap_audit"])
    assert "PASS" not in json.dumps(inc["fixed_statuses"])
    applied = {a["id"] for a in doc["owner_answers_applied"]}
    assert {"A9.6 sec. 2", "A9.6 sec. 5-7", "A9.6 sec. 8", "A9.6 sec. 14"} <= applied
    assert "PENDING docs/experiments/hall_icp/p3_coupled_thermal/" in " ".join(inc["not_done_here"])


def test_a96_workflow_stages_complete(doc, camp, red):
    """A9.6 sec. 8: every stage represented with entry / exit criteria, record template, required channels and a
    reducer that exists."""
    wf = doc["a9_6_incorporation"]["workflow"]
    assert [w["id"] for w in wf] == ["P1-W%02d" % i for i in range(1, 11)]
    names = " ".join(w["name"] for w in wf)
    for must in ("P1-G0", "RF cold checkout", "dummy load", "unlit antenna", "ignition", "electron-current surface",
                 "ICP-45 discharge-OFF capacity", "RF-OFF paired correction", "Kirchhoff", "stable-region",
                 "topology control", "NEUTRALIZATION_CONSISTENCY"):
        assert must in names, must
    meas = {m["id"] for m in doc["measurements"]}
    for w in wf:
        assert w["entry"] and w["exit"] and w["required_channels"] and w["record_template"]["required_fields"]
        assert set(w["required_channels"]) <= meas, w["id"]
        for fn in w["reducer"].replace(";", " ").split():
            if fn.startswith("p1_reducer."):
                assert callable(getattr(red, fn.split(".", 1)[1])), fn
    assert "never a gate" in " ".join(wf[8]["exit"]) and "after capacity" in wf[9]["name"]
    assert "1.05 kV DC / 60 s" in " ".join(wf[0]["exit"]) and "ICPQ-06" in " ".join(wf[0]["exit"])
    assert camp.WORKFLOW == wf


def test_a96_fail_closed_audit_has_one_test_per_bullet(doc):
    audit = doc["a9_6_incorporation"]["fail_closed_audit"]
    assert len(audit) == 10
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for a in audit:
        name = a["test"].split("::")[1]
        assert re.search(r"^def %s\(" % name, src, re.M), name
    bullets = " | ".join(a["a9_6_sec14_bullet"] for a in audit)
    for must in ("no PASS", "sign convention", "current path", "synthetic/measured", "RF-ON/RF-OFF",
                 "I_d,max,H1", "uncertainty", "UNCERTAIN", "line loss", "OUT_OF_DOMAIN"):
        assert must in bullets, must


def test_a96_derived_resolutions_and_open_questions(doc):
    inc = doc["a9_6_incorporation"]
    res = {r["id"]: r for r in inc["derived_resolutions"]}
    for k in ("P1Q-19 (ext)", "P1Q-19 (below propagation)", "P1Q-21", "P1Q-22", "P1Q-23 (a)", "P1Q-23 (b)"):
        assert res[k]["disposition"] == "DERIVED" and res[k]["follows_from"], k
    assert res["P1Q-19 (require vs use larger)"]["disposition"] == "TBD_OWNER"
    assert "JCGM 100:2008 5.1.2" in res["P1Q-23 (a)"]["follows_from"]
    assert "5.2.2" in res["P1Q-23 (b)"]["follows_from"] and "F.2.2.1" in res["P1Q-19 (ext)"]["follows_from"]
    assert "A9_5_p1_closure_owner_decisions.json" in res["P1Q-21"]["follows_from"]
    g = inc["external_reference"]
    assert g["url"].startswith("https://www.bipm.org/") and len(g["fetched_pdf_sha256"]) == 64
    qs = {q["id"]: q for q in doc["open_owner_questions"]}
    assert "P1Q-19" in qs and qs["P1Q-19"]["status"] == "TBD_OWNER"
    assert not ({"P1Q-21", "P1Q-22", "P1Q-23"} & set(qs))
    items = {i["id"]: i for i in doc["items"]}
    assert items["P1-IT-57"]["value"].startswith("TBD_OWNER") and items["P1-IT-52"]["value"].startswith("TBD")


def test_a96_schemas_cover_all_kinds_and_report(red, camp):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    assert [x["$ref"].split("/")[-1] for x in sc["oneOf"]] == list(red.RECORD_KINDS)
    for k in red.RECORD_KINDS:
        assert k in sc["$defs"], k
    assert sc["$defs"]["p1_g0_readiness"]["x-owner-values"]["dwv_V_test_V_min"] == 1050.0
    with open(REPORT_SCHEMA_PATH, encoding="utf-8") as f:
        rs = json.load(f)
    assert rs["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert _structural_metaschema_errors(rs) == [] and _structural_metaschema_errors(sc) == []
    assert rs["required"] == list(camp.REPORT_REQUIRED)
    assert rs["properties"]["capacity"]["properties"]["point_outcomes"]["items"]["properties"]["outcome"]["enum"] == \
        list(red.POINT_OUTCOMES)
    assert "PASS" not in json.dumps(rs["properties"]["icp45_status"])
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.Draft202012Validator.check_schema(rs)
    jsonschema.Draft202012Validator.check_schema(sc)


def test_a96_campaign_complete_synthetic(red, camp):
    b = synth_bundle(red)
    rep = camp.run_campaign(b)
    _check_every_raw_record_kept(rep, b)
    assert all(x["disposition"] == "REDUCED" for x in rep["raw_record_index"]), rep["raw_record_index"]
    assert rep["readiness"]["g0_status"] == "G0_ENTRY_CONDITIONS_RECORDED"
    assert rep["rf_cold_checkout"]["rf_chain_status"] == "CROSS_CHECK_AGREES"
    assert rep["rf_cold_checkout"]["verified_loss_ids"] == ["SYNTH-LOSS-A"]
    assert rep["rf_cold_checkout"]["cross_checks"][0]["z_x"] == pytest.approx(1.0 / math.sqrt(2.0))
    assert rep["rf_cold_checkout"]["antenna_records"][0]["plasma_state"] == "UNCERTAIN"
    assert rep["ignition_map"]["points"][0]["ignition_success_fraction"] == 1.0
    assert _outcome(rep, "SYNTH-CAP-ON")["outcome"] == "CLOSURE_VALID_CANDIDATE"
    assert rep["icp45_status"]["status"] == "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
    assert rep["capacity"]["icp45a"]["I_e_cap_A"] == pytest.approx(2.8)
    assert rep["neutralization_consistency"][0]["row_status"] == "DESCRIPTIVE_CONSISTENCY_CHECK_NOT_A_GATE"
    assert rep["stable_region"]["status"] == "REGION_OF_TESTED_POINTS_WITHIN_OWNER_CRITERIA"
    assert rep["stable_region"]["envelope_of_tested_points"]["P_fwd_W"] == [100.0, 100.0]
    assert rep["topology_control"][0]["gate"] is False and rep["topology_control"][0]["scoring"] is False
    row = {r["record_id"]: r for r in rep["surface"]}["SYNTH-OP-001"]
    assert row["factors"]["P_delivered_kind"] == "P_RF_DELIVERED" and row["plasma_state"] == "OPTICAL_NOT_RECORDED"
    assert _no_pass_anywhere({k: v for k, v in rep.items() if k != "raw_records"})
    assert rep["evidence_class"] == "ENGINEERING_ONLY_NON_SCORING"
    assert json.dumps(camp.run_campaign(copy.deepcopy(b)), sort_keys=True) == json.dumps(rep, sort_keys=True)
    try:
        import jsonschema
    except ImportError:
        return
    with open(REPORT_SCHEMA_PATH, encoding="utf-8") as f:
        jsonschema.Draft202012Validator(json.load(f)).validate(rep)


def test_a96_campaign_measured_evaluates_engineering_only(red, camp):
    rep = camp.run_campaign(_measured_bundle(red))
    assert rep["icp45_status"]["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert rep["icp45_status"]["condition_met"] is True
    assert rep["icp45_status"]["m16_state"].startswith("PENDING_ICP45")
    assert rep["any_synthetic"] is False


def test_a96_cli_directory_and_bundle(red, tmp_path):
    cli = _load_mod(CLI, "p1_campaign_cli_under_test")
    b = synth_bundle(red)
    bf = tmp_path / "bundle.json"
    bf.write_text(json.dumps(b), encoding="utf-8")
    out1 = tmp_path / "r1.json"
    assert cli.main([str(bf), "--out", str(out1)]) == 0
    d = tmp_path / "camp"
    (d / "records").mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps(b["manifest"]), encoding="utf-8")
    (d / "registrations.json").write_text(json.dumps(b["registrations"]), encoding="utf-8")
    for i, r in enumerate(b["records"]):
        (d / "records" / ("%03d.json" % i)).write_text(json.dumps(r), encoding="utf-8")
    out2 = tmp_path / "r2.json"
    assert cli.main([str(d), "--out", str(out2)]) == 0
    assert json.loads(out1.read_text()) == json.loads(out2.read_text())
    bad = copy.deepcopy(b)
    bad["records"][5]["synthetic"] = False
    bf.write_text(json.dumps(bad), encoding="utf-8")
    assert cli.main([str(bf), "--out", str(tmp_path / "r3.json")]) == 2
    assert not (tmp_path / "r3.json").exists()


# --- A9.6 sec. 14, one explicit test per bullet (names cited in a9_6_incorporation.fail_closed_audit)
def test_a96_sec14_missing_required_data_no_pass(red, camp):
    b = synth_bundle(red)
    del b["records"][7]["capacity_monitoring"]["V_icp_body_V"]               # SYNTH-CAP-ON loses a required field
    del b["records"][3]["optical"]                                           # an ignition record without its optics
    rep = camp.run_campaign(b)
    _check_every_raw_record_kept(rep, b)
    ix = _idx(rep)
    assert ix["SYNTH-CAP-ON"]["disposition"] == "REFUSED_INVALID_RECORD"
    assert "capacity_monitoring.V_icp_body_V missing" in ix["SYNTH-CAP-ON"]["reasons"][0]
    assert ix["SYNTH-IGN-0"]["disposition"] == "REFUSED_INVALID_RECORD"
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED"
    assert _no_pass_anywhere({k: v for k, v in rep.items() if k != "raw_records"})
    # missing registrations -> NOT_EVALUATED, never a default
    rep = camp.run_campaign(synth_bundle(red, stable_criteria=None, closure_rule=None))
    assert rep["stable_region"]["status"] == "NOT_EVALUATED"
    assert _outcome(rep, "SYNTH-CAP-ON")["outcome"] == "EXCLUDED"
    assert "Kirchhoff closure rule not registered" in " ".join(_outcome(rep, "SYNTH-CAP-ON")["reasons"])
    bb = synth_bundle(red)
    del bb["registrations"]["margin_rule"]
    with pytest.raises(camp.CampaignInputError):
        camp.run_campaign(bb)
    # the self-check refuses a PASS anywhere in a report
    with pytest.raises(camp.red.P1RecordError):
        camp._walk_no_pass({"x": [{"y": "PASS"}]})


def test_a96_sec14_sign_convention_mismatch_excluded(red, camp):
    b = synth_bundle(red)
    b["records"][8]["terminals"]["h1_body"]["sign_convention_id"] = "SYNTH-OTHER"   # RF-OFF partner channel
    rep = camp.run_campaign(b)
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "EXCLUDED" and "sign conventions differ" in " ".join(o["reasons"])
    assert any(e["record_id"] == "SYNTH-CAP-ON" and e["outcome"] == "EXCLUDED" for e in rep["excluded_records"])
    b = synth_bundle(red)
    b["records"][7]["collector"]["I_e_sign_convention"] = "ELECTRON_FLOW_POSITIVE"
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-CAP-ON"]["disposition"] == "REFUSED_INVALID_RECORD"
    assert "I_e_sign_convention" in _idx(rep)["SYNTH-CAP-ON"]["reasons"][0]


def test_a96_sec14_missing_current_path_excluded(red, camp):
    b = synth_bundle(red)
    b["records"][7]["terminals"]["facility_ground"] = {"I_A": None, "basis": "NOT_MEASURED"}
    rep = camp.run_campaign(b)
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "EXCLUDED" and "intentional return path unmeasured" in " ".join(o["reasons"])
    b = synth_bundle(red)
    del b["records"][7]["terminals"]["h1_body"]                             # absent, not even declared
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-CAP-ON"]["disposition"] == "REFUSED_INVALID_RECORD"
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED"


def test_a96_sec14_mixed_evidence_refused(red, camp):
    b = synth_bundle(red)
    b["records"][9]["synthetic"] = False
    with pytest.raises(camp.MixedEvidenceError):
        camp.run_campaign(b)
    b = _measured_bundle(red)
    b["records"][0]["synthetic"] = True
    with pytest.raises(camp.MixedEvidenceError):
        camp.run_campaign(b)


def test_a96_sec14_invalid_pair_excluded(red, camp):
    b = synth_bundle(red)
    b["records"][8]["collector"]["V_collector_V"] = -35.0                    # RF-OFF not at the same bias
    rep = camp.run_campaign(b)
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "EXCLUDED" and "pairing not matched" in " ".join(o["reasons"])
    assert "collector.V_collector_V differs" in " ".join(o["reasons"])
    rep = camp.run_campaign(synth_bundle(red, facility_match=None))
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "EXCLUDED" and "pressure-match rule not registered" in " ".join(o["reasons"])
    b = synth_bundle(red)
    b["records"][8]["rf"]["P_refl_W"] = 1.0                                 # RF-OFF record physically impossible
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-CAP-OFF"]["disposition"] == "REFUSED_INVALID_RECORD"
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "EXCLUDED" and "paired RF-OFF record 'SYNTH-CAP-OFF' is REFUSED_INVALID_RECORD" in \
        " ".join(o["reasons"])
    b = synth_bundle(red)
    b["registrations"]["facility_pairs"] = [["SYNTH-CAP-ON", "SYNTH-NOT-THERE"]]
    with pytest.raises(camp.CampaignInputError):
        camp.run_campaign(b)


def test_a96_sec14_unknown_i_d_max_not_evaluated(red, camp):
    rep = camp.run_campaign(synth_bundle(red, i_d_max_registration=None))
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED" and rep["icp45_status"]["condition_met"] is None
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "NOT_EVALUATED_REGISTRATION" and o["closure"]["closure_valid"] is True
    assert rep["neutralization_consistency"][0]["row_status"] == "OUT_OF_DOMAIN"
    rep = camp.run_campaign(synth_bundle(red, margin_rule=None))
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED" and "margin rule not registered" in \
        rep["icp45_status"]["reason"]
    assert _outcome(rep, "SYNTH-CAP-ON")["outcome"] == "CLOSURE_VALID_CANDIDATE"
    reg = dict(REG, I_d_max_H1_A=8.33, basis="STAND_CEILING")               # the bench ceiling is never I_d,max,H1
    with pytest.raises(camp.red.RegistrationError):
        camp.run_campaign(synth_bundle(red, i_d_max_registration=reg))


def test_a96_sec14_missing_uncertainty_not_evaluated(red, camp):
    b = synth_bundle(red)
    del b["records"][7]["terminals"]["electron_collector"]["uncertainty"]["u_zero_offset_A"]
    rep = camp.run_campaign(b)
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "NOT_EVALUATED_UNCERTAINTY" and "u(I_k) unavailable" in " ".join(o["reasons"])
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED"
    for k in ("u_I_e_A", "u_I_d_max_A"):
        rep = camp.run_campaign(synth_bundle(red, margin_rule=dict(RULE, **{k: 0.0})))
        assert rep["icp45_status"]["status"] == "NOT_EVALUATED" and "F.2.2.1" in rep["icp45_status"]["reason"]
    b = synth_bundle(red)
    b["records"][1]["calorimetric_cross_check"]["u_P_cal_W"] = 0.0         # zero is not an uncertainty
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-S1-1"]["disposition"] == "REFUSED_INVALID_RECORD"
    assert rep["rf_cold_checkout"]["rf_chain_status"] == "NOT_EVALUATED"


def test_a96_sec14_unresolved_plasma_state_uncertain(red, camp):
    for kw, why in (({"los": False}, "line of sight"), ({"sat": True}, "saturated"),
                    ({"threshold": None}, "no registered unlit threshold"),
                    ({"signal": 0.01, "elec": True, "mode": None}, "electrical evidence"),
                    ({"mode": None}, "no registered E_MODE / H_MODE")):
        st, reason = red.classify_plasma_state(_optical(**kw))
        assert st == "UNCERTAIN" and why in reason, kw
    assert red.classify_plasma_state(_optical(signal=0.01, mode=None))[0] == "UNLIT"
    assert red.classify_plasma_state(_optical())[0] == "H_MODE"
    bad = _optical()
    del bad["unlit_threshold"]
    with pytest.raises(red.MissingInputError):
        red.classify_plasma_state(bad)
    b = synth_bundle(red)
    b["records"][6]["optical"] = _optical(threshold=None)                   # surface record with an optical record
    b["records"][4]["optical"] = _optical(sat=True)
    rep = camp.run_campaign(b)
    row = {r["record_id"]: r for r in rep["surface"]}["SYNTH-OP-001"]
    assert row["plasma_state"] == "UNCERTAIN"
    att = {a["record_id"]: a for a in rep["ignition_map"]["attempts"]}
    assert att["SYNTH-IGN-1"]["plasma_state"] == "UNCERTAIN" and att["SYNTH-IGN-1"]["ignited"] is True
    b = synth_bundle(red)
    b["records"][4]["optical"] = _optical(signal=0.01, mode=None)          # recorded ignition, optically unlit
    rep = camp.run_campaign(b)
    att = {a["record_id"]: a for a in rep["ignition_map"]["attempts"]}
    assert att["SYNTH-IGN-1"]["flag"].startswith("IGNITION_INDICATORS_DISAGREE")


def test_a96_sec14_unverified_loss_no_reconstructed_power(red, camp):
    b = synth_bundle(red)
    b["records"][6]["rf"]["line_match_loss"]["source"] = "SYNTH-UNKNOWN-CHAR"
    rep = camp.run_campaign(b)
    row = {r["record_id"]: r for r in rep["surface"]}["SYNTH-OP-001"]
    assert row["factors"]["P_delivered_kind"] == "P_RF_DELIVERED_UPPER_BOUND_LOSS_UNVERIFIED"
    assert row["factors"]["P_delivered_W"] == pytest.approx(100.0 - 4.0) and row["C_e_kind"] == "C_e_UPPER_BOUND"
    assert any(f.startswith("LINE_MATCH_LOSS_UNVERIFIED") for f in row["flags"])
    b = synth_bundle(red)
    b["records"][1]["calorimetric_cross_check"]["P_cal_W"] = 90.0          # |z_x| = 9 / sqrt(2) > 2
    rep = camp.run_campaign(b)
    assert rep["rf_cold_checkout"]["rf_chain_status"] == "EXCLUDED_INSTRUMENT"
    assert rep["rf_cold_checkout"]["verified_loss_ids"] == []
    row = {r["record_id"]: r for r in rep["surface"]}["SYNTH-OP-001"]
    assert row["factors"]["P_delivered_W"] is None and row["C_e_W_per_A"] is None
    assert row["factors"]["P_delivered_kind"] == "EXCLUDED_INSTRUMENT_RF_CROSS_CHECK"
    b = synth_bundle(red)
    b["records"] = [r for r in b["records"] if r["record_id"] != "SYNTH-S1-1"]   # no cross-check at all
    rep = camp.run_campaign(b)
    assert rep["rf_cold_checkout"]["rf_chain_status"] == "NOT_EVALUATED"
    row = {r["record_id"]: r for r in rep["surface"]}["SYNTH-OP-001"]
    assert row["factors"]["P_delivered_kind"] == "P_RF_DELIVERED_UPPER_BOUND_LOSS_UNVERIFIED"
    assert "P_plasma" not in json.dumps(rep["surface"]).replace("never P_plasma", "")


def test_a96_sec14_out_of_domain_not_fail(red, camp):
    b = synth_bundle(red)
    b["registrations"]["operating_domains"]["P1-S4"]["P_fwd_W"] = [0.0, 50.0]   # capacity RF-ON at 100 W outside
    rep = camp.run_campaign(b)
    ix = _idx(rep)
    assert ix["SYNTH-CAP-ON"]["disposition"] == "OUT_OF_DOMAIN" and ix["SYNTH-CAP-OFF"]["disposition"] == "REDUCED"
    o = _outcome(rep, "SYNTH-CAP-ON")
    assert o["outcome"] == "OUT_OF_DOMAIN" and "outside registered operating domain" in " ".join(o["reasons"])
    assert rep["icp45_status"]["status"] == "NOT_EVALUATED" and rep["icp45_status"]["condition_met"] is None
    vals = re.findall(r'": "([A-Z_]+)"', json.dumps({k: v for k, v in rep.items() if k != "raw_records"}))
    assert vals and not [v for v in vals if v == "FAIL" or v.startswith("FAIL_")]     # no FAIL-valued field
    b = synth_bundle(red)
    b["registrations"]["operating_domains"]["P1-S4"]["P_fwd_W"] = [0.0, 50.0]
    b["registrations"]["operating_domains"]["P1-S4"]["V_collector_V"] = [0.0, 100.0]  # RF-OFF partner outside too
    rep = camp.run_campaign(b)
    assert _idx(rep)["SYNTH-CAP-OFF"]["disposition"] == "OUT_OF_DOMAIN"
    b = synth_bundle(red)
    del b["registrations"]["operating_domains"]["P1-S3"]                     # unregistered stage
    rep = camp.run_campaign(b)
    assert all(_idx(rep)["SYNTH-IGN-%d" % i]["disposition"] == "OUT_OF_DOMAIN" for i in range(3))
    b = synth_bundle(red)
    b["records"][0]["dwv_tests"][0]["leakage_acceptance"] = None             # G0 TBD -> later stages out of domain
    rep = camp.run_campaign(b)
    assert rep["readiness"]["g0_status"] == "G0_NOT_EVALUATED_TBD"
    assert all(x["disposition"] == "OUT_OF_DOMAIN" for x in rep["raw_record_index"] if x["stage_id"] != "P1-S0")
    _check_every_raw_record_kept(rep, b)
    b = synth_bundle(red)
    b["records"][6]["timestamp_utc"] = "1998-01-01T00:00:00Z"                 # taken before P1-G0
    rep = camp.run_campaign(b)
    assert "before the governing P1-G0" in " ".join(_idx(rep)["SYNTH-OP-001"]["reasons"])


def test_a96_readiness_rules(red):
    ok = red.reduce_readiness(synth_readiness(red))
    assert ok["g0_status"] == "G0_ENTRY_CONDITIONS_RECORDED" and not ok["deficiencies"] and not ok["tbd"]
    gl = {g["line_id"]: g for g in ok["rows"]["gas_lines"]}
    assert gl["SYNTH-GL-SAME"]["isolator_required"] is False and gl["SYNTH-GL-BRIDGE"]["isolator_required"] is True
    for mut, frag in ((lambda r: r["dwv_tests"][0].update(V_test_V=1000.0), "V_test 1000.0 V < 1.05 kV"),
                      (lambda r: r["dwv_tests"][0].update(duration_s=30.0), "< 60 s"),
                      (lambda r: r["dwv_tests"][0].update(current_limited=False), "not current-limited"),
                      (lambda r: r["gas_lines"][0].update(qualification=None), "no ~1 kV representative-gas"),
                      (lambda r: r["gas_lines"][0].update(isolator_installed=False), "without a gas isolator"),
                      (lambda r: r["interlocks"].pop(), "P1-SI-11"),
                      (lambda r: r["isolation_class"].update(V_design_withstand_V=500.0), ">= 525 V"),
                      (lambda r: r.update(ar_mfcs=[{"mfc_id": "A", "range_min_mg_s": 0.0, "range_max_mg_s": 1.0},
                                                   {"mfc_id": "B", "range_min_mg_s": 2.0, "range_max_mg_s": 5.0}]),
                       "do not overlap"),
                      (lambda r: r.update(ar_mfcs=[{"mfc_id": x, "range_min_mg_s": 0.0, "range_max_mg_s": 5.0}
                                                   for x in "ABCD"]), "no four-range set"),
                      (lambda r: r.update(generator_class="FLIGHT_REPRESENTATIVE_DC_RF_SOURCE"), "GROUND/FACILITY")):
        rec = synth_readiness(red)
        mut(rec)
        out = red.reduce_readiness(rec)
        assert out["g0_status"] == "G0_NOT_MET" and frag in " ".join(out["deficiencies"]), frag
    rec = synth_readiness(red)
    rec["ar_sweep_bounds_mg_s"] = None
    assert red.reduce_readiness(rec)["g0_status"] == "G0_NOT_EVALUATED_TBD"
    rec = synth_readiness(red)
    rec["dwv_tests"][1].pop("not_applicable_reason")
    with pytest.raises(red.MissingInputError):
        red.reduce_readiness(rec)
    rec = synth_readiness(red)
    rec["P_bus_W"] = 1.0
    with pytest.raises(red.PMainsNotPBusError):
        red.reduce_readiness(rec)


def test_a96_magnitude_form_of_denominator(red):
    """A9.6 sec. 2: max(|I_e,collector|, I_scale,min) and 3 u_R <= 0.02 |I_e,collector| (signed collector current)."""
    on, off = _pair(on_ie=-0.5, off_ie=0.0, tag="NEG")                    # I_e,collector = -0.5 A (net ion collection)
    ev = red.kirchhoff_closure(on, CLOSE)
    assert ev["I_e_collector_A"] == pytest.approx(-0.5) and ev["denominator_A"] == pytest.approx(0.5)
    assert ev["instrument_adequate"] is True and "|I_e,collector|" in ev["denominator_form"]


def test_a96_p1q19_alternatives_side_by_side(red):
    on, off = _pair(tag="Q19")
    ic = _ic(red, on, off)
    alts = ic["p1q19_alternatives"]
    assert alts["agree"] is True and ic["status"] == "EVALUATED_ENGINEERING_ONLY"
    assert alts["REQUIRE_REGISTERED_GE_CHANNEL"] == alts["USE_LARGER_OF_REGISTERED_AND_CHANNEL"]
    ic = _ic(red, on, off, margin=dict(RULE, u_I_e_A=1e-4))
    alts = ic["p1q19_alternatives"]
    assert alts["agree"] is False and ic["status"] == "NOT_EVALUATED" and "TBD_OWNER P1Q-19" in ic["reason"]
    assert alts["REQUIRE_REGISTERED_GE_CHANNEL"]["status"] == "NOT_EVALUATED"
    assert alts["USE_LARGER_OF_REGISTERED_AND_CHANNEL"]["u_I_e_cap_A"] == pytest.approx(math.sqrt(2.0) * U1)
    assert "M_n" not in ic


def test_a96_p1q23_correlated_form(red):
    u, basis = red.u_i_e_cap_channels(3e-3, 4e-3)
    assert u == pytest.approx(5e-3) and basis.startswith("ASSUMPTION_INDEPENDENT")
    u, basis = red.u_i_e_cap_channels(3e-3, 4e-3, {"correlation_id": "SYNTH-R", "r": 0.5})
    assert u == pytest.approx(math.sqrt(9e-6 + 16e-6 - 12e-6)) and "REGISTERED_CORRELATION SYNTH-R" in basis
    on, off = _pair(tag="Q23")
    ic = _ic(red, on, off, margin=dict(RULE, rf_on_off_collector_correlation={"correlation_id": "SYNTH-R", "r": 1.0}))
    assert ic["u_I_e_cap_from_channels_A"] == pytest.approx(0.0, abs=1e-12)
    assert "REGISTERED_CORRELATION" in ic["u_I_e_cap_from_channels_basis"]
    with pytest.raises(red.RegistrationError):
        _ic(red, on, off, margin=dict(RULE, rf_on_off_collector_correlation={"correlation_id": "X", "r": 1.5}))


def test_a96_campaign_code_hygiene():
    for path in (CAMPAIGN, CLI):
        src = open(path, encoding="utf-8").read()
        assert ("xe" + "_ledger") not in src
        for banned in ("archengine", "plasma_devices", "hall_map", "requests", "urllib"):
            assert banned not in src, (path, banned)
    src = open(CAMPAIGN, encoding="utf-8").read()
    imports = set(re.findall(r"^(?:import|from) (\S+)", src, re.M))
    assert imports <= {"copy", "hashlib", "importlib.util", "json", "os"}, imports
    assert "open(" not in src
