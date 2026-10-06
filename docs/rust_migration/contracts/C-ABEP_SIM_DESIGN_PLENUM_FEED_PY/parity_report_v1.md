# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V1

Verdict: **PARITY_FAIL** (NOT_ADMITTED). Generated from the JSON report next to this file.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v1.json` sha256 `ab93bbde3f2f3e98e61c511f03633fdf3fcd4611e282c2152aec74e3bcbebff3`, registered in `fd124442c10d`.
* Python reference commit `e3b7e6712d10`; Rust commit `59e32b57293c`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905303 (scoring); 3815 vectors; 247 per-test failures.

## Checks

* per_test: FAIL
* determinism: pass
* invariants_and_conservation: pass
* materials_equal_db: pass
* threshold_proximity_limit: pass
* all: FAIL

## Vectors per entry

| entry | n | Python refusals | Rust refusals | not scored at threshold |
|---|---|---|---|---|
| plenum.orbital_period | 100 | 0 | 0 | 0 |
| plenum.cbar | 100 | 0 | 0 | 0 |
| plenum.kt_over_m | 100 | 0 | 0 | 0 |
| plenum.intake | 150 | 0 | 0 | 0 |
| plenum.f1_candidate_id | 50 | 0 | 0 | 0 |
| plenum.filter_case | 114 | 29 | 29 | 0 |
| plenum.filter_cases | 4 | 0 | 0 | 0 |
| plenum.plenum | 108 | 8 | 8 | 0 |
| plenum.plant | 200 | 0 | 0 | 0 |
| plenum.chain | 200 | 0 | 0 | 0 |
| plenum.solve_pressures | 200 | 0 | 0 | 0 |
| plenum.steady | 440 | 10 | 10 | 0 |
| plenum.evaluate | 100 | 0 | 0 | 0 |
| plenum.sweep | 12 | 0 | 0 | 0 |
| plenum.area_for_pressure | 83 | 3 | 3 | 0 |
| plenum.bisection_failed | 14 | 0 | 0 | 0 |
| plenum.lambda_upper | 10 | 0 | 0 | 0 |
| plenum.segment_metrics | 150 | 0 | 0 | 0 |
| plenum.settling | 30 | 0 | 0 | 0 |
| plenum.domain_reasons | 20 | 0 | 0 | 0 |
| plenum.ripple | 10 | 0 | 0 | 0 |
| plenum.inlet_tau | 10 | 0 | 0 | 0 |
| plenum.transient_run | 17 | 3 | 3 | 0 |
| plenum.transient_case | 17 | 0 | 0 | 0 |
| plenum.event_sequence | 2 | 0 | 0 | 0 |
| plenum.orbit_qs | 10 | 0 | 0 | 0 |
| plenum.orbit_sim | 4 | 0 | 0 | 0 |
| plenum.strict_blockers | 1 | 0 | 0 | 0 |
| plenum.status_from_reasons | 25 | 0 | 0 | 0 |
| plenum.reasons_from_bits | 25 | 0 | 0 | 0 |
| plenum.scheduled | 22 | 2 | 2 | 0 |
| plenum.compare_modes | 7 | 1 | 1 | 0 |
| plenum.pareto_ids | 25 | 0 | 0 | 0 |
| plenum.controller_state | 25 | 0 | 0 | 0 |
| reservoir.conductance | 100 | 0 | 0 | 0 |
| reservoir.steady | 301 | 1 | 1 | 0 |
| reservoir.size_orifice | 100 | 0 | 0 | 0 |
| reservoir.startup | 60 | 0 | 0 | 0 |
| plenum.constants | 1 | 0 | 0 | 0 |
| upstream.constants | 1 | 0 | 0 | 0 |
| upstream.pressure_domain | 30 | 0 | 0 | 0 |
| upstream.classify | 30 | 6 | 6 | 0 |
| upstream.combine | 30 | 2 | 2 | 0 |
| upstream.constraint | 30 | 0 | 0 | 0 |
| upstream.control | 55 | 2 | 2 | 0 |
| upstream.setpoint | 415 | 20 | 20 | 0 |
| upstream.controller_view | 5 | 3 | 3 | 0 |
| upstream.schedule_input | 40 | 22 | 22 | 0 |
| upstream.h1_tolerance | 48 | 15 | 15 | 0 |
| upstream.governing_band | 40 | 4 | 4 | 0 |
| upstream.coverage | 40 | 0 | 0 | 0 |
| upstream.fixed_gate | 3 | 2 | 2 | 0 |
| upstream.flight_requirement | 4 | 0 | 0 | 0 |
| upstream.flow_gap | 1 | 0 | 0 | 0 |
| upstream.lowering | 20 | 18 | 18 | 0 |
| upstream.state_coverage | 40 | 1 | 1 | 0 |
| upstream.robust_set | 30 | 17 | 17 | 0 |
| upstream.candidate | 2 | 2 | 2 | 0 |
| upstream.verify_decisions | 1 | 0 | 0 | 0 |
| upstream.cite | 2 | 0 | 0 | 0 |
| upstream.dense | 1 | 0 | 0 | 0 |

## Float observables (non-bit-identical leaves only; every scored leaf is in the JSON report)

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| plenum.steady | a_eq_m2 | ULP_BOUNDED | 385 | 0 | 368 | 1.11e-16 | 3.42e-15 | 25 |
| plenum.steady | bisection_residual_rel | ULP_BOUNDED | 385 | 0 | 375 | 4.44e-16 | 1 | 8.99e+307 |
| plenum.steady | domain_diagnostics/feed_Kn_upper_O_omitted | ULP_BOUNDED | 318 | 0 | 309 | 6.25e-13 | 1.68e-15 | 11 |
| plenum.steady | offered/mdot_s_kgps/<s> | ULP_BOUNDED | 75 | 0 | 73 | 1.32e-23 | 7.01e-16 | 5 |
| plenum.steady | offered/P_Pa | ULP_BOUNDED | 20 | 0 | 19 | 1.04e-17 | 8.73e-16 | 6 |
| plenum.steady | offered/p_s_Pa/<s> | ULP_BOUNDED | 75 | 0 | 72 | 4.34e-18 | 1.37e-15 | 8 |
| plenum.steady | offered/x_s_flow_mole/<s> | ULP_BOUNDED | 75 | 0 | 73 | 5.55e-17 | 8.01e-16 | 5 |
| plenum.steady | offered/w_s_flow_mass/<s> | ULP_BOUNDED | 75 | 0 | 73 | 1.11e-16 | 6.52e-16 | 3 |
| plenum.steady | offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 75 | 0 | 72 | 1.11e-16 | 5.22e-16 | 4 |
| plenum.steady | compressor_inlet_p_s_Pa/<s> | ULP_BOUNDED | 75 | 0 | 74 | 3.39e-21 | 1.62e-16 | 1 |
| plenum.steady | mdot_compressor_gross_kgps/<s> | ULP_BOUNDED | 75 | 0 | 74 | 1.32e-23 | 1.74e-16 | 1 |
| plenum.steady | mdot_compressor_backleak_kgps/<s> | ULP_BOUNDED | 75 | 0 | 72 | 8.08e-27 | 1.4e-15 | 9 |
| plenum.steady | mdot_plenum_leak_kgps/<s> | ULP_BOUNDED | 75 | 0 | 72 | 2.52e-28 | 1.35e-15 | 9 |
| plenum.steady | mdot_recombined_O_kgps | ULP_BOUNDED | 25 | 0 | 24 | 3.31e-24 | 9.35e-16 | 8 |
| plenum.steady | mdot_intake_net_kgps/<s> | ULP_BOUNDED | 75 | 0 | 74 | 4.14e-25 | 1.75e-16 | 1 |
| plenum.steady | compressor/P_gas_W | ULP_BOUNDED | 25 | 0 | 24 | 1.11e-16 | 1.53e-16 | 1 |
| plenum.steady | compressor/p_stage_max_Pa | ULP_BOUNDED | 21 | 0 | 20 | 5.2e-18 | 4.36e-16 | 3 |
| plenum.steady | feed/a_eq_m2 | ULP_BOUNDED | 25 | 0 | 24 | 1.73e-17 | 8.65e-16 | 5 |
| plenum.steady | feed/d_eq_m | ULP_BOUNDED | 25 | 0 | 24 | 8.33e-17 | 5.21e-16 | 3 |
| plenum.steady | feed/Kn_upper_O_omitted | ULP_BOUNDED | 25 | 0 | 24 | 4.44e-15 | 5.72e-16 | 5 |
| plenum.steady | feed/lambda_upper_m | ULP_BOUNDED | 25 | 0 | 24 | 1.33e-15 | 1.07e-15 | 6 |
| plenum.evaluate | a_eq_m2 | ULP_BOUNDED | 66 | 0 | 63 | 1.39e-17 | 1.99e-16 | 1 |
| plenum.evaluate | bisection_residual_rel | ULP_BOUNDED | 66 | 0 | 63 | 2.22e-16 | 0.5 | 4.49e+307 |
| plenum.evaluate | domain_diagnostics/compressor_K_over_K0_max | ULP_BOUNDED | 50 | 0 | 49 | 2.22e-16 | 3.34e-16 | 2 |
| plenum.evaluate | domain_diagnostics/feed_Kn_upper_O_omitted | ULP_BOUNDED | 52 | 0 | 50 | 5.68e-14 | 1.47e-16 | 1 |
| plenum.sweep | sweep/mdot_s_kgps/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5756 | 1.32e-23 | 5.7e-16 | 5 |
| plenum.sweep | sweep/x_s_flow_mole/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5757 | 1.11e-16 | 2.82e-16 | 2 |
| plenum.sweep | sweep/a_eq_m2/[]/[] | ULP_BOUNDED | 1920 | 0 | 1918 | 1.73e-17 | 8.81e-16 | 5 |
| plenum.sweep | sweep/bisection_residual_rel/[]/[] | ULP_BOUNDED | 1920 | 0 | 1919 | 4.44e-16 | 2 | 9.01e+15 |
| plenum.sweep | sweep/Kn_upper/[]/[] | ULP_BOUNDED | 1920 | 0 | 1919 | 7.11e-15 | 6.57e-16 | 4 |
| plenum.area_for_pressure | a_eq | ULP_BOUNDED | 80 | 0 | 77 | 1.36e-20 | 1.6e-16 | 1 |
| plenum.area_for_pressure | resid | ULP_BOUNDED | 80 | 0 | 78 | 4.44e-16 | 0.333 | 2.25e+15 |
| plenum.segment_metrics | valve_travel | ULP_BOUNDED | 150 | 0 | 129 | 8.88e-16 | 4.16e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_P | ULP_BOUNDED | 36 | 0 | 26 | 1.11e-16 | 2.41e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_mdot | ULP_BOUNDED | 36 | 0 | 26 | 1.11e-16 | 3.76e-16 | 2 |
| plenum.transient_run | segments/[]/t/[] | SOLVER_TOLERANCE | 16912 | 0 | 15960 | 3.55e-15 | 2.09e-16 | 1 |
| plenum.transient_run | segments/[]/p/[] | SOLVER_TOLERANCE | 16912 | 0 | 1548 | 6.85e-07 | 5.64e-05 | 3.2e+11 |
| plenum.transient_run | segments/[]/mdot/[] | SOLVER_TOLERANCE | 16912 | 112 | 1125 | 1.62e-12 | 1.01 | 8.15e+15 |
| plenum.transient_run | segments/[]/u/[] | SOLVER_TOLERANCE | 16912 | 0 | 1108 | 0.000227 | 1.01 | 8.92e+15 |
| plenum.transient_run | segments/[]/xO/[] | SOLVER_TOLERANCE | 16912 | 3 | 1312 | 3.21e-06 | 5.64e-05 | 4.32e+11 |
| plenum.transient_run | segments/[]/K_min | SOLVER_TOLERANCE | 112 | 9 | 36 | 4.17e+38 | 29.1 | 1.38e+17 |
| plenum.transient_run | segments/[]/K_over_K0_max | SOLVER_TOLERANCE | 112 | 0 | 96 | 8.79e-05 | 8.79e-05 | 3.96e+11 |
| plenum.transient_run | segments/[]/p_stage_max_Pa | SOLVER_TOLERANCE | 112 | 46 | 8 | 1.76e+67 | 1 | 7.31e+15 |
| plenum.transient_run | segments/[]/p_inlet_max_Pa | SOLVER_TOLERANCE | 112 | 0 | 20 | 8.84e-10 | 1.15e-07 | 1.02e+09 |
| plenum.transient_run | segments/[]/P_el_max_W | SOLVER_TOLERANCE | 112 | 35 | 10 | 5.11e+66 | 1 | 7.63e+15 |
| plenum.transient_run | segments/[]/T_comp_max_K | SOLVER_TOLERANCE | 112 | 35 | 10 | 1.28e+67 | 1 | 6.08e+15 |
| plenum.transient_run | throughput_kg | SOLVER_TOLERANCE | 14 | 0 | 2 | 3.01e-15 | 1.39e-10 | 8.89e+05 |
| plenum.transient_case | metrics/[]/P_final_Pa | SOLVER_TOLERANCE | 120 | 0 | 6 | 2.59e-06 | 0.000642 | 2.99e+12 |
| plenum.transient_case | metrics/[]/mdot_final_kgps | SOLVER_TOLERANCE | 120 | 0 | 9 | 2.86e-13 | 1 | 8.24e+15 |
| plenum.transient_case | metrics/[]/P_min_Pa | SOLVER_TOLERANCE | 120 | 0 | 11 | 3.12e-07 | 8.98e-05 | 7.2e+11 |
| plenum.transient_case | metrics/[]/P_max_Pa | SOLVER_TOLERANCE | 120 | 0 | 4 | 3.4e-07 | 5.57e-05 | 3.92e+11 |
| plenum.transient_case | metrics/[]/mdot_min_kgps | SOLVER_TOLERANCE | 120 | 0 | 4 | 3.14e-14 | 1 | 8.24e+15 |
| plenum.transient_case | metrics/[]/mdot_max_kgps | SOLVER_TOLERANCE | 120 | 0 | 6 | 9.07e-14 | 0.000442 | 3.51e+12 |
| plenum.transient_case | metrics/[]/xO_min | SOLVER_TOLERANCE | 120 | 0 | 4 | 4.51e-07 | 0.00328 | 1.66e+13 |
| plenum.transient_case | metrics/[]/xO_max | SOLVER_TOLERANCE | 120 | 0 | 4 | 8.08e-07 | 0.000322 | 1.86e+12 |
| plenum.transient_case | metrics/[]/valve_travel | SOLVER_TOLERANCE | 120 | 0 | 1 | 0.00348 | 3.5 | 1.58e+16 |
| plenum.transient_case | metrics/[]/u_min | SOLVER_TOLERANCE | 120 | 1 | 5 | 0.000155 | 1 | 6.24e+15 |
| plenum.transient_case | metrics/[]/u_max | SOLVER_TOLERANCE | 120 | 0 | 12 | 0.000154 | 0.000229 | 1.39e+12 |
| plenum.transient_case | metrics/[]/final_setpoint_error_frac | SOLVER_TOLERANCE | 120 | 6 | 7 | 0.000518 | 2.2 | 3.51e+307 |
| plenum.transient_case | metrics/[]/settling_time_s | SOLVER_TOLERANCE | 111 | 0 | 106 | 2.22e-16 | 1.66e-16 | 1 |
| plenum.transient_case | metrics/[]/flow_recovery_s | SOLVER_TOLERANCE | 120 | 0 | 118 | 3.55e-15 | 1.8e-16 | 1 |
| plenum.transient_case | metrics/[]/peak_deviation_frac | SOLVER_TOLERANCE | 90 | 0 | 5 | 6.25e-05 | 1 | 7.63e+15 |
| plenum.transient_case | metrics/[]/overshoot_frac | SOLVER_TOLERANCE | 30 | 0 | 9 | 0.0101 | 1 | +inf |
| plenum.transient_case | summary/P_min_Pa | SOLVER_TOLERANCE | 15 | 0 | 0 | 3.08e-07 | 8.98e-05 | 7.11e+11 |
| plenum.transient_case | summary/P_max_Pa | SOLVER_TOLERANCE | 15 | 0 | 0 | 8.37e-08 | 6.34e-06 | 4.8e+10 |
| plenum.transient_case | summary/mdot_min_kgps | SOLVER_TOLERANCE | 15 | 0 | 2 | 4.63e-15 | 1 | 8.24e+15 |
| plenum.transient_case | summary/mdot_max_kgps | SOLVER_TOLERANCE | 15 | 0 | 0 | 9.07e-14 | 0.000442 | 3.51e+12 |
| plenum.transient_case | summary/xO_flow_min | SOLVER_TOLERANCE | 15 | 0 | 0 | 4.43e-07 | 1.62e-05 | 9.41e+10 |
| plenum.transient_case | summary/xO_flow_max | SOLVER_TOLERANCE | 15 | 0 | 0 | 6.77e-08 | 2.67e-05 | 1.56e+11 |
| plenum.transient_case | summary/overshoot_max | SOLVER_TOLERANCE | 15 | 0 | 4 | 0.0101 | 1 | 5.96e+15 |
| plenum.transient_case | summary/a_eq_design_m2 | SOLVER_TOLERANCE | 15 | 0 | 14 | 4.24e-22 | 1.24e-16 | 1 |
| plenum.transient_case | summary/a_eq_max_m2 | SOLVER_TOLERANCE | 15 | 0 | 14 | 8.47e-22 | 1.19e-16 | 1 |
| plenum.transient_case | summary/plenum_tau_s/[] | SOLVER_TOLERANCE | 30 | 0 | 29 | 8.88e-16 | 2.08e-16 | 1 |
| plenum.transient_case | objectives/valve_travel | SOLVER_TOLERANCE | 15 | 0 | 0 | 0.0015 | 0.00018 | 8.19e+11 |
| plenum.transient_case | objectives/settling_max_s | SOLVER_TOLERANCE | 13 | 0 | 12 | 2.22e-16 | 1.66e-16 | 1 |
| plenum.transient_case | objectives/peak_deviation_max | SOLVER_TOLERANCE | 15 | 0 | 0 | 6.16e-05 | 0.000196 | 1.11e+12 |
| plenum.orbit_qs | rows/[]/ripple_pp_frac_mdot | ULP_BOUNDED | 2 | 0 | 0 | 1.11e-16 | 2.18e-16 | 1 |
| plenum.orbit_sim | P_dev_max_frac | SOLVER_TOLERANCE | 3 | 0 | 0 | 2.09e-07 | 0.00289 | 1.54e+13 |
| plenum.orbit_sim | mdot_min_kgps | SOLVER_TOLERANCE | 3 | 0 | 0 | 6.86e-13 | 8.55e-06 | 5.18e+10 |
| plenum.orbit_sim | mdot_max_kgps | SOLVER_TOLERANCE | 3 | 0 | 0 | 7.7e-14 | 3.58e-07 | 2.41e+09 |
| plenum.scheduled | rows/[]/a_eq_m2 | ULP_BOUNDED | 57 | 0 | 54 | 6.94e-18 | 2.12e-16 | 1 |
| plenum.scheduled | rows/[]/offered/mdot_s_kgps/<s> | ULP_BOUNDED | 39 | 0 | 37 | 2.65e-23 | 1.3e-16 | 1 |
| plenum.scheduled | rows/[]/offered/mdot_total_kgps | ULP_BOUNDED | 13 | 0 | 12 | 5.29e-23 | 2e-16 | 1 |
| plenum.scheduled | rows/[]/offered/p_s_Pa/<s> | ULP_BOUNDED | 39 | 0 | 37 | 4.34e-19 | 2.49e-16 | 2 |
| plenum.scheduled | rows/[]/offered/x_s_flow_mole/<s> | ULP_BOUNDED | 39 | 0 | 37 | 2.78e-17 | 3.56e-16 | 2 |
| plenum.scheduled | rows/[]/offered/w_s_flow_mass/<s> | ULP_BOUNDED | 39 | 0 | 37 | 1.39e-17 | 2.88e-16 | 2 |
| plenum.scheduled | rows/[]/offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 39 | 0 | 37 | 2.78e-17 | 3.19e-16 | 2 |
| plenum.compare_modes | baseline/rows/[]/a_eq_m2 | ULP_BOUNDED | 8 | 0 | 7 | 3.39e-21 | 1.25e-16 | 1 |

Scored float leaves: 176316 (110535 bit-identical); EXACT_VALUE leaves: 68761.

Reported, not scored:

* plenum.steady conservation_residual_rel: n 25, max abs diff 0, max rel diff 0
* plenum.evaluate conservation_residual_rel: n 4, max abs diff 0, max rel diff 0
* plenum.transient_run segments/[]/_ucmd_end: n 112, max abs diff 0.000131, max rel diff 0.00292
* plenum.transient_run mass_residual_rel: n 14, max abs diff 4.17e-16, max rel diff 56.1
* plenum.transient_run nfev: n 14, max abs diff 3.38e+04, max rel diff 12.4
* plenum.transient_case summary/mass_residual_rel: n 15, max abs diff 1.15e-15, max rel diff 118
* plenum.transient_case summary/nfev: n 15, max abs diff 9.26e+04, max rel diff 13
* plenum.orbit_sim mass_residual_rel: n 3, max abs diff 1.8e-16, max rel diff 1.3
* plenum.orbit_sim nfev: n 3, max abs diff 3.12e+03, max rel diff 17.5
* reservoir.steady iterations: n 300, max abs diff 0, max rel diff 0

## Domain / error parity

171 vectors with a refusal on either side, 0 mismatches.

| entry | Python | Rust | n |
|---|---|---|---|
| plenum.area_for_pressure | ValueError | ValueError | 3 |
| plenum.compare_modes | ValueError | ValueError | 1 |
| plenum.filter_case | FilterStageError | FilterStageError | 29 |
| plenum.plenum | ValueError | ValueError | 8 |
| plenum.scheduled | ValueError | ValueError | 2 |
| plenum.steady | ZeroDivisionError | ZeroDivisionError | 10 |
| plenum.transient_run | ValueError | ValueError | 3 |
| reservoir.steady | KeyError | KeyError | 1 |
| upstream.candidate | A913RuleError | A913RuleError | 2 |
| upstream.classify | A913RuleError | A913RuleError | 6 |
| upstream.combine | A913RuleError | A913RuleError | 2 |
| upstream.control | A913RuleError | A913RuleError | 2 |
| upstream.controller_view | A913RuleError | A913RuleError | 3 |
| upstream.fixed_gate | A913RuleError | A913RuleError | 2 |
| upstream.governing_band | A913RuleError | A913RuleError | 4 |
| upstream.h1_tolerance | A913RuleError | A913RuleError | 15 |
| upstream.lowering | A913RuleError | A913RuleError | 18 |
| upstream.robust_set | A913RuleError | A913RuleError | 13 |
| upstream.robust_set | RepresentativeSelectionRefused | RepresentativeSelectionRefused | 4 |
| upstream.schedule_input | A913RuleError | A913RuleError | 22 |
| upstream.setpoint | A913RuleError | A913RuleError | 20 |
| upstream.state_coverage | A913RuleError | A913RuleError | 1 |

## Threshold proximity

0 vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % limit: none.

## Invariants and conservation

* Rust two processes byte-identical: True (stdout sha256 `c147f3bbd32f551b...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-P-02: {"n": 1920, "n_fail": 0, "failures": [], "ok": true}
* INV-P-04: {"ok": true}
* CONS-P-01: {"n": 29, "n_fail": 0, "ok": true, "max_residual_over_floor": 2.77870126460643e-16}
* CONS-P-02: {"n": 29, "n_fail": 0, "ok": true, "max_residual_rel": 1.0333316916456899e-12}
* CONS-P-03: {"n": 32, "n_fail": 0, "ok": true, "max_mass_residual_rel": 4.011781278074797e-15}
* CONS-P-04: {"n": 300, "n_fail": 0, "ok": true, "max_balance_residual_rel": 2.0270884311340592e-16}

## Performance (reported, never a criterion)

* PERF-P-01 (12 vectors): Python 0.068 s, Rust 0.108 s (median of 3; speed-up 0.6x; the 12 P38 steady sweeps (Rust request also runs the scalar twin)).
* PERF-P-02 (12 vectors): Python 0.708 s, Rust 0.204 s (median of 3; speed-up 3.5x; the 12 production transient_case vectors).
* PERF-P-03 (300 vectors): Python 0.027 s, Rust 0.035 s (median of 3; speed-up 0.8x; the 300 P49 Reservoir.steady_state vectors).

## Failures (first 50)

* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.818105188234859e-20", "python": "1.815733316840589e-20", "path": "segments/1/mdot/128", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.5314693033864145e-22", "python": "9.630189428629306e-23", "path": "segments/1/mdot/129", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "7.912511790888797e-25", "python": "1.4205167331317562e-23", "path": "segments/1/mdot/130", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "2.312426503490989e-27", "python": "-3.356460188367867e-25", "path": "segments/1/mdot/131", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "3.275602946795516e-30", "python": "1.9117891932022546e-24", "path": "segments/1/mdot/132", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.4043488100894177e-33", "python": "-2.7781788000177655e-25", "path": "segments/1/mdot/133", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "-2.9503971267082946e-37", "python": "1.4327435107632315e-25", "path": "segments/1/mdot/134", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.8252360204274177e-40", "python": "8.461898022492827e-27", "path": "segments/1/mdot/135", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "-1.5898648199215907e-43", "python": "-7.938899303242821e-26", "path": "segments/1/mdot/136", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.6005086807894673e-46", "python": "1.1908185829820134e-25", "path": "segments/1/mdot/137", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "-1.6674774391017e-49", "python": "-1.529064693052075e-26", "path": "segments/1/mdot/138", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.635559921176952e-52", "python": "6.537849141126663e-26", "path": "segments/1/mdot/139", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "-1.3500974943359892e-55", "python": "-2.85229020590232e-26", "path": "segments/1/mdot/140", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "7.8438581725025056e-59", "python": "1.1691900167181959e-26", "path": "segments/1/mdot/141", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "-2.034660054896562e-62", "python": "-1.6639172774887607e-26", "path": "segments/1/mdot/142", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/xO/[]", "rust": "0.00021479375528787092", "python": "'NaN'", "path": "segments/1/xO/131", "tolerance": {"rel": 0.0, "abs": 0.001}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/xO/[]", "rust": "0.00021316045885650422", "python": "'NaN'", "path": "segments/1/xO/133", "tolerance": {"rel": 0.0, "abs": 0.001}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/xO/[]", "rust": "'NaN'", "python": "0.00021225218778746205", "path": "segments/1/xO/134", "tolerance": {"rel": 0.0, "abs": 0.001}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/K_min", "rust": "-9.53226900100708", "python": "-77.15963244438171", "path": "segments/2/K_min", "tolerance": {"rel": 0.001, "abs": 1e-06}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/p_stage_max_Pa", "rust": "0.0775086027171915", "python": "0.07904483069402587", "path": "segments/3/p_stage_max_Pa", "tolerance": {"rel": 0.001, "abs": 1e-06}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-00", "entry": "plenum.transient_run", "observable": "segments/[]/p_stage_max_Pa", "rust": "0.07904397275323875", "python": "0.07750889335063683", "path": "segments/4/p_stage_max_Pa", "tolerance": {"rel": 0.001, "abs": 1e-06}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "1.2669190903777322e-12", "python": "1.2683297072740683e-12", "path": "segments/1/mdot/147", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "7.334413311643842e-12", "python": "7.325677110706838e-12", "path": "segments/4/mdot/149", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288374090910147e-12", "python": "9.297839994341432e-12", "path": "segments/4/mdot/150", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288374090910147e-12", "python": "9.297839994341432e-12", "path": "segments/5/mdot/0", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288812634399008e-12", "python": "9.298278817125474e-12", "path": "segments/5/mdot/1", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288855242202242e-12", "python": "9.298321452063874e-12", "path": "segments/5/mdot/2", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288901989737398e-12", "python": "9.298368229370533e-12", "path": "segments/5/mdot/3", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.288953279229543e-12", "python": "9.298419551526646e-12", "path": "segments/5/mdot/4", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289009551987385e-12", "python": "9.298475860121931e-12", "path": "segments/5/mdot/5", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289071292201507e-12", "python": "9.298537639655293e-12", "path": "segments/5/mdot/6", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.28913903111184e-12", "python": "9.298605421704939e-12", "path": "segments/5/mdot/7", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.28921335158026e-12", "python": "9.298679789503889e-12", "path": "segments/5/mdot/8", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289294893107761e-12", "python": "9.298761382960325e-12", "path": "segments/5/mdot/9", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289384357339418e-12", "python": "9.298850904166084e-12", "path": "segments/5/mdot/10", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289482514104652e-12", "python": "9.298949123440735e-12", "path": "segments/5/mdot/11", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.28959020804484e-12", "python": "9.299056885963438e-12", "path": "segments/5/mdot/12", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289708365885489e-12", "python": "9.299175119049716e-12", "path": "segments/5/mdot/13", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289838004415693e-12", "python": "9.299304840136007e-12", "path": "segments/5/mdot/14", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.289980239243753e-12", "python": "9.299447165540839e-12", "path": "segments/5/mdot/15", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.290136294404574e-12", "python": "9.299603320078339e-12", "path": "segments/5/mdot/16", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.290307512901776e-12", "python": "9.299774647607051e-12", "path": "segments/5/mdot/17", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.290495368275647e-12", "python": "9.299962622605244e-12", "path": "segments/5/mdot/18", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.290701477296896e-12", "python": "9.300168862872709e-12", "path": "segments/5/mdot/19", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.290927613895995e-12", "python": "9.300395143468979e-12", "path": "segments/5/mdot/20", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.29117572444859e-12", "python": "9.300643412008432e-12", "path": "segments/5/mdot/21", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.291447944549353e-12", "python": "9.300915805444797e-12", "path": "segments/5/mdot/22", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.291746617419496e-12", "python": "9.30121466849034e-12", "path": "segments/5/mdot/23", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.292074314107531e-12", "python": "9.301542573829508e-12", "path": "segments/5/mdot/24", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`
* `{"vector": "P42-PROD-03", "entry": "plenum.transient_run", "observable": "segments/[]/mdot/[]", "rust": "9.29243385565847e-12", "python": "9.301902344302279e-12", "path": "segments/5/mdot/25", "tolerance": {"rel": 0.001, "abs": 0.0}, "class": "SOLVER_TOLERANCE"}`

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring
* entry indices: the contract registers vector counts per P-number; the function assigned to each index is fixed in the harness docstring (written before the scoring run); P40 (synthetic-segment metrics) is not named in any float group of the contract and takes the strictest closed-form class (k_ulp 4 / r_rel 1e-12)
* harness instrumentation: TransientRun._segment_record is wrapped in the harness process to record u_cmd at the segment end and the samples (threshold-proximity rule); the record it returns is unchanged and no reference file is modified. The Rust transient_run request returns the same u_cmd as '_ucmd_end' (reported, not scored)
* the Rust steady_sweep request also returns the scalar twin of every point ('_scalar', stripped before the comparison) for INV-P-02
* nfev and mass_residual_rel of the transients, iterations of the reservoir fixed point and every conservation_residual_rel leaf are reported, not scored (registered); CONS-P-02 / -03 gate them
* pre-scoring disclosure (written before this scoring run, from development-seed comparisons only): every development difference was in the transient entries (P42 / P43) and was classified CONTRACT_DEFECT, not RUST_DEFECT: (i) mdot samples are registered with a relative tolerance only, but mdot is linear in the valve opening u, which is registered with an absolute tolerance; where the valve is (nearly) closed (|u| within 10 x its tolerance) the relative mdot difference is unbounded (all development mdot differences were there); (ii) xO is NaN in the reference where the integrator's u noise around 0 is negative, so the None-ness of xO at a closed valve is the sign of rounding noise (all development xO differences were there); (iii) the cascade diagnostics of a transient segment (K_min, p_stage_max_Pa, P_el_max_W, T_comp_max_K) on trajectories outside the Gaede domain evaluate K0 - (K0 - 1) x with K0 up to 1e20, i.e. rounding noise of size ulp(K0) in the reference itself; (iv) final_setpoint_error_frac is a small difference quantity whose registered absolute floor (1e-6) is below the production integrator tolerance (rtol 1e-5); (v) with 17 transient_case vectors one isolated settling-index coincidence exceeds the 1 % proximity limit. Trajectories p, u and t agreed within their registered tolerances in both the production and the reference-tolerance sets. PROGRAMME.md sec. 7 rule 11: a contract defect needs a new contract version and is never resolved by changing a tolerance; the re-specification of these transient observables is an owner / coordinator decision (reported as a blocker)

## Ledger update requested

* C-ABEP_SIM_DESIGN_PLENUM_FEED_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_RESERVOIR_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
