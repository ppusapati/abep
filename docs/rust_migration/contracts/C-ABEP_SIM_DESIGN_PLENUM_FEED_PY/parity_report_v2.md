# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_PLENUM_FEED_PY-V2

Verdict: **PARITY_FAIL** (NOT_ADMITTED). Generated from the JSON report next to this file.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v2.json` sha256 `8ee5a18c5ea0a6672da32e20c07c583a514cf9c8bcd543778d9332e229ead0a5`, registered in `92aec7212b46`.
* Python reference commit `af467735bdab`; Rust commit `d55e7e07328b`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905313 (scoring); 3781 vectors; 1 per-test failures.

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
| plenum.filter_case | 114 | 28 | 28 | 0 |
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
| upstream.classify | 30 | 2 | 2 | 0 |
| upstream.combine | 30 | 4 | 4 | 0 |
| upstream.constraint | 30 | 0 | 0 | 0 |
| upstream.control | 55 | 3 | 3 | 0 |
| upstream.setpoint | 415 | 14 | 14 | 0 |
| upstream.controller_view | 5 | 3 | 3 | 0 |
| upstream.schedule_input | 40 | 29 | 29 | 0 |
| upstream.h1_tolerance | 48 | 15 | 15 | 0 |
| upstream.governing_band | 40 | 5 | 5 | 0 |
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
| plenum.steady | a_eq_m2 | ULP_BOUNDED | 380 | 0 | 356 | 1.11e-16 | 9.54e-16 | 7 |
| plenum.steady | bisection_residual_rel | ULP_BOUNDED | 380 | 0 | 367 | 4.44e-16 | 2 | 8.99e+307 |
| plenum.steady | domain_diagnostics/compressor_K_min | ULP_BOUNDED | 294 | 0 | 293 | 3.55e-15 | 1.15e-14 | 64 |
| plenum.steady | domain_diagnostics/compressor_K_over_K0_max | ULP_BOUNDED | 268 | 0 | 267 | 1.11e-16 | 1.76e-16 | 1 |
| plenum.steady | domain_diagnostics/compressor_p_stage_max_Pa | ULP_BOUNDED | 309 | 0 | 308 | 3.47e-18 | 1.19e-15 | 8 |
| plenum.steady | domain_diagnostics/feed_Kn_upper_O_omitted | ULP_BOUNDED | 310 | 0 | 300 | 1.14e-13 | 4.03e-16 | 3 |
| plenum.steady | offered/mdot_s_kgps/<s> | ULP_BOUNDED | 78 | 0 | 69 | 1.32e-23 | 2.73e-16 | 2 |
| plenum.steady | offered/mdot_total_kgps | ULP_BOUNDED | 26 | 0 | 21 | 2.65e-23 | 1.9e-16 | 1 |
| plenum.steady | offered/P_Pa | ULP_BOUNDED | 24 | 0 | 21 | 2.17e-18 | 1.01e-15 | 5 |
| plenum.steady | offered/p_s_Pa/<s> | ULP_BOUNDED | 78 | 0 | 68 | 1.73e-18 | 1.03e-15 | 8 |
| plenum.steady | offered/x_s_flow_mole/<s> | ULP_BOUNDED | 78 | 0 | 71 | 1.11e-16 | 2.41e-16 | 2 |
| plenum.steady | offered/w_s_flow_mass/<s> | ULP_BOUNDED | 78 | 0 | 71 | 1.11e-16 | 2.45e-16 | 2 |
| plenum.steady | offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 78 | 0 | 71 | 1.11e-16 | 3.83e-16 | 2 |
| plenum.steady | compressor_inlet_p_s_Pa/<s> | ULP_BOUNDED | 78 | 0 | 74 | 2.17e-19 | 1.87e-16 | 1 |
| plenum.steady | compressor_inlet_P_Pa | ULP_BOUNDED | 26 | 0 | 25 | 4.34e-19 | 2.12e-16 | 1 |
| plenum.steady | mdot_compressor_gross_kgps/<s> | ULP_BOUNDED | 78 | 0 | 73 | 1.32e-23 | 3.95e-16 | 2 |
| plenum.steady | mdot_compressor_backleak_kgps/<s> | ULP_BOUNDED | 78 | 0 | 69 | 3.43e-27 | 3.41e-15 | 23 |
| plenum.steady | mdot_plenum_leak_kgps/<s> | ULP_BOUNDED | 78 | 0 | 70 | 1.14e-28 | 1.09e-15 | 9 |
| plenum.steady | mdot_recombined_O_kgps | ULP_BOUNDED | 26 | 0 | 25 | 4.14e-25 | 1.57e-16 | 1 |
| plenum.steady | mdot_intake_net_kgps/<s> | ULP_BOUNDED | 78 | 0 | 76 | 6.62e-24 | 1.61e-16 | 1 |
| plenum.steady | compressor/P_gas_W | ULP_BOUNDED | 26 | 0 | 24 | 2.78e-17 | 2.17e-16 | 1 |
| plenum.steady | compressor/K_min | ULP_BOUNDED | 23 | 0 | 21 | 2.22e-16 | 2.18e-16 | 1 |
| plenum.steady | compressor/K_over_K0_max | ULP_BOUNDED | 26 | 0 | 23 | 5.55e-16 | 9.22e-16 | 5 |
| plenum.steady | compressor/p_stage_max_Pa | ULP_BOUNDED | 25 | 0 | 23 | 8.67e-19 | 4.03e-16 | 2 |
| plenum.steady | feed/a_eq_m2 | ULP_BOUNDED | 26 | 0 | 20 | 3.47e-17 | 9.54e-16 | 5 |
| plenum.steady | feed/d_eq_m | ULP_BOUNDED | 26 | 0 | 22 | 1.11e-16 | 5.16e-16 | 4 |
| plenum.steady | feed/Kn_upper_O_omitted | ULP_BOUNDED | 26 | 0 | 22 | 3.64e-12 | 6.74e-16 | 4 |
| plenum.steady | feed/lambda_upper_m | ULP_BOUNDED | 26 | 0 | 22 | 5.33e-15 | 1.17e-15 | 6 |
| plenum.evaluate | a_eq_m2 | ULP_BOUNDED | 71 | 0 | 70 | 6.94e-18 | 1.28e-16 | 1 |
| plenum.evaluate | bisection_residual_rel | ULP_BOUNDED | 71 | 0 | 70 | 1.11e-16 | 0.5 | 2.25e+15 |
| plenum.evaluate | offered/mdot_s_kgps/<s> | ULP_BOUNDED | 21 | 0 | 20 | 6.62e-24 | 1.3e-16 | 1 |
| plenum.evaluate | offered/P_Pa | ULP_BOUNDED | 5 | 0 | 4 | 1.73e-18 | 1.88e-16 | 1 |
| plenum.evaluate | offered/p_s_Pa/<s> | ULP_BOUNDED | 21 | 0 | 19 | 8.67e-19 | 1.73e-16 | 1 |
| plenum.evaluate | offered/x_s_flow_mole/<s> | ULP_BOUNDED | 21 | 0 | 20 | 1.39e-17 | 2.17e-16 | 1 |
| plenum.evaluate | offered/x_s_plenum_mole/<s> | ULP_BOUNDED | 21 | 0 | 19 | 5.55e-17 | 1.81e-16 | 1 |
| plenum.evaluate | mdot_compressor_backleak_kgps/<s> | ULP_BOUNDED | 21 | 0 | 19 | 1.62e-27 | 5.38e-15 | 38 |
| plenum.evaluate | mdot_plenum_leak_kgps/<s> | ULP_BOUNDED | 21 | 0 | 19 | 5.05e-29 | 1.63e-16 | 1 |
| plenum.evaluate | feed/a_eq_m2 | ULP_BOUNDED | 7 | 0 | 6 | 6.94e-18 | 1.28e-16 | 1 |
| plenum.evaluate | feed/Kn_upper_O_omitted | ULP_BOUNDED | 7 | 0 | 6 | 8.88e-16 | 1.66e-16 | 1 |
| plenum.evaluate | feed/lambda_upper_m | ULP_BOUNDED | 7 | 0 | 6 | 2.22e-16 | 1.58e-16 | 1 |
| plenum.sweep | sweep/mdot_total_kgps/[]/[] | ULP_BOUNDED | 1920 | 0 | 1918 | 1.32e-23 | 1.37e-16 | 1 |
| plenum.sweep | sweep/mdot_s_kgps/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5752 | 1.32e-23 | 2.59e-16 | 2 |
| plenum.sweep | sweep/x_s_flow_mole/<s>/[]/[] | ULP_BOUNDED | 5760 | 0 | 5753 | 1.11e-16 | 3.46e-16 | 2 |
| plenum.sweep | sweep/a_eq_m2/[]/[] | ULP_BOUNDED | 1920 | 0 | 1915 | 6.94e-18 | 1.84e-16 | 1 |
| plenum.sweep | sweep/bisection_residual_rel/[]/[] | ULP_BOUNDED | 1920 | 0 | 1919 | 2.22e-16 | 0.5 | 2.25e+15 |
| plenum.sweep | sweep/Kn_upper/[]/[] | ULP_BOUNDED | 1920 | 0 | 1918 | 5.68e-14 | 4.3e-16 | 2 |
| plenum.area_for_pressure | a_eq | ULP_BOUNDED | 80 | 0 | 79 | 1.73e-18 | 1.53e-16 | 1 |
| plenum.area_for_pressure | resid | ULP_BOUNDED | 80 | 0 | 79 | 2.22e-16 | 0.333 | 2.25e+15 |
| plenum.segment_metrics | valve_travel | ULP_BOUNDED | 150 | 0 | 122 | 8.88e-16 | 3.92e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_P | ULP_BOUNDED | 27 | 0 | 19 | 1.11e-16 | 2.33e-16 | 2 |
| plenum.segment_metrics | ripple_pp_frac_mdot | ULP_BOUNDED | 27 | 0 | 21 | 5.55e-17 | 2.87e-16 | 2 |
| plenum.orbit_qs | rows/[]/u_max | ULP_BOUNDED | 9 | 0 | 8 | 1.11e-16 | 2.33e-16 | 2 |
| plenum.orbit_qs | rows/[]/ripple_pp_frac_mdot | ULP_BOUNDED | 9 | 0 | 5 | 1.11e-16 | 3.5e-16 | 2 |
| plenum.orbit_sim | P_dev_max_frac | SOLVER_TOLERANCE | 3 | 1 | 0 | 0.00061 | 0.00273 | 2.2e+13 |
| plenum.orbit_sim | mdot_min_kgps | SOLVER_TOLERANCE | 3 | 0 | 0 | 7.28e-12 | 0.0209 | 1.41e+14 |
| plenum.orbit_sim | mdot_max_kgps | SOLVER_TOLERANCE | 3 | 0 | 0 | 5.64e-11 | 0.0222 | 1.36e+14 |
| plenum.compare_modes | fallback_reference/rows/[]/a_eq_m2 | ULP_BOUNDED | 27 | 0 | 26 | 5.55e-17 | 1.43e-16 | 1 |

Scored float leaves: 89022 (88767 bit-identical); EXACT_VALUE leaves: 66369.

Reported, not scored:

* plenum.steady conservation_residual_rel: n 26, max abs diff 0, max rel diff 0
* plenum.evaluate conservation_residual_rel: n 7, max abs diff 0, max rel diff 0
* plenum.orbit_sim mass_residual_rel: n 3, max abs diff 1.19e-13, max rel diff 0.987
* plenum.orbit_sim nfev: n 3, max abs diff 1e+06, max rel diff 22.8
* reservoir.steady iterations: n 300, max abs diff 0, max rel diff 0

## Domain / error parity

168 vectors with a refusal on either side, 0 mismatches.

| entry | Python | Rust | n |
|---|---|---|---|
| plenum.area_for_pressure | ValueError | ValueError | 3 |
| plenum.compare_modes | ValueError | ValueError | 1 |
| plenum.filter_case | FilterStageError | FilterStageError | 28 |
| plenum.plenum | ValueError | ValueError | 8 |
| plenum.scheduled | ValueError | ValueError | 2 |
| plenum.steady | ZeroDivisionError | ZeroDivisionError | 10 |
| reservoir.steady | KeyError | KeyError | 1 |
| upstream.candidate | A913RuleError | A913RuleError | 2 |
| upstream.classify | A913RuleError | A913RuleError | 2 |
| upstream.combine | A913RuleError | A913RuleError | 4 |
| upstream.control | A913RuleError | A913RuleError | 3 |
| upstream.controller_view | A913RuleError | A913RuleError | 3 |
| upstream.fixed_gate | A913RuleError | A913RuleError | 2 |
| upstream.governing_band | A913RuleError | A913RuleError | 5 |
| upstream.h1_tolerance | A913RuleError | A913RuleError | 15 |
| upstream.lowering | A913RuleError | A913RuleError | 18 |
| upstream.robust_set | A913RuleError | A913RuleError | 13 |
| upstream.robust_set | RepresentativeSelectionRefused | RepresentativeSelectionRefused | 4 |
| upstream.schedule_input | A913RuleError | A913RuleError | 29 |
| upstream.setpoint | A913RuleError | A913RuleError | 14 |
| upstream.state_coverage | A913RuleError | A913RuleError | 1 |

## Threshold proximity

0 vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % limit: none.

## Invariants and conservation

* Rust two processes byte-identical: True (stdout sha256 `84ecded4f0219ad4...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-P-02: {"n": 1920, "n_fail": 0, "failures": [], "ok": true}
* INV-P-04: {"ok": true}
* CONS-P-01: {"n": 33, "n_fail": 0, "ok": true, "max_residual_over_floor": 2.5694624219178297e-16}
* CONS-P-02: {"n": 33, "n_fail": 0, "ok": true, "max_residual_rel": 1.911919760691118e-12}
* CONS-P-03: {"n": 3, "n_fail": 0, "ok": true, "max_mass_residual_rel": 1.5515998671703187e-15}
* CONS-P-04: {"n": 300, "n_fail": 0, "ok": true, "max_balance_residual_rel": 2.019430832575789e-16}

## Performance (reported, never a criterion)

* PERF-P-01 (12 vectors): Python 0.069 s, Rust 0.105 s (median of 3; speed-up 0.7x; the 12 P38 steady sweeps (Rust request also runs the scalar twin)).
* PERF-P-03 (300 vectors): Python 0.024 s, Rust 0.030 s (median of 3; speed-up 0.8x; the 300 P49 Reservoir.steady_state vectors).

## Failures (first 50)

* `{"vector": "P45-0", "entry": "plenum.orbit_sim", "observable": "P_dev_max_frac", "rust": "0.22424606598975216", "python": "0.22363615646224144", "path": "P_dev_max_frac", "tolerance": {"rel": 0.001, "abs": 1e-06}, "class": "SOLVER_TOLERANCE"}`

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring
* entry indices: the contract registers vector counts per P-number; the function assigned to each index is fixed in the harness docstring (written before the scoring run); P40 (synthetic-segment metrics) is not named in any float group of the contract and takes the strictest closed-form class (k_ulp 4 / r_rel 1e-12)
* harness instrumentation: TransientRun._segment_record is wrapped in the harness process to record u_cmd at the segment end and the samples (threshold-proximity rule); the record it returns is unchanged and no reference file is modified. The Rust transient_run request returns the same u_cmd as '_ucmd_end' (reported, not scored)
* the Rust steady_sweep request also returns the scalar twin of every point ('_scalar', stripped before the comparison) for INV-P-02
* nfev and mass_residual_rel of the transients, iterations of the reservoir fixed point and every conservation_residual_rel leaf are reported, not scored (registered); CONS-P-02 / -03 gate them
* v2 is v1 minus the transient entries plenum.transient_run (P42) and plenum.transient_case (P43) (scope_reduction_v2); v1 (PARITY_FAIL, all 247 failures in P42 / P43, classified CONTRACT_DEFECT) stays. Every other observable, tolerance, generator, n and decision rule is v1's, with fresh seeds. The re-specification of the transient observables is a pending owner decision; transient_run / transient_case stay PYTHON_REFERENCE until an owner-ruled transient contract exists. The harness generates the P42 / P43 vectors from their own streams and drops them before any call; CONS-P-03 is evaluated on P45 only; PERF-P-02 (transient_case) is not measured

## Ledger update requested

* C-ABEP_SIM_DESIGN_PLENUM_FEED_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_RESERVOIR_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
