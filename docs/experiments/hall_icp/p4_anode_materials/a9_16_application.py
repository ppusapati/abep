"""A9.16 step 1 - owner decisions of 2026-10-01 applied to the P4 anode / collector materials package (lane P4 ANODE /
COLLECTOR MATERIALS).

Data + record module read by build_p4_anode_materials.py (deterministic; no I/O of its own). Each applied decision is
cited by its immutable decision file path, the sha256 of its machine-readable json and the question id; the VERBATIM
.md of every decision was read in full and governs over the json 'summary' digest. The rules themselves are the pure
functions of p4_a9_16_rules.py; every number the owner deferred to a later registration is a registration slot with a
fail-closed refusal - never invented here. No material is selected; FINAL_ANODE_MATERIAL, FINAL_COLLECTOR_MATERIAL and
the filter material stay OPEN; ANODE_THERMAL_CLOSURE and ICP_COUPLED_THERMAL stay UNRESOLVED; nothing is a PASS.
"""

DEC = {
    "A9.12": ("docs/decisions/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json",
              "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d",
              "docs/decisions/OD_2026_10_01_A9_12_S5_P3_P4_OWNER_DECISIONS.md",
              "d8baac842cfe574037427aef1ced2476ba96919d80ceacda9b2bf16502e0af62"),
    "A9.13": ("docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
              "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
              "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
              "adf11923c07f773276ee893d6ad01cd51c4988ba4bfb8865ec1d781a4978c8bf"),
    "A9.15": ("docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903"),
}
ORDER = ("A9.12", "A9.13", "A9.15")
RULES_REL = "docs/experiments/hall_icp/p4_anode_materials/p4_a9_16_rules.py"
TEST_REL = "tests/test_p4_a9_16_owner_rules.py"
F2_REL = "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json"


def decision_pins():
    """(key -> (path, sha256, role)) for the builder's PINS table (verified like every other pin)."""
    out = {}
    for k in ORDER:
        j, js, m, ms = DEC[k]
        tag = k.replace(".", "")
        out[tag] = (j, js, "owner %s (machine-readable; A9.16 step 1)" % k)
        out[tag + "_MD"] = (m, ms, "owner %s verbatim (governs over the json summary; A9.16 step 1)" % k)
    return out


# (decision, question id, sequenced no, owner answer code, how applied, where implemented, tests)
APPLIED = [
    ("A9.12", "P4-OQ-01", "S5.10", "STAGED",
     "staged T_validated,continuous: stage 1 coupon screening under the service-representative combination of "
     "atmosphere / species, temperature, electrical bias / current, exposure duration and thermal cycling (where "
     "applicable) with pre-registered electrical, oxidation / recession, mass-loss and surface / material metrics -> "
     "the highest temperature meeting them is a COUPON_SUPPORTED_PROVISIONAL_LIMIT for design screening only; stage 2 "
     "integrated replaceable anode / collector confirmation of the down-selected material on the H-1 / ICP article in "
     "the applicable plasma, electrical and thermal environment -> only then T_VALIDATED_CONTINUOUS for the P3 / LOCK-1 "
     "material-temperature closure; stage 3 full-duration or justified accelerated-life qualification before a final "
     "flight-life claim; melting point, short vendor exposure, generic air-use temperature and a brief coupon test "
     "(shorter than the pre-registered exposure) are refused (NOT_CONTINUOUS_USE_VALIDATION); the CR-01 gate admits a "
     "T_validated_continuous record only at stage 2 or later, proven by a referenced stage record (id + sha256) that "
     "validation_stage_record classifies to that stage, material and limit - a bare declaration is INCOMPLETE_EVIDENCE "
     "(A9.16 repair COR-06)",
     "p4_a9_16_rules.validation_stage_record, limit_use_check, gate_admissible_t_validated; p4_screening.evaluate_gate "
     "(CR-01 stage check, t_validated_stage_refusal); items IT-12 / IT-23; test plan stages ST-1..ST-3 (Q0/Q1, Q4, Q5); criteria CR-01 rule",
     ["test_p4_a9_16_stage_1_is_screening_only", "test_p4_a9_16_stage_2_needs_stage_1_and_article",
      "test_p4_a9_16_stage_3_life", "test_p4_a9_16_non_validation_bases_refused",
      "test_p4_a9_16_cr01_gate_requires_stage_2"]),
    ("A9.12", "P4-OQ-02", "S5.11", "BROAD_Q0_DOWNSELECT_Q1",
     "Q0 matrix exactly as the owner listed it: R8-C01 316L engineering / reference control only; R8-C02 IN600, "
     "IN625, Haynes 230 (+ X-750 as an additional comparison only if readily available; generic Hastelloy refused "
     "until an exact grade is declared); R8-C03 IN601, Haynes 214 and ONE explicitly specified FeCrAl grade (grade TBD, "
     "declared before admission); R8-C04 Rh-coated 316L; R8-C05 Pt-clad / plated 316L; R8-C06 Cr-plated 316L; R8-C07 "
     "IrO2 / RuO2-type MMO with the exact coating system and substrate declared; R8-C08 bare W negative / reference "
     "control only (not restored as baseline anode candidate); R8-C09 specified isotropic graphite reference / control "
     "(grade declared); Ti, TiN / ZrN, bulk Cu, bulk Ir reserve only (specific hypothesis / need before activation, "
     "outside the baseline campaign); Mo / TZM, ZrB2 / HfB2 / SiC and Hf / Zr are not in the owner Q0 matrix; Q1 "
     "admits only Q0 survivors meeting the pre-registered screening criteria; every coating records composition, "
     "thickness, deposition process, substrate, surface preparation and lot / process provenance",
     "p4_a9_16_rules.Q0_MATRIX, RESERVE, q0_admission, reserve_activation, q1_admission; candidates[].q0_disposition; "
     "a9_16_owner_rules.q0_matrix; item IT-17; QUAL_STAGES Q0 / Q1",
     ["test_p4_a9_16_q0_matrix_exact", "test_p4_a9_16_q0_declarations_refused",
      "test_p4_a9_16_coating_record_required", "test_p4_a9_16_reserve_and_not_listed",
      "test_p4_a9_16_q1_only_q0_survivors"]),
    ("A9.12", "P4-OQ-03", "S5.12", "LOCK_2_AFTER_METROLOGY_BEFORE_EXPOSURE",
     "LOCK-2: first commission the Q0 / Q1 metrology (resistance repeatability / resolution, mass-change detection "
     "limit, profilometry / recession resolution, SEM / XPS where applicable, coupon-to-coupon / process "
     "repeatability, AO / ion dosimetry) on standards, blanks, controls or sacrificial commissioning coupons only; then, "
     "before ANY acceptance-bearing candidate exposure, freeze the resistance-rise threshold, mass-loss / recession "
     "limits, sputtering / erosion acceptance, exposure duration / fluence, uncertainty treatment and acceptance / "
     "rejection logic; thresholds derived from candidate coupon performance are refused; a criterion the metrology "
     "cannot resolve returns NOT_EVALUATED_METROLOGY and is never widened; any post-freeze change refused",
     "p4_a9_16_rules.metrology_commissioning, lock2_freeze, threshold_revision; items IT-13 / IT-24; requirements CR-02 "
     "/ CR-03 / CR-04 tbd text; test plan TP-00",
     ["test_p4_a9_16_lock2_requires_commissioning", "test_p4_a9_16_lock2_refuses_candidate_derived_thresholds",
      "test_p4_a9_16_lock2_metrology_never_widened", "test_p4_a9_16_lock2_before_acceptance_exposure"]),
    ("A9.12", "P4-OQ-04", "S5.13", "BOTH",
     "BOTH: lawful acquisition (library, inter-library loan, publisher purchase, institutional subscription, other "
     "legitimate licensed route) of species-resolved N+ / N2+ / O+ / O2+ sputter yields where available, used for prior "
     "bounds, test-matrix selection, comparison and model initialisation only; in parallel project ion-beam "
     "measurement of the down-selected candidates gives the candidate-specific evidence at the relevant species / "
     "energy / angle / material condition; an elemental-target yield is never silently substituted for an alloy / "
     "coating (refused without a registered NOT_MATERIAL assessment; even then an explicitly labelled proxy for "
     "literature uses only); no acquisition is performed by this lane (no contact, no purchase)",
     "p4_a9_16_rules.sputter_record_use; items IT-22 / IT-25; test plan TP-04",
     ["test_p4_a9_16_sputter_literature_uses_only", "test_p4_a9_16_sputter_elemental_substitution_refused",
      "test_p4_a9_16_sputter_species_resolved_and_lawful"]),
    ("A9.12", "P4-OQ-05", "S5.14", "NEGATIVE_BIAS_PLUS_FLOATING_CONTROL",
     "collector coupon programme = negative-biased (ion-collecting service polarity) set + floating matched control; "
     "polarity frozen NEGATIVE now; the bias magnitude / ion energy is derived from the measured P1 collector operating "
     "envelope and plasma / sheath evidence before any acceptance-bearing biased exposure "
     "(NOT_EVALUATED_BIAS_MAGNITUDE_TBD_P1 until then; never invented); a pre-P1 biased Q0 exposure is fixture / "
     "process verification, ENGINEERING_ONLY, never the final service-condition qualification; the anode pair of row "
     "106 (biased + floating) is unchanged",
     "p4_a9_16_rules.collector_coupon_exposure; items IT-14 / IT-19; test plan TP-01 / TP-02; ID-06 note",
     ["test_p4_a9_16_collector_polarity_frozen", "test_p4_a9_16_collector_bias_from_p1"]),
    ("A9.12", "OQ-A907-05", "S5.3", "PROVISIONAL_ONLY",
     "context for P4-OQ-01: a supplier continuous-use rating is never a P4 validation stage "
     "(SUPPLIER_CONTINUOUS_RATING refused by validation_stage_record); P4 stage-2 / stage-3 limits are the qualified "
     "material limits that replace provisional values (the provisional-limit rule itself is applied in the P3 lane)",
     "p4_a9_16_rules.NON_VALIDATION_BASES", ["test_p4_a9_16_non_validation_bases_refused"]),
    ("A9.13", "F2-OQ-04", "S6.6", "COMPRESSOR_INLET_PLUS_APP_FILTER",
     "APP-FILTER added as a third P4 application: baseline filter at intake / channel array -> filter -> compressor "
     "inlet (downstream of the primary intake / collimator, upstream of the compressor; axial location, area and "
     "thermal state remain design variables), inert / low-recombination baseline (S6.4; a catalytic O -> O2 element "
     "is only a separately labelled research variant with its own conversion, flow, qualification and H-1 map); "
     "filter criteria CR-10..CR-15 (AO / O exposure and erosion, catalytic / recombination behaviour, particulate "
     "retention, thermal cycling, transmission and conductance effects) and tests TP-10..TP-15; filter acceptance "
     "slots pre-registered before LOCK-1 from the contamination environment, H-1 feed requirement and measured filter "
     "material / geometry (S6.3; NOT_EVALUATED_FILTER_ACCEPTANCE_TBD); no filter material candidate is invented "
     "(candidate set TBD_AFTER_EVIDENCE, F2 lane F2-IF-08)",
     "APPLICATIONS['APP-FILTER']; CRITERIA CR-10..CR-15; requirements RQ-10-F..RQ-15-F; TEST_PLAN TP-10..TP-15; "
     "p4_a9_16_rules.filter_material_role, filter_acceptance; interface ID-12",
     ["test_p4_a9_16_app_filter_present", "test_p4_a9_16_filter_baseline_inert_catalytic_variant",
      "test_p4_a9_16_filter_acceptance_slots"]),
    ("A9.15", "RFP-COMPLIANT PROPELLANT POLICY", "-", "RFP_GOVERNS_AIR_AND_XE",
     "reviewed: the P4 package carries no text that restricts Xe to a C1 contingency; Xe+ stays in the CR-04 / TP-04 sputter "
     "species set because Xe is an RFP-required system propellant capability (ambient air AND Xe), not a contingency; "
     "the ICP gas-mode baseline (A9.1 G-REUSE primary, G-XE declared variant) is unchanged; no C1 Xe is invented or "
     "excluded here",
     "criteria CR-04; TEST_PLAN TP-04", ["test_p4_a9_16_no_xe_contingency_text"]),
]


def owner_answers_applied_rows():
    rows = []
    for dk, qid, seq, code, how, where, tests in APPLIED:
        j, js, m, ms = DEC[dk]
        rows.append({"decision": "%s %s" % (dk, qid), "kind": dk, "path": j, "sha256": js, "verbatim_path": m,
                     "verbatim_sha256": ms, "question_id": qid, "covers_ids": [qid], "sequenced_no": seq,
                     "answer": code, "owner_answer_verbatim": "see " + m + " (" + seq + ")", "how_applied": how,
                     "implemented_in": where, "tests": tests, "step": "A9.16 step 1"})
    return rows


def cite(dk, qid):
    j, js, _, _ = DEC[dk]
    return "%s %s (%s sha256 %s)" % (dk, qid, j, js)


DECIDED_OWNER_QUESTIONS = {
    "P4-OQ-01": ("A9.12", "S5.10", "STAGED"),
    "P4-OQ-02": ("A9.12", "S5.11", "BROAD_Q0_DOWNSELECT_Q1"),
    "P4-OQ-03": ("A9.12", "S5.12", "LOCK_2_AFTER_METROLOGY_BEFORE_EXPOSURE"),
    "P4-OQ-04": ("A9.12", "S5.13", "BOTH"),
    "P4-OQ-05": ("A9.12", "S5.14", "NEGATIVE_BIAS_PLUS_FLOATING_CONTROL"),
}

# rules that also bind artifacts outside this lane's allowed paths (integration / other lanes; listed, not edited)
OUT_OF_LANE = [
    ("docs/procurement/rfq_a9_v2/ (pair XL-27 text 'coupon shortlist TBD_OWNER P4 IT-17' - identical pair text on both "
     "sides; the Q0 matrix of A9.12 P4-OQ-02 now fixes the shortlist, so RFQ and P4 re-state XL-27 together at the "
     "integration re-pin; the RFQ v3 coupon lots follow the Q0 matrix and coating records)", ["P4-OQ-02"]),
    ("docs/experiments/hall_icp/p1_icp_bench/ (P1 collector envelope P1-M-10 / P1-M-11 / P1-M-27 and P1-M-30 feed the "
     "collector-coupon bias magnitude; pair XL-25 re-stated with P1 by the A9.16 repair lane, F2: sheath energy from the "
     "P1-M-30 Langmuir probe, A9.8 P3Q-01 option C)", ["P4-OQ-05"]),
    ("docs/experiments/lifetime_ao/ (AO / lifetime register: a future revision adds filter erosion / recombination, "
     "F2-IF-09, and the LOCK-2 coupon thresholds)", ["F2-OQ-04", "P4-OQ-03"]),
    ("docs/design_synthesis/f2_filter/ (F2-IF-08 status 'TBD_OWNER (F2-OQ-04)' - now decided; P4 APP-FILTER exists)",
     ["F2-OQ-04"]),
    ("docs/budgets/owner_decisions/owner_questions_state_v4.* (rows still TBD_OWNER)",
     ["P4-OQ-01", "P4-OQ-02", "P4-OQ-03", "P4-OQ-04", "P4-OQ-05", "F2-OQ-04"]),
    ("docs/experiments/hall_icp/integration/ (M16 v4 rows 18 / 20 / 21: framework only, readiness unchanged)",
     ["P4-OQ-01", "P4-OQ-02"]),
]
