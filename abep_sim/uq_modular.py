"""UQ on the modular architecture engine (document 16, item 38).

For a fixed design (architecture, operating variables, intake area, reservoir pressure, array area) sample:
  epistemic: anomalous transport alpha_anom, ionisation-zone fraction, ionisation-rate scale, collisional-loss scale,
             intake accommodation (Maxwell alpha), ECR transported-current scale (assisted architectures)
  aleatory : bus frontal area (DRDO spacecraft unknown), AOCS pointing
and re-run the same propulsion physics at mean / solar-min / solar-max captured flow (design point from a cold start,
off-design by continuation), with the bus-power cap applied at solar max. Closure metric per sample:
  r = min( T/D (mean), T_lo/D_lo, T_hi/D_hi ),  mission closes with margin if r >= 1.1.
Returns samples, P(r >= 1), P(r >= 1.1), quantiles and Spearman sensitivities.

A9.22 layer separation: this module holds the priors and the per-sample physics (sample_closure). The UQ runner
(evaluate_sample / run_uq, which attach the evaluation-only success flag of abep_sim.assessment.arch_constraints) is
the programme layer, abep_sim.programme.uq_modular.
"""
from __future__ import annotations
import copy, math
import numpy as np
from .archengine import enumerate_architectures, arch_name, _propulsion, make_gas_fn, HALL_OVERRIDES
from .atmosphere import atmosphere
from .mission_env import Spacecraft, spacecraft_drag
from . import plasma_chem as PC
from . import plasma_devices as PD

PRIORS = {  # name: (low, mode, high, kind)
    "alpha_anom": (0.75, 0.88, 1.00, "epistemic"),
    "L_iz_frac": (0.33, 0.40, 0.47, "epistemic"),
    "rate_scale": (0.80, 1.00, 1.25, "epistemic"),
    "epsc_scale": (0.85, 1.00, 1.20, "epistemic"),
    "accommodation": (0.60, 0.80, 0.95, "epistemic"),
    "ecr_scale": (0.5, 1.0, 2.0, "epistemic"),
    "bus_frontal": (0.06, 0.10, 0.16, "aleatory"),
    "pointing": (0.3, 0.5, 1.0, "aleatory"),
}


def _tri(rng, lo, mo, hi, n):
    return rng.triangular(lo, mo, hi, n)


def sample_closure(a, x, area, p_level, A_array, P_cap, xs: dict, alt=200.0, eta_ppu=0.9, P_mag=25.0) -> dict:
    """Physics of one UQ sample: thrust / power at mean, solar-min and solar-max captured flow, drag, the closure ratio,
    ignition and the design-point component life. The evaluation-only success flag (ratio and life against the
    firing-life requirement) is an assessment: abep_sim.programme.uq_modular.evaluate_sample adds it (A9.22)."""
    alpha_q = round(xs["accommodation"] / 0.05) * 0.05                     # reuse cached gas states
    gf = make_gas_fn(alpha=alpha_q, alt=alt)
    gas = gf(area, p_level)
    rates0 = dict(PC.RATES); eps0 = dict(PC.EPS_C)
    for k, (k0, p, E, ion) in list(PC.RATES.items()):
        PC.RATES[k] = (k0 * xs["rate_scale"], p, E, ion)
    for k, (aa, bb) in list(PC.EPS_C.items()):
        PC.EPS_C[k] = (aa * xs["epsc_scale"], bb * xs["epsc_scale"])
    HALL_OVERRIDES.clear(); HALL_OVERRIDES.update({"alpha_anom": xs["alpha_anom"], "L_iz_frac": xs["L_iz_frac"]})
    x2 = dict(x)
    if "P_ion" in x2:
        x2["P_ion"] = x2["P_ion"] * xs["ecr_scale"]          # transported-current uncertainty as an effective power scale
    try:
        atm = atmosphere(alt, "mean")
        r_lo = atmosphere(alt, "low")["rho"] / atm["rho"]; r_hi = atmosphere(alt, "high")["rho"] / atm["rho"]
        sc = Spacecraft(bus_frontal_m2=xs["bus_frontal"], array_area_m2=A_array, pointing_sigma_deg=xs["pointing"])
        D = spacecraft_drag(sc, atm["rho"], atm.get("V_rel", atm["V"]), area, gas["C_D"])["D_total_N"]

        def run(scale, start):
            g2 = dict(gas); g2["mdot_air"] = gas["mdot_air"] * scale; g2["p_in"] = gas["p_in"] * scale
            HALL_OVERRIDES["start"] = start
            try:
                q = _propulsion(a, g2, x2)
            except ValueError:
                return 0.0, 0.0
            P = (q["P_acc_W"] + q["P_ion_W"] + q["P_neut_W"] + P_mag + gas["comp_power"] + 5.0) / eta_ppu + 12.0
            return q["T_N"], P

        T0, P0 = run(1.0, "cold")
        # component life at the design point (accelerator, neutralizer, blade/intake coatings)
        HALL_OVERRIDES["start"] = "cold"
        try:
            q0 = _propulsion(a, gas, x2)
            life = min(list(q0["life_items"].values()) + [gas["blade_life_h"], gas["intake_life_h"]])
        except ValueError:
            life = 0.0
        T_lo, _ = run(r_lo, "hot") if T0 > 0 else (0.0, 0.0)
        T_hi, P_hi = run(r_hi, "hot") if T0 > 0 else (0.0, 0.0)
        if P_hi > P_cap:
            T_hi *= P_cap / P_hi
        ratio = min(T0 / D, T_lo / (D * r_lo), T_hi / (D * r_hi)) if D > 0 else 0.0
        return {"T_mN": T0 * 1e3, "P_bus_W": P0, "T_lo_mN": T_lo * 1e3, "T_hi_mN": T_hi * 1e3, "D_mN": D * 1e3,
                "ratio_min": ratio, "ignited": T0 > 0, "life_h": life, "limit": ["mean", "solar_min", "solar_max"][int(np.argmin(
                    [T0 / D, T_lo / (D * r_lo), T_hi / (D * r_hi)]))] if T0 > 0 else "no_ignition"}
    finally:
        PC.RATES.clear(); PC.RATES.update(rates0); PC.EPS_C.clear(); PC.EPS_C.update(eps0); HALL_OVERRIDES.clear()
