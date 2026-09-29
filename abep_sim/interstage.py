"""Pre-ionizer -> Hall interstage transfer model (lane 18, ``interstage_v1``).

One common model for the plasma/gas transfer from an RF (``rf_hall``) or ECR (``ecr_hall``) pre-ionizer exit into the
downstream Hall channel. ``hall_only`` has no interstage and is refused. The RF and ECR arms differ only in the source
exit state they hand to this model; the duct, wall, junction and conservation logic are identical.

What it computes (steady, quasi-1-D plug flow along the duct, then a junction split):
  * ion wall loss: Bohm flux ``h n u_B`` to the side wall (unmagnetized Lieberman edge-to-centre ratio, the strong-axial-B
    "no radial loss" limit, or an explicitly supplied, sourced ``h``); floating dielectric wall only;
  * volume reactions (dissociative / radiative recombination, charge transfer, electron-impact ionization, ...) from a
    caller-supplied, sourced reaction list; wall neutralization of every ion; optional wall atom recombination;
  * neutral transport and pressure drop in free-molecular flow (Santeler transmission probability, aperture
    conductance), or an explicitly supplied conductance for other regimes; neutral entry-state consistency gate;
  * charge-state fraction evolution, ion transport efficiency ``eta_transport`` (= ion current delivered into the Hall
    channel / ion current leaving the source), neutral delivery / leakage, plume leakage of uncaptured ions;
  * an energy ledger (electron heat drawn from the source to hold T_e, wall heat, reaction heat, junction outflows);
  * element (particle), charge, mass and energy conservation residuals, gated (CLAUDE.md rule 4). Under the isothermal
    electron closure the energy residual is a bookkeeping-consistency check only (the conducted source heat closes the
    electron energy balance by construction); the element, charge and mass gates are independent checks;
  * process completeness: every required process class (recombination, ionization, charge transfer, electron-impact
    excitation / dissociation / elastic loss, wall atom recombination) is modelled or explicitly excluded per species.

Rules this module follows (CLAUDE.md rules 3, 4, 6, 10; docs/EVIDENCE.md):
  * No default physical, efficiency or numerical values. Every numeric input is a ``Sourced`` record (value, unit,
    source, evidence class, uncertainty) or an explicit ``TBD`` naming what it requires; a TBD anywhere in a case makes
    ``solve_interstage`` refuse (``InterstageTBDError``). Missing inputs raise; nothing is silently filled.
  * No silent extrapolation: every rate coefficient carries its stated validity domain and is refused outside it
    (``InterstageDomainError``); formula domains (free-molecular Knudsen range, the Lieberman h-factor pressure range)
    are enforced the same way.
  * Non-convergence and infeasibility are reported as ``status`` MODEL_ERROR / INFEASIBLE with every performance number
    set to ``None`` (never a half-converged state).
  * Pure and not wired into ``archengine`` (wiring is a model change; goldens must not move). It takes no Hall
    transport closure input and says nothing about Hall performance; it never compares architectures.

Formulas and data: docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md (equations, sources, evidence classes,
validity domain, limitations, milestone support). Interchange format: schemas/architecture_comparison/interstage_v1.schema.json.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Mapping, Sequence

import numpy as np

from .constants import AMU, E_CHARGE, K_B

MODEL_VERSION = "interstage_v1"
SCHEMA_ID = "interstage_v1"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
ARCHITECTURES_WITH_INTERSTAGE = ("rf_hall", "ecr_hall")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
STATUS_VALUES = ("OK", "INFEASIBLE", "MODEL_ERROR")

# Electron mass, CODATA 2022 (NIST, https://physics.nist.gov/cgi-bin/cuu/Value?me, accessed 2026-09-26):
# 9.1093837139(28) x 10^-31 kg. e and k_B are exact SI values, imported from abep_sim/constants.py.
M_E = 9.1093837139e-31

#: Sources of the formulas implemented here (all openly accessible; accessed 2026-09-26). "slide N" = the page number
#: printed on the slide. Details, equations and evidence classes: INTERSTAGE_MODEL.md section 7.
SOURCES = {
    "lieberman_short_course_2015": ("M. A. Lieberman, 'A short course on the principles of plasma discharges and "
                                    "materials processing' (LiebermanShortCourse15), UC Berkeley, "
                                    "https://people.eecs.berkeley.edu/~lieber/Day1View150315crop.pdf"),
    "chiggiato_2014": ("P. Chiggiato, 'Vacuum Technology for Ion Sources', CAS-CERN Accelerator School: Ion Sources, "
                       "arXiv:1404.0960, https://arxiv.org/abs/1404.0960"),
    "santeler_1986": ("D. J. Santeler, 'New concepts in molecular gas flow', J. Vac. Sci. Technol. A 4(3) (1986) 338-343, "
                      "doi:10.1116/1.573923 (bibliographic data via Crossref 2026-09-26; full text not accessed) - "
                      "formula as given by Chiggiato 2014 Eq. 21. Chiggiato's ref. [9] prints page 348, which Crossref "
                      "assigns to Santeler, 'Exit loss in viscous tube flow', JVST A 4, 348-352 (doi:10.1116/1.573925): "
                      "a citation error in the secondary source"),
    "leybold_fundamentals_2016": ("Leybold GmbH, 'Fundamentals of Vacuum Technology', Part No. 199 90, Edition 2016, "
                                  "https://www.leybold.com/content/dam/brands/leybold/downloads/brochures/"
                                  "general-brochures/Fundamentals_of_Vacuum_Technology_EN.pdf"),
    "sheehan_st_maurice_2004": ("C. H. Sheehan & J.-P. St.-Maurice, J. Geophys. Res. Space Phys. 109(A3) (2004), "
                                "doi:10.1029/2003JA010132 - abstract only (Crossref); full text not accessed"),
    "nist_asd": "NIST Atomic Spectra Database, ionization energies, https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html",
    "nist_webbook_n2": "NIST Chemistry WebBook, N2, https://webbook.nist.gov/cgi/cbook.cgi?ID=C7727379&Mask=20",
    "walker_ni_2011": "H. F. Walker & P. Ni, SIAM J. Numer. Anal. 49(4) (2011) 1715-1735, doi:10.1137/10078356X",
}

# Closure / mode vocabularies (all must be chosen explicitly by the caller; there is no default).
H_LIEBERMAN = "lieberman_unmagnetized"          # h_R = 0.8 / (4 + R/lambda_i)^(1/2), Lieberman short course slide 44
H_STRONG_B = "strong_axial_B_no_radial_loss"    # h = 0, Lieberman short course slide 53 (idealized limit)
H_EXPLICIT = "explicit_h"                       # caller-supplied, sourced h per ion species
RADIAL_LOSS_CLOSURES = (H_LIEBERMAN, H_STRONG_B, H_EXPLICIT)
WALL_ELECTRICAL = ("floating",)
NC_SANTELER = "molecular_santeler_circular"
NC_TRANSMISSION = "molecular_explicit_transmission"
NC_EXPLICIT = "explicit_conductance"
NEUTRAL_CONDUCTANCE_MODES = (NC_SANTELER, NC_TRANSMISSION, NC_EXPLICIT)
ELECTRON_CLOSURE_ISOTHERMAL = "isothermal_source_conduction"
ELECTRON_ENERGY_CLOSURES = (ELECTRON_CLOSURE_ISOTHERMAL,)
# Electron energy removed from the electron fluid per recombination event (explicit choice per reaction, no default):
#  * RECOMBINING_ELECTRON_THERMAL: (3/2) T_e, the mean energy of a Maxwellian electron. ASSUMED: it ignores the energy
#    dependence of the cross section. For k proportional to T_e^alpha the rate-weighted value is (3/2 + alpha) T_e, so
#    (3/2) T_e over-states the removed energy for alpha < 0 (e.g. 1.11 T_e for alpha = -0.39, 0.80 T_e for -0.70).
#  * RECOMBINING_ELECTRON_RATE_WEIGHTED: (3/2 + alpha) T_e, where alpha = d ln k / d ln T_e is the exponent of the
#    power-law rate. MODEL-DERIVED: for a Maxwellian, k = <sigma v> and dk/dT = (<sigma v eps>/T - 3k/2)/T, hence
#    <sigma v eps>/<sigma v> = (3/2 + alpha) T (derivation in INTERSTAGE_MODEL.md section 2). Exact only for Maxwellian
#    electrons and a rate that is a power law in T_e over the case's T_e; refused if 3/2 + alpha < 0.
RECOMBINING_ELECTRON_THERMAL = "recombining_electron_thermal_1.5Te"
RECOMBINING_ELECTRON_RATE_WEIGHTED = "recombining_electron_rate_weighted_(1.5+alpha)Te"
RECOMBINING_ELECTRON_OPTIONS = (RECOMBINING_ELECTRON_THERMAL, RECOMBINING_ELECTRON_RATE_WEIGHTED)
NO_ELECTRON = "none"                                                   # heavy-particle reaction: no electron energy
# Process class each volume reaction declares (checked against its structure; drives the completeness gate).
P_RECOMBINATION = "volume_recombination"
P_IONIZATION = "electron_impact_ionization"
P_CHARGE_TRANSFER = "ion_neutral_charge_transfer"
P_EXCITATION = "electron_impact_excitation"
P_DISSOCIATION = "electron_impact_dissociation"
P_ELASTIC = "electron_elastic_energy_loss"
PROCESS_KINDS = (P_RECOMBINATION, P_IONIZATION, P_CHARGE_TRANSFER, P_EXCITATION, P_DISSOCIATION, P_ELASTIC)
WALL_ATOM_RECOMBINATION = "wall_atom_recombination"
#: Accepted spellings of the dimensionless unit ("-" in this module; "1" in abep_sim/breakeven.py, breakeven_v1).
DIMENSIONLESS_UNITS = ("-", "1")
RATE_VARIABLES = ("electron_temperature_eV", "electron_temperature_K", "ion_axial_energy_eV")
ELECTRON = "e"

# Formula domains stated by the sources (see INTERSTAGE_MODEL.md section 3).
KN_MOLECULAR_MIN = 0.5            # Chiggiato 2014, Table 7: free molecular flow for Kn > 0.5
KN_VISCOUS_MAX = 0.01             # Chiggiato 2014, Table 7: continuous (viscous) flow for Kn < 0.01
LIEBERMAN_H_P_MAX_PA = 0.1 * 133.32   # Lieberman slide 44: "applies for pressures < 100 mTorr in argon";
                                      # 1 Torr = 133.32 Pa (Chiggiato 2014, Table 1)
LEYBOLD_MBAR_PER_PA = 1.0e-2      # 1 mbar = 10^2 Pa (Chiggiato 2014, Table 1)


# ----------------------------------------------------------------------------------------------------- errors
class InterstageError(Exception):
    """Base class: the interstage model refuses the case."""


class InterstageInputError(InterstageError, ValueError):
    """Missing, malformed or physically inconsistent input (no default is ever substituted)."""


class InterstageTBDError(InterstageError):
    """A required input is TBD; the model refuses until it is supplied with a source."""


class InterstageDomainError(InterstageError):
    """An input or formula would be used outside its stated validity domain (no silent extrapolation)."""


# ----------------------------------------------------------------------------------------------- input records
@dataclass(frozen=True)
class Sourced:
    """A numeric input with provenance (docs/EVIDENCE.md: source, evidence class, uncertainty)."""
    value: float
    unit: str
    source: str
    evidence_class: str
    uncertainty: str

    def __post_init__(self):
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise InterstageInputError(f"Sourced.value must be a finite number, got {self.value!r}")
        for name in ("unit", "source", "uncertainty"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise InterstageInputError(f"Sourced.{name} must be a non-empty string (value {self.value!r})")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise InterstageInputError(f"Sourced.evidence_class {self.evidence_class!r} not in {EVIDENCE_CLASSES}")


@dataclass(frozen=True)
class TBD:
    """An input that is not available yet; ``requires`` states what is needed. Using it refuses the solve."""
    requires: str

    def __post_init__(self):
        if not isinstance(self.requires, str) or not self.requires.strip():
            raise InterstageInputError("TBD.requires must say what is required")


@dataclass(frozen=True)
class RateCoefficient:
    """Two-body rate coefficient k = k_ref * (x / x_ref) ** exponent [m^3 s^-1], x = ``variable``.

    ``validity_min`` / ``validity_max`` are the bounds the source states for x (None = the source states no bound on
    that side; at least one bound must be stated). Evaluating outside them raises ``InterstageDomainError``."""
    variable: str
    k_ref_m3_s: float
    x_ref: float
    exponent: float
    validity_min: float | None
    validity_max: float | None
    source: str
    evidence_class: str
    uncertainty: str

    def __post_init__(self):
        if self.variable not in RATE_VARIABLES:
            raise InterstageInputError(f"RateCoefficient.variable {self.variable!r} not in {RATE_VARIABLES}")
        for name in ("k_ref_m3_s", "x_ref", "exponent"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise InterstageInputError(f"RateCoefficient.{name} must be finite, got {v!r}")
        if self.k_ref_m3_s < 0 or self.x_ref <= 0:
            raise InterstageInputError("RateCoefficient needs k_ref_m3_s >= 0 and x_ref > 0")
        if self.validity_min is None and self.validity_max is None:
            raise InterstageInputError("RateCoefficient must state a validity domain (at least one bound)")
        for name in ("validity_min", "validity_max"):
            v = getattr(self, name)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)):
                raise InterstageInputError(f"RateCoefficient.{name} must be finite or None")
        if (self.validity_min is not None and self.validity_max is not None
                and self.validity_min > self.validity_max):
            raise InterstageInputError("RateCoefficient validity_min > validity_max")
        for name in ("source", "uncertainty"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise InterstageInputError(f"RateCoefficient.{name} must be a non-empty string")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise InterstageInputError(f"RateCoefficient.evidence_class {self.evidence_class!r} not in {EVIDENCE_CLASSES}")

    def evaluate(self, x: float, where: str) -> float:
        if (self.validity_min is not None and x < self.validity_min) or \
                (self.validity_max is not None and x > self.validity_max):
            raise InterstageDomainError(
                f"{where}: {self.variable} = {x:.6g} is outside the source-stated validity "
                f"[{self.validity_min}, {self.validity_max}] of '{self.source}'. No extrapolation: supply a rate "
                f"coefficient whose stated domain covers this value (TBD otherwise).")
        return self.k_ref_m3_s * (x / self.x_ref) ** self.exponent


@dataclass(frozen=True)
class Species:
    """A heavy species. ``charge`` = 0 for neutrals, Z >= 1 for ions. ``formation_energy`` [eV] is the internal energy
    relative to the case's ``energy_reference`` (e.g. ionization + dissociation energies); ``mass`` [kg]. Ion masses
    must equal the neutral mass minus Z electron masses (see ``ion_mass_from_neutral``) so that mass closes."""
    name: str
    charge: int
    composition: Mapping[str, int]
    mass: Sourced | TBD
    formation_energy: Sourced | TBD


@dataclass(frozen=True)
class SourceExitState:
    """Pre-ionizer exit state handed to the interstage (produced by the RF / ECR source lanes)."""
    ion_density: Mapping[str, Sourced | TBD]        # m^-3, every ion species of the case (0 allowed)
    ion_axial_speed: Mapping[str, Sourced | TBD]    # m s^-1, every ion species (constant along the duct: assumption)
    electron_temperature: Sourced | TBD             # eV
    neutral_density: Mapping[str, Sourced | TBD]    # m^-3, every neutral species (checked against the flow path)
    neutral_flow: Mapping[str, Sourced | TBD]       # s^-1, every neutral species entering the duct
    neutral_temperature: Sourced | TBD              # K (walls isothermal at this temperature: assumption)


@dataclass(frozen=True)
class CircularDuct:
    length: Sourced | TBD                   # m (0 allowed: no interstage length)
    radius: Sourced | TBD                   # m
    wall_material: str
    axial_magnetic_field: Sourced | TBD     # T (0 = unmagnetized)


@dataclass(frozen=True)
class AnnularDuct:
    length: Sourced | TBD
    inner_radius: Sourced | TBD
    outer_radius: Sourced | TBD
    wall_material: str
    axial_magnetic_field: Sourced | TBD


@dataclass(frozen=True)
class WallModel:
    radial_loss_closure: str                                      # one of RADIAL_LOSS_CLOSURES
    wall_electrical: str                                          # "floating" (the only supported condition)
    neutralization_products: Mapping[str, Sequence[str]]          # ion -> neutral product(s) of wall neutralization
    ion_neutral_cross_section: Mapping[str, Sourced | TBD] | None  # m^2, per ion (lieberman closure only)
    explicit_h: Mapping[str, Sourced | TBD] | None                # -, per ion (explicit_h closure only)


@dataclass(frozen=True)
class NeutralConductanceModel:
    mode: str                                                     # one of NEUTRAL_CONDUCTANCE_MODES
    collision_cross_section: Mapping[str, Sourced | TBD]          # m^2 per neutral species (mean free path, Kn)
    transmission_probability: Sourced | TBD | None                # -, molecular_explicit_transmission only
    explicit_conductance: Mapping[str, Sourced | TBD] | None      # m^3 s^-1 per neutral, explicit_conductance only


@dataclass(frozen=True)
class JunctionModel:
    """Interstage exit -> Hall channel junction. Uncaptured ions leave as plume leakage; the neutral flow splits
    between the Hall-channel path and the leak path in proportion to their free-molecular conductances."""
    ion_capture_fraction: Mapping[str, Sourced | TBD]   # -, per ion species, in [0, 1]
    hall_path_effective_area: Sourced | TBD             # m^2 (area x transmission probability, exit -> space via Hall)
    leak_path_effective_area: Sourced | TBD             # m^2 (area x transmission probability of all leak paths)
    characteristic_dimension: Sourced | TBD             # m (Knudsen-number check at the junction)


@dataclass(frozen=True)
class VolumeReaction:
    reaction_id: str
    reactants: tuple[str, ...]
    products: tuple[str, ...]
    rate: RateCoefficient | TBD
    electron_energy_loss: Sourced | TBD | str   # eV per event, one of RECOMBINING_ELECTRON_OPTIONS, or NO_ELECTRON
    process: str                                # one of PROCESS_KINDS (checked against the reaction's structure)


@dataclass(frozen=True)
class WallAtomRecombination:
    atom: str
    product: str
    probability: Sourced | TBD     # -, recombination probability per wall impact


@dataclass(frozen=True)
class Numerics:
    n_steps: int
    convergence_rtol: float
    conservation_rtol: float
    boundary_rtol: float
    fixed_point_rtol: float
    max_fixed_point_iterations: int
    fixed_point_relaxation: float     # under-relaxation of the neutral-flow profile, 0 < omega <= 1
    fixed_point_anderson_depth: int   # Anderson-acceleration history depth (0 = plain under-relaxed iteration)


@dataclass(frozen=True)
class InterstageCase:
    case_id: str
    architecture: str
    energy_reference: str
    species: tuple[Species, ...]
    source_exit: SourceExitState
    geometry: CircularDuct | AnnularDuct
    wall: WallModel
    reactions: tuple[VolumeReaction, ...]
    wall_atom_recombination: tuple[WallAtomRecombination, ...]
    process_exclusions: Mapping[str, str]
    neutral_conductance: NeutralConductanceModel
    junction: JunctionModel
    electron_energy_closure: str
    numerics: Numerics


# ------------------------------------------------------------------------------------- cited formula functions
def bohm_speed(T_e_eV: float, mass_kg: float, charge: int) -> float:
    """u_B = (Z e T_e / M)^(1/2) [m/s]. Z = 1: Lieberman short course 2015, slide 41. Z > 1: generalization to (Z e T_e / M)^(1/2)
    (isothermal electrons, cold ions; the ion-sound-speed form of the NRL Plasma Formulary - not accessed in this
    session, verify). Model-derived for Z > 1."""
    if T_e_eV < 0 or mass_kg <= 0 or charge < 1:
        raise InterstageInputError("bohm_speed needs T_e >= 0, mass > 0, charge >= 1")
    return math.sqrt(charge * E_CHARGE * T_e_eV / mass_kg)


def bohm_wall_flux(center_density_m3: float, h: float, u_B: float) -> float:
    """Gamma_wall = h n_0 u_B [m^-2 s^-1] (Lieberman short course 2015, slides 41 and 44)."""
    if center_density_m3 < 0 or not (0.0 <= h <= 1.0) or u_B < 0:
        raise InterstageInputError("bohm_wall_flux needs n >= 0, 0 <= h <= 1, u_B >= 0")
    return h * center_density_m3 * u_B


def ion_mean_free_path(neutral_density_m3: float, sigma_i_m2: float) -> float:
    """lambda_i = 1 / (n_g sigma_i) [m] (Lieberman short course 2015, slide 38); inf for n_g = 0."""
    if neutral_density_m3 < 0 or sigma_i_m2 <= 0:
        raise InterstageInputError("ion_mean_free_path needs n_g >= 0 and sigma_i > 0")
    return math.inf if neutral_density_m3 == 0 else 1.0 / (neutral_density_m3 * sigma_i_m2)


def h_radial_lieberman(R_m: float, lambda_i_m: float) -> float:
    """h_R = 0.8 / (4 + R/lambda_i)^(1/2) (Lieberman short course 2015, slide 44; < 100 mTorr in argon)."""
    if R_m <= 0 or lambda_i_m <= 0:
        raise InterstageInputError("h_radial_lieberman needs R > 0 and lambda_i > 0")
    return 0.8 / math.sqrt(4.0 + R_m / lambda_i_m)


def h_axial_lieberman(l_m: float, lambda_i_m: float) -> float:
    """h_l = 0.86 / (3 + l/(2 lambda_i))^(1/2) (Lieberman short course 2015, slides 43-44). Provided for checks; the
    open-ended duct has no axial end walls (its ends are the source exit and the junction)."""
    if l_m <= 0 or lambda_i_m <= 0:
        raise InterstageInputError("h_axial_lieberman needs l > 0 and lambda_i > 0")
    return 0.86 / math.sqrt(3.0 + l_m / (2.0 * lambda_i_m))


def electron_mean_speed(T_e_eV: float) -> float:
    """v_e_bar = (8 e T_e / (pi m))^(1/2) [m/s] (Lieberman short course 2015, slide 48)."""
    if T_e_eV <= 0:
        raise InterstageInputError("electron_mean_speed needs T_e > 0")
    return math.sqrt(8.0 * E_CHARGE * T_e_eV / (math.pi * M_E))


def floating_sheath_potential(T_e_eV: float, edge_ions: Sequence[tuple[int, float, float]]) -> float:
    """Floating-wall sheath voltage V_s [V] from the wall flux balance of Lieberman slide 48,
    sum_s Z_s n_s,edge u_B,s = (1/4) n_e,edge v_e_bar exp(-V_s/T_e), n_e,edge = sum_s Z_s n_s,edge, for ion tuples
    (Z, n_edge [m^-3], u_B [m/s]). One singly charged species reduces exactly to V_s = (T_e/2) ln(M / (2 pi m))
    (slide 48); the several-species form is this module's generalization (model-derived, assumed quasi-neutral edge)."""
    ion_flux = sum(Z * n * u for Z, n, u in edge_ions)
    n_e_edge = sum(Z * n for Z, n, _ in edge_ions)
    if ion_flux <= 0 or n_e_edge <= 0:
        raise InterstageInputError("floating_sheath_potential needs a positive ion wall flux")
    ratio = 0.25 * n_e_edge * electron_mean_speed(T_e_eV) / ion_flux
    V_s = T_e_eV * math.log(ratio)
    if V_s < 0:
        raise InterstageDomainError("negative floating sheath voltage: ion wall flux exceeds the electron random "
                                    "flux, the floating-sheath model of Lieberman slide 48 does not apply")
    return V_s


def mean_molecular_speed(T_K: float, mass_kg: float) -> float:
    """<v> = (8 k_B T / (pi m))^(1/2) [m/s] (Chiggiato 2014, Eq. 3)."""
    if T_K <= 0 or mass_kg <= 0:
        raise InterstageInputError("mean_molecular_speed needs T > 0 and m > 0")
    return math.sqrt(8.0 * K_B * T_K / (math.pi * mass_kg))


def aperture_conductance(area_m2: float, T_K: float, mass_kg: float) -> float:
    """C = (1/4) <v> A [m^3/s], thin wall slot in free-molecular flow (Chiggiato 2014, Eq. 13)."""
    if area_m2 < 0:
        raise InterstageInputError("aperture_conductance needs area >= 0")
    return 0.25 * mean_molecular_speed(T_K, mass_kg) * area_m2


def santeler_transmission_probability(L_m: float, R_m: float) -> float:
    """tau = 1 / (1 + (3L/8R) (1 + 1 / (3 (1 + L/(7R))))) for a circular tube, < 0.7 % error (Santeler 1986, JVST A 4,
    338, doi:10.1116/1.573923, as given by Chiggiato 2014, Eq. 21; see SOURCES['santeler_1986']). tau(0) = 1."""
    if L_m < 0 or R_m <= 0:
        raise InterstageInputError("santeler_transmission_probability needs L >= 0 and R > 0")
    return 1.0 / (1.0 + (3.0 * L_m / (8.0 * R_m)) * (1.0 + 1.0 / (3.0 * (1.0 + L_m / (7.0 * R_m)))))


def duct_conductance_molecular(area_m2: float, tau: float, T_K: float, mass_kg: float) -> float:
    """C = C' A tau = (1/4) <v> A tau [m^3/s] (Chiggiato 2014, Eqs. 19-20)."""
    if not (0.0 <= tau <= 1.0):
        raise InterstageInputError("transmission probability must lie in [0, 1]")
    return aperture_conductance(area_m2, T_K, mass_kg) * tau


def molecular_mean_free_path(total_density_m3: float, sigma_c_m2: float) -> float:
    """lambda = 1 / (sqrt(2) n sigma_c) [m] (Chiggiato 2014, Eq. 7); inf for n = 0."""
    if total_density_m3 < 0 or sigma_c_m2 <= 0:
        raise InterstageInputError("molecular_mean_free_path needs n >= 0 and sigma_c > 0")
    return math.inf if total_density_m3 == 0 else 1.0 / (math.sqrt(2.0) * total_density_m3 * sigma_c_m2)


def knudsen_number(mean_free_path_m: float, dimension_m: float) -> float:
    """Kn = lambda / D (Chiggiato 2014, Eq. 10)."""
    if dimension_m <= 0:
        raise InterstageInputError("knudsen_number needs D > 0")
    return mean_free_path_m / dimension_m


def flow_regime(Kn: float) -> str:
    """Gas-dynamic regime by Knudsen number (Chiggiato 2014, Table 7)."""
    if Kn > KN_MOLECULAR_MIN:
        return "free_molecular"
    if Kn < KN_VISCOUS_MAX:
        return "viscous"
    return "transitional"


def knudsen_conductance_air_20C_leybold(d_m: float, l_m: float, p1_Pa: float, p2_Pa: float) -> float:
    """Knudsen equation for a straight circular pipe, air at 20 C, l >= 10 d (Leybold GmbH, "Fundamentals of Vacuum
    Technology", Part No. 199 90, Edition 2016, Section 1.5.3 a) "Conductance for piping and orifices", Eq. 1.26, p. 16;
    accessed 2026-09-26): C = 135 d^4/l p_bar + 12.1 d^3/l (1 + 192 d p_bar) / (1 + 237 d p_bar) [l/s] with d, l in
    cm and p in mbar. Returned in m^3/s. Refuses outside the stated domain (air at 20 C is the caller's responsibility:
    the formula carries air properties in its coefficients and is not valid for other gases or temperatures)."""
    if d_m <= 0 or l_m <= 0 or p1_Pa < 0 or p2_Pa < 0:
        raise InterstageInputError("knudsen_conductance_air_20C_leybold needs d, l > 0 and p >= 0")
    if l_m < 10.0 * d_m:
        raise InterstageDomainError("Leybold Eq. 1.26 requires l >= 10 d")
    d_cm, l_cm = d_m * 100.0, l_m * 100.0
    p_bar = 0.5 * (p1_Pa + p2_Pa) * LEYBOLD_MBAR_PER_PA
    C_l_s = (135.0 * d_cm ** 4 / l_cm * p_bar
             + 12.1 * d_cm ** 3 / l_cm * (1.0 + 192.0 * d_cm * p_bar) / (1.0 + 237.0 * d_cm * p_bar))
    return C_l_s * 1.0e-3


def gyroradius(mass_kg: float, speed_m_s: float, charge_number: int, B_T: float) -> float:
    """r = v / omega_c with omega_c = |Z| e B / m [m]: definition of the gyroradius
    of a charge Z e in a field B (NRL Plasma Formulary - not accessed in this session, verify). Diagnostic only."""
    if mass_kg <= 0 or speed_m_s < 0 or charge_number == 0 or B_T <= 0:
        raise InterstageInputError("gyroradius needs m > 0, v >= 0, Z != 0, B > 0")
    return speed_m_s * mass_kg / (abs(charge_number) * E_CHARGE * B_T)


def ion_mass_from_neutral(neutral_mass_kg: float, charge: int) -> float:
    """Ion mass = neutral mass - Z m_e (bookkeeping identity; keeps wall neutralization and recombination mass-exact)."""
    return neutral_mass_kg - charge * M_E


# ----------------------------------------------------------------------------------------- catalogue of records
def _cat(value, unit, source, evidence_class, uncertainty):
    return Sourced(value, unit, source, evidence_class, uncertainty)


_NIST_ASD = ("NIST Atomic Spectra Database (NIST SRD 78; Kramida, Ralchenko et al.), ionization energies, "
             "https://doi.org/10.18434/T4W30F, queried 2026-09-26 via physics.nist.gov/cgi-bin/ASD/ie.pl (database "
             "version string not recorded)")
_SHEEHAN = ("Sheehan & St.-Maurice, J. Geophys. Res. Space Phys. 109(A3) (2004), doi:10.1029/2003JA010132 - ABSTRACT ONLY "
            "(read via the Crossref API 2026-09-26; full text not accessed). Rate "
            "converted cm^3 s^-1 -> m^3 s^-1 (x 1e-6)")
_CHIGGIATO = ("P. Chiggiato, 'Vacuum Technology for Ion Sources', CAS-CERN Accelerator School: Ion Sources, "
              "arXiv:1404.0960 (https://arxiv.org/abs/1404.0960, full text accessed 2026-09-26), Table 6")

#: Sourced records a caller may reuse (read-only). TBD entries name what is missing; using one refuses the solve.
CATALOGUE: dict[str, Sourced | RateCoefficient | TBD] = {
    "ionization_energy:N": _cat(14.53413, "eV", _NIST_ASD + " (N I)", "measured", "+/-0.00004 eV (NIST ASD)"),
    "ionization_energy:N+": _cat(29.60125, "eV", _NIST_ASD + " (N II; value printed in brackets '[ ]' by ASD, i.e. not "
                                 "a direct experimental value - verify the bracket definition in the ASD help)", "inferred", "+/-0.00009 eV (NIST ASD)"),
    "ionization_energy:O": _cat(13.618055, "eV", _NIST_ASD + " (O I)", "measured", "+/-0.000007 eV (NIST ASD)"),
    "ionization_energy:O+": _cat(35.12112, "eV", _NIST_ASD + " (O II)", "measured", "+/-0.00006 eV (NIST ASD)"),
    "ionization_energy:Xe": _cat(12.1298437, "eV", _NIST_ASD + " (Xe I)", "measured", "+/-0.0000015 eV (NIST ASD)"),
    "ionization_energy:Xe+": _cat(20.975, "eV", _NIST_ASD + " (Xe II; value printed in brackets '[ ]' by ASD - verify the bracket definition)", "inferred",
                                  "+/-0.004 eV (NIST ASD)"),
    "ionization_energy:N2": _cat(15.581, "eV", "NIST Chemistry WebBook, N2 (CAS 7727-37-9), gas-phase ion energetics, "
                                 "IE (evaluated), https://webbook.nist.gov/cgi/cbook.cgi?ID=C7727379&Mask=20, "
                                 "queried 2026-09-26", "measured", "+/-0.008 eV (WebBook evaluated)"),
    "collision_cross_section:N2": _cat(0.43e-18, "m^2", _CHIGGIATO + " (sigma_c = 0.43 nm^2, elastic, room temperature)",
                                       "inferred", "not stated; the lecture gives no primary reference or method "
                                       "(quantity type assigned conservatively - verify primary reference)"),
    "collision_cross_section:O2": _cat(0.40e-18, "m^2", _CHIGGIATO + " (sigma_c = 0.40 nm^2, elastic, room temperature)",
                                       "inferred", "not stated; the lecture gives no primary reference or method "
                                       "(quantity type assigned conservatively - verify primary reference)"),
    "dissociative_recombination:N2+": RateCoefficient(
        "electron_temperature_K", 2.2e-13, 300.0, -0.39, None, 1200.0, _SHEEHAN + "; ground electronic and vibrational "
        "state N2+, stated for T < 1200 K (lower bound not stated in the abstract)", "inferred",
        "not stated in the abstract (full text not accessed)"),
    "dissociative_recombination:O2+": RateCoefficient(
        "electron_temperature_K", 1.95e-13, 300.0, -0.70, None, 1200.0, _SHEEHAN + "; ground electronic and vibrational "
        "state O2+, stated for T < 1200 K (lower bound not stated in the abstract)", "inferred",
        "not stated in the abstract (full text not accessed)"),
    # --- TBD: required by realistic N2/O2/O/Xe cases, not yet available from an accessed open source ---
    "dissociative_recombination:N2+@Te>1200K": TBD(
        "N2+ dissociative-recombination rate coefficient valid at interstage electron temperatures (> 1200 K, i.e. "
        "> 0.103 eV), e.g. a Maxwellian integral of storage-ring cross sections from an accessed open source"),
    "dissociative_recombination:O2+@Te>1200K": TBD(
        "O2+ dissociative-recombination rate coefficient valid above 1200 K from an accessed open source"),
    "dissociation_energy:N2": TBD("D0(N2) from an accessed evaluated source (e.g. JANAF 0 K enthalpies)"),
    "dissociation_energy:O2": TBD("D0(O2) from an accessed evaluated source"),
    "ionization_energy:O2": TBD("O2 adiabatic ionization energy from an accessed evaluated source"),
    "collision_cross_section:O": TBD("atomic-O gas-kinetic collision cross section for the mean free path"),
    "ion_neutral_cross_section:N2+/N2": TBD("total N2+ - N2 momentum-transfer + charge-transfer cross section at the "
                                            "interstage ion energy, from an accessed open source"),
    "ion_neutral_cross_section:O+/O": TBD("total O+ - O cross section at the interstage ion energy"),
    "ion_neutral_cross_section:Xe+/Xe": TBD("total Xe+ - Xe cross section at the interstage ion energy"),
    "wall_atom_recombination:N": TBD("N-atom wall recombination probability on the chosen interstage wall material"),
    "wall_atom_recombination:O": TBD("O-atom wall recombination probability on the chosen interstage wall material"),
    "junction_ion_capture_fraction": TBD("ion capture fraction of the Vyovrinda interstage/Hall junction (field "
                                         "topology dependent): measurement or a validated 2-D model"),
    "magnetized_cross_field_h": TBD("edge-to-centre ratio for a partially magnetized interstage (between the "
                                    "unmagnetized and strong-B limits): measurement or a validated 2-D model"),
}


def catalogue_entry(key: str) -> Sourced | RateCoefficient:
    """Return a catalogue record; refuses TBD entries and unknown keys."""
    if key not in CATALOGUE:
        raise InterstageInputError(f"unknown catalogue key {key!r}")
    rec = CATALOGUE[key]
    if isinstance(rec, TBD):
        raise InterstageTBDError(f"catalogue entry {key!r} is TBD: requires {rec.requires}")
    return rec


def architecture_has_interstage(architecture: str) -> bool:
    if architecture not in ARCHITECTURES:
        raise InterstageInputError(f"unknown architecture id {architecture!r}; expected one of {ARCHITECTURES}")
    return architecture in ARCHITECTURES_WITH_INTERSTAGE


# ------------------------------------------------------------------------------------------ TBD / provenance walk
def _walk(obj, path):
    """Yield (path, leaf) for every Sourced / TBD / RateCoefficient reachable from a case object."""
    if isinstance(obj, (Sourced, TBD, RateCoefficient)):
        yield path, obj
    elif is_dataclass(obj):
        for f in fields(obj):
            yield from _walk(getattr(obj, f.name), f"{path}.{f.name}" if path else f.name)
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            yield from _walk(v, f"{path}[{k}]")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            key = getattr(v, "name", None) or getattr(v, "reaction_id", None) or str(i)
            yield from _walk(v, f"{path}[{key}]")


def find_tbd(case: InterstageCase) -> list[tuple[str, str]]:
    """All (path, requires) TBD entries in a case."""
    return [(p, leaf.requires) for p, leaf in _walk(case, "") if isinstance(leaf, TBD)]


def provenance(case: InterstageCase) -> list[dict]:
    out = []
    for p, leaf in _walk(case, ""):
        if isinstance(leaf, Sourced):
            out.append({"input": p, "value": leaf.value, "unit": leaf.unit, "source": leaf.source,
                        "evidence_class": leaf.evidence_class, "uncertainty": leaf.uncertainty})
        elif isinstance(leaf, RateCoefficient):
            out.append({"input": p, "value": leaf.k_ref_m3_s, "unit": "m^3 s^-1",
                        "source": leaf.source, "evidence_class": leaf.evidence_class, "uncertainty": leaf.uncertainty,
                        "form": f"k_ref*({leaf.variable}/{leaf.x_ref})^{leaf.exponent}",
                        "validity": [leaf.validity_min, leaf.validity_max]})
    return out


# ------------------------------------------------------------------------------------------------ input checks
def _need(x, path: str, unit: str, *, lo=None, hi=None, lo_open=False) -> float:
    if x is None:
        raise InterstageInputError(f"{path}: missing (the interstage model has no default values)")
    if isinstance(x, TBD):
        raise InterstageTBDError(f"{path}: TBD - requires {x.requires}")
    if not isinstance(x, Sourced):
        raise InterstageInputError(f"{path}: must be a Sourced record, got {type(x).__name__}")
    if x.unit != unit and not (unit in DIMENSIONLESS_UNITS and x.unit in DIMENSIONLESS_UNITS):
        raise InterstageInputError(f"{path}: unit {x.unit!r}, expected {unit!r}")
    v = float(x.value)
    if lo is not None and (v <= lo if lo_open else v < lo):
        raise InterstageInputError(f"{path}: value {v} must be {'>' if lo_open else '>='} {lo}")
    if hi is not None and v > hi:
        raise InterstageInputError(f"{path}: value {v} must be <= {hi}")
    return v


def _need_map(m, keys, path, unit, **kw) -> dict:
    if m is None:
        raise InterstageInputError(f"{path}: missing mapping")
    extra = set(m) - set(keys)
    missing = [k for k in keys if k not in m]
    if missing:
        raise InterstageInputError(f"{path}: missing entries for {missing} (no defaults)")
    if extra:
        raise InterstageInputError(f"{path}: entries for unknown species {sorted(extra)}")
    return {k: _need(m[k], f"{path}[{k}]", unit, **kw) for k in keys}


def _composition_add(acc: dict, comp: Mapping[str, int], sign: int):
    for el, n in comp.items():
        acc[el] = acc.get(el, 0) + sign * n


class _Compiled:
    """Validated, array-form view of a case (built once per solve)."""

    def __init__(self, case: InterstageCase):
        if not isinstance(case, InterstageCase):
            raise InterstageInputError("solve_interstage needs an InterstageCase")
        self.case = case
        if not architecture_has_interstage(case.architecture):
            raise InterstageInputError(
                f"architecture {case.architecture!r} has no interstage (hall_only feeds the Hall channel directly); "
                "eta_transport is undefined, the comparison harness must treat the interstage block as absent")
        tbd = find_tbd(case)
        if tbd:
            raise InterstageTBDError("interstage case has TBD inputs; refusing until they are supplied: "
                                     + "; ".join(f"{p}: requires {r}" for p, r in tbd))
        if not isinstance(case.case_id, str) or not case.case_id.strip():
            raise InterstageInputError("case_id must be a non-empty string")
        if not isinstance(case.energy_reference, str) or not case.energy_reference.strip():
            raise InterstageInputError("energy_reference must state the formation-energy reference state")
        if case.electron_energy_closure not in ELECTRON_ENERGY_CLOSURES:
            raise InterstageTBDError(
                f"electron_energy_closure {case.electron_energy_closure!r} not implemented; available "
                f"{ELECTRON_ENERGY_CLOSURES}. A self-consistent electron energy equation (ambipolar-field work, "
                "field-aligned conduction) is TBD")
        self._numerics(case.numerics)
        self._species(case.species)
        self._state(case.source_exit)
        self._geometry(case.geometry)
        self._wall(case.wall)
        self._reactions(case.reactions)
        self._wall_atom(case.wall_atom_recombination)
        self._completeness(case.process_exclusions)
        self._neutral_conductance(case.neutral_conductance)
        self._junction(case.junction)

    # -- numerics
    def _numerics(self, nm: Numerics):
        if not isinstance(nm, Numerics):
            raise InterstageInputError("numerics: missing Numerics record (no defaults)")
        if isinstance(nm.n_steps, bool) or not isinstance(nm.n_steps, int) or nm.n_steps < 1:
            raise InterstageInputError("numerics.n_steps must be an integer >= 1")
        if isinstance(nm.max_fixed_point_iterations, bool) or not isinstance(nm.max_fixed_point_iterations, int) \
                or nm.max_fixed_point_iterations < 1:
            raise InterstageInputError("numerics.max_fixed_point_iterations must be an integer >= 1")
        if isinstance(nm.fixed_point_anderson_depth, bool) or not isinstance(nm.fixed_point_anderson_depth, int) \
                or nm.fixed_point_anderson_depth < 0:
            raise InterstageInputError("numerics.fixed_point_anderson_depth must be an integer >= 0")
        for name in ("convergence_rtol", "conservation_rtol", "boundary_rtol", "fixed_point_rtol",
                     "fixed_point_relaxation"):
            v = getattr(nm, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise InterstageInputError(f"numerics.{name} must be a finite number > 0")
        if nm.fixed_point_relaxation > 1:
            raise InterstageInputError("numerics.fixed_point_relaxation must lie in (0, 1]")
        self.nm = nm

    # -- species
    def _species(self, species):
        if not species:
            raise InterstageInputError("species: empty")
        names = [s.name for s in species]
        if len(set(names)) != len(names) or ELECTRON in names:
            raise InterstageInputError(f"species names must be unique and not {ELECTRON!r}: {names}")
        self.sp = {}
        for s in species:
            if not isinstance(s.charge, int) or isinstance(s.charge, bool) or s.charge < 0:
                raise InterstageInputError(f"species {s.name}: charge must be an integer >= 0 (negative ions TBD)")
            if not s.composition or any((not isinstance(n, int)) or n < 1 for n in s.composition.values()):
                raise InterstageInputError(f"species {s.name}: composition must map elements to counts >= 1")
            self.sp[s.name] = {
                "Z": s.charge, "comp": dict(s.composition),
                "M": _need(s.mass, f"species[{s.name}].mass", "kg", lo=0.0, lo_open=True),
                "F": _need(s.formation_energy, f"species[{s.name}].formation_energy", "eV")}
        self.ions = [s.name for s in species if s.charge > 0]
        self.neutrals = [s.name for s in species if s.charge == 0]
        if not self.ions:
            raise InterstageInputError("no ion species: a pre-ionizer interstage transports ions (eta undefined)")
        self.elements = sorted({el for s in species for el in s.composition})
        self.Z = np.array([self.sp[i]["Z"] for i in self.ions], float)
        self.Mi = np.array([self.sp[i]["M"] for i in self.ions])
        self.Fi = np.array([self.sp[i]["F"] for i in self.ions])
        self.Mn = np.array([self.sp[k]["M"] for k in self.neutrals])
        self.Fn = np.array([self.sp[k]["F"] for k in self.neutrals])

    # -- state
    def _state(self, st: SourceExitState):
        if not isinstance(st, SourceExitState):
            raise InterstageInputError("source_exit: missing SourceExitState")
        self.n_i0 = _need_map(st.ion_density, self.ions, "source_exit.ion_density", "m^-3", lo=0.0)
        self.v_i = _need_map(st.ion_axial_speed, self.ions, "source_exit.ion_axial_speed", "m s^-1", lo=0.0,
                             lo_open=True)
        self.Te = _need(st.electron_temperature, "source_exit.electron_temperature", "eV", lo=0.0, lo_open=True)
        self.n_n0_supplied = _need_map(st.neutral_density, self.neutrals, "source_exit.neutral_density", "m^-3", lo=0.0)
        self.G0 = _need_map(st.neutral_flow, self.neutrals, "source_exit.neutral_flow", "s^-1", lo=0.0)
        self.Tn = _need(st.neutral_temperature, "source_exit.neutral_temperature", "K", lo=0.0, lo_open=True)
        if sum(self.n_i0.values()) <= 0:
            raise InterstageInputError("source_exit.ion_density: all zero - no entering ion current, eta undefined")
        self.v = np.array([self.v_i[i] for i in self.ions])
        self.KE = 0.5 * self.Mi * self.v ** 2          # J per ion (axial, constant: assumption)

    # -- geometry
    def _geometry(self, g):
        if isinstance(g, CircularDuct):
            R = _need(g.radius, "geometry.radius", "m", lo=0.0, lo_open=True)
            self.kind, self.A, self.P = "circular", math.pi * R ** 2, 2.0 * math.pi * R
            self.Dh, self.radial_scale, self.R = 2.0 * R, R, R
        elif isinstance(g, AnnularDuct):
            ri = _need(g.inner_radius, "geometry.inner_radius", "m", lo=0.0, lo_open=True)
            ro = _need(g.outer_radius, "geometry.outer_radius", "m", lo=0.0, lo_open=True)
            if ro <= ri:
                raise InterstageInputError("geometry: outer_radius must exceed inner_radius")
            self.kind, self.A, self.P = "annular", math.pi * (ro ** 2 - ri ** 2), 2.0 * math.pi * (ro + ri)
            self.Dh = 4.0 * self.A / self.P          # hydraulic diameter 4A/P (assumed characteristic dimension)
            self.radial_scale, self.R = 0.5 * (ro - ri), None
        else:
            raise InterstageInputError("geometry must be CircularDuct or AnnularDuct")
        if not isinstance(g.wall_material, str) or not g.wall_material.strip():
            raise InterstageInputError("geometry.wall_material must be named (label; coefficients are separate inputs)")
        self.L = _need(g.length, "geometry.length", "m", lo=0.0)
        self.B = _need(g.axial_magnetic_field, "geometry.axial_magnetic_field", "T", lo=0.0)

    # -- wall
    def _wall(self, w: WallModel):
        if not isinstance(w, WallModel):
            raise InterstageInputError("wall: missing WallModel")
        if w.wall_electrical not in WALL_ELECTRICAL:
            raise InterstageTBDError(f"wall_electrical {w.wall_electrical!r}: only {WALL_ELECTRICAL} is implemented "
                                     "(biased/conducting walls TBD)")
        if w.radial_loss_closure not in RADIAL_LOSS_CLOSURES:
            raise InterstageInputError(f"radial_loss_closure {w.radial_loss_closure!r} not in {RADIAL_LOSS_CLOSURES}")
        self.h_mode = w.radial_loss_closure
        if self.h_mode == H_LIEBERMAN:
            if self.B > 0:
                raise InterstageDomainError("lieberman_unmagnetized closure requested with B > 0; use the strong-B "
                                            "limit or explicit_h (partially magnetized h is TBD)")
            if self.kind != "circular":
                raise InterstageDomainError("Lieberman h_R is stated for a cylinder of radius R; an annular duct "
                                            "needs explicit_h (TBD)")
            self.sigma_i = np.array(list(_need_map(w.ion_neutral_cross_section, self.ions,
                                                   "wall.ion_neutral_cross_section", "m^2", lo=0.0,
                                                   lo_open=True).values()))
        elif w.ion_neutral_cross_section is not None:
            raise InterstageInputError("wall.ion_neutral_cross_section is only used by the lieberman closure")
        if self.h_mode == H_STRONG_B and self.B <= 0:
            raise InterstageDomainError("strong_axial_B_no_radial_loss requires an axial magnetic field B > 0")
        if self.h_mode == H_EXPLICIT:
            self.h_explicit = np.array(list(_need_map(w.explicit_h, self.ions, "wall.explicit_h", "-", lo=0.0,
                                                      hi=1.0).values()))
        elif w.explicit_h is not None:
            raise InterstageInputError("wall.explicit_h is only used by the explicit_h closure")
        # wall neutralization: every ion must name its neutral product(s), composition-exact, mass-exact
        np_map = w.neutralization_products
        if np_map is None or set(np_map) != set(self.ions):
            raise InterstageInputError("wall.neutralization_products must name the neutral product(s) of every ion")
        self.wall_prod = np.zeros((len(self.ions), len(self.neutrals)))
        for a, ion in enumerate(self.ions):
            prods = list(np_map[ion])
            if not prods or any(p not in self.neutrals for p in prods):
                raise InterstageInputError(f"wall.neutralization_products[{ion}] must be neutral species of the case")
            comp = {}
            _composition_add(comp, self.sp[ion]["comp"], 1)
            mass = self.sp[ion]["M"] + self.sp[ion]["Z"] * M_E
            for p in prods:
                _composition_add(comp, self.sp[p]["comp"], -1)
                mass -= self.sp[p]["M"]
                self.wall_prod[a, self.neutrals.index(p)] += 1
            if any(comp.values()):
                raise InterstageInputError(f"wall neutralization of {ion} -> {prods} does not conserve elements")
            if abs(mass) > self.nm.conservation_rtol * self.sp[ion]["M"]:
                raise InterstageInputError(
                    f"wall neutralization of {ion} -> {prods} does not conserve mass (ion mass + Z m_e vs products, "
                    f"difference {mass:.3e} kg); use ion_mass_from_neutral")
            heat = self.sp[ion]["F"] - sum(self.sp[p]["F"] for p in prods)
            if heat < 0:
                raise InterstageInputError(f"wall neutralization of {ion}: formation energies give negative "
                                           "recombination energy (inconsistent energy reference)")
        self.F_wall_neutralization = np.array(
            [self.sp[i]["F"] - float(self.wall_prod[a] @ self.Fn) for a, i in enumerate(self.ions)])

    # -- reactions
    def _reactions(self, reactions):
        self.rx = []
        ids = set()
        for r in reactions:
            if not isinstance(r, VolumeReaction):
                raise InterstageInputError("reactions must be VolumeReaction records")
            if not r.reaction_id or r.reaction_id in ids:
                raise InterstageInputError(f"reaction id {r.reaction_id!r} empty or duplicated")
            ids.add(r.reaction_id)
            where = f"reaction[{r.reaction_id}]"
            for s in (*r.reactants, *r.products):
                if s != ELECTRON and s not in self.sp:
                    raise InterstageInputError(f"{where}: unknown species {s!r}")
            if len(r.reactants) != 2:
                raise InterstageInputError(f"{where}: only two-body reactions are implemented (three-body TBD)")
            heavy_ions = [s for s in r.reactants if s in self.ions]
            if len(heavy_ions) > 1:
                raise InterstageInputError(f"{where}: ion-ion reactions are not implemented")
            e_in, e_out = r.reactants.count(ELECTRON), r.products.count(ELECTRON)
            if e_in > 1:
                raise InterstageInputError(f"{where}: at most one reactant electron")
            comp, charge, mass = {}, 0, 0.0
            for s in r.reactants:
                if s == ELECTRON:
                    charge -= 1
                    mass += M_E
                else:
                    _composition_add(comp, self.sp[s]["comp"], 1)
                    charge += self.sp[s]["Z"]
                    mass += self.sp[s]["M"]
            for s in r.products:
                if s == ELECTRON:
                    charge += 1
                    mass -= M_E
                else:
                    _composition_add(comp, self.sp[s]["comp"], -1)
                    charge -= self.sp[s]["Z"]
                    mass -= self.sp[s]["M"]
            if any(comp.values()):
                raise InterstageInputError(f"{where}: does not conserve elements")
            if charge != 0:
                raise InterstageInputError(f"{where}: does not conserve charge")
            m_heavy = sum(self.sp[s]["M"] for s in r.reactants if s != ELECTRON)
            if abs(mass) > self.nm.conservation_rtol * m_heavy:
                raise InterstageInputError(f"{where}: does not conserve mass (difference {mass:.3e} kg); ion masses "
                                           "must be neutral mass - Z m_e (ion_mass_from_neutral)")
            if not isinstance(r.rate, RateCoefficient):
                raise InterstageInputError(f"{where}: rate must be a RateCoefficient")
            # domain check up front: T_e and ion speeds are constant along the duct in this closure
            if r.rate.variable == "ion_axial_energy_eV":
                if not heavy_ions:
                    raise InterstageInputError(f"{where}: ion_axial_energy_eV rate needs an ion reactant")
                ion = heavy_ions[0]
                x = self.KE[self.ions.index(ion)] / E_CHARGE
            elif e_in != 1:
                raise InterstageInputError(f"{where}: an electron-temperature rate needs an electron reactant")
            else:
                x = self.Te if r.rate.variable == "electron_temperature_eV" else self.Te * E_CHARGE / K_B
            k = r.rate.evaluate(x, where)
            # declared process class must match the reaction's structure (drives the completeness gate)
            heavy_in = sorted(s for s in r.reactants if s != ELECTRON)
            heavy_out = sorted(s for s in r.products if s != ELECTRON)
            d_q = sum(self.sp[s]["Z"] for s in heavy_out) - sum(self.sp[s]["Z"] for s in heavy_in)
            proc = r.process
            if proc not in PROCESS_KINDS:
                raise InterstageInputError(f"{where}: process {proc!r} not in {PROCESS_KINDS}")
            structure_ok = {
                P_RECOMBINATION: e_in == 1 and d_q < 0,
                P_IONIZATION: e_in == 1 and d_q > 0,
                P_CHARGE_TRANSFER: e_in == 0 and len(heavy_ions) == 1
                and any(s in self.neutrals for s in r.reactants),
                P_EXCITATION: e_in == 1 and e_out == 1 and heavy_out == heavy_in,
                P_ELASTIC: e_in == 1 and e_out == 1 and heavy_out == heavy_in,
                P_DISSOCIATION: e_in == 1 and e_out == 1 and d_q == 0 and len(heavy_out) >= 2 and heavy_out != heavy_in,
            }[proc]
            if not structure_ok:
                raise InterstageInputError(f"{where}: declared process {proc!r} does not match the reaction "
                                           f"{r.reactants} -> {r.products}")
            # electron energy loss per event
            eel = r.electron_energy_loss
            eel_basis = None
            if e_in == 0:
                if eel != NO_ELECTRON:
                    raise InterstageInputError(f"{where}: heavy-particle reaction must declare electron_energy_loss "
                                               f"= {NO_ELECTRON!r}")
                eps_e = 0.0
                eel_basis = NO_ELECTRON
            elif isinstance(eel, str) and eel in RECOMBINING_ELECTRON_OPTIONS:
                if e_out != 0 or proc != P_RECOMBINATION:
                    raise InterstageInputError(f"{where}: {eel} only for electron-consuming recombination reactions")
                if eel == RECOMBINING_ELECTRON_THERMAL:
                    eps_e = 1.5 * self.Te
                    eel_basis = "assumed: (3/2) T_e (mean Maxwellian energy; ignores the cross-section energy dependence)"
                else:
                    if r.rate.variable not in ("electron_temperature_eV", "electron_temperature_K"):
                        raise InterstageInputError(f"{where}: {eel} needs a rate that is a power law in T_e")
                    if 1.5 + r.rate.exponent < 0:
                        raise InterstageDomainError(f"{where}: {eel} gives (3/2 + alpha) = {1.5 + r.rate.exponent:.4g} "
                                                    "< 0; the Maxwellian power-law relation does not apply")
                    eps_e = (1.5 + r.rate.exponent) * self.Te
                    eel_basis = (f"model-derived: (3/2 + alpha) T_e with alpha = {r.rate.exponent:g} "
                                 "(Maxwellian electrons, power-law rate)")
            elif isinstance(eel, (Sourced, TBD)) or eel is None:
                eps_e = _need(eel, f"{where}.electron_energy_loss", "eV", lo=0.0)
                eel_basis = f"{eel.evidence_class}: {eel.source}"
            else:
                raise InterstageInputError(f"{where}: electron_energy_loss must be Sourced (eV), one of "
                                           f"{RECOMBINING_ELECTRON_OPTIONS} or {NO_ELECTRON!r}")
            d_ion = np.zeros(len(self.ions))
            d_neu = np.zeros(len(self.neutrals))
            for s in r.reactants:
                if s in self.ions:
                    d_ion[self.ions.index(s)] -= 1
                elif s in self.neutrals:
                    d_neu[self.neutrals.index(s)] -= 1
            for s in r.products:
                if s in self.ions:
                    d_ion[self.ions.index(s)] += 1
                elif s in self.neutrals:
                    d_neu[self.neutrals.index(s)] += 1
            prod_ion_KE = sum(self.KE[self.ions.index(s)] for s in r.products if s in self.ions)
            react_ion_KE = sum(self.KE[self.ions.index(s)] for s in r.reactants if s in self.ions)
            F_react = sum(self.sp[s]["F"] for s in r.reactants if s != ELECTRON)
            F_prod = sum(self.sp[s]["F"] for s in r.products if s != ELECTRON)
            # heat/radiation released per event [J]: formation-energy decrease + consumed ion kinetic energy +
            # energy taken from the electron fluid for the inelastic process (see INTERSTAGE_MODEL.md, energy ledger)
            q = (F_react - F_prod + eps_e) * E_CHARGE + react_ion_KE
            scale = (abs(F_react) + abs(F_prod) + eps_e) * E_CHARGE + react_ion_KE
            if q < -1e-12 * max(scale, 1e-30):
                raise InterstageInputError(
                    f"{where}: energy inconsistent - declared electron energy loss {eps_e:.6g} eV does not cover the "
                    f"endothermicity {F_prod - F_react:.6g} eV (net heat {q / E_CHARGE:.6g} eV per event)")
            self.rx.append({
                "id": r.reaction_id, "k": k, "reactants": list(r.reactants), "d_ion": d_ion, "d_neu": d_neu,
                "idx": [("e", -1) if s == ELECTRON else ("i", self.ions.index(s)) if s in self.ions
                        else ("n", self.neutrals.index(s)) for s in r.reactants],
                "d_charge": float(d_ion @ self.Z), "eps_e_J": eps_e * E_CHARGE, "prod_ion_KE": prod_ion_KE,
                "heat_J": q, "e_in": e_in, "rate": r.rate, "process": proc,
                "heavy_reactants": heavy_in, "eps_e_eV": eps_e, "eel_basis": eel_basis})

    def _wall_atom(self, recs):
        self.wr = []
        for w in recs:
            if not isinstance(w, WallAtomRecombination):
                raise InterstageInputError("wall_atom_recombination must be WallAtomRecombination records")
            if w.atom not in self.neutrals or w.product not in self.neutrals:
                raise InterstageInputError(f"wall atom recombination {w.atom}->{w.product}: neutral species required")
            comp = {}
            _composition_add(comp, self.sp[w.atom]["comp"], 2)
            _composition_add(comp, self.sp[w.product]["comp"], -1)
            if any(comp.values()) or sum(self.sp[w.atom]["comp"].values()) != 1:
                raise InterstageInputError(f"wall atom recombination: 2 {w.atom} -> {w.product} must conserve elements")
            if abs(2 * self.sp[w.atom]["M"] - self.sp[w.product]["M"]) > self.nm.conservation_rtol * self.sp[w.product]["M"]:
                raise InterstageInputError(f"wall atom recombination 2 {w.atom} -> {w.product} does not conserve mass")
            gamma = _need(w.probability, f"wall_atom_recombination[{w.atom}].probability", "-", lo=0.0, hi=1.0)
            heat = 2 * self.sp[w.atom]["F"] - self.sp[w.product]["F"]
            if heat < 0:
                raise InterstageInputError(f"wall atom recombination {w.atom}: negative heat release (energy reference)")
            self.wr.append({"atom": self.neutrals.index(w.atom), "prod": self.neutrals.index(w.product),
                            "gamma": gamma, "heat_J": heat * E_CHARGE, "name": w.atom,
                            "vbar": mean_molecular_speed(self.Tn, self.sp[w.atom]["M"])})

    # -- process completeness: nothing may be omitted silently
    def required_processes(self) -> list[str]:
        """Process classes every case must model (a reaction declaring that ``process`` with the species as a heavy
        reactant) or explicitly exclude with a justification. The electron-energy-loss classes (excitation, elastic,
        dissociation) are included because ``electron_heat_from_source_W`` is otherwise under-counted silently."""
        molecular = [s for s in self.ions + self.neutrals if sum(self.sp[s]["comp"].values()) >= 2]
        req = [f"{P_RECOMBINATION}:{i}" for i in self.ions]
        req += [f"{P_IONIZATION}:{s}" for s in self.ions + self.neutrals]
        if self.neutrals:
            req += [f"{P_CHARGE_TRANSFER}:{i}" for i in self.ions]
        req += [f"{P_EXCITATION}:{s}" for s in self.ions + self.neutrals]
        req += [f"{P_ELASTIC}:{k}" for k in self.neutrals]
        req += [f"{P_DISSOCIATION}:{s}" for s in molecular]
        req += [f"{WALL_ATOM_RECOMBINATION}:{k}" for k in self.neutrals if sum(self.sp[k]["comp"].values()) == 1]
        return req

    def _addressed(self, key: str) -> bool:
        kind, sp = key.split(":", 1)
        if kind == WALL_ATOM_RECOMBINATION:
            return any(w["name"] == sp for w in self.wr)
        return any(r["process"] == kind and sp in r["heavy_reactants"] for r in self.rx)

    def _completeness(self, exclusions):
        if exclusions is None:
            raise InterstageInputError("process_exclusions: missing (use an empty mapping if nothing is excluded)")
        req = self.required_processes()
        for k, why in exclusions.items():
            if k not in req:
                raise InterstageInputError(f"process_exclusions[{k}]: not a required process key {req}")
            if not isinstance(why, str) or not why.strip():
                raise InterstageInputError(f"process_exclusions[{k}]: justification (with source or bound) required")
        missing = [k for k in req if not self._addressed(k) and k not in exclusions]
        if missing:
            raise InterstageTBDError(
                "processes neither modelled nor explicitly excluded (TBD: supply a sourced rate or an exclusion "
                "with a sourced justification): " + ", ".join(missing))
        both = [k for k in exclusions if self._addressed(k)]
        if both:
            raise InterstageInputError(f"processes both modelled and excluded: {both}")
        self.exclusions = dict(exclusions)

    # -- neutral conductance
    def _neutral_conductance(self, nc: NeutralConductanceModel):
        if not isinstance(nc, NeutralConductanceModel):
            raise InterstageInputError("neutral_conductance: missing NeutralConductanceModel")
        if nc.mode not in NEUTRAL_CONDUCTANCE_MODES:
            raise InterstageInputError(f"neutral_conductance.mode {nc.mode!r} not in {NEUTRAL_CONDUCTANCE_MODES}")
        self.nc_mode = nc.mode
        self.sigma_c = np.array(list(_need_map(nc.collision_cross_section, self.neutrals,
                                               "neutral_conductance.collision_cross_section", "m^2", lo=0.0,
                                               lo_open=True).values())) if self.neutrals else np.zeros(0)
        if nc.mode == NC_SANTELER:
            if self.kind != "circular":
                raise InterstageDomainError("Santeler transmission probability is stated for circular tubes; use "
                                            "molecular_explicit_transmission for an annular duct")
            if nc.transmission_probability is not None or nc.explicit_conductance is not None:
                raise InterstageInputError("molecular_santeler_circular takes no transmission/conductance input")
            self.tau = santeler_transmission_probability(self.L, self.R)
            self.tau_source = "Santeler 1986 (doi:10.1116/1.573923) via Chiggiato 2014 Eq. 21 (model-derived)"
        elif nc.mode == NC_TRANSMISSION:
            if nc.explicit_conductance is not None:
                raise InterstageInputError("molecular_explicit_transmission takes no explicit_conductance")
            self.tau = _need(nc.transmission_probability, "neutral_conductance.transmission_probability", "-",
                             lo=0.0, hi=1.0)
            if self.L == 0 and self.tau != 1.0:
                raise InterstageInputError("a zero-length duct has transmission probability 1")
            self.tau_source = nc.transmission_probability.source
        else:
            if nc.transmission_probability is not None:
                raise InterstageInputError("explicit_conductance takes no transmission_probability")
            self.tau, self.tau_source = None, None
            self.C_explicit = np.array(list(_need_map(nc.explicit_conductance, self.neutrals,
                                                      "neutral_conductance.explicit_conductance", "m^3 s^-1",
                                                      lo=0.0).values()))
        if self.tau is not None:
            self.C_duct = np.array([duct_conductance_molecular(self.A, self.tau, self.Tn, m) for m in self.Mn])
        else:
            self.C_duct = self.C_explicit

    # -- junction
    def _junction(self, j: JunctionModel):
        if not isinstance(j, JunctionModel):
            raise InterstageInputError("junction: missing JunctionModel")
        self.f_cap = np.array(list(_need_map(j.ion_capture_fraction, self.ions, "junction.ion_capture_fraction", "-",
                                             lo=0.0, hi=1.0).values()))
        self.A_hall = _need(j.hall_path_effective_area, "junction.hall_path_effective_area", "m^2", lo=0.0)
        self.A_leak = _need(j.leak_path_effective_area, "junction.leak_path_effective_area", "m^2", lo=0.0)
        self.D_junction = _need(j.characteristic_dimension, "junction.characteristic_dimension", "m", lo=0.0,
                                lo_open=True)
        self.C_J = np.array([aperture_conductance(self.A_hall + self.A_leak, self.Tn, m) for m in self.Mn])
        tot = self.A_hall + self.A_leak
        self.leak_fraction = (self.A_leak / tot) if tot > 0 else None


# ------------------------------------------------------------------------------------------------- the solver
class _Infeasible(Exception):
    pass


class _ModelError(Exception):
    pass


def _layout(c: _Compiled):
    nI, nK, nR, nW = len(c.ions), len(c.neutrals), len(c.rx), len(c.wr)
    idx = {}
    o = 0
    for name, n in (("N", nI), ("G", nK), ("wall", nI), ("react", nR), ("wallrec", nW)):
        idx[name] = slice(o, o + n)
        o += n
    for name in ("E_wall_ion_kin", "E_wall_ion_pot", "E_wall_neut", "E_wall_elec", "E_wall_atom", "E_react", "E_cond"):
        idx[name] = o
        o += 1
    return idx, o


def _pressure_profile(c: _Compiled, zg: np.ndarray, Gprof: np.ndarray, strict: bool = True) -> np.ndarray:
    """Partial pressures p_k(z_j) [Pa] for a net-flow profile Gprof[k, j] [s^-1]: p_k(L) = Q_k(L)/C_J,k (downstream
    back-pressure zero), p_k(z) = p_k(L) + int_z^L Q_k dz' / (C_duct,k L) (duct resistance distributed uniformly, i.e.
    one-dimensional free-molecular diffusion). Entry boundary: the net flow of species k across the source-exit plane
    is the supplied G_k(0) (zero for a species the source does not emit); p_k(0) is whatever the integral gives, so a
    species formed in the duct has p_k(0) > 0 with zero net entry flow (a reflecting entry: no net back-flow into the
    source). Inside the duct a species may flow upstream (Q_k < 0 locally, e.g. a product formed downstream diffusing
    back); its partial pressure must stay >= 0 and its net flow into the junction must be >= 0. The integral is the
    end-corrected (Euler-Maclaurin) trapezoidal rule on the RK4 grid, O(dz^4), so p_k(0) still carries a quadrature
    error; its step-doubling change is reported (diagnostics.p_entry_step_doubling_rel_change) and ``boundary_rtol``
    must not be set below it. Source lanes must take the entry densities from ``flow_path_entry_densities`` (same grid,
    same quadrature), not from an independent calculation, or the boundary gate can reject an otherwise exact state. A zero-length duct (two coincident grid points) is its entrance aperture: p(0) = p(L) + Q/C_duct.
    ``strict=False`` is used for intermediate fixed-point iterates only (non-physical iterates are clipped, not
    accepted); the converged profile is always re-checked with ``strict=True``."""
    nK, nz = Gprof.shape
    p = np.zeros((nK, nz))
    for k in range(nK):
        Q = Gprof[k] * K_B * c.Tn
        q_scale = max(float(np.max(np.abs(Q))), 1e-300)
        if strict and Q[-1] < -1e-12 * q_scale:
            raise _Infeasible(f"net flow of {c.neutrals[k]} into the junction is negative: the duct consumes more "
                              "than the supplied entry flow provides (no steady state with zero back-pressure)")
        q_out = max(Q[-1], 0.0)
        if c.C_J[k] == 0:
            if q_out > 1e-12 * q_scale:
                raise _Infeasible(f"junction closed to neutrals (hall + leak effective area 0) but {c.neutrals[k]} "
                                  "arrives at the junction: no steady state")
            p_out = 0.0
        else:
            p_out = q_out / c.C_J[k]
        if c.L == 0:
            if Q[0] > 0 and c.C_duct[k] == 0:
                raise _Infeasible(f"duct conductance 0 for {c.neutrals[k]} with positive throughput")
            p[k, :] = p_out
            p[k, 0] = p_out + (Q[0] / c.C_duct[k] if Q[0] != 0 else 0.0)
        elif c.C_duct[k] == 0:
            if np.any(np.abs(Q) > 1e-12 * q_scale):
                raise _Infeasible(f"closed duct (conductance 0) for {c.neutrals[k]} with nonzero throughput")
            p[k, :] = p_out
        else:
            # end-corrected trapezoid (Euler-Maclaurin, uniform grid): int_z^L Q = T(z) - dz^2/12 (Q'(L) - Q'(z))
            # + O(dz^4); Q' by second-order finite differences of the grid profile (first order on a 2-point grid)
            dz = zg[1] - zg[0]
            seg = 0.5 * (Q[1:] + Q[:-1]) * dz
            tail = np.concatenate([np.cumsum(seg[::-1])[::-1], [0.0]])
            dQ = np.gradient(Q, zg, edge_order=2 if len(zg) >= 3 else 1)
            tail = tail - dz * dz / 12.0 * (dQ[-1] - dQ)
            p[k] = p_out + tail / (c.C_duct[k] * c.L)
        p_scale = max(float(np.max(np.abs(p[k]))), 1e-300)
        if strict and np.any(p[k] < -1e-9 * p_scale):
            raise _ModelError(f"negative partial pressure of {c.neutrals[k]} in the duct (upstream diffusion exceeds "
                              "what the flow path supports; refine numerics or revisit the entry flows)")
        p[k] = np.maximum(p[k], 0.0)
    return p


def _derivs(c: _Compiled, y: np.ndarray, pz: np.ndarray, idx) -> tuple[np.ndarray, dict]:
    nI = len(c.ions)
    N = y[idx["N"]]
    n_i = N / (c.v * c.A)
    n_e = float(n_i @ c.Z)
    n_n = pz / (K_B * c.Tn) if len(c.neutrals) else np.zeros(0)
    u_B = np.sqrt(c.Z * E_CHARGE * c.Te / c.Mi)
    if c.h_mode == H_STRONG_B:
        h = np.zeros(nI)
    elif c.h_mode == H_EXPLICIT:
        h = c.h_explicit
    else:
        n_g = float(n_n.sum())
        # h_R = 0.8 / (4 + R / lambda_i)^(1/2), lambda_i = 1/(n_g sigma_i) (vectorized h_radial_lieberman)
        h = 0.8 / np.sqrt(4.0 + c.R * n_g * c.sigma_i)
    Lw = h * n_i * u_B * c.P                       # ions lost to the side wall per unit length [s^-1 m^-1]
    if float(Lw @ c.Z) > 0:
        V_s = floating_sheath_potential(c.Te, [(int(Z), hh * n, u) for Z, hh, n, u in zip(c.Z, h, n_i, u_B)
                                                if hh * n > 0])
    else:
        V_s = 0.0
    dy = np.zeros_like(y)
    dN = -Lw.copy()
    dG = Lw @ c.wall_prod if len(c.neutrals) else np.zeros(0)
    Le = float(np.sum(Lw * c.Z)) * E_CHARGE * (2.5 * c.Te + V_s)   # electrons 2 T_e + ion energy (T_e/2 + V_s), x Z
    react_rates = np.zeros(len(c.rx))
    heat_react = 0.0
    for r_i, r in enumerate(c.rx):
        rate = r["k"] * c.A                          # events per unit length
        for kind, a in r["idx"]:
            rate *= n_e if kind == "e" else (n_i[a] if kind == "i" else n_n[a])
        react_rates[r_i] = rate
        dN += rate * r["d_ion"]
        if len(c.neutrals):
            dG += rate * r["d_neu"]
        Le += rate * (r["eps_e_J"] + r["prod_ion_KE"])
        heat_react += rate * r["heat_J"]
    wallrec = np.zeros(len(c.wr))
    heat_atom = 0.0
    for j, w in enumerate(c.wr):
        k = w["atom"]
        imp = 0.25 * n_n[k] * w["vbar"] * c.P                              # impingement per unit length
        ev = 0.5 * w["gamma"] * imp                                       # molecules formed per unit length
        wallrec[j] = ev
        dG[k] -= 2.0 * ev
        dG[w["prod"]] += ev
        heat_atom += ev * w["heat_J"]
    dN_e = float(dN @ c.Z)
    dy[idx["N"]] = dN
    if len(c.neutrals):
        dy[idx["G"]] = dG
    dy[idx["wall"]] = Lw
    dy[idx["react"]] = react_rates
    dy[idx["wallrec"]] = wallrec
    dy[idx["E_wall_ion_kin"]] = float(Lw @ c.KE)
    dy[idx["E_wall_ion_pot"]] = float(np.sum(Lw * c.Z)) * E_CHARGE * (0.5 * c.Te + V_s)
    dy[idx["E_wall_neut"]] = float(Lw @ c.F_wall_neutralization) * E_CHARGE
    dy[idx["E_wall_elec"]] = float(np.sum(Lw * c.Z)) * E_CHARGE * 2.0 * c.Te
    dy[idx["E_wall_atom"]] = heat_atom
    dy[idx["E_react"]] = heat_react
    dy[idx["E_cond"]] = 2.5 * E_CHARGE * c.Te * dN_e + Le     # isothermal: heat conducted from the source
    return dy, {"h": h, "u_B": u_B, "V_s": V_s, "n_i": n_i, "n_e": n_e}


def _anderson_update(x: np.ndarray, gx: np.ndarray, hist_x: list, hist_f: list, depth: int, omega: float):
    """Next iterate of the fixed point x = g(x) (neutral-flow profile). depth = 0: under-relaxed Picard,
    x' = omega g(x) + (1 - omega) x. depth > 0: Anderson acceleration (Walker & Ni, SIAM J. Numer. Anal. 49(4) (2011)
    1715-1735, doi:10.1137/10078356X; bibliographic data checked via Crossref 2026-09-26) with damping omega. Only the iterate changes;
    acceptance is always the true fixed-point residual test in ``_integrate`` (no silent acceptance)."""
    f = (gx - x).ravel()
    if depth == 0:
        return omega * gx + (1.0 - omega) * x
    hist_x.append(x.ravel().copy())
    hist_f.append(f.copy())
    if len(hist_x) > depth + 1:
        del hist_x[0], hist_f[0]
    if len(hist_x) == 1:
        return omega * gx + (1.0 - omega) * x
    dX = np.diff(np.array(hist_x), axis=0).T         # columns x_{j+1} - x_j
    dF = np.diff(np.array(hist_f), axis=0).T
    scale = np.linalg.norm(dF, axis=0)
    keep = scale > 0
    if not np.any(keep):
        return omega * gx + (1.0 - omega) * x
    dX, dF, scale = dX[:, keep], dF[:, keep], scale[keep]
    gamma, *_ = np.linalg.lstsq(dF / scale, f, rcond=None)
    gamma = gamma / scale
    x_bar = x.ravel() - dX @ gamma
    f_bar = f - dF @ gamma
    return (x_bar + omega * f_bar).reshape(x.shape)


def _integrate(c: _Compiled, n_steps: int):
    idx, size = _layout(c)
    y0 = np.zeros(size)
    N0 = np.array([c.n_i0[i] * c.v_i[i] * c.A for i in c.ions])
    y0[idx["N"]] = N0
    if c.neutrals:
        y0[idx["G"]] = np.array([c.G0[k] for k in c.neutrals])
    zg = np.linspace(0.0, c.L, n_steps + 1) if c.L > 0 else np.zeros(2)   # L = 0: entry and exit planes coincide
    nK = len(c.neutrals)
    Gprof = np.repeat(y0[idx["G"]][:, None], len(zg), axis=1) if nK else np.zeros((0, len(zg)))
    # No Knudsen gate on this entry-flow estimate: the domain is judged on the converged profile only
    # (_domain_gates), so a case whose converged state is in-domain is never refused on a provisional iterate.
    history = None
    converged = False
    it = 0
    omega = c.nm.fixed_point_relaxation
    depth = c.nm.fixed_point_anderson_depth
    hist_x, hist_f = [], []            # Anderson history (flattened neutral-flow profiles and their residuals)
    for it in range(1, c.nm.max_fixed_point_iterations + 1):
        p = _pressure_profile(c, zg, Gprof, strict=False) if nK else np.zeros((0, len(zg)))
        # dp_k/dz = -Q_k / (C_duct,k L) (the pressure-profile equation), used for cubic-Hermite mid-step pressures so
        # that the neutral coupling keeps the RK4 order (linear interpolation would make it O(dz^2))
        dpdz = np.zeros_like(p)
        if nK and c.L > 0:
            for k in range(nK):
                if c.C_duct[k] > 0:
                    dpdz[k] = -Gprof[k] * K_B * c.Tn / (c.C_duct[k] * c.L)
        Y = np.zeros((len(zg), size))
        Y[0] = y0
        diag0 = None
        for j in range(len(zg) - 1):
            dz = zg[j + 1] - zg[j]
            pa, pb = p[:, j], p[:, j + 1]
            pm = np.maximum(0.5 * (pa + pb) + dz / 8.0 * (dpdz[:, j] - dpdz[:, j + 1]), 0.0)
            yj = Y[j]
            with np.errstate(over="ignore", invalid="ignore"):     # blow-up is detected explicitly below
                k1, d = _derivs(c, yj, pa, idx)
                if j == 0:
                    diag0 = d
                k2, _ = _derivs(c, yj + 0.5 * dz * k1, pm, idx)
                k3, _ = _derivs(c, yj + 0.5 * dz * k2, pm, idx)
                k4, _ = _derivs(c, yj + dz * k3, pb, idx)
                Y[j + 1] = yj + dz / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            if not np.all(np.isfinite(Y[j + 1])):
                raise _ModelError(f"non-finite state at z = {zg[j + 1]:.6g} m (integration blew up; refine "
                                  "numerics.n_steps or check the rate inputs)")
        if diag0 is None:
            _, diag0 = _derivs(c, y0, p[:, 0], idx)
        _, diagL = _derivs(c, Y[-1], p[:, -1], idx)
        if np.any(Y[:, idx["N"]] < -1e-12 * float(N0.sum())):
            raise _ModelError("negative ion flow during integration (refine numerics.n_steps)")
        history = (zg, Y, p, diag0, diagL)
        if not nK:
            converged = True
            break
        Gnew = Y[:, idx["G"]].T.copy()      # may be locally negative (upstream diffusion inside the duct)
        # true fixed-point residual: pressures implied by the new flows vs the pressures this trajectory used
        p_check = _pressure_profile(c, zg, Gnew, strict=False)
        # scale-safe: an all-zero trial profile (e.g. zero neutral entry flow) cannot be accepted by a 0/0 or x/tiny
        p_scale = max(float(p[:, 0].sum()), float(p_check[:, 0].sum()), float(np.max(np.abs(p_check))),
                      float(np.max(np.abs(p))))
        if p_scale == 0.0:
            residual = 0.0                  # no neutrals anywhere in either profile: trivially self-consistent
        else:
            residual = float(np.max(np.abs(p_check - p))) / p_scale
        if not math.isfinite(residual):
            raise _ModelError("non-finite neutral-pressure fixed-point residual")
        if residual <= c.nm.fixed_point_rtol:
            _pressure_profile(c, zg, Gnew, strict=True)       # the accepted state must be physical
            converged = True
            break
        Gprof = _anderson_update(Gprof, Gnew, hist_x, hist_f, depth, omega)
    if not converged:
        raise _ModelError(f"neutral pressure fixed point not converged in {c.nm.max_fixed_point_iterations} "
                          f"iterations (fixed_point_rtol {c.nm.fixed_point_rtol}, relaxation {omega})")
    zg, Y, p, diag0, diagL = history
    # reported pressures are the ones the accepted trajectory used (self-consistent within fixed_point_rtol)
    return {"z": zg, "Y": Y, "p": p, "idx": idx, "N0": N0, "diag0": diag0, "diagL": diagL, "iterations": it}


def _json_safe(x):
    """Replace non-finite floats by None (NaN/inf are not JSON numbers and must never be reported as values)."""
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    if isinstance(x, (float, np.floating)) and not math.isfinite(float(x)):
        return None
    return x


def _null_result(c_or_case, status: str, reason: str, diagnostics: dict | None = None) -> dict:
    case = c_or_case.case if isinstance(c_or_case, _Compiled) else c_or_case
    res = _empty_result(case)
    res.update(status=status, status_reason=reason, converged=False, diagnostics=_json_safe(diagnostics or {}))
    return res


MILESTONE_SUPPORT = {
    "A": ("supports conditional selection: turns 'rf_hall / ecr_hall is baseline provided the interstage delivers "
          "eta_transport >= eta_transport_required (abep_sim/breakeven.py, breakeven_v1: place_evidence()['eta_transport_min'])' into a computable, input-traceable condition "
          "and lists the TBD inputs that condition depends on"),
    "B": ("not yet: needs an admitted Hall transport closure (for eta_transport_required), sourced rate coefficients "
          "valid at the interstage T_e (dissociative recombination above 1200 K, ion-neutral cross sections), a "
          "magnetized wall-flux closure or measurement, junction capture data and a transitional-flow conductance for "
          "the actual gas"),
    "C": ("not yet: the wall-heat and ion-wall-energy outputs feed abep_sim/thermal_life.py (thermal load, wall "
          "erosion) and the energy ledger feeds bus_power_boundary_v1 (rf_source / ecr_source); both need the "
          "physics-backed inputs of milestone B and hardware data"),
}

NOT_A_COMPARISON = ("interstage_v1 computes the transfer efficiency of one pre-ionizer architecture for stated inputs; "
                    "it does not rank or select architectures and makes no Hall performance claim")


def _empty_result(case) -> dict:
    return {
        "schema": SCHEMA_ID, "model_version": MODEL_VERSION, "case_id": getattr(case, "case_id", None),
        "architecture": getattr(case, "architecture", None), "status": None, "status_reason": "",
        "converged": False, "eta_transport": None, "eta_duct": None, "eta_junction": None,
        "eta_transport_particle": None, "eta_transport_mass": None, "mass_delivery_fraction": None,
        "ions": None, "neutrals": None, "charge_state_fractions": None, "neutral_transport": None,
        "reactions": None, "wall": None, "energy_ledger_W": None, "conservation": None, "numerics": None,
        "profiles": None, "provenance": provenance(case) if isinstance(case, InterstageCase) else [],
        "process_exclusions": dict(getattr(case, "process_exclusions", {}) or {}),
        "assumptions": list(ASSUMPTIONS), "milestone_support": dict(MILESTONE_SUPPORT),
        "not_a_comparison": NOT_A_COMPARISON, "diagnostics": {},
    }


ASSUMPTIONS = (
    "steady quasi-1-D plug flow; each ion species moves at its supplied constant axial speed (no axial field)",
    "cold ions (T_i not tracked); each ion species reaches its own Bohm speed (Z e T_e / M)^(1/2) at the sheath edge",
    "isothermal electrons: T_e held at the source-exit value by heat conducted from the source; the conducted power is "
    "reported (electron_heat_from_source_W)",
    "quasi-neutral, current-free (floating dielectric wall): Z electrons leave with every wall-lost ion of charge Z",
    "wall-lost ions are neutralized to the declared neutral product(s), which re-enter the neutral flow at T_n",
    "neutral thermal enthalpy is held by isothermal walls at T_n and is not part of the energy ledger",
    "neutral species flow independently (free-molecular); the duct resistance 1/C is distributed uniformly along "
    "its length; downstream back-pressure of the Hall and leak paths is zero",
    "conductances in series/parallel combine as for elements separated by volumes (Chiggiato 2014 Eqs. 26-28); "
    "a transmission-probability combination for directly joined elements is not implemented",
    "entry boundary: the net flow of each neutral species across the source-exit plane is the supplied neutral_flow "
    "(zero for species the source does not emit); species formed in the duct may have nonzero entry partial pressure "
    "but no net back-flow into the source (reflecting entry); inside the duct local upstream flow is allowed",
    "Gamma_wall = h n u_B uses the plug-flow (cross-section-average) density N/(v A) in place of the centre density n_0 "
    "of Lieberman slides 41/44 (assumed; the h values of the closures refer to n_0, so the wall flux is biased by "
    "the ratio of centre to mean density, not modelled)",
    "Lieberman h_R (slide 44) is the edge-to-centre ratio of an ionization-sustained low-pressure discharge in argon; "
    "applying it to a drifting, decaying (source-free) interstage plasma and to other gases is an extrapolation of both "
    "configuration and gas (model-derived applicability, not validated)",
    "electron energy removed per recombination: declared per reaction, either (3/2) T_e (assumed; biased high for rate "
    "exponents alpha < 0) or (3/2 + alpha) T_e (model-derived from the power-law rate, Maxwellian electrons)",
    "energy gate under isothermal_source_conduction: the conducted source heat is the electron-energy residual, so the "
    "energy residual checks ledger bookkeeping consistency, not physical energy conservation",
    "uncaptured ions at the junction leave as plume leakage together with their electrons",
    "the mixture mean free path uses 1 / (sqrt(2) sum_k n_k sigma_k) (generalization of Chiggiato Eq. 7)",
)


def _run(c: _Compiled, n_steps: int) -> dict:
    sol = _integrate(c, n_steps)
    Y, idx, N0 = sol["Y"], sol["idx"], sol["N0"]
    yL = Y[-1]
    NL = yL[idx["N"]]
    GL = yL[idx["G"]] if c.neutrals else np.zeros(0)
    G0 = Y[0][idx["G"]] if c.neutrals else np.zeros(0)
    cap = c.f_cap * NL
    plume = NL - cap
    q0 = float(N0 @ c.Z)
    qL = float(NL @ c.Z)
    qcap = float(cap @ c.Z)
    eta_duct = qL / q0
    eta_junction = (qcap / qL) if qL > 0 else None
    eta = qcap / q0
    eta_p = float(cap.sum()) / float(N0.sum())
    eta_m = float(cap @ c.Mi) / float(N0 @ c.Mi)
    if c.neutrals:
        if c.leak_fraction is None:
            G_hall = G_leak = np.zeros_like(GL)
        else:
            G_leak = c.leak_fraction * GL
            G_hall = GL - G_leak
    else:
        G_hall = G_leak = np.zeros(0)
    # --- conservation (elements, charge, mass, energy)
    elem_res = {}
    for el in c.elements:
        ai = np.array([c.sp[i]["comp"].get(el, 0) for i in c.ions], float)
        an = np.array([c.sp[k]["comp"].get(el, 0) for k in c.neutrals], float)
        a_in = float(N0 @ ai) + (float(G0 @ an) if c.neutrals else 0.0)
        a_out = float(cap @ ai + plume @ ai) + (float(G_hall @ an + G_leak @ an) if c.neutrals else 0.0)
        elem_res[el] = abs(a_in - a_out) / a_in if a_in > 0 else abs(a_out)
    wall = yL[idx["wall"]]
    react = yL[idx["react"]]
    dq_react = np.array([r["d_charge"] for r in c.rx]) if c.rx else np.zeros(0)
    charge_out = qcap + float(plume @ c.Z) + float(wall @ c.Z) - float(react @ dq_react)
    charge_res = abs(q0 - charge_out) / q0
    m_ion = c.Mi + c.Z * M_E
    m_in = float(N0 @ m_ion) + (float(G0 @ c.Mn) if c.neutrals else 0.0)
    m_out = float((cap + plume) @ m_ion) + (float((G_hall + G_leak) @ c.Mn) if c.neutrals else 0.0)
    mass_res = abs(m_in - m_out) / m_in
    e_ion = c.KE + c.Fi * E_CHARGE
    Wcoef = 2.5 * E_CHARGE * c.Te
    E_in = {"ions_kinetic_plus_formation": float(N0 @ e_ion), "electron_enthalpy": Wcoef * q0,
            "neutral_formation": float(G0 @ c.Fn) * E_CHARGE if c.neutrals else 0.0}
    E_cond = float(yL[idx["E_cond"]])
    E_out = {"ions_to_hall": float(cap @ e_ion), "electrons_to_hall": Wcoef * qcap,
             "ions_plume_leak": float(plume @ e_ion), "electrons_plume_leak": Wcoef * float(plume @ c.Z),
             "neutral_formation_to_hall": float(G_hall @ c.Fn) * E_CHARGE if c.neutrals else 0.0,
             "neutral_formation_leak": float(G_leak @ c.Fn) * E_CHARGE if c.neutrals else 0.0}
    sinks = {"wall_ion_axial_kinetic": float(yL[idx["E_wall_ion_kin"]]),
             "wall_ion_presheath_sheath": float(yL[idx["E_wall_ion_pot"]]),
             "wall_neutralization": float(yL[idx["E_wall_neut"]]),
             "wall_electron": float(yL[idx["E_wall_elec"]]),
             "wall_atom_recombination": float(yL[idx["E_wall_atom"]]),
             "volume_reaction_heat_radiation": float(yL[idx["E_react"]])}
    lhs = sum(E_in.values()) + E_cond
    rhs = sum(E_out.values()) + sum(sinks.values())
    norm = sum(abs(v) for v in E_in.values()) + abs(E_cond) + sum(abs(v) for v in E_out.values()) + \
        sum(abs(v) for v in sinks.values())
    energy_res = abs(lhs - rhs) / norm if norm > 0 else 0.0
    # --- charge-state fractions per element (ion particle flows)
    def csf(flows):
        out = {}
        for el in c.elements:
            sel = [a for a, i in enumerate(c.ions) if el in c.sp[i]["comp"]]
            tot = float(sum(flows[a] for a in sel))
            if not sel:
                continue
            fr = {}
            for a in sel:
                Z = str(int(c.Z[a]))
                fr[Z] = fr.get(Z, 0.0) + (float(flows[a]) / tot if tot > 0 else 0.0)
            out[el] = fr if tot > 0 else None
        return out
    zg, p = sol["z"], sol["p"]
    Nz = Y[:, idx["N"]]
    prof = {"z_m": [float(z) for z in zg],
            "eta_duct": [float(Nz[j] @ c.Z) / q0 for j in range(len(zg))],
            "charge_state_fractions": [csf(Nz[j]) for j in range(len(zg))],
            "neutral_partial_pressure_Pa": {k: [float(v) for v in p[a]] for a, k in enumerate(c.neutrals)}}
    # --- neutral transport diagnostics
    ntot = p.sum(axis=0) / (K_B * c.Tn) if c.neutrals else np.zeros(len(zg))
    sig_mix = (lambda j: float((p[:, j] / (K_B * c.Tn)) @ c.sigma_c) / ntot[j] if ntot[j] > 0 else float(c.sigma_c.mean()))
    lam = [molecular_mean_free_path(float(ntot[j]), sig_mix(j)) if c.neutrals else math.inf for j in range(len(zg))]
    Kn_duct_min = min(knudsen_number(l, c.Dh) for l in lam)
    Kn_junction = knudsen_number(lam[-1], c.D_junction)
    regime = flow_regime(Kn_duct_min)
    return {"eta": eta, "eta_duct": eta_duct, "eta_junction": eta_junction, "eta_p": eta_p, "eta_m": eta_m,
            "N0": N0, "NL": NL, "cap": cap, "plume": plume, "wall": wall, "react": react, "G0": G0, "GL": GL,
            "G_hall": G_hall, "G_leak": G_leak, "p": p, "z": zg, "elem_res": elem_res, "charge_res": charge_res,
            "mass_res": mass_res, "energy_res": energy_res, "E_in": E_in, "E_out": E_out, "sinks": sinks,
            "E_cond": E_cond, "csf_in": csf(N0), "csf_exit": csf(NL), "csf_cap": csf(cap), "profiles": prof,
            "Kn_duct_min": Kn_duct_min, "Kn_junction": Kn_junction, "regime": regime,
            "p_max_total": float(p.sum(axis=0).max()) if c.neutrals else 0.0,
            "iterations": sol["iterations"], "diag0": sol["diag0"], "diagL": sol["diagL"], "wallrec": yL[idx["wallrec"]],
            "m_in": m_in, "m_out_hall": float(cap @ m_ion) + (float(G_hall @ c.Mn) if c.neutrals else 0.0)}


def _domain_gates(c: _Compiled, r: dict):
    """Formula-domain gates (raise: a refusal, not a status)."""
    if c.neutrals and c.nc_mode in (NC_SANTELER, NC_TRANSMISSION) and r["Kn_duct_min"] <= KN_MOLECULAR_MIN:
        raise InterstageDomainError(
            f"duct Knudsen number {r['Kn_duct_min']:.4g} <= {KN_MOLECULAR_MIN}: not free-molecular "
            f"({r['regime']}); the molecular conductance does not apply. TBD: supply a sourced transitional/viscous "
            "conductance via neutral_conductance.mode = explicit_conductance")
    if c.neutrals and r["Kn_junction"] <= KN_MOLECULAR_MIN:
        raise InterstageDomainError(
            f"junction Knudsen number {r['Kn_junction']:.4g} <= {KN_MOLECULAR_MIN}: the free-molecular junction split "
            "does not apply (TBD: transitional junction model)")
    if c.h_mode == H_LIEBERMAN and r["p_max_total"] >= LIEBERMAN_H_P_MAX_PA:
        raise InterstageDomainError(
            f"neutral pressure {r['p_max_total']:.4g} Pa >= 100 mTorr: outside the stated domain of Lieberman h_R")


def _refuse_if_entry_estimate_out_of_domain(c: _Compiled, exc: Exception):
    """Called only when no converged state exists. The formula domain is normally judged on the converged profile
    (_domain_gates); without one, the entry-flow estimate (uniform supplied neutral flows) is the only state available.
    If that estimate is itself outside the free-molecular domain, the failure is reported as a domain refusal (the
    formulas were never applicable), not as a solver status."""
    if not c.neutrals or c.nc_mode not in (NC_SANTELER, NC_TRANSMISSION):
        return
    zg = np.linspace(0.0, c.L, c.nm.n_steps + 1) if c.L > 0 else np.zeros(2)
    G = np.repeat(np.array([c.G0[k] for k in c.neutrals])[:, None], len(zg), axis=1)
    try:
        p = _pressure_profile(c, zg, G, strict=False)
    except (_Infeasible, _ModelError):
        return
    n = p / (K_B * c.Tn)
    ntot = n.sum(axis=0)
    for j in range(len(zg)):
        if ntot[j] <= 0:
            continue
        Kn = knudsen_number(molecular_mean_free_path(float(ntot[j]), float(n[:, j] @ c.sigma_c) / float(ntot[j])),
                            c.Dh)
        if Kn <= KN_MOLECULAR_MIN:
            raise InterstageDomainError(
                f"no converged state ({exc}); the entry-flow estimate has duct Knudsen number {Kn:.4g} <= "
                f"{KN_MOLECULAR_MIN} ({flow_regime(Kn)}), outside the free-molecular conductance domain. TBD: supply a "
                "sourced transitional/viscous conductance via neutral_conductance.mode = explicit_conductance") from None


def solve_interstage(case: InterstageCase) -> dict:
    """Solve one interstage case. Raises (refuses) on missing/invalid/TBD/out-of-domain inputs; returns a result dict
    (schemas/architecture_comparison/interstage_v1.schema.json, ``result``) whose ``status`` is OK, INFEASIBLE or
    MODEL_ERROR. Only an OK result carries performance numbers."""
    c = _Compiled(case)
    try:
        r1 = _run(c, c.nm.n_steps)
        r2 = _run(c, 2 * c.nm.n_steps)
    except _Infeasible as exc:
        _refuse_if_entry_estimate_out_of_domain(c, exc)
        return _null_result(c, "INFEASIBLE", str(exc))
    except _ModelError as exc:
        _refuse_if_entry_estimate_out_of_domain(c, exc)
        return _null_result(c, "MODEL_ERROR", str(exc))
    _domain_gates(c, r1)
    _domain_gates(c, r2)
    # --- numerical convergence (step doubling). Scale-safe normalisation: one common scale per quantity, taken over
    # BOTH runs (never a 1e-300 floor that turns a zero entry flow into inf/NaN), and a non-finite change is an error.
    n_scale = float(r1["N0"].sum())                                   # > 0 (checked in _Compiled._state)
    parts1 = [np.array([r1["eta"], r1["eta_duct"]]), r1["NL"] / n_scale, r1["cap"] / n_scale]
    parts2 = [np.array([r2["eta"], r2["eta_duct"]]), r2["NL"] / n_scale, r2["cap"] / n_scale]
    p_entry_change = 0.0
    if c.neutrals:
        g_scale = max(float(r1["G0"].sum()), float(np.abs(r1["GL"]).sum()), float(np.abs(r2["GL"]).sum()))
        p_scale = max(float(r1["p"][:, 0].sum()), float(r2["p"][:, 0].sum()))
        if g_scale > 0:
            parts1.append(r1["GL"] / g_scale)
            parts2.append(r2["GL"] / g_scale)
        if p_scale > 0:
            parts1.append(r1["p"][:, 0] / p_scale)
            parts2.append(r2["p"][:, 0] / p_scale)
            p_entry_change = float(np.max(np.abs(r1["p"][:, 0] - r2["p"][:, 0]))) / p_scale
    step_change = float(np.max(np.abs(np.concatenate(parts1) - np.concatenate(parts2))))
    r = r2
    cons = {"elements_rel": r["elem_res"], "charge_rel": r["charge_res"], "mass_rel": r["mass_res"],
            "energy_rel": r["energy_res"], "gate_rtol": c.nm.conservation_rtol}
    # every residual must be finite AND within tolerance (max() over a list with NaN is order-dependent)
    cons["passed"] = all(math.isfinite(v) and v <= c.nm.conservation_rtol
                         for v in [*r["elem_res"].values(), r["charge_res"], r["mass_res"], r["energy_res"]])
    # --- neutral boundary consistency: supplied source-exit densities vs the flow-path densities
    n_path = {k: float(r["p"][a, 0]) / (K_B * c.Tn) for a, k in enumerate(c.neutrals)}
    n_path_tot = sum(n_path.values())
    mismatch = {k: (abs(c.n_n0_supplied[k] - n_path[k]) / n_path_tot if n_path_tot > 0 else abs(c.n_n0_supplied[k]))
                for k in c.neutrals}
    boundary_ok = (max(mismatch.values()) <= c.nm.boundary_rtol) if c.neutrals else True
    finite = math.isfinite(step_change)
    diagnostics = {"step_doubling_rel_change": step_change if finite else None,
                   "p_entry_step_doubling_rel_change": p_entry_change if math.isfinite(p_entry_change) else None,
                   "flow_path_entry_density_m3": n_path,
                   "supplied_entry_density_m3": dict(c.n_n0_supplied),
                   "boundary_mismatch_rel": mismatch, "conservation": cons}
    if not finite:
        return _null_result(c, "MODEL_ERROR", "step-doubling change is not finite (NaN/inf in the solution); the "
                                              "convergence gate cannot be evaluated", diagnostics)
    if step_change > c.nm.convergence_rtol:
        return _null_result(c, "MODEL_ERROR", f"step-doubling change {step_change:.3e} > convergence_rtol "
                                              f"{c.nm.convergence_rtol:g} (increase numerics.n_steps)", diagnostics)
    if not cons["passed"]:
        return _null_result(c, "MODEL_ERROR", "conservation gate failed (CLAUDE.md rule 4)", diagnostics)
    if not boundary_ok:
        return _null_result(c, "INFEASIBLE", "supplied source-exit neutral densities are inconsistent with the "
                                             "interstage + junction flow path at the supplied neutral flows "
                                             f"(max mismatch {max(mismatch.values()):.3e} > boundary_rtol "
                                             f"{c.nm.boundary_rtol:g}); see diagnostics.flow_path_entry_density_m3",
                            diagnostics)
    res = _empty_result(case)
    ions = {}
    for a, i in enumerate(c.ions):
        ions[i] = {"entry_flow_s": float(r["N0"][a]), "exit_flow_s": float(r["NL"][a]),
                   "delivered_to_hall_flow_s": float(r["cap"][a]), "plume_leak_flow_s": float(r["plume"][a]),
                   "wall_loss_flow_s": float(r["wall"][a]),
                   "net_volume_reaction_change_s": float(sum(r["react"][b] * c.rx[b]["d_ion"][a]
                                                             for b in range(len(c.rx)))),
                   "axial_speed_m_s": float(c.v[a]), "charge": int(c.Z[a]),
                   "bohm_speed_entry_m_s": float(r["diag0"]["u_B"][a]),
                   "h_entry": float(r["diag0"]["h"][a]), "h_exit": float(r["diagL"]["h"][a])}
    neutrals = {}
    for a, k in enumerate(c.neutrals):
        neutrals[k] = {"entry_flow_s": float(r["G0"][a]), "exit_flow_s": float(r["GL"][a]),
                       "to_hall_flow_s": float(r["G_hall"][a]), "leak_flow_s": float(r["G_leak"][a]),
                       "p_entry_Pa": float(r["p"][a, 0]), "p_exit_Pa": float(r["p"][a, -1]),
                       "pressure_drop_Pa": float(r["p"][a, 0] - r["p"][a, -1]),
                       "duct_conductance_m3_s": float(c.C_duct[a]),
                       "junction_conductance_m3_s": float(c.C_J[a]),
                       "entry_density_supplied_m3": float(c.n_n0_supplied[k]),
                       "entry_density_flow_path_m3": n_path[k], "boundary_mismatch_rel": float(mismatch[k])}
    wall_area = c.P * c.L
    wall_heat = sum(v for key, v in r["sinks"].items() if key.startswith("wall_"))
    mag = None
    if c.B > 0:
        r_e = gyroradius(M_E, math.sqrt(E_CHARGE * c.Te / M_E), 1, c.B)
        mag = {"B_T": c.B, "electron_gyroradius_m": r_e, "electron_gyroradius_over_radial_scale": r_e / c.radial_scale,
               "ion_gyroradius_at_bohm_speed_m": {i: gyroradius(float(c.Mi[a]), float(r["diag0"]["u_B"][a]),
                                                               int(c.Z[a]), c.B) for a, i in enumerate(c.ions)},
               "radial_scale_m": c.radial_scale,
               "note": "diagnostic only; no sourced magnetization threshold gates the closure choice"}
    res.update({
        "status": "OK", "status_reason": "", "converged": True,
        "eta_transport": r["eta"], "eta_duct": r["eta_duct"], "eta_junction": r["eta_junction"],
        "eta_transport_particle": r["eta_p"], "eta_transport_mass": r["eta_m"],
        "mass_delivery_fraction": r["m_out_hall"] / r["m_in"],
        "ions": ions, "neutrals": neutrals,
        "charge_state_fractions": {"entry": r["csf_in"], "exit": r["csf_exit"], "delivered": r["csf_cap"]},
        "neutral_transport": {"mode": c.nc_mode, "regime_duct": r["regime"] if c.neutrals else None,
                              "knudsen_duct_min": r["Kn_duct_min"] if c.neutrals else None,
                              "knudsen_junction": r["Kn_junction"] if c.neutrals else None,
                              "transmission_probability": c.tau, "transmission_source": c.tau_source,
                              "junction_leak_fraction": c.leak_fraction,
                              "hydraulic_diameter_m": c.Dh, "fixed_point_iterations": r["iterations"]},
        "reactions": {rx["id"]: {"events_s": float(r["react"][b]), "rate_coefficient_m3_s": rx["k"],
                                 "heat_per_event_eV": rx["heat_J"] / E_CHARGE, "process": rx["process"],
                                 "electron_energy_loss_eV": rx["eps_e_eV"],
                                 "electron_energy_loss_basis": rx["eel_basis"]}
                      for b, rx in enumerate(c.rx)},
        "wall": {"radial_loss_closure": c.h_mode, "wall_electrical": "floating",
                 "wall_material": case.geometry.wall_material, "side_wall_area_m2": wall_area,
                 "sheath_potential_entry_V": r["diag0"]["V_s"], "sheath_potential_exit_V": r["diagL"]["V_s"],
                 "ion_wall_impact_energy_entry_eV": {
                     i: float(c.KE[a] / E_CHARGE + c.Z[a] * (0.5 * c.Te + r["diag0"]["V_s"]))
                     for a, i in enumerate(c.ions)},
                 "wall_heat_W": wall_heat,
                 "mean_wall_heat_flux_W_m2": (wall_heat / wall_area) if wall_area > 0 else None,
                 "wall_atom_recombination_events_s": {w["name"]: float(r["wallrec"][j]) for j, w in enumerate(c.wr)},
                 "magnetization": mag},
        "energy_ledger_W": {"in": r["E_in"], "electron_heat_from_source_W": r["E_cond"], "out": r["E_out"],
                            "sinks": r["sinks"], "residual_rel": r["energy_res"],
                            "note": ("bookkeeping consistency check, not a physical energy-conservation test: under "
                                     "isothermal_source_conduction electron_heat_from_source_W is the electron-energy "
                                     "residual, so the balance closes by construction; neutral thermal enthalpy "
                                     "excluded (isothermal walls)")},
        "conservation": cons,
        "numerics": {"n_steps": c.nm.n_steps, "n_steps_check": 2 * c.nm.n_steps,
                     "step_doubling_rel_change": step_change, "convergence_rtol": c.nm.convergence_rtol,
                     "integrator": "classical RK4 on a uniform grid (linear invariants preserved to round-off)"},
        "profiles": r["profiles"], "diagnostics": _json_safe(diagnostics),
    })
    return res


def flow_path_entry_densities(case: InterstageCase) -> dict:
    """Neutral densities [m^-3] at the duct entry implied by the supplied neutral flows, the duct and the junction
    (what the source model must match). Refuses like ``solve_interstage``; raises InterstageError if the flow path is
    infeasible or the solve does not converge."""
    c = _Compiled(case)
    try:
        r = _run(c, 2 * c.nm.n_steps)        # the resolution solve_interstage reports and gates on
    except (_Infeasible, _ModelError) as exc:
        _refuse_if_entry_estimate_out_of_domain(c, exc)
        raise InterstageError(f"flow path not solvable: {exc}") from None
    _domain_gates(c, r)
    return {k: float(r["p"][a, 0]) / (K_B * c.Tn) for a, k in enumerate(c.neutrals)}


def _as_sourced_requirement(x) -> Sourced:
    """Accept this module's ``Sourced`` or a duck-typed record with value / unit / evidence_class / source attributes
    (e.g. abep_sim/breakeven.py ``Evidenced``, which has no uncertainty field) without importing the sibling module."""
    if isinstance(x, (Sourced, TBD)) or x is None:
        return x
    try:
        value, unit, ev, src = x.value, x.unit, x.evidence_class, x.source
    except AttributeError:
        raise InterstageInputError("eta_transport_required must be Sourced or an evidenced record with value, unit, "
                                   "evidence_class and source") from None
    unc = getattr(x, "uncertainty", None)
    return Sourced(value, unit, src, ev, unc if isinstance(unc, str) and unc.strip()
                   else "not carried by the supplying record (propagate before use)")


def compare_with_required(result: dict, eta_transport_required) -> dict:
    """Per-architecture condition check against the break-even lane's required eta_transport (abep_sim/breakeven.py,
    breakeven_v1: place_evidence()['eta_transport_min']). ``eta_transport_required`` is a ``Sourced`` or a duck-typed
    evidenced record (breakeven ``Evidenced``); the dimensionless unit may be spelled '-' (this module) or '1'
    (breakeven_v1). Not an architecture comparison: it answers only 'does this case meet its own break-even condition'."""
    if result.get("status") != "OK":
        raise InterstageInputError("compare_with_required needs an OK interstage result")
    rec = _as_sourced_requirement(eta_transport_required)
    req = _need(rec, "eta_transport_required", "-", lo=0.0)
    eta = result["eta_transport"]
    return {"architecture": result["architecture"], "case_id": result["case_id"], "eta_transport": eta,
            "eta_transport_required": req, "margin": eta - req, "condition_met": bool(eta >= req),
            "required_source": rec.source,
            "required_evidence_class": rec.evidence_class,
            "note": "a single-case condition; uncertainty envelopes of both sides must be propagated before any use"}


def eta_transport_evidence(result: dict) -> dict:
    """The keyword arguments of a breakeven_v1 ``Evidenced(value, unit, evidence_class, source)`` for this result's
    eta_transport (unit '1', the breakeven_v1 convention; evidence class model-derived). Only for an OK result; the
    caller constructs the sibling record, this module does not import it. breakeven_v1 accepts only 0 < value <= 1;
    an eta_transport > 1 (in-duct ionization) is passed through unchanged and will be refused there."""
    if result.get("status") != "OK":
        raise InterstageInputError("eta_transport_evidence needs an OK interstage result")
    eta = result["eta_transport"]
    if not (isinstance(eta, (int, float)) and math.isfinite(eta)):
        raise InterstageInputError("eta_transport is not a finite number")
    return {"value": float(eta), "unit": "1", "evidence_class": "model-derived",
            "source": (f"abep_sim/interstage.py {MODEL_VERSION}, case {result['case_id']!r} ({result['architecture']}); "
                       "conditional on every input in result['provenance']")}


# -------------------------------------------------------------------------------------- dict (de)serialization
def _s_to(x):
    if x is None:
        return None
    if isinstance(x, TBD):
        return {"tbd": x.requires}
    if isinstance(x, Sourced):
        return {"value": x.value, "unit": x.unit, "source": x.source, "evidence_class": x.evidence_class,
                "uncertainty": x.uncertainty}
    raise InterstageInputError(f"cannot serialize {type(x).__name__}")


def _s_from(d, path):
    if d is None:
        return None
    if not isinstance(d, Mapping):
        raise InterstageInputError(f"{path}: expected an object")
    if set(d) == {"tbd"}:
        return TBD(d["tbd"])
    keys = {"value", "unit", "source", "evidence_class", "uncertainty"}
    if set(d) != keys:
        raise InterstageInputError(f"{path}: sourced value needs exactly {sorted(keys)} (or {{'tbd': ...}})")
    return Sourced(d["value"], d["unit"], d["source"], d["evidence_class"], d["uncertainty"])


def _map_from(d, path):
    if d is None:
        return None
    return {k: _s_from(v, f"{path}[{k}]") for k, v in d.items()}


def _rate_to(r):
    if isinstance(r, TBD):
        return {"tbd": r.requires}
    return {"variable": r.variable, "k_ref_m3_s": r.k_ref_m3_s, "x_ref": r.x_ref, "exponent": r.exponent,
            "validity_min": r.validity_min, "validity_max": r.validity_max, "source": r.source,
            "evidence_class": r.evidence_class, "uncertainty": r.uncertainty}


def _rate_from(d, path):
    if set(d) == {"tbd"}:
        return TBD(d["tbd"])
    keys = {"variable", "k_ref_m3_s", "x_ref", "exponent", "validity_min", "validity_max", "source", "evidence_class",
            "uncertainty"}
    if set(d) != keys:
        raise InterstageInputError(f"{path}: rate needs exactly {sorted(keys)}")
    return RateCoefficient(**d)


def _strict(d, keys, path):
    if not isinstance(d, Mapping):
        raise InterstageInputError(f"{path}: expected an object")
    missing, extra = set(keys) - set(d), set(d) - set(keys)
    if missing or extra:
        raise InterstageInputError(f"{path}: missing {sorted(missing)}, unexpected {sorted(extra)}")


def case_to_dict(case: InterstageCase) -> dict:
    g = case.geometry
    if isinstance(g, CircularDuct):
        geom = {"kind": "circular", "length": _s_to(g.length), "radius": _s_to(g.radius),
                "inner_radius": None, "outer_radius": None}
    else:
        geom = {"kind": "annular", "length": _s_to(g.length), "radius": None,
                "inner_radius": _s_to(g.inner_radius), "outer_radius": _s_to(g.outer_radius)}
    geom.update(wall_material=g.wall_material, axial_magnetic_field=_s_to(g.axial_magnetic_field))
    st = case.source_exit
    m = lambda mp: None if mp is None else {k: _s_to(v) for k, v in mp.items()}
    w, nc, j, nm = case.wall, case.neutral_conductance, case.junction, case.numerics
    return {
        "schema": SCHEMA_ID, "case_id": case.case_id, "architecture": case.architecture,
        "energy_reference": case.energy_reference,
        "species": [{"name": s.name, "charge": s.charge, "composition": dict(s.composition), "mass": _s_to(s.mass),
                     "formation_energy": _s_to(s.formation_energy)} for s in case.species],
        "source_exit": {"ion_density": m(st.ion_density), "ion_axial_speed": m(st.ion_axial_speed),
                        "electron_temperature": _s_to(st.electron_temperature),
                        "neutral_density": m(st.neutral_density), "neutral_flow": m(st.neutral_flow),
                        "neutral_temperature": _s_to(st.neutral_temperature)},
        "geometry": geom,
        "wall": {"radial_loss_closure": w.radial_loss_closure, "wall_electrical": w.wall_electrical,
                 "neutralization_products": {k: list(v) for k, v in w.neutralization_products.items()},
                 "ion_neutral_cross_section": m(w.ion_neutral_cross_section), "explicit_h": m(w.explicit_h)},
        "reactions": [{"reaction_id": r.reaction_id, "reactants": list(r.reactants), "products": list(r.products),
                       "rate": _rate_to(r.rate),
                       "electron_energy_loss": (r.electron_energy_loss if isinstance(r.electron_energy_loss, str)
                                                else _s_to(r.electron_energy_loss)),
                       "process": r.process} for r in case.reactions],
        "wall_atom_recombination": [{"atom": x.atom, "product": x.product, "probability": _s_to(x.probability)}
                                    for x in case.wall_atom_recombination],
        "process_exclusions": dict(case.process_exclusions),
        "neutral_conductance": {"mode": nc.mode, "collision_cross_section": m(nc.collision_cross_section),
                                "transmission_probability": _s_to(nc.transmission_probability),
                                "explicit_conductance": m(nc.explicit_conductance)},
        "junction": {"ion_capture_fraction": m(j.ion_capture_fraction),
                     "hall_path_effective_area": _s_to(j.hall_path_effective_area),
                     "leak_path_effective_area": _s_to(j.leak_path_effective_area),
                     "characteristic_dimension": _s_to(j.characteristic_dimension)},
        "electron_energy_closure": case.electron_energy_closure,
        "numerics": {f.name: getattr(nm, f.name) for f in fields(nm)},
    }


def case_from_dict(d: Mapping) -> InterstageCase:
    top = ("schema", "case_id", "architecture", "energy_reference", "species", "source_exit", "geometry", "wall",
           "reactions", "wall_atom_recombination", "process_exclusions", "neutral_conductance", "junction",
           "electron_energy_closure", "numerics")
    _strict(d, top, "case")
    if d["schema"] != SCHEMA_ID:
        raise InterstageInputError(f"case.schema must be {SCHEMA_ID!r}")
    species = []
    for s in d["species"]:
        _strict(s, ("name", "charge", "composition", "mass", "formation_energy"), "species[]")
        species.append(Species(s["name"], s["charge"], dict(s["composition"]), _s_from(s["mass"], f"{s['name']}.mass"),
                               _s_from(s["formation_energy"], f"{s['name']}.formation_energy")))
    st = d["source_exit"]
    _strict(st, ("ion_density", "ion_axial_speed", "electron_temperature", "neutral_density", "neutral_flow",
                 "neutral_temperature"), "source_exit")
    source_exit = SourceExitState(_map_from(st["ion_density"], "ion_density"),
                                  _map_from(st["ion_axial_speed"], "ion_axial_speed"),
                                  _s_from(st["electron_temperature"], "electron_temperature"),
                                  _map_from(st["neutral_density"], "neutral_density"),
                                  _map_from(st["neutral_flow"], "neutral_flow"),
                                  _s_from(st["neutral_temperature"], "neutral_temperature"))
    g = d["geometry"]
    _strict(g, ("kind", "length", "radius", "inner_radius", "outer_radius", "wall_material", "axial_magnetic_field"),
            "geometry")
    if g["kind"] == "circular":
        geometry = CircularDuct(_s_from(g["length"], "length"), _s_from(g["radius"], "radius"), g["wall_material"],
                                _s_from(g["axial_magnetic_field"], "axial_magnetic_field"))
    elif g["kind"] == "annular":
        geometry = AnnularDuct(_s_from(g["length"], "length"), _s_from(g["inner_radius"], "inner_radius"),
                               _s_from(g["outer_radius"], "outer_radius"), g["wall_material"],
                               _s_from(g["axial_magnetic_field"], "axial_magnetic_field"))
    else:
        raise InterstageInputError("geometry.kind must be 'circular' or 'annular'")
    w = d["wall"]
    _strict(w, ("radial_loss_closure", "wall_electrical", "neutralization_products", "ion_neutral_cross_section",
                "explicit_h"), "wall")
    wall = WallModel(w["radial_loss_closure"], w["wall_electrical"],
                     {k: tuple(v) for k, v in w["neutralization_products"].items()},
                     _map_from(w["ion_neutral_cross_section"], "ion_neutral_cross_section"),
                     _map_from(w["explicit_h"], "explicit_h"))
    reactions = []
    for r in d["reactions"]:
        _strict(r, ("reaction_id", "reactants", "products", "rate", "electron_energy_loss", "process"), "reactions[]")
        eel = r["electron_energy_loss"]
        reactions.append(VolumeReaction(r["reaction_id"], tuple(r["reactants"]), tuple(r["products"]),
                                        _rate_from(r["rate"], r["reaction_id"]),
                                        eel if isinstance(eel, str) else _s_from(eel, r["reaction_id"]),
                                        r["process"]))
    war = []
    for x in d["wall_atom_recombination"]:
        _strict(x, ("atom", "product", "probability"), "wall_atom_recombination[]")
        war.append(WallAtomRecombination(x["atom"], x["product"], _s_from(x["probability"], "probability")))
    nc = d["neutral_conductance"]
    _strict(nc, ("mode", "collision_cross_section", "transmission_probability", "explicit_conductance"),
            "neutral_conductance")
    neutral_conductance = NeutralConductanceModel(
        nc["mode"], _map_from(nc["collision_cross_section"], "collision_cross_section"),
        _s_from(nc["transmission_probability"], "transmission_probability"),
        _map_from(nc["explicit_conductance"], "explicit_conductance"))
    j = d["junction"]
    _strict(j, ("ion_capture_fraction", "hall_path_effective_area", "leak_path_effective_area",
                "characteristic_dimension"), "junction")
    junction = JunctionModel(_map_from(j["ion_capture_fraction"], "ion_capture_fraction"),
                             _s_from(j["hall_path_effective_area"], "hall_path_effective_area"),
                             _s_from(j["leak_path_effective_area"], "leak_path_effective_area"),
                             _s_from(j["characteristic_dimension"], "characteristic_dimension"))
    nm = d["numerics"]
    _strict(nm, [f.name for f in fields(Numerics)], "numerics")
    return InterstageCase(d["case_id"], d["architecture"], d["energy_reference"], tuple(species), source_exit, geometry,
                          wall, tuple(reactions), tuple(war), dict(d["process_exclusions"]), neutral_conductance,
                          junction, d["electron_energy_closure"], Numerics(**nm))
