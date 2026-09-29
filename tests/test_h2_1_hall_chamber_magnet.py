"""H2-1 Hall chamber + magnetic circuit preliminary sizing (docs/hardware/h2/h2_1_hall_chamber_magnet/).

- the committed JSON and markdown are exactly what the deterministic builder produces;
- the owner decisions are pinned by their immutable sha256;
- the required H2 structure is present (design parameters, interface demands, hard-incompatibility check, A7 blockers,
  M16 rows, H3/H4 inputs, milestones) with the declared vocabularies;
- headline numbers are recomputed here with independently written formulas;
- no performance source, screening candidate, 0-D Hall model or winner appears; missing inputs raise.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "hardware" / "h2" / "h2_1_hall_chamber_magnet"
DATA = DIR / "h2_1_hall_chamber_magnet_v1.json"
MD = DIR / "H2_1_HALL_CHAMBER_MAGNET.md"
BUILDER = DIR / "build_h2_1_hall_chamber_magnet.py"

ARCH_IDS = ["hall_only", "rf_hall", "ecr_hall"]
CLASS_WORDS = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
REPS = {"FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"}
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
ROLLUPS = {"architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
           "proposal-only documentation gap"}
DECISION_PINS = {
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json":
        "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json":
        "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json":
        "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
}
MU0 = 1.25663706127e-6
ME = 9.1093837139e-31
QE = 1.602176634e-19


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_h2_1", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def doc():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_committed_files_match_builder(builder):
    d = builder.build()
    assert DATA.read_text(encoding="utf-8") == builder.dump(d), "JSON stale: rerun the builder"
    assert MD.read_text(encoding="utf-8") == builder.render_md(d), "markdown stale: rerun the builder"


def test_decision_pins():
    for rel, pin in DECISION_PINS.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == pin


def test_pins_recorded_and_no_mutable_governance(doc):
    for k in ("A5", "A6", "A7"):
        assert doc["owner_decisions"][k]["sha256"] == DECISION_PINS[doc["owner_decisions"][k]["path"]]
    pinned = [v["path"] for v in doc["owner_decisions"].values()] + \
        [v["path"] for v in doc["repository_inputs"].values()]
    for p in pinned:
        assert (ROOT / p).exists(), p
        assert "docs/orchestration" not in p and "ledger" not in p and "runtime_state" not in p, p
    assert ".claude/worktrees" not in BUILDER.read_text(encoding="utf-8")


def test_architectures_and_no_winner(doc):
    assert doc["architectures"] == ARCH_IDS
    low = (DATA.read_text(encoding="utf-8") + MD.read_text(encoding="utf-8")).lower()
    for bad in ("winner is", "is selected as the architecture", "eliminated_within_tested_envelope",
                "conditional_baseline("):
        assert bad not in low
    assert "no winner" in low


def test_no_forbidden_performance_sources(doc):
    blob = json.dumps(doc["design_parameters"]) + json.dumps(doc["coil_design"]) + json.dumps(doc["channel"])
    for bad in ("plasma_devices", "sgb-screen", "screening_candidates", "hallthruster_bridge/bfield",
                "hallthruster_bridge/cases", "HallChannel"):
        assert bad not in blob, bad
    # no thrust / efficiency / discharge-current prediction field in the sizing output
    for key in ("thrust_mN_pred", "eta_", "I_d_pred", "T_pred"):
        assert key not in blob


def test_design_parameter_table(doc):
    ids = [p["id"] for p in doc["design_parameters"]]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"H21-\d\d", i) for i in ids)
    assert len(ids) >= 25
    for p in doc["design_parameters"]:
        for f in ("name", "value", "units", "basis", "source", "evidence_class", "status", "representativeness"):
            assert f in p, (p["id"], f)
        assert p["representativeness"] in REPS, p["id"]
        assert any(b in p["basis"] for b in BASES), p["id"]
        assert any(c in p["evidence_class"] for c in CLASS_WORDS), p["id"]
        assert p["status"].startswith(("PRELIMINARY", "PENDING", "TBD", "PROPOSED")), p["id"]
        if p["status"].startswith("PENDING"):
            assert "docs/" in p["status"]


def test_assumed_inputs_explicit(doc):
    for k, v in doc["assumed_inputs"].items():
        for f in ("value", "unit", "basis", "evidence_class", "status", "why"):
            assert f in v, (k, f)
        assert v["status"].startswith(("PROPOSED", "PRELIMINARY", "PENDING")), k


def test_required_sections(doc):
    for sec in ("interface_demands", "hard_incompatibility_check", "architecture_changing_blockers_touched",
                "m16_rows", "h3_procurement_inputs", "h4_test_inputs", "milestones", "magnetic_topology_options",
                "bz_target_envelope", "coil_design", "materials"):
        assert doc[sec], sec
    assert set(doc["milestones"]) == {"A", "B", "C"}
    assert doc["hard_incompatibility_check"]["verdict"] == "none found"
    assert len(doc["hard_incompatibility_check"]["checked"]) >= 5
    assert {b["blocker"] for b in doc["architecture_changing_blockers_touched"]} == {1, 2, 3}
    for d in doc["interface_demands"]:
        for f in ("from", "to", "quantity", "value", "units", "status"):
            assert f in d
    for m in doc["m16_rows"]:
        assert m["proposed_state"] in {"READY", "RUNNING", "BLOCKED", "VERIFIED"}
        if m["proposed_state"] == "BLOCKED":
            assert isinstance(m["blocking_item"], str) and m["blocking_item"]
            assert m["rollup_category"] in ROLLUPS
    a5 = json.loads((ROOT / "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json")
                    .read_text(encoding="utf-8"))
    subsystems = set(sum((a5["architecture"][k] for k in ("atmospheric_branch", "xe_branch", "propulsion", "support")),
                         []))
    for m in doc["m16_rows"]:
        assert m["subsystem"] in subsystems, m["subsystem"]
    assert sum(1 for t in doc["magnetic_topology_options"] if t["status"] == "PRELIMINARY CHOICE") == 1


def test_recompute_area_window(doc):
    ch = doc["channel"]
    P_lo, P_hi = 0.5 * 1300.0, 1350.0
    A_cp = [math.pi * P_lo / 1.2e6 * 1e4, math.pi * P_hi / 1.2e6 * 1e4]
    A_jd = [P_lo / 350.0 / 1500.0 * 1e4, P_hi / 180.0 / 1000.0 * 1e4]
    win = [max(A_cp[0], A_jd[0]), min(A_cp[1], A_jd[1])]
    assert ch["area_window_cm2"] == pytest.approx(win, rel=1e-3)
    # geometry corners: h = sqrt(A / (pi d/h))
    h_min = math.sqrt(win[0] * 1e-4 / (math.pi * 9.0)) * 1e3
    h_max = math.sqrt(win[1] * 1e-4 / (math.pi * 3.8)) * 1e3
    assert ch["h_mm"] == pytest.approx([h_min, h_max], rel=1e-3)
    assert ch["L_over_h_window"][0] >= 8.6 - 1e-9


def test_recompute_field_criterion(doc):
    def B(h, Te):
        v = math.sqrt(8 * QE * Te / (math.pi * ME))
        return ME * v / (QE * 0.1 * h) * 1e4
    # MaSMi p. 5: 213 G at h = 8 mm, T_e = 20 eV
    assert doc["bz_target_envelope"]["masmi_reproduction_G"] == pytest.approx(213.0, rel=0.01)
    h = doc["channel"]["h_mm"]
    tgt = doc["bz_target_envelope"]["target_peak_Br_G"]
    # full declared criterion bracket 10-30 eV (lower end at the widest channel, upper at the narrowest)
    assert tgt == pytest.approx([B(h[1] * 1e-3, 10.0), B(h[0] * 1e-3, 30.0)], rel=2e-3)
    assert doc["bz_target_envelope"]["capability_G"] == pytest.approx(1.5 * tgt[1], rel=2e-3)


def test_recompute_gap_mmf_and_coil(doc):
    c = doc["coil_design"]["cases"][1]  # RP-1, f_NI = 2
    assert c["gap_mm"] == pytest.approx(12.0 + 2 * 4.0 + 2 * 1.0)
    assert c["NI_gap_A"] == pytest.approx(c["B_gap_G"] * 1e-4 * c["gap_mm"] * 1e-3 / MU0, rel=2e-3)
    assert c["NI_total_A"] == pytest.approx(2.0 * (c["NI_gap_A"] + c["NI_core_A"]), rel=2e-3)
    # coil I^2 R with NBS copper: R200/R20 = 1 + 0.00393 * 180
    for k in ("inner", "outer"):
        ch = c["coils"][k]["chosen"]
        assert ch["R200_ohm"] / ch["R20_ohm"] == pytest.approx(1 + 0.00393 * 180, rel=2e-3)
        assert ch["P20_W"] == pytest.approx(ch["I_A"] ** 2 * ch["R20_ohm"], rel=5e-3)
        assert ch["N"] * ch["I_A"] == pytest.approx(c["coils"][k]["NI_A"], rel=2e-3)
    # working flux density = 0.7 x cited saturation
    assert c["B_work_inner_T"] == pytest.approx(0.7 * 2.30, rel=1e-3)
    assert c["B_work_iron_T"] == pytest.approx(0.7 * 2.15, rel=1e-3)


def test_central_cathode_constraint_reported(doc):
    cases = doc["coil_design"]["cases"]
    assert any(x["status"].startswith("INFEASIBLE") for x in cases), "small-d corner must expose the bore limit"
    dmin = doc["coil_design"]["min_d_mean_for_central_cathode_mm"]
    for v in dmin.values():
        assert v["bore_12mm"] is not None and v["bore_18mm"] >= v["bore_12mm"]


def test_materials_cited(doc):
    mats = doc["materials"]["candidates"]
    assert mats["Hiperco_50"]["curie_C"][0] == 938.0 and "SRC-HIPERCO50" in mats["Hiperco_50"]["curie_C"][1]
    assert mats["ARMCO_pure_iron"]["B_sat_T"][0] == 2.15 and "SRC-ARMCO" in mats["ARMCO_pure_iron"]["B_sat_T"][1]
    assert "verify" in mats["ARMCO_pure_iron"]["curie_C"][1]
    for sid, s in doc["sources"].items():
        assert s["url"].startswith("https://"), sid
        assert s["sha256"] is None or re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), sid
    assert "ABSTRACT ONLY" in doc["sources"]["SRC-MIKELLIDES2014"]["access"]


def test_missing_inputs_raise(builder):
    with pytest.raises(KeyError):
        builder.need({}, "absent")
    saved = builder.ASSUMED.pop("fill_factor")
    try:
        with pytest.raises(KeyError):
            builder.a("fill_factor")
    finally:
        builder.ASSUMED["fill_factor"] = saved


def test_copper_model_not_extrapolated(builder):
    from abep_sim import magnet_power as MP
    with pytest.raises(ValueError):
        MP.resistance_factor(MP.ANNEALED_COPPER_IACS, 250.0)
    assert builder.ASSUMED["coil_temperatures_C"]["value"][1] <= 200.0


def test_sourced_constants_read_from_repository(builder):
    I = builder.read_inputs()
    href = json.loads((ROOT / "docs/architecture_comparison/hall_reference/hall_reference_v1.json").read_text())
    rel = {r["id"]: r for r in href["geometry_interface"]["sizing_relations"]}
    assert I["C_P_star_W_m2"] == rel["EV-G6"]["stated_values"]["C_P_empirical_xenon"]["value"]
    assert I["n_crit_Xe_m3"] == rel["EV-G5"]["stated_values"]["critical_atom_density_xenon"]["value"]
    j = rel["EV-G7"]["stated_values"]["discharge_current_density_xenon"]["value"]
    assert I["j_d_A_m2"] == pytest.approx([1e4 * j[0], 1e4 * j[1]])
    assert I["P_alloc_W"] == [1300.0, 1350.0] and I["thrust_alloc_mN"] == [15.0, 22.0]
    assert I["mdot_A5_quote_kgps"] == pytest.approx(3.2e-6)
    with pytest.raises(RuntimeError):
        builder.parse_range("about 15 mN", "mN")


def test_kulgrid_hot_resistance_from_mcq(builder, doc):
    mcq = json.loads((ROOT / "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json").read_text())
    em03 = {c["id"]: c for c in mcq["candidates"]}["MCQ-EM-03"]["values"]
    r5, r10 = em03["resistance_500F"]["value"], em03["resistance_1000F"]["value"]
    iacs20 = 1.7241e-8 / ((math.pi / 4) * (0.001 * 0.0254) ** 2 / 0.3048)  # ohm-cmil/ft
    assert iacs20 == pytest.approx(10.371, rel=1e-3)
    for c in doc["coil_design"]["cases"][:3]:
        for k in ("inner", "outer"):
            ch = c["coils"][k]["chosen"]
            # R(1000 F) / R_IACS(20 C) = 42.3 / 10.371 (same wire, same turns)
            assert ch["R_kulgrid_538C_ohm"] / ch["R20_ohm"] == pytest.approx(r10 / iacs20, rel=2e-3)
            assert ch["R_kulgrid_260C_ohm"] / ch["R20_ohm"] == pytest.approx(r5 / iacs20, rel=2e-3)
            assert ch["P_kulgrid_538C_W"] == pytest.approx(ch["I_A"] ** 2 * ch["R_kulgrid_538C_ohm"], rel=5e-3)
    # the hall_magnet demand upper bound is the Kulgrid class-temperature value (not 200 C copper)
    dem = [d for d in doc["interface_demands"] if d["quantity"].startswith("hall_magnet load")][0]
    cases = doc["coil_design"]["cases"]
    assert dem["value"][1] == pytest.approx(max(cases[1]["P_coils_kulgrid_538C_W"], cases[2]["P_coils_kulgrid_538C_W"]),
                                            rel=1e-3)
    assert dem["value"][1] > max(cases[1]["P_coils_200C_W"], cases[2]["P_coils_200C_W"])
    from abep_sim import magnet_power as MP
    kul = builder.kulgrid_material(builder.read_inputs())
    with pytest.raises(ValueError):
        MP.resistance_factor(kul, 250.0)  # below 500 F: not extrapolated (MCQ-TL-04)


def test_supply_window_checked_at_both_ends(doc):
    flagged = []
    for c in doc["coil_design"]["cases"]:
        if "coils" not in c:
            continue
        for k in ("inner", "outer"):
            ch = c["coils"][k]["chosen"]
            ok = 1.0 <= ch["I_A"] <= 5.0 and ch["V20_V"] >= 1.0 and ch["V_max_V"] <= 12.0
            assert ch["in_supply_window"] == ok, (c["name"], k)
            assert ch["V_min_V"] == ch["V20_V"]
            assert ch["V_max_V"] >= ch["V_kulgrid_538C_V"] - 1e-12
            if not ok:
                assert "OUTSIDE" in ch["flag"]
                flagged.append(f"{c['name']} {k}")
    dem = [d for d in doc["interface_demands"] if d["quantity"].startswith("coils OUTSIDE")][0]
    assert dem["value"] == flagged


def test_inner_core_mechanical_minimum_and_cathode_heat(doc):
    for c in doc["coil_design"]["cases"]:
        assert c["inner_core_wall_mm"] >= 2.0 - 1e-9
        assert c["inner_core_bore_r_mm"] == pytest.approx(c["cathode_bore_d_mm"] / 2 + 2.0)
    qs = " ".join(d["quantity"] for d in doc["interface_demands"])
    assert "C-1 heat load into the inner core" in qs
    assert any(d["to"].startswith("docs/hardware/h2/h2_5_thermal_network/") and "C-1 bore" in d["quantity"]
               for d in doc["interface_demands"])
    assert any("trim coil" in d["quantity"] for d in doc["interface_demands"])


def test_thrust_targets_explicitly_not_an_area_bound(doc):
    tb = doc["channel"]["thrust_bound"]
    assert tb["applied_as_area_bound"] is False
    assert tb["thrust_rfp_mN"] == [12.0, 25.0] and tb["thrust_alloc_mN"] == [15.0, 22.0]
    assert "performance prediction" in tb["why_not"]
    assert "not applied as an area bound" in MD.read_text(encoding="utf-8")
