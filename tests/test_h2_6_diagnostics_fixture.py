"""Tests for the H2-6 diagnostics + H-1 fixture deliverable (fo_h2_6_diagnostics_fixture, owner addendum A7).

Pure file checks plus the deterministic builder; no network, no Julia, fast.
"""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(ROOT, "docs", "hardware", "h2", "h2_6_diagnostics_fixture")
BUILDER = os.path.join(LANE, "build_h2_6_diagnostics_fixture.py")
JSON_PATH = os.path.join(LANE, "h2_6_diagnostics_fixture_v1.json")
MD_PATH = os.path.join(LANE, "H2_6_DIAGNOSTICS_FIXTURE.md")

EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
BASES = {"requirement", "allocation", "analog", "derived", "assumed", "pending"}
CLASSES = {"FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"}
ARCHS = ["hall_only", "rf_hall", "ecr_hall"]
CI_IDS = {"H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR", "DIV-1"}
PLANES = {"IP-UP", "IP-DN", "HALL_INLET_Z0"}


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_h2_6_diagnostics_fixture", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def b():
    return _load_builder()


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _rj(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def test_outputs_reproduce_exactly(b):
    assert b.check() == []


def test_pins_hold(b):
    assert b.verify_pins() == []


def test_consumed_values_match_live_sources(b):
    assert b.verify_sources() == []


def test_governance_files_never_pinned(b, doc):
    pinned = {p["path"] for p in doc["authority_pins"] + doc["deliverable_pins"]}
    for g in b.GOVERNANCE_NOT_PINNED:
        assert g not in pinned
    for p in pinned:
        assert "orchestration" not in p


def test_owner_decisions_a5_a6_a7_pinned(doc):
    pins = {p["path"]: p["sha256"] for p in doc["authority_pins"]}
    assert pins["docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"] == \
        "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"
    assert pins["docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"] == \
        "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"
    assert pins["docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"] == \
        "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925"
    assert "docs/decisions/verification/A5_BASELINE_VERIFICATION.json" in pins


def test_required_sections_present(doc):
    for k in ("design_parameters", "interface_demands", "hard_incompatibility_check",
              "architecture_changing_blockers_touched", "m16_rows", "h3_procurement_inputs", "h4_test_inputs",
              "milestones", "measurement_map", "fixture", "facility", "ground_vs_flight"):
        assert doc.get(k), k
    assert set(doc["milestones"]) >= {"A", "B", "C"}
    assert doc["architectures"] == ARCHS


def test_design_parameter_table_fields(doc):
    ids = [p["id"] for p in doc["design_parameters"]]
    assert len(ids) == len(set(ids))
    for p in doc["design_parameters"]:
        assert re.fullmatch(r"H26-\d\d", p["id"]), p["id"]
        assert p["basis"] in BASES, p
        assert p["evidence_class"] in EVIDENCE, p
        assert p["flight_classification"] in CLASSES, p
        assert p["source"], p
        st = p["status"]
        assert st == "PRELIMINARY" or st.startswith("PENDING ") or st.startswith("TBD - requires") \
            or st.startswith("UNFROZEN") or st.startswith("consumed by"), (p["id"], st)
        if p["value"] is None:
            assert not st.startswith("PRELIMINARY"), p["id"]
        for ci in p["applies_to"]:
            assert ci in CI_IDS | {"H-1 mount"}, ci


def test_pending_markers_name_real_lane_paths(b, doc):
    paths = {path for _l, path, _w in b.PENDING_LANES}
    txt = json.dumps(doc)
    for m in re.findall(r"PENDING (docs/[A-Za-z0-9_/.-]+/)", txt):
        assert m in paths, m
    # the verified A6 lanes are consumed, not pending
    assert "PENDING docs/experiments/phase1_prereg_framework" not in txt
    assert "PENDING docs/budgets/xe_ledger" not in txt


def test_no_dependency_on_parallel_lanes(b):
    for row in b.pending_status():
        assert row["state"] in ("PRESENT_NOT_CONSUMED", "MISSING_IN_CHECKOUT")
    src = open(BUILDER, encoding="utf-8").read()
    for _l, path, _w in b.PENDING_LANES:
        assert f'_load(root, "{path}' not in src


def test_every_p1dq_measurement_chain_is_covered(b):
    assert b.p1dq_coverage() == []


def test_measurement_rows_have_roles_and_stages(doc):
    fw = _rj("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json")
    fw_ids = {q["id"] for q in fw["decision_quantities"]}
    for m in doc["measurement_map"]:
        for q in m["phase1_decision_quantities"]:
            assert q in fw_ids
            assert q in m["role"]
        assert m["flight_classification"] in CLASSES
        stages = {q["stage"] for q in m["qualification"]}
        assert "S1a" in stages, m["id"]


def test_referenced_ids_exist_in_their_registers(doc):
    txt = json.dumps(doc)
    w3 = _rj("docs/experiments/hardware/hardware_requirements_v1.json")
    w4 = _rj("docs/experiments/hardware/snapshots/w4_instrumentation_definition_v1_at_fe2c05e.json")
    ms = _rj("docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json")
    cd = _rj("docs/experiments/capability_demo/capability_demo_prep_v1.json")
    s1a = _rj("docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json")
    s1 = _rj("docs/experiments/s1_readiness/s1_readiness_conditions_v1.json")
    hw = {r["id"] for r in w3["requirements"]}
    ins = {i["id"] for i in w4["instruments"]} | {p["id"] for p in w4["procedures"]}
    msi = {x["id"] for x in ms["general_requirements"]} | {x["id"] for x in ms["measurands"]}
    cdi = {x["id"] for x in cd["demonstrations"]} | {x["id"] for x in cd["proposed_thresholds"]}
    hwq = {q["id"] for q in w3["owner_questions"]}
    gates = {c["id"] for c in s1a["conditions"]} | {c["id"] for c in s1["conditions"]}
    for pat, known in ((r"HW-[A-Z0-9]+-\d\d", hw), (r"INS-(?:P-)?\d\d", ins), (r"MS-[GM]-\d\d", msi),
                       (r"CD-P-[A-Z0-9-]+|CD-\d\d", cdi), (r"HWQ-\d\d", hwq), (r"S1A?-(?:C\d|FW)", gates)):
        missing = sorted(set(re.findall(pat, txt)) - known)
        assert not missing, (pat, missing)
    for ci in doc["configuration_items_used"]:
        assert ci in {c["id"] for c in w3["configuration_items"]}
    for pl in doc["interface_planes_used"]:
        assert pl in {p["id"] for p in w3["interface_planes"]}


def test_firewall_classes_are_s1a_allowed_or_registration(doc):
    s1a = _rj("docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json")
    fw = s1a["firewall_reference_classes"]
    allowed = set(fw["allowed"]) | {"REG-GEOM", "REG-BZ", "REG-FEED", "REG-PB"}
    for m in doc["measurement_map"]:
        for q in m["qualification"]:
            if q["stage"] == "S1a" and "s1a_data_class" in q:
                bare = re.sub(r"\([^)]*\)", "", q["s1a_data_class"])
                toks = re.findall(r"\b[A-Z][A-Z_]+(?:-[A-Z]+)?\b", bare)
                assert toks, m["id"]
                for tok in toks:
                    assert tok in allowed, (m["id"], tok)


def test_interface_demands_structure(doc):
    for d in doc["interface_demands"]:
        assert set(d) >= {"from", "to", "quantity", "value", "units", "status"}
        assert "fo_h2_6_diagnostics_fixture" in (d["from"], d["to"])


def test_m16_rows_scheduler_rules(doc):
    a7 = _rj("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json")
    states = set(a7["m16_as_scheduler"]["execution_states"])
    rollups = set(a7["m16_as_scheduler"]["rollup_categories"])
    a5 = _rj("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json")
    names = set()
    for grp in ("atmospheric_branch", "xe_branch", "propulsion", "support"):
        names |= set(a5["architecture"][grp])
    assert len(names) == a5["architecture"]["baseline_subsystem_count"] == 16
    for r in doc["m16_rows"]:
        assert r["proposed_state"] in states
        if r["proposed_state"] == "BLOCKED":
            assert isinstance(r["blocking_item"], str) and r["blocking_item"]
            assert r["rollup_category"] in rollups
        else:
            assert r["blocking_item"] is None
        assert r["subsystem"] in names or r["subsystem"].startswith("RF pre-ionization module interface")


def test_blockers_touched_are_a7_blockers(doc):
    for x in doc["architecture_changing_blockers_touched"]:
        assert x["blocker"] in (1, 2, 3)


def test_hard_incompatibility_check_states_what_was_checked(doc):
    h = doc["hard_incompatibility_check"]
    assert h["verdict"] == "none found"
    assert len(h["what_was_checked"]) >= 5
    assert h["evidence_class_of_this_finding"]


def test_no_prediction_no_winner_no_forbidden_sources(doc):
    txt = json.dumps(doc).lower()
    for bad in ("sgb-screen-0", "winner", "recommended architecture", "selected architecture"):
        assert bad not in txt, bad
    # forbidden performance sources may only be named in the not_used / compliance statements
    src = open(BUILDER, encoding="utf-8").read()
    assert "import abep_sim" not in src and "from abep_sim" not in src
    assert "plasma_devices" not in json.dumps(doc["design_parameters"])
    assert "NO_BASELINE_YET" in json.dumps(doc)


def test_thrust_span_covers_rfp_band(doc):
    d = doc["derived"]
    assert d["thrust_span_upper_mN_planning"]["value"] > 25.0
    assert abs(d["thrust_span_upper_mN_planning"]["value"] - 25.0 / (1 - 1.64485 * 0.01)) < 1e-6


def test_pumping_speed_derivation(b, doc):
    # S = (mdot / m) k T / p ; independent recomputation for N2 3.14236 mg/s + Xe 0.15 mg/s at 1e-5 Torr
    kB, amu, T = 1.380649e-23, 1.66053906660e-27, 300.0
    q = (3.14236387222e-06 / (28.0 * amu) + 0.15e-6 / (131.3 * amu)) * kB * T
    s = q / (1e-5 * 101325.0 / 760.0) * 1e3
    got = doc["derived"]["S_eff_required"]["total_N2_mdot_max_plus_Xe_upper"]["1.0e-05 Torr"]["value"]
    assert abs(got - s) / s < 1e-9


def test_derive_refuses_missing_input(b):
    inputs = dict(b.INPUTS)
    inputs.pop("T_gas_K")
    with pytest.raises(KeyError):
        b.derive(inputs)
    inputs = dict(b.INPUTS)
    inputs["p_b_planning_Torr"] = dict(inputs["p_b_planning_Torr"], value=None)
    with pytest.raises(ValueError):
        b.derive(inputs)


def test_xe_cathode_capability_and_zero_xe_rule(doc):
    p = {x["id"]: x for x in doc["design_parameters"]}
    v = p["H26-21"]["value"]
    assert v["design_mgps"] == 0.10 and v["upper_test_point_mgps"] == 0.15
    lo, hi = v["full_scale_window_mgps"]
    assert lo >= 0.15 and 0.10 >= 0.2 * hi - 1e-12
    assert p["H26-24"]["value"] == 0.0


def test_fixture_module_exchange_isolated(doc):
    fx = doc["fixture"]
    ids = {f["id"] for f in fx["features"]}
    assert {"H26-FX-02", "H26-FX-03", "H26-FX-04", "H26-FX-05", "H26-FX-07"} <= ids
    for f in fx["features"]:
        assert f["flight_classification"] in CLASSES
    svc = fx["service_line_bundle"]
    arms = {"rf_hall": "RF coax", "ecr_hall": "microwave feed"}
    for arm, line in arms.items():
        row = [s for s in svc if line in s["line"]][0]
        assert set(row["sham_in"]) == set(ARCHS) - {arm}
    assert len(fx["remount_reproducibility"]["contributors"]) == 5


def test_ground_vs_flight_subset(doc):
    rows = doc["ground_vs_flight"]
    for r in rows:
        assert r["flight_classification"] in CLASSES
        if r["flight_telemetry_subset"]:
            assert r["flight_classification"] == "FLIGHT-REPRESENTATIVE"
    thrust = [r for r in rows if r["diagnostic"].startswith("thrust stand")][0]
    assert thrust["flight_classification"] == "GROUND/FACILITY-ONLY"


def test_references_have_access_statements(doc):
    for r in doc["references"]:
        assert r["access"], r["id"]
        if r["access"].startswith("full text accessed by this lane"):
            assert re.fullmatch(r"[0-9a-f]{64}", r.get("retrieved_sha256", "")), r["id"]
    txt = json.dumps(doc)
    for rid in set(re.findall(r"REF-[A-Z0-9-]+", txt)):
        if rid in ("REF-COND", "REF-MERGED"):
            continue
        assert any(r["id"] == rid for r in doc["references"]), rid


def test_markdown_companion_consistent(doc):
    md = open(MD_PATH, encoding="utf-8").read()
    for sec in ("## (a) Design parameters", "## (b) Interface demands", "## (c) Hard-incompatibility check",
                "## (d) Architecture-changing blockers", "## (e) M16 rows", "## (f) H3 procurement",
                "## (g) H4 test inputs", "## (h) Milestones"):
        assert sec in md
    for p in doc["design_parameters"]:
        assert f"| {p['id']} |" in md
