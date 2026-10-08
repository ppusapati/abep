# M2 196-state RFP closure - DBF-1 (report v1)

Record `m2_closure_record_v1.json` (sha256 `600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394`), run manifest `m2_run_manifest_v1.json` (`7c29039800f623d59cbeb094dbc25b968e39cc4106d0035b3e6814ac8dee234f`), DBF-1 `dbf1_v1.json` (`d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f`), addendum A8. This report restates the record; it is not the M3 decision.

## Classification (computed, verbatim)

**NOT_DETERMINABLE** at procedure step **C1** (C0, CA4 (A4), C1..C4 verbatim (A9.32); C1 blocker read as HALL_NUMERICS_NOT_CONVERGED (A8)).

## Counts

| mode | required states | layer (a) | layer (b) | Hall closure | non-Hall closure |
|---|---|---|---|---|---|
| AIR_PRIMARY | 196 | {"NOT_DETERMINABLE": 196} | {"NOT_EVALUATED": 196} | {"NOT_EVALUATED": 196} | {"NON_CLOSING_NOT_ELIGIBLE": 54, "OPEN": 142} |
| XE_CONTINGENCY | 196 | {"NOT_DETERMINABLE": 196} | {"NOT_EVALUATED": 196} | {"NOT_EVALUATED": 196} | {"OPEN": 196} |

## Binding constraints, ranked (states)

**AIR_PRIMARY**

| constraint | code | category | type | states |
|---|---|---|---|---|
| HALL_T12_AT_PBUS | HALL_NUMERICS_NOT_CONVERGED | MISSING_EVIDENCE | model-numerics | 142 |
| A5-NH-INTAKE | A5_AREA_BELOW_REQUIRED_T25 | DESIGN_VARIABLE_LIMIT | design-variable | 25 |
| A5-NH-INTAKE | A5_DELIVERED_BELOW_REQUIRED_T25 | DESIGN_VARIABLE_LIMIT | design-variable | 21 |
| A5-NH-INTAKE | A5_CAPTURE_BELOW_REQUIRED_T25 | DESIGN_VARIABLE_LIMIT | design-variable | 7 |
| A5-NH-INTAKE | A5_AREA_BELOW_REQUIRED_T12 | DESIGN_VARIABLE_LIMIT | design-variable | 1 |

**XE_CONTINGENCY**

| constraint | code | category | type | states |
|---|---|---|---|---|
| HALL_XE_FUNCTIONAL_AT_PBUS | HALL_NUMERICS_NOT_CONVERGED | MISSING_EVIDENCE | model-numerics | 196 |

## Blockers by type (required cells, both modes)

- **design-variable**: A5_AREA_BELOW_REQUIRED_T12 (1), A5_AREA_BELOW_REQUIRED_T25 (26), A5_CAPTURE_BELOW_REQUIRED_T12 (3), A5_CAPTURE_BELOW_REQUIRED_T25 (33), A5_DELIVERED_BELOW_REQUIRED_T12 (11), A5_DELIVERED_BELOW_REQUIRED_T25 (54), A8_DBF1_AREA_BELOW_REQUIRED_T12 (1), A8_DBF1_AREA_BELOW_REQUIRED_T25 (26), A8_DBF1_CAPTURE_BELOW_REQUIRED_T12 (3), A8_DBF1_CAPTURE_BELOW_REQUIRED_T25 (33), A8_DBF1_DELIVERED_BELOW_REQUIRED_T12 (11), A8_DBF1_DELIVERED_BELOW_REQUIRED_T25 (54), A8_DBF1_GAS_PATH_OUT_OF_DOMAIN_IN_SCENARIO (18)
- **missing-evidence**: A8_DBF1_ANODE_MATERIAL_FROZEN_P4_EVIDENCE_INCOMPLETE (392), A8_DBF1_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED (25), A8_DBF1_SCENARIO_DEPENDENT (117), BUS_LEDGER_NOT_COMPLETE (392), CHG-04_NO_XE_RATE_SET (196), CREDIBLE_HALL_TRANSPORT_SET_EMPTY (392), DOM-06_B_ICP_NOT_REGISTERED (392), DOM-12_NO_NEGATIVE_ION_BALANCE (196), HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY (392), HOST_DRAG_REFERENCE_PENDING_CUSTOMER_ICD (196), ICP_CAPACITY_NOT_EVALUATED (392), IN-05_DELIVERED_COMPOSITION_TBD (196), IN-08_RF_INPUT_NOT_REGISTERED (392), IN-11_ELECTRODES_NOT_REGISTERED (392), IN-12_NEUTRAL_SOURCE_NOT_REGISTERED (392), IN-16_NO_REGISTERED_RATE_SET:AIR (196), IN-16_NO_REGISTERED_RATE_SET:XE (196), IN-17_NO_EDGE_FACTOR_SOURCE (392), LIFE_NOT_EVALUATED (392), MASS_INCOMPLETE_EVIDENCE (392), NO_HALL_CLOSING_POINT (178), NP-ICP-CHEM-AIR:AIR-DIS-02 (196), NP-ICP-CHEM-AIR:AIR-EL-03 (196), NP-ICP-CHEM-AIR:AIR-EL-04 (196), NP-ICP-CHEM-AIR:AIR-EXC-04 (196), NP-ICP-CHEM-AIR:AIR-EXC-05 (196), NP-ICP-CHEM-AIR:AIR-EXC-09 (196), NP-ICP-CHEM-AIR:AIR-ION-02 (196), NP-ICP-CHEM-AIR:AIR-ION-05 (196), NP-ICP-CHEM-AIR:AIR-NL-02 (196), NP-ICP-CHEM-AIR:AIR-WALL-01 (196), NP-ICP-CHEM-AIR:AIR-WALL-02 (196), NP-ICP-CHEM-AIR:AIR-WALL-03 (196), NP-ICP-CHEM-AIR:XE-EL-01 (196), NP-ICP-CHEM-AIR:XE-EXC-01 (196), NP-ICP-CHEM-AIR:XE-ION-01 (196), NP-ICP-CHEM-AIR:XE-WALL-01 (196), NP_ICP_CHEM_AIR_NOT_ADMITTED (196), NP_ICP_CHEM_AIR_XE_NOT_ADMITTED (196), NP_ICP_NOT_ADMITTED (392), SP-04_SPECIES_BOUND_UNRESOLVED:SB-NO (196), SPACECRAFT_THERMAL_ICD_ABSENT (392), THERMAL_FLIGHT_CASE_NOT_REGISTERED (392), THERMAL_LOADS_NOT_EVALUATED (392), WET_MASS_OBJECTIVE_NOT_EVALUATED (392), XE_FEED_FLOW_NOT_REGISTERED (196), XE_LOAD_NOT_FROZEN (392)
- **model-numerics**: HALL_NUMERICS_NOT_CONVERGED (392)

## What would move each blocker

| codes | type | evidence |
|---|---|---|
| HALL_NUMERICS_NOT_CONVERGED | model-numerics | a converged H-1 Hall subset from the A9.36 numerical-method investigation and a rerun of the registered envelope under its own addendum (A7), consumed on the DBF-1 hardware (G-RP1, BZ-P5B16) without a DCR (A8) |
| A8_DBF1_*_BELOW_REQUIRED_* / A5_*_BELOW_REQUIRED_* | design-variable | a larger effective collection area / higher capture and delivered flow (a DBF-1 DCR with a physical reason: new intake / compressor design, measured accommodation DI-1.3, compressor coefficients T-1 / T-2); a FROZEN A_eff,max (A4-REG-01) would make the A4 bound eligible (CA4) - none is registered (A9.35) |
| A8_DBF1_GAS_PATH_OUT_OF_DOMAIN_IN_SCENARIO | design-variable | dead-head at P_set 0.02 Pa in the low-accommodation scenarios (maxwell / cll alpha 0, 0.2): a DCR on P_set or the compressor, or a preregistered DI-1.3 accommodation measurement narrowing the scenario set |
| A8_DBF1_SCENARIO_DEPENDENT / A8_DBF1_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED | missing-evidence | DI-1.3 accommodation evidence (scenario dependence) and a Hall closing point (a met necessary condition establishes nothing) |
| ICP_CAPACITY_NOT_EVALUATED / IN-* / NP-ICP-CHEM-AIR:* / NP_ICP_* / DOM-* / SP-04 / CHG-04 | missing-evidence | admitted NP-ICP-CHEM-AIR AIR and Xe rate sets, registered RF absorbed power / P2 coupling evidence, electrode potentials and bias range (P1-IT-36 / P1-IT-18), neutral-source pressure, edge-factor source, B_ICP; then a VALIDATED_BENCH I_e,cap (P1 ICP-45) for HC-05 |
| BUS_LEDGER_NOT_COMPLETE | missing-evidence | the 23 TBD ledger terms (Hall discharge at a closing point, magnet coils, RF chain, valves, controls, thermal control) from registered loads |
| THERMAL_* / SPACECRAFT_THERMAL_ICD_ABSENT | missing-evidence | the host spacecraft thermal ICD (SCI-A values), a registered flight thermal case and evaluated Hall / ICP heat loads |
| MASS_INCOMPLETE_EVIDENCE / WET_MASS_OBJECTIVE_NOT_EVALUATED / XE_LOAD_NOT_FROZEN | missing-evidence | a current-best-estimate dry mass (mass-closure actions MCA; compressor CBE vs AL-02) and a selected flight Xe load |
| LIFE_NOT_EVALUATED / HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY / A8_DBF1_ANODE_MATERIAL_FROZEN_P4_EVIDENCE_INCOMPLETE | missing-evidence | wall_life_trustworthy Hall runs (ion_wall_losses = true) and P4 Q0 / Q1 coupon evidence for INCONEL 600 / 601 |
| HOST_DRAG_REFERENCE_PENDING_CUSTOMER_ICD | missing-evidence | the customer host-spacecraft drag ICD (A9.13 S6.18) |
| CREDIBLE_HALL_TRANSPORT_SET_EMPTY | missing-evidence | an admitted Hall transport member (layer (b)) |
| XE_FEED_FLOW_NOT_REGISTERED | missing-evidence | a registered H-1 Xe flow (OQ-HPE-03) |

## DBF-1 baseline deficiencies

| id | finding | category |
|---|---|---|
| DBF1-BD-01 | drag closes (intake-face drag <= 17.59 mN <= 25 mN) but flow does not: the frozen design delivers 1.428e-09 kg/s at its worst state in its worst covered scenario, 33.59 x below the 12 mN necessary flow; A_eff 0.25 m^2 < A_req 0.2511 m^2 | DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound) |
| DBF1-BD-02 | the design is an F7 Pareto member in 6 of 10 admitted scenarios; its FC00 twin is infeasible in the other four (compressor characteristic / dead-head); no registered candidate is robust (F8 robust set EMPTY) | DESIGN_VARIABLE_LIMIT |
| DBF1-BD-03 | the F3 model mass of the selected compressor exceeds the AL-02 allocation; the registered candidates within 5.5 kg (T4 compressors) cover 2 scenarios at ~5x lower delivered flow | DESIGN_VARIABLE_LIMIT |
| DBF1-BD-04 | the current provisional planning roll-up (owner MEV lines + evidence floors; not a CBE) is above the 34 kg nominal-dry target and the 40 kg wet limit at 2 kg Xe (MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED); planning values are never eligible for a non-closure (HR-07) | MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA) |
| DBF1-BD-05 | the simulated field is a P5-shape surrogate scaled into the H1F-BZ-03 band: a Hall non-closure under it is never eligible (envelope prereg bz_family classification_effect) | MISSING_EVIDENCE |
| DBF1-BD-06 | with the frozen geometry and RF, I_e,cap stays NOT_EVALUATED: the remaining inputs are operating points or evidence, not design values | MISSING_EVIDENCE |

M2 confirms: BD-01 L-DEL-DBF1|T12 fails in every admitted scenario at 11 states (worst ds2:ECSS_LT_LOW:alt230:lat-80.0000:lst21:lon0:doy184, k_fav 3.696); L-DEL-DBF1|T25 at 54 states; L-AREA-DBF1|T12 at 1. BD-02 steady point out of domain (dead-head, class R) in some admitted scenario at 18 states. Feed-loop classes {"R": 44, "S": 1916} (Python reference, Rust R2 agreement on every row).

## A9.31 sec. 23 items

- **A_feasible_region**: NOT DETERMINABLE in M2: no Hall thrust value may enter (A9.36)
- **B_physically_feasible_states**: 0
- **C_robust_states**: 0
- **D_worst_state**: {"T_required": {"state_id": "ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1", "T_required_max_mN": 54.45537872932814}, "delivered_flow_T12": {"state_id": "ds2:ECSS_LT_LOW:alt230:lat-80.0000:lst21:lon0:doy184", "k_fav": 3.69574378635125}}
- **E_min_max**: {"thrust": "NOT_EVALUATED (HALL_NUMERICS_NOT_CONVERGED)", "drag_T_required_mN": [1.1578451566619796, 54.45537872932814], "T_minus_D": "NOT_EVALUATED (T_available not evaluated)", "bus_power_nonHall_lower_bound_W": {"AIR_PRIMARY": [9.30487082877053, 9.947070060074756], "XE_CONTINGENCY": [0.0, 0.0], "note": "TBD loads at 0 W; not a P_bus"}, "delivered_atmospheric_mass_flow_kg_s": [8.903924824262307e-11, 1.348732616719161e-06], "delivered_flow_held_state_min_range_kg_s": [8.903924824262307e-11, 4.64055215719246e-07], "icp_electron_current_margin": "NOT_EVALUATED (I_e,cap not evaluable; I_d not evaluated)", "wet_mass_kg": {"planning_rollup_at_2kg_Xe": 40.34901052, "status": "planning value, not a CBE"}}
- **F_constraints_physically_closing**: none is evaluated as closing (every constraint is OPEN, NOT_EVALUATED or NON_CLOSING-not-eligible)
- **G_evidence_limited**: Hall thrust / I_d / P_d, ICP I_e,cap, bus ledger, thermal, mass CBE, life, T - D
- **H_dominant_blocker**: {"code": "HALL_NUMERICS_NOT_CONVERGED", "type": "model-numerics", "category": "MISSING_EVIDENCE"}
- **H_dominant_design_finding**: DBF-1 delivered flow below the A4 necessary condition (DESIGN_VARIABLE_LIMIT, never eligible)
- **I_alternatives**: not part of M2 (M3)

## T_required = D(state) against 12 / 25 mN

Range 1.158-54.46 mN (body 0.7938-36.86 mN, intake 0.364-17.59 mN). Per state, unfavourable scenario: {"GT_HC02_25mN": 40, "HC01_TO_HC02_12_25mN": 73, "LE_HC01_12mN": 83}; favourable: {"GT_HC02_25mN": 39, "HC01_TO_HC02_12_25mN": 72, "LE_HC01_12mN": 85}. Worst ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1 (54.46 mN). Reference body RC-DIAMANT, REFERENCE_PENDING_CUSTOMER_ICD; body sensitivity per declared case in the record.

## Conclusion-category input (A9.31 sec. 20)

D: MODEL CANNOT YET DETERMINE ARCHITECTURE FEASIBILITY. Input to M3, not the decision.

