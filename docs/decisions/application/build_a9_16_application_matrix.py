"""A9.16 decision-application matrix: every owner decision id of A9.8 .. A9.15 -> how it is applied to the artifacts.

Owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1). One entry per decision id with
an overall status from the closed vocabulary STATUSES, the artifact applications (artifact path + record locations +
commit), and residual items (blocked / pending parts). Lane applications come from the A9.16 step-1 lane results
(commit of each lane); every one is verified at build time: the question id must occur in the lane artifact (fail
closed). Integration applications are read from the integration artifacts' owner_answers_applied rows. Nothing here
answers a question; decision files are only read (pinned through a9_16_lib).

    python docs/decisions/application/build_a9_16_application_matrix.py          # write JSON + MD
    python docs/decisions/application/build_a9_16_application_matrix.py --check  # verify both are current
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import a9_16_lib as L  # noqa: E402

OUT_JSON = HERE / "a9_16_application_matrix.json"
OUT_MD = HERE / "a9_16_application_matrix.md"
REL = lambda p: Path(p).resolve().relative_to(ROOT).as_posix()

STATUSES = {
    "APPLIED": "applied to the governing artifact(s) (artifact path + record locations + commit)",
    "NOT_APPLICABLE_TO_ARTIFACTS": "no artifact change is required now (reason given); registered in state v5",
    "PENDING_STEP_2_MODEL_CHANGE": "A9.9 production-model change, authorised; implemented in A9.16 step 2",
    "PENDING_STEP_3_ARCHITECTURE": "A9.13 decision whose application changes design-synthesis / optimizer code; "
                                   "record-level parts applied where listed; code in A9.16 step 3",
    "PENDING_CI_CHANGE": "needs a CI workflow change (.github/workflows), outside every A9.16 step-1 allowed path",
    "BLOCKED": "cannot be applied yet (missing input or record outside the allowed paths; named in 'residual')",
    "PARTIAL": "the decision's rule is recorded in the governing artifact but a named part it requires (a selection, a "
               "registration) is still pending - not APPLIED until that part exists (named in 'residual')",
}
RESIDUAL_STATUSES = ("BLOCKED", "PENDING_STEP_2_MODEL_CHANGE", "PENDING_STEP_3_ARCHITECTURE", "PENDING_EVIDENCE",
                     "PENDING_CI_CHANGE", "OPEN_OWNER_QUESTION")

INTEGRATION_COMMITS = {"repin": "5acdcde8be7d41cfb0d6c26b1ad7cb899d279871",
                       "records": "d681230d79e98de1f68085310950086e5e18048c"}
# A9.16 repair lane (review findings F1-F11, COR-01..07): the commit that applied the decisions below. Every
# application is verified at build time like a lane result (the question id must occur in the artifact).
REPAIR_COMMIT = "1d515542e268dc042c9e48a4b1e496de4891f6e5"
REPAIR = [
    # (question id, artifact, what) - F1 / F5
    ("ICPQ-10", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "F1: P2 records ICPQ-10 OWNER_DECIDED (A9.12 S5.1 alternative A); alternative B only as rejected history; RC-HEAT "
     "references p3_a9_16_rules.icp43_total_module_bound and refuses any other heat_load_option"),
    ("OQ-A910-06", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "F5: P2 output OQ-A910-06 OWNER_DECIDED (A9.12 S5.8), P2 envelope consumed by p3_a9_16_rules.rf_thermal_basis"),
    ("OQ-A910-06", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
     "F5: open_register_status OQ-A910-06 OWNER_DECIDED (A9.12 S5.8)"),
    # F2
    ("P3Q-01", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
     "F2: P1-M-30 REQUIRED Langmuir probe (matched diagnostic runs, calorimetry primary); capacity records exclude an "
     "undeclared / unevidenced probe; XL-18 / XL-25 re-stated"),
    ("P3Q-01", "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
     "F2: XL-18 re-stated on the P3 side (P3-IF-N02)"),
    ("P3Q-01", "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
     "F2: XL-25 re-stated on the P4 side (ID-06)"),
    # F3
    ("OD5", "docs/requirements/rvm_a9/rvm_a9_v1.json",
     "F3: RVM-14 ICP-first sequence limited by registered dwell / thermal limits only; 120 s / 360 s kept for the "
     "C1-selected variant's Xe booking"),
    ("XA9Q-02", "docs/requirements/rvm_a9/rvm_a9_v1.json", "F3: 120 s / 360 s scoped to the C1 variant"),
    # F4
    ("OQ-RFQV2-10", "docs/procurement/rfq_a9_v3/rfq_a9_v3.json",
     "F4: RFQ3-H1FAB sent against the P9e configuration-controlled P1 engineering drawing set; LOCK-1 release kept for "
     "the flight H-1 only (recorder reading for the owner to confirm)"),
    # F6 / F11
    ("MPQ-01", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
     "F6: P-FL-C1 a configuration-scope zero (no C1 in hall_icp_neutralizer), not an owner Xe exclusion; XV2-02 and the "
     "C1 sensitivity labelled A5 design-target placeholders"),
    ("XA9Q-05", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
     "F11: ICP-feed 'contingency' label traced to A9.1 HIQ-06; whether A9.15 changes it is open owner question XV3Q-01"),
    # F9
    ("P1Q-19", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
     "F9: the rejected alternative is NOT_OWNER_SELECTED_INFORMATIONAL (no margin, no condition_met); docstrings "
     "follow the owner choice"),
    # F10
    ("OQ-A907-01", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
     "F10: C-S4 keeper ignition <= 3 dwells (1 + 2 retries) x 120 s = 360 s maximum booking"),
    ("XA9Q-02", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json", "F10: as above"),
    # F8
    ("OD5", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json",
     "F8: AFC-SY-CTL-01 sequence OWNER_DECIDED, dwell / thermal limits PENDING_REGISTRATION"),
    ("XA9Q-07", "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json",
     "F8: Xe rows re-pointed to xe_accounting_a9_v3 / mass_power_a9_v3 / state v5 (v2 / v4 sources marked history)"),
    # COR-06 / COR-07
    ("P4-OQ-01", "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
     "COR-06: CR-01 admits T_validated_continuous only with a referenced stage record (id + sha256) classified by "
     "validation_stage_record; a bare declaration is INCOMPLETE_EVIDENCE"),
    ("P2Q-01", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
     "COR-07: method_agreement needs ZM-B valid = True at the same operating point / configuration"),
    ("P2Q-03", "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", "COR-07: as above"),
]
REPAIR_FIXES = [
    {"id": "COR-01", "what": "immutable state-v4 builder reproduces again: P1 / P2 keep their as-raised "
     "open_owner_questions (current status in owner_question_status_current / answered_owner_questions + "
     "owner_questions_open_now), P1 derived_resolutions keep the as-raised disposition (owner_decision beside it), "
     "P4 / RVM keep the as-raised status (status_current beside it), P3 v1 is the A9.6 package"},
    {"id": "COR-02", "what": "immutable RFQ v2 builder reproduces again: P1-IT-36 and P1-M-30 keep the read-back "
     "status / quantity text (status_a9_16 / quantity_a9_16 govern)"},
    {"id": "COR-05", "what": "build_p3_coupled_thermal.py and its v1 outputs restored byte-identical (F0-profiled "
     "source pinned through the parity pre-registration); every A9.16 P3 change moved to build_p3_coupled_thermal_v2.py "
     "-> p3_coupled_thermal_v2.json / P3_COUPLED_THERMAL_V2.md, which the current-state consumers read"},
    {"id": "COR-03", "what": "F4 regenerated (build_f4_plenum.py, build CPU 102 s): only its pin of the current H-1 "
     "freeze candidate changed; --check and tests/test_design_f4_plenum.py::test_pins_hold pass"},
    {"id": "COR-04", "what": "F7 / F8 NOT regenerated: its builder exceeds the 2-minute command limit (BLOCKED; pins "
     "to F6 / H-1 / F4 stay stale until a run without that limit)"},
]

# ------------------------------------------------------------------------------------------------ lane results
LANES = {
    "P1": ("b1bac8dc5df0a03e55954e0f0b26bf27bdcd86a4", "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
           ["P1Q-04", "P1Q-09", "P1Q-11", "P1Q-18", "P1Q-20", "P1-IT-52", "P1-IT-55", "OQ-RFQV2-06", "OQ-RFQV2-08",
            "P1Q-02", "P1Q-03", "P1Q-05", "P1Q-06", "P1Q-07", "P1Q-08", "P1Q-19", "P1Q-24", "OQ-RFQV2-09", "P1Q-01",
            "P1Q-17", "P1Q-12", "OD5", "ICPQ-08", "F6-OQ-03"]),
    "P2": ("3ff91954875e69f2baf9ba41cca546c657d6260d",
           "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
           ["P2Q-01", "P2Q-03", "P2Q-04", "P2Q-07", "P2Q-08", "P2Q-09", "P1Q-24", "P2Q-02", "ICPQ-11", "P2Q-10",
            "P2Q-06", "F6-OQ-02"]),
    "P3": ("c00f9b5c424feda2c653c87b3eb1b7d9d3a51009",
           "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json",
           ["P3Q-01", "ICPQ-10", "OQ-A907-03", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "OQ-A907-09", "OQ-A907-10",
            "OQ-A910-06", "P3Q-02", "ICPQ-03", "ICPQ-09"]),
    "P4": ("673c058c4dd0a52633470e1c4593ab41f99f7665",
           "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
           ["P4-OQ-01", "P4-OQ-02", "P4-OQ-03", "P4-OQ-04", "P4-OQ-05", "OQ-A907-05", "F2-OQ-04"]),
    "RFQ": ("f68b9999ebc89c41ab051bfaebf03c04fc58cc78", "docs/procurement/rfq_a9_v3/rfq_a9_v3.json",
            ["P2Q-02", "OQ-RFQV2-01", "OQ-RFQV2-02", "OQ-RFQV2-03", "OQ-RFQV2-04", "OQ-RFQV2-05", "OQ-RFQV2-06",
             "OQ-RFQV2-08", "P1-IT-55", "OQ-RFQV2-09", "OQ-RFQV2-10", "P2Q-07", "OQ-RFQ-01", "OQ-RFQ-03", "OQ-RFQ-04",
             "OQ-RFQ-08", "OQ-RFQ-09", "XA9Q-06", "XA9Q-01", "OQ-A907-04", "XA9Q-07", "XA9Q-05", "P1Q-09", "P3Q-01",
             "P1Q-17", "MQ-05"]),
    "MASS_POWER_V3": ("d008ac31daa11b6d0fcfe4ad78f9587e359bced3", "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
                      ["MQ-01", "MQ-02", "MQ-03", "MQ-04", "MQ-05", "MQ-06", "MQ-07", "MQ-09", "MQ-10", "MPQ-01",
                       "MPQ-02", "OQ-A907-07", "OQ-A910-01", "OQ-A910-03", "OQ-A910-05", "XA9Q-07"]),
    "XE_V3": ("d008ac31daa11b6d0fcfe4ad78f9587e359bced3", "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json",
              ["XA9Q-07", "XV2Q-01", "XA9Q-02", "OQ-A907-01", "XA9Q-03", "XA9Q-04", "XA9Q-06", "XA9Q-05", "XA9Q-01",
               "MQ-09", "OQ-A910-01", "OD6", "OQ-A907-07", "MPQ-01"]),
}
# A9.15 reviews by lanes (no 'Xe contingency-only for C1' wording to amend): NOT_APPLICABLE applications
A915_REVIEWED_NA = {"P1": "P1 is the Ar engineering step; no Xe-contingency wording; G-REUSE unchanged",
                    "P2": "no Xe-contingency wording; G-REUSE / G-XE ICP gas modes unchanged",
                    "P3": "no Xe-contingency wording and no Xe heat term",
                    "P4": "no Xe-contingency wording; Xe+ stays a sputter species because Xe is RFP-required"}
A915_APPLIED = {"RFQ": "RFQ3-GAS-N03 / RFQ3-GAS-N04, NIR-07: system Xe capability for both configurations, C1 Xe "
                       "lines only for a selected C1 needing Xe, ICP getter an engineering / vendor requirement",
                "MASS_POWER_V3": "propellant_policy; C1 Xe branch neither assumed nor excluded (AL-08)",
                "XE_V3": "propellant_policy; RA-FUNC APPLIES; Xe-free reading retired; XV2Q-01 NOT_APPLICABLE"}

# integration artifacts (this lane) and the key of their owner-answer rows
INTEGRATION = {
    "docs/budgets/owner_decisions/owner_questions_state_v5.json": None,
    "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json": "a9_16_owner_answers_applied",
    "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json": "a9_16_owner_answers_applied",
    "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json": "owner_answers_applied",
    "docs/requirements/rvm_a9/rvm_a9_v1.json": "a9_16_owner_answers_applied",
    "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json": "a9_16_owner_answers_applied",
}

# A9.13 decisions whose application changes design-synthesis / optimizer / production-path code (step 3)
STEP3 = {
    "F1Q-02": "F1 intake synthesis: budgeting-assumption labels, sourced structure before LOCK-1",
    "F1Q-03": "F1 / intake-surface v2 domain over the registered AOCS pointing envelope",
    "F2-OQ-01": "F2 filter stage: baseline protection functions and pre-registered acceptance fields",
    "F2-OQ-02": "F2 concept list: catalytic O->O2 element as a separate research variant",
    "F2-OQ-03": "F2 / F7 contexts: FC-00 'none' as a reference bound only",
    "OQ-F3-02": "F3 compressor geometry: explicit hub ratio / blade span",
    "OQ-F3-03": "F3: transitional-regime model in parallel; NOT_EVALUATED_OUT_OF_DOMAIN above 0.1 Pa",
    "OQ-F3-04": "F3 search: Al / CFRP re-admitted only through the S2.3 strength-basis gate",
    "OQ-F4-01": "F4 plenum control: scheduled setpoint baseline, fixed setpoint fallback",
    "OQ-F4-02": "F4: higher-pressure compression as the primary direction",
    "OQ-F4-04": "F4 / F7: flow-gap levers in the owner order (no requirement relaxation)",
    "OQ-F4-05": "orbit-resolved frozen atmosphere dataset (rule-1 versioned build) and its use in F4 / F7",
    # A9.16 repair F7: only a state-v5 row / F9 annotation exists; the F4 / F7-F8 records that hold these decisions are
    # not rebuilt (CPU limit) - not APPLIED
    "OQ-F4-03": "F4 transient metrics accepted provisionally: annotation of the F4 record (F-lane regeneration)",
    "OQ-F78-02": "F7 / F8: all admitted scenarios carried: annotation of the F7 / F8 records (F-lane regeneration)",
    "OQ-F78-01": "F7 / F8: HC-08 hard statewise T - D >= 0",
    "OQ-F78-03": "F7 / F8: ripple as a hard feed-quality constraint; Pareto (no weighted scalar)",
    "OQ-F78-04": "F7 / F8: REFERENCE/PARAMETRIC sourced spacecraft geometry for interim drag studies",
    "UPSTREAM_ICD-Q1": "filter as a separate production-path element between IF-A1 and IF-A2",
    "F9-OQ-02": "F4 / F7: AG-12 feed-state constraint in the upstream evaluation (F9-ID-09)",
}
CPU_BLOCKED = ("F-lane records F1 / F4 / F7-F8 not rebuilt: their builders exceed the 2-minute command limit of this "
               "step (pins verified unchanged); annotation of their open_owner_questions is part of the step-3 F-lane "
               "regeneration")

# residual items (status, what, where)
RESIDUAL = {
    "OQ-A907-03": [("BLOCKED", "A9-07 uncoupled thermal rerun bounding corners", "docs/hardware/h2_a9_revisions/** "
                    "(outside the allowed paths)")],
    "OQ-A907-05": [("BLOCKED", "provisional BN / ceramic-wire limits in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/** (outside the allowed paths)")],
    "OQ-A907-06": [("BLOCKED", "mount-heat levers (50 W governing) in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/** (outside the allowed paths)")],
    "OQ-A907-08": [("BLOCKED", "coating limit in the A9-07 revisions", "docs/hardware/h2_a9_revisions/**")],
    "OQ-A907-09": [("BLOCKED", "environmental margin in the A9-07 revisions", "docs/hardware/h2_a9_revisions/**")],
    "OQ-A907-10": [("BLOCKED", "search allowance / SEARCH_SENSITIVE flag in the A9-07 revisions",
                    "docs/hardware/h2_a9_revisions/**")],
    "ICPQ-10": [("PENDING_EVIDENCE", "Q_ICP,bound value needs the registered P_fwd,max (complete P2 envelope) and "
                 "the registered H-1 P_d,max (form decided; RC-HEAT TBD_AFTER_EVIDENCE)",
                 "docs/experiments/hall_icp/p2_impedance_map/, p3_coupled_thermal/")],
    "F5-OQ-02": [("PENDING_EVIDENCE", "the engineering channel point itself is not yet selected: H1F-CH-11 "
                  "NOT_SELECTED_PENDING_FEMM (the non-performance selection rule and the ENGINEERING_FREEZE_CANDIDATE "
                  "label are recorded)", "docs/hardware/h1_freeze_candidate/ (after the authorised FEMM analysis "
                                         "points, F5-OQ-01)")],
    "P4-OQ-02": [("BLOCKED", "XL-27 pair text 'coupon shortlist TBD_OWNER P4 IT-17' must stay identical with RFQ v2 "
                  "IFD-17", "docs/procurement/rfq_a9_v2/ (immutable v2; outside the allowed paths)")],
    "F2-OQ-04": [("PENDING_STEP_3_ARCHITECTURE", "F2 lane F2-IF-08 status 'TBD_OWNER (F2-OQ-04)' stale",
                  "docs/design_synthesis/f2_filter/ (F-lane regeneration, step 3)")],
    "OQ-F4-03": [("BLOCKED", "F4 record annotation (provisional metric acceptance)", CPU_BLOCKED)],
    "OQ-F78-02": [("BLOCKED", "F7 / F8 record annotation (all admitted scenarios)", CPU_BLOCKED)],
    "OQ-F78-04": [("BLOCKED", "F7 / F8 not regenerated in the repair lane (COR-04): its pins to F6 / H-1 / F4 are stale",
                   CPU_BLOCKED)],
    "MQ-06": [("OPEN_OWNER_QUESTION", "controls-line allocation after the split: MPV3Q-01 (TBD_OWNER in state v5)",
               "docs/budgets/mass_power_a9_v3/")],
    "OQ-A907-07": [("PENDING_EVIDENCE", "flight C1 BOM / C1 Xe lines wait for C1 selection (not assumed, not excluded)",
                    "docs/budgets/mass_power_a9_v3/, docs/budgets/xe_accounting_a9_v3/")],
    "MPQ-01": [("PENDING_EVIDENCE", "AL-C1 = 1.20 x selected C1 CBE only once C1 is selected",
                "docs/budgets/mass_power_a9_v3/")],
    "F9-OQ-03": [("BLOCKED", "AG-15 closure: the official RFP is not registered in the repository (owner-held)",
                  "evidence registration of the RFP (owner act)")],
    "OD12": [("BLOCKED", "RFP clauses owner-stated; requirement_frozen stays false until AG-15", "RFP registration")],
    "OD3": [("PENDING_EVIDENCE", "design atmosphere states wait for the orbit-resolved dataset build (A9.13 OQ-F4-05)",
             "abep_sim/data/ (rule-1 versioned build; not this step)")],
    "M16-V3-Q-01": [("PENDING_EVIDENCE", "named persons from the project staffing ledger (none in the repository; none "
                     "fabricated)", "staffing ledger (owner)"),
                    ("PENDING_STEP_3_ARCHITECTURE", "re-derivation of M16 scheduler blocking items from the A9.8 .. "
                     "A9.15 answers (M16 v5 refresh)", "docs/experiments/hall_icp/integration/")],
}
NOT_APPLICABLE = {
    "OQ-A910-02": "the producing stage and decision quantity are assigned at LOCK-1 from the frozen A9-01 stage map and "
                  "the decision-quantity consumer table; no assignment is inferred now to eliminate a TBD (registered "
                  "in state v5)",
}
SPECIAL = {
    "F0-OQ-01": ("BLOCKED", "thresholds (60 s / 10 s) already the preregistered values of scripts/perf/profile_baseline.py; "
                 "the owner acceptance cannot be recorded in docs/performance/** (pins only; the baseline JSON is "
                 "pinned by the parity pre-registration) nor in scripts/perf/** (outside the allowed paths); the "
                 "baseline is CURRENT again (A9.16 repair COR-05: the profiled P3 builder is byte-identical to the "
                 "measured source; A9.16 P3 changes live in build_p3_coupled_thermal_v2.py)"),
    "F5-OQ-02": ("PARTIAL", "selection rule recorded (non-performance criteria, ENGINEERING_FREEZE_CANDIDATE); the "
                 "engineering channel point is not yet selected (H1F-CH-11 NOT_SELECTED_PENDING_FEMM) - A9.16 repair F7"),
    "F0-OQ-02": ("BLOCKED", "dedicated unloaded-machine re-measurement (CPU, OS, Python, toolchain, thermal / power, "
                 "threads, workload hash) is an owner-machine action (A9.17); existing ADMITTED verdicts stay "
                 "parity-only; not recordable in docs/performance/** in this step (pins only)"),
    "RUST-OQ-02": ("PENDING_CI_CHANGE", "optional Rust CI job with mandatory parity on Rust changes needs "
                   ".github/workflows/**, outside the allowed paths"),
}
RULES = [
    {"id": "R-RUST-OQ-01", "decision": None, "rule": "Python is authoritative for frozen and score-bearing outputs: "
     "frozen datasets, golden / reference rebuilds and score-bearing evidence are produced or independently reproduced "
     "by the Python reference; an admitted Rust kernel may accelerate exploration, CI parity and non-authoritative runs",
     "application": "abep_sim/design/tpmc_backend.py has no frozen-data or score-bearing path (default backend python; "
                    "not wired into the intake-surface build, goldens or scoring), so no refusal code is added: editing "
                    "the wrapper would also change the parity-report build provenance and de-admit the kernels "
                    "(RUST-OQ-02). Guarded by tests/test_decision_application_a9_16.py::"
                    "test_frozen_and_score_bearing_paths_never_use_rust",
     "status": "APPLIED"},
    {"id": "R-RFP", "decision": None, "rule": L.RFP_PENDING_NOTE, "status": "APPLIED",
     "application": "state v5 rows, F9 / RVM records carry rfp_citation_status"},
    {"id": "R-A915", "decision": None, "rule": L.a915_governing_statement(), "status": "APPLIED",
     "application": "A9.15 governs every 'Xe contingency-only for C1' reading; the A9.1 ICP gas-mode baseline (G-REUSE "
                    "primary, G-XE a declared ICP-feed variant) is unchanged"},
]


EXTRA_APPS = {
    "RUST-OQ-01": [{"lane": "INTEGRATION", "artifact": "tests/test_decision_application_a9_16.py",
                    "commit": INTEGRATION_COMMITS["records"], "status": "APPLIED",
                    "record_locations": ["test_frozen_and_score_bearing_paths_never_use_rust"],
                    "what": "rule R-RUST-OQ-01 recorded here; guard test: no frozen / golden / score-bearing path imports "
                            "tpmc_backend or abep_core; tpmc_backend default backend python (no frozen-data path exists "
                            "in tpmc_backend, so no refusal code is added)"}],
}


def _qid_re(qid):
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(qid) + r"(?![0-9A-Za-z])")


def _locations(doc, qid, limit=4):
    pat = _qid_re(qid)
    out = []

    def walk(o, p):
        if len(out) >= limit:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{p}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}/{i}")
        elif isinstance(o, str) and pat.search(o):
            out.append(p)
    walk(doc, "")
    return out


def repair_applications():
    apps = {}
    for qid, art, what in REPAIR:
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        locs = _locations(doc, qid)
        if not locs:
            raise SystemExit(f"REPAIR: question id {qid} not found in {art} (repair application not verifiable)")
        apps.setdefault(qid, []).append({"lane": "REPAIR", "artifact": art, "commit": REPAIR_COMMIT,
                                         "status": "APPLIED", "record_locations": locs, "what": what})
    return apps


def lane_applications():
    apps = {}
    for lane, (commit, art, qids) in LANES.items():
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        for q in qids:
            locs = _locations(doc, q)
            if not locs:
                raise SystemExit(f"{lane}: question id {q} not found in {art} (lane result not verifiable)")
            apps.setdefault(q, []).append({"lane": lane, "artifact": art, "commit": commit, "status": "APPLIED",
                                           "record_locations": locs})
    return apps


def integration_applications():
    apps, a915 = {}, []
    commit = INTEGRATION_COMMITS["records"]
    for art, key in INTEGRATION.items():
        doc = json.loads((ROOT / art).read_text(encoding="utf-8"))
        if key is None:     # state v5: one registered row per answered question
            for i, r in enumerate(doc["rows"]):
                if r.get("answer_decision"):
                    apps.setdefault(r["id"], []).append({
                        "lane": "INTEGRATION", "artifact": art, "commit": commit, "status": "APPLIED",
                        "record_locations": [f"/rows/{i}"], "what": f"state v5 row {r['status']}"})
            continue
        for i, row in enumerate(doc[key]):
            if "question_id" not in row:
                continue
            if row["decision"] == "A9.15":
                a915.append({"lane": "INTEGRATION", "artifact": art, "commit": commit,
                             "status": "NOT_APPLICABLE_TO_ARTIFACTS" if row["how_applied"].startswith("reviewed")
                             else "APPLIED", "record_locations": [f"/{key}/{i}"], "what": row["how_applied"]})
                continue
            apps.setdefault(row["question_id"], []).append({
                "lane": "INTEGRATION", "artifact": art, "commit": commit, "status": "APPLIED",
                "record_locations": [f"/{key}/{i}"] + [r for r in row["record_ids"]][:4], "what": row["how_applied"]})
    return apps, a915


def overall(key, qid, applied):
    if qid in SPECIAL:
        return SPECIAL[qid][0], SPECIAL[qid][1]
    if key == "A9.9":
        return "PENDING_STEP_2_MODEL_CHANGE", "A9.9 production-model change (authorised; A9.16 step 2)"
    if qid in STEP3:
        return "PENDING_STEP_3_ARCHITECTURE", STEP3[qid]
    if qid in NOT_APPLICABLE:
        return "NOT_APPLICABLE_TO_ARTIFACTS", NOT_APPLICABLE[qid]
    governing = [a for a in applied if a["artifact"] != "docs/budgets/owner_decisions/owner_questions_state_v5.json"]
    if governing:
        return "APPLIED", None
    return "BLOCKED", "no governing artifact application"


def build():
    lane = lane_applications()
    rep = repair_applications()
    integ, a915_integ = integration_applications()
    entries = []
    for key in L.ORDER:
        if key == "A9.15":
            continue
        for qid in L.decision_ids(key):
            a = L.answer(qid)
            applied = lane.get(qid, []) + rep.get(qid, []) + integ.get(qid, []) + EXTRA_APPS.get(qid, [])
            st, reason = overall(key, qid, applied)
            e = {"decision": key, "question_id": qid, "sequenced_no": a["sequenced_no"],
                 "decision_code": a["decision_code"], "decision_json": a["decision_json"],
                 "decision_json_sha256": a["decision_json_sha256"], "status": st}
            if reason:
                e["status_reason"] = reason
            if "amended_by" in a:
                e["amended_by_a9_15"] = a["amended_by"]["verbatim_excerpt"]
            if a["rfp_citation_status"]:
                e["rfp_citation_status"] = a["rfp_citation_status"]
            e["applications"] = applied
            e["residual"] = [{"status": s, "what": w, "where": wh} for s, w, wh in RESIDUAL.get(qid, [])]
            if qid in STEP3 and key == "A9.13":
                e["residual"].append({"status": "PENDING_STEP_3_ARCHITECTURE", "what": STEP3[qid],
                                      "where": "design-synthesis / optimizer code (A9.16 step 3)"})
            if key == "A9.9":
                e["residual"].append({"status": "PENDING_STEP_2_MODEL_CHANGE", "what": "controlled production-model "
                                      "change with regression tests, goldens and docs/HISTORY.md entry",
                                      "where": "abep_sim/ (A9.16 step 2)"})
            entries.append(e)
    a15 = L.LOADED["A9.15"]
    a915_apps = [{"lane": ln, "artifact": LANES[ln][1], "commit": LANES[ln][0], "status": "APPLIED",
                  "record_locations": _locations(json.loads((ROOT / LANES[ln][1]).read_text(encoding="utf-8")),
                                                 "A9.15"), "what": w} for ln, w in A915_APPLIED.items()]
    a915_apps += [{"lane": ln, "artifact": LANES[ln][1], "commit": LANES[ln][0], "status": "NOT_APPLICABLE_TO_ARTIFACTS",
                   "what": w} for ln, w in A915_REVIEWED_NA.items()]
    a915_apps += a915_integ
    for x in a915_apps:
        if x["status"] == "APPLIED" and not x.get("record_locations"):
            raise SystemExit(f"A9.15 application in {x['artifact']} has no locatable record")
    entries.append({"decision": "A9.15", "question_id": "A9.15 governing_rule", "sequenced_no": None,
                    "decision_code": a15["doc"]["decision"], "decision_json": a15["json"],
                    "decision_json_sha256": a15["json_sha256"], "status": "APPLIED",
                    "amends": list(L.A915_AMENDED) + ["A9.13 owner_statements.xenon"],
                    "rfp_citation_status": L.RFP_PENDING, "applications": a915_apps,
                    "residual": [{"status": "BLOCKED", "what": "RFP clauses (two separate propellant tanks, air + Xe "
                                  "compatibility) are owner-stated; registration of the RFP (AG-15) pending",
                                  "where": "RFP registration (owner act)"}]})
    counts, rcounts = {}, {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
        for r in e["residual"]:
            rcounts[r["status"]] = rcounts.get(r["status"], 0) + 1
    ids_by_dec = {k: len(L.decision_ids(k)) for k in L.ORDER if k != "A9.15"}
    return {
        "schema": "a9_16_application_matrix_v1", "id": "a9_16_application_matrix_v1",
        "lane": "A9.16 step 1 integration", "date": "2026-10-01",
        "generated_by": "docs/decisions/application/build_a9_16_application_matrix.py",
        "companion_document": REL(OUT_MD), "test": "tests/test_decision_application_a9_16.py",
        "status_vocabulary": STATUSES, "residual_status_vocabulary": list(RESIDUAL_STATUSES),
        "rule": "one entry per decision id of A9.8 .. A9.14 plus the A9.15 governing rule; the verbatim .md governs; "
                "statuses never PASS; an application is listed only when its question id is locatable in the artifact",
        "pins": L.pins(),
        "integration_commits": INTEGRATION_COMMITS,
        "repair_commit": REPAIR_COMMIT,
        "repair_fixes": REPAIR_FIXES,
        "lane_commits": {k: v[0] for k, v in LANES.items()},
        "decision_id_counts": ids_by_dec,
        "counts": dict(sorted(counts.items())),
        "residual_counts": dict(sorted(rcounts.items())),
        "rules": RULES,
        "entries": entries,
        "superseded_statements": [{"id": "A9.13 owner_statements.xenon",
                                   "text": L.LOADED["A9.13"]["doc"]["owner_statements"]["xenon"],
                                   "superseded_by": "A9.15 governing_rule"}],
        "builders_check_summary": "A9.16 repair lane: state v4, RFQ v2, mass-power v2, Xe v2 and the F0 performance "
                                  "baseline --check reproduce again (COR-01 / 02 / 05); P1, P2, P3 v1 + v2, P4, RVM, "
                                  "mass-power v3, Xe v3, RFQ v3, state v5, M16 v4, H-1, F9 rebuilt; F4 regenerated "
                                  "(COR-03); F7 / F8 not regenerated (COR-04: the build did not finish inside the "
                                  "2-minute command limit) - its pins to F6 / H-1 / F4 stay stale and "
                                  "tests/test_design_f7_f8_optimizer.py::test_pins_hold stays red until a run "
                                  "without that limit",
    }


def _c(s):
    return " ".join(str(s).split()).replace("|", "\\|")


def render_md(doc):
    out = ["# A9.16 decision-application matrix", "",
           f"Generated by `{doc['generated_by']}` (do not edit by hand; `--check` verifies). {doc['rule']}.", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + ". Residual items: "
           + ", ".join(f"{k} {v}" for k, v in doc["residual_counts"].items()) + ".", "",
           "Integration commits: " + ", ".join(f"{k} `{v}`" for k, v in doc["integration_commits"].items())
           + ". Lane commits: " + ", ".join(f"{k} `{v[:7]}`" for k, v in doc["lane_commits"].items()) + ".", "",
           "## Rules recorded", ""]
    out += [f"- **{r['id']}** ({r['status']}): {_c(r['rule'])} - {_c(r['application'])}" for r in doc["rules"]]
    out += ["", "## Entries", "", "| decision | id | seq | code | status | applied in (lane: artifact @ commit) | residual |",
            "|---|---|---|---|---|---|---|"]
    for e in doc["entries"]:
        apps = "; ".join(f"{a['lane']}: {a['artifact'].rsplit('/', 1)[-1]} @ {a['commit'][:7]}"
                         + ("" if a["status"] == "APPLIED" else f" ({a['status']})") for a in e["applications"])
        res = "; ".join(f"{r['status']}: {r['what']}" for r in e["residual"])
        st = e["status"] + (f" - {e['status_reason']}" if e.get("status_reason") else "")
        out.append(f"| {e['decision']} | {e['question_id']} | {e['sequenced_no'] or '-'} | {e['decision_code']} | "
                   f"{_c(st)} | {_c(apps) or '-'} | {_c(res) or '-'} |")
    out += ["", "## Pins", ""] + [f"- `{p['path']}` sha256 `{p['sha256']}`" for p in doc["pins"]]
    out += ["", "No PASS; no question answered here; RFP-cited facts are OWNER_STATED_PENDING_RFP_REGISTRATION."]
    return "\n".join(out) + "\n"


def outputs(doc=None):
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc)}


def main():
    outs = outputs()
    if "--check" in sys.argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"A9.16 application matrix stale: {stale}")
        print("A9.16 application matrix: current")
        return
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    d = json.loads(outs[OUT_JSON])
    print("wrote A9.16 application matrix: " + json.dumps(d["counts"]))


if __name__ == "__main__":
    main()
