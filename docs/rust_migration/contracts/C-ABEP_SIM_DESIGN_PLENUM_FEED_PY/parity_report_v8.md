# Parity report v8 - PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V8

Verdict: **PARITY_FAIL** (NOT_ADMITTED). Generated from the JSON report next to this file.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v8.json` sha256 `05192a43d1b5dadff79a0f82ebdf1fee71900a88820ec15a9d82a49eefad973b`, registered in `8943d26bde9a`.
* Python reference commit `0d8922cfe39b`; Rust commit `7262ad274a36`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905373 (scoring); 4040 vectors; 17 per-test failures.

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
| plenum.filter_case | 114 | 23 | 23 | 0 |
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
| plenum.transient_run | 32 | 4 | 4 | 0 |
| plenum.transient_case | 32 | 0 | 0 | 0 |
| plenum.event_sequence | 2 | 0 | 0 | 0 |
| plenum.orbit_qs | 10 | 0 | 0 | 0 |
| plenum.orbit_sim | 13 | 1 | 1 | 0 |
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
| upstream.classify | 30 | 3 | 3 | 0 |
| upstream.combine | 30 | 4 | 4 | 0 |
| upstream.constraint | 30 | 0 | 0 | 0 |
| upstream.control | 55 | 3 | 3 | 0 |
| upstream.setpoint | 415 | 26 | 26 | 0 |
| upstream.controller_view | 5 | 3 | 3 | 0 |
| upstream.schedule_input | 40 | 23 | 23 | 0 |
| upstream.h1_tolerance | 48 | 15 | 15 | 0 |
| upstream.governing_band | 40 | 2 | 2 | 0 |
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
| plenum.stability_class | 77 | 0 | 0 | 0 |
| plenum.stability_spectrum | 32 | 0 | 0 | 0 |
| plenum.transient_run_assessed | 32 | 0 | 4 | 0 |
| plenum.transient_case_assessed | 32 | 0 | 0 | 0 |
| plenum.orbit_sim_assessed | 13 | 0 | 1 | 0 |

## Float observables (non-bit-identical leaves only; every scored leaf is in the JSON report)

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| plenum.steady | a_eq_m2 | ULP_BOUNDED | 375 | 0 | 363 | 2.22e-16 | 2.06e-16 | 1 |
| plenum.steady | bisection_residual_rel | ULP_BOUNDED | 375 | 0 | 369 | 2.22e-16 | 1 | 4.49e+307 |
| plenum.steady | domain_diagnostics/feed_Kn_upper_O_omitted | ULP_BOUNDED | 315 | 0 | 310 | 2.27e-13 | 2.56e-16 | 2 |
| plenum.steady | offered/mdot_s_kgps/<s> | ULP_BOUNDED | 96 | 0 | 91 | 1.32e-23 | 2.61e-16 | 2 |
| plenum.steady | offered/mdot_total_kgps | ULP_BOUNDED | 32 | 0 | 31 | 2.58e-26 | 1.42e-16 | 1 |
| plenum.steady | offered/P_Pa | ULP_BOUNDED | 28 | 0 | 27 | 1.08e-19 | 1.43e-16 | 1 |
| plenum.steady | offered/p_s_Pa/<s> | ULP_BOUNDED | 96 | 0 | 92 | 1.08e-19 | 1.8e-16 | 1 |
| plenum.steady | offered/x_s_flow_mole/<s> | ULP_BOUNDED | 96 | 0 | 93 | 1.11e-16 | 1.54e-16 | 1 |
| plenum.steady | offered/w_s_flow_mass/<s> | ULP_BOUNDED | 96 | 0 | 92 | 1.11e-16 | 2.49e-16 | 2 |
| plenum.steady | offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 96 | 0 | 95 | 3.47e-18 | 1.22e-16 | 1 |
| plenum.steady | mdot_compressor_backleak_kgps/<s> | ULP_BOUNDED | 96 | 0 | 95 | 2.02e-28 | 3.29e-16 | 2 |
| plenum.steady | mdot_plenum_leak_kgps/<s> | ULP_BOUNDED | 96 | 0 | 92 | 5.05e-29 | 2.31e-16 | 2 |
| plenum.steady | feed/a_eq_m2 | ULP_BOUNDED | 32 | 0 | 29 | 3.47e-18 | 1.51e-16 | 1 |
| plenum.steady | feed/d_eq_m | ULP_BOUNDED | 32 | 0 | 31 | 2.78e-17 | 1.4e-16 | 1 |
| plenum.steady | feed/Kn_upper_O_omitted | ULP_BOUNDED | 32 | 0 | 31 | 5.68e-14 | 1.39e-16 | 1 |
| plenum.steady | feed/lambda_upper_m | ULP_BOUNDED | 32 | 0 | 31 | 1.78e-15 | 1.44e-16 | 1 |
| plenum.evaluate | a_eq_m2 | ULP_BOUNDED | 74 | 0 | 70 | 2.71e-20 | 2.08e-16 | 1 |
| plenum.evaluate | bisection_residual_rel | ULP_BOUNDED | 74 | 0 | 72 | 2.22e-16 | 1 | 4.5e+15 |
| plenum.evaluate | domain_diagnostics/feed_Kn_upper_O_omitted | ULP_BOUNDED | 57 | 0 | 54 | 4.55e-13 | 2.86e-16 | 2 |
| plenum.evaluate | offered/mdot_s_kgps/<s> | ULP_BOUNDED | 36 | 0 | 34 | 1.03e-25 | 2.83e-16 | 2 |
| plenum.evaluate | offered/P_Pa | ULP_BOUNDED | 9 | 0 | 8 | 8.67e-19 | 1.89e-16 | 1 |
| plenum.evaluate | offered/p_s_Pa/<s> | ULP_BOUNDED | 36 | 0 | 34 | 8.67e-19 | 2.25e-16 | 2 |
| plenum.evaluate | offered/x_s_flow_mole/<s> | ULP_BOUNDED | 36 | 0 | 34 | 5.55e-17 | 4.63e-16 | 3 |
| plenum.evaluate | offered/w_s_flow_mass/<s> | ULP_BOUNDED | 36 | 0 | 34 | 1.11e-16 | 2.75e-16 | 2 |
| plenum.evaluate | offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 36 | 0 | 34 | 1.11e-16 | 2.06e-16 | 1 |
| plenum.evaluate | mdot_compressor_backleak_kgps/<s> | ULP_BOUNDED | 36 | 0 | 35 | 2.02e-28 | 1.32e-16 | 1 |
| plenum.evaluate | mdot_plenum_leak_kgps/<s> | ULP_BOUNDED | 36 | 0 | 34 | 5.05e-29 | 2.64e-16 | 2 |
| plenum.evaluate | feed/a_eq_m2 | ULP_BOUNDED | 12 | 0 | 11 | 2.71e-20 | 1.72e-16 | 1 |
| plenum.evaluate | feed/Kn_upper_O_omitted | ULP_BOUNDED | 12 | 0 | 11 | 1.42e-14 | 1.15e-16 | 1 |
| plenum.evaluate | feed/lambda_upper_m | ULP_BOUNDED | 12 | 0 | 11 | 2.22e-16 | 1.27e-16 | 1 |
| plenum.sweep | sweep/mdot_total_kgps/[]/[] | ULP_BOUNDED | 1920 | 0 | 1910 | 5.29e-23 | 5.9e-16 | 4 |
| plenum.sweep | sweep/mdot_s_kgps/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5729 | 2.65e-23 | 3.85e-16 | 3 |
| plenum.sweep | sweep/x_s_flow_mole/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5739 | 1.11e-16 | 3.65e-16 | 2 |
| plenum.sweep | sweep/a_eq_m2/[]/[] | ULP_BOUNDED | 1920 | 0 | 1904 | 2.43e-17 | 1.75e-15 | 9 |
| plenum.sweep | sweep/bisection_residual_rel/[]/[] | ULP_BOUNDED | 1920 | 0 | 1913 | 3.33e-16 | 1 | 6.74e+307 |
| plenum.sweep | sweep/Kn_upper/[]/[] | ULP_BOUNDED | 1920 | 0 | 1914 | 5.68e-14 | 6.53e-16 | 4 |
| plenum.area_for_pressure | a_eq | ULP_BOUNDED | 80 | 0 | 76 | 6.94e-18 | 1.5e-16 | 1 |
| plenum.area_for_pressure | resid | ULP_BOUNDED | 80 | 0 | 77 | 4.44e-16 | 1 | 4.5e+15 |
| plenum.segment_metrics | valve_travel | ULP_BOUNDED | 150 | 0 | 121 | 1.78e-15 | 3.94e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_P | ULP_BOUNDED | 27 | 0 | 11 | 1.11e-16 | 4.26e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_mdot | ULP_BOUNDED | 27 | 0 | 17 | 5.55e-17 | 2.41e-16 | 2 |
| plenum.transient_run | segments/[]/t/[] | ULP_BOUNDED | 19328 | 0 | 18240 | 3.55e-15 | 2.09e-16 | 1 |
| plenum.transient_run | segments/[]/p/[] | CONVERGENCE_ENVELOPE | 19328 | 0 | 1838 | 2.37e-07 | 9.48e-06 | 5.63e+10 |
| plenum.transient_run | segments/[]/mdot/[] | CONVERGENCE_ENVELOPE | 19328 | 0 | 1408 | 2.23e-12 | 3.48e-05 | 2.69e+11 |
| plenum.transient_run | segments/[]/u/[] | CONVERGENCE_ENVELOPE | 19328 | 0 | 1376 | 1.26e-05 | 3.55e-05 | 2.27e+11 |
| plenum.transient_run | segments/[]/xO/[] | CONVERGENCE_ENVELOPE | 19328 | 0 | 1513 | 2.83e-06 | 1.47e-05 | 8.03e+10 |
| plenum.transient_run | segments/[]/p_inlet_max_Pa | CONVERGENCE_ENVELOPE | 128 | 0 | 20 | 5.67e-10 | 1.47e-07 | 1.31e+09 |
| plenum.transient_run | throughput_kg | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 7.27e-17 | 8.6e-13 | 5.36e+03 |
| plenum.transient_case | metrics/[]/P_final_Pa | CONVERGENCE_ENVELOPE | 128 | 2 | 9 | 4.3e-07 | 4.34e-05 | 2.48e+11 |
| plenum.transient_case | metrics/[]/mdot_final_kgps | CONVERGENCE_ENVELOPE | 128 | 2 | 13 | 4.32e-14 | 0.999 | 8.54e+15 |
| plenum.transient_case | metrics/[]/P_min_Pa | CONVERGENCE_ENVELOPE | 128 | 1 | 15 | 6.15e-07 | 4.9e-05 | 2.77e+11 |
| plenum.transient_case | metrics/[]/P_max_Pa | CONVERGENCE_ENVELOPE | 128 | 1 | 7 | 5.03e-07 | 4.93e-05 | 2.9e+11 |
| plenum.transient_case | metrics/[]/mdot_min_kgps | CONVERGENCE_ENVELOPE | 128 | 1 | 5 | 1.24e-12 | 1 | 8.54e+15 |
| plenum.transient_case | metrics/[]/mdot_max_kgps | CONVERGENCE_ENVELOPE | 128 | 1 | 9 | 1.16e-12 | 0.000804 | 6.59e+12 |
| plenum.transient_case | metrics/[]/xO_min | CONVERGENCE_ENVELOPE | 128 | 0 | 3 | 3.27e-06 | 1.23e-05 | 8.24e+10 |
| plenum.transient_case | metrics/[]/xO_max | CONVERGENCE_ENVELOPE | 128 | 0 | 4 | 3.51e-06 | 1.23e-05 | 8.1e+10 |
| plenum.transient_case | metrics/[]/valve_travel | CONVERGENCE_ENVELOPE | 128 | 0 | 1 | 0.0118 | 4.6 | 2.59e+16 |
| plenum.transient_case | metrics/[]/u_min | CONVERGENCE_ENVELOPE | 128 | 1 | 8 | 0.000438 | 1 | 5.95e+15 |
| plenum.transient_case | metrics/[]/u_max | CONVERGENCE_ENVELOPE | 128 | 1 | 10 | 0.00043 | 0.000835 | 5.44e+12 |
| plenum.transient_case | metrics/[]/final_setpoint_error_frac | CONVERGENCE_ENVELOPE | 128 | 2 | 9 | 4.3e-05 | 4 | 3.51e+307 |
| plenum.transient_case | metrics/[]/settling_time_s | ULP_BOUNDED | 125 | 0 | 124 | 5.55e-17 | 1.83e-16 | 1 |
| plenum.transient_case | metrics/[]/flow_recovery_s | ULP_BOUNDED | 128 | 0 | 126 | 3.55e-15 | 1.8e-16 | 1 |
| plenum.transient_case | metrics/[]/peak_deviation_frac | CONVERGENCE_ENVELOPE | 96 | 1 | 7 | 5.03e-05 | 1 | 8.6e+15 |
| plenum.transient_case | metrics/[]/overshoot_frac | CONVERGENCE_ENVELOPE | 32 | 1 | 3 | 0.000498 | 1 | 7.38e+15 |
| plenum.transient_case | summary/P_min_Pa | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 6.15e-07 | 1.87e-05 | 1.01e+11 |
| plenum.transient_case | summary/P_max_Pa | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 1.85e-07 | 7.44e-06 | 4.83e+10 |
| plenum.transient_case | summary/mdot_min_kgps | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 3.48e-17 | 1 | 5.61e+15 |
| plenum.transient_case | summary/mdot_max_kgps | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 1.73e-14 | 0.000191 | 1.34e+12 |
| plenum.transient_case | summary/xO_flow_min | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 1.39e-06 | 7.73e-06 | 5.16e+10 |
| plenum.transient_case | summary/xO_flow_max | CONVERGENCE_ENVELOPE | 16 | 0 | 0 | 5.62e-07 | 1.23e-05 | 8.1e+10 |
| plenum.transient_case | summary/overshoot_max | CONVERGENCE_ENVELOPE | 16 | 1 | 1 | 0.000498 | 1 | 7.38e+15 |
| plenum.transient_case | summary/a_eq_design_m2 | ULP_BOUNDED | 16 | 0 | 14 | 3.47e-18 | 1.22e-16 | 1 |
| plenum.transient_case | summary/a_eq_max_m2 | ULP_BOUNDED | 16 | 0 | 14 | 1.39e-17 | 1.72e-16 | 1 |
| plenum.transient_case | summary/plenum_tau_s/[] | ULP_BOUNDED | 32 | 0 | 31 | 2.78e-17 | 1.57e-16 | 1 |
| plenum.transient_case | objectives/valve_travel | CONVERGENCE_ENVELOPE | 16 | 1 | 0 | 0.0545 | 0.00157 | 7.67e+12 |
| plenum.transient_case | objectives/peak_deviation_max | CONVERGENCE_ENVELOPE | 16 | 1 | 0 | 5.03e-05 | 0.00244 | 1.45e+13 |
| plenum.orbit_qs | rows/[]/ripple_pp_frac_mdot | ULP_BOUNDED | 3 | 0 | 1 | 2.78e-17 | 1.67e-16 | 1 |
| plenum.orbit_sim | P_dev_max_frac | CONVERGENCE_ENVELOPE | 4 | 0 | 0 | 5.06e-07 | 0.0432 | 2.99e+14 |
| plenum.orbit_sim | mdot_min_kgps | CONVERGENCE_ENVELOPE | 4 | 0 | 0 | 1.47e-13 | 4.88e-07 | 2.49e+09 |
| plenum.orbit_sim | mdot_max_kgps | CONVERGENCE_ENVELOPE | 4 | 0 | 0 | 5.06e-14 | 8.73e-07 | 5.16e+09 |
| plenum.scheduled | rows/[]/a_eq_m2 | ULP_BOUNDED | 66 | 0 | 63 | 8.67e-19 | 1.8e-16 | 1 |
| plenum.scheduled | rows/[]/offered/P_Pa | ULP_BOUNDED | 12 | 0 | 11 | 3.47e-18 | 1.14e-16 | 1 |
| plenum.scheduled | rows/[]/offered/p_s_Pa/<s> | ULP_BOUNDED | 42 | 0 | 40 | 3.47e-18 | 2.17e-16 | 1 |
| plenum.scheduled | rows/[]/offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 42 | 0 | 41 | 2.78e-17 | 1.14e-16 | 1 |
| plenum.compare_modes | fallback_reference/rows/[]/a_eq_m2 | ULP_BOUNDED | 28 | 0 | 27 | 8.47e-22 | 1.48e-16 | 1 |
| plenum.stability_spectrum | equilibria/[]/jacobian/[]/[] | ULP_BOUNDED | 9325 | 0 | 9218 | 1.78e-15 | 3.91e-16 | 3 |
| plenum.stability_spectrum | equilibria/[]/re_lead | CONVERGENCE_ENVELOPE | 373 | 0 | 10 | 1.36e-14 | 5.09e-12 | 3.35e+04 |
| plenum.stability_spectrum | equilibria/[]/im_lead | CONVERGENCE_ENVELOPE | 373 | 0 | 31 | 1.87e-14 | 5.03e-15 | 44 |

Scored float leaves: 199118 (123951 bit-identical); EXACT_VALUE leaves: 71445.

Reported, not scored:

* plenum.steady conservation_residual_rel: n 32, max abs diff 0, max rel diff 0
* plenum.evaluate conservation_residual_rel: n 12, max abs diff 0, max rel diff 0
* plenum.transient_run segments/[]/K_min: n 128, max abs diff 8.33e+38, max rel diff 59.8
* plenum.transient_run segments/[]/K_over_K0_max: n 128, max abs diff 0.000151, max rel diff 0.000151
* plenum.transient_run segments/[]/p_stage_max_Pa: n 128, max abs diff 5.11e+61, max rel diff 1
* plenum.transient_run segments/[]/P_el_max_W: n 128, max abs diff 6.87e+60, max rel diff 1.92
* plenum.transient_run segments/[]/T_comp_max_K: n 128, max abs diff 1.72e+61, max rel diff 1.76
* plenum.transient_run segments/[]/_ucmd_end: n 128, max abs diff 1.07e-06, max rel diff 3.58e-06
* plenum.transient_run mass_residual_rel: n 16, max abs diff 3.29e-16, max rel diff 7.08
* plenum.transient_run nfev: n 16, max abs diff 3.22e+04, max rel diff 12.9
* plenum.transient_case summary/mass_residual_rel: n 16, max abs diff 2.24e-16, max rel diff 4.1e+03
* plenum.transient_case summary/nfev: n 16, max abs diff 5.43e+04, max rel diff 12.8
* plenum.orbit_sim mass_residual_rel: n 4, max abs diff 3.19e-16, max rel diff 0.674
* plenum.orbit_sim nfev: n 4, max abs diff 3.11e+03, max rel diff 19.2
* reservoir.steady iterations: n 300, max abs diff 0, max rel diff 0
* plenum.stability_class events/[]/re_max: n 725, max abs diff 5.08e-13, max rel diff 5.09e-12

## Domain / error parity

172 vectors with a refusal on either side, 0 mismatches.

| entry | Python | Rust | n |
|---|---|---|---|
| plenum.area_for_pressure | ValueError | ValueError | 3 |
| plenum.compare_modes | ValueError | ValueError | 1 |
| plenum.filter_case | FilterStageError | FilterStageError | 23 |
| plenum.orbit_sim | ValueError | ValueError | 1 |
| plenum.plenum | ValueError | ValueError | 8 |
| plenum.scheduled | ValueError | ValueError | 2 |
| plenum.steady | ZeroDivisionError | ZeroDivisionError | 10 |
| plenum.transient_run | ValueError | ValueError | 4 |
| reservoir.steady | KeyError | KeyError | 1 |
| upstream.candidate | A913RuleError | A913RuleError | 2 |
| upstream.classify | A913RuleError | A913RuleError | 3 |
| upstream.combine | A913RuleError | A913RuleError | 4 |
| upstream.control | A913RuleError | A913RuleError | 3 |
| upstream.controller_view | A913RuleError | A913RuleError | 3 |
| upstream.fixed_gate | A913RuleError | A913RuleError | 2 |
| upstream.governing_band | A913RuleError | A913RuleError | 2 |
| upstream.h1_tolerance | A913RuleError | A913RuleError | 15 |
| upstream.lowering | A913RuleError | A913RuleError | 18 |
| upstream.robust_set | A913RuleError | A913RuleError | 13 |
| upstream.robust_set | RepresentativeSelectionRefused | RepresentativeSelectionRefused | 4 |
| upstream.schedule_input | A913RuleError | A913RuleError | 23 |
| upstream.setpoint | A913RuleError | A913RuleError | 26 |
| upstream.state_coverage | A913RuleError | A913RuleError | 1 |

## Threshold proximity

0 vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % limit: none.

## Invariants and conservation

* Rust two processes byte-identical: True (stdout sha256 `725b8c082d240429...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-P-02: {"n": 1920, "n_fail": 0, "failures": [], "ok": true}
* INV-P-04: {"ok": true}
* CONS-P-01: {"n": 44, "n_fail": 0, "ok": true, "max_residual_over_floor": 2.0588711355873368e-16}
* CONS-P-02: {"n": 44, "n_fail": 0, "ok": true, "max_residual_rel": 1.7114116380621011e-12}
* CONS-P-03: {"n": 68, "n_fail": 0, "ok": true, "python_recorded": {"n": 68, "n_fail": 0, "max_mass_residual_rel": 1.6733088246593945e-13}, "max_mass_residual_rel": 5.1108253569171696e-14}
* CONS-P-04: {"n": 300, "n_fail": 0, "ok": true, "max_balance_residual_rel": 2.0800914859557812e-16}

## Contract v8: strata, class, leading eigenvalues, reported time-domain outputs

* Strata: {"P42/PROD/S": 12, "P42/PROD/R": 3, "P42/PROD/U": 8, "P42/REF/S": 4, "P42/REF/R": 1, "P42/REF/U": 4, "P43/PROD/S": 12, "P43/PROD/R": 3, "P43/PROD/U": 8, "P43/REF/S": 4, "P43/REF/R": 1, "P43/REF/U": 4, "P45/PROD/S": 4, "P45/PROD/R": 1, "P45/PROD/U": 8}.
* Stability class (both implementations; a disagreement is a scored failure): 77 vectors, 0 disagreements.
* Leading eigenvalues (U stratum): 32 vectors, 373 UNSAT equilibria, NOT_CONVERGENT 0, im_lead {"SCORED": 373, "LEADING_MODE_REAL": 0, "LEADING_MODE_AMBIGUOUS": 0}; largest used fraction of the bound {"re_lead": 0.004798260204935712, "im_lead": 5.022587428537749e-06}; largest own eigen-solver error over the frozen envelope {"python": {"re_lead": 0.8515009967415672, "im_lead": 0.9196764663326711}, "rust": {"re_lead": 0.9309118909515497, "im_lead": 1.1968073512815691}}.
* Stable-stratum reuse check: {"ok": true, "v7_record_sha256": "e4774be4927aebe91c4cf1692405f3c463e1d4de21fc62f406fe075d69c9855f", "registered_sha256": "e4774be4927aebe91c4cf1692405f3c463e1d4de21fc62f406fe075d69c9855f", "copied_values_equal": true}.
* Non-vacuity (frozen record): True.
* Excused xO None-ness samples (counted once per vector and segment; each passed the |u| test): 0 (all listed in the JSON report).
* Reported, not scored: {}.

Unstable stratum time-domain outputs (REPORTED, ILL_POSED_UNSTABLE_EQUILIBRIUM, never scored); spreads in family units:

| vector | max Re lambda | family | leaves | cross-level python | cross-level rust | cross-implementation |
|---|---|---|---|---|---|---|
| P42-PROD-U-000 | 0.0225 | F42.p | 1208 | 0.000142 | 1.35e-05 | 0.000128 |
| P42-PROD-U-000 | 0.0225 | F42.mdot | 1208 | 0.00134 | 0.000122 | 0.00122 |
| P42-PROD-U-000 | 0.0225 | F42.u | 1208 | 0.000464 | 4.24e-05 | 0.000422 |
| P42-PROD-U-000 | 0.0225 | F42.xO | 1208 | 1.02e-05 | 9.83e-07 | 9.2e-06 |
| P42-PROD-U-000 | 0.0225 | F42.ucmd_end | 8 | 0.000368 | 3.4e-05 | 0.000334 |
| P42-PROD-U-000 | 0.0225 | F42.throughput | 1 | 1.05e-11 | 1.56e-12 | 1.19e-11 |
| P42-PROD-U-001 | 0.467 | F42.p | 1208 | 0.000318 | 3.5e-06 | 0.000322 |
| P42-PROD-U-001 | 0.467 | F42.mdot | 1208 | 0.00106 | 1.19e-05 | 0.00107 |
| P42-PROD-U-001 | 0.467 | F42.u | 1208 | 0.000363 | 4.03e-06 | 0.000367 |
| P42-PROD-U-001 | 0.467 | F42.xO | 1208 | 3.44e-06 | 3.76e-08 | 3.48e-06 |
| P42-PROD-U-001 | 0.467 | F42.ucmd_end | 8 | 0.00177 | 2.01e-05 | 0.00179 |
| P42-PROD-U-001 | 0.467 | F42.throughput | 1 | 2.39e-11 | 6.37e-14 | 2.38e-11 |
| P42-PROD-U-002 | 0.099 | F42.p | 1208 | 0.000341 | 2.47e-05 | 0.000316 |
| P42-PROD-U-002 | 0.099 | F42.mdot | 1208 | 0.00246 | 0.000178 | 0.00228 |
| P42-PROD-U-002 | 0.099 | F42.u | 1208 | 0.000929 | 6.75e-05 | 0.000861 |
| P42-PROD-U-002 | 0.099 | F42.xO | 1208 | 2.47e-05 | 1.77e-06 | 2.3e-05 |
| P42-PROD-U-002 | 0.099 | F42.ucmd_end | 8 | 0.00126 | 9.38e-05 | 0.00117 |
| P42-PROD-U-002 | 0.099 | F42.throughput | 1 | 3.98e-11 | 2.01e-12 | 3.78e-11 |
| P42-PROD-U-003 | 0.0389 | F42.p | 1208 | 0.000254 | 3.63e-05 | 0.000218 |
| P42-PROD-U-003 | 0.0389 | F42.mdot | 1208 | 0.00728 | 0.00105 | 0.00623 |
| P42-PROD-U-003 | 0.0389 | F42.u | 1208 | 0.00271 | 0.000387 | 0.00232 |
| P42-PROD-U-003 | 0.0389 | F42.xO | 1208 | 1.85e-05 | 2.63e-06 | 1.59e-05 |
| P42-PROD-U-003 | 0.0389 | F42.ucmd_end | 8 | 0.00247 | 0.00035 | 0.00212 |
| P42-PROD-U-003 | 0.0389 | F42.throughput | 1 | 2e-10 | 2.77e-11 | 1.72e-10 |
| P42-PROD-U-004 | 0.00508 | F42.p | 1208 | 3.07e-05 | 1.17e-06 | 2.96e-05 |
| P42-PROD-U-004 | 0.00508 | F42.mdot | 1208 | 0.000351 | 1.89e-05 | 0.000345 |
| P42-PROD-U-004 | 0.00508 | F42.u | 1208 | 0.000208 | 1.05e-05 | 0.000203 |
| P42-PROD-U-004 | 0.00508 | F42.xO | 1208 | 1.09e-08 | 4.15e-10 | 1.05e-08 |
| P42-PROD-U-004 | 0.00508 | F42.ucmd_end | 8 | 9.53e-05 | 9.02e-06 | 8.63e-05 |
| P42-PROD-U-004 | 0.00508 | F42.throughput | 1 | 6.22e-12 | 5.88e-14 | 6.17e-12 |
| P42-PROD-U-005 | 0.284 | F42.p | 1208 | 0.000187 | 1.33e-06 | 0.000186 |
| P42-PROD-U-005 | 0.284 | F42.mdot | 1208 | 0.00253 | 1.84e-05 | 0.00251 |
| P42-PROD-U-005 | 0.284 | F42.u | 1208 | 0.000783 | 5.72e-06 | 0.000777 |
| P42-PROD-U-005 | 0.284 | F42.xO | 1208 | 5.61e-08 | 4.05e-10 | 5.57e-08 |
| P42-PROD-U-005 | 0.284 | F42.ucmd_end | 8 | 0.00116 | 8.81e-06 | 0.00115 |
| P42-PROD-U-005 | 0.284 | F42.throughput | 1 | 3.33e-11 | 3.26e-13 | 3.29e-11 |
| P42-PROD-U-006 | 0.313 | F42.p | 1208 | 0.00476 | 0.00129 | 0.00603 |
| P42-PROD-U-006 | 0.313 | F42.mdot | 1208 | 0.00651 | 0.00176 | 0.00825 |
| P42-PROD-U-006 | 0.313 | F42.u | 1208 | 0.00329 | 0.000888 | 0.00417 |
| P42-PROD-U-006 | 0.313 | F42.xO | 1208 | 1.28e-05 | 3.45e-06 | 1.62e-05 |
| P42-PROD-U-006 | 0.313 | F42.ucmd_end | 8 | 0.00689 | 0.00188 | 0.00875 |
| P42-PROD-U-006 | 0.313 | F42.throughput | 1 | 2.69e-10 | 2.33e-10 | 3.62e-11 |
| P42-PROD-U-007 | 0.226 | F42.p | 1208 | 0.000314 | 1.11e-06 | 0.000313 |
| P42-PROD-U-007 | 0.226 | F42.mdot | 1208 | 0.00415 | 1.1e-05 | 0.00414 |
| P42-PROD-U-007 | 0.226 | F42.u | 1208 | 0.00116 | 3.21e-06 | 0.00116 |
| P42-PROD-U-007 | 0.226 | F42.xO | 1208 | 4.37e-07 | 1.44e-09 | 4.36e-07 |
| P42-PROD-U-007 | 0.226 | F42.ucmd_end | 8 | 0.00147 | 2.48e-06 | 0.00147 |
| P42-PROD-U-007 | 0.226 | F42.throughput | 1 | 9.02e-11 | 3.08e-12 | 9.33e-11 |
| P42-REF-U-000 | 0.0118 | F42.p | 1208 | 7.15e-07 | 3.33e-08 | 6.96e-07 |
| P42-REF-U-000 | 0.0118 | F42.mdot | 1208 | 3.84e-06 | 1.55e-07 | 3.73e-06 |
| P42-REF-U-000 | 0.0118 | F42.u | 1208 | 1.15e-06 | 4.64e-08 | 1.11e-06 |
| P42-REF-U-000 | 0.0118 | F42.xO | 1208 | 5e-08 | 2.06e-09 | 4.86e-08 |
| P42-REF-U-000 | 0.0118 | F42.ucmd_end | 8 | 1.46e-06 | 6.83e-08 | 1.4e-06 |
| P42-REF-U-000 | 0.0118 | F42.throughput | 1 | 3.31e-12 | 6.9e-14 | 3.27e-12 |
| P42-REF-U-001 | 0.33 | F42.p | 1208 | 8.49e-07 | 1.38e-08 | 7.01e-07 |
| P42-REF-U-001 | 0.33 | F42.mdot | 1208 | 5.26e-06 | 8.62e-08 | 4.32e-06 |
| P42-REF-U-001 | 0.33 | F42.u | 1208 | 2.27e-06 | 3.73e-08 | 1.87e-06 |
| P42-REF-U-001 | 0.33 | F42.xO | 1208 | 4.25e-09 | 6.88e-11 | 3.51e-09 |
| P42-REF-U-001 | 0.33 | F42.ucmd_end | 8 | 4.15e-06 | 7.38e-08 | 3.35e-06 |
| P42-REF-U-001 | 0.33 | F42.throughput | 1 | 8.73e-14 | 2.39e-15 | 8.81e-14 |
| P42-REF-U-002 | 0.214 | F42.p | 1208 | 1.21e-06 | 4.25e-09 | 1.27e-06 |
| P42-REF-U-002 | 0.214 | F42.mdot | 1208 | 7.01e-06 | 2.55e-08 | 7.35e-06 |
| P42-REF-U-002 | 0.214 | F42.u | 1208 | 3.31e-06 | 1.23e-08 | 3.47e-06 |
| P42-REF-U-002 | 0.214 | F42.xO | 1208 | 8.45e-08 | 2.91e-10 | 8.87e-08 |
| P42-REF-U-002 | 0.214 | F42.ucmd_end | 8 | 9.68e-06 | 3.69e-08 | 1.02e-05 |
| P42-REF-U-002 | 0.214 | F42.throughput | 1 | 1.09e-13 | 1.54e-15 | 1.05e-13 |
| P42-REF-U-003 | 0.901 | F42.p | 1208 | 2.56e-06 | 6.36e-08 | 2.32e-06 |
| P42-REF-U-003 | 0.901 | F42.mdot | 1208 | 1.12e-05 | 2.8e-07 | 1.01e-05 |
| P42-REF-U-003 | 0.901 | F42.u | 1208 | 3.35e-06 | 8.49e-08 | 3e-06 |
| P42-REF-U-003 | 0.901 | F42.xO | 1208 | 1.74e-07 | 4.23e-09 | 1.58e-07 |
| P42-REF-U-003 | 0.901 | F42.ucmd_end | 8 | 2.34e-05 | 5.46e-07 | 2.12e-05 |
| P42-REF-U-003 | 0.901 | F42.throughput | 1 | 6.65e-15 | 2.09e-15 | 1.77e-14 |
| P43-PROD-U-000 | 0.0241 | F43.p | 26 | 0.000102 | 1.71e-05 | 9.21e-05 |
| P43-PROD-U-000 | 0.0241 | F43.mdot | 26 | 0.000281 | 3.21e-05 | 0.000249 |
| P43-PROD-U-000 | 0.0241 | F43.xO | 18 | 1.49e-07 | 2.41e-08 | 1.33e-07 |
| P43-PROD-U-000 | 0.0241 | F43.valve_travel | 8 | 0.00285 | 0.000266 | 0.00259 |
| P43-PROD-U-000 | 0.0241 | F43.u | 16 | 0.000114 | 1.18e-05 | 0.000102 |
| P43-PROD-U-000 | 0.0241 | F43.setpoint_frac | 15 | 0.000102 | 1.71e-05 | 9.21e-05 |
| P43-PROD-U-000 | 0.0241 | F43.overshoot | 3 | 0.26 | 0.0572 | 0.203 |
| P43-PROD-U-000 | 0.0241 | F43.valve_travel_total | 1 | 0.00262 | 4.71e-05 | 0.00267 |
| P43-PROD-U-001 | 0.46 | F43.p | 26 | 1.76e-05 | 1.66e-06 | 1.56e-05 |
| P43-PROD-U-001 | 0.46 | F43.mdot | 26 | 0.000176 | 1.48e-05 | 0.000167 |
| P43-PROD-U-001 | 0.46 | F43.xO | 18 | 2.57e-07 | 3.11e-08 | 2.19e-07 |
| P43-PROD-U-001 | 0.46 | F43.valve_travel | 8 | 0.000406 | 3.04e-05 | 0.000369 |
| P43-PROD-U-001 | 0.46 | F43.u | 16 | 8.91e-06 | 9.25e-07 | 8.09e-06 |
| P43-PROD-U-001 | 0.46 | F43.setpoint_frac | 15 | 1.76e-05 | 1.66e-06 | 1.56e-05 |
| P43-PROD-U-001 | 0.46 | F43.overshoot | 3 | 2.86e-05 | 1.42e-06 | 2.9e-05 |
| P43-PROD-U-001 | 0.46 | F43.valve_travel_total | 1 | 0.000683 | 4.4e-05 | 0.000631 |
| P43-PROD-U-002 | 0.106 | F43.p | 26 | 9.32e-05 | 3.03e-05 | 6.84e-05 |
| P43-PROD-U-002 | 0.106 | F43.mdot | 26 | 0.00132 | 0.00065 | 0.000944 |
| P43-PROD-U-002 | 0.106 | F43.xO | 18 | 3.58e-06 | 1.82e-06 | 1.76e-06 |
| P43-PROD-U-002 | 0.106 | F43.valve_travel | 8 | 0.00226 | 0.000994 | 0.00203 |
| P43-PROD-U-002 | 0.106 | F43.u | 16 | 8.27e-05 | 3.09e-05 | 7.97e-05 |
| P43-PROD-U-002 | 0.106 | F43.setpoint_frac | 15 | 9.32e-05 | 3.03e-05 | 6.84e-05 |
| P43-PROD-U-002 | 0.106 | F43.overshoot | 3 | 0.00431 | 0.000238 | 0.00407 |
| P43-PROD-U-002 | 0.106 | F43.valve_travel_total | 1 | 0.00104 | 0.000304 | 0.000732 |
| P43-PROD-U-003 | 0.014 | F43.p | 26 | 4.35e-05 | 2.67e-06 | 4.08e-05 |
| P43-PROD-U-003 | 0.014 | F43.mdot | 26 | 0.000589 | 3.65e-05 | 0.000553 |
| P43-PROD-U-003 | 0.014 | F43.xO | 18 | 6.49e-09 | 4.8e-10 | 6.01e-09 |
| P43-PROD-U-003 | 0.014 | F43.valve_travel | 8 | 0.000602 | 4.15e-05 | 0.00056 |
| P43-PROD-U-003 | 0.014 | F43.u | 16 | 5.29e-05 | 5.07e-06 | 4.78e-05 |
| P43-PROD-U-003 | 0.014 | F43.setpoint_frac | 15 | 4.35e-05 | 2.67e-06 | 4.08e-05 |
| P43-PROD-U-003 | 0.014 | F43.overshoot | 3 | 0.000198 | 1.9e-05 | 0.000217 |
| P43-PROD-U-003 | 0.014 | F43.valve_travel_total | 1 | 0.000178 | 1.66e-05 | 0.000161 |
| P43-PROD-U-004 | 0.00294 | F43.p | 26 | 3.65e-05 | 4.73e-06 | 3.18e-05 |
| P43-PROD-U-004 | 0.00294 | F43.mdot | 26 | 0.00136 | 0.000178 | 0.00119 |
| P43-PROD-U-004 | 0.00294 | F43.xO | 18 | 3.56e-09 | 4.05e-10 | 3.16e-09 |
| P43-PROD-U-004 | 0.00294 | F43.valve_travel | 8 | 0.00409 | 0.00048 | 0.00361 |
| P43-PROD-U-004 | 0.00294 | F43.u | 16 | 0.000307 | 2.72e-05 | 0.00028 |
| P43-PROD-U-004 | 0.00294 | F43.setpoint_frac | 15 | 3.65e-05 | 4.73e-06 | 3.18e-05 |
| P43-PROD-U-004 | 0.00294 | F43.overshoot | 3 | 8.53e-06 | 1.31e-06 | 7.22e-06 |
| P43-PROD-U-004 | 0.00294 | F43.valve_travel_total | 1 | 0.0127 | 0.00124 | 0.0114 |
| P43-PROD-U-005 | 0.00323 | F43.p | 26 | 4.39e-05 | 4.34e-06 | 3.96e-05 |
| P43-PROD-U-005 | 0.00323 | F43.mdot | 26 | 0.000429 | 4.02e-05 | 0.000413 |
| P43-PROD-U-005 | 0.00323 | F43.xO | 18 | 1.68e-08 | 9.23e-10 | 1.62e-08 |
| P43-PROD-U-005 | 0.00323 | F43.valve_travel | 8 | 0.00204 | 6.01e-05 | 0.00202 |
| P43-PROD-U-005 | 0.00323 | F43.u | 16 | 0.0002 | 1.41e-05 | 0.000191 |
| P43-PROD-U-005 | 0.00323 | F43.setpoint_frac | 15 | 4.39e-05 | 4.34e-06 | 3.96e-05 |
| P43-PROD-U-005 | 0.00323 | F43.overshoot | 3 | 2.21e-05 | 2.34e-06 | 1.97e-05 |
| P43-PROD-U-005 | 0.00323 | F43.valve_travel_total | 1 | 0.00751 | 0.000156 | 0.00736 |
| P43-PROD-U-006 | 0.0163 | F43.p | 26 | 0.00016 | 2.17e-05 | 0.000138 |
| P43-PROD-U-006 | 0.0163 | F43.mdot | 26 | 0.00254 | 0.000348 | 0.0022 |
| P43-PROD-U-006 | 0.0163 | F43.xO | 18 | 2e-07 | 2.5e-08 | 1.75e-07 |
| P43-PROD-U-006 | 0.0163 | F43.valve_travel | 8 | 0.0149 | 0.00224 | 0.0127 |
| P43-PROD-U-006 | 0.0163 | F43.u | 16 | 0.000667 | 0.000132 | 0.000535 |
| P43-PROD-U-006 | 0.0163 | F43.setpoint_frac | 15 | 0.00016 | 2.17e-05 | 0.000138 |
| P43-PROD-U-006 | 0.0163 | F43.overshoot | 3 | 0.000309 | 0.000108 | 0.000415 |
| P43-PROD-U-006 | 0.0163 | F43.valve_travel_total | 1 | 0.0169 | 0.00344 | 0.0134 |
| P43-PROD-U-007 | 0.0323 | F43.p | 26 | 6.66e-05 | 1.02e-05 | 5.76e-05 |
| P43-PROD-U-007 | 0.0323 | F43.mdot | 26 | 0.000537 | 7.52e-05 | 0.000462 |
| P43-PROD-U-007 | 0.0323 | F43.xO | 18 | 9.75e-07 | 1.26e-07 | 9.63e-07 |
| P43-PROD-U-007 | 0.0323 | F43.valve_travel | 8 | 0.000427 | 7.47e-05 | 0.000374 |
| P43-PROD-U-007 | 0.0323 | F43.u | 16 | 3.57e-05 | 4.61e-06 | 3.25e-05 |
| P43-PROD-U-007 | 0.0323 | F43.setpoint_frac | 15 | 6.66e-05 | 1.02e-05 | 5.76e-05 |
| P43-PROD-U-007 | 0.0323 | F43.overshoot | 3 | 1.34e+04 | 1.2e+04 | 1.36e+03 |
| P43-PROD-U-007 | 0.0323 | F43.valve_travel_total | 1 | 0.000272 | 5.16e-05 | 0.000322 |
| P43-REF-U-000 | 0.333 | F43.p | 26 | 4.01e-06 | 2.08e-08 | 4.09e-06 |
| P43-REF-U-000 | 0.333 | F43.mdot | 26 | 1.96e-05 | 1.04e-07 | 2e-05 |
| P43-REF-U-000 | 0.333 | F43.xO | 18 | 1.47e-09 | 7.86e-12 | 1.5e-09 |
| P43-REF-U-000 | 0.333 | F43.valve_travel | 8 | 5.7e-05 | 2.89e-07 | 5.82e-05 |
| P43-REF-U-000 | 0.333 | F43.u | 16 | 1.57e-06 | 7.7e-09 | 1.6e-06 |
| P43-REF-U-000 | 0.333 | F43.setpoint_frac | 15 | 4.01e-06 | 2.08e-08 | 4.09e-06 |
| P43-REF-U-000 | 0.333 | F43.overshoot | 3 | 2.87e-06 | 1.79e-08 | 2.93e-06 |
| P43-REF-U-000 | 0.333 | F43.valve_travel_total | 1 | 5.03e-05 | 2.25e-07 | 5.13e-05 |
| P43-REF-U-001 | 0.0126 | F43.p | 26 | 9.76e-07 | 8.42e-09 | 9.93e-07 |
| P43-REF-U-001 | 0.0126 | F43.mdot | 26 | 3.15e-06 | 2.9e-08 | 3.2e-06 |
| P43-REF-U-001 | 0.0126 | F43.xO | 18 | 5.86e-08 | 2.63e-10 | 5.97e-08 |
| P43-REF-U-001 | 0.0126 | F43.valve_travel | 8 | 1.67e-05 | 6.53e-08 | 1.7e-05 |
| P43-REF-U-001 | 0.0126 | F43.u | 16 | 1.03e-06 | 7.57e-09 | 1.05e-06 |
| P43-REF-U-001 | 0.0126 | F43.setpoint_frac | 15 | 9.76e-07 | 7.65e-09 | 9.93e-07 |
| P43-REF-U-001 | 0.0126 | F43.overshoot | 3 | 2.35e-06 | 3.66e-08 | 2.37e-06 |
| P43-REF-U-001 | 0.0126 | F43.valve_travel_total | 1 | 3.26e-05 | 1.5e-08 | 3.33e-05 |
| P43-REF-U-002 | 0.114 | F43.p | 26 | 1.66e-06 | 6.79e-09 | 1.68e-06 |
| P43-REF-U-002 | 0.114 | F43.mdot | 26 | 1.26e-05 | 5.24e-08 | 1.27e-05 |
| P43-REF-U-002 | 0.114 | F43.xO | 18 | 2.99e-09 | 1.23e-11 | 3.03e-09 |
| P43-REF-U-002 | 0.114 | F43.valve_travel | 8 | 4.38e-05 | 1.99e-07 | 4.44e-05 |
| P43-REF-U-002 | 0.114 | F43.u | 16 | 1.28e-06 | 4.47e-09 | 1.29e-06 |
| P43-REF-U-002 | 0.114 | F43.setpoint_frac | 15 | 1.66e-06 | 6.79e-09 | 1.68e-06 |
| P43-REF-U-002 | 0.114 | F43.overshoot | 3 | 1.41e-05 | 6.16e-08 | 1.43e-05 |
| P43-REF-U-002 | 0.114 | F43.valve_travel_total | 1 | 2.17e-05 | 1.02e-07 | 2.21e-05 |
| P43-REF-U-003 | 0.0927 | F43.p | 26 | 3.96e-06 | 2.88e-08 | 3.99e-06 |
| P43-REF-U-003 | 0.0927 | F43.mdot | 26 | 2.23e-05 | 1.63e-07 | 2.25e-05 |
| P43-REF-U-003 | 0.0927 | F43.xO | 18 | 8.05e-08 | 5.64e-10 | 8.11e-08 |
| P43-REF-U-003 | 0.0927 | F43.valve_travel | 8 | 8.39e-05 | 6.15e-07 | 8.46e-05 |
| P43-REF-U-003 | 0.0927 | F43.u | 16 | 2.11e-06 | 1.51e-08 | 2.13e-06 |
| P43-REF-U-003 | 0.0927 | F43.setpoint_frac | 15 | 3.96e-06 | 2.88e-08 | 3.99e-06 |
| P43-REF-U-003 | 0.0927 | F43.overshoot | 3 | 0.016 | 0.000122 | 0.0162 |
| P43-REF-U-003 | 0.0927 | F43.valve_travel_total | 1 | 5.45e-05 | 3.97e-07 | 5.5e-05 |
| P45-PROD-U-000 | 0.465 | F45.P_dev | 1 | 0.00178 | 1.25e-05 | 0.00177 |
| P45-PROD-U-000 | 0.465 | F45.mdot | 2 | 0.0102 | 0.000243 | 0.00997 |
| P45-PROD-U-000 | | P_dev_max_frac (N / T1 / T2) | | 0.213, 0.214, 0.214 | 0.214, 0.214, 0.214 | |
| P45-PROD-U-001 | 0.577 | F45.P_dev | 1 | 4.71e-08 | 0 | 4.68e-08 |
| P45-PROD-U-001 | 0.577 | F45.mdot | 2 | 0.00842 | 0.00266 | 0.011 |
| P45-PROD-U-001 | | P_dev_max_frac (N / T1 / T2) | | 0.14, 0.14, 0.14 | 0.14, 0.14, 0.14 | |
| P45-PROD-U-002 | 0.262 | F45.P_dev | 1 | 0.000109 | 4.43e-07 | 0.000108 |
| P45-PROD-U-002 | 0.262 | F45.mdot | 2 | 0.00189 | 1.56e-05 | 0.00186 |
| P45-PROD-U-002 | | P_dev_max_frac (N / T1 / T2) | | 0.114, 0.114, 0.114 | 0.114, 0.114, 0.114 | |
| P45-PROD-U-003 | 0.00725 | F45.P_dev | 1 | 0.0604 | 0 | 0.0604 |
| P45-PROD-U-003 | 0.00725 | F45.mdot | 2 | 0.0442 | 3.31e-07 | 0.0441 |
| P45-PROD-U-003 | | P_dev_max_frac (N / T1 / T2) | | 0.0606, 0.00018, 0.00018 | 0.00018, 0.00018, 0.00018 | |
| P45-PROD-U-004 | 0.408 | F45.P_dev | 1 | 3.73e-05 | 1.44e-06 | 3.81e-05 |
| P45-PROD-U-004 | 0.408 | F45.mdot | 2 | 0.000288 | 2.54e-05 | 0.000289 |
| P45-PROD-U-004 | | P_dev_max_frac (N / T1 / T2) | | 0.15, 0.15, 0.15 | 0.15, 0.15, 0.15 | |
| P45-PROD-U-005 | 0.411 | F45.P_dev | 1 | 0.00304 | 5.37e-05 | 0.00299 |
| P45-PROD-U-005 | 0.411 | F45.mdot | 2 | 0.0201 | 0.000599 | 0.0207 |
| P45-PROD-U-005 | | P_dev_max_frac (N / T1 / T2) | | 0.17, 0.173, 0.173 | 0.173, 0.173, 0.173 | |
| P45-PROD-U-006 | 0.154 | F45.P_dev | 1 | 0.00143 | 4.59e-06 | 0.00143 |
| P45-PROD-U-006 | 0.154 | F45.mdot | 2 | 0.0377 | 0.000168 | 0.0375 |
| P45-PROD-U-006 | | P_dev_max_frac (N / T1 / T2) | | 0.106, 0.108, 0.108 | 0.108, 0.108, 0.108 | |
| P45-PROD-U-007 | 0.904 | F45.P_dev | 1 | 0.000655 | 0.000161 | 0.000814 |
| P45-PROD-U-007 | 0.904 | F45.mdot | 2 | 0.00279 | 0.00203 | 0.00143 |
| P45-PROD-U-007 | | P_dev_max_frac (N / T1 / T2) | | 0.0623, 0.0617, 0.0617 | 0.0615, 0.0617, 0.0617 | |


## Transient procedure v3 (A9.31 sec. 5)

* Frozen envelope record `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/transient_envelope_v8.json` sha256 `29430be1b259b16a75b590c0ace58d8491219612ab5e3bea2a1b24960bccc269`, committed in `7262ad274a36` (before any held-out vector was run).
* Bound per leaf: (E_py + E_rust) x s_F + max(4 ulp, 1e-9 |py|); p_inlet_max_Pa: primitive image W + the same floating allowance; K_min, K_over_K0_max, p_stage_max_Pa, P_el_max_W, T_comp_max_K: reported with conditioning, scored through their primitives (contract v5).

| entry | observable | family | n | fail | max abs diff | max used fraction of the bound |
|---|---|---|---|---|---|---|
| plenum.transient_run | segments/[]/p/[] | F42.p | 19328 | 0 | 2.37e-07 | 0.101 |
| plenum.transient_run | segments/[]/mdot/[] | F42.mdot | 19328 | 0 | 2.23e-12 | 0.0816 |
| plenum.transient_run | segments/[]/u/[] | F42.u | 19328 | 0 | 1.26e-05 | 0.115 |
| plenum.transient_run | segments/[]/xO/[] | F42.xO | 19328 | 0 | 2.83e-06 | 0.403 |
| plenum.transient_run | segments/[]/p_inlet_max_Pa | image:p_inlet_max_Pa | 128 | 0 | 5.67e-10 | 0.00875 |
| plenum.transient_run | throughput_kg | F42.throughput | 16 | 0 | 7.27e-17 | 0.000186 |
| plenum.transient_case | metrics/[]/P_final_Pa | F43.p | 128 | 2 | 4.3e-07 | 1.05 |
| plenum.transient_case | metrics/[]/mdot_final_kgps | F43.mdot | 128 | 2 | 4.32e-14 | 1.17 |
| plenum.transient_case | metrics/[]/P_min_Pa | F43.p | 128 | 1 | 6.15e-07 | 1.18 |
| plenum.transient_case | metrics/[]/P_max_Pa | F43.p | 128 | 1 | 5.03e-07 | 1.23 |
| plenum.transient_case | metrics/[]/mdot_min_kgps | F43.mdot | 128 | 1 | 1.24e-12 | 1.17 |
| plenum.transient_case | metrics/[]/mdot_max_kgps | F43.mdot | 128 | 1 | 1.16e-12 | 1.15 |
| plenum.transient_case | metrics/[]/xO_min | F43.xO | 128 | 0 | 3.27e-06 | 0.836 |
| plenum.transient_case | metrics/[]/xO_max | F43.xO | 128 | 0 | 3.51e-06 | 0.898 |
| plenum.transient_case | metrics/[]/valve_travel | F43.valve_travel | 128 | 0 | 0.0118 | 0.93 |
| plenum.transient_case | metrics/[]/u_min | F43.u | 128 | 1 | 0.000438 | 1.15 |
| plenum.transient_case | metrics/[]/u_max | F43.u | 128 | 1 | 0.00043 | 1.13 |
| plenum.transient_case | metrics/[]/final_setpoint_error_frac | F43.setpoint_frac | 128 | 2 | 4.3e-05 | 1.05 |
| plenum.transient_case | metrics/[]/peak_deviation_frac | F43.setpoint_frac | 96 | 1 | 5.03e-05 | 1.23 |
| plenum.transient_case | metrics/[]/overshoot_frac | F43.overshoot | 32 | 1 | 0.000498 | 1.54 |
| plenum.transient_case | summary/P_min_Pa | F43.p | 16 | 0 | 6.15e-07 | 0.428 |
| plenum.transient_case | summary/P_max_Pa | F43.p | 16 | 0 | 1.85e-07 | 0.205 |
| plenum.transient_case | summary/mdot_min_kgps | F43.mdot | 16 | 0 | 3.48e-17 | 0.00797 |
| plenum.transient_case | summary/mdot_max_kgps | F43.mdot | 16 | 0 | 1.73e-14 | 0.468 |
| plenum.transient_case | summary/xO_flow_min | F43.xO | 16 | 0 | 1.39e-06 | 0.354 |
| plenum.transient_case | summary/xO_flow_max | F43.xO | 16 | 0 | 5.62e-07 | 0.208 |
| plenum.transient_case | summary/overshoot_max | F43.overshoot | 16 | 1 | 0.000498 | 1.54 |
| plenum.transient_case | objectives/valve_travel | F43.valve_travel_total | 16 | 1 | 0.0545 | 1.7 |
| plenum.transient_case | objectives/peak_deviation_max | F43.setpoint_frac | 16 | 1 | 5.03e-05 | 1.23 |
| plenum.orbit_sim | P_dev_max_frac | F45.P_dev | 4 | 0 | 5.06e-07 | 0.0896 |
| plenum.orbit_sim | mdot_min_kgps | F45.mdot | 4 | 0 | 1.47e-13 | 0.0284 |
| plenum.orbit_sim | mdot_max_kgps | F45.mdot | 4 | 0 | 5.06e-14 | 0.0588 |
| plenum.stability_spectrum | equilibria/[]/re_lead | L.re_lead | 373 | 0 | 1.36e-14 | 0.0048 |
| plenum.stability_spectrum | equilibria/[]/im_lead | L.im_lead | 373 | 0 | 1.87e-14 | 5.02e-06 |

Cascade diagnostics conditioning kappa = W / (delta |f|): 768 values, 534 with kappa <= 1e2, 17 with kappa > 1e6 (0 infinite); 3 with kappa_round > 1e6 (a 4-ulp change of the states moves the computed value by more than 1e6 x its 4-ulp scale: the computed digits are rounding noise). Recorded, no tolerance invented.

Reported with conditioning, scored through their primitives (v5):

* segments/[]/K_min: n 128, max abs diff 8.33e+38, max rel diff 59.8
* segments/[]/K_over_K0_max: n 128, max abs diff 0.000151, max rel diff 0.000151
* segments/[]/p_stage_max_Pa: n 128, max abs diff 5.11e+61, max rel diff 1
* segments/[]/P_el_max_W: n 128, max abs diff 6.87e+60, max rel diff 1.92
* segments/[]/T_comp_max_K: n 128, max abs diff 1.72e+61, max rel diff 1.76

* NN-P-01: {"n": 72, "n_fail": 0, "ok": true, "python_recorded": {"n": 72, "n_fail": 0, "failures": []}}
* NN-P-02: {"n": 40, "n_fail": 0, "ok": true, "python_recorded": {"n": 40, "n_fail": 0, "failures": []}}
* VS-P-01: {"n": 40, "n_fail": 0, "ok": true, "python_recorded": {"n": 40, "n_fail": 0, "failures": []}}
* EV-P-01: {"n": 72, "n_fail": 0, "ok": true, "python_recorded": {"n": 72, "n_fail": 0, "failures": []}}
* IMG-CHECK (f(y) equals the Python reported diagnostic): {"n": 16, "ok": true}

## Performance (reported, never a criterion)

* PERF-P-01 (12 vectors): Python 0.080 s, Rust 0.113 s (median of 3; speed-up 0.7x; the 12 P38 steady sweeps (Rust request also runs the scalar twin)).
* PERF-P-02 (36 vectors): Python 0.824 s, Rust 0.457 s (median of 3; speed-up 1.8x; the 12 production (v7: stable-stratum) transient_case vectors).
* PERF-P-03 (300 vectors): Python 0.029 s, Rust 0.034 s (median of 3; speed-up 0.9x; the 300 P49 Reservoir.steady_state vectors).

## Failures (first 50)

* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/overshoot_frac", "rust": "1.1652399909557876", "python": "1.1647421250054284", "path": "metrics/2/overshoot_frac", "tolerance": {"abs_env": 0.00032244067066622417, "family": "F43.overshoot", "level": "PROD"}, "c`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/P_final_Pa", "rust": "0.009904951852167573", "python": "0.009905381654265452", "path": "metrics/4/P_final_Pa", "tolerance": {"abs_env": 4.0798057323807035e-07, "family": "F43.p", "level": "PROD"}, "class": "CONV`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/final_setpoint_error_frac", "rust": "0.009504814783242721", "python": "0.009461834573454807", "path": "metrics/4/final_setpoint_error_frac", "tolerance": {"abs_env": 4.079805732378622e-05, "family": "F43.setpoin`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/mdot_final_kgps", "rust": "1.963506739716432e-11", "python": "1.967828501958903e-11", "path": "metrics/5/mdot_final_kgps", "tolerance": {"abs_env": 3.704699676519386e-14, "family": "F43.mdot", "level": "PROD"}, `
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/P_final_Pa", "rust": "0.010095203670897607", "python": "0.010094786805796589", "path": "metrics/6/P_final_Pa", "tolerance": {"abs_env": 4.0798057323807035e-07, "family": "F43.p", "level": "PROD"}, "class": "CONV`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/P_min_Pa", "rust": "0.009800246670735771", "python": "0.00980072732846648", "path": "metrics/6/P_min_Pa", "tolerance": {"abs_env": 4.0798057323807035e-07, "family": "F43.p", "level": "PROD"}, "class": "CONVERGEN`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/P_max_Pa", "rust": "0.010206574722370666", "python": "0.010206071455475663", "path": "metrics/6/P_max_Pa", "tolerance": {"abs_env": 4.0798057323807035e-07, "family": "F43.p", "level": "PROD"}, "class": "CONVERGE`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/mdot_min_kgps", "rust": "1.957533591552228e-11", "python": "1.96188383839859e-11", "path": "metrics/6/mdot_min_kgps", "tolerance": {"abs_env": 3.704699676519386e-14, "family": "F43.mdot", "level": "PROD"}, "clas`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/mdot_max_kgps", "rust": "5.5253992233352744e-11", "python": "5.5211431884124025e-11", "path": "metrics/6/mdot_max_kgps", "tolerance": {"abs_env": 3.704699676519386e-14, "family": "F43.mdot", "level": "PROD"}, "c`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/u_min", "rust": "0.19674752288112948", "python": "0.19718520339460763", "path": "metrics/6/u_min", "tolerance": {"abs_env": 0.0003791771510670561, "family": "F43.u", "level": "PROD"}, "class": "CONVERGENCE_ENVEL`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/u_max", "rust": "0.5559969167725349", "python": "0.5555668782782089", "path": "metrics/6/u_max", "tolerance": {"abs_env": 0.0003791771510670561, "family": "F43.u", "level": "PROD"}, "class": "CONVERGENCE_ENVELOP`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/final_setpoint_error_frac", "rust": "0.009520367089760687", "python": "0.009478680579658866", "path": "metrics/6/final_setpoint_error_frac", "tolerance": {"abs_env": 4.079805732378622e-05, "family": "F43.setpoin`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/peak_deviation_frac", "rust": "0.020657472237066606", "python": "0.020607145547566277", "path": "metrics/6/peak_deviation_frac", "tolerance": {"abs_env": 4.079805732378622e-05, "family": "F43.setpoint_frac", "le`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "metrics/[]/mdot_final_kgps", "rust": "3.7809875239766503e-11", "python": "3.7772637567292206e-11", "path": "metrics/7/mdot_final_kgps", "tolerance": {"abs_env": 3.704699676519386e-14, "family": "F43.mdot", "level": "PROD"}`
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "summary/overshoot_max", "rust": "1.1652399909557876", "python": "1.1647421250054284", "path": "summary/overshoot_max", "tolerance": {"abs_env": 0.00032244067066622417, "family": "F43.overshoot", "level": "PROD"}, "class": `
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "objectives/valve_travel", "rust": "34.70488046761449", "python": "34.65038264861498", "path": "objectives/valve_travel", "tolerance": {"abs_env": 0.032067830348548654, "family": "F43.valve_travel_total", "level": "PROD"}, `
* `{"vector": "P43-PROD-S-010", "entry": "plenum.transient_case", "observable": "objectives/peak_deviation_max", "rust": "0.020657472237066606", "python": "0.020607145547566277", "path": "objectives/peak_deviation_max", "tolerance": {"abs_env": 4.079805732378622e-05, "family": "F43.setpoint_frac", "lev`

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring
* entry indices: the contract registers vector counts per P-number; the function assigned to each index is fixed in the harness docstring (written before the scoring run); P40 (synthetic-segment metrics) is not named in any float group of the contract and takes the strictest closed-form class (k_ulp 4 / r_rel 1e-12)
* harness instrumentation: TransientRun._segment_record is wrapped in the harness process to record u_cmd at the segment end and the samples (threshold-proximity rule); the record it returns is unchanged and no reference file is modified. The Rust transient_run request returns the same u_cmd as '_ucmd_end' (reported, not scored)
* the Rust steady_sweep request also returns the scalar twin of every point ('_scalar', stripped before the comparison) for INV-P-02
* nfev and mass_residual_rel of the transients, iterations of the reservoir fixed point and every conservation_residual_rel leaf are reported, not scored (registered); CONS-P-02 / -03 gate them
* harness instrumentation (v3): the tap of TransientRun._segment_record also keeps the run's states at the samples (for the primitive image of the cascade diagnostics and the per-segment proximity flags); the reference record is unchanged (IMG-CHECK: f(y) equals the reported value bit for bit)
* v8 is contract v7 (registered bd11e5c; REGISTERED_NEVER_SCORED, superseded: unstable-stratum time-domain observables ill-posed, noise-seeded growth) with transient_convergence_procedure_v8: the unstable stratum is scored on its input-only class and its leading eigenvalues at every UNSAT event equilibrium (Jacobian blocks under the steady class; re_lead / im_lead under the convergence-derived eigen envelope of the frozen v8 record); every time-domain output of an unstable vector is reported labelled ILL_POSED_UNSTABLE_EQUILIBRIUM with its cross-level and cross-implementation spread; the Rust typed status is checked by ST-P-01 (DIV-P-04); the stable stratum is scored as in v7 with the reused v7 stable-stratum envelopes (record e4774be4..., 60df0d4)
* order of commits: the Rust typed-status addition b5018a9, the v7 supersession and DIV-P-REF-01 addendum A1, contract v8 (alone), the v8 harness, the frozen v8 envelope record (eigen refinement incl. the non-vacuity check), the captured scoring run, the reports
* development runs after the registration (development_master_seed 731905473 only, never scored, no report in the contract directory): a 22-vector draft of the eigen refinement, a development comparison of the transient entries and one full development report, used to test the v8 harness
* downstream-consumer audit of the plenum transient (every crate of the workspace): no crate other than abep-gaspath calls TransientRun / transient_case / orbit_simulated (abep-assess, abep-design and abep-uq use only the steady plenum_feed functions, upstream, compressor, rec and pyops; abep-ci only names the crate); inside abep-gaspath transient_case and orbit_simulated are the producers and the *_assessed entries wrap them with the typed status; the parity CLI and this harness report the plain records and do not use them as results; the guard test no_crate_outside_gaspath_reads_plain_transient_records keeps it so. No admitted output changed

## Ledger update requested

* C-ABEP_SIM_DESIGN_PLENUM_FEED_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_RESERVOIR_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_DESIGN_PLENUM_FEED_PY: PYTHON_REFERENCE note (DIV-P-REF-01 and addendum A1): the Python transient output (TransientRun.run, transient_case, orbit_simulated) is not trustworthy on unstable closed loops at any tolerance level; production use of those results on such loops is not admissible evidence
* C-ABEP_SIM_COMPRESSOR_PY, C-ABEP_SIM_ROTOR_STRENGTH_PY, C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY (compressor v2) and C-ABEP_SIM_DESIGN_FILTER_STAGE_PY (filter stage v1 / v2), ADMITTED: unchanged (recorded-source note): their reports record the sha256 of every abep-gaspath source; the shared sources changed after admission in 361a197 (growing-mode guard), b4de97d (stability class) and b5018a9 (typed transient status), all in crates/abep-gaspath/src/transient.rs and the parity CLI; parity CLI stdout on their captured scoring inputs is byte-identical before and after each change (2368 / 1732 / 1732 requests)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
