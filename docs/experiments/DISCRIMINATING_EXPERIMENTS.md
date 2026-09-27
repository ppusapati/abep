# Discriminating experiments: Hall-only vs RF+Hall vs ECR+Hall

Status: **draft for the IIST / professor discussion (2026-09-26), revision r3** (second-lens repair against the
integrated execution branch at `d07249b`; r2 was repaired against `e15f66f`). It is not pre-registered, not approved, and commits no hardware. **Every threshold,
convention and decision rule here is PROPOSED for the owner.** The machine-readable version is
`docs/experiments/experiment_plan_v1.json`, and it is the authoritative list of measurements, rules and decision rows.

Architecture ids are the shared contract ids `hall_only`, `rf_hall`, `ecr_hall` (`abep_sim/arch_boundary.py`,
`comparison_grid_v1.json`). The modes M0–M2 below are experimental hardware/power states, not architecture ids.

**Relation to merged lanes.** `lane_25_min_decisive_experiment`
(`docs/architecture_comparison/minimum_decisive_experiment/`) designs the *minimum* version of the same paired experiment,
and `lane_06_experiment_protocol` (`docs/architecture_comparison/experiment_protocol/`) the full protocol. This package is
the discussion-level superset for IIST (it adds M0c, an Xe reference and the transport-identifiability items). Since
`d07249b` the owner decision record that reconciles lane_25 and lane_06 is `fo_experiment_package`
(`docs/architecture_comparison/experiment_package/EXPERIMENT_PACKAGE.md`, decisions D-01..D-15, including D-06 hardware
configuration and D-07 decision margin δ). This package does **not** govern: where the conventions differ (§3, §5, §9),
that decision record (and, through it, lane_25_min_decisive_experiment/lane_06_experiment_protocol) governs a
pre-registered run. lane_06_experiment_protocol §17 defers alignment with `docs/experiments/` to owner review; this is the reciprocal note.

## 0. Milestones

| milestone | what E1 supports | what is still needed / what blocks it |
|---|---|---|
| **A** conditional selection | Paired, common-boundary (V1 basis, §9) architecture differences Δ_arch(T/P_bus) of each source arm against `hall_only` (M0), ignition-threshold shifts and stability changes per architecture and condition: enough for "architecture X is baseline provided …" (D1–D3), with the flight source-chain efficiency stated as a condition. Does not need Physics Baseline 1.0. | δ_req from `lane_28_break_even`; the delivered feed envelope (`lane_16_feed_envelope`, ICD IF-A5); ledger efficiencies and the ICD compressor draw; owner reconciliation with lane_25_min_decisive_experiment/lane_06_experiment_protocol; hardware and facility (§10). |
| **B** physics-backed selection | Transport-independent source data (load-plane source power, interstage delivered current, species) and identifiability data on the tested hardware (§7). | No admitted Hall transport closure (credible set ∅, gate 3 FAIL); no O/O₂ chemistry; any use of E1 data as promotion evidence needs its own audit and pre-registration *before* measurement; second lens for single-lens lanes. |
| **C** proposal/PDR freeze | Measured load-plane power per consumer, lab source-chain efficiency as ledger evidence, temperatures, ignition statistics. | Integrated mass (`lane_21_mass_bom`), thermal/life (`lane_15_thermal_life`, `docs/evidence/wall_life/`), cathode (`lane_19_cathode_integration`), flight PPU/generator efficiencies, mission closure. E1 alone does not support C; flight life is unavailable from it. |

## 1. Why this experiment, and why now

- **There is no architecture winner.** The simulator cannot predict absolute Hall performance for any architecture
  today. The credible transport set is empty. The P5-N₂ v1 vacuum campaign left all nine screening candidates
  INCONCLUSIVE / NOT ELIGIBLE (`hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md`), and that
  outcome is permanent. No design Hall maps exist.
- This plan does **not** depend on any running or future validation outcome. It is designed so that each possible
  result discriminates between stated hypotheses.
- The architecture model (`abep_sim/archengine.py`) separates RF+Hall and ECR+Hall from Hall-only through a handful of
  **assumed priors**:
  - the pre-ionizer gain (η_u lift) and Hall utilization versus inlet pressure;
  - the interstage ion transport (`plasma_devices.Interstage`: wall loss, 2 V barrier);
  - the source DC-to-RF/microwave efficiencies (`plasma_devices.RFSource` / `ECRSource`);
  - the pre-ionizer minimum pressure `p_min_Pa` (RF 0.05 Pa, ECR 0.002 Pa).

  None of these priors has been measured on hardware. A superseded 0-D closure ranked pre-ionizer (ECR) gain, Hall
  η_u,max and interstage transport among the dominant sensitivities of T/D (Spearman 0.48, 0.28, 0.28), and put source
  efficiency and p_min below 0.06, "irrelevant to closure, relevant only to compliance margins" (docs/HISTORY.md v0.3).
  So p_min and source efficiency are listed here for the feed-pressure window (H2, H7) and for the P_bus ledger, not as
  closure drivers. The ranking indicates which priors matter; its absolute results are withdrawn.
- **Published precedent.** Shabshelowitz, Gallimore & Peterson, "Performance of a Helicon Hall Thruster Operating with
  Xenon, Argon, and Nitrogen", *J. Propulsion and Power* 30(3):664–671 (2014), doi:10.2514/1.B35041 (metadata via
  Crossref, abstract via OpenAlex, accessed 2026-09-26; **abstract only**). They measured single- and two-stage operation,
  including nitrogen at 200 V. In two-stage operation thrust increased only marginally with RF power, while propulsive
  efficiency and thrust-to-power both decreased; probe diagnostics suggested a slight rise in propellant efficiency that
  did not overcome the added power. That is real-hardware evidence for H0 over H1 on a different device, and a reason
  δ_req must be resolvable. The flow rates and the basis on which RF power was counted are not recoverable from the
  abstract (verify before quantitative use).
- Under docs/EVIDENCE.md, hardware measurement supersedes literature-derived assumptions within the hardware's
  validated domain. Measured on Vyovrinda hardware, the result is level-1 evidence. Measured on an IIST lab thruster, it
  is level 2 or 3, depending on how similar that thruster is (the owner classifies it).

## 2. Hypotheses under test

| id | hypothesis |
|---|---|
| H0 | At matched feed state, V_d and coils, powering an RF or ECR pre-ionizer does **not** raise T/P_bus. This is CLAUDE.md's "probably robust" finding that RF/helicon pre-ionisers add nothing, here extended to ECR as a test. |
| H1 | Pre-ionization raises η_u enough that T/P_bus rises despite the added bus power. |
| H2 | Pre-ionization lowers the ignition/sustainment threshold in flow or feed pressure (startup, low density). |
| H3 | Most upstream ions are lost in the interstage before they reach the Hall channel. |
| H4 | Pre-ionization changes stability (breathing-mode amplitude/frequency, sustainment window). |
| H5 | Pre-ionization shifts the species mix (N⁺/N₂⁺) or the species acceleration voltage (birth location). This feeds the non-gating E×B forensics lane. |
| H6 | The ECR stage's own magnetic field (875 G resonance at 2.45 GHz) perturbs the Hall B(z). |
| H7 | Any pre-ionizer benefit exists only inside a feed-pressure window, bounded by source coupling (p_min) below and by adequate Hall-only ionization above. |

## 3. The key discriminating experiment (E1)

**The same accelerator, feed state and operating condition are used throughout. Only the upstream ionization stage is
switched.** The following stay identical:
- the Hall channel, anode and gas distributor, magnetic circuit and coil currents;
- the cathode and its flow;
- the thrust stand and the facility;
- the feed state at a defined inlet reference plane (ṁ per species, P_feed, T_feed, composition).

Every comparison is a **within-session paired difference**, so stand calibration, facility effects and hardware ageing
largely cancel.

| mode | configuration | purpose |
|---|---|---|
| M0 | `hall_only`, pre-ionizer removed (lane_25_min_decisive_experiment HW-0) | **architecture reference**: the only state reported as `hall_only`. All architecture comparisons of `rf_hall`/`ecr_hall` are against M0. |
| M0b | pre-ionizer installed but **unpowered** (lane_25_min_decisive_experiment installed-off state); architecture id **none (control state)**. It is *not* Hall-only (lane_25 §2; `fo_experiment_package`: a CFG-A reference with applicators installed is not bare `hall_only`). | within-block drift reference and the denominator of the attribution split R_within = M1/M0b (or M2/M0b). It separates conductance and neutral-pressure effects of the hardware from plasma effects. It never replaces M0 as the architecture baseline. |
| M0c | ECR installed, microwaves off, **ECR magnets on** (no lane_25_min_decisive_experiment equivalent) | isolates the field perturbation (H6) |
| M1 | `rf_hall`, source power swept (lane_25_min_decisive_experiment HW-RF) | |
| M2 | `ecr_hall`, source power swept (lane_25_min_decisive_experiment HW-ECR) | |

**Permanent-magnet ECR.** A permanent-magnet ECR circuit cannot be de-energized, so for that hardware M0b = M0c and H6
cannot be separated by switching the magnets off. It is then bounded only by M0 vs M0b (which confounds the field with
conductance), by measured B(z) in both states, and by the re-trimmed-coil condition of D7.

**Factors.**
- Gas: Xe first as the reference, then N₂. N₂/O₂ mixtures come later and only on owner decision; atomic O needs a
  dedicated source (TBD).
- Anode flow: TBD. It requires the delivered feed envelope of `lane_16_feed_envelope`
  (`docs/architecture_comparison/feed_envelope/feed_envelope_v1.json`, upstream ICD IF-A5), using the common point set
  of `lane_23_comparison_grid` where it applies, and must include the low-flow end.
- V_d: TBD. At least three levels across the sustainment window.
- Pre-ionizer power (net RF/microwave power at the source load plane): 0 plus at least three levels.
- Two comparison bases:
  - (a) matched ṁ and V_d, with the pre-ionizer power added;
  - (b) matched total P_bus, with the Hall discharge power reduced to compensate.

**Protocol.**
- Randomize and interleave the mode order, with M0b return points between blocks to measure drift (and M0 anchors per
  the hardware configuration adopted under `fo_experiment_package` D-06).
- Approach each point up and down to detect hysteresis.
- Repeat on separate days.
- For ignition and sustainment: sweep flow and feed pressure down to extinction and back up to re-ignition in every
  mode. Record cold-start success/attempt counts and the ignition transients.

## 4. Measurements

| measurement | instrument | closes which gap |
|---|---|---|
| I_d mean **and time trace** | high-bandwidth current probe | No I_d traces are published for P5 or ECHT. Gives the stability metric. |
| Thrust | stand with in-situ calibration, drift record, **per-gas and per-mode cold-flow tare** | ECHT has no total uncertainty and no N₂ tare. |
| **Bus power, ledger basis** | load-plane power of every `bus_power_boundary_v1` component, sampled simultaneously (§9) | Common boundary. Hall discharge power alone is **never** substituted for P_bus. |
| RF/µW forward and reflected power **at the source load plane**; matching settings | directional coupler at the coil/antenna feed or coupling-structure input | Net load-plane power for `rf_source`/`ecr_source`. With the generator DC input it gives the lab source-chain efficiency as evidence against the assumed η_dc/feed priors. |
| Ion species fractions (numerical) | E×B probe | P5-N₂ Ω_i,n were never published numerically. |
| Acceleration voltage / IEDF | RPA plus E×B peaks, V_p-corrected | P5-N₂ V_a exists only at N1–N3 and 1 m far field. |
| Beam current and divergence **at every point** | Faraday polar sweep at ≥ 2 radii | P5-N₂ has none at N4/N5, and its A/B readings differ by up to 11 %. ECHT has no plume data. |
| T_e, n_e, V_p (if available) | Langmuir probes in the source, interstage and near plume | Tests H3. Informs the physics question of whether T_e > 30 eV occurs. |
| Ion current delivered by the interstage | biased collector at the interstage exit | Measures the interstage transport efficiency directly (H3). |
| Ignition / extinction thresholds, cold-start rate | protocol above | H2, H7; the `startup` field |
| Oscillation amplitude and frequency (I_d, V_cg) | spectra | H4; the `stability` field |
| Cathode: gas, flow, keeper/heater power, **coupling voltage** | supply logs | ECHT coupling voltage is missing. The P5 cathode ran on Xe. |
| **Measured B(z)** at the operating coil currents, in every mode | Hall-probe map | P5 coil currents and field shape are unpublished. ECHT B was measured only at 2 A. |
| Feed state: ṁ_s, P_feed, T_feed, x_s | gas-calibrated MFCs, inlet P/T sensors | common feed boundary |
| Background pressure: gauge location, gas correction, RGA | ion gauges, RGA | facility-ingestion interpretation |
| Component temperatures at equilibrium | TC/IR | Q_reject, for `lane_15_thermal_life` |

**Derived metrics.**

- **T/P_bus** and the decisive architecture metric **R_arch = (T/P_bus)[M1 or M2] / (T/P_bus)[M0]** (reported as ln R_arch,
  or as the paired difference Δ_arch(T/P_bus) = M1/M2 − M0), i.e. each source arm against `hall_only` on HW-0. This is
  the lane_25 §0/§2 definition.
- **Attribution split (diagnostic, not decisive):** R_arch = R_within × R_install, with R_within = M1/M0b (effect of
  powering the source) and R_install = M0b/M0 (passive presence of the hardware). The installation penalty is a real cost
  of the architecture and is **inside** R_arch; it is never removed from the decision.
- **η_u**, species-resolved: Σ_i (I_beam·Ω_i/q_i)·m_i / (e·ṁ_anode).
  - For N₂ it is reported on a nitrogen-atom mass basis, so that dissociation is not double counted.
  - Cathode-gas ions are excluded or reported separately.
- **η_V** and the axial factor, with a check that the thrust decomposition closes.
- **Ignition-threshold shift**, the **stability envelope** (its threshold is TBD, from the PPU/power requirement), and
  the **interstage transport efficiency**.
- An experimental **energy-ledger residual**. It is reported, not forced to close.

## 5. Required accuracy, stated as discrimination requirements

The decisive quantities are **paired differences**. Their uncertainty must include repeatability and drift, not only
instrument accuracy. No target numbers are invented here. All rows are **PROPOSED**.

**Convention.** Two conventions exist in merged drafts. R1 below is a single-comparison, discussion-level statement
(k = 2). `lane_25_min_decisive_experiment` §6 classifies ln R_arch against a proposed ±5 % band with simultaneous
Student-t intervals at Welch–Satterthwaite dof (m = 14, ν_eff 28.8, k = 3.1727), and lane_06_experiment_protocol uses HIGHER / LOWER /
NOT_DISTINGUISHED with Holm step-down. This package does not govern: for a pre-registered run, lane_25_min_decisive_experiment's convention (or
the owner's reconciliation) applies, and R1 then reads "the multiplicity-corrected interval must resolve δ_req".

| id | requirement | still needed |
|---|---|---|
| R1 | The expanded uncertainty (k = 2) of the architecture difference Δ_arch(T/P_bus) (M1/M2 vs M0; equivalently ln R_arch) must be below δ_req/2. If M0 is not measured in the same installation (D-06), the uncertainty includes the installation/re-mount reproducibility. δ_req is the break-even gain at which the pre-ionizer's added power, mass, heat and complexity are repaid. The ½ is a proposed convention (owner decision). | δ_req is TBD. It needs `lane_28_break_even` on the `lane_11_bus_boundary` boundary, `lane_15_thermal_life` and `lane_21_mass_bom`. |
| R2 | Resolve the Δη_u that would move T/P_bus across δ_req, with the propagation model stated. | follows from R1 |
| R3 | Flow and feed-pressure resolution must be finer than the gap between the Hall-only threshold and the lowest feed state the intake/compressor delivers at 180–230 km. | the `lane_16_feed_envelope` delivered envelope (ICD IF-A5) |
| R4 | For testing transport closures on our hardware, the I_d and thrust uncertainty must be below the spread across the closures being discriminated. It must also be no worse than the literature uncertainties that already limited P5: thrust σ 2.6 mN; I_d only from 3-significant-figure P_d, with no stated uncertainty; the Xe2 blind I_d of −15.56 % against a 15 % criterion. | The spread on our geometry needs an admitted credible set (currently ∅) or an owner-approved non-design sensitivity study. Screening candidates never produce design maps. |
| R5 | Species V_a and fractions must be good enough to decide whether the N⁺/N₂⁺ ordering is reproduced and whether it moves with pre-ionization. The literature reference is σ 11.6 V (P5-N₂, far field). | probe design review |
| R6 | The uncertainty in P_bus on the ledger basis (including ledger-efficiency bounds and, on the V1 basis, the ICD compressor uncertainty) must not dominate R1. | |
| R7 | An effect smaller than the measured M0b drift is **UNRESOLVED**. It is not read as zero. | |

## 6. Decision logic

All rows are **PROPOSED**.

| # | outcome | supports | refutes / decision |
|---|---|---|---|
| D1 | Δ_arch(T/P_bus) (M1/M2 vs M0, i.e. R_arch incl. the installation penalty) resolvably > +δ_req in the delivered feed envelope, on the V1 basis (a PARTIAL_BOUNDARY-only result is not decisive) | H1. That pre-ionizer becomes a CONDITIONAL_BASELINE candidate within the tested envelope. | Refutes H0 there. Establishes nothing about flight performance, life or closure. |
| D2 | \|Δ_arch(T/P_bus)\| < δ_req (M1/M2 vs M0, resolved, V1 basis), with no threshold shift | H0: Hall-only as the simpler conditional baseline | Refutes H1 and H2 for that source within the envelope. |
| D3 | Δ_arch(T/P_bus) < 0 (vs M0), but the ignition threshold is resolvably lower | H2 without H1: the source enables startup and low-density operation but does not improve performance | No winner. The choice depends on whether the delivered feed falls below the Hall-only threshold (`lane_16_feed_envelope`, `lane_28_break_even`). Duty-cycled pre-ionization is a separate question. |
| D4 | η_u rises but T/P_bus falls or stays flat | The source's ion cost exceeds the gain | Attribute the cause with the RF/µW power and interstage-current data. |
| D5 | The interstage delivers a small fraction of the source ions | H3 | Refutes the interstage model (`lane_18_interstage`, `abep_sim/interstage.py`) for that geometry. The shortfall is not attributed to the Hall accelerator, and there is no architecture conclusion until the interstage is redesigned and retested. |
| D6 | M0b ≠ M0 | A hardware installation effect (R_install ≠ 1) | Architecture decisions (D1–D3) stay referenced to M0 and include the penalty. Report the split R_within (vs M0b) and R_install (M0b vs M0) for attribution only. A pre-ionizer whose powered gain over M0b is cancelled by its installation penalty does **not** pass D1. |
| D7 | M0c ≠ M0b | H6 | Also compare at re-matched B(z) (coil re-trim) as a pre-declared condition, and report both comparisons. |
| D8 | The stability envelope changes | H4 (direction as measured) | Goes to `lane_24_hard_gates` only if no stable operation exists anywhere in the envelope. |
| D9 | A mode cannot ignite or sustain anywhere in the delivered envelope, repeatably | Hard-gate evidence | ELIMINATED_WITHIN_TESTED_ENVELOPE only via `lane_24_hard_gates`. Never extrapolated. |
| D10 | The species mix or V_a shifts | H5 | Non-gating forensics only (`lane_29_exb_physics`). Never used for tuning. |
| D11 | All differences fall below resolution | nothing | UNRESOLVED. Fix repeatability first. This outcome is not evidence for H0. |

## 7. Measurements that most reduce Hall-transport non-identifiability

These gaps are recorded in `hallthruster_bridge/identification/p5_n2_measurement_audit_findings_v1.json`,
`identification/echt_n2/`, docs/EVIDENCE.md and CLAUDE.md item 1. On our own hardware they can be measured instead of
carried as layer-1 nuisance.

1. **Measured B(z) and coil currents per point**, with the axis tied to the anode and the exit. This removes the
   P5 L38/L32 registration and coil-shape hypotheses.
2. **Channel depth, radii and anode position**, as built. This removes the P5 32 vs 38 mm conflict and the missing
   ECHT radii.
3. **Per-point divergence and beam current.** This removes the divergence reading A/B and the P5 N4/N5 gap.
4. **I_d time traces.** These test the quiet/oscillatory regime classification directly.
5. **Species fractions (numerical) and V_a at more than one distance.**
6. **Cathode coupling voltage and cathode gas.**
7. **Background pressure** with gauge location and composition, ideally at two pressures per point.
8. **A thrust uncertainty budget and per-gas cold-flow tare.**
9. **Near-channel T_e, if non-perturbing.** This is physics-lane evidence on whether T_e > 30 eV is real. It is **not** a
   basis for extending rate-table limits: extension needs independent published evidence and a new v2 pre-registration,
   and Question A stays A-NO.

**Use rule.** If these data ever test closures, the sequence is: audit, then pre-register, then simulate. There is no
retuning, and vacuum and facility modes are never crossed.

## 8. What cannot yet be claimed

- **Withdrawn:** all absolute Hall results of the 0-D closure (v1.2–v1.6): ABEP thrust, the 2.5 kW closure,
  110–120 kg, and ECR+Hall P(success) 0.77 vs 0.63.
- **Superseded historical sweep statements** ("ECR+Hall closes on physics", "12 ABEP-closed", P(closed) 3–5 %;
  docs/HISTORY.md v0.2.1 and v0.3).
- **Numerical artefact:** the v1.3 hysteresis / low-mode collapse.
- **No closures:** there is no admitted transport closure and no design Hall map; the credible set is ∅.
- **No winner:** there is no architecture winner and no demonstrated ABEP drag closure.
- **Gate-4 numbers:** absolute gate-4 mission-UQ numbers are conditional on gate 3, which fails.
- **Running work:** nothing is stated about O4, the escalations or the facility runs.
- **P5-N₂ v1 stays INCONCLUSIVE** and is never rewritten.
- **ECHT-N₂** is not an independent scoreable dataset without forced assumptions.
- **Not measurements:** P5-N₂ Φ_m,n, η_SP,n and ξ_N are model-derived.

**Probably robust (mechanism level, CLAUDE.md):**
- grids are life-limited by CEX and the perveance window;
- magnetic nozzles are excluded by energy per particle;
- "RF/helicon pre-ionisers add nothing". That last finding is **H0**, and E1 is the experiment that tests it.

## 9. Mapping to the common comparison boundary

**One power basis** (`bus_power_boundary_v1`, `lane_11_bus_boundary`,
`docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md` §3). Every component, including the pre-ionizers,
is booked at its load-side reference plane and divided by a pre-registered ledger efficiency:
P_bus = Σ P_load,c / η_c (`bus_power_ledger(arch, loads, efficiencies)`). For `rf_source`/`ecr_source` the load plane is
the net RF/microwave power (forward − reflected) at the coil/antenna feed or coupling-structure input. This is the basis
of lane_25_min_decisive_experiment §5.
- The DC input of each **lab** supply and generator is recorded only as efficiency evidence (η_lab = P_load/P_DC,in). It
  may feed a secondary ratio labelled LAB_CHAIN, never a common-boundary result. No model PPU loss is added on top of a
  lab DC input, which would double-count conversion. Charging `rf_hall`/`ecr_hall` at non-flight lab generator
  efficiency would bias the outcome toward H0, the hypothesis under test.
- **Compressor: ABSENT_IN_LAB** in every mode (the lab feed starts at the valve outlets). It is explicitly unavailable
  from E1 and is **reconstructed** from the upstream ICD (bus draw at the delivered total flow and composition), as in
  lane_06_experiment_protocol §5. It is never a placeholder and never zero.
- **Totals.** P_bus,lab (all measured components, compressor excluded) is labelled **PARTIAL_BOUNDARY**.
  P_bus,v1 = P_bus,lab + P_compressor,ICD exists only when the ICD supplies the compressor draw; otherwise it is
  UNAVAILABLE. A common additive term does not cancel in paired ratios, so PARTIAL_BOUNDARY ratios are never reported as
  `bus_power_boundary_v1` ratios. Common loads the lab hardware does not represent (flight `flow_control`,
  `housekeeping`, `thermal_control`) are ledger inputs with their evidence class, identical across arms.
- **Open reconciliation.** lane_06_experiment_protocol books `rf_source`/`ecr_source` at the generator DC input (`rf_generator_input`,
  `microwave_source_input`). lane_25_min_decisive_experiment and the lane_11_bus_boundary contract use the load plane. This package follows the contract;
  the reconciliation of the two lanes is recorded in `fo_experiment_package`
  (`docs/architecture_comparison/experiment_package/`), which this package defers to.

E1 populates these mandatory fields:
- ṁ_s, P_feed, T_feed and x_s (feed instrumentation, plus E×B for the beam);
- V_d;
- T;
- P_bus: **PARTIAL_BOUNDARY** from E1; complete only as P_bus,v1 with the ICD-reconstructed compressor;
- Q_reject (estimated from temperatures);
- startup;
- η_u;
- stability.

Explicitly not populated by E1 (CLAUDE.md admissibility: populated or explicitly unavailable):
- **compressor share of P_bus**: ABSENT_IN_LAB, reconstructed from the ICD or UNAVAILABLE;
- **m**: lab-hardware mass by weighing, flagged as not flight mass;
- **flight life**: unavailable from E1; at most hours-class erosion witnesses.

Lanes that consume or constrain the results (machine ids from `docs/orchestration/lane_registry_v1.json`; context
re-checked at `d07249b`):
- `fo_experiment_package` (owner decision record reconciling lane_25/lane_06, D-01..D-15; governs where this package differs),
  `lane_06_experiment_protocol` (protocol), `lane_25_min_decisive_experiment` (minimum; owns the decisive convention),
  `lane_23_comparison_grid` (common points);
- `lane_11_bus_boundary` (P_bus basis), `lane_16_feed_envelope` (flows, R3, D3), `lane_12_arch_harness` (harness);
- `lane_07_rf_evidence`, `lane_08_ecr_evidence`, `lane_09_hall_sustainment` (priors E1 tests), `lane_18_interstage` (H3, D5);
- `lane_15_thermal_life`, `lane_19_cathode_integration`, `lane_21_mass_bom`, `lane_28_break_even` (δ_req);
- `lane_24_hard_gates` (D8, D9), `lane_29_exb_physics` (H5, D10; non-gating).

## 10. Questions for the IIST discussion

1. **Facility:** pumping speed and background pressure at the N₂ flows of interest, gauge locations, and whether an RGA
   is available.
2. **Thrust stand:** resolution, calibration method and multi-hour drift.
3. **Diagnostics:** which of E×B, RPA, Faraday (guard ring, polar arm), Langmuir probes, fast current probes and a
   Hall-probe B mapper are available.
4. **Hardware:** can an existing Hall thruster take an upstream RF or ECR stage without changing its channel? Is a
   2.45 GHz ECR stage available or buildable?
5. **Cathode:** type and gas. Can it run on N₂, or must it run on Xe or Ar? This affects species attribution.
6. **Gases:** N₂ and N₂/O₂ compatibility of the hardware, and oxygen safety.
7. **Scope:** the minimum feasible subset of M0/M0b/M0c/M1/M2 to run first.
8. **Data terms:** raw traces and per-point data must be archivable with their provenance.

## Sources

- Repository only: CLAUDE.md; docs/EVIDENCE.md; docs/HISTORY.md (superseded results, cited only as non-claims);
  `abep_sim/archengine.py`; `abep_sim/plasma_devices.py`;
  `hallthruster_bridge/identification/p5_n2_measurement_audit_findings_v1.json`;
  `hallthruster_bridge/identification/echt_n2/` (README and audit JSON);
  `hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md`.
- Merged lanes at `e15f66f` and `d07249b`, read-only: `docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md`,
  `docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md`,
  `docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md`,
  `docs/orchestration/lane_registry_v1.json`,
  `docs/architecture_comparison/experiment_package/EXPERIMENT_PACKAGE.md` (`d07249b`).
- External, accessed 2026-09-26 (r2): Crossref metadata and OpenAlex abstract for doi:10.2514/1.B35041
  (Shabshelowitz, Gallimore & Peterson 2014); abstract only.
- Other literature named here comes through the repository audit files (Brabston et al., JPP 2025,
  doi:10.2514/1.B39623; Marchioni, MSc thesis 2020). The historical RF p_min prior "Shabshelowitz 2013" in
  docs/HISTORY.md is a different item and stays **verify**.
