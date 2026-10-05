# 03 - Development and test plan

**Status: DRAFT_FOR_OWNER_REVIEW.** Technical source: commit `b0937e8` (`b0937e88b4ad21cb31c5778aac4b3dca88fdd94a`, pinned by
`docs/bid/bid_technical_baseline_v2.json`); every cited path is a file at that commit. **No calendar date is stated.**
The only times used are the RFP's own T0 offsets and payment percentages (RFP-P20-04 .. RFP-P21-02). T0 is not set
(RVM-25), and resourcing the hardware order inside these offsets is an owner confirmation (OIR-SCH-01).

## 1. Principles

1. **Hardware first.** The decisive thrust question is answered by a controlled hardware experiment, not by the
   simulator (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`). Modelling continues in parallel and never gates
   hardware preparation.
2. **Fail-closed gates.** A gate without its required evidence is NOT_EVALUATED, never PASS or GO (A9.21 item 4; RVM
   status rules `docs/requirements/rvm_a9/rvm_a9_v1.json` `#/status_rules`).
3. **Pre-registration.** Criteria, domains and thresholds are frozen before the data that is scored against them
   (LOCK-1 before S1; LOCK-2 from measured S1 noise / calibration before score-bearing runs; P4 thresholds before
   acceptance-bearing exposure). Part of the new hardware data is pre-registered, before any data, as held-out
   Hall-transport validation evidence; P5-N2 v1 stays INCONCLUSIVE and is never rewritten.
4. **Evidence order by gas.** Ar (engineering / commissioning only, never counts for a requirement) -> N2 ->
   O2-bearing (labelled NO_ATOMIC_O) -> separate atomic-O life programme
   (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json`). Each gas / mode gets its
   own operating domain and provenance (A9.21 item 8).
5. **Physics and assessment stay separate.** Frozen engineering constraints (`config/constraints/engineering_constraints_v1.json`,
   FROZEN (12/12)) and the frozen operating scenario (mission_scenario_v2 (FROZEN_ENGINEERING_CONFIGURATION, FROZEN)) are configuration; a compliance threshold never
   changes raw physics.

## 2. A9.21 hardware programme (owner order)

Source: `docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json` `#/steps` (generated companion
`HW_PROGRAMME_A9_21.md`); decision `docs/decisions/OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json`.
Only the predecessor column binds; the listing order is not a sequence. Entry statuses are read from the programme record
at b0937e8; none of them is a test result or a start authorisation.

| # | step | what | predecessor (basis) | entry status at b0937e8 |
|---|---|---|---|---|
| 1 | H1-S7.1 | FEMM magnetostatics of MC-1 at the authorised analysis points | - | NOT_STARTABLE_PRECONDITION_MISSING |
| 2 | H1-S7.2 | H-1 engineering channel point (magnetic feasibility, thermal margin, mass, packaging, manufacturability; not thrust-optimised) | H1-S7.1 (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 3 | C1-REF | H-1 + C1 ground reference characterization (C1 GROUND_REFERENCE_ONLY); registers I_d,max,H1,Ar | H1-S7.2 (PHYSICAL_PREREQUISITE_RECORDER) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 4 | ICP-AR-REF | ICP Ar engineering / commissioning reference (P1 stages) | - | ENTRY_GATED_BY_EXISTING_STAGE_RULES |
| 5 | ICP-45A-P1-S7 | ICP-45 capacity stage on Ar (needs I_d,max,H1,Ar frozen first) | C1-REF (EXPLICIT_A9_21), ICP-AR-REF (EXISTING_OWNER_RULE) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 6 | ICP-45N | registered air / N2 ICP-45 campaign (own domain, provenance, four closures frozen first) | ICP-45A-P1-S7 (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 7 | ICP-XE-MODE | separate registered Xe-mode campaign (contingency supply mode) | ICP-45N (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 8 | P2-MAP | ICP plasma impedance map, after the in-house V/I magnitude / phase calibration and its uncertainty budget are frozen | - | NOT_STARTABLE_PRECONDITION_MISSING |
| 9 | COUPLED-H1-ICP | coupled H-1 + ICP operation | - | NO_A9_21_ENTRY_PRECONDITION_LISTED |
| 10 | P3-THERMAL | coupled thermal analysis and test | COUPLED-H1-ICP (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 11 | P4-ACCEPTANCE-EXPOSURE | anode-material acceptance-bearing coupon exposure (LOCK-2 thresholds frozen first) | P3-THERMAL (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 12 | H1-THRUST-FEED-MAP | measured H-1 thrust / feed map (mandatory) | - | NO_A9_21_ENTRY_PRECONDITION_LISTED |
| 13 | AG-12 | performance-derived, statewise feed-state sufficiency | H1-THRUST-FEED-MAP (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |
| 14 | AG-13 | statewise drag compensation T_available(state) - D_spacecraft(state) >= 0 | AG-12 (EXPLICIT_A9_21) | NOT_STARTABLE_PREDECESSOR_INCOMPLETE |

Programme flow in short: **H1-S7.1 FEMM -> S7.2 -> C1 reference -> ICP Ar -> N2 ICP-45 -> Xe; P2 after calibration
freeze; coupled H-1 + ICP -> P3 -> P4; measured thrust / feed map -> AG-12 -> AG-13.**

## 3. Gates

| gate | placement | status at b0937e8 (verbatim) | criteria | source |
|---|---|---|---|---|
| GNG-ICP-01 ICP go / no-go | mandatory, before LOCK-1 | NOT_EVALUATED | criteria PENDING_OWNER_ACCEPTANCE (no numerical criterion approved; recorder proposal RP-A919-01 preserved for review only) | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/pre_lock1_gates[id=GNG-ICP-01]` |
| LOCK-1 | after D-01..D-15 and GNG-ICP-01 | not releasable (`lock1_release_reportable` false) | owner decisions D-01..D-15 | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/lock1_precondition` |
| ICP-45 (AG-04) | before relying on ICP capacity | PENDING_ICP45; ICP45 NOT_EVALUATED | I_e,cap (discharge-OFF, signed) vs I_d,max,H1 | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-04]` |
| AG-05 coupled H-1 / ICP thermal | before freeze | UNRESOLVED | P3 (cathodeless successor model post-bid, AFI-03) | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-05]` |
| AG-06 anode thermal | before freeze | UNRESOLVED | P3 | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-06]` |
| AG-07 anode material | before freeze | OPEN | P4 under LOCK-2 | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-07]` |
| AG-10 bus power | before freeze | PARTIAL_BOUNDARY | P_bus,1ms,max < 1500 W | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-10]` |
| AG-11 mass | before freeze | INCOMPLETE_EVIDENCE (no CBE; AL-04 / AL-07 / AL-08 below evidence floors) | < 40 kg wet on CBE / measured mass | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-11]` |
| AG-12 feed-state sufficiency | after the measured thrust / feed map | NOT_EVALUATED (validated H-1 thrust-versus-feed map does not exist) | statewise | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-12]` |
| AG-13 drag compensation | after AG-12 and the host drag ICD | NOT_EVALUATED | statewise | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-13]` |
| AG-02 Hall credible transport set | successor held-out validation | EMPTY (members = []) | pre-registered successor validation | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-02]` |
| AG-03 Hall-transport validation | successor held-out validation | INCONCLUSIVE (permanent; promotable = []) | P5-N2 v1 unchanged | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-03]` |
| AG-15 requirement basis | before freeze | DETERMINING_EVIDENCE_PRESENT_NO_REMAINING_CONDITION | owner closure of the RVM re-base (requirement basis only) | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates[id=AG-15]` |

S1 (qualification of stand and metrology) follows LOCK-1 and the hardware / instrumentation; LOCK-2 is frozen from the
measured S1 noise / calibration before score-bearing runs (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`); neither
has started. The full AG-01..AG-15 list with verbatim statuses is in `01_COMPLIANCE_MATRIX.md`.

## 4. Mapping onto the RFP milestones (PROPOSED for owner confirmation)

The mapping below is this package's proposal. It uses only the RFP's offsets and percentages.

| RFP milestone | offset / payment | RFP content (registered clause) | programme content proposed for this milestone | evidence entering the review |
|---|---|---|---|---|
| M1 PDR-1 (Hardware) | T0+09 months, 15 % | preliminary mechanical / electrical design, BoM, preliminary test plan, EM clearance; PDR document, CAD / EDA, test-facility document (RFP-P20-04) | H1-S7.1 FEMM and H1-S7.2 channel point; GNG-ICP-01 criteria accepted by the owner; D-01..D-15 -> LOCK-1 preparation; PPU block diagram and electronics FMEA / redundancy concept; mass-closure actions (AL-07 current cathodeless PPU CBE / requote; AL-08 quote / design rebase; AL-04 completed Hall-head CBE; AL-09 design-derived CBE; actual routed harness; subsystem integration / structural optimization); upstream flow-gap levers in the owner order (F9-DF-01); RFQ quotations returned (AL-08 rebase); test-facility document (OIR-FAC-01..04) | H-1 freeze-candidate definition, RVM, mass record mass_power_a9_v4, bus boundary v2, instrumentation definition, RFQ v3 packages and the RFQ3-GAS rev1 successor |
| M2 PDR-2 (Algorithms, Software, Test plan) | T0+12 months, 10 % | PSE software preliminary design, FDIR, telemetry (MATLAB and C), test-facility readiness (RFP-P20-05) | PSE / PPU controller software preliminary design incl. start-up sequencing (SEQ-1) and FDIR; 1553B / discrete ICD; C1-REF on the built H-1 (I_d,max,H1,Ar registered; C1 GROUND_REFERENCE_ONLY); ICP-AR-REF commissioning; P2 calibration and uncertainty budget frozen; S1 stand / metrology qualification | bus-boundary sequencing, P1 / P2 frameworks |
| M3 CDR | T0+20 months, 20 % | EM thruster and EM PSE realized and demonstrated with STORAGE input, not intake (RFP-P20-06) | GNG-ICP-01 evaluated -> LOCK-1 -> S1 -> LOCK-2; ICP-45A, ICP-45N, ICP-XE-MODE campaigns; P2-MAP; COUPLED-H1-ICP on stored N2 and Xe; measured H-1 thrust / feed map; AG-12 evaluated | measured records (none exist at b0937e8) |
| M4 EM intake; QM PSE and thruster | T0+24 months, 35 % | EM intake with compressor and storage; QM PSE and thruster testing (RFP-P21-01); exit criterion: qualified thruster with O and N2 (RFP-P20-03) | P3-THERMAL; P4-ACCEPTANCE-EXPOSURE; EM intake / compressor / storage with the RFP-P19-06 b rarefied-gas test; AG-13 statewise check once the host drag ICD exists; QM PSE and thruster tests on N2 and O2-bearing gas (NO_ATOMIC_O) plus the AO programme | measured records |
| M5 QM integration, ENTEST, delivery | T0+36 months, 20 % | QM intake, total QM ABEP integration, ENTEST qualification, documentation and delivery (RFP-P21-02) | QM integration and ENTEST against the PDR-issued specification (launch vibration / shock, AO, radiation, thermal, ThermoVac); ATP after DDR / CDR | QM test reports |

**Schedule risk to disclose:** the Milestone-4 exit criterion (qualified thruster with O and N2) depends on Hall-transport
validation, O-bearing operation and atomic-O evidence that do not exist at the technical source (risks R-01, R-02, R-09).
The owner must decide how the bid presents this (OIR-SCH-01).

## 5. RFP test requirements (RFP-P19-06) and how they are planned

| RFP 4.1 item | plan at b0937e8 | gap / owner input |
|---|---|---|
| a) AO-beam coating / surface tests, erosion-yield measurement | AO / lifetime register v5 (`docs/experiments/lifetime_ao/ao_lifetime_register_v5.json`): witness coupons, AOL-EX-01 / -02 ground exposure, post-test SEM / EDS / XPS; P4 screens | ground AO facility and target fluence (AOL-OQ-05) -> OIR-FAC-04 |
| b) rarefied gas with prescribed mg/s and velocity for intake-erosion tests | none: no facility or test record exists (RVM-22) | OIR-FAC-03 |
| c) EM / QM functional performance in integration mode: force, variable intake mg/s, Isp, total-system efficiency | thrust stand INS-01 (torsional or inverted pendulum, null-type preferred, in-situ calibration under vacuum; `docs/experiments/instrumentation/instrumentation_definition_v1.json` `#/instruments`); time-resolved bus-power metering; Isp and efficiency derived from the same measured thrust | stand ownership / resolution -> OIR-FAC-02 |
| d) test plan reviewed by an expert committee, approved by PMMG / SPMMG | accepted as process; the pre-registered campaign documents are the inputs | - |

Thrust-measurement note: the planned stand targets the 12-25 mN range; it is **not** evidence of micro-newton-level
capability (RFP-P30-01; DISC-10).

## 6. Verification approach (RVM)

Every RFP-derived requirement is carried by a row of `docs/requirements/rvm_a9/rvm_a9_v1.json` with its verification
methods (analysis, inspection, test). Status rules: no PASS without determining evidence; implementation completeness
is never compliance. AG-15 (owner closure of the RVM re-base against the registered RFP) at b0937e8: DETERMINING_EVIDENCE_PRESENT_NO_REMAINING_CONDITION;
`requirement_frozen` is true on 22 of 22 RFP-clause rows (A9.22 G3 requirements
snapshot). This freezes the requirement basis only, never compliance: every row keeps its evidence status.
