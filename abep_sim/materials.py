"""Materials database (Phase 2, item 21).

Every entry carries mechanical, thermal, optical, AO, surface-chemistry, sputtering, SEE, outgassing and
radiation fields with a fidelity tag. Values are literature-class priors unless `fidelity` says otherwise;
replace with coupon data via `set_property()`, which records provenance.

Field notes
  ao_yield_cm3_atom   erosion yield for 5 eV ram O (Kapton-referenced, 3.0e-24)
  gamma0, gamma_Ea_eV O-atom surface recombination: gamma(T) = gamma_min + gamma0*exp(-Ea/kT)  (Arrhenius-like,
                      literature spread is large; metals 0.01-0.3, oxides/glass 1e-3-1e-2)
  sputter_Eth_eV, sputter_Y300  threshold energy and yield at 300 eV normal incidence (atoms/ion, Xe-referenced),
                      Y(E) ~ Y300 * ((E/Eth - 1)/(300/Eth - 1))^1.5 clipped >= 0 (Bohdansky-shaped)
  see_Emax_eV, see_dmax  secondary electron emission: delta(E) = dmax * (E/Emax) * exp(1 - E/Emax) (Vaughan-lite)
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from .constants import K_B, E_CHARGE


@dataclass
class Material:
    name: str
    cls: str                       # metal | ceramic | polymer | composite | coating | magnet | emitter
    density: float                 # kg/m3
    E_GPa: float
    yield_MPa: float
    cte_ppm_K: float
    k_W_mK: float
    cp_J_kgK: float
    emissivity: float
    absorptivity: float
    ao_yield_cm3_atom: float
    gamma_min: float
    gamma0: float
    gamma_Ea_eV: float
    sputter_Eth_eV: float
    sputter_Y300: float
    see_Emax_eV: float
    see_dmax: float
    tml_pct: float                 # total mass loss (outgassing)
    cvcm_pct: float
    rad_tid_krad: float            # tolerance where relevant (structural: high)
    T_max_K: float
    fidelity: str = "literature"
    source: str = "literature-class prior"
    notes: str = ""

    def gamma_O(self, T_K: float) -> float:
        return self.gamma_min + self.gamma0 * math.exp(-self.gamma_Ea_eV * E_CHARGE / (K_B * T_K))

    def sputter_yield(self, E_eV: float) -> float:
        if E_eV <= self.sputter_Eth_eV:
            return 0.0
        x = (E_eV / self.sputter_Eth_eV - 1.0) / (300.0 / self.sputter_Eth_eV - 1.0)
        return self.sputter_Y300 * max(x, 0.0) ** 1.5

    def see_yield(self, E_eV: float) -> float:
        x = E_eV / self.see_Emax_eV
        return self.see_dmax * x * math.exp(1.0 - x)


DB: dict[str, Material] = {}


def _add(*a, **k):
    m = Material(*a, **k); DB[m.name] = m


#     name             cls        rho    E    Ys  CTE   k    cp   eps  alp  AOyield   gmin   g0    Ea    Eth  Y300  Emax dmax  TML  CVCM  TID   Tmax
_add("Al6061",         "metal",   2700,  69,  276, 23.6, 167, 896, 0.05, 0.15, 0.0,     0.02,  0.30, 0.10, 27,  1.0,  300, 0.95, 0.0, 0.0, 1e6, 500, notes="bare Al; anodise for AO")
_add("Al2O3_anodised", "coating", 3950, 370,  0,   8.1,  30, 880, 0.80, 0.30, 0.0,     0.002, 0.02, 0.15, 60,  0.35, 400, 6.5,  0.0, 0.0, 1e6, 1200, notes="low gamma, AO stable, high SEE")
_add("Ti6Al4V",        "metal",   4430, 114,  880, 8.6,  7,  560, 0.30, 0.50, 0.0,     0.01,  0.10, 0.08, 30,  0.55, 280, 0.9,  0.0, 0.0, 1e6, 700)
_add("SS316",          "metal",   8000, 193,  290, 16,   16, 500, 0.35, 0.45, 0.0,     0.03,  0.35, 0.09, 30,  0.7,  300, 1.1,  0.0, 0.0, 1e6, 800, notes="catalytic for O recombination")
_add("Cu_OFHC",        "metal",   8960, 117,  70,  17,   390, 385, 0.05, 0.30, 0.007e-24, 0.05, 0.60, 0.07, 25, 1.9, 300, 1.3, 0.0, 0.0, 1e6, 600)
_add("Mo",             "metal",   10200, 330, 500, 4.8,  138, 250, 0.10, 0.40, 0.05e-24, 0.02, 0.20, 0.10, 45, 0.6, 350, 1.25, 0.0, 0.0, 1e6, 1500, notes="MoO3 volatile > ~600 C")
_add("W",              "metal",   19300, 411, 750, 4.5,  173, 132, 0.05, 0.40, 0.0,     0.02,  0.20, 0.10, 60, 0.35, 650, 1.4, 0.0, 0.0, 1e6, 2000, notes="WO3 volatile > ~800 C")
_add("Graphite",       "ceramic", 1800,  10,  30,  3.0,  100, 710, 0.85, 0.90, 1.2e-24,  0.01, 0.05, 0.10, 35, 0.2,  300, 1.0, 0.0, 0.0, 1e6, 2500, notes="CO/CO2 chemical erosion in O")
_add("BN",             "ceramic", 2100,  50,  0,   1.0,  30, 800, 0.85, 0.30, 0.0,     0.002, 0.02, 0.15, 45, 0.25, 350, 2.8,  0.0, 0.0, 1e6, 1200, notes="Hall channel; slight B2O3 surface glass")
_add("BN_SiO2",        "ceramic", 2000,  40,  0,   1.5,  20, 800, 0.85, 0.30, 0.0,     0.002, 0.02, 0.15, 45, 0.20, 350, 2.9,  0.0, 0.0, 1e6, 1200, notes="M26/Borosil-class")
_add("SiC",            "ceramic", 3200, 410,  0,   4.0,  120, 750, 0.85, 0.85, 0.0,     0.003, 0.02, 0.15, 50, 0.30, 400, 2.5,  0.0, 0.0, 1e6, 1600, notes="passivating SiO2")
_add("Quartz",         "ceramic", 2200,  72,  0,   0.5,  1.4, 740, 0.85, 0.10, 0.0,     0.0005,0.005,0.20, 40, 0.30, 400, 2.4,  0.0, 0.0, 1e6, 1300)
_add("Kapton_HN",      "polymer", 1420,  2.5, 70,  20,   0.12,1090,0.80, 0.40, 3.0e-24,  0.01, 0.05, 0.10, 20, 0.5, 300, 2.0, 0.8, 0.01, 1e5, 550)
_add("Kapton_SiOx",    "coating", 1450,  2.5, 70,  20,   0.12,1090,0.80, 0.40, 0.02e-24, 0.001,0.01, 0.20, 40, 0.3, 400, 2.4, 0.5, 0.01, 1e5, 550, notes="1300 A SiOx; pinhole-limited")
_add("CFRP",           "composite",1600, 70,  600, 1.0,  5,   800, 0.85, 0.90, 2.6e-24,  0.01, 0.05, 0.10, 30, 0.4, 300, 1.2, 0.5, 0.05, 1e6, 450)
_add("SmCo_bare",      "magnet",  8400, 150, 0,   10,   12,  370, 0.35, 0.50, 0.3e-24,  0.02, 0.20, 0.10, 30, 0.8, 300, 1.2, 0.0, 0.0, 1e7, 620, notes="Curie ~1070 K, T_op <= 350 C; coat")
_add("LaB6",           "emitter", 4720, 400, 0,   6.4,  47,  560, 0.60, 0.60, 0.0,     0.02,  0.20, 0.10, 30, 0.5, 300, 1.1, 0.0, 0.0, 1e6, 2000, notes="poisons in O; Xe-shield")
_add("Ag",             "metal",   10490, 83,  55,  18.9, 429, 235, 0.03, 0.10, 10.5e-24, 0.05, 0.60, 0.05, 20, 2.5, 300, 1.5, 0.0, 0.0, 1e6, 500, notes="AO catastrophic")


def set_property(name: str, field_name: str, value, source: str, fidelity: str = "breadboard"):
    m = DB[name]
    setattr(m, field_name, value); m.fidelity = fidelity; m.source = source


def table():
    import pandas as pd
    return pd.DataFrame([asdict(m) for m in DB.values()])


def surface_ageing_alpha(alpha0: float, fluence_atoms_m2: float, phi_c: float = 1.0e26, alpha_inf: float = 0.95) -> float:
    """Accommodation drift with AO fluence: alpha -> alpha_inf as the surface roughens/oxidises.
    phi_c is the characteristic fluence (literature-class prior; coupon data replaces it)."""
    return alpha_inf - (alpha_inf - alpha0) * math.exp(-fluence_atoms_m2 / phi_c)
