"""Tests for the A9 mass + power integration v2 (A9.6 lane fo_a9_6_mass_power_integration).

Run: python -m pytest -q tests/test_mass_power_a9_v2.py   (a few seconds; standard library + pytest only).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "mass_power_a9_v2"
SCRIPT = LANE / "build_mass_power_a9_v2.py"
JSON_PATH = LANE / "mass_power_a9_v2.json"
MD_PATH = LANE / "MASS_POWER_A9_V2.md"
M6 = "docs/budgets/mass_a9/mass_a9_v1.json"
M6_SHA = "071b03fb634c6b25ef422e7ec81006d337e6c333b80133240bdea32999a4f7d4"
BB_SHA = "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a"
ROW54 = {"AL-01": 3.5, "AL-02": 5.5, "AL-03": 1.0, "AL-04": 3.0, "AL-05": 2.0, "AL-06": 1.5, "AL-07": 2.5,
         "AL-08": 1.5, "AL-09": 1.0, "AL-10": 2.5}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"}
CONFIGS = ("hall_icp_neutralizer", "hall_c1_reference")


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def b():
    spec = importlib.util.spec_from_file_location("_mass_power_a9_v2_builder_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def v1():
    return json.loads((REPO / M6).read_text(encoding="utf-8"))


def _walk(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)


# ------------------------------------------------------------------------------------------------ build / structure
def test_builder_check_reproduces(b):
    assert b.main(["--check"]) == 0


def test_json_and_md_consistent(doc, b):
    assert MD_PATH.read_text(encoding="utf-8") == b.render_md(doc)
    for key in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
                "m16_impact", "bom", "lines", "rollups", "power"):
        assert doc[key], key
    assert doc["schema"] == "mass_power_a9_v2"


def test_pins_match_and_base_untouched(doc):
    for p in doc["pins"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]
    pinned = {p["path"] for p in doc["pins"]}
    assert _sha(M6) == M6_SHA and M6 in pinned
    assert _sha("abep_sim/bus_boundary_a9.py") == BB_SHA
    assert doc["revision_of"]["sha256"] == M6_SHA
    for gov in doc["never_pinned"]:
        assert gov not in pinned


def test_pin_mismatch_aborts(b, monkeypatch):
    bad = dict(b.PINS)
    p, s, k = bad["A9"]
    bad["A9"] = (p, "0" * 64, k)
    monkeypatch.setattr(b, "PINS", bad)
    with pytest.raises(SystemExit):
        b.verify_pins()


def test_code_hygiene():
    for p in (SCRIPT, Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert ("xe" + "_ledger" in src) is False, p.name
    src = SCRIPT.read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:from|import) ([\w.]+)", src, re.M))
    assert imports <= {"__future__", "argparse", "hashlib", "json", "math", "sys", "pathlib", "abep_sim"}, imports
    imported = " ".join(re.findall(r"^(?:from|import) .*$", src, re.M))
    assert "archengine" not in imported and "plasma_devices" not in imported and "hall_map" not in imported
    assert "bus_boundary_a9 as bb" in imported


# ------------------------------------------------------------------------------------------------ items / evidence
def test_items_have_source_or_tbd(doc):
    for i in doc["items"]:
        assert i["freeze_point"] in {"NOW", "LOCK-1", "LOCK-2", "after-evidence"}, i["id"]
        assert i["evidence_class"] is None or i["evidence_class"] in EVIDENCE_CLASSES, i["id"]
        if isinstance(i["value"], str):
            assert i["value"] in ("TBD", "TBD_OWNER"), i["id"]
            assert re.match(r"^(TBD|NOT_EVALUATED)", i["status"]), i["id"]
        else:
            assert i["source"], i["id"]


def test_owner_answer_fingerprints(doc):
    ans = json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json").read_text(encoding="utf-8"))
    by = {r["row"]: r for r in ans["answers"]}
    for x in doc["owner_answers_applied"]:
        assert hashlib.sha256(by[x["row"]]["owner_answer_verbatim"].encode()).hexdigest() == x["answer_sha256"]


def test_allocations_unchanged(doc):
    for c in CONFIGS:
        for L in doc["lines"][c]:
            if L["line"] in ROW54:
                assert L["allocation_kg"] == ROW54[L["line"]]
            else:
                assert L["line"] == "AL-C1" and L["allocation_kg"] is None
                assert L["state"] == "ALLOCATION_ABSENT_TBD_OWNER"
    icp = {L["line"] for L in doc["lines"]["hall_icp_neutralizer"]}
    c1 = {L["line"] for L in doc["lines"]["hall_c1_reference"]}
    assert icp == set(ROW54) and "AL-05" not in c1 and "AL-06" not in c1 and "AL-C1" in c1


# ------------------------------------------------------------------------------------------------ four columns
def test_four_columns_strictly_distinct(doc):
    for x in doc["bom"]:
        cols = x["columns"]
        assert set(cols) == {"ALLOCATION", "EVIDENCE_FLOOR", "CBE", "MEASURED"}, x["id"]
        assert cols["ALLOCATION"]["value"] is None          # line-level only
        assert cols["CBE"]["value"] is None and cols["CBE"]["status"]   # no CBE exists anywhere
        assert cols["MEASURED"]["value"] is None
        f = cols["EVIDENCE_FLOOR"]
        if f is not None:
            assert f["evidence_class"] in EVIDENCE_CLASSES - {"owner-allocation", "assumed"}
            assert "not a CBE" in f["note"]


def test_bom_propagation(doc):
    by = {x["id"]: x for x in doc["bom"]}
    for i in ("A9B-17", "A9B-18", "A9B-19", "A9B-20", "A9B-21", "A9B-22"):
        assert by[i]["configurations"] == {"hall_icp_neutralizer": "INSTALLED", "hall_c1_reference": "NOT_INSTALLED"}
    for i in ("A9B-C01", "A9B-C02", "A9B-C03", "A9B-C04", "A9B-C05"):
        assert by[i]["configurations"]["hall_icp_neutralizer"] == "NOT_INSTALLED"
        assert by[i]["configurations"]["hall_c1_reference"] == "INSTALLED"
        assert by[i]["allocation_line"] == "AL-C1"
    for i in ("A9B-13", "A9B-14", "A9B-C06"):     # Xe load / residual / C1 Xe term are wet terms, never dry lines
        assert "WET_TERM_XE_ACCOUNTING" in by[i]["configurations"].values()
        assert by[i]["columns"]["EVIDENCE_FLOOR"] is None
    assert by["A9B-23"]["configurations"]["hall_icp_neutralizer"] == "VARIANT_ONLY"   # G-REUSE primary
    assert "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE" in by["A9B-19"]["v2_propagation"]
    assert "GROUND/FACILITY_ONLY" in by["A9B-19"]["v2_propagation"]
    assert "local adjustable match" in by["A9B-20"]["v2_propagation"]
    assert "no long unmatched coax" in by["A9B-21"]["v2_propagation"]
    assert "REJECTED_AS_CURRENT_BASELINE" in by["A9B-15"]["v2_propagation"]
    assert "UNRESOLVED" in by["A9B-30"]["v2_propagation"]
    assert {"MPV2-N01", "MPV2-N02", "MPV2-N03", "MPV2-N04", "MPV2-N05", "MPV2-N06"} <= set(by)
    for x in doc["bom"]:
        if x["v1_list"] == "removed_preionizer_only":
            assert set(x["configurations"].values()) == {"REMOVED_PREIONIZER_ONLY"}
    ga = {g["id"]: g for g in doc["ground_article_only"]}
    assert "GROUND/FACILITY_ONLY" in ga["GA-07"]["rule"] and "GROUND/FACILITY_ONLY" in ga["GA-02"]["v2_note"]


def test_coil_mass_correction(doc):
    cm = doc["coil_mass_correction"]
    assert cm["booked_copper_kg"] == 1.579 and cm["sensitivity_basis_60W_kg"] == 0.136
    assert cm["complete_coil_copper_estimate_kg"] == 1.58
    al4 = [L for L in doc["lines"]["hall_icp_neutralizer"] if L["line"] == "AL-04"][0]
    assert al4["evidence_floor_kg"] == 3.504
    kgs = [c["kg"] for c in al4["floor_constituents"]]
    assert 1.579 in kgs and 0.136 not in kgs
    items = {i["id"]: i for i in doc["items"]}
    assert items["MPV2-M02"]["status"] == "SENSITIVITY_BASIS_ONLY"


def test_c1_line_no_double_count(doc):
    c1 = [L for L in doc["lines"]["hall_c1_reference"] if L["line"] == "AL-C1"][0]
    assert c1["evidence_floor_kg"] == 0.2          # cathode-unit low end only; 0.285 branch is inside the AL-08 floor
    al8 = [L for L in doc["lines"]["hall_c1_reference"] if L["line"] == "AL-08"][0]
    assert al8["evidence_floor_kg"] == 5.044


# ------------------------------------------------------------------------------------------------ roll-ups
def test_icp_rollup_reproduces_v1(doc, v1):
    rd = v1["wet_closure"]["readings"]
    want = {("OWNER_V0_LITERAL", "ALLOCATIONS"): rd["R0"]["dry_kg"],
            ("OWNER_V0_LITERAL", "WITH_EVIDENCE_FLOORS"): rd["R0E"]["dry_kg"],
            ("MQ01_MEV_LEVEL", "ALLOCATIONS"): rd["R1"]["dry_kg"],
            ("MQ01_MEV_LEVEL", "WITH_EVIDENCE_FLOORS"): rd["R1E"]["dry_kg"],
            ("MQ01_CBE_LEVEL", "ALLOCATIONS"): rd["R2"]["dry_kg"],
            ("MQ01_CBE_LEVEL", "WITH_EVIDENCE_FLOORS"): rd["R2E"]["dry_kg"]}
    got = {(r["reading"], r["basis"]): r["dry_known_kg"] for r in doc["rollups"]
           if r["configuration"] == "hall_icp_neutralizer"}
    for k, v in want.items():
        assert abs(got[k] - v) < 1e-5, (k, got[k], v)


def test_all_readings_side_by_side_none_chosen(doc):
    combos = {(r["configuration"], r["reading"], r["basis"]) for r in doc["rollups"]}
    assert len(combos) == 2 * 3 * 2
    for r in doc["rollups"]:
        xr = {(w["xe_case_reading"], w["xe_case_kg"], w["reference"]) for w in r["wet"]}
        assert len(xr) == 2 * 3 * 3
    txt = json.dumps(doc).lower()
    for banned in ("primary_reading", "selected reading", "winner:", "best architecture", "recommended architecture",
                   "sgb-screen", "ensemble_member_id"):
        assert (banned in txt) is False, banned


def test_residual_booked_once(doc, v1):
    top = {float(k): v for k, v in v1["wet_closure"]["residual"]["by_case_kg"]["residual_on_top_MQ-09"].items()}
    for r in doc["rollups"]:
        for w in r["wet"]:
            if w["xe_case_reading"] == "LOADED_XA9Q01":
                assert w["residual_added_on_top_kg"] == 0.0 and w["residual_inside_case_kg"] is not None
                assert abs(w["wet_known_kg"] - (r["dry_known_kg"] + w["xe_case_kg"])) < 1e-5
            else:
                assert w["residual_added_on_top_kg"] == top[w["xe_case_kg"]]
                assert abs(w["wet_known_kg"] - (r["dry_known_kg"] + w["xe_case_kg"] + top[w["xe_case_kg"]])) < 1e-5


def test_no_cell_closes(doc):
    for r in doc["rollups"]:
        assert r["all_terms_resolved"] is False
        for w in r["wet"]:
            assert w["state"] in ("DOES_NOT_CLOSE", "NOT_EVALUABLE")


def test_c1_xe_case_flag(doc):
    flagged = {(r["configuration"], w["xe_case_kg"]) for r in doc["rollups"] for w in r["wet"] if w["xe_case_flag"]}
    assert ("hall_c1_reference", 2.0) in flagged and ("hall_c1_reference", 5.0) in flagged
    assert not any(c == "hall_icp_neutralizer" for c, _ in flagged)


def test_rollup_fail_closed(b):
    lines = [{"line": "AL-01", "allocation_kg": 1.0, "evidence_floor_kg": None, "is_harness": False},
             {"line": "AL-09", "allocation_kg": 1.0, "evidence_floor_kg": None, "is_harness": True}]
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup(lines, "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05, None, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup([dict(lines[0])], "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05, 0.2, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup([{"line": "X", "is_harness": False}, lines[1]], "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05,
                     0.2, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup(lines, "SOME_READING", "ALLOCATIONS", 4.0, 0.05, 0.2, 0.2)
    d = b.dry_rollup(lines + [{"line": "AL-C1", "allocation_kg": None, "evidence_floor_kg": None,
                               "is_harness": False}], "MQ01_MEV_LEVEL", "ALLOCATIONS", 4.0, 0.05, 0.2, 0.2)
    assert d["every_line_has_a_value"] is False and any("AL-C1" in u for u in d["unresolved"])
    with pytest.raises(b.MassPowerV2Error):
        b.wet_cell(d, 2.0, "USABLE", 0.04, 40.0, True)
    with pytest.raises(b.MassPowerV2Error):
        b.wet_cell(d, None, "USABLE_MQ09", 0.04, 40.0, True)
    full = dict(d, all_terms_resolved=True)
    assert b.wet_cell(full, 1.0, "LOADED_XA9Q01", 0.0, 40.0, True)["state"] == "CLOSES"
    assert b.wet_cell(dict(full, dry_known_kg=39.0), 1.0, "LOADED_XA9Q01", 0.0, 40.0, True)["state"] == "DOES_NOT_CLOSE"


# ------------------------------------------------------------------------------------------------ power
def test_power_no_pass_all_tbd(doc):
    p = doc["power"]
    assert p["boundary_version"] == "bus_power_boundary_a9_v1"
    assert p["gate"]["limit_W"] == 1500.0 and p["gate"]["window_s"] == 1e-3 and p["gate"]["strict"] is True
    assert p["allocations"]["design_allocation_W"]["value"] == 1350.0
    assert p["allocations"]["common_allocation_W"]["value"] == 300.0
    assert p["allocations"]["controls_thermal_allowance_W"]["value"] == 50.0
    assert p["allocations"]["hall_and_electron_source_envelope_at_common_upper_W"]["value"] == 1050.0
    for c in CONFIGS:
        pc = p["configurations"][c]
        assert pc["rfp_gate_1ms"]["verdict"] == "NOT_EVALUABLE"
        st = pc["phases"]["steady"]
        assert st["ledger_status"] == "PARTIAL_BOUNDARY" and st["P_bus_W"] is None
        for s in pc["slots"]:
            assert s["CBE_W"] is None and s["MEASURED_W"] is None
            if s["slot"] != "reserved_dc_port":
                assert s["ALLOCATION_W"] is None
    for k, v in _walk(doc):
        if k in ("verdict", "state", "status", "sequence_status"):
            assert v != "PASS", (k, v)
    assert "icp_rf_source" not in [s["slot"] for s in p["configurations"]["hall_c1_reference"]["slots"]]
    assert "c1_heater" not in [s["slot"] for s in p["configurations"]["hall_icp_neutralizer"]["slots"]]
    assert "flow_control_icp_feed" not in p["configurations"]["hall_icp_neutralizer"]["installed_slots"]
    assert p["icp_rf_chain"]["bus_crossing_plane"] == "generator_dc_input"


def test_statuses_never_pass(doc):
    s = doc["statuses"]["a9_2_statuses"]
    assert len(s) == 10 and "PASS" not in s.values()
    assert s["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert s["coupled H-1/ICP thermal closure"] == "UNRESOLVED"
    f = doc["statuses"]["a9_6_fixed_statuses"]
    assert f["316L_FLIGHT_ANODE"] == "REJECTED_AS_CURRENT_BASELINE" and f["FINAL_ANODE_MATERIAL"] == "OPEN"


def test_icp_rf_dc_input_fail_closed(b):
    ce = {"value": 200.0, "evidence_class": "measured", "boundary": "generator_dc_input"}
    reg = {"value": 5.0, "status": "REGISTERED"}
    with pytest.raises(b.MassPowerV2Error):
        b.icp_rf_generator_dc_input(ce, reg, "GROUND/FACILITY_ONLY")
    with pytest.raises(b.MassPowerV2Error):
        b.icp_rf_generator_dc_input(ce, reg, "LAB")
    with pytest.raises(b.MassPowerV2Error):
        b.icp_rf_generator_dc_input(dict(ce, synthetic=True), reg, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    with pytest.raises(b.MassPowerV2Error):
        b.icp_rf_generator_dc_input(dict(ce, boundary="mains_input"), reg, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    with pytest.raises(b.MassPowerV2Error):
        b.icp_rf_generator_dc_input({"evidence_class": "measured"}, reg, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    r = b.icp_rf_generator_dc_input(ce, {"value": "TBD"}, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    assert r["status"] == "NOT_EVALUATED" and r["P_DC_in_W"] is None
    r = b.icp_rf_generator_dc_input(ce, {"value": 8.33, "status": "STAND_CEILING"}, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    assert r["status"] == "NOT_EVALUATED"
    r = b.icp_rf_generator_dc_input({"value": "TBD"}, reg, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    assert r["status"] == "TBD"
    r = b.icp_rf_generator_dc_input(ce, reg, "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE")
    assert r["P_DC_in_W"] == 1000.0


# ------------------------------------------------------------------------------------------------ sections
def test_open_questions_new_only_and_open(doc):
    oqs = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v3.json").read_text(encoding="utf-8"))
    existing = {r["id"] for r in oqs["rows"]}
    for q in doc["open_owner_questions"]:
        assert q["id"] not in existing and q["status"] == "OPEN" and q["proposed"] and q["needed_by"]
    for k, v in doc["open_register_status"].items():
        assert v == "OPEN", k           # carried owner calls stay open (never answered here)


def test_pending_lanes_referenced_not_read(doc, b):
    for k, v in doc["pending_parallel_lanes"].items():
        assert v.startswith("PENDING "), v
    pinned = {p["path"] for p in doc["pins"]}
    for _lane, path in b.PENDING_LANES.values():
        assert path not in pinned
    demands = {d["id"]: d for d in doc["interface_demands"]}
    assert any(d["to"].startswith("PENDING docs/experiments/hall_icp/p3_coupled_thermal/") for d in demands.values())
    assert any(d["to"].startswith("PENDING docs/budgets/xe_accounting_a9_v2/") for d in demands.values())


def test_m16_no_state_promotion(doc):
    for m in doc["m16_impact"]:
        assert m["state_change"].startswith("none")
    txt = json.dumps(doc["m16_impact"])
    assert "VERIFIED" not in txt and "READY" not in txt
