"""Tests for the A9.6 complete Xe accounting v2 (docs/budgets/xe_accounting_a9_v2/, follow-on fo_a9_6_xe_accounting).

Checks: byte-for-byte reproduction; pinned inputs (incl. the immutable A9-08 Xe ledger) unchanged; primary G-REUSE books
m_Xe,ICP = 0 exactly; every C1 phase is its own line; optional G-XE / G-ATM / diagnostic entries are absent from every
primary scenario; reserve and residual are booked exactly once (no double counting, including a synthetic proof and the
refusal of a second booking); fail-closed evaluation (TBD -> REFUSED, malformed lines raise, no default fractions); both
readings of every OPEN owner question are carried and none is answered; design cases under both case readings and the
323.15 K tank volumes reproduce the verified A9-08 table and the pinned NIST snapshot. Only this lane's files are
exercised. Run: python -m pytest -q tests/test_xe_accounting_a9_v2.py   (well under a second).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "xe_accounting_a9_v2"
BUILDER = LANE / "build_xe_accounting_a9_v2.py"
OUT_JSON = LANE / "xe_accounting_a9_v2.json"
OUT_MD = LANE / "XE_ACCOUNTING_A9_V2.md"
FORBIDDEN = "xe" + "_ledger"          # never spelled contiguously in code outside the v1 module
PREV_DIR = REPO / "docs" / "budgets" / (FORBIDDEN + "_a9")


def _mod(name="build_xe_accounting_a9_v2_under_test"):
    spec = importlib.util.spec_from_file_location(name, BUILDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _mod()


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _evals(d, sid):
    return [e for e in d["evaluations"] if e["scenario"] == sid]


def _ev(d, sid, **reading):
    return next(e for e in _evals(d, sid) if e["reading"] == reading)


def _line(e, lid):
    return next(x for x in e["lines"] if x["line"] == lid)


def _items(d):
    return {i["id"]: i for i in d["items"]}


# ------------------------------------------------------------------------------------------------ reproduction / pins
def test_builder_reproduces_outputs(mod):
    js, md = mod.render()
    assert OUT_JSON.read_text(encoding="utf-8") == js
    assert OUT_MD.read_text(encoding="utf-8") == md
    assert mod.main(["--check"]) == 0


def test_pins_verified_and_governance_never_pinned(d):
    allp = [p for grp in d["pins"].values() for p in grp]
    for p in allp:
        assert _sha(REPO / p["path"]) == p["sha256"], p["path"]
    joined = " ".join(p["path"] for p in allp)
    for banned in ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state"):
        assert banned not in joined
    for need in ("A9", "ANS", "PACK", "A91", "A92", "A93", "A94", "A95", "A96", "A96MD"):
        assert need in {p["key"] for p in d["pins"]["decisions"]}


def test_a908_revision_base_pinned_and_unchanged(d):
    prev = PREV_DIR / (FORBIDDEN + "_a9_v1.json")
    assert d["revision_of"]["path"] == str(prev.relative_to(REPO))
    assert _sha(prev) == d["revision_of"]["sha256"] == "37c32cda9fb04200f6e9041b0e790ca700e270866f29e7c10f8a298034ddacfd"
    for h in d["historical_reuse"]:
        assert _sha(REPO / h["artifact"]) == h["sha256"], h["artifact"]


def test_refuses_on_pin_mismatch():
    m = _mod("build_xe_accounting_a9_v2_pin_mismatch")
    rel, _h, role = m.DECISIONS["A96"]
    m.DECISIONS["A96"] = (rel, "0" * 64, role)
    with pytest.raises(m.PinError):
        m.build_doc()


def test_code_hygiene():
    for p in (BUILDER, Path(__file__)):
        src = p.read_text(encoding="utf-8")
        assert FORBIDDEN not in src, p.name
    src = BUILDER.read_text(encoding="utf-8")
    for banned in ("import archengine", "from abep_sim", "hall_map", "hall_ensemble", "plasma_devices", "julia"):
        assert banned not in src, banned


def test_sections_present(d):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact"):
        assert d[k], k
    assert {x["direction"] for x in d["interface_demands"]} == {"IN", "OUT"}


# ------------------------------------------------------------------------------------------------ CASE-1 primary
def test_primary_greuse_icp_xe_exactly_zero(d):
    it = _items(d)
    assert it["XV2-21"]["value"] == 0.0 and it["XV2-21"]["a9_08_item"] == "XA9-21"
    for e in _evals(d, "S1-FL-PRIMARY") + _evals(d, "S1-GT-PRIMARY"):
        lid = "P-FL-ICP-XE" if e["scenario"].startswith("S1-FL") else "P-GT-ICP-XE"
        x = _line(e, lid)
        assert x["presence"] == "EXACT_ZERO_BY_OWNER_DECISION" and x["kg"] == 0.0
        assert _line(e, lid)["kg"] == 0.0
    c1 = _line(_ev(d, "S1-FL-PRIMARY", **{"RA-FUNC": "APPLIES"}), "P-FL-C1")
    assert c1["presence"] == "ABSENT_BY_OWNER_DECISION" and c1["kg"] == 0.0


def test_optional_entries_never_in_primary(d):
    opt = {ln["id"] for ln in d["ledger_lines"] if ln["optional_entry"]}
    assert opt == {"OPT-FL-GXE", "OPT-FL-FLOWUNC-GXE", "OPT-FL-GATM", "OPT-GT-GXE", "OPT-GT-GATM",
                   "OPT-GT-P1-GXE-DIAG"}
    for ln in d["ledger_lines"]:
        assert ln["optional_entry"] == (ln["case"] == "CASE-3"), ln["id"]
    for sc in d["scenarios"]:
        if sc["case"] != "CASE-3":
            assert not opt & set(sc["lines"]), sc["id"]
    gxe = [s for s in d["scenarios"] if s["id"] == "S3-FL-GXE"][0]
    assert "OPT-FL-GXE" in gxe["lines"] and "P-FL-ICP-XE" not in gxe["lines"]   # replaces, never adds to, G-REUSE
    for e in _evals(d, "S3-FL-GXE"):
        assert _line(e, "OPT-FL-GXE")["kg"] is None and e["booking"]["status"] == "REFUSED_TBD_INPUTS"
    for e in _evals(d, "S3-FL-GATM"):
        assert _line(e, "OPT-FL-GATM")["kg"] == 0.0


def test_p1_bench_is_ar_only(d):
    it = _items(d)["XV2-43"]
    assert it["value"] == 0.0 and "Ar engineering reproduction" in it["source"]
    assert _line(_ev(d, "S1-GT-PRIMARY"), "P-GT-P1-BENCH")["presence"] == "ZERO_BY_SCOPE"


def test_row6_functional_mode_both_readings(d):
    app = _ev(d, "S1-FL-PRIMARY", **{"RA-FUNC": "APPLIES"})
    assert app["booking"]["status"] == "REFUSED_TBD_INPUTS" and "P-FL-FUNC" in app["booking"]["tbd_lines"]
    assert _line(app, "P-FL-FUNC")["presence"] == "PRESENT"
    nap = _ev(d, "S1-FL-PRIMARY", **{"RA-FUNC": "NOT_APPLIED"})
    assert nap["booking"]["status"] == "COMPUTED_EXACT_ZERO" and nap["booking"]["totals"]["loaded_kg"] == 0.0
    assert all(x["kg"] == 0.0 for x in nap["lines"])
    # ground-test Xe does not depend on the flight reading
    assert _line(_ev(d, "S1-GT-PRIMARY"), "P-GT-XE-REFERENCE")["presence"] == "PRESENT"


# ------------------------------------------------------------------------------------------------ CASE-2 C1 reference
def test_c1_every_phase_is_its_own_sourced_line(d):
    sc = [s for s in d["scenarios"] if s["id"] == "S2-FL-C1"][0]
    lines = {ln["id"]: ln for ln in d["ledger_lines"]}
    phases = {}
    for lid in sc["lines"]:
        phases.setdefault(lines[lid]["phase"], []).append(lid)
        assert lines[lid]["sources"] and all(s for s in lines[lid]["sources"]), lid
    for ph in ("purge", "preheat", "ignition", "keeper_cathode", "transition", "fallback"):
        assert ph in phases, ph
    for lid in ("C1-FL-PURGE", "C1-FL-HEAT", "C1-FL-IGN", "C1-FL-KEEPER", "C1-FL-TRANSITION", "C1-FL-FALLBACK"):
        assert lid in sc["lines"]
    assert "row 93" in " ".join(lines["C1-FL-PURGE"]["sources"]) and "row 42" in " ".join(lines["C1-FL-HEAT"]["sources"])
    gt = [s for s in d["scenarios"] if s["id"] == "S2-GT-C1"][0]["lines"]
    for lid in ("C1-GT-PURGE", "C1-GT-HEAT", "C1-GT-IGN", "C1-GT-KEEPER", "C1-GT-TRANSITION"):
        assert lid in gt
    # C1 lines only in the C1 configuration (OQ-A902-04: no combined flight C1 + ICP)
    for ln in d["ledger_lines"]:
        if ln["id"].startswith("C1-"):
            assert ln["configuration"] == "hall_c1_reference"


def test_c1_closed_values(d):
    e = _ev(d, "S2-FL-C1", **{"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    assert _line(e, "C1-FL-KEEPER")["kg"] == 5.4          # 0.1 mg/s x 15,000 h (A5, row 46)
    assert _line(e, "C1-FL-FLOWUNC")["kg"] == 0.216       # 0.02 x 0.2 mg/s x 15,000 h (row 96)
    assert _line(e, "C1-FL-ICP-XE")["kg"] == 0.0
    f = e["booking"]["floors_closed_terms_only"]
    assert (f["reserve_kg"], f["residual_kg"], f["loaded_kg"]) == (1.1232, 0.134784, 6.873984)
    o = _ev(d, "S2-FL-C1", **{"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"})
    g = o["booking"]["floors_closed_terms_only"]
    assert (g["reserve_base_kg"], g["outside_base_kg"], g["reserve_kg"]) == (5.4, 0.216, 1.08)


def test_dwell_readings_both_carried(mod, d):
    it = _items(d)
    assert it["XV2-08"]["value"] is None and it["XV2-08"]["value_by_reading"] == {"ATTEMPTS_3": 3.0, "ATTEMPTS_2": 2.0}
    assert it["XV2-42"]["value_by_reading"] == {"ATTEMPTS_3": 360.0, "ATTEMPTS_2": 240.0}
    assert "TBD_OWNER" in it["XV2-08"]["status"]
    rows = {r["reading"]: r for r in d["design_cases"]["c1_ignition_per_start"]["rows"]}
    assert rows["ATTEMPTS_3"]["xe_per_start_per_mg_s_of_ignition_flow_kg"] == 0.00036
    assert rows["ATTEMPTS_2"]["xe_per_start_per_mg_s_of_ignition_flow_kg"] == 0.00024
    # synthetic inputs (test only): one start at 1 mg/s ignition flow
    items = copy.deepcopy(_items(d))
    items["XV2-14"]["value"] = 1.0
    items["XV2-09"]["value"] = 1.0
    ln = next(x for x in d["ledger_lines"] if x["id"] == "C1-FL-IGN")
    kg3 = mod.eval_line(ln, items, {"RA-DWELL": "ATTEMPTS_3"}, {})["kg"]
    kg2 = mod.eval_line(ln, items, {"RA-DWELL": "ATTEMPTS_2"}, {})["kg"]
    assert (kg3, kg2) == (0.00036, 0.00024)
    with pytest.raises(mod.BookingError):
        mod.eval_line(ln, items, {}, {})                  # no hidden default reading


# ------------------------------------------------------------------------------------------------ reserve / residual
def test_reserve_and_residual_booked_exactly_once(d):
    lines = {ln["id"]: ln for ln in d["ledger_lines"]}
    assert not [ln for ln in d["ledger_lines"] if ln["phase"] in ("reserve", "residual")]
    for e in d["evaluations"]:
        b = e["booking"]
        assert not [x for x in e["lines"] if lines[x["line"]]["phase"] in ("reserve", "residual")]
        assert len({x["line"] for x in e["lines"]}) == len(e["lines"])
        if e["scenario"].split("-")[1] == "FL":
            assert b["reserve_line"]["phase"] == "reserve" and b["residual_line"]["phase"] == "residual"
            f = b["floors_closed_terms_only"]
            assert abs(f["non_reserve_kg"] + f["reserve_kg"] + f["residual_kg"] - f["loaded_kg"]) < 1e-9
            assert abs(f["reserve_kg"] - 0.2 * f["reserve_base_kg"]) < 1e-12
            assert abs(f["residual_kg"] - 0.02 * f["usable_kg"]) < 1e-12
        else:
            assert "reserve_line" not in b and "residual_line" not in b
            assert "XA9Q-04" in b["reserve_residual"]


def test_booking_function_synthetic_and_refuses_double_counting(mod):
    lines = {"A": {"phase": "keeper_cathode", "reserve_base": True},
             "B": {"phase": "uncertainty", "reserve_base": "RA-FLOWUNC"},
             "RESERVE": {"phase": "reserve", "reserve_base": True}}
    evals = [{"line": "A", "kg": 10.0}, {"line": "B", "kg": 1.0}]
    ins = mod.book_reserve_and_residual(evals, lines, 0.2, 0.02, {"RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    assert ins["status"] == "COMPUTED"
    t = ins["totals"]
    assert (t["reserve_kg"], t["usable_kg"], t["residual_kg"], t["loaded_kg"]) == (2.2, 13.2, 0.264, 13.464)
    out = mod.book_reserve_and_residual(evals, lines, 0.2, 0.02, {"RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"})
    t = out["totals"]
    assert (t["reserve_kg"], t["usable_kg"], t["residual_kg"], t["loaded_kg"]) == (2.0, 13.0, 0.26, 13.26)
    with pytest.raises(mod.BookingError):     # a second reserve booking
        mod.book_reserve_and_residual(evals + [{"line": "RESERVE", "kg": 2.2}], lines, 0.2, 0.02,
                                      {"RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    with pytest.raises(mod.BookingError):     # the same line twice
        mod.book_reserve_and_residual(evals + [evals[0]], lines, 0.2, 0.02, {"RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    with pytest.raises(mod.BookingError):     # no default fraction
        mod.book_reserve_and_residual(evals, lines, None, 0.02, {"RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    with pytest.raises(mod.BookingError):     # no default reading
        mod.book_reserve_and_residual(evals, lines, 0.2, 0.02, {})
    tbd = mod.book_reserve_and_residual([{"line": "A", "kg": None}, {"line": "B", "kg": 1.0}], lines, 0.2, 0.02,
                                        {"RA-FLOWUNC": "INSIDE_RESERVE_BASE"})
    assert tbd["status"] == "REFUSED_TBD_INPUTS" and tbd["totals"] is None and tbd["reserve_line"]["kg"] is None


def test_reserve_line_cannot_be_declared(mod):
    bad = mod.L("X", "CASE-2", "hall_c1_reference", None, "FLIGHT", "reserve", "x", "x", [], "PRESENT", None, ["s"])
    with pytest.raises(mod.BookingError):
        mod._validate_line(bad)


def test_design_case_split_counts_residual_once(mod, d):
    for rd in ("LOADED", "USABLE_RESIDUAL_ON_TOP"):
        for c in (2.0, 5.0, 10.0):
            s = mod.case_split(c, rd, 0.2, 0.02)
            assert abs(s["non_reserve_cap_kg"] + s["reserve_kg"] + s["residual_kg"] - s["loaded_kg"]) < 1e-12
            assert s["loaded_kg"] == (c if rd == "LOADED" else c * 1.02)
    with pytest.raises(mod.BookingError):
        mod.case_split(2.0, "OTHER", 0.2, 0.02)
    readings = {r["reading"] for r in d["design_cases"]["reserve_residual_split"]["rows"]}
    assert readings == {"LOADED", "USABLE_RESIDUAL_ON_TOP"}


# ------------------------------------------------------------------------------------------------ fail-closed
def test_fail_closed_evaluation(mod, d):
    items = copy.deepcopy(_items(d))
    keeper = next(x for x in d["ledger_lines"] if x["id"] == "C1-FL-KEEPER")
    items["XV2-02"]["value"] = None
    r = mod.eval_line(keeper, items, {}, {})
    assert r["kg"] is None and r["missing"][0]["item"] == "XV2-02"
    bad = copy.deepcopy(keeper)
    bad["fields"] = [mod.F("t1", "XV2-01", "h"), mod.F("t2", "XV2-01", "h")]
    with pytest.raises(mod.BookingError):
        mod._validate_line(bad)
    bad["fields"] = [mod.F("m", "XV2-02", "kg/h"), mod.F("t", "XV2-01", "h")]
    with pytest.raises(mod.BookingError):
        mod._validate_line(bad)
    bad = copy.deepcopy(keeper)
    bad["presence"] = "SOMETHING"
    with pytest.raises(mod.BookingError):
        mod._validate_line(bad)


def test_every_total_with_tbd_is_refused(d):
    for e in d["evaluations"]:
        b = e["booking"]
        has_tbd = any(x["kg"] is None for x in e["lines"])
        assert (b["status"] == "REFUSED_TBD_INPUTS") == has_tbd
        if has_tbd:
            assert b.get("totals") is None and b.get("total_kg") is None


# ------------------------------------------------------------------------------------------------ design cases / tank
def _tsv(path):
    rows = path.read_text(encoding="utf-8").splitlines()
    h = rows[0].split("\t")
    ip, ir = h.index("Pressure (bar)"), h.index("Density (kg/m3)")
    return {float(r.split("\t")[ip]): float(r.split("\t")[ir]) for r in rows[1:] if r.strip()}


def test_tank_volume_reproduces_a908_and_nist(d):
    prev = json.loads((PREV_DIR / (FORBIDDEN + "_a9_v1.json")).read_text(encoding="utf-8"))
    pv = {(r["case_kg"], r["p_bar"]): r["V_min_323K_l"] for r in prev["design_cases"]["tank_volume"]["rows"]}
    rho = _tsv(PREV_DIR / "sources" / "nist_webbook_xe_isotherm_323.15K_70-200bar.tsv")
    rows = d["design_cases"]["tank_volume"]["rows"]
    assert len(rows) == 2 * 3 * 4
    for r in rows:
        loaded = r["case_kg"] * (1.0 if r["reading"] == "LOADED" else 1.02)
        v = float(f"{loaded / (rho[r['p_bar']] * (1 - 0.002)) * 1000.0:.6g}")
        assert r["V_min_323K_l"] == v
        if r["reading"] == "LOADED":
            assert r["V_min_323K_l"] == pv[(r["case_kg"], r["p_bar"])]
        else:
            assert r["V_min_323K_l"] > pv[(r["case_kg"], r["p_bar"])]
    for a in d["design_cases"]["density_axis"]["rows"]:
        assert a["rho_323K_kg_m3"] == rho[a["p_bar"]]
    assert d["design_cases"]["a9_08_agreement"] and all(a["agrees"] for a in d["design_cases"]["a9_08_agreement"])


def test_headroom_both_readings_and_no_xe_case(d):
    rows = d["design_cases"]["headroom"]["rows"]
    c1 = {(r["reading"]["RA-FLOWUNC"], r["reading"]["RA-CASE"], r["case_kg"]): r for r in rows
          if r["scenario"] == "S2-FL-C1"}
    assert len(c1) == 12
    assert c1[("INSIDE_RESERVE_BASE", "LOADED", 10.0)]["headroom_for_TBD_terms_kg"] == 2.55393   # = A9-08
    assert c1[("INSIDE_RESERVE_BASE", "LOADED", 2.0)]["status"] == "EXCEEDED_BY_CLOSED_TERMS"
    nap = [r for r in rows if r["scenario"] == "S1-FL-PRIMARY" and r["reading"]["RA-FUNC"] == "NOT_APPLIED"]
    assert nap and all(r["status"] == "NOT_APPLICABLE_NO_FLIGHT_XE_UNDER_READING" for r in nap)
    assert all("RA-DWELL" not in r["reading"] for r in rows)


# ------------------------------------------------------------------------------------------------ owner discipline
def test_open_questions_carried_not_answered(d):
    oqs = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v3.json").read_text(encoding="utf-8"))
    st = {r["id"]: r["status"] for r in oqs["rows"]}
    carried = {q["id"] for q in d["open_questions_carried"]}
    assert carried == {"XA9Q-01", "XA9Q-02", "XA9Q-03", "XA9Q-07", "MQ-09", "OQ-A907-01", "OQ-A910-01"}
    for q in carried:
        assert st[q] == "OPEN"
    for axis, spec in d["reading_axes"].items():
        assert len(spec["readings"]) == 2, axis
    for q in d["open_owner_questions"]:
        assert q["status"] == "OPEN" and q["id"] not in st and q["needed_by"]


def test_owner_answers_verbatim(d):
    ans = json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json").read_text(encoding="utf-8"))
    rows = {f"row {r['row']}": r["owner_answer_verbatim"] for r in ans["answers"]}
    applied = [a for a in d["owner_answers_applied"] if a["decision"] == "147 answers"]
    for a in applied:
        assert a["owner_answer_verbatim"] == rows[a["id"]]
    ids = {a["id"] for a in applied}
    for need in ("row 6", "row 42", "row 43", "row 45", "row 46", "row 48", "row 50", "row 93", "row 96"):
        assert need in ids
    a96 = [a for a in d["owner_answers_applied"] if a["id"] == "sec. 12"][0]
    assert "m_{\\rm Xe,ICP}=0" in a96["owner_answer_verbatim"] and "double-count" in a96["owner_answer_verbatim"]


def test_item_discipline(d):
    need = ("id", "value", "unit", "basis", "source", "evidence_class", "status", "freeze_point")
    classes = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation",
               "none"}
    for it in d["items"]:
        for k in need:
            assert k in it, (it["id"], k)
        assert it["evidence_class"] in classes and it["freeze_point"] in ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
        assert it["source"]
        if it["value"] is None:
            assert str(it["value_display"]).startswith("TBD"), it["id"]
            if it["evidence_class"] == "none":
                assert "TBD" in it["status"]


def test_no_pass_no_winner(d):
    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        else:
            yield x
    for v in walk(d):
        assert v != "PASS"
    txt = json.dumps(d).lower()
    for banned in ("winner:", "best architecture", "recommended architecture", "sgb-screen", "ensemble_member_id"):
        assert banned not in txt
    assert d["a9_6_fixed_statuses_unchanged"]["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
