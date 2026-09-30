"""Tests for the A9-07 H2 revisions deliverable (fo_a9_07_h2_revisions).

Run: python -m pytest -q tests/test_h2_a9_revisions.py   (about 60 s: one deterministic rebuild in memory, the thermal
worst-case search split over fork worker processes).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "hardware" / "h2_a9_revisions"
SCRIPT = LANE / "build_h2_a9_revisions.py"
JSON_PATH = LANE / "h2_a9_revisions_v1.json"
MD_PATH = LANE / "H2_A9_REVISIONS.md"

DECISION_SHA = {
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json":
        "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
    "docs/decisions/OD_2026_09_29_owner_answers_147.json":
        "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
    "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md":
        "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
    "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json":
        "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4",
    "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md":
        "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e",
}
# verified H2 v1 deliverables at the base commit: they must stay byte-identical (this lane only reads them)
H2_V1_SHA = {
    "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json": "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d",
    "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json": "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971",
    "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json": "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b",
    "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json": "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef",
    "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json": "68c5be61443d0ef1c7308c4aba265426137292dcf9363e57903e0a1f6c8bc083",
    "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json": "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56",
    "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json": "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630",
    "docs/hardware/h2/h2_1_hall_chamber_magnet/build_h2_1_hall_chamber_magnet.py": "5df465d564640db49ddc585669b027d21a6961631bff8614d5b8597584f16ff2",
    "docs/hardware/h2/h2_5_thermal_network/build_h2_5_thermal_network.py": "4e937fa97b104d1004765f5a8a3c624bf702375fb822b81bc97b979446aebbec",
    "docs/hardware/h2/h2_1_hall_chamber_magnet/H2_1_HALL_CHAMBER_MAGNET.md": "4b6ee8414cd150c1f65917aa82dc83c20d39be288094d1b590fcd4794ab5ba3c",
    "docs/hardware/h2/h2_5_thermal_network/H2_5_THERMAL_NETWORK.md": "87a4d2f546d62694644a7c3eed0b0d9a6a1cb915018ebbc970eb8ad428b5daf4",
}
REQUIRED_SECTIONS = ("revision_register", "new_items", "interface_demands", "owner_answers_applied",
                     "open_owner_questions", "historical_reuse", "m16_impact", "h3_inputs", "h4_inputs",
                     "recomputations", "a9_1_decisions_applied", "hard_incompatibility_check")
REV_FIELDS = ("id", "h2_lane", "h2_item", "topic", "old", "new", "units", "driver", "basis", "evidence_class",
              "status", "freeze_point", "applies_to", "recomputation")


def _sens(e: dict, key: str):
    """A9.2 ICP_COUPLED_THERMAL: pass-like hall_icp_neutralizer statuses are reported UNRESOLVED; the computed
    (uncoupled) value is kept beside them as uncoupled_sensitivity_<key>. The arithmetic checks use that value."""
    return e.get("uncoupled_sensitivity_" + key, e[key])


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _resolve(doc, pointer):
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


@pytest.fixture(scope="module")
def builder():
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("_a907_builder_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = saved
    return mod


@pytest.fixture(scope="module")
def outputs(builder):
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return builder.outputs()
    finally:
        sys.dont_write_bytecode = saved


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_committed_outputs_are_reproduced_exactly(builder, outputs):
    assert outputs[builder.OUT_JSON] == JSON_PATH.read_text(encoding="utf-8")
    assert outputs[builder.OUT_MD] == MD_PATH.read_text(encoding="utf-8")


def test_decisions_pinned_and_unchanged(doc):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"]}
    for rel, sha in DECISION_SHA.items():
        assert _sha(rel) == sha, rel
        assert pins[rel] == sha, rel


def test_h2_v1_deliverables_byte_identical(doc):
    for rel, sha in H2_V1_SHA.items():
        assert _sha(rel) == sha, f"verified H2 v1 file changed: {rel}"
    for p in doc["deliverable_pins"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]


def test_no_mutable_governance_pinned(doc):
    pinned = {p["path"] for p in doc["decision_pins"] + doc["deliverable_pins"]}
    for g in doc["never_pinned"]:
        assert g not in pinned


def test_structure_and_vocabulary(doc):
    for s in REQUIRED_SECTIONS:
        assert s in doc and doc[s], s
    assert doc["configurations"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    assert "NO_VIABLE_CASE" in doc["outcome_vocabulary"]
    assert doc["status_not_outcome"] == ["OPEN"]
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"


def test_revision_register_entries_complete_and_traceable(doc):
    ids = [r["id"] for r in doc["revision_register"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 40
    h2_docs = {}
    for r in doc["revision_register"]:
        for f in REV_FIELDS:
            assert f in r, (r["id"], f)
        assert r["status"] in doc["rev_statuses"], r["id"]
        assert r["freeze_point"] in doc["freeze_points"], r["id"]
        if r["evidence_class"] is not None:
            assert r["evidence_class"].split()[0] in doc["evidence_classes"], r["id"]
        else:
            assert r["status"] in ("TBD", "SUPERSEDED_FOR_A9", "OWNER_GIVEN"), r["id"]
        assert r["driver"], r["id"]
        for c in r["applies_to"]:
            assert c in doc["configurations"]
        o = r["old"]
        src = o["source"]
        path = src["path"]
        assert src["sha256"] == _sha(path), r["id"]
        if path not in h2_docs:
            h2_docs[path] = json.loads((REPO / path).read_text(encoding="utf-8"))
        assert _resolve(h2_docs[path], src["pointer"]) == o[o["field"]], r["id"]
        assert "requirement" in r["new"] or "value" in r["new"], r["id"]


def test_coverage_of_the_brief(doc):
    items = {r["h2_item"] for r in doc["revision_register"]}
    # (1) external C1
    for i in ("H21-22", "H22-01", "H22-28", "H22-30", "H22-22", "H22-09", "H22-47", "H22-27"):
        assert i in items, i
    # (2) downstream fixture
    for i in ("H26-40", "H26-41", "H26-42", "H26-43", "H26-FX-03"):
        assert i in items, i
    # (4) H2-4 flagged items
    for i in ("H24-19", "H24-26", "H24-35", "H24-04", "H24-36", "H24-37"):
        assert i in items, i
    # (5) interfaces
    for i in ("H24-25", "H23-27"):
        assert i in items, i
    new = {i["id"] for i in doc["new_items"]}
    assert {"A9H-INS-01", "A9H-INS-04", "A9H-INS-05", "A9H-INS-09", "A9H-CAL-01", "A9H-CAL-02", "A9H-CAL-03",
            "A9H-CAL-04"} <= new


def test_owner_rows_resolve_with_fingerprints(doc):
    ans = {a["row"]: a for a in json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json")
                                           .read_text(encoding="utf-8"))["answers"]}
    seen = 0

    def walk(x):
        nonlocal seen
        if isinstance(x, dict):
            if x.get("kind") == "owner_row":
                a = ans[x["row"]]
                assert x["covers_ids"] == a["covers_ids"]
                assert x["answer_sha256"] == hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest()
                seen += 1
            if x.get("kind") == "A9.1":
                dec = json.loads((REPO / x["path"]).read_text(encoding="utf-8"))["decisions"]
                assert x["id"] in dec
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    assert seen > 50
    for r in (79, 86, 89, 90, 92, 93, 94, 105, 110, 111, 112, 116, 122, 133):
        assert r in {a["row"] for a in doc["owner_answers_applied"]}, r


def test_external_c1_recomputation(doc):
    h1 = doc["recomputations"]["h21_central_bore"]
    v1 = json.loads((REPO / "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json")
                    .read_text(encoding="utf-8"))
    h2122 = [p for p in v1["design_parameters"] if p["id"] == "H21-22"][0]["value"]
    matched = 0
    for r in h1["rows"]:
        key = f"{r['h_mm']:.4g}"
        if key in h2122:
            assert r["v1_central_cathode_floor_mm"]["bore_12mm"] == h2122[key]["bore_12mm"]
            assert r["v1_central_cathode_floor_mm"]["bore_18mm"] == h2122[key]["bore_18mm"]
            matched += 1
        f = r["external_c1_magnetic_floor_mm"]
        # without a bore the floor must be lower than with either bore
        assert f["nominal_assumptions"] < r["v1_central_cathode_floor_mm"]["bore_12mm"]
        assert f["nominal_assumptions"] <= f["worst_case_assumptions"]
        lo, hi = r["channel_window_d_mean_mm_at_this_h"]
        assert r["external_floor_binding"]["nominal_assumptions"] == (f["nominal_assumptions"] > lo)
        assert r["external_floor_binding"]["worst_case_assumptions"] == (f["worst_case_assumptions"] > lo)
    assert matched == 3
    assert h1["in_memory_override"]["restored"] is True
    # REV-01 binding flags must agree with the rows (review finding: the flag was inverted)
    rev01 = [r for r in doc["revision_register"] if r["id"] == "REV-01"][0]["new"]
    for kind in ("nominal_assumptions", "worst_case_assumptions"):
        rows = [r["h_mm"] for r in h1["rows"] if r["external_c1_magnetic_floor_mm"][kind]
                > r["channel_window_d_mean_mm_at_this_h"][0]]
        assert rev01["binding_inside_window"][kind] == bool(rows), kind
        assert rev01["binding_rows_h_mm"][kind] == rows, kind
    assert rev01["binding_inside_window"]["worst_case_assumptions"] is True


def test_small_derivations(doc):
    s = doc["recomputations"]["small"]
    assert s["icp46_isolation_basis_V"]["value"] == 900.0          # A9.1 ICP-46: 1.5 x 600 V
    assert math.isclose(s["flight_discharge_output_current_bound_A"]["value"], 1350.0 / 180.0, rel_tol=1e-4)
    assert math.isclose(s["rfp_bound_current_A"]["value"], 1500.0 / 180.0, rel_tol=1e-4)
    assert math.isclose(s["rfp_bound_current_A"]["check_H24_27"], 1500.0 / 180.0, rel_tol=1e-4)
    xe = s["c1_ignition_dwell_xe_bound_g"]["value"]
    assert math.isclose(xe["attempts_3_literal"], 1.0e-3 * 120.0 * 3, rel_tol=1e-6)   # 1.0 mg/s x 120 s x 3 -> g
    assert math.isclose(xe["attempts_2_shorthand"], 1.0e-3 * 120.0 * 2, rel_tol=1e-6)


def test_ceramic_conductor_factor_independent(doc):
    kf = doc["recomputations"]["h25_thermal_rerun"]["coil_conductor_factor"]
    cmil_ft = (math.pi / 4.0) * (0.001 * 0.0254) ** 2 / 0.3048          # ohm-cmil/ft -> ohm m
    rho_cu20 = 1.7241e-8
    roeser = {0.0: 1.0, 100.0: 1.431, 200.0: 1.862, 300.0: 2.299, 400.0: 2.747, 500.0: 3.21}

    def cu(T):
        ks = sorted(roeser)
        for a, b in zip(ks, ks[1:]):
            if a <= T <= b:
                return roeser[a] + (roeser[b] - roeser[a]) * (T - a) / (b - a)
        if T > 500.0:   # end-chord continuation (H2-5 cu_factor_vs_20C)
            return roeser[400.0] + (roeser[500.0] - roeser[400.0]) * (T - 400.0) / 100.0
        raise ValueError(T)
    T5, T10 = (500 - 32) * 5 / 9, (1000 - 32) * 5 / 9
    ratios = {}
    for T, r in ((T5, 26.9), (T10, 42.3)):   # the two SOURCED Kulgrid points only (review finding)
        ratios[f"{T:.2f}"] = r * cmil_ft / (rho_cu20 * cu(T) / cu(20.0))
    assert set(kf["points_degC"]) == {"260.00", "537.78"}
    for k, v in ratios.items():
        assert math.isclose(kf["points_degC"][k]["ratio"], v, rel_tol=1e-3), k
    assert math.isclose(ratios["537.78"], 1.3088, rel_tol=1e-3)
    assert math.isclose(kf["factor"], max(ratios.values()), rel_tol=1e-3) and kf["factor_at"] == "260.00 degC"


def test_thermal_rules_and_verdicts(doc):
    th = doc["recomputations"]["h25_thermal_rerun"]
    assert th["rule"]["margin_K"] == 50.0 and th["rule"]["heat_load_margin"] == 1.2
    lim = th["limits"]
    assert lim["BN_wall"]["limit_C"] == 900.0
    assert math.isclose(lim["coil_ceramic"]["limit_C"], (1000.0 - 32.0) * 5.0 / 9.0, abs_tol=1e-3)
    alw = th["search"]["allowance_K"]
    gaps = th["search"]["gap_check"]["gap_per_reference_and_output"]
    assert len(gaps) >= 2   # more than one reference combination (review finding)
    assert alw >= 0.0 and alw == max(v for g in gaps.values() for k, v in g.items() if k != "Q_mount_W")
    for cfg, levers in th["results"].items():
        assert cfg in doc["configurations"]
        for lv, cases in levers.items():
            for c, rec in cases.items():
                for n, e in rec["nodes"].items():
                    assert e["T_min_C"] <= e["T_nominal_C"] + 1e-6 <= e["T_max_C"] + 2e-6, (cfg, lv, c, n)
                    # the searched / bounded maximum is never below the OAT adverse corner
                    assert e["T_max_C"] >= e["oat_corner_T_max_C"] - 1e-9, (cfg, lv, c, n)
                    key = "sensitivity_outcome" if cfg == "hall_c1_reference" else "verdict"
                    assert ("verdict" in e) == (cfg != "hall_c1_reference"), (cfg, lv, c, n)
                    if e.get("limit_C") is not None:
                        ceil = e["limit_C"] - 50.0
                        if rec["domain_exits"]:
                            assert e[key] == "DO_NOT_CLOSE_MODEL_DOMAIN_EXCEEDED"
                        else:
                            assert (_sens(e, key) == "CLOSES") == (e["T_max_C"] + alw <= ceil + 1e-9), (cfg, lv, c, n)
                    else:
                        assert e[key] == "OPEN_LIMIT_TBD"
    # dominated orbit cases carry the searched orbit_hot @ 60 degC maximum of the same lever as their bound
    icp = th["results"]["hall_icp_neutralizer"]
    for lv, cases in icp.items():
        if lv.startswith("LV-BASE-BARE"):
            continue
        dom = cases["orbit_hot@T_mount=60C"]["nodes"]
        for c, rec in cases.items():
            if c.startswith("orbit") and c != "orbit_hot@T_mount=60C":
                for n in ("WI", "WO", "CI", "CO", "PI", "PO", "BP"):
                    assert rec["nodes"][n]["T_max_C"] == dom[n]["T_max_C"], (lv, c, n)
                    assert rec["nodes"][n]["oat_corner_T_max_C"] <= dom[n]["T_max_C"], (lv, c, n)
    # the v1 11.2 K case is reproduced with the imported solver
    rep = th["reproduction_check"]
    assert rep["v1_margin_worst_K"] == 11.2 and abs(rep["reproduced_T_max_C"] - rep["v1_T_max_C"]) <= 0.15
    assert th["bn_wall_11_2K_case"]["status"] == "UNRESOLVED"                       # A9.2
    assert _sens(th["bn_wall_11_2K_case"], "status") in ("CONDITIONALLY_RESOLVED", "OPEN")
    assert th["overall"]["status"] == "UNRESOLVED" and th["overall"]["status_before_a9_2"] == "OPEN"
    # EM-only: no permanent-magnet rows; coating baseline is the high-emittance option
    assert "Sm2Co17" not in json.dumps(th["results"])
    assert th["levers"]["LV-BASE"]["set"] == {}


def test_levers_never_leave_the_h2_5_ranges(doc):
    v1 = json.loads((REPO / "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json")
                    .read_text(encoding="utf-8"))
    rng = {p["key"]: p["value"] for p in v1["design_parameters"]}
    for name, lv in doc["recomputations"]["h25_thermal_rerun"]["levers"].items():
        for k, (op, val) in lv["set"].items():
            if op == "fix":
                lo, hi = rng[k]
                assert lo <= val <= hi, (name, k, val)
            else:
                assert op == "scale_hi" and 0.0 < val <= 1.0, (name, k)


def test_mount_heat_row85_consistency(doc):
    th = doc["recomputations"]["h25_thermal_rerun"]
    aw = th["search"]["allowance_W"]
    for lv, cases in th["mount_heat_vs_row85"].items():
        for c, r in cases.items():
            w = r.get("within_allowable_W_uncoupled_sensitivity", r["within_allowable_W"])
            assert "CLOSES" not in r["within_allowable_W"].values()                     # A9.2
            for a, v in w.items():
                assert (v == "CLOSES") == (r["Q_mount_W"]["max_W"] + aw <= float(a))
    ok = sorted(lv for lv, cases in th["mount_heat_vs_row85"].items()
                if all(r.get("within_allowable_W_uncoupled_sensitivity", r["within_allowable_W"])["100"] == "CLOSES"
                       for r in cases.values()))
    assert ok == th["row85_compatible_levers_100W"]


def test_no_prediction_no_winner_no_forbidden_sources():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "xe_ledger" not in src
    imports = [ln for ln in src.splitlines() if re.match(r"\s*(import|from)\s", ln)]
    for ln in imports:
        for banned in ("plasma_devices", "hall_map", "hall_ensemble", "archengine", "hallthruster_bridge"):
            assert banned not in ln, ln
    txt = JSON_PATH.read_text(encoding="utf-8") + MD_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\bwinner is\b|\bselected as (the )?baseline\b|\bis the winner\b", txt, re.I)
    assert not re.search(r"\bA9 is (a |the )?flight baseline|(hall_icp_neutralizer|hall_c1_reference) is the "
                         r"(flight )?baseline", txt, re.I)


def test_pending_references_point_to_parallel_lanes(doc):
    txt = json.dumps([doc["interface_demands"], doc["new_items"], [r["new"] for r in doc["revision_register"]]])
    for m in re.finditer(r"PENDING ([^ \"(]+)", txt):
        p = m.group(1)
        assert p.startswith("docs/") or p.startswith("fo_") or p.startswith("A9-"), p


def test_markdown_sections():
    md = MD_PATH.read_text(encoding="utf-8")
    for h in ("## (a) Revision register", "## (a) New A9 items", "## (b) Interface demands",
              "## (c) Owner answers applied", "## (d) Open owner questions", "## (e) Historical reuse",
              "## (f) M16 impact", "## (g) H3 inputs"):
        assert h in md, h


def test_abort_list_is_limit_minus_50K(doc):
    """IDA7-16 (to A9-01): aborts are limit - 50 K (UBQ-06, row 86), never the limit itself (review finding)."""
    d = [x for x in doc["interface_demands"] if x["id"] == "IDA7-16"][0]
    assert d["to"].startswith("A9-01")
    lim = doc["recomputations"]["h25_thermal_rerun"]["limits"]
    assert set(d["value"]) == {k for k in lim if k != "rule"}
    for k, v in d["value"].items():
        if lim[k].get("limit_C") is not None:
            assert v["limit_C"] == lim[k]["limit_C"]
            assert math.isclose(v["abort_C"], lim[k]["limit_C"] - 50.0, abs_tol=1e-3), k
        else:
            assert isinstance(v["abort_C"], str) and v["abort_C"].startswith("TBD - requires"), k
    assert d["value"]["BN_wall"]["abort_C"] == 850.0
    assert math.isclose(d["value"]["coil_ceramic"]["abort_C"], 487.778, abs_tol=1e-3)


def test_h2_4_flags_all_covered(doc):
    bpb = json.loads((REPO / "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json")
                     .read_text(encoding="utf-8"))
    rev = {r["id"]: r for r in doc["revision_register"]}
    cov = {c["h2_4_id"]: c for c in doc["h2_4_flag_coverage"]}
    for f in bpb["h2_4_revision_flags"]:
        c = cov[f["h2_4_id"]]
        assert c["a9_02_disposition"] == f["disposition"]
        if f["disposition"] in ("RETAINED", "RETAINED_AS_CANDIDATE"):
            assert c["covered_by"] == []
        else:
            assert c["covered_by"] and all(r in rev for r in c["covered_by"]), f["h2_4_id"]
    # H24-33 re-derived on the 100 V internal bus (row 111)
    r67 = [r for r in doc["revision_register"] if r["h2_item"] == "H24-33"][0]
    cur = r67["new"]["value"]["internal_bus_current_upper_bound_at_nominal_100V_A"]
    assert cur == {"1300 W": 13.0, "1350 W": 13.5, "1500 W": 15.0}
    assert "UPPER BOUND" in r67["new"]["requirement"]
    assert r67["new"]["value"]["internal_bus_current_upper_bound_at_V_bus_min_A"].startswith("TBD - requires")
    # REV-52: the partition defers to the full A9-02 slot list
    r52 = [r for r in doc["revision_register"] if r["h2_item"] == "OQ-H24-03"][0]
    assert r52["new"]["value"] == [x["slot"] for x in bpb["slots"]]
    for slot in ("icp_assist_magnet", "filter_getter", "active_cooling", "flow_control_icp_feed"):
        assert slot in r52["new"]["value"]


def test_minimal_levers_and_buildability(doc):
    th = doc["recomputations"]["h25_thermal_rerun"]
    icp = th["results"]["hall_icp_neutralizer"]
    ok85 = set(th["row85_compatible_levers_100W"])
    for n in ("WI", "WO", "CI", "CO"):
        s = th["closure_summary_hall_icp_neutralizer"][n]
        closing = [lv for lv in th["levers"] if lv != "LV-BASE" and
                   all(_sens(icp[lv][c]["nodes"][n], "verdict") == "CLOSES" for c in icp[lv])]
        assert closing == s["levers_that_close_every_case"], n
        good = [lv for lv in closing if lv in ok85]
        m = s["minimal_closing_within_row85_100W"]
        if good:
            k = min(len(th["levers"][lv]["parts"]) for lv in good)
            assert m["lever_count"] == k
            assert [x["lever"] for x in m["sets"]] == [lv for lv in good if len(th["levers"][lv]["parts"]) == k]
        else:
            assert m["sets"] == []
    # single levers are also evaluated with the isolated mount (review finding)
    for lv in ("LV-OPEN+ISO", "LV-RAD+ISO", "LV-COIL+ISO", "LV-COND+ISO", "LV-BN+ISO"):
        assert lv in th["levers"]
    assert th["levers"]["LV-COIL"]["buildability"]["status"] == "NOT_DEMONSTRATED"
    assert "combination" in th["levers"]["LV-ALL-ISO"]["buildability"]
    assert all(v["buildability"]["status"] != "DEMONSTRATED" for v in th["levers"].values())


def test_search_bounds_random_points(builder):
    """Seeded random states of the hottest baseline box never exceed the reported searched maximum + allowance."""
    import random
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    th = doc["recomputations"]["h25_thermal_rerun"]
    M5 = builder.h25()
    rows = M5.build_parameters()
    pm = M5.param_map(rows)
    fx = M5.fixed_inputs(pm)
    rg = builder._ranges(pm, "orbit_hot", "hall_icp_neutralizer", 60.0, "LV-BASE", th["coil_conductor_factor"]["factor"])
    rec = th["results"]["hall_icp_neutralizer"]["LV-BASE"]["orbit_hot@T_mount=60C"]
    alw = th["search"]["allowance_K"]
    rnd = random.Random(7)
    for _ in range(25):
        x = {k: (lo if lo == hi else rnd.choice((lo, hi, rnd.uniform(lo, hi)))) for k, (lo, hi) in rg.items()}
        T, _ = builder._run(x, fx, "orbit_hot", builder.FINISH_BASE, pm["P_d_max_W"]["value"])
        for n in ("WI", "WO", "CI", "CO", "PI", "PO", "BP"):
            assert T[n] - 273.15 <= rec["nodes"][n]["T_max_C"] + alw + 0.05, n
        assert T["Q_mount_W"] <= rec["Q_mount_W"]["max_W"] + th["search"]["allowance_W"] + 0.05


def test_review_fixes_documented(doc):
    th = doc["recomputations"]["h25_thermal_rerun"]
    assert th["limits"]["exterior_coating"]["limit_C"] is None
    assert set(th["limits"]["exterior_coating"]["nodes"]) == {"PO", "BP"}
    q = {x["id"] for x in doc["open_owner_questions"]}
    assert {"OQ-A907-08", "OQ-A907-09"} <= q
    assert "EXTENDS" in [r for r in doc["revision_register"] if r["h2_item"] == "H25-36"][0]["new"]["requirement"]
    assert "NOT a verdict" in th["hall_c1_reference_note"]
    d1 = [x for x in doc["interface_demands"] if x["id"] == "IDA7-01"][0]
    assert "LV-COIL_copper_delta_kg" in d1["value"] and "lower_bound" not in json.dumps(d1["value"])
    assert d1["value"]["LV-COIL_mass_to_book_kg"].startswith("TBD - requires")
    assert d1["value"]["LV-RAD_mass_delta_kg"].startswith("TBD - requires")


def test_icp_heat_conditions_and_verified_allowances(doc):
    """Review finding (major): every hall_icp_neutralizer CLOSES is conditional on the ICP-43 heat into H-1, with the
    row-86 1.2 margin applied to that heat; allowances are verified by re-solving the network."""
    th = doc["recomputations"]["h25_thermal_rerun"]
    icp = th["results"]["hall_icp_neutralizer"]
    for lv, cases in icp.items():
        for c, rec in cases.items():
            for n, e in rec["nodes"].items():
                if _sens(e, "verdict") == "CLOSES":
                    assert "1.2 x Q_ICP->H-1" in e["closes_conditional_on"], (lv, c, n)
                    assert isinstance(e["search_sensitive"], bool)
                    assert e["search_sensitive"] == (e["margin_to_design_ceiling_K"] < 10.0)
                assert "domain_flags_at_T_max_state" in e
    assert any("ICP-43" in x for x in th["overall"]["open_items"])
    assert "1.2 x Q_ICP->H-1" in th["overall"]["status_conditional_on"]
    ih = th["icp_heat_into_h1"]
    assert "super-linear, so the allowance is an upper estimate" not in ih["note"]
    for lv, cases in ih["per_lever_and_case"].items():
        for c, per in cases.items():
            for n, v in per.items():
                for inj in ("PO", "BP"):
                    lin = v["Q_ICP_allowable_W_linearised_incl_row86_margin"][inj]
                    ver = v["Q_ICP_allowable_W_verified_incl_row86_margin"][inj]
                    assert 0.0 <= ver <= lin + 1e-9
                    if lin > 0:
                        chk = v["resolve_check_at_1_2_x_allowable"][inj]
                        if chk["within_ceiling_after_allowance"]:
                            assert ver == lin
                        else:
                            assert ver == chk["verified_by_bisection_W"]
                    # the 1.2 margin is inside the linearised allowance
                    if lin > 0 and v["dT_dQ_K_per_W"][inj] > 0:
                        assert math.isclose(lin * 1.2 * v["dT_dQ_K_per_W"][inj], v["headroom_to_ceiling_K"],
                                            rel_tol=2e-2, abs_tol=0.2)
        for inj in ("PO", "BP"):
            for n in ("WI", "WO", "CI", "CO"):
                assert ih["min_allowance_W"][lv][inj][n] == min(
                    per[n]["Q_ICP_allowable_W_verified_incl_row86_margin"][inj] for per in cases.values())
    for n in ("WI", "WO", "CI", "CO"):
        s = th["closure_summary_hall_icp_neutralizer"][n]
        assert _sens(s, "brief_verdict_at_baseline") == ("CLOSES" if _sens(s, "status") == "CLOSES" else "DO_NOT_CLOSE")
        closers = (["LV-BASE"] if _sens(s, "status") == "CLOSES" else []) + s["levers_that_close_every_case"]
        assert sorted(s["icp_heat_allowable_W_per_closing_lever_set"]) == sorted(closers)
    lc = ih["linearity_check"]
    assert lc["checks"] > 0 and lc["all_sub_linear_inside_domain"] is True


def test_anode_design_driver_and_wording_fixes(doc):
    th = doc["recomputations"]["h25_thermal_rerun"]
    an = th["closure_summary_hall_icp_neutralizer"]["AN"]
    assert an["brief_verdict_at_baseline"] == "OPEN_LIMIT_TBD"
    icp = th["results"]["hall_icp_neutralizer"]
    lows = [max(icp[lv][c]["nodes"]["AN"]["T_max_C"] for c in icp[lv]) for lv in th["levers"]]
    assert an["design_driver"]["lowest_worst_case_over_lever_sets_C"]["T_max_C"] == min(lows)
    assert "DESIGN DRIVER" in an["design_driver"]["statement"]
    assert "anode" in doc["hard_incompatibility_check"]["not_covered"]
    reg = {r["id"]: r for r in doc["revision_register"]}
    for rid in ("REV-18", "REV-46"):
        t = reg[rid]["new"]["requirement"]
        assert "SENSITIVITY" in t and "conservative bound" not in t, rid
    d1 = [x for x in doc["interface_demands"] if x["id"] == "IDA7-01"][0]["quantity"]
    assert "STAYS in the flight BOM (rows 55, 90)" in d1
    assert "OQ-A907-10" in {x["id"] for x in doc["open_owner_questions"]}


def test_h21_worst_corner_uses_window_capability(doc):
    h1 = doc["recomputations"]["h21_central_bore"]
    for r in h1["rows"]:
        f = r["external_c1_magnetic_floor_mm"]
        assert f["nominal_assumptions"] <= f["upper_assumptions_own_width_capability_f_NI_1"] <= f["worst_case_assumptions"]
    assert h1["inputs"]["window_wide_capability_G"] > 0


# ---------------------------------------------------------------------------------------------------------------------
# review repair 3
# ---------------------------------------------------------------------------------------------------------------------
def test_rf_reference_plane_relations_independent(doc):
    """Review finding (major): forward/reflected/net power, VSWR and peak voltage at the coupler plane after the match."""
    rf = doc["recomputations"]["rf_reference_plane"]
    z0 = 50.0
    for name, v in rf["sensitivity_loads"].items():
        z = complex(*v["Z_load_ohm"])
        g = abs((z - z0) / (z + z0))
        assert math.isclose(v["gamma_mag"], g, rel_tol=1e-3, abs_tol=1e-9), name
        pf = 500.0 / (1 - g * g)
        assert math.isclose(v["P_fwd_W"], pf, rel_tol=1e-3), name
        assert math.isclose(v["V_pk_max_V"], math.sqrt(2 * pf * z0) * (1 + g), rel_tol=1e-3), name
        if g > 0:
            assert math.isclose(v["VSWR"], (1 + g) / (1 - g), rel_tol=1e-3), name
        assert v["evidence_class"].startswith("assumed (sensitivity case")
    r = rf["sensitivity_loads"]["review_case_20+j50"]
    assert math.isclose(r["VSWR"], 5.2, rel_tol=0.01) and 900 < r["P_fwd_W"] < 950 and 490 < r["V_pk_max_V"] < 530
    # no rating is taken from the sensitivity loads
    for opt in rf["options"].values():
        for k, val in opt["ratings"].items():
            assert str(val).startswith("TBD - requires"), k
    items = {i["id"]: i for i in doc["new_items"]}
    assert {"A9H-INS-14", "A9H-INS-15", "A9H-INS-16"} <= set(items)
    assert items["A9H-INS-01"]["value"]["coupler_plane_P_fwd_max_W"].startswith("TBD - requires")
    ids = {x["id"]: x for x in doc["interface_demands"]}
    assert ids["IDA7-20"]["from"].startswith("A9-03") and ids["IDA7-21"]["to"].startswith("A9-04")
    assert "OQ-A907-11" in {q["id"] for q in doc["open_owner_questions"]}


def test_two_port_and_directivity_helpers(builder):
    # lossless matched line: all net power reaches the load
    assert math.isclose(builder.two_port_load_power_ratio(0, 1, 1, 0, 0.5 + 0.3j), 1.0, rel_tol=1e-12)
    # 1 dB lossy line into a mismatched load: part of the net power is dissipated in the line
    s21 = 10 ** (-1 / 20)
    r = builder.two_port_load_power_ratio(0, s21, s21, 0, 0.9)
    assert 0 < r < 1
    assert builder.directivity_error_rel(0.0, 20.0) == pytest.approx(0.01)
    with pytest.raises(ValueError):
        builder.rf_mismatch(500.0, 1.0)


def test_lv_coil_copper_delta_consistent_geometry(doc):
    """Review finding (major): P x m_cu is invariant at fixed NI and mean turn; no lower-bound claim."""
    lc = doc["recomputations"]["lv_coil_copper_delta"]
    cd = lc["coil_definition"]
    P, m = cd["P_RP1_20C_W"], cd["m_RP1_kg"]
    for c in cd["coils"].values():
        k = 1.7241e-8 * 8890.0 * (c["NI_A"] * c["mean_turn_m"]) ** 2
        assert math.isclose(c["P20_W"] * c["Cu_mass_kg"], k, rel_tol=0.01)
    b60 = lc["bases"]["P_mag_basis_60W_H25-08_upper"]
    assert b60["P_mag_20C_W"] == 60.0
    assert math.isclose(b60["LV-COIL_copper_delta_kg"], m * P / 60.0, rel_tol=2e-3)
    assert 0.13 < b60["LV-COIL_copper_delta_kg"] < 0.145
    assert "lower bound" not in json.dumps(lc).replace("not a bound", "")


def test_em_only_pmag_floor_and_labels(doc, builder):
    th = doc["recomputations"]["h25_thermal_rerun"]
    M5 = builder.h25()
    pm = M5.param_map(M5.build_parameters())
    rg = builder._ranges(pm, "orbit_hot", "hall_icp_neutralizer", 60.0, "LV-BASE", th["coil_conductor_factor"]["factor"])
    assert rg["P_mag_W"][0] == builder.em_only_pmag_floor_W() > 0.0
    # IDA7-03 is an ignition-dwell-only bound
    d3 = [x for x in doc["interface_demands"] if x["id"] == "IDA7-03"][0]
    assert d3["value"]["scope"] == "IGNITION_DWELL_ONLY" and "ignition dwell only" in d3["units"]
    # REV-38 states old and new units
    r38 = [r for r in doc["revision_register"] if r["id"] == "REV-38"][0]
    assert "old: uN" in r38["units"] and "k = 1" in r38["units"]
    # every hall_icp_neutralizer CLOSES carries the radiative-view condition
    for lv, cases in th["results"]["hall_icp_neutralizer"].items():
        for c, rec in cases.items():
            for n, e in rec["nodes"].items():
                if _sens(e, "verdict") == "CLOSES":
                    assert "view" in e["closes_conditional_on_view"], (lv, c, n)
    assert "ICP-05" in th["overall"]["status_conditional_on_view"]
    an = th["closure_summary_hall_icp_neutralizer"]["AN"]["design_driver"]
    assert "316L" in an["statement"] and "verify" in an["anode_316L_note"]["316L_melting_range_C_approx"]
    md = MD_PATH.read_text(encoding="utf-8")
    assert "sensitivity outcome (not a verdict)" in md and "Recomputation 3" in md and "Recomputation 4" in md


def test_a9_2_incorporation(doc):
    """A9.2 (owner decisions 2026-09-30): coupled thermal UNRESOLVED, local match, anode blockers, coil-mass wording."""
    th = doc["recomputations"]["h25_thermal_rerun"]
    for lv, cases in th["results"]["hall_icp_neutralizer"].items():
        for c, rec in cases.items():
            for n, e in rec["nodes"].items():
                assert e["verdict"] not in ("CLOSES", "PASS"), (lv, c, n)
                assert e.get("necessary_check") != "PASS", (lv, c, n)
    for n, s in th["closure_summary_hall_icp_neutralizer"].items():
        assert not str(s["status"]).startswith("CLOSES") and s["brief_verdict_at_baseline"] != "CLOSES", n
    ct = th["a9_2_icp_coupled_thermal"]
    assert ct["ICP_COUPLED_THERMAL"] == "UNRESOLVED" and ct["coupled H-1/ICP thermal closure"] == "UNRESOLVED"
    assert ct["pole_allowance_warning"]["value_W"] == th["icp_heat_into_h1"]["min_allowance_W"]["LV-BASE"]["PO"]["CO"]
    assert "ignore" in ct["prohibited_assumption"]
    an = th["closure_summary_hall_icp_neutralizer"]["AN"]["a9_2_anode"]
    assert an["ANODE_BASELINE"] == "OPEN" and an["316L flight anode"] == "REJECTED_AS_CURRENT_BASELINE"
    ids = {x["id"]: x for x in doc["new_items"]}
    for i in ("A9H-ANODE-01", "A9H-ANODE-02", "A9H-RF-LM-01", "A9H-RF-PROT-01", "A9H-TH-01"):
        assert ids[i]["value"].startswith("TBD - requires"), i
    assert ids["A9H-INS-14"]["status"] == "SUPERSEDED_BY_A9_2"
    q = {x["id"]: x for x in doc["open_owner_questions"]}
    assert q["OQ-A907-11"]["status"] == "ANSWERED_BY_A9_2 (OQ-A907-11)"
    rp = doc["recomputations"]["rf_reference_plane"]
    assert "LOCAL matching network" in rp["reference_plane"] and "A9.1 A9-03-matching" in rp["reference_plane_before_a9_2"]
    assert rp["options"]["a_on_module_pre_match"]["status"].startswith("SUPERSEDED_BY_A9_2")
    assert rp["sensitivity_loads"]["review_case_20+j50"]["P_fwd_W"] == 925.0      # numbers unchanged
    assert "NOT the MC-1 coil mass" in doc["recomputations"]["lv_coil_copper_delta"]["a9_2_coil_mass_correction"]["text"]
    assert "alternative estimates" in doc["key_findings"][11]
