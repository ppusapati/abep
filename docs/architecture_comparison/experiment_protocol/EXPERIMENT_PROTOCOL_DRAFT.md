# Hall-only vs RF + Hall vs ECR + Hall: common-condition experiment protocol (DRAFT)

| | |
|---|---|
| status | **DRAFT_PENDING_OWNER**: a proposal for the project owner, not an owner decision. Nothing here is registered. |
| machine-readable form | [`protocol_draft.json`](protocol_draft.json), schema [`protocol.schema.json`](protocol.schema.json) |
| tools | [`protocol_tools.py`](protocol_tools.py): `--check` validates, recomputes derived values and checks the register below; `--write-md` regenerates it |
| test | `tests/test_architecture_experiment_protocol.py` |
| bus-power boundary | `bus_power_boundary_v1` (defined by a separate lane in `abep_sim/arch_boundary.py`; referenced by name only, not imported) |
| base commit | `daa0e759e26416847f200a4781194f266be27c5c` |

The JSON is authoritative for every value; any difference between this text and the JSON is a defect in the text.

## 0. What this protocol is, and what it does not claim

This protocol defines how to compare three ionization architectures that feed **the same Hall acceleration stage**:
Hall-only, an RF pre-ionizer + Hall, and an ECR (microwave) pre-ionizer + Hall. The pre-ionizer is the **only**
change. Every consumer is accounted at **one DC input bus boundary** that is identical for all three arms.

It does **not** claim:

- which architecture performs better. It defines the measurement and the classification rules, nothing more.
- any simulator prediction of arm differences. The Hall transport credible set is empty and gate 3 is FAIL, so the
  repository cannot currently predict absolute Hall performance. The withdrawn 0-D closure results (including every
  pre-ionizer trade number in docs/HISTORY.md) are not quoted or used. The repository's mechanism-level expectation
  that RF/helicon pre-ionizers "add nothing" (CLAUDE.md) is a model hypothesis that this experiment is designed to be
  able to confirm or contradict. It is not a prior that the protocol assumes.
- demonstrated ABEP closure, an architecture selection or any transport admission.
- anything about the P5-N2 v1 validation. That outcome is final and is not re-scored, re-labelled or re-interpreted.

Results of this experiment would be **evidence level 1** (in-house measurement on Vyovrinda hardware, docs/EVIDENCE.md).
Direct readings are *measured*; quantities computed from them (utilization, efficiencies, bus-side power reconstructed
through a converter efficiency) are *inferred* or *reconstructed*, each with its transformation chain.

## 1. Scope

The experiment covers the **ionization/discharge → acceleration/thrust** block of the RFP architecture. It starts at the
valve outlets. The atmospheric path upstream (intake → filter → compressor → atmospheric gas chamber → valve) and the Xe
chamber are replaced by laboratory gas supplies and are outside the experiment.

Out of scope, and declared as limitations:

- **Atomic oxygen.** Bottled O2/N2 mixtures cannot reproduce intake-delivered atomic O. The mixtures are not claimed
  to be a surrogate for it.
- Intake, compressor and spacecraft performance. The upstream ICD supplies the delivered flow and composition.
- Life and erosion (a separate test). Any change to the Hall geometry between arms. Any new propulsion family (CLAUDE.md rule 8).

## 2. Arms, controls and hardware configurations

| arm | pre-ionizer | only change vs HALL_ONLY |
|---|---|---|
| `HALL_ONLY` (reference) | none energized | none |
| `RF_HALL` | RF (inductive/helicon class; topology is a hardware decision). Frequency, DC-input power levels and feed topology are TBD | RF pre-ionizer energized (in CFG-B, also its applicator installed) |
| `ECR_HALL` | ECR microwave, resonance at B_res = 2π f m_e / e. Frequency, DC-input power levels and feed topology are TBD | ECR pre-ionizer energized (in CFG-B, also its applicator and resonance magnets installed) |

Each pre-ionizer arm runs at the pre-registered set of DC-input power levels. The set includes zero and at least
`preionizer_nonzero_levels_min` non-zero levels (PROPOSED), so the result is a dose-response, not a single point.

**Hardware configurations** (owner chooses after a feasibility review):

- **CFG-A, integrated article (PROPOSED preferred).** Both applicators are installed on one test article, and arms are
  switched electrically without venting. `HALL_ONLY` is then "both applicators installed, unenergized". This lets arms be
  randomized inside a pump-down and keeps the gas path and magnetic circuit physically identical. The risk is mutual
  interference between the applicators.
- **CFG-B, separate builds (PROPOSED fallback).** The bare Hall, RF + Hall and ECR + Hall builds are separated by vents.
  CFG-B needs the sham controls below and replicate builds to separate reassembly variance.

**Controls** (all PROPOSED):

| control | what it separates |
|---|---|
| `SHAM_RF`, `SHAM_ECR` | Applicator installed but not energized (CFG-B). This separates the effect of the hardware (gas path, volume, surfaces, resonance magnets) from the effect of energizing it. In CFG-A, `HALL_ONLY` is this control for both applicators. |
| `DUMMY_LOAD_PICKUP` | Each generator drives a matched dummy load (no plasma, no flow) at every power level while all common diagnostics record. Repeated in every pump-down. This quantifies electromagnetic pickup. |
| `XE_HEALTH_CHECK` | `HALL_ONLY` at the Xe reference point at the start and end of every day. This detects drift of the channel, cathode, thrust stand and diagnostics. |

## 3. Common conditions: the invariants

Every invariant is verified and logged at every operating point. Each tolerance is a PROPOSED threshold whose value is
TBD until the owner fixes it.

| id | invariant | verification | proposed tolerance |
|---|---|---|---|
| INV-PROP | same propellant composition to the discharge (same certified premix lot, or the same calibrated per-species controllers) | certificate / MFC logs | `inv_prop_tol` (TBD) |
| INV-FLOW | same m_dot_prop = m_dot_a + m_dot_p and same m_dot_c, set by the same calibrated controllers; split fixed per arm | MFC logs, in-situ flow verification | `inv_flow_tol` (TBD) |
| INV-CHANNEL | same serial-numbered channel, anode and distributor | serials, dimensional inspection before and after | `inv_channel_tol` (TBD) |
| INV-MAG | same magnet hardware and coil currents; B(z) mapped in every configuration with every pre-ionizer magnet installed | Gauss-probe map | `inv_mag_peak_tol`, `inv_mag_loc_tol` (TBD); a miss makes the comparison CONFOUNDED_MAGNETIC |
| INV-VD | same V_d set points, constant-voltage mode at the thruster terminals; flow never adjusted by I_d feedback | V_d log | `inv_vd_tol` (TBD) |
| INV-CATH | same Xe-fed LaB6 hollow cathode (serial), position, Xe flow, heater/keeper settings and electrical configuration | cathode-to-ground and keeper voltage logs | `inv_cath_drift` (TBD) |
| INV-FAC | same chamber, pumps, thruster position and reference gauges; compare arms only at matched reference pressure | p_ref log, gauge calibrations | `inv_fac_tol` (TBD) |
| INV-DIAG | same instruments, positions, calibrations and reduction code; arm-specific monitors are additive and shown non-perturbing | serials/positions per pump-down; DUMMY_LOAD_PICKUP | `inv_diag_pickup` (TBD) |
| INV-ELEC | same grounding/floating scheme, cabling, filters and supplies | checklist and photographs | none |
| INV-THERM | same thermal-settling criterion before any point is recorded | thermocouples | `inv_therm_rate` (TBD) |
| INV-BUS | the same **declared laboratory subset** of `bus_power_boundary_v1` in every arm: same component list (mapped to v1 ids), measurement points and instrument classes; the compressor row is ABSENT_IN_LAB in every arm and reconstructed from the upstream ICD (§5) | one row per component per point | none (a missing row excludes the point) |

The cathode is a Xe-fed LaB6 hollow cathode. That follows the task definition and the repository's default neutralizer
`lab6_xe` (`abep_sim/archengine.py`); the owner confirms it.

## 4. Flow accounting

| symbol | meaning |
|---|---|
| m_dot_a | propellant to the Hall anode/gas distributor |
| m_dot_p | propellant injected into the pre-ionizer (0 in HALL_ONLY; equals m_dot_prop for a series feed) |
| m_dot_prop | m_dot_a + m_dot_p: **matched between arms** |
| m_dot_c | Xe to the LaB6 cathode: **matched between arms** |
| m_dot_tot | m_dot_prop + m_dot_c: the denominator of every efficiency and utilization |
| m_dot_transient | any ignition or conditioning puff on any line, reported with the ignition metric |

Rules:

- Every line has its own calibrated controller and logged reading.
- Controllers are calibrated **on each working gas and mixture, in the final configuration**. Calibrations are traceable
  to a national metrology standard and fall within the interval `mfc_calibration_interval` (REF-SNYDER2017 Sec. IV
  and VI).
- Facility-ingested background gas is never added to m_dot_tot. It is characterized by the reference pressure and the
  background-pressure sweep (§9).

## 5. Bus-power boundary (`bus_power_boundary_v1`)

**Boundary point.** The DC input bus. Every consumer is measured at its input terminals from the common DC bus, at the
bus voltage `bus_voltage` (TBD from the spacecraft EPS ICD). The preferred laboratory setup feeds all consumers from one
DC bus supply through breadboard or flight-like converters. It has a main-bus meter and one branch meter per component.
Where a laboratory supply replaces a bus-fed converter, bus-side power is **reconstructed** as P_out / eta_conv. Here
eta_conv is measured for that converter at that load, and the value is labelled *reconstructed*.

The **same component list applies to all three arms**. The test enforces this: each arm's `component_ids` must equal
the list below. Each row maps name by name onto the component identifiers of `bus_power_boundary_v1`
(`abep_sim/arch_boundary.py`, `COMMON_COMPONENTS` and `PREIONIZER_COMPONENTS`; referenced by name, never imported), and
every v1 identifier is covered exactly once.

| component id | v1 component id(s) | consumer | inside the boundary |
|---|---|---|---|
| `hall_ppu_input` | `hall_discharge` | Hall PPU (discharge converter) DC input | conversion loss, output filter, cabling to the thruster; V_d and I_d are also recorded to report eta_conv |
| `magnet_supplies` | `hall_magnet`, `ecr_magnet` | magnet supplies DC input | two separately metered sub-items, one per v1 id: Hall coil supplies (`hall_magnet`) and ECR resonance-field coil supplies (`ecr_magnet`, recorded in every arm, ABSENT or measured standby outside ECR_HALL); 0 W rows for permanent magnets are still reported |
| `rf_generator_input` | `rf_source` | RF generator DC input | generator loss, matching network and RF cable losses. Forward/reflected power is a diagnostic only. An RF-applicator DC field coil, if the design has one, has no separate v1 id; this draft books it as a metered sub-item here (mapping proposal for the owner) |
| `microwave_source_input` | `ecr_source` | microwave source DC input | source loss, isolator/circulator, tuner, waveguide/coax and window losses. Forward/reflected power is a diagnostic only |
| `cathode_heater` | `cathode_heater` | cathode heater supply DC input | converter loss. Steady state is reported separately from start-up energy |
| `cathode_keeper` | `cathode_keeper` | cathode keeper supply DC input | converter loss |
| `valves_flow_control` | `flow_control` | valves and flow control DC input | valve drivers and controllers on the anode, pre-ionizer and cathode lines. Laboratory-only controller power is a flagged sub-item |
| `compressor` | `compressor` | gas-path compressor motor-drive DC input | **ABSENT_IN_LAB in every arm** (the laboratory feed starts at the valve outlets). Explicitly unavailable from the experiment; reconstructed from the upstream ICD (`compressor_bus_power`, TBD) |
| `thermal_control` | `thermal_control` | thermal control DC input | heaters and active cooling the flight system would power (thruster, pre-ionizer, PPU) |
| `housekeeping` | `housekeeping` | housekeeping DC input | control, telemetry and sensor electronics of the propulsion string |

**Declared laboratory subset.** The laboratory measures `bus_power_boundary_v1` **minus the compressor**:
P_bus,lab is a *partial-boundary* total and is labelled PARTIAL_BOUNDARY wherever it appears. The compressor row is
carried in every arm with presence ABSENT_IN_LAB. Its bus draw depends on the total flow and composition at the point,
which are identical across arms, and it is **reconstructed** from the upstream ICD (evidence class *reconstructed*, with
the ICD revision and its uncertainty). It is never a placeholder and never taken as zero. When the ICD supplies it,
P_bus,v1 = P_bus,lab + P_compressor,ICD; otherwise P_bus,v1 is UNAVAILABLE. The omission is the same in all arms, but
a common additive term in the denominators does not cancel in the paired ratios of M1 and M2: it moves them. So
partial-boundary ratios are never reported as `bus_power_boundary_v1` ratios (§13).

- **Presence rule.** Every row is recorded for every arm at every point. An absent component is recorded as 0 W,
  presence ABSENT. An installed but unenergized component is **measured** for its standby draw, never assumed zero.
  A missing row makes P_bus,lab (and P_bus,v1) undefined, and the point becomes `EXCLUDED_MISSING_BOUNDARY_COMPONENT`. No
  placeholder is ever filled in.
- **Totals.** P_bus,lab is the sum over all components measured in the laboratory (partial boundary). P_bus,v1 adds
  the reconstructed compressor draw when the ICD supplies it. The per-component breakdown, per v1 id, is reported for
  every point and arm.
- **Facility services disclosure.** Some generators, applicators, magnets or PPUs may be cooled by facility water or
  gas. That heat load is reported per arm, outside the boundary, because in flight the thermal subsystem would have to
  reject it. Facility pumping and laboratory instrumentation are excluded identically for all arms.
- **Ledger check (THR-LEDGER, PROPOSED).** The residual is |P_main − Σ branch| / P_main, and it must not exceed
  `ledger_residual_max`. That value is the simulator's energy-ledger gate from CLAUDE.md rule 4, proposed here for the
  experimental ledger.
- **Uncertainty target (THR-UNC-BUS, PROPOSED).** The expanded relative uncertainty of P_bus,lab (and of P_bus,v1, including the ICD
  compressor uncertainty, when it is formed) must not exceed
  `bus_unc_ratio` × delta_m1. Instruments are DC power-analyzer channels with traceable calibration, 4-wire voltage
  sensing at the consumer input, simultaneous V and I sampling, and a bandwidth that covers converter ripple.

**Consistency with `abep_sim/arch_boundary.py`.** That module did not exist at the base commit; it is defined by a
separate lane (sibling commit `a2a1396`). `protocol_tools.py` carries a transcribed copy of the v1 component ids and
checks the mapping above: every v1 id covered exactly once, and every v1 component required for an arm's architecture
recorded in that arm. The test parses the module source with `ast` (never imports or executes it), from
`abep_sim/arch_boundary.py` when merged or otherwise from the sibling commit when that git object is reachable, and
compares `BOUNDARY_VERSION`, `COMMON_COMPONENTS` and `PREIONIZER_COMPONENTS` with the transcribed copy.

## 6. Diagnostics (identical for all arms)

| id | quantity | instrument and practice |
|---|---|---|
| DIAG-THRUST | T | Pendulum-type stand with **end-to-end in-situ calibration of the whole installation** (REF-POLK2017 Sec. IV). This protocol applies that principle to the RF cables, waveguide or coax that cross the stand interface; that application is XPROT's, not a statement of the source. At least `thrust_cal_before_min` calibrations before and `thrust_cal_after_min` after (REF-POLK2017 Sec. V.A). Zero is taken with the thruster off, thermocouples track drift (Sec. VI.B) and the uncertainty budget is reported (Sec. VI.C, VII). Target THR-UNC-THRUST (PROPOSED) |
| DIAG-DISCHARGE | V_d, I_d (DC and time-resolved), cathode-to-ground, keeper, coil currents | Calibrated meters plus a high-bandwidth current probe. The sampling rate `discharge_sampling_rate` is TBD from the Hall-only pilot and is the same for all arms |
| DIAG-FARADAY | beam current I_b, divergence | Faraday-probe sweep per REF-BROWN2017 (metadata only accessed: verify corrections before pre-registration) |
| DIAG-EXB | species/charge fractions (N2+, N+, O2+, O+, NO+ if present, multiply charged, cathode Xe+) | E×B probe or equivalent. Analysis per REF-SHASTRY2009 (metadata only: verify). Resolution `exb_resolution` TBD |
| DIAG-IEDF | ion energy distribution | Retarding potential analyzer. No recommended practice located by this lane (open item) |
| DIAG-PRESSURE | reference background pressure p_ref | Hot-cathode ionization gauges calibrated **on each working gas and mixture** with their controller, cabling and feedthrough (REF-DANKANICH2017 Sec. III). Mounted near the chamber wall at the thruster exit plane (Sec. IV.A), at least `gauge_offset_chamber_radii_min` chamber radii from the centreline and `gauge_distance_thruster_min` m from the thruster outer diameter. Sampled at ≥ `pressure_sampling_min` Hz and averaged over `pressure_average_window` s. Readings are taken ≥ `pressure_settle_min` min after a flow change larger than `pressure_settle_flow_change`. Calibration interval `gauge_calibration_interval` months or `gauge_calibration_hours` h, whichever comes first. Radial asymmetry under THR-PRESSURE-ASYM. The O2/N2 gas correction `gauge_correction_o2n2` is TBD by calibration |
| DIAG-FLOW | m_dot_a, m_dot_p, m_dot_c | §4 (REF-SNYDER2017) |
| DIAG-BUS | per-component DC input power, P_main | §5 |
| DIAG-TEMP | stand, thruster, applicator, PPU temperatures | Thermocouples for INV-THERM and drift correction |

Arm-specific monitors are **additive only**: RF and microwave forward/reflected power, and the pre-ionizer chamber
pressure if a port exists. They feed stability metric S5 and diagnostics. They never substitute for the DC input power.

## 7. Test matrix

Operating-point values are **parameters**. Values the upstream ICD must supply are TBD and **are not invented here**.

| factor | levels | value source |
|---|---|---|
| F-PROP propellant | Xe reference; N2; O2/N2 mixtures | Xe point: owner. N2 purity: owner. **Mixture compositions: upstream ICD** (composition delivered at the valve outlet across the RFP altitude envelope and solar conditions) |
| F-MDOT m_dot_prop | TBD | **upstream ICD** (delivered mass-flow range). Must include the lowest ICD-delivered flow |
| F-MDOTC m_dot_c | TBD | LaB6 cathode specification; identical in all arms |
| F-VD V_d | TBD | Hall design envelope (owner) |
| F-MAG magnet setting | TBD | Hall magnetic design; fixed across arms |
| F-PREP pre-ionizer DC input power | TBD, includes zero | RF and ECR designs |
| F-PBG background pressure | base + elevated levels, TBD | facility characterization (§9) |

The primary matrix is F-PROP × F-MDOT × F-VD at base background pressure, for every arm, and for the sham controls in
CFG-B, with each pre-ionizer at each non-zero power level. The background-pressure sweep and the minimum-flow search run
on a pre-registered subset of points (owner). A full factorial is not required.

## 8. Design: order, randomisation, replication

- **Within a day.** Propellant blocks run in the fixed order Xe reference → N2 → O2/N2. Oxygen can change cathode and wall
  surfaces irreversibly, so oxygen-containing points are not interleaved with the others. Inside a block, the operating
  points are shuffled. In CFG-A, the arm order is also shuffled inside every point, so drift cannot line up with arm.
- **Between builds (CFG-B).** The build order is balanced over replicate builds. Each build is installed at least twice,
  and the HALL_ONLY build is revisited between test-arm builds.
- **Algorithm.** `protocol_tools.randomized_schedule` generates the order deterministically from a seed
  (`schedule_seed`), which is drawn and recorded at pre-registration.
- **Replication.** A replicate is an independent visit, separated by a thruster shutdown and restart (in CFG-B,
  preferably a re-installation). There are at least `replicates_min` replicates per (arm, point) (PROPOSED). The final
  count comes from a power analysis on the Hall-only pilot variance.
- **Drift controls.** XE_HEALTH_CHECK, thrust-stand calibrations before and after each sequence, and randomized arm order.
- **Blinding (PROPOSED).** The analysis pipeline is frozen and runs on coded arm labels. The labels are decoded only
  after the per-metric classification exists.
- **Conditioning.** The same pre-registered sequence (bake-out, cathode activation, Hall conditioning on Xe) follows
  every vent, for all arms.

## 9. Facility-effect controls

The background pressure is raised by injecting the **same working gas** downstream of the thruster. At least one pumping
surface lies between the injection point and the gauge, and the injection point is at least `pbg_injection_distance_min`
m downstream of the exit plane or, preferably, near the facility centreline. The baseline is taken at maximum facility
pumping capability (REF-DANKANICH2017 Sec. IV.B). There are at least `pbg_elevated_levels_min` elevated levels above the
base level (PROPOSED).

- Each metric is regressed on p_ref for every arm, and the arm × pressure interaction is reported.
- Suppose an arm difference at base pressure changes sign or classification within the swept range. It is labelled
  **FACILITY_SENSITIVE** and is not carried forward as a vacuum-representative result.
- Extrapolation to zero pressure is a secondary, model-based analysis, labelled *reconstructed*.
- **Never crossed.** Paired comparisons are made only at matched p_ref (THR-INV-FAC). Results at different pressures are
  never compared directly.
- **Why the sweep is mandatory for every arm.** The P5-N2 reference data needed a facility ingestion correction
  (REF-BRABSTON2025, as audited in the repository). A pre-ionizer may change that sensitivity.

## 10. Ignition, sustainment and extinction

- **Ignition.** Each attempt follows the pre-registered start sequence: cathode heater, keeper, flows, pre-ionizer where
  applicable, then the discharge supply. An attempt succeeds if I_d reaches the steady window within `ignition_timeout`
  and stays sustained for `ignition_hold` (both TBD). Transient puffs are logged.
- **Extinction (THR-EXTINCTION, PROPOSED).** The rule has the same functional form as the simulation rule O1
  (`hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json`, key `operational_rules.O1_extinction_SUSTAINMENT`), so experiment and simulation share one definition.
  An extinction is uncommanded if **both** conditions hold. First, the mean I_d over the hold window is below
  `ext_mean_frac` × I_d,ref. Second, at least `ext_sample_share` of the samples are below `ext_sample_frac` × I_d,ref.
  I_d,ref is the median I_d of the preceding steady window, of length `ext_window` (TBD). A low but steady discharge is
  sustained. A single deep breathing trough is not an extinction.
- **Minimum sustained flow.** At fixed V_d and magnet setting, m_dot_prop is stepped down in steps of `min_flow_step`
  (TBD) with a pre-registered dwell, until extinction or the hardware limit. The lowest sustained step is m_dot_min.
  Extinctions are **data** (M6, S6), never exclusions.

## 11. Stability metrics

| id | metric |
|---|---|
| S1 | σ(I_d) / mean(I_d) over the steady window, in the pre-registered band |
| S2 | (max − min)(I_d) / mean(I_d) |
| S3 | dominant frequency of the I_d power spectral density in the band |
| S4 | thrust-signal standard deviation after drift correction |
| S5 | mean and σ of reflected/forward power (pre-ionizer arms; diagnostic) |
| S6 | uncommanded extinctions and mode transitions per hour, per arm and propellant |

## 12. Point statuses

Statuses in order of precedence:

1. `EXCLUDED_MISSING_BOUNDARY_COMPONENT`
2. `CONFOUNDED_MAGNETIC`
3. `EXCLUDED_INSTRUMENT` (a thrust-calibration shift or ledger residual beyond its threshold, or another instrument fault)
4. `EXCLUDED_FACILITY` (p_ref outside the matched band, a gauge fault, or asymmetry)
5. `NOT_IGNITED`
6. `NOT_SUSTAINED`
7. `VALID`

Excluded points are reported with their reason and are never deleted. NOT_IGNITED and NOT_SUSTAINED are outcomes, not
exclusions. Re-runs of excluded points go to the end of the same block, under the same randomization rule, with a
pre-registered cap.

## 13. Decision metrics and PROPOSED thresholds

Every threshold below is **PROPOSED** for the owner, with `decided_by: null`. Each comparison is a **paired ratio**:
arm vs HALL_ONLY, at the same point, on the same day, at matched p_ref.

| id | metric | role (PROPOSED) | PROPOSED classification rule |
|---|---|---|---|
| M1 | thrust per bus power, T / P_bus [mN/kW], on two labelled bases: PARTIAL (P_bus,lab) and V1 (P_bus,lab + P_compressor,ICD, only when the ICD supplies it). Only a V1-basis classification is a `bus_power_boundary_v1` result; a PARTIAL-basis one is always labelled PARTIAL_BOUNDARY | primary | HIGHER if the lower bound of the two-sided `confidence_level` CI of R exceeds unity by more than `delta_m1`. LOWER if the upper bound is below unity by more than `delta_m1`. Else NOT_DISTINGUISHED |
| M2 | beam ion current per bus power, I_b / P_bus [A/kW], on the same two labelled bases as M1 | secondary | as M1 with `delta_m2`, `confidence_level_m2` |
| M3 | mass utilization, η_m,tot = Σ_j (m_j / (q_j e)) I_b,j / m_dot_tot, with I_b,j = I_b Ω_j from E×B; η_m,prop reported alongside | secondary | as M1 with `delta_m3`, `confidence_level_m3` |
| M4 | stability (S1; S2–S6 reported) | secondary, non-inferiority | NOT_WORSE if the upper CI bound of the S1 ratio is ≤ unity plus `delta_m4`. WORSE if the lower bound exceeds it. Else NOT_DISTINGUISHED |
| M5 | ignition reliability | secondary | MEETS if the one-sided `ignition_confidence` Clopper–Pearson lower bound over `ignition_attempts` attempts is ≥ `ignition_p_min`. Else NOT_DEMONSTRATED |
| M6 | minimum sustained propellant flow | secondary | LOWER_MIN_FLOW if m_dot_min(arm) is below m_dot_min(HALL_ONLY) by ≥ `m6_steps` flow steps in every replicate. HIGHER_MIN_FLOW symmetrically. Else NOT_DISTINGUISHED |

All minimum effects of interest (`delta_m1`–`delta_m4`, `m6_steps`) are **TBD by the owner**. They are the changes that
would alter an architecture decision. They cannot be derived from the simulator while the Hall credible set is empty.

Reported but not classified: anode and bus-level total efficiency (T² / (2 m_dot_tot P_bus), on the same labelled bases), specific impulse
on m_dot_tot, divergence, ion acceleration voltage, species fractions, cathode coupling voltage, and the bus-power
breakdown.

## 14. RFP screens (informational)

These screens use the **partial laboratory boundary**, which has no intake or compressor. Passing one is necessary, not
sufficient, and failing one ranks nothing.

- SCR-THRUST-WINDOW: report whether `rfp_thrust_min` ≤ T ≤ `rfp_thrust_max` at the point.
- SCR-TP-FLOOR: report whether T / P_bus,lab > `rfp_thrust_per_power_floor` (PARTIAL_BOUNDARY), and T / P_bus,v1 when
  the ICD compressor draw is available. The floor is
  rfp_thrust_min / rfp_power_max, computed by `protocol_tools.py` from `abep_sim/constants.py`. An RFP-relevant point
  needs T ≥ rfp_thrust_min at total system power below rfp_power_max. The laboratory bus power cannot exceed the system
  power, so T / P_bus,lab must exceed the floor.

The RFP values are transcriptions recorded in the repository (`abep_sim/constants.py`, CLAUDE.md). This lane did not
re-read them from the RFP (verify).

## 15. Statistics

- **Unit of analysis.** Paired (arm, HALL_ONLY) visits on the same day at matched p_ref.
- **Intervals (PROPOSED).** A t-interval on replicate-level paired log-ratios, with a bootstrap over replicates as a
  cross-check.
- **Multiplicity (PROPOSED).** Holm step-down across the pre-registered primary family (M1 at every primary point and
  arm). Secondary metrics carry both unadjusted and adjusted intervals.
- **No aggregation.** There is no composite score and no single overall ranking. The output is the per-metric, per-point,
  per-arm classification table. Any aggregation rule must be pre-registered by the owner before measurement.
- **Ignition decision aid.** After n successes in n attempts, the one-sided lower bound at confidence c is
  (1 − c)^(1/n). The smallest n that demonstrates a target p is ⌈ln(1 − c) / ln p⌉. The register below lists n for three
  illustrative targets at `aid_confidence` (computed by `protocol_tools.py`). The targets are illustrations, not
  requirements. `clopper_pearson_lower` implements the general bound for the analysis.

## 16. Pre-registration: before any measurement

**No score-bearing measurement happens before the lock merges.** This mirrors the `hallthruster_bridge/prereg/` practice.

1. **PR-1.** The owner resolves every TBD and every PROPOSED item (accept, change or reject) and records the decision.
   Only an owner decision moves the status from DRAFT_PENDING_OWNER to REGISTERED.
2. **PR-2 (pilot, disclosed).** The Hall-only arm is used for repeatability and facility characterization. Pre-ionizer
   arms get **functional checkout only** (ignition, matching, dummy-load pickup), and no thrust, current or utilization
   metric is computed for them. Pilot data never enter the decision analysis.
3. **PR-3.** Freeze the protocol JSON (status REGISTERED), the analysis code, the schedule seed, the upstream-ICD revision
   and the list of calibration certificates. Write a sha256 lock file under `prereg/`, which is created only at this step.
4. **PR-4.** Merge the lock, then run the campaign.
5. **PR-5.** Any later change is a dated addendum that discloses what data had been seen. The lock is never edited.
6. **PR-6.** Raw data are frozen with sha256 before analysis. The classification table is produced by the frozen code,
   with coded arm labels.

## 17. Open items for the owner

- Choose CFG-A or CFG-B after a hardware feasibility review.
- Confirm the Xe-fed LaB6 cathode, its Xe flow, and the thruster/cathode electrical configuration.
- Set `delta_m1`–`delta_m4`, `m6_steps` and the confidence levels. Accept, change or reject every PROPOSED threshold and
  every adopted practice value.
- Obtain the upstream ICD revision for delivered flows and O2/N2 compositions.
- Decide the primary endpoint(s), the primary point family, and the subset of points for the pressure sweep and the
  minimum-flow search.
- Confirm the name-by-name mapping to `bus_power_boundary_v1` (in particular booking any RF-applicator DC field coil
  under `rf_source`), and re-run the test against `abep_sim/arch_boundary.py` once it merges.
- Confirm the declared laboratory subset (compressor ABSENT_IN_LAB, reconstructed from the upstream ICD) and obtain
  the ICD compressor bus draw per operating point.
- Verify the metadata-only references and locate an RPA recommended practice.
- Align with `docs/experiments/` if and when it exists (not present at the base commit).

## 18. References

| id | citation | access |
|---|---|---|
| REF-POLK2017 | Polk, Pancotti, Haag, King, Walker, Blakely, Ziemer, "Recommended Practice for Thrust Measurement in Electric Propulsion Testing", J. Propuls. Power 33(3), 539–555, 2017, doi:10.2514/1.B35564 | full text (PubMed Central author manuscript, PMC7839308) |
| REF-DANKANICH2017 | Dankanich, Walker, Swiatek, Yim, "Recommended Practice for Pressure Measurement and Calculation of Effective Pumping Speed in Electric Propulsion Testing", J. Propuls. Power 33(3), 668–680, 2017, doi:10.2514/1.B35478 | full text (open PDF, Georgia Tech HPEPL) |
| REF-SNYDER2017 | Snyder, Baldwin, Frieman, Walker, Hicks, Polzin, Singleton, "Recommended Practice for Flow Control and Measurement in Electric Propulsion Testing", J. Propuls. Power 33(3), 556–565, 2017, doi:10.2514/1.B35644 | full text (open PDF, Georgia Tech HPEPL) |
| REF-BROWN2017 | Brown, Walker, Szabo, Huang, Foster, "Recommended Practice for Use of Faraday Probes in Electric Propulsion Testing", J. Propuls. Power 33(3), 582–613, 2017, doi:10.2514/1.B35696 | metadata only (Crossref); the open repository copy returned HTTP 403 and was not bypassed. Verify |
| REF-SHASTRY2009 | Shastry, Hofer, Reid, Gallimore, "Method for analyzing E×B probe spectra from Hall thruster plumes", Rev. Sci. Instrum. 80, 2009, doi:10.1063/1.3152218 | metadata only (Crossref). Verify |
| REF-SHABSHELOWITZ2014 | Shabshelowitz, Gallimore, Peterson, "Performance of a Helicon Hall Thruster Operating with Xenon, Argon, and Nitrogen", J. Propuls. Power 30, 664–671, 2014, doi:10.2514/1.B35041 | metadata only; the open copy returned HTTP 403 and was not bypassed. No result from it is used. Context only |
| REF-BRABSTON2025 | Brabston et al., J. Propuls. Power 2025, doi:10.2514/1.B39623 | repository record (`hallthruster_bridge/identification/brabston_p5_n2_measurement_audit_v1.json`) |

## Appendix A: numeric register (generated from the JSON)

Every number in the protocol carries a source and an evidence class. Every open value is TBD and says what it
requires. Every recommended-practice value is an **adopted** value, class *assumed*, whose adoption is PROPOSED. Every
RFP value is a repository transcription. The derived values are recomputed by the tools script and the test.

<!-- BEGIN GENERATED: numeric_register (protocol_tools.py --write-md) -->

Numeric values (41), each with source and evidence class:

| id | value | unit | status | evidence class | source |
|---|---|---|---|---|---|
| `mfc_calibration_interval` | 12 | months (maximum) | PROPOSED | assumed | REF-SNYDER2017 Sec. VI (paraphrase: calibrations traceable to NIST, performed at least every twelve months over the entire flow scale) |
| `ledger_residual_max` | 0.02 | fraction | PROPOSED | assumed | CLAUDE.md rule 4 (architecture energy-ledger residual < 2 % for the simulator); adoption for the experimental ledger is a proposal |
| `bus_unc_ratio` | 0.25 | fraction of delta_m1 | PROPOSED | assumed | XPROT draft proposal, analogous to the common 4:1 test-uncertainty-ratio convention (from memory - verify); not derived from data |
| `thrust_cal_before_min` | 10 | calibrations (minimum) | PROPOSED | assumed | REF-POLK2017 Sec. V.A ('Perform a minimum of ten calibrations to generate a calibration curve') |
| `thrust_cal_after_min` | 10 | calibrations (minimum) | PROPOSED | assumed | REF-POLK2017 Sec. V.A ('Perform a minimum of ten calibrations after thruster operation') |
| `thrust_unc_ratio` | 0.25 | fraction of delta_m1 | PROPOSED | assumed | XPROT draft proposal (same ratio as THR-UNC-BUS); not derived from data |
| `gauge_offset_chamber_radii_min` | 0.6 | chamber radii from the centreline (minimum) | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('at least 0.6 chamber radii away from the centerline') |
| `gauge_distance_thruster_min` | 1 | m from the thruster outer diameter (minimum) | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('at least 1 m from the outer diameter of the thruster') |
| `pressure_settle_min` | 2 | min (minimum) after a commanded flow change greater than the fraction below | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('no less than 2 min after a commanded flow-rate change greater than 10%') |
| `pressure_settle_flow_change` | 0.1 | fraction of commanded flow | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A |
| `pressure_sampling_min` | 10 | Hz (minimum) | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('The sampling rate should be no less than 10 Hz') |
| `pressure_average_window` | 3 | s | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('pressure should be measured as the 3 s average value') |
| `gauge_calibration_interval` | 12 | months (maximum; or the operating-hour limit below, whichever is less) | PROPOSED | assumed | REF-DANKANICH2017 Sec. III ('the lesser of 12 months or 2000 h of noncontinuous operation') |
| `gauge_calibration_hours` | 2000 | h of noncontinuous operation (maximum) | PROPOSED | assumed | REF-DANKANICH2017 Sec. III |
| `pressure_asym_max` | 0.2 | fraction | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.A ('Asymmetric pressure variation should be less than 20%') |
| `replicates_min` | 3 | replicates per (arm, point) | PROPOSED | assumed | XPROT draft proposal; the final count follows a power analysis on Hall-only pilot variance (TBD) |
| `preionizer_nonzero_levels_min` | 2 | non-zero power levels per pre-ionizer arm | PROPOSED | assumed | XPROT draft proposal (needed to see a dose-response rather than a single point) |
| `pbg_elevated_levels_min` | 2 | elevated background-pressure levels in addition to the base level | PROPOSED | assumed | XPROT draft proposal (two elevated levels allow a slope and a curvature check) |
| `pbg_injection_distance_min` | 2 | m downstream of the thruster exit plane (minimum) | PROPOSED | assumed | REF-DANKANICH2017 Sec. IV.B ('at least 2 m downstream of the thruster exit plane or preferably near the centerline of the facility') |
| `ext_mean_frac` | 0.05 | fraction of I_d,ref | PROPOSED | assumed | p5_n2_validation_criteria_v1.json operational_rules.O1_extinction_SUSTAINMENT (project decision for simulation scoring); adoption for experiments is a proposal |
| `ext_sample_share` | 0.9 | fraction of samples | PROPOSED | assumed | p5_n2_validation_criteria_v1.json operational_rules.O1_extinction_SUSTAINMENT; adoption for experiments is a proposal |
| `ext_sample_frac` | 0.1 | fraction of I_d,ref | PROPOSED | assumed | p5_n2_validation_criteria_v1.json operational_rules.O1_extinction_SUSTAINMENT; adoption for experiments is a proposal |
| `confidence_level` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (conventional level); multiplicity handled by the statistics section |
| `confidence_level_m2` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (same as THR-M1) |
| `confidence_level_m3` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (same as THR-M1) |
| `confidence_level_m4` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (same as THR-M1) |
| `ignition_confidence` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (conventional level) |
| `rfp_thrust_min` | 12 | mN | REQUIREMENT_TRANSCRIBED | assumed | RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 Part III Para 2, as transcribed in abep_sim/constants.py (RFPConstraints.thrust_min_mN) and CLAUDE.md; not re-read from the RFP by this lane - verify |
| `rfp_thrust_max` | 25 | mN | REQUIREMENT_TRANSCRIBED | assumed | RFP Part III Para 2 as transcribed in abep_sim/constants.py (RFPConstraints.thrust_max_mN); verify |
| `rfp_power_max` | 1500 | W | REQUIREMENT_TRANSCRIBED | assumed | RFP Part III Para 2 as transcribed in abep_sim/constants.py (RFPConstraints.power_max_W; CLAUDE.md '< 1.5 kW'); verify |
| `rfp_thrust_per_power_floor` | 8.0 | mN/kW | DERIVED | model-derived | derived by protocol_tools.py: rfp_thrust_min / rfp_power_max. A point with T >= rfp_thrust_min at total system power < rfp_power_max has T / P_system > this value, and P_bus,lab <= P_system, so T / P_bus,lab > this value is necessary |
| `rfp_thrust_min_ref` | 12 | mN | REQUIREMENT_TRANSCRIBED | assumed | rfp_screens.rfp_values.rfp_thrust_min |
| `rfp_thrust_max_ref` | 25 | mN | REQUIREMENT_TRANSCRIBED | assumed | rfp_screens.rfp_values.rfp_thrust_max |
| `rfp_tp_floor_ref` | 8.0 | mN/kW | DERIVED | model-derived | rfp_screens.derived.rfp_thrust_per_power_floor (protocol_tools.py) |
| `aid_confidence` | 0.95 | - | PROPOSED | assumed | XPROT draft proposal (same as ignition_confidence) |
| `aid_target_p90` | 0.9 | probability | PROPOSED | assumed | illustrative grid point chosen by this draft; not a requirement |
| `aid_nmin_p90` | 29 | attempts | DERIVED | model-derived | derived by protocol_tools.py (zero-failure Clopper-Pearson bound) |
| `aid_target_p95` | 0.95 | probability | PROPOSED | assumed | illustrative grid point chosen by this draft; not a requirement |
| `aid_nmin_p95` | 59 | attempts | DERIVED | model-derived | derived by protocol_tools.py (zero-failure Clopper-Pearson bound) |
| `aid_target_p99` | 0.99 | probability | PROPOSED | assumed | illustrative grid point chosen by this draft; not a requirement |
| `aid_nmin_p99` | 299 | attempts | DERIVED | model-derived | derived by protocol_tools.py (zero-failure Clopper-Pearson bound) |

TBD values (43), each with what it requires:

| id | unit | requires |
|---|---|---|
| `rf_frequency` | MHz | RF pre-ionizer design (owner/hardware) |
| `rf_dc_input_power_levels` | W | RF pre-ionizer design; the level set must include zero (sham) and at least the number of non-zero levels in design.pre_ionizer_power_levels_min |
| `rf_feed_topology` | - | hardware decision: series (all propellant through the pre-ionizer) or parallel (split m_dot_p / m_dot_prop); fixed and pre-registered |
| `mw_frequency` | GHz | ECR pre-ionizer design (owner/hardware) |
| `mw_dc_input_power_levels` | W | ECR pre-ionizer design; the level set must include zero (sham) and at least the number of non-zero levels in design.pre_ionizer_power_levels_min |
| `mw_feed_topology` | - | hardware decision: series or parallel propellant feed; fixed and pre-registered |
| `inv_prop_tol` | mole fraction | gas-supply specification and the composition uncertainty of the chosen supply |
| `inv_flow_tol` | fraction | MFC calibration uncertainty on the working gas (from the pre-campaign calibration) |
| `inv_channel_tol` | mm | Hall channel design and metrology capability |
| `inv_mag_peak_tol` | fraction | Hall magnetic design and Gauss-probe uncertainty |
| `inv_mag_loc_tol` | mm | Hall magnetic design and probe positioning uncertainty |
| `inv_vd_tol` | V | discharge supply regulation specification |
| `inv_cath_drift` | V | cathode specification and Hall-only pilot repeatability |
| `inv_fac_tol` | fraction | facility characterization (pressure sensitivity of the Hall-only arm from the pilot) |
| `inv_diag_pickup` | fraction | owner decision after the diagnostic uncertainty budget is known |
| `inv_therm_rate` | K/min | thrust-stand thermal-drift characterization |
| `bus_voltage` | V | spacecraft EPS ICD |
| `compressor_bus_power` | W | upstream ICD: compressor bus draw as a function of delivered total flow and composition at each operating point (abep_sim/compressor.py is the model reference; not evaluated here) |
| `thrust_cal_shift_max` | fraction | thrust-stand characterization (owner) |
| `discharge_sampling_rate` | Hz | oscillation band observed in the Hall-only pilot, with anti-alias filtering; the same rate for all arms |
| `exb_resolution` | - | species set of the O2/N2 mixtures from the upstream ICD and E x B probe design |
| `gauge_correction_o2n2` | - | calibration of the gauges on each O2/N2 mixture (N2 is the industry reference gas; REF-DANKANICH2017 Sec. II.A.2 and III: calibration on the gas of interest, if practical, gives higher precision than a gas correction factor) |
| `prop_xe_reference` | - | owner choice of the Xe reference point (flow and voltage) for drift checks and cross-facility comparison |
| `prop_n2` | - | gas purity specification (owner) |
| `prop_o2n2_mixtures` | mole fractions | upstream ICD: composition delivered at the valve outlet across the RFP altitude envelope (abep_sim/constants.py RFPConstraints.alt_min_km to alt_max_km) and solar conditions (intake -> filter -> compressor -> gas chamber); not invented here |
| `mdot_prop_levels` | mg/s | upstream ICD: delivered mass-flow range at the valve outlet; the set must include the lowest ICD-delivered flow |
| `mdot_cathode` | mg/s | LaB6 cathode specification (owner/supplier); identical in all arms |
| `vd_levels` | V | Hall design envelope (owner) |
| `mag_setting` | A (coil currents) or design ID | Hall magnetic design (owner); fixed across arms |
| `preionizer_power_levels` | W | arms[].pre_ionizer.dc_input_power_levels (RF and ECR designs); includes zero |
| `pbg_levels` | Torr (gas-corrected) | facility characterization: base level at maximum facility capability plus elevated levels spanning the expected operating range |
| `schedule_seed` | - | drawn at pre-registration and recorded in the lock |
| `ignition_timeout` | s | start-sequence design and Hall-only pilot |
| `ignition_hold` | s | owner decision |
| `ext_window` | s | discharge oscillation band from the Hall-only pilot |
| `min_flow_step` | mg/s | MFC resolution and owner decision; it sets the resolution of M6 |
| `delta_m1` | fraction | owner: minimum effect of interest (the change in thrust per bus power that would alter an architecture decision); not derivable from the simulator while the Hall credible set is empty |
| `delta_m2` | fraction | owner: minimum effect of interest for M2 |
| `delta_m3` | fraction | owner: minimum effect of interest for M3 |
| `delta_m4` | fraction | owner: tolerable increase in oscillation (depends on PPU and cathode design) |
| `ignition_attempts` | attempts per arm and propellant | owner, using the ignition decision aid (statistics.ignition_decision_aid) |
| `ignition_p_min` | probability | owner/system requirement (cathode start-cycle budget over the RFP mission duration, abep_sim/constants.py RFPConstraints.mission_hours) |
| `m6_steps` | flow steps | owner, after the flow step (sustainment_and_extinction.flow_step) is fixed |

<!-- END GENERATED: numeric_register -->
