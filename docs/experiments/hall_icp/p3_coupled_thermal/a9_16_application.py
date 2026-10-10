"""A9.16 step 1 - owner decisions of 2026-10-01 applied to the P3 coupled-thermal package (lane P3 COUPLED THERMAL).

Data + record module read by build_p3_coupled_thermal_v2.py (deterministic; no I/O of its own). Each applied decision is
cited by its immutable decision file path, the sha256 of its machine-readable json and the question id; the VERBATIM
.md of every decision was read in full and governs over the json 'summary' digest. The rules themselves are the pure
functions of p3_a9_16_rules.py; every number the owner deferred to a later registration is a registration slot with a
fail-closed refusal - never invented here. Nothing here is a thermal PASS; ICP_COUPLED_THERMAL and
ANODE_THERMAL_CLOSURE stay UNRESOLVED.
"""

DEC = {
    "A9.8": ("docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json",
             "e96b8bc0a27f5fbc03d48d36db6e470dfc60c4960d6ba02cdaac8871752b537f",
             "docs/decisions/OD_2026_10_01_A9_8_S1_P1_START_OWNER_DECISIONS.md",
             "8e770d0edf056a0402f6ec8c86a2a2feec169ab971fae788c7a9a620211e1aa0"),
    "A9.12": ("docs/decisions/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json",
              "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d",
              "docs/decisions/OD_2026_10_01_A9_12_S5_P3_P4_OWNER_DECISIONS.md",
              "d8baac842cfe574037427aef1ced2476ba96919d80ceacda9b2bf16502e0af62"),
    "A9.14": ("docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
              "2a61c761120863c4b5821043ab78b6f9b28227584f7d83cb48ecd6598ed0af07"),
    "A9.15": ("docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903"),
}
ORDER = ("A9.8", "A9.12", "A9.14", "A9.15")
RULES_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_a9_16_rules.py"
TEST_REL = "tests/test_p3_a9_16_owner_rules.py"


def decision_pins():
    """(key -> (path, sha256, role)) for the builder's DECISIONS table (verified like every other pin)."""
    out = {}
    for k in ORDER:
        j, js, m, ms = DEC[k]
        tag = k.replace(".", "")
        out[tag] = (j, js, "owner %s (machine-readable; A9.16 step 1)" % k)
        out[tag + "MD"] = (m, ms, "owner %s verbatim (governs over the json summary; A9.16 step 1)" % k)
    return out


# (decision, question id, sequenced no, owner answer code, how applied, where implemented, tests)
APPLIED = [
    ("A9.8", "P3Q-01", "S1.7", "C_BOTH_CALORIMETRY_PRIMARY",
     "option C: the calorimetric collector energy balance (calibrated temperatures, registered thermal conductances / "
     "thermal mass, RF-ON / RF-OFF comparison, collector-current / bias steps) is the PRIMARY Q_collector evidence; "
     "the Langmuir-probe sheath-model route (T_e, plasma potential: P3-P1-04 / P3-P1-05) is an independent "
     "cross-check, preferably in matched diagnostic runs, never replacing or averaged with the primary value; the "
     "agreement criterion is a registration slot (NOT_EVALUATED_CROSS_CHECK_CRITERION_TBD); a probe present during an "
     "ICP45 capacity record without prior evidence that its perturbation is negligible refuses the record "
     "(PROBE_PERTURBATION_NOT_SHOWN_NEGLIGIBLE)",
     "p3_a9_16_rules.q_collector_evidence, q_collector_cross_check, icp45_record_probe_admissibility; items "
     "P3-P1-04 / P3-P1-05 / P3-P1-09; heat_terms.Q_collector",
     ["test_p3_a9_16_q_collector_calorimetry_primary", "test_p3_a9_16_probe_cross_check_criterion_slot",
      "test_p3_a9_16_icp45_probe_contamination_refused"]),
    ("A9.12", "ICPQ-10", "S5.1", "A_1_20_X_PFWD_PLUS_PD",
     "ICP-43 total-module bound Q_ICP,bound = 1.20 x (P_fwd,max + P_d,max): P_fwd,max = maximum ADMITTED RF "
     "forward-power operating point of the registered ICP / P2 envelope, P_d,max = registered H-1 discharge-power "
     "bound; either missing -> INCOMPLETE_EVIDENCE; never 1.20 x 1.5 kW (a bus-ceiling basis is refused; "
     "alternative B rejected, P3-B-02); a thermal bounding rule, not a deposition statement; replaced by measured "
     "coupled heat terms (same 1.20, never relaxed) once P1 / P2 / P3 deposition and loss terms exist",
     "p3_a9_16_rules.icp43_total_module_bound; items P3-B-01 / P3-B-02; a9_16_owner_rules.icp43_bound_evaluation",
     ["test_p3_a9_16_icp43_bound_rule", "test_p3_a9_16_icp43_refuses_bus_ceiling_and_missing",
      "test_p3_a9_16_icp43_measured_terms_keep_margin", "test_p3_a9_16_registered_inputs_refused"]),
    ("A9.12", "OQ-A907-03", "S5.2", "BOUNDING_CORNER_ADMISSIBLE_JOINT_STATES",
     "the >= 50 K rule is evaluated at the worst ADMISSIBLE combined corner: a joint-state admissibility declaration "
     "(registered before the evaluation) excludes a corner only by a sourced MUTUALLY_EXCLUSIVE_STATES / "
     "KNOWN_CORRELATED_EXTREMES exclusion; per admissible case the 1.20 dissipated-load margin and the hot / cold "
     "environmental boundary are applied and EVERY temperature-limited node is evaluated against "
     "T_validated,continuous - 50 K; the 50 K is never relaxed; analog ranges are replaced by measured deposition "
     "fractions when they exist; unregistered declaration -> NOT_EVALUATED_ADMISSIBILITY_TBD",
     "p3_a9_16_rules.admissible_corners, bounding_case_evaluation, node_margin; item P3-A-01",
     ["test_p3_a9_16_admissible_corners", "test_p3_a9_16_bounding_case_every_node"]),
    ("A9.12", "OQ-A907-05", "S5.3", "PROVISIONAL_ONLY",
     "supplier continuous ratings (BN guide value, ceramic wire) are SUPPLIER_PROVISIONAL limits usable only for "
     "preliminary screening, equipment protection, design sensitivity and procurement down-selection; they never "
     "establish T_validated,continuous; a margin depending on one is UNRESOLVED_CONDITIONAL_ON_PROVISIONAL_LIMIT; "
     "design / flight / LOCK-1 closure use is refused",
     "p3_a9_16_rules.node_limit, limit_use_check, node_margin; item P3-M-04",
     ["test_p3_a9_16_provisional_supplier_limits"]),
    ("A9.12", "OQ-A907-06", "S5.4", "ISOLATED_MOUNT_RADIATOR_50W_PROVISIONAL",
     "thermally isolated H-1 mount + dedicated radiator; mount-heat allocations 50 W governing (provisional), "
     "100 W contingency / sensitivity only, 25 W stretch; all three always reported; a result meeting only 100 W is "
     "ONLY_WITHIN_100W_CONTINGENCY_NOT_CLOSED; 50 W is an owner design allocation, not a spacecraft requirement, "
     "replaced by the spacecraft thermal ICD when it exists",
     "p3_a9_16_rules.mount_heat_report; item P3-M-05", ["test_p3_a9_16_mount_heat_allocations"]),
    ("A9.12", "OQ-A907-08", "S5.5", "YES_COATING_NODE_LIMIT",
     "the exterior coating is its own temperature-limited node, T_op <= T_validated,continuous - 50 K, once sourced / "
     "validated for the actual coating / substrate / application system (not the generic family name); until then "
     "OPEN_COATING_LIMIT_NOT_SOURCED and no configuration relying on the coating receives a final thermal closure; "
     "sensitivities retained as engineering information",
     "p3_a9_16_rules.node_limit (is_coating), node_margin; item P3-M-07", ["test_p3_a9_16_coating_node_open"]),
    ("A9.12", "OQ-A907-09", "S5.6", "DISSIPATED_ONLY",
     "the 1.20 heat-load margin multiplies internally dissipated loads only (discharge, RF / match, coil, cathode, "
     "collector, plume interception, other dissipative); solar / albedo / outgoing-IR use their registered hot / "
     "cold envelope case and are never multiplied; an inadequate environmental bound is enlarged explicitly through "
     "its own record; an untagged load is refused",
     "p3_a9_16_rules.apply_heat_load_margin; item P3-M-01", ["test_p3_a9_16_margin_dissipated_only"]),
    ("A9.12", "OQ-A907-10", "S5.7", "YES_10K_SEARCH_SENSITIVE",
     "margin to the design ceiling after the REGISTERED search allowance < 10 K -> label SEARCH_SENSITIVE (label "
     "only: status unchanged, does not replace 50 K, no 10 K requirement); before LOCK-1 use an independent bounding "
     "check (global optimisation / interval bounding / exhaustive admissible grid / demonstrated bounding method) is "
     "required; the more adverse result governs; the allowance is never increased after the outcome",
     "p3_a9_16_rules.search_sensitivity, lock1_use_of_search_result; item P3-M-08",
     ["test_p3_a9_16_search_sensitive_label_only", "test_p3_a9_16_search_sensitive_needs_independent_bound"]),
    ("A9.12", "OQ-A910-06", "S5.8", "YES_600W_TEMPORARY",
     "Q_RF,allocation = 500 W x 1.20 = 600 W retained TEMPORARILY as the ICP RF-path thermal allocation, labelled not "
     "a component rating / not a demonstrated flight operating point / not the ICP-43 total-module bound / not a "
     "substitute for measured delivered RF power; P_line/match,loss additional (a total without it is refused); "
     "superseded after P2 by 1.20 x the VERIFIED P2 envelope of P_delivered + line / matching losses (antenna / plasma "
     "loading and uncertainty registered)",
     "p3_a9_16_rules.rf_allocation_record, rf_thermal_basis; item P3-B-03",
     ["test_p3_a9_16_rf_allocation_600w_labels", "test_p3_a9_16_rf_allocation_superseded_by_p2"]),
    ("A9.12", "P3Q-02", "S5.9", "A_LUMPED_PLUS_CORRELATION_CONDITIONAL",
     "model class A (lumped H2-5 network + P3 radiosity enclosure) accepted for LOCK-1 conditionally: the correlation "
     "plan registers sensor locations, measurement uncertainty, comparison quantities, residual band and sensor "
     "placement / contact treatment BEFORE the correlation data (slots P3-C-01..05; missing -> "
     "NOT_EVALUATED_CORRELATION_PLAN_TBD); residual outside the band or unrepresentable gradients / hot spots -> "
     "ESCALATE_TO_FINER_MODEL_MANDATORY before any LOCK-1 thermal closure; finer local models allowed earlier",
     "p3_a9_16_rules.correlation_plan_check, correlation_outcome; items P3-C-01..05",
     ["test_p3_a9_16_correlation_plan_slots", "test_p3_a9_16_correlation_escalation"]),
    ("A9.14", "ICPQ-03", "S8.1", "YES_BOTH_MODULES_ON_MOVING_PLATFORM",
     "both interchangeable downstream modules and their representative mounting on the moving thrust platform: the "
     "carrier conduction path P3-K-02 is the moving-platform path (no fixed-mount alternative carried)",
     "item P3-K-02; existing_open_owner_questions_carried.ICPQ-03", ["test_p3_a9_16_carried_questions_answered"]),
    ("A9.14", "ICPQ-09", "S8.3", "PLUME_INTERCEPTION_INSIDE_SYSTEM_BOUNDARY",
     "plume interception by the ICP structure stays inside the system boundary (Q_plume reported; never corrected "
     "away)", "heat_terms.Q_plume; existing_open_owner_questions_carried.ICPQ-09",
     ["test_p3_a9_16_carried_questions_answered"]),
    ("A9.15", "RFP-COMPLIANT PROPELLANT POLICY", "-", "RFP_GOVERNS_AIR_AND_XE",
     "reviewed: the P3 package contains no 'Xe contingency-only for C1' text and no Xe heat term; the ICP gas-mode "
     "baseline (A9.1 G-REUSE primary) is unchanged; nothing to amend here",
     "-", ["test_p3_a9_16_no_xe_contingency_text"]),
]


def owner_answers_applied_rows():
    rows = []
    for dk, qid, seq, code, how, where, tests in APPLIED:
        j, js, m, ms = DEC[dk]
        rows.append({"kind": dk, "path": j, "sha256": js, "verbatim_path": m, "verbatim_sha256": ms,
                     "decision": qid, "sequenced_no": seq, "answer": code, "applied": how, "implemented_in": where,
                     "tests": tests, "step": "A9.16 step 1"})
    return rows


def cite(dk, qid):
    j, js, _, _ = DEC[dk]
    return "%s %s (%s sha256 %s)" % (dk, qid, j, js)


DECIDED_OWNER_QUESTIONS = {
    "P3Q-01": ("A9.8", "C_BOTH_CALORIMETRY_PRIMARY"),
    "P3Q-02": ("A9.12", "A_LUMPED_PLUS_CORRELATION_CONDITIONAL"),
    "ICPQ-03": ("A9.14", "YES_BOTH_MODULES_ON_MOVING_PLATFORM"),
    "ICPQ-09": ("A9.14", "PLUME_INTERCEPTION_INSIDE_SYSTEM_BOUNDARY"),
    "ICPQ-10": ("A9.12", "A_1_20_X_PFWD_PLUS_PD"),
    "OQ-A907-06": ("A9.12", "ISOLATED_MOUNT_RADIATOR_50W_PROVISIONAL"),
    "OQ-A907-09": ("A9.12", "DISSIPATED_ONLY"),
    "OQ-A907-10": ("A9.12", "YES_10K_SEARCH_SENSITIVE"),
    "OQ-A910-06": ("A9.12", "YES_600W_TEMPORARY"),
}

CARRIED_HANDLING = {
    "ICPQ-03": "A9.14 S8.1: both modules on the moving thrust platform - carrier conduction path P3-K-02 is the "
               "moving-platform path",
    "ICPQ-09": "A9.14 S8.3: plume interception stays inside the system boundary (Q_plume computed and reported, never "
               "corrected away)",
    "ICPQ-10": "A9.12 S5.1: alternative A 1.20 x (P_fwd,max + P_d,max) (P3-B-01, inputs TBD); alternative B rejected "
               "(P3-B-02)",
    "OQ-A907-06": "A9.12 S5.4: 50 W governing provisional / 100 W contingency / 25 W stretch, all reported "
                  "(mount_heat_report, P3-M-05)",
    "OQ-A907-09": "A9.12 S5.6: 1.20 on dissipated loads only; environmental via the registered hot / cold envelope "
                  "(apply_heat_load_margin, P3-M-01)",
    "OQ-A907-10": "A9.12 S5.7: SEARCH_SENSITIVE label below 10 K after the registered allowance; independent bound "
                  "before LOCK-1 (P3-M-08)",
    "OQ-A910-06": "A9.12 S5.8: 600 W temporary allocation with the four labels, P_line/match,loss additional, "
                  "superseded after P2 (P3-B-03, rf_thermal_basis)",
}

# rules that also bind artifacts outside this lane's allowed paths (integration / other lanes; listed, not edited)
OUT_OF_LANE = [
    ("docs/hardware/h2_a9_revisions/ (A9-07 uncoupled thermal rerun: bounding corners, search allowance / "
     "search_sensitive flag, mount-heat levers, provisional BN / ceramic-wire ratings, coating limit, environmental "
     "margin treatment)", ["OQ-A907-03", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "OQ-A907-09", "OQ-A907-10"]),
    ("docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py (pair XL-18 and P1-M-30 re-stated together with "
     "P3 by the A9.16 repair lane, F2: Langmuir probe REQUIRED for the Ar P1 campaign, calorimetry primary)",
     ["P3Q-01"]),
    ("docs/experiments/hall_icp/p2_impedance_map/ (ICPQ-10 applied by the A9.16 repair lane, F1: alternative A; "
     "RC-HEAT references p3_a9_16_rules.icp43_total_module_bound)", ["ICPQ-10"]),
    ("docs/budgets/mass_power_a9_v2/ (immutable v2 history keeps OQ-A910-06 OPEN; mass / power v3 and P2 record it "
     "OWNER_DECIDED - A9.16 repair F5)", ["OQ-A910-06"]),
    ("docs/budgets/owner_decisions/owner_questions_state_v4.* (rows still TBD_OWNER)",
     ["P3Q-01", "P3Q-02", "ICPQ-10", "OQ-A907-03", "OQ-A907-05", "OQ-A907-06", "OQ-A907-08", "OQ-A907-09",
      "OQ-A907-10", "OQ-A910-06"]),
]
