#!/usr/bin/env python3
"""M16 subsystem maturity matrix (fo_subsystem_maturity_matrix, owner addendum A6): deterministic builder.

The central execution dashboard for the A5 Proposal Reference Architecture: one row per A5 baseline subsystem (16, names
read verbatim from A5 ``architecture``) plus the reserved RF pre-ionization module interface (row 17, reserved, not
baseline flight hardware). Nine columns per row, in this order:

    requirement -> allocation -> interface_status -> preliminary_design -> evidence_status -> procurement_status
    -> analysis_test_needed -> blocker -> owner

Usage::

    python docs/budgets/subsystem_maturity/build_subsystem_maturity.py --write   # write JSON + Markdown
    python docs/budgets/subsystem_maturity/build_subsystem_maturity.py --check   # committed files == rebuild (exit 1 if not)

What the builder does and does not do
  * The row CONTENT (which requirement, which allocation, which ids) is curated in ``ROWS`` below; every entry cites the
    base file it was read from. The builder never computes a physical or performance number.
  * It verifies the pinned decision files (A4, A5, A6, G0) by sha256 and refuses to build on a mismatch.
  * It resolves EVERY typed reference id (HW-*, INS-*, S1A-*, S1-*, D-xx, MCQ-*, IF-*, G-xx, BOM items, RI-*, ...) against
    the base file that defines it and raises on an unknown id, so no id is invented.
  * It reads the live state of referenced gate items (S1a/S1 condition states, LOCK-1 decision statuses, MCQ states,
    hardware-requirement statuses, BOM CBE bases, ICD field statuses) and derives the interface status (FROZEN /
    PARTIAL / OPEN) by a fixed rule.
  * Three parallel lanes (pre-ionizer ICD, Xe ledger, Phase-1 pre-registration framework) do not exist in the base. Their
    paths are probed LAZILY: missing -> PENDING_PARALLEL_LANE; present -> PRESENT_NOT_YET_INTEGRATED with file sha256 and
    a top-level ``status`` field if the file has one. Their content is never interpreted or copied into a cell; a
    present deliverable is integrated by a reviewed revision of this matrix.

Pure standard library. Deterministic: no clock, no randomness, sorted file listings, fixed JSON formatting. Nothing
here is wired into archengine; no frozen data, golden, prereg or campaign file is read for writing or modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DEFAULT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REL = "docs/budgets/subsystem_maturity"
OUT_JSON = "subsystem_maturity_v1.json"
OUT_MD = "SUBSYSTEM_MATURITY.md"
SCRIPT_REL = f"{REL}/build_subsystem_maturity.py"

# --------------------------------------------------------------------------------------------------------------------
# Pins (immutable inputs only; mutable governance files are never pinned)
# --------------------------------------------------------------------------------------------------------------------
A4 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"
A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0 = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
PINS = {
    A4: "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4",
    A5: "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    A6: "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    G0: "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
}

# Base inputs read (verified deliverables at the base commit). Their sha256 is recorded as provenance of this build.
ICD_MD = "docs/interfaces/UPSTREAM_ICD.md"
ICD_SCHEMA = "schemas/interfaces/upstream_icd_v1.json"
HWDEF = "docs/experiments/hardware/hardware_requirements_v1.json"
INSDEF = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
METROLOGY = "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json"
S1A_COND = "docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json"
S1A_STAT = "docs/experiments/s1a_readiness/s1a_readiness_status_current.json"
S1_COND = "docs/experiments/s1_readiness/s1_readiness_conditions_v1.json"
S1_STAT = "docs/experiments/s1_readiness/s1_readiness_status_current.json"
LOCK1 = "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"
MCQ = "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json"
AOL = "docs/experiments/lifetime_ao/ao_lifetime_register_v5.json"
BOM = "docs/architecture_comparison/mass_bom/mass_bom_v1.json"
AUX = "docs/architecture_comparison/aux_bus/aux_bus_comparison_v1.json"
PWRB = "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md"
VETO = "docs/architecture_comparison/veto_layer/veto_layer_v1.json"
CMP = "docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json"
CATHI = "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json"
CATHD = "docs/evidence/cathode/cathode_evidence_v1.json"
RTM = "docs/traceability/rtm_v1.json"
HGM = "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"
HGS = "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json"
DFS = "schemas/controls/dual_feed_state_machine_v1.json"
FSC = "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json"
B1 = "docs/milestones/bundle1/bundle1_v5.json"
W5 = "docs/validation/hall_transport_v2_prereg/hall_transport_v2_prereg_DRAFT.json"
THL = "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md"
BOUNDARY_PY = "abep_sim/arch_boundary.py"
BASE_INPUTS = (ICD_MD, ICD_SCHEMA, HWDEF, INSDEF, METROLOGY, S1A_COND, S1A_STAT, S1_COND, S1_STAT, LOCK1, MCQ, AOL, BOM,
               AUX, PWRB, VETO, CMP, CATHI, CATHD, RTM, HGM, HGS, DFS, FSC, B1, W5, THL, BOUNDARY_PY)

# Evidence matrices named in the lane contract (paths only; existence is checked).
EVIDENCE_MATRICES = {
    "rf_source": "docs/evidence/rf_source/rf_evidence_matrix.json",
    "ecr_source": "docs/evidence/ecr_source/ecr_evidence_matrix.json",
    "hall_sustainment": "docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
    "cathode": "docs/evidence/cathode/cathode_evidence_v1.json",
    "wall_life": "docs/evidence/wall_life/sputter_yield_db_v1.json",
}

# Parallel lanes (A6 authorized_now; they run simultaneously with this lane and are NOT in the base).
PARALLEL = {
    "fo_preionizer_module_icd": ["docs/interfaces/preionizer_module", "schemas/interfaces/preionizer_module_icd_v1.json"],
    "fo_xe_system_ledger": ["docs/budgets/xe_ledger"],
    "fo_phase1_prereg_framework": ["docs/experiments/phase1_prereg_framework"],
}

# Gate sequence, verbatim from A6 authorized_now.fo_phase1_prereg_framework (checked at build time).
A6_SEQUENCE_TEXT = "S1a -> LOCK-1 -> W5 freeze -> S1/S1b -> LOCK-2 -> Phase 1"
GATES = ["S1a", "LOCK-1", "W5 freeze", "S1/S1b", "LOCK-2", "Phase 1"]
BEYOND = {
    "PHASE1_BRANCH_DECISION": "resolved only BY Phase 1 (A5 phase1_branch_decision: A hall_only / B rf_hall / C ecr_hall / "
                              "NO_VIABLE_CASE); blocks the propulsion-branch decision, not entry to Phase 1",
    "FLIGHT_DESIGN_FREEZE": "not on the Phase-1 test path (Phase 1 uses the lab feed system FS-C and lab supplies PS-C); "
                            "blocks flight design freeze / Milestone C",
}

# A6 frozen Phase-1 decision-quantity names (verbatim substrings of A6 fo_phase1_prereg_framework). The P1DQ-* labels are
# local to this matrix; the parallel framework lane assigns its own ids.
P1DQ = {
    "P1DQ-SUST": "sustainment",
    "P1DQ-TPBUS": "T/P_bus",
    "P1DQ-ETAU": "eta_u",
    "P1DQ-ENV": "operating-envelope width",
    "P1DQ-IGN": "ignition/restart behaviour",
    "P1DQ-STAB": "stability/oscillation",
    "P1DQ-TABS": "absolute thrust compatibility",
    "P1DQ-PBUS": "full bus-power compatibility",
    "P1DQ-NOXE": "no continuous Xe augmentation",
}

BLOCKER_CATEGORIES = {
    "propulsion physics": "the blocking item is an unmeasured / unvalidated discharge-physics quantity (sustainment, "
                          "utilization, stability) that only H-1 measurement or an admitted closure can supply",
    "cathode-Xe": "the blocking item is the cathode or the stored/metered Xe (selection, minimum flow, Xe ledger terms, "
                  "Xe-mode durations)",
    "mass": "the blocking item is a missing mass basis or mass allocation",
    "thermal": "the blocking item is a missing thermal design input, rejection path or thermal limit",
    "compressor": "the blocking item is compressor evidence or the compressor concept (DI-1.4)",
    "unresolved interface": "the blocking item is an interface quantity, boundary or configuration that is not defined "
                            "or not frozen (ICD, feed state, mounting / module interface, bus voltage)",
    "procurement": "the blocking item is hardware, instruments or a facility that is not yet selected, specified, "
                   "available or calibrated (incl. the owner approval that depends on their real ratings)",
}

RISKS_SOURCE = f"{A5}#architecture_closing_risks"
PLACEHOLDERS = ("TBD", "UNKNOWN - owner to confirm", "OWNER_TO_ASSIGN", "TO_BE_ALLOCATED", "NONE")

# --------------------------------------------------------------------------------------------------------------------
# Row content (curated; every statement cites the base file it comes from)
# --------------------------------------------------------------------------------------------------------------------
ICD = "docs/interfaces/UPSTREAM_ICD.md (schemas/interfaces/upstream_icd_v1.json)"
OWNER_BASIS = ("no accountable party for this subsystem is recorded in the base (searched: A4, A5, A6, "
               "hardware_requirements_v1, instrumentation_definition_v1, mass_bom_v1, lock1_decision_brief_v1); "
               "the lane registry names lanes, not accountable persons")
PROC_UNKNOWN = "UNKNOWN - owner to confirm"
HW_NOT_ORDERED = ("hardware_requirements_v1 status_note: requirements specification only; 'Nothing here is approved, "
                  "pre-registered or ordered'")


def _row(key, group, index, **cols):
    return {"key": key, "group": group, "index": index, **cols}


ROWS = [
    # ---------------------------------------------------------------- atmospheric branch
    _row(
        "intake", "atmospheric_branch", 0,
        requirement={
            "summary": "RFP 180-230 km (RFP-ALT, air RFP-PROP); derived: molecular-entrance inlet >= 0.098-0.377 m2 at b = 0.25 (A4)",
            "items": [
                {"text": "operate over 180-230 km", "class": "RFP (secondary in-repo transcription; verify against RFP document)", "source": f"{RTM}#RFP-ALT"},
                {"text": "atmospheric propellant (air) is the primary discharge feed", "class": "RFP + A5 decision", "source": f"{RTM}#RFP-PROP; {A5}#decision_statement"},
                {"text": "molecular-entrance constraint: 0.098-0.377 m2 minimum inlet at b = 0.25; intake/compressor sizing is a spacecraft-level driver before flight geometry is locked", "class": "derived (owner-recorded, A4)", "source": f"{A4}#decisions.intake_sizing"},
            ],
            "refs": ["RTM:RFP-ALT", "RTM:RFP-PROP"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [],
                    "note": "no intake mass or power sub-allocation exists; the A5 system allocations (<= 34-36 kg, <= 1.30-1.35 kW) are not sub-allocated",
                    "sources": [f"{A5}#allocations_and_requirements", f"{BOM}#items[intake].cbe (basis TBD)"], "refs": ["BOM:intake"]},
        interface={"docs": {"upstream_icd": ["IF-A0", "IF-A1"]},
                   "note": "free stream -> aperture and intake -> filter records exist (DRAFT); IF-A0 V_rel never produced (G-10), species-selective collection lost (G-02)",
                   "refs": ["ICDGAP:G-10", "ICDGAP:G-02"]},
        design={"summary": "NONE (Vyovrinda intake geometry); PROPOSED candidate geometries G10/G20 in the feed-state closure, not frozen (DI-1.1/DI-1.2)",
                "sources": [f"{FSC}#owner_decisions_DI1 (DI-1.1, DI-1.2)", f"{BOM}#items[intake].cbe"]},
        evidence={"summary": "model-derived only (frozen TPMC ROM abep_sim/intake_tpmc.py; feed-state closure from assumed inputs); no evidence matrix for the intake",
                  "classes": ["model-derived"], "matrices": [], "sources": [f"{FSC}#test_points (evidence_class 'model-derived (from assumed inputs)')"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[intake]"]},
        needed={"summary": "owner DI-1.1 (area sizing rule), DI-1.2 (geometry), DI-1.3 (accommodation); drag/mass budget from the spacecraft",
                "refs": ["S1:S1-C3"], "sources": [f"{FSC}#owner_decisions_DI1"],
                "note": "S1-C3 accepts DI-1 frozen OR explicitly labelled ground-qualification feed points, so the flight intake does not gate S1"},
        blocker={"item": "owner decisions DI-1.1 / DI-1.2 (intake area sizing rule and geometry) not taken; A4 records intake sizing as a spacecraft-level driver",
                 "category": "unresolved interface", "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE",
                 "decision_by": f"owner ({FSC}#owner_decisions_DI1)", "sources": [f"{FSC}#owner_decisions_DI1", f"{A4}#decisions.intake_sizing"]},
        risks={"1": "contributing: sets delivered flow (<= ~3.2 mg/s) and O2 fraction (0.42-0.60) seen by the discharge",
               "4": "contributing: mass term (and spacecraft drag)"},
    ),
    _row(
        "filter", "atmospheric_branch", 1,
        requirement={
            "summary": "A5 baseline chain element; functional requirement TBD - requires a filter concept (ICD owner question 1, contamination scope G-11)",
            "items": [
                {"text": "protective/filter stage between intake and compressor", "class": "A5 decision (architecture element)", "source": f"{A5}#architecture.atmospheric_branch"},
                {"text": "TBD - requires the filter concept and the contaminant list (which contaminants, from which cited sources)", "class": "TBD", "source": f"{ICD_MD}#9 (owner questions 1 and 5)"},
            ],
            "refs": ["ICDGAP:G-01", "ICDGAP:G-11"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no filter mass or power sub-allocation",
                    "sources": [f"{BOM}#items[filter].cbe (basis TBD)"], "refs": ["BOM:filter"]},
        interface={"docs": {"upstream_icd": ["IF-A1", "IF-A2"]},
                   "note": "filter flow effect absent on the production path (G-01); no pressure-loss model (G-08)",
                   "refs": ["ICDGAP:G-01", "ICDGAP:G-08"]},
        design={"summary": "NONE (mass_bom: 'filter concept and geometry (not defined in this repository)')", "sources": [f"{BOM}#items[filter].cbe"]},
        evidence={"summary": "TBD - no evidence for a filter; no evidence matrix", "classes": ["TBD"], "matrices": [], "sources": [f"{ICD_MD}#7 (G-01, G-11)"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[filter]"]},
        needed={"summary": "owner decision on filter as a separate element (ICD OQ1) and contaminant scope (OQ5); then a concept and a transmission / pressure-loss characterization",
                "refs": [], "sources": [f"{ICD_MD}#9"]},
        blocker={"item": "filter concept undefined (ICD G-01 / owner question 1)", "category": "unresolved interface",
                 "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": f"owner ({ICD_MD}#9 OQ1)",
                 "sources": [f"{ICD_MD}#7", f"{BOM}#items[filter]"]},
        risks={"4": "contributing: mass and pressure-loss term"},
    ),
    _row(
        "compressor", "atmospheric_branch", 2,
        requirement={
            "summary": "full-system P_bus < 1.5 kW is the hard gate (A4, RFP-PWR); firing life > 15,000 h (RFP-FIRING, T-9); HG-1..HG-6 of the downselect",
            "items": [
                {"text": "P_bus < 1.5 kW for the full system (hard gate); a compressor above 300 W is not rejected if the system closes", "class": "RFP + A4 decision", "source": f"{A4}#decisions.compressor_power_allocation; {RTM}#RFP-PWR"},
                {"text": "life toward > 15,000 h firing (bearings, rotor creep/fatigue)", "class": "RFP (verify)", "source": f"{RTM}#RFP-FIRING; {CMP}#minimum_data_to_freeze_DI_1_4 T-9"},
                {"text": "compression ratio and inlet pumping speed per the requirement envelope (HG-4, HG-5)", "class": "derived (DRAFT for owner review)", "source": f"{CMP}#gates"},
            ],
            "refs": ["RTM:RFP-PWR", "RTM:RFP-FIRING", "CMP:HG-1", "CMP:HG-4", "CMP:HG-5", "CMP:T-9"],
        },
        allocation={"status": "PARTIAL",
                    "entries": [{"quantity": "compressor bus power", "value": "300 W", "status": "design/screening allocation, NOT a hard physical elimination gate",
                                 "evidence_class": "assumed (owner allocation)", "source": f"{A4}#decisions.compressor_power_allocation"}],
                    "note": "mass: TO_BE_ALLOCATED (mass_bom compressor CBE TBD)",
                    "sources": [f"{A4}#decisions.compressor_power_allocation", f"{BOM}#items[compressor]"], "refs": ["BOM:compressor", "AUXTBD:compressor"]},
        interface={"docs": {"upstream_icd": ["IF-A2", "IF-A3"], "boundary_contract": ["compressor"]},
                   "note": "no convergence flag from the leak fixed point (G-03); heat split assumed (G-17); wall-collision counts unsourced (G-16)",
                   "refs": ["ICDGAP:G-03", "ICDGAP:G-16", "ICDGAP:G-17"]},
        design={"summary": "C1 (bladed turbomolecular first stage) = LEADING_CANDIDATE_PENDING_PRIMARY_EVIDENCE (A4); DI-1.4 NOT frozen; C3 passive intake retained as reference branch",
                "sources": [f"{A4}#decisions.DI_1_4_compressor_C1", f"{CMP}#recommendation"], "refs": ["CMP:C1", "CMP:C3"]},
        evidence={"summary": "the only ABEP-specific active-compressor data point (LI2015, CR >= 3500) is a secondary citation not read first-hand (EV-08); other entries are commercial-TMP / physics bounds",
                  "classes": ["secondary citation (unverified)", "model-derived"], "matrices": [f"{CMP}#evidence"],
                  "sources": [f"{CMP}#concepts[C1].published_performance", f"{A4}#decisions.DI_1_4_compressor_C1"], "refs": ["CMPEV:EV-08"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{CMP}#owner_decisions"]},
        needed={"summary": "first-hand Li 2015 verification; minimum data to freeze DI-1.4: T-1 CR vs inlet pressure, T-2 pumping speed, T-3 AO-bearing flow, T-4 bus power, T-5 T_feed, T-6 AO materials, T-7 mass, T-8 back-streaming, T-9 life; LOCK-1 D-11 (unmeasured compressor bus draw)",
                "refs": ["CMP:T-1", "CMP:T-2", "CMP:T-3", "CMP:T-4", "CMP:T-5", "CMP:T-6", "CMP:T-7", "CMP:T-8", "CMP:T-9", "LOCK1:D-11", "DQ:DQ-PBUS"],
                "sources": [f"{CMP}#minimum_data_to_freeze_DI_1_4", f"{LOCK1}#decisions D-11"]},
        blocker={"item": "first-hand verification of the Li 2015 compression claim (A4: DI-1.4 not frozen until verified; a secondary citation is not enough)",
                 "category": "compressor", "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE",
                 "decision_by": f"owner ({A4}#decisions.DI_1_4_compressor_C1)",
                 "note": "A4 critical_path[0] lists primary compressor evidence in parallel with H-1 manufacture; it gates DI-1.4 and the full-v1 P_bus term (DQ-PBUS), not the Phase-1 test gates",
                 "sources": [f"{A4}#decisions.DI_1_4_compressor_C1", f"{A4}#critical_path"]},
        risks={"1": "contributing: compression sets delivered flow and O2 fraction", "4": "contributing: largest named auxiliary bus term (300 W allocation) and mass"},
    ),
    _row(
        "buffer_plenum", "atmospheric_branch", 3,
        requirement={
            "summary": "derived: hold the atmospheric-chamber feed state at IF-A3/IF-A4 for the metering valve; no numeric requirement recorded (TBD)",
            "items": [
                {"text": "buffer/plenum between compressor and metering valve", "class": "A5 decision (architecture element)", "source": f"{A5}#architecture.atmospheric_branch"},
                {"text": "TBD - requires chamber volume and operating pressure (design inputs)", "class": "TBD", "source": f"{BOM}#items[atmospheric_gas_chamber].cbe"},
            ],
            "refs": ["BOM:atmospheric_gas_chamber"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no plenum mass sub-allocation", "sources": [f"{BOM}#items[atmospheric_gas_chamber]"], "refs": ["BOM:atmospheric_gas_chamber"]},
        interface={"docs": {"upstream_icd": ["IF-A3", "IF-A4"]},
                   "note": "chamber balance has no convergence flag (G-04); orifice sizing no residual (G-05); chamber volume not linked to vessel mass (G-15)",
                   "refs": ["ICDGAP:G-04", "ICDGAP:G-05", "ICDGAP:G-15"]},
        design={"summary": "NONE (only the reservoir model abep_sim/reservoir.py; no design volume/pressure)", "sources": [f"{BOM}#items[atmospheric_gas_chamber].cbe", f"{ICD_MD}#7"]},
        evidence={"summary": "model-derived only (abep_sim/reservoir.py); no evidence matrix", "classes": ["model-derived"], "matrices": [], "sources": [f"{ICD_MD}#6 (IF-A4 coverage)"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[atmospheric_gas_chamber]"]},
        needed={"summary": "design inputs (volume, operating pressure, wall material); convergence flags G-04/G-05 (owner decides when, ICD OQ7); dynamics (G-09) for mode transitions",
                "refs": ["ICDGAP:G-09"], "sources": [f"{ICD_MD}#9 OQ7"]},
        blocker={"item": "chamber volume and operating pressure not set (mass_bom atmospheric_gas_chamber CBE requires them)", "category": "unresolved interface",
                 "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": None, "sources": [f"{BOM}#items[atmospheric_gas_chamber].cbe"]},
        risks={"4": "contributing: mass term"},
    ),
    _row(
        "atm_metering_valve", "atmospheric_branch", 4,
        requirement={
            "summary": "deliver the IF-A5 thruster-boundary feed state (mdot_s, p, T, x_s); Phase-1 region <= ~3.2 mg/s, x_O2 0.42-0.60 (A5); lab MFC range 0.030-3.14 mg/s (A4)",
            "items": [
                {"text": "IF-A5 thruster-boundary feed state, defined identically for every Hall closure", "class": "derived (ICD DRAFT)", "source": f"{ICD_MD}#IF-A5"},
                {"text": "H-1 sweep concentrated near the delivered-flow region (<= ~3.2 mg/s under H_RAM) and delivered O2 mass fraction 0.42-0.60", "class": "A5 decision (test region, not a flight requirement)", "source": f"{A5}#phase1_branch_decision.test_matrix"},
                {"text": "lab MFCs: 0.030-3.14 mg/s (~106:1), >= 3 overlapping ranges per gas path", "class": "A4 decision (lab FS-C)", "source": f"{A4}#decisions.MFC_ranges"},
            ],
            "refs": ["ICD:IF-A5", "RTM:RFP-IGN-SUST"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "flow_control is a bus_power_boundary_v1 component with no load and no allocation",
                    "sources": [f"{AUX}#tbd_register[flow_control]", f"{BOM}#items[atmospheric_valve]"], "refs": ["BOM:atmospheric_valve", "AUXTBD:flow_control"]},
        interface={"docs": {"upstream_icd": ["IF-A4", "IF-A5"], "hardware_definition": ["FS-C", "IP-UP", "HW-FS-01", "HW-FS-02"], "boundary_contract": ["flow_control"]},
                   "note": "no valve model (G-06); IF-A5 T_feed not propagated (G-07); no pressure-loss model (G-08)",
                   "refs": ["ICDGAP:G-06", "ICDGAP:G-07", "ICDGAP:G-08"]},
        design={"summary": "NONE for the flight valve; lab analogue FS-C (thermal MFCs, single mixing point) PROPOSED in the hardware definition",
                "sources": [f"{HWDEF}#configuration_items[FS-C]", f"{HWDEF}#requirements HW-FS-01..HW-FS-07"], "refs": ["HW:HW-FS-01", "HW:HW-FS-07"]},
        evidence={"summary": "TBD for the flight valve (no evidence matrix); feed-state closure test points are model-derived from assumed inputs",
                  "classes": ["model-derived", "TBD"], "matrices": [], "sources": [f"{FSC}#test_points"]},
        procurement={"status": "IN_PROCUREMENT_PLANNING (lab MFCs only)",
                     "recorded": ["A4: MFC range 0.030-3.14 mg/s, at least three overlapping ranges per gas path 'become part of procurement planning'",
                                  "flight valve / flow controller: " + PROC_UNKNOWN, HW_NOT_ORDERED],
                     "sources": [f"{A4}#decisions.MFC_ranges", f"{HWDEF}#status_note"]},
        needed={"summary": "owner release of GROUND_QUALIFICATION_POINT feed points (S1A-C3); MFC calibration procedure frozen (S1A-C4); INS-05 flow, INS-06 P_feed, INS-07 T_feed at the valve outlet; LOCK-1 D-11 (valve-outlet feed state)",
                "refs": ["S1A:S1A-C3", "S1A:S1A-C4", "S1:S1-C3", "INS:INS-05", "INS:INS-06", "INS:INS-07", "LOCK1:D-11", "DQ:DQ-KNEE"],
                "sources": [f"{S1A_COND}#conditions", f"{INSDEF}#instruments"]},
        blocker={"item": "released ground-qualification feed points (S1A-C3: GROUND_QUALIFICATION_POINT from the feed-state closure, owner-released) do not exist",
                 "category": "unresolved interface", "first_gate": "S1a", "beyond": None,
                 "decision_by": f"owner ({S1A_COND}#conditions S1A-C3)", "sources": [f"{S1A_STAT}#missing", f"{FSC}#flight_status_control"]},
        risks={"1": "contributing: delivers the low-flow / high-O2 feed state at which sustainment is tested", "4": "contributing: flow_control bus term and mass"},
    ),
    # ---------------------------------------------------------------- Xe branch
    _row(
        "xe_tank", "xe_branch", 0,
        requirement={
            "summary": "RFP < 40 kg; A6: Xe decided on the complete stored-Xe subsystem mass (m_Xe + tank + regulator + valves + plumbing + mounting/thermal) against 40 kg",
            "items": [
                {"text": "system mass < 40 kg", "class": "RFP (verify)", "source": f"{RTM}#RFP-MASS"},
                {"text": "system decision on m_Xe_subsystem = m_Xe + m_tank + m_regulator + m_valves + m_plumbing + m_mounting/thermal, not on propellant mass alone", "class": "A6 decision", "source": f"{A6}#authorized_now.fo_xe_system_ledger"},
                {"text": "operation on Xe (air + Xe)", "class": "RFP (verify)", "source": f"{RTM}#RFP-XE-OP"},
            ],
            "refs": ["RTM:RFP-MASS", "RTM:RFP-XE-OP"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [],
                    "context": [{"quantity": "cathode Xe ledger term (context, NOT a tank allocation)", "value": "5.4 kg at 0.10 mg/s over 15,000 h", "status": "A5 reference arithmetic",
                                 "evidence_class": "model-derived (arithmetic on an assumed design target)", "source": f"{A5}#xe_mass_allocation.reference_arithmetic_15000h"}],
                    "note": "m_Xe_total = PENDING_OWNER (A5); freezing total Xe mass is not authorized (A6 not_authorized); startup/transition/fallback/reserve terms unallocated; tank mass CBE TBD",
                    "sources": [f"{A5}#xe_mass_allocation.m_Xe_total_value", f"{A6}#not_authorized", f"{BOM}#items[xe_tank]", f"{BOM}#items[xe_load]"],
                    "refs": ["BOM:xe_tank", "BOM:xe_load", "BOM:xe_residual", "PAR:fo_xe_system_ledger"]},
        interface={"docs": {"upstream_icd": ["IF-X1"]}, "note": "Xe path has no storage state (G-12); pending parallel lane fo_xe_system_ledger for the ledger terms",
                   "refs": ["ICDGAP:G-12", "PAR:fo_xe_system_ledger"]},
        design={"summary": "NONE (mass_bom xe_tank: requires declared Xe load, storage p/T, tank concept)", "sources": [f"{BOM}#items[xe_tank].cbe"]},
        evidence={"summary": "TBD - no tank evidence; no evidence matrix", "classes": ["TBD"], "matrices": [], "sources": [f"{BOM}#items[xe_tank]"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[xe_tank]"]},
        needed={"summary": "parametric Xe ledger (pending parallel lane fo_xe_system_ledger at docs/budgets/xe_ledger/); H-1/C-1 measurements of startup/transition/fallback Xe (A6); owner m_Xe_total from the system mass ledger (A5); mass_bom OD-M4",
                "refs": ["PAR:fo_xe_system_ledger", "BOMOD:OD-M4"], "sources": [f"{A6}#authorized_now.fo_xe_system_ledger", f"{A5}#xe_mass_allocation"]},
        blocker={"item": "m_Xe_total not set (A5 PENDING_OWNER) and not yet settable: startup/transition/fallback terms stay symbolic until H-1/C-1 measure them (A6)",
                 "category": "cathode-Xe", "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": f"owner ({A5}#xe_mass_allocation)",
                 "sources": [f"{A5}#xe_mass_allocation", f"{A6}#authorized_now.fo_xe_system_ledger", f"{A6}#not_authorized"]},
        risks={"3": "contributing: stores the single fixed Xe allocation every Xe mode consumes", "4": "contributing: stored-Xe subsystem mass"},
    ),
    _row(
        "xe_regulator", "xe_branch", 1,
        requirement={
            "summary": "A6: m_regulator is a term of the stored-Xe subsystem mass; functional pressure requirement TBD - requires tank storage state and IF-X2 feed pressure",
            "items": [
                {"text": "regulator mass counted in m_Xe_subsystem against 40 kg", "class": "A6 decision", "source": f"{A6}#authorized_now.fo_xe_system_ledger"},
                {"text": "TBD - requires storage pressure/temperature and the IF-X2 feed pressure (ICD: p gap at IF-X2)", "class": "TBD", "source": f"{ICD_MD}#6"},
            ],
            "refs": ["RTM:RFP-XE-OP", "ICD:IF-X2"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no regulator mass/power sub-allocation (mass_bom books it inside xe_valve_and_flow_control, CBE TBD)",
                    "sources": [f"{BOM}#items[xe_valve_and_flow_control]"], "refs": ["BOM:xe_valve_and_flow_control"]},
        interface={"docs": {"upstream_icd": ["IF-X1", "IF-X2"]}, "note": "no regulator model (G-12) and no pressure-loss model for the Xe regulator (G-08)",
                   "refs": ["ICDGAP:G-12", "ICDGAP:G-08", "PAR:fo_xe_system_ledger"]},
        design={"summary": "NONE", "sources": [f"{BOM}#items[xe_valve_and_flow_control].cbe", f"{ICD_MD}#7 G-12"]},
        evidence={"summary": "TBD - no regulator evidence; no evidence matrix", "classes": ["TBD"], "matrices": [], "sources": [f"{ICD_MD}#7 G-12"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[xe_valve_and_flow_control]"]},
        needed={"summary": "owner scope decision on the Xe path (ICD OQ6: tank EOS, regulator model, one shared inventory); regulator concept; pending parallel lane fo_xe_system_ledger (m_regulator term)",
                "refs": ["PAR:fo_xe_system_ledger"], "sources": [f"{ICD_MD}#9 OQ6"]},
        blocker={"item": "no regulator concept or model (ICD G-12; owner question OQ6 open)", "category": "unresolved interface",
                 "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": f"owner ({ICD_MD}#9 OQ6)", "sources": [f"{ICD_MD}#7", f"{ICD_MD}#9"]},
        risks={"3": "contributing: Xe supply to the cathode", "4": "contributing: mass term"},
    ),
    _row(
        "xe_metering", "xe_branch", 2,
        requirement={
            "summary": "cathode flow design target 0.10 mg/s (0.15 mg/s test point only); every Xe mode has an explicit max duration; no continuous Xe support of the main discharge (A5)",
            "items": [
                {"text": "cathode flow design target 0.10 mg/s; 0.15 mg/s experimental upper test point only until the mass ledger shows it affordable", "class": "A5 decision (design target / test point)", "source": f"{A5}#xe_mass_allocation"},
                {"text": "every mode that consumes Xe carries an explicit maximum duration and draws on the single fixed Xe allocation; continuous Xe support of the main discharge is not nominal", "class": "A5 decision", "source": f"{A5}#operating_modes.rules"},
                {"text": "m_startup = N_starts * t_startup * mdot_startup; m_transition = N_transitions * t_transition * mdot_transition; m_fallback = t_fallback_max * mdot_fallback", "class": "A6 decision (symbolic until measured)", "source": f"{A6}#authorized_now.fo_xe_system_ledger"},
            ],
            "refs": ["P1DQ:P1DQ-NOXE"],
        },
        allocation={"status": "PARTIAL",
                    "entries": [{"quantity": "cathode Xe flow", "value": "0.10 mg/s", "status": "design target (0.15 mg/s = test point only)",
                                 "evidence_class": "assumed (owner design target)", "source": f"{A5}#xe_mass_allocation.cathode_flow_design_target_mg_s"}],
                    "note": "ignition/transition/fallback flows and durations: TO_BE_ALLOCATED (A6 not_authorized: freezing startup/transition/fallback quantities without evidence)",
                    "sources": [f"{A5}#xe_mass_allocation", f"{A6}#not_authorized"], "refs": ["BOM:xe_valve_and_flow_control", "PAR:fo_xe_system_ledger"]},
        interface={"docs": {"upstream_icd": ["IF-X2"], "hardware_definition": ["FS-C", "HW-FS-01", "HW-FS-03", "HW-C1-04"], "boundary_contract": ["flow_control"]},
                   "note": "IF-X2 thruster boundary: p and T are gaps; cathode Xe flow evidence class 'assumed' (code defaults)", "refs": ["PAR:fo_xe_system_ledger"]},
        design={"summary": "NONE for flight; lab analogue FS-C: separate Xe anode and Xe cathode MFCs, Xe ignition then anode transfer to N2 / N2-O2 (PROPOSED)",
                "sources": [f"{HWDEF}#requirements HW-FS-01, HW-FS-03, HW-C1-04"], "refs": ["HW:HW-FS-01", "HW:HW-FS-03", "HW:HW-C1-04"]},
        evidence={"summary": "reference cathode flows of other cathodes 0.08-1.0 mg/s (inferred, not verdict-bearing; RI-MASS-CATHODE-XE straddles 40 kg)",
                  "classes": ["inferred"], "matrices": [EVIDENCE_MATRICES["cathode"]], "sources": [f"{VETO}#risk_indicators[RI-MASS-CATHODE-XE]"], "refs": ["RI:RI-MASS-CATHODE-XE"]},
        procurement={"status": "IN_PROCUREMENT_PLANNING (lab MFCs only)",
                     "recorded": ["A4: at least three overlapping MFC ranges per gas path become part of procurement planning", "flight Xe flow control: " + PROC_UNKNOWN, HW_NOT_ORDERED],
                     "sources": [f"{A4}#decisions.MFC_ranges", f"{HWDEF}#status_note"]},
        needed={"summary": "FS-C identified for S1a (S1A-C1); MFC calibration (S1A-C4); C-1 minimum-flow measurement (C-1 diode allowed in S1a, A4); Phase-1 'no continuous Xe augmentation' quantity (pending parallel lane fo_phase1_prereg_framework); Xe ledger terms (pending parallel lane fo_xe_system_ledger)",
                "refs": ["S1A:S1A-C1", "S1A:S1A-C4", "INS:INS-05", "P1DQ:P1DQ-NOXE", "PAR:fo_phase1_prereg_framework", "PAR:fo_xe_system_ledger", "CATHTBD:cathode_min_flow"],
                "sources": [f"{A4}#decisions.C1_diode_in_S1a", f"{A6}#authorized_now"]},
        blocker={"item": "FS-C (incl. Xe anode and Xe cathode MFCs) not identified/available for S1a (S1A-C1 MISSING; MFCs only in procurement planning per A4)",
                 "category": "procurement", "first_gate": "S1a", "beyond": None, "decision_by": None,
                 "sources": [f"{S1A_STAT}#missing[S1A-C1]", f"{A4}#decisions.MFC_ranges"]},
        risks={"3": "primary: meters the cathode Xe that sets consumption (<= 0.10 mg/s target)", "4": "contributing: flow_control bus term"},
    ),
    # ---------------------------------------------------------------- propulsion
    _row(
        "hall_chamber", "propulsion", 0,
        requirement={
            "summary": "RFP 12-25 mN (A5 operating target 15-22 mN allocation), Hall preferred, > 15,000 h firing (A5 internal target >= 18,000 h), ignition and sustainment on atmospheric propellant",
            "items": [
                {"text": "absolute RFP thrust envelope 12-25 mN", "class": "RFP (verify; 25 mN reading open)", "source": f"{A5}#allocations_and_requirements; {RTM}#RFP-THR-MIN, RFP-THR-MAX"},
                {"text": "Hall thruster preferred", "class": "RFP (verify)", "source": f"{RTM}#RFP-HALL"},
                {"text": "firing life >= 15,000 h (requirement, not demonstrated)", "class": "RFP", "source": f"{A5}#allocations_and_requirements; {RTM}#RFP-FIRING"},
                {"text": "ignition and sustainment on atmospheric propellant; no continuous Xe support of the main discharge", "class": "RFP-inferred (verify) + A5 rule", "source": f"{RTM}#RFP-IGN-SUST; {A5}#operating_modes.rules"},
            ],
            "refs": ["RTM:RFP-THR-MIN", "RTM:RFP-THR-MAX", "RTM:RFP-HALL", "RTM:RFP-FIRING", "RTM:RFP-IGN-SUST", "HG:G1_thrust", "HG:G4_firing_life", "HG:G6_ignition_sustainment"],
        },
        allocation={"status": "SYSTEM_LEVEL_ALLOCATION_ONLY",
                    "entries": [{"quantity": "thrust operating target", "value": "15-22 mN", "status": "allocation; to be demonstrated", "evidence_class": "assumed (owner allocation)", "source": f"{A5}#allocations_and_requirements"},
                                {"quantity": "internal design life target", "value": ">= 18,000 h", "status": "design margin target, not evidenced", "evidence_class": "assumed (owner allocation)", "source": f"{A5}#allocations_and_requirements"}],
                    "note": "discharge power and head mass: TO_BE_ALLOCATED (hall_discharge load needs an admitted closure or hardware V_d*I_d; mass_bom hall_thruster_head CBE TBD). A5 numbers are allocations, never predictions.",
                    "sources": [f"{A5}#allocations_and_requirements", f"{AUX}#tbd_register[hall_discharge]", f"{BOM}#items[hall_thruster_head]"],
                    "refs": ["BOM:hall_thruster_head", "AUXTBD:hall_discharge"]},
        interface={"docs": {"upstream_icd": ["IF-A5", "IF-X2"], "hardware_definition": ["H-1", "IP-DN", "HALL_INLET_Z0", "HW-H1-06", "HW-ELEC-01", "HW-ELEC-02"],
                            "boundary_contract": ["hall_discharge"], "parallel": ["fo_preionizer_module_icd"]},
                   "note": "ionization-region boundary with the reserved pre-ionizer: IP-DN / HALL_INLET_Z0 PROPOSED; module potential HW-ELEC-02 TBD; common pre-ionizer ICD pending parallel lane fo_preionizer_module_icd",
                   "refs": ["PAR:fo_preionizer_module_icd"]},
        design={"summary": "H-1 requirements PROPOSED (hardware definition); H-1 = Vyovrinda design or surrogate is LOCK-1 D-09 (open); channel geometry release HW-H1-03 TBD; no Vyovrinda channel geometry",
                "sources": [f"{HWDEF}#requirements HW-H1-01, HW-H1-03", f"{LOCK1}#decisions D-09"], "refs": ["HW:HW-H1-01", "HW:HW-H1-03", "LOCK1:D-09"]},
        evidence={"summary": "credible Hall transport set EMPTY (no admitted closure); published air / N2-O2 points on other hardware at 2.75-7 mg/s vs <= ~3.2 mg/s delivered, all 9 air cases UNDETERMINED (A5 risk 1); PPS1350 N2/O2 + 10 % Xe life 7,000-9,500 h (A5 risk 2); no measured N/O wall yield",
                  "classes": ["measured (other hardware, not verdict-bearing)", "model-derived"], "matrices": [EVIDENCE_MATRICES["hall_sustainment"], EVIDENCE_MATRICES["wall_life"]],
                  "sources": [RISKS_SOURCE, f"{VETO}#risk_indicators"], "refs": ["RI:RI-LIFE-HALL-CHANNEL-AIR-EROSION", "RI:RI-LIFE-HALL-ANODE-OXIDATION"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED, "A4 critical_path[0] names 'H-1 manufacture/configuration' as critical-path work (no order recorded)"],
                     "sources": [f"{HWDEF}#status_note", f"{A4}#critical_path"]},
        needed={"summary": "LOCK-1 D-09; H-1 design release (HW-H1-01/-03) and S1A-C1 hardware record; S1-C2 configuration freeze; Phase-1 decision quantities sustainment, T/P_bus, eta_u, envelope width, ignition/restart, stability, absolute thrust (pending parallel lane fo_phase1_prereg_framework); DQ-KNEE on N2; W5 held-out validation pre-registration; AO life provisions (witness coupons, replaceable anode/wall rings)",
                "refs": ["LOCK1:D-09", "S1A:S1A-C1", "S1:S1-C2", "DQ:DQ-KNEE", "DQ:DQ-SUST", "P1DQ:P1DQ-SUST", "P1DQ:P1DQ-TPBUS", "P1DQ:P1DQ-ETAU", "P1DQ:P1DQ-ENV",
                         "P1DQ:P1DQ-IGN", "P1DQ:P1DQ-STAB", "P1DQ:P1DQ-TABS", "PAR:fo_phase1_prereg_framework", "INS:INS-04", "INS:INS-10", "HW:HW-H1-09", "HW:HW-H1-10", "HW:HW-H1-11", "AOL:AOL-WC-01"],
                "sources": [f"{A5}#phase1_branch_decision", f"{A6}#authorized_now.fo_phase1_prereg_framework", W5]},
        blocker={"item": "atmospheric sustainment at the delivered low flow / high O2 fraction is undemonstrated and no admitted Hall transport closure exists; only H-1 Phase 1 can resolve it",
                 "category": "propulsion physics", "first_gate": None, "beyond": "PHASE1_BRANCH_DECISION", "decision_by": None,
                 "note": "path prerequisites (listed under analysis/test needed): LOCK-1 D-09, H-1 design release, S1A-C1",
                 "sources": [RISKS_SOURCE, f"{A5}#phase1_branch_decision", f"{A4}#project_conclusion"]},
        risks={"1": "primary: the discharge whose sustainment is risk 1", "2": "primary: anode/channel oxygen life", "4": "contributing: hall_discharge dominates P_bus"},
    ),
    _row(
        "magnetic_circuit", "propulsion", 1,
        requirement={
            "summary": "derived: one magnetic circuit identical across arms, B(z) measurable at actual coil currents; hall_magnet P_bus term inside < 1.5 kW; life > 15,000 h",
            "items": [
                {"text": "one circuit, never modified between arms; coil currents recorded with every reading; B(z) mapped at actual coil currents", "class": "derived (PROPOSED, hardware definition)", "source": f"{HWDEF}#requirements HW-MC-01..HW-MC-03"},
                {"text": "hall_magnet bus power inside the full-system P_bus < 1.5 kW", "class": "RFP (verify)", "source": f"{RTM}#RFP-PWR"},
                {"text": "firing life > 15,000 h", "class": "RFP (verify)", "source": f"{RTM}#RFP-FIRING"},
            ],
            "refs": ["HW:HW-MC-01", "HW:HW-MC-02", "HW:HW-MC-03", "RTM:RFP-PWR", "RTM:RFP-FIRING"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no hall_magnet load or mass allocation (aux_bus: requires the Vyovrinda magnetic circuit or a PM decision)",
                    "sources": [f"{AUX}#tbd_register[hall_magnet]", f"{BOM}#items[hall_magnets]"], "refs": ["BOM:hall_magnets", "AUXTBD:hall_magnet"]},
        interface={"docs": {"hardware_definition": ["MC-1", "HW-MC-12", "HW-PIM-03", "HW-PIM-06", "HW-ELEC-05"], "boundary_contract": ["hall_magnet"], "parallel": ["fo_preionizer_module_icd"]},
                   "note": "permitted magnetic-field disturbance from a module (HW-PIM-06, INV-B3 tolerance) TBD; the common pre-ionizer ICD that fixes it is pending parallel lane fo_preionizer_module_icd",
                   "refs": ["PAR:fo_preionizer_module_icd"]},
        design={"summary": "NONE (Vyovrinda circuit); MC-1 requirements PROPOSED; magnet/coil candidate register (supplier datasheets, reference only); PM vs electromagnet undecided",
                "sources": [f"{MCQ}#candidates", f"{HWDEF}#configuration_items[MC-1]", f"{AUX}#owner_questions"], "refs": ["HW:HW-MC-01"]},
        evidence={"summary": "supplier-published magnet/coil material data (reference only, not Vyovrinda hardware); no Vyovrinda B(z)",
                  "classes": ["measured (supplier-published, reference only)"], "matrices": [MCQ], "sources": [f"{MCQ}#candidates", f"{MCQ}#reference_only_evidence"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED], "sources": [f"{HWDEF}#status_note"]},
        needed={"summary": "MCQ-S1-01..08 (all MISSING); B(z) maps at actual coil currents (INS-09, INS-P-07); coil temperature (INS-24); S1A-C1 MC-1 record; S1A-C4 B(z) calibration",
                "refs": ["MCQ:MCQ-S1-01", "MCQ:MCQ-S1-02", "MCQ:MCQ-S1-03", "MCQ:MCQ-S1-04", "MCQ:MCQ-S1-05", "MCQ:MCQ-S1-06", "MCQ:MCQ-S1-07", "MCQ:MCQ-S1-08",
                         "INS:INS-09", "INS:INS-P-07", "INS:INS-24", "S1A:S1A-C1", "S1A:S1A-C4", "P1DQ:P1DQ-STAB"],
                "sources": [f"{MCQ}#s1_gate_items", f"{HWDEF}#hardware_readiness_review"]},
        blocker={"item": "MC-1 not selected: permanent magnet vs electromagnet undecided, so the coil EIS selection MCQ-S1-01 cannot close (MC-1 also required in the S1A-C1 hardware record)",
                 "category": "procurement", "first_gate": "S1a", "beyond": None, "decision_by": f"owner ({AUX}#owner_questions)",
                 "sources": [f"{MCQ}#s1_gate_items", f"{S1A_STAT}#missing[S1A-C1]", f"{AUX}#owner_questions"]},
        risks={"1": "contributing: B(z) sets the discharge regime at which sustainment is tested", "2": "contributing: field topology and wall flux (magnetic shielding, RI-LIFE-HALL-SHIELDED-COUNTER)", "4": "contributing: hall_magnet bus term and mass"},
    ),
    _row(
        "cathode", "propulsion", 2,
        requirement={
            "summary": "A5: shielded Xe-fed LaB6 hollow cathode, isolated from the atmospheric plume; flow design target 0.10 mg/s; RFP > 15,000 h firing",
            "items": [
                {"text": "shielded Xe-fed LaB6 hollow cathode", "class": "A5 decision", "source": f"{A5}#architecture.propulsion"},
                {"text": "measured cathode flow at <= 0.10 mg/s design target; shielding/isolation from the atmospheric plume", "class": "A5 decision (risk-3 response)", "source": RISKS_SOURCE},
                {"text": "firing life > 15,000 h", "class": "RFP (verify)", "source": f"{RTM}#RFP-FIRING"},
            ],
            "refs": ["RTM:RFP-FIRING", "HG:P2_cathode", "HW:HW-C1-01", "HW:HW-C1-02"],
        },
        allocation={"status": "PARTIAL",
                    "entries": [{"quantity": "cathode Xe flow", "value": "0.10 mg/s", "status": "design target (0.15 mg/s test point only)",
                                 "evidence_class": "assumed (owner design target)", "source": f"{A5}#xe_mass_allocation.cathode_flow_design_target_mg_s"}],
                    "note": "keeper / heater bus power and cathode mass: TO_BE_ALLOCATED (aux_bus heater start-up bracket is a LOWER_BOUND, not an allocation)",
                    "sources": [f"{A5}#xe_mass_allocation", f"{AUX}#components.cathode_heater", f"{BOM}#items[cathode]"],
                    "refs": ["BOM:cathode", "AUXTBD:cathode_keeper", "AUXTBD:cathode_heater"]},
        interface={"docs": {"upstream_icd": ["IF-X2"], "hardware_definition": ["C-1", "HW-C1-04", "HW-C1-05"], "boundary_contract": ["cathode_keeper", "cathode_heater"]},
                   "note": "cathode gas never crosses HALL_INLET_Z0; air-fed cathode excluded pending test (ICD IF-A5 mdot_cathode_air_kgps held at zero)", "refs": []},
        design={"summary": "cathode integration model (DRAFT) and C-1 requirements PROPOSED (Xe-fed LaB6, owner confirms HWQ-09); cathode hardware not selected",
                "sources": [f"{CATHI}#cathode_baseline", f"{HWDEF}#requirements HW-C1-01", f"{CATHI}#tbd[cathode_hardware]"], "refs": ["CATHTBD:cathode_hardware"]},
        evidence={"summary": "dossier of other LaB6 / BaO-W cathodes (measured on similar hardware, secondary where cited); air-exposure life toward exceedance (RI-LIFE-CATHODE-AIR-EXPOSURE); Xe mass straddles 40 kg (RI-MASS-CATHODE-XE); no Vyovrinda cathode data",
                  "classes": ["measured (other cathodes)", "inferred"], "matrices": [EVIDENCE_MATRICES["cathode"]],
                  "sources": [f"{CATHD}#hardware_test_gaps", f"{VETO}#risk_indicators"], "refs": ["RI:RI-LIFE-CATHODE-AIR-EXPOSURE", "RI:RI-MASS-CATHODE-XE", "RI:RI-STARTUP-CATHODE-HEATER"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED], "sources": [f"{HWDEF}#status_note"]},
        needed={"summary": "C-1 selection and S1-C2 freeze; measured spot-mode minimum flow (cathode_min_flow); C-1 diode commissioning allowed in S1a with Hall discharge inhibited (A4); dossier gaps G01 (coupled operation), G02 (O poisoning), G04 (wear); near-cathode RGA (INS-22), emitter/tube temperature (INS-23, HW-C1-09); Xe ledger cathode term (pending parallel lane fo_xe_system_ledger)",
                "refs": ["S1:S1-C2", "CATHTBD:cathode_min_flow", "CATHGAP:G01", "CATHGAP:G02", "CATHGAP:G04", "INS:INS-22", "INS:INS-23", "HW:HW-C1-09", "PAR:fo_xe_system_ledger", "P1DQ:P1DQ-IGN"],
                "sources": [f"{A4}#decisions.C1_diode_in_S1a", f"{CATHD}#hardware_test_gaps", f"{CATHI}#tbd"]},
        blocker={"item": "C-1 not selected (cathode_integration tbd 'cathode_hardware'); S1-C2 requires C-1 FROZEN_FOR_QUALIFICATION, and its measured minimum Xe flow (risk 3) is unknown until it exists",
                 "category": "cathode-Xe", "first_gate": "S1/S1b", "beyond": None, "decision_by": f"owner ({HWDEF}#requirements HW-C1-01, HWQ-09)",
                 "sources": [f"{CATHI}#tbd", f"{S1_STAT}#missing[S1-C2]"]},
        risks={"3": "primary: cathode Xe consumption and oxygen isolation", "4": "contributing: keeper/heater bus terms and mass"},
    ),
    # ---------------------------------------------------------------- support
    _row(
        "ppu", "support", 0,
        requirement={
            "summary": "RFP P_bus < 1.5 kW at bus_power_boundary_v1 (all electrical power crossing the spacecraft-side DC boundary); electronics redundancy (inferred, verify)",
            "items": [
                {"text": "P_bus < 1.5 kW", "class": "RFP (verify)", "source": f"{RTM}#RFP-PWR; {BOUNDARY_PY}"},
                {"text": "no single-point failure in electronics", "class": "RFP-inferred from repo text (verify)", "source": f"{RTM}#RFP-REDUND"},
            ],
            "refs": ["RTM:RFP-PWR", "RTM:RFP-REDUND", "HG:G2_bus_power"],
        },
        allocation={"status": "SYSTEM_LEVEL_ALLOCATION_ONLY",
                    "entries": [{"quantity": "bus-power design allocation (whole system, at the PPU input boundary)", "value": "<= 1.30-1.35 kW", "status": "allocation leaving margin to 1.5 kW; P_bus per bus_power_boundary_v1",
                                 "evidence_class": "assumed (owner allocation)", "source": f"{A5}#allocations_and_requirements"}],
                    "note": "no PPU-loss or per-component sub-allocation; aux-bus ledgers 0/6 evaluable; PPU mass CBE TBD",
                    "sources": [f"{A5}#allocations_and_requirements", f"{AUX}#ledger_summary", f"{BOM}#items[ppu]"], "refs": ["BOM:ppu", "AUXTBD:housekeeping"]},
        interface={"docs": {"boundary_contract": ["hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control", "compressor", "thermal_control", "housekeeping", "rf_source", "ecr_source", "ecr_magnet"],
                            "hardware_definition": ["PS-C", "HW-ELEC-01", "HW-ELEC-04"]},
                   "note": "bus_power_boundary_v1 accounting boundary is frozen in code; the electrical ICD (bus voltage, grounding) is open (aux_bus: owner bus-voltage decision)", "refs": []},
        design={"summary": "NONE (flight PPU); lab supplies PS-C with load-plane metering PROPOSED; discharge-supply efficiency evidence only at 28 V input points",
                "sources": [f"{BOM}#items[ppu].cbe", f"{HWDEF}#configuration_items[PS-C]", PWRB]},
        evidence={"summary": "discharge-supply efficiency eta_d 0.7716-0.9072 at measured 28 V-input points (digitized, Rhodes 2024) - other hardware; no Vyovrinda PPU data",
                  "classes": ["digitized"], "matrices": [f"{PWRB}#8"], "sources": [f"{AUX}#headroom.eta_d_measured_range_28V", f"{PWRB}#8"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED + " (PS-C lab supplies)"], "sources": [f"{HWDEF}#status_note"]},
        needed={"summary": "owner bus-voltage decision and measured supply efficiencies (supply-efficiency campaign); INS-02 per-component bus metering; Phase-1 T/P_bus and full bus-power compatibility (pending parallel lane fo_phase1_prereg_framework); DQ-PBUS",
                "refs": ["INS:INS-02", "DQ:DQ-PBUS", "P1DQ:P1DQ-TPBUS", "P1DQ:P1DQ-PBUS", "PAR:fo_phase1_prereg_framework", "AUXTBD:hall_discharge"],
                "sources": [f"{AUX}#tbd_register", f"{INSDEF}#instruments"]},
        blocker={"item": "owner bus-voltage decision open, so no supply efficiency at the Vyovrinda bus voltage and load can be measured (aux_bus tbd_register hall_discharge efficiency)",
                 "category": "unresolved interface", "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": f"owner ({AUX}#tbd_register)",
                 "sources": [f"{AUX}#tbd_register"]},
        risks={"4": "primary: P_bus closure under the <= 1.30-1.35 kW allocation"},
    ),
    _row(
        "thermal_control", "support", 1,
        requirement={
            "summary": "derived: heat rejection Q_reject closes for every node (DER-THERMAL); thermal limits per the thermal/life framework (TBD)",
            "items": [
                {"text": "heat rejection (Q_reject) closes", "class": "derived (project)", "source": f"{RTM}#DER-THERMAL"},
                {"text": "thermal_control load inside P_bus < 1.5 kW", "class": "RFP (verify)", "source": f"{RTM}#RFP-PWR"},
            ],
            "refs": ["RTM:DER-THERMAL", "HG:P1_thermal"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no thermal_control load or thermal-hardware mass allocation",
                    "sources": [f"{AUX}#tbd_register[thermal_control]", f"{BOM}#items[thermal_hardware]"], "refs": ["BOM:thermal_hardware", "AUXTBD:thermal_control"]},
        interface={"docs": {"boundary_contract": ["thermal_control"], "hardware_definition": ["HW-H1-07", "HW-H1-12", "HW-PIM-09"]},
                   "note": "thermal rejection interface per node undefined; schemas/ledgers/thermal_rejection_ledger_v1.json exists without inputs", "refs": ["PATH:schemas/ledgers/thermal_rejection_ledger_v1.json"]},
        design={"summary": "NONE (framework only: abep_sim/thermal_life.py pure, every design input TBD)", "sources": [THL, "schemas/thermal_life/inputs_v1.json"], "refs": ["PATH:schemas/thermal_life/inputs_v1.json"]},
        evidence={"summary": "TBD for Vyovrinda nodes; RF passive-cooling and ECR microwave-line thermal indicators on other hardware (measured, not verdict-bearing)",
                  "classes": ["TBD", "measured (other hardware)"], "matrices": [EVIDENCE_MATRICES["rf_source"], EVIDENCE_MATRICES["ecr_source"]],
                  "sources": [THL, f"{VETO}#risk_indicators"], "refs": ["RI:RI-THERMAL-RF-PASSIVE-COOLING", "RI:RI-THERMAL-ECR-MICROWAVE-LINE"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[thermal_hardware]"]},
        needed={"summary": "thermal geometry and rejection paths; owner decisions of the framework (derating policy, wall environment, copper model); INS-17 temperatures; thermal settling T-SETTLE (HW-H1-07, TBD at S1)",
                "refs": ["INS:INS-17", "HW:HW-H1-07"], "sources": [THL]},
        blocker={"item": "no thermal design inputs (thermal/life framework: every design input TBD; no admitted HallMap to supply wall heat)",
                 "category": "thermal", "first_gate": None, "beyond": "FLIGHT_DESIGN_FREEZE", "decision_by": None, "sources": [THL]},
        risks={"2": "contributing: anode/channel temperature drives oxidation", "4": "contributing: thermal_control bus term and radiator mass"},
    ),
    _row(
        "control_fdir", "support", 2,
        requirement={
            "summary": "A5 mode sequence OFF -> Xe ignition -> transition -> atmospheric Hall + Xe cathode -> degraded -> time-limited Xe contingency -> shutdown; every Xe mode time-limited; RFP ignition/sustainment and redundancy (verify)",
            "items": [
                {"text": "operating-mode sequence and rules (explicit max duration per Xe mode; transition never silently becomes long-duration)", "class": "A5 decision", "source": f"{A5}#operating_modes"},
                {"text": "ignition and sustainment on atmospheric propellant", "class": "RFP-inferred (verify)", "source": f"{RTM}#RFP-IGN-SUST"},
                {"text": "S1a minimum interlocks (E-stop, vacuum abort, pumping/cooling abort, cathode and magnet over-current/-temperature, gas/oxidizer interlock, DAQ fault, Hall-discharge inhibit)", "class": "A4 decision (lab)", "source": f"{A4}#decisions.S1a_minimum_interlocks"},
            ],
            "refs": ["RTM:RFP-IGN-SUST", "RTM:RFP-REDUND", "DFS:XE_FALLBACK", "DFS:SAFE_MODE"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "housekeeping load/efficiency and Xe-mode durations unallocated (A6 not_authorized: freezing startup/transition/fallback without evidence)",
                    "sources": [f"{AUX}#tbd_register[housekeeping]", f"{A6}#not_authorized"], "refs": ["AUXTBD:housekeeping"]},
        interface={"docs": {"upstream_icd": ["IF-A5", "IF-X2"], "state_machine": ["dual_feed_state_machine_v1"], "boundary_contract": ["housekeeping"]},
                   "note": "controller -> valve commands defined in the ICD (DRAFT); state machine v1.1 DRAFT with TBD guard parameters", "refs": []},
        design={"summary": "dual-feed state machine v1.1 DRAFT (17 states incl. XE_FALLBACK, DEGRADED_OPERATION, SAFE_MODE; guards and Xe-per-state TBD)",
                "sources": [DFS, "docs/controls/DUAL_FEED_STATES.md"], "refs": ["DFS:DEGRADED_OPERATION", "PATH:docs/controls/DUAL_FEED_STATES.md"]},
        evidence={"summary": "definition only (state machine and guard semantics); no measured transition data; no evidence matrix",
                  "classes": ["TBD"], "matrices": [], "sources": [DFS]},
        procurement={"status": PROC_UNKNOWN, "recorded": [], "sources": [f"{BOM}#items[ppu] (control/housekeeping electronics booked inside PPU)"]},
        needed={"summary": "S1A-C2 owner-approved limits and interlocks (from real hardware/facility ratings); LOCK-1 D-13 (ignition/start attempts); ignition/restart and no-continuous-Xe decision quantities (pending parallel lane fo_phase1_prereg_framework); Xe-mode durations (pending parallel lane fo_xe_system_ledger); INS-10 extinction/ignition detection",
                "refs": ["S1A:S1A-C2", "S1:S1-C8", "LOCK1:D-13", "P1DQ:P1DQ-IGN", "P1DQ:P1DQ-NOXE", "PAR:fo_phase1_prereg_framework", "PAR:fo_xe_system_ledger", "INS:INS-10"],
                "sources": [f"{A4}#decisions.S1a_interlock_limits", f"{LOCK1}#decisions D-13"]},
        blocker={"item": "S1A-C2 owner-approved safety/operational limits and the A4 minimum interlock set do not exist; limits must come from real hardware/facility ratings (A4), which need the facility (S1A-C5) and hardware (S1A-C1)",
                 "category": "procurement", "first_gate": "S1a", "beyond": None, "decision_by": f"owner ({S1A_COND}#conditions S1A-C2)",
                 "sources": [f"{S1A_STAT}#missing[S1A-C2]", f"{A4}#decisions.S1a_interlock_limits"]},
        risks={"3": "contributing: enforces Xe-mode durations against the single Xe allocation", "4": "contributing: housekeeping bus term"},
    ),
    _row(
        "sensors_diagnostics", "support", 3,
        requirement={
            "summary": "A5 Phase-1 minimum measurements (I_d, thrust, P_bus, source power, cathode flow/power, stability, ignition/restart, species where available); A4 SI-traceable ISO/IEC 17025 calibration; flight sensor set TBD",
            "items": [
                {"text": "minimum measurements at every Phase-1 point", "class": "A5 decision", "source": f"{A5}#phase1_branch_decision.minimum_measurements"},
                {"text": "SI-traceable calibration through an ISO/IEC 17025-accredited scope; certificate, uncertainty budget, traceability chain, raw record", "class": "A4 decision", "source": f"{A4}#decisions.force_DC_RF_traceability"},
                {"text": "flight sensor set: TBD - requires the flight control/FDIR guard list", "class": "TBD", "source": DFS},
            ],
            "refs": ["DQ:DQ-RARCH", "DQ:DQ-TABS", "DQ:DQ-PBUS", "DQ:DQ-SUST", "DQ:DQ-KNEE"],
        },
        allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no sensor mass/power allocation (sensors booked inside housekeeping; required measurement uncertainties are PROPOSED, not allocations)",
                    "sources": [f"{AUX}#tbd_register[housekeeping]", f"{INSDEF}#proposed_thresholds"], "refs": ["AUXTBD:housekeeping"]},
        interface={"docs": {"hardware_definition": ["HW-H1-08", "HW-PIM-07", "HW-FS-04"], "upstream_icd": ["IF-A5"]},
                   "note": "diagnostic access PROPOSED; INS-06/INS-07 measure P_feed/T_feed at IF-A5", "refs": ["INS:INS-06", "INS:INS-07"]},
        design={"summary": "lab instrumentation definition v1-r2 (INS-01..INS-24, procedures INS-P-01..12), DRAFT_PENDING_OWNER; metrology measurement spec; no flight sensor design",
                "sources": [INSDEF, METROLOGY], "refs": ["INS:INS-01", "INS:INS-24", "INS:INS-P-12"]},
        evidence={"summary": "required uncertainties PROPOSED; no demonstrated measurement capability (metrology spec approval 'does NOT constitute a demonstrated measurement capability', A4)",
                  "classes": ["assumed (PROPOSED)"], "matrices": [], "sources": [f"{A4}#decisions.metrology_specification", f"{INSDEF}#proposed_thresholds"]},
        procurement={"status": "APPROVED_FOR_PROCUREMENT (metrology specification only)",
                     "recorded": ["A4: metrology specification approved as the procurement specification (authorizes quotes / lab capability); scope INS-19, INS-20, INS-P-01..INS-P-05",
                                  "file status of the spec itself: DRAFT_PENDING_OWNER (A4 is the approval record)",
                                  "all other instruments: " + PROC_UNKNOWN],
                     "sources": [f"{A4}#decisions.metrology_specification", f"{METROLOGY}#serves"], "refs": ["INS:INS-19", "INS:INS-20"]},
        needed={"summary": "S1A-C4 frozen calibration procedures (thrust stand, power channels, MFCs, B(z), DAQ time base, temperatures); S1-C4 capability demonstrated (six S1a categories, then S1b); S1A-FW data firewall; W5 held-out observables",
                "refs": ["S1A:S1A-C4", "S1A:S1A-FW", "S1:S1-C4", "S1:S1-C5", "S1:S1-C6", "INS:INS-01", "INS:INS-02", "INS:INS-18"],
                "sources": [f"{S1A_COND}#conditions", f"{S1_COND}#conditions", f"{A4}#decisions.S1_C4_categories"]},
        blocker={"item": "S1A-C4 frozen calibration procedures do not exist, and the instruments they calibrate are not procured (only the metrology specification is approved for procurement)",
                 "category": "procurement", "first_gate": "S1a", "beyond": None, "decision_by": None,
                 "sources": [f"{S1A_STAT}#missing[S1A-C4]", f"{A4}#decisions.metrology_specification"]},
        risks={"1": "contributing: measures sustainment/stability", "2": "contributing: witness coupons and post-test metrology (INS-19/INS-20)", "3": "contributing: cathode flow and near-cathode RGA", "4": "contributing: INS-02 bus metering"},
    ),
    _row(
        "mechanical_structural", "support", 4,
        requirement={
            "summary": "RFP < 40 kg (A5 allocation <= 34-36 kg); lab: installation reproducibility of ln(T/P_bus) within u_inst,max (PROPOSED); flight launch loads TBD",
            "items": [
                {"text": "system mass < 40 kg", "class": "RFP (verify)", "source": f"{RTM}#RFP-MASS"},
                {"text": "re-mount reproducibility no worse than u_inst,max at the n fixed at LOCK-2", "class": "derived (PROPOSED)", "source": f"{HWDEF}#requirements HW-SVC-03"},
                {"text": "TBD - requires configuration and launch-load environment (not defined in this repository)", "class": "TBD", "source": f"{BOM}#items[structure].cbe"},
            ],
            "refs": ["RTM:RFP-MASS", "HW:HW-SVC-03", "HG:G3_mass"],
        },
        allocation={"status": "SYSTEM_LEVEL_ALLOCATION_ONLY",
                    "entries": [{"quantity": "system mass design allocation", "value": "<= 34-36 kg", "status": "allocation leaving margin to 40 kg", "evidence_class": "assumed (owner allocation)", "source": f"{A5}#allocations_and_requirements"}],
                    "note": "structure mass not sub-allocated (mass_bom structure CBE TBD; mass roll-up REFUSED with 16 TBD items)",
                    "sources": [f"{A5}#allocations_and_requirements", f"{BOM}#rollups", f"{BOM}#items[structure]"], "refs": ["BOM:structure", "BOM:harness"]},
        interface={"docs": {"hardware_definition": ["SVC-1", "HW-SVC-01", "HW-SVC-03", "HW-SVC-04", "HW-H1-06"]},
                   "note": "lab mount / service-line bundle PROPOSED; configuration-change procedure open (HWQ-01, LOCK-1 D-06); flight mechanical ICD: none", "refs": ["LOCK1:D-06"]},
        design={"summary": "NONE (flight structure); lab mount and service-line bundle requirements PROPOSED", "sources": [f"{BOM}#items[structure].cbe", f"{HWDEF}#requirements HW-SVC-01..06"]},
        evidence={"summary": "TBD - no evidence; no evidence matrix", "classes": ["TBD"], "matrices": [], "sources": [f"{BOM}#plausibility_screen (LOWER_BOUNDS_UNAVAILABLE)"]},
        procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED + " (SVC-1, H-1 mount)"], "sources": [f"{HWDEF}#status_note"]},
        needed={"summary": "LOCK-1 D-06 (HW-0 spacer + S1b re-mounts / OPTION-DIVERTER / CFG-A/B); S1b remount reproducibility (u_inst); owner margin decisions OD-M1/OD-M2; launch-load environment",
                "refs": ["LOCK1:D-06", "HW:HW-SVC-04", "BOMOD:OD-M1", "BOMOD:OD-M2"], "sources": [f"{LOCK1}#decisions D-06", f"{BOM}#open_owner_decisions"]},
        blocker={"item": "LOCK-1 D-06 (hardware configuration and configuration-change procedure) open",
                 "category": "unresolved interface", "first_gate": "LOCK-1", "beyond": None, "decision_by": f"owner ({LOCK1}#decisions D-06)",
                 "sources": [f"{LOCK1}#decisions", f"{HWDEF}#owner_questions HWQ-01"]},
        risks={"3": "contributing: cathode mounting/shielding position relative to the plume", "4": "contributing: structure mass"},
    ),
]

RESERVED_ROW = _row(
    "preionizer_interface", "reserved_interface", None,
    requirement={
        "summary": "A5: defined electrical, mechanical, gas and control ICD produced now, so fitting RF after H-1 needs no thruster redesign; A6: common interface not secretly RF-specific",
        "items": [
            {"text": "a defined electrical, mechanical, gas and control ICD is produced now so that fitting RF after H-1 does not require redesigning the thruster", "class": "A5 decision", "source": f"{A5}#architecture.reserved_interface.requirement"},
            {"text": "the common pre-ionizer interface must not be secretly RF-specific; HW-0 uses a blank/spacer module with equivalent interfaces", "class": "A6 decision", "source": f"{A6}#common_interface_rule; {A6}#authorized_now.fo_preionizer_module_icd"},
        ],
        "refs": ["PAR:fo_preionizer_module_icd"],
    },
    allocation={"status": "TO_BE_ALLOCATED", "entries": [], "note": "no rf_source / ecr_source / ecr_magnet load or mass allocation (reserved; not baseline flight hardware)",
                "sources": [f"{AUX}#tbd_register[rf_source, ecr_source, ecr_magnet]", f"{BOM}#items[rf_source]"],
                "refs": ["BOM:rf_source", "BOM:rf_generator", "BOM:rf_matching_network", "BOM:ecr_source", "AUXTBD:rf_source", "AUXTBD:ecr_source", "AUXTBD:ecr_magnet"]},
    interface={"docs": {"hardware_definition": ["IP-UP", "IP-DN", "PIM-0", "PIM-RF", "PIM-ECR", "HW-PIM-01", "HW-PIM-11", "HW-ELEC-02", "HW-ELEC-03", "HW-FS-04", "HW-FS-05"],
                        "boundary_contract": ["rf_source", "ecr_source", "ecr_magnet"], "parallel": ["fo_preionizer_module_icd"]},
               "note": "IP-UP / IP-DN planes and module requirements PROPOSED; module interface control drawing not frozen (HRR entry criterion); source frequencies not selected (HW-PIM-11 TBD); common pre-ionizer ICD pending parallel lane fo_preionizer_module_icd",
               "refs": ["PAR:fo_preionizer_module_icd"]},
    design={"summary": "PIM-0 / PIM-RF / PIM-ECR module requirements PROPOSED (lab); no source design",
            "sources": [f"{HWDEF}#configuration_items", f"{BOM}#items[rf_source].cbe"], "refs": ["HW:HW-PIM-01", "HW:HW-PIM-15"]},
    evidence={"summary": "published RF / ECR sources on other hardware (evidence audits, no architecture conclusion); RF passive cooling toward exceedance; no verdict-bearing evidence",
              "classes": ["measured (other hardware)", "assumed / inferred"], "matrices": [EVIDENCE_MATRICES["rf_source"], EVIDENCE_MATRICES["ecr_source"]],
              "sources": [f"{VETO}#risk_indicators"], "refs": ["RI:RI-THERMAL-RF-PASSIVE-COOLING", "RI:RI-LIFE-RF-DIELECTRIC", "RI:RI-MASS-RF-HARDWARE-UNKNOWN", "RI:RI-MASS-ECR-AMPLIFIER-BREADBOARD"]},
    procurement={"status": PROC_UNKNOWN, "recorded": [HW_NOT_ORDERED + " (PIM-0, PIM-RF, PIM-ECR)"], "sources": [f"{HWDEF}#status_note"]},
    needed={"summary": "common pre-ionizer module ICD (pending parallel lane fo_preionizer_module_icd); HRR: module interface control drawing frozen; LOCK-1 D-06 configuration; Phase-1 order-balanced execution (A6 clarification) and T/P_bus, sustainment, eta_u decision quantities (pending parallel lane fo_phase1_prereg_framework); INS-03 source power",
            "refs": ["PAR:fo_preionizer_module_icd", "PAR:fo_phase1_prereg_framework", "LOCK1:D-06", "INS:INS-03", "DQ:DQ-RARCH", "P1DQ:P1DQ-TPBUS", "P1DQ:P1DQ-SUST", "P1DQ:P1DQ-ETAU"],
            "sources": [f"{HWDEF}#hardware_readiness_review", f"{A6}#clarification_execution_order"]},
    blocker={"item": "common pre-ionizer module ICD does not exist in the base (pending parallel lane fo_preionizer_module_icd); HW-PIM-01 module interface control drawing not frozen (HRR entry criterion before S1)",
             "category": "unresolved interface", "first_gate": "S1/S1b", "beyond": None, "decision_by": None,
             "sources": [f"{HWDEF}#hardware_readiness_review", f"{A5}#architecture.reserved_interface"]},
    risks={"1": "contributing: RF/ECR are the contingency response to risk 1 (A5)", "4": "contributing: source bus power and mass if fitted"},
)

COLUMNS = ["requirement", "allocation", "interface_status", "preliminary_design", "evidence_status", "procurement_status",
           "analysis_test_needed", "blocker", "owner"]
_COL_FROM_ROW = {"requirement": "requirement", "allocation": "allocation", "interface_status": "interface",
                 "preliminary_design": "design", "evidence_status": "evidence", "procurement_status": "procurement",
                 "analysis_test_needed": "needed", "blocker": "blocker"}


# --------------------------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------------------------
def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(root: str, rel: str):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"required base input missing: {rel}")
    with open(p, encoding="utf-8") as f:
        return json.load(f) if rel.endswith(".json") else f.read()


def verify_pins(root: str) -> dict:
    out = {}
    for rel, want in PINS.items():
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"pinned decision file missing: {rel}")
        got = _sha(p)
        if got != want:
            raise ValueError(f"pinned file {rel} sha256 {got} != pinned {want}; decisions are immutable - refusing to build")
        out[rel] = want
    g0 = _load(root, G0)
    if g0.get("a5_sha256") != PINS[A5] or g0.get("verdict") != "CLEAN":
        raise ValueError("G0 record does not verify the pinned A5 hash with verdict CLEAN")
    a6 = _load(root, A6)
    if a6.get("follows_sha256") != PINS[A5]:
        raise ValueError("A6 does not follow the pinned A5 hash")
    return out


def probe_parallel(root: str) -> dict:
    """Lazy probe of the parallel lanes' deliverables. Never interprets content."""
    out = {}
    for lane, paths in PARALLEL.items():
        found = []
        for rel in paths:
            p = os.path.join(root, rel)
            if os.path.isdir(p):
                for dp, dn, fn in os.walk(p):
                    dn.sort()
                    for name in sorted(fn):
                        fp = os.path.join(dp, name)
                        found.append(os.path.relpath(fp, root).replace(os.sep, "/"))
            elif os.path.isfile(p):
                found.append(rel)
        files = []
        for rel in sorted(found):
            entry = {"path": rel, "sha256": _sha(os.path.join(root, rel))}
            if rel.endswith(".json"):
                try:
                    with open(os.path.join(root, rel), encoding="utf-8") as f:
                        d = json.load(f)
                    if isinstance(d, dict) and isinstance(d.get("status"), str):
                        entry["status_field"] = d["status"]
                except (ValueError, OSError):
                    entry["status_field"] = "UNREADABLE_JSON"
            files.append(entry)
        out[lane] = {
            "expected_paths": paths,
            "state": "PRESENT_NOT_YET_INTEGRATED" if files else "PENDING_PARALLEL_LANE",
            "files": files,
            "meaning": ("deliverable present; its content is NOT interpreted by this matrix - cells that reference this lane "
                        "stay 'pending review' until a reviewed revision integrates it") if files else
                       "deliverable not in this checkout; cells that reference this lane read 'pending parallel lane'",
        }
    return out


class Registry:
    """Id sets and live states read from the base files, for reference resolution."""

    def __init__(self, root: str):
        self.root = root
        hw = _load(root, HWDEF)
        self.hw_status = {r["id"]: r["status"] for r in hw["requirements"]}
        self.hw_items = {c["id"] for c in hw["configuration_items"]} | {p["id"] for p in hw["interface_planes"]}
        self.hw_doc_status = hw["status"]
        self.hwq = {q["id"] for q in hw["owner_questions"]}
        ins = _load(root, INSDEF)
        self.ins = {x["id"] for x in ins["instruments"]} | {x["id"] for x in ins["procedures"]}
        self.dq = {x["id"] for x in ins["decision_quantities"]}
        s1a = _load(root, S1A_STAT)
        self.s1a_verdict = s1a["verdict"]
        self.s1a = {c["id"]: c["state"] for c in s1a["conditions"]}
        self.s1a_counts = (s1a["n_satisfied"], s1a["n_conditions"])
        s1 = _load(root, S1_STAT)
        self.s1_verdict = s1["verdict"]
        self.s1 = {c["id"]: c["state"] for c in s1["conditions"]}
        self.s1_counts = (s1["n_satisfied"], s1["n_conditions"])
        for cid in _load(root, S1A_COND)["conditions"]:
            if cid["id"] not in self.s1a:
                raise ValueError(f"S1a condition {cid['id']} has no current state")
        l1 = _load(root, LOCK1)
        self.lock1 = {d["id"]: d["status"] for d in l1["decisions"]}
        self.lock1_status = l1["status"]
        self.mcq = {x["id"]: x["state"] for x in _load(root, MCQ)["s1_gate_items"]}
        self.aol = {x["id"] for x in _load(root, AOL)["requirements"]}
        bom = _load(root, BOM)
        self.bom = {it["id"]: it["cbe"]["basis"] for it in bom["items"]}
        self.bom_od = {d["id"] for d in bom["open_owner_decisions"]}
        self.bom_rollups = {a: bom["rollups"][a]["strict"]["status"] for a in sorted(bom["rollups"])}
        aux = _load(root, AUX)
        self.aux_tbd = {t["component"] for t in aux["tbd_register"]}
        self.aux_ledgers = aux["ledger_summary"]
        veto = _load(root, VETO)
        self.ri = {r["id"] for r in veto["risk_indicators"]}
        self.veto_counts = veto["status_counts"]
        cmp_ = _load(root, CMP)
        self.cmp = ({x["id"] for x in cmp_["minimum_data_to_freeze_DI_1_4"]} | {c["id"] for c in cmp_["concepts"]}
                    | {g["id"] for g in cmp_["gates"]})
        self.cmp_ev = {e["id"] for e in cmp_["evidence"]}
        self.cath_tbd = {t["id"] for t in _load(root, CATHI)["tbd"]}
        self.cath_gap = {g["id"] for g in _load(root, CATHD)["hardware_test_gaps"]}
        self.rtm = {r["id"] for r in _load(root, RTM)["requirements"]}
        self.hg = {g["id"] for g in _load(root, HGM)["gates"]}
        hgs = _load(root, HGS)
        self.hg_eliminated = hgs["eliminated"]
        self.hg_admitted = hgs["admitted_members"]
        dfs = _load(root, DFS)
        self.dfs_states = set(dfs["states"].keys()) if isinstance(dfs["states"], dict) else {s["id"] for s in dfs["states"]}
        self.dfs_status = dfs["status"]
        icd = _load(root, ICD_SCHEMA)
        self.icd_status = icd["x-icd"]["status"]
        self.icd_ifs = list(icd["x-icd"]["interface_order"])
        self.icd_field_status = {}
        for iface in self.icd_ifs:
            counts = {}
            for fld in icd["$defs"][iface]["properties"].values():
                st = fld.get("x-field", {}).get("status")
                if st:
                    counts[st] = counts.get(st, 0) + 1
            self.icd_field_status[iface] = {k: counts[k] for k in sorted(counts)}
        md = _load(root, ICD_MD)
        self.icd_gaps = set(re.findall(r"^\| (G-\d\d) \|", md, flags=re.M))
        b1 = _load(root, B1)
        self.bundle1 = b1["outcome"]["label"]
        self.w5_status = _load(root, W5)["status"]
        self.metrology_status = _load(root, METROLOGY)["status"]
        bpy = _load(root, BOUNDARY_PY)
        m = re.search(r'^BOUNDARY_VERSION = "([^"]+)"', bpy, flags=re.M)
        if not m or m.group(1) != "bus_power_boundary_v1":
            raise ValueError("abep_sim/arch_boundary.py does not define BOUNDARY_VERSION 'bus_power_boundary_v1'")
        self.boundary_components = {"hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater", "flow_control",
                                    "compressor", "thermal_control", "housekeeping", "rf_source", "ecr_source", "ecr_magnet"}
        for c in self.boundary_components:
            if f'"{c}"' not in bpy:
                raise ValueError(f"bus_power_boundary_v1 component {c!r} not found in {BOUNDARY_PY}")

    def resolve(self, ref: str):
        """Return (kind, id, live_state or None). Raises on an unknown id."""
        kind, _, rid = ref.partition(":")
        state = None
        if kind == "HW":
            if rid in self.hw_status:
                state = self.hw_status[rid]
            elif rid not in self.hw_items and rid != "HRR":
                raise KeyError(ref)
        elif kind == "INS":
            ok = rid in self.ins
        elif kind == "DQ":
            ok = rid in self.dq
        elif kind == "S1A":
            if rid not in self.s1a:
                raise KeyError(ref)
            state = self.s1a[rid]
        elif kind == "S1":
            if rid not in self.s1:
                raise KeyError(ref)
            state = self.s1[rid]
        elif kind == "LOCK1":
            if rid not in self.lock1:
                raise KeyError(ref)
            state = self.lock1[rid]
        elif kind == "MCQ":
            if rid not in self.mcq:
                raise KeyError(ref)
            state = self.mcq[rid]
        elif kind == "BOM":
            if rid not in self.bom:
                raise KeyError(ref)
            state = f"CBE basis: {self.bom[rid]}"
        elif kind == "BOMOD":
            ok = rid in self.bom_od
        elif kind == "AOL":
            ok = rid in self.aol
        elif kind == "AUXTBD":
            ok = rid in self.aux_tbd
        elif kind == "RI":
            ok = rid in self.ri
        elif kind == "CMP":
            ok = rid in self.cmp
        elif kind == "CMPEV":
            ok = rid in self.cmp_ev
        elif kind == "CATHTBD":
            if rid not in self.cath_tbd:
                raise KeyError(ref)
            state = "TBD"
        elif kind == "CATHGAP":
            ok = rid in self.cath_gap
        elif kind == "RTM":
            ok = rid in self.rtm
        elif kind == "HG":
            ok = rid in self.hg
        elif kind == "DFS":
            ok = rid in self.dfs_states
        elif kind == "ICD":
            ok = rid in self.icd_ifs
        elif kind == "ICDGAP":
            ok = rid in self.icd_gaps
        elif kind == "P1DQ":
            ok = rid in P1DQ
        elif kind == "PAR":
            ok = rid in PARALLEL
        elif kind == "PATH":
            ok = os.path.exists(os.path.join(self.root, rid))
        else:
            raise KeyError(f"unknown reference kind in {ref!r}")
        if kind not in ("HW", "S1A", "S1", "LOCK1", "MCQ", "BOM", "CATHTBD") and not ok:
            raise KeyError(ref)
        return {"ref": ref, "state": state} if state is not None else {"ref": ref}


def _check_source_paths(root: str, sources) -> None:
    for s in sources:
        for part in s.split(";"):
            path = part.strip().split("#")[0].split(" ")[0]
            if path and "/" in path and not os.path.exists(os.path.join(root, path)):
                raise FileNotFoundError(f"cited source path does not exist: {path} (in {s!r})")


def _interface_status(reg: Registry, docs: dict, parallel_state: dict) -> dict:
    """FROZEN: every governing document owner-frozen. PARTIAL: at least one base ICD record, not all frozen.
    OPEN: no base record (only a pending parallel lane or nothing)."""
    doc_states = []
    detail = {}
    for kind, ids in docs.items():
        if kind == "upstream_icd":
            for i in ids:
                if i not in reg.icd_ifs:
                    raise KeyError(f"ICD interface {i}")
            doc_states.append(("docs/interfaces/UPSTREAM_ICD.md", reg.icd_status.upper().startswith("FROZEN")))
            detail["upstream_icd"] = {"document": ICD, "document_status": reg.icd_status,
                                      "interfaces": {i: reg.icd_field_status[i] for i in ids}}
        elif kind == "hardware_definition":
            for i in ids:
                reg.resolve(f"HW:{i}")
            doc_states.append((HWDEF, reg.hw_doc_status == "FROZEN"))
            detail["hardware_definition"] = {"document": HWDEF, "document_status": reg.hw_doc_status,
                                             "items": {i: reg.hw_status.get(i, "defined item/plane") for i in ids}}
        elif kind == "boundary_contract":
            for c in ids:
                if c not in reg.boundary_components:
                    raise KeyError(f"boundary component {c}")
            doc_states.append((BOUNDARY_PY, True))
            detail["boundary_contract"] = {"document": f"{BOUNDARY_PY} (BOUNDARY_VERSION bus_power_boundary_v1; power-accounting boundary, not an electrical ICD)",
                                           "document_status": "FROZEN (accounting boundary only)", "components": ids}
        elif kind == "state_machine":
            doc_states.append((DFS, reg.dfs_status == "FROZEN"))
            detail["state_machine"] = {"document": DFS, "document_status": reg.dfs_status}
        elif kind == "parallel":
            detail["parallel"] = {lane: {"expected_paths": PARALLEL[lane], "state": parallel_state[lane]["state"]} for lane in ids}
        else:
            raise KeyError(f"unknown interface document kind {kind}")
    base = [s for s in doc_states if s[0] != BOUNDARY_PY]
    if not doc_states:
        status = "OPEN"
    elif base and all(f for _, f in base) and "parallel" not in docs:
        status = "FROZEN"
    elif base or doc_states:
        status = "PARTIAL"
    return {"status": status, "documents": detail}


def _first_gate_blocks(first_gate):
    if first_gate is None:
        return {g: False for g in GATES}
    if first_gate not in GATES:
        raise ValueError(f"unknown gate {first_gate}")
    i = GATES.index(first_gate)
    return {g: (k >= i) for k, g in enumerate(GATES)}


def build(root: str = ROOT_DEFAULT) -> dict:
    pins = verify_pins(root)
    a5 = _load(root, A5)
    a6 = _load(root, A6)
    if A6_SEQUENCE_TEXT not in a6["authorized_now"]["fo_phase1_prereg_framework"]:
        raise ValueError("A6 gate sequence text not found verbatim; refusing to build")
    for name in P1DQ.values():
        if name not in a6["authorized_now"]["fo_phase1_prereg_framework"]:
            raise ValueError(f"Phase-1 decision quantity {name!r} not in A6")
    for rel in EVIDENCE_MATRICES.values():
        if not os.path.isfile(os.path.join(root, rel)):
            raise FileNotFoundError(rel)
    reg = Registry(root)
    parallel = probe_parallel(root)
    arch = a5["architecture"]
    if arch["baseline_subsystem_count"] != 16:
        raise ValueError("A5 baseline_subsystem_count is not 16")
    risks = {str(r["rank"]): r["risk"] for r in a5["architecture_closing_risks"]}

    rows_out = []
    for n, spec in enumerate(ROWS + [RESERVED_ROW], start=1):
        if spec["group"] == "reserved_interface":
            name = arch["reserved_interface"]["name"]
            if arch["reserved_interface"]["baseline_flight_hardware"] is not False:
                raise ValueError("A5 reserved interface is not flagged baseline_flight_hardware false")
            flag = "reserved, not baseline flight hardware"
            locator = f"{A5}#architecture.reserved_interface.name"
        else:
            name = arch[spec["group"]][spec["index"]]
            flag = "baseline subsystem"
            locator = f"{A5}#architecture.{spec['group']}[{spec['index']}]"
        cells = {}
        for col in COLUMNS:
            if col == "owner":
                cells[col] = {"value": "OWNER_TO_ASSIGN", "basis": OWNER_BASIS}
                continue
            c = json.loads(json.dumps(spec[_COL_FROM_ROW[col]]))
            refs = c.pop("refs", [])
            resolved = [reg.resolve(r) for r in refs]
            if col == "interface_status":
                st = _interface_status(reg, c.pop("docs"), parallel)
                c = {"status": st["status"], "documents": st["documents"], "note": c.get("note", "")}
            if col == "blocker":
                if c["category"] not in BLOCKER_CATEGORIES:
                    raise ValueError(f"row {name}: unknown blocker category {c['category']}")
                c["blocks_gates"] = _first_gate_blocks(c["first_gate"])
                if c["first_gate"] is None and c.get("beyond") not in BEYOND:
                    raise ValueError(f"row {name}: a blocker off the gate path needs a 'beyond' reason")
                c["beyond_meaning"] = BEYOND.get(c["beyond"]) if c.get("beyond") else None
            if col == "allocation":
                for e in c["entries"]:
                    for k in ("quantity", "value", "status", "evidence_class", "source"):
                        if not e.get(k):
                            raise ValueError(f"row {name}: allocation entry missing {k}")
                if not c["entries"] and c["status"] != "TO_BE_ALLOCATED":
                    raise ValueError(f"row {name}: allocation without entries must be TO_BE_ALLOCATED")
            srcs = list(c.get("sources", []))
            for it in c.get("items", []):
                srcs.append(it["source"])
            for e in c.get("entries", []) + c.get("context", []):
                srcs.append(e["source"])
            _check_source_paths(root, srcs)
            if resolved:
                c["refs"] = resolved
            cells[col] = c
        par_refs = sorted({r["ref"].split(":", 1)[1] for col in cells.values() for r in col.get("refs", []) if r["ref"].startswith("PAR:")}
                          | set(cells["interface_status"]["documents"].get("parallel", {}).keys()))
        rows_out.append({
            "row": n,
            "key": spec["key"],
            "group": spec["group"],
            "name": name,
            "name_source": locator,
            "flag": flag,
            "baseline_flight_hardware": spec["group"] != "reserved_interface",
            "cells": cells,
            "depends_on_parallel_lanes": {lane: ("pending parallel lane " + lane) if parallel[lane]["state"] == "PENDING_PARALLEL_LANE"
                                          else "present, pending review" for lane in par_refs},
            "a5_risk_mapping": [{"rank": int(k), "risk": risks[k], "role": v} for k, v in sorted(spec["risks"].items())],
        })

    # ----------------------------------------------------------------- rollups
    cat_rows = {c: [] for c in BLOCKER_CATEGORIES}
    gate_rows = {g: [] for g in GATES}
    beyond_rows = {b: [] for b in BEYOND}
    for r in rows_out:
        b = r["cells"]["blocker"]
        cat_rows[b["category"]].append(r["name"])
        if b["first_gate"]:
            gate_rows[b["first_gate"]].append(r["name"])
        else:
            beyond_rows[b["beyond"]].append(r["name"])
    earliest = next((g for g in GATES if gate_rows[g]), None)
    path_cats = {}
    for r in rows_out:
        b = r["cells"]["blocker"]
        if b["first_gate"]:
            path_cats[b["category"]] = path_cats.get(b["category"], 0) + 1
    branch_rows = beyond_rows["PHASE1_BRANCH_DECISION"]
    branch_cats = sorted({r["cells"]["blocker"]["category"] for r in rows_out if r["name"] in branch_rows})
    risk_rollup = {}
    for k in sorted(risks):
        risk_rollup[k] = {"risk": risks[k],
                          "primary_rows": [r["name"] for r in rows_out for m in r["a5_risk_mapping"] if str(m["rank"]) == k and m["role"].startswith("primary")],
                          "contributing_rows": [r["name"] for r in rows_out for m in r["a5_risk_mapping"] if str(m["rank"]) == k and m["role"].startswith("contributing")]}

    rollup = {
        "definitions": BLOCKER_CATEGORIES,
        "rows_per_category": {c: {"count": len(v), "rows": v} for c, v in cat_rows.items()},
        "rows_per_first_gate": {g: {"count": len(v), "rows": v} for g, v in gate_rows.items()},
        "rows_off_gate_path": {b: {"count": len(v), "rows": v, "meaning": BEYOND[b]} for b, v in beyond_rows.items()},
        "earliest_blocked_gate": earliest,
        "categories_blocking_the_phase1_path": {k: path_cats[k] for k in sorted(path_cats)},
        "categories_blocking_the_branch_decision": branch_cats,
        "risk_rollup": risk_rollup,
        "answer": _answer(earliest, gate_rows, path_cats, branch_cats, branch_rows, cat_rows, reg,
                          beyond_rows["FLIGHT_DESIGN_FREEZE"],
                          sorted({r["cells"]["blocker"]["category"] for r in rows_out if r["cells"]["blocker"].get("beyond") == "FLIGHT_DESIGN_FREEZE"})),
    }

    snapshot = {
        "bundle1_outcome": reg.bundle1,
        "credible_hall_set": "EMPTY (CLAUDE.md gate 3 FAIL; A4 project_conclusion; hard_gate_status admitted_members = [])",
        "hard_gates_eliminated": reg.hg_eliminated,
        "hard_gates_admitted_members": reg.hg_admitted,
        "veto_layer_status_counts": reg.veto_counts,
        "s1a_verdict": reg.s1a_verdict, "s1a_satisfied": f"{reg.s1a_counts[0]}/{reg.s1a_counts[1]}", "s1a_conditions": reg.s1a,
        "s1_verdict": reg.s1_verdict, "s1_satisfied": f"{reg.s1_counts[0]}/{reg.s1_counts[1]}", "s1_conditions": reg.s1,
        "lock1_brief_status": reg.lock1_status,
        "lock1_open_decisions": sorted(k for k, v in reg.lock1.items() if v == "OPEN_OWNER_DECISION"),
        "w5_prereg_status": reg.w5_status,
        "hardware_definition_status": reg.hw_doc_status,
        "upstream_icd_status": reg.icd_status,
        "state_machine_status": reg.dfs_status,
        "mass_rollup_strict": reg.bom_rollups,
        "aux_bus_ledgers": reg.aux_ledgers,
        "metrology_spec_file_status": reg.metrology_status,
        "metrology_spec_owner_approval": "APPROVED_FOR_PROCUREMENT as the procurement specification; not a demonstrated capability (A4 decisions.metrology_specification)",
        "compressor_C1": "LEADING_CANDIDATE_PENDING_PRIMARY_EVIDENCE (A4 decisions.DI_1_4_compressor_C1)",
        "mcq_s1_gate_items": reg.mcq,
    }

    inputs_read = {rel: _sha(os.path.join(root, rel)) for rel in BASE_INPUTS}

    return {
        "schema": "subsystem_maturity_matrix_v1",
        "id": "subsystem_maturity_v1",
        "lane": "fo_subsystem_maturity_matrix (M16)",
        "trigger": "T_A5_SUBSYSTEM_MATURITY",
        "authorization": f"{A6}#authorized_now.fo_subsystem_maturity_matrix",
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "generated_by": SCRIPT_REL,
        "companion_document": f"{REL}/{OUT_MD}",
        "what_it_is": "the central execution dashboard (A6): per A5 subsystem, requirement -> allocation -> interface status -> "
                      "preliminary design -> evidence status -> procurement status -> analysis/test needed -> blocker -> owner",
        "what_it_is_not": [
            "not a performance prediction: every A5 number is an allocation or requirement, never a prediction",
            "not an architecture ranking: no winner among hall_only, rf_hall, ecr_hall; the branch is decided by H-1 Phase 1 only",
            "not a change of Bundle 1 (stays NO_BASELINE_YET) and not an admission of any Hall closure (credible set EMPTY)",
            "not a sub-allocation: where no allocation exists in A5 / A4 / mass_bom / power_boundary / aux_bus the cell reads TO_BE_ALLOCATED",
            "not a procurement record: procurement status is only what the base records; otherwise 'UNKNOWN - owner to confirm'",
            "not an owner assignment: no accountable party is recorded, so every owner cell reads OWNER_TO_ASSIGN",
        ],
        "pins": {"sha256": pins, "note": "immutable decision inputs verified at build time; mutable governance files "
                                         "(lane/trigger registries, trigger ledger, runtime_state) are never pinned"},
        "g0_record": {"file": G0, "sha256": PINS[G0], "verdict": "CLEAN", "verified_a5_sha256": PINS[A5]},
        "inputs_read_sha256": inputs_read,
        "evidence_matrices": EVIDENCE_MATRICES,
        "architecture_branch_ids": ["hall_only", "rf_hall", "ecr_hall"],
        "gate_sequence": {"text": A6_SEQUENCE_TEXT, "source": f"{A6}#authorized_now.fo_phase1_prereg_framework", "gates": GATES},
        "phase1_decision_quantities": {"source": f"{A6}#authorized_now.fo_phase1_prereg_framework (names verbatim; ids local to this matrix)", "items": P1DQ},
        "columns": COLUMNS,
        "placeholders": list(PLACEHOLDERS),
        "rows": rows_out,
        "blocker_rollup": rollup,
        "base_status_snapshot": snapshot,
        "parallel_lanes": parallel,
        "milestone": _milestone(),
        "compliance": {
            "no_hall_performance_source": "no Hall transport closure, screening candidate (sgb-screen-*) or withdrawn 0-D number is used",
            "no_winner": "no architecture is ranked, preferred or eliminated",
            "nuisance": "P5 calibration nuisance (registration, coil shape, divergence reading, facility interpretation) is not a row, column or variable",
            "upstream": "Hall-closure uncertainty does not enter any atmospheric- or Xe-branch cell",
            "pure": "standard library only; nothing wired into archengine; no frozen data, golden, prereg or campaign file touched",
            "no_invention": "every typed id is resolved against its defining base file at build time; unknown ids raise",
        },
    }


def _answer(earliest, gate_rows, path_cats, branch_cats, branch_rows, cat_rows, reg, flight_rows, flight_cats) -> dict:
    top = sorted(path_cats.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "architecture_branch_decision": (
            f"blocked by {', '.join(branch_cats)} (rows: {', '.join(branch_rows)}): atmospheric sustainment at low flow and "
            f"high O2 fraction (A5 risk 1) is undemonstrated and the credible Hall set is EMPTY; only H-1 Phase 1 can "
            f"resolve it. The branch outcome also depends on the common bus-power, mass and life constraints (A5 case "
            f"NO_VIABLE_CASE; risks 2-4), which stay open but do not decide between A/B/C before Phase-1 data exist."),
        "path_to_phase1": (
            f"the earliest blocked gate is {earliest} ({len(gate_rows[earliest]) if earliest else 0} rows); rows blocking a "
            f"gate on the Phase-1 path by category: " + ", ".join(f"{k} {v}" for k, v in top) +
            f". S1a is {reg.s1a_verdict} ({reg.s1a_counts[0]}/{reg.s1a_counts[1]}), S1 is {reg.s1_verdict} "
            f"({reg.s1_counts[0]}/{reg.s1_counts[1]}), LOCK-1 has {sum(1 for v in reg.lock1.values() if v == 'OPEN_OWNER_DECISION')} "
            f"open owner decisions. What stops the architecture question from being asked on hardware is "
            f"{' and '.join(k for k, _ in top[:2])}"
            + ("" if "propulsion physics" in path_cats else ", not propulsion physics") + "."),
        "flight_closure": (
            f"{', '.join(flight_cats)} items block flight design freeze (Milestone C) but none gates Phase 1 "
            f"({len(flight_rows)} rows off the gate path). Mass is the single current blocker of {len(cat_rows['mass'])} rows; that is NOT "
            f"evidence that mass closes: the strict mass roll-up is {'/'.join(sorted(set(reg.bom_rollups.values())))} for "
            f"{', '.join(sorted(reg.bom_rollups))} (every item TBD), and A5 risk 4 (bus power and mass closure) remains open."),
        "status": "PROPOSED reading for the owner (the rollup counts are mechanical; the category assignment of each blocker is this lane's reading)",
    }


def _milestone() -> dict:
    return {
        "supports": ["A"],
        "statement": (
            "Milestone A (conditional selection): SUPPORTED as an execution input only. The matrix states, per A5 subsystem, "
            "the conditions that must be demonstrated for the A5 proposal reference architecture to hold; it selects no "
            "architecture branch and leaves Bundle 1 at NO_BASELINE_YET. Milestone B (physics-backed selection): NOT "
            "supported - it needs an admitted Hall closure or H-1 Phase-1 data (credible set EMPTY). Milestone C "
            "(proposal/PDR freeze): input only - it lists the TO_BE_ALLOCATED / TBD / UNKNOWN cells that must close."),
        "three_questions": {
            "i_conditional_selection_now": "none; A5 is a frozen proposal reference, the branch (hall_only / rf_hall / ecr_hall / NO_VIABLE_CASE) is open until H-1 Phase 1",
            "ii_what_blocks_physics_backed_selection": "propulsion physics (A5 risk 1) resolvable only on H-1; on the path to it: S1a/S1 readiness items (procurement) and LOCK-1 open decisions / interfaces",
            "iii_what_could_overturn": "A5 risks 2-4: oxygen/anode/channel life, cathode Xe consumption and isolation, bus-power and mass closure with all auxiliaries",
        },
        "unlocks": [
            "gives the three parallel lanes (fo_preionizer_module_icd, fo_xe_system_ledger, fo_phase1_prereg_framework) fixed cells to fill: rerunning the builder records their presence",
            "names the planned next-wave hardware work per row (A6 next_wave_planned) without registering it",
        ],
    }


# --------------------------------------------------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------------------------------------------------
def _cell_summary(col: str, c: dict) -> str:
    if col == "owner":
        return c["value"]
    if col == "allocation":
        if c["entries"]:
            return "; ".join(f"{e['quantity']}: {e['value']} ({e['status'].split(' (')[0].split(';')[0].split(',')[0]})" for e in c["entries"]) + f" [{c['status']}]"
        return "TO_BE_ALLOCATED"
    if col == "interface_status":
        docs = []
        d = c["documents"]
        if "upstream_icd" in d:
            docs.append("ICD " + "/".join(d["upstream_icd"]["interfaces"]))
        if "hardware_definition" in d:
            docs.append("HW " + ", ".join(list(d["hardware_definition"]["items"])[:4]) + ("..." if len(d["hardware_definition"]["items"]) > 4 else ""))
        if "boundary_contract" in d:
            docs.append("bus_power_boundary_v1")
        if "state_machine" in d:
            docs.append("dual_feed_state_machine_v1")
        if "parallel" in d:
            docs.append("pending " + ", ".join(d["parallel"]))
        return f"**{c['status']}** ({'; '.join(docs)})"
    if col == "procurement_status":
        return c["status"]
    if col == "blocker":
        g = f"first gate blocked: {c['first_gate']}" if c["first_gate"] else f"off the gate path: {c['beyond']}"
        return f"{c['item']} [**{c['category']}**; {g}]"
    return c.get("summary", "")


def _esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# Subsystem maturity matrix v1 (M16) - central execution dashboard")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| lane | `{doc['lane']}` (trigger `{doc['trigger']}`, authorized by `{doc['authorization']}`) |")
    a(f"| status | **{doc['status']}** |")
    a(f"| generated by | `{doc['generated_by']}` (`--check` reproduces this file and the JSON exactly) |")
    a(f"| machine-readable | `{REL}/{OUT_JSON}` |")
    a(f"| tests | `tests/test_subsystem_maturity.py` |")
    a("")
    a("**Pinned immutable inputs (sha256, verified at build time):**")
    a("")
    for rel, h in doc["pins"]["sha256"].items():
        a(f"- `{rel}` - `{h}`")
    a("")
    a("Mutable governance files (lane/trigger registries, trigger ledger, `runtime_state.json`) are never pinned.")
    a("")
    a("## Milestone statement")
    a("")
    m = doc["milestone"]
    a(m["statement"])
    a("")
    for k, v in m["three_questions"].items():
        a(f"- **{k}**: {v}")
    a("")
    a("What this is not: " + "; ".join(doc["what_it_is_not"]) + ".")
    a("")
    a("## Dashboard (one line per row; details and sources below)")
    a("")
    head = ["#", "subsystem (A5 name)"] + doc["columns"]
    a("| " + " | ".join(head) + " |")
    a("|" + "---|" * len(head))
    for r in doc["rows"]:
        name = r["name"] + (" *(reserved, not baseline flight hardware)*" if not r["baseline_flight_hardware"] else "")
        cells = [_esc(_cell_summary(col, r["cells"][col])) for col in doc["columns"]]
        a(f"| {r['row']} | {_esc(name)} | " + " | ".join(cells) + " |")
    a("")
    a("## Blocker rollup - which category actually blocks the architecture")
    a("")
    ro = doc["blocker_rollup"]
    for k in ("architecture_branch_decision", "path_to_phase1", "flight_closure"):
        a(f"- **{k.replace('_', ' ')}**: {ro['answer'][k]}")
    a(f"- *{ro['answer']['status']}*")
    a("")
    a("| category | rows (single current blocker) | definition |")
    a("|---|---|---|")
    for c, v in ro["rows_per_category"].items():
        a(f"| {c} | {v['count']}: {', '.join(v['rows']) or '-'} | {_esc(ro['definitions'][c])} |")
    a("")
    a("| first gate blocked (A6 sequence `" + doc["gate_sequence"]["text"] + "`) | rows |")
    a("|---|---|")
    for g, v in ro["rows_per_first_gate"].items():
        a(f"| {g} | {v['count']}: {', '.join(v['rows']) or '-'} |")
    for b, v in ro["rows_off_gate_path"].items():
        a(f"| off the gate path: {b} | {v['count']}: {', '.join(v['rows']) or '-'} |")
    a("")
    a("A blocker at a gate blocks every later gate in the A6 sequence (`blocks_gates` in the JSON).")
    a("")
    a("### Mapping to the A5 architecture-closing risks")
    a("")
    a("| rank | risk | primary rows | contributing rows |")
    a("|---|---|---|---|")
    for k, v in ro["risk_rollup"].items():
        a(f"| {k} | {_esc(v['risk'])} | {', '.join(v['primary_rows']) or '-'} | {', '.join(v['contributing_rows']) or '-'} |")
    a("")
    a("## Parallel lanes (lazy probe; content never interpreted here)")
    a("")
    a("| lane | expected paths | state |")
    a("|---|---|---|")
    for lane, v in doc["parallel_lanes"].items():
        a(f"| `{lane}` | {', '.join('`' + p + '`' for p in v['expected_paths'])} | {v['state']} ({len(v['files'])} files) |")
    a("")
    a("## Base status snapshot (read at build time)")
    a("")
    s = doc["base_status_snapshot"]
    for k in ("bundle1_outcome", "credible_hall_set", "hard_gates_eliminated", "s1a_verdict", "s1a_satisfied", "s1_verdict",
              "s1_satisfied", "lock1_brief_status", "lock1_open_decisions", "w5_prereg_status", "hardware_definition_status",
              "upstream_icd_status", "state_machine_status", "mass_rollup_strict", "aux_bus_ledgers", "compressor_C1",
              "metrology_spec_owner_approval"):
        a(f"- `{k}`: {json.dumps(s[k]) if not isinstance(s[k], str) else s[k]}")
    a("")
    a("## Row details")
    for r in doc["rows"]:
        a("")
        a(f"### {r['row']}. {r['name']} (`{r['key']}`, {r['group']}; {r['flag']})")
        a("")
        a(f"Name source: `{r['name_source']}`.")
        if r["depends_on_parallel_lanes"]:
            a("Depends on: " + "; ".join(f"`{k}`: {v}" for k, v in r["depends_on_parallel_lanes"].items()) + ".")
        a("")
        for col in doc["columns"]:
            c = r["cells"][col]
            a(f"- **{col}**: {_esc(_cell_summary(col, c))}")
            if col == "requirement":
                for it in c["items"]:
                    a(f"  - {_esc(it['text'])} - *{it['class']}* - `{it['source']}`")
            if col == "allocation":
                if c.get("note"):
                    a(f"  - {_esc(c['note'])}")
                for e in c["entries"]:
                    a(f"  - {e['quantity']} = {e['value']} ({e['status']}; {e['evidence_class']}) - `{e['source']}`")
                for e in c.get("context", []):
                    a(f"  - context only: {e['quantity']} = {e['value']} ({e['status']}; {e['evidence_class']}) - `{e['source']}`")
            if col == "interface_status":
                if c.get("note"):
                    a(f"  - {_esc(c['note'])}")
                d = c["documents"]
                if "upstream_icd" in d:
                    for i, cnt in d["upstream_icd"]["interfaces"].items():
                        a(f"  - {i} field statuses: {json.dumps(cnt)} (ICD {d['upstream_icd']['document_status']})")
            if col == "evidence_status":
                a(f"  - classes: {', '.join(c['classes'])}; matrices: {', '.join('`' + x + '`' for x in c['matrices']) or 'none'}")
            if col == "procurement_status":
                for x in c["recorded"]:
                    a(f"  - {_esc(x)}")
            if col == "blocker":
                gates = [g for g, v in c["blocks_gates"].items() if v]
                a(f"  - blocks: {', '.join(gates) if gates else 'none of ' + ', '.join(GATES)}"
                  + (f"; {c['beyond_meaning']}" if c.get("beyond_meaning") else ""))
                if c.get("decision_by"):
                    a(f"  - decision by: {c['decision_by']}")
                if c.get("note"):
                    a(f"  - {_esc(c['note'])}")
            if col == "owner":
                a(f"  - {c['basis']}")
            if c.get("refs"):
                a("  - refs: " + ", ".join(f"`{x['ref']}`" + (f" ({x['state']})" if 'state' in x else "") for x in c["refs"]))
            if c.get("sources"):
                a("  - sources: " + "; ".join(f"`{x}`" for x in c["sources"]))
        a(f"- **A5 risks**: " + "; ".join(f"{m['rank']} ({m['role']})" for m in r["a5_risk_mapping"]))
    a("")
    return "\n".join(L)


def dump_json(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=ROOT_DEFAULT)
    args = ap.parse_args(argv)
    doc = build(args.root)
    js, md = dump_json(doc), render_md(doc)
    pj, pm = os.path.join(args.root, REL, OUT_JSON), os.path.join(args.root, REL, OUT_MD)
    if args.write:
        with open(pj, "w", encoding="utf-8") as f:
            f.write(js)
        with open(pm, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"wrote {REL}/{OUT_JSON} and {REL}/{OUT_MD} ({len(doc['rows'])} rows)")
        return 0
    ok = True
    for p, want in ((pj, js), (pm, md)):
        if not os.path.isfile(p) or open(p, encoding="utf-8").read() != want:
            print(f"STALE: {os.path.relpath(p, args.root)}")
            ok = False
    print("OK" if ok else "rebuild with --write")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
