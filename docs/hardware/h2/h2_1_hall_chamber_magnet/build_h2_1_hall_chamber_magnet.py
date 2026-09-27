#!/usr/bin/env python3
"""H2-1: Hall chamber + magnetic circuit preliminary sizing for H-1 / MC-1 (fo_h2_1_hall_chamber_magnet).

Deterministic builder. It reads its repository inputs (each pinned by sha256 at build time), evaluates the sizing
relations listed below and writes

    docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json
    docs/hardware/h2/h2_1_hall_chamber_magnet/H2_1_HALL_CHAMBER_MAGNET.md

Usage:
    python docs/hardware/h2/h2_1_hall_chamber_magnet/build_h2_1_hall_chamber_magnet.py           # (re)write both files
    python docs/hardware/h2/h2_1_hall_chamber_magnet/build_h2_1_hall_chamber_magnet.py --check   # verify committed files

What it is: an H2 hardware design / preliminary-sizing lane (owner addendum A7). It is NOT an architecture-selection
lane and makes NO performance prediction: no Hall transport closure (none is admitted), no screening candidate, no
0-D Hall model (abep_sim/plasma_devices.py, superseded) and no withdrawn v1.2-v1.6 number enters any value. Channel
sizing uses requirements, A5 allocations, published xenon-derived scaling relations (hypotheses for N2/O/O2, labelled)
and published analog hardware (labelled analog, never a Vyovrinda design value). The coil calculation uses the pure
magnetostatic module abep_sim/magnet_power.py (lumped reluctance + integer-turn coil, NBS copper R(T); it is NOT the
superseded 0-D Hall physics: it contains no plasma model). Every assumed number is an explicit input below with its
evidence class; missing inputs raise (no silent fallback). Thresholds not in the RFP are PROPOSED for the owner.

Nothing here reads a sibling worktree: parallel-lane values are carried as 'PENDING <lane path>' with the range that
can be justified from base-commit evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

from abep_sim import constants as C  # noqa: E402  (fundamental constants + RFP set; no model)
from abep_sim import magnet_power as MP  # noqa: E402  (pure magnetostatics + copper R(T); no plasma model)

OUT_JSON = HERE / "h2_1_hall_chamber_magnet_v1.json"
OUT_MD = HERE / "H2_1_HALL_CHAMBER_MAGNET.md"
LANE_DIR = "docs/hardware/h2/h2_1_hall_chamber_magnet/"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
DATE = "2026-09-27"
ARCHS = ("hall_only", "rf_hall", "ecr_hall")

# ------------------------------------------------------------------------------------------------ pinned inputs
# Immutable owner decisions (pinned; the test fails if they differ) and verified deliverables (sha256 recorded at
# build time; a change makes --check fail so the lane is rebuilt deliberately). Mutable governance files
# (lane/trigger registries, ledgers, runtime_state.json) are never read or pinned.
DECISIONS = {
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925"),
    "G0": ("docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
           "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523"),
}
REPO_INPUTS = {
    "HWREQ": "docs/experiments/hardware/hardware_requirements_v1.json",
    "MCQ": "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json",
    "SCALING": "docs/architecture_comparison/scaling/scaling_similarity.json",
    "HALLREF": "docs/architecture_comparison/hall_reference/hall_reference_v1.json",
    "FEED": "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json",
    "HSM": "docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
    "VETO": "docs/architecture_comparison/veto_layer/veto_layer_v1.json",
    "WALL": "docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md",
    "AOL": "docs/experiments/lifetime_ao/ao_lifetime_register_v5.json",
    "ELEC": "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
    "CONSTANTS": "abep_sim/constants.py",
    "MAGNET_POWER": "abep_sim/magnet_power.py",
}

# ------------------------------------------------------------------------------------------------ open sources
# Accessed by this lane on 2026-09-27 (sha256 of the file as downloaded). Repository-carried sources are cited by
# the repository record that holds them (path + field).
SOURCES = {
    "SRC-MASMI": {
        "citation": "R. W. Conversano, D. M. Goebel, R. R. Hofer, T. S. Matlock, R. E. Wirz, 'Magnetically Shielded "
                    "Miniature Hall Thruster: Development and Initial Testing', IEPC-2013-201, 33rd IEPC, Washington "
                    "D.C. (2013)",
        "url": "https://electricrocket.org/IEPC/h8gqm62v.pdf",
        "accessed": DATE, "access": "open full text (ERPS proceedings; copyright R. W. Conversano, published by ERPS "
                                    "with permission, p. 1)",
        "sha256": "802f91ddc64251978ea28047f4c29b74ab9e800bc7b64dd179705f622877234e",
        "evidence_level": "measured design dimensions / measured operating values of a xenon laboratory device; "
                          "model-predicted field value (p. 5); published analog only",
    },
    "SRC-HIPERCO50": {
        "citation": "Carpenter Electrification, 'HIPERCO 50' data sheet (E200; PDF creation date 2022-11-09 per file "
                    "metadata)",
        "url": "https://f.hubspotusercontent20.net/hubfs/7407327/carpenter_electrification/Resources/Datasheets/"
               "Hiperco_50_Alloy_(E200).pdf",
        "accessed": DATE, "access": "open supplier data sheet (reference only; no supplier contact)",
        "sha256": "cdbe75cee6f446971f64279e45fbb7834ce056f913e96fba9691241769757f1d",
        "evidence_level": "supplier-typical (measured, procedure not published); strip data (0.355 mm / 0.152 mm)",
    },
    "SRC-ARMCO": {
        "citation": "AK Steel International (Cleveland-Cliffs), 'ARMCO Pure Iron - High Purity Iron', Product Data "
                    "Bulletin, October 2022",
        "url": "https://www.aksteel.nl/files/downloads/clf_productdata__armco_pure_iron_pdb_euro_final_072022_92.pdf",
        "accessed": DATE, "access": "open supplier data bulletin (reference only; no supplier contact)",
        "sha256": "b3306c48e295f80ad1c63e93854d495338682906665850121159a7e4e4c8a0e9",
        "evidence_level": "supplier-typical (measured, procedure not published)",
    },
    "SRC-WIKI-CURIE": {
        "citation": "Wikipedia, 'Curie temperature', table 'Curie points of various materials' (cites Buschow 2001, "
                    "Jullien & Guinier 1989, Kittel 1986)",
        "url": "https://en.wikipedia.org/wiki/Curie_temperature",
        "accessed": DATE, "access": "open encyclopedia (dynamic page, no stable hash); secondary: verify against "
                                    "Kittel before design use",
        "sha256": None,
        "evidence_level": "secondary compilation (verify)",
    },
    "SRC-MIKELLIDES2014": {
        "citation": "I. G. Mikellides, I. Katz, R. R. Hofer, D. M. Goebel, 'Magnetic shielding of a laboratory Hall "
                    "thruster. I. Theory and validation', J. Appl. Phys. 115, 043303 (2014), doi:10.1063/1.4862313",
        "url": "https://api.crossref.org/works/10.1063/1.4862313 ; https://api.openalex.org/works/doi:10.1063/1.4862313",
        "accessed": DATE, "access": "ABSTRACT ONLY (closed access per OpenAlex; publisher/ADS/OSTI pages not "
                                    "readable: 405/503; not bypassed)",
        "sha256": None,
        "evidence_level": "abstract statement of a xenon 6 kW laboratory result (simulation + experiment)",
    },
}

# ------------------------------------------------------------------------------------------------ explicit inputs
# Every assumed number of this lane, with basis and evidence class. Nothing below is hidden in code.
ASSUMED = {
    "discharge_share_min": {
        "value": 0.5, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "lower bracket of the hall_discharge share of the A5 bus allocation, used only to bound the power-"
               "based channel-area rules from below; the real share is PENDING docs/hardware/h2/h2_4_ppu_bus/"},
    "T_n_K": {
        "value": [300.0, 800.0], "unit": "K", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "neutral temperature bracket of the scaling lane (scaling_similarity.json inputs.analysis T_n_K: 300 K "
               "ingestion reference, 800 K DM2008 channel gas); the distributor thermal state is PENDING "
               "docs/hardware/h2/h2_5_thermal_network/"},
    "LH_upper": {
        "value": 12.0, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "packaging upper bracket of L/h for this preliminary window (mass, B(z) length, probe reach); the "
               "equal-n_e ionization-length rule allows up to ~33 (see channel.L_over_h_rules) but part of the "
               "N2 n_e*L demand can be met by n_e, so it is not adopted; owner decision"},
    "rLe_fraction_of_h": {
        "value": 0.1, "unit": "-", "basis": "analog", "evidence_class": "inferred",
        "status": "PRELIMINARY",
        "why": "electron Larmor radius <= 10 % of channel width, 'as is generally deemed optimal' (SRC-MASMI p. 5, "
               "citing Goebel & Katz); used as a lower-bound field criterion, not a transport optimization"},
    "T_e_criterion_eV": {
        "value": [10.0, 20.0, 30.0], "unit": "eV", "basis": "assumed", "evidence_class": "assumed",
        "status": "PROPOSED",
        "why": "electron temperature inserted in the r_Le criterion: 20 eV as used by SRC-MASMI p. 5; 10 and 30 eV "
               "bracket it inside the project chemistry domain (T_e <= 30 eV). A design parameter of the criterion, "
               "not a predicted plasma state"},
    "B_headroom_factor": {
        "value": 1.5, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "MC-1 capability = factor x upper target field, so the S1b coil-current scan (HW-MC-05) and the "
               "reported N2 need for a stronger field than on Xe/Kr (1.48x, MOSKOVITZ2026 via hall_sustainment E10) "
               "stay inside the circuit rating; owner decision"},
    "B_work_fraction_of_Bsat": {
        "value": 0.7, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "iron working flux density = fraction x room-temperature saturation, leaving margin for the "
               "temperature-dependent B-H curve (not sourced, HW-MC-13) and FEMM-found local concentrations"},
    "mu_r_core": {
        "value": 1000.0, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "conservative linear relative permeability of the return path at the working flux density; the "
               "suppliers quote only maximum permeability (Hiperco 50 DC mu_max 15000-18000, SRC-HIPERCO50 p. 3) "
               "and ungraded curves (ARMCO Fig. 7/8, not digitized); FEMM with the real B-H curve replaces it"},
    "t_wall_mm": {
        "value": [3.0, 4.0, 6.0], "unit": "mm", "basis": "assumed", "evidence_class": "assumed",
        "status": "PROPOSED",
        "why": "ceramic channel wall thickness (min / reference / max); no sourced value; wall grade is an owner "
               "decision (HW-H1-04)"},
    "gap_clearance_mm": {
        "value": 1.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "radial assembly clearance between wall and pole on each side"},
    "pole_tip_width_mm": {
        "value": [5.0, 8.0, 10.0], "unit": "mm", "basis": "assumed", "evidence_class": "assumed",
        "status": "PROPOSED", "why": "axial pole-tip width that sets the gap area A_g = 2 pi R_mean w_p"},
    "leakage_factor": {
        "value": [1.5, 2.0, 3.0], "unit": "-", "basis": "assumed", "evidence_class": "assumed",
        "status": "PROPOSED",
        "why": "core flux / gap flux (leakage + fringing) for the magnet_power reluctance model; no value is "
               "sourced (electrical_closure example used 1.5 as an assumed analysis input); FEMM closes it"},
    "NI_margin_factor": {
        "value": [1.0, 2.0], "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "multiplier on the lumped-gap ampere-turns: the channel-centreline field of a real pole geometry is "
               "below the uniform-gap value and a shielded topology needs extra MMF; unknown until FEMM/3-D "
               "magnetostatics (H4 / H2 follow-up); the coil is sized at the upper value"},
    "NI_split_inner": {
        "value": 0.5, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "share of total NI on the inner coil (rest on the outer coil); set by FEMM"},
    "fill_factor": {
        "value": 0.5, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "bare-copper fraction of the winding window (insulation, bobbin, packing inside it); same assumed "
               "analysis input as the electrical_closure magnet example; high-temperature insulation may lower it"},
    "bobbin_mm": {"value": 1.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
                  "why": "coil former / ground insulation radial allowance on each coil"},
    "screen_mm": {"value": 2.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
                  "why": "radial allowance between inner coil and inner channel wall (magnetic screen / heat shield)"},
    "inner_coil_min_build_mm": {
        "value": 5.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "smallest inner-coil radial build accepted as buildable (feasibility test for a central cathode)"},
    "outer_coil_build_mm": {"value": 10.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed",
                            "status": "PROPOSED", "why": "outer-coil radial build"},
    "coil_axial_fraction_of_L": {
        "value": 0.8, "unit": "-", "basis": "assumed", "evidence_class": "assumed", "status": "PROPOSED",
        "why": "coil axial length as a fraction of channel length (the rest: pole, back plate, terminations)"},
    "back_plate_mm_min": {"value": 5.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed",
                          "status": "PROPOSED", "why": "minimum back-plate thickness (mechanical), flux sizing may "
                                                          "require more"},
    "outer_core_mm_min": {"value": 3.0, "unit": "mm", "basis": "assumed", "evidence_class": "assumed",
                          "status": "PROPOSED", "why": "minimum outer-core tube wall (mechanical); flux sizing alone "
                                                      "gives sub-millimetre walls at these fluxes"},
    "cathode_bore_diameter_mm": {
        "value": [12.0, 18.0], "unit": "mm", "basis": "pending", "evidence_class": "assumed",
        "status": "PENDING docs/hardware/h2/h2_2_cathode_integration/",
        "why": "C-1 OD + radial gap for the central (L-C) cathode location: published C-1-class analog OD 10-16 mm "
               "(H2-2 lane draft demand, not read at build time) + 1 mm radial gap each side (assumed)"},
    "coil_supply_window": {
        "value": {"I_A": [1.0, 5.0], "V_V": [1.0, 12.0], "P_W_max": 60.0}, "unit": "A, V, W", "basis": "analog",
        "evidence_class": "assumed", "status": "PRELIMINARY",
        "why": "rating of a published sub-kW Hall PPU electromagnet supply (Rhodes et al. IEPC-2024-331 slide 3 as "
               "recorded in electrical_closure_data_v1.json HM-SUPPLY-EFF applicability.notes); a design rating of "
               "an analog, used only to pick the wire gauge; not a Vyovrinda supply (PENDING h2_4_ppu_bus)"},
    "awg_candidates": {"value": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26], "unit": "AWG", "basis": "assumed",
                       "evidence_class": "assumed", "status": "PROPOSED",
                       "why": "gauges searched for the coil current/voltage window"},
    "coil_temperatures_C": {
        "value": [20.0, 200.0], "unit": "degC", "basis": "assumed", "evidence_class": "assumed",
        "status": "PRELIMINARY",
        "why": "cold and the upper end of the NBS copper linear R(T) domain [0, 200] C (magnet_power "
               "ANNEALED_COPPER_IACS); a hotter coil is outside the model and its I^2R is TBD (MCQ-TL-04)"},
    "rp1_geometry": {
        "value": {"d_mean_mm": 70.0, "h_mm": 12.0, "L_over_h": 8.6}, "unit": "mm / -", "basis": "assumed",
        "evidence_class": "assumed", "status": "PROPOSED",
        "why": "coil-sizing reference point RP-1 chosen inside the preliminary window (area 26.4 cm^2, d/h 5.83, "
               "L/h at the window lower bound); a calculation anchor, NOT a design selection"},
}

# Material data read by this lane from the accessed data sheets (value, locator).
MATERIALS = {
    "ARMCO_pure_iron": {
        "B_sat_T": (2.15, "SRC-ARMCO PDF p. 9 (Magnetic Properties, High Inductions): 'maximum intrinsic induction (B-mu0 H), or a saturation induction value "
                          "of 2.15 T (21.5 kG)'"),
        "density_kg_m3": (7860.0, "SRC-ARMCO PDF p. 5 Table 1: density 7.86 g/cm3"),
        "curie_C": (770.0, "SRC-WIKI-CURIE (iron 1043 K / 770 C; secondary, verify); not stated in SRC-ARMCO"),
        "oxidation_note": ("'Improved resistance against corrosion and oxidation in comparison to normal steels' "
                           "(SRC-ARMCO PDF p. 3) - i.e. still an oxidizing iron; no statement on O/atomic-O exposure",
                           "SRC-ARMCO PDF p. 3"),
        "evidence_class": "measured (supplier-typical)",
    },
    "Hiperco_50": {
        "B_sat_T": (2.30, "SRC-HIPERCO50 p. 3 DC properties: B = 2.30 T at 16000 A/m (0.355 mm strip, typical "
                          "magnetic anneal); p. 1 description: 'highest magnetic saturation (24 kilogauss)'"),
        "density_kg_m3": (8110.0, "SRC-HIPERCO50 p. 2: density 8.11 g/cm3"),
        "curie_C": (938.0, "SRC-HIPERCO50 p. 2: Curie temperature 1720 F (938 C)"),
        "B_at_800_A_per_m_T": (2.15, "SRC-HIPERCO50 p. 3: 2.15 T at 800 A/m (0.355 mm strip, magnetic anneal)"),
        "mu_max": (18000.0, "SRC-HIPERCO50 p. 3: DC relative permeability mu max 18000 (0.355 mm, magnetic anneal)"),
        "forms": ("strip, plate (SRC-HIPERCO50 p. 1 'Forms manufactured'); bar not listed in the accessed sheet",
                  "SRC-HIPERCO50 p. 1"),
        "anneal_note": ("anneal 704-871 C in dry hydrogen or high vacuum 'to minimize oxide contamination'; never "
                        "above 871 C (SRC-HIPERCO50 p. 5)", "SRC-HIPERCO50 p. 5"),
        "evidence_class": "measured (supplier-typical, strip specimens)",
    },
}

# Published analog hardware used as context/bounds (never Vyovrinda design values).
ANALOGS = [
    {"id": "AN-ECHT", "device": "ECHT (Stanford extended-channel Hall thruster), N2 anode, Ar cathode",
     "L_mm": 86.0, "h_mm": 10.0, "OD_mm": 100.0, "d_over_h": 9.0, "L_over_h": 8.6,
     "B_G": "85.3 (centreline plateau at 2 A coil current only, digitized; the thesis '130 G' is a FEMM value, "
            "model-derived)",
     "source": "hall_sustainment_matrix.json entries[E03] (REPO_ECHT_AUDIT, MARCHIONI2020); CLAUDE.md "
               "(86 mm long, 10 mm wide, 100 mm OD); d/h 9 per scaling_similarity.json echt_groups (r_in/r_out "
               "40/50 mm reading A, inferred, verify)",
     "evidence_class": "measured (design dimensions); digitized (B)", "use": "published analog only"},
    {"id": "AN-CAMILA", "device": "Simplified CAMILA (ASRI Technion), pure N2, 212-452 W",
     "d_mean_mm": 49.0, "h_mm": 12.0, "d_over_h": round(49.0 / 12.0, 4),
     "B_G": "N2 needed 1.48x the Xe/Kr field (ratio, measured); absolute N2 B not legible",
     "source": "hall_sustainment_matrix.json entries[E10] (MOSKOVITZ2026 Table 3 p. 6, abstract/p. 13)",
     "evidence_class": "measured", "use": "published analog only"},
    {"id": "AN-Z70", "device": "Z-70 (Stanford, refurbished), Xe/N2 and Xe/air mixtures, 331-745 W",
     "OD_mm": 72.0, "ID_mm": 42.0, "depth_mm": 23.0, "d_mean_mm": 57.0, "h_mm": 15.0,
     "d_over_h": round(57.0 / 15.0, 4), "L_over_h": round(23.0 / 15.0, 4),
     "B_G": "135 (exit centreline, Xe/N2); 135-160 (Xe/air)",
     "source": "hall_sustainment_matrix.json entries[E13] and [E14] (GURCIULLO2020 p. 148, p. 201)",
     "evidence_class": "measured", "use": "published analog only (xenon-assisted, not pure air)"},
    {"id": "AN-MASMI", "device": "MaSMi magnetically shielded miniature Hall thruster, xenon, 325 W",
     "OD_mm": 44.0, "d_mean_mm": 36.0, "h_mm": 8.0, "L_mm": 16.0, "d_over_h": 4.5, "L_over_h": 2.0,
     "B_G": "~218 max on centreline (magnetic-circuit model prediction), 213 G required for r_Le <= 0.1 h at 20 eV",
     "coils": "single inner + single outer coil, AWG-22 Ni-plated fiberglass-insulated Cu 'rated to over 400 C'; "
              "5.2 A / 1.5 A, 29 W combined; Hiperco core because iron 'displays severe magnetic saturation "
              "problems at small thruster scales'",
     "temperatures": "~450 C channel base, ~475 C front pole piece (p. 11)",
     "source": "SRC-MASMI pp. 5, 7, 8-9, 11, 13, 18",
     "evidence_class": "measured (dimensions, coil currents/power, temperatures); model-derived (218 G)",
     "use": "published analog only (xenon; magnetic shielding at low power)"},
    {"id": "AN-P5N2", "device": "P5 on N2 (Brabston 2025)", "B_G": "130 (peak radial B at channel centre, exit plane)",
     "source": "hall_sustainment_matrix.json entries[E01] (REPO_P5_N2_AUDIT, Table 2)",
     "evidence_class": "measured", "use": "context magnitude only; P5 geometry/B(z) files are forbidden design "
                                          "sources (hall_reference_v1.json) and P5 calibration nuisance is never a "
                                          "design variable"},
    {"id": "AN-XEDB", "device": "xenon Hall database (DM2011)", "B_G": "typically ~200 'whatever the input power'",
     "source": "hall_reference_v1.json EV-B4 (DM2011 p. 242)", "evidence_class": "inferred",
     "use": "context magnitude only (xenon)"},
]


# ------------------------------------------------------------------------------------------------ helpers
def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sig(x, n=4):
    """Round to n significant figures (deterministic JSON)."""
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return [sig(v, n) for v in x]
    if isinstance(x, dict):
        return {k: sig(v, n) for k, v in x.items()}
    if isinstance(x, bool) or not isinstance(x, float):
        return x
    if x == 0.0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n}g}")


def need(d, *keys):
    """Explicit lookup: a missing key raises (no silent fallback)."""
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            if k not in cur:
                raise KeyError(f"required input missing: {'/'.join(map(str, keys))}")
            cur = cur[k]
        elif isinstance(cur, list):
            cur = cur[k]
        else:
            raise KeyError(f"required input missing: {'/'.join(map(str, keys))}")
    return cur


def a(key):
    return need(ASSUMED, key, "value")


def check_decision_pins():
    out = {}
    for k, (rel, pin) in DECISIONS.items():
        got = sha256_file(rel)
        if got != pin:
            raise RuntimeError(f"decision file {rel} sha256 {got} != pinned {pin}; decisions are immutable")
        out[k] = {"path": rel, "sha256": pin}
    return out


# ------------------------------------------------------------------------------------------------ inputs
def read_inputs():
    hw = load(REPO_INPUTS["HWREQ"])
    feed = load(REPO_INPUTS["FEED"])
    sc = load(REPO_INPUTS["SCALING"])
    hsm = load(REPO_INPUTS["HSM"])
    elec = load(REPO_INPUTS["ELEC"])
    a5 = load(DECISIONS["A5"][0])

    reqs = {r["id"]: r for r in need(hw, "requirements")}
    vd_set = need(reqs, "HW-ENV-01", "values", "V_d_proposed_set_V", "value")
    vd_hi = need(reqs, "HW-ENV-01", "values", "V_d_rating_upper_V", "value")

    alloc = {x["quantity"]: x["value"] for x in need(a5, "allocations_and_requirements")}
    if alloc.get("thrust operating target") != "15-22 mN" or alloc.get("bus-power design allocation") != "<= 1.30-1.35 kW":
        raise RuntimeError("A5 allocation strings not as expected; re-read the decision")

    # delivered flow: nominal valve-outlet states of every closed candidate x case, plus the MFC upper bound
    vo = need(feed, "valve_outlet")
    M = {"O": need(C.M_SPECIES, "O") / C.AMU, "N2": need(C.M_SPECIES, "N2") / C.AMU,
         "O2": need(C.M_SPECIES, "O2") / C.AMU}
    noms, mmol, w_oel, design_case = [], [], [], []
    for cand in sorted(vo):
        for case in sorted(vo[cand]):
            n = need(vo, cand, case, "nominal")
            md = need(n, "mdot_total_kgps")
            ws = need(n, "w_s")
            noms.append(md)
            mmol.append(1.0 / sum(ws[s] / M[s] for s in ws))
            w_oel.append(ws.get("O", 0.0) + ws.get("O2", 0.0))
            if case == "alt200_mean":
                design_case.append(md)
    mfc_max = need(feed, "mfc_range_requirement", "mdot_max_kgps")

    ech = need(sc, "echt_groups", "all_points")
    gtf = need(sc, "gas_transfer_factor")
    lam = [v for te in sorted(gtf, key=float) for v in need(gtf, te, "lambda_ratio_N2_over_Xe")]
    rel_inputs = need(sc, "inputs")

    ents = {e["id"]: e for e in need(hsm, "entries")}
    # sanity: the analog records exist where they are cited
    for eid in ("E01", "E03", "E07", "E09", "E10", "E13", "E14"):
        need(ents, eid)
    hm = [c for c in need(elec, "components") if isinstance(c, dict)] if isinstance(elec.get("components"), list) \
        else None
    return {
        "V_d_set_V": vd_set, "V_d_rating_upper_V": vd_hi,
        "thrust_rfp_mN": [C.RFP.thrust_min_mN, C.RFP.thrust_max_mN], "thrust_alloc_mN": [15.0, 22.0],
        "P_rfp_W": C.RFP.power_max_W, "P_alloc_W": [1300.0, 1350.0],
        "mdot_nominal_kgps": [min(noms), max(noms)], "mdot_design_case_kgps": [min(design_case), max(design_case)],
        "mdot_mfc_max_kgps": mfc_max, "mdot_A5_quote_kgps": 3.2e-6,
        "molar_mass_flight_gmol": [min(mmol), max(mmol)], "w_O_element": [min(w_oel), max(w_oel)],
        "n_n_ECHT_m3": need(ech, "n_n"), "lambda_ratio_N2_Xe": [min(lam), max(lam)],
        "n_crit_Xe_m3": 1.2e19, "C_P_star_W_m2": 1.2e6, "j_d_A_m2": [1000.0, 1500.0],
        "_scaling_inputs_present": bool(rel_inputs),
        "_hm": hm is not None,
    }


# ------------------------------------------------------------------------------------------------ physics helpers
def v_n(T_K, M_gmol):
    """Neutral speed convention v_n = sqrt(2 k T / m) (DM2008 p. 14, as carried by the scaling lane)."""
    return math.sqrt(2.0 * C.K_B * T_K / (M_gmol * C.AMU))


M_E = 9.1093837139e-31  # CODATA 2022 electron mass (scaling_similarity.json sources.NIST_me; hardware derived_numbers)


def B_rLe(h_m, Te_eV, frac):
    """Field for mean-speed electron Larmor radius r_Le = m_e v_bar/(e B) = frac * h, v_bar = sqrt(8 e T_e/(pi m_e))
    (Goebel & Katz Eq. 7.2-1 form as used by SRC-MASMI p. 5; reproduces its 213 G at h = 8 mm, T_e = 20 eV)."""
    vbar = math.sqrt(8.0 * C.E_CHARGE * Te_eV / (math.pi * M_E))
    return M_E * vbar / (C.E_CHARGE * frac * h_m)


def r_Li(m_amu, V, B):
    """Ion Larmor radius bound r = sqrt(2 m V / e) / B (Goebel & Katz Eq. 7.2-3 as carried by the scaling lane)."""
    return math.sqrt(2.0 * m_amu * C.AMU * V / C.E_CHARGE) / B


# ------------------------------------------------------------------------------------------------ channel window
def channel_window(I):
    P_hi = I["P_alloc_W"][1]
    P_lo = a("discharge_share_min") * I["P_alloc_W"][0]
    V_lo, V_hi = min(I["V_d_set_V"]), I["V_d_rating_upper_V"]
    j_lo, j_hi = I["j_d_A_m2"]
    Cp = I["C_P_star_W_m2"]
    # EV-G6 (DM2008 Eq. 4.6): P = C_P* h d  ->  A = pi h d = pi P / C_P*
    A_CP = [math.pi * P_lo / Cp, math.pi * P_hi / Cp]
    # EV-G7 (GK2008 p. 337): A = I_d / j, with I_d <= P / V_d (bus-compliance bound, HW-ENV-02 logic)
    A_jd = [P_lo / V_hi / j_hi, P_hi / V_lo / j_lo]
    A_win = [max(A_CP[0], A_jd[0]), min(A_CP[1], A_jd[1])]
    if not A_win[0] < A_win[1]:
        raise RuntimeError("power- and current-density area rules do not overlap")
    dh = sorted([x["d_over_h"] for x in ANALOGS if "d_over_h" in x])
    dh_win = [dh[0], dh[-1]]

    def geo(A, r):
        h = math.sqrt(A / (math.pi * r))
        return h, r * h
    corners = {}
    for tag, A, r in (("A_min_dh_min", A_win[0], dh_win[0]), ("A_min_dh_max", A_win[0], dh_win[1]),
                      ("A_max_dh_min", A_win[1], dh_win[0]), ("A_max_dh_max", A_win[1], dh_win[1])):
        h, d = geo(A, r)
        corners[tag] = {"A_cm2": A * 1e4, "d_over_h": r, "h_mm": h * 1e3, "d_mean_mm": d * 1e3,
                        "OD_channel_mm": (d + h) * 1e3, "ID_channel_mm": (d - h) * 1e3}
    h_rng = [min(c["h_mm"] for c in corners.values()), max(c["h_mm"] for c in corners.values())]
    d_rng = [min(c["d_mean_mm"] for c in corners.values()), max(c["d_mean_mm"] for c in corners.values())]
    od_rng = [min(c["OD_channel_mm"] for c in corners.values()), max(c["OD_channel_mm"] for c in corners.values())]
    id_rng = [min(c["ID_channel_mm"] for c in corners.values()), max(c["ID_channel_mm"] for c in corners.values())]

    # density rule (EV-G5; xenon critical density, a hypothesis for air species) at the delivered flows
    Tn = a("T_n_K")
    masses = {"flight_mix": I["molar_mass_flight_gmol"], "N2": [C.M_SPECIES["N2"] / C.AMU] * 2}
    w = I["w_O_element"]
    mO2, mN2 = C.M_SPECIES["O2"] / C.AMU, C.M_SPECIES["N2"] / C.AMU
    masses["S-O2E_ground"] = sorted([1.0 / (x / mO2 + (1 - x) / mN2) for x in w])
    flows = {"design_case_min": I["mdot_design_case_kgps"][0], "design_case_max": I["mdot_design_case_kgps"][1],
             "delivered_max_A5": I["mdot_A5_quote_kgps"]}
    n_ref = {"n_crit_Xe": I["n_crit_Xe_m3"], "ECHT_max": I["n_n_ECHT_m3"][1]}
    A_nc = {}
    for fk, md in flows.items():
        vals = []
        for mk, mr in masses.items():
            for Mg in mr:
                for T in Tn:
                    for nk, n in n_ref.items():
                        vals.append(md / (n * Mg * C.AMU * v_n(T, Mg)))
        A_nc[fk] = [min(vals) * 1e4, max(vals) * 1e4]
    # neutral density inside the area window at each flow (the low-flow argument)
    nn = {}
    for fk, md in flows.items():
        vals = []
        for mk, mr in masses.items():
            for Mg in mr:
                for T in Tn:
                    for A in A_win:
                        vals.append(md / (A * Mg * C.AMU * v_n(T, Mg)))
        nn[fk] = {"n_n_m3": [min(vals), max(vals)],
                  "n_n_over_n_crit_Xe": [min(vals) / I["n_crit_Xe_m3"], max(vals) / I["n_crit_Xe_m3"]]}

    # length: extended channel rules
    conv = [x for x in ANALOGS if x["id"] in ("AN-Z70", "AN-MASMI")]
    lh_conv = sorted(x["L_over_h"] for x in conv)
    lam = I["lambda_ratio_N2_Xe"]
    LH_equal_ne = [lh_conv[0] * lam[0], lh_conv[-1] * lam[1]]
    LH_ECHT = 8.6
    LH_win = [max(LH_ECHT, LH_equal_ne[0]), a("LH_upper")]
    L_rng = [LH_win[0] * h_rng[0], LH_win[1] * h_rng[1]]
    # residence time tau = L / v_n
    vn_all = [v_n(T, Mg) for mr in masses.values() for Mg in mr for T in Tn]
    tau = [L_rng[0] * 1e-3 / max(vn_all), L_rng[1] * 1e-3 / min(vn_all)]

    return {
        "P_d_band_W": [P_lo, P_hi], "V_d_band_V": [V_lo, V_hi],
        "area_rules_cm2": {
            "A_CP": {"value": [x * 1e4 for x in A_CP], "rule": "EV-G6 DM2008 Eq. 4.6: P = C_P* h d, A = pi h d; "
                     "C_P* = 1.2e6 W/m2 (xenon empirical)", "applicability": "xenon database; N2/O/O2 transfer is a "
                     "hypothesis (evidence level 6)"},
            "A_jd": {"value": [x * 1e4 for x in A_jd], "rule": "EV-G7 GK2008 p. 337: j = 0.10-0.15 A/cm2 typical, "
                     "A = I_d / j with the bus bound I_d <= P / V_d", "applicability": "xenon SPT family; transfer "
                     "to air species a hypothesis; I_d is a bound, not a predicted current"},
            "A_ncXe_by_flow": {"value": A_nc, "rule": "EV-G5 DM2008 Eq. 2.7 / DM2011 p. 241: mdot = n m v_n A with "
                               "n between the xenon critical density 1.2e19 m^-3 and the ECHT-N2 anchor upper value",
                               "applicability": "xenon critical density applied to air species is a hypothesis "
                                                "(scaling TR-14)"},
        },
        "area_window_cm2": [x * 1e4 for x in A_win],
        "area_window_rule": "intersection of A_CP and A_jd (both power-allocation bounded); A_ncXe is reported per "
                            "flow, not intersected (the delivered flow spans a factor ~8.5)",
        "d_over_h_window": dh_win,
        "d_over_h_sources": {x["id"]: x["d_over_h"] for x in ANALOGS if "d_over_h" in x},
        "corners": corners,
        "h_mm": h_rng, "d_mean_mm": d_rng, "OD_channel_mm": od_rng, "ID_channel_mm": id_rng,
        "molar_mass_gmol": masses, "flows_kgps": flows, "neutral_density_in_window": nn,
        "L_over_h_rules": {
            "ECHT_analog": LH_ECHT,
            "equal_ne_ionization_length": {"value": LH_equal_ne, "rule": "L/h of conventional xenon-class analogs "
                                           "(Z-70 1.53, MaSMi 2.0) x lambda_i(N2)/lambda_i(Xe) at equal n_e, T_e, "
                                           "T_n (scaling TR-01, T_e 5-30 eV); a longer channel OR higher n_e meets "
                                           "the N2 demand (GK2008 p. 336 Eq. 7.2-19: lighter propellants need a "
                                           "longer ionization region)",
                                           "lambda_ratio_range": lam, "conventional_L_over_h": lh_conv},
        },
        "L_over_h_window": LH_win, "L_mm": L_rng, "residence_time_s": tau,
    }


# ------------------------------------------------------------------------------------------------ B target
SPECIES_AMU = {"N+": 14.0, "O+": 16.0, "N2+": 28.0, "O2+": 32.0, "Xe+": 131.3}  # abep_sim/constants.py masses


def b_target(ch, I):
    f = a("rLe_fraction_of_h")
    Te = a("T_e_criterion_eV")
    h_lo, h_hi = ch["h_mm"][0] * 1e-3, ch["h_mm"][1] * 1e-3
    tab = {str(int(t)): {"h_min_G": B_rLe(h_lo, t, f) * 1e4, "h_max_G": B_rLe(h_hi, t, f) * 1e4} for t in Te}
    target = [B_rLe(h_hi, 20.0, f) * 1e4, B_rLe(h_lo, 30.0, f) * 1e4]
    cap = a("B_headroom_factor") * target[1]
    # MaSMi reproduction check (p. 5: 213 G for h = 8 mm, T_e = 20 eV)
    masmi = B_rLe(8e-3, 20.0, f) * 1e4
    # ion Larmor radius at the MC-1 capability vs the FULL channel length (conservative; the relevant length is the
    # magnetized length from FEMM B(z))
    V_lo = min(I["V_d_set_V"])
    rli = {}
    for sp, m in SPECIES_AMU.items():
        r = r_Li(m, V_lo, cap * 1e-4)
        rli[sp] = {"r_Li_m": r, "r_Li_over_L_min": r / (ch["L_mm"][0] * 1e-3),
                   "r_Li_over_L_max": r / (ch["L_mm"][1] * 1e-3)}
    return {"rLe_rule_table_G": tab, "target_peak_Br_G": target, "capability_G": cap, "masmi_check_G": masmi,
            "ion_larmor_at_capability_Vd_min": {"V_d_V": V_lo, "B_G": cap, "species": rli}}


# ------------------------------------------------------------------------------------------------ coil design
def coil_case(name, d_mm, h_mm, L_mm, B_cap_G, bore_d_mm, t_w_mm, w_p_mm, k_leak, f_NI):
    """Lumped magnetic circuit + integer-turn coils for one geometry (every argument explicit)."""
    mu_r = a("mu_r_core")
    fw = a("B_work_fraction_of_Bsat")
    B_ic = fw * MATERIALS["Hiperco_50"]["B_sat_T"][0]      # inner core / inner pole: Hiperco 50 (PRELIMINARY)
    B_fe = fw * MATERIALS["ARMCO_pure_iron"]["B_sat_T"][0]  # back plate, outer core, outer pole: pure iron
    c = a("gap_clearance_mm")
    R = d_mm / 2.0
    r_in, r_out = R - h_mm / 2.0, R + h_mm / 2.0
    g = h_mm + 2.0 * t_w_mm + 2.0 * c
    B_g = B_cap_G * 1e-4
    A_g = 2.0 * math.pi * R * 1e-3 * w_p_mm * 1e-3
    phi_core = k_leak * B_g * A_g
    # inner core (Hiperco) with the central-cathode bore
    r_b = bore_d_mm / 2.0
    A_ic = phi_core / B_ic
    r_c = math.sqrt((r_b * 1e-3) ** 2 + A_ic / math.pi) * 1e3
    inner_build = (r_in - t_w_mm - a("screen_mm")) - (r_c + a("bobbin_mm"))
    feasible_LC = inner_build >= a("inner_coil_min_build_mm")
    out = {"name": name, "d_mean_mm": d_mm, "h_mm": h_mm, "L_mm": L_mm, "B_gap_G": B_cap_G,
           "cathode_bore_d_mm": bore_d_mm, "t_wall_mm": t_w_mm, "pole_tip_w_mm": w_p_mm, "leakage_factor": k_leak,
           "NI_margin_factor": f_NI, "gap_mm": g, "gap_area_m2": A_g, "core_flux_Wb": phi_core,
           "inner_core_r_mm": r_c, "inner_coil_build_mm": inner_build, "central_cathode_feasible": feasible_LC,
           "B_work_inner_T": B_ic, "B_work_iron_T": B_fe}
    if not feasible_LC:
        out["status"] = ("INFEASIBLE for the central cathode location L-C at this geometry: inner-coil build "
                         f"{inner_build:.3g} mm < {a('inner_coil_min_build_mm')} mm")
        return out
    # return-path segments sized at the working flux density
    L_c = a("coil_axial_fraction_of_L") * L_mm
    r_oc_in = r_out + t_w_mm + 2.0 + a("outer_coil_build_mm") + 1.0
    A_oc = phi_core / B_fe
    t_oc = max(a("outer_core_mm_min"), A_oc / (2.0 * math.pi * r_oc_in * 1e-3) * 1e3)
    A_oc = 2.0 * math.pi * (r_oc_in + t_oc / 2.0) * 1e-3 * t_oc * 1e-3
    R_body = r_oc_in + t_oc
    r_bp_mid = 0.5 * (r_c + R_body)
    t_bp = max(a("back_plate_mm_min"), phi_core / B_fe / (2.0 * math.pi * r_bp_mid * 1e-3) * 1e3)
    t_pole = w_p_mm
    segs = [
        MP.CoreSegment("inner core (Hiperco 50)", (L_mm + t_bp) * 1e-3, A_ic, mu_r, B_ic * 1.0000001),
        MP.CoreSegment("back plate (pure iron)", (R_body - r_c) * 1e-3,
                       2.0 * math.pi * r_bp_mid * 1e-3 * t_bp * 1e-3, mu_r, B_fe * 1.0000001),
        MP.CoreSegment("outer core (pure iron)", (L_mm + t_bp) * 1e-3, A_oc, mu_r, B_fe * 1.0000001),
        MP.CoreSegment("outer pole (pure iron)", (R_body - (r_out + t_w_mm + c)) * 1e-3,
                       max(A_oc, 2.0 * math.pi * (r_out + t_w_mm + c) * 1e-3 * t_pole * 1e-3), mu_r,
                       B_fe * 1.0000001),
        MP.CoreSegment("inner pole (Hiperco 50)", ((r_in - t_w_mm - c) - r_c) * 1e-3,
                       max(A_ic, 2.0 * math.pi * r_c * 1e-3 * t_pole * 1e-3), mu_r, B_ic * 1.0000001),
    ]
    circ = MP.ampere_turns(B_g, g * 1e-3, A_g, segs, k_leak)
    NI_total = f_NI * circ["NI_A"]
    split = a("NI_split_inner")
    coils = {}
    win = a("coil_supply_window")
    for cname, NI, r_i, build in (("inner", split * NI_total, r_c + a("bobbin_mm"), inner_build),
                                  ("outer", (1 - split) * NI_total, r_out + t_w_mm + 2.0, a("outer_coil_build_mm"))):
        A_w = build * 1e-3 * L_c * 1e-3
        l_mt = 2.0 * math.pi * (r_i + build / 2.0) * 1e-3
        opts = []
        for g_awg in a("awg_candidates"):
            dw = MP.awg_diameter_m(g_awg)
            try:
                cold = MP.coil_design(NI, A_w, a("fill_factor"), l_mt, dw, MP.ANNEALED_COPPER_IACS,
                                      a("coil_temperatures_C")[0])
                hot = MP.coil_design(NI, A_w, a("fill_factor"), l_mt, dw, MP.ANNEALED_COPPER_IACS,
                                     a("coil_temperatures_C")[1])
            except ValueError:
                continue
            ok = (win["I_A"][0] <= hot["I_A"] <= win["I_A"][1]) and (hot["V_V"] <= win["V_V"][1])
            opts.append({"awg": g_awg, "N": cold["N_turns"], "I_A": cold["I_A"], "R20_ohm": cold["R_ohm"],
                         "R200_ohm": hot["R_ohm"], "V200_V": hot["V_V"], "P20_W": cold["P_W"],
                         "P200_W": hot["P_W"], "J_A_mm2": cold["J_A_per_m2"] * 1e-6,
                         "Cu_mass_kg": cold["copper_mass_kg"], "in_supply_window": ok})
        if not opts:
            raise RuntimeError(f"{name} {cname} coil: no AWG candidate fits the winding window")
        inwin = [o for o in opts if o["in_supply_window"]]
        # inside the analog supply window: current closest to the window centre (3 A); otherwise (flagged, not
        # silent) the gauge whose 200 C current is closest to the window - the supply window is an analog rating
        if inwin:
            chosen = dict(min(inwin, key=lambda o: abs(o["I_A"] - 3.0)))
        else:
            lo, hi = win["I_A"]
            chosen = dict(min(opts, key=lambda o: max(lo - o["I_A"], o["I_A"] - hi, 0.0)))
            chosen["flag"] = "OUTSIDE the analog supply window (no candidate gauge inside); supply rating PENDING h2_4"
        P_cont20 = MP.coil_power_continuous_W(NI, A_w, a("fill_factor"), l_mt, MP.ANNEALED_COPPER_IACS, 20.0)
        P_cont200 = MP.coil_power_continuous_W(NI, A_w, a("fill_factor"), l_mt, MP.ANNEALED_COPPER_IACS, 200.0)
        coils[cname] = {"NI_A": NI, "window_radial_mm": build, "window_axial_mm": L_c, "window_area_m2": A_w,
                        "mean_turn_m": l_mt, "P_continuous_20C_W": P_cont20, "P_continuous_200C_W": P_cont200,
                        "chosen": chosen, "options": opts}
    rho_h = MATERIALS["Hiperco_50"]["density_kg_m3"][0]
    rho_fe = MATERIALS["ARMCO_pure_iron"]["density_kg_m3"][0]
    m_iron = 0.0
    for s in segs:
        m_iron += s.length_m * s.area_m2 * (rho_h if "Hiperco" in s.name else rho_fe)
    m_cu = sum(coils[k]["chosen"]["Cu_mass_kg"] for k in coils)
    P20 = sum(coils[k]["chosen"]["P20_W"] for k in coils)
    P200 = sum(coils[k]["chosen"]["P200_W"] for k in coils)
    out.update({
        "status": "SIZED (lumped model)",
        "segments": [{"name": s["name"], "B_T": s["B_T"], "mmf_A": s["mmf_A"]} for s in circ["segments"]],
        "NI_gap_A": circ["mmf_gap_A"], "NI_core_A": circ["mmf_core_A"], "NI_total_A": NI_total,
        "outer_core_t_mm": t_oc, "back_plate_t_mm": t_bp, "body_OD_mm": 2.0 * R_body,
        "coils": coils, "P_coils_20C_W": P20, "P_coils_200C_W": P200,
        "iron_mass_kg": m_iron, "copper_mass_kg": m_cu,
        "flux_margin": {"inner_core_B_over_Bsat": B_ic / MATERIALS["Hiperco_50"]["B_sat_T"][0],
                        "iron_B_over_Bsat": B_fe / MATERIALS["ARMCO_pure_iron"]["B_sat_T"][0]},
    })
    return out


def min_d_for_central_cathode(h_mm, B_cap_G, bore_d_mm, t_w_mm, w_p_mm, k_leak):
    """Smallest mean diameter (0.5 mm grid, 20-200 mm) at which the inner coil build reaches the minimum."""
    for i in range(40, 401):
        d = i * 0.5
        c = coil_case("scan", d, h_mm, 8.6 * h_mm, B_cap_G, bore_d_mm, t_w_mm, w_p_mm, k_leak, 1.0)
        if c["central_cathode_feasible"]:
            return d
    return None


def coil_design_all(ch, bt):
    rp = a("rp1_geometry")
    t_w = a("t_wall_mm")
    w_p = a("pole_tip_width_mm")
    kl = a("leakage_factor")
    fni = a("NI_margin_factor")
    bore = a("cathode_bore_diameter_mm")
    f = a("rLe_fraction_of_h")
    head = a("B_headroom_factor")
    cases = []
    # RP-1: capability for its own width at T_e = 30 eV, nominal assumptions, both NI margins
    B_rp = head * B_rLe(rp["h_mm"] * 1e-3, 30.0, f) * 1e4
    L_rp = rp["L_over_h"] * rp["h_mm"]
    for fn in fni:
        cases.append(coil_case(f"RP-1 f_NI={fn:g}", rp["d_mean_mm"], rp["h_mm"], L_rp, B_rp, bore[1], t_w[1],
                               w_p[1], kl[1], fn))
    # RP-1 worst corner of the assumptions (thick wall, wide pole, high leakage, f_NI max, window-wide capability)
    cases.append(coil_case("RP-1 worst-case assumptions", rp["d_mean_mm"], rp["h_mm"], L_rp, bt["capability_G"],
                           bore[1], t_w[2], w_p[2], kl[2], fni[1]))
    # window corners (nominal assumptions, f_NI max, own-width capability)
    for tag in ("A_min_dh_min", "A_max_dh_max", "A_max_dh_min", "A_min_dh_max"):
        cc = ch["corners"][tag]
        Bc = head * B_rLe(cc["h_mm"] * 1e-3, 30.0, f) * 1e4
        cases.append(coil_case(f"corner {tag}", cc["d_mean_mm"], cc["h_mm"], ch["L_over_h_window"][0] * cc["h_mm"],
                               Bc, bore[1], t_w[1], w_p[1], kl[1], fni[1]))
    # minimum mean diameter for a central cathode, over the h window, at the larger bore and nominal assumptions
    dmin = {}
    for hh in (ch["h_mm"][0], rp["h_mm"], ch["h_mm"][1]):
        Bc = head * B_rLe(hh * 1e-3, 30.0, f) * 1e4
        dmin[f"{hh:.4g}"] = {"bore_12mm": min_d_for_central_cathode(hh, Bc, bore[0], t_w[1], w_p[1], kl[1]),
                             "bore_18mm": min_d_for_central_cathode(hh, Bc, bore[1], t_w[1], w_p[1], kl[1])}
    return {"method": "abep_sim/magnet_power.py ampere_turns (lumped reluctance, uniform-gap field, explicit leakage "
                      "factor) + coil_design (integer turns, NBS copper R(T) 0-200 C); NI multiplied by the "
                      "explicit NI_margin_factor",
            "accuracy_limits": [
                "a Hall-thruster pole geometry is not a uniform gap: the centreline field, fringing, leakage and the "
                "shielding topology are 2-D/3-D effects; the lumped estimate can be off by a factor of order the "
                "NI_margin_factor bracket (not quantified); FEMM (axisymmetric) or 3-D magnetostatics with the "
                "supplier B-H curves is the H4 / H2-follow-up that closes it",
                "linear core permeability (mu_r = 1000 assumed) and a working-flux-density cap; saturation onset, "
                "temperature dependence of B-H and permanent-magnet options are outside the model",
                "copper R(T) valid only 0-200 C; coils hotter than 200 C (analog pole pieces reach ~475 C, "
                "SRC-MASMI p. 11) need a sourced conductor R(T) table (MCQ-TL-04): P(200 C) is then a LOWER "
                "bound of the hot I^2R",
                "coil windows use assumed builds and a 0.5 fill factor; high-temperature insulation lowers the fill"],
            "cases": cases, "min_d_mean_for_central_cathode_mm": dmin}


# ------------------------------------------------------------------------------------------------ document
def P(pid, name, value, unit, basis, source, ev, status, rep, note=None):
    d = {"id": pid, "name": name, "value": value, "units": unit, "basis": basis, "source": source,
         "evidence_class": ev, "status": status, "representativeness": rep}
    if note:
        d["note"] = note
    return d


FR, TA, GO = "FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"
TH = "docs/hardware/h2/h2_1_hall_chamber_magnet/build_h2_1_hall_chamber_magnet.py"


def build():
    pins = check_decision_pins()
    I = read_inputs()
    ch = channel_window(I)
    bt = b_target(ch, I)
    cd = coil_design_all(ch, bt)
    rp_nom = cd["cases"][0]
    rp_max = cd["cases"][1]
    rp_worst = cd["cases"][2]
    for c in (rp_nom, rp_max, rp_worst):
        if not c["central_cathode_feasible"]:
            raise RuntimeError(f"reference case {c['name']} infeasible: {c['status']}")
    Pmag = [rp_nom["P_coils_20C_W"], max(rp_max["P_coils_200C_W"], rp_worst["P_coils_200C_W"])]
    corner_P200 = [c["P_coils_200C_W"] for c in cd["cases"][3:] if c.get("P_coils_200C_W") is not None]

    inputs_hashes = {k: {"path": v, "sha256": sha256_file(v)} for k, v in REPO_INPUTS.items()}

    params = [
        P("H21-01", "channel annulus area window", sig(ch["area_window_cm2"]), "cm^2", "derived",
          f"{TH}: channel_window (intersection of EV-G6 C_P* rule and EV-G7 j_d rule over P_d "
          f"{sig(ch['P_d_band_W'])} W and V_d {ch['V_d_band_V']} V)", "model-derived", "PRELIMINARY", FR,
          "power bound from the A5 allocation (hall_discharge share PENDING docs/hardware/h2/h2_4_ppu_bus/); xenon "
          "relations, hypotheses for air species"),
        P("H21-02", "mean-diameter / width ratio window d/h", sig(ch["d_over_h_window"]), "-", "analog",
          "ANALOGS AN-Z70 (3.8), AN-MASMI (4.5), AN-CAMILA (4.08), AN-ECHT (9.0); DM2011 p. 241 h proportional "
          "to d (coefficient unpublished)", "measured (analog design dimensions)", "PRELIMINARY", FR),
        P("H21-03", "channel width h", sig(ch["h_mm"]), "mm", "derived", f"{TH}: H21-01 x H21-02 corners",
          "model-derived", "PRELIMINARY", FR),
        P("H21-04", "channel mean diameter d", sig(ch["d_mean_mm"]), "mm", "derived", f"{TH}: H21-01 x H21-02",
          "model-derived", "PRELIMINARY", FR),
        P("H21-05", "channel outer diameter (channel OD = d + h)", sig(ch["OD_channel_mm"]), "mm", "derived",
          f"{TH}", "model-derived", "PRELIMINARY", FR, "the ECHT 100 mm OD (analog, ambiguous: channel vs BN piece) "
          "lies inside; ECHT is never our design"),
        P("H21-06", "channel inner diameter (channel ID = d - h)", sig(ch["ID_channel_mm"]), "mm", "derived", f"{TH}",
          "model-derived", "PRELIMINARY", FR, "lower end constrained further by a central cathode (H21-22)"),
        P("H21-07", "channel length / width (extended channel)", sig(ch["L_over_h_window"]), "-", "analog/derived",
          "lower: ECHT L/h 8.6 (analog) = equal-n_e rule lower end (Z-70 1.53 x lambda ratio 5.61); upper: "
          "ASSUMED LH_upper (PROPOSED)", "measured (analog) / model-derived / assumed", "PRELIMINARY", FR),
        P("H21-08", "channel length L (anode face HALL_INLET_Z0 z=0 to exit plane z=L)", sig(ch["L_mm"]), "mm",
          "derived", f"{TH}: H21-07 x H21-03", "model-derived", "PRELIMINARY", FR,
          "ECHT 86 mm is a published analog only"),
        P("H21-09", "anode position", "anode/gas-distributor face at z = 0 = HALL_INLET_Z0 (lane 17 convention); "
          "fixed for all score-bearing runs", "-", "requirement", "hall_reference_v1.json geometry_interface "
          "anode_axial_position; hardware_requirements HW-H1-06", "assumed (convention)", "PRELIMINARY", FR),
        P("H21-10", "adjustable-anode development insert (spacer rings stepping L inside H21-08)",
          "optional; pre-S1 development only", "-", "analog",
          "SRC-MASMI p. 5 (channel built long to allow variable anode placement)", "measured (analog practice)",
          "PROPOSED (owner)", TA, "any L change after S1 creates H-1' (HW-H1-02); never used across a comparison"),
        P("H21-11", "exit plane", "z = L; downstream wall edges chamfered if the shielded topology is kept "
          "(H21-12)", "-", "analog", "hall_reference exit_plane_axial_position; SRC-MASMI p. 5 (chamfered edges "
          "characteristic of shielded thrusters)", "assumed / measured (analog)", "PRELIMINARY", FR),
        P("H21-12", "magnetic topology (preliminary choice)", "T2 magnetically shielded, single inner coil + single "
          "concentric outer coil, replaceable pole pieces, trim-coil provision", "-", "analog",
          "see magnetic_topology_options", "measured (analog) / abstract-only (SRC-MIKELLIDES2014)", "PRELIMINARY",
          FR, "unshielded T1 kept as a fallback via replaceable pole pieces (TEST-ARTICLE feature H21-13)"),
        P("H21-13", "replaceable pole-piece set (shielded / unshielded)", "one alternate set, same coils", "-",
          "assumed", "this lane", "assumed", "PROPOSED (owner)", TA, "switching sets creates H-1' (HW-H1-02)"),
        P("H21-14", "peak centreline B_r target envelope (at/near exit)", sig(bt["target_peak_Br_G"]), "G",
          "derived/analog", f"{TH}: r_Le <= 0.1 h at T_e 20 eV (h max) .. 30 eV (h min); analog span 85-218 G "
          "(ANALOGS)", "model-derived (criterion) / measured+digitized (analogs)", "PRELIMINARY", FR,
          "a design target envelope, not a transport optimization"),
        P("H21-15", "MC-1 field capability", sig(bt["capability_G"]), "G", "assumed/derived",
          "B_headroom_factor x H21-14 upper", "model-derived", "PRELIMINARY", FR),
        P("H21-16", "B_r(z) shape: gradient and anode region", "monotonic rise toward the exit, peak at or just "
          "downstream of z = L; field near the anode as low as the circuit allows (numeric B_anode/B_peak TBD)",
          "-", "analog", "hall_reference EV-B1 (GK2008 pp. 329, 331), EV-B5 (GK2008 p. 335); ECHT plateau "
          "(EV-B6) recorded as the alternative published extended-channel practice", "inferred",
          "TBD - requires FEMM B(z) of the preliminary circuit and an owner tolerance", FR),
        P("H21-17", "total ampere-turns (RP-1, f_NI 1..2)", sig([rp_nom["NI_total_A"], rp_max["NI_total_A"]]), "A",
          "derived", f"{TH}: coil_design_all cases RP-1", "model-derived", "PRELIMINARY", FR),
        P("H21-18", "coil power at the terminals (sum inner + outer) RP-1: 20 C nominal .. 200 C upper-assumption "
          "case", sig(Pmag), "W", "derived", f"{TH}: magnet_power.coil_design", "model-derived",
          "PRELIMINARY (hot > 200 C TBD)", FR, "hot-coil I^2R above 200 C requires a sourced conductor R(T) "
          "(MCQ-TL-04)"),
        P("H21-19", "coil temperature class", "high-temperature class: ceramic/glass-insulated (Ni-clad) Cu "
          "candidate MCQ-EM-03 (-267.8..537.8 C continuous) preferred over polyimide MW 16-C (240 C material "
          "class)", "-", "analog", "magnet_coil_qualification_v1.json MCQ-EM-01/03; SRC-MASMI p. 5 (Ni-plated "
          "fiberglass Cu 'rated to over 400 C'), p. 11 (front pole ~475 C)", "assumed (supplier ratings) / "
          "measured (analog temperatures)", "PRELIMINARY (owner MCQ-OQ-02)", FR,
          "a Ni cladding is ferromagnetic: HW-MC-12 map check"),
        P("H21-20", "inner core / inner pole material", "Hiperco 50 (Fe-49Co-2V)", "-", "analog",
          "SRC-HIPERCO50 pp. 1-3; SRC-MASMI p. 5 (iron saturates at small scale; Hiperco chosen)",
          "measured (supplier-typical)", "PRELIMINARY (owner HWQ-18 / MCQ-OQ-05)", FR),
        P("H21-21", "outer core, back plate, outer pole material", "high-purity iron (ARMCO class)", "-", "analog",
          "SRC-ARMCO PDF p. 9", "measured (supplier-typical)", "PRELIMINARY (owner HWQ-18 / MCQ-OQ-05)", FR),
        P("H21-22", "minimum mean diameter for a central cathode (bore 12-18 mm)",
          cd["min_d_mean_for_central_cathode_mm"], "mm", "derived", f"{TH}: min_d_for_central_cathode",
          "model-derived", "PENDING docs/hardware/h2/h2_2_cathode_integration/ (bore)", FR),
        P("H21-23", "working flux density / saturation", {"Hiperco_50": a("B_work_fraction_of_Bsat"),
          "iron": a("B_work_fraction_of_Bsat")}, "-", "assumed", "ASSUMED B_work_fraction_of_Bsat", "assumed",
          "PROPOSED", FR),
        P("H21-24", "iron + copper mass of MC-1 (RP-1, f_NI 2)", {"iron_kg": sig(rp_max["iron_mass_kg"]),
          "copper_kg": sig(rp_max["copper_mass_kg"])}, "kg", "derived", f"{TH}", "model-derived",
          "PRELIMINARY (excludes channel ceramics, anode, structure; PENDING docs/hardware/h2/h2_7_mechanical_bom/)",
          FR, "the coils fill the whole assumed winding window (minimum-I^2R design); a smaller window trades copper "
              "mass for coil power - a FEMM / H2-7 mass-power trade"),
        P("H21-25", "MC-1 body outer diameter (RP-1, f_NI 2)", sig(rp_max["body_OD_mm"]), "mm", "derived", f"{TH}",
          "model-derived", "PRELIMINARY", FR),
        P("H21-26", "neutral residence time L / v_n", sig(ch["residence_time_s"]), "s", "derived",
          f"{TH}: L window / v_n(T_n 300-800 K, flight mix / N2 / S-O2E)", "model-derived", "PRELIMINARY", FR),
        P("H21-27", "coil supply channels", "inner, outer, trim (3), current-controlled, current recorded per "
          "reading", "-", "requirement", "hardware_requirements HW-MC-02; MCQ-W4-02", "assumed (requirement)",
          "PRELIMINARY", FR),
        P("H21-28", "reference field sensor on MC-1 outside the plasma + coil 4-wire leads + hot-spot TCs",
          "provisions", "-", "requirement", "HW-MC-04, HW-MC-14, MCQ-W4-01", "assumed (requirement)",
          "PRELIMINARY", TA, "flight units may keep only coil voltage/current telemetry (owner)"),
        P("H21-29", "Hall-probe access path from beyond the exit plane to the anode face", "provision", "-",
          "requirement", "HW-H1-08", "assumed (requirement)", "PRELIMINARY", TA,
          "the probe and its drive are GROUND/FACILITY-ONLY (docs/hardware/h2/h2_6_diagnostics_fixture/)"),
    ]

    topology = [
        {"id": "T1", "name": "unshielded conventional: inner coil + single concentric outer coil (or discrete outer "
                              "coils), pole pieces at the exit, field lines crossing the walls near the exit",
         "wall_life_consequence": "highest wall-erosion exposure; the only published air-species channel-life figure "
                                  "is an unshielded PPS1350 on N2/O2 + 10 % Xe: 7,000-9,500 h authors' estimate "
                                  "(0.47-0.63 of the 15,000 h requirement; second-hand, engineering estimate, "
                                  "RI-LIFE-HALL-CHANNEL-AIR-EROSION, veto_layer_v1.json); no N/O sputter yield on "
                                  "BN/BN-SiO2/SiC (WALL_LIFE_EVIDENCE.md)",
         "modelling_support": "hall_map_schema_v1 wall_life_trustworthy requires 'unshielded' (hall_reference "
                              "wall_life_interface) - only after a closure is admitted",
         "status": "FALLBACK"},
        {"id": "T2", "name": "magnetically shielded: field lines curve around the downstream wall edges and follow "
                              "the walls toward the anode (SRC-MASMI p. 4), chamfered wall edges, single inner + single "
                              "outer coil (no separatrix, SRC-MASMI pp. 8-9)",
         "wall_life_consequence": "xenon evidence: erosion reduced by 'at least a few orders of magnitude' "
                                  "(SRC-MIKELLIDES2014 abstract, 6 kW lab thruster) and ~3 orders at 325 W "
                                  "(SRC-MASMI p. 1) with weaker inner-wall shielding 'likely due to magnetic circuit "
                                  "saturation' (pp. 1, 13); air-species counter-indicator: shielded HT5k DM2 on "
                                  "N2/O2 'seems effective', 10 h, qualitative (RI-LIFE-HALL-SHIELDED-COUNTER). "
                                  "Shielding does not address anode oxidation (E07: flame-outs after ~314 h) or "
                                  "pole-face exposure (AO register AOL-WC-04 witness pair)",
         "modelling_support": "HallThruster.jl shielded flag not wired in the bridge; a shielded design has no wall "
                              "fields under hall_map_schema_v1: wall life is evidenced by test only (A5 risk 2 "
                              "response)",
         "risks": ["no published extended-channel shielded device with geometry was found (hall_sustainment matrix)",
                   "small-scale saturation of the inner core/pole (SRC-MASMI), aggravated by a central-cathode bore "
                   "(H21-22)"],
         "status": "PRELIMINARY CHOICE"},
        {"id": "T3", "name": "trim coil (rear/inner) added to T1 or T2 to shape the upstream gradient / anode region",
         "wall_life_consequence": "none directly", "status": "PROVISION (winding space + supply channel)",
         "note": "no accessed source quantifies a trim coil for this class: verify"},
        {"id": "T4", "name": "permanent-magnet circuit (0 W, HM-PM-OPTION)",
         "wall_life_consequence": "as T1/T2 by topology",
         "status": "NOT FOR H-1 (preliminary): the S1b coil-current scan (HW-MC-05) and B(z)-vs-current traceability "
                   "(MCQ-OQ-01) need an electromagnet; a flight PM variant stays an owner question"},
    ]
    why = ("A5 architecture-closing risk 2 (oxygen/anode/channel lifetime) is the only ranked life risk and the one "
           "air-species channel-life figure is 0.47-0.63 of the requirement on unshielded hardware; shielding is the "
           "published design lever that moves channel erosion by orders of magnitude on xenon and has a qualitative "
           "air-species counter-indicator. It is chosen PRELIMINARILY because H-1 must be flight-representative "
           "(HW-H1-01): the Phase-1 sustainment result should be obtained on the channel/field topology the flight "
           "unit would carry. The fallback (T1) is kept buildable with the same coils via a replaceable pole set, "
           "because shielding at small scale is saturation-limited and no extended-channel shielded analog exists.")

    bz = {
        "target_peak_Br_G": sig(bt["target_peak_Br_G"]),
        "capability_G": sig(bt["capability_G"]),
        "rLe_rule_table_G": sig(bt["rLe_rule_table_G"]),
        "masmi_reproduction_G": sig(bt["masmi_check_G"]),
        "masmi_reported_G": 213.0,
        "analog_magnitudes": [{"id": x["id"], "B_G": x["B_G"], "source": x["source"],
                               "evidence_class": x["evidence_class"]} for x in ANALOGS if "B_G" in x],
        "gradient": "dB_r/dz > 0 toward the exit inside the channel (EV-B1, EV-B5); numeric gradient TBD - FEMM",
        "anode_region": "low-field region over the upstream channel: with L/h >= 8.6 and the magnetized region set "
                        "by the exit pole gap (~h + walls), the anode lies several gap lengths upstream (geometric "
                        "argument, inferred); B_anode/B_peak numeric target TBD - FEMM + owner. The ECHT measured a "
                        "plateau (EV-B6), a different published practice",
        "peak_position": "at or just downstream of the exit plane (EV-B1); tolerance TBD - FEMM + owner",
        "ion_larmor_check": sig(bt["ion_larmor_at_capability_Vd_min"]),
        "ion_larmor_note": "r_Li at the capability field and the lowest V_d, divided by the FULL channel length "
                           "(conservative). Values near or below ~1 for N+/O+ in the longest channels flag that the "
                           "magnetized length (not the channel length) must satisfy r_Li >> L_mag (EV-B2); checked on "
                           "the FEMM B(z); not a veto",
        "not_a_transport_optimization": True,
    }

    materials = {
        "candidates": {
            k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in MATERIALS.items()
        },
        "preliminary_choice": {"inner core + inner pole": "Hiperco_50", "back plate, outer core, outer pole":
                               "ARMCO_pure_iron"},
        "flux_margin_RP1": sig(rp_max["flux_margin"]),
        "max_use_temperature": "no supplier maximum-use temperature for magnetic service was found in either sheet; "
                               "Curie 770 C (iron, secondary, verify) / 938 C (Hiperco 50) are upper physical bounds, "
                               "the working limit is the B-H at the pole temperature (HW-MC-13, TBD - requires "
                               "supplier B-H vs temperature and the H2-5 pole temperature)",
        "O_O2_exposure": [
            "pure iron and FeCo oxidize: ARMCO only claims better oxidation resistance than normal steels (SRC-ARMCO PDF p. 3); "
            "Hiperco 50 must be annealed in dry H2 or vacuum 'to minimize oxide contamination' (SRC-HIPERCO50 p. 5) - oxide "
            "growth in an O/O2 plume is expected (inferred) and its effect on B-H and outgassing is unmeasured",
            "pole faces facing the plume need a protective coating or ceramic cover; qualification by the "
            "MC-1 witness pair (HW-MC-06, AOL-WC-04) and ground AO exposure (AOL-EX-02); TBD",
            "an oxide layer or coating on the pole face does not change the circuit reluctance materially if thin "
            "(inferred); any spalling contaminates the channel - inspection at each block boundary (HW-H1-13)"],
    }

    interface_demands = [
        {"from": "H2-1", "to": "docs/hardware/h2/h2_4_ppu_bus/ (hall_magnet, PS-C)",
         "quantity": "hall_magnet load at the coil terminals (sum of coils)", "value": sig(Pmag), "units": "W",
         "status": "PRELIMINARY (20 C nominal .. 200 C upper-assumption case; > 200 C TBD)"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_4_ppu_bus/ (PS-C)", "quantity": "coil supply channels",
         "value": "3 (inner, outer, trim), current control, per-channel I and V telemetry", "units": "-",
         "status": "PRELIMINARY"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_4_ppu_bus/ (PS-C)", "quantity": "per-coil current / voltage at "
         "200 C (RP-1, chosen gauge)",
         "value": {k: {"I_A": sig(v["chosen"]["I_A"]), "V200_V": sig(v["chosen"]["V200_V"])}
                   for k, v in rp_max["coils"].items()}, "units": "A, V",
         "status": "PRELIMINARY (inside the analog 1-5 A / 1-12 V window)"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_5_thermal_network/", "quantity": "coil heat (= I^2R) into MC-1",
         "value": sig(Pmag), "units": "W", "status": "PRELIMINARY"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_5_thermal_network/", "quantity": "temperature limits",
         "value": {"coil_EIS": "MW 16-C 240 C material class or ceramic wire 537.8 C continuous (MCQ-EM-01/03; "
                               "class vs hot spot, MCQ-QT-06)",
                   "pole_core": "Curie 770 C iron (verify) / 938 C Hiperco 50 as absolute bounds; working limit TBD "
                                "(HW-MC-13)"}, "units": "degC", "status": "PRELIMINARY"},
        {"from": "docs/hardware/h2/h2_5_thermal_network/", "to": "H2-1", "quantity": "coil hot-spot and pole "
         "temperatures", "value": None, "units": "degC",
         "status": "PENDING docs/hardware/h2/h2_5_thermal_network/ (closes R_hot and B(T))"},
        {"from": "docs/hardware/h2/h2_2_cathode_integration/", "to": "H2-1", "quantity": "inner-core bore diameter "
         "for C-1 (central location L-C)", "value": a("cathode_bore_diameter_mm"), "units": "mm",
         "status": "PENDING docs/hardware/h2/h2_2_cathode_integration/"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_2_cathode_integration/", "quantity": "minimum channel mean "
         "diameter for which a central bore keeps the inner coil buildable and the Hiperco inner core at the working "
         "flux density", "value": cd["min_d_mean_for_central_cathode_mm"], "units": "mm",
         "status": "PRELIMINARY (lumped model; FEMM confirms)"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_2_cathode_integration/", "quantity": "field at the C-1 orifice",
         "value": "axial on the axis by symmetry (H2-2 derivation); magnitude TBD - requires FEMM of the preliminary "
                  "circuit", "units": "G", "status": "TBD"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_7_mechanical_bom/", "quantity": "H-1/MC-1 envelope and mass "
         "(RP-1, f_NI 2)", "value": {"body_OD_mm": sig(rp_max["body_OD_mm"]), "length_mm": sig(rp_max["L_mm"] +
                                                                                             rp_max["back_plate_t_mm"]),
                                     "iron_kg": sig(rp_max["iron_mass_kg"]), "copper_kg": sig(rp_max["copper_mass_kg"])},
         "units": "mm, kg", "status": "PRELIMINARY (magnetic parts only)"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_3_gas_path_plenum/", "quantity": "anode/gas-distributor annulus "
         "at HALL_INLET_Z0 (z = 0): width and mean diameter", "value": {"h_mm": sig(ch["h_mm"]),
                                                                       "d_mean_mm": sig(ch["d_mean_mm"])},
         "units": "mm", "status": "PRELIMINARY (distributor belongs to H-1, HW-H1-06)"},
        {"from": "H2-1", "to": "docs/interfaces/preionizer_module/ (PMI-09)", "quantity": "permitted module-induced "
         "field change in the channel epsilon_B", "value": None, "units": "-",
         "status": "PENDING docs/interfaces/preionizer_module/ (PMI-09; owner INV-B3)"},
        {"from": "H2-1", "to": "docs/interfaces/preionizer_module/ (PMI-09)", "quantity": "MC-1 leakage field at IP-DN "
         "and inside the module slot (upstream of the back plate)", "value": None, "units": "G",
         "status": "TBD - requires FEMM of the preliminary circuit"},
        {"from": "H2-1", "to": "docs/interfaces/preionizer_module/ + H-1 IP-DN", "quantity": "axial distance IP-DN -> "
         "HALL_INLET_Z0 (back plate + distributor)", "value": {"back_plate_t_mm_RP1": sig(rp_max["back_plate_t_mm"]),
                                                               "distributor_depth_mm": None}, "units": "mm",
         "status": "PRELIMINARY / distributor depth PENDING docs/hardware/h2/h2_3_gas_path_plenum/"},
        {"from": "H2-1", "to": "docs/hardware/h2/h2_6_diagnostics_fixture/", "quantity": "Hall-probe path length "
         "(anode face to beyond exit) and MC-1 reference-sensor / coil thermocouple / 4-wire provisions",
         "value": {"channel_L_mm": sig(ch["L_mm"])}, "units": "mm", "status": "PRELIMINARY (downstream extent "
                                                                                    "PENDING cathode position)"},
        {"from": "H2-1", "to": "docs/budgets/subsystem_maturity/ (M16)", "quantity": "rows 'extended-channel Hall "
         "discharge chamber/accelerator' and 'magnetic circuit'", "value": "see m16_rows", "units": "-",
         "status": "PROPOSED"},
        {"from": "H2-1", "to": "docs/experiments/lifetime_ao/ (AOL-WC-04)", "quantity": "pole/core grades for the "
         "witness pair", "value": ["Hiperco_50", "ARMCO_pure_iron"], "units": "-", "status": "PRELIMINARY"},
    ]

    hard = {
        "verdict": "none found",
        "checked": [
            {"item": "channel window exists inside the A5 power allocation", "result": "yes: area rules overlap "
             f"({sig(ch['area_window_cm2'])} cm^2)", "evidence_class": "model-derived"},
            {"item": "magnet power vs bus allocation", "result": f"hall_magnet {sig(Pmag)} W at <= 200 C vs 1.30-1.35 "
             "kW; small, but hot > 200 C unbounded until MCQ-TL-04 - not a veto", "evidence_class": "model-derived"},
            {"item": "iron saturation at the reference geometry", "result": "inner core sized at 0.7 Bsat Hiperco "
             "50; central cathode feasible above the H21-22 diameter; below it the choice is L-E external cathode or "
             "a larger d - a design constraint, not an architecture veto", "evidence_class": "model-derived"},
            {"item": "Curie / temperature limits", "result": "analog pole temperatures ~475 C (SRC-MASMI) are below "
             "the Curie points 770/938 C; B-H at temperature TBD", "evidence_class": "measured (analog) / supplier"},
            {"item": "ion non-magnetization with an extended channel", "result": "r_Li/L (full length, capability "
             "field, lowest V_d) can fall near 1 for N+/O+; must be checked on L_mag from FEMM - flag, not veto",
             "evidence_class": "model-derived"},
            {"item": "coil temperature class", "result": "ceramic-insulated wire rated 537.8 C continuous exists "
             "(MCQ-EM-03); life basis at hot spot TBD (MCQ-QT-01)", "evidence_class": "assumed (supplier rating)"},
            {"item": "pre-ionizer magnetic interaction", "result": "ECR 875 G resonance field (HW-PIM-06) vs Hall "
             "~100-270 G target: a module-side constraint gated by PMI-09 / INV-B3; MC-1 common to all arms",
             "evidence_class": "model-derived"},
            {"item": "O/O2 exposure of the magnetic circuit", "result": "oxidation expected, unmeasured; mitigated by "
             "covers/coatings, qualified by witness coupons - no evidence of incompatibility",
             "evidence_class": "inferred"},
        ],
    }

    blockers = [
        {"blocker": 1, "touched": True,
         "how": "H-1 is the hardware on which Hall-only sustainment at the actual feed state is measured. This lane "
                "shows that one fixed channel cannot keep the analog neutral-density band across the delivered-flow "
                "range (factor ~8.5 between design-case minimum and the delivered maximum); the knee test therefore "
                "measures the design, and the MC-1 capability (H21-15) gives the coil-current scan room. It informs, "
                "does not resolve, blocker 1; no sustainment prediction is made"},
        {"blocker": 2, "touched": True,
         "how": "MC-1 and hall_magnet are common to hall_only, rf_hall and ecr_hall (same bus component, same "
                "schedule, HW-MC-01); the permitted module field change is PMI-09 (PENDING). No bias between arms "
                "is introduced by this lane"},
        {"blocker": 3, "touched": True,
         "how": "indirectly: the central-cathode bore (H21-22) and the field at the C-1 orifice (TBD) are H2-2 inputs; "
                "no Xe quantity is set here"},
    ]

    m16 = [
        {"subsystem": "extended-channel Hall discharge chamber/accelerator", "proposed_state": "BLOCKED",
         "blocking_item": "owner selection of the channel design point (h, d, L) inside the H2-1 preliminary window "
                          "(H21-01..08), which the H-1 design release and drawing need",
         "rollup_category": "hardware-definition blocker"},
        {"subsystem": "magnetic circuit", "proposed_state": "BLOCKED",
         "blocking_item": "axisymmetric magnetostatic (FEMM-class) analysis of the preliminary MC-1 circuit at the "
                          "chosen design point (closes NI margin, leakage, B(z) shape, orifice field, IP-DN leakage)",
         "rollup_category": "hardware-definition blocker"},
    ]

    h3 = [
        {"item": "Hiperco 50 plate for inner core / inner pole", "long_lead": True,
         "spec_level_needed": "grade, form (plate; bar not listed in the accessed sheet), thickness >= inner-core "
                              "diameter or segmented, magnetic anneal 704-871 C dry H2/vacuum, lot traceability "
                              "(HW-H1-14)", "reference": "SRC-HIPERCO50 (reference only; no supplier contact)"},
        {"item": "high-purity iron bar/plate for outer core, back plate, outer pole", "long_lead": False,
         "spec_level_needed": "grade, anneal, lot", "reference": "SRC-ARMCO (reference only)"},
        {"item": "high-temperature magnet wire (ceramic-insulated Ni-clad Cu) + potting", "long_lead": True,
         "spec_level_needed": "gauge from coil_design (RP-1 chosen AWG), length = N x mean turn x margin, class vs "
                              "measured hot spot, outgassing screen (MCQ-QT-03)",
         "reference": "magnet_coil_qualification_v1.json MCQ-EM-03/04"},
        {"item": "channel ceramic rings (BN / BN-SiO2 class)", "long_lead": True,
         "spec_level_needed": "grade (owner HW-H1-04), ID/OD/length within H21-03..08, replaceable exit rings",
         "reference": "hardware_requirements HW-H1-04, HW-H1-10"},
        {"item": "3-channel current-controlled coil supplies", "long_lead": False,
         "spec_level_needed": "per H2-4 interface demands", "reference": "PENDING docs/hardware/h2/h2_4_ppu_bus/"},
    ]

    h4 = [
        {"stage": "bench (before S1a)", "measure": "cold B(z) at several coil currents on MC-1 alone; NI vs B slope",
         "closes": ["H21-14", "H21-15", "H21-17", "NI_margin_factor", "leakage_factor"]},
        {"stage": "bench (before S1)", "measure": "coil resistance vs temperature, hot-spot vs average offset "
         "(MCQ-QT-06) in vacuum at the design current", "closes": ["H21-18", "H21-19"]},
        {"stage": "S1a", "measure": "B(z) maps at the operating currents per configuration and control state "
         "(HW-MC-03); M0 vs M0b (PMI-09)", "closes": ["H21-16", "PMI-09 epsilon_B admissibility"]},
        {"stage": "S1", "measure": "coil and pole temperatures while firing; reference-sensor B drift (HW-MC-04/15)",
         "closes": ["H21-18 hot", "H21-23"]},
        {"stage": "S1b", "measure": "coil-current scan S_B = d ln(T/P_bus)/d ln B on HW-0 (HW-MC-05)",
         "closes": ["H21-15 adequacy"]},
        {"stage": "Phase 1", "measure": "wall/pole-face inspection and witness coupons after O-bearing blocks "
         "(HW-H1-13, AOL-WC-04); anode inspection", "closes": ["H21-12 wall-life consequence (evidence, not life)"]},
    ]

    milestones = {
        "A": "SUPPORTS as a precondition: a buildable H-1/MC-1 preliminary sizing inside the A5 allocations, common "
             "to hall_only / rf_hall / ecr_hall; a conditional selection can state 'provided H-1 is built within "
             "the H2-1 window and MC-1 reaches the H21-15 capability'",
        "B": "NOT SUPPORTED directly: needs the measured B(z) of the built circuit (W5 held-out input), an admitted "
             "transport closure (credible set empty) and the Vyovrinda geometry release",
        "C": "INPUTS ONLY: coil power/heat, magnetic mass and materials for the PDR budgets; life needs test evidence",
    }

    doc = {
        "schema": "h2_design_lane_v1",
        "id": "H2-1",
        "title": "H2-1 Hall chamber + magnetic circuit preliminary sizing (H-1 / MC-1)",
        "lane": "fo_h2_1_hall_chamber_magnet",
        "trigger": "T_H2_1_HALL_CHAMBER_MAGNET",
        "status": "PRELIMINARY_DRAFT_FOR_OWNER_REVIEW",
        "date": DATE,
        "base_commit": BASE_COMMIT,
        "generated_by": TH,
        "architectures": list(ARCHS),
        "configuration_items": ["H-1", "MC-1"],
        "interface_planes": ["IP-DN", "HALL_INLET_Z0"],
        "owner_decisions": pins,
        "repository_inputs": inputs_hashes,
        "hard_statements": [
            "not an architecture-selection lane: no winner among hall_only, rf_hall, ecr_hall",
            "no performance prediction: no thrust, efficiency, discharge current or plasma state is predicted; no "
            "Hall closure (credible set empty), no screening candidate, no 0-D Hall model, no withdrawn number",
            "A5 numbers are allocations/requirements; analog hardware is never a Vyovrinda design value",
            "P5 calibration nuisance is never a design variable; P5 geometry/B(z) files are not design sources",
            "the valve-outlet feed state is read from feed_state_closure_v1.json, never from 0-D assumptions",
            "Bundle 1 stays NO_BASELINE_YET",
            "reuse check: abep_sim/magnet_power.py is used (pure magnetostatics + NBS copper R(T), no plasma model, "
            "not superseded); abep_sim/sizing.py is NOT used: it evaluates abep_sim.system/thruster CARDS "
            "(T_air_mN from the superseded 0-D Hall chain)",
        ],
        "sources": SOURCES,
        "assumed_inputs": ASSUMED,
        "read_inputs": sig({k: v for k, v in I.items() if not k.startswith("_")}),
        "analogs": ANALOGS,
        "channel": sig(ch),
        "magnetic_topology_options": topology,
        "magnetic_topology_preliminary_choice": {"choice": "T2 (+T3 provision; T1 fallback via replaceable poles)",
                                                 "why": why},
        "bz_target_envelope": bz,
        "coil_design": sig(cd),
        "materials": materials,
        "design_parameters": params,
        "interface_demands": interface_demands,
        "hard_incompatibility_check": hard,
        "architecture_changing_blockers_touched": blockers,
        "m16_rows": m16,
        "h3_procurement_inputs": h3,
        "h4_test_inputs": h4,
        "milestones": milestones,
        "open_questions_for_owner": [
            "Q1 design flow for channel sizing: the delivered flow spans 0.38-1.29 mg/s (design case) to ~3.2 mg/s; "
            "which point should the channel neutral density be matched at?",
            "Q2 keep the magnetically shielded topology (T2) as the H-1 baseline with a T1 replaceable pole set?",
            "Q3 L/h upper bound (12 proposed) and whether an adjustable-anode development insert is allowed pre-S1",
            "Q4 pole/core grades (Hiperco 50 inner, pure iron outer) - HWQ-18 / MCQ-OQ-05",
            "Q5 coil insulation family (ceramic Ni-clad Cu vs polyimide) - MCQ-OQ-02; hot-spot margin MCQ-OQ-03",
            "Q6 cathode location: central L-C constrains d_mean >= H21-22; accept, or choose external L-E",
            "Q7 PROPOSED factors: B headroom 1.5, working flux 0.7 Bsat, discharge share >= 0.5",
        ],
    }
    return doc


# ------------------------------------------------------------------------------------------------ markdown
def fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, list):
        return "–".join(fmt(x) for x in v) if len(v) == 2 and all(isinstance(x, (int, float)) for x in v) \
            else ", ".join(fmt(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {fmt(x)}" for k, x in v.items())
    return str(v)


def render_md(doc):
    ch, bz, cd = doc["channel"], doc["bz_target_envelope"], doc["coil_design"]
    L = []
    w = L.append
    w("# H2-1 Hall chamber + magnetic circuit: preliminary sizing for H-1 / MC-1")
    w("")
    w("> Generated by `build_h2_1_hall_chamber_magnet.py` from the same data as `h2_1_hall_chamber_magnet_v1.json`. "
      "Do not edit by hand (`--check` verifies).")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| lane | `{doc['lane']}` (trigger `{doc['trigger']}`, owner addendum A7) |")
    w(f"| status | **{doc['status']}** |")
    w(f"| configuration items | {', '.join(doc['configuration_items'])}; planes {', '.join(doc['interface_planes'])} |")
    w(f"| architectures | {', '.join('`'+a_+'`' for a_ in doc['architectures'])} (common hardware; no winner) |")
    w(f"| base commit | `{doc['base_commit']}` |")
    for k, v in doc["owner_decisions"].items():
        w(f"| {k} | `{v['path']}` sha256 `{v['sha256']}` |")
    w("")
    w("**What this is.** An H2 hardware design / preliminary-sizing lane (A7). It sizes the H-1 channel envelope and "
      "the MC-1 magnetic circuit from requirements, A5 allocations, published xenon-derived scaling relations "
      "(hypotheses for air species), labelled published analog hardware and magnetostatics.")
    w("")
    w("**What this is not.** Not an architecture selection and not a performance prediction. No Hall closure (the "
      "credible set is empty), no screening candidate, no 0-D Hall model and no withdrawn number is used. ECHT and "
      "every other device below are published analogs, never Vyovrinda design values. Bundle 1 stays NO_BASELINE_YET.")
    w("")
    w("Hard statements:")
    for x in doc["hard_statements"]:
        w(f"- {x}")
    w("")
    w("## 1. Channel envelope (H-1)")
    w("")
    w(f"Discharge power band used by the area rules: {fmt(ch['P_d_band_W'])} W (upper = A5 bus allocation ceiling, "
      f"lower = PROPOSED 0.5 share of 1.30 kW; the real share is PENDING `docs/hardware/h2/h2_4_ppu_bus/`). "
      f"V_d band {fmt(ch['V_d_band_V'])} V (HW-ENV-01).")
    w("")
    w("| rule | relation (source) | area [cm²] | applicability |")
    w("|---|---|---|---|")
    for k in ("A_CP", "A_jd"):
        r = ch["area_rules_cm2"][k]
        w(f"| {k} | {r['rule']} | {fmt(r['value'])} | {r['applicability']} |")
    for fk, v in ch["area_rules_cm2"]["A_ncXe_by_flow"]["value"].items():
        w(f"| A_ncXe @ {fk} ({fmt(ch['flows_kgps'][fk]*1e6)} mg/s) | {ch['area_rules_cm2']['A_ncXe_by_flow']['rule']} "
          f"| {fmt(v)} | {ch['area_rules_cm2']['A_ncXe_by_flow']['applicability']} |")
    w("")
    w(f"**Preliminary area window** {fmt(ch['area_window_cm2'])} cm² ({ch['area_window_rule']}). With the analog "
      f"d/h window {fmt(ch['d_over_h_window'])} ({fmt(ch['d_over_h_sources'])}):")
    w("")
    w("| quantity | range |")
    w("|---|---|")
    w(f"| width h [mm] | {fmt(ch['h_mm'])} |")
    w(f"| mean diameter d [mm] | {fmt(ch['d_mean_mm'])} |")
    w(f"| channel OD [mm] | {fmt(ch['OD_channel_mm'])} |")
    w(f"| channel ID [mm] | {fmt(ch['ID_channel_mm'])} |")
    w(f"| L/h (extended) | {fmt(ch['L_over_h_window'])} |")
    w(f"| L [mm] (anode face z = 0 = HALL_INLET_Z0 to exit plane z = L) | {fmt(ch['L_mm'])} |")
    w(f"| neutral residence time L/v_n [s] | {fmt(ch['residence_time_s'])} |")
    w("")
    r = ch["L_over_h_rules"]["equal_ne_ionization_length"]
    w(f"**Why extended.** At equal n_e, T_e and T_n the N₂ ionization mean free path is {fmt(r['lambda_ratio_range'])}× "
      f"the xenon one (scaling TR-01, T_e 5–30 eV). Conventional xenon-class analogs run L/h "
      f"{fmt(r['conventional_L_over_h'])} (Z-70, MaSMi), so equal-n_e similarity asks for L/h {fmt(r['value'])}; "
      "GK2008 p. 336 (Eq. 7.2-19): lighter propellants need a longer ionization region. The lower end coincides with "
      "the ECHT extended channel (L/h 8.6; analog only). Part of the demand can be met by a higher n_e, so the upper "
      "bound is a PROPOSED packaging value.")
    w("")
    w("**Delivered-flow argument (feed_state_closure).** Neutral density inside the area window:")
    w("")
    w("| flow | ṁ [mg/s] | n_n [m⁻³] | n_n / n_crit,Xe |")
    w("|---|---|---|---|")
    for fk, v in ch["neutral_density_in_window"].items():
        w(f"| {fk} | {fmt(ch['flows_kgps'][fk]*1e6)} | {fmt(v['n_n_m3'])} | {fmt(v['n_n_over_n_crit_Xe'])} |")
    w("")
    w("One fixed channel cannot hold the xenon-analog density band across the delivered-flow range; the low-flow knee "
      "(A5 risk 1) is exactly what H-1 Phase 1 measures. This is a density bookkeeping statement, not a sustainment "
      "prediction.")
    w("")
    w("## 2. Magnetic topology options")
    w("")
    w("| id | option | wall-life consequence | status |")
    w("|---|---|---|---|")
    for t in doc["magnetic_topology_options"]:
        w(f"| {t['id']} | {t['name']} | {t['wall_life_consequence']} | {t['status']} |")
    w("")
    w(f"**Preliminary choice:** {doc['magnetic_topology_preliminary_choice']['choice']}. "
      f"{doc['magnetic_topology_preliminary_choice']['why']}")
    w("")
    w("## 3. B_r(z) target envelope (design target, not a transport optimization)")
    w("")
    w(f"- Peak centreline B_r at/near the exit: **{fmt(bz['target_peak_Br_G'])} G**; MC-1 capability "
      f"**{fmt(bz['capability_G'])} G** (PROPOSED headroom 1.5).")
    w(f"- Criterion: r_Le ≤ 0.1 h (SRC-MASMI p. 5 citing Goebel & Katz); this script reproduces MaSMi's 213 G as "
      f"{fmt(bz['masmi_reproduction_G'])} G. Table by T_e (assumed criterion parameter): {fmt(bz['rLe_rule_table_G'])}.")
    w(f"- Gradient: {bz['gradient']}.")
    w(f"- Anode region: {bz['anode_region']}.")
    w(f"- Peak position: {bz['peak_position']}.")
    w(f"- Ion Larmor check: {bz['ion_larmor_note']}.")
    w("")
    w("| analog | B | source | class |")
    w("|---|---|---|---|")
    for x in bz["analog_magnitudes"]:
        w(f"| {x['id']} | {x['B_G']} | {x['source']} | {x['evidence_class']} |")
    w("")
    w("## 4. Coil design (lumped magnetic circuit)")
    w("")
    w(f"Method: {cd['method']}.")
    w("")
    w("Accuracy limits:")
    for x in cd["accuracy_limits"]:
        w(f"- {x}")
    w("")
    w("| case | d/h/L [mm] | B_gap [G] | gap [mm] | NI total [A] | inner build [mm] | coils (AWG, N, I [A], V@200 C) "
      "| P 20 C / 200 C [W] | body OD [mm] | iron / Cu [kg] |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for c in cd["cases"]:
        if c["status"].startswith("INFEASIBLE"):
            w(f"| {c['name']} | {fmt(c['d_mean_mm'])}/{fmt(c['h_mm'])}/{fmt(c['L_mm'])} | {fmt(c['B_gap_G'])} | "
              f"{fmt(c['gap_mm'])} | – | {fmt(c['inner_coil_build_mm'])} | {c['status']} | – | – | – |")
            continue
        cs = []
        for k in ("inner", "outer"):
            ch_ = c["coils"][k]["chosen"]
            cs.append(f"{k}: AWG {ch_['awg']}, {ch_['N']}, {fmt(ch_['I_A'])}, {fmt(ch_['V200_V'])} V"
                      + (" (outside analog supply window)" if "flag" in ch_ else ""))
        w(f"| {c['name']} | {fmt(c['d_mean_mm'])}/{fmt(c['h_mm'])}/{fmt(c['L_mm'])} | {fmt(c['B_gap_G'])} | "
          f"{fmt(c['gap_mm'])} | {fmt(c['NI_total_A'])} | {fmt(c['inner_coil_build_mm'])} | {'; '.join(cs)} | "
          f"{fmt(c['P_coils_20C_W'])} / {fmt(c['P_coils_200C_W'])} | {fmt(c['body_OD_mm'])} | "
          f"{fmt(c['iron_mass_kg'])} / {fmt(c['copper_mass_kg'])} |")
    w("")
    w(f"Minimum mean diameter for a central cathode (bore 12 / 18 mm) by width h: "
      f"{fmt(cd['min_d_mean_for_central_cathode_mm'])} mm.")
    w("")
    w("Coil temperature class: high-temperature ceramic-insulated wire (MCQ-EM-03, 537.8 °C continuous) preferred; "
      "above 200 °C the copper model is not extrapolated and the hot I²R is TBD (MCQ-TL-04). FEMM/3-D "
      "magnetostatics is the H4 / H2-follow-up.")
    w("")
    w("## 5. Magnetic materials")
    w("")
    w("| material | B_sat | Curie | density | locator |")
    w("|---|---|---|---|---|")
    for k, v in doc["materials"]["candidates"].items():
        w(f"| {k} | {fmt(v['B_sat_T'][0])} T | {fmt(v['curie_C'][0])} °C | {fmt(v['density_kg_m3'][0])} kg/m³ | "
          f"{v['B_sat_T'][1]}; {v['curie_C'][1]} |")
    w("")
    w(f"Preliminary: {fmt(doc['materials']['preliminary_choice'])}. Flux margin (B_work/B_sat): "
      f"{fmt(doc['materials']['flux_margin_RP1'])}. {doc['materials']['max_use_temperature']}.")
    w("")
    w("O/O₂ exposure:")
    for x in doc["materials"]["O_O2_exposure"]:
        w(f"- {x}")
    w("")
    w("## 6. Design-parameter table")
    w("")
    w("| id | name | value | units | basis | source | evidence | status | representativeness |")
    w("|---|---|---|---|---|---|---|---|---|")
    for p in doc["design_parameters"]:
        w(f"| {p['id']} | {p['name']} | {fmt(p['value'])} | {p['units']} | {p['basis']} | {p['source']} | "
          f"{p['evidence_class']} | {p['status']} | {p['representativeness']} |")
    w("")
    w("## 7. Interface demands")
    w("")
    w("| from | to | quantity | value | units | status |")
    w("|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        w(f"| {d['from']} | {d['to']} | {d['quantity']} | {fmt(d['value'])} | {d['units']} | {d['status']} |")
    w("")
    w("Mounting datums: axis = datum A; z = 0 at the anode face (HALL_INLET_Z0, lane-17 convention); exit plane "
      "z = L; the rear flange of H-1 is IP-DN, upstream of the back plate. The pre-ionizer module slot is upstream "
      "of IP-DN; MC-1 leakage into the slot and the module field change in the channel are PMI-09 items.")
    w("")
    w("## 8. Hard-incompatibility check")
    w("")
    w(f"**Verdict: {doc['hard_incompatibility_check']['verdict']}.** Checked:")
    for c in doc["hard_incompatibility_check"]["checked"]:
        w(f"- {c['item']}: {c['result']} ({c['evidence_class']})")
    w("")
    w("## 9. Architecture-changing blockers (A7) touched")
    w("")
    for b in doc["architecture_changing_blockers_touched"]:
        w(f"- Blocker {b['blocker']}: {b['how']}")
    w("")
    w("## 10. M16 rows")
    w("")
    w("| subsystem | proposed state | blocking item | rollup |")
    w("|---|---|---|---|")
    for m in doc["m16_rows"]:
        w(f"| {m['subsystem']} | {m['proposed_state']} | {m['blocking_item']} | {m['rollup_category']} |")
    w("")
    w("## 11. H3 procurement inputs")
    w("")
    for h in doc["h3_procurement_inputs"]:
        w(f"- **{h['item']}** (long lead: {h['long_lead']}): {h['spec_level_needed']} — {h['reference']}")
    w("")
    w("## 12. H4 test inputs")
    w("")
    for h in doc["h4_test_inputs"]:
        w(f"- **{h['stage']}**: {h['measure']} → closes {', '.join(h['closes'])}")
    w("")
    w("## 13. Milestones")
    w("")
    for k, v in doc["milestones"].items():
        w(f"- **{k}**: {v}")
    w("")
    w("## 14. Owner questions")
    w("")
    for q in doc["open_questions_for_owner"]:
        w(f"- {q}")
    w("")
    w("## 15. Sources accessed by this lane")
    w("")
    for k, s in doc["sources"].items():
        w(f"- **{k}**: {s['citation']}. {s['url']} (accessed {s['accessed']}; {s['access']}; sha256 "
          f"{s['sha256'] or 'n/a'}).")
    w("")
    w("Assumed inputs (all PROPOSED or PRELIMINARY; JSON `assumed_inputs`):")
    w("")
    for k, v in doc["assumed_inputs"].items():
        w(f"- `{k}` = {fmt(v['value'])} {v['unit']} ({v['evidence_class']}, {v['status']}): {v['why']}")
    w("")
    return "\n".join(L)


def dump(doc):
    return json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv):
    doc = build()
    js, md = dump(doc), render_md(doc)
    if "--check" in argv:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and \
            OUT_MD.exists() and OUT_MD.read_text(encoding="utf-8") == md
        print("OK" if ok else "MISMATCH: rerun the builder")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
