#!/usr/bin/env python3
"""H2-6 diagnostics + H-1 fixture (fo_h2_6_diagnostics_fixture): deterministic builder of the lane deliverable.

Owner addendum A7 wave H2 (trigger T_H2_6_DIAGNOSTICS_FIXTURE). This is a hardware design / preliminary-sizing lane,
NOT an architecture-selection lane: it never predicts thrust, efficiency, discharge current or plasma state, never
selects hall_only / rf_hall / ecr_hall and never uses a Hall transport closure, a screening candidate, the superseded
0-D Hall model (abep_sim/plasma_devices.py) or the withdrawn v1.2-v1.6 numbers.

Outputs (same folder)::

    h2_6_diagnostics_fixture_v1.json     machine-readable deliverable (authoritative)
    H2_6_DIAGNOSTICS_FIXTURE.md          companion document rendered from the JSON

Usage::

    python docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py --write
    python docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py --check           # exit 1 on drift
    python docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py --verify-sources  # pins + values
    python docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py --pending-status  # lazy lane check

Rules implemented here:
  * every number is either an explicit input (value, unit, evidence class, source) or derived from inputs by the
    functions below; ``derive()`` raises on a missing input (CLAUDE.md rule 3: no silent default);
  * the output does not depend on the presence or content of any parallel (PENDING) lane; ``pending_status()`` only
    reports whether a pending lane path exists in the checkout and never reads its content into a value;
  * immutable owner decision files are pinned by sha256; mutable deliverables are consumed by value and re-checked
    value-by-value (``--verify-sources``), their sha256 at the base commit is recorded as provenance, not as a pin;
  * governance files (lane registry, trigger registry, ledgers, runtime_state) are never pinned.

Pure standard library; no network; deterministic (no clock, no randomness).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
LANE_REL = "docs/hardware/h2/h2_6_diagnostics_fixture"
SCRIPT_REL = f"{LANE_REL}/build_h2_6_diagnostics_fixture.py"
JSON_NAME = "h2_6_diagnostics_fixture_v1.json"
MD_NAME = "H2_6_DIAGNOSTICS_FIXTURE.md"
BASE_COMMIT = "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e"

ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
FLIGHT_CLASSES = ("FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY")
BASES = ("requirement", "allocation", "analog", "derived", "assumed", "pending")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")
STAGES = ("S1a", "S1-C4", "S1b", "Phase 1", "Phase 2", "Phase 3", "S5")
M16_STATES = ("READY", "RUNNING", "BLOCKED", "VERIFIED")
ROLLUPS = ("architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
           "proposal-only documentation gap")

# ---------------------------------------------------------------------------------------------------------------------
# Authority: immutable owner decision files (pinned) and mutable deliverables (provenance only)
# ---------------------------------------------------------------------------------------------------------------------
DECISION_PINS = (
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json",
     "5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac", "original owner disposition od_hardware_pivot"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json",
     "10d79026f1a65e0c2a9fa9e1f9a5f9abc9d162692711857bd43575f3095c8d4e",
     "A3: metrology lab / cathode temperature / near-cathode RGA / k = 2 / S1a gate"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
     "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4",
     "A4: force/DC/RF traceability, metrology spec approved as procurement spec, MFC ranges, S1a interlocks, C-1 diode"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
     "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
     "A5: proposal reference architecture / Phase-1 baseline (allocations, 16 subsystems, closing risks)"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
     "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
     "A6: follow-on authorization, Phase-1 decision quantities, not_authorized list, execution-order clarification"),
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
     "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
     "A7: execution model (H2 = design/preliminary sizing; architecture-changing blockers 1-3; M16 scheduler)"),
    ("docs/decisions/verification/A5_BASELINE_VERIFICATION.json",
     "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
     "G0 governance baseline (verdict CLEAN; A5 may be pinned)"),
)

# Verified, merged deliverables and immutable snapshots consumed by this lane: pinned by sha256 at the base commit.
# A change to any of them fails verify_pins() and requires a deliberate re-pin (producer -> consumer chain).
DELIVERABLE_PINS = (
    ("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
     "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28",
     "A6 P1-PREG (verified, merged 3122bcd): the nine Phase-1 decision quantities P1DQ-* and their measurement chains"),
    ("docs/budgets/xe_ledger/xe_ledger_v1.json",
     "965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad",
     "A6 XE (verified, merged 732bbde): parametric Xe ledger; consumer of measured per-mode Xe"),
    ("docs/experiments/hardware/hardware_requirements_v1.json",
     "0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0",
     "W3 H-1/C-1 hardware definition (CI ids, planes, HW-* requirements, identity matrix, derived numbers)"),
    ("docs/experiments/hardware/snapshots/w4_instrumentation_definition_v1_at_fe2c05e.json",
     "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96",
     "W4 instrumentation definition v1-r2 immutable snapshot (INS-01..24, INS-P-01..12); byte-identical to "
     "docs/experiments/instrumentation/instrumentation_definition_v1.json at this base"),
    ("docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
     "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865",
     "W4 metrology measurement specification (MS-G / MS-M; A3/A4 standards)"),
    ("docs/experiments/capability_demo/capability_demo_prep_v1.json",
     "ba465206f3a9d7773e338e06dc9e98961c3a97d7f89357c2ed3a227f2a924e67",
     "W4 capability demonstration preparation CD-01..CD-07 and CD-P-* planning values"),
    ("docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json",
     "011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac",
     "S1a engineering gate (S1A-C1..C5, S1A-FW firewall classes)"),
    ("docs/experiments/s1_readiness/s1_readiness_conditions_v1.json",
     "1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1", "N4 S1-readiness gate (S1-C1..C8)"),
)

# Mutable drafts / modules consumed by value only (re-checked value-by-value by --verify-sources; never pinned).
PROVENANCE_INPUTS = (
    ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
     "W4 live file (values re-checked; the pinned snapshot is the authority)"),
    ("docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json",
     "W1 feed-state closure (MFC range requirement, sccm reference)"),
    ("docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json",
     "lane 25 minimum decisive experiment (S1a/S1b plan, thresholds, S_eff per mg/s)"),
    ("docs/architecture_comparison/experiment_package/experiment_package_v1.json",
     "experiment package (REQ-FAC-01..05, REQ-HW-01..08)"),
    ("abep_sim/constants.py", "RFP constants and physical constants (parsed with ast, never imported)"),
    ("abep_sim/arch_boundary.py", "bus_power_boundary_v1 component contract (referenced by name, never imported)"),
)

# Mutable governance files: named, NEVER pinned.
GOVERNANCE_NOT_PINNED = (
    "docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/runtime_state.json",
)

PENDING_LANES = (
    ("fo_preionizer_module_icd", "docs/interfaces/preionizer_module/",
     "PMI-xx items (A6 list): mechanical envelope + mounting datum, gas path, service-line routing, permitted "
     "magnetic disturbance, diagnostics, installation/removal reproducibility"),
    ("fo_subsystem_maturity_matrix", "docs/budgets/subsystem_maturity/", "M16 row ids and scheduler states"),
    ("fo_h2_1_hall_chamber_magnet", "docs/hardware/h2/h2_1_hall_chamber_magnet/",
     "H-1 channel geometry, exit OD, domain length, B_max, coil count/current, rear flange (IP-DN), fiducials"),
    ("fo_h2_2_cathode_integration", "docs/hardware/h2/h2_2_cathode_integration/",
     "C-1 mount position, keeper/heater ranges, cathode-tube TC and pyrometer view, near-cathode sampling inlet"),
    ("fo_h2_3_gas_path_plenum", "docs/hardware/h2/h2_3_gas_path_plenum/",
     "IP-UP location, gas isolator, feed-pressure/temperature ports, conductance (P_feed vs mdot), flight sensors"),
    ("fo_h2_4_ppu_bus", "docs/hardware/h2/h2_4_ppu_bus/",
     "per-component ledger efficiencies, PPU telemetry channel list, I_d ripple telemetry capability"),
    ("fo_h2_5_thermal_network", "docs/hardware/h2/h2_5_thermal_network/",
     "heat into the mount, module waste heat at IP-DN, thermocouple positions, thermal time constants"),
    ("fo_h2_7_mechanical_bom", "docs/hardware/h2/h2_7_mechanical_bom/",
     "masses on the stand per configuration, mounting interface, envelope"),
)


P1_UNFROZEN = ("UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability "
               "(docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal)")
XE_CONSUMER = "consumed by docs/budgets/xe_ledger/xe_ledger_v1.json (verified; parametric, nothing frozen)"


def _pending(key: str) -> str:
    for lane, path, _ in PENDING_LANES:
        if lane == key:
            return f"PENDING {path}"
    raise KeyError(f"unknown pending lane {key!r}")


# ---------------------------------------------------------------------------------------------------------------------
# Explicit inputs (every number used in a derivation). No defaults exist anywhere else in this script.
# ---------------------------------------------------------------------------------------------------------------------
def _inp(value, unit, evidence_class, basis, source, locator, note=None):
    d = {"value": value, "unit": unit, "evidence_class": evidence_class, "basis": basis, "source": source,
         "locator": locator}
    if note:
        d["note"] = note
    return d


A5P = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
W1P = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
W3P = "docs/experiments/hardware/hardware_requirements_v1.json"
W4P = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
CDP = "docs/experiments/capability_demo/capability_demo_prep_v1.json"
L25P = "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"
CONSTP = "abep_sim/constants.py"

INPUTS = {
    "K_B": _inp(1.380649e-23, "J K^-1", "assumed", "requirement", CONSTP, "K_B (exact SI value)"),
    "AMU": _inp(1.66053906660e-27, "kg", "measured", "requirement", CONSTP, "AMU (CODATA)"),
    "M_N2_u": _inp(28.0, "u", "assumed", "requirement", CONSTP, "M_SPECIES['N2'] = 28.0 * AMU (repository rounding)"),
    "M_O2_u": _inp(32.0, "u", "assumed", "requirement", CONSTP, "M_SPECIES['O2'] = 32.0 * AMU (repository rounding)"),
    "M_Xe_u": _inp(131.3, "u", "assumed", "requirement", CONSTP, "M_SPECIES['Xe'] = 131.3 * AMU (repository rounding)"),
    "Torr_Pa": _inp(133.32236842105263, "Pa Torr^-1", "assumed", "requirement", "definition",
                    "1 Torr = 101325/760 Pa (exact)"),
    "T_gas_K": _inp(300.0, "K", "assumed", "assumed", L25P,
                    "derived_numbers.S_eff_required_per_mgps source text 'T = 300.0 K' (gauge-wall gas temperature; "
                    "planning assumption shared with lane 25 and W4 derived.background_one_way_mass_flux)"),
    "p_b_planning_Torr": _inp([1.0e-5, 1.3e-5, 5.0e-5], "Torr", "assumed", "analog", "REF-DANKANICH2017",
                              "Sec. V p. 677 (5e-5 performance, 1.3e-5 near-field plume: early SPT-100 guidance) and "
                              "p. 678 (below 1e-5 needed to identify the SPT-100 thrust-slope change); xenon/SPT-100 "
                              "specific, used as planning scenarios only (same set as lane 25 section 12)"),
    "sccm_T0_K": _inp(273.15, "K", "assumed", "assumed", W1P, "design_input_inventory ground.sccm_reference "
                                                               "('273.15 K, 101325.0 Pa', PROPOSED there)"),
    "sccm_p0_Pa": _inp(101325.0, "Pa", "assumed", "assumed", W1P, "design_input_inventory ground.sccm_reference"),
    "mdot_anode_min_kgps": _inp(2.95480462098e-08, "kg s^-1", "model-derived", "derived", W1P,
                                "mfc_range_requirement.mdot_min_kgps (backflow-inclusive lower bracket; an "
                                "instrumentation range input, not a test point; A4: candidate range, not flight truth)"),
    "mdot_anode_max_kgps": _inp(3.14236387222e-06, "kg s^-1", "model-derived", "derived", W1P,
                                "mfc_range_requirement.mdot_max_kgps (no-backflow upper bound; A5 'delivered-flow "
                                "region (<= ~3.2 mg/s under H_RAM)')"),
    "mdot_O2_max_W1_kgps": _inp(1.39517895148e-06, "kg s^-1", "model-derived", "derived", W1P,
                                "mfc_range_requirement.O2_max_kgps (largest O2 flow over the closed W1 candidate cases; "
                                "the factorial grid corner w_O2 0.60 x mdot_max is larger and sets the O2 MFC path)"),
    "mdot_anode_max_accum_kgps": _inp(5.44676404518e-06, "kg s^-1", "model-derived", "derived", W1P,
                                      "mfc_range_requirement.mdot_max_with_accumulation_kgps (PROPOSED as MFC headroom "
                                      "only, finding FC-08)"),
    "w_O2_range": _inp([0.42, 0.60], "mass fraction", "model-derived", "allocation", A5P,
                       "phase1_branch_decision.test_matrix 'delivered O2 mass fraction 0.42-0.60' (air surrogate: "
                       "O + O2 supplied as O2, W3 HW-ENV-07)"),
    "mdot_xe_cathode_design_mgps": _inp(0.10, "mg s^-1", "assumed", "allocation", A5P,
                                        "xe_mass_allocation.cathode_flow_design_target_mg_s"),
    "mdot_xe_cathode_upper_mgps": _inp(0.15, "mg s^-1", "assumed", "allocation", A5P,
                                       "xe_mass_allocation.cathode_flow_experimental_upper_test_point_mg_s (test "
                                       "point only until the mass ledger shows it is affordable)"),
    "firing_hours_min_h": _inp(15000.0, "h", "assumed", "requirement", CONSTP, "RFPConstraints.ignition_hours"),
    "mfc_min_fraction_fs": _inp(0.2, "fraction of full scale", "assumed", "assumed", CDP,
                                "proposed_thresholds CD-P-MFC-MINFRAC (PROPOSED; owner decides at S1-C5)"),
    "mfc_accuracy_fs": _inp(0.01, "fraction of full scale (treated as 1 sigma)", "assumed", "analog", W4P,
                            "instruments INS-05 / derived.mfc_relative_u_by_setpoint_fraction (REF-SNYDER2017 "
                            "'typically 1% full scale'; treated as 1 sigma - verify the certificate's coverage)"),
    "u_mfc_grid": _inp([0.01, 0.05], "relative (1 sigma)", "assumed", "derived", W4P,
                       "derived.mfc_relative_u_by_setpoint_fraction '1.0' (0.01) and '0.2' (0.05): the relative MFC "
                       "term at full scale and at the CD-P-MFC-MINFRAC floor"),
    "thrust_min_mN": _inp(12.0, "mN", "assumed", "requirement", CONSTP, "RFPConstraints.thrust_min_mN"),
    "thrust_max_mN": _inp(25.0, "mN", "assumed", "requirement", CONSTP, "RFPConstraints.thrust_max_mN"),
    "power_max_W": _inp(1500.0, "W", "assumed", "requirement", CONSTP, "RFPConstraints.power_max_W"),
    "a5_thrust_target_mN": _inp([15.0, 22.0], "mN", "assumed", "allocation", A5P,
                                "allocations_and_requirements 'thrust operating target' 15-22 mN (allocation)"),
    "a5_pbus_allocation_W": _inp([1300.0, 1350.0], "W", "assumed", "allocation", A5P,
                                 "allocations_and_requirements 'bus-power design allocation' <= 1.30-1.35 kW"),
    "n_grid": _inp([4, 6, 8], "-", "assumed", "derived", W4P, "requirement_basis.lane25_by_n keys (lane-25 plan_by_n)"),
    "u_T_max_by_n": _inp({"4": 0.0049836144, "6": 0.0062695641, "8": 0.0073219142}, "relative (1 sigma, per reading)",
                         "model-derived", "derived", W4P, "requirement_basis.lane25_by_n.<n>.u_T_max (lane 25)"),
    "u_P_max_by_n": _inp({"4": 0.0049836144, "6": 0.0062695641, "8": 0.0073219142}, "relative (1 sigma, per reading)",
                         "model-derived", "derived", W4P, "requirement_basis.lane25_by_n.<n>.u_P_max (lane 25)"),
    "k_one_sided": _inp(1.64485, "-", "model-derived", "derived", W4P,
                        "derived.k_one_sided (I-ALPHA-ABS = 0.05, PROPOSED)"),
    "u_abs_planning": _inp(0.01, "relative (1 sigma)", "assumed", "assumed", W4P,
                           "proposed_thresholds I-U-ABS-T and I-U-ABS-P (PROPOSED; LOCK-2 value pending)"),
    "u_abs_grid": _inp([0.005, 0.01, 0.015, 0.02, 0.03, 0.05], "relative (1 sigma)", "assumed", "derived", W4P,
                       "derived.absolute_thrust_gate keys (planning grid)"),
    "I_d_bound_A": _inp(8.333333333, "A", "model-derived", "derived", W3P,
                        "derived_numbers.outputs.I_d_bound_envelope_max_A (P_max / min V_d; not a prediction of I_d)"),
    "V_d_rating_upper_V": _inp(350.0, "V", "assumed", "assumed", W3P,
                               "requirements HW-ENV-01 values.V_d_rating_upper_V (PROPOSED, HWQ-03)"),
    "I_d_noise_floor_frac": _inp(0.01, "fraction of I_d,ref", "assumed", "assumed", W4P,
                                 "proposed_thresholds I-U-ID-FLOOR (PROPOSED)"),
    "osc_band_Hz": _inp([1.0e3, 60.0e6], "Hz", "assumed", "analog", "REF-CHOUEIRI2001",
                        "abstract: oscillations in the 1 kHz - 60 MHz range reviewed (abstract-level only; band-by-band "
                        "values not read - verify)"),
    "echt_channel_length_m": _inp(0.086, "m", "inferred", "analog", "REF-MARCHIONI2020",
                                  "as recorded in CLAUDE.md 'Superseded / withdrawn' and docs/HISTORY.md 2026-09-26 "
                                  "(ECHT-N2 audit); published analog only, never a Vyovrinda design value"),
    "echt_channel_width_m": _inp(0.010, "m", "inferred", "analog", "REF-MARCHIONI2020",
                                 "as recorded in CLAUDE.md / docs/HISTORY.md 2026-09-26 (10 mm channel height); analog"),
    "echt_OD_m": _inp(0.100, "m", "inferred", "analog", "REF-MARCHIONI2020",
                      "as recorded in CLAUDE.md / docs/HISTORY.md 2026-09-26 ('100 mm OD'; channel radii are NOT "
                      "published per the ECHT-N2 audit, so OD = channel outer diameter is an inference); analog only"),
    "faraday_far_field_diameters": _inp(4.0, "channel diameters", "assumed", "analog", "REF-BROWN2017",
                                        "far field > 4 channel diameters (Table A1, as recorded by lane 25 M5)"),
    "gauge_min_distance_from_OD_m": _inp(1.0, "m", "assumed", "analog", "REF-DANKANICH2017",
                                         "p. 672: gauge near the wall at the exit plane, >= 0.6 chamber radii off the "
                                         "centreline and >= 1 m from the thruster outer diameter"),
    "gauge_min_offset_R": _inp(0.6, "chamber radii", "assumed", "analog", "REF-DANKANICH2017", "p. 672"),
    "u_inst_max_n4": _inp(0.0024918072, "ln-ratio (1 sigma, per installation)", "model-derived", "derived", W3P,
                          "derived_numbers.inputs.u_inst_max_n4 (lane 25 plan_by_n.4.u_inst_max)"),
    "theta_align_max_n4_deg": _inp(2.70440471, "deg", "model-derived", "derived", W3P,
                                   "derived_numbers.outputs.theta_align_max_n4_deg (cosine loss = one of five equal "
                                   "RSS shares, HW-SVC-03)"),
    "remount_K": _inp(6, "cycles", "assumed", "assumed", L25P, "thresholds T-S1-REMOUNT-CYCLES (PROPOSED)"),
    "remount_r": _inp(3, "readings per cycle", "assumed", "assumed", L25P, "thresholds T-S1-READINGS-PER-CYCLE (PROPOSED)"),
    "pb_elev_factor": _inp(2.0, "x base p_b", "assumed", "assumed", L25P, "thresholds T-PB-ELEV-FACTOR (PROPOSED)"),
    "B_res_2p45GHz_T": _inp(0.08752347556, "T", "model-derived", "derived", W3P,
                            "derived_numbers.outputs.B_res_ecr_2p45GHz_T (candidate frequency, not selected)"),
    "B_res_5p8GHz_T": _inp(0.2071984319, "T", "model-derived", "derived", W3P,
                           "derived_numbers.outputs.B_res_ecr_5p8GHz_T (candidate frequency, not selected)"),
    "calibrations_min": _inp(10, "calibrations before and after", "assumed", "analog", W3P,
                             "requirements HW-SVC-02 calibrations_before_min / calibrations_after_min "
                             "(REF-POLK2017 recommended practice)"),
    "cd_bz_maps": _inp(3, "maps per configuration", "assumed", "assumed", CDP, "proposed_thresholds CD-P-BZ-MAPS"),
    "cd_bz_cycles": _inp(3, "current cycles", "assumed", "assumed", CDP, "proposed_thresholds CD-P-BZ-CYCLES"),
    "ingestion_fraction_grid": _inp([0.01, 0.05, 0.10], "fraction of anode mass flow", "assumed", "assumed",
                                    "this lane (PROPOSED planning grid for the owner's T-PB-MAX decision)",
                                    "not a requirement; the owner sets T-PB-MAX at LOCK-1"),
    "A_ref_m2": _inp(0.01, "m^2", "assumed", "assumed", W4P,
                     "derived.background_one_way_mass_flux reporting unit 'per 100 cm^2 of exit area'"),
}

REQUIRED_INPUTS = tuple(INPUTS)


def _sig(x):
    """Round to 10 significant digits (stable text representation; recomputation compares exactly)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return x
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.10g}")


def _val(inputs: dict, key: str):
    if key not in inputs:
        raise KeyError(f"input {key!r} is missing; no default exists (CLAUDE.md rule 3)")
    v = inputs[key].get("value")
    if v is None:
        raise ValueError(f"input {key!r} has no value; cannot derive")
    return v


def _d(value, unit, how, note=None):
    out = {"value": _sig(value) if not isinstance(value, list) else [_sig(v) for v in value], "unit": unit,
           "evidence_class": "model-derived", "source": f"{SCRIPT_REL}: {how}"}
    if note:
        out["note"] = note
    return out


def _tkey(p):
    return f"{p:.1e} Torr"


def derive(inputs: dict) -> dict:
    """Recompute every derived number from ``inputs``. Raises on any missing input."""
    for k in REQUIRED_INPUTS:
        _val(inputs, k)
    kB = float(_val(inputs, "K_B"))
    amu = float(_val(inputs, "AMU"))
    T = float(_val(inputs, "T_gas_K"))
    torr = float(_val(inputs, "Torr_Pa"))
    m = {g: float(_val(inputs, f"M_{g}_u")) * amu for g in ("N2", "O2", "Xe")}
    pbs = [float(p) for p in _val(inputs, "p_b_planning_Torr")]
    mmin = float(_val(inputs, "mdot_anode_min_kgps"))
    mmax = float(_val(inputs, "mdot_anode_max_kgps"))
    macc = float(_val(inputs, "mdot_anode_max_accum_kgps"))
    w_lo, w_hi = (float(x) for x in _val(inputs, "w_O2_range"))
    xe_d = float(_val(inputs, "mdot_xe_cathode_design_mgps")) * 1e-6
    xe_u = float(_val(inputs, "mdot_xe_cathode_upper_mgps")) * 1e-6
    out: dict = {}

    # --- 1. effective pumping speed S_eff = Q / p_b, Q = (mdot / m) k_B T (REF-DANKANICH2017 Eq. 9 form, p. 673) ------
    def s_eff_Ls(mdot_by_gas: dict, p_torr: float) -> float:
        q = sum(md / m[g] for g, md in mdot_by_gas.items()) * kB * T
        return q / (p_torr * torr) * 1e3

    per = {}
    for g in ("N2", "O2", "Xe"):
        per[g] = {_tkey(p): _d(s_eff_Ls({g: 1e-6}, p), "L s^-1 per (mg s^-1)",
                               f"S_eff = (1 mg/s / m_{g}) k_B T / p_b, p_b = {p:g} Torr, T = T_gas_K") for p in pbs}
    out["S_eff_per_mgps"] = per

    cases = {
        "anode_N2_at_mdot_max": {"N2": mmax},
        "anode_surrogate_wO2_min_at_mdot_max": {"N2": (1 - w_lo) * mmax, "O2": w_lo * mmax},
        "anode_surrogate_wO2_max_at_mdot_max": {"N2": (1 - w_hi) * mmax, "O2": w_hi * mmax},
        "cathode_Xe_design": {"Xe": xe_d},
        "cathode_Xe_upper": {"Xe": xe_u},
        "total_N2_mdot_max_plus_Xe_upper": {"N2": mmax, "Xe": xe_u},
        "sensitivity_N2_at_mdot_max_with_accumulation": {"N2": macc},
    }
    tab = {}
    for name, flows in cases.items():
        desc = ", ".join(f"{g} {v * 1e6:.6g} mg/s" for g, v in flows.items())
        tab[name] = {_tkey(p): _d(s_eff_Ls(flows, p), "L s^-1", f"S_eff for {{{desc}}} at p_b = {p:g} Torr")
                     for p in pbs}
    out["S_eff_required"] = tab

    # --- 2. one-way background mass flux and ingestion scale (a SCALE, never a correction; W4 INS-08) ----------------
    def flux(g, p_torr):  # kg m^-2 s^-1 : p sqrt(m / (2 pi k T))
        return p_torr * torr * math.sqrt(m[g] / (2 * math.pi * kB * T))

    a_ref = float(_val(inputs, "A_ref_m2"))
    od = float(_val(inputs, "echt_OD_m"))
    wch = float(_val(inputs, "echt_channel_width_m"))
    a_echt = math.pi / 4 * (od ** 2 - (od - 2 * wch) ** 2)
    out["echt_analog_exit_annulus_m2"] = _d(a_echt, "m^2", "pi/4 (OD^2 - (OD - 2 w)^2), analog OD and width",
                                            "illustration only: published analog (inferred OD = channel OD); H-1 exit "
                                            "area is " + _pending("fo_h2_1_hall_chamber_magnet"))
    out["one_way_mass_flux_per_100cm2"] = {
        g: {_tkey(p): _d(flux(g, p) * a_ref * 1e6, "mg s^-1 per 100 cm^2", f"p_b sqrt(m_{g}/(2 pi k_B T)) x A_ref")
            for p in pbs} for g in ("N2", "O2")}
    ing = {}
    for aname, area in (("per_100cm2", a_ref), ("echt_analog_annulus", a_echt)):
        ing[aname] = {}
        for fname, fl in (("at_mdot_anode_min", mmin), ("at_mdot_anode_max", mmax)):
            ing[aname][fname] = {_tkey(p): _d(flux("N2", p) * area / fl, "-",
                                              f"N2 one-way mass flux x area / anode flow, p_b = {p:g} Torr")
                                 for p in pbs}
    out["ingestion_scale_N2"] = ing
    pb_for = {}
    for aname, area in (("per_100cm2", a_ref), ("echt_analog_annulus", a_echt)):
        pb_for[aname] = {}
        for f in _val(inputs, "ingestion_fraction_grid"):
            p_pa = float(f) * mmin / (area * math.sqrt(m["N2"] / (2 * math.pi * kB * T)))
            pb_for[aname][f"f={float(f):g}"] = _d(p_pa / torr, "Torr",
                                                   f"p_b at which the N2 ingestion scale equals f at mdot_anode_min")
    out["p_b_for_ingestion_fraction_at_mdot_min"] = pb_for

    # --- 3. MFC ranges per pure-gas path, overlapping-range count at the CD-P-MFC-MINFRAC floor -------------------------
    minfrac = float(_val(inputs, "mfc_min_fraction_fs"))
    paths = {
        "anode_total": (mmin, mmax),
        "N2_path": ((1 - w_hi) * mmin, mmax),  # pure-N2 Phase 1 reaches mdot_max
        "O2_path": (w_lo * mmin, w_hi * mmax),
    }
    mfc = {}
    for name, (lo, hi) in paths.items():
        td = hi / lo
        n_rng = math.ceil(math.log(td) / math.log(1 / minfrac) - 1e-12)
        mfc[name] = {"min": _d(lo * 1e6, "mg s^-1", f"{name} lower end"),
                     "max": _d(hi * 1e6, "mg s^-1", f"{name} upper end"),
                     "turndown": _d(td, "-", "max / min"),
                     "overlapping_ranges_min": {"value": n_rng, "unit": "ranges", "evidence_class": "model-derived",
                                                "source": f"{SCRIPT_REL}: ceil(ln(turndown) / ln(1 / "
                                                          f"CD-P-MFC-MINFRAC)) (each range used from its floor "
                                                          f"fraction to full scale)"}}
    out["mfc_paths"] = mfc

    # sccm conversion (W1 reference conditions)
    T0 = float(_val(inputs, "sccm_T0_K"))
    p0 = float(_val(inputs, "sccm_p0_Pa"))
    n_per_sccm = p0 * 1e-6 / 60.0 / (kB * T0)  # molecules s^-1 per sccm
    out["mgps_per_sccm"] = {g: _d(n_per_sccm * m[g] * 1e6, "mg s^-1 per sccm", f"p0 1e-6 m^3 / 60 s / (k_B T0) x m_{g}")
                            for g in ("N2", "O2", "Xe")}
    xe_mgps_per_sccm = n_per_sccm * m["Xe"] * 1e6
    fs_lo = xe_u * 1e6
    fs_hi = xe_d * 1e6 / minfrac
    acc = float(_val(inputs, "mfc_accuracy_fs"))
    hours = float(_val(inputs, "firing_hours_min_h"))
    m_xe_design = xe_d * hours * 3600.0
    out["xe_cathode_mfc"] = {
        "design_sccm": _d(xe_d * 1e6 / xe_mgps_per_sccm, "sccm Xe", "0.10 mg/s / (mg/s per sccm Xe)"),
        "upper_sccm": _d(xe_u * 1e6 / xe_mgps_per_sccm, "sccm Xe", "0.15 mg/s / (mg/s per sccm Xe)"),
        "full_scale_window_mgps": _d([fs_lo, fs_hi], "mg s^-1",
                                     "[upper test point, design / CD-P-MFC-MINFRAC]: both A5 points >= floor x FS"),
        "full_scale_window_sccm": _d([fs_lo / xe_mgps_per_sccm, fs_hi / xe_mgps_per_sccm], "sccm Xe", "as above"),
        "relative_u_at_design_over_fs_window": _d([acc * fs_lo / (xe_d * 1e6), acc * fs_hi / (xe_d * 1e6)],
                                                  "relative (1 sigma treated)",
                                                  "mfc_accuracy_fs x FS / 0.10 mg/s at the two FS-window ends"),
        "m_xe_design_over_firing_hours_kg": _d(m_xe_design, "kg", "0.10 mg/s x 15,000 h (cross-check of A5 5.4 kg)"),
        "m_xe_upper_over_firing_hours_kg": _d(xe_u * hours * 3600.0, "kg", "0.15 mg/s x 15,000 h (A5 8.1 kg)"),
        "m_xe_1sigma_from_flow_u_kg": _d([acc * fs_lo / (xe_d * 1e6) * m_xe_design,
                                          acc * fs_hi / (xe_d * 1e6) * m_xe_design], "kg",
                                         "relative flow u x design-term mass (fully correlated scale error)"),
    }

    # mixture O2 mass fraction uncertainty w(1-w) sqrt(u_N2^2 + u_O2^2) (same form as W4 mass_fraction_u)
    mix = {}
    for w in (w_lo, w_hi):
        mix[f"w={w:g}"] = {f"u={u:g}": _d(w * (1 - w) * math.sqrt(2) * u, "mass fraction (1 sigma, absolute)",
                                          f"w(1-w) sqrt(u_N2^2 + u_O2^2), u_N2 = u_O2 = {u:g}")
                           for u in _val(inputs, "u_mfc_grid")}
    out["o2_mass_fraction_u"] = mix

    # --- 4. thrust stand -------------------------------------------------------------------------------------------------
    k = float(_val(inputs, "k_one_sided"))
    tmin = float(_val(inputs, "thrust_min_mN"))
    tmax = float(_val(inputs, "thrust_max_mN"))
    pmax = float(_val(inputs, "power_max_W"))
    uT = _val(inputs, "u_T_max_by_n")
    uP = _val(inputs, "u_P_max_by_n")
    ns = [str(n) for n in _val(inputs, "n_grid")]
    out["thrust_span_upper_mN_by_u_abs"] = {f"u={u:g}": _d(tmax / (1 - k * u), "mN",
                                                            "T_max / (1 - k_one_sided u): the smallest reading that "
                                                            "passes the 25 mN gate (W4 lower_gate form)")
                                            for u in _val(inputs, "u_abs_grid")}
    ua = float(_val(inputs, "u_abs_planning"))
    out["thrust_span_upper_mN_planning"] = _d(tmax / (1 - k * ua), "mN", "at u_abs_planning (I-U-ABS-T)")
    out["sigma_T_at_T_min_uN_by_n"] = {f"n={n}": _d(float(uT[n]) * tmin * 1e3, "uN (1 sigma, per reading)",
                                                    "u_T_max[n] x thrust_min") for n in ns}
    out["sigma_T_at_T_max_uN_by_n"] = {f"n={n}": _d(float(uT[n]) * tmax * 1e3, "uN (1 sigma, per reading)",
                                                    "u_T_max[n] x thrust_max") for n in ns}
    out["resolution_step_max_uN_by_n"] = {f"n={n}": _d(float(uT[n]) * tmin * 1e3, "uN",
                                                       "q <= sigma_T target at thrust_min (PROPOSED rule)") for n in ns}
    out["quantization_variance_inflation_at_q_eq_sigma"] = _d(math.sqrt(1 + 1 / 12), "-",
                                                              "sqrt(1 + (q/sqrt(12))^2 / sigma^2) at q = sigma "
                                                              "(uniform quantization, GUM Type B)")
    out["sigma_T_abs_at_T_min_uN_planning"] = _d(ua * tmin * 1e3, "uN (1 sigma)", "u_abs_planning x thrust_min")
    out["u_T_over_Pbus_per_reading_by_n"] = {f"n={n}": _d(math.hypot(float(uT[n]), float(uP[n])), "relative (1 sigma)",
                                                          "sqrt(u_T^2 + u_P^2), independent channels") for n in ns}

    # --- 5. bus power ------------------------------------------------------------------------------------------------------
    alloc = [float(x) for x in _val(inputs, "a5_pbus_allocation_W")]
    out["sigma_Pbus_W_by_n"] = {f"n={n}": {f"P={p:g} W": _d(float(uP[n]) * p, "W (1 sigma, per reading)",
                                                              "u_P_max[n] x P") for p in alloc + [pmax]} for n in ns}
    out["Pbus_gate_pass_max_W_planning"] = _d(pmax / (1 + k * ua), "W", "P_max / (1 + k_one_sided u_abs_planning)")

    # --- 6. discharge current / oscillation ---------------------------------------------------------------------------------
    band = [float(x) for x in _val(inputs, "osc_band_Hz")]
    out["exploratory_sampling_min_Sps"] = _d(2 * band[1], "samples s^-1",
                                             "Nyquist: 2 x upper edge of the literature planning band")

    # --- 7. geometry-scaled facility preferences (analog illustration) -------------------------------------------------------
    out["faraday_far_field_radius_min_m_analog"] = _d(float(_val(inputs, "faraday_far_field_diameters")) * od, "m",
                                                      "4 x channel OD (analog OD; conservative vs mean diameter)")
    out["chamber_radius_for_wall_gauge_min_m_analog"] = _d(float(_val(inputs, "gauge_min_distance_from_OD_m")) + od / 2,
                                                           "m", "1 m from thruster OD to a wall gauge in the exit "
                                                                "plane: R >= 1 m + OD/2 (analog OD)")
    out["fixture_heat_load_upper_bound_W"] = _d(pmax, "W", "every watt crossing the bus boundary ends as beam power or "
                                                           "heat: heat into H-1 + mount <= P_bus <= P_max (bound)")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Content (hand-written, PROPOSED/PRELIMINARY; every number points at an input or a derived key)
# ---------------------------------------------------------------------------------------------------------------------
P1DQ = (
    ("P1DQ-SUST", "sustainment", ["DQ-SUST", "DQ-KNEE"]),
    ("P1DQ-TPBUS", "T/P_bus", ["DQ-RARCH"]),
    ("P1DQ-ETAU", "eta_u", []),
    ("P1DQ-ENVW", "operating-envelope width", ["DQ-SUST", "DQ-KNEE"]),
    ("P1DQ-IGN", "ignition/restart behaviour", []),
    ("P1DQ-STAB", "stability/oscillation", []),
    ("P1DQ-TABS", "absolute thrust compatibility", ["DQ-TABS"]),
    ("P1DQ-PBUS", "full bus-power compatibility", ["DQ-PBUS"]),
    ("P1DQ-NOXE", "no continuous Xe augmentation", []),
)


def _p(pid, name, value, units, basis, source, evidence_class, status, flight, applies_to, note=None):
    d = {"id": pid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status, "flight_classification": flight,
         "applies_to": applies_to}
    if note:
        d["note"] = note
    return d


def _dv(der: dict, *path):
    node = der
    for p in path:
        node = node[p]
    return node["value"]


def design_parameters(der: dict) -> list:
    G, T, F = "GROUND/FACILITY-ONLY", "H-1 TEST-ARTICLE-ONLY", "FLIGHT-REPRESENTATIVE"
    PR = "PRELIMINARY"
    P1 = P1_UNFROZEN
    H1 = _pending("fo_h2_1_hall_chamber_magnet")
    H2 = _pending("fo_h2_2_cathode_integration")
    H3 = _pending("fo_h2_3_gas_path_plenum")
    H4 = _pending("fo_h2_4_ppu_bus")
    H5 = _pending("fo_h2_5_thermal_network")
    H7 = _pending("fo_h2_7_mechanical_bom")
    ICD = _pending("fo_preionizer_module_icd")
    XE = XE_CONSUMER
    ns = ("n=4", "n=6", "n=8")
    rows = [
        # ---- thrust --------------------------------------------------------------------------------------------------
        _p("H26-01", "thrust-stand calibrated span, lower end", 0.0, "mN", "requirement",
           "W4 INS-01 range note ('from the knee-scan extinction end'); lane 25 knee scan runs to extinction", "assumed",
           PR, G, ["SVC-1", "H-1 mount"], "the stand must read through the knee and extinction to zero thrust"),
        _p("H26-02", "thrust-stand calibrated span, upper end (minimum)",
           _dv(der, "thrust_span_upper_mN_planning"), "mN", "derived",
           "derived.thrust_span_upper_mN_planning (RFP 25 mN, W4 k_one_sided, I-U-ABS-T planning 0.01); grid in "
           "derived.thrust_span_upper_mN_by_u_abs", "model-derived", P1 + " (LOCK-2 absolute uncertainty)", G,
           ["SVC-1", "H-1 mount"],
           "REF-POLK2017: calibration forces span the expected range; the span must include the smallest reading "
           "that passes the 25 mN capability gate at the LOCK-2 u_abs (HWQ-10 decides whether 25 mN is also gated "
           "inside P_bus < 1.5 kW)"),
        _p("H26-03", "thrust per-reading repeatability target at 12 mN (1 sigma)",
           {k: _dv(der, "sigma_T_at_T_min_uN_by_n", k) for k in ns}, "uN", "derived",
           "derived.sigma_T_at_T_min_uN_by_n (lane 25 u_T_max via W4 requirement_basis)", "model-derived",
           P1 + " (n fixed at LOCK-2)", G, ["SVC-1"],
           "W4 INS-01 feasibility AT_RISK: achievability TBD - requires S1b"),
        _p("H26-04", "thrust read-out resolution step (maximum)",
           {k: _dv(der, "resolution_step_max_uN_by_n", k) for k in ns}, "uN", "derived",
           "PROPOSED rule q <= sigma_T target; quantization then inflates the per-reading sigma by "
           "derived.quantization_variance_inflation_at_q_eq_sigma", "model-derived", PR, G, ["SVC-1"]),
        _p("H26-05", "absolute (traceable) thrust uncertainty at 12 mN (1 sigma, planning)",
           _dv(der, "sigma_T_abs_at_T_min_uN_planning"), "uN", "derived",
           "W4 I-U-ABS-T 0.01 (PROPOSED) x RFP 12 mN", "model-derived", P1 + " (LOCK-2 u_abs)", G, ["SVC-1"],
           "traceability per A4 force_DC_RF_traceability: SI-traceable through an ISO/IEC 17025 accredited scope; no "
           "invented class"),
        _p("H26-06", "in-situ calibrations before and after each operating sequence (minimum)",
           INPUTS["calibrations_min"]["value"], "calibrations", "analog",
           "W3 HW-SVC-02; REF-POLK2017 (minimum of ten before and ten after)", "assumed", PR, G, ["SVC-1"]),
        _p("H26-07", "T/P_bus per-reading combined relative uncertainty (1 sigma)",
           {k: _dv(der, "u_T_over_Pbus_per_reading_by_n", k) for k in ns}, "relative", "derived",
           "derived.u_T_over_Pbus_per_reading_by_n", "model-derived", P1 + " (LOCK-2)", G, ["SVC-1", "PS-C"]),
        _p("H26-08", "sustained-thrust dwell (hold time) and its zero-drift allowance", None, "s", "pending",
           "W4 open owner decision 'dwell (hold time) for sustained >= 12 mN'", "assumed",
           "TBD - requires the owner hold-time decision and the S1b thermal time constants (T-SETTLE)", G, ["SVC-1"]),
        # ---- power ---------------------------------------------------------------------------------------------------
        _p("H26-09", "bus-power channel set at the bus-boundary-equivalent point",
           "hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, "
           "housekeeping; + rf_source (rf_hall); + ecr_source, ecr_magnet (ecr_hall)", "-", "requirement",
           "abep_sim/arch_boundary.py COMMON_COMPONENTS / PREIONIZER_COMPONENTS (BOUNDARY_VERSION "
           "bus_power_boundary_v1); W4 bus_power_channels", "assumed", PR, G, ["PS-C", "PIM-RF", "PIM-ECR"],
           "lab: load-plane V and I per present consumer (INS-02), net RF/microwave power at the load plane (INS-03); "
           "compressor ABSENT_IN_LAB (reconstructed, never zero); flow_control and housekeeping LEDGER_INPUT"),
        _p("H26-10", "per-channel power repeatability at the A5 bus allocation and at the RFP ceiling (1 sigma)",
           {k: {kk: vv["value"] for kk, vv in der["sigma_Pbus_W_by_n"][k].items()} for k in ns}, "W", "derived",
           "derived.sigma_Pbus_W_by_n (lane 25 u_P_max; A5 1.30-1.35 kW allocation; RFP 1.5 kW)", "model-derived",
           P1 + " (n fixed at LOCK-2)", G, ["PS-C"]),
        _p("H26-11", "ledger efficiencies converting load-plane power to P_bus", None, "-", "pending",
           "bus_power_boundary_v1: P_bus = sum_c P_load,c / eta_c (explicit, no defaults)", "assumed",
           H4 + " (LOCK-1 ledger inputs)", F, ["PS-C"],
           "until they exist the lab P_bus is PARTIAL_BOUNDARY (necessary, not sufficient) - W4 INS-02 feasibility"),
        _p("H26-12", "P_bus gate: largest measured P_bus that passes < 1.5 kW (planning)",
           _dv(der, "Pbus_gate_pass_max_W_planning"), "W", "derived",
           "derived.Pbus_gate_pass_max_W_planning (W4 I-U-ABS-P 0.01, k_one_sided)", "model-derived",
           P1 + " (LOCK-2 u_abs)", G, ["PS-C"]),
        # ---- discharge current / oscillation --------------------------------------------------------------------------
        _p("H26-13", "discharge-current DC channel range (minimum upper end)", INPUTS["I_d_bound_A"]["value"], "A",
           "derived", "W3 derived_numbers.outputs.I_d_bound_envelope_max_A (P_max / min V_d; a bound, not an I_d "
                      "prediction)", "model-derived",
           "TBD - requires the transient margin (W3 HW-ENV-02: supply protection design and S1 transients)", G,
           ["PS-C"]),
        _p("H26-14", "discharge-voltage channel range (minimum upper end)", INPUTS["V_d_rating_upper_V"]["value"], "V",
           "assumed", "W3 HW-ENV-01 V_d_rating_upper_V (PROPOSED, HWQ-03)", "assumed", PR, G, ["PS-C"]),
        _p("H26-15", "I_d offset + noise floor within the extinction window (1 sigma)",
           INPUTS["I_d_noise_floor_frac"]["value"], "fraction of I_d,ref", "assumed", "W4 I-U-ID-FLOOR (PROPOSED)",
           "assumed", P1 + " (I_d,ref and window from S1b)", G, ["PS-C"]),
        _p("H26-16", "exploratory I_d(t) acquisition: band and minimum sampling rate for the S1b spectrum",
           {"band_Hz": INPUTS["osc_band_Hz"]["value"], "sampling_min_Sps": _dv(der, "exploratory_sampling_min_Sps")},
           "Hz / samples s^-1", "analog",
           "REF-CHOUEIRI2001 abstract (1 kHz - 60 MHz reviewed; verify band edges); Nyquist in "
           "derived.exploratory_sampling_min_Sps", "assumed",
           "TBD - requires the S1b I_d spectrum on HW-0 (score-bearing band and rate fixed at LOCK-2; W4 INS-04)", G,
           ["PS-C"], "if the exploratory chain cannot reach the upper edge, the band actually covered is recorded; no "
                     "band is claimed as sufficient before S1b"),
        # ---- flows ---------------------------------------------------------------------------------------------------
        _p("H26-17", "anode total-flow range and turndown",
           {"min_mgps": _dv(der, "mfc_paths", "anode_total", "min"), "max_mgps": _dv(der, "mfc_paths", "anode_total", "max"),
            "turndown": _dv(der, "mfc_paths", "anode_total", "turndown"),
            "overlapping_ranges_min": der["mfc_paths"]["anode_total"]["overlapping_ranges_min"]["value"]},
           "mg s^-1 / - / ranges", "derived", "W1 mfc_range_requirement; derived.mfc_paths.anode_total (A4: 'at least "
                                               "three overlapping ranges per gas path')", "model-derived",
           PR, G, ["FS-C"], "candidate range, not flight truth (A4 DI_1_4); registered test points stay TBD from W1/LOCK-1"),
        _p("H26-18", "N2 pure-gas MFC path range and overlapping-range count",
           {"min_mgps": _dv(der, "mfc_paths", "N2_path", "min"), "max_mgps": _dv(der, "mfc_paths", "N2_path", "max"),
            "turndown": _dv(der, "mfc_paths", "N2_path", "turndown"),
            "overlapping_ranges_min": der["mfc_paths"]["N2_path"]["overlapping_ranges_min"]["value"]},
           "mg s^-1 / - / ranges", "derived", "derived.mfc_paths.N2_path (one MFC per pure gas, W4 INS-05; w_O2 0.42-0.60 "
                                               "A5; pure-N2 Phase 1 to mdot_max)", "model-derived", PR, G, ["FS-C"]),
        _p("H26-19", "O2 pure-gas MFC path range and overlapping-range count",
           {"min_mgps": _dv(der, "mfc_paths", "O2_path", "min"), "max_mgps": _dv(der, "mfc_paths", "O2_path", "max"),
            "turndown": _dv(der, "mfc_paths", "O2_path", "turndown"),
            "overlapping_ranges_min": der["mfc_paths"]["O2_path"]["overlapping_ranges_min"]["value"]},
           "mg s^-1 / - / ranges", "derived", "derived.mfc_paths.O2_path", "model-derived", PR, G, ["FS-C"],
           "every O2-wetted MFC and line is O2-cleaned (W3 HW-FS-07). The upper end is the factorial corner "
           "w_O2 0.60 x mdot_max (A5 sweeps mdot x x_O2 jointly); the largest O2 flow in the closed W1 cases is "
           f"{INPUTS['mdot_O2_max_W1_kgps']['value'] * 1e6:.4g} mg/s (W1 O2_max_kgps)"),
        _p("H26-20", "air-surrogate O2 mass-fraction set range and its 1 sigma from the flow ratio",
           {"w_O2_range": INPUTS["w_O2_range"]["value"],
            "u_w_abs": {w: {u: v["value"] for u, v in d.items()} for w, d in der["o2_mass_fraction_u"].items()}},
           "mass fraction", "derived", "A5 test_matrix; derived.o2_mass_fraction_u (W4 mass_fraction_u form)",
           "model-derived", PR, G, ["FS-C"]),
        _p("H26-21", "Xe cathode MFC capability and full-scale window",
           {"design_mgps": INPUTS["mdot_xe_cathode_design_mgps"]["value"],
            "upper_test_point_mgps": INPUTS["mdot_xe_cathode_upper_mgps"]["value"],
            "design_sccm": _dv(der, "xe_cathode_mfc", "design_sccm"), "upper_sccm": _dv(der, "xe_cathode_mfc", "upper_sccm"),
            "full_scale_window_mgps": _dv(der, "xe_cathode_mfc", "full_scale_window_mgps"),
            "full_scale_window_sccm": _dv(der, "xe_cathode_mfc", "full_scale_window_sccm")},
           "mg s^-1 / sccm Xe", "allocation", "A5 xe_mass_allocation; derived.xe_cathode_mfc", "model-derived",
           H2 + " (C-1 flow path)", G, ["C-1", "FS-C"],
           "the lab MFC is ground-only; the flight Xe metering telemetry is the flight-representative counterpart"),
        _p("H26-22", "Xe cathode flow 1 sigma at 0.10 mg/s and the implied Xe-mass 1 sigma over 15,000 h",
           {"relative_u": _dv(der, "xe_cathode_mfc", "relative_u_at_design_over_fs_window"),
            "m_xe_1sigma_kg": _dv(der, "xe_cathode_mfc", "m_xe_1sigma_from_flow_u_kg"),
            "m_xe_design_kg": _dv(der, "xe_cathode_mfc", "m_xe_design_over_firing_hours_kg")},
           "relative / kg", "derived", "derived.xe_cathode_mfc (1 % FS typical accuracy, REF-SNYDER2017 via W4; verify "
                                       "certificate)", "model-derived", XE + " (consumer of the measured cathode term)",
           G, ["C-1", "FS-C"]),
        _p("H26-23", "Xe anode start / transition flow range", None, "mg s^-1", "pending",
           "W3 HW-ENV-03 xe_start_flow_range (lane-14 start parameters all TBD)", "assumed",
           "TBD - requires the lane-14 start parameters and " + H3, G, ["FS-C"]),
        _p("H26-24", "Xe anode flow at every atmospheric Hall reading", 0.0, "mg s^-1", "requirement",
           "A5 operating_modes.rules (continuous Xe support of the main discharge is not a nominal mode); A6 decision "
           "quantity 'no continuous Xe augmentation'", "assumed", PR, G, ["FS-C"],
           "verified per reading by the Xe-anode valve-closed state AND the Xe-anode MFC reading inside its zero band "
           "(zero band from the S1a MFC calibration); every Xe-consuming mode is logged with its duration"),
        # ---- pressures -----------------------------------------------------------------------------------------------
        _p("H26-25", "feed pressure at IP-UP / manifold / module source chamber (range)", None, "Pa", "pending",
           "W3 HW-ENV-04, HW-FS-04; W1 flight setpoint ladder 0.1-0.3 Pa at the valve outlet (PROPOSED there) as the "
           "reference band", "assumed", H3 + " (gas-path conductance: ground P_feed follows mdot)", F,
           ["FS-C", "PIM-0", "PIM-RF", "PIM-ECR"],
           "measured covariate, never matched by adjustment unless the owner decides so (DI-1.9)"),
        _p("H26-26", "feed temperature at IP-UP", None, "K", "pending", "W3 HW-ENV-04 T_feed_range; W1 T_feed_ground",
           "assumed", "TBD - requires owner decision DI-1.10 (feed-gas temperature conditioning)", F, ["FS-C"]),
        _p("H26-27", "maximum base background pressure for a scoreable Hall-on reading (T-PB-MAX)",
           {"planning_scenarios_Torr": INPUTS["p_b_planning_Torr"]["value"],
            "p_b_for_ingestion_fraction_at_mdot_min_Torr": {
                a: {f: v["value"] for f, v in d.items()} for a, d in der["p_b_for_ingestion_fraction_at_mdot_min"].items()}},
           "Torr", "pending", "lane 25 T-PB-MAX (TBD, owner at LOCK-1); REF-DANKANICH2017 Sec. V (xenon/SPT-100, "
                               "'insufficient ... for absolute requirements', p. 678)", "assumed",
           "TBD - requires the owner decision at LOCK-1 from the facility specification", G, [],
           "the ingestion-scale columns are this lane's planning aid (PROPOSED fractions), never a correction"),
        _p("H26-28", "required effective pumping speed at the delivered-flow upper end (N2 3.14 mg/s + Xe cathode 0.15 mg/s)",
           {p: v["value"] for p, v in der["S_eff_required"]["total_N2_mdot_max_plus_Xe_upper"].items()}, "L s^-1",
           "derived", "derived.S_eff_required (REF-DANKANICH2017 Eq. 9 form S = Q/(p - p_base), p_base neglected)",
           "model-derived", "TBD - requires T-PB-MAX (owner, LOCK-1) and the facility choice (S1-C7 / S1A-C5)", G, []),
        _p("H26-29", "N2 ingestion scale at the lowest candidate anode flow (analog exit annulus)",
           {p: v["value"] for p, v in der["ingestion_scale_N2"]["echt_analog_annulus"]["at_mdot_anode_min"].items()},
           "fraction of anode mass flow", "derived",
           "derived.ingestion_scale_N2 (one-way flux x analog area / anode flow; W4 INS-08 'a scale, not a correction')",
           "model-derived", H1 + " (H-1 exit area replaces the analog)", G, [],
           "the scale is largest exactly where A7 blocker 1 is decided (low flow); p_b is logged with every knee reading"),
        _p("H26-30", "background-gauge placement and reading rule",
           {"offset_min_chamber_radii": INPUTS["gauge_min_offset_R"]["value"],
            "distance_from_thruster_OD_min_m": INPUTS["gauge_min_distance_from_OD_m"]["value"],
            "sampling_min_Hz": 10, "average_s": 3, "settle_after_flow_change_min": 2, "flow_change_threshold": 0.10},
           "-", "analog", "REF-DANKANICH2017 pp. 672-673 (accessed by this lane 2026-09-29: placement p. 672; >= 10 Hz, 3 s averages, no reading within 2 min of a > 10 % flow change pp. 672-673); experiment package REQ-FAC-03", "assumed", PR, G, [],
           "calibrated on N2 (the industry-standard gas, p. 670) and on the O2/N2 mixture (REQ-FAC-03 TBD)"),
        _p("H26-31", "elevated-p_b capability for the S5 facility-effect check",
           {"factor": INPUTS["pb_elev_factor"]["value"], "injection_distance_min_m": 2.0}, "x base p_b / m", "analog",
           "lane 25 T-PB-ELEV-FACTOR; experiment package REQ-FAC-02 (REF-DANKANICH2017 Sec. IV.B)", "assumed", PR, G, []),
        _p("H26-32", "chamber radius that allows the preferred wall-gauge position (analog illustration)",
           _dv(der, "chamber_radius_for_wall_gauge_min_m_analog"), "m", "derived",
           "derived.chamber_radius_for_wall_gauge_min_m_analog (REF-DANKANICH2017 p. 672; analog OD)", "model-derived",
           H1 + " (H-1 OD)", G, [],
           "a preference, not a hard requirement: p. 672 gives the alternative of a gauge >= 2 m downstream"),
        # ---- B field -------------------------------------------------------------------------------------------------
        _p("H26-33", "B(z) map extent (probe path from beyond the exit plane to the anode face along the mean radius)",
           None, "m", "pending", "W3 HW-H1-08 domain_length TBD (lane 17 geometry_interface)", "assumed",
           H1 + " (channel length, mean radius, domain length)", T, ["H-1", "MC-1"],
           "reachable with any module installed (probe enters from downstream; no module port needed)"),
        _p("H26-34", "gaussmeter range",
           {"hall_channel": "PENDING H2-1 B_max", "ecr_resonance_zone_if_mapped_T": [INPUTS["B_res_2p45GHz_T"]["value"],
                                                                                    INPUTS["B_res_5p8GHz_T"]["value"]]},
           "T", "derived", "W3 derived B_res_ecr (2.45 / 5.8 GHz candidates, frequency not selected); ECR zone mapping "
                           "belongs to the PIM-ECR annex", "model-derived", H1 + " and " + ICD, G, ["MC-1", "PIM-ECR"]),
        _p("H26-35", "B(z) map uncertainty", None, "T", "pending", "W3 HW-MC-03 bz_uncertainty; W4 INS-09", "assumed",
           "TBD - requires the INV-B3 tolerance (HWQ-04) and the W5 B(z) comparison tolerance", G, ["MC-1"]),
        _p("H26-36", "B(z) maps per configuration and coil-current cycles (S1a repeatability)",
           {"maps": INPUTS["cd_bz_maps"]["value"], "current_cycles": INPUTS["cd_bz_cycles"]["value"]}, "-", "assumed",
           "W4 CD-05 (CD-P-BZ-MAPS, CD-P-BZ-CYCLES, PROPOSED)", "assumed", PR, G, ["MC-1"]),
        # ---- species / energy ----------------------------------------------------------------------------------------
        _p("H26-37", "Faraday far-field arc radius (minimum; analog illustration)",
           _dv(der, "faraday_far_field_radius_min_m_analog"), "m", "derived",
           "derived.faraday_far_field_radius_min_m_analog (REF-BROWN2017 via lane 25: > 4 channel diameters)",
           "model-derived", H1 + " (H-1 channel diameter)", G, []),
        _p("H26-38", "ExB accelerating bias for resolving m/q 14, 16, 28, 32 at low energy", None, "V", "pending",
           "REF-ROVEY2025 via lane 25 / W4 INS-13", "assumed",
           "TBD - requires the ExB probe design and the W5 species-fraction tolerance", G, []),
        _p("H26-39", "eta_u measured inputs (operational definition P1DQ-ETAU, lane-06 metric M3)",
           "I_b (INS-15 far-field Faraday), Omega_j and q_j (INS-13 ExB), m_dot_prop and m_dot_c (INS-05); "
           "INS-14 RPA supporting; p_b (INS-08) for the charge-exchange correction", "-", "requirement",
           "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json decision_quantities P1DQ-ETAU "
           "measurement_chain (verified, pinned)", "assumed", P1, G, [],
           "eta_u needs INS-13 and INS-15, both AT_RISK in W4: this is the weakest link of the measurement chain "
           "(a test-readiness risk, not an architecture veto)"),
        # ---- fixture -------------------------------------------------------------------------------------------------
        _p("H26-40", "configuration-change procedure: H-1 stays mounted, only the module between IP-UP and IP-DN is "
                     "exchanged", True, "-", "assumed", "W3 HW-SVC-04 (PROPOSED; owner HWQ-01)", "assumed", PR, G,
           ["H-1 mount", "PIM-0", "PIM-RF", "PIM-ECR"]),
        _p("H26-41", "module carrier: kinematic (exactly-constrained, 6-constraint) seat on the stand moving platform",
           "3-point kinematic seat (PROPOSED concept)", "-", "assumed",
           "engineering practice (assumed); interface dimensions and datum from the pre-ionizer ICD", "assumed",
           ICD + " (mechanical envelope, mounting datum, installation/removal reproducibility item)", G,
           ["PIM-0", "PIM-RF", "PIM-ECR", "SVC-1"]),
        _p("H26-42", "module weight path", "carried by the module carrier; IP-DN joint is a seal/gas and alignment "
                                           "interface only", "-", "assumed",
           "this lane (PROPOSED); W3 HW-PIM-01 same flange pattern, seals and torque in every module", "assumed",
           ICD, G, ["PIM-0", "PIM-RF", "PIM-ECR", "H-1"]),
        _p("H26-43", "mass on the stand moving platform per configuration", None, "kg", "pending",
           "W4 tbd_register 'thrust range and mass on stand per configuration'", "assumed", H7 + " and " + ICD, G,
           ["H-1", "C-1", "MC-1", "PIM-0", "PIM-RF", "PIM-ECR"]),
        _p("H26-44", "heat load into H-1 + mount (upper bound for stand thermal design)",
           _dv(der, "fixture_heat_load_upper_bound_W"), "W", "derived",
           "derived.fixture_heat_load_upper_bound_W (RFP P_bus ceiling; a bound, not an estimate)", "model-derived",
           H5 + " (conduction share into the mount)", G, ["H-1 mount"],
           "REF-POLK2017: thermal shrouds / active cooling of critical stand components; thermally isolated mount"),
        _p("H26-45", "electrical isolation of H-1 from the stand and facility ground (rating)",
           INPUTS["V_d_rating_upper_V"]["value"], "V", "assumed",
           "W3 HW-ELEC-01 (thruster floats), HW-ENV-01 rating; margin as HW-FS-06 / HW-ELEC-05", "assumed",
           "TBD - requires the owner isolation margin and the HW-ELEC-05 test voltage", G, ["H-1 mount", "SVC-1"]),
        _p("H26-46", "non-ferromagnetic exclusion zone around MC-1 (fixture, fasteners, calibrator)", None, "m",
           "pending", "W3 HW-MC-12, HW-PIM-03; REF-POLK2017 non-ferrous stand materials, magnetic tare", "assumed",
           H1 + " (MC-1 magnetostatic model) and the INV-B3 tolerance (HWQ-04)", G, ["MC-1", "SVC-1"]),
        _p("H26-47", "thrust-axis alignment change per installation (one RSS share, cosine only)",
           INPUTS["theta_align_max_n4_deg"]["value"], "deg", "derived", "W3 derived theta_align_max_n4_deg",
           "model-derived", PR, G, ["H-1 mount"],
           "with H26-40 adopted a module exchange should not move the H-1 axis at all; the alignment reference reading "
           "(fixture FX-07) records it"),
        _p("H26-48", "installation reproducibility of ln(T/P_bus) and the qualification series",
           {"u_inst_max_n4": INPUTS["u_inst_max_n4"]["value"], "K_cycles": INPUTS["remount_K"]["value"],
            "r_readings": INPUTS["remount_r"]["value"]}, "ln-ratio / - / -", "derived",
           "W3 HW-SVC-03 (lane 25 u_inst,max n = 4); lane 25 T-S1-REMOUNT-CYCLES / T-S1-READINGS-PER-CYCLE (PROPOSED)",
           "model-derived", P1 + " (n and u_inst at LOCK-2)", G, ["H-1 mount", "PIM-0", "SVC-1"]),
        _p("H26-49", "service-line bundle inventory (SVC-1)", "see fixture.service_line_bundle", "-", "assumed",
           "W3 HW-SVC-01; this lane's inventory", "assumed",
           H1 + ", " + H2 + " and " + ICD + " (line counts)", G, ["SVC-1"]),
        _p("H26-50", "flight telemetry subset", "see ground_vs_flight (flight_telemetry_subset = true)", "-", "assumed",
           "bus_power_boundary_v1 housekeeping definition (sensors + telemetry interface inside the boundary)",
           "assumed", H4 + " (PPU telemetry) and the control/FDIR row", F, ["PS-C", "FS-C", "C-1", "MC-1"]),
        _p("H26-51", "working-gas purity (N2, O2, Xe)", None, "-", "pending", "W3 HW-ENV-07 working gases",
           "assumed", "TBD - requires the owner / facility gas specification (no value is sourced here)", G, ["FS-C"]),
        _p("H26-52", "O2-service cleaning standard for FS-C and module wetted parts", None, "-", "pending",
           "W3 HW-FS-07 o2_cleaning_standard TBD; candidate guides REF-ASTM-G93 (not accessed - verify) and REF-NSS1740-15 "
           "Sec. 104", "assumed", "TBD - requires the facility safety case (owner channel)", G, ["FS-C", "PIM-0",
                                                                                                "PIM-RF", "PIM-ECR"]),
    ]
    return rows


def measurement_map() -> list:
    """(1) measurement list -> Phase-1 decision quantities (P1DQ-*), W4 INS / INS-P ids, qualification stage,
    flight class."""
    G, T, F = "GROUND/FACILITY-ONLY", "H-1 TEST-ARTICLE-ONLY", "FLIGHT-REPRESENTATIVE"
    return [
        {"id": "H26-MEAS-01", "quantity": "thrust (paired and absolute)",
         "phase1_decision_quantities": ["P1DQ-TPBUS", "P1DQ-TABS", "P1DQ-STAB", "P1DQ-ENVW", "P1DQ-SUST"],
         "role": {"P1DQ-TPBUS": "decisive", "P1DQ-TABS": "decisive", "P1DQ-STAB": "decisive (S4 thrust noise)",
                  "P1DQ-ENVW": "supporting", "P1DQ-SUST": "supporting"},
         "instruments": ["INS-01", "INS-17", "INS-18"], "procedures": ["INS-P-12"], "capability_demo": ["CD-01", "CD-02"],
         "metrology_spec": [], "hardware_provisions": ["HW-SVC-01", "HW-SVC-02", "HW-SVC-03", "HW-SVC-04", "HW-SVC-05"],
         "design_parameters": ["H26-01", "H26-02", "H26-03", "H26-04", "H26-05", "H26-06", "H26-08"],
         "traceability": "A4 force_DC_RF_traceability: SI-traceable force calibration through an ISO/IEC 17025 "
                         "accredited scope (NABL in India); certificate, uncertainty budget, traceability chain, raw "
                         "record mandatory; no invented class",
         "qualification": [
             {"stage": "S1a", "what": "in-situ force calibration, linearity, zero drift, magnetic and line tares, "
                                      "per-configuration calibration with modules/dummies (CD-01); no plasma",
              "s1a_data_class": "CALIBRATION / REPEATABILITY / DRIFT (S1A-FW allowed classes, PROPOSED)"},
             {"stage": "S1a", "what": "no-plasma module-exchange reproducibility of the stand slope (CD-02a)",
              "s1a_data_class": "REINSTALLATION"},
             {"stage": "S1-C4", "what": "thrust_stand category of the owner-accepted capability record"},
             {"stage": "S1b", "what": "Hall-on u_T, u_inst (K re-installations x r readings at OP3 on HW-0), thermal "
                                      "settling T-SETTLE, drift"},
             {"stage": "Phase 1", "what": "score-bearing only after LOCK-2"}],
         "firewall_note": "Hall-on thrust is W5 VO-T: forbidden in S1a",
         "flight_classification": G, "feasibility_w4": "AT_RISK (INS-01)"},
        {"id": "H26-MEAS-02", "quantity": "bus power at the bus-boundary-equivalent point (with H2-4)",
         "phase1_decision_quantities": ["P1DQ-TPBUS", "P1DQ-PBUS", "P1DQ-IGN"],
         "role": {"P1DQ-TPBUS": "decisive", "P1DQ-PBUS": "decisive",
                  "P1DQ-IGN": "condition (heater, keeper and discharge power during the start sequence)"},
         "instruments": ["INS-02", "INS-03", "INS-18"], "procedures": [], "capability_demo": ["CD-03", "CD-02"],
         "metrology_spec": [], "hardware_provisions": ["HW-ENV-05", "HW-C1-05", "HW-PIM-12", "HW-ELEC-03"],
         "design_parameters": ["H26-09", "H26-10", "H26-11", "H26-12"],
         "traceability": "A4: SI-traceable DC and RF/microwave power calibration through an ISO/IEC 17025 accredited "
                         "scope; DUMMY_LOAD_PICKUP control",
         "qualification": [
             {"stage": "S1a", "what": "channel calibration against a traceable DC standard; RF/microwave load-plane "
                                      "characterisation into matched dummy loads; pickup check (CD-03)",
              "s1a_data_class": "CALIBRATION / CHANNEL_PERFORMANCE"},
             {"stage": "S1a", "what": "C-1 diode commissioning of keeper/heater channels with Hall discharge "
                                      "physically inhibited (A4 C1_diode_in_S1a; NON_SCORE_BEARING_ENGINEERING_ONLY)",
              "s1a_data_class": "CHANNEL_PERFORMANCE"},
             {"stage": "S1-C4", "what": "bus_power_metering and discharge_current categories"},
             {"stage": "S1b", "what": "Hall-on u_P and power-channel re-connection reproducibility"},
             {"stage": "Phase 1", "what": "P_bus = sum load-plane power / LOCK-1 ledger efficiency; compressor "
                                          "reconstructed from the upstream ICD (ABSENT_IN_LAB)"}],
         "firewall_note": "Hall-on P_bus on HW-0 is embargoed (HW0-PBUS-HALL-ON, S1A-FW PROPOSED)",
         "flight_classification": G, "flight_equivalent": "PPU per-channel V/I telemetry (FLIGHT-REPRESENTATIVE)",
         "feasibility_w4": "TBD (INS-02); AT_RISK (INS-03)"},
        {"id": "H26-MEAS-03", "quantity": "discharge current I_d (DC and time-resolved) and V_d",
         "phase1_decision_quantities": ["P1DQ-SUST", "P1DQ-ENVW", "P1DQ-IGN", "P1DQ-STAB", "P1DQ-NOXE",
                                        "P1DQ-TABS"],
         "role": {"P1DQ-SUST": "decisive", "P1DQ-ENVW": "decisive", "P1DQ-IGN": "decisive", "P1DQ-STAB": "decisive",
                  "P1DQ-NOXE": "decisive (sustainment after the Xe cut-off)",
                  "P1DQ-TABS": "condition (every visit SUSTAINED)"},
         "instruments": ["INS-04", "INS-10", "INS-18"], "procedures": ["INS-P-09"], "capability_demo": ["CD-03", "CD-06"],
         "metrology_spec": [], "hardware_provisions": ["HW-ENV-02", "HW-ELEC-01"],
         "design_parameters": ["H26-13", "H26-14", "H26-15", "H26-16"],
         "traceability": "probe gain/offset against the calibrated DC channel (INS-04)",
         "qualification": [
             {"stage": "S1a", "what": "probe gain/offset, DAQ time base and swept-sine response (CD-03, CD-06); "
                                      "no plasma", "s1a_data_class": "CALIBRATION / CHANNEL_PERFORMANCE"},
             {"stage": "S1-C4", "what": "discharge_current and (partial) stability_oscillations categories"},
             {"stage": "S1b", "what": "I_d spectrum on HW-0 fixes the band, sampling rate, ext_window and I_d,ref; "
                                      "THR-EXTINCTION validated on commanded shutdowns before any score-bearing reading"},
             {"stage": "Phase 1", "what": "sustainment classes, knee, restarts"}],
         "firewall_note": "VO-ID, VO-OSC, VO-IGNEXT: forbidden in S1a",
         "flight_classification": G, "flight_equivalent": "PPU I_d / V_d telemetry and, if H2-4 provides it, an I_d "
                                                          "ripple (rms) channel (FLIGHT-REPRESENTATIVE)",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE (INS-04, INS-10)"},
        {"id": "H26-MEAS-04", "quantity": "atmospheric anode flows (N2, O2 air surrogate) and O2 mass fraction",
         "phase1_decision_quantities": ["P1DQ-SUST", "P1DQ-ENVW", "P1DQ-ETAU", "P1DQ-TABS"],
         "role": {"P1DQ-SUST": "decisive (knee axis)", "P1DQ-ENVW": "decisive", "P1DQ-ETAU": "decisive (denominator)",
                  "P1DQ-TABS": "condition (I-FLOW-CONSERVATIVE)"},
         "instruments": ["INS-05", "INS-18"], "procedures": [], "capability_demo": ["CD-04"], "metrology_spec": [],
         "hardware_provisions": ["HW-FS-01", "HW-FS-02", "HW-FS-05", "HW-FS-07", "HW-ENV-03", "HW-ENV-07"],
         "design_parameters": ["H26-17", "H26-18", "H26-19", "H26-20", "H26-51", "H26-52"],
         "traceability": "each MFC calibrated on its own gas, installed, at the expected inlet P and T, traceable, "
                         "<= 12 months (REF-SNYDER2017 via W4)",
         "qualification": [
             {"stage": "S1a", "what": "MFC calibration per gas across the range incl. zero drift and orientation "
                                      "(CD-04); calibrated setpoints at released feed points are REG-FEED (custody-held)",
              "s1a_data_class": "CALIBRATION (instrument); REG-FEED (registration input, custody)"},
             {"stage": "S1-C4", "what": "flow category"},
             {"stage": "S1b", "what": "setpoint stability at OP3 on N2 under Hall-on conditions"},
             {"stage": "Phase 1", "what": "knee scan down and up; O2 fraction points"}],
         "flight_classification": G,
         "flight_equivalent": "atmospheric metering-valve command/state + plenum pressure and temperature "
                              "(FLIGHT-REPRESENTATIVE; H2-3)", "feasibility_w4": "AT_RISK (INS-05, low-FS setpoints)"},
        {"id": "H26-MEAS-05", "quantity": "Xe flows: cathode (0.10-0.15 mg/s capability) and anode start/transition; "
                                          "Xe consumption per mode",
         "phase1_decision_quantities": ["P1DQ-NOXE", "P1DQ-IGN"],
         "role": {"P1DQ-NOXE": "decisive", "P1DQ-IGN": "supporting"},
         "instruments": ["INS-05", "INS-18"], "procedures": ["INS-P-08"], "capability_demo": ["CD-04"],
         "metrology_spec": [], "hardware_provisions": ["HW-C1-03", "HW-C1-04", "HW-FS-01", "HW-FS-03"],
         "design_parameters": ["H26-21", "H26-22", "H26-23", "H26-24"],
         "traceability": "as MEAS-04 (Xe-calibrated MFCs)",
         "qualification": [
             {"stage": "S1a", "what": "Xe MFC calibration; C-1 diode commissioning with the Hall discharge inhibited "
                                      "(A4) - start log, keeper/heater, daily Xe reference definition",
              "s1a_data_class": "CALIBRATION / CHANNEL_PERFORMANCE"},
             {"stage": "S1b", "what": "first Hall-on ignitions on Xe and transfer to N2 (HW-FS-03); per-mode Xe "
                                      "totals and durations"},
             {"stage": "Phase 1", "what": "Xe anode flow = 0 verified at every atmospheric reading; cathode Xe at the "
                                          "design target"}],
         "flight_classification": G, "flight_equivalent": "Xe regulator/metering state, valve states and tank "
                                                          "pressure/temperature (FLIGHT-REPRESENTATIVE; H2-2 / XE ledger)",
         "feasibility_w4": "AT_RISK (INS-05)"},
        {"id": "H26-MEAS-06", "quantity": "feed pressure and temperature at IP-UP / manifold / module source chamber",
         "phase1_decision_quantities": ["P1DQ-SUST", "P1DQ-ENVW"],
         "role": {"P1DQ-SUST": "condition (same feed state)", "P1DQ-ENVW": "condition"},
         "instruments": ["INS-06", "INS-07", "INS-18"], "procedures": [], "capability_demo": [], "metrology_spec": [],
         "hardware_provisions": ["HW-ENV-04", "HW-FS-04"], "design_parameters": ["H26-25", "H26-26"],
         "traceability": "capacitance manometer zero at base vacuum and span against a traceable standard (INS-06)",
         "qualification": [
             {"stage": "S1a", "what": "manometer zero/span; cold-flow manifold pressure at each grid flow per "
                                      "configuration (HW-FS-05)", "s1a_data_class": "CALIBRATION; REG-FEED (custody)"},
             {"stage": "S1-C4", "what": "pressure category (W4 must add it: uncovered by CD-01..07)"},
             {"stage": "S1b", "what": "P_feed covariate at OP3 Hall-on"}],
         "flight_classification": F, "flight_equivalent": "flight plenum / valve-outlet pressure and temperature "
                                                          "sensors (H2-3)", "feasibility_w4": "TBD (INS-06, INS-07)"},
        {"id": "H26-MEAS-07", "quantity": "chamber / background pressure p_b and its effect on Hall operation",
         "phase1_decision_quantities": ["P1DQ-SUST", "P1DQ-TPBUS", "P1DQ-ENVW", "P1DQ-TABS", "P1DQ-ETAU"],
         "role": {"P1DQ-SUST": "condition", "P1DQ-TPBUS": "condition", "P1DQ-ENVW": "condition", "P1DQ-TABS": "condition",
                  "P1DQ-ETAU": "condition (charge-exchange correction)"},
         "instruments": ["INS-08", "INS-11", "INS-18"], "procedures": [], "capability_demo": [], "metrology_spec": [],
         "hardware_provisions": [], "design_parameters": ["H26-27", "H26-28", "H26-29", "H26-30", "H26-31", "H26-32"],
         "traceability": "ion gauges calibrated on N2 and on the O2/N2 mixture (REQ-FAC-03)",
         "known_effect_on_hall_operation": [
             "background neutrals change thrust, cathode coupling and divergence; the facility wall provides current "
             "paths absent in orbit (REF-BYRNE2022 Sec. I, accessed by this lane 2026-09-29)",
             "simple ingestion of background gas is an inadequate explanation of the thrust rise at higher pressure; "
             "NASA-173M at 15 A: thrust reduction <= 2.5 % as the chamber pressure was reduced to 6e-6 Torr (range studied ~3e-6 to ~3.5e-5 Torr) (REF-TIGHE2015 abstract, accessed by this lane 2026-09-29; "
             "xenon, different thruster - context only)",
             "SPT-100: below 1e-5 Torr needed to identify the thrust-slope change; discharge-current stability and "
             "breathing-mode frequency keep changing into the 1e-6 Torr range; data insufficient for absolute "
             "pressure requirements for general designs (REF-DANKANICH2017 p. 678, accessed by this lane 2026-09-29)"],
         "qualification": [
             {"stage": "S1a", "what": "gauge calibration; no-flow base pressure and qualitative residual gas "
                                      "(FACILITY_BACKGROUND); cold-flow p_b at released feed points = REG-PB (custody); "
                                      "effective pumping speed by REF-DANKANICH2017 Eq. 9 from those cold-flow points",
              "s1a_data_class": "CALIBRATION / FACILITY_BACKGROUND; REG-PB (custody)"},
             {"stage": "S1-C4", "what": "pressure category (W4 must add it)"},
             {"stage": "S1b", "what": "Hall-on p_b at the OP3 flow (lane 25 S1b output)"},
             {"stage": "S5", "what": "p_b raised to 2 x base by downstream injection; class FACILITY_ROBUST or "
                                     "FACILITY_CONDITIONAL; no ingestion model applied"}],
         "flight_classification": G, "feasibility_w4": "TBD (INS-08)"},
        {"id": "H26-MEAS-08", "quantity": "magnetic-field mapping B(z) at actual coil currents",
         "phase1_decision_quantities": ["P1DQ-TPBUS", "P1DQ-SUST"],
         "role": {"P1DQ-TPBUS": "condition (same accelerator condition, INV-B3)", "P1DQ-SUST": "condition"},
         "instruments": ["INS-09", "INS-24", "INS-02", "INS-18"], "procedures": ["INS-P-07"], "capability_demo": ["CD-05"],
         "metrology_spec": [], "hardware_provisions": ["HW-H1-08", "HW-MC-02", "HW-MC-03", "HW-MC-04", "HW-MC-05",
                                                       "HW-MC-15", "HW-PIM-06"],
         "design_parameters": ["H26-33", "H26-34", "H26-35", "H26-36", "H26-46"],
         "traceability": "probe calibration in a reference field and zero-field offset; stage position calibration",
         "qualification": [
             {"stage": "S1a", "what": "maps per configuration and control state (M0, M0b, M0c), hysteresis cycles, "
                                      "cold and heated-soak maps (CD-05, HW-MC-15)",
              "s1a_data_class": "REG-BZ (registration input, custody until LOCK-H1); probe constants CALIBRATION"},
             {"stage": "S1-C4", "what": "magnetic_field_Bz category"},
             {"stage": "S1b", "what": "hot reference sensor logged during firing (HW-MC-04); S_B coil-current scan if "
                                      "adopted (HW-MC-05)"}],
         "flight_classification": G, "flight_equivalent": "coil current telemetry (FLIGHT-REPRESENTATIVE); the MC-1 "
                                                          "reference field sensor is H-1 TEST-ARTICLE-ONLY",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE (INS-09)"},
        {"id": "H26-MEAS-09", "quantity": "oscillation diagnostics (I_d(t) spectrum/amplitude, coupling voltage)",
         "phase1_decision_quantities": ["P1DQ-STAB", "P1DQ-SUST"],
         "role": {"P1DQ-STAB": "decisive", "P1DQ-SUST": "supporting (extinction logic)"},
         "instruments": ["INS-04", "INS-18", "INS-10"], "procedures": ["INS-P-09"], "capability_demo": ["CD-06"],
         "metrology_spec": [], "hardware_provisions": ["HW-C1-05"], "design_parameters": ["H26-15", "H26-16"],
         "traceability": "as MEAS-03",
         "qualification": [
             {"stage": "S1a", "what": "time base and fast-channel response only (CD-06)",
              "s1a_data_class": "CHANNEL_PERFORMANCE"},
             {"stage": "S1-C4", "what": "stability_oscillations category (partial until S1b)"},
             {"stage": "S1b", "what": "oscillation spectra (A4 S1_C4_categories: S1b supplies them)"}],
         "firewall_note": "VO-OSC: forbidden in S1a",
         "flight_classification": G, "flight_equivalent": "I_d ripple telemetry if H2-4 provides it",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE (band TBD from S1b)"},
        {"id": "H26-MEAS-10", "quantity": "species / energy / current-density diagnostics (ExB, RPA, Faraday, "
                                          "Langmuir, OES) where feasible",
         "phase1_decision_quantities": ["P1DQ-ETAU", "P1DQ-TPBUS"],
         "role": {"P1DQ-ETAU": "decisive input (P1DQ-ETAU: I_b x Omega_j)", "P1DQ-TPBUS": "supporting"},
         "instruments": ["INS-13", "INS-14", "INS-15", "INS-16", "INS-12"], "procedures": [], "capability_demo": [],
         "metrology_spec": [], "hardware_provisions": ["HW-PIM-07"],
         "design_parameters": ["H26-37", "H26-38", "H26-39"],
         "traceability": "REF-BROWN2017 Faraday practice (probe area, bias sweep, SEE/gap corrections); ExB "
                         "mass-resolution check on known ions",
         "qualification": [
             {"stage": "S1a", "what": "bench calibration only (areas, grid transparency, bias supplies)",
              "s1a_data_class": "CALIBRATION"},
             {"stage": "S1-C4", "what": "species_divergence category (W4 must add it or the owner reduces the set)"},
             {"stage": "S1b", "what": "species/divergence capability on HW-0 (A4: S1b supplies it)"},
             {"stage": "Phase 1", "what": "eta_u inputs at every scored point where the framework requires them"}],
         "firewall_note": "VO-SPECIES, VO-IEDF, VO-DIV, VO-TENE: forbidden in S1a",
         "flight_classification": G, "feasibility_w4": "AT_RISK (INS-13 low-energy resolution; INS-15 CEX bound "
                                                       "needs a cited N2+ on N2 cross section; INS-16 AT_RISK); "
                                                       "OPTIONAL (INS-12)"},
        {"id": "H26-MEAS-11", "quantity": "ignition / restart behaviour",
         "phase1_decision_quantities": ["P1DQ-IGN", "P1DQ-NOXE"],
         "role": {"P1DQ-IGN": "decisive", "P1DQ-NOXE": "supporting (Xe start/transition duration)"},
         "instruments": ["INS-04", "INS-10", "INS-05", "INS-18"], "procedures": ["INS-P-08", "INS-P-09"],
         "capability_demo": ["CD-06"], "metrology_spec": [], "hardware_provisions": ["HW-FS-03", "HW-C1-07"],
         "design_parameters": ["H26-16", "H26-23", "H26-24"],
         "traceability": "as MEAS-03 / MEAS-05",
         "qualification": [
             {"stage": "S1a", "what": "C-1 start log only (heater power, time to ignition, keeper ignition voltage) "
                                      "with the Hall discharge inhibited", "s1a_data_class": "CHANNEL_PERFORMANCE"},
             {"stage": "S1b", "what": "Hall ignition on Xe, transfer to N2, commanded shutdown and restart"},
             {"stage": "Phase 1", "what": "restart after extinction at knee points; attempts and timeouts"}],
         "firewall_note": "VO-IGNEXT: forbidden in S1a",
         "flight_classification": G, "flight_equivalent": "start-sequence timing, keeper ignition voltage, heater "
                                                          "time and attempt counts (FLIGHT-REPRESENTATIVE, control/FDIR)",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE"},
        {"id": "H26-MEAS-12", "quantity": "temperatures (stand, mount, H-1, MC-1 coils, C-1 tube, module)",
         "phase1_decision_quantities": ["P1DQ-TPBUS", "P1DQ-TABS", "P1DQ-SUST", "P1DQ-IGN"],
         "role": {"P1DQ-TPBUS": "condition (T-SETTLE, thrust drift)", "P1DQ-TABS": "condition",
                  "P1DQ-SUST": "condition (thermal settling before the dwell)",
                  "P1DQ-IGN": "condition (C-1 cathode-tube temperature at start, INS-23)"},
         "instruments": ["INS-17", "INS-23", "INS-24", "INS-18"], "procedures": ["INS-P-07"], "capability_demo": ["CD-07"],
         "metrology_spec": [], "hardware_provisions": ["HW-H1-07", "HW-H1-12", "HW-MC-14", "HW-C1-09", "HW-PIM-09"],
         "design_parameters": ["H26-44"],
         "traceability": "thermocouple calibration by comparison (ASTM E220 via W4, metadata only - verify)",
         "cathode_temperature_rule": "A3/A4: the cathode-tube thermocouple is mandatory and never labelled emitter "
                                     "temperature; without a pyrometer view the emitter temperature is 'unmeasured'",
         "qualification": [
             {"stage": "S1a", "what": "sensor calibration, cold junction, isothermal cross-check, pickup (CD-07)",
              "s1a_data_class": "CALIBRATION / CHANNEL_PERFORMANCE"},
             {"stage": "S1-C4", "what": "temperature category"},
             {"stage": "S1b", "what": "thermal time constants (T-SETTLE)"}],
         "flight_classification": G, "flight_equivalent": "anode/body temperature, coil temperature via resistance, "
                                                          "cathode-tube temperature (FLIGHT-REPRESENTATIVE subset)",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE (INS-17); AT_RISK (INS-23 emitter view)"},
        {"id": "H26-MEAS-13", "quantity": "electrical coupling and integrity (cathode-to-ground / anode-to-ground "
                                          "potential, anode 4-wire resistance, insulation resistance)",
         "phase1_decision_quantities": ["P1DQ-SUST", "P1DQ-TPBUS"],
         "role": {"P1DQ-SUST": "supporting", "P1DQ-TPBUS": "condition (facility electrical effects)"},
         "instruments": ["INS-02", "INS-04", "INS-21"], "procedures": ["INS-P-06"], "capability_demo": [],
         "metrology_spec": [], "hardware_provisions": ["HW-C1-05", "HW-ELEC-04", "HW-ELEC-05"],
         "design_parameters": ["H26-45"],
         "traceability": "meter calibration against traceable resistance standards (INS-21)",
         "qualification": [{"stage": "S1a", "what": "baseline anode and insulation resistance",
                            "s1a_data_class": "CALIBRATION / CHANNEL_PERFORMANCE"},
                           {"stage": "S1b", "what": "coupling voltage at OP3; between-block anode resistance"}],
         "flight_classification": T, "flight_equivalent": "cathode-to-spacecraft potential telemetry if H2-4 provides it",
         "feasibility_w4": "FEASIBLE_IN_PRINCIPLE (INS-21)"},
        {"id": "H26-MEAS-14", "quantity": "common time base / DAQ", "phase1_decision_quantities": ["P1DQ-TPBUS", "P1DQ-STAB"],
         "role": {"P1DQ-TPBUS": "condition (simultaneous V and I)", "P1DQ-STAB": "condition"},
         "instruments": ["INS-18"], "procedures": ["INS-P-10"], "capability_demo": ["CD-06"], "metrology_spec": [],
         "hardware_provisions": [], "design_parameters": ["H26-16"], "traceability": "timing check with a common trigger",
         "qualification": [{"stage": "S1a", "what": "skew and drift (CD-06)", "s1a_data_class": "CHANNEL_PERFORMANCE"}],
         "flight_classification": G, "feasibility_w4": "FEASIBLE_IN_PRINCIPLE"},
        {"id": "H26-MEAS-15", "quantity": "witness-coupon and part metrology, near-cathode gas sampling (life / O "
                                          "exposure evidence; not a Phase-1 decision quantity)",
         "phase1_decision_quantities": [], "role": {},
         "instruments": ["INS-19", "INS-20", "INS-22", "INS-11"],
         "procedures": ["INS-P-01", "INS-P-02", "INS-P-03", "INS-P-04", "INS-P-05", "INS-P-10", "INS-P-11", "INS-P-12"],
         "capability_demo": [], "metrology_spec": ["MS-G-01", "MS-G-02", "MS-G-03", "MS-M-01", "MS-M-02", "MS-M-03",
                                                   "MS-M-04", "MS-M-05"],
         "hardware_provisions": ["HW-H1-09", "HW-H1-13", "HW-C1-06", "HW-C1-07", "HW-PIM-14", "HW-SVC-06"],
         "design_parameters": [],
         "traceability": "A3 metrology_lab: ISO/IEC 17025 accredited scope (NABL in India); OIML R111 E2 or better "
                         "reference masses; ISO 25178-700 surface standards; ASTM E1508 quantitative EDS; ISO 15472 "
                         "XPS energy scale; A4: approved as the procurement specification, not a demonstrated capability",
         "qualification": [{"stage": "S1a", "what": "baseline metrology before first ignition (INS-P-02); "
                                                    "qualitative RGA only unless calibrated (A3)",
                            "s1a_data_class": "QUALITATIVE_RGA (no dose or lifetime claim)"}],
         "flight_classification": T, "feasibility_w4": "TBD / AT_RISK (INS-19, INS-22)"},
    ]


def fixture() -> dict:
    """(2) H-1 fixture: stand mounting, module slot, SVC-1, isolation, remount reproducibility."""
    ICD = _pending("fo_preionizer_module_icd")
    return {
        "principle": "H-1 + C-1 + MC-1 are one assembly on the stand's moving platform. The pre-ionizer module "
                     "(PIM-0 / PIM-RF / PIM-ECR) sits in its own kinematic carrier on the same platform between IP-UP "
                     "and IP-DN. A configuration change exchanges only the module; the H-1 mount is never unbolted "
                     "(W3 HW-SVC-04 PROPOSED, HWQ-01). The fixture belongs to the W3 identity-matrix element 'thrust "
                     "stand, mount, service-line bundle (with shams), grounding and cable routing' (must be identical "
                     "in every configuration); it is not a new configuration item.",
        "features": [
            {"id": "H26-FX-01", "name": "H-1 mounting adapter on the stand moving platform",
             "description": "one adapter carries H-1 with MC-1 and the C-1 mount; C-1 position fixed on H-1 and "
                            "recorded (W3 HW-C1-01); a thermally isolating, electrically insulating interface between "
                            "adapter and platform (FX-04, FX-05)",
             "why": "cathode position alone changed NASA-173M thrust by more than 3 % when raised 6 in "
                    "(REF-TIGHE2015 abstract, accessed by this lane 2026-09-29; context, different thruster): the C-1 position must not "
                    "move with a module exchange",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["H-1", "C-1", "MC-1"],
             "status": _pending("fo_h2_1_hall_chamber_magnet") + " and " + _pending("fo_h2_7_mechanical_bom")},
            {"id": "H26-FX-02", "name": "module slot: kinematic module carrier",
             "description": "a carrier on the moving platform locates each module by an exactly-constrained "
                            "(6-constraint, 3-point) seat with preload; the module's weight goes through the carrier, "
                            "not through IP-DN; the IP-DN joint makes only the gas seal and the flange-pattern "
                            "alignment (same pattern, seals and torque for every module, HW-PIM-01), with a "
                            "torque-reaction tool so no assembly torque reaches the H-1 mount; IP-UP stays fixed in "
                            "the stand frame (W3 interface_planes)",
             "why": "module exchange is the controlled variable (A6 fo_preionizer_module_icd); installation terms do "
                    "not average down (lane 25 G5, W3 HW-SVC-01 rationale)",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["PIM-0", "PIM-RF", "PIM-ECR", "IP-UP",
                                                                            "IP-DN"],
             "status": ICD + " (mechanical envelope, mounting datum, installation/removal reproducibility item)"},
            {"id": "H26-FX-03", "name": "service-line bundle SVC-1 fixed routing with shams",
             "description": "every line crossing the stand is present in every configuration; arm-specific lines are "
                            "shams in the other configurations (RF coax and microwave feed in HW-0, terminated "
                            "off-stand); lines cross from the stand base to the moving platform orthogonal to the "
                            "thrust axis with fixed loops; gas lines in solid metal tubing (REF-POLK2017); per-"
                            "configuration line tare in the in-situ calibration",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["SVC-1"],
             "status": "PRELIMINARY"},
            {"id": "H26-FX-04", "name": "thermal isolation and stand thermal control",
             "description": "low-conductance standoffs between the H-1 adapter and the platform; stand thermal "
                            "shroud / active cooling of critical stand components (REF-POLK2017); thermocouples on the "
                            "adapter, standoffs, platform and module carrier; module waste heat into H-1 either "
                            "isolated at IP-DN or instrumented (W3 HW-PIM-09)",
             "sizing_bound": "heat into H-1 + mount <= 1500 W (H26-44, bound not estimate)",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["H-1", "PIM-RF", "PIM-ECR"],
             "status": _pending("fo_h2_5_thermal_network")},
            {"id": "H26-FX-05", "name": "electrical isolation of the stand",
             "description": "H-1 body isolated from the platform and facility ground (thruster floats, W3 HW-ELEC-01) "
                            "with isolation rated >= 350 V + margin; the same grounding scheme and cable routing in "
                            "every arm; RF and microwave returns separate from the discharge return (HW-ELEC-03); "
                            "module body potential declared identically for PIM-0 (HW-ELEC-02, HWQ-07); the gas "
                            "isolator is upstream of IP-UP (HW-FS-06)",
             "why": "the conducting facility wall provides current paths absent in orbit (REF-BYRNE2022 Sec. I); the "
                    "H9 there ran electrically isolated from the facility (Sec. II)",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["H-1", "PS-C", "SVC-1", "PIM-0",
                                                                            "PIM-RF", "PIM-ECR"],
             "status": "TBD - requires the owner isolation margin (HW-FS-06 / HW-ELEC-05) and " + ICD + " (module potential)"},
            {"id": "H26-FX-06", "name": "non-ferromagnetic fixture and magnetic tare",
             "description": "no ferromagnetic fixture part, fastener or calibrator part inside the MC-1 exclusion zone "
                            "(H26-46); magnetic tare characterised across coil settings and, for PIM-ECR, magnet on/off "
                            "(REF-POLK2017; W3 HW-SVC-05); M0 vs M0b B(z) map shows the fixture within INV-B3",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["MC-1", "PIM-ECR"],
             "status": _pending("fo_h2_1_hall_chamber_magnet")},
            {"id": "H26-FX-07", "name": "remount-reproducibility features",
             "description": "fiducials on the H-1 exit rings (HW-H1-11) and the module carrier; an alignment reference "
                            "(mirror or inclinometer seat) on the H-1 adapter read before and after every exchange; "
                            "dowelled carrier; documented torque and sequence; serial/part log (HW-H1-02)",
             "flight_classification": "H-1 TEST-ARTICLE-ONLY", "interfaces": ["H-1", "PIM-0", "PIM-RF", "PIM-ECR"],
             "status": "PRELIMINARY"},
            {"id": "H26-FX-08", "name": "diagnostic access on H-1 and fixture",
             "description": "B(z) probe guide keyed to the H-1 exit fiducials (probe path to the anode face with any "
                            "module installed, HW-H1-08); manifold and module source-chamber pressure ports "
                            "(HW-FS-04); near-cathode RGA sampling inlet (INS-22, HW-C1-07); cathode-tube thermocouple "
                            "and pyrometer line of sight where possible (HW-C1-09); anode sense lead (HW-ELEC-04); MC-1 "
                            "reference field sensor (HW-MC-04); witness holder outside the beam core (HW-SVC-06)",
             "flight_classification": "H-1 TEST-ARTICLE-ONLY", "interfaces": ["H-1", "C-1", "MC-1", "SVC-1"],
             "status": _pending("fo_h2_2_cathode_integration")},
            {"id": "H26-FX-09", "name": "in-situ force calibrator",
             "description": "applies known forces on the thrust axis at the H-1 thrust-axis height, with the force "
                            "line aligned with the thrust vector (REF-POLK2017); span H26-01..H26-02; >= 10 "
                            "calibrations before and after (H26-06)",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["SVC-1"], "status": "PRELIMINARY"},
            {"id": "H26-FX-10", "name": "stand principle and inclination",
             "description": "torsional (response independent of the mass on the stand) or inverted pendulum with "
                            "active inclination control (REF-POLK2017; W4 INS-01); because the module mass changes "
                            "between arms, either a mass-independent response or a full calibration per configuration "
                            "(HW-SVC-02) is required - both are carried, the owner chooses",
             "flight_classification": "GROUND/FACILITY-ONLY", "interfaces": ["SVC-1"],
             "status": "TBD - requires the owner stand-principle decision (W4 open owner decision)"},
        ],
        "service_line_bundle": [
            {"line": "anode gas feed (after the gas isolator) to IP-UP", "arms": "all", "sham_in": []},
            {"line": "C-1 Xe gas line (own MFC, never crosses HALL_INLET_Z0)", "arms": "all", "sham_in": []},
            {"line": "discharge anode and cathode-common leads", "arms": "all", "sham_in": []},
            {"line": "keeper leads; heater leads", "arms": "all", "sham_in": []},
            {"line": "MC-1 coil leads + 4-wire potential leads per coil", "arms": "all", "sham_in": [],
             "count": _pending("fo_h2_1_hall_chamber_magnet")},
            {"line": "anode 4-wire sense lead (HW-ELEC-04)", "arms": "all", "sham_in": []},
            {"line": "thermocouples (H-1, wall rings, coupons, coil hot spots, C-1 tube, adapter, carrier)", "arms": "all",
             "sham_in": [], "count": _pending("fo_h2_5_thermal_network")},
            {"line": "MC-1 reference field sensor cable (HW-MC-04, if adopted)", "arms": "all", "sham_in": []},
            {"line": "module source-chamber pressure port line (blanked or connected identically in PIM-0, HW-FS-04)",
             "arms": "all", "sham_in": ["hall_only"]},
            {"line": "near-cathode RGA sampling tube (INS-22)", "arms": "all", "sham_in": []},
            {"line": "RF coax to PIM-RF", "arms": "rf_hall", "sham_in": ["hall_only", "ecr_hall"]},
            {"line": "microwave feed (waveguide or coax) to PIM-ECR", "arms": "ecr_hall", "sham_in": ["hall_only",
                                                                                                   "rf_hall"]},
            {"line": "ECR magnet leads (electromagnet option, HWQ-05)", "arms": "ecr_hall",
             "sham_in": ["hall_only", "rf_hall"]},
            {"line": "module enable / interlock / control lines", "arms": "all", "sham_in": ["hall_only"],
             "count": ICD},
        ],
        "remount_reproducibility": {
            "requirement": "u_inst of ln(T/P_bus) <= lane-25 u_inst,max at the n fixed at LOCK-2 (0.249 % at n = 4, "
                           "W3 HW-SVC-03), unless a no-vent switch (D-06-B) is adopted",
            "contributors": [
                {"id": "c1", "name": "stand calibration and zero shift", "features": ["H26-FX-09", "H26-FX-10",
                                                                                     "H26-FX-03"],
                 "measured_in": ["S1a CD-01 (per-configuration calibration)", "S1a CD-02a", "S1b"]},
                {"id": "c2", "name": "thrust-axis alignment", "features": ["H26-FX-01", "H26-FX-02", "H26-FX-07"],
                 "measured_in": ["S1a CD-02a (alignment reference reading per cycle)", "S1b"]},
                {"id": "c3", "name": "magnetic-circuit / B(z) change", "features": ["H26-FX-06"],
                 "measured_in": ["S1a CD-05 / HW-MC-03 map before and after each exchange", "S1b"]},
                {"id": "c4", "name": "gas path, distributor and leak change", "features": ["H26-FX-02"],
                 "measured_in": ["S1a HW-FS-05 cold-flow manifold pressure and leak check per exchange", "S1b"]},
                {"id": "c5", "name": "service-line, thermal and electrical environment change",
                 "features": ["H26-FX-03", "H26-FX-04", "H26-FX-05"],
                 "measured_in": ["S1a CD-02a power-channel gain check per cycle", "S1b"]},
            ],
            "series": "CD-02a (S1a, no plasma) and S1b (Hall-on at OP3 on HW-0) both replicate exactly the adopted "
                      "configuration-change procedure: K = 6 cycles x r = 3 readings (lane 25 PROPOSED); nu = K - 1",
            "icd_item": ICD + ": the installation/removal reproducibility item of the common pre-ionizer interface "
                              "(the in-progress ICD draft, read-only, names it PMI-11; not consumed here - confirmed at the integration pass)",
        },
        "configuration_change_procedure_proposed": [
            "record alignment reference and module-carrier seating before venting",
            "vent; release the IP-DN seal joint with the torque-reaction tool; lift the module from its carrier",
            "seat the next module in the carrier; make the IP-DN seal at the ICD torque; connect module lines at their "
            "fixed break points (shams for absent arms)",
            "leak check; cold-flow manifold pressure at each grid flow (HW-FS-05)",
            "pump down; alignment reference and carrier seating re-read; B(z) map in the control states (HW-MC-03)",
            "in-situ thrust-stand calibration (>= 10 calibrations, HW-SVC-02); dummy-load pickup check for source arms",
        ],
        "proposed_additions_to_w3_verification_per_configuration_change": [
            "alignment-reference reading before and after the exchange (H26-FX-07)",
            "module-carrier seating check (H26-FX-02)",
        ],
    }


def facility(der: dict) -> dict:
    """(3) facility requirements: pumping speed, background pressure, gas supply, O2 safety."""
    return {
        "requirements": [
            {"id": "H26-FAC-01", "requirement": "effective pumping speed at the thruster exit plane S_eff = Q / "
                                                "(p_b - p_base) (REF-DANKANICH2017 Eq. 9, p. 673) sufficient to hold "
                                                "T-PB-MAX at the total grid flow (anode + cathode), reported per gas "
                                                "(N2, O2, Xe)",
             "values": "H26-28; derived.S_eff_required", "stage": "S1a cold flow (REG-PB custody) and S1b Hall-on",
             "status": "TBD - requires T-PB-MAX (owner, LOCK-1) and the facility choice"},
            {"id": "H26-FAC-02", "requirement": "background gauges placed and operated per REF-DANKANICH2017 pp. 672-673 "
                                                "and calibrated on N2 and the O2/N2 mixture", "values": "H26-30",
             "stage": "S1a", "status": "PRELIMINARY"},
            {"id": "H26-FAC-03", "requirement": "ability to raise p_b to 2 x base by downstream injection >= 2 m "
                                                "with a pumping surface between injection and gauge (S5)",
             "values": "H26-31", "stage": "S5", "status": "PRELIMINARY"},
            {"id": "H26-FAC-04", "requirement": "one facility, stand and mount procedure for S1b and every score-"
                                                "bearing stage (REQ-FAC-05)", "values": "-", "stage": "S1b onward",
             "status": "PRELIMINARY"},
            {"id": "H26-FAC-05", "requirement": "gas supply: separate pure N2 and O2 supplies metered by one MFC per "
                                                "pure gas (INS-05) and mixed at one point upstream of IP-UP (HW-FS-02); "
                                                "O2 mass fraction 0.42-0.60 set by the flow ratio; Xe for start, "
                                                "transfer, health check and C-1",
             "values": "H26-17..H26-21, H26-51", "stage": "S1a", "status": "PRELIMINARY"},
            {"id": "H26-FAC-06", "requirement": "O2 safety case before any O2 flow (see o2_safety)",
             "values": "H26-52", "stage": "before the first O2-bearing flow (S1a cold flow)",
             "status": "TBD - requires the facility safety case (owner channel; REQ-FAC-04)"},
            {"id": "H26-FAC-07", "requirement": "chamber size allowing the preferred wall-gauge position and the "
                                                "Faraday far-field arc", "values": "H26-32, H26-37",
             "stage": "facility choice", "status": _pending("fo_h2_1_hall_chamber_magnet") + " (H-1 OD)"},
        ],
        "pumping_speed_table_L_per_s": {case: {p: v["value"] for p, v in d.items()}
                                        for case, d in der["S_eff_required"].items()},
        "pumping_speed_note": "planning scenarios only (xenon/SPT-100 derived pressures, REF-DANKANICH2017 Sec. V); "
                              "the anode upper end is the W1 no-backflow upper bound; the with-accumulation row is W1 "
                              "MFC headroom only (FC-08). Published comparison: the Aerospace EP2 facility is quoted "
                              "with a xenon pumping speed of ~250 kL/s (REF-TIGHE2015 Sec. II.A) - a xenon figure, not "
                              "an N2/O2 figure.",
        "ingestion_scale_note": "one-way background N2 mass flux over the exit area divided by the anode flow; a scale, "
                                "never a correction and never applied to rescue a class (lane 25 Sec. 8)",
        "o2_safety": [
            {"item": "O2 cleanliness of every wetted part of FS-C and the modules",
             "basis": "W3 HW-FS-07; REF-NSS1740-15 Sec. 104 c ('Oxygen systems shall be kept clean because organic "
                      "compound contamination, such as hydrocarbon oil, can ignite easily'); cleaning-level selection "
                      "guide REF-ASTM-G93 (not accessed - verify)", "status": "TBD - requires the facility safety case"},
            {"item": "pump lubricants and pump type compatible with O2 throughput",
             "basis": "REF-EDWARDS-RV ('Where a high concentration of oxygen or other chemically reactive gases are "
                      "present', highly inert man-made lubricants are recommended)", "status": "TBD - facility data"},
            {"item": "cryopump oxidizer accumulation and ozone: regeneration frequency, oxygen concentration during "
                     "roughing, inert-gas dilution of the exhaust",
             "basis": "REF-ULVAC-CRYO ('Explosion occurring from ozone in the cryopump could cause severe injury'; "
                      "ozone as a by-product when oxygen is a process gas; 'Regenerate as frequently and periodically as practical to minimize the amount "
                      "of oxidizer present in the cryopump'; inert purge of the exhaust line)",
             "status": "TBD - facility data; the plasma is an ionizing process (ozone formation is plausible, not "
                       "quantified here)"},
            {"item": "two independent barriers or safeguards so that two simultaneous undesired events are needed "
                     "before injury", "basis": "REF-NSS1740-15 Sec. 104 f", "status": "PRELIMINARY"},
            {"item": "interlocks: IL-OXIDIZER-ISOLATION, IL-VACUUM, IL-EMERGENCY-STOP, Hall-discharge inhibit in S1a; "
                     "limits from real hardware/facility ratings, not invented thresholds",
             "basis": "S1a gate S1A-C2 (PROPOSED ids); A4 S1a_minimum_interlocks and S1a_interlock_limits",
             "status": "PRELIMINARY"},
            {"item": "hot LaB6 emitter with O2 present: Xe flow whenever the emitter is hot and O2-bearing gas is in "
                     "the chamber; purge before heating", "basis": "W3 HW-C1-03 (G&K Sec. 6.8.5 via lane 19)",
             "status": "PRELIMINARY"},
            {"item": "room oxygen-concentration monitoring near vents and exhausts", "basis": "assumed (engineering "
                                                                                             "practice; no source cited)",
             "status": "TBD - requires the facility safety case"},
        ],
    }


def ground_vs_flight() -> list:
    """(4) diagnostics: ground-only vs flight-representative (flight telemetry subset)."""
    F, T, G = "FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"
    rows = [
        ("thrust stand (INS-01)", G, False, "none (thrust is not measured in flight)"),
        ("lab precision power metering per channel (INS-02, INS-03)", G, False, "PPU per-channel V and I telemetry"),
        ("PPU per-channel output V and I (discharge, magnet, keeper, heater, source)", F, True, "itself"),
        ("discharge current and voltage DC telemetry", F, True, "itself"),
        ("wide-band I_d(t) probe and fast DAQ (INS-04 fast channel)", G, False, "I_d ripple (rms) telemetry if H2-4 "
                                                                                 "provides it"),
        ("I_d ripple / oscillation amplitude telemetry", F, True, "candidate; " + _pending("fo_h2_4_ppu_bus")),
        ("thermal MFCs N2 / O2 / Xe (INS-05)", G, False, "metering-valve and Xe-metering states"),
        ("atmospheric metering-valve command/state; Xe regulator/metering state; valve states", F, True, "itself"),
        ("feed pressure / temperature at the valve outlet (flight sensor at the IP-UP-equivalent plane)", F, True,
         _pending("fo_h2_3_gas_path_plenum")),
        ("capacitance manometers at manifold and module source chamber (INS-06)", G, False, "flight feed-pressure sensor"),
        ("Xe tank pressure and temperature", F, True, "itself (stored-Xe subsystem of docs/budgets/xe_ledger/, verified)"),
        ("background-pressure ion gauges, RGA (INS-08, INS-11, INS-22)", G, False, "none"),
        ("B(z) gaussmeter and positioning stage (INS-09)", G, False, "coil-current telemetry"),
        ("magnet coil current telemetry; coil temperature from coil resistance", F, True, "itself"),
        ("MC-1 reference field sensor (HW-MC-04)", T, False, "none"),
        ("ExB, RPA, Faraday, Langmuir, OES (INS-12..16)", G, False, "none"),
        ("anode / body temperature; cathode-tube temperature", F, True, "itself (tube, never labelled emitter)"),
        ("life-mechanism thermocouples at wall rings and coupons; coil hot-spot thermocouples (INS-23, INS-24)", T,
         False, "none"),
        ("stand, adapter and carrier thermocouples (INS-17)", G, False, "none"),
        ("anode 4-wire resistance lead, insulation-resistance access (INS-21)", T, False, "none"),
        ("cathode-to-ground coupling potential", F, True, "cathode-to-spacecraft potential, candidate; "
                                                          + _pending("fo_h2_4_ppu_bus")),
        ("start log: heater time, keeper ignition voltage, attempts, sequence timing", F, True, "control/FDIR"),
        ("witness coupons, holders and external metrology (INS-19, INS-20)", T, False, "none"),
        ("common time base / DAQ (INS-18)", G, False, "spacecraft time tagging (outside this lane)"),
    ]
    return [{"diagnostic": d, "flight_classification": c, "flight_telemetry_subset": s, "flight_counterpart": fc}
            for d, c, s, fc in rows]


def interface_demands() -> list:
    L = "fo_h2_6_diagnostics_fixture"

    def dem(frm, to, q, v, u, s):
        return {"from": frm, "to": to, "quantity": q, "value": v, "units": u, "status": s}

    H1 = _pending("fo_h2_1_hall_chamber_magnet")
    H2 = _pending("fo_h2_2_cathode_integration")
    H3 = _pending("fo_h2_3_gas_path_plenum")
    H4 = _pending("fo_h2_4_ppu_bus")
    H5 = _pending("fo_h2_5_thermal_network")
    H7 = _pending("fo_h2_7_mechanical_bom")
    ICD = _pending("fo_preionizer_module_icd")
    XE = XE_CONSUMER
    P1 = P1_UNFROZEN
    M16 = _pending("fo_subsystem_maturity_matrix")
    return [
        dem("fo_h2_1_hall_chamber_magnet", L, "channel mean radius, exit OD, channel length and domain length",
            "analog context only: ECHT 86 mm / 10 mm / 100 mm OD", "m", H1),
        dem("fo_h2_1_hall_chamber_magnet", L, "design B_max on the channel centreline and coil count / max current",
            None, "T / A", H1),
        dem("fo_h2_1_hall_chamber_magnet", L, "H-1 rear flange (IP-DN) pattern, exit-ring fiducial positions, "
                                              "thermocouple points", None, "-", H1),
        dem(L, "fo_h2_1_hall_chamber_magnet", "B(z) probe path to the anode face with any module installed "
                                              "(HW-H1-08) and a probe-guide seat keyed to exit fiducials",
            "required", "-", "PRELIMINARY"),
        dem(L, "fo_h2_1_hall_chamber_magnet", "non-ferromagnetic exclusion-zone extent around MC-1 for the fixture",
            None, "m", H1),
        dem("fo_h2_2_cathode_integration", L, "C-1 mount position on H-1, keeper/heater V-I ranges, tube-TC and "
                                              "pyrometer view, near-cathode sampling inlet position", None, "-", H2),
        dem(L, "fo_h2_2_cathode_integration", "Xe cathode MFC capability and full-scale window",
            "0.10-0.15 mg/s capability; FS 0.15-0.50 mg/s (H26-21)", "mg s^-1", "PRELIMINARY"),
        dem("fo_h2_3_gas_path_plenum", L, "IP-UP location in the stand frame, gas-isolator position, manifold and "
                                          "source-chamber port positions, P_feed vs mdot conductance", None, "-", H3),
        dem(L, "fo_h2_3_gas_path_plenum", "flight-representative feed pressure/temperature sensors at the valve "
                                          "outlet (telemetry subset)", "required", "-", "PRELIMINARY"),
        dem(L, "fo_h2_3_gas_path_plenum", "per-gas MFC paths and overlapping ranges for ground supply",
            "N2 0.0118-3.14 mg/s, O2 0.0124-1.89 mg/s, 4 ranges each at the 20 % FS floor (H26-18/19)", "mg s^-1",
            "PRELIMINARY"),
        dem("fo_h2_4_ppu_bus", L, "per-component ledger efficiencies (bus_power_boundary_v1) and PPU telemetry "
                                  "channel list incl. I_d ripple and coupling potential", None, "-", H4),
        dem(L, "fo_h2_4_ppu_bus", "lab load-plane measurement points identical to the PPU output terminals per "
                                  "component (bus-boundary-equivalent point)", "hall_discharge ... ecr_magnet",
            "-", "PRELIMINARY"),
        dem(L, "fo_h2_5_thermal_network", "heat into H-1 + mount (upper bound for stand thermal design)", 1500.0, "W",
            "PRELIMINARY"),
        dem("fo_h2_5_thermal_network", L, "conductive share into the mount; module waste heat at IP-DN; thermal "
                                          "time constants for T-SETTLE planning", None, "W / s", H5),
        dem("fo_h2_7_mechanical_bom", L, "mass on the stand moving platform per configuration (H-1 + C-1 + MC-1; "
                                         "PIM-0 / PIM-RF / PIM-ECR)", None, "kg", H7),
        dem(L, "fo_h2_7_mechanical_bom", "fixture items are test-article/ground-only and excluded from the flight "
                                         "mass model (FX-01..FX-10)", "excluded", "-", "PRELIMINARY"),
        dem(L, "fo_preionizer_module_icd", "module mechanical envelope and mounting datum compatible with a "
                                           "kinematic carrier; module weight not carried by IP-DN", "required", "-",
            ICD),
        dem(L, "fo_preionizer_module_icd", "installation/removal reproducibility item measured by CD-02a and S1b "
                                           "with the procedure of fixture.configuration_change_procedure_proposed",
            "u_inst <= 0.249 % (n = 4)", "ln-ratio", ICD),
        dem(L, "fo_preionizer_module_icd", "service-line routing: RF coax, microwave feed, ECR magnet and module "
                                           "control lines present as shams in the other arms (SVC-1)", "required",
            "-", ICD),
        dem(L, "fo_preionizer_module_icd", "source-chamber pressure port in every module and blanked/connected "
                                           "identically in PIM-0 (HW-FS-04); I_src access (HW-PIM-07)", "required",
            "-", ICD),
        dem(L, "fo_xe_system_ledger", "measured Xe per mode (cathode, startup, transition, fallback) from totalized "
                                      "Xe MFC flows and logged durations", "cathode term 1 sigma 0.081-0.27 kg over "
                                                                           "15,000 h (H26-22)", "kg", XE),
        dem(L, "fo_phase1_prereg_framework", "measurement map of the nine P1DQ-* decision quantities to instruments "
                                             "and qualification stages (measurement_map; every DECISIVE / CONDITION "
                                             "ins_id of each P1DQ measurement_chain is covered, checked by the test)",
            "required", "-", "PRELIMINARY (framework verified; this map is an input to LOCK-1)"),
        dem("fo_phase1_prereg_framework", L, "LOCK-2 numeric boundaries: n, u_T / u_P / u_inst, dwell, ext_window, "
                                             "I_d band and sampling, zero band of the Xe MFC", None, "-", P1),
        dem(L, "fo_subsystem_maturity_matrix", "proposed M16 rows (m16_rows)", "4 rows", "-", M16),
        dem(L, "H-1", "test-article-only provisions do not alter the flight-representative flow path or anode area "
                      "(HW-H1-09 rule)", "required", "-", "PRELIMINARY"),
        dem(L, "IP-DN", "seal/alignment joint only; no module part downstream of IP-DN (HW-H1-06)", "required", "-",
            "PRELIMINARY"),
        dem(L, "IP-UP", "fixed in the stand frame; the feed line upstream never moves between configurations",
            "required", "-", "PRELIMINARY"),
        dem(L, "HALL_INLET_Z0", "no diagnostic, probe or fixture part changes the inlet state setting; the inlet state "
                                "remains a result, not a setting", "required", "-", "PRELIMINARY"),
        dem(L, "SVC-1", "line inventory with shams (fixture.service_line_bundle)", "14 line groups", "-",
            "PRELIMINARY"),
    ]


def hard_incompatibility_check(der: dict) -> dict:
    return {
        "verdict": "none found",
        "what_was_checked": [
            "G1_thrust / absolute thrust gate measurability: a stand spanning 0 to >= 25.42 mN with ~60-88 uN per-reading "
            "1 sigma at 12 mN is a stated recommended-practice class of instrument (REF-POLK2017; REF-XU2009 abstract "
            "gives a 1 mN - 5 N null-type example - verify); achievability is a test-readiness item (S1b), not an "
            "incompatibility",
            "G2_bus_power measurability at the bus-boundary-equivalent point: every bus_power_boundary_v1 component "
            "has a load-plane measurement or a ledger input; the compressor is reconstructed (never zero) - partial "
            "boundary until H2-4 efficiencies and the upstream ICD exist",
            "G6_ignition_sustainment measurability: I_d(t) + THR-EXTINCTION logic + p_b per reading; the ingestion "
            "scale at the lowest candidate flow is large (H26-29) - a validity threat to the knee measurement that the "
            "S5 check and T-PB-MAX handle, not a hardware incompatibility",
            "G7_air_xenon: the gas supply (pure N2, O2, Xe MFCs, single mixing point) covers N2, the air surrogate "
            "and Xe; atomic O is not reproduced by the minimum hardware (W3 HW-ENV-07, HWQ-11) - a recorded "
            "representativeness limitation, not an incompatibility",
            "module exchange vs H-1 alignment: a kinematic carrier keeps module weight and assembly torque off the H-1 "
            "mount; nothing downstream of IP-DN changes",
            "flight representativeness: all test-article provisions are removable/additive and must not alter the "
            "flow path or anode area (HW-H1-09); the flight telemetry subset uses only quantities a PPU/controller "
            "can provide",
            "O2 service in the facility: hazards are known and addressed by procedure/design (cleaning, lubricants, "
            "cryopump regeneration, two barriers); a facility-selection constraint, not an architecture veto",
            "effective pumping speed: the required S_eff at the delivered-flow upper end is large "
            f"({der['S_eff_required']['total_N2_mdot_max_plus_Xe_upper'][_tkey(1e-5)]['value']:.4g} L/s at 1e-5 Torr, "
            f"{der['S_eff_required']['total_N2_mdot_max_plus_Xe_upper'][_tkey(5e-5)]['value']:.4g} L/s at 5e-5 Torr) - "
            "it constrains facility choice and T-PB-MAX; the knee region (low flow) needs far less throughput",
        ],
        "evidence_class_of_this_finding": "model-derived (from sourced inputs) + published recommended practice",
        "not_used": ["any Hall transport closure", "screening candidates", "abep_sim/plasma_devices.py",
                     "withdrawn v1.2-v1.6 numbers", "P5 calibration nuisance items"],
    }


def blockers_touched() -> list:
    return [
        {"blocker": 1, "text": "Hall-only sustainment at the actual atmospheric feed state, especially low flow and "
                               "high O2 fraction",
         "how": "defines the measurement chain that decides it (I_d(t) + extinction logic, per-gas MFC paths down to "
                "0.012 mg/s per gas and w_O2 0.42-0.60, feed pressure/temperature, p_b with every reading, S5 "
                "elevated-p_b check) and flags that the background-ingestion scale is largest at the low-flow knee; "
                "decides nothing"},
        {"blocker": 2, "text": "incremental benefit of RF/ECR after full bus-power accounting",
         "how": "same power channels at the same load planes in every arm incl. rf_source / ecr_source / ecr_magnet "
                "and generator DC input as efficiency evidence; the module-exchange fixture and SVC-1 shams keep "
                "installation effects out of R_arch; compressor stays reconstructed until the upstream ICD exists"},
        {"blocker": 3, "text": "Xe/cathode closure (no continuous Xe assistance; cathode Xe within the mass allocation)",
         "how": "Xe anode flow verified zero at every atmospheric reading; Xe cathode MFC with a full-scale window "
                "keeping 0.10 and 0.15 mg/s >= 20 % FS; per-mode Xe totals for the Xe ledger"},
    ]


def m16_rows() -> list:
    """Proposed rows for the M16 scheduler (A7 m16_as_scheduler). The M16 matrix itself is
    PENDING docs/budgets/subsystem_maturity/; subsystem names are the A5 baseline names."""
    M16 = _pending("fo_subsystem_maturity_matrix")
    return [
        {"subsystem": "sensors/diagnostics", "a5_group": "support",
         "matured_by_this_lane": "primary: ground diagnostic chain for the nine P1DQ quantities, qualification path "
                                 "S1a / S1-C4 / S1b, flight telemetry subset (ground_vs_flight)",
         "proposed_state": "BLOCKED",
         "blocking_item": "owner facility identification with a documented N2/O2 effective pumping speed at the "
                          "delivered-flow region and an O2 safety case (S1A-C5 / S1-C7 artifact; T-PB-MAX at LOCK-1)",
         "rollup_category": "test-readiness blocker", "m16_matrix": M16},
        {"subsystem": "mechanical/structural interfaces", "a5_group": "support",
         "matured_by_this_lane": "H-1 test fixture and module slot only (the flight structure is H2-7's)",
         "proposed_state": "BLOCKED",
         "blocking_item": "fo_preionizer_module_icd mechanical envelope + mounting datum and installation/removal "
                          "reproducibility items (docs/interfaces/preionizer_module/)",
         "rollup_category": "hardware-definition blocker", "m16_matrix": M16},
        {"subsystem": "control/FDIR", "a5_group": "support",
         "matured_by_this_lane": "contribution: S1a interlock list and flight telemetry subset",
         "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "m16_matrix": M16},
        {"subsystem": "RF pre-ionization module interface (reserved row)", "a5_group": "reserved_interface",
         "matured_by_this_lane": "contribution: fixture slot, SVC-1 shams, diagnostic access demands",
         "proposed_state": "RUNNING", "blocking_item": None, "rollup_category": None, "m16_matrix": M16},
    ]


def h3_procurement_inputs() -> list:
    def it(item, spec, ref="no product selected; published catalog data as reference only, no supplier contact"):
        return {"item": item, "specification_level_needed_to_order": spec, "reference": ref}

    return [
        it("thrust stand with in-situ calibrator (INS-01)", "principle (torsional or inverted pendulum, null-type "
           "preferred; owner decision), calibrated span 0 to >= H26-02, resolution <= H26-04, per-reading 1 sigma "
           "H26-03 (LOCK-2), mass capacity per H26-43 (PENDING H2-7), non-ferrous construction, thermal control, "
           "SI-traceable force calibration through an ISO/IEC 17025 scope (A4)"),
        it("module carrier and H-1 adapter (fixture)", "kinematic seat concept, envelope and datum from the "
           "pre-ionizer ICD (PENDING), non-ferromagnetic, isolation rating H26-45"),
        it("mass-flow controllers (INS-05)", "one per pure gas: N2 and O2 paths with 4 overlapping ranges each "
           "(H26-18/19), Xe cathode FS 0.15-0.50 mg/s (H26-21), Xe anode start range TBD; O2-cleaned; calibration "
           "on each gas, traceable, <= 12 months (REF-SNYDER2017 via W4); A4: at least three ranges per gas path"),
        it("power metering (INS-02) and RF/microwave load-plane sensors (INS-03)", "one simultaneously sampled V/I "
           "channel per bus_power_boundary_v1 component, per-channel repeatability H26-10 (LOCK-2), SI-traceable DC "
           "and RF/microwave calibration through an ISO/IEC 17025 scope (A4); frequencies not selected (HW-PIM-11)"),
        it("wide-band discharge-current probe and fast DAQ (INS-04, INS-18)", "exploratory band and sampling H26-16; "
           "common time base; simultaneous V and I"),
        it("pressure instruments (INS-06, INS-08)", "capacitance manometers (range PENDING H2-3), hot-cathode ion "
           "gauges calibrated on N2 and O2/N2, >= 10 Hz (H26-30)"),
        it("gaussmeter and positioning stage (INS-09)", "range H26-34 (PENDING H2-1 B_max), probe calibration in a "
           "reference field, stage keyed to H-1 fiducials"),
        it("RGA with near-cathode sampling (INS-11, INS-22)", "quantitative O2/N2/H2O capability for the AO programme "
           "(A3)"),
        it("plume diagnostics (INS-13..16)", "ExB with accelerating bias (H26-38), multi-grid RPA, guarded Faraday "
           "array on an arc >= H26-37, Langmuir probes - 'where feasible'"),
        it("thermocouples / pyrometer (INS-17, INS-23, INS-24)", "types and ranges PENDING H2-5; pyrometer only if the "
           "C-1 view exists (HW-C1-09)"),
        it("vacuum facility (owner channel)", "S_eff per H26-28 at T-PB-MAX, gauge positions H26-30/32, elevated-p_b "
           "injection H26-31, O2 safety case H26-FAC-06; facility selection and any contact are the owner's",
           ref="no facility named or contacted"),
        it("witness-coupon metrology lab", "per the approved metrology measurement specification (A4: approved as "
           "the procurement specification)", ref="no laboratory named or contacted"),
    ]


def h4_test_inputs() -> list:
    return [
        {"closes": "H26-03, H26-04, H26-06, H26-07", "stage": "S1a CD-01 then S1b",
         "measure": "force calibration repeatability, resolution, drift; Hall-on u_T at OP3"},
        {"closes": "H26-02, H26-05, H26-12", "stage": "LOCK-2", "measure": "adopted u_abs from the S1 calibration "
                                                                           "uncertainty budget"},
        {"closes": "H26-08", "stage": "S1b", "measure": "thermal time constants and zero drift over the dwell"},
        {"closes": "H26-10, H26-11", "stage": "S1a CD-03, S1b, LOCK-1", "measure": "channel calibration; ledger "
                                                                                    "efficiencies (H2-4)"},
        {"closes": "H26-13, H26-15, H26-16", "stage": "S1b", "measure": "I_d spectrum on HW-0, transients, I_d,ref"},
        {"closes": "H26-17..H26-22", "stage": "S1a CD-04", "measure": "per-gas MFC calibration across the ranges, "
                                                                      "zero drift, orientation"},
        {"closes": "H26-25, H26-26", "stage": "S1a cold flow", "measure": "P_feed and T_feed at each released flow"},
        {"closes": "H26-27, H26-28, H26-29", "stage": "S1a cold flow + S1b + S5", "measure": "S_eff by Eq. 9 on each "
                                                                                           "gas; Hall-on p_b at OP3; "
                                                                                           "2 x p_b check"},
        {"closes": "H26-33..H26-36", "stage": "S1a CD-05", "measure": "B(z) repeatability and hysteresis per "
                                                                     "configuration"},
        {"closes": "H26-37..H26-39", "stage": "S1b", "measure": "species/divergence capability on HW-0"},
        {"closes": "H26-47, H26-48", "stage": "S1a CD-02a then S1b", "measure": "K = 6 module-exchange cycles x r = 3; "
                                                                               "alignment reference; c1..c5 split"},
        {"closes": "H26-44, H26-45, H26-46", "stage": "S1a", "measure": "stand thermal drift with heat applied, "
                                                                       "isolation test, magnetic tare and M0/M0b maps"},
    ]


def milestones() -> dict:
    return {
        "A": "supports conditional selection as a precondition only: it defines the measurement chain and the H-1 "
             "fixture needed for the controlled HW-0 / HW-RF / HW-ECR experiment whose outcome (A / B / C / "
             "NO_VIABLE_CASE) is decided by measurement; no architecture is selected, ranked or eliminated here",
        "B": "physics-backed selection needs measured data: S1a -> LOCK-1 -> S1/S1b -> LOCK-2 -> Phase 1-3 with the "
             "instruments here demonstrated (S1-C4), and an admitted Hall closure for absolute performance (credible "
             "set empty)",
        "C": "proposal/PDR freeze needs the flight telemetry subset integrated with the PPU (H2-4) and control/FDIR, "
             "and the fixture/test-article items kept out of the flight mass (H2-7)",
    }


def references() -> list:
    """Every external source with the access actually made. 'accessed by this lane' entries were re-read on
    2026-09-29 (PDF text extraction; sha256 of the retrieved copy recorded; copies not redistributed)."""
    return [
        {"id": "REF-DANKANICH2017", "citation": "J. W. Dankanich, M. L. R. Walker, M. W. Swiatek, J. T. Yim, "
                                                "'Recommended Practice for Pressure Measurement and Calculation of "
                                                "Effective Pumping Speed in Electric Propulsion Testing', J. Propulsion "
                                                "and Power 33(3):668-680 (2017), doi:10.2514/1.B35478",
         "url": "https://hpepl.ae.gatech.edu/sites/default/files/Journal_Articles/JPP%20V33%20No3%20MayJune2017_PressureMeasurement.pdf",
         "retrieved_sha256": "d346026673f4f2225e39faa4f867a567bc5b55572dd263291bd5ef55e4935a0e",
         "access": "full text accessed by this lane 2026-09-29 (author-lab PDF, pdftotext): p. 670 ('industry "
                   "standard gas is nitrogen' for gauge calibration); p. 672 (reference gauge near the wall in the exit "
                   "plane, >= 0.6 chamber radii from the centreline and >= 1 m from the thruster outer diameter); p. 673 "
                   "(Eq. (9) effective pumping speed from measured minus base pressure, valid when the operating "
                   "pressure is >= 10x base; supplemental gas >= 2 m downstream); p. 677 (Sec. V: early SPT-100 guidance "
                   "5e-5 Torr for performance and 1.3e-5 Torr for near-field plume, whose basis does not cover "
                   "'applicability to thrusters beyond the SPT-100'; 'Hall thrusters in particular have sparse data'); "
                   "p. 678 (SPT-100 transportability study: below 1e-5 Torr necessary to identify the thrust-slope "
                   "change; discharge-current stability and breathing-mode frequency keep changing into the 1e-6 Torr "
                   "range; results 'insufficient to justify a set of absolute pressure requirements for general "
                   "thruster designs')"},
        {"id": "REF-TIGHE2015", "citation": "W. G. Tighe, R. Spektor, K. D. Diamant, H. Kamhawi, 'Effects of "
                                            "Background Pressure on the NASA 173M Hall Current Thruster Performance', "
                                            "IEPC-2015-152 / ISTS-2015-b-152, 34th IEPC, Kobe (2015)",
         "url": "https://electricrocket.org/IEPC/IEPC-2015-152_ISTS-2015-b-152.pdf",
         "retrieved_sha256": "ae0d684e811aaa36fb7d8d1ed75ed6c9d072fdf4c9ad3bd3a32f57fecfdb6839",
         "access": "full text accessed by this lane 2026-09-29: abstract ('Simple ingestion and ionization of the "
                   "background gases has been determined to be an inadequate explanation of increased thrust at higher "
                   "background pressure'; range ~3e-6 to ~3.5e-5 Torr; at 15 A a thrust reduction <= 2.5 % as pressure "
                   "was reduced to 6e-6 Torr; thrust increased by more than 3 % with the cathode raised 6 inches); "
                   "Sec. II.A ('a xenon pumping speed of ~250 kl/s'; pressures reported corrected by 0.348 for xenon relative to "
                   "nitrogen). Xenon, NASA-173M: context only, never a "
                   "value for H-1"},
        {"id": "REF-BYRNE2022", "citation": "M. P. Byrne, P. J. Roberts, B. A. Jorns, 'Coupling of Electrical and "
                                            "Pressure Facility Effects in Hall Effect Thruster Testing', IEPC-2022-377, "
                                            "37th IEPC, MIT (2022)",
         "url": "https://januselectricpropulsion.com/sites/default/files/2023-04/IEPC_2022_377_Byrne_Coupling%20of%20Electrical%20and%20Pressure%20Facility%20Effects%20in%20Hall%20Effect%20Thruster%20Testing.pdf",
         "retrieved_sha256": "f4e251d5de2dd1d6efe03e0d63207aa57d3b01ca138ab290691b81eb5314ec0a",
         "access": "full text accessed by this lane 2026-09-29: Sec. I (residual background gas affects 'the thrust, "
                   "cathode coupling potential, and divergence angle'; the 'conducting and grounded wall of the vacuum "
                   "facility ... provide[s] alternate current paths that do not exist on orbit'); Sec. II (thruster run "
                   "'cathode-tied and electrically isolated from the facility'); abstract (background pressure 'a "
                   "strong driver of how the thruster and plume couple to the facility')"},
        {"id": "REF-POLK2017", "citation": "J. E. Polk et al., 'Recommended Practice for Thrust Measurement in "
                                           "Electric Propulsion Testing', J. Propulsion and Power 33(3):539-555 "
                                           "(2017), doi:10.2514/1.B35564",
         "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7839308/",
         "access": "as accessed and recorded by W4 (instrumentation_definition_v1 references REF-POLK2017: stand types, "
                   "end-to-end in-situ calibration, >= 10 calibrations, thermal shrouds / active cooling, zero before "
                   "and after, active inclination control, line/cable tares, magnetic tare) and lane 25; not re-accessed "
                   "by this lane; exact wording - verify"},
        {"id": "REF-CHOUEIRI2001", "citation": "E. Y. Choueiri, 'Plasma oscillations in Hall thrusters', Physics of "
                                               "Plasmas 8(4):1411-1426 (2001), doi:10.1063/1.1354644",
         "access": "abstract only, as recorded by W4 (1 kHz - 60 MHz reviewed band by band); band-by-band values not "
                   "read (verify)"},
        {"id": "REF-BROWN2017", "citation": "D. L. Brown et al., 'Recommended Practice for Use of Faraday Probes in "
                                            "Electric Propulsion Testing', J. Propulsion and Power 33(3):582-613 "
                                            "(2017), doi:10.2514/1.B35696",
         "access": "as accessed and cited by lane 25 (Table A1, far field > 4 channel diameters); not re-accessed"},
        {"id": "REF-ROVEY2025", "citation": "J. L. Rovey et al., 'Recommended Practice for Use of ExB Probes in "
                                            "Electric Propulsion Testing', IEPC-2025-483",
         "access": "as accessed and cited by lane 25 / W4 INS-13; not re-accessed"},
        {"id": "REF-SNYDER2017", "citation": "J. S. Snyder et al., 'Recommended Practice for Flow Control and "
                                             "Measurement in Electric Propulsion Testing', J. Propulsion and Power "
                                             "33(3) (2017), doi:10.2514/1.B35644",
         "access": "as accessed and quoted by W4 INS-05 (1 % FS typical; per-gas calibration; <= 12 months); not "
                   "re-accessed"},
        {"id": "REF-XU2009", "citation": "K. G. Xu, M. L. R. Walker, 'High-power, null-type, inverted pendulum thrust "
                                         "stand', Rev. Sci. Instrum. 80(5):055103 (2009)",
         "access": "abstract only, as recorded by W4 (1 mN to 5 N range example; verify)"},
        {"id": "REF-MARCHIONI2020", "citation": "F. Marchioni, 'Design and Performance Measurements of a Long Channel "
                                                "Hall Thruster for Air-Breathing Electric Propulsion', MSc thesis, "
                                                "Politecnico di Torino (co-tutelle Stanford), 2020; ECHT extended-channel "
                                                "Hall thruster",
         "url": "https://webthesis.biblio.polito.it/14618/",
         "access": "not re-accessed by this lane; geometry (86 mm long, 10 mm channel height, '100 mm OD'; channel "
                   "radii not published) as recorded in CLAUDE.md 'Superseded / withdrawn' and docs/HISTORY.md "
                   "2026-09-26 (ECHT-N2 audit, hallthruster_bridge/identification/echt_n2/). Published analog only, "
                   "never a Vyovrinda design value"},
        {"id": "REF-ULVAC-CRYO", "citation": "ULVAC, 'Cryopump safety instructions' (manufacturer published "
                                             "trouble-shooting / safety page)",
         "url": "https://showcase.ulvac.co.jp/en/how-to/trouble-shooting/cryo-pump-safety.html",
         "access": "accessed by this lane 2026-09-29 (fetch-tool extraction; wording - verify): ozone can be a "
                   "by-product when oxygen is a process gas and can explode in the cryopump; 'Regenerate as frequently "
                   "and periodically as practical to minimize the amount of oxidizer present in the cryopump'; keep the "
                   "oxygen concentration in the cryopump below atmospheric when roughing; above 20 % O2 during "
                   "regeneration there is a danger of combustion or explosion of rotary pump oil; inert-gas purge "
                   "(e.g. N2) of the exhaust line. Reference only, no supplier contact"},
        {"id": "REF-EDWARDS-RV", "citation": "Edwards Vacuum, knowledge page on working with oil-sealed rotary vane "
                                             "pumps (manufacturer published page; title - verify)",
         "url": "https://www.edwardsvacuum.com/en-us/vacuum-pumps/knowledge/applications/working-with-oil-sealed-rotary-vane-pumps",
         "access": "accessed by this lane 2026-09-29 (fetch-tool extraction): 'Where a high concentration of oxygen or "
                   "other chemically reactive gases are present, highly inert, man-made lubricants are recommended'; "
                   "no concentration threshold stated. Reference only"},
        {"id": "REF-NSS1740-15", "citation": "NASA NSS 1740.15, 'Safety Standard for Oxygen and Oxygen Systems' "
                                             "(January 1996)",
         "url": "https://ntrs.nasa.gov/api/citations/19960021046/downloads/19960021046.pdf",
         "retrieved_sha256": "c2c73b31b7153580b06f00846a8083a8010be7aa010921da3c75c13cc1be0965",
         "access": "accessed by this lane 2026-09-29 (pdftotext): Sec. 101 scope (gaseous and liquid oxygen, not "
                   "oxygen-enriched mixtures, 'although many of the same considerations apply'); Sec. 104 (p. 1-2) "
                   "item c ('Oxygen systems shall be kept clean because organic compound contamination ...') and item f "
                   "(at least two barriers or safeguards so that at least two simultaneous undesired events must occur "
                   "before personnel injury)"},
        {"id": "REF-ASTM-G93", "citation": "ASTM G93/G93M, 'Standard Guide for Cleanliness Levels and Cleaning "
                                           "Methods for Materials and Equipment Used in Oxygen-Enriched Environments'",
         "access": "not accessed by this lane; named only as a candidate cleaning-level guide for the owner's safety "
                   "case (title from memory - verify)"},
    ]


def owner_questions() -> list:
    return [
        {"id": "H26Q-01", "question": "T-PB-MAX: set with the low-flow knee in view? The ingestion-scale planning table "
                                      "(H26-27, H26-29) is offered as an aid; the fractions are PROPOSED"},
        {"id": "H26Q-02", "question": "stand principle (torsional vs inverted pendulum) given the module mass change "
                                      "between arms (W4 open decision; FX-10)"},
        {"id": "H26Q-03", "question": "adopt the kinematic module carrier (module weight off IP-DN, H-1 never "
                                      "unbolted) as the fixture concept for the ICD installation/removal item?"},
        {"id": "H26Q-04", "question": "per-gas MFC paths: 4 overlapping ranges per pure-gas path at the 20 % FS floor "
                                      "(H26-18/19) vs A4 'at least three per gas path' computed on the total flow"},
        {"id": "H26Q-05", "question": "exploratory I_d(t) chain to the literature planning band edge (60 MHz, "
                                      "abstract-level source) for S1b, or a narrower band recorded as such?"},
        {"id": "H26Q-06", "question": "flight telemetry subset (ground_vs_flight) as the input to H2-4 / control-FDIR"},
        {"id": "H26Q-07", "question": "O2 safety case ownership and the cleaning standard (H26-52)"},
    ]


def compliance() -> list:
    return [
        "no thrust, efficiency, discharge-current or plasma-state prediction; every thrust/power number is an RFP "
        "value, an A5 allocation, a W4/lane-25 measurement-uncertainty target or a bound",
        "no Hall transport closure, screening candidate, abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number used",
        "no architecture selected, ranked or eliminated; architecture ids used exactly: hall_only, rf_hall, ecr_hall",
        "P5 calibration nuisance (registration, coil shape, beam-efficiency reading, facility interpretation) is never "
        "a design variable here",
        "Hall-closure uncertainty does not enter any upstream item (intake, compressor, gas chambers, valves)",
        "published/open sources only; no person, lab, facility or supplier contacted; access stated per reference",
        "only W3 configuration-item and plane ids are used (H-1, MC-1, C-1, FS-C, PS-C, SVC-1, PIM-0, PIM-RF, PIM-ECR, "
        "DIV-1, IP-UP, IP-DN, HALL_INLET_Z0); fixture features are FX ids inside the existing stand/mount element",
        "no module wired into abep_sim.archengine; no golden moves; only files under the lane directory and the lane "
        "test are written",
        "governance files are not pinned; owner decisions, the G0 record, verified merged deliverables and immutable "
        "snapshots are pinned by sha256; mutable drafts and modules are consumed by value and re-checked",
        "no value depends on a parallel (PENDING) lane at import or test time; pending_status() reports presence only",
        "Bundle 1 stays NO_BASELINE_YET; the credible Hall set stays empty; A5 numbers are allocations or requirements",
    ]


def build(root: str = ROOT) -> dict:
    der = derive(INPUTS)
    doc = {
        "schema": "abep_h2_lane_deliverable_v1",
        "id": "h2_6_diagnostics_fixture_v1",
        "lane": "fo_h2_6_diagnostics_fixture",
        "trigger": "T_H2_6_DIAGNOSTICS_FIXTURE",
        "owner_addendum": "A7 (wave H2)",
        "title": "H2-6 diagnostics + H-1 fixture: measurement chain for the Phase-1 decision quantities, H-1 "
                 "thrust-stand fixture with a repeatable pre-ionizer module slot, facility requirements",
        "status": "PRELIMINARY_DRAFT_PENDING_OWNER",
        "status_note": "H2 hardware design / preliminary-sizing lane (A7 h2_scope), not an architecture-selection lane. "
                       "Nothing here is approved, pre-registered, locked or ordered. Values are PRELIMINARY, PENDING a "
                       "named lane, or TBD with what they require. A5 numbers are allocations or requirements, never "
                       "predictions. Bundle 1 stays NO_BASELINE_YET; the credible Hall set is empty.",
        "base_commit": BASE_COMMIT,
        "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}",
        "test": "tests/test_h2_6_diagnostics_fixture.py",
        "authority_pins": [{"path": p, "sha256": s, "role": r, "immutable": True} for p, s, r in DECISION_PINS],
        "deliverable_pins": [{"path": p, "sha256": s, "role": r,
                              "kind": "verified merged deliverable or immutable snapshot, pinned at the base commit"}
                             for p, s, r in DELIVERABLE_PINS],
        "provenance_inputs": [{"path": p, "role": r, "kind": "mutable draft or module consumed by value (not a pin); "
                                                          "values re-checked by --verify-sources"}
                              for p, r in PROVENANCE_INPUTS],
        "governance_files_not_pinned": list(GOVERNANCE_NOT_PINNED),
        "context": {
            "bundle1_outcome": "NO_BASELINE_YET (unchanged)",
            "credible_hall_set": "EMPTY (no admitted Hall transport closure)",
            "a5_numbers": "allocations or requirements, never predictions",
            "lane_scope": "A7 h2_scope: H2 hardware design / preliminary-sizing lane, NOT an architecture-selection lane",
            "architecture_changing_blockers_A7": [
                "1 Hall-only sustainment at the actual atmospheric feed state, especially low flow and high O2 fraction",
                "2 incremental benefit of RF/ECR after full bus-power accounting",
                "3 Xe/cathode closure: no continuous Xe assistance; cathode Xe within the system mass allocation"],
        },
        "architectures": list(ARCHITECTURES),
        "configuration_items_used": ["H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR",
                                     "DIV-1"],
        "interface_planes_used": ["IP-UP", "IP-DN", "HALL_INLET_Z0"],
        "classification_legend": {
            "FLIGHT-REPRESENTATIVE": "the quantity/interface exists in the A5 flight baseline and is measured or "
                                     "provided the same way in flight",
            "H-1 TEST-ARTICLE-ONLY": "a provision on H-1/C-1/MC-1 that exists only on the test article (removable or "
                                     "additive; never alters the flight-representative flow path or anode area)",
            "GROUND/FACILITY-ONLY": "stand, facility, lab instrument or procedure"},
        "phase1_decision_quantities": [{"id": i, "text": t, "w4_decision_quantity_ids": w,
                                        "source": "A6 authorized_now.fo_phase1_prereg_framework (verbatim list); ids "
                                                  "from phase1_prereg_framework_v1.json decision_quantities"}
                                       for i, t, w in P1DQ],
        "inputs": INPUTS,
        "derived": der,
        "design_parameters": design_parameters(der),
        "measurement_map": measurement_map(),
        "fixture": fixture(),
        "facility": facility(der),
        "ground_vs_flight": ground_vs_flight(),
        "interface_demands": interface_demands(),
        "hard_incompatibility_check": hard_incompatibility_check(der),
        "architecture_changing_blockers_touched": blockers_touched(),
        "m16_rows": m16_rows(),
        "h3_procurement_inputs": h3_procurement_inputs(),
        "h4_test_inputs": h4_test_inputs(),
        "milestones": milestones(),
        "pending_lanes": [{"lane": l, "path": p, "what": w} for l, p, w in PENDING_LANES],
        "owner_questions": owner_questions(),
        "references": references(),
        "compliance": compliance(),
    }
    return doc


# ---------------------------------------------------------------------------------------------------------------------
# Markdown rendering (deterministic, from the JSON document only)
# ---------------------------------------------------------------------------------------------------------------------
def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return str(v).replace("|", "/")


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# H2-6 diagnostics + H-1 fixture")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| status | **{doc['status']}** |")
    a(f"| lane | `{doc['lane']}` (trigger `{doc['trigger']}`, owner addendum A7) |")
    a(f"| register (authoritative) | [`h2_6_diagnostics_fixture_v1.json`](h2_6_diagnostics_fixture_v1.json) |")
    a(f"| builder | [`build_h2_6_diagnostics_fixture.py`](build_h2_6_diagnostics_fixture.py) (`--write`, `--check`, "
      f"`--verify-sources`, `--pending-status`) |")
    a(f"| test | `{doc['test']}` |")
    a(f"| base commit | `{doc['base_commit'][:7]}` |")
    a("")
    a(doc["status_note"])
    a("")
    a("**Authority (immutable, pinned by sha256):**")
    a("")
    for p in doc["authority_pins"]:
        a(f"- `{p['path']}` - `{p['sha256']}` ({p['role']})")
    a("")
    a("**Verified deliverables and immutable snapshots (pinned by sha256 at the base commit):**")
    a("")
    for p in doc["deliverable_pins"]:
        a(f"- `{p['path']}` - `{p['sha256']}` ({p['role']})")
    a("")
    a("Mutable drafts and modules (" + ", ".join(f"`{p['path']}`" for p in doc["provenance_inputs"])
      + ") are consumed by value and re-checked by `--verify-sources`; they are not pinned. Governance files ("
      + ", ".join(f"`{g}`" for g in doc["governance_files_not_pinned"]) + ") are never pinned.")
    a("")
    a("## Summary")
    a("")
    der = doc["derived"]
    s_tot = der["S_eff_required"]["total_N2_mdot_max_plus_Xe_upper"]
    ing = der["ingestion_scale_N2"]["echt_analog_annulus"]["at_mdot_anode_min"]
    a("- **Every Phase-1 decision quantity (P1DQ-*) maps to W4 instruments** (measurement map below); every "
      "DECISIVE and CONDITION instrument of each P1DQ measurement chain is covered. eta_u is the weakest link: its "
      "inputs come from INS-13 (ExB) and INS-15 (Faraday), both AT_RISK in W4. This is a test-readiness risk, not an "
      "architecture veto.")
    a(f"- **Thrust stand:** calibrated span 0 to >= {_fmt(der['thrust_span_upper_mN_planning']['value'])} mN "
      f"(planning, u_abs = 1 %); per-reading 1 sigma at 12 mN "
      f"{_fmt(der['sigma_T_at_T_min_uN_by_n']['n=4']['value'])}-{_fmt(der['sigma_T_at_T_min_uN_by_n']['n=8']['value'])}"
      f" uN (n = 4-8, LOCK-2); resolution step no larger than that.")
    a(f"- **Facility:** holding the xenon-derived planning pressures at the delivered-flow upper end (N2 3.14 mg/s + "
      f"Xe cathode 0.15 mg/s) needs S_eff = {_fmt(s_tot[_tkey(1e-5)]['value'])} L/s at 1e-5 Torr and "
      f"{_fmt(s_tot[_tkey(5e-5)]['value'])} L/s at 5e-5 Torr. That is a facility-choice constraint.")
    a(f"- **Background ingestion matters most at the knee:** at the lowest candidate anode flow, the N2 one-way "
      f"background flux over the analog exit annulus is {_fmt(ing[_tkey(1e-5)]['value'])} of the anode flow at "
      f"1e-5 Torr and {_fmt(ing[_tkey(5e-5)]['value'])} at 5e-5 Torr (a scale, not a correction). p_b is logged "
      f"with every knee reading, and the S5 elevated-p_b check is kept.")
    a(f"- **MFCs:** pure-gas paths raise the turndown to "
      f"{_fmt(der['mfc_paths']['N2_path']['turndown']['value'])}:1 (N2) and "
      f"{_fmt(der['mfc_paths']['O2_path']['turndown']['value'])}:1 (O2), so 4 overlapping ranges per path are needed at "
      f"the 20 % FS floor. The Xe cathode MFC full scale is 0.15-0.50 mg/s.")
    a("- **Fixture:** the pre-ionizer module sits in its own kinematic carrier, so neither its weight nor assembly "
      "torque reaches IP-DN or the H-1 mount, and H-1 is never unbolted. SVC-1 carries every line in every "
      "configuration, with shams. Remount contributors c1..c5 are each mapped to a feature and to CD-02a (S1a) and "
      "S1b.")
    a("- **Hard incompatibility:** none found (section c).")
    a("")
    a("## (a) Design parameters")
    a("")
    a("| id | name | value | units | basis | evidence | status | class |")
    a("|---|---|---|---|---|---|---|---|")
    for p in doc["design_parameters"]:
        a(f"| {p['id']} | {_fmt(p['name'])} | {_fmt(p['value'])} | {_fmt(p['units'])} | {p['basis']} | "
          f"{p['evidence_class']} | {_fmt(p['status'])} | {p['flight_classification']} |")
    a("")
    a("Sources and notes per parameter are in the JSON (`design_parameters[].source`, `.note`).")
    a("")
    a("## (1) Measurement list mapped to the Phase-1 decision quantities")
    a("")
    a("Phase-1 decision quantities (A6 list, framework ids): "
      + "; ".join(f"{d['id']} {d['text']}" for d in doc["phase1_decision_quantities"]))
    a("")
    a("| id | quantity | P1DQ | INS | INS-P | CD | qualifying steps | class |")
    a("|---|---|---|---|---|---|---|---|")
    for m in doc["measurement_map"]:
        steps = "; ".join(f"{q['stage']}: {q['what']}" for q in m["qualification"])
        a(f"| {m['id']} | {_fmt(m['quantity'])} | {', '.join(m['phase1_decision_quantities']) or '-'} | "
          f"{', '.join(m['instruments'])} | {', '.join(m['procedures']) or '-'} | "
          f"{', '.join(m['capability_demo']) or '-'} | {_fmt(steps)} | {m['flight_classification']} |")
    a("")
    a("**Known effect of background pressure on Hall operation (H26-MEAS-07):**")
    a("")
    for e in doc["measurement_map"][6]["known_effect_on_hall_operation"]:
        a(f"- {e}")
    a("")
    a("## (2) H-1 fixture")
    a("")
    fx = doc["fixture"]
    a(fx["principle"])
    a("")
    a("| id | feature | description | class | status |")
    a("|---|---|---|---|---|")
    for f in fx["features"]:
        a(f"| {f['id']} | {_fmt(f['name'])} | {_fmt(f['description'])} | {f['flight_classification']} | "
          f"{_fmt(f['status'])} |")
    a("")
    a("**SVC-1 service-line bundle (present in every configuration):**")
    a("")
    a("| line | used by | sham in |")
    a("|---|---|---|")
    for s in fx["service_line_bundle"]:
        a(f"| {_fmt(s['line'])} | {s['arms']} | {', '.join(s['sham_in']) or '-'} |")
    a("")
    rr = fx["remount_reproducibility"]
    a(f"**Remount reproducibility.** {rr['requirement']}. {rr['series']}. ICD item: {rr['icd_item']}.")
    a("")
    a("| contributor | features | measured in |")
    a("|---|---|---|")
    for c in rr["contributors"]:
        a(f"| {c['id']} {c['name']} | {', '.join(c['features'])} | {'; '.join(c['measured_in'])} |")
    a("")
    a("**Proposed configuration-change procedure:**")
    a("")
    for i, s in enumerate(fx["configuration_change_procedure_proposed"], 1):
        a(f"{i}. {s}")
    a("")
    a("## (3) Facility requirements")
    a("")
    fac = doc["facility"]
    a("| id | requirement | values | stage | status |")
    a("|---|---|---|---|---|")
    for r in fac["requirements"]:
        a(f"| {r['id']} | {_fmt(r['requirement'])} | {_fmt(r['values'])} | {_fmt(r['stage'])} | {_fmt(r['status'])} |")
    a("")
    a("**Required effective pumping speed (L/s):**")
    a("")
    pbs = [_tkey(p) for p in doc["inputs"]["p_b_planning_Torr"]["value"]]
    a("| case | " + " | ".join(pbs) + " |")
    a("|---|" + "---|" * len(pbs))
    for case, row in fac["pumping_speed_table_L_per_s"].items():
        a(f"| {case} | " + " | ".join(_fmt(row[p]) for p in pbs) + " |")
    a("")
    a(fac["pumping_speed_note"])
    a("")
    a("**N2 ingestion scale (one-way background flux x exit area / anode flow):**")
    a("")
    a("| area | flow | " + " | ".join(pbs) + " |")
    a("|---|---|" + "---|" * len(pbs))
    for area, d in der["ingestion_scale_N2"].items():
        for fl, row in d.items():
            a(f"| {area} | {fl} | " + " | ".join(_fmt(row[p]["value"]) for p in pbs) + " |")
    a("")
    a(fac["ingestion_scale_note"] + ".")
    a("")
    a("**O2 safety:**")
    a("")
    for o in fac["o2_safety"]:
        a(f"- {o['item']} - {o['basis']} ({o['status']})")
    a("")
    a("## (4) Ground-only vs flight-representative diagnostics")
    a("")
    a("| diagnostic | class | flight telemetry subset | flight counterpart |")
    a("|---|---|---|---|")
    for g in doc["ground_vs_flight"]:
        a(f"| {_fmt(g['diagnostic'])} | {g['flight_classification']} | {_fmt(g['flight_telemetry_subset'])} | "
          f"{_fmt(g['flight_counterpart'])} |")
    a("")
    a("## (b) Interface demands")
    a("")
    a("| from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['from']} | {d['to']} | {_fmt(d['quantity'])} | {_fmt(d['value'])} | {_fmt(d['units'])} | "
          f"{_fmt(d['status'])} |")
    a("")
    a("## (c) Hard-incompatibility check")
    a("")
    h = doc["hard_incompatibility_check"]
    a(f"**Verdict: {h['verdict']}.** Evidence class: {h['evidence_class_of_this_finding']}. Checked:")
    a("")
    for c in h["what_was_checked"]:
        a(f"- {c}")
    a("")
    a("## (d) Architecture-changing blockers touched (A7)")
    a("")
    for b in doc["architecture_changing_blockers_touched"]:
        a(f"- **Blocker {b['blocker']}** ({b['text']}): {b['how']}")
    a("")
    a("## (e) M16 rows (proposed)")
    a("")
    a("| subsystem | matured by this lane | proposed state | blocking item | rollup |")
    a("|---|---|---|---|---|")
    for r in doc["m16_rows"]:
        a(f"| {r['subsystem']} | {_fmt(r['matured_by_this_lane'])} | {r['proposed_state']} | "
          f"{_fmt(r['blocking_item'])} | {_fmt(r['rollup_category'])} |")
    a("")
    a("## (f) H3 procurement inputs (long-lead)")
    a("")
    for i in doc["h3_procurement_inputs"]:
        a(f"- **{i['item']}**: {i['specification_level_needed_to_order']} ({i['reference']})")
    a("")
    a("## (g) H4 test inputs")
    a("")
    a("| closes | stage | measure |")
    a("|---|---|---|")
    for t in doc["h4_test_inputs"]:
        a(f"| {t['closes']} | {t['stage']} | {_fmt(t['measure'])} |")
    a("")
    a("## (h) Milestones")
    a("")
    for k in ("A", "B", "C"):
        a(f"- **{k}:** {doc['milestones'][k]}")
    a("")
    a("## Pending lanes (values marked PENDING)")
    a("")
    for p in doc["pending_lanes"]:
        a(f"- `{p['lane']}` - `{p['path']}`: {p['what']}")
    a("")
    a("## Owner questions (PROPOSED)")
    a("")
    for q in doc["owner_questions"]:
        a(f"- **{q['id']}**: {q['question']}")
    a("")
    a("## References")
    a("")
    for r in doc["references"]:
        url = f" <{r['url']}>" if r.get("url") else ""
        a(f"- **{r['id']}**: {r['citation']}{url}. Access: {r['access']}.")
    a("")
    a("## Compliance")
    a("")
    for c in doc["compliance"]:
        a(f"- {c}")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------------------------------------------------
# Verification helpers (lazy; nothing here runs at import time)
# ---------------------------------------------------------------------------------------------------------------------
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_pins(root: str = ROOT) -> list:
    errs = []
    for rel, sha, _ in DECISION_PINS + DELIVERABLE_PINS:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            errs.append(f"pinned file missing: {rel}")
        elif _sha256(p) != sha:
            errs.append(f"pinned file altered (re-pin deliberately): {rel}")
    return errs


def p1dq_coverage(root: str = ROOT) -> list:
    """For each Phase-1 decision quantity of the (pinned) framework, every DECISIVE / CONDITION instrument of its
    measurement chain must appear in a measurement_map row mapped to that quantity. Returns the gaps."""
    fw = _load(root, "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json")
    mm = measurement_map()
    gaps = []
    ids_here = {i for i, _t, _w in P1DQ}
    ids_fw = {q["id"] for q in fw["decision_quantities"]}
    if ids_here != ids_fw:
        gaps.append(f"P1DQ id set differs from the framework: {sorted(ids_here ^ ids_fw)}")
    for q in fw["decision_quantities"]:
        covered = set()
        for m in mm:
            if q["id"] in m["phase1_decision_quantities"]:
                covered.update(m["instruments"])
        for c in q["measurement_chain"]:
            if c["role"] in ("DECISIVE", "CONDITION") and c["ins_id"] not in covered:
                gaps.append(f"{q['id']}: {c['role']} instrument {c['ins_id']} not in any mapped measurement row")
    return gaps


def _load(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return json.load(f)


def _by_id(lst, i):
    for x in lst:
        if isinstance(x, dict) and x.get("id") == i:
            return x
    raise KeyError(i)


def _constants(root: str) -> dict:
    tree = ast.parse(open(os.path.join(root, CONSTP), encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("K_B", "AMU") and isinstance(node.value, ast.Constant):
                out[name] = node.value.value
            if name == "M_SPECIES" and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(v, ast.BinOp) and isinstance(v.left, ast.Constant):
                        out[f"M_{k.value}_u"] = v.left.value
        if isinstance(node, ast.ClassDef) and node.name == "RFPConstraints":
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.value, ast.Constant):
                    out[f"RFP.{st.target.id}"] = st.value.value
    return out


def verify_sources(root: str = ROOT) -> list:
    """Value-level check of consumed inputs against their live repository sources (lazy; raises nothing on drift,
    returns a list of discrepancies; a missing source file is reported, never filled)."""
    errs = list(verify_pins(root))

    def cmp(name, got, want, rel=1e-9):
        if isinstance(want, (int, float)) and isinstance(got, (int, float)):
            if not math.isclose(float(got), float(want), rel_tol=rel, abs_tol=0.0):
                errs.append(f"{name}: live source {got!r} != consumed {want!r}")
        elif got != want:
            errs.append(f"{name}: live source {got!r} != consumed {want!r}")

    def V(k):
        return INPUTS[k]["value"]

    try:
        c = _constants(root)
        cmp("K_B", c.get("K_B"), V("K_B"))
        cmp("AMU", c.get("AMU"), V("AMU"))
        for g in ("N2", "O2", "Xe"):
            cmp(f"M_{g}_u", c.get(f"M_{g}_u"), V(f"M_{g}_u"))
        cmp("thrust_min_mN", c.get("RFP.thrust_min_mN"), V("thrust_min_mN"))
        cmp("thrust_max_mN", c.get("RFP.thrust_max_mN"), V("thrust_max_mN"))
        cmp("power_max_W", c.get("RFP.power_max_W"), V("power_max_W"))
        cmp("firing_hours_min_h", c.get("RFP.ignition_hours"), V("firing_hours_min_h"))
    except FileNotFoundError as e:
        errs.append(f"source missing: {e}")
    try:
        a5 = _load(root, A5P)
        xa = a5["xe_mass_allocation"]
        cmp("mdot_xe_cathode_design_mgps", xa["cathode_flow_design_target_mg_s"], V("mdot_xe_cathode_design_mgps"))
        cmp("mdot_xe_cathode_upper_mgps", xa["cathode_flow_experimental_upper_test_point_mg_s"],
            V("mdot_xe_cathode_upper_mgps"))
        if "0.42-0.60" not in a5["phase1_branch_decision"]["test_matrix"]:
            errs.append("w_O2_range: A5 test_matrix no longer states 0.42-0.60")
        allo = {x["quantity"]: x["value"] for x in a5["allocations_and_requirements"]}
        if allo.get("thrust operating target") != "15-22 mN":
            errs.append("a5_thrust_target_mN: A5 allocation text changed")
        if allo.get("bus-power design allocation") != "<= 1.30-1.35 kW":
            errs.append("a5_pbus_allocation_W: A5 allocation text changed")
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"A5 source: {e!r}")
    try:
        w1 = _load(root, W1P)["mfc_range_requirement"]
        cmp("mdot_anode_min_kgps", w1["mdot_min_kgps"], V("mdot_anode_min_kgps"))
        cmp("mdot_anode_max_kgps", w1["mdot_max_kgps"], V("mdot_anode_max_kgps"))
        cmp("mdot_anode_max_accum_kgps", w1["mdot_max_with_accumulation_kgps"], V("mdot_anode_max_accum_kgps"))
        cmp("mdot_O2_max_W1_kgps", w1["O2_max_kgps"], V("mdot_O2_max_W1_kgps"))
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"W1 source: {e!r}")
    try:
        w4 = _load(root, W4P)
        for n in ("4", "6", "8"):
            cmp(f"u_T_max_by_n[{n}]", w4["requirement_basis"]["lane25_by_n"][n]["u_T_max"]["value"], V("u_T_max_by_n")[n])
            cmp(f"u_P_max_by_n[{n}]", w4["requirement_basis"]["lane25_by_n"][n]["u_P_max"]["value"], V("u_P_max_by_n")[n])
        cmp("k_one_sided", w4["derived"]["k_one_sided"]["value"], V("k_one_sided"))
        pt = {t["id"]: t["value"] for t in w4["proposed_thresholds"]}
        cmp("u_abs_planning(T)", pt["I-U-ABS-T"], V("u_abs_planning"))
        cmp("u_abs_planning(P)", pt["I-U-ABS-P"], V("u_abs_planning"))
        cmp("I_d_noise_floor_frac", pt["I-U-ID-FLOOR"], V("I_d_noise_floor_frac"))
        grid = sorted(float(k) for k in w4["derived"]["absolute_thrust_gate"])
        cmp("u_abs_grid", grid, [float(x) for x in V("u_abs_grid")])
        cmp("mfc_accuracy_fs", w4["derived"]["mfc_relative_u_by_setpoint_fraction"]["1.0"]["value"],
            V("mfc_accuracy_fs"))
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"W4 source: {e!r}")
    try:
        w3 = _load(root, W3P)
        out = w3["derived_numbers"]["outputs"]
        cmp("I_d_bound_A", out["I_d_bound_envelope_max_A"]["value"], V("I_d_bound_A"))
        cmp("theta_align_max_n4_deg", out["theta_align_max_n4_deg"]["value"], V("theta_align_max_n4_deg"))
        cmp("B_res_2p45GHz_T", out["B_res_ecr_2p45GHz_T"]["value"], V("B_res_2p45GHz_T"))
        cmp("B_res_5p8GHz_T", out["B_res_ecr_5p8GHz_T"]["value"], V("B_res_5p8GHz_T"))
        cmp("u_inst_max_n4", w3["derived_numbers"]["inputs"]["u_inst_max_n4"]["value"], V("u_inst_max_n4"))
        env01 = _by_id(w3["requirements"], "HW-ENV-01")
        cmp("V_d_rating_upper_V", env01["values"]["V_d_rating_upper_V"]["value"], V("V_d_rating_upper_V"))
        svc02 = _by_id(w3["requirements"], "HW-SVC-02")
        cmp("calibrations_min", svc02["values"]["calibrations_before_min"]["value"], V("calibrations_min"))
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"W3 source: {e!r}")
    try:
        l25 = _load(root, L25P)
        th = {t["id"]: t.get("value") for t in l25["thresholds"]}
        cmp("remount_K", th["T-S1-REMOUNT-CYCLES"], V("remount_K"))
        cmp("remount_r", th["T-S1-READINGS-PER-CYCLE"], V("remount_r"))
        cmp("pb_elev_factor", th["T-PB-ELEV-FACTOR"], V("pb_elev_factor"))
        cmp("S_eff N2 1e-5 Torr cross-check", l25["derived_numbers"]["S_eff_required_per_mgps"]["N2"]["1.0e-05 Torr"]["value"],
            derive(INPUTS)["S_eff_per_mgps"]["N2"][_tkey(1e-5)]["value"], rel=1e-4)
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"lane 25 source: {e!r}")
    try:
        cd = _load(root, CDP)
        pt = {t["id"]: t["value"] for t in cd["proposed_thresholds"]}
        cmp("mfc_min_fraction_fs", pt["CD-P-MFC-MINFRAC"], V("mfc_min_fraction_fs"))
        cmp("cd_bz_maps", pt["CD-P-BZ-MAPS"], V("cd_bz_maps"))
        cmp("cd_bz_cycles", pt["CD-P-BZ-CYCLES"], V("cd_bz_cycles"))
    except (FileNotFoundError, KeyError) as e:
        errs.append(f"capability demo source: {e!r}")
    return errs


def pending_status(root: str = ROOT) -> list:
    """Lazy resolution of the parallel (PENDING) lanes. Reports presence only; never reads content into values."""
    out = []
    for lane, path, what in PENDING_LANES:
        present = os.path.isdir(os.path.join(root, path))
        out.append({"lane": lane, "path": path, "state": "PRESENT_NOT_CONSUMED" if present else "MISSING_IN_CHECKOUT",
                    "consequence": "values stay 'PENDING <path>' until an integration pass consumes the verified lane"})
    return out


def _dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def outputs(root: str = ROOT) -> dict:
    doc = build(root)
    return {JSON_NAME: _dump(doc), MD_NAME: render_md(doc)}


def check(root: str = ROOT) -> list:
    errs = []
    for name, text in outputs(root).items():
        p = os.path.join(HERE, name)
        if not os.path.exists(p):
            errs.append(f"{name} missing (run --write)")
            continue
        with open(p, encoding="utf-8") as f:
            if f.read() != text:
                errs.append(f"{name} differs from a fresh build (run --write)")
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--verify-sources", action="store_true")
    g.add_argument("--pending-status", action="store_true")
    a = ap.parse_args(argv)
    if a.write:
        for name, text in outputs().items():
            with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
                f.write(text)
        print("written:", ", ".join(outputs()))
        return 0
    if a.check:
        errs = check()
    elif a.verify_sources:
        errs = verify_sources()
    else:
        print(json.dumps(pending_status(), indent=1))
        return 0
    for e in errs:
        print("ERROR:", e, file=sys.stderr)
    print("OK" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
