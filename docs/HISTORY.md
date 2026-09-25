# abep-sim — system-closure simulator for ABEP-VLEO (DRDO TDF DTDF/06/13516)

Evaluates every propulsion architecture × orbit × solar state × intake × compressor ×
discharge-voltage combination against **all** RFP constraints simultaneously:

| Constraint | Where enforced |
|---|---|
| 12–25 mN | `chk_thrust_air_ge_req` (12 mN sustained on air), `chk_thrust_peak_25mN` (25 mN with Xe topping) |
| < 1500 W total | `chk_power_air`, `chk_power_peak` (10 % margin held by default) |
| < 40 kg total incl. intake, compressor, PSE, Xe + tank, structure, 10 % margin | `chk_mass` |
| N₂ + nascent O | species-resolved thrust/current model from MSIS-class composition |
| Xe as propellant | Xe-fed cathode + Xe anode topping to 25 mN; mission Xe mass computed |
| > 15,000 h ignition, 26,000 h mission | `chk_life` (O-exposed component life priors) |
| 180–230 km | atmosphere model |
| ≥ 75 % IC, thruster ≥ 80 % | `chk_ic_total`, `chk_ic_thruster` (mass-weighted) |
| Hall preferable | reported as `chk_hall_preferred` |
| Net drag compensation on air alone | `T_over_D_air`, `chk_net_drag_comp_air` — second classification (below) |

Two classifications are reported for every configuration:
- **`rfp_compliant`** — every stated RFP limit met, *including 12 mN sustained on air alone* and 25 mN peak with Xe.
- **`abep_closed`** — `rfp_compliant` AND T > D on air alone. This is the physical purpose of an ABEP; the RFP
  does not state it, so it is kept separate rather than folded into compliance.
`feasible` is retained as an alias of `rfp_compliant`.

This is **not** a plasma code. It is a 0-D closure model with every physical coefficient
exposed as a parameter, so DSMC, breadboard and IIST diagnostic results replace priors
without touching the pipeline. Its job is to say which architectures *can* close, where,
and on what the answer hinges — i.e. what PDR-1 must measure.

## Install / run

```bash
pip install -e .            # or: pip install numpy pandas pyyaml matplotlib
pip install pymsis          # optional: real NRLMSISE-00 instead of the built-in table
python -m abep_sim configs/baseline.yaml -o results/baseline
```

Outputs: `sweep.csv` (one row per configuration, ~80 columns), `summary.txt`,
`thrust_vs_power.png`, `closure_vs_altitude.png`, `mass_vs_xenon.png`.

Single design point:

```python
from abep_sim import Config, evaluate
from abep_sim.intake import IntakeParams, CompressorParams
r = evaluate(Config("hall_ecr", 200, "mean", IntakeParams(area_m2=1.0, accommodation=0.3),
                    CompressorParams(ratio=2000), vd_V=250))
```

Override any card prior from the YAML (e.g. once IIST measures ECR-stage utilisation):

```yaml
card_overrides:
  hall_ecr:
    stage1: {eta_u_boost: 0.22, ic: 0.88, power_fixed_W: 80}
    eta_b: {air: 0.65}
```

## Model

```
atmosphere(alt, solar) -> rho, fO, fN2, fO2, V_orb            [MSIS table or pymsis]
collection: mdot_col = eta_c(accommodation, off-axis) * rho V A ;  D = ½ rho V² Cd A_front
compressor: p_in = n_amb * CR * k T_out ;  P_comp = P_base + k * mdot * ln(CR)
thruster:   eta_u = eta_u_max(gas) * sigmoid(log p_in / p_min)  [+ pre-ioniser lift]
            I_b = Σ eta_u mdot_s e/m_s ;  v_s = sqrt(2 e Vd eta_v / m_s)
            T = cos_div Σ eta_u mdot_s v_s ;  P_d = I_b Vd / eta_b ;  P_stage1 = (P0 + k mdot)/eta_source
Xe:         cathode flow × 15,000 h + anode topping to 25 mN × xe_aug_hours
power:      (P_thruster + P_comp + P_ctrl) / eta_PPU  vs 1500 W × (1 − margin)
mass:       thruster + stage1 + PPU(P) + intake(A) + compressor(CR) + Xe + tank + structure, × (1 + margin)
IC:         mass-weighted; pre-ioniser hardware counted under "thruster"
life:       min over O-exposed component priors vs 15,000 h
```

## Calibration anchors (priors — replace with test data)

- Single-stage Hall on N₂: Marchioni & Cappelli, *J. Appl. Phys.* 130, 053306 (2021) —
  ~2 mg/s, 17–22 mN, 500–800 W, Isp ~1000 s. Reproduced by `tests/test_hall_n2_calibration`.
- Hall on Xe: 40–75 mN/kW, Isp 1200–1900 s at 250 V (`tests/test_xe_baseline_reasonable`).
- ECR pre-ioniser: ignition at mPa (ONERA-class); ECR+cylindrical-Hall precedent assumes CR ≈ 500 → ~0.01 Pa.
- RF pre-ioniser: Michigan Helicon-Hall (Shabshelowitz 2013) — small η_u gain, T/P loss;
  coupling collapses below ~0.05 Pa → `p_min_Pa = 5e-2`.
- Air microwave cathode: AMPCAT (Surrey, 2023) — 0.8 A on 0.1 mg/s air, 145 W, hours-class life → `o_life_h = 3000`.
- Grid-less ECR / helicon: T/P priors from ECRA / IPT literature; no 25 mN demonstration exists.

## v0.2.1 corrections (review findings)
1. `chk_thrust_air_ge_req` (12 mN sustained on air) is now in the hard gate — earlier "feasible" counts were too high.
2. `rfp_compliant` vs `abep_closed` split as above.
3. Compressor: requested total ratio below the passive ram ratio no longer under-reports outlet pressure
   (`ratio_effective = max(requested, passive)`); regression test added.
4. Sizing pressure target now respects the pre-ioniser: RF+Hall sized at 3 × 0.05 = 0.15 Pa (was 0.045 Pa).
   Effect: RF+Hall active ratio ≈ 8–40 at 180–200 km, 25–106 at 230 km (ECR+Hall: 2–12 / 7–32).

## What the baseline sweep says (9,450 configurations, v0.2.1)
- **504 RFP-compliant, 0 ABEP-closed** with the microwave-source IC prior at 0.70.
- Ignoring only the thruster-IC prior: hall_ecr 342 RFP-compliant, **12 ABEP-closed** (T/D 1.01–1.05: 180–230 km,
  0.5–2 m², fresh near-specular intake, 300 V, Isp ~2,100–2,250 s, 0.8–1.3 kW, 31–37 kg); hall_1stage 0 closed; hall_rf 0 closed.
- Closure margins are thin (≤ 5 %) and depend on accommodation 0.3 and Vd 300 V. This is the honest state of the
  physics with literature priors: ECR+Hall *can* close; nothing else does; and it closes only with a fresh, near-specular
  intake surface — which AO ageing degrades. Priority measurements: η_c vs AO fluence, η_u(p_in) with ECR stage.

## Earlier sweep notes (v0.1, superseded counts)

1. **Only Hall-family architectures close the hard constraints.** Grid-less ECR, helicon and
   RF gridded ion fail on power (T/P), IC, or grid life in O — every one of them, everywhere.
2. **Single-stage Hall closes on 25 mN / 1.5 kW / 40 kg / IC** at 180–200 km, but only by
   collecting a lot of air (≥ 2–3 mg/s → 2–3 m² intake) at low Isp (~800–900 s).
   Its T/D on air never exceeds ~0.4. It compensates its own intake's drag at ≈40 %.
3. **ECR + Hall closes on physics with T/D up to ~1.2** (0.5–1 m² intake, CR 500–2000,
   Vd 250–300 V, Isp ~2,400 s, ~1.1–1.2 kW). It fails in this sweep **only** on the
   indigenous-content prior for the microwave stage (0.70 → blended thruster IC 0.76 < 0.80).
   That is a supply-chain finding, not a physics one: the ECR source must be ≥ ~0.85 IC or
   argued as a separate subsystem.
4. **RF + Hall closes hard constraints and reaches T/D ≈ 1** only at CR 2000
   (p_in ≥ 0.1 Pa) — i.e. it needs a 4× harder compressor than ECR + Hall for the same result.
5. **The pivot variable is compressor outlet pressure**, exactly as argued in the meeting brief:
   at CR 500 (~0.02–0.05 Pa) ECR is the only pre-ioniser that works; at CR 2000 both do.
6. **Mass fails more than anything else** — driven by Xe: any configuration that cannot hold
   12 mN on air alone must top up with Xe for 15,000 h, and that Xe destroys the 40 kg budget.
   The 12 mN sustained-on-air point is therefore the real sizing requirement.

## What to feed it next

- DSMC η_c vs accommodation and off-axis angle → `IntakeParams`
- Compressor breadboard P_out, power, mass vs CR → `CompressorParams`
- IIST measurements of η_u(p_in) for Hall-only vs ECR/RF-assisted on N₂ and O → `Card.eta_u_max`,
  `p_min_Pa`, `Stage1.eta_u_boost`
- AO erosion yields → `Card.o_life_h`
- Actual BoM IC → `ic_*`

## Layout

```
abep_sim/constants.py   RFP limits, physical constants
abep_sim/atmosphere.py  MSIS table / pymsis
abep_sim/intake.py      collection, drag, compressor
abep_sim/thruster.py    architecture cards + performance model
abep_sim/system.py      budgets, Xe, life, IC, checks
abep_sim/sweep.py       grid runner, summary, plots, CLI
configs/baseline.yaml   default grid
tests/                  calibration tests (pytest)
```

## v0.2 additions

### Atomic-oxygen chemistry (`aochem.py`)
- Ram AO flux and 26,000 h fluence per case (200 km mean: 3.6e19 atoms/m²/s, 5 eV, 3.4e27 atoms/m² mission).
- Erosion depth per material from Kapton-referenced yields → what survives on the ram face
  (Kapton 10 mm, CFRP 9 mm, silver 36 mm, graphite 4 mm; Al/Ti/BN/alumina/SiC ~0; SiOx-coated polyimide 68 µm).
- **Heterogeneous wall recombination O + O(ads) → O₂.** Every wall collision carries a probability γ.
  With a stainless molecular-drag compressor (~300 collisions, γ≈0.07) the thruster receives
  essentially **no atomic O**: inlet composition becomes ~44 % N₂ / 56 % O₂. All-alumina walls
  pass ~33 % of the O; quartz ~83 %. Neutral–neutral thermal gas-phase chemistry is negligible in the rarefied intake/reservoir path
  (mean free path ≫ device); electron-impact plasma chemistry inside the ioniser/thruster is essential and is the
  next physics block to add (species-resolved ionisation/dissociation/excitation, see roadmap).
- Consequences propagated into the thruster model: heavier mean ion mass (thrust per ion), O₂
  dissociation sink (5.12 eV) before O⁺, and which species reaches the cathode. Consequence for the
  RFP: "ionise nascent O" is a **wall-material decision**, not only a thruster decision — and the
  AO-beam test (RFP 4.1a) must measure recombination coefficient γ, not just erosion yield.
- Material class notes for emitters/plasma-facing parts (LaB₆, BaO-W poisoning; W/Mo volatile oxides; BN, alumina, SiC stable).

### Intake–compressor sizing (`sizing.py`)
`python -m abep_sim.sizing` → for 180/200/230 km × low/mean/high, for 12 and 25 mN sustained on air,
per architecture: available mg/s per m², intake area required, delivered mg/s, **passive ram compression**
(free-molecular flux balance: n_p/n = 4 η_c V/c̄ · A_in/A_throat ≈ 180–210 at area ratio 10), passive outlet
pressure, required active ratio to reach 3× the thruster's minimum inlet pressure, compressor power/mass, T/D, total mass.
Headline (accommodation 0.5, area ratio 10):
- Passive intake alone gives 0.004–0.02 Pa; a shielded Hall needs ~0.045 Pa → active ratio 2–12 at
  180–200 km, 7–32 at 230 km. The compressor is a small machine (50–140 W) — **if** the passive stage
  performs as free-molecular theory says. That is the DSMC item.
- Single-stage Hall for 25 mN on air: 1.1–3.3 m² at 180–200 km, 4–16 m² at 230 km (mass fails at 230 km low/mean).
- ECR+Hall for 25 mN on air: 0.56–1.6 m² at 180–200 km, 1.9–8 m² at 230 km.

### Mission transient (`transient.py`)
`python -m abep_sim.transient --arch hall_ecr --area 0.7 --acc 0.3 --cr 2000 --vd 300 --phase 0`
Hour-by-hour over 26,000 h: F10.7 solar cycle (phase selectable), density interpolation, drag, available
air thrust, altitude-hold controller (flow-throttled), Xe topping policy, orbit decay
(da/dt = 2a^1.5(T−D)/(m√μ)), Xe/energy/AO-fluence bookkeeping, re-entry detection.
Findings:
- Single-stage Hall re-enters from 200 km in **~90 h** with any Xe policy short of continuous topping (T/D≈0.4).
- ECR+Hall with 1 m² ram face holds 200 km only until drag exceeds the RFP's 25 mN cap
  (solar rising phase → re-entry at ~10,400 h); with **0.7 m²** it holds all 26,000 h, 100 % duty, ~1.07 kW mean,
  4.7 kg Xe (cathode). Launching at solar max with 1 m² re-enters in 67 h.
- Therefore the RFP's 12–25 mN window implies a DRDO spacecraft ram area of **≤ ~0.7 m² at 200 km**
  or a higher hold altitude at solar max. Ask DRDO for the spacecraft ballistic coefficient.

### Interactive explorer (`explorer.py`)
`python -m abep_sim.explorer results/baseline/sweep.csv explorer.html` → single-file HTML (Chart.js from cdnjs),
filters on architecture/altitude/solar/CR/Vd/surface state, RFP limits drawn, top-25 table by any metric,
"ignore thruster-IC check" toggle for the microwave-source IC question.

## v0.3 — uncertainty & sensitivity (`uncertainty.py`)
`python -m abep_sim.uncertainty --arch hall_ecr --alt 180 --solar mean --area 0.5 --cr 2000 --vd 300 -n 2000 [--map]`

28 priors become triangular distributions (collection efficiencies, accommodation, C_D, compressor coefficients,
Hall η_u/η_b/η_v/p_min, ECR/RF boost, cap, **interstage transport efficiency** (new `Stage1.transport_eff`),
source efficiency, stage power/mass/IC, PPU, wall recombination γ). Outputs: P(rfp_compliant), P(abep_closed),
T/D quantiles, Spearman global sensitivity, one-at-a-time tornado, and a robustness map over the ECR+Hall grid.

### Result: the 12 nominal closure points are not robust
- At the best point (180 km mean, 0.5 m², CR 2000, 300 V): **P(closed) ≈ 3–5 %** (IC prior ignored),
  T/D p10/p50/p90 = 0.55 / 0.75 / 0.96. The nominal sweep closed only because it used accommodation 0.3
  and the ECR gain at its mode with lossless interstage transport.
- Robustness map: no ECR+Hall design point exceeds P(closed) ≈ 5 %. Raising Vd to 400–450 V lifts T/D
  (p50 0.86–0.91) but P(rfp_compliant) falls because power exceeds 1.5 kW in the upper tail.
- Everything reduces to one product: **T/D ≈ 4.35 · η_c · η_u** (fit, 300 V, N₂/O₂ inlet). Closure needs
  η_c·η_u ≥ 0.23. Nominal medians give ≈ 0.19.
- Sensitivity ranking (Spearman on T/D): ECR gain 0.48, η_c,specular 0.46, accommodation −0.38, η_c,diffuse 0.30,
  C_D −0.29, Hall η_u,max 0.28, interstage transport 0.28. Everything else (compressor, PPU, masses, source
  efficiency, p_min, γ) is < 0.06 — irrelevant to closure, relevant only to compliance margins.
- Conditional: P(closed | η_c ≥ 0.40 and ECR gain ≥ 0.25) ≈ 0.42; P(closed | η_c ≥ 0.45) ≈ 0.25 (small n).

### What this means for the programme
The intake is the closure variable, not the thruster: an AO-aged diffuse intake (accommodation → 0.7–0.8)
kills closure regardless of the pre-ioniser. The two experiments that move P(closed) are (1) η_c versus AO
fluence on candidate near-specular surfaces (DSMC + AO-beam coupons), and (2) ECR-stage net utilisation gain
including interstage transport, measured, not assumed. The DPR should state closure as a probability with
these two as the named drivers — not as a nominal T/D = 1.05.

## v0.3.1
Three classifications now come from `system.py` and are used everywhere (sweep, explorer, UQ):
`rfp_compliant` (all RFP limits), `abep_closed` (+ T > D on air), and **`technical_compliant` / `technical_closed`**
(same, with *both* IC checks removed). The old `closed_ignoring_ic` in `uncertainty.py` — which still kept
`chk_ic_total` — is replaced by `technical_closed`. Hierarchy enforced by test.

## v0.3.2 — PDR-1 acceptance thresholds (`thresholds.py`)
Treats the three closure drivers as *measured* inputs (effective intake η_c after AO exposure; net ECR gain
Δη_u·η_transport) and computes P(technical_closed) with every other prior still sampled — with intake area and
V_d re-optimised per cell, so better physics is not penalised by a fixed design (fixed-design P(closed) falls
at high performance because thrust runs into the 1.5 kW cap; the design must shrink the intake instead).

| η_c,eff ↓ / net ECR gain → | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 | 0.35 |
|---|---|---|---|---|---|---|
| 0.35 | 0 | 0 | 0 | 0 | 0.08 | 0.23 |
| 0.40 | 0 | 0 | 0.05 | 0.25 | 0.58 | 0.73 |
| 0.45 | 0 | 0.07 | 0.37 | 0.72 | 0.79 | 0.84 |
| 0.50 | 0.07 | 0.36 | 0.70 | 0.79 | 0.96 | 0.96 |
| 0.55 | 0.27 | 0.64 | 0.79 | 0.95 | 0.98 | 0.98 |

(Superseded by v0.4 table below.)

## v0.4 — audit corrections
1. **Drag closure scope.** `body_area_m2` (spacecraft frontal area beyond the intake) is now an explicit `Config`/grid
   input, default 0, and every result row carries `drag_closure_scope` = "intake-face only" or "spacecraft". Until DRDO
   supplies frontal area, C_D, mass and attitude, all closure statements in this repo are **propulsion/intake-face closure**.
2. **Atmosphere.** `pymsis` (NRLMSIS 2.1) is now used when installed, orbit-averaged over latitude −60…60 and four
   local-time sectors, F10.7 = F10.7A = 70/150/230 (or numeric), Ap = 15. Every sweep row reports `atm_source`.
   The built-in table remains the fallback and is within ~15 % of MSIS at all nine states.
3. **Joint gas-surface state.** UQ no longer samples accommodation and C_D independently: one latent `surface_state`
   (0 fresh-specular → 1 AO-aged diffuse) drives accommodation (hence η_c and passive CR) and C_D = (1−s)·C_D,spec + s·C_D,diff.
   Placeholder for the DSMC response surface (η_c, C_D, CR_passive) = f(geometry, accommodation, AO, angle).
4. **Conductance coupling.** `CompressorParams.anode_conductance_m3_s` switches the reservoir to a throughput balance
   p = ṁ·k·T/(m·C) (floored at the passive ratio) instead of a prescribed density ratio; `backflow_frac` removes leakage
   before the anode. Prescribed-ratio mode is kept for screening.
5. **O₂ dissociation sink is now consumed** in `performance()` (`o2_diss_fraction` × ionised O₂ mass × 5.12 eV);
   ≤ 13 W across the sweep — architecture ranking unchanged, as predicted.
6. **`thresholds.py` now contains the re-optimisation loop** (intake area and V_d per cell, screened at n/5, winner
   re-evaluated at n), default n = 1000, CLI, and a test.

### v0.4 PDR-1 thresholds — P(technical_closed), n = 600, area/V_d re-optimised, NRLMSIS 2.1, joint surface state

| 180 km mean | gain 0.20 | 0.25 | 0.30 |   | 200 km mean | 0.20 | 0.25 | 0.30 |   | 230 km mean | 0.25 | 0.30 | 0.35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| η_c 0.40 | 0.09 | 0.44 | 0.80 |   | | | | |   | | | | |
| η_c 0.45 | 0.55 | **0.88** | 0.85 |   | η_c 0.45 | 0.52 | **0.88** | 0.95 |   | η_c 0.45 | 0.56 | **0.77** | 0.84 |
| η_c 0.50 | 0.84 | 0.93 | 0.98 |   | η_c 0.50 | 0.88 | 0.93 | 0.98 |   | η_c 0.50 | 0.80 | 0.83 | 0.85 |
| η_c 0.55 | 0.91 | 0.98 | 0.99 |   | | | | |   | η_c 0.55 | 0.80 | 0.86 | 0.89 |

Chosen designs: 0.3–0.5 m² / 250–300 V at 180–200 km; **1.5 m² / 250–300 V at 230 km** (the 12 mN-on-air floor forces
the larger intake there, which is also why 230 km is the hard case: mass and power margins shrink, not T/D).
200 km does not need extra ECR gain once the intake is resized — the earlier README sentence is withdrawn.
Design targets with margin (not the cliff edge): **η_c,eff ≥ 0.50 after AO exposure; net gain Δη_u·η_transport ≥ 0.25,
stretch ≥ 0.30 for 230 km.** Nothing here proves 230 km / solar-minimum closure.

## v0.5 — mission-level closure, mass CBE/MGA/MEV, provenance
- **`mission_uq.py`** — the number to trust: P[∀t ∈ 0…26,000 h: altitude held ∧ T ≥ D ∧ P_bus < 1.5 kW ∧ Xe not exhausted
  ∧ m_MEV ≤ 40 kg ∧ life ≥ 1], sampled over the joint priors (epistemic) and solar-cycle launch phase (aleatory),
  with the limiting mechanism per sample. Mass uses the mission's actual Xe consumption (+20 % reserve), not the
  static "12 mN-on-air-else-Xe" rule. `--eta-c` / `--gain` impose measured drivers.
- **Mass** now reported as CBE / MGA / MEV (item-class growth: 30 % new design, 15 % modified, 5 % existing) alongside
  the legacy flat-margin total; `chk_mass_mev` and `chk_mass_cbe_target` (32 kg internal target).
- **Provenance**: every `Prior` carries source, fidelity (analytical → literature → breadboard → qualified), epistemic/
  aleatory kind and test_id; `set_measured()` replaces a prior with a measurement and records it; `provenance_table()`.
- README wording corrected: neutral thermal gas-phase chemistry is negligible in the rarefied path; electron-impact
  plasma chemistry in the ioniser/thruster is essential (next physics block).

### Mission-level results, ECR+Hall, 200 km, CR 2000, 300 V, 150 kg spacecraft, n = 120

| Case | P(mission closed) | limits | CBE / MEV kg | 12 mN on air at mean solar |
|---|---|---|---|---|
| literature priors only, 0.5 m² | **0.18** | re-entry 75 %, mass 7 % | 33.7 / 38.7 | 0 % |
| η_c = 0.50, gain = 0.25, 0.4 m² | 0.99 | mass 1 % | 30.3 / 35.0 | 0 % |
| η_c = 0.50, gain = 0.25, 0.5 m² | 0.97 | mass 3 % | 30.8 / 35.6 | 12 % |
| η_c = 0.50, gain = 0.25, **0.6–0.7 m²** | **0.95–0.97** | mass 3–5 % | 31–32 / 36–37 | **95–100 %** |
| η_c = 0.50, gain = 0.25, 0.8 m² | 0.91 | mass 8 %, power 1 % | 32.2 / 37.3 | 100 % |
| η_c = 0.45, gain = 0.25, 0.5 m² | 0.97 | mass 3 % | 30.8 / 35.7 | 0 % |

Reading: with the two PDR-1 targets met, the mission closes with ~95 % probability and the residual limit is MEV mass,
not physics. The RFP's 12–25 mN window maps onto a **0.6–0.8 m² ram face at 200 km** (12 mN floor at mean solar,
25 mN cap at solar max); smaller spacecraft close more easily but cannot show 12 mN on air. Ask DRDO for the bus.

## Phase 1 — Environment & intake physics (roadmap items 1, 2, 3, 4, 5, 36)
- **`orbit_atm.py`** — along-track NRLMSIS 2.1 over a circular Keplerian orbit (inclination, RAAN, epoch, F10.7/F10.7A/Ap),
  co-rotating atmosphere → V_rel (SSO at 200 km: 7,857 m/s vs V_orb 7,788), species O/N₂/O₂/N/He/H/Ar, mean free path
  (240–510 m at 200 km) and Knudsen number. J2 and drag-coupled propagation arrive in Phase 5.
- **`intake_tpmc.py`** — test-particle Monte-Carlo, free-molecular (valid: Kn ≫ 1 all the way into the plenum — at
  0.08 Pa the mean free path is ~0.1 m > channel diameter), honeycomb of circular channels (d, L/d, φ), Maxwell
  accommodation α per wall hit (0 specular … 1 diffuse), incidence θ, optional filter. Returns η_c, C_D, Clausing
  back-transmission K_back, passive CR from flux balance, and geometric mass (substrate + coating + supports).
  `response_surface()` + `IntakeSurface` give an interpolating ROM over (L/d, φ, α, θ); `IntakeParams(use_tpmc=True)`
  routes the system model through it. Surfaces are cached per atmosphere state.

Physics it reproduces (200 km mean, φ 0.85):

| L/d | α | η_c | C_D | K_back | CR_passive |
|---|---|---|---|---|---|
| 3–20 | 0.0 | 0.85 | 2.03 | 1.00 | 52 |
| 10 | 0.3 | 0.70 | 2.05 | 0.36 | 121 |
| 10 | 1.0 | 0.43 | 2.08 | 0.11 | 234 |
| 20 | 1.0 | 0.35 | 2.09 | 0.10 | 219 |

The known ABEP intake trade falls out: specular walls collect but do not compress (backflow is also transparent);
diffuse walls compress but lose collection. η_c and CR_passive are now the *same* physics, as the audit required.
Coupled into ECR+Hall (0.6 m², CR 2000, 300 V): realistic α = 0.7–1.0 (5 eV O on engineering coatings is mostly
diffuse) gives η_c 0.42–0.68 → T/D 1.2–2.0 at L/d 5–10; L/d 20 breaks the mass budget (MEV 45–48 kg) before it
helps. The parametric prior (η_c ≈ 0.38) corresponds to α ≈ 0.8–1.0, L/d 10–20 — i.e. it was the pessimistic
(aged, long-channel) corner. An *actively pumped* intake collects the forward transmission; only a passive intake
pays the full backflow penalty — this is why compressor + short specular-leaning channel is the right pairing.

Limits: single-channel, no edge/inter-channel effects, Maxwell (not CLL) scattering, surface temperature fixed.
Not a DSMC replacement for the compressor internals; it is the correct tool for the intake itself.

## Phase 2 — Gas path physics (roadmap items 6, 7, 8, 21)
- **`materials.py`** — 18 materials with density/E/yield/CTE/k/cp/ε/α, AO erosion yield, O-recombination
  γ(T) = γ_min + γ₀·exp(−Ea/kT), Bohdansky-shaped sputter yield Y(E), Vaughan-lite SEE δ(E), TML/CVCM, TID, T_max,
  each with a fidelity tag and `set_property()` provenance; `surface_ageing_alpha(α₀, Φ_AO)` for AO-driven
  accommodation drift feeding the TPMC intake.
- **`compressor.py`** — turbomolecular first stage (blade rows, S = k_S·u·A, ln K₀ = k_K·u/c̄ per row) followed by
  optional Holweck drag stages; species-resolved Gaede characteristic K = K₀ − (K₀−1)·Q/(S·p); free-molecular blade/
  channel shear power, bearing and motor losses; rotor hoop-stress tip-speed limit from the materials DB; leakage;
  lumped temperature; geometric mass. `size_for()` finds the lightest machine reaching a target ratio.
- **`reservoir.py`** — species-resolved steady-state balance dm_s/dt = ṁ_in − n_s·C_s·m_s + R_s with molecular
  conductances (∝ c̄_s), leak path, wall recombination O + O(ads) → O₂ at γ(T) of the wall material, upstream
  (compressor) collisions, residence time and wall-collision count; mass-conserving; `size_orifice_for_pressure()`.
- `Config(gaspath_physics=True, rotor_material=…, reservoir_material=…)` routes the system through all three.

What the physics says (200 km mean, ECR+Hall):
1. **The compressor is pumping-speed-limited, not compression-limited.** 1 mg/s at 0.005–0.01 Pa is 13–26 m³/s of
   volumetric flow. A Holweck drag stage (S ≈ 0.004 m³/s) does nothing at the inlet; the first stage must be a
   turbomolecular rotor spanning the intake throat (0.25–0.45 m²) at 350–430 m/s tip speed. Ti (u_max ≈ 315 m/s)
   is marginal; CFRP (≈ 430 m/s) works. Once S > Q/p the ratio jumps (cliff), so the reservoir orifice/channel sets p.
   Sized machine: 3 CFRP rows, 10–12 krpm, CR 8–9, **14–18 W, 4–5 kg**, 330–340 K — cheaper in power than the
   parametric prior, heavier, and hotter at high tip speed (459 K at 433 m/s, 6 rows).
2. **Species selectivity**: the turbo compresses N₂ ~2.5× more than O (c̄ ∝ 1/√m) — the reservoir is O-depleted before
   any chemistry. With anodised-alumina walls O survival is ~0.9; Ti ~0.35; stainless ~0.6 downstream of a CFRP rotor
   and ~0.01 if the whole path is stainless. **Wall material choice is worth more nascent O than any thruster trick.**
3. **The rotor blades are the most AO-exposed moving surface in the system** (5 eV O at 430 m/s tip): bare CFRP erodes
   (2.6e-24 cm³/atom); blades need an AO-resistant coating or Al/Ti at lower speed with larger area. Open item.
4. **Closure with physics, no priors on η_c/CR/γ** (TPMC intake L/d 5, φ 0.85; CFRP turbo; alumina reservoir; 250–300 V):

| ram face | α | η_c | ṁ mg/s | p_in Pa | T_air mN | Isp s | P_total W | CBE / MEV kg | T/D | closed |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 m² | 0.80 | 0.65 | 0.70 | 0.045 | 18.8 | 2549 | 1181 | 29.6 / 34.4 | 2.17 | yes |
| 0.4 m² | 0.80 | 0.65 | 0.56 | 0.045 | 15.0 | 2506 | 990 | 29.8 / 34.2 | 2.17 | yes |
| 0.4 m² | 0.95 | 0.61 | 0.53 | 0.045 | 12.9 | 2275 | 835 | 30.8 / 35.3 | 1.85 | yes |
| 0.5 m², L/d 10 | 0.80 | 0.50 | 0.54 | 0.045 | 13.3 | 2281 | 857 | 34.4 / 39.9 | 1.52 | yes |
| 0.4 m², L/d 10 | 0.95 | 0.45 | 0.39 | 0.045 | 9.5 | 2203 | 675 | 45.8 / 51.0 | 1.35 | no (12 mN floor) |

The Phase-0 parametric model (η_c 0.35 prior, γ^N stainless) gave T/D 0.94 at the same point. The physics
models replace the pessimistic corner with a short-channel, actively-pumped, alumina-lined design that closes with
margin **if** the intake surface behaves as Maxwell-α ≤ 0.95 and the rotor survives AO. Those two are now the
measurements: α after AO fluence on the coupon (feeds `surface_ageing_alpha`), and blade coating erosion.

## Phase 3 — Plasma physics (roadmap items 9–18, 22)
- **`plasma_chem.py`** — global (0-D) model: O, O₂, N₂, N, Xe neutrals; O⁺, O₂⁺, N₂⁺, N⁺, Xe⁺; Maxwellian T_e.
  Ionisation, dissociative ionisation, O₂/N₂ dissociation, lumped excitation/vibrational loss ε_c(T_e), Bohm wall
  and exit losses, magnetised-wall factor, neutral effusion. Particle balance → T_e, power balance → n_e.
  Outputs species ion currents, utilisation, eV per usable ion, power partition, dissociation fractions, overdense ratio.
- **`plasma_devices.py`** — `ECRSource` (DC→µW efficiency, feed loss, pressure gate, overdense penalty), `RFSource`
  (ICP coupling R_p/(R_p+R_coil), collapses below ~0.05 Pa), `Interstage` (magnetised cross-field wall loss, entrance
  barrier, charge exchange), `HallChannel` (SEE-limited T_e from the materials DB, ionisation-zone residence, Bohm
  exit, anomalous electron back-current, species-resolved thrust, plume CX, sputter erosion with magnetic-shielding
  factor), `LaB6Cathode` (Richardson emission, irreversible O-oxide coverage vs thermal cleaning, Xe-orifice
  attenuation, evaporation life). Calibrated: Marchioni N₂ (2 mg/s, 250 V → 24 mN, 690 W, 1230 s), SPT-100 Xe
  (5 mg/s, 300 V → 91 mN, 0.96 utilisation). `Config(plasma_physics=True, s1_power_dc_W=…, hall_L_m=…, hall_wall=…)`.

### What the plasma physics says (200 km mean, physics intake + gas path, 300 V)
1. **A Hall channel cannot self-sustain on air below a flow threshold that depends on channel length**: 10 cm →
   ≥1.5 mg/s; 20 cm → ≥0.8 mg/s; 30 cm → ≥0.5 mg/s. This is the extended-channel argument, derived. ABEP flows
   (0.5–1.4 mg/s) sit exactly on this threshold — the discharge either starves or over-ionises (bifurcation).
2. **The ECR stage is expensive**: 200–250 eV per usable ion absorbed (≈ 350–400 eV/ion DC), 2.45 GHz is overdense
   (n_e/n_c 1.3–4), the interstage passes 45–60 %. At 450 W DC it delivers ~0.3–0.4 A of pre-ionisation — a net beam
   utilisation gain of ~0.13, not the 0.25–0.30 the prior assumed at 150–250 W.
3. **What closes**: single-stage extended Hall, **20 cm channel, 0.7 m², 0.98 mg/s → 18.3 mN, 755 W total, T/D 1.51,
   MEV 35 kg**. ECR+Hall at the same point → 13.6 mN at 1135 W. The pre-ioniser earns its keep only below the Hall
   sustainment flow; above it, channel length is the cheaper lever.
4. **Erosion is the next wall**: BN at T_e ≈ 27 eV (SEE-limited) sees ~150 eV ions; even with a shielding factor of
   0.08 the model gives 350–450 µm/kh → 5–7 mm over 15,000 h. Lower T_e (V_d 200–250 V), better shielding (≤ 0.03)
   or SiC/BN-SiO₂ walls are the levers; Phase 4 turns this into a life prediction.
5. Cathode: with a Xe-orificed LaB₆ (attenuation ~10⁻³) the emitter runs ~1720 K, coverage 5 %; bare in the plume
   it climbs to ~1950 K at 50 % oxide coverage. Evaporation life is not the limit; poisoning is.

Caveats: rate coefficients and ε_c are literature-class fits; the sustainment threshold is sensitive to `L_iz_frac`
(bifurcation) and must be calibrated on the breadboard; the ECR chamber geometry (V, wall area, magnetisation) moves
stage-1 utilisation by ±50 %. These are now explicit parameters, not hidden in one number.

## Phase 4 — Life, thermal, power electronics, mass (roadmap items 19, 20, 23, 24, 25, 27–32, 41 partial)
- **`thermal.py`** — 7-node lumped network (intake, compressor, thruster, magnets, stage-1 source, cathode, PPU) +
  radiator; solar/Earth-IR/albedo, **ram aerodynamic heating** (½ρV³α ≈ 50 W/m² at 200 km), conduction to radiator,
  Newton solve for hot (sunlit) and cold (eclipse); radiator sized to keep every node under its limit; thermal mass
  from areal density. Thruster waste heat = discharge power − beam power.
- **`ppu.py`** — per-converter efficiency maps (fixed + I² + switching losses, step-ratio and temperature derating),
  anode/magnet/keeper/heater/motor/aux (+ 4 kV magnetron or RF amp), cold-redundant duplicates, harness/controller/
  sensors/switch-matrix/housing mass; **startup / steady / peak** load modes; PPU temperature fed back from thermal.
- **`life.py`** — Hall wall: sputter (from the plasma model) + AO chemical erosion → remaining thickness and life;
  intake coating erosion and α(Φ_AO) drift; **turbo blade AO erosion at (V_rel ⊕ tip speed) impact energy with a
  pinhole-exposed substrate**; magnet temperature/demag margin; cathode evaporation and start cycles; bearings;
  series reliability (exponential electronics with redundancy, Weibull β = 3 wear-out) → R(15,000 h), R(26,000 h).
- **`mass_bom.py`** — Xe tank from pressure-vessel sizing, low-pressure reservoir at minimum gauge, Hall magnetic
  circuit from MMF/flux (SmCo rings + iron yoke/poles), channel ceramic, frame/brackets (the mounting deck is the
  spacecraft's — reported separately), CBE/MGA/MEV by item class.
- `Config(engineering_physics=True, hall_shielding=…, hall_wall_mm=…, blade_coating_um=…, xe_aug_hours=…)`; thermal
  feasibility and life join the hard gate; power and mass gates use the PPU bus power and the BOM MEV.

### Full-chain result (Phases 1–4), extended Hall, 200 km mean, TPMC intake L/d 5 α 0.8, CFRP turbo, alumina reservoir

| ram face | channel | V_d | blade coat | Xe reserve | T mN | T/D | bus W (peak) | Hall life h | blade life h | R15k / R26k | CBE / MEV kg | closed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.7 m² | 20 cm | 300 | 20 µm | 1500 h | 18.3 | 1.51 | 710 (885) | 36,400 | 11,300 | 0.09 / 0.00 | 40.6 / 47.0 | no |
| 0.7 m² | 20 cm | 300 | 50 µm | 500 h | 18.3 | 1.51 | 710 (885) | 36,400 | 28,300 | 0.80 / 0.32 | 37.3 / 43.4 | no (mass) |
| 0.6 m² | 25 cm | 250 | 50 µm | 500 h | 14.5 | 1.39 | 533 (741) | 47,600 | 28,300 | 0.83 / 0.39 | 35.2 / **40.8** | no (0.8 kg) |
| 0.7 m² | 20 cm | 275 | 50 µm | 500 h | 17.5 | 1.45 | 660 (838) | 36,400 | 28,300 | 0.80 / 0.32 | 37.1 / 43.2 | no (mass) |

BOM at 0.7 m² / 20 cm / 275 V (CBE → MEV): intake 3.3→4.3, compressor 6.7→8.7, reservoir+feed 1.1, Hall channel
1.2→1.4, magnetics 3.1→3.6, cathode 1.1→1.3, Xe 4.1→4.5, tank 1.0, PPU converters 5.1→5.8, control+sensors 1.6→1.8,
housing/shield 2.3→2.4, harness 1.4→1.5, thermal 0.7, structure 4.6→5.1. **Total 37.1 → 43.2 kg.**

Findings:
1. **Physics closes T > D with 700–900 W bus power and ~0.8 m² of radiator-free margin** (PPU is the thermal limiter;
   waste heat 120–160 W). Power is not the problem.
2. **Mass is.** With cold-redundant converters (RFP redundancy), a 6–9 kg turbomolecular compressor, 3–4 kg magnetic
   circuit and even a 500 h Xe reserve, MEV lands at **41–43 kg** against 40. The 32–34 kg CBE target is right; the
   MGA takes it over the line. Levers: Xe reserve (≈1.9 kg per 500 h), non-redundant low-power converters
   (≈1.5 kg), lighter rotor (Ti blades at larger area), and the compressor's 30 % new-design MGA maturing.
3. **Turbo-blade AO erosion is the reliability driver**, not the Hall channel: 20 µm alumina on CFRP with 1 % pinholes
   lasts ~11,000 h; 50 µm ~28,000 h (R26k 0.3–0.4 because the Weibull knee sits at the mission end). Hall life at
   shielding 0.03 / 6 mm BN is 36,000–52,000 h. The blade coating is a coupon test with the same AO beam.
4. Cathode: 541 starts over the mission (well under 10,000); evaporation life not limiting.
5. The hot-case magnet temperature is 333–336 K — SmCo fine; the stage-1 magnetron, if used, needs its own 1.4 m²
   radiator (5.9 kg) — another reason the pre-ioniser is the contingency, not the baseline.

## Phase 5 — Mission & environment (roadmap items 26, 33–41)
- **`mission_env.py`** — `Spacecraft` (bus frontal area, arrays edge-on or not, span/thickness, pointing σ, EPS
  efficiency, housekeeping, inclination, LTAN); `spacecraft_drag` (intake + bus + arrays with Gaussian pointing:
  cos² collection loss and sin(θ) array exposure); `plume_interaction` (direct beam tail into the array cone, CEX
  backflow, coverglass sputter); `sso_inclination_deg`; β-angle and eclipse fraction; `propagate` (secular J2 RAAN
  drift, co-rotation, full-spacecraft drag, thrust, orbit-average array power vs demand).
- **`radiation.py`** — parameterised dose-depth (TID, DDD) and SEU rates for a 200 km high-inclination orbit,
  device library with RDM = 2 margins, shielding mass; UV absorptivity drift; AO-oxidised contamination → intake
  accommodation increment; micrometeoroid/debris Poisson puncture probability.
- **`mission5.py`** — the full chain on the real profile: solar cycle, AO-fluence-driven intake ageing through the
  TPMC ROM, power-limited flow throttling, altitude hold, radiation, plume, debris, reliability on the actual hours.
  Atmosphere lookups now come from a 5 km × 3-state MSIS grid and one global TPMC surface (a 26,000 h run ≈ 5 s).

### What the mission model says (extended Hall 0.7 m² / 20 cm / 275 V, 18 mN class; 150 kg bus)
| spacecraft | D mean | intake share of drag | T mean | P bus / P avail | result |
|---|---|---|---|---|---|
| bus 0.25 m², arrays 2 m² edge-on, σ 1° | 27.5 mN | 44 % | 21.9 mN | 783 / 595 W | re-entry |
| bus 0.10 m², arrays 3.5 m² edge-on, σ 0.5°, dawn-dusk | 18.4 mN | 66 % | 18.3 mN | 683 / 1070 W | re-entry (eclipse-season throttle) |
| same, arrays not edge-on | 215 mN | 6 % | — | — | re-entry in days |
| same, σ 2° | 23 mN | 53 % | 20.6 mN | — | re-entry |

1. **The intake is only 45–65 % of the spacecraft's drag.** The bus and the *edges* of the solar arrays cost 6–9 mN;
   arrays that are not knife-edge to the flow cost 200 mN. At 200 km the spacecraft is an aerodynamic object first.
2. **Power and drag are coupled through the arrays.** A 700–800 W propulsion bus needs ≥ 3.5–4 m² of arrays at 200 km
   even dawn-dusk, because the shadow cone at 200 km still produces eclipse seasons (β_min ≈ 66° < 76° needed);
   every m² of array adds edge drag and pointing sensitivity. Body-mounted cells do not reach 800 W.
3. **There is no recovery in VLEO.** A thrust deficit of a few mN for a few days is a runaway: density rises as the
   orbit sinks. The design needs T/D ≥ 1.3–1.5 *on the whole spacecraft* at the worst eclipse season and solar
   phase, not T/D ≈ 1 at a design point. With the calibrated physics that means ~28–32 mN of air thrust capability
   for a 0.1 m² bus — above the RFP's 25 mN — or a smaller/lower-power spacecraft, or Xe augmentation in peaks.
4. **Radiation is not a driver** — 12.9 krad(Si) behind 2 mm Al over 3 years; rad-tolerant MCU/GaN/1553 parts have
   > 2× margin, COTS screened MCUs do not. **Debris/micrometeoroid** puncture probability of the intake < 1e-4.
   **Plume** erosion of coverglass < 0.01 µm with knife-edge arrays at 75° from the axis.
5. AO ageing of the intake (α → 1) costs ~30 % of collected flow over the mission at the fast-ageing prior; at
   φ_c = 1e28 it costs ~10 %. This is the coupon measurement with the highest leverage after the plasma sustainment curve.

**The mission-level conclusion for the DPR and for DRDO:** the propulsion system closes; the *spacecraft* has to
be designed around it — ≤ 0.1 m² bus frontal area, knife-edge deployable arrays of 3.5–4 m², pointing ≤ 0.5°,
dawn-dusk SSO, and either an altitude band (decay/raise) or Xe-assisted peak thrust above 25 mN in eclipse seasons.
None of that is in the RFP; all of it decides whether the ABEP flies.

## Phase 6 — UQ & optimisation on the full chain (roadmap items 42–47, 49, 52, 53)
- **`uq6.py`** — 19 priors over the *physics* chain, each tagged epistemic / aleatory / **tolerance** (channel gap ±1 mm,
  B ±10 %, honeycomb L/d and open fraction, coating thickness); **Gaussian-copula correlation within groups** (surface
  state ↔ ageing fluence, plasma coefficients, compressor coefficients); `evaluate_full` patches the physics modules
  per sample (rate and ε_c multipliers, γ multiplier, anomalous transport, ionisation-zone fraction, pumping
  coefficients, switching losses) and runs the whole Phase 1–5 chain at the design point (**≈15 ms/eval** once the
  TPMC surface is cached); **mission ROM** (item 53): closure requires T_air(end-of-life η_c, density scatter) ≥
  k_season · D_spacecraft with k_season = 1.35 from Phase-5 runs, so the Monte-Carlo never calls the 5 s propagator;
  **conservation checker** (item 49): mass, charge (I_d = I_b/η_b) and power residuals — a failed check is never
  feasible; **Sobol** (Saltelli/Jansen, independent samples); **Pareto** (LHS over area, channel length, V_d, Xe
  reserve; objectives T−D_sc, bus power, MEV, min life, Xe); **robust design** (P(mission ROM) ≥ target under the
  correlated priors); **ABC data assimilation** (item 52): measurements at test conditions accept/reject prior
  samples and rewrite the priors with `fidelity = breadboard`; **fidelity registry** (item 51/53).

### Results at the reference design (0.7 m² / 20 cm / 275 V, 0.1 m² bus, 3.5 m² arrays)
- Sobol total-order on end-of-life spacecraft T/D: **ionisation-rate scale ≈ 1.0**, intake accommodation 0.11,
  channel-gap tolerance 0.08, honeycomb open fraction 0.05, L/d 0.04; everything else < 0.01 (compressor coefficients,
  wall γ, PPU losses, shielding, density scatter, pointing). The Hall sustainment bifurcation makes the response
  bimodal, which is why S₁ exceeds 1 — the indices are qualitative; the ranking is not.
- Design-space census (240 LHS designs, nominal priors): 70 % have T > D_sc; **49 % meet closure (T/D_sc,EOL ≥ 1.35)**;
  82 % under 1.35 kW; **11 % under 40 kg MEV**; 88 % over 15,000 h life. **Closure ∧ power: 74 designs, MEV 42–54 kg.**
  Lightest closing design: 0.59 m², 28 cm channel, 310 V, 210 h Xe reserve → 832 W, **MEV 42.1 kg**, T−D = 8 mN, life 28 kh.
- Robust design on the three lightest closing candidates: **P(mission ROM) = 0** under the correlated literature
  priors — the T/D_sc p10 is 0.8–1.1, i.e. the lower half of the rate-coefficient / accommodation priors kills closure.
- ABC assimilation with two hypothetical breadboard measurements (17.5 ± 1.5 mN, 660 ± 60 W at the design point)
  narrows rate_scale from [0.7, 1.4] to [0.90, 1.14] and alpha0 from [0.55, 0.98] to [0.62, 0.91] — the first test
  campaign removes most of the epistemic spread that currently prevents robust closure.

### Where the whole programme stands after six phases
1. **The physics closes; the margins don't yet.** A 0.6–0.7 m² extended-channel Hall ABEP produces 15–18 mN on air at
   650–850 W and beats a 0.1 m² bus with knife-edge arrays by 30–50 % at beginning of life. It weighs 42–47 kg MEV
   against 40, and its closure probability under today's literature spread is ~0 because two coefficients — the
   ionisation rate on N₂/O₂ (sustainment) and the intake accommodation after AO — each span a factor that flips the
   answer. Neither is a design choice; both are measurements.
2. **The two experiments** (unchanged since v0.3, now with the physics behind them): (a) Hall discharge sustainment
   vs. N₂/O₂ flow and channel length on IIST's SPT diagnostics — calibrates `L_iz_frac` and `rate_scale`; (b) AO-beam
   coupons of the intake coating measuring accommodation (specular fraction) vs. fluence — calibrates `alpha0`, `phi_c`.
   ABC assimilation shows two numbers from (a) alone cut the rate prior by 3×.
3. **The spacecraft is the third variable.** Bus frontal ≤ 0.1 m², 3.5–4 m² knife-edge arrays, ≤ 0.5° pointing,
   dawn-dusk SSO, and a decay/raise or Xe-peak strategy for eclipse seasons. This belongs in the pre-bid queries.
4. **Mass** is the engineering problem, not power or thermal: compressor (6–9 kg), redundant PPU (~10 kg), magnetics
   (3–4 kg), Xe reserve (2–5 kg). A 40 kg MEV needs the 30 % new-design allowances to mature — i.e. a breadboard
   compressor and intake, which are the same hardware the two experiments need.

## v1.0 — Modular architecture engine and research mode (documents 12/13)
- **pymsis is now a hard dependency**; the table fallback warns loudly (reproducibility).
- **`archengine.py`** — stages with interfaces: `Ionizer` (Hall-internal, DC discharge, RF-ICP, helicon, ECR/microwave,
  arc) → `Accelerator` (Hall E×B, electrostatic grids, magnetic nozzle, MPD/Lorentz, PIT inductive, thermal nozzle;
  FEEP / electrospray / PPT carried with `air_compatible=False`) → `Neutralizer` (LaB₆/Xe, microwave air cathode,
  RF cathode, none). The enumerator connects only compatible stages (48 enumerated, 45 valid, 3 reported as
  propellant-incompatible). Every valid architecture runs through the same gas path (Phases 1–2), the global
  ionisation model (Phase 3), the accelerator physics, neutralizer, generic PPU/thermal/mass, spacecraft T/D and
  RFP flags. **Research mode**: RFP gates are reported, ranking is on physics. Accelerator physics: Child–Langmuir
  grids with CEX accel-grid erosion; ambipolar magnetic nozzle (≈6 T_e); Maecker MPD with onset; PIT with
  η(E_pulse) and capacitor-bank mass; resistojet/arcjet/MET from stagnation enthalpy.

### Architecture trade at the reference gas state (200 km, 0.7 m², CFRP turbo, 0.05 Pa, 0.98 mg/s; 0.1 m² bus, 3.5 m² arrays)
| architecture | T mN | Isp s | P_bus W | η_total | T/D_sc | MEV kg | life h | notes |
|---|---|---|---|---|---|---|---|---|
| **extended Hall + RF air cathode** | 17.5 | 1729 | 715 | 0.25 | **1.09** | **37.1** | 36,400 | Xe-free; all RFP flags pass; O-exposed electrodes |
| extended Hall + LaB₆/Xe | 17.5 | 1729 | 687 | 0.26 | 1.09 | 42.1 | 36,400 | mass fails on Xe + tank |
| RF-ICP + Hall | 14.5 | 1432 | 1087 | 0.11 | 0.90 | 49 | 43,000 | pre-ioniser costs more than it gives |
| helicon + Hall | 12.3 | 1215 | 1023 | 0.08 | 0.77 | 50 | 50,000 | |
| ECR + grids | 8.5 | 841 | 1307 | 0.03 | 0.53 | 49 | **645** | CEX erosion of the accel grid at 0.05 Pa |
| ECR + Hall (1 L chamber) | 8.4 | 827 | 903 | 0.04 | 0.52 | 49 | 70,000 | chamber geometry ±50 % |
| DC discharge + grids / Hall | 4.5–4.9 | 450–490 | 770–1060 | 0.01 | 0.3 | 40–45 | 1,100 (grids) | cathode in O plasma |
| ECR magnetic nozzle | 3.0 | 308 | 740 | 0.007 | 0.19 | 36 | 60,000 | cathode-less but 6 T_e is too little |
| arcjet / MET / resistojet | 2.3–2.8 | 240–290 | 1610 | 0.003 | 0.15 | 41–44 | 1,500–10,000 | Isp far below closure need |
| PIT | 1.7–1.9 | 180–200 | 1610 | 0.001 | 0.11 | 45–49 | 20,000 | η ≈ 5 % at 100 J pulses |
| MPD | 1.1 | 110 | 1610 | 0.000 | 0.07 | 43–47 | 8,000 | needs kA, not 40 A |

Two things the wider trade adds: (1) the Hall family's lead is now established against every air-compatible family
under the same closure, not against two variants of itself; (2) **the air-fed RF cathode is the mass lever** — it
removes 4–5 kg of Xe and tank and takes the extended Hall to 37 kg MEV with every RFP flag green, at the price of an
electrodeless emitter in the oxygen plume whose life is unmeasured (item for the AO-beam campaign).

### Full 26,000 h propagator (not the ROM) — closure envelope
| design | arrays | design T / P | mission | D mean | notes |
|---|---|---|---|---|---|
| 0.7 m² / 20 cm / 300 V (RFP 25 mN cap) | 3.5 m² | 18.3 mN / 710 W | re-entry | 18.4 mN | eclipse-season power throttle |
| 0.7 m² / 20 cm / 300 V | **5.0 m²** | 18.3 mN / 710 W | **holds 26,000 h** | 20.4 mN | P_avail min-season ≥ P_bus + 120 W |
| 0.85 m² / 20 cm / 275 V, cap 35 mN | 5.0 m² | 31.9 mN / 1099 W | **holds 26,000 h** | 23.6 mN | 47 kg MEV |
The mission closes when two inequalities hold simultaneously at the worst eclipse season and solar phase:
P_arrays(1 − f_ecl,max)·η_EPS ≥ P_bus,full + P_housekeeping, and T_full ≥ ~1.3·D_spacecraft. At 200 km dawn-dusk
that is ≈ 5 m² of knife-edge arrays for a 700–800 W propulsion system. The array area, not the thruster, sets the bus.

### Backlog (from the audit, in priority order)
DSMC for the plenum/compressor interface (Kn → transition); compressor validation (rotor dynamics, pumping-speed
maps, bearings); an EM field solver or calibration for ECR resonance/overdense coupling; NO/NO⁺, metastables, O⁻ and
state-resolved N₂ in the chemistry, kept only if sensitivity says so; interface-level mass/charge/momentum/energy
ledgers; Sobol with bootstrap CIs plus Shapley effects for correlated inputs; SPENVIS/OMERE radiation environment.

## v1.1 — Audit rectifications (document 14, P0 set)
1. **Interfaces**: `hall_internal` feeds only Hall; MPD/PIT/resistojet are `self_ionizing` (`self` ionizer); thermal
   branch split into resistojet / arcjet / electrothermal-from-plasma (MET, RF-ET, helicon-ET) with different limits.
2. **Upstream state consumed**: MPD voltage split (ionisation drop falls with χ_i, Spitzer resistive drop from T_e,
   onset relaxed by χ_i); PIT η raised by χ_i (sheet formation); thermal branch takes T_e/χ_i and a frozen-flow loss.
3. **Neutralizer current/life closure**: `Neutralizer.operate(I_req, p_O)` — LaB₆ via the Phase-3 model; plasma-bridge
   cathodes (microwave / RF on air) via a small global discharge with extraction calibrated to the AMPCAT point
   (0.8 A at 145 W, 0.1 mg/s). A Hall at 25 mN needs ~3 A; the air cathodes deliver ~0.8–0.95 A at up to 470 W and
   their sputter life in the cavity is tens of hours. **The 37 kg "RF air cathode" result is withdrawn**: the current
   is not closed, exactly as the audit predicted. The lever survives only if a ~3 A, >15,000 h air cathode is
   demonstrated — a test, not a design choice.
4. **System life = min over all components** (channel, grids, neutralizer, blade coating, intake coating, bearings, PPU),
   with the limiting item named.
5. **Canonical PPU / thermal / BOM**: `ppu.py` converters per architecture (anode, keeper, heater, magnet, motor, RF/HV
   magnetron, MPD high-current, PIT capacitor charger, resistive heater), `thermal.py` radiator sizing from the
   energy ledger (device electrical − jet power), `mass_bom.py` with per-item MGA by maturity.
6. **Nested optimisation** (item 38): each architecture searched over its own variables (Hall: V_d × channel length;
   plasma stages: P_ion; grids: V_b; MPD/thermal: P_acc; PIT: P_acc × E_pulse) for max (T − 1.3·D_sc) inside
   `DesignConstraints(P_bus_max_W)`; the RFP is `rfp_preset()`. Spacecraft is an explicit argument (item 26).
7. `thrust_min_ok` / `thrust_max_ok` separated (the `T ≥ 12` collapse is fixed); pymsis mandatory; every gas state
   records the atmosphere model string.

### Trade after nested optimisation (200 km, 0.7 m², 0.98 mg/s; bus 0.10 m², arrays 5 m², σ 0.5°; P_bus ≤ 1.5 kW)
| architecture (optimum) | T mN | Isp s | P_bus W | I_neut req / max | T/D_sc | Q_waste W | MEV kg | life_sys h (limit) |
|---|---|---|---|---|---|---|---|---|
| **extended Hall + LaB₆/Xe** — 300 V, 25 cm | **28.6** | 2817 | 1016 | 2.9 / 12 | **1.75** | 387 | 48.4 | 23,200 (channel) |
| RF-ICP + Hall + LaB₆ — 150 W, 300 V, 25 cm | 28.0 | 2757 | 1160 | 2.9 / 12 | 1.72 | 517 | 55.5 | 23,600 (channel) |
| helicon + Hall + LaB₆ | 27.4 | 2697 | 1146 | 2.8 / 12 | 1.68 | 518 | 56.1 | 24,000 (channel) |
| ECR + Hall + LaB₆ — 150 W | 20.5 | 2025 | 952 | 2.2 / 12 | 1.26 | 513 | 55.5 | 28,200 (blades) |
| DC discharge + Hall | 13.9 | 1366 | 737 | — | 0.85 | 423 | 49.0 | 28,200 |
| ECR + grids — 600 W, 1000 V | 10.0 | 991 | 1307 | 0.6 / 12 | 0.62 | 989 | 79.8 | **496 (grids)** |
| PIT (any ioniser) — 1.2 kW, 500 J | 4.1–4.2 | 430–440 | 1330–1490 | — | 0.25 | 920–1070 | 77–85 | 28,200 |
| ECR magnetic nozzle — 600 W | 3.0 | 308 | 692 | — | 0.18 | 631 | 62.2 | 28,200 |
| electrothermal (MET / RF-ET / helicon-ET) | 2.1–2.2 | 215–230 | 640 | — | 0.14 | 456–476 | 35–39 | 10–15,000 |
| MPD (self / pre-ionised) — 1.2 kW | 1.1 | 117–119 | 1330–1490 | — | 0.07 | 930–1080 | 65–74 | 8,000 (electrodes) |
| Hall + air cathode (mw / RF) | 1.2 | 105–115 | 220–265 | 0.13 / 0.2 | 0.07 | — | 33 | 20,000 / 28 h |
| resistojet, arcjet | — | — | — | — | — | — | — | no point inside 1.5 kW / T > 0 |

Reading: with every architecture at its own optimum, the same PPU/thermal/BOM and the cathode current closed, the
extended Hall's lead is larger, not smaller; every pre-ioniser lands at its minimum allowed power (150 W) — the optimiser
wants it off; grids die on CEX; MPD/PIT/thermal/nozzle are an order of magnitude short at this power. **The remaining
uncertainty is not which family, but the Hall channel's own sustainment and erosion coefficients.**

Interpretation the audit asked for: *extended Hall is the strongest candidate under the most mature model; the other
families have screening-grade physics (items 13–19 of the backlog) and an order-of-magnitude gap that screening
fidelity is unlikely to close at 1.5 kW.*

Backlog retained in the audit's order: canonical `GasState/PlasmaState/BeamState/…` objects; grid CX σ(E) per species
and geometric impingement; magnetic-nozzle field/detachment model; applied-field MPD and electrode drops; PIT circuit;
electrothermal thermochemistry; ECR/RF field solvers or calibrated maps; species-resolved Hall sputter/CX;
NO/O⁻/metastable chemistry after sensitivity; DSMC transition interface; compressor validation; dynamic reservoir;
interface conservation ledgers; Sobol CIs + Shapley; SPENVIS; thermal feedback into B(T), γ(T), η_PPU(T); CG/inertia.

## v1.2 — Audit rectifications (document 15)
**P0 (all done):** resistojet/arcjet branch bug (Python `.get()` default evaluation) fixed and executed by tests — resistojet
runs (1.7 mN at 480 W), arcjet is *infeasible on its pressure envelope* (needs ≥ 500 Pa, has 0.05 Pa), recorded as such;
exceptions are never swallowed (`status = OK | INFEASIBLE | MODEL_ERROR | INCOMPATIBLE`, `strict=True` re-raises);
**every design constraint, converter rating and thermal bound is enforced inside the candidate loop** (a T_max = 25 mN
preset now returns a ≤ 25 mN optimum, not a flag); PPU `loads()` enforces `I ≤ I_max` and plasma-bridge cathodes get
their own converter; thermal infeasibility rejects candidates (analytic bound in the loop, full network on the winner);
**Hall plume CEX** uses the neutral directed velocity and species σ_CX(E) (Rapp–Francis form) — and, because charge
exchange conserves momentum, only ~25 % of CEX events cost thrust (slow-ion deflection / fast-neutral divergence):
f_CX ≈ 0.11 at Marchioni's point (recalibrated: 21.1 mN, 625 W, 1078 s); **air-fed cathodes draw from the captured
flow** (mass balance); neutralizer cache keyed on p_O; wall-atom mass from the wall material (BN 12.4 amu); MPD back-EMF
(μ₀/2π)·ln(r_a/r_c)·I·u_e replaces the zeroed placeholder; electrothermal branch consumes χ_i and T_e (recoverable
plasma enthalpy); ionizer pressure envelopes enforced at the interface; `structure_mass()` used in the BOM;
**gas path is part of each architecture's search** (intake area × reservoir pressure level); P_ion = 0 included for
assisted Hall; wider grids with an `optimum_at_search_edge` flag; pymsis **fails fast** unless
`ABEP_ALLOW_TABLE_ATMOSPHERE=1`; **`run_mission_generic()`** puts any architecture through the same 26,000 h propagator.

**Hall ignition (item 5):** `hall_fixed_points()` maps n_e → F(n_e) and finds the fixed points. In this reduced model the
map has no intermediate unstable branch: where an upper branch exists, F'(0) > 1 and the discharge ignites from any
seed (keeper plume ~3e16 m⁻³); where it does not (short channel × low flow), no seed helps — a pre-ioniser then
*sustains* the plasma itself rather than igniting the Hall branch. So sustainment ≡ ignition here, with no hysteresis,
because the model lacks the T_e(n_e) coupling that produces hysteresis in real thrusters. That coupling — and the
breadboard ignition-vs-flow curve — is the highest-value measurement left in the Hall decision; the conclusion "the
optimiser wants the pre-ioniser off" is conditional on it.

### v1.2 trade (research preset, P_bus ≤ 1.5 kW; bus 0.1 m², arrays 5 m², σ 0.5°; every constraint inside the search)
| architecture (optimum) | area / p | V_d / L | T mN | Isp s | P_bus W | T/D_sc | MEV kg | life (limit) |
|---|---|---|---|---|---|---|---|---|
| **extended Hall + LaB₆/Xe** | 0.85 m² / low | 275 V / 30 cm | **44.3** | 3629 | 1455 | **2.34** | 54.8 | 28 kh (blades) |
| any pre-ioniser + Hall + LaB₆ | same, **P_ion = 0** | same | 44.3 | 3629 | 1455 | 2.34 | 56–59 | 28 kh |
| ECR + grids | 0.6 / low, 500 W, 1000 V | — | 11.5 | 1315 | 1270 | 0.79 | 59.7 | **530 h (grids)** |
| Hall + microwave air cathode | 0.6, 350 W, 350 V, 30 cm | — | 8.8–9.4 | 1070–1135 | 880–1130 | 0.6 | 50–57 | **23 h (cathode)** |
| ECR magnetic nozzle | 0.6 / nominal, 500 W | — | 7.8 | 948 | 580 | 0.54 | 38.2 | 28 kh |
| PIT / MPD / thermal | — | — | 1–4 | 100–440 | 500–1500 | < 0.3 | 29–85 | — |

With P_ion = 0 admitted, **every assisted-Hall architecture collapses onto the plain extended Hall** — the derivative of
the objective with respect to pre-ioniser power is negative all the way to zero. Grids die on CEX (530 h), air cathodes
on current (0.9–1.1 A available vs 4.8 A needed) and cavity sputtering.

### RFP preset — the only binding constraint is mass
With `rfp_preset()` (12–25 mN, ≤ 1.5 kW, ≤ 40 kg MEV, ≥ 15,000 h) **no architecture has a feasible point**
(Hall: thrust_min 222 / mass 96 / thrust_max 87 / power 27 rejections). Relaxing *only* mass:

| mass cap | optimum | T | P_bus | MEV | life | T/D_sc |
|---|---|---|---|---|---|---|
| none | 0.6 m² / low / 350 V / 30 cm | 25.0 mN | 1033 W | 48.7 kg | 28 kh | 1.71 |
| **45 kg** | **0.5 m² / low / 300 V / 35 cm** | **18.8 mN** | **744 W** | **44.3 kg** | 28 kh | **1.46** |
| 40 kg | — | infeasible | | | | |

The 45 kg design holds 200 km for all 26,000 h in `run_mission_generic` (5 m² arrays; 664 W mean; α_end 0.85).
**The gap to the RFP is 4–5 kg of MEV, and nothing else.** It is made of the compressor's and intake's 30 % new-design
allowances (≈ 2.5 kg), redundant PPU (≈ 1.5 kg), and Xe (≈ 1 kg at a 500 h reserve).

Backlog (document 15, P1/P2 not yet done): T_e(n_e) coupling and 1-D transient ignition model; continuum-vs-rarefied
nozzle selection; frozen versioned atmosphere dataset; magnetic-nozzle field/mass sizing; species-resolved grid
optics; air-cathode chemistry/oxidation; nested search with adaptive/continuous optimisation; correlated mission UQ
on the modular architectures (the generic mission function is in place; the UQ wrapper is next).

## v1.3 — Physics-baseline stabilisation (document 16, first tranche)
**Reproducibility.** Frozen, versioned, species-resolved TPMC intake surface shipped in `abep_sim/data/`
(720 points: O/N₂/O₂ × Maxwell/CLL × L/d × φ × α × θ; SHA-256 prefix and build metadata in the JSON; max unresolved
fraction 8×10⁻⁴). `evaluate()` never generates it (`python -m abep_sim.intake_tpmc build` does). Full test suite runs in
~20 s. NRLMSIS failures of any kind now abort (no silent fallback); outputs record epoch and n_O.

**Intake physics.** Particles still in the channel are never counted as collected (tracing continues until < 10⁻³ remain;
L/d 20, α 1: η_c 0.35 → 0.26). CLL kernel implemented (Lord sampling). At nominal α = 0.8, CLL gives η_c 0.85 vs
Maxwell 0.64 — the coupon test must measure α_n and α_t separately; Maxwell is the conservative default.

**Hall physics.** `hall_run_coupled()` is a single consistent (n_e, T_e) solution: quasi-steady electron energy balance
(Joule heating by back-streaming + cathode-seed electrons vs ionisation/excitation, SEE-limited Hobbs–Wesson sheath
losses, anode convection), density fixed points refined by bisection, **deterministic hot-branch T_e selection**,
acceleration-zone length set by the B-field gradient (3.3 cm), beam current by species from the ionisation rates at the
selected root, electron back-current from the same closure. Calibrated to the one air anchor (Marchioni N₂, 2 mg/s,
250 V): α_anom = 0.88, L_iz = 0.4 → 21.6 mN / 867 W / 1101 s / T_e 30 eV. **Mode structure** now appears: hysteresis at
1.3–1.4× design flow (cold start low branch 13 mN, running thruster 30 mN) and a collapse to the low mode above.
Design points use the cold-start branch (conservative); mission maps use continuation (hot branch).
Two earlier model errors are withdrawn: a second density closure inside the old `run()` (10× inconsistency, jittery maps)
and an acceleration zone scaling with channel length (made longer channels look worse).

**Engine.** Strict energy ledger (every watt once, residual enforced < 2 %, achieved ≈ 0); species-resolved jet power per
family; calibration-envelope flags with graded extrapolation limits; architecture-neutral absolute reservoir pressure;
Xe from firing hours; AO fluence from n_O·V_rel; heat-strap sizing with mass; runner-up fallback on thermal failure;
BOM rebuilt after the full thermal solve; **arrays sized inside the search** from the orbit's worst eclipse season and
solar-maximum power, with their drag and mass charged; **mission envelope inside the search** (each candidate re-run at
solar-min/mean/max flow, must close at all three with margin); mission loop hard-capped at the bus power limit.

### What v1.3 says (consistent physics, 200 km, 0.1 m² bus, arrays sized, full solar cycle, 10 % margin)
| bus power cap | best min(T/D) over the cycle | status |
|---|---|---|
| 1.5 kW | 0.71 | not closed (180 km 0.56; 0.05 m² bus 0.74) |
| 2.0 kW | 0.82 | not closed |
| 2.5 kW | 1.09 | marginal — 46 mN, 2.39 kW, 71 kg, 1.3 m² intake |
| 3.0 kW | closes | |
At ABEP flows a 0.3 A pre-ionised seed roughly doubles thrust near the sustainment knee (20 cm, 0.8–1.0 mg/s:
2.9→9.7, 6.8→14.0 mN), but the reduced ECR model delivers ~0.1 A transported for 50–350 W, so the optimiser
still prefers large intakes above the knee with the source off. The earlier "closes at 700–850 W" results were
artefacts of the fixed-T_e model. The decision rests on three measurements: air-Hall thrust/current vs flow
(0.5–1.5 mg/s, 15–25 cm), transported ECR ion current per watt, and intake α_n/α_t after AO exposure.

## v1.3.1 — Conservation fix and modular UQ
**Mass-conservation bug (item 12), found by the UQ:** ions reaching the walls of the ECR/RF/helicon chamber and of the
interstage were deleted instead of recombining into neutrals. That penalised every plasma-fed architecture. Wall-lost
ions now return to the neutral pool (O⁺→O, N₂⁺→N₂, …) in the global model and in the interstage; the global model's
mass balance closes to < 1 % (test added). The same fix raised the air cathode's *predicted* current (3.4 A at 470 W);
per item 29 the ranking now uses the **validated ceiling** (microwave air cathode 1.0 A, AMPCAT-class; RF air cathode
0.5 A, no data) and reports the prediction separately (`I_max_predicted_A`, `life_validated_h`).

**`uq_modular.py`** — correlated-free triangular sampling of the parameters that decide closure (α_anom, ionisation-zone
fraction, ionisation-rate and collisional-loss scales, intake accommodation, ECR effective-power scale; bus frontal
area and pointing as aleatory), re-running the same propulsion physics at mean / solar-min / solar-max flow (cold start at
design, continuation off-design, power cap at solar max). Metric: r = min(T/D over the three).

| design (200 km, 0.1 m² bus, arrays sized) | P(r ≥ 1) | P(r ≥ 1.1) | r q10 / q50 / q90 | binding case |
|---|---|---|---|---|
| extended Hall, best at 1.5 kW (1.3 m², 300 V, 25 cm) | 0.00 | 0.00 | 0.38 / 0.65 / 0.70 | solar-max 61 % |
| extended Hall, best at 2.5 kW (1.3 m², 325 V, 20 cm) | 0.62 | 0.13 | 0.85 / 1.04 / 1.10 | solar-min 62 % |
| ECR + Hall, 100 W source, same design | **0.76** | 0.01 | **0.95** / 1.04 / 1.07 | solar-max 71 % |
| ECR + Hall, 200 W source | 0.59 | 0.00 | 0.96 / 1.01 / 1.04 | solar-max 84 % |

Leading sensitivities (Spearman on r): at 1.5 kW ionisation-zone fraction −0.63, α_anom +0.55, collisional loss −0.30;
at 2.5 kW ionisation-rate scale +0.74, intake accommodation −0.32, pointing −0.22. A small ECR stage buys robustness at
solar minimum (q10 0.85 → 0.95) and pays for it in solar-maximum power headroom under a fixed cap.

## v1.4 — Pareto output, Sobol with confidence intervals, compressor leakage, start-up reservoir
- **Compressor leakage solved self-consistently** (`DragCompressor.run(self_consistent=True)`): recirculated flow raises
  the machine's throughput until the leak and the pumping characteristic agree. With the turbomolecular stage pumping
  ~38 m³/s, a realistic clearance leak recirculates ~0.1 % — negligible here, now shown rather than assumed.
- **Dynamic reservoir start-up** (`reservoir.startup_transient`): species inventory ODE with rotor spin-up and wall
  recombination. Time constant ~1 ms, so reservoir pressure tracks the compressor (ignition pressure at 49 s of a 60 s
  spin-up). It sets ignition sequencing; it does not affect the 26,000 h mission.
- **Pareto-first output.** Every candidate is recorded with its worst-case T/D over the solar cycle (`env_ratio`),
  including rejected ones; `pareto_front()` ranks closing designs in (env_ratio, bus power, system mass incl. arrays,
  life, Xe); `dedupe_designs()` merges candidates that differ only in non-influential variables. Array area is now sized
  to each run's own power cap (a defect sized 2–3 kW designs with 1.5 kW arrays; fixed).

### Pareto front of closing designs (200 km, 0.1 m² bus, arrays sized, full cycle, worst-case T/D ≥ 1)
| architecture | intake | ECR W | V_d / L | T mN | worst T/D | P_bus kW | propulsion MEV kg | arrays m² | system kg |
|---|---|---|---|---|---|---|---|---|---|
| extended Hall | 1.3 m² | — | 325 / 25 cm | 43.7 | 1.06 | 2.25 | 70.8 | 12.2 | **109.8** |
| extended Hall | 1.3 m² | — | 325 / 20 cm | 46.4 | 1.06 | 2.39 | 71.1 | 12.2 | 110.1 |
| ECR + Hall | 1.3 m² | 50 | 325 / 25 cm | 44.4 | 1.09 | 2.36 | 79.0 | 12.2 | 118.0 |
| ECR + Hall | 1.3 m² | 100 | 325 / 25 cm | 45.0 | **1.12** | 2.46 | 80.6 | 12.2 | 119.6 |
| extended Hall | 1.6 m² | — | 300 / 20 cm | 56.9 | 1.18 | 2.77 | 77.1 | 14.5 | 123.6 |
| ECR + Hall | 1.6 m² | 100 | 300 / 20 cm | 58.4 | 1.22 | 2.99 | 87.0 | 14.5 | 133.5 |
Best worst-case T/D by power cap: 1.5 kW 0.71 (no design closes); 2.5 kW Hall 1.06 / ECR+Hall 1.12; 3.0 kW 1.21 / 1.22.
**At ≤ 2.5 kW only ECR+Hall reaches a 10 % margin (+8 kg). Every closing design is ~110–135 kg of propulsion + arrays.**

### Sobol indices on worst-case T/D (2.5 kW extended Hall, n = 128, 1152 evaluations, bootstrap 90 % CI)
| input | kind | S₁ [CI] | S_T [CI] |
|---|---|---|---|
| anomalous transport α | epistemic | 0.45 [0.28, 0.57] | 0.37 [0.27, 0.49] |
| ionisation-rate scale | epistemic | 0.40 [0.28, 0.52] | 0.36 [0.27, 0.51] |
| collisional-loss scale | epistemic | 0.16 [−0.04, 0.37] | 0.23 [0.14, 0.34] |
| ionisation-zone fraction | epistemic | 0.16 [−0.06, 0.36] | 0.21 [0.14, 0.31] |
| intake accommodation | epistemic | 0.06 [−0.10, 0.20] | 0.11 [0.08, 0.15] |
| pointing | aleatory | — | 0.014 [0.010, 0.019] |
| bus frontal area | aleatory | — | 0.006 [0.004, 0.008] |
~95 % of the variance is epistemic and ~75 % of it is Hall discharge physics (transport + ionisation), i.e. reducible by
the air-Hall breadboard curve. The spacecraft unknowns (bus area, pointing) are < 2 %.

## v1.5 — Equal-footing physics for gridded ion and magnetic nozzle
- **`grid_optics()`** — species-resolved two-grid optics: extracted current from the source plasma state, Child–Langmuir
  limit with the mixture effective mass and effective length √(g² + r_s²), normalised perveance → beamlet divergence and
  crossover/edge impingement, electron-backstreaming floor on the accel voltage, charge exchange from the actual neutral
  flux through the grids with σ_CX(E) per species, accel-grid Mo sputtering scaled per ion species by energy-transfer
  factor, life = time to erode half the web mass. Search variables: V_b, grid open area, gap (and source power).
- **`magnetic_nozzle()`** — plume energy from the source's power partition (Bohm energy + polytropic ambipolar
  expansion to detachment at n₀/R_m), detachment efficiency and divergence vs mirror ratio, SmCo magnet sized from the
  stored field energy in the throat region. **Energy-bound variant** (`NOZZLE_ENERGY_BOUND`): every watt not spent on
  ionisation/excitation/dissociation becomes directed ion energy — the most favourable any electron model could give.
  Search variables: source power, throat field, mirror ratio, throat area; the source chamber scales with the exit area.
- **Source guard:** a global-model state with T_e pinned at a bound, utilisation > 1 or a mass residual > 2 % is rejected
  (no sustained plasma). This removed an artefact in which the ECR nozzle appeared to close at 1.5 kW.
- **Energy ledger** for accelerators without their own supply (nozzle, plasma-fed electrothermal): jet power is drawn
  from the source power, counted once.
- **Off-design retuning:** at solar-min/max the controller may retune source power (0.5–1.25×) within the bus cap —
  the same freedom for every plasma-fed architecture.

### Cross-family result (200 km, P_bus ≤ 2.5 kW, 0.1 m² bus, arrays sized, full solar cycle; worst-case T/D)
| architecture | best worst-case T/D | limited by |
|---|---|---|
| **ECR + Hall** | **1.15** (1.3 m², 100 W, 325 V, 25 cm: 45 mN, 2.45 kW, 80 kg + 12.2 m² arrays = 119 kg) | solar-max power |
| extended Hall | 1.06 (1.3 m², 325 V, 25 cm: 44 mN, 2.25 kW, 110 kg system) | solar-min flow |
| ECR + grids | 0.99 | accel-grid life: hours to ~6,000 h (CEX with unionised air; crossover at low perveance) |
| DC + grids | 0.96 | grid life, power |
| helicon + grids | 0.81 | source utilisation |
| helicon + nozzle (energy bound) | 0.62 | energy per particle at ABEP flow |
| RF + grids | 0.45 | RF coupling at 0.05 Pa |
| ECR + nozzle | 0.17 Maxwellian / 0.23 energy bound | energy per particle |

Only the Hall family closes at 2.5 kW; ECR+Hall adds ~9 % worst-case margin for ~9 kg and is the only variant that
closes with a 1.0 m² intake (350 W source). Grids are a life-limited near-miss; nozzles are excluded even at the
energy bound because ABEP flow leaves only ~20–60 eV of power per molecule.

## v1.6-candidate — Stabilisation cycle (document 17 gates). NOT a frozen physics baseline.
| gate | status |
|---|---|
| 1 clean-install reproducibility | **pass** — frozen hashed NRLMSIS 2.1 dataset is the default atmosphere (live pymsis optional); pinned `requirements-lock.txt`; `scripts/install_and_test.sh`; suite passes with pymsis present and blocked; two call-order-dependent caches made pure functions of their keys |
| 2 grid-life inconsistency | **pass** — optimiser degeneracy (near-tied designs), not a regression; near-ties flagged; tests now check the perveance window at fixed designs |
| 3 multi-point Hall validation | **FAIL (structural)** — blind prediction of the P5 5-kW HET on N₂ (Brabston et al., JPP 2025, doi:10.2514/1.B39623, Table 2 N1–N5): model does not ignite; no parameter set reproduces both discharge current and thrust; required T_e 60–110 eV. Recorded as a strict xfail test. P5 radii in `validation.py` are from memory and must be verified |
| 4 cross-family mission UQ | **done (conditional on gate 3)** — see table below |
| 5 numerical convergence | **pass** — source mass/power exact; Hall 1×–8× identical; TPMC ≤1.25 %; mission Δt 3×10⁻⁵; search grid 0.9 % |
| 6 golden benchmarks | **pass** — `abep_sim/data/golden_v1.json`, 31 stage-by-stage entries, reproduced to 1e-6 inside the suite |

Defects found and fixed this cycle: source solver non-convergence above ~300 W (now T_e-parameterised with threshold
bracketing, exact balances 20 W–1.4 kW); ion density split by production instead of production/u_B; Hall T_e root pairs
under-resolved near a fold (**v1.3 hysteresis / low-mode collapse withdrawn**); neutral balance solved exactly in one pass
(8× faster, identical results); cache call-order dependence.

### Gate-4 result (200 km, ≤ 2.5 kW, life ≥ 15,000 h, n = 150 paired samples; success = worst-case T/D ≥ 1 ∧ life ≥ 15 kh)
| architecture | P(success) | P(T/D ≥ 1.1) | r q10/50/90 | paired vs extended Hall |
|---|---|---|---|---|
| ECR + Hall (100 W) | 0.77 | 0.02 | 0.96/1.03/1.08 | 26 wins / 4 losses, McNemar p = 6e-5 |
| helicon + Hall | 0.64 | 0.02 | 0.88/1.02/1.08 | n.s. (p = 0.75) |
| extended Hall | 0.63 | 0.20 | 0.82/1.05/1.11 | — |
| RF + Hall | 0.61 | 0.01 | 0.85/1.02/1.07 | n.s. (p = 0.75) |
| ECR + grids | 0.00 | 0.00 | 0.65/0.81/0.90 | grid life q10 ≈ 90 h (perveance window) |

**Interpretation.** Family-level conclusions rest on mechanisms independent of the Hall closure (grid CEX/perveance life;
nozzle energy per particle; RF/helicon pre-ionisers add nothing) and are probably robust. All absolute Hall numbers at ABEP
flows — thrust, 2.5 kW closure, 110–120 kg, the ECR+Hall probability advantage — come from a model that fails its only
independent test. Next: quasi-1-D Hall model fitted to Marchioni and P5 together.

## v1.7-candidate — HallThruster.jl adopted as the Hall-discharge solver (decision, document 18)
**Architecture.** HallThruster.jl (UM PEPL, MIT) is the authoritative Hall-discharge solver, run **offline** to produce
frozen, versioned response maps; Python remains authoritative for everything else. Not a Julia migration.
- **Pinned:** v0.23.1, commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5` (recovered from the release tarball). Molecular
  support confirmed in the source of this tagged release: `propellant_config` TOML, electron-impact dissociation /
  ionization / dissociative ionization. Defaults: `TwoZoneBohm(1/160, 1/16)`, `WallSheath(BNSiO2, 1.0)`.
- **`hallthruster_bridge/`**: `PINNED.toml`, `Project.toml` (compat `=0.23.1`), `run_cases.jl` (driver, **untested here —
  Julia binaries are not reachable from the development sandbox**), `propellants/n2_n.toml` (Stage A N₂/N), validation case
  files `cases/p5_xenon.json` (Brabston Table 4), `cases/p5_n2.json` (Table 2), `cases/echt_n2.json` (true ECHT geometry;
  B_max and per-point data still to be obtained). B(z) is a documented Gaussian placeholder until measured profiles exist.
- **`abep_sim/hall_map.py`**: loader that refuses maps from another commit or missing any required output (thrust, I_d, I_i,
  P_d, anode/mass/divergence efficiency, T_e and n_e peaks, wall ion flux and energy, atomic-ion fraction, oscillation
  metric, sustainment, convergence), flags queries touching unconverged nodes, and never extrapolates.
- **`abep_sim/rate_tables.py`**: Maxwellian integration of cross sections into HallThruster.jl's table format (mean energy
  3/2 T_e), verified against the closed-form step-cross-section rate to < 1 %.
- **`hall1d.py`** kept only as an independent reduced-order sanity model.

**Chemistry finding.** The N₂ ionisation Arrhenius fit used throughout the simulator was **2.2–3.2× low** versus the
Itikawa-2006-derived table shipped with HallThruster.jl, over T_e = 3–200 eV. The cited table is now authoritative
(`abep_sim/data/rates/`, provenance file). Every other rate (O, O₂, N ionisation; dissociation; dissociative ionisation;
excitation) remains an unverified fit until cross sections are integrated. With correct chemistry *and* the true ECHT
geometry, the superseded 0-D model moves from "P5 does not ignite" (×100 miss) to within ~2× on both thrusters — the P5
failure was largely chemistry.

**Superseded.** All absolute Hall numbers from the 0-D closure (v1.2–v1.6: thrust at ABEP flows, 2.5 kW closure,
110–120 kg, ECR+Hall P(success) 0.77 vs 0.63) were produced with a 3×-low N₂ rate and a calibration on an invented
geometry. They are withdrawn pending HallThruster.jl maps. Five calibration tests are retired (skipped, reason recorded);
the strict P5 expected-failure stays.

**Remaining to run the Hall validation ladder:** Julia access (allow julialang-s3.julialang.org, pkg.julialang.org,
storage.julialang.org, or run offline); N ionisation, N₂ dissociation, N₂ excitation and N elastic cross sections (LXCat
sets — lxcat.net is also not reachable from the sandbox); measured B(z) for P5 and ECHT; ECHT per-point data and B_max.
