# P7 thermal closure v1 (DBF-1, frozen topology)

Companion of `thermal_closure_v1.json` (the JSON governs). Model NP-THERMAL-CATHODELESS 2.0.0, case class PARAMETRIC (label PARAMETRIC_NOT_A_PREDICTION), validation status NOT_VALIDATED. Preregistration `docs/closure/thermal/thermal_cases_prereg_v1.json` (sha256 `5666c528486f8cb7935863b3826c66e60271242637b31826468adde09394ecba`); load inputs `docs/closure/thermal/thermal_load_inputs_v1.json` (sha256 `c87cdb2fc913e667760d5c9bce88c9cce5cba237689e0ac93dbf101cd9dd4b41`); Rust commit `ef88081f56a15744d7ba5f292bc8118763ac5e71`.

**Closure state: DCR REQUIRED**

Selected design levers: R_HALL area 0.02 m^2, back-plate doubler 2.0 W/K (FEASIBLE_CONFIRMED); R_HALL mass at 4 kg/m^2: 0.1 kg.

## Nodes (governing hot cases TC1-TC4 with 1.2 x heat loads; cold TC5 / TC6)

| node | limit class | limit degC | ceiling (limit - 50 K) | T max hot degC | margin K | verdict | required capability degC | coating capability degC | T min cold op / non-op degC |
|---|---|---|---|---|---|---|---|---|---|
| H1_ANODE | REQUIREMENT_ONLY | - | - | 561.3 | - | REQUIREMENT | 611.3 | - | 72.0 / -18.5 |
| H1_BACKPLATE | NECESSARY_CEILING | 754.0 | 704.0 | 364.4 | 339.6 | PASS | - | - | 60.5 / -18.5 |
| H1_COIL_IN | SOURCED_GUIDE | 537.8 | 487.8 | 475.3 | 12.5 | PASS | - | - | 70.0 / -17.8 |
| H1_COIL_OUT | SOURCED_GUIDE | 537.8 | 487.8 | 273.5 | 214.3 | PASS | - | - | 39.4 / -25.6 |
| H1_COIL_TRIM | SOURCED_GUIDE | 537.8 | 487.8 | 364.4 | 123.4 | PASS | - | - | 60.6 / -18.5 |
| H1_POLE_IN | NECESSARY_CEILING | 938.0 | 888.0 | 460.9 | 427.1 | PASS | - | 510.9 | 69.3 / -17.8 |
| H1_POLE_OUT | NECESSARY_CEILING | 754.0 | 704.0 | 251.4 | 452.6 | PASS | - | 301.4 | 38.7 / -25.6 |
| H1_WALL_IN | SOURCED_GUIDE | 900.0 | 850.0 | 487.0 | 363.0 | PASS | - | - | 96.0 / -18.9 |
| H1_WALL_OUT | SOURCED_GUIDE | 900.0 | 850.0 | 464.9 | 385.1 | PASS | - | - | 90.8 / -19.1 |
| N_ANTENNA | REQUIREMENT_ONLY | - | - | 612.2 | - | REQUIREMENT | 662.2 | - | 253.7 / -43.8 |
| N_COLLECTOR | REQUIREMENT_ONLY | - | - | 510.1 | - | REQUIREMENT | 560.1 | - | 181.1 / -47.3 |
| N_HOUSING | REQUIREMENT_ONLY | - | - | 251.7 | - | REQUIREMENT | 301.7 | 301.7 | 98.9 / -43.8 |
| N_MATCH | DERATED_ELECTRONICS | 110.0 | 60.0 | 183.5 | -123.5 | FAIL | - | 233.5 | 70.8 / -34.2 |
| N_MOUNT | REQUIREMENT_ONLY | - | - | 210.9 | - | REQUIREMENT | 260.9 | 260.9 | 78.0 / -35.7 |
| N_VESSEL | ASSUMED_FROM_MEMORY | 490.0 | 440.0 | 366.1 | 73.9 | PASS | - | - | 136.4 / -46.4 |
| R_HALL | REQUIREMENT_ONLY | - | - | 298.8 | - | REQUIREMENT | 348.8 | 348.8 | 53.0 / -18.7 |

## Per case (T max / T min, degC)

| node | S1-BAND-1350-BSTAR | TC1-HOT-H-BSTAR | TC2-HOT-H-B0 | TC3-HOT-I-BSTAR | TC4-HOT-I-B0 | TC5-COLD-OP-B0 | TC6-COLD-NONOP-B0 | TC7-HOT-H-BSTAR-XE |
|---|---|---|---|---|---|---|---|---|
| H1_ANODE | 659.1 / 659.1 | 560.3 / 560.3 | 561.3 / 559.1 | 419.3 / 419.3 | 420.4 / 417.9 | 75.2 / 72.0 | -15.2 / -18.5 | 560.3 / 560.3 |
| H1_BACKPLATE | 413.5 / 413.5 | 363.3 / 363.3 | 364.4 / 362.0 | 292.9 / 292.9 | 294.1 / 291.4 | 63.8 / 60.5 | -15.2 / -18.5 | 363.3 / 363.3 |
| H1_COIL_IN | 532.8 / 532.8 | 474.7 / 474.7 | 475.3 / 473.8 | 394.3 / 394.3 | 394.9 / 393.1 | 71.7 / 70.0 | -16.2 / -17.8 | 474.7 / 474.7 |
| H1_COIL_OUT | 308.5 / 308.5 | 273.1 / 273.1 | 273.5 / 270.8 | 228.0 / 228.0 | 228.2 / 225.3 | 42.7 / 39.4 | -22.1 / -25.6 | 273.1 / 273.1 |
| H1_COIL_TRIM | 413.5 / 413.5 | 363.3 / 363.3 | 364.4 / 362.0 | 292.9 / 292.9 | 294.1 / 291.4 | 63.8 / 60.6 | -15.2 / -18.5 | 363.3 / 363.3 |
| H1_POLE_IN | 516.2 / 516.2 | 460.3 / 460.3 | 460.9 / 459.3 | 382.7 / 382.7 | 383.4 / 381.6 | 71.1 / 69.3 | -16.2 / -17.8 | 460.3 / 460.3 |
| H1_POLE_OUT | 280.1 / 280.1 | 251.1 / 251.1 | 251.4 / 248.8 | 213.1 / 213.1 | 213.3 / 210.3 | 42.1 / 38.7 | -22.1 / -25.6 | 251.1 / 251.1 |
| H1_WALL_IN | 549.5 / 549.5 | 486.6 / 486.6 | 487.0 / 485.7 | 393.0 / 393.0 | 393.4 / 391.8 | 98.2 / 96.0 | -16.6 / -18.9 | 486.6 / 486.6 |
| H1_WALL_OUT | 525.2 / 525.2 | 464.5 / 464.5 | 464.9 / 463.5 | 373.9 / 373.9 | 374.4 / 372.6 | 93.2 / 90.8 | -16.7 / -19.1 | 464.5 / 464.5 |
| N_ANTENNA | 414.5 / 414.5 | 401.3 / 401.3 | 401.6 / 399.5 | 611.9 / 611.9 | 612.2 / 611.0 | 256.4 / 253.7 | -39.1 / -43.8 | 401.3 / 401.3 |
| N_COLLECTOR | 492.7 / 492.7 | 451.6 / 451.6 | 451.7 / 450.8 | 509.9 / 509.9 | 510.1 / 509.4 | 183.2 / 181.1 | -43.4 / -47.3 | 451.6 / 451.6 |
| N_HOUSING | 219.9 / 219.9 | 205.5 / 205.5 | 206.1 / 203.0 | 251.2 / 251.2 | 251.7 / 249.2 | 102.4 / 98.9 | -38.8 / -43.8 | 205.5 / 205.5 |
| N_MATCH | 155.4 / 155.4 | 147.2 / 147.2 | 150.2 / 145.2 | 180.6 / 180.6 | 183.5 / 178.8 | 75.9 / 70.8 | -28.9 / -34.2 | 147.2 / 147.2 |
| N_MOUNT | 200.1 / 200.1 | 185.9 / 185.9 | 187.0 / 184.0 | 209.8 / 209.8 | 210.9 / 208.3 | 81.5 / 78.0 | -31.2 / -35.7 | 185.9 / 185.9 |
| N_VESSEL | 320.0 / 320.0 | 297.8 / 297.8 | 298.1 / 296.3 | 365.9 / 365.9 | 366.1 / 364.8 | 139.0 / 136.4 | -42.4 / -46.4 | 297.8 / 297.8 |
| R_HALL | 331.0 / 331.0 | 296.9 / 296.9 | 298.8 / 295.6 | 246.2 / 246.2 | 248.3 / 244.6 | 57.6 / 53.0 | -14.0 / -18.7 | 296.9 / 296.9 |
| run status | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED |
| Q into spacecraft W | 111.8 | 96.9 | 97.3 | 80.2 | 80.6 | 18.4 | -16.0 | 96.9 |

## Allowables (bisection at the selected design, 1.2 x loads)

| allowable | value |
|---|---|
| AL-PD/H1_BACKPLATE | P_d_allowable_W = 3000.0 |
| AL-PD/H1_COIL_IN | P_d_allowable_W = 1113.7 |
| AL-PD/H1_COIL_OUT | P_d_allowable_W = 3000.0 |
| AL-PD/H1_COIL_TRIM | P_d_allowable_W = 1878.2 |
| AL-PD/H1_POLE_IN | P_d_allowable_W = 3000.0 |
| AL-PD/H1_POLE_OUT | P_d_allowable_W = 3000.0 |
| AL-PD/H1_WALL_IN | P_d_allowable_W = 3000.0 |
| AL-PD/H1_WALL_OUT | P_d_allowable_W = 3000.0 |
| AL-PFWD/N_MATCH | P_fwd_allowable_W = - |
| AL-PFWD/N_VESSEL | P_fwd_allowable_W = 794.0 |
| AL-PLUME/N_MATCH | Q_plume_to_icp_allowable_W_before_factor = - |
| AL-PLUME/N_VESSEL | Q_plume_to_icp_allowable_W_before_factor = 452.7 |
| AL-RETURN/N_MATCH | Q_return_allowable_W_before_factor = - |
| AL-RETURN/N_VESSEL | Q_return_allowable_W_before_factor = 702.3 |

## Boundary units (rejection requirement)

| unit | Q hot W | design T degC | radiator m^2 | heater op W | heater non-op W |
|---|---|---|---|---|---|
| COMPRESSOR_MOTOR | 15.7 | 130.0 | 0.012 | - | - |
| PPU | 257.1 | 30.0 | 0.706 | 0.0 | 58.3 |
| RF_GENERATOR | 400.0 | 30.0 | 1.099 | 45.7 | 90.8 |

## Cold lower limits

- N_MATCH@TC5-COLD-OP-B0: T_min 70.8 degC vs -20.0 degC; heater 0.0 W
- N_MATCH@TC6-COLD-NONOP-B0: T_min -34.2 degC vs -40.0 degC; heater 0.0 W

## P8 materials screening ceilings and DCR triggers (T max hot, 1.2 x loads)

| node | grade | ceiling degC | T max hot degC | headroom K |
|---|---|---|---|---|
| H1_ANODE | IN600 (CAND-02A, primary, DBF1-MAT-01) | 930.0 | 561.3 | 368.7 |
| H1_ANODE | IN601 (CAND-03A, backup, DBF1-MAT-02) | 1150.0 | 561.3 | 588.7 |
| H1_WALL_IN | BN Combat AX05 (distributor sheet) | 800.0 | 487.0 | 313.0 |
| H1_WALL_IN | BN HeBoSint PL 100 | 850.0 | 487.0 | 363.0 |
| H1_WALL_IN | BN-SiO2 Combat M26 (distributor sheet) | 950.0 | 487.0 | 463.0 |
| H1_WALL_IN | BN-SiO2 HeBoSint CL-S 200 | 850.0 | 487.0 | 363.0 |
| H1_WALL_OUT | BN Combat AX05 (distributor sheet) | 800.0 | 464.9 | 335.1 |
| H1_WALL_OUT | BN HeBoSint PL 100 | 850.0 | 464.9 | 385.1 |
| H1_WALL_OUT | BN-SiO2 Combat M26 (distributor sheet) | 950.0 | 464.9 | 485.1 |
| H1_WALL_OUT | BN-SiO2 HeBoSint CL-S 200 | 850.0 | 464.9 | 385.1 |
| N_COLLECTOR | IN600 (CAND-02A, primary, DBF1-MAT-03) | 930.0 | 510.1 | 419.9 |
| N_COLLECTOR | IN601 (CAND-03A, backup, DBF1-MAT-03) | 1150.0 | 510.1 | 639.9 |

| trigger | node | above degC | fires | action |
|---|---|---|---|---|
| MAT-TRIG-AN-930 | H1_ANODE | 930.0 | false | DCR swapping primary and backup (DBF1-MAT-01 / DBF1-MAT-02) |
| MAT-TRIG-AN-1150 | H1_ANODE | 1150.0 | false | DCR on DBF1-MAT-02 and the anode heat path (A9H-ANODE-02) |
| MAT-TRIG-COL-930 | N_COLLECTOR | 930.0 | false | DCR swapping primary and backup in DBF1-MAT-03 |
| MAT-TRIG-COL-1150 | N_COLLECTOR | 1150.0 | false | DCR on DBF1-MAT-03 and the collector thermal path |
| MAT-TRIG-WALL-850 | H1_WALL_IN | 850.0 | false | the grade within DBF1-MAT-04 or the thermal path changes by DCR (CL-S 200 ceiling) |

Thermal cycling: cycle bound 17928; hot / cold swing K {"H1_ANODE":579.7576680683062,"H1_WALL_IN":505.90764583994803,"H1_WALL_OUT":483.9866037798497,"N_COLLECTOR":557.3468848740564}; anode - outer wall (TC1) 95.8 K, radial differential growth (TC1) [0.046746590563907314,0.06389339325025856] mm, over the swing [0.28292174201733344,0.3866983646015602] mm.

## Spacecraft interface

Max heat into the spacecraft (hot cases): 97.3 W against the owner provisional 50 W governing allocation; the T_SC 20 / 40 / 60 degC sensitivity changes a verdict: false; smallest R_HALL grid point keeping TC1 and TC3 within 50 W: {"A_RH_m2":0.15,"G_RH_W_K":10.0,"TC1_Q_W":48.408630616586024,"TC3_Q_W":40.1489047437494}. Status REFERENCE_PENDING_ICD.

## Sensitivities (non-governing, TC1)

| sensitivity | node T max degC (TC1) |
|---|---|
| SENS-ANODE-LO (CONVERGED) | H1_ANODE 282.1, H1_BACKPLATE 248.7, H1_COIL_IN 401.5, H1_COIL_OUT 222.1, H1_COIL_TRIM 248.7, H1_POLE_IN 387.3, H1_POLE_OUT 205.1, H1_WALL_IN 415.7, H1_WALL_OUT 396.0, N_ANTENNA 394.4, N_COLLECTOR 448.3, N_HOUSING 195.7, N_MATCH 135.9, N_MOUNT 166.6, N_VESSEL 292.1, R_HALL 212.6 |
| SENS-COIL-CAP (CONVERGED) | H1_ANODE 572.8, H1_BACKPLATE 375.8, H1_COIL_IN 519.0, H1_COIL_OUT 304.9, H1_COIL_TRIM 375.8, H1_POLE_IN 496.1, H1_POLE_OUT 274.5, H1_WALL_IN 505.1, H1_WALL_OUT 480.7, N_ANTENNA 403.3, N_COLLECTOR 452.5, N_HOUSING 208.4, N_MATCH 149.1, N_MOUNT 189.0, N_VESSEL 299.4, R_HALL 305.6 |
| SENS-CORE-ARMCO (CONVERGED) | H1_ANODE 561.5, H1_BACKPLATE 364.8, H1_COIL_IN 465.9, H1_COIL_OUT 273.1, H1_COIL_TRIM 364.8, H1_POLE_IN 449.8, H1_POLE_OUT 251.1, H1_WALL_IN 484.9, H1_WALL_OUT 463.8, N_ANTENNA 401.1, N_COLLECTOR 451.5, N_HOUSING 205.3, N_MATCH 147.3, N_MOUNT 185.9, N_VESSEL 297.6, R_HALL 298.0 |
| SENS-GAN-LO (CONVERGED) | H1_ANODE 675.1, H1_BACKPLATE 356.4, H1_COIL_IN 479.7, H1_COIL_OUT 275.9, H1_COIL_TRIM 356.4, H1_POLE_IN 463.9, H1_POLE_OUT 252.9, H1_WALL_IN 497.0, H1_WALL_OUT 473.9, N_ANTENNA 401.7, N_COLLECTOR 451.8, N_HOUSING 206.1, N_MATCH 147.0, N_MOUNT 185.4, N_VESSEL 298.1, R_HALL 292.1 |
| SENS-HC-HI (OUT_OF_DOMAIN) |  |
| SENS-HC-LO (CONVERGED) | H1_ANODE 558.3, H1_BACKPLATE 357.0, H1_COIL_IN 513.3, H1_COIL_OUT 272.1, H1_COIL_TRIM 357.0, H1_POLE_IN 499.4, H1_POLE_OUT 246.0, H1_WALL_IN 521.3, H1_WALL_OUT 495.9, N_ANTENNA 402.8, N_COLLECTOR 452.3, N_HOUSING 207.7, N_MATCH 147.6, N_MOUNT 186.5, N_VESSEL 299.0, R_HALL 292.5 |
| SENS-RETURN-HI (CONVERGED) | H1_ANODE 564.9, H1_BACKPLATE 368.0, H1_COIL_IN 480.2, H1_COIL_OUT 277.3, H1_COIL_TRIM 368.0, H1_POLE_IN 465.9, H1_POLE_OUT 255.0, H1_WALL_IN 491.0, H1_WALL_OUT 468.6, N_ANTENNA 455.2, N_COLLECTOR 672.4, N_HOUSING 250.6, N_MATCH 162.4, N_MOUNT 212.4, N_VESSEL 405.1, R_HALL 300.2 |
| SENS-TSC-20 (CONVERGED) | H1_ANODE 554.1, H1_BACKPLATE 356.4, H1_COIL_IN 470.9, H1_COIL_OUT 270.4, H1_COIL_TRIM 356.4, H1_POLE_IN 456.4, H1_POLE_OUT 248.7, H1_WALL_IN 483.0, H1_WALL_OUT 461.0, N_ANTENNA 400.4, N_COLLECTOR 451.2, N_HOUSING 204.3, N_MATCH 145.0, N_MOUNT 182.0, N_VESSEL 297.1, R_HALL 290.7 |
| SENS-TSC-40 (CONVERGED) | H1_ANODE 557.2, H1_BACKPLATE 359.9, H1_COIL_IN 472.8, H1_COIL_OUT 271.8, H1_COIL_TRIM 359.9, H1_POLE_IN 458.3, H1_POLE_OUT 249.9, H1_WALL_IN 484.8, H1_WALL_OUT 462.8, N_ANTENNA 400.8, N_COLLECTOR 451.4, N_HOUSING 204.9, N_MATCH 146.1, N_MOUNT 184.0, N_VESSEL 297.4, R_HALL 293.8 |
| SENS-WALL-LO (CONVERGED) | H1_ANODE 506.7, H1_BACKPLATE 312.4, H1_COIL_IN 393.8, H1_COIL_OUT 220.1, H1_COIL_TRIM 312.4, H1_POLE_IN 386.6, H1_POLE_OUT 207.3, H1_WALL_IN 363.0, H1_WALL_OUT 342.5, N_ANTENNA 395.1, N_COLLECTOR 448.7, N_HOUSING 196.7, N_MATCH 140.7, N_MOUNT 174.8, N_VESSEL 292.7, R_HALL 260.6 |

## Closure

State **DCR REQUIRED**. DCR nodes: ["N_MATCH"]. Fundamental: []. Requirement-only nodes: ["H1_ANODE","N_ANTENNA","N_COLLECTOR","N_HOUSING","N_MOUNT","R_HALL"].
