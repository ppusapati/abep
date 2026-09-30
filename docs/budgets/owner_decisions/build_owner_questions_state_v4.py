"""Owner-question state v4: state v3 + every question raised since v3 by the merged lanes, re-classified under A9.6.

Owner directive A9.6 (docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md) sec. 5-7 and sec. 18 ('no orphan
questions'). State v3 stays immutable (pinned by sha256 here); v4 is built from it as follows:

1. every v3 row is copied; rows that are not OPEN in v3 are copied unchanged;
2. every v3 OPEN row is re-classified into exactly one of ANSWERED_BY_A9_4 / ANSWERED_BY_A9_5 / DERIVED / TBD_OWNER /
   SUPERSEDED (A9.6 sec. 6-7). The v3 status is kept in 'v3_status';
3. every question raised since v3 by the merged lanes (P1, P2, P3, P4, mass/power v2, Xe accounting v2, RFQ v2), the
   P1 registration items P1-IT-52 / P1-IT-55, the A9.4 / A9.5 answers (P1Q-10/13/14, P2Q-05; P1Q-15/16) and the lane
   DERIVED settlements (P1 derived_resolutions, RFQ v2 closed_since_previous_revision) is added as a row with a
   resolvable source (path + locator). Lane packages are mutable deliverables: they are read and their ids checked,
   never sha-pinned; historical question texts that were removed from a lane package when answered are quoted from
   the git blob of an earlier commit and pinned by the sha256 of that blob.

Every TBD_OWNER row carries the dependency that makes it a genuine owner question (A9.6 sec. 7) and what it blocks.
Nothing is answered here: DERIVED rows name the owner decision / standard rule they follow from and the artifact that
implements them; when in doubt a row stays TBD_OWNER. Missing or unexpected ids raise; there are no defaults.

stdlib only.

    python docs/budgets/owner_decisions/build_owner_questions_state_v4.py          # write JSON + MD + CSV
    python docs/budgets/owner_decisions/build_owner_questions_state_v4.py --check  # verify outputs are current
"""
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REL = lambda p: p.relative_to(ROOT).as_posix()

V3 = HERE / "owner_questions_state_v3.json"
DEC = ROOT / "docs/decisions"
A94 = DEC / "OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"
A94_MD = DEC / "OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"
A95 = DEC / "OD_2026_09_30_A9_5_p1_closure_owner_decisions.json"
A95_MD = DEC / "OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md"
A96 = DEC / "OD_2026_09_30_A9_6_implementation_first_directive.json"
A96_MD = DEC / "OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"

P1 = ROOT / "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"
P2 = ROOT / "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"
P3 = ROOT / "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json"
P4 = ROOT / "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json"
MP = ROOT / "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json"
XV2 = ROOT / "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json"
RFQV2 = ROOT / "docs/procurement/rfq_a9_v2/rfq_a9_v2.json"
A910 = ROOT / "docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json"
# register completion (lane A9_6_M16, fo_a9_6_m16_refresh; RVM interface demands RVM-ID-10 / RVM-ID-11)
HGM = ROOT / "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"  # historical lane-24 matrix (immutable)
HGM_SHA = "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f"
ANS = DEC / "OD_2026_09_29_owner_answers_147.json"
ANS_SHA = "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"
RVM = ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json"  # mutable deliverable: read, ids checked, never pinned

OUT_JSON = HERE / "owner_questions_state_v4.json"
OUT_MD = HERE / "OWNER_QUESTIONS_STATE_v4.md"
OUT_CSV = HERE / "owner_questions_state_v4.csv"

# ----------------------------------------------------------------------------------------------------------------------
# closed vocabularies
# ----------------------------------------------------------------------------------------------------------------------
NEW_STATUSES = {
    "ANSWERED_BY_A9_4": "answered by an A9.4 owner decision (docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json)",
    "ANSWERED_BY_A9_5": "answered by an A9.5 owner decision (docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json)",
    "DERIVED": "A9.6 sec. 6: a consequence of an existing owner decision, a mechanical / bookkeeping / schema / status "
               "propagation or a standard derived rule; 'derived_rule' cites the decision or rule and 'implemented_in' "
               "names the artifact that implements it (the owner may reopen it)",
    "TBD_OWNER": "A9.6 sec. 7: a genuine design / architecture / policy choice or a value that depends on evidence not yet "
                 "available; 'dependency' says which, 'blocks' says what it blocks; admissible alternatives are carried",
}
REUSED_STATUS = {"SUPERSEDED"}  # already in the v3 vocabulary; for a v4 re-classification 'superseded_by' is required
RECLASS_STATUSES = set(NEW_STATUSES) | REUSED_STATUS

DEPENDENCIES = {
    "OWNER_JUDGMENT": "a genuine design / architecture / policy / organisational choice (A9.6 sec. 7)",
    "P1_DATA": "depends on P1 measured data",
    "P2_IMPEDANCE_DATA": "depends on P2 ICP antenna impedance-map data",
    "MEASURED_H1_DISCHARGE_CURRENT": "depends on the measured / registered H-1 discharge current (I_d,max,H1)",
    "VENDOR_QUOTATIONS": "depends on vendor quotations, datasheets or ratings",
    "MATERIAL_DATA": "depends on selected / validated material data",
    "MEASURED_THERMAL_COUPLING": "depends on measured thermal coupling",
    "FACILITY_CAPABILITY": "depends on facility / laboratory capability",
    "OFFICIAL_RFP_TEXT": "depends on the reading of the canonical RFP document, which is not in the repository (owner row "
                         "1: obtain it through the legitimate owner / portal route; do not freeze ambiguous RFP "
                         "interpretations from secondary sources)",
}
BLOCKS = {
    "BLOCKS_P1_START": "needed at or before P1-G0 (incl. dispatch of P1_NEEDED RFQ lines)",
    "BLOCKS_P1_LATER_STAGE": "needed at the entry of a later P1 stage (named in 'blocks_stage'); does not block P1-G0",
    "BLOCKS_P2": "needed before the P2 impedance map / a P2 point",
    "BLOCKS_P3_P4": "needed by the P3 coupled-thermal or P4 anode/materials closure path",
    "BLOCKS_LOCK_1": "needed by LOCK-1",
    "NOTHING_IMMEDIATE": "needed later (LOCK-2, after the complete P2 map, before a reverification, before an M16 row "
                         "becomes READY); does not block P1, P2, P3/P4 or LOCK-1",
}
GROUP_RELATIONS = {"SAME_QUESTION": "the members ask the same question in different lanes; one owner answer closes all",
                   "COUPLED": "the members are separate questions whose answers constrain each other; answer together"}

# ----------------------------------------------------------------------------------------------------------------------
# historical question texts (removed from a lane package when answered / settled); quoted verbatim from git blobs
# ----------------------------------------------------------------------------------------------------------------------
HIST_BLOBS = {
    "p1_at_434b366": {"commit": "434b36630932477f4a3382b7c5e012504e1d7b40",
                      "path": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
                      "sha256": "2602e1ee366d256029c404ba7156876af7a73d3c259f97b843eee1caf06f87bc",
                      "what": "P1 bench as merged after A9.3 (before A9.4)"},
    "p2_at_434b366": {"commit": "434b36630932477f4a3382b7c5e012504e1d7b40",
                      "path": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
                      "sha256": "c83dd7bc4e0f52adec58a8e73a8ce46783e103f8beab3d8b849d678aa99b4bf3",
                      "what": "P2 impedance prep as merged after A9.3 (before A9.4)"},
    "p1_at_f7d945b": {"commit": "f7d945b521886b1f41f6291ef4bae99d274528f2",
                      "path": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
                      "sha256": "61fad7c2afcb4d3fad0e2f6493371e13ee9b744158d0a4e24ce86b0a3b231fba",
                      "what": "P1 bench after A9.4 (before A9.5)"},
    "p1_at_9374d44": {"commit": "9374d44893a7e075a0b1712dcd968c5dcff2b940",
                      "path": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
                      "sha256": "5b17278314061f12f8de3fa014335789a17ab515d8792a7142dd8bfdba063227",
                      "what": "P1 bench after A9.5 (before the A9.6 P1 workflow lane)"},
}

HISTORICAL_QUESTIONS = {
    'P1Q-10': {'blob': 'p1_at_434b366', 'question': 'Adopt the PROPOSED I_e,cap definition for the ICP-45A engineering evaluation (P1-IT-38): I_e,cap as a CAPACITY measurement = maximum facility-corrected extracted current in the registered extraction topology (discharge supply OFF, electrons to the registered electron-collecting electrode) at the gas/magnet conditions of registered H-1 points, with Hall-ON P1-S7 records used only as a descriptive neutralization-consistency check? (Alternative: a Hall-ON-based definition, which by current continuity can never exceed I_d and would need a different acceptance form.)',
             'proposed': "owner call; PROPOSED: adopt the capacity-extraction form. Until adopted any EVALUATED_ENGINEERING_ONLY output carries the label 'I_e,cap definition PROPOSED'; with no eligible capacity record the reducer returns NOT_EVALUATED, never a FAIL", 'needed_by': 'P1-S7 entry'},
    'P1Q-13': {'blob': 'p1_at_434b366', 'question': 'Register the H-1 electrical configuration for the Hall-OFF stages (P1-S3..S5, P1-S7 capacity block): H-1 anode disconnected from the discharge-supply output and floating (V_anode recorded) or tied to the reference through a metered return; H-1 body / magnetic-circuit grounding (P1-IT-39)?',
             'proposed': 'owner call; PROPOSED: anode disconnected and floating with V_anode recorded (terminal OPEN_CIRCUIT_BY_CONSTRUCTION), metered return only as a registered diagnostic; an OFF supply output left connected is not used', 'needed_by': 'P1-G0'},
    'P1Q-14': {'blob': 'p1_at_434b366', 'question': 'Extend the row-81 350 V isolation class (plus transient/qualification margin) to the ICP body and collector circuits, which row 81 does not name, and set the P1-G0 insulation-resistance / hipot test voltage for the floating circuits?',
             'proposed': 'owner call; PROPOSED: yes, same class as the H-1 anode circuit they face; test voltage and margin owner call at P1-G0', 'needed_by': 'P1-G0'},
    'P2Q-05': {'blob': 'p2_at_434b366', 'question': 'Add an optical-emission photodiode as a mode-jump (E/H) indicator and as the unlit-verification indicator of the S-08 powered-unlit records?',
             'proposed': 'yes (PROPOSED; low-cost, independent of the RF chain; without it (or an equivalent independent indicator named by the owner) S-08 powered-unlit records cannot be reduced)', 'needed_by': 'LOCK-1'},
    'P1Q-15': {'blob': 'p1_at_f7d945b', 'question': "Register the Kirchhoff closure tolerance for ICP-45 capacity points (A9.4 P1Q-13: 'a large unexplained residual invalidates that capacity point') and the sign convention of the collector, body, anode, facility and ICP-body terms (P1-IT-47)?",
             'proposed': 'owner call on the value; PROPOSED: set from the combined channel resolutions measured in P1-S2/S3 before the first ICP45_CAPACITY record; sign convention = P1-IT-42 (conventional current into the isolated network positive)', 'needed_by': 'before the first ICP45_CAPACITY record (P1-G0)'},
    'P1Q-16': {'blob': 'p1_at_f7d945b', 'question': "Confirm the recorder reading of the incomplete A9.4 P1Q-10 'Define:' formula: I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (the verbatim text lacks 'I_e,cap =' and the minus sign)?",
             'proposed': "YES (consistent with the owner's 'matched RF-OFF measurements used to quantify facility/background electron current'; implemented as such)", 'needed_by': 'P1-S7 entry'},
    'P1Q-19': {'blob': 'p1_at_9374d44', 'question': "The margin rule's preregistered u_I_e_A (A9.1 UBQ-02 / UBQ-07) is kept as the I_e,cap uncertainty in M_n; the reducer also reports sqrt(u^2(I_col,RFON) + u^2(I_col,RFOFF)) from the channel uncertainties and flags REGISTERED_u_I_e_BELOW_CHANNEL_PROPAGATION when the registered value is smaller. Should the preregistration require u_I_e_A >= the channel-propagated value (or use the larger of the two)? Also: the reducer treats a registered u_I_e_A or u_I_d_max_A that is absent, None or 0 as 'not available' (A9.5 P1Q-16 condition 3 false -> ICP45 = NOT_EVALUATED), reading a zero standard uncertainty of a measured / registered current as no uncertainty statement. Confirm?",
             'proposed': 'owner call; PROPOSED: register u_I_e_A no smaller than the channel propagation (it then also covers any non-channel terms), frozen before the first P1-S7 point; YES to zero = not available', 'needed_by': 'P1-S7 entry'},
    'P1Q-21': {'blob': 'p1_at_9374d44', 'question': "A9.4 P1Q-13 says an ICP45_CAPACITY record whose H-1 anode is not physically disconnected / floating is 'refused, never merely flagged'; A9.5 P1Q-15 lists the same case as an exclusion whose point 'remains in the raw record with the exclusion reason'. Recorder reading implemented: A9.5 (the later owner decision) governs - the point is excluded with its reason, never admitted, and the other points of the bundle are still evaluated; non-capacity records keep the A9.4 refusal of an OFF supply left connected. Confirm?",
             'proposed': 'YES (the point can never feed I_e,cap either way; the exclusion keeps the raw record and does not abort the other points)', 'needed_by': 'before the first ICP45_CAPACITY record (P1-G0)'},
    'P1Q-22': {'blob': 'p1_at_9374d44', 'question': 'Outcome precedence at a capacity point that is instrument-inadequate (3 u_R > 0.02 I_e,collector) and also fails the statistical or fractional closure. Recorder reading implemented: structural exclusions first (pairing, anode, unmeasured return path, ground path, sign convention, missing u(I_k), mixed evidence); otherwise NOT_EVALUATED_INSTRUMENT takes precedence over the closure-test failure, which is kept as closure_test_results_not_decisive (when the instrument cannot resolve 2 %, a fractional failure is expected and should not point the laboratory at a ground-path problem). Confirm?',
             'proposed': 'YES', 'needed_by': 'before the first ICP45_CAPACITY record (P1-G0)'},
    'P1Q-23': {'blob': 'p1_at_9374d44', 'question': 'Two uncertainty combinations are lane choices, not owner text: (a) u(I_k) = root-sum-square of the five listed components (calibration, zero/offset, resolution, repeatability where applicable, registered RF-pickup) (P1-D-14); (b) the reported u(I_e,cap)_channels = sqrt(u^2(I_col,RFON) + u^2(I_col,RFOFF)) treats the RF-ON and RF-OFF readings of the same collector channel as independent, although their calibration terms are largely common-mode (P1-D-15; reported only, never used in M_n). Adopt, or register other forms (e.g. a registered RF-ON / RF-OFF correlation)?',
             'proposed': 'owner call; PROPOSED: (a) YES (GUM-style combination of independent components); (b) register the RF-ON / RF-OFF correlation of the collector channel with the channel calibration before the first P1-S7 point and use the correlated form', 'needed_by': 'P1-S7 entry'},
}

# ----------------------------------------------------------------------------------------------------------------------
# lane sources: every question container of every merged lane; each enumerated id must be classified below
# ----------------------------------------------------------------------------------------------------------------------
LANES = [
    # (lane label, path, container locator, row kind)
    ("P1 (fo_a9_6_p1_workflow_completion)", P1, "open_owner_questions", "lane_question"),
    ("P1 (fo_a9_6_p1_workflow_completion)", P1, "a9_6_incorporation.derived_resolutions", "lane_derived_resolution"),
    ("P2 (fo_a9_6_p2_framework_completion)", P2, "open_owner_questions", "lane_question"),
    ("P3 (fo_a9_6_p3_coupled_thermal)", P3, "open_owner_questions", "lane_question"),
    ("P4 (fo_a9_6_p4_anode_materials)", P4, "open_owner_questions", "lane_question"),
    ("mass/power v2 (fo_a9_6_mass_power_integration)", MP, "open_owner_questions", "lane_question"),
    ("Xe accounting v2 (fo_a9_6_xe_accounting)", XV2, "open_owner_questions", "lane_question"),
    ("RFQ v2 (fo_a9_6_rfq_completion)", RFQV2, "open_owner_questions.new", "lane_question"),
    ("RFQ v2 (fo_a9_6_rfq_completion)", RFQV2, "open_owner_questions.closed_since_previous_revision",
     "lane_closed_question"),
]
# P1 registration items raised as owner registrations (task scope: P1-IT-52 / P1-IT-55)
P1_REGISTRATIONS = ["P1-IT-52", "P1-IT-55"]
# answered by A9.4 / A9.5 (question text from HISTORICAL_QUESTIONS; lane locator where the lane records the application)
ANSWERED = {
    "P1Q-10": ("ANSWERED_BY_A9_4", A94, "definition_recorder_reading", P1, "owner_answers_applied[id=A9.4 P1Q-10]"),
    "P1Q-13": ("ANSWERED_BY_A9_4", A94, "anode", P1, "owner_answers_applied[id=A9.4 P1Q-13]"),
    "P1Q-14": ("ANSWERED_BY_A9_4", A94, "class", P1, "owner_answers_applied[id=A9.4 P1Q-14]"),
    "P2Q-05": ("ANSWERED_BY_A9_4", A94, "roles", P2, "a9_4_incorporation.answered.P2Q-05"),
    "P1Q-15": ("ANSWERED_BY_A9_5", A95, "residual", P1, "owner_answers_applied[id=A9.5 P1Q-15]"),
    "P1Q-16": ("ANSWERED_BY_A9_5", A95, "formula", P1, "owner_answers_applied[id=A9.5 P1Q-16]"),
}
# ids the task names explicitly; the builder raises when one is not produced
EXPECTED_NEW = (["P1Q-%02d" % i for i in range(1, 21) if i != 19] + ["P1Q-19", "P1Q-19 (ext)", "P1Q-19 (below propagation)",
                "P1Q-21", "P1Q-22", "P1Q-23 (a)", "P1Q-23 (b)", "P1-IT-52", "P1-IT-55"]
                + ["P2Q-%02d" % i for i in range(1, 11)] + ["P3Q-01", "P3Q-02"] + ["P4-OQ-%02d" % i for i in range(1, 6)]
                + ["MPQ-01", "MPQ-02", "XV2Q-01"] + ["OQ-RFQV2-%02d" % i for i in range(1, 11)])

A96_S6 = "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md sec. 6"
A96_S7 = "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md sec. 7"

# ----------------------------------------------------------------------------------------------------------------------
# DERIVED re-classifications of v3 OPEN rows and of RFQ v2 closed questions (each names its rule and implementing artifact)
# ----------------------------------------------------------------------------------------------------------------------
DERIVED_V3 = {
    "MQ-08": {
        "answer": "the verified H2-7 ID-11 arithmetic (3.5 + 0.974 + 0.57 = 5.044 kg low end, 5.044-12.77 kg) governs the "
                  "combined Xe analog floor; the A9 recorder flag (4.54-12.77 kg) stays immutable as recorded",
        "derived_rule": A96_S6 + " (mechanical cross-reference repair: an arithmetic reconciliation against a verified "
                        "deliverable; the immutable A9 file is not edited)",
        "implemented_in": ["docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json lines.*[AL-08].evidence_floor_kg / "
                           "floor_arithmetic (5.044 kg)",
                           "docs/procurement/rfq_a9_v2/rfq_a9_v2.json AL-08_evidence_floor_kg (5.044)"],
        "implemented_paths": ["docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
                              "docs/procurement/rfq_a9_v2/rfq_a9_v2.json"],
        "evidence_strings": {"docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json": "3.5 + 0.974 + 0.57 = 5.044"},
    },
    "OQ-INT-01": {
        "answer": "the UNMAPPED A9-04 ids (UB-DQ-*) stay measurement-chain ids; their relation to the A9-01 DQ-HI ids is "
                  "the explicit chain -> DQ-HI consumer table (ids kept, no id renamed)",
        "derived_rule": A96_S6 + " (schema propagation / bookkeeping: a cross-reference table between two id "
                        "systems; no physics value and no design choice)",
        "implemented_in": ["docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json dq_consumer_table"],
        "implemented_paths": ["docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json"],
        "evidence_strings": {"docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json": "dq_consumer_table"},
    },
    "OQ-INT-02": {
        "answer": "deliverables pin only acyclic dependencies (immutable inputs and upstream deliverables); a mutual "
                  "(circular) pin pair is replaced by id checks; governance files are never pinned",
        "derived_rule": A96_S6 + " (bookkeeping / builder integration) and sec. 18 ('no circular hash mistakes')",
        "implemented_in": ["commit 4d83d1c 'Integration: break circular P1/P2 <-> RFQ v2 sha pins (ids checked instead)'",
                           "docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py",
                           "docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py",
                           "docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py (deliverable_pins, never_pinned)"],
        "implemented_paths": ["docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py",
                              "docs/experiments/hall_icp/p2_impedance_map/build_p2_impedance_prep.py",
                              "docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py"],
        "evidence_strings": {"docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py": "deliverable_pins"},
    },
    "OQ-A910-04": {
        "answer": "the M16 v3 JSON stays at docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json "
                  "(the alternative requires editing the immutable H2-7 v1 builder)",
        "derived_rule": A96_S6 + " (bookkeeping: file location; historical artifacts stay immutable, A9.6 sec. 18 "
                        "'immutable historical artifacts unchanged')",
        "implemented_in": ["docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py -> "
                           "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"],
        "implemented_paths": ["docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py",
                              "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"],
        "evidence_strings": {"docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py": "m16_v3"},
    },
}
DERIVED_RFQV2_CLOSED = {
    "OQ-RFQV2-07": {
        "implemented_in": ["docs/procurement/rfq_a9_v2/rfq_a9_v2.json packages[RFQ2-HALLEL] line_items HE-L15 / HE-L16 / "
                           "HE-L17 (dispatch P1_NEEDED)"],
        "implemented_paths": ["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"],
        "evidence_strings": {"docs/procurement/rfq_a9_v2/rfq_a9_v2.json": "HE-L17"},
    },
}

# ----------------------------------------------------------------------------------------------------------------------
# TBD_OWNER classification: id -> (dependencies, blocks, blocks_stage or None, basis)
# ----------------------------------------------------------------------------------------------------------------------
LK, P3P4, P2B, P1S, P1L, NI = "BLOCKS_LOCK_1", "BLOCKS_P3_P4", "BLOCKS_P2", "BLOCKS_P1_START", "BLOCKS_P1_LATER_STAGE", "NOTHING_IMMEDIATE"
OJ, P1D, P2D, IDM, VQ, MD, MTC, FC = ("OWNER_JUDGMENT", "P1_DATA", "P2_IMPEDANCE_DATA", "MEASURED_H1_DISCHARGE_CURRENT",
                                      "VENDOR_QUOTATIONS", "MATERIAL_DATA", "MEASURED_THERMAL_COUPLING", "FACILITY_CAPABILITY")
RFP = "OFFICIAL_RFP_TEXT"
TBD = {
    # --- v3 OPEN rows ---
    "ICPQ-03": ([OJ, FC], [LK], None, "measured-system boundary on the thrust stand (architecture/measurement choice); P3 carries both mountings"),
    "ICPQ-08": ([FC, OJ], [LK], None, "depends on whether the gaussmeter is shown RF-immune (facility instrument capability)"),
    "ICPQ-09": ([OJ], [LK], None, "reporting-boundary choice; P3 computes Q_plume inside the boundary without choosing"),
    "ICPQ-10": ([P2D, OJ], [LK, P3P4], None, "P_fwd,max comes from the P2 impedance map; P3 carries both bounds (P3-B-01/02)"),
    "ICPQ-11": ([P2D, OJ], [LK], None, "k_RF is an owner margin applied to the P2 mismatch envelope (RF ratings TBD_AFTER_IMPEDANCE_MAP)"),
    "OQ-VI-04": ([OJ], [LK], None, "ICP lifetime / cycle requirement is a requirement-level owner choice; cycles need the mission mode profile"),
    "MQ-01": ([OJ], [LK], None, "allocation policy (MEV vs CBE level)"),
    "MQ-02": ([OJ], [LK], None, "allocation policy (reserve vs row-52 margin)"),
    "MQ-03": ([OJ], [LK], None, "re-allocation choice"),
    "MQ-04": ([OJ, VQ], [LK], None, "re-allocation choice; PPU mass from quotations"),
    "MQ-05": ([OJ, VQ], [LK], None, "re-allocation and scope choice; tank / regulator mass from quotations"),
    "MQ-06": ([OJ], [LK], None, "allocation-line structure; mass/power v2 keeps the v1 convention with MQ-06 OPEN"),
    "MQ-07": ([OJ], [LK], None, "allocation mapping (PROPOSED_MAPPING only)"),
    "MQ-09": ([OJ], [LK], None, "reading of owner row 48; carried both ways"),
    "MQ-10": ([OJ], [LK], None, "mass-closure strategy"),
    "OQ-A907-01": ([OJ], [LK], None, "reading of owner row 93; the Xe accounting v2 carries both readings (RA-DWELL)"),
    "OQ-A907-03": ([OJ, MTC], [LK, P3P4], None, "thermal verification method; measured deposition data replace analog ranges later"),
    "OQ-A907-04": ([OJ, VQ], [LK], None, "coil-conductor choice; perturbation needs measurement and wire quotation"),
    "OQ-A907-05": ([MD, OJ], [LK, P3P4], None, "provisional supplier ratings until qualification data exist"),
    "OQ-A907-06": ([OJ, MTC], [LK, P3P4], None, "spacecraft/PDR interface choice; P3 reports carrier / mount heat without choosing"),
    "OQ-A907-07": ([OJ], [LK], None, "architecture scheduling choice for the fallback flight C1"),
    "OQ-A907-08": ([MD], [LK, P3P4], None, "coating temperature capability not established (datasheet / coupon value needed)"),
    "OQ-A907-09": ([OJ], [LK, P3P4], None, "margin-policy reading of owner row 86"),
    "OQ-A907-10": ([OJ], [LK, P3P4], None, "verification-method policy (search allowance threshold)"),
    "XA9Q-01": ([OJ], [LK], None, "reading of owner row 48 (lane: NOW; the Xe accounting v2 carries both readings)"),
    "XA9Q-02": ([OJ], [NI], None, "reading of owner row 93; freeze at LOCK-2 (lane)"),
    "XA9Q-03": ([OJ, P1D], [LK], None, "booking convention until S1a demonstrates a flow class (lane: NOW; both readings carried)"),
    "XA9Q-04": ([OJ], [NI], None, "ground-test supply margin (LOCK-2)"),
    "XA9Q-05": ([VQ, OJ], [NI], None, "G-XE is diagnostic / contingency only (A9.6 sec. 5); purity need from the ICP vendor spec (after-evidence)"),
    "XA9Q-06": ([VQ], [LK], None, "MEOP chosen from quotations"),
    "XA9Q-07": ([OJ], [LK], None, "architecture reading of owner row 6 (lane: NOW; the Xe accounting v2 carries both readings)"),
    "OQ-RFQ-01": ([OJ], [LK], None, "spares policy"),
    "OQ-RFQ-03": ([OJ], [LK], None, "procurement timing choice"),
    "OQ-RFQ-04": ([VQ, OJ], [LK], None, "depends on the C1 vendor start procedure"),
    "OQ-RFQ-08": ([OJ], [LK], None, "procurement strategy choice"),
    "OQ-RFQ-09": ([VQ, OJ], [LK], None, "MEOP basis after quotations"),
    "OQ-A910-01": ([OJ], [LK], None, "one reading must govern both lanes (RA-CASE)"),
    "OQ-A910-02": ([OJ], [LK], None, "assignment of producing stage / decision quantity to 98 validation inputs is not implemented anywhere; kept TBD_OWNER (conservative)"),
    "OQ-A910-03": ([OJ], [LK], None, "gate-admission policy for peak-sampled ledgers"),
    "OQ-A910-05": ([OJ], [LK], None, "sham configuration and its allocation line; the match selection is itself open"),
    "OQ-A910-06": ([P2D, OJ], [LK, P3P4], None, "RF-path heat allocation until the P2 map gives the delivered / loss envelope"),
    "M16-V3-Q-01": ([OJ], [NI], None, "organisational: blocking items, role owners, responsible engineers (before any M16 row becomes READY)"),
    # --- P1 ---
    "P1Q-01": ([P1D, OJ], [P2B], None, "values set after the first P1-S5 dwells; needed for the P1-G5 -> P2 handoff"),
    "P1Q-02": ([FC, OJ], [P1L], "P1-S6", "Hall start-attempt limits inside the laboratory supply rating"),
    "P1Q-03": ([P1D, OJ], [P1L], "P1-S6", "definition uses the measured pickup floor (P1-M-22)"),
    "P1Q-04": ([OJ, MD], [P1S], None, "policy extension of A9.1 UBQ-06 to non-scoring operation; validated limit needs material data"),
    "P1Q-05": ([OJ], [P1L, P2B], "P1-S5", "minimum re-ignitions per surface point for the P2 handoff"),
    "P1Q-06": ([OJ], [P1L], "P1-S3", "magnet state factor; fringe field in the ICP volume not yet known"),
    "P1Q-07": ([IDM, OJ], [P1L], "P1-S7", "I_d,max,H1 never from the 8.33 A rating (A9.4 execution_decisions.i_d_max_h1); ICP45 NOT_EVALUATED until registered"),
    "P1Q-08": ([OJ], [P1L], "P1-S3", "envelope classification of the ICP-only stages"),
    "P1Q-09": ([OJ], [P1S], None, "collector geometry / position / V_collector reference; option (B) use for non-capacity records"),
    "P1Q-11": ([P1D, OJ], [P1S], None, "value from S2/S3 gauge repeatability; lane needed_by P1-G0"),
    "P1Q-12": ([OJ], [LK], None, "ICD revision scope"),
    "P1Q-17": ([OJ, VQ], [NI], None, "later reverification level (ECSS clause not identified - verify); before any reverification"),
    "P1Q-18": ([OJ], [P1S], None, "confirms the recorder reading of the A9.5 'candidate qualification point' scope; not settled by the lane"),
    "P1Q-19": ([OJ], [P1L], "P1-S7", "remaining preregistration choice REQUIRE_REGISTERED_GE_CHANNEL vs USE_LARGER_OF_REGISTERED_AND_CHANNEL (both computed)"),
    "P1Q-20": ([P1D, OJ], [P1S], None, "leakage recorded in the P1-S0 DWV test (P1-IT-44) vs u = 0 by construction"),
    "P1-IT-52": ([VQ, OJ], [P1S], None, "per-stage operating domains from procured ratings and the P1 run matrix; no default domain"),
    "P1-IT-55": ([VQ, OJ], [P1S], None, "leakage acceptance needs the insulation-path / feedthrough ratings; G0_NOT_EVALUATED_TBD until registered"),
    # --- P2 ---
    "P2Q-01": ([OJ], [LK, P2B], None, "primary Z_antenna method"),
    "P2Q-02": ([OJ], [P1S], None, "RFQ package placement of P1_NEEDED RF-metrology lines RF-L12..RF-L19 / RF-O01"),
    "P2Q-03": ([OJ], [LK, P2B], None, "agreement-rule form (k frozen at LOCK-1); no value proposed"),
    "P2Q-04": ([OJ], [LK, P2B], None, "hot-map tuning policy"),
    "P2Q-06": ([P2D, OJ], [LK], None, "conditional on the P2Q-03 bench agreement"),
    "P2Q-07": ([FC, OJ], [LK, P2B], None, "depends on whether an accredited 13.56 MHz V/I phase-calibration scope exists"),
    "P2Q-08": ([OJ], [P2B], None, "scope of the A9.3 ICPQ-06 isolator qualification (before the first biased / floating P2 point)"),
    "P2Q-09": ([OJ], [LK, P2B], None, "electrical-evidence rule for UNLIT -> UNCERTAIN (form at LOCK-1, multiple at LOCK-2)"),
    "P2Q-10": ([P2D, OJ], [NI], None, "rating margin per component class applied to the complete measured P2 envelope (after the P2 map)"),
    # --- P3 / P4 ---
    "P3Q-01": ([OJ], [P1S, P3P4], None, "probe diagnostic vs calorimetric Q_collector evidence (alternatives A/B/C)"),
    "P3Q-02": ([OJ], [LK, P3P4], None, "model class for the coupled thermal closure (alternatives A/B)"),
    "P4-OQ-01": ([OJ, MD], [P3P4], None, "evidence standard for T_validated,continuous"),
    "P4-OQ-02": ([OJ], [P3P4], None, "coupon shortlist"),
    "P4-OQ-03": ([OJ], [P3P4, LK], None, "pre-registered coupon acceptance thresholds"),
    "P4-OQ-04": ([OJ], [P3P4], None, "authorization of lawful acquisition of species-resolved sputtering data (an external commitment)"),
    "P4-OQ-05": ([OJ, P1D], [P3P4], None, "collector coupon bias polarity (one alternative defers to the P1 collector bias)"),
    # --- mass/power v2, Xe v2 ---
    "MPQ-01": ([OJ], [LK], None, "C1 allocation line for hall_c1_reference (options a/b/c carried)"),
    "MPQ-02": ([OJ], [LK], None, "allocation mapping of the A9.2-A9.6 lines (PROPOSED_MAPPING only)"),
    "XV2Q-01": ([OJ], [LK], None, "architecture reading conditional on XA9Q-07 (lane: with XA9Q-07, NOW)"),
    # --- RFQ v2 ---
    "OQ-RFQV2-01": ([OJ], [P1S], None, "certificate level for the Ar MFC (P1 RFQ dispatch)"),
    "OQ-RFQV2-02": ([FC], [P1S], None, "facility identification (P1 RFQ dispatch)"),
    "OQ-RFQV2-03": ([VQ, OJ], [P1S], None, "allowed if the supplier certifies both functions (P1 RFQ dispatch)"),
    "OQ-RFQV2-04": ([OJ], [P1S], None, "package placement of items outside the owner's six lists (dispatch of the affected package)"),
    "OQ-RFQV2-05": ([FC], [P1S], None, "availability of a laboratory magnet supply (P1 RFQ dispatch)"),
    "OQ-RFQV2-06": ([OJ], [P1S], None, "extension of the A9.4 P1Q-14 basis to the row-81 H-1 anode isolation (P1 RFQ dispatch)"),
    "OQ-RFQV2-08": ([OJ, FC], [P1S], None, "who performs the initial DWV (P1 RFQ dispatch)"),
    "OQ-RFQV2-09": ([OJ], [P1L], "P1-S6", "C1 hardware for P1-S6: advance to P1_NEEDED or run with C1 absent"),
    "OQ-RFQV2-10": ([OJ, VQ], [P1L], "P1-S3", "H-1 fabrication route (separate RFQ / RFQ2-MECH / in-house)"),
    # --- register completion: lane-24 open decisions carried by RVM rows (RVM-ID-11) and RVMQ-01 (RVM-ID-10) ---
    "OD2": ([RFP, OJ], [NI], None, "RFP reading of the quantifier over 180-230 km x atmosphere states (every point vs some "
                                   "altitude); owner row 1 forbids freezing it from secondary sources; RVM-01 carries both "
                                   "readings and is NOT_EVALUATED; needed before any requirement verdict (Milestone C), not "
                                   "by P1 / P2 / P3 / P4 / LOCK-1"),
    "OD3": ([OJ], [NI], None, "definition of the atmosphere design states (lane 24 used a PROPOSED low / mean / high set on "
                              "the frozen atmosphere dataset; never adopted by the owner); a design-basis choice for the "
                              "altitude verdict of RVM-01, not an input of the P1-P4 hardware stages"),
    "OD5": ([RFP, OJ], [NI], None, "whether an air-only start is required or a xenon-assisted start is acceptable; owner row "
                                   "24 already makes the experiments record start attempts per arm (air-only and Xe-assisted) "
                                   "and row 93 bounds the dwell, so both readings are measured; only the RVM-14 verdict waits"),
    "OD6": ([RFP, OJ], [NI], None, "residual of the 'air + Xe' meaning after owner row 6 (bounded functional Xe-capable mode "
                                   "required, not continuous): whether feed switching without extinction or a simultaneous "
                                   "mixed feed is also required; RVM-10 carries the readings side by side"),
    "OD12": ([RFP, OJ], [NI], None, "whether the recorded-but-ungated RFP statements (indigenous content, no single-point "
                                    "failure in electronics, 'ionise nascent O') become gates; owner rows 55 (limited "
                                    "redundancy), 102 / 132 (species measured, NO_ATOMIC_O) set policies without deciding "
                                    "the gate question; RVM-09 / -16 / -18 / -19 carry it"),
    "OD14": ([RFP, OJ], [NI], None, "whether ignition from the off state on atmospheric propellant is an RFP requirement "
                                    "(lane 24: inferred, no ignition / restart clause recorded); owner rows 24 / 108 / 112 "
                                    "set recording, start-up power and sequencing rules without deciding the requirement; RVM-14 "
                                    "carries it"),
    "RVMQ-01": ([RFP, OJ], [NI], None, "redundancy basis if the official RFP confirms 'no single-point failure in "
                                       "electronics' (row 55 limited redundancy vs re-basing RVM-19 on the RFP clause); "
                                       "genuine design choice (mass / power / FMEA); needed when the RFP is obtained, before "
                                       "Milestone C (RVM lane needed_by)"),
}

# register completion (lane A9_6_M16): lane-24 open decisions named by RVM-ID-11 and the RVM question named by RVM-ID-10.
# Each lane-24 decision is registered with its historical source (pinned matrix) and the RVM rows that carry it. A row is
# SUPERSEDED only where an owner answer answers the same question (quoted verbatim and sha-checked); every other row is
# TBD_OWNER (A9.6 sec. 7) and names the owner answers that bear on it without settling it.
LANE24_REGISTERED = ["OD2", "OD3", "OD5", "OD6", "OD12", "OD13", "OD14"]
RVM_QUESTIONS = ["RVMQ-01"]
RVM_DEMANDS = {"RVM-ID-10": RVM_QUESTIONS, "RVM-ID-11": LANE24_REGISTERED}
LANE24_SUPERSEDED = {
    "OD13": {
        "owner_row": 3,
        "how": "owner row 3 answers the same question ('is > 15,000 h firing in the RFP?'): retain > 15,000 h firing as a "
               "provisional hard requirement until the official RFP confirms it. The lane-24 option 'cumulative firing "
               "time' is therefore the governing engineering basis; what remains is verification of the wording against "
               "the canonical RFP, which is the owner action of row 1 (RVM-ID-12, AWAITING_OWNER_ACTION), not an open "
               "question. A different official wording would open a new question.",
        "implemented_in": ("RVM", "rows[id=RVM-12]"),
    },
}
LANE24_RELATED_ROWS = {  # owner answers that bear on a TBD_OWNER lane-24 decision without settling it (why not)
    "OD2": [(1, "orders the canonical RFP to be obtained and forbids freezing ambiguous readings; does not choose one")],
    "OD5": [(24, "records start attempts per arm (air-only and Xe-assisted); does not say which start the RFP requires"),
            (93, "bounds the C1 ignition dwell; says nothing on an air-only start requirement")],
    "OD6": [(6, "settles that a demonstrated bounded functional Xe-capable mode is required (beyond ignition, cathode and "
                "contingency); does not decide feed switching without extinction or a simultaneous mixed feed")],
    "OD12": [(55, "sets a limited-redundancy policy; does not decide whether the no-SPF statement is a gate (see RVMQ-01)"),
             (102, "delivered species measured, O survival never assumed; does not make 'ionise nascent O' a gate"),
             (132, "dedicated AO source for materials / lifetime, NO_ATOMIC_O label on N2 + O2 surrogates; does not make "
                   "'ionise nascent O' a gate")],
    "OD14": [(24, "records ICP ignition, Hall ignition with ICP electrons, restart success and cycle count; does not make "
                  "ignition an RFP requirement"),
             (108, "start-up transients below 1.5 kW; a power rule, not an ignition requirement")],
}

GROUPS = [
    ("DG-XE-CASE", "SAME_QUESTION", ["XA9Q-01", "MQ-09", "OQ-A910-01"], "content of the row-48 Xe design cases (RA-CASE)"),
    ("DG-IGN-DWELL", "SAME_QUESTION", ["OQ-A907-01", "XA9Q-02"], "row-93 ignition dwell / retry count (RA-DWELL)"),
    ("DG-XE-FUNC", "COUPLED", ["XA9Q-07", "XV2Q-01", "OD6"], "Xe functional mode of hall_icp_neutralizer; XV2Q-01 applies "
     "only if XA9Q-07 = NO; OD6 (register completion) is the residual RFP meaning of 'air + Xe' that the mode must satisfy"),
    ("DG-MEOP", "SAME_QUESTION", ["XA9Q-06", "OQ-RFQ-09"], "Xe tank MEOP basis from quotations"),
    ("DG-MASS-MAP", "COUPLED", ["MQ-07", "MPQ-02", "OQ-A910-05"], "mapping of unnamed A9 items to row-54 allocation lines"),
    ("DG-MASS-CLOSURE", "COUPLED", ["MQ-01", "MQ-02", "MQ-03", "MQ-04", "MQ-05", "MQ-10"], "allocation policy and re-allocation for mass closure"),
    ("DG-C1-FLIGHT", "COUPLED", ["OQ-A907-07", "MPQ-01"], "flight C1 integration of the fallback configuration and its allocation line"),
    ("DG-ICP-HEAT-BOUND", "COUPLED", ["ICPQ-10", "OQ-A910-06"], "ICP module heat-load bound and RF-path heat allocation (after the P2 map)"),
    ("DG-RF-RATING-MARGIN", "COUPLED", ["ICPQ-11", "P2Q-10"], "RF component rating margins applied to the P2 envelope"),
    ("DG-THERMAL-LIMITS", "COUPLED", ["OQ-A907-05", "P4-OQ-01", "P1Q-04"], "validated continuous-use limits and the limit - 50 K rule"),
    ("DG-THERMAL-METHOD", "COUPLED", ["OQ-A907-03", "OQ-A907-09", "OQ-A907-10", "P3Q-02"], "thermal worst-case / margin method and model class"),
    ("DG-ISOLATION-DWV", "COUPLED", ["OQ-RFQV2-06", "OQ-RFQV2-08", "P1Q-17", "P1-IT-55"], "insulation class, DWV execution, leakage acceptance, reverification"),
    ("DG-COLLECTOR", "COUPLED", ["P1Q-09", "P3Q-01", "P4-OQ-05"], "electron collector geometry / diagnostics / coupon bias"),
    ("DG-HALL-START", "COUPLED", ["P1Q-02", "P1Q-03", "OQ-RFQV2-09"], "P1-S6 Takahashi-like topology control"),
    ("DG-Z-METHOD", "COUPLED", ["P2Q-01", "P2Q-03", "P2Q-06"], "Z_antenna method and agreement rule"),
    # register completion (lane-24 decisions / RVM question)
    ("DG-RFP-ENVELOPE", "COUPLED", ["OD2", "OD3"], "altitude-envelope quantifier and the atmosphere design states it "
     "ranges over (lane-24 topic 'envelope quantifier over 180-230 km x atmosphere states'; RVM-01)"),
    ("DG-RFP-START", "COUPLED", ["OD5", "OD14"], "whether ignition from off on atmospheric propellant is an RFP requirement "
     "and, if so, whether it must be air-only (RVM-14)"),
    ("DG-RFP-UNGATED", "COUPLED", ["OD12", "RVMQ-01"], "gate status of the recorded RFP statements (indigenous content, "
     "no-SPF, nascent O) and the redundancy basis if no-SPF is confirmed (RVM-09 / -16 / -18 / -19)"),
]


# ----------------------------------------------------------------------------------------------------------------------
def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


_SEG = re.compile(r"([^.\[\]]+)(?:\[id=([^\]]+)\])?(?:\.|$)")


def _segments(locator):
    segs, pos = [], 0
    while pos < len(locator):
        m = _SEG.match(locator, pos)
        if not m or m.end() == pos:
            raise KeyError(f"{locator}: malformed at {pos}")
        segs.append((m.group(1), m.group(2)))
        pos = m.end()
    return segs


def resolve(doc, locator):
    """Resolve 'a.b[id=X].c' (ids may contain dots and spaces) in a loaded JSON document; raise KeyError on any miss."""
    cur = doc
    for key, rid in _segments(locator):
        if not isinstance(cur, dict) or key not in cur:
            raise KeyError(f"{locator}: step {key!r} not found")
        cur = cur[key]
        if rid is not None:
            hits = [x for x in cur if isinstance(x, dict) and x.get("id") == rid] if isinstance(cur, list) else []
            if len(hits) != 1:
                raise KeyError(f"{locator}: id {rid!r} found {len(hits)} times")
            cur = hits[0]
    return cur


def _container(doc, locator):
    cur = resolve(doc, locator)
    if not isinstance(cur, list):
        raise SystemExit(f"state v4: {locator} is not a list")
    return cur


def _flat(v):
    if isinstance(v, list):
        return "; ".join(_flat(x) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_flat(x)}" for k, x in v.items())
    return str(v)


def _clip(s, n=400):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def _check_decisions():
    for jf, mf, want in ((A94, A94_MD, "A9_4_P1_P2_DECISIONS_RECORDED"), (A95, A95_MD, "A9_5_P1_CLOSURE_DECISIONS_RECORDED"),
                         (A96, A96_MD, "A9_6_IMPLEMENTATION_FIRST_DIRECTIVE_RECORDED")):
        d = _load(jf)
        if d["decision"] != want:
            raise SystemExit(f"state v4: {jf.name} has an unexpected decision value")
        if d["verbatim"]["sha256"] != _sha(mf):
            raise SystemExit(f"state v4: {mf.name} does not match the sha256 pinned in {jf.name}")


def _tbd_fields(rid):
    if rid not in TBD:
        raise SystemExit(f"state v4: {rid} has no TBD_OWNER classification (no hidden default)")
    deps, blocks, stage, basis = TBD[rid]
    bad = [d for d in deps if d not in DEPENDENCIES] + [b for b in blocks if b not in BLOCKS]
    if bad or not deps or not blocks:
        raise SystemExit(f"state v4: {rid} classification invalid: {bad or 'empty'}")
    if ("BLOCKS_P1_LATER_STAGE" in blocks) != (stage is not None):
        raise SystemExit(f"state v4: {rid} blocks_stage must be given exactly when BLOCKS_P1_LATER_STAGE")
    if "NOTHING_IMMEDIATE" in blocks and len(blocks) != 1:
        raise SystemExit(f"state v4: {rid} NOTHING_IMMEDIATE is exclusive")
    return {"dependency": list(deps), "blocks": list(blocks), "blocks_stage": stage, "classification_basis": basis}


def _derived_fields(spec):
    for p in spec["implemented_paths"]:
        if not (ROOT / p).exists():
            raise SystemExit(f"state v4: implementing artifact missing: {p}")
    for p, s in spec.get("evidence_strings", {}).items():
        if s not in (ROOT / p).read_text(encoding="utf-8"):
            raise SystemExit(f"state v4: implementing artifact {p} does not contain {s!r}")
    return {"implemented_in": list(spec["implemented_in"]), "implemented_paths": list(spec["implemented_paths"])}


def _reclassify_v3(r, a94, a95):
    rid = r["id"]
    r = dict(r)
    r["v3_status"] = r["status"]
    if rid in DERIVED_V3:
        spec = DERIVED_V3[rid]
        r.update(status="DERIVED", status_detail="DERIVED (A9.6 sec. 6)", derived_answer=spec["answer"],
                 derived_rule=spec["derived_rule"], **_derived_fields(spec))
    elif rid in a94 or rid in a95:
        raise SystemExit(f"state v4: {rid} is answered in A9.4/A9.5 but has no mapping here")
    else:
        r.update(status="TBD_OWNER", status_detail="TBD_OWNER (A9.6 sec. 7)", **_tbd_fields(rid))
    return r


def _answered_row(rid, docs):
    status, dec_path, field, lane_path, lane_loc = ANSWERED[rid]
    dec = docs[dec_path]["decisions"][rid]
    resolve(docs[lane_path], lane_loc)  # the lane records the application; raises if not
    h = HISTORICAL_QUESTIONS[rid]
    blob = HIST_BLOBS[h["blob"]]
    tag = "A9.4" if status == "ANSWERED_BY_A9_4" else "A9.5"
    note = ""
    if rid == "P1Q-16":
        note = " (confirmed definitively by A9.6 sec. 2: signed algebraic currents; do not ask again)"
    return {
        "id": rid, "kind": "lane_answered", "lane": "P2 (fo_a9_p2_impedance_prep)" if rid.startswith("P2") else "P1 (fo_a9_p1_icp_bench)",
        "source": f"{REL(lane_path)} {lane_loc}; question text: git {blob['commit'][:7]}:{blob['path']} open_owner_questions[id={rid}]",
        "source_ref": {"path": REL(lane_path), "locator": lane_loc, "historical_blob": h["blob"]},
        "question": h["question"], "proposed": h["proposed"], "needed_by": h["needed_by"],
        "status": status, "status_detail": f"ANSWERED ({tag}){note}",
        "answer_pointer": f"{REL(dec_path)} decisions.{rid}", "answer_sha256": _sha(dec_path),
        "answer_excerpt": _clip(f"{dec['status']} :: {_flat(dec[field])}"),
    }


def _lane_rows(docs, a94, a95):
    rows, seen, tbd_parts = [], set(), {}
    for lane, path, loc, kind in LANES:
        for q in _container(docs[path], loc):
            rid = q["id"]
            if rid in seen:
                raise SystemExit(f"state v4: duplicate lane id {rid}")
            seen.add(rid)
            ref = {"path": REL(path), "locator": f"{loc}[id={rid}]"}
            base = {"id": rid, "kind": kind, "lane": lane, "source": f"{ref['path']} {ref['locator']}", "source_ref": ref}
            if kind == "lane_derived_resolution":
                if q["disposition"] == "DERIVED":
                    impl = q["implemented_in"]
                    reducer = "docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py"
                    base.update(
                        question=(HISTORICAL_QUESTIONS[rid.split(" ")[0]]["question"]),
                        proposed=HISTORICAL_QUESTIONS[rid.split(" ")[0]]["proposed"],
                        needed_by=HISTORICAL_QUESTIONS[rid.split(" ")[0]]["needed_by"],
                        question_source=f"git {HIST_BLOBS['p1_at_9374d44']['commit'][:7]}:{HIST_BLOBS['p1_at_9374d44']['path']} "
                                        f"open_owner_questions[id={rid.split(' ')[0]}] (part settled: {rid})",
                        status="DERIVED", status_detail="DERIVED (A9.6 sec. 6; settled by the P1 workflow lane)",
                        derived_answer=q["answer"], derived_rule=q["follows_from"],
                        implemented_in=[f"{reducer} {impl}"], implemented_paths=[reducer], tests=list(q.get("tests", [])))
                    rows.append(base)
                elif q["disposition"] == "TBD_OWNER":
                    # the remaining part of P1Q-19 is carried by its open_owner_questions row; checked below
                    if rid.split(" ")[0] not in [x["id"] for x in docs[P1]["open_owner_questions"]]:
                        raise SystemExit(f"state v4: {rid} TBD_OWNER part has no open question row")
                    seen.discard(rid)
                    tbd_parts.setdefault(rid.split(" ")[0], []).append(f"{REL(path)} {loc}[id={rid}]")
                else:
                    raise SystemExit(f"state v4: {rid} unknown disposition {q['disposition']}")
                continue
            if kind == "lane_closed_question":
                if rid not in DERIVED_RFQV2_CLOSED:
                    raise SystemExit(f"state v4: closed RFQ v2 question {rid} not mapped")
                if q["state"] != "CLOSED_BY_A9_6_MECHANICAL_PROPAGATION":
                    raise SystemExit(f"state v4: {rid} unexpected state {q['state']}")
                base.update(question="(closed by the lane; question text not retained in the package) " + q["how"],
                            proposed="", needed_by="", status="DERIVED",
                            status_detail="DERIVED (A9.6 sec. 6; closed by the RFQ v2 lane)", derived_answer=q["how"],
                            derived_rule=q["source"], **_derived_fields(DERIVED_RFQV2_CLOSED[rid]))
                rows.append(base)
                continue
            if rid in a94 or rid in a95:
                raise SystemExit(f"state v4: {rid} still listed open in {REL(path)} but answered by the owner")
            lane_status = q.get("status")
            if lane_status not in (None, "OPEN", "TBD_OWNER"):
                raise SystemExit(f"state v4: {rid} lane status {lane_status!r} not handled")
            proposed = q.get("proposed_answer", q.get("proposed", ""))
            alts = q.get("alternatives") or q.get("admissible_alternatives")
            if not proposed and alts:
                proposed = "owner call; admissible alternatives: " + " | ".join(alts)
            base.update(question=q["question"], proposed=proposed, needed_by=q.get("needed_by", ""),
                        status="TBD_OWNER", status_detail="TBD_OWNER (A9.6 sec. 7)", **_tbd_fields(rid))
            if alts:
                base["alternatives"] = list(alts)
            if q.get("related_existing_open"):
                base["related_existing_open"] = q["related_existing_open"]
            rows.append(base)
    for base_id, refs in tbd_parts.items():
        hit = [r for r in rows if r["id"] == base_id]
        if len(hit) != 1:
            raise SystemExit(f"state v4: TBD_OWNER part of {base_id} has no single row")
        hit[0]["related_sources"] = refs
    # P1 registrations
    for rid in P1_REGISTRATIONS:
        it = resolve(docs[P1], f"items[id={rid}]")
        ref = {"path": REL(P1), "locator": f"items[id={rid}]"}
        rows.append({"id": rid, "kind": "lane_registration", "lane": "P1 (fo_a9_6_p1_workflow_completion)",
                     "source": f"{ref['path']} {ref['locator']}", "source_ref": ref,
                     "question": f"Register {it['name']} ({it['units']}): {it['value']}", "proposed": "",
                     "needed_by": f"{it['p1_gate']} (freeze point {it['freeze_point']})",
                     "status": "TBD_OWNER", "status_detail": "TBD_OWNER (A9.6 sec. 7)", **_tbd_fields(rid)})
    # answered by A9.4 / A9.5
    for rid in ANSWERED:
        rows.append(_answered_row(rid, docs))
    return rows


def _owner_row(answers, row):
    hit = [a for a in answers if a["row"] == row]
    if len(hit) != 1 or not hit[0]["owner_answer_verbatim"]:
        raise SystemExit(f"state v4: owner answer row {row} missing or empty")
    return hit[0]


def _register_completion_rows(docs):
    """Lane-24 open decisions carried by RVM rows (RVM-ID-11) and the RVM question RVMQ-01 (RVM-ID-10)."""
    for p, want in ((HGM, HGM_SHA), (ANS, ANS_SHA)):
        if _sha(p) != want:
            raise SystemExit(f"state v4: pinned input {REL(p)} changed (sha256 mismatch)")
    hgm, rvm, answers = docs[HGM], docs[RVM], docs[ANS]["answers"]
    for dem, ids in RVM_DEMANDS.items():
        text = resolve(rvm, f"interface_demands[id={dem}]")
        blob = json.dumps(text, ensure_ascii=False)
        missing = [i for i in ids if i not in blob]
        if missing:
            raise SystemExit(f"state v4: {dem} no longer names {missing}")
    carried = {}
    for row in rvm["rows"]:
        for o in row.get("open_readings", []):
            if o.get("register") == REL(HGM):
                carried.setdefault(o["id"], []).append(row["id"])
    if sorted(carried) != sorted(LANE24_REGISTERED):
        raise SystemExit(f"state v4: lane-24 decisions carried by RVM rows {sorted(carried)} != registered "
                         f"{sorted(LANE24_REGISTERED)}")
    out = []
    for rid in LANE24_REGISTERED:
        od = resolve(hgm, f"open_owner_decisions[id={rid}]")
        ref = {"path": REL(HGM), "locator": f"open_owner_decisions[id={rid}]"}
        base = {"id": rid, "kind": "lane24_open_decision", "lane": "lane-24 hard-gate matrix v1 (historical; registered by "
                "A9_6_M16 via RVM-ID-11)", "source": f"{ref['path']} {ref['locator']}; carried by "
                f"{REL(RVM)} rows {', '.join(carried[rid])}", "source_ref": ref, "source_sha256": HGM_SHA,
                "rvm_rows": carried[rid], "rvm_interface_demand": f"{REL(RVM)} interface_demands[id=RVM-ID-11]",
                "question": od["topic"], "alternatives": list(od["options"]),
                "lane24_current_handling": od["current_handling"], "proposed": "", "needed_by": ""}
        if rid in LANE24_SUPERSEDED:
            spec = LANE24_SUPERSEDED[rid]
            a = _owner_row(answers, spec["owner_row"])
            key, loc = spec["implemented_in"]
            resolve(docs[RVM], loc)
            base.update(status="SUPERSEDED", status_detail="SUPERSEDED (owner row %d; register completion)" % a["row"],
                        superseded_by={"owner_row": a["row"], "covers_ids": a["covers_ids"], "path": REL(ANS),
                                       "sha256": ANS_SHA, "owner_answer_verbatim": a["owner_answer_verbatim"]},
                        supersession_basis=spec["how"], implemented_in=[f"{REL(RVM)} {loc}"],
                        implemented_paths=[REL(RVM)])
        else:
            base.update(status="TBD_OWNER", status_detail="TBD_OWNER (A9.6 sec. 7)", **_tbd_fields(rid))
            rel = []
            for row, why in LANE24_RELATED_ROWS.get(rid, []):
                a = _owner_row(answers, row)
                rel.append({"owner_row": row, "covers_ids": a["covers_ids"], "owner_answer_verbatim":
                            a["owner_answer_verbatim"], "why_not_settled": why})
            if rel:
                base["related_owner_answers"] = rel
        out.append(base)
    for rid in RVM_QUESTIONS:
        q = resolve(rvm, f"open_owner_questions[id={rid}]")
        if q.get("status") != "TBD_OWNER":
            raise SystemExit(f"state v4: {rid} lane status {q.get('status')!r} not handled")
        ref = {"path": REL(RVM), "locator": f"open_owner_questions[id={rid}]"}
        rows_citing = [row["id"] for row in rvm["rows"] if rid in json.dumps(row, ensure_ascii=False)]
        if not rows_citing:
            raise SystemExit(f"state v4: no RVM row cites {rid}")
        out.append({"id": rid, "kind": "lane_question", "lane": "RVM (fo_a9_6_rvm; registered by A9_6_M16 via RVM-ID-10)",
                    "source": f"{ref['path']} {ref['locator']}", "source_ref": ref, "rvm_rows": rows_citing,
                    "rvm_interface_demand": f"{REL(RVM)} interface_demands[id=RVM-ID-10]",
                    "question": q["question"], "alternatives": list(q["admissible_readings"]),
                    "proposed": "owner call; admissible alternatives: " + " | ".join(q["admissible_readings"]),
                    "needed_by": q["needed_by"], "status": "TBD_OWNER", "status_detail": "TBD_OWNER (A9.6 sec. 7)",
                    **_tbd_fields(rid)})
    return out


def build():
    _check_decisions()
    v3 = _load(V3)
    docs = {p: _load(p) for p in (A94, A95, P1, P2, P3, P4, MP, XV2, RFQV2, A910, HGM, ANS, RVM)}
    a94, a95 = set(docs[A94]["decisions"]), set(docs[A95]["decisions"])
    for k, v in HIST_BLOBS.items():
        if not re.fullmatch(r"[0-9a-f]{64}", v["sha256"]) or not re.fullmatch(r"[0-9a-f]{40}", v["commit"]):
            raise SystemExit(f"state v4: historical blob {k} pin malformed")

    rows = []
    for r in v3["rows"]:
        rows.append(_reclassify_v3(r, a94, a95) if r["status"] == "OPEN" else dict(r))
    v3_ids = {r["id"] for r in v3["rows"]}
    new = _lane_rows(docs, a94, a95)
    completion = _register_completion_rows(docs)
    new += completion
    if len({r["id"] for r in new}) != len(new):
        raise SystemExit("state v4: duplicate id among the rows added since v3")
    clash = sorted({r["id"] for r in new} & v3_ids)
    if clash:
        raise SystemExit(f"state v4: lane ids collide with v3 ids: {clash}")
    missing = sorted(set(EXPECTED_NEW) - {r["id"] for r in new})
    if missing:
        raise SystemExit(f"state v4: expected lane questions not produced: {missing}")
    unused = sorted(set(TBD) - {r["id"] for r in rows + new if r.get("status") == "TBD_OWNER"})
    if unused:
        raise SystemExit(f"state v4: TBD classifications without a row: {unused}")
    no = len(rows)
    for r in new:
        no += 1
        rows.append({"no": no, **r})

    # groups
    by_id = {}
    for r in rows:
        by_id.setdefault(r["id"], []).append(r)
    groups = []
    for gid, rel, members, what in GROUPS:
        if rel not in GROUP_RELATIONS:
            raise SystemExit(f"state v4: group {gid} relation {rel}")
        for m in members:
            live = [x for x in by_id.get(m, []) if x["status"] == "TBD_OWNER"]
            if len(live) != 1:
                raise SystemExit(f"state v4: group {gid} member {m} is not exactly one TBD_OWNER row")
            if "group" in live[0]:
                raise SystemExit(f"state v4: {m} in two groups")
            live[0]["group"] = gid
        groups.append({"id": gid, "relation": rel, "members": members, "what": what})

    # vocabulary
    vocab = {k: v for k, v in v3["status_vocabulary"].items() if k != "OPEN"}
    vocab.update(NEW_STATUSES)
    vocab["SUPERSEDED"] = (v3["status_vocabulary"]["SUPERSEDED"] + "; v4 register completion: also a registered lane-24 "
                           "open decision whose question an owner answer supersedes ('superseded_by' quotes it)")
    detail = dict(v3["status_detail_vocabulary"])
    detail.update({"ANSWERED (A9.4)": "A9.4 owner decision (binding); status ANSWERED_BY_A9_4",
                   "ANSWERED (A9.5)": "A9.5 owner decision (binding); status ANSWERED_BY_A9_5",
                   "DERIVED (...)": "status DERIVED; the parenthesis names where the settlement was made",
                   "TBD_OWNER (A9.6 sec. 7)": "status TBD_OWNER"})
    for r in rows:
        if r["status"] not in vocab:
            raise SystemExit(f"state v4: {r['id']} status {r['status']} outside the closed vocabulary")
        if r["status"] == "DERIVED" and not r.get("implemented_in"):
            raise SystemExit(f"state v4: DERIVED row {r['id']} names no implementing artifact")
        if r["status"] == "SUPERSEDED" and (r.get("v3_status") == "OPEN" or r.get("kind") == "lane24_open_decision") \
                and not r.get("superseded_by"):
            raise SystemExit(f"state v4: SUPERSEDED row {r['id']} names nothing that superseded it")

    counts, reclass, new_counts, blocks_counts = {}, {}, {}, {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r.get("v3_status") == "OPEN":
            reclass[r["status"]] = reclass.get(r["status"], 0) + 1
        if r["no"] > len(v3["rows"]):
            new_counts[r["status"]] = new_counts.get(r["status"], 0) + 1
        for b in r.get("blocks", []) if r["status"] == "TBD_OWNER" else []:
            blocks_counts[b] = blocks_counts.get(b, 0) + 1
    tbd = counts.get("TBD_OWNER", 0)

    pins = {"state_v3": {"path": REL(V3), "sha256": _sha(V3)},
            "lane24_hard_gate_matrix": {"path": REL(HGM), "sha256": HGM_SHA},
            "owner_answers_147": {"path": REL(ANS), "sha256": ANS_SHA}}
    for key, p in (("a9_4_decision", A94), ("a9_4_verbatim", A94_MD), ("a9_5_decision", A95), ("a9_5_verbatim", A95_MD),
                   ("a9_6_decision", A96), ("a9_6_verbatim", A96_MD)):
        pins[key] = {"path": REL(p), "sha256": _sha(p)}

    items = [
        ("V4-IT-01", "rows in state v4", len(rows)),
        ("V4-IT-02", "rows copied from state v3", len(v3["rows"])),
        ("V4-IT-03", "v3 OPEN rows re-classified", v3["open_count"]),
        ("V4-IT-04", "rows added since v3 (lane questions, registrations, A9.4/A9.5 answers, lane DERIVED settlements, register completion)", len(new)),
        ("V4-IT-05", "TBD_OWNER rows (genuine owner questions still open)", tbd),
        ("V4-IT-06", "DERIVED rows", counts.get("DERIVED", 0)),
        ("V4-IT-07", "TBD_OWNER rows that block P1 start", blocks_counts.get("BLOCKS_P1_START", 0)),
        ("V4-IT-08", "OPEN rows remaining (must be 0: every v3 OPEN row re-classified)", counts.get("OPEN", 0)),
        ("V4-IT-09", "rows added by the register completion (lane-24 decisions of RVM-ID-11, RVM question of RVM-ID-10)",
         len(completion)),
        ("V4-IT-10", "register-completion rows TBD_OWNER", sum(1 for r in completion if r["status"] == "TBD_OWNER")),
    ]
    items = [{"id": i, "name": n, "value": v, "units": "count", "basis": "deterministic count over 'rows' by this builder",
              "source": f"{REL(OUT_JSON)} rows", "evidence_class": "derived (bookkeeping count; no physical quantity)",
              "status": "COMPUTED", "freeze_point": "rebuilt whenever a pinned input or a lane package changes"}
             for i, n, v in items]

    return {
        "schema": "owner_questions_state_v4", "id": "owner_questions_state_v4",
        "lane": "A9_6_DECPROP (fo_a9_6_decision_propagation)",
        "status": v3["status"],
        "a9_status": "Hall -> downstream 13.56 MHz ICP neutralizer INVESTIGATION_HYPOTHESIS; C1 CONTROL_FALLBACK; "
                     "no status here is a PASS; no winner declared",
        "supersedes_for_use": "docs/budgets/owner_decisions/owner_questions_state_v3.json (kept immutable)",
        "generated_by": REL(Path(__file__).resolve()),
        "companion_document": REL(OUT_MD), "companion_csv": REL(OUT_CSV),
        "test": "tests/test_owner_questions_state_v4.py",
        "pins": pins,
        "historical_blobs": HIST_BLOBS,
        "referenced_not_pinned": {
            "rule": "lane packages are mutable deliverables: read at build time and their ids checked (a missing id raises); "
                    "never sha-pinned; governance files (lane/trigger registries, ledgers, runtime state) are never read or pinned",
            "paths": [REL(p) for p in (P1, P2, P3, P4, MP, XV2, RFQV2, A910, RVM)]},
        "revisions": [
            {"lane": "A9_6_DECPROP (fo_a9_6_decision_propagation)", "what": "state v4 built from v3 and the merged lanes"},
            {"lane": "A9_6_M16 (fo_a9_6_m16_refresh)", "what": "register completion (A9.6 sec. 16 lane): lane-24 open "
             "decisions OD2, OD3, OD5, OD6, OD12, OD13, OD14 carried by RVM rows (RVM-ID-11) and RVMQ-01 (RVM-ID-10) "
             "registered; OD13 SUPERSEDED by owner row 3, the others TBD_OWNER; groups DG-RFP-ENVELOPE, DG-RFP-START, "
             "DG-RFP-UNGATED added and OD6 joined to DG-XE-FUNC"}],
        "status_vocabulary": vocab, "status_vocabulary_retired": {"OPEN": v3["status_vocabulary"]["OPEN"] +
                                                                   " (retired in v4: every v3 OPEN row re-classified under A9.6 sec. 6-7)"},
        "status_detail_vocabulary": detail,
        "dependency_vocabulary": DEPENDENCIES, "blocks_vocabulary": BLOCKS, "group_relation_vocabulary": GROUP_RELATIONS,
        "status_rule": v3["status_rule"] + " v4: a v3 OPEN row keeps its v3 status in 'v3_status' and gets exactly one of "
                       "ANSWERED_BY_A9_4 / ANSWERED_BY_A9_5 / DERIVED / TBD_OWNER / SUPERSEDED; DERIVED rows carry "
                       "'derived_rule' and 'implemented_in'; TBD_OWNER rows carry 'dependency', 'blocks' (and "
                       "'blocks_stage' for a later P1 stage); rows added since v3 carry 'source_ref' {path, locator}.",
        "counts": dict(sorted(counts.items())), "tbd_owner_count": tbd,
        "v3_open_reclassified": dict(sorted(reclass.items())), "added_since_v3": dict(sorted(new_counts.items())),
        "tbd_owner_blocks": dict(sorted(blocks_counts.items())),
        "question_groups": groups,
        "items": items,
        "interface_demands": [
            {"id": "IF-V4-01", "direction": "consumes", "counterpart": REL(V3), "quantity": "all 294 v3 rows (pinned)", "status": "APPLIED"},
            {"id": "IF-V4-02", "direction": "consumes", "counterpart": "P1 / P2 / P3 / P4 / mass-power v2 / Xe v2 / RFQ v2 packages",
             "quantity": "open_owner_questions, derived_resolutions, closed questions, P1-IT-52 / P1-IT-55 (ids resolved at build time)", "status": "APPLIED"},
            {"id": "IF-V4-03", "direction": "consumes", "counterpart": "A9.4 / A9.5 / A9.6 owner decisions (pinned)",
             "quantity": "answers P1Q-10/13/14, P2Q-05, P1Q-15/16; classification rule sec. 6-7", "status": "APPLIED"},
            {"id": "IF-V4-04", "direction": "provides", "counterpart": "cross-lane integration and the requirement-verification matrix (A9.6 sec. 15)",
             "quantity": "open owner questions per blocker (tbd_owner_blocks, question_groups)", "status": "PROVIDED"},
            {"id": "IF-V4-05", "direction": "provides", "counterpart": "consolidated verification (A9.6 sec. 18 'no orphan questions')",
             "quantity": "one row per lane question id with a resolvable source; the test resolves every source_ref", "status": "PROVIDED"},
            {"id": "IF-V4-06", "direction": "provides", "counterpart": "each lane package (next rebuild)",
             "quantity": "v4 status of every id the lane carries; a lane still listing a v4-DERIVED id as open should cite v4", "status": "PROVIDED"},
            {"id": "IF-V4-07", "direction": "consumes", "counterpart": "docs/requirements/rvm_a9/rvm_a9_v1.json RVM-ID-10 / RVM-ID-11 "
             "and the historical lane-24 matrix (pinned)", "quantity": "lane-24 decisions carried by RVM rows; RVMQ-01 "
             "(ids and carrying rows resolved at build time; a lane-24 id carried by an RVM row but not registered raises)",
             "status": "APPLIED"},
            {"id": "IF-V4-08", "direction": "provides", "counterpart": "M16 v4 (docs/experiments/hall_icp/integration/m16_v4/)",
             "quantity": "owner-question ids used as M16 v4 blocking items (each must resolve to a TBD_OWNER row here)",
             "status": "PROVIDED"},
        ],
        "owner_answers_applied": [
            {"id": "A9.4 P1Q-10 / P1Q-13 / P1Q-14 / P2Q-05", "how_applied": "rows ANSWERED_BY_A9_4 with pointer, sha256, excerpt"},
            {"id": "A9.5 P1Q-15 / P1Q-16", "how_applied": "rows ANSWERED_BY_A9_5; P1Q-16 notes the A9.6 sec. 2 definitive confirmation"},
            {"id": "A9.6 sec. 6", "how_applied": "DERIVED rows: MQ-08, OQ-INT-01, OQ-INT-02, OQ-A910-04 (v3), P1 derived_resolutions, OQ-RFQV2-07"},
            {"id": "A9.6 sec. 7", "how_applied": "every other open question stays TBD_OWNER with its dependency and blocker; no answer invented"},
            {"id": "A9.6 sec. 18", "how_applied": "no orphan questions: every question container of every merged lane enumerated; unmapped ids raise"},
            {"id": "A9.4 execution_decisions.i_d_max_h1", "how_applied": "P1Q-07 dependency MEASURED_H1_DISCHARGE_CURRENT (never from the 8.33 A rating)"},
            {"id": "owner row 3 (WEB-RFP-1)", "how_applied": "lane-24 OD13 SUPERSEDED: > 15,000 h firing retained as a "
             "provisional hard requirement until the official RFP confirms it (verbatim in superseded_by)"},
            {"id": "owner rows 1, 6, 24, 55, 93, 102, 108, 132", "how_applied": "quoted as related_owner_answers of the "
             "TBD_OWNER lane-24 decisions with why each does not settle the question; nothing answered"},
        ],
        "open_owner_questions": [],
        "open_owner_questions_note": "no new owner question is raised here: v4 re-classifies existing ones and registers "
                                     "existing lane-24 decisions and the RVM question RVMQ-01 (raised by the RVM lane)",
        "historical_reuse": [{"path": v["path"], "commit": v["commit"], "sha256": v["sha256"], "use": "verbatim question texts"}
                             for v in HIST_BLOBS.values()] + [{"path": REL(V3), "sha256": _sha(V3), "use": "all rows copied"},
                                                              {"path": REL(HGM), "sha256": HGM_SHA,
                                                               "use": "lane-24 open decisions (topic, options, handling) "
                                                                      "quoted for the register completion"}],
        "m16_impact": "none from this register: no M16 row changes state here; M16 v4 "
                      "(docs/experiments/hall_icp/integration/m16_v4/) cites v4 TBD_OWNER ids as blocking items; "
                      "M16-V3-Q-01 stays TBD_OWNER (NOTHING_IMMEDIATE)",
        "compliance": ["every v3 row present; non-OPEN v3 rows copied unchanged",
                       "every v3 OPEN row re-classified into exactly one A9.6 class",
                       "DERIVED only where an owner decision / standard rule applies and an implementing artifact exists",
                       "when in doubt TBD_OWNER; no answer invented; no winner declared; no PASS produced"],
        "rows": rows,
    }


# ----------------------------------------------------------------------------------------------------------------------
def render_md(doc):
    cell = lambda s: " ".join(_flat(s).split()).replace("|", "\\|")
    rows = doc["rows"]
    out = ["# Owner questions — state v4", "",
           "State v3 plus every question raised since v3 by the merged lanes, re-classified under owner directive A9.6 "
           "sec. 6-7 (generated by `" + doc["generated_by"] + "`; do not edit by hand).", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + f". **{doc['tbd_owner_count']} TBD_OWNER.**", "",
           "v3 OPEN rows re-classified: " + ", ".join(f"{k} {v}" for k, v in doc["v3_open_reclassified"].items()) + ".", "",
           "Added since v3: " + ", ".join(f"{k} {v}" for k, v in doc["added_since_v3"].items()) + ".", "",
           "TBD_OWNER rows by blocker: " + ", ".join(f"{k} {v}" for k, v in doc["tbd_owner_blocks"].items()) + ".", ""]
    out += ["## TBD_OWNER by blocker", ""]
    for b in doc["blocks_vocabulary"]:
        sel = [r for r in rows if r["status"] == "TBD_OWNER" and b in r["blocks"]]
        out += [f"### {b} ({len(sel)})", "", doc["blocks_vocabulary"][b], "",
                "| # | ID | Question | Dependency | Stage | Group | Needed by (lane) |", "|---|---|---|---|---|---|---|"]
        out += [f"| {r['no']} | {r['id']} | {cell(_clip(r['question'], 240))} | {cell(r['dependency'])} | "
                f"{cell(r.get('blocks_stage') or '')} | {cell(r.get('group', ''))} | {cell(r.get('needed_by', ''))} |" for r in sel]
        out.append("")
    out += ["## DERIVED", "", "| # | ID | Settlement | Rule | Implemented in |", "|---|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {cell(_clip(r['derived_answer'], 260))} | {cell(_clip(r['derived_rule'], 220))} | "
            f"{cell(r['implemented_in'])} |" for r in rows if r["status"] == "DERIVED"]
    out += ["", "## Answered by A9.4 / A9.5", "", "| # | ID | Status | Answer (excerpt) |", "|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r['status']} | {cell(r['answer_excerpt'])} |" for r in rows
            if r["status"] in ("ANSWERED_BY_A9_4", "ANSWERED_BY_A9_5")]
    out += ["", "## Register completion (lane-24 decisions carried by RVM rows; RVM question)", "",
            "| # | ID | Status | Topic | RVM rows | Blocks | Basis / superseded by |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["kind"] == "lane24_open_decision" or r["id"] in RVM_QUESTIONS:
            why = (f"owner row {r['superseded_by']['owner_row']}: {r['supersession_basis']}" if r["status"] == "SUPERSEDED"
                   else r["classification_basis"])
            out.append(f"| {r['no']} | {r['id']} | {r['status']} | {cell(_clip(r['question'], 200))} | "
                       f"{cell(r.get('rvm_rows', ''))} | {cell(r.get('blocks', ''))} | {cell(_clip(why, 300))} |")
    out += ["", "## Question groups", "", "| Group | Relation | Members | What |", "|---|---|---|---|"]
    out += [f"| {g['id']} | {g['relation']} | {', '.join(g['members'])} | {cell(g['what'])} |" for g in doc["question_groups"]]
    out += ["", "## Sources of the rows added since v3", "", "| # | ID | Kind | Source |", "|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r['kind']} | {cell(r['source'])} |" for r in rows if "source_ref" in r]
    out += ["", "## Pins", ""] + [f"- `{v['path']}` sha256 `{v['sha256']}`" for v in doc["pins"].values()]
    out += [f"- git `{v['commit'][:7]}:{v['path']}` sha256 `{v['sha256']}` ({v['what']})" for v in doc["historical_blobs"].values()]
    out += ["", "No new owner question is raised here. M16 impact: none from this register (M16 v4 cites v4 ids). No PASS, no winner."]
    return "\n".join(out) + "\n"


def render_csv(doc):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    cols = ["no", "id", "kind", "lane", "source", "v3_status", "status", "status_detail", "question", "dependency", "blocks",
            "blocks_stage", "group", "derived_rule", "implemented_in", "answer_pointer", "answer_excerpt", "superseded_by",
            "proposed", "needed_by"]
    w.writerow(cols)
    for r in doc["rows"]:
        w.writerow([_flat(r.get(c, "") if r.get(c) is not None else "") for c in cols])
    return buf.getvalue()


def outputs(doc=None):
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc), OUT_CSV: render_csv(doc)}


def main():
    outs = outputs()
    if "--check" in sys.argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"state v4 outputs stale: {stale}")
        print("owner-question state v4: current")
        return
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    print("wrote state v4: " + json.dumps(json.loads(outs[OUT_JSON])["counts"]))


if __name__ == "__main__":
    main()
