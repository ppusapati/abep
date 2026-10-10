# DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM

DBF-1.2 Design Baseline Freeze 1.2 - hall_icp_neutralizer (DCR-DBF1-001: intake / compressor / plenum-feed, mass and power closure)

Authoritative record: `dbf1_2_v1.json` (this page restates it). Machine-readable subset: `dbf1_2_config_v1.json`. Requirement trace: `dbf1_2_requirement_trace_v1.json`. Risk register: `dbf1_2_risk_register_v1.json`. Source manifest: `dbf1_2_source_manifest_v1.json`. Hash lock: `dbf1_2_lock_v1.json`. Change control: `docs/baseline/DBF-1/DCR_PROCESS.md` (DBF-1.2 is immutable except through a new DCR).

Status meaning: architecture and design parameters are frozen at preliminary-design level; measured compliance is open to EM / QM testing. It is not fully RFP-qualified, not demonstrated compliant, not flight-qualified, not performance validated, not a final flight design.

## Lineage

- parent: DBF-1.1, lock `257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8` (immutable); DBF-1 lock `517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907` (immutable)
- change authority: DCR-DBF1-001 (approved); approval A9.41 `docs/decisions/OD_2026_10_10_A9_41_dcr_dbf1_001_approval_mass_risk.json`; approval record `docs/baseline/DCR-001/dcr001_approval_v1.json`; register `docs/baseline/DBF-1/dcr_register_v5.json`
- build directions: A9.42, A9.43 (power reconciliation); operating concept A9.40; source checkpoint `6f4e3bb7025ec387143865fb737cbaaa841404fa`
- open DCRs not applied: DCR-DBF1-003 (REQUESTED_EVALUATION_TO_BE_PREREGISTERED)

## Intake / compressor / plenum-feed (DCR-DBF1-001)

- intake: aperture 0.7 m² (equivalent diameter 0.944 m), collimator L/D 20, retention S_eff 11.254 m³/s; delivered flow regulated by active compressor / retention control with density-aware altitude scheduling; exposed frontal drag is NOT controlled by compressor speed
- compressor: integrated contra-rotating molecular compressor, 7 blade rows + shared Holweck rear section, two coaxial counter-rotating shafts, 8603 rpm, tip speed 300 m/s, full-aperture front section, no separate finishing pump; governing mass 7.767 kg MEV; power estimate 38.5 W, allowance 77 W
- plenum: setpoint 5.027 Pa (band 4.78-5.28 Pa), volume 9.26 L; 22 km/s sensitivity needs 6.12 Pa
- distributor: 186 x 3 mm holes, ring 12 x 20 mm, 8 inlets; +/-5 % azimuthal flow (preliminary H1 interface / design requirement, not demonstrated)

| row | shaft | r_tip / r_hub (m) | blade (mm) | u_rel (m/s) | p_in -> p_out (Pa) | K | Kn out | classification |
|---|---|---|---|---|---|---|---|---|
| F1 | A | 0.333 / 0.133 | 199.8 | 210 | 0.0041 -> 0.0044 | 1.05 | 7.8 | ADMITTED_FREE_MOLECULAR |
| F2 | B | 0.333 / 0.200 | 132.7 | 450 | 0.0044 -> 0.0081 | 1.87 | 6.3 | ADMITTED_FREE_MOLECULAR |
| F3 | A | 0.333 / 0.279 | 54.0 | 516 | 0.0081 -> 0.0170 | 2.09 | 7.4 | ADMITTED_FREE_MOLECULAR |
| F4 | B | 0.333 / 0.310 | 23.5 | 565 | 0.0170 -> 0.0396 | 2.33 | 7.3 | ADMITTED_FREE_MOLECULAR |
| F5 | A | 0.333 / 0.323 | 9.6 | 585 | 0.0396 -> 0.0965 | 2.44 | 7.3 | ADMITTED_FREE_MOLECULAR |
| F6 | B | 0.333 / 0.328 | 5.0 | 593 | 0.0965 -> 0.2724 | 2.82 | 5.0 | EM_VERIFICATION_RISK_CROSSES_0.1_Pa |
| B7 | A | 0.333 / 0.328 | 5.0 | 595 | 0.2724 -> 0.7844 | 2.88 | 1.7 | EM_VERIFICATION_RISK_TRANSITIONAL |
| H | A (drum skin) | - | groove 2.0 | - | 0.784 -> 5.027 | - | 0.68 | PRELIMINARY_MOLECULAR_DRAG_DESIGN_WITHIN_Kn_CRITERION_COEFFICIENTS_REQUIRE_VERIFICATION |

## AIR design point and operating modes

- DBF12-AIR-01: {"thrust_mN": 12.0, "v_eff_km_s": 26.8, "hall_feed_mg_s": 0.44776119402985076, "icp_dedicated_flow_mg_s": 0.0, "P_d_W": 650.0, "window": "only inside the app...
- DBF12-AIR-02: {"v_eff_km_s": 22.0, "hall_feed_mg_s": 0.5454545454545455, "plenum_setpoint_required_Pa": 6.123684498523269}
- DBF12-AIR-03: NOT_SUPPORTED_BY_DBF-1.2
- DBF12-OPS-01: PRIMARY_NOMINAL: density-aware altitude scheduling within 180-230 km; 12 mN sizing point; only inside the admissible AIR density / thrust / drag window
- DBF12-OPS-02: REQUIRED_SECONDARY: contingency / off-nominal / upper-envelope (25 mN capability); atmospheric compressor OFF; used when AIR does not give adequate thrust / drag margin
- DBF12-OPS-03: CONSERVATIVE_VERIFICATION_DATASET (retained, not weakened; not 196 mandatory independent AIR propulsion points)

## Power (P6 ledger + DBF-1.2 compressor; A9.43)

| case | P_d (W) | compressor (W) | P_bus (W) | margin to 1,350 W | margin to 1,500 W |
|---|---|---|---|---|---|
| AIR 12 mN reference | 650.0 | 38.5 | 1222.337 | 127.663 | 277.663 |
| AIR 12 mN conservative | 650.0 | 77.0 | 1263.067 | 86.933 | 236.933 |

Model thrust at P_d 650 W: 12.537 mN — MODEL-DERIVED / NOT VALIDATED (T = sqrt(2 eta m_dot P_d), eta 0.27, m_dot 0.448 mg/s); never demonstrated thrust.

| Xe 25 mN Hall discharge allocation | nominal ICP (W) | +100 W RF (W) |
|---|---|---|
| ≤ 1,450 W design ceiling | ≤ 876.087 | ≤ 747.515 |
| < 1,500 W RFP | < 918.623 | < 790.052 |

Xe 25 mN is a design capability requirement. The Hall discharge-power allocation is <= 876 W at the 1,450 W design ceiling under the nominal ICP case and <= 748 W under the +100 W RF sensitivity case. Performance is to be verified on EM/QM hardware. The ~658 W RP-1 Xe result is PARAMETRIC / NOT_VALIDATED. Atmospheric compressor OFF in Xe mode.

Basis: chain efficiency 0.850725, P-XE non-discharge 420.1882 W, +100 W RF = +151.1316 W bus (DCR-001 v4 terms 412.5 W / 0.855 / +129 W superseded); DCR-001 596 / 600 W discharge figures are historical model predictions, not governing.

## Mass (A9.41, approved v6 roll-up)

| line | MEV (kg) |
|---|---|
| AL-01 intake | 4.2690 |
| AL-02 compressor | 7.8431 |
| AL-03 plenum/feed | 1.7340 |
| AL-04 Hall head + magnets | 4.2050 |
| AL-05 ICP neutralizer | 1.3430 |
| AL-06 RF generator / match | 1.5000 |
| AL-07 PPU | 5.4600 |
| AL-08 Xe hardware (single branch, 2 kg Xe) | 2.9193 |
| AL-09 controls / FDIR | 1.0000 |
| AL-10 structure / thermal | 2.5000 |
| non-harness | 32.7734 |
| harness (5/95) | 1.7249 |
| nominal dry | 34.4983 |
| + 10 % system margin | 37.9481 |
| + Xe reference | 2.0000 |
| **preliminary wet** | **39.9481** |

Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin.

PPU: 5.46 kg MEV (PRELIMINARY CBE / NOT MEASURED / REQUIRES EARLY CONFIRMATION); historical 6.0 kg floor preserved in history. ICP open-frame support / spacer counted once (AL-10, MQ-02); duplicate removed from AL-05 (v6). 7.767 kg is the governing compressor-design mass (v5 machine). The AL-02 line of the approved v6 roll-up is 7.843 kg because the v6 intake-compressor integration books the shared joint, assembly mount feet and reinforcement in AL-02 and removes the bolted flange pair and duplicate mounts from AL-01 / AL-02 (net -0.284 kg on AL-01 + AL-02 = 12.112 kg); bookkeeping between lines, totals unchanged.

## Host interface

- IR-HOST-DRAG-01: {"requirement": "host spacecraft C_D*A supplied at PDR and within the propulsion drag-compensation envelope", "reference_proposal_sizing_CdA_m2": 0.5, "scope...

## Open risks / verification (do not unfreeze the baseline)

| id | item | basis | verification |
|---|---|---|---|
| MR-DCR001-01 | mass closure: preliminary roll-up 39.948 kg wet; ~0.052 kg numerical headroom is NOT design margin | A9.41 mass risk | CBE / quotation / EM mass measurement; any mass growth needs a DCR before acceptance |
| VR-PPU-01 | AL-07 PPU preliminary CBE 4.55 kg (5.46 kg MEV) confirmation | v6 component estimate, mostly assumed | early PPU design / quotation (RFQ3-HALLEL); revert to 6.0 kg floor gives ~40.57 kg wet |
| VR-XE-01 | Xe tank MEOP / burst factor / quotation | XA9-28 / XA9-29 TBD; 1.25 L Ti sphere sized at 150 bar, burst factor 2 | tank quotation with MEOP at 323 K |
| VR-CMP-01 | compressor actual mass (7.767 kg MEV governing) | component estimates partly assumed | EM mass measurement |
| VR-CMP-02 | compressor F6 / B7 transitional performance | F6 crosses 0.1 Pa, B7 transitional; not admitted | EM compressor characterisation |
| VR-CMP-03 | Holweck coefficients | drag-channel form, coefficients uncited | EM test |
| VR-CMP-04 | rotor growth / running clearance | drum growth 0.34-0.36 mm vs 0.3 mm running clearance | EM spin test, clearance design |
| VR-FEED-01 | H1 distributor flow uniformity (+/-5 %) | preliminary interface requirement | EM flow-uniformity test |
| VR-HALL-01 | air-Hall 26.8 km/s design-performance basis | PARAMETRIC / NOT_VALIDATED; Hall credible set empty | EM thrust measurement on N2 / air |
| VR-HALL-02 | 22 km/s sensitivity (0.545 mg/s, ~6.1 Pa setpoint) | sensitivity case | EM verification |
| VR-XE-02 | Xe 25 mN power / performance | allocation <= 876.1 W (nominal ICP) / <= 747.5 W (+100 W RF) at 1,450 W; ~658 W RP-1 Xe result PARAMETRIC / NOT_VALIDATED | EM / QM thrust and power measurement |
| VR-PWR-01 | AIR 12 mN bus under the P6 conservative non-discharge corner | P-12 conservative corner + 77 W compressor allowance = 1469.9 W (below the 1,500 W RFP limit; reference / conservative design values 1222.3 / 1263.1 W) | measured non-discharge loads (RF generator efficiency, ICP, magnets, housekeeping) on EM; corner exceedance managed by RF / altitude schedule |
| VR-HAR-01 | routed harness mass | 5/95 rule until routed | routed harness design |
| VR-AL09-01 | AL-09 control-electronics CBE | 1.0 kg owner allocation | controller design CBE |
| VR-AL10-01 | AL-10 structural / thermal CBE | 2.5 kg owner allocation | structural / thermal design CBE |
| VR-HOST-01 | actual host C_D*A | IR-HOST-DRAG-01 reference 0.50 m2 | host ICD at PDR |
| VR-EMQM-01 | EM / QM AO, thermal, life and qualification tests | RFP-P19-04 / P19-06 | EM / QM programme |

## Requirement trace

| requirement | RVM | RFP | DBF-1.2 items | state |
|---|---|---|---|---|
| altitude 180-230 km | RVM-01 | RFP-P18-08 | DBF12-OPS-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM |
| >= 12 mN sustained atmospheric | RVM-02 | RFP-P18-06 | DBF12-AIR-01, DBF12-PWR-05 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM |
| 25 mN capability | RVM-03 | RFP-P18-06 | DBF12-OPS-02, DBF12-PWR-06 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM |
| P_bus < 1500 W | RVM-04 | RFP-P18-10 | DBF12-PWR-05, DBF12-PWR-06 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM |
| internal 1350 W allocation | RVM-05 |  | DBF1-PWR-01, DBF12-PWR-05 | WITHIN_ALLOCATION (AIR nominal) |
| mass < 40 kg | RVM-06 | RFP-P18-11 | DBF12-MASS-05 | CONFORMING_BY_PRELIMINARY_ROLLUP / OPEN_MASS_RISK |
| internal 34 / 36 kg allocation | RVM-07 |  | DBF1-MASS-02, DBF12-MASS-05 | TARGET_NOT_MET (nominal dry 34.498 kg) |
| atmospheric propellant | RVM-08 | RFP-P18-08, RFP-P17-03, RFP-P17-04 | DBF12-IN-01, DBF12-CMP-01, DBF12-FEED-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM |
| Xe capability, two separate tanks | RVM-10 / RVM-29 | RFP-P18-08, RFP-P17-05 | DBF12-OPS-02 | CONFORMING_BY_DESIGN |
| Hall preferred | RVM-11 | RFP-P18-07 | DBF1-H1-01 | CONFORMING_BY_DESIGN |
| neutralization (cathodeless) | RVM-15 / RVM-28 |  | DBF1-ICP-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM |
| AO material compatibility | RVM-16 | RFP-P19-04 | DBF1-MAT-01 | VERIFY_EM_QM |
| thermal closure | RVM-17 |  | DBF1-TH-01 | VERIFY_EM_QM |
| electronics redundancy (no SPF) | RVM-19 | RFP-P18-09, RFP-P18-02 | DBF12-MASS-05 | CONFORMING_BY_DESIGN (PPU N+1) / VERIFY_FMEA |
| MIL-1553B interface | RVM-20 | RFP-P18-12 |  | ALLOCATED_TO_AL-09 |
| environmental qualification | RVM-21 | RFP-P19-04 |  | VERIFY_EM_QM |
| mission life / firing hours | RVM-12 / RVM-13 |  |  | VERIFY_EM_QM |

## Items

| id | item | value | status (DBF-1.2) |
|---|---|---|---|
| DBF1-H1-01 | channel mean diameter d_mean | 70.0 | INHERITED_UNCHANGED |
| DBF1-H1-02 | channel width h | 12.0 | INHERITED_UNCHANGED |
| DBF1-H1-03 | channel length L (HALL_INLET_Z0 to IP-EXIT) | 103.2 | INHERITED_UNCHANGED |
| DBF1-H1-04 | derived radii r_in = (d_mean - h) / 2, r_out = (d_mean + h) / 2 | {"r_in_mm": 29.0, "r_out_mm": 41.0, "A_channel_mm2": 2638.937829} | INHERITED_UNCHANGED |
| DBF1-H1-05 | discharge-voltage operating band (operating variable, not a design value) | [180.0, 350.0] | INHERITED_UNCHANGED |
| DBF1-H1-06 | discharge-power band (H2-1) | [650.0, 1350.0] | INHERITED_UNCHANGED |
| DBF1-BZ-01 | B_r(z) shape target (design target) | monotonic rise toward the exit, peak at or just downstream of z = L; field near the anode as low as the circuit allows (numeric B_anode/B_peak TBD) | INHERITED_UNCHANGED |
| DBF1-BZ-02 | peak centreline B_r target band at / near IP-EXIT | [69.93, 268.6] | INHERITED_UNCHANGED |
| DBF1-BZ-03 | B_peak operating levels used by the simulation | {"BP-LO": 69.93, "BP-HI": 268.6} | INHERITED_UNCHANGED |
| DBF1-BZ-04 | simulation B(z) shape (H-1 FE-derived field) | BZ-H1FE-V1 | INHERITED_UNCHANGED |
| DBF1-BZ-05 | MC-1 field capability (necessary design capability) | 403.0 | INHERITED_UNCHANGED |
| DBF1-RF-01 | RF frequency | 13.56 | INHERITED_UNCHANGED |
| DBF1-RF-02 | RF forward-power operating envelope at the generator / 50-ohm reference plane | [0.0, 500.0] | INHERITED_UNCHANGED |
| DBF1-RF-03 | matching architecture | adjustable local match, on / immediately adjacent to the ICP module (match_colocated = true) | INHERITED_UNCHANGED |
| DBF1-RF-04 | RF component ratings (generator, coupler, coax, match, feedthrough) | >= the DBF1-RF-02 envelope upper end (500 W forward) | INHERITED_UNCHANGED |
| DBF1-ICP-01 | ICP topology | open-tube coaxial downstream ICP, unmagnetized, CFG-CAP-OFF electron extraction topology per P1-IT-36 when registered | INHERITED_UNCHANGED |
| DBF1-ICP-02 | module geometry vector (L_standoff, r_aperture, r_module, L_module, tau_support) | {"L_standoff": 0.05, "r_aperture": 0.06, "r_module": 0.09, "L_module": 0.15, "tau_support": 0.0} | INHERITED_UNCHANGED |
| DBF1-ICP-03 | NP-ICP v2 volume model | ASSUMED_GEOMETRIC_TUBE (V = pi R^2 L with R = r_aperture 0.06 m, L = L_module 0.15 m) | INHERITED_UNCHANGED |
| DBF1-ICP-04 | ion-collecting electrode (collector) | C-type electrode on the inner wall of the bore, 0.10 m axial length, axial slit for RF penetration; separately biased and metered, ICP body floating | INHERITED_UNCHANGED |
| DBF1-ICP-05 | ICP neutral source / gas routing | G-REUSE (Hall exhaust -> ICP; mdot_ICP,dedicated = 0); capped dedicated port retained; declared variant G-XE | INHERITED_UNCHANGED |
| DBF1-ICP-06 | ICP body / collector isolation class | 350.0 | INHERITED_UNCHANGED |
| DBF1-ICP-07 | dielectric bore (vessel) material | borosilicate glass (pyrex class) | INHERITED_UNCHANGED |
| DBF1-IN-01 | upstream design vector (intake, filter, compressor, plenum, P_set) | A0.25_Ld20_phi0.9\|F4-FIL-T0.9\|T6-A1-U2-D0-Ti6Al4V-H0.5\|V0.001\|P0.02 | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-IN-01 |
| DBF1-IN-02 | intake geometry (F1 candidate, d collapsed) | {"area_m2": 0.25, "L_over_d": 20.0, "phi": 0.9, "candidate": "A0.25_Ld20_phi0.9", "channel_diameter": "collapsed: every TPMC output is d-invariant at fixed L... | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-IN-01 |
| DBF1-IN-03 | TPMC surface-scenario basis | ["maxwell_a0", "maxwell_a0.2", "maxwell_a0.5", "maxwell_a0.8", "maxwell_a1", "cll_a0", "cll_a0.2", "cll_a0.5", "cll_a0.8", "cll_a1"] | INHERITED_UNCHANGED |
| DBF1-IN-04 | filter case | F4-FIL-T0.9 | INHERITED_UNCHANGED |
| DBF1-IN-05 | compressor design (F3 design grid) | {"id": "T6-A1-U2-D0-Ti6Al4V-H0.5", "N_turbo": 6, "A_turbo_m2": 0.1963495408, "R_turbo_m": 0.2886751346, "u_tip_turbo_mps": 290.6899682, "rpm": 9615.946745, "... | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-CMP-01 |
| DBF1-IN-06 | plenum volume / wall / target pressure | {"V_m3": 0.001, "wall_case": "WALL-G0", "P_set_Pa": 0.02} | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-FEED-01 |
| DBF1-IN-07 | feed-loop controller (normalized PI on plenum pressure) | {"Kp": 0.3, "Ti_s": 3.0, "f_valve_hz": 1.0, "authority": 3.0} | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-IN-02 |
| DBF1-IN-08 | registered F7 performance of the frozen design (per covered scenario) | {"cll_a0.5": {"mdot_delivered_min_kg_s": 1.084126071518558e-08, "mdot_captured_min_kg_s": 4.08271125e-08, "P_compressor_el_max_W": 11.125100048512362, "drag_... | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-CMP-01 / DBF12-FEED-01 (F7 performance of the superseded DBF-1 upstream design) |
| DBF1-PWR-01 | design power allocation (all flight loads at the spacecraft-side DC boundary) | 1350.0 | INHERITED_UNCHANGED |
| DBF1-PWR-02 | RFP bus-power gate (assessment only) | 1500.0 | INHERITED_UNCHANGED |
| DBF1-PWR-03 | common-load allocation (compressor + flow control + filter/getter + thermal control + housekeeping) | 300.0 | INHERITED_UNCHANGED |
| DBF1-PWR-04 | mapping to bus_power_boundary_a9_v2 | {"boundary": "bus_power_boundary_a9_v2 (flight configuration hall_icp_neutralizer; flight C1 loads NONE)", "slots_by_group": {"hall": ["hall_discharge", "hal... | INHERITED_UNCHANGED |
| DBF1-MASS-01 | system mass-margin policy | 0.1 | INHERITED_UNCHANGED |
| DBF1-MASS-02 | nominal-dry mass target | 34.0 | INHERITED_UNCHANGED |
| DBF1-MASS-03 | reference Xe load | 2.0 | INHERITED_UNCHANGED |
| DBF1-MASS-04 | wet-mass target at the reference Xe load (arithmetic) | 39.4 | INHERITED_UNCHANGED |
| DBF1-TH-01 | thermal network topology (NP-THERMAL-CATHODELESS 2.0.0) | {"solved_nodes": ["H1_ANODE", "H1_WALL_IN", "H1_WALL_OUT", "H1_POLE_IN", "H1_POLE_OUT", "H1_BACKPLATE", "H1_COIL_IN", "H1_COIL_OUT", "H1_COIL_TRIM", "N_VESSE... | INHERITED_UNCHANGED |
| DBF1-TH-02 | spacecraft interface form | SCI-A conductance to a fixed spacecraft temperature at H1_BACKPLATE (isolated mount), N_MOUNT and R_HALL; values from the host thermal ICD | INHERITED_UNCHANGED |
| DBF1-TH-03 | thermal design margin rule | {"margin_K": 50.0, "heat_load_factor": 1.2} | INHERITED_UNCHANGED |
| DBF1-MAT-01 | H-1 anode / gas distributor material (primary) | INCONEL alloy 600 (chromia-forming Ni alloy) | INHERITED_UNCHANGED |
| DBF1-MAT-02 | H-1 anode / gas distributor material (backup) | INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy) | INHERITED_UNCHANGED |
| DBF1-MAT-03 | ICP ion-collecting electrode material (primary / backup) | {"primary": "INCONEL alloy 600 (chromia-forming Ni alloy)", "backup": "INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy)"} | INHERITED_UNCHANGED |
| DBF1-MAT-04 | H-1 channel wall ceramic (primary / backup) | {"primary": "BN-SiO2 (borosil class)", "backup": "BN"} | INHERITED_UNCHANGED |
| DBF1-DRAG-01 | reference host-spacecraft body (drag case) | {"case_id": "RC-DIAMANT", "record_id": "REF-T1-DIAMANT", "a_ref_m2": 0.5, "cd": 2.2, "cd_a_m2": 1.1, "shape": "not stated by the source (body frontal area on... | SUPERSEDED_BY_DCR-DBF1-001 -> DBF12-HOST-01 |
| DBF1-DRAG-02 | drag model | D(state) = q (C_D A_ref)_body + D_intake(state, scenario), q = 1/2 rho v^2 at the frozen orbit-resolved state (F1 envelope atmospheres); D_intake = F1 intake... | INHERITED_UNCHANGED |
| DBF1-DRAG-03 | surface accommodation basis | body: as stated by the case source (not stated: C_D 2.2 is a literature-typical value); intake: the 10 admitted TPMC scenarios (Maxwell / CLL, alpha 0-1), re... | INHERITED_UNCHANGED |
| DBF12-IN-01 | intake physical aperture / collimator | {"aperture_m2": 0.7, "equivalent_diameter_m": 0.9440697438826297, "collimator_L_over_D": 20.0, "retention_design": "S_eff = 2 C_back (2/3 retention)", "S_eff... | FROZEN |
| DBF12-IN-02 | delivered-flow regulation concept | ACTIVE_COMPRESSOR_RETENTION_CONTROL_WITH_DENSITY_AWARE_ALTITUDE_SCHEDULING | FROZEN |
| DBF12-AIR-01 | guaranteed AIR proposal sizing point | {"thrust_mN": 12.0, "v_eff_km_s": 26.8, "hall_feed_mg_s": 0.44776119402985076, "icp_dedicated_flow_mg_s": 0.0, "P_d_W": 650.0, "window": "only inside the app... | FROZEN_ASSUMPTION |
| DBF12-AIR-02 | 22 km/s sensitivity (carried, not guaranteed) | {"v_eff_km_s": 22.0, "hall_feed_mg_s": 0.5454545454545455, "plenum_setpoint_required_Pa": 6.123684498523269} | FROZEN_ASSUMPTION |
| DBF12-AIR-03 | 1.33 mg/s AIR capability point | NOT_SUPPORTED_BY_DBF-1.2 | FROZEN |
| DBF12-CMP-01 | integrated contra-rotating molecular compressor | {"blade_rows": 7, "rear_section": "shared Holweck (outer skin of the shaft-A drum, stationary grooved Al band)", "shafts": "two coaxial counter-rotating", "r... | FROZEN_ASSUMPTION |
| DBF12-CMP-02 | pressure-domain classification | {"rows": [{"row": "F1", "shaft": "A", "r_tip_m": 0.333, "r_hub_m": 0.1332, "blade_height_mm": 199.8, "rpm": 8602.969896859207, "u_tip_m_s": 300.0, "u_rel_m_s... | FROZEN_ASSUMPTION |
| DBF12-FEED-01 | plenum setpoint / band / volume | {"setpoint_Pa": 5.026905185354923, "band_Pa": [4.775559926087176, 5.278250444622669], "volume_L": 9.257419758367076, "sensitivity_setpoint_22kms_Pa": 6.12368... | FROZEN_ASSUMPTION |
| DBF12-FEED-02 | H1 distributor / manifold concept | {"outlet_holes": 186, "hole_d_mm": 3.0, "open_fraction": 0.49821428571428555, "ring_mm": [12.0, 20.0], "inlets": 8, "uniformity_requirement": "+/-5 % azimuth... | FROZEN_ASSUMPTION |
| DBF12-MASS-05 | preliminary system mass roll-up (A9.41) | {"nonharness_kg": 32.773399999999995, "harness_kg": 1.7249157894736842, "nominal_dry_kg": 34.49831578947368, "dry_10pct_kg": 37.94814736842105, "xe_reference... | FROZEN_ASSUMPTION |
| DBF12-PWR-05 | AIR 12 mN bus power (P6 ledger + DBF-1.2 compressor) | {"reference": 1222.3365718806567, "conservative": 1263.0665374982182} | FROZEN |
| DBF12-PWR-06 | Xe 25 mN Hall discharge-power allocation (design capability requirement) | {"1450W_design_ceiling_le": {"nominal_ICP_P_d_max_W": 876.0866831287905, "RF_plus_100W_P_d_max_W": 747.5152545573619}, "1500W_rfp_supremum_lt": {"nominal_ICP... | FROZEN |
| DBF12-OPS-01 | AIR mode | PRIMARY_NOMINAL: density-aware altitude scheduling within 180-230 km; 12 mN sizing point; only inside the admissible AIR density / thrust / drag window | FROZEN |
| DBF12-OPS-02 | Xe mode | REQUIRED_SECONDARY: contingency / off-nominal / upper-envelope (25 mN capability); atmospheric compressor OFF; used when AIR does not give adequate thrust / ... | FROZEN |
| DBF12-OPS-03 | 196-state set | CONSERVATIVE_VERIFICATION_DATASET (retained, not weakened; not 196 mandatory independent AIR propulsion points) | FROZEN |
| DBF12-HOST-01 | IR-HOST-DRAG-01 | {"requirement": "host spacecraft C_D*A supplied at PDR and within the propulsion drag-compensation envelope", "reference_proposal_sizing_CdA_m2": 0.5, "scope... | REFERENCE_PENDING_ICD |

## Baseline deficiencies

| id | category | status |
|---|---|---|
| DBF1-BD-01 | DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound) | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-02 | DESIGN_VARIABLE_LIMIT | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-03 | DESIGN_VARIABLE_LIMIT | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-04 | MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA) | OPEN_AS_MASS_RISK_MR-DCR001-01 |
| DBF1-BD-05 | MISSING_EVIDENCE | CLOSED_BY_DCR-DBF1-002 |
| DBF1-BD-06 | MISSING_EVIDENCE | OPEN |

## Not

- not a performance prediction
- not a PASS / qualification / flight baseline approval
- not a change to any RFP requirement, owner decision or admitted / scored record
- not an M2 or M3 result
- not fully RFP-qualified, not demonstrated compliant, not flight-qualified, not performance validated, not a final flight design
- not a proposal / technical-annexure / bid-package regeneration
