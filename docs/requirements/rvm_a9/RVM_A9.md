# A9 system requirement-verification matrix (RVM)

**Status: DRAFT_IMPLEMENTATION_FIRST_PENDING_CONSOLIDATED_VERIFICATION.** Lane `fo_a9_6_rvm` (trigger `T_A9_6_RVM`, A9.6 sec. 15 (implementation-first)); A9 status `OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE`. Base commit `3acdbcc165b6205082e3aa04be76d79bba094d0d`. Generated from `docs/requirements/rvm_a9/build_rvm_a9.py` (rules `docs/requirements/rvm_a9/rvm_rules.py`, rows `docs/requirements/rvm_a9/rvm_a9_rows.py`); machine-readable `rvm_a9_v1.json`. Do not edit by hand.

## Read this first

- not a compliance claim: implementation completeness is never compliance; no row is PASS
- not a performance prediction: no Hall transport closure (credible set empty), screening candidate, abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number is used
- not an architecture selection or ranking; no winner
- not a thermal, RF-rating, anode or ICP-capacity PASS (A9.2 / A9.6 fixed statuses carried)
- not an answer to any open owner question and not a freeze of any RFP interpretation (rows 1-3)
- not wired into archengine; goldens unaffected
- The official RFP is not in the repository (owner rows 1-2); every RFP-recorded requirement is a secondary transcription and carries `requirement_frozen = false`.
- Hall: credible set EMPTY; P5-N2 v1 INCONCLUSIVE (permanent); 0-D absolute results WITHDRAWN - no thrust, power or life analysis evidence exists.
- Evidence rule: PASS only with a DETERMINING artifact of kind MEASUREMENT that is measured, verified, non-synthetic, in domain, meets and covers the requirement, and a frozen requirement basis; FAIL only from such a measurement or from a VERIFIED lower-bound floor exceeding the limit under every admissible open reading (docs/EVIDENCE.md; CLAUDE.md rules 6, 10).

## Status counts

| status | hall_icp_neutralizer | hall_c1_reference |
|---|---|---|
| PASS | 0 | 0 |
| FAIL | 0 | 0 |
| NOT_EVALUATED | 15 | 15 |
| OUT_OF_DOMAIN | 0 | 0 |
| INCOMPLETE_EVIDENCE | 4 | 4 |
| NUMERICAL_FAILURE | 0 | 0 |

## Matrix

| id | requirement | limit | method | hall_icp_neutralizer | hall_c1_reference |
|---|---|---|---|---|---|
| RVM-01 | Altitude envelope 180-230 km | orbital altitude within 180 / 230 km | analysis, test | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-02 | >= 12 mN minimum sustained thrust on atmospheric propellant | sustained thrust on atmospheric propellant >= 12 mN | test | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-03 | 25 mN demonstrated system capability inside P_bus < 1.5 kW | demonstrated thrust capability at P_bus < 1500 W >= 25 mN | test, demonstration | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-04 | < 1.5 kW full bus power (A9-02 boundary, steady and start-up, 1 ms window) | P_bus,1ms,max (steady and start-up) < 1500 W | test, analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-05 | Internal ~1.35 kW design allocation (row 109) | system bus power at every registered condition (internal allocation) <= 1350 W | test, analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-06 | < 40 kg wet (incl. Xe + tank) | wet propulsion-system mass < 40 kg | inspection, analysis | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) |
| RVM-07 | Internal 34 kg and 36 kg design allocations (row 53) | wet propulsion-system mass (internal allocation) <= 34 / 36 kg | inspection, analysis | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) |
| RVM-08 | Atmospheric propellant (air: N2 / O2 path; NO_ATOMIC_O labels) | propellant is delivered atmospheric air - | test, demonstration | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-09 | Ionise nascent (atomic) O (recorded as an RFP statement; verify) | no numeric threshold recorded | test, analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-10 | Xe capability (air + Xe; bounded functional Xe mode) | Xe-capable operating mode demonstrated bounded functional - | demonstration, analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-11 | Hall-effect thruster preferred | no numeric threshold recorded | inspection | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-12 | > 15,000 h firing (provisional hard requirement) | cumulative firing time > 15000 h | test, analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-13 | Mission-life basis >= 26,280 h | mission life >= 26280 h | analysis | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-14 | Start-up / restart (ignition, Hall ignition with the electron source, restart, transients) | C1 ignition dwell per attempt (preliminary protocol) <= 120 s | test, demonstration | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-15 | Beam neutralization / electron-current capacity (ICP-45 or C1) | I_e,cap - I_d,max,H1 (one-sided lower confidence bound) > 0 A | test | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-16 | Atomic-oxygen / material compatibility (AO-beam test; anode, collector, keeper, gas path) | no numeric threshold recorded | test, inspection | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) |
| RVM-17 | Thermal closure (>= 50 K below validated limits, 20 % heat-load margin) | margin below validated continuous-use limit >= 50 K | analysis, test | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) | **INCOMPLETE_EVIDENCE** (R6-INCOMPLETE) |
| RVM-18 | Indigenous content >= 75 % total | indigenous content (total) >= 75 % | inspection | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |
| RVM-19 | No single-point failure in electronics (recorded; verify) vs limited redundancy (row 55) | no numeric threshold recorded | analysis, inspection | **NOT_EVALUATED** (R7-NOT-EVALUATED) | **NOT_EVALUATED** (R7-NOT-EVALUATED) |

## Status rules (applied in this order by `rvm_rules.assign_status`)

- `R0-SYNTHETIC`: synthetic evidence is refused (raises); synthetic and measured evidence are never mixed
- `R1-NUMERICAL`: a determining evaluation reports non-convergence and no verified measurement exists -> NUMERICAL_FAILURE
- `R2-FAIL-MEASURED`: a verified, measured, in-domain determining measurement violates the requirement -> FAIL
- `R3-PASS`: every verified, measured, in-domain determining measurement meets the requirement, at least one covers it completely, and the requirement basis is frozen -> PASS
- `R3b-BASIS-NOT-FROZEN`: measurements would pass but the requirement basis is not frozen (official RFP not obtained, owner rows 1-3) -> INCOMPLETE_EVIDENCE
- `R3c-COVERAGE`: verified measurements exist but none covers the requirement completely -> INCOMPLETE_EVIDENCE
- `R4-FAIL-FLOOR`: a determining budget evaluation whose floor is a VERIFIED lower bound exceeds the limit under EVERY admissible open reading -> FAIL
- `R5-OUT-OF-DOMAIN`: determining evaluations exist and every one lies outside its applicability domain -> OUT_OF_DOMAIN
- `R6-INCOMPLETE`: a determining evaluation was run in domain with at least one evidenced (non-allocation, non-TBD) term but cannot conclude -> INCOMPLETE_EVIDENCE
- `R7-NOT-EVALUATED`: no determining evaluation with evidenced terms exists (plans, frameworks, allocations, analogs or unavailable analyses only) -> NOT_EVALUATED

## Rows in detail

### RVM-01 - Altitude envelope 180-230 km

- Category: `rfp_recorded`; key `ALTITUDE_ENVELOPE`
- Requirement: Operate the ABEP propulsion system in very low Earth orbit over the altitude band 180-230 km (the quantifier over the band and the atmosphere design states are open: lane-24 OD2 and OD3).
- Limit: orbital altitude within 180 / 230 km
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false) (frozen: False)
- Verification: analysis, test - analysis of drag vs delivered thrust over the band on the frozen NRLMSIS atmosphere (abep_sim/data/atmosphere_msis21_v1.*: a model input, not compliance evidence) plus thrust tests at delivered feed states representative of the band
- Sources: R2 clauses[topic='(d) Altitude']: "orbital altitudes ranging between 180 km and 230 km" (S1 para 4); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 1 (sha256 e16fbaa3a781...)
- Open readings (TBD_OWNER, carried side by side): OD2 (OPEN): Envelope quantifier over 180–230 km × atmosphere states; OD3 (OPEN): Atmosphere design states
- Historical cross-reference: RTM RFP-ALT; lane-24 gates G1_thrust, G2_bus_power, G6_ignition_sustainment
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` `feed_state_closure_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT for owner review
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` `feed_state_closure_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT for owner review

### RVM-02 - >= 12 mN minimum sustained thrust on atmospheric propellant

- Category: `rfp_recorded`; key `THRUST_12MN_SUSTAINED`
- Requirement: Demonstrate >= 12 mN sustained atmospheric operation (owner row 4 reading of '12-25 mN'), measured on the full system inside the < 1.5 kW spacecraft-DC boundary.
- Limit: sustained thrust on atmospheric propellant >= 12 mN
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner engineering reading row 4 (frozen: False)
- Verification: test - torsional thrust stand (row 115), 1 % target (row 121, A9.1 UBQ-01), S1a u_T acceptance test at 12 mN (row 120); Ar data never count (row 36, A9.1 HIQ-08)
- Sources: R2 clauses[topic='(c) Thrust']: "demonstrate sustained thrust levels between 12 mN and 25 mN" (S1 para 4 (news paraphrase)); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 4 (sha256 a855c0b49429...); owner row 120 (sha256 a6ad1cf6e8a2...); OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `requirement_discipline`
- Historical cross-reference: RTM RFP-THR-MIN; lane-24 gates G1_thrust
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-HD-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-HD-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists

### RVM-03 - 25 mN demonstrated system capability inside P_bus < 1.5 kW

- Category: `rfp_recorded`; key `THRUST_25MN_CAPABILITY`
- Requirement: Demonstrate 25 mN system capability inside the same full spacecraft-DC propulsion boundary with P_bus < 1.5 kW (16.67 mN/kW absolute full-system floor at that point); Xe is not required for 25 mN, any Xe use is booked, and XE_AUGMENTED_PEAK points are never atmospheric-only evidence.
- Limit: demonstrated thrust capability at P_bus < 1500 W >= 25 mN
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner engineering reading rows 4, 27 (frozen: False)
- Verification: test, demonstration - same boundary as RVM-04 (A9-02); thrust per bus power >= 16.67 mN/kW at the 25 mN point (row 27)
- Sources: R2 clauses[topic='(c) Thrust']: "demonstrate sustained thrust levels between 12 mN and 25 mN" (S1 para 4 (news paraphrase)); owner row 4 (sha256 a855c0b49429...); owner row 27 (sha256 a5e26d5d06b8...); owner row 26 (sha256 3549676dc536...)
- Historical cross-reference: RTM RFP-THR-MAX; lane-24 gates G1_thrust, G2_bus_power
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S1-FL-PRIMARY]`: XE ACCOUNTING (supporting; never a capability demonstration): S1-FL-PRIMARY {"RA-FUNC": "APPLIES"}: REFUSED_TBD_INPUTS; S1-FL-PRIMARY {"RA-FUNC": "NOT_APPLIED"}: COMPUTED_EXACT_ZERO
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-ABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-ABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-TABS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S2-FL-C1]`: XE ACCOUNTING (supporting; never a capability demonstration): S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS

### RVM-04 - < 1.5 kW full bus power (A9-02 boundary, steady and start-up, 1 ms window)

- Category: `rfp_recorded`; key `PBUS_LT_1500W_FULL_BUS`
- Requirement: P_bus,1ms,max = max_t (1/1 ms) integral P_bus dt < 1500 W at the spacecraft-DC propulsion boundary (every active load: Hall discharge, magnets, RF source / match, collector bias, C1 supplies, compressor, flow control, housekeeping, thermal), for steady state AND start-up transients unless the official RFP grants a transient exception.
- Limit: P_bus,1ms,max (steady and start-up) < 1500 W
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner rows 108, 110; A9.1 OQ-A902-01 engineering definition (frozen: False)
- Verification: test, analysis - time-resolved spacecraft-side bus power: synchronized channels, >= 100 kSa/s, >= 20 kHz, documented anti-aliasing (A9.1 OQ-A902-01); a ledger alone never PASSes; a mains-powered laboratory RF generator is GROUND/FACILITY_ONLY and never flight P_bus evidence (A9.3 OQ-RFQ-06)
- Sources: R2 clauses[topic='(d) Power']: "strict power budget of less than 1,500 W" (S1 para 6); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 108 (sha256 caedb1162f6e...); owner row 110 (sha256 5227bccf1810...); OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-01`; OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `requirement_discipline`
- Open readings (TBD_OWNER, carried side by side): OQ-A910-03 (OPEN): May a ledger declared 'peak_sampled' (the unaveraged sampled peak) PASS the 1.5 kW gate when the peak is below 1500 W and the record meets the A9.1 OQ-A902-01 ...
- Historical cross-reference: RTM RFP-PWR; lane-24 gates G2_bus_power
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: fo_a9_6_mass_power_integration_v2:power.configurations.hall_icp_neutralizer.rfp_gate_1ms [BUDGET_EVALUATION], A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS [PLAN_OR_FRAMEWORK]
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_icp_neutralizer.rfp_gate_1ms`: LEDGER EVALUATED, NOT_EVALUABLE - steady ledger PARTIAL_BOUNDARY, 22 TBD, P_bus lower bound 0.0 W; P_bus,1ms,max gate NOT_EVALUABLE in all 7 registered steps; slots with a CBE 0, measured 0
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status REQUIREMENT_AS_RECORDED
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status ADOPTED (A9.1; A9 engineering definition pending authoritative RFP wording)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json` `p2_impedance_prep_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PREPARATION_ONLY_NOT_RUN (plasma impedance map waits for the P1 stable region; A9.3)
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: fo_a9_6_mass_power_integration_v2:power.configurations.hall_c1_reference.rfp_gate_1ms [BUDGET_EVALUATION], A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS [PLAN_OR_FRAMEWORK]
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_c1_reference.rfp_gate_1ms`: LEDGER EVALUATED, NOT_EVALUABLE - steady ledger PARTIAL_BOUNDARY, 26 TBD, P_bus lower bound 0.0 W; P_bus,1ms,max gate NOT_EVALUABLE in all 8 registered steps; slots with a CBE 0, measured 0
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-PBUS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status REQUIREMENT_AS_RECORDED
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status ADOPTED (A9.1; A9 engineering definition pending authoritative RFP wording)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-03`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY

### RVM-05 - Internal ~1.35 kW design allocation (row 109)

- Category: `owner_internal_allocation`; key `INTERNAL_1350W_ALLOCATION`
- Requirement: The downstream ICP power must fit inside the internal ~1.35 kW design allocation; the 1.35 -> 1.5 kW margin is not consumed nominally; P_ICP,available = 1350 - P_common - P_Hall - P_other,active at every registered condition (no fixed Hall/ICP split). An owner allocation, not an RFP gate.
- Limit: system bus power at every registered condition (internal allocation) <= 1350 W
- Basis: OWNER_ALLOCATION (row 109; A9.1 OQ-A902-03 / -07): owner-given internal design allocation (frozen: True)
- Verification: test, analysis - ICP-45 demonstrated within P_ICP,available (A9.1 OQ-A902-03); the 0-500 W laboratory RF range is a test capability only
- Sources: owner row 109 (sha256 8506c9cf6790...); OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-03`; OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-07`
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: fo_a9_6_mass_power_integration_v2:power.configurations.hall_icp_neutralizer.phases.steady.design_allocation_1350W [BUDGET_EVALUATION], A9_01_hall_icp_prereg_framework_v1:DQ-HI-PALLOC [PLAN_OR_FRAMEWORK]
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_icp_neutralizer.phases.steady.design_allocation_1350W`: ALLOCATION CHECK EVALUATED, NOT_EVALUABLE - 22 TBD loads; P_ICP,available = 1350 - P_common - P_Hall - P_other,active: NOT_EVALUABLE (upper bound 1350.0 W)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status ALLOCATION (not a prediction, not a gate)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status FIXED_BY_OWNER
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-PALLOC`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: fo_a9_6_mass_power_integration_v2:power.configurations.hall_c1_reference.phases.steady.design_allocation_1350W [BUDGET_EVALUATION]
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_c1_reference.phases.steady.design_allocation_1350W`: ALLOCATION CHECK EVALUATED, NOT_EVALUABLE - 26 TBD loads
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1:A902-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER; item status ALLOCATION (not a prediction, not a gate)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-PB-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status FIXED_BY_OWNER

### RVM-06 - < 40 kg wet (incl. Xe + tank)

- Category: `rfp_recorded`; key `MASS_LT_40KG_WET`
- Requirement: Total propulsion-system mass < 40 kg, read as the wet system including Xe and tank unless the official RFP defines it as dry (row 5); 20 % internal development margin (row 52).
- Limit: wet propulsion-system mass < 40 kg
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner wet reading row 5 (frozen: False)
- Verification: inspection, analysis - weighed flight-representative hardware (inspection) and a CBE roll-up (analysis); allocation vs CBE vs measured kept distinct (A9.6 sec. 11)
- Sources: R2 clauses[topic='(a) Mass']: "maintain a total mass under 40 kg" (S1 para 6 (news paraphrase; RFP clause not seen)); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 5 (sha256 033b66092382...); owner row 52 (sha256 14168ed8540b...); OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `requirement_discipline`
- Open readings (TBD_OWNER, carried side by side): MQ-01 (OPEN): Are the row-54 allocations MEV-level line budgets (row-57 equipment margin inside) or CBE-level budgets (row-57 margin on top)? RFQ ceilings and closure depend ...; MQ-02 (OPEN): Is the 4 kg dry development reserve (row 54) the row-52 20 % internal system margin, or additional to it?; MQ-09 (OPEN): Do the 2 / 5 / 10 kg Xe design cases (row 48) include the row-43 20 % reserve, with the row-45 residual on top?; MQ-10 (OPEN): Under the primary policy reading with the three evidence floors (R2E) the dry mass alone exceeds 40 kg. Accept that closure requires reducing the six ...; XA9Q-01 (OPEN): Are the row-48 design cases (2 / 5 / 10 kg) LOADED Xe (usable + residual) or usable Xe?; XA9Q-07 (OPEN): Does the row-6 functional Xe mode apply to the hall_icp_neutralizer flight configuration (so it also carries a Xe tank and Xe flow control)?; OQ-A910-01 (OPEN): Which content do the row-48 Xe design cases have for BOTH the A9 Xe ledger and the A9 mass BOM: LOADED Xe incl. reserve and residual (A9-08 XA9Q-01) or usable ...
- Historical cross-reference: RTM RFP-MASS; lane-24 gates G3_mass
- **hall_icp_neutralizer: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: fo_a9_6_mass_power_integration_v2:rollups[hall_icp_neutralizer] (3 evidenced term(s))
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:rollups[hall_icp_neutralizer]`: BUDGET EVALUATED, INCONCLUSIVE - no CBE and no measured mass; evidence floors are analog planning values declared 'not a physical lower bound' by the mass package; HARD_40_WET: floor-only 8.504-13.548 kg vs < 40.0 kg, exceeding in 0 of 24 readings; mixed allocation+floor basis DOES_NOT_CLOSE 14 / NOT_EVALUABLE 10; FAIL not admissible: (a) floor-only sums exceed the limit in 0 of 24 admissible readings (FAIL needs all), and (b) the floors are not verified lower bounds; per-reading results reported, status INCOMPLETE_EVIDENCE
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-DMASS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S1-FL-PRIMARY]`: XE ACCOUNTING (supporting; never a capability demonstration): S1-FL-PRIMARY {"RA-FUNC": "APPLIES"}: REFUSED_TBD_INPUTS; S1-FL-PRIMARY {"RA-FUNC": "NOT_APPLIED"}: COMPUTED_EXACT_ZERO
    - mass HARD_40_WET: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg; floor-only 8.504-13.548 kg in 24 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 14, "NOT_EVALUABLE": 10}
- **hall_c1_reference: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: fo_a9_6_mass_power_integration_v2:rollups[hall_c1_reference] (4 evidenced term(s))
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:rollups[hall_c1_reference]`: BUDGET EVALUATED, INCONCLUSIVE - no CBE and no measured mass; evidence floors are analog planning values declared 'not a physical lower bound' by the mass package; HARD_40_WET: floor-only 13.748-13.748 kg vs < 40.0 kg, exceeding in 0 of 12 readings; mixed allocation+floor basis DOES_NOT_CLOSE 10 / NOT_EVALUABLE 14; FAIL not admissible: (a) floor-only sums exceed the limit in 0 of 12 admissible readings (FAIL needs all), and (b) the floors are not verified lower bounds; per-reading results reported, status INCOMPLETE_EVIDENCE
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-DMASS`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S2-FL-C1]`: XE ACCOUNTING (supporting; never a capability demonstration): S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS
    - mass HARD_40_WET: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg, AL-C1 0.2 kg; floor-only 13.748-13.748 kg in 12 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 10, "NOT_EVALUABLE": 14}

### RVM-07 - Internal 34 kg and 36 kg design allocations (row 53)

- Category: `owner_internal_allocation`; key `INTERNAL_34_36KG_ALLOCATION`
- Requirement: Evaluate the 34 kg and 36 kg internal design allocations side by side; 40 kg remains the hard wet limit. An owner allocation, not an RFP gate.
- Limit: wet propulsion-system mass (internal allocation) <= 34 / 36 kg
- Basis: OWNER_ALLOCATION (row 53): both values carried, neither selected (frozen: True)
- Verification: inspection, analysis - as RVM-06
- Sources: owner row 53 (sha256 59d47a36bfbf...)
- Open readings (TBD_OWNER, carried side by side): MQ-01 (OPEN): Are the row-54 allocations MEV-level line budgets (row-57 equipment margin inside) or CBE-level budgets (row-57 margin on top)? RFQ ceilings and closure depend ...; MQ-02 (OPEN): Is the 4 kg dry development reserve (row 54) the row-52 20 % internal system margin, or additional to it?; MQ-09 (OPEN): Do the 2 / 5 / 10 kg Xe design cases (row 48) include the row-43 20 % reserve, with the row-45 residual on top?; MQ-10 (OPEN): Under the primary policy reading with the three evidence floors (R2E) the dry mass alone exceeds 40 kg. Accept that closure requires reducing the six ...; XA9Q-07 (OPEN): Does the row-6 functional Xe mode apply to the hall_icp_neutralizer flight configuration (so it also carries a Xe tank and Xe flow control)?
- **hall_icp_neutralizer: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: fo_a9_6_mass_power_integration_v2:rollups[hall_icp_neutralizer] (3 evidenced term(s))
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:rollups[hall_icp_neutralizer]`: BUDGET EVALUATED, INCONCLUSIVE - no CBE and no measured mass; evidence floors are analog planning values declared 'not a physical lower bound' by the mass package; INTERNAL_34: floor-only 8.504-13.548 kg vs <= 34.0 kg, exceeding in 0 of 24 readings; mixed allocation+floor basis DOES_NOT_CLOSE 22 / NOT_EVALUABLE 2; INTERNAL_36: floor-only 8.504-13.548 kg vs <= 36.0 kg, exceeding in 0 of 24 readings; mixed allocation+floor basis DOES_NOT_CLOSE 20 / NOT_EVALUABLE 4; FAIL not admissible: (a) floor-only sums exceed the limit in 0 of 48 admissible readings (FAIL needs all), and (b) the floors are not verified lower bounds; per-reading results reported, status INCOMPLETE_EVIDENCE
    - mass INTERNAL_34: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg; floor-only 8.504-13.548 kg in 24 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 22, "NOT_EVALUABLE": 2}
    - mass INTERNAL_36: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg; floor-only 8.504-13.548 kg in 24 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 20, "NOT_EVALUABLE": 4}
- **hall_c1_reference: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: fo_a9_6_mass_power_integration_v2:rollups[hall_c1_reference] (4 evidenced term(s))
    - [DETERMINING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:rollups[hall_c1_reference]`: BUDGET EVALUATED, INCONCLUSIVE - no CBE and no measured mass; evidence floors are analog planning values declared 'not a physical lower bound' by the mass package; INTERNAL_34: floor-only 13.748-13.748 kg vs <= 34.0 kg, exceeding in 0 of 12 readings; mixed allocation+floor basis DOES_NOT_CLOSE 18 / NOT_EVALUABLE 6; INTERNAL_36: floor-only 13.748-13.748 kg vs <= 36.0 kg, exceeding in 0 of 12 readings; mixed allocation+floor basis DOES_NOT_CLOSE 14 / NOT_EVALUABLE 10; FAIL not admissible: (a) floor-only sums exceed the limit in 0 of 24 admissible readings (FAIL needs all), and (b) the floors are not verified lower bounds; per-reading results reported, status INCOMPLETE_EVIDENCE
    - mass INTERNAL_34: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg, AL-C1 0.2 kg; floor-only 13.748-13.748 kg in 12 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 18, "NOT_EVALUABLE": 6}
    - mass INTERNAL_36: evidence floors AL-04 3.504 kg, AL-07 5.0 kg, AL-08 5.044 kg, AL-C1 0.2 kg; floor-only 13.748-13.748 kg in 12 readings, exceeding 0; lower bound verified: False; mixed basis {"CLOSES": 0, "DOES_NOT_CLOSE": 14, "NOT_EVALUABLE": 10}

### RVM-08 - Atmospheric propellant (air: N2 / O2 path; NO_ATOMIC_O labels)

- Category: `rfp_recorded`; key `ATMOSPHERIC_PROPELLANT`
- Requirement: Operate on intake-collected atmospheric air through the RFP architecture path (intake -> filter -> compressor -> atmospheric gas chamber -> valve -> ionization/discharge -> acceleration). Evidence order: Ar (engineering-only, never counts) -> N2 -> O2-bearing surrogate labelled NO_ATOMIC_O -> separate atomic-O programme; no N2 + O2 test is AO proof.
- Limit: propellant is delivered atmospheric air -
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner rows 36, 132; A9 evidence_sequence (frozen: False)
- Verification: test, demonstration - Hall-on sustainment on N2 and O2-bearing surrogates in HI-S1 / HI-CMP (NO_ATOMIC_O); atomic-O effects only through HI-AO (RVM-09, RVM-16)
- Sources: R2 clauses[topic='(b) Air + Xe']: "ambient atmospheric air supplemented with Xenon" (S1 para 5 (news paraphrase)); rfp.recorded_in[id=R4] (docs/HISTORY.md (Hall uncertainty scope rule) and CLAUDE.md Next work 1, 'Scope'); owner row 36 (sha256 eda83de4a8ab...); owner row 132 (sha256 fe6f23c2ddd4...); OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `evidence_sequence`; OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `HIQ-08`
- Historical cross-reference: RTM RFP-PROP, RFP-IGN-SUST; lane-24 gates G6_ignition_sustainment
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-CMP [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-CMP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-GAS-07`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` `feed_state_closure_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT for owner review
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-CMP [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-CMP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-SUST`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-GAS-07`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` `feed_state_closure_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT for owner review

### RVM-09 - Ionise nascent (atomic) O (recorded as an RFP statement; verify)

- Category: `rfp_inferred_from_repo_text`; key `IONISE_NASCENT_O`
- Requirement: The ABEP ionises nascent (atomic) O from the collected atmosphere. Recorded only in-repo (R6); no threshold recorded; whether it needs its own gate is lane-24 OD12.
- Limit: no numeric threshold recorded
- Basis: RFP_INFERRED_FROM_REPO_TEXT - verify against the RFP document (frozen: False)
- Verification: test, analysis - delivered species state measured (row 102); the O / O2 chemistry v0 tables are unvalidated (not evidence); N2 + O2 surrogate data are NO_ATOMIC_O
- Sources: rfp.recorded_in[id=R6] (docs/HISTORY.md, wall recombination section); owner row 132 (sha256 fe6f23c2ddd4...); owner row 102 (sha256 22d2ffa98a73...)
- Open readings (TBD_OWNER, carried side by side): OD12 (OPEN): RFP requirements recorded but not gated (indigenous content, no single-point failure, 'ionise nascent O')
- Historical cross-reference: RTM RFP-NASCENT-O; lane-24 gates -
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-AO [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-AO`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/chemistry/o_o2/v0/channel_status_v0.json` `o_o2_channel_status_v0`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-AO [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-AO`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/chemistry/o_o2/v0/channel_status_v0.json` `o_o2_channel_status_v0`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists

### RVM-10 - Xe capability (air + Xe; bounded functional Xe mode)

- Category: `rfp_recorded`; key `XE_CAPABILITY`
- Requirement: Demonstrate a bounded functional Xe-capable operating mode beyond bookkeeping (need not be continuous nominal operation) and book every Xe use (PHASE_TOTAL_FLOW); Xe reference / health checks are labelled and never atmospheric evidence.
- Limit: Xe-capable operating mode demonstrated bounded functional -
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false); owner reading row 6 (frozen: False)
- Verification: demonstration, analysis - Xe mode demonstrated on H-1 (XE_REFERENCE / XE_AUGMENTED_PEAK labels); the Xe accounting is supporting only (XV2-IF-09); whether the row-6 mode applies to the hall_icp_neutralizer flight configuration is XA9Q-07 (OPEN, carried side by side)
- Sources: R2 clauses[topic='(b) Air + Xe']: "ambient atmospheric air supplemented with Xenon" (S1 para 5 (news paraphrase)); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 6 (sha256 a2df92d79838...); owner row 42 (sha256 afb93b0c07cf...); owner row 26 (sha256 3549676dc536...); OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `HIQ-03`
- Open readings (TBD_OWNER, carried side by side): XA9Q-07 (OPEN): Does the row-6 functional Xe mode apply to the hall_icp_neutralizer flight configuration (so it also carries a Xe tank and Xe flow control)?; XA9Q-01 (OPEN): Are the row-48 design cases (2 / 5 / 10 kg) LOADED Xe (usable + residual) or usable Xe?; OD6 (OPEN): Meaning of 'air + Xe'
- Historical cross-reference: RTM RFP-XE-OP; lane-24 gates G7_air_xenon
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-CMP [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-CMP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S1-FL-PRIMARY]`: XE ACCOUNTING (supporting; never a capability demonstration): S1-FL-PRIMARY {"RA-FUNC": "APPLIES"}: REFUSED_TBD_INPUTS; S1-FL-PRIMARY {"RA-FUNC": "NOT_APPLIED"}: COMPUTED_EXACT_ZERO
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:HI-CMP [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-CMP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` `xe_accounting_a9_v2:evaluations[S2-FL-C1]`: XE ACCOUNTING (supporting; never a capability demonstration): S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_3", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "INSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS; S2-FL-C1 {"RA-DWELL": "ATTEMPTS_2", "RA-FLOWUNC": "OUTSIDE_RESERVE_BASE"}: REFUSED_TBD_INPUTS
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-SU-05`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY

### RVM-11 - Hall-effect thruster preferred

- Category: `rfp_recorded`; key `HALL_PREFERENCE`
- Requirement: Preference (not mandate) for a Hall-effect thruster configuration. Both A9 configurations use the H-1 Hall accelerator; A9 keeps the Hall family (CLAUDE.md rule 8).
- Limit: no numeric threshold recorded
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false) (frozen: False)
- Verification: inspection - inspection of a frozen design baseline (Milestone C); the A9 architecture is OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE, so there is no baseline to inspect; a design intent is not verification evidence
- Sources: R2 clauses[topic='(d) Hall preferred']: "preference for a Hall-effect thruster configuration" (S1 para 5); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `primary_hypothesis`; OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `control_fallback`
- Historical cross-reference: RTM RFP-HALL; lane-24 gates -
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK

### RVM-12 - > 15,000 h firing (provisional hard requirement)

- Category: `rfp_recorded`; key `FIRING_GT_15000H_PROVISIONAL`
- Requirement: Cumulative firing time > 15,000 h, retained as a provisional hard requirement until the official RFP confirms it (row 3). C1 carries the 15,000 h cathode basis; the ICP neutralizer must carry its own RF-neutralizer lifetime / cycle requirement (row 46; not yet defined: OQ-VI-04).
- Limit: cumulative firing time > 15000 h
- Basis: PROVISIONAL (row 3) - verify against the RFP; no accessed source mentions it (R2) (frozen: False)
- Verification: test, analysis - pre-registered wear / endurance segments (AOL-LF-02) plus a life analysis that uses no Hall map, screening candidate or withdrawn number (AOL-LF-01)
- Sources: rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 3 (sha256 d4b082801ab7...); owner row 46 (sha256 49ccf1043315...)
- Open readings (TBD_OWNER, carried side by side): OQ-VI-04 (OPEN): ICP-neutralizer lifetime and cycle requirement (VI-LF-05); OD13 (OPEN): '>15,000 h ignition' wording
- Historical cross-reference: RTM RFP-FIRING; lane-24 gates G4_firing_life, P2_cathode
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: ao_lifetime_register_v5:AOL-LF-02 [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS], hall_icp_validation_inputs_v1:VI-LF-05 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-LF-05`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status OPEN
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: ao_lifetime_register_v5:AOL-LF-02 [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE [PLAN_OR_FRAMEWORK], transport_ensemble_v0:members [VALIDATED_ANALYSIS]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-CX-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED

### RVM-13 - Mission-life basis >= 26,280 h

- Category: `rfp_recorded`; key `MISSION_LIFE_GE_26280H`
- Requirement: Mission life >= 26,280 h (three years), the conservative engineering basis versus the repository's 26,000 h until the official wording is verified (row 3).
- Limit: mission life >= 26280 h
- Basis: OWNER_ENGINEERING_BASIS (row 3) pending the official RFP wording (frozen: False)
- Verification: analysis - mission analysis combining life, propellant and duty cycle; each input needs its own evidence (RVM-06, RVM-10, RVM-12)
- Sources: R2 clauses[topic='(d) Life']: "mission life requirement has been set at three years" (S1 para 7); rfp.recorded_in[id=R1] (CLAUDE.md, section 'What this is'); owner row 3 (sha256 d4b082801ab7...)
- Historical cross-reference: RTM RFP-MISSION; lane-24 gates G5_mission
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: transport_ensemble_v0:members [VALIDATED_ANALYSIS], A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE [PLAN_OR_FRAMEWORK]
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: transport_ensemble_v0:members [VALIDATED_ANALYSIS], A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE [PLAN_OR_FRAMEWORK]
    - [DETERMINING/VALIDATED_ANALYSIS] `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `transport_ensemble_v0:members`: UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; Credible set is EMPTY (P5-Xe blind validation failed; no can...); P5-N2 v1 p5_n2_campaign_v1_vacuum: promotable [], inconclusive 9 of 9 candidates (permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis evidence exists
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-LIFE`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-LF-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED

### RVM-14 - Start-up / restart (ignition, Hall ignition with the electron source, restart, transients)

- Category: `rfp_inferred_from_repo_text`; key `STARTUP_RESTART`
- Requirement: Ignite and restart from the off state and record ICP ignition, Hall ignition with ICP electrons, restart success and cycle count (row 24); C1 ignition dwell <= 120 s with at most two retries in the preliminary protocol, all Xe booked (row 93); start-up transients inside < 1.5 kW (row 108) with sequenced peaks (row 112, A9.1 SEQ-*). No ignition / restart clause is recorded from the RFP (lane-24 OD14).
- Limit: C1 ignition dwell per attempt (preliminary protocol) <= 120 s
- Basis: RFP_INFERRED (lane-24 G6 ignition inferred) + owner rows 24, 93, 108, 112 (frozen: False)
- Verification: test, demonstration - DQ-HI-IGN hard gate and DQ-HI-RESTART Pareto quantity; the OQ-VI-05 Ar topology control is engineering-only, not an architecture gate
- Sources: owner row 24 (sha256 f512c61dcb42...); owner row 93 (sha256 70360d5a7cdd...); owner row 108 (sha256 caedb1162f6e...); owner row 112 (sha256 a2f14a719852...); OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `SEQ-peaks`; OD_HARDWARE_PIVOT_2026_09_30_A9_3_post_a9_tier1_owner_decisions `OQ-VI-05`
- Open readings (TBD_OWNER, carried side by side): OD5 (OPEN): Ignition start sequence and restart count; OD14 (OPEN): Is ignition from the off state on atmospheric propellant an RFP requirement? (G6.ignition is inferred from 'air + Xe' and the RFP architecture; no ignition or ...; OQ-A907-01 (OPEN): Row 93 'cap each ignition dwell at 120 s and allow at most two retries': book 3 attempts (1 + 2 retries, literal) or 2 (the '120 s x 2' shorthand used in the ...; XA9Q-02 (OPEN): Row 93 'at most two retries': is the per-start bound 3 dwells (1 + 2 retries, 360 s) or 2 dwells (240 s)?
- Historical cross-reference: RTM RFP-IGN-SUST; lane-24 gates G6_ignition_sustainment, P2_cathode
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:DQ-HI-IGN [PLAN_OR_FRAMEWORK], hall_icp_validation_inputs_v1:VI-SU-01 [PLAN_OR_FRAMEWORK], hall_icp_validation_inputs_v1:VI-SU-02 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-IGN`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-RESTART`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_icp_neutralizer.phases.startup`: SEQUENCE RULES RULES_NOT_EVALUABLE (5 rules not evaluable; template bus_boundary_a9.SEQUENCE_TEMPLATES (PROPOSED, row 112))
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-SU-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-SU-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json` `p1_icp_bench_v1:P1-S6`: PLANNED / FRAMEWORK ONLY - nothing measured; package status ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:DQ-HI-IGN [PLAN_OR_FRAMEWORK], hall_icp_validation_inputs_v1:VI-SU-04 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-IGN`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-RESTART`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/BUDGET_EVALUATION] `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` `fo_a9_6_mass_power_integration_v2:power.configurations.hall_c1_reference.phases.startup`: SEQUENCE RULES RULES_NOT_EVALUABLE (6 rules not evaluable; template bus_boundary_a9.SEQUENCE_TEMPLATES (PROPOSED, row 112))
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-SU-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY

### RVM-15 - Beam neutralization / electron-current capacity (ICP-45 or C1)

- Category: `derived_from_owner_decision`; key `NEUTRALIZATION`
- Requirement: hall_icp_neutralizer: ICP-45 capacity I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (signed, discharge-OFF, anode disconnected and floating, Kirchhoff admission) >= I_d,max,H1 with the pre-registered one-sided margin before any score-bearing point; Hall-ON is NEUTRALIZATION_CONSISTENCY only. hall_c1_reference: heated Xe-fed LaB6 C1 sized to the measured / derived current demand (CONTROL_FALLBACK).
- Limit: I_e,cap - I_d,max,H1 (one-sided lower confidence bound) > 0 A
- Basis: OWNER_DECIDED criterion form (A9.1 ICP-45, A9.3-A9.5); I_d,max,H1 is TBD - requires measured / registered H-1 operation (frozen: False)
- Verification: test - unknown I_d,max,H1 -> NOT_EVALUATED (A9.6 sec. 14); ICP capacity status PENDING_ICP45; the 8.33 A stand ceiling is not a requirement (A9.3 OQ-A907-02)
- Sources: OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `ICP-45`; OD_HARDWARE_PIVOT_2026_09_30_A9_3_post_a9_tier1_owner_decisions `OQ-A907-02`; OD_HARDWARE_PIVOT_2026_09_30_A9_4_p1_p2_owner_decisions `P1Q-10`; OD_HARDWARE_PIVOT_2026_09_30_A9_4_p1_p2_owner_decisions `P1Q-13`; OD_HARDWARE_PIVOT_2026_09_30_A9_5_p1_closure_owner_decisions `P1Q-15`; OD_HARDWARE_PIVOT_2026_09_30_A9_5_p1_closure_owner_decisions `P1Q-16`; owner row 88 (sha256 d932abe4b143...); OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `control_fallback`
- Historical cross-reference: RTM -; lane-24 gates P2_cathode
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: p1_icp_bench_v1:P1-S7 [PLAN_OR_FRAMEWORK], icp_neutralizer_icd_v1:ICP-45 [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-ECAP [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-VCPL [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json` `p1_icp_bench_v1:P1-S7`: PLANNED / FRAMEWORK ONLY - nothing measured; package status ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING
    - [DETERMINING/PLAN_OR_FRAMEWORK] `schemas/interfaces/icp_neutralizer_icd_v1.json` `icp_neutralizer_icd_v1:ICP-45`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_PENDING_OWNER; item status TBD (value); form OWNER_GIVEN (A9.1 ICP-45)
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-ECAP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-VCPL`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json` `p1_icp_bench_v1:P1-S7H`: PLANNED / FRAMEWORK ONLY - nothing measured; package status ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-EX-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PROCUREMENT] `docs/procurement/rfq_a9_v2/rfq_a9_v2.json` `RFQ_A9_V2`: PLANNED / FRAMEWORK ONLY - nothing measured; package status COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.6 sec. 13; consolidated verification pending)
    - [CONTEXT/PUBLISHED_ANALOG] `docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json` `icp_neutralizer_evidence_v1:anchor`: PUBLISHED ANALOG ONLY (other hardware, Ar): topology precedent, never Vyovrinda performance
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: A9_01_hall_icp_prereg_framework_v1:DQ-HI-ECAP [PLAN_OR_FRAMEWORK], A9_01_hall_icp_prereg_framework_v1:DQ-HI-VCPL [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-ECAP`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:DQ-HI-VCPL`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-EX-07`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
    - [SUPPORTING/PROCUREMENT] `docs/procurement/rfq_a9_v2/rfq_a9_v2.json` `RFQ_A9_V2`: PLANNED / FRAMEWORK ONLY - nothing measured; package status COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.6 sec. 13; consolidated verification pending)

### RVM-16 - Atomic-oxygen / material compatibility (AO-beam test; anode, collector, keeper, gas path)

- Category: `rfp_inferred_from_repo_text`; key `AO_MATERIAL_COMPATIBILITY`
- Requirement: AO-exposed and O / O2-wetted materials qualified in a dedicated AO programme (AO-beam test recorded as 'RFP 4.1a', verify); 316L REJECTED_AS_CURRENT_BASELINE for the flight anode; final anode / collector material OPEN until coupon evidence; no graphite flight keeper for O / AO exposure; no silver in O / AO-wetted gas-path parts.
- Limit: no numeric threshold recorded
- Basis: RFP_INFERRED_FROM_REPO_TEXT (R6) + owner rows 94, 103, 106, 132; A9.1 / A9.2 (frozen: False)
- Verification: test, inspection - biased and floating coupons (row 106), ground AO exposure with a fluence witness (AOL-EX-01 / -02), post-test SEM/EDS/XPS; P4 screens every candidate fail-closed
- Sources: rfp.recorded_in[id=R6] (docs/HISTORY.md, wall recombination section); owner row 132 (sha256 fe6f23c2ddd4...); owner row 106 (sha256 7ea19b29bcfb...); owner row 94 (sha256 964e5c0b6634...); owner row 103 (sha256 8d6289fe3b11...); OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `anode_316L`; OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `A9-03-collector`
- Open readings (TBD_OWNER, carried side by side): OD12 (OPEN): RFP requirements recorded but not gated (indigenous content, no single-point failure, 'ionise nascent O')
- Historical cross-reference: RTM RFP-AO-TEST; lane-24 gates -
- **hall_icp_neutralizer: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: p4_anode_materials_v1:candidate_screening_states (21 evidenced term(s))
    - [DETERMINING/FRAMEWORK_EVALUATION] `docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json` `p4_anode_materials_v1:candidate_screening_states`: FRAMEWORK EVALUATED - 44 application x candidate screens all INCOMPLETE_EVIDENCE; final anode / collector material OPEN; 21 bulk property record(s) from open datasheets; no AO / oxidation / sputter evidence on any candidate (P4 ID-10)
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-EX-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-EX-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-AO`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-LF-06`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
- **hall_c1_reference: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: p4_anode_materials_v1:candidate_screening_states (21 evidenced term(s))
    - [DETERMINING/FRAMEWORK_EVALUATION] `docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json` `p4_anode_materials_v1:candidate_screening_states`: FRAMEWORK EVALUATED - 44 application x candidate screens all INCOMPLETE_EVIDENCE; final anode / collector material OPEN; 21 bulk property record(s) from open datasheets; no AO / oxidation / sputter evidence on any candidate (P4 ID-10)
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-EX-01`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `ao_lifetime_register_v5:AOL-EX-02`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status PROPOSED
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` `A9_01_hall_icp_prereg_framework_v1:HI-AO`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PROPOSED_FRAMEWORK_NOT_A_LOCK
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-LF-06`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY

### RVM-17 - Thermal closure (>= 50 K below validated limits, 20 % heat-load margin)

- Category: `derived_project`; key `THERMAL_CLOSURE`
- Requirement: Every component >= 50 K below its validated continuous-use limit with a 20 % heat-load margin (row 86); no unsourced anode target (row 87); ICP_COUPLED_THERMAL and ANODE_THERMAL_CLOSURE stay UNRESOLVED until the coupled model has its inputs; never a thermal PASS from a negligible-coupling calculation (A9.2).
- Limit: margin below validated continuous-use limit >= 50 K
- Basis: DERIVED_PROJECT (not an RFP clause; RTM DER-THERMAL): owner rows 86, 87; A9.2 (frozen: True)
- Verification: analysis, test - coupled thermal model with Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume and view factors (P3) plus thermal-vacuum tests with a measured sink temperature (row 131)
- Sources: owner row 86 (sha256 e9d2eb1f07e6...); owner row 87 (sha256 9d0d1a4d6faa...); OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `icp_coupled_thermal`; OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `anode_approach`
- Open readings (TBD_OWNER, carried side by side): OQ-A907-03 (OPEN): Is the >= 50 K rule tested at the bounding corner (all adverse analog inputs together, as done here) or at a nominal point plus a pre-registered uncertainty ...; OQ-A907-05 (OPEN): Accept the supplier continuous ratings (BN 900 degC oxidizing guide value, ceramic wire 1000 F) as PROVISIONAL limits for the >= 50 K rule until qualification ...; OQ-A907-09 (OPEN): Row 86 '20% heat-load design margin': this lane scales only the DISSIPATED loads (discharge fractions, coil I^2R, cathode) by 1.2 and keeps the environmental ...; OQ-A907-10 (OPEN): The thermal worst case is found by a local search plus a heuristic search allowance (not an upper bound). Within-limit results (for hall_icp_neutralizer: ...
- Historical cross-reference: RTM DER-THERMAL; lane-24 gates P1_thermal
- **hall_icp_neutralizer: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: p3_coupled_thermal_v1:fail_closed_evaluations (6 evidenced term(s))
    - [DETERMINING/FRAMEWORK_EVALUATION] `docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json` `p3_coupled_thermal_v1:fail_closed_evaluations`: FRAMEWORK EVALUATED - ICP_COUPLED_THERMAL UNRESOLVED and ANODE_THERMAL_CLOSURE UNRESOLVED; heat terms Q_Hall->ICP INCOMPLETE_EVIDENCE, Q_collector INCOMPLETE_EVIDENCE, Q_RF/match INCOMPLETE_EVIDENCE, Q_plume INCOMPLETE_EVIDENCE, coupled_network INCOMPLETE_EVIDENCE; 6 analog / model-derived input(s) in the framework; never a thermal PASS (A9.2, A9.6)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-LF-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY
- **hall_c1_reference: INCOMPLETE_EVIDENCE** (`R6-INCOMPLETE`) - evaluation run with evidenced terms but inconclusive: p3_coupled_thermal_v1:fail_closed_evaluations (6 evidenced term(s))
    - [DETERMINING/FRAMEWORK_EVALUATION] `docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json` `p3_coupled_thermal_v1:fail_closed_evaluations`: FRAMEWORK EVALUATED - ANODE_THERMAL_CLOSURE UNRESOLVED (shared H-1 anode; A9.2 anode_approach); the ICP heat terms do not apply to this configuration; the H-1 network is only method-checked against H2-5 (no temperatures reported); 6 analog / model-derived input(s) in the framework; never a thermal PASS (A9.2, A9.6)
    - [SUPPORTING/PLAN_OR_FRAMEWORK] `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` `hall_icp_validation_inputs_v1:VI-LF-04`: PLANNED / FRAMEWORK ONLY - nothing measured; package status DRAFT_FOR_OWNER_REVIEW; item status HARDWARE_ONLY

### RVM-18 - Indigenous content >= 75 % total

- Category: `rfp_recorded`; key `INDIGENOUS_CONTENT`
- Requirement: Total indigenous content >= 75 % (subsystem minima thruster 0.80, intake 0.80, compressor 0.60, PSE 0.70 exist only in in-repo code, R2; not found in any accessed source).
- Limit: indigenous content (total) >= 75 %
- Basis: SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false) (frozen: False)
- Verification: inspection - inspection of the selected-part bill of materials and supplier origin; no part is selected (quotation only)
- Sources: R2 clauses[topic='(d) Indigenous content']: "minimum of 75 percent" (S1 para 8); rfp.recorded_in[id=R2] (abep_sim/constants.py, class RFPConstraints)
- Open readings (TBD_OWNER, carried side by side): OD12 (OPEN): RFP requirements recorded but not gated (indigenous content, no single-point failure, 'ionise nascent O')
- Historical cross-reference: RTM RFP-IC; lane-24 gates -
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: RFQ_A9_V2 [PROCUREMENT]
    - [DETERMINING/PROCUREMENT] `docs/procurement/rfq_a9_v2/rfq_a9_v2.json` `RFQ_A9_V2`: PLANNED / FRAMEWORK ONLY - nothing measured; package status COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.6 sec. 13; consolidated verification pending)
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: RFQ_A9_V2 [PROCUREMENT]
    - [DETERMINING/PROCUREMENT] `docs/procurement/rfq_a9_v2/rfq_a9_v2.json` `RFQ_A9_V2`: PLANNED / FRAMEWORK ONLY - nothing measured; package status COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.6 sec. 13; consolidated verification pending)

### RVM-19 - No single-point failure in electronics (recorded; verify) vs limited redundancy (row 55)

- Category: `rfp_inferred_from_repo_text`; key `ELECTRONICS_REDUNDANCY`
- Requirement: 'Redundancy per RFP: no single-point failure in electronics' is recorded only in a code docstring (R7, unverified). Owner row 55 sets limited redundancy (dual series isolation on the high-pressure Xe path, critical sensing / FDIR redundancy; no duplicated thruster, ICP or full PPU at this stage). Both are carried side by side; see RVMQ-01.
- Limit: no numeric threshold recorded
- Basis: RFP_INFERRED_FROM_REPO_TEXT (R7) - verify against the RFP document (frozen: False)
- Verification: analysis, inspection - FMEA / failure-tree analysis of the selected electronics (none selected)
- Sources: rfp.recorded_in[id=R7] (abep_sim/ppu.py, module docstring); owner row 55 (sha256 44214bd428d2...); owner row 90 (sha256 77c6b2a2e6be...)
- Open readings (TBD_OWNER, carried side by side): OD12 (OPEN): RFP requirements recorded but not gated (indigenous content, no single-point failure, 'ionise nascent O')
- Historical cross-reference: RTM RFP-REDUND; lane-24 gates -
- **hall_icp_neutralizer: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: bus_power_boundary_a9_v1 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER
- **hall_c1_reference: NOT_EVALUATED** (`R7-NOT-EVALUATED`) - no determining evaluation with evidenced terms: bus_power_boundary_a9_v1 [PLAN_OR_FRAMEWORK]
    - [DETERMINING/PLAN_OR_FRAMEWORK] `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `bus_power_boundary_a9_v1`: PLANNED / FRAMEWORK ONLY - nothing measured; package status PRELIMINARY_DRAFT_FOR_OWNER

## (a) Items

| id | name | value | units | basis | evidence class | status | freeze point |
|---|---|---|---|---|---|---|---|
| RVM-IT-01 | altitude band lower edge | 180 | km | RFP as recorded | requirement-as-recorded | REQUIREMENT_AS_RECORDED (verify against the official RFP) | after-evidence |
| RVM-IT-02 | altitude band upper edge | 230 | km | RFP as recorded | requirement-as-recorded | REQUIREMENT_AS_RECORDED (verify against the official RFP) | after-evidence |
| RVM-IT-03 | minimum sustained atmospheric thrust | 12 | mN | owner reading of '12-25 mN' (row 4) | owner-stated | OWNER_GIVEN | NOW |
| RVM-IT-04 | demonstrated system thrust capability | 25 | mN | owner reading (rows 4, 27) | owner-stated | OWNER_GIVEN | NOW |
| RVM-IT-05 | absolute full-system thrust-per-bus-power floor at the 25 mN point | 16.67 | mN/kW | row 27 | owner-stated | OWNER_GIVEN | NOW |
| RVM-IT-06 | bus-power requirement (strict '<') | 1500 | W | RFP as recorded; row 108 | requirement-as-recorded | REQUIREMENT_AS_RECORDED (verify against the official RFP) | after-evidence |
| RVM-IT-07 | averaging window of the gate quantity P_bus,1ms,max | 0.001 | s | A9.1 OQ-A902-01 | owner-stated | OWNER_GIVEN (A9 engineering definition pending the RFP wording) | NOW |
| RVM-IT-08 | internal design allocation | 1350 | W | row 109; A9.1 OQ-A902-03 | owner-allocation | OWNER_ALLOCATION (not a gate) | NOW |
| RVM-IT-09 | wet mass limit incl. Xe + tank (strict '<') | 40 | kg | RFP as recorded; row 5 | requirement-as-recorded | REQUIREMENT_AS_RECORDED (verify against the official RFP) | after-evidence |
| RVM-IT-10 | internal wet design allocation (lower) | 34 | kg | row 53 | owner-allocation | OWNER_ALLOCATION (carried with RVM-IT-11) | NOW |
| RVM-IT-11 | internal wet design allocation (upper) | 36 | kg | row 53 | owner-allocation | OWNER_ALLOCATION (carried with RVM-IT-10) | NOW |
| RVM-IT-12 | internal development / system mass margin | 20 | % | row 52 | owner-stated | OWNER_GIVEN | NOW |
| RVM-IT-13 | mission-life engineering basis | 26280 | h | row 3 | owner-stated | OWNER_GIVEN (engineering basis until the RFP is verified) | after-evidence |
| RVM-IT-14 | provisional firing-time requirement (strict '>') | 15000 | h | row 3 | owner-stated | PROVISIONAL_HARD_REQUIREMENT (row 3) | after-evidence |
| RVM-IT-15 | C1 ignition dwell cap per attempt (preliminary protocol) | 120 | s | row 93 | owner-stated | OWNER_GIVEN (final bound frozen before score-bearing C1 testing) | LOCK-2 |
| RVM-IT-16 | C1 ignition retries per start (preliminary protocol) | 2 | - | row 93 | owner-stated | OWNER_GIVEN; Xe booking of 2 vs 3 dwells is OPEN (OQ-A907-01 / XA9Q-02) | LOCK-2 |
| RVM-IT-17 | indigenous content, total | 75 | % | RFP as recorded (secondary) | requirement-as-recorded | REQUIREMENT_AS_RECORDED (verify against the official RFP) | after-evidence |
| RVM-IT-18 | thermal margin below validated continuous-use limits | 50 | K | row 86 | owner-stated | OWNER_GIVEN | NOW |
| RVM-IT-19 | ICP-45 required electron current I_d,max,H1 | TBD - requires the registered maximum H-1 discharge current from measured / registered H-1 operation (A9.3 OQ-A907-02; not the 8.33 A stand ceiling) | A | A9.1 ICP-45; A9.3 OQ-A907-02 | owner-stated | TBD_AFTER_EVIDENCE | after-evidence |
| RVM-IT-20 | ICP-neutralizer lifetime / cycle requirement | TBD_OWNER - OQ-VI-04 (row 46 requires one; none defined) | h; cycles | row 46 | owner-stated | TBD_OWNER | LOCK-1 |

## (b) Interface demands

| id | direction | counterpart | content | status |
|---|---|---|---|---|
| RVM-ID-01 | RVM <- mass/power v2 | docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json (MPV2-ID-11) | mass rows: < 40 kg wet and 34 / 36 kg from the roll-ups (no CBE); power rows: < 1.5 kW and 1.35 kW from the A9 ledger (all loads TBD); consumed as RVM-04 / -05 / -06 / -07 | CONSUMED |
| RVM-ID-02 | RVM <- Xe accounting v2 | docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json (XV2-IF-09) | Xe accounting states (REFUSED totals with TBD inputs) as SUPPORTING evidence of RVM-03 / -06 / -10; never a Xe-capability demonstration | CONSUMED |
| RVM-ID-03 | RVM <- P4 | docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json (ID-10) | AO / material compatibility: INCOMPLETE_EVIDENCE for every candidate and application; consumed as RVM-16 | CONSUMED |
| RVM-ID-04 | RVM <- P3 | docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json (fail_closed_evaluations) | coupled / anode thermal closure states (UNRESOLVED); consumed as RVM-17 | CONSUMED |
| RVM-ID-05 | RVM <- P1 | docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json (P1-S7 / P1-S7H) | ICP-45 discharge-OFF capacity records (signed I_ON - I_OFF, Kirchhoff admission) are the determining measurement of RVM-15 for hall_icp_neutralizer once they exist; none exist | AWAITING_EVIDENCE |
| RVM-ID-06 | RVM <- A9-01 pre-registration | docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json (DQ-HI-*; HI-ABS, HI-CMP, HI-AO) | score-bearing gate classifications per configuration (DQ-HI-TABS, -SUST, -PBUS, -PALLOC, -IGN, -ECAP, -VCPL) become the determining measurements of RVM-02..-05, -08, -14, -15 | AWAITING_EVIDENCE |
| RVM-ID-07 | RVM <- Hall transport ensemble | hallthruster_bridge/ensemble/transport_ensemble_v0.json | an admitted member would enable VALIDATED_ANALYSIS artifacts (the builder refuses to run when the credible set becomes non-empty until the rules are reviewed) | BLOCKED (credible set empty) |
| RVM-ID-08 | RVM -> M16 refresh | PENDING (M16 refresh after the implementation batch; A9.6 sec. 16) (fo_a9_6_m16_refresh) | requirement-status column per M16 row (m16_impact); no row READY / VERIFIED from this lane | OFFERED |
| RVM-ID-09 | RVM -> consolidated verification | PENDING fo_a9_6_consolidated_verification (A9.6 sec. 18) | rules R0-R7, probes and per-row artifacts for the structural / evidence review | OFFERED |
| RVM-ID-10 | RVM -> owner-question state v4 | PENDING fo_a9_6_decision_propagation (owner-question state v4) | new question RVMQ-01 | OFFERED |
| RVM-ID-11 | RVM -> owner-question state v4 | PENDING fo_a9_6_decision_propagation (owner-question state v4) | lane-24 open decisions carried by RVM rows but absent from owner_questions_state_v3: OD2, OD3, OD5, OD6, OD12, OD13, OD14 (register or declare superseded for the A9 configurations; bookkeeping, no answer implied) | OFFERED |
| RVM-ID-12 | RVM <- official RFP | owner rows 1-2 (legitimate owner / portal route) | the canonical RFP PDF with sha256: every RVM row with requirement_frozen = false re-derives its basis | AWAITING_OWNER_ACTION |

## (c) Owner answers and decisions applied

- Row 1 (WEB-ACC-1; sha256 e16fbaa3a781...): no RFP interpretation frozen: every RFP-recorded row carries requirement_frozen = false
- Row 2 (WEB-ACC-2; sha256 af603606e9e0...): RFP reference / bid date not frozen here
- Row 3 (WEB-RFP-1; sha256 d4b082801ab7...): RVM-12 (> 15,000 h provisional) and RVM-13 (>= 26,280 h basis)
- Row 4 (OD1; sha256 a855c0b49429...): RVM-02 (>= 12 mN sustained atmospheric) and RVM-03 (25 mN capability; Xe not required, booked if used)
- Row 5 (OD-XE-8, OD-M7, H27-Q3; sha256 033b66092382...): RVM-06 wet reading incl. Xe + tank
- Row 6 (OD-XE-6; sha256 a2df92d79838...): RVM-10 bounded functional Xe mode
- Row 24 (D-13; sha256 f512c61dcb42...): RVM-14 recorded start / restart quantities
- Row 26 (D-15, R-14; sha256 3549676dc536...): RVM-03 / RVM-10: Xe points labelled, never atmospheric evidence
- Row 27 (HWQ-10; sha256 a5e26d5d06b8...): RVM-03 25 mN inside the same full boundary; 16.67 mN/kW floor
- Row 36 (R-10; sha256 eda83de4a8ab...): RVM-08 Ar never counts toward DRDO atmospheric requirements
- Row 42 (OD-XE-1, R6-Q2; sha256 afb93b0c07cf...): RVM-10 PHASE_TOTAL_FLOW booking
- Row 46 (OD-XE-5; sha256 49ccf1043315...): RVM-12 C1 15,000 h basis; ICP lifetime / cycle requirement TBD_OWNER (OQ-VI-04)
- Row 52 (OD-M1, H27-Q2; sha256 14168ed8540b...): RVM-06 20 % internal margin; 40 kg hard wet gate
- Row 53 (H27-Q1; sha256 59d47a36bfbf...): RVM-07 34 and 36 kg side by side
- Row 55 (H27-Q4; sha256 44214bd428d2...): RVM-19 limited redundancy carried beside the recorded no-SPF statement
- Row 86 (H25-Q4, H25-Q6; sha256 e9d2eb1f07e6...): RVM-17 >= 50 K margin, 20 % heat-load margin
- Row 87 (OQ-R8-4; sha256 9d0d1a4d6faa...): RVM-17 no unsourced anode target
- Row 88 (HWQ-09; sha256 d932abe4b143...): RVM-15 C1 sized to the measured / derived current demand (CONTROL_FALLBACK)
- Row 93 (H22-OQ-06; sha256 70360d5a7cdd...): RVM-14 120 s dwell cap, two retries (preliminary)
- Row 94 (H22-OQ-07; sha256 964e5c0b6634...): RVM-16 no graphite flight keeper for O / AO exposure
- Row 102 (GP-D03; sha256 22d2ffa98a73...): RVM-09 delivered species state measured; O survival never assumed
- Row 103 (GP-D04; sha256 8d6289fe3b11...): RVM-16 no silver in O / AO-wetted parts
- Row 106 (HWQ-08, OQ-R8-1, OQ-R8-2, OQ-R3-3; sha256 7ea19b29bcfb...): RVM-16 flight anode material open until coupon evidence
- Row 108 (OQ-H24-01; sha256 caedb1162f6e...): RVM-04 spacecraft-DC boundary, steady and start-up
- Row 109 (OQ-H24-02; sha256 8506c9cf6790...): RVM-05 internal ~1.35 kW allocation
- Row 110 (OQ-H24-03; sha256 5227bccf1810...): RVM-04 every active load in a bus slot
- Row 112 (OQ-H24-05; sha256 a2f14a719852...): RVM-14 sequenced start-up peaks
- Row 120 (OD-TS-6; sha256 a6ad1cf6e8a2...): RVM-02 S1a thrust-uncertainty acceptance test at 12 mN
- Row 132 (HWQ-11; sha256 fe6f23c2ddd4...): RVM-08 / -09 / -16 NO_ATOMIC_O; dedicated AO source
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-01`: RVM-04 gate quantity P_bus,1ms,max; ledger alone never PASSes
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-03`: RVM-05 P_ICP,available relation; no fixed split
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `OQ-A902-07`: RVM-05 1350 W active check, 1300 W context
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `ICP-45`: RVM-15 ICP-45 entry condition
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `HIQ-03`: RVM-10 Xe reference / health check
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `HIQ-08`: RVM-08 Ar never in DRDO compliance claims
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `SEQ-peaks`: RVM-14 one peak-class rise per start-up step
- OD_HARDWARE_PIVOT_2026_09_30_A9_1_followup_owner_decisions `A9-03-collector`: RVM-16 collector material via the O / AO coupon programme
- OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `a9_10_statuses`: all rows: the ten A9.2 statuses are carried unchanged; none is turned into PASS
- OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `anode_316L`: RVM-16 316L REJECTED_AS_CURRENT_BASELINE
- OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `anode_approach`: RVM-17 ANODE_BASELINE OPEN
- OD_HARDWARE_PIVOT_2026_09_30_A9_2_a907_followup_owner_decisions `icp_coupled_thermal`: RVM-17 ICP_COUPLED_THERMAL UNRESOLVED
- OD_HARDWARE_PIVOT_2026_09_30_A9_3_post_a9_tier1_owner_decisions `OQ-A907-02`: RVM-15 I_e,required = I_d,max,H1 (TBD); 8.33 A is the stand ceiling only
- OD_HARDWARE_PIVOT_2026_09_30_A9_3_post_a9_tier1_owner_decisions `OQ-VI-05`: RVM-14 Ar topology control engineering-only
- OD_HARDWARE_PIVOT_2026_09_30_A9_3_post_a9_tier1_owner_decisions `OQ-RFQ-06`: RVM-04 mains laboratory RF generator GROUND/FACILITY_ONLY
- OD_HARDWARE_PIVOT_2026_09_30_A9_4_p1_p2_owner_decisions `P1Q-10`: RVM-15 capacity extraction form (discharge OFF)
- OD_HARDWARE_PIVOT_2026_09_30_A9_4_p1_p2_owner_decisions `P1Q-13`: RVM-15 anode floating, body single-point metered ground
- OD_HARDWARE_PIVOT_2026_09_30_A9_5_p1_closure_owner_decisions `P1Q-15`: RVM-15 Kirchhoff admission of capacity records
- OD_HARDWARE_PIVOT_2026_09_30_A9_5_p1_closure_owner_decisions `P1Q-16`: RVM-15 signed I_e,cap = I_RFON - I_RFOFF
- OD_HARDWARE_PIVOT_2026_09_30_A9_6_implementation_first_directive `summary.rvm_states / summary.fixed_statuses`: status vocabulary exactly PASS, FAIL, NOT_EVALUATED, OUT_OF_DOMAIN, INCOMPLETE_EVIDENCE, NUMERICAL_FAILURE; fixed statuses carried: {"316L_FLIGHT_ANODE": "REJECTED_AS_CURRENT_BASELINE", "ANODE_THERMAL_CLOSURE": "UNRESOLVED", "FINAL_ANODE_MATERIAL": "OPEN", "ICP_COUPLED_THERMAL": "UNRESOLVED", "RF_COMPONENT_RATINGS": "TBD_AFTER_IMPEDANCE_MAP"}
- OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer `requirement_discipline / evidence_sequence / control_fallback / status`: status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE; full-system gates; evidence order; C1 control / fallback

## (d) Open owner questions (new in this lane)

- **RVMQ-01** (TBD_OWNER, needed by when the official RFP is obtained (row 1), before Milestone C): If the official RFP confirms 'no single-point failure in electronics' (recorded only in abep_sim/ppu.py, R7), does the row-55 limited-redundancy policy (no duplicated thruster, ICP neutralizer or full PPU at this stage) stand, or must RVM-19 be re-based on the RFP clause? Readings: keep row 55 as is (R7 not an RFP clause or waived) / re-base on the RFP clause (redundant PPU / RF electronics; mass and power impact). Why new: row 55 set the redundancy policy without reference to the R7 statement; the lane-24 OD12 question only asks whether R7 becomes a gate. Genuine design choice (mass / power / FMEA); not answerable from existing decisions.

## (e) Historical reuse

- `docs/traceability/rtm_v1.json` sha256 `21dec718458eb0d50caa2c779ecd2ea6c663cba61d5f1324242d69839a64bc55` - historical requirement traceability matrix v1 (hall_only / rf_hall / ecr_hall)
- `docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json` sha256 `7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f` - historical lane-24 hard-gate matrix v1 (RFP records R1-R7, OD1-OD14)
- `docs/procurement/web_track_v1/threads/R2_rfp.json` sha256 `b2796ff856f041b22c623b87e403b75748e2c25e818b9e8149e5c766f22c4b8c` - web track R2: RFP requirement interpretation (secondary sources; RFP not obtained)
- `docs/traceability/RTM.md` sha256 `ce5b608a5079a86d1b2096f222266f558fab2ebdabc1aa8dfef3153076faa802` - historical companion (read only)
- `docs/traceability/build_rtm.py` sha256 `1f29e4ee85722c060021e4f6e0334135e15e0f719c0fc647a29b22653907667b` - historical companion (read only)
- `docs/architecture_comparison/hard_gates/hard_gate_status_v1.json` sha256 `2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527` - historical companion (read only)
- Reused: requirement list and ids (RTM RFP-* / DER-*), RFP records R1-R7, lane-24 gate ids and open decisions OD1-OD14, R2 secondary quotes (all copied by pointer, pinned by sha256)
- Not reused: the RTM status vocabulary (modeled / partial / open / blocked_by_gate_3) and the historical architectures hall_only / rf_hall / ecr_hall; the lane-24 verdicts (UNDETERMINED for those architectures); the A9 configurations get their own statuses here

## (f) M16 impact

- Row 1 `intake` (v3 BLOCKED): RVM RVM-01, RVM-08, RVM-09 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 2 `filter` (v3 BLOCKED): RVM RVM-08, RVM-09 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 3 `compressor` (v3 BLOCKED): RVM RVM-01, RVM-08 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 4 `buffer_plenum` (v3 BLOCKED): RVM RVM-08 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 5 `atm_metering_valve` (v3 BLOCKED): RVM RVM-08 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 6 `xe_tank` (v3 BLOCKED): RVM RVM-06, RVM-07, RVM-10, RVM-13 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 7 `xe_regulator` (v3 BLOCKED): RVM RVM-10 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 8 `xe_metering` (v3 BLOCKED): RVM RVM-10 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 9 `hall_chamber` (v3 BLOCKED): RVM RVM-01, RVM-02, RVM-03, RVM-08, RVM-09, RVM-11, RVM-12, RVM-13 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 10 `magnetic_circuit` (v3 BLOCKED): RVM RVM-02, RVM-11 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 11 `cathode` (v3 BLOCKED): RVM RVM-12, RVM-13, RVM-14, RVM-15, RVM-16 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 12 `ppu` (v3 BLOCKED): RVM RVM-02, RVM-03, RVM-04, RVM-05, RVM-06, RVM-07, RVM-14, RVM-19 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 13 `thermal_control` (v3 BLOCKED): RVM RVM-17 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 14 `control_fdir` (v3 BLOCKED): RVM RVM-14, RVM-19 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 16 `mechanical_structural` (v3 BLOCKED): RVM RVM-06, RVM-07 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 18 `icp_neutralizer_head` (v3 BLOCKED): RVM RVM-05, RVM-12, RVM-13, RVM-14, RVM-15, RVM-16 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 19 `flight_rf_chain` (v3 BLOCKED): RVM RVM-04, RVM-05, RVM-15 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 20 `h1_anode_material` (v3 BLOCKED): RVM RVM-12, RVM-16, RVM-17 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)
- Row 21 `h1_anode_heat_path` (v3 BLOCKED): RVM RVM-17 - none (requirement-status input to PENDING fo_a9_6_m16_refresh; no row READY/VERIFIED)

## Pins and references

- pinned `docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json` `74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f` (governing owner decision A9)
- pinned `docs/decisions/OD_2026_09_29_owner_answers_147.json` `50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1` (147 owner answers (machine-readable))
- pinned `docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md` `8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976` (147 owner answers (verbatim pack))
- pinned `docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json` `7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4` (owner decisions A9.1)
- pinned `docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json` `e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03` (owner decisions A9.2)
- pinned `docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json` `81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b` (owner decisions A9.3)
- pinned `docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json` `b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d` (owner decisions A9.4)
- pinned `docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json` `c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3` (owner decisions A9.5)
- pinned `docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json` `d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327` (owner directive A9.6)
- pinned `docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md` `c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634` (owner directive A9.6 (verbatim))
- pinned `docs/budgets/owner_decisions/owner_questions_state_v3.json` `1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2` (owner question state v3)
- pinned `docs/EVIDENCE.md` `a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61` (evidence rules (CLAUDE.md rule 10))
- pinned `hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json` `0a57a397883141be20196853b7d722404dc3cb20c72fba666121fd43507dc97c` (P5-N2 v1 vacuum validation release (permanent INCONCLUSIVE; never rewritten))
- pinned `docs/procurement/web_track_v1/threads/R2_rfp.json` `b2796ff856f041b22c623b87e403b75748e2c25e818b9e8149e5c766f22c4b8c` (web track R2: RFP requirement interpretation (secondary sources; RFP not obtained))
- pinned `docs/traceability/rtm_v1.json` `21dec718458eb0d50caa2c779ecd2ea6c663cba61d5f1324242d69839a64bc55` (historical requirement traceability matrix v1 (hall_only / rf_hall / ecr_hall))
- pinned `docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json` `7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f` (historical lane-24 hard-gate matrix v1 (RFP records R1-R7, OD1-OD14))
- read, not pinned: `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` (A9-02 bus-power boundary (1 ms gate, 1.35 kW allocation))
- read, not pinned: `docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json` (A9-01 Hall->ICP pre-registration framework (stages, DQ-HI-*))
- read, not pinned: `docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json` (A9-05 validation-input list (VI-*))
- read, not pinned: `schemas/interfaces/icp_neutralizer_icd_v1.json` (A9-03 ICP neutralizer ICD (ICP-*))
- read, not pinned: `docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json` (A9 ICP neutralizer published-analog evidence (Takahashi et al. 2024))
- read, not pinned: `docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json` (P1 ICP bench workflow (ICP-45 capacity, discharge-OFF))
- read, not pinned: `docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json` (P2 impedance-map framework)
- read, not pinned: `docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json` (P3 coupled-thermal framework)
- read, not pinned: `docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json` (P4 anode / collector materials framework)
- read, not pinned: `docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json` (A9.6 mass + power integration v2)
- read, not pinned: `docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json` (A9.6 Xe accounting v2)
- read, not pinned: `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` (AO / lifetime register v5)
- read, not pinned: `hallthruster_bridge/ensemble/transport_ensemble_v0.json` (Hall transport ensemble (credible set))
- read, not pinned: `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` (feed-state closure (delivered feed vs altitude))
- read, not pinned: `docs/chemistry/o_o2/v0/channel_status_v0.json` (O / O2 chemistry v0 channel status)
- read, not pinned: `docs/procurement/rfq_a9_v2/rfq_a9_v2.json` (RFQ packages v2 (quotation only))
- read, not pinned: `docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json` (M16 subsystem maturity v3)

## Excluded candidates

- PRG-BID: programmatic (bid close date), not a system requirement
- DER-NETDRAG: derived purpose of ABEP; docs/HISTORY.md records that the RFP does not state it; covered physically by RVM-01..-03
- DER-HALL-CLOSURE: an enabler of analysis (probe_hall_analysis), not a system requirement
- DER-MODEL-INTEGRITY: simulator integrity gates (CLAUDE.md rules 1-5), not a system requirement
