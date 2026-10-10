# Plenum / feed transient envelope record v3 (REFINEMENT_FROZEN)

Contract `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v5.json` sha256 `1b382387491bef6c4a1669b27170dac42ae5a416fc43527f1c840e9d8aa2f092` (registered in `f44dbfe5ef65`). Generated from the JSON record next to this file.

* Procedure: transient_convergence_procedure_v3 steps 1-4 (A9.31 sec. 5); estimator e = (|x_N - x_T2| + |x_T1 - x_T2|) / s_F, E = max over the grid, no multiplier.
* Seed 731905543; 2560 refinement vectors {"P42": {"PROD": 768, "REF": 256}, "P43": {"PROD": 768, "REF": 256}, "P45": {"PROD": 512}}; inputs sha256 `4d4c6110e918f982...`.
* Python reference commit `0d8922cfe39b`; code at `faa4c1d28176`; rustc 1.94.1 (e408947bf 2026-03-25); Python 3.11.15, numpy 2.4.4, scipy 1.17.1.
* Checks: {"COMP-P-01": true, "no_missing_envelope": true}; missing envelopes: none.

## Envelopes (normalised by the family scale)

| level | entry | family | scale | E python | E rust | combined | n leaves (py / rust) | worst vector (py) |
|---|---|---|---|---|---|---|---|---|
| PROD | P42 | F42.mdot | mdot_scale | 0.00289 | 0.00125 | 0.00414 | 809360 / 825064 | R42-PROD-078 |
| PROD | P42 | F42.p | r0 | 0.00083 | 0.000312 | 0.00114 | 809360 / 825064 | R42-PROD-411 |
| PROD | P42 | F42.throughput | relative | 1.61e-08 | 1.44e-11 | 1.61e-08 | 670 / 683 | R42-PROD-555 |
| PROD | P42 | F42.u | 1 | 0.000818 | 0.000544 | 0.00136 | 809360 / 825064 | R42-PROD-078 |
| PROD | P42 | F42.ucmd_end | 1 | 0.00209 | 0.00121 | 0.00329 | 5360 / 5464 | R42-PROD-411 |
| PROD | P42 | F42.xO | 1 | 4.25e-05 | 2.14e-05 | 6.39e-05 | 809360 / 824811 | R42-PROD-486 |
| PROD | P43 | F43.mdot | mdot_scale | 0.00577 | 0.000544 | 0.00631 | 18278 / 18278 | R43-PROD-213 |
| PROD | P43 | F43.overshoot | 1 | 0.789 | 0.235 | 1.02 | 2109 / 2109 | R43-PROD-719 |
| PROD | P43 | F43.p | r0 | 0.000759 | 0.000142 | 0.0009 | 18278 / 18278 | R43-PROD-194 |
| PROD | P43 | F43.setpoint_frac | 1 | 0.000759 | 0.000142 | 0.0009 | 10545 / 10545 | R43-PROD-194 |
| PROD | P43 | F43.u | 1 | 0.000689 | 0.000168 | 0.000856 | 11248 / 11248 | R43-PROD-194 |
| PROD | P43 | F43.valve_travel | 1 | 0.00632 | 0.001 | 0.00732 | 5624 / 5624 | R43-PROD-345 |
| PROD | P43 | F43.valve_travel_total | 1 | 0.00736 | 0.00166 | 0.00902 | 703 / 703 | R43-PROD-194 |
| PROD | P43 | F43.xO | 1 | 0.000226 | 2.59e-06 | 0.000229 | 12654 / 12654 | R43-PROD-451 |
| PROD | P45 | F45.P_dev | 1 | 0.00622 | 0.0311 | 0.0373 | 366 / 366 | R45-054 |
| PROD | P45 | F45.mdot | mdot_scale | 0.0465 | 0.782 | 0.829 | 732 / 732 | R45-198 |
| REF | P42 | F42.mdot | mdot_scale | 4.54e-05 | 4.38e-07 | 4.59e-05 | 266968 / 270592 | R42-REF-893 |
| REF | P42 | F42.p | r0 | 2.11e-05 | 2e-07 | 2.13e-05 | 266968 / 270592 | R42-REF-893 |
| REF | P42 | F42.throughput | relative | 1.96e-12 | 4.15e-15 | 1.97e-12 | 221 / 224 | R42-REF-832 |
| REF | P42 | F42.u | 1 | 1.84e-05 | 1.77e-07 | 1.86e-05 | 266968 / 270592 | R42-REF-893 |
| REF | P42 | F42.ucmd_end | 1 | 0.000122 | 1.18e-06 | 0.000124 | 1768 / 1792 | R42-REF-893 |
| REF | P42 | F42.xO | 1 | 1.03e-06 | 9.93e-09 | 1.04e-06 | 266968 / 270535 | R42-REF-893 |
| REF | P43 | F43.mdot | mdot_scale | 3.69e-05 | 2.35e-07 | 3.72e-05 | 6032 / 6032 | R43-REF-906 |
| REF | P43 | F43.overshoot | 1 | 0.00528 | 1.18e-05 | 0.00529 | 696 / 696 | R43-REF-980 |
| REF | P43 | F43.p | r0 | 1.22e-05 | 4.48e-08 | 1.22e-05 | 6032 / 6032 | R43-REF-980 |
| REF | P43 | F43.setpoint_frac | 1 | 1.22e-05 | 4.48e-08 | 1.22e-05 | 3480 / 3480 | R43-REF-980 |
| REF | P43 | F43.u | 1 | 3.43e-06 | 2.08e-08 | 3.45e-06 | 3712 / 3712 | R43-REF-906 |
| REF | P43 | F43.valve_travel | 1 | 8.13e-05 | 5.09e-07 | 8.19e-05 | 1856 / 1856 | R43-REF-906 |
| REF | P43 | F43.valve_travel_total | 1 | 5.99e-05 | 3.03e-07 | 6.02e-05 | 232 / 232 | R43-REF-928 |
| REF | P43 | F43.xO | 1 | 0.000271 | 5.23e-06 | 0.000276 | 4176 / 4176 | R43-REF-952 |

## Recorded, not used

Converged T2 vs T2 across implementations (model-equivalence diagnostic, not a verdict), max over the grid in family units:

* PROD/P42/F42.p: 9.3e-08 (n 841976)
* PROD/P42/F42.mdot: 5.99e-07 (n 841976)
* PROD/P42/F42.u: 2.19e-07 (n 841976)
* PROD/P42/F42.xO: 2.5e-09 (n 840804)
* PROD/P42/F42.ucmd_end: 4.38e-07 (n 5576)
* PROD/P42/F42.throughput: 4.66e-11 (n 697)
* REF/P42/F42.p: 1.26e-06 (n 276632)
* REF/P42/F42.mdot: 2.7e-06 (n 276632)
* REF/P42/F42.u: 1.09e-06 (n 276632)
* REF/P42/F42.xO: 6.13e-08 (n 276155)
* REF/P42/F42.ucmd_end: 7.28e-06 (n 1832)
* REF/P42/F42.throughput: 8.43e-12 (n 229)
* PROD/P43/F43.p: 1.42e-07 (n 18278)
* PROD/P43/F43.mdot: 1.36e-06 (n 18278)
* PROD/P43/F43.xO: 0.000226 (n 12654)
* PROD/P43/F43.valve_travel: 1.4e-06 (n 5624)
* PROD/P43/F43.u: 1.41e-07 (n 11248)
* PROD/P43/F43.setpoint_frac: 1.42e-07 (n 10545)
* PROD/P43/F43.overshoot: 0.000374 (n 2109)
* PROD/P43/F43.valve_travel_total: 3.06e-06 (n 703)
* REF/P43/F43.p: 4.39e-07 (n 6032)
* REF/P43/F43.mdot: 5.84e-07 (n 6032)
* REF/P43/F43.xO: 7.16e-05 (n 4176)
* REF/P43/F43.valve_travel: 2.81e-06 (n 1856)
* REF/P43/F43.u: 1.74e-07 (n 3712)
* REF/P43/F43.setpoint_frac: 4.39e-07 (n 3480)
* REF/P43/F43.overshoot: 0.000207 (n 696)
* REF/P43/F43.valve_travel_total: 2.2e-06 (n 232)
* PROD/P45/F45.P_dev: 3.5e-06 (n 366)
* PROD/P45/F45.mdot: 2.83e-05 (n 732)

Convergence ratio max|T1 - T2| / max|N - T2|:

* python: PROD/P42/F42.mdot 0.00492; PROD/P42/F42.p 0.00763; PROD/P42/F42.throughput 0.00317; PROD/P42/F42.u 0.00649; PROD/P42/F42.ucmd_end 0.00734; PROD/P42/F42.xO 0.00403; PROD/P43/F43.mdot 0.0044; PROD/P43/F43.overshoot 0.00822; PROD/P43/F43.p 0.0047; PROD/P43/F43.setpoint_frac 0.0047; PROD/P43/F43.u 0.00479; PROD/P43/F43.valve_travel 0.00381; PROD/P43/F43.valve_travel_total 0.00601; PROD/P43/F43.xO 21.2; PROD/P45/F45.P_dev 0.00993; PROD/P45/F45.mdot 0.014; REF/P42/F42.mdot 0.0709; REF/P42/F42.p 0.0707; REF/P42/F42.throughput 0.205; REF/P42/F42.u 0.0709; REF/P42/F42.ucmd_end 0.071; REF/P42/F42.xO 0.0709; REF/P43/F43.mdot 0.0342; REF/P43/F43.overshoot 0.0516; REF/P43/F43.p 0.0474; REF/P43/F43.setpoint_frac 0.0474; REF/P43/F43.u 0.0818; REF/P43/F43.valve_travel 0.0586; REF/P43/F43.valve_travel_total 0.0478; REF/P43/F43.xO 34.8
* rust: PROD/P42/F42.mdot 0.00023; PROD/P42/F42.p 0.000401; PROD/P42/F42.throughput 0.00818; PROD/P42/F42.u 0.000149; PROD/P42/F42.ucmd_end 0.000181; PROD/P42/F42.xO 0.000208; PROD/P43/F43.mdot 0.0011; PROD/P43/F43.overshoot 0.000714; PROD/P43/F43.p 0.000501; PROD/P43/F43.setpoint_frac 0.000501; PROD/P43/F43.u 0.000303; PROD/P43/F43.valve_travel 0.000858; PROD/P43/F43.valve_travel_total 0.000552; PROD/P43/F43.xO 0.684; PROD/P45/F45.P_dev 0.000109; PROD/P45/F45.mdot 5.12e-05; REF/P42/F42.mdot 0.021; REF/P42/F42.p 0.0209; REF/P42/F42.throughput 0.275; REF/P42/F42.u 0.021; REF/P42/F42.ucmd_end 0.021; REF/P42/F42.xO 0.021; REF/P43/F43.mdot 0.0137; REF/P43/F43.overshoot 0.0027; REF/P43/F43.p 0.0107; REF/P43/F43.setpoint_frac 0.0107; REF/P43/F43.u 0.0198; REF/P43/F43.valve_travel 0.0137; REF/P43/F43.valve_travel_total 0.0223; REF/P43/F43.xO 966

Segment cascade diagnostics, relative N - T2 difference (ill-conditioning; scored through the primitive image):

* python: PROD/K_min/out_of_domain +inf (n 4545); PROD/K_over_K0_max/out_of_domain 0.000166 (n 4545); PROD/p_stage_max_Pa/out_of_domain 1.43e+34 (n 4545); PROD/p_inlet_max_Pa/out_of_domain 1.18e-06 (n 4545); PROD/P_el_max_W/out_of_domain 2.02e+34 (n 4545); PROD/T_comp_max_K/out_of_domain 2.02e+34 (n 4545); PROD/K_min/in_domain 1.4e+42 (n 815); PROD/K_over_K0_max/in_domain 4.2e-05 (n 815); PROD/p_stage_max_Pa/in_domain 1.02e+35 (n 815); PROD/p_inlet_max_Pa/in_domain 5.56e-06 (n 815); PROD/P_el_max_W/in_domain 1.42e+35 (n 815); PROD/T_comp_max_K/in_domain 1.41e+35 (n 815); REF/K_min/out_of_domain 2.29e+23 (n 1516); REF/K_over_K0_max/out_of_domain 4.69e-05 (n 1516); REF/p_stage_max_Pa/out_of_domain 5.43e+21 (n 1516); REF/p_inlet_max_Pa/out_of_domain 8.59e-09 (n 1516); REF/P_el_max_W/out_of_domain 5.34e+21 (n 1516); REF/T_comp_max_K/out_of_domain 4.31e+21 (n 1516); REF/K_min/in_domain 6.4e-06 (n 252); REF/K_over_K0_max/in_domain 2.33e-08 (n 252); REF/p_stage_max_Pa/in_domain 0.0233 (n 252); REF/p_inlet_max_Pa/in_domain 1.03e-08 (n 252); REF/P_el_max_W/in_domain 2.02e-06 (n 252); REF/T_comp_max_K/in_domain 1.77e-07 (n 252)
* rust: PROD/K_min/out_of_domain 1.49e+03 (n 4628); PROD/K_over_K0_max/out_of_domain 0.000151 (n 4628); PROD/p_stage_max_Pa/out_of_domain 5.62e+13 (n 4628); PROD/p_inlet_max_Pa/out_of_domain 1.95e-09 (n 4628); PROD/P_el_max_W/out_of_domain 7.94e+13 (n 4628); PROD/T_comp_max_K/out_of_domain 7.94e+13 (n 4628); PROD/K_min/in_domain 2.78e-09 (n 836); PROD/K_over_K0_max/in_domain 7.82e-09 (n 836); PROD/p_stage_max_Pa/in_domain 0.00472 (n 836); PROD/p_inlet_max_Pa/in_domain 3.3e-10 (n 836); PROD/P_el_max_W/in_domain 0.00441 (n 836); PROD/T_comp_max_K/in_domain 0.00441 (n 836); REF/K_min/out_of_domain 1.28e+03 (n 1532); REF/K_over_K0_max/out_of_domain 4.69e-05 (n 1532); REF/p_stage_max_Pa/out_of_domain 1.76e+14 (n 1532); REF/p_inlet_max_Pa/out_of_domain 1.22e-12 (n 1532); REF/P_el_max_W/out_of_domain 2.49e+14 (n 1532); REF/T_comp_max_K/out_of_domain 2.49e+14 (n 1532); REF/K_min/in_domain 5.87e-06 (n 260); REF/K_over_K0_max/in_domain 6.83e-10 (n 260); REF/p_stage_max_Pa/in_domain 0.0561 (n 260); REF/p_inlet_max_Pa/in_domain 2.45e-10 (n 260); REF/P_el_max_W/in_domain 4.78e-06 (n 260); REF/T_comp_max_K/in_domain 3.17e-07 (n 260)

CONS-P-03 (mass residual) per run:

* python: PROD/P42/N max 1.68e-14 (above MASS_TOL 0); PROD/P42/T1 max 1.66e-14 (above MASS_TOL 0); PROD/P42/T2 max 1.66e-14 (above MASS_TOL 0); REF/P42/N max 2.3e-13 (above MASS_TOL 0); REF/P42/T1 max 2.36e-13 (above MASS_TOL 0); REF/P42/T2 max 2.33e-13 (above MASS_TOL 0); PROD/P43/N max 1.01e-13 (above MASS_TOL 0); PROD/P43/T1 max 6.07e-14 (above MASS_TOL 0); PROD/P43/T2 max 1.86e-14 (above MASS_TOL 0); REF/P43/N max 3.88e-15 (above MASS_TOL 0); REF/P43/T1 max 4.17e-15 (above MASS_TOL 0); REF/P43/T2 max 3.86e-15 (above MASS_TOL 0); PROD/P45/N max 3.41e-13 (above MASS_TOL 0); PROD/P45/T1 max 1.97e-12 (above MASS_TOL 0); PROD/P45/T2 max 6.25e-13 (above MASS_TOL 0)
* rust: PROD/P42/N max 1.7e-14 (above MASS_TOL 0); PROD/P42/T1 max 1.68e-14 (above MASS_TOL 0); PROD/P42/T2 max 1.71e-14 (above MASS_TOL 0); REF/P42/N max 2.31e-13 (above MASS_TOL 0); REF/P42/T1 max 2.36e-13 (above MASS_TOL 0); REF/P42/T2 max 2.33e-13 (above MASS_TOL 0); PROD/P43/N max 1.04e-14 (above MASS_TOL 0); PROD/P43/T1 max 1.05e-14 (above MASS_TOL 0); PROD/P43/T2 max 1.04e-14 (above MASS_TOL 0); REF/P43/N max 4.06e-15 (above MASS_TOL 0); REF/P43/T1 max 4.19e-15 (above MASS_TOL 0); REF/P43/T2 max 4.32e-15 (above MASS_TOL 0); PROD/P45/N max 5.54e-14 (above MASS_TOL 0); PROD/P45/T1 max 7.63e-14 (above MASS_TOL 0); PROD/P45/T2 max 2.44e-13 (above MASS_TOL 0)

## Excluded vectors and discrete differences

* python: 368 vectors excluded (refused / failed run); 863 discrete N-vs-T2 leaf differences; 0 leaves with zero scale skipped.
* rust: 352 vectors excluded (refused / failed run); 695 discrete N-vs-T2 leaf differences; 0 leaves with zero scale skipped.

Statement: frozen before any held-out (scoring_master_seed) vector is generated or run; never edited after the scoring run.
