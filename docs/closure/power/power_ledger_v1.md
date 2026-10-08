# Bus-power closure ledger v1 (A9.38 P6)

Record `power_ledger_v1.json` (Rust `abep_subsystems::power::closure_v1` + `abep_assess::power_closure`, bin `abep-assess-power-closure`; this page restates it). Boundary `bus_power_boundary_a9_v2`, configuration `hall_icp_neutralizer`, inputs `power_closure_inputs_v1.json` (sha256 `a588c0dbfb2a...`).

Every installed slot carries a load and an efficiency with an evidence class: **0 TBD terms** (the official A9-02 ledger has 24 and the M2 ledger 24). The Hall discharge power is **DESIGN_ALLOCATION_NOT_PREDICTED** at every point (no converged Hall envelope yet, HALL_NUMERICS_NOT_CONVERGED).

## Points

| point | mode | P_d [W] (basis) | P_bus non-discharge [W] | P_bus [W] | margin to 1,350 W | margin to 1,500 W | P_d,max @1,350 W | P_d,max @1,500 W |
|---|---|---|---|---|---|---|---|---|
| P-NOM | AIR_PRIMARY | 784.5 (closes the 1,350 W design allocation: DESIGN_ALLOCATION_NOT_PREDICTED) | 427.9 | 1,350.0 | 0.0 | 150.0 | 784.5 | 912.1 |
| P-12 | AIR_PRIMARY | 650.0 (PD-LOW: DESIGN_ALLOCATION_NOT_PREDICTED) | 427.9 | 1,191.9 | 158.1 | 308.1 | 784.5 | 912.1 |
| P-25 | AIR_PRIMARY | 1,350.0 (PD-HIGH: DESIGN_ALLOCATION_NOT_PREDICTED) | 429.3 | 2,016.2 | -666.2 | -516.2 | 783.2 | 910.9 |
| P-WORST | AIR_PRIMARY | 1,350.0 (PD-HIGH: DESIGN_ALLOCATION_NOT_PREDICTED) | 543.6 | 2,130.5 | -780.5 | -630.5 | 686.0 | 813.6 |
| P-XE | XE_CONTINGENCY | 650.0 (PD-LOW: DESIGN_ALLOCATION_NOT_PREDICTED) | 420.2 | 1,184.2 | 165.8 | 315.8 | 791.0 | 918.6 |

Margins are allocation / requirement differences on a design ledger, not verified margins; the 1,500 W comparison is strict (<), so P_d,max @1,500 W is a supremum. Negative margin = the registered discharge allocation does not fit at that point.

## Uncertainty corners (non-discharge loads)

| point | P_bus non-discharge conservative / reference / favourable [W] | P_d,max @1,350 W conservative / favourable | P_d,max @1,500 W conservative / favourable |
|---|---|---|---|
| P-NOM | 634.7 / 427.9 / 286.9 | 560.3 / 947.7 | 677.8 / 1,081.5 |
| P-12 | 634.7 / 427.9 / 286.9 | 560.3 / 947.7 | 677.8 / 1,081.5 |
| P-25 | 636.2 / 429.3 / 288.3 | 559.1 / 946.5 | 676.6 / 1,080.2 |
| P-WORST | 636.2 / 543.6 / 288.3 | 559.1 / 946.5 | 676.6 / 1,080.2 |
| P-XE | 626.7 / 420.2 / 277.3 | 566.5 / 956.3 | 684.0 / 1,090.0 |

## Slot ledger per point (P_bus at the spacecraft DC boundary, W)

| slot | P-NOM | P-12 | P-25 | P-WORST | P-XE | load / efficiency terms |
|---|---|---|---|---|---|---|
| hall_discharge | 922.1 | 764.1 | 1,586.9 | 1,586.9 | 764.1 | closes 1,350 W; eta ETA-HD x ETA-H-HV |
| hall_magnet_inner | 11.4 | 11.4 | 11.4 | 49.8 | 11.4 | MAG-IN-REF; eta ETA-MAG x ETA-H-LV |
| hall_magnet_outer | 28.7 | 28.7 | 28.7 | 104.5 | 28.7 | MAG-OUT-REF; eta ETA-MAG x ETA-H-LV |
| hall_magnet_trim | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | MAG-TRIM; eta ETA-MAG x ETA-H-LV |
| icp_rf_source | 302.3 | 302.3 | 302.3 | 302.3 | 302.3 | RF-PFWD / ETA-RFGEN; eta ETA-H-HV |
| icp_matching_network | 6.7 | 6.7 | 6.7 | 6.7 | 6.7 | RF-MATCH-ACT; eta ETA-DRV x ETA-H-LV |
| icp_collector_bias | 13.2 | 13.2 | 13.2 | 13.2 | 13.2 | ICP-BIAS; eta ETA-BIAS x ETA-H-HV |
| flow_control_atmospheric | 5.3 | 5.3 | 5.3 | 5.3 | 0.0 | VALVE-COIL; eta ETA-DRV x ETA-H-LV |
| flow_control_xe | 0.0 | 0.0 | 0.0 | 0.0 | 7.9 | 0 W; eta ETA-DRV x ETA-H-LV |
| compressor | 10.3 | 10.3 | 11.8 | 11.8 | 0.0 | CP-NOM; eta ETA-CPD x ETA-H-HV |
| thermal_control | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 50 W allowance residual; eta ETA-TH x ETA-H-LV |
| housekeeping_controls | 46.0 | 46.0 | 46.0 | 46.0 | 46.0 | HK-LOAD; eta ETA-HK x ETA-H-LV |
| reserved_dc_port | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 W; eta ETA-RES |
| **total** | **1,350.0** | **1,191.9** | **2,016.2** | **2,130.5** | **1,184.2** | |

## Losses inside P_bus (W)

| point | conversion (PPU supplies) | harness | front end | RF generator (DC -> forward RF) |
|---|---|---|---|---|
| P-NOM | 119.8 | 7.9 | 67.5 | 85.7 |
| P-12 | 104.8 | 7.1 | 59.6 | 85.7 |
| P-25 | 182.6 | 11.0 | 100.8 | 85.7 |
| P-WORST | 225.2 | 13.2 | 106.5 | 85.7 |
| P-XE | 105.3 | 7.1 | 59.2 | 85.7 |

## Owner-allocation checks (admitted `allocation_checks` / `icp_power_allocation_check`)

| point | design 1,350 W | common 300 W (P_bus) | controls / thermal 50 W | P_ICP vs available |
|---|---|---|---|---|
| P-NOM | WITHIN_ALLOCATION | WITHIN_ALLOCATION (65.6) | WITHIN_ALLOWANCE (50.0) | WITHIN_AVAILABLE (322.2 vs 322.2) |
| P-12 | WITHIN_ALLOCATION | WITHIN_ALLOCATION (65.6) | WITHIN_ALLOWANCE (50.0) | WITHIN_AVAILABLE (322.2 vs 480.3) |
| P-25 | EXCEEDS_ALLOCATION | WITHIN_ALLOCATION (67.0) | WITHIN_ALLOWANCE (50.0) | EXCEEDS_AVAILABLE (322.2 vs -344.0) |
| P-WORST | EXCEEDS_ALLOCATION | WITHIN_ALLOCATION (67.0) | WITHIN_ALLOWANCE (50.0) | EXCEEDS_AVAILABLE (322.2 vs -458.3) |
| P-XE | WITHIN_ALLOCATION | WITHIN_ALLOCATION (57.9) | WITHIN_ALLOWANCE (50.0) | WITHIN_AVAILABLE (322.2 vs 488.0) |

## RF trade line (P-12 loads; no fixed Hall / ICP split, A9.1 OQ-A902-03)

| P_fwd [W] | ICP group P_bus [W] | P_d,max @1,350 W | P_d,max @1,500 W |
|---|---|---|---|
| 0 | 19.9 | 1,041.6 | 1,169.2 |
| 100 | 171.1 | 913.0 | 1,040.7 |
| 200 | 322.2 | 784.5 | 912.1 |
| 300 | 473.3 | 655.9 | 783.5 |
| 400 | 624.5 | 527.3 | 654.9 |
| 500 | 775.6 | 398.8 | 526.4 |

## Compressor headroom (for DCR-001)

At P-NOM the compressor motor-drive input may grow to **231.3 W** inside the 300 W common allocation; each extra watt of compressor input lowers P_d,max by 0.9000 W. DCR-001 replaces CP-NOM / CP-WORST (model-derived, code-default coefficients).

## Derived requirement on the Hall discharge (input to P2)

Until the Hall envelope converges (P2), the discharge power is an allocation. With every other bus term closed, the bus closes at the 12 mN point if H-1 delivers 12 mN at P_d <= 784 W (1,350 W design allocation; T/P_d >= 15.3 mN/kW) and the 25 mN capability if it delivers 25 mN at P_d < 911 W (HC-03; T/P_d >= 27.4 mN/kW). The registered DBF-1 band upper end (1,350 W discharge) does not fit the bus with the ICP, magnet and common loads: it is a sizing band, and the flight operating ceiling is P_d,max. These are requirements on the Hall envelope, not predictions.

| point | thrust | P_d,max (reference) [W] | required T / P_d [mN/kW] | conservative corner P_d,max [W] | required T / P_d [mN/kW] |
|---|---|---|---|---|---|
| P-12 | 12 mN @ design allocation 1,350 W | 784.5 | 15.3 | 560.3 | 21.4 |
| P-12 | 12 mN @ HC-03 1,500 W | 912.1 | 13.2 | 677.8 | 17.7 |
| P-25 | 25 mN @ design allocation 1,350 W | 783.2 | 31.9 | 559.1 | 44.7 |
| P-25 | 25 mN @ HC-03 1,500 W | 910.9 | 27.4 | 676.6 | 36.9 |
| P-WORST | 25 mN @ HC-03 1,500 W | 813.6 | 30.7 | 676.6 | 36.9 |

## Closed terms

| term | quantity | value | bounds | evidence class | closure class | flags |
|---|---|---|---|---|---|---|
| PD-LOW | Hall discharge load-plane power at the 12 mN point (V_d x I_d) | 650 W | [650, 650] | owner-allocation (level OWNER_DECISION) | DESIGN_ALLOCATION_NOT_PREDICTED | DESIGN_ALLOCATION_NOT_PREDICTED |
| PD-HIGH | Hall discharge load-plane power at the 25 mN point (band upper end) | 1350 W | [1350, 1350] | owner-allocation (level OWNER_DECISION) | DESIGN_ALLOCATION_NOT_PREDICTED | DESIGN_ALLOCATION_NOT_PREDICTED |
| RF-PFWD | ICP RF forward power at the generator / 50-ohm reference plane (reference value) | 200 W | [0, 500] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | OPERATING_VARIABLE, UPDATE_FROM_P4_ICP45 |
| MAG-IN-REF | inner coil terminal power at the B band upper end (268.6 G), hot | 6.34597 W | [0.3652, 27.84] | model-derived (level 6) | MODEL_DERIVED | FEMM_PENDING_P3 |
| MAG-OUT-REF | outer coil terminal power at the B band upper end (268.6 G), hot | 16.043 W | [0.9236, 58.4] | model-derived (level 6) | MODEL_DERIVED | FEMM_PENDING_P3 |
| MAG-IN-CAP | inner coil terminal power at the MC-1 capability (403 G), worst-case assumptions | 27.84 W | [0.3652, 27.84] | model-derived (level 6) | MODEL_DERIVED | FEMM_PENDING_P3 |
| MAG-OUT-CAP | outer coil terminal power at the MC-1 capability (403 G), worst-case assumptions | 58.4 W | [0.9236, 58.4] | model-derived (level 6) | MODEL_DERIVED | FEMM_PENDING_P3 |
| MAG-TRIM | trim coil terminal power | 0 W | [0, 0] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | FEMM_PENDING_P3 |
| RF-MATCH-ACT | adjustable local match: tuning actuators and controller DC input | 5 W | [0, 10] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY, UPDATE_FROM_P2_IMPEDANCE_MAP |
| ICP-BIAS | collector / bias supply output (V_bias x I_bias) | 10 W | [0, 20] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY, UPDATE_FROM_P1_IT_18 |
| VALVE-COIL | proportional / isolation valve coil power per energised valve (hot) | 1.9631 W | [0.407813, 1.9631] | inferred (level 3) | SOURCED_ANALOG | VERIFY_COIL_MATERIAL |
| HK-LOAD | propulsion controller, PPU control, FDIR, sensors, TM/TC interface and quiescent draw | 30 W | [12, 30] | assumed (level 5) | SOURCED_ANALOG | RATING_USED_AS_LOAD |
| CP-NOM | compressor motor-drive electrical input, nominal (median over required states of the per-state maximum over admitted in-domain surface scenarios) | 9.76239 W | [9.76239, 9.76239] | model-derived (level 6) | MODEL_DERIVED | UPDATE_FROM_DCR_001, CODE_DEFAULT_COEFFICIENTS |
| CP-WORST | compressor motor-drive electrical input, maximum over every required state and admitted in-domain surface scenario (at the worst admitted state) | 11.1251 W | [11.1251, 11.1251] | model-derived (level 6) | MODEL_DERIVED | UPDATE_FROM_DCR_001, CODE_DEFAULT_COEFFICIENTS |
| ETA-FE | front end: spacecraft DC bus -> regulated 100 V internal propulsion bus | 0.95 - | [0.92, 0.97] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY, SPACECRAFT_ICD_DEPENDENT |
| ETA-HD | Hall discharge supply (100 V internal bus -> V_d at the anode terminals) | 0.9 - | [0.86, 0.92] | digitized (level 3) | SOURCED_ANALOG | UPDATE_FROM_ROW_113_BREADBOARD |
| ETA-MAG | per-coil magnet supply (current-controlled, isolated) | 0.6 - | [0.6, 0.85] | assumed (level 5) | SOURCED_ANALOG | - |
| ETA-RFGEN | 13.56 MHz RF generator DC input -> forward RF power | 0.7 - | [0.6, 0.92] | inferred (level 6) | SOURCED_ANALOG | UPDATE_FROM_RFQ_06 |
| ETA-BIAS | collector / bias supply | 0.8 - | [0.8, 0.9] | measured (level 3) | SOURCED_ANALOG | - |
| ETA-DRV | valve-driver / actuator-driver supply | 0.8 - | [0.8, 0.9] | assumed (level 5) | SOURCED_ANALOG | - |
| ETA-HK | auxiliary / housekeeping supply | 0.7 - | [0.7, 0.85] | assumed (level 5) | SOURCED_ANALOG | - |
| ETA-TH | heater switch (resistive heaters switched from the internal bus) | 0.98 - | [0.95, 0.99] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY |
| ETA-CPD | compressor drive supply path (drive fed from the internal bus) | 1 - | [1, 1] | model-derived (level 6) | MODEL_DERIVED | UPDATE_FROM_DCR_001 |
| ETA-H-HV | harness, 100 V-class power lines (discharge, RF generator, bias, compressor drive) | 0.995 - | [0.99, 0.999] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY |
| ETA-H-LV | harness, low-voltage lines (magnets, valves, actuators, housekeeping, heaters) | 0.98 - | [0.97, 0.995] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | VERIFY |
| ETA-RES | reserved DC port (unused, 0 W) | 1 - | [1, 1] | assumed (level 7) | FROZEN_ENGINEERING_ASSUMPTION | - |

## Summary

- Ledger terms closed: 27 (the 24 TBD entries of the official ledger - 12 slot loads and 12 slot efficiencies - plus the front-end efficiency and the two harness terms that every slot efficiency carries); TBD remaining: 0.
- By closure class: SOURCED_ANALOG 12, MODEL_DERIVED 4, FROZEN_ENGINEERING_ASSUMPTION 9, OWNER_ALLOCATION_RESIDUAL 1, DESIGN_ALLOCATION_NOT_PREDICTED 1.
- By evidence class (efficiencies by their converter term): measured 1, digitized 1, inferred 1, model-derived 4, owner-allocation 2, assumed 18.
- Register terms: SOURCED_ANALOG 8, MODEL_DERIVED 7, FROZEN_ENGINEERING_ASSUMPTION 9, DESIGN_ALLOCATION_NOT_PREDICTED 2.

## Not

- not a Hall performance prediction: the discharge power is DESIGN_ALLOCATION_NOT_PREDICTED at every point (HALL_NUMERICS_NOT_CONVERGED)
- not a gate verdict: HC-03 margins are differences on a design ledger, not a P_bus,1ms,max measurement (A9.1 OQ-A902-01)
- not a change to the official A9-02 ledger, the admitted power functions or DBF-1
- not measured: every term is a sourced analog, a model output, an allocation or a frozen engineering assumption with bounds
