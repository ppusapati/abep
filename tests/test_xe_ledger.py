"""Parametric Xe ledger + stored-Xe subsystem ledger v1 (fo_xe_system_ledger; owner addenda A5/A6).

Checks that abep_sim/xe_ledger.py implements exactly the A6 formulas with no hidden defaults (missing/TBD inputs raise
and are all listed; every value needs unit, source and evidence class), that the explicit reserve and tank forms and the
inverse allowance solver are consistent, that Hall-closure / P5-nuisance keys are refused, that the builder reproduces
the committed JSON + MD byte for byte, that the owner decision files and the G0 record are pinned by sha256, that the
cathode design term is 5.4 kg (8.1 kg at the 0.15 mg/s test point) as in A5, that no total Xe mass and no
startup/transition/fallback value is frozen (A6 not_authorized), that scenarios are labelled illustrative and recompute
from their own parameters, that analogue transcriptions match the base evidence deliverables, and that nothing ranks
hall_only / rf_hall / ecr_hall. Run: python -m pytest -q tests/test_xe_ledger.py   (a few seconds).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from abep_sim import xe_ledger as xl

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "budgets" / "xe_ledger"
SCRIPT = DIR / "build_xe_ledger.py"
JSON_PATH = DIR / "xe_ledger_v1.json"
MD_PATH = DIR / "XE_LEDGER.md"
A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0 = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
CATHINT = REPO / "docs" / "architecture_comparison" / "cathode_integration" / "cathode_integration_data_v1.json"
HSUST = REPO / "docs" / "evidence" / "hall_sustainment" / "hall_sustainment_matrix.json"
DOSSIER = REPO / "docs" / "evidence" / "cathode" / "CATHODE_DOSSIER.md"
EVIDENCE = set(xl.EVIDENCE_CLASSES)
TBD_FIELDS = ("N_starts", "t_startup", "mdot_startup", "N_transitions", "t_transition", "mdot_transition",
              "t_fallback_max", "mdot_fallback", "reserve_policy", "tank_model", "m_regulator", "m_valves",
              "m_plumbing", "m_mounting_thermal")


def Q(v, unit, ev="assumed", src="test fixture (not evidence)"):
    return xl.Quantity(v, unit, src, ev)


def full_inputs(**over) -> dict:
    """A complete synthetic input set (test fixture values, not evidence)."""
    inp = {"architecture_scope": ["hall_only", "rf_hall", "ecr_hall"], "accounting_convention": "PHASE_TOTAL_FLOW",
           "mdot_cathode": Q(0.10, "mg/s"), "t_firing": Q(15000.0, "h"),
           "N_starts": Q(100.0, "1"), "t_startup": Q(600.0, "s"), "mdot_startup": Q(2.0, "mg/s"),
           "N_transitions": Q(100.0, "1"), "t_transition": Q(60.0, "s"), "mdot_transition": Q(5.0, "mg/s"),
           "t_fallback_max": Q(10.0, "h"), "mdot_fallback": Q(4.0, "mg/s"),
           "reserve_policy": {"form": "fraction_of_other_terms", "value": Q(0.1, "1")},
           "tank_model": {"form": "tankage_fraction", "value": Q(0.2, "1")},
           "m_regulator": Q(0.5, "kg"), "m_valves": Q(0.3, "kg"), "m_plumbing": Q(0.2, "kg"),
           "m_mounting_thermal": Q(0.4, "kg")}
    inp.update(over)
    return inp


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("_xe_ledger_builder_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(JSON_PATH.read_text())


# ------------------------------------------------------------------------------------------------ module: formulas
def test_terms_match_a6_formulas():
    ev = xl.evaluate(full_inputs(), level="subsystem")
    t = ev["terms_kg"]
    assert t["m_cathode"] == pytest.approx(0.10e-6 * 15000 * 3600)
    assert t["m_startup"] == pytest.approx(100 * 600 * 2.0e-6)
    assert t["m_transition"] == pytest.approx(100 * 60 * 5.0e-6)
    assert t["m_fallback"] == pytest.approx(10 * 3600 * 4.0e-6)
    others = t["m_cathode"] + t["m_startup"] + t["m_transition"] + t["m_fallback"]
    assert t["m_reserve"] == pytest.approx(0.1 * others)
    assert ev["m_Xe_total_kg"] == pytest.approx(1.1 * others)
    assert ev["m_tank_kg"] == pytest.approx(0.2 * ev["m_Xe_total_kg"])
    assert ev["m_Xe_subsystem_kg"] == pytest.approx(ev["m_Xe_total_kg"] * 1.2 + 1.4)
    assert ev["complete_xe_total"] and ev["complete_subsystem"] and ev["missing"] == []


def test_cathode_design_term_is_a5_value():
    t = Q(15000.0, "h")
    assert xl.product_term_kg({"mdot_cathode": Q(0.10, "mg/s"), "t_firing": t}, "m_cathode") == pytest.approx(5.4)
    assert xl.product_term_kg({"mdot_cathode": Q(0.15, "mg/s"), "t_firing": t}, "m_cathode") == pytest.approx(8.1)
    assert xl.flow_consuming_mass_mg_s(40.0, t) == pytest.approx(40.0 / 5.4e7 * 1e6)


def test_unit_conversions_are_exact():
    a = xl.product_term_kg({"mdot_cathode": Q(0.10, "mg/s"), "t_firing": Q(15000.0, "h")}, "m_cathode")
    b = xl.product_term_kg({"mdot_cathode": Q(1.0e-7, "kg/s"), "t_firing": Q(5.4e7, "s")}, "m_cathode")
    assert a == pytest.approx(b, rel=1e-12)


def test_reserve_forms_and_tank_forms():
    absr = full_inputs(reserve_policy={"form": "absolute_mass", "value": Q(1.5, "kg")},
                       tank_model={"form": "tank_mass", "value": Q(2.0, "kg")})
    ev = xl.evaluate(absr, level="subsystem")
    assert ev["terms_kg"]["m_reserve"] == pytest.approx(1.5)
    assert ev["m_tank_kg"] == pytest.approx(2.0)
    four = sum(ev["terms_kg"][k] for k in xl.PRODUCT_TERMS)
    assert ev["m_Xe_total_kg"] == pytest.approx(four + 1.5)
    assert ev["m_Xe_subsystem_kg"] == pytest.approx(four + 1.5 + 2.0 + 1.4)
    with pytest.raises(ValueError):
        xl.evaluate(full_inputs(reserve_policy={"form": "percent", "value": Q(10, "1")}), level="xe_total")
    with pytest.raises(ValueError):   # wrong unit for the form
        xl.evaluate(full_inputs(tank_model={"form": "tank_mass", "value": Q(0.2, "1")}), level="subsystem")


# ------------------------------------------------------------------------------------------------ module: refusal
def test_tbd_and_missing_inputs_raise_and_are_all_listed():
    inp = full_inputs(N_starts=xl.TBD("ops concept"), mdot_fallback={"tbd": "H-1 measurement"})
    del inp["m_valves"]
    with pytest.raises(xl.LedgerIncomplete) as exc:
        xl.evaluate(inp, level="subsystem")
    fields = [m["field"] for m in exc.value.missing]
    assert {"N_starts", "mdot_fallback", "m_valves"} <= set(fields)
    part = xl.evaluate(inp, level="subsystem", allow_partial=True)
    assert part["m_Xe_total_kg"] is None and part["m_Xe_subsystem_kg"] is None
    assert part["terms_kg"]["m_startup"] is None and part["terms_kg"]["m_reserve"] is None
    assert part["terms_kg"]["m_cathode"] == pytest.approx(5.4)


def test_no_hidden_defaults():
    with pytest.raises(ValueError):               # a value record without evidence class
        xl.coerce({"value": 1.0, "unit": "kg", "source": "x"}, "m_valves")
    with pytest.raises(ValueError):
        xl.evaluate(full_inputs(m_valves=Q(1.0, "kg", ev="guess")), level="subsystem")
    with pytest.raises(ValueError):
        xl.evaluate(full_inputs(m_valves=xl.Quantity(1.0, "kg", "", "assumed")), level="subsystem")
    for bad in (Q(-1.0, "kg"), Q(True, "kg"), Q(float("nan"), "kg"), Q(1.0, "lb")):
        with pytest.raises(ValueError):
            xl.evaluate(full_inputs(m_valves=bad), level="subsystem")
    with pytest.raises(ValueError):               # counts are whole numbers
        xl.evaluate(full_inputs(N_starts=Q(10.5, "1")), level="xe_total")
    inp = full_inputs()
    del inp["accounting_convention"]
    with pytest.raises(ValueError):
        xl.evaluate(inp, level="xe_total")
    for scope in ([], ["hall_only", "hall_only"], ["hall-only"], "hall_only"):
        with pytest.raises(ValueError):
            xl.evaluate(full_inputs(architecture_scope=scope), level="xe_total")
    with pytest.raises(ValueError):
        xl.allocation_shares(5.4, [])
    with pytest.raises(ValueError):
        xl.allocation_shares(5.4, [{"id": "x", "value_kg": 40.0, "kind": "requirement"}])


def test_hall_closure_and_p5_nuisance_keys_are_refused():
    from abep_sim import mass_bom
    assert xl.CALIBRATION_NUISANCE_KEYS == mass_bom.CALIBRATION_NUISANCE_KEYS
    assert xl.HALL_CLOSURE_KEYS == mass_bom.HALL_CLOSURE_KEYS
    for extra in ({"ensemble_member_id": "m1"}, {"screening_candidate_id": "sgb-screen-01"},
                  {"meta": {"coil_shape": "1.6kW"}}, {"depends_on_hall_closure": True}):
        with pytest.raises(ValueError):
            xl.evaluate(full_inputs(**extra), level="xe_total")


# ------------------------------------------------------------------------------------------------ module: inverse
@pytest.mark.parametrize("rform,rval,tform,tval", [
    ("fraction_of_other_terms", Q(0.1, "1"), "tankage_fraction", Q(0.2, "1")),
    ("fraction_of_other_terms", Q(0.1, "1"), "tank_mass", Q(2.0, "kg")),
    ("absolute_mass", Q(1.0, "kg"), "tankage_fraction", Q(0.2, "1")),
    ("absolute_mass", Q(1.0, "kg"), "tank_mass", Q(2.0, "kg")),
])
def test_xe_sum_cap_closed_forms(rform, rval, tform, tval):
    inp = full_inputs(reserve_policy={"form": rform, "value": rval}, tank_model={"form": tform, "value": tval})
    s = xl.xe_sum_cap_kg(inp, 20.0)
    hw = 1.4
    if tform == "tankage_fraction":
        xe = (20.0 - hw) / 1.2
    else:
        xe = 20.0 - hw - 2.0
    expect = xe / 1.1 if rform == "fraction_of_other_terms" else xe - 1.0
    assert s == pytest.approx(expect)


@pytest.mark.parametrize("field", ["N_starts", "t_fallback_max", "mdot_startup", "N_transitions", "mdot_cathode"])
def test_max_allowance_round_trip(field):
    cap = 15.0
    inp = full_inputs(**{field: xl.TBD("solved")})
    a = xl.max_allowance(inp, field, cap)
    assert a["status"] == "ALLOWANCE" and a["value"] >= 0
    unit = {"count": "1", "time": "h", "mass_flow": "mg/s"}[xl.FIELD_KINDS[field]]
    assert a["unit"] == unit
    at = xl.evaluate(full_inputs(**{field: Q(a["value"], unit)}), level="subsystem")
    assert at["m_Xe_subsystem_kg"] <= cap + 1e-9
    if xl.FIELD_KINDS[field] == "count":
        over = xl.evaluate(full_inputs(**{field: Q(a["value"] + 1.0, unit)}), level="subsystem")
        assert over["m_Xe_subsystem_kg"] > cap
    else:
        assert at["m_Xe_subsystem_kg"] == pytest.approx(cap, rel=1e-9)


def test_max_allowance_statuses_and_guards():
    inp = full_inputs(N_starts=xl.TBD("solved"))
    assert xl.max_allowance(inp, "N_starts", 2.0)["status"] == "EXCEEDED_WITHOUT_THIS_TERM"
    zero = full_inputs(N_starts=xl.TBD("solved"), t_startup=Q(0.0, "s"))
    assert xl.max_allowance(zero, "N_starts", 30.0)["status"] == "NOT_CONSTRAINED"
    with pytest.raises(ValueError):          # the solved field must not also be supplied
        xl.max_allowance(full_inputs(), "N_starts", 30.0)
    with pytest.raises(xl.LedgerIncomplete):  # everything else must be explicit
        xl.max_allowance(full_inputs(N_starts=xl.TBD("solved"), m_plumbing=xl.TBD("procurement")), "N_starts", 30.0)


# ------------------------------------------------------------------------------------------------ deliverable
def test_reproduces_committed_outputs(builder):
    assert builder.main(["--check"]) == 0


def test_decision_files_and_g0_pinned(doc):
    pins = doc["decision_pins"]
    for rel in (A5, A6, G0):
        assert rel in pins, rel
    for rel, h in pins.items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == h, rel
    g0 = json.loads((REPO / G0).read_text())
    assert g0["verdict"] == "CLEAN" and g0["a5_sha256"] == pins[A5]
    assert doc["g0_precondition"]["verdict"] == "CLEAN"
    for mutable in ("lane_registry", "trigger_registry", "trigger_ledger", "runtime_state", "fired_triggers"):
        assert not any(mutable in rel for rel in pins), mutable


def test_header_scope_and_neutrality(doc):
    assert doc["schema"] == "xe_ledger_v1" and doc["follow_on"] == "fo_xe_system_ledger"
    assert doc["trigger"] == "T_A5_XE_LEDGER"
    assert doc["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    assert doc["architecture_neutrality"].startswith("COMMON_MODE")
    for s in doc["scenarios"]:
        assert s["architecture_scope"] == ["hall_only", "rf_hall", "ecr_hall"]
    text = (JSON_PATH.read_text() + MD_PATH.read_text()).lower()
    for w in ("winner", "best architecture", "recommended architecture", "eliminated_within", "conditional_baseline("):
        assert w not in text, w
    for tok in ("ensemble_member_id", "sgb-screen", "hallthruster_bridge/ensemble", "coil_shape", "beam_efficiency",
                "facility_ingestion"):
        assert tok not in text, tok


def test_cathode_term_matches_a5(doc):
    a5 = json.loads((REPO / A5).read_text())["xe_mass_allocation"]
    c = doc["cathode_term"]
    assert c["design_term"]["mdot_mg_s"] == a5["cathode_flow_design_target_mg_s"] == 0.10
    assert c["upper_test_point"]["mdot_mg_s"] == a5["cathode_flow_experimental_upper_test_point_mg_s"] == 0.15
    assert c["design_term"]["m_cathode_kg"] == pytest.approx(a5["reference_arithmetic_15000h"]["0.10_mg_s_kg"])
    assert c["upper_test_point"]["m_cathode_kg"] == pytest.approx(a5["reference_arithmetic_15000h"]["0.15_mg_s_kg"])
    assert "never the allocation" in c["upper_test_point"]["status"]
    shares = {s["id"]: s["share"] for s in c["design_term"]["shares"]}
    assert shares == pytest.approx({"RFP_40kg": 5.4 / 40, "A5_alloc_36kg": 5.4 / 36, "A5_alloc_34kg": 5.4 / 34},
                                   rel=1e-5)
    assert c["rejection_illustration"]["flow_consuming_40kg_in_15000h_mg_s"] == pytest.approx(0.740741, rel=1e-5)


def test_mass_references_match_a5_and_rfp(doc):
    from abep_sim.constants import RFP
    refs = {r["id"]: r for r in doc["mass_references"]}
    assert refs["RFP_40kg"]["value_kg"] == RFP.mass_max_kg == 40.0 and refs["RFP_40kg"]["kind"] == "requirement"
    assert refs["A5_alloc_36kg"]["value_kg"] == 36.0 and refs["A5_alloc_34kg"]["value_kg"] == 34.0
    a5 = json.loads((REPO / A5).read_text())
    alloc = [e for e in a5["allocations_and_requirements"] if e["quantity"] == "system mass design allocation"]
    assert alloc[0]["value"] == "<= 34-36 kg"
    assert "never as a prediction" in doc["reporting_rule"]


def test_no_total_frozen_and_parameters_tbd(doc):
    st = doc["ledger_state"]
    assert st["refused"] is True
    assert st["m_Xe_total_kg"] is None and st["m_Xe_subsystem_kg"] is None and st["m_tank_kg"] is None
    assert st["terms_kg"]["m_cathode"] == pytest.approx(5.4)
    assert set(st["missing"]) == set(TBD_FIELDS) and st["n_missing"] == len(TBD_FIELDS)
    params = {p["id"]: p for p in doc["parameters"]}
    assert set(params) == {"mdot_cathode", "t_firing"} | set(TBD_FIELDS)
    for pid in TBD_FIELDS:
        p = params[pid]
        assert p["status"].startswith("TBD — requires"), pid
        assert "value" not in p, pid
        assert p["closes_with"] and p["milestone"] in ("A", "B", "C")
    for pid in ("mdot_cathode", "t_firing"):
        p = params[pid]
        assert p["source"] and p["evidence_class"] in EVIDENCE
    assert doc["a5_basis"]["m_Xe_total_value"].startswith("PENDING_OWNER")
    a6 = json.loads((REPO / A6).read_text())
    assert [n["item"] for n in doc["a6_not_authorized_compliance"]] == a6["not_authorized"]


def _inputs_from_json(params: dict) -> dict:
    inp = {}
    for k, v in params.items():
        if "tbd" in v:
            inp[k] = xl.TBD(v["tbd"])
        elif "form" in v:
            inp[k] = {"form": v["form"], "value": xl.Quantity(v["value"], v["unit"], v["source"], v["evidence_class"])}
        else:
            inp[k] = xl.Quantity(v["value"], v["unit"], v["source"], v["evidence_class"])
    return inp


def test_scenarios_labelled_sourced_and_recomputed(doc):
    names = [s["name"] for s in doc["scenarios"]]
    assert names == ["cathode_only_minimum", "nominal_restart", "heavy_restart", "fallback_limited"]
    for s in doc["scenarios"]:
        assert "illustrative" in s["label"] and "not an allocation" in s["label"] and "not frozen" in s["label"]
        assert s["accounting_convention"] in xl.ACCOUNTING_CONVENTIONS
        for k, v in s["parameters"].items():
            if "tbd" in v:
                continue
            assert v["source"] and v["evidence_class"] in EVIDENCE, (s["id"], k)
        if s["id"] == "SC-3":
            continue
        inp = _inputs_from_json(s["parameters"])
        inp.update(architecture_scope=s["architecture_scope"], accounting_convention=s["accounting_convention"])
        ev = xl.evaluate(inp, level="xe_total")
        assert s["results"]["m_Xe_total_kg_scenario"] == pytest.approx(ev["m_Xe_total_kg"], rel=1e-5)
    sc0 = doc["scenarios"][0]
    assert sc0["results"]["m_Xe_total_kg_scenario"] == pytest.approx(5.4)


def test_heavy_restart_orbit_count(doc):
    from abep_sim.constants import MU_EARTH, R_EARTH
    t_h = 2 * math.pi * math.sqrt((R_EARTH + 180e3) ** 3 / MU_EARTH) / 3600.0
    sc2 = next(s for s in doc["scenarios"] if s["id"] == "SC-2")
    assert sc2["N_starts_derivation"]["N_starts"] == math.floor(26000.0 / t_h)
    assert sc2["parameters"]["N_starts"]["evidence_class"] == "model-derived"


def test_fallback_limited_rows_match_module(doc):
    sc3 = next(s for s in doc["scenarios"] if s["id"] == "SC-3")
    assert sc3["parameters"]["t_fallback_max"] == {"tbd": "solved for in this scenario"}
    base = _inputs_from_json(sc3["parameters"])
    base.update(architecture_scope=sc3["architecture_scope"], accounting_convention=sc3["accounting_convention"])
    for r in sc3["results"]["rows"]:
        inp = dict(base, tank_model={"form": "tankage_fraction", "value": Q(r["f_tank_axis"], "1")},
                   **{h: Q(0.0, "kg") for h in xl.HARDWARE_ITEMS})
        a = xl.max_allowance(inp, "t_fallback_max", r["cap_kg"])
        assert a["status"] == r["status"]
        if a["value"] is not None:
            assert r["t_fallback_max_allowable_h"] == pytest.approx(a["value"], rel=1e-5)


def test_surfaces_consistent(doc):
    ss = {s["id"]: s for s in doc["sensitivity_surfaces"]}
    assert set(ss) == {"SS-1", "SS-2", "SS-3", "SS-4", "SS-5"}
    refs = {r["id"]: r["value_kg"] for r in doc["mass_references"]}
    assert len(ss["SS-1"]["rows"]) == 3 * 3 * 3 * 3 * 3
    for r in ss["SS-1"]["rows"]:
        smax = (r["share"] * refs[r["reference"]] - r["m_hw_nontank_kg"]) / ((1 + r["f_tank"]) * (1 + r["f_reserve"]))
        assert r["S_max_kg"] == pytest.approx(smax, rel=1e-5, abs=1e-9)
        assert r["H_kg_at_0p10"] == pytest.approx(smax - 5.4, rel=1e-5, abs=1e-6)
    for r in ss["SS-2"]["rows"]:
        assert r["N_starts_max"] == math.floor(r["H_kg"] * 1000 / r["xe_per_cycle_g"] + 1e-9)
    for r in ss["SS-3"]["rows"]:
        assert r["t_fallback_max_h"] == pytest.approx(r["H_kg"] / (r["mdot_fallback_mg_s"] * 1e-6) / 3600, rel=1e-5)
    for s in ("SS-1", "SS-2", "SS-3", "SS-5"):
        assert "not evidence" in ss[s]["axes_label"]


# ------------------------------------------------------------------------------------------------ transcriptions
def test_analogue_transcriptions_match_base_evidence(doc):
    cat = json.loads(CATHINT.read_text())["parameters"]
    an = {a["id"]: a for a in doc["illustrative_analogues"]}
    for a in an.values():
        assert "never the allocation" in a["label"]
        for v in a["values"]:
            assert v["evidence_class"] in EVIDENCE and v["evidence_level"] in range(1, 8)
    for v in an["AN-01"]["values"] + an["AN-03"]["values"]:
        key = v["pointer"].split("parameters.")[1].split(".value")[0]
        assert v["value"] == cat[key]["value"], key
    h6 = an["AN-04"]["values"][0]
    assert h6["value"] == cat["jpl_h6_heater_starts_min"]["value"]
    assert "> 350 ignitions" in cat["hc1_ignition_keeper_voltage_V"]["validation_status"]
    assert "25,000 ignitions (title only, verify)" in DOSSIER.read_text()
    e09 = next(e for e in json.loads(HSUST.read_text())["entries"] if e["id"] == "E09")
    assert "10 mg/s Xe (anode) + 1 mg/s Xe (cathode)" in e09["ignition"]["statement"]
    assert [v["value"] for v in an["AN-02"]["values"]] == [10.0, 1.0]
    tank = an["AN-05"]
    assert tank["source"]["url"].startswith("https://") and tank["source"]["accessed"] == "2026-09-27"
    assert "OUT OF APPLICABILITY" in tank["reading"]


def test_module_is_pure_and_not_wired():
    src = (REPO / "abep_sim" / "xe_ledger.py").read_text()
    for banned in ("import os", "open(", "import archengine", "from abep_sim", "hall_map", "hall_ensemble"):
        assert banned not in src, banned
    for p in (REPO / "abep_sim").glob("*.py"):
        if p.name != "xe_ledger.py":
            assert "xe_ledger" not in p.read_text(), p.name
