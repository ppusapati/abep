# DCR-DBF1-003 evaluation v1 (co-located RF match, P7)

Companion of `dcr003_evaluation_v1.json` (the JSON governs). Preregistration `docs/baseline/DCR-003/dcr003_eval_prereg_v1.json` (sha256 `13b27c04265660c08a457bab0d03d86d1798028f5672fda008d19bc455f77b9b`, lock `57f94f7c5c93fe0ddbd2eb67813a6f868d9317beaeb8b9cefae575d0e53f9580`); P7 preregistration sha256 `5666c528486f8cb7935863b3826c66e60271242637b31826468adde09394ecba`; load inputs `docs/closure/thermal/thermal_load_inputs_v2.json` (sha256 `c748b8fe394b503c2791f88b9113a2dd500cc5942cf38f0771ac1f91c886d12f`); Rust commit `1849fef3d1e71f8f83af7eb84882bcfe2117852e`. Model NP-THERMAL-CATHODELESS 2.0.0, PARAMETRIC, NOT_VALIDATED.

**Selected route: R-1** (DCR-DBF1-003 WITHDRAWN (no DBF-1 value changes)). **P7 closure state: REFERENCE/ICD DEPENDENT.**

## R-1: isolated co-located match with its own radiator (no DCR)

HOT corner G_iso 0.04 W/K, G_lead 0.025 W/K, Q_match_frac 0.06. Selected A_MA **0.15 m^2** (FEASIBLE_CONFIRMED); radiator mass 0.600 kg at 4 kg/m^2, standoffs 0.012 kg. Criteria: {"R1-a":true,"R1-b":true,"R1-c":true,"R1-d":"reported (power_penalty_vs_P6)"}. Admissible: **true**.

| A_MA m^2 | feasible | N_MATCH TC1 degC | N_MATCH TC3 degC | N_MATCH min margin K |
|---|---|---|---|---|
| 0.02 | false | 123.8 | 187.0 | -127.0 |
| 0.05 | false | 65.1 | 111.3 | -51.3 |
| 0.08 | false | 37.6 | 76.7 | -16.7 |
| 0.1 | false | 25.4 | 61.5 | -1.5 |
| 0.12 | true | 15.8 | 49.5 | 10.5 |
| 0.15 | true | 4.6 | 35.6 | 24.4 |
| 0.2 | true | -8.9 | 18.8 | 41.2 |
| 0.25 | true | -18.6 | 6.7 | 53.3 |
| 0.3 | true | -26.0 | -2.6 | 62.6 |
| 0.4 | true | -36.7 | -16.2 | 76.2 |

Confirmations (TC2 / TC4): [{"A_MA_m2":0.12,"TC2_N_MATCH_C":34.129616084915426,"TC4_N_MATCH_C":65.41899847171652,"confirmed":false},{"A_MA_m2":0.15,"TC2_N_MATCH_C":26.317598768908056,"TC4_N_MATCH_C":54.41727779377459,"confirmed":true}]

### Nodes at the selected design (HOT corner, governing hot cases TC1-TC4)

| node | class | ceiling degC | T max hot degC | margin K | verdict | v2 verdict | v2 T degC | dT vs v2 K |
|---|---|---|---|---|---|---|---|---|
| H1_ANODE | REQUIREMENT_ONLY | - | 512.7 | - | REQUIREMENT | REQUIREMENT | 512.0 | 0.7 |
| H1_BACKPLATE | NECESSARY_CEILING | 704.0 | 339.5 | 364.5 | PASS | PASS | 338.7 | 0.8 |
| H1_COIL_IN | SOURCED_GUIDE | 487.8 | 446.0 | 41.8 | PASS | PASS | 445.6 | 0.4 |
| H1_COIL_OUT | SOURCED_GUIDE | 487.8 | 256.2 | 231.6 | PASS | PASS | 255.9 | 0.3 |
| H1_COIL_TRIM | SOURCED_GUIDE | 487.8 | 339.5 | 148.3 | PASS | PASS | 338.7 | 0.8 |
| H1_POLE_IN | NECESSARY_CEILING | 888.0 | 432.5 | 455.5 | PASS | PASS | 432.1 | 0.4 |
| H1_POLE_OUT | NECESSARY_CEILING | 704.0 | 236.9 | 467.1 | PASS | PASS | 236.6 | 0.2 |
| H1_WALL_IN | SOURCED_GUIDE | 850.0 | 454.8 | 395.2 | PASS | PASS | 454.4 | 0.4 |
| H1_WALL_OUT | SOURCED_GUIDE | 850.0 | 433.8 | 416.2 | PASS | PASS | 433.5 | 0.4 |
| N_ANTENNA | REQUIREMENT_ONLY | - | 592.0 | - | REQUIREMENT | REQUIREMENT | 612.2 | -20.2 |
| N_COLLECTOR | REQUIREMENT_ONLY | - | 506.8 | - | REQUIREMENT | REQUIREMENT | 510.1 | -3.2 |
| N_HOUSING | REQUIREMENT_ONLY | - | 249.2 | - | REQUIREMENT | REQUIREMENT | 251.7 | -2.5 |
| N_MATCH | DERATED_ELECTRONICS | 60.0 | 54.4 | 5.6 | PASS | FAIL | 183.5 | -129.0 |
| N_MOUNT | REQUIREMENT_ONLY | - | 214.1 | - | REQUIREMENT | REQUIREMENT | 210.9 | 3.2 |
| N_VESSEL | ASSUMED_FROM_MEMORY | 440.0 | 361.0 | 79.0 | PASS | PASS | 366.1 | -5.2 |
| R_HALL | REQUIREMENT_ONLY | - | 281.3 | - | REQUIREMENT | REQUIREMENT | 280.8 | 0.5 |

### Cold (worst of the four COLD corners)

TC5 N_MATCH T_min -40.5 degC, heater 11.5 W; TC6 N_MATCH T_min -80.1 degC, heater 17.2 W.

### Power penalty against P6

- lead loss, R_A 1 Ohm: dP_fwd 1.9 W, dP_bus 2.9 W, dP_d,max -2.5 W
- lead loss, R_A 0.5 Ohm: dP_fwd 3.9 W, dP_bus 5.9 W, dP_d,max -5.0 W
- operating heater 11.5 W (bus 12.6 W) against the P6 thermal_control slot 4.0 W: excess 8.7 W (dP_d,max -7.4 W)
- total, conservative lead + heater excess: dP_bus 14.5 W, dP_d,max -12.4 W, against the P-NOM margin to 1,500 W of 150.0 W
- non-operating survival heater 17.2 W

AL-QMATCH (TC3, HOT corner): Q_match_frac <= 0.107. T_SC sensitivity changes a verdict: false. Q into the spacecraft (max hot) 90.5 W (v2 89.6 W).

## R-2: match at the RF generator (DCR, DBF-1.1)

Criteria: {"R2-a":true,"R2-b":false,"R2-c":false}. Admissible: **false**.

| node | class | ceiling degC | T max hot degC | margin K | verdict | v2 verdict | v2 T degC | dT vs v2 K |
|---|---|---|---|---|---|---|---|---|
| H1_ANODE | REQUIREMENT_ONLY | - | 513.8 | - | REQUIREMENT | REQUIREMENT | 512.0 | 1.7 |
| H1_BACKPLATE | NECESSARY_CEILING | 704.0 | 340.6 | 363.4 | PASS | PASS | 338.7 | 1.9 |
| H1_COIL_IN | SOURCED_GUIDE | 487.8 | 446.9 | 40.9 | PASS | PASS | 445.6 | 1.3 |
| H1_COIL_OUT | SOURCED_GUIDE | 487.8 | 256.8 | 231.0 | PASS | PASS | 255.9 | 0.9 |
| H1_COIL_TRIM | SOURCED_GUIDE | 487.8 | 340.6 | 147.2 | PASS | PASS | 338.7 | 1.9 |
| H1_POLE_IN | NECESSARY_CEILING | 888.0 | 433.4 | 454.6 | PASS | PASS | 432.1 | 1.3 |
| H1_POLE_OUT | NECESSARY_CEILING | 704.0 | 237.5 | 466.5 | PASS | PASS | 236.6 | 0.8 |
| H1_WALL_IN | SOURCED_GUIDE | 850.0 | 455.6 | 394.4 | PASS | PASS | 454.4 | 1.2 |
| H1_WALL_OUT | SOURCED_GUIDE | 850.0 | 434.6 | 415.4 | PASS | PASS | 433.5 | 1.1 |
| N_ANTENNA | REQUIREMENT_ONLY | - | 613.2 | - | REQUIREMENT | REQUIREMENT | 612.2 | 1.0 |
| N_COLLECTOR | REQUIREMENT_ONLY | - | 510.7 | - | REQUIREMENT | REQUIREMENT | 510.1 | 0.6 |
| N_HOUSING | REQUIREMENT_ONLY | - | 253.9 | - | REQUIREMENT | REQUIREMENT | 251.7 | 2.2 |
| N_MOUNT | REQUIREMENT_ONLY | - | 221.4 | - | REQUIREMENT | REQUIREMENT | 210.9 | 10.5 |
| N_VESSEL | ASSUMED_FROM_MEMORY | 440.0 | 367.3 | 72.7 | PASS | PASS | 366.1 | 1.2 |
| R_HALL | REQUIREMENT_ONLY | - | 282.1 | - | REQUIREMENT | REQUIREMENT | 280.8 | 1.3 |

Antenna reference L_A 1.926 uH, X_A 164.1 Ohm (Wheeler, P7 antenna geometry, assumed).

| corner | R_A Ohm | X_A Ohm | matched loss dB | VSWR | eta_line | P_fwd,R2 anchor W | dP_bus anchor W | dP_d,max anchor W | P_fwd,R2 at 500 W W | RF unit Q hot anchor W |
|---|---|---|---|---|---|---|---|---|---|---|
| CONSERVATIVE | 0.5 | 213.3 | 0.200 | 1919.7 | 0.022 | 9044.1 | 13366.2 | -11371.0 | 22610.2 | 17866.2 |
| FAVOURABLE | 5.0 | 114.8 | 0.010 | 62.8 | 0.933 | 214.5 | 21.9 | -18.6 | 536.2 | 206.9 |
| REFERENCE | 1.0 | 164.1 | 0.050 | 588.4 | 0.228 | 877.5 | 1023.8 | -871.0 | 2193.6 | 1532.9 |

Q into the spacecraft (max hot) 91.6 W.

## Selection

R-1 if R-1 is admissible (DCR-DBF1-003 is then WITHDRAWN: no DBF-1 value changes; the match isolation, radiator and lead become registered design-completion values for a P7 load-input / network version); otherwise R-2 if R-2 is admissible (DCR-DBF1-003 proceeds as DBF-1.1 for the coordinator); otherwise BLOCKED with the residual (the N_MATCH shortfall of R-1 and the failed R-2 criterion with its quantity)

Route **R-1**: DCR-DBF1-003 WITHDRAWN (no DBF-1 value changes). P7 closure state **REFERENCE/ICD DEPENDENT**.
