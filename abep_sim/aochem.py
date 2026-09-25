"""Atomic-oxygen chemistry for ABEP.

What matters, and what this module computes:

1. Ram AO flux and mission fluence (atoms/m^2). At V~7.8 km/s the O atom carries ~5 eV,
   enough to break C-C, C-H, Si-O bonds: erosion, not just oxidation.
2. Erosion depth per material over the mission from published erosion yields
   (cm^3/atom, Kapton-referenced). Decides intake, harness, coating, insulator choice.
3. Heterogeneous recombination on intake/compressor walls: O + O(ads) -> O2. Every wall
   collision has a probability gamma of recombining. After N collisions the O fraction
   is (1-gamma)^N. A compressor with hundreds of wall collisions delivers mostly O2, not O.
   This changes: mean ion mass (thrust per ion), dissociation energy sink in the discharge
   (O2 -> 2O costs ~5.1 eV before ionisation), and which species hits the cathode.
4. Oxidation/poisoning classes for plasma-facing and emitter materials.
5. Homogeneous gas-phase chemistry is negligible at these pressures (< 1 Pa): mean free
   path >> reservoir size, three-body recombination rate ~ n^3 -> zero. Only walls matter.

Yields and gammas are literature-class priors (NASA/ESA AO databases; recombination
coefficients from low-pressure plasma reactor literature). Replace with coupon data
from the RFP-mandated AO-beam tests.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .constants import M_SPECIES, E_CHARGE, AMU

# Erosion yield, cm^3 / O-atom (5 eV ram O). Kapton reference = 3.0e-24.
EROSION_YIELD_CM3_PER_ATOM = {
    "kapton_HN": 3.0e-24, "teflon_FEP": 0.05e-24, "epoxy_CFRP": 2.6e-24, "polyimide_coated_SiOx": 0.02e-24,
    "silver": 10.5e-24, "copper": 0.007e-24, "aluminium": 0.0, "titanium": 0.0,
    "molybdenum": 0.05e-24, "graphite": 1.2e-24, "carbon_carbon": 0.9e-24,
    "boron_nitride": 0.0, "alumina": 0.0, "SiC": 0.0, "SmCo_bare": 0.3e-24,
}
# Effective wall recombination coefficient for O on the surface (per collision)
RECOMB_GAMMA = {
    "aluminium_oxide": 0.005, "stainless_steel": 0.07, "titanium": 0.02, "copper": 0.2,
    "silver": 0.25, "boron_nitride": 0.003, "alumina": 0.003, "quartz": 0.0005, "gold": 0.03,
}
# Emitter / plasma-facing behaviour in O-rich plasma
MATERIAL_CLASS = {
    "LaB6": "poisons: forms La2O3/B2O3 layers, work function rises; must be Xe-shielded",
    "BaO_W": "poisons rapidly; unacceptable without Xe shielding",
    "tungsten": "forms volatile WO3 above ~800 C: erosion accelerates with temperature",
    "molybdenum": "MoO3 volatile above ~600 C: grid/keeper erosion",
    "graphite": "CO/CO2 formation: sputter + chemical erosion",
    "boron_nitride": "stable; slight B2O3 surface glass, acceptable channel wall",
    "alumina": "stable insulator",
    "SiC": "passivating SiO2; acceptable",
    "SmCo": "oxidises if bare -> coat or shield magnets",
}


@dataclass
class AOParams:
    intake_wall: str = "aluminium_oxide"     # anodised Al collimator
    compressor_wall: str = "stainless_steel"
    n_wall_collisions_intake: float = 20.0
    n_wall_collisions_compressor: float = 300.0   # molecular-drag stages: many
    n_wall_collisions_reservoir: float = 50.0
    reservoir_wall: str = "titanium"
    wall_T_K: float = 350.0


def ao_flux(atm: dict) -> dict:
    """Ram AO number flux [atoms/m^2/s] and kinetic energy [eV]."""
    n_O = atm["rho"] * atm["fO"] / M_SPECIES["O"]
    flux = n_O * atm["V"]
    E_eV = 0.5 * M_SPECIES["O"] * atm["V"] ** 2 / E_CHARGE
    return {"n_O": n_O, "ao_flux": flux, "ao_energy_eV": E_eV}


def fluence(atm: dict, hours: float) -> float:
    return ao_flux(atm)["ao_flux"] * hours * 3600.0


def erosion_depth_um(material: str, fl_atoms_m2: float, exposure_factor: float = 1.0) -> float:
    """Depth [um] = yield[cm3/atom] * fluence[atoms/cm2] * exposure factor (1 = full ram)."""
    y = EROSION_YIELD_CM3_PER_ATOM[material]
    return y * (fl_atoms_m2 * 1e-4) * exposure_factor * 1e4


def recombination_fraction(ao: AOParams) -> float:
    """Fraction of incoming O that survives to the thruster as atomic O."""
    surv = 1.0
    for wall, n in ((ao.intake_wall, ao.n_wall_collisions_intake),
                    (ao.compressor_wall, ao.n_wall_collisions_compressor),
                    (ao.reservoir_wall, ao.n_wall_collisions_reservoir)):
        surv *= (1.0 - RECOMB_GAMMA[wall]) ** n
    return surv


def inlet_composition(atm: dict, ao: AOParams) -> dict:
    """Mass fractions delivered to the thruster after wall recombination (O -> O2).
    Mass is conserved: recombined O mass goes to O2."""
    s = recombination_fraction(ao)
    fO = atm["fO"] * s
    fO2 = atm["fO2"] + atm["fO"] * (1.0 - s)
    fN2 = atm["fN2"]
    m_mean = 1.0 / (fO / M_SPECIES["O"] + fN2 / M_SPECIES["N2"] + fO2 / M_SPECIES["O2"])
    # Extra energy sink per delivered kg: O2 dissociation (5.12 eV) needed before O+ can form,
    # if the discharge dissociates it; N2 dissociation (9.8 eV) is mostly avoided (N2+ path).
    diss_J_per_kg = fO2 * (5.12 * E_CHARGE) / M_SPECIES["O2"]
    return {"fO": fO, "fN2": fN2, "fO2": fO2, "O_survival": s, "m_mean_inlet": m_mean,
            "diss_sink_J_per_kg": diss_J_per_kg}


def material_report(atm: dict, hours: float, materials=None, exposure_factor=1.0) -> list[dict]:
    fl = fluence(atm, hours)
    rows = []
    for m in (materials or EROSION_YIELD_CM3_PER_ATOM):
        rows.append({"material": m, "erosion_um": erosion_depth_um(m, fl, exposure_factor),
                     "fluence_atoms_m2": fl})
    return rows
