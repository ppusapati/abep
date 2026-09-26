# Minimum decisive experiment: Hall-only vs RF+Hall vs ECR+Hall

**Status: DRAFT_PENDING_OWNER.** Lane 25 (MINEXP), 2026-09-26, base commit `c53b75a`. Nothing here is pre-registered
or approved. Every threshold and rule is **PROPOSED** for the owner. The machine-readable twin is
`experiment_draft.json` in this folder. Every derived number comes from `minexp_numbers.py` in this folder; its
`--check` mode reproduces the JSON block and `tests/test_minimum_decisive_experiment.py` checks both.

Numbers in this document are one of three kinds: **PROPOSED thresholds** (evidence class *assumed*, owner decision),
**derived requirements** (evidence class *model-derived*, from the script), or **cited literature statements**
(source given). Everything else is **TBD — requires …**. No performance number of any Hall thruster is used.

## 0. Summary

- **Question.** At one common feed state and one common DC bus boundary (`bus_power_boundary_v1`), does an RF or an
  ECR pre-ionizer in front of the **same** Hall accelerator raise thrust per bus watt, or let the discharge run where
  Hall-only cannot, compared with Hall-only?
- **When to run it.** Only if the literature and model evidence (`docs/evidence/rf_source/`, `docs/evidence/ecr_source/`,
  `docs/evidence/hall_sustainment/`) still can't settle the question. This draft doesn't judge that.
- **Design.** One Hall unit H-1 and one cathode C-1 in three hardware configurations: HW-0 (bare feed, the
  `hall_only` arm), HW-RF and HW-ECR. Three N₂ flows straddle the Hall-only sustainment knee, plus one air-surrogate
  point, two source powers, and two V_d levels for Hall-only only (iso-power reference). Blocks are paired and
  randomised.
- **Decisive metric.** R_arch = (T/P_bus) of the source arm divided by (T/P_bus) of Hall-only at the same point. It is
  classified against a proposed ±5 % band (δ = 0.05 on ln R) with simultaneous 95 % intervals. The break-even identity
  R_arch > 1 ⇔ C_del < C* ties it to the source's delivered-ion cost.
- **Size.** 40 Hall-on conditions per block: 160 readings at 4 blocks. Add 64 source-bench readings and a 10-reading
  knee scan. If both source arms stop after their confirmation subsets, the Hall-on count is 104 readings.
- **Uncertainty target.** To classify every point with m = 14 simultaneous comparisons, σ(ln R) must be at most 0.00858.
  With five equal variance shares, that means per-reading thrust and bus-power repeatability of at most 0.54 % at 4
  blocks. Whether that is achievable is **TBD — requires S1 data**. The owner can widen δ instead; the trade-off is in §6.
- **Output.** A per-arm, per-point classification, each with its conditions. The output never names a winner.

## 1. Milestones supported

| milestone | what this experiment delivers | what is still needed to reach it / the next one |
|---|---|---|
| **A** conditional selection | Measured, paired, common-boundary classes per arm and point (SOURCE_BETTER / EQUIVALENT / SOURCE_WORSE / ENABLES / UNRESOLVED, each FACILITY_ROBUST or FACILITY_CONDITIONAL), with the conditions they depend on. Enough for "architecture X is baseline provided A/B/C". Doesn't need Physics Baseline 1.0. | S0–S4 done for `hall_only` and every non-stopped source arm; S5 for the facility qualifier. Feed-envelope values from the upstream ICD (IF-A5) and the bus allocation. |
| **B** physics-backed selection | Source boundary data that don't depend on Hall transport (P_src,bus, I_src, I_del, η_ts, delivered-ion energy and species). Hall data on the tested hardware (B(z) maps with coil currents, geometry, I_d traces, species fractions, divergence per point). | An admitted Hall transport closure; the credible set is empty today (CLAUDE.md gate 3). O/O₂ chemistry for air (CLAUDE.md next work 4); the air surrogate here has no atomic O. If the physics track wants these data as promotion evidence, it must pre-register that separately, before the measurement. |
| **C** proposal/PDR freeze | Measured bus-power ledger entries per consumer at the tested points; source waste heat. | Mass, thermal, life (`docs/evidence/wall_life/`, `abep_sim/thermal_life.py`), startup, cathode (`docs/evidence/cathode/`) and mission closure integrated; a flight-representative PPU and generator. This experiment alone doesn't support C. |

This is the fastest physical route to milestone A. It also feeds milestone B directly once a closure is admitted.

## 2. What is held identical, and the one thing that changes

| element | `hall_only` (HW-0) | `rf_hall` (HW-RF) | `ecr_hall` (HW-ECR) |
|---|---|---|---|
| Hall accelerator | H-1 (same serial unit, channel, anode, magnetic circuit, coil currents per point) | H-1 | H-1 |
| cathode | C-1, same position, flow and keeper setting | C-1 | C-1 |
| feed state | FS-common: same anode flow, composition (same MFCs and bottles), cathode flow, supply temperature (IF-A5 / IF-X2 fields) | same | same |
| V_d, facility, stand, meters, probes, calibration standards | same | same | same |
| pre-ionizer | none (flow-equivalent spacer) | RF source + interstage + DC-input RF generator + matching | ECR source + interstage + DC-input microwave generator + waveguide/antenna + ECR magnet |
| arm-specific bus components | none | `rf_source` | `ecr_source`, `ecr_magnet` |

Common bus components (`bus_power_boundary_v1`, `abep_sim/arch_boundary.py`, other lane, referenced by path only):
`hall_discharge`, `hall_magnet`, `cathode_keeper`, `cathode_heater`, `flow_control`, `compressor`, `thermal_control`,
`housekeeping`. The lab measures the consumers it has (§5). `compressor` and `housekeeping` don't exist in a
bottled-feed test. They enter every arm's bus sum as explicit ledger inputs with their evidence class, identical
across arms.

**Installation effect.** With its source unpowered, HW-RF or HW-ECR is *not* Hall-only: gas still flows through the
source chamber, and an ECR permanent magnet would still perturb the Hall field. So:

- `hall_only` is measured on HW-0;
- the installed-off state of each source configuration is a within-block drift reference;
- R_arch = R_within × R_install separates the effect of powering the source from the passive presence of its
  hardware.

B(z) is mapped for every configuration (§5, M11).

**OPTION-DIVERTER (PROPOSED hardware option).** An in-vacuum feed-path diverter routes gas through the source or
straight to the anode distributor without venting. It removes the re-mount term (G5, §6) from the comparison and needs
one check against a true HW-0. Owner decision.

## 3. Break-even logic

### 3.1 Decisive quantities

| id | symbol | quantity | measured in |
|---|---|---|---|
| Q1 | I_del | delivered ion current: ion current across the Hall channel exit plane with the Hall discharge off and magnet on (cold transport through the whole accelerator), integrated over the beam | S3 |
| Q2 | P_src,bus | DC input power of the source generator (+ `ecr_magnet`) on the common bus | S3, S4 |
| Q3 | η_ts | interstage transport efficiency I_del / I_src (I_src = ion current leaving the source exit plane) | S3 |
| Q4 | ΔI_d | Hall discharge-current change, source arm vs `hall_only`, at fixed V_d, ṁ, composition, coil currents | S2, S4 |
| Q5 | ΔT | thrust change at the same fixed conditions | S2, S4 |
| Q6 | ΔP_bus | change of the `bus_power_boundary_v1` sum | S2, S4 |

### 3.2 The inequality

The source arm's bus power is P_bus,X = P_bus,0 + V_d·ΔI_d/η_d + P_src,bus + ΔP_other, where η_d is the ledger's
discharge-converter efficiency (the same for all arms). Then

  R_arch = (T_X / P_bus,X) / (T_0 / P_bus,0) > 1 ⇔ ΔT · P_bus,0 > T_0 · (V_d·ΔI_d/η_d + P_src,bus + ΔP_other).

Dividing by I_del gives the break-even form:

  **C_del ≡ P_src,bus / I_del < C\* ≡ y · (P_bus,0 / T_0) − κ · V_d / η_d − ΔP_other / I_del**,
  with y = ΔT / I_del and κ = ΔI_d / I_del.

C_del has units of W/A = V, which is numerically the energy spent per delivered ion in eV. C\* has three terms:

- the bus power Hall-only spends per unit thrust, times the thrust bought per delivered ampere;
- minus the extra discharge power the delivered ions draw;
- minus any other bus change.

"The measured delivered-ion cost exceeds the break-even cost" is therefore exactly "R_arch < 1". It is an identity with
no physical assumption; the test checks it numerically.

### 3.3 The ion-momentum ceiling, and why a Hall-off bound only screens

An ion of charge Ze fully accelerated through V_d with no divergence carries at most y_max = √(2 m_i V_d / (Z e)) of
thrust per ampere. Values per √V (ion mass ≈ neutral mass from `abep_sim/constants.py`):

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

So the bound is used only to shrink S4 for an arm that fails it everywhere (D2), and the stop needs Hall-on data (D3).

### 3.4 Iso-power comparison

Under a hard bus cap, Hall-only could spend the source's watts on a higher V_d instead. R_iso = T_X / T_0(P_bus =
P_bus,X), with Hall-only thrust linearly interpolated between V_nom and V_hi at the same ṁ. It is reported only where
the two Hall-only points bracket P_bus,X; there is no extrapolation. It is a second comparison family (m = 8).

### 3.5 Priors this experiment tests

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

### 3.6 Common loads dilute R

Loads common to all arms that the lab doesn't have (compressor, housekeeping) raise P_bus,0 and therefore C\*. R is
reported both with lab-measured consumers only and with the full `bus_power_boundary_v1` sum. The full sum is decisive,
and each ledger input carries its evidence class.

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
| OP3 | ṁ_nom | V_nom | N₂ | off, lo, hi | nominal feed; the other side of the break-even surface |
| OP2H | ṁ_knee | V_hi | N₂ | Hall-only | iso-power reference |
| OP3H | ṁ_nom | V_hi | N₂ | Hall-only | iso-power reference |
| OP5 | ṁ_knee | V_nom | air surrogate | off, hi | composition transfer at the most sensitive flow |

**Knee scan (S2, HW-0, N₂, V_nom).** 5 flow levels (T-KNEE-LEVELS) from ṁ_nom down to ṁ_min and back up, as a
hysteresis check. ṁ_knee is the lowest level sustained in both directions. If every level is sustained, ṁ_knee is the
midpoint of ṁ_min and ṁ_nom. If no level is sustained, ṁ_knee = ṁ_nom and every point becomes a test of whether the
source lets the discharge run (ENABLES).

**Run matrix** (`experiment_draft.json` rows R01–R40), per block:

| configuration | conditions | content |
|---|---|---|
| HW-0 (`hall_only`) | 10 | OP1, OP2, OP3, OP5, OP2H, OP3H; S5 elevated-p_b at OP2, OP3; end-of-campaign re-mount repeat at OP2, OP3 |
| HW-RF | 15 | OP1–OP3 × {off, lo, hi}; OP5 × {off, hi}; S5 at OP2, OP3 × {off, hi} |
| HW-ECR | 15 | as HW-RF |

- Primary comparison family: 7 source-on conditions per arm, m = 14.
- Iso-power family: OP2, OP3 × {lo, hi} per arm, m = 8.
- Confirmation subset for a stop candidate: {OP1, OP2, OP3, OP5} × {off, hi} = 8 conditions per arm.
- Bench (S3, Hall discharge off): the flows of OP1, OP2, OP3, OP5 × {lo, hi} per arm, 16 conditions in all.

**Why not fewer.**

- One flow cannot straddle a break-even that depends on how well Hall-only ionizes. ṁ_min and ṁ_nom are the envelope
  edges, and ṁ_knee is where the sign is most likely to change.
- One source power cannot give the marginal yield, and C_del's dependence on power is unknown.
- V_hi only on Hall-only is the cheapest iso-power reference.
- Air at a single point and power is a transfer check, not a map.
- Dropping HW-0 would leave `hall_only` unmeasured (installation effect).

## 5. Measurements and instruments

| id | quantity | instrument | practice / requirement |
|---|---|---|---|
| M1 | thrust T | pendulum-type thrust stand (hanging, inverted or torsional) with in-situ calibration | REF-POLK2017: end-to-end in-situ calibration under vacuum; at least ten calibrations before and after operation; zero with power and flow off before thermal drift; error budget reported. Requirement: u_T per reading ≤ §6 value. Range **TBD — requires the Hall design** |
| M2 | bus-level DC power per consumer | multi-channel DC power analyzer or calibrated shunt/divider pairs, simultaneous sampling; one channel per `bus_power_boundary_v1` component present; **DC input of each source generator** on its supply side | same channels for all arms; traceable calibration (owner to specify). u_P ≤ §6; source-channel scale (incl. generator efficiency if the DC input is not measured) ≤ §6 |
| M3 | forward/reflected RF or microwave power | directional coupler + power sensors | diagnostic (coupling, DC→RF efficiency); never a substitute for the DC input |
| M4 | I_d(t) | current probe, time-synchronised DAQ | sampling **TBD — requires the S1 I_d spectrum**; traces archived for every reading; T-SUSTAIN uses extinction; oscillation reported, non-gating |
| M5 | I_src, I_del | guarded Faraday collector/probe array at the source exit; downstream Faraday sweep / integrating collector with the Hall discharge off | REF-BROWN2017 Table A1 (ion-saturation bias checked across the plume, SEE and gap corrections, alignment, cabling). The full practice asks for at least four background pressures and four distances; the minimum set uses fewer and says so |
| M6 | ion energy distribution | RPA at interstage/channel exit (S3) and far field (S4, both states) | explanatory |
| M7 | species current fractions N₂⁺, N⁺, O₂⁺, O⁺ | E×B probe, with an accelerating bias for low-energy interstage ions | REF-ROVEY2025: at low energy the four air ions (m/q 32, 28, 16, 14) are not all resolved without an accelerating bias; the CEX correction's dominant uncertainty is the background neutral density from ion gauges (typically 10–20 %). Species if possible; explanatory |
| M8 | far-field current density, beam current, divergence | far-field Faraday sweep, both states | REF-BROWN2017 (far field > 4 channel diameters); decomposes ΔT; published per point |
| M9 | p_b and feed/source pressure p | hot-cathode ion gauge(s) for p_b; capacitance manometer for p | REF-DANKANICH2017 Sec. IV.A: in-chamber, line of sight to the thruster, near the wall at the exit plane (≥ 0.6 chamber radii off axis, ≥ 1 m from the thruster OD), ≥ 10 Hz, 3 s averages, no reading within 2 min of a > 10 % flow change; calibrate on the gas of interest where practical (nitrogen is the industry-standard calibration gas, Sec. II.A.2); record wall temperature |
| M10 | mass flow | thermal MFCs calibrated for N₂, O₂, Xe (cathode) | REF-SNYDER2017 (title/DOI only; verify). Identical setpoints across arms |
| M11 | B(z) | Hall-probe gaussmeter on a positioning stage | every configuration, source magnet on/off where applicable, operating coil currents, before and after; published with coil currents (the gap that made P5 non-identifiable). Range **TBD — requires the Hall design** |
| M12 | temperatures | thermocouples on anode/body, magnet circuit, source, generator, cathode mount | settling (T-SETTLE), `thermal_control` input |
| M13 | species/background (optional) | OES in source/interstage; RGA | qualitative; O₂ background check |
| M14 | electrical environment | cathode-to-ground, anode-to-ground potentials | recorded every reading; same grounding for all arms |

## 6. Uncertainty targets, derived from the break-even inequality

**Variance model** (`sigma_lnR()` in `minexp_numbers.py`, first order) for ln R_arch:

  σ²(ln R) = 2u_T²/n + 2u_P²/n + (f_src·u_src)² + Σ_c (w_c·u_c)² + u_rm²

| group | term | averages down with blocks? | cancels? |
|---|---|---|---|
| G1 thrust random (incl. zero and calibration drift) | 2u_T²/n | yes | stand scale factor cancels when one in-situ calibration set brackets both conditions |
| G2 bus-power random | 2u_P²/n | yes | meter scale of an unchanged consumer cancels to first order |
| G3 source-power scale (meter; generator efficiency if its DC input isn't measured) | (f_src·u_src)², f_src = P_src,bus/P_bus,X | no | no — the source channel exists in one condition only |
| G4 common-consumer scale, unmeasured ledger loads, η_d | Σ(w_c·u_c)², w_c = \|P_c,X/P_bus,X − P_c,0/P_bus,0\| | no | partially |
| G5 re-mount / between-session reproducibility (incl. stand re-calibration shifts) | u_rm² | no | no; from the HW-0 start/end repeat; removed by OPTION-DIVERTER |

G3 shows why a flight-representative, DC-input generator matters. Its efficiency enters with weight f_src and never
cancels.

**Classification** (simultaneous interval ln R̂ ± h, h = z·σ, band (−δ, +δ)):

| class | condition |
|---|---|
| EQUIVALENT | the whole interval lies inside (−δ, +δ) |
| SOURCE_BETTER | not EQUIVALENT, and the lower bound > 0 |
| SOURCE_WORSE | not EQUIVALENT, and the upper bound < 0 |
| UNRESOLVED | anything else |

**UNRESOLVED is impossible if h < δ/2.** If a point isn't EQUIVALENT, then |x| + h ≥ δ, so |x| ≥ δ − h > h, and the
interval excludes 0. With h ≥ δ/2 a gap δ − h ≤ |x| ≤ h opens. The script checks both cases numerically: 0 unresolved
grid points at h = 0.999·δ/2, 668 at h = 0.75·δ. **Requirement: σ(ln R) < δ/(2z).**

**Derived numbers** (PROPOSED inputs: δ = 0.05, family-wise α = 0.05 Bonferroni, 5 equal variance shares, n = 4–8
blocks):

| quantity | value |
|---|---|
| primary family size m | 14 |
| z (two-sided, Bonferroni, primary) | 2.9137 |
| σ_max(ln R) = δ/(2z) | 0.00858 |
| per-group share σ_max/√5 (also the u_rm limit) | 0.00384 |
| u_T, u_P max per reading, n = 4 | 0.54 % |
| u_T, u_P max per reading, n = 6 | 0.66 % |
| u_T, u_P max per reading, n = 8 | 0.77 % |
| iso-power family m, z, σ_max | 8, 2.7344, 0.00914 |
| S3 screen z (one-sided, α = 0.05) | 1.6449 |

Source-scale limit (G3 share): u_src ≤ 0.00384 / f_src. That is 3.84 %, 1.92 %, 1.28 % and 0.96 % for f_src = 0.1,
0.2, 0.3 and 0.4 (planning values, hypothetical).

**Floor that no number of repeats beats.** δ_floor = 2z·s_nonavg, where s_nonavg combines G3–G5: s = 0.005 → 0.0291;
s = 0.01 → 0.0583; s = 0.02 → 0.117. If the S1-measured non-averaging terms put δ_floor above δ, the owner must
widen δ, improve instruments or adopt OPTION-DIVERTER before any score-bearing run (D0).

**Blocks needed** (u_T = u_P = u; the three non-averaging groups at their allocated share; even, at least 4):

| δ | u = 0.5 % | u = 1 % | u = 2 % |
|---|---|---|---|
| 0.05 | 4 | 14 (> 8) | 56 (> 8) |
| 0.10 | 4 | 4 | 14 (> 8) |

In words: at δ = 0.05 the campaign needs about 0.5 % per-reading repeatability. At 1 % it needs δ = 0.10 or many more
blocks. **Achievability is TBD — requires S1 repeatability and calibration certificates.** No instrument accuracy is
claimed here.

**Why no facility correction enters the decisive metric.** In P5-N₂ the ingestion correction to I_d was 2.2–3.7 %
(docs/EVIDENCE.md register, reconstructed from Brabston Eqs. 13/14). The facility-ingestion interpretation became a
calibration-nuisance dimension (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`). That is the same order as
δ. So the decisive metric uses raw paired data at the measured p_b, and the p_b sensitivity is measured directly (S5).

**S3 screen uncertainty.** u(ln C_del)² = u(P_src,bus)² + u(I_del)²; u(ln C\*_ub)² = u_abs(P_bus,0)² + u_abs(T_0)².
These are absolute calibrations, so scale terms don't cancel. A larger u(I_del) never creates a stop candidate: the
screen errs toward running more.

## 7. Randomisation and repeatability

- **Configuration order.** HW-0 runs first and last. A seeded coin, published in the pre-registration, orders HW-RF
  and HW-ECR between them.
- **Blocks.** A block visits every condition of the current configuration once. The operating-point order is a seeded
  permutation, re-drawn for each block. n is fixed at D0 from S1 repeatability, between 4 and 8, and never changed
  after the first score-bearing reading.
- **Within a point.** The order is off, lo, hi, off in odd blocks and off, hi, lo, off in even blocks. The two off
  readings bracket drift, and linear drift cancels over block pairs (hence an even n). The thrust zero is taken at
  the end of each point visit (REF-POLK2017).
- **Repeatability.**
  - Blocks run on different days where possible, and the day is recorded.
  - The HW-0 re-mount repeat at OP2 and OP3 gives u_rm.
  - The knee scan runs in both directions.
- **Blind scoring.** The raw dataset is frozen and hashed, then scored once by the frozen, hash-locked analysis
  script. This mirrors the P5-N₂ practice (`hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json`).

## 8. Facility controls

- **Background pressure.** M9 follows REF-DANKANICH2017, and every reading carries p_b. Base p_b must satisfy
  T-PB-MAX (**TBD**). The Sec. V guidance values in that paper are SPT-100/xenon specific; its authors note that
  their basis does not address other thrusters and that the data don't justify absolute requirements for general
  designs. A reading above T-PB-MAX is NOT_SCOREABLE_FACILITY, which is not evidence against any arm.
- **S5 facility-effect check.** At OP2 and OP3, for Hall-only and every non-stopped source arm at P_hi, p_b is raised
  to 2 × base (T-PB-ELEV-FACTOR). The method is REF-DANKANICH2017 Sec. IV.B: supplemental primary gas ≥ 2 m downstream,
  with a pumping surface between the injection and the gauge. If the class is unchanged the point is FACILITY_ROBUST;
  otherwise it is FACILITY_CONDITIONAL. No ingestion model is applied to rescue a class (the P5-N₂ lesson).
- **Publish what P5 lacked.** B(z) maps and coil currents, channel geometry, I_d traces, per-point divergence, gauge
  location and calibration.
- **Electrical and gas.** Grounding and cable routing are the same for every arm (M14). Facility compatibility with O₂
  flow (pump type, safety case) is **TBD — requires facility data**.

## 9. Sequential decision tree and stopping rules (all PROPOSED)

```
S0  pre-registration (owner approves thresholds, seed, frozen script; hash lock) ........ not score-bearing
S1  qualification: calibrations, B(z) per configuration, repeatability, p_b vs flow ....... not score-bearing
    D0  T-READINESS: calibrated; n_req <= 8 at delta; delta_floor < delta; p_b <= T-PB-MAX
        fail -> OWNER (no score-bearing run)                pass -> S2
S2  hall_only on HW-0: knee scan (down + up), R01-R06
    D1  fix mdot_knee (T-OP2-FALLBACK); flag points where hall_only is not SUSTAINED as ENABLES tests
S3  source bench, Hall discharge off (both arms): P_src,bus, I_src, I_del, eta_ts, C_del
    G-SRC  hard gate (measured): source can't sustain within P_hi at a flow (bench and one Hall-on try)
           -> INFEASIBLE_AT_POINT; at every flow -> arm STOPPED
    D2  T-SCREEN-RULE: hall_only SUSTAINED everywhere AND ln C_del - ln C*_ub > z_screen*u at every point
        yes -> STOP_CANDIDATE: S4 confirmation subset only       no -> S4 full
S4  paired Hall-on, randomised: R_arch, R_within, R_install, R_iso, y, kappa, C*, ENABLES
    D3  T-STOP-RULE: every tested sustained point SOURCE_WORSE (i.e. C_del > C* with simultaneous confidence)
        AND no R_iso SOURCE_BETTER AND no ENABLES
        AND (subset only) y - z*u(y) <= y_max and kappa + z*u(kappa) >= 0 at every subset point
        yes -> arm STOPPED        no, from subset -> rest of S4        no -> S5
    D5  EXPERIMENT_MOOT if hall_only is sustained nowhere and no arm ENABLES anywhere -> report to owner
S5  facility check at 2x p_b (OP2, OP3)
    D4  T-FACILITY-ROBUST: class unchanged -> FACILITY_ROBUST, else FACILITY_CONDITIONAL
S6  HW-0 re-mount repeat -> freeze raw dataset (hash) -> score once -> per-arm, per-point classes + conditions
```

Stopping rules in words:

- An arm stops only on **measured** paired data: SOURCE_WORSE at every tested point where Hall-only is sustained, no
  iso-power advantage, and nowhere where only the source arm sustains the discharge. For the RF arm this is exactly
  "the measured delivered-ion cost exceeds the break-even cost at all tested points" (§3.2).
- EQUIVALENT never stops an arm. It is reported to the owner, who weighs mass, complexity and life.
- The Hall-off screen (D2) only shrinks the Hall-on grid.
- The hard gate G-SRC stops an arm only when its source can't sustain plasma at any grid flow within its allocated power.

## 10. Pre-registration step (before any score-bearing reading)

The owner-approved successor of `experiment_draft.json` records:

1. A decision on every PROPOSED threshold and rule, with its date.
2. ṁ_min, ṁ_nom, composition (IF-A5), V_nom, V_hi and P_hi.
3. The ledger efficiencies and unmeasured common loads, each with an evidence class.
4. The instruments, their calibration certificates, and the S1 repeatability used to fix n.
5. The seed and the configuration-order draw.
6. The frozen analysis script (sha256) implementing §6 and §9.
7. The score-bearing rows.
8. Whether the physics track pre-registers any result as Hall-closure evidence. That is their decision, in their own
   pre-registration.

A lock file holds the hashes. Score-bearing data taken before the lock are excluded. The location of the pre-registration
and lock files is the owner's decision; it is outside `hallthruster_bridge/prereg/`, which this lane may not modify.

## 11. Minimum hardware list

1. Hall accelerator H-1, one unit. It must be the Vyovrinda design for evidence level 1. A surrogate gives level 2/3
   evidence, which transfers only through an admitted closure.
2. Cathode C-1 with keeper and heater supplies (type **TBD — requires the cathode lane**).
3. Feed: MFCs for N₂, O₂ (air surrogate) and Xe (cathode); a common manifold; a flow-equivalent spacer (HW-0) or
   OPTION-DIVERTER.
4. RF source module + interstage + **DC-input** RF generator + matching network.
5. ECR source module + interstage + **DC-input** microwave generator + waveguide/antenna + ECR magnet.
6. Discharge, magnet, keeper and heater supplies (lab supplies; bus conversion through the ledger efficiencies).
7. DC power-analyzer channels for every present bus component, an I_d current probe, and a time-synchronised DAQ.
8. A thrust stand with an in-situ calibration system.
9. Diagnostics: Faraday collector/array at the source exit, a downstream Faraday sweep, an RPA, and an E×B probe
   (the E×B probe is optional for the minimum).
10. Pressure and field instruments: ion gauge(s) calibrated on N₂, a capacitance manometer, a wall thermocouple, a
    supplemental gas injector, and a gaussmeter with a positioning stage.
11. A vacuum facility meeting T-PB-MAX at the grid flows (§12).

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
| S1 calibrations, B(z) | no plasma; B(z) mapping is magnetostatic (room temperature; hot-state effects TBD) | yes |
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
| `docs/architecture_comparison/experiment_protocol/` | Full common-condition protocol. This draft is its minimum decisive subset and sequencing; where they differ, the owner decides. Not present in this worktree when written. |
| `docs/experiments/` | IIST experiment package: facility-specific packaging of any stage. |
| `abep_sim/arch_boundary.py` | `bus_power_boundary_v1` contract (component names and `ledger(arch, loads, efficiencies)`) used above. |
| `abep_sim/arch_compare.py` | Comparison harness; this experiment's measured results are candidate inputs once pre-registered. |
| `abep_sim/thermal_life.py`, `docs/evidence/wall_life/`, `docs/evidence/cathode/` | Milestone C inputs; C-1 choice. |
| `docs/evidence/rf_source/`, `docs/evidence/ecr_source/`, `docs/evidence/hall_sustainment/` | Decide whether this experiment is needed at all; set expectations for S2/S3. |
| `schemas/interfaces/upstream_icd_v1.json` (IF-A5, IF-X2), `schemas/ledgers/` | Feed-state fields; ledger schemas for the bus sum. |
| `docs/hallmap/` | B(z) and geometry measured here are Hall-map inputs for Vyovrinda hardware (milestone B). |

## 14. Thresholds register (all PROPOSED; values in `experiment_draft.json`)

| id | proposal |
|---|---|
| T-DELTA | δ = 0.05 on ln R |
| T-ALPHA-FW | family-wise α = 0.05, Bonferroni simultaneous intervals |
| T-ALPHA-SCREEN | one-sided α = 0.05 for the S3 screen |
| T-N-MIN / T-N-MAX | 4 / 8 blocks (even for drift cancellation) |
| T-VAR-GROUPS | 5 equal variance shares (G1–G5) |
| T-PB-ELEV-FACTOR | 2 × base p_b in S5 |
| T-PB-MAX | **TBD — requires S1 and an owner decision** |
| T-KNEE-LEVELS | 5 levels |
| T-OP2-FALLBACK | ṁ_knee rule (§4) |
| T-PLO-FRACTION | P_lo = max(lowest stable, 0.5·P_hi) |
| T-SUSTAIN | no extinction or restart during the dwell (dwell **TBD — requires S1**) |
| T-SETTLE | **TBD — requires S1 thermal time constants** |
| T-SCREEN-RULE, T-STOP-RULE, T-FACILITY-ROBUST, T-READINESS, G-SRC, D5 | §9 |

## 15. Open owner decisions

1. Approve, change or reject every PROPOSED threshold and rule.
2. Supply ṁ_min, ṁ_nom, composition (IF-A5), V_nom, V_hi, P_hi, the ledger efficiencies, and the unmeasured common
   loads with their evidence classes.
3. Choose between the HW-0 spacer and OPTION-DIVERTER.
4. Decide whether the tested Hall is the Vyovrinda design or a surrogate.
5. Choose the facility per stage, and decide whether to seek any facility's specification (owner's channel).
6. Decide whether to add Xe anode operation or a second V_d on the source arms (outside the minimum).
7. Decide where the pre-registration and lock files live.

## 16. Compliance

- No Hall transport closure, screening candidate or withdrawn 0-D number is used as a performance source; there is no
  retuning.
- P5 calibration nuisance is never an axis.
- Hall-closure uncertainty doesn't leak upstream: the feed state is a fixed IF-A5 input, identical across arms, and
  upstream loads are identical ledger inputs.
- No arm is eliminated except by the measured gate G-SRC or the measured stop rule D3, and no winner is declared.
- Every number is sourced with an evidence class or marked TBD, and the derived numbers are reproducible by
  `minexp_numbers.py --check`.
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
- **REF-IIST-WEB.** IIST, "Space Research", https://iist.ac.in/space-research. Page text via the fetch tool.
- **REF-BRABSTON2025.** Brabston, Marino, Lev, Walker, *J. Propulsion and Power* 2025, doi:10.2514/1.B39623. Not
  re-accessed; used through this repository's docs/EVIDENCE.md register and `hallthruster_bridge/identification/`.
- **Repository.** CLAUDE.md; docs/EVIDENCE.md; docs/HISTORY.md; `hallthruster_bridge/ensemble/transport_ensemble_v0.json`;
  `hallthruster_bridge/prereg/p5_n2_run_status_rule_v1.json`, `p5_n2_prereg_lock_v1.json` (at `c53b75a`).
