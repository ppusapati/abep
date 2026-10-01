"""A9.7 F4 plenum / feed synthesis: module physics (F1 law, F2 coupling, DragCompressor mirror, Reservoir cross-check,
fail-closed domain gates, vectorized == scalar, transient integrator, Jacobian, orbit check) and the committed study
(structure, labels, pins, reproduction of committed samples). Fast (< 30 s): the full builder is NOT run here
(minutes of CPU); `python docs/design_synthesis/f4_plenum/build_f4_plenum.py --check` reproduces it."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from abep_sim.design import filter_stage as fs
from abep_sim.design import plenum_feed as pf
from abep_sim.reservoir import size_orifice_for_pressure

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design_synthesis/f4_plenum"
BUILDER = OUT / "build_f4_plenum.py"
JSON_MAIN = OUT / "f4_plenum_feed_v1.json"
JSON_CHAINS = OUT / "f4_plenum_chains_v1.json"
JSON_TRANS = OUT / "f4_plenum_transients_v1.json"
MD = OUT / "F4_PLENUM_FEED.md"
MODULE = ROOT / "abep_sim/design/plenum_feed.py"
STATES = ("h200_f150", "h180_f70", "h180_f230", "h230_f70", "h230_f230")


@pytest.fixture(scope="module")
def f1():
    return pf.load_f1(ROOT)


@pytest.fixture(scope="module")
def grid():
    d3 = json.loads((ROOT / "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json").read_text())
    return {x["id"]: x for x in d3["design_grid"]}


@pytest.fixture(scope="module")
def recs(f1):
    r = pf.load_f1_records(f1, [0.25, 0.5], scenarios=["cll_a0.8", "maxwell_a1"])
    return {(x.candidate, x.scenario, x.state): x for x in r}


@pytest.fixture(scope="module")
def main_doc():
    return json.loads(JSON_MAIN.read_text(encoding="utf-8"))


def _plant(grid, i="T6-A1-U2-D0-Ti6Al4V"):
    return pf.CompressorPlant.from_design(grid[i])


def _pl(V=1e-2, gamma=0.0, wall="WALL-G0"):
    return pf.Plenum(V, gamma, wall, pf.RES_DEFAULTS["leak_area_m2"])


# ------------------------------------------------------------------------------------------------- registry
def test_parameter_registry_fields_and_tbd():
    reg = pf.parameter_registry()
    assert len({p["id"] for p in reg}) == len(reg)
    for p in reg:
        for k in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
            assert k in p, (p["id"], k)
        if p["evidence_class"] == "TBD":
            assert p["value"] == "TBD" and "TBD" in p["status"]
    tbd = {p["id"] for p in reg if p["value"] == "TBD"}
    assert {"F4-P-05", "F4-P-06", "F4-P-08", "F4-P-09", "F4-P-10", "F4-P-11"} <= tbd


def test_strict_mode_refuses(recs, grid):
    ch = pf.Chain(recs[("A0.25_Ld20_phi0.8", "cll_a0.8", "h200_f150")], pf.filter_none(), _plant(grid), _pl())
    r = pf.evaluate(ch, 0.02, mode=pf.MODE_STRICT)
    assert r["status"] == pf.ST_NOT_EVALUATED and r["offered"] is None and len(r["blockers"]) >= 5
    r2 = pf.evaluate(ch, 0.02)
    assert r2["label"] == pf.LABEL_PARAMETRIC


# ------------------------------------------------------------------------------------------------- F1 / F2
def test_f1_escape_probability_is_phi_kback(recs):
    for (cand, sc, st), it in recs.items():
        phi = float(cand.split("phi")[1])
        a = it.escape_probability()
        for s in pf.SPECIES:
            assert a[s] == pytest.approx(phi * it.K_back[s], rel=2e-3)
            assert 0.0 < a[s] <= 1.0


def test_filter_none_reproduces_f1_law(recs):
    it = recs[("A0.5_Ld10_phi0.9", "maxwell_a1", "h200_f150")]
    fc = pf.filter_none()
    D, E = fc.coefficients(it.escape_probability())
    side = pf.intake_side([it], fc)
    for s in pf.SPECIES:
        assert D[s] == 1.0
        assert E[s] == pytest.approx(-it.escape_probability()[s], rel=1e-14)
        # with no compressor draw the node sits at the F1 passive pressure
        assert side["f"][s][0] / side["e"][s][0] == pytest.approx(it.p_passive_Pa[s], rel=1e-12)


def test_filter_cases_labels_and_refusal():
    cases = pf.filter_cases()
    assert cases[0].case_id == "F4-FIL-NONE" and cases[0].label == fs.LABEL_NORMALIZED
    for c in cases[1:]:
        assert c.label == fs.LABEL_SENSITIVITY and c.overrides
    with pytest.raises(fs.FilterStageError):
        pf.filter_case_from_stage("x", fs.FilterStage.tbd("X", "FC-X"), None)


def test_filter_reduces_delivery_and_raises_no_mass(recs):
    it = recs[("A0.5_Ld10_phi0.9", "maxwell_a1", "h200_f150")]
    a = it.escape_probability()
    for tau in (0.9, 0.5):
        D, E = pf.filter_parametric(tau).coefficients(a)
        for s in pf.SPECIES:
            assert 0.0 < D[s] < 1.0 and -1.0 <= E[s] < 0.0


# ------------------------------------------------------------------------------------------------- compressor
@pytest.mark.parametrize("did", ["T1-A0-U2-D0-Ti6Al4V", "T4-A1-U1-D0-Ti6Al4V", "T6-A2-U0-D0-Ti6Al4V",
                                 "T3-A1-U2-D2-Ti6Al4V"])
def test_cascade_mirror_matches_run_once(grid, did):
    pc = pf.CompressorPlant.from_design(grid[did])
    md = {"O": 3.0e-7, "N2": 5.0e-7, "O2": 0.4e-7}
    p_in = 0.004
    r = pc.comp._run_once(p_in, dict(md))
    nflow = {s: md[s] / pf.M_SPECIES[s] for s in pf.SPECIES}
    p_conv = {s: p_in * nflow[s] / sum(nflow.values()) for s in pf.SPECIES}
    Q = {s: nflow[s] * pf.K_B * pc.comp.T_gas_K for s in pf.SPECIES}
    c = pc.cascade(p_conv, Q)
    if c["K_min"] >= 1.0 and c["K_over_K0_max"] <= 1.0:          # module clips outside; mirror valid inside
        assert c["p_out_total"] == pytest.approx(r["p_out_Pa"], rel=1e-12)
        assert c["P_el_W"] == pytest.approx(r["P_el_W"], rel=1e-12)
        assert c["mass_kg"] == pytest.approx(r["mass_kg"], rel=1e-12)
        assert c["T_comp_K"] == pytest.approx(r["T_comp_K"], rel=1e-12)
    ca = pf.cascade_arrays(pc, {s: np.array([p_conv[s]]) for s in pf.SPECIES},
                           {s: np.array([Q[s]]) for s in pf.SPECIES})
    for k in ("P_el_W", "mass_kg", "T_comp_K", "K_min", "K_over_K0_max", "p_stage_max"):
        assert float(ca[k][0]) == pytest.approx(c[k], rel=1e-12)


def test_characteristic_inverts_the_cascade(grid):
    pc = _plant(grid)
    ch = pc.characteristic()
    p_in = {"O": 0.002, "N2": 0.0018, "O2": 0.0001}
    p_out = {"O": 0.01, "N2": 0.011, "O2": 0.0007}
    Q = {s: (ch[s][0] * p_in[s] - p_out[s]) / ch[s][1] for s in pf.SPECIES}
    c = pc.cascade(p_in, Q)
    for s in pf.SPECIES:
        assert c["p_out"][s] == pytest.approx(p_out[s], rel=1e-10)


# ------------------------------------------------------------------------------------------------- steady
def test_steady_point_conservation_and_reservoir_crosscheck(recs, grid):
    from abep_sim.materials import DB
    pl = _pl(gamma=DB["Ti6Al4V"].gamma_O(350.0), wall="WALL-TI64-DB")
    ch = pf.Chain(recs[("A0.5_Ld10_phi0.9", "maxwell_a1", "h200_f150")], pf.filter_none(), _plant(grid), pl)
    op = pf.steady_operating_point(ch, 0.01)
    assert op["status"] == pf.ST_FEASIBLE, op["reasons"]
    for v in op["conservation_residual_rel"].values():
        assert v < 1e-12
    assert op["offered"]["P_Pa"] == pytest.approx(0.01, rel=1e-10)
    assert op["mdot_recombined_O_kgps"] > 0.0
    mdot_in = {s: op["mdot_compressor_gross_kgps"][s] - op["mdot_compressor_backleak_kgps"][s] for s in pf.SPECIES}
    rs = pl.reservoir(op["a_eq_m2"]).steady_state(mdot_in)
    assert rs["p_total_Pa"] == pytest.approx(0.01, rel=1e-6)
    for s in pf.SPECIES:
        assert rs["mdot_anode"][s] == pytest.approx(op["offered"]["mdot_s_kgps"][s], rel=1e-6)
    a2 = size_orifice_for_pressure(pl.reservoir(1e-6), mdot_in, 0.01)
    assert a2 == pytest.approx(op["a_eq_m2"], rel=1e-6)
    # coupled inlet below the F1 passive pressure (net flow > 0)
    for s in pf.SPECIES:
        assert op["compressor_inlet_p_s_Pa"][s] < ch.intake.p_passive_Pa[s]


def test_target_above_domain_is_ood_without_flow(recs, grid):
    ch = pf.Chain(recs[("A0.5_Ld10_phi0.9", "maxwell_a1", "h200_f150")], pf.filter_none(), _plant(grid), _pl())
    for P in (0.1000001, 0.2, 10.0):
        op = pf.steady_operating_point(ch, P)
        assert op["status"] == pf.ST_OOD and op["offered"] is None
        assert pf.R_TARGET_ABOVE_DOMAIN in op["reasons"]


def test_characteristic_violation_is_ood_without_flow(recs, grid):
    ch = pf.Chain(recs[("A0.5_Ld3_phi0.9", "maxwell_a1", "h180_f230")], pf.filter_none(), _plant(grid), _pl())
    op = pf.steady_operating_point(ch, 0.001)
    assert op["status"] == pf.ST_OOD and op["offered"] is None
    assert pf.R_CHARACTERISTIC in op["reasons"] and op["domain_diagnostics"]["compressor_K_min"] < 1.0


def test_deadhead_is_infeasible(recs, grid):
    ch = pf.Chain(recs[("A0.5_Ld3_phi0.9", "maxwell_a1", "h230_f70")], pf.filter_none(),
                  _plant(grid, "T1-A0-U2-D0-Ti6Al4V"), _pl())
    op = pf.steady_operating_point(ch, 0.05)
    assert op["status"] == pf.ST_INFEASIBLE and pf.R_DEADHEAD in op["reasons"] and op["offered"] is None
    assert op["p_deadhead_Pa"] < 0.05


def test_vectorized_sweep_matches_scalar(recs, grid):
    its = [recs[(c, sc, s)] for c in ("A0.25_Ld20_phi0.8", "A0.5_Ld3_phi0.9") for sc in ("cll_a0.8", "maxwell_a1")
           for s in STATES]
    targets = (0.001, 0.005, 0.02, 0.05, 0.1, 0.2)
    for fc in (pf.filter_none(), pf.filter_parametric(0.7)):
        pc, pl = _plant(grid), _pl()
        sw = pf.steady_sweep(pf.intake_side(its, fc), pc, pl, targets,
                             np.array([i.f1_status == "FEASIBLE_AT_STATE" for i in its]))
        for j, it in enumerate(its):
            for k, P in enumerate(targets):
                op = pf.steady_operating_point(pf.Chain(it, fc, pc, pl), P)
                assert sorted(pf.reasons_from_bits(sw["bits"][j, k])) == sorted(op["reasons"])
                if op["offered"] is not None:
                    assert sw["mdot_total_kgps"][j, k] == pytest.approx(op["offered"]["mdot_total_kgps"], rel=1e-9)
                elif not np.isnan(sw["mdot_total_kgps"][j, k]):
                    assert op["status"] == pf.ST_INFEASIBLE      # in domain but infeasible (e.g. F1 upstream)


def test_status_precedence():
    assert pf.status_from_reasons([]) == pf.ST_FEASIBLE
    assert pf.status_from_reasons([pf.R_FLOW, pf.R_CHARACTERISTIC]) == pf.ST_OOD
    assert pf.status_from_reasons([pf.R_CHARACTERISTIC, pf.R_CONSERVATION]) == pf.ST_MODEL_ERROR
    assert pf.status_from_reasons([pf.R_SATURATED]) == pf.ST_INFEASIBLE
    for st in (pf.ST_FEASIBLE, pf.ST_INFEASIBLE, pf.ST_OOD, pf.ST_MODEL_ERROR, pf.ST_NOT_EVALUATED):
        assert not any(w in st.split("_") for w in pf.FORBIDDEN_STATUS_WORDS)


# ------------------------------------------------------------------------------------------------- transient
def test_jacobian_matches_finite_differences(recs, grid):
    it = recs[("A0.25_Ld20_phi0.8", "cll_a0.8", "h200_f150")]
    from abep_sim.materials import DB
    pl = _pl(V=1e-3, gamma=DB["Ti6Al4V"].gamma_O(350.0), wall="WALL-TI64-DB")
    tr = pf.TransientRun(pf.filter_none(), _plant(grid), pl, pf.Controller(1.0, 0.3, 1.0, 3.0), it, 0.02)
    ev = pf.Event("e", "orbit", 100.0, 0.021, 0.9, it, 0.1, 5000.0)
    rhs, jac = tr._make(ev)
    y = np.array([x * 1.03 for x in tr.p_init]) / tr.r0
    y = np.concatenate([y, [0.35, 0.2, 0.0, 0.0, 0.0]])
    J = jac(3.0, y)
    for j in range(8):
        h = 1e-7 * max(abs(y[j]), 1.0)
        yp, ym = y.copy(), y.copy()
        yp[j] += h
        ym[j] -= h
        col = (np.array(rhs(3.0, yp)) - np.array(rhs(3.0, ym))) / (2 * h)
        assert np.allclose(J[:, j], col, rtol=1e-5, atol=1e-6 * (np.abs(col).max() + 1e-30)), j


def test_transient_case_conserves_mass_and_settles(recs, grid):
    it = recs[("A0.25_Ld20_phi0.8", "cll_a0.8", "h200_f150")]
    r = pf.transient_case(pf.filter_none(), _plant(grid), _pl(V=1e-3), pf.Controller(3.0, 0.3, 1.0, 3.0), it, 0.02)
    assert r["summary"]["mass_residual_rel"] < pf.MASS_TOL
    m = {x["event"]: x for x in r["metrics"]}
    assert m["E0_hold"]["settling_time_s"] == 0.0                    # starts at its own steady state
    assert m["E1_setpoint_up"]["P_final_Pa"] == pytest.approx(0.022, rel=2 * pf.SETTLE_BAND)
    assert m["E3_feed_path_step"]["peak_deviation_frac"] > 0.0
    assert set(r["objectives"]) == set(pf.OBJECTIVES)
    if r["status"] == pf.ST_FEASIBLE:
        assert r["objectives"]["settling_max_s"] is not None


def test_orbit_quasi_static_matches_transient(recs, grid):
    it = recs[("A0.25_Ld20_phi0.8", "cll_a0.8", "h200_f150")]
    pc, pl = _plant(grid), _pl()
    co = pf.Chain(it, pf.filter_none(), pc, pl).node_coefficients()
    a, _, _, ok = pf.area_for_pressure(co, 0.02, 0.0, {s: pl.leak_m3_s(s) for s in pf.SPECIES},
                                       {s: pl.feed_c(s) for s in pf.SPECIES})
    assert bool(ok)
    oc = pf.orbit_quasi_static(pf.filter_none(), pc, pl, [it], 0.02, 0.1, 3.0 * float(a))
    row = oc["rows"][0]
    assert not row["reasons"]
    sim = pf.orbit_simulated(pf.filter_none(), pc, pl, pf.Controller(3.0, 0.3, 1.0, 3.0), it, it, 0.02, 0.1)
    assert sim["ok"] and sim["P_dev_max_frac"] < 1e-3
    assert sim["mdot_min_kgps"] == pytest.approx(row["mdot_min_kgps"], rel=1e-3)
    assert sim["mdot_max_kgps"] == pytest.approx(row["mdot_max_kgps"], rel=1e-3)


def test_settling_time_and_pareto_helpers():
    t = np.linspace(0, 10, 11)
    y = np.array([0, 5, 9, 10.5, 10.1, 10.0, 10, 10, 10, 10, 10.0])
    assert pf.settling_time(t, y, 10.0) == 4.0
    assert pf.settling_time(t, np.r_[y[:-1], 12.0], 10.0) is None
    rows = [{"id": "a", "status": pf.ST_FEASIBLE, "objectives": {"x": 1, "y": 2}},
            {"id": "b", "status": pf.ST_FEASIBLE, "objectives": {"x": 2, "y": 1}},
            {"id": "c", "status": pf.ST_FEASIBLE, "objectives": {"x": 2, "y": 2}},
            {"id": "d", "status": pf.ST_INFEASIBLE, "objectives": {"x": 0, "y": 0}}]
    assert pf.pareto_ids(rows, ("x", "y")) == ["a", "b"]


def test_wall_g0_steady_is_volume_independent(recs, grid):
    it = recs[("A0.25_Ld20_phi0.8", "cll_a0.8", "h200_f150")]
    a = pf.steady_operating_point(pf.Chain(it, pf.filter_none(), _plant(grid), _pl(V=1e-3)), 0.02)
    b = pf.steady_operating_point(pf.Chain(it, pf.filter_none(), _plant(grid), _pl(V=1e-1)), 0.02)
    assert a["offered"]["mdot_total_kgps"] == pytest.approx(b["offered"]["mdot_total_kgps"], rel=1e-12)


# ------------------------------------------------------------------------------------------------- committed study
def test_committed_study_structure_and_labels(main_doc):
    d = main_doc
    assert d["schema"] == pf.SCHEMA and d["status"] == "INVESTIGATION_HYPOTHESIS"
    assert d["deliverable_status"].startswith("PARAMETRIC_SENSITIVITY")
    assert d["strict_mode"]["status"] == pf.ST_NOT_EVALUATED
    for k in ("items", "interface_demands", "open_owner_questions", "m16_impact", "findings", "requirement_sweep",
              "metric_definitions", "pareto", "offered_to_h1", "steady", "transient", "checks"):
        assert d[k], k
    for p in d["items"]:
        for k in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
            assert k in p
    dirs = " ".join(x["direction"] for x in d["interface_demands"])
    assert "F4 -> F5" in dirs and "F5 -> F4" in dirs and "F3 -> F4" in dirs and "F4 -> F3" in dirs
    assert all(m["state_after"] == m["state_before"] for m in d["m16_impact"])
    assert all(v is False for k, v in d["compliance"].items() if k not in ("deterministic", "new_pytest_skips"))
    assert d["compliance"]["new_pytest_skips"] == 0
    text = JSON_MAIN.read_text(encoding="utf-8")
    for w in ('"PASS"', '"WINNER"', '"SELECTED"', '"OPTIMUM"'):
        assert w not in text


def test_committed_domain_cap_and_requirement_sweep(main_doc):
    for key, v in main_doc["steady"]["feasibility_regions"].items():
        for sc, rows in v["per_scenario"].items():
            for x in rows:
                if x["P_req_Pa"] > pf.P_DOMAIN_PA:
                    assert x["frontier_mdot_mgps"] is None and x["n_chains_all_state_feasible"] == 0
                    assert x["scheduled_setpoint"]["frontier_mdot_mgps"] is None
                if x["frontier_mdot_mgps"] is not None and x["scheduled_setpoint"]["frontier_mdot_mgps"] is not None:
                    assert x["scheduled_setpoint"]["frontier_mdot_mgps"] >= x["frontier_mdot_mgps"] * (1 - 1e-7)
    rs = main_doc["requirement_sweep"]
    assert "PARAMETRIC" in rs["status"] and max(rs["P_req_Pa"]) > pf.P_DOMAIN_PA


def test_committed_pareto_members_feasible_and_offered(main_doc):
    rows = {r["id"]: r for r in json.loads(JSON_TRANS.read_text(encoding="utf-8"))["rows"]}
    for p in main_doc["pareto"]:
        for i in p["pareto_ids"]:
            assert rows[i]["by_orbit_amplitude"][str(p["orbit_amplitude"])]["status"] == pf.ST_FEASIBLE
    for o in main_doc["offered_to_h1"]:
        assert o["label"] == pf.LABEL_PARAMETRIC and o["P_Pa"] <= pf.P_DOMAIN_PA
        assert set(o["mdot_s_mgps"]) == set(pf.SPECIES) and abs(sum(o["x_s_flow_mole"].values()) - 1) < 1e-6
    for r in rows.values():
        if r["objectives"] is not None:
            assert r["summary"]["mass_residual_rel"] < pf.MASS_TOL
            for amp, x in r["by_orbit_amplitude"].items():
                assert (x["status"] == pf.ST_FEASIBLE) == (not x["reasons"])


def test_committed_transient_sample_reproduces(main_doc, f1, grid):
    """Recompute one committed simulated row from the module (the builder itself is checked with --check)."""
    rows = [r for r in json.loads(JSON_TRANS.read_text(encoding="utf-8"))["rows"] if r["objectives"] is not None]
    assert rows
    r = rows[0]
    recs = pf.load_f1_records(f1, [float(r["candidate"].split("_")[0][1:])], scenarios=[r["scenario"]],
                              states=["h200_f150"])
    it = [x for x in recs if x.candidate == r["candidate"]][0]
    c = r["controller"]
    x = pf.transient_case(pf.filter_none(), pf.CompressorPlant.from_design(grid[r["compressor"]]), _pl(V=r["V_m3"]),
                          pf.Controller(c["Kp"], c["Ti_s"], c["f_valve_hz"], c["authority"]), it, r["P_set_Pa"])
    assert x["status"] == r["event_sequence_status"]
    for k in ("valve_travel", "peak_deviation_max", "ripple_transfer_shaft", "P_compressor_el_W"):
        assert x["objectives"][k] == pytest.approx(r["objectives"][k], rel=1e-6)


def test_committed_chain_sample_reproduces(f1, grid):
    ch = json.loads(JSON_CHAINS.read_text(encoding="utf-8"))
    row = ch["rows_with_any_feasible_P_req"][0]
    cand, sc, comp = row[0], row[1], row[2]
    A = float(cand.split("_")[0][1:])
    its = [x for x in pf.load_f1_records(f1, [A], scenarios=[sc]) if x.candidate == cand]
    its.sort(key=lambda x: STATES.index(x.state))
    pc = pf.CompressorPlant.from_design(grid[comp])
    sw = pf.steady_sweep(pf.intake_side(its, pf.filter_none()), pc, _pl(), ch["targets_Pa"],
                         np.array([i.f1_status == "FEASIBLE_AT_STATE" for i in its]))
    ok = (sw["bits"] == 0).all(axis=0)
    with np.errstate(all="ignore"):
        md = np.where(ok, np.min(np.where(np.isfinite(sw["mdot_total_kgps"]), sw["mdot_total_kgps"], np.inf), axis=0),
                      np.nan)
    for i in range(len(ch["targets_Pa"])):
        vals = md[i:]
        best = np.nanmax(vals) if np.isfinite(vals).any() else None
        got = row[3 + i]
        if best is None:
            assert got is None
        else:
            assert got == pytest.approx(best * 1e6, rel=1e-6)


def test_pins_hold(main_doc):
    for p, h in main_doc["pins"].items():
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h, p


def test_md_generated_from_json(main_doc):
    md = MD.read_text(encoding="utf-8")
    assert "Generated by" in md and main_doc["deliverable_status"] in md
    for f in main_doc["findings"]:
        assert f["id"] in md


def test_hygiene_new_files():
    for p in (MODULE, BUILDER, Path(__file__)):
        t = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in t
    t = Path(__file__).read_text(encoding="utf-8")
    assert "pytest." + "skip" not in t and "mark." + "skip" not in t and "xfa" + "il" not in t
    assert "archengine" not in MODULE.read_text(encoding="utf-8").split('"""', 2)[2]
    for name in (JSON_MAIN, JSON_CHAINS, JSON_TRANS):
        json.loads(name.read_text(encoding="utf-8"))
    assert math.isfinite(pf.orbital_period_s(200.0))
    # the builder's record of the size_orifice_for_pressure bracket matches the (unmodified) reservoir source
    assert "lo, hi = 1e-8, 3e-2" in (ROOT / "abep_sim/reservoir.py").read_text(encoding="utf-8")
    assert "SIZE_ORIFICE_BRACKET_M2 = (1e-8, 3e-2)" in BUILDER.read_text(encoding="utf-8")
