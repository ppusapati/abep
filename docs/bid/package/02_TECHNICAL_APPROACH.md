# 02 - Technical approach

**Status: DRAFT_FOR_OWNER_REVIEW.** Bidder: Vyovrinda Aerospace. Tender 2026_DRDO_788433_1, RFP
DTDF/06/13516/DSP/ABEP/X/L/M/01 (Part III). Technical source: bid freeze commit `bbc480c`
(`bbc480cd6aacaa40c39eb459a056b942fe996b32`, `docs/bid/bid_technical_baseline.json`). Every path cited below is a file at
that commit (`git show bbc480c:<path>`). Nothing in this document is submitted by the repository.

**Quantity labels (CLAUDE.md rule 10, `docs/EVIDENCE.md`).** Every number carries one label: *measured*, *model-derived*,
*assumed*, *owner-allocation* (an owner design allocation, not evidence), or *pending* (no value exists yet). There is no
*measured* Vyovrinda hardware value at the freeze: no H-1, ICP, PPU or upstream hardware has been built or tested.

## 1. Validation status (read first)

| item | status at bbc480c | source |
|---|---|---|
| Architecture | INVESTIGATION_HYPOTHESIS; frozen reference flight architecture: false | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_status` |
| Hall-transport validation (gate 3) | FAIL. P5-Xe: transport not identifiable; P5-N2 v1: all 9 screening candidates INCONCLUSIVE / NOT ELIGIBLE (permanent) | `CLAUDE.md` section "Gate status"; `hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json` |
| Credible Hall transport set | EMPTY (members = []) | `hallthruster_bridge/ensemble/transport_ensemble_v0.json` `#/members` |
| Absolute Hall performance (thrust, Isp, efficiency, discharge current, life) | none offered. Every absolute result of the superseded 0-D Hall closure is WITHDRAWN and is not quoted anywhere in this package | `CLAUDE.md` section "Superseded / withdrawn (do not quote)" |
| RVM, flight configuration `hall_icp_neutralizer` | 27 NOT_EVALUATED, 3 INCOMPLETE_EVIDENCE, 0 PASS | `docs/requirements/rvm_a9/rvm_a9_v1.json` `#/status_counts` |
| Architecture-level gates AG-01..AG-15, GNG-ICP-01 | none sufficient for freeze; none PASS / GO (table in `01_COMPLIANCE_MATRIX.md`) | `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/architecture_gates`, `#/pre_lock1_gates` |

The programme is therefore **hardware-first**. The owner moved the decisive-thrust question from literature and
simulation to a controlled hardware experiment (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`). The order of that
hardware programme is A9.21 (`docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json`); see
`03_DEVELOPMENT_AND_TEST_PLAN.md`. Thrust, power and life numbers will come from measurements on the Vyovrinda hardware,
not from the simulator.

## 2. Architecture

Owner decision A9.19 (`docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json`
`#/architecture`), status of the A9 line `OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE`
(`docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json`):

- **one Hall accelerator (H-1)**: ionization zone and acceleration zone in one annular channel (RFP Figure 1 "Thruster
  (Ionization zone | Acceleration zone)");
- **one downstream 13.56 MHz RF inductively coupled plasma (ICP) electron source / neutralizer**, cathodeless and
  electrodeless, serving both supply modes. Topology precedent only: Takahashi et al., J. Electr. Propuls. 3:18 (2024)
  (cited in the A9 decision);
- **two propellant supply modes**: ambient atmospheric propellant (primary) and xenon (contingency / emergency;
  RFP-P17-05 "an extra input system to take care any problems on board unforeseen problems", RFP-P18-08 two separate
  tanks; `#/xenon_role`);
- **no conventional hollow cathode** in the flight architecture. The heated Xe-fed LaB6 hollow cathode C1 is a
  **ground-only laboratory reference** (owner decision A9.20,
  `docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json`): it registers I_d,max,H1,Ar on H-1 and is the
  bench control in the C1-vs-ICP comparison; it is never flight hardware and never in the flight mass / power / Xe
  budgets (RVM-30).

### 2.1 Mapping onto the RFP logical block diagram (RFP-P16-02)

| RFP block (Figure 1) | proposed element | repository lane at bbc480c | status |
|---|---|---|---|
| Intake | passive intake (TPMC reduced-order model, Maxwell + CLL wall models) | `docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json` | INVESTIGATION_HYPOTHESIS, screening only |
| Filter | filter stage (protection benefit NOT_EVALUATED; a context axis, not searched) | `docs/design_synthesis/f2_filter/f2_filter_stage_v1.json` | INVESTIGATION_HYPOTHESIS |
| Compressor | compressor (Gaede / turbo-row characteristic) | `docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json` | INVESTIGATION_HYPOTHESIS |
| Gas Chamber | plenum / feed with set-pressure control | `docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json` | INVESTIGATION_HYPOTHESIS |
| Valve | atmospheric metering / isolation valve (driver load slot `flow_control_atmospheric`) | `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` `#/slots` | load TBD |
| Xenon Gas -> Valve | Xe storage and flow hardware (tank, regulator, valves, plumbing, mounting / thermal; AL-08), driver slot `flow_control_xe` | `docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json` `#/lines/hall_icp_neutralizer[line=AL-08]` | provisional planning floor (A9.21 AL08) |
| Thruster (ionization + acceleration) | H-1 Hall accelerator, magnetically shielded topology T2 with MC-1 electromagnet (H1F-MC-01) | `docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json` | NOT_FROZEN engineering freeze candidate |
| (added, outside Figure 1) | downstream RF-ICP neutralizer | `docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md`; `docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json` | ICD DRAFT_PENDING_OWNER; geometry search not run |

The ICP neutralizer is an addition to the RFP diagram (the diagram shows no electron source). It replaces the hollow
cathode that a conventional Hall thruster would carry. The owner should decide whether the bid explains this addition
explicitly next to Figure 1 (recommended; no requirement is changed by it).

### 2.2 Subsystem breakdown (RFP-P19-03)

| RFP subsystem | contents | mass line (owner allocation, MEV level) |
|---|---|---|
| a. Air intake and compressor storage | intake / filter / duct; compressor + drive; plenum / feed; Xe storage / flow (separate path) | AL-01 3.5 kg, AL-02 5.5 kg, AL-03 1.0 kg (*owner-allocation*); AL-08 6.05 kg (*owner-stated MEV planning floor*, provisional) |
| b. Power supply electronics | Hall PPU incl. collector / bias supply; RF generator / matching; controls / valve drivers / flight sensors | AL-07 6.0 kg (*MEV planning floor*); AL-06 1.5 kg (*owner-allocation*); AL-09 no value (TBD_OWNER, MPV3Q-01) |
| c. Thruster | H-1 head + magnet incl. anode heat-removal hardware; ICP neutralizer incl. collector / bias electrode | AL-04 4.20 kg (*MEV planning floor*); AL-05 2.0 kg (*owner-allocation*) |
| (system) | structure / thermal; harness; 20 % system margin | AL-10 2.5 kg (*owner-allocation*); harness by rule; margin 20 % of nominal dry |

Source: `docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json` `#/lines`, `#/margin_convention`. None of these values is a
current best estimate (CBE).

## 3. Thruster: H-1 Hall accelerator

What exists at bbc480c is an engineering-article definition, `docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json`
(status NOT_FROZEN; FREEZE_CANDIDATE items are candidates only):

- topology: T2 magnetically shielded, MC-1 electromagnet only, inner + outer coil with trim-coil provision (H1F-MC-01,
  -02; *owner-allocation* / *assumed*);
- channel: only **windows** exist, no design point. Annulus area 17.02-35.34 cm^2, mean diameter 45.37-100.6 mm,
  width 7.758-17.21 mm, length 66.74-206.5 mm (H1F-CH-02, -04, -05, -10; *model-derived* from xenon scaling rules and
  published analogs). The design point (H1F-CH-11) is TBD and will be selected at H1-S7.2 on magnetic feasibility,
  thermal margin, mass, packaging and manufacturability, **not on thrust** (A9.21 item 6);
- sizing flow about 1.3 mg/s delivered atmospheric flow, operability / thermal characterization range 0.38-3.2 mg/s
  (H1F-CH-12; *owner-allocation*; characterization coverage, not a requirement);
- anode: 316L REJECTED_AS_CURRENT_BASELINE; final material OPEN (P4); heat-removal path, allowable and operating
  temperatures TBD (H1F-AN-04..-08); electrical rating basis 350 V V_d plus margin TBD (H1F-AN-10);
- B(z): no Vyovrinda-specific B(z) evidence exists yet (H1F-BZ-01: no FEMM of MC-1, no measured map); the P5 field
  profile is a reference for P5 only.

No thrust, specific impulse, efficiency or discharge current is stated for H-1: no transport closure is admitted
(AG-02 EMPTY) and the measured H-1 thrust / feed map (A9.21 item 11) does not exist yet.

## 4. Electron source / neutralizer: downstream RF-ICP

- 13.56 MHz RF ICP electron source downstream of the Hall exit (A9 decision). RF matching:
  LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT; RF component ratings TBD_AFTER_IMPEDANCE_MAP; ICP RF power closure
  PENDING_HARDWARE; ICP electron-current capacity PENDING_ICP45 (A9.2 statuses,
  `docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json` `#/a9_2_statuses`).
- ICP-45 capacity is defined discharge-OFF as I_e,cap = I_on - I_off (signed) and stays NOT_EVALUATED until
  I_d,max,H1 is registered on H-1 (AG-04; RVM-15).
- ICP gas feed: primary mode G-REUSE (no dedicated ICP Xe feed, m_Xe,ICP = 0 booked); G-XE is a declared variant
  (`docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json` `#/propellant_policy`; *owner-allocation*).
- Bench programme: P1 ICP bench (`docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json`,
  ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING) and P2 impedance map (`docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json`,
  PREPARATION_ONLY_NOT_RUN).
- Mandatory **ICP go / no-go gate GNG-ICP-01 before LOCK-1** (owner decision A9.21 item 4): existence and placement
  approved; fail-closed (missing evidence -> NOT_EVALUATED, never GO); **no criterion is approved**. Status at bbc480c:
  NOT_EVALUATED, criteria PENDING_OWNER_ACCEPTANCE (`#/pre_lock1_gates[id=GNG-ICP-01]`).

## 5. Propellant handling (RFP-P18-08, RFP-P17-03..05)

- **Ambient-air path (primary):** intake -> filter -> compressor -> gas chamber / plenum -> metering valve -> H-1. The
  intake is sized statewise from air density as a function of solar activity and altitude on the frozen NRLMSIS 2.1
  dataset (`abep_sim/data/atmosphere_msis21_v1.json`, a model input, not compliance evidence) and its orbit-resolved
  design states (`abep_sim/data/atmosphere_msis21_orbit_v1_design_states.json`).
- **Upstream status at bbc480c (model-derived, PARAMETRIC_SENSITIVITY inputs):** the coupled upstream screen F7 finds a
  nominal all-state delivered-flow frontier of 0.0983 mg/s, and no Pareto member reaches the lower end (0.38 mg/s) of
  the characterization coverage at every state (`docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json`
  `#/findings[id=F78-02]`). These are five-state screening results. **Post-freeze caveat (owner decision point; see
  `04_RISK_REGISTER.md` R-03):** the package does not claim robust upstream (intake / compressor / feed) closure.
- **Xe path (contingency / emergency):** separate Xe tank, regulator, valves, plumbing -> H-1 (and the ICP only in the
  declared G-XE variant). AL-08 = 6.05 kg is kept only as a provisional planning floor until quotations split tank,
  regulator, valves, plumbing, mounting / thermal and any C1-specific branch (A9.21 AL08; about 0.285 kg of C1 branch
  hardware may be inside the analog figure). No mission Xe load is frozen
  (`docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json` `#/status`).
- **Atomic oxygen:** O2-bearing ground tests are labelled NO_ATOMIC_O; atomic-O effects are addressed only through the
  separate AO life programme (A9 evidence order). The O / O2 electron-impact chemistry v0 tables are DRAFT and unused
  (`docs/chemistry/o_o2/v0/channel_status_v0.json` `#/status`).

## 6. Power processing from the bus (< 1.5 kW, RFP-P18-01 / -10)

Boundary and gate (`docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json`, PRELIMINARY_DRAFT_FOR_OWNER):

- P_bus is all electrical power crossing the spacecraft-side DC boundary. RFP gate: **P_bus,1ms,max < 1500 W**, steady
  and every start-up step, measured with synchronized channels (>= 100 kSa/s, >= 20 kHz bandwidth) (`#/gates_and_allocations`;
  definition FROZEN_A9_ENGINEERING_DEFINITION).
- Owner allocations (not gates, not evidence): 1350 W internal design allocation; 300 W common allocation incl. 50 W
  controls / thermal; 1300 W context level only (*owner-allocation*).
- Load slots of the flight configuration: Hall discharge; inner / outer / trim magnet supplies; 13.56 MHz RF generator
  DC input; matching-network actuators; ICP collector / bias; atmospheric and Xe valve drivers; compressor drive;
  thermal control; housekeeping / controls; reserved DC port (`#/slots`). Every load value is TBD; the ledger is
  PARTIAL_BOUNDARY (compressor load TBD) and the gate is NOT_EVALUABLE (AG-10).
- Bus architecture: configurable spacecraft-input front end (input voltage TBD, A902-12) feeding a regulated 100 V
  internal propulsion bus (`#/bus_architecture`; *owner-allocation*).
- PPU topology options (analogs, `docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json`, PRELIMINARY_DRAFT_FOR_OWNER):
  discharge supply class LCC resonant converter (NASA SSEP sub-kW breadboard analog) or ZVS full-bridge (1 kW string PPU
  analog); separate current-controlled per-coil magnet supplies; start-up / stop / failure-recovery sequencer in the PPU
  controller. H2-4 predates A9.19: its cathode heater / keeper supplies now apply only to the ground C1 reference. A
  mains-powered laboratory RF generator is GROUND/FACILITY_ONLY and never flight P_bus evidence (RVM-04).

## 7. Redundancy and single-point failure (RFP-P18-02, RFP-P18-09)

The requirement is accepted. **No redundancy design and no FMEA exist at bbc480c** (RVM-19 NOT_EVALUATED: "FMEA /
failure-tree analysis of the selected electronics (none selected)"). The architecture failure trees
(`docs/architecture_comparison/failure_tree/failure_trees_v1.json`) are architecture-comparison work, not an electronics
FMEA. Proposed approach for the owner to confirm (OIR-TEC-02):

1. electronics FMEA and single-point-failure list at PDR-1 (Milestone 1), against the PPU block diagram;
2. redundancy concept (which units are redundant, cold or hot, cross-strapping of the sensors) decided by the owner
   with its mass and power cost booked, because mass closure is already DOES_NOT_CLOSE at the MEV planning level (§9);
3. FDIR in the PSE software at PDR-2 (Milestone 2, RFP-P20-05).

## 8. Electrical / data interface: MIL-STD-1553B (RFP-P18-12)

Offered: a MIL-STD-1553B remote terminal on the propulsion controller for configuration and high-rate data logging with
the satellite onboard computer and data recorder, discrete lines for thruster operation, and the hardware drivers inside
the propulsion system. **No interface design, ICD or test artifact exists in the repository** (RVM-20). Verification
path (RVM-20): ICD (inspection), 1553B configuration / data-logging test on a representative bus, discrete-line
operation demonstration. The RT implementation (core / transceiver source, use of the standard's dual A/B bus) is an
owner choice (OIR-TEC-06). The interface ICD is planned as a PDR-2 input.

## 9. Mass (< 40 kg, RFP-P18-11) - disclosed open item

Read as < 40 kg **wet** (owner's conservative reading; DISC-02 recorded for DRDO clarification). The single governing
MEV-level planning roll-up (`docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json` `#/flight_rollup_vs_40kg`): nominal
33.96 kg + 20 % system margin = **dry known 40.75 kg** (AL-09 controls has no value and is excluded), wet known 42.75 /
45.75 / 50.75 kg at 2 / 5 / 10 kg loaded Xe: **DOES_NOT_CLOSE** in all three cases. These are owner allocations and
owner-stated MEV planning floors (1.20 x analog floors), not CBEs and not measurements. The margin reading is not relaxed
(MQ-10): closure requires redesign, integration or lighter qualified parts. AG-11 is INCOMPLETE_EVIDENCE.

## 10. Thermal, materials, life

- Thermal: ICP_COUPLED_THERMAL UNRESOLVED and ANODE_THERMAL_CLOSURE UNRESOLVED; no heat term evaluated on evidenced
  inputs; never reported as a thermal pass (`docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json`;
  RVM-17). Owner allocation: steady heat into the spacecraft mount <= 50 W (RVM-27; *owner-allocation*, provisional).
- Materials: final anode material OPEN; every P4 screen INCOMPLETE_EVIDENCE
  (`docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json`).
- Life: design basis >= 26,280 h mission and > 15,000 h cumulative energized operation (RVM-12, -13; *assumed* design
  basis from RFP-P19-01). No admissible life analysis exists (needs an admitted Hall closure or measured wear); AO /
  lifetime register v5 defines the wear / endurance segments (`docs/experiments/lifetime_ao/ao_lifetime_register_v5.json`).

## 11. What this approach does not claim

- no thrust, Isp, efficiency, power or life value for the proposed system;
- no PASS / GO for any gate; GNG-ICP-01, AG-12, AG-13 and ICP-45 are NOT_EVALUATED;
- no frozen architecture or design point; no CBE mass;
- no robust upstream closure (post-freeze caveat);
- nothing about RFP pages 1-15 and 34-40 (not screened by the repository).
