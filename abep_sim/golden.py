"""Golden benchmark cases (stabilisation gate 6).

Each case records the intermediate state of the chain — not only the final thrust — so that any later implementation
(Julia/Rust) can be checked stage by stage: atmosphere -> intake -> compressor/reservoir -> source plasma -> accelerator
-> power/thermal/mass/life -> spacecraft T/D -> mission. Values are produced by the frozen scenario (frozen NRLMSIS
dataset + frozen TPMC surface), so they are deterministic on any machine.

    python -m abep_sim.golden generate      # rewrite abep_sim/data/golden_v1.json (only on an intentional model change)
    python -m abep_sim.golden check         # compare; also run by the test suite
"""
from __future__ import annotations
import json, os, math

GOLDEN_FILE = os.path.join(os.path.dirname(__file__), "data", "golden_v1.json")


def _flt(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, bool) or v is None or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def case_atmosphere():
    from .atmosphere import atmosphere
    out = {}
    for alt in (180.0, 200.0, 230.0):
        for sol in ("low", "mean", "high"):
            a = atmosphere(alt, sol)
            out[f"{int(alt)}_{sol}"] = _flt({k: a[k] for k in ("rho", "fO", "fN2", "fO2", "T", "n", "V", "n_O")})
    return out


def case_intake():
    from .atmosphere import atmosphere
    from .intake import IntakeParams, collection
    atm = atmosphere(200.0, "mean"); out = {}
    for sc in ("maxwell", "cll"):
        for a, ld in ((0.8, 5.0), (0.95, 10.0), (0.5, 3.0)):
            c = collection(IntakeParams(area_m2=0.7, accommodation=a, use_tpmc=True, L_over_d=ld, scattering=sc), atm)
            out[f"{sc}_a{a}_ld{ld}"] = _flt({k: c[k] for k in ("eta_c", "C_D", "mdot_collected", "mdot_incident") if k in c})
    return out


def case_gas_path():
    from .system import Config, evaluate
    from .intake import IntakeParams, CompressorParams
    out = {}
    for area in (0.7, 1.3):
        r = evaluate(Config("hall_1stage", 200, "mean", IntakeParams(area_m2=area, accommodation=0.8, use_tpmc=True, L_over_d=5),
                            CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True))
        out[f"A{area}"] = _flt({k: r[k] for k in ("eta_c", "C_D", "mdot_air_mgps", "p_in_Pa", "P_comp_W", "m_comp_kg", "m_intake_kg",
                                                   "fO_inlet", "fO2_inlet", "drag_mN") if k in r})
    return out


def case_source_plasma():
    from .plasma_chem import Chamber, solve_global
    md = {"O": 0.40e-6, "N2": 0.50e-6, "O2": 0.10e-6}; out = {}
    for P in (100.0, 300.0):
        st = solve_global(Chamber(magnetised_wall_factor=0.3, volume_m3=1e-3, wall_area_m2=0.06), md, P, f_cutoff_Hz=2.45e9)
        out[f"P{int(P)}"] = _flt({"Te_eV": st.Te_eV, "n_e": st.n_e, "util_total": st.util_total, "eV_per_ion": st.eV_per_usable_ion,
                                  "P_iz_W": st.power["ionisation_excitation_W"], "P_wall_W": st.power["wall_W"],
                                  "I_exit_A": sum(st.ion_exit_A.values()), "sustained": st.sustained})
    return out


def case_hall():
    from .plasma_devices import coupled_channel, hall_run_coupled
    out = {}
    r = hall_run_coupled(coupled_channel(), 250.0, {"N2": 2e-6})
    out["anchor_N2"] = _flt({k: r[k] for k in ("T_N", "P_d_W", "I_d_A", "I_beam_A", "eta_b", "Te_eV", "n_e", "P_jet_W", "f_cx", "util_hall")})
    for md, start in ((1.0, "cold"), (1.3, "cold"), (1.7, "cold"), (1.7, "hot")):
        f = {"O": 0.43 * md * 1e-6, "N2": 0.51 * md * 1e-6, "O2": 0.06 * md * 1e-6}
        r = hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f, start=start)
        out[f"air_{md}_{start}"] = _flt({k: r.get(k) for k in ("T_N", "P_d_W", "I_d_A", "Te_eV", "n_e", "P_jet_W", "ignited")})
    f = {"O": 0.43e-6, "N2": 0.51e-6, "O2": 0.06e-6}
    r = hall_run_coupled(coupled_channel(L_m=0.20), 275.0, f, {"O+": 0.17, "N2+": 0.10, "O2+": 0.03})
    out["air_1.0_seed0.3A"] = _flt({k: r.get(k) for k in ("T_N", "P_d_W", "Te_eV", "n_e")})
    return out


def case_accelerators():
    from . import archengine as AE
    gf = AE.make_gas_fn(); gas = gf(0.7, "nominal")
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    out = {}
    g = AE._propulsion(A["ecr+grids+lab6_xe"], gas, {"P_ion": 800.0, "Vb": 1000.0, "A_grid": 1.2e-2, "gap": 1e-3})
    out["ecr_grids"] = _flt({"T_N": g["T_N"], "P_acc_W": g["P_acc_W"], "I_beam_A": g["I_beam_A"], "P_hat": g["P_hat"], "f_cx": g["f_cx"],
                             "life_h": g["life_items"]["grids"], "chi": g["chi_preion"]})
    AE.NOZZLE_ENERGY_BOUND["on"] = False
    n = AE._propulsion(A["ecr+mag_nozzle"], gas, {"P_ion": 700.0, "B0": 0.0875, "R_m": 50.0, "A_throat": 3e-3})
    out["ecr_nozzle"] = _flt({"T_N": n["T_N"], "E_i_eV": n["E_i_eV"], "eta_det": n["eta_det"], "m_acc": n["m_acc"], "chi": n["chi_preion"]})
    h = AE._propulsion(A["ecr+hall+lab6_xe"], gas, {"P_ion": 100.0, "Vd": 300.0, "L_ch": 0.20})
    out["ecr_hall"] = _flt({"T_N": h["T_N"], "P_acc_W": h["P_acc_W"], "I_beam_A": h["I_beam_A"], "chi": h["chi_preion"], "P_neut_W": h["P_neut_W"]})
    return out


def case_architecture_closure():
    from . import archengine as AE
    from .mission_env import Spacecraft
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    out = {}
    r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], gf, sc, AE.DesignConstraints(2500.0), gas_vars={"area": [1.3], "p_level": [0.05]},
                              size_arrays=True, mission_envelope=True, envelope_margin=1.0, keep_candidates=False)
    out["ext_hall_2p5kW"] = _flt({k: r.get(k) for k in ("status", "x_Vd", "x_L_ch", "T_mN", "P_bus_W", "P_jet_W", "ledger_resid", "T_over_D_sc",
                                                         "MEV_kg", "CBE_kg", "A_array_m2", "m_system_kg", "life_sys_h", "Q_waste_W", "A_rad_m2", "xe_kg")})
    return out


def case_mission():
    from . import archengine as AE
    from .mission_env import Spacecraft
    from .mission5 import run_mission_generic
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], gf, sc, AE.DesignConstraints(2500.0), gas_vars={"area": [1.3], "p_level": [0.05]},
                              size_arrays=True, mission_envelope=True, envelope_margin=1.0, keep_candidates=False)
    pm = AE.propulsion_map(r, gf)
    import copy
    scm = copy.copy(sc); scm.array_area_m2 = r["A_array_m2"]
    m = run_mission_generic(r, scm, gf(r["x_area"], r["x_p_level"]), hours=4000.0, dt_h=6.0, pmap=pm, P_bus_max_W=2500.0)
    out = {"map_T_N": {str(s): float(t) for s, t in zip(pm["scale"], pm["T_N"])},
           "mission_4000h": _flt({k: m[k] for k in ("mission_closed", "min_alt_km", "D_mean_mN", "T_mean_mN", "P_bus_mean_W", "P_bus_peak_W",
                                                     "ao_fluence_m2", "fired_hours")})}
    return out


CASES = {"atmosphere": case_atmosphere, "intake": case_intake, "gas_path": case_gas_path, "source_plasma": case_source_plasma,
         "hall": case_hall, "accelerators": case_accelerators, "architecture_closure": case_architecture_closure, "mission": case_mission}


def generate() -> dict:
    data = {"version": "golden_v1", "model": "ABEP Python Physics Candidate v1.5.1", "cases": {k: f() for k, f in CASES.items()}}
    json.dump(data, open(GOLDEN_FILE, "w"), indent=1, sort_keys=True)
    return data


def _compare(ref, new, path, rtol, errs):
    if isinstance(ref, dict):
        for k in ref:
            if k not in new:
                errs.append(f"{path}/{k}: missing"); continue
            _compare(ref[k], new[k], f"{path}/{k}", rtol, errs)
    elif isinstance(ref, float) and isinstance(new, float):
        if not (math.isclose(ref, new, rel_tol=rtol, abs_tol=1e-30) or (math.isnan(ref) and math.isnan(new))):
            errs.append(f"{path}: {ref!r} -> {new!r} ({(new / ref - 1) if ref else float('inf'):+.2e})")
    elif ref != new:
        errs.append(f"{path}: {ref!r} -> {new!r}")


def check(cases=None, rtol: float = 1e-6) -> list[str]:
    ref = json.load(open(GOLDEN_FILE))["cases"]
    errs = []
    for k in (cases or CASES):
        _compare(ref[k], json.loads(json.dumps(CASES[k]())), k, rtol, errs)
    return errs


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        d = generate(); print("written", GOLDEN_FILE, sum(len(v) for v in d["cases"].values()), "entries")
    else:
        e = check(); print("OK" if not e else "\n".join(e))
