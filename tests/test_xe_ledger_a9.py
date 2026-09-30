"""Tests for the A9-08 Xe ledger update (docs/budgets/xe_ledger_a9/, follow-on fo_a9_08_xe_ledger_update).

Checks: byte-for-byte reproduction by the builder; the v1 Xe ledger (module and deliverable) unchanged; G-REUSE books zero
ICP Xe and no dedicated feed; C1 terms only in hall_c1_reference; XE_REFERENCE only in the ground-test ledger; the owner
values (rows 42, 43, 45, 46, 48, 50, 93, 96) are applied as stated; every total with a TBD input is refused; the 323.15 K
tank table recomputes from the pinned NIST snapshot; item/evidence discipline; no winner vocabulary. Only this lane's
files are exercised; no parallel A9 lane is imported. Run: python -m pytest -q tests/test_xe_ledger_a9.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

from abep_sim import xe_ledger as xl

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "xe_ledger_a9"
BUILDER = LANE / "build_xe_ledger_a9.py"
OUT_JSON = LANE / "xe_ledger_a9_v1.json"
OUT_MD = LANE / "XE_LEDGER_A9.md"


def _mod():
    spec = importlib.util.spec_from_file_location("build_xe_ledger_a9", BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _mod()


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _sha(rel):
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _eval(d, sid):
    return next(e for e in d["evaluations"] if e["scenario"] == sid)


def _term(e, tid):
    return next(t for t in e["terms"] if t["term"] == tid)


# ------------------------------------------------------------------------------------------------ reproduction / pins
def test_builder_reproduces_outputs(mod):
    js, md = mod.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert mod.main(["--check"]) == 0


def test_pins_verified_and_v1_untouched(mod, d):
    for p in d["decision_pins"] + d["deliverable_pins"] + d["source_snapshots"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]
    v1 = {p["path"]: p["sha256"] for p in d["deliverable_pins"]}
    for rel in ("abep_sim/xe_ledger.py", "docs/budgets/xe_ledger/xe_ledger_v1.json",
                "docs/budgets/xe_ledger/XE_LEDGER.md", "docs/budgets/xe_ledger/build_xe_ledger.py"):
        assert _sha(rel) == v1[rel]
    for rel, h in mod.HISTORICAL.values():
        assert _sha(rel) == h


def test_decision_files_pinned_and_governance_never(d):
    paths = [p["path"] for p in d["decision_pins"]]
    for need in ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
                 "docs/decisions/OD_2026_09_29_owner_answers_147.json",
                 "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
                 "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
                 "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md"):
        assert need in paths
    all_pins = " ".join(p["path"] for p in d["decision_pins"] + d["deliverable_pins"] + d["source_snapshots"])
    for banned in ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state"):
        assert banned not in all_pins


def test_no_abep_sim_module_names_the_ledger():
    for p in (REPO / "abep_sim").glob("*.py"):
        if p.name != "xe_ledger.py":
            assert "xe_ledger" not in p.read_text(encoding="utf-8"), p.name


# ------------------------------------------------------------------------------------------------ configurations
def test_configuration_ids_and_scenarios(d):
    assert d["configurations"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    ids = {s["id"] for s in d["scenarios"]}
    assert ids == {f"{p}-{s}" for p in ("FL", "GT") for s in ("C1", "ICP-REUSE", "ICP-ATM", "ICP-XE")}
    assert d["not_primary_variants"][0]["status"] == "NOT_A_PRIMARY_A9_VARIANT"


def test_g_reuse_books_zero_icp_xe(d):
    for sid in ("FL-ICP-REUSE", "GT-ICP-REUSE"):
        e = _eval(d, sid)
        icp = [t for t in e["terms"] if "ICP-XE" in t["term"]]
        assert len(icp) == 1 and icp[0]["status"] == "ZERO_BY_OWNER_DECISION" and icp[0]["kg"] == 0.0
    item = next(i for i in d["items"] if i["id"] == "XA9-21")
    assert item["value"] == 0.0 and "no dedicated atmospheric feed" in item["source"]
    assert "never counted again" in d["icp_gas_modes"]["G-REUSE"]


def test_g_atm_books_no_xe_and_g_xe_is_explicit(d):
    assert _term(_eval(d, "FL-ICP-ATM"), "F-ICP-XE")["kg"] == 0.0
    gxe = _term(_eval(d, "FL-ICP-XE"), "F-ICP-XE")
    assert gxe["status"] == "PRESENT" and gxe["kg"] is None and gxe["missing"]
    assert "CONTINGENCY" in d["icp_gas_modes"]["G-XE"] and "PHASE_TOTAL_FLOW" in d["icp_gas_modes"]["G-XE"]


def test_c1_terms_only_in_c1_configuration(d):
    for sid in ("FL-ICP-REUSE", "FL-ICP-ATM", "FL-ICP-XE", "GT-ICP-REUSE", "GT-ICP-ATM", "GT-ICP-XE"):
        for t in _eval(d, sid)["terms"]:
            if "-C1-" in t["term"]:
                assert t["status"] == "ABSENT_BY_OWNER_DECISION"
                assert "OQ-A902-04" in t["why"]
    for t in _eval(d, "FL-C1")["terms"]:
        if "-C1-" in t["term"]:
            assert t["status"] == "PRESENT"


def test_xe_reference_ground_only_and_peak_separate(d):
    for e in d["evaluations"]:
        names = {t["term"] for t in e["terms"]}
        if e["scenario"].startswith("FL-"):
            assert "G-XE-REFERENCE" not in names and "G-XE-AUGMENTED-PEAK" not in names
            assert {"F-XE-FUNCTIONAL", "F-XE-PEAK", "F-RESERVE", "F-RESIDUAL"} <= names
        else:
            assert {"G-XE-REFERENCE", "G-XE-AUGMENTED-PEAK"} <= names
            assert "F-RESERVE" not in names and "F-RESIDUAL" not in names


# ------------------------------------------------------------------------------------------------ owner values
def test_c1_cathode_and_flow_uncertainty_terms(d):
    e = _eval(d, "FL-C1")
    assert _term(e, "F-C1-CATHODE")["kg"] == 5.4
    assert _term(e, "F-C1-FLOWUNC")["kg"] == 0.216
    v1 = xl.product_term_kg({"mdot_cathode": xl.Quantity(0.10, "mg/s", "t", "assumed"),
                             "t_firing": xl.Quantity(15000.0, "h", "t", "assumed")}, "m_cathode")
    assert abs(v1 - 5.4) < 1e-12
    it = {i["id"]: i for i in d["items"]}
    assert it["XA9-01"]["value"] == 15000.0 and "row 46" in it["XA9-01"]["source"]
    assert it["XA9-04"]["value"] == 0.02 and "row 96" in it["XA9-04"]["source"]


def test_reserve_residual_and_ignition_bound(d):
    it = {i["id"]: i for i in d["items"]}
    assert it["XA9-23"]["value"] == 0.20 and it["XA9-23"]["basis"] == "ASSUMED_ENGINEERING_ALLOCATION"
    assert it["XA9-24"]["value"] == 0.02
    assert it["XA9-07"]["value"] == 120.0 and it["XA9-08"]["value"] == 3.0 and "row 93" in it["XA9-07"]["source"]
    res = [t for t in d["terms"] if t["kind"] == "residual"]
    assert len(res) == 1 and res[0]["id"] == "F-RESIDUAL"
    floor = _eval(d, "FL-C1")["floor_known_terms_only"]
    assert abs(floor["reserve_kg"] - 0.2 * 5.616) < 1e-9
    assert abs(floor["loaded_kg"] - 5.616 * 1.2 * 1.02) < 1e-5
    assert any("A9-06" in x["to"] and "ONE line" in x["quantity"] for x in d["interface_demands"])


def test_phase_total_flow_convention(d):
    ac = d["accounting_convention"]
    assert ac["id"] == "PHASE_TOTAL_FLOW" and ac["owner_row"] == 42
    assert ac["v1_definition"] == xl.ACCOUNTING_CONVENTIONS["PHASE_TOTAL_FLOW"]
    phases = {t["phase"] for t in d["terms"]}
    for p in ("purge", "preheat", "ignition", "keeper_cathode", "transition", "fallback"):
        assert p in phases and p in ac["phases_booked"]


def test_every_total_refused_while_tbd(d):
    for e in d["evaluations"]:
        assert e["refused"] is True and e["missing"] and e["non_reserve_kg"] is None
        if e["scenario"].startswith("FL-"):
            assert e["loaded_kg"] is None and e["residual_kg"] is None


def test_no_single_mission_load_frozen(d):
    it = {i["id"]: i for i in d["items"]}
    assert it["XA9-30"]["value"] == [2.0, 5.0, 10.0]
    assert "no single mission load frozen" in it["XA9-30"]["status"]
    assert {r["case_kg"] for r in d["design_cases"]["tank_volume"]["rows"]} == {2.0, 5.0, 10.0}


# ------------------------------------------------------------------------------------------------ tank sizing
def test_tank_volume_recomputes_from_nist_snapshot(mod, d):
    rho = mod.read_isotherm(mod.SNAPSHOTS["NIST323"][0])
    assert rho[150.0] == 1673.5  # row 50 question: 1.67 g/cm3 at 323 K / 150 bar
    assert mod.read_isotherm(mod.SNAPSHOTS["NIST300"][0])[150.0] == 1969.5  # row 50: 1.97 at 300 K (contrast)
    u = next(i for i in d["items"] if i["id"] == "XA9-27")["value"]
    for r in d["design_cases"]["tank_volume"]["rows"]:
        v = r["case_kg"] / (rho[r["p_bar"]] * (1 - u)) * 1000
        assert abs(v - r["V_min_323K_l"]) <= 1e-5 * v
    it = {i["id"]: i for i in d["items"]}
    assert it["XA9-28"]["value"] is None and it["XA9-29"]["value"] is None  # MEOP / safety factors explicit TBD
    assert it["XA9-25"]["value"] == 323.0


def test_design_case_arithmetic(d):
    for r in d["design_cases"]["reserve_residual_split"]["rows"]:
        m = r["case_kg"]
        assert abs(r["residual_kg"] + r["reserve_kg"] + r["non_reserve_cap_kg"] - m) < 1e-5
    hr = {(x["scenario"], x["case_kg"]): x for x in d["design_cases"]["headroom"]["rows"]}
    assert hr[("FL-C1", 2.0)]["status"] == "EXCEEDED_BY_CLOSED_TERMS"
    assert hr[("FL-C1", 10.0)]["status"] == "HEADROOM"


# ------------------------------------------------------------------------------------------------ discipline
def test_items_discipline(mod, d):
    for i in d["items"]:
        for k in ("id", "name", "unit", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert i.get(k) not in (None, ""), (i["id"], k)
        assert i["freeze_point"] in mod.FREEZE_POINTS
        if i["value"] is None:
            assert i["evidence_class"] == "none" and i["value_display"].startswith("TBD - requires ")
        else:
            assert i["evidence_class"] in mod.EVIDENCE_CLASSES


def test_filter_getter_c1_branch_only(d):
    fg = d["filter_getter"]
    assert fg["flight_hall_icp_neutralizer"].startswith("NOT_INSTALLED")
    it = {i["id"]: i for i in d["items"]}
    for k in ("XA9-31", "XA9-32"):
        assert it[k]["applies_to"]["configs"] == ["hall_c1_reference"] and it[k]["value"] is None


def test_owner_answers_verbatim(d):
    ans = json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json").read_text(encoding="utf-8"))
    rows = {r["row"]: r["owner_answer_verbatim"] for r in ans["answers"]}
    applied = {a["row"] for a in d["owner_answers_applied"]}
    for need in (6, 26, 42, 43, 45, 46, 48, 50, 51, 93, 96):
        assert need in applied
    for a in d["owner_answers_applied"]:
        assert a["owner_answer_verbatim"] == rows[a["row"]]
    dec = {a["decision"] for a in d["a9_1_decisions_applied"]}
    assert {"HIQ-03", "HIQ-06", "HIQ-06_accounting", "OQ-A902-04", "OQ-A902-05"} <= dec


def test_required_sections_and_pending_lanes(d):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_inputs", "h4_inputs"):
        assert d[k], k
    md = OUT_MD.read_text(encoding="utf-8")
    for h in ("## (a)", "## (b)", "## (c)", "## (d)", "## (e)", "## (f)", "## (g)"):
        assert h in md
    txt = json.dumps(d["interface_demands"])
    for p in ("docs/budgets/mass_a9/", "docs/hardware/h2_a9_revisions/", "docs/procurement/rfq_a9/"):
        assert f"PENDING {p}" in txt
    assert {m["m16_row"] for m in d["m16_impact"]} == {6, 7, 8, 11}


def test_no_winner_no_hall_closure_no_prediction(d):
    xl.reject_forbidden_keys(d)
    txt = json.dumps(d).lower()
    assert not re.search(r"\bwinner\b(?! is declared)(?! unless)", txt.replace("no winner", ""))
    for banned in ("sgb-screen", "plasma_devices", "hall_map", "ensemble_member_id"):
        assert banned not in txt
