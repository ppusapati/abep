"""H2-5 thermal network (fo_h2_5_thermal_network, trigger T_H2_5_THERMAL_NETWORK, owner addendum A7).

Preliminary lumped-node STEADY-STATE thermal network for the H-1 flight-representative test article (Hall accelerator
H-1 + common magnetic circuit MC-1 + cathode C-1 + the common pre-ionizer slot at IP-DN) and the spacecraft-side
propulsion nodes (PPU, compressor, gas path/plenum, mounting interface).

What this script is
  * a deterministic builder: python docs/hardware/h2/h2_5_thermal_network/build_h2_5_thermal_network.py
    writes h2_5_thermal_network_v1.json and H2_5_THERMAL_NETWORK.md next to itself (no network access, no clock, a
    fixed RNG seed, < 1 min on one CPU);
  * pure: it imports only the standard library and numpy; it is NOT wired into abep_sim/archengine.py and it does NOT
    use abep_sim/thermal.py (its default_nodes() hard-codes unsourced emissivities/conductances and books thruster heat
    from the superseded 0-D Hall closure; see provenance_checks) nor abep_sim/plasma_devices.py.

What this script is NOT
  * not a Hall performance model: discharge heat enters ONLY as a parametric fraction of the discharge power
    allocation, with the fraction bounded by published xenon analog hardware (labelled analog). No Hall transport
    closure, screening candidate or withdrawn 0-D number is used. A5 numbers are allocations, never predictions.
  * not an architecture selector: the pre-ionizer slot enters only through the common thermal-rejection interface
    PMI-05 of the pre-ionizer module ICD (PENDING); hall_only / rf_hall / ecr_hall are never ranked.

Every input value carries basis, source, evidence class, status and scope in PARAMETERS below; missing inputs raise
(no silent defaults, CLAUDE.md rule 3).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
OUT_JSON = os.path.join(HERE, "h2_5_thermal_network_v1.json")
OUT_MD = os.path.join(HERE, "H2_5_THERMAL_NETWORK.md")
REL_DIR = "docs/hardware/h2/h2_5_thermal_network"

BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
SIGMA_SB = 5.670374419e-8          # W m^-2 K^-4, exact (CODATA 2022; limits_v1.json source nist_codata_sigma)
K_B = 1.380649e-23                 # J/K, exact SI
E_CHARGE = 1.602176634e-19         # C, exact SI
LORENZ_SOMMERFELD = (math.pi ** 2 / 3.0) * (K_B / E_CHARGE) ** 2   # W ohm K^-2 (free-electron value, exact from SI)
T0C = 273.15
R_EARTH_M = 6371.0e3               # abep_sim/constants.py R_EARTH (repository constant; mean radius, verify)
RNG_SEED = 20260927
N_LHS = 256

# ----------------------------------------------------------------------------------------------- pinned inputs
PINNED = {
    "A5": {"path": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "sha256": "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621", "kind": "owner decision (immutable)"},
    "A6": {"path": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "sha256": "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180", "kind": "owner decision (immutable)"},
    "A7": {"path": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "sha256": "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925", "kind": "owner decision (immutable)"},
    "G0": {"path": "docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
           "sha256": "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523", "kind": "verified G0 baseline (immutable)"},
    "LIMITS": {"path": "schemas/thermal_life/limits_v1.json",
               "sha256": "0df363f76dcb6efcef41bc0a07e1775b6255c2c9d84b185228862958ef827dbb",
               "kind": "frozen sourced-limits contract (frozen_on 2026-09-26, lane 15 THL); read-only"},
    "MCQ": {"path": "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json",
            "sha256": "53e92f4536f7b30054d3521adbd504eca725c4c6d79a6cb3b51c2fc4ce220b32",
            "kind": "verified deliverable pinned by W3 (SRC-MCQ)"},
}
# Mutable / DRAFT repository files are referenced by path at the base commit, never pinned (A7 pinning rule).
REFERENCED_AT_BASE = {
    "W3": "docs/experiments/hardware/hardware_requirements_v1.json (DRAFT_PENDING_OWNER; CI ids H-1, MC-1, C-1, FS-C, PS-C, SVC-1, PIM-0/-RF/-ECR, DIV-1; planes IP-UP, IP-DN, HALL_INLET_Z0)",
    "AOL": "docs/experiments/lifetime_ao/ao_lifetime_register_v5.json (mechanisms AOL-M01..M11)",
    "THL": "abep_sim/thermal_life.py + schemas/thermal_life/inputs_v1.json (read-only)",
    "TRL": "schemas/ledgers/thermal_rejection_ledger_v1.json (DRAFT schema)",
    "CATH": "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
    "FT": "docs/architecture_comparison/failure_tree/failure_trees_v1.json (N-THM-01, wall/anode node)",
    "ECHT": "CLAUDE.md 'Superseded / withdrawn' (true ECHT: 86 mm long, 10 mm wide, 100 mm OD; Marchioni 2020 thesis via the repository ECHT audit)",
    "BOUNDARY": "abep_sim/arch_boundary.py (BOUNDARY_VERSION bus_power_boundary_v1)",
}

# External documents actually accessed on 2026-09-27 (sha256 of the retrieved file).
EXTERNAL = {
    "EXT-MARTINEZ2014": {
        "citation": "R. A. Martinez, H. Dao, M. L. R. Walker, 'Power Deposition into the Discharge Channel of a Hall Effect Thruster', J. Propulsion and Power 30(1), 2014, DOI 10.2514/1.B34897",
        "url": "https://hpepl.ae.gatech.edu/papers/2014_JPP_Rafael.pdf", "access": "full text (author laboratory copy)",
        "sha256": "039e3620d1e4fabaf4fa3d4bf8cf2c6dc6e1b18eadb9c6198f4ab108fb431b61"},
    "EXT-MYERS2016": {
        "citation": "J. Myers, H. Kamhawi, J. Yim, L. Clayman, 'Hall Thruster Thermal Modeling and Test Data Correlation', AIAA Propulsion and Energy Forum, Salt Lake City, July 2016 (NASA NTRS 20170000961)",
        "url": "https://ntrs.nasa.gov/api/citations/20170000961/downloads/20170000961.pdf", "access": "full text (NTRS)",
        "sha256": "8a9f79089c8630123b2e1ec8ad0740dcd3141377d897462ca1ebcbf7d5c8e85f"},
    "EXT-MAZOUFFRE2005": {
        "citation": "S. Mazouffre, J. Perez Luna, D. Gawron, M. Dudeck, P. Echegut, 'An infrared thermography study on the thermal load experienced by a high power Hall thruster', IEPC-2005-063, Princeton, 2005",
        "url": "https://electricrocket.org/IEPC/063.pdf", "access": "full text (ERPS IEPC archive)",
        "sha256": "b1f0a23e4102ae009dcb55d28758a19696b15bc36d2183766096196642df8a81"},
    "EXT-HENZE2021": {
        "citation": "Henze Boron Nitride Products AG, HeBoSint Boron Nitride Solids qualities datasheet, 08.2021 (typical values, guide only)",
        "url": "https://nitrid.eu/files/henze/en/HS_Qualities_en.pdf", "access": "manufacturer datasheet (also limits_v1.json source henze_hebosint_2021)",
        "sha256": "e0cbaec33c1d63bf663f991a1118194a36c892302e97791ec1770aa8276a3700"},
    "EXT-HENNINGER1984": {
        "citation": "J. H. Henninger, 'Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings', NASA Reference Publication 1121, April 1984",
        "url": "https://ntrs.nasa.gov/api/citations/19840015630/downloads/19840015630.pdf", "access": "full text (NTRS)",
        "sha256": "03282ed76b9b25fad264631ef9d4a80807840490f39de37a843c6d9dcfd2bcf1"},
    "EXT-NASA-TM2001": {
        "citation": "B. J. Anderson, C. G. Justus, G. W. Batts, 'Guidelines for the Selection of Near-Earth Thermal Environment Parameters for Spacecraft Design', NASA/TM-2001-211221, October 2001",
        "url": "https://ntrs.nasa.gov/api/citations/20020004360/downloads/20020004360.pdf", "access": "full text (NTRS)",
        "sha256": "a6ea8902b65e59ef3932d1a1f84c5b3a45938f240344b1d8a7465e79a625467e"},
    "EXT-NIST-CRYO": {
        "citation": "NIST Cryogenics Technologies Group, Material Properties (thermal-conductivity curve fits): OFHC copper, 304 stainless steel, molybdenum, Ti-6Al-4V, 6061-T6 aluminum",
        "url": "https://trc.nist.gov/cryogenics/materials/materialproperties.htm", "access": "open web pages (fit coefficients transcribed 2026-09-27)",
        "sha256": None, "sha256_note": "HTML pages; coefficients transcribed below verbatim, no file hash"},
    "EXT-NICOFE-A848": {
        "citation": "Nicofe, ASTM A848 Type 1 Soft Magnetic Iron datasheet IAW3078 v2 (typical data)",
        "url": "https://www.nicofe.com/wp-content/uploads/2025/12/IAW3078-Nicofe-ASTM-A848-Type-1-A4-datasheet-v2.pdf",
        "access": "manufacturer datasheet", "sha256": "84be2d2f1643214bc27b85ff08265299d2b5540ffa36a28d01c2040e883fc032"},
    "EXT-EEE-INST-002": {
        "citation": "NASA/TP-2003-212242 EEE-INST-002 (April 2008 edition incl. Addendum 1) (also limits_v1.json source nasa_eee_inst_002)",
        "url": "https://nepp.nasa.gov/docuploads/FFB52B88-36AE-4378-A05B2C084B5EE2CC/EEE-INST-002_add1.pdf",
        "access": "full text (NASA NEPP)", "sha256": "4bd84c11401d51613911a4cdfd4afaacefc113e7b538fd86b2a60f99afa1d3dd"},
}

SCOPES = ("FLIGHT_REPRESENTATIVE", "H1_TEST_ARTICLE_ONLY", "GROUND_FACILITY_ONLY")
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
EVIDENCE = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")


def P(pid, key, name, value, units, basis, source, evidence, status, scope, note=""):
    """One design-parameter row. `value` is a number, a [lo, hi] range, a dict, or None (then status must be TBD/PENDING)."""
    if basis not in BASES or evidence not in EVIDENCE or scope not in SCOPES:
        raise ValueError(f"{pid}: bad basis/evidence/scope")
    if value is None and not (status.startswith("TBD") or status.startswith("PENDING")):
        raise ValueError(f"{pid}: null value needs a TBD/PENDING status")
    return {"id": pid, "key": key, "name": name, "value": value, "units": units, "basis": basis, "source": source,
            "evidence_class": evidence, "status": status, "scope": scope, "note": note}


# ----------------------------------------------------------------------------------------------- source-derived numbers
# NIST cryogenic fits, transcribed coefficients (EXT-NIST-CRYO). Valid ranges as stated on each page.
NIST_FITS = {
    "OFHC_copper_RRR100": {"form": "rational_sqrtT", "range_K": [4, 300], "fit_error_pct": 1,
                            "coef": {"a": 2.2154, "b": -0.47461, "c": -0.88068, "d": 0.13871, "e": 0.29505,
                                     "f": -0.02043, "g": -0.04831, "h": 0.001281, "i": 0.003207}},
    "SS304": {"form": "log10_poly", "range_K": [4, 300], "fit_error_pct": 2,
              "coef": [-1.4087, 1.3982, 0.2543, -0.6260, 0.2334, 0.4256, -0.4658, 0.1650, -0.0199]},
    "molybdenum": {"form": "log10_poly", "range_K": [2, 373], "fit_error_pct": 3,
                   "coef": [10.78259, -72.13065, 228.57351, -384.50447, 381.43825, -228.83783, 81.26658, -15.69097, 1.26814]},
    "Ti6Al4V": {"form": "log10_poly", "range_K": [20, 300], "fit_error_pct": 2,
                "coef": [-5107.8774, 19240.422, -30789.064, 27134.756, -14226.379, 4438.2154, -763.07767, 55.796592, 0.0]},
    "Al6061_T6": {"form": "log10_poly", "range_K": [4, 300], "fit_error_pct": 0.5,
                  "coef": [0.07918, 1.0957, -0.07277, 0.08084, 0.02803, -0.09464, 0.04179, -0.00571, 0.0]},
}


def nist_k(name: str, T: float) -> float:
    f = NIST_FITS[name]
    lo, hi = f["range_K"]
    if not lo <= T <= hi:
        raise ValueError(f"NIST fit {name} is valid {lo}-{hi} K only (asked {T} K); no extrapolation")
    if f["form"] == "log10_poly":
        x = math.log10(T)
        return 10 ** sum(c * x ** k for k, c in enumerate(f["coef"]))
    c = f["coef"]
    num = c["a"] + c["c"] * T ** 0.5 + c["e"] * T + c["g"] * T ** 1.5 + c["i"] * T ** 2
    den = 1 + c["b"] * T ** 0.5 + c["d"] * T + c["f"] * T ** 1.5 + c["h"] * T ** 2
    return 10 ** (num / den)


# Nicofe A848 Type 1 electrical resistivity table (EXT-NICOFE-A848 'Electrical resistivity at elevated temperatures').
FE_RHO_TABLE_C = [0, 100, 200, 300, 400, 500, 600, 700, 800]
FE_RHO_TABLE_UOHM_CM = [9.6, 15.0, 22.6, 31.4, 43.1, 55.3, 69.8, 87.0, 105.5]


def fe_rho_ohm_m(T_K: float) -> float:
    Tc = T_K - T0C
    xs, ys = FE_RHO_TABLE_C, FE_RHO_TABLE_UOHM_CM
    if not xs[0] <= Tc <= xs[-1]:
        raise ValueError(f"iron resistivity table covers 0-800 degC only (asked {Tc:.1f} degC)")
    for j in range(len(xs) - 1):
        if xs[j] <= Tc <= xs[j + 1]:
            y = ys[j] + (ys[j + 1] - ys[j]) * (Tc - xs[j]) / (xs[j + 1] - xs[j])
            return y * 1e-8
    raise AssertionError


FE_CLAMP = {"count": 0}


def fe_k_wf(T_K: float, mult: float) -> float:
    """Model-derived electronic thermal conductivity of soft iron (Wiedemann-Franz, Sommerfeld Lorenz number) x mult.
    Below 0 degC (outside the resistivity table) k is held at its 0 degC value and the use is COUNTED and reported
    (affects only cold-case minima; every hot-case / margin solve stays inside the table or raises)."""
    if T_K < T0C:
        FE_CLAMP["count"] += 1
        T_K = T0C
    return mult * LORENZ_SOMMERFELD * T_K / fe_rho_ohm_m(T_K)


def slot_view_factors(L: float, h: float) -> dict:
    """2-D Hottel crossed-string view factors of an annular channel treated as a planar slot (curvature neglected)."""
    diag = math.sqrt(L * L + h * h)
    return {"F_anode_to_exit": (diag - L) / h, "F_wall_to_exit": (L + h - diag) / (2 * L)}


def earth_view_bound(h_km: float) -> dict:
    """Bounds for a horizontal cylinder's lateral surface: elements whose normal lies within 90 deg + horizon dip of nadir
    can see the Earth; each sees at most F = 1 -> F_e,avg <= (180 + 2 dip)/360. Nadir-plate F = (R/(R+h))^2."""
    ratio = R_EARTH_M / (R_EARTH_M + h_km * 1e3)
    dip = math.degrees(math.acos(ratio))
    return {"horizon_dip_deg": dip, "F_nadir_plate": ratio ** 2, "F_e_lateral_upper_bound": (180 + 2 * dip) / 360}


def two_surface_R(eps1, A1, eps2, A2, F12=1.0):
    return (1 - eps1) / (eps1 * A1) + 1 / (A1 * F12) + (1 - eps2) / (eps2 * A2)


# ----------------------------------------------------------------------------------------------- parameters
EV_S = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
FINISHES = {
    # alpha_s, eps_n from Henninger 1984 (room-temperature measurements; eps normal emittance)
    "bare_machined_stainless": {"alpha": 0.47, "eps": 0.14, "locator": "EXT-HENNINGER1984 'Metals and conversion coatings', Stainless Steel Machined 0.47 / 0.14 (p. 10)"},
    "sandblasted_stainless": {"alpha": 0.58, "eps": 0.38, "locator": "EXT-HENNINGER1984 'Metals and conversion coatings', Stainless Steel Sandblasted 0.58 / 0.38 (p. 10)"},
    "z93_white_inorganic": {"alpha": 0.17, "eps": 0.92, "locator": "EXT-HENNINGER1984 'White paints', Zerlauts Z-93 White Paint 0.17 / 0.92 (white-paint table); its temperature capability on a 200-400 degC Hall body is NOT established here (TBD - requires coating datasheet / S1a coupon test)"},
}


def build_parameters() -> list:
    ex_vf = slot_view_factors(0.086, 0.010)
    eb180 = earth_view_bound(180.0)
    rows = [
        # --- allocations / requirements
        P("H25-01", "P_bus_alloc_W", "A5 bus-power design allocation (P_bus per bus_power_boundary_v1)", [1300.0, 1350.0], "W",
          "allocation", f"{EV_S} allocations_and_requirements[bus-power design allocation]", "assumed", "PRELIMINARY",
          "FLIGHT_REPRESENTATIVE", "allocation, not a prediction"),
        P("H25-02", "P_d_max_W", "bounding hall_discharge power used for the hot case (P_d <= P_bus allocation upper end)", 1350.0, "W",
          "allocation", f"{EV_S} (<= 1.30-1.35 kW); hall_discharge share PENDING docs/hardware/h2/h2_4_ppu_bus/", "assumed",
          "PENDING docs/hardware/h2/h2_4_ppu_bus/ (hall_discharge allocation); bound used now", "FLIGHT_REPRESENTATIVE",
          "P_d cannot exceed the whole bus allocation; using it is conservative for every hot-case temperature"),
        P("H25-03", "P_d_grid_frac", "evaluation grid of P_d as fractions of H25-02", [0.5, 0.75, 1.0], "-",
          "assumed", "this lane (evaluation grid only, not an allocation)", "assumed", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
        # --- discharge heat fractions (xenon analog hardware only)
        P("H25-04", "f_anode", "fraction of P_d deposited on the anode (xenon analog envelope)", [0.0206, 0.1667], "-",
          "analog", "lower: EXT-MYERS2016 Table 3 correlated anode 257.9 W / 12.5 kW (HERMeS TDU-1, Xe, magnetically shielded); "
          "upper: EXT-MAZOUFFRE2005 p. 13 'Panode = Id x Es, Es around 30 eV' (PPSX000, Xe) evaluated as 30 V / V_d,min with "
          "V_d,min = 180 V (W3 HW-ENV-01 PROPOSED set)", "inferred",
          "PRELIMINARY (air/N2-O2 value unknown: no published fraction; measured in Phase 1)", "FLIGHT_REPRESENTATIVE",
          "analog only; never a transport-model prediction"),
        P("H25-05", "f_walls", "fraction of P_d deposited on the channel walls (xenon analog envelope)", [0.0439, 0.15], "-",
          "analog", "lower: EXT-MYERS2016 Table 3 correlated DC walls 549.1 W / 12.5 kW; upper: EXT-MARTINEZ2014 abstract "
          "'Approximately 13 +/- 2% of the discharge power is deposited into the discharge channel wall' (T-140, Xe, M26 BN, 0.63-2.83 kW); "
          "EXT-MAZOUFFRE2005 (PPSX000, Xe) ~7 % lies inside", "inferred",
          "PRELIMINARY (air/N2-O2 value unknown; failure_trees_v1 wall/anode node: 'not established by a cited item')",
          "FLIGHT_REPRESENTATIVE"),
        P("H25-06", "f_pole", "fraction of P_d deposited on the inner front pole (magnetically shielded analog only)", [0.0, 0.01448], "-",
          "analog", "EXT-MYERS2016 Table 3: inner front pole 181 W Hall2De-predicted (upper, /12.5 kW), 41.6 W correlated; lower 0 for "
          "an unshielded design (pole heat then inside f_walls)", "inferred", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
        P("H25-07", "f_total_context", "total plasma heat to thruster body, published context", [0.068, 0.25], "-",
          "analog", "EXT-MYERS2016 p. 16: 'total plasma heat load of 849 W which is ~ 6.8% of thruster discharge power ... previous NASA "
          "development Hall thrusters (10 to 25 %) ... limited, not validated'; EXT-MAZOUFFRE2005: 'around 15% of the input power' lost inside the channel",
          "inferred", "PRELIMINARY (context; the solve uses H25-04..06 whose sum reaches 0.33, above this context)", "FLIGHT_REPRESENTATIVE"),
        # --- other heat loads
        P("H25-08", "P_mag_W", "Hall magnet coil I^2R (both coils, steady); 0 W for a permanent-magnet MC-1", [0.0, 60.0], "W",
          "pending", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (NI, R(T), coil count); evaluation range assumed here", "assumed",
          "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE",
          "evaluation range only; HERMeS 44.1 + 48.1 W at 12.5 kW (EXT-MYERS2016) is a different size class and not transferred"),
        P("H25-09", "coil_split_inner", "inner-coil share of P_mag", 0.478, "-", "analog",
          "EXT-MYERS2016 Table 3: inner 44.1 W / (44.1 + 48.1) W", "inferred", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/",
          "FLIGHT_REPRESENTATIVE"),
        P("H25-10", "Q_cath_W", "C-1 steady heat into the H-1 environment (keeper + emitter radiation)", [9.0, 101.0], "W",
          "pending", "keeper: cathode_integration_data_v1.json hc1_keeper_only_power_W [9, 20] and hc3_keeper_only_power_W [25, 60] "
          "(SITAEL, stand-alone keeper, Pedrini 2017); radiated: EXT-MYERS2016 p. 8 '41 W for the BaO cathode' (HERMeS); "
          "range = 9 .. 60 + 41", "inferred", "PENDING docs/hardware/h2/h2_2_cathode_integration/", "FLIGHT_REPRESENTATIVE",
          "heater power (start-up only) is not a steady load; heater transient TBD"),
        P("H25-11", "Q_PIM_W", "active heat entering H-1 at IP-DN from the pre-ionizer slot occupant (PMI-05 common thermal interface)", 0.0, "W",
          "pending", "PENDING docs/interfaces/preionizer_module/ + schemas/interfaces/preionizer_module_icd_v1.json (PMI-05); "
          "0 W for PIM-0 (HW-0 passive spacer, W3)", "assumed", "PENDING docs/interfaces/preionizer_module/ (PMI-05)",
          "H1_TEST_ARTICLE_ONLY", "reported as influence coefficients dT/dQ_PIM (K/W), identical for every occupant; no RF/ECR-specific value"),
        # --- geometry (ECHT analog + assumed; all PENDING H2-1 / H2-7)
        P("H25-12", "L_ch_m", "channel length", 0.086, "m", "analog", "REF ECHT (CLAUDE.md: true ECHT 86 mm long)", "measured",
          "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE", "published analog only, not a Vyovrinda value"),
        P("H25-13", "h_ch_m", "channel width", 0.010, "m", "analog", "REF ECHT (10 mm wide)", "measured",
          "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-14", "D_out_m", "channel outer diameter", 0.100, "m", "analog", "REF ECHT (100 mm OD); D_in = D_out - 2 h", "measured",
          "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-15", "t_wall_m", "channel wall thickness", [0.003, 0.006], "m", "assumed",
          "assumed; EXT-MAZOUFFRE2005 p. 4 'thickness of both inner and outer dielectric wall is a few mm' (context)", "assumed",
          "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-16", "D_core_m", "inner magnetic core diameter", [0.030, 0.050], "m", "assumed", "assumed (must fit inside D_in - 2 t_wall with the inner coil)",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-17", "L_core_m", "inner core conduction length to the back pole", [0.10, 0.12], "m", "assumed", "assumed (> L_ch)",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-18", "D_body_m", "outer magnetic shell / body outer diameter", [0.14, 0.18], "m", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_7_mechanical_bom/ (envelope)", "FLIGHT_REPRESENTATIVE"),
        P("H25-19", "L_body_m", "body length (outer shell)", [0.10, 0.13], "m", "assumed", "assumed", "assumed",
          "PENDING docs/hardware/h2/h2_7_mechanical_bom/ (envelope)", "FLIGHT_REPRESENTATIVE"),
        P("H25-20", "t_shell_m", "outer shell wall thickness (conduction to back pole)", [0.003, 0.006], "m", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-21", "w_support_m", "axial width of each wall-to-back-pole support contact ring", [0.002, 0.005], "m", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/", "FLIGHT_REPRESENTATIVE"),
        P("H25-22", "A_cath_ext_m2", "C-1 body external radiating area", [0.002, 0.006], "m2", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_2_cathode_integration/", "FLIGHT_REPRESENTATIVE"),
        P("H25-23", "f_open_outer", "fraction of the outer-wall back surface that views the environment directly (open body)", [0.0, 0.5], "-",
          "assumed", "assumed; EXT-MAZOUFFRE2005 p. 5 (PPSX000 body 'open to enable the outer dielectric wall to evacuate most of its thermal power outwards', qualitative)",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (design choice)", "FLIGHT_REPRESENTATIVE"),
        # --- material properties
        P("H25-24", "k_BN_W_mK", "boron-nitride wall conductivity (20 degC, grade and direction span)", [10.0, 75.0], "W/(m K)",
          "analog", "EXT-HENZE2021 row 'Thermal Conductivity at 20 degC [W/mK]': 10 (CL-S 200, perp.) .. 75 (SL-A 400, par.); "
          "EXT-MARTINEZ2014 used 29 W/(m K) for M26", "measured",
          "PRELIMINARY (temperature dependence not given: verify; grade PENDING HWQ-08)", "FLIGHT_REPRESENTATIVE", "manufacturer typical values"),
        P("H25-25", "kFe_mult", "multiplier on the Wiedemann-Franz electronic conductivity of soft iron", [1.0, 1.25], "-",
          "assumed", "WF (Sommerfeld L0) from EXT-NICOFE-A848 resistivity table is the electronic part only (lower bound); +25 % "
          "upper for lattice conduction / Lorenz-number deviation is assumed (verify with a sourced k(T) of the HW-MC-13 grade)",
          "assumed", "PRELIMINARY", "FLIGHT_REPRESENTATIVE",
          "the datasheet's own 'Thermal conductivity 0.73 W/mK' is inconsistent with its 10.7 microohm-cm resistivity by ~90x (unit slip?): not used"),
        P("H25-26", "eps_BN", "BN-SiO2 wall emissivity", 0.92, "-", "analog",
          "EXT-MAZOUFFRE2005 p. 4: 'In the 8-9 um spectral band ... the BN-SiO2 emissivity mean value is 0.92' (also EXT-MARTINEZ2014 p. 11)",
          "measured", "PRELIMINARY (spectral band value used as total hemispherical: verify)", "FLIGHT_REPRESENTATIVE"),
        P("H25-27", "eps_metal", "internal metal surfaces (poles, coil cans, cathode body) emittance", [0.14, 0.38], "-",
          "analog", "EXT-HENNINGER1984 p. 10 stainless steel machined 0.14 .. sandblasted 0.38 (room-temperature normal emittance)",
          "measured", "PRELIMINARY (iron and elevated-temperature values: verify)", "FLIGHT_REPRESENTATIVE"),
        P("H25-28", "eps_anode", "anode emittance", [0.14, 0.80], "-", "analog",
          "lower EXT-HENNINGER1984 machined stainless 0.14; upper EXT-MAZOUFFRE2005 p. 4 'emissivity of the latter was fixed to 0.8' (assumed there)",
          "assumed", "TBD - requires the anode material (owner question HWQ-08, W3)", "FLIGHT_REPRESENTATIVE"),
        P("H25-29", "finish", "exterior finish option of MC-1 shell / back pole (design option)", {k: {"alpha_s": v["alpha"], "eps": v["eps"]} for k, v in FINISHES.items()},
          "-", "analog", "; ".join(v["locator"] for v in FINISHES.values()), "measured",
          "PRELIMINARY (design option; high-temperature coating capability TBD)", "FLIGHT_REPRESENTATIVE"),
        # --- contacts and mounts
        P("H25-30", "h_contact_W_m2K", "bolted/clamped interface contact conductance", [155.0, 3100.0], "W/(m2 K)", "analog",
          "EXT-MYERS2016 Table 6 (HERMeS TDU-1, correlation-tuned): 155 .. 3100 W/m2-K for pole/coil/shield interfaces (anode-to-DC 15500 excluded)",
          "inferred", "PRELIMINARY (tuned values of another thruster; measured on the H-1 bench in S1a)", "FLIGHT_REPRESENTATIVE"),
        P("H25-31", "G_anode_mount_W_K", "anode to back pole conductance (isolators + gas feed)", [0.1, 1.0], "W/K", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ + docs/hardware/h2/h2_3_gas_path_plenum/", "FLIGHT_REPRESENTATIVE"),
        P("H25-32", "G_cath_mount_W_K", "C-1 body to back pole conductance (mount bracket)", [0.1, 2.0], "W/K", "assumed", "assumed",
          "assumed", "PENDING docs/hardware/h2/h2_2_cathode_integration/", "FLIGHT_REPRESENTATIVE"),
        P("H25-33", "G_mount_W_K", "thruster to mounting-interface conductance (thrust stand / spacecraft)", [0.2, 2.0], "W/K", "assumed",
          "assumed; EXT-MYERS2016 p. 9 context: ~6 % of the HERMeS heat load conducted into its stand", "assumed",
          "TBD - requires the spacecraft thermal ICD (flight) / H2-6 fixture design (ground)", "FLIGHT_REPRESENTATIVE"),
        # --- sinks
        P("H25-34", "T_env_ground_K", "facility radiative sink temperature (ground test)", [246.15, 293.15], "K", "analog",
          "EXT-MYERS2016 p. 9: VF-5 dormant thruster -27 degC (cryopanel environment) .. ambient 20 degC", "measured",
          "PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ (facility)", "GROUND_FACILITY_ONLY"),
        P("H25-35", "T_mount_ground_K", "thrust-stand interface temperature (ground)", [293.15, 315.15], "K", "analog",
          "EXT-MYERS2016 p. 9: ambient 20 degC; 'stand base temperature was recorded (42 C)'", "measured",
          "PENDING docs/hardware/h2/h2_6_diagnostics_fixture/", "GROUND_FACILITY_ONLY"),
        P("H25-36", "T_mount_orbit_K", "spacecraft mounting-interface temperature (orbit)", [273.15, 323.15], "K", "assumed",
          "assumed evaluation range", "assumed", "TBD - requires the spacecraft thermal ICD (owner)", "FLIGHT_REPRESENTATIVE"),
        P("H25-37", "S_solar_W_m2", "direct solar irradiance, cold/hot", [1322.0, 1414.0], "W/m2", "analog",
          "EXT-NASA-TM2001 sec. 3: Cold Case 1322, Median 1367, Hot Case 1414 W/m2", "measured", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
        P("H25-38", "albedo_OLR_hot", "hot-case albedo and OLR (90-min averaging, max over the three inclination tables)", {"albedo": 0.26, "OLR_W_m2": 275.0},
          "-, W/m2", "analog", "EXT-NASA-TM2001 Tables 4.2.3-1..3, 'Combined' hot cases, 90 minute: 0.24/275 (low), 0.26/257 (medium), 0.26/244 (high); "
          "max albedo and max OLR combined (conservative); referenced to R_E + 30 km", "measured",
          "PRELIMINARY (orbit inclination not fixed by the RFP; thruster time constant PENDING S1)", "FLIGHT_REPRESENTATIVE"),
        P("H25-39", "OLR_cold_W_m2", "cold-case OLR (90-min, min 'Combined' cold over the three tables); eclipse => no solar/albedo", 218.0, "W/m2", "analog",
          "EXT-NASA-TM2001 Tables 4.2.3-1..3 'Combined' cold cases, 90 minute: 228, 218, 218", "measured", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
        P("H25-40", "F_e_lateral", "Earth view factor of the body lateral surface (and front faces)", [0.0, round(eb180["F_e_lateral_upper_bound"], 4)], "-",
          "derived", f"upper bound (180 + 2 x horizon dip)/360 at 180 km, dip {eb180['horizon_dip_deg']:.3f} deg from R_E (abep_sim/constants.py R_EARTH)",
          "model-derived", "PRELIMINARY (attitude/shadowing PENDING spacecraft ICD)", "FLIGHT_REPRESENTATIVE"),
        P("H25-41", "F_s_lateral", "solar view factor of the body lateral surface", [0.0, round(1 / math.pi, 4)], "-", "derived",
          "projected/total lateral area of a cylinder = 1/pi (sun normal to the axis)", "model-derived", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
        P("H25-42", "F_s_face", "solar view factor of front faces / exit aperture", [0.0, 1.0], "-", "derived", "geometric bound", "model-derived",
          "PRELIMINARY", "FLIGHT_REPRESENTATIVE", "solar into the aperture is booked on the anode with absorptance bounded by 1"),
        P("H25-43", "view_factors_channel", "channel-exit view factors (2-D crossed strings, curvature neglected)",
          {k: round(v, 5) for k, v in ex_vf.items()}, "-", "derived", "Hottel crossed-string method on L = 86 mm, h = 10 mm (H25-12, H25-13)",
          "model-derived", "PRELIMINARY", "FLIGHT_REPRESENTATIVE"),
    ]
    return rows


# ----------------------------------------------------------------------------------------------- limits
def build_limits() -> list:
    lim = "schemas/thermal_life/limits_v1.json"
    return [
        {"node": "WI/WO", "quantity": "BN wall maximum use temperature, oxidizing atmosphere", "value_C": 900.0,
         "source": f"{lim} records bn_hebosint_* T_use_max_oxidizing_C ('~ 900', EXT-HENZE2021)", "evidence_class": "measured",
         "applies": "O-bearing feed: the oxidizing value applies (conservative); atomic O and ion bombardment not covered (AOL-M02/M03)",
         "live": True},
        {"node": "WI/WO", "quantity": "BN maximum use temperature, inert/vacuum (context only)", "value_C": [1500.0, 2000.0],
         "source": f"{lim} bn_hebosint_* T_use_max_inert_vacuum_C", "evidence_class": "measured", "applies": "not used (air feed)", "live": False},
        {"node": "CI/CO", "quantity": "coil insulation thermal class candidates (IEC 60085 Table 1)", "value_C": [180.0, 200.0, 220.0, 250.0],
         "source": f"{lim} record iec60085_thermal_classes (classes over 250 increase in 25 degC increments)", "evidence_class": "measured",
         "applies": "compared with the lumped coil temperature; hot-spot offset TBD (HW-MC-14); the EIS family is HWQ-20; EEE-INST-002 derating is reference only (HW-MC-08)",
         "live": True},
        {"node": "CI/CO (permanent-magnet MC-1 option)", "quantity": "Sm2Co17 maximum service / use temperature", "value_C": [300.0, 350.0],
         "source": f"{lim} pm_sm2co17_recoma35e T_max_use_C 300, pm_smco_2_17_mmpa 350 (Curie 820 / 825)", "evidence_class": "measured",
         "applies": "only if HWQ-19 selects permanent magnets; irreversible-loss criterion additionally (HW-MC-09)", "live": True},
        {"node": "PI/PO/BP", "quantity": "soft-magnetic pole/core maximum temperature", "value_C": None,
         "source": "TBD - requires the HW-MC-13 grade (HWQ-18) with B-H and saturation vs temperature; iron Curie point 770 degC is from memory (verify) and is NOT used as a limit",
         "evidence_class": "assumed", "applies": "no margin computed", "live": False},
        {"node": "AN", "quantity": "anode maximum temperature", "value_C": None,
         "source": "TBD - requires the anode material (HWQ-08) and its oxidation behaviour in O2/atomic O (AOL-M01)", "evidence_class": "assumed",
         "applies": "temperature reported for AOL-M01 only", "live": False},
        {"node": "CB (keeper/body)", "quantity": "cathode assembly limiting temperature", "value_C": None,
         "source": f"{lim} record cathode_assembly_temperature_limit is TBD", "evidence_class": "assumed", "applies": "no margin computed", "live": False},
        {"node": "CE (emitter)", "quantity": "LaB6 temperature for O2 tolerance (a MINIMUM, not a maximum)", "value_C": 1570.0,
         "source": f"{lim} lab6_poisoning_goebel (Goebel & Katz 2008 sec. 6.8.5 p. 306: LaB6 at 1570 C withstands pO2 up to 1e-4 Torr)",
         "evidence_class": "measured", "applies": "emitter temperature is set by emission (thermal_life Richardson-Dushman), not by this network", "live": False},
        {"node": "PPU", "quantity": "transistor junction temperature derating", "value_C": 125.0,
         "source": "EXT-EEE-INST-002 Section S1 Table 4 'Transistor derating requirements' note 2 (p. 12 of 13): 'Do not exceed Tj = 125 C or 40 C below the manufacturer's maximum rating, whichever is lower'; microcircuits (M3 Table 4 note 2): 110 C",
         "evidence_class": "measured", "applies": "baseplate allowable = Tj,derated - junction-to-baseplate rise (PENDING H2-4 device selection)", "live": False},
        {"node": "COMP", "quantity": "compressor motor / bearing limit", "value_C": None,
         "source": "TBD - requires the compressor selection (docs/architecture_comparison/compressor_downselect/, PENDING docs/hardware/h2/h2_3_gas_path_plenum/)",
         "evidence_class": "assumed", "applies": "demand only", "live": False},
        {"node": "GP", "quantity": "gas path / plenum / valve seal limit and T_feed band", "value_C": None,
         "source": "TBD - requires valve and seal datasheets (PENDING docs/hardware/h2/h2_3_gas_path_plenum/) and the W1 feed-state T_feed (HW-ENV-04)",
         "evidence_class": "assumed", "applies": "demand only", "live": False},
    ]


# ----------------------------------------------------------------------------------------------- network
NODES = ["AN", "WI", "WO", "PI", "PO", "BP", "CI", "CO", "CB"]
NODE_INFO = {
    "AN": ("anode / gas distributor", "H-1", "FLIGHT_REPRESENTATIVE"),
    "WI": ("inner channel wall (BN)", "H-1", "FLIGHT_REPRESENTATIVE"),
    "WO": ("outer channel wall (BN)", "H-1", "FLIGHT_REPRESENTATIVE"),
    "PI": ("inner magnetic core + inner front pole", "MC-1", "FLIGHT_REPRESENTATIVE"),
    "PO": ("outer magnetic shell + outer front pole", "MC-1", "FLIGHT_REPRESENTATIVE"),
    "BP": ("back pole / back plate (carries IP-DN and the mount)", "MC-1 / H-1", "FLIGHT_REPRESENTATIVE"),
    "CI": ("inner coil (lumped winding)", "MC-1", "FLIGHT_REPRESENTATIVE"),
    "CO": ("outer coil(s) (lumped winding)", "MC-1", "FLIGHT_REPRESENTATIVE"),
    "CB": ("cathode body + keeper (lumped)", "C-1", "FLIGHT_REPRESENTATIVE"),
}
UNC_KEYS = ["f_anode", "f_walls", "f_pole", "P_mag_W", "Q_cath_W", "t_wall_m", "D_core_m", "L_core_m", "D_body_m", "L_body_m",
            "t_shell_m", "w_support_m", "A_cath_ext_m2", "f_open_outer", "k_BN_W_mK", "kFe_mult", "eps_metal", "eps_anode",
            "h_contact_W_m2K", "G_anode_mount_W_K", "G_cath_mount_W_K", "G_mount_W_K"]
CASE_KEYS = {"ground": ["T_env_ground_K", "T_mount_ground_K"],
             "orbit_hot": ["T_mount_orbit_K", "F_e_lateral", "F_s_lateral", "F_s_face"],
             "orbit_cold": ["T_mount_orbit_K", "F_e_lateral"]}


def param_map(rows):
    return {r["key"]: r for r in rows}


def ranges_for(case, pm):
    out = {}
    for k in UNC_KEYS + CASE_KEYS[case]:
        v = pm[k]["value"]
        if not (isinstance(v, list) and len(v) == 2):
            raise ValueError(f"parameter {k} must be a [lo, hi] range")
        out[k] = (float(v[0]), float(v[1]))
    return out


def fixed_inputs(pm):
    need = ["L_ch_m", "h_ch_m", "D_out_m", "eps_BN", "coil_split_inner", "Q_PIM_W", "S_solar_W_m2", "albedo_OLR_hot", "OLR_cold_W_m2"]
    for k in need:
        if pm.get(k) is None or pm[k]["value"] is None:
            raise ValueError(f"missing input {k}")
    return {"L": pm["L_ch_m"]["value"], "h": pm["h_ch_m"]["value"], "D_out": pm["D_out_m"]["value"],
            "eps_BN": pm["eps_BN"]["value"], "split_in": pm["coil_split_inner"]["value"], "Q_PIM": pm["Q_PIM_W"]["value"],
            "S_hot": pm["S_solar_W_m2"]["value"][1], "albedo_hot": pm["albedo_OLR_hot"]["value"]["albedo"],
            "OLR_hot": pm["albedo_OLR_hot"]["value"]["OLR_W_m2"], "OLR_cold": pm["OLR_cold_W_m2"]["value"]}


def assemble(x, fx, case, finish, P_d):
    """Build heat loads and links. x: uncertain + case parameters (dict). Returns (loads, links, bnd)."""
    for k in UNC_KEYS + CASE_KEYS[case]:
        if k not in x:
            raise ValueError(f"missing input {k}")
    L, h, Do = fx["L"], fx["h"], fx["D_out"]
    Di = Do - 2 * h
    tw = x["t_wall_m"]
    if x["D_core_m"] >= Di - 2 * tw:
        raise ValueError("inconsistent geometry: core does not fit inside the inner wall")
    if x["D_body_m"] <= Do + 2 * tw + 2 * x["t_shell_m"]:
        raise ValueError("inconsistent geometry: body smaller than the channel")
    vf = slot_view_factors(L, h)
    alpha, eps_ext = FINISHES[finish]["alpha"], FINISHES[finish]["eps"]
    em, ean, eBN = x["eps_metal"], x["eps_anode"], fx["eps_BN"]
    hc = x["h_contact_W_m2K"]
    A_an = math.pi / 4 * (Do ** 2 - Di ** 2)
    A_WI, A_WO = math.pi * Di * L, math.pi * Do * L
    A_WIb, A_WOb = math.pi * (Di - 2 * tw) * L, math.pi * (Do + 2 * tw) * L
    A_CIo = math.pi * (Di - 2 * tw) * L          # inner coil outer surface facing the inner wall back (gap neglected)
    A_COi = math.pi * (Do + 2 * tw) * L          # outer coil inner surface facing the outer wall back
    Dcore, Lcore = x["D_core_m"], x["L_core_m"]
    Db, Lb, ts = x["D_body_m"], x["L_body_m"], x["t_shell_m"]
    A_pf = math.pi / 4 * (Di - 2 * tw) ** 2                  # inner front pole face (disc inside the inner wall)
    A_opf = math.pi / 4 * (Db ** 2 - (Do + 2 * tw) ** 2)     # outer front pole annulus
    A_lat = math.pi * Db * Lb
    A_rear = math.pi / 4 * Db ** 2
    # --- loads
    Pm = x["P_mag_W"]
    loads = {"AN": x["f_anode"] * P_d, "WI": x["f_walls"] * P_d * A_WI / (A_WI + A_WO),
             "WO": x["f_walls"] * P_d * A_WO / (A_WI + A_WO), "PI": x["f_pole"] * P_d,
             "PO": 0.0, "BP": fx["Q_PIM"], "CI": fx["split_in"] * Pm, "CO": (1 - fx["split_in"]) * Pm, "CB": x["Q_cath_W"]}
    # --- links between nodes: ("cond", i, j, G) | ("condFe", i, j, A_over_L) | ("rad", i, j, Rsum)
    links = []
    kbn = x["k_BN_W_mK"]
    for wall, D in (("WI", Di), ("WO", Do)):
        G_ax = kbn * math.pi * D * tw / (L / 2)
        G_c = hc * math.pi * D * x["w_support_m"]
        links.append(("cond", wall, "BP", 1 / (1 / G_ax + 1 / G_c)))
    F_an_w = 1 - vf["F_anode_to_exit"]
    for wall, A in (("WI", A_WI), ("WO", A_WO)):
        share = A / (A_WI + A_WO)
        links.append(("rad", "AN", wall, two_surface_R(ean, A_an, eBN, A, F_an_w * share)))
    links.append(("cond", "AN", "BP", x["G_anode_mount_W_K"]))
    links.append(("rad", "WI", "CI", two_surface_R(eBN, A_WIb, em, A_CIo, 1.0)))
    fo = x["f_open_outer"]
    if fo < 1.0:
        links.append(("rad", "WO", "CO", two_surface_R(eBN, A_WOb * (1 - fo), em, A_COi * (1 - fo), 1.0)))
    L_coil = L
    links.append(("cond", "CI", "PI", hc * math.pi * Dcore * L_coil))
    links.append(("cond", "CO", "PO", hc * math.pi * (Db - 2 * ts) * L_coil))
    links.append(("condFe", "PI", "BP", math.pi * Dcore ** 2 / 4 / Lcore))
    A_sh = math.pi * Db * ts
    links.append(("condFe_contact", "PO", "BP", A_sh / Lb, hc * A_sh))
    links.append(("cond", "CB", "BP", x["G_cath_mount_W_K"]))
    # --- boundary exchanges: ("rad_env", node, eps*A, absorbed_W) and ("cond_mount", node, G, T_mount)
    if case == "ground":
        Tenv = x["T_env_ground_K"]
        q = {"lat": 0.0, "face": 0.0, "pole_face": 0.0, "aperture": 0.0}
        Tm = x["T_mount_ground_K"]
        rear_T = Tenv
    elif case == "orbit_hot":
        Tenv, Tm = 0.0, x["T_mount_orbit_K"]
        S, a, OLR = fx["S_hot"], fx["albedo_hot"], fx["OLR_hot"]
        Fe = x["F_e_lateral"]
        q = {"lat": alpha * (S * x["F_s_lateral"] + a * S * Fe) + eps_ext * OLR * Fe,
             "face": alpha * (S * x["F_s_face"] + a * S * Fe) + eps_ext * OLR * Fe,
             # bare metal inner pole face: solar/albedo absorptance bounded by 1 (no sourced alpha for the pole grade)
             "pole_face": 1.0 * (S * x["F_s_face"] + a * S * Fe) + em * OLR * Fe,
             "aperture": 1.0 * S * x["F_s_face"]}
        rear_T = Tm
    elif case == "orbit_cold":
        Tenv, Tm = 0.0, x["T_mount_orbit_K"]
        Fe = x["F_e_lateral"]
        q = {"lat": eps_ext * fx["OLR_cold"] * Fe, "face": eps_ext * fx["OLR_cold"] * Fe,
             "pole_face": em * fx["OLR_cold"] * Fe, "aperture": 0.0}
        rear_T = Tm
    else:
        raise ValueError(case)
    bnd = [
        ("rad_env", "AN", ean * A_an * vf["F_anode_to_exit"], q["aperture"] * A_an, Tenv),
        ("rad_env", "WI", eBN * A_WI * vf["F_wall_to_exit"], 0.0, Tenv),
        ("rad_env", "WO", eBN * A_WO * vf["F_wall_to_exit"], 0.0, Tenv),
        ("rad_env", "WO", eBN * A_WOb * fo, 0.0, Tenv),
        ("rad_env", "PI", em * A_pf, q["pole_face"] * A_pf, Tenv),
        ("rad_env", "PO", eps_ext * (A_lat + A_opf), q["lat"] * A_lat + q["face"] * A_opf, Tenv),
        ("rad_env", "BP", eps_ext * A_rear, 0.0, rear_T),
        ("rad_env", "CB", em * x["A_cath_ext_m2"], 0.0, Tenv),
        ("cond_mount", "BP", x["G_mount_W_K"], Tm),
    ]
    return loads, links, bnd, x["kFe_mult"]


def solve(loads, links, bnd, kFe_mult, T0=450.0):
    idx = {n: i for i, n in enumerate(NODES)}
    n = len(NODES)

    def flows(T):
        r = np.array([loads[nd] for nd in NODES], dtype=float)
        for lk in links:
            typ, a, b = lk[0], idx[lk[1]], idx[lk[2]]
            if typ == "cond":
                Q = lk[3] * (T[a] - T[b])
            elif typ == "rad":
                Q = SIGMA_SB * (T[a] ** 4 - T[b] ** 4) / lk[3]
            elif typ in ("condFe", "condFe_contact"):
                Tm = 0.5 * (T[a] + T[b])
                G = fe_k_wf(Tm, kFe_mult) * lk[3]
                if typ == "condFe_contact":
                    G = 1 / (1 / G + 1 / lk[4])
                Q = G * (T[a] - T[b])
            else:
                raise ValueError(typ)
            r[a] -= Q
            r[b] += Q
        out = 0.0
        for bd in bnd:
            i = idx[bd[1]]
            if bd[0] == "rad_env":
                Q = bd[2] * SIGMA_SB * (T[i] ** 4 - bd[4] ** 4) - bd[3]
            else:
                Q = bd[2] * (T[i] - bd[3])
            r[i] -= Q
            out += Q
        return r, out

    T = np.full(n, float(T0))
    for it in range(200):
        r, _ = flows(T)
        J = np.zeros((n, n))
        for j in range(n):
            dT = 1e-3
            Tp = T.copy()
            Tp[j] += dT
            J[:, j] = (flows(Tp)[0] - r) / dT
        step = np.linalg.solve(J, -r)
        step = np.clip(step, -100.0, 100.0)
        T = T + step
        if np.max(np.abs(step)) < 1e-7:
            r, out = flows(T)
            if np.max(np.abs(r)) > 1e-6:
                break
            total_in = sum(loads.values()) + sum(bd[3] for bd in bnd if bd[0] == "rad_env")
            total_out = out + sum(bd[3] for bd in bnd if bd[0] == "rad_env")
            if abs(total_in - total_out) > 1e-6 * max(1.0, total_in):
                raise RuntimeError("energy balance does not close")
            return {nd: float(T[i]) for i, nd in enumerate(NODES)}, {"iterations": it + 1, "load_W": sum(loads.values()),
                                                                     "rejected_W": out, "max_residual_W": float(np.max(np.abs(r))),
                                                                     "fe_k_held_at_0C": any(0.5 * (T[idx[lk[1]]] + T[idx[lk[2]]]) < T0C
                                                                                            for lk in links if lk[0].startswith("condFe"))}
    raise RuntimeError("thermal network did not converge (MODEL_ERROR); no half-converged state is returned")


MOUNT_KEY = {"ground": "T_mount_ground_K", "orbit_hot": "T_mount_orbit_K", "orbit_cold": "T_mount_orbit_K"}
OUTS = NODES + ["Q_mount_W"]
COIL_CLASSES_C = [180.0, 200.0, 220.0, 250.0]
PM_LIMITS_C = [300.0, 350.0]
WALL_LIMIT_C = 900.0


def run(x, fx, case, finish, P_d):
    loads, links, bnd, km = assemble(x, fx, case, finish, P_d)
    T, info = solve(loads, links, bnd, km)
    out = dict(T)
    out["Q_mount_W"] = x["G_mount_W_K"] * (T["BP"] - x[MOUNT_KEY[case]])
    return out, info


# ----------------------------------------------------------------------------------------------- envelope
def envelope(pm, fx, case, finish, P_d):
    rg = ranges_for(case, pm)
    nom = {k: 0.5 * (lo + hi) for k, (lo, hi) in rg.items()}
    T_nom, _ = run(nom, fx, case, finish, P_d)
    sens = {}
    for k, (lo, hi) in rg.items():
        xl, xh = dict(nom), dict(nom)
        xl[k], xh[k] = lo, hi
        Tl, _ = run(xl, fx, case, finish, P_d)
        Th, _ = run(xh, fx, case, finish, P_d)
        sens[k] = {o: Th[o] - Tl[o] for o in OUTS}
    res = {}
    for o in OUTS:
        xmax = {k: (rg[k][1] if sens[k][o] >= 0 else rg[k][0]) for k in rg}
        xmin = {k: (rg[k][0] if sens[k][o] >= 0 else rg[k][1]) for k in rg}
        Tmax, bal = run(xmax, fx, case, finish, P_d)
        Tmin, bal_min = run(xmin, fx, case, finish, P_d)
        dom = sorted(rg, key=lambda k: -abs(sens[k][o]))[:3]
        if o == "Q_mount_W":
            res[o] = {"min_W": round(Tmin[o], 2), "nominal_W": round(T_nom[o], 2), "max_W": round(Tmax[o], 2),
                      "dominant_inputs": [{"input": k, "d_lo_to_hi_W": round(sens[k][o], 2)} for k in dom]}
            continue
        res[o] = {"T_min_K": round(Tmin[o], 2), "T_nominal_K": round(T_nom[o], 2), "T_max_K": round(Tmax[o], 2),
                  "dominant_inputs": [{"input": k, "dT_lo_to_hi_K": round(sens[k][o], 2)} for k in dom],
                  "hot_corner_energy_balance_W": {"load": round(bal["load_W"], 3), "rejected_to_boundaries": round(bal["rejected_W"], 3)},
                  "iron_k_held_at_0C": {"hot_corner": bal["fe_k_held_at_0C"], "cold_corner": bal_min["fe_k_held_at_0C"]}}
    # influence coefficient of the pre-ionizer-slot heat (PMI-05) at the nominal point
    fx1 = dict(fx)
    fx1["Q_PIM"] = fx["Q_PIM"] + 1.0
    T_pim, _ = run(nom, fx1, case, finish, P_d)
    for nd in NODES:
        res[nd]["dT_dQ_PIM_K_per_W_nominal"] = round(T_pim[nd] - T_nom[nd], 4)
    return res, rg


def _pct(vals, q):
    v = sorted(vals)
    i = q * (len(v) - 1)
    lo = int(math.floor(i))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def lhs_check(fx, case, finish, P_d, env, rg, n=N_LHS):
    """Seeded Latin-hypercube sample of the input box (coverage of the box, NOT a probability distribution): checks the
    corner bounds and reports sample statistics and the fraction of samples above each live limit."""
    rnd = random.Random(f"{RNG_SEED}-{case}-{finish}-{P_d}")
    keys = sorted(rg)
    perms = {k: rnd.sample(range(n), n) for k in keys}
    samples = {o: [] for o in OUTS}
    for s in range(n):
        x = {}
        for k in keys:
            lo, hi = rg[k]
            u = (perms[k][s] + rnd.random()) / n
            x[k] = lo + u * (hi - lo)
        T, _ = run(x, fx, case, finish, P_d)
        for o in OUTS:
            samples[o].append(T[o])
    out = {"n": n, "seed": f"{RNG_SEED}-{case}-{finish}-{P_d}", "nodes": {}}
    for nd in NODES:
        v = samples[nd]
        out["nodes"][nd] = {"sample_min_C": round(min(v) - T0C, 1), "sample_median_C": round(_pct(v, 0.5) - T0C, 1),
                            "sample_p95_C": round(_pct(v, 0.95) - T0C, 1), "sample_max_C": round(max(v) - T0C, 1),
                            "max_sample_above_corner_T_max_K": round(max(v) - env[nd]["T_max_K"], 3),
                            "max_sample_below_corner_T_min_K": round(env[nd]["T_min_K"] - min(v), 3)}
    q = samples["Q_mount_W"]
    out["Q_mount_W"] = {"sample_min": round(min(q), 1), "sample_median": round(_pct(q, 0.5), 1), "sample_max": round(max(q), 1),
                        "max_sample_above_corner_max": round(max(q) - env["Q_mount_W"]["max_W"], 3)}
    frac = {}
    for nd in ("WI", "WO"):
        frac[f"{nd}>BN 900"] = round(sum(t > WALL_LIMIT_C + T0C for t in samples[nd]) / n, 4)
    for nd in ("CI", "CO"):
        for c in COIL_CLASSES_C + PM_LIMITS_C:
            frac[f"{nd}>{int(c)}"] = round(sum(t > c + T0C for t in samples[nd]) / n, 4)
    out["fraction_of_samples_above_limit"] = frac
    return out


def verdict(Tmin_K, Tmax_K, limit_C):
    if limit_C is None:
        return "NO_LIMIT_TBD"
    Lk = limit_C + T0C
    if Tmax_K <= Lk:
        return "PASS_WHOLE_ENVELOPE"
    if Tmin_K > Lk:
        return "EXCEEDED_WHOLE_ENVELOPE"
    return "DESIGN_DRIVING"


def evaluate(rows):
    pm = param_map(rows)
    fx = fixed_inputs(pm)
    Pd_max = pm["P_d_max_W"]["value"]
    grid = [round(f * Pd_max, 3) for f in pm["P_d_grid_frac"]["value"]]
    out = {"method": ("per output: one-at-a-time sensitivity (lo->hi at the range midpoints) fixes the sign of each input; the "
                      "per-output hot (cold) corner puts every input at the end that raises (lowers) that output; T_max/T_min are the "
                      "solves at those corners (a bounding envelope: all adverse ends together). Monotonicity is checked by a "
                      "seeded Latin-hypercube sample of the input box at P_d max, which also gives sample statistics (box coverage, "
                      "not probabilities)"),
           "P_d_grid_W": grid, "n_lhs": N_LHS, "cases": {}}
    for case in ("ground", "orbit_hot", "orbit_cold"):
        out["cases"][case] = {}
        for finish in FINISHES:
            per_pd = {}
            for P_d in grid:
                env, rg = envelope(pm, fx, case, finish, P_d)
                per_pd[str(P_d)] = env
            env_max = per_pd[str(grid[-1])]
            chk = lhs_check(fx, case, finish, grid[-1], env_max, ranges_for(case, pm))
            out["cases"][case][finish] = {"by_P_d_W": per_pd, "lhs_at_P_d_max": chk}
    return out


def _mrow(case, finish, nd, label, c, e, frac):
    return {"case": case, "finish": finish, "node": nd, "limit": label, "limit_C": c,
            "T_min_C": round(e[nd]["T_min_K"] - T0C, 1), "T_nominal_C": round(e[nd]["T_nominal_K"] - T0C, 1),
            "T_max_C": round(e[nd]["T_max_K"] - T0C, 1),
            "margin_worst_K": round(c + T0C - e[nd]["T_max_K"], 1), "margin_nominal_K": round(c + T0C - e[nd]["T_nominal_K"], 1),
            "margin_best_K": round(c + T0C - e[nd]["T_min_K"], 1),
            "verdict": verdict(e[nd]["T_min_K"], e[nd]["T_max_K"], c), "lhs_fraction_above_limit": frac,
            "dominant_inputs": [di["input"] for di in e[nd]["dominant_inputs"]]}


def margins(ev):
    """Margins to the live limits at P_d max for every case / finish; coil margins against each IEC class candidate and
    the Sm2Co17 permanent-magnet option."""
    rows = []
    Pd = str(ev["P_d_grid_W"][-1])
    for case, fin_d in ev["cases"].items():
        for finish, d in fin_d.items():
            e = d["by_P_d_W"][Pd]
            fr = d["lhs_at_P_d_max"]["fraction_of_samples_above_limit"]
            for nd in ("WI", "WO"):
                rows.append(_mrow(case, finish, nd, "BN oxidizing max use 900 degC", WALL_LIMIT_C, e, fr[f"{nd}>BN 900"]))
            for nd in ("CI", "CO"):
                for c in COIL_CLASSES_C:
                    rows.append(_mrow(case, finish, nd, f"IEC 60085 class {int(c)}", c, e, fr[f"{nd}>{int(c)}"]))
                for c in PM_LIMITS_C:
                    rows.append(_mrow(case, finish, nd, f"Sm2Co17 max use {int(c)} degC (PM option)", c, e, fr[f"{nd}>{int(c)}"]))
    return rows


def hard_incompatibility(margin_rows):
    """A node is a hard-incompatibility candidate only if its limit is exceeded across the WHOLE envelope for EVERY design
    option still open (every exterior finish, and for the coils every sourced insulation class and the PM option)."""
    findings = []
    for case in ("ground", "orbit_hot", "orbit_cold"):
        for node in ("WI", "WO", "CI", "CO"):
            rs = [r for r in margin_rows if r["case"] == case and r["node"] == node]
            if rs and all(r["verdict"] == "EXCEEDED_WHOLE_ENVELOPE" for r in rs):
                findings.append({"case": case, "node": node, "evidence": "every option exceeds its sourced limit over the whole envelope"})
    return findings


# ----------------------------------------------------------------------------------------------- material table
def material_table():
    rows = []
    for name, f in NIST_FITS.items():
        T = 293.15 if f["range_K"][1] >= 293.15 else None
        rows.append({"material": name, "T_K": T, "k_W_mK": round(nist_k(name, T), 2), "source": "EXT-NIST-CRYO", "fit_range_K": f["range_K"],
                     "fit_error_pct": f["fit_error_pct"], "evidence_class": "measured (curve fit to data)",
                     "note": "value at 293.15 K; elevated-temperature k is outside the fit range: TBD - requires a sourced k(T)"})
    for TC in (20.0, 200.0, 400.0, 600.0):
        T = TC + T0C
        rows.append({"material": "soft iron (A848 Type 1), WF electronic part", "T_K": T, "k_W_mK": round(fe_k_wf(T, 1.0), 2),
                     "source": "EXT-NICOFE-A848 resistivity table + Sommerfeld Lorenz number", "fit_range_K": [273.15, 1073.15],
                     "fit_error_pct": None, "evidence_class": "model-derived",
                     "note": "lower bound of k (electronic only); used with multiplier H25-25"})
    rows.append({"material": "hBN solids (HeBoSint grades)", "T_K": 293.15, "k_W_mK": [10.0, 75.0], "source": "EXT-HENZE2021",
                 "fit_range_K": None, "fit_error_pct": None, "evidence_class": "measured (typical, guide only)", "note": "grade and pressing direction span"})
    return rows


# ----------------------------------------------------------------------------------------------- deliverable
def spacecraft_side_demands(pm):
    Pbus = pm["P_bus_alloc_W"]["value"][1]
    eta_grid = [0.80, 0.85, 0.90, 0.95]
    return {
        "PPU": {"load": "Q_PPU = P_bus x (1 - eta_PPU) (all conversion loss is heat at the PPU baseplate)",
                "eta_PPU": "PENDING docs/hardware/h2/h2_4_ppu_bus/ (not selected here)",
                "evaluation_grid": [{"eta_PPU_assumed": e, "Q_PPU_W": round(Pbus * (1 - e), 1)} for e in eta_grid],
                "allowable": "T_baseplate <= Tj,derated - dT(junction->baseplate); Tj,derated = min(125 degC, T_j,max,rated - 40 degC) for transistors (EEE-INST-002 S1 Table 4 note 2)",
                "demand": "required baseplate conductance to the spacecraft sink G >= Q_PPU / (T_baseplate,allow - T_sink); T_sink PENDING spacecraft ICD",
                "scope": "FLIGHT_REPRESENTATIVE (H-1 uses laboratory supplies outside the thermal network, W3 PS-C)"},
        "COMP": {"load": "Q_comp = P_bus[compressor] (whole electrical input booked as heat at the compressor; gas enthalpy rise carried to the plenum, conservative for the motor node)",
                 "value": "PENDING docs/hardware/h2/h2_3_gas_path_plenum/ and docs/architecture_comparison/compressor_downselect/",
                 "limit": "TBD (motor / bearing / seal limits of the selected compressor)", "scope": "FLIGHT_REPRESENTATIVE"},
        "GP": {"load": "compressed-gas enthalpy + conduction from the compressor and from H-1 through the feed line",
               "coupling_to_H1": "the only H-1-side path is the anode gas feed (inside G_anode_mount, H25-31) and the IP-UP/IP-DN module slot (PMI-05); "
                                  "heat conducted from the anode into the feed line changes T_feed at HALL_INLET_Z0 - a measured result, never a Hall-closure input upstream",
               "limit": "TBD (valve/seal ratings; W1 T_feed band, HW-ENV-04)", "scope": "FLIGHT_REPRESENTATIVE"},
        "MI": {"quantity": "heat conducted into the spacecraft through the thruster mount, Q_mount = G_mount (T_BP - T_mount)",
               "status": "TBD - requires the spacecraft thermal ICD (allowable heat flux and interface temperature)", "scope": "FLIGHT_REPRESENTATIVE"},
    }


def mount_heat(ev):
    """Heat conducted into the mounting interface (stand / spacecraft) at P_d max: bounding corners and LHS statistics."""
    out = {}
    Pd = str(ev["P_d_grid_W"][-1])
    for case, fins in ev["cases"].items():
        for finish, d in fins.items():
            e = d["by_P_d_W"][Pd]["Q_mount_W"]
            out[f"{case}/{finish}"] = {"corner_min_W": e["min_W"], "nominal_W": e["nominal_W"], "corner_max_W": e["max_W"],
                                       "lhs": d["lhs_at_P_d_max"]["Q_mount_W"]}
    return out


def design_findings(ev, mrows):
    """Deterministic plain-language findings computed from the solve (no new numbers)."""
    Pd = str(ev["P_d_grid_W"][-1])
    out = []
    ci = [r for r in mrows if r["node"] == "CI" and r["limit"] == "IEC 60085 class 250"]
    lo = min(r["T_nominal_C"] for r in ci)
    hi = max(r["T_nominal_C"] for r in ci)
    fr = [r["lhs_fraction_above_limit"] for r in ci]
    out.append(f"F1 inner coil CI is the design-driving node: nominal (range-midpoint) temperature {lo:g}-{hi:g} degC across cases and "
               f"finishes at P_d = {float(Pd):g} W; {min(fr):.0%}-{max(fr):.0%} of the input-box samples exceed IEC class 250 degC. "
               "At this bounding P_d (the whole bus allocation) the inner coil needs an insulation class above 250 degC (IEC 60085 continues in "
               "25 degC steps; supplier EIS and endurance evidence required, HWQ-20), a permanent-magnet inner circuit (HWQ-19) or a stronger "
               "inner conduction path (core diameter, contacts); not a hard incompatibility (best corners pass).")
    wi = [r for r in mrows if r["node"] in ("WI", "WO")]
    out.append(f"F2 BN walls pass the 900 degC oxidizing guide value over the whole bounding envelope in every case "
               f"(smallest worst-corner margin {min(r['margin_worst_K'] for r in wi):g} K); atomic-O / ion effects are not covered by that limit.")
    co = [r for r in mrows if r["node"] == "CO" and r["limit"] == "IEC 60085 class 220"]
    out.append("F3 exterior finish is design-driving for the outer coil: with the high-emittance finish the outer-coil samples above 220 degC are "
               + ", ".join(f"{r['case']} {r['lhs_fraction_above_limit']:.0%}" for r in co if r["finish"] == "z93_white_inorganic")
               + "; with bare machined stainless "
               + ", ".join(f"{r['case']} {r['lhs_fraction_above_limit']:.0%}" for r in co if r["finish"] == "bare_machined_stainless") + ".")
    mh = mount_heat(ev)
    nom = [v["nominal_W"] for v in mh.values()]
    firsts = {}
    for fins in ev["cases"].values():
        for d in fins.values():
            for nd in NODES:
                k = d["by_P_d_W"][Pd][nd]["dominant_inputs"][0]["input"]
                firsts[k] = firsts.get(k, 0) + 1
    top = sorted(firsts.items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(firsts.values())
    out.append(f"F4 first-ranked dominant input over all node/case/finish envelopes at P_d max: "
               + ", ".join(f"{k} {v}/{total}" for k, v in top) + f". The nominal heat into the stand/spacecraft is "
               f"{min(nom):g}-{max(nom):g} W at P_d = {float(Pd):g} W, so the spacecraft thermal ICD (allowable heat and T_mount) is a "
               "first-order input (H25-Q3).")
    out.append("F5 anode and cathode-body temperatures have no sourced limit (HWQ-08, cathode_assembly_temperature_limit TBD); their ranges are "
               "reported for AOL-M01/M05 only.")
    return out


def build():
    rows = build_parameters()
    pm = param_map(rows)
    ev = evaluate(rows)
    mrows = margins(ev)
    hic = hard_incompatibility(mrows)
    Pd = str(ev["P_d_grid_W"][-1])
    # summary of design-driving findings
    summary = []
    for case, fins in ev["cases"].items():
        for finish, d in fins.items():
            e = d["by_P_d_W"][Pd]
            summary.append({"case": case, "finish": finish,
                            **{nd: [round(e[nd]["T_min_K"] - T0C, 1), round(e[nd]["T_max_K"] - T0C, 1)] for nd in NODES}})
    doc = {
        "schema": "h2_design_lane_v1",
        "id": "h2_5_thermal_network_v1",
        "lane": "H2_5",
        "follow_on": "fo_h2_5_thermal_network",
        "trigger": "T_H2_5_THERMAL_NETWORK",
        "owner_disposition": {"A7": PINNED["A7"]["path"]},
        "status": "DRAFT_PRELIMINARY",
        "base_commit": BASE_COMMIT,
        "date": "2026-09-27",
        "generated_by": f"{REL_DIR}/build_h2_5_thermal_network.py",
        "regenerate": f"python {REL_DIR}/build_h2_5_thermal_network.py",
        "test": "tests/test_h2_5_thermal_network.py",
        "architectures": list(ARCHS),
        "scope": ("preliminary lumped-node steady-state thermal network of the H-1 flight-representative test article (H-1, MC-1, C-1, "
                  "IP-DN pre-ionizer slot) plus spacecraft-side demand nodes (PPU, compressor, gas path/plenum, mounting interface); "
                  "ground-test and 180-230 km orbit sinks"),
        "what_this_is_not": [
            "not a Hall performance prediction: discharge heat is a parametric fraction of the P_d allocation bounded by published xenon analogs",
            "not an architecture selection: hall_only / rf_hall / ecr_hall are never ranked; the pre-ionizer slot enters only via PMI-05",
            "not a thermal qualification: steady state, lumped, preliminary geometry (ECHT analog + assumed, PENDING H2-1/H2-7)",
            "no Hall transport closure, screening candidate (sgb-screen-*), abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number is used",
            "abep_sim/thermal.py is not used (unsourced defaults, 0-D Hall heat booking; see provenance_checks)",
        ],
        "pinned_inputs": PINNED,
        "referenced_at_base_commit": REFERENCED_AT_BASE,
        "external_sources": EXTERNAL,
        "provenance_checks": {
            "abep_sim/thermal.py": "NOT USED. default_nodes() books thruster heat as 0.6 x (P_d - I_beam V_d 0.85) (superseded 0-D Hall closure) and hard-codes unsourced emissivities, conductances and limits; schemas/ledgers/thermal_rejection_ledger_v1.json node_map marks the thruster node 'superseded (0-D Hall closure)'; veto_layer_v1.json lists its defaults as unsourced.",
            "abep_sim/thermal_life.py": "READ ONLY, not imported. It accounts heat against sourced limits (schemas/thermal_life/limits_v1.json, pinned here and used for the BN, IEC 60085, Sm2Co17 and LaB6 records). Its hall_discharge wall-heat path is gated (G11) on an ADMITTED Hall map or measured hardware data: the analog fractions of this lane are NOT admissible thermal_life inputs and are never passed to it.",
            "abep_sim/plasma_devices.py": "NOT USED (superseded 0-D Hall).",
        },
        "configuration_items_used": {"H-1": "anode, walls, back plate, IP-DN flange", "MC-1": "core, shell, poles, coils", "C-1": "cathode body/keeper/emitter",
                                      "PIM-0 / PIM-RF / PIM-ECR": "slot at IP-DN via PMI-05 only (Q_PIM)", "SVC-1": "thermocouple harness (no heat load modelled)",
                                      "FS-C": "gas path (demand node GP)", "PS-C": "laboratory supplies (outside the network, ground)",
                                      "planes": ["IP-UP", "IP-DN", "HALL_INLET_Z0"]},
        "node_list": (
            [{"id": nd, "name": NODE_INFO[nd][0], "ci": NODE_INFO[nd][1], "scope": NODE_INFO[nd][2], "solved": True} for nd in NODES]
            + [{"id": "CE", "name": "cathode emitter (LaB6)", "ci": "C-1", "scope": "FLIGHT_REPRESENTATIVE", "solved": False,
                "reason": "temperature set by emission (Richardson-Dushman, abep_sim/thermal_life.py); its heat into H-1 is inside Q_cath (H25-10)"},
               {"id": "CK", "name": "cathode keeper", "ci": "C-1", "scope": "FLIGHT_REPRESENTATIVE", "solved": False,
                "reason": "lumped with the cathode body CB in v1 (keeper geometry PENDING H2-2)"},
               {"id": "PIM", "name": "pre-ionizer module interface slot (IP-UP..IP-DN)", "ci": "PIM-0 / PIM-RF / PIM-ECR", "scope": "H1_TEST_ARTICLE_ONLY",
                "solved": False, "reason": "enters only through the common thermal-rejection interface PMI-05 (PENDING docs/interfaces/preionizer_module/): heat Q_PIM into BP at IP-DN, reported as dT/dQ_PIM; identical for every occupant"},
               {"id": "PPU", "name": "PPU / power distribution", "ci": "flight PPU (H-1 uses PS-C lab supplies)", "scope": "FLIGHT_REPRESENTATIVE", "solved": False,
                "reason": "demand node: required conductance/area from Q_PPU (spacecraft_side_demands)"},
               {"id": "COMP", "name": "compressor", "ci": "atmospheric branch", "scope": "FLIGHT_REPRESENTATIVE", "solved": False, "reason": "demand node (PENDING H2-3)"},
               {"id": "GP", "name": "gas path / plenum", "ci": "FS-C (ground) / atmospheric branch (flight)", "scope": "FLIGHT_REPRESENTATIVE", "solved": False, "reason": "demand node (PENDING H2-3)"},
               {"id": "MI", "name": "mounting interface", "ci": "H-1 mount / spacecraft", "scope": "FLIGHT_REPRESENTATIVE", "solved": False,
                "reason": "boundary: T_mount (H25-35 ground, H25-36 orbit) through G_mount (H25-33)"}]),
        "links": {
            "conduction": [
                "WI->BP, WO->BP: series of axial BN conduction k_BN pi D t_w / (L/2) and support contact h_c pi D w_support",
                "AN->BP: G_anode_mount (isolators + feed tube)",
                "CI->PI: h_c pi D_core L; CO->PO: h_c pi (D_body - 2 t_shell) L",
                "PI->BP: k_Fe(T) pi D_core^2/4 / L_core (Wiedemann-Franz iron)",
                "PO->BP: k_Fe(T) pi D_body t_shell / L_body in series with the joint contact h_c pi D_body t_shell",
                "CB->BP: G_cath_mount", "BP->mount: G_mount to T_mount"],
            "radiation_internal": [
                "AN<->WI, AN<->WO: gray two-surface exchange, F = (1 - F_anode_to_exit) split by wall area",
                "WI back <-> CI: concentric cylinders F = 1", "WO back <-> CO: concentric cylinders, fraction (1 - f_open_outer)"],
            "radiation_to_environment": [
                "AN, WI, WO through the exit aperture (crossed-string F)", "WO back x f_open_outer",
                "PI front face (eps_metal)", "PO lateral + outer front face (exterior finish)",
                "BP rear face: facility (ground) / spacecraft at T_mount (orbit)", "CB (eps_metal)"],
            "orbit_absorbed": "q = alpha (S F_s + a S F_e) + eps OLR F_e per unit area (NASA/TM-2001-211221 parameters); aperture solar absorbed with alpha <= 1 (bound); deep-space sink 0 K (cosmic background neglected)",
            "k_BN_temperature_dependence": "not modelled (20 degC datasheet values; verify)",
        },
        "design_parameters": rows,
        "material_properties": material_table(),
        "limits": build_limits(),
        "solve": ev,
        "summary_at_P_d_max_degC": {"P_d_W": float(Pd), "note": "[T_min, T_max] degC per node", "rows": summary},
        "margins_at_P_d_max": mrows,
        "design_findings": design_findings(ev, mrows),
        "mount_heat_W": mount_heat(ev),
        "spacecraft_side_demands": spacecraft_side_demands(pm),
        "hard_incompatibility_check": {
            "rule": ("a node is a hard-incompatibility candidate only if its sourced limit is exceeded over the WHOLE plausible envelope for "
                     "EVERY still-open design option (each exterior finish; for coils each IEC 60085 class candidate up to 250 degC and the "
                     "Sm2Co17 permanent-magnet option); design-driving cases are not incompatibilities"),
            "checked": ["BN walls vs 900 degC oxidizing use limit", "coils vs IEC 60085 classes 180/200/220/250 degC and Sm2Co17 300/350 degC",
                        "ground, orbit hot, orbit cold", "three exterior finishes", "P_d up to the whole 1.35 kW bus allocation",
                        "anode / poles / cathode body: no sourced limit (TBD) -> cannot be vetoed"],
            "findings": hic,
            "result": "none found" if not hic else "HARD_INCOMPATIBILITY_CANDIDATE",
            "evidence_class_of_envelope": "inferred (xenon analog heat fractions) + assumed geometry; air-specific heat fractions are unknown",
        },
        "architecture_changing_blockers_touched": [
            {"blocker": 1, "how": "none decided. Indirect: wall/anode/magnet temperatures are confounders of the same-condition comparison (A6 order-balance clarification); T-SETTLE and thermocouple provisions (HW-H1-07/12) are fed by this network. No sustainment inference is made."},
            {"blocker": 2, "how": "informs, does not decide: any RF/ECR occupant heat entering H-1 at IP-DN raises BP/AN/walls by dT/dQ_PIM (reported, identical for every occupant) and thermal_control heater power is a P_bus term under bus_power_boundary_v1; the incremental-benefit decision stays with Phase 1"},
            {"blocker": 3, "how": "informs: C-1 heat into H-1 (Q_cath) and the emitter O2-tolerance temperature (>= 1570 degC, Goebel p. 306) are carried; Xe tank/regulator thermal control is a thermal_control heater term PENDING the Xe ledger (docs/budgets/xe_ledger/) and spacecraft cold case"},
        ],
        "m16_rows": [
            {"subsystem": "thermal control", "matured_by_this_lane": "node list, links, sinks, limits, preliminary envelope and margins",
             "proposed_state": "BLOCKED", "blocking_item": "H2-1 preliminary geometry and magnet-circuit design release (wall thickness, core/shell dimensions, coil P_mag and EIS) - PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/",
             "rollup_category": "hardware-definition blocker"},
            {"subsystem": "magnetic circuit", "matured_by_this_lane": "coil/magnet temperature envelope vs IEC 60085 classes and Sm2Co17; EIS class demand",
             "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "note": "owned by H2-1"},
            {"subsystem": "extended-channel Hall discharge chamber/accelerator", "matured_by_this_lane": "wall/anode temperature envelope; BN oxidizing-limit margin",
             "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "note": "owned by H2-1"},
            {"subsystem": "shielded Xe-fed LaB6 hollow cathode", "matured_by_this_lane": "cathode heat into H-1 and mount conductance demand",
             "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "note": "owned by H2-2"},
            {"subsystem": "PPU/power distribution", "matured_by_this_lane": "PPU heat demand structure (Q_PPU vs eta) and derating allowable",
             "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "note": "owned by H2-4"},
        ],
        "interface_demands": [
            {"from": "H2-5", "to": "H2-1 (docs/hardware/h2/h2_1_hall_chamber_magnet/)", "quantity": "wall thickness, core/shell/body dimensions, support contact widths, coil P_mag split and R(T), f_open_outer", "value": "ranges H25-15..H25-23, H25-08", "units": "m, W", "status": "PENDING"},
            {"from": "H2-5", "to": "H2-1", "quantity": "inner-coil thermal design: EIS class above 250 degC, permanent-magnet inner circuit, or a stronger inner conduction path (design_findings F1)", "value": "see margins_at_P_d_max (class vs finish)", "units": "degC", "status": "PRELIMINARY"},
            {"from": "H2-1", "to": "H2-5", "quantity": "selected EIS class / magnet option and coil hot-spot model (R(T), potting conductance)", "value": None, "units": "degC, ohm, W/K", "status": "PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/"},
            {"from": "H2-5", "to": "H2-1", "quantity": "exterior finish of MC-1 (high-emittance, temperature-capable) is design-driving", "value": "eps >= 0.9 class finish vs bare metal", "units": "-", "status": "PRELIMINARY"},
            {"from": "H2-2 (docs/hardware/h2/h2_2_cathode_integration/)", "to": "H2-5", "quantity": "C-1 steady heat into H-1 (keeper + radiation) and mount conductance", "value": [9.0, 101.0], "units": "W", "status": "PENDING"},
            {"from": "H2-5", "to": "H2-2", "quantity": "cathode-body temperature envelope at its mount (for keeper/heater insulation selection)", "value": "CB rows in solve", "units": "K", "status": "PRELIMINARY"},
            {"from": "H2-4 (docs/hardware/h2/h2_4_ppu_bus/)", "to": "H2-5", "quantity": "hall_discharge allocation and PPU efficiency (Q_PPU)", "value": "P_d <= 1350 bound used", "units": "W, -", "status": "PENDING"},
            {"from": "H2-5", "to": "H2-4", "quantity": "thermal_control heater load per mode (incl. PPU, Xe, plenum survival heaters)", "value": None, "units": "W", "status": "TBD - requires the spacecraft cold case and the Xe ledger"},
            {"from": "H2-3 (docs/hardware/h2/h2_3_gas_path_plenum/)", "to": "H2-5", "quantity": "compressor input power, plenum/valve limits, feed-line isolator conductance", "value": None, "units": "W, degC, W/K", "status": "PENDING"},
            {"from": "H2-5", "to": "H2-3", "quantity": "anode-to-feed-line conductive heat (T_feed at HALL_INLET_Z0 is a measured result)", "value": "inside G_anode_mount [0.1, 1.0]", "units": "W/K", "status": "PRELIMINARY"},
            {"from": "H2-5", "to": "H2-6 (docs/hardware/h2/h2_6_diagnostics_fixture/)", "quantity": "thermocouple positions at AN, WI/WO exit rings, CI/CO hot spots, PI/PO poles, BP, CB tube; facility sink and stand temperatures", "value": "node list", "units": "-", "status": "PRELIMINARY"},
            {"from": "H2-6", "to": "H2-5", "quantity": "facility radiative sink and stand interface temperatures", "value": {"T_env": [246.15, 293.15], "T_mount": [293.15, 315.15]}, "units": "K", "status": "PENDING"},
            {"from": "H2-5", "to": "H2-7 (docs/hardware/h2/h2_7_mechanical_bom/)", "quantity": "body envelope D_body, L_body and mount heat into the stand/spacecraft", "value": "H25-18/19; mount_heat_W", "units": "m, W", "status": "PENDING"},
            {"from": "fo_preionizer_module_icd (docs/interfaces/preionizer_module/, PMI-05)", "to": "H2-5", "quantity": "occupant active heat into H-1 at IP-DN (common interface; 0 for PIM-0)", "value": None, "units": "W", "status": "PENDING"},
            {"from": "H2-5", "to": "fo_preionizer_module_icd (PMI-05)", "quantity": "H-1 sensitivity to heat at IP-DN", "value": "dT_dQ_PIM_K_per_W_nominal per node", "units": "K/W", "status": "PRELIMINARY"},
            {"from": "H2-5", "to": "fo_subsystem_maturity_matrix (docs/budgets/subsystem_maturity/)", "quantity": "m16_rows", "value": "see m16_rows", "units": "-", "status": "PRELIMINARY"},
            {"from": "H2-5", "to": "H-1 / HW-MC-08, HW-MC-14, HW-MC-16", "quantity": "coil hot-spot locations, max coil current/temperature inputs, thermal-cycle profile", "value": "CI/CO envelope", "units": "K", "status": "PRELIMINARY"},
        ],
        "thermal_life_link": [
            {"temperature": "AN", "feeds": "AOL-M01 anode/gas-distributor oxidation (anode temperature TBD there)", "note": "no anode limit exists; material HWQ-08"},
            {"temperature": "WI/WO", "feeds": "AOL-M02 / AOL-M03 wall sputtering and oxidation at wall temperature; BN oxidizing 900 degC guide (lane 15)"},
            {"temperature": "CE (not solved)", "feeds": "AOL-M04 emitter poisoning (LaB6 >= 1570 degC for pO2 <= 1e-4 Torr); thermal_life cathode node (Richardson-Dushman)"},
            {"temperature": "CB", "feeds": "AOL-M05 keeper/orifice erosion context; cathode_assembly_temperature_limit (TBD in limits_v1.json)"},
            {"temperature": "PI/PO/BP", "feeds": "AOL-M06 magnetic-circuit oxidation/temperature; HW-MC-13 grade"},
            {"temperature": "CI/CO", "feeds": "AOL-M07 insulation thermal ageing (IEC 60085 class); thermal_life hall_magnet: this network supplies external_heat_W and rejection_paths structure only once H2-1 defines the coil (not now)"},
            {"temperature": "exterior finish", "feeds": "AOL-M08 coatings/emissivity change; AOL-M09 ram AO on the exterior"},
            {"temperature": "all", "feeds": "thermal_life.py is NOT called: its discharge wall-heat inputs must come from an admitted Hall map or measured hardware (G11); none exists"},
        ],
        "h3_procurement_inputs": [
            {"item": "BN channel wall stock (grade with oxidizing-atmosphere rating; e.g. HeBoSint or Combat M26 class)", "spec_needed": "grade, k(T) both directions, oxidizing max use temperature, SiO2/binder content, lot certificate", "reference_data": "EXT-HENZE2021 (reference only); Combat M26 datasheet TBD (bot challenge, limits_v1 bn_combat_m26)", "long_lead": True},
            {"item": "coil magnet wire + electrical insulation system (EIS)", "spec_needed": "thermal class (>= the class the margins table requires; possibly > 250 degC ceramic), thermal-endurance basis >= 15,000 h at hot spot (HW-MC-07), potting compound k", "reference_data": "IEC 60085 classes (limits_v1)", "long_lead": True},
            {"item": "soft-magnetic pole/core stock (HW-MC-13)", "spec_needed": "grade, B-H and saturation vs temperature to the pole maximum, k(T) or resistivity(T), oxidation behaviour", "reference_data": "EXT-NICOFE-A848 (reference only)", "long_lead": True},
            {"item": "high-emittance temperature-capable exterior coating for MC-1", "spec_needed": "hemispherical emittance at 150-400 degC, alpha_s, adhesion/outgassing, AO durability (AOL-M08/M09)", "reference_data": "EXT-HENNINGER1984 (room-temperature data only)", "long_lead": False},
            {"item": "ceramic thermal/electrical isolators for anode and cathode mounts", "spec_needed": "k, dielectric strength at temperature, size", "reference_data": "TBD", "long_lead": False},
            {"item": "thermocouples + feedthroughs (W4)", "spec_needed": "types and ranges per node envelope (wall to ~900 degC)", "reference_data": "instrumentation_definition_v1", "long_lead": False},
        ],
        "h4_test_inputs": [
            {"stage": "S1a", "measure": "coil hot-spot/average offset in vacuum on the bench (HW-MC-14); contact conductances of pole/coil/shell joints (bench heater test); emittance of as-built surfaces (AOL-M08 pre)", "closes": ["H25-08", "H25-30", "H25-27", "H25-29"]},
            {"stage": "S1", "measure": "thermal time constants T-SETTLE; facility sink and stand temperatures; dormant thruster temperature", "closes": ["H25-34", "H25-35", "HW-H1-07 T_SETTLE"]},
            {"stage": "S1b", "measure": "remount reproducibility of AN/WI/WO/BP temperatures at fixed setpoints", "closes": ["installation thermal term c5 (HW-SVC-03)"]},
            {"stage": "Phase 1", "measure": "AN, WI/WO, PI/PO, CI/CO, CB temperatures vs P_d, V_d, mdot_atm, x_O2 on N2 and air; inversion of the anode and wall heat fractions by a correlated model (EXT-MYERS2016 / EXT-MAZOUFFRE2005 method)", "closes": ["H25-04", "H25-05", "H25-06"]},
            {"stage": "Phase 1 (rf_hall/ecr_hall arms)", "measure": "anode/BP temperature difference between arms at the same setpoint (HW-PIM-09) and occupant heat at IP-DN", "closes": ["H25-11"]},
        ],
        "milestone_statement": {
            "A": "supports conditional selection: states the thermal conditions under which the A5 baseline is buildable (high-emittance exterior finish and a coil EIS class chosen from the margins table, or a permanent-magnet MC-1), with no architecture ranking",
            "B": "needs measured anode/wall heat fractions on N2/air (Phase 1) and the H2-1 geometry; not an admitted Hall closure",
            "C": "needs the integrated flight thermal design (spacecraft ICD, radiators, heaters, transients/eclipse cycling)",
        },
        "owner_questions": [
            {"id": "H25-Q1", "question": "Exterior finish of MC-1: accept a high-emittance temperature-capable coating as a baseline requirement (bare metal is design-driving in every case)?"},
            {"id": "H25-Q2", "question": "Coil EIS: which IEC 60085 class (or ceramic > 250 degC) is the design basis (HWQ-20), given the coil envelope, or a permanent-magnet MC-1 (HWQ-19)?"},
            {"id": "H25-Q3", "question": "Spacecraft thermal ICD: mounting-interface temperature and allowable heat into the spacecraft (G_mount, T_mount)."},
            {"id": "H25-Q4", "question": "PROPOSED: thermal margins (e.g. K below each limit) for PDR are not in the RFP; owner to set them."},
        ],
        "compliance": {
            "no_hall_performance_source": "discharge heat = parametric fraction x P_d allocation; fractions from published xenon analog hardware only",
            "no_winner": "no architecture ranked; PIM slot via PMI-05 only",
            "nuisance": "no P5 calibration-nuisance item is a design variable",
            "upstream": "Hall-closure uncertainty does not enter the gas path: GP/COMP are demand nodes with their own inputs",
            "pure": "standard library + numpy; not wired into archengine; no frozen data, golden, prereg or campaign file touched",
            "no_contact": "published sources only; no supplier/lab contact",
        },
    }
    return doc


# ----------------------------------------------------------------------------------------------- markdown
def fmt(v):
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "; ".join(f"{k}: {fmt(x)}" for k, x in v.items())
    return "—" if v is None else str(v)


def render_md(doc):
    L = []
    a = L.append
    a("# H2-5 Thermal network (preliminary lumped-node model)\n")
    a(f"Lane `{doc['follow_on']}` (trigger `{doc['trigger']}`, owner addendum A7). Status **{doc['status']}**. "
      f"Generated by `{doc['generated_by']}` from base commit `{doc['base_commit']}`; machine-readable data in "
      "`h2_5_thermal_network_v1.json`. This is an H2 hardware design / preliminary-sizing lane, **not** an architecture-selection lane.\n")
    a("## What this is not\n")
    for s in doc["what_this_is_not"]:
        a(f"- {s}")
    a("\n## Design findings (computed; P_d = whole 1.35 kW bus allocation, bounding)\n")
    for f in doc["design_findings"]:
        a(f"- {f}")
    a(f"\nHard-incompatibility check: **{doc['hard_incompatibility_check']['result']}** (details below).\n")
    a("\n## Pinned decisions and inputs\n")
    a("| key | path | sha256 |\n|---|---|---|")
    for k, v in doc["pinned_inputs"].items():
        a(f"| {k} | `{v['path']}` | `{v['sha256']}` |")
    a("\nMutable files are referenced at the base commit, not pinned: " + "; ".join(f"{k}: {v}" for k, v in doc["referenced_at_base_commit"].items()) + ".\n")
    a("## Provenance of existing thermal code\n")
    for k, v in doc["provenance_checks"].items():
        a(f"- `{k}`: {v}")
    a("\n## Nodes\n")
    a("| id | node | CI | scope | solved |\n|---|---|---|---|---|")
    for n in doc["node_list"]:
        a(f"| {n['id']} | {n['name']} | {n['ci']} | {n['scope']} | {'yes' if n['solved'] else 'no: ' + n['reason']} |")
    a("\n## Links\n")
    for k, v in doc["links"].items():
        if isinstance(v, list):
            a(f"- **{k}**: " + "; ".join(v))
        else:
            a(f"- **{k}**: {v}")
    a("\n## Design-parameter table\n")
    a("| id | name | value | units | basis | evidence | status | scope | source |\n|---|---|---|---|---|---|---|---|---|")
    for r in doc["design_parameters"]:
        a(f"| {r['id']} | {r['name']} | {fmt(r['value'])} | {r['units']} | {r['basis']} | {r['evidence_class']} | {r['status']} | {r['scope']} | {r['source']} |")
    a("\n## Material properties (source-derived)\n")
    a("| material | T (K) | k (W/m K) | source | evidence | note |\n|---|---|---|---|---|---|")
    for m in doc["material_properties"]:
        a(f"| {m['material']} | {fmt(m['T_K'])} | {fmt(m['k_W_mK'])} | {m['source']} | {m['evidence_class']} | {m['note']} |")
    a("\n## Temperature limits\n")
    a("| node | quantity | value (degC) | live | source |\n|---|---|---|---|---|")
    for l in doc["limits"]:
        a(f"| {l['node']} | {l['quantity']} | {fmt(l['value_C'])} | {l['live']} | {l['source']} |")
    s = doc["summary_at_P_d_max_degC"]
    a(f"\n## Node temperature envelopes at P_d = {s['P_d_W']:g} W (degC, [min, max])\n")
    a("| case | finish | " + " | ".join(NODES) + " |\n|---|---|" + "---|" * len(NODES))
    for r in s["rows"]:
        a(f"| {r['case']} | {r['finish']} | " + " | ".join(f"{r[n][0]:g} .. {r[n][1]:g}" for n in NODES) + " |")
    a("\nMethod: " + doc["solve"]["method"] + ".\n")
    a("## Latin-hypercube sample statistics at P_d max (degC; box coverage, not probabilities)\n")
    a("| case | finish | " + " | ".join(f"{n} med / p95 / max" for n in NODES) + " |\n|---|---|" + "---|" * len(NODES))
    for case, fins in doc["solve"]["cases"].items():
        for fin, d in fins.items():
            st = d["lhs_at_P_d_max"]["nodes"]
            a(f"| {case} | {fin} | " + " | ".join(f"{st[n]['sample_median_C']:g} / {st[n]['sample_p95_C']:g} / {st[n]['sample_max_C']:g}" for n in NODES) + " |")
    a("\n## Margins to live limits at P_d max (K below the limit: worst corner / nominal / best corner; verdict on the corner envelope)\n")
    a("| case | finish | node | limit | T corner range (degC) | T nominal | margin worst | margin nominal | margin best | LHS fraction above | verdict | dominant inputs |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in doc["margins_at_P_d_max"]:
        a(f"| {r['case']} | {r['finish']} | {r['node']} | {r['limit']} | {r['T_min_C']:g} .. {r['T_max_C']:g} | {r['T_nominal_C']:g} | {r['margin_worst_K']:g} | {r['margin_nominal_K']:g} | {r['margin_best_K']:g} | {r['lhs_fraction_above_limit']:g} | {r['verdict']} | {', '.join(r['dominant_inputs'])} |")
    hc = doc["hard_incompatibility_check"]
    a("\n## Hard-incompatibility check\n")
    a(f"Rule: {hc['rule']}.\n\nChecked: " + "; ".join(hc["checked"]) + f".\n\n**Result: {hc['result']}**. Envelope evidence class: {hc['evidence_class_of_envelope']}.\n")
    for f in hc["findings"]:
        a(f"- {f['case']} / {f['node']}: {f['evidence']}")
    a("\n## Envelope versus discharge power (corner T_max, degC, per P_d grid point)\n")
    grid = doc["solve"]["P_d_grid_W"]
    a("| case | finish | node | " + " | ".join(f"P_d {g:g} W" for g in grid) + " |\n|---|---|---|" + "---|" * len(grid))
    for case, fins in doc["solve"]["cases"].items():
        for fin, d in fins.items():
            for n in ("AN", "WI", "CI", "CO", "BP"):
                a(f"| {case} | {fin} | {n} | " + " | ".join(f"{d['by_P_d_W'][str(g)][n]['T_max_K'] - T0C:.1f}" for g in grid) + " |")
    a("\n## Pre-ionizer slot influence (PMI-05, identical for every occupant)\n")
    a("dT/dQ_PIM at the nominal point (K per W entering BP at IP-DN):\n")
    Pd = str(doc["solve"]["P_d_grid_W"][-1])
    a("| case | finish | " + " | ".join(NODES) + " |\n|---|---|" + "---|" * len(NODES))
    for case, fins in doc["solve"]["cases"].items():
        for fin, d in fins.items():
            e = d["by_P_d_W"][Pd]
            a(f"| {case} | {fin} | " + " | ".join(f"{e[n]['dT_dQ_PIM_K_per_W_nominal']:g}" for n in NODES) + " |")
    a("\n## Heat into the mounting interface at P_d max (W)\n")
    a("| case / finish | corner min | nominal | corner max | LHS median | LHS max |\n|---|---|---|---|---|---|")
    for k, v in doc["mount_heat_W"].items():
        a(f"| {k} | {v['corner_min_W']:g} | {v['nominal_W']:g} | {v['corner_max_W']:g} | {v['lhs']['sample_median']:g} | {v['lhs']['sample_max']:g} |")
    a("\n## Spacecraft-side demand nodes\n")
    for k, v in doc["spacecraft_side_demands"].items():
        a(f"- **{k}**: " + "; ".join(f"{kk}: {fmt(vv) if not isinstance(vv, list) else json.dumps(vv)}" for kk, vv in v.items()))
    a("\n## Interface demands\n")
    a("| from | to | quantity | value | units | status |\n|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['from']} | {d['to']} | {d['quantity']} | {fmt(d['value'])} | {d['units']} | {d['status']} |")
    a("\n## Architecture-changing blockers touched (A7)\n")
    for b in doc["architecture_changing_blockers_touched"]:
        a(f"- Blocker {b['blocker']}: {b['how']}")
    a("\n## M16 rows (proposed)\n")
    a("| subsystem | matured | proposed state | blocking item | rollup |\n|---|---|---|---|---|")
    for m in doc["m16_rows"]:
        a(f"| {m['subsystem']} | {m['matured_by_this_lane']} | {m['proposed_state']} | {fmt(m['blocking_item'])} | {fmt(m['rollup_category'])} |")
    a("\n## Thermal-life link\n")
    for t in doc["thermal_life_link"]:
        a(f"- {t['temperature']}: {t['feeds']}" + (f" ({t['note']})" if t.get("note") else ""))
    a("\n## H3 procurement inputs\n")
    for p in doc["h3_procurement_inputs"]:
        a(f"- {p['item']} (long lead: {p['long_lead']}): {p['spec_needed']}. Reference: {p['reference_data']}")
    a("\n## H4 test inputs\n")
    for t in doc["h4_test_inputs"]:
        a(f"- **{t['stage']}**: {t['measure']} (closes {', '.join(t['closes'])})")
    a("\n## Milestone statement\n")
    for k, v in doc["milestone_statement"].items():
        a(f"- **{k}**: {v}")
    a("\n## Owner questions\n")
    for q in doc["owner_questions"]:
        a(f"- {q['id']}: {q['question']}")
    a("\n## External sources accessed (2026-09-27)\n")
    for k, v in doc["external_sources"].items():
        a(f"- {k}: {v['citation']}. {v['url']} ({v['access']}; sha256 {v['sha256'] or v.get('sha256_note')})")
    a("")
    return "\n".join(L)


def main(argv=None):
    doc = build()
    txt = json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(txt)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(render_md(doc))
    print(f"wrote {OUT_JSON} and {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
