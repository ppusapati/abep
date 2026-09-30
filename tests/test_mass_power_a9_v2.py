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


def test_downstream_lanes_referenced_not_read(doc, b):
    """S-02 / PHYS-01: RVM and M16 are merged and consume this package; they are named as downstream consumers (built
    later in the A9.6 order, never pinned - a pin would be circular), never as 'PENDING / not merged'."""
    assert "pending_parallel_lanes" not in doc
    for k, v in doc["downstream_consumer_lanes"].items():
        assert v.startswith("downstream consumer "), v
    pinned = {p["path"] for p in doc["pins"]}
    for _lane, path in b.DOWNSTREAM_LANES.values():
        assert path not in pinned
    assert set(doc["downstream_consumer_lanes"]) == {"M16", "RVM"}
    txt = json.dumps(doc)
    assert "PENDING fo_a9_6_" not in txt and "not merged in this base" not in txt
    demands = {d["id"]: d for d in doc["interface_demands"]}
    assert demands["MPV2-ID-01"]["from"].startswith("docs/experiments/hall_icp/p3_coupled_thermal/")
    assert demands["MPV2-ID-15"]["from"].startswith("docs/budgets/xe_accounting_a9_v2/")


def test_xe_residual_imported_once_from_xe_v2_both_readings(doc, v1):
    """XL-30: the residual is read from the merged Xe accounting v2 (both readings), equals the immutable v1 import,
    and is booked once per wet cell (inside the case or on top, never both)."""
    xe = json.loads((REPO / "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json").read_text(encoding="utf-8"))
    rows = xe["design_cases"]["reserve_residual_split"]["rows"]
    imp = doc["xe_v2_import"]["residual_by_reading_kg"]
    for r in rows:
        assert imp[r["reading"]][str(float(r["case_kg"]))] == r["residual_kg"]
    assert all(a["agrees"] for a in doc["xe_v2_import"]["agreement_with_mass_a9_v1"])
    for r in doc["rollups"]:
        for w in r["wet"]:
            inside = w["residual_inside_case_kg"] is not None
            on_top = w["residual_added_on_top_kg"] != 0.0
            assert inside != on_top
            assert "Xe accounting v2" in w["xe_case_headroom_status"]


def test_xe_residual_disagreement_refused(b, monkeypatch):
    m6 = b.load("M6")
    m6["wet_closure"]["residual"]["by_case_kg"]["residual_on_top_MQ-09"]["2.0"] = 0.05
    with pytest.raises(b.MassPowerV2Error):
        b.import_xe_v2(m6)


def test_p4_densities_imported_not_booked(doc):
    """XL-26: P4 densities are informational imports (never a CBE / booked mass)."""
    p4 = json.loads((REPO / "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json").read_text(
        encoding="utf-8"))
    recs = {r["id"]: r for r in p4["property_records"]}
    got = doc["p4_density_import"]["records"]
    assert [r["id"] for r in got] == ["PR-001", "PR-011", "PR-021"]
    for r in got:
        assert r["density_kg_m3"] == recs[r["id"]]["value_si"] and "not a CBE" in r["use_here"]
    for line in doc["bom"]:
        assert line["columns"]["CBE"]["value"] is None


def test_m16_no_state_promotion(doc):
    for m in doc["m16_impact"]:
        assert m["state_change"].startswith("none")
    txt = json.dumps(doc["m16_impact"])
    assert "VERIFIED" not in txt and "READY" not in txt


# ------------------------------------------------------------------ A9.6 cross-lane integration (fo_a9_6_cross_lane_integration)
_XL_SELF = 'MP'
_XL_JSON = {
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "MP": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
    "XE": "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
    "RFQ": "docs/procurement/rfq_a9_v2/rfq_a9_v2.json",
}
_XL_MD = ['docs/budgets/mass_power_a9_v2/MASS_POWER_A9_V2.md']
_XL_BUILDER = 'docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py'
_XL_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _xl_load(k):
    return __import__("json").loads((_XL_ROOT / _XL_JSON[k]).read_text(encoding="utf-8"))


def _xl_demands(d):
    ifd = d["interface_demands"]
    return [e for v in ifd.values() for e in v] if isinstance(ifd, dict) else list(ifd)


def _xl_builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("xl_builder_" + _XL_SELF.lower(), str(_XL_ROOT / _XL_BUILDER))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_xlane_pairs_reconciled_both_directions():
    """A9.6 sec. 5-6: every cross-lane interface demand of this package has exactly one matching entry in the
    counterpart package: same pair id, identical quantity / units / status text, mutual pointers; a single-pair entry
    carries the pair's units and status itself; no pair status is a PASS."""
    here = _xl_load(_XL_SELF)
    n = 0
    for e in _xl_demands(here):
        for x in e.get("xref", []):
            pkg, cid = x["counterpart"].split(":", 1)
            assert x["counterpart_path"] == _XL_JSON[pkg]
            there = _xl_demands(_xl_load(pkg))
            match = [(f, y) for f in there if f["id"] == cid for y in f.get("xref", []) if y["pair"] == x["pair"]]
            assert len(match) == 1, (x["pair"], x["counterpart"])
            f, y = match[0]
            assert y["counterpart"] == _XL_SELF + ":" + e["id"], x["pair"]
            for k in ("quantity", "units", "status"):
                assert y[k] == x[k], (x["pair"], k)
            assert not x["status"].upper().startswith("PASS"), x["pair"]
            if len(e["xref"]) == 1:
                assert e["units"] == x["units"] and e["status"] == x["status"], e["id"]
            n += 1
    assert n >= 1


def test_xlane_references_checked_not_pinned_not_stale():
    """A9.6 sec. 18 'no stale references': no 'PENDING <merged package>' marker survives; every merged package is
    recorded MERGED and never sha-pinned (packages read each other back: a pin would be circular); the builder's
    build-time id check passes on the committed JSON and refuses a broken counterpart id."""
    import copy
    import hashlib
    import re
    doc = _xl_load(_XL_SELF)
    txt = (_XL_ROOT / _XL_JSON[_XL_SELF]).read_text(encoding="utf-8") + "".join(
        (_XL_ROOT / p).read_text(encoding="utf-8") for p in _XL_MD)
    for k, p in _XL_JSON.items():
        if k == _XL_SELF:
            continue
        d = p.rsplit("/", 1)[0]
        assert re.search(r"PENDING[ :`'\"]*" + re.escape(d), txt) is None, d
        sha = hashlib.sha256((_XL_ROOT / p).read_bytes()).hexdigest()
        assert sha not in txt, "sha-pinned merged package " + p
    rec = doc["merged_cross_lane"]
    assert rec["build_order"] == ["P4", "XE", "P1", "P2", "P3", "MP", "RFQ"]
    for k, v in rec["packages"].items():
        assert v["state"] == "MERGED" and v["sha_pinned"] is False and v["path"] == _XL_JSON[k]
    b = _xl_builder()
    assert b.xlane_check(doc) == []
    bad = copy.deepcopy(doc)
    for e in _xl_demands(bad):
        if e.get("xref"):
            e["xref"][0]["counterpart"] = e["xref"][0]["counterpart"].split(":")[0] + ":NO-SUCH-ID"
            break
    assert b.xlane_check(bad)



def test_sw08_rollup_refuses_impossible_line_values(b):
    """SW-08: negative / NaN / string masses, duplicate lines and a harness without allocation are refused; a NaN never
    reaches NOT_EVALUABLE or CONSISTENT."""
    good = [{"line": "AL-01", "allocation_kg": 1.0, "evidence_floor_kg": None, "is_harness": False},
            {"line": "AL-09", "allocation_kg": 1.0, "evidence_floor_kg": None, "is_harness": True}]
    for bad in (-30.0, float("nan"), float("inf"), "3", True):
        for key in ("allocation_kg", "evidence_floor_kg"):
            lines = [dict(good[0], **{key: bad}), good[1]]
            with pytest.raises(b.MassPowerV2Error):
                b.dry_rollup(lines, "MQ01_CBE_LEVEL", "WITH_EVIDENCE_FLOORS", 4.0, 0.05, 0.2, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup(good + [dict(good[0])], "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05, 0.2, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.dry_rollup([good[0], dict(good[1], allocation_kg=None)], "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05, 0.2,
                     0.2)
    d = b.dry_rollup(good, "MQ01_CBE_LEVEL", "ALLOCATIONS", 4.0, 0.05, 0.2, 0.2)
    with pytest.raises(b.MassPowerV2Error):
        b.wet_cell(dict(d, dry_known_kg=float("nan")), 1.0, "LOADED_XA9Q01", 0.0, 40.0, True)
    for alloc, floor in ((5.0, float("nan")), (-1.0, None), (5.0, -2.0)):
        with pytest.raises(b.MassPowerV2Error):
            b.line_state(alloc, floor, False)
    assert b.line_state(5.0, 4.0, False) == "CONSISTENT"
