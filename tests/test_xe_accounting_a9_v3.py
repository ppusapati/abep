"""Tests for the A9 Xe accounting v3 (A9.16 step 1: owner decisions A9.14 / A9.15 applied).

Checks reproducibility, immutability of v2, verbatim-checked owner-decision citations (file + json sha256 + question id),
the RFP-compliant propellant policy (Xe capability in every flight configuration, never a C1 contingency; flight C1 Xe
neither assumed nor excluded), the resolved reading axes (LOADED, 3 x 120 s = 360 s, flow class inside the reserve base),
the 20 % ground logistics margin with explicit procedure lines, the retired 75-bar MEOP placeholder, and every
fail-closed rule function (refusals included).
Run: python -m pytest -q tests/test_xe_accounting_a9_v3.py
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
LANE = REPO / "docs" / "budgets" / "xe_accounting_a9_v3"
BUILDER = LANE / "build_xe_accounting_a9_v3.py"
JSON_PATH = LANE / "xe_accounting_a9_v3.json"
MD_PATH = LANE / "XE_ACCOUNTING_A9_V3.md"
FORBIDDEN = "xe" + "_ledger"          # never spelled contiguously in code outside the v1 module
V2 = {
    "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json":
        "ad6102fc12df3ad6c4bcc85264c1893b8ab51857b0319b9881afecd8a6c4730a",
    "docs/budgets/xe_accounting_a9_v2/XE_ACCOUNTING_A9_V2.md":
        "f2cca970bf7fc9870c001af75f5e855b8183cd8e1fbdccb0af78a4596162ff69",
    "docs/budgets/xe_accounting_a9_v2/build_xe_accounting_a9_v2.py":
        "2c279af73e9d322a501d8577f9dd916f0fc057459b9ec49618e8c11734ba235a",
}
DEC_SHA = {"A9.14": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
           "A9.15": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309"}
REQUIRED = [("A9.15", "governing_rule"), ("A9.14", "XA9Q-07"), ("A9.15", "XA9Q-07"), ("A9.14", "XV2Q-01"),
            ("A9.15", "XV2Q-01"), ("A9.14", "XA9Q-01"), ("A9.14", "MQ-09"), ("A9.14", "OQ-A910-01"),
            ("A9.14", "XA9Q-02"), ("A9.14", "OQ-A907-01"), ("A9.14", "XA9Q-03"), ("A9.14", "XA9Q-04"),
            ("A9.14", "XA9Q-06"), ("A9.14", "OQ-A907-07"), ("A9.15", "OQ-A907-07"), ("A9.14", "MPQ-01"),
            ("A9.15", "MPQ-01"), ("A9.14", "XA9Q-05"), ("A9.15", "XA9Q-05")]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def m():
    spec = importlib.util.spec_from_file_location("build_xe_accounting_a9_v3_under_test", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def d():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_builder_check_reproduces():
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_json_md_consistent(d, m):
    js, md = m.render()
    assert json.loads(js) == d
    assert MD_PATH.read_text(encoding="utf-8") == md


def test_v2_immutable_and_pinned(d):
    for rel, h in V2.items():
        assert _sha(REPO / rel) == h, rel
    assert d["revision_of"]["sha256"] == V2["docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json"]
    for p in d["pins"]["decisions"]:
        assert _sha(REPO / p["json"]) == p["json_sha256"]
        assert _sha(REPO / p["md"]) == p["md_sha256"]


def test_pin_mismatch_aborts(m, monkeypatch):
    bad = dict(m.DECISIONS)
    bad["A9.15"] = dict(bad["A9.15"], json_sha256="0" * 64)
    monkeypatch.setattr(m, "DECISIONS", bad)
    with pytest.raises(m.PinError):
        m.verify_pins()


def test_code_hygiene():
    for p in (BUILDER, Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert FORBIDDEN not in src.replace('"xe" + "_ledger"', ""), p.name
    src = BUILDER.read_text(encoding="utf-8")
    for banned in ("import archengine", "from abep_sim", "hall_map", "hall_ensemble", "plasma_devices", "julia"):
        assert banned not in src, banned


def test_every_required_decision_cited_with_sha_and_quote(d):
    got = {(r["key"], r["id"]) for r in d["owner_answers_applied"]}
    for k in REQUIRED:
        assert k in got, k
    for r in d["owner_answers_applied"]:
        assert r["json_sha256"] == DEC_SHA[r["key"]]
        md = " ".join((REPO / r["path"]).read_text(encoding="utf-8").split())
        assert " ".join(r["quote"].split()) in md, (r["key"], r["id"])
        assert r["how_applied"]


def test_quote_not_verbatim_refused(m):
    with pytest.raises(m.BookingError):
        m.OD("A9.14", "XA9Q-04", "BOOK A 25% GROUND-TEST Xe LOGISTICS MARGIN.")
    with pytest.raises(m.BookingError):
        m.OD("A9.14", "NOT-AN-ID", "THREE DWELLS / 360 s MAXIMUM BOOKING.")


# ------------------------------------------------------------------------------- RFP-compliant propellant policy
def test_xe_capability_every_configuration_independent_of_c1(m, d):
    for cfg in m.CONFIGS:
        for sel in (None, True, False):
            assert m.xe_system_capability(cfg, sel)["xe_propulsion_capability"] == "PRESENT_RFP_REQUIRED"
    with pytest.raises(m.BookingError):
        m.xe_system_capability("hall_only_xe_free")
    caps = {c["configuration"]: c for c in d["propellant_policy"]["per_configuration"]}
    assert set(caps) == {"hall_icp_neutralizer", "hall_c1_reference"}
    assert all(c["xe_propulsion_capability"] == "PRESENT_RFP_REQUIRED" for c in caps.values())
    assert "contingency-only for C1" in d["propellant_policy"]["superseded_wording"]["A9.13 owner_statements.xenon"]


def test_no_xe_free_reading_remains(d):
    assert d["reading_axes_resolved"]["RA-FUNC"]["v3"] == "APPLIES"
    for ln in d["ledger_lines"]:
        assert isinstance(ln["presence"], str)
        assert ln["presence"] != "ABSENT_UNDER_READING", ln["id"]
    for e in d["evaluations"]:
        if e["scenario"] in ("S1-FL-PRIMARY", "S3-FL-GATM", "S3-FL-GXE"):
            pres = {x["line"]: x["presence"] for x in e["lines"]}
            assert pres["P-FL-FUNC"] == "PRESENT" and pres["P-FL-FALLBACK"] == "PRESENT"
    q = {x["id"]: x for x in d["open_owner_questions"]}
    assert q["XV2Q-01"]["status"] == "NOT_APPLICABLE"


def test_retired_presence_refused(m):
    ln = {"id": "X", "presence": "ABSENT_UNDER_READING", "phase": "xe_mode", "kind": "product", "fields": []}
    with pytest.raises(m.BookingError):
        m._validate_line(ln)


def test_c1_flight_xe_neither_assumed_nor_excluded(m, d):
    st = m.c1_flight_xe_booking(False)
    assert st["state"] == "PENDING_C1_NOT_SELECTED" and st["booked"] is None
    assert m.c1_flight_xe_booking(True)["state"] == "TBD_FROM_SELECTED_C1_HARDWARE"
    assert m.c1_flight_xe_booking(True, True)["state"] == "BOOKED_IN_SYSTEM_XE_ARCHITECTURE"
    assert m.c1_flight_xe_booking(True, False) == {"state": "NO_C1_XE", "booked": False,
                                                   "rule": m.c1_flight_xe_booking(True, False)["rule"]}
    with pytest.raises(m.BookingError):
        m.c1_flight_xe_booking(False, True)      # no Xe requirement without a selected C1
    with pytest.raises(m.BookingError):
        m.c1_flight_xe_booking(None)
    lines = {x["id"]: x for x in d["ledger_lines"]}
    for lid in ("C1-FL-PURGE", "C1-FL-HEAT", "C1-FL-IGN", "C1-FL-KEEPER", "C1-FL-FLOWUNC"):
        assert lines[lid]["presence"] == "CONDITIONAL_ON_C1_FLIGHT_SELECTION"
    ev = next(e for e in d["evaluations"] if e["scenario"] == "S2-FL-C1")
    assert ev["booking"]["status"] == "REFUSED_TBD_INPUTS"
    k = next(x for x in ev["lines"] if x["line"] == "C1-FL-KEEPER")
    assert k["kg"] is None and k["missing"]                       # not 0 (not excluded), not 5.4 kg (not assumed)
    # ground (development / reference C1) lines stay booked
    assert lines["C1-GT-KEEPER"]["presence"] == "PRESENT"
    items = {i["id"]: i for i in d["items"]}
    assert items["XV3-01"]["value"] == "NOT_SELECTED" and items["XV3-02"]["value"] is None


def test_icp_gas_mode_baseline_unchanged(d):
    lines = {x["id"]: x for x in d["ledger_lines"]}
    assert lines["P-FL-ICP-XE"]["presence"] == "EXACT_ZERO_BY_OWNER_DECISION"
    assert lines["OPT-FL-GXE"]["presence"] == "PRESENT_WHEN_ACTIVATED"
    assert "G-REUSE primary" in d["propellant_policy"]["icp_gas_mode_baseline_unchanged"]


def test_icp_getter_engineering_requirement(m):
    assert m.icp_xe_getter(False)["state"] == "NOT_APPLICABLE_G_REUSE_BASELINE"
    assert m.icp_xe_getter(True)["state"] == "NOT_REQUIRED_BY_DEFAULT"
    assert m.icp_xe_getter(True, {"source": "spec X", "requires_getter": True})["state"] == \
        "REQUIRED_BY_SPEC_TBD_MASS_POWER"
    with pytest.raises(m.BookingError):
        m.icp_xe_getter(True, {"requires_getter": True})


# ------------------------------------------------------------------------------- loaded cases, dwell, margins
def test_loaded_cases_only_residual_inside(m, d):
    rows = d["design_cases"]["loaded_split"]["rows"]
    assert [r["case_kg"] for r in rows] == [2.0, 5.0, 10.0]
    for r in rows:
        assert r["loaded_kg"] == r["case_kg"]
        assert abs(r["mission_usable_kg"] + r["reserve_kg"] + r["residual_kg"] - r["loaded_kg"]) < 1e-5
    with pytest.raises(m.BookingError):
        m.case_split_loaded(2.0, 0.2, 0.02, reading="USABLE_RESIDUAL_ON_TOP")
    with pytest.raises(m.BookingError):
        m.case_split_loaded(float("nan"), 0.2, 0.02)
    assert d["reading_axes_resolved"]["RA-CASE"]["v3"] == "LOADED"
    assert all(ag["agrees"] for ag in d["design_cases"]["v2_agreement"])


def test_ignition_booking_three_by_120(m, d):
    assert m.ignition_booking_s() == 360.0
    items = {i["id"]: i for i in d["items"]}
    assert items["XV2-08"]["value"] == 3.0 and items["XV2-42"]["value"] == 360.0
    assert "value_by_reading" not in items["XV2-08"]
    for bad in (4, 0, 2.5, True):
        with pytest.raises(m.BookingError):
            m.ignition_booking_s(bad)
    with pytest.raises(m.BookingError):
        m.ignition_booking_s(3, 121.0)
    with pytest.raises(m.BookingError):
        m.ignition_booking_s(3, 100.0)                 # tighter dwell only with evidence
    assert m.ignition_booking_s(3, 100.0, evidence="measured H-1 start log") == 300.0


def test_flow_class_inside_reserve_base(m, d):
    lines = {x["id"]: x for x in d["ledger_lines"]}
    assert lines["C1-FL-FLOWUNC"]["reserve_base"] is True
    assert all(x["reserve_base"] is True for x in d["ledger_lines"] if x["ledger"] == "FLIGHT")
    ld = {"A": {"phase": "xe_mode", "reserve_base": "RA-FLOWUNC"}}
    with pytest.raises(m.BookingError):
        m.book_reserve_and_residual([{"line": "A", "kg": 1.0}], ld, 0.2, 0.02)


def test_reserve_residual_once(m):
    ld = {"A": {"phase": "xe_mode", "reserve_base": True}, "B": {"phase": "transition", "reserve_base": True}}
    b = m.book_reserve_and_residual([{"line": "A", "kg": 1.0}, {"line": "B", "kg": 0.5}], ld, 0.2, 0.02)
    assert b["status"] == "COMPUTED"
    t = b["totals"]
    assert t["reserve_kg"] == 0.3 and abs(t["loaded_kg"] - 1.8 * 1.02) < 1e-12
    with pytest.raises(m.BookingError):
        m.book_reserve_and_residual([{"line": "A", "kg": 1.0}, {"line": "A", "kg": 1.0}], ld, 0.2, 0.02)
    with pytest.raises(m.BookingError):
        m.book_reserve_and_residual([{"line": "RESIDUAL", "kg": 1.0}], dict(ld, RESIDUAL={"phase": "residual",
                                                                                         "reserve_base": True}), 0.2, 0.02)
    r = m.book_reserve_and_residual([{"line": "A", "kg": None}], ld, 0.2, 0.02)
    assert r["status"] == "REFUSED_TBD_INPUTS" and r["totals"] is None


def test_ground_logistics_margin_and_explicit_procedures(m, d):
    procs = {"purge": 0.1, "conditioning": 0.2, "line_fill": 0.05, "vendor_procedures": 0.15}
    g = m.ground_supply({"ref": 1.5}, procs)
    assert g["status"] == "COMPUTED" and g["calculated_kg"] == 2.0 and g["margin_kg"] == 0.4 and g["supply_kg"] == 2.4
    with pytest.raises(m.BookingError):
        m.ground_supply({"ref": 1.0}, procs, margin=0.1)
    with pytest.raises(m.BookingError):
        m.ground_supply({"ref": 1.0}, {"purge": 0.1})            # procedures must be booked explicitly
    r = m.ground_supply({"ref": 1.0}, dict(procs, line_fill=None))
    assert r["status"] == "REFUSED_TBD_INPUTS" and "line_fill" in r["tbd"]
    items = {i["id"]: i for i in d["items"]}
    assert items["XV2-37"]["value"] == 0.2
    for sc in d["scenarios"]:
        if sc["ledger"] == "GROUND_TEST":
            assert sum(1 for x in sc["lines"] if "-PROC-" in x) == 4, sc["id"]
    for e in d["evaluations"]:
        if e["scenario"].split("-")[1] == "GT":
            assert e["booking"]["status"] == "REFUSED_TBD_INPUTS" and e["booking"]["supply_kg"] is None


def test_meop_placeholder_retired(m, d):
    assert all(r["p_bar"] != 75.0 for r in d["design_cases"]["density_axis"]["rows"])
    assert all(r["p_bar"] != 75.0 for r in d["design_cases"]["tank_volume"]["rows"])
    items = {i["id"]: i for i in d["items"]}
    assert items["XV2-28"]["value"] is None and "TBD_FROM_QUOTATIONS" in items["XV2-28"]["status"]
    assert m.meop_basis(None)["state"] == "TBD_FROM_QUOTATIONS"
    with pytest.raises(m.BookingError):
        m.meop_basis({"meop_bar": 75.0, "basis": "placeholder"})
    assert m.meop_basis({"meop_bar": 150.0})["state"] == "NOT_SELECTED_INCOMPLETE_BASIS"
    full = {"meop_bar": 150.0, "design_case_kg": 5.0, "design_temperature_K": 293.15, "supplier_quotation_id": "Q-1",
            "supplier_qualification_basis": "x", "pressure_vessel_practice": "y"}
    assert m.meop_basis(full)["state"] == "NOT_SELECTED_WRONG_DESIGN_TEMPERATURE"
    assert m.meop_basis(dict(full, design_temperature_K=323.0))["state"] == \
        "CANDIDATE_FROM_QUOTATION_OWNER_SELECTION_PENDING"


def test_no_total_with_tbd_and_no_pass(d):
    for e in d["evaluations"]:
        b = e["booking"]
        if b["tbd_lines"]:
            assert b["status"].startswith("REFUSED")
    assert "PASS" not in json.dumps(d["evaluations"])


def test_v2_ids_carried(d):
    v2 = json.loads((REPO / "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json").read_text(encoding="utf-8"))
    ids3 = {i["id"] for i in d["items"]}
    assert {i["id"] for i in v2["items"]} <= ids3
    assert {x["id"] for x in v2["ledger_lines"]} <= {x["id"] for x in d["ledger_lines"]}
    assert all(i.get("owner_answers_applied") is not None for i in d["items"])



def test_a9_16_repair_f6_f11_c1_scope_placeholder_and_icp_feed_label(d):
    """A9.16 repair F6: P-FL-C1 is a configuration-scope zero (no C1 in hall_icp_neutralizer), not an owner Xe exclusion;
    XV2-02 and the C1 sensitivity are A5 design-target placeholders (no within-ceiling verdict). F11: the ICP-feed
    'contingency' label is the owner's A9.1 HIQ-06 term, and whether A9.15 changes it is open owner question XV3Q-01."""
    ln = {x["id"]: x for x in d["ledger_lines"]}
    p = ln["P-FL-C1"]
    assert p["presence"] == "ZERO_BY_SCOPE" and p["presence_v2"] == "ABSENT_BY_OWNER_DECISION"
    assert p["scope_note"].startswith("CONFIGURATION_SCOPE_EXCLUSION") and "PENDING_C1_NOT_SELECTED" in p["scope_note"]
    for x in d["ledger_lines"]:
        if "contingency" in x["name"] and x.get("gas_mode") in ("G-ATM", "G-XE"):
            assert "A9.1 HIQ-06" in x["label_note"], x["id"]
    it = {x["id"]: x for x in d["items"]}
    assert it["XV2-02"]["status"].startswith("A5_DESIGN_TARGET_PLACEHOLDER") and "FIXED_DESIGN_TERM" in \
        it["XV2-02"]["status_v2"]
    cs = d["design_cases"]["c1_conditional_sensitivity"]
    assert cs["label"].startswith("A5_DESIGN_TARGET_PLACEHOLDER_SENSITIVITY_NOT_BOOKED")
    assert all(set(r) == {"case_kg", "c1_flow_ceiling_mg_s_all_other_terms_zero"} for r in cs["flow_ceiling_rows"])
    for i in ("XV2-22", "XV2-44"):
        assert "A9.1 HIQ-06" in it[i]["label_note"] and "XV3Q-01" in it[i]["label_note"]
    q = {x["id"]: x for x in d["open_owner_questions"]}["XV3Q-01"]
    assert q["status"] == "OPEN" and "separately declared contingency variants" in q["a9_1_basis_verbatim"]
    a91 = (REPO / "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md").read_text(encoding="utf-8")
    assert " ".join(q["a9_1_basis_verbatim"].split()) in " ".join(a91.split())
    md = (REPO / "docs/budgets/xe_accounting_a9_v3/XE_ACCOUNTING_A9_V3.md").read_text(encoding="utf-8")
    assert "| within |" not in md and "XV3Q-01: OPEN" in md


def test_propellant_policy_cites_registered_rfp_clauses():
    """A9.16 repair RFP-06: the propellant policy cites the registered RFP clauses, no 'pending registration' wording."""
    d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rc = d["propellant_policy"]["rfp_clauses"]
    assert [c["clause_id"] for c in rc["clauses"]] == ["RFP-P18-08", "RFP-P17-05", "RFP-P16-02"]
    assert "Two separate propellant tanks" in rc["clauses"][0]["verbatim"]
    for c in d["propellant_policy"]["per_configuration"]:
        assert "pending" not in c["storage_paths"] and "RFP-P18-08" in c["storage_paths"]
