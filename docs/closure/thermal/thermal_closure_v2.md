# P7 thermal closure v2 (DBF-1, frozen topology)

Companion of `thermal_closure_v2.json` (the JSON governs). Model NP-THERMAL-CATHODELESS 2.0.0, case class PARAMETRIC (label PARAMETRIC_NOT_A_PREDICTION), validation status NOT_VALIDATED. Preregistration `docs/closure/thermal/thermal_cases_prereg_v1.json` (sha256 `5666c528486f8cb7935863b3826c66e60271242637b31826468adde09394ecba`); load inputs `docs/closure/thermal/thermal_load_inputs_v2.json` (sha256 `c748b8fe394b503c2791f88b9113a2dd500cc5942cf38f0771ac1f91c886d12f`); Rust commit `fb29e9611927b68d0fc73026e4ae09811da12c3d`.

**Closure state: DCR REQUIRED**

Selected design levers: R_HALL area 0.02 m^2, back-plate doubler 2.0 W/K (FEASIBLE_CONFIRMED); R_HALL mass at 4 kg/m^2: 0.1 kg.

## Nodes (governing hot cases TC1-TC4 with 1.2 x heat loads; cold TC5 / TC6)

| node | limit class | limit degC | ceiling (limit - 50 K) | T max hot degC | margin K | verdict | required capability degC | coating capability degC | T min cold op / non-op degC |
|---|---|---|---|---|---|---|---|---|---|
| H1_ANODE | REQUIREMENT_ONLY | - | - | 512.0 | - | REQUIREMENT | 562.0 | - | 72.0 / -18.5 |
| H1_BACKPLATE | NECESSARY_CEILING | 754.0 | 704.0 | 338.7 | 365.3 | PASS | - | - | 60.5 / -18.5 |
| H1_COIL_IN | SOURCED_GUIDE | 537.8 | 487.8 | 445.6 | 42.2 | PASS | - | - | 70.0 / -17.8 |
| H1_COIL_OUT | SOURCED_GUIDE | 537.8 | 487.8 | 255.9 | 231.9 | PASS | - | - | 39.4 / -25.6 |
| H1_COIL_TRIM | SOURCED_GUIDE | 537.8 | 487.8 | 338.7 | 149.1 | PASS | - | - | 60.6 / -18.5 |
| H1_POLE_IN | NECESSARY_CEILING | 938.0 | 888.0 | 432.1 | 455.9 | PASS | - | 482.1 | 69.3 / -17.8 |
| H1_POLE_OUT | NECESSARY_CEILING | 754.0 | 704.0 | 236.6 | 467.4 | PASS | - | 286.6 | 38.7 / -25.6 |
| H1_WALL_IN | SOURCED_GUIDE | 900.0 | 850.0 | 454.4 | 395.6 | PASS | - | - | 96.0 / -18.9 |
| H1_WALL_OUT | SOURCED_GUIDE | 900.0 | 850.0 | 433.5 | 416.5 | PASS | - | - | 90.8 / -19.1 |
| N_ANTENNA | REQUIREMENT_ONLY | - | - | 612.2 | - | REQUIREMENT | 662.2 | - | 253.7 / -43.8 |
| N_COLLECTOR | REQUIREMENT_ONLY | - | - | 510.1 | - | REQUIREMENT | 560.1 | - | 181.1 / -47.3 |
| N_HOUSING | REQUIREMENT_ONLY | - | - | 251.7 | - | REQUIREMENT | 301.7 | 301.7 | 98.9 / -43.8 |
| N_MATCH | DERATED_ELECTRONICS | 110.0 | 60.0 | 183.5 | -123.5 | FAIL | - | 233.5 | 70.8 / -34.2 |
| N_MOUNT | REQUIREMENT_ONLY | - | - | 210.9 | - | REQUIREMENT | 260.9 | 260.9 | 78.0 / -35.7 |
| N_VESSEL | ASSUMED_FROM_MEMORY | 490.0 | 440.0 | 366.1 | 73.9 | PASS | - | - | 136.4 / -46.4 |
| R_HALL | REQUIREMENT_ONLY | - | - | 280.8 | - | REQUIREMENT | 330.8 | 330.8 | 53.0 / -18.7 |

## Per case (T max / T min, degC)

| node | S1-BAND-1350-BSTAR | TC1-HOT-H-BSTAR | TC2-HOT-H-B0 | TC3-HOT-I-BSTAR | TC4-HOT-I-B0 | TC5-COLD-OP-B0 | TC6-COLD-NONOP-B0 | TC7-HOT-H-BSTAR-XE |
|---|---|---|---|---|---|---|---|---|
| H1_ANODE | 659.1 / 659.1 | 511.0 / 511.0 | 512.0 / 509.7 | 419.3 / 419.3 | 420.4 / 417.9 | 75.2 / 72.0 | -15.2 / -18.5 | 511.0 / 511.0 |
| H1_BACKPLATE | 413.5 / 413.5 | 337.6 / 337.6 | 338.7 / 336.2 | 292.9 / 292.9 | 294.1 / 291.4 | 63.8 / 60.5 | -15.2 / -18.5 | 337.6 / 337.6 |
| H1_COIL_IN | 532.8 / 532.8 | 445.0 / 445.0 | 445.6 / 444.0 | 394.3 / 394.3 | 394.9 / 393.1 | 71.7 / 70.0 | -16.2 / -17.8 | 445.0 / 445.0 |
| H1_COIL_OUT | 308.5 / 308.5 | 255.6 / 255.6 | 255.9 / 253.1 | 228.0 / 228.0 | 228.2 / 225.3 | 42.7 / 39.4 | -22.1 / -25.6 | 255.6 / 255.6 |
| H1_COIL_TRIM | 413.5 / 413.5 | 337.6 / 337.6 | 338.7 / 336.2 | 292.9 / 292.9 | 294.1 / 291.4 | 63.8 / 60.6 | -15.2 / -18.5 | 337.6 / 337.6 |
| H1_POLE_IN | 516.2 / 516.2 | 431.5 / 431.5 | 432.1 / 430.4 | 382.7 / 382.7 | 383.4 / 381.6 | 71.1 / 69.3 | -16.2 / -17.8 | 431.5 / 431.5 |
| H1_POLE_OUT | 280.1 / 280.1 | 236.3 / 236.3 | 236.6 / 233.8 | 213.1 / 213.1 | 213.3 / 210.3 | 42.1 / 38.7 | -22.1 / -25.6 | 236.3 / 236.3 |
| H1_WALL_IN | 549.5 / 549.5 | 454.0 / 454.0 | 454.4 / 453.0 | 393.0 / 393.0 | 393.4 / 391.8 | 98.2 / 96.0 | -16.6 / -18.9 | 454.0 / 454.0 |
| H1_WALL_OUT | 525.2 / 525.2 | 433.0 / 433.0 | 433.5 / 431.9 | 373.9 / 373.9 | 374.4 / 372.6 | 93.2 / 90.8 | -16.7 / -19.1 | 433.0 / 433.0 |
| N_ANTENNA | 414.5 / 414.5 | 394.8 / 394.8 | 395.1 / 392.9 | 611.9 / 611.9 | 612.2 / 611.0 | 256.4 / 253.7 | -39.1 / -43.8 | 394.8 / 394.8 |
| N_COLLECTOR | 492.7 / 492.7 | 430.8 / 430.8 | 430.9 / 429.9 | 509.9 / 509.9 | 510.1 / 509.4 | 183.2 / 181.1 | -43.4 / -47.3 | 430.8 / 430.8 |
| N_HOUSING | 219.9 / 219.9 | 198.4 / 198.4 | 198.9 / 195.8 | 251.2 / 251.2 | 251.7 / 249.2 | 102.4 / 98.9 | -38.8 / -43.8 | 198.4 / 198.4 |
| N_MATCH | 155.4 / 155.4 | 143.0 / 143.0 | 146.0 / 140.9 | 180.6 / 180.6 | 183.5 / 178.8 | 75.9 / 70.8 | -28.9 / -34.2 | 143.0 / 143.0 |
| N_MOUNT | 200.1 / 200.1 | 178.7 / 178.7 | 179.8 / 176.8 | 209.8 / 209.8 | 210.9 / 208.3 | 81.5 / 78.0 | -31.2 / -35.7 | 178.7 / 178.7 |
| N_VESSEL | 320.0 / 320.0 | 286.6 / 286.6 | 286.9 / 285.1 | 365.9 / 365.9 | 366.1 / 364.8 | 139.0 / 136.4 | -42.4 / -46.4 | 286.6 / 286.6 |
| R_HALL | 331.0 / 331.0 | 278.8 / 278.8 | 280.8 / 277.4 | 246.2 / 246.2 | 248.3 / 244.6 | 57.6 / 53.0 | -14.0 / -18.7 | 278.8 / 278.8 |
| run status | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED | CONVERGED |
| Q into spacecraft W | 111.8 | 89.3 | 89.6 | 80.2 | 80.6 | 18.4 | -16.0 | 89.3 |

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
| AL-PLUME/N_VESSEL | Q_plume_to_icp_allowable_W_before_factor = 458.0 |
| AL-RETURN/N_MATCH | Q_return_allowable_W_before_factor = - |
| AL-RETURN/N_VESSEL | Q_return_allowable_W_before_factor = 610.0 |

## Boundary units (rejection requirement)

| unit | Q hot W | design T degC | radiator m^2 | heater op W | heater non-op W |
|---|---|---|---|---|---|
| COMPRESSOR_MOTOR | 13.4 | 130.0 | 0.010 | - | - |
| PPU | 224.8 | 30.0 | 0.618 | 0.0 | 51.0 |
| RF_GENERATOR | 400.0 | 30.0 | 1.099 | 45.7 | 90.8 |

## Cold lower limits

- N_MATCH@TC5-COLD-OP-B0: T_min 70.8 degC vs -20.0 degC; heater 0.0 W
- N_MATCH@TC6-COLD-NONOP-B0: T_min -34.2 degC vs -40.0 degC; heater 0.0 W

## P8 materials screening ceilings and DCR triggers (T max hot, 1.2 x loads)

| node | grade | ceiling degC | T max hot degC | headroom K |
|---|---|---|---|---|
| H1_ANODE | IN600 (CAND-02A, primary, DBF1-MAT-01) | 930.0 | 512.0 | 418.0 |
| H1_ANODE | IN601 (CAND-03A, backup, DBF1-MAT-02) | 1150.0 | 512.0 | 638.0 |
| H1_WALL_IN | BN Combat AX05 (distributor sheet) | 800.0 | 454.4 | 345.6 |
| H1_WALL_IN | BN HeBoSint PL 100 | 850.0 | 454.4 | 395.6 |
| H1_WALL_IN | BN-SiO2 Combat M26 (distributor sheet) | 950.0 | 454.4 | 495.6 |
| H1_WALL_IN | BN-SiO2 HeBoSint CL-S 200 | 850.0 | 454.4 | 395.6 |
| H1_WALL_OUT | BN Combat AX05 (distributor sheet) | 800.0 | 433.5 | 366.5 |
| H1_WALL_OUT | BN HeBoSint PL 100 | 850.0 | 433.5 | 416.5 |
| H1_WALL_OUT | BN-SiO2 Combat M26 (distributor sheet) | 950.0 | 433.5 | 516.5 |
| H1_WALL_OUT | BN-SiO2 HeBoSint CL-S 200 | 850.0 | 433.5 | 416.5 |
| N_COLLECTOR | IN600 (CAND-02A, primary, DBF1-MAT-03) | 930.0 | 510.1 | 419.9 |
| N_COLLECTOR | IN601 (CAND-03A, backup, DBF1-MAT-03) | 1150.0 | 510.1 | 639.9 |

| trigger | node | above degC | fires | action |
|---|---|---|---|---|
| MAT-TRIG-AN-930 | H1_ANODE | 930.0 | false | DCR swapping primary and backup (DBF1-MAT-01 / DBF1-MAT-02) |
| MAT-TRIG-AN-1150 | H1_ANODE | 1150.0 | false | DCR on DBF1-MAT-02 and the anode heat path (A9H-ANODE-02) |
| MAT-TRIG-COL-930 | N_COLLECTOR | 930.0 | false | DCR swapping primary and backup in DBF1-MAT-03 |
| MAT-TRIG-COL-1150 | N_COLLECTOR | 1150.0 | false | DCR on DBF1-MAT-03 and the collector thermal path |
| MAT-TRIG-WALL-850 | H1_WALL_IN | 850.0 | false | the grade within DBF1-MAT-04 or the thermal path changes by DCR (CL-S 200 ceiling) |

Thermal cycling: cycle bound 17928; hot / cold swing K {"H1_ANODE":530.5063442159928,"H1_WALL_IN":473.27780191746547,"H1_WALL_OUT":452.52848150371983,"N_COLLECTOR":557.3468848740564}; anode - outer wall (TC1) 78.0 K, radial differential growth (TC1) [0.03805149789910256,0.05200891208750288] mm, over the swing [0.2588870959774045,0.3538477315920672] mm.

## Spacecraft interface

Max heat into the spacecraft (hot cases): 89.6 W against the owner provisional 50 W governing allocation; the T_SC 20 / 40 / 60 degC sensitivity changes a verdict: false; smallest R_HALL grid point keeping TC1 and TC3 within 50 W: {"A_RH_m2":0.15,"G_RH_W_K":5.0,"TC1_Q_W":46.79735176588378,"TC3_Q_W":42.56909969266805}. Status REFERENCE_PENDING_ICD.

## Sensitivities (non-governing, TC1)

| sensitivity | node T max degC (TC1) |
|---|---|
| SENS-ANODE-LO (CONVERGED) | H1_ANODE 262.1, H1_BACKPLATE 233.2, H1_COIL_IN 376.4, H1_COIL_OUT 208.3, H1_COIL_TRIM 233.2, H1_POLE_IN 363.0, H1_POLE_OUT 193.2, H1_WALL_IN 387.5, H1_WALL_OUT 368.7, N_ANTENNA 388.5, N_COLLECTOR 427.7, N_HOUSING 189.6, N_MATCH 132.5, N_MOUNT 161.1, N_VESSEL 281.4, R_HALL 200.5 |
| SENS-COIL-CAP (CONVERGED) | H1_ANODE 524.8, H1_BACKPLATE 351.4, H1_COIL_IN 492.7, H1_COIL_OUT 288.9, H1_COIL_TRIM 351.4, H1_POLE_IN 470.6, H1_POLE_OUT 261.3, H1_WALL_IN 474.0, H1_WALL_OUT 450.5, N_ANTENNA 396.8, N_COLLECTOR 431.8, N_HOUSING 201.3, N_MATCH 145.0, N_MOUNT 182.1, N_VESSEL 288.3, R_HALL 288.6 |
| SENS-CORE-ARMCO (CONVERGED) | H1_ANODE 512.3, H1_BACKPLATE 339.1, H1_COIL_IN 434.8, H1_COIL_OUT 255.6, H1_COIL_TRIM 339.1, H1_POLE_IN 419.6, H1_POLE_OUT 236.4, H1_WALL_IN 452.0, H1_WALL_OUT 432.2, N_ANTENNA 394.6, N_COLLECTOR 430.7, N_HOUSING 198.1, N_MATCH 143.1, N_MOUNT 178.7, N_VESSEL 286.4, R_HALL 279.9 |
| SENS-GAN-LO (CONVERGED) | H1_ANODE 617.3, H1_BACKPLATE 332.4, H1_COIL_IN 449.0, H1_COIL_OUT 257.7, H1_COIL_TRIM 332.4, H1_POLE_IN 434.4, H1_POLE_OUT 237.6, H1_WALL_IN 462.7, H1_WALL_OUT 440.9, N_ANTENNA 395.1, N_COLLECTOR 430.9, N_HOUSING 198.8, N_MATCH 142.8, N_MOUNT 178.4, N_VESSEL 286.9, R_HALL 275.1 |
| SENS-HC-HI (OUT_OF_DOMAIN) |  |
| SENS-HC-LO (CONVERGED) | H1_ANODE 508.8, H1_BACKPLATE 331.5, H1_COIL_IN 485.2, H1_COIL_OUT 254.3, H1_COIL_TRIM 331.5, H1_POLE_IN 472.2, H1_POLE_OUT 231.2, H1_WALL_IN 490.3, H1_WALL_OUT 466.0, N_ANTENNA 396.2, N_COLLECTOR 431.5, N_HOUSING 200.5, N_MATCH 143.3, N_MOUNT 179.2, N_VESSEL 287.8, R_HALL 274.4 |
| SENS-RETURN-HI (CONVERGED) | H1_ANODE 515.6, H1_BACKPLATE 342.3, H1_COIL_IN 450.5, H1_COIL_OUT 259.7, H1_COIL_TRIM 342.3, H1_POLE_IN 437.1, H1_POLE_OUT 240.1, H1_WALL_IN 458.4, H1_WALL_OUT 437.2, N_ANTENNA 444.3, N_COLLECTOR 638.6, N_HOUSING 240.8, N_MATCH 157.6, N_MOUNT 203.9, N_VESSEL 387.2, R_HALL 282.1 |
| SENS-TSC-20 (CONVERGED) | H1_ANODE 504.3, H1_BACKPLATE 330.4, H1_COIL_IN 440.8, H1_COIL_OUT 252.7, H1_COIL_TRIM 330.4, H1_POLE_IN 427.2, H1_POLE_OUT 233.7, H1_WALL_IN 450.0, H1_WALL_OUT 429.2, N_ANTENNA 393.8, N_COLLECTOR 430.3, N_HOUSING 197.1, N_MATCH 140.7, N_MOUNT 174.7, N_VESSEL 285.8, R_HALL 272.2 |
| SENS-TSC-40 (CONVERGED) | H1_ANODE 507.7, H1_BACKPLATE 334.0, H1_COIL_IN 442.9, H1_COIL_OUT 254.1, H1_COIL_TRIM 334.0, H1_POLE_IN 429.3, H1_POLE_OUT 235.0, H1_WALL_IN 452.0, H1_WALL_OUT 431.1, N_ANTENNA 394.3, N_COLLECTOR 430.6, N_HOUSING 197.7, N_MATCH 141.9, N_MOUNT 176.7, N_VESSEL 286.2, R_HALL 275.5 |
| SENS-WALL-LO (CONVERGED) | H1_ANODE 460.1, H1_BACKPLATE 289.2, H1_COIL_IN 370.3, H1_COIL_OUT 207.6, H1_COIL_TRIM 289.2, H1_POLE_IN 362.9, H1_POLE_OUT 196.0, H1_WALL_IN 337.1, H1_WALL_OUT 317.8, N_ANTENNA 389.2, N_COLLECTOR 428.1, N_HOUSING 190.6, N_MATCH 136.9, N_MOUNT 168.4, N_VESSEL 282.0, R_HALL 243.5 |

## Closure

State **DCR REQUIRED**. DCR nodes: ["N_MATCH"]. Fundamental: []. Requirement-only nodes: ["H1_ANODE","N_ANTENNA","N_COLLECTOR","N_HOUSING","N_MOUNT","R_HALL"].
