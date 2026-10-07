# NP-MISSION-INTEGRATION v1 — verification report v1

Verdict: **VERIFIED** (software verification only; validation_status NOT_VALIDATED). Generated from `verification_report_v1.json`.

* Prereg sha256 `9d3a72022ecb236f71a30ead5c31023d166a31e05f6a4f4579c589f62a5d4f79` (cd52b05); addendum 01 `6d8d9ddd6cdf9f87…` (093568a, before implementation).
* Implementation commit `b8f8fc4037ca`; rustc 1.94.1 (e408947bf 2026-03-25).
* The criteria are the preregistered ones; the suite also ran during implementation and no criterion changed after any run.

## Analytic / synthetic cases

| id | test | result |
|---|---|---|
| AL-01 | `al01_constant_rate_and_time_totals` | ok |
| AL-02 | `al02_piecewise_integral_and_ledgers` | ok |
| AL-03 | `al03_xe_ledger_closes_exactly` | ok |
| AL-04 | `al04_time_accounting_and_schedule_refusals` | ok |
| AL-05 | `al05_status_propagation_and_parametric_layer` | ok |
| AL-06 | `integration::quantity::tests::al06_severity_table` | ok |
| AL-07 | `al07_routing_table` | ok |
| AL-08 | `al08_ao_fluence_is_bracketed_by_pb_ao_for_200_schedules` | ok |
| AL-09 | `al09_cancellation_is_exact` | ok |
| AL-10 | `al10_derived_quantities` | ok |
| AL-11 | `al11_planning_cases_are_parametric_and_none_is_selected` | ok |

## Conservation

| id | where | result |
|---|---|---|
| CONS-T1 | AL-01, AL-02, AL-04 (exact expansion equality) | ok |
| CONS-M1 | AL-02, AL-03 (exact closure + 1 ulp on reported values); IV-01 | ok |
| CONS-M2 | AL-02, AL-03 | ok |
| CONS-F1 | AL-01, AL-02 | ok |
| CONS-S1 | today's run: 196 states x 3 modes in file order | ok |
| CONS-I1 | AL-01 (q * (H * S) exact) | ok |

## Fail-closed, determinism

| id | test | result |
|---|---|---|
| FT-01..FT-05 | `ft01_to_ft05_todays_run_fails_closed` | ok |
| FT-06 | `ft06_other_configuration_is_model_error` | ok |
| FT-07 | `al04_time_accounting_and_schedule_refusals (case d)` | ok |
| FT-08 | `al04_time_accounting_and_schedule_refusals (case f)` | ok |
| FT-09 / FT-15 | `ft09_ft15_vocabulary` | ok |
| FT-10 | `ft10_no_requirement_or_assessment_file_is_read (addendum 01)` | ok |
| FT-11 | `ft11_no_xe_from_duration` | ok |
| FT-12 | `ft12_parametric_values_never_reach_evidence` | ok |
| FT-13 | `al04_time_accounting_and_schedule_refusals (case b: exact residual 2^-30 h reported)` | ok |
| FT-14 | `ft14_malformed_input_quantity_is_model_error + integration::quantity::tests::ft14_malformed_quantities_are_model_errors` | ok |
| DET-01 / DET-02 / CONS-S1 | `det01_det02_cons_s1` | ok |
| lock | `prereg_files_match_the_lock` | ok |

## IV-01 (non-authoritative exact-rational cross-check)

204 synthetic cases, 2853 checks, 0 disagreements: Rust within 1 ulp of the correctly rounded rational value everywhere; PB-AO brackets the fluence of all 200 AL-08 schedules.

## Today's run over the frozen 196-state set (IF-MIS-DECISIVE)

Horizons: H_M = 26280.0 h (MISSION_DURATION_BASIS), H_F = 15000.0 h (SUBSYSTEM_FIRING_LIFE_ASSUMPTION). Record byte-identical on two runs.

| layer | status | detail |
|---|---|---|
| environment (abep_atmos::execution) | EVALUATED | 196 states, 196 EVALUATED, 0 OUT_OF_DOMAIN, 0 MODEL_ERROR |
| Hall (abep_hall::status::HallGate) | NOT_EVALUATED | admitted members []; credible Hall transport set EMPTY (no admitted member, no Hall map) |
| RF/ICP AIR_PRIMARY (abep_icp) | NOT_EVALUATED | NP-ICP-NEUTRALIZER ledger status RUST_IMPL (not ADMITTED); NP-ICP-NEUTRALIZER crate status INCOMPLETE_EVIDENCE for the registered-today AIR_PRIMARY case; reason |
| RF/ICP XE_CONTINGENCY (abep_icp) | NOT_EVALUATED | NP-ICP-NEUTRALIZER ledger status RUST_IMPL (not ADMITTED); NP-ICP-NEUTRALIZER crate status INCOMPLETE_EVIDENCE for the registered-today XE_CONTINGENCY case; rea |
| electrical (official_flight_ledger) | INCOMPLETE_EVIDENCE | official flight ledger PARTIAL_BOUNDARY (24 TBD terms; bus_power_boundary_a9_v2) |
| mass (wet_mass objective) | NOT_EVALUATED | m_wet objective NOT_EVALUATED: no CBE or measured mass exists for any BOM line (mass/power v3); the wet roll-ups of the owner reading 'MEV_LEVEL_EVIDENCE_BASED  |

| field | AIR_PRIMARY | XE_CONTINGENCY | NON_FIRING |
|---|---|---|---|
| I_d_A | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| I_ecap_A | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| P_bus_W | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| T_K | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| T_feed_K | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| ao_flux_m2_s | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| drag_body_N | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| drag_intake_N | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| drag_total_N | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| fN2 | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| fO | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| fO2 | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| feed_balance_kg_s | NOT_EVALUATED 196 | NOT_APPLICABLE | NOT_APPLICABLE |
| freestream_mass_flux_kg_m2_s | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| hall_state | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| intake_capture_kg_s | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| mdot_atm_consumed_kg_s | NOT_EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| mdot_atm_delivered_kg_s | NOT_EVALUATED 196 | NOT_APPLICABLE | NOT_APPLICABLE |
| mdot_hall_anode_kg_s | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| mdot_icp_dedicated_kg_s | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| mdot_xe_tank_kg_s | EVALUATED 196 | NOT_EVALUATED 196 | EVALUATED 196 |
| n_O_m3 | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| p_feed_Pa | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_APPLICABLE |
| rho_kg_m3 | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |
| t_minus_d_N | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| thermal_t_max_K | NOT_EVALUATED 196 | NOT_EVALUATED 196 | NOT_EVALUATED 196 |
| thrust_N | NOT_EVALUATED 196 | NOT_EVALUATED 196 | EVALUATED 196 |
| v_orbital_m_s | EVALUATED 196 | EVALUATED 196 | EVALUATED 196 |

Structural zeros (EVALUATED 0, evidence_class structural) appear only at the registered routing cells (Xe draw in AIR_PRIMARY under G-REUSE; atmospheric consumption in XE_CONTINGENCY; NON_FIRING thrust / draws).

Environment envelopes (model-derived from the frozen set, AIR_PRIMARY rows; the environment is mode independent):

| field | min | max |
|---|---|---|
| T_K | 469.649 (ds2:ECSS_LT_LOW:alt180:lat-80.0000:lst21:lon0:doy184) | 1824.27 (ds2:ECSS_ST_HIGH:alt230:lat-87.0000:lst0:lon180:doy184) |
| ao_flux_m2_s | 2.5139e+18 (ds2:ECSS_ST_HIGH:alt230:lat-87.0000:lst3:lon240:doy184) | 1.57843e+20 (ds2:ECSS_ST_HIGH:alt180:lat-4.0000:lst9:lon60:doy92) |
| fN2 | 0.13887 (ds2:ECSS_LT_LOW:alt230:lat-81.0000:lst21:lon0:doy138) | 0.910234 (ds2:ECSS_ST_HIGH:alt180:lat+71.0000:lst0:lon0:doy184) |
| fO | 0.0295436 (ds2:ECSS_ST_HIGH:alt180:lat-86.0000:lst3:lon240:doy184) | 0.849435 (ds2:ECSS_LT_LOW:alt230:lat-81.0000:lst21:lon0:doy138) |
| fO2 | 0.00589021 (ds2:ECSS_ST_HIGH:alt230:lat-1.0000:lst15:lon0:doy92) | 0.0991939 (ds2:ECSS_LT_LOW:alt180:lat+67.0000:lst6:lon240:doy229) |
| freestream_mass_flux_kg_m2_s | 1.85738e-07 (ds2:ECSS_LT_LOW:alt230:lat-84.0000:lst0:lon60:doy184) | 8.59252e-06 (ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1) |
| mdot_xe_tank_kg_s | 0 (ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47) | 0 (ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47) |
| n_O_m3 | 3.23507e+14 (ds2:ECSS_ST_HIGH:alt230:lat-87.0000:lst3:lon240:doy184) | 2.02354e+16 (ds2:ECSS_ST_HIGH:alt180:lat-4.0000:lst9:lon60:doy92) |
| rho_kg_m3 | 2.39021e-11 (ds2:ECSS_LT_LOW:alt230:lat-84.0000:lst0:lon60:doy184) | 1.10155e-09 (ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1) |
| v_orbital_m_s | 7770.77 (ds2:ECSS_LT_HIGH:alt230:lat+2.0000:lst15:lon0:doy92) | 7800.37 (ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47) |

PB-AO (PARAMETRIC_BOUND, not evidence): [2.378e+26, 1.493e+28] m^-2 over H_M; the evidence-qualified fluence is NOT_EVALUATED (no schedule).

Schedule: NOT_EVALUATED (MISSION_SCHEDULE_NOT_REGISTERED): every mission total carries no value. Mass: m_dry NOT_EVALUATED, m_xe,0 NOT_EVALUATED (XE_LOAD_NOT_FROZEN); planning cases [2.0, 5.0, 10.0] kg carried together, none selected, no ledger formed (consumption NOT_EVALUATED).

## Ledger update requested

* NP-MISSION-INTEGRATION: VERIFIED (software verification; validation_status NOT_VALIDATED)
* C-ABEP_SIM_MISSION_ENV_PY: function subset ADMITTED under PARITY-C-ABEP_SIM_MISSION_ENV_PY-PROPAGATION-V1 (with the constants kernel already ADMITTED); spacecraft_drag NOT_PORTED (lane brief), pointing_factors AUDITED_NOT_PORTED (OQ-MI-03), plume_interaction / ARRAY_AREAL_KG_M2 not in scope (class-H callers)
