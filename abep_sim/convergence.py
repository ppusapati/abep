"""Numerical convergence study (stabilisation gate 5). Each item doubles (or halves) a numerical resolution and
reports the relative change of the engineering outputs. Pass criterion: |change| < 2 %."""
from __future__ import annotations
import math, time
import pandas as pd

TOL = 0.02


def _rel(a, b):
    return abs(b / a - 1.0) if a else (0.0 if b == 0 else float("inf"))


def tpmc_statistics_and_interpolation() -> list[dict]:
    """(a) statistical: frozen-surface points (n=12,000) vs direct TPMC at n=48,000; (b) interpolation: off-grid ROM vs
    direct TPMC at n=48,000."""
    from .atmosphere import atmosphere
    from .intake_tpmc import IntakeGeometry, intake_response
    from .intake import _tpmc_surface
    from .constants import M_SPECIES
    atm = atmosphere(200.0, "mean"); rows = []
    surf = _tpmc_surface(atm, "maxwell")
    fr = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}
    for ld, al, kind in ((5.0, 0.8, "on-grid"), (10.0, 0.5, "on-grid"), (7.0, 0.65, "off-grid"), (4.0, 0.9, "off-grid")):
        rom = surf(ld, 0.85 if kind == "off-grid" else 0.8, al, 0.0, fractions=fr)
        eta = 0.0; cd = 0.0
        tot = sum(fr.values())
        for sp, w in fr.items():
            r = intake_response(IntakeGeometry(area_m2=0.5, L_over_d=ld, phi=0.85 if kind == "off-grid" else 0.8), atm, al, 0.0,
                                n=48000, seed=7, species_mass=M_SPECIES[sp])
            eta += w / tot * r["eta_c"]; cd += w / tot * r["C_D"]
        rows.append({"item": f"TPMC {kind} L/d={ld} a={al}", "quantity": "eta_c", "ref": eta, "value": rom["eta_c"], "rel": _rel(eta, rom["eta_c"])})
        rows.append({"item": f"TPMC {kind} L/d={ld} a={al}", "quantity": "C_D", "ref": cd, "value": rom["C_D"], "rel": _rel(cd, rom["C_D"])})
    return rows


def hall_solver_resolution() -> list[dict]:
    from . import plasma_devices as PD
    cases = [("anchor N2 2 mg/s 250 V", PD.coupled_channel(), 250.0, {"N2": 2e-6}, "cold"),
             ("air 1.3 mg/s 20 cm cold", PD.coupled_channel(L_m=0.20), 275.0, {"O": 0.559e-6, "N2": 0.663e-6, "O2": 0.078e-6}, "cold"),
             ("air 1.7 mg/s 20 cm hot", PD.coupled_channel(L_m=0.20), 275.0, {"O": 0.731e-6, "N2": 0.867e-6, "O2": 0.102e-6}, "hot")]
    rows = []
    base = dict(PD.NUMERICS)
    for name, ch, V, f, start in cases:
        r1 = PD.hall_run_coupled(ch, V, f, start=start)
        PD.NUMERICS.update({"hall_n_grid": 2 * base["hall_n_grid"], "hall_T_scan": 2 * base["hall_T_scan"], "hall_bisect": 2 * base["hall_bisect"]})
        r2 = PD.hall_run_coupled(ch, V, f, start=start)
        PD.NUMERICS.update(base)
        for q in ("T_N", "P_d_W", "Te_eV"):
            rows.append({"item": f"Hall {name}", "quantity": q, "ref": r2[q], "value": r1[q], "rel": _rel(r2[q], r1[q])})
    return rows


def source_balances() -> list[dict]:
    """Global model: power accounted vs absorbed, and mass conservation, at three powers."""
    import math as _m
    from .plasma_chem import Chamber, solve_global, M_ION, M_NEUT
    from .constants import E_CHARGE, K_B
    md = {"O": 0.40e-6, "N2": 0.50e-6, "O2": 0.10e-6}; rows = []
    for P in (100.0, 300.0, 600.0):
        ch = Chamber(magnetised_wall_factor=0.3, volume_m3=1e-3, wall_area_m2=0.06)
        st = solve_global(ch, md, P)
        acc = sum(st.power.values())
        cbar = {s: _m.sqrt(8 * K_B * ch.T_gas_K / (_m.pi * M_NEUT[s])) for s in M_NEUT}
        out = sum(st.n_neut.get(s, 0) * ch.exit_neutral_K * ch.exit_area_m2 * cbar[s] / 4 * M_NEUT[s] for s in ("O", "O2", "N2", "N")) + \
              sum(st.ion_exit_A[i] / E_CHARGE * M_ION[i] for i in st.ion_exit_A)
        rows.append({"item": f"source {int(P)} W", "quantity": "power accounted / absorbed", "ref": P, "value": acc, "rel": _rel(P, acc)})
        rows.append({"item": f"source {int(P)} W", "quantity": "mass out / in", "ref": sum(md.values()), "value": out, "rel": _rel(sum(md.values()), out)})
    return rows


def mission_timestep() -> list[dict]:
    import copy
    from . import archengine as AE
    from .mission_env import Spacecraft
    from .mission5 import run_mission_generic
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], gf, sc, AE.DesignConstraints(2500.0), gas_vars={"area": [1.3], "p_level": [0.05]},
                              size_arrays=True, mission_envelope=True, envelope_margin=1.0, keep_candidates=False)
    pm = AE.propulsion_map(r, gf); scm = copy.copy(sc); scm.array_area_m2 = r["A_array_m2"]
    res = {dt: run_mission_generic(r, scm, gf(r["x_area"], r["x_p_level"]), hours=8766.0, dt_h=dt, pmap=pm, P_bus_max_W=2500.0) for dt in (6.0, 3.0)}
    rows = []
    for q in ("T_mean_mN", "D_mean_mN", "P_bus_mean_W", "ao_fluence_m2", "min_alt_km"):
        rows.append({"item": "mission 1 yr dt 6 h vs 3 h", "quantity": q, "ref": res[3.0][q], "value": res[6.0][q], "rel": _rel(res[3.0][q], res[6.0][q])})
    rows.append({"item": "mission 1 yr dt 6 h vs 3 h", "quantity": "closed (same verdict)", "ref": float(res[3.0]["mission_closed"]),
                 "value": float(res[6.0]["mission_closed"]), "rel": 0.0 if res[3.0]["mission_closed"] == res[6.0]["mission_closed"] else 1.0})
    return rows


def search_resolution() -> list[dict]:
    """Nested-search grid: best worst-case T/D with the standard Hall grid vs a refined one (half steps)."""
    from . import archengine as AE
    from .mission_env import Spacecraft
    gf = AE.make_gas_fn(); A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    sc = Spacecraft(bus_frontal_m2=0.10, pointing_sigma_deg=0.5)
    def best(vd, L):
        orig = AE._variables
        AE._variables = lambda a: {"Vd": vd, "L_ch": L}
        try:
            r = AE.close_architecture(A["hall_internal+hall+lab6_xe"], gf, sc, AE.DesignConstraints(2500.0), gas_vars={"area": [1.3], "p_level": [0.05]},
                                      size_arrays=True, mission_envelope=True, envelope_margin=1.0)
        finally:
            AE._variables = orig
        c = pd.DataFrame(r.get("_candidates") or [])
        return float(c.env_ratio.max()) if len(c) else 0.0
    b1 = best([225.0, 250.0, 275.0, 300.0, 325.0], [0.12, 0.15, 0.20, 0.25, 0.30])
    b2 = best([225.0, 237.5, 250.0, 262.5, 275.0, 287.5, 300.0, 312.5, 325.0], [0.12, 0.135, 0.15, 0.175, 0.20, 0.225, 0.25, 0.275, 0.30])
    return [{"item": "Hall search grid standard vs half-step", "quantity": "best worst-case T/D", "ref": b2, "value": b1, "rel": _rel(b2, b1)}]


def run_all() -> pd.DataFrame:
    rows = []
    for f in (tpmc_statistics_and_interpolation, hall_solver_resolution, source_balances, mission_timestep, search_resolution):
        t = time.time(); rr = f()
        for r in rr: r["t_s"] = round(time.time() - t, 1)
        rows += rr
    df = pd.DataFrame(rows); df["pass"] = df.rel < TOL
    return df


if __name__ == "__main__":
    df = run_all(); pd.set_option("display.width", 200)
    print(df.round(5).to_string(index=False)); print("ALL PASS" if df["pass"].all() else f"{(~df['pass']).sum()} FAIL")
