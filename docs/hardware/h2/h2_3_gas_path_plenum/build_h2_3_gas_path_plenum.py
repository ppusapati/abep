#!/usr/bin/env python3
"""H2-3 atmospheric gas path / plenum preliminary design v1 (follow-on fo_h2_3_gas_path_plenum; trigger
T_H2_3_GAS_PATH_PLENUM; owner addenda A5, A6, A7).

What it is: an H2 hardware-design / preliminary-sizing lane (A7 h2_scope) for the FS-C atmospheric branch of the A5
Proposal Reference Architecture: compressor outlet -> buffer/plenum -> atmospheric metering valve -> Xe tie-in ->
gas isolator -> IP-UP -> pre-ionizer module slot -> IP-DN -> H-1 anode manifold / gas distributor -> HALL_INLET_Z0.
It gives the line topology with the interface planes placed on it, the P_feed / T_feed / x_s measurement locations,
segment conductances with their flow regime (Knudsen number), a cold-flow pressure budget, plenum volume ranges from
explicit requirements (compressor ripple, metering-valve bandwidth, ride-through, ram-flow variation), the fill/drain
time constants tau = V/C, the anode-manifold azimuthal-uniformity sizing rule, atomic-O recombination consequences and
O2 materials compatibility, and the interface demands to the other H2 / A6 lanes.

What it is not: not an architecture-selection lane (never ranks hall_only / rf_hall / ecr_hall), not a performance
prediction (no thrust, efficiency, discharge current or plasma state; no Hall transport closure, no screening
candidate, no abep_sim/plasma_devices.py, no withdrawn v1.2-v1.6 number), not a model change (no abep_sim module is
modified or wired). Every pressure computed here is a COLD-FLOW (no plasma) gas-dynamics quantity. P5 calibration
nuisance never enters. The valve-outlet feed state is taken from the W1 feed-state closure deliverable, never from the
superseded 0-D assumptions. Analog geometry (ECHT: 86 mm long, 10 mm wide, 100 mm OD, CLAUDE.md) is used for
ILLUSTRATION ONLY and is labelled as such; the H-1 geometry is PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/.

Inputs: immutable owner decisions + G0 record (sha256-pinned; the build refuses on mismatch); read-only consumed
deliverables (fingerprinted by sha256 in provenance, not pinned); the frozen atmosphere dataset
abep_sim/data/atmosphere_msis21_v1.csv (read directly, never live MSIS); abep_sim.constants (K_B, AMU, M_SPECIES,
MU_EARTH, R_EARTH; read only). Published sources are hard-coded in REFERENCES with URL, locator and access level.

Deterministic, standard library only, no Julia, runs in well under a second.

Usage:
  python docs/hardware/h2/h2_3_gas_path_plenum/build_h2_3_gas_path_plenum.py          # (re)write JSON + MD
  python docs/hardware/h2/h2_3_gas_path_plenum/build_h2_3_gas_path_plenum.py --check  # exit 1 unless reproduced
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from abep_sim.constants import AMU, K_B, M_SPECIES, MU_EARTH, R_EARTH  # noqa: E402

OUT_DIR_REL = "docs/hardware/h2/h2_3_gas_path_plenum"
SCRIPT_REL = f"{OUT_DIR_REL}/build_h2_3_gas_path_plenum.py"
JSON_NAME = "h2_3_gas_path_plenum_v1.json"
MD_NAME = "H2_3_GAS_PATH_PLENUM.md"
SCHEMA_ID = "h2_3_gas_path_plenum_v1"
VERSION = "1.0.0"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
ARCHS = ["hall_only", "rf_hall", "ecr_hall"]

OD_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
A4_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"
A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A7_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"
G0_REL = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
# Immutable inputs only (owner decision files and the G0 verification record). Mutable governance files
# (lane_registry_v1.json, trigger_registry_v1.json, trigger ledgers, runtime_state.json) are never pinned or read.
DECISION_PINS = {
    OD_REL: "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    A4_REL: "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4",
    A5_REL: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6_REL: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    A7_REL: "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    G0_REL: "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
}

W1_REL = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
CMP_REL = "docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json"
HW_REL = "docs/experiments/hardware/hardware_requirements_v1.json"
INS_REL = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
ICD_REL = "schemas/interfaces/upstream_icd_v1.json"
FENV_REL = "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json"
DFS_REL = "schemas/controls/dual_feed_state_machine_v1.json"
DFS_MD_REL = "docs/controls/DUAL_FEED_STATES.md"
XEL_REL = "docs/budgets/xe_ledger/xe_ledger_v1.json"
BOM_REL = "docs/architecture_comparison/mass_bom/mass_bom_v1.json"
ATM_REL = "abep_sim/data/atmosphere_msis21_v1.csv"
ATM_META_REL = "abep_sim/data/atmosphere_msis21_v1.json"
ARCHB_REL = "abep_sim/arch_boundary.py"
# Consumed deliverables: read-only; sha256 recorded as a build fingerprint (a change requires regeneration). They are
# not pinned as immutable inputs.
CONSUMED = [W1_REL, CMP_REL, HW_REL, INS_REL, ICD_REL, FENV_REL, DFS_REL, DFS_MD_REL, XEL_REL, BOM_REL, ATM_REL,
            ATM_META_REL, ARCHB_REL]

# Parallel lanes (not in the base). Referenced as PENDING only; nothing in this build reads them.
PENDING_LANES = {
    "PMI": "docs/interfaces/preionizer_module/ + schemas/interfaces/preionizer_module_icd_v1.json (fo_preionizer_module_icd)",
    "M16": "docs/budgets/subsystem_maturity/ (fo_subsystem_maturity_matrix)",
    "H2-1": "docs/hardware/h2/h2_1_hall_chamber_magnet/",
    "H2-2": "docs/hardware/h2/h2_2_cathode_integration/",
    "H2-4": "docs/hardware/h2/h2_4_ppu_bus/",
    "H2-5": "docs/hardware/h2/h2_5_thermal_network/",
    "H2-6": "docs/hardware/h2/h2_6_diagnostics_fixture/",
    "H2-7": "docs/hardware/h2/h2_7_mechanical_bom/",
}
PENDING_PROBE_FILES = {
    "PMI": "schemas/interfaces/preionizer_module_icd_v1.json",
    "M16": "docs/budgets/subsystem_maturity",
    "H2-1": "docs/hardware/h2/h2_1_hall_chamber_magnet",
    "H2-2": "docs/hardware/h2/h2_2_cathode_integration",
    "H2-4": "docs/hardware/h2/h2_4_ppu_bus",
    "H2-5": "docs/hardware/h2/h2_5_thermal_network",
    "H2-6": "docs/hardware/h2/h2_6_diagnostics_fixture",
    "H2-7": "docs/hardware/h2/h2_7_mechanical_bom",
}

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
REPRESENTATIVENESS = ("FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY")
M16_STATES = ("READY", "RUNNING", "BLOCKED", "VERIFIED")
ROLLUP = ("architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
          "proposal-only documentation gap")

# ------------------------------------------------------------------------------------------------------------------
# Published references (accessed in this lane unless stated; no contact, no paywall bypass, no LXCat)
# ------------------------------------------------------------------------------------------------------------------
REFERENCES = {
    "REF-CHIGGIATO": {
        "citation": "P. Chiggiato, 'Vacuum Technology for Ion Sources', CERN Accelerator School: Ion Sources, "
                    "CERN-2013-007 (2013); arXiv:1404.0960",
        "url": "https://arxiv.org/pdf/1404.0960",
        "access": "full text read 2026-09-27",
        "used_for": "Eq. 3 mean speed; Eq. 7 mean free path; Table 6 sigma_c (N2 0.43 nm^2, O2 0.40 nm^2); Eq. 10 and "
                    "Table 7 Knudsen regimes (free molecular Kn > 0.5, viscous Kn < 0.01, transitional between); "
                    "Eq. 13 thin-slot conductance C = A<v>/4 and Table 8 (N2 117.5 m^3 s^-1 m^-2 at 293 K); "
                    "Eqs. 19-20 C = C'A tau; Eq. 21 Santeler transmission probability (< 0.7 % error); Eq. 26 series "
                    "combination",
    },
    "REF-LEYBOLD2016": {
        "citation": "Leybold GmbH, 'Fundamentals of Vacuum Technology', Part No. 199 90 (00.200.02), 2016 edition",
        "url": "https://www.leybold.com/content/dam/brands/leybold/downloads/brochures/general-brochures/"
               "Fundamentals_of_Vacuum_Technology_EN.pdf",
        "access": "full text read 2026-09-27 (supplier handbook; used for textbook relations only, no product data)",
        "used_for": "Sec. 1.5.3 a) Eq. 1.26 / 1.26a / 1.27 Knudsen equation for straight pipes (air, 20 degC, "
                    "l >= 10 d; transitional range 1e-2 < d p_mean < 6e-1 mbar cm) (pp. 16-17); Sec. 1.5.1 regime "
                    "limits in p d (p. 15); Sec. 3.2.2.4 capacitance diaphragm gauges: gas-type independent, used "
                    "to 1e-3 mbar with uncertainty rising rapidly from 1e-4 mbar, three decades per sensor, "
                    "e.g. 1 to 1e-3 mbar (pp. 78-79)",
    },
    "REF-SANTELER1986": {
        "citation": "D. J. Santeler, 'New concepts in molecular gas flow', J. Vac. Sci. Technol. A 4 (1986) 338-343, "
                    "doi:10.1116/1.573923",
        "url": "https://doi.org/10.1116/1.573923",
        "access": "not read; formula used as given by REF-CHIGGIATO Eq. 21 (bibliographic data as recorded by "
                  "docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md section 7)",
        "used_for": "transmission probability of circular tubes (via REF-CHIGGIATO)",
    },
    "REF-REID2007": {
        "citation": "B. M. Reid, A. D. Gallimore, 'Review of Hall Thruster Neutral Flow Dynamics', IEPC-2007-038, "
                    "30th International Electric Propulsion Conference, Florence (2007)",
        "url": "https://pepl.engin.umich.edu/wp-content/uploads/pdf/IEPC-2007-038.pdf",
        "access": "full text read 2026-09-27",
        "used_for": "p. 2: the anode typically serves as electrode and gas distributor, delivering neutrals through "
                    "an annular array of small-diameter orifices whose spacing/location alter axial velocity and "
                    "azimuthal uniformity; p. 7: a cold-flow pressure probe at the anode centerline with ~3 % "
                    "reported probe error and a single azimuthal sweep was used to verify the azimuthal uniformity "
                    "of a newly fabricated anode (deGrys et al., as reviewed); p. 8: a manufacturing error causing "
                    "an azimuthal neutral-density non-uniformity decreased efficiency, plume symmetry and stability "
                    "(Hofer, as reviewed); near-anode non-uniformities expected to be reduced within the first 50 % "
                    "of the channel length",
    },
    "REF-ROBERTS2024": {
        "citation": "D. Roberts, 'Enhancing Neutral Propellant Flow Uniformity in Hall Thrusters via Anode Design', "
                    "Master's thesis, University of Washington (2024)",
        "url": "https://digital.lib.washington.edu/researchworks/items/972b2e52-ea16-4c72-9524-ffb95dd1d632/full",
        "access": "repository record / abstract only, read 2026-09-27; body not read",
        "used_for": "abstract: results compared with 'the NASA standard acceptance criteria of <= 5 % absolute "
                    "deviation and <= 10 % peak-to-peak deviation from the mean pressure at the axial midpoint "
                    "between the anode and thruster exit plane'; additive-manufactured anodes with internal baffles. "
                    "The primary NASA source of the criterion is not named in the accessed text: verify",
    },
    "REF-PAUL2023": {
        "citation": "D. Paul, M. Mozetic, R. Zaplotnik, G. Primc, D. Donlagic, A. Vesel, 'A Review of Recombination "
                    "Coefficients of Neutral Oxygen Atoms for Various Materials', Materials 16(5) (2023) 1774, "
                    "doi:10.3390/ma16051774 (CC BY)",
        "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10004365/fullTextXML",
        "access": "full text read 2026-09-27 via Europe PMC (PMC10004365); the publisher page returned HTTP 403 and "
                  "was not bypassed",
        "used_for": "classes: catalytic gamma > 0.1, semi-catalytic 0.01-0.1, inert < 0.01; stainless steel 0.07 "
                    "(10-100 Pa, 400-700 K) and 0.14 (1-15 Pa, 300-400 K); stainless steel and titanium rising "
                    "0.04 -> 0.16 and gold 0.03 -> 0.2 with O-plasma exposure (40 Pa, room temperature); anodized "
                    "aluminium 0.4-0.6 at 1 Pa, room temperature (called 'very large compared to other reports'); "
                    "quartz 0.0012-0.0039 and PTFE 0.0006-0.00066 at room temperature; silver the most catalytic of "
                    "the metals surveyed; 'a large scattering of results' between authors",
    },
    "REF-JANAF-O": {
        "citation": "NIST-JANAF Thermochemical Tables, Oxygen (O), O1(g), table O-001",
        "url": "https://janaf.nist.gov/tables/O-001.txt",
        "access": "table read 2026-09-27",
        "used_for": "delta-f H(O, g, 298.15 K) = 249.173 kJ/mol, so 2 O -> O2 releases 498.346 kJ per mol O2 "
                    "(5.165 eV per O2 formed) at 298.15 K; 246.790 kJ/mol at 0 K",
    },
    "REF-CIFALI2011": {
        "citation": "G. Cifali et al., 'Preliminary characterization test of HET and RIT with Nitrogen and Oxygen', "
                    "IEPC-2011-224 (as recorded in the repository)",
        "url": "https://electricrocket.org/IEPC/IEPC-2011-224.pdf",
        "access": "not re-read in this lane; quoted as recorded by docs/controls/DUAL_FEED_STATES.md (design "
                  "rationale 1) and hardware_requirements_v1.json HW-H1-05 / HW-FS-03",
        "used_for": "Xe ignition then smooth anode transfer to N2 or N2/O2 with the cathode on Xe; post-test anode "
                    "oxidation ('rusty') named the main endurance concern",
    },
    "REF-SI2019": {
        "citation": "SI defining constants (9th SI Brochure, BIPM 2019): Avogadro constant N_A = 6.02214076e23 "
                    "mol^-1 (exact); Boltzmann constant k = 1.380649e-23 J/K (exact, also abep_sim.constants.K_B)",
        "url": "https://www.bipm.org/en/publications/si-brochure",
        "access": "exact defining values quoted from memory of the definition (verify against the brochure)",
        "used_for": "R = N_A k_B; unit conversions",
    },
}

# ------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------
N_A = 6.02214076e23
R_GAS = N_A * K_B
EV = 1.602176634e-19
MOLAR = {s: M_SPECIES[s] / AMU * 1e-3 for s in M_SPECIES}  # kg/mol (repo constants: 16, 28, 32, 131.3 g/mol)
SIGMA_C = {"N2": 0.43e-18, "O2": 0.40e-18}  # m^2, REF-CHIGGIATO Table 6
SIGMA_BOUND = max(SIGMA_C.values())          # used for every species (atomic O not tabulated): shortest lambda
DH_REC_J_PER_MOL_O2 = 2.0 * 249.173e3        # REF-JANAF-O, 298.15 K
CBAR_AIR_LEYBOLD = 12.1e-3 * 1e4 * 12.0 / math.pi  # implied by Leybold Eq. 1.28b: C = 12.1 d^3/l [l/s, cm] = pi cbar d^3/(12 l)


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


def sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def load(rel: str):
    return json.loads((REPO / rel).read_text())


def cbar(T: float, M: float) -> float:
    """Mean molecular speed <v> = sqrt(8 R T / (pi M)) [m/s] (REF-CHIGGIATO Eq. 3; M in kg/mol)."""
    return math.sqrt(8.0 * R_GAS * T / (math.pi * M))


def mix_molar(w: dict) -> float:
    """Mixture molar mass from mass fractions, M = 1 / sum(w_s / M_s) [kg/mol]."""
    tot = sum(w.values())
    if abs(tot - 1.0) > 1e-6:
        raise ValueError(f"mass fractions must sum to 1, got {tot}")
    return 1.0 / sum(w[s] / MOLAR[s] for s in w)


def throughput(mdot: float, T: float, M: float) -> float:
    """pV throughput Q = mdot R T / M [Pa m^3/s]."""
    return mdot * R_GAS * T / M


def mfp(p: float, T: float) -> float:
    """lambda = k T / (sqrt 2 sigma p) (REF-CHIGGIATO Eqs. 7-8) with the largest tabulated sigma_c (0.43 nm^2, N2) for
    every species: the shortest lambda, i.e. the conservative side for any 'molecular regime' statement."""
    return K_B * T / (math.sqrt(2.0) * SIGMA_BOUND * p)


def regime(kn: float) -> str:
    if kn > 0.5:
        return "free-molecular (Kn > 0.5)"
    if kn < 0.01:
        return "viscous (Kn < 0.01)"
    return "transitional (0.01 <= Kn <= 0.5)"


def santeler_tau(L: float, R: float) -> float:
    """Santeler transmission probability for a circular tube (REF-CHIGGIATO Eq. 21)."""
    if L == 0:
        return 1.0
    return 1.0 / (1.0 + (3.0 * L / (8.0 * R)) * (1.0 + 1.0 / (3.0 * (1.0 + L / (7.0 * R)))))


def knudsen_f(d_m: float, pbar_pa: float) -> float:
    """Leybold Eq. 1.27 transitional factor f(d p_mean) = (1 + 203 x + 2780 x^2)/(1 + 237 x), x = d[cm] p[mbar],
    written for air at 20 degC. Applied here to N2/O2/O and Xe at 300-500 K as an INFERRED correction to the
    gas-specific molecular conductance (verify: transfers the air-20 degC function to other gases/temperatures)."""
    x = (d_m * 100.0) * (pbar_pa / 100.0)
    return (1.0 + 203.0 * x + 2780.0 * x * x) / (1.0 + 237.0 * x)


KNUDSEN_F_MIN = min(knudsen_f(0.01, p) for p in [i * 1e-3 for i in range(1, 20001)])


def c_tube_mol(D: float, L: float, cb: float) -> float:
    """Molecular conductance of a circular tube C = (<v>/4)(pi D^2/4) tau (REF-CHIGGIATO Eqs. 19-21) [m^3/s]."""
    return cb / 4.0 * math.pi * D * D / 4.0 * santeler_tau(L, D / 2.0)


def c_annulus_mol(D_out: float, width: float, L: float, cb: float) -> float:
    """Molecular conductance of an annular channel, approximated as C = (<v>/4) A_annulus tau(L, R_h) with R_h = w
    (hydraulic diameter 2w, the lane-18 D_h convention; ASSUMED approximation, not a sourced annulus tau)."""
    D_in = D_out - 2.0 * width
    A = math.pi / 4.0 * (D_out ** 2 - D_in ** 2)
    return cb / 4.0 * A * santeler_tau(L, width)


def solve_upstream(p_down: float, Q: float, c_mol: float, d_char: float) -> tuple:
    """Upstream pressure p_up with Q = C_mol f(d p_mean) (p_up - p_down); bisection (deterministic, 200 steps)."""
    lo = p_down
    hi = p_down + Q / (c_mol * KNUDSEN_F_MIN) * 1.01 + 1e-12
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        g = c_mol * knudsen_f(d_char, 0.5 * (mid + p_down)) * (mid - p_down) - Q
        if g > 0:
            hi = mid
        else:
            lo = mid
    p_up = 0.5 * (lo + hi)
    return p_up, knudsen_f(d_char, 0.5 * (p_up + p_down))


def solve_manifold(p_z0: float, Q: float, c_ring_mol: float, bore: float, nf: int, delta: float) -> tuple:
    """Self-consistent manifold pressure for the uniformity rule: the hole-array conductance is set to its maximum
    C_h = 8 N_f^2 delta C_ring(p_man), with C_ring(p_man) = C_ring,mol f(bore p_man) (the ring conductance rises with
    pressure in the transitional range), and p_man - p_z0 = Q / C_h. Bisection (the right-hand side falls with p)."""
    lo, hi = p_z0, p_z0 + Q / (8.0 * nf * nf * delta * c_ring_mol * KNUDSEN_F_MIN) * 1.01 + 1e-12
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        g = (mid - p_z0) - Q / (8.0 * nf * nf * delta * c_ring_mol * knudsen_f(bore, mid))
        if g > 0:
            hi = mid
        else:
            lo = mid
    p = 0.5 * (lo + hi)
    return p, knudsen_f(bore, p)


# ------------------------------------------------------------------------------------------------------------------
# inputs
# ------------------------------------------------------------------------------------------------------------------
def check_pins() -> None:
    for rel, want in DECISION_PINS.items():
        got = sha256(rel)
        if got != want:
            raise SystemExit(f"REFUSED: {rel} sha256 {got} != pinned {want}")


def frozen_atmosphere() -> dict:
    meta = load(ATM_META_REL)
    raw = (REPO / ATM_REL).read_bytes()
    if hashlib.sha256(raw).hexdigest()[:16] != meta["sha256_16"]:
        raise SystemExit("REFUSED: frozen atmosphere CSV does not match its sha256_16 provenance")
    rows = {}
    with open(REPO / ATM_REL, newline="") as fh:
        for r in csv.DictReader(fh):
            rows[(round(float(r["alt_km"]), 3), round(float(r["f107"]), 3))] = {k: float(v) for k, v in r.items()}
    return {"meta": meta, "rows": rows}


LEVELS = {"low": 70.0, "mean": 150.0, "high": 230.0}  # feed_envelope section 2 mapping (assumed convention)
ALTS = (180.0, 200.0, 230.0)


def atmosphere_facts(atm: dict) -> dict:
    """Frozen-data facts used here: full-recombination O-element mass fraction (w_O + w_O2), free-stream w_O, density
    scale height H = -dh / d ln rho (central difference over +-2 km nodes), orbital period (Kepler, repo constants)."""
    rows = atm["rows"]
    out = []
    for h in ALTS:
        for lvl, f in LEVELS.items():
            r = rows[(h, f)]
            rp, rm = rows[(h + 2.0, f)], rows[(h - 2.0, f)]
            H = -4.0e3 / math.log(rp["rho"] / rm["rho"])
            out.append({"case": f"alt{int(h)}_{lvl}", "alt_km": h, "f107": f, "w_O_free_stream": sig(r["fO"]),
                        "w_O_element_full_recombination": sig(r["fO"] + r["fO2"]), "scale_height_km": sig(H / 1e3),
                        "T_orbit_min": sig(2 * math.pi * math.sqrt((R_EARTH + h * 1e3) ** 3 / MU_EARTH) / 60.0)})
    return {"cases": out,
            "w_O2_full_recombination_min": min(c["w_O_element_full_recombination"] for c in out),
            "w_O2_full_recombination_max": max(c["w_O_element_full_recombination"] for c in out),
            "w_O_free_stream_max": max(c["w_O_free_stream"] for c in out),
            "scale_height_km_min": min(c["scale_height_km"] for c in out),
            "scale_height_km_max": max(c["scale_height_km"] for c in out),
            "T_orbit_min_min": min(c["T_orbit_min"] for c in out)}


def w1_facts(w1: dict) -> dict:
    vo = w1["valve_outlet"]
    rec = []
    for cand in sorted(vo):
        for case, v in vo[cand].items():
            n = v["nominal"]
            rec.append({"candidate": cand, "case": case, "mdot": n["mdot_total_kgps"], "p_feed": n["p_feed_Pa"],
                        "T": n["T_feed_K"], "x_s": n["x_s"], "w_s": n["w_s"], "O_survival": n["O_survival"],
                        "lower": v["mdot_total_kgps_bracket"]["lower"], "upper": v["mdot_total_kgps_bracket"]["upper"],
                        "rpm": n["compressor_rpm"]})
    design = [r for r in rec if r["case"] == "alt200_mean"]
    per_cand = {}
    for cand in sorted(vo):
        rs = [r for r in rec if r["candidate"] == cand]
        per_cand[cand] = {
            "mdot_upper_max": max(r["mdot"] for r in rs), "mdot_upper_min": min(r["mdot"] for r in rs),
            "mdot_bracket_lower_min": min(r["lower"] for r in rs),
            "turndown_upper_bound_flows": sig(max(r["mdot"] for r in rs) / min(r["mdot"] for r in rs), 4),
            "turndown_incl_backflow_bracket": sig(max(r["upper"] for r in rs) / min(r["lower"] for r in rs), 4)}
    orich = max(rec, key=lambda r: r["x_s"]["O"])
    mfc = w1["mfc_range_requirement"]
    return {"records": rec, "design": design, "per_candidate": per_cand, "o_rich": orich,
            "mdot_min": mfc["mdot_min_kgps"], "mdot_max": mfc["mdot_max_kgps"],
            "setpoint_ladder": w1["design_axes"]["setpoint_ladder_Pa"],
            "rpm_min": min(r["rpm"] for r in rec), "rpm_max": max(r["rpm"] for r in rec),
            "T_min": min(r["T"] for r in rec), "T_max": max(r["T"] for r in rec)}


# ------------------------------------------------------------------------------------------------------------------
# design options (explicit; every value is an ASSUMED design option or an ANALOG illustration, never a Vyovrinda
# design value; the owning lanes replace them)
# ------------------------------------------------------------------------------------------------------------------
GEOMETRY_OPTIONS = {
    # bore / length of: line valve-outlet -> tee -> isolator -> IP-UP; PIM blank slot IP-UP -> IP-DN; H-1 stub IP-DN ->
    # manifold inlet. ASSUMED sizing options (no Vyovrinda drawing exists); routing lengths PENDING H2-7, PIM envelope
    # PENDING PMI-01, H-1 stub PENDING H2-1.
    "GEO-S": {"line_D_m": 0.006, "line_L_m": 1.0, "iso_D_m": 0.006, "iso_L_m": 0.1, "pim_D_m": 0.010,
              "pim_L_m": 0.15, "stub_D_m": 0.006, "stub_L_m": 0.05},
    "GEO-M": {"line_D_m": 0.010, "line_L_m": 1.0, "iso_D_m": 0.010, "iso_L_m": 0.1, "pim_D_m": 0.020,
              "pim_L_m": 0.15, "stub_D_m": 0.010, "stub_L_m": 0.05},
    "GEO-L": {"line_D_m": 0.016, "line_L_m": 1.0, "iso_D_m": 0.016, "iso_L_m": 0.1, "pim_D_m": 0.030,
              "pim_L_m": 0.15, "stub_D_m": 0.016, "stub_L_m": 0.05},
}
ANALOG_CHANNEL = {"device": "ECHT (extended-channel Hall thruster)", "outer_diameter_m": 0.100, "width_m": 0.010,
                  "length_m": 0.086, "source": "CLAUDE.md 'Superseded / withdrawn' (true ECHT: 86 mm long, 10 mm wide, "
                  "100 mm OD)", "evidence_class": "inferred",
                  "use": "ILLUSTRATION ONLY of the cold-flow back-pressure scale at HALL_INLET_Z0; never an H-1 design "
                         "value (HW-H1-03 forbids P5/ECHT as design-value sources); the H-1 channel is PENDING H2-1"}
RING = {"mean_diameter_m": 0.090, "mean_diameter_basis": "analog: ECHT mean channel diameter (100 mm OD - 10 mm), "
        "illustration only, PENDING H2-1", "bore_options_m": [0.004, 0.006, 0.008], "feed_points_options": [1, 2, 4],
        "hole_diameter_options_m": [0.0005, 0.001], "hole_plate_thickness_m": 0.001}
DIST_OPTIONS = {"DIST-A": (0.006, 2), "DIST-B": (0.008, 4)}  # ASSUMED: (ring bore m, feed points); middle / most permissive
UNIFORMITY = {"abs_dev_max": 0.05, "p2p_max": 0.10, "source": "REF-ROBERTS2024 (abstract; 'NASA standard acceptance "
              "criteria', primary source not named: verify)", "status": "PROPOSED for the owner (not an RFP value)"}
FLOW_POINTS = ["F-MIN", "F-DES-LO", "F-DES-HI", "F-MAX"]
T_POINTS = [300.0, 500.0]
VALVE_AUTHORITY_R = [1.0, 3.0]            # PROPOSED: C_valve,open / C_downstream at the maximum flow
RIPPLE_ATTENUATION = [0.1, 0.01]           # PROPOSED: plenum attenuation of compressor ripple at the valve inlet
VALVE_BANDWIDTH_HZ = [0.1, 1.0, 10.0]      # ASSUMED options until a valve class is selected
RIDE_THROUGH_S = [0.1, 1.0, 10.0]          # ASSUMED options (no requirement exists)
RIDE_THROUGH_DP_FRACTION = 0.10            # PROPOSED allowable plenum pressure sag during ride-through
ALT_EXCURSION_KM = [1.0, 5.0]              # ASSUMED altitude-keeping excursion (TBD - requires the mission profile)
GAMMA_O = [0.001, 0.01, 0.07, 0.14]        # REF-PAUL2023 values/class limits (quartz-class, class limit, SS, SS)
PLENUM_VOLUMES_M3 = [0.0005, 0.002, 0.01, 0.05]  # evaluation grid for tau, fill time and O survival (not a choice)


# ------------------------------------------------------------------------------------------------------------------
# computations
# ------------------------------------------------------------------------------------------------------------------
def compositions(atmf: dict, w1f: dict) -> dict:
    lo, hi = atmf["w_O2_full_recombination_min"], atmf["w_O2_full_recombination_max"]
    orich = w1f["o_rich"]
    comps = {
        "COMP-REC-LO": {"w": {"N2": 1.0 - lo, "O2": lo}, "basis": "full recombination, minimum O-element mass fraction "
                        "over the 9 frozen cases (A5 'delivered O2 mass fraction 0.42-0.60')", "evidence_class": "model-derived"},
        "COMP-REC-HI": {"w": {"N2": 1.0 - hi, "O2": hi}, "basis": "full recombination, maximum O-element mass fraction "
                        "over the 9 frozen cases", "evidence_class": "model-derived"},
        "COMP-W1-ORICH": {"w": dict(orich["w_s"]), "basis": f"W1 valve-outlet nominal with the highest atomic-O mole "
                          f"fraction ({orich['candidate']}/{orich['case']}, x_O {sig(orich['x_s']['O'], 4)}; chain "
                          f"recombination priors, see finding GP-F05)", "evidence_class": "model-derived (from assumed inputs)"},
        "COMP-N2": {"w": {"N2": 1.0}, "basis": "ground surrogate S-N2 (Phase 1 knee)", "evidence_class": "assumed"},
        "COMP-XE": {"w": {"Xe": 1.0}, "basis": "Xe ignition / transition feed through the same line (A5 operating "
                    "modes)", "evidence_class": "assumed"},
    }
    for c in comps.values():
        c["M_kg_per_mol"] = sig(mix_molar(c["w"]))
        c["w"] = {k: sig(v) for k, v in c["w"].items()}
    return comps


def flow_points(w1f: dict) -> dict:
    des = w1f["design"]
    return {
        "F-MIN": {"mdot_kgps": w1f["mdot_min"], "basis": "W1 mfc_range_requirement.mdot_min_kgps (backflow-inclusive "
                  "lower bracket; A4 MFC range 0.030 mg/s)"},
        "F-DES-LO": {"mdot_kgps": min(r["mdot"] for r in des), "basis": "W1 valve_outlet alt200_mean nominal, minimum "
                     "over the 4 closed candidates (upper-bound flow basis)"},
        "F-DES-HI": {"mdot_kgps": max(r["mdot"] for r in des), "basis": "W1 valve_outlet alt200_mean nominal, maximum "
                     "over the 4 closed candidates"},
        "F-MAX": {"mdot_kgps": w1f["mdot_max"], "basis": "W1 mfc_range_requirement.mdot_max_kgps (A4 3.14 mg/s; A5 "
                  "'<= ~3.2 mg/s under H_RAM')"},
    }


def pressure_budget(comps: dict, flows: dict) -> dict:
    """Cold-flow pressure budget, solved from vacuum (p = 0 downstream of the channel exit; facility background is a
    ground-only item) upstream to the plenum: channel (ANALOG illustration) -> distributor holes (sized by the
    uniformity rule) -> manifold ring -> H-1 stub (IP-DN) -> PIM slot (blank, illustrative) -> isolator + line (IP-UP
    <- IF-A5) -> metering valve (authority rule) -> plenum. Returns one row per (flow, composition, T, geometry)."""
    rows = []
    ch = ANALOG_CHANNEL
    for fk in FLOW_POINTS:
        mdot = flows[fk]["mdot_kgps"]
        for ck in ("COMP-REC-LO", "COMP-REC-HI", "COMP-W1-ORICH", "COMP-N2"):
            M = comps[ck]["M_kg_per_mol"]
            for T in T_POINTS:
                cb = cbar(T, M)
                Q = throughput(mdot, T, M)
                c_ch = c_annulus_mol(ch["outer_diameter_m"], ch["width_m"], ch["length_m"], cb)
                p_z0, f_ch = solve_upstream(0.0, Q, c_ch, 2.0 * ch["width_m"])
                for dk, (ring_bore, nf) in DIST_OPTIONS.items():
                    ring_len = math.pi * RING["mean_diameter_m"]
                    c_ring_mol = c_tube_mol(ring_bore, ring_len, cb)
                    p2p = min(UNIFORMITY["p2p_max"], 1.5 * UNIFORMITY["abs_dev_max"])
                    p_man, f_ring = solve_manifold(p_z0, Q, c_ring_mol, ring_bore, nf, p2p)
                    c_h = 8.0 * nf * nf * p2p * c_ring_mol * f_ring
                    dp_h = p_man - p_z0
                    row = {"flow": fk, "composition": ck, "T_K": T, "distributor": dk,
                           "mdot_mg_s": sig(mdot * 1e6, 5), "Q_Pa_m3_s": sig(Q),
                           "cbar_m_s": sig(cb, 5), "C_channel_mol_m3_s": sig(c_ch), "p_HALL_INLET_Z0_cold_Pa": sig(p_z0),
                           "Kn_channel": sig(mfp(max(p_z0, 1e-9), T) / (2 * ch["width_m"]), 4),
                           "knudsen_f_channel": sig(f_ch, 4), "C_holes_max_m3_s": sig(c_h),
                           "dp_holes_min_Pa": sig(dp_h), "p_manifold_Pa": sig(p_man),
                           "Kn_ring": sig(mfp(p_man, T) / ring_bore, 4), "geometries": {}}
                    for gk, g in GEOMETRY_OPTIONS.items():
                        p = p_man
                        segs = []
                        for name, D, L in (("H-1 stub IP-DN -> manifold", g["stub_D_m"], g["stub_L_m"]),
                                           ("PIM slot IP-UP -> IP-DN (blank, illustrative)", g["pim_D_m"], g["pim_L_m"]),
                                           ("gas isolator", g["iso_D_m"], g["iso_L_m"]),
                                           ("line tee/IF-A5 -> isolator", g["line_D_m"], g["line_L_m"])):
                            cm = c_tube_mol(D, L, cb)
                            p_up, f = solve_upstream(p, Q, cm, D)
                            segs.append({"segment": name, "D_m": D, "L_m": L, "C_mol_m3_s": sig(cm), "knudsen_f": sig(f, 4),
                                         "Kn_at_upstream_end": sig(mfp(p_up, T) / D, 4),
                                         "regime": regime(mfp(p_up, T) / D), "dp_Pa": sig(p_up - p)})
                            p = p_up
                        p_a5 = p
                        per_r = {}
                        for r in VALVE_AUTHORITY_R:
                            # C_valve,open = r * C_down, C_down = Q / p_A5 (incremental conductance of everything downstream)
                            c_down = Q / p_a5
                            dp_v = Q / (r * c_down)
                            per_r[f"r={r:g}"] = {"dp_valve_min_Pa": sig(dp_v), "p_plenum_min_Pa": sig(p_a5 + dp_v),
                                                 "C_valve_open_m3_s": sig(r * c_down),
                                                 "C_total_plenum_to_vacuum_m3_s": sig(Q / (p_a5 + dp_v))}
                        row["geometries"][gk] = {"segments": segs, "p_IF_A5_Pa": sig(p_a5),
                                                 "dp_IP_UP_to_IP_DN_blank_Pa": segs[1]["dp_Pa"], "valve": per_r}
                    rows.append(row)
    return {"rows": rows,
            "method": "cold-flow (no plasma) series solve from vacuum upstream; each segment Q = C_mol f(d p_mean) "
                      "(p_up - p_down) with C_mol from REF-CHIGGIATO Eqs. 19-21 (tube) or the annulus approximation, "
                      "f from REF-LEYBOLD2016 Eq. 1.27 (inferred transfer to other gases/temperatures); f_min over the "
                      f"tabulated range = {sig(KNUDSEN_F_MIN, 4)}",
            "channel_is_analog_illustration": ANALOG_CHANNEL["use"],
            "distributor_options": {k: {"ring_bore_m": v[0], "feed_points": v[1]} for k, v in DIST_OPTIONS.items()},
            "distributor_rule_used": "holes sized to the largest conductance the uniformity limit allows (smallest drop)"}


def uniformity_table(comps: dict, pb: dict) -> dict:
    """Azimuthal-uniformity sizing rule (model-derived; 1-D diffusion along the ring, uniform withdrawal by the
    injection holes, small deviation): for N_f equally spaced feed points the peak-to-peak manifold pressure deviation
    relative to the hole pressure drop is delta = C_h / (8 N_f^2 C_ring), C_ring = conductance of the full
    circumference as a straight tube at the manifold pressure (molecular x Leybold f). Parabolic profile: max
    |deviation from mean| = (2/3) delta, so the +-5 % criterion gives delta <= 0.075 (binding over 10 % p2p). The
    holes are set to the largest conductance the rule allows (smallest drop); manifold pressure solved
    self-consistently from the analog cold-flow back-pressure p_Z0 (illustration)."""
    M = comps["COMP-REC-LO"]["M_kg_per_mol"]
    delta = min(UNIFORMITY["p2p_max"], 1.5 * UNIFORMITY["abs_dev_max"])
    rows = []
    for r in pb["rows"]:
        if r["composition"] != "COMP-REC-LO" or r["flow"] == "F-MIN" or r["distributor"] != "DIST-A":
            continue
        T, Q, p_z0 = r["T_K"], r["Q_Pa_m3_s"], r["p_HALL_INLET_Z0_cold_Pa"]
        cb = cbar(T, M)
        for bore in RING["bore_options_m"]:
            c_ring = c_tube_mol(bore, math.pi * RING["mean_diameter_m"], cb)
            for nf in RING["feed_points_options"]:
                p_man, f = solve_manifold(p_z0, Q, c_ring, bore, nf, delta)
                c_h = 8.0 * nf * nf * delta * c_ring * f
                a_h = c_h / (cb / 4.0)
                holes = {}
                for dh in RING["hole_diameter_options_m"]:
                    tau = santeler_tau(RING["hole_plate_thickness_m"], dh / 2.0)
                    n = a_h / (math.pi * dh * dh / 4.0 * tau)
                    kn = mfp(p_man, T) / dh
                    holes[f"{dh * 1e3:g} mm"] = {"tau_hole": sig(tau, 4), "N_holes_max_molecular": int(math.floor(n)),
                                                 "Kn_hole": sig(kn, 3), "regime": regime(kn)}
                rows.append({"flow": r["flow"], "T_K": T, "ring_bore_m": bore, "feed_points": nf,
                             "p_Z0_cold_Pa": p_z0, "p_manifold_Pa": sig(p_man, 4), "dp_holes_Pa": sig(p_man - p_z0, 4),
                             "Kn_ring": sig(mfp(p_man, T) / bore, 3), "C_ring_m3_s": sig(c_ring * f),
                             "C_holes_max_m3_s": sig(c_h), "A_holes_equiv_thin_max_m2": sig(a_h),
                             "holes_for_max_C": holes})
    return {"rule": "delta_p2p = C_h / (8 N_f^2 C_ring) <= 0.075 (from +-5 %)", "composition": "COMP-REC-LO",
            "ring_mean_diameter_m": RING["mean_diameter_m"], "rows": rows,
            "note": "N_holes_max_molecular is the largest count of that hole size compatible with the limit if the "
                    "holes are free-molecular; where Kn_hole <= 0.5 a hole passes more than its molecular conductance, "
                    "so the count is an UPPER bound (fewer holes needed). Fewer/smaller holes raise the distributor "
                    "drop and the required plenum pressure. Cold flow only: the plasma-on distribution is not "
                    "predicted"}


def plenum_sizing(pb: dict, w1f: dict, atmf: dict) -> dict:
    """Plenum volume ranges from explicit requirements. RC model: plenum volume V fed by the compressor (ideal flow
    source, ASSUMED) and drained through the valve + downstream path with total conductance C_tot = Q / p_plenum
    (linear molecular chain); tau = V / C_tot."""
    # representative C_tot range over the budget rows (F-DES-LO..F-MAX, GEO-S..GEO-L, r=1 and r=3)
    ctots = []
    for row in pb["rows"]:
        if row["flow"] == "F-MIN":
            continue
        for g in row["geometries"].values():
            for v in g["valve"].values():
                ctots.append(v["C_total_plenum_to_vacuum_m3_s"])
    c_lo, c_hi = min(ctots), max(ctots)
    f_rot = sorted({sig(w1f["rpm_min"] / 60.0, 5), sig(w1f["rpm_max"] / 60.0, 5), 1000.0})
    ripple = []
    for f in f_rot:
        for a in RIPPLE_ATTENUATION:
            tau = math.sqrt(1.0 / (a * a) - 1.0) / (2.0 * math.pi * f)
            ripple.append({"f_ripple_Hz": f, "attenuation": a, "tau_min_s": sig(tau, 4),
                           "V_min_m3_at_C_tot_lo": sig(tau * c_lo, 4), "V_min_m3_at_C_tot_hi": sig(tau * c_hi, 4)})
    bw = []
    for fb in VALVE_BANDWIDTH_HZ:
        tau = 1.0 / (2.0 * math.pi * fb)
        bw.append({"f_valve_bw_Hz": fb, "tau_min_s": sig(tau, 4), "V_min_m3_at_C_tot_lo": sig(tau * c_lo, 4),
                   "V_min_m3_at_C_tot_hi": sig(tau * c_hi, 4)})
    ride = []
    for row in pb["rows"]:
        if row["composition"] != "COMP-REC-LO" or row["T_K"] != 300.0 or row["flow"] not in ("F-DES-HI", "F-MAX"):
            continue
        pbufs = {f"budget {row['distributor']} GEO-M r=1": row["geometries"]["GEO-M"]["valve"]["r=1"]["p_plenum_min_Pa"]}
        if row["distributor"] == "DIST-A":
            pbufs.update({f"W1 ladder {p:g} Pa": p for p in (min(w1f["setpoint_ladder"]), 0.3)})
        for label, pbuf in pbufs.items():
            for t in RIDE_THROUGH_S:
                V = row["Q_Pa_m3_s"] * t / (RIDE_THROUGH_DP_FRACTION * pbuf)
                ride.append({"flow": row["flow"], "pressure_basis": label, "p_plenum_Pa": pbuf, "t_ride_s": t,
                             "V_required_m3": sig(V, 4)})
    rb = [r for r in ride if r["pressure_basis"].startswith("budget")]
    rl = [r for r in ride if r["pressure_basis"].startswith("W1")]
    fill = []
    for V in PLENUM_VOLUMES_M3:
        fill.append({"V_m3": V, "tau_at_C_tot_hi_s": sig(V / c_hi, 4), "tau_at_C_tot_lo_s": sig(V / c_lo, 4),
                     "t99_fill_or_drain_at_C_tot_lo_s": sig(4.605 * V / c_lo, 4)})
    ram = []
    for c in atmf["cases"]:
        for dh in ALT_EXCURSION_KM:
            ram.append({"case": c["case"], "scale_height_km": c["scale_height_km"], "dh_km": dh,
                        "delta_rho_over_rho": sig(math.expm1(dh / c["scale_height_km"]), 4),
                        "T_orbit_min": c["T_orbit_min"]})
    tau_req_max = max(max(r["tau_min_s"] for r in ripple), max(r["tau_min_s"] for r in bw))
    return {
        "C_tot_range_m3_s": [c_lo, c_hi],
        "C_tot_basis": "Q / p_plenum over the cold-flow budget rows F-DES-LO..F-MAX, GEO-S/M/L, r = 1 and 3 (analog "
                       "channel illustration; PENDING H2-1)",
        "compressor_ripple": {"rows": ripple, "frequency_basis": "once-per-revolution frequency of the W1 chain-sized "
                              "machines (code-default rpm, assumed) and ~1 kHz DN100 turbomolecular pump rotation "
                              "(compressor_downselect EV-04, REF-CHIGGIATO2013 as cited there); blade-passing "
                              "harmonics are higher and filtered more; ripple amplitude TBD - requires the compressor "
                              "design (C1)", "formula": "|H| = 1/sqrt(1 + (2 pi f tau)^2) <= a => tau >= "
                              "sqrt(1/a^2 - 1)/(2 pi f)"},
        "valve_bandwidth": {"rows": bw, "rule": "plenum pole at or below the valve control bandwidth, tau >= "
                            "1/(2 pi f_bw), so disturbances the valve loop cannot follow are attenuated by the plenum",
                            "f_bw_status": "TBD - requires the metering-valve class selection (H3)"},
        "ride_through": {"rows": ride, "rule": "V = Q t_ride / dp_allow, dp_allow = 10 % of p_plenum (PROPOSED)",
                         "conclusion": (
                             "ride-through volume scales as 1/p_plenum: at the W1 setpoint-ladder pressures "
                             f"({min(w1f['setpoint_ladder']):g}-0.3 Pa) 1 s needs "
                             f"{sig(min(r['V_required_m3'] for r in rl if r['t_ride_s'] == 1.0), 3)}-"
                             f"{sig(max(r['V_required_m3'] for r in rl if r['t_ride_s'] == 1.0), 3)} m^3; at the cold-flow "
                             f"budget pressures 1 s needs {sig(min(r['V_required_m3'] for r in rb if r['t_ride_s'] == 1.0), 3)}-"
                             f"{sig(max(r['V_required_m3'] for r in rb if r['t_ride_s'] == 1.0), 3)} m^3 and 10 s "
                             f"{sig(min(r['V_required_m3'] for r in rb if r['t_ride_s'] == 10.0), 3)}-"
                             f"{sig(max(r['V_required_m3'] for r in rb if r['t_ride_s'] == 10.0), 3)} m^3. A plenum can "
                             "therefore bridge at most seconds of compressor interruption; longer interruptions are "
                             "handled by the dual-feed state machine (XE_FALLBACK, time-limited, A5) or by shutdown")},
        "ram_variation": {"rows": ram, "rule": "delta rho / rho = exp(dh/H) - 1 for an altitude excursion dh "
                          "(ASSUMED 1 and 5 km; TBD - requires the mission altitude profile); H from the frozen "
                          "dataset (orbit-averaged: within-orbit day/night and latitude variation is NOT in the frozen "
                          "data, TBD - requires an orbit-resolved producer, ICD IF-A0 dmdot_dt_kgps2 gap)",
                          "tau_required_max_s": tau_req_max,
                          "timescale_ratio_min": sig(atmf["T_orbit_min_min"] * 60.0 / 4.0 / tau_req_max, 4),
                          "conclusion": (
                              f"ram-flow variation evolves on quarter-orbit time scales (>= "
                              f"{sig(atmf['T_orbit_min_min'] / 4.0, 3)} min), at least "
                              f"{sig(atmf['T_orbit_min_min'] * 60.0 / 4.0 / tau_req_max, 3)} x the largest required "
                              f"plenum time constant ({sig(tau_req_max, 3)} s); a plenum sized to its requirement does "
                              "not filter it: ram variation sets the metering-valve / compressor operating range "
                              "(turndown), not the plenum volume; only plenums far above the minimum (tau of hundreds "
                              "of seconds, see fill_drain) approach orbital time scales")},
        "fill_drain": {"rows": fill, "formula": "tau = V / C_tot; 99 % in 4.6 tau (first-order RC)"},
        "volume_range": {
            "V_min_m3": sig(min(r["V_min_m3_at_C_tot_lo"] for r in ripple if r["attenuation"] == 0.1
                                and r["f_ripple_Hz"] == 1000.0), 4),
            "V_min_basis": "weakest requirement set: 1 kHz ripple, attenuation 0.1, lowest C_tot",
            "V_upper_of_minimum_m3": sig(max(max(r["V_min_m3_at_C_tot_hi"] for r in ripple),
                                             max(r["V_min_m3_at_C_tot_hi"] for r in bw)), 4),
            "V_upper_of_minimum_basis": "strongest requirement set on the grid: max(ripple at the lowest rotation "
                                        "frequency with a = 0.01, valve bandwidth 0.1 Hz) at the highest C_tot",
            "V_max_status": "TBD - requires the H2-7 envelope/mass allocation, the lane-14 atmosphere-admission time "
                            "(fill time 4.6 tau) and the owner's O-survival preference (GP-D03)",
            "status": "PRELIMINARY (derived from explicit PROPOSED/ASSUMED requirement values; the range narrows "
                      "when the compressor ripple, valve bandwidth and H-1 conductance are known)"},
    }


def o_recombination(pb: dict, atmf: dict, flows: dict, w1f: dict) -> dict:
    """Atomic-O survival in the plenum (cylinder L = D, ASSUMED shape), residence time t_res = V / C_tot with C_tot =
    Q / p_plenum. Wall-loss frequency: kinetic limit nu_kin = -ln(1 - gamma) <v_O> A_w / (4 V) (wall impingement,
    REF-CHIGGIATO Eq. 4); diffusion limit nu_D = D / Lambda^2 with 1/Lambda^2 = (2.405/R)^2 + (pi/L)^2 (fundamental
    diffusion mode of a finite cylinder) and D = lambda <v_O> / 3 (elementary kinetic-theory estimate, ASSUMED order of
    magnitude, verify); nu_eff = 1 / (1/nu_kin + 1/nu_D) (series combination, ASSUMED). Survival = exp(-nu_eff t_res).
    The kinetic-only survival is a LOWER bound on survival; the effective value accounts for diffusion limitation at
    transitional/viscous plenum pressures. Recombination heat P = (mdot w_O / M_O)(dH / 2), dH = 498.346 kJ per mol O2
    (REF-JANAF-O), with the free-stream w_O as an upper bound on the O reaching the gas path."""
    cases = []
    for r in pb["rows"]:
        if r["composition"] == "COMP-REC-LO" and r["flow"] in ("F-DES-LO", "F-DES-HI", "F-MAX") \
                and r["distributor"] == "DIST-B":
            cases.append({"label": f"{r['flow']} budget DIST-B GEO-M r=1", "T_K": r["T_K"], "Q": r["Q_Pa_m3_s"],
                          "p": r["geometries"]["GEO-M"]["valve"]["r=1"]["p_plenum_min_Pa"]})
            if r["flow"] == "F-DES-HI":
                cases.append({"label": "F-DES-HI at W1 setpoint 0.1 Pa (chain convention)", "T_K": r["T_K"],
                              "Q": r["Q_Pa_m3_s"], "p": 0.1})
    rows = []
    for c in cases:
        cb = cbar(c["T_K"], MOLAR["O"])
        lam = mfp(c["p"], c["T_K"])
        Dcoef = lam * cb / 3.0
        for V in PLENUM_VOLUMES_M3:
            Dm = (4.0 * V / math.pi) ** (1.0 / 3.0)
            Aw = 1.5 * math.pi * Dm * Dm
            t_res = V * c["p"] / c["Q"]
            inv_l2 = (2.405 / (Dm / 2.0)) ** 2 + (math.pi / Dm) ** 2
            nu_d = Dcoef * inv_l2
            surv_k, surv_e = {}, {}
            for g in GAMMA_O:
                nu_k = -math.log(1.0 - g) * cb * Aw / (4.0 * V)
                nu_e = 1.0 / (1.0 / nu_k + 1.0 / nu_d)
                surv_k[f"gamma={g:g}"] = sig(math.exp(-nu_k * t_res), 3)
                surv_e[f"gamma={g:g}"] = sig(math.exp(-nu_e * t_res), 3)
            rows.append({"case": c["label"], "T_K": c["T_K"], "p_plenum_Pa": c["p"], "V_m3": V,
                         "Kn_plenum": sig(lam / Dm, 3), "t_res_s": sig(t_res, 4), "nu_diffusion_per_s": sig(nu_d, 4),
                         "O_survival_kinetic_limit": surv_k, "O_survival_effective": surv_e})
    heat = []
    for fk in ("F-DES-LO", "F-DES-HI", "F-MAX"):
        mdot = flows[fk]["mdot_kgps"]
        P = mdot * atmf["w_O_free_stream_max"] / MOLAR["O"] * DH_REC_J_PER_MOL_O2 / 2.0
        heat.append({"flow": fk, "mdot_mg_s": sig(mdot * 1e6, 5), "w_O_upper": atmf["w_O_free_stream_max"],
                     "P_recombination_full_W": sig(P, 4)})
    budget = [r for r in rows if "budget" in r["case"]]
    best_budget = max(max(r["O_survival_effective"].values()) for r in budget)
    ladder = [r for r in rows if "W1 setpoint" in r["case"]]
    return {"method": "see o_recombination docstring (kinetic and diffusion limits; ASSUMED forms, verify)",
            "survival": rows, "heat": heat,
            "max_effective_survival_at_budget_pressures": best_budget,
            "effective_survival_at_W1_setpoint_gamma_0p001": [r["O_survival_effective"]["gamma=0.001"] for r in ladder],
            "conclusion": (
                "at the cold-flow budget plenum pressures the residence time is seconds and the largest effective "
                f"O survival on the grid is {sig(best_budget, 3)} (any wall class, including quartz-class gamma 1e-3): "
                "the plenum returns essentially all atomic O as O2, and the delivered feed is N2 + O2 at the A5 O2 "
                "mass fraction 0.42-0.60 (full recombination), which the ground surrogate S-O2E reproduces by "
                "construction. Only at the W1 chain convention (plenum ~0.1 Pa, short residence) can an inert lining "
                "keep a material O fraction. Recombination releases up to the tabulated heat in the compressor / "
                "plenum / line walls (demand to H2-5)")}


def xe_tie_in(comps: dict) -> dict:
    """Xe hold-up of the shared line downstream of the Xe tie-in (tee -> Z0) per Pa, and molecular line time constants
    tau = V / C for the Xe -> atmosphere transfer (model-derived; line + isolator + PIM blank + stub volumes)."""
    rows = []
    M = MOLAR["Xe"]
    for gk, g in GEOMETRY_OPTIONS.items():
        V = sum(math.pi * g[f"{k}_D_m"] ** 2 / 4.0 * g[f"{k}_L_m"] for k in ("line", "iso", "pim", "stub"))
        for T in T_POINTS:
            cb = cbar(T, M)
            C = 1.0 / sum(1.0 / c_tube_mol(g[f"{k}_D_m"], g[f"{k}_L_m"], cb) for k in ("line", "iso", "pim", "stub"))
            rows.append({"geometry": gk, "T_K": T, "V_shared_m3": sig(V, 4),
                         "m_Xe_holdup_kg_per_Pa": sig(V * M / (R_GAS * T), 4),
                         "tau_line_Xe_s": sig(V / C, 4)})
    hold = [r["m_Xe_holdup_kg_per_Pa"] for r in rows]
    taus = [r["tau_line_Xe_s"] for r in rows]
    return {"rows": rows, "conclusion": (
        f"the shared line holds {sig(min(hold), 3)}-{sig(max(hold), 3)} kg Xe per Pa: the gas-path dead volume is not a "
        "material term of the A6 Xe ledger (m_startup / m_transition are flow x time terms, docs/budgets/xe_ledger/). "
        f"Free-molecular line time constants for Xe are {sig(min(taus), 3)}-{sig(max(taus), 3)} s (an upper bound: "
        "at transitional pressures the conductance is higher), i.e. of the order of seconds, so the lane-14 "
        "transfer ramp and the Xe-to-atmosphere changeover at HALL_INLET_Z0 lag the valve commands by several line "
        "time constants (demand to lane 14 and PMI-02.R7)")}


# ------------------------------------------------------------------------------------------------------------------
# document
# ------------------------------------------------------------------------------------------------------------------
def P(pid, name, value, units, basis, source, evidence, status, rep, note=None):
    assert basis in BASES, basis
    assert rep in REPRESENTATIVENESS, rep
    assert evidence in EVIDENCE_CLASSES or evidence == "TBD" or evidence.startswith("model-derived"), evidence
    d = {"id": pid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence, "status": status, "representativeness": rep}
    if note:
        d["note"] = note
    return d


def build() -> dict:
    check_pins()
    a5 = load(A5_REL)
    w1 = load(W1_REL)
    atm = frozen_atmosphere()
    atmf = atmosphere_facts(atm)
    w1f = w1_facts(w1)
    comps = compositions(atmf, w1f)
    flows = flow_points(w1f)
    pb = pressure_budget(comps, flows)
    uni = uniformity_table(comps, pb)
    ps = plenum_sizing(pb, w1f, atmf)
    orc = o_recombination(pb, atmf, flows, w1f)
    xe = xe_tie_in(comps)

    # summary numbers used in the tables
    def rows_where(**kw):
        return [r for r in pb["rows"] if all(r[k] == v for k, v in kw.items())]
    p_z0_all = [r["p_HALL_INLET_Z0_cold_Pa"] for r in pb["rows"]]
    p_a5_all = [g["p_IF_A5_Pa"] for r in pb["rows"] for g in r["geometries"].values()]
    p_pl_all = [v["p_plenum_min_Pa"] for r in pb["rows"] for g in r["geometries"].values() for v in g["valve"].values()]
    p_pl_des = [v["p_plenum_min_Pa"] for r in pb["rows"] if r["flow"] in ("F-DES-LO", "F-DES-HI")
                for g in r["geometries"].values() for v in g["valve"].values()]
    dp_pim = [g["dp_IP_UP_to_IP_DN_blank_Pa"] for r in pb["rows"] for g in r["geometries"].values()]
    setpoints = w1f["setpoint_ladder"]
    ratio_min = min(p_pl_des) / max(setpoints[:4])
    ratio_max = max(p_pl_des) / min(setpoints)
    kn_line = [s["Kn_at_upstream_end"] for r in pb["rows"] for g in r["geometries"].values() for s in g["segments"]]
    regimes_line = {s["regime"] for r in pb["rows"] for g in r["geometries"].values() for s in g["segments"]}
    dist_ratio = [r["dp_holes_min_Pa"] / r["p_HALL_INLET_Z0_cold_Pa"] for r in pb["rows"] if r["flow"] != "F-MIN"]
    dp_h_a = [r["dp_holes_min_Pa"] for r in pb["rows"] if r["distributor"] == "DIST-A" and r["flow"] != "F-MIN"]
    dp_h_b = [r["dp_holes_min_Pa"] for r in pb["rows"] if r["distributor"] == "DIST-B" and r["flow"] != "F-MIN"]
    heat_max = max(h["P_recombination_full_W"] for h in orc["heat"])
    heat_des = [h["P_recombination_full_W"] for h in orc["heat"] if h["flow"].startswith("F-DES")]
    turndowns = {c: v for c, v in w1f["per_candidate"].items()}
    td_ub = [v["turndown_upper_bound_flows"] for v in turndowns.values()]
    td_bf = [v["turndown_incl_backflow_bracket"] for v in turndowns.values()]
    vr = ps["volume_range"]
    xe_hold = [r["m_Xe_holdup_kg_per_Pa"] for r in xe["rows"]]
    p_span_lo = sig(min(p_z0_all), 3)
    p_span_hi = sig(max(p_pl_all), 3)
    n_heads = math.ceil(math.log10(p_span_hi / p_span_lo) / 3.0)
    p_a5_budget = [min(p_a5_all), max(p_a5_all)]
    w01 = [r for r in orc["survival"] if "W1 setpoint" in r["case"] and r["V_m3"] == 0.002
           and r["T_K"] == 300.0][0]["O_survival_effective"]

    FR, TA, GO = REPRESENTATIVENESS
    PEND = lambda k: f"PENDING {PENDING_LANES[k]}"  # noqa: E731
    params = [
        P("H23-01", "flight atmospheric branch topology (compressor outlet -> isolation valve -> plenum -> metering "
          "valve -> IF-A5 -> Xe tie-in tee -> gas isolator -> IP-UP -> PIM slot -> IP-DN -> H-1 stub -> anode manifold "
          "-> distributor -> HALL_INLET_Z0)", "see topology", "-", "requirement",
          f"{A5_REL} architecture.atmospheric_branch / reserved_interface; {HW_REL} interface_planes; {ICD_REL} IF-A3..IF-A5",
          "assumed", "PRELIMINARY", FR,
          "the compressor-outlet isolation valve follows the compressor down-selection recommendation (stopped-rotor "
          "back-streaming protection, compressor_downselect recommendation.primary)"),
        P("H23-02", "delivered atmospheric flow range at IF-A5 (all closed W1 candidates, incl. backflow bracket)",
          [sig(w1f["mdot_min"] * 1e6, 4), sig(w1f["mdot_max"] * 1e6, 4)], "mg/s", "requirement",
          f"{W1_REL} mfc_range_requirement; {A4_REL} decisions.MFC_ranges", "model-derived", "PRELIMINARY", FR,
          "candidate range, not a flight truth (A4); upper bound with backflow excluded (W1 FC-01)"),
        P("H23-03", "delivered O2 mass fraction (full recombination) test range", [sig(atmf["w_O2_full_recombination_min"], 4),
          sig(atmf["w_O2_full_recombination_max"], 4)], "-", "requirement",
          f"{A5_REL} phase1_branch_decision.test_matrix (0.42-0.60); recomputed here from {ATM_REL} (w_O + w_O2)",
          "model-derived", "PRELIMINARY", FR),
        P("H23-04", "feed-gas temperature range used for sizing", [300.0, 500.0], "K", "derived",
          f"{W1_REL} finding FC-04 (chain clamp convention 300-500 K)", "assumed", "TBD - requires the H2-5 thermal "
          "network (plenum and line wall temperatures)", FR, "a convention, not a thermal result"),
        P("H23-05", "cold-flow back-pressure at HALL_INLET_Z0 (analog channel illustration)",
          [min(p_z0_all), max(p_z0_all)], "Pa", "analog", f"this script pressure_budget; {ANALOG_CHANNEL['source']}",
          "model-derived", PEND("H2-1"), FR, "ILLUSTRATION ONLY (ECHT-size channel, annulus approximation); "
          "plasma-on neutral pressure is not predicted"),
        P("H23-06", "pressure at IF-A5 (valve outlet) needed to push the flow through the downstream path, cold flow",
          [min(p_a5_all), max(p_a5_all)], "Pa", "derived", "this script pressure_budget (GEO-S/M/L, analog channel)",
          "model-derived", PEND("H2-1"), FR, "scales with the H-1 channel / distributor conductance"),
        P("H23-07", "minimum plenum pressure (valve authority r = 1..3), design-case flows", [min(p_pl_des), max(p_pl_des)],
          "Pa", "derived", "this script pressure_budget", "model-derived", PEND("H2-1"), FR,
          f"{sig(ratio_min, 3)}-{sig(ratio_max, 3)} x the W1 setpoint ladder values (finding GP-F01)"),
        P("H23-08", "Knudsen number range in the feed segments (line, isolator, PIM blank, stub)",
          [min(kn_line), max(kn_line)], "-", "derived", "REF-CHIGGIATO Eq. 10 / Table 7; this script",
          "model-derived", "PRELIMINARY", FR, "regimes present: " + "; ".join(sorted(regimes_line))),
        P("H23-09", "allowable pressure drop IP-UP -> IP-DN (pre-ionizer slot)", None, "Pa", "pending",
          "PMI-10 epsilon_p_band / delta_p_per_occupant_cold (TBD there)", "TBD", PEND("PMI"), FR,
          f"illustrative blank (bore 10-30 mm, 0.15 m) cold drop {sig(min(dp_pim), 3)}-{sig(max(dp_pim), 3)} Pa over "
          "the budget rows; every Pa allowed here raises the required plenum pressure one-for-one"),
        P("H23-10", "anode-manifold azimuthal uniformity requirement (cold flow)", [UNIFORMITY["abs_dev_max"],
          UNIFORMITY["p2p_max"]], "- (abs. deviation, peak-to-peak)", "analog", UNIFORMITY["source"], "inferred",
          "PRELIMINARY (PROPOSED for the owner)", FR),
        P("H23-11", "distributor sizing rule", "delta_p2p = C_h / (8 N_f^2 C_ring) <= 0.075", "-", "derived",
          "this script uniformity_table (1-D molecular diffusion along the ring)", "model-derived", "PRELIMINARY", FR),
        P("H23-12", "anode manifold ring mean diameter, bore, feed points", None, "m / m / -", "pending",
          "H-1 design release HW-H1-03", "TBD", PEND("H2-1"), FR,
          "evaluated here on 90 mm (analog) x bore 4/6/8 mm x 1/2/4 feed points"),
        P("H23-13", "plenum volume, lower end of the minimum-volume range", vr["V_min_m3"], "m^3", "derived",
          "this script plenum_sizing (ripple, attenuation 0.1 at 1 kHz)", "model-derived", "PRELIMINARY", FR),
        P("H23-14", "plenum volume, upper end of the minimum-volume range", vr["V_upper_of_minimum_m3"], "m^3",
          "derived", "this script plenum_sizing (ripple a = 0.01 at the chain rotation frequency / valve bandwidth "
          "0.1 Hz)", "model-derived", "PRELIMINARY", FR),
        P("H23-15", "plenum maximum volume", None, "m^3", "pending", "H2-7 envelope/mass; lane-14 admission time",
          "TBD", PEND("H2-7"), FR),
        P("H23-16", "plenum time constant tau = V / C_tot (evaluation grid)",
          [min(r["tau_at_C_tot_hi_s"] for r in ps["fill_drain"]["rows"]),
           max(r["tau_at_C_tot_lo_s"] for r in ps["fill_drain"]["rows"])], "s", "derived", "this script plenum_sizing",
          "model-derived", "PRELIMINARY", FR),
        P("H23-17", "compressor ripple frequency / amplitude", None, "Hz / -", "pending",
          f"{CMP_REL} (C1 LEADING_CANDIDATE_PENDING_PRIMARY_EVIDENCE, A4)", "TBD",
          "TBD - requires the C1 compressor design (blade count, rpm, outlet ripple)", FR,
          f"bracketed here by {sig(w1f['rpm_min'] / 60, 4)}-{sig(w1f['rpm_max'] / 60, 4)} Hz (chain, assumed) and "
          "1 kHz (EV-04)"),
        P("H23-18", "metering-valve control bandwidth", None, "Hz", "pending", "valve class selection (H3)", "TBD",
          "TBD - requires the metering-valve class selection", FR, "evaluated at 0.1 / 1 / 10 Hz (assumed)"),
        P("H23-19", "metering-valve conductance turndown, fixed plenum setpoint strategy (single candidate)",
          [min(td_ub), max(td_bf)], "- (flow ratio; conductance ratio is larger, see text)", "derived",
          f"{W1_REL} valve_outlet per candidate", "model-derived", "PRELIMINARY", FR,
          "flow turndown per candidate over the nine cases, upper-bound flows to backflow bracket"),
        P("H23-20", "plenum ride-through capability", "seconds at most (see plenum_sizing.ride_through)", "-",
          "derived", "this script plenum_sizing.ride_through", "model-derived", "PRELIMINARY", FR,
          "compressor interruptions handled by XE_FALLBACK (time-limited) or shutdown"),
        P("H23-21", "O recombination heat release in compressor / plenum / line (full recombination)",
          [min(heat_des), heat_max], "W", "derived", "REF-JANAF-O; this script o_recombination", "model-derived",
          PEND("H2-5"), FR, "location split depends on wall gamma (compressor vs plenum vs line)"),
        P("H23-22", "plenum / line wetted-wall O recombination coefficient class", None, "-", "pending",
          "REF-PAUL2023 (classes); owner decision GP-D03", "TBD", "TBD - requires the owner decision GP-D03 and "
          "coupon evidence at the flight wall temperature", FR),
        P("H23-23", "Xe hold-up of the shared line (tee -> Z0)", [min(xe_hold), max(xe_hold)], "kg/Pa", "derived",
          "this script xe_tie_in", "model-derived", "PRELIMINARY", FR),
        P("H23-24", "ground feed (FS-C: MFCs, bottles, single mixing point, isolator, manifold manometer)",
          "per HW-FS-01..07", "-", "requirement", f"{HW_REL} requirements HW-FS-01..07", "assumed", "PRELIMINARY", GO,
          "replaces compressor + plenum + metering valve on the ground; the ground IF-A5 analog is the manifold "
          "pressure upstream of IP-UP"),
        P("H23-25", "H-1 anode-manifold static-pressure tap (cold-flow uniformity and budget closure)", "1-3 taps",
          "-", "derived", "REF-REID2007 p. 7 (cold-flow probe practice); this lane", "inferred",
          PEND("H2-6"), TA, "must not change the flow path; blanked or identical in every arm"),
        P("H23-26", "feed-path pressure span to be measured on the H-1 ground fixture (cold flow, all taps)",
          [p_span_lo, p_span_hi], "Pa",
          "derived", "this script pressure_budget; REF-LEYBOLD2016 Sec. 3.2.2.4 pp. 78-79 (capacitance diaphragm "
          "gauges: three decades per sensor, used down to 1e-3 mbar = 0.1 Pa)", "model-derived", "PRELIMINARY", GO,
          f"{n_heads} three-decade heads cover the span; values below 0.1 Pa (HALL_INLET_Z0 at the lowest flows, "
          "W1 0.05 Pa setpoints) sit where the gauge uncertainty rises; flight sensor class TBD (proposal gap)"),
        P("H23-27", "gas isolator (voltage break) position and rating", "upstream of IP-UP, downstream of the Xe tee",
          "-", "requirement", f"{HW_REL} HW-FS-06", "assumed", "TBD - requires the H2-4 discharge-voltage rating plus "
          "margin", FR),
        P("H23-28", "wetted-material set (O2 / O service)", "see materials table", "-", "analog",
          "REF-PAUL2023; REF-CIFALI2011 as recorded; HW-FS-07; HW-H1-05", "inferred", "PRELIMINARY", FR),
    ]

    topology = {
        "flight_nodes": [
            {"id": "N0", "name": "compressor outlet (C1 turbomolecular-type first stage + optional drag stage)",
             "plane": "IF-A3", "owner": "compressor lane (docs/architecture_comparison/compressor_downselect/)",
             "representativeness": FR},
            {"id": "V0", "name": "compressor-outlet isolation valve (stopped-rotor back-streaming protection)",
             "plane": None, "owner": "H2-3", "representativeness": FR},
            {"id": "N1", "name": "buffer/plenum (atmospheric gas chamber)", "plane": "IF-A3 -> IF-A4",
             "owner": "H2-3", "representativeness": FR},
            {"id": "V1", "name": "atmospheric metering valve (variable conductance)", "plane": "IF-A4 -> IF-A5",
             "owner": "H2-3", "representativeness": FR},
            {"id": "N2", "name": "valve outlet = thruster boundary, atmospheric port", "plane": "IF-A5",
             "owner": "H2-3", "representativeness": FR},
            {"id": "T1", "name": "Xe tie-in tee (single mixing point; Xe anode line from the Xe metering)",
             "plane": "IF-X2 joins here", "owner": "H2-3 (tee) / Xe branch (line)", "representativeness": FR},
            {"id": "I1", "name": "gas isolator (voltage break)", "plane": None, "owner": "H2-3 / H2-4 rating",
             "representativeness": FR},
            {"id": "N3", "name": "module inlet plane", "plane": "IP-UP", "owner": "PMI ICD", "representativeness": FR},
            {"id": "M1", "name": "pre-ionizer module slot: PIM-0 blank (hall_only) / PIM-RF / PIM-ECR",
             "plane": "IP-UP -> IP-DN", "owner": "PMI ICD", "representativeness": FR,
             "note": "A5 reserved interface; RF not baseline flight hardware, ECR alternate test module only"},
            {"id": "N4", "name": "H-1 rear inlet flange", "plane": "IP-DN", "owner": "H2-1 / PMI",
             "representativeness": FR},
            {"id": "D1", "name": "H-1 stub and anode manifold ring (feed points N_f)", "plane": None, "owner": "H2-1",
             "representativeness": FR},
            {"id": "D2", "name": "gas distributor (orifice array / baffle / porous stage)", "plane": "HALL_INLET_Z0",
             "owner": "H2-1 (H-1 part, identical in every arm, HW-H1-06)", "representativeness": FR},
        ],
        "ground_substitution": {
            "replaced_upstream_of_IP_UP": "FS-C: N2 / O2 / Xe-anode / Xe-cathode MFCs from bottles, single mixing point "
                                          "and manifold, gas isolator, line to IP-UP, capacitance manometer at the "
                                          "manifold (HW-FS-01..07); no compressor, plenum or flight metering valve",
            "representativeness": GO,
            "consequence": "the H-1 test article reproduces everything from IP-UP to HALL_INLET_Z0 (flight-"
                           "representative); the plenum and metering valve are qualified separately (h4 inputs)"},
        "cathode_gas": "own line, never crosses HALL_INLET_Z0 and never enters a module (HW-C1-04, PMI-02.R2); "
                       "owned by H2-2",
        "architecture_independence": "one topology for hall_only / rf_hall / ecr_hall; only the occupant of the slot "
                                     "IP-UP -> IP-DN changes (PMI-01)",
    }

    measurement = [
        {"quantity": "P_feed (bus_power_boundary_v1 mandatory field)", "definition_plane": "IF-A5 (valve outlet)",
         "flight_location": "static tap at N2 (valve outlet), upstream of the Xe tee", "flight_sensor":
         "capacitance diaphragm class (gas independent, REF-LEYBOLD2016); flight unit TBD", "ground_location":
         "FS-C manifold capacitance manometer upstream of IP-UP (HW-FS-04) = ground IF-A5 analog",
         "INS": ["INS-06"], "also": "PMI-07.R1 module source-chamber port; H23-25 anode-manifold tap (proposed)",
         "note": "the W1 chain's P_feed is the pressure upstream of ONE lumped restriction (valve + line + "
                 "distributor); in hardware the drops are distinct and P_feed must be read at IF-A5 (finding GP-F02)"},
        {"quantity": "T_feed (mandatory field)", "definition_plane": "IF-A5",
         "flight_location": "line-wall RTD/thermocouple at N2 and on the plenum wall", "ground_location":
         "INS-07 line thermocouple at the IF-A5-analog plane; line heater state recorded",
         "INS": ["INS-07", "INS-17"], "note": "gas temperature taken equal to wall temperature after many wall "
         "collisions (N_wall >> 1 in the plenum; thermal accommodation assumed ~1, verify); inferred, not measured"},
        {"quantity": "x_s / w_s (mandatory field)", "definition_plane": "IF-A5",
         "flight_location": "no baseline composition sensor: inferred from the frozen atmosphere + measured wall "
                            "recombination class (proposal-only documentation gap GP-G01)",
         "ground_location": "MFC flow ratio (INS-05, one MFC per pure gas) defines x_s; RGA (INS-11) qualitative "
                            "check; atomic O cannot be bottled (W1 section 7)", "INS": ["INS-05", "INS-11"],
         "note": "O2 mass fraction 0.42-0.60 (A5) under full recombination; see o_recombination"},
        {"quantity": "mdot_s (mandatory field)", "definition_plane": "IF-A5",
         "flight_location": "derived from calibrated valve conductance x measured dp (V1) or from compressor state; "
                            "no flight flowmeter class identified for 0.03-3.14 mg/s at the IF-A5 pressure range "
                            "(TBD)",
         "ground_location": "INS-05 MFCs (A4: at least three overlapping ranges per gas path)", "INS": ["INS-05"]},
        {"quantity": "plenum pressure (control variable)", "definition_plane": "N1 (IF-A4)",
         "flight_location": "plenum capacitance gauge (valve-loop feedback)", "ground_location": "not present (GO)",
         "INS": []},
        {"quantity": "manifold / distributor pressure", "definition_plane": "D1", "flight_location": "none (flight)",
         "ground_location": "H23-25 tap(s) on H-1 (test-article-only) + cold-flow probe sweep at the channel "
                            "(REF-REID2007 p. 7 practice)", "INS": [], "note": "PENDING H2-6 port allocation"},
    ]

    materials = [
        {"part": "plenum and line walls", "option": "stainless steel / titanium", "O_behaviour":
         "semi-catalytic, gamma 0.04-0.16 rising with O exposure (REF-PAUL2023)", "consequence":
         "near-complete O -> O2 recombination; heat release in the walls", "status": "option"},
        {"part": "plenum and line walls", "option": "anodized aluminium", "O_behaviour":
         "gamma 0.4-0.6 reported at 1 Pa, RT (one report, 'very large', REF-PAUL2023); the repository prior "
         "Al2O3_anodised is low-gamma (abep_sim/materials.py, unsourced)", "consequence":
         "catalytic in the accessed measurement; conflicts with the chain prior (finding GP-F05)", "status": "option"},
        {"part": "plenum liner (only if O is to be preserved)", "option": "fused quartz / silica-class",
         "O_behaviour": "inert, gamma ~1e-3 (REF-PAUL2023)", "consequence": "partial O survival in small plenums "
         "only; brittle liner, mounting TBD", "status": "option"},
        {"part": "seals", "option": "metal seals preferred; PTFE", "O_behaviour": "PTFE gamma ~6e-4 (REF-PAUL2023); "
         "AO erosion / outgassing of polymers TBD (no source accessed in this lane)", "consequence": "TBD",
         "status": "TBD"},
        {"part": "any wetted part", "option": "silver", "O_behaviour": "most catalytic metal surveyed "
         "(REF-PAUL2023); repository prior 'AO catastrophic' (materials.py, unsourced)", "consequence":
         "EXCLUDED from wetted parts (PROPOSED)", "status": "PROPOSED exclusion"},
        {"part": "anode / gas distributor (H-1)", "option": "oxidation-resistant material/coating", "O_behaviour":
         "PPS1350-TSD anode 'rusty' after N2/O2 (REF-CIFALI2011 as recorded, HW-H1-05)", "consequence":
         "selection with cited O2 oxidation evidence (HWQ-08); owned by H2-1", "status": PEND("H2-1")},
        {"part": "ground O2 supply (bottles, regulators, MFCs)", "option": "O2-service cleaning", "O_behaviour":
         "high-pressure O2 on the ground side only", "consequence": "cleaning standard TBD (HW-FS-07, facility "
         "safety case)", "status": "TBD"},
    ]

    interface_demands = [
        {"from": "H2-3", "to": "compressor lane (C1; docs/architecture_comparison/compressor_downselect/)",
         "quantity": "compressor outlet (plenum) pressure at design flows, cold-flow analog illustration",
         "value": [min(p_pl_des), max(p_pl_des)], "units": "Pa", "status": f"{PEND('H2-1')} (channel conductance)"},
        {"from": "H2-3", "to": "compressor lane", "quantity": "outlet ripple amplitude and frequency; outlet "
         "back-conductance (ideal-source assumption here)", "value": None, "units": "- / Hz / m^3 s^-1",
         "status": "TBD - requires the C1 design"},
        {"from": "H2-3", "to": "compressor lane", "quantity": "outlet isolation valve (stopped-rotor back-streaming)",
         "value": "required", "units": "-", "status": "PRELIMINARY"},
        {"from": "H2-3", "to": "H2-1 (H-1 CI, HALL_INLET_Z0)", "quantity": "channel + distributor cold-flow "
         "conductance; manifold ring bore, mean diameter, feed points, hole count/diameter", "value": None,
         "units": "m^3 s^-1 / m / -", "status": PEND("H2-1")},
        {"from": "H2-1", "to": "H2-3", "quantity": "distributor uniformity acceptance (cold flow)", "value":
         [UNIFORMITY["abs_dev_max"], UNIFORMITY["p2p_max"]], "units": "-", "status": "PRELIMINARY (PROPOSED)"},
        {"from": "H2-3", "to": "PMI ICD (PMI-02, PMI-10)", "quantity": "allowable cold-flow dp IP-UP -> IP-DN at the "
         "W1 grid flows (epsilon_p band)", "value": [min(dp_pim), max(dp_pim)], "units": "Pa",
         "status": f"{PEND('PMI')} (illustrative blank range given)"},
        {"from": "H2-3", "to": "PMI ICD (PMI-02.R7)", "quantity": "occupant free volume -> line time constant for the "
         "Xe -> atmosphere transfer", "value": None, "units": "m^3", "status": PEND("PMI")},
        {"from": "H2-3", "to": "H2-4 (PPU/bus; bus_power_boundary_v1 flow_control, thermal_control)", "quantity":
         "metering-valve drive power, isolation-valve power, plenum/line heater power (T_feed conditioning)",
         "value": None, "units": "W", "status": "TBD - requires the valve class and the H2-5 thermal network"},
        {"from": "H2-3", "to": "H2-4", "quantity": "gas-isolator voltage rating", "value": None, "units": "V",
         "status": "TBD - requires the discharge-voltage rating plus margin (HW-FS-06)"},
        {"from": "H2-3", "to": "H2-5 (thermal network)", "quantity": "O recombination heat in compressor / plenum / "
         "line walls (full recombination, upper bound)", "value": [min(heat_des), heat_max], "units": "W",
         "status": "PRELIMINARY"},
        {"from": "H2-5", "to": "H2-3", "quantity": "plenum / line wall temperature range (sets T_feed)", "value": None,
         "units": "K", "status": PEND("H2-5")},
        {"from": "H2-3", "to": "H2-6 (diagnostics + fixture)", "quantity": "pressure taps: FS-C manifold (INS-06), "
         "H-1 anode manifold (H23-25), module source-chamber port (PMI-07); T_feed thermocouple (INS-07); RGA feed "
         "sample (INS-11)", "value": None, "units": "-", "status": PEND("H2-6")},
        {"from": "H2-3", "to": "H2-6", "quantity": "pressure span to be measured (cold flow)", "value":
         [p_span_lo, p_span_hi], "units": "Pa",
         "status": "PRELIMINARY"},
        {"from": "H2-3", "to": "H2-7 (mechanical/BOM; mass_bom atmospheric_gas_chamber, atmospheric_valve)",
         "quantity": "plenum volume range (minimum-volume range) and line routing lengths", "value":
         [vr["V_min_m3"], vr["V_upper_of_minimum_m3"]], "units": "m^3", "status": "PRELIMINARY"},
        {"from": "H2-7", "to": "H2-3", "quantity": "plenum envelope / mass allocation (sets V_max)", "value": None,
         "units": "m^3 / kg", "status": PEND("H2-7")},
        {"from": "H2-3", "to": "H2-2 (cathode integration)", "quantity": "cathode Xe line kept separate from the "
         "anode path; no shared plenum", "value": "separate", "units": "-", "status": "PRELIMINARY"},
        {"from": "H2-3", "to": "Xe ledger (docs/budgets/xe_ledger/)", "quantity": "shared-line Xe hold-up",
         "value": [min(xe_hold), max(xe_hold)], "units": "kg/Pa", "status": "PRELIMINARY"},
        {"from": "H2-3", "to": "lane-14 dual-feed state machine (schemas/controls/dual_feed_state_machine_v1.json)",
         "quantity": "plenum fill time (4.6 tau) before ATMOSPHERE_ADMISSION; compressor-interruption handling via "
         "XE_FALLBACK", "value": None, "units": "s", "status": "TBD - requires V and the H-1 conductance"},
        {"from": "H2-3", "to": "intake / filter (docs/interfaces/UPSTREAM_ICD.md IF-A1/IF-A2)", "quantity":
         "no direct demand: the gas path starts at the compressor outlet; the filter contaminant flow (IF-A2 gap) "
         "is a plenum/valve contamination input", "value": None, "units": "kg s^-1", "status": "TBD - requires the "
         "filter model (ICD G-01)"},
    ]

    hard = {
        "result": "none found",
        "checked": [
            {"id": "HI-01", "what": "pressure budget: can a compressor outlet feed the path?", "finding":
             f"cold-flow plenum pressure for an ECHT-size channel is {sig(ratio_min, 3)}-{sig(ratio_max, 3)} x the "
             "W1 setpoint ladder at the design-case flows; the required compression ratio rises by the same factor "
             "and exceeds the 0.1 Pa TMP molecular-regime limit (EV-03), so a drag stage behind the blades is "
             "needed (already an option in C1)", "evidence_class": "model-derived (analog geometry)", "veto": False,
             "why_not": "not evidenced for H-1: the channel/distributor conductance is PENDING H2-1 and the plasma-on "
                        "neutral pressure is not predicted; measured cold-flow manifold pressure (S1a) closes it"},
            {"id": "HI-02", "what": "plenum ride-through", "finding": "a plenum bridges at most seconds (GP-F03)",
             "evidence_class":
             "model-derived", "veto": False, "why_not": "A5 does not require atmospheric storage; interruptions go to "
             "time-limited XE_FALLBACK or shutdown (A5 operating_modes)"},
            {"id": "HI-03", "what": "O2 / atomic-O materials compatibility", "finding": "inert and semi-catalytic "
             "wall options exist (REF-PAUL2023); anode oxidation is H2-1's selection", "evidence_class": "inferred",
             "veto": False, "why_not": "no evidence that no compatible material exists"},
            {"id": "HI-04", "what": "flight metering valve for 0.03-3.14 mg/s at IF-A5 pressures of "
             f"{sig(p_a5_budget[0], 3)}-{sig(p_a5_budget[1], 3)} Pa (cold-flow budget)", "finding": "no flight-qualified "
             "variable-conductance valve class identified in accessed sources", "evidence_class": "TBD",
             "veto": False, "why_not": "absence of an accessed source is not evidence of impossibility; H3 item"},
            {"id": "HI-05", "what": "azimuthal uniformity vs pressure budget", "finding": (
                "the uniformity rule sets a distributor drop of "
                f"{sig(min(dist_ratio), 3)}-{sig(max(dist_ratio), 3)} x the analog channel back-pressure at "
                f"F-DES-LO..F-MAX (DIST-A {sig(min(dp_h_a), 3)}-{sig(max(dp_h_a), 3)} Pa, DIST-B "
                f"{sig(min(dp_h_b), 3)}-{sig(max(dp_h_b), 3)} Pa): the distributor, not the channel or the line, "
                "dominates the cold-flow budget; larger ring bore and more feed points (or multi-stage baffles) "
                "reduce it"), "evidence_class": "model-derived", "veto": False,
             "why_not": "geometric options exist; the distributor is an H2-1 design choice"},
        ],
    }

    blockers = [
        {"blocker": 1, "how": "defines where P_feed / T_feed / x_s of the actual atmospheric feed state are measured; "
         "shows that a catalytic gas path delivers N2 + O2 at the A5 0.42-0.60 O2 mass fraction, which the ground "
         "surrogate S-O2E reproduces (design option GP-D03), and that P_feed at IF-A5 depends on the H-1 "
         "conductance (a covariate to record in Phase 1). Does not assess sustainment."},
        {"blocker": 2, "how": "the gas path is common to hall_only / rf_hall / ecr_hall; its flow_control and "
         "thermal_control loads enter P_bus identically; only the IP-UP -> IP-DN occupant differs (PMI-10 cold-flow "
         "equivalence). Does not assess RF/ECR benefit."},
        {"blocker": 3, "how": "Xe tie-in downstream of the metering valve, upstream of the isolator; shared-line "
         "hold-up ~1e-8 kg/Pa (negligible for the ledger); the cathode Xe line stays separate. Does not set any Xe "
         "quantity (A6 not_authorized)."},
    ]

    m16 = [
        {"a5_subsystem": "buffer/plenum", "m16_row_draft_id": f"SM-ATM-04 ({PEND('M16')})",
         "matured_by_this_lane": "topology, volume range from explicit requirements, tau, O recombination, "
         "materials options", "proposed_state": "BLOCKED", "blocking_item": "C1 compressor outlet characteristic "
         "(outlet pressure capability, ripple amplitude/frequency) needed to close the minimum volume and the "
         "plenum pressure", "rollup": "hardware-definition blocker"},
        {"a5_subsystem": "atmospheric metering valve", "m16_row_draft_id": f"SM-ATM-05 ({PEND('M16')})",
         "matured_by_this_lane": "function (plenum-pressure regulation vs fixed orifice), conductance range, "
         "authority rule, bandwidth requirement, sensor class", "proposed_state": "BLOCKED",
         "blocking_item": "no identified variable-conductance valve class for 0.03-3.14 mg/s at the cold-flow "
         f"IF-A5 pressures ({sig(p_a5_budget[0], 3)}-{sig(p_a5_budget[1], 3)} Pa) (H3 survey needed)",
         "rollup": "procurement blocker"},
        {"a5_subsystem": "sensors/diagnostics", "m16_row_draft_id": f"SM-SUP-04 ({PEND('M16')})",
         "matured_by_this_lane": "P_feed / T_feed / x_s measurement locations and ranges; H-1 manifold tap",
         "proposed_state": "RUNNING", "blocking_item": None, "rollup": None},
        {"a5_subsystem": "extended-channel Hall discharge chamber/accelerator", "m16_row_draft_id":
         f"SM-PROP-01 ({PEND('M16')})", "matured_by_this_lane": "distributor sizing rule and uniformity criterion "
         "(input only; H2-1 owns the design)", "proposed_state": "RUNNING", "blocking_item": None, "rollup": None},
        {"a5_subsystem": "compressor", "m16_row_draft_id": f"SM-ATM-03 ({PEND('M16')})", "matured_by_this_lane":
         "outlet-side demands only (pressure, isolation valve, ripple)", "proposed_state": "not proposed by this lane",
         "blocking_item": None, "rollup": None},
    ]

    h3 = [
        {"item": "atmospheric metering valve (variable conductance, flight-representative)", "long_lead": True,
         "spec_level_needed": "fully-open conductance >= r x C_down at 3.14 mg/s (r = 1-3 PROPOSED); conductance "
         "turndown per the chosen control strategy; bandwidth >= f_bw; internal leak; O2/O-compatible wetted "
         "materials; drive power", "reference_data": "published catalog/datasheet data only; no supplier contact",
         "status": "TBD - requires H2-1 conductance and the control-strategy decision GP-D01"},
        {"item": "compressor-outlet isolation valve", "long_lead": True, "spec_level_needed": "open conductance >> "
         "plenum C_tot; closure on rotor deceleration; O2/O compatible", "status": "PRELIMINARY"},
        {"item": "capacitance diaphragm gauges (ground FS-C manifold, H-1 manifold tap, flight-like plenum)",
         "long_lead": False, "spec_level_needed": f"gas-type independent; span {p_span_lo}-{p_span_hi} Pa needs "
         f"{n_heads} overlapping three-decade heads (REF-LEYBOLD2016 pp. 78-79); below 0.1 Pa uncertainty rises",
         "status": "PRELIMINARY"},
        {"item": "MFCs (ground)", "long_lead": True, "spec_level_needed": "A4: 0.030-3.14 mg/s, >= 3 overlapping "
         "ranges per gas path, calibrated on each gas (HW-FS-01, INS-05)", "status": "PRELIMINARY (A4)"},
        {"item": "gas isolator", "long_lead": True, "spec_level_needed": "bore >= line bore option; voltage rating "
         "TBD (H2-4); O2-compatible", "status": "TBD"},
        {"item": "plenum vessel (+ optional inert liner)", "long_lead": False, "spec_level_needed": "volume within "
         "the minimum-volume range; wall material per GP-D03", "status": "PRELIMINARY"},
    ]

    h4 = [
        {"stage": "S1a", "measure": "cold-flow manifold pressure vs flow on N2, O2 mix and Xe with PIM-0 and each "
         "module (PMI-10); H-1 manifold tap pressure", "closes": ["H23-05", "H23-06", "H23-07", "H23-09"]},
        {"stage": "S1a", "measure": "cold-flow azimuthal sweep at the channel (probe, REF-REID2007 p. 7 practice)",
         "closes": ["H23-10", "H23-11", "H23-12"]},
        {"stage": "S1a", "measure": "line/manifold step response (flow step -> manifold pressure) to measure tau",
         "closes": ["H23-16", "H23-23"]},
        {"stage": "S1a", "measure": "T_feed thermocouple vs line heater state; gauge temperature", "closes":
         ["H23-04"]},
        {"stage": "S1", "measure": "repeatability of manifold pressure at every grid flow after remount", "closes":
         ["H23-09"]},
        {"stage": "S1b", "measure": "manifold / module pressure with the discharge on (recorded, never matched)",
         "closes": ["H23-05 (plasma-on context)"]},
        {"stage": "Phase 1", "measure": "P_feed (INS-06) and T_feed (INS-07) as covariates at every point",
         "closes": ["H23-06"]},
        {"stage": "component test (outside H-1)", "measure": "plenum + metering valve + compressor breadboard: ripple "
         "transfer, valve bandwidth, O recombination on the selected wall (coupon)", "closes":
         ["H23-13", "H23-14", "H23-17", "H23-18", "H23-21", "H23-22"]},
    ]

    findings = [
        {"id": "GP-F01", "finding": f"the cold-flow plenum pressure needed to push design-case flows through an "
         f"ECHT-size channel plus a uniform distributor and the feed path is {sig(min(p_pl_des), 3)}-"
         f"{sig(max(p_pl_des), 3)} Pa, i.e. {sig(ratio_min, 3)}-{sig(ratio_max, 3)} x the W1 setpoint ladder "
         "(0.05-0.3 Pa); the compressor required compression ratio scales by the same factor", "evidence_class":
         "model-derived (analog illustration)", "handling": "demand to the compressor lane; closes with the H-1 "
         "conductance (H2-1) and the S1a cold-flow data"},
        {"id": "GP-F02", "finding": "the W1 chain lumps valve, line and distributor into one restriction, so its "
         "P_feed is a reservoir pressure; in hardware P_feed must be read at IF-A5 and differs from the manifold "
         "and HALL_INLET_Z0 pressures", "evidence_class": "inferred", "handling": "measurement map; INS-06 location"},
        {"id": "GP-F03", "finding": ps["ride_through"]["conclusion"], "evidence_class":
         "model-derived", "handling": "state machine handles interruptions (XE_FALLBACK, time-limited)"},
        {"id": "GP-F04", "finding": ps["ram_variation"]["conclusion"], "evidence_class": "model-derived",
         "handling": "valve turndown requirement H23-19"},
        {"id": "GP-F05", "finding": (
            "the W1 chain's valve-outlet x_O 0.44-0.65 (chain O_survival "
            f"{sig(min(r['O_survival'] for r in w1f['records']), 3)}-{sig(max(r['O_survival'] for r in w1f['records']), 3)}) "
            "rests on repository recombination priors (Al2O3_anodised low gamma, unsourced); the accessed review "
            "reports gamma 0.4-0.6 for anodized aluminium (one report) and 0.04-0.16 for steels. With this lane's "
            "model at the chain convention (0.1 Pa, 2 L plenum, 300 K) steel-class gamma 0.07 / 0.14 gives O survival "
            f"{w01['gamma=0.07']} / {w01['gamma=0.14']} in the plenum alone, and at the cold-flow budget pressures "
            "survival is ~0"),
         "evidence_class": "inferred", "handling": "flagged to the owner; not fixed here (W1 is another lane)"},
        {"id": "GP-F06", "finding": "full recombination releases up to the tabulated heat (tens of W at the maximum "
         "flow) in the compressor / plenum / line walls", "evidence_class": "model-derived", "handling": "H2-5 demand"},
    ]

    owner_decisions = [
        {"id": "GP-D01", "question": "metering-valve control strategy", "options": ["fixed plenum setpoint (valve "
         "conductance turndown larger than the flow turndown)", "floating plenum pressure with a fixed restrictor "
         "(valve for isolation/transients only; compressor sees varying outlet pressure)"],
         "recommendation": "PROPOSED: decide after the C1 outlet characteristic is known; carry both"},
        {"id": "GP-D02", "question": "adopt the +-5 % / 10 % peak-to-peak cold-flow uniformity criterion",
         "options": ["adopt (REF-ROBERTS2024, verify primary)", "other"], "recommendation": "PROPOSED: adopt for S1a; "
         "note the budget consequence: the distributor drop scales as 1/delta, so the criterion directly sets the "
         "required plenum / compressor outlet pressure (HI-05)"},
        {"id": "GP-D03", "question": "gas-path wall recombination policy", "options": ["catalytic path: deliver "
         "N2 + O2 (ground S-O2E then matches the flight feed)", "inert lining: preserve some atomic O (ground "
         "cannot reproduce it)"], "recommendation": "PROPOSED for the owner; no preference asserted (no chemistry "
         "evidence on O vs O2 for the discharge)"},
        {"id": "GP-D04", "question": "exclude silver from wetted parts", "options": ["yes", "no"],
         "recommendation": "PROPOSED: yes"},
    ]

    doc = {
        "schema": SCHEMA_ID,
        "version": VERSION,
        "status": "DRAFT_PENDING_OWNER (H2 preliminary sizing; every value not in the RFP or a cited source is "
                  "PROPOSED, ASSUMED or TBD)",
        "lane": "fo_h2_3_gas_path_plenum",
        "trigger": "T_H2_3_GAS_PATH_PLENUM",
        "owner_authorization": "A7 (waves H2; h2_scope design/preliminary-sizing lane)",
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL,
        "companion_document": f"{OUT_DIR_REL}/{MD_NAME}",
        "test": "tests/test_h2_3_gas_path_plenum.py",
        "architectures": ARCHS,
        "architecture_neutrality": "no value depends on the architecture id; never declares a winner",
        "closure_independence": "no Hall transport closure, ensemble member, screening candidate, plasma_devices.py "
                                "value or withdrawn v1.2-v1.6 number enters; P5 calibration nuisance is never a "
                                "design variable; every pressure is a cold-flow gas-dynamics quantity",
        "decision_pins": [{"path": k, "sha256": v} for k, v in DECISION_PINS.items()],
        "input_fingerprints": [{"path": p, "sha256": sha256(p), "role": "consumed read-only (not pinned)"}
                               for p in CONSUMED],
        "pending_lanes": PENDING_LANES,
        "a5_context": {"atmospheric_branch": a5["architecture"]["atmospheric_branch"],
                       "reserved_interface": a5["architecture"]["reserved_interface"]["location"],
                       "operating_modes": a5["operating_modes"]["sequence"]},
        "references": REFERENCES,
        "design_parameters": params,
        "topology": topology,
        "measurement_locations": measurement,
        "compositions": comps,
        "flow_points": {k: {"mdot_mg_s": sig(v["mdot_kgps"] * 1e6, 5), "basis": v["basis"]} for k, v in flows.items()},
        "atmosphere_facts": atmf,
        "w1_turndown_per_candidate": turndowns,
        "pressure_budget": pb,
        "distributor_uniformity": uni,
        "plenum_sizing": ps,
        "o_recombination": orc,
        "xe_tie_in": xe,
        "materials": materials,
        "interface_demands": interface_demands,
        "hard_incompatibility_check": hard,
        "architecture_changing_blockers_touched": blockers,
        "m16_rows": m16,
        "h3_procurement_inputs": h3,
        "h4_test_inputs": h4,
        "findings": findings,
        "owner_decisions": owner_decisions,
        "proposal_gaps": [{"id": "GP-G01", "gap": "no flight composition sensor: x_s at IF-A5 is inferred",
                           "rollup": "proposal-only documentation gap"}],
        "milestones": {
            "supports": "A",
            "A": "a conditional selection can name the gas-path conditions: plenum pressure within the compressor "
                 "outlet capability at the measured H-1 conductance; cold-flow distributor uniformity within the "
                 "PROPOSED criterion; P_feed / T_feed / x_s recorded at IF-A5 (ground analog upstream of IP-UP)",
            "B": "needs the H-1 geometry (H2-1), measured S1a cold-flow manifold pressures and uniformity, the C1 "
                 "outlet characteristic, a selected valve class, measured wall recombination on the chosen material",
            "C": "needs flight plenum / valve / isolator designs with mass (H2-7), heater and valve power in the "
                 "bus_power_boundary_v1 ledger (H2-4), thermal closure incl. recombination heat (H2-5), and "
                 "component qualification",
        },
    }
    return doc


# ------------------------------------------------------------------------------------------------------------------
# markdown
# ------------------------------------------------------------------------------------------------------------------
def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, list):
        return " – ".join(fmt(x) for x in v)
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def render_md(d: dict) -> str:
    L = []
    a = L.append
    a("# H2-3 atmospheric gas path / plenum — preliminary design v1")
    a("")
    a(f"> Generated by `{SCRIPT_REL}` from `{JSON_NAME}`. Do not edit by hand; rerun the script (`--check` verifies).")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| machine-readable | [`{JSON_NAME}`]({JSON_NAME}) |")
    a(f"| status | **{d['status']}** (version {d['version']}) |")
    a(f"| lane | `{d['lane']}` (trigger `{d['trigger']}`, owner addendum A7) |")
    a("| scope | H2 hardware design / preliminary sizing, **not** architecture selection (A7 `h2_scope`) |")
    a("| architectures | `hall_only`, `rf_hall`, `ecr_hall`: one gas path; only the IP-UP → IP-DN occupant differs |")
    a(f"| test | `{d['test']}` |")
    a(f"| base commit | `{d['base_commit']}` |")
    a("")
    a("**What it is.** The FS-C atmospheric branch of the A5 Proposal Reference Architecture from the compressor outlet "
      "to `HALL_INLET_Z0`: topology with the interface planes, where P_feed / T_feed / x_s are measured, segment "
      "conductances and flow regimes, a cold-flow pressure budget, plenum volume ranges from explicit requirements, "
      "fill/drain time constants, the distributor uniformity rule, atomic-O recombination and materials, and the "
      "interface demands to the other lanes.")
    a("")
    a("**What it is not.** No thrust, efficiency, discharge current or plasma state is predicted; no Hall transport "
      "closure, screening candidate, `plasma_devices.py` value or withdrawn v1.2–v1.6 number is used; no P5 "
      "calibration-nuisance item is a design variable. Every pressure below is a **cold-flow** (no plasma) quantity. "
      "The ECHT geometry (86 mm long, 10 mm wide, 100 mm OD) is used **only as an analog illustration** of the "
      "back-pressure scale; the H-1 geometry is PENDING H2-1. A5 numbers are allocations/requirements, never "
      "predictions. Bundle 1 stays NO_BASELINE_YET; the credible Hall set is empty.")
    a("")
    a("## 1. Pinned decisions and consumed inputs")
    a("")
    a("| path | sha256 | role |")
    a("|---|---|---|")
    for p in d["decision_pins"]:
        a(f"| `{p['path']}` | `{p['sha256']}` | immutable, pinned (build refuses on mismatch) |")
    for p in d["input_fingerprints"]:
        a(f"| `{p['path']}` | `{p['sha256'][:16]}…` | {p['role']} |")
    a("")
    a("Parallel lanes referenced only as PENDING (nothing here reads them): " +
      "; ".join(f"{k}: `{v}`" for k, v in d["pending_lanes"].items()) + ".")
    a("")
    a("## 2. Line topology and interface planes")
    a("")
    a("```")
    a("compressor (C1) -N0/IF-A3-> [V0 isolation valve] -> N1 plenum -IF-A4-> V1 metering valve -N2/IF-A5-> T1 Xe tee")
    a("   (Xe anode line from Xe metering joins at T1) -> I1 gas isolator -> IP-UP -> [PIM-0 | PIM-RF | PIM-ECR] -> IP-DN")
    a("   -> H-1 stub -> D1 anode manifold ring (N_f feed points) -> D2 distributor -> HALL_INLET_Z0 -> channel")
    a("ground (H-1 test article): FS-C MFCs + bottles + mixing point + isolator + manifold gauge replace N0..T1")
    a("```")
    a("")
    a("| node | element | plane | owner | representativeness |")
    a("|---|---|---|---|---|")
    for n in d["topology"]["flight_nodes"]:
        a(f"| {n['id']} | {n['name']} | {fmt(n['plane'])} | {n['owner']} | {n['representativeness']} |")
    g = d["topology"]["ground_substitution"]
    a("")
    a(f"Ground substitution ({g['representativeness']}): {g['replaced_upstream_of_IP_UP']}. {g['consequence']}. "
      f"Cathode gas: {d['topology']['cathode_gas']}.")
    a("")
    a("## 3. Design-parameter table")
    a("")
    a("| id | name | value | units | basis | evidence | status | representativeness | source / note |")
    a("|---|---|---|---|---|---|---|---|---|")
    for p in d["design_parameters"]:
        note = p["source"] + (f" — {p['note']}" if p.get("note") else "")
        a(f"| {p['id']} | {p['name']} | {fmt(p['value'])} | {p['units']} | {p['basis']} | {p['evidence_class']} | "
          f"{p['status']} | {p['representativeness']} | {note} |")
    a("")
    a("## 4. Measurement locations (bus_power_boundary_v1 mandatory fields P_feed, T_feed, x_s, ṁ_s)")
    a("")
    a("| quantity | defined at | flight location | ground (H-1) location | INS ids | note |")
    a("|---|---|---|---|---|---|")
    for m in d["measurement_locations"]:
        a(f"| {m['quantity']} | {m['definition_plane']} | {m['flight_location']} | {m['ground_location']} | "
          f"{', '.join(m['INS']) or '—'} | {m.get('note', '') + ((' ' + m['also']) if m.get('also') else '')} |")
    a("")
    a("## 5. Flow points, compositions and flow regime")
    a("")
    a("| flow point | ṁ [mg/s] | basis |")
    a("|---|---|---|")
    for k, v in d["flow_points"].items():
        a(f"| {k} | {v['mdot_mg_s']} | {v['basis']} |")
    a("")
    a("| composition | mass fractions | M [kg/mol] | basis |")
    a("|---|---|---|---|")
    for k, v in d["compositions"].items():
        a(f"| {k} | {v['w']} | {v['M_kg_per_mol']:.5g} | {v['basis']} ({v['evidence_class']}) |")
    a("")
    a("Mean free path λ = kT/(√2 σ_c p) with σ_c = 0.43 nm² (N₂, the largest tabulated value, used for every species "
      "because atomic O is not tabulated; shortest λ, conservative for 'molecular' statements). Regimes: "
      "free-molecular Kn > 0.5, viscous Kn < 0.01 (REF-CHIGGIATO Table 7). Molecular conductances: thin slot "
      "C = A⟨v⟩/4, tube C = (⟨v⟩/4)(πD²/4)τ with the Santeler τ; transitional segments use the Leybold Knudsen factor "
      f"f(d·p̄) (Eq. 1.27, air 20 °C; inferred transfer, verify), f_min = {KNUDSEN_F_MIN:.4g}.")
    a("")
    a("## 6. Cold-flow pressure budget (analog channel illustration)")
    a("")
    a(d["pressure_budget"]["method"] + ". " + d["pressure_budget"]["channel_is_analog_illustration"] + ". "
      + d["pressure_budget"]["distributor_rule_used"] + "; distributor options (ASSUMED): " + "; ".join(
          f"{k} ring bore {v['ring_bore_m'] * 1e3:g} mm, {v['feed_points']} feed points"
          for k, v in d["pressure_budget"]["distributor_options"].items()) + ".")
    a("")
    a("| flow | composition | T [K] | distributor | Q [Pa m³/s] | p_Z0 cold [Pa] | Kn channel | dp holes [Pa] | "
      "p manifold [Pa] | p_IF-A5 S/M/L [Pa] | p_plenum r=1 S/M/L [Pa] | dp PIM blank S/M/L [Pa] |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in d["pressure_budget"]["rows"]:
        gs = r["geometries"]
        a(f"| {r['flow']} | {r['composition']} | {r['T_K']:g} | {r['distributor']} | {r['Q_Pa_m3_s']:.3g} | "
          f"{r['p_HALL_INLET_Z0_cold_Pa']:.3g}"
          f" | {r['Kn_channel']:.3g} | {r['dp_holes_min_Pa']:.3g} | {r['p_manifold_Pa']:.3g} | "
          + " / ".join(f"{gs[k]['p_IF_A5_Pa']:.3g}" for k in GEOMETRY_OPTIONS) + " | "
          + " / ".join(f"{gs[k]['valve']['r=1']['p_plenum_min_Pa']:.3g}" for k in GEOMETRY_OPTIONS) + " | "
          + " / ".join(f"{gs[k]['dp_IP_UP_to_IP_DN_blank_Pa']:.3g}" for k in GEOMETRY_OPTIONS) + " |")
    a("")
    a("Geometry options (ASSUMED, not design values): " + "; ".join(
        f"{k}: line {v['line_D_m'] * 1e3:g} mm × {v['line_L_m']:g} m, isolator {v['iso_D_m'] * 1e3:g} mm × "
        f"{v['iso_L_m']:g} m, PIM blank {v['pim_D_m'] * 1e3:g} mm × {v['pim_L_m']:g} m, stub {v['stub_D_m'] * 1e3:g} mm × "
        f"{v['stub_L_m']:g} m" for k, v in GEOMETRY_OPTIONS.items()) + ". Valve authority r = C_valve,open / C_down "
      "(PROPOSED 1 or 3): p_plenum ≥ (1 + 1/r) p_IF-A5. Segment detail (C, Kn, regime, dp) is in the JSON.")
    a("")
    a("## 7. Anode manifold / distributor")
    a("")
    u = d["distributor_uniformity"]
    a(f"Rule (model-derived): {u['rule']}. {u['note']}. Practice: the anode usually doubles as gas distributor with an "
      "annular array of small orifices whose spacing/location set azimuthal uniformity (REF-REID2007 p. 2); an "
      "azimuthal neutral-density non-uniformity from a manufacturing error reduced efficiency, symmetry and stability "
      "(p. 8); cold-flow probe sweeps are used to verify a new anode (p. 7). Criterion PROPOSED: ±5 % / 10 % "
      "peak-to-peak (REF-ROBERTS2024, abstract; verify primary). Options: orifice array (baseline), internal baffles "
      "(additive manufacturing, REF-ROBERTS2024), porous stage (no source accessed in this lane: verify).")
    a("")
    a("| flow | T [K] | ring bore [mm] | feed points | p_Z0 [Pa] | p manifold [Pa] | dp holes [Pa] | Kn ring | "
      "N holes max 0.5 / 1 mm (Kn hole) |")
    a("|---|---|---|---|---|---|---|---|---|")
    for r in u["rows"]:
        hs = r["holes_for_max_C"]
        a(f"| {r['flow']} | {r['T_K']:g} | {r['ring_bore_m'] * 1e3:g} | {r['feed_points']} | {r['p_Z0_cold_Pa']:.3g} | "
          f"{r['p_manifold_Pa']:.3g} | {r['dp_holes_Pa']:.3g} | {r['Kn_ring']:.3g} | "
          f"{hs['0.5 mm']['N_holes_max_molecular']} ({hs['0.5 mm']['Kn_hole']:.2g}) / "
          f"{hs['1 mm']['N_holes_max_molecular']} ({hs['1 mm']['Kn_hole']:.2g}) |")
    a("")
    a("## 8. Plenum sizing")
    a("")
    ps = d["plenum_sizing"]
    a(f"C_tot (plenum → vacuum) range {fmt(ps['C_tot_range_m3_s'])} m³/s ({ps['C_tot_basis']}). The compressor is "
      "treated as an ideal flow source (ASSUMED; its back-conductance is a compressor-lane demand).")
    a("")
    a(f"**Compressor ripple** — {ps['compressor_ripple']['formula']}; {ps['compressor_ripple']['frequency_basis']}.")
    a("")
    a("| f [Hz] | attenuation a | τ_min [s] | V_min at C_tot lo / hi [m³] |")
    a("|---|---|---|---|")
    for r in ps["compressor_ripple"]["rows"]:
        a(f"| {r['f_ripple_Hz']:g} | {r['attenuation']:g} | {r['tau_min_s']:.3g} | {r['V_min_m3_at_C_tot_lo']:.3g} / "
          f"{r['V_min_m3_at_C_tot_hi']:.3g} |")
    a("")
    a(f"**Valve bandwidth** — {ps['valve_bandwidth']['rule']} ({ps['valve_bandwidth']['f_bw_status']}).")
    a("")
    a("| f_bw [Hz] | τ_min [s] | V_min at C_tot lo / hi [m³] |")
    a("|---|---|---|")
    for r in ps["valve_bandwidth"]["rows"]:
        a(f"| {r['f_valve_bw_Hz']:g} | {r['tau_min_s']:.3g} | {r['V_min_m3_at_C_tot_lo']:.3g} / "
          f"{r['V_min_m3_at_C_tot_hi']:.3g} |")
    a("")
    a(f"**Ride-through** — {ps['ride_through']['rule']}.")
    a("")
    a("| flow | plenum pressure basis | p [Pa] | t_ride [s] | V required [m³] |")
    a("|---|---|---|---|---|")
    for r in ps["ride_through"]["rows"]:
        a(f"| {r['flow']} | {r['pressure_basis']} | {r['p_plenum_Pa']:.3g} | {r['t_ride_s']:g} | "
          f"{r['V_required_m3']:.3g} |")
    a("")
    a(ps["ride_through"]["conclusion"] + ".")
    a("")
    a(f"**Ram-flow variation** — {ps['ram_variation']['rule']}. Scale height {d['atmosphere_facts']['scale_height_km_min']}"
      f"–{d['atmosphere_facts']['scale_height_km_max']} km; δρ/ρ for 1 / 5 km: " + ", ".join(
        f"{r['case']} {r['dh_km']:g} km {r['delta_rho_over_rho']:.3g}" for r in ps["ram_variation"]["rows"]
        if r["case"].endswith("mean"))
      + f". Quarter-orbit / largest grid τ ≥ {ps['ram_variation']['timescale_ratio_min']:.3g}. "
      f"{ps['ram_variation']['conclusion']}.")
    a("")
    a(f"**Fill / drain** — {ps['fill_drain']['formula']}.")
    a("")
    a("| V [m³] | τ at C_tot hi [s] | τ at C_tot lo [s] | t99 at C_tot lo [s] |")
    a("|---|---|---|---|")
    for r in ps["fill_drain"]["rows"]:
        a(f"| {r['V_m3']:g} | {r['tau_at_C_tot_hi_s']:.3g} | {r['tau_at_C_tot_lo_s']:.3g} | "
          f"{r['t99_fill_or_drain_at_C_tot_lo_s']:.3g} |")
    vr = ps["volume_range"]
    a("")
    a(f"**Volume range (PRELIMINARY):** minimum-volume requirement {vr['V_min_m3']:.3g} m³ ({vr['V_min_basis']}) up to "
      f"{vr['V_upper_of_minimum_m3']:.3g} m³ ({vr['V_upper_of_minimum_basis']}); V_max {vr['V_max_status']}.")
    a("")
    a("## 9. Composition, atomic-O recombination and materials")
    a("")
    orc = d["o_recombination"]
    a(orc["method"] + ".")
    a("")
    a("| case | T [K] | p [Pa] | V [m³] | Kn | t_res [s] | O survival, kinetic limit (γ 0.001/0.01/0.07/0.14) | "
      "O survival, effective |")
    a("|---|---|---|---|---|---|---|---|")
    for r in orc["survival"]:
        a(f"| {r['case']} | {r['T_K']:g} | {r['p_plenum_Pa']:.3g} | {r['V_m3']:g} | {r['Kn_plenum']:.3g} | "
          f"{r['t_res_s']:.3g} | " + " / ".join(f"{v:.3g}" for v in r["O_survival_kinetic_limit"].values()) + " | "
          + " / ".join(f"{v:.3g}" for v in r["O_survival_effective"].values()) + " |")
    a("")
    a("Recombination heat (full recombination of the free-stream O, upper bound): " + "; ".join(
        f"{h['flow']} ({h['mdot_mg_s']} mg/s) {h['P_recombination_full_W']:.3g} W" for h in orc["heat"]) +
      f". {orc['conclusion']}.")
    a("")
    a("| part | option | O / O₂ behaviour | consequence | status |")
    a("|---|---|---|---|---|")
    for m in d["materials"]:
        a(f"| {m['part']} | {m['option']} | {m['O_behaviour']} | {m['consequence']} | {m['status']} |")
    a("")
    a("## 10. Xe tie-in (ignition / transition)")
    a("")
    a("The Xe anode line joins at T1 (single mixing point, HW-FS-02, PMI-02.R1) downstream of the metering valve and "
      "upstream of the isolator, so Xe never fills the plenum; ignition on Xe then smooth anode transfer to N₂ or "
      "N₂/O₂ with the cathode on Xe (REF-CIFALI2011 as recorded). Continuous Xe support is not a nominal mode (A5).")
    a("")
    a("| geometry | T [K] | shared volume [m³] | Xe hold-up [kg/Pa] | τ line (Xe) [s] |")
    a("|---|---|---|---|---|")
    for r in d["xe_tie_in"]["rows"]:
        a(f"| {r['geometry']} | {r['T_K']:g} | {r['V_shared_m3']:.3g} | {r['m_Xe_holdup_kg_per_Pa']:.3g} | "
          f"{r['tau_line_Xe_s']:.3g} |")
    a("")
    a(d["xe_tie_in"]["conclusion"] + ".")
    a("")
    a("## 11. Interface demands")
    a("")
    a("| from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|")
    for i in d["interface_demands"]:
        a(f"| {i['from']} | {i['to']} | {i['quantity']} | {fmt(i['value'])} | {i['units']} | {i['status']} |")
    a("")
    a("## 12. Hard-incompatibility check")
    a("")
    a(f"**Result: {d['hard_incompatibility_check']['result']}.** Checked:")
    a("")
    a("| id | what | finding | evidence class | veto | why not |")
    a("|---|---|---|---|---|---|")
    for h in d["hard_incompatibility_check"]["checked"]:
        a(f"| {h['id']} | {h['what']} | {h['finding']} | {h['evidence_class']} | {h['veto']} | {h['why_not']} |")
    a("")
    a("## 13. Architecture-changing blockers touched (A7)")
    a("")
    for b in d["architecture_changing_blockers_touched"]:
        a(f"- **Blocker {b['blocker']}:** {b['how']}")
    a("")
    a("## 14. M16 rows (proposed execution state)")
    a("")
    a("| A5 subsystem | draft M16 row | matured here | proposed state | blocking item | rollup |")
    a("|---|---|---|---|---|---|")
    for m in d["m16_rows"]:
        a(f"| {m['a5_subsystem']} | {m['m16_row_draft_id']} | {m['matured_by_this_lane']} | {m['proposed_state']} | "
          f"{fmt(m['blocking_item'])} | {fmt(m['rollup'])} |")
    a("")
    a("## 15. H3 procurement inputs (specification level; catalog data as reference only, no supplier contact)")
    a("")
    a("| item | long lead | specification level needed | status |")
    a("|---|---|---|---|")
    for h in d["h3_procurement_inputs"]:
        a(f"| {h['item']} | {h['long_lead']} | {h['spec_level_needed']} | {h['status']} |")
    a("")
    a("## 16. H4 test inputs")
    a("")
    a("| stage | measure | closes |")
    a("|---|---|---|")
    for h in d["h4_test_inputs"]:
        a(f"| {h['stage']} | {h['measure']} | {', '.join(h['closes'])} |")
    a("")
    a("## 17. Findings and owner decisions")
    a("")
    a("| id | finding | evidence class | handling |")
    a("|---|---|---|---|")
    for f in d["findings"]:
        a(f"| {f['id']} | {f['finding']} | {f['evidence_class']} | {f['handling']} |")
    a("")
    a("| id | question | options | recommendation |")
    a("|---|---|---|---|")
    for o in d["owner_decisions"]:
        a(f"| {o['id']} | {o['question']} | {'; '.join(o['options'])} | {o['recommendation']} |")
    a("")
    a("Proposal gaps: " + "; ".join(f"{g['id']} {g['gap']} ({g['rollup']})" for g in d["proposal_gaps"]) + ".")
    a("")
    a("## 18. Milestones")
    a("")
    ms = d["milestones"]
    a(f"Supports **{ms['supports']}**. A: {ms['A']}. To reach **B**: {ms['B']}. To reach **C**: {ms['C']}.")
    a("")
    a("## 19. References")
    a("")
    for k, r in d["references"].items():
        a(f"- **{k}**: {r['citation']}. {r['url']} ({r['access']}). Used for: {r['used_for']}.")
    a("")
    a("## 20. Reproduce")
    a("")
    a("```")
    a(f"python {SCRIPT_REL}           # rewrite {JSON_NAME} and {MD_NAME}")
    a(f"python {SCRIPT_REL} --check   # exit 1 unless both are reproduced byte for byte")
    a("python -m pytest -q tests/test_h2_3_gas_path_plenum.py")
    a("```")
    a("")
    return "\n".join(L)


def outputs() -> dict:
    doc = build()
    return {JSON_NAME: json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n", MD_NAME: render_md(doc)}


def resolve_pending() -> dict:
    """Lazy status of the parallel lanes (never used in the committed outputs)."""
    return {k: ("present" if (REPO / p).exists() else "missing (PENDING)") for k, p in PENDING_PROBE_FILES.items()}


def main(argv: list) -> int:
    out_dir = REPO / OUT_DIR_REL
    outs = outputs()
    if "--check" in argv:
        bad = [n for n, t in outs.items() if not (out_dir / n).exists() or (out_dir / n).read_text() != t]
        if bad:
            print("NOT REPRODUCED:", ", ".join(bad))
            return 1
        print("OK: reproduced", ", ".join(outs))
        return 0
    for n, t in outs.items():
        (out_dir / n).write_text(t)
    print("wrote", ", ".join(outs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
