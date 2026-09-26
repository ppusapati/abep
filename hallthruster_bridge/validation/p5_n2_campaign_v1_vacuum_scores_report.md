# P5-N2 no-retuning validation campaign: pre-registered result

Pre-registration: `prereg/p5_n2_validation_criteria_v1.json`. Records scored: 1080.

## 1. Candidate verdicts

| candidate | vacuum (admission) | facility (non-gating) |
|---|---|---|
| sgb-screen-01 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-02 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-03 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-04 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-05 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-06 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-07 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-08 | **INCONCLUSIVE / NOT ELIGIBLE** | — |
| sgb-screen-09 | **INCONCLUSIVE / NOT ELIGIBLE** | — |

## 2. Global layer-1 member verdicts (vacuum)

| candidate | L32-anode\|1p6kW\|A | L32-anode\|1p6kW\|B | L32-anode\|3p0kW\|A | L32-anode\|3p0kW\|B | L32-exit\|1p6kW\|A | L32-exit\|1p6kW\|B | L32-exit\|3p0kW\|A | L32-exit\|3p0kW\|B | L38-hist\|1p6kW\|A | L38-hist\|1p6kW\|B | L38-hist\|3p0kW\|A | L38-hist\|3p0kW\|B |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sgb-screen-01 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-02 | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-03 | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-04 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-05 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-06 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-07 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-08 | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL |
| sgb-screen-09 | FAIL | FAIL | FAIL | FAIL | INCONCLUSIVE | INCONCLUSIVE | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |

## 3. Run status and failure reasons

Counts are per (run, divergence reading); CURRENT and SUSTAINMENT do not depend on the reading.

**vacuum**: FAIL_VALIDATION 700, OUT_OF_DOMAIN 1428, PASS 32; reasons: CURRENT 552, SUSTAINMENT 260, THRUST 308

| vacuum by candidate | PASS | FAIL_VALIDATION | OUT_OF_DOMAIN | NUMERICAL_FAILURE | CURRENT | THRUST | SUSTAINMENT |
|---|---|---|---|---|---|---|---|
| sgb-screen-01 | 14 | 86 | 140 | 0 | 82 | 42 | 8 |
| sgb-screen-02 | 0 | 64 | 176 | 0 | 64 | 32 | 24 |
| sgb-screen-03 | 0 | 42 | 198 | 0 | 42 | 18 | 0 |
| sgb-screen-04 | 0 | 78 | 162 | 0 | 68 | 52 | 18 |
| sgb-screen-05 | 0 | 130 | 110 | 0 | 82 | 64 | 74 |
| sgb-screen-06 | 2 | 112 | 126 | 0 | 88 | 44 | 30 |
| sgb-screen-07 | 0 | 84 | 156 | 0 | 38 | 13 | 54 |
| sgb-screen-08 | 12 | 14 | 214 | 0 | 14 | 14 | 0 |
| sgb-screen-09 | 4 | 90 | 146 | 0 | 74 | 29 | 52 |

| vacuum by chemistry | PASS | FAIL_VALIDATION | OUT_OF_DOMAIN | NUMERICAL_FAILURE | CURRENT | THRUST | SUSTAINMENT |
|---|---|---|---|---|---|---|---|
| n2_n.toml | 11 | 181 | 348 | 0 | 146 | 78 | 64 |
| n2_n_di_lower.toml | 9 | 179 | 352 | 0 | 140 | 79 | 62 |
| n2_n_di_lower_nel_wang.toml | 7 | 175 | 358 | 0 | 136 | 79 | 70 |
| n2_n_nel_wang.toml | 5 | 165 | 370 | 0 | 130 | 72 | 64 |

| vacuum by point | PASS | FAIL_VALIDATION | OUT_OF_DOMAIN | NUMERICAL_FAILURE | CURRENT | THRUST | SUSTAINMENT |
|---|---|---|---|---|---|---|---|
| N1 | 4 | 60 | 368 | 0 | 58 | 60 | 16 |
| N2 | 0 | 110 | 322 | 0 | 102 | 106 | 30 |
| N3 | 4 | 156 | 272 | 0 | 112 | 142 | 62 |
| N4 | 14 | 184 | 234 | 0 | 136 | 0 | 76 |
| N5 | 10 | 190 | 232 | 0 | 144 | 0 | 76 |

## 4. Signed residuals (vacuum)

dI = (I_sim - I_target)/I_target; dT = T_axial,sim - T_target [mN] (reading A and B listed separately). Numerically valid runs of every status; the OUT_OF_DOMAIN share is shown.

| point | dI: n / min / median / max | OOD share | dT reading A: min / median / max | dT reading B: min / median / max |
|---|---|---|---|---|
| N1 | 216 / -0.653 / -0.037 / +0.756 | 0.85 | -37.77 / -3.54 / +40.04 | -37.52 / -2.91 / +41.15 |
| N2 | 216 / -0.463 / +0.242 / +0.762 | 0.75 | -33.86 / +10.50 / +42.41 | -31.01 / +16.57 / +50.79 |
| N3 | 216 / -0.328 / +0.265 / +0.928 | 0.63 | -26.20 / +12.81 / +56.15 | -19.84 / +23.63 / +71.92 |
| N4 | 216 / -0.251 / +0.286 / +0.933 | 0.54 | — | — |
| N5 | 216 / -0.267 / +0.305 / +0.954 | 0.54 | — | — |

Per candidate, median signed dI by point (reading-independent) and median dT (A / B) at N1-N3:

| candidate | dI N1 | dI N2 | dI N3 | dI N4 | dI N5 | dT N1 A/B | dT N2 A/B | dT N3 A/B |
|---|---|---|---|---|---|---|---|---|
| sgb-screen-01 | +0.133 | +0.435 | +0.483 | +0.511 | +0.558 | +5.9 / +6.7 | +20.4 / +27.2 | +26.3 / +38.7 |
| sgb-screen-02 | +0.205 | +0.347 | +0.376 | +0.390 | +0.424 | +5.8 / +6.6 | +14.7 / +21.1 | +14.2 / +25.1 |
| sgb-screen-03 | +0.206 | +0.460 | +0.596 | +0.623 | +0.642 | +10.9 / +11.7 | +22.5 / +29.5 | +37.4 / +51.0 |
| sgb-screen-04 | +0.407 | +0.423 | +0.620 | +0.589 | +0.545 | +16.0 / +16.8 | +16.5 / +23.0 | +39.0 / +52.8 |
| sgb-screen-05 | -0.140 | +0.264 | +0.114 | +0.120 | +0.288 | -9.8 / -9.3 | +11.2 / +17.4 | -3.2 / +5.8 |
| sgb-screen-06 | -0.078 | +0.183 | +0.138 | +0.160 | +0.163 | -4.5 / -3.9 | +9.1 / +15.1 | +4.9 / +14.9 |
| sgb-screen-07 | -0.098 | +0.013 | +0.088 | +0.102 | +0.134 | -3.5 / -2.9 | +1.1 / +6.5 | +2.6 / +12.2 |
| sgb-screen-08 | -0.394 | -0.255 | -0.065 | -0.036 | -0.003 | -18.7 / -18.3 | -16.3 / -12.2 | -3.5 / +5.5 |
| sgb-screen-09 | -0.391 | -0.102 | -0.022 | -0.003 | -0.056 | -20.8 / -20.4 | -5.4 / -0.5 | -3.5 / +5.5 |

## 5. E×B diagnostic (non-gating)

V_a,model = m u²/(2Ze) at the model outlet vs the E×B value at 1 m; residuals are diagnostic only.

| point | species | dV_a [V]: min / median / max | dV_a/11.6 V median | outlet flux fraction median |
|---|---|---|---|---|
| N1 | N2+ | -56.9 / -30.2 / -4.6 | -2.60 | 0.520 |
| N1 | N+ | -140.6 / -123.9 / -84.9 | -10.68 | 0.469 |
| N2 | N2+ | -57.7 / -14.7 / +21.8 | -1.27 | 0.468 |
| N2 | N+ | -154.5 / -140.2 / -102.6 | -12.08 | 0.517 |
| N3 | N2+ | -34.6 / +8.0 / +47.1 | +0.69 | 0.437 |
| N3 | N+ | -172.0 / -150.9 / -95.7 | -13.01 | 0.543 |

Species ordering V_a(N+) > V_a(N2+) holds in 0 of 648 runs (measured: holds at N1-N3).
