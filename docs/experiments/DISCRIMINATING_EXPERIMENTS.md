# Discriminating experiments: Hall-only vs RF+Hall vs ECR+Hall

Status: **draft for the IIST / professor discussion (2026-09-26).** It is not pre-registered, not approved, and commits no
hardware. The machine-readable version is `docs/experiments/experiment_plan_v1.json`, and it is the authoritative list of
measurements, rules and decision rows.

## 1. Why this experiment, and why now

- **There is no architecture winner.** The simulator cannot predict absolute Hall performance for any architecture
  today. The credible transport set is empty. The P5-N₂ v1 vacuum campaign left all nine screening candidates
  INCONCLUSIVE / NOT ELIGIBLE (`hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md`), and that
  outcome is permanent. No design Hall maps exist.
- This plan does **not** depend on any running or future validation outcome. It is designed so that each possible
  result discriminates between stated hypotheses.
- The architecture model (`abep_sim/archengine.py`) separates RF+Hall and ECR+Hall from Hall-only through a handful of
  **assumed priors**:
  - the pre-ionizer minimum pressure `p_min_Pa` (RF 0.05 Pa, ECR 0.002 Pa);
  - the source DC-to-RF/microwave efficiencies (`plasma_devices.RFSource` / `ECRSource`);
  - the interstage ion transport (`plasma_devices.Interstage`: wall loss, 2 V barrier);
  - Hall utilization versus inlet pressure.

  None of these priors has been measured on hardware. A superseded 0-D closure ranked pre-ionizer gain, Hall η_u and
  interstage transport among the dominant sensitivities (docs/HISTORY.md v0.3). That ranking indicates which priors
  matter. Its absolute results are withdrawn.
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
| M0 | Hall-only, pre-ionizer removed | reference |
| M0b | Hall-only, pre-ionizer installed but **unpowered** | control. It separates conductance and neutral-pressure effects of the hardware from plasma effects. All M1/M2 effects are referenced to M0b. |
| M0c | ECR installed, microwaves off, **ECR magnets on** | isolates the field perturbation (H6) |
| M1 | RF+Hall, source power swept | |
| M2 | ECR+Hall, source power swept | |

**Factors.**
- Gas: Xe first as the reference, then N₂. N₂/O₂ mixtures come later and only on owner decision; atomic O needs a
  dedicated source (TBD).
- Anode flow: TBD. It requires the delivered feed envelope from lane_11 and must include the low-flow end.
- V_d: TBD. At least three levels across the sustainment window.
- Pre-ionizer power: 0 plus at least three levels.
- Two comparison bases:
  - (a) matched ṁ and V_d, with the pre-ionizer power added;
  - (b) matched total P_bus, with the Hall discharge power reduced to compensate.

**Protocol.**
- Randomize and interleave the mode order, with M0b return points between blocks to measure drift.
- Approach each point up and down to detect hysteresis.
- Repeat on separate days.
- For ignition and sustainment: sweep flow and feed pressure down to extinction and back up to re-ignition in every
  mode. Record cold-start success/attempt counts and the ignition transients.

## 4. Measurements

| measurement | instrument | closes which gap |
|---|---|---|
| I_d mean **and time trace** | high-bandwidth current probe | No I_d traces are published for P5 or ECHT. Gives the stability metric. |
| Thrust | stand with in-situ calibration, drift record, **per-gas and per-mode cold-flow tare** | ECHT has no total uncertainty and no N₂ tare. |
| **Actual bus power** | DC input of *every* supply, logged simultaneously: anode, RF/ECR amplifier input, Hall and ECR magnets, cathode heater/keeper, flow control, controls/cooling | Needed for the common `bus_power_boundary_v1`. Forward, absorbed or reflected RF power and Hall-only discharge power are **never** substituted for P_bus. PPU losses stay "assumed" until a PPU is measured. |
| RF/µW forward, reflected, absorbed power; matching settings | directional coupler | Replaces the assumed η_dc and feed efficiencies. |
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
| Component temperatures at equilibrium | TC/IR | Q_reject, for lane_15 |

**Derived metrics.**

- **T/P_bus** and the paired **Δ(T/P_bus)** relative to M0b. The installation penalty M0b − M0 is reported separately.
- **η_u**, species-resolved: Σ_i (I_beam·Ω_i/q_i)·m_i / (e·ṁ_anode).
  - For N₂ it is reported on a nitrogen-atom mass basis, so that dissociation is not double counted.
  - Cathode-gas ions are excluded or reported separately.
- **η_V** and the axial factor, with a check that the thrust decomposition closes.
- **Ignition-threshold shift**, the **stability envelope** (its threshold is TBD, from the PPU/power requirement), and
  the **interstage transport efficiency**.
- An experimental **energy-ledger residual**. It is reported, not forced to close.

## 5. Required accuracy, stated as discrimination requirements

The decisive quantities are **paired differences**. Their uncertainty must include repeatability and drift, not only
instrument accuracy. No target numbers are invented here.

| id | requirement | still needed |
|---|---|---|
| R1 | The expanded uncertainty (k = 2) of Δ(T/P_bus) must be below δ_req/2. δ_req is the break-even gain at which the pre-ionizer's added power, mass, heat and complexity are repaid. The ½ is a proposed convention (owner decision). | δ_req is TBD. It needs the lane_28 break-even on lane_11's boundary, lane_15 thermal/life and the lane_21 mass BOM. |
| R2 | Resolve the Δη_u that would move T/P_bus across δ_req, with the propagation model stated. | follows from R1 |
| R3 | Flow and feed-pressure resolution must be finer than the gap between the Hall-only threshold and the lowest feed state the intake/compressor delivers at 180–230 km. | the lane_11 feed envelope |
| R4 | For testing transport closures on our hardware, the I_d and thrust uncertainty must be below the spread across the closures being discriminated. It must also be no worse than the literature uncertainties that already limited P5: thrust σ 2.6 mN; I_d only from 3-significant-figure P_d, with no stated uncertainty; the Xe2 blind I_d of −15.56 % against a 15 % criterion. | The spread on our geometry needs an admitted credible set (currently ∅) or an owner-approved non-design sensitivity study. Screening candidates never produce design maps. |
| R5 | Species V_a and fractions must be good enough to decide whether the N⁺/N₂⁺ ordering is reproduced and whether it moves with pre-ionization. The literature reference is σ 11.6 V (P5-N₂, far field). | probe design review |
| R6 | The uncertainty in total P_bus must not dominate R1. | |
| R7 | An effect smaller than the measured M0b drift is **UNRESOLVED**. It is not read as zero. | |

## 6. Decision logic

| # | outcome | supports | refutes / decision |
|---|---|---|---|
| D1 | Δ(T/P_bus) resolvably > +δ_req in the delivered feed envelope | H1. That pre-ionizer becomes a CONDITIONAL_BASELINE candidate within the tested envelope. | Refutes H0 there. Establishes nothing about flight performance, life or closure. |
| D2 | \|Δ(T/P_bus)\| < δ_req (resolved), with no threshold shift | H0: Hall-only as the simpler conditional baseline | Refutes H1 and H2 for that source within the envelope. |
| D3 | Δ(T/P_bus) < 0, but the ignition threshold is resolvably lower | H2 without H1: the source enables startup and low-density operation but does not improve performance | No winner. The choice depends on whether the delivered feed falls below the Hall-only threshold (lane_11, lane_28). Duty-cycled pre-ionization is a separate question. |
| D4 | η_u rises but T/P_bus falls or stays flat | The source's ion cost exceeds the gain | Attribute the cause with the RF/µW power and interstage-current data. |
| D5 | The interstage delivers a small fraction of the source ions | H3 | Refutes the model's efficient-transport assumption for that geometry. The shortfall is not attributed to the Hall accelerator, and there is no architecture conclusion until the interstage is redesigned and retested. |
| D6 | M0b ≠ M0 | A hardware installation effect | Reference everything to M0b and report the installation penalty. |
| D7 | M0c ≠ M0b | H6 | Also compare at re-matched B(z) (coil re-trim) as a pre-declared condition, and report both comparisons. |
| D8 | The stability envelope changes | H4 (direction as measured) | Goes to lane_24 only if no stable operation exists anywhere in the envelope. |
| D9 | A mode cannot ignite or sustain anywhere in the delivered envelope, repeatably | Hard-gate evidence | ELIMINATED_WITHIN_TESTED_ENVELOPE only via lane_24. Never extrapolated. |
| D10 | The species mix or V_a shifts | H5 | Non-gating forensics only. Never used for tuning. |
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

E1 populates these `bus_power_boundary_v1` mandatory fields:
- ṁ_s, P_feed, T_feed and x_s (feed instrumentation, plus E×B for the beam);
- V_d;
- T;
- P_bus (all DC supplies);
- Q_reject (estimated from temperatures);
- startup;
- η_u;
- stability.

Two fields stay open:
- **m** is lab-hardware mass by weighing, flagged as not flight mass.
- **Flight life** is explicitly *unavailable* from E1: at most hours-class erosion witnesses.

Lanes that consume the results:
- lane_06 (protocol), lane_11 (boundary), lane_12 (harness), lane_15 (thermal/life);
- lane_19 (cathode), lane_21 (BOM), lane_24 (hard gates), lane_25 (minimum decisive experiment, for which E1 is a
  candidate superset);
- lane_28 (δ_req).

The lane ids follow CLAUDE.md and the owner's instructions. The registry lives on the execution branch; verify the ids
there.

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
- No external source was accessed for this document. The literature named here comes through those audit files
  (Brabston et al., JPP 2025, doi:10.2514/1.B39623; Marchioni, MSc thesis 2020). The historical RF prior
  "Shabshelowitz 2013" is marked **verify**.
