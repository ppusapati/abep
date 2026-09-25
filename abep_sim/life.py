"""Life and reliability (Phase 4, items 19, 20, 23; item 41 partial).

Hall channel:   remaining wall thickness = t0 - (sputter rate + AO chemical rate) * hours ; life = t0 / rate
Intake coating: AO erosion depth vs coating thickness; accommodation drift alpha(Phi) -> eta_c(t) via TPMC ROM
Turbo blades:   AO erosion at tip (impact energy from V_rel + tip speed), coating thickness limited
Magnets:        SmCo demagnetisation margin vs temperature (linear loss to Curie), AO if bare
Cathode:        oxide coverage growth -> work function -> required T -> evaporation; start-cycle limit
Compressor:     bearing life (magnetic: electronics-limited; ball: L10 hours)
Reliability:    series system, exponential for electronics, Weibull for wear-out; R(15,000 h), R(26,000 h), SPF list
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .materials import DB, surface_ageing_alpha
from .constants import AMU, E_CHARGE


@dataclass
class LifeInputs:
    hall_wall_material: str = "BN"
    hall_wall_thickness_mm: float = 4.0
    hall_sputter_um_per_kh: float = 300.0
    hall_wall_O_flux_atoms_m2_s: float = 1e20       # neutral O hitting the channel wall (chemical erosion)
    intake_coating: str = "Al2O3_anodised"
    intake_coating_um: float = 15.0
    intake_alpha0: float = 0.6
    ao_flux_ram_m2_s: float = 3.6e19
    blade_material: str = "CFRP"
    blade_coating: str = "Al2O3_anodised"
    blade_coating_um: float = 20.0
    blade_tip_mps: float = 430.0
    V_rel_mps: float = 7800.0
    magnet_T_K: float = 380.0
    magnet_material: str = "SmCo_bare"
    magnet_coated: bool = True
    cathode_T_K: float = 1720.0
    cathode_starts: int = 3000
    cathode_start_limit: int = 10000
    bearing_type: str = "magnetic"
    duty: float = 0.58
    mission_h: float = 26000.0
    firing_h: float = 15000.0


def hall_channel_life(li: LifeInputs) -> dict:
    m = DB[li.hall_wall_material]
    # chemical erosion by O: yield * flux (thermal/low-energy O on ceramics is small but non-zero)
    chem_um_per_kh = m.ao_yield_cm3_atom * (li.hall_wall_O_flux_atoms_m2_s * 1e-4) * 3600e3 * 1e4
    rate = li.hall_sputter_um_per_kh + chem_um_per_kh
    life_h = li.hall_wall_thickness_mm * 1e3 / max(rate, 1e-9) * 1e3
    return {"rate_um_per_kh": rate, "chem_um_per_kh": chem_um_per_kh, "life_h": life_h,
            "remaining_mm_at_15kh": li.hall_wall_thickness_mm - rate * 15.0 / 1e3, "ok": life_h >= li.firing_h}


def intake_life(li: LifeInputs, tpmc_surface=None) -> dict:
    m = DB[li.intake_coating]
    fl = li.ao_flux_ram_m2_s * li.mission_h * 3600
    depth_um = m.ao_yield_cm3_atom * (fl * 1e-4) * 1e4
    alpha_end = surface_ageing_alpha(li.intake_alpha0, fl)
    out = {"ao_fluence_m2": fl, "coating_erosion_um": depth_um, "coating_ok": depth_um < li.intake_coating_um,
           "alpha_start": li.intake_alpha0, "alpha_end": alpha_end}
    if tpmc_surface is not None:
        out["eta_c_start"] = tpmc_surface(5.0, 0.85, li.intake_alpha0)["eta_c"]
        out["eta_c_end"] = tpmc_surface(5.0, 0.85, min(alpha_end, 1.0))["eta_c"]
    return out


def blade_life(li: LifeInputs) -> dict:
    """AO on the rotor tip: relative impact speed adds tip speed in quadrature-ish; yield scales ~ E^0.7 above 5 eV."""
    v_imp = math.sqrt(li.V_rel_mps ** 2 + li.blade_tip_mps ** 2)
    E_eV = 0.5 * 16 * AMU * v_imp ** 2 / E_CHARGE
    scale = (E_eV / 5.0) ** 0.7
    coat = DB[li.blade_coating]; sub = DB[li.blade_material]
    flux = li.ao_flux_ram_m2_s * 0.5       # blade sees roughly half the ram flux (chord/solidity)
    hours = li.mission_h
    rate_coat_um_per_kh = coat.ao_yield_cm3_atom * scale * (flux * 1e-4) * 3600e3 * 1e4
    rate_sub_um_per_kh = sub.ao_yield_cm3_atom * scale * (flux * 1e-4) * 3600e3 * 1e4
    # coating defects: a pinhole fraction exposes the substrate; effective rate = coating rate + f_pinhole * substrate rate
    f_pinhole = 0.01
    rate_eff = rate_coat_um_per_kh + f_pinhole * rate_sub_um_per_kh
    coat_life_h = li.blade_coating_um / max(rate_eff, 1e-9) * 1e3
    return {"impact_E_eV": E_eV, "coating_rate_um_per_kh": rate_coat_um_per_kh, "substrate_rate_um_per_kh": rate_sub_um_per_kh,
            "coating_life_h": coat_life_h, "ok": coat_life_h >= hours, "substrate_loss_if_bare_mm": rate_sub_um_per_kh * hours / 1e6}


def magnet_life(li: LifeInputs) -> dict:
    m = DB[li.magnet_material]
    # reversible loss ~ -0.03 %/K for SmCo; irreversible above ~T_max
    loss_frac = 0.0003 * max(li.magnet_T_K - 293.0, 0.0)
    ok = li.magnet_T_K < m.T_max_K and loss_frac < 0.05
    ao_ok = li.magnet_coated or m.ao_yield_cm3_atom == 0.0
    return {"B_loss_frac": loss_frac, "T_ok": li.magnet_T_K < m.T_max_K, "ao_ok": ao_ok, "ok": ok and ao_ok}


def cathode_life(li: LifeInputs) -> dict:
    evap_A, evap_E = 3.4e7, 5.9
    evap = evap_A * math.exp(-evap_E * E_CHARGE / (1.380649e-23 * li.cathode_T_K))
    life_evap_h = 1.0e-3 * DB["LaB6"].density / max(evap, 1e-30) / 3600.0
    cycles_ok = li.cathode_starts <= li.cathode_start_limit
    return {"life_evaporation_h": life_evap_h, "starts": li.cathode_starts, "cycles_ok": cycles_ok,
            "ok": life_evap_h >= li.firing_h and cycles_ok}


def compressor_life(li: LifeInputs) -> dict:
    if li.bearing_type == "magnetic":
        return {"bearing_life_h": 1e6, "ok": True, "note": "electronics-limited; no wear-out"}
    L10 = 20000.0
    return {"bearing_life_h": L10, "ok": L10 >= li.mission_h, "note": "ball bearing L10"}


def reliability(li: LifeInputs, wearout: dict, lam_electronics_per_h: float = 2.0e-6, redundant_electronics=True) -> dict:
    """Series system. Electronics: exponential (redundant pair -> 2R - R^2). Wear-out items: Weibull with beta=3
    and characteristic life = predicted life."""
    def weibull(t, eta_life, beta=3.0):
        return math.exp(-(t / max(eta_life, 1e-9)) ** beta)
    out = {}
    for t in (li.firing_h, li.mission_h):
        R_el = math.exp(-lam_electronics_per_h * t)
        if redundant_electronics:
            R_el = 2 * R_el - R_el ** 2
        R = R_el
        for k, life in wearout.items():
            R *= weibull(t, life)
        out[f"R_{int(t)}h"] = R
    spf = [k for k, life in wearout.items() if life < li.mission_h * 1.5]
    return {**out, "single_point_or_marginal": spf}
