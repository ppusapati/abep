#!/usr/bin/env python3
"""DI-1.4 compressor down-selection v1 (follow-on fo_compressor_downselect; trigger T_PIVOT_COMPRESSOR_DOWNSELECT;
owner disposition od_hardware_pivot, addendum A3 `DI_1_4_compressor_downselect`).

What it is: a survey of open published compressor concepts for ABEP intake gas at 180-230 km, the requirement envelope
the W1 feed-state closure places on the compressor (pumping speed, compression ratio incl. atomic O, pneumatic power, AO
exposure, power headroom) evaluated at the nine frozen atmospheric cases with the repository chain used READ-ONLY, a
down-selection matrix with explicit hard gates, PROPOSED candidate(s) and the minimum data/test needed to freeze DI-1.4.

What it is not: a compressor design, a flight value, an architecture ranking or a model change. The compressor is
COMMON-MODE across hall_only / rf_hall / ecr_hall (same feed state, same compressor), so nothing here favours an
architecture. No abep_sim module is modified or wired; no frozen dataset is rebuilt; no Hall transport closure,
ensemble member, screening candidate or P5 calibration-nuisance variable enters any value. The 0.030-3.14 mg/s valve
flow bracket stays a candidate range (owner addendum A3), not a flight truth.

Inputs (read-only, sha256-pinned in the output):
  docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json  (W1 closure: candidates, valve states,
      self-consistent backflow, design-input documents)
  scripts/architecture/build_feed_envelope.py  (lane 16: frozen_state, field lists; loaded by path)
  abep_sim.intake.collection / compress, abep_sim.compressor.DragCompressor, abep_sim.constants  (called, never changed)
Literature values are hard-coded below with reference, location, access level and evidence class; each was read in
the accessed document on 2026-09-27 (or is labelled secondary / search-snippet / verify).

Deterministic, no Julia, a few seconds single-threaded.

Usage:
  python docs/architecture_comparison/compressor_downselect/build_compressor_downselect.py          # (re)write outputs
  python docs/architecture_comparison/compressor_downselect/build_compressor_downselect.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT_DIR_REL = "docs/architecture_comparison/compressor_downselect"
SCRIPT_REL = f"{OUT_DIR_REL}/build_compressor_downselect.py"
JSON_NAME = "compressor_downselect_v1.json"
MD_NAME = "COMPRESSOR_DOWNSELECT.md"
CLOSURE_REL = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
LANE16_REL = "scripts/architecture/build_feed_envelope.py"
SCHEMA_ID = "compressor_downselect_v1"
VERSION = "1.0.0"
BASE_COMMIT = "7d373374dcd47eb6c2464423eb5f45a1fa14ef78"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
ALTITUDES_KM = (180.0, 200.0, 230.0)
LEVELS = ("low", "mean", "high")
AIR = ("O", "N2", "O2")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
ACCESS_LEVELS = ("full_text", "abstract_only", "secondary_citation", "search_engine_excerpt")
GATE_RESULTS = ("PASS", "FAIL", "FAIL_AT_PUBLISHED_POINT", "CONDITIONAL", "NOT_EVALUABLE", "OUT_OF_SCOPE")
VALUE_STATUS = "PROPOSED (candidate-conditional)"
DERIVED_EVIDENCE = "model-derived (from assumed design inputs and cited model forms)"

# Owner decision files: immutable, consumers pin them by sha256 (lane registry od_hardware_pivot.immutability).
DECISION_PINS = {
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json":
        "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A1_controls.json":
        "04c5a6f46ed2cb3e3fb174bcc7305d129e15ef53af2349d2a8abc4f6d8975992",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json":
        "f82fb78cc0f608c03fd37d9ecbede6aab4ec525eecf5f8a47619eca35e1e73b6",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json":
        "10d79026f1a65e0c2a9fa9e1f9a5f9abc9d162692711857bd43575f3095c8d4e",
}
READ_ONLY_INPUTS = (CLOSURE_REL, LANE16_REL, "abep_sim/compressor.py", "abep_sim/intake.py", "abep_sim/intake_tpmc.py",
                    "abep_sim/constants.py", "abep_sim/materials.py", "abep_sim/atmosphere.py",
                    "abep_sim/data/atmosphere_msis21_v1.csv", "abep_sim/data/atmosphere_msis21_v1.json",
                    "abep_sim/data/intake_surface_v1.csv", "abep_sim/data/intake_surface_v1.json")

# ------------------------------------------------------------------------------------------ PROPOSED analysis levels
# Values not in the RFP are PROPOSED for owner review; each is a screening level, not a requirement.
PROPOSED = {
    "backflow_targets_b": {
        "value": [0.5, 0.25, 0.1], "unit": "-",
        "meaning": "plenum backflow fraction b = p_plenum / p_passive (W1 finding FC-01 model); delivered flow ~ (1 - b) "
                   "x forward flow. 0.5 ~ the W1 SC-BACKFLOW level, 0.25 and 0.1 = PROPOSED design targets"},
    "u_ref_mps": {
        "value": 500.0, "unit": "m/s",
        "meaning": "reference rotor circumferential speed for the pumping-speed area bound; the published order of "
                   "commercial TMP rotors (EV-04), not a Vyovrinda design value"},
    "compressor_power_allocation_frac": {
        "value": 0.2, "unit": "- (of RFP P_bus 1.5 kW)",
        "meaning": "PROPOSED screening allocation for the compressor load (300 W); the owner sets the real allocation "
                   "(OD-C2); the RFP-derived necessary condition HG-1 does not depend on it"},
    "rotor_erosion_allowance_m": {
        "value": 1.0e-4, "unit": "m",
        "meaning": "PROPOSED allowable AO recession of an unprotected wetted rotor surface over the mission (0.1 mm); "
                   "used only to express the ram-yield bound as a required yield reduction factor"},
    "sccm_reference": {"value": [273.15, 101325.0], "unit": "K, Pa",
                       "meaning": "standard conditions for the sccm conversion (same as W1)"},
}
THRUST_FOR_POWER_GATE_ATTR = "thrust_min_mN"      # RFP minimum thrust (12 mN) for the jet-power lower bound

# ------------------------------------------------------------------------------------------------------ references
REFERENCES = {
    "REF-CHIGGIATO2013": {
        "citation": "P. Chiggiato, 'Vacuum Technology for Ion Sources', CERN Accelerator School: Ion Sources, "
                    "CERN-2013-007 (2013); arXiv:1404.0960",
        "doi_or_url": "https://arxiv.org/pdf/1404.0960", "access_level": "full_text", "accessed": "2026-09-27",
        "note": "tutorial review; figures of commercial pumps are courtesy of a supplier (supplier data not accessed)"},
    "REF-SINGH2014": {
        "citation": "L. A. Singh, 'Very Low Earth Orbit Propellant Collection Feasibility Assessment', PhD thesis, "
                    "Georgia Institute of Technology (2014)",
        "doi_or_url": "https://hpepl.ae.gatech.edu/papers/Singh.pdf", "access_level": "full_text",
        "accessed": "2026-09-27", "note": "page numbers are PDF page indices"},
    "REF-SINGH2015": {
        "citation": "L. A. Singh, M. L. R. Walker, 'A review of research in low earth orbit propellant collection', "
                    "Progress in Aerospace Sciences 75 (2015) 15-25",
        "doi_or_url": "doi:10.1016/j.paerosci.2015.03.001 (author copy "
                      "https://hpepl.ae.gatech.edu/papers/ProgAerospace_Singh_V75_2015_pp15-25.pdf)",
        "access_level": "full_text", "accessed": "2026-09-27", "note": "page numbers are PDF page indices"},
    "REF-MOON2025": {
        "citation": "G. Moon, Y. Ko, M. Yi, E. Jun, 'Operational Feasibility Analysis of a Cryogenic Active Intake "
                    "Device for Atmosphere-Breathing Electric Propulsion', arXiv:2503.02021v1 (2025)",
        "doi_or_url": "https://arxiv.org/html/2503.02021v1", "access_level": "full_text", "accessed": "2026-09-27",
        "note": "preprint; the CRAID design paper it builds on is G. Moon, M. Yi, E. Jun, Aerosp. Sci. Technol. 151 "
                "(2024) 109300, doi:10.1016/j.ast.2024.109300 (publisher page not accessed; closed access)"},
    "REF-LI2015": {
        "citation": "Y. Li, X. Chen, D. Li, Y. Xiao, P. Dai, C. Gong, 'Design and analysis of vacuum air-intake device "
                    "used in air-breathing electric propulsion', Vacuum 120 (2015) 89-95",
        "doi_or_url": "doi:10.1016/j.vacuum.2015.06.011 (DOI from Crossref metadata)",
        "access_level": "secondary_citation", "accessed": "2026-09-27",
        "note": "not read: publisher page returned HTTP 403 (not bypassed); values only as cited by REF-MOON2025 "
                "Sec. 1 [26]; verify"},
    "REF-ZHENG2021": {
        "citation": "P. Zheng, J. Wu, Y. Zhang, Y. Zhao, 'Design and Optimization of vacuum Intake for "
                    "Atmosphere-Breathing electric propulsion (ABEP) system', Vacuum 195 (2021) 110652",
        "doi_or_url": "doi:10.1016/j.vacuum.2021.110652 (DOI from Crossref metadata)",
        "access_level": "search_engine_excerpt", "accessed": "2026-09-27",
        "note": "not read: publisher page returned HTTP 403 (not bypassed); values from a web-search excerpt of the "
                "abstract only; verify before any use"},
    "REF-FERRATO2022": {
        "citation": "E. Ferrato, V. Giannetti, M. Tisaev, A. Lucca Fabris, F. Califano, T. Andreussi, 'Rarefied Flow "
                    "Simulation of Conical Intake and Plasma Thruster for Very Low Earth Orbit Spaceflight', "
                    "Frontiers in Physics 10 (2022) 823098",
        "doi_or_url": "doi:10.3389/fphy.2022.823098", "access_level": "full_text", "accessed": "2026-09-27",
        "note": "open access; page numbers are PDF page indices"},
    "REF-GAIER1996": {
        "citation": "J. R. Gaier, M. L. Davidson, R. Shively, 'Durability of Intercalated Graphite Epoxy Composites in "
                    "Low Earth Orbit', NASA TM-107157 (1996)",
        "doi_or_url": "https://ntrs.nasa.gov/api/citations/19960020439/downloads/19960020439.pdf",
        "access_level": "full_text", "accessed": "2026-09-27", "note": "page numbers are PDF page indices"},
    "REF-NASA-HDBK-6024": {
        "citation": "NASA-HDBK-6024 w/Change 2, 'Spacecraft Polymers Atomic Oxygen Durability Handbook' "
                    "(revalidated 2022-12-16)",
        "doi_or_url": "https://standards.nasa.gov/sites/default/files/standards/NASA/Baseline-w/CHANGE-2/2/"
                      "2022-12-16-NASA-HDBK-6024_w-Chg-2_Reval-Final.pdf",
        "access_level": "full_text", "accessed": "2026-09-27", "note": "page numbers as printed ('N of 207')"},
    "REF-CUSHEN2024": {
        "citation": "A. T. Cushen et al., 'Performance Test Methodology for Atmosphere-Breathing Electric Propulsion "
                    "Intakes in an Atomic Oxygen Facility', arXiv:2406.06299 (2024)",
        "doi_or_url": "https://arxiv.org/abs/2406.06299", "access_level": "abstract_only", "accessed": "2026-09-27",
        "note": "abstract only"},
}

# --------------------------------------------------------------------------------------------- evidence register
# Every literature statement used below. 'value' is exactly what the source states (units as stated); evidence_class
# says how the SOURCE obtained it (per docs/EVIDENCE.md); verify=True where the text was not read first-hand.
EVIDENCE = (
    {"id": "EV-01", "ref": "REF-CHIGGIATO2013", "where": "Sec. 4.1.1, Eq. (46), PDF p. 21",
     "statement": "molecular (drag) pump pumping speed S = Q_p / P = (1/2) u b h: proportional to the moving-wall speed "
                  "u and the channel cross-section b h, independent of the gas species",
     "value": {"form": "S = u*b*h/2"}, "evidence_class": "model-derived", "verify": False,
     "used_for": "pumping-speed area bound (HG-5) and the DragCompressor S0 form (same form with xi)"},
    {"id": "EV-02", "ref": "REF-CHIGGIATO2013", "where": "Sec. 4.1.1, Eq. (47), PDF p. 21",
     "statement": "zero-flow compression ratio K0 = exp(u b h L / c) ~ exp(u L / (<v> h)) ~ exp(u sqrt(m) L / h): high "
                  "K0 needs u of the order of the mean molecular speed and long narrow ducts; K0 depends strongly on "
                  "molecular mass",
     "value": {"form": "ln K0 proportional to sqrt(m)"}, "evidence_class": "model-derived", "verify": False,
     "used_for": "species scaling of a published compression ratio to atomic O (HG-4); DragCompressor ln K0 form"},
    {"id": "EV-03", "ref": "REF-CHIGGIATO2013", "where": "Sec. 4.1.2, PDF p. 23",
     "statement": "a TMP works at full pumping speed only in the molecular regime (P < 1e-3 mbar); its pumping speed "
                  "is 10-3000 l/s depending on inlet diameter and design; maximum compression ratio lowest for H2, "
                  "about 1e3 in classical designs; up to 1e6 by adding a Gaede/Holweck drag stage behind the blades",
     "value": {"molecular_regime_limit_mbar": 1e-3, "pumping_speed_l_s": [10, 3000], "K0_H2_classical": 1e3,
               "K0_H2_with_drag_stage": 1e6},
     "evidence_class": "inferred", "verify": False,
     "used_for": "published pumping-speed range (HG-5); applicability of the free-molecular DragCompressor at the "
                 "compressor outlet (setpoints 0.05-1 Pa vs the 0.1 Pa molecular-regime limit)"},
    {"id": "EV-04", "ref": "REF-CHIGGIATO2013", "where": "Sec. 4.1.2, PDF p. 24",
     "statement": "rotor blade sets machined from high-strength aluminium alloys; DN100 pumps rotate at ~1 kHz with "
                  "circumferential speeds up to 500 m/s; lubricated bearings removed by magnetic suspension; on "
                  "unwanted rotor deceleration the system must be protected by valves against back-streaming",
     "value": {"u_circumferential_max_mps": 500.0, "rotation_Hz": 1000.0}, "evidence_class": "inferred",
     "verify": False,
     "used_for": "reference rotor speed u_ref (area bound), rotor material class, stopped-rotor backflow (HG-5b)"},
    {"id": "EV-05", "ref": "REF-SINGH2014", "where": "Sec. 3.2.4, PDF p. 98 (printed pp. 78-79)",
     "statement": "the most likely analog for a propellant-collection compressor is the turbomolecular pump; "
                  "Hablanian (J. Vac. Sci. Technol. A 11, 1993) estimates TMP thermodynamic efficiency to be 'only a "
                  "few percent'; compressor efficiency is taken to vary between one and ten percent",
     "value": {"eta_thermodynamic_range": [0.01, 0.10]}, "evidence_class": "assumed", "verify": True,
     "used_for": "pneumatic power band P = Q ln(CR) / eta (HG-1); the primary Hablanian 1993 source was not "
                 "accessed (verify)"},
    {"id": "EV-06", "ref": "REF-SINGH2014", "where": "Sec. 2 (Reichel analysis), PDF p. 49 (printed p. 30)",
     "statement": "collected air must be compressed above the triple point of nitrogen for liquefaction, "
                  "approximately 94 Torr",
     "value": {"p_triple_N2_Torr": 94.0}, "evidence_class": "inferred", "verify": False,
     "used_for": "compression ratio a liquefaction/storage concept needs (C5)"},
    {"id": "EV-07", "ref": "REF-SINGH2015", "where": "Sec. 5, PDF p. 10",
     "statement": "compression and storage is the least addressed subsystem in the literature; an integrated "
                  "compression and liquefaction system that operates in space, survives launch and provides the "
                  "necessary compression remains to be demonstrated",
     "value": {}, "evidence_class": "inferred", "verify": False,
     "used_for": "demonstration status of storage-based concepts (C4, C5); maturity of all active concepts"},
    {"id": "EV-08", "ref": "REF-LI2015", "where": "as cited in REF-MOON2025 Sec. 1 (ref. [26])",
     "statement": "active intake with a multi-hole plate and a turbomolecular pump; numerical simulations and "
                  "subsystem experiments estimated a capture efficiency of approximately 60 % and a compression ratio "
                  "of 3500 or higher",
     "value": {"capture_efficiency": 0.60, "compression_ratio_min": 3500.0}, "evidence_class": "inferred",
     "verify": True,
     "used_for": "published compression-ratio capability of a throat-spanning TMP concept (C1, HG-4); species, inlet "
                 "pressure, throughput, power and mass not stated in the accessed text"},
    {"id": "EV-09", "ref": "REF-ZHENG2021", "where": "abstract (web-search excerpt only)",
     "statement": "active intake of a multi-hole plate, cylinder chamber and turbomolecular pump analysed "
                  "experimentally; an optimized scheme reaches a compression ratio of 210.2 and a capture efficiency "
                  "of 65.79 %",
     "value": {"compression_ratio": 210.2, "capture_efficiency": 0.6579}, "evidence_class": "inferred",
     "verify": True,
     "used_for": "second published compression-ratio point of a TMP concept (C1, HG-4); species and conditions not "
                 "available in the accessed excerpt"},
    {"id": "EV-10", "ref": "REF-MOON2025", "where": "Sec. 4.3.2",
     "statement": "an RTB cryocooler with a power consumption of 1.2 kW would be required to provide 14 W of cooling "
                  "during the condensation sequence",
     "value": {"P_cryocooler_W": 1200.0, "Q_cool_W": 14.0}, "evidence_class": "model-derived", "verify": False,
     "used_for": "power gate of the cryocondensation concept (C4, HG-1b)"},
    {"id": "EV-11", "ref": "REF-MOON2025", "where": "Sec. 4.6.1",
     "statement": "effective capture efficiency 26.1 % and effective compression ratio 3.0e7 for the conceptual "
                  "prototype model",
     "value": {"capture_efficiency_eff": 0.261, "compression_ratio_eff": 3.0e7}, "evidence_class": "model-derived",
     "verify": False, "used_for": "C4 compression capability (HG-4)"},
    {"id": "EV-12", "ref": "REF-MOON2025", "where": "Sec. 4.3.1",
     "statement": "free-stream conditions simplified by assuming complete recombination of AO atoms",
     "value": {}, "evidence_class": "assumed", "verify": False,
     "used_for": "C4 atomic-O treatment is an assumption of the source, not a demonstrated behaviour (HG-3)"},
    {"id": "EV-13", "ref": "REF-MOON2025", "where": "Sec. 2 and Sec. 4.4.2",
     "statement": "cryopanel raised to 54.5 K for regeneration (below the N2 and O2 triple points); practical "
                  "regeneration time 31.7 min assuming 20 sccm for two RITs",
     "value": {"T_regeneration_K": 54.5, "t_regen_min": 31.7, "flow_sccm_two_thrusters": 20.0},
     "evidence_class": "model-derived", "verify": False,
     "used_for": "C4 is a batch (condense/regenerate) process: T_feed and duty cycle need a storage model"},
    {"id": "EV-14", "ref": "REF-FERRATO2022", "where": "Sec. 4.1 / Fig. 9F, PDF p. 12; Sec. 3, PDF p. 10",
     "statement": "optimal passive intake designs give transmission about 0.4 to 0.1 and compression 180 to 240; "
                  "compression ratios in the 100 to 300 range seem attainable",
     "value": {"transmission_range": [0.1, 0.4], "compression_range": [180.0, 240.0]},
     "evidence_class": "model-derived", "verify": False,
     "used_for": "order-of-magnitude cross-check of the frozen TPMC CR_passive (C3); compression-ratio definitions may "
                 "differ (verify)"},
    {"id": "EV-15", "ref": "REF-FERRATO2022", "where": "Sec. 2, PDF p. 5",
     "statement": "in the double-staged concept the ionization stage increases flow compression by pumping and "
                  "channeling the ionized particles into the acceleration stage",
     "value": {}, "evidence_class": "inferred", "verify": False,
     "used_for": "plasma/electrostatic pumping concept (C7): compression inside the ionization stage"},
    {"id": "EV-16", "ref": "REF-GAIER1996", "where": "Results, PDF p. 7; summary, PDF p. 8",
     "statement": "graphite-epoxy composites flown on EOIM-3 (STS-46, 230 km, ram fluence ~2.6e20 atoms/cm2): matrix "
                  "erosion yield ~3.5e-24 cm3/atom, fiber ~0.85e-24 cm3/atom; SiO2-protected faces showed no "
                  "noticeable erosion",
     "value": {"Ey_matrix_cm3_per_atom": 3.5e-24, "Ey_fiber_cm3_per_atom": 0.85e-24, "fluence_atoms_cm2": 2.6e20},
     "evidence_class": "measured", "verify": False,
     "used_for": "ram-energy AO erosion reference for CFRP wetted surfaces (HG-3)"},
    {"id": "EV-17", "ref": "REF-NASA-HDBK-6024", "where": "Sec. 6.x, pp. 40-41 of 207",
     "statement": "thermal-energy atoms (~0.04 eV) require orders of magnitude more atoms to erode as much material as "
                  "LEO atoms arriving at ~4.5 eV",
     "value": {"E_thermal_eV": 0.04, "E_LEO_eV": 4.5}, "evidence_class": "inferred", "verify": False,
     "used_for": "the ram-yield erosion estimate for thermalised compressor gas is an upper bound (HG-3)"},
    {"id": "EV-18", "ref": "REF-NASA-HDBK-6024", "where": "Sec. 6.3, p. 37 of 207",
     "statement": "the most common protection of AO-susceptible materials is a thin protective film (SiO2, Al2O3, ITO, "
                  "Ge, Si, Al, Au; a few hundred angstroms to >100 nm)",
     "value": {}, "evidence_class": "inferred", "verify": False,
     "used_for": "coating mitigation path for non-metallic wetted parts (HG-3)"},
    {"id": "EV-19", "ref": "REF-CUSHEN2024", "where": "abstract",
     "statement": "ground test methods for sub-scaled ABEP intakes in an atomic-oxygen facility: pressure difference "
                  "between the intake extremities, and a gas sensor for collection efficiency, both checked by DSMC",
     "value": {}, "evidence_class": "inferred", "verify": True,
     "used_for": "precedent for an AO-flow ground test of the intake + compressor inlet (minimum test T-3)"},
)


class DownselectError(RuntimeError):
    pass


# -------------------------------------------------------------------------------------------------------- helpers
def sha256_file(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        raise DownselectError(f"required read-only input {rel} not found")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def case_id(alt: float, lvl: str) -> str:
    return f"alt{int(alt)}_{lvl}"


def _load_lane16():
    path = REPO / LANE16_REL
    if not path.exists():
        raise DownselectError(f"{LANE16_REL} (lane 16 feed envelope) is required and was not found")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("_lane16_build_feed_envelope_cd", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ev(eid: str) -> dict:
    for e in EVIDENCE:
        if e["id"] == eid:
            return e
    raise DownselectError(f"unknown evidence id {eid}")


def need(d: dict, key: str, where: str):
    """Explicit-input rule (CLAUDE.md rule 3): a missing input raises, never a default."""
    if key not in d or d[key] is None:
        raise DownselectError(f"missing required input {key!r} in {where}")
    return d[key]


def rnd(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            raise DownselectError("non-finite value in output")
        return float(f"{x:.10g}")
    if isinstance(x, dict):
        return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v) for v in x]
    return x


def rng(vals):
    v = [x for x in vals if x is not None]
    return {"min": min(v), "max": max(v)} if v else None


# --------------------------------------------------------------------------------------------- requirement envelope
def requirement_envelope(fe, closure: dict) -> dict:
    """Per closed W1 candidate and atmospheric case: what any compressor concept must do. The plenum state and forward
    flow are recomputed read-only with abep_sim.intake (collection, compress) from the W1 design-input documents and
    cross-checked against the W1 JSON; the chain-sized DragCompressor (code-default, assumed parameters) is re-run
    read-only for its species compression ratios."""
    from abep_sim.intake import IntakeParams, CompressorParams, collection, compress
    from abep_sim.compressor import DragCompressor
    from abep_sim.constants import K_B, M_SPECIES, RFP

    closed = [c for c, v in closure["closure"].items() if v["status"] == "CLOSED"]
    if not closed:
        raise DownselectError("W1 closure has no closed candidate")
    T_req_N = getattr(RFP, THRUST_FOR_POWER_GATE_ATTR) * 1e-3
    P_bus = RFP.power_max_W
    eta_lo, eta_hi = ev("EV-05")["value"]["eta_thermodynamic_range"]
    u_ref = PROPOSED["u_ref_mps"]["value"]
    S_pub_max = ev("EV-03")["value"]["pumping_speed_l_s"][1] * 1e-3
    Ey_ref = ev("EV-16")["value"]["Ey_matrix_cm3_per_atom"] * 1e-6          # m^3/atom (conservative: matrix)
    allow = PROPOSED["rotor_erosion_allowance_m"]["value"]
    t_fire_s = RFP.ignition_hours * 3600.0
    t_mission_s = RFP.mission_hours * 3600.0
    out = {}
    for cid in closed:
        doc = need(closure["design_input_documents"], cid, "W1 design_input_documents")
        dv = {k: v["value"] for k, v in doc["inputs"].items()}
        T_pl = float(need(dv, "plenum.T_gas_K", cid))
        rows = {}
        for a in ALTITUDES_KM:
            for l in LEVELS:
                cs = case_id(a, l)
                vo = need(closure["valve_outlet"][cid], cs, f"W1 valve_outlet {cid}")
                nom, sc = vo["nominal"], vo["backflow_self_consistent"]
                atm, _ = fe.frozen_state(a, l)
                ip = IntakeParams(area_m2=float(dv["intake.area_m2"]), accommodation=float(dv["intake.accommodation"]),
                                  off_axis_deg=float(dv["intake.off_axis_deg"]), scattering=dv["intake.scattering"],
                                  L_over_d=float(dv["intake.L_over_d"]), phi=float(dv["intake.phi"]), use_tpmc=True)
                col = collection(ip, atm)
                cmp_ = compress(CompressorParams(T_out_K=T_pl, backflow_frac=float(dv["plenum.backflow_frac"])),
                                atm, col["mdot_collected"], col["eta_c"], col["passive_override"])
                F = cmp_["mdot_net"]
                p_pass = cmp_["p_passive_Pa"]
                if abs(p_pass / sc["p_plenum_chain_Pa"] - 1.0) > 1e-8:
                    raise DownselectError(f"{cid} {cs}: recomputed plenum pressure does not reproduce W1")
                w = {"O": atm["fO"], "N2": atm["fN2"], "O2": atm["fO2"]}          # W1 chain_freestream_split
                wt = sum(w.values())
                w = {s: w[s] / wt for s in AIR}
                ndot = sum(F * w[s] / M_SPECIES[s] for s in AIR)             # molecules/s at the compressor inlet
                m_bar = F / ndot
                Q = ndot * K_B * T_pl                                         # Pa m^3/s
                setp = float(nom["setpoint_Pa"])
                CR_up = setp / p_pass
                CR_sc = sc["CR_required"]
                mdot_up, mdot_sc = nom["mdot_total_kgps"], sc["mdot_total_kgps"]
                # pumping speed the compressor inlet needs so that the plenum backflow is b (FC-01 model):
                # net pumped (1-b) F at p_plenum = b p_passive
                S_req = {str(b): (1.0 - b) * Q / (b * p_pass) for b in PROPOSED["backflow_targets_b"]["value"]}
                A_req = {k: v / (0.5 * u_ref) for k, v in S_req.items()}     # EV-01 ideal S/A = u/2 (lower bound)
                # pneumatic (isothermal) compression power band (EV-05), both flow ends
                def pn(mdot, CR):
                    n = mdot / m_bar
                    P0 = n * K_B * T_pl * math.log(max(CR, 1.0))
                    return {"ideal_W": P0, "eta_0p10_W": P0 / eta_hi, "eta_0p01_W": P0 / eta_lo}
                # RFP-derived necessary condition: jet power of 12 mN at the delivered flow (thruster efficiency <= 1)
                def jet(mdot):
                    return T_req_N ** 2 / (2.0 * mdot)
                P_jet_up, P_jet_sc = jet(mdot_up), jet(mdot_sc)
                # chain-sized nominal machine (code-default, assumed) re-run read-only for its species CRs
                kw = {f: (int(dv["compressor." + f]) if f in fe.COMP_INT_FIELDS else dv["compressor." + f])
                      for f in fe._dragcompressor_fields() if f not in fe.COMP_SIZED_FIELDS}
                rows_n, stages_n = nom["compressor_stages"]
                machine = DragCompressor(**kw, turbo_rows=int(rows_n), n_stages=int(stages_n),
                                         rpm=float(nom["compressor_rpm"]))
                r = machine.run(p_pass, {s: F * w[s] for s in AIR})
                crs = r["CR_by_species"]
                lnratio_O_N2 = math.log(crs["O"]) / math.log(crs["N2"]) if crs["N2"] > 1.0 else None
                # AO exposure of wetted rotor blades (code-default blade geometry, assumed)
                A_wet = int(rows_n) * float(dv["compressor.turbo_area_m2"]) * \
                    float(dv["compressor.turbo_blade_area_frac"]) * 2.0
                ndot_O = F * w["O"] / M_SPECIES["O"]
                depth_fire = Ey_ref * ndot_O * t_fire_s / A_wet
                depth_mission = Ey_ref * ndot_O * t_mission_s / A_wet
                rows[cs] = {
                    "altitude_km": a, "solar_level": l,
                    "forward_flow_to_compressor_kgps": F, "p_passive_Pa": p_pass, "T_plenum_K": T_pl,
                    "w_s_inlet": w, "m_mean_amu": m_bar / 1.66053906660e-27, "Q_Pa_m3_s": Q,
                    "setpoint_Pa": setp,
                    "CR_required": {"upper_bound_flow_basis": CR_up, "self_consistent_backflow": CR_sc},
                    "mdot_valve_kgps": {"upper_bound": mdot_up, "self_consistent_backflow": mdot_sc,
                                        "bracket_lower": vo["mdot_total_kgps_bracket"]["lower"],
                                        "bracket_upper": vo["mdot_total_kgps_bracket"]["upper"]},
                    "S_required_m3_s": S_req, "S_required_over_published_TMP_max": {
                        k: v / S_pub_max for k, v in S_req.items()},
                    "A_rotor_min_m2_at_u_ref": A_req,
                    "intake_area_m2": float(dv["intake.area_m2"]),
                    "P_pneumatic_W": {"upper_bound_flow": pn(mdot_up, CR_up),
                                      "self_consistent_backflow": pn(mdot_sc, CR_sc)},
                    "P_jet_min_W_at_12mN": {"upper_bound_flow": P_jet_up, "self_consistent_backflow": P_jet_sc},
                    "P_headroom_W_for_compressor_and_losses": {"upper_bound_flow": P_bus - P_jet_up,
                                                               "self_consistent_backflow": P_bus - P_jet_sc},
                    "chain_sized_machine": {
                        "turbo_rows": int(rows_n), "n_stages": int(stages_n), "rpm": float(nom["compressor_rpm"]),
                        "CR_by_species_at_forward_flow": dict(crs), "lnCR_O_over_lnCR_N2": lnratio_O_N2,
                        "P_el_W_nominal": nom["compressor_P_el_W"], "P_el_W_sc": sc["compressor_P_el_W"],
                        "T_comp_K": nom["compressor_T_comp_K"], "T_clamp_active": nom["compressor_T_clamp_active"],
                        "x_s_valve": nom["x_s"], "evidence_class": "model-derived (from assumed code-default inputs)"},
                    "AO": {"ndot_O_per_s": ndot_O, "A_wet_blades_m2": A_wet,
                           "ram_yield_recession_bound_m": {"firing_15000h": depth_fire, "mission_26000h": depth_mission},
                           "required_yield_reduction_for_allowance": depth_mission / allow},
                }
        out[cid] = {"status": VALUE_STATUS, "evidence_class": DERIVED_EVIDENCE, "cases": rows}
    return out


def envelope_summary(env: dict) -> dict:
    def collect(fn):
        return [fn(r) for c in env.values() for r in c["cases"].values()]
    b = [str(x) for x in PROPOSED["backflow_targets_b"]["value"]]
    return {
        "candidate_cases": sum(len(c["cases"]) for c in env.values()),
        "CR_required_self_consistent": rng(collect(lambda r: r["CR_required"]["self_consistent_backflow"])),
        "CR_required_upper_bound_flow": rng(collect(lambda r: r["CR_required"]["upper_bound_flow_basis"])),
        "p_passive_Pa": rng(collect(lambda r: r["p_passive_Pa"])),
        "setpoint_Pa": rng(collect(lambda r: r["setpoint_Pa"])),
        "mdot_valve_bracket_kgps": {"min": min(collect(lambda r: r["mdot_valve_kgps"]["bracket_lower"])),
                                    "max": max(collect(lambda r: r["mdot_valve_kgps"]["bracket_upper"]))},
        "S_required_m3_s": {k: rng(collect(lambda r, k=k: r["S_required_m3_s"][k])) for k in b},
        "S_required_over_published_TMP_max": {
            k: rng(collect(lambda r, k=k: r["S_required_over_published_TMP_max"][k])) for k in b},
        "A_rotor_min_m2_at_u_ref": {k: rng(collect(lambda r, k=k: r["A_rotor_min_m2_at_u_ref"][k])) for k in b},
        "P_pneumatic_eta_0p01_W": rng(collect(lambda r: max(r["P_pneumatic_W"]["upper_bound_flow"]["eta_0p01_W"],
                                                            r["P_pneumatic_W"]["self_consistent_backflow"]["eta_0p01_W"]))),
        "P_pneumatic_eta_0p10_W": rng(collect(lambda r: max(r["P_pneumatic_W"]["upper_bound_flow"]["eta_0p10_W"],
                                                            r["P_pneumatic_W"]["self_consistent_backflow"]["eta_0p10_W"]))),
        "P_jet_min_W_at_12mN": rng(collect(lambda r: r["P_jet_min_W_at_12mN"]["self_consistent_backflow"])
                                   + collect(lambda r: r["P_jet_min_W_at_12mN"]["upper_bound_flow"])),
        "cases_headroom_negative_self_consistent": sorted(
            f"{c}/{k}" for c, v in env.items() for k, r in v["cases"].items()
            if r["P_headroom_W_for_compressor_and_losses"]["self_consistent_backflow"] < 0.0),
        "cases_headroom_negative_upper_bound": sorted(
            f"{c}/{k}" for c, v in env.items() for k, r in v["cases"].items()
            if r["P_headroom_W_for_compressor_and_losses"]["upper_bound_flow"] < 0.0),
        "chain_machine_P_el_W": rng(collect(lambda r: r["chain_sized_machine"]["P_el_W_nominal"])),
        "chain_machine_lnCR_O_over_lnCR_N2": rng(collect(lambda r: r["chain_sized_machine"]["lnCR_O_over_lnCR_N2"])),
        "AO_ram_yield_recession_bound_mission_m": rng(collect(lambda r: r["AO"]["ram_yield_recession_bound_m"]["mission_26000h"])),
        "AO_required_yield_reduction": rng(collect(lambda r: r["AO"]["required_yield_reduction_for_allowance"])),
    }


# --------------------------------------------------------------------------------------------------------- concepts
def published_O_capability(K_published: float) -> float:
    """EV-02: ln K0 proportional to sqrt(m) at equal machine geometry, speed and temperature. ASSUMPTION (verify): the
    published compression ratio refers to N2 (the accessed texts do not state the species)."""
    from abep_sim.constants import M_SPECIES
    return math.exp(math.log(K_published) * math.sqrt(M_SPECIES["O"] / M_SPECIES["N2"]))


def drag_only_probe(fe, closure: dict, env: dict) -> dict:
    """C2: a Holweck/Gaede drag-only machine (turbo_rows = 0) with the DragCompressor code-default channel geometry
    (assumed, uncited), at the rotor-stress-limited speed capped by size_for's rpm_max default, fed at the plenum of
    each closed candidate. Shows the pumping-speed deficit of a drag stage as the first stage (EV-01 form)."""
    from abep_sim.compressor import DragCompressor
    res = {}
    for cid, c in env.items():
        dv = {k: v["value"] for k, v in closure["design_input_documents"][cid]["inputs"].items()}
        kw = {f: (int(dv["compressor." + f]) if f in fe.COMP_INT_FIELDS else dv["compressor." + f])
              for f in fe._dragcompressor_fields() if f not in fe.COMP_SIZED_FIELDS}
        probe = DragCompressor(**kw, turbo_rows=0, n_stages=int(dv["compressor.size_for.max_drag_stages"]), rpm=1.0)
        # drag rotor at its own stress limit (u_max / r), capped by the size_for rpm_max default (both assumed)
        rpm = min(float(dv["compressor.size_for.rpm_max"]),
                  probe.u_max() / probe.rotor_radius_m * 60.0 / (2 * math.pi))
        probe.rpm = rpm
        worst = None
        for cs, r in c["cases"].items():
            out = probe.run(r["p_passive_Pa"], {s: r["forward_flow_to_compressor_kgps"] * r["w_s_inlet"][s] for s in AIR})
            S0 = probe.xi * probe.u * probe.h_mm * 1e-3 * probe.w_mm * 1e-3 / 2.0
            ratio = r["S_required_m3_s"]["0.5"] / S0
            row = {"case": cs, "S0_m3_s": S0, "S_required_b0p5_over_S0": ratio, "CR_active": out["CR_active"],
                   "CR_required_sc": r["CR_required"]["self_consistent_backflow"]}
            if worst is None or ratio > worst["S_required_b0p5_over_S0"]:
                worst = row
        res[cid] = {"rpm": rpm, "u_mps": probe.u, "worst_case": worst}
    return {"evidence_class": "model-derived (from assumed code-default inputs)", "per_candidate": res}


def concepts(env: dict, summ: dict, drag_probe: dict) -> list[dict]:
    from abep_sim.constants import RFP
    CR_req_max = summ["CR_required_self_consistent"]["max"]
    CR_req_min = summ["CR_required_self_consistent"]["min"]
    K_li = ev("EV-08")["value"]["compression_ratio_min"]
    K_zh = ev("EV-09")["value"]["compression_ratio"]
    KO_li, KO_zh = published_O_capability(K_li), published_O_capability(K_zh)
    n_cases = summ["candidate_cases"]
    n_zh_ok = sum(1 for c in env.values() for r in c["cases"].values()
                  if r["CR_required"]["self_consistent_backflow"] <= KO_zh)
    n_zh_ok_up = sum(1 for c in env.values() for r in c["cases"].values()
                     if r["CR_required"]["upper_bound_flow_basis"] <= KO_zh)
    p_pass_max = summ["p_passive_Pa"]["max"]
    set_min = summ["setpoint_Pa"]["min"]
    alloc_W = PROPOSED["compressor_power_allocation_frac"]["value"] * RFP.power_max_W
    P_cryo = ev("EV-10")["value"]["P_cryocooler_W"]
    Pn01 = summ["P_pneumatic_eta_0p01_W"]["max"]
    p_triple_Pa = ev("EV-06")["value"]["p_triple_N2_Torr"] * 133.322368
    CR_liq_min = p_triple_Pa / summ["p_passive_Pa"]["max"]
    dp = drag_probe["per_candidate"]
    drag_worst = max(v["worst_case"]["S_required_b0p5_over_S0"] for v in dp.values())
    drag_best = min(min(v["worst_case"]["S_required_b0p5_over_S0"] for v in dp.values()), drag_worst)
    S_over_pub = summ["S_required_over_published_TMP_max"]["0.25"]
    rows_all = [r for c in env.values() for r in c["cases"].values()]

    def n_fit(P_comp_fn, basis):
        """cases where P_compressor + P_jet_min(12 mN) < P_bus on the given flow basis (HG-1 necessary condition)"""
        return sum(1 for r in rows_all
                   if P_comp_fn(r, basis) + r["P_jet_min_W_at_12mN"][basis] < RFP.power_max_W)
    pn01 = lambda r, bs: r["P_pneumatic_W"]["upper_bound_flow" if bs == "upper_bound_flow" else
                                            "self_consistent_backflow"]["eta_0p01_W"]
    c1_fit_sc, c1_fit_ub = n_fit(pn01, "self_consistent_backflow"), n_fit(pn01, "upper_bound_flow")
    c4_fit_sc = n_fit(lambda r, bs: P_cryo, "self_consistent_backflow")
    c4_fit_ub = n_fit(lambda r, bs: P_cryo, "upper_bound_flow")
    neg_sc = summ["cases_headroom_negative_self_consistent"]

    def g(result, basis, evidence, evidence_class):
        if result not in GATE_RESULTS:
            raise DownselectError(result)
        return {"result": result, "basis": basis, "evidence": evidence, "evidence_class": evidence_class}

    C = []
    C.append({
        "id": "C1", "name": "throat-spanning bladed turbomolecular rotor (+ optional downstream drag / second TMP stage)",
        "family": "molecular-drag / turbomolecular-type (active mechanical)",
        "published_basis": ["EV-08", "EV-09", "EV-03", "EV-04", "EV-05", "EV-01", "EV-02"],
        "published_performance": {
            "compression_ratio": f"LI2015: >= {K_li:g} (secondary citation, species/inlet pressure not stated; verify); "
                                 f"ZHENG2021: {K_zh:g} (search excerpt; verify)",
            "capture_efficiency": "LI2015 ~0.60; ZHENG2021 0.6579 (as above; not transferable to the W1 TPMC geometry)",
            "throughput_pumping_speed": "commercial TMPs 10-3000 l/s (EV-03); no ABEP-scale published value accessed",
            "power": "TBD - requires measured motor/drive/bearing input power of an ABEP-scale unit (none accessed); "
                     "pneumatic band only (EV-05 eta 1-10 %, assumed by source)",
            "mass": "TBD - no published mass accessed",
            "T_feed": "TBD - no published gas temperature rise accessed",
            "rotor_material_O": "commercial rotors are high-strength Al alloys (EV-04); AO behaviour at thermal energy "
                                "TBD (no source accessed)",
            "TRL": "TBD - not stated in accessed sources; LI2015 reported as 'numerical simulations and subsystem "
                   "experiments' (secondary)",
            "life": "TBD - requires > 15,000 h (RFP firing) bearing/rotor life evidence; magnetic suspension exists "
                    "(EV-04, qualitative)"},
        "dragcompressor_mapping": {
            "parameters_required": ["turbo_rows", "turbo_area_m2 (>= A_rotor_min at u)", "turbo_radius_m", "rpm",
                                    "turbo_kS (measured S per area)", "turbo_kK (measured ln K0 per row vs species)",
                                    "turbo_blade_area_frac", "rotor_material", "stress_safety", "eta_motor",
                                    "k_bear_W_per_rads", "P_ctrl_W", "motor_kg_per_Nm", "bearing_kg",
                                    "stator_mass_factor", "conductance_to_sink_W_K", "leak_conductance_m3_s",
                                    "and for a drag back stage: n_stages, h_mm, w_mm, L_per_stage_m, xi"],
            "parameters_sourced_today": [],
            "model_changes_needed": [
                "species-resolved K per row fitted to measured N2/O2 (and O or a declared surrogate) data instead of "
                "the uncited turbo_kK; atomic O is the least compressed species (EV-02 sqrt(m) scaling)",
                "outlet pressures 0.05-1 Pa reach/exceed the 0.1 Pa (1e-3 mbar) molecular-regime limit (EV-03): the "
                "free-molecular Gaede characteristic in DragCompressor is outside its domain at the outlet; needs a "
                "transitional-regime stage characteristic from data",
                "plenum backflow coupling (W1 FC-01 / DI-1.12): compressor sized for the self-consistent plenum, not "
                "the passive plenum",
                "wiring measured parameters into the chain is a model change (goldens may move; HISTORY entry)"]},
        "implied_states": {
            "availability": "PARTIAL - requirement-derived only; no published parameter set exists to run "
                            "DragCompressor for this concept",
            "mdot": "between the W1 SC-BACKFLOW flow and the upper bound, depending on the achieved inlet pumping "
                    "speed (per-case S_required for b = 0.5 / 0.25 / 0.1 in requirement_envelope)",
            "P_feed": "valve setpoint (W1 ladder, PROPOSED); requires the concept to reach CR_required",
            "T_feed": "TBD - requires measured gas temperature rise; W1 value is the DragCompressor lumped model with "
                      "the 300-500 K clamp convention (FC-04)",
            "x_s": "model-derived from the chain-sized code-default machine (heavy species compressed more; W1 "
                   "valve x_s); a measured species-resolved K replaces it",
            "P_compressor": f"pneumatic band <= {Pn01:.3g} W at eta 1 % (all 36 candidate-cases); fixed "
                            "motor/bearing/control loads TBD"},
        "gates": {
            "HG-1": g("CONDITIONAL", f"pneumatic band <= {Pn01:.3g} W at eta = 1 % (fixed loads TBD; the chain-sized "
                                     "code-default machine gives "
                                     f"{summ['chain_machine_P_el_W']['min']:.3g}-{summ['chain_machine_P_el_W']['max']:.3g}"
                                     f" W); with the 12 mN jet-power bound the bus closes at {c1_fit_ub}/{n_cases} "
                                     f"candidate-cases on the upper-bound flow and {c1_fit_sc}/{n_cases} on the "
                                     "self-consistent flow; the misses (" + (", ".join(neg_sc) or "none") + ") fail "
                                     "for any compressor: the delivered flow is too low (raise it via HG-5)",
                      ["EV-05"], "model-derived"),
            "HG-1b": g("CONDITIONAL", f"within the PROPOSED {alloc_W:.0f} W allocation only if the fixed motor, "
                                      "bearing and control loads are; requires measured input power", ["EV-05"],
                       "model-derived"),
            "HG-2": g("NOT_EVALUABLE", "no published mass for an ABEP-scale unit; LI2015 excerpt calls the device "
                                       "complex and heavy (verify)", ["EV-08"], "inferred"),
            "HG-3": g("CONDITIONAL", "metallic (Al alloy / Ti) or coated wetted parts: thermal-AO data TBD; bare CFRP "
                                     "or polymer wetted parts fail the ram-yield bound unless the thermal yield is "
                                     f"lower by >= {summ['AO_required_yield_reduction']['max']:.3g}x (EV-17 says "
                                     "'orders of magnitude' lower: verify with a test)",
                      ["EV-16", "EV-17", "EV-18"], "inferred"),
            "HG-4": g("CONDITIONAL", f"published CR {K_zh:g} and >= {K_li:g} would cover the required "
                                     f"{CR_req_min:.3g}-{CR_req_max:.3g} for heavy species; scaled to atomic O (EV-02, assuming the "
                                     f"published CR is for N2): {KO_zh:.3g} (ZHENG2021) covers {n_zh_ok}/{n_cases} "
                                     f"self-consistent cases ({n_zh_ok_up}/{n_cases} upper-bound basis), "
                                     f"{KO_li:.3g} (LI2015) covers all; species and inlet pressure of the published "
                                     "values unverified", ["EV-08", "EV-09", "EV-02"], "inferred"),
            "HG-5": g("CONDITIONAL", "inlet pumping speed must be "
                                     f"{S_over_pub['min']:.3g}-{S_over_pub['max']:.3g}x the largest published "
                                     "commercial TMP speed for b = 0.25 -> a throat-spanning rotor (as in LI2015 / "
                                     "ZHENG2021), not a catalogue pump; stopped-rotor back-streaming needs an "
                                     "isolation valve (EV-04)", ["EV-01", "EV-03", "EV-04"], "model-derived"),
            "HG-6": g("PASS", "upstream of the valve; identical for hall_only / rf_hall / ecr_hall", [], "assumed"),
        },
    })
    C.append({
        "id": "C2", "name": "molecular-drag (Holweck / Gaede) stages only, fed from the passive plenum",
        "family": "molecular-drag (active mechanical)",
        "published_basis": ["EV-01", "EV-02", "EV-03"],
        "published_performance": {
            "compression_ratio": "high K0 for long narrow channels (EV-02); drag stages are used behind TMP blades to "
                                 "raise K0 (EV-03)",
            "throughput_pumping_speed": "S = u b h / 2 (EV-01): small channel cross-section -> small speed",
            "power": "TBD", "mass": "TBD", "T_feed": "TBD", "rotor_material_O": "TBD", "TRL": "TBD", "life": "TBD"},
        "dragcompressor_mapping": {
            "parameters_required": ["n_stages", "rotor_radius_m", "rpm", "h_mm", "w_mm", "L_per_stage_m", "xi",
                                    "rotor_material", "leak_conductance_m3_s", "motor/bearing/thermal fields"],
            "parameters_sourced_today": [],
            "model_changes_needed": ["same transitional-regime and species issues as C1"]},
        "implied_states": {
            "availability": "PROBE ONLY - DragCompressor run read-only with turbo_rows = 0 and code-default channel "
                            "geometry (assumed)",
            "mdot": "not closable: pumping speed deficit (below)", "P_feed": "TBD", "T_feed": "TBD", "x_s": "TBD",
            "P_compressor": "TBD"},
        "gates": {
            "HG-1": g("NOT_EVALUABLE", "no sourced power data", [], "assumed"),
            "HG-1b": g("NOT_EVALUABLE", "no sourced power data", [], "assumed"),
            "HG-2": g("NOT_EVALUABLE", "no sourced mass data", [], "assumed"),
            "HG-3": g("CONDITIONAL", "same material logic as C1", ["EV-16", "EV-17"], "inferred"),
            "HG-4": g("CONDITIONAL", "K0 can be made large (EV-02); not the binding constraint", ["EV-02"],
                      "model-derived"),
            "HG-5": g("FAIL", f"as first stage: S_required(b = 0.5) / S0 = {drag_best:.3g}-{drag_worst:.3g} with the "
                              "code-default channel (worst case per candidate; DragCompressor then gives CR_active = 1, "
                              "i.e. no compression at that throughput); raising b h to the needed area turns "
                              "it into a throat-spanning rotor (C1). Retained only as a back stage of C1",
                      ["EV-01"], "model-derived"),
            "HG-6": g("PASS", "upstream of the valve; architecture-neutral", [], "assumed"),
        },
    })
    C.append({
        "id": "C3", "name": "passive collimated intake only (no active compressor)",
        "family": "passive collimated-intake compression",
        "published_basis": ["EV-14"],
        "published_performance": {
            "compression_ratio": "passive intake compression ~100-300 (EV-14, model-derived; definitions may differ); "
                                 "the frozen W1 TPMC CR_passive 162-278 is of the same order",
            "throughput_pumping_speed": "n/a", "power": "0 W compressor", "mass": "intake only",
            "T_feed": "intake wall temperature (TBD)", "rotor_material_O": "no rotor; intake walls see ram AO",
            "TRL": "TBD", "life": "TBD"},
        "dragcompressor_mapping": {
            "parameters_required": [], "parameters_sourced_today": [],
            "model_changes_needed": ["the chain has no 'no compressor' mode (lane-16 run_chain supports 'fixed' and "
                                     "'size_for'); a bypass option is a chain change outside this lane"]},
        "implied_states": {
            "availability": "REQUIREMENT CHECK - feed pressure = passive plenum pressure",
            "mdot": "TBD - set by the downstream (thruster) conductance at p_passive, not by a setpoint",
            "P_feed": f"<= {p_pass_max:.3g} Pa (max over 36 candidate-cases) vs lowest ladder setpoint {set_min:g} Pa",
            "T_feed": "TBD", "x_s": "free-stream split with wall recombination (TBD)", "P_compressor": "0 W"},
        "gates": {
            "HG-1": g("PASS", "no compressor load", [], "model-derived"),
            "HG-1b": g("PASS", "no compressor load", [], "model-derived"),
            "HG-2": g("PASS", "no compressor mass", [], "model-derived"),
            "HG-3": g("NOT_EVALUABLE", "intake-wall AO is an intake-lane item", [], "assumed"),
            "HG-4": g("FAIL", f"CR_active = 1 < required {CR_req_min:.3g}-{CR_req_max:.3g}: P_feed <= "
                              f"{p_pass_max:.3g} Pa is below every ladder setpoint (>= {set_min:g} Pa). The gate "
                              "rests on the PROPOSED setpoint ladder, not on the RFP: C3 is eliminated only WITHIN "
                              "the tested (W1 ladder) envelope and returns if the Phase-1 knee shows sustainment at "
                              "the passive plenum pressure with a direct-feed channel", [], "model-derived"),
            "HG-5": g("NOT_EVALUABLE", "backflow is the passive flux balance itself (FC-01)", [], "inferred"),
            "HG-6": g("PASS", "architecture-neutral", [], "assumed"),
        },
    })
    C.append({
        "id": "C4", "name": "cryocondensation-regeneration active intake (CRAID-type, storage-based)",
        "family": "cryo / storage-based",
        "published_basis": ["EV-10", "EV-11", "EV-12", "EV-13", "EV-07"],
        "published_performance": {
            "compression_ratio": "effective 3.0e7 (EV-11, model-derived by source)",
            "capture_efficiency": "effective 0.261 (EV-11)",
            "throughput_pumping_speed": "batch: condense then regenerate; 31.7 min regeneration at 20 sccm for two "
                                        "RITs (EV-13)",
            "power": f"cryocooler {P_cryo:g} W for 14 W of cryopanel cooling during condensation (EV-10)",
            "mass": "TBD - not in the accessed text",
            "T_feed": "regeneration at 54.5 K panel (EV-13); reservoir gas temperature TBD",
            "rotor_material_O": "no rotor; AO assumed fully recombined by the source (EV-12, assumption)",
            "TRL": "conceptual prototype model, numerical analysis (REF-MOON2025); integrated in-space system not "
                   "demonstrated (EV-07)", "life": "TBD - cryocooler life > 15,000 h not in accessed text"},
        "dragcompressor_mapping": {
            "parameters_required": [], "parameters_sourced_today": [],
            "model_changes_needed": ["DragCompressor does not apply: needs a condense/regenerate storage-cycle model "
                                     "(panel heat load, cryocooler COP, duty cycle vs firing time, W1 FC-08 "
                                     "accumulation)"]},
        "implied_states": {
            "availability": "NOT EVALUABLE at the nine cases - no published scaling of cryocooler power with "
                            "condensed flow; only the published point design",
            "mdot": "TBD", "P_feed": "TBD", "T_feed": "TBD", "x_s": "TBD (AO recombination assumed by source)",
            "P_compressor": f"{P_cryo:g} W at the published point (EV-10)"},
        "gates": {
            "HG-1": g("CONDITIONAL", f"{P_cryo:g} W < 1.5 kW leaves {RFP.power_max_W - P_cryo:g} W for the Hall "
                                     "discharge and all other loads during condensation; if thruster and condensation "
                                     f"run concurrently, the 12 mN jet-power bound fits at {c4_fit_ub}/{n_cases} "
                                     f"(upper-bound flow) and {c4_fit_sc}/{n_cases} (self-consistent flow) W1 "
                                     "candidate-cases before any thruster loss (W1 flows used as a proxy; CRAID's own "
                                     "delivered flow differs)", ["EV-10"], "model-derived"),
            "HG-1b": g("FAIL_AT_PUBLISHED_POINT", f"{P_cryo:g} W > PROPOSED allocation {alloc_W:.0f} W; a scaled "
                                                  "variant is NOT_EVALUABLE (no published scaling)", ["EV-10"],
                       "model-derived"),
            "HG-2": g("NOT_EVALUABLE", "no mass in accessed text", [], "assumed"),
            "HG-3": g("NOT_EVALUABLE", "AO handling is an assumption of the source (EV-12)", ["EV-12"], "assumed"),
            "HG-4": g("PASS", "effective CR 3.0e7 >> 142 (model-derived by source)", ["EV-11"], "model-derived"),
            "HG-5": g("NOT_EVALUABLE", "batch process; backflow during regeneration not in accessed text", [],
                      "assumed"),
            "HG-6": g("PASS", "upstream of the valve; architecture-neutral", [], "assumed"),
        },
    })
    C.append({
        "id": "C5", "name": "compression + liquefaction storage (PROFAC-type)",
        "family": "storage-based",
        "published_basis": ["EV-06", "EV-07"],
        "published_performance": {
            "compression_ratio": f"needs >= {CR_liq_min:.3g} from the highest passive plenum pressure to the N2 "
                                 "triple point (EV-06; computed)",
            "throughput_pumping_speed": "TBD", "power": "TBD", "mass": "TBD", "T_feed": "TBD (cryogenic storage)",
            "rotor_material_O": "TBD", "TRL": "not demonstrated in space (EV-07)", "life": "TBD"},
        "dragcompressor_mapping": {"parameters_required": [], "parameters_sourced_today": [],
                                   "model_changes_needed": ["compressor to ~12.5 kPa plus liquefier model; outside "
                                                            "the free-molecular DragCompressor domain"]},
        "implied_states": {"availability": "NOT EVALUABLE", "mdot": "TBD", "P_feed": "TBD", "T_feed": "TBD",
                           "x_s": "TBD", "P_compressor": "TBD"},
        "gates": {
            "HG-1": g("NOT_EVALUABLE", "no sourced power", [], "assumed"),
            "HG-1b": g("NOT_EVALUABLE", "no sourced power", [], "assumed"),
            "HG-2": g("NOT_EVALUABLE", "no sourced mass", [], "assumed"),
            "HG-3": g("NOT_EVALUABLE", "no source", [], "assumed"),
            "HG-4": g("CONDITIONAL", f"requires CR >= {CR_liq_min:.3g}, more than three orders of magnitude above the feed need; "
                                     "not needed for a continuous feed", ["EV-06"], "inferred"),
            "HG-5": g("NOT_EVALUABLE", "no source", [], "assumed"),
            "HG-6": g("PASS", "architecture-neutral", [], "assumed"),
        },
    })
    C.append({
        "id": "C6", "name": "sorption / getter storage",
        "family": "storage-based",
        "published_basis": [],
        "published_performance": {k: "TBD - no open ABEP source located or accessed in this survey"
                                  for k in ("compression_ratio", "throughput_pumping_speed", "power", "mass",
                                            "T_feed", "rotor_material_O", "TRL", "life")},
        "dragcompressor_mapping": {"parameters_required": [], "parameters_sourced_today": [],
                                   "model_changes_needed": ["sorption-cycle model (TBD)"]},
        "implied_states": {"availability": "NOT EVALUABLE", "mdot": "TBD", "P_feed": "TBD", "T_feed": "TBD",
                           "x_s": "TBD", "P_compressor": "TBD"},
        "gates": {k: g("NOT_EVALUABLE", "no source accessed", [], "assumed")
                  for k in ("HG-1", "HG-1b", "HG-2", "HG-3", "HG-4", "HG-5")} |
                 {"HG-6": g("PASS", "architecture-neutral", [], "assumed")},
    })
    C.append({
        "id": "C7", "name": "plasma / electrostatic pumping inside the ionization stage",
        "family": "electrostatic / other",
        "published_basis": ["EV-15"],
        "published_performance": {
            "compression_ratio": "not quantified in the accessed text for the pumping effect alone",
            "throughput_pumping_speed": "TBD", "power": "part of the ionization-stage power", "mass": "TBD",
            "T_feed": "n/a (ions)", "rotor_material_O": "n/a", "TRL": "TBD", "life": "TBD"},
        "dragcompressor_mapping": {"parameters_required": [], "parameters_sourced_today": [],
                                   "model_changes_needed": ["belongs to the pre-ionizer / Hall block, not the gas path"]},
        "implied_states": {"availability": "OUT OF SCOPE for DI-1.4", "mdot": "n/a", "P_feed": "n/a",
                           "T_feed": "n/a", "x_s": "n/a", "P_compressor": "n/a"},
        "gates": {k: g("NOT_EVALUABLE", "out of the DI-1.4 gas-path scope", [], "assumed")
                  for k in ("HG-1", "HG-1b", "HG-2", "HG-3", "HG-4", "HG-5")} |
                 {"HG-6": g("OUT_OF_SCOPE", "compression by the ionization stage makes the feed state depend on the "
                                            "pre-ionizer, breaking the common feed boundary (RF/ECR change only the "
                                            "pre-ionization method); belongs to the rf_hall / ecr_hall source lanes, "
                                            "never to DI-1.4", ["EV-15"], "inferred")},
    })
    return C


GATES = (
    {"id": "HG-1", "name": "compressor power within the 1.5 kW bus (necessary condition)",
     "rule": "P_compressor + P_jet_min(12 mN, delivered flow) < 1.5 kW, with P_jet_min = T^2 / (2 mdot) the thrust "
             "power of 12 mN at thruster efficiency 1 (a lower bound on the Hall-block load, Hall-closure-free)",
     "origin": "RFP (power_max_W 1500, thrust_min_mN 12; abep_sim/constants.py RFP); jet-power bound model-derived",
     "status": "RFP-derived"},
    {"id": "HG-1b", "name": "compressor power within the PROPOSED allocation",
     "rule": "P_compressor <= allocation (PROPOSED 20 % of 1.5 kW = 300 W; owner decision OD-C2)",
     "origin": "PROPOSED", "status": "PROPOSED"},
    {"id": "HG-2", "name": "mass within 40 kg",
     "rule": "compressor mass (incl. motor, drive, bearings, housing) inside the propulsion-subsystem 40 kg with the "
             "mass BOM allocation (docs/architecture_comparison/mass_bom, compressor line TBD)",
     "origin": "RFP (mass_max_kg 40); allocation TBD", "status": "RFP-derived, allocation TBD"},
    {"id": "HG-3", "name": "atomic-oxygen compatibility",
     "rule": "wetted rotor/stator/channel materials must not recede beyond the PROPOSED 0.1 mm allowance over 26,000 h "
             "at the per-case AO number flow; ram-energy yields (EV-16) bound the thermal-gas case from above (EV-17)",
     "origin": "RFP mission duration; allowance PROPOSED", "status": "PROPOSED"},
    {"id": "HG-4", "name": "compression ratio 2.4-142 incl. atomic O",
     "rule": "the concept's compression ratio for the least-compressed species (atomic O, EV-02) covers the W1 "
             "self-consistent requirement at each of the 36 candidate-cases",
     "origin": "W1 feed-state closure (FC-01: required active CR 2.37-142; PROPOSED setpoint ladder)",
     "status": "derived from PROPOSED W1 inputs"},
    {"id": "HG-5", "name": "backflow",
     "rule": "(a) inlet pumping speed S >= S_required(b) so that the plenum backflow fraction b stays at the target "
             "(W1 FC-01 model; b targets PROPOSED); (b) no uncontrolled back-streaming on rotor stop (isolation valve)",
     "origin": "W1 FC-01; EV-01, EV-04", "status": "PROPOSED targets"},
    {"id": "HG-6", "name": "common feed boundary",
     "rule": "the compressor sits upstream of the valve and is identical for hall_only / rf_hall / ecr_hall; a concept "
             "whose compression depends on the pre-ionizer is out of DI-1.4 scope",
     "origin": "owner operating model (RF/ECR change only the pre-ionization method; CLAUDE.md scope rule)",
     "status": "binding scope rule"},
)


def recommendation(summ: dict) -> dict:
    return {
        "status": "PROPOSED for owner review (not a design freeze, not an architecture ranking)",
        "primary": {
            "concept": "C1",
            "statement": "a throat-spanning bladed turbomolecular-type rotor as first stage (optionally followed by a "
                         "drag or second TMP stage), metallic or coated AO-compatible wetted parts (no bare CFRP "
                         "or polymer), with an isolation valve against stopped-rotor back-streaming",
            "why": ["only concept with published ABEP-specific compression data in the required range (EV-08, "
                    "EV-09; both need verification)",
                    "the only surveyed mechanism that can supply the required inlet pumping speed continuously, at "
                    "throat-scale rotor area (EV-01 / EV-03 bound; not demonstrated at ABEP scale)",
                    "pneumatic power is small (<= %.3g W at eta 1 %%); the fixed loads are the unknown" %
                    summ["P_pneumatic_eta_0p01_W"]["max"]],
            "conditions": ["measured CR vs inlet pressure for N2, O2 and O (or an owner-accepted surrogate) covering "
                           "142 on O", "measured inlet pumping speed at throat scale meeting S_required(b = 0.25)",
                           "measured electrical input power within the owner allocation",
                           "mass within the BOM allocation", "thermal-AO compatibility of wetted materials",
                           "life evidence toward > 15,000 h firing"]},
        "retained_reference": {
            "concept": "C3",
            "statement": "passive intake without compressor is kept only as a reference branch: it fails HG-4 on the "
                         "PROPOSED setpoint ladder and returns only if the Phase-1 Hall-only knee is sustainable at "
                         "the passive plenum pressure (%.3g-%.3g Pa)" % (summ["p_passive_Pa"]["min"],
                                                                        summ["p_passive_Pa"]["max"])},
        "watch": {"concept": "C4", "statement": "cryocondensation fails the PROPOSED power allocation at its published "
                                                "point (1.2 kW cryocooler); re-enters only with a published scaling "
                                                "of cryocooler power to the W1 flows"},
        "not_carried": {"C2": "not viable as first stage (pumping speed); kept as a C1 back stage",
                        "C5": "compression far beyond need; storage not required by a continuous feed",
                        "C6": "no open source located", "C7": "out of DI-1.4 scope (common feed boundary)"},
        "never": "the down-selection never ranks hall_only / rf_hall / ecr_hall: the compressor is COMMON_MODE "
                 "(aux-bus lane: compressor cancels)",
    }


def minimum_tests() -> list[dict]:
    return [
        {"id": "T-1", "what": "compression ratio vs inlet pressure (1e-3 - 1e-1 Pa) and throughput for N2 and O2 on a "
                              "throat-scale bladed rotor stage (and the back stage), outlet 0.05 - 1 Pa",
         "freezes": ["turbo_kK / species K", "transitional outlet characteristic"], "gate": ["HG-4"]},
        {"id": "T-2", "what": "inlet pumping speed vs rpm at throat scale against the per-case S_required(b)",
         "freezes": ["turbo_kS", "turbo_area_m2", "rpm"], "gate": ["HG-5"]},
        {"id": "T-3", "what": "atomic-O-bearing flow: species-resolved compression (O vs N2) and wall recombination "
                              "in an AO facility (precedent EV-19), quantitative RGA per owner A3 near_cathode_rga "
                              "rule for any dose claim",
         "freezes": ["x_s at the valve", "O compression"], "gate": ["HG-4", "HG-3"]},
        {"id": "T-4", "what": "electrical input power (motor + drive + bearings + control) at steady state and "
                              "start-up, measured on the spacecraft-side DC bus (bus_power_boundary_v1 compressor term)",
         "freezes": ["eta_motor", "k_bear_W_per_rads", "P_ctrl_W"], "gate": ["HG-1", "HG-1b"]},
        {"id": "T-5", "what": "gas temperature rise and outlet T_feed; heat rejection to the sink",
         "freezes": ["T_gas_K", "conductance_to_sink_W_K", "T_feed"], "gate": ["T_feed field"]},
        {"id": "T-6", "what": "thermal-energy AO exposure of the rotor/stator materials (witness mass per owner A3 "
                              "metrology rule, profilometry)",
         "freezes": ["rotor_material"], "gate": ["HG-3"]},
        {"id": "T-7", "what": "flight-like unit mass incl. motor, drive, bearings, housing",
         "freezes": ["mass fields"], "gate": ["HG-2"]},
        {"id": "T-8", "what": "stopped-rotor conductance and isolation-valve leak (back-streaming)",
         "freezes": ["leak_conductance_m3_s"], "gate": ["HG-5"]},
        {"id": "T-9", "what": "life evidence toward > 15,000 h firing (bearings, rotor creep/fatigue) and the "
                              "rotor angular momentum / vibration delivered to the AOCS",
         "freezes": ["life", "AOCS interface (TBD)"], "gate": ["C-milestone"]},
    ]


def findings(summ: dict, drag_probe: dict) -> list[dict]:
    b = summ
    return [
        {"id": "CD-01", "finding": "every DragCompressor parameter used by the W1 closure is an uncited code default; "
                                   "no accessed open source gives an ABEP compressor parameter set, so no concept can "
                                   "be run through the chain with sourced inputs today",
         "evidence_class": "inferred"},
        {"id": "CD-02", "finding": "the required inlet pumping speed for b = 0.25 is %.3g-%.3g m^3/s, %.3g-%.3gx the "
                                   "largest published commercial TMP speed (3000 l/s, EV-03); the minimum ideal rotor "
                                   "area at 500 m/s is %.3g-%.3g m^2 (throat scale)" % (
                                       b["S_required_m3_s"]["0.25"]["min"], b["S_required_m3_s"]["0.25"]["max"],
                                       b["S_required_over_published_TMP_max"]["0.25"]["min"],
                                       b["S_required_over_published_TMP_max"]["0.25"]["max"],
                                       b["A_rotor_min_m2_at_u_ref"]["0.25"]["min"],
                                       b["A_rotor_min_m2_at_u_ref"]["0.25"]["max"]),
         "evidence_class": "model-derived"},
        {"id": "CD-03", "finding": "atomic O is the least-compressed species (ln K ~ sqrt(m), EV-02); the chain-sized "
                                   "code-default machine gives ln CR_O / ln CR_N2 = %.3g-%.3g (sqrt(16/28) = %.3g), so "
                                   "the valve is O-depleted relative to the inlet and HG-4 must be met on O" % (
                                       b["chain_machine_lnCR_O_over_lnCR_N2"]["min"],
                                       b["chain_machine_lnCR_O_over_lnCR_N2"]["max"], math.sqrt(16.0 / 28.0)),
         "evidence_class": "model-derived"},
        {"id": "CD-04", "finding": "the compressor outlet (setpoints 0.05-1 Pa) reaches/exceeds the 0.1 Pa "
                                   "molecular-regime limit of TMPs (EV-03): DragCompressor's free-molecular Gaede "
                                   "characteristic is out of domain at the outlet; the stage characteristic there "
                                   "must come from data (T-1)", "evidence_class": "inferred"},
        {"id": "CD-05", "finding": "pneumatic compression power is small (<= %.3g W at eta = 1 %%, EV-05); the "
                                   "compressor power is dominated by fixed motor/bearing/control loads that no "
                                   "accessed source quantifies (T-4)" % b["P_pneumatic_eta_0p01_W"]["max"],
         "evidence_class": "model-derived"},
        {"id": "CD-06", "finding": "RFP-derived power bound: 12 mN at the delivered flow needs jet power %.3g-%.3g W "
                                   "(efficiency 1); at %d candidate-case(s) on the self-consistent flow the 1.5 kW bus "
                                   "is exceeded before any compressor or loss (%s): those flows cannot give 12 mN "
                                   "within the RFP whatever the compressor, so DI-1.4 must raise the delivered flow "
                                   "(pumping speed, HG-5), not only compress" % (
                                       b["P_jet_min_W_at_12mN"]["min"], b["P_jet_min_W_at_12mN"]["max"],
                                       len(b["cases_headroom_negative_self_consistent"]),
                                       ", ".join(b["cases_headroom_negative_self_consistent"]) or "none"),
         "evidence_class": "model-derived"},
        {"id": "CD-07", "finding": "bare CFRP wetted blades (the repository rotor default) would recede %.3g-%.3g m "
                                   "over 26,000 h at the ram-energy yield (EV-16); thermal gas erodes far less (EV-17) "
                                   "but by an unmeasured factor (needed: >= %.3gx) -> metallic/coated parts or test "
                                   "T-6" % (b["AO_ram_yield_recession_bound_mission_m"]["min"],
                                            b["AO_ram_yield_recession_bound_mission_m"]["max"],
                                            b["AO_required_yield_reduction"]["max"]),
         "evidence_class": "inferred"},
        {"id": "CD-08", "finding": "published ABEP compressor data are few, partly secondary and all need "
                                   "verification (EV-08, EV-09); none reports power, mass, T_feed or life; the "
                                   "down-selection therefore stays PROPOSED and the 0.030-3.14 mg/s flow range stays a "
                                   "candidate range (owner addendum A3)", "evidence_class": "inferred"},
    ]


def owner_decisions() -> list[dict]:
    return [
        {"id": "OD-C1", "question": "Adopt C1 (throat-spanning bladed rotor + optional back stage) as the DI-1.4 "
                                    "working concept, C3 as reference branch, C4 as watch item?",
         "proposed": "yes (PROPOSED)"},
        {"id": "OD-C2", "question": "Compressor power allocation inside the 1.5 kW bus",
         "proposed": "screening level 300 W (20 %), PROPOSED; to be replaced by the owner value"},
        {"id": "OD-C3", "question": "Accept thermal-AO testing (T-6) or require metallic/coated wetted parts a priori?",
         "proposed": "metallic/coated a priori; T-6 for the selected alloy/coating"},
        {"id": "OD-C4", "question": "Target plenum backflow fraction b (sets the rotor size)",
         "proposed": "b = 0.25 screening target (PROPOSED)"},
        {"id": "OD-C5", "question": "Atomic-O surrogate policy for the compressor tests (T-1/T-3): real AO facility, "
                                    "or O2 plus a declared correction?",
         "proposed": "AO facility for T-3; N2/O2 for T-1"},
    ]


def milestones() -> dict:
    return {
        "supports": ["A"],
        "A": "conditional: 'the feed boundary is served by a C1-type compressor provided T-1..T-5 demonstrate "
             "HG-1..HG-5'; the compressor is COMMON_MODE, so milestone A for any architecture does not depend on it",
        "to_B": "measured compressor characteristics (T-1..T-5, T-8) replacing the code defaults through a controlled "
                "model change (HISTORY entry; goldens may move), W1 re-run on the measured machine, and resolution "
                "of FC-01 (DI-1.12)",
        "to_C": "mass (T-7), life and AOCS interface (T-9), AO compatibility (T-6) and the power allocation (OD-C2) "
                "integrated into the PDR budgets",
    }


# -------------------------------------------------------------------------------------------------------- assemble
def build() -> dict:
    for rel, h in DECISION_PINS.items():
        if sha256_file(rel) != h:
            raise DownselectError(f"owner decision file {rel} changed (sha256 pin)")
    closure = json.loads((REPO / CLOSURE_REL).read_text())
    if closure.get("schema") != "feed_state_closure_v1":
        raise DownselectError("unexpected W1 closure schema")
    fe = _load_lane16()
    env = requirement_envelope(fe, closure)
    summ = envelope_summary(env)
    probe = drag_only_probe(fe, closure, env)
    conc = concepts(env, summ, probe)
    matrix = {c["id"]: {gid: c["gates"][gid]["result"] for gid in [x["id"] for x in GATES]} for c in conc}
    doc = {
        "schema": SCHEMA_ID, "version": VERSION,
        "status": "DRAFT for owner review; every value not in the RFP or a cited source is PROPOSED or TBD",
        "follow_on": "fo_compressor_downselect", "trigger": "T_PIVOT_COMPRESSOR_DOWNSELECT",
        "owner_disposition": "od_hardware_pivot (addendum A3 DI_1_4_compressor_downselect)",
        "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "decision_pins": DECISION_PINS,
        "input_pins": {rel: sha256_file(rel) for rel in READ_ONLY_INPUTS},
        "architectures": list(ARCHITECTURES),
        "architecture_neutrality": "the compressor is upstream of the valve and COMMON_MODE for hall_only / rf_hall / "
                                  "ecr_hall; no result here ranks or eliminates an architecture",
        "closure_independence": "no Hall transport closure, ensemble member, screening candidate or P5 calibration "
                                "nuisance variable is used; Hall-block uncertainty never enters the compressor",
        "flow_range_status": "the 0.030-3.14 mg/s valve flow bracket remains a candidate range, not a flight truth "
                             "(owner addendum A3)",
        "milestones": milestones(),
        "proposed_levels": PROPOSED,
        "references": REFERENCES,
        "evidence": list(EVIDENCE),
        "gates": list(GATES),
        "requirement_envelope": env,
        "requirement_summary": summ,
        "drag_only_probe": probe,
        "concepts": conc,
        "downselect_matrix": matrix,
        "recommendation": recommendation(summ),
        "minimum_data_to_freeze_DI_1_4": minimum_tests(),
        "findings": findings(summ, probe),
        "owner_decisions": owner_decisions(),
    }
    return rnd(doc)


# ----------------------------------------------------------------------------------------------------------- render
def fmt(x, d=3):
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    return f"{x:.{d}g}"


def render_md(doc: dict) -> str:
    s = doc["requirement_summary"]
    L = []
    A = L.append
    A("# DI-1.4 compressor down-selection v1")
    A("")
    A(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}`. Do not edit by hand; rerun the script (`--check` verifies).")
    A("")
    A("| | |\n|---|---|")
    A(f"| machine-readable | [`{JSON_NAME}`]({JSON_NAME}) |")
    A(f"| status | **{doc['status']}** (version {doc['version']}) |")
    A(f"| lane | `{doc['follow_on']}` (trigger `{doc['trigger']}`, {doc['owner_disposition']}) |")
    A(f"| milestone | supports **A**; B and C needs in section 9 |")
    A("| architectures | `hall_only`, `rf_hall`, `ecr_hall`: compressor is COMMON_MODE (never ranks them) |")
    A("| test | `tests/test_compressor_downselect.py` |")
    A("")
    A("**What it is.** A survey of open published compressor concepts for ABEP intake gas at 180-230 km, the "
      "requirement envelope that the W1 feed-state closure places on any compressor at the nine frozen atmospheric "
      "cases (evaluated with the repository chain read-only), a down-selection matrix with explicit hard gates, "
      "PROPOSED candidate(s) and the minimum data/tests to freeze DI-1.4.")
    A("")
    A("**What it is not.** Not a compressor design, not a flight value, not an architecture ranking, not a model "
      "change. No `abep_sim` module is changed or wired. " + doc["flow_range_status"][0].upper() +
      doc["flow_range_status"][1:] + ".")
    A("")
    A("## 1. Requirement envelope (36 closed W1 candidate-cases)")
    A("")
    A("Recomputed read-only from the W1 design-input documents (`abep_sim.intake.collection/compress`, cross-checked "
      "against the W1 JSON); status " + VALUE_STATUS + ", evidence *" + DERIVED_EVIDENCE + "*.")
    A("")
    A("| quantity | range | basis |\n|---|---|---|")
    A(f"| required active CR (self-consistent backflow) | {fmt(s['CR_required_self_consistent']['min'])}–"
      f"{fmt(s['CR_required_self_consistent']['max'])} | W1 SC-BACKFLOW |")
    A(f"| required active CR (upper-bound flow basis) | {fmt(s['CR_required_upper_bound_flow']['min'])}–"
      f"{fmt(s['CR_required_upper_bound_flow']['max'])} | setpoint / p_passive |")
    A(f"| passive plenum pressure [Pa] | {fmt(s['p_passive_Pa']['min'])}–{fmt(s['p_passive_Pa']['max'])} | frozen TPMC |")
    A(f"| valve flow bracket [mg/s] | {fmt(s['mdot_valve_bracket_kgps']['min'] * 1e6)}–"
      f"{fmt(s['mdot_valve_bracket_kgps']['max'] * 1e6)} | W1 (candidate range) |")
    for k in ("0.5", "0.25", "0.1"):
        A(f"| inlet pumping speed for b = {k} [m³/s] | {fmt(s['S_required_m3_s'][k]['min'])}–"
          f"{fmt(s['S_required_m3_s'][k]['max'])} (×{fmt(s['S_required_over_published_TMP_max'][k]['min'])}–"
          f"{fmt(s['S_required_over_published_TMP_max'][k]['max'])} of 3000 l/s) | FC-01 model; EV-03 |")
    A(f"| min ideal rotor area at 500 m/s, b = 0.25 [m²] | {fmt(s['A_rotor_min_m2_at_u_ref']['0.25']['min'])}–"
      f"{fmt(s['A_rotor_min_m2_at_u_ref']['0.25']['max'])} | EV-01 S = uA/2 |")
    A(f"| pneumatic power, eta 10 % / 1 % [W] | ≤ {fmt(s['P_pneumatic_eta_0p10_W']['max'])} / ≤ "
      f"{fmt(s['P_pneumatic_eta_0p01_W']['max'])} | EV-05 |")
    A(f"| chain-sized code-default machine P_el [W] | {fmt(s['chain_machine_P_el_W']['min'])}–"
      f"{fmt(s['chain_machine_P_el_W']['max'])} | assumed inputs |")
    A(f"| jet power of 12 mN at delivered flow [W] | {fmt(s['P_jet_min_W_at_12mN']['min'])}–"
      f"{fmt(s['P_jet_min_W_at_12mN']['max'])} | RFP, efficiency 1 |")
    A(f"| ln CR_O / ln CR_N2 (chain machine) | {fmt(s['chain_machine_lnCR_O_over_lnCR_N2']['min'])}–"
      f"{fmt(s['chain_machine_lnCR_O_over_lnCR_N2']['max'])} | EV-02 |")
    A(f"| CFRP ram-yield recession, 26,000 h [m] | {fmt(s['AO_ram_yield_recession_bound_mission_m']['min'])}–"
      f"{fmt(s['AO_ram_yield_recession_bound_mission_m']['max'])} | EV-16 (upper bound, EV-17) |")
    A("")
    A("Cases where 12 mN at the self-consistent flow already exceeds 1.5 kW (efficiency 1): " +
      (", ".join(f"`{x}`" for x in s["cases_headroom_negative_self_consistent"]) or "none") +
      ". Upper-bound flow: " + (", ".join(f"`{x}`" for x in s["cases_headroom_negative_upper_bound"]) or "none") + ".")
    A("")
    A("### Per candidate and case")
    A("")
    A("| candidate | case | p_passive [Pa] | setpoint [Pa] | CR req (SC / UB) | ṁ SC–UB [mg/s] | S(b=0.25) [m³/s] | "
      "P_pn η1 % [W] | P_jet 12 mN SC [W] | x_O valve (chain) |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for cid, c in doc["requirement_envelope"].items():
        for cs, r in c["cases"].items():
            A(f"| {cid} | {cs} | {fmt(r['p_passive_Pa'])} | {fmt(r['setpoint_Pa'])} | "
              f"{fmt(r['CR_required']['self_consistent_backflow'])} / {fmt(r['CR_required']['upper_bound_flow_basis'])} | "
              f"{fmt(r['mdot_valve_kgps']['self_consistent_backflow'] * 1e6)}–{fmt(r['mdot_valve_kgps']['upper_bound'] * 1e6)} | "
              f"{fmt(r['S_required_m3_s']['0.25'])} | "
              f"{fmt(max(r['P_pneumatic_W']['upper_bound_flow']['eta_0p01_W'], r['P_pneumatic_W']['self_consistent_backflow']['eta_0p01_W']))} | "
              f"{fmt(r['P_jet_min_W_at_12mN']['self_consistent_backflow'])} | "
              f"{fmt(r['chain_sized_machine']['x_s_valve']['O'])} |")
    A("")
    A("## 2. Hard gates")
    A("")
    A("| id | gate | rule | origin |\n|---|---|---|---|")
    for gt in doc["gates"]:
        A(f"| {gt['id']} | {gt['name']} | {gt['rule']} | {gt['origin']} |")
    A("")
    A("## 3. Down-selection matrix")
    A("")
    gids = [gt["id"] for gt in doc["gates"]]
    A("| concept | " + " | ".join(gids) + " |")
    A("|---|" + "---|" * len(gids))
    for c in doc["concepts"]:
        A(f"| **{c['id']}** {c['name']} | " + " | ".join(c["gates"][g]["result"] for g in gids) + " |")
    A("")
    A("Gate bases (with evidence ids and class):")
    A("")
    for c in doc["concepts"]:
        A(f"- **{c['id']}** ({c['family']}):")
        for g in gids:
            x = c["gates"][g]
            A(f"  - {g} {x['result']}: {x['basis']} [{', '.join(x['evidence']) or '—'}; {x['evidence_class']}]")
    A("")
    A("## 4. Concepts: published data, DragCompressor mapping, implied states")
    A("")
    for c in doc["concepts"]:
        A(f"### {c['id']} — {c['name']}")
        A("")
        A("| item | published / status |\n|---|---|")
        for k, v in c["published_performance"].items():
            A(f"| {k} | {v} |")
        A("")
        m = c["dragcompressor_mapping"]
        A("DragCompressor parameters required: " + (", ".join(f"`{p}`" for p in m["parameters_required"]) or "none") +
          ". Sourced today: " + (", ".join(m["parameters_sourced_today"]) or "**none**") + ".")
        A("")
        for mc in m["model_changes_needed"]:
            A(f"- model change: {mc}")
        A("")
        A("Implied states at the nine cases: " + "; ".join(f"**{k}**: {v}" for k, v in c["implied_states"].items()))
        A("")
    p = doc["drag_only_probe"]["per_candidate"]
    A("C2 probe (DragCompressor, turbo_rows = 0, code-default channel, assumed): " + "; ".join(
        f"{cid} rpm {fmt(v['rpm'])}, worst S_req(b=0.5)/S0 = {fmt(v['worst_case']['S_required_b0p5_over_S0'])} "
        f"at {v['worst_case']['case']}" for cid, v in p.items()) + ".")
    A("")
    A("## 5. Recommendation (PROPOSED)")
    A("")
    r = doc["recommendation"]
    A(f"Status: **{r['status']}**.")
    A("")
    A(f"- **Primary: {r['primary']['concept']}** — {r['primary']['statement']}.")
    for w in r["primary"]["why"]:
        A(f"  - why: {w}")
    for w in r["primary"]["conditions"]:
        A(f"  - condition: {w}")
    A(f"- **Reference: {r['retained_reference']['concept']}** — {r['retained_reference']['statement']}.")
    A(f"- **Watch: {r['watch']['concept']}** — {r['watch']['statement']}.")
    for k, v in r["not_carried"].items():
        A(f"- not carried: **{k}** — {v}.")
    A(f"- {r['never']}.")
    A("")
    A("## 6. Minimum data / tests to freeze DI-1.4")
    A("")
    A("| id | test | freezes | gate |\n|---|---|---|---|")
    for t in doc["minimum_data_to_freeze_DI_1_4"]:
        A(f"| {t['id']} | {t['what']} | {', '.join(t['freezes'])} | {', '.join(t['gate'])} |")
    A("")
    A("## 7. Findings")
    A("")
    for f in doc["findings"]:
        A(f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}")
    A("")
    A("## 8. Owner decisions")
    A("")
    A("| id | question | proposed |\n|---|---|---|")
    for o in doc["owner_decisions"]:
        A(f"| {o['id']} | {o['question']} | {o['proposed']} |")
    A("")
    A("## 9. Milestones")
    A("")
    ms = doc["milestones"]
    A(f"- supports: {', '.join(ms['supports'])}")
    A(f"- A: {ms['A']}")
    A(f"- to reach B: {ms['to_B']}")
    A(f"- to reach C: {ms['to_C']}")
    A("")
    A("## 10. PROPOSED levels")
    A("")
    for k, v in doc["proposed_levels"].items():
        A(f"- `{k}` = {v['value']} {v['unit']}: {v['meaning']}")
    A("")
    A("## 11. Evidence register")
    A("")
    A("| id | ref | where | statement | class | verify |\n|---|---|---|---|---|---|")
    for e in doc["evidence"]:
        A(f"| {e['id']} | {e['ref']} | {e['where']} | {e['statement']} | {e['evidence_class']} | "
          f"{'yes' if e['verify'] else 'no'} |")
    A("")
    A("## 12. References (accessed 2026-09-27; open sources only, no contact, no paywall bypass)")
    A("")
    for k, v in doc["references"].items():
        A(f"- **{k}**: {v['citation']}. {v['doi_or_url']}. Access: {v['access_level']}. {v['note']}")
    A("")
    A("## 13. Pins")
    A("")
    for k, v in doc["decision_pins"].items():
        A(f"- decision `{k}` sha256 `{v}`")
    for k, v in doc["input_pins"].items():
        A(f"- input `{k}` sha256 `{v}`")
    A("")
    return "\n".join(L)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed outputs are reproduced")
    a = ap.parse_args(argv)
    doc = build()
    js, md = dump(doc), render_md(doc)
    out = REPO / OUT_DIR_REL
    if a.check:
        ok = (out / JSON_NAME).exists() and (out / JSON_NAME).read_text() == js and \
            (out / MD_NAME).exists() and (out / MD_NAME).read_text() == md
        print("OK" if ok else "MISMATCH: rerun the builder")
        return 0 if ok else 1
    (out / JSON_NAME).write_text(js)
    (out / MD_NAME).write_text(md)
    print(f"wrote {OUT_DIR_REL}/{JSON_NAME} and {MD_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
