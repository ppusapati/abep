"""Tests for the A9 mass + power integration v5 (A9.26 bid mass policy; successor of the immutable v4).

Checks reproducibility, the v4 / v3 / A9.26 pins (v4, v3, v2 never edited), the A9.26 changes (10 % system margin for
the active bid basis, 20 % line uplift kept on AL-04 / AL-07 / AL-08 with unchanged values, AL-09 = 1.0 kg
PROVISIONAL_OWNER_ALLOCATION with the harness separate, MPV3Q-01 closed, no compensating reduction), the recomputed
roll-up against the owner's approximate arithmetic (STOP when materially different), HARD_40_WET per Xe case (no PASS),
the proposal design target, the internal allocation target, the margin audit, the historical 20 % sensitivity and the
carried v4 statuses.
Run: python -m pytest -q tests/test_mass_power_a9_v5.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "mass_power_a9_v5"
BUILDER = LANE / "build_mass_power_a9_v5.py"
JSON_PATH = LANE / "mass_power_a9_v5.json"
V4_JSON = REPO / "docs" / "budgets" / "mass_power_a9_v4" / "mass_power_a9_v4.json"
FLIGHT = "hall_icp_neutralizer"


def _mod():
    spec = importlib.util.spec_from_file_location("build_mass_power_a9_v5_t", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v4():
    return json.loads(V4_JSON.read_text(encoding="utf-8"))


def _line(d, lid):
    return next(x for x in d["lines"][FLIGHT] if x["line"] == lid)


def _hard(d):
    return {w["xe_case_kg"]: w for w in d["rollups"][0]["wet"] if w["reference"] == "HARD_40_WET"}


def test_check_reproduces():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_history_and_decision_pinned():
    m = _mod()
    for _k, (p, s) in m.PINS.items():
        assert hashlib.sha256((REPO / p).read_bytes()).hexdigest() == s, p
    assert {"V4_JSON", "V4_MD", "V4_BUILDER", "V3_BUILDER", "A9_26_MD", "A9_26_JSON"} <= set(m.PINS)


def test_a9_26_record(doc):
    a = doc["a9_26"]
    assert (a["decision"], a["message"], a["key"]) == ("A9.26", 2, "MASS_BUDGET_DECISIONS_PRE_BID_FREEZE")
    assert a["text_sha256"] == "c240fca3b8109078ac0113cdb3526d729e3f13c41a8e8639b802b463f535633f"
    assert a["quotes"]["al09"]["quote"].endswith("= 1.0 kg") and a["quotes"]["margin"]["section"] == 1


def test_al09_provisional_owner_allocation(doc):
    ln = _line(doc, "AL-09")
    assert ln["value"]["value_kg"] == 1.0 and ln["value"]["governs"] == "ALLOCATION_MEV"
    assert ln["owner_allocation_kg"] == 1.0
    assert ln["owner_allocation_status"] == ["PROVISIONAL_OWNER_ALLOCATION", "NOT_CBE", "NOT_MEASURED"]
    assert ln["cbe_kg"] is None and ln["measured_kg"] is None
    assert ln["row54_allocation_kg"] is None and ln["row54_combined_allocation_kg"] == 1.0   # row 54 kept as history
    assert ln["harness"].startswith("SEPARATE") and ln["allocation_status_v4"].startswith("TBD_OWNER (MPV3Q-01)")
    assert doc["open_register_status"]["MPV3Q-01"].startswith("OWNER_DECIDED (A9.26")
    q = next(x for x in doc["open_owner_questions"] if x["id"] == "MPV3Q-01")
    assert q["status"] == "CLOSED_OWNER_DECIDED_A9_26"


def test_no_compensating_reduction_and_floors_unchanged(doc, v4):
    for a, b in zip(doc["lines"][FLIGHT], v4["lines"][FLIGHT]):
        assert a["line"] == b["line"]
        if a["line"] != "AL-09":
            assert a == b, a["line"]
    for lid, kg in (("AL-04", 4.2048), ("AL-07", 6.0), ("AL-08", 5.9148)):
        assert _line(doc, lid)["value"] == {**_line(v4, lid)["value"]} and _line(doc, lid)["value"]["value_kg"] == kg
    for k in ("bom", "power", "retired_flight_configuration_history", "afi_corrections", "statuses", "xe_v3_import"):
        assert doc[k] == v4[k], k


def test_rollup_10pct_and_owner_arithmetic(doc):
    r = doc["rollups"][0]
    assert r["reading"].startswith("MEV_LEVEL_EVIDENCE_BASED") and r["system_margin_fraction"] == 0.1
    nh = sum(p["kg"] for p in r["parts"] if p["line"] != "AL-HAR")
    assert abs(r["nonharness_known_kg"] - nh) < 1e-9 and r["lines_without_value"] == []
    assert abs(r["harness_kg"] - nh * 0.05 / 0.95) < 1e-8
    assert abs(r["system_margin_kg"] - 0.1 * r["nominal_dry_known_kg"]) < 1e-8 and r["reserve_kg"] == 0.0
    assert abs(r["dry_known_kg"] - 1.1 * r["nominal_dry_known_kg"]) < 1e-8
    got = {k: round(r[k], 4) for k in ("nonharness_known_kg", "harness_kg", "nominal_dry_known_kg",
                                       "system_margin_kg", "dry_known_kg")}
    assert got == {"nonharness_known_kg": 33.1196, "harness_kg": 1.7431, "nominal_dry_known_kg": 34.8627,
                   "system_margin_kg": 3.4863, "dry_known_kg": 38.349}
    hard = _hard(doc)
    assert {c: round(w["wet_known_kg"], 4) for c, w in hard.items()} == {2.0: 40.349, 5.0: 43.349, 10.0: 48.349}
    assert {w["state"] for w in hard.values()} == {"DOES_NOT_CLOSE"}
    assert round(hard[2.0]["exceedance_kg"], 2) == 0.35
    for w in hard.values():
        assert w["residual_added_on_top_kg"] == 0.0


def test_schema_compatible_with_v4_for_readers(doc, v4):
    """Readers (bid-package builder, F7/F8, RVM, F9) take the ONE active roll-up from `rollups`: same shape as v4; every
    historical / sensitivity roll-up lives outside `rollups` and is labelled HISTORICAL / SENSITIVITY."""
    act = [r for r in doc["rollups"] if r["configuration"] == FLIGHT]
    assert len(doc["rollups"]) == 1 and len(act) == 1
    r, r4 = act[0], v4["rollups"][0]
    assert set(r4) <= set(r)
    for k in ("nonharness_known_kg", "harness_kg", "nominal_dry_known_kg", "system_margin_kg", "dry_known_kg"):
        assert isinstance(r[k], float)
    assert [(w["xe_case_kg"], w["reference"]) for w in r["wet"]] == [(w["xe_case_kg"], w["reference"]) for w in r4["wet"]]
    assert all(set(w4) <= set(w) for w, w4 in zip(r["wet"], r4["wet"]))
    assert "HISTORICAL" not in r["reading"] and "SENSITIVITY" not in r["reading"]
    h = doc["historical_conservative_sensitivity_20pct"]
    assert "HISTORICAL" in h["label"] and "SENSITIVITY" in h["recomputed_with_al09"]["reading"]
    assert "HISTORICAL" in h["v4_al09_excluded_history"]["label"]
    assert "HISTORICAL" in doc["flight_rollup_vs_40kg"][0]["v4"]["label"]
    assert all(isinstance(ln["value"]["value_kg"], float) for ln in doc["lines"][FLIGHT] if ln["line"] != "AL-HAR")
    assert doc["margin_convention"]["system_margin"].startswith("0.10 x the current nominal dry (A9.26")


def test_closure_vs_40kg(doc):
    c = {x["xe_case_kg"]: x for x in doc["closure_vs_40kg"]}
    assert {k: v["max_allowable_dry_kg_strictly_below"] for k, v in c.items()} == {2.0: 38.0, 5.0: 35.0, 10.0: 30.0}
    assert {k: round(v["dry_reduction_needed_kg_more_than"], 4) for k, v in c.items()} == \
        {2.0: 0.349, 5.0: 3.349, 10.0: 8.349}
    assert c[2.0]["xe_case_role"].startswith("PLANNING / REFERENCE CASE") and "not the selected" in c[2.0]["xe_case_role"]
    assert all(v["state"] == "DOES_NOT_CLOSE" for v in c.values())


def test_mass_status_no_pass(doc):
    ms = doc["mass_status"]
    assert ms["status"] == "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"
    assert ms["reading"].startswith("CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR")
    assert "PASS" not in json.dumps({k: v for k, v in ms.items() if k != "owner_quotes"}).replace("no PASS", "")
    h = ms["bid_hierarchy"]
    assert h["requirement"].startswith("complete flight wet mass < 40 kg")
    assert "~39.4 kg wet" in h["proposal_design_target"] and "~38.35 kg dry" in h["current_provisional_planning_rollup"]
    assert "40.35 / 43.35 / 48.35" in h["current_provisional_planning_rollup"]
    assert [x["id"] for x in doc["mass_closure_actions"]] == [f"MCA-0{i}" for i in range(1, 7)]
    assert [x["line"] for x in doc["mass_closure_actions"]] == ["AL-07", "AL-08", "AL-04", "AL-09", "AL-HAR", "system"]


def test_proposal_design_target(doc):
    p = doc["proposal_design_target"]
    assert p["label"].startswith("PROPOSAL DESIGN TARGET - DESIGN TARGET, NOT ACHIEVED EVIDENCE")
    assert (p["nominal_dry_max_kg"], p["system_margin_fraction"], p["dry_target_kg"]) == (34.0, 0.1, 37.4)
    assert (p["xe_reference_case_kg"], p["wet_target_at_reference_kg"]) == (2.0, 39.4)
    assert {x["xe_case_kg"]: x["wet_target_kg"] for x in p["by_xe_case"]} == {2.0: 39.4, 5.0: 42.4, 10.0: 47.4}
    assert "a selected Xe load" in p["not"] and "achieved evidence" in p["not"]
    assert round(p["gap_from_current_planning_rollup"]["nominal_dry_reduction_needed_kg"], 4) == 0.8627


def test_internal_allocation_target(doc):
    t = doc["internal_allocation_target"]
    assert t["label"] == "INTERNAL ALLOCATION TARGET - NOT EVIDENCE OF MASS COMPLIANCE (A9.26 section 6)"
    assert next(x for x in t["lines"] if x["line"] == "AL-09")["allocation_kg"] == 1.0
    assert t["nonharness_allocation_sum_kg"] == 24.0 and round(t["harness_kg"], 4) == 1.2632
    assert round(t["dry_kg"], 4) == 27.7895 and t["system_margin_fraction"] == 0.1
    assert "the <= 34 kg proposal nominal-dry target" in t["not"]
    hp = t["historical_provenance"]
    assert hp["label"].startswith("HISTORICAL / INTERNAL ALLOCATION PROVENANCE") and hp["dry_budget_kg"] == 28.8
    assert doc["budget_reference"]["dry_budget_kg"] == 28.8
    assert doc["budget_reference"]["a9_26_status"].startswith("HISTORICAL / INTERNAL ALLOCATION PROVENANCE")


def test_margin_audit(doc):
    ma = doc["margin_audit"]
    assert ma["decision"].startswith("INTENTIONAL_GOVERNANCE")
    assert (ma["effective_factor_floor_lines"], ma["effective_factor_floor_lines_historical"]) == (1.32, 1.44)
    by = {x["line"]: x for x in ma["lines"]}
    for lid in ("AL-04", "AL-07", "AL-08"):
        assert by[lid]["contains_line_uplift"] is True and by[lid]["effective_factor"] == 1.32
    for lid in ("AL-01", "AL-02", "AL-03", "AL-05", "AL-06", "AL-09", "AL-10"):
        assert by[lid]["contains_line_uplift"] is False and by[lid]["effective_factor"] == 1.1


def test_historical_20pct_sensitivity(doc, v4):
    h = doc["historical_conservative_sensitivity_20pct"]
    assert h["label"].startswith("HISTORICAL / CONSERVATIVE SENSITIVITY")
    r = h["recomputed_with_al09"]
    assert r["system_margin_fraction"] == 0.2 and round(r["dry_known_kg"], 4) == 41.8353
    assert {x["xe_case_kg"]: round(x["wet_known_kg"], 4) for x in r["wet_by_loaded_case"]} == \
        {2.0: 43.8353, 5.0: 46.8353, 10.0: 51.8353}
    hv = h["v4_al09_excluded_history"]
    assert hv["dry_known_kg"] == v4["rollups"][0]["dry_known_kg"] and hv["lines_without_value"] == ["AL-09"]
    assert round(hv["dry_known_kg"], 4) == 40.5721


def test_carried_v4_statuses(doc):
    assert doc["open_register_status"]["AFI-01-S1"].startswith("RESOLVED: OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH")
    assert doc["open_register_status"]["AFI-02-RA1"] == "OPEN"
    assert doc["statuses"]["current_statuses"]["C1 conventional reference"].startswith("GROUND_REFERENCE_ONLY")
    assert doc["afi_corrections"]["AFI-01"]["new"] == {"valves_kg": 0.455, "floor_cbe_kg": 4.929, "mev_kg": 5.9148}
    assert _line(doc, "AL-07")["open_rebase_action"]["id"] == "AFI-02-RA1"


def test_margin_refusals():
    m = _mod()
    m3 = m.v3_module()
    m.system_margin_bid(m3, 30.0)
    for bad in (0.0, 0.05, 0.2):
        with pytest.raises(m.MassPolicyError):
            m.system_margin_bid(m3, 30.0, fraction=bad)
    with pytest.raises(m.MassPolicyError):
        m.system_margin_bid(m3, 30.0, reserve_kg=4.0)
    with pytest.raises(m.MassPolicyError):
        m.assert_bid_margin_reading({"allocations": "MEV", "system_margin": 0.05, "reserve_kg": 0.0, "xe_case": "LOADED"})
    with pytest.raises(m3.MassError):                                     # the 20 % rule stays v3's, never relaxed
        m3.system_margin(30.0, fraction=0.1)


def test_stop_when_materially_different(monkeypatch):
    m = _mod()
    monkeypatch.setitem(m.EXPECTED_ROLLUP, "dry_known_kg", 38.0)
    with pytest.raises(m.MassPolicyError, match="STOP"):
        m.build_doc()


def test_al09_only_once(v4):
    m = _mod()
    m3 = m.v3_module()
    al08 = copy.deepcopy(_line(v4, "AL-08"))
    with pytest.raises(m.MassPolicyError):
        m.set_al09(al08, m3)
