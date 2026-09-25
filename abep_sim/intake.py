"""Intake collection, drag, and compressor/reservoir models.

All models are first-order and parameter-driven so that DSMC / breadboard
results can replace them without touching the rest of the pipeline.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .constants import K_B


@dataclass
class IntakeParams:
    area_m2: float = 1.0            # capture (ram) area
    eta_c_specular: float = 0.45    # collection efficiency, near-specular surface
    eta_c_diffuse: float = 0.25     # collection efficiency, AO-aged / diffuse surface
    accommodation: float = 0.5      # 0 = specular, 1 = diffuse (AO ageing pushes ->1)
    off_axis_deg: float = 0.0       # pointing error
    cd: float = 2.2                 # free-molecular drag coefficient on ram face
    body_area_m2: float = 0.0       # extra spacecraft frontal area not used as intake
    mass_per_m2: float = 2.5        # kg/m2 AO-resistant honeycomb collimator
    mass_fixed: float = 1.0         # kg
    # Phase-1 TPMC geometry path: when use_tpmc, eta_c / C_D / passive CR / mass come from intake_tpmc
    use_tpmc: bool = False
    scattering: str = "maxwell"     # "maxwell" (alpha = diffuse fraction) | "cll" (alpha = alpha_n = alpha_t)
    L_over_d: float = 10.0
    phi: float = 0.85
    d_mm: float = 10.0
    filter: bool = False


@dataclass
class CompressorParams:
    ratio: float = 500.0            # TOTAL number-density ratio n_out/n_ambient (passive x active)
    area_ratio: float = 10.0        # intake capture area / throat area -> passive ram compression
    T_out_K: float = 350.0          # reservoir temperature
    p_base_W: float = 40.0          # bearings / motor / drive floor
    p_per_mgps_per_ln: float = 12.0 # W per (mg/s) per ln(ratio): losses scale ~ mdot*ln(CR)
    max_ratio: float = 5000.0       # beyond this, treat as infeasible for a single stage
    anode_conductance_m3_s: float | None = None   # if set, reservoir pressure follows throughput balance
    backflow_frac: float = 0.0      # fraction of collected flow lost to leakage/backflow before the anode
    mass_base_kg: float = 3.0
    mass_per_ln: float = 0.6        # kg per ln(ratio)


_SURF_CACHE: dict = {}


def _tpmc_surface(atm: dict, scattering: str = "maxwell"):
    """Frozen, versioned, species-resolved TPMC response surface shipped in abep_sim/data. Never generated here:
    rebuild explicitly with `python -m abep_sim.intake_tpmc build`. (eta_c, C_D, K_back depend on the speed ratio
    through sqrt(T/m), which varies < 10 % across 180-230 km and the solar cycle.)"""
    if scattering not in _SURF_CACHE:
        import pandas as pd
        from .intake_tpmc import frozen_surface_path, IntakeSurface
        df = pd.read_csv(frozen_surface_path())
        _SURF_CACHE[scattering] = IntakeSurface(df[df.scattering == scattering].reset_index(drop=True))
    return _SURF_CACHE[scattering]


def collection(intake: IntakeParams, atm: dict) -> dict:
    passive_override = None
    if intake.use_tpmc:
        fr = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}
        r = _tpmc_surface(atm, intake.scattering)(intake.L_over_d, intake.phi, min(max(intake.accommodation, 0.0), 1.0),
                                                 min(intake.off_axis_deg, 5.0), fractions=fr)
        eta_c = r["eta_c"]; cd = r["C_D"]; passive_override = r["CR_passive"]
        from .intake_tpmc import IntakeGeometry, intake_response
        m_int = r["mass_kg"] * (intake.area_m2 / 0.5)      # surface built at 0.5 m2; mass scales with area
        if intake.filter:
            m_int += 0.8 * intake.area_m2
    else:
        eta_c = ((1 - intake.accommodation) * intake.eta_c_specular
                 + intake.accommodation * intake.eta_c_diffuse)
        eta_c *= math.cos(math.radians(intake.off_axis_deg)) ** 2   # cosine-squared roll-off
        cd = intake.cd
        m_int = intake.mass_per_m2 * intake.area_m2 + intake.mass_fixed
    mdot_inc = atm["flux_kg_m2_s"] * intake.area_m2
    mdot_col = eta_c * mdot_inc
    a_front = max(intake.area_m2, 0.0) + intake.body_area_m2
    V = atm.get("V_rel", atm["V"])
    drag = 0.5 * atm["rho"] * V ** 2 * cd * a_front
    return {
        "eta_c": eta_c, "mdot_incident": mdot_inc, "mdot_collected": mdot_col, "C_D": cd,
        "drag_N": drag, "intake_mass_kg": m_int, "passive_override": passive_override,
    }


def passive_compression(comp: CompressorParams, atm: dict, eta_c: float) -> float:
    """Free-molecular ram compression of a passive intake.
    Flux balance: eta_c n V A_in = n_p (c_bar/4) A_throat  ->  n_p/n = 4 eta_c V/c_bar * A_in/A_throat."""
    c_bar = math.sqrt(8 * K_B * comp.T_out_K / (math.pi * atm["m_mean"]))
    return 4.0 * eta_c * atm["V"] / c_bar * comp.area_ratio


def compress(comp: CompressorParams, atm: dict, mdot_col: float, eta_c: float = 0.35,
             passive_override: float | None = None) -> dict:
    """Total ratio = passive (free) x active (costs power/mass)."""
    passive = passive_override if passive_override else passive_compression(comp, atm, eta_c)
    mdot_net = mdot_col * (1.0 - comp.backflow_frac)
    if comp.anode_conductance_m3_s:
        # molecular-flow network: throughput Q = (mdot/m) k T = p_res * C  ->  p_res set by flow and conductance
        p_out = (mdot_net / atm["m_mean"]) * K_B * comp.T_out_K / comp.anode_conductance_m3_s
        ratio_eff = max(p_out / (atm["n"] * K_B * comp.T_out_K), passive)
        p_out = atm["n"] * ratio_eff * K_B * comp.T_out_K
        active = max(ratio_eff / passive, 1.0)
    else:
        active = max(comp.ratio / passive, 1.0)
        ratio_eff = max(comp.ratio, passive)          # passive stage cannot be "un-compressed"
        p_out = atm["n"] * ratio_eff * K_B * comp.T_out_K
    n_out = atm["n"] * ratio_eff
    p_passive = atm["n"] * passive * K_B * comp.T_out_K
    ln_a = math.log(active)
    power = (comp.p_base_W if active > 1.0 else 0.0) + comp.p_per_mgps_per_ln * (mdot_net * 1e6) * ln_a
    mass = (comp.mass_base_kg if active > 1.0 else 0.5) + comp.mass_per_ln * ln_a
    return {
        "p_out_Pa": p_out, "p_passive_Pa": p_passive, "passive_ratio": passive, "active_ratio": active,
        "ratio_effective": ratio_eff, "mdot_net": mdot_net,
        "n_out": n_out, "comp_power_W": power, "comp_mass_kg": mass,
        "comp_feasible": active <= comp.max_ratio,
    }
