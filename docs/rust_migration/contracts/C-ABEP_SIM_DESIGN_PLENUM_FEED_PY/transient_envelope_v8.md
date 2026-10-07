# Plenum / feed transient envelope record v8 (REFINEMENT_FROZEN)

Contract `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_prereg_v8.json` sha256 `05192a43d1b5dadff79a0f82ebdf1fee71900a88820ec15a9d82a49eefad973b` (registered in `8943d26bde9a`). Generated from the JSON record next to this file.

* Procedure: transient_convergence_procedure_v8: eigen refinement (U stratum only, no transient run): per implementation e = (|x_N - x_T2| + |x_T1 - x_T2|) / rho for re_lead / im_lead, T1 / T2 the 34 / 68-digit Newton roots of the exact characteristic polynomial of the implementation's own f64 Jacobian block; E^lambda = max, no multiplier. Stable stratum: the v7 S envelopes reused.
* Seed 731905573; 704 U refinement vectors ({"P42": {"PROD": {"U": 192}, "REF": {"U": 64}}, "P43": {"PROD": {"U": 192}, "REF": {"U": 64}}, "P45": {"PROD": {"U": 192}}}), UNSAT equilibria {"P42": 2048, "P43": 2045, "P45": 4521}; inputs sha256 `f6a2ad07bd65c4d7...`.
* Python reference commit `0d8922cfe39b`; code at `56c2e08a346c`; rustc 1.94.1 (e408947bf 2026-03-25); Python 3.11.15, numpy 2.4.4.
* Stable stratum reused from `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/transient_envelope_v7.json` (sha256 `e4774be4927aebe9...`, `60df0d4`); REUSE_CHECK True.
* Checks: no missing envelope True; NON_VACUITY True; class disagreements (refinement, recorded) 0; NOT_CONVERGENT equilibria {}; largest relative Jacobian entry difference 3.92e-15.

## Draws

* P42 PROD: 5688 candidates, classes seen {"S": 4990, "U": 192, "R": 506}, accepted {"U": 192}
* P42 REF: 2229 candidates, classes seen {"S": 1935, "U": 64, "R": 230}, accepted {"U": 64}
* P43 PROD: 4983 candidates, classes seen {"S": 4341, "U": 192, "R": 450}, accepted {"U": 192}
* P43 REF: 2180 candidates, classes seen {"S": 1922, "U": 64, "R": 194}, accepted {"U": 64}
* P45 PROD: 6398 candidates, classes seen {"S": 4309, "U": 192, "R": 1897}, accepted {"U": 192}

## Non-vacuity (S rows reused from v7, family units; eigen rows relative to rho)

| stratum | level | entry | family | bound | comparison scale | ok |
|---|---|---|---|---|---|---|
| S | PROD | P42 | F42.p | 0.000178 | 0.209 | yes |
| S | PROD | P42 | F42.u | 0.000261 | 0.191 | yes |
| S | PROD | P42 | F42.mdot | 0.0005 | 0.45 | yes |
| S | PROD | P42 | F42.xO | 9.58e-06 | 0.00798 | yes |
| S | PROD | P42 | F42.ucmd_end | 0.000869 | 0.139 | yes |
| S | PROD | P42 | F42.throughput | 3.63e-09 | 1 | yes |
| S | PROD | P43 | F43.p | 4.08e-05 | 0.203 | yes |
| S | PROD | P43 | F43.setpoint_frac | 4.08e-05 | 0.08 | yes |
| S | PROD | P43 | F43.overshoot | 0.000322 | 0.0538 | yes |
| S | PROD | P43 | F43.mdot | 0.00114 | 0.45 | yes |
| S | PROD | P43 | F43.xO | 3.91e-06 | 0.00791 | yes |
| S | PROD | P43 | F43.u | 0.000379 | 0.199 | yes |
| S | PROD | P43 | F43.valve_travel | 0.0127 | 0.18 | yes |
| S | PROD | P43 | F43.valve_travel_total | 0.0321 | 0.793 | yes |
| S | PROD | P45 | F45.P_dev | 5.65e-06 | 5.29e-05 | yes |
| S | PROD | P45 | F45.mdot | 2.09e-05 | 0.251 | yes |
| S | REF | P42 | F42.p | 4.58e-07 | 0.212 | yes |
| S | REF | P42 | F42.u | 5.87e-07 | 0.201 | yes |
| S | REF | P42 | F42.mdot | 2.15e-06 | 0.45 | yes |
| S | REF | P42 | F42.xO | 1.46e-08 | 0.00796 | yes |
| S | REF | P42 | F42.ucmd_end | 5.51e-07 | 0.138 | yes |
| S | REF | P42 | F42.throughput | 2.5e-11 | 1 | yes |
| S | REF | P43 | F43.p | 1.49e-07 | 0.197 | yes |
| S | REF | P43 | F43.setpoint_frac | 1.49e-07 | 0.0724 | yes |
| S | REF | P43 | F43.overshoot | 1.36e-06 | 0.0688 | yes |
| S | REF | P43 | F43.mdot | 4.01e-06 | 0.467 | yes |
| S | REF | P43 | F43.xO | 1.31e-08 | 0.00841 | yes |
| S | REF | P43 | F43.u | 1.29e-06 | 0.217 | yes |
| S | REF | P43 | F43.valve_travel | 1.82e-05 | 0.22 | yes |
| S | REF | P43 | F43.valve_travel_total | 6.09e-05 | 0.891 | yes |
| U | pooled | P42 | L.re_lead | 1.77e-15 | 0.00205 | yes |
| U | pooled | P42 | L.im_lead | 2.62e-15 | 0.0175 | yes |
| U | pooled | P43 | L.re_lead | 1.9e-15 | 0.00385 | yes |
| U | pooled | P43 | L.im_lead | 3.71e-15 | 0.0221 | yes |
| U | pooled | P45 | L.re_lead | 2.29e-15 | 0.00326 | yes |
| U | pooled | P45 | L.im_lead | 4.51e-15 | 0.0237 | yes |

## Eigen envelopes

| implementation | entry | leaf | E | n leaves | argmax vector |
|---|---|---|---|---|---|
| python | P42 | re_lead | 9.47e-16 | 2048 | R42-PROD-U-050 |
| python | P42 | im_lead | 1.29e-15 | 2048 | R42-PROD-U-143 |
| python | P43 | re_lead | 7.95e-16 | 2045 | R43-REF-U-012 |
| python | P43 | im_lead | 1.62e-15 | 2045 | R43-PROD-U-113 |
| python | P45 | re_lead | 8.42e-16 | 4521 | R45-PROD-U-029 |
| python | P45 | im_lead | 1.84e-15 | 4521 | R45-PROD-U-044 |
| rust | P42 | re_lead | 7.65e-16 | 2048 | R42-PROD-U-001 |
| rust | P42 | im_lead | 1.19e-15 | 2048 | R42-PROD-U-066 |
| rust | P43 | re_lead | 7.51e-16 | 2045 | R43-PROD-U-104 |
| rust | P43 | im_lead | 1.32e-15 | 2045 | R43-PROD-U-114 |
| rust | P45 | re_lead | 1.06e-15 | 4521 | R45-PROD-U-081 |
| rust | P45 | im_lead | 1.43e-15 | 4521 | R45-PROD-U-178 |

Statement: frozen before any held-out (scoring_master_seed) vector is generated or run; never edited after the scoring run
