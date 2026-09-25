"""Phase 5 mission run: the complete chain on the real mission profile.

For a design (full physics), propagate 26,000 h with: J2, co-rotation, full spacecraft drag (intake + bus +
arrays with pointing), solar-cycle density, altitude-hold controller with flow throttling, eclipse and array power,
AO-fluence-driven intake ageing (alpha -> eta_c through the TPMC ROM), radiation dose, plume erosion, debris,
and the life/reliability model on the actual firing hours. Reports the mission-level closure and the limiting item.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from .constants import RFP
from .atmosphere import atmosphere
from .intake import IntakeParams, CompressorParams, collection, compress
from .system import Config, evaluate
from .mission_env import Spacecraft, spacecraft_drag, propagate, plume_interaction
from .radiation import RadEnv, electronics_margins, uv_contamination_ageing, debris_puncture, shielding_mass
from .materials import surface_ageing_alpha
from .life import LifeInputs, reliability, hall_channel_life, blade_life
from .transient import _atm_at


def run_phase5(cfg: Config, sc: Spacecraft, hours: float = RFP.mission_hours, dt_h: float = 4.0,
               f107_mean: float = 150.0, f107_amp: float = 80.0, phase_yr: float = 0.0, shield_mm: float = 2.0,
               intake_phi_c: float = 1.0e26, alpha_inf: float = 0.95, thrust_cap_mN: float = RFP.thrust_max_mN) -> dict:
    """intake_phi_c: characteristic AO fluence for accommodation drift (atoms/m^2); 1e26 = fast ageing prior,
    1e28 = a surface that keeps its scattering character over the mission. Coupon data decides."""
    base = evaluate(cfg)                                   # design point (mean solar) for masses, life rates
    alpha0 = cfg.intake.accommodation
    ao_flux = base["ao_flux_m2s"]
    fluence = 0.0; fired_h = 0.0; energy = 0.0
    state = {"fluence": 0.0}

    def drag_fn(alt, t_h):
        f107 = f107_mean + f107_amp * math.sin(2 * math.pi * (t_h / 8766.0 + phase_yr) / 11.0)
        atm = _atm_at(alt, f107)
        # AO ageing of the intake surface
        alpha = surface_ageing_alpha(alpha0, state["fluence"], phi_c=intake_phi_c, alpha_inf=alpha_inf)
        ip = IntakeParams(area_m2=cfg.intake.area_m2, accommodation=min(alpha, 1.0), use_tpmc=cfg.intake.use_tpmc,
                          L_over_d=cfg.intake.L_over_d, phi=cfg.intake.phi, off_axis_deg=sc.pointing_sigma_deg * 0.8)
        col = collection(ip, atm)
        d = spacecraft_drag(sc, atm["rho"], atm.get("V_rel", atm["V"]), cfg.intake.area_m2, col["C_D"])
        atm["_col"] = col; atm["_drag"] = d
        return d["D_total_N"], atm

    P_base = base.get("eng_P_bus_steady_W", base["P_total_air_W"])
    ecl_state = {"P_avail": None}

    def thrust_fn(alt, t_h, atm):
        col = atm["_col"]
        # throttle: scale the design-point thrust with collected mass flow (thrust ~ flow near the design point),
        # cap at drag*(1+gain*alt_err) and at 25 mN
        ratio = col["mdot_collected"] * 1e6 / max(base["mdot_air_mgps"], 1e-9)
        T_cap = base["T_air_mN"] * 1e-3 * ratio
        D = atm["_drag"]["D_total_N"]
        T_cmd = min(max(D * (1 + 0.05 * (cfg.alt_km - alt)), 0.0), thrust_cap_mN * 1e-3, T_cap)
        frac = T_cmd / max(T_cap, 1e-12)
        P_bus = P_base * (0.25 + 0.75 * frac * ratio)
        # power-limited throttling: orbit-average available power (set by propagate via atm) caps the thrust
        P_av = atm.get("_P_avail")
        if P_av is not None:
            P_room = P_av - sc.bus_housekeeping_W
            if P_bus > P_room:
                k = max((P_room - 0.25 * P_base) / max(0.75 * P_base * ratio, 1e-9), 0.0)
                T_cmd = T_cap * min(k, frac)
                P_bus = P_base * (0.25 + 0.75 * min(k, frac) * ratio)
        state["fluence"] += ao_flux * dt_h * 3600 * (atm["rho"] / base["rho"])
        return T_cmd, P_bus

    prop = propagate(sc, cfg.alt_km, hours, dt_h, drag_fn, thrust_fn)
    df = prop["df"]
    fired_h = float(len(df) * dt_h)
    # environment items on the actual profile
    rad = RadEnv(alt_km=cfg.alt_km, inc_deg=sc.inc_deg, years=hours / 8766.0)
    el = electronics_margins(rad, shield_mm)
    m_shield = shielding_mass(shield_mm, 0.12)
    uv = uv_contamination_ageing(hours, alpha_s0=0.15)
    deb_int = debris_puncture(cfg.intake.area_m2, hours, cfg.alt_km, 1.0)
    deb_rad = debris_puncture(base.get("eng_A_radiator_m2", 0.1), hours, cfg.alt_km, 0.5)
    pl = plume_interaction(sc, base["I_beam_A"] if "I_beam_A" in base else base.get("pl_I_d_A", 2.0) * 0.85,
                           22.0, base.get("pl_m_ion_amu", 22.0), base["vd_V"],
                           n_neutral_exit_m3=base["p_in_Pa"] / (1.380649e-23 * 900) * 0.3, hours=fired_h)
    li = LifeInputs(hall_sputter_um_per_kh=base.get("pl_wall_erosion_um_per_kh", 150.0), hall_wall_thickness_mm=cfg.hall_wall_mm,
                    blade_coating_um=cfg.blade_coating_um, blade_tip_mps=base.get("comp_tip_mps", 400.0),
                    ao_flux_ram_m2_s=ao_flux, intake_alpha0=alpha0, mission_h=RFP.mission_hours, firing_h=RFP.ignition_hours,
                    cathode_starts=int(hours / 24 * 0.5))
    rel = reliability(li, {"hall_channel": hall_channel_life(li)["life_h"], "blade_coating": blade_life(li)["coating_life_h"]})
    alpha_end = min(surface_ageing_alpha(alpha0, state["fluence"], phi_c=intake_phi_c, alpha_inf=alpha_inf) + uv["delta_accommodation"], 1.0)
    alt_held = (not prop["reentered"]) and prop["min_alt_km"] > cfg.alt_km - 10.0
    closed = alt_held and el["all_ok"] and pl["ok"]
    limit = ("reentry" if prop["reentered"] else "altitude_loss_power_limited" if not alt_held else
             "radiation" if not el["all_ok"] else "plume_arrays" if not pl["ok"] else "none")
    duty = float((df.T_mN > 0.05 * df.T_mN.max()).mean()) if len(df) else 0.0
    return {"df": df, "mission_closed": closed, "limiting": limit, "reentered": prop["reentered"], "min_alt_km": prop["min_alt_km"],
            "duty_power_limited": duty, "hours_throttled": float((df.P_bus_W < 0.9 * df.P_bus_W.max()).sum() * dt_h),
            "mean_eclipse": prop["mean_eclipse"], "min_power_margin_W": prop["min_power_margin_W"],
            "hours_power_short": prop["hours_power_short"], "raan_drift_deg_per_day": prop["raan_drift_deg_per_day"],
            "ao_fluence_m2": state["fluence"], "alpha_end": alpha_end, "tid_krad": el["tid_krad_behind_shield"],
            "ddd_p_cm2": el["ddd_p_cm2_behind_shield"], "electronics_ok": el["all_ok"],
            "worst_device": min(el["devices"].items(), key=lambda kv: kv[1]["tid_margin"])[0], "shield_mass_kg": m_shield,
            "uv_alpha_s_end": uv["alpha_s_end"], "contamination_um": uv["contamination_deposit_um"],
            "debris_P_intake": deb_int["P_at_least_one"], "debris_P_radiator": deb_rad["P_at_least_one"],
            "plume_direct_frac": pl["f_beam_direct"], "coverglass_erosion_um": pl["coverglass_erosion_cex_um"] + pl["coverglass_erosion_direct_um"],
            "R_15000h": rel["R_15000h"], "R_26000h": rel["R_26000h"], "D_mean_mN": float(df.D_mN.mean()),
            "D_intake_frac": float(base["drag_mN"] / df.D_mN.mean()) if df.D_mN.mean() > 0 else 0.0,
            "T_mean_mN": float(df.T_mN.mean()), "P_bus_mean_W": float(df.P_bus_W.mean()), "P_avail_mean_W": float(df.P_avail_W.mean())}


if __name__ == "__main__":
    import json
    cfg = Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5),
                 CompressorParams(ratio=2000), vd_V=275, gaspath_physics=True, plasma_physics=True, engineering_physics=True,
                 hall_L_m=0.20, hall_shielding=0.03, hall_wall_mm=6.0, blade_coating_um=50, xe_aug_hours=500)
    r = run_phase5(cfg, Spacecraft())
    print(json.dumps({k: v for k, v in r.items() if k != "df"}, indent=1, default=float))


def run_mission_generic(arch_result: dict, sc: Spacecraft, gas: dict, hours: float = RFP.mission_hours, dt_h: float = 6.0,
                        f107_mean: float = 150.0, f107_amp: float = 80.0, phase_yr: float = 0.0, intake_phi_c: float = 1.0e28,
                        alpha0: float = 0.8, L_over_d: float = 5.0, thrust_cap_mN: float | None = None, pmap: dict | None = None,
                        alt0_km: float = 200.0, P_bus_max_W: float = RFP.power_max_W) -> dict:
    """Item 10: every architecture from archengine goes through the same 26,000 h propagator. The propulsion is
    represented by its optimised design point (thrust ∝ collected flow near the point, power ∝ flow), the intake by
    the TPMC ROM with AO ageing, the spacecraft by `sc`. Returns the same summary fields as run_phase5."""
    import numpy as np
    T0 = arch_result["T_mN"] * 1e-3; P0 = arch_result["P_bus_W"]; md0 = arch_result["mdot_air_mgps"] * 1e-6
    area = arch_result["x_area"]
    state = {"fluence": 0.0, "xe_used": 0.0, "fired_h": 0.0}

    def drag_fn(alt, t_h):
        f107 = f107_mean + f107_amp * math.sin(2 * math.pi * (t_h / 8766.0 + phase_yr) / 11.0)
        atm = _atm_at(alt, f107)
        alpha = surface_ageing_alpha(alpha0, state["fluence"], phi_c=intake_phi_c)
        ip = IntakeParams(area_m2=area, accommodation=min(alpha, 1.0), use_tpmc=True, L_over_d=L_over_d, off_axis_deg=sc.pointing_sigma_deg * 0.8)
        col = collection(ip, atm)
        d = spacecraft_drag(sc, atm["rho"], atm.get("V_rel", atm["V"]), area, col["C_D"])
        atm["_col"] = col; atm["_drag"] = d
        return d["D_total_N"], atm

    def thrust_fn(alt, t_h, atm):
        col = atm["_col"]; ratio = col["mdot_collected"] / max(md0, 1e-12)
        if pmap is not None:
            T_cap = float(np.interp(ratio, pmap["scale"], pmap["T_N"]))
            P_full = float(np.interp(ratio, pmap["scale"], pmap["P_bus_W"]))
        else:
            T_cap = T0 * ratio; P_full = P0 * ratio
        D = atm["_drag"]["D_total_N"]
        cap = (thrust_cap_mN or 1e9) * 1e-3
        T_cmd = min(max(D * (1 + 0.05 * (alt0_km - alt)), 0.0), cap, T_cap)
        frac = T_cmd / max(T_cap, 1e-12) if T_cap > 0 else 0.0
        P_bus = P_full * (0.25 + 0.75 * frac)
        P_av = atm.get("_P_avail")
        P_room = P_bus_max_W if P_av is None else min(P_av - sc.bus_housekeeping_W, P_bus_max_W)
        if P_bus > P_room:
            k = max((P_room - 0.25 * P_full) / max(0.75 * P_full, 1e-9), 0.0)
            T_cmd = T_cap * min(k, frac); P_bus = P_full * (0.25 + 0.75 * min(k, frac))
        state["P_peak"] = max(state.get("P_peak", 0.0), P_bus)
        # item 19: AO fluence from the actual atomic-O number density and relative velocity
        n_O = atm["rho"] * atm["fO"] / (16.0 * 1.66053906660e-27)
        state["fluence"] += n_O * atm.get("V_rel", atm["V"]) * dt_h * 3600
        if T_cmd > 0:
            state["fired_h"] += dt_h
        return T_cmd, P_bus

    prop = propagate(sc, alt0_km, hours, dt_h, drag_fn, thrust_fn)
    df = prop["df"]
    alt_held = (not prop["reentered"]) and prop["min_alt_km"] > alt0_km - 10.0
    return {"architecture": arch_result["architecture"], "mission_closed": alt_held, "reentered": prop["reentered"],
            "min_alt_km": prop["min_alt_km"], "D_mean_mN": float(df.D_mN.mean()), "T_mean_mN": float(df.T_mN.mean()),
            "P_bus_mean_W": float(df.P_bus_W.mean()), "P_avail_mean_W": float(df.P_avail_W.mean()),
            "hours_throttled": float((df.P_bus_W < 0.9 * df.P_bus_W.max()).sum() * dt_h), "mean_eclipse": prop["mean_eclipse"],
            "alpha_end": min(surface_ageing_alpha(alpha0, state["fluence"], phi_c=intake_phi_c), 1.0),
            "ao_fluence_m2": state["fluence"], "fired_hours": state["fired_h"], "P_bus_peak_W": state.get("P_peak", 0.0),
            "xe_cathode_kg_actual": 0.05e-6 * state["fired_h"] * 3600 if "lab6" in arch_result["architecture"] else 0.0}
