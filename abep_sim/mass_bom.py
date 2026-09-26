"""Hierarchical mass properties (Phase 4, items 30, 31, 32).

Every line: CBE from geometry/physics, MGA by item class, MEV = CBE*(1+MGA). Tanks from pressure-vessel sizing,
Hall magnetic circuit from required flux, structure from launch loads (quasi-static + first-mode stiffness),
thermal from thermal.py, PPU from ppu.py, intake/compressor from Phases 1-2. Also centre of mass / inertia
about the thrust axis for the propulsion assembly (rough, for AOCS interface).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from .materials import DB

MU0 = 4e-7 * math.pi
MGA = {"new": 0.30, "modified": 0.15, "existing": 0.05, "calculated": 0.10}


def xe_tank(m_xe_kg: float, p_MPa: float = 15.0, material: str = "Ti6Al4V", safety: float = 2.0, rho_xe_kg_m3: float = 1600.0) -> dict:
    """Spherical tank: t = p r / (2 sigma_allow); mass = 4 pi r^2 t rho + fittings. Minimum gauge 0.8 mm."""
    V = m_xe_kg / rho_xe_kg_m3 * 1.05
    r = (3 * V / (4 * math.pi)) ** (1 / 3)
    m = DB[material]
    t = max(p_MPa * 1e6 * r / (2 * m.yield_MPa * 1e6 / safety), 0.8e-3)
    mass = 4 * math.pi * r ** 2 * t * m.density + 0.35
    return {"V_L": V * 1e3, "r_mm": r * 1e3, "t_mm": t * 1e3, "mass_kg": mass, "material": material}


def reservoir_vessel(V_m3: float, material: str = "Al6061") -> dict:
    """Low-pressure vessel: minimum gauge dominates (p << 1 kPa)."""
    r = (3 * V_m3 / (4 * math.pi)) ** (1 / 3)
    m = DB[material]; t = 1.0e-3
    return {"mass_kg": 4 * math.pi * r ** 2 * t * m.density + 0.25, "t_mm": t * 1e3}


def hall_magnetic_circuit(B_gap_T: float, r_in: float, r_out: float, L: float, material: str = "SmCo_bare",
                          H_op_A_m: float = 4.0e5, leakage: float = 3.0, yoke_t_m: float = 0.004, iron_rho: float = 7800.0) -> dict:
    """Permanent-magnet circuit sized by MMF and flux: magnet length l_m = leakage * B_gap * gap / (mu0 * H_op),
    magnet area = flux / B_m (B_m ~ 0.8 T at the operating point), for inner and outer magnet rings;
    soft-iron yoke: cylindrical shell around the channel + two end plates + inner core."""
    gap = r_out - r_in
    l_m = leakage * B_gap_T * gap / (MU0 * H_op_A_m)
    flux = B_gap_T * 2 * math.pi * 0.5 * (r_in + r_out) * L * 0.5     # radial flux across half the channel length
    A_m = leakage * flux / 0.8
    V_mag = 2 * l_m * A_m                                              # inner + outer rings
    m_mag = V_mag * DB[material].density
    r_y = r_out + 0.015
    m_shell = 2 * math.pi * r_y * L * yoke_t_m * iron_rho
    m_plates = 2 * math.pi * (r_y ** 2) * yoke_t_m * iron_rho
    m_core = math.pi * (r_in - 0.004) ** 2 * L * iron_rho * 0.5
    return {"m_magnets_kg": m_mag, "m_poles_kg": m_shell + m_plates + m_core, "mass_kg": m_mag + m_shell + m_plates + m_core,
            "l_m_mm": l_m * 1e3}


def hall_channel_mass(r_in, r_out, L, t_wall_mm=4.0, material="BN") -> float:
    m = DB[material]
    A = 2 * math.pi * (r_in + r_out) * L
    return A * t_wall_mm * 1e-3 * m.density + 0.3     # + anode/gas distributor


def structure_mass(m_supported_kg: float, span_m: float, g_qs: float = 12.0, f_min_Hz: float = 60.0,
                   material: str = "Al6061", core_h_m: float = 0.025, core_rho: float = 50.0) -> dict:
    """Secondary structure of the propulsion module: aluminium-faced honeycomb sandwich deck (span x span) sized by
    first-mode stiffness (distributed mass, simply supported: f = (pi/2L^2) sqrt(D/(m/A)) ) and by quasi-static
    bending at g_qs; plus intake support frame and brackets."""
    m = DB[material]
    E = m.E_GPa * 1e9
    A = span_m * span_m
    # sandwich bending stiffness per unit width D = E t_f h^2 / 2 ; mass per area mu = 2 t_f rho + core
    t_f = 0.3e-3
    for _ in range(60):
        D = E * t_f * core_h_m ** 2 / 2.0
        mu = 2 * t_f * m.density + core_h_m * core_rho + m_supported_kg / A
        f = (math.pi / (2 * span_m ** 2)) * math.sqrt(D / mu)
        F = m_supported_kg * 9.81 * g_qs
        sigma = (F * span_m / 8) / (t_f * core_h_m * span_m)        # face-sheet stress, sandwich
        if f >= f_min_Hz and sigma < m.yield_MPa * 1e6 / 1.5:
            break
        t_f *= 1.1
    mass_deck = A * (2 * t_f * m.density + core_h_m * core_rho)
    frame = 0.10 * m_supported_kg + 1.5 * span_m                     # brackets, inserts, struts, intake frame
    # The mounting deck is spacecraft-provided (DRDO bus); the propulsion module carries only its frame/brackets.
    return {"panel_t_mm": t_f * 1e3, "core_mm": core_h_m * 1e3, "mass_kg": frame, "deck_if_own_kg": mass_deck,
            "first_mode_Hz": f, "sigma_MPa": sigma / 1e6}


@dataclass
class BOMLine:
    name: str
    cbe_kg: float
    cls: str
    note: str = ""

    @property
    def mga(self):
        return MGA[self.cls]

    @property
    def mev_kg(self):
        return self.cbe_kg * (1 + self.mga)


def build_bom(parts: dict, classes: dict, notes: dict | None = None) -> dict:
    lines = [BOMLine(k, v, classes.get(k, "new"), (notes or {}).get(k, "")) for k, v in parts.items()]
    cbe = sum(l.cbe_kg for l in lines); mev = sum(l.mev_kg for l in lines)
    return {"lines": lines, "cbe_kg": cbe, "mev_kg": mev, "mga_kg": mev - cbe,
            "table": [(l.name, round(l.cbe_kg, 2), l.cls, round(l.mev_kg, 2), l.note) for l in lines]}


# =====================================================================================================================
# Architecture mass BOM skeleton v1 (CBE / MGA / MEV) for 'hall_only', 'rf_hall' and 'ecr_hall'.
# =====================================================================================================================
# Everything above this banner is the legacy v1.7 mass model. archengine.py and system.py import it, so it is left
# byte-identical (goldens must not move). Its numbers (the MGA dict, tank fittings, magnet leakage, frame fractions, ...)
# carry no citation and are NOT used below.
#
# The skeleton below is pure: it is not wired into archengine, reads no file at import time and holds no physical,
# efficiency or mass default. Every mass is a sourced value, a scaling relation with sourced inputs, or TBD; a roll-up
# with a TBD item is refused unless the caller explicitly asks for a partial roll-up that lists the missing items.
# Margin policy: ESA SRE-PA/2011.097 Issue 1 Rev 3 (open document, see MASS_BOM_SOURCES). System margin: PROPOSED.
# Document: docs/architecture_comparison/mass_bom/MASS_BOM.md; data: mass_bom_v1.json (built by
# `python -m abep_sim.mass_bom build`, checked by `python -m abep_sim.mass_bom check`).
import copy as _copy
import json as _json
import re as _re
import sys as _sys
from pathlib import Path as _Path

BOM_VERSION = "mass_bom_v1"
BOM_CREATED = "2026-09-26"
BOM_SCHEMA_PATH = "schemas/architecture_comparison/mass_bom_v1.schema.json"
BOM_DOC_PATH = "docs/architecture_comparison/mass_bom/mass_bom_v1.json"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
MASS_CLASSES = ("dry", "propellant")
# Bases on which the hard-gate matrix (G3_mass, fail_sufficient_bases) accepts a FAIL-side lower bound.
G3_FAIL_BASES = ("hard_physical_bound", "measurement_vyovrinda", "measurement_same_hardware", "model_closure_independent")
# P5 calibration nuisance (CLAUDE.md, layer 1) is never a design variable: any such key in a BOM item is rejected.
CALIBRATION_NUISANCE_KEYS = frozenset({
    "p5_registration", "registration", "coil_shape", "historical_coil_shape", "divergence_reading",
    "beam_efficiency_reading", "facility_interpretation", "facility_ingestion_interpretation"})
# Keys that would mark a mass as derived from a Hall transport closure (G3 is closure-independent: always rejected).
HALL_CLOSURE_KEYS = frozenset({"hall_closure_id", "ensemble_member_id", "screening_candidate_id", "transport_closure"})

MASS_BOM_SOURCES = {
    "ESA_MARGIN_2012": {
        "citation": "ESA SRE-PA & D-TEC staff, 'Margin philosophy for science assessment studies', "
                    "SRE-PA/2011.097/, Issue 1, Revision 3, 15/06/2012 (technical note, marked 'ESA UNCLASSIFIED - For "
                    "Official Use', publicly posted on sci.esa.int)",
        "url": "https://sci.esa.int/documents/34375/36249/"
               "1567260131067-Margin_philosophy_for_science_assessment_studies_1.3.pdf",
        "accessed": "2026-09-26",
        "access": "open, full text (PDF, 11 pages)",
        "sha256_as_fetched": "0ddc1b0116f96b2a4f26732dfe67ca682b7df397156c0ed6809c3c0392cc9501",
        "sections_used": "2.1.1 Margin on total dry mass (R-M1-1 ... R-M1-10), pages 5-6",
        "kind": "margin policy (a convention, not physical evidence)",
        "applicability": "written for ESA science-mission assessment studies at spacecraft level; applying it to a "
                         "propulsion subsystem is this BOM's choice (PROPOSED to the owner)",
    },
    "RFP_MASS_AS_RECORDED": {
        "citation": "abep_sim/constants.py RFPConstraints.mass_max_kg (docstring 'Hard limits from Part III Para 2 of "
                    "the RFP'); CLAUDE.md '< 40 kg'; docs/HISTORY.md v0.1 table '< 40 kg total incl. intake, "
                    "compressor, PSE, Xe + tank, structure, 10 % margin'",
        "kind": "requirement as recorded in this repository",
        "verify": "verify against the RFP document (DTDF/06/13516/DSP/ABEP/X/L/M/01)",
    },
    "THIN_WALL_SPHERE": {
        "citation": "membrane equilibrium of a thin-walled pressurised sphere, sigma = p r / (2 t); derivation in "
                    "docs/architecture_comparison/mass_bom/MASS_BOM.md (section 'Tank lower-bound relation')",
        "kind": "model-derived (first-principles relation, no fitted constant)",
    },
    "HARD_GATE_MATRIX": {
        "citation": "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json, gate G3_mass (hard-gate lane; "
                    "referenced by path only, not present in this worktree at creation, never imported)",
        "kind": "shared contract (read-only reference)",
    },
    "POWER_BOUNDARY": {
        "citation": "abep_sim/arch_boundary.py, BOUNDARY_VERSION 'bus_power_boundary_v1' (power-boundary lane; resolved "
                    "lazily by check_power_boundary_coverage(), never imported at module load)",
        "kind": "shared contract (read-only reference)",
    },
}

_ESA = "ESA_MARGIN_2012"
MATURITY_CATEGORIES = {
    "ecss_ab_off_the_shelf": {
        "mga": 0.05, "ecss_category": "A/B", "requirement": "R-M1-41 (also R-M2-41)", "source": _ESA,
        "text": "≥ 5 % for “Off-The-Shelf” items (ECSS Category: A / B, see ECSS-E-ST-10-02C)",
        "evidence_class": "assumed", "note": "policy minimum ('≥'); applied at the minimum"},
    "ecss_c_minor_modification": {
        "mga": 0.10, "ecss_category": "C", "requirement": "R-M2-42 (label as printed under R-M1-4)", "source": _ESA,
        "text": "≥ 10 % for “Off-The-Shelf” items requiring minor modifications (ECSS Category: C, see "
                "ECSS-E-ST-10-02C)",
        "evidence_class": "assumed", "note": "policy minimum ('≥'); applied at the minimum"},
    "ecss_d_new_or_major_modification": {
        "mga": 0.20, "ecss_category": "D", "requirement": "R-M1-43 (also R-M2-43)", "source": _ESA,
        "text": "≥ 20 % for new designed / developed items, or items requiring major modifications or re-design "
                "(ECSS Category: D, see ECSS-E-ST-10-02C)",
        "evidence_class": "assumed", "note": "policy minimum ('≥'); applied at the minimum"},
    "propellant_not_equipment": {
        "mga": 0.0, "ecss_category": None, "requirement": "R-M1-3, R-M1-4, R-M1-6", "source": _ESA,
        "text": "maturity margins are applied 'at equipment level' (R-M1-4); the system margin shall 'not include any "
                "propellant residuals or unused propellant' (R-M1-3); residuals are a separate 2 % allocation (R-M1-6)",
        "evidence_class": "inferred",
        "note": "the document states no maturity margin for propellant; MGA 0 is this BOM's reading of its structure"},
    "policy_allocation_nominal": {
        "mga": 0.0, "ecss_category": None, "requirement": "R-M1-7, R-M1-2", "source": _ESA,
        "text": "'Harness mass shall be considered to be at least 5 % of nominal dry mass' (R-M1-7); the nominal dry "
                "mass includes the design maturity margins (R-M1-2)",
        "evidence_class": "inferred",
        "note": "the allocation is already defined on the nominal (margin-including) dry mass, so no further MGA is "
                "added (this BOM's reading)"},
}

SYSTEM_MARGIN = {
    "proposed_fraction": 0.20,
    "status": "PROPOSED",
    "basis": "ESA R-M1-1: 'The total dry mass at launch of the spacecraft shall include an ESA system level mass margin "
             "of 20 % of the nominal dry mass at launch (this shall include the equipment level margin as specified in "
             "R-M1-4).' Spacecraft-level requirement; applying it to the propulsion subsystem is a proposal to the owner.",
    "source": _ESA,
    "base": "nominal dry mass = sum over dry items of CBE x (1 + MGA); propellant excluded (R-M1-3)",
    "alternatives": [
        {"id": "rfp_r3_10pct", "fraction": 0.10, "status": "RFP_AS_RECORDED",
         "text": "'10 % margin' in the recorded RFP constraint (docs/HISTORY.md v0.1, hard-gate R3); whether it is a "
                 "system margin, a growth allowance or both is unresolved (hard-gate OD7). Verify against RFP document."},
    ],
}

ESA_HARNESS_FRACTION = {"value": 0.05, "unit": "1", "source": _ESA, "evidence_class": "assumed",
                        "note": "R-M1-7 floor ('at least 5 % of nominal dry mass'), policy allocation"}
ESA_RESIDUAL_FRACTION = {"value": 0.02, "unit": "1", "source": _ESA, "evidence_class": "assumed",
                         "note": "R-M1-6 'A 2% of propellant residuals shall be added to the propellant calculated'"}

_D = {"category": "ecss_d_new_or_major_modification", "status": "PROPOSED",
      "rationale": "no Vyovrinda design and no selected part exist; placed in the highest ESA category (D, 20 %) until a "
                   "design or heritage part is identified. Conservative on the PASS side; the FAIL-side screen is "
                   "margin-free and does not depend on it."}
_PROP = {"category": "propellant_not_equipment", "status": "PROPOSED", "rationale": "propellant, not equipment"}
_HARN = {"category": "policy_allocation_nominal", "status": "PROPOSED",
         "rationale": "ESA R-M1-7 harness allocation on nominal dry mass until a harness design exists"}
_NO_LB = "no closure-independent lower bound with architecture scope is available"


def _tbd(requires: str) -> dict:
    return {"basis": "TBD", "requires": requires}


def _no_lb(requires: str) -> dict:
    return {"basis": "none", "requires": requires}


def _item(iid, name, scope, rfp_block, gate_element, boundary, cbe_requires, lb_requires, *, mass_class="dry",
          hall_related=False, maturity=None, cbe=None, lower_bound=None, notes=""):
    return {"id": iid, "name": name, "scope": scope, "rfp_block": rfp_block, "gate_element": gate_element,
            "power_boundary_components": list(boundary), "mass_class": mass_class, "hall_related": hall_related,
            "maturity": dict(maturity or _D), "cbe": cbe or _tbd(cbe_requires),
            "lower_bound": lower_bound or _no_lb(lb_requires), "notes": notes}


_HALL_NOTE = ("Hall-related: the mass of a given head design is closure-independent. No unadmitted closure (the nine "
              "sgb-screen candidates or any other) may size or scale it; the credible set is empty (CLAUDE.md). The "
              "legacy hall_channel_mass()/hall_magnetic_circuit() defaults above are unsourced and not used.")
_PREION_NOTE = ("Includes its own mounting, harness and thermal-control increments (PROPOSED accounting convention, so "
                "that common items keep identical definitions).")

_CATALOG = (
    # ---- common items (identical definitions in every architecture) ----
    _item("intake", "Intake (atmospheric collector)", "common", "atmospheric path: intake", "intake", (),
          "Vyovrinda intake geometry (owner: frontal area, L/d, collimator) and sourced material densities, or a "
          "measured mass; abep_sim/intake_tpmc.py gives collection performance, not mass",
          _NO_LB + "; a bound needs a minimum frontal area (from drag/flow requirements) and a minimum areal mass, "
          "both sourced"),
    _item("filter", "Filter (atmospheric path)", "common", "atmospheric path: filter", "filter", (),
          "filter concept and geometry (not defined in this repository) or a measured mass", _NO_LB),
    _item("compressor", "Compressor", "common", "atmospheric path: compressor", "compressor", ("compressor",),
          "compressor design (geometry, materials, motor) or a measured breadboard mass", _NO_LB),
    _item("atmospheric_gas_chamber", "Atmospheric gas chamber", "common", "atmospheric path: atmospheric gas chamber",
          "atmospheric_gas_chamber", (), "chamber volume and operating pressure (design inputs) and wall material "
          "(sourced), or a measured mass", _NO_LB),
    _item("atmospheric_valve", "Atmospheric-path valve(s) and flow control", "common", "atmospheric path: valve",
          "valves_and_flow_control", ("flow_control",), "selected valve / flow-controller parts (supplier "
          "measured mass) and redundancy scheme", _NO_LB),
    _item("xe_valve_and_flow_control", "Xe-path valve(s), regulator and flow control", "common", "Xe path: valve",
          "valves_and_flow_control", ("flow_control",), "selected Xe valve / regulator / flow-controller parts "
          "(supplier measured mass) and redundancy scheme", _NO_LB),
    _item("xe_tank", "Xe tank (Xe chamber)", "common", "Xe path: Xe chamber", "xenon_chamber_and_xenon_load", (),
          "declared Xe load, storage pressure and temperature (design inputs), Xe density at storage conditions "
          "(sourced), tank concept and material, or a supplier tank mass",
          "a lower bound becomes available once its inputs are declared: thin_wall_sphere_membrane (THIN_WALL_SPHERE) "
          "with MEOP, burst factor, wall strength and density, and internal volume (ESA R-M1-10: sized for the "
          "propellant plus at least 10 %), each sourced; monolithic isotropic metal shell only"),
    _item("xe_load", "Xe propellant load (declared allocation)", "common", "Xe path: Xe chamber",
          "xenon_chamber_and_xenon_load", (), "the declared mission Xe allocation (owner design input; hard gate G3: a "
          "declared allocation, never sized from Hall-closure Xe-mode performance)",
          _NO_LB + "; a physics bound would be a sourced minimum Xe flow (e.g. cathode) x the Xe-fed hours required by "
          "the RFP (interpretation open)", mass_class="propellant", maturity=_PROP),
    _item("xe_residual", "Xe residuals (2 % of the Xe load)", "common", "Xe path: Xe chamber",
          "xenon_chamber_and_xenon_load", (), "", "policy allocation, not a physical bound", mass_class="propellant",
          maturity=_PROP, cbe={"basis": "scaling_relation", "relation": "fraction_of_item", "of_item": "xe_load",
                               "fraction": ESA_RESIDUAL_FRACTION}),
    _item("hall_thruster_head", "Hall thruster head (channel, anode / gas distributor, body)", "common",
          "ionization/discharge -> acceleration/thrust", "hall_thruster", ("hall_discharge",),
          "Vyovrinda Hall head geometry and material selection (own design), or a measured mass",
          _NO_LB, hall_related=True, notes=_HALL_NOTE),
    _item("hall_magnets", "Hall magnetic circuit (magnets / coils, pole pieces, yoke)", "common",
          "ionization/discharge -> acceleration/thrust", "hall_thruster", ("hall_magnet",),
          "Vyovrinda magnetic-circuit design for its own B(z) (not P5 calibration nuisance), or a measured mass",
          _NO_LB, hall_related=True, notes=_HALL_NOTE),
    _item("cathode", "Cathode (neutraliser) with heater and keeper", "common",
          "ionization/discharge -> acceleration/thrust", "cathode", ("cathode_keeper", "cathode_heater"),
          "selected cathode (supplier measured mass) or Vyovrinda cathode design; redundancy scheme", _NO_LB),
    _item("ppu", "Power processing unit (PSE) incl. control / housekeeping electronics", "common",
          "power supply electronics (RFP inclusion list, R3)", "power_processing",
          ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor",
           "housekeeping"),
          "PPU design or supplier unit, sized on the bus_power_boundary_v1 loads of the common components; redundancy "
          "per the recorded 'no single-point failure in electronics' (hard-gate R7, verify)", _NO_LB,
          notes="Pre-ionizer supplies (RF generator, microwave source) are booked to the architecture-specific items so "
                "that this item's definition is identical in every architecture (PROPOSED accounting convention)."),
    _item("harness", "Harness", "common", "harness (RFP inclusion list: structure / PSE, R3)", "harness_and_structure",
          (), "", "policy allocation, not a physical bound", maturity=_HARN,
          cbe={"basis": "scaling_relation", "relation": "fraction_of_nominal_dry", "fraction": ESA_HARNESS_FRACTION},
          notes="Until a harness design exists: harness = f/(1-f) x (nominal dry mass of all other dry items), so that "
                "harness = f x total nominal dry mass (ESA R-M1-7, f = 0.05 floor)."),
    _item("thermal_hardware", "Thermal-control hardware (radiators, heaters, MLI, heat paths)", "common",
          "thermal control", "thermal_control", ("thermal_control",),
          "thermal design (abep_sim/thermal_life.py, other lane, or a thermal network with sourced inputs) and "
          "materials", _NO_LB),
    _item("structure", "Propulsion-module structure (frames, brackets, interfaces)", "common",
          "structure (RFP inclusion list, R3)", "harness_and_structure", (),
          "configuration and launch-load environment (not defined in this repository) and structural design", _NO_LB),
    # ---- rf_hall only ----
    _item("rf_source", "RF pre-ionization source (discharge vessel, antenna / coil)", "rf_hall",
          "ionization/discharge (pre-ionization stage)", "rf_source", ("rf_source",),
          "Vyovrinda RF source design or a measured mass (docs/evidence/rf_source/, other lane)", _NO_LB,
          notes=_PREION_NOTE),
    _item("rf_generator", "RF generator (power amplifier / supply)", "rf_hall", "power supply electronics",
          "rf_source", ("rf_source",), "RF power level (bus_power_boundary_v1 rf_source load) and a supplier unit or "
          "design", _NO_LB),
    _item("rf_matching_network", "RF matching network", "rf_hall", "power supply electronics", "rf_source",
          ("rf_source",), "matching-network design or supplier unit", _NO_LB),
    # ---- ecr_hall only ----
    _item("ecr_source", "ECR pre-ionization source (cavity / antenna, coupling)", "ecr_hall",
          "ionization/discharge (pre-ionization stage)", "ecr_source", ("ecr_source",),
          "Vyovrinda ECR source design or a measured mass (docs/evidence/ecr_source/, other lane)", _NO_LB,
          notes=_PREION_NOTE),
    _item("microwave_source", "Microwave source (generator / supply)", "ecr_hall", "power supply electronics",
          "ecr_source", ("ecr_source",), "microwave power and frequency (design inputs) and a supplier unit or design",
          _NO_LB),
    _item("waveguide", "Waveguide / transmission line", "ecr_hall", "ionization/discharge (pre-ionization stage)",
          "ecr_source", ("ecr_source",), "frequency band, routing length and waveguide or coax selection", _NO_LB),
    _item("ecr_magnets", "ECR magnets (resonance-field magnetic circuit)", "ecr_hall",
          "ionization/discharge (pre-ionization stage)", "ecr_magnet", ("ecr_magnet",),
          "ECR magnetic-circuit design for the chosen frequency (resonance field) and geometry, or a measured mass",
          _NO_LB),
)


def bom_catalog() -> list[dict]:
    """Every BOM item definition (common + architecture-specific), as independent deep copies."""
    return _copy.deepcopy(list(_CATALOG))


def architecture_items(arch: str, catalog: list[dict] | None = None) -> list[dict]:
    """Items of one architecture: every 'common' item followed by the items scoped to `arch` (deep copies)."""
    if arch not in ARCHITECTURES:
        raise ValueError(f"unknown architecture {arch!r}; expected one of {ARCHITECTURES}")
    cat = bom_catalog() if catalog is None else _copy.deepcopy(list(catalog))
    return [it for it in cat if it["scope"] == "common"] + [it for it in cat if it["scope"] == arch]


# ---------------------------------------------------------------------------------------------------- validation
def _real(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{what} must be a finite real number, got {x!r}")
    return float(x)


def _nonempty(x, what: str) -> str:
    if not isinstance(x, str) or not x.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return x


def _evidence(x, what: str) -> str:
    if x not in EVIDENCE_CLASSES:
        raise ValueError(f"{what}: evidence_class {x!r} not in {EVIDENCE_CLASSES}")
    return x


def _quantity(q, what: str) -> float:
    """A sourced input: {'value', 'unit', 'source', 'evidence_class'}. Missing or unsourced -> ValueError."""
    if not isinstance(q, dict):
        raise ValueError(f"{what} must be a sourced quantity dict (value, unit, source, evidence_class), got {q!r}")
    for k in ("value", "unit", "source", "evidence_class"):
        if k not in q:
            raise ValueError(f"{what} is missing {k!r} (no silent defaults)")
    _nonempty(q["unit"], f"{what}.unit")
    _nonempty(q["source"], f"{what}.source")
    _evidence(q["evidence_class"], what)
    return _real(q["value"], f"{what}.value")


def _walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            yield k, p, v
            yield from _walk_keys(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{path}[{i}]")


_SPHERE_INPUTS = ("p_meop_Pa", "burst_factor", "sigma_ult_Pa", "rho_wall_kg_m3", "volume_m3")


def thin_wall_sphere_min_mass_kg(p_meop_Pa: float, burst_factor: float, sigma_ult_Pa: float, rho_wall_kg_m3: float,
                                 volume_m3: float) -> float:
    """Membrane lower bound on the shell mass of a spherical, monolithic, isotropic pressure vessel:
    sigma_ult >= (burst_factor p) r / (2 t)  =>  m = 4 pi r^2 t rho >= (3/2) burst_factor p V rho / sigma_ult.
    Excludes bosses, ports, liner, mounts and any thick-wall correction (all add mass). Every argument is explicit."""
    p = _real(p_meop_Pa, "p_meop_Pa"); bf = _real(burst_factor, "burst_factor")
    s = _real(sigma_ult_Pa, "sigma_ult_Pa"); rho = _real(rho_wall_kg_m3, "rho_wall_kg_m3")
    V = _real(volume_m3, "volume_m3")
    if p <= 0 or bf < 1 or s <= 0 or rho <= 0 or V <= 0:
        raise ValueError("thin_wall_sphere_min_mass_kg needs p > 0, burst_factor >= 1, sigma > 0, rho > 0, V > 0")
    return 1.5 * bf * p * V * rho / s


def check_item(item: dict) -> None:
    """Validate one BOM item definition; raises ValueError on any violation (see module banner)."""
    if not isinstance(item, dict):
        raise ValueError("BOM item must be a dict")
    for k in ("id", "name", "scope", "gate_element", "mass_class", "hall_related", "maturity", "cbe", "lower_bound"):
        if k not in item:
            raise ValueError(f"BOM item {item.get('id', '?')!r} is missing {k!r}")
    iid = _nonempty(item["id"], "item.id")
    for key, path, val in _walk_keys(item):
        if key in CALIBRATION_NUISANCE_KEYS:
            raise ValueError(f"item {iid!r}: {path!r} is P5 calibration nuisance (layer 1); it is never a design "
                             "variable or mass input")
        if key in HALL_CLOSURE_KEYS or (key == "depends_on_hall_closure" and val):
            raise ValueError(f"item {iid!r}: {path!r} marks a Hall-closure-derived mass; mass (G3) is closure-"
                             "independent and unadmitted closures are never a performance or sizing source")
    if item["scope"] not in ("common",) + ARCHITECTURES:
        raise ValueError(f"item {iid!r}: scope {item['scope']!r} invalid")
    if item["mass_class"] not in MASS_CLASSES:
        raise ValueError(f"item {iid!r}: mass_class {item['mass_class']!r} not in {MASS_CLASSES}")
    cat = item["maturity"].get("category") if isinstance(item["maturity"], dict) else None
    if cat != "TBD" and cat not in MATURITY_CATEGORIES:
        raise ValueError(f"item {iid!r}: maturity category {cat!r} unknown (use a MATURITY_CATEGORIES key or 'TBD')")
    if item["mass_class"] == "propellant" and cat not in ("propellant_not_equipment", "TBD"):
        raise ValueError(f"item {iid!r}: propellant must use maturity 'propellant_not_equipment'")
    cbe = item["cbe"]
    basis = cbe.get("basis") if isinstance(cbe, dict) else None
    if basis == "TBD":
        _nonempty(cbe.get("requires"), f"item {iid!r} cbe.requires")
    elif basis == "sourced_value":
        if _real(cbe.get("value_kg"), f"item {iid!r} cbe.value_kg") < 0:
            raise ValueError(f"item {iid!r}: negative CBE")
        _nonempty(cbe.get("source"), f"item {iid!r} cbe.source")
        _evidence(cbe.get("evidence_class"), f"item {iid!r} cbe")
        for k in ("uncertainty", "applicability"):
            _nonempty(cbe.get(k), f"item {iid!r} cbe.{k}")
    elif basis == "scaling_relation":
        rel = cbe.get("relation")
        f = _quantity(cbe.get("fraction"), f"item {iid!r} cbe.fraction")
        if not 0.0 <= f < 1.0:
            raise ValueError(f"item {iid!r}: fraction {f} outside [0, 1)")
        if rel == "fraction_of_item":
            _nonempty(cbe.get("of_item"), f"item {iid!r} cbe.of_item")
        elif rel != "fraction_of_nominal_dry":
            raise ValueError(f"item {iid!r}: unknown scaling relation {rel!r}")
    else:
        raise ValueError(f"item {iid!r}: cbe.basis {basis!r} not in ('TBD', 'sourced_value', 'scaling_relation')")
    lb = item["lower_bound"]
    lbb = lb.get("basis") if isinstance(lb, dict) else None
    if lbb == "none":
        _nonempty(lb.get("requires"), f"item {iid!r} lower_bound.requires")
    elif lbb in ("sourced_value", "thin_wall_sphere_membrane"):
        if lb.get("gate_basis") not in G3_FAIL_BASES:
            raise ValueError(f"item {iid!r}: lower_bound.gate_basis must be one of {G3_FAIL_BASES}")
        _nonempty(lb.get("scope_justification"), f"item {iid!r} lower_bound.scope_justification")
        if lbb == "sourced_value":
            if _real(lb.get("value_kg"), f"item {iid!r} lower_bound.value_kg") < 0:
                raise ValueError(f"item {iid!r}: negative lower bound")
            _nonempty(lb.get("source"), f"item {iid!r} lower_bound.source")
            _evidence(lb.get("evidence_class"), f"item {iid!r} lower_bound")
        else:
            if lb["gate_basis"] != "hard_physical_bound":
                raise ValueError(f"item {iid!r}: thin_wall_sphere_membrane is a hard_physical_bound")
            inputs = lb.get("inputs") or {}
            thin_wall_sphere_min_mass_kg(**{k: _quantity(inputs.get(k), f"item {iid!r} lower_bound.{k}")
                                            for k in _SPHERE_INPUTS})
    else:
        raise ValueError(f"item {iid!r}: lower_bound.basis {lbb!r} invalid")


def _lower_bound_kg(item: dict) -> float | None:
    lb = item["lower_bound"]
    if lb["basis"] == "none":
        return None
    if lb["basis"] == "sourced_value":
        return float(lb["value_kg"])
    return thin_wall_sphere_min_mass_kg(**{k: float(lb["inputs"][k]["value"]) for k in _SPHERE_INPUTS})


def _check_set(items: list[dict]) -> None:
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list of BOM item dicts")
    for it in items:
        check_item(it)
    ids = [it["id"] for it in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate item ids: {sorted({i for i in ids if ids.count(i) > 1})}")


def _fraction(x, what: str) -> float:
    v = _real(x, what)
    if not 0.0 <= v < 1.0:
        raise ValueError(f"{what} must lie in [0, 1), got {v}")
    return v


def _mga_of(item: dict) -> float | None:
    cat = item["maturity"]["category"]
    return None if cat == "TBD" else MATURITY_CATEGORIES[cat]["mga"]


# ---------------------------------------------------------------------------------------------------- roll-up
def rollup(items: list[dict], *, system_margin_fraction: float, allow_partial: bool = False,
           g3_margin_floor: float | None = None) -> dict:
    """MEV = sum_dry CBE x (1 + MGA) + system margin + propellant, with system margin = fraction x nominal dry mass
    (nominal dry = sum_dry CBE x (1 + MGA); propellant carries no MGA or system margin, ESA R-M1-3). The system-margin
    fraction has no default.

    Refuses (ValueError listing every missing item) when any item is TBD or unresolvable, unless allow_partial=True: the
    result then has complete=False, mev_kg=None, the missing items with reasons, and known-items-only sums that are NOT
    an architecture MEV. g3_margin_floor (optional, explicit) adds the hard-gate G3 PASS-side quantity
    sum_all CBE x (1 + max(MGA, floor)) to a complete roll-up."""
    sm = _fraction(system_margin_fraction, "system_margin_fraction")
    floor = None if g3_margin_floor is None else _fraction(g3_margin_floor, "g3_margin_floor")
    _check_set(items)
    by_id = {it["id"]: it for it in items}
    cbe, missing = {}, {}
    for it in items:
        c = it["cbe"]
        if c["basis"] == "TBD":
            missing[it["id"]] = "CBE TBD: requires " + c["requires"]
        elif c["basis"] == "sourced_value":
            cbe[it["id"]] = float(c["value_kg"])
    for it in items:
        c = it["cbe"]
        if c["basis"] == "scaling_relation" and c["relation"] == "fraction_of_item":
            tgt = c["of_item"]
            if tgt not in by_id:
                raise ValueError(f"item {it['id']!r} scales item {tgt!r}, which is not in this BOM")
            if by_id[tgt]["cbe"]["basis"] == "scaling_relation":
                raise ValueError(f"item {it['id']!r}: fraction_of_item must not reference another scaled item")
            if by_id[tgt]["mass_class"] != it["mass_class"]:
                raise ValueError(f"item {it['id']!r}: fraction_of_item must keep the mass class of {tgt!r}")
            if tgt in cbe:
                cbe[it["id"]] = float(c["fraction"]["value"]) * cbe[tgt]
            else:
                missing[it["id"]] = f"depends on missing item {tgt!r}"
    for it in items:
        if it["id"] in cbe and _mga_of(it) is None:
            missing[it["id"]] = "maturity category TBD: MGA cannot be applied"
    harness_like = [it for it in items if it["cbe"]["basis"] == "scaling_relation"
                    and it["cbe"]["relation"] == "fraction_of_nominal_dry"]
    if len(harness_like) > 1:
        raise ValueError("at most one fraction_of_nominal_dry item is allowed")
    for it in harness_like:
        if it["mass_class"] != "dry":
            raise ValueError(f"item {it['id']!r}: fraction_of_nominal_dry applies to a dry item")
        others = [o for o in items if o["mass_class"] == "dry" and o["id"] != it["id"]]
        gap = [o["id"] for o in others if o["id"] in missing or o["id"] not in cbe]
        if gap:
            missing[it["id"]] = f"depends on the nominal dry mass of missing items {gap}"
        elif _mga_of(it) is None:
            missing[it["id"]] = "maturity category TBD: MGA cannot be applied"
        else:
            f = float(it["cbe"]["fraction"]["value"])
            rest = sum(cbe[o["id"]] * (1.0 + _mga_of(o)) for o in others)
            cbe[it["id"]] = f / (1.0 - f) * rest / (1.0 + _mga_of(it))
    lines = []
    for it in items:
        ok = it["id"] in cbe and it["id"] not in missing
        mga = _mga_of(it)
        lines.append({"id": it["id"], "mass_class": it["mass_class"], "basis": it["cbe"]["basis"],
                      "maturity_category": it["maturity"]["category"], "mga": mga,
                      "cbe_kg": cbe[it["id"]] if ok else None,
                      "nominal_kg": cbe[it["id"]] * (1.0 + mga) if ok else None,
                      "status": "resolved" if ok else "missing", "missing_reason": missing.get(it["id"])})
    miss = [{"id": ln["id"], "reason": ln["missing_reason"]} for ln in lines if ln["status"] == "missing"]
    if miss and not allow_partial:
        raise ValueError("mass roll-up refused: %d item(s) TBD or unresolved: %s. Pass allow_partial=True for a partial "
                         "roll-up that lists the missing items (it is not an MEV)."
                         % (len(miss), "; ".join(f"{m['id']} ({m['reason']})" for m in miss)))
    ok_lines = [ln for ln in lines if ln["status"] == "resolved"]
    cbe_dry = sum(ln["cbe_kg"] for ln in ok_lines if ln["mass_class"] == "dry")
    nom_dry = sum(ln["nominal_kg"] for ln in ok_lines if ln["mass_class"] == "dry")
    prop = sum(ln["cbe_kg"] for ln in ok_lines if ln["mass_class"] == "propellant")
    totals = {"cbe_dry_kg": cbe_dry, "mga_kg": nom_dry - cbe_dry, "nominal_dry_kg": nom_dry,
              "system_margin_fraction": sm, "system_margin_kg": sm * nom_dry, "propellant_kg": prop,
              "cbe_total_kg": cbe_dry + prop, "mev_kg": nom_dry * (1.0 + sm) + prop}
    out = {"bom_version": BOM_VERSION, "complete": not miss, "n_items": len(lines), "n_missing": len(miss),
           "missing_items": miss, "lines": lines}
    if miss:
        out.update({"mev_kg": None, "partial_known_items_only": totals,
                    "partial_note": "sums over resolved items only; NOT an MEV of the architecture"})
    else:
        out.update(totals)
        if floor is not None:
            out["g3_margin_floor"] = floor
            out["g3_bounding_mass_kg"] = sum(ln["cbe_kg"] * (1.0 + max(ln["mga"], floor)) for ln in lines)
    return out


# ---------------------------------------------------------------------------------------------------- screen
SCREEN_VERDICTS = ("EXCEEDS_LIMIT_MARGIN_FREE", "EXCEEDS_LIMIT_MEV_ONLY", "NOT_EXCLUDED_PARTIAL_COVERAGE",
                   "NOT_EXCLUDED_FULL_COVERAGE", "LOWER_BOUNDS_UNAVAILABLE")


def plausibility_screen(items_by_arch: dict, *, threshold_kg: float, system_margin_fraction: float) -> dict:
    """Milestone-A mass screen from sourced lower bounds only. Per architecture:
    margin-free CBE lower bound = sum of item lower bounds (an item without one contributes its trivial floor 0 kg, so
    the sum is still a valid lower bound); MEV lower bound = sum_dry LB x (1 + MGA) x (1 + system margin) + propellant
    LB (MGA TBD -> 0, its minimum). The comparison is strict ('> limit'); a bound equal to the limit decides nothing.
    EXCEEDS_LIMIT_MARGIN_FREE is the only verdict usable as G3 FAIL-side evidence (flag mass_margin_free_lower_bound);
    EXCEEDS_LIMIT_MEV_ONLY depends on the margin policy (hard-gate OD7) and eliminates nothing."""
    thr = _real(threshold_kg, "threshold_kg")
    sm = _fraction(system_margin_fraction, "system_margin_fraction")
    if not items_by_arch or any(a not in ARCHITECTURES for a in items_by_arch):
        raise ValueError(f"items_by_arch keys must be architecture ids from {ARCHITECTURES}")
    res = {}
    for arch, items in items_by_arch.items():
        _check_set(items)
        with_lb, without = [], []
        cbe_lb = mev_lb = common_lb = specific_lb = 0.0
        for it in items:
            v = _lower_bound_kg(it)
            if v is None:
                without.append(it["id"])
                continue
            mga = _mga_of(it) or 0.0
            with_lb.append({"id": it["id"], "lower_bound_kg": v, "gate_basis": it["lower_bound"]["gate_basis"]})
            cbe_lb += v
            mev_lb += v * (1.0 + mga) * (1.0 + sm) if it["mass_class"] == "dry" else v
            if it["scope"] == "common":
                common_lb += v
            else:
                specific_lb += v
        if cbe_lb > thr:
            verdict = "EXCEEDS_LIMIT_MARGIN_FREE"
        elif mev_lb > thr:
            verdict = "EXCEEDS_LIMIT_MEV_ONLY"
        elif not with_lb:
            verdict = "LOWER_BOUNDS_UNAVAILABLE"
        elif without:
            verdict = "NOT_EXCLUDED_PARTIAL_COVERAGE"
        else:
            verdict = "NOT_EXCLUDED_FULL_COVERAGE"
        res[arch] = {"verdict": verdict, "cbe_margin_free_lower_bound_kg": cbe_lb, "mev_lower_bound_kg": mev_lb,
                     "common_items_lower_bound_kg": common_lb, "architecture_specific_lower_bound_kg": specific_lb,
                     "n_items": len(items), "items_with_lower_bound": with_lb, "items_without_lower_bound": without,
                     "g3_fail_evidence": verdict == "EXCEEDS_LIMIT_MARGIN_FREE",
                     "g3_flags": ["mass_margin_free_lower_bound"] if with_lb else []}
    return {"threshold_kg": thr, "comparator": "> (strict; equality decides nothing)", "system_margin_fraction": sm,
            "architectures": res,
            "any_architecture_excluded": any(r["verdict"] == "EXCEEDS_LIMIT_MARGIN_FREE" for r in res.values())}


# ---------------------------------------------------------------------------------------------------- shared contract
def check_power_boundary_coverage() -> dict:
    """Lazily resolve abep_sim/arch_boundary.py (other lane) and report, per architecture, bus_power_boundary_v1
    components carried by no BOM item ('uncovered') and component names no boundary defines ('unknown')."""
    try:
        from . import arch_boundary as ab  # lazy on purpose: shared contract built by another lane
    except ImportError as e:
        raise ImportError("abep_sim/arch_boundary.py (bus_power_boundary_v1) is not present in this checkout; it is "
                          "built by the power-boundary lane and resolved lazily") from e
    out = {"boundary_version": ab.BOUNDARY_VERSION, "architectures": {}}
    for arch in ARCHITECTURES:
        req = set(ab.REQUIRED_COMPONENTS[arch])
        named = {c for it in architecture_items(arch) for c in it["power_boundary_components"]}
        out["architectures"][arch] = {"uncovered": sorted(req - named), "unknown": sorted(named - req)}
    return out


# ---------------------------------------------------------------------------------------------------- schema check
def validate_against_schema(instance, schema, _root=None, _path="$") -> None:
    """Minimal JSON-Schema validator for the 2020-12 subset used by mass_bom_v1.schema.json; raises ValueError."""
    root = schema if _root is None else _root
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"{_path}: unsupported $ref {ref}")
        validate_against_schema(instance, root["$defs"][ref[len("#/$defs/"):]], root, _path)
    t = schema.get("type")
    if t is not None:
        chk = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
               "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
               "null": lambda v: v is None, "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
               "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)}
        if not any(chk[x](instance) for x in (t if isinstance(t, list) else [t])):
            raise ValueError(f"{_path}: expected type {t}, got {type(instance).__name__}")
    if "const" in schema and instance != schema["const"]:
        raise ValueError(f"{_path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValueError(f"{_path}: {instance!r} not in enum")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValueError(f"{_path}: {instance} < minimum {schema['minimum']}")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            raise ValueError(f"{_path}: {instance} >= exclusiveMaximum {schema['exclusiveMaximum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ValueError(f"{_path}: string shorter than {schema['minLength']}")
        if "pattern" in schema and not _re.search(schema["pattern"], instance):
            raise ValueError(f"{_path}: {instance!r} does not match {schema['pattern']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValueError(f"{_path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, v in enumerate(instance):
                validate_against_schema(v, schema["items"], root, f"{_path}[{i}]")
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                raise ValueError(f"{_path}: missing required {k!r}")
        props = schema.get("properties", {})
        for k, v in instance.items():
            if k in props:
                validate_against_schema(v, props[k], root, f"{_path}.{k}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    raise ValueError(f"{_path}: unexpected property {k!r}")
                if isinstance(ap, dict):
                    validate_against_schema(v, ap, root, f"{_path}.{k}")
    for key in ("anyOf", "oneOf"):
        if key in schema:
            ok = 0
            for sub in schema[key]:
                try:
                    validate_against_schema(instance, sub, root, _path)
                    ok += 1
                except ValueError:
                    pass
            if ok == 0 or (key == "oneOf" and ok != 1):
                raise ValueError(f"{_path}: {key} matched {ok} subschemas")
    for sub in schema.get("allOf", []):
        validate_against_schema(instance, sub, root, _path)


# ---------------------------------------------------------------------------------------------------- document
MILESTONES = {
    "supports": ["A"],
    "A": "Supported: one mass accounting (same items, same margin policy) for the three architectures; a sourced-lower-"
         "bound plausibility screen feeding the hard-gate G3 mass FAIL side; refusal of any roll-up with TBD items. "
         "Current result: lower bounds are unavailable for every item, so no architecture is excluded on mass.",
    "B": "Needs: CBEs from closure-independent design models or supplier data for every item (Vyovrinda intake, "
         "compressor, Hall head and magnetic circuit, cathode, PPU, pre-ionizer hardware), a declared Xe allocation, "
         "owner decisions OD-M1..OD-M7, and physics lower bounds where they exist.",
    "C": "Needs: PDR-level design masses (measured or supplier-measured where possible), harness and structure from the "
         "configuration and launch loads, thermal hardware from the integrated thermal design, and the integrated "
         "mass / power / thermal / life / mission closure.",
}

OPEN_OWNER_DECISIONS = [
    {"id": "OD-M1", "topic": "system margin",
     "options": ["20 % of nominal dry mass (ESA R-M1-1 by analogy, PROPOSED)", "10 % per recorded RFP R3 (verify)"],
     "current_handling": "PROPOSED 20 %; hard-gate G3 PASS uses max(MGA, 10 %) and FAIL the margin-free CBE, so no G3 "
                         "verdict depends on this choice"},
    {"id": "OD-M2", "topic": "maturity categories",
     "options": ["accept PROPOSED ECSS D (20 %) for every dry equipment item", "assign per selected part"],
     "current_handling": "PROPOSED D for every dry equipment item"},
    {"id": "OD-M3", "topic": "legacy MGA dict in abep_sim/mass_bom.py (new 30 %, modified 15 %, existing 5 %, "
                             "calculated 10 %; no citation in the file), referenced by hard-gate OD7",
     "options": ["retire it in favour of the ESA table (model change for archengine: goldens, HISTORY)",
                 "keep it and cite a source"],
     "current_handling": "left unchanged (archengine and system import it); not used by mass_bom_v1"},
    {"id": "OD-M4", "topic": "Xe allocation", "options": ["declare a mission Xe load (design input)"],
     "current_handling": "TBD; xe_load, xe_residual and the xe_tank bound stay unresolved"},
    {"id": "OD-M5", "topic": "item list (PROPOSED, cf. hard-gate OD10)", "options": ["accept", "amend (new BOM version)"],
     "current_handling": "PROPOSED list used"},
    {"id": "OD-M6", "topic": "harness allocation on a propulsion subsystem",
     "options": ["ESA R-M1-7 5 % of nominal dry mass (PROPOSED)", "designed harness"],
     "current_handling": "5 % allocation (scaling relation)"},
    {"id": "OD-M7", "topic": "whether the RFP 40 kg includes the Xe load",
     "options": ["includes Xe + tank (recorded R3, verify)", "dry mass only"],
     "current_handling": "Xe load and residuals are included in MEV as propellant (R3 as recorded)"},
]


def build_document() -> dict:
    """The deterministic content of docs/architecture_comparison/mass_bom/mass_bom_v1.json."""
    from .constants import RFP
    sm = SYSTEM_MARGIN["proposed_fraction"]
    per_arch = {a: architecture_items(a) for a in ARCHITECTURES}
    rollups = {}
    for a, items in per_arch.items():
        try:
            rollup(items, system_margin_fraction=sm)
            strict = {"status": "COMPLETE", "message": ""}
        except ValueError as e:
            strict = {"status": "REFUSED", "message": str(e)}
        rollups[a] = {"strict": strict, "partial": rollup(items, system_margin_fraction=sm, allow_partial=True)}
    screen = plausibility_screen(per_arch, threshold_kg=RFP.mass_max_kg, system_margin_fraction=sm)
    screen["threshold_source"] = "RFP_MASS_AS_RECORDED (abep_sim/constants.py RFP.mass_max_kg; verify against RFP)"
    unavailable = all(r["verdict"] == "LOWER_BOUNDS_UNAVAILABLE" for r in screen["architectures"].values())
    screen["statement"] = (
        "Sourced lower bounds are unavailable for every item in every architecture (no Vyovrinda design, no selected "
        "parts, no declared Xe load). The only valid lower bound today is the trivial 0 kg, so the screen cannot show "
        "that any architecture's minimum plausible MEV exceeds the limit: no architecture is excluded on mass."
        if unavailable else "See the per-architecture verdicts.")
    return {
        "schema": BOM_SCHEMA_PATH, "bom_version": BOM_VERSION, "created": BOM_CREATED,
        "generator": "python -m abep_sim.mass_bom build (abep_sim/mass_bom.py, section 'Architecture mass BOM skeleton')",
        "purpose": "Same mass accounting (CBE / MGA / MEV) for hall_only, rf_hall and ecr_hall; plausibility screen from "
                   "sourced lower bounds for the hard-gate G3 mass gate. Never an architecture ranking.",
        "architecture_ids": list(ARCHITECTURES),
        "milestones": MILESTONES,
        "mev_definition": "MEV = sum_dry CBE x (1 + MGA) + system margin + propellant; system margin = fraction x "
                          "nominal dry mass (nominal dry = sum_dry CBE x (1 + MGA)); propellant carries no MGA and no "
                          "system margin (ESA R-M1-3)",
        "sources": MASS_BOM_SOURCES,
        "margin_policy": {"id": "esa_sre_pa_2011_097_i1r3", "source": _ESA, "maturity_categories": MATURITY_CATEGORIES,
                          "aiaa_s120a": "not used: TBD (no openly accessible reproduction of AIAA S-120A was consulted)",
                          "legacy_repository_mga": "abep_sim/mass_bom.py MGA dict (v1.7, uncited) is not used; OD-M3"},
        "system_margin": SYSTEM_MARGIN,
        "hall_closure_policy": "Mass is closure-independent (hard-gate G3). No Hall mass comes from any transport "
                               "closure; closure-derived inputs are rejected by check_item(). The credible set is empty "
                               "(CLAUDE.md), so no Hall map feeds this BOM.",
        "items": bom_catalog(),
        "architectures": {a: {"item_ids": [it["id"] for it in per_arch[a]],
                              "common_item_ids": [it["id"] for it in per_arch[a] if it["scope"] == "common"],
                              "specific_item_ids": [it["id"] for it in per_arch[a] if it["scope"] != "common"]}
                          for a in ARCHITECTURES},
        "rollups": rollups,
        "plausibility_screen": screen,
        "open_owner_decisions": OPEN_OWNER_DECISIONS,
        "not_used": "Repository mass figures from earlier versions (docs/HISTORY.md v0.5 and Phase 4 tables; the "
                    "withdrawn 110-120 kg) are not CBE sources: they rest on the superseded 0-D Hall closure and on "
                    "uncited defaults. Do not quote them.",
    }


def document_text(doc: dict | None = None) -> str:
    return _json.dumps(build_document() if doc is None else doc, indent=1, ensure_ascii=False) + "\n"


def _repo_root() -> _Path:
    return _Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(_sys.argv[1:] if argv is None else argv)
    if args not in (["build"], ["check"]):
        print("usage: python -m abep_sim.mass_bom build|check", file=_sys.stderr)
        return 2
    root = _repo_root()
    text = document_text()
    validate_against_schema(_json.loads(text), _json.loads((root / BOM_SCHEMA_PATH).read_text(encoding="utf-8")))
    doc_path = root / BOM_DOC_PATH
    if args == ["build"]:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(text, encoding="utf-8")
        print(f"wrote {BOM_DOC_PATH}")
        return 0
    if not doc_path.exists() or doc_path.read_text(encoding="utf-8") != text:
        print(f"MISMATCH: {BOM_DOC_PATH} differs from build_document()", file=_sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
