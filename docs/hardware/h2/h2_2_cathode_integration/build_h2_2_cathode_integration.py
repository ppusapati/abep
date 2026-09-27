#!/usr/bin/env python3
"""H2-2 cathode integration for C-1 (follow-on fo_h2_2_cathode_integration; trigger T_H2_2_CATHODE_INTEGRATION;
owner addendum A7, H2 hardware wave).

What it is: an H2 hardware-design / preliminary-sizing lane for C-1, the shielded Xe-fed LaB6 hollow cathode of the A5
Proposal Reference Architecture. It covers mechanical location, plume/oxygen shielding, magnetic and thermal isolation,
keeper/heater/ignition supplies, the cathode Xe branch, the electrical return path and the flow-measurement capability
needed to measure 0.10-0.15 mg/s Xe. Every design item carries its basis, source, evidence class, status and whether it
is FLIGHT_REPRESENTATIVE, H1_TEST_ARTICLE_ONLY or GROUND_FACILITY_ONLY.

What it is not: an architecture-selection lane (A7 h2_scope), a performance prediction, a Hall-closure result, a cathode
selection or a procurement. No thrust, efficiency, discharge current or plasma state is predicted; no screening candidate
or unadmitted Hall closure, no abep_sim/plasma_devices.py value and no withdrawn v1.2-v1.6 number is used. hall_only /
rf_hall / ecr_hall share the same C-1 (INV-C1); no winner is declared.

Inputs:
  * immutable owner decisions + G0 record, pinned by sha256 (the build refuses on a mismatch);
  * verified base-commit deliverables, read for a few values (V_d set and I_d bound of the hardware definition,
    N_starts scenarios of the Xe ledger); their sha256 at read time is recorded as provenance and the values are
    re-read and compared on every build;
  * published open sources read in full by this lane (URL + sha256 of the file fetched on 2026-09-27) and values
    transcribed from the repository's evidence deliverables with path + locator.
Mutable governance files (lane/trigger registries, trigger ledgers, runtime_state.json) are never read or pinned.

Deterministic, standard library only, no Julia, runs in well under a second.

Usage:
  python docs/hardware/h2/h2_2_cathode_integration/build_h2_2_cathode_integration.py            # write JSON + MD
  python docs/hardware/h2/h2_2_cathode_integration/build_h2_2_cathode_integration.py --check    # byte-for-byte check
  python docs/hardware/h2/h2_2_cathode_integration/build_h2_2_cathode_integration.py --resolve  # report PENDING lanes
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LANE_DIR_REL = "docs/hardware/h2/h2_2_cathode_integration"
SCRIPT_REL = f"{LANE_DIR_REL}/build_h2_2_cathode_integration.py"
JSON_NAME = "h2_2_cathode_integration_v1.json"
MD_NAME = "H2_2_CATHODE_INTEGRATION.md"
TEST_REL = "tests/test_h2_2_cathode_integration.py"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")

# ----------------------------------------------------------------------------------------------------------------------
# Pins
# ----------------------------------------------------------------------------------------------------------------------
OD_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json"
A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A7_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"
G0_REL = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
DECISION_PINS = {
    OD_REL: "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac",
    A5_REL: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6_REL: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    A7_REL: "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    G0_REL: "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
}

HWDEF_REL = "docs/experiments/hardware/hardware_requirements_v1.json"
XEL_REL = "docs/budgets/xe_ledger/xe_ledger_v1.json"
CATHINT_REL = "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json"
DOSSIER_REL = "docs/evidence/cathode/cathode_evidence_v1.json"
AOL_REL = "docs/experiments/lifetime_ao/ao_lifetime_register_v5.json"
W4_REL = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
CONTROLS_REL = "schemas/controls/dual_feed_state_machine_v1.json"
# Verified merged deliverables read at the base commit. sha256 recorded as provenance (values re-read every build).
PROVENANCE_READS = {
    HWDEF_REL: "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
    XEL_REL: "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad",
    CATHINT_REL: "df020bfe3ef87b0fc6f49c56db7e38dc585c4640b5c89dd167d1f18e928dbd6f",
    DOSSIER_REL: "050060204e443d5583c307becadaab55a9f213d406ff4454be856bca21249110",
    AOL_REL: "fea8aa05bd561d5ea559b934803d472f1fb1ed1013bfa925a5afb6c68a33e637",
    W4_REL: "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
}
# Never pinned, never read (mutable governance, CLAUDE.md operating model).
NEVER_PINNED = ("lane_registry_v1.json", "trigger_registry_v1.json", "fired_triggers.jsonl",
                "trigger_ledger_v2.jsonl", "runtime_state.json")

# Parallel lanes (not in the base). Referenced by path only; resolved lazily by --resolve, never at import/test time.
H2_1 = "docs/hardware/h2/h2_1_hall_chamber_magnet/"
H2_3 = "docs/hardware/h2/h2_3_gas_path_plenum/"
H2_4 = "docs/hardware/h2/h2_4_ppu_bus/"
H2_5 = "docs/hardware/h2/h2_5_thermal_network/"
H2_6 = "docs/hardware/h2/h2_6_diagnostics_fixture/"
H2_7 = "docs/hardware/h2/h2_7_mechanical_bom/"
PMI = "docs/interfaces/preionizer_module/"
M16 = "docs/budgets/subsystem_maturity/"
P1PF = "docs/experiments/phase1_prereg_framework/"
XEL = "docs/budgets/xe_ledger/"
PARALLEL_PATHS = (H2_1, H2_3, H2_4, H2_5, H2_6, H2_7, PMI, M16)

# ----------------------------------------------------------------------------------------------------------------------
# Vocabularies (the test enforces them)
# ----------------------------------------------------------------------------------------------------------------------
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "none")
ARTICLE_CLASSES = ("FLIGHT_REPRESENTATIVE", "H1_TEST_ARTICLE_ONLY", "GROUND_FACILITY_ONLY")
M16_STATES = ("READY", "RUNNING", "BLOCKED", "VERIFIED")
ROLLUP = ("architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
          "proposal-only documentation gap")

# ----------------------------------------------------------------------------------------------------------------------
# Sources
# ----------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "GK2008": {
        "citation": "D. M. Goebel and I. Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL "
                    "Space Science and Technology Series, JPL / Wiley, 2008",
        "url": "https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf",
        "sha256": "a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e",
        "access": "open full text, read by this lane 2026-09-27 (same file as lane 19 records)",
        "evidence_level": "4-5 (textbook relations; summaries of the authors' measurements)",
    },
    "IEPC2015_43": {
        "citation": "D. M. Goebel and J. E. Polk, 'Lanthanum Hexaboride Hollow Cathode for the Asteroid Redirect "
                    "Robotic Mission 12.5 kW Hall Thruster', IEPC-2015-43/ISTS-2015-b-43, Kobe, 2015",
        "url": "https://electricrocket.org/IEPC/IEPC-2015-43_ISTS-2015-b-43.pdf",
        "sha256": "6f5873d4ca95496714d427b0bdb568f57043d601085d2bd8f8d5b718829e1501",
        "access": "open full text, read by this lane 2026-09-27; page = printed page number",
        "evidence_level": "3 (primary report on other hardware: JPL 1.5-cm LaB6, 7.5-40 A class)",
    },
    "IEPC2017_365": {
        "citation": "D. Pedrini, F. Cannelli, C. Tellini, C. Ducci, T. Misuri, F. Paganucci and M. Andrenucci, "
                    "'Hollow Cathodes for Low-Power Hall Effect Thrusters', IEPC-2017-365, Atlanta, 2017",
        "url": "https://electricrocket.org/IEPC/IEPC_2017_365.pdf",
        "sha256": "d98374b080642877ed0b2aa2428173b104fa4ff4a633c6dc523203c5b6f81cf6",
        "access": "open full text, read by this lane 2026-09-27; values from text, figures not digitized",
        "evidence_level": "3 (primary report on other hardware: SITAEL HC1 0.3-1 A and HC3 1-3 A LaB6)",
    },
    "HOFER2008": {
        "citation": "R. R. Hofer et al., 'Effects of Internally Mounted Cathodes on Hall Thruster Plume "
                    "Properties', IEEE Trans. Plasma Sci. 36(5), Oct. 2008, starting p. 2005 (last page to verify), "
                    "doi:10.1109/TPS.2008.2000962 (DOI printed on the first page of the file)",
        "url": "http://richard.hofer.com/pdf/hofer_ieeetps_2008.pdf",
        "sha256": "43661dd3f457b6c6f442aad6d9b0b35130ed1d459ff293fb2f1880e8bb82cb04",
        "access": "author-hosted full text at an open URL, read 2026-09-27; nothing bypassed; co-author list and "
                  "page range to verify against the journal record",
        "evidence_level": "3 (primary measurements on the 8-kW BHT-8000 on Xe: another device and power class)",
    },
    "BRONKHORST_ELFLOW_SELECT": {
        "citation": "Bronkhorst High-Tech, 'EL-FLOW Select: Digital Thermal Mass Flow Meters and Controllers for "
                    "Gases', product catalog (8 pages)",
        "url": "https://products.bronkhorst.com/media/cp3lfvo1/el-flow-select_en.pdf",
        "sha256": "69e5a7654f03758b6b9939366a5113a9669c083fd84f0d18f6b3009d5428f296",
        "access": "public manufacturer catalog downloaded 2026-09-27; REFERENCE ONLY for the specification level "
                  "(no supplier contact, no selection, no quotation)",
        "evidence_level": "6 (manufacturer specification of a product class, not a calibration of any unit)",
    },
    "LANE19": {
        "citation": "CATHINT lane 19 data file (transcriptions of IEPC-2017-276, IEPC-2017-377, G&K and SITAEL "
                    "values with locators)",
        "path": CATHINT_REL,
        "access": "repository deliverable (read only)",
    },
    "DOSSIER": {
        "citation": "Cathode evidence dossier v1 (Joussot 2017, Zschaetzsch 2022 and G&K Sec. 6.8.5 transcriptions)",
        "path": DOSSIER_REL,
        "access": "repository deliverable (read only)",
    },
    "AOL5": {"citation": "AO/lifetime register v5", "path": AOL_REL, "access": "repository deliverable (read only)"},
    "W4": {"citation": "W4 instrumentation definition v1 (records REF-SNYDER2017, Snyder et al., J. Propul. Power "
                       "33(3) 2017, doi:10.2514/1.B35644, read by W4)", "path": W4_REL,
           "access": "repository deliverable (read only)"},
    "HWDEF": {"citation": "W3 common-hardware definition (H-1, MC-1, C-1, FS-C, PS-C, SVC-1, PIM-*)",
              "path": HWDEF_REL, "access": "repository deliverable (read only; DRAFT_PENDING_OWNER)"},
    "XEL": {"citation": "Parametric Xe ledger v1 (verified, T_A5_XE_LEDGER)", "path": XEL_REL,
            "access": "repository deliverable (read only)"},
    "CONTROLS": {"citation": "Dual-feed state machine v1 (state names)", "path": CONTROLS_REL,
                 "access": "repository deliverable (read only)"},
    "A5": {"citation": "Owner addendum A5", "path": A5_REL, "access": "immutable owner decision (pinned)"},
    "A7": {"citation": "Owner addendum A7", "path": A7_REL, "access": "immutable owner decision (pinned)"},
    "CLAUDE_MD": {"citation": "CLAUDE.md 'Superseded / withdrawn' (true ECHT geometry: 86 mm long, 10 mm wide, "
                              "100 mm OD)", "path": "CLAUDE.md", "access": "repository instructions (read only)"},
}

# ----------------------------------------------------------------------------------------------------------------------
# Constants used in derivations (each sourced)
# ----------------------------------------------------------------------------------------------------------------------
XE_MG_S_PER_SCCM = 0.0983009      # G&K App. B Eq. (B-5) p. 464, via LANE19 parameters.xe_mg_s_per_sccm (273.15 K, 1 atm)
R_UNIVERSAL = 8.314462618          # J/(mol K), CODATA exact-derived (k_B * N_A)
M_XE_KG_PER_MOL = 0.131293         # G&K App. B (M_a = 131.293), via LANE19 locator
KELVIN = 273.15
SECONDS_PER_HOUR = 3600.0


class InputMissing(ValueError):
    """Raised when an explicit input is absent (CLAUDE.md rule 3: no silent fallbacks)."""


def _req(name: str, value, positive: bool = True):
    if value is None:
        raise InputMissing(f"{name} is required (no default)")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputMissing(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise InputMissing(f"{name} must be finite")
    if positive and value <= 0:
        raise InputMissing(f"{name} must be > 0, got {value!r}")
    return float(value)


# ----------------------------------------------------------------------------------------------------------------------
# Pure relations (unit-tested)
# ----------------------------------------------------------------------------------------------------------------------
def mg_s_to_sccm(mdot_mg_s):
    return _req("mdot_mg_s", mdot_mg_s) / XE_MG_S_PER_SCCM


def xe_mass_kg(mdot_mg_s, hours):
    return _req("mdot_mg_s", mdot_mg_s) * 1e-6 * _req("hours", hours) * SECONDS_PER_HOUR


def mfc_relative_u(q, fs, rd_frac, fs_frac):
    """Relative flow uncertainty of a thermal MFC with spec '+/-(rd_frac of reading + fs_frac of full scale)'.

    Explicit inputs only; q must lie inside (0, fs]. Returns rd_frac + fs_frac * fs / q (linear sum, as the
    specification form states it; treated as 1 sigma following the W4 convention, coverage to verify).
    """
    q = _req("q", q)
    fs = _req("fs", fs)
    rd = _req("rd_frac", rd_frac, positive=False)
    fsf = _req("fs_frac", fs_frac, positive=False)
    if rd < 0 or fsf < 0:
        raise InputMissing("specification fractions must be >= 0")
    if rd == 0 and fsf == 0:
        raise InputMissing("at least one specification term must be non-zero")
    if q > fs:
        raise InputMissing(f"setpoint {q} exceeds full scale {fs}")
    return rd + fsf * fs / q


def rss(*terms):
    if not terms:
        raise InputMissing("rss needs at least one term")
    return math.sqrt(sum(_req("term", t, positive=False) ** 2 for t in terms))


def gravimetric_min_mass_g(u_balance_mg, u_target_rel):
    """Collected mass that keeps the two-weighing balance term at u_target (u_m = sqrt(2) u_bal)."""
    return math.sqrt(2.0) * _req("u_balance_mg", u_balance_mg) * 1e-3 / _req("u_target_rel", u_target_rel)


def rate_of_rise_Pa_s(mdot_mg_s, volume_L, temperature_K):
    """Constant-volume calibrator: dp/dt = mdot * R_s * T / V (ideal gas)."""
    r_s = R_UNIVERSAL / M_XE_KG_PER_MOL
    return _req("mdot_mg_s", mdot_mg_s) * 1e-6 * r_s * _req("temperature_K", temperature_K) / (
        _req("volume_L", volume_L) * 1e-3)


def discharge_current_upper_bound_A(p_W, v_d_V):
    """I_d <= P / V_d (all of P into the discharge): a bound from power, never a prediction."""
    return _req("p_W", p_W) / _req("v_d_V", v_d_V)


# ----------------------------------------------------------------------------------------------------------------------
# Input reading
# ----------------------------------------------------------------------------------------------------------------------
def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_decision_pins() -> dict:
    out = {}
    for rel, want in DECISION_PINS.items():
        got = _sha(rel)
        if got != want:
            raise SystemExit(f"PIN MISMATCH {rel}: {got} != {want}")
        out[rel] = want
    return out


def _load(rel: str):
    return json.loads((REPO / rel).read_text())


def read_inputs() -> dict:
    a5 = _load(A5_REL)
    xa = a5["xe_mass_allocation"]
    hw = _load(HWDEF_REL)
    envr = {r["id"]: r for r in hw["requirements"]}
    vd_set = envr["HW-ENV-01"]["values"]["V_d_proposed_set_V"]["value"]
    p_max = hw["rfp_basis"]["power_max_W"]["value"]
    xel = _load(XEL_REL)
    sc = {s["id"]: s for s in xel["scenarios"]}
    return {
        "mdot_design_mg_s": xa["cathode_flow_design_target_mg_s"],
        "mdot_upper_test_mg_s": xa["cathode_flow_experimental_upper_test_point_mg_s"],
        "a5_ref_kg": xa["reference_arithmetic_15000h"],
        "vd_set_V": list(vd_set),
        "p_max_W": p_max,
        "n_starts_sc1": sc["SC-1"]["parameters"]["N_starts"]["value"],
        "n_starts_sc2": sc["SC-2"]["parameters"]["N_starts"]["value"],
    }


# ----------------------------------------------------------------------------------------------------------------------
# Derived numbers
# ----------------------------------------------------------------------------------------------------------------------
def r(x, n=6):
    return float(f"{x:.{n}g}")


# Flow-measurement specification classes (value, source). Reference only; no instrument is selected.
SPEC_CLASSES = [
    {"id": "SPEC-FS1", "rd_frac": 0.0, "fs_frac": 0.01,
     "source": "W4 REF-SNYDER2017 as recorded in instrumentation_definition_v1.json references ('manufacturer "
               "accuracy typically 1% full scale'); W4 treats it as 1 sigma (coverage to verify)",
     "evidence_class": "measured"},
    {"id": "SPEC-CAT-STD", "rd_frac": 0.005, "fs_frac": 0.001,
     "source": "BRONKHORST_ELFLOW_SELECT p. 2 'Accuracy (incl. linearity) standard: +/-0,5% Rd plus +/-0,1%FS' "
               "(based on actual calibration)", "evidence_class": "assumed"},
    {"id": "SPEC-CAT-LOW", "rd_frac": 0.008, "fs_frac": 0.002,
     "source": "BRONKHORST_ELFLOW_SELECT p. 2 '+/-0,8% Rd plus +/-0,2% FS for F-110C-005/F-200CV-005' (lowest "
               "ranges)", "evidence_class": "assumed"},
    {"id": "SPEC-CAT-002", "rd_frac": 0.0, "fs_frac": 0.02,
     "source": "BRONKHORST_ELFLOW_SELECT p. 2 '+/-2% FS for F-110C-002/F-200CV-002'", "evidence_class": "assumed"},
]
# Candidate full scales in mg/s Xe (a design axis of this lane, not a product range: catalog ranges are air-based and
# the Xe range of any unit is TBD - requires the manufacturer's Xe calibration).
FS_OPTIONS_MG_S = [0.2, 0.3, 0.5, 1.0, 2.0]
# Zero-shift terms (% FS) recorded by W4 from REF-SNYDER2017.
ORIENTATION_ZERO_FS = 0.004        # 'can alter the zero point ... by up to 0.4% of full scale'
TEMP_ZERO_FS_PER_C = 0.0012        # 'approximately 0.12% per degree'
DELTA_T_C_OPTIONS = [1.0, 5.0]     # parametric axis (assumed), not a facility value


def derive(inp: dict) -> dict:
    q_d = inp["mdot_design_mg_s"]
    q_u = inp["mdot_upper_test_mg_s"]
    flows = {"design_target": q_d, "upper_test_point": q_u}
    d: dict = {}

    d["flow_units"] = {
        k: {"mdot_mg_s": v, "sccm_Xe": r(mg_s_to_sccm(v)),
            "source": "mdot / 0.0983009 mg/s per sccm (G&K App. B Eq. B-5 p. 464, 273.15 K / 1 atm; LANE19 "
                      "parameters.xe_mg_s_per_sccm)", "evidence_class": "model-derived"}
        for k, v in flows.items()}

    mass = {}
    for k, v in flows.items():
        for h in (15000.0, 18000.0):
            mass[f"{k}_{int(h)}h_kg"] = r(xe_mass_kg(v, h))
    d["cathode_xe_mass"] = {
        "values": mass,
        "a5_reference_arithmetic_15000h": inp["a5_ref_kg"],
        "consistent_with_a5": (abs(mass["design_target_15000h_kg"] - inp["a5_ref_kg"]["0.10_mg_s_kg"]) < 1e-9
                               and abs(mass["upper_test_point_15000h_kg"] - inp["a5_ref_kg"]["0.15_mg_s_kg"]) < 1e-9),
        "note": "18,000 h is the A5 internal design-life target (sensitivity only; A5 books 15,000 h)",
        "evidence_class": "model-derived",
    }

    # Flow-measurement uncertainty grid.
    grid = []
    for spec in SPEC_CLASSES:
        for fs in FS_OPTIONS_MG_S:
            for k, q in flows.items():
                if q > fs:
                    continue
                u_spec = mfc_relative_u(q, fs, spec["rd_frac"], spec["fs_frac"])
                row = {"spec": spec["id"], "fs_mg_s": fs, "fs_sccm_Xe": r(mg_s_to_sccm(fs), 4), "flow": k,
                       "setpoint_fraction_of_fs": r(q / fs, 4), "u_rel_spec": r(u_spec, 4),
                       "u_m_15000h_kg_spec": r(u_spec * xe_mass_kg(q, 15000.0), 4)}
                for dt in DELTA_T_C_OPTIONS:
                    extra = rss(ORIENTATION_ZERO_FS * fs / q, TEMP_ZERO_FS_PER_C * dt * fs / q)
                    tot = rss(u_spec, extra)
                    row[f"u_rel_with_zero_terms_dT{int(dt)}C"] = r(tot, 4)
                    row[f"u_m_15000h_kg_with_zero_terms_dT{int(dt)}C"] = r(tot * xe_mass_kg(q, 15000.0), 4)
                grid.append(row)
    d["flow_measurement_uncertainty"] = {
        "relation": "u_rel = rd_frac + fs_frac * FS / Q (specification form); zero terms added in quadrature: "
                    "orientation 0.4 % FS and temperature 0.12 % FS/degC x dT (REF-SNYDER2017 via W4); u_m = u_rel x "
                    "m_cathode(15,000 h), treated as fully correlated over the mission (a calibration bias does not "
                    "average down)",
        "gas_conversion_note": "every row assumes the instrument is calibrated ON XENON in its final configuration; a "
                               "gas-conversion-factor (GCF) reading adds an uncertainty that no accessed source "
                               "quantifies for Xe (REF-SNYDER2017 Table 2 covers Ar, He, SF6, C2F6, H2 only, per W4) "
                               "-> TBD - requires a Xe calibration",
        "rows": grid,
        "evidence_class": "model-derived",
    }
    d["reference_condition_mismatch"] = {
        "ratio_293_15_over_273_15": r((20.0 + KELVIN) / KELVIN),
        "meaning": "a flow unit referenced to 20 degC read as if referenced to 0 degC (or the reverse) is off by "
                   "this factor (~7.3 %); the MFC certificate's standard/normal reference conditions must be declared "
                   "and converted explicitly (G&K Eq. B-5 uses 273.15 K / 1 atm)",
        "evidence_class": "model-derived",
    }

    grav = []
    for ub in (1.0, 10.0):
        for ut in (0.005, 0.01):
            m_g = gravimetric_min_mass_g(ub, ut)
            row = {"u_balance_mg": ub, "u_target_rel": ut, "min_collected_mass_g": r(m_g, 4)}
            for k, q in flows.items():
                row[f"duration_h_at_{k}"] = r(m_g * 1e-3 / (q * 1e-6) / SECONDS_PER_HOUR, 4)
            grav.append(row)
    d["gravimetric_calibration"] = {
        "relation": "m_min = sqrt(2) * u_balance / u_target (two weighings, balance term only; buoyancy, "
                    "line-volume and temperature corrections come on top); duration = m_min / Q",
        "axes_note": "u_balance values are a parametric axis (assumed), not a statement about any balance; a heavy "
                     "Xe bottle on a high-capacity balance usually has a coarser readability - the bottle mass sets "
                     "the achievable u_balance (TBD - requires the calibration-rig design, H2-6)",
        "rows": grav,
        "evidence_class": "model-derived",
    }
    ror = []
    for vol in (0.5, 1.0):
        for k, q in flows.items():
            ror.append({"volume_L": vol, "temperature_K": 293.15, "flow": k,
                        "dp_dt_Pa_per_s": r(rate_of_rise_Pa_s(q, vol, 293.15), 4)})
    d["rate_of_rise_check"] = {
        "relation": "dp/dt = Q R_s T / V, R_s = R / M_Xe (M_Xe = 131.293 g/mol, G&K App. B)",
        "axes_note": "volume and temperature are example axes (assumed); u(Q)^2 = u(V)^2 + u(T)^2 + u(dp/dt)^2 in "
                     "relative terms",
        "rows": ror,
        "evidence_class": "model-derived",
    }

    preheat_cases = [
        {"id": "PH-HC1-60W", "heater_W": 60.0, "t_s": 200.0,
         "source": "IEPC2017_365 p. 5 (60 W -> about 200 s to about 1460 K emitter)", "evidence_class": "measured"},
        {"id": "PH-HC1-45W", "heater_W": 45.0, "t_s": 600.0,
         "source": "IEPC2017_365 p. 5 (45 W -> about 1460 K in about 600 s)", "evidence_class": "measured"},
        {"id": "PH-JPL-1p5cm", "heater_W": None, "t_s": 1200.0,
         "source": "IEPC2015_43 p. 4 ('cathode heater turned on for about 20 minutes'; heater power up to 300 W "
                   "capability, p. 3; the power used is not stated)", "evidence_class": "measured"},
    ]
    ph_rows = []
    for c in preheat_cases:
        for k, q in flows.items():
            g_per_start = q * 1e-3 * c["t_s"]
            row = {"case": c["id"], "t_preheat_s": c["t_s"], "purge_flow": k, "purge_mdot_mg_s": q,
                   "xe_per_start_g": r(g_per_start, 4),
                   "mission_kg_at_N_starts_SC1": r(g_per_start * inp["n_starts_sc1"] * 1e-3, 4),
                   "mission_kg_at_N_starts_SC2": r(g_per_start * inp["n_starts_sc2"] * 1e-3, 4)}
            if c["heater_W"] is not None:
                row["heater_energy_Wh_per_start"] = r(c["heater_W"] * c["t_s"] / SECONDS_PER_HOUR, 4)
            ph_rows.append(row)
    d["preheat_purge_xe"] = {
        "relation": "Xe per start = t_preheat x mdot_purge (HW-C1-03 rule: the emitter is heated only under Xe flow) "
                    "; mission = Xe per start x N_starts",
        "cases": preheat_cases,
        "N_starts_SC1": inp["n_starts_sc1"], "N_starts_SC2": inp["n_starts_sc2"],
        "N_starts_source": f"{XEL_REL} scenarios SC-1 (nominal_restart) / SC-2 (heavy_restart: one start per orbit "
                           "over 26,000 h at 180 km); scenario values, not allocations",
        "rows": ph_rows,
        "finding": "the preheat time is set by the C-1 heater design; under the purge-while-hot rule it converts "
                   "directly into Xe per start. Heater power (start-phase bus peak, H2-4) trades against Xe per start "
                   "(Xe ledger m_startup); with per-orbit restarts this term can reach the kg class",
        "evidence_class": "model-derived",
    }

    idb = []
    for p_lbl, p_w in (("RFP_1500W", inp["p_max_W"]), ("A5_alloc_1350W", 1350.0), ("A5_alloc_1300W", 1300.0)):
        for vd in inp["vd_set_V"]:
            idb.append({"power_label": p_lbl, "P_W": p_w, "V_d_V": vd,
                        "I_d_upper_bound_A": r(discharge_current_upper_bound_A(p_w, vd), 4)})
    d["emission_current_upper_bounds"] = {
        "relation": "I_d <= P / V_d with all of P in the discharge (bound only; the real I_d is lower and is an H-1 "
                    "measurement). I_emit = I_d + I_keeper + I_interstage (G&K Eqs. 7.2-24/25 p. 339; LANE19)",
        "V_d_source": f"{HWDEF_REL} requirements HW-ENV-01 values.V_d_proposed_set_V (PROPOSED there)",
        "P_source": f"{HWDEF_REL} rfp_basis.power_max_W; A5 allocations_and_requirements 'bus-power design "
                    "allocation <= 1.30-1.35 kW'",
        "rows": idb,
        "evidence_class": "model-derived",
    }

    temps = [
        ("Lafferty fit at 5 A/cm2", 1844.5, "LANE19 derived table (CATHODE_INTEGRATION.md section 5)", "model-derived"),
        ("Lafferty fit at 10 A/cm2", 1915.0, "LANE19 derived table (CATHODE_INTEGRATION.md section 5)",
         "model-derived"),
        ("G&K: > 10 A/cm2 at 1650 degC", 1650.0 + KELVIN, "DOSSIER lab6.t.goebel_10Acm2 (G&K p. 254)", "measured"),
        ("IEPC-2015-43: > 20 A/cm2 at about 1700 degC", 1700.0 + KELVIN, "IEPC2015_43 p. 1", "measured"),
        ("SITAEL: LaB6 operates at about 1900 K", 1900.0, "IEPC2017_365 p. 2", "measured"),
        ("Joussot: about 1600 degC at 19 A", 1600.0 + KELVIN, "DOSSIER lab6.t.joussot_19A", "measured"),
    ]
    trows = [{"point": a, "T_K": r(b, 6), "source": c, "evidence_class": e} for a, b, c, e in temps]
    d["emitter_temperature_points"] = {
        "rows": trows,
        "operating_span_K": [min(t["T_K"] for t in trows), max(t["T_K"] for t in trows)],
        "o2_tolerance_point_K": r(1570.0 + KELVIN, 6),
        "o2_tolerance_source": "DOSSIER lab6.env.o2_withstand_1570C / IEPC2015_43 p. 2 (withstands O2 up to 1e-4 Torr "
                               "at 1570 degC without emission degradation)",
        "ignition_points_K": {
            "SITAEL HC1 heating target about 1460 K": 1460.0,
            "Joussot ignition allowed above about 1300 degC": r(1300.0 + KELVIN, 6),
            "Joussot preheat about 1420 degC": r(1420.0 + KELVIN, 6),
        },
        "evidence_class": "model-derived (unit conversion of the cited points)",
    }
    d["echt_context"] = {
        "channel_OD_mm": 100.0, "channel_width_mm": 10.0,
        "inner_channel_wall_diameter_mm": 100.0 - 2 * 10.0,
        "jpl_1p5cm_keeper_OD_mm": 30.0,
        "note": "published-analog geometry only (CLAUDE.md; IEPC2015_43 p. 4 'keeper has an outer diameter of about "
                "3.0 cm'): at analog scale a 30 mm keeper is smaller than the 80 mm inner channel-wall diameter, so "
                "a central bore is not geometrically excluded; the real check needs H-1's inner wall, inner core and "
                "coil cross-sections (PENDING H2-1). Never a Vyovrinda dimension.",
        "evidence_class": "model-derived (arithmetic on analog values)",
    }
    return d


# ----------------------------------------------------------------------------------------------------------------------
# Design-parameter table
# ----------------------------------------------------------------------------------------------------------------------
def P(pid, name, value, units, basis, source, evidence_class, status, article_class, note=""):
    return {"id": pid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
            "evidence_class": evidence_class, "status": status, "article_class": article_class, "note": note}


FR, TA, GF = ARTICLE_CLASSES
PEND = lambda path: f"PENDING {path}"  # noqa: E731


def parameters(inp: dict, d: dict) -> list:
    q_d, q_u = inp["mdot_design_mg_s"], inp["mdot_upper_test_mg_s"]
    ts = d["emitter_temperature_points"]["operating_span_K"]
    return [
        # --- (1) location ------------------------------------------------------------------------------------------
        P("H22-01", "C-1 mounting location", "central, on the thruster axis inside the inner magnetic core (option "
          "L-CENTRAL); L-EXTERNAL retained as the alternative", "-", "analog",
          "HOFER2008 pp. 2008-2009 (internal cathode improved coupling voltage by 5-10 V vs external; 6-11 V in the "
          "Jameson 6-kW study quoted there; centerline mounting 'favors the improved coupling'), pp. 2007, 2010-2011 "
          "(more collimated, symmetric plume), p. 2012 (drawbacks)", "inferred", "PRELIMINARY", FR,
          "choice inferred from analog practice; magnitudes are not transferable (8-kW Xe device). Owner question "
          "H22-OQ-01; feasibility PENDING H2-1 inner-core bore"),
        P("H22-02", "C-1 axis orientation", "parallel to the thrust axis", "-", "analog",
          "HOFER2008 p. 2006 ('The major axis of both cathodes was aligned parallel with the thrust axis')",
          "measured", "PRELIMINARY", FR),
        P("H22-03", "C-1 orifice axial position relative to the H-1 exit plane / inner pole", None, "mm", "pending",
          "HOFER2008 p. 2006 (analog: internal cathode 'slightly recessed upstream of a hollow section of the inner "
          "magnetic pole')", "none", PEND(H2_1), FR,
          "needs the H-1 inner pole geometry and B map; fixed and recorded once chosen (HW-C1-01)"),
        P("H22-04", "inner-core bore diameter needed for L-CENTRAL", ">= C-1 keeper OD + radial clearance", "mm",
          "pending", "IEPC2015_43 p. 4 (analog keeper OD about 3.0 cm for the 1.5-cm JPL cathode); SITAEL HC1/HC3 "
          "keeper OD not stated (IEPC2017_365)", "none", PEND(H2_1), FR,
          "keeper OD TBD - requires the C-1 selection (HWQ-09); clearance TBD - requires H2-1/H2-5"),
        P("H22-05", "cathode service-line routing for L-CENTRAL", "heater, keeper, cathode-common, thermocouple leads "
          "and the Xe line exit through the rear of the inner core; they must pass the pre-ionizer module slot "
          "between IP-UP and IP-DN without changing with the module and without crossing HALL_INLET_Z0",
          "-", "requirement", f"{HWDEF_REL} HW-C1-01, HW-C1-04, HW-PIM-01 (summary section 0), HW-SVC-01",
          "assumed", PEND(PMI), FR, "interface demand to the pre-ionizer module ICD (A6)"),
        # --- (2) plume / oxygen --------------------------------------------------------------------------------------
        P("H22-06", "shielding / isolation concept of the emitter", "S1 Xe flows whenever the emitter is hot and O2 "
          "may be present; S2 Xe purge before heating (XE_PURGE -> CATHODE_CONDITIONING); S3 keeper encloses the "
          "orifice and shields it from back-ion bombardment; S4 O-compatible keeper/orifice-plate material; S5 "
          "emitter kept at or above the reported O2-tolerance temperature during O-bearing operation", "-",
          "requirement", f"{HWDEF_REL} HW-C1-03; {CONTROLS_REL} states; IEPC2015_43 p. 2 (keeper protects the "
          "orifice plate from back-ion bombardment); IEPC2017_365 p. 3; DOSSIER lab6.env.o2_withstand_1570C",
          "inferred", "PRELIMINARY", FR,
          "S1-S3 are adopted requirements/practice; S4-S5 are PROPOSED design rules of this lane"),
        P("H22-07", "emitter temperature floor during O-bearing operation (PROPOSED design rule)",
          d["emitter_temperature_points"]["o2_tolerance_point_K"], "K", "analog",
          "DOSSIER lab6.env.o2_withstand_1570C (G&K p. 306) and IEPC2015_43 p. 2: LaB6 at 1570 degC withstands O2 up "
          "to 1e-4 Torr without emission degradation", "measured", "PRELIMINARY", FR,
          "secondary statement of diode tests (level 5); O2 only - no atomic-O or N2 threshold exists "
          "(DOSSIER U04, U05); PROPOSED, not in the RFP"),
        P("H22-08", "required attenuation of O from the local environment to the emitter", None, "-", "pending",
          "LANE19 required_attenuation(p_ext, p_tol); DOSSIER U03, G02", "none",
          "TBD - requires a measured emitter-region O/O2 tolerance (G02) and near-cathode partial pressures (RGA, "
          "HW-C1-07)", FR),
        P("H22-09", "keeper / orifice-plate material", None, "-", "pending",
          "IEPC2015_43 p. 2 (analog keeper and orifice-plate materials: graphite); AOL5 evidence on graphite in O "
          "(RIT10 grid erosion higher on O2 than N2, attributed to O-graphite chemistry; MISSE 2 pyrolytic graphite "
          "AO erosion yield 4.15e-25 cm3/atom)", "none",
          "TBD - requires the C-1 selection and keeper-material coupon results (HW-C1-06)", FR,
          "graphite keepers are standard on Xe but carry a published O-chemistry warning; owner question H22-OQ-07"),
        # --- (3) magnetic ------------------------------------------------------------------------------------------
        P("H22-10", "magnetic-field magnitude at the C-1 orifice", None, "G", "pending",
          "HOFER2008 p. 2012 (analog: the centerline region has an axially diverging field of the order of the peak "
          "channel field, 100-300 G)", "none", PEND(H2_1), FR,
          "value comes from the MC-1 design and the M0 B-map at the actual coil currents (HW-MC-03)"),
        P("H22-11", "magnetic-field orientation at the C-1 orifice", "axial (parallel to the cathode axis) for "
          "L-CENTRAL; set by the local field line for L-EXTERNAL", "-", "analog",
          "HOFER2008 p. 2007 (internal cathode plume 'compressed and elongated in the axial direction by the axial "
          "magnetic field emanating from the inner magnetic circuit'); IEPC2015_43 p. 4 (solenoid gives 'an "
          "adjustable axial magnetic field at the cathode exit to simulate that found on axis' of HERMeS)",
          "measured", "PRELIMINARY", FR),
        P("H22-12", "allowed field magnitude at emitter and keeper", None, "G", "pending",
          "no accessed source states a limit; G&K p. 313 (ionization instabilities in the cathode plume can be "
          "inhibited by gas flow and/or the applied axial field): the field is a functional parameter of the "
          "cathode, not only an interference", "none",
          "TBD - requires C-1 characterization inside the MC-1 field at the operating coil currents (S1a) and the "
          "H2-1 field at the cathode location", FR),
        P("H22-13", "ferromagnetic-free zone around C-1 and its mount", "no ferromagnetic conductor, fastener or "
          "structure near MC-1 unless the model and M0/M0b map show it within INV-B3", "-", "requirement",
          f"{HWDEF_REL} HW-MC-12", "assumed", "PRELIMINARY", FR,
          "C-1 tube/flange/heat-shield materials must be declared magnetically (analog JPL: Mo tube, Ta foil, "
          "graphite; IEPC2015_43 pp. 2-3)"),
        # --- (4) thermal -------------------------------------------------------------------------------------------
        P("H22-14", "LaB6 emitter operating temperature (reported/derived span)", ts, "K", "analog",
          "see derived.emitter_temperature_points (G&K p. 254; IEPC2015_43 p. 1; IEPC2017_365 p. 2; DOSSIER "
          "Joussot; LANE19 Lafferty table)", "inferred", "PRELIMINARY", FR,
          "span of cited points for other hardware; the C-1 value depends on its emission current density; C-1 "
          "tube temperature is measured (HW-C1-09), emitter temperature only with a pyrometer view"),
        P("H22-15", "emitter temperature reached before ignition", [1460.0, r(1420.0 + KELVIN, 6)], "K", "analog",
          "IEPC2017_365 p. 5 (about 1460 K); DOSSIER lab6.t.joussot_preheat (about 1420 degC)", "measured",
          "PRELIMINARY", FR),
        P("H22-16", "heater power during preheat (analog envelope)", [45.0, 400.0], "W", "analog",
          "IEPC2017_365 p. 5 (45 W / 60 W, HC1); IEPC2015_43 p. 3 (120 W routinely, H6 LaB6; up to 300 W for the "
          "1.5-cm cathode); DOSSIER lab6.start.joussot_heater_ignition (184.5 W), lab6.start.zsch_heater_max (up to "
          "400 W, non-optimized)", "measured", PEND(H2_4), FR,
          "C-1 value TBD - requires the C-1 selection; a start-phase load on cathode_heater"),
        P("H22-17", "steady heater power", "0 W if C-1 self-heats at the lowest H-1 operating I_d; otherwise the "
          "maintained heater power of the selected unit (analog 185 W below 5 A, Joussot)", "W", "analog",
          "LANE19 (G&K p. 337: heater off once the discharge runs); DOSSIER lab6.heater.joussot_maintained, "
          "lab6.heater.joussot_selfheat_current", "measured",
          "TBD - requires the C-1 self-heating current (S1a) and the lowest operating I_d (Phase 1)", FR),
        P("H22-18", "conduction path C-1 -> H-1", "thin refractory cathode tube -> base flange -> insulating ring "
          "-> H-1 inner core / back pole", "-", "analog",
          "IEPC2015_43 pp. 2-3 (tube 'sufficiently long and thin to minimize conduction of heat from the insert to "
          "the base plate'), p. 4 (flange 'insulated from the thruster body by a Macor-ceramic ring'; flight: brazed "
          "assembly)", "measured", PEND(H2_5), FR),
        P("H22-19", "analog mounting-interface temperature", {"flange_K": 500.0, "keeper_K": 600.0,
          "at_heater_W": 20.0}, "K", "analog", "IEPC2017_365 p. 5 (HC1 thermal test: interface about 500 K, keeper "
          "about 600 K at about 20 W heater power; emitter about 1250 K)", "measured", PEND(H2_5), FR,
          "one analog point at low heater power; not a C-1 boundary condition"),
        P("H22-20", "radiation path C-1 -> inner magnetic circuit", "heat shields around the heater (analog about ten "
          "turns of Ta foil) + an inner-coil hot-spot check against the coil insulation class", "-", "analog",
          "HOFER2008 p. 2012 (internal mounting 'can potentially lead to overheating of the thruster's inner magnetic "
          "circuit due to radiation from the hot cathode insert'); IEPC2015_43 p. 3 (Ta foil heat shield); "
          f"{HWDEF_REL} HW-MC-07, HW-MC-08", "measured", PEND(H2_5), FR),
        # --- (5) keeper / igniter ----------------------------------------------------------------------------------
        P("H22-21", "keeper DC ignition voltage capability (PROPOSED)", 150.0, "V", "analog",
          "IEPC2015_43 p. 4 (150 V applied to the keeper); G&K pp. 310-311 (standard DC keeper voltage 50-150 V; "
          "100-500 V for larger-orifice LaB6 cathodes)", "measured", PEND(H2_4), FR,
          "minimum capability; the C-1 value comes from its ignition test with heater (SITAEL HC1 45-50 V; HC3 < "
          "300 V: IEPC2017_365 pp. 6, 8)"),
        P("H22-22", "keeper pulse ignition capability (PROPOSED)", [300.0, 600.0], "V", "analog",
          "G&K pp. 310-311 ('To ensure reliable thruster ignition over life, it is standard to apply both a DC "
          "keeper voltage in the 50- to 150-V range and a pulsed keeper voltage in the 300- to 600-V range')",
          "measured", PEND(H2_4), FR,
          "motivated also by O exposure: the RAM-HET cathode could not be re-ignited after two days of N2/O2 "
          "testing (LANE19 andreussi_ram_het_cathode; not attributed to poisoning in the source). Owner question "
          "H22-OQ-02"),
        P("H22-23", "keeper current: ignition limit and continuous capability", {"ignition_limit_A": 2.0,
          "continuous_capability_A": [0.5, 3.0]}, "A", "analog",
          "IEPC2015_43 p. 4 (keeper current regulated to 2 A at ignition); IEPC2017_365 p. 8 (HC1 350 h endurance on "
          "MSHT100 with 0.5 A keeper); DOSSIER lab6.start.zsch_keeper_min (at least 3 A keeper for self-heating)",
          "measured", PEND(H2_4), FR, "C-1 value TBD - requires the C-1 selection"),
        P("H22-24", "keeper running voltage (analog envelope)", [5.0, 35.0], "V", "analog",
          "IEPC2015_43 p. 4 (5-15 V after ignition); IEPC2017_365 p. 7 (HC1 keeper-only 30 -> 15 V), p. 8 (HC3 "
          "14-35 V)", "measured", PEND(H2_4), FR),
        P("H22-25", "keeper mode after discharge ignition", "floating if C-1 self-heats at the operating I_d; "
          "current-carrying otherwise (steady cathode_keeper load)", "-", "analog",
          "IEPC2015_43 p. 4 (keeper off and floating above 10 A), p. 5 (below 5 A the cathode stopped unless keeper "
          "> 2 A); IEPC2017_365 pp. 8-9 (HC1 floating with HT100; keeper on with MSHT100 and with HC3 on HT100)",
          "measured", "TBD - requires the C-1 self-heating current measured in S1a vs the H-1 I_d range", FR),
        P("H22-26", "heater supply current capability", 13.0, "A", "analog",
          "LANE19 startup_reference / IEPC-2017-276 p. 3 (1.5-cm LaB6 heater current 13 A); IEPC2017_365 p. 4 (lab "
          "heater supply 80 V / 13 A, reference only)", "measured", PEND(H2_4), FR,
          "C-1 value TBD - requires the C-1 selection"),
        P("H22-27", "ignition sequence", ["XE_PURGE", "CATHODE_CONDITIONING (heater on, Xe cathode flow on)",
          "CATHODE_IGNITION (keeper voltage, then keeper current regulation)", "XE_DISCHARGE_IGNITION (anode supply "
          "on, heater off)", "keeper off/floating or held on (H22-25)"], "-", "requirement",
          f"{CONTROLS_REL} state names; LANE19 startup_reference.hall_only (G&K p. 337; IEPC-2017-276 pp. 3-4; "
          "IEPC2015_43 p. 4)", "assumed", "PRELIMINARY", FR, "identical in every arm (INV-C1)"),
        P("H22-28", "heaterless ignition", "alternative only, not baseline", "-", "analog",
          "IEPC2017_365 p. 3 (heater is a single point of failure; heaterless ignition possible 'at the cost of "
          "requiring higher voltages with the risk of damaging the LaB6 emitter due to thermal shocks'), p. 6 (HC1 "
          "up to 800 V; pp. 6-7: 1 mg/s), p. 8 (HC3 up to 700 V at 1-2 mg/s); DOSSIER lab6.start.heaterless_ignitions_title "
          "(title-level, verify)", "measured", "PRELIMINARY", FR,
          "heaterless starts need a higher ignition flow (Xe per start) and a higher-voltage keeper supply"),
        # --- (6) Xe plumbing ---------------------------------------------------------------------------------------
        P("H22-29", "cathode Xe branch topology", ["Xe metering split (A5 Xe branch)", "isolation valve(s), normally "
          "closed", "particulate filter", "flow control (H-1: cathode MFC; flight: restrictor or proportional valve, "
          "TBD)", "pressure transducer near C-1", "dielectric break (if the grounding scheme needs one)",
          "C-1 gas inlet"], "-", "requirement",
          f"A5 architecture.xe_branch; {HWDEF_REL} HW-C1-04 (own line, never crosses HALL_INLET_Z0), HW-FS-01",
          "assumed", PEND(H2_3), FR, "element order PROPOSED by this lane"),
        P("H22-30", "number of isolation valves in series (flight)", 2, "-", "assumed",
          "PROPOSED by this lane (single-fault tolerance against Xe loss); no accessed source fixes it", "assumed",
          "TBD - requires the owner's fault-tolerance/safety standard and H2-3", FR, "owner question H22-OQ-03"),
        P("H22-31", "filter rating", None, "um", "pending", "no accessed source", "none",
          "TBD - requires the smallest passage of the flow restrictor / C-1 orifice (C-1 selection) and H2-3", FR),
        P("H22-32", "flight flow restrictor / regulated inlet pressure", None, "Pa", "pending", "no accessed source",
          "none", PEND(H2_3), FR, "sized from the measured C-1 flow (H4 output), never from an assumed flow"),
        P("H22-33", "cathode Xe purity", {"flight_lower_bound_percent": 99.99, "h1_test_PROPOSED_percent": 99.999},
          "%", "analog", "IEPC2015_43 p. 2 and DOSSIER lab6.purity.crudest_grade (LaB6 tolerates about 99.99 % Xe); "
          "HOFER2008 p. 2007 (research grade 99.9995 % used); IEPC2017_365 p. 5 (grade 4.5)", "measured",
          "PRELIMINARY", FR,
          "the H-1 test value is PROPOSED so that feed impurities do not confound the O-exposure attribution"),
        P("H22-34", "cathode-line pressure transducer", "near C-1 (analog: about 20 cm from the emitter)", "-",
          "analog", "IEPC2017_365 p. 5 (Kulite transducer on the feed line about 20 cm from the emitter)", "measured",
          "PRELIMINARY", TA, "test-article diagnostic; a flight pressure sensor is H2-3's decision"),
        P("H22-35", "dielectric break rating on the cathode line", None, "V", "pending",
          "depends on the grounding choice (H22-37) and the keeper pulse (H22-22)", "none", PEND(H2_4), FR),
        # --- (7) electrical return ---------------------------------------------------------------------------------
        P("H22-36", "discharge-supply topology", "discharge supply between anode and cathode common; the thruster "
          "floats", "-", "requirement", f"{HWDEF_REL} HW-ELEC-01; G&K p. 339 ('the thruster floats with respect to "
          "either spacecraft common in space or vacuum-chamber common on the ground')", "assumed", "PRELIMINARY",
          FR),
        P("H22-37", "cathode-common reference (option E-FLOAT-R)", "cathode common floating; spacecraft common "
          "(flight) or facility ground (test) tied to cathode common through a declared resistor", "-", "analog",
          "G&K p. 339 ('can be controlled on a spacecraft by a resistor between the spacecraft common and the cathode "
          "common'); IEPC2017_365 p. 4 (all supplies to a common negative reference, setup floating with respect to "
          "ground)", "measured", "PRELIMINARY", FR,
          "resistor value TBD - requires the H2-4 bus/charging analysis and the facility safety case (H22-OQ-04)"),
        P("H22-38", "analog cathode-to-ground potential", [-22.0, -10.0], "V", "analog",
          "HOFER2008 p. 2008 (internal BaO -10 to -13 V; external LaB6 -22 to -15 V; typical -10 to -20 V); G&K "
          "p. 339 (coupling voltage typically about 20 V)", "measured", "PRELIMINARY", FR,
          "sets the order of magnitude of cathode-common-to-ground stand-off; not a C-1 value"),
        P("H22-39", "C-1 body isolation from the H-1 body", "insulating ring between C-1 flange and H-1 mount; H-1 "
          "body potential declared", "-", "analog", "IEPC2015_43 p. 4 (Macor ring); H-1 body potential: owner "
          f"decision (extends {HWDEF_REL} HWQ-07)", "measured", "TBD - requires the owner's H-1 body potential "
          "decision", FR),
        P("H22-40", "C-1 lines across the thrust stand", "heater +/-, keeper, cathode common, tube thermocouple, "
          "Xe line: all in SVC-1, identical in every configuration", "-", "requirement",
          f"{HWDEF_REL} HW-SVC-01, HW-C1-05, HW-C1-09", "assumed", PEND(H2_6), TA),
        P("H22-41", "interstage current return", "any separately biased pre-ionizer electrode returns to cathode "
          "common and is metered (enters I_emit)", "-", "requirement", f"{HWDEF_REL} HW-ELEC-02; LANE19 section 2",
          "assumed", PEND(PMI), TA, "rf_hall / ecr_hall configurations only; hall_only has none"),
        # --- (8) flow measurement ----------------------------------------------------------------------------------
        P("H22-42", "cathode Xe design flow and upper test point (A5)", [q_d, q_u], "mg/s", "allocation",
          f"{A5_REL} xe_mass_allocation.cathode_flow_design_target_mg_s / "
          "cathode_flow_experimental_upper_test_point_mg_s", "assumed", "PRELIMINARY", FR,
          "allocation and test point, not demonstrated flows; the measured spot-mode flow is an H4 output"),
        P("H22-43", "cathode MFC precision range full scale (PROPOSED)", 0.2, "mg/s Xe", "derived",
          "derived.flow_measurement_uncertainty: FS 0.2 mg/s puts 0.10 / 0.15 mg/s at 50 % / 75 % of FS",
          "model-derived", PEND(H2_6), TA,
          f"= {r(mg_s_to_sccm(0.2), 4)} sccm Xe; Xe range of any real unit TBD - requires the manufacturer's Xe "
          "calibration"),
        P("H22-44", "cathode start-flow range full scale (PROPOSED)", 1.0, "mg/s Xe", "analog",
          "IEPC2017_365 p. 6 (HC1 started at 0.6 and 0.1 mg/s with heater), p. 8 (HC3 0.4-0.8 mg/s with heater), "
          "p. 7 (HC1 diode 0.8 mg/s); heaterless 1-2 mg/s (p. 8) excluded", "measured", PEND(H2_6), TA,
          "separate controller or second range; covers heated-start analogs up to 1 mg/s"),
        P("H22-45", "flow accuracy class (PROPOSED)", "+/-(0.5 % of reading + 0.1 % of FS), calibrated on Xe",
          "-", "analog", "BRONKHORST_ELFLOW_SELECT p. 2 (catalog class, reference only)", "assumed", PEND(H2_6), TA,
          "at FS 0.2 mg/s: u_rel = 0.70 % at 0.10 mg/s (see derived); a 1 % FS class at FS 1.0 mg/s gives 10 %"),
        P("H22-46", "flow repeatability", 0.002, "fraction of reading", "analog",
          "BRONKHORST_ELFLOW_SELECT p. 2 ('Repeatability < 0,2% Rd', catalog class)", "assumed", PEND(H2_6), TA,
          "repeatability is what R_arch sees (same MFC, same setpoint in every arm; W4 INS-05)"),
        P("H22-47", "flow step for the spot-mode minimum-flow search (PROPOSED)", 0.005, "mg/s", "assumed",
          "PROPOSED by this lane: 5 % of the design flow, 2.5 % of the proposed precision FS, above the repeatability",
          "assumed", "TBD - requires owner confirmation (H22-OQ-05)", TA),
        P("H22-48", "flow calibration method", "gravimetric on Xe in the final configuration (primary) with a "
          "constant-volume rate-of-rise cross-check; reference conditions declared", "-", "requirement",
          f"{W4_REL} INS-05 calibration (REF-SNYDER2017: each gas, final configuration, across the range, at least "
          "every 12 months; constant-volume or constant-pressure calibrator)", "assumed", PEND(H2_6), GF,
          "gravimetric primary PROPOSED by this lane; see derived.gravimetric_calibration and rate_of_rise_check"),
        P("H22-49", "uncertainty of the 15,000 h cathode Xe mass from flow measurement", {
            "FS0.2_catalog_std_at_0.10": next(x for x in d["flow_measurement_uncertainty"]["rows"]
                                             if x["spec"] == "SPEC-CAT-STD" and x["fs_mg_s"] == 0.2
                                             and x["flow"] == "design_target")["u_m_15000h_kg_spec"],
            "FS1.0_1pctFS_at_0.10": next(x for x in d["flow_measurement_uncertainty"]["rows"]
                                        if x["spec"] == "SPEC-FS1" and x["fs_mg_s"] == 1.0
                                        and x["flow"] == "design_target")["u_m_15000h_kg_spec"]},
          "kg", "derived", "derived.flow_measurement_uncertainty", "model-derived", "PRELIMINARY", TA,
          "measurement term only; the flow itself is an H4 output"),
        # --- (9) Xe ledger -----------------------------------------------------------------------------------------
        P("H22-50", "cathode flow delivered to the Xe ledger", None, "mg/s", "pending",
          f"{XEL_REL} parameters mdot_cathode (closes with the C-1 measured spot-mode minimum flow)", "none",
          "TBD - requires the H4 measurement (S1a / Phase 1)", FR,
          "the ledger keeps the A5 0.10 mg/s design term until then; this lane never replaces it"),
        P("H22-51", "Xe per start from the purge-while-hot rule", "t_preheat x mdot_purge (derived table)", "g",
          "derived", "derived.preheat_purge_xe", "model-derived", PEND(XEL), FR,
          "feeds the ledger's m_startup; the ledger already books a preheat term (scenario_per_event_derivation)"),
    ]


# ----------------------------------------------------------------------------------------------------------------------
# Location options, shielding, magnetic, thermal, keeper, plumbing, electrical, flow sections
# ----------------------------------------------------------------------------------------------------------------------
LOCATION_OPTIONS = [
    {"id": "L-CENTRAL", "description": "C-1 on the thruster axis inside the inner magnetic core, cantilevered from "
                                       "the back pole",
     "published_practice": "internally mounted cathodes on JPL/Busek high-power thrusters (BHT-8000 internal BaO; "
                           "HERMeS on-axis LaB6 field simulated by a solenoid)",
     "sources": ["HOFER2008 pp. 2006-2012", "IEPC2015_43 p. 4"], "analog_label": "ANALOG (8-kW BHT-8000 on Xe; "
                                                                             "12.5-kW HERMeS cathode)",
     "coupling_voltage": "analog improvement of 5-10 V (BHT-8000, 8 kW) and 6-11 V (6-kW study quoted) vs external; "
                         "the source attributes it to location, not emitter (HOFER2008 p. 2009)",
     "plume_exposure": "sits in the central region where the source notes a possible trap for low-energy ions and "
                       "increased keeper erosion (HOFER2008 p. 2012); for ABEP those ions include N+, N2+, O+, O2+ "
                       "(AOL-M05) - keeper erosion and O chemistry at the keeper are a C-1 test item",
     "magnetic_field_at_orifice": "axial, of the order of the peak channel field (analog 100-300 G, HOFER2008 "
                                  "p. 2012); predictable from the MC-1 design because it lies on the axis",
     "thermal": "radiates into the inner magnetic circuit (overheating risk, HOFER2008 p. 2012) -> heat shields and "
                "an inner-coil hot-spot check (H2-5, HW-MC-07/08)",
     "mechanical": "cantilever from the back pole: launch-vibration moment arm (HOFER2008 p. 2012) -> H2-7; needs an "
                   "inner-core bore (H2-1)",
     "experiment_identity": "position cannot change with a module exchange; axisymmetric plume keeps the thrust "
                            "vector on the axis for every arm",
     "rear_interface": "service lines leave through the rear axis, where the pre-ionizer module slot sits "
                       "(IP-UP..IP-DN): routing must be designed into the module ICD"},
    {"id": "L-EXTERNAL", "description": "C-1 outside the outer pole, axis parallel to the thrust axis",
     "published_practice": "traditional external mounting (HOFER2008 p. 2006: 'typical of Hall thrusters with "
                           "optimized cathode locations'); SITAEL HC1/HC3 coupled externally to HT100 "
                           "(IEPC2017_365 pp. 7-9)",
     "sources": ["HOFER2008 pp. 2006-2012", "IEPC2017_365 pp. 7-9"], "analog_label": "ANALOG",
     "coupling_voltage": "analog: larger coupling voltage (-15 to -22 V vs -10 to -13 V, HOFER2008 p. 2008)",
     "plume_exposure": "outside the beam; the external cathode's electrons form a 'halo' along field lines around "
                       "the pole pieces (HOFER2008 p. 2007); inner-core erosion negligible (p. 2012)",
     "magnetic_field_at_orifice": "set by the fringing field at the chosen position; depends on the separatrix "
                                  "location (no accessed source for H-1) -> PENDING H2-1 map",
     "thermal": "decoupled from the inner coil; radiates to the outer pole and the spacecraft side",
     "mechanical": "bracket on the outer pole; no inner-core bore",
     "experiment_identity": "asymmetric near-field plume (HOFER2008 pp. 2009-2011) - identical in every arm, so a "
                            "common-mode effect on R_arch",
     "rear_interface": "service lines stay clear of the pre-ionizer module slot"},
]

SHIELDING = {
    "threat": "A5 architecture-closing risk rank 3 ('Xe-fed cathode consumption and oxygen isolation', evidence "
              "RI-MASS-CATHODE-XE): O2/O from the thruster's own neutral efflux, back-flowing plume ions (N+, N2+, "
              "O+, O2+) and, on ground, the facility background; in flight the thruster faces the wake, so the "
              "ram-facing AO flux of lane 19 is an upper bound, not the local value (inferred; magnitude TBD)",
    "concept": ["S1 Xe cathode flow on whenever the emitter is hot (HW-C1-03)",
                "S2 Xe purge before heating (XE_PURGE)",
                "S3 keeper enclosing the orifice (physical and ion shield)",
                "S4 O-compatible keeper/orifice-plate/insulator materials (TBD, coupons HW-C1-06)",
                "S5 emitter at or above 1843 K (1570 degC) during O-bearing operation (PROPOSED, H22-07)",
                "S6 no emitter heating while O2 is in the chamber without Xe flow; exposure log (AOL-CX-05)"],
    "must_be_demonstrated": [
        {"id": "D-CX-01", "what": "C-1 emission, keeper and coupling voltage stay within a pre-registered drift band "
                                  "over the O-bearing Phase-1 hours (daily Xe reference, AOL-CX-01)"},
        {"id": "D-CX-02", "what": "near-cathode O2 / H2O / N2 partial pressures logged during O-bearing operation "
                                  "(RGA sampling port, HW-C1-07 / AOL-CX-03), as the proxy for the emitter-region "
                                  "environment (G02)"},
        {"id": "D-CX-03", "what": "spot-mode minimum Xe flow vs emission current measured on C-1 in the H-1 field "
                                  "with an atmospheric anode feed (A5 risk 3, G06); poisoning can enlarge the "
                                  "plume-mode region (Suzuki 2024 abstract via LANE19)"},
        {"id": "D-CX-04", "what": "restart after O-bearing operation succeeds within the keeper capability "
                                  "(start log AOL-CX-02)"},
        {"id": "D-CX-05", "what": "post-campaign insert/orifice/keeper inspection (HW-C1-08, AOL-PM-05)"},
    ],
    "not_demonstrable_on_ground_here": "atomic-O exposure (no AO source in HW-ENV-07; HWQ-11) - flight "
                                       "transfer stays open (DOSSIER G02, G09)",
}

FLOW_MEASUREMENT = {
    "requirement": "measure the C-1 Xe flow at the A5 design target 0.10 mg/s and the upper test point 0.15 mg/s, "
                   "and step down to the spot-mode minimum, with an uncertainty small enough that the measured flow "
                   "can be booked in the Xe ledger; the flow itself is NOT assumed (H4 output)",
    "concept": ["two ranges: a precision cathode MFC (FS about 0.2 mg/s Xe) and a start-flow range (FS about 1 mg/s "
                "Xe)", "calibrated on Xe, installed, at the operating inlet pressure and temperature (W4 INS-05)",
                "gravimetric primary calibration + rate-of-rise cross-check", "reference conditions declared on "
                "every certificate (7.3 % trap between 0 and 20 degC references)",
                "zero checked at the installed orientation and temperature before each block"],
    "percent_of_reading_vs_full_scale": "a % FS specification inflates the relative error as 1/Q: at 0.10 mg/s a "
                                        "1 % FS device with FS 1.0 mg/s gives 10 % (0.54 kg over 15,000 h), the "
                                        "same class with FS 0.2 mg/s gives 2 %; a % Rd + % FS class gives 0.70 %",
}


def interface_demands(inp: dict, d: dict) -> list:
    return [
        {"id": "IFD-01", "from": "H2-2", "to": f"H2-1 ({H2_1})", "quantity": "inner-core bore for L-CENTRAL",
         "value": ">= C-1 keeper OD + clearance (analog keeper OD 30 mm)", "units": "mm",
         "status": "PENDING C-1 selection and H2-1 core flux cross-section"},
        {"id": "IFD-02", "from": f"H2-1 ({H2_1})", "to": "H2-2", "quantity": "B magnitude and direction at the C-1 "
         "orifice and along the keeper, at the operating coil currents", "value": None, "units": "G",
         "status": PEND(H2_1)},
        {"id": "IFD-03", "from": "H2-2", "to": f"H2-1 ({H2_1})", "quantity": "ferromagnetic-free zone and declared "
         "magnetic properties of C-1 materials (HW-MC-12)", "value": "declared list", "units": "-",
         "status": "PRELIMINARY"},
        {"id": "IFD-04", "from": "H2-2", "to": f"H2-4 PS-C ({H2_4})", "quantity": "keeper supply: DC ignition "
         "voltage, pulse capability, current limit, continuous current", "value": {"dc_V_min": 150.0,
         "pulse_V": [300.0, 600.0], "ignition_limit_A": 2.0, "continuous_A": [0.5, 3.0],
         "running_V": [5.0, 35.0]}, "units": "V / A", "status": "PRELIMINARY (analog; C-1 values PENDING)"},
        {"id": "IFD-05", "from": "H2-2", "to": f"H2-4 PS-C ({H2_4})", "quantity": "heater supply", "value": {
         "power_W": [45.0, 400.0], "current_A_max": 13.0}, "units": "W / A",
         "status": "PENDING C-1 selection (analog envelope)"},
        {"id": "IFD-06", "from": "H2-2", "to": f"H2-4 PS-C ({H2_4})", "quantity": "bus components booked by C-1",
         "value": ["cathode_heater (start phases; steady only if not self-heating)", "cathode_keeper (ignition; "
                   "steady only if not self-heating)"], "units": "W",
         "status": "PRELIMINARY (bus_power_boundary_v1 component names)"},
        {"id": "IFD-07", "from": "H2-2", "to": f"H2-4 PS-C ({H2_4})", "quantity": "grounding: floating cathode "
         "common with a declared resistor to spacecraft common / facility ground; cathode-line dielectric break "
         "rating", "value": "E-FLOAT-R; analog cathode-to-ground -10 to -22 V", "units": "V / ohm",
         "status": "TBD - requires H2-4 charging analysis and facility safety case"},
        {"id": "IFD-08", "from": "H2-2", "to": f"H2-4 PS-C ({H2_4})", "quantity": "emission capability to cover",
         "value": "I_emit = I_d + I_keeper + I_interstage with I_d <= 8.33 A at 180 V (RFP bound); <= 7.5 A at "
                  "180 V under the 1.35 kW allocation", "units": "A", "status": "PRELIMINARY (bounds, not "
                                                                               "predictions)"},
        {"id": "IFD-09", "from": "H2-2", "to": f"H2-5 ({H2_5})", "quantity": "C-1 heat loads and nodes", "value": {
         "start_heat_W": [45.0, 400.0], "emitter_K": d["emitter_temperature_points"]["operating_span_K"],
         "analog_flange_K": 500.0, "analog_keeper_K": 600.0, "steady_heat_to_body_W": None}, "units": "W / K",
         "status": "PRELIMINARY; steady heat TBD - requires the C-1 selection and S1a tube thermocouple data"},
        {"id": "IFD-10", "from": f"H2-5 ({H2_5})", "to": "H2-2", "quantity": "inner-coil hot spot with C-1 "
         "radiation (L-CENTRAL); flange boundary temperature", "value": None, "units": "K", "status": PEND(H2_5)},
        {"id": "IFD-11", "from": "H2-2", "to": f"H2-3 ({H2_3})", "quantity": "cathode Xe branch from the Xe metering "
         "split: isolation valves, filter, flow control, transducer, break; never crosses HALL_INLET_Z0",
         "value": "H22-29..H22-35", "units": "-", "status": "PENDING H2-3 (if the Xe branch is outside H2-3's scope, "
                                                              "the integration pass reassigns it)"},
        {"id": "IFD-12", "from": "H2-2", "to": f"H2-6 ({H2_6})", "quantity": "cathode diagnostics and flow metrology",
         "value": ["precision cathode MFC FS about 0.2 mg/s Xe", "start range FS about 1 mg/s Xe",
                   "gravimetric + rate-of-rise calibration rig", "tube thermocouple (HW-C1-09)", "pyrometer view if "
                   "possible", "RGA port near C-1 (HW-C1-07)", "cathode-line pressure transducer", "keeper voltage "
                   "oscillation channel (plume-mode detection)", "cathode-to-ground potential", "witness coupons "
                   "HW-C1-06"], "units": "-", "status": PEND(H2_6)},
        {"id": "IFD-13", "from": "H2-2", "to": f"H2-7 ({H2_7})", "quantity": "C-1 mass, envelope and mount",
         "value": {"analog_mass_g_without_cables": {"SITAEL HC1": 30.0, "SITAEL HC3": 50.0}, "mount": "cantilever "
                   "from the back pole (L-CENTRAL) - vibration check", "disassembly": "HW-C1-08"}, "units": "g",
         "status": "PENDING C-1 selection (IEPC2017_365 pp. 5, 8 analog masses)"},
        {"id": "IFD-14", "from": "H2-2", "to": f"A6 pre-ionizer module ICD ({PMI})", "quantity": "C-1 service-line "
         "routing past the module slot; C-1 position independent of the module; interstage return to cathode common "
         "metered", "value": "H22-05, H22-41", "units": "-", "status": PEND(PMI)},
        {"id": "IFD-15", "from": "H2-2", "to": f"A6 Xe ledger ({XEL})", "quantity": "measured mdot_cathode with its "
         "uncertainty; t_preheat and purge flow per start", "value": {"mdot_cathode": "H4 output",
         "u_rel_flow_at_0.10_mg_s_FS0.2_catalog_std": 0.007, "xe_per_start_g": "derived.preheat_purge_xe"},
         "units": "mg/s, g", "status": "PRELIMINARY (ledger present and verified in base; values closed by H4)"},
        {"id": "IFD-16", "from": "H2-2", "to": f"A6 Phase-1 prereg framework ({P1PF})", "quantity": "cathode flow and "
         "power identical across arms (INV-C1) and logged at every point; cathode state logged at every extinction",
         "value": "HW-C1-01, HW-C1-05, AOL-CX-06", "units": "-", "status": "PRELIMINARY"},
        {"id": "IFD-17", "from": "H-1 CI C-1 (hardware definition)", "to": "H2-2", "quantity": "C-1 fixed recorded "
         "position; HWQ-09 C-1 type and emission rating", "value": None, "units": "-",
         "status": "TBD - requires the owner decision HWQ-09"},
    ]


HARD_INCOMPATIBILITY = {
    "verdict": "none found",
    "checked": [
        {"item": "central-mount geometry", "finding": "at analog scale a 30 mm keeper fits inside an 80 mm inner "
         "channel-wall diameter (ECHT OD 100 mm, width 10 mm); the real check is PENDING H2-1", "evidence_class":
         "model-derived (analog arithmetic)", "veto": False},
        {"item": "cathode Xe mass vs the 40 kg requirement", "finding": "the A5 design term 0.10 mg/s gives 5.4 kg "
         "(13.5 %); analog diode minimum flows (0.6 mg/s at 2.5-4 A) would give 81 % but belong to other hardware "
         "and are not verdict-bearing (veto layer RI-MASS-CATHODE-XE straddles); closes only by measurement "
         "(A7 blocker 3)", "evidence_class": "model-derived / measured (analog)", "veto": False},
        {"item": "purge-while-hot Xe per start", "finding": "0.02-0.18 g per start for the analog preheat times at "
         "0.10-0.15 mg/s; kg-class only with per-orbit restarts (N_starts is TBD) - a design driver for fast "
         "preheat, not an incompatibility", "evidence_class": "model-derived", "veto": False},
        {"item": "oxygen exposure of the emitter", "finding": "no atomic-O or N2 threshold exists "
         "(NO_QUANTITATIVE_EVIDENCE); O2 evidence tolerates up to 1e-4 Torr at 1570 degC; cannot be refuted or "
         "confirmed without test", "evidence_class": "measured (secondary)", "veto": False},
        {"item": "magnetic field at the orifice", "finding": "no accessed source gives a limit; axial fields of "
         "100-300 G on axis are standard analog practice", "evidence_class": "measured (analog)", "veto": False},
        {"item": "electrical return", "finding": "floating cathode common with a resistor tie is published flight "
         "practice", "evidence_class": "measured (textbook)", "veto": False},
        {"item": "emission range vs analog cathode classes", "finding": "the H-1 envelope (bound 8.33 A at 180 V, "
         "unknown low end) straddles published classes (SITAEL HC3 1-3 A design; JPL 1.5-cm needs >= 7.5 A without "
         "keeper; Joussot self-heats from 5 A): a steady keeper or heater load may be needed at the low end - a bus "
         "cost to carry, not a veto", "evidence_class": "measured (analog)", "veto": False},
        {"item": "flow-measurement capability at 0.10 mg/s", "finding": "catalog-class instruments with Xe "
         "calibration reach < 1 % (1 sigma treated) at FS 0.2 mg/s; measurable", "evidence_class":
         "model-derived", "veto": False},
    ],
}

BLOCKERS = [
    {"blocker": 3, "text": "Xe/cathode closure", "how": "direct: defines the flow-measurement capability for the "
     "0.10-0.15 mg/s measurement, the spot-mode minimum-flow search (D-CX-03), the purge-while-hot Xe per start and "
     "the O-isolation demonstrations (D-CX-01..05); no value is closed here"},
    {"blocker": 1, "text": "Hall-only sustainment at the actual atmospheric feed state", "how": "indirect: C-1 is "
     "identical in every arm; Phase-1 extinction records must separate cathode-limited (plume-mode, keeper "
     "oscillation) from discharge extinctions (AOL-CX-06) so that a cathode limit is never read as a sustainment "
     "limit"},
    {"blocker": 2, "text": "incremental RF/ECR benefit after full bus-power accounting", "how": "indirect: "
     "cathode_keeper and cathode_heater are common bus components; if an arm's I_d falls below the C-1 self-heating "
     "current a steady keeper load appears in that arm only (LANE19) - measured per arm, never assumed"},
]

M16_ROWS = [
    {"subsystem": "shielded Xe-fed LaB6 hollow cathode", "role": "primary", "proposed_state": "BLOCKED",
     "blocking_item": "HWQ-09: C-1 type and emission rating (owner confirmation + selection) - fixes keeper OD, "
                      "heater power, ignition flow and self-heating current used by every PENDING row here",
     "rollup_category": "hardware-definition blocker",
     "note": "the architecture-level closure (A5 risk 3) follows only from the H4 measurement; not a blocker of "
             "H-1 build"},
    {"subsystem": "Xe metering (splits to ignition/transition feed and cathode feed)", "role": "contributes the "
     "cathode branch and flow-measurement specification", "proposed_state": "RUNNING",
     "blocking_item": None, "rollup_category": None},
    {"subsystem": "sensors/diagnostics", "role": "contributes C-1 diagnostics and flow metrology demands (H2-6 owns)",
     "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None},
    {"subsystem": "PPU/power distribution", "role": "contributes keeper/heater supply demands (H2-4 owns)",
     "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None},
    {"subsystem": "thermal control", "role": "contributes C-1 heat loads and nodes (H2-5 owns)",
     "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None},
    {"subsystem": "mechanical/structural interfaces", "role": "contributes the C-1 mount and envelope (H2-7 owns)",
     "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None},
]

H3_PROCUREMENT = [
    {"id": "H3-C1-01", "item": "C-1 LaB6 hollow cathode unit (+ spare; a sacrificial unit if the owner wants a "
     "destructive O-exposure test)", "long_lead": True, "spec_level_needed_to_order": [
         "emission range covering I_emit up to the 8.33 A bound plus keeper/interstage (HW-C1-02), with the lowest "
         "self-heating current the design allows (reported)", "spot-mode minimum flow vs current curve on Xe "
         "(supplier data as reference)", "heater power and time to ignition; keeper ignition voltage with heater",
         "keeper OD/length/mass envelope (feeds H2-1 bore, H2-7)", "keeper/orifice/insulator material list (O "
         "compatibility, magnetic properties)", "tube thermocouple point and pyrometer view (HW-C1-09); "
         "disassemblable (HW-C1-08)"], "reference_data": "SITAEL HC1/HC3 (IEPC2017_365), JPL 0.63/1.5-cm LaB6 "
     "(IEPC2015_43), Joussot laboratory LaB6 (DOSSIER) - published reference only, no supplier contact"},
    {"id": "H3-C1-02", "item": "cathode precision MFC (FS about 0.2 mg/s Xe) and start-range MFC (FS about 1 mg/s "
     "Xe), Xe-calibrated", "long_lead": False, "spec_level_needed_to_order": [
         "Xe calibration by the manufacturer at the stated reference conditions", "accuracy class +/-(0.5 % Rd + "
         "0.1 % FS) or better", "repeatability < 0.2 % Rd", "zero temperature coefficient stated", "vacuum-rated "
         "outlet, metal seals preferred, He leak spec stated"],
     "reference_data": "BRONKHORST_ELFLOW_SELECT catalog (reference only; not a selection)"},
    {"id": "H3-C1-03", "item": "gravimetric calibration kit (small Xe cylinder, balance, fixture) and a constant-"
     "volume calibrator", "long_lead": False, "spec_level_needed_to_order": [
         "balance capacity above cylinder + fixture and readability per derived.gravimetric_calibration",
         "calibrator volume known to the uncertainty budget"], "reference_data": "W4 REF-SNYDER2017 practice"},
    {"id": "H3-C1-04", "item": "cathode-branch valves, filter, dielectric break, pressure transducer",
     "long_lead": False, "spec_level_needed_to_order": ["Xe service, cleanliness class TBD (H2-3)", "break voltage "
     "PENDING H2-4"], "reference_data": "none accessed"},
    {"id": "H3-C1-05", "item": "keeper (DC + pulse) and heater supplies (PS-C)", "long_lead": False,
     "spec_level_needed_to_order": ["IFD-04, IFD-05"], "reference_data": "IEPC2017_365 p. 4 lab supplies "
     "(reference only)"},
]

H4_TESTS = [
    {"closes": "H22-10/H22-11/H22-12 (field at the orifice)", "stage": "S1a", "measure": "B map at the C-1 "
     "orifice at the operating coil currents (M0); C-1 characterization inside that field"},
    {"closes": "H22-17/H22-25 (self-heating current, keeper mode)", "stage": "S1a", "measure": "C-1 minimum "
     "discharge current without keeper and heater; keeper current needed below it"},
    {"closes": "H22-16/H22-21/H22-22/H22-23 (heater, keeper)", "stage": "S1a", "measure": "heater power and time to "
     "ignition; keeper ignition voltage; start log per start (AOL-CX-02)"},
    {"closes": "H22-43..H22-49 (flow measurement)", "stage": "S1a", "measure": "gravimetric Xe calibration of both "
     "ranges installed; rate-of-rise cross-check; zero vs orientation and temperature"},
    {"closes": "H22-50 (mdot_cathode)", "stage": "S1a + Phase 1", "measure": "spot-mode minimum Xe flow vs emission "
     "current with an atmospheric anode feed (D-CX-03); plume-mode onset by keeper-voltage oscillation"},
    {"closes": "H22-38 (cathode-to-ground potential)", "stage": "S1 / every reading", "measure": "cathode-to-ground "
     "and coupling voltage (HW-C1-05)"},
    {"closes": "H22-01 position reproducibility", "stage": "S1b", "measure": "C-1 position after remount; daily Xe "
     "reference (AOL-CX-01)"},
    {"closes": "H22-06/H22-07/H22-08 (shielding)", "stage": "Phase 1", "measure": "near-cathode RGA partial "
     "pressures, hot-emitter O-exposure log, emitter/tube temperature, drift of the daily Xe reference"},
    {"closes": "H22-51 (Xe per start)", "stage": "S1a + Phase 1", "measure": "integrated Xe per start per phase "
     "(purge, conditioning, ignition)"},
    {"closes": "H22-09 (keeper material)", "stage": "post-campaign", "measure": "keeper/insert/orifice inspection "
     "(HW-C1-08) and coupons (HW-C1-06)"},
]

MILESTONE = {
    "A": "supported: C-1 integration is conditionally closable - 'the architecture holds provided C-1 sustains "
         "spot mode at <= the Xe flow the ledger can afford, keeps its emission/keeper drift inside the "
         "pre-registered band under O-bearing operation, and restarts within the keeper capability'",
    "B": "needs the H4 measurements (D-CX-01..04), the H2-1 field at the orifice, the C-1 selection (HWQ-09) and "
         "the Xe ledger closed with the measured flow",
    "C": "needs the flight C-1 design (heater/keeper qualification, start cycles G05, wear/life G04), the flight "
         "flow restrictor sized from measurement, thermal and vibration closure of the mount",
}

OWNER_QUESTIONS = [
    {"id": "H22-OQ-01", "q": "Confirm L-CENTRAL as the PRELIMINARY C-1 location (L-EXTERNAL as the alternative if "
                             "H2-1 cannot provide the inner-core bore)."},
    {"id": "H22-OQ-02", "q": "Require a pulsed keeper ignition capability (300-600 V) in PS-C?"},
    {"id": "H22-OQ-03", "q": "Two isolation valves in series on the flight cathode branch?"},
    {"id": "H22-OQ-04", "q": "Resistor value and switching for the cathode-common tie to facility ground / spacecraft "
                             "common."},
    {"id": "H22-OQ-05", "q": "Flow step (PROPOSED 0.005 mg/s) and stopping rule for the spot-mode minimum-flow "
                             "search."},
    {"id": "H22-OQ-06", "q": "Purge flow and purge duration rule before heating (sets Xe per start)."},
    {"id": "H22-OQ-07", "q": "Keeper material (graphite vs an O-resistant alternative) given the O-chemistry "
                             "warning."},
    {"id": "H22-OQ-08", "q": "Adopt the PROPOSED emitter temperature floor of 1843 K during O-bearing operation?"},
]


# ----------------------------------------------------------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    pins = verify_decision_pins()
    inp = read_inputs()
    d = derive(inp)
    doc = {
        "schema": "h2_design_lane_v1",
        "id": "h2_2_cathode_integration_v1",
        "lane": "fo_h2_2_cathode_integration",
        "trigger": "T_H2_2_CATHODE_INTEGRATION",
        "owner_addendum": "A7",
        "wave": "H2 hardware (design / preliminary sizing; not architecture selection)",
        "status": "PRELIMINARY_DRAFT_PENDING_INTEGRATION",
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_DIR_REL}/{MD_NAME}",
        "test": TEST_REL,
        "configuration_items": {"primary": "C-1", "touched": ["H-1", "MC-1", "FS-C", "PS-C", "SVC-1", "PIM-0",
                                                             "PIM-RF", "PIM-ECR"],
                                "interface_planes": ["IP-UP", "IP-DN", "HALL_INLET_Z0"]},
        "architectures": list(ARCHITECTURES),
        "architecture_neutrality": "C-1 is common to hall_only, rf_hall and ecr_hall (INV-C1); no ranking, no "
                                   "winner, no elimination",
        "what_this_is_not": [
            "not a performance prediction (no thrust, efficiency, discharge current or plasma state)",
            "not based on any Hall transport closure (credible set empty) or on abep_sim/plasma_devices.py",
            "not a C-1 selection or a procurement; catalog data are reference only",
            "A5 numbers are allocations or requirements, never predictions",
        ],
        "decision_pins": pins,
        "provenance_reads_sha256": dict(PROVENANCE_READS),
        "never_pinned": list(NEVER_PINNED),
        "inputs_read": inp,
        "sources": SOURCES,
        "design_parameters": parameters(inp, d),
        "location_options": LOCATION_OPTIONS,
        "location_preliminary_choice": "L-CENTRAL (PRELIMINARY; H22-01)",
        "shielding_isolation": SHIELDING,
        "flow_measurement": FLOW_MEASUREMENT,
        "derived": d,
        "interface_demands": interface_demands(inp, d),
        "hard_incompatibility_check": HARD_INCOMPATIBILITY,
        "architecture_changing_blockers_touched": BLOCKERS,
        "m16_rows": M16_ROWS,
        "h3_procurement_inputs": H3_PROCUREMENT,
        "h4_test_inputs": H4_TESTS,
        "milestone": MILESTONE,
        "owner_questions": OWNER_QUESTIONS,
        "parallel_lanes_referenced": list(PARALLEL_PATHS),
    }
    return doc


# ----------------------------------------------------------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------------------------------------------------------
def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return str(v)


def _esc(s: str) -> str:
    return str(s).replace("|", "/").replace("\n", " ")


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# H2-2 cathode integration for C-1 (shielded Xe-fed LaB6 hollow cathode)")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| lane | `{doc['lane']}` (trigger `{doc['trigger']}`, owner addendum A7, H2 hardware wave) |")
    a(f"| status | **{doc['status']}**: design / preliminary sizing, not architecture selection |")
    a(f"| data (authoritative) | [`{JSON_NAME}`]({JSON_NAME}), written by [`{Path(SCRIPT_REL).name}`]"
      f"({Path(SCRIPT_REL).name}) (`--check` reproduces both files byte for byte) |")
    a(f"| test | `{TEST_REL}` |")
    a(f"| base commit | `{BASE_COMMIT[:7]}` |")
    a("| architectures | `hall_only`, `rf_hall`, `ecr_hall` share one C-1 (INV-C1). No winner, no ranking |")
    a("")
    a("This file is generated. Edit the builder, not this file.")
    a("")
    a("**Owner basis (immutable, sha256-pinned; the build refuses on a mismatch):**")
    a("")
    a("| file | sha256 |")
    a("|---|---|")
    for k, v in doc["decision_pins"].items():
        a(f"| `{k}` | `{v}` |")
    a("")
    a("Verified deliverables read for values (sha256 at the base commit, recorded as provenance; the values are "
      "re-read and compared on every build): " + ", ".join(f"`{k}`" for k in doc["provenance_reads_sha256"]) + ".")
    a("Mutable governance files are never read or pinned.")
    a("")
    a("**What this is not.** " + " ".join(s[0].upper() + s[1:] + "." for s in doc["what_this_is_not"]))
    a("")
    a("## Summary")
    a("")
    a("- **Location (PRELIMINARY): L-CENTRAL.** Put C-1 on the axis inside the inner magnetic core. The published "
      "analog practice is JPL/Busek internal mounting. On the 8-kW BHT-8000 the internal cathode gave a 5-10 V "
      "better coupling voltage than the external one, and a more collimated, symmetric plume (Hofer et al. 2008). "
      "That is an analog result: its magnitudes do not transfer to H-1. Internal mounting brings its own costs: "
      "radiation into the inner coil, a cantilever mount, keeper erosion by trapped low-energy ions (for ABEP: N, "
      "O ions) and service lines that leave through the rear axis, where the pre-ionizer module slot sits. "
      "L-EXTERNAL remains the alternative if H2-1 cannot provide the bore.")
    a("- **Flow measurement.** Two ranges are proposed: a precision range with FS about 0.2 mg/s Xe and a start "
      "range with FS about 1 mg/s. In the tabulated grid, better than 1 % at 0.10 mg/s needs a precision FS of about "
      "0.3 mg/s or less, and that cannot also cover the analog ignition flows (up to about 1 mg/s). A single "
      "1 %-FS device sized for ignition flows (FS 1 mg/s) gives 10 % at 0.10 mg/s, which is 0.54 kg on the 5.4 kg "
      "cathode term. A catalog-class ±(0.5 % Rd + 0.1 % FS) device, calibrated on Xe at FS 0.2 mg/s, gives 0.70 % "
      "(0.038 kg). Every certificate must declare its reference conditions: 0 °C versus 20 °C is a 7.3 % trap.")
    a("- **Purge-while-hot costs Xe per start.** The poisoning rule (heat the emitter only under Xe flow) turns the "
      "preheat time into Xe: 0.02-0.18 g per start for the analog preheat times at 0.10-0.15 mg/s. Heater power "
      "(the start-phase bus peak) therefore trades against Xe per start. The term reaches the kg class only with "
      "per-orbit restarts, and N_starts is TBD.")
    a("- **Emission class straddle.** The H-1 envelope is bounded at 8.33 A at 180 V (RFP), and its low end is "
      "unknown. It spans published LaB6 classes. At the low end a steady keeper or heater load may be needed, and "
      "that load is booked per arm.")
    a("- **Hard incompatibility: none found** (eight checks, section 9).")
    a("")
    a("## 1. Design-parameter table")
    a("")
    a("Basis ∈ {requirement, allocation, analog, derived, assumed, pending}. Article class: FR = flight-representative, "
      "TA = H-1 test-article only, GF = ground/facility only.")
    a("")
    a("| id | name | value | units | basis | evidence | status | class | source |")
    a("|---|---|---|---|---|---|---|---|---|")
    short = {"FLIGHT_REPRESENTATIVE": "FR", "H1_TEST_ARTICLE_ONLY": "TA", "GROUND_FACILITY_ONLY": "GF"}
    for p in doc["design_parameters"]:
        a(f"| {p['id']} | {_esc(p['name'])} | {_esc(_fmt(p['value']))} | {_esc(p['units'])} | {p['basis']} | "
          f"{p['evidence_class']} | {_esc(p['status'])} | {short[p['article_class']]} | {_esc(p['source'])} |")
    a("")
    notes = [p for p in doc["design_parameters"] if p["note"]]
    a("Notes:")
    a("")
    for p in notes:
        a(f"- **{p['id']}:** {p['note']}")
    a("")
    a("## 2. Mechanical location options (published analogs, labelled)")
    a("")
    keys = ["description", "analog_label", "published_practice", "coupling_voltage", "plume_exposure",
            "magnetic_field_at_orifice", "thermal", "mechanical", "experiment_identity", "rear_interface"]
    a("| aspect | " + " | ".join(o["id"] for o in doc["location_options"]) + " |")
    a("|---|" + "---|" * len(doc["location_options"]))
    for k in keys:
        a(f"| {k.replace('_', ' ')} | " + " | ".join(_esc(o[k]) for o in doc["location_options"]) + " |")
    a("")
    a(f"**PRELIMINARY choice:** {doc['location_preliminary_choice']}. Owner question H22-OQ-01.")
    a("")
    a("## 3. Plume / oxygen exposure and shielding (A5 risk 3)")
    a("")
    sh = doc["shielding_isolation"]
    a(f"- **Threat.** {sh['threat']}.")
    a("- **Concept:**")
    for c in sh["concept"]:
        a(f"  - {c};")
    a("- **Must be demonstrated:**")
    for c in sh["must_be_demonstrated"]:
        a(f"  - **{c['id']}:** {c['what']};")
    a(f"- **Not demonstrable here:** {sh['not_demonstrable_on_ground_here']}.")
    a("")
    a("## 4. Magnetic, thermal, keeper/igniter, Xe plumbing, electrical return")
    a("")
    a("These are covered by rows H22-10..H22-41 of section 1:")
    a("")
    a("- **Magnetic:** H22-10..13. The field at the orifice is PENDING H2-1. It is a functional parameter "
      "(G&K p. 313), so C-1 must be characterized inside the MC-1 field, not only in diode mode.")
    a("- **Thermal:** H22-14..20.")
    a("- **Keeper/igniter:** H22-21..28, including the ignition sequence expressed as dual-feed state-machine "
      "states. Heaterless ignition is an alternative only.")
    a("- **Xe plumbing:** H22-29..35.")
    a("- **Electrical:** H22-36..41. The PRELIMINARY choice is E-FLOAT-R: a floating cathode common with a declared "
      "resistor tie to spacecraft common or facility ground.")
    a("")
    t = doc["derived"]["emitter_temperature_points"]
    a("Emitter temperature points (K):")
    a("")
    a("| point | T (K) | source | evidence |")
    a("|---|---|---|---|")
    for row in t["rows"]:
        a(f"| {row['point']} | {row['T_K']} | {_esc(row['source'])} | {row['evidence_class']} |")
    a("")
    a(f"The operating span of the cited points is {t['operating_span_K'][0]}-{t['operating_span_K'][1]} K. The O2 "
      f"tolerance point is {t['o2_tolerance_point_K']} K.")
    a("")
    a("Discharge-current upper bounds I_d ≤ P/V_d. These are bounds, not predictions; they size the C-1 emission "
      "capability (HW-C1-02):")
    a("")
    a("| P label | P (W) | V_d (V) | I_d bound (A) |")
    a("|---|---|---|---|")
    for row in doc["derived"]["emission_current_upper_bounds"]["rows"]:
        a(f"| {row['power_label']} | {row['P_W']} | {row['V_d_V']} | {row['I_d_upper_bound_A']} |")
    a("")
    a("## 5. Flow-measurement capability for 0.10-0.15 mg/s Xe")
    a("")
    fm = doc["flow_measurement"]
    a(f"- **Requirement.** {fm['requirement']}.")
    a("- **Concept:**")
    for c in fm["concept"]:
        a(f"  - {c};")
    a(f"- **% of reading vs % of full scale.** {fm['percent_of_reading_vs_full_scale']}.")
    a("")
    fu = doc["derived"]["flow_measurement_uncertainty"]
    a(f"Relation: {fu['relation']}.")
    a("")
    a(f"Gas: {fu['gas_conversion_note']}.")
    a("")
    a("| spec | FS (mg/s) | FS (sccm Xe) | flow | Q/FS | u_rel spec | u_m 15,000 h (kg) | u_rel +zero (ΔT 1 °C) | "
      "u_rel +zero (ΔT 5 °C) |")
    a("|---|---|---|---|---|---|---|---|---|")
    for row in fu["rows"]:
        a(f"| {row['spec']} | {row['fs_mg_s']} | {row['fs_sccm_Xe']} | {row['flow']} | "
          f"{row['setpoint_fraction_of_fs']} | {row['u_rel_spec']} | {row['u_m_15000h_kg_spec']} | "
          f"{row['u_rel_with_zero_terms_dT1C']} | {row['u_rel_with_zero_terms_dT5C']} |")
    a("")
    a("Specification classes:")
    a("")
    for s in SPEC_CLASSES:
        a(f"- `{s['id']}`: {s['source']}.")
    a("")
    gc = doc["derived"]["gravimetric_calibration"]
    a(f"Gravimetric calibration: {gc['relation']}. {gc['axes_note']}.")
    a("")
    a("| u_balance (mg) | u_target | min mass (g) | duration at 0.10 mg/s (h) | duration at 0.15 mg/s (h) |")
    a("|---|---|---|---|---|")
    for row in gc["rows"]:
        a(f"| {row['u_balance_mg']} | {row['u_target_rel']} | {row['min_collected_mass_g']} | "
          f"{row['duration_h_at_design_target']} | {row['duration_h_at_upper_test_point']} |")
    a("")
    rr = doc["derived"]["rate_of_rise_check"]
    a(f"Rate-of-rise cross-check: {rr['relation']}. " + "; ".join(
        f"V = {x['volume_L']} L, {x['flow']}: {x['dp_dt_Pa_per_s']} Pa/s" for x in rr["rows"]) + ".")
    a("")
    rc = doc["derived"]["reference_condition_mismatch"]
    a(f"Reference conditions: the ratio is {rc['ratio_293_15_over_273_15']}. {rc['meaning']}.")
    a("")
    a("## 6. Cathode Xe to the parametric Xe ledger")
    a("")
    cx = doc["derived"]["cathode_xe_mass"]
    a(f"A5 arithmetic reproduced: {_fmt(cx['values'])} (consistent with A5: {cx['consistent_with_a5']}).")
    a("")
    pp = doc["derived"]["preheat_purge_xe"]
    a(f"Purge-while-hot: {pp['relation']}. N_starts: {pp['N_starts_source']}.")
    a("")
    a("| case | t_preheat (s) | purge flow | Xe per start (g) | kg at SC-1 N | kg at SC-2 N | heater Wh per start |")
    a("|---|---|---|---|---|---|---|")
    for row in pp["rows"]:
        a(f"| {row['case']} | {row['t_preheat_s']} | {row['purge_mdot_mg_s']} | {row['xe_per_start_g']} | "
          f"{row['mission_kg_at_N_starts_SC1']} | {row['mission_kg_at_N_starts_SC2']} | "
          f"{row.get('heater_energy_Wh_per_start', '—')} |")
    a("")
    a(f"Finding: {pp['finding']}.")
    a("")
    a("## 7. Interface demands")
    a("")
    a("| id | from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|---|")
    for x in doc["interface_demands"]:
        a(f"| {x['id']} | {_esc(x['from'])} | {_esc(x['to'])} | {_esc(x['quantity'])} | {_esc(_fmt(x['value']))} | "
          f"{_esc(x['units'])} | {_esc(x['status'])} |")
    a("")
    a("## 8. Architecture-changing blockers touched (A7)")
    a("")
    for b in doc["architecture_changing_blockers_touched"]:
        a(f"- **Blocker {b['blocker']} ({b['text']}).** {b['how'][0].upper() + b['how'][1:]}.")
    a("")
    a("## 9. Hard-incompatibility check")
    a("")
    a(f"**Verdict: {doc['hard_incompatibility_check']['verdict']}.**")
    a("")
    a("| item | finding | evidence class | veto |")
    a("|---|---|---|---|")
    for c in doc["hard_incompatibility_check"]["checked"]:
        a(f"| {c['item']} | {_esc(c['finding'])} | {c['evidence_class']} | {c['veto']} |")
    a("")
    a("## 10. M16 rows (proposed execution states)")
    a("")
    a("| subsystem (A5) | role | proposed state | blocking item | rollup |")
    a("|---|---|---|---|---|")
    for m in doc["m16_rows"]:
        a(f"| {m['subsystem']} | {_esc(m['role'])} | {m['proposed_state']} | {_esc(_fmt(m['blocking_item']))} | "
          f"{_fmt(m['rollup_category'])} |")
    a("")
    a("## 11. H3 procurement inputs (specification level; published data as reference only)")
    a("")
    for h in doc["h3_procurement_inputs"]:
        a(f"- **{h['id']}: {h['item']}.** Long lead: {h['long_lead']}. Reference data: {h['reference_data']}.")
        a("  To order it needs:")
        for s in h["spec_level_needed_to_order"]:
            a(f"  - {s};")
    a("")
    a("## 12. H4 test inputs")
    a("")
    a("| closes | stage | measure |")
    a("|---|---|---|")
    for h in doc["h4_test_inputs"]:
        a(f"| {_esc(h['closes'])} | {h['stage']} | {_esc(h['measure'])} |")
    a("")
    a("## 13. Milestones")
    a("")
    for k, v in doc["milestone"].items():
        a(f"- **{k}:** {v}.")
    a("")
    a("## 14. Owner questions")
    a("")
    for q in doc["owner_questions"]:
        a(f"- **{q['id']}:** {q['q']}")
    a("")
    a("## 15. Sources")
    a("")
    for k, s in doc["sources"].items():
        loc = s.get("url") or s.get("path")
        sha = f" sha256 `{s['sha256']}`." if "sha256" in s else ""
        a(f"- **{k}.** {s['citation']}. {loc}. {s['access']}.{sha}")
    a("")
    a("Reproduce:")
    a("")
    a("```")
    a(f"python {SCRIPT_REL} --check")
    a(f"python -m pytest -q {TEST_REL}")
    a("```")
    a("")
    return "\n".join(L)


def render_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def resolve_parallel() -> dict:
    """Lazy status of the parallel lanes (never used by the build or the test)."""
    return {p: ("present" if (REPO / p).exists() else "PENDING (not in this checkout)") for p in PARALLEL_PATHS}


def main(argv) -> int:
    if "--resolve" in argv:
        print(json.dumps(resolve_parallel(), indent=1))
        return 0
    doc = build()
    js, md = render_json(doc), render_md(doc)
    out_dir = REPO / LANE_DIR_REL
    if "--check" in argv:
        ok = ((out_dir / JSON_NAME).read_text() == js) and ((out_dir / MD_NAME).read_text() == md)
        print("OK" if ok else "MISMATCH")
        return 0 if ok else 1
    (out_dir / JSON_NAME).write_text(js)
    (out_dir / MD_NAME).write_text(md)
    print(f"wrote {LANE_DIR_REL}/{JSON_NAME} and {MD_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
