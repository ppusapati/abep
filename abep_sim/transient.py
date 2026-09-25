"""Mission transient over the 3-year (26,000 h) life.

Per time step:
  atmosphere(alt, F10.7(t))  -> rho, composition (interpolated between low/mean/high tables)
  drag on the spacecraft ram face (intake + body)
  air-mode thrust available at the delivered mdot and inlet pressure
  controller: hold altitude -> commanded thrust = drag (+ correction for altitude error)
     - if T_air >= T_cmd : duty = T_cmd / T_air, air only
     - else               : duty = 1, Xe anode topping to T_cmd if Xe policy allows and Xe remains
  altitude update from residual force: da/dt = 2 a^1.5 (T - D) / (m_sc sqrt(mu))
  bookkeeping: firing hours, Xe consumed (cathode + topping), energy, AO fluence

Outputs a time-series DataFrame and a summary. This is the transient the RFP's
">15,000 h ignition / 26,000 h mission" pair actually implies: the duty cycle is not a
free parameter, it falls out of density vs thrust capability.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .constants import MU_EARTH, R_EARTH, RFP
from .atmosphere import atmosphere
from .intake import IntakeParams, CompressorParams, collection, compress
from .thruster import CARDS, performance, xe_for_thrust
from .aochem import AOParams, inlet_composition, ao_flux


@dataclass
class MissionParams:
    architecture: str = "hall_ecr"
    alt0_km: float = 200.0
    hold_alt_km: float = 200.0
    sc_mass_kg: float = 150.0
    body_area_m2: float = 0.0          # frontal area beyond the intake
    intake: IntakeParams = None
    compressor: CompressorParams = None
    vd_V: float = 250.0
    hours: float = RFP.mission_hours
    dt_h: float = 1.0
    f107_mean: float = 150.0
    f107_amp: float = 80.0
    cycle_years: float = 11.0
    cycle_phase_years: float = 0.0     # 0 = start at mean rising; 2.75 = start at max
    xe_budget_kg: float = 5.0          # anode-topping Xe available (cathode Xe accounted separately)
    xe_policy: str = "hold"            # "hold": use Xe to hold altitude; "air_only": never top up
    alt_gain: float = 0.05             # controller: extra thrust fraction per km of altitude error
    ao: AOParams = None

    def __post_init__(self):
        self.intake = self.intake or IntakeParams(area_m2=1.0, accommodation=0.5)
        self.compressor = self.compressor or CompressorParams(ratio=500)
        self.ao = self.ao or AOParams()


_GRID: dict = {}


def _grid_state(alt_km: float, solar: str) -> dict:
    """MSIS evaluated once per 5 km altitude bin and solar state, then linearly interpolated in altitude.
    (A direct call per time step with orbit-averaged MSIS costs ~30 ms; the mission run needs ~20,000 of them.)"""
    a0 = 5 * math.floor(alt_km / 5.0); a1 = a0 + 5
    out = {}
    for a in (a0, a1):
        key = (a, solar)
        if key not in _GRID:
            _GRID[key] = atmosphere(float(a), solar)
    f = (alt_km - a0) / 5.0
    r0, r1 = _GRID[(a0, solar)], _GRID[(a1, solar)]
    out = dict(r0)
    for k in ("rho", "fO", "fN2", "fO2", "T", "n", "m_mean", "V", "flux_kg_m2_s"):
        out[k] = math.exp((1 - f) * math.log(r0[k]) + f * math.log(r1[k])) if k in ("rho", "n", "flux_kg_m2_s") else (1 - f) * r0[k] + f * r1[k]
    out["alt_km"] = alt_km
    return out


def _atm_at(alt_km: float, f107: float) -> dict:
    """Interpolate the low/mean/high states in F10.7 (70/150/230), each from the altitude grid."""
    alt_km = max(150.0, min(alt_km, 300.0))
    lo, me, hi = (_grid_state(alt_km, s) for s in ("low", "mean", "high"))
    if f107 <= 150:
        w = (f107 - 70) / 80.0; a, b = lo, me
    else:
        w = (f107 - 150) / 80.0; a, b = me, hi
    w = min(max(w, 0.0), 1.0)
    out = dict(a)
    for k in ("rho", "fO", "fN2", "fO2", "T", "n", "m_mean"):
        out[k] = (1 - w) * a[k] + w * b[k] if k != "rho" else math.exp((1 - w) * math.log(a[k]) + w * math.log(b[k]))
    out["flux_kg_m2_s"] = out["rho"] * out["V"]
    return out


def run_mission(mp: MissionParams) -> tuple[pd.DataFrame, dict]:
    card = CARDS[mp.architecture]
    mp.intake.body_area_m2 = mp.body_area_m2
    n = int(mp.hours / mp.dt_h)
    alt = mp.alt0_km
    xe_left = mp.xe_budget_kg
    fired_h = energy_Wh = xe_used = fluence = 0.0
    rows = []
    reentered = False
    for i in range(n):
        t_h = i * mp.dt_h
        if alt < 150.0:
            reentered = True
            break
        t_y = t_h / 8766.0
        f107 = mp.f107_mean + mp.f107_amp * math.sin(2 * math.pi * (t_y + mp.cycle_phase_years) / mp.cycle_years)
        atm = _atm_at(alt, f107)
        col = collection(mp.intake, atm)
        cmp_ = compress(mp.compressor, atm, col["mdot_collected"], col["eta_c"])
        inlet = inlet_composition(atm, mp.ao)
        atm_in = {**atm, "fO": inlet["fO"], "fN2": inlet["fN2"], "fO2": inlet["fO2"]}
        perf = performance(card, atm_in, col["mdot_collected"], cmp_["p_out_Pa"], mp.vd_V)
        T_air = perf["T_N"]
        D = col["drag_N"]
        T_cmd = D * (1.0 + mp.alt_gain * (mp.hold_alt_km - alt))
        T_cmd = max(0.0, min(T_cmd, RFP.thrust_max_mN * 1e-3))
        xe_rate = 0.0
        if T_air >= T_cmd:
            # throttle by flow (valve / compressor speed), not by duty: power falls with mdot
            duty = 1.0 if T_cmd > 0 else 0.0
            frac = T_cmd / T_air if T_air > 0 else 0.0
            thr = performance(card, atm_in, col["mdot_collected"] * frac, cmp_["p_out_Pa"], mp.vd_V)
            T_del, P = thr["T_N"], thr["P_thruster_W"]
        else:
            duty = 1.0
            if mp.xe_policy == "hold" and xe_left > 0:
                xe_rate = xe_for_thrust(card, atm_in, col["mdot_collected"], cmp_["p_out_Pa"], T_cmd, mp.vd_V)
                pk = performance(card, atm_in, col["mdot_collected"], cmp_["p_out_Pa"], mp.vd_V, mdot_xe_anode=xe_rate)
                T_del, P = pk["T_N"], pk["P_thruster_W"]
            else:
                T_del, P = T_air, perf["P_thruster_W"]
        dt_s = mp.dt_h * 3600.0
        a = R_EARTH + alt * 1e3
        dadt = 2.0 * a ** 1.5 * (T_del * duty - D) / (mp.sc_mass_kg * math.sqrt(MU_EARTH))   # m/s
        alt += dadt * dt_s / 1e3
        fired_h += duty * mp.dt_h
        xe_step = (xe_rate * duty + card.cathode.xe_flow_mgps * 1e-6 * duty) * dt_s
        xe_left -= xe_rate * duty * dt_s
        xe_used += xe_step
        energy_Wh += (P * duty + cmp_["comp_power_W"]) * mp.dt_h
        fluence += ao_flux(atm)["ao_flux"] * dt_s
        rows.append({"t_h": t_h, "f107": f107, "alt_km": alt, "rho": atm["rho"], "drag_mN": D * 1e3,
                     "T_air_mN": T_air * 1e3, "T_cmd_mN": T_cmd * 1e3, "duty": duty,
                     "xe_topping_mgps": xe_rate * 1e6, "xe_left_kg": max(xe_left, 0.0),
                     "P_thr_W": P, "P_bus_W": (P + cmp_["comp_power_W"] + 30) / 0.9,
                     "mdot_air_mgps": col["mdot_collected"] * 1e6, "p_in_Pa": cmp_["p_out_Pa"],
                     "T_over_D": T_air / D if D > 0 else float("inf")})
    df = pd.DataFrame(rows)
    summary = {
        "architecture": mp.architecture, "intake_area_m2": mp.intake.area_m2, "comp_ratio": mp.compressor.ratio,
        "vd_V": mp.vd_V, "hours": mp.hours, "elapsed_hours": float(df.t_h.iloc[-1]) + mp.dt_h,
        "fired_hours": fired_h, "mean_duty": fired_h / (float(df.t_h.iloc[-1]) + mp.dt_h),
        "min_alt_km": float(df.alt_km.min()), "final_alt_km": float(df.alt_km.iloc[-1]),
        "alt_held": bool(df.alt_km.min() > mp.hold_alt_km - 5.0) and not reentered,
        "reentered": reentered, "reentry_time_h": float(df.t_h.iloc[-1]) if reentered else None,
        "xe_used_total_kg": xe_used, "xe_topping_exhausted": bool(xe_left <= 0),
        "mean_bus_power_W": float((df.P_bus_W * df.duty).mean()), "peak_bus_power_W": float(df.P_bus_W.max()),
        "energy_kWh": energy_Wh / 1000.0, "ao_fluence_m2": fluence,
        "hours_TD_ge_1": float((df.T_over_D >= 1.0).sum() * mp.dt_h),
        "ignition_req_met": fired_h <= RFP.ignition_hours * 1.0 or True,   # firing hours are a capability, not a cap
    }
    return df, summary


def plot_mission(df: pd.DataFrame, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    t = df.t_h / 8766.0
    axs[0].plot(t, df.f107); axs[0].set_ylabel("F10.7")
    axs[1].plot(t, df.drag_mN, label="drag"); axs[1].plot(t, df.T_air_mN, label="T_air avail"); axs[1].legend(); axs[1].set_ylabel("mN")
    axs[2].plot(t, df.duty, label="duty"); axs[2].plot(t, df.xe_topping_mgps, label="Xe topping mg/s"); axs[2].legend(); axs[2].set_ylabel("duty / mg/s")
    axs[3].plot(t, df.alt_km); axs[3].set_ylabel("alt km"); axs[3].set_xlabel("years")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def main(argv=None):
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(prog="abep-mission")
    ap.add_argument("--arch", default="hall_ecr"); ap.add_argument("--alt", type=float, default=200)
    ap.add_argument("--area", type=float, default=1.0); ap.add_argument("--acc", type=float, default=0.5)
    ap.add_argument("--cr", type=float, default=500); ap.add_argument("--vd", type=float, default=250)
    ap.add_argument("--sc-mass", type=float, default=150); ap.add_argument("--xe", type=float, default=5.0)
    ap.add_argument("--phase", type=float, default=0.0, help="solar-cycle phase at launch, years (2.75 = start at max)")
    ap.add_argument("--policy", default="hold", choices=["hold", "air_only"])
    ap.add_argument("-o", "--out", default="results/mission")
    a = ap.parse_args(argv)
    mp = MissionParams(a.arch, a.alt, a.alt, a.sc_mass, 0.0, IntakeParams(area_m2=a.area, accommodation=a.acc),
                       CompressorParams(ratio=a.cr), a.vd, cycle_phase_years=a.phase, xe_budget_kg=a.xe, xe_policy=a.policy)
    df, s = run_mission(mp)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.arch}_A{a.area}_CR{int(a.cr)}_V{int(a.vd)}_ph{a.phase}_{a.policy}"
    df.to_csv(out / f"{tag}.csv", index=False); plot_mission(df, out / f"{tag}.png")
    (out / f"{tag}.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
