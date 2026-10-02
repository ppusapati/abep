"""Tests for the A9 mass + power integration v3 (A9.16 step 1: owner decisions A9.14 / A9.15 applied).

Checks reproducibility, immutability of v2, verbatim-checked owner-decision citations (file + json sha256 + question id),
the single MEV reading with the 20 % system margin replacing the 4 kg reserve (24 -> 4.8 -> 28.8 kg), the rebased AL-04 /
AL-07 / AL-08 planning floors, the controls / harness split, the decided BOM mappings, LOADED Xe with the residual never
added again, the evidence-based dry / wet totals vs 40 kg with every TBD and the redesign need (no margin relaxation),
C1 option (c) and the RFP-required Xe hardware in both configurations, and the new peak_sampled gate helper
(OQ-A910-03) with its refusals.
A9.19 / A9.20: the single flight configuration hall_icp_neutralizer (no conventional hollow cathode), no AL-C1 / C1
electronics / C1 Xe branch in any flight roll-up, the pre-A9.19 C1 column kept only as labelled history, C1 BOM items
GROUND_ONLY_LAB_EQUIPMENT, AL-08 REQUIRED_RFP_XE_CAPABILITY with role CONTINGENCY_EMERGENCY, flight roll-ups
numerically unchanged vs the pre-A9.19 commit.
Run: python -m pytest -q tests/test_mass_power_a9_v3.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "mass_power_a9_v3"
BUILDER = LANE / "build_mass_power_a9_v3.py"
HELPER = LANE / "peak_sampled_gate_a9_v3.py"
JSON_PATH = LANE / "mass_power_a9_v3.json"
MD_PATH = LANE / "MASS_POWER_A9_V3.md"
V2 = {
    "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json":
        "c1a7875fdd0e27b3425cc02ba915ab61bcf9760ac032d294b69a887a91e78459",
    "docs/budgets/mass_power_a9_v2/MASS_POWER_A9_V2.md":
        "6032ca8c15798460e6a67913c14a0413e12e3f4698730152a33f79d4230bba4e",
    "docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py":
        "88a4f0878ba388f8a792138ee5625f83a087fc069dd67049e883a96e0701481b",
    "abep_sim/bus_boundary_a9.py": "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a",
}
DEC_SHA = {"A9.12": "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d",     # A9.16 repair F5
           "A9.14": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
           "A9.15": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
           "A9.19": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
           "A9.20": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6"}
REQUIRED = [("A9.14", q) for q in ("MQ-01", "MQ-02", "MQ-03", "MQ-04", "MQ-05", "MQ-06", "MQ-07", "MQ-09", "MQ-10",
                                    "XA9Q-01", "OQ-A910-01", "MPQ-01", "MPQ-02", "OQ-A907-07", "XA9Q-07", "XV2Q-01",
                                    "OQ-A910-05", "OQ-A910-03")] + \
           [("A9.15", q) for q in ("governing_rule", "MPQ-01", "OQ-A907-07", "XA9Q-07", "XV2Q-01")] + \
           [("A9.19", q) for q in ("architecture", "xenon_role", "A9.15", "A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07",
                                    "A9 C1 CONTROL_FALLBACK")] + [("A9.20", "answer")]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m():
    return _load(BUILDER, "build_mass_power_a9_v3_under_test")


@pytest.fixture(scope="module")
def h():
    return _load(HELPER, "peak_sampled_gate_a9_v3_under_test")


@pytest.fixture(scope="module")
def d():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _roll(d, cfg):
    rr = d["rollups"] + d["retired_flight_configuration_history"]["rollups"]
    return next(r for r in rr if r["configuration"] == cfg)


def _line(d, cfg, lid):
    ll = dict(d["lines"], **d["retired_flight_configuration_history"]["lines"])
    return next(x for x in ll[cfg] if x["line"] == lid)


def test_builder_check_reproduces():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_json_md_consistent(d, m):
    js, md = m.render()
    assert json.loads(js) == d
    assert MD_PATH.read_text(encoding="utf-8") == md


def test_v2_and_bus_module_untouched(d):
    for rel, hh in V2.items():
        assert _sha(REPO / rel) == hh, rel
    assert d["power"]["peak_sampled_rule_v3"]["helper_sha256"] == _sha(HELPER)


def test_pin_mismatch_aborts(m, monkeypatch):
    bad = dict(m.DECISIONS)
    bad["A9.14"] = dict(bad["A9.14"], md_sha256="0" * 64)
    monkeypatch.setattr(m, "DECISIONS", bad)
    with pytest.raises(m.PinError):
        m.verify_pins()


def test_code_hygiene():
    for p in (BUILDER, HELPER, Path(__file__)):
        assert ("xe" + "_ledger") not in p.read_text(encoding="utf-8"), p.name
    for banned in ("import archengine", "hall_map", "hall_ensemble", "plasma_devices", "julia"):
        assert banned not in BUILDER.read_text(encoding="utf-8")


def test_every_required_decision_cited(d):
    got = {(r["key"], r["id"]) for r in d["owner_answers_applied"]}
    for k in REQUIRED:
        assert k in got, k
    for r in d["owner_answers_applied"]:
        assert r["json_sha256"] == DEC_SHA[r["key"]]
        md = " ".join((REPO / r["path"]).read_text(encoding="utf-8").split())
        assert " ".join(r["quote"].split()) in md, (r["key"], r["id"])


# ------------------------------------------------------------------------------------ MQ-01 / MQ-02 / MQ-10
def test_single_mev_reading_no_second_margin(m, d):
    v = m.line_mev_value(3.5)
    assert v == {"value_kg": 3.5, "governs": "ALLOCATION_MEV", "candidates": [{"basis": "ALLOCATION_MEV", "kg": 3.5}]}
    assert m.line_mev_value(3.0, None, 3.504)["value_kg"] == 4.2048          # heavier floor overrides
    assert m.line_mev_value(10.0, None, 3.504)["governs"] == "ALLOCATION_MEV"
    assert m.line_mev_value(2.5, 4.0, 5.0)["value_kg"] == 4.8              # a CBE replaces the floor
    assert m.line_mev_value()["value_kg"] is None                           # nothing -> TBD, never 0
    with pytest.raises(m.MassError):
        m.line_mev_value(1.0, equipment_margin=0.1)
    with pytest.raises(m.MassError):
        m.line_mev_value(-1.0)
    assert "MQ01_CBE_LEVEL (second row-57 margin)" in d["margin_convention"]["retired_v2_readings"]
    assert {r["reading"] for r in d["rollups"]} == {"MEV_LEVEL_EVIDENCE_BASED (the single owner reading)"}


def test_system_margin_replaces_reserve_24_48_288(m, d):
    assert m.system_margin(24.0) == {"pre_margin_kg": 24.0, "system_margin_kg": 4.8, "total_kg": 28.8}
    b = d["budget_reference"]
    assert (b["row54_allocation_sum_kg"], b["system_margin_kg"], b["dry_budget_kg"]) == (24.0, 4.8, 28.8)
    with pytest.raises(m.MassError):
        m.system_margin(24.0, reserve_kg=4.0)                                # never both
    with pytest.raises(m.MassError):
        m.system_margin(24.0, fraction=0.1)                                  # MQ-10: no relaxation
    for r in d["rollups"]:
        assert r["reserve_kg"] == 0.0
        assert abs(r["system_margin_kg"] - 0.2 * r["nominal_dry_known_kg"]) < 1e-6   # recomputed, not frozen 4.8
    items = {i["id"]: i for i in d["items_v2"]}
    assert items["MA-RES"]["v3_status"].startswith("RETIRED")


def test_no_margin_relaxation_refused(m):
    ok = {"allocations": "MEV", "system_margin": 0.2, "reserve_kg": 0.0, "xe_case": "LOADED"}
    m.assert_no_margin_relaxation(ok)
    for bad in (dict(ok, system_margin=0.1), dict(ok, allocations="CBE"), dict(ok, reserve_kg=4.0),
                dict(ok, xe_case="USABLE_RESIDUAL_ON_TOP")):
        with pytest.raises(m.MassError):
            m.assert_no_margin_relaxation(bad)


# ------------------------------------------------------------------------------------ MQ-03 / 04 / 05 / 06
def test_rebased_planning_floors(d):
    for cfg in ("hall_icp_neutralizer", "hall_c1_reference"):           # flight column + the history column
        for lid, kg in (("AL-04", 4.2048), ("AL-07", 6.0), ("AL-08", 6.0528)):
            ln = _line(d, cfg, lid)
            assert ln["value"]["value_kg"] == kg and ln["value"]["governs"] == "MEV_PLANNING_FLOOR"
            assert ln["owner_mev_planning_floor_kg"] == kg and ln["cbe_kg"] is None
    tbd = " ".join(_roll(d, "hall_icp_neutralizer")["tbd"])
    assert "AL-04: floor INCOMPLETE" in tbd and "AL-08: floor INCOMPLETE" in tbd


def test_controls_harness_split(m, d):
    ctrl = _line(d, "hall_icp_neutralizer", "AL-09")
    assert ctrl["row54_allocation_kg"] is None and ctrl["row54_combined_allocation_kg"] == 1.0
    assert ctrl["value"]["value_kg"] is None and "MPV3Q-01" in ctrl["allocation_status"]
    r = _roll(d, "hall_icp_neutralizer")
    assert "AL-09" in r["lines_without_value"]
    har = next(p for p in r["parts"] if p["line"] == "AL-HAR")
    assert har["kg"] == m.harness_row60(r["nonharness_known_kg"]) and har["partial"] is True
    assert abs(m.harness_row60(19.0) - 1.0) < 1e-12
    with pytest.raises(m.MassError):
        m.harness_row60(10.0, fraction=0.03)
    assert any(q["id"] == "MPV3Q-01" and q["status"] == "OPEN" for q in d["open_owner_questions"])


def test_bom_mappings_exact(d):
    bom = {x["id"]: x for x in d["bom"]}
    want = {"A9B-18": "AL-05", "A9B-22": "AL-07", "A9B-21": "AL-06", "A9B-20": "AL-06", "A9B-26": "AL-09",
            "A9B-29": "AL-09", "A9B-27": "AL-09", "A9B-28": "AL-HAR", "A9B-08": "AL-08", "A9B-12": "AL-08",
            "MPV2-N01": "AL-05", "MPV2-N02": "AL-06", "MPV2-N03": "AL-04", "MPV2-N04": "AL-10"}
    for iid, line in want.items():
        assert bom[iid]["allocation_line"] == line, iid
        assert bom[iid]["allocation_mapping"].startswith("OWNER_MAPPING"), iid
    assert not any("PROPOSED_MAPPING" in x["allocation_mapping"] for x in d["bom"] if x["allocation_mapping"])
    # A9.19 / A9.20: the pre-A9.19 C1 flight mappings survive only as history
    pre = {"A9B-C01": "AL-C1", "A9B-C02": "AL-C1", "A9B-C05": "AL-C1", "A9B-C03": "AL-07", "A9B-C04": "AL-08",
           "A9B-C07": "AL-09"}
    for iid, line in pre.items():
        assert bom[iid]["allocation_line_pre_a9_19"] == line, iid
        assert bom[iid]["allocation_line"] == "GROUND_ONLY_LAB_EQUIPMENT", iid


# ------------------------------------------------------------------------------------ Xe (LOADED, RFP) and C1
def test_loaded_xe_residual_never_added(d):
    for r in d["rollups"]:
        for w in r["wet"]:
            assert w["residual_added_on_top_kg"] == 0.0
            assert w["xe_loaded_kg"] == w["xe_case_kg"]
            assert abs(w["wet_known_kg"] - (r["dry_known_kg"] + w["xe_case_kg"])) < 1e-9
    assert d["xe_v3_import"]["reading"] == "LOADED"


def test_xe_import_refuses_non_loaded(m, monkeypatch):
    real = m._load

    def fake(rel):
        doc = real(rel)
        if rel == m.XE_V3:
            doc = json.loads(json.dumps(doc))
            doc["design_cases"]["loaded_split"]["rows"][0]["loaded_kg"] = 2.04
        return doc
    monkeypatch.setattr(m, "_load", fake)
    with pytest.raises(m.MassError):
        m.import_xe(m.S())


def test_xe_hardware_rfp_required_flight_config_contingency_role(m, d):
    assert m.CONFIGS == ("hall_icp_neutralizer",)
    r = m.xe_hardware_required("hall_icp_neutralizer")
    assert r["AL-08"] == "REQUIRED_RFP_XE_CAPABILITY" and r["xe_role"] == "CONTINGENCY_EMERGENCY"
    assert set(r["rfp_clauses"]) == {"RFP-P17-05", "RFP-P18-08"}
    al08 = _line(d, "hall_icp_neutralizer", "AL-08")
    assert al08["value"]["value_kg"] == 6.0528 and al08["xe_role"] == "CONTINGENCY_EMERGENCY"
    assert al08["c1_branch"] == {"state": "NO_C1_XE_BRANCH_IN_FLIGHT (A9.19 / A9.20)", "in_AL08": False}
    for bad in ("xe_free", "hall_c1_reference"):
        with pytest.raises(m.MassError):
            m.xe_hardware_required(bad)
    bom = {x["id"]: x for x in d["bom"]}
    assert bom["A9B-07"]["configurations"] == {"hall_icp_neutralizer": "INSTALLED"}
    assert bom["A9B-07"]["rfp_required_flight_configuration"] is True and bom["A9B-07"]["xe_role"] == XE_ROLE
    assert d["open_register_status"]["XV2Q-01"] == "NOT_APPLICABLE"
    xr = d["propellant_policy"]["xenon_role"]
    assert xr["role"] == "CONTINGENCY_EMERGENCY" and "A9.19 xenon_role" in xr["source"]
    assert "G-REUSE primary" in d["propellant_policy"]["icp_feed_gas_baseline"]


XE_ROLE = "CONTINGENCY_EMERGENCY"


def test_c1_never_flight_ground_only(m, d):
    assert m.al_c1_allocation() == {"state": "NOT_IN_FLIGHT_ARCHITECTURE_A9_19_A9_20", "kg": None}
    for bad in ((True,), (False, 0.5), ("yes",)):
        with pytest.raises(m.MassError):
            m.al_c1_allocation(*bad)
    assert m.c1_xe_branch_booking() == {"state": "NO_C1_XE_BRANCH_IN_FLIGHT (A9.19 / A9.20)", "in_AL08": False}
    with pytest.raises(m.MassError):
        m.c1_xe_branch_booking(True)
    # no C1 in any flight line / roll-up / power configuration
    assert set(d["lines"]) == {"hall_icp_neutralizer"} and [r["configuration"] for r in d["rollups"]] == \
        ["hall_icp_neutralizer"]
    assert "AL-C1" not in {x["line"] for x in d["lines"]["hall_icp_neutralizer"]}
    al07 = _line(d, "hall_icp_neutralizer", "AL-07")
    assert al07["c1_electronics"].startswith("NOT_BOOKED") and "C1 heater" not in al07["name"]
    assert set(d["power"]["configurations"]) == {"hall_icp_neutralizer"}
    flight = json.dumps({"lines": d["lines"], "rollups": d["rollups"], "power": d["power"]["configurations"]})
    assert "c1_heater" not in flight and "c1_keeper" not in flight
    with pytest.raises(m.MassError):
        m.build_lines(json.loads(json.dumps({"lines": {}})), m.S(), ("hall_c1_reference",))
    # C1 BOM items are ground-only lab equipment
    bom = {x["id"]: x for x in d["bom"]}
    for iid in ("A9B-C01", "A9B-C02", "A9B-C03", "A9B-C04", "A9B-C05", "A9B-C06", "A9B-C07"):
        assert bom[iid]["allocation_line"] == "GROUND_ONLY_LAB_EQUIPMENT" and bom[iid]["classification"] == \
            "GROUND_ONLY_LAB_EQUIPMENT", iid
        assert bom[iid]["configurations"] == {"hall_icp_neutralizer": "NOT_INSTALLED",
                                              "ground_lab_reference": "GROUND_ONLY_LAB_EQUIPMENT (A9.20)"}, iid
    ga = {g["id"]: g for g in d["ground_article_only"]}
    assert "GROUND_ONLY" in ga["GA-01"]["a9_20_rule"]
    items = {i["id"]: i for i in d["items_v3"]}
    assert items["MPV3-05"]["status"].startswith("RETIRED_FROM_FLIGHT") and items["MPV3-05"]["value"] is None


def test_c1_history_column_labelled_and_unchanged(d):
    h = d["retired_flight_configuration_history"]
    assert h["label"].startswith("HISTORY") and h["pre_a9_19_commit"] == "f55abf6222c12f07c81c09194df9051e3a297d10"
    c1 = _line(d, "hall_c1_reference", "AL-C1")
    assert c1["value"]["value_kg"] is None and c1["a9_19_status"].startswith("RETIRED_FROM_FLIGHT")
    r = _roll(d, "hall_c1_reference")
    assert r["note"].startswith("HISTORY") and "AL-C1" in r["lines_without_value"]
    assert r["nonharness_known_kg"] == 28.7576 and abs(r["dry_known_kg"] - 36.32538948) < 1e-9
    assert d["configurations"]["hall_c1_reference"].startswith("RETIRED")
    assert "hall_c1_reference" in d["power"]["retired_flight_configuration_history"]["configurations"]


def test_flight_rollup_unchanged_and_c1_mass_check(d):
    f = d["flight_rollup_vs_40kg"]
    assert [x["configuration"] for x in f] == ["hall_icp_neutralizer"]
    assert f[0]["dry_known_kg"] == 40.7464421 and f[0]["numerically_unchanged_vs_pre_a9_19"] is True
    assert f[0]["wet_known_kg_by_loaded_case"] == {"2.0": 42.7464421, "5.0": 45.7464421, "10.0": 50.7464421}
    assert set(f[0]["hard_40_wet_state_by_loaded_case"].values()) == {"DOES_NOT_CLOSE"}
    c = d["c1_mass_check"]
    assert c["owner_request"] == "check C1 mass" and c["v2_c1_evidence_floor_kg"] == 0.2
    assert c["v2_c1_floor_is_partial"] is True and "A9.19" in c["source"]


def test_local_match_al06_and_sham(d):
    bom = {x["id"]: x for x in d["bom"]}
    assert bom["A9B-20"]["allocation_line"] == "AL-06"
    ga = {g["id"]: g for g in d["ground_article_only"]}
    assert "local-match parasitics" in ga["GA-03"]["v3_rule"] and "TBD" in ga["GA-03"]["v3_rule"]


# ------------------------------------------------------------------------------------ evidence-based totals
def test_evidence_based_totals_vs_40kg(d):
    r = _roll(d, "hall_icp_neutralizer")
    assert r["nonharness_known_kg"] == 32.2576
    assert abs(r["dry_known_kg"] - 40.746442) < 1e-6
    hard = {w["xe_case_kg"]: w for w in r["wet"] if w["reference"] == "HARD_40_WET"}
    assert set(hard) == {2.0, 5.0, 10.0}
    for c, w in hard.items():
        assert w["state"] == "DOES_NOT_CLOSE"
        assert abs(w["exceedance_kg"] - (w["wet_known_kg"] - 40.0)) < 1e-9
        need = w["redesign_need"]["nonharness_nominal_reduction_kg_at_least"]
        assert abs(need - (32.2576 - (40.0 - c) * 0.95 / 1.2)) < 1e-6
    c1 = _roll(d, "hall_c1_reference")                                      # history column (pre-A9.19)
    c1hard = {w["xe_case_kg"]: w["state"] for w in c1["wet"] if w["reference"] == "HARD_40_WET"}
    assert c1hard == {2.0: "NOT_EVALUABLE", 5.0: "DOES_NOT_CLOSE", 10.0: "DOES_NOT_CLOSE"}
    for rr in d["rollups"] + d["retired_flight_configuration_history"]["rollups"]:
        assert rr["tbd"] and rr["all_terms_resolved"] is False
        assert "CLOSES" not in {w["state"] for w in rr["wet"]}


def test_closure_state_rules(m):
    assert m.closure_state(40.0, 40.0, True, False) == "DOES_NOT_CLOSE"
    assert m.closure_state(39.0, 40.0, True, False) == "NOT_EVALUABLE"
    assert m.closure_state(39.0, 40.0, True, True) == "CLOSES"
    assert m.closure_state(34.0, 34.0, False, False) == "NOT_EVALUABLE"
    with pytest.raises(m.MassError):
        m.closure_state(float("nan"), 40.0, True, False)


def test_statuses_never_pass(d):
    for grp in ("a9_2_statuses", "a9_6_fixed_statuses"):
        assert all("PASS" not in v for v in d["statuses"][grp].values())
    assert "PASS" not in json.dumps(d["rollups"])
    assert d["statuses"]["a9_6_fixed_statuses"]["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
    assert "NOT_EVALUABLE" in d["power"]["peak_sampled_rule_v3"]["state_today"]


# ------------------------------------------------------------------------------------ OQ-A910-03 helper
def _rec(**kw):
    r = {"peak_sampled_W": 1400.0, "sample_rate_Sa_s": 100e3, "bandwidth_Hz": 20e3, "anti_alias_documented": True,
         "synchronized": True, "no_saturation": True, "total_bus_power_reconstruction": True, "source": "synthetic"}
    r.update(kw)
    return r


def test_peak_below_limit_conformant_is_sufficient_pass(h):
    g = h.peak_sampled_gate(_rec())
    assert g["verdict"] == "PASS" and g["basis"] == "ONE_SIDED_SUFFICIENT_PEAK_SAMPLED_BELOW_LIMIT"


@pytest.mark.parametrize("bad", [dict(sample_rate_Sa_s=50e3), dict(bandwidth_Hz=10e3),
                                 dict(anti_alias_documented=False), dict(synchronized=False),
                                 dict(no_saturation=False), dict(total_bus_power_reconstruction=False)])
def test_nonconformant_record_not_evaluable(h, bad):
    g = h.peak_sampled_gate(_rec(**bad))
    assert g["verdict"] == "NOT_EVALUABLE" and g["nonconformance"]
    g2 = h.peak_sampled_gate(_rec(peak_sampled_W=1600.0, **bad))
    assert g2["verdict"] == "NOT_EVALUABLE"                                   # nonconformant: never FAIL either


def test_peak_at_or_above_limit_is_not_a_failure(h):
    g = h.peak_sampled_gate(_rec(peak_sampled_W=1500.0))
    assert g["verdict"] == "NOT_EVALUABLE"
    assert g["basis"] == "PEAK_AT_OR_ABOVE_LIMIT_IS_NOT_A_FAILURE_1MS_MAXIMUM_REQUIRED"


def test_one_ms_maximum_decides(h):
    n = 100                                                                   # 1 ms at 100 kSa/s
    spike = [1000.0] * 300 + [1800.0] * 10 + [1000.0] * 300                   # short spike: 1 ms mean 1080 W
    g = h.peak_sampled_gate(_rec(peak_sampled_W=1800.0), spike)
    assert g["verdict"] == "PASS" and g["basis"] == "P_BUS_1MS_MAX_FROM_SAMPLES"
    assert abs(g["P_bus_1ms_max_W"] - 1080.0) < 1e-9
    plateau = [1000.0] * 300 + [1600.0] * (2 * n) + [1000.0] * 300
    g2 = h.peak_sampled_gate(_rec(peak_sampled_W=1600.0), plateau)
    assert g2["verdict"] == "FAIL"


def test_helper_refusals(h):
    with pytest.raises(h.PeakGateError):
        h.peak_sampled_gate({k: v for k, v in _rec().items() if k != "no_saturation"})
    with pytest.raises(h.PeakGateError):
        h.peak_sampled_gate(_rec(extra=1))
    with pytest.raises(h.PeakGateError):
        h.peak_sampled_gate(_rec(peak_sampled_W=1400.0), [1000.0] * 200 + [1450.0])   # declared peak != samples
    with pytest.raises(h.PeakGateError):
        h.peak_sampled_gate(_rec(source=""))
    with pytest.raises(h.PeakGateError):
        h.rfp_power_gate_peak_sampled((_rec(), None), [])                    # start-up required


def test_overall_gate_combination(h):
    ok = (_rec(), None)
    assert h.rfp_power_gate_peak_sampled(ok, [ok])["verdict"] == "PASS"
    assert h.rfp_power_gate_peak_sampled(ok, [(_rec(peak_sampled_W=1550.0), None)])["verdict"] == "NOT_EVALUABLE"
    plateau = [1000.0] * 100 + [1600.0] * 200 + [1000.0] * 100
    assert h.rfp_power_gate_peak_sampled(ok, [(_rec(peak_sampled_W=1600.0), plateau)])["verdict"] == "FAIL"



def test_a9_16_repair_f5_f10_register_and_c1_dwell_wording():
    """A9.16 repair F5: OQ-A910-06 is OWNER_DECIDED (A9.12 S5.8, 600 W temporary then the P2-derived envelope).
    F10: the C1 keeper-ignition step books 3 dwells (1 + 2 retries) x 120 s = 360 s (A9.14 OQ-A907-01 / XA9Q-02); the
    retired '120 s x 2 retries' reading survives only as the v2 history field."""
    d = json.loads((REPO / "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json").read_text(encoding="utf-8"))
    st = d["open_register_status"]["OQ-A910-06"]
    assert st.startswith("OWNER_DECIDED (A9.12 S5.8") and "rf_thermal_basis" in st
    hist = d["power"]["retired_flight_configuration_history"]["configurations"]          # A9.19: history only
    step = [x for x in hist["hall_c1_reference"]["phases"]["startup"]["steps"]
            if x["step_id"] == "C-S4"][0]
    assert "3 dwells (1 + 2 retries) x 120 s = 360 s" in step["name"] and "120 s x 2" not in step["name"]
    assert "120 s x 2 retries" in step["name_v2"]
    applied = {(a["key"], a["id"]) for a in d["owner_answers_applied"]}
    assert {("A9.12", "OQ-A910-06"), ("A9.14", "OQ-A907-01"), ("A9.14", "XA9Q-02")} <= applied
    txt = json.dumps({k: v for k, v in d.items() if k != "power"})
    assert "OPEN (not this lane)" not in txt


def test_propellant_policy_cites_registered_rfp_clauses():
    """A9.16 repair RFP-06: the A9.15 propellant policy cites the registered RFP clauses."""
    d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rc = d["propellant_policy"]["rfp_clauses"]
    assert [c["clause_id"] for c in rc["clauses"]] == ["RFP-P18-08", "RFP-P17-05", "RFP-P16-02"]
    assert rc["pdf_sha256"] == "a128a419414b571983d46be9b27f7bf2c4279693408399e0b92148f598e5dd00"


def test_rv19_09_c1_mass_check_flight_bullet_qualified(d):
    """RV19-09: the flight bullet must not flatly deny a C1 Xe branch inside the kept AL-08 H2-7 floor."""
    flight = d["c1_mass_check"]["flight"]
    assert "no C1 Xe branch in AL-08 in the flight" not in flight
    assert "no C1 Xe branch booked as a line in AL-08" in flight
    assert "two-branch valve set" in flight and "recorder_flags" in flight
    assert any("two-branch valve set" in f for f in d["recorder_flags"])
    assert "no C1 Xe branch in AL-08 in the flight architecture" not in MD_PATH.read_text(encoding="utf-8")
