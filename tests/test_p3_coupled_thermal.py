"""Tests for the P3 coupled H-1 / downstream-ICP thermal framework (docs/experiments/hall_icp/p3_coupled_thermal/,
lane fo_a9_6_p3_coupled_thermal, trigger T_A9_6_P3_COUPLED_THERMAL; owner directive A9.6 sec. 10, A9.2).

Checks: byte-for-byte reproduction; pins; closed-form view factors (catalogue identities, reciprocity, domains);
ray-quadrature engine vs the closed forms, summation and reciprocity; open-frame fraction; radiosity and network
solvers against analytic cases; H2-5 reproduction by the coupling adapter with no ICP body; adapter refusals; the four
heat terms (formulas, refusals, units, synthetic/evidence mixing); plume interception; fail-closed evaluation of the
registered inputs; item / evidence discipline; no PASS anywhere; statuses UNRESOLVED; P1 / P2 ids referenced exist.
All numeric inputs here are SYNTHETIC_TEST_DATA_NOT_EVIDENCE.
Run: python -m pytest -q tests/test_p3_coupled_thermal.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p3_coupled_thermal"
BUILDER = LANE / "build_p3_coupled_thermal.py"
OUT_JSON = LANE / "p3_coupled_thermal_v1.json"
OUT_MD = LANE / "P3_COUPLED_THERMAL.md"
H25_PY = REPO / "docs" / "hardware" / "h2" / "h2_5_thermal_network" / "build_h2_5_thermal_network.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def mod():
    return _load("p3_builder_under_test", BUILDER)


@pytest.fixture(scope="module")
def L(mod):
    return mod.LIB


@pytest.fixture(scope="module")
def d():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def h25():
    return _load("h25_under_p3_test", H25_PY)


def S(L, v, u):
    return L.q(v, u, L.SYN, "test")


# ------------------------------------------------------------------------------------------------ reproduction / pins
def test_builder_reproduces_outputs(mod):
    assert mod.main(["--check"]) == 0


def test_pins_match_and_governance_not_pinned(mod, d):
    for rel, h, _ in list(mod.DECISIONS.values()) + list(mod.DELIVERABLES.values()):
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == h, rel
    pinned = {p["path"] for p in d["decision_pins"] + d["deliverable_pins"]}
    assert not pinned & set(mod.NEVER_PINNED)
    for p in mod.REFERENCED_NOT_PINNED.values():
        assert p not in pinned


def test_referenced_p1_p2_ids_exist(mod):
    p1 = (REPO / mod.REFERENCED_NOT_PINNED["P1"]).read_text(encoding="utf-8")
    p2 = (REPO / mod.REFERENCED_NOT_PINNED["P2"]).read_text(encoding="utf-8")
    for i in mod.P1_IDS:
        assert f'"{i}"' in p1, i
    for i in mod.P2_IDS:
        assert f'"{i}"' in p2, i


# ------------------------------------------------------------------------------------------------ closed forms
def test_closed_form_identities(L):
    for r, a in ((0.5, 0.6), (1.0, 3.0), (0.2, 0.05)):
        assert L.vf_disk_to_parallel_coaxial_disk_same_radius(r, a) == pytest.approx(
            L.vf_disk_to_parallel_coaxial_disk(r, r, a), abs=1e-12)
    for args in ((0.2, 0.5, 0.3, 0.8, 0.6), (1.0, 2.0, 1.5, 3.0, 0.8), (0.1, 0.9, 0.05, 0.2, 0.3)):
        assert L.vf_annulus_to_parallel_coaxial_annulus(*args) == pytest.approx(
            L.vf_annulus_to_annulus_by_disk_algebra(*args), abs=1e-12)
    for r1, r2, h in ((0.3, 0.4, 1.0), (1.0, 1.0, 0.5), (0.2, 0.9, 0.1)):
        assert L.vf_disk_in_base_to_cylinder_inside(r1, r2, h) == pytest.approx(
            1 - L.vf_disk_to_parallel_coaxial_disk(r1, r2, h), abs=1e-12)
    # C-81 with h2 = 0 equals C-80 (r1 = r2) by reciprocity: F_cyl->disk = (A_disk / A_cyl) F_disk->cyl
    for r, h in ((0.4, 0.5), (1.0, 3.0)):
        f80 = L.vf_disk_in_base_to_cylinder_inside(r, r, h)
        assert L.vf_cylinder_inside_to_coaxial_disk(r, h, 0.0) == pytest.approx(f80 * (r * r) / (2 * r * h),
                                                                                 abs=1e-12)


def test_closed_form_limits_and_domain(L):
    assert L.vf_disk_to_parallel_coaxial_disk(1.0, 1.0, 1e-6) == pytest.approx(1.0, abs=1e-5)
    assert L.vf_disk_to_parallel_coaxial_disk(1.0, 1.0, 1e4) == pytest.approx(1e-8, rel=1e-3)
    for f, args in ((L.vf_disk_to_parallel_coaxial_disk, (0, 1, 1)), (L.vf_annulus_to_parallel_coaxial_annulus,
                                                                      (0.5, 0.2, 0.3, 0.8, 1)),
                    (L.vf_cylinder_outer_to_end_annulus, (0.8, 0.3, 1)), (L.vf_disk_in_base_to_cylinder_inside,
                                                                          (0.5, 0.3, 1)),
                    (L.vf_cylinder_inside_to_coaxial_disk, (0.4, 0.0, 0.1))):
        with pytest.raises(L.DomainError):
            f(*args)


# ------------------------------------------------------------------------------------------------ engine
def test_engine_matches_catalogue(d, mod):
    cf = d["closed_form_verification"]
    assert cf["data_class"] == "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
    assert {c["entry"] for c in cf["cases"]} == {"C-40", "C-41", "C-52", "C-77", "C-80", "C-81"}
    assert all(c["abs_error"] <= cf["tolerance_abs"] for c in cf["cases"])


def test_engine_independent_geometry(L):
    B = L.Body
    vf = L.view_factors([B("A", 0.0, 0.03, -0.01, 0.0), B("B", 0.0, 0.07, 0.05, 0.06)], (16, 32, 64))
    assert vf["F"]["A.down"]["B.up"] == pytest.approx(L.vf_disk_to_parallel_coaxial_disk(0.03, 0.07, 0.05), abs=3e-3)
    for s in vf["surfaces"]:
        assert sum(vf["F"][s].values()) == pytest.approx(1.0, abs=1e-12)
    assert vf["reciprocity_max_rel"] < 0.05


def test_open_frame_fraction_halves_single_body(L):
    B = L.Body
    h = B("H", 0.0, 0.05, -0.1, 0.0)
    f0 = L.view_factors([h, B("I", 0.03, 0.06, 0.02, 0.1)], (8, 16, 32), emitters=["H.down"])["F"]["H.down"]
    f1 = L.view_factors([h, B("I", 0.03, 0.06, 0.02, 0.1, tau=0.5)], (8, 16, 32), emitters=["H.down"])["F"]["H.down"]
    tot0 = sum(v for k, v in f0.items() if k.startswith("I."))
    tot1 = sum(v for k, v in f1.items() if k.startswith("I."))
    assert tot1 == pytest.approx(0.5 * tot0, rel=1e-12)
    assert sum(f1.values()) == pytest.approx(1.0, abs=1e-12)


def test_geometry_refusals(L):
    B = L.Body
    with pytest.raises(L.GeometryError):
        B("X", 0.2, 0.1, 0, 1)
    with pytest.raises(L.GeometryError):
        B("X", 0.0, 0.1, 0, 1, down=[("a", 0.0, 0.05), ("b", 0.06, 0.1)])
    with pytest.raises(L.GeometryError):
        L.view_factors([B("A", 0, 0.1, 0, 1), B("B", 0.05, 0.2, 0.5, 2)], (2, 2, 2))
    with pytest.raises(L.GeometryError):
        B("X", 0.0, 0.1, 0, 1, tau=1.0)


# ------------------------------------------------------------------------------------------------ radiosity / network
def test_radiosity_parallel_plates_and_reradiating(L):
    F = {"a": {"a": 0.0, "b": 1.0, "SPACE": 0.0}, "b": {"a": 1.0, "b": 0.0, "SPACE": 0.0}}
    res = L.radiosity_solve(["a", "b"], {"a": 1.0, "b": 1.0}, F, {"a": 0.8, "b": 0.3}, {"a": 600.0, "b": 300.0}, 0.0)
    ref = L.SIGMA_SB * (600.0 ** 4 - 300.0 ** 4) / (1 / 0.8 + 1 / 0.3 - 1)
    assert res["q_W"]["a"] == pytest.approx(ref, rel=1e-12)
    assert res["q_W"]["a"] + res["q_W"]["b"] + 0.0 == pytest.approx(res["q_space_W"], abs=1e-9)
    F2 = {"a": {"a": 0.0, "r": 0.5, "SPACE": 0.5}, "r": {"a": 0.5, "r": 0.0, "SPACE": 0.5}}
    res2 = L.radiosity_solve(["a", "r"], {"a": 1.0, "r": 1.0}, F2, {"a": 0.9, "r": "RERADIATING"}, {"a": 500.0}, 0.0)
    assert res2["q_W"]["r"] == 0.0
    assert res2["q_W"]["a"] == pytest.approx(res2["q_space_W"], rel=1e-12)


def test_reciprocity_enforcement_conserves_energy(L):
    B = L.Body
    vf = L.view_factors([B("H", 0.0, 0.08, -0.1, 0.0), B("I", 0.05, 0.1, 0.03, 0.12)], (8, 16, 32))
    G, adj = L.enforce_reciprocity(vf["F"], vf["area_m2"], vf["surfaces"])
    eps = {s: 0.7 for s in vf["surfaces"]}
    T = {s: 300.0 + 10 * i for i, s in enumerate(vf["surfaces"])}
    res = L.radiosity_solve(vf["surfaces"], vf["area_m2"], G, eps, T, 50.0)
    assert sum(res["q_W"].values()) == pytest.approx(res["q_space_W"], rel=1e-9, abs=1e-9)


def test_network_analytic_and_refusals(L):
    net = L.Network(unknown=["n"], fixed={}, loads={"n": 100.0}, env_rad=[("n", 0.005, 0.0, 3.0)])
    assert L.solve_network(net)["T_K"]["n"] == pytest.approx((100.0 / (0.005 * L.SIGMA_SB) + 81.0) ** 0.25, rel=1e-9)
    with pytest.raises(L.NumericalFailure):
        L.solve_network(net, max_iter=1)
    bad = L.Network(unknown=["n"], fixed={"f": 300.0}, loads={"n": 1.0}, cond=[("n", "f", 1.0)],
                    env_rad=[("f", 0.01, 0.0, 3.0)])
    with pytest.raises(L.InputError):
        L.solve_network(bad)


def test_h25_reproduction_recorded(d):
    hr = d["h25_reproduction_check"]
    assert hr["max_abs_dT_K"] <= 1e-6
    assert {c["case"] for c in hr["cases"]} == {"ground", "orbit_hot", "orbit_cold"}
    assert "NOT reported" in hr["evaluation_point"]


def _h25_x(h25, case="ground"):
    pm = h25.param_map(h25.build_parameters())
    fx = h25.fixed_inputs(pm)
    x = {k: 0.5 * (a + b) for k, (a, b) in h25.ranges_for(case, pm).items()}
    return x, fx


def test_adapter_refuses_unmapped_surfaces(L, h25):
    x, fx = _h25_x(h25)
    icp = L.Body("ICP", 0.06, 0.08, 0.05, 0.15)
    with pytest.raises(L.MissingInputError):
        L.h25_coupled_network(h25, x, fx, "ground", "z93_white_inorganic", 1350.0, [icp], {}, {}, (4, 8, 16))
    smap = {s: "ICP" for s in icp.surface_ids()}
    with pytest.raises(L.MissingInputError):
        L.h25_coupled_network(h25, x, fx, "ground", "z93_white_inorganic", 1350.0, [icp], smap, {}, (4, 8, 16))


def test_adapter_hot_icp_heats_h1_and_closes_energy(L, h25):
    """SYNTHETIC: an ICP body held at a fixed temperature above the H-1 front must raise PO / PI (back-radiation);
    energy closure is enforced by solve_network."""
    x, fx = _h25_x(h25)
    net0, _ = L.h25_coupled_network(h25, x, fx, "ground", "z93_white_inorganic", 1350.0, [], {}, {}, (8, 16, 32))
    T0 = L.solve_network(net0, T0=450.0)["T_K"]
    icp = L.Body("ICP", 0.055, 0.09, 0.03, 0.13)
    smap = {s: "ICPFIX" for s in icp.surface_ids()}
    eps = {s: 0.9 for s in icp.surface_ids()}
    net1, info = L.h25_coupled_network(h25, x, fx, "ground", "z93_white_inorganic", 1350.0, [icp], smap, eps,
                                       (8, 16, 32), icp_fixed={"ICPFIX": 1000.0})
    T1 = L.solve_network(net1, T0=450.0)["T_K"]
    assert T1["PO"] > T0["PO"] and T1["PI"] > T0["PI"] and T1["AN"] > T0["AN"]
    assert sum(info["aperture_weights"].values()) == pytest.approx(1.0, abs=1e-12)


def test_equivalent_heat_sign(L):
    B = L.Body
    h = B("H", 0.0, 0.05, -0.1, 0.0, down=[("H.face", 0.0, 0.05)], outer=[("H.lat", -0.1, 0.0)],
          up=[("H.rear", 0.0, 0.05)])
    icp = B("I", 0.03, 0.07, 0.02, 0.1)
    res = (8, 16, 32)
    vw, vwo = L.view_factors([h, icp], res), L.view_factors([h], res)
    eps = {s: 0.8 for s in vw["surfaces"]}
    h1map = {"H.face": "N", "H.lat": "N", "H.rear": "N"}
    T_h1 = {"H.face": 600.0, "H.lat": 600.0, "H.rear": 600.0}
    hot = L.equivalent_heat_into_h1(vw, vwo, h1map, eps, T_h1, {s: 900.0 for s in icp.surface_ids()}, 3.0)
    assert hot["N"] > 0
    cold = L.equivalent_heat_into_h1(vw, vwo, h1map, eps, T_h1, {s: 3.0 for s in icp.surface_ids()}, 3.0)
    assert hot["N"] > cold["N"]
    ch = L.h1_view_change(vw, vwo, ["H.face"])
    assert ch["H.face"]["delta_F_space"] < 0
    assert ch["H.face"]["F_to_icp"] == pytest.approx(-ch["H.face"]["delta_F_space"], abs=1e-12)


# ------------------------------------------------------------------------------------------------ heat terms
def _rf(L, **over):
    base = {"P_forward_W": 300.0, "P_reflected_W": 20.0, "P_line_match_loss_W": 30.0,
            "f_line_match_loss_on_module": 0.6, "f_delivered_leaving_module": 0.1}
    base.update(over)
    return {k: S(L, v, L.Q_RF_SPEC[k]) for k, v in base.items()}


def test_q_rf_match_formula_and_refusals(L):
    r = L.q_rf_match(_rf(L))
    assert r["P_delivered_W"] == pytest.approx(250.0)
    assert r["Q_RF_match_W"] == pytest.approx(0.6 * 30.0 + 0.9 * 250.0)
    assert r["provenance"]["basis"] == "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
    assert r["status"] == "COMPUTED_CONDITIONAL"
    with pytest.raises(L.InputError):
        L.q_rf_match(_rf(L, P_reflected_W=400.0))
    with pytest.raises(L.InputError):
        L.q_rf_match(_rf(L, P_line_match_loss_W=290.0))
    with pytest.raises(L.DomainError):
        L.q_rf_match(_rf(L, f_delivered_leaving_module=1.2))
    rec = _rf(L)
    rec["P_forward_W"] = L.q(300.0, "kW", L.SYN, "t")
    with pytest.raises(L.InputError):
        L.q_rf_match(rec)
    rec = _rf(L)
    rec["P_forward_W"] = L.q(300.0, "W", "measured", "t")
    with pytest.raises(L.SyntheticMixError):
        L.q_rf_match(rec)
    rec = _rf(L)
    rec["P_line_match_loss_W"] = L.q("TBD_AFTER_IMPEDANCE_MAP", "W", None, "t")
    with pytest.raises(L.MissingInputError) as e:
        L.q_rf_match(rec)
    assert e.value.missing == ["P_line_match_loss_W"]
    rec = _rf(L)
    rec["I_antenna_rms_A"] = S(L, 5.0, "A")
    rec["R_antenna_cold_ohm"] = S(L, 0.4, "ohm")
    out = L.q_rf_match(rec)
    assert out["Q_antenna_ohmic_W"] == pytest.approx(10.0)
    assert out["antenna_ohmic_consistency"] == "CONSISTENT"


def _coll(L, **over):
    base = {"I_electron_collected_A": 2.0, "I_ion_collected_A": 3.0, "T_e_eV": 4.0, "V_plasma_V": 20.0,
            "V_surface_V": -80.0}
    base.update(over)
    rec = {k: S(L, v, L.Q_COLL_SPEC[k]) for k, v in base.items()}
    rec["surface_energy_terms"] = {"value": "EXCLUDED", "source": "test"}
    return rec


def test_q_collector_formula_and_switch(L):
    r = L.q_collector(_coll(L))
    # retarding for electrons (V_s < V_p): 2 Te; ion: Te/2 + (V_p - V_s)
    assert r["eps_electron_eV"] == pytest.approx(8.0)
    assert r["eps_ion_eV"] == pytest.approx(2.0 + 100.0)
    assert r["Q_collector_W"] == pytest.approx(2.0 * 8.0 + 3.0 * 102.0)
    acc = L.q_collector(_coll(L, V_surface_V=30.0))
    assert acc["eps_electron_eV"] == pytest.approx(8.0 + 10.0) and acc["eps_ion_eV"] == pytest.approx(2.0)
    rec = _coll(L)
    del rec["surface_energy_terms"]
    with pytest.raises(L.MissingInputError):
        L.q_collector(rec)
    rec = _coll(L)
    rec["surface_energy_terms"] = {"value": "INCLUDED", "source": "test"}
    with pytest.raises(L.MissingInputError):
        L.q_collector(rec)
    rec["phi_wf_eV"] = S(L, 4.5, "eV")
    rec["E_iz_eV"] = S(L, 15.6, "eV")
    out = L.q_collector(rec)
    assert out["terms_W"]["ion_neutralization_W"] == pytest.approx(3.0 * (15.6 - 4.5))
    assert "verify" in out["surface_terms_note"]
    with pytest.raises(L.InputError):
        L.q_collector(_coll(L, I_ion_collected_A=-1.0))
    with pytest.raises(L.DomainError):
        L.q_collector(_coll(L, T_e_eV=0.0))


def test_plume_interception_and_q_plume(L, mod):
    B = L.Body
    h = B("H", 0.0, 0.08, -0.1, 0.0, down=[("H.c", 0.0, 0.04), ("H.ap", 0.04, 0.05), ("H.o", 0.05, 0.08)])
    icp = B("I", 0.05, 0.08, 0.03, 0.15)
    f = L.plume_interception([h, icp], h, "H.ap", mod.uniform_cone_cdf(40.0), (8, 16, 32))
    assert sum(f.values()) == pytest.approx(1.0, abs=1e-12)
    narrow = L.plume_interception([h, icp], h, "H.ap", [(0.0, 0.0), (1e-3, 1.0)], (8, 16, 32))
    assert narrow["SPACE"] == pytest.approx(1.0, abs=1e-12)  # axial pencil passes the aperture
    rec = {"I_beam_A": S(L, 3.0, "A"), "E_ion_mean_eV": S(L, 200.0, "eV"),
           "alpha_energy_accommodation": S(L, 1.0, "-")}
    q = L.q_plume(rec, f)
    assert q["Q_plume_W"] == pytest.approx(600.0 * (1.0 - f["SPACE"]), rel=1e-12)
    for bad in ([(0.0, 0.0), (30.0, 0.9)], [(5.0, 0.0), (30.0, 1.0)], [(0.0, 0.0), (100.0, 1.0)]):
        with pytest.raises(L.DomainError):
            L.plume_directions(bad, 4, 4)
    with pytest.raises(L.GeometryError):
        L.plume_interception([h, icp], h, "H.nope", mod.uniform_cone_cdf(20.0), (4, 4, 4))


def test_take_rejects_bad_records(L):
    with pytest.raises(L.InputError):
        L.take({"a": L.q(True, "W", L.SYN, "t")}, {"a": "W"}, "x")
    with pytest.raises(L.InputError):
        L.take({"a": L.q(float("nan"), "W", L.SYN, "t")}, {"a": "W"}, "x")
    with pytest.raises(L.InputError):
        L.take({"a": L.q(1.0, "W", "guess", "t")}, {"a": "W"}, "x")
    with pytest.raises(L.InputError):
        L.take({"a": L.q(1.0, "W", "measured", "")}, {"a": "W"}, "x")
    v, p = L.take({"a": L.q(1.0, "W", "measured", "t"), "b": L.q(2.0, "W", "assumed", "t")},
                  {"a": "W", "b": "W"}, "x")
    assert p["basis"] == "CONDITIONAL_ON_NON_MEASURED_INPUTS" and p["conditional_on"] == ["b"]


# ------------------------------------------------------------------------------------------------ deliverable discipline
def test_fail_closed_on_registered_inputs(d):
    fc = d["fail_closed_evaluations"]
    for k in ("Q_RF/match", "Q_collector", "Q_plume", "Q_Hall->ICP", "coupled_network"):
        assert fc[k]["status"] == "INCOMPLETE_EVIDENCE" and fc[k]["missing"]


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def test_no_pass_anywhere_and_statuses(d, L):
    assert "PASS" not in L.RESULT_STATUSES
    for k, v in _walk(d):
        if isinstance(v, str) and ("status" in str(k).lower() or str(k) in ("ICP_COUPLED_THERMAL",
                                                                         "ANODE_THERMAL_CLOSURE")):
            assert "PASS" not in v.upper().split("_") and v.upper() != "PASS", (k, v)
    assert d["closure_statuses"]["ICP_COUPLED_THERMAL"] == "UNRESOLVED"
    assert d["closure_statuses"]["ANODE_THERMAL_CLOSURE"] == "UNRESOLVED"
    a92 = json.loads((REPO / "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json").read_text())
    assert d["a9_2_statuses_carried"] == a92["decisions"]["a9_10_statuses"]
    ps = d["radiative_view_parametric_study"]
    assert ps["label"] == "PARAMETRIC_STUDY_NOT_A_DESIGN" and ps["status"] == "COMPUTED_CONDITIONAL"
    assert ps["plume_geometric_interception"]["label"] == "GEOMETRIC_TEST_DISTRIBUTION_NOT_A_PLUME_PREDICTION"


def test_items_discipline(d, mod):
    ids = [i["id"] for i in d["items"]]
    assert len(ids) == len(set(ids))
    for it in d["items"]:
        for k in ("id", "name", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point",
                  "supplier", "used_by"):
            assert k in it
        assert it["freeze_point"] in mod.FREEZE_POINTS and it["status"] in mod.ITEM_STATUSES
        assert it["source"]
        if it["status"].startswith("TBD") or it["status"] == "PENDING":
            assert it["evidence_class"] is None and str(it["value"]).startswith(("TBD", "PENDING"))
    need = {"P1": {"P3-P1-01", "P3-P1-02", "P3-P1-03"}, "P2": {"P3-P2-01", "P3-P2-02", "P3-P2-03", "P3-P2-06"},
            "hardware": {"P3-G-01", "P3-G-02", "P3-K-01", "P3-R-02"}}
    by = {s: {i for i, _ in lst} for s, lst in d["inputs_by_supplier"].items()}
    for s, must in need.items():
        assert must <= by[s], s
    # ICPQ-10 alternatives carried side by side, neither chosen
    alts = {i["id"]: i for i in d["items"] if i["id"] in ("P3-B-01", "P3-B-02")}
    assert all(a["status"] == "TBD_OWNER" for a in alts.values())


def test_owner_questions(d):
    oq3 = json.loads((REPO / "docs/budgets/owner_decisions/owner_questions_state_v3.json").read_text())
    known = {r["id"] for r in oq3["rows"]}
    for q in d["open_owner_questions"]:
        assert q["id"] not in known and q["status"] == "TBD_OWNER" and len(q["alternatives"]) >= 2
    for qid, v in d["existing_open_owner_questions_carried"].items():
        assert v["status"] == "OPEN"
    for sec in ("interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
                "m16_impact"):
        assert d[sec]
    for h in d["historical_reuse"]:
        assert hashlib.sha256((REPO / h["path"]).read_bytes()).hexdigest() == h["sha256"]
    for m in d["m16_impact"]:
        assert "VERIFIED" not in m["proposed_change"]


def test_lane_hygiene():
    for p in list(LANE.glob("*.py")) + [Path(__file__)]:
        t = p.read_text(encoding="utf-8")
        assert "xe_" + "ledger" not in t
    for p in LANE.glob("*.py"):
        t = p.read_text(encoding="utf-8")
        for forbidden in ("archengine", "plasma_devices", "hall_map", "hall_ensemble"):
            assert f"import {forbidden}" not in t and f"from abep_sim.{forbidden}" not in t
    md = OUT_MD.read_text(encoding="utf-8")
    assert md.startswith("# P3 coupled H-1 / downstream-ICP thermal framework")
