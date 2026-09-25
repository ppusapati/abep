"""Radiation, UV/contamination and debris (Phase 5, items 26, 39, 40).

Radiation: dose-depth for a 200 km, high-inclination orbit over 3 years is dominated by SAA trapped protons
and outer-zone electrons; a parameterised dose-depth curve (literature-class, replace with SPENVIS/OMERE run):
  TID(t_Al) = D_e0 * exp(-t/l_e) + D_p0 * exp(-t/l_p) + D_floor   [krad(Si)] for t in mm Al
Displacement damage: 10 MeV-equivalent proton fluence behind shielding, same shape.
SEE: device upset rates from a generic LET-integral fit with shielding-independent heavy ions + shielding-
dependent proton-induced component. Margins per device class with RDM = 2.

UV/contamination: absorptivity drift of thermal coatings, silicone contamination -> SiOx deposit -> accommodation
increment on the intake. Debris/micrometeoroid: flux-area-time Poisson puncture probability for the intake and
radiator; 200 km is a low-debris regime (rapid decay), micrometeoroids dominate.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

DEVICES = {
    "mcu_fpga_radtol": {"tid_krad": 100.0, "ddd_p_cm2": 1e11, "let_th": 15.0, "seu_per_bit_day_geo": 1e-9, "sel_immune": True},
    "mcu_cots_screened": {"tid_krad": 30.0, "ddd_p_cm2": 5e10, "let_th": 8.0, "seu_per_bit_day_geo": 1e-7, "sel_immune": False},
    "gan_fet": {"tid_krad": 500.0, "ddd_p_cm2": 1e13, "let_th": 40.0, "seu_per_bit_day_geo": 0.0, "sel_immune": True},
    "si_mosfet": {"tid_krad": 100.0, "ddd_p_cm2": 1e12, "let_th": 30.0, "seu_per_bit_day_geo": 0.0, "sel_immune": True},
    "adc_dac": {"tid_krad": 50.0, "ddd_p_cm2": 1e11, "let_th": 20.0, "seu_per_bit_day_geo": 1e-8, "sel_immune": False},
    "1553_transceiver": {"tid_krad": 100.0, "ddd_p_cm2": 1e11, "let_th": 37.0, "seu_per_bit_day_geo": 0.0, "sel_immune": True},
    "magnetron_sspa": {"tid_krad": 50.0, "ddd_p_cm2": 1e11, "let_th": 20.0, "seu_per_bit_day_geo": 0.0, "sel_immune": False},
}


@dataclass
class RadEnv:
    alt_km: float = 200.0
    inc_deg: float = 97.4
    years: float = 3.0
    solar_max: bool = False
    # dose-depth parameters (krad(Si) per year at 0 mm and folding lengths): 200 km SSO class
    D_e0_krad_yr: float = 8.0
    l_e_mm: float = 0.8
    D_p0_krad_yr: float = 6.0
    l_p_mm: float = 3.5
    D_floor_krad_yr: float = 0.3
    ddd_p0_cm2_yr: float = 6e9
    l_ddd_mm: float = 4.0
    ddd_floor_cm2_yr: float = 3e8

    def tid_krad(self, t_al_mm: float) -> float:
        f = 1.4 if self.solar_max else 1.0
        return self.years * f * (self.D_e0_krad_yr * math.exp(-t_al_mm / self.l_e_mm)
                                 + self.D_p0_krad_yr * math.exp(-t_al_mm / self.l_p_mm) + self.D_floor_krad_yr)

    def ddd_fluence(self, t_al_mm: float) -> float:
        return self.years * (self.ddd_p0_cm2_yr * math.exp(-t_al_mm / self.l_ddd_mm) + self.ddd_floor_cm2_yr)

    def seu_rate_per_bit_day(self, let_th: float, t_al_mm: float) -> float:
        """GEO-referenced heavy-ion rate scaled by geomagnetic shielding at low inclination is ~0.1; SSO passes
        the poles so keep ~0.6; plus proton-induced term behind shielding."""
        hi = 0.6 * math.exp(-let_th / 20.0)
        proton = 3e-8 * math.exp(-t_al_mm / 3.0) * math.exp(-let_th / 6.0)
        return hi * 1e-8 + proton


def electronics_margins(env: RadEnv, t_al_mm: float, devices: dict | None = None, rdm: float = 2.0) -> dict:
    tid = env.tid_krad(t_al_mm); ddd = env.ddd_fluence(t_al_mm)
    out = {}
    for name, d in (devices or DEVICES).items():
        seu = env.seu_rate_per_bit_day(d["let_th"], t_al_mm)
        out[name] = {"tid_margin": d["tid_krad"] / (rdm * tid), "ddd_margin": d["ddd_p_cm2"] / (rdm * ddd),
                     "seu_per_bit_day": seu, "sel_risk": not d["sel_immune"],
                     "ok": d["tid_krad"] >= rdm * tid and d["ddd_p_cm2"] >= rdm * ddd}
    return {"tid_krad_behind_shield": tid, "ddd_p_cm2_behind_shield": ddd, "t_al_mm": t_al_mm, "devices": out,
            "all_ok": all(v["ok"] for v in out.values())}


def shielding_mass(t_al_mm: float, box_area_m2: float, rho: float = 2700.0) -> float:
    return t_al_mm * 1e-3 * box_area_m2 * rho


def uv_contamination_ageing(hours: float, alpha_s0: float = 0.15, d_alpha_s_per_yr: float = 0.03,
                            contamination_um_per_yr: float = 0.05, accommodation_per_um: float = 0.6) -> dict:
    """Coating solar absorptivity drift under UV; silicone/organic contamination oxidised by AO to SiOx deposit,
    which roughens the intake surface: delta_alpha_accommodation = k * deposit thickness."""
    yrs = hours / 8766.0
    dep = contamination_um_per_yr * yrs
    return {"alpha_s_end": alpha_s0 + d_alpha_s_per_yr * yrs, "contamination_deposit_um": dep,
            "delta_accommodation": min(accommodation_per_um * dep, 0.3)}


def debris_puncture(area_m2: float, hours: float, alt_km: float = 200.0, size_mm: float = 1.0) -> dict:
    """Poisson puncture probability. Flux priors (per m^2 per yr): micrometeoroids > size_mm ~ 3e-5 * (1/size)^2.5;
    debris > 1 mm at 200 km ~ 1e-5 (decays fast); at 400 km ~ 3e-4."""
    yrs = hours / 8766.0
    f_mm = 3e-5 * (1.0 / size_mm) ** 2.5
    f_deb = 1e-5 * math.exp((alt_km - 200.0) / 60.0) * (1.0 / size_mm) ** 2.0
    lam = (f_mm + f_deb) * area_m2 * yrs
    return {"expected_hits": lam, "P_at_least_one": 1 - math.exp(-lam), "flux_mm": f_mm, "flux_debris": f_deb}
