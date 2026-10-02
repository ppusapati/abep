"""F3 compressor geometry synthesis (A9.7, follow-on fo_a9_7_f3_compressor_synthesis).

A bounded physical design search beside ``abep_sim.compressor.DragCompressor.size_for`` (which is NOT modified: it
stays the three-variable sizing search the goldens use). This module builds ``DragCompressor`` instances (the
free-molecular turbomolecular rows + Holweck/Gaede drag stages that the module supports), runs them through the
module's own self-consistent ``run()`` and then applies explicit, fail-closed gates that ``run()`` / ``size_for()``
do not apply:

  * rotor stress    : thin-ring hoop stress sigma = rho u^2 (the module's stated relation, compressor.py docstring) at
                      the larger of the turbo / drag tip speeds, against a CITED material allowable times the safety
                      factor; materials without a cited allowable are excluded (never evaluated with an uncited value)
  * convergence     : the leak-recirculation fixed point of ``run()`` is re-checked (``run()`` reports no convergence and
                      returns its last iterate after 40 iterations); residual above the module's own 1e-4 tolerance or
                      a non-finite state rejects the design and NO performance value is returned (never half-converged)
  * characteristic  : ``_run_once`` clips each per-species Gaede K to [1, K0]; an unclipped K < 1 means the throughput
                      exceeds the stage's pumping capacity at that pressure, i.e. the fixed inlet pressure is not
                      self-consistent. Such designs are rejected (the module would silently report K = 1)
  * evidence domain : free-molecular regime. Every stage outlet pressure <= 1e-3 mbar = 0.1 Pa (Chiggiato 2013,
                      Sec. 4.1.2: TMPs work at full pumping speed only in the molecular regime; repository finding
                      compressor_downselect CD-04), and in drag channels Kn = lambda / h >= 0.5 (Chiggiato Table 7)
                      evaluated with the N2/O2 cross sections of Chiggiato Table 6 (atomic O cross section TBD, so the
                      Kn value is an upper bound and is a necessary, not sufficient, check); tip speed <= 500 m/s
                      (Chiggiato Sec. 4.1.2, the circumferential speed of commercial Al-alloy TMP rotors)
  * thermal         : the module's lumped compressor temperature against the materials-DB service limit (labelled)

Species O, N2, O2 are carried individually: per-species delivered mass flow, per-species compression ratio, outlet
partial-pressure composition x_s,out and the delivered-flow composition (which equals the inlet composition in
steady state: the module delivers the captured flow, ``run()['delivered_kgps']``).

Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md; A9.7 "never convert a TBD input into an assumed
value to obtain an optimum"):
  * Every DragCompressor coefficient that is not searched is an uncited code default (compressor_downselect CD-01,
    evidence class 'assumed'). In MODE_STRICT the search REFUSES (status NOT_EVALUATED, blockers listed) unless every
    such coefficient is supplied with non-assumed evidence and the inlet record is a real interface record.
  * MODE_PARAMETRIC runs the search on the code defaults and labels every output PARAMETRIC_SENSITIVITY: a model-
    derived screening under assumed coefficients, never a design value, never a PASS, never a winner.
  * Outputs are a feasible set and Pareto fronts (non-dominated filter) with every rejected design kept with its
    reasons. There is no scalar objective and no selected optimum.

Not wired into archengine; imports only abep_sim.compressor, abep_sim.constants and abep_sim.materials (read-only).

A9.13 / A9.9 owner decisions applied (A9.16 step 3 design layer; docs/decisions/OD_2026_10_01_A9_13_* json sha256
9afaca45..., OD_2026_10_01_A9_9_* json sha256 b6010d9d...; shared rules in abep_sim/design/upstream_a9_13.py):
  * S6.7 / OQ-F3-02: hub ratio nu = R_hub / R_tip and blade span (R_tip - R_hub) are explicit geometry variables;
    R_tip = sqrt(A / (pi (1 - nu^2))). The zero-hub relation R = sqrt(A / pi) is only the analytical bound
    (ZERO_HUB_ANALYTICAL_BOUND, reported apart from the Pareto front); no hub-ratio bound is invented: the searched
    values ``HUB_RATIO_PARAMETRIC`` are a declared PARAMETRIC_SENSITIVITY coverage of the definitional domain [0, 1);
    final bounds come from shaft / bearing, rotor-structural, motor / interface, manufacturability and pumping
    interfaces.
  * S6.8 / OQ-F3-03: a design touching a pressure above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN (no outputs); the
    transitional model abep_sim/compressor_transitional.py is CANDIDATE_NOT_ADMITTED and is not imported here.
  * A9.9 S2.3 / S2.5 MCC-03 (review finding D-05) and A9.13 S6.9 / OQ-F3-04: rotor structural acceptance is granted
    ONLY through abep_sim.rotor_strength.qualify_rotor (registered basis, yield AND ultimate). Without a registered
    basis MODE_STRICT returns NOT_EVALUATED_MATERIAL_BASIS; the 827 MPa x 2.0 thin-ring gate survives only as the
    labelled legacy PARAMETRIC_SENSITIVITY case of MODE_PARAMETRIC. Aluminium and CFRP re-enter only through a
    registered basis plus an AO disposition (CFRP additionally laminate, directional allowables, environment and
    manufacturing / inspection bases): ``material_admission``.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Mapping

from .. import rotor_strength as rs
from ..compressor import DragCompressor
from ..constants import K_B, M_SPECIES
from ..materials import DB
from . import upstream_a9_13 as u13

SCHEMA = "f3_compressor_synthesis_v1"
VERSION = "1.0.0"
SPECIES = ("O", "N2", "O2")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation")

MODE_STRICT = "strict"
MODE_PARAMETRIC = "parametric_sensitivity"
MODES = (MODE_STRICT, MODE_PARAMETRIC)

LABEL_PARAMETRIC = "PARAMETRIC_SENSITIVITY"
LABEL_INTERFACE = "F1_F2_INTERFACE_RECORD"
INLET_LABELS = (LABEL_PARAMETRIC, LABEL_INTERFACE)

ST_FEASIBLE = "FEASIBLE_UNDER_PARAMETRIC_SENSITIVITY_INPUTS"
ST_FEASIBLE_STRICT = "FEASIBLE_UNDER_SUPPLIED_EVIDENCE"
ST_REJECTED = "REJECTED"
ST_NOT_EVALUATED = "NOT_EVALUATED"
ST_NOT_EVALUATED_OOD = u13.NOT_EVALUATED_OOD                     # A9.13 S6.8
ST_NOT_EVALUATED_MATERIAL_BASIS = rs.Q_NOT_EVALUATED_MATERIAL_BASIS  # A9.9 S2.3 / MCC-03

# rejection reasons (a design can carry several)
R_ALLOWABLE_TBD = "ROTOR_MATERIAL_ALLOWABLE_TBD"
R_STRESS = "ROTOR_STRESS_ABOVE_CITED_ALLOWABLE_WITH_SAFETY_FACTOR"
R_TIP_DOMAIN = "TIP_SPEED_ABOVE_PUBLISHED_TMP_PRACTICE"
R_INLET_DOMAIN = "INLET_PRESSURE_OUTSIDE_FREE_MOLECULAR_DOMAIN"
R_MODEL = "MODEL_ERROR_NON_FINITE_OR_EXCEPTION"
R_NONCONV = "SELF_CONSISTENT_RUN_NOT_CONVERGED"
R_CLIP = "GAEDE_CHARACTERISTIC_CLIPPED_THROUGHPUT_ABOVE_STAGE_CAPACITY"
R_DOMAIN_P = "STAGE_PRESSURE_OUTSIDE_FREE_MOLECULAR_DOMAIN"
R_DOMAIN_KN = "DRAG_CHANNEL_KNUDSEN_BELOW_FREE_MOLECULAR_LIMIT"
R_THERMAL = "COMPRESSOR_TEMPERATURE_ABOVE_MATERIAL_SERVICE_LIMIT"
R_ROTOR_QUAL_FAIL = "ROTOR_QUALIFICATION_FAIL_REGISTERED_BASIS"
R_ROTOR_QUAL_OOD = "ROTOR_QUALIFICATION_OUTSIDE_REGISTERED_BASIS_DOMAIN"
R_READMISSION_RECORDS = "MATERIAL_READMISSION_RECORDS_MISSING"          # A9.13 S6.9 (Al / CFRP extra records)
REASONS = (R_ALLOWABLE_TBD, R_STRESS, R_TIP_DOMAIN, R_INLET_DOMAIN, R_MODEL, R_NONCONV, R_CLIP, R_DOMAIN_P,
           R_DOMAIN_KN, R_THERMAL, R_ROTOR_QUAL_FAIL, R_ROTOR_QUAL_OOD, R_READMISSION_RECORDS)
DOMAIN_REASONS = (R_INLET_DOMAIN, R_DOMAIN_P, R_DOMAIN_KN)                       # pressure above the 0.1 Pa domain
INLET_INDEPENDENT_REASONS = (R_ALLOWABLE_TBD, R_STRESS, R_TIP_DOMAIN, R_ROTOR_QUAL_FAIL)

# A9.13 S6.7: hub ratio values searched as a declared PARAMETRIC_SENSITIVITY coverage of the definitional domain
# [0, 1) (equal spacing; NOT design bounds, none is sourced). 0 = zero-hub analytical bound (not a buildable rotor).
HUB_RATIO_PARAMETRIC = (0.0, 0.25, 0.5, 0.75)
HUB_ZERO_BOUND = "ZERO_HUB_ANALYTICAL_BOUND_NOT_BUILDABLE"
HUB_PARAMETRIC = "PARAMETRIC_SENSITIVITY_HUB_RATIO_BOUNDS_TBD"
HUB_BOUND_SOURCES = ("shaft / bearing geometry", "rotor structural analysis", "motor / interface geometry",
                     "blade manufacturability", "pumping-performance model")
STRESS_CASE_LEGACY = "LEGACY_PARAMETRIC_SENSITIVITY"
STRESS_CASE_REGISTERED = "REGISTERED_BASIS_QUALIFY_ROTOR"
# A9.13 S6.9: additional basis records for re-admitted rotor materials (beyond the registered strength basis)
AO_DISPOSITION_KEY = "ao_disposition"
CFRP_EXTRA_BASIS_KEYS = ("laminate_definition", "directional_allowables", "temperature_moisture_environment_basis",
                         "manufacturing_inspection_basis", AO_DISPOSITION_KEY)
READMITTED_MATERIALS = {"Al6061": (AO_DISPOSITION_KEY,), "CFRP": CFRP_EXTRA_BASIS_KEYS}

# ----------------------------------------------------------------------------------------------------------- sources
SOURCES = {
    "SRC-CHIGGIATO2013": {
        "citation": "P. Chiggiato, 'Vacuum Technology for Ion Sources', CERN Accelerator School: Ion Sources, "
                    "CERN-2013-007 (2013); arXiv:1404.0960",
        "url": "https://arxiv.org/pdf/1404.0960",
        "access_level": "full_text",
        "accessed": "2026-10-01",
        "accessed_copy_sha256": "7946e9d76a7065f15ff3f2981c2e2b922d25568f22bc20f702369faaf53419ba",
        "note": "page numbers are PDF page indices of the arXiv PDF (same reference as compressor_downselect "
                "REF-CHIGGIATO2013, EV-01..EV-04, EV-20)",
    },
    "SRC-NASA-HDBK-6025": {
        "citation": "NASA-HDBK-6025, 'Guidelines for the Specification and Certification of Titanium Alloys for NASA "
                    "Flight Applications' (approved 2014-04-24)",
        "url": "https://standards.nasa.gov/sites/default/files/standards/NASA/Baseline-w/CHANGE-1/1/Historical/"
               "NASA-HDBK-6025.pdf",
        "access_level": "full_text",
        "accessed": "2026-10-01",
        "accessed_copy_sha256": "cea557a74d04f0c82ad917a06e6dca9bedbd21c5a8b444dd86e207847c267163",
        "note": "the A-basis value is quoted by the handbook from MMPDS-06 (MMPDS itself not accessed): a secondary "
                "quotation of a design-allowables handbook",
    },
    "SRC-DOWNSELECT": {
        "citation": "repository: docs/architecture_comparison/compressor_downselect/compressor_downselect_v2.json "
                    "(DI-1.4 compressor down-selection, v2 = A9.16 regeneration; v1 kept as history)",
        "access_level": "repository",
        "note": "requirement envelope (W1 feed-state closure cases), CD-01..CD-08, EV-01..EV-20, T-1..T-9",
    },
    "SRC-R1-THREAD": {
        "citation": "repository: docs/procurement/web_track_v1/threads/R1_compressor.json (Li 2015 evidence thread)",
        "access_level": "repository",
        "note": "LI2015 inlet diameter 500 mm: abstract via search-engine excerpts only (reconstructed, verify)",
    },
    "SRC-OWNER-147": {
        "citation": "repository: docs/decisions/OD_2026_09_29_owner_answers_147.json row 54 (v0 dry-mass allocation: "
                    "compressor+drive 5.5 kg; 'allocations, not CBEs')",
        "access_level": "repository",
    },
    "SRC-COMPRESSOR-PY": {
        "citation": "repository: abep_sim/compressor.py DragCompressor (dataclass defaults, run(), _run_once(), "
                    "size_for())",
        "access_level": "repository",
        "note": "code defaults are uncited (compressor_downselect CD-01)",
    },
    "SRC-MATERIALS-PY": {
        "citation": "repository: abep_sim/materials.py DB ('literature-class prior' values, no per-value citation)",
        "access_level": "repository",
    },
}


def _p(pid, value, units, basis, source, evidence_class, status, **extra):
    d = {"id": pid, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status}
    d.update(extra)
    return d


# ------------------------------------------------------------------------------------------- cited / labelled values
P_MOLECULAR_LIMIT_PA = 0.1          # 1e-3 mbar
KN_FREE_MOLECULAR_MIN = 0.5
SIGMA_C_M2 = {"N2": 0.43e-18, "O2": 0.40e-18}          # O: TBD
U_TIP_PUBLISHED_MAX_MPS = 500.0
TI64_FTY_A_BASIS_PA = 827e6
RECIRC_RTOL = 1e-4                  # DragCompressor.run fixed-point stopping criterion (module's own tolerance)
MIRROR_RTOL = 1e-12
RPM_SEARCH_MIN = 5000.0             # DragCompressor.size_for rpm search start (code)
SIZE_FOR_MAX_TURBO_ROWS = 6         # DragCompressor.size_for(max_turbo_rows=6) default
SIZE_FOR_MAX_DRAG_STAGES = 4        # DragCompressor.size_for(max_drag_stages=4) default
OWNER_MASS_ALLOCATION_KG = 5.5      # row 54 (allocation, not CBE)
LI2015_INLET_DIAMETER_M = 0.5       # reconstructed, verify (R1 thread)
# compressor_downselect_v2.json requirement_summary.A_inlet_min_m2["0.25"] (min, max): PROPOSED b = 0.25 target
A_INLET_MIN_B025_RANGE_M2 = (0.1128299365, 0.1137287437)   # re-pinned after the W1 S6.8 domain gate (only DC-S12-G20 closes in domain)

CITED_VALUES = [
    _p("P-MOLECULAR-LIMIT", P_MOLECULAR_LIMIT_PA, "Pa",
       "'this type of pump works at full pumping speed only in molecular regimes (P < 10^-3 mbar)'; applied to every "
       "turbo-row and drag-stage outlet pressure as the domain of the free-molecular Gaede characteristic of "
       "DragCompressor (repository finding compressor_downselect CD-04)",
       "SRC-CHIGGIATO2013 Sec. 4.1.2, PDF p. 23 (= compressor_downselect EV-03)", "inferred", "CITED"),
    _p("P-KN-FREE-MOLECULAR", KN_FREE_MOLECULAR_MIN, "-",
       "Table 7: 'Kn > 0.5 Free molecular flow'; Kn = lambda / D (Eq. 10) with D = drag-channel depth h",
       "SRC-CHIGGIATO2013 Sec. 2.2, Eq. (10), Table 7, PDF p. 6", "inferred", "CITED"),
    _p("P-SIGMA-C-N2", SIGMA_C_M2["N2"], "m^2", "elastic collision cross section 0.43 nm^2 (Table 6); mean free path "
       "lambda = 1/(sqrt(2) n sigma_c) (Eq. 7), mixture form 1/(sqrt(2) sum_k n_k sigma_k) as in abep_sim/interstage.py",
       "SRC-CHIGGIATO2013 Sec. 2.2, Eq. (7), Table 6, PDF p. 5", "inferred",
       "CITED (no primary reference given by the lecture; verify primary)"),
    _p("P-SIGMA-C-O2", SIGMA_C_M2["O2"], "m^2", "elastic collision cross section 0.40 nm^2 (Table 6)",
       "SRC-CHIGGIATO2013 Sec. 2.2, Table 6, PDF p. 5", "inferred",
       "CITED (no primary reference given by the lecture; verify primary)"),
    _p("P-SIGMA-C-O", "TBD", "m^2", "atomic-O gas-kinetic collision cross section; not in the accessed sources (same "
       "TBD as abep_sim/interstage.py CATALOGUE 'collision_cross_section:O'). Consequence: the drag-channel Kn is "
       "evaluated with the O contribution omitted, an UPPER bound on Kn (a necessary, not sufficient, check)",
       "none", "TBD", "TBD"),
    _p("P-U-TIP-PUBLISHED-MAX", U_TIP_PUBLISHED_MAX_MPS, "m/s",
       "'Each set of rotor blades is machined from a single block of high-strength aluminium alloys. Typical pumps "
       "equipped with a DN100 flange rotate at a frequency of 1 kHz, therefore approaching circumferential speeds up "
       "to 500 m/s': upper end of the searched tip-speed range (published commercial practice, not a Vyovrinda limit)",
       "SRC-CHIGGIATO2013 Sec. 4.1.2, PDF p. 24 (= compressor_downselect EV-04)", "inferred", "CITED"),
    _p("P-TI64-FTY-A-BASIS", TI64_FTY_A_BASIS_PA, "Pa",
       "'the A-basis values of Ti-6Al-4V annealed plate with thickness of 50.8 to 101.6 mm (2 to 4 in) are: tensile "
       "strength = 896 MPa (130 ksi); yield strength = 827 MPa (120 ksi) ... (MMPDS-06 Handbook)'. Room-temperature "
       "plate value; the rotor product form and elevated-temperature knock-down are TBD",
       "SRC-NASA-HDBK-6025 Sec. 3 (definitions, 'Mechanical Properties'), p. 18 of 75", "inferred",
       "CITED (secondary quotation of MMPDS-06)"),
    _p("P-TI64-DENSITY", DB["Ti6Al4V"].density, "kg/m^3", "rotor density used in sigma = rho u^2 and in the module mass "
       "model (materials.DB['Ti6Al4V'].density)", "SRC-MATERIALS-PY", "assumed",
       "UNCITED_DB_PRIOR (verify against a primary datasheet)"),
    _p("P-TI64-T-SERVICE", DB["Ti6Al4V"].T_max_K, "K", "materials.DB['Ti6Al4V'].T_max_K used as the thermal gate on the "
       "module's lumped compressor temperature", "SRC-MATERIALS-PY", "assumed", "UNCITED_DB_PRIOR (verify)"),
    _p("P-STRESS-SAFETY", DragCompressor.stress_safety, "-", "safety factor on the allowable (DragCompressor."
       "stress_safety code default); the flight factor is an owner/design-policy decision",
       "SRC-COMPRESSOR-PY", "assumed", "CODE_DEFAULT_UNCITED; LEGACY_PARAMETRIC_SENSITIVITY only (A9.9 S2.3 / "
       "OQ-F3-01: flight rotor acceptance only through a registered strength basis, rotor_strength.qualify_rotor)"),
    _p("P-RPM-SEARCH-MIN", RPM_SEARCH_MIN, "rpm", "lower end of the size_for rpm search (range(5000, ...)); used as the "
       "lower end of the tip-speed range", "SRC-COMPRESSOR-PY", "assumed", "MODULE_LIMIT"),
    _p("P-RECIRC-RTOL", RECIRC_RTOL, "-", "DragCompressor.run leak-recirculation fixed-point stopping criterion; a "
       "design whose re-evaluated residual exceeds it is NOT converged", "SRC-COMPRESSOR-PY", "model-derived",
       "MODULE_TOLERANCE"),
    _p("P-OWNER-MASS-ALLOCATION", OWNER_MASS_ALLOCATION_KG, "kg", "owner v0 dry allocation 'compressor+drive 5.5' "
       "(mass_power_a9_v2 MA-AL-02); used only to report allocation margin, never as a gate or a CBE",
       "SRC-OWNER-147 row 54", "owner-allocation", "OWNER_ALLOCATION (not a CBE)"),
    _p("P-LI2015-INLET-DIAMETER", LI2015_INLET_DIAMETER_M, "m", "inlet diameter of the Li 2015 active intake (abstract "
       "via search-engine excerpts only); one A_turbo grid point = pi (D/2)^2", "SRC-R1-THREAD (LI2015)",
       "reconstructed", "VERIFY (first-hand text not accessed)"),
    _p("P-A-INLET-MIN-RANGE", list(A_INLET_MIN_B025_RANGE_M2), "m^2", "minimum inlet area for the PROPOSED backflow "
       "target b = 0.25 over the W1 candidate-cases (in-domain closures, A9.13 S6.8), max(2S/u_ref, 4S/c_bar) (compressor_downselect CD-02); ends of "
       "the A_turbo search range", "SRC-DOWNSELECT requirement_summary.A_inlet_min_m2['0.25']",
       "model-derived", "PROPOSED-DERIVED (from PROPOSED b and W1 inputs)"),
]

# Materials: only those with a CITED allowable are searched (fail closed); the others are listed with the reason.
CITED_ALLOWABLES_PA = {"Ti6Al4V": TI64_FTY_A_BASIS_PA}   # legacy PARAMETRIC_SENSITIVITY stress case only (A9.9 S2.3)
MATERIALS_EXCLUDED = {
    "Al6061": "allowable TBD: materials.DB yield 276 MPa is an uncited prior; no accessed A/B-basis source. Chiggiato "
              "names 'high-strength aluminium alloys' for commercial rotors (alloy and temper not stated). Re-enters "
              "only through a registered rotor-strength basis (rotor_strength.register_basis) plus an AO disposition "
              "(A9.13 S6.9)",
    "CFRP": "allowable TBD (materials.DB 600 MPa uncited prior; laminate-dependent); bare CFRP wetted parts recede "
            "0.48-15.9 mm over 26,000 h at the ram AO yield (compressor_downselect CD-07); owner OD-C3 PROPOSED "
            "metallic/coated a priori. Re-enters only through a registered basis plus laminate definition, directional "
            "allowables, temperature / moisture / environment basis, manufacturing / inspection basis and AO "
            "disposition of every exposed surface (A9.13 S6.9)",
}


def registered_bases_for(material: str) -> list:
    """Registered rotor-strength bases (rotor_strength.REGISTRY) that apply to ``material`` (no transfer)."""
    return sorted(k for k, b in rs.REGISTRY.items() if b.materials_db_key == material)


def material_admission(material: str, extra_basis: Mapping | None = None) -> dict:
    """Admission status of a rotor material for the design search (A9.13 S6.9, A9.9 S2.3). A handbook strength number
    never admits a material: only a registered rotor-strength basis does, plus the S6.9 extra records for re-admitted
    materials (Al: AO disposition; CFRP: laminate, directional allowables, environment, manufacturing / inspection,
    AO disposition)."""
    if material not in DB:
        raise SynthesisInputError(f"rotor material {material!r} is not in materials.DB")
    bases = registered_bases_for(material)
    extra = dict(extra_basis or {})
    missing_extra = [k for k in READMITTED_MATERIALS.get(material, ()) if not str(extra.get(k, "")).strip()]
    if bases and not missing_extra:
        return {"material": material, "status": "ADMITTED_VIA_REGISTERED_BASIS", "bases": bases,
                "structural_acceptance": "rotor_strength.qualify_rotor only"}
    if material in CITED_ALLOWABLES_PA:
        return {"material": material, "status": STRESS_CASE_LEGACY, "bases": bases, "missing_extra": missing_extra,
                "structural_acceptance": ST_NOT_EVALUATED_MATERIAL_BASIS,
                "note": rs.LEGACY_SENSITIVITY_LABEL}
    return {"material": material, "status": ST_NOT_EVALUATED_MATERIAL_BASIS, "bases": bases,
            "missing_extra": missing_extra, "reason": MATERIALS_EXCLUDED.get(material, "no registered basis")}

# --------------------------------------------------------------------------------------------- coefficient registry
# Role of every DragCompressor field in this search. The closing test ids are compressor_downselect T-1..T-9.
SEARCHED = "SEARCHED"
DERIVED = "DERIVED"
FIXED = "FIXED_CODE_DEFAULT"
FROM_INLET = "FROM_INLET_RECORD"
FIELD_ROLES = {
    "turbo_rows": (SEARCHED, "N_turbo", "-", "T-1/T-2"),
    "turbo_area_m2": (SEARCHED, "A_turbo", "m^2", "T-2"),
    "turbo_radius_m": (DERIVED, "R_turbo (tip radius from A_turbo and hub ratio)", "m", "T-2 (hub-ratio bounds TBD)"),
    "turbo_kS": (FIXED, "turbo pumping-speed coefficient", "-", "T-2"),
    "turbo_kK": (FIXED, "turbo ln K0 coefficient per row", "-", "T-1"),
    "turbo_blade_area_frac": (FIXED, "blade area fraction (drag area, mass)", "-", "T-4/T-7"),
    "turbo_disc_thickness_m": (FIXED, "turbo disc thickness (mass)", "m", "T-7"),
    "n_stages": (SEARCHED, "N_drag", "-", "T-1"),
    "rotor_radius_m": (FIXED, "R_rotor (drag rotor radius)", "m", "T-1/T-7"),
    "rpm": (SEARCHED, "RPM (via turbo tip speed)", "rpm", "T-2"),
    "h_mm": (FIXED, "h (drag channel depth)", "mm", "T-1"),
    "w_mm": (FIXED, "w (drag channel width)", "mm", "T-1"),
    "L_per_stage_m": (FIXED, "L (unwrapped drag channel length per stage)", "m", "T-1"),
    "xi": (FIXED, "xi (drag-channel geometric efficiency; the module's equivalent of the helix-angle effect)", "-",
           "T-1"),
    "rotor_material": (SEARCHED, "rotor material (restricted to cited allowables)", "-", "T-6"),
    "stress_safety": (FIXED, "stress safety factor", "-", "owner policy"),
    "T_gas_K": (FROM_INLET, "gas temperature for c_bar", "K", "T-5"),
    "leak_conductance_m3_s": (FIXED, "outlet-to-inlet leak conductance", "m^3/s", "T-8"),
    "k_bear_W_per_rads": (FIXED, "bearing loss coefficient", "W s/rad", "T-4"),
    "eta_motor": (FIXED, "motor efficiency (P_el = P_shaft / eta_motor + P_ctrl)", "-", "T-4"),
    "P_ctrl_W": (FIXED, "control power", "W", "T-4"),
    "rotor_disc_thickness_m": (FIXED, "drag rotor disc thickness (mass)", "m", "T-7"),
    "stator_mass_factor": (FIXED, "stator + housing mass relative to rotor", "-", "T-7"),
    "motor_kg_per_Nm": (FIXED, "motor mass per torque", "kg/(N m)", "T-7"),
    "bearing_kg": (FIXED, "bearing mass", "kg", "T-7"),
    "conductance_to_sink_W_K": (FIXED, "thermal conductance to sink", "W/K", "T-5"),
    "T_sink_K": (FIXED, "sink temperature", "K", "T-5"),
}


class SynthesisInputError(ValueError):
    """An input record or design point is malformed (refused, never repaired)."""


def module_defaults() -> dict:
    return {f.name: f.default for f in dataclasses.fields(DragCompressor)}


def coefficient_registry() -> list[dict]:
    """One parameter record per DragCompressor field (value, units, basis, source, evidence class, status)."""
    defaults = module_defaults()
    missing = set(defaults) ^ set(FIELD_ROLES)
    if missing:
        raise SynthesisInputError(f"FIELD_ROLES out of sync with DragCompressor fields: {sorted(missing)}")
    out = []
    for f, (role, name, units, test) in FIELD_ROLES.items():
        if role == FIXED:
            out.append(_p(f"C-{f}", defaults[f], units, f"{name}; not searched: no accessed open source gives a value "
                          "or a range (compressor_downselect CD-01)", f"SRC-COMPRESSOR-PY DragCompressor.{f}",
                          "assumed", f"FIXED_CODE_DEFAULT_UNCITED (closing test {test})", role=role))
        elif role == SEARCHED:
            out.append(_p(f"C-{f}", "SEARCHED", units, name, "see search_variables", "see search_variables",
                          "SEARCHED", role=role))
        elif role == DERIVED:
            out.append(_p(f"C-{f}", "DERIVED", units, f"{name} = sqrt(A_turbo / (pi (1 - nu^2))) with hub ratio nu "
                          "(A9.13 S6.7; nu = 0 is the zero-hub analytical bound only; closing test " + test + ")",
                          "geometry", "model-derived", "DERIVED", role=role))
        else:
            out.append(_p(f"C-{f}", "FROM_INLET", units, f"{name} = inlet record T", "inlet record",
                          "per inlet record", "FROM_INLET", role=role))
    return out


def search_variables(grid: "SearchGrid | None" = None) -> list[dict]:
    """The A9.7 candidate variables with the range basis actually used (or FIXED / TBD and excluded)."""
    g = grid or SearchGrid()
    d = module_defaults()
    return [
        _p("N_turbo", list(g.n_turbo), "-", "turbo rows 1..6: DragCompressor.size_for(max_turbo_rows=6) module limit",
           "SRC-COMPRESSOR-PY size_for", "assumed", "SEARCHED (module limit)"),
        _p("A_turbo", list(g.a_turbo_m2), "m^2", "ends: minimum inlet area range for the PROPOSED b = 0.25 target "
           "(P-A-INLET-MIN-RANGE); interior point: Li 2015 inlet area pi*0.25^2 (P-LI2015-INLET-DIAMETER, verify)",
           "SRC-DOWNSELECT CD-02; SRC-R1-THREAD", "model-derived / reconstructed", "SEARCHED (evidence-bounded range)"),
        _p("R_turbo", "sqrt(A_turbo / (pi (1 - nu^2)))", "m", "tip radius derived from A_turbo and the hub ratio nu "
           "(A9.13 S6.7); not an independent variable", "geometry", "model-derived", "DERIVED"),
        _p("hub_ratio", list(g.hub_ratios), "-", "hub ratio nu = R_hub / R_tip: explicit geometry variable (A9.13 "
           "S6.7). Searched values are a declared PARAMETRIC_SENSITIVITY coverage of the definitional domain [0, 1); "
           "nu = 0 is the zero-hub analytical bound only (not buildable). Bounds TBD from: " +
           "; ".join(HUB_BOUND_SOURCES), "owner decision A9.13 S6.7 (no numerical bound given)", "assumed",
           "SEARCHED (PARAMETRIC_SENSITIVITY; bounds TBD)"),
        _p("blade_span", "R_tip (1 - nu)", "m", "turbo blade span derived from the tip radius and hub ratio "
           "(A9.13 S6.7)", "geometry", "model-derived", "DERIVED"),
        _p("N_drag", list(g.n_drag), "-", "drag stages 0..4: DragCompressor.size_for(max_drag_stages=4) module limit",
           "SRC-COMPRESSOR-PY size_for", "assumed", "SEARCHED (module limit)"),
        _p("R_rotor", d["rotor_radius_m"], "m", "drag rotor radius: no accessed source gives a range", "SRC-COMPRESSOR-PY",
           "assumed", "FIXED_CODE_DEFAULT (excluded from search; TBD evidence T-1/T-7)"),
        _p("RPM", f"via turbo tip speed u_t in [u(R_turbo, {RPM_SEARCH_MIN:g} rpm), {U_TIP_PUBLISHED_MAX_MPS:g} m/s], "
           f"{g.n_tip_speeds} linear points", "rpm", "lower end: size_for rpm search start (P-RPM-SEARCH-MIN); upper "
           "end: published TMP circumferential speed (P-U-TIP-PUBLISHED-MAX); rotor-stress gate rejects the excess",
           "SRC-COMPRESSOR-PY; SRC-CHIGGIATO2013", "assumed / inferred", "SEARCHED (module limit + cited practice)"),
        _p("h", d["h_mm"], "mm", "drag channel depth: no accessed source", "SRC-COMPRESSOR-PY", "assumed",
           "FIXED_CODE_DEFAULT (excluded; TBD evidence T-1)"),
        _p("w", d["w_mm"], "mm", "drag channel width: no accessed source", "SRC-COMPRESSOR-PY", "assumed",
           "FIXED_CODE_DEFAULT (excluded; TBD evidence T-1)"),
        _p("L", d["L_per_stage_m"], "m", "drag channel length per stage: no accessed source", "SRC-COMPRESSOR-PY",
           "assumed", "FIXED_CODE_DEFAULT (excluded; TBD evidence T-1)"),
        _p("xi", d["xi"], "-", "the module has no helix angle; its equivalent is the geometric efficiency xi of the drag "
           "channel (ln K0 and S0 both scale with xi). No accessed source gives a value", "SRC-COMPRESSOR-PY", "assumed",
           "FIXED_CODE_DEFAULT (excluded; TBD evidence T-1)"),
        _p("rotor_material", list(g.materials), "-", "only materials with a CITED allowable (CITED_ALLOWABLES_PA); "
           "excluded: " + "; ".join(f"{k}: {v}" for k, v in MATERIALS_EXCLUDED.items()),
           "SRC-NASA-HDBK-6025", "inferred", "SEARCHED (restricted)"),
    ]


# -------------------------------------------------------------------------------------------------------- inlet record
@dataclass(frozen=True)
class InletRecord:
    """Compressor inlet state (the F1 intake-exit / F2 filter-outlet interface record).

    mdot_kgps: per-species mass flow into the compressor [kg/s]; p_total_Pa: inlet (plenum) total pressure; T_K: gas
    temperature. p_species_Pa is optional; DragCompressor splits p_total by number-flow fraction, so a supplied split
    must agree with that convention (else refused: the module cannot represent it)."""
    record_id: str
    mdot_kgps: Mapping[str, float]
    p_total_Pa: float
    T_K: float
    label: str
    source: str
    evidence_class: str
    status: str = ""
    p_species_Pa: Mapping[str, float] | None = None
    extra: Mapping = field(default_factory=dict)

    def __post_init__(self):
        if self.label not in INLET_LABELS:
            raise SynthesisInputError(f"inlet label must be one of {INLET_LABELS}")
        if set(self.mdot_kgps) != set(SPECIES):
            raise SynthesisInputError(f"inlet record must carry exactly {SPECIES}, got {sorted(self.mdot_kgps)}")
        for s, v in self.mdot_kgps.items():
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0.0):
                raise SynthesisInputError(f"mdot[{s}] must be finite and >= 0")
        if sum(self.mdot_kgps.values()) <= 0.0:
            raise SynthesisInputError("total inlet mass flow must be > 0")
        for k in ("p_total_Pa", "T_K"):
            v = getattr(self, k)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0.0):
                raise SynthesisInputError(f"{k} must be finite and > 0")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise SynthesisInputError(f"evidence_class must be one of {EVIDENCE_CLASSES}")
        if not self.source.strip():
            raise SynthesisInputError("inlet record needs a source")
        if self.p_species_Pa is not None:
            conv = self.module_partial_pressures()
            if set(self.p_species_Pa) != set(SPECIES):
                raise SynthesisInputError("p_species_Pa must carry exactly O, N2, O2")
            if abs(sum(self.p_species_Pa.values()) / self.p_total_Pa - 1.0) > 1e-9:
                raise SynthesisInputError("p_species_Pa does not sum to p_total_Pa")
            for s in SPECIES:
                if abs(self.p_species_Pa[s] - conv[s]) > 1e-6 * self.p_total_Pa:
                    raise SynthesisInputError(
                        f"p_species_Pa[{s}] differs from the DragCompressor convention (partial pressure proportional "
                        "to number flow); the module cannot represent this inlet state (refused, not repaired)")

    def module_partial_pressures(self) -> dict:
        nflow = {s: self.mdot_kgps[s] / M_SPECIES[s] for s in SPECIES}
        tot = sum(nflow.values())
        return {s: self.p_total_Pa * nflow[s] / tot for s in SPECIES}

    def as_dict(self) -> dict:
        return {"record_id": self.record_id, "label": self.label, "mdot_kgps": dict(self.mdot_kgps),
                "p_total_Pa": self.p_total_Pa, "T_K": self.T_K, "source": self.source,
                "evidence_class": self.evidence_class, "status": self.status,
                "p_species_Pa": dict(self.p_species_Pa) if self.p_species_Pa else None, "extra": dict(self.extra)}


# ------------------------------------------------------------------------------------------------------- search grid
@dataclass(frozen=True)
class SearchGrid:
    n_turbo: tuple = tuple(range(1, SIZE_FOR_MAX_TURBO_ROWS + 1))
    a_turbo_m2: tuple = (A_INLET_MIN_B025_RANGE_M2[0], math.pi * (LI2015_INLET_DIAMETER_M / 2.0) ** 2,
                         A_INLET_MIN_B025_RANGE_M2[1])
    n_tip_speeds: int = 6
    n_drag: tuple = tuple(range(0, SIZE_FOR_MAX_DRAG_STAGES + 1))
    materials: tuple = ("Ti6Al4V",)
    hub_ratios: tuple = HUB_RATIO_PARAMETRIC

    def __post_init__(self):
        for m in self.materials:
            if m not in CITED_ALLOWABLES_PA and not registered_bases_for(m):
                raise SynthesisInputError(f"search material {m!r} has neither a registered rotor-strength basis nor "
                                          "the legacy cited sensitivity allowable (A9.13 S6.9 / A9.9 S2.3)")
        if any(a <= 0 for a in self.a_turbo_m2) or self.n_tip_speeds < 2:
            raise SynthesisInputError("bad grid")
        if not self.hub_ratios or any(not (_real(h) is not None and 0.0 <= h < 1.0) for h in self.hub_ratios):
            raise SynthesisInputError("hub ratios must be finite and in [0, 1)")

    def tip_speeds(self, r_turbo_m: float) -> list[float]:
        u_lo = r_turbo_m * RPM_SEARCH_MIN * 2.0 * math.pi / 60.0
        u_hi = U_TIP_PUBLISHED_MAX_MPS
        if u_lo >= u_hi:
            return []
        n = self.n_tip_speeds
        return [u_lo + (u_hi - u_lo) * i / (n - 1) for i in range(n)]

    def designs(self) -> list[dict]:
        """Design points. Ids of zero-hub points keep the historical form T{n}-A{i}-U{j}-D{k}-{mat}; points with a
        hub get the suffix -H{nu}."""
        out = []
        for ia, a in enumerate(self.a_turbo_m2):
            for nu in self.hub_ratios:
                r = r_turbo_from_area(a, nu)
                for iu, u in enumerate(self.tip_speeds(r)):
                    for nt in self.n_turbo:
                        for nd in self.n_drag:
                            for mat in self.materials:
                                sfx = "" if nu == 0.0 else f"-H{nu:g}"
                                out.append({"id": f"T{nt}-A{ia}-U{iu}-D{nd}-{mat}{sfx}", "N_turbo": nt,
                                            "A_turbo_m2": a, "R_turbo_m": r, "u_tip_turbo_mps": u,
                                            "rpm": rpm_from_tip(u, r), "N_drag": nd, "rotor_material": mat,
                                            **hub_geometry(a, nu)})
        return out


def r_turbo_from_area(a_m2: float, hub_ratio: float = 0.0) -> float:
    """Tip radius of an annulus of swept area A with hub ratio nu: R = sqrt(A / (pi (1 - nu^2))) (A9.13 S6.7).
    nu = 0 is the zero-hub analytical bound."""
    if not 0.0 <= hub_ratio < 1.0:
        raise SynthesisInputError("hub ratio must be in [0, 1)")
    return math.sqrt(a_m2 / (math.pi * (1.0 - hub_ratio ** 2)))


def hub_geometry(a_m2: float, hub_ratio: float) -> dict:
    """Explicit hub geometry record of a turbo-row annulus (A9.13 S6.7)."""
    r = r_turbo_from_area(a_m2, hub_ratio)
    return {"hub_ratio": float(hub_ratio), "R_hub_m": hub_ratio * r, "blade_span_m": r * (1.0 - hub_ratio),
            "hub_geometry_status": HUB_ZERO_BOUND if hub_ratio == 0.0 else HUB_PARAMETRIC}


def rpm_from_tip(u_mps: float, r_m: float) -> float:
    return u_mps / r_m * 60.0 / (2.0 * math.pi)


# ------------------------------------------------------------------------------------------- strict-mode evidence
def strict_blockers(inlet: InletRecord, coefficient_evidence: Mapping[str, dict] | None = None) -> list[dict]:
    """What MODE_STRICT needs before it may evaluate anything. Empty list = evaluable."""
    ev = dict(coefficient_evidence or {})
    out = []
    for f, (role, name, _units, test) in FIELD_ROLES.items():
        if role != FIXED:
            continue
        e = ev.get(f)
        if e is None or e.get("evidence_class") in (None, "assumed", "TBD") or not str(e.get("source", "")).strip():
            out.append({"id": f"C-{f}", "what": name, "status": "CODE_DEFAULT_UNCITED (assumed)",
                        "needs": f"non-assumed evidence (compressor_downselect test {test})"})
        else:
            try:
                validate_coefficient(f, e.get("value"))
            except SynthesisInputError as exc:
                out.append({"id": f"C-{f}", "what": name, "status": "NON_FINITE_OR_OUT_OF_DOMAIN",
                            "needs": f"a finite in-domain value ({exc})"})
    if inlet.label != LABEL_INTERFACE or inlet.evidence_class == "assumed":
        out.append({"id": "INLET", "what": f"inlet record {inlet.record_id}", "status": inlet.label,
                    "needs": "an F1/F2 interface record (abep_sim/design/intake_synthesis.py F1-ID-03, "
                             "abep_sim/design/filter_stage.py F2-IF-03) with non-assumed evidence"})
    dens = ev.get("rotor_density")
    if dens is None or dens.get("evidence_class") in (None, "assumed", "TBD") or not str(dens.get("source", "")).strip():
        out.append({"id": "P-TI64-DENSITY", "what": "rotor density", "status": "UNCITED_DB_PRIOR",
                    "needs": "cited density for the rotor alloy"})
    elif not _positive_finite(dens.get("value")):          # NaN / inf / <= 0 never passes the gate (PR #36)
        out.append({"id": "P-TI64-DENSITY", "what": "rotor density", "status": "NON_FINITE_OR_OUT_OF_DOMAIN",
                    "needs": "a finite, positive cited density for the rotor alloy"})
    elif abs(float(dens["value"]) / DB["Ti6Al4V"].density - 1.0) > 1e-9:
        out.append({"id": "P-TI64-DENSITY", "what": "rotor density", "status": "MODULE_CANNOT_REPRESENT",
                    "needs": "the cited density differs from materials.DB, which DragCompressor reads; a materials "
                             "change is a model change (CLAUDE.md rule 2), outside this lane"})
    bid = ev.get("rotor_strength_basis_id", {}).get("value") if isinstance(ev.get("rotor_strength_basis_id"),
                                                                          Mapping) else None
    if rs.get_registered(bid) is None:
        out.append({"id": "ROTOR-STRENGTH-BASIS", "what": "registered rotor-strength basis (A9.9 S2.3 / MCC-03)",
                    "status": ST_NOT_EVALUATED_MATERIAL_BASIS,
                    "needs": "an owner-registered basis in abep_sim.rotor_strength.REGISTRY (stock / product form, "
                             "design temperature, yield AND ultimate allowables, factors, maximum speed, proof spin); "
                             "supply its id as coefficient_evidence['rotor_strength_basis_id']"})
    return out


def _basis_id(design: Mapping, coefficient_evidence: Mapping | None):
    if design.get("rotor_strength_basis_id"):
        return design["rotor_strength_basis_id"]
    rec = (coefficient_evidence or {}).get("rotor_strength_basis_id")
    return rec.get("value") if isinstance(rec, Mapping) else None


def _not_evaluated_status(blockers: list) -> str:
    """NOT_EVALUATED_MATERIAL_BASIS whenever the registered rotor basis is missing (A9.9 S2.3 / D-05), else
    NOT_EVALUATED."""
    return ST_NOT_EVALUATED_MATERIAL_BASIS if any(b["id"] == "ROTOR-STRENGTH-BASIS" for b in blockers) \
        else ST_NOT_EVALUATED


def _positive_finite(v) -> bool:
    if isinstance(v, bool):
        return False
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and x > 0.0


# ------------------------------------------------------------------------------------------------- mirror (checks)
def stage_trace(comp: DragCompressor, p_in_Pa: float, mdot_species: Mapping[str, float]) -> dict:
    """Diagnostic mirror of DragCompressor._run_once's pressure cascade, exposing the UNCLIPPED per-species Gaede K of
    every turbo row and drag stage. Used only for checks; its p_out must reproduce the module's (else MODEL_ERROR)."""
    u = comp.u
    h = comp.h_mm * 1e-3; w = comp.w_mm * 1e-3; L = comp.L_per_stage_m
    S0 = comp.xi * u * h * w / 2.0
    nflow = {s: mdot_species[s] / M_SPECIES[s] for s in mdot_species}
    ntot = sum(nflow.values()) or 1e-30
    p_s = {s: p_in_Pa * nflow[s] / ntot for s in nflow}
    u_t = comp.turbo_radius_m * comp.rpm * 2 * math.pi / 60.0
    S_t = comp.turbo_kS * u_t * comp.turbo_area_m2
    stages = []

    def _stage(kind, idx, lnK0_of, S):
        k_raw = {}
        for s in nflow:
            cb = comp._cbar(M_SPECIES[s])
            K0 = math.exp(lnK0_of(cb))
            Q = nflow[s] * K_B * comp.T_gas_K
            K = K0 - (K0 - 1.0) * Q / max(S * p_s[s], 1e-30)
            k_raw[s] = K
            p_s[s] *= max(min(K, K0), 1.0)
        stages.append({"kind": kind, "index": idx, "K_unclipped": k_raw, "p_out_Pa": sum(p_s.values()),
                       "p_species_out_Pa": dict(p_s)})

    for row in range(comp.turbo_rows):
        _stage("turbo", row, lambda cb: comp.turbo_kK * u_t / cb, S_t)
    for st in range(comp.n_stages):
        _stage("drag", st, lambda cb: 2 * u * L / (cb * h) * comp.xi, S0)
    return {"stages": stages, "p_out_Pa": sum(p_s.values())}


def drag_knudsen_upper(p_species_Pa: Mapping[str, float], T_K: float, h_m: float) -> float:
    """Kn = lambda/h with lambda = 1/(sqrt(2) sum_k n_k sigma_k) over the species WITH a cited sigma (N2, O2); the O
    contribution (sigma TBD) is omitted, so the value is an upper bound on the true mixture Kn."""
    denom = sum(p_species_Pa.get(s, 0.0) / (K_B * T_K) * SIGMA_C_M2[s] for s in SIGMA_C_M2)
    if denom <= 0.0:
        return math.inf
    return 1.0 / (math.sqrt(2.0) * denom) / h_m


# --------------------------------------------------------------------------------------------------- evaluation
def _finite(*xs) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


# Physical domain of the FIXED DragCompressor coefficients (definitional bounds only, no evidence range implied):
# 'pos' > 0, 'nonneg' >= 0, 'frac' in (0, 1]. Consolidated verification round 1 (SW-02): a non-finite or
# out-of-domain coefficient is refused, never evaluated (a NaN safety factor used to fail the stress gate open).
COEFFICIENT_DOMAIN = {
    "turbo_kS": "pos", "turbo_kK": "pos", "turbo_blade_area_frac": "frac", "turbo_disc_thickness_m": "pos",
    "rotor_radius_m": "pos", "h_mm": "pos", "w_mm": "pos", "L_per_stage_m": "pos", "xi": "frac",
    "stress_safety": "pos", "leak_conductance_m3_s": "nonneg", "k_bear_W_per_rads": "nonneg", "eta_motor": "frac",
    "P_ctrl_W": "nonneg", "rotor_disc_thickness_m": "pos", "stator_mass_factor": "nonneg",
    "motor_kg_per_Nm": "nonneg", "bearing_kg": "nonneg", "conductance_to_sink_W_K": "pos", "T_sink_K": "pos",
}


def _real(v) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def validate_coefficient(name: str, value) -> float:
    """Refuse a non-finite or out-of-domain FIXED coefficient value (SynthesisInputError)."""
    if FIELD_ROLES.get(name, (None,))[0] != FIXED:
        raise SynthesisInputError(f"only FIXED coefficients can be overridden, not {name}")
    v = _real(value)
    dom = COEFFICIENT_DOMAIN[name]
    if v is None or (dom == "pos" and not v > 0.0) or (dom == "nonneg" and not v >= 0.0) or \
            (dom == "frac" and not 0.0 < v <= 1.0):
        raise SynthesisInputError(f"coefficient {name}={value!r} is non-finite or outside its domain ({dom})")
    return v


def validate_design(design: Mapping) -> None:
    """Refuse a malformed design vector (SW-03): rpm, A_turbo_m2 and R_turbo_m finite and > 0; N_turbo and N_drag
    non-negative integers; rotor_material in materials.DB (an uncited DB material is rejected later by the
    allowable gate, R_ALLOWABLE_TBD)."""
    for k in ("rpm", "A_turbo_m2"):
        v = _real(design.get(k))
        if v is None or not v > 0.0:
            raise SynthesisInputError(f"design {design.get('id')}: {k}={design.get(k)!r} must be finite and > 0")
    if "R_turbo_m" in design:
        v = _real(design["R_turbo_m"])
        if v is None or not v > 0.0:
            raise SynthesisInputError(f"design {design.get('id')}: R_turbo_m={design['R_turbo_m']!r} must be finite "
                                      "and > 0")
    for k in ("N_turbo", "N_drag"):
        v = design.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or \
                float(v) != int(v) or int(v) < 0:
            raise SynthesisInputError(f"design {design.get('id')}: {k}={v!r} must be a non-negative integer")
    if design.get("rotor_material") not in DB:
        raise SynthesisInputError(f"design {design.get('id')}: rotor_material {design.get('rotor_material')!r} is "
                                  "not in materials.DB")
    if "hub_ratio" in design:
        nu = _real(design["hub_ratio"])
        if nu is None or not 0.0 <= nu < 1.0:
            raise SynthesisInputError(f"design {design.get('id')}: hub_ratio={design['hub_ratio']!r} must be in [0, 1)")
        if "R_turbo_m" in design:
            r_exp = r_turbo_from_area(float(design["A_turbo_m2"]), nu)
            if abs(float(design["R_turbo_m"]) / r_exp - 1.0) > 1e-9:
                raise SynthesisInputError(f"design {design.get('id')}: R_turbo_m inconsistent with A_turbo and "
                                          "hub_ratio (refused, not repaired)")


def build_compressor(design: Mapping, inlet: InletRecord, coefficient_overrides: Mapping[str, object] | None = None
                     ) -> DragCompressor:
    validate_design(design)
    kw = module_defaults()
    for f, v in (coefficient_overrides or {}).items():
        kw[f] = validate_coefficient(f, v)
    a = float(design["A_turbo_m2"])
    r = float(design.get("R_turbo_m", r_turbo_from_area(a, float(design.get("hub_ratio", 0.0)))))
    kw.update({"turbo_rows": int(design["N_turbo"]), "turbo_area_m2": a, "turbo_radius_m": r,
               "n_stages": int(design["N_drag"]), "rpm": float(design["rpm"]),
               "rotor_material": design["rotor_material"], "T_gas_K": float(inlet.T_K)})
    return DragCompressor(**kw)


def evaluate_design(design: Mapping, inlet: InletRecord, mode: str = MODE_PARAMETRIC,
                    coefficient_evidence: Mapping[str, dict] | None = None) -> dict:
    """Evaluate one design point. Returns a record with status, reasons, diagnostics and (feasible only) outputs."""
    if mode not in MODES:
        raise SynthesisInputError(f"mode must be one of {MODES}")
    if mode == MODE_STRICT:
        blk = strict_blockers(inlet, coefficient_evidence)
        if blk:
            return {"id": design.get("id"), "status": _not_evaluated_status(blk), "reasons": [], "blockers": blk,
                    "outputs": None, "diagnostics": None,
                    "rotor_qualification": ST_NOT_EVALUATED_MATERIAL_BASIS
                    if rs.get_registered(_basis_id(design, coefficient_evidence)) is None else ST_NOT_EVALUATED}
    overrides = {f: e["value"] for f, e in (coefficient_evidence or {}).items()
                 if f in FIELD_ROLES and FIELD_ROLES[f][0] == FIXED}
    comp = build_compressor(design, inlet, overrides)
    md = {s: float(inlet.mdot_kgps[s]) for s in SPECIES}
    reasons: list[str] = []
    diag: dict = {}

    # --- rotor structural acceptance (A9.9 S2.3 / MCC-03, D-05): ONLY rotor_strength.qualify_rotor grants it. Without a
    # registered basis, MODE_PARAMETRIC keeps the labelled legacy thin-ring case (cited 827 MPa A-basis plate value x
    # the uncited code factor 2.0, sigma = rho u^2) as a PARAMETRIC_SENSITIVITY screen; it never qualifies a rotor.
    mat = comp.rotor_material
    u_t = comp.turbo_radius_m * comp.rpm * 2 * math.pi / 60.0
    u_d = comp.u
    u_max_tip = max(u_t, u_d)
    rho = DB[mat].density
    sigma = rho * u_max_tip ** 2
    diag.update({"u_tip_turbo_mps": u_t, "u_tip_drag_mps": u_d, "hoop_stress_Pa": sigma,
                 "module_rotor_ok_uncited_db_yield": None,
                 "hub_ratio": float(design.get("hub_ratio", 0.0)),
                 "hub_geometry_status": design.get("hub_geometry_status", HUB_ZERO_BOUND)})
    basis_id = _basis_id(design, coefficient_evidence)
    registered = rs.get_registered(basis_id) is not None
    extra = design.get("material_extra_basis") or (coefficient_evidence or {}).get("material_extra_basis")
    admission = material_admission(mat, extra)
    diag["material_admission"] = admission["status"]
    if registered and admission.get("missing_extra"):
        # A9.13 S6.9: a registered strength basis alone does not re-admit Al / CFRP (AO / laminate records missing)
        reasons.append(R_READMISSION_RECORDS)
        diag["stress_case"] = ST_NOT_EVALUATED_MATERIAL_BASIS
    elif registered:
        diag["stress_case"] = STRESS_CASE_REGISTERED          # qualify_rotor evaluated after the run (needs T_rotor)
    elif mat not in CITED_ALLOWABLES_PA:
        reasons.append(R_ALLOWABLE_TBD)
        diag["stress_margin"] = None
        diag["stress_case"] = ST_NOT_EVALUATED_MATERIAL_BASIS
    else:
        allow = CITED_ALLOWABLES_PA[mat]
        margin = allow / (comp.stress_safety * sigma) - 1.0
        diag.update({"allowable_Pa": allow, "safety_factor": comp.stress_safety, "stress_margin": margin,
                     "u_allow_with_sf_mps": math.sqrt(allow / (comp.stress_safety * rho)),
                     "stress_case": STRESS_CASE_LEGACY, "stress_case_label": rs.LEGACY_SENSITIVITY_LABEL})
        if not margin >= 0.0:                # fail closed: a NaN margin is never a pass (SW-02)
            reasons.append(R_STRESS)
    if u_t > U_TIP_PUBLISHED_MAX_MPS * (1.0 + 1e-12):
        reasons.append(R_TIP_DOMAIN)
    if inlet.p_total_Pa > P_MOLECULAR_LIMIT_PA:
        reasons.append(R_INLET_DOMAIN)

    # --- self-consistent run, then independent convergence re-check (run() reports no convergence)
    r = None
    try:
        r = comp.run(inlet.p_total_Pa, md, self_consistent=True)
        through = {s: md[s] + r["recirculated_kgps"][s] for s in SPECIES}
        again = comp._run_once(inlet.p_total_Pa, through)
        resid = max(abs(max(again["leak_kgps"][s], 0.0) - r["recirculated_kgps"][s]) / max(md[s], 1e-15)
                    for s in SPECIES)
        trace = stage_trace(comp, inlet.p_total_Pa, through)
        finite = _finite(r["p_out_Pa"], r["P_el_W"], r["mass_kg"], r["T_comp_K"], resid, trace["p_out_Pa"])
    except (OverflowError, ZeroDivisionError, ValueError) as exc:
        reasons.append(R_MODEL)
        diag["exception"] = f"{type(exc).__name__}: {exc}"
        finite = False
    if r is not None and not finite and R_MODEL not in reasons:
        reasons.append(R_MODEL)
    if R_MODEL not in reasons:
        diag["recirculation_residual"] = resid
        diag["module_rotor_ok_uncited_db_yield"] = bool(r["rotor_ok"])
        if resid > RECIRC_RTOL:
            reasons.append(R_NONCONV)
        if abs(trace["p_out_Pa"] / again["p_out_Pa"] - 1.0) > MIRROR_RTOL:
            reasons.append(R_MODEL)
            diag["exception"] = "stage_trace mirror does not reproduce DragCompressor._run_once p_out"
        else:
            k_min = min(min(st["K_unclipped"].values()) for st in trace["stages"]) if trace["stages"] else None
            diag["K_unclipped_min"] = k_min
            if k_min is not None and k_min < 1.0:
                reasons.append(R_CLIP)
            p_stage_max = max([inlet.p_total_Pa] + [st["p_out_Pa"] for st in trace["stages"]])
            diag["p_stage_max_Pa"] = p_stage_max
            if p_stage_max > P_MOLECULAR_LIMIT_PA:
                reasons.append(R_DOMAIN_P)
            drag = [st for st in trace["stages"] if st["kind"] == "drag"]
            if drag:
                kn = min(drag_knudsen_upper(st["p_species_out_Pa"], comp.T_gas_K, comp.h_mm * 1e-3) for st in drag)
                diag["drag_Kn_min_upper_bound_O_omitted"] = kn
                if kn < KN_FREE_MOLECULAR_MIN:
                    reasons.append(R_DOMAIN_KN)
            else:
                diag["drag_Kn_min_upper_bound_O_omitted"] = None
            t_lim = DB[mat].T_max_K
            diag["T_comp_K"] = r["T_comp_K"]
            if r["T_comp_K"] > t_lim:
                reasons.append(R_THERMAL)

    # --- rotor qualification through the registered-basis gate (both modes; never PASS on the legacy case)
    T_rotor = diag.get("T_comp_K", float("nan"))
    rq = rs.qualify_rotor(basis_id, mat, u_max_tip, comp.rpm, T_rotor, design.get("rotor_stock_thickness_m"))
    diag["rotor_qualification"] = {k: rq[k] for k in ("rotor_qualification", "rotor_ok", "rotor_strength_basis_id",
                                                      "rotor_qualification_reasons", "margin_yield",
                                                      "margin_ultimate")}
    if registered and R_READMISSION_RECORDS in reasons:
        rq = dict(rq, rotor_qualification=ST_NOT_EVALUATED_MATERIAL_BASIS, rotor_ok=False)
        diag["rotor_qualification"].update(rotor_qualification=ST_NOT_EVALUATED_MATERIAL_BASIS, rotor_ok=False)
    elif registered:
        if rq["rotor_qualification"] == rs.Q_FAIL:
            reasons.append(R_ROTOR_QUAL_FAIL)
        elif rq["rotor_qualification"] != rs.Q_PASS:
            reasons.append(R_ROTOR_QUAL_OOD)

    rec = {"id": design.get("id"), "design": {k: design[k] for k in design if k != "id"}, "reasons": reasons,
           "diagnostics": diag, "outputs": None,
           "rotor_structural_acceptance": rq["rotor_qualification"],
           "architecture_point_status": ST_NOT_EVALUATED_OOD if any(x in DOMAIN_REASONS for x in reasons)
           else u13.DOMAIN_IN}
    if mode == MODE_STRICT and not registered:            # defensive: strict_blockers already refuses this
        rec["status"] = ST_NOT_EVALUATED_MATERIAL_BASIS
        return rec
    if reasons:
        # A9.13 S6.8: above the 0.1 Pa domain nothing is evaluated; an inlet-independent rejection (rotor / tip /
        # allowable) still rejects the design point regardless of the inlet state
        if any(x in INLET_INDEPENDENT_REASONS for x in reasons):
            rec["status"] = ST_REJECTED
        elif any(x in DOMAIN_REASONS for x in reasons):
            rec["status"] = ST_NOT_EVALUATED_OOD
        elif R_ROTOR_QUAL_OOD in reasons or R_READMISSION_RECORDS in reasons:
            # registered basis present but the rotor is outside it (temperature, stock section, material): not
            # evaluated, never accepted (A9.9 S2.3)
            rec["status"] = ST_NOT_EVALUATED_MATERIAL_BASIS
        else:
            rec["status"] = ST_REJECTED
        return rec
    rec["status"] = ST_FEASIBLE_STRICT if mode == MODE_STRICT else ST_FEASIBLE
    delivered = {s: float(r["delivered_kgps"][s]) for s in SPECIES}
    dtot = sum(delivered.values())
    nflow = {s: delivered[s] / M_SPECIES[s] for s in SPECIES}
    ntot = sum(nflow.values())
    rec["outputs"] = {
        "P_out_Pa": r["p_out_Pa"], "CR_total": r["CR_active"], "CR_by_species": {s: r["CR_by_species"][s] for s in SPECIES},
        "mdot_delivered_kgps": delivered, "mdot_delivered_total_kgps": dtot,
        "x_s_out_partial_pressure": {s: r["composition_out"][s] for s in SPECIES},
        "x_s_delivered_flow_mole": {s: nflow[s] / ntot for s in SPECIES},
        "P_compressor_el_W": r["P_el_W"], "P_shaft_W": r["P_gas_W"] + r["P_bear_W"], "P_gas_drag_W": r["P_gas_W"],
        "P_bearing_W": r["P_bear_W"], "eta_motor": comp.eta_motor, "P_ctrl_W": comp.P_ctrl_W,
        "m_compressor_kg": r["mass_kg"], "T_compressor_K": r["T_comp_K"], "T_gas_K": comp.T_gas_K,
        "S_turbo_m3_s": r["S_turbo_m3_s"], "S0_drag_m3_s": r["S0_drag_m3_s"],
        "recirculation_frac": r["recirculation_frac"],
        "mass_allocation_margin_kg": OWNER_MASS_ALLOCATION_KG - r["mass_kg"],
        "rotor_structural_acceptance": rq["rotor_qualification"],
        "hub_ratio": float(design.get("hub_ratio", 0.0)),
        "blade_span_m": comp.turbo_radius_m * (1.0 - float(design.get("hub_ratio", 0.0))),
    }
    return rec


# ------------------------------------------------------------------------------------------------------- Pareto
PRIMARY_OBJECTIVES = (("P_out_Pa", "max"), ("mdot_delivered_total_kgps", "max"), ("P_compressor_el_W", "min"),
                      ("m_compressor_kg", "min"))
SECONDARY_OBJECTIVES = PRIMARY_OBJECTIVES + (("S_turbo_m3_s", "max"),)


def _dominates(a: Mapping, b: Mapping, objectives) -> bool:
    better = False
    for k, sense in objectives:
        x, y = (a[k], b[k]) if sense == "max" else (-a[k], -b[k])
        if x < y:
            return False
        if x > y:
            better = True
    return better


def pareto_front(records: list[dict], objectives=PRIMARY_OBJECTIVES) -> list[str]:
    """Ids of the non-dominated feasible records (weak Pareto dominance; ties are all kept). Deterministic order."""
    # OPT-04: records with a non-finite objective never enter dominance (fail closed)
    feas = sorted((r for r in records if r.get("outputs") and
                   all(_finite(r["outputs"].get(k)) for k, _ in objectives)), key=lambda r: r["id"])
    out = []
    for a in feas:
        if not any(_dominates(b["outputs"], a["outputs"], objectives) for b in feas if b is not a):
            out.append(a["id"])
    return out


def is_dominated_by(rec_outputs: Mapping, front_records: list[dict], objectives=PRIMARY_OBJECTIVES) -> bool:
    return any(_dominates(f["outputs"], rec_outputs, objectives) for f in front_records)


def synthesize(inlet: InletRecord, mode: str = MODE_PARAMETRIC, grid: SearchGrid | None = None,
               coefficient_evidence: Mapping[str, dict] | None = None) -> dict:
    """Bounded design search for one inlet record. MODE_STRICT refuses (NOT_EVALUATED) while blockers remain."""
    if mode not in MODES:
        raise SynthesisInputError(f"mode must be one of {MODES}")
    if mode == MODE_STRICT:
        blk = strict_blockers(inlet, coefficient_evidence)
        if blk:
            return {"inlet": inlet.record_id, "mode": mode, "status": _not_evaluated_status(blk), "blockers": blk,
                    "designs": [], "feasible_ids": [], "pareto_ids": [], "pareto_with_S_ids": [],
                    "domain": u13.classify_pressure_target(inlet.p_total_Pa)}
    elif inlet.label != LABEL_PARAMETRIC and inlet.evidence_class == "assumed":
        raise SynthesisInputError("an assumed inlet record must be labelled PARAMETRIC_SENSITIVITY")
    g = grid or SearchGrid()
    recs = [evaluate_design(d, inlet, mode, coefficient_evidence) for d in g.designs()]
    feas = [r["id"] for r in recs if r["outputs"]]
    # A9.13 S6.7: zero-hub points are the analytical bound only; the Pareto front is formed over hub > 0 points
    # (the bound front is reported separately)
    hub = [r for r in recs if r["design"].get("hub_geometry_status", HUB_ZERO_BOUND) != HUB_ZERO_BOUND]
    bound = [r for r in recs if r["design"].get("hub_geometry_status", HUB_ZERO_BOUND) == HUB_ZERO_BOUND]
    return {"inlet": inlet.record_id, "mode": mode,
            "label": LABEL_PARAMETRIC if mode == MODE_PARAMETRIC else LABEL_INTERFACE,
            "status": "EVALUATED", "designs": recs, "feasible_ids": feas,
            "pareto_ids": pareto_front(hub, PRIMARY_OBJECTIVES),
            "pareto_with_S_ids": pareto_front(hub, SECONDARY_OBJECTIVES),
            "zero_hub_bound_pareto_ids": pareto_front(bound, PRIMARY_OBJECTIVES),
            "status_counts": {st: sum(1 for r in recs if r["status"] == st) for st in sorted({r["status"] for r in recs})},
            "domain": u13.classify_pressure_target(inlet.p_total_Pa),
            "transitional_model": dict(u13.TRANSITIONAL_MODEL)}


# ------------------------------------------------------------------------------------- size_for consistency check
def size_for_comparison(inlet: InletRecord, cr_target: float, a_turbo_m2: float, front_records: list[dict],
                        material: str = "Ti6Al4V", mode: str = MODE_PARAMETRIC) -> dict:
    """What DragCompressor.size_for() returns for the same inlet (module defaults, same A_turbo / R_turbo / material /
    T_gas), passed through this module's gates and compared with the synthesis front. A consistency check, not a
    replacement: size_for is not modified and is still what the goldens use."""
    r_t = r_turbo_from_area(a_turbo_m2)
    kw = module_defaults()
    kw.update({"turbo_area_m2": a_turbo_m2, "turbo_radius_m": r_t, "rotor_material": material, "T_gas_K": inlet.T_K})
    comp = DragCompressor(**kw)
    md = {s: float(inlet.mdot_kgps[s]) for s in SPECIES}
    try:
        res = comp.size_for(inlet.p_total_Pa, md, CR_target=cr_target)
    except (OverflowError, ZeroDivisionError, ValueError) as exc:
        return {"a_turbo_m2": a_turbo_m2, "material": material, "cr_target": cr_target,
                "size_for": {"exception": f"{type(exc).__name__}: {exc}"}, "gate_status": ST_REJECTED,
                "gate_reasons": [R_MODEL], "on_front": False, "dominated_by_front": None}
    design = {"id": "size_for", "N_turbo": int(res["turbo_rows"]), "A_turbo_m2": a_turbo_m2, "R_turbo_m": r_t,
              "u_tip_turbo_mps": r_t * float(res["rpm"]) * 2 * math.pi / 60.0, "rpm": float(res["rpm"]),
              "N_drag": int(res["n_stages"]), "rotor_material": material}
    ev = evaluate_design(design, inlet, mode)
    out = {"a_turbo_m2": a_turbo_m2, "material": material, "cr_target": cr_target,
           "size_for": {"sized": bool(res["sized"]), "turbo_rows": int(res["turbo_rows"]), "n_stages": int(res["n_stages"]),
                        "rpm": float(res["rpm"]), "p_out_Pa": res["p_out_Pa"], "CR_active": res["CR_active"],
                        "P_el_W": res["P_el_W"], "mass_kg": res["mass_kg"], "rotor_ok_uncited_db_yield": bool(res["rotor_ok"]),
                        "objective": "mass + 0.02 x P_el (size_for's hard-coded scalar)"},
           "gate_status": ev["status"], "gate_reasons": ev["reasons"]}
    if ev["outputs"]:
        out["on_front"] = not is_dominated_by(ev["outputs"], front_records)
        out["dominated_by_front"] = not out["on_front"]
    else:
        out["on_front"] = False
        out["dominated_by_front"] = None
    return out
