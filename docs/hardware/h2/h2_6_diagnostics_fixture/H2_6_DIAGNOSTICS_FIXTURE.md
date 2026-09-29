# H2-6 diagnostics + H-1 fixture

| | |
|---|---|
| status | **PRELIMINARY_DRAFT_PENDING_OWNER** |
| lane | `fo_h2_6_diagnostics_fixture` (trigger `T_H2_6_DIAGNOSTICS_FIXTURE`, owner addendum A7) |
| register (authoritative) | [`h2_6_diagnostics_fixture_v1.json`](h2_6_diagnostics_fixture_v1.json) |
| builder | [`build_h2_6_diagnostics_fixture.py`](build_h2_6_diagnostics_fixture.py) (`--write`, `--check`, `--verify-sources`, `--pending-status`) |
| test | `tests/test_h2_6_diagnostics_fixture.py` |
| base commit | `8ea7e4b` |

H2 hardware design / preliminary-sizing lane (A7 h2_scope), not an architecture-selection lane. Nothing here is approved, pre-registered, locked or ordered. Values are PRELIMINARY, PENDING a named lane, or TBD with what they require. A5 numbers are allocations or requirements, never predictions. Bundle 1 stays NO_BASELINE_YET; the credible Hall set is empty.

**Authority (immutable, pinned by sha256):**

- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` - `5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac` (original owner disposition od_hardware_pivot)
- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json` - `10d79026f1a65e0c2a9fa9e1f9a5f9abc9d162692711857bd43575f3095c8d4e` (A3: metrology lab / cathode temperature / near-cathode RGA / k = 2 / S1a gate)
- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json` - `beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4` (A4: force/DC/RF traceability, metrology spec approved as procurement spec, MFC ranges, S1a interlocks, C-1 diode)
- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json` - `0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621` (A5: proposal reference architecture / Phase-1 baseline (allocations, 16 subsystems, closing risks))
- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json` - `aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180` (A6: follow-on authorization, Phase-1 decision quantities, not_authorized list, execution-order clarification)
- `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json` - `dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925` (A7: execution model (H2 = design/preliminary sizing; architecture-changing blockers 1-3; M16 scheduler))
- `docs/decisions/verification/A5_BASELINE_VERIFICATION.json` - `4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523` (G0 governance baseline (verdict CLEAN; A5 may be pinned))

**Verified deliverables and immutable snapshots (pinned by sha256 at the base commit):**

- `docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json` - `84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28` (A6 P1-PREG (verified, merged 3122bcd): the nine Phase-1 decision quantities P1DQ-* and their measurement chains)
- `docs/budgets/xe_ledger/xe_ledger_v1.json` - `965fdafa60ae9c3ee1e36189f22ef00198ae3f8a906696213bec13bdcbfb09ad` (A6 XE (verified, merged 732bbde): parametric Xe ledger; consumer of measured per-mode Xe)
- `docs/experiments/hardware/hardware_requirements_v1.json` - `0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0` (W3 H-1/C-1 hardware definition (CI ids, planes, HW-* requirements, identity matrix, derived numbers))
- `docs/experiments/hardware/snapshots/w4_instrumentation_definition_v1_at_fe2c05e.json` - `7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96` (W4 instrumentation definition v1-r2 immutable snapshot (INS-01..24, INS-P-01..12); byte-identical to docs/experiments/instrumentation/instrumentation_definition_v1.json at this base)
- `docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json` - `55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865` (W4 metrology measurement specification (MS-G / MS-M; A3/A4 standards))
- `docs/experiments/capability_demo/capability_demo_prep_v1.json` - `ba465206f3a9d7773e338e06dc9e98961c3a97d7f89357c2ed3a227f2a924e67` (W4 capability demonstration preparation CD-01..CD-07 and CD-P-* planning values)
- `docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json` - `011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac` (S1a engineering gate (S1A-C1..C5, S1A-FW firewall classes))
- `docs/experiments/s1_readiness/s1_readiness_conditions_v1.json` - `1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1` (N4 S1-readiness gate (S1-C1..C8))

Mutable drafts and modules (`docs/experiments/instrumentation/instrumentation_definition_v1.json`, `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json`, `docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json`, `docs/architecture_comparison/experiment_package/experiment_package_v1.json`, `abep_sim/constants.py`, `abep_sim/arch_boundary.py`) are consumed by value and re-checked by `--verify-sources`; they are not pinned. Governance files (`docs/orchestration/lane_registry_v1.json`, `docs/orchestration/trigger_registry_v1.json`, `docs/orchestration/fired_triggers.jsonl`, `docs/orchestration/trigger_ledger_v2.jsonl`, `docs/orchestration/runtime_state.json`) are never pinned.

## Summary

- **Every Phase-1 decision quantity (P1DQ-*) maps to W4 instruments** (measurement map below); every DECISIVE and CONDITION instrument of each P1DQ measurement chain is covered. eta_u is the weakest link: its inputs come from INS-13 (ExB) and INS-15 (Faraday), both AT_RISK in W4. This is a test-readiness risk, not an architecture veto.
- **Thrust stand:** calibrated span 0 to >= 25.4181 mN (planning, u_abs = 1 %); per-reading 1 sigma at 12 mN 59.8034-87.863 uN (n = 4-8, LOCK-2); resolution step no larger than that.
- **Facility:** holding the xenon-derived planning pressures at the delivered-flow upper end (N2 3.14 mg/s + Xe cathode 0.15 mg/s) needs S_eff = 212104 L/s at 1e-5 Torr and 42420.9 L/s at 5e-5 Torr. That is a facility-choice constraint.
- **Background ingestion matters most at the knee:** at the lowest candidate anode flow, the N2 one-way background flux over the analog exit annulus is 0.170521 of the anode flow at 1e-5 Torr and 0.852605 at 5e-5 Torr (a scale, not a correction). p_b is logged with every knee reading, and the S5 elevated-p_b check is kept.
- **MFCs:** pure-gas paths raise the turndown to 265.869:1 (N2) and 151.925:1 (O2), so 4 overlapping ranges per path are needed at the 20 % FS floor. The Xe cathode MFC full scale is 0.15-0.50 mg/s.
- **Fixture:** the pre-ionizer module sits in its own kinematic carrier, so neither its weight nor assembly torque reaches IP-DN or the H-1 mount, and H-1 is never unbolted. SVC-1 carries every line in every configuration, with shams. Remount contributors c1..c5 are each mapped to a feature and to CD-02a (S1a) and S1b.
- **Hard incompatibility:** none found (section c).

## (a) Design parameters

| id | name | value | units | basis | evidence | status | class |
|---|---|---|---|---|---|---|---|
| H26-01 | thrust-stand calibrated span, lower end | 0 | mN | requirement | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-02 | thrust-stand calibrated span, upper end (minimum) | 25.4181 | mN | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (LOCK-2 absolute uncertainty) | GROUND/FACILITY-ONLY |
| H26-03 | thrust per-reading repeatability target at 12 mN (1 sigma) | n=4: 59.8034; n=6: 75.2348; n=8: 87.863 | uN | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (n fixed at LOCK-2) | GROUND/FACILITY-ONLY |
| H26-04 | thrust read-out resolution step (maximum) | n=4: 59.8034; n=6: 75.2348; n=8: 87.863 | uN | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-05 | absolute (traceable) thrust uncertainty at 12 mN (1 sigma, planning) | 120 | uN | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (LOCK-2 u_abs) | GROUND/FACILITY-ONLY |
| H26-06 | in-situ calibrations before and after each operating sequence (minimum) | 10 | calibrations | analog | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-07 | T/P_bus per-reading combined relative uncertainty (1 sigma) | n=4: 0.0070479; n=6: 0.0088665; n=8: 0.0103548 | relative | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (LOCK-2) | GROUND/FACILITY-ONLY |
| H26-08 | sustained-thrust dwell (hold time) and its zero-drift allowance | - | s | pending | assumed | TBD - requires the owner hold-time decision and the S1b thermal time constants (T-SETTLE) | GROUND/FACILITY-ONLY |
| H26-09 | bus-power channel set at the bus-boundary-equivalent point | hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping; + rf_source (rf_hall); + ecr_source, ecr_magnet (ecr_hall) | - | requirement | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-10 | per-channel power repeatability at the A5 bus allocation and at the RFP ceiling (1 sigma) | n=4: P=1300 W: 6.4787; P=1350 W: 6.72788; P=1500 W: 7.47542; n=6: P=1300 W: 8.15043; P=1350 W: 8.46391; P=1500 W: 9.40435; n=8: P=1300 W: 9.51849; P=1350 W: 9.88458; P=1500 W: 10.9829 | W | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (n fixed at LOCK-2) | GROUND/FACILITY-ONLY |
| H26-11 | ledger efficiencies converting load-plane power to P_bus | - | - | pending | assumed | PENDING docs/hardware/h2/h2_4_ppu_bus/ (LOCK-1 ledger inputs) | FLIGHT-REPRESENTATIVE |
| H26-12 | P_bus gate: largest measured P_bus that passes < 1.5 kW (planning) | 1475.73 | W | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (LOCK-2 u_abs) | GROUND/FACILITY-ONLY |
| H26-13 | discharge-current DC channel range (minimum upper end) | 8.33333 | A | derived | model-derived | TBD - requires the transient margin (W3 HW-ENV-02: supply protection design and S1 transients) | GROUND/FACILITY-ONLY |
| H26-14 | discharge-voltage channel range (minimum upper end) | 350 | V | assumed | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-15 | I_d offset + noise floor within the extinction window (1 sigma) | 0.01 | fraction of I_d,ref | assumed | assumed | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (I_d,ref and window from S1b) | GROUND/FACILITY-ONLY |
| H26-16 | exploratory I_d(t) acquisition: band and minimum sampling rate for the S1b spectrum | band_Hz: [1000, 6e+07]; sampling_min_Sps: 1.2e+08 | Hz / samples s^-1 | analog | assumed | TBD - requires the S1b I_d spectrum on HW-0 (score-bearing band and rate fixed at LOCK-2; W4 INS-04) | GROUND/FACILITY-ONLY |
| H26-17 | anode total-flow range and turndown | min_mgps: 0.029548; max_mgps: 3.14236; turndown: 106.348; overlapping_ranges_min: 3 | mg s^-1 / - / ranges | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-18 | N2 pure-gas MFC path range and overlapping-range count | min_mgps: 0.0118192; max_mgps: 3.14236; turndown: 265.869; overlapping_ranges_min: 4 | mg s^-1 / - / ranges | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-19 | O2 pure-gas MFC path range and overlapping-range count | min_mgps: 0.0124102; max_mgps: 1.88542; turndown: 151.925; overlapping_ranges_min: 4 | mg s^-1 / - / ranges | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-20 | air-surrogate O2 mass-fraction set range and its 1 sigma from the flow ratio | w_O2_range: [0.42, 0.6]; u_w_abs: w=0.42: u=0.01: 0.00344502; u=0.05: 0.0172251; w=0.6: u=0.01: 0.00339411; u=0.05: 0.0169706 | mass fraction | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-21 | Xe cathode MFC capability and full-scale window | design_mgps: 0.1; upper_test_point_mgps: 0.15; design_sccm: 1.02425; upper_sccm: 1.53637; full_scale_window_mgps: [0.15, 0.5]; full_scale_window_sccm: [1.53637, 5.12124] | mg s^-1 / sccm Xe | allocation | model-derived | PENDING docs/hardware/h2/h2_2_cathode_integration/ (C-1 flow path) | GROUND/FACILITY-ONLY |
| H26-22 | Xe cathode flow 1 sigma at 0.10 mg/s and the implied Xe-mass 1 sigma over 15,000 h | relative_u: [0.015, 0.05]; m_xe_1sigma_kg: [0.081, 0.27]; m_xe_design_kg: 5.4 | relative / kg | derived | model-derived | consumed by docs/budgets/xe_ledger/xe_ledger_v1.json (verified; parametric, nothing frozen) (consumer of the measured cathode term) | GROUND/FACILITY-ONLY |
| H26-23 | Xe anode start / transition flow range | - | mg s^-1 | pending | assumed | TBD - requires the lane-14 start parameters and PENDING docs/hardware/h2/h2_3_gas_path_plenum/ | GROUND/FACILITY-ONLY |
| H26-24 | Xe anode flow at every atmospheric Hall reading | 0 | mg s^-1 | requirement | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-25 | feed pressure at IP-UP / manifold / module source chamber (range) | - | Pa | pending | assumed | PENDING docs/hardware/h2/h2_3_gas_path_plenum/ (gas-path conductance: ground P_feed follows mdot) | FLIGHT-REPRESENTATIVE |
| H26-26 | feed temperature at IP-UP | - | K | pending | assumed | TBD - requires owner decision DI-1.10 (feed-gas temperature conditioning) | FLIGHT-REPRESENTATIVE |
| H26-27 | maximum base background pressure for a scoreable Hall-on reading (T-PB-MAX) | planning_scenarios_Torr: [1e-05, 1.3e-05, 5e-05]; p_b_for_ingestion_fraction_at_mdot_min_Torr: per_100cm2: f=0.01: 1.65811e-07; f=0.05: 8.29057e-07; f=0.1: 1.65811e-06; echt_analog_annulus: f=0.01: 5.86438e-07; f=0.05: 2.93219e-06; f=0.1: 5.86438e-06 | Torr | pending | assumed | TBD - requires the owner decision at LOCK-1 from the facility specification | GROUND/FACILITY-ONLY |
| H26-28 | required effective pumping speed at the delivered-flow upper end (N2 3.14 mg/s + Xe cathode 0.15 mg/s) | 1.0e-05 Torr: 212104; 1.3e-05 Torr: 163157; 5.0e-05 Torr: 42420.9 | L s^-1 | derived | model-derived | TBD - requires T-PB-MAX (owner, LOCK-1) and the facility choice (S1-C7 / S1A-C5) | GROUND/FACILITY-ONLY |
| H26-29 | N2 ingestion scale at the lowest candidate anode flow (analog exit annulus) | 1.0e-05 Torr: 0.170521; 1.3e-05 Torr: 0.221677; 5.0e-05 Torr: 0.852605 | fraction of anode mass flow | derived | model-derived | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (H-1 exit area replaces the analog) | GROUND/FACILITY-ONLY |
| H26-30 | background-gauge placement and reading rule | offset_min_chamber_radii: 0.6; distance_from_thruster_OD_min_m: 1; sampling_min_Hz: 10; average_s: 3; settle_after_flow_change_min: 2; flow_change_threshold: 0.1 | - | analog | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-31 | elevated-p_b capability for the S5 facility-effect check | factor: 2; injection_distance_min_m: 2 | x base p_b / m | analog | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-32 | chamber radius that allows the preferred wall-gauge position (analog illustration) | 1.05 | m | derived | model-derived | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (H-1 OD) | GROUND/FACILITY-ONLY |
| H26-33 | B(z) map extent (probe path from beyond the exit plane to the anode face along the mean radius) | - | m | pending | assumed | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (channel length, mean radius, domain length) | H-1 TEST-ARTICLE-ONLY |
| H26-34 | gaussmeter range | hall_channel: PENDING H2-1 B_max; ecr_resonance_zone_if_mapped_T: [0.0875235, 0.207198] | T | derived | model-derived | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ and PENDING docs/interfaces/preionizer_module/ | GROUND/FACILITY-ONLY |
| H26-35 | B(z) map uncertainty | - | T | pending | assumed | TBD - requires the INV-B3 tolerance (HWQ-04) and the W5 B(z) comparison tolerance | GROUND/FACILITY-ONLY |
| H26-36 | B(z) maps per configuration and coil-current cycles (S1a repeatability) | maps: 3; current_cycles: 3 | - | assumed | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-37 | Faraday far-field arc radius (minimum; analog illustration) | 0.4 | m | derived | model-derived | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (H-1 channel diameter) | GROUND/FACILITY-ONLY |
| H26-38 | ExB accelerating bias for resolving m/q 14, 16, 28, 32 at low energy | - | V | pending | assumed | TBD - requires the ExB probe design and the W5 species-fraction tolerance | GROUND/FACILITY-ONLY |
| H26-39 | eta_u measured inputs (operational definition P1DQ-ETAU, lane-06 metric M3) | I_b (INS-15 far-field Faraday), Omega_j and q_j (INS-13 ExB), m_dot_prop and m_dot_c (INS-05); INS-14 RPA supporting; p_b (INS-08) for the charge-exchange correction | - | requirement | assumed | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) | GROUND/FACILITY-ONLY |
| H26-40 | configuration-change procedure: H-1 stays mounted, only the module between IP-UP and IP-DN is exchanged | yes | - | assumed | assumed | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-41 | module carrier: kinematic (exactly-constrained, 6-constraint) seat on the stand moving platform | 3-point kinematic seat (PROPOSED concept) | - | assumed | assumed | PENDING docs/interfaces/preionizer_module/ (mechanical envelope, mounting datum, installation/removal reproducibility item) | GROUND/FACILITY-ONLY |
| H26-42 | module weight path | carried by the module carrier; IP-DN joint is a seal/gas and alignment interface only | - | assumed | assumed | PENDING docs/interfaces/preionizer_module/ | GROUND/FACILITY-ONLY |
| H26-43 | mass on the stand moving platform per configuration | - | kg | pending | assumed | PENDING docs/hardware/h2/h2_7_mechanical_bom/ and PENDING docs/interfaces/preionizer_module/ | GROUND/FACILITY-ONLY |
| H26-44 | heat load into H-1 + mount (upper bound for stand thermal design) | 1500 | W | derived | model-derived | PENDING docs/hardware/h2/h2_5_thermal_network/ (conduction share into the mount) | GROUND/FACILITY-ONLY |
| H26-45 | electrical isolation of H-1 from the stand and facility ground (rating) | 350 | V | assumed | assumed | TBD - requires the owner isolation margin and the HW-ELEC-05 test voltage | GROUND/FACILITY-ONLY |
| H26-46 | non-ferromagnetic exclusion zone around MC-1 (fixture, fasteners, calibrator) | - | m | pending | assumed | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (MC-1 magnetostatic model) and the INV-B3 tolerance (HWQ-04) | GROUND/FACILITY-ONLY |
| H26-47 | thrust-axis alignment change per installation (one RSS share, cosine only) | 2.7044 | deg | derived | model-derived | PRELIMINARY | GROUND/FACILITY-ONLY |
| H26-48 | installation reproducibility of ln(T/P_bus) and the qualification series | u_inst_max_n4: 0.00249181; K_cycles: 6; r_readings: 3 | ln-ratio / - / - | derived | model-derived | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) (n and u_inst at LOCK-2) | GROUND/FACILITY-ONLY |
| H26-49 | service-line bundle inventory (SVC-1) | see fixture.service_line_bundle | - | assumed | assumed | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/, PENDING docs/hardware/h2/h2_2_cathode_integration/ and PENDING docs/interfaces/preionizer_module/ (line counts) | GROUND/FACILITY-ONLY |
| H26-50 | flight telemetry subset | see ground_vs_flight (flight_telemetry_subset = true) | - | assumed | assumed | PENDING docs/hardware/h2/h2_4_ppu_bus/ (PPU telemetry) and the control/FDIR row | FLIGHT-REPRESENTATIVE |
| H26-51 | working-gas purity (N2, O2, Xe) | - | - | pending | assumed | TBD - requires the owner / facility gas specification (no value is sourced here) | GROUND/FACILITY-ONLY |
| H26-52 | O2-service cleaning standard for FS-C and module wetted parts | - | - | pending | assumed | TBD - requires the facility safety case (owner channel) | GROUND/FACILITY-ONLY |

Sources and notes per parameter are in the JSON (`design_parameters[].source`, `.note`).

## (1) Measurement list mapped to the Phase-1 decision quantities

Phase-1 decision quantities (A6 list, framework ids): P1DQ-SUST sustainment; P1DQ-TPBUS T/P_bus; P1DQ-ETAU eta_u; P1DQ-ENVW operating-envelope width; P1DQ-IGN ignition/restart behaviour; P1DQ-STAB stability/oscillation; P1DQ-TABS absolute thrust compatibility; P1DQ-PBUS full bus-power compatibility; P1DQ-NOXE no continuous Xe augmentation

| id | quantity | P1DQ | INS | INS-P | CD | qualifying steps | class |
|---|---|---|---|---|---|---|---|
| H26-MEAS-01 | thrust (paired and absolute) | P1DQ-TPBUS, P1DQ-TABS, P1DQ-STAB, P1DQ-ENVW, P1DQ-SUST | INS-01, INS-17, INS-18 | INS-P-12 | CD-01, CD-02 | S1a: in-situ force calibration, linearity, zero drift, magnetic and line tares, per-configuration calibration with modules/dummies (CD-01); no plasma; S1a: no-plasma module-exchange reproducibility of the stand slope (CD-02a); S1-C4: thrust_stand category of the owner-accepted capability record; S1b: Hall-on u_T, u_inst (K re-installations x r readings at OP3 on HW-0), thermal settling T-SETTLE, drift; Phase 1: score-bearing only after LOCK-2 | GROUND/FACILITY-ONLY |
| H26-MEAS-02 | bus power at the bus-boundary-equivalent point (with H2-4) | P1DQ-TPBUS, P1DQ-PBUS, P1DQ-IGN | INS-02, INS-03, INS-18 | - | CD-03, CD-02 | S1a: channel calibration against a traceable DC standard; RF/microwave load-plane characterisation into matched dummy loads; pickup check (CD-03); S1a: C-1 diode commissioning of keeper/heater channels with Hall discharge physically inhibited (A4 C1_diode_in_S1a; NON_SCORE_BEARING_ENGINEERING_ONLY); S1-C4: bus_power_metering and discharge_current categories; S1b: Hall-on u_P and power-channel re-connection reproducibility; Phase 1: P_bus = sum load-plane power / LOCK-1 ledger efficiency; compressor reconstructed from the upstream ICD (ABSENT_IN_LAB) | GROUND/FACILITY-ONLY |
| H26-MEAS-03 | discharge current I_d (DC and time-resolved) and V_d | P1DQ-SUST, P1DQ-ENVW, P1DQ-IGN, P1DQ-STAB, P1DQ-NOXE, P1DQ-TABS | INS-04, INS-10, INS-18 | INS-P-09 | CD-03, CD-06 | S1a: probe gain/offset, DAQ time base and swept-sine response (CD-03, CD-06); no plasma; S1-C4: discharge_current and (partial) stability_oscillations categories; S1b: I_d spectrum on HW-0 fixes the band, sampling rate, ext_window and I_d,ref; THR-EXTINCTION validated on commanded shutdowns before any score-bearing reading; Phase 1: sustainment classes, knee, restarts | GROUND/FACILITY-ONLY |
| H26-MEAS-04 | atmospheric anode flows (N2, O2 air surrogate) and O2 mass fraction | P1DQ-SUST, P1DQ-ENVW, P1DQ-ETAU, P1DQ-TABS | INS-05, INS-18 | - | CD-04 | S1a: MFC calibration per gas across the range incl. zero drift and orientation (CD-04); calibrated setpoints at released feed points are REG-FEED (custody-held); S1-C4: flow category; S1b: setpoint stability at OP3 on N2 under Hall-on conditions; Phase 1: knee scan down and up; O2 fraction points | GROUND/FACILITY-ONLY |
| H26-MEAS-05 | Xe flows: cathode (0.10-0.15 mg/s capability) and anode start/transition; Xe consumption per mode | P1DQ-NOXE, P1DQ-IGN | INS-05, INS-18 | INS-P-08 | CD-04 | S1a: Xe MFC calibration; C-1 diode commissioning with the Hall discharge inhibited (A4) - start log, keeper/heater, daily Xe reference definition; S1b: first Hall-on ignitions on Xe and transfer to N2 (HW-FS-03); per-mode Xe totals and durations; Phase 1: Xe anode flow = 0 verified at every atmospheric reading; cathode Xe at the design target | GROUND/FACILITY-ONLY |
| H26-MEAS-06 | feed pressure and temperature at IP-UP / manifold / module source chamber | P1DQ-SUST, P1DQ-ENVW | INS-06, INS-07, INS-18 | - | - | S1a: manometer zero/span; cold-flow manifold pressure at each grid flow per configuration (HW-FS-05); S1-C4: pressure category (W4 must add it: uncovered by CD-01..07); S1b: P_feed covariate at OP3 Hall-on | FLIGHT-REPRESENTATIVE |
| H26-MEAS-07 | chamber / background pressure p_b and its effect on Hall operation | P1DQ-SUST, P1DQ-TPBUS, P1DQ-ENVW, P1DQ-TABS, P1DQ-ETAU | INS-08, INS-11, INS-18 | - | - | S1a: gauge calibration; no-flow base pressure and qualitative residual gas (FACILITY_BACKGROUND); cold-flow p_b at released feed points = REG-PB (custody); effective pumping speed by REF-DANKANICH2017 Eq. 9 from those cold-flow points; S1-C4: pressure category (W4 must add it); S1b: Hall-on p_b at the OP3 flow (lane 25 S1b output); S5: p_b raised to 2 x base by downstream injection; class FACILITY_ROBUST or FACILITY_CONDITIONAL; no ingestion model applied | GROUND/FACILITY-ONLY |
| H26-MEAS-08 | magnetic-field mapping B(z) at actual coil currents | P1DQ-TPBUS, P1DQ-SUST | INS-09, INS-24, INS-02, INS-18 | INS-P-07 | CD-05 | S1a: maps per configuration and control state (M0, M0b, M0c), hysteresis cycles, cold and heated-soak maps (CD-05, HW-MC-15); S1-C4: magnetic_field_Bz category; S1b: hot reference sensor logged during firing (HW-MC-04); S_B coil-current scan if adopted (HW-MC-05) | GROUND/FACILITY-ONLY |
| H26-MEAS-09 | oscillation diagnostics (I_d(t) spectrum/amplitude, coupling voltage) | P1DQ-STAB, P1DQ-SUST | INS-04, INS-18, INS-10 | INS-P-09 | CD-06 | S1a: time base and fast-channel response only (CD-06); S1-C4: stability_oscillations category (partial until S1b); S1b: oscillation spectra (A4 S1_C4_categories: S1b supplies them) | GROUND/FACILITY-ONLY |
| H26-MEAS-10 | species / energy / current-density diagnostics (ExB, RPA, Faraday, Langmuir, OES) where feasible | P1DQ-ETAU, P1DQ-TPBUS | INS-13, INS-14, INS-15, INS-16, INS-12 | - | - | S1a: bench calibration only (areas, grid transparency, bias supplies); S1-C4: species_divergence category (W4 must add it or the owner reduces the set); S1b: species/divergence capability on HW-0 (A4: S1b supplies it); Phase 1: eta_u inputs at every scored point where the framework requires them | GROUND/FACILITY-ONLY |
| H26-MEAS-11 | ignition / restart behaviour | P1DQ-IGN, P1DQ-NOXE | INS-04, INS-10, INS-05, INS-18 | INS-P-08, INS-P-09 | CD-06 | S1a: C-1 start log only (heater power, time to ignition, keeper ignition voltage) with the Hall discharge inhibited; S1b: Hall ignition on Xe, transfer to N2, commanded shutdown and restart; Phase 1: restart after extinction at knee points; attempts and timeouts | GROUND/FACILITY-ONLY |
| H26-MEAS-12 | temperatures (stand, mount, H-1, MC-1 coils, C-1 tube, module) | P1DQ-TPBUS, P1DQ-TABS, P1DQ-SUST, P1DQ-IGN | INS-17, INS-23, INS-24, INS-18 | INS-P-07 | CD-07 | S1a: sensor calibration, cold junction, isothermal cross-check, pickup (CD-07); S1-C4: temperature category; S1b: thermal time constants (T-SETTLE) | GROUND/FACILITY-ONLY |
| H26-MEAS-13 | electrical coupling and integrity (cathode-to-ground / anode-to-ground potential, anode 4-wire resistance, insulation resistance) | P1DQ-SUST, P1DQ-TPBUS | INS-02, INS-04, INS-21 | INS-P-06 | - | S1a: baseline anode and insulation resistance; S1b: coupling voltage at OP3; between-block anode resistance | H-1 TEST-ARTICLE-ONLY |
| H26-MEAS-14 | common time base / DAQ | P1DQ-TPBUS, P1DQ-STAB | INS-18 | INS-P-10 | CD-06 | S1a: skew and drift (CD-06) | GROUND/FACILITY-ONLY |
| H26-MEAS-15 | witness-coupon and part metrology, near-cathode gas sampling (life / O exposure evidence; not a Phase-1 decision quantity) | - | INS-19, INS-20, INS-22, INS-11 | INS-P-01, INS-P-02, INS-P-03, INS-P-04, INS-P-05, INS-P-10, INS-P-11, INS-P-12 | - | S1a: baseline metrology before first ignition (INS-P-02); qualitative RGA only unless calibrated (A3) | H-1 TEST-ARTICLE-ONLY |

**Known effect of background pressure on Hall operation (H26-MEAS-07):**

- background neutrals change thrust, cathode coupling and divergence; the facility wall provides current paths absent in orbit (REF-BYRNE2022 Sec. I, accessed by this lane 2026-09-29)
- simple ingestion of background gas is an inadequate explanation of the thrust rise at higher pressure; NASA-173M at 15 A: thrust reduction <= 2.5 % as the chamber pressure was reduced to 6e-6 Torr (range studied ~3e-6 to ~3.5e-5 Torr) (REF-TIGHE2015 abstract, accessed by this lane 2026-09-29; xenon, different thruster - context only)
- SPT-100: below 1e-5 Torr needed to identify the thrust-slope change; discharge-current stability and breathing-mode frequency keep changing into the 1e-6 Torr range; data insufficient for absolute pressure requirements for general designs (REF-DANKANICH2017 p. 678, accessed by this lane 2026-09-29)

## (2) H-1 fixture

H-1 + C-1 + MC-1 are one assembly on the stand's moving platform. The pre-ionizer module (PIM-0 / PIM-RF / PIM-ECR) sits in its own kinematic carrier on the same platform between IP-UP and IP-DN. A configuration change exchanges only the module; the H-1 mount is never unbolted (W3 HW-SVC-04 PROPOSED, HWQ-01). The fixture belongs to the W3 identity-matrix element 'thrust stand, mount, service-line bundle (with shams), grounding and cable routing' (must be identical in every configuration); it is not a new configuration item.

| id | feature | description | class | status |
|---|---|---|---|---|
| H26-FX-01 | H-1 mounting adapter on the stand moving platform | one adapter carries H-1 with MC-1 and the C-1 mount; C-1 position fixed on H-1 and recorded (W3 HW-C1-01); a thermally isolating, electrically insulating interface between adapter and platform (FX-04, FX-05) | GROUND/FACILITY-ONLY | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ and PENDING docs/hardware/h2/h2_7_mechanical_bom/ |
| H26-FX-02 | module slot: kinematic module carrier | a carrier on the moving platform locates each module by an exactly-constrained (6-constraint, 3-point) seat with preload; the module's weight goes through the carrier, not through IP-DN; the IP-DN joint makes only the gas seal and the flange-pattern alignment (same pattern, seals and torque for every module, HW-PIM-01), with a torque-reaction tool so no assembly torque reaches the H-1 mount; IP-UP stays fixed in the stand frame (W3 interface_planes) | GROUND/FACILITY-ONLY | PENDING docs/interfaces/preionizer_module/ (mechanical envelope, mounting datum, installation/removal reproducibility item) |
| H26-FX-03 | service-line bundle SVC-1 fixed routing with shams | every line crossing the stand is present in every configuration; arm-specific lines are shams in the other configurations (RF coax and microwave feed in HW-0, terminated off-stand); lines cross from the stand base to the moving platform orthogonal to the thrust axis with fixed loops; gas lines in solid metal tubing (REF-POLK2017); per-configuration line tare in the in-situ calibration | GROUND/FACILITY-ONLY | PRELIMINARY |
| H26-FX-04 | thermal isolation and stand thermal control | low-conductance standoffs between the H-1 adapter and the platform; stand thermal shroud / active cooling of critical stand components (REF-POLK2017); thermocouples on the adapter, standoffs, platform and module carrier; module waste heat into H-1 either isolated at IP-DN or instrumented (W3 HW-PIM-09) | GROUND/FACILITY-ONLY | PENDING docs/hardware/h2/h2_5_thermal_network/ |
| H26-FX-05 | electrical isolation of the stand | H-1 body isolated from the platform and facility ground (thruster floats, W3 HW-ELEC-01) with isolation rated >= 350 V + margin; the same grounding scheme and cable routing in every arm; RF and microwave returns separate from the discharge return (HW-ELEC-03); module body potential declared identically for PIM-0 (HW-ELEC-02, HWQ-07); the gas isolator is upstream of IP-UP (HW-FS-06) | GROUND/FACILITY-ONLY | TBD - requires the owner isolation margin (HW-FS-06 / HW-ELEC-05) and PENDING docs/interfaces/preionizer_module/ (module potential) |
| H26-FX-06 | non-ferromagnetic fixture and magnetic tare | no ferromagnetic fixture part, fastener or calibrator part inside the MC-1 exclusion zone (H26-46); magnetic tare characterised across coil settings and, for PIM-ECR, magnet on/off (REF-POLK2017; W3 HW-SVC-05); M0 vs M0b B(z) map shows the fixture within INV-B3 | GROUND/FACILITY-ONLY | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| H26-FX-07 | remount-reproducibility features | fiducials on the H-1 exit rings (HW-H1-11) and the module carrier; an alignment reference (mirror or inclinometer seat) on the H-1 adapter read before and after every exchange; dowelled carrier; documented torque and sequence; serial/part log (HW-H1-02) | H-1 TEST-ARTICLE-ONLY | PRELIMINARY |
| H26-FX-08 | diagnostic access on H-1 and fixture | B(z) probe guide keyed to the H-1 exit fiducials (probe path to the anode face with any module installed, HW-H1-08); manifold and module source-chamber pressure ports (HW-FS-04); near-cathode RGA sampling inlet (INS-22, HW-C1-07); cathode-tube thermocouple and pyrometer line of sight where possible (HW-C1-09); anode sense lead (HW-ELEC-04); MC-1 reference field sensor (HW-MC-04); witness holder outside the beam core (HW-SVC-06) | H-1 TEST-ARTICLE-ONLY | PENDING docs/hardware/h2/h2_2_cathode_integration/ |
| H26-FX-09 | in-situ force calibrator | applies known forces on the thrust axis at the H-1 thrust-axis height, with the force line aligned with the thrust vector (REF-POLK2017); span H26-01..H26-02; >= 10 calibrations before and after (H26-06) | GROUND/FACILITY-ONLY | PRELIMINARY |
| H26-FX-10 | stand principle and inclination | torsional (response independent of the mass on the stand) or inverted pendulum with active inclination control (REF-POLK2017; W4 INS-01); because the module mass changes between arms, either a mass-independent response or a full calibration per configuration (HW-SVC-02) is required - both are carried, the owner chooses | GROUND/FACILITY-ONLY | TBD - requires the owner stand-principle decision (W4 open owner decision) |

**SVC-1 service-line bundle (present in every configuration):**

| line | used by | sham in |
|---|---|---|
| anode gas feed (after the gas isolator) to IP-UP | all | - |
| C-1 Xe gas line (own MFC, never crosses HALL_INLET_Z0) | all | - |
| discharge anode and cathode-common leads | all | - |
| keeper leads; heater leads | all | - |
| MC-1 coil leads + 4-wire potential leads per coil | all | - |
| anode 4-wire sense lead (HW-ELEC-04) | all | - |
| thermocouples (H-1, wall rings, coupons, coil hot spots, C-1 tube, adapter, carrier) | all | - |
| MC-1 reference field sensor cable (HW-MC-04, if adopted) | all | - |
| module source-chamber pressure port line (blanked or connected identically in PIM-0, HW-FS-04) | all | hall_only |
| near-cathode RGA sampling tube (INS-22) | all | - |
| RF coax to PIM-RF | rf_hall | hall_only, ecr_hall |
| microwave feed (waveguide or coax) to PIM-ECR | ecr_hall | hall_only, rf_hall |
| ECR magnet leads (electromagnet option, HWQ-05) | ecr_hall | hall_only, rf_hall |
| module enable / interlock / control lines | all | hall_only |

**Remount reproducibility.** u_inst of ln(T/P_bus) <= lane-25 u_inst,max at the n fixed at LOCK-2 (0.249 % at n = 4, W3 HW-SVC-03), unless a no-vent switch (D-06-B) is adopted. CD-02a (S1a, no plasma) and S1b (Hall-on at OP3 on HW-0) both replicate exactly the adopted configuration-change procedure: K = 6 cycles x r = 3 readings (lane 25 PROPOSED); nu = K - 1. ICD item: PENDING docs/interfaces/preionizer_module/: the installation/removal reproducibility item of the common pre-ionizer interface (the in-progress ICD draft, read-only, names it PMI-11; not consumed here - confirmed at the integration pass).

| contributor | features | measured in |
|---|---|---|
| c1 stand calibration and zero shift | H26-FX-09, H26-FX-10, H26-FX-03 | S1a CD-01 (per-configuration calibration); S1a CD-02a; S1b |
| c2 thrust-axis alignment | H26-FX-01, H26-FX-02, H26-FX-07 | S1a CD-02a (alignment reference reading per cycle); S1b |
| c3 magnetic-circuit / B(z) change | H26-FX-06 | S1a CD-05 / HW-MC-03 map before and after each exchange; S1b |
| c4 gas path, distributor and leak change | H26-FX-02 | S1a HW-FS-05 cold-flow manifold pressure and leak check per exchange; S1b |
| c5 service-line, thermal and electrical environment change | H26-FX-03, H26-FX-04, H26-FX-05 | S1a CD-02a power-channel gain check per cycle; S1b |

**Proposed configuration-change procedure:**

1. record alignment reference and module-carrier seating before venting
2. vent; release the IP-DN seal joint with the torque-reaction tool; lift the module from its carrier
3. seat the next module in the carrier; make the IP-DN seal at the ICD torque; connect module lines at their fixed break points (shams for absent arms)
4. leak check; cold-flow manifold pressure at each grid flow (HW-FS-05)
5. pump down; alignment reference and carrier seating re-read; B(z) map in the control states (HW-MC-03)
6. in-situ thrust-stand calibration (>= 10 calibrations, HW-SVC-02); dummy-load pickup check for source arms

## (3) Facility requirements

| id | requirement | values | stage | status |
|---|---|---|---|---|
| H26-FAC-01 | effective pumping speed at the thruster exit plane S_eff = Q / (p_b - p_base) (REF-DANKANICH2017 Eq. 9, p. 673) sufficient to hold T-PB-MAX at the total grid flow (anode + cathode), reported per gas (N2, O2, Xe) | H26-28; derived.S_eff_required | S1a cold flow (REG-PB custody) and S1b Hall-on | TBD - requires T-PB-MAX (owner, LOCK-1) and the facility choice |
| H26-FAC-02 | background gauges placed and operated per REF-DANKANICH2017 pp. 672-673 and calibrated on N2 and the O2/N2 mixture | H26-30 | S1a | PRELIMINARY |
| H26-FAC-03 | ability to raise p_b to 2 x base by downstream injection >= 2 m with a pumping surface between injection and gauge (S5) | H26-31 | S5 | PRELIMINARY |
| H26-FAC-04 | one facility, stand and mount procedure for S1b and every score-bearing stage (REQ-FAC-05) | - | S1b onward | PRELIMINARY |
| H26-FAC-05 | gas supply: separate pure N2 and O2 supplies metered by one MFC per pure gas (INS-05) and mixed at one point upstream of IP-UP (HW-FS-02); O2 mass fraction 0.42-0.60 set by the flow ratio; Xe for start, transfer, health check and C-1 | H26-17..H26-21, H26-51 | S1a | PRELIMINARY |
| H26-FAC-06 | O2 safety case before any O2 flow (see o2_safety) | H26-52 | before the first O2-bearing flow (S1a cold flow) | TBD - requires the facility safety case (owner channel; REQ-FAC-04) |
| H26-FAC-07 | chamber size allowing the preferred wall-gauge position and the Faraday far-field arc | H26-32, H26-37 | facility choice | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ (H-1 OD) |

**Required effective pumping speed (L/s):**

| case | 1.0e-05 Torr | 1.3e-05 Torr | 5.0e-05 Torr |
|---|---|---|---|
| anode_N2_at_mdot_max | 209967 | 161513 | 41993.4 |
| anode_surrogate_wO2_min_at_mdot_max | 198944 | 153034 | 39788.7 |
| anode_surrogate_wO2_max_at_mdot_max | 194219 | 149400 | 38843.9 |
| cathode_Xe_design | 1424.91 | 1096.09 | 284.982 |
| cathode_Xe_upper | 2137.37 | 1644.13 | 427.473 |
| total_N2_mdot_max_plus_Xe_upper | 212104 | 163157 | 42420.9 |
| sensitivity_N2_at_mdot_max_with_accumulation | 363943 | 279956 | 72788.5 |

planning scenarios only (xenon/SPT-100 derived pressures, REF-DANKANICH2017 Sec. V); the anode upper end is the W1 no-backflow upper bound; the with-accumulation row is W1 MFC headroom only (FC-08). Published comparison: the Aerospace EP2 facility is quoted with a xenon pumping speed of ~250 kL/s (REF-TIGHE2015 Sec. II.A) - a xenon figure, not an N2/O2 figure.

**N2 ingestion scale (one-way background flux x exit area / anode flow):**

| area | flow | 1.0e-05 Torr | 1.3e-05 Torr | 5.0e-05 Torr |
|---|---|---|---|---|
| per_100cm2 | at_mdot_anode_min | 0.603095 | 0.784023 | 3.01547 |
| per_100cm2 | at_mdot_anode_max | 0.00567098 | 0.00737227 | 0.0283549 |
| echt_analog_annulus | at_mdot_anode_min | 0.170521 | 0.221677 | 0.852605 |
| echt_analog_annulus | at_mdot_anode_max | 0.00160343 | 0.00208446 | 0.00801716 |

one-way background N2 mass flux over the exit area divided by the anode flow; a scale, never a correction and never applied to rescue a class (lane 25 Sec. 8).

**O2 safety:**

- O2 cleanliness of every wetted part of FS-C and the modules - W3 HW-FS-07; REF-NSS1740-15 Sec. 104 c ('Oxygen systems shall be kept clean because organic compound contamination, such as hydrocarbon oil, can ignite easily'); cleaning-level selection guide REF-ASTM-G93 (not accessed - verify) (TBD - requires the facility safety case)
- pump lubricants and pump type compatible with O2 throughput - REF-EDWARDS-RV ('Where a high concentration of oxygen or other chemically reactive gases are present', highly inert man-made lubricants are recommended) (TBD - facility data)
- cryopump oxidizer accumulation and ozone: regeneration frequency, oxygen concentration during roughing, inert-gas dilution of the exhaust - REF-ULVAC-CRYO ('Explosion occurring from ozone in the cryopump could cause severe injury'; ozone as a by-product when oxygen is a process gas; 'Regenerate as frequently and periodically as practical to minimize the amount of oxidizer present in the cryopump'; inert purge of the exhaust line) (TBD - facility data; the plasma is an ionizing process (ozone formation is plausible, not quantified here))
- two independent barriers or safeguards so that two simultaneous undesired events are needed before injury - REF-NSS1740-15 Sec. 104 f (PRELIMINARY)
- interlocks: IL-OXIDIZER-ISOLATION, IL-VACUUM, IL-EMERGENCY-STOP, Hall-discharge inhibit in S1a; limits from real hardware/facility ratings, not invented thresholds - S1a gate S1A-C2 (PROPOSED ids); A4 S1a_minimum_interlocks and S1a_interlock_limits (PRELIMINARY)
- hot LaB6 emitter with O2 present: Xe flow whenever the emitter is hot and O2-bearing gas is in the chamber; purge before heating - W3 HW-C1-03 (G&K Sec. 6.8.5 via lane 19) (PRELIMINARY)
- room oxygen-concentration monitoring near vents and exhausts - assumed (engineering practice; no source cited) (TBD - requires the facility safety case)

## (4) Ground-only vs flight-representative diagnostics

| diagnostic | class | flight telemetry subset | flight counterpart |
|---|---|---|---|
| thrust stand (INS-01) | GROUND/FACILITY-ONLY | no | none (thrust is not measured in flight) |
| lab precision power metering per channel (INS-02, INS-03) | GROUND/FACILITY-ONLY | no | PPU per-channel V and I telemetry |
| PPU per-channel output V and I (discharge, magnet, keeper, heater, source) | FLIGHT-REPRESENTATIVE | yes | itself |
| discharge current and voltage DC telemetry | FLIGHT-REPRESENTATIVE | yes | itself |
| wide-band I_d(t) probe and fast DAQ (INS-04 fast channel) | GROUND/FACILITY-ONLY | no | I_d ripple (rms) telemetry if H2-4 provides it |
| I_d ripple / oscillation amplitude telemetry | FLIGHT-REPRESENTATIVE | yes | candidate; PENDING docs/hardware/h2/h2_4_ppu_bus/ |
| thermal MFCs N2 / O2 / Xe (INS-05) | GROUND/FACILITY-ONLY | no | metering-valve and Xe-metering states |
| atmospheric metering-valve command/state; Xe regulator/metering state; valve states | FLIGHT-REPRESENTATIVE | yes | itself |
| feed pressure / temperature at the valve outlet (flight sensor at the IP-UP-equivalent plane) | FLIGHT-REPRESENTATIVE | yes | PENDING docs/hardware/h2/h2_3_gas_path_plenum/ |
| capacitance manometers at manifold and module source chamber (INS-06) | GROUND/FACILITY-ONLY | no | flight feed-pressure sensor |
| Xe tank pressure and temperature | FLIGHT-REPRESENTATIVE | yes | itself (stored-Xe subsystem of docs/budgets/xe_ledger/, verified) |
| background-pressure ion gauges, RGA (INS-08, INS-11, INS-22) | GROUND/FACILITY-ONLY | no | none |
| B(z) gaussmeter and positioning stage (INS-09) | GROUND/FACILITY-ONLY | no | coil-current telemetry |
| magnet coil current telemetry; coil temperature from coil resistance | FLIGHT-REPRESENTATIVE | yes | itself |
| MC-1 reference field sensor (HW-MC-04) | H-1 TEST-ARTICLE-ONLY | no | none |
| ExB, RPA, Faraday, Langmuir, OES (INS-12..16) | GROUND/FACILITY-ONLY | no | none |
| anode / body temperature; cathode-tube temperature | FLIGHT-REPRESENTATIVE | yes | itself (tube, never labelled emitter) |
| life-mechanism thermocouples at wall rings and coupons; coil hot-spot thermocouples (INS-23, INS-24) | H-1 TEST-ARTICLE-ONLY | no | none |
| stand, adapter and carrier thermocouples (INS-17) | GROUND/FACILITY-ONLY | no | none |
| anode 4-wire resistance lead, insulation-resistance access (INS-21) | H-1 TEST-ARTICLE-ONLY | no | none |
| cathode-to-ground coupling potential | FLIGHT-REPRESENTATIVE | yes | cathode-to-spacecraft potential, candidate; PENDING docs/hardware/h2/h2_4_ppu_bus/ |
| start log: heater time, keeper ignition voltage, attempts, sequence timing | FLIGHT-REPRESENTATIVE | yes | control/FDIR |
| witness coupons, holders and external metrology (INS-19, INS-20) | H-1 TEST-ARTICLE-ONLY | no | none |
| common time base / DAQ (INS-18) | GROUND/FACILITY-ONLY | no | spacecraft time tagging (outside this lane) |

## (b) Interface demands

| from | to | quantity | value | units | status |
|---|---|---|---|---|---|
| fo_h2_1_hall_chamber_magnet | fo_h2_6_diagnostics_fixture | channel mean radius, exit OD, channel length and domain length | analog context only: ECHT 86 mm / 10 mm / 100 mm OD | m | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| fo_h2_1_hall_chamber_magnet | fo_h2_6_diagnostics_fixture | design B_max on the channel centreline and coil count / max current | - | T / A | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| fo_h2_1_hall_chamber_magnet | fo_h2_6_diagnostics_fixture | H-1 rear flange (IP-DN) pattern, exit-ring fiducial positions, thermocouple points | - | - | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| fo_h2_6_diagnostics_fixture | fo_h2_1_hall_chamber_magnet | B(z) probe path to the anode face with any module installed (HW-H1-08) and a probe-guide seat keyed to exit fiducials | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | fo_h2_1_hall_chamber_magnet | non-ferromagnetic exclusion-zone extent around MC-1 for the fixture | - | m | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| fo_h2_2_cathode_integration | fo_h2_6_diagnostics_fixture | C-1 mount position on H-1, keeper/heater V-I ranges, tube-TC and pyrometer view, near-cathode sampling inlet position | - | - | PENDING docs/hardware/h2/h2_2_cathode_integration/ |
| fo_h2_6_diagnostics_fixture | fo_h2_2_cathode_integration | Xe cathode MFC capability and full-scale window | 0.10-0.15 mg/s capability; FS 0.15-0.50 mg/s (H26-21) | mg s^-1 | PRELIMINARY |
| fo_h2_3_gas_path_plenum | fo_h2_6_diagnostics_fixture | IP-UP location in the stand frame, gas-isolator position, manifold and source-chamber port positions, P_feed vs mdot conductance | - | - | PENDING docs/hardware/h2/h2_3_gas_path_plenum/ |
| fo_h2_6_diagnostics_fixture | fo_h2_3_gas_path_plenum | flight-representative feed pressure/temperature sensors at the valve outlet (telemetry subset) | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | fo_h2_3_gas_path_plenum | per-gas MFC paths and overlapping ranges for ground supply | N2 0.0118-3.14 mg/s, O2 0.0124-1.89 mg/s, 4 ranges each at the 20 % FS floor (H26-18/19) | mg s^-1 | PRELIMINARY |
| fo_h2_4_ppu_bus | fo_h2_6_diagnostics_fixture | per-component ledger efficiencies (bus_power_boundary_v1) and PPU telemetry channel list incl. I_d ripple and coupling potential | - | - | PENDING docs/hardware/h2/h2_4_ppu_bus/ |
| fo_h2_6_diagnostics_fixture | fo_h2_4_ppu_bus | lab load-plane measurement points identical to the PPU output terminals per component (bus-boundary-equivalent point) | hall_discharge ... ecr_magnet | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | fo_h2_5_thermal_network | heat into H-1 + mount (upper bound for stand thermal design) | 1500 | W | PRELIMINARY |
| fo_h2_5_thermal_network | fo_h2_6_diagnostics_fixture | conductive share into the mount; module waste heat at IP-DN; thermal time constants for T-SETTLE planning | - | W / s | PENDING docs/hardware/h2/h2_5_thermal_network/ |
| fo_h2_7_mechanical_bom | fo_h2_6_diagnostics_fixture | mass on the stand moving platform per configuration (H-1 + C-1 + MC-1; PIM-0 / PIM-RF / PIM-ECR) | - | kg | PENDING docs/hardware/h2/h2_7_mechanical_bom/ |
| fo_h2_6_diagnostics_fixture | fo_h2_7_mechanical_bom | fixture items are test-article/ground-only and excluded from the flight mass model (FX-01..FX-10) | excluded | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | fo_preionizer_module_icd | module mechanical envelope and mounting datum compatible with a kinematic carrier; module weight not carried by IP-DN | required | - | PENDING docs/interfaces/preionizer_module/ |
| fo_h2_6_diagnostics_fixture | fo_preionizer_module_icd | installation/removal reproducibility item measured by CD-02a and S1b with the procedure of fixture.configuration_change_procedure_proposed | u_inst <= 0.249 % (n = 4) | ln-ratio | PENDING docs/interfaces/preionizer_module/ |
| fo_h2_6_diagnostics_fixture | fo_preionizer_module_icd | service-line routing: RF coax, microwave feed, ECR magnet and module control lines present as shams in the other arms (SVC-1) | required | - | PENDING docs/interfaces/preionizer_module/ |
| fo_h2_6_diagnostics_fixture | fo_preionizer_module_icd | source-chamber pressure port in every module and blanked/connected identically in PIM-0 (HW-FS-04); I_src access (HW-PIM-07) | required | - | PENDING docs/interfaces/preionizer_module/ |
| fo_h2_6_diagnostics_fixture | fo_xe_system_ledger | measured Xe per mode (cathode, startup, transition, fallback) from totalized Xe MFC flows and logged durations | cathode term 1 sigma 0.081-0.27 kg over 15,000 h (H26-22) | kg | consumed by docs/budgets/xe_ledger/xe_ledger_v1.json (verified; parametric, nothing frozen) |
| fo_h2_6_diagnostics_fixture | fo_phase1_prereg_framework | measurement map of the nine P1DQ-* decision quantities to instruments and qualification stages (measurement_map; every DECISIVE / CONDITION ins_id of each P1DQ measurement_chain is covered, checked by the test) | required | - | PRELIMINARY (framework verified; this map is an input to LOCK-1) |
| fo_phase1_prereg_framework | fo_h2_6_diagnostics_fixture | LOCK-2 numeric boundaries: n, u_T / u_P / u_inst, dwell, ext_window, I_d band and sampling, zero band of the Xe MFC | - | - | UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability (docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json threshold_status_literal) |
| fo_h2_6_diagnostics_fixture | fo_subsystem_maturity_matrix | proposed M16 rows (m16_rows) | 4 rows | - | PENDING docs/budgets/subsystem_maturity/ |
| fo_h2_6_diagnostics_fixture | H-1 | test-article-only provisions do not alter the flight-representative flow path or anode area (HW-H1-09 rule) | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | IP-DN | seal/alignment joint only; no module part downstream of IP-DN (HW-H1-06) | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | IP-UP | fixed in the stand frame; the feed line upstream never moves between configurations | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | HALL_INLET_Z0 | no diagnostic, probe or fixture part changes the inlet state setting; the inlet state remains a result, not a setting | required | - | PRELIMINARY |
| fo_h2_6_diagnostics_fixture | SVC-1 | line inventory with shams (fixture.service_line_bundle) | 14 line groups | - | PRELIMINARY |

## (c) Hard-incompatibility check

**Verdict: none found.** Evidence class: model-derived (from sourced inputs) + published recommended practice. Checked:

- G1_thrust / absolute thrust gate measurability: a stand spanning 0 to >= 25.42 mN with ~60-88 uN per-reading 1 sigma at 12 mN is a stated recommended-practice class of instrument (REF-POLK2017; REF-XU2009 abstract gives a 1 mN - 5 N null-type example - verify); achievability is a test-readiness item (S1b), not an incompatibility
- G2_bus_power measurability at the bus-boundary-equivalent point: every bus_power_boundary_v1 component has a load-plane measurement or a ledger input; the compressor is reconstructed (never zero) - partial boundary until H2-4 efficiencies and the upstream ICD exist
- G6_ignition_sustainment measurability: I_d(t) + THR-EXTINCTION logic + p_b per reading; the ingestion scale at the lowest candidate flow is large (H26-29) - a validity threat to the knee measurement that the S5 check and T-PB-MAX handle, not a hardware incompatibility
- G7_air_xenon: the gas supply (pure N2, O2, Xe MFCs, single mixing point) covers N2, the air surrogate and Xe; atomic O is not reproduced by the minimum hardware (W3 HW-ENV-07, HWQ-11) - a recorded representativeness limitation, not an incompatibility
- module exchange vs H-1 alignment: a kinematic carrier keeps module weight and assembly torque off the H-1 mount; nothing downstream of IP-DN changes
- flight representativeness: all test-article provisions are removable/additive and must not alter the flow path or anode area (HW-H1-09); the flight telemetry subset uses only quantities a PPU/controller can provide
- O2 service in the facility: hazards are known and addressed by procedure/design (cleaning, lubricants, cryopump regeneration, two barriers); a facility-selection constraint, not an architecture veto
- effective pumping speed: the required S_eff at the delivered-flow upper end is large (2.121e+05 L/s at 1e-5 Torr, 4.242e+04 L/s at 5e-5 Torr) - it constrains facility choice and T-PB-MAX; the knee region (low flow) needs far less throughput

## (d) Architecture-changing blockers touched (A7)

- **Blocker 1** (Hall-only sustainment at the actual atmospheric feed state, especially low flow and high O2 fraction): defines the measurement chain that decides it (I_d(t) + extinction logic, per-gas MFC paths down to 0.012 mg/s per gas and w_O2 0.42-0.60, feed pressure/temperature, p_b with every reading, S5 elevated-p_b check) and flags that the background-ingestion scale is largest at the low-flow knee; decides nothing
- **Blocker 2** (incremental benefit of RF/ECR after full bus-power accounting): same power channels at the same load planes in every arm incl. rf_source / ecr_source / ecr_magnet and generator DC input as efficiency evidence; the module-exchange fixture and SVC-1 shams keep installation effects out of R_arch; compressor stays reconstructed until the upstream ICD exists
- **Blocker 3** (Xe/cathode closure (no continuous Xe assistance; cathode Xe within the mass allocation)): Xe anode flow verified zero at every atmospheric reading; Xe cathode MFC with a full-scale window keeping 0.10 and 0.15 mg/s >= 20 % FS; per-mode Xe totals for the Xe ledger

## (e) M16 rows (proposed)

| subsystem | matured by this lane | proposed state | blocking item | rollup |
|---|---|---|---|---|
| sensors/diagnostics | primary: ground diagnostic chain for the nine P1DQ quantities, qualification path S1a / S1-C4 / S1b, flight telemetry subset (ground_vs_flight) | BLOCKED | owner facility identification with a documented N2/O2 effective pumping speed at the delivered-flow region and an O2 safety case (S1A-C5 / S1-C7 artifact; T-PB-MAX at LOCK-1) | test-readiness blocker |
| mechanical/structural interfaces | H-1 test fixture and module slot only (the flight structure is H2-7's) | BLOCKED | fo_preionizer_module_icd mechanical envelope + mounting datum and installation/removal reproducibility items (docs/interfaces/preionizer_module/) | hardware-definition blocker |
| control/FDIR | contribution: S1a interlock list and flight telemetry subset | RUNNING | - | - |
| RF pre-ionization module interface (reserved row) | contribution: fixture slot, SVC-1 shams, diagnostic access demands | RUNNING | - | - |

## (f) H3 procurement inputs (long-lead)

- **thrust stand with in-situ calibrator (INS-01)**: principle (torsional or inverted pendulum, null-type preferred; owner decision), calibrated span 0 to >= H26-02, resolution <= H26-04, per-reading 1 sigma H26-03 (LOCK-2), mass capacity per H26-43 (PENDING H2-7), non-ferrous construction, thermal control, SI-traceable force calibration through an ISO/IEC 17025 scope (A4) (no product selected; published catalog data as reference only, no supplier contact)
- **module carrier and H-1 adapter (fixture)**: kinematic seat concept, envelope and datum from the pre-ionizer ICD (PENDING), non-ferromagnetic, isolation rating H26-45 (no product selected; published catalog data as reference only, no supplier contact)
- **mass-flow controllers (INS-05)**: one per pure gas: N2 and O2 paths with 4 overlapping ranges each (H26-18/19), Xe cathode FS 0.15-0.50 mg/s (H26-21), Xe anode start range TBD; O2-cleaned; calibration on each gas, traceable, <= 12 months (REF-SNYDER2017 via W4); A4: at least three ranges per gas path (no product selected; published catalog data as reference only, no supplier contact)
- **power metering (INS-02) and RF/microwave load-plane sensors (INS-03)**: one simultaneously sampled V/I channel per bus_power_boundary_v1 component, per-channel repeatability H26-10 (LOCK-2), SI-traceable DC and RF/microwave calibration through an ISO/IEC 17025 scope (A4); frequencies not selected (HW-PIM-11) (no product selected; published catalog data as reference only, no supplier contact)
- **wide-band discharge-current probe and fast DAQ (INS-04, INS-18)**: exploratory band and sampling H26-16; common time base; simultaneous V and I (no product selected; published catalog data as reference only, no supplier contact)
- **pressure instruments (INS-06, INS-08)**: capacitance manometers (range PENDING H2-3), hot-cathode ion gauges calibrated on N2 and O2/N2, >= 10 Hz (H26-30) (no product selected; published catalog data as reference only, no supplier contact)
- **gaussmeter and positioning stage (INS-09)**: range H26-34 (PENDING H2-1 B_max), probe calibration in a reference field, stage keyed to H-1 fiducials (no product selected; published catalog data as reference only, no supplier contact)
- **RGA with near-cathode sampling (INS-11, INS-22)**: quantitative O2/N2/H2O capability for the AO programme (A3) (no product selected; published catalog data as reference only, no supplier contact)
- **plume diagnostics (INS-13..16)**: ExB with accelerating bias (H26-38), multi-grid RPA, guarded Faraday array on an arc >= H26-37, Langmuir probes - 'where feasible' (no product selected; published catalog data as reference only, no supplier contact)
- **thermocouples / pyrometer (INS-17, INS-23, INS-24)**: types and ranges PENDING H2-5; pyrometer only if the C-1 view exists (HW-C1-09) (no product selected; published catalog data as reference only, no supplier contact)
- **vacuum facility (owner channel)**: S_eff per H26-28 at T-PB-MAX, gauge positions H26-30/32, elevated-p_b injection H26-31, O2 safety case H26-FAC-06; facility selection and any contact are the owner's (no facility named or contacted)
- **witness-coupon metrology lab**: per the approved metrology measurement specification (A4: approved as the procurement specification) (no laboratory named or contacted)

## (g) H4 test inputs

| closes | stage | measure |
|---|---|---|
| H26-03, H26-04, H26-06, H26-07 | S1a CD-01 then S1b | force calibration repeatability, resolution, drift; Hall-on u_T at OP3 |
| H26-02, H26-05, H26-12 | LOCK-2 | adopted u_abs from the S1 calibration uncertainty budget |
| H26-08 | S1b | thermal time constants and zero drift over the dwell |
| H26-10, H26-11 | S1a CD-03, S1b, LOCK-1 | channel calibration; ledger efficiencies (H2-4) |
| H26-13, H26-15, H26-16 | S1b | I_d spectrum on HW-0, transients, I_d,ref |
| H26-17..H26-22 | S1a CD-04 | per-gas MFC calibration across the ranges, zero drift, orientation |
| H26-25, H26-26 | S1a cold flow | P_feed and T_feed at each released flow |
| H26-27, H26-28, H26-29 | S1a cold flow + S1b + S5 | S_eff by Eq. 9 on each gas; Hall-on p_b at OP3; 2 x p_b check |
| H26-33..H26-36 | S1a CD-05 | B(z) repeatability and hysteresis per configuration |
| H26-37..H26-39 | S1b | species/divergence capability on HW-0 |
| H26-47, H26-48 | S1a CD-02a then S1b | K = 6 module-exchange cycles x r = 3; alignment reference; c1..c5 split |
| H26-44, H26-45, H26-46 | S1a | stand thermal drift with heat applied, isolation test, magnetic tare and M0/M0b maps |

## (h) Milestones

- **A:** supports conditional selection as a precondition only: it defines the measurement chain and the H-1 fixture needed for the controlled HW-0 / HW-RF / HW-ECR experiment whose outcome (A / B / C / NO_VIABLE_CASE) is decided by measurement; no architecture is selected, ranked or eliminated here
- **B:** physics-backed selection needs measured data: S1a -> LOCK-1 -> S1/S1b -> LOCK-2 -> Phase 1-3 with the instruments here demonstrated (S1-C4), and an admitted Hall closure for absolute performance (credible set empty)
- **C:** proposal/PDR freeze needs the flight telemetry subset integrated with the PPU (H2-4) and control/FDIR, and the fixture/test-article items kept out of the flight mass (H2-7)

## Pending lanes (values marked PENDING)

- `fo_preionizer_module_icd` - `docs/interfaces/preionizer_module/`: PMI-xx items (A6 list): mechanical envelope + mounting datum, gas path, service-line routing, permitted magnetic disturbance, diagnostics, installation/removal reproducibility
- `fo_subsystem_maturity_matrix` - `docs/budgets/subsystem_maturity/`: M16 row ids and scheduler states
- `fo_h2_1_hall_chamber_magnet` - `docs/hardware/h2/h2_1_hall_chamber_magnet/`: H-1 channel geometry, exit OD, domain length, B_max, coil count/current, rear flange (IP-DN), fiducials
- `fo_h2_2_cathode_integration` - `docs/hardware/h2/h2_2_cathode_integration/`: C-1 mount position, keeper/heater ranges, cathode-tube TC and pyrometer view, near-cathode sampling inlet
- `fo_h2_3_gas_path_plenum` - `docs/hardware/h2/h2_3_gas_path_plenum/`: IP-UP location, gas isolator, feed-pressure/temperature ports, conductance (P_feed vs mdot), flight sensors
- `fo_h2_4_ppu_bus` - `docs/hardware/h2/h2_4_ppu_bus/`: per-component ledger efficiencies, PPU telemetry channel list, I_d ripple telemetry capability
- `fo_h2_5_thermal_network` - `docs/hardware/h2/h2_5_thermal_network/`: heat into the mount, module waste heat at IP-DN, thermocouple positions, thermal time constants
- `fo_h2_7_mechanical_bom` - `docs/hardware/h2/h2_7_mechanical_bom/`: masses on the stand per configuration, mounting interface, envelope

## Owner questions (PROPOSED)

- **H26Q-01**: T-PB-MAX: set with the low-flow knee in view? The ingestion-scale planning table (H26-27, H26-29) is offered as an aid; the fractions are PROPOSED
- **H26Q-02**: stand principle (torsional vs inverted pendulum) given the module mass change between arms (W4 open decision; FX-10)
- **H26Q-03**: adopt the kinematic module carrier (module weight off IP-DN, H-1 never unbolted) as the fixture concept for the ICD installation/removal item?
- **H26Q-04**: per-gas MFC paths: 4 overlapping ranges per pure-gas path at the 20 % FS floor (H26-18/19) vs A4 'at least three per gas path' computed on the total flow
- **H26Q-05**: exploratory I_d(t) chain to the literature planning band edge (60 MHz, abstract-level source) for S1b, or a narrower band recorded as such?
- **H26Q-06**: flight telemetry subset (ground_vs_flight) as the input to H2-4 / control-FDIR
- **H26Q-07**: O2 safety case ownership and the cleaning standard (H26-52)

## References

- **REF-DANKANICH2017**: J. W. Dankanich, M. L. R. Walker, M. W. Swiatek, J. T. Yim, 'Recommended Practice for Pressure Measurement and Calculation of Effective Pumping Speed in Electric Propulsion Testing', J. Propulsion and Power 33(3):668-680 (2017), doi:10.2514/1.B35478 <https://hpepl.ae.gatech.edu/sites/default/files/Journal_Articles/JPP%20V33%20No3%20MayJune2017_PressureMeasurement.pdf>. Access: full text accessed by this lane 2026-09-29 (author-lab PDF, pdftotext): p. 670 ('industry standard gas is nitrogen' for gauge calibration); p. 672 (reference gauge near the wall in the exit plane, >= 0.6 chamber radii from the centreline and >= 1 m from the thruster outer diameter); p. 673 (Eq. (9) effective pumping speed from measured minus base pressure, valid when the operating pressure is >= 10x base; supplemental gas >= 2 m downstream); p. 677 (Sec. V: early SPT-100 guidance 5e-5 Torr for performance and 1.3e-5 Torr for near-field plume, whose basis does not cover 'applicability to thrusters beyond the SPT-100'; 'Hall thrusters in particular have sparse data'); p. 678 (SPT-100 transportability study: below 1e-5 Torr necessary to identify the thrust-slope change; discharge-current stability and breathing-mode frequency keep changing into the 1e-6 Torr range; results 'insufficient to justify a set of absolute pressure requirements for general thruster designs').
- **REF-TIGHE2015**: W. G. Tighe, R. Spektor, K. D. Diamant, H. Kamhawi, 'Effects of Background Pressure on the NASA 173M Hall Current Thruster Performance', IEPC-2015-152 / ISTS-2015-b-152, 34th IEPC, Kobe (2015) <https://electricrocket.org/IEPC/IEPC-2015-152_ISTS-2015-b-152.pdf>. Access: full text accessed by this lane 2026-09-29: abstract ('Simple ingestion and ionization of the background gases has been determined to be an inadequate explanation of increased thrust at higher background pressure'; range ~3e-6 to ~3.5e-5 Torr; at 15 A a thrust reduction <= 2.5 % as pressure was reduced to 6e-6 Torr; thrust increased by more than 3 % with the cathode raised 6 inches); Sec. II.A ('a xenon pumping speed of ~250 kl/s'; pressures reported corrected by 0.348 for xenon relative to nitrogen). Xenon, NASA-173M: context only, never a value for H-1.
- **REF-BYRNE2022**: M. P. Byrne, P. J. Roberts, B. A. Jorns, 'Coupling of Electrical and Pressure Facility Effects in Hall Effect Thruster Testing', IEPC-2022-377, 37th IEPC, MIT (2022) <https://januselectricpropulsion.com/sites/default/files/2023-04/IEPC_2022_377_Byrne_Coupling%20of%20Electrical%20and%20Pressure%20Facility%20Effects%20in%20Hall%20Effect%20Thruster%20Testing.pdf>. Access: full text accessed by this lane 2026-09-29: Sec. I (residual background gas affects 'the thrust, cathode coupling potential, and divergence angle'; the 'conducting and grounded wall of the vacuum facility ... provide[s] alternate current paths that do not exist on orbit'); Sec. II (thruster run 'cathode-tied and electrically isolated from the facility'); abstract (background pressure 'a strong driver of how the thruster and plume couple to the facility').
- **REF-POLK2017**: J. E. Polk et al., 'Recommended Practice for Thrust Measurement in Electric Propulsion Testing', J. Propulsion and Power 33(3):539-555 (2017), doi:10.2514/1.B35564 <https://pmc.ncbi.nlm.nih.gov/articles/PMC7839308/>. Access: as accessed and recorded by W4 (instrumentation_definition_v1 references REF-POLK2017: stand types, end-to-end in-situ calibration, >= 10 calibrations, thermal shrouds / active cooling, zero before and after, active inclination control, line/cable tares, magnetic tare) and lane 25; not re-accessed by this lane; exact wording - verify.
- **REF-CHOUEIRI2001**: E. Y. Choueiri, 'Plasma oscillations in Hall thrusters', Physics of Plasmas 8(4):1411-1426 (2001), doi:10.1063/1.1354644. Access: abstract only, as recorded by W4 (1 kHz - 60 MHz reviewed band by band); band-by-band values not read (verify).
- **REF-BROWN2017**: D. L. Brown et al., 'Recommended Practice for Use of Faraday Probes in Electric Propulsion Testing', J. Propulsion and Power 33(3):582-613 (2017), doi:10.2514/1.B35696. Access: as accessed and cited by lane 25 (Table A1, far field > 4 channel diameters); not re-accessed.
- **REF-ROVEY2025**: J. L. Rovey et al., 'Recommended Practice for Use of ExB Probes in Electric Propulsion Testing', IEPC-2025-483. Access: as accessed and cited by lane 25 / W4 INS-13; not re-accessed.
- **REF-SNYDER2017**: J. S. Snyder et al., 'Recommended Practice for Flow Control and Measurement in Electric Propulsion Testing', J. Propulsion and Power 33(3) (2017), doi:10.2514/1.B35644. Access: as accessed and quoted by W4 INS-05 (1 % FS typical; per-gas calibration; <= 12 months); not re-accessed.
- **REF-XU2009**: K. G. Xu, M. L. R. Walker, 'High-power, null-type, inverted pendulum thrust stand', Rev. Sci. Instrum. 80(5):055103 (2009). Access: abstract only, as recorded by W4 (1 mN to 5 N range example; verify).
- **REF-MARCHIONI2020**: F. Marchioni, 'Design and Performance Measurements of a Long Channel Hall Thruster for Air-Breathing Electric Propulsion', MSc thesis, Politecnico di Torino (co-tutelle Stanford), 2020; ECHT extended-channel Hall thruster <https://webthesis.biblio.polito.it/14618/>. Access: not re-accessed by this lane; geometry (86 mm long, 10 mm channel height, '100 mm OD'; channel radii not published) as recorded in CLAUDE.md 'Superseded / withdrawn' and docs/HISTORY.md 2026-09-26 (ECHT-N2 audit, hallthruster_bridge/identification/echt_n2/). Published analog only, never a Vyovrinda design value.
- **REF-ULVAC-CRYO**: ULVAC, 'Cryopump safety instructions' (manufacturer published trouble-shooting / safety page) <https://showcase.ulvac.co.jp/en/how-to/trouble-shooting/cryo-pump-safety.html>. Access: accessed by this lane 2026-09-29 (fetch-tool extraction; wording - verify): ozone can be a by-product when oxygen is a process gas and can explode in the cryopump; 'Regenerate as frequently and periodically as practical to minimize the amount of oxidizer present in the cryopump'; keep the oxygen concentration in the cryopump below atmospheric when roughing; above 20 % O2 during regeneration there is a danger of combustion or explosion of rotary pump oil; inert-gas purge (e.g. N2) of the exhaust line. Reference only, no supplier contact.
- **REF-EDWARDS-RV**: Edwards Vacuum, knowledge page on working with oil-sealed rotary vane pumps (manufacturer published page; title - verify) <https://www.edwardsvacuum.com/en-us/vacuum-pumps/knowledge/applications/working-with-oil-sealed-rotary-vane-pumps>. Access: accessed by this lane 2026-09-29 (fetch-tool extraction): 'Where a high concentration of oxygen or other chemically reactive gases are present, highly inert, man-made lubricants are recommended'; no concentration threshold stated. Reference only.
- **REF-NSS1740-15**: NASA NSS 1740.15, 'Safety Standard for Oxygen and Oxygen Systems' (January 1996) <https://ntrs.nasa.gov/api/citations/19960021046/downloads/19960021046.pdf>. Access: accessed by this lane 2026-09-29 (pdftotext): Sec. 101 scope (gaseous and liquid oxygen, not oxygen-enriched mixtures, 'although many of the same considerations apply'); Sec. 104 (p. 1-2) item c ('Oxygen systems shall be kept clean because organic compound contamination ...') and item f (at least two barriers or safeguards so that at least two simultaneous undesired events must occur before personnel injury).
- **REF-ASTM-G93**: ASTM G93/G93M, 'Standard Guide for Cleanliness Levels and Cleaning Methods for Materials and Equipment Used in Oxygen-Enriched Environments'. Access: not accessed by this lane; named only as a candidate cleaning-level guide for the owner's safety case (title from memory - verify).

## Compliance

- no thrust, efficiency, discharge-current or plasma-state prediction; every thrust/power number is an RFP value, an A5 allocation, a W4/lane-25 measurement-uncertainty target or a bound
- no Hall transport closure, screening candidate, abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number used
- no architecture selected, ranked or eliminated; architecture ids used exactly: hall_only, rf_hall, ecr_hall
- P5 calibration nuisance (registration, coil shape, beam-efficiency reading, facility interpretation) is never a design variable here
- Hall-closure uncertainty does not enter any upstream item (intake, compressor, gas chambers, valves)
- published/open sources only; no person, lab, facility or supplier contacted; access stated per reference
- only W3 configuration-item and plane ids are used (H-1, MC-1, C-1, FS-C, PS-C, SVC-1, PIM-0, PIM-RF, PIM-ECR, DIV-1, IP-UP, IP-DN, HALL_INLET_Z0); fixture features are FX ids inside the existing stand/mount element
- no module wired into abep_sim.archengine; no golden moves; only files under the lane directory and the lane test are written
- governance files are not pinned; owner decisions, the G0 record, verified merged deliverables and immutable snapshots are pinned by sha256; mutable drafts and modules are consumed by value and re-checked
- no value depends on a parallel (PENDING) lane at import or test time; pending_status() reports presence only
- Bundle 1 stays NO_BASELINE_YET; the credible Hall set stays empty; A5 numbers are allocations or requirements
