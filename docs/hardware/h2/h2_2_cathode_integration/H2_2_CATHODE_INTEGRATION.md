# H2-2 cathode integration for C-1 (shielded Xe-fed LaB6 hollow cathode)

| | |
|---|---|
| lane | `fo_h2_2_cathode_integration` (trigger `T_H2_2_CATHODE_INTEGRATION`, owner addendum A7, H2 hardware wave) |
| status | **PRELIMINARY_DRAFT_PENDING_INTEGRATION**: design / preliminary sizing, not architecture selection |
| data (authoritative) | [`h2_2_cathode_integration_v1.json`](h2_2_cathode_integration_v1.json), written by [`build_h2_2_cathode_integration.py`](build_h2_2_cathode_integration.py) (`--check` reproduces both files byte for byte) |
| test | `tests/test_h2_2_cathode_integration.py` |
| base commit | `8ea7e4b` |
| architectures | `hall_only`, `rf_hall`, `ecr_hall` share one C-1 (INV-C1). No winner, no ranking |

This file is generated. Edit the builder, not this file.

**Owner basis (immutable, sha256-pinned; the build refuses on a mismatch):**

| file | sha256 |
|---|---|
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` | `5a5adb8116eecee418992977c239f198a88835c739f357f13a8bddd51778c2ac` |
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json` | `0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621` |
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json` | `aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180` |
| `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json` | `dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925` |
| `docs/decisions/verification/A5_BASELINE_VERIFICATION.json` | `4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523` |

Verified deliverables read for values (sha256 at the base commit, recorded as provenance; the values are re-read and compared on every build): `docs/experiments/hardware/hardware_requirements_v1.json`, `docs/budgets/xe_ledger/xe_ledger_v1.json`, `docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json`, `docs/evidence/cathode/cathode_evidence_v1.json`, `docs/experiments/lifetime_ao/ao_lifetime_register_v5.json`, `docs/experiments/instrumentation/instrumentation_definition_v1.json`.
Mutable governance files are never read or pinned.

**What this is not.** Not a performance prediction (no thrust, efficiency, discharge current or plasma state). Not based on any Hall transport closure (credible set empty) or on abep_sim/plasma_devices.py. Not a C-1 selection or a procurement; catalog data are reference only. A5 numbers are allocations or requirements, never predictions.

## Summary

- **Location (PRELIMINARY): L-CENTRAL.** Put C-1 on the axis inside the inner magnetic core. The published analog practice is JPL/Busek internal mounting. On the 8-kW BHT-8000 the internal cathode gave a 5-10 V better coupling voltage than the external one, and a more collimated, symmetric plume (Hofer et al. 2008). That is an analog result: its magnitudes do not transfer to H-1. Internal mounting brings its own costs: radiation into the inner coil, a cantilever mount, keeper erosion by trapped low-energy ions (for ABEP: N, O ions) and service lines that leave through the rear axis, where the pre-ionizer module slot sits. L-EXTERNAL remains the alternative if H2-1 cannot provide the bore.
- **Flow measurement.** Two ranges are proposed: a precision range with FS about 0.2 mg/s Xe and a start range with FS about 1 mg/s. Even under the standard class, better than 1 % spec-only at 0.10 mg/s needs a precision FS of about 0.3 mg/s or less, and that cannot also cover the analog ignition flows (up to about 1 mg/s). A single 1 %-FS device sized for ignition flows (FS 1 mg/s) gives 10 % at 0.10 mg/s, which is 0.54 kg on the 5.4 kg cathode term. At FS 0.2 mg/s (about 2 sccm Xe) the catalog places the range in its lowest model, rated ±2 % FS: 4.0 % (0.216 kg) spec-only, and 4.09-4.25 % with the zero terms (ΔT 1-5 °C). That is the value the Xe ledger carries for now. The standard ±(0.5 % Rd + 0.1 % FS) class would give 0.7 % (0.0378 kg) spec-only, or 1.09-1.6 % with the zero terms. It is a procurement requirement still to be demonstrated on Xe. Reaching < 1 % needs both that class and a per-block installed zero check. Every certificate must declare its reference conditions: 0 °C versus 20 °C is a 7.3 % trap.
- **Purge-while-hot costs Xe per start.** The poisoning rule (heat the emitter only under Xe flow) turns the preheat time into Xe: 0.02-0.18 g per start for the analog preheat times at 0.10-0.15 mg/s, excluding any ignition-flow dwell. If conditioning ran at the analog start flow (1 mg/s) for the whole preheat, the figure would be up to 1.2 g per start (bound rows), about 21 kg at the SC-2 heavy-restart N_starts. The start procedure must therefore bound the ignition-flow dwell. Heater power (the start-phase bus peak) trades against Xe per start. At design flows the term reaches the kg class only with per-orbit restarts, and N_starts is TBD.
- **Emission class straddle.** The H-1 envelope is bounded at 8.33 A at 180 V (RFP), and its low end is unknown. It spans published LaB6 classes. At the low end a steady keeper or heater load may be needed, and that load is booked per arm.
- **Hard incompatibility: none found** (eight checks, section 9).

## 1. Design-parameter table

Basis ∈ {requirement, allocation, analog, derived, assumed, pending}. Article class: FR = flight-representative, TA = H-1 test-article only, GF = ground/facility only.

| id | name | value | units | basis | evidence | status | class | source |
|---|---|---|---|---|---|---|---|---|
| H22-01 | C-1 mounting location | central, on the thruster axis inside the inner magnetic core (option L-CENTRAL); L-EXTERNAL retained as the alternative | - | analog | inferred | PRELIMINARY | FR | HOFER2008 pp. 2008-2009 (internal cathode improved coupling voltage by 5-10 V vs external; 6-11 V in the Jameson 6-kW study quoted there; centerline mounting 'favors the improved coupling'), pp. 2007, 2010-2011 (more collimated, symmetric plume), p. 2012 (drawbacks) |
| H22-02 | C-1 axis orientation | parallel to the thrust axis | - | analog | measured | PRELIMINARY | FR | HOFER2008 p. 2006 ('The major axis of both cathodes was aligned parallel with the thrust axis') |
| H22-03 | C-1 orifice axial position relative to the H-1 exit plane / inner pole | — | mm | pending | none | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ | FR | HOFER2008 p. 2006 (analog: internal cathode 'slightly recessed upstream of a hollow section of the inner magnetic pole') |
| H22-04 | inner-core bore diameter needed for L-CENTRAL | >= C-1 keeper OD + radial clearance | mm | pending | none | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ | FR | IEPC2015_43 p. 4 (analog keeper OD about 3.0 cm for the 1.5-cm JPL cathode); SITAEL HC1/HC3 keeper OD not stated (IEPC2017_365) |
| H22-05 | cathode service-line routing for L-CENTRAL | heater, keeper, cathode-common, thermocouple leads and the Xe line exit through the rear of the inner core; they must pass the pre-ionizer module slot between IP-UP and IP-DN without changing with the module and without crossing HALL_INLET_Z0 | - | requirement | assumed | PENDING docs/interfaces/preionizer_module/ | FR | docs/experiments/hardware/hardware_requirements_v1.json HW-C1-01, HW-C1-04, HW-PIM-01 (summary section 0), HW-SVC-01 |
| H22-06 | shielding / isolation concept of the emitter | S1 Xe flows whenever the emitter is hot and O2 may be present; S2 Xe purge before heating (XE_PURGE -> CATHODE_CONDITIONING); S3 keeper encloses the orifice and shields it from back-ion bombardment; S4 O-compatible keeper/orifice-plate material; S5 emitter kept at or above the reported O2-tolerance temperature during O-bearing operation | - | requirement | inferred | PRELIMINARY | FR | docs/experiments/hardware/hardware_requirements_v1.json HW-C1-03; schemas/controls/dual_feed_state_machine_v1.json states; IEPC2015_43 p. 2 (keeper protects the orifice plate from back-ion bombardment); IEPC2017_365 p. 3; DOSSIER lab6.env.o2_withstand_1570C |
| H22-07 | emitter temperature floor during O-bearing operation (PROPOSED design rule) | 1843.15 | K | analog | measured (secondary) | PRELIMINARY | FR | DOSSIER lab6.env.o2_withstand_1570C (G&K p. 306) and IEPC2015_43 p. 2: LaB6 at 1570 degC withstands O2 up to 1e-4 Torr without emission degradation |
| H22-08 | required attenuation of O from the local environment to the emitter | — | - | pending | none | TBD - requires a measured emitter-region O/O2 tolerance (G02) and near-cathode partial pressures (RGA, HW-C1-07) | FR | LANE19 required_attenuation(p_ext, p_tol); DOSSIER U03, G02 |
| H22-09 | keeper / orifice-plate material | — | - | pending | none | TBD - requires the C-1 selection and keeper-material coupon results (HW-C1-06) | FR | IEPC2015_43 p. 2 (analog keeper and orifice-plate materials: graphite); AOL5 evidence on graphite in O (RIT10 grid erosion higher on O2 than N2, attributed to O-graphite chemistry; MISSE 2 pyrolytic graphite AO erosion yield 4.15e-25 cm3/atom) |
| H22-10 | magnetic-field magnitude at the C-1 orifice | — | G | pending | none | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ | FR | HOFER2008 p. 2012 (analog: the centerline region has an axially diverging field of the order of the peak channel field, 100-300 G) |
| H22-11 | magnetic-field orientation at the C-1 orifice | axial (parallel to the cathode axis) for L-CENTRAL; set by the local field line for L-EXTERNAL | - | analog | measured | PRELIMINARY | FR | HOFER2008 p. 2007 (internal cathode plume 'compressed and elongated in the axial direction by the axial magnetic field emanating from the inner magnetic circuit'); IEPC2015_43 p. 4 (solenoid gives 'an adjustable axial magnetic field at the cathode exit to simulate that found on axis' of HERMeS) |
| H22-12 | allowed field magnitude at emitter and keeper | — | G | pending | none | TBD - requires C-1 characterization inside the MC-1 field at the operating coil currents (S1a) and the H2-1 field at the cathode location | FR | no accessed source states a limit; G&K p. 313 (ionization instabilities in the cathode plume can be inhibited by gas flow and/or the applied axial field): the field is a functional parameter of the cathode, not only an interference |
| H22-13 | ferromagnetic-free zone around C-1 and its mount | no ferromagnetic conductor, fastener or structure near MC-1 unless the model and M0/M0b map show it within INV-B3 | - | requirement | assumed | PRELIMINARY | FR | docs/experiments/hardware/hardware_requirements_v1.json HW-MC-12 |
| H22-14 | LaB6 emitter operating temperature (reported/derived span) | 1844.5, 1973.15 | K | analog | inferred | PRELIMINARY | FR | see derived.emitter_temperature_points (G&K p. 254; IEPC2015_43 p. 1; IEPC2017_365 p. 2; DOSSIER Joussot; LANE19 Lafferty table) |
| H22-15 | emitter temperature reached before ignition | 1460.0, 1693.15 | K | analog | measured | PRELIMINARY | FR | IEPC2017_365 p. 5 (about 1460 K); DOSSIER lab6.t.joussot_preheat (about 1420 degC) |
| H22-16 | heater power during preheat (analog envelope) | 45.0, 400.0 | W | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | IEPC2017_365 p. 5 (45 W / 60 W, HC1); IEPC2015_43 p. 3 (120 W routinely, H6 LaB6; up to 300 W for the 1.5-cm cathode); DOSSIER lab6.start.joussot_heater_ignition (184.5 W), lab6.start.zsch_heater_max (up to 400 W, non-optimized) |
| H22-17 | steady heater power | 0 W if C-1 self-heats at the lowest H-1 operating I_d; otherwise the maintained heater power of the selected unit (analog 185 W below 5 A, Joussot) | W | analog | measured | TBD - requires the C-1 self-heating current (S1a) and the lowest operating I_d (Phase 1) | FR | LANE19 (G&K p. 337: heater off once the discharge runs); DOSSIER lab6.heater.joussot_maintained, lab6.heater.joussot_selfheat_current |
| H22-18 | conduction path C-1 -> H-1 | thin refractory cathode tube -> base flange -> insulating ring -> H-1 inner core / back pole | - | analog | measured | PENDING docs/hardware/h2/h2_5_thermal_network/ | FR | IEPC2015_43 pp. 2-3 (tube 'sufficiently long and thin to minimize conduction of heat from the insert to the base plate'), p. 4 (flange 'insulated from the thruster body by a Macor-ceramic ring'; flight: brazed assembly) |
| H22-19 | analog mounting-interface temperature | flange_K: 500.0; keeper_K: 600.0; at_heater_W: 20.0 | K | analog | measured | PENDING docs/hardware/h2/h2_5_thermal_network/ | FR | IEPC2017_365 p. 5 (HC1 thermal test: interface about 500 K, keeper about 600 K at about 20 W heater power; emitter about 1250 K) |
| H22-20 | radiation path C-1 -> inner magnetic circuit | heat shields around the heater (analog about ten turns of Ta foil) + an inner-coil hot-spot check against the coil insulation class | - | analog | measured | PENDING docs/hardware/h2/h2_5_thermal_network/ | FR | HOFER2008 p. 2012 (internal mounting 'can potentially lead to overheating of the thruster's inner magnetic circuit due to radiation from the hot cathode insert'); IEPC2015_43 p. 3 (Ta foil heat shield); docs/experiments/hardware/hardware_requirements_v1.json HW-MC-07, HW-MC-08 |
| H22-21 | keeper DC ignition voltage capability (PROPOSED) | 150.0 | V | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | IEPC2015_43 p. 4 (150 V applied to the keeper); G&K pp. 310-311 (standard DC keeper voltage 50-150 V; higher ignition voltages for 'cathodes with larger orifices (typically 2-mm diameter or larger)' - a statement about orifice size, not specific to LaB6; the 100-500 V figure recorded in the first draft of this row is to verify) |
| H22-22 | keeper pulse ignition capability (PROPOSED) | 300.0, 600.0 | V | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | G&K pp. 310-311 ('To ensure reliable thruster ignition over life, it is standard to apply both a DC keeper voltage in the 50- to 150-V range and a pulsed keeper voltage in the 300- to 600-V range') |
| H22-23 | keeper current: ignition limit and continuous capability | ignition_limit_A: 2.0; continuous_capability_A: 0.5, 3.0 | A | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | IEPC2015_43 p. 4 (keeper current regulated to 2 A at ignition); IEPC2017_365 p. 8 (HC1 350 h endurance on MSHT100 with 0.5 A keeper); DOSSIER lab6.start.zsch_keeper_min (at least 3 A keeper for self-heating) |
| H22-24 | keeper running voltage (analog envelope) | 5.0, 35.0 | V | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | IEPC2015_43 p. 4 (5-15 V after ignition); IEPC2017_365 p. 7 (HC1 keeper-only 30 -> 15 V), p. 8 (HC3 14-35 V) |
| H22-25 | keeper mode after discharge ignition | floating if C-1 self-heats at the operating I_d; current-carrying otherwise (steady cathode_keeper load) | - | analog | measured | TBD - requires the C-1 self-heating current measured in S1a vs the H-1 I_d range | FR | IEPC2015_43 p. 4 (keeper off and floating above 10 A), p. 5 (below 5 A the cathode stopped unless keeper > 2 A); IEPC2017_365 pp. 8-9 (HC1 floating with HT100; keeper on with MSHT100 and with HC3 on HT100) |
| H22-26 | heater supply current capability | 13.0 | A | analog | measured | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | LANE19 startup_reference / IEPC-2017-276 p. 3 (1.5-cm LaB6 heater current 13 A); IEPC2017_365 p. 4 (lab heater supply 80 V / 13 A, reference only) |
| H22-27 | ignition sequence | XE_PURGE (Xe cathode flow at the purge setpoint; heater, keeper, magnet off), CATHODE_CONDITIONING (heater on, Xe cathode flow at its setpoint; magnet off), CATHODE_IGNITION (keeper voltage, then keeper current regulation; heater on; magnet off), PREIONIZER_SEED (start variant V2 of rf_hall / ecr_hall only: pre-ionizer ignited on Xe after keeper coupling and before anode voltage; absent in hall_only and in V1), XE_DISCHARGE_IGNITION (magnet on, Xe anode flow at the ignition setpoint, anode voltage applied; heater 'per cathode design (TBD - requires cathode qualification)'), WARM_UP (heater off; keeper 'per cathode design', off/floating or held on per H22-25) | - | requirement | assumed | PRELIMINARY | FR | schemas/controls/dual_feed_state_machine_v1.json state names; LANE19 startup_reference.hall_only (G&K p. 337; IEPC-2017-276 pp. 3-4; IEPC2015_43 p. 4) |
| H22-28 | heaterless ignition | alternative only, not baseline | - | analog | measured | PRELIMINARY | FR | IEPC2017_365 p. 3 (heater is a single point of failure; heaterless ignition possible 'at the cost of requiring higher voltages with the risk of damaging the LaB6 emitter due to thermal shocks'), p. 6 (HC1 up to 800 V; pp. 6-7: 1 mg/s), p. 8 (HC3 up to 700 V at 1-2 mg/s); DOSSIER lab6.start.heaterless_ignitions_title (title-level, verify) |
| H22-29 | cathode Xe branch topology | Xe metering split (A5 Xe branch), isolation valve(s), normally closed, particulate filter, flow control (H-1: cathode MFC; flight: restrictor or proportional valve, TBD), pressure transducer near C-1, dielectric break (if the grounding scheme needs one), C-1 gas inlet | - | requirement | assumed | PENDING docs/hardware/h2/h2_3_gas_path_plenum/ | FR | A5 architecture.xe_branch; docs/experiments/hardware/hardware_requirements_v1.json HW-C1-04 (own line, never crosses HALL_INLET_Z0), HW-FS-01 |
| H22-30 | number of isolation valves in series (flight) | 2 | - | assumed | assumed | TBD - requires the owner's fault-tolerance/safety standard and H2-3 | FR | PROPOSED by this lane (single-fault tolerance against Xe loss); no accessed source fixes it |
| H22-31 | filter rating | — | um | pending | none | TBD - requires the smallest passage of the flow restrictor / C-1 orifice (C-1 selection) and H2-3 | FR | no accessed source |
| H22-32 | flight flow restrictor / regulated inlet pressure | — | Pa | pending | none | PENDING docs/hardware/h2/h2_3_gas_path_plenum/ | FR | no accessed source |
| H22-33 | cathode Xe purity | flight_lower_bound_percent: 99.99; h1_test_PROPOSED_percent: 99.999 | % | analog | measured | PRELIMINARY | FR | IEPC2015_43 p. 2 and DOSSIER lab6.purity.crudest_grade (LaB6 tolerates about 99.99 % Xe); HOFER2008 p. 2007 (research grade 99.9995 % used); IEPC2017_365 p. 5 (grade 4.5) |
| H22-34 | cathode-line pressure transducer | near C-1 (analog: about 20 cm from the emitter) | - | analog | measured | PRELIMINARY | TA | IEPC2017_365 p. 5 (Kulite transducer on the feed line about 20 cm from the emitter) |
| H22-35 | dielectric break rating on the cathode line | — | V | pending | none | PENDING docs/hardware/h2/h2_4_ppu_bus/ | FR | depends on the grounding choice (H22-37) and the keeper pulse (H22-22) |
| H22-36 | discharge-supply topology | discharge supply between anode and cathode common; the thruster floats | - | requirement | assumed | PRELIMINARY | FR | docs/experiments/hardware/hardware_requirements_v1.json HW-ELEC-01; G&K p. 339 ('the thruster floats with respect to either spacecraft common in space or vacuum-chamber common on the ground') |
| H22-37 | cathode-common reference (option E-FLOAT-R) | cathode common floating; spacecraft common (flight) or facility ground (test) tied to cathode common through a declared resistor | - | analog | measured | PRELIMINARY | FR | G&K p. 339 ('can be controlled on a spacecraft by a resistor between the spacecraft common and the cathode common'); IEPC2017_365 p. 4 (all supplies to a common negative reference, setup floating with respect to ground) |
| H22-38 | analog cathode-to-ground potential | -22.0, -10.0 | V | analog | measured | PRELIMINARY | FR | HOFER2008 p. 2008 (internal BaO -10 to -13 V; external LaB6 -22 to -15 V; typical -10 to -20 V); G&K p. 339 (coupling voltage typically about 20 V) |
| H22-39 | C-1 body isolation from the H-1 body | insulating ring between C-1 flange and H-1 mount; H-1 body potential declared | - | analog | measured | TBD - requires the owner's H-1 body potential decision | FR | IEPC2015_43 p. 4 (Macor ring); H-1 body potential: owner decision (extends docs/experiments/hardware/hardware_requirements_v1.json HWQ-07) |
| H22-40 | C-1 lines across the thrust stand | heater +/-, keeper, cathode common, tube thermocouple, Xe line: all in SVC-1, identical in every configuration | - | requirement | assumed | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | docs/experiments/hardware/hardware_requirements_v1.json HW-SVC-01, HW-C1-05, HW-C1-09 |
| H22-41 | interstage current return | any separately biased pre-ionizer electrode returns to cathode common and is metered (enters I_emit) | - | requirement | assumed | PENDING docs/interfaces/preionizer_module/ | TA | docs/experiments/hardware/hardware_requirements_v1.json HW-ELEC-02; LANE19 section 2 |
| H22-42 | cathode Xe design flow and upper test point (A5) | 0.1, 0.15 | mg/s | allocation | assumed | PRELIMINARY | FR | docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json xe_mass_allocation.cathode_flow_design_target_mg_s / cathode_flow_experimental_upper_test_point_mg_s |
| H22-43 | cathode MFC precision range full scale (PROPOSED) | 0.2 | mg/s Xe | derived | model-derived | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | derived.flow_measurement_uncertainty: FS 0.2 mg/s puts 0.10 / 0.15 mg/s at 50 % / 75 % of FS |
| H22-44 | cathode start-flow range full scale (PROPOSED) | 1.0 | mg/s Xe | analog | measured | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | IEPC2017_365 p. 6 (HC1 started at 0.6 and 0.1 mg/s with heater), p. 8 (HC3 0.4-0.8 mg/s with heater), p. 7 (HC1 diode 0.8 mg/s); heaterless 1-2 mg/s (p. 8) excluded |
| H22-45 | flow accuracy class | procurement_requirement_PROPOSED: +/-(0.5 % of reading + 0.1 % of FS), calibrated on Xe, to be demonstrated at FS about 0.2 mg/s Xe; conservative_catalog_class_at_FS0.2: +/-2 % FS (F-110C-002 / F-200CV-002 range) | - | analog | assumed | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | BRONKHORST_ELFLOW_SELECT p. 2 [PDF pages 3-4] (catalog classes and range table, reference only); derived.catalog_class_applicability |
| H22-46 | flow repeatability | 0.002 | fraction of reading | analog | assumed | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | BRONKHORST_ELFLOW_SELECT p. 2 ('Repeatability < 0,2% Rd', catalog class) |
| H22-47 | flow step for the spot-mode minimum-flow search (PROPOSED) | 0.005 | mg/s | assumed | assumed | TBD - requires owner confirmation (H22-OQ-05) | TA | PROPOSED by this lane: 5 % of the design flow, 2.5 % of the proposed precision FS; checked against the resolution requirement (H22-52), the catalog control stability, the repeatability and the lower control limit in derived.flow_resolution_and_lower_limit |
| H22-52 | flow readout / setpoint resolution | requirement_PROPOSED_mg_s: 0.0005; instrument_value: — | mg/s | assumed | assumed | TBD - requires the selected instrument's stated resolution (H3-C1-02) | TA | PROPOSED by this lane (<= 1/10 of the H22-47 step); the accessed catalog states no resolution |
| H22-53 | minimum controllable / usable flow of the precision range | lower_control_limit_digital_mg_s: 0.001067; lower_control_limit_analog_mg_s: 0.004; flow_at_10pct_u_rel_conservative_class_mg_s: 0.04 | mg/s | derived | model-derived | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | TA | FS 0.2 mg/s / catalog turndown (BRONKHORST_ELFLOW_SELECT PDF page 3, reference only); accuracy floor from derived.flow_resolution_and_lower_limit |
| H22-48 | flow calibration method | gravimetric on Xe in the final configuration (primary) with a constant-volume rate-of-rise cross-check; reference conditions declared | - | requirement | assumed | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ | GF | docs/experiments/instrumentation/instrumentation_definition_v1.json INS-05 calibration (REF-SNYDER2017: each gas, final configuration, across the range, at least every 12 months; constant-volume or constant-pressure calibrator) |
| H22-49 | uncertainty of the 15,000 h cathode Xe mass from flow measurement | FS0.2_conservative_catalog_class_at_0.10_spec_only: 0.216; FS0.2_conservative_catalog_class_at_0.10_with_zero_terms_dT5C: 0.2296; FS0.2_standard_class_requirement_at_0.10_spec_only: 0.0378; FS0.2_standard_class_requirement_at_0.10_with_zero_terms_dT1C: 0.05885; FS0.2_standard_class_requirement_at_0.10_with_zero_terms_dT5C: 0.08657; FS1.0_1pctFS_at_0.10: 0.54 | kg | derived | model-derived | PRELIMINARY | TA | derived.flow_measurement_uncertainty, derived.flow_measurement_headline |
| H22-50 | cathode flow delivered to the Xe ledger | — | mg/s | pending | none | TBD - requires the H4 measurement (S1a / Phase 1) | FR | docs/budgets/xe_ledger/xe_ledger_v1.json parameters mdot_cathode (closes with the C-1 measured spot-mode minimum flow) |
| H22-51 | Xe per start from the purge-while-hot rule | t_preheat x mdot_purge (derived table) | g | derived | model-derived | PENDING docs/budgets/xe_ledger/ | FR | derived.preheat_purge_xe |

Notes:

- **H22-01:** choice inferred from analog practice; magnitudes are not transferable (8-kW Xe device). Owner question H22-OQ-01; feasibility PENDING H2-1 inner-core bore
- **H22-03:** needs the H-1 inner pole geometry and B map; fixed and recorded once chosen (HW-C1-01)
- **H22-04:** keeper OD TBD - requires the C-1 selection (HWQ-09); clearance TBD - requires H2-1/H2-5
- **H22-05:** interface demand to the pre-ionizer module ICD (A6)
- **H22-06:** S1-S3 are adopted requirements/practice; S4-S5 are PROPOSED design rules of this lane
- **H22-07:** secondary statement of diode tests (level 5); O2 only - no atomic-O or N2 threshold exists (DOSSIER U04, U05); PROPOSED, not in the RFP
- **H22-09:** graphite keepers are standard on Xe but carry a published O-chemistry warning; owner question H22-OQ-07
- **H22-10:** value comes from the MC-1 design and the M0 B-map at the actual coil currents (HW-MC-03)
- **H22-12:** the magnet is off in CATHODE_IGNITION and comes on in XE_DISCHARGE_IGNITION (schemas/controls/dual_feed_state_machine_v1.json), so the lit keeper discharge sees a field step at discharge ignition; the S1a characterization must include that transient (keeper voltage/current through magnet turn-on)
- **H22-13:** C-1 tube/flange/heat-shield materials must be declared magnetically (analog JPL: Mo tube, Ta foil, graphite; IEPC2015_43 pp. 2-3)
- **H22-14:** span of cited points for other hardware; the C-1 value depends on its emission current density; C-1 tube temperature is measured (HW-C1-09), emitter temperature only with a pyrometer view
- **H22-16:** C-1 value TBD - requires the C-1 selection; a start-phase load on cathode_heater
- **H22-19:** one analog point at low heater power; not a C-1 boundary condition
- **H22-21:** minimum capability; the C-1 value comes from its ignition test with heater (SITAEL HC1 45-50 V; HC3 < 300 V: IEPC2017_365 pp. 6, 8)
- **H22-22:** motivated also by O exposure: the RAM-HET cathode could not be re-ignited after two days of N2/O2 testing (LANE19 andreussi_ram_het_cathode; not attributed to poisoning in the source). Owner question H22-OQ-02
- **H22-23:** C-1 value TBD - requires the C-1 selection
- **H22-26:** C-1 value TBD - requires the C-1 selection
- **H22-27:** state outputs as in the state machine; the C-1 part (purge, conditioning, cathode ignition) is identical in every arm (INV-C1); PREIONIZER_SEED is an arm-specific start step between keeper coupling and anode voltage; the heater-off point (XE_DISCHARGE_IGNITION or WARM_UP) is a C-1 qualification result
- **H22-28:** heaterless starts need a higher ignition flow (Xe per start) and a higher-voltage keeper supply
- **H22-29:** element order PROPOSED by this lane
- **H22-30:** owner question H22-OQ-03
- **H22-32:** sized from the measured C-1 flow (H4 output), never from an assumed flow
- **H22-33:** the H-1 test value is PROPOSED so that feed impurities do not confound the O-exposure attribution
- **H22-34:** test-article diagnostic; a flight pressure sensor is H2-3's decision
- **H22-37:** resistor value TBD - requires the H2-4 bus/charging analysis and the facility safety case (H22-OQ-04)
- **H22-38:** sets the order of magnitude of cathode-common-to-ground stand-off; not a C-1 value
- **H22-41:** rf_hall / ecr_hall configurations only; hall_only has none
- **H22-42:** allocation and test point, not demonstrated flows; the measured spot-mode flow is an H4 output
- **H22-43:** = 2.035 sccm Xe (G&K/LANE19 convention; 2.049 sccm ideal gas, derived.sccm_convention); Xe range of any real unit TBD - requires the manufacturer's Xe calibration; lower control limit 0.001067 mg/s digital (catalog turndown 1:187.5, reference only); resolution: see H22-52
- **H22-44:** separate controller or second range; covers heated-start analogs up to 1 mg/s
- **H22-45:** at FS 0.2 mg/s and 0.10 mg/s: 4.0 % under the conservative catalog class, 0.70 % under the standard class (spec-only; the standard class is not established by the catalog for this range - procurement requirement still to be demonstrated); a 1 % FS class at FS 1.0 mg/s gives 10 %
- **H22-46:** repeatability is what R_arch sees (same MFC, same setpoint in every arm; W4 INS-05)
- **H22-47:** the step is at least 10x the PROPOSED resolution, the catalog control stability and the repeatability, and 4.7x the digital lower control limit at FS 0.2 mg/s, so successive steps are distinguishable on the same instrument; the absolute value of the minimum flow still carries the class accuracy (0.004 mg/s under the conservative class, about one step) until the gravimetric calibration closes it. Catalog control stability is quoted 'typical for 1 ln/min N2' and is not a Xe value
- **H22-53:** the catalog does not state that the accuracy class holds at the turndown limit; the usable floor of the search is set by the accepted accuracy (10 % is a parametric axis, assumed)
- **H22-48:** gravimetric primary PROPOSED by this lane; see derived.gravimetric_calibration and rate_of_rise_check
- **H22-49:** measurement term only; the flow itself is an H4 output; spec-only values require the per-block installed zero check (derived.flow_measurement_headline.zero_term_condition)
- **H22-50:** the ledger keeps the A5 0.10 mg/s design term until then; this lane never replaces it
- **H22-51:** feeds the ledger's m_startup; the ledger already books a preheat term (scenario_per_event_derivation)

## 2. Mechanical location options (published analogs, labelled)

| aspect | L-CENTRAL | L-EXTERNAL |
|---|---|---|
| description | C-1 on the thruster axis inside the inner magnetic core, cantilevered from the back pole | C-1 outside the outer pole, axis parallel to the thrust axis |
| analog label | ANALOG (8-kW BHT-8000 on Xe; 12.5-kW HERMeS cathode) | ANALOG |
| published practice | internally mounted cathodes on JPL/Busek high-power thrusters (BHT-8000 internal BaO; HERMeS on-axis LaB6 field simulated by a solenoid) | traditional external mounting (HOFER2008 p. 2006: 'typical of Hall thrusters with optimized cathode locations'); SITAEL HC1/HC3 coupled externally to HT100 (IEPC2017_365 pp. 7-9) |
| coupling voltage | analog improvement of 5-10 V (BHT-8000, 8 kW) and 6-11 V (6-kW study quoted) vs external; the source attributes it to location, not emitter (HOFER2008 p. 2009) | analog: larger coupling voltage (-15 to -22 V vs -10 to -13 V, HOFER2008 p. 2008) |
| plume exposure | sits in the central region where the source notes a possible trap for low-energy ions and increased keeper erosion (HOFER2008 p. 2012); for ABEP those ions include N+, N2+, O+, O2+ (AOL-M05) - keeper erosion and O chemistry at the keeper are a C-1 test item | outside the beam; the external cathode's electrons form a 'halo' along field lines around the pole pieces (HOFER2008 p. 2007); inner-core erosion negligible (p. 2012) |
| magnetic field at orifice | axial, of the order of the peak channel field (analog 100-300 G, HOFER2008 p. 2012); predictable from the MC-1 design because it lies on the axis | set by the fringing field at the chosen position; depends on the separatrix location (no accessed source for H-1) -> PENDING H2-1 map |
| thermal | radiates into the inner magnetic circuit (overheating risk, HOFER2008 p. 2012) -> heat shields and an inner-coil hot-spot check (H2-5, HW-MC-07/08) | decoupled from the inner coil; radiates to the outer pole and the spacecraft side |
| mechanical | cantilever from the back pole: launch-vibration moment arm (HOFER2008 p. 2012) -> H2-7; needs an inner-core bore (H2-1) | bracket on the outer pole; no inner-core bore |
| experiment identity | position cannot change with a module exchange; axisymmetric plume keeps the thrust vector on the axis for every arm | asymmetric near-field plume (HOFER2008 pp. 2009-2011) - identical in every arm, so a common-mode effect on R_arch |
| rear interface | service lines leave through the rear axis, where the pre-ionizer module slot sits (IP-UP..IP-DN): routing must be designed into the module ICD | service lines stay clear of the pre-ionizer module slot |

**PRELIMINARY choice:** L-CENTRAL (PRELIMINARY; H22-01). Owner question H22-OQ-01.

## 3. Plume / oxygen exposure and shielding (A5 risk 3)

- **Threat.** A5 architecture-closing risk rank 3 ('Xe-fed cathode consumption and oxygen isolation', evidence RI-MASS-CATHODE-XE): O2/O from the thruster's own neutral efflux, back-flowing plume ions (N+, N2+, O+, O2+) and, on ground, the facility background; in flight the thruster faces the wake, so the ram-facing AO flux of lane 19 is an upper bound, not the local value (inferred; magnitude TBD).
- **Concept:**
  - S1 Xe cathode flow on whenever the emitter is hot (HW-C1-03);
  - S2 Xe purge before heating (XE_PURGE);
  - S3 keeper enclosing the orifice (physical and ion shield);
  - S4 O-compatible keeper/orifice-plate/insulator materials (TBD, coupons HW-C1-06);
  - S5 emitter at or above 1843 K (1570 degC) during O-bearing operation (PROPOSED, H22-07);
  - S6 no emitter heating while O2 is in the chamber without Xe flow; exposure log (AOL-CX-05);
- **Must be demonstrated:**
  - **D-CX-01:** C-1 emission, keeper and coupling voltage stay within a pre-registered drift band over the O-bearing Phase-1 hours (daily Xe reference, AOL-CX-01);
  - **D-CX-02:** near-cathode O2 / H2O / N2 partial pressures logged during O-bearing operation (RGA sampling port, HW-C1-07 / AOL-CX-03), as the proxy for the emitter-region environment (G02);
  - **D-CX-03:** spot-mode minimum Xe flow vs emission current measured on C-1 in the H-1 field with an atmospheric anode feed (A5 risk 3, G06); poisoning can enlarge the plume-mode region (Suzuki 2024 abstract via LANE19);
  - **D-CX-04:** restart after O-bearing operation succeeds within the keeper capability (start log AOL-CX-02);
  - **D-CX-05:** post-campaign insert/orifice/keeper inspection (HW-C1-08, AOL-PM-05);
- **Not demonstrable here:** atomic-O exposure (no AO source in HW-ENV-07; HWQ-11) - flight transfer stays open (DOSSIER G02, G09).

## 4. Magnetic, thermal, keeper/igniter, Xe plumbing, electrical return

These are covered by rows H22-10..H22-41 of section 1:

- **Magnetic:** H22-10..13. The field at the orifice is PENDING H2-1. It is a functional parameter (G&K p. 313), so C-1 must be characterized inside the MC-1 field, not only in diode mode.
- **Thermal:** H22-14..20.
- **Keeper/igniter:** H22-21..28, including the ignition sequence expressed as dual-feed state-machine states. Heaterless ignition is an alternative only.
- **Xe plumbing:** H22-29..35.
- **Electrical:** H22-36..41. The PRELIMINARY choice is E-FLOAT-R: a floating cathode common with a declared resistor tie to spacecraft common or facility ground.

Emitter temperature points (K):

| point | T (K) | source | evidence |
|---|---|---|---|
| Lafferty fit at 5 A/cm2 | 1844.5 | LANE19 derived table (CATHODE_INTEGRATION.md section 5) | model-derived |
| Lafferty fit at 10 A/cm2 | 1915.0 | LANE19 derived table (CATHODE_INTEGRATION.md section 5) | model-derived |
| G&K: > 10 A/cm2 at 1650 degC | 1923.15 | DOSSIER lab6.t.goebel_10Acm2 (G&K p. 254) | measured |
| IEPC-2015-43: > 20 A/cm2 at about 1700 degC | 1973.15 | IEPC2015_43 p. 1 | measured |
| SITAEL: LaB6 operates at about 1900 K | 1900.0 | IEPC2017_365 p. 2 | measured |
| Joussot: about 1600 degC at 19 A | 1873.15 | DOSSIER lab6.t.joussot_19A | measured |

The operating span of the cited points is 1844.5-1973.15 K. Its lower end is a model-derived Lafferty-fit point; the others are measured analog values. The O2 tolerance point is 1843.15 K.

Discharge-current upper bounds I_d ≤ P/V_d. These are bounds, not predictions; they size the C-1 emission capability (HW-C1-02):

| P label | P (W) | V_d (V) | I_d bound (A) |
|---|---|---|---|
| RFP_1500W | 1500 | 180 | 8.333 |
| RFP_1500W | 1500 | 200 | 7.5 |
| RFP_1500W | 1500 | 250 | 6.0 |
| RFP_1500W | 1500 | 300 | 5.0 |
| RFP_1500W | 1500 | 305 | 4.918 |
| A5_alloc_1350W | 1350.0 | 180 | 7.5 |
| A5_alloc_1350W | 1350.0 | 200 | 6.75 |
| A5_alloc_1350W | 1350.0 | 250 | 5.4 |
| A5_alloc_1350W | 1350.0 | 300 | 4.5 |
| A5_alloc_1350W | 1350.0 | 305 | 4.426 |
| A5_alloc_1300W | 1300.0 | 180 | 7.222 |
| A5_alloc_1300W | 1300.0 | 200 | 6.5 |
| A5_alloc_1300W | 1300.0 | 250 | 5.2 |
| A5_alloc_1300W | 1300.0 | 300 | 4.333 |
| A5_alloc_1300W | 1300.0 | 305 | 4.262 |

## 5. Flow-measurement capability for 0.10-0.15 mg/s Xe

- **Requirement.** measure the C-1 Xe flow at the A5 design target 0.10 mg/s and the upper test point 0.15 mg/s, and step down to the spot-mode minimum, with an uncertainty small enough that the measured flow can be booked in the Xe ledger; the flow itself is NOT assumed (H4 output).
- **Concept:**
  - two ranges: a precision cathode MFC (FS about 0.2 mg/s Xe) and a start-flow range (FS about 1 mg/s Xe);
  - calibrated on Xe, installed, at the operating inlet pressure and temperature (W4 INS-05);
  - gravimetric primary calibration + rate-of-rise cross-check;
  - reference conditions declared on every certificate (7.3 % trap between 0 and 20 degC references);
  - zero checked at the installed orientation and temperature before each block;
- **% of reading vs % of full scale.** a % FS specification inflates the relative error as 1/Q: at 0.10 mg/s a 1 % FS device with FS 1.0 mg/s gives 10 % (0.54 kg over 15,000 h), the same class with FS 0.2 mg/s gives 2 %; the catalog's lowest-range model (+/-2 % FS, the conservative class at FS 0.2 mg/s) gives 4 %; the standard +/-(0.5 % Rd + 0.1 % FS) class would give 0.70 %, but the catalog does not establish it for a FS of about 2 sccm Xe (procurement requirement to be demonstrated); all spec-only, zero terms excluded.

Relation: u_rel = rd_frac + fs_frac * FS / Q (specification form); zero terms added in quadrature: orientation 0.4 % FS and temperature 0.12 % FS/degC x dT (REF-SNYDER2017 via W4); u_m = u_rel x m_cathode(15,000 h), treated as fully correlated over the mission (a calibration bias does not average down).

Gas: every row assumes the instrument is calibrated ON XENON in its final configuration; a gas-conversion-factor (GCF) reading adds an uncertainty that no accessed source quantifies for Xe (REF-SNYDER2017 Table 2 covers Ar, He, SF6, C2F6, H2 only, per W4) -> TBD - requires a Xe calibration.

| spec | FS (mg/s) | FS (sccm Xe) | flow | Q/FS | u_rel spec | u_m 15,000 h (kg) | u_rel +zero (ΔT 1 °C) | u_rel +zero (ΔT 5 °C) |
|---|---|---|---|---|---|---|---|---|
| SPEC-FS1 | 0.2 | 2.035 | design_target | 0.5 | 0.02 | 0.108 | 0.02167 | 0.02466 |
| SPEC-FS1 | 0.2 | 2.035 | upper_test_point | 0.75 | 0.01333 | 0.108 | 0.01445 | 0.01644 |
| SPEC-FS1 | 0.3 | 3.052 | design_target | 0.3333 | 0.03 | 0.162 | 0.03251 | 0.03699 |
| SPEC-FS1 | 0.3 | 3.052 | upper_test_point | 0.5 | 0.02 | 0.162 | 0.02167 | 0.02466 |
| SPEC-FS1 | 0.5 | 5.086 | design_target | 0.2 | 0.05 | 0.27 | 0.05418 | 0.06164 |
| SPEC-FS1 | 0.5 | 5.086 | upper_test_point | 0.3 | 0.03333 | 0.27 | 0.03612 | 0.0411 |
| SPEC-FS1 | 1.0 | 10.17 | design_target | 0.1 | 0.1 | 0.54 | 0.1084 | 0.1233 |
| SPEC-FS1 | 1.0 | 10.17 | upper_test_point | 0.15 | 0.06667 | 0.54 | 0.07225 | 0.08219 |
| SPEC-FS1 | 2.0 | 20.35 | design_target | 0.05 | 0.2 | 1.08 | 0.2167 | 0.2466 |
| SPEC-FS1 | 2.0 | 20.35 | upper_test_point | 0.075 | 0.1333 | 1.08 | 0.1445 | 0.1644 |
| SPEC-CAT-STD | 0.2 | 2.035 | design_target | 0.5 | 0.007 | 0.0378 | 0.0109 | 0.01603 |
| SPEC-CAT-STD | 0.2 | 2.035 | upper_test_point | 0.75 | 0.006333 | 0.0513 | 0.008433 | 0.01151 |
| SPEC-CAT-STD | 0.3 | 3.052 | design_target | 0.3333 | 0.008 | 0.0432 | 0.01486 | 0.02307 |
| SPEC-CAT-STD | 0.3 | 3.052 | upper_test_point | 0.5 | 0.007 | 0.0567 | 0.0109 | 0.01603 |
| SPEC-CAT-STD | 0.5 | 5.086 | design_target | 0.2 | 0.01 | 0.054 | 0.02315 | 0.03742 |
| SPEC-CAT-STD | 0.5 | 5.086 | upper_test_point | 0.3 | 0.008333 | 0.0675 | 0.01622 | 0.02544 |
| SPEC-CAT-STD | 1.0 | 10.17 | design_target | 0.1 | 0.015 | 0.081 | 0.04437 | 0.07365 |
| SPEC-CAT-STD | 1.0 | 10.17 | upper_test_point | 0.15 | 0.01167 | 0.0945 | 0.03019 | 0.04947 |
| SPEC-CAT-STD | 2.0 | 20.35 | design_target | 0.05 | 0.025 | 0.135 | 0.08718 | 0.1464 |
| SPEC-CAT-STD | 2.0 | 20.35 | upper_test_point | 0.075 | 0.01833 | 0.1485 | 0.05862 | 0.09788 |
| SPEC-CAT-LOW | 0.2 | 2.035 | design_target | 0.5 | 0.012 | 0.0648 | 0.01462 | 0.01876 |
| SPEC-CAT-LOW | 0.2 | 2.035 | upper_test_point | 0.75 | 0.01067 | 0.0864 | 0.01203 | 0.01436 |
| SPEC-CAT-LOW | 0.3 | 3.052 | design_target | 0.3333 | 0.014 | 0.0756 | 0.01879 | 0.02577 |
| SPEC-CAT-LOW | 0.3 | 3.052 | upper_test_point | 0.5 | 0.012 | 0.0972 | 0.01462 | 0.01876 |
| SPEC-CAT-LOW | 0.5 | 5.086 | design_target | 0.2 | 0.018 | 0.0972 | 0.02757 | 0.0403 |
| SPEC-CAT-LOW | 0.5 | 5.086 | upper_test_point | 0.3 | 0.01467 | 0.1188 | 0.02022 | 0.02816 |
| SPEC-CAT-LOW | 1.0 | 10.17 | design_target | 0.1 | 0.028 | 0.1512 | 0.05028 | 0.07736 |
| SPEC-CAT-LOW | 1.0 | 10.17 | upper_test_point | 0.15 | 0.02133 | 0.1728 | 0.03507 | 0.05259 |
| SPEC-CAT-LOW | 2.0 | 20.35 | design_target | 0.05 | 0.048 | 0.2592 | 0.09633 | 0.152 |
| SPEC-CAT-LOW | 2.0 | 20.35 | upper_test_point | 0.075 | 0.03467 | 0.2808 | 0.06559 | 0.1022 |
| SPEC-CAT-002 | 0.2 | 2.035 | design_target | 0.5 | 0.04 | 0.216 | 0.04086 | 0.04252 |
| SPEC-CAT-002 | 0.2 | 2.035 | upper_test_point | 0.75 | 0.02667 | 0.216 | 0.02724 | 0.02835 |
| SPEC-CAT-002 | 0.3 | 3.052 | design_target | 0.3333 | 0.06 | 0.324 | 0.06129 | 0.06378 |
| SPEC-CAT-002 | 0.3 | 3.052 | upper_test_point | 0.5 | 0.04 | 0.324 | 0.04086 | 0.04252 |
| SPEC-CAT-002 | 0.5 | 5.086 | design_target | 0.2 | 0.1 | 0.54 | 0.1022 | 0.1063 |
| SPEC-CAT-002 | 0.5 | 5.086 | upper_test_point | 0.3 | 0.06667 | 0.54 | 0.0681 | 0.07087 |
| SPEC-CAT-002 | 1.0 | 10.17 | design_target | 0.1 | 0.2 | 1.08 | 0.2043 | 0.2126 |
| SPEC-CAT-002 | 1.0 | 10.17 | upper_test_point | 0.15 | 0.1333 | 1.08 | 0.1362 | 0.1417 |
| SPEC-CAT-002 | 2.0 | 20.35 | design_target | 0.05 | 0.4 | 2.16 | 0.4086 | 0.4252 |
| SPEC-CAT-002 | 2.0 | 20.35 | upper_test_point | 0.075 | 0.2667 | 2.16 | 0.2724 | 0.2835 |

Specification classes:

- `SPEC-FS1`: W4 REF-SNYDER2017 as recorded in instrumentation_definition_v1.json references ('manufacturer accuracy typically 1% full scale'); W4 treats it as 1 sigma (coverage to verify).
- `SPEC-CAT-STD`: BRONKHORST_ELFLOW_SELECT p. 2 [PDF page 3 of 8, 'Technical specifications'] 'Accuracy (incl. linearity) standard: +/-0,5% Rd plus +/-0,1%FS' (based on actual calibration); applies to the models other than F-110C-002/-005 and F-200CV-002/-005.
- `SPEC-CAT-LOW`: BRONKHORST_ELFLOW_SELECT p. 2 [PDF page 3] '+/-0,8% Rd plus +/-0,2% FS for F-110C-005/F-200CV-005' (second-lowest range model).
- `SPEC-CAT-002`: BRONKHORST_ELFLOW_SELECT p. 2 [PDF page 3] '+/-2% FS for F-110C-002/F-200CV-002' (lowest range model).

Which catalog class applies: the Xe FS in sccm is read numerically against the catalog's air and Ar columns of the min/max-range table (BRONKHORST_ELFLOW_SELECT PDF page 4). This is INDICATIVE only: Xe is not listed, the Xe conversion factor of the instrument is not in any accessed source (TBD - requires the manufacturer's Xe range and calibration statement), and the table's normal reference conditions are not defined on the accessed pages (verify). The conservative class is the worst class among all models matched under either reading.

| FS (mg/s) | FS (sccm Xe) | models if read as air | models if read as Ar | conservative class |
|---|---|---|---|---|
| 0.2 | 2.035 | F-110C-002 / F-200CV-002 | F-110C-002 / F-200CV-002 | SPEC-CAT-002 |
| 0.3 | 3.052 | F-110C-002 / F-200CV-002, F-110C-005 / F-200CV-005 | F-110C-002 / F-200CV-002 | SPEC-CAT-002 |
| 0.5 | 5.086 | F-110C-005 / F-200CV-005 | F-110C-002 / F-200CV-002, F-110C-005 / F-200CV-005 | SPEC-CAT-002 |
| 1.0 | 10.17 | F-111B-020 / F-201CV-020 | F-111B-020 / F-201CV-020 | SPEC-CAT-STD |
| 2.0 | 20.35 | F-111B-020 / F-201CV-020, F-111B-050 / F-201CV-050 | F-111B-020 / F-201CV-020 | SPEC-CAT-STD |

Finding: at FS about 2 sccm Xe (0.2 mg/s) both readings fall only in the F-110C-002 / F-200CV-002 model, whose catalog class is +/-2 % FS; the standard +/-(0.5 % Rd + 0.1 % FS) class is NOT established by the catalog for this range and is therefore a procurement requirement still to be demonstrated (Xe calibration certificate + S1a gravimetric calibration).

Headline at 0.10 mg/s, FS 0.2 mg/s (u_rel as a fraction; u_m in kg over 15,000 h):

| class | spec | u_rel spec-only | u_m spec-only | u_rel +zero ΔT 1 °C | u_rel +zero ΔT 5 °C | u_m +zero ΔT 1 °C | u_m +zero ΔT 5 °C |
|---|---|---|---|---|---|---|---|
| conservative catalog class | SPEC-CAT-002 | 0.04 | 0.216 | 0.04086 | 0.04252 | 0.2207 | 0.2296 |
| standard class procurement requirement | SPEC-CAT-STD | 0.007 | 0.0378 | 0.0109 | 0.01603 | 0.05885 | 0.08657 |

Zero-term condition: the spec-only values hold only if (PROPOSED requirement) the zero is checked in the installed orientation at the operating temperature before each block (removes the 0.4 % FS orientation term) and the MFC body temperature stays within a declared dT of the zero-check temperature during the block; otherwise the zero-term-inclusive values apply (REF-SNYDER2017 via W4: 0.4 % FS orientation, 0.12 % FS/degC; the catalog states < 0.05 % FS/degC zero and 0.2 % at 90 deg attitude, typical N2 - the lane keeps the larger W4 terms).

Finding: at 0.10 mg/s with FS 0.2 mg/s the flow-measurement term is between the standard-class requirement (0.7 % spec-only) and the conservative catalog class (4.0 % spec-only, 4.25 % with zero terms at dT 5 degC); the < 1 % level is reachable only if the standard class is demonstrated on Xe AND the zero terms are removed by the per-block zero check.

Resolution and lower control limit. Instrument resolution: TBD - requires the selected instrument's readout and setpoint resolution (not stated in the accessed catalog). Requirement: ≤ 0.0005 mg/s (PROPOSED by this lane: <= 1/10 of the spot-mode search step (H22-47)). FS / turndown with the catalog turndown 1:187.5 (digital) or 1:50 (analog), reference only; the catalog does not state that the accuracy class holds down to this limit, so the usable floor of the minimum-flow search is where the accuracy is still acceptable (flow_at_u_rel columns; the 5 %/10 % targets are parametric axes, assumed). Digital setpoint communication is PROPOSED because the analog turndown gives 0.004 mg/s at FS 0.2 mg/s.

| FS (mg/s) | LCL digital (mg/s) | LCL analog (mg/s) | control stability (mg/s) | q at 5 % (±2 % FS) | q at 10 % (±2 % FS) | q at 10 % (standard) |
|---|---|---|---|---|---|---|
| 0.2 | 0.001067 | 0.004 | 0.0002 | 0.08 | 0.04 | 0.002105 |
| 1.0 | 0.005333 | 0.02 | 0.001 | 0.4 | 0.2 | 0.01053 |

Search step 0.005 mg/s: step_over_resolution_requirement: 10.0; step_over_control_stability_FS0.2: 25.0; step_over_repeatability_at_0.10: 25.0; step_over_min_controllable_digital_FS0.2: 4.688; conservative_absolute_accuracy_at_0.10_mg_s: 0.004. the step is at least 10x the PROPOSED resolution, the catalog control stability and the repeatability, and 4.7x the digital lower control limit at FS 0.2 mg/s, so successive steps are distinguishable on the same instrument; the absolute value of the minimum flow still carries the class accuracy (0.004 mg/s under the conservative class, about one step) until the gravimetric calibration closes it. Catalog control stability is quoted 'typical for 1 ln/min N2' and is not a Xe value.

sccm convention: 0.0983009 mg/s per sccm is used (ideal gas at 273.15 K / 1 atm: 0.0976274; ideal / Z = 0.098301; difference 0.006899). the lane constant equals the ideal-gas value divided by the compressibility factor quoted in the LANE19 locator for G&K Eq. B-5 (verify against the book). The two conventions differ by about 0.7 %; this affects only the informational sccm columns (masses and uncertainties are computed in mg/s). An MFC certificate states its own conversion (ideal gas or real gas, and its reference conditions); the H3 order must name the convention explicitly.

Gravimetric calibration: m_min = sqrt(2) * u_balance / u_target (two weighings, balance term only; buoyancy, line-volume and temperature corrections come on top); duration = m_min / Q. u_balance values are a parametric axis (assumed), not a statement about any balance; a heavy Xe bottle on a high-capacity balance usually has a coarser readability - the bottle mass sets the achievable u_balance (TBD - requires the calibration-rig design, H2-6).

| u_balance (mg) | u_target | min mass (g) | duration at 0.10 mg/s (h) | duration at 0.15 mg/s (h) |
|---|---|---|---|---|
| 1.0 | 0.005 | 0.2828 | 0.7857 | 0.5238 |
| 1.0 | 0.01 | 0.1414 | 0.3928 | 0.2619 |
| 10.0 | 0.005 | 2.828 | 7.857 | 5.238 |
| 10.0 | 0.01 | 1.414 | 3.928 | 2.619 |

Rate-of-rise cross-check: dp/dt = Q R_s T / V, R_s = R / M_Xe (M_Xe = 131.293 g/mol, G&K App. B). V = 0.5 L, design_target: 3.713 Pa/s; V = 0.5 L, upper_test_point: 5.569 Pa/s; V = 1.0 L, design_target: 1.856 Pa/s; V = 1.0 L, upper_test_point: 2.785 Pa/s.

Reference conditions: the ratio is 1.07322. a flow unit referenced to 20 degC read as if referenced to 0 degC (or the reverse) is off by this factor (~7.3 %); the MFC certificate's standard/normal reference conditions must be declared and converted explicitly (G&K Eq. B-5 uses 273.15 K / 1 atm).

## 6. Cathode Xe to the parametric Xe ledger

A5 arithmetic reproduced: design_target_15000h_kg: 5.4; design_target_18000h_kg: 6.48; upper_test_point_15000h_kg: 8.1; upper_test_point_18000h_kg: 9.72 (consistent with A5: True).

Purge-while-hot: Xe per start = t_preheat x mdot_purge (HW-C1-03 rule: the emitter is heated only under Xe flow) ; mission = Xe per start x N_starts. N_starts: docs/budgets/xe_ledger/xe_ledger_v1.json scenarios SC-1 (nominal_restart) / SC-2 (heavy_restart: one start per orbit over 26,000 h at 180 km); scenario values, not allocations.

| case | t_preheat (s) | purge flow | Xe per start (g) | kg at SC-1 N | kg at SC-2 N | heater Wh per start |
|---|---|---|---|---|---|---|
| PH-HC1-60W | 200.0 | 0.1 | 0.02 | 0.02 | 0.3547 | 3.333 |
| PH-HC1-60W | 200.0 | 0.15 | 0.03 | 0.03 | 0.5321 | 3.333 |
| PH-HC1-60W | 200.0 | 1.0 | 0.2 | 0.2 | 3.547 | 3.333 |
| PH-HC1-45W | 600.0 | 0.1 | 0.06 | 0.06 | 1.064 | 7.5 |
| PH-HC1-45W | 600.0 | 0.15 | 0.09 | 0.09 | 1.596 | 7.5 |
| PH-HC1-45W | 600.0 | 1.0 | 0.6 | 0.6 | 10.64 | 7.5 |
| PH-JPL-1p5cm | 1200.0 | 0.1 | 0.12 | 0.12 | 2.128 | — |
| PH-JPL-1p5cm | 1200.0 | 0.15 | 0.18 | 0.18 | 3.193 | — |
| PH-JPL-1p5cm | 1200.0 | 1.0 | 1.2 | 1.2 | 21.28 | — |

Finding: the preheat time is set by the C-1 heater design; under the purge-while-hot rule it converts directly into Xe per start. Heater power (start-phase bus peak, H2-4) trades against Xe per start (Xe ledger m_startup). At the cathode design flows (0.10-0.15 mg/s) the term reaches the kg class only with per-orbit restarts; if conditioning or ignition ran at the analog start flow (up to 1 mg/s) for the whole preheat, Xe per start rises by up to 10x (bound rows), so the ignition-flow dwell must be bounded by the start procedure (H22-OQ-06).

## 7. Interface demands

| id | from | to | quantity | value | units | status |
|---|---|---|---|---|---|---|
| IFD-01 | H2-2 | H2-1 (docs/hardware/h2/h2_1_hall_chamber_magnet/) | inner-core bore for L-CENTRAL | >= C-1 keeper OD + clearance (analog keeper OD 30 mm) | mm | PENDING C-1 selection and H2-1 core flux cross-section |
| IFD-02 | H2-1 (docs/hardware/h2/h2_1_hall_chamber_magnet/) | H2-2 | B magnitude and direction at the C-1 orifice and along the keeper, at the operating coil currents | — | G | PENDING docs/hardware/h2/h2_1_hall_chamber_magnet/ |
| IFD-03 | H2-2 | H2-1 (docs/hardware/h2/h2_1_hall_chamber_magnet/) | ferromagnetic-free zone and declared magnetic properties of C-1 materials (HW-MC-12) | declared list | - | PRELIMINARY |
| IFD-04 | H2-2 | H2-4 PS-C (docs/hardware/h2/h2_4_ppu_bus/) | keeper supply: DC ignition voltage, pulse capability, current limit, continuous current | dc_V_min: 150.0; pulse_V: 300.0, 600.0; ignition_limit_A: 2.0; continuous_A: 0.5, 3.0; running_V: 5.0, 35.0 | V / A | PRELIMINARY (analog; C-1 values PENDING) |
| IFD-05 | H2-2 | H2-4 PS-C (docs/hardware/h2/h2_4_ppu_bus/) | heater supply | power_W: 45.0, 400.0; current_A_max: 13.0 | W / A | PENDING C-1 selection (analog envelope) |
| IFD-06 | H2-2 | H2-4 PS-C (docs/hardware/h2/h2_4_ppu_bus/) | bus components booked by C-1 | cathode_heater (start phases; steady only if not self-heating), cathode_keeper (ignition; steady only if not self-heating) | W | PRELIMINARY (bus_power_boundary_v1 component names) |
| IFD-07 | H2-2 | H2-4 PS-C (docs/hardware/h2/h2_4_ppu_bus/) | grounding: floating cathode common with a declared resistor to spacecraft common / facility ground; cathode-line dielectric break rating | E-FLOAT-R; analog cathode-to-ground -10 to -22 V | V / ohm | TBD - requires H2-4 charging analysis and facility safety case |
| IFD-08 | H2-2 | H2-4 PS-C (docs/hardware/h2/h2_4_ppu_bus/) | emission capability to cover | I_emit = I_d + I_keeper + I_interstage with I_d <= 8.33 A at 180 V (RFP bound); <= 7.5 A at 180 V under the 1.35 kW allocation | A | PRELIMINARY (bounds, not predictions) |
| IFD-09 | H2-2 | H2-5 (docs/hardware/h2/h2_5_thermal_network/) | C-1 heat loads and nodes | start_heat_W: 45.0, 400.0; emitter_K: 1844.5, 1973.15; emitter_K_span_note: span of cited points for other hardware; its lower end (1844.5 K) is a model-derived Lafferty-fit point (LANE19), the other points are measured analog values (derived.emitter_temperature_points); analog_flange_K: 500.0; analog_keeper_K: 600.0; steady_heat_to_body_W: — | W / K | PRELIMINARY; steady heat TBD - requires the C-1 selection and S1a tube thermocouple data |
| IFD-10 | H2-5 (docs/hardware/h2/h2_5_thermal_network/) | H2-2 | inner-coil hot spot with C-1 radiation (L-CENTRAL); flange boundary temperature | — | K | PENDING docs/hardware/h2/h2_5_thermal_network/ |
| IFD-11 | H2-2 | H2-3 (docs/hardware/h2/h2_3_gas_path_plenum/) | cathode Xe branch from the Xe metering split: isolation valves, filter, flow control, transducer, break; never crosses HALL_INLET_Z0 | H22-29..H22-35 | - | PENDING H2-3 (if the Xe branch is outside H2-3's scope, the integration pass reassigns it) |
| IFD-12 | H2-2 | H2-6 (docs/hardware/h2/h2_6_diagnostics_fixture/) | cathode diagnostics and flow metrology | precision cathode MFC FS about 0.2 mg/s Xe; accuracy class: standard +/-(0.5 % Rd + 0.1 % FS) on Xe as a requirement to be demonstrated, +/-2 % FS as the conservative catalog class for this range; readout/setpoint resolution <= 0.0005 mg/s (PROPOSED, H22-52); lower control limit about 0.0011 mg/s with digital setpoint (catalog turndown, reference only, H22-53), start range FS about 1 mg/s Xe, per-block installed zero check (orientation, temperature) with MFC body temperature logged, gravimetric + rate-of-rise calibration rig, tube thermocouple (HW-C1-09), pyrometer view if possible, RGA port near C-1 (HW-C1-07), cathode-line pressure transducer, keeper voltage oscillation channel (plume-mode detection), cathode-to-ground potential, witness coupons HW-C1-06 | - | PENDING docs/hardware/h2/h2_6_diagnostics_fixture/ |
| IFD-13 | H2-2 | H2-7 (docs/hardware/h2/h2_7_mechanical_bom/) | C-1 mass, envelope and mount | analog_mass_g_without_cables: SITAEL HC1: 30.0; SITAEL HC3: 50.0; mount: cantilever from the back pole (L-CENTRAL) - vibration check; disassembly: HW-C1-08 | g | PENDING C-1 selection (IEPC2017_365 pp. 5, 8 analog masses) |
| IFD-14 | H2-2 | A6 pre-ionizer module ICD (docs/interfaces/preionizer_module/) | C-1 service-line routing past the module slot; C-1 position independent of the module; interstage return to cathode common metered | H22-05, H22-41 | - | PENDING docs/interfaces/preionizer_module/ |
| IFD-15 | H2-2 | A6 Xe ledger (docs/budgets/xe_ledger/) | measured mdot_cathode with its uncertainty; t_preheat and purge flow per start | mdot_cathode: H4 output; u_rel_flow_at_0.10_mg_s_FS0.2: conservative_catalog_class_spec_only: 0.04; conservative_catalog_class_with_zero_terms_dT1C_dT5C: 0.04086, 0.04252; standard_class_requirement_spec_only: 0.007; standard_class_requirement_with_zero_terms_dT1C_dT5C: 0.0109, 0.01603; use: the ledger carries the conservative class until the Xe calibration demonstrates the standard class; spec-only values apply only under the per-block installed zero check (derived.flow_measurement_headline.zero_term_condition), otherwise the zero-term values; xe_per_start_g: derived.preheat_purge_xe (design-flow rows exclude the ignition-flow dwell; bound rows at 1 mg/s include it) | mg/s (fraction for u_rel), g | PRELIMINARY (ledger present and verified in base, unlike the brief's PENDING listing; values closed by H4) |
| IFD-16 | H2-2 | A6 Phase-1 prereg framework (docs/experiments/phase1_prereg_framework/) | cathode flow and power identical across arms (INV-C1) and logged at every point; cathode state logged at every extinction | HW-C1-01, HW-C1-05, AOL-CX-06 | - | PRELIMINARY |
| IFD-17 | H-1 CI C-1 (hardware definition) | H2-2 | C-1 fixed recorded position; HWQ-09 C-1 type and emission rating | — | - | TBD - requires the owner decision HWQ-09 |

## 8. Architecture-changing blockers touched (A7)

- **Blocker 3 (Xe/cathode closure).** Direct: defines the flow-measurement capability for the 0.10-0.15 mg/s measurement, the spot-mode minimum-flow search (D-CX-03), the purge-while-hot Xe per start and the O-isolation demonstrations (D-CX-01..05); no value is closed here.
- **Blocker 1 (Hall-only sustainment at the actual atmospheric feed state).** Indirect: C-1 is identical in every arm; Phase-1 extinction records must separate cathode-limited (plume-mode, keeper oscillation) from discharge extinctions (AOL-CX-06) so that a cathode limit is never read as a sustainment limit.
- **Blocker 2 (incremental RF/ECR benefit after full bus-power accounting).** Indirect: cathode_keeper and cathode_heater are common bus components; if an arm's I_d falls below the C-1 self-heating current a steady keeper load appears in that arm only (LANE19) - measured per arm, never assumed.

## 9. Hard-incompatibility check

**Verdict: none found.**

| item | finding | evidence class | veto |
|---|---|---|---|
| central-mount geometry | no evidence either way: the check is the H-1 inner-core bore (after inner wall, inner coil radial build and non-saturating core cross-section) against the C-1 keeper OD + clearance, PENDING H2-1 and the C-1 selection; L-EXTERNAL remains the fallback, so even a negative result moves the location, not the architecture (derived.central_bore_check) | none (pending) | False |
| cathode Xe mass vs the 40 kg requirement | the A5 design term 0.10 mg/s gives 5.4 kg (13.5 %); analog diode minimum flows (0.6 mg/s at 2.5-4 A) would give 81 % but belong to other hardware and are not verdict-bearing (veto layer RI-MASS-CATHODE-XE straddles); closes only by measurement (A7 blocker 3) | model-derived / measured (analog) | False |
| purge-while-hot Xe per start | 0.02-0.18 g per start for the analog preheat times at 0.10-0.15 mg/s (ignition-flow dwell excluded); up to 1.2 g per start if conditioning ran at the analog start flow of 1 mg/s for a 20-min preheat (bound rows), which at the Xe ledger's SC-2 heavy-restart N_starts would be about 21 kg, more than half of the 40 kg requirement; at design flows the term is kg-class only with per-orbit restarts. The bound combines the longest analog preheat with the highest analog ignition flow and is not evidence about C-1, so it is not a veto; it makes a fast preheat and a bounded ignition-flow dwell (H22-OQ-06) start-procedure requirements | model-derived | False |
| oxygen exposure of the emitter | no atomic-O or N2 threshold exists (NO_QUANTITATIVE_EVIDENCE); O2 evidence tolerates up to 1e-4 Torr at 1570 degC; cannot be refuted or confirmed without test | measured (secondary) | False |
| magnetic field at the orifice | no accessed source gives a limit; axial fields of 100-300 G on axis are standard analog practice | measured (analog) | False |
| electrical return | floating cathode common with a resistor tie is published flight practice | measured (textbook) | False |
| emission range vs analog cathode classes | the H-1 envelope (bound 8.33 A at 180 V, unknown low end) straddles published classes (SITAEL HC3 1-3 A design; JPL 1.5-cm needs >= 7.5 A without keeper; Joussot self-heats from 5 A): a steady keeper or heater load may be needed at the low end - a bus cost to carry, not a veto | measured (analog) | False |
| flow-measurement capability at 0.10 mg/s | measurable, but not yet to < 1 %: at FS 0.2 mg/s the conservative catalog class for that range (+/-2 % FS) gives 4 % spec-only (0.22 kg over 15,000 h, about 0.5 % of the 40 kg requirement); < 1 % needs the standard class demonstrated on Xe (a procurement requirement) AND the zero terms removed by a per-block installed zero check (derived.flow_measurement_headline) - a measurement-quality item, not a veto | model-derived | False |

## 10. M16 rows (proposed execution states)

| subsystem (A5) | role | proposed state | blocking item | rollup |
|---|---|---|---|---|
| shielded Xe-fed LaB6 hollow cathode | primary | BLOCKED | HWQ-09: C-1 type and emission rating (owner confirmation + selection) - fixes keeper OD, heater power, ignition flow and self-heating current used by every PENDING row here | hardware-definition blocker |
| Xe metering (splits to ignition/transition feed and cathode feed) | contributes the cathode branch and flow-measurement specification | RUNNING | — | — |
| sensors/diagnostics | contributes C-1 diagnostics and flow metrology demands (H2-6 owns) | RUNNING | — | — |
| PPU/power distribution | contributes keeper/heater supply demands (H2-4 owns) | RUNNING | — | — |
| thermal control | contributes C-1 heat loads and nodes (H2-5 owns) | RUNNING | — | — |
| mechanical/structural interfaces | contributes the C-1 mount and envelope (H2-7 owns) | RUNNING | — | — |

## 11. H3 procurement inputs (specification level; published data as reference only)

- **H3-C1-01: C-1 LaB6 hollow cathode unit (+ spare; a sacrificial unit if the owner wants a destructive O-exposure test).** Long lead: True. Reference data: SITAEL HC1/HC3 (IEPC2017_365), JPL 0.63/1.5-cm LaB6 (IEPC2015_43), Joussot laboratory LaB6 (DOSSIER) - published reference only, no supplier contact.
  To order it needs:
  - emission range covering I_emit up to the 8.33 A bound plus keeper/interstage (HW-C1-02), with the lowest self-heating current the design allows (reported);
  - spot-mode minimum flow vs current curve on Xe (supplier data as reference);
  - heater power and time to ignition; keeper ignition voltage with heater;
  - keeper OD/length/mass envelope (feeds H2-1 bore, H2-7);
  - keeper/orifice/insulator material list (O compatibility, magnetic properties);
  - tube thermocouple point and pyrometer view (HW-C1-09); disassemblable (HW-C1-08);
- **H3-C1-02: cathode precision MFC (FS about 0.2 mg/s Xe) and start-range MFC (FS about 1 mg/s Xe), Xe-calibrated.** Long lead: False. Reference data: BRONKHORST_ELFLOW_SELECT catalog (reference only; not a selection).
  To order it needs:
  - Xe calibration by the manufacturer at the stated reference conditions, with the sccm/normal-unit convention (ideal or real gas, reference temperature) named (derived.sccm_convention);
  - accuracy class +/-(0.5 % Rd + 0.1 % FS) or better demonstrated ON Xe at FS about 0.2 mg/s (about 2 sccm Xe); the catalog's lowest-range model is only +/-2 % FS, so the supplier's Xe statement for this range is the order criterion;
  - readout and setpoint resolution <= 0.0005 mg/s (PROPOSED, H22-52);
  - digital setpoint communication (catalog turndown 1:187.5 digital vs 1:50 analog);
  - repeatability < 0.2 % Rd;
  - zero temperature coefficient and attitude sensitivity stated;
  - vacuum-rated outlet, metal seals preferred, He leak spec stated;
- **H3-C1-03: gravimetric calibration kit (small Xe cylinder, balance, fixture) and a constant-volume calibrator.** Long lead: False. Reference data: W4 REF-SNYDER2017 practice.
  To order it needs:
  - balance capacity above cylinder + fixture and readability per derived.gravimetric_calibration;
  - calibrator volume known to the uncertainty budget;
- **H3-C1-04: cathode-branch valves, filter, dielectric break, pressure transducer.** Long lead: False. Reference data: none accessed.
  To order it needs:
  - Xe service, cleanliness class TBD (H2-3);
  - break voltage PENDING H2-4;
- **H3-C1-05: keeper (DC + pulse) and heater supplies (PS-C).** Long lead: False. Reference data: IEPC2017_365 p. 4 lab supplies (reference only).
  To order it needs:
  - IFD-04, IFD-05;

## 12. H4 test inputs

| closes | stage | measure |
|---|---|---|
| H22-10/H22-11/H22-12 (field at the orifice) | S1a | B map at the C-1 orifice at the operating coil currents (M0); C-1 characterization inside that field |
| H22-17/H22-25 (self-heating current, keeper mode) | S1a | C-1 minimum discharge current without keeper and heater; keeper current needed below it |
| H22-16/H22-21/H22-22/H22-23 (heater, keeper) | S1a | heater power and time to ignition; keeper ignition voltage; start log per start (AOL-CX-02) |
| H22-43..H22-49, H22-52, H22-53 (flow measurement) | S1a | gravimetric Xe calibration of both ranges installed (demonstrates or refutes the standard class on Xe); rate-of-rise cross-check; zero vs orientation and temperature; setpoint resolution and the lowest flow at which the calibrated accuracy is still acceptable |
| H22-12 (field transient) | S1a | keeper voltage/current of the lit C-1 through magnet turn-on at the operating coil currents (CATHODE_IGNITION -> XE_DISCHARGE_IGNITION) |
| H22-50 (mdot_cathode) | S1a + Phase 1 | spot-mode minimum Xe flow vs emission current with an atmospheric anode feed (D-CX-03); plume-mode onset by keeper-voltage oscillation |
| H22-38 (cathode-to-ground potential) | S1 / every reading | cathode-to-ground and coupling voltage (HW-C1-05) |
| H22-01 position reproducibility | S1b | C-1 position after remount; daily Xe reference (AOL-CX-01) |
| H22-06/H22-07/H22-08 (shielding) | Phase 1 | near-cathode RGA partial pressures, hot-emitter O-exposure log, emitter/tube temperature, drift of the daily Xe reference |
| H22-51 (Xe per start) | S1a + Phase 1 | integrated Xe per start per phase (purge, conditioning, ignition) |
| H22-09 (keeper material) | post-campaign | keeper/insert/orifice inspection (HW-C1-08) and coupons (HW-C1-06) |

## 13. Milestones

- **A:** supported: C-1 integration is conditionally closable - 'the architecture holds provided C-1 sustains spot mode at <= the Xe flow the ledger can afford, keeps its emission/keeper drift inside the pre-registered band under O-bearing operation, and restarts within the keeper capability'.
- **B:** needs the H4 measurements (D-CX-01..04), the H2-1 field at the orifice, the C-1 selection (HWQ-09) and the Xe ledger closed with the measured flow.
- **C:** needs the flight C-1 design (heater/keeper qualification, start cycles G05, wear/life G04), the flight flow restrictor sized from measurement, thermal and vibration closure of the mount.

## 14. Owner questions

- **H22-OQ-01:** Confirm L-CENTRAL as the PRELIMINARY C-1 location (L-EXTERNAL as the alternative if H2-1 cannot provide the inner-core bore).
- **H22-OQ-02:** Require a pulsed keeper ignition capability (300-600 V) in PS-C?
- **H22-OQ-03:** Two isolation valves in series on the flight cathode branch?
- **H22-OQ-04:** Resistor value and switching for the cathode-common tie to facility ground / spacecraft common.
- **H22-OQ-05:** Flow step (PROPOSED 0.005 mg/s) and stopping rule for the spot-mode minimum-flow search.
- **H22-OQ-06:** Purge flow and purge duration rule before heating, and the bound on the ignition-flow dwell (together they set Xe per start; bound rows at 1 mg/s).
- **H22-OQ-07:** Keeper material (graphite vs an O-resistant alternative) given the O-chemistry warning.
- **H22-OQ-08:** Adopt the PROPOSED emitter temperature floor of 1843 K during O-bearing operation?

## 15. Sources

- **GK2008.** D. M. Goebel and I. Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL Space Science and Technology Series, JPL / Wiley, 2008. https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf. open full text, read by this lane 2026-09-27 (same file as lane 19 records). sha256 `a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e`.
- **IEPC2015_43.** D. M. Goebel and J. E. Polk, 'Lanthanum Hexaboride Hollow Cathode for the Asteroid Redirect Robotic Mission 12.5 kW Hall Thruster', IEPC-2015-43/ISTS-2015-b-43, Kobe, 2015. https://electricrocket.org/IEPC/IEPC-2015-43_ISTS-2015-b-43.pdf. open full text, read by this lane 2026-09-27; page = printed page number. sha256 `6f5873d4ca95496714d427b0bdb568f57043d601085d2bd8f8d5b718829e1501`.
- **IEPC2017_365.** D. Pedrini, F. Cannelli, C. Tellini, C. Ducci, T. Misuri, F. Paganucci and M. Andrenucci, 'Hollow Cathodes for Low-Power Hall Effect Thrusters', IEPC-2017-365, Atlanta, 2017. https://electricrocket.org/IEPC/IEPC_2017_365.pdf. open full text, read by this lane 2026-09-27; values from text, figures not digitized. sha256 `d98374b080642877ed0b2aa2428173b104fa4ff4a633c6dc523203c5b6f81cf6`.
- **HOFER2008.** R. R. Hofer et al., 'Effects of Internally Mounted Cathodes on Hall Thruster Plume Properties', IEEE Trans. Plasma Sci. 36(5), Oct. 2008, starting p. 2005 (last page to verify), doi:10.1109/TPS.2008.2000962 (DOI printed on the first page of the file). http://richard.hofer.com/pdf/hofer_ieeetps_2008.pdf. author-hosted full text at an open URL, read 2026-09-27; nothing bypassed; co-author list and page range to verify against the journal record. sha256 `43661dd3f457b6c6f442aad6d9b0b35130ed1d459ff293fb2f1880e8bb82cb04`.
- **BRONKHORST_ELFLOW_SELECT.** Bronkhorst High-Tech, 'EL-FLOW Select: Digital Thermal Mass Flow Meters and Controllers for Gases', product catalog (8 pages). https://products.bronkhorst.com/media/cp3lfvo1/el-flow-select_en.pdf. public manufacturer catalog downloaded 2026-09-27; REFERENCE ONLY for the specification level (no supplier contact, no selection, no quotation). sha256 `69e5a7654f03758b6b9939366a5113a9669c083fd84f0d18f6b3009d5428f296`.
- **LANE19.** CATHINT lane 19 data file (transcriptions of IEPC-2017-276, IEPC-2017-377, G&K and SITAEL values with locators). docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json. repository deliverable (read only).
- **DOSSIER.** Cathode evidence dossier v1 (Joussot 2017, Zschaetzsch 2022 and G&K Sec. 6.8.5 transcriptions). docs/evidence/cathode/cathode_evidence_v1.json. repository deliverable (read only).
- **AOL5.** AO/lifetime register v5. docs/experiments/lifetime_ao/ao_lifetime_register_v5.json. repository deliverable (read only).
- **W4.** W4 instrumentation definition v1 (records REF-SNYDER2017, Snyder et al., J. Propul. Power 33(3) 2017, doi:10.2514/1.B35644, read by W4). docs/experiments/instrumentation/instrumentation_definition_v1.json. repository deliverable (read only).
- **HWDEF.** W3 common-hardware definition (H-1, MC-1, C-1, FS-C, PS-C, SVC-1, PIM-*). docs/experiments/hardware/hardware_requirements_v1.json. repository deliverable (read only; DRAFT_PENDING_OWNER).
- **XEL.** Parametric Xe ledger v1 (verified, T_A5_XE_LEDGER). docs/budgets/xe_ledger/xe_ledger_v1.json. repository deliverable (read only).
- **CONTROLS.** Dual-feed state machine v1 (state names). schemas/controls/dual_feed_state_machine_v1.json. repository deliverable (read only).
- **A5.** Owner addendum A5. docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json. immutable owner decision (pinned).
- **A7.** Owner addendum A7. docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json. immutable owner decision (pinned).

Reproduce:

```
python docs/hardware/h2/h2_2_cathode_integration/build_h2_2_cathode_integration.py --check
python -m pytest -q tests/test_h2_2_cathode_integration.py
```
