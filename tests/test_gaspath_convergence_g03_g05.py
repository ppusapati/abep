"""G-03..G-05 gas-path convergence flags (owner decision A9.9 S2.4, UPSTREAM_ICD-Q7).

G-03 DragCompressor.run() reports converged / iterations / residual; the iteration limit is not convergence.
G-04 Reservoir.steady_state() reports converged / iterations / final balance residual.
G-05 size_orifice_for_pressure() reports the final pressure residual and whether the target is bracketed; a bracket
     endpoint is not convergence.
Converged numerics are unchanged: each solver is compared with a verbatim copy of its pre-change loop."""
import math

import pytest

from abep_sim.compressor import DragCompressor
from abep_sim.constants import K_B, M_SPECIES
from abep_sim.materials import DB
from abep_sim.reservoir import Reservoir, size_orifice_for_pressure, ORIFICE_BRACKET_M2

MD = {"O": 0.45e-6, "N2": 0.50e-6, "O2": 0.05e-6}


def _leaky():
    c = DragCompressor(turbo_area_m2=0.45, turbo_radius_m=0.40, rotor_material="CFRP", leak_conductance_m3_s=2.0)
    c.turbo_rows, c.n_stages, c.rpm = 3, 0, 10000
    return c


def _legacy_run(c, p_in, md):
    """Pre-G-03 DragCompressor.run(self_consistent=True), verbatim loop."""
    recirc = {s: 0.0 for s in md}
    r = None
    for _ in range(40):
        through = {s: md[s] + recirc[s] for s in md}
        r = c._run_once(p_in, through)
        new = {s: max(r["leak_kgps"][s], 0.0) for s in md}
        if all(abs(new[s] - recirc[s]) <= 1e-4 * max(md[s], 1e-15) for s in md):
            recirc = new; break
        recirc = {s: 0.5 * (recirc[s] + new[s]) for s in md}
    r["recirculated_kgps"] = recirc
    r["recirculation_frac"] = sum(recirc.values()) / max(sum(md.values()), 1e-30)
    r["delivered_kgps"] = dict(md)
    r["leak_kgps"] = recirc
    return r


def _legacy_steady_state(res, mdot_in):
    """Pre-G-04 Reservoir.steady_state() fixed point (number densities only), verbatim loop."""
    g_up = DB[res.upstream_material].gamma_O(res.T_K)
    surv_up = (1.0 - g_up) ** res.upstream_collisions
    m_in = dict(mdot_in)
    lost = m_in.get("O", 0.0) * (1.0 - surv_up)
    m_in["O"] = m_in.get("O", 0.0) * surv_up
    m_in["O2"] = m_in.get("O2", 0.0) + lost
    gam = DB[res.wall_material].gamma_O(res.T_K)
    species = ("O", "O2", "N2")
    n = {s: 1e14 for s in species}
    C = {s: res.conductance(s, res.anode_orifice_area_m2, res.anode_orifice_K) + res.conductance(s, res.leak_area_m2)
         for s in species}
    for _ in range(200):
        new = {}
        k_rec = gam * (res._cbar("O") / 4.0) * res.wall_area_m2
        new["O"] = m_in["O"] / (M_SPECIES["O"] * (C["O"] + k_rec)) if (C["O"] + k_rec) > 0 else 0.0
        rec_mass = k_rec * new["O"] * M_SPECIES["O"]
        new["O2"] = (m_in["O2"] + rec_mass) / (M_SPECIES["O2"] * C["O2"])
        new["N2"] = m_in["N2"] / (M_SPECIES["N2"] * C["N2"])
        if all(abs(new[s] - n[s]) <= 1e-6 * max(new[s], 1e-30) for s in species):
            n = new; break
        n = {s: 0.5 * (n[s] + new[s]) for s in species}
    return n


def _legacy_orifice(res, mdot_in, p_target):
    lo, hi = 1e-8, 3e-2
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        res.anode_orifice_area_m2 = mid
        p = res.steady_state(mdot_in)["p_total_Pa"]
        if p > p_target:
            lo = mid
        else:
            hi = mid
    return res.anode_orifice_area_m2


# ---------------------------------------------------------------- G-03
def test_g03_compressor_converged_flags_and_unchanged_numerics():
    c = _leaky()
    r = c.run(0.008, MD)
    assert r["converged"] is True and r["solver_status"] == "CONVERGED"
    assert 1 <= r["iterations"] < DragCompressor.RECIRC_MAX_ITER
    assert r["residual"] <= DragCompressor.RECIRC_RTOL
    ref = _legacy_run(_leaky(), 0.008, MD)
    for k in ("p_out_Pa", "CR_active", "P_el_W", "mass_kg", "recirculation_frac"):
        assert r[k] == ref[k], k                                     # bit-identical
    assert r["CR_by_species"] == ref["CR_by_species"] and r["leak_kgps"] == ref["leak_kgps"]


def test_g03_iteration_limit_is_not_convergence():
    c = _leaky()
    c.RECIRC_MAX_ITER = 2                                           # instance override: force the limit
    r = c.run(0.008, MD)
    assert r["converged"] is False and r["solver_status"] == "MODEL_NOT_CONVERGED"
    assert r["iterations"] == 2 and r["residual"] > DragCompressor.RECIRC_RTOL
    assert r["p_out_Pa"] > 0 and "recirculated_kgps" in r          # raw state kept for diagnostics


def test_g03_direct_evaluation_and_size_for_carry_status():
    c = _leaky()
    d = c.run(0.008, MD, self_consistent=False)
    assert d["solver_status"] == "DIRECT_EVALUATION" and d["converged"] is True
    s = DragCompressor(turbo_area_m2=0.05, turbo_radius_m=0.12).size_for(0.005, MD, 5)
    assert {"converged", "iterations", "residual", "solver_status"} <= set(s)


# ---------------------------------------------------------------- G-04
def test_g04_reservoir_flags_balance_and_unchanged_numerics():
    res = Reservoir()
    r = res.steady_state(MD)
    assert r["converged"] is True and r["solver_status"] == "CONVERGED"
    assert 1 <= r["iterations"] < Reservoir.SS_MAX_ITER and r["residual"] <= Reservoir.SS_RTOL
    assert r["balance_residual_rel"] < 1e-5                         # mass balance closes at the returned state
    assert r["n_species"] == _legacy_steady_state(Reservoir(), MD)


def test_g04_iteration_limit_is_not_convergence():
    res = Reservoir(); res.SS_MAX_ITER = 3
    r = res.steady_state(MD)
    assert r["converged"] is False and r["solver_status"] == "MODEL_NOT_CONVERGED"
    assert r["iterations"] == 3 and r["residual"] > Reservoir.SS_RTOL and r["balance_residual_rel"] > 1e-3


# ---------------------------------------------------------------- G-05
def test_g05_reachable_target_converges_and_area_unchanged():
    res = Reservoir()
    area = size_orifice_for_pressure(res, MD, 0.05)
    assert isinstance(area, float)                                   # legacy interface unchanged
    assert area == _legacy_orifice(Reservoir(), MD, 0.05)
    rep = size_orifice_for_pressure(Reservoir(), MD, 0.05, report=True)
    assert rep["area_m2"] == area and rep is not None
    assert rep["bracketed"] and rep["reachable"] and rep["converged"] and rep["solver_status"] == "CONVERGED"
    assert abs(rep["p_residual_rel"]) <= 1e-6
    assert res.orifice_sizing["converged"] is True                  # diagnostics left on the reservoir


@pytest.mark.parametrize("p_target", [1e12, 1e-9])
def test_g05_unbracketed_target_is_not_convergence(p_target):
    rep = size_orifice_for_pressure(Reservoir(), MD, p_target, report=True)
    assert rep["bracketed"] is False and rep["reachable"] is False
    assert rep["converged"] is False and rep["solver_status"] == "MODEL_NOT_CONVERGED"
    lo, hi = ORIFICE_BRACKET_M2
    assert math.isclose(rep["area_m2"], lo if p_target > 1 else hi, rel_tol=1e-6)   # ended on a bracket endpoint
    assert abs(rep["p_residual_rel"]) > 1e-3


# ---------------------------------------------------------------- production callers (fail closed / carry)
def _eval(area, p_target):
    from abep_sim.system import Config
    from abep_sim.programme.closure import evaluate
    from abep_sim.intake import IntakeParams, CompressorParams
    return evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=area, accommodation=0.8, use_tpmc=True, L_over_d=5),
                           CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, p_target_Pa=p_target))


def test_system_evaluate_flags_unbracketed_orifice_and_fails_closed():
    bad = _eval(1.3, 0.05)                    # orifice setpoint not reachable inside the area bracket
    assert bad["gaspath_status"] == "MODEL_NOT_CONVERGED" and "orifice_sizing" in bad["gaspath_not_converged"]
    assert bad["orifice_bracketed"] is False and bad["chk_compressor_feasible"] is False and bad["feasible"] is False
    ok = _eval(0.7, 0.1)
    assert ok["gaspath_status"] == "CONVERGED" and ok["gaspath_not_converged"] == []
    assert ok["comp_converged"] and ok["res_converged"] and ok["orifice_converged"]


def _arch():
    from abep_sim import archengine as AE
    from abep_sim.mission_env import Spacecraft
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    return AE, A["hall_internal+hall+lab6_xe"], Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)


def test_archengine_refuses_half_converged_gas_state():
    AE, a, sc = _arch()
    good = AE.make_gas_fn()(0.7, 0.1)
    assert good["gaspath_status"] == "CONVERGED"
    bad = dict(good, gaspath_status="MODEL_NOT_CONVERGED", gaspath_not_converged="compressor_recirculation")
    r = AE.close_architecture(a, lambda area, p: bad, sc, AE.DesignConstraints(2500.0),
                              gas_vars={"area": [0.7], "p_level": [0.1]}, keep_candidates=False)
    assert r["status"] == "MODEL_NOT_CONVERGED" and r["feasible"] is False


def test_archengine_carries_orifice_flag_and_arch_compare_refuses():
    AE, a, sc = _arch()
    from abep_sim import arch_compare as ac
    gf = AE.make_gas_fn()
    flagged = gf(1.3, 0.05)
    assert flagged["gaspath_status"] == "MODEL_NOT_CONVERGED" and flagged["gaspath_not_converged"] == "orifice_sizing"
    r = AE.close_architecture(a, gf, sc, AE.DesignConstraints(2500.0), gas_vars={"area": [1.3], "p_level": [0.05]},
                              keep_candidates=False)
    # review fix D-02/N2 (2026-10-01): the orifice-unreached state is never reported as a successful solution
    assert r["status"] == "MODEL_NOT_CONVERGED" and r["feasible"] is False
    assert r["gaspath_status"] == "MODEL_NOT_CONVERGED" and r["evidence_admissible"] is False
    with pytest.raises(ac.SpecError, match="not admissible"):
        ac.UpstreamState.from_gas_path(flagged, "x")
    good = gf(0.7, 0.1)
    u = ac.UpstreamState.from_gas_path(good, "x")
    stripped = {k: v for k, v in good.items() if k not in ("gaspath_status", "gaspath_not_converged")}
    assert u.fingerprint() == ac.UpstreamState.from_gas_path(stripped, "x").fingerprint()
