"""Tests for the A9 mass + power integration v4 (A9.24 AFI pre-bid corrections; successor of the immutable v3).

Checks reproducibility, the v3 pins (v3 never edited), the AFI-01 AL-08 re-base (only the C1 cathode-feed PFCV removed,
the second latch kept: AFI-01-S1 OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH, A9.25 message 8), roll-ups recomputed exactly as v3 (20 % system margin on
the current pre-margin sum, row-60 harness, LOADED Xe 2 / 5 / 10 kg, no margin relaxation), every other line unchanged,
AFI-02 AL-07 label with the 6.0 kg owner floor unchanged, and C1 = GROUND_REFERENCE_ONLY with A9.2 only quoted.
Run: python -m pytest -q tests/test_mass_power_a9_v4.py
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
LANE = REPO / "docs" / "budgets" / "mass_power_a9_v4"
BUILDER = LANE / "build_mass_power_a9_v4.py"
JSON_PATH = LANE / "mass_power_a9_v4.json"
V3_JSON = REPO / "docs" / "budgets" / "mass_power_a9_v3" / "mass_power_a9_v3.json"
FLIGHT = "hall_icp_neutralizer"


def _mod():
    spec = importlib.util.spec_from_file_location("build_mass_power_a9_v4_t", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v3():
    return json.loads(V3_JSON.read_text(encoding="utf-8"))


def _line(d, lid):
    return next(x for x in d["lines"][FLIGHT] if x["line"] == lid)


def test_check_reproduces():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_v3_and_sources_pinned():
    m = _mod()
    for _k, (p, s) in m.PINS.items():
        if s:
            assert hashlib.sha256((REPO / p).read_bytes()).hexdigest() == s, p


def test_al08_rebase(doc):
    a = doc["afi_corrections"]["AFI-01"]
    assert (a["old"]["valves_kg"], a["old"]["floor_cbe_kg"], a["old"]["mev_kg"]) == (0.57, 5.044, 6.0528)
    assert a["new"] == {"valves_kg": 0.455, "floor_cbe_kg": 4.929, "mev_kg": 5.9148}
    assert [r["kg"] for r in a["removed"]] == [0.115] and "A9B-C04" in a["removed"][0]["source_ids"]
    assert [r["kg"] for r in a["retained_valves"]] == [0.17, 0.115, 0.17]
    assert a["stop_items"] == []                                          # A9.25 message 8: no open stop item
    s = a["resolved_stop_items"][0]
    assert s["id"] == "AFI-01-S1" and s["state"] == "OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH"
    assert s["current_function"] == "SECOND SERIES FLIGHT XE ISOLATION VALVE" and s["numbers_changed"] is False
    assert s["decided_by"]["message"] == 8 and s["decided_by"]["key"] == "FINAL_PRE_BID_AFI_RESOLUTION"
    assert s["rejected_alternative"]["mev_kg"] == 5.7108                  # owner: do not use (history only)
    latch2 = a["retained_valves"][2]
    assert latch2["current_function"] == "SECOND SERIES FLIGHT XE ISOLATION VALVE"
    assert "cathode" not in latch2["what"] and latch2["mass_provenance"].startswith("HISTORICAL")
    assert a["c1_hardware_in_flight_al08"].startswith("NONE")
    ln = _line(doc, "AL-08")
    assert ln["evidence_floor_cbe_kg"] == 4.929 and ln["value"]["value_kg"] == 5.9148
    assert ln["value"]["governs"] == "MEV_PLANNING_FLOOR" and ln["floor_is_partial"] is True
    assert "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN" in ln["a9_21_status"]
    kept = {c["what"]: c["kg"] for c in ln["floor_constituents"]}
    assert 3.5 in kept.values() and 0.974 in kept.values()
    assert any(c["kg"] is None for c in ln["floor_constituents"])        # plumbing / mounting stay pending


def test_other_lines_unchanged(doc, v3):
    for a, b in zip(doc["lines"][FLIGHT], v3["lines"][FLIGHT]):
        assert a["line"] == b["line"]
        if a["line"] != "AL-08":
            assert a["value"] == b["value"] and a["evidence_floor_cbe_kg"] == b["evidence_floor_cbe_kg"]
    assert doc["retired_flight_configuration_history"] == v3["retired_flight_configuration_history"]
    assert doc["bom"] == v3["bom"] and doc["power"] == v3["power"]


def test_rollup_rules(doc):
    r = doc["rollups"][0]
    nh = sum(p["kg"] for p in r["parts"] if p["line"] != "AL-HAR" and p["kg"] is not None)
    assert abs(r["nonharness_known_kg"] - nh) < 1e-9
    assert abs(r["harness_kg"] - nh * 0.05 / 0.95) < 1e-8
    assert abs(r["system_margin_kg"] - 0.2 * r["nominal_dry_known_kg"]) < 1e-8 and r["reserve_kg"] == 0.0
    assert abs(r["dry_known_kg"] - 1.2 * r["nominal_dry_known_kg"]) < 1e-8
    hard = {w["xe_case_kg"]: w for w in r["wet"] if w["reference"] == "HARD_40_WET"}
    assert sorted(hard) == [2.0, 5.0, 10.0]
    for c, w in hard.items():
        assert w["residual_added_on_top_kg"] == 0.0 and abs(w["wet_known_kg"] - r["dry_known_kg"] - c) < 1e-8
        assert w["state"] == "DOES_NOT_CLOSE"
    f = doc["flight_rollup_vs_40kg"][0]
    assert f["dry_known_kg"] == r["dry_known_kg"] and f["numerically_unchanged_vs_v3"] is False


def test_no_margin_relaxation():
    m = _mod().v3_module()
    with pytest.raises(m.MassError):
        m.system_margin(30.0, fraction=0.1)


def test_al07_label_only(doc, v3):
    a, b = _line(doc, "AL-07"), _line(v3, "AL-07")
    assert a["value"] == b["value"] and a["value"]["value_kg"] == 6.0
    assert a["afi_02_labels"] == ["PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR",
                                  "CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE",
                                  "REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE"]
    assert a["open_rebase_action"]["state"] == "OPEN" and a["open_rebase_action"]["number_changed"] is False


def test_c1_status_current(doc):
    st = doc["statuses"]
    assert st["current_statuses"]["C1 conventional reference"].startswith("GROUND_REFERENCE_ONLY")
    assert st["a9_2_statuses_label"].startswith("HISTORICAL_QUOTE")
    assert st["a9_2_statuses"]["C1 conventional reference"] == "CONTROL_FALLBACK"      # verbatim A9.2 quote


def test_a9_25_resolution_and_mass_wording(doc):
    """A9.25 message 8: AFI-01-S1 resolved (no open owner question), mass wording, AL-07 kept, numbers unchanged."""
    assert doc["open_register_status"]["AFI-01-S1"].startswith("RESOLVED: OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH")
    assert doc["open_register_status"]["AFI-02-RA1"] == "OPEN"
    ms = doc["mass_status"]
    assert ms["reading"].startswith("CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR")
    assert ms["mass_compliance"].startswith("INCOMPLETE_EVIDENCE / NOT YET CLOSED")
    assert "PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR" in doc["afi_corrections"]["AFI-02"]["a9_25_confirmation"]
    f = doc["flight_rollup_vs_40kg"][0]
    assert round(f["dry_known_kg"], 4) == 40.5721                        # values approved at 4c2b3b3, unchanged
    assert {c: round(v, 4) for c, v in f["wet_known_kg_by_loaded_case"].items()} == \
        {"2.0": 42.5721, "5.0": 45.5721, "10.0": 50.5721}
    r = doc["rollups"][0]
    assert (round(r["nominal_dry_known_kg"], 4), round(r["system_margin_kg"], 4)) == (33.8101, 6.762)
    assert set(f["hard_40_wet_state_by_loaded_case"].values()) == {"DOES_NOT_CLOSE"}
    assert "RETAINED_PENDING_OWNER" not in json.dumps(doc["lines"])
