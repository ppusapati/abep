# Plenum / feed transient envelope record v7 (REFINEMENT_FROZEN)

Contract `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v7.json` sha256 `4f07529b88393291c737576a12d5dc3a2a401d919958fb5fd1c6ce8007e16083` (registered in `bd11e5c215aa`). Generated from the JSON record next to this file.

* Procedure: transient_convergence_procedure_v7 (A9.31 sec. 5 estimator per stratum): S: e = (|x_N - x_T2| + |x_T1 - x_T2|) / s_F per implementation, bound E_py^S + E_rust^S; U: E_rust^U (Rust estimator) + D_py^U (max |x_T1 - x_T2| / s_F of the Python reference) over leaves whose reference is convergent (rho < 1/2); no multiplier.
* Seed 731905563; 2752 refinement vectors, strata {"P42": {"PROD": {"S": 640, "U": 192}, "REF": {"S": 192, "U": 64}}, "P43": {"PROD": {"S": 640, "U": 192}, "REF": {"S": 192, "U": 64}}, "P45": {"PROD": {"S": 384, "U": 192}}}; inputs sha256 `e0ede5225970777e...`.
* Python reference commit `0d8922cfe39b`; code at `07ed905cc256`; rustc 1.94.1 (e408947bf 2026-03-25); Python 3.11.15, numpy 2.4.4, scipy 1.17.1.
* Checks: COMP-P-01 True; no missing envelope True; NON_VACUITY False; class disagreements (refinement, recorded) 0.

## Draws

* P42 PROD: 5349 candidates, classes seen {"S": 4656, "U": 192, "R": 501}, accepted {"S": 640, "U": 192}
* P42 REF: 2028 candidates, classes seen {"S": 1765, "U": 64, "R": 199}, accepted {"S": 192, "U": 64}
* P43 PROD: 6091 candidates, classes seen {"S": 5310, "U": 192, "R": 589}, accepted {"S": 640, "U": 192}
* P43 REF: 1911 candidates, classes seen {"S": 1655, "U": 64, "R": 192}, accepted {"S": 192, "U": 64}
* P45 PROD: 5985 candidates, classes seen {"S": 4033, "U": 192, "R": 1760}, accepted {"S": 384, "U": 192}

## Bounds and non-vacuity (family units; U F45.P_dev relative to the converged reference)

| stratum | level | entry | family | bound | comparison scale | ok | vectors |
|---|---|---|---|---|---|---|---|
| S | PROD | P42 | F42.p | 0.000178 | 0.209 | yes | 614 |
| S | PROD | P42 | F42.u | 0.000261 | 0.191 | yes | 614 |
| S | PROD | P42 | F42.mdot | 0.0005 | 0.45 | yes | 614 |
| S | PROD | P42 | F42.xO | 9.58e-06 | 0.00798 | yes | 614 |
| S | PROD | P42 | F42.ucmd_end | 0.000869 | 0.139 | yes | 614 |
| S | PROD | P42 | F42.throughput | 3.63e-09 | 1 | yes | 614 |
| S | PROD | P43 | F43.p | 4.08e-05 | 0.203 | yes | 640 |
| S | PROD | P43 | F43.setpoint_frac | 4.08e-05 | 0.08 | yes | 640 |
| S | PROD | P43 | F43.overshoot | 0.000322 | 0.0538 | yes | 640 |
| S | PROD | P43 | F43.mdot | 0.00114 | 0.45 | yes | 640 |
| S | PROD | P43 | F43.xO | 3.91e-06 | 0.00791 | yes | 640 |
| S | PROD | P43 | F43.u | 0.000379 | 0.199 | yes | 640 |
| S | PROD | P43 | F43.valve_travel | 0.0127 | 0.18 | yes | 640 |
| S | PROD | P43 | F43.valve_travel_total | 0.0321 | 0.793 | yes | 640 |
| S | PROD | P45 | F45.P_dev | 5.65e-06 | 5.29e-05 | yes | 384 |
| S | PROD | P45 | F45.mdot | 2.09e-05 | 0.251 | yes | 384 |
| S | REF | P42 | F42.p | 4.58e-07 | 0.212 | yes | 183 |
| S | REF | P42 | F42.u | 5.87e-07 | 0.201 | yes | 183 |
| S | REF | P42 | F42.mdot | 2.15e-06 | 0.45 | yes | 183 |
| S | REF | P42 | F42.xO | 1.46e-08 | 0.00796 | yes | 183 |
| S | REF | P42 | F42.ucmd_end | 5.51e-07 | 0.138 | yes | 183 |
| S | REF | P42 | F42.throughput | 2.5e-11 | 1 | yes | 183 |
| S | REF | P43 | F43.p | 1.49e-07 | 0.197 | yes | 192 |
| S | REF | P43 | F43.setpoint_frac | 1.49e-07 | 0.0724 | yes | 192 |
| S | REF | P43 | F43.overshoot | 1.36e-06 | 0.0688 | yes | 192 |
| S | REF | P43 | F43.mdot | 4.01e-06 | 0.467 | yes | 192 |
| S | REF | P43 | F43.xO | 1.31e-08 | 0.00841 | yes | 192 |
| S | REF | P43 | F43.u | 1.29e-06 | 0.217 | yes | 192 |
| S | REF | P43 | F43.valve_travel | 1.82e-05 | 0.22 | yes | 192 |
| S | REF | P43 | F43.valve_travel_total | 6.09e-05 | 0.891 | yes | 192 |
| U | PROD | P42 | F42.p | 0.00278 | 0.357 | yes | 192 |
| U | PROD | P42 | F42.u | 0.00292 | 0.681 | yes | 192 |
| U | PROD | P42 | F42.mdot | 0.0104 | 1.65 | yes | 192 |
| U | PROD | P42 | F42.xO | 9.88e-05 | 0.00322 | yes | 192 |
| U | PROD | P42 | F42.ucmd_end | 0.00717 | 0.981 | yes | 192 |
| U | PROD | P42 | F42.throughput | 1.21e-09 | 1 | yes | 192 |
| U | PROD | P43 | F43.p | 0.00105 | 0.366 | yes | 192 |
| U | PROD | P43 | F43.setpoint_frac | 0.00105 | 0.153 | yes | 192 |
| U | PROD | P43 | F43.overshoot | 7.43 | 1.98 | **NO** | 192 |
| U | PROD | P43 | F43.mdot | 0.0032 | 1.66 | yes | 192 |
| U | PROD | P43 | F43.xO | 1.13e-05 | 0.00156 | yes | 192 |
| U | PROD | P43 | F43.u | 0.000232 | 0.697 | yes | 192 |
| U | PROD | P43 | F43.valve_travel | 0.00681 | 4.22 | yes | 192 |
| U | PROD | P43 | F43.valve_travel_total | 0.00824 | 38.9 | yes | 192 |
| U | PROD | P45 | F45.P_dev | 98.8 | 1 | **NO** | 186 |
| U | PROD | P45 | F45.mdot | 1.05 | 0.868 | **NO** | 187 |
| U | REF | P42 | F42.p | 1.24e-05 | 0.367 | yes | 64 |
| U | REF | P42 | F42.u | 1.03e-05 | 0.637 | yes | 64 |
| U | REF | P42 | F42.mdot | 2.24e-05 | 1.47 | yes | 64 |
| U | REF | P42 | F42.xO | 1.27e-07 | 0.00225 | yes | 64 |
| U | REF | P42 | F42.ucmd_end | 2.35e-05 | 0.943 | yes | 64 |
| U | REF | P42 | F42.throughput | 6.42e-12 | 1 | yes | 64 |
| U | REF | P43 | F43.p | 8.92e-07 | 0.368 | yes | 64 |
| U | REF | P43 | F43.setpoint_frac | 8.92e-07 | 0.159 | yes | 64 |
| U | REF | P43 | F43.overshoot | 0.00187 | 1.04 | yes | 64 |
| U | REF | P43 | F43.mdot | 2.36e-06 | 1.45 | yes | 64 |
| U | REF | P43 | F43.xO | 1.54e-08 | 0.00171 | yes | 64 |
| U | REF | P43 | F43.u | 5.78e-07 | 0.721 | yes | 64 |
| U | REF | P43 | F43.valve_travel | 8.46e-06 | 6.34 | yes | 64 |
| U | REF | P43 | F43.valve_travel_total | 1.67e-05 | 40.6 | yes | 63 |

## Envelopes

| stratum | estimator | level | entry | family | E | n leaves | argmax vector |
|---|---|---|---|---|---|---|---|
| S | python | PROD | P42 | F42.p | 0.000165 | 741712 | R42-PROD-S-291 |
| S | python | PROD | P42 | F42.mdot | 0.000465 | 741712 | R42-PROD-S-291 |
| S | python | PROD | P42 | F42.u | 0.000237 | 741712 | R42-PROD-S-291 |
| S | python | PROD | P42 | F42.xO | 8.85e-06 | 741711 | R42-PROD-S-291 |
| S | python | PROD | P42 | F42.ucmd_end | 0.000796 | 4912 | R42-PROD-S-291 |
| S | python | PROD | P42 | F42.throughput | 3.63e-09 | 614 | R42-PROD-S-314 |
| S | python | PROD | P43 | F43.p | 3.57e-05 | 16640 | R43-PROD-S-002 |
| S | python | PROD | P43 | F43.mdot | 0.00105 | 16640 | R43-PROD-S-470 |
| S | python | PROD | P43 | F43.xO | 2.64e-06 | 11460 | R43-PROD-S-060 |
| S | python | PROD | P43 | F43.valve_travel | 0.0122 | 5120 | R43-PROD-S-470 |
| S | python | PROD | P43 | F43.u | 0.000363 | 10240 | R43-PROD-S-470 |
| S | python | PROD | P43 | F43.setpoint_frac | 3.57e-05 | 9600 | R43-PROD-S-002 |
| S | python | PROD | P43 | F43.overshoot | 0.000296 | 1920 | R43-PROD-S-039 |
| S | python | PROD | P43 | F43.valve_travel_total | 0.0299 | 640 | R43-PROD-S-470 |
| S | python | PROD | P45 | F45.P_dev | 5.56e-06 | 384 | R45-PROD-S-328 |
| S | python | PROD | P45 | F45.mdot | 2.06e-05 | 768 | R45-PROD-S-205 |
| S | python | REF | P42 | F42.p | 4.54e-07 | 221064 | R42-REF-S-164 |
| S | python | REF | P42 | F42.mdot | 2.13e-06 | 221064 | R42-REF-S-164 |
| S | python | REF | P42 | F42.u | 5.83e-07 | 221064 | R42-REF-S-164 |
| S | python | REF | P42 | F42.xO | 1.44e-08 | 221064 | R42-REF-S-049 |
| S | python | REF | P42 | F42.ucmd_end | 5.46e-07 | 1464 | R42-REF-S-164 |
| S | python | REF | P42 | F42.throughput | 2.47e-11 | 183 | R42-REF-S-019 |
| S | python | REF | P43 | F43.p | 1.46e-07 | 4992 | R43-REF-S-045 |
| S | python | REF | P43 | F43.mdot | 3.99e-06 | 4992 | R43-REF-S-017 |
| S | python | REF | P43 | F43.xO | 1.29e-08 | 3446 | R43-REF-S-153 |
| S | python | REF | P43 | F43.valve_travel | 1.81e-05 | 1536 | R43-REF-S-017 |
| S | python | REF | P43 | F43.u | 1.28e-06 | 3072 | R43-REF-S-017 |
| S | python | REF | P43 | F43.setpoint_frac | 1.46e-07 | 2880 | R43-REF-S-045 |
| S | python | REF | P43 | F43.overshoot | 1.35e-06 | 576 | R43-REF-S-170 |
| S | python | REF | P43 | F43.valve_travel_total | 6.07e-05 | 192 | R43-REF-S-017 |
| S | rust | PROD | P42 | F42.ucmd_end | 7.3e-05 | 5024 | R42-PROD-S-291 |
| S | rust | PROD | P42 | F42.mdot | 3.5e-05 | 758624 | R42-PROD-S-291 |
| S | rust | PROD | P42 | F42.p | 1.38e-05 | 758624 | R42-PROD-S-291 |
| S | rust | PROD | P42 | F42.u | 2.47e-05 | 758624 | R42-PROD-S-291 |
| S | rust | PROD | P42 | F42.xO | 7.29e-07 | 758547 | R42-PROD-S-291 |
| S | rust | PROD | P42 | F42.throughput | 1.17e-12 | 628 | R42-PROD-S-291 |
| S | rust | PROD | P43 | F43.p | 5.09e-06 | 16640 | R43-PROD-S-367 |
| S | rust | PROD | P43 | F43.setpoint_frac | 5.09e-06 | 9600 | R43-PROD-S-367 |
| S | rust | PROD | P43 | F43.mdot | 9.01e-05 | 16640 | R43-PROD-S-470 |
| S | rust | PROD | P43 | F43.u | 1.59e-05 | 10240 | R43-PROD-S-470 |
| S | rust | PROD | P43 | F43.valve_travel | 0.000514 | 5120 | R43-PROD-S-470 |
| S | rust | PROD | P43 | F43.xO | 1.27e-06 | 11460 | R43-PROD-S-065 |
| S | rust | PROD | P43 | F43.overshoot | 2.65e-05 | 1920 | R43-PROD-S-426 |
| S | rust | PROD | P43 | F43.valve_travel_total | 0.00219 | 640 | R43-PROD-S-470 |
| S | rust | PROD | P45 | F45.P_dev | 8.28e-08 | 384 | R45-PROD-S-294 |
| S | rust | PROD | P45 | F45.mdot | 2.53e-07 | 768 | R45-PROD-S-362 |
| S | rust | REF | P42 | F42.ucmd_end | 5.3e-09 | 1512 | R42-REF-S-067 |
| S | rust | REF | P42 | F42.mdot | 1.68e-08 | 228312 | R42-REF-S-164 |
| S | rust | REF | P42 | F42.p | 3.5e-09 | 228312 | R42-REF-S-164 |
| S | rust | REF | P42 | F42.u | 4.55e-09 | 228312 | R42-REF-S-164 |
| S | rust | REF | P42 | F42.xO | 2.67e-10 | 228309 | R42-REF-S-059 |
| S | rust | REF | P42 | F42.throughput | 2.86e-13 | 189 | R42-REF-S-056 |
| S | rust | REF | P43 | F43.p | 2.64e-09 | 4992 | R43-REF-S-119 |
| S | rust | REF | P43 | F43.setpoint_frac | 2.3e-09 | 2880 | R43-REF-S-045 |
| S | rust | REF | P43 | F43.mdot | 2e-08 | 4992 | R43-REF-S-017 |
| S | rust | REF | P43 | F43.u | 5.28e-09 | 3072 | R43-REF-S-017 |
| S | rust | REF | P43 | F43.valve_travel | 6.45e-08 | 1536 | R43-REF-S-017 |
| S | rust | REF | P43 | F43.xO | 1.65e-10 | 3446 | R43-REF-S-105 |
| S | rust | REF | P43 | F43.overshoot | 1.04e-08 | 576 | R43-REF-S-045 |
| S | rust | REF | P43 | F43.valve_travel_total | 1.72e-07 | 192 | R43-REF-S-017 |
| U | rust | PROD | P42 | F42.p | 0.00275 | 231335 | R42-PROD-U-015 |
| U | rust | PROD | P42 | F42.mdot | 0.0103 | 230796 | R42-PROD-U-140 |
| U | rust | PROD | P42 | F42.u | 0.00288 | 231070 | R42-PROD-U-140 |
| U | rust | PROD | P42 | F42.xO | 9.81e-05 | 230499 | R42-PROD-U-164 |
| U | rust | PROD | P42 | F42.ucmd_end | 0.00711 | 1530 | R42-PROD-U-140 |
| U | rust | PROD | P42 | F42.throughput | 1.19e-09 | 192 | R42-PROD-U-030 |
| U | rust | PROD | P43 | F43.p | 0.00105 | 4976 | R43-PROD-U-131 |
| U | rust | PROD | P43 | F43.mdot | 0.00314 | 4979 | R43-PROD-U-102 |
| U | rust | PROD | P43 | F43.xO | 1.1e-05 | 3422 | R43-PROD-U-131 |
| U | rust | PROD | P43 | F43.valve_travel | 0.00674 | 1446 | R43-PROD-U-131 |
| U | rust | PROD | P43 | F43.u | 0.000223 | 3064 | R43-PROD-U-090 |
| U | rust | PROD | P43 | F43.setpoint_frac | 0.00105 | 2677 | R43-PROD-U-131 |
| U | rust | PROD | P43 | F43.overshoot | 7.3 | 575 | R43-PROD-U-173 |
| U | rust | PROD | P43 | F43.valve_travel_total | 0.00811 | 192 | R43-PROD-U-090 |
| U | rust | PROD | P45 | F45.mdot | 0.874 | 365 | R45-PROD-U-119 |
| U | rust | PROD | P45 | F45.P_dev | 86.4 | 186 | R45-PROD-U-061 |
| U | rust | REF | P42 | F42.p | 1.09e-05 | 75738 | R42-REF-U-026 |
| U | rust | REF | P42 | F42.mdot | 1.89e-05 | 75487 | R42-REF-U-026 |
| U | rust | REF | P42 | F42.u | 8.46e-06 | 75496 | R42-REF-U-026 |
| U | rust | REF | P42 | F42.xO | 8.11e-08 | 75363 | R42-REF-U-026 |
| U | rust | REF | P42 | F42.ucmd_end | 1.91e-05 | 499 | R42-REF-U-026 |
| U | rust | REF | P42 | F42.throughput | 6.21e-12 | 64 | R42-REF-U-026 |
| U | rust | REF | P43 | F43.p | 1.06e-07 | 1646 | R43-REF-U-006 |
| U | rust | REF | P43 | F43.mdot | 3.87e-07 | 1634 | R43-REF-U-040 |
| U | rust | REF | P43 | F43.xO | 1.89e-09 | 1139 | R43-REF-U-030 |
| U | rust | REF | P43 | F43.valve_travel | 1.73e-06 | 494 | R43-REF-U-044 |
| U | rust | REF | P43 | F43.u | 1.02e-07 | 1002 | R43-REF-U-039 |
| U | rust | REF | P43 | F43.setpoint_frac | 1.06e-07 | 942 | R43-REF-U-006 |
| U | rust | REF | P43 | F43.overshoot | 0.000326 | 189 | R43-REF-U-011 |
| U | rust | REF | P43 | F43.valve_travel_total | 3.1e-06 | 63 | R43-REF-U-044 |
| U | python_T1_T2 | PROD | P42 | F42.p | 3.21e-05 | 231335 | R42-PROD-U-036 |
| U | python_T1_T2 | PROD | P42 | F42.mdot | 0.000137 | 230796 | R42-PROD-U-036 |
| U | python_T1_T2 | PROD | P42 | F42.u | 3.47e-05 | 231070 | R42-PROD-U-036 |
| U | python_T1_T2 | PROD | P42 | F42.xO | 7.1e-07 | 230499 | R42-PROD-U-065 |
| U | python_T1_T2 | PROD | P42 | F42.ucmd_end | 5.57e-05 | 1530 | R42-PROD-U-030 |
| U | python_T1_T2 | PROD | P42 | F42.throughput | 1.57e-11 | 192 | R42-PROD-U-030 |
| U | python_T1_T2 | PROD | P43 | F43.p | 6.41e-06 | 4976 | R43-PROD-U-178 |
| U | python_T1_T2 | PROD | P43 | F43.mdot | 6.06e-05 | 4979 | R43-PROD-U-189 |
| U | python_T1_T2 | PROD | P43 | F43.xO | 2.48e-07 | 3422 | R43-PROD-U-189 |
| U | python_T1_T2 | PROD | P43 | F43.valve_travel | 7.19e-05 | 1446 | R43-PROD-U-177 |
| U | python_T1_T2 | PROD | P43 | F43.u | 8.97e-06 | 3064 | R43-PROD-U-189 |
| U | python_T1_T2 | PROD | P43 | F43.setpoint_frac | 6.41e-06 | 2677 | R43-PROD-U-178 |
| U | python_T1_T2 | PROD | P43 | F43.overshoot | 0.13 | 575 | R43-PROD-U-173 |
| U | python_T1_T2 | PROD | P43 | F43.valve_travel_total | 0.000133 | 192 | R43-PROD-U-061 |
| U | python_T1_T2 | PROD | P45 | F45.mdot | 0.178 | 365 | R45-PROD-U-000 |
| U | python_T1_T2 | PROD | P45 | F45.P_dev | 12.4 | 186 | R45-PROD-U-045 |
| U | python_T1_T2 | REF | P42 | F42.p | 1.44e-06 | 75738 | R42-REF-U-046 |
| U | python_T1_T2 | REF | P42 | F42.mdot | 3.5e-06 | 75487 | R42-REF-U-046 |
| U | python_T1_T2 | REF | P42 | F42.u | 1.88e-06 | 75496 | R42-REF-U-036 |
| U | python_T1_T2 | REF | P42 | F42.xO | 4.61e-08 | 75363 | R42-REF-U-056 |
| U | python_T1_T2 | REF | P42 | F42.ucmd_end | 4.45e-06 | 499 | R42-REF-U-036 |
| U | python_T1_T2 | REF | P42 | F42.throughput | 2.11e-13 | 64 | R42-REF-U-005 |
| U | python_T1_T2 | REF | P43 | F43.p | 7.86e-07 | 1646 | R43-REF-U-058 |
| U | python_T1_T2 | REF | P43 | F43.mdot | 1.97e-06 | 1634 | R43-REF-U-000 |
| U | python_T1_T2 | REF | P43 | F43.xO | 1.35e-08 | 1139 | R43-REF-U-032 |
| U | python_T1_T2 | REF | P43 | F43.valve_travel | 6.73e-06 | 494 | R43-REF-U-024 |
| U | python_T1_T2 | REF | P43 | F43.u | 4.76e-07 | 1002 | R43-REF-U-024 |
| U | python_T1_T2 | REF | P43 | F43.setpoint_frac | 7.86e-07 | 942 | R43-REF-U-058 |
| U | python_T1_T2 | REF | P43 | F43.overshoot | 0.00154 | 189 | R43-REF-U-011 |
| U | python_T1_T2 | REF | P43 | F43.valve_travel_total | 1.36e-05 | 63 | R43-REF-U-024 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.p | 0.00687 | 231335 | R42-PROD-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.mdot | 0.0291 | 230796 | R42-PROD-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.u | 0.00735 | 231070 | R42-PROD-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.xO | 0.000325 | 230499 | R42-PROD-U-065 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.ucmd_end | 0.0274 | 1530 | R42-PROD-U-119 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P42 | F42.throughput | 3.8e-09 | 192 | R42-PROD-U-030 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.p | 0.00248 | 4976 | R43-PROD-U-179 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.mdot | 0.00565 | 4979 | R43-PROD-U-058 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.xO | 3.14e-05 | 3422 | R43-PROD-U-015 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.valve_travel | 0.0135 | 1446 | R43-PROD-U-143 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.u | 0.00166 | 3064 | R43-PROD-U-179 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.setpoint_frac | 0.00248 | 2677 | R43-PROD-U-179 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.overshoot | 25.2 | 575 | R43-PROD-U-158 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P43 | F43.valve_travel_total | 0.0365 | 192 | R43-PROD-U-061 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P45 | F45.mdot | 0.916 | 365 | R45-PROD-U-000 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | PROD | P45 | F45.P_dev | 6.33e+03 | 186 | R45-PROD-U-045 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.p | 3.48e-05 | 75738 | R42-REF-U-046 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.mdot | 8.45e-05 | 75487 | R42-REF-U-046 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.u | 5.87e-05 | 75496 | R42-REF-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.xO | 1.28e-06 | 75363 | R42-REF-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.ucmd_end | 0.000137 | 499 | R42-REF-U-036 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P42 | F42.throughput | 9.04e-12 | 64 | R42-REF-U-005 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.p | 2.12e-05 | 1646 | R43-REF-U-058 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.mdot | 5.92e-05 | 1634 | R43-REF-U-040 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.xO | 2.79e-07 | 1139 | R43-REF-U-032 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.valve_travel | 0.000129 | 494 | R43-REF-U-024 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.u | 9.03e-06 | 1002 | R43-REF-U-024 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.setpoint_frac | 2.12e-05 | 942 | R43-REF-U-058 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.overshoot | 0.0432 | 189 | R43-REF-U-011 |
| U | python_nominal (DIV-P-REF-01 evidence, not used) | REF | P43 | F43.valve_travel_total | 0.000273 | 63 | R43-REF-U-044 |

## Not-convergent reference leaves (U stratum)

* PROD/P42/F42.mdot: scored 230796, NOT_CONVERGENT_REFERENCE 1140
* PROD/P42/F42.p: scored 231335, NOT_CONVERGENT_REFERENCE 601
* PROD/P42/F42.throughput: scored 192, NOT_CONVERGENT_REFERENCE 0
* PROD/P42/F42.u: scored 231070, NOT_CONVERGENT_REFERENCE 866
* PROD/P42/F42.ucmd_end: scored 1530, NOT_CONVERGENT_REFERENCE 6
* PROD/P42/F42.xO: scored 230499, NOT_CONVERGENT_REFERENCE 1431
* PROD/P43/F43.mdot: scored 4979, NOT_CONVERGENT_REFERENCE 13
* PROD/P43/F43.overshoot: scored 575, NOT_CONVERGENT_REFERENCE 1
* PROD/P43/F43.p: scored 4976, NOT_CONVERGENT_REFERENCE 16
* PROD/P43/F43.setpoint_frac: scored 2677, NOT_CONVERGENT_REFERENCE 203
* PROD/P43/F43.u: scored 3064, NOT_CONVERGENT_REFERENCE 8
* PROD/P43/F43.valve_travel: scored 1446, NOT_CONVERGENT_REFERENCE 90
* PROD/P43/F43.valve_travel_total: scored 192, NOT_CONVERGENT_REFERENCE 0
* PROD/P43/F43.xO: scored 3422, NOT_CONVERGENT_REFERENCE 34
* PROD/P45/F45.P_dev: scored 186, NOT_CONVERGENT_REFERENCE 6
* PROD/P45/F45.mdot: scored 365, NOT_CONVERGENT_REFERENCE 19
* REF/P42/F42.mdot: scored 75487, NOT_CONVERGENT_REFERENCE 1825
* REF/P42/F42.p: scored 75738, NOT_CONVERGENT_REFERENCE 1574
* REF/P42/F42.throughput: scored 64, NOT_CONVERGENT_REFERENCE 0
* REF/P42/F42.u: scored 75496, NOT_CONVERGENT_REFERENCE 1816
* REF/P42/F42.ucmd_end: scored 499, NOT_CONVERGENT_REFERENCE 13
* REF/P42/F42.xO: scored 75363, NOT_CONVERGENT_REFERENCE 1812
* REF/P43/F43.mdot: scored 1634, NOT_CONVERGENT_REFERENCE 30
* REF/P43/F43.overshoot: scored 189, NOT_CONVERGENT_REFERENCE 3
* REF/P43/F43.p: scored 1646, NOT_CONVERGENT_REFERENCE 18
* REF/P43/F43.setpoint_frac: scored 942, NOT_CONVERGENT_REFERENCE 18
* REF/P43/F43.u: scored 1002, NOT_CONVERGENT_REFERENCE 22
* REF/P43/F43.valve_travel: scored 494, NOT_CONVERGENT_REFERENCE 18
* REF/P43/F43.valve_travel_total: scored 63, NOT_CONVERGENT_REFERENCE 1
* REF/P43/F43.xO: scored 1139, NOT_CONVERGENT_REFERENCE 13

## Closing-valve xO extrema (reported, not scored)

{
 "per_level": {
  "PROD": {
   "n": 120,
   "max_e": {
    "python": 0.00011771589954689965,
    "rust": 0.00048075772647415693
   },
   "max_cross_T2": 0.0007580760126988939,
   "argmax": {
    "vector": "R43-PROD-S-372",
    "path": "metrics/6/xO_min",
    "python_T2": 0.4399006205508398,
    "rust_T2": 0.4391425445381409
   }
  },
  "REF": {
   "n": 20,
   "max_e": {
    "python": 0.0024579516889345343,
    "rust": 0.0024579510114994263
   },
   "max_cross_T2": 0.0024579510236540925,
   "argmax": {
    "vector": "R43-REF-S-121",
    "path": "metrics/6/xO_min",
    "python_T2": 0.4493747458821647,
    "rust_T2": 0.4469167948585106
   }
  }
 },
 "known_property": "converged cross-implementation disagreement of an ill-posed observable (the sign of a rounding-level valve opening decides which samples have a defined xO); not resolved by choosing one value; v6 grid instance R43-REF-809 segment 6 xO_min: Rust 0.51716, Python 0.51607 (refinement_v6_p4243_note.md)"
}

Statement: frozen before any held-out (scoring_master_seed) vector is generated or run; never edited after the scoring run
