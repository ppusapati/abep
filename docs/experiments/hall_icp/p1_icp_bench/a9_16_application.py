"""A9.16 step 1 - owner decisions of 2026-10-01 applied to the P1 ICP bench package (lane P1 ICP BENCH).

Data module read by build_p1_icp_bench.py (deterministic; no I/O of its own). Each applied decision is cited by its
immutable decision file path, the sha256 of its machine-readable json and the question id; the VERBATIM .md of every
decision was read in full and governs over the json 'summary' digest. Owner-supplied numbers used here are exactly the
owner's (k_loss = 2.0; 700 V DC / 60 s; >= 525 V / 1.05 kV DC 60 s; UBQ-06 limit - 50 K; 8.33 A only as the stand
ceiling; at most 1 + 2 start attempts in the OD5 baseline sequence; >= 3 independent re-ignitions). Every number the
owner deferred to a later registration is a registration slot with a fail-closed refusal - never invented here.
"""

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


def pins():
    out = []
    for k in ("A9.8", "A9.10", "A9.11", "A9.14", "A9.15"):
        j, js, m, ms = DEC[k]
        out.append((j, js, "owner %s (machine-readable; A9.16 step 1)" % k))
        out.append((m, ms, "owner %s verbatim (governs over the json summary; A9.16 step 1)" % k))
    return out


# (decision, question id, sequenced no, owner answer code, how applied, where implemented, tests)
APPLIED = [
    ("A9.8", "P1Q-04", "S1.1", "YES",
     "UBQ-06 abort / derate (validated continuous-use limit - 50 K) on ALL P1 operation incl. non-scoring runs: the "
     "P1-G0 readiness record registers the validated limits of every component temperature channel (null -> "
     "G0_NOT_EVALUATED_TBD); every later record at / above limit - 50 K is OUT_OF_DOMAIN with the abort / derate reason "
     "and listed in owner_rules_a9_16.thermal_protection; never a thermal PASS (ICP_COUPLED_THERMAL stays UNRESOLVED)",
     "p1_reducer.reduce_readiness (thermal_limits); p1_a9_16_rules.thermal_abort_rows; p1_campaign",
     ["test_p1_a9_16_thermal_abort_all_operation", "test_p1_a9_16_readiness_thermal_limits_required"]),
    ("A9.8", "P1Q-09", "S1.2", "DEDICATED_ISOLATED_TARGET_NO_CHAMBER_WALL",
     "dedicated isolated electron-collecting target for ICP45_CAPACITY AND the P1-S4 ENGINEERING_SURFACE records; the "
     "chamber wall (CHAMBER_WALL_FACILITY_GROUND) is REFUSED as electron collector for every record; V_collector is "
     "referenced to the target (ELECTRON_COLLECTOR_ELECTRODE) and must be < 0 (ICP ion-collecting electrode biased "
     "negative w.r.t. the target, potential recorded); six terminals collector_supply, icp_body, facility_ground, "
     "electron_collector, h1_body, hall_anode required; OPEN_CIRCUIT_BY_CONSTRUCTION only with a recorded "
     "physical_verification_id; target geometry registered at P1-G0 (extraction.target_geometry_id, readiness "
     "registration electron_collector_target_geometry_id) - no dimension invented; 316L stays acceptable for the Ar "
     "engineering article only (A9.1 A9-03-collector), not a flight collector material",
     "p1_reducer.validate_operating_point (REFUSED_EXTRACTION_ELECTRODES, P1Q09_TERMINALS, TARGET_GEOMETRY_FIELD, "
     "OPEN_CIRCUIT_VERIFICATION_FIELD)",
     ["test_p1_a9_16_chamber_wall_refused_surface_and_capacity", "test_p1_a9_16_target_bias_reference_and_geometry",
      "test_p1_a9_16_open_circuit_needs_physical_verification", "test_extraction_topology_rules (updated)"]),
    ("A9.8", "P1Q-11", "S1.3", "DERIVE_FROM_INSTALLED_GAUGE",
     "pressure-match tolerance is a registration (criteria_id, p_chamber_rel_tol, gauge_id, derived_from_record_ids of "
     "P1-S2 / P1-S3 records, repeatability_basis, frozen_utc) frozen before the first P1-S4 matched pair; one "
     "registration per campaign (immutable); not registered / not admissible -> the RF-OFF correction is not formed and "
     "the capacity point is NOT_EVALUATED_REGISTRATION; an unmatched pair stays an exclusion (P1-IT-51); no percentage "
     "is set here",
     "p1_a9_16_rules.check_pressure_match_registration; p1_campaign",
     ["test_p1_a9_16_pressure_match_registration", "test_a96_sec14_invalid_pair_excluded (updated)"]),
    ("A9.8", "P1Q-18", "S1.4", "CONFIRMED",
     "recorder reading confirmed and kept: full adequacy 3 u_R > 0.02 |I_e,collector| on the RF-ON ICP45_CAPACITY "
     "candidate; matched RF-OFF record floor-based (I_scale,min); a fractional-only RF-OFF resolution failure is "
     "NOT_EVALUATED_INSTRUMENT, not an exclusion",
     "p1_reducer.kirchhoff_closure / icp45a_candidates (unchanged)",
     ["test_met03_rf_off_adequacy_applied", "test_p1_a9_16_p1q18_confirmed_reading"]),
    ("A9.8", "P1Q-20", "S1.5", "YES",
     "an OPEN_CIRCUIT_BY_CONSTRUCTION terminal (floating H-1 anode, registered open terminals) never gets u = 0 by "
     "default: it carries leakage {dwv_path_id, leakage_upper_bound_A >= the leakage measured on that ACCEPTED DWV path "
     "of the governing P1-G0 record, u_leakage_A > 0} entering u_R as the zero-offset / leakage term; zero only when "
     "DEMONSTRABLY_NEGLIGIBLE under a registered closure_rule.leakage_negligibility_ratio_max (no default); missing / "
     "untraceable -> NOT_EVALUATED_UNCERTAINTY",
     "p1_reducer._leakage_uncertainty / kirchhoff_closure; p1_campaign (dwv_leakage_by_path from P1-G0)",
     ["test_p1_a9_16_open_circuit_leakage_enters_u_R", "test_p1_a9_16_leakage_negligible_only_registered",
      "test_p1_a9_16_campaign_leakage_traced_to_accepted_dwv"]),
    ("A9.8", "P1-IT-52", "S1.15", "STAGE_DOMAINS_FROM_REAL_HARDWARE",
     "every registered stage domain carries a unique domain_id, frozen_utc and its hardware basis; P_fwd_W, "
     "p_chamber_Pa, mdot_Ar_H1_mg_s, V_collector_V as [min, max]; frozen at / after the stage's first record -> that "
     "stage's records OUT_OF_DOMAIN (never a FAIL); 0-500 W stays the laboratory investigation capability, not a stage "
     "domain; no numbers set here",
     "p1_a9_16_rules.check_operating_domains / domain_freeze_reasons; p1_campaign",
     ["test_p1_a9_16_domain_registration_unique_and_frozen"]),
    ("A9.8", "P1-IT-55", "S1.16", "PER_PATH_DOCUMENTED_LEAKAGE_LIMIT",
     "per-path leakage limit = registered criterion with basis_document_id (most restrictive documented component / "
     "feedthrough / insulator / supplier specification), u_measurement_A and uncertainty_treatment, registered_utc "
     "before the test; flashover, breakdown, tracking / disruptive discharge or protective trip -> deficiency; no "
     "documented basis -> G0_NOT_EVALUATED_TBD (no universal uA value); accepted leakage feeds P1Q-20",
     "p1_reducer.reduce_readiness (LEAKAGE_ACCEPTANCE_REQUIRED, DWV_APPLICABLE_REQUIRED)",
     ["test_p1_a9_16_dwv_per_path_limit_rules"]),
    ("A9.8", "OQ-RFQV2-06", "S1.13", "YES",
     "the 350 V class / >= 525 V design withstand / 1.05 kV DC 60 s initial DWV applies to the H-1 anode / discharge-"
     "supply isolation and feedthrough paths: readiness requires a DWV record (tested, or not applicable with reason) "
     "of path class H1_ANODE_DISCHARGE_SUPPLY_350V_CLASS beside ICP_BODY_COLLECTOR_350V_CLASS; RF antenna / matching "
     "insulation, Paschen-risk gas paths and combined RF+DC stress stay separately qualified (P1-IT-46 OPEN)",
     "p1_reducer.reduce_readiness (DWV_REQUIRED_PATH_CLASSES)", ["test_p1_a9_16_dwv_path_classes_required"]),
    ("A9.8", "OQ-RFQV2-08", "S1.14", "BOTH_SUPPLIER_AND_IN_HOUSE",
     "every applicable DWV path: in-house current-limited 1.05 kV DC / 60 s on the ASSEMBLED configuration "
     "(test_configuration ASSEMBLED_SYSTEM_IN_HOUSE, configuration_id) before first HV / RF operation, plus a supplier / "
     "factory certificate id or the recorded reason the rating does not permit it; test voltage, duration, leakage, "
     "configuration and pass / fail observations recorded",
     "p1_reducer.reduce_readiness", ["test_p1_a9_16_dwv_in_house_assembled_and_supplier"]),
    ("A9.10", "P1Q-02", "S3.1", "HARDWARE_DERIVED_LIMITS_BEFORE_P1_S6",
     "registration slot start_attempt_limits {V_d_max_V <= V_qualified_envelope_V, I_limit_A <= min(I_h1_safe_A, "
     "I_supply_capability_A, 8.33 A stand ceiling), attempt_duration_max_s, max_attempts, cooldown_condition, thermal / "
     "isolation / interlock basis ids, frozen_utc}; frozen before the first P1-S6 record else P1-S6 OUT_OF_DOMAIN; the "
     "step-4 attempt outside the limits -> OUT_OF_DOMAIN_START_LIMITS_EXCEEDED; a later revision may not increase any "
     "limit after a failed ignition (refused); 8.33 A never I_d,max,H1",
     "p1_reducer.check_start_attempt_limits / reduce_topology_control; p1_a9_16_rules.check_start_limit_revisions",
     ["test_p1_a9_16_start_limits_bounds", "test_p1_a9_16_start_limits_never_raised_after_failure",
      "test_p1_a9_16_s6_entry_requires_registrations"]),
    ("A9.10", "P1Q-03", "S3.2", "PREREGISTERED_CURRENT_AND_TIME_CRITERION",
     "registration slot sustainment_definition {I_threshold_A > measured P1-M-22 pickup floor, u of the floor, "
     "min_duration_s, DAQ bandwidth, transient basis, frozen_utc}; SUSTAINED computed from the recorded I_d trace: "
     "supply enabled + connected, above threshold continuously >= min duration, not an artifact, no interlock; a "
     "recorded bool that contradicts the criterion is RECORD_AND_REVIEW, never resolved after the run",
     "p1_reducer.check_sustainment_definition / classify_sustained / reduce_topology_control",
     ["test_p1_a9_16_sustained_definition", "test_topology_control_paths (updated)"]),
    ("A9.10", "P1Q-05", "S3.3", "MIN_3_INDEPENDENT_REIGNITIONS",
     "ignition records carry start_state (EXTINGUISHED_RF_OFF) and restart_condition_met; per point all attempts count "
     "and independent_attempts are reported; a stable-region classification with < 3 independent re-ignitions is "
     "NOT_EVALUATED (INSUFFICIENT_REIGNITION_EVIDENCE); the minimum is repeatability evidence, never a PASS",
     "p1_reducer.validate_ignition / reduce_ignition / classify_stable_region",
     ["test_p1_a9_16_reignition_minimum_three", "test_sw01_stable_criteria_validated (updated)"]),
    ("A9.10", "P1Q-06", "S3.4", "BOTH_AS_FACTOR_F6",
     "h1_magnet_state OFF | REGISTERED_SETTING on ignition and operating-point records; magnet-on records carry "
     "h1_magnet_field_setting_id and the measured h1_coil_currents_A; in P1-S3..S5 a magnet-on record before the "
     "stage's magnet-OFF baseline is OUT_OF_DOMAIN (magnet OFF first); the fringe field is never assumed negligible",
     "p1_reducer.check_magnet_state; p1_a9_16_rules.magnet_order_reasons",
     ["test_p1_a9_16_magnet_factor_f6"]),
    ("A9.10", "P1Q-07", "S3.5", "DEDICATED_H1_C1_CHARACTERIZATION",
     "the I_d,max,H1 registration needs propellant Ar, characterization_id, electron_source C1_CONVENTIONAL_REFERENCE, "
     "envelope_id HI-AR, u_I_d_max_H1_A > 0, frozen_utc and scope AR_ENGINEERING_QUALIFICATION_REFERENCE_NOT_FLIGHT_"
     "RELEVANT; frozen at / after the first P1-S7 record -> not usable (NOT_EVALUATED_REGISTRATION); the later flight-"
     "relevant I_d,max,H1 is a separate registration; never the 8.33 A ceiling",
     "p1_reducer._check_registration; p1_a9_16_rules.freeze_before_stage_reasons; p1_campaign",
     ["test_p1_a9_16_i_d_max_ar_registration"]),
    ("A9.10", "P1Q-08", "S3.6", "YES",
     "P1-S0..S5 = HI-ENG / HI-S1A; the P1-S6 topology-control sequence must name the signed HI-HOLDOUT-A record "
     "(hi_holdout_a_id) - required immediately before the first Hall-on reading, not earlier",
     "p1_reducer.reduce_topology_control (HOLDOUT_STAGE)", ["test_p1_a9_16_holdout_and_c1_absent"]),
    ("A9.10", "P1Q-19", "S3.7", "REQUIRE_REGISTERED_GE_CHANNEL",
     "u_I_e,registered < u(I_e,cap)_channels -> ICP-45 status NOT_EVALUATED_REGISTRATION (registration inadmissible, "
     "never silently replaced by the larger value); the other alternative is still computed for transparency only",
     "p1_reducer.icp45a_evaluate (P1Q19_OWNER_SELECTED)",
     ["test_a96_p1q19_alternatives_side_by_side (updated)", "test_p1_a9_16_p1q19_owner_selected"]),
    ("A9.10", "P1Q-24", "S3.8", "K_LOSS_2_FAIL_CLOSED_CONFIRMED",
     "k_loss = 2.0 (owner constant) for the at-power loss-model verification of P1 and P2; a record's k is null (owner "
     "value applies) or exactly 2.0, any other k refused; until LOSS_MODEL_VERIFIED, P_delivered and C_e stay upper "
     "bounds; small-signal S-parameters alone never verify the loss model",
     "p1_reducer.at_power_loss_check (K_LOSS)",
     ["test_met02_loss_needs_at_power_verification (updated)", "test_p1_a9_16_k_loss_owner_constant"]),
    ("A9.10", "OQ-RFQV2-09", "S3.9", "C1_ABSENT_ALLOWED_P1_S6",
     "P1-S6 records c1_configuration C1_NOT_INSTALLED (with c1_absence_record_id documenting absent / open electrical "
     "and gas connections) or C1_INSTALLED_DISCONNECTED; HE-L10..L12 not advanced to P1_NEEDED for P1-S6; C1 is "
     "scheduled against the I_d,max,H1,Ar characterization gate (P1Q-07)",
     "p1_reducer.reduce_topology_control (C1_CONFIGURATIONS)", ["test_p1_a9_16_holdout_and_c1_absent"]),
    ("A9.11", "P1Q-01", "S4.1", "FORM_FROZEN_VALUES_PREREGISTERED_BEFORE_P1_S5_HANDOFF",
     "stable criteria carry the classify_stable_region limits plus frozen_utc, criteria_sha256 (sha256 of the canonical "
     "record without that field, verified by the campaign), derived_from_record_ids (P1-S2..S4 evidence of this "
     "campaign) and derivation_basis; frozen at / after a P1-S5 dwell or derived from non-P1-S2..S4 records -> "
     "NOT_EVALUATED (raw dwells kept); pass label WITHIN_OWNER_CRITERIA only; Z stability carried per dwell",
     "p1_reducer.check_stable_criteria / stable_region_handoff; p1_a9_16_rules.check_stable_criteria_registration",
     ["test_p1_a9_16_stable_criteria_frozen_hashed", "test_sw02_stable_region_failure_branches (updated)"]),
    ("A9.14", "P1Q-17", "S9.5", "REVERIFICATION_700V_DC_60S_TRIGGERED_ONLY",
     "triggered reverification record: 700 V DC / 60 s current-limited at representative pressure / gas, only after "
     "repair, insulation-path modification, suspected fault or a defined requalification trigger (routine pre-run "
     "refused); per-path leakage criterion (P1-IT-55 form); separate from the initial 1.05 kV qualification; level "
     "basis OWNER_DEVELOPMENT_ACCEPTANCE_LEVEL_A9_14_P1Q-17, never attributed to an ECSS clause",
     "p1_a9_16_rules.reduce_dwv_reverification", ["test_p1_a9_16_reverification_700v_triggered_only"]),
    ("A9.14", "P1Q-12", "S8.31", "YES_IP_NEU_LOCK1_ICD_INTERFACE",
     "the reusable IP-NEU interface is a LOCK-1 ICD revision item (not built here); P1 registers the controlled interim "
     "harness drawing at P1-G0 (readiness registration ip_neu_interim_harness_drawing_id; missing -> "
     "G0_NOT_EVALUATED_TBD)",
     "p1_reducer.READINESS_REGISTRATIONS", ["test_p1_a9_16_readiness_registrations"]),
    ("A9.14", "OD5", "S9.9", "ICP_FIRST_HALL_SECOND_MAX_3_ATTEMPTS",
     "baseline start sequence checker: gas / plenum / feed -> H-1 magnet state -> ICP ignite / stabilize -> verify "
     "electron-source condition -> apply V_d -> verify sustained Hall discharge; at most 1 + 2 attempts under a "
     "registered dwell / thermal limit id (no values set); C1-selected variant uses its own qualified sequence id; the "
     "P1-S6 ICP-OFF-first control experiment (A9.3 OQ-VI-05) is explicitly not this baseline sequence",
     "p1_a9_16_rules.check_baseline_start_sequence", ["test_p1_a9_16_od5_start_sequence"]),
    ("A9.14", "ICPQ-08", "S8.2", "ENERGIZED_IF_RF_IMMUNE_ELSE_REGISTERED_RF_OFF_DELAY",
     "B(z) map record: ENERGIZED only with a gaussmeter RF-immunity record, else NOT_EVALUATED_REGISTRATION; RF_OFF only "
     "at a preregistered decay-characterized delay (delay_s, delay_tolerance_s registered), otherwise "
     "NOT_EVALUATED_REGISTRATION / OUT_OF_DOMAIN",
     "p1_a9_16_rules.check_bz_mapping", ["test_p1_a9_16_bz_mapping"]),
    ("A9.14", "F6-OQ-03", "S7.8", "MULTI_GEOMETRY_BENCH_FIRST_MODEL_AFTER_VALIDATION",
     "registration slot icp_geometry_matrix {matrix_id, frozen_utc, geometries [{geometry_id, drawing_id, revision, "
     "within_drawing_envelope true}]}; operating points carry icp_geometry_id in the matrix (else OUT_OF_DOMAIN); each "
     "geometry reported MEASURED_GEOMETRY / NOT_YET_MEASURED; no surrogate between geometries before separate predictive "
     "validation; a geometry outside the drawing envelope is refused (F6-OQ-02)",
     "p1_a9_16_rules.geometry_matrix_report; p1_campaign", ["test_p1_a9_16_geometry_matrix"]),
]

NOT_APPLICABLE = [
    ("A9.15", "RFP-COMPLIANT PROPELLANT POLICY (amends A9.13 xenon statement; A9.14 OQ-A907-07, XA9Q-07, MPQ-01, "
              "XV2Q-01, XA9Q-05, OD6)",
     "reviewed: the P1 package contains no wording that restricts Xe to a C1 contingency (nothing to amend); P1 is the Ar engineering step "
     "(G-REUSE, ICP gas-mode baseline A9.1 unchanged; G-XE stays a declared ICP-feed variant, a dedicated feed only as "
     "a labelled diagnostic booked in the corresponding atmospheric / Xe ledger); C1_NOT_INSTALLED in P1-S6 (A9.10 "
     "OQ-RFQV2-09) is a bench topology control and does not remove the RFP-required system Xe capability"),
    ("A9.14", "OQ-A907-07 / XA9Q-07 / MPQ-01 / XV2Q-01 / XA9Q-05 / OD6 (as amended by A9.15)",
     "mass / Xe accounting / flight-configuration items; no P1 bench artifact carries them (owned by the mass / Xe and "
     "RFQ lanes)"),
]

# item overrides: id -> (new value or None, new status, extra source, note appended)
ITEM_UPDATES = {
    "P1-IT-07": (None, "OWNER_DECIDED (A9.10 P1Q-07 DEDICATED_H1_C1_CHARACTERIZATION; value registered before P1-S7)",
                 "A9.10", "I_d,max,H1,Ar from a dedicated H-1 + conventional C1 characterization in HI-AR with its "
                          "uncertainty, frozen before P1-S7 (Ar engineering reference only; the flight-relevant "
                          "I_d,max,H1 is a later separate registration); never 8.33 A"),
    "P1-IT-25": (None, "OWNER_DECIDED rule (A9.8 P1Q-04: applies to ALL P1 operation incl. non-scoring); limits "
                       "registered at P1-G0", "A9.8",
                 "registered per component in the P1-G0 readiness record (thermal_limits); never a thermal PASS"),
    "P1-IT-30": (None, "OWNER_DECIDED form (A9.11 P1Q-01); values registered, frozen and hashed before the first P1-S5 "
                       "handoff classification", "A9.11",
                 "criteria_id versioned; derived from P1-S2..S4 evidence and >= 3 independent re-ignitions (A9.10 "
                 "P1Q-05); unregistered -> NOT_EVALUATED; pass label WITHIN_OWNER_CRITERIA only"),
    "P1-IT-31": (None, "OWNER_DECIDED methodology (A9.10 P1Q-02); values registered before P1-S6", "A9.10",
                 "registrations.start_attempt_limits; current limit <= min(safe H-1, supply, 8.33 A); never increased "
                 "after a failed ignition"),
    "P1-IT-32": (None, "OWNER_DECIDED definition (A9.10 P1Q-03); threshold / duration registered before P1-S6",
                 "A9.10", "registrations.sustainment_definition; SUSTAINED computed from the I_d trace"),
    "P1-IT-33": (None, "OWNER_GIVEN; confirmed A9.10 P1Q-08 (HI-HOLDOUT-A starts at P1-S6)", "A9.10",
                 "the P1-S6 sequence names hi_holdout_a_id"),
    "P1-IT-36": (None, "OWNER_DECIDED (A9.8 P1Q-09 DEDICATED_ISOLATED_TARGET_NO_CHAMBER_WALL); geometry registered at "
                       "P1-G0 from the ICP module drawing", "A9.8",
                 "option (B) chamber wall REFUSED for every record; ion collector biased negative w.r.t. the target; "
                 "six metered terminals; OPEN_CIRCUIT_BY_CONSTRUCTION only physically verified"),
    "P1-IT-37": (None, "OWNER_DECIDED method (A9.8 P1Q-11); value derived from installed-gauge repeatability, frozen "
                       "before the first P1-S4 pair", "A9.8",
                 "immutable within the campaign; not registered -> NOT_EVALUATED_REGISTRATION; unmatched pair -> "
                 "P1-IT-51 exclusion"),
    "P1-IT-45": (None, "OWNER_DECIDED (A9.14 P1Q-17 REVERIFICATION_700V_DC_60S_TRIGGERED_ONLY)", "A9.14",
                 "700 V DC / 60 s current-limited, triggered only; per-path leakage criterion; owner development "
                 "acceptance level, not an ECSS clause; p1_a9_16_rules.reduce_dwv_reverification"),
    "P1-IT-49": (None, None, "A9.8",
                 "A9.8 P1Q-20: OPEN_CIRCUIT_BY_CONSTRUCTION terminals carry the measured DWV leakage term (never u = 0 "
                 "by default)"),
    "P1-IT-52": (None, "OWNER_DECIDED form (A9.8 P1-IT-52 STAGE_DOMAINS_FROM_REAL_HARDWARE); values registered per "
                       "stage", "A9.8",
                 "unique domain_id, frozen_utc before the stage's first record, hardware basis; outside -> "
                 "OUT_OF_DOMAIN"),
    "P1-IT-55": (None, "OWNER_DECIDED form (A9.8 P1-IT-55 PER_PATH_DOCUMENTED_LEAKAGE_LIMIT); per-path values "
                       "registered before the DWV test", "A9.8",
                 "no documented basis -> G0_NOT_EVALUATED_TBD; flashover / breakdown / tracking / trip fail; leakage "
                 "feeds P1Q-20; in-house assembled test plus supplier certificate (OQ-RFQV2-08)"),
    "P1-IT-57": ("OWNER_DECIDED (A9.10 P1Q-19): REQUIRE_REGISTERED_GE_CHANNEL - u_I_e,registered >= u(I_e,cap)_channels "
                 "under the registered correlation treatment before the first P1-S7 point, else the ICP-45 evaluation is "
                 "NOT_EVALUATED_REGISTRATION; corrected only before data acquisition, never after seeing the result",
                 "OWNER_DECIDED (A9.10 P1Q-19 REQUIRE_REGISTERED_GE_CHANNEL)", "A9.10",
                 "registered below propagation -> NOT_EVALUATED_REGISTRATION"),
}

NEW_ITEMS = [
    ("P1-IT-58", "at-power RF loss-model agreement factor k_loss (P1 and P2)", 2.0, "-", "owner decision",
     "A9.10", "decisions.P1Q-24", "owner-stated", "OWNER_GIVEN (A9.10 P1Q-24 K_LOSS_2_FAIL_CLOSED_CONFIRMED)", "NOW",
     "P1-G1", "|eta_meas - eta_pred| / u_c <= 2; never relaxed in P1 or P2; P_delivered / C_e upper bounds until passed"),
    ("P1-IT-59", "baseline start sequence (OD5)", "gas / plenum / feed -> H-1 magnet state -> ICP ignite / stabilize -> "
     "verify electron-source condition -> apply V_d -> verify sustained Hall discharge; max 1 initial + 2 retries",
     "-, count", "owner decision", "A9.14", "decisions.OD5", "owner-stated",
     "OWNER_GIVEN (A9.14 OD5; dwell / thermal limits registered)", "NOW", "P1-S7H",
     "C1-selected variant uses its own qualified sequence; the P1-S6 control experiment is not this sequence"),
    ("P1-IT-60", "B(z) mapping with RF present (ICPQ-08)", "energized only with demonstrated gaussmeter RF immunity; "
     "else after RF-off at a preregistered decay-characterized delay (TBD - registered)", "s", "owner decision",
     "A9.14", "decisions.ICPQ-08", "owner-stated", "OWNER_DECIDED (delay value TBD - registered)", "after-evidence",
     "P1-G0", "p1_a9_16_rules.check_bz_mapping"),
    ("P1-IT-61", "ICP geometry bench matrix (F6-OQ-03)", "TBD - registered matrix of modular ICP geometry variants "
     "inside the drawing envelope; each geometry measured; no surrogate before separate validation", "-",
     "owner decision", "A9.14", "decisions.F6-OQ-03", "owner-stated", "OWNER_DECIDED (matrix TBD - registered)",
     "LOCK-1", "P1-G0", "registrations.icp_geometry_matrix; p1_a9_16_rules.geometry_matrix_report"),
    ("P1-IT-62", "IP-NEU module interface (P1Q-12)", "defined in the LOCK-1 ICD revision; P1 builds to a controlled "
     "interim harness drawing (id registered at P1-G0)", "-", "owner decision", "A9.14", "decisions.P1Q-12",
     "owner-stated", "OWNER_DECIDED (A9.14 P1Q-12 YES_IP_NEU_LOCK1_ICD_INTERFACE)", "LOCK-1", "P1-G0",
     "readiness registration ip_neu_interim_harness_drawing_id"),
]

FAIL_CLOSED = [
    ("chamber wall as electron collector (any record)", "refused (ExtractionTopologyError)",
     "test_p1_a9_16_chamber_wall_refused_surface_and_capacity"),
    ("OPEN_CIRCUIT_BY_CONSTRUCTION without physical verification", "refused (MissingInputError)",
     "test_p1_a9_16_open_circuit_needs_physical_verification"),
    ("open-circuit terminal without a traceable DWV leakage term", "NOT_EVALUATED_UNCERTAINTY",
     "test_p1_a9_16_open_circuit_leakage_enters_u_R"),
    ("pressure-match tolerance not registered / frozen late / not gauge-derived", "NOT_EVALUATED_REGISTRATION",
     "test_p1_a9_16_pressure_match_registration"),
    ("stage domain frozen at / after its first record", "OUT_OF_DOMAIN", "test_p1_a9_16_domain_registration_unique_and_frozen"),
    ("DWV path without documented leakage basis", "G0_NOT_EVALUATED_TBD", "test_p1_a9_16_dwv_per_path_limit_rules"),
    ("DWV limit registered after the test / tracking / trip", "G0_NOT_MET", "test_p1_a9_16_dwv_per_path_limit_rules"),
    ("component temperature >= validated limit - 50 K", "OUT_OF_DOMAIN (abort / derate)",
     "test_p1_a9_16_thermal_abort_all_operation"),
    ("start limits / sustainment definition missing or frozen late", "P1-S6 OUT_OF_DOMAIN / NOT_EVALUATED_REGISTRATION",
     "test_p1_a9_16_s6_entry_requires_registrations"),
    ("start-limit increase after a failed ignition", "refused (RuleError)",
     "test_p1_a9_16_start_limits_never_raised_after_failure"),
    ("< 3 independent re-ignitions", "NOT_EVALUATED (INSUFFICIENT_REIGNITION_EVIDENCE)",
     "test_p1_a9_16_reignition_minimum_three"),
    ("magnet-on before the magnet-OFF baseline", "OUT_OF_DOMAIN", "test_p1_a9_16_magnet_factor_f6"),
    ("I_d,max,H1,Ar not from H-1 + C1 HI-AR characterization / frozen late", "refused / NOT_EVALUATED_REGISTRATION",
     "test_p1_a9_16_i_d_max_ar_registration"),
    ("registered u_I_e below channel propagation", "NOT_EVALUATED_REGISTRATION", "test_p1_a9_16_p1q19_owner_selected"),
    ("k other than k_loss = 2.0", "refused", "test_p1_a9_16_k_loss_owner_constant"),
    ("stable criteria unhashed / frozen after a P1-S5 dwell", "refused / NOT_EVALUATED",
     "test_p1_a9_16_stable_criteria_frozen_hashed"),
    ("routine pre-run 700 V test or ECSS attribution", "refused", "test_p1_a9_16_reverification_700v_triggered_only"),
    ("energized B(z) map without RF-immunity record", "NOT_EVALUATED_REGISTRATION", "test_p1_a9_16_bz_mapping"),
    ("geometry outside the registered matrix", "OUT_OF_DOMAIN", "test_p1_a9_16_geometry_matrix"),
]


def owner_answer_rows():
    rows = []
    for d, q, sq, code, how, where, tests in APPLIED:
        j, js, m, _ms = DEC[d]
        rows.append({"id": "%s %s" % (d, q), "kind": "owner decision (A9.16 step 1)",
                     "how_applied": "APPLIED (%s): %s [decision %s sha256 %s, %s %s; verbatim %s]"
                                    % (code, how, j, js, sq, q, m),
                     "decision_file": j, "decision_json_sha256": js, "question_id": q, "sequenced_no": sq,
                     "owner_answer": code, "implemented_in": where, "tests": list(tests)})
    for d, q, why in NOT_APPLICABLE:
        j, js, m, _ms = DEC[d]
        rows.append({"id": "%s %s" % (d, q.split(" ")[0]), "kind": "owner decision reviewed (A9.16 step 1)",
                     "how_applied": "NOT_APPLICABLE to the P1 artifacts: %s [decision %s sha256 %s; verbatim %s]"
                                    % (why, j, js, m),
                     "decision_file": j, "decision_json_sha256": js, "question_id": q, "sequenced_no": None,
                     "owner_answer": None, "implemented_in": None, "tests": []})
    return rows


def apply_item_updates(items_list):
    out = []
    for x in items_list:
        x = dict(x)
        up = ITEM_UPDATES.get(x["id"])
        if up is not None:
            val, status, dkey, note = up
            j, js, _m, _ms = DEC[dkey]
            if val is not None:
                x["value"] = val
                if x["evidence_class"] is None and not str(val).startswith(("TBD", "PENDING")):
                    x["evidence_class"] = "owner-stated"      # the value is now the owner's decision text
            if status is not None:
                x["status"] = status
            x["source"] = (x["source"] or "") + "; " + j + " (sha256 " + js + ")"
            x["note"] = ((x["note"] + "; ") if x["note"] else "") + "A9.16 step 1: " + note
        out.append(x)
    for i, name, value, units, basis, dkey, sub, ev, status, fp, gate, note in NEW_ITEMS:
        j, js, _m, _ms = DEC[dkey]
        out.append({"id": i, "name": name, "value": value, "units": units, "basis": basis,
                    "source": "%s %s (sha256 %s)" % (j, sub, js), "evidence_class": ev, "status": status,
                    "freeze_point": fp, "p1_gate": gate, "note": note})
    return out


def incorporation(red, camp, rules):
    return {
        "step": "A9.16 step 1 (owner instruction 2026-10-01 'continue implementing them sequentially'), lane P1 ICP "
                "BENCH",
        "decisions": [{"decision": k, "json": DEC[k][0], "json_sha256": DEC[k][1], "verbatim": DEC[k][2],
                       "verbatim_sha256": DEC[k][3]} for k in ("A9.8", "A9.10", "A9.11", "A9.14", "A9.15")],
        "reading_rule": "the verbatim .md of every applied decision was read in full; it governs over the json "
                        "'summary' digest; A9.15 (RFP-compliant propellant policy) governs wherever older text restricts Xe to a C1 contingency",
        "applied": [{"decision": d, "question_id": q, "sequenced_no": sq, "owner_answer": c, "implemented_in": w,
                     "tests": t} for d, q, sq, c, _h, w, t in APPLIED],
        "not_applicable": [{"decision": d, "question_ids": q, "why": w} for d, q, w in NOT_APPLICABLE],
        "owner_numbers_used": {"k_loss": red.K_LOSS, "reverification_V_DC": rules.REVERIFICATION_V_DC,
                               "reverification_duration_s": rules.REVERIFICATION_DURATION_S,
                               "initial_dwv_V_DC": red.DWV_V_TEST_V, "initial_dwv_duration_s": red.DWV_DURATION_S,
                               "design_withstand_min_V": red.ISOLATION_V_DESIGN_WITHSTAND_MIN_V,
                               "thermal_abort_margin_K": red.THERMAL_ABORT_MARGIN_K,
                               "stand_ceiling_A (never I_d,max,H1)": red.STAND_CEILING_A,
                               "od5_max_attempts": rules.OD5_MAX_ATTEMPTS,
                               "min_independent_reignitions": red.MIN_INDEPENDENT_REIGNITIONS},
        "registration_slots_not_filled": ["pressure-match tolerance (P1Q-11)", "stage operating domains (P1-IT-52)",
                                          "start-attempt limits (P1Q-02)", "sustained-discharge threshold / duration "
                                          "(P1Q-03)", "stable-region limits (P1Q-01)", "per-path DWV leakage limits "
                                          "(P1-IT-55)", "electron-collector target geometry (P1Q-09)",
                                          "validated continuous-use temperature limits (P1Q-04)",
                                          "leakage negligibility ratio (P1Q-20, optional)", "I_d,max,H1,Ar (P1Q-07)",
                                          "B(z) RF-off delay and tolerance (ICPQ-08)", "ICP geometry matrix "
                                          "(F6-OQ-03)", "IP-NEU interim harness drawing id (P1Q-12)",
                                          "OD5 dwell / thermal limits id"],
        "campaign_registration_keys_added": ["sustainment_definition", "start_attempt_limits", "icp_geometry_matrix"],
        "record_fields_added": {
            "icp_operating_point": ["h1_magnet_state (+ h1_magnet_field_setting_id, h1_coil_currents_A when on)",
                                    "extraction.target_geometry_id (dedicated target)",
                                    "terminals.<open>.physical_verification_id", "terminals.<open>.leakage",
                                    "icp_geometry_id (when a geometry matrix is registered)"],
            "ignition_attempt": ["start_state", "restart_condition_met", "h1_magnet_state in OFF / REGISTERED_SETTING"],
            "topology_control_sequence": ["c1_configuration", "c1_absence_record_id (C1_NOT_INSTALLED)",
                                          "hi_holdout_a_id", "steps 5/7: supply_enabled_connected, "
                                          "artifact_or_transient_only, interlock_invalidates"],
            "p1_g0_readiness": ["thermal_limits", "dwv_tests[].path_class / tracking_or_disruptive_discharge / "
                                "protective_trip / test_configuration / configuration_id / supplier_certificate / "
                                "test_utc", "leakage_acceptance.basis_document_id / u_measurement_A / "
                                "uncertainty_treatment / registered_utc", "registrations."
                                "electron_collector_target_geometry_id / ip_neu_interim_harness_drawing_id"]},
        "fail_closed": [{"case": c, "outcome": o, "test": "tests/test_p1_a9_16_owner_rules.py::" + t}
                        for c, o, t in FAIL_CLOSED],
        "existing_tests_updated": ["test_topology_control_paths", "test_stable_region_and_facility_check",
                                   "test_extraction_topology_rules", "test_a94_capacity_record_refusals",
                                   "test_a94_not_evaluated_until_registration", "test_a95_eligibility_conditions",
                                   "test_a95_unmeasured_return_paths_excluded_uniformly",
                                   "test_a96_sec14_invalid_pair_excluded", "test_a96_p1q19_alternatives_side_by_side",
                                   "test_a96_derived_resolutions_and_open_questions", "test_a94_answered_questions_moved",
                                   "test_stable_region_handoff_fields_match_p2_consumer",
                                   "test_e2_open_circuit_only_for_floating_anode_or_registered",
                                   "test_met02_loss_needs_at_power_verification", "test_sw01_stable_criteria_validated",
                                   "test_sw02_stable_region_failure_branches",
                                   "test_sw_r2_01_synthetic_handoff_never_opens_measured_p2_map",
                                   "test_met06_at_power_check_tied_to_characterization_and_registered_k"],
        "pinning_note": "the P1 json / reducer / campaign are sha-pinned or read by other packages (state v4, RVM, M16 "
                        "v4, RFQ v2, F6): the integration lane re-pins; nothing outside this lane's paths was edited",
        "statuses_unchanged": "ICP45 = NOT_EVALUATED until registered; ICP_COUPLED_THERMAL UNRESOLVED; RF ratings "
                              "TBD_AFTER_IMPEDANCE_MAP; anode material OPEN; C1 CONTROL_FALLBACK; no PASS anywhere",
    }
