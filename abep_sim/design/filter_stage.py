"""A9.7 F2 - explicit filter-stage interface between the intake exit (IF-A1) and the compressor inlet (IF-A2).

Lane fo_a9_7_f2_filter_stage (owner directive OD_2026_10_01_A9_7, section F2). New design-synthesis code: it imports
``abep_sim.constants`` (species masses, k_B) and, only to *record* repository placeholders, reads the dataclass defaults
of ``abep_sim.intake_tpmc.IntakeGeometry``. It modifies no existing module, is not wired into archengine and moves no
golden benchmark.

What a FilterStage carries, per species s (every number an evidence-labelled ``EV`` record or TBD):
  * forward transmission tau_f,s  - fraction of the s-molecules arriving at the INLET face (intake side) that leave the
    OUTLET face (compressor side) still as s, for the declared forward incidence (diffuse thermal or hyperthermal);
  * forward capture  k_f,s       - fraction retained by the element (adsorbed, deposited);
  * forward conversion v_f,s     - fraction converted into other species (e.g. heterogeneous O + O -> O2), with a fixed
    stoichiometric product map and a product routing fraction (to the outlet side);
  * forward reflection r_f,s = 1 - tau_f,s - k_f,s - v_f,s (derived; refused if negative), so
    forward + reflected + lost = 1 per species by construction, with lost = captured + converted;
  * the same four for the backflow direction (molecules arriving at the OUTLET face from the plenum / compressor side,
    the F4 coupling): tau_b,s, k_b,s, v_b,s, r_b,s;
  * the pressure / conductance effect: free-molecular conductance C_s = alpha_s * A * cbar_s / 4 (Livesey 1998, in
    Lafferty (ed.) "Foundations of Vacuum Science and Technology", Wiley, Eqs. (2.14)-(2.15)), alpha_s = transmission
    probability for diffuse (chaotic-gas) incidence; regime declared free molecular, applicable only for Kn > 0.5
    (Livesey Table 2.1). The net-throughput pressure difference is dp_s = Q_s / C_s (Livesey Sec. 2.2: two independent
    fluxes, net flux proportional to the pressure difference). Outside the regime the stage refuses (OUT_OF_DOMAIN);
  * mass = areal mass x face area (both EV);
  * contamination / protection functions (what it stops: particulates / debris, sputter or wear products, atomic O to
    downstream surfaces, ambient charged particles; and what it emits itself), qualitative + capture efficiency EV;
  * atomic-oxygen / material applicability records using the P4 evidence vocabulary
    (docs/experiments/hall_icp/p4_anode_materials/p4_screening.py: gate outcomes, never PASS) and the owner row-132
    label NO_ATOMIC_O for N2 + O2 surrogate evidence.

Fail-closed rules
  * ``apply`` produces numbers only when every parameter it needs is usable evidence (status EVIDENCED, MODEL_DERIVED,
    OWNER_GIVEN or DEFINITION, finite value, evidence class not 'assumed', non-empty source). A TBD, a placeholder or
    an assumed value makes it REFUSE (status REFUSED_TBD) and list what is missing.
  * The only way to obtain numbers with TBD inputs is an explicit ``SensitivityCase``: its label must contain
    PARAMETRIC_SENSITIVITY, every override is listed in the result, and the result label is
    PARAMETRIC_SENSITIVITY_NOT_EVIDENCE. A search never converts a TBD into an assumed value silently (A9.7 F7).
  * The repository's present filter numbers (``abep_sim/intake_tpmc.py`` IntakeGeometry.filter_*; ``intake.py`` /
    ``system.py`` 0.8 kg/m2) are recorded as PLACEHOLDER_NOT_A_FLIGHT_DESIGN (``repository_placeholders``) and are
    usable only through ``placeholder_sensitivity_case`` - never silently.
  * Inlet states labelled other than EVIDENCE propagate their label to the outlet.
  * The 'none' option (``FilterStage.none``) is the definitional identity (no element): tau = 1, nothing lost, no
    pressure effect, zero mass. It exists for trade studies as the FC-00 reference bound only; the owner answered
    F2-OQ-03 (A9.13 S6.5): never an admissible flight architecture under the RFP intake -> filter -> compressor chain.
  * Nothing here selects, ranks or declares a filter concept; no status is ever PASS / SELECTED / WINNER / QUALIFIED.

A9.13 owner decisions applied (A9.16 step 3, design layer; docs/decisions/OD_2026_10_01_A9_13_*, json sha256
9afaca45...; ids S6.3 / F2-OQ-01, S6.4 / F2-OQ-02, S6.5 / F2-OQ-03, S6.6 / F2-OQ-04, S6.19 / UPSTREAM_ICD-Q1):
  * the filter is a SEPARATE production-path element between IF-A1 (intake / channel-array exit) and IF-A2
    (compressor inlet) (``INTERFACE_POSITION``); its effect is never folded into the intake efficiency: every result
    exposes species-resolved forward and reverse transmission, the conductance / pressure effect, species
    conversion / recombination, the retained inventory, the thermal load, the material state and validity / domain
    flags (``FilterResult``: ``retained_inventory``, ``thermal_load``, ``material_state``, ``validity_flags``);
  * baseline role = protection against particulates / debris while preserving the atmospheric propellant, with an
    inert / low-recombination element (``ROLE_BASELINE``). Atomic O is NOT a contaminant to be removed; compressor
    wear products are not credited to this filter. A deliberately catalytic O -> O2 element exists only as the
    labelled research variant ``ROLE_CATALYTIC_RESEARCH`` (never admissible as baseline; it needs its own species-
    conversion, flow / conductance, thermal / material and converted-composition H-1 evidence);
  * FC-00 / ``FilterStage.none`` is ``ROLE_REFERENCE_BOUND``: an ideal reference bound to quantify the filter cost,
    never an admissible flight architecture (the RFP chain RFP-P16-02 contains intake -> filter -> compressor);
  * APP-FILTER is a P4 materials application (S6.6); quantitative acceptance limits (capture, transmission,
    pressure loss, O recombination, capacity, erosion) are pre-registered before LOCK-1 from evidence, never defaulted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

from ..constants import K_B, M_SPECIES

# --------------------------------------------------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------------------------------------------------
# quantity types: docs/EVIDENCE.md six types, plus the P4 extensions (p4_anode_materials_v1.json vocabulary)
QUANTITY_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                  "owner-allocation", "owner-stated", "published analog", "qualitative", "definition",
                  "published convention")
EV_STATUSES = ("EVIDENCED", "MODEL_DERIVED", "OWNER_GIVEN", "DEFINITION", "TBD", "PLACEHOLDER_NOT_A_FLIGHT_DESIGN")
USABLE_STATUSES = ("EVIDENCED", "MODEL_DERIVED", "OWNER_GIVEN", "DEFINITION")
PLACEHOLDER = "PLACEHOLDER_NOT_A_FLIGHT_DESIGN"
# P4 gate-outcome vocabulary (docs/experiments/hall_icp/p4_anode_materials/p4_screening.py GATE_OUTCOMES); a test
# asserts equality with the P4 module so the two never drift.
AO_GATE_OUTCOMES = ("INCOMPLETE_EVIDENCE", "OUT_OF_DOMAIN", "GATE_VIOLATED_BY_EVIDENCE",
                    "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN")
FORBIDDEN_STATUS_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED")
NO_ATOMIC_O = "NO_ATOMIC_O"   # owner row 132: N2 + O2 surrogate evidence label, never AO-life proof
SURROGATE_LABELS = (NO_ATOMIC_O, "DEDICATED_AO_SOURCE", "NONE")

INCIDENCES = ("diffuse_thermal", "hyperthermal_directed")
REGIMES = ("free_molecular",)
# Livesey 1998 Table 2.1: molecular flow Kn > 0.5; transitional 0.5 > Kn > 0.01; continuum Kn < 0.01.
KN_MOLECULAR_MIN = 0.5
KN_SOURCE = ("R. G. Livesey, 'Flow of gases through tubes and orifices', ch. 2 in J. M. Lafferty (ed.), Foundations of "
             "Vacuum Science and Technology, Wiley 1998, ISBN 0-471-17593-5, Table 2.1 (molecular Kn > 0.5)")

PROTECTION_TARGETS = (
    "particulates_debris",                  # solid objects / particles reaching the compressor rotor
    "sputter_wear_products",                # products from downstream (compressor wear, plume back-sputter) or upstream
    "atomic_oxygen_to_downstream_surfaces",  # O reaching compressor / plenum / H-1 surfaces
    "ambient_charged_particles",            # ionospheric ions / electrons entering with the neutral flow
    "filter_self_contamination",            # what the element itself emits (erosion, outgassing)
)

INLET_LABELS = ("EVIDENCE", "PARAMETRIC_SENSITIVITY", "NORMALIZED_UNIT_INPUT")
LABEL_EVIDENCE = "EVIDENCE_BASED"
LABEL_SENSITIVITY = "PARAMETRIC_SENSITIVITY_NOT_EVIDENCE"
LABEL_NORMALIZED = "NORMALIZED_UNIT_INPUT_NOT_A_PHYSICAL_STATE"

RESULT_STATUSES = ("NUMERIC", "NO_FILTER_IDENTITY", "REFUSED_TBD", "OUT_OF_DOMAIN", "NONPHYSICAL_INPUT")

# Fixed stoichiometric product maps (definitional mass yields of a conversion channel). Only channels named here can
# be given a non-zero conversion fraction; adding one is a model change of this module.
CONVERSION_PRODUCTS: dict[str, dict[str, float]] = {
    "O": {"O2": 1.0},        # heterogeneous recombination O + O -> O2 (mass conserved)
}

CONSERVATION_TOL = 1e-12

# A9.13 S6.3-S6.6 / S6.19 roles and interface position
ROLE_BASELINE = "BASELINE_INERT_LOW_RECOMBINATION"
ROLE_CATALYTIC_RESEARCH = "RESEARCH_VARIANT_CATALYTIC_NOT_BASELINE"
ROLE_REFERENCE_BOUND = "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE_FLIGHT_ARCHITECTURE"
ROLES = (ROLE_BASELINE, ROLE_CATALYTIC_RESEARCH, ROLE_REFERENCE_BOUND)
INTERFACE_POSITION = {"upstream_interface": "IF-A1 (intake / channel-array exit, downstream of the primary intake / "
                                            "collimator)",
                      "downstream_interface": "IF-A2 (compressor inlet)",
                      "production_path_element": True, "folded_into_intake_efficiency": False,
                      "basis": "A9.13 S6.6 / S6.19; RFP-P16-02 (Intake -> Filter -> Compressor)"}
# the evidence a catalytic research variant needs (A9.13 S6.4) before any of its results is more than a sensitivity
CATALYTIC_VARIANT_EVIDENCE = ("species-conversion measurement", "flow / conductance measurement",
                              "thermal / material qualification", "H-1 performance map on the converted composition")
BASELINE_PROTECTION_TARGETS = ("particulates_debris",)          # S6.3: intake-borne particulates, foreign debris,
#                                                                 manufacturing / released particulates
NOT_CREDITED_TARGETS = {
    "atomic_oxygen_to_downstream_surfaces": "atomic O is propellant (RFP-P17-05), not a contaminant to be removed "
                                            "in the baseline (A9.13 S6.3)",
    "sputter_wear_products": "compressor wear products are downstream-generated: not credited to the intake filter "
                             "unless backstream transport is demonstrated; a separate downstream guard / trap is "
                             "defined if needed (A9.13 S6.3)",
    "ambient_charged_particles": "not a baseline filter requirement unless a hazard analysis demonstrates the need "
                                 "(A9.13 S6.3)",
}
# quantitative filter acceptance (A9.13 S6.3): pre-registered before LOCK-1 from evidence; none is defaulted here
ACCEPTANCE_ITEMS = ("capture efficiency vs registered contaminant / particle class",
                    "species-resolved propellant transmission", "pressure-loss / conductance penalty",
                    "O recombination / conversion probability", "retained contaminant capacity",
                    "AO erosion / material durability", "effect on AG-12 feed-state closure")


class FilterStageError(ValueError):
    """Malformed input record (not a TBD: a TBD is a legal input that makes ``apply`` refuse)."""


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# --------------------------------------------------------------------------------------------------------------------
# evidence-labelled value
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EV:
    """VALUE | UNCERTAINTY | EVIDENCE CLASS | SOURCE | STATUS record (docs/EVIDENCE.md four attributes + type).

    ``status`` TBD: ``value`` is None and ``requires`` says what is needed. Any other status: finite value, units,
    quantity type, source. ``evidence_level`` is the docs/EVIDENCE.md 1-7 source level (None when not applicable,
    e.g. DEFINITION)."""
    value: float | None
    units: str
    status: str
    evidence_class: str | None = None
    source: str | None = None
    uncertainty: str | None = None
    basis: str = ""
    evidence_level: int | None = None
    domain: str | None = None
    requires: str | None = None

    def __post_init__(self):
        if self.status not in EV_STATUSES:
            raise FilterStageError(f"EV.status {self.status!r} not in {EV_STATUSES}")
        if not isinstance(self.units, str) or not self.units:
            raise FilterStageError("EV.units must be a non-empty string ('-' for dimensionless)")
        if self.status == "TBD":
            if self.value is not None:
                raise FilterStageError("a TBD record carries no value")
            if not isinstance(self.requires, str) or not self.requires.strip():
                raise FilterStageError("a TBD record must say what it requires")
            return
        if not _finite(self.value):
            raise FilterStageError(f"EV.value must be finite for status {self.status}, got {self.value!r}")
        if self.evidence_class not in QUANTITY_TYPES:
            raise FilterStageError(f"EV.evidence_class {self.evidence_class!r} not in {QUANTITY_TYPES}")
        if not isinstance(self.source, str) or not self.source.strip():
            raise FilterStageError("a non-TBD record needs a source")
        if self.evidence_level is not None and (isinstance(self.evidence_level, bool)
                                                or self.evidence_level not in range(1, 8)):
            raise FilterStageError("evidence_level must be 1..7 (docs/EVIDENCE.md) or None")

    @property
    def usable_as_evidence(self) -> bool:
        return (self.status in USABLE_STATUSES and _finite(self.value) and self.evidence_class != "assumed"
                and bool(self.source))

    def to_dict(self) -> dict:
        return {"value": self.value if self.status != "TBD" else "TBD", "units": self.units, "status": self.status,
                "evidence_class": self.evidence_class, "evidence_level": self.evidence_level, "source": self.source,
                "uncertainty": self.uncertainty, "basis": self.basis, "domain": self.domain,
                "requires": self.requires}


def TBD(requires: str, units: str = "-", basis: str = "") -> EV:
    return EV(value=None, units=units, status="TBD", requires=requires, basis=basis)


def DEFINITION(value: float, units: str, basis: str) -> EV:
    return EV(value=float(value), units=units, status="DEFINITION", evidence_class="definition",
              source="definition (no physical element)", uncertainty="exact by definition", basis=basis)


# --------------------------------------------------------------------------------------------------------------------
# model-derived transmission probability of a cylindrical hole (Cole, via Livesey 1998 Table 2.5)
# --------------------------------------------------------------------------------------------------------------------
COLE_SOURCE = ("R. G. Livesey 1998 (Lafferty (ed.), Foundations of Vacuum Science and Technology, Wiley), Table 2.5 "
               "'Transmission Probabilities for Cylindrical Tubes', column alpha (Cole [11]); transcribed from the open "
               "PDF accessed 2026-10-01 (see source register LIVESEY1998)")
# (l/d, alpha) exactly as tabulated (diffuse entry, diffusely reflecting walls, free molecular flow)
COLE_TABLE_2_5 = (
    (0.05, 0.952399), (0.15, 0.869928), (0.25, 0.801271), (0.35, 0.743410), (0.45, 0.694044), (0.5, 0.671984),
    (0.6, 0.632228), (0.7, 0.597364), (0.8, 0.566507), (0.9, 0.538975), (1.0, 0.514231), (1.5, 0.420055),
    (2.0, 0.356572), (2.5, 0.310525), (3.0, 0.275438), (3.5, 0.247735), (4.0, 0.225263), (4.5, 0.206641),
    (5.0, 0.190941), (10.0, 0.109304), (15.0, 0.076912), (20.0, 0.059422), (25.0, 0.048448), (30.0, 0.040913),
    (35.0, 0.035415), (40.0, 0.031225), (45.0, 0.027925), (50.0, 0.025258), (500.0, 0.002646),
)


def cole_transmission_probability(l_over_d: float) -> EV:
    """Free-molecular transmission probability of one cylindrical hole for diffuse incidence (Cole, Livesey Table 2.5).

    Tabulated points are reproduced exactly; between them log-log linear interpolation (our transformation; error
    between points not quantified here). Outside 0.05 <= l/d <= 500 the function refuses (no extrapolation)."""
    if not _finite(l_over_d):
        raise FilterStageError("l/d must be finite")
    lo, hi = COLE_TABLE_2_5[0][0], COLE_TABLE_2_5[-1][0]
    if not lo <= l_over_d <= hi:
        raise FilterStageError(f"l/d = {l_over_d} outside the tabulated domain [{lo}, {hi}] (no extrapolation)")
    a = None
    for (x0, y0), (x1, y1) in zip(COLE_TABLE_2_5, COLE_TABLE_2_5[1:]):
        if l_over_d == x0:
            a = y0
            break
        if l_over_d == x1:
            a = y1
            break
        if x0 < l_over_d < x1:
            t = (math.log(l_over_d) - math.log(x0)) / (math.log(x1) - math.log(x0))
            a = math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
            break
    tabulated = any(l_over_d == x for x, _ in COLE_TABLE_2_5)
    return EV(value=a, units="-", status="MODEL_DERIVED", evidence_class="model-derived", evidence_level=4,
              source=COLE_SOURCE,
              uncertainty=("tabulated value (Livesey: Berman Eq. (2.24) agrees with Cole within 0.13 %)" if tabulated
                           else "log-log interpolation between tabulated points; interpolation error not quantified"),
              basis=f"cylindrical hole l/d = {l_over_d}", domain="free molecular (Kn > 0.5), diffuse incidence, "
              "diffusely reflecting walls, 0.05 <= l/d <= 500")


def perforated_plate_alpha(l_over_d: float, open_fraction: float) -> EV:
    """Face-averaged diffuse-incidence transmission of a plate of identical cylindrical holes: phi * alpha_hole.

    Model assumptions (our construction, not from a source): holes act independently (no inter-hole or land-face
    re-entry), and molecules striking the solid land are returned to the incident side. ``open_fraction`` is a design
    variable of the candidate geometry, not evidence."""
    if not _finite(open_fraction) or not 0.0 < open_fraction <= 1.0:
        raise FilterStageError("open_fraction must be in (0, 1]")
    a = cole_transmission_probability(l_over_d)
    return EV(value=open_fraction * a.value, units="-", status="MODEL_DERIVED", evidence_class="model-derived",
              evidence_level=4, source=a.source + "; face average phi * alpha (our construction)",
              uncertainty=a.uncertainty + "; independent-hole assumption not quantified",
              basis=f"perforated plate, l/d = {l_over_d}, open fraction {open_fraction} (design candidate)",
              domain=a.domain + "; independent holes; land area reflects to the incident side")


def mean_speed_m_s(species: str, T_K: float) -> float:
    """cbar = sqrt(8 k T / (pi m)) (kinetic theory; Livesey Eq. (2.15) aperture conductance A * cbar / 4)."""
    return math.sqrt(8.0 * K_B * T_K / (math.pi * M_SPECIES[species]))


# --------------------------------------------------------------------------------------------------------------------
# protection, contamination and material records
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ProtectionFunction:
    target: str
    mechanism: str                     # qualitative description of how the element acts on the target
    capture_efficiency: EV             # fraction of the target stopped (TBD unless evidenced)
    evidence_note: str = ""

    def __post_init__(self):
        if self.target not in PROTECTION_TARGETS:
            raise FilterStageError(f"protection target {self.target!r} not in {PROTECTION_TARGETS}")
        if not self.mechanism.strip():
            raise FilterStageError("protection mechanism must be stated (qualitative)")

    def to_dict(self) -> dict:
        return {"target": self.target, "mechanism": self.mechanism,
                "capture_efficiency": self.capture_efficiency.to_dict(), "evidence_note": self.evidence_note}


@dataclass(frozen=True)
class MaterialApplicability:
    """Atomic-oxygen / material applicability of a filter material (P4 vocabulary; never PASS, never selected)."""
    material: str
    ao_compatibility: str = "INCOMPLETE_EVIDENCE"        # one of AO_GATE_OUTCOMES
    surrogate_label: str = "NONE"                        # NO_ATOMIC_O when the only evidence is N2 + O2 exposure
    o_recombination_probability: EV = field(default_factory=lambda: TBD(
        "O heterogeneous recombination probability on this material at the filter temperature and surface state "
        "(dedicated AO measurement; owner row 102 retains catalytic reference coupons)"))
    ao_erosion_yield: EV = field(default_factory=lambda: TBD(
        "AO erosion yield at the filter's O energy and fluence (dedicated AO source, row 132)", units="cm^3/atom"))
    evidence_refs: tuple = ()
    note: str = ""

    def __post_init__(self):
        if self.ao_compatibility not in AO_GATE_OUTCOMES:
            raise FilterStageError(f"ao_compatibility {self.ao_compatibility!r} not in {AO_GATE_OUTCOMES}")
        if self.surrogate_label not in SURROGATE_LABELS:
            raise FilterStageError(f"surrogate_label {self.surrogate_label!r} not in {SURROGATE_LABELS}")
        if self.ao_compatibility == "GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN" and self.surrogate_label == NO_ATOMIC_O:
            raise FilterStageError("N2 + O2 surrogate evidence (NO_ATOMIC_O) is never AO proof (owner row 132)")
        if self.ao_compatibility != "INCOMPLETE_EVIDENCE" and not self.evidence_refs:
            raise FilterStageError("an AO gate outcome other than INCOMPLETE_EVIDENCE needs evidence_refs")

    def to_dict(self) -> dict:
        return {"material": self.material, "application": "APP-FILTER (P4 materials application, A9.13 S6.6)",
                "ao_compatibility": self.ao_compatibility, "surrogate_label": self.surrogate_label,
                "o_recombination_probability": self.o_recombination_probability.to_dict(),
                "ao_erosion_yield": self.ao_erosion_yield.to_dict(), "evidence_refs": list(self.evidence_refs),
                "note": self.note, "final_material_status": "OPEN"}


# --------------------------------------------------------------------------------------------------------------------
# per-species transport
# --------------------------------------------------------------------------------------------------------------------
DIRECTIONS = ("f", "b")   # f: arriving at the inlet face (intake side); b: arriving at the outlet face (backflow)
PER_SPECIES_PARAMS = ("tau", "capture", "conversion", "product_to_outlet", "alpha_conductance")


@dataclass(frozen=True)
class SpeciesTransport:
    """Per-species, per-direction transmission / capture / conversion records; reflection is derived."""
    tau_f: EV
    capture_f: EV
    conversion_f: EV
    tau_b: EV
    capture_b: EV
    conversion_b: EV
    alpha_conductance: EV                       # diffuse-incidence transmission probability used for C_s
    product_to_outlet_f: EV | None = None       # fraction of forward conversion products leaving the outlet face
    product_to_outlet_b: EV | None = None

    def records(self) -> dict[str, EV]:
        out = {"tau_f": self.tau_f, "capture_f": self.capture_f, "conversion_f": self.conversion_f,
               "tau_b": self.tau_b, "capture_b": self.capture_b, "conversion_b": self.conversion_b,
               "alpha_conductance": self.alpha_conductance}
        if self.product_to_outlet_f is not None:
            out["product_to_outlet_f"] = self.product_to_outlet_f
        if self.product_to_outlet_b is not None:
            out["product_to_outlet_b"] = self.product_to_outlet_b
        return out


def tbd_species_transport(species: str) -> SpeciesTransport:
    """All-TBD transport for one species: the honest default for every real filter concept today."""
    w = f" for {species}"
    return SpeciesTransport(
        tau_f=TBD("forward transmission" + w + " at the declared forward incidence (measured on the element, or "
                  "model-derived from a defined geometry within its domain)"),
        capture_f=TBD("forward capture fraction" + w + " (adsorption / deposition; steady-state evidence)"),
        conversion_f=TBD(("forward conversion fraction" + w + " (O recombination to O2; dedicated AO evidence)")
                         if species in CONVERSION_PRODUCTS else
                         ("forward conversion fraction" + w + ": no conversion channel is modelled, so only an "
                          "evidenced 0 is admissible (otherwise a channel must be added to CONVERSION_PRODUCTS)")),
        tau_b=TBD("backflow transmission" + w + " (diffuse incidence from the plenum side)"),
        capture_b=TBD("backflow capture fraction" + w),
        conversion_b=TBD(("backflow conversion fraction" + w + " (O recombination to O2)")
                         if species in CONVERSION_PRODUCTS else
                         ("backflow conversion fraction" + w + ": no conversion channel modelled; only an evidenced "
                          "0 is admissible")),
        alpha_conductance=TBD("diffuse-incidence transmission probability" + w + " for the conductance law"),
        product_to_outlet_f=TBD("routing of forward conversion products to the outlet face" + w)
        if species in CONVERSION_PRODUCTS else None,
        product_to_outlet_b=TBD("routing of backflow conversion products to the outlet face" + w)
        if species in CONVERSION_PRODUCTS else None,
    )


# --------------------------------------------------------------------------------------------------------------------
# inlet / sensitivity / outlet records
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InletState:
    """State presented to the filter stage (from F1 at IF-A1, plus the downstream incident flux from F4).

    ``mdot_forward_kgps``: per-species mass flow arriving at the inlet face. ``mdot_back_incident_kgps``: per-species
    mass flow arriving at the outlet face from the plenum / compressor side (F4 coupling); it is required - a zero
    must be stated explicitly with ``back_incident_basis``. ``knudsen_number`` None = not established (the stage then
    refuses unless a sensitivity case declares the regime)."""
    mdot_forward_kgps: Mapping[str, float]
    mdot_back_incident_kgps: Mapping[str, float]
    back_incident_basis: str
    T_gas_K: float | None
    incidence: str
    knudsen_number: float | None
    label: str
    provenance: str
    # optional (A9.13 S6.19 thermal load): per-species energy flux arriving at the inlet face [W], from F1 / TPMC
    incident_power_W: Mapping[str, float] | None = None
    incident_power_source: str = ""

    def __post_init__(self):
        if self.label not in INLET_LABELS:
            raise FilterStageError(f"inlet label {self.label!r} not in {INLET_LABELS}")
        if self.incident_power_W is not None:
            if set(self.incident_power_W) != set(self.mdot_forward_kgps):
                raise FilterStageError("incident_power_W must name the same species as the flows")
            if any(not _finite(v) or v < 0.0 for v in self.incident_power_W.values()):
                raise FilterStageError("incident_power_W values must be finite and >= 0")
            if not self.incident_power_source.strip():
                raise FilterStageError("incident_power_W needs incident_power_source")
        if self.incidence not in INCIDENCES:
            raise FilterStageError(f"incidence {self.incidence!r} not in {INCIDENCES}")
        if not self.provenance.strip() or not self.back_incident_basis.strip():
            raise FilterStageError("inlet provenance and back_incident_basis must be stated")
        sp = set(self.mdot_forward_kgps)
        if sp != set(self.mdot_back_incident_kgps):
            raise FilterStageError("forward and back-incident flows must name the same species")
        for s in sp:
            if s not in M_SPECIES:
                raise FilterStageError(f"species {s!r} has no mass in abep_sim.constants.M_SPECIES")
            for d in (self.mdot_forward_kgps, self.mdot_back_incident_kgps):
                if not _finite(d[s]) or d[s] < 0.0:
                    raise FilterStageError(f"mass flow of {s} must be finite and >= 0")
        if self.T_gas_K is not None and (not _finite(self.T_gas_K) or self.T_gas_K <= 0.0):
            raise FilterStageError("T_gas_K must be > 0 or None")
        if self.knudsen_number is not None and (not _finite(self.knudsen_number) or self.knudsen_number <= 0.0):
            raise FilterStageError("knudsen_number must be > 0 or None")


@dataclass(frozen=True)
class SensitivityCase:
    """Explicit, labelled parametric sensitivity case (never evidence).

    ``overrides``: parameter id -> number (ids from ``FilterStage.parameter_ids()``). ``regime_assumption``:
    'free_molecular' to run without an established Knudsen number (recorded as an assumption)."""
    case_id: str
    label: str
    overrides: Mapping[str, float]
    rationale: str
    regime_assumption: str | None = None
    temperature_override_K: float | None = None

    def __post_init__(self):
        if "PARAMETRIC_SENSITIVITY" not in self.label:
            raise FilterStageError("a sensitivity case label must contain PARAMETRIC_SENSITIVITY")
        if not self.case_id.strip() or not self.rationale.strip():
            raise FilterStageError("sensitivity case needs an id and a rationale")
        for k, v in self.overrides.items():
            if not _finite(v):
                raise FilterStageError(f"override {k} must be finite")
        if self.regime_assumption is not None and self.regime_assumption not in REGIMES:
            raise FilterStageError(f"regime_assumption must be one of {REGIMES}")
        if self.temperature_override_K is not None and (not _finite(self.temperature_override_K)
                                                        or self.temperature_override_K <= 0):
            raise FilterStageError("temperature_override_K must be > 0")


@dataclass
class FilterResult:
    status: str
    label: str
    stage_id: str
    concept_id: str
    missing: list = field(default_factory=list)
    overrides_used: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    species: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)
    composition_net_downstream: dict | None = None
    mass_kg: float | None = None
    regime: dict = field(default_factory=dict)
    protection: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    # A9.13 S6.19 element records (filled by FilterStage.apply for every outcome, numeric or refused)
    role: str = ROLE_BASELINE
    admissible_as_baseline: bool = False
    interfaces: dict = field(default_factory=dict)
    retained_inventory: dict = field(default_factory=dict)
    thermal_load: dict = field(default_factory=dict)
    material_state: dict = field(default_factory=dict)
    validity_flags: dict = field(default_factory=dict)

    @property
    def numeric(self) -> bool:
        return self.status in ("NUMERIC", "NO_FILTER_IDENTITY")

    def to_dict(self) -> dict:
        return {"status": self.status, "label": self.label, "stage_id": self.stage_id, "concept_id": self.concept_id,
                "missing": self.missing, "overrides_used": self.overrides_used, "assumptions": self.assumptions,
                "species": self.species, "totals": self.totals,
                "composition_net_downstream": self.composition_net_downstream, "mass_kg": self.mass_kg,
                "regime": self.regime, "protection": self.protection, "materials": self.materials,
                "notes": self.notes, "role": self.role, "admissible_as_baseline": self.admissible_as_baseline,
                "interfaces": self.interfaces, "retained_inventory": self.retained_inventory,
                "thermal_load": self.thermal_load, "material_state": self.material_state,
                "validity_flags": self.validity_flags}

    def species_transmission(self) -> dict:
        """Species-resolved forward and reverse (backflow) transmission fractions and the conductance / pressure
        effect (A9.13 S6.19); NOT_EVALUATED when the stage refused."""
        if not self.numeric:
            return {"status": "NOT_EVALUATED", "reason": self.status, "missing": self.missing}
        return {"status": self.status, "label": self.label, "species": {
            s: {"forward_transmission": v["fractions_forward"]["transmitted"],
                "reverse_transmission": v["fractions_backflow"]["transmitted"],
                "forward_conversion": v["fractions_forward"]["converted"],
                "reverse_conversion": v["fractions_backflow"]["converted"],
                "forward_capture": v["fractions_forward"]["captured"],
                "reverse_capture": v["fractions_backflow"]["captured"],
                "conductance_m3_s": v["conductance_m3_s"], "delta_p_Pa": v["delta_p_Pa"]}
            for s, v in self.species.items()}}

    def to_f3_record(self) -> dict:
        """IF-A2 record for the compressor inlet (F3, abep_sim/design/compressor_synthesis.py IFD-F3-02)."""
        if not self.numeric:
            return {"interface": "IF-A2 filter -> compressor", "status": "NOT_EVALUATED", "reason": self.status,
                    "missing": self.missing, "label": self.label, "filter_role": self.role}
        return {"interface": "IF-A2 filter -> compressor", "status": self.status, "label": self.label,
                "mdot_s_net_downstream_kgps": {s: v["net_downstream_kgps"] for s, v in self.species.items()},
                "mdot_s_gross_downstream_kgps": {s: v["gross_downstream_kgps"] for s, v in self.species.items()},
                "w_s_mass": None if self.composition_net_downstream is None
                else self.composition_net_downstream["mass_fraction"],
                "x_s_mole": None if self.composition_net_downstream is None
                else self.composition_net_downstream["mole_fraction"],
                "delta_p_s_Pa": {s: v["delta_p_Pa"] for s, v in self.species.items()},
                "conductance_s_m3_s": {s: v["conductance_m3_s"] for s, v in self.species.items()},
                "filter_flow_effect_applied": self.status == "NUMERIC",
                "filter_retained_mass_rate_kgps": self.totals.get("captured_kgps"),
                "mass_kg": self.mass_kg, "overrides_used": self.overrides_used,
                "filter_role": self.role, "admissible_as_baseline": self.admissible_as_baseline,
                "validity_flags": self.validity_flags}

    def to_f1_record(self) -> dict:
        """Upstream return record for the intake (F1, abep_sim/design/intake_synthesis.py F1-ID-02): what the filter
        sends back toward the intake exit (forward reflection + backflow transmission + upstream products)."""
        if not self.numeric:
            return {"interface": "IF-A1 intake <- filter (return)", "status": "NOT_EVALUATED", "reason": self.status,
                    "missing": self.missing, "label": self.label}
        return {"interface": "IF-A1 intake <- filter (return)", "status": self.status, "label": self.label,
                "mdot_s_gross_upstream_kgps": {s: v["gross_upstream_kgps"] for s, v in self.species.items()}}


# --------------------------------------------------------------------------------------------------------------------
# the stage
# --------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FilterStage:
    stage_id: str
    concept_id: str
    kind: str                                  # 'none' | 'element'
    transport: Mapping[str, SpeciesTransport]  # per species
    forward_incidence: str                     # incidence for which tau_f records are valid
    regime: str = "free_molecular"
    face_area_m2: EV = field(default_factory=lambda: TBD("filter face area (geometry)", units="m^2"))
    areal_mass_kg_m2: EV = field(default_factory=lambda: TBD("areal mass of the element incl. frame (design + "
                                                                 "sourced densities, or weighed)", units="kg/m^2"))
    protection: tuple = ()
    materials: tuple = ()
    description: str = ""
    # A9.13 S6.3-S6.6 / S6.19
    role: str = ROLE_BASELINE
    element_temperature_K: EV = field(default_factory=lambda: TBD(
        "filter element temperature at the operating state (P3 coupled thermal network / measurement)", units="K"))
    energy_accommodation: EV = field(default_factory=lambda: TBD(
        "energy accommodation of the incident gas on the element (measured / sourced for the element material)"))
    contaminant_capacity_kg: EV = field(default_factory=lambda: TBD(
        "retained contaminant capacity (defined contamination environment + measured element retention; "
        "pre-registered before LOCK-1, A9.13 S6.3)", units="kg"))
    research_variant_evidence: tuple = ()      # (item, reference) pairs; catalytic research variant only

    def __post_init__(self):
        if self.kind not in ("none", "element"):
            raise FilterStageError("kind must be 'none' or 'element'")
        if self.role not in ROLES:
            raise FilterStageError(f"role {self.role!r} not in {ROLES}")
        if (self.kind == "none") != (self.role == ROLE_REFERENCE_BOUND):
            raise FilterStageError("only the no-element FC-00 case carries the reference-bound role, and it always "
                                   "does (A9.13 S6.5)")
        if self.research_variant_evidence and self.role != ROLE_CATALYTIC_RESEARCH:
            raise FilterStageError("research_variant_evidence belongs to the catalytic research variant only")
        for it in self.research_variant_evidence:
            if not (isinstance(it, tuple) and len(it) == 2 and it[0] in CATALYTIC_VARIANT_EVIDENCE
                    and isinstance(it[1], str) and it[1].strip()):
                raise FilterStageError(f"research_variant_evidence entries are (item in {CATALYTIC_VARIANT_EVIDENCE}, "
                                       "reference) pairs")
        if self.forward_incidence not in INCIDENCES:
            raise FilterStageError(f"forward_incidence must be one of {INCIDENCES}")
        if self.regime not in REGIMES:
            raise FilterStageError(f"regime must be one of {REGIMES}")
        for s, t in self.transport.items():
            if s not in M_SPECIES:
                raise FilterStageError(f"species {s!r} has no mass in abep_sim.constants.M_SPECIES")
            if s in CONVERSION_PRODUCTS:
                if t.product_to_outlet_f is None or t.product_to_outlet_b is None:
                    raise FilterStageError(f"{s} has a conversion channel: product routing records are required")
            else:
                for d in ("conversion_f", "conversion_b"):
                    r = getattr(t, d)
                    if r.status != "TBD" and r.value != 0.0:
                        raise FilterStageError(f"{s} has no conversion channel in CONVERSION_PRODUCTS; "
                                               f"{d} must be 0 or TBD")
        for p in self.protection:
            if not isinstance(p, ProtectionFunction):
                raise FilterStageError("protection entries must be ProtectionFunction")
        for m in self.materials:
            if not isinstance(m, MaterialApplicability):
                raise FilterStageError("materials entries must be MaterialApplicability")

    # ---- factories ---------------------------------------------------------------------------------------------
    @classmethod
    def none(cls, species=("O", "N2", "O2")) -> "FilterStage":
        """The 'no filter' option for trade studies: the definitional identity (no element)."""
        one = DEFINITION(1.0, "-", "no element: every molecule passes")
        zero = DEFINITION(0.0, "-", "no element: nothing captured / converted")
        tr = {s: SpeciesTransport(tau_f=one, capture_f=zero, conversion_f=zero, tau_b=one, capture_b=zero,
                                  conversion_b=zero, alpha_conductance=one,
                                  product_to_outlet_f=zero if s in CONVERSION_PRODUCTS else None,
                                  product_to_outlet_b=zero if s in CONVERSION_PRODUCTS else None)
              for s in species}
        return cls(stage_id="F2-NONE", concept_id="FC-00", kind="none", transport=tr,
                   forward_incidence="diffuse_thermal",
                   face_area_m2=DEFINITION(0.0, "m^2", "no element"),
                   areal_mass_kg_m2=DEFINITION(0.0, "kg/m^2", "no element"), role=ROLE_REFERENCE_BOUND,
                   element_temperature_K=DEFINITION(0.0, "K", "no element (no element temperature)"),
                   energy_accommodation=DEFINITION(0.0, "-", "no element: nothing absorbs energy"),
                   contaminant_capacity_kg=DEFINITION(0.0, "kg", "no element: nothing is retained"),
                   description="no filter stage: FC-00 ideal reference bound only (A9.13 S6.5), never an admissible "
                               "flight architecture under the RFP intake -> filter -> compressor chain")

    @classmethod
    def tbd(cls, stage_id: str, concept_id: str, species=("O", "N2", "O2"),
            forward_incidence: str = "diffuse_thermal", description: str = "", protection=(),
            materials=(), role: str = ROLE_BASELINE) -> "FilterStage":
        """A filter concept with every physical parameter TBD (fails closed in evidence mode). Default role: the
        inert / low-recombination baseline (A9.13 S6.4)."""
        return cls(stage_id=stage_id, concept_id=concept_id, kind="element",
                   transport={s: tbd_species_transport(s) for s in species}, forward_incidence=forward_incidence,
                   protection=tuple(protection), materials=tuple(materials), description=description, role=role)

    @classmethod
    def catalytic_research_variant(cls, stage_id: str, concept_id: str, species=("O", "N2", "O2"),
                                   forward_incidence: str = "diffuse_thermal", description: str = "",
                                   materials=(), research_variant_evidence=()) -> "FilterStage":
        """A deliberately catalytic O -> O2 element: a separately labelled research / contingency variant only (A9.13
        S6.4). It never replaces the baseline composition; every result carries its role and is never admissible as
        baseline."""
        return cls(stage_id=stage_id, concept_id=concept_id, kind="element",
                   transport={s: tbd_species_transport(s) for s in species}, forward_incidence=forward_incidence,
                   materials=tuple(materials), role=ROLE_CATALYTIC_RESEARCH,
                   research_variant_evidence=tuple(research_variant_evidence),
                   description=description or "catalytic O -> O2 research variant (not baseline, A9.13 S6.4)")

    # ---- parameters ----------------------------------------------------------------------------------------------
    def parameters(self) -> dict[str, EV]:
        out = {"face_area_m2": self.face_area_m2, "areal_mass_kg_m2": self.areal_mass_kg_m2}
        for s, t in self.transport.items():
            for k, ev in t.records().items():
                out[f"{k}.{s}"] = ev
        return out

    def parameter_ids(self) -> tuple:
        return tuple(self.parameters())

    def _resolve(self, case: SensitivityCase | None):
        params = self.parameters()
        unknown = sorted(set(case.overrides) - set(params)) if case else []
        if unknown:
            raise FilterStageError(f"sensitivity overrides name unknown parameters: {unknown}")
        vals, missing, used = {}, [], []
        for pid, ev in params.items():
            if case is not None and pid in case.overrides:
                vals[pid] = float(case.overrides[pid])
                used.append({"parameter": pid, "value": vals[pid], "replaces_status": ev.status,
                             "replaces_value": ev.value})
            elif ev.usable_as_evidence:
                vals[pid] = float(ev.value)
            else:
                missing.append({"parameter": pid, "status": ev.status,
                                "requires": ev.requires if ev.status == "TBD" else
                                f"{ev.status} record is not usable as evidence (class {ev.evidence_class})"})
        return vals, missing, used

    # ---- apply ---------------------------------------------------------------------------------------------------
    def apply(self, inlet: InletState, case: SensitivityCase | None = None) -> FilterResult:
        """Outlet state per species, or a refusal (see the module docstring for the fail-closed rules), annotated with
        the A9.13 S6.19 element records: role, interfaces, retained inventory, thermal load, material state and
        validity / domain flags."""
        res = self._apply_core(inlet, case)
        self._annotate(res, inlet)
        return res

    def _annotate(self, res: FilterResult, inlet: InletState) -> None:
        res.role = self.role
        # a baseline element is admissible as baseline only once its pre-registered acceptance is met by evidence
        # (A9.13 S6.3): never claimed here. FC-00 and the catalytic variant are never admissible as baseline.
        res.admissible_as_baseline = False
        res.interfaces = dict(INTERFACE_POSITION)
        cap_ev = self.contaminant_capacity_kg
        captured = res.totals.get("captured_kgps") if res.numeric else None
        res.retained_inventory = {
            "propellant_capture_rate_kgps": captured,
            "propellant_capture_status": "EVALUATED_FROM_STAGE_RECORDS" if captured is not None else "NOT_EVALUATED",
            "contaminant_capture_rate": "TBD (contamination environment / particle classes not defined; A9.13 S6.3)",
            "capacity_kg": cap_ev.to_dict(),
            "inventory_over_time": "retained_inventory_kg(result, duration_s)",
            "note": "compressor wear products are not credited to this filter (A9.13 S6.3)"}
        res.thermal_load = self._thermal_load(res, inlet)
        aos = sorted({m.ao_compatibility for m in self.materials}) or ["INCOMPLETE_EVIDENCE"]
        res.material_state = {
            "application": "APP-FILTER (P4, A9.13 S6.6)", "materials": [m.material for m in self.materials],
            "ao_compatibility": aos, "element_temperature_K": self.element_temperature_K.to_dict(),
            "erosion_state": "NOT_EVALUATED (AO erosion yield / fluence TBD per material)",
            "final_material_status": "OPEN" if self.kind == "element" else "NOT_APPLICABLE_NO_ELEMENT"}
        conv_o = None
        if res.numeric and "O" in res.species:
            conv_o = {d: res.species["O"][k]["converted"] for d, k in (("forward", "fractions_forward"),
                                                                       ("reverse", "fractions_backflow"))}
        res.validity_flags = {
            "status": res.status, "label": res.label, "regime": res.regime or None,
            "incidence_declared": self.forward_incidence, "incidence_inlet": inlet.incidence,
            "species_resolved": True, "folded_into_intake_efficiency": False,
            "reference_bound_only": self.role == ROLE_REFERENCE_BOUND,
            "research_variant_only": self.role == ROLE_CATALYTIC_RESEARCH,
            "research_variant_evidence_missing": [i for i in CATALYTIC_VARIANT_EVIDENCE
                                                  if i not in {e[0] for e in self.research_variant_evidence}]
            if self.role == ROLE_CATALYTIC_RESEARCH else [],
            "o_conversion_fraction": conv_o,
            "o_recombination_acceptance_limit": "TBD (pre-registered before LOCK-1 from evidence, A9.13 S6.3)",
            "acceptance_items_preregistration_pending": list(ACCEPTANCE_ITEMS),
            "baseline_protection_targets": list(BASELINE_PROTECTION_TARGETS),
            "not_credited_targets": dict(NOT_CREDITED_TARGETS),
            "f4_gap_model_supports_lossy_element": False}

    def _thermal_load(self, res: FilterResult, inlet: InletState) -> dict:
        """Absorbed thermal load bound: energy accommodation x incident energy flux, an UPPER bound on the gas-transfer
        term (every incident molecule is counted as striking the element). Recombination heat is added only when the
        conversion is zero; otherwise the load stays NOT_EVALUATED (the heat of O + O -> O2 is not sourced here)."""
        if self.kind == "none":
            return {"status": "NO_ELEMENT", "absorbed_upper_bound_W": 0.0}
        need = []
        if inlet.incident_power_W is None:
            need.append("incident energy flux per species at the inlet face (F1 / TPMC)")
        ea = self.energy_accommodation
        if not ea.usable_as_evidence:
            need.append(ea.requires or f"energy accommodation ({ea.status} is not usable evidence)")
        if not res.numeric:
            need.append(f"stage outcome {res.status}")
        elif res.totals.get("converted_kgps", 0.0) > 0.0:
            need.append("O recombination heat release (sourced) for the converted O flow")
        if need:
            return {"status": "NOT_EVALUATED", "requires": need}
        inc = sum(inlet.incident_power_W.values())
        return {"status": "UPPER_BOUND_GAS_TRANSFER", "absorbed_upper_bound_W": float(ea.value) * inc,
                "incident_W": inc, "energy_accommodation": float(ea.value), "recombination_heat_W": 0.0,
                "source": inlet.incident_power_source, "label": res.label}

    def _apply_core(self, inlet: InletState, case: SensitivityCase | None = None) -> FilterResult:
        label = LABEL_EVIDENCE
        if inlet.label == "NORMALIZED_UNIT_INPUT":
            label = LABEL_NORMALIZED
        if inlet.label == "PARAMETRIC_SENSITIVITY" or case is not None:
            label = LABEL_SENSITIVITY
        res = FilterResult(status="REFUSED_TBD", label=label, stage_id=self.stage_id, concept_id=self.concept_id,
                           protection=[p.to_dict() for p in self.protection],
                           materials=[m.to_dict() for m in self.materials])
        if case is not None:
            res.notes.append(f"sensitivity case {case.case_id}: {case.rationale}")
        if set(inlet.mdot_forward_kgps) != set(self.transport):
            raise FilterStageError(f"inlet species {sorted(inlet.mdot_forward_kgps)} != stage species "
                                   f"{sorted(self.transport)}")
        vals, missing, used = self._resolve(case)
        res.overrides_used = used

        # --- regime / incidence domain (not needed for the no-element identity)
        T = inlet.T_gas_K
        if case is not None and case.temperature_override_K is not None:
            T = case.temperature_override_K
            res.assumptions.append({"what": "gas temperature", "value_K": T, "basis": "sensitivity override"})
        if self.kind == "element":
            if inlet.incidence != self.forward_incidence:
                res.status = "OUT_OF_DOMAIN"
                res.missing = [{"parameter": "forward_incidence", "status": "OUT_OF_DOMAIN",
                                "requires": f"tau_f records valid for {self.forward_incidence}; inlet is "
                                            f"{inlet.incidence}"}]
                return res
            if inlet.knudsen_number is not None:
                res.regime = {"regime": self.regime, "knudsen_number": inlet.knudsen_number,
                              "criterion": f"Kn > {KN_MOLECULAR_MIN}", "source": KN_SOURCE}
                if not inlet.knudsen_number > KN_MOLECULAR_MIN:
                    res.status = "OUT_OF_DOMAIN"
                    res.missing = [{"parameter": "knudsen_number", "status": "OUT_OF_DOMAIN",
                                    "requires": f"free-molecular laws need Kn > {KN_MOLECULAR_MIN} (Livesey Table "
                                                f"2.1); a transitional / continuum law is not implemented"}]
                    return res
            elif case is not None and case.regime_assumption == "free_molecular":
                res.regime = {"regime": self.regime, "knudsen_number": None,
                              "criterion": "ASSUMED free molecular (sensitivity case; Kn not established)"}
                res.assumptions.append({"what": "flow regime", "value": "free_molecular",
                                        "basis": "sensitivity case regime_assumption"})
            else:
                missing.append({"parameter": "knudsen_number", "status": "TBD",
                                "requires": "Knudsen number at the filter (mean free path from the IF-A1 state and "
                                            "sourced collision cross sections; characteristic dimension of the "
                                            "element)"})
            if T is None:
                missing.append({"parameter": "T_gas_K", "status": "TBD",
                                "requires": "gas temperature at the filter (IF-A1)"})
        else:
            res.regime = {"regime": "no element", "knudsen_number": inlet.knudsen_number,
                          "criterion": "not applicable (identity)"}

        # product routing is only needed where conversion is non-zero (or unknown)
        missing = [m for m in missing if not self._routing_not_needed(m["parameter"], vals)]
        if missing:
            res.status = "REFUSED_TBD"
            res.missing = missing
            return res

        # --- per-species balances
        species = {}
        produced_down = {s: 0.0 for s in self.transport}
        produced_up = {s: 0.0 for s in self.transport}
        tot = {"incident_kgps": 0.0, "captured_kgps": 0.0, "converted_kgps": 0.0, "produced_kgps": 0.0,
               "gross_downstream_kgps": 0.0, "gross_upstream_kgps": 0.0}
        fractions = {}
        for s in self.transport:
            fr = {}
            for d in DIRECTIONS:
                tau, cap, conv = vals[f"tau_{d}.{s}"], vals[f"capture_{d}.{s}"], vals[f"conversion_{d}.{s}"]
                for name, v in (("tau", tau), ("capture", cap), ("conversion", conv)):
                    if not 0.0 <= v <= 1.0:
                        res.status = "NONPHYSICAL_INPUT"
                        res.missing = [{"parameter": f"{name}_{d}.{s}", "status": "NONPHYSICAL_INPUT",
                                        "requires": "a fraction in [0, 1]"}]
                        return res
                refl = 1.0 - tau - cap - conv
                if refl < -CONSERVATION_TOL:
                    res.status = "NONPHYSICAL_INPUT"
                    res.missing = [{"parameter": f"tau_{d}.{s} + capture_{d}.{s} + conversion_{d}.{s}",
                                    "status": "NONPHYSICAL_INPUT", "requires": "sum <= 1 (reflection >= 0)"}]
                    return res
                refl = max(refl, 0.0)
                if conv > 0.0 and s not in CONVERSION_PRODUCTS:
                    raise FilterStageError(f"{s}: conversion without a product channel")
                fr[d] = {"transmitted": tau, "reflected": refl, "captured": cap, "converted": conv,
                         "lost": cap + conv, "sum": tau + refl + cap + conv}
            if not 0.0 <= vals[f"alpha_conductance.{s}"] <= 1.0:
                res.status = "NONPHYSICAL_INPUT"
                res.missing = [{"parameter": f"alpha_conductance.{s}", "status": "NONPHYSICAL_INPUT",
                                "requires": "a probability in [0, 1]"}]
                return res
            fractions[s] = fr
            if (self.kind == "element" and self.forward_incidence == "diffuse_thermal"
                    and fr["f"]["lost"] == 0.0 and fr["b"]["lost"] == 0.0
                    and abs(fr["f"]["transmitted"] - fr["b"]["transmitted"]) > 1e-9):
                res.notes.append(f"{s}: tau_f != tau_b for diffuse incidence on a loss-free element; free-molecular "
                                 f"reciprocity (Livesey 1998 Sec. 2.2: the same transmission probability applies to "
                                 f"molecules arriving at either plane of a duct) is not satisfied - check the records "
                                 f"(unequal face areas or temperatures would have to be documented)")
        for s, fr in fractions.items():
            mf, mb = inlet.mdot_forward_kgps[s], inlet.mdot_back_incident_kgps[s]
            conv_mass_f, conv_mass_b = mf * fr["f"]["converted"], mb * fr["b"]["converted"]
            if conv_mass_f + conv_mass_b > 0.0:
                for prod, y in CONVERSION_PRODUCTS[s].items():
                    if prod not in self.transport:
                        res.status = "REFUSED_TBD"
                        res.missing = [{"parameter": f"species {prod}", "status": "TBD",
                                        "requires": f"product {prod} of {s} conversion must be a carried species"}]
                        return res
                    pf, pb = vals[f"product_to_outlet_f.{s}"], vals[f"product_to_outlet_b.{s}"]
                    if not (0.0 <= pf <= 1.0 and 0.0 <= pb <= 1.0):
                        res.status = "NONPHYSICAL_INPUT"
                        res.missing = [{"parameter": f"product_to_outlet.{s}", "status": "NONPHYSICAL_INPUT",
                                        "requires": "a fraction in [0, 1]"}]
                        return res
                    produced_down[prod] += y * (conv_mass_f * pf + conv_mass_b * pb)
                    produced_up[prod] += y * (conv_mass_f * (1 - pf) + conv_mass_b * (1 - pb))
        for s, fr in fractions.items():
            mf, mb = inlet.mdot_forward_kgps[s], inlet.mdot_back_incident_kgps[s]
            r = {
                "incident_forward_kgps": mf, "incident_back_kgps": mb,
                "forward": {k: mf * fr["f"][k] for k in ("transmitted", "reflected", "captured", "converted")},
                "backflow": {k: mb * fr["b"][k] for k in ("transmitted", "reflected", "captured", "converted")},
                "fractions_forward": fr["f"], "fractions_backflow": fr["b"],
                "produced_to_outlet_kgps": produced_down[s], "produced_to_inlet_kgps": produced_up[s],
            }
            r["gross_downstream_kgps"] = r["forward"]["transmitted"] + r["backflow"]["reflected"] + produced_down[s]
            r["gross_upstream_kgps"] = r["forward"]["reflected"] + r["backflow"]["transmitted"] + produced_up[s]
            r["net_downstream_kgps"] = r["gross_downstream_kgps"] - mb
            ins = mf + mb + produced_down[s] + produced_up[s]
            outs = (r["gross_downstream_kgps"] + r["gross_upstream_kgps"] + r["forward"]["captured"]
                    + r["backflow"]["captured"] + r["forward"]["converted"] + r["backflow"]["converted"])
            r["species_balance_residual_kgps"] = ins - outs
            # conductance and pressure difference for the net throughput (free molecular)
            if self.kind == "none":
                r["conductance_m3_s"] = "INFINITE_NO_ELEMENT"
                r["delta_p_Pa"] = 0.0
                r["delta_p_per_net_kgps_Pa"] = 0.0
            else:
                A, a = vals["face_area_m2"], vals[f"alpha_conductance.{s}"]
                C = a * A * mean_speed_m_s(s, T) / 4.0
                r["conductance_m3_s"] = C
                if C > 0.0:
                    coef = K_B * T / (M_SPECIES[s] * C)      # Pa per (kg/s) of net throughput
                    r["delta_p_per_net_kgps_Pa"] = coef
                    r["delta_p_Pa"] = coef * r["net_downstream_kgps"]
                else:
                    r["delta_p_per_net_kgps_Pa"] = "UNBOUNDED_ZERO_CONDUCTANCE"
                    r["delta_p_Pa"] = "UNBOUNDED_ZERO_CONDUCTANCE"
            species[s] = r
            tot["incident_kgps"] += mf + mb
            tot["captured_kgps"] += r["forward"]["captured"] + r["backflow"]["captured"]
            tot["converted_kgps"] += r["forward"]["converted"] + r["backflow"]["converted"]
            tot["produced_kgps"] += produced_down[s] + produced_up[s]
            tot["gross_downstream_kgps"] += r["gross_downstream_kgps"]
            tot["gross_upstream_kgps"] += r["gross_upstream_kgps"]
        tot["mass_balance_residual_kgps"] = (tot["incident_kgps"] - tot["gross_downstream_kgps"]
                                             - tot["gross_upstream_kgps"] - tot["captured_kgps"]
                                             - tot["converted_kgps"] + tot["produced_kgps"])
        tot["converted_minus_produced_kgps"] = tot["converted_kgps"] - tot["produced_kgps"]
        scale = max(tot["incident_kgps"], 1e-300)
        if abs(tot["mass_balance_residual_kgps"]) > 1e-9 * scale or \
                abs(tot["converted_minus_produced_kgps"]) > 1e-9 * scale:
            raise FilterStageError(f"internal conservation failure: {tot}")
        res.species = species
        res.totals = tot
        net = {s: v["net_downstream_kgps"] for s, v in species.items()}
        if all(v >= 0.0 for v in net.values()) and sum(net.values()) > 0.0:
            mt = sum(net.values())
            nmol = {s: net[s] / M_SPECIES[s] for s in net}
            nt = sum(nmol.values())
            res.composition_net_downstream = {"mass_fraction": {s: net[s] / mt for s in net},
                                              "mole_fraction": {s: nmol[s] / nt for s in net}}
        else:
            res.composition_net_downstream = None
            res.notes.append("net downstream flow is zero or reversed for at least one species: composition of the "
                             "net delivered flow is not defined (NET_REVERSE_OR_ZERO)")
        res.mass_kg = vals["face_area_m2"] * vals["areal_mass_kg_m2"]
        res.status = "NO_FILTER_IDENTITY" if self.kind == "none" else "NUMERIC"
        return res

    @staticmethod
    def _routing_not_needed(pid: str, vals: dict) -> bool:
        """product routing records are only needed when the matching conversion is non-zero or unknown."""
        if not pid.startswith("product_to_outlet_"):
            return False
        d, s = pid[len("product_to_outlet_"):].split(".", 1)
        conv = vals.get(f"conversion_{d}.{s}")
        return conv is not None and conv == 0.0

    # ---- F4 coupling ---------------------------------------------------------------------------------------------
    def backflow_coupling(self, T_gas_K: float | None, case: SensitivityCase | None = None) -> dict:
        """Linear boundary coefficients for the plenum model (F4, abep_sim/design/plenum_feed.py F4-ID-03): per unit mass flow
        arriving at the outlet face, the fractions transmitted upstream, reflected back to the plenum, captured and
        converted, plus the free-molecular conductance. Refuses (status REFUSED_TBD) when any record is unusable."""
        vals, missing, used = self._resolve(case)
        need = []
        for s in self.transport:
            need += [f"tau_b.{s}", f"capture_b.{s}", f"conversion_b.{s}", f"alpha_conductance.{s}"]
        need.append("face_area_m2")
        miss = [m for m in missing if m["parameter"] in need]
        if self.kind == "element" and T_gas_K is None:
            miss.append({"parameter": "T_gas_K", "status": "TBD", "requires": "gas temperature at the filter"})
        label = LABEL_SENSITIVITY if case is not None else LABEL_EVIDENCE
        if miss:
            return {"status": "REFUSED_TBD", "label": label, "missing": miss}
        out = {}
        for s in self.transport:
            tau, cap, conv = vals[f"tau_b.{s}"], vals[f"capture_b.{s}"], vals[f"conversion_b.{s}"]
            refl = 1.0 - tau - cap - conv
            if min(tau, cap, conv) < 0.0 or refl < -CONSERVATION_TOL:
                return {"status": "NONPHYSICAL_INPUT", "label": label, "species": s}
            C = ("INFINITE_NO_ELEMENT" if self.kind == "none"
                 else vals[f"alpha_conductance.{s}"] * vals["face_area_m2"] * mean_speed_m_s(s, T_gas_K) / 4.0)
            out[s] = {"to_upstream": tau, "reflected_to_plenum": max(refl, 0.0), "captured": cap, "converted": conv,
                      "conductance_m3_s": C}
        return {"status": "NUMERIC", "label": label, "species": out,
                "overrides_used": [u["parameter"] for u in used]}

    def to_dict(self) -> dict:
        return {"stage_id": self.stage_id, "concept_id": self.concept_id, "kind": self.kind, "role": self.role,
                "interfaces": dict(INTERFACE_POSITION),
                "forward_incidence": self.forward_incidence, "regime": self.regime,
                "description": self.description,
                "parameters": {k: v.to_dict() for k, v in self.parameters().items()},
                "protection": [p.to_dict() for p in self.protection],
                "materials": [m.to_dict() for m in self.materials]}


# --------------------------------------------------------------------------------------------------------------------
# repository placeholders (recorded, never used silently)
# --------------------------------------------------------------------------------------------------------------------
def repository_placeholder_values() -> dict:
    """Read (without modifying) the current repository filter defaults from abep_sim.intake_tpmc.IntakeGeometry."""
    from ..intake_tpmc import IntakeGeometry   # local import: only to record the placeholder values
    g = IntakeGeometry()
    return {"filter": g.filter, "filter_open_frac": g.filter_open_frac,
            "filter_transmission": g.filter_transmission, "filter_mass_per_m2": g.filter_mass_per_m2,
            "area_m2": g.area_m2, "T_wall_K": g.T_wall_K}


def placeholder_sensitivity_case(stage: FilterStage) -> SensitivityCase:
    """The repository's present filter law as an explicit, labelled sensitivity case (PLACEHOLDER_NOT_A_FLIGHT_DESIGN).

    Mapping of the law in abep_sim/intake_tpmc.py intake_response (filter branch) onto this interface:
      forward: eta_c *= filter_open_frac * filter_transmission ** 0.5  -> tau_f = open_frac * sqrt(transmission)
      backward: K_back *= filter_transmission                           -> tau_b = transmission
      no loss term in the law                                            -> capture = conversion = 0
      conductance: 'thermal Clausing factor of the filter element'      -> alpha_conductance = transmission
      mass: filter_mass_per_m2 * area_m2 (also intake.py / system.py 0.8 * area)
    Face area and gas temperature take the IntakeGeometry defaults (area_m2, T_wall_K), also placeholders.
    The regime is ASSUMED free molecular (the repository states Kn >> 1 at 180-230 km for the intake, not for a
    filter). Species-independent, as in the repository law."""
    p = repository_placeholder_values()
    ov = {"face_area_m2": p["area_m2"], "areal_mass_kg_m2": p["filter_mass_per_m2"]}
    for s in stage.transport:
        ov[f"tau_f.{s}"] = p["filter_open_frac"] * p["filter_transmission"] ** 0.5
        ov[f"tau_b.{s}"] = p["filter_transmission"]
        ov[f"alpha_conductance.{s}"] = p["filter_transmission"]
        for d in DIRECTIONS:
            ov[f"capture_{d}.{s}"] = 0.0
            ov[f"conversion_{d}.{s}"] = 0.0
    return SensitivityCase(
        case_id="SC-PLACEHOLDER-REPO-FILTER",
        label="PARAMETRIC_SENSITIVITY / PLACEHOLDER_NOT_A_FLIGHT_DESIGN (repository filter defaults)",
        overrides=ov, regime_assumption="free_molecular", temperature_override_K=p["T_wall_K"],
        rationale="reproduces the unsourced repository filter law (abep_sim/intake_tpmc.py IntakeGeometry filter_* "
                  "defaults) so its effect can be bounded; not evidence, not a flight design")


def retained_inventory_kg(result: FilterResult, duration_s: float) -> dict:
    """Propellant mass retained by the element over ``duration_s`` at the result's capture rate, against the element's
    capacity record (A9.13 S6.19 retained inventory). NOT_EVALUATED when the stage refused."""
    if not _finite(duration_s) or duration_s < 0.0:
        raise FilterStageError("duration_s must be finite and >= 0")
    rate = result.retained_inventory.get("propellant_capture_rate_kgps")
    if rate is None:
        return {"status": "NOT_EVALUATED", "reason": result.status}
    cap = result.retained_inventory.get("capacity_kg", {})
    m = rate * duration_s
    capv = cap.get("value")
    return {"status": "EVALUATED_FROM_STAGE_RECORDS", "label": result.label, "retained_kg": m,
            "capacity_kg": capv, "capacity_status": cap.get("status"),
            "capacity_margin_kg": (capv - m) if isinstance(capv, (int, float)) else "NOT_EVALUATED (capacity TBD)"}
