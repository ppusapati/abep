#!/usr/bin/env python3
"""A9_INT core integration record (fo_a9_int_core_integration, trigger T_A9_INT_CORE_INTEGRATION) -- deterministic builder.

MECHANICAL INTEGRATION / RECONCILIATION OF A9-01..A9-05. NOT A NEW SCIENTIFIC RESULT.

Writes
  docs/experiments/hall_icp/integration/a9_core_integration_v1.json   (authoritative, machine-readable)
  docs/experiments/hall_icp/integration/A9_CORE_INTEGRATION.md        (rendered from the JSON)

What it records and machine-checks (base commit BASE, read with ``git show``; current files from the working tree):
  1. the id mapping UB-DQ-* (A9-04 provisional) -> DQ-HI-* (A9-01 final), read from the A9-04 deliverable and checked
     against the A9-01 decision quantities; ids without a unique counterpart are kept and marked 'UNMAPPED - owner/A9-10';
  2. every resolved 'PENDING <A9 lane>' cross-reference (declared below, with its target file and item ids; each target
     item is checked to exist) and every remaining PENDING occurrence with a reason code;
  3. the no-change statement: every numeric leaf (int / float / bool / null) of every A9 JSON deliverable is equal before
     (BASE) and after this lane; every changed string leaf is explained exactly by a declared reference resolution or by
     the declared id rename; no key or list element is removed; the only added key is A9-04 /dq_id_mapping;
  4. pinned-input sha256 updates (none needed: no pinned file changed) and the post-integration sha256 of every target;
  5. that no historical / immutable artifact changed.

No physics value, threshold, gate, allocation, requirement meaning, evidence class or owner-answer interpretation is
changed; the A9.1 follow-up owner decisions are read, not applied (A9-06..A9-10). Standard library only; no network.

Usage:
  python docs/experiments/hall_icp/integration/build_a9_core_integration.py           # (re)write JSON + MD
  python docs/experiments/hall_icp/integration/build_a9_core_integration.py --check   # exit 1 on any drift / failure
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LANE_DIR = "docs/experiments/hall_icp/integration"
JSON_REL = LANE_DIR + "/a9_core_integration_v1.json"
MD_REL = LANE_DIR + "/A9_CORE_INTEGRATION.md"
SCRIPT_REL = LANE_DIR + "/build_a9_core_integration.py"
TEST_REL = "tests/test_a9_core_integration.py"

BASE = "88e4d478b81b25f0b4fd7de32aa5f76f0726c361"
CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
UNMAPPED = "UNMAPPED - owner/A9-10"

# ------------------------------------------------------------------------------------------------------------------
# Authority (immutable; pinned by sha256) and governance (mutable; never pinned)
# ------------------------------------------------------------------------------------------------------------------
AUTHORITY_PINS = [
    ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
     "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
     "A9 governing owner decision (OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE)"),
    ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
     "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
     "owner answers 1-147 (machine-readable; cited by row)"),
    ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
     "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976",
     "verbatim owner decision pack 147"),
    ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
     "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4",
     "A9.1 follow-up owner decisions: execution step_1_integration_repair defines this lane; the HIQ-/UBQ-/ICPQ- "
     "decisions are read, NOT applied here (A9-06..A9-10)"),
    ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
     "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e",
     "A9.1 verbatim"),
]
GOVERNANCE_NOT_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                         "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/runtime_state.json"]

# ------------------------------------------------------------------------------------------------------------------
# The five A9 deliverables (A9-05 has two parts). json = the machine-readable deliverable compared leaf by leaf.
# ------------------------------------------------------------------------------------------------------------------
J01 = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
J02 = "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json"
M02 = "abep_sim/bus_boundary_a9.py"
S02 = "schemas/interfaces/bus_power_boundary_a9_v1.json"
J03 = "schemas/interfaces/icp_neutralizer_icd_v1.json"
J04 = "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json"
EV = "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json"
PX = "docs/evidence/icp_neutralizer/takahashi2024_fig_pixels_v1.json"
VI = "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json"

DELIVERABLES = [
    {"key": "A9-01", "lane": "fo_a9_01_hall_icp_prereg_framework", "json": J01,
     "md": "docs/experiments/hall_icp/prereg_framework/HALL_ICP_PREREG_FRAMEWORK.md",
     "builder": "docs/experiments/hall_icp/prereg_framework/build_hall_icp_prereg_framework.py",
     "builder_check_args": ["--check"], "test": "tests/test_hall_icp_prereg_framework.py"},
    {"key": "A9-02", "lane": "fo_a9_02_bus_boundary_a9", "json": J02,
     "md": "docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md",
     "builder": "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py",
     "builder_check_args": ["--check"], "test": "tests/test_bus_boundary_a9.py", "extra": [S02, M02]},
    {"key": "A9-03", "lane": "fo_a9_03_icp_neutralizer_icd", "json": J03,
     "md": "docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md",
     "builder": "docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py",
     "builder_check_args": ["--check"], "test": "tests/test_icp_neutralizer_icd.py"},
    {"key": "A9-04", "lane": "fo_a9_04_hall_icp_uncertainty_budget", "json": J04,
     "md": "docs/experiments/hall_icp/uncertainty_budget/HALL_ICP_UNCERTAINTY_BUDGET.md",
     "builder": "docs/experiments/hall_icp/uncertainty_budget/build_hall_icp_uncertainty_budget.py",
     "builder_check_args": ["--check"], "test": "tests/test_hall_icp_uncertainty_budget.py"},
    {"key": "A9-05ev", "lane": "fo_a9_05_hall_icp_validation_inputs (part 1, evidence)", "json": EV,
     "md": "docs/evidence/icp_neutralizer/ICP_NEUTRALIZER_EVIDENCE.md",
     "builder": "docs/evidence/icp_neutralizer/build_icp_neutralizer_evidence.py",
     "builder_check_args": ["--check"], "test": "tests/test_hall_icp_validation_inputs.py", "extra": [PX]},
    {"key": "A9-05vi", "lane": "fo_a9_05_hall_icp_validation_inputs (part 2, validation inputs)", "json": VI,
     "md": "docs/experiments/hall_icp/validation_inputs/HALL_ICP_VALIDATION_INPUTS.md",
     "builder": "docs/experiments/hall_icp/validation_inputs/build_hall_icp_validation_inputs.py",
     "builder_check_args": ["--check"], "test": "tests/test_hall_icp_validation_inputs.py"},
]
# JSON files compared leaf by leaf (the six deliverables + the A9-02 instance schema + the A9-05 pixel record)
COMPARED_JSON = [(d["key"], d["json"]) for d in DELIVERABLES] + [("A9-02", S02), ("A9-05ev", PX)]
# the only key this lane may add to a deliverable
ALLOWED_ADDED_KEYS = {(J04, "/dq_id_mapping")}

# Pinned inputs between the A9 deliverables at BASE (path -> pinned by). Recomputed and verified in build().
PINNED_INPUT_LINKS = [
    {"pinned_file": EV, "pinned_by": VI, "field": "/evidence_input/sha256"},
    {"pinned_file": PX, "pinned_by": EV, "field": "/pixel_record/sha256"},
]

# Historical / immutable artifacts that must be byte-identical to BASE (A9 supersession rule; read-only for this lane)
HISTORICAL_ROOTS = ["docs/experiments/phase1_prereg_framework", "docs/interfaces/preionizer_module",
                    "docs/architecture_comparison/lock1", "abep_sim/arch_boundary.py",
                    "schemas/interfaces/preionizer_module_icd_v1.json", "docs/decisions"]

# ------------------------------------------------------------------------------------------------------------------
# Declared reference resolutions. Each: deliverable json, JSON pointer (regex, full match), old substring (must occur
# in the BASE leaf), new text, and the target file(s) + item ids that define the referenced thing (checked to exist).
# ------------------------------------------------------------------------------------------------------------------
INT_REL = JSON_REL
P01_02 = "PENDING docs/architecture_comparison/power_boundary_a9/ (A9-02)"
P01_03 = "PENDING docs/interfaces/icp_neutralizer/ (A9-03)"
P01_04 = "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04)"
P01_05 = "PENDING docs/evidence/icp_neutralizer/ and docs/experiments/hall_icp/validation_inputs/ (A9-05)"
REF01_02 = J02 + " (A9-02)"
REF01_02_SLOTS = J02 + " slots (A9-02)"
REF01_03 = J03 + " (A9-03)"
REF01_04 = J04 + " (A9-04)"
REF01_05 = EV + " and " + VI + " (A9-05)"
A902_REF = M02 + " + " + J02


def icd01(*ids):
    return J03 + " " + ", ".join(ids) + " (A9-03)"


def ub01(what):
    return J04 + " " + what + " (A9-04)"


def R(key, ptr, old, new, targets):
    """targets: list of (file, [tokens]); a token is an item id, 'measurement_chains[dq=X]', 'slot NAME', a top-level
    key, or '' (file-level reference)."""
    return {"deliverable": key, "pointer": ptr, "old": old, "new": new, "targets": targets}


def _why(lane, target):
    return (lane + " deliverable merged in the base (" + target + "); cited by path, not pinned here "
            "(post-integration sha256 in " + INT_REL + ")")


RESOLUTIONS = [
    # ---------------- A9-01 prereg framework ----------------
    R("A9-01", r"/referenced_not_pinned\[5\]/why", "parallel lane A9-02, not in the base; PENDING",
      _why("A9-02", J02), [(J02, [""])]),
    R("A9-01", r"/referenced_not_pinned\[6\]/why", "parallel lane A9-02, not in the base; PENDING",
      "A9-02 module merged in the base; cited by path, not pinned here (post-integration sha256 in " + INT_REL + ")",
      [(M02, [""])]),
    R("A9-01", r"/referenced_not_pinned\[7\]/why", "parallel lane A9-03, not in the base; PENDING",
      _why("A9-03", J03), [(J03, [""])]),
    R("A9-01", r"/referenced_not_pinned\[8\]/why", "parallel lane A9-04, not in the base; PENDING",
      _why("A9-04", J04), [(J04, [""])]),
    R("A9-01", r"/referenced_not_pinned\[9\]/why", "parallel lane A9-05, not in the base; PENDING",
      _why("A9-05", EV), [(EV, [""])]),
    R("A9-01", r"/referenced_not_pinned\[10\]/why", "parallel lane A9-05, not in the base; PENDING",
      _why("A9-05", VI), [(VI, [""])]),
    R("A9-01", r"/stage_map\[1\]/entry\[1\]", P01_03, icd01("ICP-34"), [(J03, ["ICP-34"])]),
    R("A9-01", r"/stage_map\[3\]/what", P01_05, REF01_05, [(EV, [""]), (VI, [""])]),
    R("A9-01", r"/stage_map\[3\]/entry\[1\]", P01_03, REF01_03, [(J03, [""])]),
    R("A9-01", r"/stage_map\[4\]/what", P01_04, ub01("stop_rules"), [(J04, ["stop_rules"])]),
    R("A9-01", r"/stage_map\[4\]/entry\[1\]", P01_02, REF01_02_SLOTS, [(J02, ["slots"])]),
    R("A9-01", r"/stage_map\[4\]/entry\[2\]", P01_04, REF01_04, [(J04, [""])]),
    R("A9-01", r"/stage_map\[6\]/entry\[2\]", P01_03, REF01_03, [(J03, [""])]),
    R("A9-01", r"/stage_map\[11\]/entry\[1\]", P01_02, REF01_02_SLOTS, [(J02, ["slots"])]),
    R("A9-01", r"/gate_deadlines\[0\]/owner_lane", P01_03, REF01_03, [(J03, [""])]),
    R("A9-01", r"/gate_deadlines\[6\]/owner_lane", P01_04, ub01("stop_rules"), [(J04, ["stop_rules"])]),
    R("A9-01", r"/gate_deadlines\[7\]/owner_lane", P01_04, ub01("UB-C-01"), [(J04, ["UB-C-01"])]),
    R("A9-01", r"/gate_deadlines\[8\]/owner_lane", P01_04, ub01("UB-C-06, readiness_n"),
      [(J04, ["UB-C-06", "readiness_n"])]),
    R("A9-01", r"/gate_deadlines\[15\]/owner_lane", P01_04, ub01("UB-C-08, interpolation"),
      [(J04, ["UB-C-08", "interpolation"])]),
    R("A9-01", r"/configurations/common_article/carrier", P01_03, icd01("ICP-06", "ICP-07"),
      [(J03, ["ICP-06", "ICP-07"])]),
    R("A9-01", r"/configurations/configurations\[0\]/shams_present\[3\]", P01_03, icd01("ICP-09", "ICP-34"),
      [(J03, ["ICP-09", "ICP-34"])]),
    R("A9-01", r"/configurations/configurations\[1\]/shams_present\[2\]", P01_03, icd01("ICP-09"),
      [(J03, ["ICP-09"])]),
    R("A9-01", r"/configurations/topology_precedent/extraction", P01_05, REF01_05, [(EV, [""]), (VI, [""])]),
    R("A9-01", r"/module_exchange\[1\]/interface_reference", P01_03,
      icd01("ICP-06", "ICP-07", "ICP-15", "ICP-18", "ICP-21", "ICP-27", "ICP-33", "ICP-34", "ICP-39"),
      [(J03, ["ICP-06", "ICP-07", "ICP-15", "ICP-18", "ICP-21", "ICP-27", "ICP-33", "ICP-34", "ICP-39"])]),
    R("A9-01", r"/same_condition/variables\[13\]/instruments\[2\]", P01_03, icd01("ICP-34"), [(J03, ["ICP-34"])]),
    R("A9-01", r"/decision_quantities\[1\]/measurement_chain\[2\]", P01_03, icd01("ICP-21"), [(J03, ["ICP-21"])]),
    R("A9-01", r"/decision_quantities\[2\]/measurement_chain\[1\]", P01_03, icd01("ICP-20", "ICP-21"),
      [(J03, ["ICP-20", "ICP-21"])]),
    R("A9-01", r"/decision_quantities\[7\]/measurement_chain\[5\]", P01_03, icd01("ICP-16"), [(J03, ["ICP-16"])]),
    R("A9-01", r"/decision_quantities\[3\]/measurement_chain_uncertainty_owner", P01_04,
      ub01("measurement_chains[dq=DQ-HI-TABS]"), [(J04, ["measurement_chains[dq=DQ-HI-TABS]"])]),
    R("A9-01", r"/decision_quantities\[4\]/measurement_chain_uncertainty_owner", P01_04,
      ub01("measurement_chains[dq=DQ-HI-PBUS]"), [(J04, ["measurement_chains[dq=DQ-HI-PBUS]"])]),
    R("A9-01", r"/decision_quantities\[16\]/measurement_chain_uncertainty_owner", P01_04,
      ub01("measurement_chains[dq=DQ-HI-ETAU]"), [(J04, ["measurement_chains[dq=DQ-HI-ETAU]"])]),
    R("A9-01", r"/decision_quantities\[4\]/operational_definition", P01_02, M02 + " + " + REF01_02,
      [(M02, [""]), (J02, ["slots"])]),
    R("A9-01", r"/decision_topology/external_inputs/boundary", P01_02, M02 + " + " + REF01_02,
      [(M02, [""]), (J02, [""])]),
    R("A9-01", r"/execution_design/stopped_arm", P01_04, ub01("stop_rules"), [(J04, ["stop_rules"])]),
    R("A9-01", r"/data_quality\[8\]/check", P01_02, REF01_02_SLOTS, [(J02, ["slots"])]),
    R("A9-01", r"/items\[29\]/source", P01_04, ub01("UB-C-01"), [(J04, ["UB-C-01"])]),
    R("A9-01", r"/items\[30\]/source", P01_04, ub01("UB-C-06, readiness_n"), [(J04, ["UB-C-06", "readiness_n"])]),
    R("A9-01", r"/items\[32\]/source", P01_04, ub01("stop_rules"), [(J04, ["stop_rules"])]),
    R("A9-01", r"/items\[39\]/source", P01_03, icd01("ICP-26"), [(J03, ["ICP-26"])]),
    R("A9-01", r"/items\[40\]/source", P01_05, REF01_05, [(EV, [""]), (VI, [""])]),
    R("A9-01", r"/interface_demands\[[01]\]/counterpart", P01_02, M02 + " + " + REF01_02, [(M02, [""]), (J02, [""])]),
    R("A9-01", r"/interface_demands\[[23]\]/counterpart", P01_03, REF01_03, [(J03, [""])]),
    R("A9-01", r"/interface_demands\[[45]\]/counterpart", P01_04, REF01_04, [(J04, [""])]),
    R("A9-01", r"/interface_demands\[[67]\]/counterpart", P01_05, REF01_05, [(EV, [""]), (VI, [""])]),
    R("A9-01", r"/owner_answers_applied\[8\]/applied_as", "new budget PENDING A9-04 (IF-HI-05/06)",
      "new budget " + J04 + " (A9-04; IF-HI-05/06)", [(J04, [""])]),
    R("A9-01", r"/h3_h4_inputs/h3_procurement_inputs_quotations_only\[1\]", P01_03, icd01("ICP-06"),
      [(J03, ["ICP-06"])]),
    # ---------------- A9-02 bus-power boundary ----------------
    R("A9-02", r"/items\[22\]/source", "PENDING docs/interfaces/icp_neutralizer/", J03 + " ICP-20, ICP-21",
      [(J03, ["ICP-20", "ICP-21"])]),
    R("A9-02", r"/items\[23\]/source", "PENDING docs/interfaces/icp_neutralizer/", J03 + " ICP-26",
      [(J03, ["ICP-26"])]),
    R("A9-02", r"/items\[35\]/source", "PENDING docs/experiments/hall_icp/uncertainty_budget/",
      J04 + " measurement_chains[dq=DQ-HI-PBUS]", [(J04, ["measurement_chains[dq=DQ-HI-PBUS]"])]),
    R("A9-02", r"/h3_inputs\[3\]/basis", "PENDING docs/interfaces/icp_neutralizer/", J03 + " ICP-21",
      [(J03, ["ICP-21"])]),
    # ---------------- A9-03 ICD ----------------
    R("A9-03", r"/published_analog_annex/source/authority_note", "(PENDING docs/evidence/icp_neutralizer/)",
      "(" + EV + ")", [(EV, [""])]),
    # ---------------- A9-04 uncertainty budget (references; the id rename is ID_RENAME below) ----------------
    R("A9-04", r"/decision_quantities\[0\]/(a9_01_dq_id|role)",
      "PENDING docs/experiments/hall_icp/prereg_framework/ (decision-quantity id and role)",
      J01 + " DQ-HI-TABS (role HARD_GATE)", [(J01, ["DQ-HI-TABS"])]),
    R("A9-04", r"/decision_quantities\[1\]/a9_01_dq_id",
      "PENDING docs/experiments/hall_icp/prereg_framework/ (decision-quantity id and role)",
      J01 + " DQ-HI-PBUS (role HARD_GATE)", [(J01, ["DQ-HI-PBUS"])]),
    R("A9-04", r"/decision_quantities\[9\]/a9_01_dq_id",
      "PENDING docs/experiments/hall_icp/prereg_framework/ (decision-quantity id and role)",
      J01 + " DQ-HI-ETAU (role CONDITIONAL)", [(J01, ["DQ-HI-ETAU"])]),
    R("A9-04", r"/decision_quantities\[2\]/role",
      "PENDING abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/",
      A902_REF + " slots icp_rf_source / icp_matching_network",
      [(J02, ["slot icp_rf_source", "slot icp_matching_network"])]),
    R("A9-04", r"/items\[3\]/note", "PENDING docs/interfaces/icp_neutralizer/", J03 + " ICP-08", [(J03, ["ICP-08"])]),
    R("A9-04", r"/measurement_chains\[1\]/equations\[0\]",
      "PENDING abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/", A902_REF + " slots",
      [(J02, ["slots"])]),
    R("A9-04", r"/measurement_chains\[2\]/not_a_component",
      "PENDING docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/", EV + " + " + VI,
      [(EV, [""]), (VI, [""])]),
    R("A9-04", r"/measurement_chains\[5\]/equations\[4\]", "PENDING docs/interfaces/icp_neutralizer/",
      J03 + " ICP-26", [(J03, ["ICP-26"])]),
    R("A9-04", r"/stop_rules/gate_stop/gate_definition", "PENDING docs/experiments/hall_icp/prereg_framework/",
      J01 + " DQ-HI-ECAP", [(J01, ["DQ-HI-ECAP"])]),
    R("A9-04", r"/stop_rules/not_tested/vocabulary_owner", "PENDING docs/experiments/hall_icp/prereg_framework/",
      J01 + " decision_topology (outcomes, statuses)", [(J01, ["decision_topology"])]),
    R("A9-04", r"/references\[7\]/access",
      "is PENDING docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/",
      "is in " + EV + " (A9-05)", [(EV, [""])]),
    R("A9-04", r"/compliance\[1\]", "(PENDING A9-05)", "(A9-05: " + EV + ")", [(EV, [""])]),
    R("A9-04", r"/h3_procurement_inputs\[3\]/spec_form", "PENDING docs/interfaces/icp_neutralizer/",
      J03 + " ICP-21", [(J03, ["ICP-21"])]),
    R("A9-04", r"/h3_procurement_inputs\[7\]/spec_form",
      "PENDING abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/", A902_REF + " slots",
      [(J02, ["slots"])]),
]

P5_901 = "PENDING docs/experiments/hall_icp/prereg_framework/ (A9-01 stage map)"
P5_902 = "PENDING abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/ (A9-02)"
P5_903 = "PENDING docs/interfaces/icp_neutralizer/ (A9-03 ICD)"
P5_904 = "PENDING docs/experiments/hall_icp/uncertainty_budget/ (A9-04 measurement chain / decision quantity)"


def _chain(dq):
    return J04 + " measurement_chains[dq=" + dq + "] (A9-04)"


def _slot(what):
    return A902_REF + " " + what + " (A9-02)"


def _icd5(*ids):
    return J03 + " " + ", ".join(ids) + " (A9-03 ICD)"


def _vi_chain(idx, dq):
    return R("A9-05vi", r"/items\[%s\]/how_obtained/chain" % idx, P5_904, _chain(dq),
             [(J04, ["measurement_chains[dq=" + dq + "]"])])


RESOLUTIONS += [
    R("A9-05vi", r"/decision_vocabulary/full_vocabulary", P5_901, J01 + " decision_topology (A9-01)",
      [(J01, ["decision_topology"])]),
    R("A9-05vi", r"/items\[1\]/definition", "PENDING A9-03", _icd5("ICP-14"), [(J03, ["ICP-14"])]),
    _vi_chain("[123]", "UB-DQ-RF"),
    R("A9-05vi", r"/items\[7\]/how_obtained/chain", P5_902, _slot("slot icp_rf_source"),
      [(J02, ["slot icp_rf_source"])]),
    R("A9-05vi", r"/items\[11\]/how_obtained/chain", P5_903, _icd5("ICP-20", "ICP-21", "ICP-34"),
      [(J03, ["ICP-20", "ICP-21", "ICP-34"])]),
    _vi_chain("(11|12|13|14|15|16|17)", "UB-DQ-NEUT"),
    R("A9-05vi", r"/items\[14\]/how_obtained/chain", P5_902, _slot("slot icp_collector_bias"),
      [(J02, ["slot icp_collector_bias"])]),
    R("A9-05vi", r"/items\[(19|35|36)\]/how_obtained/chain", P5_902, _slot("slots"), [(J02, ["slots"])]),
    _vi_chain("21", "UB-DQ-ID"),
    _vi_chain("23", "DQ-HI-TABS"),
    _vi_chain("25", "UB-DQ-BZ"),
    R("A9-05vi", r"/items\[(30|31)\]/how_obtained/chain", P5_903, _icd5("ICP-27"), [(J03, ["ICP-27"])]),
    R("A9-05vi", r"/items\[37\]/how_obtained/chain", P5_904, J04 + " UB-P-07 (A9-04)", [(J04, ["UB-P-07"])]),
    R("A9-05vi", r"/what_this_is_not\[3\]", "PENDING and referenced",
      "separate deliverables (" + J01 + "; " + A902_REF + "; " + J03 + "; " + J04 + ") referenced",
      [(J01, [""]), (M02, [""]), (J02, [""]), (J03, [""]), (J04, [""])]),
]

# A9-04 id rename: applied to every A9-04 string leaf outside the added /dq_id_mapping (whole-token, prefix-safe).
ID_RENAME = [("UB-DQ-T", "DQ-HI-TABS"), ("UB-DQ-PBUS", "DQ-HI-PBUS"), ("UB-DQ-ETAU", "DQ-HI-ETAU")]


def apply_id_rename(text: str) -> str:
    for old, new in ID_RENAME:
        text = re.sub(re.escape(old) + r"(?![A-Za-z0-9])", new, text)
    return text


# ------------------------------------------------------------------------------------------------------------------
# Remaining PENDING occurrences: reason codes. Explicit pointer rules first, then generic rules (first match wins).
# ------------------------------------------------------------------------------------------------------------------
REASONS = {
    "NOT_A_CROSS_REFERENCE": "vocabulary / document status literal (e.g. DRAFT_PENDING_OWNER, the 'PENDING <lane path>' "
                             "form definition, 'TBD or PENDING'); not a reference to another lane",
    "HISTORICAL_COPY": "status copied verbatim from a historical artifact; historical text is never rewritten",
    "UNMAPPED_DQ_ID": "the referenced item is keyed by a decision-quantity id with no unique UB-DQ <-> DQ-HI counterpart "
                      "(UNMAPPED - owner/A9-10); no id is invented",
    "ASSIGNMENT_NOT_DEFINED_BY_TARGET": "per-input stage / decision-quantity assignment: the target (A9-01 stage map, "
                                        "A9-04 chains) exists, but no target defines the per-input assignment; making "
                                        "it would be new content (A9-10 / owner)",
    "DEPENDS_ON_A9_06_TO_A9_10": "target lane A9-06..A9-10 is not in the base (mass BOM, H2 revisions, Xe ledger update, "
                                 "governance / M16 refresh)",
    "DEPENDS_ON_H2_REVISION": "target is an H2 deliverable revision (A9-07) or H-1 hardware, not in the base",
    "DEPENDS_ON_LOCK_OR_OWNER": "the referenced item is frozen only at LOCK-1 / LOCK-2 or needs an owner decision "
                                "(A9-01 defines the form only)",
    "DEPENDS_ON_HARDWARE_OR_EVIDENCE": "the value needs hardware or measurements (no lane target)",
    "TARGET_DOES_NOT_DEFINE": "the target deliverable is in the base but does not define the referenced item",
    "STATUS_FIELD": "a status field: re-evaluating a status against the now-available target is not a mechanical "
                    "reference update (A9-10 / owner); left unchanged",
    "VALUE_FIELD": "an item value / 'TBD - requires' field: filling or re-pointing a value is not a mechanical reference "
                   "update; left unchanged",
    "ITEM_STATUS_STATEMENT": "text restating that an item's value is PENDING; left unchanged with that item's status",
    "ASSESSMENT_FIELD": "an assessment (M16 blocking item, hard-incompatibility finding) made while the target was "
                        "missing; re-assessment is A9-10 work; left unchanged",
}

EXPLICIT_REMAINING = [
    # (deliverable, pointer regex, reason, note)
    ("A9-01", r"/items\[38\]/source", "TARGET_DOES_NOT_DEFINE",
     "ITM-39 re-mount series K and readings per cycle r: A9-04 defines no K / r item"),
    ("A9-02", r"/items\[21\]/source", "TARGET_DOES_NOT_DEFINE",
     "fixed vs auto-tuned matching network: the ICD defines the matching-network location (ICP-13) only"),
    ("A9-02", r"/h3_inputs\[2\]/basis", "TARGET_DOES_NOT_DEFINE",
     "matching network (fixed or auto-tuned): the ICD defines the location (ICP-13) only"),
    ("A9-02", r"/(items\[24\]/note|slots\[5\]/load_plane|owner_answers_applied\[18\]/how_applied)",
     "TARGET_DOES_NOT_DEFINE",
     "C1 keeper pulse-energy measurement record in the power chain: A9-04 records pulse energy only as a C1 supply "
     "capability note (UB-N-09), not in the P_bus chain"),
    ("A9-04", r"/items\[60\]/note", "TARGET_DOES_NOT_DEFINE",
     "C1 spot-mode minimum-flow search stopping criteria: A9-01 defines none"),
    ("A9-04", r"/measurement_chains\[2\]/equations\[4\]", "TARGET_DOES_NOT_DEFINE",
     "calorimetry method: ICD ICP-14 names calorimetry only as an independent cross-check"),
    ("A9-04", r"/measurement_chains\[3\]/equations\[2\]", "TARGET_DOES_NOT_DEFINE",
     "collector current sign convention: the ICD defines none"),
    ("A9-04", r"/measurement_chains\[3\]/equations\[4\]", "DEPENDS_ON_LOCK_OR_OWNER",
     "margin value: A9-01 margins are NOT SET until LOCK-2"),
    ("A9-04", r"/measurement_chains\[9\]/equations\[0\]", "TARGET_DOES_NOT_DEFINE",
     "mdot_prop basis for eta_u: A9-01 DQ-HI-ETAU does not define it"),
    ("A9-04", r"/(variance_groups/estimand|stop_rules/contrast_stop/applies_to)", "DEPENDS_ON_LOCK_OR_OWNER",
     "list of preregistered paired contrasts: frozen at LOCK-1 (A9-01 lists Pareto quantities, not the contrast list)"),
    ("A9-04", r"/owner_answers_applied\[(22|45)\]/how_applied", "ITEM_STATUS_STATEMENT",
     "restates the PENDING status of UB-F-12 / UB-P-01"),
    ("A9-05ev", r"/h3_h4_inputs/h4_measurement\[0\]", "DEPENDS_ON_LOCK_OR_OWNER",
     "Ar topology-check criterion: preregistered at LOCK-1 (A9-01 is a framework, not a lock)"),
    ("A9-05vi", r"/items\[13\]/definition", "TARGET_DOES_NOT_DEFINE",
     "declared reference potential of V_coll: not fixed by the ICD (ICP-22 V_d definition is itself PENDING A9-01)"),
    ("A9-05vi", r"/items\[26\]/how_obtained/chain", "DEPENDS_ON_H2_REVISION",
     "H-1 fringe field in the ICP volume: the ICD routes it to H2-1 (interface demand ID-13, A9-07)"),
    ("A9-05vi", r"/items\[40\]/how_obtained/chain", "DEPENDS_ON_LOCK_OR_OWNER",
     "Hall-ignition-with-ICP criterion: classified per the preregistration (A9-01 DQ-HI-IGN form; LOCK-1)"),
    ("A9-05vi", r"/items\[(4|5|6|9|10|18|22|24)\]/how_obtained/chain", "TARGET_DOES_NOT_DEFINE",
     "A9-04 has no measurement chain for this quantity (antenna current / resistance, absorbed power, coupling mode, "
     "RF pickup, beam-neutralization evidence, anode potential, IEDF)"),
    ("A9-05vi", r"/items\[8\]/definition", "DEPENDS_ON_HARDWARE_OR_EVIDENCE",
     "flight value of the RF chain efficiency (no lane target)"),
]


def classify(key: str, ptr: str, frag: str, full: str):
    for k, pat, reason, note in EXPLICIT_REMAINING:
        if k == key and re.fullmatch(pat, ptr):
            return reason, note
    last = ptr.rsplit("/", 1)[-1]
    if ptr == "/status" or ptr.endswith("/literals/pending_form") or "TBD or PENDING" in full:
        return "NOT_A_CROSS_REFERENCE", ""
    if "/copied_from/" in ptr:
        return "HISTORICAL_COPY", ""
    if (key == "A9-01" and last == "measurement_chain_uncertainty_owner") or (key == "A9-04" and last == "a9_01_dq_id"):
        return "UNMAPPED_DQ_ID", ""
    if key == "A9-05vi" and last in ("producing_stage", "decision_quantity_ids"):
        return "ASSIGNMENT_NOT_DEFINED_BY_TARGET", ""
    head = frag[:170]
    if re.search(r"A9-(06|07|08|09|10)|docs/budgets/", head):
        return "DEPENDS_ON_A9_06_TO_A9_10", ""
    if re.search(r"docs/hardware/h2/|H2-[0-9]|hardware not built", head):
        return "DEPENDS_ON_H2_REVISION", ""
    if last == "status" or re.fullmatch(r"status", last):
        return "STATUS_FIELD", ""
    if last in ("value", "tbd"):
        return "VALUE_FIELD", ""
    if last in ("finding", "blocking_item"):
        return "ASSESSMENT_FIELD", ""
    return None, ""


# ------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return sha256_bytes(f.read())


def git_show(rel: str) -> bytes:
    r = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show {BASE}:{rel} failed (base commit must be available): "
                           f"{r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def git_ls(rel: str):
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE, "--", rel], cwd=ROOT, capture_output=True,
                       text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-tree {BASE} {rel} failed: {r.stderr.strip()}")
    return [x for x in r.stdout.splitlines() if x]


def load_json(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def leaves(o, p=""):
    """Yield (pointer, value) for every leaf; containers are recorded with their type and length/keys."""
    if isinstance(o, dict):
        yield p, ("<dict>", tuple(o.keys()))
        for k, v in o.items():
            yield from leaves(v, p + "/" + k)
    elif isinstance(o, list):
        yield p, ("<list>", len(o))
        for i, v in enumerate(o):
            yield from leaves(v, p + f"[{i}]")
    else:
        yield p, o


def is_numeric_leaf(v) -> bool:
    return v is None or isinstance(v, (bool, int, float))


def get_ptr(doc, ptr):
    cur = doc
    for m in re.finditer(r"/([^/\[]+)|\[(\d+)\]", ptr):
        cur = cur[m.group(1)] if m.group(1) is not None else cur[int(m.group(2))]
    return cur


def target_defines(rel: str, token: str) -> bool:
    if token == "":
        return os.path.isfile(os.path.join(ROOT, rel))
    doc = load_json(rel)
    m = re.fullmatch(r"measurement_chains\[dq=(.+)\]", token)
    if m:
        return any(c.get("dq") == m.group(1) for c in doc.get("measurement_chains", []))
    m = re.fullmatch(r"slot (\S+)", token)
    if m:
        return any(s.get("slot") == m.group(1) for s in doc.get("slots", []))
    if isinstance(doc, dict) and token in doc:
        return True
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") == token:
                found.append(True)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(doc)
    return bool(found)


# ------------------------------------------------------------------------------------------------------------------
# core checks
# ------------------------------------------------------------------------------------------------------------------
def compare_deliverable(key: str, rel: str, errors: list, before=None, after=None):
    """Compare BASE vs current (or the given documents) leaf by leaf; append every violation to errors."""
    before = json.loads(git_show(rel).decode("utf-8")) if before is None else before
    after = load_json(rel) if after is None else after
    lb, la = dict(leaves(before)), dict(leaves(after))
    main_json = {d["key"]: d["json"] for d in DELIVERABLES}[key]
    decl = [r for r in RESOLUTIONS if r["deliverable"] == key and rel == main_json]
    used = {id(r): 0 for r in decl}
    added = sorted(p for p in la if p not in lb)
    removed = sorted(p for p in lb if p not in la)
    allowed_prefixes = [p for (f, p) in ALLOWED_ADDED_KEYS if f == rel]
    for p in added:
        if not any(p == a or p.startswith(a + "/") or p.startswith(a + "[") for a in allowed_prefixes):
            errors.append(f"{rel}: undeclared added path {p}")
        elif isinstance(la[p], (bool, int, float)):
            errors.append(f"{rel}: added path carries a number {p}")
    for p in removed:
        errors.append(f"{rel}: removed path {p}")
    n_num, n_str, changed = 0, 0, []
    for p, vb in lb.items():
        if p not in la:
            continue
        va = la[p]
        if isinstance(vb, tuple):  # container
            if isinstance(va, tuple) and vb[0] == "<list>" and va != vb:
                errors.append(f"{rel}{p}: list length changed {vb[1]} -> {va[1]}")
            elif isinstance(va, tuple) and vb[0] == "<dict>":
                extra = [k for k in va[1] if k not in vb[1]]
                if [k for k in va[1] if k in vb[1]] != list(vb[1]):
                    errors.append(f"{rel}{p}: key order / keys changed")
                for k in extra:
                    if not any((p + "/" + k) == a for a in allowed_prefixes):
                        errors.append(f"{rel}{p}: undeclared added key {k}")
            elif not isinstance(va, tuple):
                errors.append(f"{rel}{p}: container became a leaf")
            continue
        if is_numeric_leaf(vb) or is_numeric_leaf(va):
            n_num += 1
            if type(vb) is not type(va) or vb != va:
                errors.append(f"{rel}{p}: numeric leaf changed {vb!r} -> {va!r}")
            continue
        if not isinstance(vb, str) or not isinstance(va, str):
            errors.append(f"{rel}{p}: unexpected leaf type")
            continue
        n_str += 1
        expect = vb
        applied = []
        for r in decl:
            if re.fullmatch(r["pointer"], p):
                if r["old"] not in expect:
                    errors.append(f"{rel}{p}: declared old text not in base leaf: {r['old']!r}")
                    continue
                expect = expect.replace(r["old"], r["new"])
                used[id(r)] += 1
                applied.append(r)
        if key == "A9-04":
            renamed = apply_id_rename(expect)
            if renamed != expect:
                applied.append({"id_rename": True})
            expect = renamed
        if expect != va:
            errors.append(f"{rel}{p}: string leaf change not explained by the declared resolutions / id rename")
        elif va != vb:
            changed.append({"pointer": p, "before": vb, "after": va, "by": applied})
    for r in decl:
        if used[id(r)] == 0:
            errors.append(f"{rel}: declared resolution matched no leaf: {r['pointer']}")
    return before, after, {"numeric_leaves_compared": n_num, "string_leaves_compared": n_str,
                           "string_leaves_changed": len(changed), "added_paths": added,
                           "removed_paths": removed}, changed


def pending_occurrences(key: str, doc):
    out = []
    for p, v in leaves(doc):
        if isinstance(v, str) and "PENDING" in v:
            for m in re.finditer("PENDING", v):
                out.append((p, v[m.start():m.start() + 200], v))
    return out


LANE_DIR_TO_FILE = [
    ("docs/experiments/hall_icp/prereg_framework/", J01),
    ("docs/architecture_comparison/power_boundary_a9/", J02),
    ("abep_sim/bus_boundary_a9.py", M02),
    ("docs/interfaces/icp_neutralizer/", J03),
    ("docs/experiments/hall_icp/uncertainty_budget/", J04),
    ("docs/evidence/icp_neutralizer/", EV),
    ("docs/experiments/hall_icp/validation_inputs/", VI),
]


def targets_in_base(frag: str):
    head = frag.split(";")[0][:170]
    return sorted({f for d, f in LANE_DIR_TO_FILE if d in head})


# ------------------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------------------
def build():
    errors = []
    # authority pins
    pins = []
    for rel, sha, what in AUTHORITY_PINS:
        got = sha256_file(rel)
        if got != sha:
            errors.append(f"authority pin mismatch: {rel}")
        pins.append({"path": rel, "sha256": got, "what": what})

    # A9-01 decision quantities and the A9-04 mapping table
    a901 = load_json(J01)
    dq01 = {q["id"]: q for q in a901["decision_quantities"]}
    a904_base = json.loads(git_show(J04).decode("utf-8"))
    a904 = load_json(J04)
    mapping = a904.get("dq_id_mapping")
    if not mapping:
        raise RuntimeError("A9-04 deliverable has no dq_id_mapping (run the A9-04 builder first)")
    base_ub = [q["id"] for q in a904_base["decision_quantities"]]
    rows = mapping["rows"]
    if [r["ub_dq_id"] for r in rows] != base_ub:
        errors.append("mapping rows do not list every base UB-DQ id exactly once, in order")
    targets = [r["dq_hi_id"] for r in rows if r["dq_hi_id"]]
    if len(targets) != len(set(targets)):
        errors.append("a DQ-HI id is the target of two UB-DQ ids")
    after_ids = [q["id"] for q in a904["decision_quantities"]]
    for r, new_id in zip(rows, after_ids):
        if r["status"] == "MAPPED":
            if r["dq_hi_id"] not in dq01:
                errors.append(f"mapped target {r['dq_hi_id']} not an A9-01 decision quantity")
            if new_id != r["dq_hi_id"]:
                errors.append(f"A9-04 id {new_id} != mapping {r['dq_hi_id']}")
            if (r["ub_dq_id"], r["dq_hi_id"]) not in ID_RENAME:
                errors.append(f"mapping {r['ub_dq_id']} not in the declared id rename")
        else:
            if r["status"] != UNMAPPED or r["dq_hi_id"] is not None or new_id != r["ub_dq_id"]:
                errors.append(f"unmapped row {r['ub_dq_id']} inconsistent")
        for c in r["a9_01_consumers_not_counterparts"]:
            if c.split()[0] not in dq01:
                errors.append(f"consumer {c} not an A9-01 id")
    if sorted(ID_RENAME) != sorted((r["ub_dq_id"], r["dq_hi_id"]) for r in rows if r["status"] == "MAPPED"):
        errors.append("declared id rename differs from the mapped rows")
    mapping_rows = []
    for r in rows:
        q = dq01.get(r["dq_hi_id"]) if r["dq_hi_id"] else None
        mapping_rows.append(dict(r, a9_01_role=(q["role"] if q else None), a9_01_units=(q["units"] if q else None)))

    # mapped ids must not survive anywhere in the A9 deliverables (outside the mapping tables)
    for key, rel in COMPARED_JSON:
        doc = load_json(rel)
        if rel == J04:
            doc = {k: v for k, v in doc.items() if k != "dq_id_mapping"}
        txt = json.dumps(doc, ensure_ascii=False)
        for old, _ in ID_RENAME:
            if re.search(re.escape(old) + r"(?![A-Za-z0-9])", txt):
                errors.append(f"{rel}: mapped provisional id {old} still present")

    # declared resolutions: targets must exist and define the item
    for r in RESOLUTIONS:
        for f, toks in r["targets"]:
            for t in toks:
                if not target_defines(f, t):
                    errors.append(f"resolution target {f} does not define {t!r} ({r['deliverable']} {r['pointer']})")

    # leaf-by-leaf comparison
    no_change, resolved = [], []
    rename_leaves = 0
    for key, rel in COMPARED_JSON:
        _, after, stats, changed = compare_deliverable(key, rel, errors)
        no_change.append(dict({"deliverable": key, "path": rel}, **stats,
                              numeric_leaves_equal=not any(e.startswith(rel) and "numeric leaf" in e for e in errors)))
        for c in changed:
            refs = [b for b in c["by"] if "id_rename" not in b]
            if any("id_rename" in b for b in c["by"]):
                rename_leaves += 1
            for b in refs:
                resolved.append({"deliverable": key, "file": rel, "pointer": c["pointer"], "old": b["old"],
                                 "new": b["new"],
                                 "targets": [{"path": f, "items": [t for t in toks if t]} for f, toks in b["targets"]]})

    # remaining PENDING occurrences
    remaining, unclassified = [], []
    for key, rel in COMPARED_JSON:
        for p, frag, full in pending_occurrences(key, load_json(rel)):
            reason, note = classify(key, p, frag, full)
            if reason is None:
                unclassified.append(f"{rel}{p}: {frag[:80]}")
                continue
            remaining.append({"deliverable": key, "file": rel, "pointer": p, "text": frag[:160], "reason": reason,
                              "note": note, "target_now_in_base": targets_in_base(frag)})
    for u in unclassified:
        errors.append("unclassified remaining PENDING: " + u)

    # pinned-input links between A9 deliverables
    pin_updates = []
    for link in PINNED_INPUT_LINKS:
        pinned = get_ptr(load_json(link["pinned_by"]), link["field"])
        now = sha256_file(link["pinned_file"])
        base_now = sha256_bytes(git_show(link["pinned_file"]))
        if pinned != now:
            errors.append(f"pinned input stale: {link['pinned_by']}{link['field']} != sha256({link['pinned_file']})")
        pin_updates.append(dict(link, sha256=now, changed_by_this_lane=(now != base_now), updated=(now != base_now)))

    # historical / immutable artifacts unchanged
    historical = []
    for root in HISTORICAL_ROOTS:
        for rel in git_ls(root):
            b = sha256_bytes(git_show(rel))
            n = sha256_file(rel) if os.path.isfile(os.path.join(ROOT, rel)) else None
            if b != n:
                errors.append(f"historical / immutable file changed: {rel}")
            historical.append({"path": rel, "sha256": n, "unchanged_since_base": b == n})

    # post-integration pins of every A9 deliverable file (targets of the resolved references)
    post = []
    for d in DELIVERABLES:
        for rel in [d["json"], d["md"], d["builder"]] + d.get("extra", []):
            post.append({"deliverable": d["key"], "path": rel, "sha256": sha256_file(rel),
                         "changed_by_this_lane": sha256_file(rel) != sha256_bytes(git_show(rel))})

    counts = {
        "ub_dq_ids": len(rows),
        "mapped": sum(1 for r in rows if r["status"] == "MAPPED"),
        "unmapped": sum(1 for r in rows if r["status"] != "MAPPED"),
        "resolved_references": len(resolved),
        "leaves_changed_by_id_rename": rename_leaves,
        "remaining_pending_occurrences": len(remaining),
        "remaining_by_reason": {k: sum(1 for x in remaining if x["reason"] == k) for k in REASONS},
        "remaining_by_deliverable": {k: sum(1 for x in remaining if x["deliverable"] == k)
                                     for k in [d["key"] for d in DELIVERABLES]},
        "numeric_leaves_compared": sum(x["numeric_leaves_compared"] for x in no_change),
        "string_leaves_changed": sum(x["string_leaves_changed"] for x in no_change),
        "historical_files_checked": len(historical),
    }
    doc = assemble(pins, mapping, mapping_rows, resolved, remaining, no_change, pin_updates, historical, post, counts,
                   errors)
    return doc, errors


def assemble(pins, mapping, mapping_rows, resolved, remaining, no_change, pin_updates, historical, post, counts,
             errors):
    unmapped_ids = [r["ub_dq_id"] for r in mapping_rows if r["status"] != "MAPPED"]
    rem = counts["remaining_by_reason"]
    items = [
        {"id": "INT-01", "name": "UB-DQ -> DQ-HI mapping rule", "value": mapping["rule"], "units": "-",
         "basis": "task scope (1); A9-01 and A9-04 definitions (name, units, configurations, measurement chain)",
         "source": J04 + " dq_id_mapping; " + J01 + " decision_quantities", "evidence_class": "inferred",
         "status": "APPLIED (mechanical; owner / A9-10 may revise)", "freeze_point": "NOW"},
        {"id": "INT-02", "name": "UB-DQ ids mapped to a unique DQ-HI id", "value": counts["mapped"], "units": "count",
         "basis": "INT-01", "source": "computed by this builder from " + J04, "evidence_class": "inferred",
         "status": "APPLIED", "freeze_point": "NOW"},
        {"id": "INT-03", "name": "UB-DQ ids kept and marked " + UNMAPPED, "value": counts["unmapped"], "units": "count",
         "basis": "INT-01 (no counterpart or several counterparts; no id invented)",
         "source": "computed by this builder from " + J04, "evidence_class": "inferred",
         "status": "OPEN - owner/A9-10", "freeze_point": "after-evidence"},
        {"id": "INT-04", "name": "resolved cross-references (leaf-level)", "value": counts["resolved_references"],
         "units": "count", "basis": "task scope (2)", "source": "computed by this builder (declared RESOLUTIONS "
         "verified leaf by leaf against " + BASE + ")", "evidence_class": "inferred", "status": "APPLIED",
         "freeze_point": "NOW"},
        {"id": "INT-05", "name": "remaining PENDING occurrences (with reason codes)",
         "value": counts["remaining_pending_occurrences"], "units": "count", "basis": "task scope (2)",
         "source": "computed by this builder", "evidence_class": "inferred", "status": "OPEN (listed)",
         "freeze_point": "after-evidence"},
        {"id": "INT-06", "name": "numeric / bool / null leaves compared before/after (all equal)",
         "value": counts["numeric_leaves_compared"], "units": "count",
         "basis": "strict prohibition: no numeric physics value, threshold, gate or allocation changed",
         "source": "computed by this builder; independently re-checked by " + TEST_REL,
         "evidence_class": "inferred", "status": "VERIFIED" if not errors else "FAILED", "freeze_point": "NOW"},
        {"id": "INT-07", "name": "sha256 policy for resolved references", "value":
            "cite path + item id in the deliverables; pin the post-integration sha256 of every target here only "
            "(the five A9 deliverables reference each other, e.g. A9-01 <-> A9-04, so an in-file sha256 has no "
            "fixed point)", "units": "-", "basis": "task scope (2)-(3); A9.1 execution step_1 ('paths/hashes')",
         "source": "this lane", "evidence_class": "inferred", "status": "PROPOSED (owner call, OQ-INT-02)",
         "freeze_point": "NOW"},
        {"id": "INT-08", "name": "pinned-input sha256 updates needed", "value":
            sum(1 for x in pin_updates if x["updated"]), "units": "count", "basis": "task scope (3)",
         "source": "computed by this builder", "evidence_class": "inferred", "status": "VERIFIED",
         "freeze_point": "NOW"},
        {"id": "INT-09", "name": "historical / immutable files byte-identical to the base",
         "value": sum(1 for x in historical if x["unchanged_since_base"]), "units": "count",
         "basis": "A9 supersession rule (historical artifacts preserved byte-for-byte)",
         "source": "computed by this builder", "evidence_class": "inferred", "status": "VERIFIED",
         "freeze_point": "NOW"},
    ]
    interface_demands = [
        {"id": "IF-INT-01", "direction": "from A9-01 to this lane", "counterpart": J01,
         "quantity": "final decision-quantity ids DQ-HI-* (name, units, role, measurement chain)", "units": "-",
         "status": "CONSUMED"},
        {"id": "IF-INT-02", "direction": "from A9-02..A9-05 to this lane",
         "counterpart": ", ".join([M02, J02, J03, J04, EV, VI]),
         "quantity": "items / slots / chains that resolve cross-references", "units": "-", "status": "CONSUMED"},
        {"id": "IF-INT-03", "direction": "from this lane to A9-04", "counterpart": J04,
         "quantity": "id rename (" + ", ".join(f"{a} -> {b}" for a, b in ID_RENAME) + ") and dq_id_mapping table",
         "units": "-", "status": "SUPPLIED (this lane)"},
        {"id": "IF-INT-04", "direction": "from this lane to A9-10", "counterpart": "A9-10 governance (no path yet)",
         "quantity": "resolve the UNMAPPED UB-DQ ids " + ", ".join(unmapped_ids), "units": "-",
         "status": "OPEN - owner/A9-10"},
        {"id": "IF-INT-05", "direction": "from this lane to A9-10", "counterpart": "A9-10 governance (no path yet)",
         "quantity": "re-evaluate status / value / assessment fields whose target is now in the base",
         "units": "count", "value": rem["STATUS_FIELD"] + rem["VALUE_FIELD"] + rem["ASSESSMENT_FIELD"]
         + rem["ITEM_STATUS_STATEMENT"], "status": "OPEN"},
        {"id": "IF-INT-06", "direction": "from this lane to A9-10", "counterpart": "A9-10 governance (no path yet)",
         "quantity": "per-input producing stage and decision-quantity assignment in the A9-05 validation inputs",
         "units": "count", "value": rem["ASSIGNMENT_NOT_DEFINED_BY_TARGET"], "status": "OPEN"},
        {"id": "IF-INT-07", "direction": "from this lane to A9-06 / A9-07 / A9-08 / A9-10",
         "counterpart": "A9-06 mass BOM, A9-07 H2 revisions, A9-08 Xe ledger update, A9-10 governance",
         "quantity": "references that stay PENDING until those lanes exist", "units": "count",
         "value": rem["DEPENDS_ON_A9_06_TO_A9_10"] + rem["DEPENDS_ON_H2_REVISION"], "status": "OPEN"},
        {"id": "IF-INT-08", "direction": "from this lane to every later A9 lane", "counterpart": "A9-06..A9-10",
         "quantity": "post-integration sha256 of every A9 deliverable file (post_integration_pins); a later change "
                     "to a pinned file must rebuild this record", "units": "-", "status": "SUPPLIED (this lane)"},
        {"id": "IF-INT-09", "direction": "H2 / H-1 items", "counterpart": "docs/hardware/h2/ (H2-1..H2-7); H-1",
         "quantity": "none: no H2 deliverable and no H-1 item is read for values or changed by this lane",
         "units": "-", "status": "NOT APPLICABLE"},
    ]
    owner_answers = [
        {"row": 18, "how_applied": "no effect-size / decision margin set or changed; every numeric leaf equal "
                                   "before/after (no_change_statement)"},
        {"row": 19, "how_applied": "no block count n set or changed (numeric-leaf check)"},
        {"row": 30, "how_applied": "no seed or seed rule changed (string-diff check: only declared references)"},
        {"row": 37, "how_applied": "NET_BENEFIT form untouched; no weighted scalar introduced; no winner declared"},
        {"row": 38, "how_applied": "OPEN stays a status (A9-04 not_tested vocabulary pointer resolved to the A9-01 "
                                   "decision_topology; vocabulary unchanged)"},
    ]
    open_q = [
        {"id": "OQ-INT-01", "question": "How should the UNMAPPED A9-04 ids (" + ", ".join(unmapped_ids) + ") relate "
         "to the A9-01 DQ-HI ids?", "proposed_answer": "keep them as measurement-chain ids (they are measured "
         "quantities feeding several or no decision quantities) and add in A9-10 an explicit chain -> DQ-HI consumer "
         "table; owner call", "status": "OPEN - owner/A9-10"},
        {"id": "OQ-INT-02", "question": "Should the A9 deliverables pin each other's sha256 in-file?",
         "proposed_answer": "no: they reference each other (no fixed point); pin post-integration hashes only in "
                            "this integration record and rebuild it after any later change; owner call",
         "status": "OPEN"},
        {"id": "OQ-INT-03", "question": "Status / value / assessment fields that still read 'PENDING <lane>' although "
         "the lane is now in the base: re-evaluate in A9-10?", "proposed_answer": "yes, in A9-10 with the consolidated "
         "owner-question state (not a mechanical change)", "status": "OPEN"},
        {"id": "OQ-INT-04", "question": "A9-03 published-analog annex says it 'must be reconciled with A9-05 when it "
         "merges'; the pointer is resolved here, the reconciliation is not", "proposed_answer": "A9-10 reconciles the "
         "annex against " + EV + " (content, not mechanical)", "status": "OPEN"},
    ]
    doc = {
        "schema": "a9_core_integration_v1",
        "id": "a9_core_integration_v1",
        "lane": "fo_a9_int_core_integration",
        "trigger": "T_A9_INT_CORE_INTEGRATION",
        "owner_decision": "A9 (+ A9.1 execution step_1_integration_repair)",
        "status": "MECHANICAL_INTEGRATION_NOT_A_SCIENTIFIC_RESULT",
        "base_commit": BASE,
        "generated_by": SCRIPT_REL + " (--check reproduces JSON and MD exactly and re-runs every check)",
        "companion_document": MD_REL,
        "test": TEST_REL,
        "configurations": list(CONFIGURATIONS),
        "what_this_is_not": [
            "not a new scientific result, not a performance prediction, not a winner declaration",
            "not an application of the A9.1 follow-up decisions (HIQ-/UBQ-/ICPQ-; applied later by A9-06..A9-10)",
            "no numeric physics value, threshold, gate, allocation, requirement meaning, evidence class or owner-answer "
            "interpretation changed; no new item added to any deliverable",
        ],
        "authority_pins": pins,
        "governance_files_not_pinned": GOVERNANCE_NOT_PINNED,
        "dq_id_mapping": {"rule": mapping["rule"], "source": J04 + " /dq_id_mapping (mirrored here)",
                          "a9_01_source": J01 + " /decision_quantities", "rows": mapping_rows},
        "resolved_references": resolved,
        "remaining_references": remaining,
        "reason_codes": REASONS,
        "counts": counts,
        "no_change_statement": {
            "machine_checked": True,
            "statement": "every numeric leaf (int, float, bool, null) of every compared A9 JSON deliverable is equal "
                         "at " + BASE + " (git show) and after this lane; every changed string leaf equals the base "
                         "leaf with the declared reference resolutions (resolved_references) and, in A9-04 only, the "
                         "declared id rename applied; no key or list element removed; the only added key is A9-04 "
                         "/dq_id_mapping",
            "allowed_change_fields": ["A9-04 decision-quantity ids (/decision_quantities[*]/id) and their uses "
                                      "(/items[*]/dq, /measurement_chains[*]/dq, id tokens in text) per id_rename",
                                      "reference strings listed in resolved_references (pointer, old, new)",
                                      "added key " + J04 + " /dq_id_mapping (strings and nulls only; no number)"],
            "id_rename": [{"from": a, "to": b} for a, b in ID_RENAME],
            "per_deliverable": no_change,
            "errors": errors,
        },
        "pinned_input_updates": {"links": pin_updates,
                                 "note": "no pinned file changed in this lane (A9-05 evidence JSON and pixel record "
                                         "untouched), so no builder pin needed updating; verified"},
        "post_integration_pins": post,
        "historical_unchanged": historical,
        "items": items,
        "interface_demands": interface_demands,
        "owner_answers_applied": owner_answers,
        "a9_1_execution_step_1": {
            "path": "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "applied": ["rename A9-04 decision quantities to A9-01 ids (mapped ids only; UNMAPPED kept)",
                        "replace resolved PENDING A9-01..05 cross-references with paths (hashes in this record)",
                        "no physics values changed (machine-checked)", "no thresholds changed (machine-checked)"],
            "not_run_here": "full suite + golden + integrity (run by the orchestrator after merge; this lane runs only "
                            "the A9 builders --check and the A9 test files, CPU rule)",
        },
        "open_owner_questions": open_q,
        "historical_reuse": {
            "reused": [],
            "not_reused": ["A5 Phase-1 prereg framework, pre-ionizer module ICD, LOCK-1 drafts, arch_boundary.py "
                           "(bus_power_boundary_v1), A8 / RF||Hall v2: nothing reused; byte-identity verified "
                           "(historical_unchanged)"],
        },
        "m16_impact": {"rows_touched": [], "note": "no M16 row or m16_impact entry of any A9 deliverable changed "
                                                  "(no declared resolution under /m16_impact); M16 refresh is A9-10"},
        "h3_h4_inputs": {"new": [], "reference_only_changes": [
            x["deliverable"] + " " + x["pointer"] for x in resolved if "h3" in x["pointer"] or "h4" in x["pointer"]]},
        "compliance": [
            "owner-given values untouched; no number created (counts are computed by this builder)",
            "immutable inputs pinned by sha256; mutable governance never pinned",
            "no screening candidate or unadmitted Hall closure used; no winner declared",
            "no source contacted; no network used",
        ],
    }
    return doc


# ------------------------------------------------------------------------------------------------------------------
# markdown
# ------------------------------------------------------------------------------------------------------------------
def _c(v):
    if v is None:
        return "-"
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_md(d) -> str:
    L = []
    a = L.append
    a("# A9 core integration (A9_INT): id mapping, cross-reference resolution, no-change check")
    a("")
    a(f"<!-- GENERATED by {SCRIPT_REL} from a9_core_integration_v1.json; do not edit by hand -->")
    a("")
    a(f"Status: **{d['status']}**. Lane `{d['lane']}` (trigger `{d['trigger']}`), base commit `{d['base_commit']}`. "
      "Mechanical integration of A9-01..A9-05; not a new scientific result.")
    a("")
    for x in d["what_this_is_not"]:
        a(f"* {x}")
    a("")
    a("## Authority pins (immutable)")
    a("| path | sha256 | what |")
    a("|---|---|---|")
    for p in d["authority_pins"]:
        a(f"| `{p['path']}` | `{p['sha256']}` | {_c(p['what'])} |")
    a("")
    a("Not pinned (mutable governance): " + ", ".join(f"`{g}`" for g in d["governance_files_not_pinned"]))
    a("")
    c = d["counts"]
    a("## Summary")
    a(f"* UB-DQ ids: {c['ub_dq_ids']}; mapped: {c['mapped']}; kept as `{UNMAPPED}`: {c['unmapped']}.")
    a(f"* Resolved cross-references: {c['resolved_references']}; leaves changed by the id rename: "
      f"{c['leaves_changed_by_id_rename']}; remaining PENDING occurrences: {c['remaining_pending_occurrences']}.")
    a(f"* Numeric / bool / null leaves compared (all equal): {c['numeric_leaves_compared']}; string leaves changed: "
      f"{c['string_leaves_changed']} (all explained); historical files verified unchanged: "
      f"{c['historical_files_checked']}.")
    a("")
    m = d["dq_id_mapping"]
    a("## Decision-quantity id mapping UB-DQ-* -> DQ-HI-*")
    a("")
    a(f"Rule: {m['rule']}. Source: `{m['source']}`; A9-01: `{m['a9_01_source']}`.")
    a("")
    a("| UB-DQ id | DQ-HI id | status | A9-01 role | A9-04 definition | A9-01 definition | basis | A9-01 consumers "
      "(not counterparts) |")
    a("|---|---|---|---|---|---|---|---|")
    for r in m["rows"]:
        a(f"| {r['ub_dq_id']} | {r['dq_hi_id'] or '-'} | {r['status']} | {r['a9_01_role'] or '-'} | "
          f"{_c(r['ub_definition'])} | {_c(r['a9_01_definition'])} | {_c(r['basis'])} | "
          f"{_c(', '.join(r['a9_01_consumers_not_counterparts']) or '-')} |")
    a("")
    ns = d["no_change_statement"]
    a("## No-change statement (machine-checked)")
    a("")
    a(ns["statement"] + ".")
    a("")
    a("| deliverable | file | numeric leaves (equal) | string leaves | string leaves changed | added paths |")
    a("|---|---|---|---|---|---|")
    for x in ns["per_deliverable"]:
        a(f"| {x['deliverable']} | `{x['path']}` | {x['numeric_leaves_compared']} "
          f"({'yes' if x['numeric_leaves_equal'] else 'NO'}) | {x['string_leaves_compared']} | "
          f"{x['string_leaves_changed']} | {len(x['added_paths'])} |")
    a("")
    a("Allowed change fields: " + "; ".join(ns["allowed_change_fields"]) + ".")
    a("")
    a("Errors: " + ("none" if not ns["errors"] else "; ".join(ns["errors"])))
    a("")
    a("## Resolved cross-references")
    a("| deliverable | pointer | old | new | target items |")
    a("|---|---|---|---|---|")
    for x in d["resolved_references"]:
        tg = "; ".join(f"`{t['path']}` {', '.join(t['items'])}".strip() for t in x["targets"])
        a(f"| {x['deliverable']} | `{x['pointer']}` | {_c(x['old'])} | {_c(x['new'])} | {tg} |")
    a("")
    a("## Remaining PENDING references")
    a("| reason | meaning | count |")
    a("|---|---|---|")
    for k, v in d["reason_codes"].items():
        a(f"| {k} | {_c(v)} | {c['remaining_by_reason'][k]} |")
    a("")
    a("| deliverable | pointer | reason | note | target now in base | text |")
    a("|---|---|---|---|---|---|")
    for x in d["remaining_references"]:
        a(f"| {x['deliverable']} | `{x['pointer']}` | {x['reason']} | {_c(x['note']) if x['note'] else '-'} | "
          f"{_c(', '.join(x['target_now_in_base']) or '-')} | {_c(x['text'])} |")
    a("")
    a("## Pinned-input updates")
    a(d["pinned_input_updates"]["note"] + ".")
    a("")
    a("| pinned file | pinned by | field | sha256 | changed by this lane |")
    a("|---|---|---|---|---|")
    for x in d["pinned_input_updates"]["links"]:
        a(f"| `{x['pinned_file']}` | `{x['pinned_by']}` | `{x['field']}` | `{x['sha256']}` | "
          f"{x['changed_by_this_lane']} |")
    a("")
    a("## Post-integration pins (targets of the resolved references)")
    a("| deliverable | path | sha256 | changed by this lane |")
    a("|---|---|---|---|")
    for x in d["post_integration_pins"]:
        a(f"| {x['deliverable']} | `{x['path']}` | `{x['sha256']}` | {x['changed_by_this_lane']} |")
    a("")
    a("## (a) Items")
    a("| id | name | value | units | basis | source | evidence class | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|---|")
    for x in d["items"]:
        a(f"| {x['id']} | {_c(x['name'])} | {_c(x['value'])} | {x['units']} | {_c(x['basis'])} | {_c(x['source'])} | "
          f"{x['evidence_class']} | {_c(x['status'])} | {x['freeze_point']} |")
    a("")
    a("## (b) Interface demands")
    a("| id | direction | counterpart | quantity | units | value | status |")
    a("|---|---|---|---|---|---|---|")
    for x in d["interface_demands"]:
        a(f"| {x['id']} | {x['direction']} | {_c(x['counterpart'])} | {_c(x['quantity'])} | {x['units']} | "
          f"{_c(x.get('value'))} | {x['status']} |")
    a("")
    a("## (c) Owner answers applied")
    for x in d["owner_answers_applied"]:
        a(f"* row {x['row']}: {x['how_applied']}")
    s1 = d["a9_1_execution_step_1"]
    a(f"* A9.1 (`{s1['path']}`) execution step_1: " + "; ".join(s1["applied"]) + f". Not run here: {s1['not_run_here']}.")
    a("")
    a("## (d) Open owner questions (new)")
    for x in d["open_owner_questions"]:
        a(f"* **{x['id']}** ({x['status']}): {x['question']} Proposed: {x['proposed_answer']}.")
    a("")
    a("## (e) Historical reuse")
    a("Reused: none. " + " ".join(d["historical_reuse"]["not_reused"]) + ".")
    a("")
    a("| path | sha256 | unchanged since base |")
    a("|---|---|---|")
    for x in d["historical_unchanged"]:
        a(f"| `{x['path']}` | `{x['sha256']}` | {x['unchanged_since_base']} |")
    a("")
    a("## (f) M16 impact")
    a(d["m16_impact"]["note"] + ".")
    a("")
    a("## (g) H3 / H4 inputs")
    a("No new H3/H4 input. Reference-only changes: " + (", ".join(f"`{x}`" for x in
                                                                   d["h3_h4_inputs"]["reference_only_changes"]) or "none") + ".")
    a("")
    a("## Compliance")
    for x in d["compliance"]:
        a(f"* {x}")
    a("")
    return "\n".join(L)


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are reproduced exactly and all checks pass")
    args = ap.parse_args(argv)
    doc, errors = build()
    js, md = dumps(doc), render_md(doc)
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
    jp, mp = os.path.join(ROOT, JSON_REL), os.path.join(ROOT, MD_REL)
    if args.check:
        ok = not errors
        for p, want in ((jp, js), (mp, md)):
            try:
                with open(p, encoding="utf-8") as f:
                    got = f.read()
            except FileNotFoundError:
                got = None
            if got != want:
                print(f"MISMATCH: {os.path.relpath(p, ROOT)}", file=sys.stderr)
                ok = False
        print("OK" if ok else "FAILED")
        return 0 if ok else 1
    if errors:
        print("not written: checks failed", file=sys.stderr)
        return 1
    with open(jp, "w", encoding="utf-8") as f:
        f.write(js)
    with open(mp, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {JSON_REL} and {MD_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
