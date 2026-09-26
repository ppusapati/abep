# Minimum decisive experiment: Hall-only vs RF+Hall vs ECR+Hall

**Status: DRAFT_PENDING_OWNER.** Lane 25 (MINEXP), 2026-09-26, base commit `c53b75a`, revision r2 (adversarial-review
repair; §18 maps each finding to its fix). Nothing here is pre-registered or approved. Every threshold and rule is
**PROPOSED** for the owner. The machine-readable twin is `experiment_draft.json` in this folder. Every derived number
comes from `minexp_numbers.py` in this folder; its `--check` mode reproduces the JSON block and
`tests/test_minimum_decisive_experiment.py` checks both.

Numbers in this document are one of three kinds: **PROPOSED thresholds** (evidence class *assumed*, owner decision),
**derived requirements** (evidence class *model-derived*, from the script), or **cited literature statements**
(source given). Everything else is **TBD — requires …**. No performance number of any Hall thruster is used.

## 0. Summary

- **Question.** At one common feed state and one common bus boundary (`bus_power_boundary_v1`), does an RF or an ECR
  pre-ionizer in front of the **same** Hall accelerator raise thrust per bus watt, or let the discharge run where
  Hall-only cannot, compared with Hall-only?
- **When to run it.** Only if the literature and model evidence (`docs/evidence/rf_source/`, `docs/evidence/ecr_source/`,
  `docs/evidence/hall_sustainment/`) still can't settle the question. This draft doesn't judge that.
- **Design.** One Hall unit H-1 and one cathode C-1 in three hardware configurations: HW-0 (bare feed, the
  `hall_only` arm), HW-RF and HW-ECR. Three N₂ flows straddle the Hall-only sustainment knee, plus one air-surrogate
  point, two source powers, and two V_d levels for Hall-only only (iso-power reference). Blocks are paired and
  randomised.
- **Bus basis.** Every component is booked the way `abep_sim/arch_boundary.py` defines it: load-side power at the
  component's load plane, divided by a pre-registered ledger efficiency. For the sources that load plane is the net
  RF or microwave power at the coupling terminals. The lab generator's DC input is recorded as efficiency evidence
  only.
- **Decisive metric.** R_arch = (T/P_bus) of the source arm divided by (T/P_bus) of Hall-only at the same point. It is
  classified against a proposed ±5 % band (δ = 0.05 on ln R). The intervals are simultaneous Student-t intervals at
  Welch–Satterthwaite effective degrees of freedom. The break-even identity R_arch > 1 ⇔ C_del < C* ties it to the
  source's delivered-ion cost.
- **Size.** 40 Hall-on conditions per block, taken as 52 readings per block (bracketing readings included): 208
  readings at 4 blocks. Add 120 bench readings, a 10-reading knee scan and an 18-reading S1b re-mount series (not
  score-bearing). If both source arms stop after their confirmation subsets, the Hall-on count is 128 readings.
- **Uncertainty target.** With m = 14 simultaneous comparisons and n = 4 blocks, the planning ν_eff is 28.8, so
  k = 3.1727 (not the normal 2.9137). σ(ln R) must then be at most 0.00788. With five equal variance shares, that
  means per-reading thrust and bus-power repeatability of at most 0.50 % and an installation (re-mount)
  reproducibility of at most 0.25 %. Whether that is achievable is **TBD — requires S1 data**. The owner can widen δ
  or adopt OPTION-DIVERTER instead; the trade-off is in §6.
- **Output.** A per-arm, per-condition classification with its qualifiers and conditions. The output never names a
  winner.

## 1. Milestones supported

| milestone | what this experiment delivers | what is still needed to reach it / the next one |
|---|---|---|
| **A** conditional selection | Measured, paired, common-boundary classes per arm and condition, each with qualifiers and conditions. Classes: SOURCE_BETTER / EQUIVALENT / SOURCE_WORSE / UNRESOLVED / ENABLES / DISABLES / …. Qualifiers: FACILITY_*, LEDGER_*. Conditions include the break-even source-chain efficiency η_src,be. Enough for "architecture X is baseline provided A/B/C". Doesn't need Physics Baseline 1.0. | S0 (LOCK-1); S1 with D0 passed (LOCK-2); S2–S4 for `hall_only` and every non-stopped source arm; S5 for the facility qualifier; S6 re-installation check. Feed-envelope values from the upstream ICD (IF-A5), the bus allocation and the ledger inputs. |
| **B** physics-backed selection | Source boundary data that don't depend on Hall transport: P_src,load, P_src,bus, I_src, I_del, η_ts, delivered-ion energy and species. Hall data on the tested hardware: B(z) maps with coil currents, geometry, I_d traces, species fractions and divergence per point. | An admitted Hall transport closure; the credible set is empty today (CLAUDE.md gate 3). O/O₂ chemistry for air (CLAUDE.md next work 4); the air surrogate here has no atomic O. If the physics track wants these data as promotion evidence, it must pre-register that separately, before the measurement. |
| **C** proposal/PDR freeze | Measured load-plane power per consumer at the tested points; source waste heat; measured lab source-chain efficiency as evidence for the ledger. | Mass, thermal, life (`docs/evidence/wall_life/`, `abep_sim/thermal_life.py`), startup, cathode (`docs/evidence/cathode/`) and mission closure integrated; flight-representative PPU and generator efficiencies. This experiment alone doesn't support C. |

This is the fastest physical route to milestone A. It also feeds milestone B directly once a closure is admitted.

## 2. What is held identical, and the one thing that changes

| element | `hall_only` (HW-0) | `rf_hall` (HW-RF) | `ecr_hall` (HW-ECR) |
|---|---|---|---|
| Hall accelerator | H-1 (same serial unit, channel, anode, magnetic circuit, coil currents per point) | H-1 | H-1 |
| cathode | C-1, same position, flow and keeper setting | C-1 | C-1 |
| feed state | FS-common: same anode flow, composition (same MFCs and bottles), cathode flow, supply temperature (IF-A5 / IF-X2 fields) | same | same |
| V_d, facility, stand, meters, probes, calibration standards | same | same | same |
| ledger efficiency of every common component | same values (LOCK-1) | same | same |
| pre-ionizer | none (flow-equivalent spacer) | RF source + interstage + RF generator + matching | ECR source + interstage + microwave generator + isolator + waveguide/antenna + ECR magnet |
| arm-specific bus components | none | `rf_source` | `ecr_source`, `ecr_magnet` |

Common bus components (`bus_power_boundary_v1`, `abep_sim/arch_boundary.py`, other lane, referenced by path only):
`hall_discharge`, `hall_magnet`, `cathode_keeper`, `cathode_heater`, `flow_control`, `compressor`, `thermal_control`,
`housekeeping`. The mapping from measurements to the contract is in §5.

**Installation effect.** With its source unpowered, HW-RF or HW-ECR is *not* Hall-only: gas still flows through the
source chamber, and an ECR permanent magnet would still perturb the Hall field. So:

- `hall_only` is measured on HW-0;
- the installed-off state of each source configuration is a within-block drift reference;
- R_arch = R_within × R_install separates the effect of powering the source from the passive presence of its
  hardware.

B(z) is mapped for every configuration (§5, M11).

**OPTION-DIVERTER (PROPOSED hardware option).** An in-vacuum feed-path diverter routes gas through the source or
straight to the anode distributor without venting. Hall-only is then measured in the same installation as the source
arm, which removes the installation term (G5, §6). It needs one check against a true HW-0. Its intent matches the
full-protocol lane's CFG-A (§13). Owner decision.

## 3. Break-even logic

### 3.1 Decisive quantities

| id | symbol | quantity | measured in |
|---|---|---|---|
| Q1 | I_del | delivered ion current: ion current across the Hall channel exit plane with the Hall discharge off and magnet on (cold transport through the whole accelerator), integrated over the beam | S3 |
| Q2 | P_src,bus | bus draw of the arm-specific components: `bus_power_ledger` with the load-plane powers (net RF/microwave power at the coupling terminals, M3; `ecr_magnet` coil power, M2) and the pre-registered ledger efficiencies | S3, S4 |
| Q3 | η_ts | interstage transport efficiency I_del / I_src (I_src = ion current leaving the source exit plane) | S3 |
| Q4 | ΔI_d | Hall discharge-current change, source arm vs `hall_only`, at fixed V_d, ṁ, composition, coil currents | S2, S4 |
| Q5 | ΔT | thrust change at the same fixed conditions | S2, S4 |
| Q6 | ΔP_bus | change of the `bus_power_ledger` sum, same ledger inputs | S2, S4 |

### 3.2 The inequality

On the ledger basis, the source arm's bus power is P_bus,X = P_bus,0 + V_d·ΔI_d/η_d + P_src,bus + ΔP_other. Here
η_d is the ledger's `hall_discharge` efficiency, the same value in all arms. Then

  R_arch = (T_X / P_bus,X) / (T_0 / P_bus,0) > 1 ⇔ ΔT · P_bus,0 > T_0 · (V_d·ΔI_d/η_d + P_src,bus + ΔP_other).

Dividing by I_del gives the break-even form:

  **C_del ≡ P_src,bus / I_del < C\* ≡ y · (P_bus,0 / T_0) − κ · V_d / η_d − ΔP_other / I_del**,
  with y = ΔT / I_del and κ = ΔI_d / I_del.

C_del has units of W/A = V: the bus energy spent per elementary charge delivered, in eV. It is the energy per ion
only for singly charged ions; doubly charged N ions are in the project's N₂/N reaction set. C\* has three terms:

- the bus power Hall-only spends per unit thrust, times the thrust bought per delivered ampere;
- minus the extra discharge power the delivered ions draw;
- minus any other bus change.

"The delivered-ion cost exceeds the break-even cost" (C_del > C\*) is the same statement as "R_arch < 1". This is an
identity with no physical assumption; the test checks it numerically. The stop rule (§9) states it with simultaneous
confidence.

### 3.3 Break-even source-chain efficiency

P_src,bus = P_src,load/η_src + P_mag,bus, so R_arch > 1 ⇔ η_src > **η_src,be = P_src,load / (C\*·I_del − P_mag,bus)**,
when the denominator is positive. If it isn't, no efficiency reaches break-even. The flight RF or microwave chain
isn't part of this experiment, so η_src,be is reported at every compared condition as a milestone-A condition: "X is
better at this point provided its flight source chain reaches η_src,be." The identity is tested.

### 3.4 The ion-momentum ceiling, and why a Hall-off bound only screens

An ion of charge Ze fully accelerated through V_d with no divergence carries at most y_max = √(2 m_i V_d / (Z e)) of
thrust per ampere. Values per √V for Z = 1 (ion mass ≈ neutral mass from `abep_sim/constants.py`):

| ion | y_max / √(V_d/V) [mN A⁻¹] |
|---|---|
| N₂⁺ | 0.7618 |
| O₂⁺ | 0.8144 |
| N⁺ | 0.5387 |
| O⁺ | 0.5759 |
| Xe⁺ | 1.6497 |

If y ≤ y_max (heaviest singly charged species in the feed), κ ≥ 0 and ΔP_other ≥ 0, then C\* ≤ C\*_ub = y_max · P_bus,0
/ T_0. C\*_ub needs only S2 (Hall-only) and S3 (bench) data. It can't stop an arm, because:

- y can exceed y_max if the delivered plasma seeds extra Hall ionization, or if Hall-on transport beats cold transport;
- κ can be negative. The ID-Hall abstract (REF-MARTINORTEGA2020) reports that the I–V overshoot of single-stage
  operation disappears in double-stage operation at intermediate voltages, which the authors read as decreased
  anomalous electron transport.

So the bound is used only to shrink S4 for an arm that fails it everywhere (D2), and a stop needs Hall-on data (D3).

### 3.5 Iso-power comparison

Under a hard bus cap, Hall-only could spend the source's watts on a higher V_d instead. R_iso = T_X / T0_iso, where
T0_iso is Hall-only thrust on the chord between its (P_bus, T) points at V_nom and V_hi (same ṁ), evaluated at
P_bus = P_bus,X. It is reported only where the two Hall-only points bracket P_bus,X; there is no extrapolation. It is a
second comparison family (m = 8) with its own variance model (§6.5).

### 3.6 Priors this experiment tests

- CLAUDE.md lists "RF/helicon pre-ionisers add nothing" as probably robust at mechanism level (independent of the Hall
  closure). It comes from the project's own models, so it is model-derived; within the tested domain, hardware
  measurement supersedes it (docs/EVIDENCE.md).
- The helicon Hall thruster precedent (REF-SHABSHELOWITZ2014, abstract only) measured single-stage and two-stage
  operation, including nitrogen. It reports thrust marginally up and thrust-to-power down with RF power. Whether RF
  power was counted at the DC input or as forward power is not checked (verify).
- The decision tree lets an arm stop early if such a prior holds on this hardware; that is where the savings come from.
  No arm is stopped on a prior.
- The v1.3 record (docs/HISTORY.md) had already named "air-Hall thrust/current vs flow" and "transported ECR ion current
  per watt" as decisive measurements. Its absolute numbers are withdrawn (CLAUDE.md) and are not used.

### 3.7 Common loads dilute R

Common loads the lab doesn't have (compressor, housekeeping) raise P_bus,0 and therefore C\*. R is reported both with
lab-measured consumers only and with the full `bus_power_boundary_v1` sum. The full sum is decisive. Each ledger input
carries its evidence class and a pre-registered bound (§6.7).

## 4. Operating points

Grid axes follow the common comparison-grid concept (ṁ, p, V_d, composition, P_source). The P5 calibration-nuisance
dimensions (registration, coil shape, beam-efficiency reading, facility-ingestion interpretation) are **never** axes.

| axis | role | levels | values |
|---|---|---|---|
| ṁ | set | ṁ_min, ṁ_knee, ṁ_nom | **TBD — requires the IF-A5 feed envelope** (ṁ_min, ṁ_nom); ṁ_knee from the S2 knee scan (T-OP2-FALLBACK) |
| p | measured covariate | feed/source-chamber pressure (capacitance manometer), background p_b | With fixed hardware p follows ṁ and conductance; setting it independently needs a hardware change. A mismatch with IF-A5 `p_feed_Pa` limits applicability. |
| V_d | set | V_nom; V_hi for Hall-only only | **TBD — requires the Hall design point and the bus allocation**; V_hi must bracket source-on bus power |
| composition | set | N₂; air surrogate | Air surrogate = N₂ + O₂ at the IF-A5 oxygen mass fraction (O + O₂ supplied as O₂): **TBD — requires IF-A5**. No atomic O (limitation). Xe as anode propellant is outside the minimum. |
| P_source | set (source arms) | off, lo, hi | P_hi: **TBD — requires the source allocation in `bus_power_boundary_v1`**; P_lo = max(lowest stable source power at that flow, 0.5·P_hi) (T-PLO-FRACTION) |

| point | ṁ | V_d | gas | P_source | why |
|---|---|---|---|---|---|
| OP1 | ṁ_min | V_nom | N₂ | off, lo, hi | lower edge of the feed envelope; Hall-only ionization weakest; tests whether the source lets the discharge run where Hall-only can't (ENABLES) |
| OP2 | ṁ_knee | V_nom | N₂ | off, lo, hi | Hall-only sustainment knee; hypothesised sign change of the source benefit (hypothesis) |
| OP3 | ṁ_nom | V_nom | N₂ | off, lo, hi | nominal feed; the other side of the break-even surface; also the S1b re-mount point |
| OP2H | ṁ_knee | V_hi | N₂ | Hall-only | iso-power reference |
| OP3H | ṁ_nom | V_hi | N₂ | Hall-only | iso-power reference |
| OP5 | ṁ_knee | V_nom | air surrogate | off, hi | composition transfer at the most sensitive flow |

**Knee scan (S2, HW-0, N₂, V_nom).** 5 flow levels (T-KNEE-LEVELS) from ṁ_nom down to ṁ_min and back up, as a
hysteresis check. ṁ_knee is the lowest level sustained in both directions. If every level is sustained, ṁ_knee is the
midpoint of ṁ_min and ṁ_nom. If no level is sustained, ṁ_knee = ṁ_nom and every point becomes a test of whether the
source lets the discharge run (ENABLES).

**Run matrix** (`experiment_draft.json` rows R01–R40), per block:

| configuration | conditions | readings | content |
|---|---|---|---|
| HW-0 (`hall_only`) | 10 | 10 | OP1, OP2, OP3, OP5, OP2H, OP3H; S5 elevated-p_b at OP2, OP3; S6 re-installation check at OP2, OP3 |
| HW-RF | 15 | 21 | OP1–OP3 × {off, lo, hi}; OP5 × {off, hi}; S5 at OP2, OP3 × {off, hi} |
| HW-ECR | 15 | 21 | as HW-RF |

- **Readings.** In a source configuration every visit of an operating point is bracketed: off, lo, hi, off (or off,
  hi, off). The leading off reading is the installed-off condition, and the trailing one brackets drift. That is why
  the 40 conditions per block need 52 readings. The counts in `derived_numbers.run_counts` use this rule
  (`run_matrix.reading_rule`).
- **Families.** Primary: 7 source-on conditions per arm, m = 14. Iso-power: OP2, OP3 × {lo, hi} per arm, m = 8.
  Facility (S5): OP2, OP3 × hi at elevated p_b per arm, m = 4.
- **Confirmation subset** for a stop candidate: {OP1, OP2, OP3, OP5} × {off, hi} = 8 conditions (12 readings) per arm.
- **Bench** (S3, Hall discharge off): OP1–OP3 × {lo, hi} and OP5 × hi per arm, 7 conditions (15 readings with
  source-off probe zeros) per arm. These are exactly the source levels that have a Hall-on counterpart.

**Why not fewer.**

- One flow cannot straddle a break-even that depends on how well Hall-only ionizes. ṁ_min and ṁ_nom are the envelope
  edges, and ṁ_knee is where the sign is most likely to change.
- One source power cannot give the marginal yield, and C_del's dependence on power is unknown.
- V_hi only on Hall-only is the cheapest iso-power reference.
- Air at a single point and power is a transfer check, not a map.
- Dropping HW-0 would leave `hall_only` unmeasured (installation effect).

## 5. Measurements and instruments

**Mapping onto `bus_power_boundary_v1`.** The contract (`abep_sim/arch_boundary.py`, power-boundary lane) is
`bus_power_ledger(arch, loads, efficiencies)`; the lane brief writes the same call as `ledger(…)`. It takes, per
component, the load-side power at the component's load plane and the bus-to-load efficiency, and it returns
P_bus = Σ P_load/η. Every component goes through it on the same basis:

| component | load plane (contract) | load in this experiment | efficiency |
|---|---|---|---|
| `hall_discharge` | anode–cathode terminals at the thruster, V_d × I_d | measured (M2) | ledger, same in all arms |
| `hall_magnet`, `cathode_keeper`, `cathode_heater` | coil / keeper / heater terminals | measured (M2) | ledger, same in all arms |
| `rf_source` | net RF power (forward − reflected) at the coil/antenna feed terminals | measured (M3) at the load plane, or reconstructed from M3 upstream minus the matching-network and cable loss characterised in S1a | ledger (bus → DC supply → generator → matching → cable) |
| `ecr_source` | net microwave power at the coupling-structure input | as `rf_source` (isolator and feed-line loss) | ledger |
| `ecr_magnet` | resonance-coil terminals | measured (M2); 0 W for a permanent magnet | ledger (1 for a permanent magnet) |
| `flow_control`, `compressor`, `housekeeping` | actuator terminals / motor-drive input / controller | ledger inputs (lab hardware isn't flight hardware), same in all arms | ledger |
| `thermal_control` | heater / active thermal terminals | ledger input per arm with evidence class | ledger |

No lab converter's own efficiency enters the decisive R_arch. The lab generator's DC input (M2) gives a measured
η_lab = P_load / P_DC,in. That value is evidence for the ledger efficiency and feeds only the secondary R_lab.

| id | quantity | instrument | practice / requirement |
|---|---|---|---|
| M1 | thrust T | pendulum-type thrust stand (hanging, inverted or torsional) with in-situ calibration | REF-POLK2017: end-to-end in-situ calibration under vacuum; at least ten calibrations before and after operation; zero with power and flow off before thermal drift; error budget reported. Requirement: u_T per reading ≤ §6 value at the n fixed at LOCK-2. Range **TBD — requires the Hall design** |
| M2 | load-plane DC power per DC consumer | multi-channel DC power analyzer or calibrated shunt/divider pairs, simultaneous sampling, at each DC consumer's load plane; plus the DC input of each DC-fed lab generator (efficiency evidence only) | same channels for all arms; traceable calibration (owner to specify). u_P ≤ §6; common-consumer scale (G4) Type B from certificates |
| M3 | net RF / microwave power at the source load plane | directional coupler + forward and reflected power sensors at the coil/antenna feed terminals or coupling-structure input; else upstream, with the loss to the load plane characterised in S1a (evidence class *reconstructed*) | load = forward − reflected at the load plane; source scale u_src (G3) ≤ §6 |
| M4 | I_d(t) | current probe, time-synchronised DAQ | sampling **TBD — requires the S1 I_d spectrum**; traces archived for every reading; T-SUSTAIN uses extinction; oscillation reported, non-gating |
| M5 | I_src, I_del | guarded Faraday collector/probe array at the source exit; downstream Faraday sweep / integrating collector with the Hall discharge off | REF-BROWN2017 Table A1 (ion-saturation bias checked across the plume, SEE and gap corrections, alignment, cabling). The full practice asks for at least four background pressures and four distances; the minimum set uses fewer and says so |
| M6 | ion energy distribution | RPA at interstage/channel exit (S3) and far field (S4, both states) | explanatory |
| M7 | species current fractions N₂⁺, N⁺, O₂⁺, O⁺ | E×B probe, with an accelerating bias for low-energy interstage ions | REF-ROVEY2025: at low energy the four air ions (m/q 32, 28, 16, 14) are not all resolved without an accelerating bias; the CEX correction's dominant uncertainty is the background neutral density from ion gauges (typically 10–20 %). Species if possible; explanatory |
| M8 | far-field current density, beam current, divergence | far-field Faraday sweep, both states | REF-BROWN2017 (far field > 4 channel diameters); decomposes ΔT; published per point |
| M9 | p_b and feed/source pressure p | hot-cathode ion gauge(s) for p_b; capacitance manometer for p | REF-DANKANICH2017 Sec. IV.A: in-chamber, line of sight to the thruster, near the wall at the exit plane (≥ 0.6 chamber radii off axis, ≥ 1 m from the thruster OD), ≥ 10 Hz, 3 s averages, no reading within 2 min of a > 10 % flow change; calibrate on the gas of interest where practical (nitrogen is the industry-standard calibration gas, Sec. II.A.2); record wall temperature |
| M10 | mass flow | thermal MFCs calibrated for N₂, O₂, Xe (cathode) | REF-SNYDER2017 (title/DOI only; verify). Identical setpoints across arms |
| M11 | B(z) | Hall-probe gaussmeter on a positioning stage | every configuration, source magnet on/off where applicable, operating coil currents, before and after; published with coil currents (the gap that made P5 non-identifiable). Range **TBD — requires the Hall design** |
| M12 | temperatures | thermocouples on anode/body, magnet circuit, source, generator, cathode mount | settling (T-SETTLE), `thermal_control` evidence |
| M13 | species/background (optional) | OES in source/interstage; RGA | qualitative; O₂ background check |
| M14 | electrical environment | cathode-to-ground, anode-to-ground potentials | recorded every reading; same grounding for all arms |

## 6. Uncertainty targets, derived from the break-even inequality

### 6.1 Variance model, and how each component is evaluated

`sigma_lnR()` and `nu_eff_lnR()` in `minexp_numbers.py` implement the model (first order) for ln R_arch:

  σ²(ln R) = 2u_T²/n + 2u_P²/n + (f_src·u_src)² + Σ_c (w_c·u_c)² + 2u_inst²

| group | term | evaluation | degrees of freedom | averages down? |
|---|---|---|---|---|
| G1 thrust random (block-to-block within one installation, incl. zero drift and day effects) | 2u_T²/n | Type A, in campaign | n − 1 per condition and side, estimated with G2 from the n block values of ln(T/P_bus) of that condition (no pooling across conditions) | yes |
| G2 bus-power random | 2u_P²/n | Type A, in campaign (jointly with G1) | as G1 | yes |
| G3 source load-plane power scale (sensor and coupler calibration; reconstructed matching/cable loss) | (f_src·u_src)², f_src = P_src,bus/P_bus,X | Type B (certificates, S1a characterisation) | ∞: treated as exactly known (REF-GUM2008 G.4.3); if the owner states a reliability Δu/u at LOCK-1, ν = ½(Δu/u)⁻² (REF-GUM2008 Eq. G.3) | no; never cancels |
| G4 common-consumer load-plane meter scale | Σ(w_c·u_c)², w_c = \|P_c,X/P_bus,X − P_c,0/P_bus,0\| | Type B | as G3 | no; partially cancels |
| G5 installation (re-mount) reproducibility of ln(T/P_bus), incl. stand re-calibration shifts | 2u_inst²: R_arch compares two installations, each with its own offset | Type A, S1b re-mount series (§6.4) | K − 1 (K = T-S1-REMOUNT-CYCLES = 6 → 5) | no; removed by OPTION-DIVERTER |

Ledger inputs (efficiencies, unmeasured loads) are **not** variance terms. They are conditioning inputs fixed at
LOCK-1 (§6.7).

### 6.2 Interval and classes

For each compared condition, ln R̂ = mean_b ln(T/P_bus)_X,b − mean_b ln(T/P_bus)_0,b, and σ̂² = s_X²/n + s_0²/n +
(f_src·u_src)² + Σ(w_c·u_c)² + 2u_inst². Here s_X and s_0 are the per-condition block SDs. The effective degrees of
freedom ν_eff come from the Welch–Satterthwaite formula (REF-GUM2008 Eq. G.2b). The half-width is h = k·σ̂, where k
is the two-sided Bonferroni **Student-t** quantile at ν_eff for the family's m. Simultaneous coverage is approximately
1 − α. The approximation is Welch–Satterthwaite's (REF-GUM2008 G.4.1), and the coverage is conditional on the Type B
components being stated correctly. r1 used the normal quantile (2.9137 for m = 14), which treated every component as
known. At 3, 2 or 7 degrees of freedom the Bonferroni t quantile is 8.37, 16.7 or 4.30, so that was anti-conservative.

| class | condition |
|---|---|
| EQUIVALENT | the whole interval lies inside (−δ, +δ) |
| SOURCE_BETTER | not EQUIVALENT, and the lower bound > 0 |
| SOURCE_WORSE | not EQUIVALENT, and the upper bound < 0 |
| UNRESOLVED | anything else |

**UNRESOLVED is impossible if h < δ/2.** If a point isn't EQUIVALENT, then |x| + h ≥ δ, so |x| ≥ δ − h > h, and the
interval excludes 0. With h ≥ δ/2 a gap δ − h ≤ |x| ≤ h opens. The script checks both cases numerically: 0 unresolved
grid points at h = 0.999·δ/2, 668 at h = 0.75·δ. **Planning requirement: σ(ln R) < δ/(2k).** The realised h can still
exceed δ/2 when a realised estimate exceeds its plan. Such points are UNRESOLVED, which is a legitimate outcome.

These size classes are what the owner reads. The stop rule doesn't use them; it uses the sign statement of §9.

### 6.3 Derived numbers (planning)

PROPOSED inputs: δ = 0.05, family-wise α = 0.05, T-BUDGET-SHARES = five equal shares (G1–G5, 0.2 each), n = 4–8
blocks (even), K = 6 re-mount cycles. The planning ν_eff puts every group exactly at its share (Type A share 0.4 with
n − 1 per side, re-mount share 0.2 with K − 1, Type B share 0.4 with ν = ∞). That is the smallest ν_eff consistent
with the budget being met, so k is conservative. Values (`derived_numbers.plan_by_n`):

| quantity | n = 4 | n = 6 | n = 8 |
|---|---|---|---|
| planning ν_eff | 28.8 | 41.7 | 51.5 |
| k (primary, m = 14) | 3.1727 | 3.0887 | 3.0539 |
| σ_max(ln R) = δ/(2k) | 0.00788 | 0.00809 | 0.00819 |
| per-group share σ_max·√0.2 | 0.00352 | 0.00362 | 0.00366 |
| u_T max per reading | 0.50 % | 0.63 % | 0.73 % |
| u_P max per reading | 0.50 % | 0.63 % | 0.73 % |
| u_inst max per installation | 0.25 % | 0.26 % | 0.26 % |
| k, σ_max (iso-power, m = 8) | 2.9498, 0.00848 | 2.8803, 0.00868 | 2.8514, 0.00877 |
| u_interp max (chord model error) | 0.31 % | 0.31 % | 0.31 % |
| k, σ_max (facility, m = 4) | 2.6641, 0.00938 | 2.6108, 0.00958 | 2.5885, 0.00966 |

For reference, the known-variance limit (ν = ∞) is k = 2.9137. Source-scale limit (G3 share, n = 4):
u_src ≤ 0.00352 / f_src. That is 3.52 %, 1.76 %, 1.17 % and 0.88 % for f_src = 0.1, 0.2, 0.3 and 0.4 (planning
values, hypothetical). S3 screen (one-sided, α = 0.05): k_screen lies between 1.6449 (all components known) and
2.3534 (all Type A with ν = 3).

### 6.4 The installation term G5 and the S1b re-mount series

R_arch compares HW-X with HW-0, which are different installations. The installation offset doesn't average down with
blocks. r1 estimated it from one end-of-campaign re-installation, which gives about one degree of freedom, comes after
every score-bearing reading, and leaves D0 unevaluable. r2 measures it first:

- **S1b** (not score-bearing, in the Hall-on facility, on the S2/S4/S5 stand, with the same mount procedure): K = 6
  re-installations of HW-0 at OP3 (T-S1-REMOUNT-CYCLES). Each cycle is: vent; remove and re-install the spacer and the
  thruster mount exactly as a configuration change does; pump down; condition; settle; in-situ calibration; r = 3
  readings (T-S1-READINGS-PER-CYCLE).
- u_inst = SD of the K cycle means of ln(T/P_bus), with ν_rm = K − 1 = 5. This is conservative, because it also
  contains the within-cycle scatter divided by r. The within-cycle readings (K(r − 1) = 12 degrees of freedom) give the
  u_T, u_P used to fix n at LOCK-2. Scoring uses the campaign's own per-condition scatter.
- **S6** re-installs HW-0 at the end (R09, R10) as a check (T-REMOUNT-CHECK, D6), never as the estimate.

Effect of K on k (n = 4, `derived_numbers.k_primary_by_remount_cycles`):

| K (ν_rm) | planning ν_eff | k (primary) |
|---|---|---|
| 3 (2) | 21.4 | 3.2720 |
| 6 (5) | 28.8 | 3.1727 |
| 11 (10) | 32.6 | 3.1407 |

The requirement u_inst ≤ 0.25 % (installation-to-installation reproducibility of thrust per bus watt) is demanding.
Whether a stand and mount achieve it is **TBD — requires S1b**. If they don't, D0 fails and the owner widens δ,
improves the mount, or adopts OPTION-DIVERTER (which sets the G5 share to 0 at LOCK-1).

### 6.5 Iso-power and facility families

**Iso-power (m = 8).** ln R_iso = ln T_X − ln T0_iso. T0_iso lies on the Hall-only chord, with
λ = (P_X − P_nom)/(P_hi − P_nom) and chord elasticity ε = slope·P_X/T0_iso. To first order (`var_lnR_iso_random()`):

  var = (u_T²/n)(1 + a_T² + b_T²) + ε²(u_P²/n)(1 + a_P² + b_P²) + ε²[(f_src·u_src)² + Σ(w_c·u_c)²] + 2u_inst² + u_interp²,

with a_T = (1−λ)T_nom/T0, b_T = λT_hi/T0, a_P = (1−λ)P_nom/P_X and b_P = λP_hi/P_X. Because a + b = 1 with a, b ≥ 0,
a² + b² ≤ 1. The iso variance is therefore at most σ²(ln R_arch) + u_interp² whenever |ε| ≤ 1. ε is computed from the
measured data at every point, and scoring uses the full formula. u_interp is the Type B model error of the linear
chord (T-ISO-INTERP). With every R_arch group at its share, the budget leaves u_interp ≤ √(σ_max,iso² − σ_max²) =
0.31 % for it. How u_interp is obtained is an owner decision at LOCK-1. The options are a pre-registered bound, or a
V_mid reading on HW-0 at OP2 and OP3 (+2 conditions per block) whose deviation from the chord bounds it.

**Facility (m = 4).** S5 classifies R_arch at elevated p_b with k_facility at each condition's ν_eff. m stays at 4
even if an arm stops (conservative).

### 6.6 Floor, and blocks needed

**Floor that no number of blocks beats.** As n → ∞ the random terms vanish and ν_eff → 45.0 (the re-mount and Type B
shares at their ratio). This gives k = 3.0751 and δ_floor = 2k·s_nonavg, where s_nonavg combines G3–G5:
s = 0.005 → 0.0308; s = 0.01 → 0.0615; s = 0.02 → 0.123.

**Blocks needed** (u_T = u_P = u; G3–G5 at their shares; even, at least 4; k re-evaluated at each n):

| δ | u = 0.5 % | u = 1 % | u = 2 % |
|---|---|---|---|
| 0.05 | 6 | 16 (> 8) | 58 (> 8) |
| 0.10 | 4 | 6 | 16 (> 8) |

In words: at δ = 0.05 the campaign needs about 0.5 % per-reading repeatability and 6 blocks. At 1 % it needs δ = 0.10
or many more blocks. **Achievability is TBD — requires the S1 values and calibration certificates.** No instrument
accuracy is claimed here. D0 decides with the actual S1 values: `readiness_n()` returns the smallest admissible n with
k(n)·σ(n) < δ/2, with k from the Welch–Satterthwaite ν_eff of the actual S1 components. If there is none, D0 fails.

### 6.7 Ledger conditioning

Flight PPU and generator efficiencies and unmeasured loads are not measured here. Classes are therefore computed at
the LOCK-1 nominal ledger inputs, and each is qualified by T-LEDGER-SENSITIVITY. R_arch is monotone in every ledger
input when the others are held fixed, so its extremes over the pre-registered box lie at vertices. The analysis
evaluates every vertex. A class is LEDGER_ROBUST if the class and the stop support are the same at every vertex;
otherwise it is LEDGER_CONDITIONAL. η_src,be (§3.3) states the break-even source-chain efficiency directly.

### 6.8 Other notes

**Why no facility correction enters the decisive metric.** In P5-N₂ the ingestion correction to I_d was 2.2–3.7 %
(docs/EVIDENCE.md register, reconstructed from Brabston Eqs. 13/14). The facility-ingestion interpretation became a
calibration-nuisance dimension (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`). That is the same order as
δ. So the decisive metric uses raw paired data at the measured p_b, and the p_b sensitivity is measured directly (S5).

**S3 screen uncertainty.** u(ln C_del)² = u(P_src,bus)² + u(I_del)²; u(ln C\*_ub)² = u_abs(P_bus,0)² + u_abs(T_0)².
These are absolute calibrations, so scale terms don't cancel. The screen's k is the one-sided Student-t quantile at
the Welch–Satterthwaite ν_eff of these terms. A larger u(I_del) never creates a stop candidate: the screen errs toward
running more.

## 7. Randomisation and repeatability

- **Configuration order.** S1b runs on HW-0. Then HW-0 (S2) comes first and HW-0 (S6) last. A seeded coin,
  published at LOCK-1, orders HW-RF and HW-ECR between them.
- **Blocks.** A block visits every operating point of the current configuration and stage once. The operating-point
  order is a seeded permutation, re-drawn for each block. n is fixed at LOCK-2 by `readiness_n()` from the S1 values,
  between 4 and 8 and even, and never changed after the first score-bearing reading.
- **Within a point.** The order is off, lo, hi, off in odd blocks and off, hi, lo, off in even blocks. The two off
  readings bracket drift, and linear drift cancels over block pairs (hence an even n). The thrust zero is taken at
  the end of each point visit (REF-POLK2017). The reading counts include the bracketing readings.
- **Repeatability.**
  - The S1b re-mount series gives u_inst, and the S6 re-installation checks it.
  - Blocks run on different days where possible, and the day is recorded.
  - The knee scan runs in both directions.
- **Interim looks.** D2 and D3 are pre-registered interim looks. The frozen analysis script runs on a hashed interim
  dataset, and the result is logged and never revised.
- **Blind scoring.** The raw dataset is frozen and hashed, then scored once by the frozen, hash-locked analysis
  script, which recomputes every class. This mirrors the P5-N₂ practice
  (`hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json`).

## 8. Facility controls

- **Background pressure.** M9 follows REF-DANKANICH2017, and every reading carries p_b. Base p_b must satisfy
  T-PB-MAX, set at LOCK-1 from the facility specification (**TBD**). The Sec. V guidance values in that paper are
  SPT-100/xenon specific; its authors note that their basis does not address other thrusters and that the data don't
  justify absolute requirements for general designs. A reading above T-PB-MAX is NOT_SCOREABLE_FACILITY, which is not
  evidence against any arm.
- **S5 facility-effect check.** At OP2 and OP3, for Hall-only and every non-stopped source arm at P_hi, p_b is raised
  to 2 × base (T-PB-ELEV-FACTOR). The method is REF-DANKANICH2017 Sec. IV.B: supplemental primary gas ≥ 2 m downstream,
  with a pumping surface between the injection and the gauge. The elevated-p_b comparisons form the facility family
  (m = 4, §6.5). If the class and the stop support are unchanged, the condition is FACILITY_ROBUST; otherwise it is
  FACILITY_CONDITIONAL. No ingestion model is applied to rescue a class (the P5-N₂ lesson).
- **Publish what P5 lacked.** B(z) maps and coil currents, channel geometry, I_d traces, per-point divergence, gauge
  location and calibration.
- **Electrical and gas.** Grounding and cable routing are the same for every arm (M14). Facility compatibility with O₂
  flow (pump type, safety case) is **TBD — requires facility data**.

## 9. Sequential decision tree and stopping rules (all PROPOSED)

```
S0  pre-registration LOCK-1 (thresholds, rules, ledger inputs + bounds, frozen script, seed, S1 plan) .. not score-bearing
S1  qualification .................................................................................. not score-bearing
    S1a no plasma: calibrations (M1, M2, M3 load plane, M9, M10), B(z) per configuration
    S1b Hall-on on HW-0 at OP3: K re-installations x r readings -> u_inst (K-1 dof), u_T, u_P, settling, p_b
    D0  T-READINESS: calibrated; B(z) mapped; readiness_n(S1 values) returns n <= T-N-MAX; p_b <= T-PB-MAX
        fail -> OWNER (no score-bearing run)            pass -> LOCK-2 (S1 values + n) -> S2
S2  hall_only on HW-0: knee scan (down + up), R01-R06
    D1  fix mdot_knee (T-OP2-FALLBACK); per-condition sustainment (T-SUSTAIN)
S3  source bench, Hall discharge off (both arms): P_src,load, P_src,bus, I_src, I_del, eta_ts, C_del
    G-SRC  hard gate (measured): source can't sustain within P_hi at a flow (bench and one Hall-on try)
           -> INFEASIBLE_AT_POINT; at every flow -> arm STOPPED
    D2  T-SCREEN-RULE: hall_only SUSTAINED everywhere AND ln C_del - ln C*_ub > k_screen*u at every bench condition
        yes -> STOP_CANDIDATE: S4 confirmation subset only       no -> S4 full
S4  paired Hall-on, randomised: R_arch, R_within, R_install, R_iso, y, kappa, C*, eta_src_be, sustainment classes
    D3  T-STOP-RULE over the tested set T (interim look):
        every condition in T stop-supporting: upper bound of ln R_arch < 0 (<=> C_del > C* with simultaneous
          confidence) or DISABLES / NEITHER_SUSTAINED / INFEASIBLE_AT_POINT; at least one upper bound < 0 or DISABLES
        AND no R_iso lower bound > 0   AND the same at the most favourable ledger vertex
        AND (subset only) y - k_s*u(y) <= y_max and kappa + k_s*u(kappa) >= 0 at every subset condition
        yes -> arm STOPPED (conditions never run: NOT_TESTED)   no, from subset -> rest of S4   no -> S5
    D5  EXPERIMENT_MOOT if hall_only is sustained nowhere and no arm ENABLES anywhere -> report to owner
S5  facility check at 2x p_b (OP2, OP3), facility family
    D4  T-FACILITY-ROBUST: class and stop support unchanged -> FACILITY_ROBUST, else FACILITY_CONDITIONAL
S6  HW-0 re-installation (R09, R10) -> D6 T-REMOUNT-CHECK -> freeze raw dataset (hash) -> score once -> report
```

**Per-condition classes.** The sustainment outcome is aggregated per condition over the n blocks: SUSTAINED in every
block, NOT_SUSTAINED in none, SUSTAINMENT_MIXED otherwise.

| `hall_only` | source-on | class |
|---|---|---|
| SUSTAINED | SUSTAINED | size class from R_arch (§6.2) |
| NOT_SUSTAINED | SUSTAINED | ENABLES |
| SUSTAINED | NOT_SUSTAINED | DISABLES (R undefined; the source puts out a discharge that runs without it) |
| NOT_SUSTAINED | NOT_SUSTAINED | NEITHER_SUSTAINED |
| either SUSTAINMENT_MIXED | | SUSTAINMENT_MIXED (R not scored; reported) |

INFEASIBLE_AT_POINT (G-SRC) and NOT_SCOREABLE_FACILITY override the table. NOT_TESTED marks conditions an arm never
ran because it stopped from its confirmation subset.

**Stopping rules in words.**

- An arm stops only on **measured** paired Hall-on data over its **tested set**. Every tested condition must support a
  stop, and at least one must do so through a confident R_arch < 1 or a DISABLES outcome. There must be no confident
  iso-power advantage, and all of this must hold at the ledger vertex most favourable to the arm. The whole rule is
  therefore stricter than the brief's plain wording ("the delivered-ion cost exceeds the break-even cost at all tested
  points"): that wording is condition (a) only.
- Per condition, stop support is the **sign statement**: the simultaneous upper bound of ln R_arch is below 0. By the
  break-even identity (§3.2) this is the same condition as "C_del > C\* with simultaneous confidence" at that
  condition. It is not the size class. SOURCE_WORSE additionally requires the lower bound
  to reach −δ, so it is stricter than the sign statement. r1 conflated the two. As a result, whether an arm stopped for
  a true effect in (−δ, 0) depended on how good the repeatability turned out to be.
- Worked example (δ = 0.05, estimate −0.03, k = 2.9137 as in r1): at σ = 0.006 the interval is [−0.0475, −0.0125],
  which is EQUIVALENT and stop-supporting. At σ = 0.0072 it is [−0.0510, −0.0090], which is SOURCE_WORSE and
  stop-supporting. Under r1's rule the first case did not support a stop. Stop support is now monotone in precision: a
  smaller h never removes it from a negative estimate. The test checks this.
- An EQUIVALENT condition whose interval contains 0 blocks a stop. So does any condition that is SOURCE_BETTER,
  UNRESOLVED, SUSTAINMENT_MIXED or NOT_SCOREABLE_FACILITY.
- **Stops from the confirmation subset.** These cover only the tested conditions (P_hi). The P_lo conditions that were
  never run Hall-on are recorded NOT_TESTED. They are not evidence either way, and the report lists them. Whether a
  subset stop should require P_lo Hall-on data (+3 conditions per block per arm) is an owner decision (§15).
- **Owner alternative STOP-MARGIN.** Stop only if the upper bound < −δ. This is also monotone in precision, and more
  permissive toward arms that are within δ.
- The Hall-off screen (D2) only shrinks the Hall-on grid.
- The hard gate G-SRC stops an arm only when its source can't sustain plasma at any grid flow within its allocated power.
- If D6 fails, every cross-installation class carries REMOUNT_CHECK_FAILED. Any earlier stop is reported as taken under
  a failed check, and the owner decides whether to reopen the arm.

## 10. Pre-registration: two locks

The owner-approved successor of `experiment_draft.json` is locked twice.

**LOCK-1 (S0, before S1)** records:

1. A decision on every PROPOSED threshold and rule, with its date, including T-BUDGET-SHARES.
2. ṁ_min, ṁ_nom, composition (IF-A5), V_nom, V_hi and P_hi.
3. The ledger inputs (efficiencies, unmeasured loads), each with an evidence class, and their T-LEDGER-SENSITIVITY
   bounds. Also the f_src and w_c allocations that D0 uses.
4. T-PB-MAX and the T-ISO-INTERP choice.
5. The S1 plan (K, r, S1b point) and the instrument list.
6. The seed and the configuration-order draw.
7. The frozen analysis script (sha256) implementing §6 and §9, including `readiness_n()` and the
   Welch–Satterthwaite/Student-t interval.
8. The score-bearing rows.
9. Whether the physics track pre-registers any result as Hall-closure evidence. That is their decision, in their own
   pre-registration.

**LOCK-2 (end of S1, after D0 passes, before the first score-bearing reading)** records:

- the sha256 of LOCK-1;
- the calibration certificates, and the Type B u_src and u_c from S1a;
- the S1b values: u_T, u_P, u_inst with ν_rm = K − 1, thermal time constants, p_b;
- the n returned by `readiness_n()`, and the D0 record.

LOCK-2 may only add S1 values and what the LOCK-1 rules compute from them, without discretion. Any change to a LOCK-1
item voids LOCK-1 and restarts S0. Score-bearing data taken before LOCK-2 are excluded. The location of the lock files
is the owner's decision; it is outside `hallthruster_bridge/prereg/`, which this lane may not modify.

## 11. Minimum hardware list

1. Hall accelerator H-1, one unit. It must be the Vyovrinda design for evidence level 1. A surrogate gives level 2/3
   evidence, which transfers only through an admitted closure.
2. Cathode C-1 with keeper and heater supplies (type **TBD — requires the cathode lane**).
3. Feed: MFCs for N₂, O₂ (air surrogate) and Xe (cathode); a common manifold; a flow-equivalent spacer (HW-0) or
   OPTION-DIVERTER.
4. RF source module + interstage + RF generator (DC-fed preferred, so that its DC input gives efficiency evidence) +
   matching network.
5. ECR source module + interstage + microwave generator (DC-fed preferred) + isolator + waveguide/antenna + ECR magnet.
6. Discharge, magnet, keeper and heater supplies (lab supplies; bus conversion through the ledger efficiencies).
7. DC power-analyzer channels at every present DC consumer's load plane (and each lab generator's DC input), an I_d
   current probe, and a time-synchronised DAQ.
8. A thrust stand with an in-situ calibration system.
9. Diagnostics: Faraday collector/array at the source exit, a downstream Faraday sweep, an RPA, and an E×B probe
   (the E×B probe is optional for the minimum).
10. Directional couplers and forward/reflected power sensors for the RF and microwave load planes, plus matched dummy
    loads for the S1a load-plane characterisation (method **TBD — requires the RF/microwave design**).
11. Pressure and field instruments: ion gauge(s) calibrated on N₂, a capacitance manometer, a wall thermocouple, a
    supplemental gas injector, and a gaussmeter with a positioning stage.
12. A vacuum facility meeting T-PB-MAX at the grid flows (§12).

## 12. University facility vs larger chamber

The effective pumping speed needed is S_eff = Q / p_b,max, with Q = (ṁ/m) k_B T at the gauge-wall temperature. Per mg/s
of flow, at T = 300 K (assumed):

| gas | p_b = 1.0e-5 Torr | 1.3e-5 Torr | 5.0e-5 Torr |
|---|---|---|---|
| N₂ | 66,818 L/s | 51,399 L/s | 13,364 L/s |
| O₂ | 58,466 L/s | 44,974 L/s | 11,693 L/s |

The three pressures come from REF-DANKANICH2017 Sec. V. 5e-5 and 1.3e-5 Torr are early SPT-100 guidance for
performance and near-field plume measurements. 1e-5 Torr is the level below which the SPT-100 transportability study
found the thrust-slope change identifiable. All three are xenon/SPT-100 specific and are used here only as planning
scenarios. The cathode flow adds load, and the gauge reading is gas-specific. S_eff scales linearly with the total
flow, which is **TBD — requires the IF-A5 envelope**.

| stage | needs | smaller (university-class) facility? |
|---|---|---|
| S1a calibrations, B(z), load-plane characterisation | no plasma; B(z) mapping is magnetostatic (room temperature; hot-state effects TBD) | yes |
| S1b Hall-on re-mount series | the same facility, stand and mount procedure as S2/S4/S5 (it measures that facility's installation reproducibility) | only if that facility also does S2/S4/S5 |
| S3 source bench | vacuum at grid flows with CEX loss on the collector path bounded (attenuation form exp(−n₀σz), REF-ROVEY2025 Eq. 37; σ for N₂⁺ on N₂ **TBD — requires a cited cross section**) | possibly, if its S_eff meets that bound (TBD) |
| S2, S4, S5 Hall-on thrust | p_b ≤ T-PB-MAX at grid flows, plus the ability to raise p_b | S_eff from the table × total flow; likely a larger chamber at nominal flow (TBD) |

**IIST (published information only).** REF-IIST-WEB, accessed 2026-09-26, states three things:

- IIST collaborates in the LPSC-led "High Thrust Electric Propulsion" inter-centre project on the design, development,
  testing and implementation of diagnostic tools for characterising the Stationary Plasma Thruster being developed by
  LPSC.
- It developed a back-diffusion plasma source and an ion beam source in-house.
- Its plasma facility can be tuned to lower-ionospheric conditions ("India's only ionospheric plasma simulator").

No chamber dimensions, base pressure or pumping speed were found in published sources. Suitability for any stage is
**TBD — requires the facility's specification**. Obtaining it, and any discussion, are the owner's decision; this lane
made no contact. Nothing here commits any institution, facility or person. The IIST package lane (`docs/experiments/`)
owns facility-specific packaging.

## 13. Relation to other lanes (referenced by path; none is required by this draft or its test)

| path | relation |
|---|---|
| `docs/architecture_comparison/experiment_protocol/` | Full common-condition protocol (XPROT). It was read-only from that lane's committed draft (commit `1428265`, not merged, may change). The two are **not** in a strict subset relation, and the owner reconciles them. (1) Boundary basis: XPROT measures every consumer at its DC input from the common bus. Its ids are `hall_ppu_input`, `magnet_supplies`, `rf_generator_input`, `microwave_source_input`, `cathode_heater`, `cathode_keeper`, `valves_flow_control`, `thermal_control` and `housekeeping`; there is no compressor row. Where a lab supply replaces a bus-fed converter, it reconstructs P_out/η_conv. This draft follows `abep_sim/arch_boundary.py` (load plane plus ledger efficiency). Mapping: `hall_discharge` → `hall_ppu_input`; `hall_magnet`, `ecr_magnet` → `magnet_supplies`; `rf_source` → `rf_generator_input`; `ecr_source` → `microwave_source_input`; `flow_control` → `valves_flow_control`; the rest by name. (2) Classes: XPROT uses HIGHER / LOWER / NOT_DISTINGUISHED against an owner-TBD δ_m1, with a t-interval on replicate-level paired log-ratios and Holm step-down. This draft uses size classes against δ, a sign statement for stops, and Bonferroni Student-t intervals at Welch–Satterthwaite dof. (3) Hardware: XPROT prefers CFG-A (arms switched without venting) with CFG-B (separate builds, sham controls, replicate builds) as fallback. This draft uses separate configurations with OPTION-DIVERTER as its no-vent option. It adds the S3 break-even screen, the sequential stop rule and the S1b re-mount series. |
| `docs/experiments/` | IIST experiment package: facility-specific packaging of any stage. |
| `abep_sim/arch_boundary.py` | `bus_power_boundary_v1` contract: component names, load-plane definitions (`COMPONENT_DEFINITIONS`) and `bus_power_ledger(arch, loads, efficiencies)` (the lane brief's `ledger(…)`). Read-only from the power-boundary lane (commit `a2a1396`). |
| `abep_sim/arch_compare.py` | Comparison harness; this experiment's measured results are candidate inputs once pre-registered. |
| `abep_sim/thermal_life.py`, `docs/evidence/wall_life/`, `docs/evidence/cathode/` | Milestone C inputs; C-1 choice. |
| `docs/evidence/rf_source/`, `docs/evidence/ecr_source/`, `docs/evidence/hall_sustainment/` | Decide whether this experiment is needed at all; set expectations for S2/S3. |
| `schemas/interfaces/upstream_icd_v1.json` (IF-A5, IF-X2), `schemas/ledgers/` | Feed-state fields; ledger schemas for the bus sum. |
| `docs/hallmap/` | B(z) and geometry measured here are Hall-map inputs for Vyovrinda hardware (milestone B). |

## 14. Thresholds register (all PROPOSED; values in `experiment_draft.json`)

| id | proposal |
|---|---|
| T-DELTA | δ = 0.05 on ln R |
| T-ALPHA-FW | family-wise α = 0.05, Bonferroni simultaneous Student-t intervals at Welch–Satterthwaite dof |
| T-ALPHA-SCREEN | one-sided α = 0.05 for the S3 screen |
| T-N-MIN / T-N-MAX | 4 / 8 blocks (even for drift cancellation) |
| T-BUDGET-SHARES | 0.2 each for G1–G5 (keys must equal the variance groups; shares sum to 1) |
| T-S1-REMOUNT-CYCLES | K = 6 re-installations in S1b |
| T-S1-READINGS-PER-CYCLE | r = 3 |
| T-PB-ELEV-FACTOR | 2 × base p_b in S5 |
| T-PB-MAX | **TBD — requires an owner decision at LOCK-1**, checked at D0 |
| T-KNEE-LEVELS | 5 levels |
| T-OP2-FALLBACK | ṁ_knee rule (§4) |
| T-PLO-FRACTION | P_lo = max(lowest stable, 0.5·P_hi) |
| T-SUSTAIN | no extinction or restart during the dwell (dwell **TBD — requires S1**); per condition over blocks |
| T-SETTLE | **TBD — requires S1 thermal time constants** |
| T-ISO-INTERP | **TBD — requires an owner decision** (bound or V_mid reading) |
| T-READINESS, T-SCREEN-RULE, T-STOP-RULE, T-FACILITY-ROBUST, T-REMOUNT-CHECK, T-LEDGER-SENSITIVITY, G-SRC, D5 | §6, §9 |

## 15. Open owner decisions

1. Approve, change or reject every PROPOSED threshold and rule, including T-BUDGET-SHARES.
2. Supply ṁ_min, ṁ_nom, composition (IF-A5), V_nom, V_hi and P_hi; the ledger inputs with evidence classes and bounds;
   and the f_src / w_c allocations used by D0.
3. Choose between the HW-0 spacer with K S1b re-installations and OPTION-DIVERTER.
4. Choose the stop rule: sign form (proposed) or STOP-MARGIN.
5. Decide whether a subset stop requires Hall-on data at P_lo (+3 conditions per block per arm).
6. T-ISO-INTERP: a pre-registered chord bound, or a V_mid reading on HW-0.
7. Decide whether the tested Hall is the Vyovrinda design or a surrogate.
8. Choose the facility per stage, and decide whether to seek any facility's specification (owner's channel).
9. Decide whether to add Xe anode operation or a second V_d on the source arms (outside the minimum).
10. Reconcile this draft with the full-protocol lane (boundary basis, classes, multiplicity, CFG-A/B).
11. Decide where the lock files live.

## 16. Compliance

- No Hall transport closure, screening candidate or withdrawn 0-D number is used as a performance source; there is no
  retuning.
- P5 calibration nuisance is never an axis.
- Hall-closure uncertainty doesn't leak upstream: the feed state is a fixed IF-A5 input, identical across arms, and
  upstream loads are identical ledger inputs.
- No arm is eliminated except by the measured gate G-SRC or the measured stop rule D3 over its tested set. Untested
  conditions are NOT_TESTED, and no winner is declared.
- Every number is sourced with an evidence class or marked TBD, and the derived numbers are reproducible by
  `minexp_numbers.py --check`. Missing or inconsistent inputs raise.
- Nothing is wired into `archengine`; no frozen data, golden, prereg or campaign file is touched.

## 17. References (accessed 2026-09-26 unless stated)

- **REF-POLK2017.** J. E. Polk, A. Pancotti, T. Haag, S. King, M. Walker, J. Blakely, J. Ziemer, "Recommended Practice
  for Thrust Measurement in Electric Propulsion Testing", *J. Propulsion and Power* 33(3):539–555 (2017),
  doi:10.2514/1.B35564. Full text via PMC7839308; cited statements checked against it; wording paraphrased.
- **REF-DANKANICH2017.** J. W. Dankanich, M. Walker, M. W. Swiatek, J. T. Yim, "Recommended Practice for Pressure
  Measurement and Calculation of Effective Pumping Speed in Electric Propulsion Testing", *J. Propulsion and Power*
  33(3) (2017), doi:10.2514/1.B35478. Full-text PDF from the authors' lab page, text extracted (Secs. II.A.2, IV.A,
  IV.B, V).
- **REF-BROWN2017.** D. L. Brown, M. L. R. Walker, J. Szabo, W. Huang, J. E. Foster, "Recommended Practice for Use of
  Faraday Probes in Electric Propulsion Testing", *J. Propulsion and Power* 33(3):582–613 (2017),
  doi:10.2514/1.B35696. Full-text PDF from the authors' lab page (Table A1).
- **REF-SNYDER2017.** J. S. Snyder et al., "Recommended Practice for Flow Control and Measurement in Electric
  Propulsion Testing", *J. Propulsion and Power* 33(3) (2017), doi:10.2514/1.B35644. Title and DOI only; content not
  read (verify).
- **REF-ROVEY2025.** J. L. Rovey, T. Yamauchi, W. Huang, R. E. Thomas, W. J. Hurley, S. C. Farnell, S. J. Thompson,
  C. C. Farnell, C. C. Farnell, W. P. Brabston, "Recommended Practice for Use of ExB Probes in Electric Propulsion
  Testing", IEPC-2025-483, 39th IEPC, London, 14–19 Sept 2025.
  https://januselectricpropulsion.ae.gatech.edu/sites/default/files/2025-10/IEPC-2025-483_Rovey.pdf (full text; Sec.
  V.A and Fig. 8 air example, Sec. VI.C Eq. 37, Sec. VI.D).
- **REF-SHABSHELOWITZ2014.** A. Shabshelowitz, A. D. Gallimore, P. Y. Peterson, "Performance of a Helicon Hall
  Thruster Operating with Xenon, Argon, and Nitrogen", *J. Propulsion and Power* 30(3):664–671 (2014),
  doi:10.2514/1.B35041. Metadata via the Crossref API and abstract via the OpenAlex API. The full text was not accessed:
  AIAA and Deep Blue returned HTTP 403 to the fetch tool, and this was not bypassed.
- **REF-MARTINORTEGA2020.** A. Martín Ortega, A. Guglielmi, F. Gaboriau, C. Boniface, J. P. Boeuf, "Experimental
  characterization of ID-Hall, a double stage Hall thruster with an inductive ionization stage", *Physics of Plasmas*
  27(2):023518 (2020), doi:10.1063/1.5140241. Abstract via OpenAlex; the open copy hal-03033131 was not read.
- **REF-DUBOIS2018.** L. Dubois et al., "ID-HALL, a new double stage Hall thruster design. I / II", *Physics of Plasmas*
  25(9):093503 and 093504 (2018), doi:10.1063/1.5043354 and 10.1063/1.5043355. Metadata only; context.
- **REF-GUM2008.** JCGM 100:2008, "Evaluation of measurement data — Guide to the expression of uncertainty in
  measurement" (GUM 1995 with minor corrections), first edition September 2008.
  https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf (full text extracted: G.4.1 Eq. G.2b
  Welch–Satterthwaite; G.4.2 Eq. G.3 degrees of freedom of a Type B evaluation; G.4.3 Type B components viewed as
  exactly known, ν → ∞).
- **REF-IIST-WEB.** IIST, "Space Research", https://iist.ac.in/space-research. Page text via the fetch tool.
- **REF-BRABSTON2025.** Brabston, Marino, Lev, Walker, *J. Propulsion and Power* 2025, doi:10.2514/1.B39623. Not
  re-accessed; used through this repository's docs/EVIDENCE.md register and `hallthruster_bridge/identification/`.
- **Repository.** CLAUDE.md; docs/EVIDENCE.md; docs/HISTORY.md; `hallthruster_bridge/ensemble/transport_ensemble_v0.json`;
  `hallthruster_bridge/prereg/p5_n2_run_status_rule_v1.json`, `p5_n2_prereg_lock_v1.json` (at `c53b75a`);
  `requirements-lock.txt` (scipy pin). Other lanes, read-only: `abep_sim/arch_boundary.py` (commit `a2a1396`) and
  `docs/architecture_comparison/experiment_protocol/` (commit `1428265`).

## 18. Revision r2: review findings and where they are addressed

| finding | fix |
|---|---|
| normal quantile with estimated σ (anti-conservative) | §6.1–6.3: every group states its evaluation and dof; Student-t at Welch–Satterthwaite ν_eff; all targets regenerated |
| D0 not evaluable (u_rm only at S6; one re-mount ≈ 1 dof) | §6.4: S1b re-mount series (K = 6, ν = 5) before any score-bearing reading; S6 becomes a check (D6); `readiness_n()` |
| source arms off the contract basis | §5: every component at its contract load plane with ledger efficiencies; source = net RF/microwave power at the load plane (M3); lab DC input only as efficiency evidence (R_lab); §3.3 η_src,be |
| stop rule misdescribed ("equivalently", "exactly") | §9: stop on the sign statement (upper bound < 0 ⇔ C_del > C\*), monotone in precision; worked example tested |
| API name | `bus_power_ledger(arch, loads, efficiencies)` (§5, §13) |
| reading counts omit bracketing readings | §4: 52 readings per block (208 at n = 4); subset case 128; bench 120 |
| "eV per delivered ion" | §3.2: eV per elementary charge |
| iso-power family without a variance model; chord error unbudgeted | §6.5: first-order model, bound proof, u_interp budget line and T-ISO-INTERP |
| S5 classification without family or k | §6.5: facility family, m = 4 |
| S0/S1 sequence vs pre-registration contents | §10: LOCK-1 (S0) and LOCK-2 (after S1) |
| relation to the full protocol unchecked | §13: differences stated from its committed draft |
| hidden constants (n = 6, "3 shares", √5); T-VAR-GROUPS | T-BUDGET-SHARES keyed by the variance groups (script refuses a mismatch); n grid from T-N-MIN..T-N-MAX |
| class gap (Hall goes out with the source on) | §9: DISABLES, NEITHER_SUSTAINED, SUSTAINMENT_MIXED |
| stop on untested conditions; OP5 × lo bench orphan | §9: NOT_TESTED, owner option; OP5 × lo removed from the bench |
| helpers accept invalid inputs | `ratio_R`, `breakeven_cost`, `delivered_ion_cost`, `breakeven_efficiency` raise on non-positive T_0, P_0, P_1, I_del |
