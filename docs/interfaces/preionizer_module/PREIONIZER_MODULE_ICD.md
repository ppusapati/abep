# H-1 common Pre-Ionizer Module ICD (`preionizer_module_icd_v1`)

| item | value |
|---|---|
| follow-on / trigger | `fo_preionizer_module_icd` / `T_A5_PREIONIZER_ICD` (owner addendum A6, lane H1-ICD) |
| status | DRAFT_PENDING_OWNER |
| machine-readable | `schemas/interfaces/preionizer_module_icd_v1.json` (JSON Schema for occupant declarations + `x-preionizer-module-icd`) |
| builder | `docs/interfaces/preionizer_module/build_preionizer_module_icd.py` (`--check` verifies both files) |
| test | `tests/test_preionizer_module_icd.py` |
| base commit | `302e1c94b3bddeb005f17bb189407f2e4641519a` |
| A5 | `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json` sha256 `0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621` |
| A6 | `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json` sha256 `aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180` |
| G0 baseline | `docs/decisions/verification/A5_BASELINE_VERIFICATION.json` sha256 `4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523`: verdict **CLEAN** at `23b79c843528656f21333fd44bdf02c2e9e3e3b8` (pytest 1617 passed, 5 skipped, 1 xfailed; golden OK; ci_checks 10/10 passed (parse, prereg_lock, audit_manifest, hallthruster_pin, rate_validity_coverage, variant_configs, p5_n2_cases, launch_manifests, multiply_charged_tables, ensemble_gate)) |

Interface definition for owner review. Nothing here is approved, pre-registered, procured or frozen; every threshold not in the RFP is PROPOSED; every numeric value is copied from a repository deliverable with its evidence class, or is TBD.

## Standing facts

* **bundle1**: NO_BASELINE_YET (docs/milestones/bundle1/bundle1_v5.json; A6 not_authorized: changing Bundle 1)
* **credible_hall_set**: EMPTY (A4 project_conclusion; no Hall closure admitted)
* **a5_numbers**: A5 numbers are ALLOCATIONS or REQUIREMENTS, never predictions
* **no_winner**: No architecture is ranked, preferred on performance or eliminated here; H-1 Phase 1 decides among A hall_only / B rf_hall / C ecr_hall / NO_VIABLE_CASE.
* **execution_order**: A5's per-point order names the configurations; the score-bearing order is order-balanced (A6 clarification_execution_order).

Architecture ids: `hall_only`, `rf_hall`, `ecr_hall`. Phase-1 outcomes: A hall_only / B rf_hall / C ecr_hall / NO_VIABLE_CASE.

## 1. Module slot and A5 reserved interface

* **IP-UP**: module inlet plane: end of the common feed line (after the mixing point and the gas isolator); fixed in the thrust-stand frame
* **IP-DN**: module outlet plane = H-1 rear inlet flange, immediately upstream of HALL_INLET_Z0; everything downstream is H-1 and identical in every configuration
* **HALL_INLET_Z0**: anode/gas-distributor plane; the inlet state here is the only allowed physical difference between arms (a result, not a setting)

Occupants: `PIM-0` = hall_only (HW-0); `PIM-RF` = rf_hall (HW-RF); `PIM-ECR` = ecr_hall (HW-ECR).
Control states: `M0` = HW-0, hall_only reference; `M0b` = module installed, source unpowered (control state; never reported as hall_only); `M0c` = ECR module installed, microwaves off, ECR electromagnet on (only with an electromagnet).

A5 reserves the **RF pre-ionization module interface** (between feed/plenum and Hall ionization region): "a defined electrical, mechanical, gas and control ICD is produced now so that fitting RF after H-1 does not require redesigning the thruster". The A5 location is the slot IP-UP..IP-DN of the H-1 test article (W3 hardware definition). The flight-relevant parts of this ICD are the IP-DN flange/datum on H-1 (PMI-01), the gas path and pressure boundary (PMI-02), the bus_power_boundary_v1 slots (PMI-03) and the control lines (PMI-04); the stand-related items (PMI-08, PMI-11) are ground-test items. A flight ICD is Milestone C work.

## 2. Common interface items (PMI-01 .. PMI-11)

Every common item is written occupant-agnostically and carries a satisfiability entry for PIM-RF, PIM-ECR (incl. its magnet and microwave feed) and PIM-0; none is NOT_SATISFIABLE. Anything only one module can meet is an annex item.

| id | boundary | PIM-RF | PIM-ECR | PIM-0 |
|---|---|---|---|---|
| PMI-01 | Mechanical envelope and mounting datum | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-02 | Gas-flow path and pressure boundary | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-03 | Electrical power boundary (bus_power_boundary_v1) | BY_DESIGN | BY_DESIGN | TRIVIAL |
| PMI-04 | Control, enable and interlock lines | BY_DESIGN | BY_DESIGN | TRIVIAL |
| PMI-05 | Thermal rejection interface | BY_DESIGN | BY_DESIGN | TRIVIAL |
| PMI-06 | Grounding and shielding | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-07 | Diagnostics | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-08 | Service-line routing | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-09 | Permitted magnetic-field disturbance at the Hall channel | BY_DESIGN | IN_PRINCIPLE_OPEN_DESIGN_RISK | TRIVIAL |
| PMI-10 | Allowable pressure drop (pressure-drop class) | BY_DESIGN | BY_DESIGN | BY_DESIGN |
| PMI-11 | Installation/removal reproducibility | BY_DESIGN | BY_DESIGN | BY_DESIGN |

### PMI-01 Mechanical envelope and mounting datum (`mechanical_envelope_and_mounting_datum`)

**Definition.** The module slot is the volume between IP-UP (module inlet plane: end of the common feed line, after the single mixing point and the gas isolator, fixed in the thrust-stand frame) and IP-DN (module outlet plane = the H-1 rear inlet flange, immediately upstream of the anode/gas-distributor plane HALL_INLET_Z0). The mounting datum is the IP-DN flange face with its alignment features on H-1: module z axis = H-1 thrust axis, registered to the drawing with z = 0 at the anode face (the B(z) registration of HW-MC-03). Every occupant uses the same flange pattern, alignment features, seals and torque specification at IP-UP and IP-DN; no occupant part protrudes downstream of IP-DN.

**Common requirement.** The common envelope (length, maximum diameter, keep-out zones for the B(z) probe path, the witness holder and the service-line bundle) is sized to the LARGEST occupant, including the ECR resonance magnet with its yoke and the microwave feed/coupling structure, and the RF coil, Faraday shield and any on-module matching network. The envelope is therefore never RF-sized. Module mass and centre of gravity are recorded per occupant serial.

**Units.** m, kg, N m

**Values.**

* `interface_dimensions` [m]: **TBD** (the H-1 rear-flange design and the module designs (IP-UP/IP-DN flange, alignment features, seal grooves); closes at: procurement: H-1 rear-flange and module interface control drawing released before HRR (HWQ-15: interfaces frozen before Phase 1))
* `envelope_length_max` [m]: **TBD** (the ECR and RF module designs (largest occupant incl. ECR magnet/yoke and microwave coupling structure); closes at: procurement: module design release (RF and ECR), before HRR)
* `envelope_diameter_max` [m]: **TBD** (the ECR and RF module designs (largest occupant); closes at: procurement: module design release (RF and ECR), before HRR)
* `module_mass_max` [kg]: **TBD** (the W4 thrust-stand load capacity and the module designs; closes at: procurement: thrust-stand selection (W4) and module design release; checked at HRR)
* `flange_torque_spec` [N m]: **TBD** (the flange and seal selection; closes at: procurement: interface control drawing, before HRR)

**Satisfiability.**

* PIM-RF: BY_DESIGN - RF source, interstage and Faraday shield fit inside the ECR-sized envelope; same flanges and alignment features.
* PIM-ECR: BY_DESIGN - the envelope is sized to the ECR module including magnet/yoke and microwave feed; same flanges and alignment features.
* PIM-0: BY_DESIGN - replicates the module mechanical envelope and gas path with no source hardware and no magnet (HW-PIM-02); same flanges and alignment features.

**Verification.** inspection; torque and alignment record at every configuration change (HRR; every configuration change). Traces to: HW-PIM-01; HW-PIM-02; HW-H1-06; lane 17 INV-G3; A5 architecture.reserved_interface (location between feed/plenum and Hall ionization region).

### PMI-02 Gas-flow path and pressure boundary (`gas_flow_path_and_pressure_boundary`)

**Definition.** The module gas path runs from IP-UP to IP-DN, i.e. between the feed/plenum (FS-C manifold and line) and the Hall ionization region (H-1 distributor at HALL_INLET_Z0), the location A5 reserves for the pre-ionizer interface. All anode gas (Xe at start, then N2 or N2/O2) enters at IP-UP and leaves at IP-DN; in HW-RF and HW-ECR it therefore passes the source (HW-FS-02). The interstage duct belongs to the module. The C-1 cathode gas line never passes the module.

**Common requirement.** (a) No occupant has a gas inlet or outlet other than IP-UP, IP-DN and the declared source-chamber pressure port (PMI-07); any split of the IP-UP flow inside a module (e.g. injection into an ECR resonance zone) is internal to the module. (b) The module wetted volume is a sealed pressure boundary to the facility vacuum at both flanges and at every penetration (RF window/feedthrough, microwave window/feedthrough, probe and OES ports). (c) Every wetted part is oxygen-compatible and cleaned for O2 service. (d) The wetted volume and internal surface area of each occupant are recorded (transients, residence time, surface interaction), never equalised by adjustment.

**Units.** Pa m^3 s^-1, Pa, m^3, m^2

**Values.**

* `leak_rate_max` [Pa m^3 s^-1]: **TBD** (the leak-check method and the smallest grid flow (W1, W4); closes at: S1a leak check and cold-flow test, every configuration)
* `P_feed_range` [Pa]: **TBD** (the W1 test points (fo_feed_state_closure); closes at: S1a cold flow (released ground-qualification feed points, S1A-C3))
* `wetted_volume_per_occupant` [m^3]: **TBD** (the RF, ECR and PIM-0 module designs; closes at: procurement: module design release; recorded at HRR)
* `o2_cleaning_standard` [-]: **TBD** (the facility safety case (owner channel); closes at: HRR)

**Satisfiability.**

* PIM-RF: BY_DESIGN - dielectric discharge tube is part of the sealed wetted volume; RF feedthrough outside the gas path.
* PIM-ECR: BY_DESIGN - microwave window/feedthrough is a sealed penetration; any resonance-zone injection is an internal split of the IP-UP flow.
* PIM-0: BY_DESIGN - flow-equivalent duct with the same ports (HW-PIM-02, HW-FS-04).

**Verification.** inspection + leak check + cold-flow manifold pressure (HRR; S1a; every configuration change). Traces to: HW-FS-02; HW-FS-04; HW-FS-05; HW-FS-07; HW-ENV-04; lane 17 INV-F1; ICD IF-A5 (p_feed_Pa, pressure_loss_Pa gap); A5 architecture.reserved_interface.

### PMI-03 Electrical power boundary (bus_power_boundary_v1) (`electrical_power_boundary`)

**Definition.** Every electrical load of an occupant is supplied from the common spacecraft-side DC bus boundary through exactly the pre-ionizer components that bus_power_boundary_v1 assigns to its architecture (abep_sim/arch_boundary.py PREIONIZER_COMPONENTS): rf_hall -> rf_source (net RF power at the coil/antenna feed terminals); ecr_hall -> ecr_source (net microwave power at the coupling-structure input) and ecr_magnet (resonance-coil terminals; a permanent magnet is passed explicitly as 0 W with efficiency 1); hall_only -> none. Module power therefore always lands in P_bus (P_bus = load / ledger efficiency, summed by arch_boundary.bus_power_ledger with its conservation gate).

**Common requirement.** (a) No module load is booked under a common component or omitted. (b) A module load with no v1 slot (an RF assist magnet, a powered interstage electrode or bias, an active coolant pump) is NOT permitted under v1 until the owner and the bus-boundary lane define a slot in a new boundary version (see annex deviations DEV-RF-01, DEV-RF-03). (c) The module's source power is never assessed separately from P_bus (A5 discriminator_note).

**Bus components.** `hall_only`: (none); `rf_hall`: rf_source; `ecr_hall`: ecr_source, ecr_magnet

**Units.** W, -

**Values.**

* `P_bus_requirement_max` = 1500 W (RFP, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/rfp_basis/power_max_W`)
* `P_bus_design_allocation` = [1300, 1350] W (ALLOCATION, assumed; `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json#/allocations_and_requirements/2`)
* `P_hi_source` [W]: **TBD** (the source allocation in bus_power_boundary_v1 (owner, lane 11); closes at: LOCK-1 (source allocation); bench stage S3)
* `ledger_efficiency_per_preionizer_component` [-]: **TBD** (the LOCK-1 ledger efficiencies of rf_source, ecr_source and ecr_magnet (DC-fed generator input metered as evidence, HW-PIM-12); closes at: LOCK-1)

**Satisfiability.**

* PIM-RF: BY_DESIGN - one slot rf_source; DC-fed RF generator off-module, net power at the load plane.
* PIM-ECR: BY_DESIGN - slots ecr_source and ecr_magnet (0 W / efficiency 1 if permanent).
* PIM-0: TRIVIAL - empty component set; no electrical load exists to book.

**Verification.** INS-02 per component channel; INS-03 net RF/microwave power at the load plane; ledger via arch_boundary.bus_power_ledger (S1a (channel and load-plane calibration); every reading). Traces to: abep_sim/arch_boundary.py PREIONIZER_COMPONENTS, COMPONENT_DEFINITIONS; docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md; HW-PIM-05; HW-PIM-08; HW-PIM-12; INS-02; INS-03; lane 17 INV-P1.

### PMI-04 Control, enable and interlock lines (`control_enable_interlock_lines`)

**Definition.** A common harness with the same connector, pin-out and routing on every occupant carries: L1 MODULE_ID (identity/serial code of the installed occupant, logged with every reading); L2 SOURCE_ENABLE (controller permit to the occupant's off-module generator chain); L3 INTERLOCK_LOOP (hard-wired series loop through the occupant); L4 PREIONIZER_LIT (status for the state-machine guard preionizer_lit); L5 PREIONIZER_FAULT (status for the health guard preionizer_fault).

**Common requirement.** (a) The interlock loop is opened by each A4 S1a minimum interlock that applies at the module (hardware E-stop; vacuum/background-pressure abort; loss-of-pumping/cooling abort; magnet overcurrent/overtemperature, which includes an ECR electromagnet; gas/oxidizer-state interlock; DAQ fault indication; explicit Hall-discharge inhibit during S1a). Interlock limits come from real hardware/facility ratings, never invented thresholds (A4). (b) Sequencing follows schemas/controls/dual_feed_state_machine_v1.json: the pre-ionizer comes up on Xe before any atmosphere (PREIONIZER_SEED / PREIONIZER_IGNITION), a pre-ionizer loss reverts to XE_FALLBACK, CONTROLLED_SHUTDOWN removes pre-ionizer power first, retries are counter-bounded (n_preion_retry_max). (c) Source-type-specific trips (RF reflected power, microwave reflected power/arc) are annex items feeding the same L3/L5 lines.

**Units.** -

**Values.**

* `interlock_limits` [-]: **TBD** (real hardware/facility ratings of the installed units (A4 S1a_interlock_limits); closes at: S1A-C2 (safe operational limits owner-approved) and S1-C8)
* `n_preion_retry_max` [-]: **TBD** (owner FDIR policy and the pre-ionizer ignition test (controls lane parameter); closes at: S1b/S2 pre-ionizer ignition tests; owner FDIR decision)
* `preionizer_lit_detection_method` [-]: **TBD** (a pre-ionizer plasma-detection method from source design and test (docs/evidence/rf_source/, docs/evidence/ecr_source/); closes at: procurement: module design; demonstrated at bench stage S3)

**Satisfiability.**

* PIM-RF: BY_DESIGN - L1-L5 wired; RF reflected-power trip feeds L3/L5 (annex PMR-06).
* PIM-ECR: BY_DESIGN - L1-L5 wired; ECR electromagnet overcurrent/overtemperature and microwave trips feed L3/L5 (annex PME-06).
* PIM-0: TRIVIAL - L1 reports PIM-0; L2 terminated (no effect); L3 closed by a jumper so the loop topology is identical; L4/L5 report constant not-lit / no-fault.

**Verification.** inspection + interlock functional test (each input opens the loop) (S1a (before power is applied, S1A-C2); every configuration change (L1 record)). Traces to: A4 decisions.S1a_minimum_interlocks, S1a_interlock_limits; docs/controls/DUAL_FEED_STATES.md; schemas/controls/dual_feed_state_machine_v1.json; S1A-C2; S1-C8.

### PMI-05 Thermal rejection interface (`thermal_rejection_interface`)

**Definition.** Each occupant rejects its own waste heat through a declared module thermal path (radiation to the facility and/or conduction to a module-own sink on the stand frame), never through H-1 by an unrecorded path. The IP-DN conductive path is either thermally isolated by design or instrumented (HW-PIM-09), with the same isolator hardware in every occupant.

**Common requirement.** (a) Module thermocouples at fixed recorded positions (IP-DN flange, module body; source structure and ECR magnet where present), identical positions on PIM-0; anode temperature logged in every arm (HW-H1-07); thermal settling T-SETTLE before every reading. (b) Module waste heat, magnet heating and any resulting anode-temperature difference are arm consequences: recorded and reported with R_arch, never equalised (hardware identity_matrix may_differ). (c) Active liquid cooling is not a common provision (annex deviation DEV-RF-03).

**Units.** W K^-1, s, degC

**Values.**

* `module_to_H1_thermal_conductance_max` [W K^-1]: **TBD** (the module and H-1 thermal designs (lane 15 thermal_life inputs); closes at: design analysis before HRR; checked S1a/S3)
* `T_SETTLE` [s]: **TBD** (the S1 thermal time constants (lane 25 T-SETTLE); closes at: S1b)
* `module_structure_temperature_max` [degC]: **TBD** (the selected module materials and the thermal_life limit records; closes at: procurement: module design release)

**Satisfiability.**

* PIM-RF: BY_DESIGN - coil/tube/shield heat rejected by the module path; flange instrumented.
* PIM-ECR: BY_DESIGN - coupling-structure and magnet heat rejected by the module path; magnet temperature measured (HW-PIM-15).
* PIM-0: TRIVIAL - no dissipation; carries the same isolator hardware and thermocouple positions.

**Verification.** analysis + test (design; S1a; S3). Traces to: HW-PIM-09; HW-H1-07; HW-PIM-15; abep_sim/thermal_life.py THERMAL_COMPONENTS; hardware identity_matrix.may_differ.

### PMI-06 Grounding and shielding (`grounding_and_shielding`)

**Definition.** The module body and any interstage electrode sit at ONE declared potential (floating / anode / cathode common / facility ground: owner decision HWQ-07), identical for PIM-0 at IP-DN (HW-ELEC-02), through one declared bonding point on the module. The gas isolator (voltage break) is upstream of IP-UP, so every occupant sees the same gas-line potential (HW-FS-06).

**Common requirement.** (a) Any interstage current is measured, because it enters the cathode budget I_emit = I_d + I_keeper + I_interstage (lane 19). (b) RF and microwave returns are separated from the discharge return (HW-ELEC-03). (c) Source-specific electromagnetic containment (RF Faraday shield/screen, microwave leakage containment) lies inside the PMI-01 envelope and is an annex item. (d) Generator pickup on every common diagnostic is quantified with each generator on a matched dummy load at each pre-registered power, every pump-down (DUMMY_LOAD_PICKUP).

**Units.** V, A

**Values.**

* `module_potential` [V]: **TBD** (the module electrical design and an owner decision (HWQ-07); closes at: LOCK-1 input; verified S1a)
* `isolator_margin` [V]: **TBD** (the facility electrical safety case and the supply design; closes at: S1a (hipot))
* `ir_test_voltage` [V]: **TBD** (the MCQ-QT-08 procedure and an owner decision; closes at: baseline before S1)

**Satisfiability.**

* PIM-RF: BY_DESIGN - body and Faraday shield bonded at the declared point; RF return separate.
* PIM-ECR: BY_DESIGN - body, waveguide/coax outer and magnet frame bonded at the declared point; microwave return separate.
* PIM-0: BY_DESIGN - body at the same declared potential and bonding point; no generator.

**Verification.** inspection + test (S1a; every pump-down (dummy-load pickup)). Traces to: HW-ELEC-01; HW-ELEC-02; HW-ELEC-03; HW-ELEC-05; HW-FS-06; lane 06 DUMMY_LOAD_PICKUP; lane 19 electron_current_budget.

### PMI-07 Diagnostics (`diagnostics`)

**Definition.** Common diagnostic provisions at identical positions on every occupant: (a) source-chamber pressure port (blanked or connected identically on PIM-0, HW-FS-04); (b) source-exit ion-collector access for I_src (INS-15 source-exit collector, HW-PIM-07), present on PIM-0 to confirm zero I_src; (c) optional OES view port (INS-12): if any occupant has one, all carry it (blanked where unused); (d) module thermocouples (PMI-05, INS-17); (e) the Hall-probe path for B(z) through the channel with any occupant installed (HW-H1-08, INS-09); (f) a load-plane source-power channel slot for the arm's pre-ionizer components (INS-03; empty in hall_only); (g) MODULE_ID in every DAQ record (PMI-04 L1); (h) the interstage-current channel (PMI-06).

**Common requirement.** Delivered current I_del is measured across the Hall channel exit with the discharge off (S3) and needs no module port. The load-plane source-power uncertainty must satisfy the lane 25 source-scale bound at the LOCK-1 source fraction f_src; frequency-specific sensors are annex items.

**Units.** Pa, A, relative (1 sigma)

**Values.**

* `u_src_scale` [relative]: **TBD** (the f_src allocation at LOCK-1 (package REQ-HW-03 gives u_src,max(f_src)); closes at: LOCK-1; calibrated S1a)
* `u_src_scale_max_at_f_src_0.1` = 0.035239475 relative (1 sigma) (SOURCED, model-derived; `docs/experiments/instrumentation/instrumentation_definition_v1.json#/instruments/2/required_uncertainty/source_scale_max/0.1`)
* `u_src_scale_max_at_f_src_0.2` = 0.017619738 relative (1 sigma) (SOURCED, model-derived; `docs/experiments/instrumentation/instrumentation_definition_v1.json#/instruments/2/required_uncertainty/source_scale_max/0.2`)
* `u_src_scale_max_at_f_src_0.3` = 0.011746492 relative (1 sigma) (SOURCED, model-derived; `docs/experiments/instrumentation/instrumentation_definition_v1.json#/instruments/2/required_uncertainty/source_scale_max/0.3`)
* `u_src_scale_max_at_f_src_0.4` = 0.0088098688 relative (1 sigma) (SOURCED, model-derived; `docs/experiments/instrumentation/instrumentation_definition_v1.json#/instruments/2/required_uncertainty/source_scale_max/0.4`)
* `I_src_collector_CEX_bound` [-]: **TBD** (a cited N2+ on N2 charge-exchange cross section (package REQ-HW-05); closes at: S1a probe calibration)

**Satisfiability.**

* PIM-RF: BY_DESIGN - ports (a)-(c) on the source chamber/interstage; INS-03 at the coil feed.
* PIM-ECR: BY_DESIGN - ports (a)-(c) on the source chamber/interstage; INS-03 at the coupling-structure input.
* PIM-0: BY_DESIGN - same ports at the same positions (blanked or connected identically); INS-03 slot empty (no component in hall_only).

**Verification.** inspection + calibration (HRR; S1a). Traces to: HW-FS-04; HW-PIM-07; HW-PIM-12; HW-H1-08; INS-03; INS-09; INS-12; INS-15; INS-17.

### PMI-08 Service-line routing (`service_line_routing`)

**Definition.** The service-line set crossing the thrust stand is the UNION of all occupants' lines and is present in every configuration (HW-SVC-01): RF coax; microwave feed (coax or waveguide, per the ECR frequency selection); ECR magnet DC lead pair; module thermocouple bundle; PMI-04 harness; source-chamber pressure line.

**Common requirement.** (a) Lines not used by the installed occupant are installed as shams with the same routing and fixation, terminated off-stand. (b) Routing is fixed relative to the stand; in-chamber cable/waveguide length is fixed per arm and characterised in S1a (HW-PIM-12). (c) End-to-end in-situ thrust-stand calibration after every configuration change. (d) A coolant pair enters the set only if an annex requires liquid cooling, and then as a sham in every other configuration (DEV-RF-03).

**Units.** calibrations, m

**Values.**

* `calibrations_before_min` = 10 calibrations (PROPOSED, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/requirements/75/values/calibrations_before_min`)
* `calibrations_after_min` = 10 calibrations (PROPOSED, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/requirements/75/values/calibrations_after_min`)
* `in_chamber_line_lengths` [m]: **TBD** (the RF and ECR chain designs and the facility layout; closes at: S1a (load-plane characterisation, M3))
* `stand_magnetic_parts` [-]: **TBD** (the W4 thrust-stand definition (fo_instrumentation_definition); closes at: S1a)

**Satisfiability.**

* PIM-RF: BY_DESIGN - RF coax live; microwave feed and ECR magnet leads as shams.
* PIM-ECR: BY_DESIGN - microwave feed and magnet leads live; RF coax as a sham.
* PIM-0: BY_DESIGN - all source lines as shams terminated off-stand; thermocouples and harness live.

**Verification.** inspection + in-situ calibration per configuration (S1a; S1b; every configuration change). Traces to: HW-SVC-01; HW-SVC-02; HW-SVC-05; HW-PIM-12; lane 06 SHAM_RF / SHAM_ECR; lane 25 G5.

### PMI-09 Permitted magnetic-field disturbance at the Hall channel (`permitted_magnetic_field_disturbance`)

**Definition.** Reference: the H-1 B-field definition is the HW-0 (PIM-0 installed) centreline B(z) over [0, domain_length] at the single pre-registered magnet_setting_schedule of MC-1 (lane 17 INV-B1, INV-B2), mapped per HW-MC-03 with coil currents, probe calibration, registration (z = 0 at the anode face) and sha256. With any occupant installed, in every control state (M0, M0b, and M0c where an ECR electromagnet allows it), the combined B(z) (MC-1 plus any module magnet fringe plus any change of the MC-1 working point) must equal the reference within the owner's INV-B3 tolerance epsilon_B.

**Common requirement.** (a) MC-1 is never modified between arms; a per-arm coil re-trim is only a separately pre-registered sensitivity condition. (b) Module structures are non-ferromagnetic; the only magnetic part of an occupant is its declared magnet (HW-PIM-03). (c) epsilon_B is admissible only if |S_B| * epsilon_B stays within the owner-assigned variance share, S_B = d ln(T/P_bus) / d ln B from the S1 coil-current scan (HW-MC-05). (d) An occupant outside the tolerance makes its arm non-comparable under this reference (INV-B3): recorded, never waived, never compensated inside the primary comparison.

**Units.** T, -, m

**Values.**

* `INV_B3_tolerance_epsilon_B` [-]: **TBD** (an owner decision (lane 17 Q5, HWQ-04) informed by the S1 sensitivity S_B; closes at: LOCK-1 (tolerance form) / LOCK-2 (value after S1b))
* `S_B` [-]: **TBD** (the S1 coil-current scan on HW-0; closes at: S1b)
* `module_to_channel_distance` [m]: **TBD** (the module and H-1 designs and a magnetostatic computation of the combined circuit; closes at: design (MCQ-QT-09) before HWQ-05; verified by S1a B(z) maps)
* `bz_uncertainty` [T]: **TBD** (the W4 instrumentation definition and the INV-B3 tolerance (HWQ-04); closes at: S1a)
* `B_hall_typical_xenon_database_context` = 200 G (SOURCED, inferred; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/B_hall_typical_xenon_database_G`)

**Satisfiability.**

* PIM-RF: BY_DESIGN - v1 is an unmagnetized ICP (HW-PIM-05, PROPOSED) with non-ferromagnetic structure; an assist magnet would move it to an open design risk (DEV-RF-01).
* PIM-ECR: IN_PRINCIPLE_OPEN_DESIGN_RISK - the resonance field is of order four times the xenon-database typical Hall field (annex PME-02), so the magnet fringe at the channel is a first-order design question; meetable by distance, magnet type and return yoke/shielding, to be shown by the MCQ-QT-09 analysis and S1a M0/M0b/M0c maps (DEV-ECR-01).
* PIM-0: TRIVIAL - no magnet, non-ferromagnetic (HW-PIM-02); defines the reference map.
* Why common: The item is a comparability condition on the Hall accelerator (lane 17 INV-B3) that every occupant must meet, not a design preference; it is written occupant-agnostically. PIM-0 and PIM-RF meet it trivially or by design; for PIM-ECR it is an open design risk whose outcome is measured, so the item does not structurally exclude the ECR branch.

**Verification.** magnetostatic analysis + B(z) maps per control state (design; S1a; before and after each configuration's block series). Traces to: lane 17 INV-B1, INV-B2, INV-B3; HW-MC-01; HW-MC-03; HW-MC-05; HW-PIM-03; HW-PIM-06; HW-MC-12; MCQ-QT-09.

### PMI-10 Allowable pressure drop (pressure-drop class) (`allowable_pressure_drop`)

**Definition.** Pressure drop of an occupant at flow m_dot and composition x_s: dp_occ(m_dot, x_s) = p_man(occ) - p_man(PIM-0) at the same MFC setpoints, cold (no plasma), where p_man is the capacitance-manometer pressure at the manifold upstream of IP-UP (HW-FS-04, INS-06). IP-DN has no port (it would change H-1). An occupant belongs to the common pressure-drop class if |dp_occ| <= dp_class at every grid flow.

**Common requirement.** (a) dp_occ is measured in S1a at every grid flow in every configuration and reported as part of R_install (lane 25 attribution split), never corrected (HW-FS-05). (b) Any conductance prediction uses the interstage-model rules: free-molecular (Santeler/Chiggiato) only for Kn > 0.5, otherwise an explicit sourced conductance (INTERSTAGE_MODEL section 4). (c) If an occupant falls outside the class, the control is a passive matched PIM-0 insert (DEV-H0-03) or reporting the difference; the MFC setpoints are never changed per arm.

**Units.** Pa

**Values.**

* `dp_class` [Pa]: **TBD** (the S1a cold-flow manifold-pressure repeatability of PIM-0 re-installation, the W1 registered P_feed tolerance per test point and an owner decision; closes at: S1a (measurement) -> LOCK-2 (value))
* `dp_occ_per_grid_flow` [Pa]: **TBD** (S1a cold-flow measurements at the released ground-qualification feed points (S1A-C3); closes at: S1a)
* `pressure_loss_IF_A5` [Pa]: **TBD** (a valve/line flow model (upstream ICD IF-A5 pressure_loss_Pa is a gap); closes at: outside this lane (upstream ICD))

**Satisfiability.**

* PIM-RF: BY_DESIGN - discharge-tube/interstage conductance chosen within the class, measured S1a.
* PIM-ECR: BY_DESIGN - coupling-structure/interstage conductance chosen within the class, measured S1a.
* PIM-0: BY_DESIGN - reference of the class; matched inserts if RF and ECR differ (DEV-H0-03).

**Verification.** cold-flow test (S1a; every configuration change). Traces to: HW-FS-04; HW-FS-05; INS-06; INTERSTAGE_MODEL.md section 4; lane 25 R_install; ICD IF-A5 pressure_loss_Pa.

### PMI-11 Installation/removal reproducibility (`installation_removal_reproducibility`)

**Definition.** Re-mount (installation) reproducibility u_inst of ln(T/P_bus) per installation, 1 sigma. Requirement: u_inst <= u_inst,max at the n fixed at LOCK-2 (HW-SVC-03, package REQ-HW-04), unless a no-vent switch (D-06-B) is adopted. PROPOSED hardware sub-allocation: five equal root-sum-square contributors (c1 stand calibration and zero shift, c2 thrust-axis alignment, c3 magnetic-circuit / B(z) change, c4 gas path, distributor and leak change, c5 service-line, thermal and electrical environment change).

**Common requirement.** How S1/S1b measures it (lane 25 s1_plan.S1b_hall_on): K re-mount cycles on HW-0 at OP3; each cycle vents, removes and re-installs the module slot occupant and mount exactly as a configuration change does, pumps down, runs the pre-registered conditioning and T-SETTLE, the in-situ calibration, then r readings; u_inst = sample SD of the K cycle means of ln(T/P_bus) with K - 1 degrees of freedom. The procedure replicated must be the adopted configuration-change procedure (HW-SVC-04, owner HWQ-01). Every exchange records: serials and part log, torque and alignment, leak check and cold-flow manifold pressure, B(z) map, in-situ calibration, dummy-load pickup, witness-set exchange (hardware verification_per_configuration_change).

**Units.** ln-ratio (1 sigma, per installation), deg, cycles (K), readings (r), -

**Values.**

* `u_inst_max_n4` = 0.0024918072 ln-ratio (1 sigma, per installation) (SOURCED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/u_inst_max_n4`)
* `u_inst_max_n6` = 0.0025595388 ln-ratio (1 sigma, per installation) (SOURCED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/u_inst_max_n6`)
* `u_inst_max_n8` = 0.0025886876 ln-ratio (1 sigma, per installation) (SOURCED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/u_inst_max_n8`)
* `n_installation_contributors` = 5 - (PROPOSED, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/n_installation_contributors`)
* `u_contributor_max_n4` = 0.001114370057 ln-ratio (1 sigma, per installation) (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/u_contributor_max_n4`)
* `theta_align_max_n4_deg` = 2.70440471 deg (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/theta_align_max_n4_deg`)
* `u_contributor_max_n6` = 0.00114466055 ln-ratio (1 sigma, per installation) (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/u_contributor_max_n6`)
* `theta_align_max_n6_deg` = 2.740899625 deg (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/theta_align_max_n6_deg`)
* `u_contributor_max_n8` = 0.001157696289 ln-ratio (1 sigma, per installation) (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/u_contributor_max_n8`)
* `theta_align_max_n8_deg` = 2.756456548 deg (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/theta_align_max_n8_deg`)
* `K_remount_cycles` = 6 cycles (K) (PROPOSED, assumed; `docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json#/thresholds/17`)
* `r_readings_per_cycle` = 3 readings (r) (PROPOSED, assumed; `docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json#/thresholds/18`)
* `u_inst_achieved` [ln-ratio (1 sigma, per installation)]: **TBD** (the S1b re-mount series on the delivered hardware; closes at: S1b -> LOCK-2)

**Satisfiability.**

* PIM-RF: BY_DESIGN - same flanges, alignment features and torque spec; exchange reproducibility not directly measured by the HW-0 S1b series (DEV-RF-05).
* PIM-ECR: BY_DESIGN - same flanges, alignment features and torque spec; magnet adds c3 exposure; not directly measured by S1b (DEV-ECR-07).
* PIM-0: BY_DESIGN - the S1b series measures exactly this occupant's exchange.

**Verification.** test (re-mount series) + per-exchange records (S1b (K re-mounts); S6 check; every configuration change). Traces to: HW-SVC-03; HW-SVC-04; package REQ-HW-04, D-01, D-06; lane 25 s1_plan.S1b_hall_on; lane 25 section 6.4 (G5); A6 fo_phase1_prereg_framework (S1/S1b establish remount reproducibility).

## 3. Annexes

### ANNEX-RF: `PIM-RF` (rf_hall), role PRIMARY_CONTINGENCY

Role basis: A5 architecture.reserved_interface ('RF pre-ionization module interface', baseline_flight_hardware false) and decision_statement ('RF pre-ionization is retained as an interface-ready Phase-1 contingency'); A6 fo_preionizer_module_icd ('RF stays the preferred contingency').

Scope: RF source + interstage between IP-UP and IP-DN; off-module chain: DC-fed RF generator, matching network, directional coupler at the load plane (hardware configuration item PIM-RF).

Uses common items: PMI-01, PMI-02, PMI-03, PMI-04, PMI-05, PMI-06, PMI-07, PMI-08, PMI-09, PMI-10, PMI-11.

Module-specific items:

* **PMR-01 RF frequency.** Not selected. Feedthrough, coax, matching network and sensors follow the selection.
  * `f_rf` [Hz]: **TBD** (the RF module design (owner); closes at: procurement: RF module design decision)
  * `f_rf_evidence_IPG6S` = 4 MHz (SOURCED, measured; `docs/evidence/rf_source/rf_evidence_matrix.json#/entries/0`)
  * `f_rf_evidence_IPT` = 40.68 MHz (SOURCED, measured; `docs/evidence/rf_source/rf_evidence_matrix.json#/entries/19`)
* **PMR-02 rf_source load plane and chain.** Net RF power (forward minus reflected) at the coil/antenna feed terminals (bus_power_boundary_v1 rf_source). DC-fed generator preferred so its DC input is metered as efficiency evidence; coupler at the load plane or upstream with the matching-network and cable loss characterised in S1a (evidence class 'reconstructed'). Matching-network location (on- or off-module) is a design choice that changes module mass and heat (DEV-RF-06).
  * `reflected_fraction_evidence_auto_matched_ICP` = {"max": 0.01} fraction (SOURCED, measured; `docs/evidence/rf_source/rf_evidence_matrix.json#/entries/50`)
  * `reflected_fraction_evidence_unmatched_IPT` = 0.2512 fraction (SOURCED, inferred; `docs/evidence/rf_source/rf_evidence_matrix.json#/entries/25`)
* **PMR-03 RF source power range.** Operable from P_lo to P_hi at the W1 grid flows on Xe (start) and the working gases; P_lo = max(lowest stable, 0.5 P_hi) (lane 25 T-PLO-FRACTION, PROPOSED).
  * `P_hi_rf` [W]: **TBD** (the source allocation in bus_power_boundary_v1 (owner, lane 11); closes at: LOCK-1; bench stage S3)
* **PMR-04 RF assist magnet.** PROPOSED: PIM-RF v1 is an unmagnetized ICP (HW-PIM-05). Published air-species RF sources used an applied field to ignite at low flow; bus_power_boundary_v1 has no slot for an RF assist magnet (DEV-RF-01).
  * `B_rf_ignition_assist_evidence` = 0.005 T (SOURCED, measured; `docs/experiments/hardware/hardware_requirements_v1.json#/requirements/58/values/B_rf_ignition_assist_T`)
* **PMR-05 Plasma-facing materials.** Dielectric tube, antenna and Faraday shield O2-compatible; no accessed source measures their erosion, sputtering or contamination (HW-PIM-10).
  * `module_materials_rf` [-]: **TBD** (the RF module design and cited O2-compatibility evidence; closes at: procurement: RF module design; inspection at HRR and after the block series)
* **PMR-06 RF-specific trips.** Reflected-power trip (and generator fault) feeding PMI-04 L3/L5.
  * `rf_reflected_power_trip` [W]: **TBD** (the selected generator's rating (A4: limits from real hardware ratings); closes at: S1A-C2)
* **PMR-07 RF containment.** Faraday shield/screen inside the PMI-01 envelope, bonded at the PMI-06 point.
* **PMR-08 Cooling.** PROPOSED: passive/radiative module cooling within PMI-05. Evidence: the IPG6-S laboratory source had coil, quartz tube, injector and oscillator all water-cooled (RF-IPG6S-09, measured, qualitative); downscaling with passive cooling was named its biggest challenge. If liquid cooling is needed, DEV-RF-03 applies.

| deviation | common items | deviation | confound risk | proposed control |
|---|---|---|---|---|
| DEV-RF-01 | PMI-03, PMI-09 | an RF assist magnet has no bus_power_boundary_v1 slot and adds a field disturbance | unbooked power (P_bus understated) and a B(z) change attributed to the ionization method | v1 unmagnetized (HW-PIM-05); if the owner adopts a magnet, a booking slot in a new boundary version before LOCK-1 (HWQ-06) and M0/M0b(/M0c) B(z) maps under PMI-09 |
| DEV-RF-02 | PMI-06 | Faraday shield or interstage electrode potential and any interstage current | cathode current budget and plasma potential differ between arms | declared potential identical to PIM-0 (HW-ELEC-02); I_interstage measured every reading |
| DEV-RF-03 | PMI-05, PMI-08, PMI-03 | liquid cooling would add coolant lines on the stand and possibly a pump load | coolant-line stiffness and flow-induced forces change stand tare/drift; pump power without a v1 slot | prefer passive cooling; if unavoidable, a coolant pair in every configuration with the same flow through a bypass at the slot for PIM-0/PIM-ECR (PROPOSED), and a booking slot defined before LOCK-1 |
| DEV-RF-04 | PMI-07 | RF pickup on common diagnostics | biased I_d, thrust-stand or probe readings in rf_hall only | DUMMY_LOAD_PICKUP at every pre-registered power, every pump-down (HW-ELEC-03) |
| DEV-RF-05 | PMI-11 | the S1b re-mount series measures the PIM-0 exchange only | an RF-module-specific installation term not covered by u_inst | PROPOSED S1a no-plasma module-exchange series with PIM-RF unpowered (cold-flow manifold pressure, in-situ calibration zero/tare, B(z)); no held-out H-1 observable exposed (S1A-FW) |
| DEV-RF-06 | PMI-01, PMI-05 | an on-module matching network adds mass and heat | stand load and thermal drift | mass/CG recorded; per-configuration in-situ calibration (HW-SVC-02); heat recorded (PMI-05) |

### ANNEX-ECR: `PIM-ECR` (ecr_hall), role ALTERNATE

**ALTERNATE - NOT AN EQUAL PROPOSAL BASELINE.** This annex does NOT make ECR an equal proposal baseline. Per A5, ECR pre-ionization is an alternate test module only, not baseline installed flight hardware, used only if RF fails the common-boundary comparison (branch C_ecr_hall: Hall-only fails, RF fails its common-boundary criterion and ECR passes it). Per A6, RF stays the preferred contingency, ECR is NOT elevated to an equal proposal baseline, and the common interface only prevents the fixture from structurally disadvantaging a Phase-1 branch before measurement.

Scope: ECR source + interstage + ECR magnet between IP-UP and IP-DN; off-module chain: DC-fed microwave generator, isolator, directional coupler, feed line to the coupling structure (PIM-ECR).

Uses common items: PMI-01, PMI-02, PMI-03, PMI-04, PMI-05, PMI-06, PMI-07, PMI-08, PMI-09, PMI-10, PMI-11.

Module-specific items:

* **PME-01 Microwave frequency.** Not selected; candidates only.
  * `f_ecr` [Hz]: **TBD** (the ECR module design (owner); closes at: procurement: ECR module design decision)
  * `f_ecr_candidate_2p45GHz` = 2450000000.0 Hz (SOURCED, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/f_ecr_candidate_2p45GHz_Hz`)
  * `f_ecr_candidate_5p8GHz` = 5800000000.0 Hz (SOURCED, assumed; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/inputs/f_ecr_candidate_5p8GHz_Hz`)
* **PME-02 Resonance field.** B_res = 2 pi f m_e / e (identity) at the candidates.
  * `B_res_2p45GHz` = 0.08752347556 T (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/B_res_ecr_2p45GHz_T`)
  * `B_res_5p8GHz` = 0.2071984319 T (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/B_res_ecr_5p8GHz_T`)
  * `ratio_B_res_2p45GHz_to_B_hall_typical` = 4.376173778 - (DERIVED, model-derived; `docs/experiments/hardware/hardware_requirements_v1.json#/derived_numbers/outputs/ratio_B_res_2p45GHz_to_B_hall_typical`)
* **PME-03 ECR magnet type.** Owner decision HWQ-05 (HW-PIM-04): an electromagnet allows the M0c state and is booked as ecr_magnet coil power; a permanent magnet makes M0b = M0c and is booked as 0 W with efficiency 1. The test magnet type matches the flight design intent, or the ecr_magnet ledger entry is the flight value (LOCK-1 input).
* **PME-04 Fringe field and magnet temperature.** Fringe field in the Hall channel (MCQ-QT-09) and, for a permanent magnet, demagnetization exposure to the combined opposing field at the magnet temperature (HW-MC-09, HW-PIM-15); magnet temperature measured during operation.
  * `ecr_fringe_field_in_channel` [T]: **TBD** (the MCQ-QT-09 magnetostatic analysis of the selected ECR magnet; closes at: design before HWQ-05; S1a maps)
  * `ecr_magnet_temperature` [degC]: **TBD** (the HW-ECR module thermal design (lane 15 ecr_magnet inputs; MCQ ecr_magnet_C); closes at: design; measured S3/Phase 2)
* **PME-05 Microwave chain and load plane.** Net microwave power at the coupling-structure input (bus_power_boundary_v1 ecr_source): DC-fed generator, isolator, directional coupler, feed line; chain loss between coupler and load plane characterised in S1a where the coupler cannot sit at the load plane (HW-PIM-12).
  * `chain_attenuation_evidence` = 2.0 dB (SOURCED, inferred; `docs/evidence/ecr_source/ecr_evidence_matrix.json#/entries/20`)
* **PME-06 Microwave-specific trips.** Reflected-power / isolator-load and electromagnet overcurrent/overtemperature trips feeding PMI-04 L3/L5.
  * `ecr_trip_limits` [-]: **TBD** (the selected generator, isolator and magnet ratings (A4); closes at: S1A-C2)
* **PME-07 Microwave leakage containment.** Inside the PMI-01 envelope, bonded at the PMI-06 point; feed-line penetration sealed (PMI-02).
* **PME-08 ECR source power range.** As PMR-03 for the ECR source.
  * `P_hi_ecr` [W]: **TBD** (the source allocation in bus_power_boundary_v1 (owner, lane 11); closes at: LOCK-1; bench stage S3)
* **PME-09 Plasma-facing materials.** Coupling structure and antenna O2-compatible (HW-PIM-10).
  * `module_materials_ecr` [-]: **TBD** (the ECR module design and cited O2-compatibility evidence; closes at: procurement: ECR module design)

| deviation | common items | deviation | confound risk | proposed control |
|---|---|---|---|---|
| DEV-ECR-01 | PMI-09 | the resonance magnet's fringe field reaches the Hall channel | a B(z) change attributed to the ionization method | MCQ-QT-09 analysis before the magnet selection; M0/M0b/M0c maps; INV-B3 tolerance; if exceeded the arm is reported non-comparable (no coil re-trim in the primary comparison) |
| DEV-ECR-02 | PMI-01, PMI-08 | magnet mass and interaction with magnetic parts of the thrust stand | stand calibration shift in ecr_hall only | per-configuration in-situ calibration; calibration with the ECR module installed, magnet on and off where possible (HW-SVC-05) |
| DEV-ECR-03 | PMI-08 | a waveguide feed is stiffer than a coax | stand stiffness/tare change | the microwave feed is a sham in every other configuration (same routing and fixation); coax preferred where the frequency permits (TBD) |
| DEV-ECR-04 | PMI-05 | magnet and coupling-structure heating | anode/gas temperature difference | recorded arm consequence; magnet and anode temperatures logged |
| DEV-ECR-05 | PMI-03 | electromagnet coil power booked under ecr_magnet; lane 19 abep_sim/cathode_integration.py PREIONIZER_COMPONENTS['ecr_hall'] lists only ecr_source (its ARCH_EXTRA_BOUNDARY_COMPONENTS includes ecr_magnet), and abep_sim/thermal_life.py covers only a permanent ecr_magnet | an ECR magnet load unseen by the lane 19 on/off checks and unchecked thermally if an electromagnet is chosen | this ICD follows bus_power_boundary_v1 (ecr_source + ecr_magnet); reconciliation belongs to the owning lanes (flagged, not fixed here) |
| DEV-ECR-06 | PMI-04, PMI-09 | a permanent magnet cannot be switched off (M0b = M0c) | installation and energization effects of the magnet cannot be separated (SHAM_ECR) | bound by M0 vs M0b B(z) maps and the re-trimmed-coil sensitivity condition (lane 37 section 3), reported |
| DEV-ECR-07 | PMI-11 | the S1b re-mount series measures the PIM-0 exchange only | an ECR-module-specific installation term (incl. magnet alignment) | PROPOSED S1a no-plasma module-exchange series with PIM-ECR unpowered (cold-flow manifold pressure, in-situ calibration zero/tare, B(z) incl. magnet); S1A-FW respected |

### ANNEX-HW0: `PIM-0` (hall_only), role CONTROLLED_REFERENCE_BLANK

HW-0 uses a blank/spacer module with equivalent interfaces and service-line presence so that module exchange is the controlled variable in Phase 1 (A6). HW-0 is the only configuration reported as hall_only; M0b (module installed, source unpowered) is a control state, never reported as hall_only.

Scope: flow-equivalent spacer between IP-UP and IP-DN; replicates the module mechanical envelope and gas path, no source hardware, no magnet (HW-PIM-02).

Uses common items: PMI-01, PMI-02, PMI-03, PMI-04, PMI-05, PMI-06, PMI-07, PMI-08, PMI-09, PMI-10, PMI-11.

Module-specific items:

* **PM0-01 Flow-equivalent duct.** Replicates the module gas path and ports; non-ferromagnetic; same body potential and bonding point.
* **PM0-02 Dummy/terminated lines.** RF coax and microwave feed as shams terminated off-stand; ECR magnet lead pair terminated; PMI-04: L1 reports PIM-0, L2 terminated, L3 jumpered, L4/L5 constant; thermocouples live.
* **PM0-03 Ports.** Source-chamber pressure port blanked or connected identically; I_src collector access present; OES port blanked if any occupant carries one.
* **PM0-04 Witness set.** Carries the per-arm interstage witness set at the identical module-outlet position on the module side of IP-DN (HW-PIM-14).
  * `witness_position` [-]: **TBD** (the module interface control drawing (HW-PIM-01); closes at: procurement: interface control drawing)
* **PM0-05 Thermal footprint.** Same IP-DN isolator hardware and thermocouple positions; no heater emulation of module waste heat (PMI-05 b).
* **PM0-06 Pressure-drop class reference.** Defines dp = 0 of PMI-10; matched passive inserts only if the RF and ECR modules fall in different classes (DEV-H0-03).

| deviation | common items | deviation | confound risk | proposed control |
|---|---|---|---|---|
| DEV-H0-01 | PMI-09 | PIM-0 cannot reproduce the ECR magnet's magnetic footprint without changing B(z) | field difference between HW-0 and HW-ECR | not emulated (a dummy magnet would itself disturb B); measured by M0/M0b/M0c maps against INV-B3 |
| DEV-H0-02 | PMI-05 | PIM-0 dissipates nothing | gas and anode temperature differ between arms | recorded arm consequence, never equalised (hardware identity_matrix may_differ); anode temperature logged; a heated PIM-0 would not represent hall_only |
| DEV-H0-03 | PMI-10, PMI-02 | one PIM-0 can match only one conductance if the RF and ECR modules differ | feed pressure at the distributor differs between arms | PROPOSED passive matched inserts (PIM-0 in the RF class and in the ECR class), each checked cold in S1a; otherwise the difference is reported in R_install |
| DEV-H0-04 | PMI-01 | PIM-0 mass and centre of gravity differ from the source modules | stand load | per-configuration in-situ calibration (HW-SVC-02) |
| DEV-H0-05 | PMI-04 | HW-0 has no PREIONIZER_IGNITION dwell in its start sequence | different Xe exposure, conditioning and thermal history before the atmosphere transfer | PROPOSED time-matched Xe hold in WARM_UP equal to the pre-registered pre-ionizer dwell; Xe consumed recorded against the single Xe allocation (A5 xe_mass_allocation) |

## 4. Confound table (what differs besides the ionization method)

| id | factor | HW-0 | RF | ECR | mechanism | removed / measured by | items | residual |
|---|---|---|---|---|---|---|---|---|
| CF-01 | module mass and centre of gravity | spacer mass | source + interstage (+ on-module matching) | source + interstage + magnet/yoke | stand load, stiffness and tare | per-configuration in-situ calibration (HW-SVC-02); mass/CG recorded | PMI-01, PMI-08 | MEASURED_AND_REPORTED |
| CF-02 | mounting and thrust-axis alignment | same flanges | same flanges | same flanges | cosine loss, zero shift | common datum and torque spec; torque/alignment record; S1b u_inst (+ PROPOSED S1a module-exchange series) | PMI-01, PMI-11 | REMOVED_BY_INTERFACE_AND_MEASURED |
| CF-03 | gas-path conductance, volume and surface | flow-equivalent duct | tube + interstage | coupling structure + interstage | feed pressure at the distributor, transients, residence time | pressure-drop class (PMI-10), cold-flow manifold pressure per configuration, wetted volume recorded; MFC setpoints identical | PMI-02, PMI-10 | MEASURED_AND_REPORTED |
| CF-04 | module wall surfaces (O recombination, outgassing, erosion products) | spacer walls | dielectric tube | coupling structure | species at HALL_INLET_Z0, deposits on H-1 | M0b control state (installed, unpowered); per-arm witness set (HW-PIM-14); inspection before/after | PMI-02, PMI-07 | RECORDED_ARM_CONSEQUENCE |
| CF-05 | magnetic field at the Hall channel | none (reference) | none in v1 | resonance magnet fringe | B(z) change | PMI-09 INV-B3 tolerance; M0/M0b/M0c maps; non-ferromagnetic structures | PMI-09 | MEASURED_WITH_COMPARABILITY_GATE |
| CF-06 | waste heat and thermal history | none | coil/tube/generator heat | coupling/magnet heat | anode and gas temperature, stand drift | declared module thermal path; isolated/instrumented IP-DN; T-SETTLE; anode temperature logged; order-balanced execution (A6 clarification) | PMI-05 | RECORDED_ARM_CONSEQUENCE |
| CF-07 | electrical potential, interstage current, generator pickup | declared potential | same + RF return | same + microwave return | cathode current budget, diagnostic bias | one declared potential (HWQ-07); I_interstage measured; separated returns; DUMMY_LOAD_PICKUP every pump-down | PMI-06, PMI-07 | REMOVED_BY_INTERFACE_AND_MEASURED |
| CF-08 | service lines on the stand | all lines as shams | RF coax live, others shams | microwave feed and magnet leads live, coax sham | stand stiffness, tare, thermal drift | union line set present in every configuration (HW-SVC-01) | PMI-08 | REMOVED_BY_INTERFACE |
| CF-09 | source power accounting | no component | rf_source | ecr_source + ecr_magnet | P_bus understated if a load is missed | bus_power_boundary_v1 slots only; no slotless module load in v1; load-plane measurement | PMI-03, PMI-07 | REMOVED_BY_INTERFACE |
| CF-10 | plume back-flow and extra atomic O at C-1 | baseline | possible | possible | cathode condition | recorded arm consequence; near-cathode RGA sampling (HW-C1-07) | PMI-07 | RECORDED_ARM_CONSEQUENCE |
| CF-11 | run order, conditioning, drift, hysteresis | - | - | - | architecture confounded with time | order-balanced scheme with HW-0 reference points (A6 clarification_execution_order); XE_HEALTH_CHECK; MODULE_ID in every record | PMI-04, PMI-11 | PROTOCOL_CONTROL |
| CF-12 | start sequence and Xe exposure | no pre-ionizer dwell | PREIONIZER_IGNITION on Xe | PREIONIZER_IGNITION on Xe | conditioning and thermal state at atmosphere transfer | PROPOSED time-matched Xe hold in HW-0 (DEV-H0-05); Xe consumed against the single allocation | PMI-04 | PROPOSED_CONTROL |
| CF-13 | cooling provisions | none | passive (PROPOSED) or liquid | passive | coolant-line forces, pump load | passive preferred; coolant sham pair with identical flow if liquid cooling is adopted (DEV-RF-03) | PMI-05, PMI-08 | PROPOSED_CONTROL |
| CF-14 | configuration identity errors | - | - | - | a reading attributed to the wrong arm | MODULE_ID line logged with every reading; configuration record | PMI-04, PMI-07 | REMOVED_BY_INTERFACE |

## 5. Milestones

* **A (conditional selection)**: YES (as a precondition). Conditional selection now: the fixture no longer structurally disadvantages any Phase-1 branch. 'Branch X is baseline provided H-1 Phase 1 shows ...' is measurable on one H-1 with module exchange as the controlled variable; no branch is selected by this ICD.
* **B (physics-backed selection)**: NOT YET. Blocked by: module designs (RF, ECR, PIM-0) and the interface control drawing; S1a values: dp_occ per grid flow, B(z) maps M0/M0b/M0c, load-plane calibration, dummy-load pickup; S1b values: u_inst, S_B, T-SETTLE; owner decisions HWQ-01/04/05/06/07/15 and PMQ-*; an admitted Hall closure for any absolute performance claim (credible set empty).
* **C (proposal/PDR freeze)**: NO (inputs only). The flight pre-ionizer ICD (flight mass, thermal, EMC, qualification) is Milestone C work; this ground-test ICD supplies its IP-DN datum, gas-path, bus-slot and control-line structure.
* **What could overturn it**: the ECR fringe field cannot meet INV-B3 at any practical distance/shielding (ecr_hall then non-comparable on H-1); an RF module that needs an assist magnet or liquid cooling without an owner-defined bus slot; S1b u_inst above u_inst,max (module exchange then not a clean controlled variable; D-06-B diverter becomes the fallback); RF and ECR conductances in different pressure-drop classes with no matched PIM-0 insert.

## 6. Owner questions

* **PMQ-01** Approve sizing the common envelope (PMI-01) to the largest occupant (ECR module with magnet/yoke and microwave feed)?
* **PMQ-02** Approve the common control harness L1-L5 including the MODULE_ID line and the PIM-0 termination rules (PMI-04)?
* **PMQ-03** Approve the pressure-drop class definition (PMI-10) and, if needed, matched passive PIM-0 inserts per class (DEV-H0-03)?
* **PMQ-04** Add an S1a no-plasma module-exchange series for PIM-RF and PIM-ECR (unpowered; cold-flow, calibration zero/tare, B(z)) to cover DEV-RF-05 / DEV-ECR-07?
* **PMQ-05** Adopt a time-matched Xe hold in the HW-0 start sequence equal to the pre-ionizer dwell (DEV-H0-05)?
* **PMQ-06** Prohibit slotless module loads (RF assist magnet, powered interstage, coolant pump) in v1, or commission a new bus-boundary version before LOCK-1?
* **PMQ-07** Relay of open hardware questions this ICD depends on: HWQ-01 (configuration-change procedure), HWQ-04 (INV-B3 tolerance), HWQ-05 (ECR magnet type), HWQ-06 (RF magnetization), HWQ-07 (module potential), HWQ-15 (interfaces frozen before Phase 1).

## 7. Consistency notes (flagged, not fixed: outside this lane's paths)

* lane 19 abep_sim/cathode_integration.py PREIONIZER_COMPONENTS['ecr_hall'] = ('ecr_source',) omits ecr_magnet (already flagged in docs/controls/DUAL_FEED_STATES.md); this ICD follows bus_power_boundary_v1.
* abep_sim/thermal_life.py checks ecr_magnet for permanent magnets only (bus allocation must be 0 W); an electromagnet choice under HWQ-05 needs a thermal check elsewhere.
* bus_power_boundary_v1 has no slot for an RF assist magnet or a powered interstage (HW-PIM-05; INTERSTAGE_MODEL.md section 9 assumes an unpowered, floating interstage).
* the lane 25 S1b re-mount series is defined on HW-0 only; module-exchange reproducibility of PIM-RF/PIM-ECR is not measured by it (PMQ-04).

## 8. Compliance

* **no_hall_performance_source**: No Hall transport closure, screening candidate or withdrawn 0-D number is used; no performance is predicted.
* **no_winner**: No architecture is ranked or eliminated; no hard-gate elimination is made here.
* **nuisance**: P5 calibration nuisance is never a design variable, setting or grid axis.
* **upstream**: Hall-closure uncertainty does not enter the feed side; IP-UP and everything upstream is identical in every configuration.
* **pure**: Pure data plus one standard-library builder; nothing wired into archengine; no frozen data, goldens or existing modules touched.
* **no_contact**: No supplier, facility or lab contact; published evidence is cited only through the merged evidence matrices.
* **numbers**: Every number is copied with source path, JSON pointer, sha256 and evidence class, or is TBD.

## 9. Pinned inputs (sha256 at the base commit; mutable governance files are not pinned)

* `abep_sim/arch_boundary.py` `8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae`
* `abep_sim/cathode_integration.py` `9c8e776b851c112da89b0621a2e1da0dd128ab647229214b81aed19c3e0561b0`
* `abep_sim/thermal_life.py` `dce2048233746ecc596866c1d561c8828f820c7960b9778db0d6d66a9c86d83c`
* `docs/architecture_comparison/experiment_protocol/protocol_draft.json` `287dd7ecd57087e46f2f3d786bfb2d64b01ac4fe29a29de21ef98b04c5ac96e3`
* `docs/architecture_comparison/hall_reference/hall_reference_v1.json` `c60e0adfbef2c6f8dddaa9b7e89cea6b0ce760d3c9777dff5a47c2bfda7cb2e6`
* `docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md` `2a08e8045d1cb61a121e84dc9f7bba268a1ec7b66476057d9093b4e044f6d616`
* `docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json` `54b7b00a60134f2d92f2eb5c9fb49f18d23623a566e04a4b7d70325a0e332509`
* `docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md` `2432edb7e9095fd630585768a62a811140b5230ba035afa3f0fc168636d11ca9`
* `docs/controls/DUAL_FEED_STATES.md` `88cd59a948336a76395c7a0ad499e92b0ecb8d95b7ae9a06c4e444d2c66c55e9`
* `docs/evidence/ecr_source/ecr_evidence_matrix.json` `4a65dbeec34f16f048fa515ced3bb959c02a981113e25da89e8bb844337fec88`
* `docs/evidence/rf_source/rf_evidence_matrix.json` `5f6d4e0ede8b2e21e45b740c28ac9320e7ddd6cfd70ef05012f85712ae0ac8e8`
* `docs/experiments/hardware/HARDWARE_DEFINITION.md` `1dfedf9743cde333684acceae5ba5ddbc42bf4bf4ad5be5edaf3fb9f8a7649d5`
* `docs/experiments/hardware/hardware_requirements_v1.json` `0b75be0a0ddc4888eb157c20e2b22dd4fce2a4bb94c4d6402cbe716ec73b0aa0`
* `docs/experiments/instrumentation/instrumentation_definition_v1.json` `7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96`
* `docs/experiments/magnet_coil/magnet_coil_qualification_v1.json` `53e92f4536f7b30054d3521adbd504eca725c4c6d79a6cb3b51c2fc4ce220b32`
* `docs/experiments/s1_readiness/s1_readiness_conditions_v1.json` `1d3388693191295f4c54ea9d1d38b36ca977193e0d9066aa40aac61776b27fd1`
* `docs/experiments/s1a_readiness/s1a_readiness_conditions_v1.json` `011808100ef38799668cb948324efa6492344d3b58ed3c436605ce5caf7025ac`
* `docs/interfaces/UPSTREAM_ICD.md` `4445031cbeb2710395298f2c1d12ca5893c17afd9f50d6b8ab9210ce4171180a`
* `docs/milestones/bundle1/bundle1_v5.json` `b61807b10fcc23e989c356b08887d6c56993f4f659900f9595dd0bfc23d822d2`
* `schemas/controls/dual_feed_state_machine_v1.json` `bc68ac0f7a35ced1c3bdcfcb1fb44880f63d57adf0e0bb22dae94d5dd07585ba`
* `schemas/interfaces/upstream_icd_v1.json` `2437d125060f2f24da06ac33b22220483f70b411033c91682cdffb5f01310850`
