# Plenum / feed transient envelope record v3 (REFINEMENT_FROZEN)

Contract `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v6.json` sha256 `60f8bc2482e967b888f1b1421f8b7b7c907a92fed4b0a88f5d3e65ad30deab5a` (registered in `aca62b36d0d1`). Generated from the JSON record next to this file.

* Procedure: transient_convergence_procedure_v3 steps 1-4 (A9.31 sec. 5); estimator e = (|x_N - x_T2| + |x_T1 - x_T2|) / s_F, E = max over the grid, no multiplier.
* Seed 731905553; 2560 refinement vectors {"P42": {"PROD": 768, "REF": 256}, "P43": {"PROD": 768, "REF": 256}, "P45": {"PROD": 512}}; inputs sha256 `66adcafd7cfa5397...`.
* Python reference commit `0d8922cfe39b`; code at `2cf494791f14`; rustc 1.94.1 (e408947bf 2026-03-25); Python 3.11.15, numpy 2.4.4, scipy 1.17.1.
* Checks: {"COMP-P-01": true, "no_missing_envelope": true}; missing envelopes: none.

## Envelopes (normalised by the family scale)

| level | entry | family | scale | E python | E rust | combined | n leaves (py / rust) | worst vector (py) |
|---|---|---|---|---|---|---|---|---|
| PROD | P42 | F42.mdot | mdot_scale | 0.00798 | 0.00115 | 0.00914 | 802112 / 822648 | R42-PROD-018 |
| PROD | P42 | F42.p | r0 | 0.00655 | 0.000233 | 0.00678 | 802112 / 822648 | R42-PROD-018 |
| PROD | P42 | F42.throughput | relative | 1.36e-09 | 1.19e-10 | 1.48e-09 | 664 / 681 | R42-PROD-046 |
| PROD | P42 | F42.u | 1 | 0.00459 | 0.000529 | 0.00512 | 802112 / 822648 | R42-PROD-018 |
| PROD | P42 | F42.ucmd_end | 1 | 0.0197 | 0.0009 | 0.0206 | 5312 / 5448 | R42-PROD-018 |
| PROD | P42 | F42.xO | 1 | 0.000301 | 8.38e-06 | 0.000309 | 802112 / 822597 | R42-PROD-018 |
| PROD | P43 | F43.mdot | mdot_scale | 0.0134 | 0.000968 | 0.0144 | 18070 / 18070 | R43-PROD-401 |
| PROD | P43 | F43.overshoot | 1 | 0.31 | 0.258 | 0.568 | 2085 / 2085 | R43-PROD-107 |
| PROD | P43 | F43.p | r0 | 0.000753 | 0.000453 | 0.00121 | 18070 / 18070 | R43-PROD-288 |
| PROD | P43 | F43.setpoint_frac | 1 | 0.000753 | 0.000453 | 0.00121 | 10425 / 10425 | R43-PROD-288 |
| PROD | P43 | F43.u | 1 | 0.00224 | 0.000451 | 0.00269 | 11120 / 11120 | R43-PROD-033 |
| PROD | P43 | F43.valve_travel | 1 | 0.0691 | 0.00864 | 0.0777 | 5560 / 5560 | R43-PROD-033 |
| PROD | P43 | F43.valve_travel_total | 1 | 0.176 | 0.00946 | 0.186 | 695 / 695 | R43-PROD-033 |
| PROD | P43 | F43.xO | 1 | 0.000318 | 0.000162 | 0.000479 | 12510 / 12510 | R43-PROD-338 |
| PROD | P45 | F45.P_dev | 1 | 0.188 | 0.0373 | 0.225 | 373 / 373 | R45-187 |
| PROD | P45 | F45.mdot | mdot_scale | 0.496 | 0.229 | 0.725 | 746 / 746 | R45-265 |
| REF | P42 | F42.mdot | mdot_scale | 3.19e-05 | 1.59e-07 | 3.21e-05 | 264552 / 274216 | R42-REF-923 |
| REF | P42 | F42.p | r0 | 6.96e-06 | 3.49e-08 | 6.99e-06 | 264552 / 274216 | R42-REF-827 |
| REF | P42 | F42.throughput | relative | 1.22e-11 | 2.37e-13 | 1.24e-11 | 219 / 227 | R42-REF-998 |
| REF | P42 | F42.u | 1 | 1.2e-05 | 6.3e-08 | 1.21e-05 | 264552 / 274216 | R42-REF-923 |
| REF | P42 | F42.ucmd_end | 1 | 3.71e-05 | 2.88e-07 | 3.74e-05 | 1752 / 1816 | R42-REF-943 |
| REF | P42 | F42.xO | 1 | 6.28e-08 | 1.15e-09 | 6.4e-08 | 264552 / 274210 | R42-REF-1010 |
| REF | P43 | F43.mdot | mdot_scale | 8.95e-05 | 7.33e-07 | 9.02e-05 | 5954 / 5954 | R43-REF-897 |
| REF | P43 | F43.overshoot | 1 | 9.86e-05 | 1.16e-07 | 9.87e-05 | 687 / 687 | R43-REF-771 |
| REF | P43 | F43.p | r0 | 4.5e-06 | 3.79e-08 | 4.54e-06 | 5954 / 5954 | R43-REF-897 |
| REF | P43 | F43.setpoint_frac | 1 | 4.5e-06 | 3.79e-08 | 4.54e-06 | 3435 / 3435 | R43-REF-897 |
| REF | P43 | F43.u | 1 | 2.87e-05 | 2.35e-07 | 2.89e-05 | 3664 / 3664 | R43-REF-897 |
| REF | P43 | F43.valve_travel | 1 | 0.000213 | 1.83e-06 | 0.000215 | 1832 / 1832 | R43-REF-897 |
| REF | P43 | F43.valve_travel_total | 1 | 8.53e-05 | 9.16e-07 | 8.63e-05 | 229 / 229 | R43-REF-897 |
| REF | P43 | F43.xO | 1 | 0.000679 | 0.00122 | 0.0019 | 4122 / 4122 | R43-REF-846 |

## Recorded, not used

Converged T2 vs T2 across implementations (model-equivalence diagnostic, not a verdict), max over the grid in family units:

* PROD/P42/F42.p: 1.09e-06 (n 840768)
* PROD/P42/F42.mdot: 1.93e-06 (n 840768)
* PROD/P42/F42.u: 1.02e-06 (n 840768)
* PROD/P42/F42.xO: 1.45e-08 (n 839757)
* PROD/P42/F42.ucmd_end: 3.57e-06 (n 5568)
* PROD/P42/F42.throughput: 6.07e-11 (n 696)
* REF/P42/F42.p: 2.4e-07 (n 277840)
* REF/P42/F42.mdot: 1.05e-06 (n 277840)
* REF/P42/F42.u: 3.04e-07 (n 277840)
* REF/P42/F42.xO: 6.5e-09 (n 277505)
* REF/P42/F42.ucmd_end: 7.04e-07 (n 1840)
* REF/P42/F42.throughput: 3.49e-12 (n 230)
* PROD/P43/F43.p: 2.46e-07 (n 18070)
* PROD/P43/F43.mdot: 3.41e-06 (n 18070)
* PROD/P43/F43.xO: 0.000162 (n 12510)
* PROD/P43/F43.valve_travel: 4.06e-05 (n 5560)
* PROD/P43/F43.u: 1.18e-06 (n 11120)
* PROD/P43/F43.setpoint_frac: 2.46e-07 (n 10425)
* PROD/P43/F43.overshoot: 4.05e-05 (n 2085)
* PROD/P43/F43.valve_travel_total: 9.14e-05 (n 695)
* REF/P43/F43.p: 6.59e-08 (n 5954)
* REF/P43/F43.mdot: 8.47e-07 (n 5954)
* REF/P43/F43.xO: 0.0011 (n 4122)
* REF/P43/F43.valve_travel: 1.99e-06 (n 1832)
* REF/P43/F43.u: 2.72e-07 (n 3664)
* REF/P43/F43.setpoint_frac: 6.59e-08 (n 3435)
* REF/P43/F43.overshoot: 4.34e-06 (n 687)
* REF/P43/F43.valve_travel_total: 9.61e-07 (n 229)
* PROD/P45/F45.P_dev: 0.0218 (n 373)
* PROD/P45/F45.mdot: 0.0565 (n 746)

Convergence ratio max|T1 - T2| / max|N - T2|:

* python: PROD/P42/F42.mdot 0.00566; PROD/P42/F42.p 0.00132; PROD/P42/F42.throughput 0.00815; PROD/P42/F42.u 0.00431; PROD/P42/F42.ucmd_end 0.00161; PROD/P42/F42.xO 0.00135; PROD/P43/F43.mdot 0.00275; PROD/P43/F43.overshoot 0.0164; PROD/P43/F43.p 0.00413; PROD/P43/F43.setpoint_frac 0.00413; PROD/P43/F43.u 0.0058; PROD/P43/F43.valve_travel 0.00654; PROD/P43/F43.valve_travel_total 0.0062; PROD/P43/F43.xO 0.22; PROD/P45/F45.P_dev 0.149; PROD/P45/F45.mdot 0.285; REF/P42/F42.mdot 0.045; REF/P42/F42.p 0.0478; REF/P42/F42.throughput 0.0184; REF/P42/F42.u 0.0346; REF/P42/F42.ucmd_end 0.025; REF/P42/F42.xO 0.138; REF/P43/F43.mdot 0.0345; REF/P43/F43.overshoot 0.0599; REF/P43/F43.p 0.0353; REF/P43/F43.setpoint_frac 0.0353; REF/P43/F43.u 0.0346; REF/P43/F43.valve_travel 0.0343; REF/P43/F43.valve_travel_total 0.0289; REF/P43/F43.xO 1
* rust: PROD/P42/F42.mdot 0.0013; PROD/P42/F42.p 0.00174; PROD/P42/F42.throughput 0.00582; PROD/P42/F42.u 0.00128; PROD/P42/F42.ucmd_end 0.00124; PROD/P42/F42.xO 0.00228; PROD/P43/F43.mdot 0.00125; PROD/P43/F43.overshoot 0.000407; PROD/P43/F43.p 0.000188; PROD/P43/F43.setpoint_frac 0.000188; PROD/P43/F43.u 0.000332; PROD/P43/F43.valve_travel 0.000506; PROD/P43/F43.valve_travel_total 0.00113; PROD/P43/F43.xO 0.431; PROD/P45/F45.P_dev 0.532; PROD/P45/F45.mdot 1.41; REF/P42/F42.mdot 0.0384; REF/P42/F42.p 0.045; REF/P42/F42.throughput 0.676; REF/P42/F42.u 0.0447; REF/P42/F42.ucmd_end 0.0447; REF/P42/F42.xO 0.041; REF/P43/F43.mdot 0.0232; REF/P43/F43.overshoot 0.044; REF/P43/F43.p 0.0232; REF/P43/F43.setpoint_frac 0.0232; REF/P43/F43.u 0.0232; REF/P43/F43.valve_travel 0.0234; REF/P43/F43.valve_travel_total 0.0239; REF/P43/F43.xO 8.51

Segment cascade diagnostics, relative N - T2 difference (ill-conditioning; scored through the primitive image):

* python: PROD/K_min/in_domain 9.93e+45 (n 838); PROD/K_over_K0_max/in_domain 3.59e-06 (n 838); PROD/p_stage_max_Pa/in_domain 1.13e+49 (n 838); PROD/p_inlet_max_Pa/in_domain 1.5e-06 (n 838); PROD/P_el_max_W/in_domain 2.02e+46 (n 838); PROD/T_comp_max_K/in_domain 2.29e+45 (n 838); PROD/K_min/out_of_domain +inf (n 4474); PROD/K_over_K0_max/out_of_domain 0.000184 (n 4474); PROD/p_stage_max_Pa/out_of_domain 1.61e+27 (n 4474); PROD/p_inlet_max_Pa/out_of_domain 1.72e-06 (n 4474); PROD/P_el_max_W/out_of_domain 1.72e+27 (n 4474); PROD/T_comp_max_K/out_of_domain 1.72e+27 (n 4474); REF/K_min/out_of_domain +inf (n 1524); REF/K_over_K0_max/out_of_domain 7.53e-05 (n 1524); REF/p_stage_max_Pa/out_of_domain 2.66e+24 (n 1524); REF/p_inlet_max_Pa/out_of_domain 1.16e-08 (n 1524); REF/P_el_max_W/out_of_domain 2.68e+24 (n 1524); REF/T_comp_max_K/out_of_domain 2.68e+24 (n 1524); REF/K_min/in_domain 9.82e-09 (n 228); REF/K_over_K0_max/in_domain 1.2e-08 (n 228); REF/p_stage_max_Pa/in_domain 2.95e-08 (n 228); REF/p_inlet_max_Pa/in_domain 1.38e-08 (n 228); REF/P_el_max_W/in_domain 7.99e-09 (n 228); REF/T_comp_max_K/in_domain 8.37e-10 (n 228)
* rust: PROD/K_min/in_domain 3.48e-07 (n 884); PROD/K_over_K0_max/in_domain 3.53e-10 (n 884); PROD/p_stage_max_Pa/in_domain 0.0118 (n 884); PROD/p_inlet_max_Pa/in_domain 1.2e-10 (n 884); PROD/P_el_max_W/in_domain 2.86e-07 (n 884); PROD/T_comp_max_K/in_domain 1.98e-08 (n 884); PROD/K_min/out_of_domain 1.27e+24 (n 4564); PROD/K_over_K0_max/out_of_domain 0.000153 (n 4564); PROD/p_stage_max_Pa/out_of_domain 4.94e+23 (n 4564); PROD/p_inlet_max_Pa/out_of_domain 1.83e-08 (n 4564); PROD/P_el_max_W/out_of_domain 3.56e+23 (n 4564); PROD/T_comp_max_K/out_of_domain 9.95e+22 (n 4564); REF/K_min/out_of_domain 15.5 (n 1573); REF/K_over_K0_max/out_of_domain 8.18e-06 (n 1573); REF/p_stage_max_Pa/out_of_domain 4.47 (n 1573); REF/p_inlet_max_Pa/out_of_domain 1.41e-10 (n 1573); REF/P_el_max_W/out_of_domain 4.78 (n 1573); REF/T_comp_max_K/out_of_domain 4.78 (n 1573); REF/K_min/in_domain 5.42e-11 (n 243); REF/K_over_K0_max/in_domain 4.75e-12 (n 243); REF/p_stage_max_Pa/in_domain 6.21e-11 (n 243); REF/p_inlet_max_Pa/in_domain 1.71e-12 (n 243); REF/P_el_max_W/in_domain 2.92e-13 (n 243); REF/T_comp_max_K/in_domain 2.69e-14 (n 243)

CONS-P-03 (mass residual) per run:

* python: PROD/P42/N max 1.91e-12 (above MASS_TOL 0); PROD/P42/T1 max 1.96e-12 (above MASS_TOL 0); PROD/P42/T2 max 1.91e-12 (above MASS_TOL 0); REF/P42/N max 5.07e-15 (above MASS_TOL 0); REF/P42/T1 max 5.4e-15 (above MASS_TOL 0); REF/P42/T2 max 5.01e-15 (above MASS_TOL 0); PROD/P43/N max 2.27e-14 (above MASS_TOL 0); PROD/P43/T1 max 2.85e-14 (above MASS_TOL 0); PROD/P43/T2 max 2.22e-14 (above MASS_TOL 0); REF/P43/N max 4e-15 (above MASS_TOL 0); REF/P43/T1 max 4.26e-15 (above MASS_TOL 0); REF/P43/T2 max 3.89e-15 (above MASS_TOL 0); PROD/P45/N max 6.84e-14 (above MASS_TOL 0); PROD/P45/T1 max 3.86e-13 (above MASS_TOL 0); PROD/P45/T2 max 6.57e-13 (above MASS_TOL 0)
* rust: PROD/P42/N max 1.92e-12 (above MASS_TOL 0); PROD/P42/T1 max 1.92e-12 (above MASS_TOL 0); PROD/P42/T2 max 1.92e-12 (above MASS_TOL 0); REF/P42/N max 5.32e-15 (above MASS_TOL 0); REF/P42/T1 max 5.13e-15 (above MASS_TOL 0); REF/P42/T2 max 5.12e-15 (above MASS_TOL 0); PROD/P43/N max 2.15e-14 (above MASS_TOL 0); PROD/P43/T1 max 2.15e-14 (above MASS_TOL 0); PROD/P43/T2 max 2.17e-14 (above MASS_TOL 0); REF/P43/N max 4e-15 (above MASS_TOL 0); REF/P43/T1 max 3.49e-15 (above MASS_TOL 0); REF/P43/T2 max 4e-15 (above MASS_TOL 0); PROD/P45/N max 1.65e-14 (above MASS_TOL 0); PROD/P45/T1 max 6.85e-14 (above MASS_TOL 0); PROD/P45/T2 max 3.47e-13 (above MASS_TOL 0)

## Excluded vectors and discrete differences

* python: 380 vectors excluded (refused / failed run); 1251 discrete N-vs-T2 leaf differences; 0 leaves with zero scale skipped.
* rust: 355 vectors excluded (refused / failed run); 399 discrete N-vs-T2 leaf differences; 0 leaves with zero scale skipped.

Statement: frozen before any held-out (scoring_master_seed) vector is generated or run; never edited after the scoring run.
