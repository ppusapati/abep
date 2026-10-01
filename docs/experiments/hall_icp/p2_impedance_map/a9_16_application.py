"""A9.16 step 1 - owner decisions of 2026-10-01 applied to the P2 impedance-map package (lane P2 IMPEDANCE MAP).

Data + transformation module read by build_p2_impedance_prep.py (deterministic; no I/O of its own). Each applied
decision is cited by its immutable decision file path, the sha256 of its machine-readable json and the question id; the
VERBATIM .md of every decision was read in full and governs over the json 'summary' digest. Owner-supplied numbers used
here are exactly the owner's (k_agreement = k_transition = k_loss = 2.0; k_RF = 1.5; continuous RF power / current
1.25; thermal 1.20). Every number the owner deferred to a later registration is a registration slot with a fail-closed
refusal (p2_a9_16_rules) - never invented here. RF ratings stay TBD_AFTER_IMPEDANCE_MAP; nothing here is a PASS.
"""
import copy

DEC = {
    "A9.8": ("docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json",
             "e96b8bc0a27f5fbc03d48d36db6e470dfc60c4960d6ba02cdaac8871752b537f",
             "docs/decisions/OD_2026_10_01_A9_8_S1_P1_START_OWNER_DECISIONS.md",
             "8e770d0edf056a0402f6ec8c86a2a2feec169ab971fae788c7a9a620211e1aa0"),
    "A9.10": ("docs/decisions/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json",
              "3a99f16dd957f533b6b7afb7539d27be132fae386148e1683e417db0ede26544",
              "docs/decisions/OD_2026_10_01_A9_10_S3_P1_LATER_STAGE_OWNER_DECISIONS.md",
              "6845f54a97192eaa934cc67d5f415c94e317707c97411353aa2325bf5f9b0491"),
    "A9.11": ("docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json",
              "d8baf59a5b92739698e29d893e89a30995559ee7167814c096dc24599679156c",
              "docs/decisions/OD_2026_10_01_A9_11_S4_P2_OWNER_DECISIONS.md",
              "4a9fd171abc6a63266a34e6a7c4cb25c4d67ed16615715e158902a57f7071a41"),
    "A9.14": ("docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
              "2a61c761120863c4b5821043ab78b6f9b28227584f7d83cb48ecd6598ed0af07"),
    "A9.15": ("docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903"),
}
ORDER = ("A9.8", "A9.10", "A9.11", "A9.14", "A9.15")
TEST_REL = "tests/test_p2_a9_16_owner_rules.py"


def decision_pins():
    """(key, path, sha256, what) for the builder's DECISIONS table (verified like every other pin)."""
    out = {}
    for k in ORDER:
        j, js, m, ms = DEC[k]
        tag = k.replace(".", "")
        out[tag] = (j, js, "owner %s (machine-readable; A9.16 step 1)" % k)
        out[tag + "MD"] = (m, ms, "owner %s verbatim (governs over the json summary; A9.16 step 1)" % k)
    return out


# (decision, question id, sequenced no, owner answer code, how applied, where implemented, tests)
APPLIED = [
    ("A9.11", "P2Q-01", "S4.2", "YES_ZM_A_PRIMARY_ZM_B_PER_POINT_ZM_C_R",
     "ZM-A (phase-resolved V/I at RP-VI de-embedded to RP-ANT) is the primary bench Z_antenna method; ZM-B (RP-CPL "
     "complex-reflection de-embedding through the characterized line + match) is the mandatory cross-check at every "
     "valid bench map point; ZM-C (calibrated antenna RF current + VERIFIED delivered power) is the independent R / "
     "power-loading cross-check only; each method carries its own uncertainty budget; a reduced record states "
     "zm_cross_check_status and zm_a_independently_verified = false - only an AGREEMENT of method_agreement sets it, a "
     "missing / invalid ZM-B never does",
     "p2_impedance_reducer.reduce_record (zm_cross_check_status); p2_a9_16_rules.method_agreement, "
     "zm_c_resistance_crosscheck",
     ["test_p2_a9_16_zm_b_missing_never_verifies_zm_a", "test_p2_a9_16_reducer_zm_status",
      "test_p2_a9_16_zm_c_needs_verified_delivered_power"]),
    ("A9.11", "P2Q-03", "S4.3", "K_AGREEMENT_2_0_METHOD_DISAGREEMENT_VS_PHYSICAL_HYSTERESIS",
     "k_agreement = 2.0: z_R = |R_A - R_B| / u_c(R_A - R_B) and z_X likewise (correlation when established) must both "
     "be <= 2.0; METHOD_DISAGREEMENT keeps both raw measurements, no average, and blocks ZM-B stand-only "
     "qualification; up / down at the same registered factor level: z_hyst <= 2.0 -> "
     "NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY, > 2.0 -> RESOLVED_HYSTERESIS (physical finding preserved in "
     "the map, never a FAIL), reported against P_forward and VERIFIED P_delivered (HM-R05)",
     "p2_a9_16_rules.method_agreement, updown_hysteresis, hysteresis_power_bases; p2_framework.hysteresis "
     "(judgement text)",
     ["test_p2_a9_16_method_agreement_k2", "test_p2_a9_16_updown_hysteresis_classes",
      "test_p2_a9_16_hysteresis_bases_need_verified_delivered"]),
    ("A9.11", "P2Q-04", "S4.4", "YES_RETUNED_PRIMARY_PLUS_FIXED_TUNE_SUB_SWEEPS",
     "every primary hot-map point re-tuned to the registered minimum-reflected-power condition with matching-state id, "
     "element positions / encoder values, tune time and residual reflection logged; only characterized tuning states "
     "(positions equal the characterized ones) or the VERIFIED CAL-P2-03 / CAL-P2-04 interpolation rule; fixed-tune "
     "sub-sweeps around pre-registered representative regions (stable nominal, envelope edge, near an E/H or "
     "impedance transition, flight-match design region - where available) whose selection rule is frozen before the "
     "sub-sweep data are interpreted; they supplement, never replace, the primary re-tuned map; no region chosen here",
     "p2_a9_16_rules.retune_point_check, fixed_tune_subsweep_check",
     ["test_p2_a9_16_retune_point_rules", "test_p2_a9_16_fixed_tune_selection_rule_frozen_first"]),
    ("A9.11", "P2Q-07", "S4.5", "YES_IN_HOUSE_VNA_TRACEABLE_WHERE_NO_ACCREDITED_SCOPE",
     "accredited ISO/IEC 17025 / NABL route needs a scope covering magnitude AND relative phase at 13.56 MHz; "
     "otherwise the in-house route needs the stated no-scope basis and every listed element (VNA / kit certificates, "
     "complex V/I gain at 13.56 MHz, short / open / known-load checks as applicable, precision 50-ohm reference, "
     "VNA-characterized reactive reference, RP-VI -> RP-ANT fixture characterization or verified coincidence, pre / post "
     "checks, probe / cable temperature and phase drift, repeatability, full magnitude + relative-phase uncertainty "
     "propagation, configuration ids / raw data / hashes); relative phase uncertainty explicit, never inferred from "
     "magnitude; VERIFIED CAL-P2-15 at-power validation; labelled in-house traceable (not an accredited certificate); "
     "uncertainty inadequate for the REGISTERED required discrimination -> NOT_EVALUATED_INSTRUMENT (never reduced "
     "administratively; no discrimination number set here)",
     "p2_a9_16_rules.vi_calibration_check, vi_measurement_adequacy",
     ["test_p2_a9_16_vi_calibration_routes", "test_p2_a9_16_vi_adequacy_registration_slot"]),
    ("A9.11", "P2Q-08", "S4.6", "YES_ICPQ06_COVERS_ICP34_WHEN_BRIDGING",
     "every ICP plumbing or pressure-sensing path (incl. ICP-34) that can bridge two intended isolated potentials "
     "(grounded transducer, chamber / facility ground, grounded tubing / manifold, DAQ / instrument chassis, other "
     "reference) needs an isolating section and a qualification of the COMPLETE INSTALLED PATH (isolator, fittings, "
     "tubing, transducer / interface, feedthroughs, mounting, representative pressure / gas, floating / bias electrical "
     "configuration) showing no unintended current-return path against the registered single-point grounding "
     "topology; a demonstrably non-conductive, non-bridging line is documented instead of duplicate-tested; unknown "
     "-> no floating / biased point",
     "p2_a9_16_rules.isolation_path_check", ["test_p2_a9_16_isolation_path_rules"]),
    ("A9.11", "P2Q-09", "S4.7", "HM_R06_INDICATORS_K_TRANSITION_2_0",
     "photodiode retained (A9.4 P2Q-05); with optical UNLIT the HM-R06 non-optical indicators (reflected power / "
     "|Gamma| at fixed tuning, R / X where valid impedance data exist, antenna RF current, collector / current-path "
     "response, pressure) are each resolved when |dy| / u_c(dy) > k_transition = 2.0 (covariance when established); "
     "UNLIT + any resolved -> UNCERTAIN with electrical_indicator_basis listing exactly those indicators; line of sight "
     "lost / saturated / threshold unavailable -> UNCERTAIN regardless; lit -> the registered E/H rule, not "
     "overridden; form and k frozen before the first P2 hot-map reduction (registration slot); the absolute-step form "
     "of p2_framework is refused",
     "p2_a9_16_rules.classify_with_hm_r06, resolved_transition_indicators, transition_criteria_registration_check; "
     "p2_framework._check_criteria (K_TRANSITION)",
     ["test_p2_a9_16_hm_r06_classification", "test_p2_a9_16_transition_criteria_frozen_before_first_reduction",
      "test_p2_a9_16_framework_eh_form_fixed", "test_eh_criteria_never_defaulted (updated)"]),
    ("A9.10", "P1Q-24", "S3.8", "K_LOSS_2_0_P1_AND_P2_FAIL_CLOSED_UPPER_BOUND",
     "the same k_loss = 2.0 in the P2 at-power loss verification CAL-P2-09 / CAL-P2-10 (|eta_meas - eta_pred| / u_c "
     "<= 2), never relaxed separately: the MET-07 protocol registry refuses any protocol with k != 2.0 and "
     "verify_line_match_loss refuses k != 2.0; until the verification passes P_delivered is reported only as the upper "
     "bound P_net (P_delivered_upper_bound_W, UPPER_BOUND_UNVERIFIED_LOSS); small-signal S-parameters alone never "
     "upgrade the loss model; a failed check is investigated, the tolerance is not widened",
     "p2_impedance_reducer.K_LOSS, loss_check_protocol, _upper_bound; p2_framework.verify_line_match_loss",
     ["test_p2_a9_16_k_loss_registry_refuses_other_k", "test_p2_a9_16_upper_bound_until_verified",
      "test_met07_r1_* / r2_r3 / r4 / r5 (updated to k = 2.0)"]),
    ("A9.8", "P2Q-02", "S1.6", "SEPARATE_RF_METROLOGY_PACKAGE",
     "V/I probe, VNA, calibration kits, fixed attenuators, antenna-simulator load, antenna current probe, phase-stable "
     "VNA cables and associated calibration accessories belong to a dedicated RF-METROLOGY package under the common "
     "interface specification, separate from RF power generation / matching (instrument_list.procurement_package_a9_8); "
     "the RFQ v2 line ids stay as cross-checked (re-mapping is the RFQ lane's work); quotation only",
     "a9_16_application.PROCUREMENT_PACKAGE (instrument_list)", ["test_p2_a9_16_rf_metrology_package"]),
    ("A9.14", "ICPQ-11", "S8.4", "K_RF_1_5",
     "antenna-circuit voltage rating >= 1.5 x V_ant,peak at the worst measured P2 mismatch / operating point "
     "(RC-ANT-V candidate); Paschen, creepage / clearance and combined RF + DC stress stay separately qualified (OPEN); "
     "a more stringent supplier / qualification requirement governs",
     "p2_framework.K_RF, rating_structure", ["test_p2_a9_16_rating_policy_stress_classes"]),
    ("A9.14", "P2Q-10", "S9.6", "RF_RATING_POLICY_V1_5_PI_1_25_THERMAL_1_20",
     "stress-class factors on the measured envelope maximum: RF voltage 1.5 x, continuous RF power / current 1.25 x, "
     "thermal 1.20 x, start-up / reflected / transient below the manufacturer's documented transient / peak rating; "
     "the more stringent supplier derating governs (max, never the product); candidates only - RF_COMPONENT_RATINGS "
     "stays TBD_AFTER_IMPEDANCE_MAP",
     "p2_framework.rating_structure (RATING_STRESS_CLASS, STRESS_CLASS_FACTORS); p2_a9_16_rules.transient_stress_check",
     ["test_p2_a9_16_rating_policy_stress_classes", "test_p2_a9_16_transient_below_manufacturer_rating",
      "test_rating_structure_never_rates (updated)"]),
    ("A9.14", "P2Q-06", "S8.32", "ZM_B_THRUST_STAND_AFTER_ZM_A_AGREEMENT",
     "ZM-B on the thrust stand only after demonstrated ZM-A / ZM-B bench agreement (every bench comparison "
     "AGREEMENT_WITHIN_K; unresolved METHOD_DISAGREEMENT blocks); ZM-A stays the bench reference and the periodic / "
     "after-change cross-check (a stand record needs an agreeing ZM-A cross-check for its configuration and the "
     "registered periodic interval - slot, no number); no unnecessary V/I probe line across the moving stage",
     "p2_a9_16_rules.zm_b_stand_qualification, stand_zm_b_record_check", ["test_p2_a9_16_zm_b_stand_rules"]),
    ("A9.14", "F6-OQ-02", "S7.7", "DRAWING_HARD_BOUNDS_BENCH_EVIDENCE_POINTS",
     "the KC-1 / ICP LOCK-1 drawing envelope is the hard bound; the registered P1 / P2 geometry matrix marks evidenced "
     "points inside it only; a point outside, on another revision or with an unbounded variable is refused (a test "
     "matrix never enlarges the envelope without a drawing revision); no envelope -> NOT_EVALUATED_REGISTRATION",
     "p2_a9_16_rules.geometry_point_check", ["test_p2_a9_16_geometry_inside_drawing_envelope"]),
]

NOT_APPLICABLE = [
    ("A9.15", "RFP propellant policy (amends A9.13 / A9.14 S8.17, S8.21, S8.33, S8.35, S9.3, S9.10)",
     "reviewed: no P2 text restricts Xe to a C1 contingency; P2 gas modes keep the A9.1 ICP gas-mode baseline "
     "(G-REUSE primary, G-XE a declared ICP-feed variant) unchanged; the RFP air + Xe dual-propellant capability is a "
     "system requirement outside the P2 impedance-map methodology"),
    ("A9.11", "P1Q-01", "P1 stable-region criteria form (P1 lane); P2 consumes the handoff unchanged via "
     "p2_framework.p1_handoff_admissible (pair XL-01 text owned jointly with P1, not edited here)"),
]

# id -> (new value or None, new status or None, decision key, question id, note)
ITEM_UPDATES = {
    "FW-08": (None, "OWNER_GIVEN", "A9.10", "P1Q-24", "k = k_loss = 2.0 (FW-09); fail-closed upper-bound rule"),
    "FW-09": (2.0, "OWNER_GIVEN", "A9.10", "P1Q-24",
              "k_loss = 2.0 for P1 and P2 (CAL-P2-09 / CAL-P2-10); every MET-07 protocol must carry it"),
    "FW-10": ("k x combined step uncertainty with k_transition = 2.0 over the HM-R06 indicator set (absolute-step form "
              "refused); frozen before the first P2 hot-map reduction", "OWNER_GIVEN", "A9.11", "P2Q-09",
              "p2_framework._check_criteria; p2_a9_16_rules.classify_with_hm_r06"),
    "FW-12": ("z_hyst = |Y_up - Y_down| / u_c(Y_up - Y_down) at the same registered factor level; <= 2.0 "
              "NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY, > 2.0 RESOLVED_HYSTERESIS (physical finding, not a "
              "FAIL); reported vs P_forward and verified P_delivered", "OWNER_GIVEN", "A9.11", "P2Q-03",
              "p2_a9_16_rules.updown_hysteresis"),
    "FW-17": ("candidate minimum = governing stress-class factor x complete measured envelope maximum (RF voltage 1.5, "
              "continuous RF power / current 1.25, thermal 1.20; stricter supplier derating governs, never the "
              "product), status REQUIRED_MINIMUM_UNDER_OWNER_POLICY_NOT_A_RATING; otherwise TBD_AFTER_EVIDENCE; "
              "RF_COMPONENT_RATINGS stays TBD_AFTER_IMPEDANCE_MAP", "OWNER_GIVEN", "A9.14", "P2Q-10",
              "p2_framework.rating_structure"),
    "FW-18": (1.5, "OWNER_GIVEN", "A9.14", "ICPQ-11",
              "antenna-circuit voltage rating >= 1.5 x V_ant,peak at the worst measured P2 point; Paschen / creepage / "
              "combined RF+DC qualification separate"),
    "FW-20": ("RF voltage 1.5 x; continuous RF power / current 1.25 x; thermal 1.20 x; transient below the "
              "manufacturer transient / peak rating (all on the measured envelope maximum)", "OWNER_GIVEN", "A9.14",
              "P2Q-10", "stress-class policy RF_RATING_POLICY_V1_5_PI_1_25_THERMAL_1_20"),
    "HM-F08": ("policy (owner): every primary point re-tuned to the registered minimum-reflected-power condition "
               "(matching-state id, encoder values, tune time, residual reflection logged; characterized states or "
               "the verified CAL-P2-03/04 interpolation only) plus fixed-tune sub-sweeps around pre-registered "
               "representative regions (selection rule frozen before interpretation; supplement, not replacement)",
               "OWNER_GIVEN", "A9.11", "P2Q-04", "p2_a9_16_rules.retune_point_check / fixed_tune_subsweep_check"),
    "HM-R05": ("every 1-D sweep is run up and down; the map and any hysteresis are reported against P_forward AND "
               "verified P_delivered (RF-DALT08-01); up / down rule (owner): z_hyst <= 2.0 "
               "NO_HYSTERESIS_RESOLVED_AT_REGISTERED_UNCERTAINTY, > 2.0 RESOLVED_HYSTERESIS - a physical finding "
               "preserved in the map, never automatically a FAIL", "OWNER_GIVEN", "A9.11", "P2Q-03",
               "p2_a9_16_rules.updown_hysteresis / hysteresis_power_bases"),
    "HM-R06": (None, "OWNER_GIVEN", "A9.11", "P2Q-09",
               "multiple fixed: k_transition = 2.0 on |dy| / u_c(dy) (form k x u_c), frozen before the first P2 "
               "hot-map reduction; optical UNLIT + resolved indicator -> UNCERTAIN (electrical_indicator_basis)"),
    "HM-R07": ("per record: matching-state id, element positions / encoder values, auto-tune on / off, tune time, "
               "residual reflection, loss-bound id if used", "OWNER_GIVEN", "A9.11", "P2Q-04",
               "residual reflection added by the owner answer"),
    "MS-P2-03": ("accredited ISO/IEC 17025 / NABL scope (magnitude AND relative phase at 13.56 MHz) where one exists, "
                 "otherwise the in-house procedure traceable through the calibrated VNA and kit with the owner's "
                 "minimum content, explicit relative-phase uncertainty and CAL-P2-15 at-power validation, labelled "
                 "in-house traceable; inadequate uncertainty -> NOT_EVALUATED_INSTRUMENT", "OWNER_GIVEN", "A9.11",
                 "P2Q-07", "p2_a9_16_rules.vi_calibration_check"),
    "CAL-P2-09": (None, None, "A9.10", "P1Q-24", "acceptance |eta_meas - eta_pred| / u_c <= k_loss = 2.0 (never relaxed "
                                                 "in P2)"),
    "CAL-P2-10": (None, None, "A9.10", "P1Q-24", "acceptance |eta_meas - eta_pred| / u_c <= k_loss = 2.0 (never relaxed "
                                                 "in P2)"),
    "CAL-P2-05": (None, None, "A9.11", "P2Q-07", "route per p2_a9_16_rules.vi_calibration_check"),
}

# P2Q-02 (A9.8 S1.6): instrument -> procurement package (the RFQ lane re-maps the RFQ line ids)
RF_METROLOGY = "RF_METROLOGY_PACKAGE (A9.8 P2Q-02; separate from RF power generation / matching)"
PROCUREMENT_PACKAGE = {
    "INS-P2-01": RF_METROLOGY, "INS-P2-04": RF_METROLOGY, "INS-P2-05": RF_METROLOGY, "INS-P2-06": RF_METROLOGY,
    "INS-P2-07": "(a) 50-ohm calorimetric load: not named by P2Q-02 (placement unchanged); (b) antenna-simulator load: "
                 + RF_METROLOGY,
    "INS-P2-08": "phase-stable VNA test cables: " + RF_METROLOGY + "; flexible live / sham stand-crossing pair: not "
                 "named by P2Q-02 (placement unchanged)",
    "INS-P2-09": RF_METROLOGY,
    "INS-P2-02": "not named by P2Q-02 (placement unchanged)", "INS-P2-03": "not named by P2Q-02 (placement unchanged)",
    "INS-P2-10": "not named by P2Q-02 (A9.4 P2Q-05 procurement unchanged)",
    "INS-P2-11": "not named by P2Q-02 (placement unchanged)",
    "INS-P2-12": "RF power generation / matching hardware (match element read-out; not measurement equipment of P2Q-02)",
}

FAIL_CLOSED = [
    ("ZM-B missing / invalid at a bench point", "ZM_B_MISSING_OR_INVALID; ZM-A not independently verified",
     "test_p2_a9_16_zm_b_missing_never_verifies_zm_a"),
    ("z_R or z_X > 2.0", "METHOD_DISAGREEMENT (raws kept, no average, stand qualification blocked)",
     "test_p2_a9_16_method_agreement_k2"),
    ("ZM-C with unverified delivered power", "NOT_EVALUATED_LOSS_UNVERIFIED", "test_p2_a9_16_zm_c_needs_verified_delivered_power"),
    ("loss-check protocol with k != 2.0", "refused (RecordError / CriteriaMissingError)",
     "test_p2_a9_16_k_loss_registry_refuses_other_k"),
    ("unverified loss", "P_delivered REFUSED; only P_delivered_upper_bound_W (UPPER_BOUND_UNVERIFIED_LOSS)",
     "test_p2_a9_16_upper_bound_until_verified"),
    ("uncharacterized tuning state / incomplete re-tune log", "REFUSED_*", "test_p2_a9_16_retune_point_rules"),
    ("fixed-tune selection rule frozen after interpretation", "REFUSED_SELECTION_RULE_NOT_FROZEN_BEFORE_INTERPRETATION",
     "test_p2_a9_16_fixed_tune_selection_rule_frozen_first"),
    ("in-house V/I calibration incomplete / phase from magnitude / no CAL-P2-15", "REFUSED_* / NOT_EVALUATED_*",
     "test_p2_a9_16_vi_calibration_routes"),
    ("uncertainty above the registered discrimination / no registration", "NOT_EVALUATED_INSTRUMENT / "
     "NOT_EVALUATED_REGISTRATION", "test_p2_a9_16_vi_adequacy_registration_slot"),
    ("bridging sensing / plumbing path not qualified as installed", "NOT_EVALUATED_ISOLATION_NOT_QUALIFIED (no floating "
     "/ biased point)", "test_p2_a9_16_isolation_path_rules"),
    ("optical UNLIT with resolved HM-R06 indicator / LOS lost / saturated / no threshold", "UNCERTAIN",
     "test_p2_a9_16_hm_r06_classification"),
    ("transition criteria frozen at / after the first hot-map reduction", "NOT_EVALUATED_REGISTRATION",
     "test_p2_a9_16_transition_criteria_frozen_before_first_reduction"),
    ("absolute-step or k != 2.0 E/H criteria", "CriteriaMissingError", "test_p2_a9_16_framework_eh_form_fixed"),
    ("ZM-B stand use without bench agreement / ZM-A after-change cross-check / periodic interval", "NOT_QUALIFIED / "
     "NOT_EVALUATED_*", "test_p2_a9_16_zm_b_stand_rules"),
    ("k_rf other than 1.5", "RatingInputError", "test_p2_a9_16_rating_policy_stress_classes"),
    ("no manufacturer transient rating", "NOT_EVALUATED_NO_MANUFACTURER_TRANSIENT_RATING",
     "test_p2_a9_16_transient_below_manufacturer_rating"),
    ("geometry point outside the drawing envelope / no envelope", "REFUSED_OUTSIDE_DRAWING_ENVELOPE_NEEDS_DRAWING_REVISION"
     " / NOT_EVALUATED_REGISTRATION", "test_p2_a9_16_geometry_inside_drawing_envelope"),
]

EXISTING_TESTS_UPDATED = [
    "tests/test_p2_impedance_framework.py::test_eh_detection_classes (k x u_c, k = 2.0 replaces the absolute-step form)",
    "tests/test_p2_impedance_framework.py::test_eh_criteria_never_defaulted (absolute-step and k != 2.0 now refused)",
    "tests/test_p2_impedance_framework.py::test_hysteresis_reported_not_judged (criteria k = 2.0)",
    "tests/test_p2_impedance_framework.py::test_sw09_sweep_index_type_checked (criteria k = 2.0)",
    "tests/test_p2_impedance_framework.py::test_met07_r1_shifted_eta_pred_cannot_flip_inconsistent_to_verified "
    "(protocol k = 2.0, u_eta_pred 0.03)",
    "tests/test_p2_impedance_framework.py::test_met07_r2_r3_protocol_fixes_k_and_uncertainties (k = 2.0)",
    "tests/test_p2_impedance_framework.py::test_met07_r4_check_power_and_application_range_fixed (k = 2.0)",
    "tests/test_p2_impedance_framework.py::test_met07_r5_check_load_registered (k = 2.0)",
    "tests/test_p2_impedance_framework.py::test_rating_structure_never_rates (owner stress-class policy)",
    "tests/test_p2_impedance_framework.py::test_a96_pins_items_questions_and_statuses (FW items owner-given, no open "
    "questions)",
    "tests/test_p2_impedance_prep.py::test_a94_p2q05_answered_and_items (P2Q-09 answered)",
    "tests/test_p2_impedance_prep.py::test_no_prediction_no_rating_no_pass (ICPQ-11 owner-given)",
]


def _ref(key, q):
    j, js, m, ms = DEC[key]
    return {"kind": key, "path": j, "sha256": js, "decision": q, "verbatim": m, "verbatim_sha256": ms}


def owner_answer_rows():
    rows = []
    for d, q, sq, code, how, where, tests in APPLIED:
        rows.append({"ref": _ref(d, q), "how": "APPLIED A9.16 step 1 (%s, %s %s): %s [implemented in %s; tests %s]"
                     % (code, sq, q, how, where, ", ".join(tests)),
                     "question_id": q, "sequenced_no": sq, "owner_answer": code, "implemented_in": where,
                     "tests": list(tests)})
    for d, q, why in NOT_APPLICABLE:
        rows.append({"ref": _ref(d, q.split(" ")[0]), "how": "REVIEWED, NOT_APPLICABLE to the P2 artifacts: " + why,
                     "question_id": q, "sequenced_no": None, "owner_answer": None, "implemented_in": None, "tests": []})
    return rows


def _update_item(x):
    up = ITEM_UPDATES.get(x["id"])
    if up is None:
        return x
    x = dict(x)
    val, status, dkey, q, note = up
    j, js, _m, _ms = DEC[dkey]
    if val is not None:
        x["value"] = val
        x["evidence_class"] = "owner-stated"
    if status is not None:
        x["status"] = status
    src = x.get("source")
    tag = "%s %s (%s, sha256 %s)" % (dkey, q, j, js)
    x["source"] = (list(src) if isinstance(src, list) else [src] if src else []) + [tag]
    x["owner_answers_applied"] = (x.get("owner_answers_applied") or []) + [
        {"decision": dkey, "question_id": q, "decision_file": j, "decision_json_sha256": js, "note": note}]
    return x


def apply(doc, oq_rows):
    """Apply the A9.16 step-1 owner decisions to the built P2 document (deterministic, returns a new document)."""
    d = copy.deepcopy(doc)
    for key in ("chain_parameters", "reference_planes", "calibration_plan", "uncertainty_items_new",
                "metrology_items_new", "instrument_list", "items"):
        d[key] = [_update_item(x) for x in d[key]]
    hm = d["hot_map_methodology"]
    hm["factors"] = [_update_item(x) for x in hm["factors"]]
    hm["rules"] = [_update_item(x) for x in hm["rules"]]
    # z_antenna methods / recommendation (P2Q-01, P2Q-03, P2Q-06)
    roles = {"ZM-A": "PRIMARY on the P1/P2 bench (A9.11 P2Q-01); bench reference and periodic / after-change "
                     "cross-check on the stand (A9.14 P2Q-06)",
             "ZM-B": "MANDATORY CROSS-CHECK at every valid bench map point (A9.11 P2Q-01); thrust-stand method only "
                     "after demonstrated bench agreement (A9.14 P2Q-06)",
             "ZM-C": "INDEPENDENT R / power-loading CROSS-CHECK with verified delivered power, not the primary "
                     "complex-impedance method (A9.11 P2Q-01); resistance split"}
    for m in d["z_antenna_methods"]:
        m["status"] = "OWNER_GIVEN"
        m["role"] = roles[m["id"]]
        m["owner_answers_applied"] = [{"decision": "A9.11", "question_id": "P2Q-01", "decision_file": DEC["A9.11"][0],
                                       "decision_json_sha256": DEC["A9.11"][1]}]
    r = d["z_antenna_recommendation"]
    r["status"] = "OWNER_GIVEN"
    r["transfer_rule"] = ("on the thrust stand ZM-B is used (no unnecessary V/I probe line across the moving stage) only "
                          "after ZM-A / ZM-B bench agreement is demonstrated under k_agreement = 2.0 (z_R, z_X <= 2.0 "
                          "at every valid bench point; an unresolved METHOD_DISAGREEMENT blocks); ZM-A remains the bench "
                          "reference and the periodic / after-change cross-check (A9.14 P2Q-06; A9.11 P2Q-03)")
    r["owner_answers_applied"] = [
        {"decision": k, "question_id": q, "decision_file": DEC[k][0], "decision_json_sha256": DEC[k][1]}
        for k, q in (("A9.11", "P2Q-01"), ("A9.11", "P2Q-03"), ("A9.14", "P2Q-06"))]
    # instruments (P2Q-02)
    for i in d["instrument_list"]:
        i["procurement_package_a9_8"] = PROCUREMENT_PACKAGE[i["id"]]
    # outputs later (ICPQ-11 answered; ICPQ-10 / OQ-A910-06 not in this lane's assignment)
    for o in d["p2_outputs_later"]:
        if o["id"] == "ICPQ-11":
            o["status"] = ("OWNER_GIVEN (A9.14 S8.4 K_RF_1_5: rated antenna-circuit voltage >= 1.5 x V_ant,peak at the "
                           "worst measured P2 mismatch / operating point; candidate only, rating "
                           "TBD_AFTER_IMPEDANCE_MAP)")
            o["source"] = DEC["A9.14"][0]
    for x in d["interface_demands"]:
        if x["id"] == "IDP2-22":
            x["status"] = ("ANSWERED except ICPQ-10: ICPQ-11 k_RF = 1.5 and P2Q-10 stress-class margins (A9.14), P2Q-09 "
                           "k_transition = 2.0 and P2Q-03 k_agreement = 2.0 (A9.11), loss-check k = 2.0 (A9.10 P1Q-24); "
                           "ICPQ-10 not applied by this lane (heat_load_option stays an explicit input)")
    # framework capability texts that named the questions as open
    for c in d["framework"]["capabilities"]:
        if c["a9_6_sec9_item"] == "E/H-mode transition detection":
            c["data_needed"] = ("criteria owner-fixed (A9.11 P2Q-09 k_transition = 2.0; P2Q-03 k_agreement = 2.0); "
                                "thresholds = 2.0 x the measured combined step uncertainties (frozen before the first "
                                "hot-map reduction)")
        if c["a9_6_sec9_item"] == "rating derivation":
            c["data_needed"] = ("complete measured envelope; owner factors A9.14 ICPQ-11 / P2Q-10 given; ICPQ-10 "
                                "heat-load bound an explicit input")
        if c["a9_6_sec9_item"] == "RF line/match loss":
            c["data_needed"] = "two-port data + calorimetric check; k = k_loss = 2.0 (A9.10 P1Q-24)"
    for o in d["owner_answers_applied"]:
        if isinstance(o["ref"], dict) and o["ref"].get("kind") == "A9.6" and o["ref"].get("decision") == "sec. 7":
            o["how"] += (" [superseded 2026-10-01: ICPQ-11 by A9.14 S8.4, P2Q-03 / P2Q-09 by A9.11 S4.3 / S4.7 - see "
                         "a9_16_incorporation; ICPQ-10 not applied by this lane]")
    d["owner_answers_applied"] += owner_answer_rows()
    # open questions: every former P2 question is answered (A9.8 / A9.11 / A9.14)
    answered = {"P2Q-01": ("A9.11", "S4.2"), "P2Q-02": ("A9.8", "S1.6"), "P2Q-03": ("A9.11", "S4.3"),
                "P2Q-04": ("A9.11", "S4.4"), "P2Q-06": ("A9.14", "S8.32"), "P2Q-07": ("A9.11", "S4.5"),
                "P2Q-08": ("A9.11", "S4.6"), "P2Q-09": ("A9.11", "S4.7"), "P2Q-10": ("A9.14", "S9.6")}
    former = d["open_owner_questions"]
    if {q["id"] for q in former} != set(answered):
        raise SystemExit("A9.16: former P2 open questions %s != answered set %s"
                         % (sorted(q["id"] for q in former), sorted(answered)))
    d["answered_owner_questions"] = [dict(q, status="ANSWERED", answered_by={
        "decision": answered[q["id"]][0], "sequenced_no": answered[q["id"]][1], "decision_file": DEC[answered[q["id"]][0]][0],
        "decision_json_sha256": DEC[answered[q["id"]][0]][1], "verbatim": DEC[answered[q["id"]][0]][2]})
        for q in former]
    d["open_owner_questions"] = []
    for q in answered:
        if q in oq_rows:
            raise SystemExit("A9.16: %s collides with state v3" % q)
    d["what_this_is_not"] = [x if x != "an answer to any open owner question" else
                             "an answer to any owner question (owner answers of 2026-10-01 are applied, not made)"
                             for x in d["what_this_is_not"]]
    return d


def incorporation(red, fw, rules, selfcheck):
    return {
        "step": "A9.16 step 1 (owner instruction 2026-10-01 'continue implementing them sequentially'), lane P2 "
                "IMPEDANCE MAP",
        "decisions": [{"decision": k, "json": DEC[k][0], "json_sha256": DEC[k][1], "verbatim": DEC[k][2],
                       "verbatim_sha256": DEC[k][3]} for k in ORDER],
        "reading_rule": "The verbatim .md of every applied decision was read in full; it governs over the json "
                        "'summary' digest; A9.15 governs wherever older text restricts Xe to a C1 contingency (none in "
                        "P2); A9.1 ICP gas-mode baseline unchanged",
        "applied": [{"decision": dd, "question_id": q, "sequenced_no": sq, "owner_answer": c, "implemented_in": w,
                     "tests": t} for dd, q, sq, c, _h, w, t in APPLIED],
        "not_applicable": [{"decision": dd, "question_ids": q, "why": w} for dd, q, w in NOT_APPLICABLE],
        "owner_numbers_used": {"k_agreement": rules.K_AGREEMENT, "k_transition": rules.K_TRANSITION,
                               "k_loss": red.K_LOSS, "k_RF": fw.K_RF, "continuous_RF_power_current_factor":
                               fw.K_CONTINUOUS_PI, "thermal_dissipation_factor": fw.K_THERMAL},
        "registration_slots_not_filled": [
            "required impedance discrimination u_R / u_X (P2Q-07)", "periodic ZM-A cross-check interval on the stand "
            "(P2Q-06)", "fixed-tune representative-region selection rule (P2Q-04)", "CAL-P2-03/04 interpolation rule "
            "verification (P2Q-04)", "HM-R06 transition-criteria registration id / freeze time (P2Q-09)",
            "LOCK-1 drawing envelope bounds (F6-OQ-02)", "manufacturer transient / peak ratings (P2Q-10)",
            "isolation qualification records of bridging paths incl. ICP-34 (P2Q-08)",
            "photodiode threshold HM-R15 (unchanged, A9.4 P2Q-05)"],
        "modules": {"rules": "docs/experiments/hall_icp/p2_impedance_map/p2_a9_16_rules.py",
                    "application": "docs/experiments/hall_icp/p2_impedance_map/a9_16_application.py",
                    "tests": TEST_REL},
        "selfcheck": selfcheck,
        "fail_closed": [{"case": c, "outcome": o, "test": TEST_REL + "::" + t} for c, o, t in FAIL_CLOSED],
        "existing_tests_updated": EXISTING_TESTS_UPDATED,
        "pinning_note": "the P2 json / reducer / framework are read or sha-pinned by other packages (P1, P3, RFQ v2, "
                        "state v4, RVM, M16 v4, F6, freeze candidate): the integration lane re-pins / rebuilds; nothing "
                        "outside this lane's paths was edited; cross-lane pair texts (XL-nn) unchanged",
        "statuses_unchanged": "RF_COMPONENT_RATINGS TBD_AFTER_IMPEDANCE_MAP; ICP_COUPLED_THERMAL UNRESOLVED; anode OPEN; "
                              "ICP45 NOT_EVALUATED; C1 CONTROL_FALLBACK; no PASS anywhere",
    }
