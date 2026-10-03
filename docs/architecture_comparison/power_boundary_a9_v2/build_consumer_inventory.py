#!/usr/bin/env python3
"""A9.22 G8 stage 1: the inventory of every consumer of bus_power_boundary_a9_v1, a deterministic scan plus a declared
classification.

Scope: every tracked file that imports, reads, sha-pins or cites the v1 boundary family. The family is
``abep_sim/bus_boundary_a9.py``, ``docs/architecture_comparison/power_boundary_a9/`` (document, builder, Markdown) and
``schemas/interfaces/bus_power_boundary_a9_v1.json``. Matches are on a family path or name, on a current or historical
sha256 of a family file (16-hex prefix), on a pin key that a consumer defines for the family and uses elsewhere
(``KEY_USERS``), or on an import of a module that imports v1 (``TRANSITIVE``). A file that matches but has no
classification stops the build, and so does a classified file that no longer matches. Nothing is re-pointed here
(stage 1).

The scan reads the tree of the fixed pre-migration commit ``BASE_COMMIT`` from git (``git ls-tree`` / ``git cat-file``),
not the working tree, so the inventory stays reproducible after the stage-2 migration re-points the consumers. Stage 2
re-ran it at the integration head 5b32edc before changing anything (line numbers had moved since 9eb302c); the
migration itself is recorded in ``STAGE2_MIGRATION.json`` (``build_stage2_migration.py``).

Each consumer gets one status:
  IMMUTABLE_HISTORY         stays on v1, never edited
  LIVE_REPOINT              moves to v2 in the single controlled stage-2 migration
  LIVE_RETAIN_V1_REFERENCE  live file whose v1 reference stays correct (origin citation, bid-freeze anchor, listing)
  TRANSITIVE_LIVE           no direct reference; follows a LIVE_REPOINT module it imports (re-run its tests)
  SELF_V1                   the v1 family itself (immutable)
  GOVERNANCE_RECORD         decisions / HISTORY / orchestration records (never re-pointed; HISTORY gets an entry)

    python docs/architecture_comparison/power_boundary_a9_v2/build_consumer_inventory.py            # (re)write
    python docs/architecture_comparison/power_boundary_a9_v2/build_consumer_inventory.py --check    # exit 1 on drift
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
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_JSON = os.path.join(HERE, "CONSUMER_INVENTORY.json")
OUT_MD = os.path.join(HERE, "CONSUMER_INVENTORY.md")
SCRIPT_REL = "docs/architecture_comparison/power_boundary_a9_v2/build_consumer_inventory.py"
# pre-migration integration head (bus boundary v2 stage 1 + AG-15 closure + F1 core view); stage 1 ran at 9eb302c
BASE_COMMIT = "5b32edcc8e9124cd8bd12aba7d91204c1470aa3f"
STAGE1_COMMIT = "9eb302c06241c8e8a369334a6bdc5bc559227143"
DATE = "2026-10-03"

V1_JSON = "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json"
V1_MOD = "abep_sim/bus_boundary_a9.py"
V1_SCHEMA = "schemas/interfaces/bus_power_boundary_a9_v1.json"
V1_BUILDER = "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py"
V1_MD = "docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md"
# sha256 (16-hex prefixes) of every committed version of the five family files; the first entry of each is current
FAMILY_SHAS = {
    V1_MOD: ("7b23dbd23d39bd57", "78014f51bec31c8c", "08d8d6e730aabb30", "239f19192d0691c8", "5bb3a2aaf1b3aad0",
             "0e373280a13accec"),
    V1_JSON: ("9f6e074cc2cdd1e2", "f855cecaa1707bfe", "3178d462d230656a", "a16496b06df5876e", "dd888719d36e5de2",
              "7ca8ed23652c4f3a", "1a3c8d29404d4648", "7c13fa1d37edc96d", "cb348cf13211788d"),
    V1_BUILDER: ("d5c8130ff0f7bea6", "901ceea5ae68e852", "92a269f660828e0c", "45213a9eec97c1c3", "90e7c9af89164f93",
                 "6a103dedeb2d6b22", "a9e0b43849e2fc4c"),
    V1_MD: ("bc2c761720ad39a3", "4780430719195b24", "bf97b53c2908a338", "4806cd454344c8cf", "c805c4bf2b94b1cd",
            "3c0d0b4bbb118441", "673a9c4bb4de1f17", "ed85493a86e3364d", "5faa91672059856d"),
    V1_SCHEMA: ("64238d1526d8ce6b", "97458dac4cce7499", "788b879477c744cd", "eec5240a282d0a44"),
}
SHA_TO_TARGET = {p: f for f, ps in FAMILY_SHAS.items() for p in ps}
NAME_RX = re.compile(r"(?:bus_boundary_a9|bus_power_boundary_a9|power_boundary_a9|BUS_POWER_BOUNDARY_A9)(?!_v2|_V2)")
SHA_RX = re.compile("|".join(SHA_TO_TARGET))
IMPORT_RX = re.compile(r"^\s*(from\s+[\w.]+\s+import\s+bus_boundary_a9\b(?!_v2)|import\s+abep_sim\.bus_boundary_a9\b(?!_v2))|"
                       r"import_module\(\s*[\"']abep_sim\.bus_boundary_a9[\"']\s*\)|"
                       r"spec_from_file_location\([^)]*build_bus_power_boundary_a9")
# v2 lane outputs (this directory, the v2 module/schema/test) are not consumers of v1
OWN = ("docs/architecture_comparison/power_boundary_a9_v2/", "abep_sim/bus_boundary_a9_v2.py",
       "schemas/interfaces/bus_power_boundary_a9_v2.json", "tests/test_bus_boundary_a9_v2.py")
# files that use a pin key defined for the v1 document in another file (key -> definer)
KEY_USERS = {
    "docs/requirements/rvm_a9/rvm_a9_rows.py": ("BUS", "docs/requirements/rvm_a9/build_rvm_a9.py REFS"),
    "docs/experiments/hall_icp/integration/m16_v4/m16_v4_rows.py":
        ("BUS", "docs/experiments/hall_icp/integration/m16_v4/build_subsystem_maturity_v4.py INPUTS"),
    "docs/experiments/hall_icp/integration/m16_v5/build_subsystem_maturity_v5.py":
        ("BUS", "docs/experiments/hall_icp/integration/m16_v4/build_subsystem_maturity_v4.py INPUTS (reused as B4)"),
}
KEY_IN_SELF = {  # a file whose own pin key for the v1 document is used on other lines (regex of the use)
    "docs/architecture/freeze_candidate/build_freeze_candidate.py": r"[\"']BUS[\"']",
    "docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py": r"[\"']BUS[\"']",
    "docs/procurement/rfq_a9/build_rfq_a9.py": r"[\"']BUS[\"']",
    "docs/bid/package/compliance_data.py": r"\bBPB\b",
}
TRANSITIVE_RX = re.compile(r"(from\s+\S*design\s+import\s+architecture_optimizer|from\s+\.\s+import\s+architecture_optimizer)")
TRANSITIVE_VIA = "abep_sim/design/architecture_optimizer.py (imports abep_sim.bus_boundary_a9 as bb)"
# code that loads a family file at build/test time (a path literal on such a line is a 'read')
READERS = {
    "docs/architecture/freeze_candidate/build_freeze_candidate.py", "docs/bid/package/compliance_data.py",
    "docs/budgets/mass_a9/build_mass_a9.py", "docs/budgets/mass_power_a9_v2/build_mass_power_a9_v2.py",
    "docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py", "docs/budgets/owner_decisions/build_owner_questions_state_v2.py",
    "docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py", "docs/budgets/xe_ledger_a9/build_xe_ledger_a9.py",
    "docs/experiments/hall_icp/integration/a9_10_overlay.py", "docs/experiments/hall_icp/integration/build_a9_10_reconciliation.py",
    "docs/experiments/hall_icp/integration/build_a9_core_integration.py",
    "docs/experiments/hall_icp/integration/m16_v4/build_subsystem_maturity_v4.py",
    "docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py",
    "docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py",
    "docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py", "docs/procurement/rfq_a9/build_rfq_a9.py",
    "docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py", "docs/requirements/rvm_a9/build_rvm_a9.py",
    "docs/experiments/hall_icp/prereg_framework/build_hall_icp_prereg_framework.py",
    "tests/test_a9_10_reconciliation.py", "tests/test_a9_core_integration.py", "tests/test_bus_boundary_a9.py",
    "tests/test_h2_a9_revisions.py", "tests/test_mass_power_a9_v2.py", "tests/test_mass_power_a9_v3.py",
    "tests/test_owner_questions_state_v2.py", "tests/test_single_flight_configuration.py",
    "tests/test_hall_icp_prereg_framework.py",
}
READ_TOKENS = ("bus_power_boundary_a9_v1.json", "abep_sim/bus_boundary_a9.py", "build_bus_power_boundary_a9.py",
               "BUS_POWER_BOUNDARY_A9.md")

# ------------------------------------------------------------------------------------------------ classification
# (path or directory prefix, family, status, evidence for the status, what changes on re-pointing, tests to run)
H = "docs/HISTORY.md"
CLASSES = [
    # ---- the v1 family itself
    ("abep_sim/bus_boundary_a9.py", "v1 boundary (A9-02)", "SELF_V1",
     "A9.22 G8: keep the existing bus_boundary_a9 immutable as historical v1",
     "nothing (byte-identical; v2 imports it)", ["tests/test_bus_boundary_a9.py", "tests/test_bus_boundary_a9_v2.py"]),
    ("docs/architecture_comparison/power_boundary_a9/", "v1 boundary (A9-02)", "SELF_V1",
     "A9.22 G8 (v1 immutable); the builder --check must keep reproducing it", "nothing",
     ["tests/test_bus_boundary_a9.py"]),
    ("schemas/interfaces/bus_power_boundary_a9_v1.json", "v1 boundary (A9-02)", "SELF_V1", "A9.22 G8 (v1 immutable)",
     "nothing", ["tests/test_bus_boundary_a9.py"]),
    ("tests/test_bus_boundary_a9.py", "v1 boundary (A9-02)", "SELF_V1", "tests of the immutable v1 boundary",
     "nothing (keeps testing v1)", []),
    # ---- governance records
    (H, "project log", "GOVERNANCE_RECORD", "append-only log (CLAUDE.md rule 1: record why in docs/HISTORY.md)",
     "stage 2 appends the migration entry; existing entries never rewritten", []),
    ("docs/decisions/", "owner decisions", "GOVERNANCE_RECORD", "owner decision records are never edited",
     "nothing", []),
    ("docs/orchestration/", "orchestration records", "GOVERNANCE_RECORD",
     "workflow scripts, lane/trigger registries and the trigger ledger record past executions (append-only "
     "ledger; registry entries describe the A9-02 lane)", "nothing (a stage-2 lane gets its own records)", []),
    # ---- immutable history
    ("docs/experiments/hall_icp/integration/a9_10_", "A9-10 reconciliation", "IMMUTABLE_HISTORY",
     "A9-10 reconciliation pins the five v1 family files byte-identically (a9_10_reconciliation_v1.json); the v1 "
     "builder imports a9_10_overlay.py", "nothing", ["tests/test_a9_10_reconciliation.py"]),
    ("docs/experiments/hall_icp/integration/A9_10_RECONCILIATION.md", "A9-10 reconciliation", "IMMUTABLE_HISTORY",
     "rendering of the A9-10 reconciliation", "nothing", ["tests/test_a9_10_reconciliation.py"]),
    ("docs/experiments/hall_icp/integration/build_a9_10_reconciliation.py", "A9-10 reconciliation", "IMMUTABLE_HISTORY",
     "A9-10 reconciliation builder", "nothing", ["tests/test_a9_10_reconciliation.py"]),
    ("tests/test_a9_10_reconciliation.py", "A9-10 reconciliation", "IMMUTABLE_HISTORY",
     "tests of the A9-10 reconciliation (imports abep_sim.bus_boundary_a9)", "nothing", []),
    ("docs/experiments/hall_icp/integration/a9_core_integration_v1.json", "A9_INT core integration", "IMMUTABLE_HISTORY",
     "A9_INT core integration pins the pre-A9-10 v1 shas (1a3c8d29.., 5bb3a2aa.., 788b8794..)", "nothing",
     ["tests/test_a9_core_integration.py"]),
    ("docs/experiments/hall_icp/integration/A9_CORE_INTEGRATION.md", "A9_INT core integration", "IMMUTABLE_HISTORY",
     "rendering of the core integration", "nothing", ["tests/test_a9_core_integration.py"]),
    ("docs/experiments/hall_icp/integration/build_a9_core_integration.py", "A9_INT core integration",
     "IMMUTABLE_HISTORY", "core integration builder", "nothing", ["tests/test_a9_core_integration.py"]),
    ("tests/test_a9_core_integration.py", "A9_INT core integration", "IMMUTABLE_HISTORY", "tests of the core integration",
     "nothing", []),
    ("docs/experiments/hall_icp/integration/m16_v3/", "M16 v3", "IMMUTABLE_HISTORY",
     "M16 v3 (A9-10 refresh) superseded by v4/v5; pinned by M16 v4, P1-P4, RFQ v2/v3", "nothing", []),
    ("docs/budgets/subsystem_maturity/", "M16 v3", "IMMUTABLE_HISTORY",
     "M16 v3 builder/rendering; pinned by the M16 v4 builder", "nothing", []),
    ("docs/experiments/hall_icp/integration/m16_v4/", "M16 v4", "IMMUTABLE_HISTORY",
     "M16 v4 superseded by v5 (HISTORY 2026-10-03: M16 v4 byte-identical); pinned by M16 v5, F9, H-1 freeze candidate",
     "nothing; M16 v5 must stop resolving 'BUS' through the v4 builder's INPUTS (see M16 v5)", ["tests/test_m16_v4.py"]),
    ("docs/budgets/owner_decisions/OWNER_QUESTIONS_STATE_v2.md", "owner-question state v2-v4", "IMMUTABLE_HISTORY",
     "CLAUDE.md: v2/v3 immutable history; v4 byte-identical (HISTORY 2026-10-03), superseded by v5", "nothing", []),
    ("docs/budgets/owner_decisions/build_owner_questions_state_v2.py", "owner-question state v2-v4",
     "IMMUTABLE_HISTORY", "state v2 builder (immutable history)", "nothing", ["tests/test_owner_questions_state_v2.py"]),
    ("docs/budgets/owner_decisions/owner_questions_state_v2.", "owner-question state v2-v4", "IMMUTABLE_HISTORY",
     "state v2 (immutable history)", "nothing", []),
    ("docs/budgets/owner_decisions/owner_questions_state_v3.", "owner-question state v2-v4", "IMMUTABLE_HISTORY",
     "state v3 (immutable history)", "nothing", []),
    ("docs/budgets/owner_decisions/owner_questions_state_v4.", "owner-question state v2-v4", "IMMUTABLE_HISTORY",
     "state v4 (byte-identical, superseded by v5; pinned by v5, F9, H-1)", "nothing", []),
    ("tests/test_owner_questions_state_v2.py", "owner-question state v2-v4", "IMMUTABLE_HISTORY",
     "tests of state v2", "nothing", []),
    ("docs/budgets/mass_a9/", "mass A9-06 v1", "IMMUTABLE_HISTORY",
     "A9-06 mass reconciliation, 'immutable' per the mass/power v2 lane; pinned by A9-10, mass/power v2, P1",
     "nothing", []),
    ("docs/budgets/mass_power_a9_v2/", "mass/power v2", "IMMUTABLE_HISTORY",
     "superseded by mass/power v3, which sha-pins its builder, JSON and Markdown", "nothing",
     ["tests/test_mass_power_a9_v2.py"]),
    ("tests/test_mass_power_a9_v2.py", "mass/power v2", "IMMUTABLE_HISTORY",
     "tests of mass/power v2 (pins the v1 module sha and boundary_version v1)", "nothing", []),
    ("docs/budgets/xe_ledger_a9/", "Xe ledger A9-08 v1", "IMMUTABLE_HISTORY",
     "A9-08 Xe ledger; pinned by A9-10, mass_a9, mass/power v2, Xe v2, P1", "nothing", []),
    ("docs/budgets/xe_accounting_a9_v2/", "Xe accounting v2", "IMMUTABLE_HISTORY",
     "superseded by Xe accounting v3, which sha-pins it", "nothing", []),
    ("docs/procurement/rfq_a9/", "RFQ v1", "IMMUTABLE_HISTORY",
     "HISTORY 2026-10-03 (AL-08 split): 'RFQ v3 revised in place (v1/v2 stay immutable)'", "nothing",
     ["tests/test_rfq_a9.py"]),
    ("docs/procurement/rfq_a9_v2/", "RFQ v2", "IMMUTABLE_HISTORY",
     "HISTORY 2026-10-03: RFQ v1/v2 stay immutable; sha-pinned by RFQ v3", "nothing", ["tests/test_rfq_a9_v2.py"]),
    ("docs/hardware/h2_a9_revisions/", "H2 A9 revisions v1 (A9-07)", "IMMUTABLE_HISTORY",
     "A9-07 verified deliverable inside the A9-10 reconciliation; sha-pinned by P1-P4, F9, H-1, mass/power v2", "nothing",
     ["tests/test_h2_a9_revisions.py"]),
    ("tests/test_h2_a9_revisions.py", "H2 A9 revisions v1 (A9-07)", "IMMUTABLE_HISTORY", "tests of A9-07", "nothing", []),
    ("docs/experiments/hall_icp/prereg_framework/", "A9-01 prereg framework", "IMMUTABLE_HISTORY",
     "A9-01 deliverable pinned by core integration and A9-10 (and by P1, F9, H-1, H2 A9, RFQ v1)", "nothing",
     ["tests/test_hall_icp_prereg_framework.py"]),
    ("tests/test_hall_icp_prereg_framework.py", "A9-01 prereg framework", "IMMUTABLE_HISTORY", "tests of A9-01",
     "nothing", []),
    ("docs/interfaces/icp_neutralizer/", "A9-03 ICP neutralizer ICD", "IMMUTABLE_HISTORY",
     "A9-03 deliverable pinned by core integration and A9-10", "nothing", []),
    ("schemas/interfaces/icp_neutralizer_icd_v1.json", "A9-03 ICP neutralizer ICD", "IMMUTABLE_HISTORY",
     "A9-03 schema; sha-pinned by F9, dossier, mass_a9, Xe ledger, A9-10, M16 v3, P1-P3, H-1, H2 A9, RFQ v1-v3",
     "nothing", []),
    ("docs/experiments/hall_icp/uncertainty_budget/", "A9-04 uncertainty budget", "IMMUTABLE_HISTORY",
     "A9-04 deliverable pinned by core integration and A9-10 (and by P1, P2, H2 A9, RFQ v1-v3)", "nothing",
     ["tests/test_hall_icp_uncertainty_budget.py"]),
    ("tests/test_hall_icp_uncertainty_budget.py", "A9-04 uncertainty budget", "IMMUTABLE_HISTORY", "tests of A9-04",
     "nothing", []),
    ("docs/experiments/hall_icp/validation_inputs/", "A9-05 validation inputs", "IMMUTABLE_HISTORY",
     "A9-05 deliverable pinned by core integration and A9-10", "nothing", ["tests/test_hall_icp_validation_inputs.py"]),
    ("tests/test_hall_icp_validation_inputs.py", "A9-05 validation inputs", "IMMUTABLE_HISTORY", "tests of A9-05",
     "nothing", []),
    ("docs/bid/owner_decision_brief_p0_p1.json", "owner decision brief P0/P1", "IMMUTABLE_HISTORY",
     "commit-anchored quotes (base 66fe963, bid source bbc480c); tests/test_owner_decision_brief.py re-reads every "
     "quote from git at the cited commit, so it stays valid while v1 stays in history", "nothing",
     ["tests/test_owner_decision_brief.py"]),
    ("docs/bid/OWNER_DECISION_BRIEF_P0_P1.md", "owner decision brief P0/P1", "IMMUTABLE_HISTORY",
     "rendering of the commit-anchored brief", "nothing", ["tests/test_owner_decision_brief.py"]),
    # ---- live, reference stays v1
    ("docs/bid/package/", "bid technical package (draft)", "LIVE_RETAIN_V1_REFERENCE",
     "DRAFT_FOR_OWNER_REVIEW whose sources are anchored at the bid freeze bbc480c (docs/bid/bid_technical_baseline.json: "
     "'Do not continue changing architecture underneath the proposal'); v2 does not exist at bbc480c",
     "nothing unless the owner moves the bid source baseline (then: BPB path in compliance_data.py -> v2 JSON; the "
     "JSON pointers #/slots, #/bus_architecture, #/gates_and_allocations, #/sequencing resolve in v2; regenerate "
     "01_COMPLIANCE_MATRIX.md + compliance_matrix_v1.json; 02/04 hand-written citations)", ["tests/test_bid_package.py"]),
    ("docs/budgets/owner_decisions/owner_questions_state_v5.", "owner-question state v5", "LIVE_RETAIN_V1_REFERENCE",
     "the seven OQ-A902-01..07 rows cite where the question was raised (A9-02, bus_power_boundary_a9_v1), plus "
     "'not declared in bus_power_boundary_a9_v1' in OQ-A902-04: provenance of origin, still correct",
     "nothing required (optionally a note that the boundary continues as v2); a rebuild changes its sha, which F9 and "
     "H-1 pin", ["tests/test_owner_questions_state_v5.py"]),
    ("docs/architecture_comparison/dossier/", "decision dossier", "LIVE_RETAIN_V1_REFERENCE",
     "scripts/architecture/build_decision_dossier.py lists every file of schemas/interfaces (input upstream_icd, "
     "lane_33) with its sha256; v1 stays listed because the file stays",
     "on its next rebuild the listing gains schemas/interfaces/bus_power_boundary_a9_v2.json; no re-point",
     ["tests/test_decision_dossier.py"]),
    # ---- live, re-point in stage 2
    ("abep_sim/design/architecture_optimizer.py", "F7 architecture optimizer (code)", "LIVE_REPOINT",
     "current design-layer code (A9.19 single flight configuration); imports the boundary as bb",
     "'from .. import bus_boundary_a9 as bb' -> bus_boundary_a9_v2; the assertion set(CONFIGURATIONS) | "
     "set(GROUND_REFERENCE_CONFIGURATIONS) == set(bb.CONFIGURATIONS) becomes CONFIGURATIONS == bb.CONFIGURATIONS and "
     "GROUND_REFERENCE_CONFIGURATIONS == tuple(bb.GROUND_REFERENCE_TEST_METADATA); source/basis strings name "
     "bus_boundary_a9_v2; ledgers carry boundary_version v2, every number identical",
     ["tests/test_design_f7_f8_optimizer.py", "tests/test_design_a9_19_architecture.py",
      "tests/test_design_a9_13_upstream.py", "tests/test_design_review_repairs.py",
      "tests/test_decision_application_a9_16.py"]),
    ("docs/design_synthesis/f7_f8_optimizer/", "F7/F8 optimizer outputs", "LIVE_REPOINT",
     "regenerated design-chain output (HISTORY: F4 -> F7/F8 -> F9 rebuilds)",
     "build_f7_f8_optimizer.py referenced_not_pinned path -> abep_sim/bus_boundary_a9_v2.py; regenerate; JSON source "
     "strings (RF_FREQUENCY_HZ, LAB_RF_FORWARD_W_RANGE, rfp_power_gate basis) name v2; values unchanged; F9 re-pins it",
     ["tests/test_design_f7_f8_optimizer.py", "tests/test_single_flight_configuration.py",
      "tests/test_architecture_freeze_candidate.py"]),
    ("docs/architecture/freeze_candidate/", "F9 architecture freeze candidate", "LIVE_REPOINT",
     "live F9 (regenerated in dependency order; AG-15 lane in flight)",
     "INPUTS 'BUS' -> v2 JSON; 24 sha pins 9f6e074c.. -> v2 sha; the JSON pointers /items[id=A902-..], /slots, "
     "/sequencing/enforced_order/hall_icp_neutralizer resolve to identical values in v2; also re-pin P1, P2, RVM, "
     "mass/power v3, Xe v3, F7/F8, state v5 if they change", ["tests/test_architecture_freeze_candidate.py",
                                                               "tests/test_f9_rfp_citations.py",
                                                               "tests/test_icp_gate_a9_21.py",
                                                               "tests/test_hw_programme_a9_21.py"]),
    ("docs/requirements/rvm_a9/", "RVM", "LIVE_REPOINT",
     "live requirements verification matrix (AG-15 lane in flight: re-point after it merges)",
     "build_rvm_a9.py REFS 'BUS' -> (v2 JSON, 'id', 'bus_power_boundary_a9_v2'); rvm_a9_rows.py plan(ctx, 'BUS', ..) "
     "unchanged; hall_icp_neutralizer artifact ids bus_power_boundary_a9_v1:A902-xx -> ..._v2:A902-xx; rows in the "
     "C1 ground-reference / retired section keep citing v1 (C1 is not a v2 configuration)",
     ["tests/test_rvm_a9.py", "tests/test_rfp_registration_v1.py", "tests/test_a9_16_repair_readback.py"]),
    ("docs/budgets/mass_power_a9_v3/", "mass/power v3", "LIVE_REPOINT",
     "current mass/power budget (A9.16 step 1, A9.19/A9.21 updates)",
     "BUS_MODULE pin and peak_sampled_gate_a9_v3.py import -> abep_sim/bus_boundary_a9_v2.py; power.boundary_version / "
     "module / module_sha256 -> v2; hall_icp_neutralizer ledgers relabelled v2 with identical numbers; "
     "retired_flight_configuration_history (C1) and the carried items_v2 source pins stay v1 (history)",
     ["tests/test_mass_power_a9_v3.py", "tests/test_single_flight_configuration.py"]),
    ("tests/test_mass_power_a9_v3.py", "mass/power v3", "LIVE_REPOINT", "tests of mass/power v3",
     "PINS: abep_sim/bus_boundary_a9.py sha -> add/replace with the v2 module sha", []),
    ("docs/budgets/xe_accounting_a9_v3/", "Xe accounting v3", "LIVE_REPOINT",
     "current Xe accounting (A9.16/A9.19 updates)",
     "the start-up-template source citation (I-S5 / C-S5) -> v2 JSON (I-S5 under sequencing.templates_PROPOSED, C-S5 "
     "under ground_reference_test_metadata); carried from Xe v2 text, so the v3 builder maps it",
     ["tests/test_xe_accounting_a9_v3.py", "tests/test_single_flight_configuration.py"]),
    ("docs/procurement/rfq_a9_v3/", "RFQ v3", "LIVE_REPOINT",
     "HISTORY 2026-10-03: 'RFQ v3 revised in place' (live)",
     "19 package requirement sources + 1 basis cite the v1 JSON (items/slots identical in v2) -> v2; "
     "carried_from_v2.deliverable_pins keeps the v1 sha (carried history); the v3 builder maps the carried sources",
     ["tests/test_rfq_a9_v3.py"]),
    ("docs/experiments/hall_icp/p1_icp_bench/", "P1 ICP bench", "LIVE_REPOINT",
     "framework updated by later owner rules (tests/test_p1_a9_16_owner_rules.py, test_p1_a9_19_owner_rules.py); "
     "sha-pinned only by F9 (live) and the commit-anchored brief",
     "BUS authority pin (path + sha) -> v2; items/interface_demands citing A902-19/21/22/23 -> v2; historical_reuse "
     "entry keeps v1; rebuild changes its sha (re-pin in F9)",
     ["tests/test_p1_icp_bench.py", "tests/test_p1_a9_16_owner_rules.py", "tests/test_p1_a9_19_owner_rules.py"]),
    ("docs/experiments/hall_icp/p2_impedance_map/", "P2 impedance prep", "LIVE_REPOINT",
     "framework updated by later owner rules (tests/test_p2_a9_16_owner_rules.py, test_p2_a9_19_owner_rules.py); "
     "sha-pinned only by F9",
     "INPUTS 'BUS' (path + sha) -> v2; deliverable_pins entry -> v2; rebuild changes its sha (re-pin in F9)",
     ["tests/test_p2_impedance_prep.py", "tests/test_p2_impedance_framework.py", "tests/test_p2_a9_16_owner_rules.py",
      "tests/test_p2_a9_19_owner_rules.py"]),
    ("docs/experiments/hall_icp/integration/m16_v5/", "M16 v5", "LIVE_REPOINT",
     "current subsystem-maturity matrix (supersedes v4)",
     "BUS_ITEM_OPEN blockers resolve 'BUS' through the immutable v4 builder's INPUTS (v1 JSON): give v5 its own 'BUS' "
     "ref -> v2 JSON (A902-21 identical); remaining_blockers artifact paths -> v2", ["tests/test_m16_v5.py"]),
    ("tests/test_design_a9_19_architecture.py", "design tests", "LIVE_REPOINT", "tests of live design code",
     "import -> v2; the C1 hollow-cathode check bb.installed_slots('hall_c1_reference') reads "
     "bb.GROUND_REFERENCE_TEST_METADATA[...]['base_slots_as_in_v1'] (v2 refuses C1 as a configuration)", []),
    ("tests/test_design_f7_f8_optimizer.py", "design tests", "LIVE_REPOINT", "tests of live design code",
     "import -> v2 (only hall_icp_neutralizer ledgers are built)", []),
    ("tests/test_single_flight_configuration.py", "single-configuration scan", "LIVE_REPOINT",
     "live scan of the design chain",
     "PINNED_PRE_A9_19 allowance for the v1 JSON stays (v1 stays byte-identical); its comment lists the consumers that "
     "still pin v1 after stage 2; the v2 JSON is scanned and passes", []),
    # ---- transitive
    ("abep_sim/design/robust_optimizer.py", "F8 robust optimizer (code)", "TRANSITIVE_LIVE",
     "imports architecture_optimizer", "nothing to edit; follows architecture_optimizer",
     ["tests/test_design_f7_f8_optimizer.py", "tests/test_design_a9_13_upstream.py"]),
    ("tests/test_design_a9_13_upstream.py", "design tests", "TRANSITIVE_LIVE", "imports architecture_optimizer",
     "nothing to edit; re-run", []),
    ("tests/test_design_review_repairs.py", "design tests", "TRANSITIVE_LIVE", "imports architecture_optimizer",
     "nothing to edit; re-run", []),
]


class InventoryError(RuntimeError):
    """A consumer without classification, or a classification without consumer (no silent gaps)."""


def _classify(path: str):
    best = None
    for c in CLASSES:
        if path == c[0] or (c[0].endswith(("/", "_", ".")) and path.startswith(c[0])):
            if best is None or len(c[0]) > len(best[0]):
                best = c
    return best


_BLOBS: dict = {}


def _git(*args, inp: bytes | None = None) -> bytes:
    r = subprocess.run(["git", *args], cwd=ROOT, input=inp, capture_output=True)
    if r.returncode:
        raise InventoryError(f"git {' '.join(args)} failed (is {BASE_COMMIT} in this clone?): "
                             f"{r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def _tracked() -> list:
    """Tracked files of BASE_COMMIT (blob contents cached for _read)."""
    if not _BLOBS:
        rows = [ln.split("\t", 1) for ln in _git("ls-tree", "-r", "-z", BASE_COMMIT).decode("utf-8").split("\0") if ln]
        ents = [(meta.split()[2], path) for meta, path in rows if meta.split()[1] == "blob"]
        out = _git("cat-file", "--batch", inp="".join(sha + "\n" for sha, _ in ents).encode())
        pos = 0
        for sha, path in ents:
            nl = out.index(b"\n", pos)
            size = int(out[pos:nl].split()[2])
            _BLOBS[path] = out[nl + 1:nl + 1 + size]
            pos = nl + 1 + size + 1
    return sorted(_BLOBS)


def _read(rel: str) -> bytes:
    _tracked()
    return _BLOBS[rel]


def _target(text: str) -> str:
    m = SHA_RX.search(text)
    if m:
        return SHA_TO_TARGET[m.group(0)]
    for tok, tgt in (("bus_power_boundary_a9_v1.json", None), (V1_SCHEMA, V1_SCHEMA), (V1_JSON, V1_JSON),
                     ("build_bus_power_boundary_a9", V1_BUILDER), ("BUS_POWER_BOUNDARY_A9.md", V1_MD),
                     ("bus_boundary_a9", V1_MOD), ("power_boundary_a9/", "docs/architecture_comparison/power_boundary_a9/"),
                     ("bus_power_boundary_a9_v1", "boundary label bus_power_boundary_a9_v1")):
        if tok in text:
            if tgt is None:
                return V1_SCHEMA if "schemas/interfaces/bus_power_boundary_a9_v1.json" in text else V1_JSON
            return tgt
    return "boundary label"


def scan() -> dict:
    files = {}
    for rel in _tracked():
        if rel.startswith(OWN) or rel in OWN:
            continue
        try:
            lines = _read(rel).decode("utf-8").split("\n")
        except UnicodeDecodeError:
            continue
        hits = []
        sha_lines = {i for i, ln in enumerate(lines) if SHA_RX.search(ln)}
        key = KEY_IN_SELF.get(rel)
        for i, ln in enumerate(lines):
            name, sha = NAME_RX.search(ln), i in sha_lines
            kind = None
            if IMPORT_RX.search(ln):
                kind = "import"
            elif sha:
                kind = "sha_pin"
            elif name and rel.endswith((".json", ".jsonl")) and any(j in sha_lines for j in range(i - 3, i + 4)):
                kind = "sha_pin"          # the path line of a pinned record
            elif name and rel in READERS and any(t in ln for t in READ_TOKENS):
                kind = "read"
            elif name:
                kind = "text_citation"
            elif key and re.search(key, ln) and not ln.lstrip().startswith("#"):
                kind = "key_reference"
            elif rel in KEY_USERS and re.search(r"[\"']" + KEY_USERS[rel][0] + r"[\"']", ln):
                kind = "key_reference"
            elif TRANSITIVE_RX.search(ln):
                kind = "transitive_import"
            if kind:
                text = ln.strip()
                tgt = (_target(text) if kind not in ("key_reference", "transitive_import") else
                       (V1_JSON if kind == "key_reference" else TRANSITIVE_VIA))
                hits.append({"line": i + 1, "kind": kind, "target": tgt,
                             "text": text if len(text) <= 200 else text[:197] + "..."})
        # a consumer: a direct reference, a declared key user, or a transitive importer (all must be classified)
        if any(h["kind"] not in ("key_reference", "transitive_import") for h in hits) or (hits and (
                rel in KEY_USERS or any(h["kind"] == "transitive_import" for h in hits))):
            files[rel] = hits
    return files


def pinned_by(files: list, tracked: list) -> dict:
    """Who sha-pins each consumer file (current sha256, full hex): the cascade a re-pointed consumer triggers."""
    shas = {}
    for rel in files:
        shas[hashlib.sha256(_read(rel)).hexdigest()] = rel
    out = {rel: [] for rel in files}
    rx = re.compile(r"[0-9a-f]{64}")
    for rel in tracked:
        try:
            found = set(rx.findall(_read(rel).decode("utf-8")))
        except UnicodeDecodeError:
            continue
        for h in found:
            if h in shas and shas[h] != rel:
                out[shas[h]].append(rel)
    return {k: sorted(v) for k, v in out.items()}


def build() -> dict:
    files = scan()
    tracked = _tracked()
    unclassified = [f for f in files if _classify(f) is None]
    if unclassified:
        raise InventoryError(f"consumers without classification: {unclassified}")
    used = {_classify(f)[0] for f in files}
    stale = [c[0] for c in CLASSES if c[0] not in used]
    if stale:
        raise InventoryError(f"classifications that match no consumer: {stale}")
    missing_tests = sorted({t for c in CLASSES for t in c[5] if t not in _BLOBS})
    if missing_tests:
        raise InventoryError(f"listed tests do not exist: {missing_tests}")
    pins = pinned_by(list(files), tracked)
    consumers = []
    for rel in sorted(files):
        prefix, family, status, evidence, change, tests = _classify(rel)
        kinds = sorted({h["kind"] for h in files[rel]})
        consumers.append({"path": rel, "family": family, "status": status, "dependency_kinds": kinds,
                          "targets": sorted({h["target"] for h in files[rel]}), "evidence": evidence,
                          "change_on_repoint": change, "tests": tests, "sha_pinned_by": pins[rel],
                          "hits": files[rel]})
    by_status, by_kind, fam = {}, {}, {}
    for c in consumers:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
        for h in c["hits"]:
            by_kind[h["kind"]] = by_kind.get(h["kind"], 0) + 1
        fam.setdefault((c["status"], c["family"]), []).append(c["path"])
    families = [{"status": s, "family": f, "files": len(v)} for (s, f), v in sorted(fam.items())]
    fam_status = {}
    for (s, _f), _v in fam.items():
        fam_status[s] = fam_status.get(s, 0) + 1
    return {
        "schema": "consumer_inventory_v1",
        "id": "bus_power_boundary_a9_v1_consumer_inventory",
        "decision": "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json G8_BUS_BOUNDARY "
                    "(item 8: list every consumer before changing anything)",
        "stage": "1 (inventory + v2 artefact; NO consumer re-pointed); re-run at the pre-migration head before the "
                 "stage-2 migration (docs/architecture_comparison/power_boundary_a9_v2/STAGE2_MIGRATION.json)",
        "date": DATE, "base_commit": BASE_COMMIT, "stage_1_commit": STAGE1_COMMIT,
        "scanned_tree": f"git tree of {BASE_COMMIT} (not the working tree: reproducible after stage 2)",
        "generated_by": SCRIPT_REL,
        "regenerate": f"python {SCRIPT_REL}  (check: --check)",
        "v1_family": {V1_MOD: FAMILY_SHAS[V1_MOD], V1_JSON: FAMILY_SHAS[V1_JSON], V1_BUILDER: FAMILY_SHAS[V1_BUILDER],
                      V1_MD: FAMILY_SHAS[V1_MD], V1_SCHEMA: FAMILY_SHAS[V1_SCHEMA]},
        "method": ["every tracked text file of the base commit's git tree scanned line by line",
                   "name match: bus_boundary_a9 | bus_power_boundary_a9 | power_boundary_a9 | BUS_POWER_BOUNDARY_A9 "
                   "(not followed by _v2)",
                   "sha match: 16-hex prefix of the sha256 of every committed version of the five v1 family files",
                   "key_reference: lines using a pin key that the file (or the declared definer) binds to the v1 "
                   "document: " + json.dumps({k: v[0] for k, v in KEY_USERS.items()}) + "; in-file keys "
                   + json.dumps(KEY_IN_SELF),
                   "transitive_import: modules/tests importing " + TRANSITIVE_VIA,
                   "kinds: import | read (code loading a family file) | sha_pin (sha line or the path line of a pinned "
                   "record) | key_reference | transitive_import | text_citation",
                   "sha_pinned_by: tracked files containing the consumer's current full sha256 (the re-pin cascade)",
                   "unclassified consumers and unused classifications refuse the build"],
        "statuses": {"IMMUTABLE_HISTORY": "stays on v1, never edited",
                     "LIVE_REPOINT": "moves to v2 in the single controlled stage-2 migration",
                     "LIVE_RETAIN_V1_REFERENCE": "live file whose v1 reference stays correct",
                     "TRANSITIVE_LIVE": "no direct reference; follows a LIVE_REPOINT module (re-run tests)",
                     "SELF_V1": "the v1 family itself (immutable)",
                     "GOVERNANCE_RECORD": "decisions / HISTORY / orchestration records"},
        "counts": {"files": len(consumers), "files_by_status": dict(sorted(by_status.items())),
                   "families_by_status": dict(sorted(fam_status.items())),
                   "hits_by_kind": dict(sorted(by_kind.items()))},
        "families": families,
        "stage_2_rules": [
            "one controlled migration after the parallel AG-15 lane merges (RVM and F9 are consumers)",
            "re-point every LIVE_REPOINT file; leave IMMUTABLE_HISTORY / SELF_V1 / GOVERNANCE_RECORD untouched",
            "update all sha pins together in dependency order: v2 artefact -> P1, P2, mass/power v3, Xe v3, RFQ v3, "
            "M16 v5, F7/F8 -> RVM -> F9 (F9 pins P1, P2, RVM, mass/power v3, Xe v3, F7/F8, state v5)",
            "no physics result may change: every re-pointed ledger/gate/allocation value must equal its v1 value "
            "(only boundary_version / module labels change); compare before/after outputs field by field",
            "run every test listed under the re-pointed consumers plus the full suite, golden and ci_checks",
            "C1 rows in live artefacts (retired / ground-reference sections) keep citing v1: C1 is not a v2 "
            "configuration",
            "owner calls flagged: bid package anchor (bbc480c) and the C1 ground-bench ledger boundary"],
        "consumers": consumers,
    }


# ------------------------------------------------------------------------------------------------------ markdown
def _e(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(d: dict) -> str:
    c = d["counts"]
    L = ["# Consumer inventory: `bus_power_boundary_a9_v1` (A9.22 G8, stage 1)", "",
         f"<!-- GENERATED by {d['generated_by']} from CONSUMER_INVENTORY.json; do not edit by hand -->", "",
         f"Decision: {d['decision']}. Stage: {d['stage']}. Base commit `{d['base_commit']}`.", "",
         "## Counts", "",
         f"- consumer files: {c['files']}",
         "- files by status: " + ", ".join(f"{k} {v}" for k, v in c["files_by_status"].items()),
         "- families by status: " + ", ".join(f"{k} {v}" for k, v in c["families_by_status"].items()),
         "- hits by dependency kind: " + ", ".join(f"{k} {v}" for k, v in c["hits_by_kind"].items()), "",
         "## Statuses", ""] + [f"- **{k}**: {v}" for k, v in d["statuses"].items()] + [
         "", "## Method", ""] + [f"- {m}" for m in d["method"]] + [
         "", "## Stage-2 rules", ""] + [f"- {r}" for r in d["stage_2_rules"]] + [
         "", "## Families", "", "| status | family | files |", "|---|---|---|"]
    L += [f"| {f['status']} | {_e(f['family'])} | {f['files']} |" for f in d["families"]]
    order = ["LIVE_REPOINT", "TRANSITIVE_LIVE", "LIVE_RETAIN_V1_REFERENCE", "IMMUTABLE_HISTORY", "SELF_V1",
             "GOVERNANCE_RECORD"]
    for st in order:
        cs = [x for x in d["consumers"] if x["status"] == st]
        if not cs:
            continue
        L += ["", f"## {st} ({len(cs)} files)", "",
              "| file | family | kinds | evidence | change on re-point | tests | sha-pinned by |", "|---|---|---|---|---|---|---|"]
        for x in cs:
            L.append(f"| `{x['path']}` | {_e(x['family'])} | {', '.join(x['dependency_kinds'])} | {_e(x['evidence'])} | "
                     f"{_e(x['change_on_repoint'])} | {_e(', '.join(x['tests']) or '-')} | "
                     f"{_e(', '.join(x['sha_pinned_by']) or '-')} |")
    L += ["", "## Hits (file:line, kind, target)", ""]
    for x in d["consumers"]:
        L.append(f"- `{x['path']}` ({x['status']}): " + "; ".join(
            f"L{h['line']} {h['kind']} -> {h['target']}" for h in x["hits"]))
    L.append("")
    return "\n".join(L)


def dumps(d: dict) -> str:
    return json.dumps(d, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the committed outputs reproduce byte-for-byte")
    a = ap.parse_args(argv)
    d = build()
    outs = {OUT_JSON: dumps(d), OUT_MD: render_md(d)}
    if a.check:
        bad = [os.path.relpath(p, ROOT) for p, txt in outs.items()
               if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt]
        if bad:
            print("DRIFT: " + ", ".join(bad))
            return 1
        print("OK")
        return 0
    for p, txt in outs.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
    print("wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
