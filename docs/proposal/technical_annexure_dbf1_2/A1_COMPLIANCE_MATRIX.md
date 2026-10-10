# A1 - Compliance matrix (DBF-1.2)

**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `45492a8` (`45492a8ef12fba13d262695bbd19f3631e80f355`), lock sha256 `103f4c9a5c0ab61d9d12e989c47e5f4fd713caa6bcbe7c45e9207e2e6ce19ee5`. Baseline status: **DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM**. Every evidence path is a file at that commit (`git show 45492a8:<path>`).

## Status vocabulary

- **COMPLY**: the offered design (DBF-1.2) meets the clause as written; a property of the offer, no test result implied
- **COMPLY_PLANNED_WITH_EVIDENCE_PATH**: the frozen DBF-1.2 preliminary design conforms by design / allocation, or a plan exists; compliance is verified on EM / QM hardware; nothing is yet demonstrated
- **PARTIAL**: some sub-items are covered by the DBF-1.2 design or plan, others are not yet (listed in the response)
- **NOT_YET_DEMONSTRATED**: the outcome depends on hardware / validation evidence that does not exist yet and that the preliminary design cannot substitute for; the annexure does not claim the outcome
- **OWNER_INPUT_REQUIRED**: organisational, commercial or facility information the repository does not hold; the owner supplies it

Status rule: A clause moves from the A9.27 package status only where the DBF-1.2 requirement trace (approved baseline, A9.41 / A9.42 / A9.43) gives a CONFORMING_BY_DESIGN / ALLOCATION state with an EM / QM verification path; owner rulings A9.27 (RFP-P19-03 COMPLY composition only; RFP-P18-08 split) are kept; no clause is raised to COMPLY by this regeneration; VERIFY_EM_QM-only trace states (life, AO, thermal) do not change a status.

## Status counts (37 registered clauses)

- COMPLY: 2
- COMPLY_PLANNED_WITH_EVIDENCE_PATH: 23
- PARTIAL: 2
- NOT_YET_DEMONSTRATED: 3
- OWNER_INPUT_REQUIRED: 7

## Changes against the 2026-10-05 bid package (`docs/bid/package/`, commit `2de86ab`)

| clause | bid package status | DBF-1.2 annexure status |
|---|---|---|
| RFP-P17-03 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P17-04 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P17-05 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P18-02 | OWNER_INPUT_REQUIRED | PARTIAL |
| RFP-P18-04 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P18-06 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P18-09 | OWNER_INPUT_REQUIRED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P18-10 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |
| RFP-P18-11 | NOT_YET_DEMONSTRATED | COMPLY_PLANNED_WITH_EVIDENCE_PATH |

## Clause-by-clause

### RFP-P16-01 - Part III 1(A)i (p. 16)

> 1. Development of Air Breathing Electric Propulsion (ABEP) which will work in the VLEO environment. 2. Testing and space qualification of the Air Breathing Electric Propulsion (ABEP).

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-21.

Vyovrinda proposes to develop, test and space-qualify an ABEP system for VLEO. The architecture and preliminary design are frozen as DBF-1.2 (DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM); compliance is verified on EM / QM hardware through Milestones 1-5 (A3_VERIFICATION_PLAN.md). Not demonstrated: no Vyovrinda hardware has been built or tested; Hall-transport validation (gate 3) is FAIL and the credible transport set is empty, so every Hall performance figure is a design allocation or a PARAMETRIC / NOT_VALIDATED model value, never a measurement.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/status_semantics`; `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace`

### RFP-P16-02 - Part III 1(A)ii Figure 1 (p. 16)

> Logical Block Diagram: Intake -> Filter -> Compressor -> Gas Chamber -> Valve -> Thruster (Ionization zone | Acceleration zone) -> Thrust; Xenon Gas -> Valve -> Thruster.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-08, RVM-10 / RVM-29.

The DBF-1.2 architecture follows the RFP logical block diagram: Intake (0.70 m2 aperture, collimator L/D 20) -> filter -> Compressor (integrated contra-rotating molecular compressor) -> Gas Chamber (plenum 9.26 L at 5.03 Pa) -> Valve / H-1 distributor -> Thruster (H-1 Hall accelerator, ionization and acceleration in one annular channel) -> Thrust; Xenon Gas -> Valve -> Thruster (separate Xe branch AL-08). One element is added outside the diagram: a downstream 13.56 MHz RF-ICP electron source / neutralizer in place of a hollow cathode (cathodeless flight architecture hall_icp_neutralizer, A9.19 / A9.20). Mapping in A2_TECHNICAL_DESCRIPTION.md section 2.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/intake_compressor_feed`; `docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json` `#/architecture`

### RFP-P17-01 - Part III Figure 2 (p. 17)

> Processing block diagram of EM QM Testing of ABEP System: EM Air Intake System, Compressor storage; EM Power processing unit (PPU); EM Thruster -> EM Integration -> EM Integration Test -> Qualification Model Intake and compressor; Qualification Model Power Electronics; Qualification Model Thruster -> QM Integration Test.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-21.

The EM -> EM integration -> EM integration test -> QM (intake / compressor, power electronics, thruster) -> QM integration test flow is the model philosophy; DBF-1.2 is the design these models build. Mapping onto the milestones and the DBF-1.2 verification items in A3_VERIFICATION_PLAN.md. No EM or QM hardware exists yet.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks[id=VR-EMQM-01]`

### RFP-P17-02 - Part III 1(A)iii (p. 17)

> List of critical technologies required for the solution: 1. Electric propulsion thruster to Ionize and accelerate N2 and nascent O. 2. Material compatibility to with stand VLEO atmospheric nascent oxygen. 3. Air Intake system design and compressor technology. 4. Test facility to simulate air mixture conditions in VLEO environment.

**Status: NOT_YET_DEMONSTRATED** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-02, RVM-16, RVM-08.

Each critical technology has a frozen DBF-1.2 design answer and an EM / QM verification path; none is demonstrated. (1) Thruster ionizing N2 and nascent O: H-1 (d_mean 70 mm, h 12 mm, L 103.2 mm, FE-derived B(z) FROZEN FOR EM) at the 12 mN AIR sizing point; the 26.8 km/s design basis is PARAMETRIC / NOT_VALIDATED (VR-HALL-01), gate 3 is FAIL and the ICP AIR closure is BLOCKED BY SPECIFIC MISSING EVIDENCE. (2) AO material compatibility: primary / backup materials frozen (INCONEL 600 / 601 anode and collector; BN-SiO2 / BN wall); materials state FROZEN FOR EM, closed only by coupon / EM tests. (3) Intake and compressor: 0.70 m2 intake and 7-row contra-rotating molecular compressor frozen; F6 / B7 transitional rows are EM verification risks (VR-CMP-02).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items`; `docs/closure/icp/icp_closure_v1.json` `#/closure`; `docs/closure/materials/materials_gates_v1.json` `#/closure_state`; `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `#/members`

### RFP-P17-03 - Part III 1(A)iv row 1 Air Intake (p. 17)

> Air intake system captures residual atmospheric particles (mainly atomic oxygen and nitrogen) at VLEO altitudes (< 250 km). Most challenging in total system.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-08.

Frozen intake (DBF12-IN-01): physical aperture 0.70 m2 (equivalent diameter 0.944 m), collimator L/D 20, retention S_eff 11.25 m3/s. Delivered flow is regulated by active compressor / retention control with density-aware altitude scheduling (DBF12-IN-02); exposed frontal drag is not controlled by compressor speed. Trace state RVM-08: CONFORMING_BY_DESIGN / VERIFY_EM_QM. Verified by EM intake / compressor tests (Milestone 4).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/intake_compressor_feed/DBF12-IN-01`; `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace[rvm=RVM-08]`

### RFP-P17-04 - Part III 1(A)iv row 2 Compressor and gas Reservoir (p. 17)

> Increases the density of the collected atmospheric gases to a usable level of ionization

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-08.

Frozen compressor (DBF12-CMP-01): integrated contra-rotating molecular compressor, 7 blade rows + shared Holweck rear section, two coaxial counter-rotating shafts, 8,603 rpm, tip speed 300 m/s, governing mass 7.767 kg MEV, power estimate 38.5 W (allowance 77 W). Gas chamber: plenum setpoint 5.03 Pa (band 4.78-5.28 Pa), volume 9.26 L. Rows F1-F5 are free-molecular; F6 / B7 (transitional) and the Holweck coefficients are EM verification risks (VR-CMP-02, VR-CMP-03), rotor growth vs running clearance VR-CMP-04.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/intake_compressor_feed/DBF12-CMP-01`; `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/intake_compressor_feed/DBF12-FEED-01`

### RFP-P17-05 - Part III 1(A)iv row 3 Thruster (p. 17)

> Capability to ionize N2, atomic oxygen in same thruster and It should have capability to use Xe as propellant, an extra input system to take care any problems on board unforeseen problems.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-10 / RVM-29, RVM-15 / RVM-28.

One H-1 Hall accelerator serves both supply modes with one downstream RF-ICP neutralizer (no hollow cathode): AIR is the primary nominal mode (N2 / O-bearing ambient air, DBF12-OPS-01); Xe is the required secondary mode for contingency / off-nominal / upper-envelope operation with the atmospheric compressor OFF (DBF12-OPS-02) - the RFP's extra input system. Trace: RVM-10 / RVM-29 CONFORMING_BY_DESIGN; RVM-15 / RVM-28 CONFORMING_BY_DESIGN / VERIFY_EM_QM. Ionization of atomic O is not demonstrated: O2-bearing ground tests are NO_ATOMIC_O, atomic O only through the AO programme; ICP AIR closure BLOCKED BY SPECIFIC MISSING EVIDENCE.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/operating_modes`; `docs/closure/icp/icp_closure_v1.json` `#/closure`

### RFP-P18-01 - Part III 1(A)iv row 4 Power System Electronics (p. 18)

> Power system electronics shall capable taking power from satellite bus and provide the total ABEP system required voltages and Current requirements.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-04.

A propulsion PPU (AL-07, 5.46 kg MEV, PRELIMINARY CBE / NOT MEASURED) takes power from the satellite bus and generates all ABEP supplies: Hall discharge, magnet supplies, 13.56 MHz RF generator + local match (AL-06), ICP collector bias, valve drivers, compressor drive, thermal control, housekeeping. No flight cathode heater / keeper supply exists. Bus power at the AIR 12 mN point: 1,222.3 W reference / 1,263.1 W conservative (P6 ledger + DBF-1.2 compressor, A9.43).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/power_rollup`; `docs/closure/power/power_ledger_v1.json` `whole file`

### RFP-P18-02 - Part III 1(A)iv row 5 Reliability (p. 18)

> The system should have redundancy in Electronics level and sensor level if any.

**Status: PARTIAL** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: RVM-19.

Electronics level: the DBF-1.2 PPU estimate carries N+1 / redundant electronics (trace RVM-19: CONFORMING_BY_DESIGN (PPU N+1) / VERIFY_FMEA); verification by FMEA at PDR-1. Sensor level: no sensor-redundancy concept is defined in DBF-1.2; it is an owner design decision to be booked within the mass risk MR-DCR001-01 (OIR-TEC-02).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace[rvm=RVM-19]`

Owner input: OIR-TEC-02

### RFP-P18-03 - Part III 1(A)iv row 6 Any other Points (p. 18)

> a) Indigenous Content: >60% to mitigate International Traffic in Arm Regulations (ITAR)/ export control restrictions b) Development partner shall be called for a presentation as part of Technical Evaluation to present the technical proposal in detail (design, realization, testing and schedules) to a technical evaluation committee. c) Consortium of different industries (if proposed) should be supported by documentary proof of consortium agreement.

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

a) Indigenous content > 60 %: no supplier is selected, so no IC figure is stated (frozen programme limit IC >= 75 % total, config/constraints). b) Vyovrinda will present the technical proposal to the technical evaluation committee (presenters: owner). c) Consortium and its documentary proof: owner.

Evidence at 45492a8: `config/constraints/engineering_constraints_v1.json` `#/constraints/ic_total_min`

Owner input: OIR-IC-01, OIR-ORG-04, OIR-ORG-05

### RFP-P18-04 - Part III 2 Functional Orbit altitude (p. 18)

> 180 to 230 km

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-01.

AIR mode operates by density-aware altitude scheduling within 180-230 km, at the 12 mN sizing point, inside the admissible AIR density / thrust / drag window (DBF12-OPS-01, A9.40); Xe mode covers contingency / off-nominal / upper-envelope cases. The 196-state set is a conservative verification dataset, not 196 mandatory AIR points (DBF12-OPS-03). Trace RVM-01: CONFORMING_BY_DESIGN / VERIFY_EM_QM. Host drag at PDR: IR-HOST-DRAG-01 (reference proposal sizing C_D*A 0.50 m2, REFERENCE_PENDING_ICD).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/operating_modes`; `docs/decisions/OD_2026_10_10_A9_40_dbf_1_2_freeze_gates_air_operating_concept_host_drag.json` `whole file`

### RFP-P18-05 - Part III 2 Air intake Specification (p. 18)

> Shall be decided by air density based on solar activity and altitude

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-08, RVM-01.

The intake is sized from air density as a function of solar activity and altitude (frozen NRLMSIS 2.1 data; conservative 196-state set). A single fixed intake cannot span the whole state set (conservation finding, architecture closure conclusion v2), so DBF-1.2 freezes a 0.70 m2 aperture with active compressor / retention control and density-aware altitude scheduling inside 180-230 km (DBF12-IN-01 / -02, DBF12-OPS-01).

Evidence at 45492a8: `docs/closure/conclusion/ARCHITECTURE_CLOSURE_CONCLUSION_v2.md` `section 2-3`; `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/intake_compressor_feed`

### RFP-P18-06 - Part III 2 Thrust Requirement (p. 18)

> 12 mN to 25 mN (From expected drag to compensate)

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-02, RVM-03.

Design basis (owner reading DISC-07): >= 12 mN sustained on air and 25 mN capability. 12 mN AIR sizing point (DBF12-AIR-01): v_eff 26.8 km/s, Hall feed 0.448 mg/s, discharge allocation P_d 650 W (FROZEN_ASSUMPTION; v_eff basis PARAMETRIC / NOT_VALIDATED, VR-HALL-01; 22 km/s sensitivity needs 0.545 mg/s, VR-HALL-02). 25 mN is a Xe-mode design capability with a Hall discharge allocation <= 876.1 W (nominal ICP) / <= 747.5 W (+100 W RF) at the 1,450 W design ceiling. Trace RVM-02 CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM; RVM-03 CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM. Not demonstrated: no Vyovrinda hardware has been built or tested; Hall-transport validation (gate 3) is FAIL and the credible transport set is empty, so every Hall performance figure is a design allocation or a PARAMETRIC / NOT_VALIDATED model value, never a measurement.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/air_design_point`; `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/power_rollup/xe_25mN`; `docs/decisions/OD_2026_10_10_A9_43_power_reconciliation_and_dbf_1_2_freeze.json` `whole file`

### RFP-P18-07 - Part III 2 Thruster Type (p. 18)

> Hall effect preferable

**Status: COMPLY** (bid package: COMPLY). DBF-1.2 trace: RVM-11.

The offered thruster is a Hall-effect thruster: one H-1 Hall accelerator (d_mean 70 mm, h 12 mm, L 103.2 mm; DBF1-H1-01..03). This states the thruster type only; no Hall performance is demonstrated.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items[id=DBF1-H1-01]`

### RFP-P18-08 - Part III 2 Propellant for propulsion system (p. 18)

> Compatible for using Ambient air (at the functional orbit altitude of 180-230km) and Xenon as propellant. Two separate propellant tanks for ambient air and xenon.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-08, RVM-10 / RVM-29.

Split (owner ruling A9.27, kept): (A) separate ambient-air path (intake -> compressor -> plenum) and separate Xe storage / flow branch (AL-08, 2.919 kg MEV with the 2.0 kg Xe reference load) - COMPLY BY DESIGN; (B) functional ambient-air + Xe propulsion capability - PLANNED / NOT YET DEMONSTRATED (verified on EM / QM). Trace RVM-08 CONFORMING_BY_DESIGN / VERIFY_EM_QM; RVM-10 / RVM-29 CONFORMING_BY_DESIGN.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/mass_rollup`; `docs/decisions/OD_2026_10_05_A9_27_final_bid_owner_rulings.json` `#/owner_decision_summary`

### RFP-P18-09 - Part III 2 Redundancy (p. 18)

> Must cater to single point failure for electronics.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: RVM-19.

Single-point-failure tolerance for electronics: the DBF-1.2 PPU estimate carries N+1 / redundant electronics (RVM-19 CONFORMING_BY_DESIGN (PPU N+1) / VERIFY_FMEA); the electronics FMEA / single-point-failure list at PDR-1 verifies it.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace[rvm=RVM-19]`

### RFP-P18-10 - Part III 2 Power (p. 18)

> <1500W

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-04, RVM-05.

P_bus (all power crossing the spacecraft-side DC boundary) at AIR 12 mN: 1,222.3 W reference / 1,263.1 W conservative, margins 277.7 / 236.9 W to 1,500 W and 127.7 / 86.9 W to the internal 1,350 W allocation. Xe 25 mN is held inside the 1,450 W design ceiling by its discharge allocation. Under the P6 conservative non-discharge corner the AIR bus is 1,469.9 W (< 1,500 W, > 1,350 W; VR-PWR-01). Trace RVM-04 CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM. Measured on EM / QM.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/power_rollup`; `docs/closure/power/power_ledger_v1.json` `whole file`

### RFP-P18-11 - Part III 2 Mass (p. 18)

> < 40kg

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-06, RVM-07.

Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin. Roll-up (A9.41): non-harness 32.773 kg + harness 1.725 kg = nominal dry 34.498 kg; + 10 % system margin = 37.948 kg; + 2.0 kg Xe reference = 39.948 kg wet. Trace RVM-06 CONFORMING_BY_PRELIMINARY_ROLLUP / OPEN_MASS_RISK; the internal 34 kg nominal-dry target is not met (RVM-07 TARGET_NOT_MET (nominal dry 34.498 kg)). Confirmed by CBE, quotation and EM mass measurement; any growth needs a DCR.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/mass_rollup`; `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks[id=MR-DCR001-01]`; `docs/decisions/OD_2026_10_10_A9_41_dcr_dbf1_001_approval_mass_risk.json` `whole file`

### RFP-P18-12 - Part III 2 Electrical Interface (p. 18)

> MIL-1553B with satellite onboard computer for configuration and for high rate data-logging with data recorder. Discrete interface for thruster operation. Necessary hardware drivers to be part of propulsion system.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-20.

MIL-STD-1553B remote terminal to the onboard computer for configuration and high-rate data logging, discrete lines for thruster operation, drivers inside the propulsion system. Allocated to AL-09 controls / FDIR (1.0 kg, owner allocation; RVM-20 ALLOCATED_TO_AL-09). Interface ICD at PDR-2; verified by inspection and a representative-bus test.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace[rvm=RVM-20]`

### RFP-P19-01 - Part III 2 Life Cycle and Maintainability (p. 19)

> Mission life: 3 years (Approx 26000 hrs). Ignition Time: More than 15000 hrs

**Status: NOT_YET_DEMONSTRATED** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: RVM-12 / RVM-13.

Design basis: mission life >= 26,280 h and > 15,000 h cumulative firing (frozen engineering constraints). DBF-1.2 trace RVM-12 / RVM-13: VERIFY_EM_QM: life is verified by wear / endurance tests (AO / lifetime register); no admissible life analysis exists.

Evidence at 45492a8: `config/constraints/engineering_constraints_v1.json` `#/constraints/mission_life_h`; `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `whole file`

### RFP-P19-02 - Part III 2 Material Specifications (p. 19)

> All materials and processes used in the product realization should be space qualified for Qualified model.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-16.

Space-qualified materials and processes for the QM. Frozen selections (DBF-1.1 inherited): anode / gas distributor INCONEL 600 (backup 601), ICP collector INCONEL 600 / 601, channel wall BN-SiO2 (backup BN), ICP vessel borosilicate. Materials state FROZEN FOR EM: no gate fails on evidence; the open gates close by coupon / EM tests.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items[id=DBF1-MAT-01]`; `docs/closure/materials/materials_gates_v1.json` `#/closure_state`

### RFP-P19-03 - Part III 2 Subsystems (p. 19)

> The overall system shall consist of the following sub-systems a. Air Intake and Compressor storage b. Power Supply Electronics c. Thruster

**Status: COMPLY** (bid package: COMPLY). DBF-1.2 trace: none.

Subsystems (owner ruling A9.27, composition only): a. Air intake and compressor storage (AL-01 intake, AL-02 compressor, AL-03 plenum / feed; plus the separate Xe branch AL-08); b. Power supply electronics (AL-07 PPU, AL-06 RF generator / match, AL-09 controls / 1553B); c. Thruster (AL-04 Hall head + magnets, AL-05 ICP neutralizer). No performance or qualification claim.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/mass_rollup/lines_mev_kg`; `docs/decisions/OD_2026_10_05_A9_27_final_bid_owner_rulings.json` `#/owner_decision_summary`

### RFP-P19-04 - Part III 2 Environment (p. 19)

> The product should qualify the launch vibrations and shock. The product shall qualify atomic oxygen erosion, radiation, thermal and ThermoVac specifications for a VLEO orbit with a mission life of 3 years. Atomic oxygen erosion environment, All parts in Intake, Compressor and Thruster design shall take care of nascent atomic oxygen erosion for lifetime. ENTEST Specifications (The specifications will be provided at the time PDR): The system has to qualify for VLEO environment for a lifetime 03 yrs and for launch loads of PSLV/ SSLV or any other Launch Vehicle decided by DRDO at the time of PDR.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-21, RVM-17.

QM ENTEST qualification (launch vibration / shock, AO erosion, radiation, thermal, ThermoVac, 3-year VLEO life) at Milestone 5 against the specification issued at PDR (no numeric levels assumed, DISC-09). Thermal: cathodeless topology frozen (DBF1-TH-01, 50 K margin rule); thermal closure state DCR REQUIRED (RVM-17 VERIFY_EM_QM); the co-located RF match exceeds its ceiling in the hot cases and is under DCR-DBF1-003 (REQUESTED_EVALUATION_TO_BE_PREREGISTERED).

Evidence at 45492a8: `docs/closure/thermal/thermal_closure_v2.json` `#/closure`; `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items[id=DBF1-TH-01]`

### RFP-P19-05 - Part III 3 Indigenous Content (p. 19)

> The firm should provide a detailed plan for achieving the minimum 75% IC in the project deliverables. Minimum Indigenization Desired: 1. Space Qualified Thruster >80%; 2. Intake system >80%; 3. Compressor and Storage >60%; 4. Power Supply Electronics >70%.

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

A detailed plan for >= 75 % project IC (thruster > 80 %, intake > 80 %, compressor and storage > 60 %, PSE > 70 %) is required; no supplier is selected, so no IC percentage is stated.

Evidence at 45492a8: `config/constraints/engineering_constraints_v1.json` `#/constraints/ic_subsystem_min`

Owner input: OIR-IC-01, OIR-IC-02, OIR-IC-03

### RFP-P19-06 - Part III 4.1 Testing (p. 19)

> The system performance should be demonstrated by means of following tests: a) Coating materials and surface tests with Atomic Oxygen beam exposure, Erosion yield measurement. b) Creation of rarefied gas with prescribed mg/sec and velocity to test Intake system Erosion process. c) Minimum functional performance testing for EM and QM in integration mode for force calculation, with variable air intake (mg/sec), Isp, Efficiency of the total system etc. d) The test plan document for different tests shall be reviewed/ finalized through an expert committee and approved by PMMG/SPMMG.

**Status: PARTIAL** (bid package: PARTIAL). DBF-1.2 trace: RVM-16.

a) AO-beam coating / erosion-yield tests: planned (AO / lifetime register, witness coupons; materials gates EM_VERIFICATION_REQUIRED); facility / fluence: owner. b) Rarefied-gas source with prescribed mg/s and velocity for intake tests: no facility record (owner). c) EM / QM force, variable intake mg/s, Isp and total-system efficiency: planned (thrust stand INS-01, time-resolved bus-power metering). d) Test plan reviewed by the expert committee: accepted.

Evidence at 45492a8: `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json` `whole file`; `docs/experiments/instrumentation/instrumentation_definition_v1.json` `#/instruments`

Owner input: OIR-FAC-02, OIR-FAC-03, OIR-FAC-04

### RFP-P20-01 - Part III 4.2-4.3 (p. 20)

> 4.2 Acceptance Criteria: Deliverable of the project should be matched with parameters given below in Para 2. 4.3 Certification: The Company shall be ISO certified. i. Acceptance/Qualification based on ATP Document. Preparation of ATP document will be carried out based on parameters listed in Para 2 above and will be finalized after DDR/CDR. ii. Testing as per Applicable Standards (MIL / ASTM/ BIS etc) / ESS Specification

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

4.2: deliverables accepted against the Para 2 parameters (DBF-1.2 requirement trace). 4.3: ISO certification is an owner fact. ATP prepared from the Para 2 parameters after DDR / CDR.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json` `#/trace`

Owner input: OIR-ORG-01

### RFP-P20-02 - Part III 5 (p. 20)

> Trial and Performance Evaluation on system, if required: Only ground demonstration in simulated environment and space qualification testing is desired.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: none.

Only ground demonstration in a simulated environment and space-qualification testing; no flight trial. Evidence order: Ar (engineering only) -> N2 -> O2-bearing (NO_ATOMIC_O) -> atomic-O life programme.

Evidence at 45492a8: `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` `whole file`

### RFP-P20-03 - Part III 6 (p. 20)

> Exit criteria / Risk Management: Successful realization of Engineering Model of ABEP system, realization of qualified electric thruster with O and N2 as propellant at milestone 4 can be considered as a partial success of the project.

**Status: NOT_YET_DEMONSTRATED** (bid package: NOT_YET_DEMONSTRATED). DBF-1.2 trace: none.

Acknowledged. The partial-success criterion (EM ABEP system and a qualified thruster on O and N2 at Milestone 4) depends on evidence that does not yet exist: measured air-Hall performance (VR-HALL-01), ICP AIR closure (BLOCKED BY SPECIFIC MISSING EVIDENCE) and atomic-O evidence. Principal schedule risk.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks[id=VR-HALL-01]`; `docs/closure/icp/icp_closure_v1.json` `#/closure`

### RFP-P20-04 - Part III 7 Milestone 1 (p. 20)

> Preliminary Design Review-1 (Hardware); PDC T0+09 months; 15%: completion of preliminary design (mechanical and electrical), finalization of BoM; preliminary test plan review; clearance for EM hardware realization. Deliverables: approved PDR document, design documents, CAD & EDA models; preliminary test plan and test facility document.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: none.

Milestone 1 (PDR-1, T0+09 months, 15 %): DBF-1.2 is the preliminary design entering PDR-1; PDR-1 closes the early confirmations (PPU CBE VR-PPU-01, Xe tank quotation VR-XE-01, AL-09 / AL-10 CBEs, routed harness, electronics FMEA), BoM and test-facility document.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks`

### RFP-P20-05 - Part III 7 Milestone 2 (p. 20)

> Preliminary Design Review-2 (Algorithms and Software and Test plan); T0+12 months; 10%: electric power supply system software preliminary design, FDIR, Telemetry (MATLAB and C); review of test facility readiness. Deliverable: approved GNC design document and codes.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: none.

Milestone 2 (PDR-2, T0+12 months, 10 %): PSE software preliminary design incl. start-up sequencing and FDIR, telemetry (MATLAB and C), 1553B / discrete ICD, test-facility readiness. The RFP names the deliverable 'approved GNC design document and codes' (verbatim; owner to confirm the reading).

### RFP-P20-06 - Part III 7 Milestone 3 (continues p21) (p. 20)

> Critical Design Review; T0+20 months; 20%: realization of Engineering Models of thruster, power supply electronics; demonstration of functionality of EM hardware with Storage input not with INTAKE; clearance for qualification unit realization except Intake system. Deliverables: EM units power electronics and thruster mechanical and electrical drawings, CAD models; test results documents, test plan documents; simulation models (mechanical and electrical); test software.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: none.

Milestone 3 (CDR, T0+20 months, 20 %): EM thruster (H-1 + ICP) and EM PSE demonstrated with STORAGE input (stored N2 / Xe), not intake: measured H-1 thrust / feed map, Xe 25 mN power (VR-XE-02), ICP coupling, measured B(z).

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks[id=VR-XE-02]`

### RFP-P21-01 - Part III 7 Milestone 4 (p. 21)

> Engineering model Intake system; Qualification model for Power Supply Electronics and Thruster; T0+24 months; 35%: realization of Engineering model Intake System with Compressor and Storage; complete Qualification model PSE and Thruster testing with Storage Atomic reminants. Deliverables: EM Intake with compressor and Storage unit design details, CAD & EDA models, drawings etc; QM PSE, Thruster units design details, CAD & EDA models, drawings etc.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: none.

Milestone 4 (T0+24 months, 35 %): EM intake with compressor and storage (VR-CMP-01..04, VR-FEED-01); QM PSE and thruster testing. Carries the RFP-P20-03 exit-criterion risk.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks`

### RFP-P21-02 - Part III 7 Milestone 5 (p. 21)

> QM integration and testing Delivery; T0+36 months; 20%: realization of QM Intake system and integration as total QM model ABEP; ENTEST qualification of QM units, documentation and delivery; documentation and final delivery, completion of project closure formalities.

**Status: COMPLY_PLANNED_WITH_EVIDENCE_PATH** (bid package: COMPLY_PLANNED_WITH_EVIDENCE_PATH). DBF-1.2 trace: RVM-21.

Milestone 5 (T0+36 months, 20 %): QM intake, total QM integration, ENTEST qualification (VR-EMQM-01), documentation, delivery and closure.

Evidence at 45492a8: `docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json` `#/risks[id=VR-EMQM-01]`

### RFP-P21-03 - Part III 8 (p. 21)

> NO Waivers shall be given for PART (IV) (B).

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

Acknowledged: no waiver is sought for Part IV(B). Its items (financial, heritage, infrastructure, manpower, academia) are organisational facts the repository does not hold.

Owner input: OIR-ORG-02, OIR-ORG-03, OIR-ORG-06

### RFP-P27-01 - Part IV(B) 3 Infrastructure (p. 27)

> i. Ultra High Vacuum Test Facility for propulsion system testing (In-house/ Consortium/ Sub contract); ii. Low Thrust measurement setup (In-house/ Consortium/ Sub contract).

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

UHV propulsion test facility and low-thrust measurement setup (in-house / consortium / sub-contract): owner facts. The repository defines the instrumentation requirements (INS-01).

Evidence at 45492a8: `docs/experiments/instrumentation/instrumentation_definition_v1.json` `#/instruments`

Owner input: OIR-FAC-01, OIR-FAC-02

### RFP-P27-02 - Part IV(B) 5 (p. 27)

> Collaboration with Academia / Research Institute/Experts with specific work share related to following critical technologies of project: i. Material compatibility of Intake and thruster exposed to atmospheric nascent Oxygen (LoI from experts or MoU with institute is to be produced).

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

Collaboration with academia / research institute on material compatibility with nascent O (LoI / MoU): owner. The materials gates and AO programme define the work share.

Evidence at 45492a8: `docs/closure/materials/materials_gates_v1.json` `#/gates`

Owner input: OIR-ORG-03

### RFP-P30-01 - Part IV(C) 5 Thrust Measurement System (p. 30)

> Thrust Measurement System capable of measuring micro-Newton level thrust (In house: 10; Consortium: 5; Sub-contract: 0 marks).

**Status: OWNER_INPUT_REQUIRED** (bid package: OWNER_INPUT_REQUIRED). DBF-1.2 trace: none.

Micro-newton-level thrust measurement (scored in-house / consortium / sub-contract). The planned stand INS-01 targets 12-25 mN; it is not evidence of micro-newton capability (DISC-10).

Evidence at 45492a8: `docs/experiments/instrumentation/instrumentation_definition_v1.json` `#/instruments`

Owner input: OIR-FAC-02
