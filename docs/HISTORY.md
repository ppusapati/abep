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

## HallThruster.jl driver runs — P5 xenon, untuned (next-work step 1, 2026-09-25)
Julia 1.11.7; `setup.jl` installs HallThruster.jl 0.23.1 at the pinned commit `bfb3019` (Manifest `repo-rev` checked by
the driver, which now refuses any other rev/version). `Project.toml` committed with `[compat] HallThruster = "=0.23.1"`
(it was described above but had never been added).

**Driver fixes vs the real v0.23.1 API** (`src/simulation/{solution,postprocess}.jl`): `Solution.grid` is a plain
`Vector{Float64}` (no `.cell_centers`); `Frame` is a struct, not a dict, with `potential` (not `ϕ`), and ion velocity /
neutral density live in `frame.ions[:Xe][Z].u` / `frame.neutrals[:Xe].n`. The old profile and efficiency blocks were
wrapped in `try … catch end` and so silently dropped every profile. Those were removed (rule 3). Failed runs now come back
as `converged=false` with the solver's error, with no averaged numbers. Outputs added: I_i, P_d, voltage/current efficiency,
T_e/n_e peaks, RMS oscillation, measured-vs-simulated I_d error. Config/Geometry1D/Thruster/Propellant/SimParams calls
were already correct.

**Results** (`cases/p5_xenon.json` as committed, all defaults: TwoZoneBohm(1/160, 1/16), WallSheath(BNSiO2, 1.0),
Gaussian placeholder B(z), 5 mg/s, 200 cells, 2 ms, averaged over 1–2 ms). All `retcode=success`, quiescent (I_d p-p < 3 %).

| case | V_d | I_d meas | I_d sim | error | P_d sim | T sim | η_anode | η_current |
|---|---|---|---|---|---|---|---|---|
| Xe1 | 230.8 | 7.582 | 6.592 | −13.1 % | 1521 W | 81.6 mN | 0.437 | 0.548 |
| Xe2 | 250.3 | 8.590 | 6.836 | −20.4 % | 1711 W | 85.2 mN | 0.424 | 0.529 |
| Xe3 | 274.3 | 7.401 | 7.100 | −4.1 % | 1947 W | 89.6 mN | 0.412 | 0.510 |

Grid 400 cells and duration 4 ms change I_d by < 0.2 %, so resolution does not explain the errors. The simulated I_d rises
monotonically with V_d (I_i ≈ 3.6 A, near full utilisation of 5 mg/s). The case-file "measured" I_d (= P_d/V_d) is
non-monotonic (8.59 A at 250 V, 7.40 A at 274 V). *Corrected 2026-09-25 (see next entry):* anode flow, cathode flow and peak
magnetic field are documented as constant; facility background pressure varies substantially between Xe1–Xe3 and must be
included or corrected before using Table 4 discharge current as a clean-vacuum validation target.
Thrust is simulated 81.6–89.6 mN against the paper's 72.8–86.8 mN range. The per-point thrust mapping is not in the case
file. Nothing has been tuned. Gate 3 is still FAIL.

## P5 xenon rerun with measured B(z) and facility ingestion; harness fixes (2026-09-25)
**Harness (no model change, no frozen data regenerated).**
- `golden.py`: per-key absolute tolerance `ATOL = {"ledger_resid": 1e-12}`. The stored `ledger_resid` is 0.0, so the
  relative check turned 1.8e-16 of round-off into an infinite change (gate 6 failed on a clean checkout). Every other key
  keeps the 1e-6 relative check, because the set holds legitimately tiny values such as densities.
  `golden_v1.json` is unchanged; `golden check` → OK. There's a regression test for the comparator.
- `hallthruster_bridge/Manifest.toml` is now committed (removed from `.gitignore`), so the exact Julia dependency graph is
  in the repo and the driver's pinned-rev check works on a fresh clone.
- `run_cases.jl`: propellant-config and rate-directory paths now resolve from `@__DIR__`, not the launch directory. Any case
  whose propellant TOML names a missing `rate_coeff_file` is refused before running. **P5-N₂ and ECHT-N₂ are therefore
  blocked**: `dissociation_N2.dat`, `excitation_N2.dat`, `elastic_N.dat` and `ionization_N.dat` don't exist yet.

**Table 4 (Brabston et al. JPP 2025, doi:10.2514/1.B39623, checked against the paper).** For Xe1–Xe3, anode Xe 5 mg/s,
cathode Xe 0.44 mg/s and peak radial B 162.5 G (channel centre, exit plane) are constant. The coils were optimised at Xe3
for minimum I_d and I_d oscillation, then held fixed. Chamber pressure varies: 4.49, 3.94, 3.28 ×10⁻⁵ Torr (Xe). With the
paper's Eq. (13) (A_en = 488 cm², T₀ = 300 K) the entrained flow is 0.846 / 0.742 / 0.618 mg/s, i.e. 12–17 % of the
anode flow. Eq. (14) with ζ_A = 1.0 gives vacuum-corrected I_d = 6.961 / 8.044 / 6.947 A (raw P_d/V_d: 7.582 / 8.590 /
7.401 A). **The corrected I_d is still non-monotonic in V_d, so background pressure doesn't explain the Xe2 point.**

**Ingestion in HallThruster.jl v0.23.1.** The ingested density is computed as m·P/(k_B·T) with P taken straight from
`background_pressure_Torr`, with no Torr→Pa conversion (`src/utilities/utility_functions.jl`). It also uses the channel
area (116 cm²), not an entrainment hemisphere. Verified numerically: the built-in flow is 0.00151 mg/s vs 0.201 mg/s from
Eq. (13) with the channel area (×133.3). The driver passes P in Torr (correct for pressure-dependent anomalous models) and
sets `neutral_ingestion_multiplier = 133.322·A_en/A_ch`. It asserts at run time that the resulting flow equals Eq. (13).
The ingested flow enters at the anode boundary in the 1-D model; Eq. (13) is a plume-entrainment estimate.

**Measured B(z).** Brabston gives no profile. Source: Peterson, Gallimore & Haas, AIAA 2001-3890 (P5 vacuum radial field,
NIST-traceable Hall probe + B-dot, 300 V). Figs. 11 (1.6 kW coils, I_in = 2 A, I_out = 1 A) and 12 (3.0 kW coils, 3 A / 2 A)
are vector plots, so the centreline traces are read from the PDF drawing commands (`scripts/digitize_p5_bfield.py` →
`hallthruster_bridge/bfield/*.csv`). Axis check: the drawn pole mid-plane and exit-plane lines read 25.41 mm and 37.99 mm.
The measured topology differs strongly from the placeholder: the peak is ~10 mm **upstream** of the exit (near the pole
mid-plane), B(exit)/B(max) ≈ 0.88, B is ~50 % of the exit value only ~20 mm from the anode, and there's a long plume tail.
The case file uses the 1.6 kW setting (closest power; Brabston's coil currents aren't published), aligns the exit planes,
and scales B(exit, centreline) to 162.5 G, which gives a 186 G maximum. **VERIFY:** Peterson's exit plane is 38.0 mm from
the anode face, but the channel length here (Brabston) is 32 mm, so the anode position in the field map is uncertain by 6 mm.
HallThruster.jl holds B constant beyond the last measured point (88 mm in model coordinates; the domain is 100 mm).

**Results** (default TwoZoneBohm(1/160, 1/16), WallSheath(BNSiO2, 1.0), 200 cells, 2 ms, averaged 1–2 ms; errors vs raw
P_d/V_d when ingestion is modelled, vs Eq. (14)-corrected I_d when in vacuum; RMS is I_d RMS / mean):

| B(z) | ingestion | Xe1 | Xe2 | Xe3 | I_d RMS |
|---|---|---|---|---|---|
| Gaussian placeholder | off (vs corrected) | −5.3 % | −15.0 % | +2.2 % | < 1 % |
| Gaussian placeholder | on (vs raw) | +5.4 % | −6.0 % | +10.3 % | < 1 % |
| measured 1.6 kW, B(exit) = 162.5 G | off | −83.3 % | −70.2 % | −55.8 % | 73–123 % |
| measured 1.6 kW, B(exit) = 162.5 G | **on (canonical case file)** | −56.2 % | −56.1 % | −47.0 % | 108–119 % |
| measured 1.6 kW, B(max) = 162.5 G | off | −55.4 % | −59.5 % | −42.1 % | 80–121 % |
| measured 3.0 kW, B(exit) = 162.5 G | off | −65.4 % | −60.4 % | −49.3 % | 102–131 % |

With the measured field and default transport, every run returns `retcode=success` but is in a deep relaxation
oscillation. I_d swings between ~0.1–0.7 A and 11–17 A, and current utilisation is ≈ 1 (almost no electron current
between bursts). It persists at 400 cells (RMS 65–79 %) and at 4 ms (RMS 106–115 %). The time-averaged I_d moves by up
to 21 % between those runs, so **those averages aren't operating points and aren't validation comparisons**. The driver
now reports `Id_min_A`, `Id_max_A` and `quasi_steady` (I_d RMS < 50 %; observed runs sit at < 1 % or > 65 %). The real
thruster ran quietly (coils tuned for minimum oscillation).

**Interpretation.** The earlier −13 / −20 / −4 % agreement came from the placeholder, which puts almost no field in the
upstream channel (B at the anode ≈ 0). With the measured topology, strong inner-channel B throughout the default inner
Bohm coefficient's zone suppresses cross-field electron transport, and the default coefficients drive the discharge into
breathing. So the P5-Xe comparison with the default anomalous-transport coefficients isn't meaningful: the measured
topology plus default TwoZoneBohm doesn't reproduce the quiet operating point. Plan step 8 (decide whether transport
needs adjusting) is now reached; nothing has been tuned. Ingestion alone adds 1.1–1.4 A to the simulated quasi-steady I_d
(Gaussian runs), about 2× the Eq. (14) correction of 0.45–0.62 A, because each ingested ion also brings electron current
at ≈ 50 % current utilisation. Gate 3 is still FAIL.

## P5 geometry / B(z) registration sensitivity, transport fixed (2026-09-25)
**Decision (project lead):** don't tune anomalous transport until the P5 geometry and B(z) registration are settled; don't
let transport absorb geometry or topology error. The earlier Gaussian-field agreement is **superseded as validation
evidence**.

**Geometry evidence.** Channel depth: 38 mm in Peterson, Gallimore & Haas (AIAA 2001-3890, "channel depth of 38 mm"; the
field-map exit plane is drawn at 37.99 mm from the anode face) and in Hofer (PhD 2004, Sec. 5.3.1: OD 173 mm, width 25 mm,
depth 38 mm; anode at z = −38 mm). Brabston 2025 (the validation data) says "32 mm discharge channel length". The 2026
HPEPL paper on the same Georgia Tech P5 (J. Electr. Propuls., doi:10.1007/s44205-026-00179-9, CC BY) gives OD 173 mm and
width 25 mm, no depth. It states that the field was measured "near the exit plane where the peak of magnetic field is
observed". OD and width agree across all sources; only the depth is disputed. **Unresolved. Question for HPEPL
(Brabston/Walker):** (1) was the 2025 channel 32 mm deep anode-to-exit, and was it a replacement or shortened ceramic;
(2) did the anode or the magnetic circuit move relative to the historical P5; (3) coil currents for Xe1–Xe3 and any
measured B(z); (4) discharge-current traces (RMS, peak-to-peak, spectrum) for Xe1–Xe3.

**Registration cases** (`scripts/make_p5_xenon_cases.py` → `cases/p5_xenon.json` and `cases/p5_xenon_coil_sensitivity.json`).
The field is rigid-shifted only, never stretched:
- `L38-hist`: 38 mm channel, field in original coordinates;
- `L32-anode`: 32 mm channel, same anode and magnetic circuit, so the ceramic ends 6 mm earlier;
- `L32-exit`: 32 mm channel with exit planes aligned, i.e. the anode moved 6 mm downstream.

In all three, B at the model exit plane (centreline) = 162.5 G. Transport is fixed at the defaults (TwoZoneBohm(1/160, 1/16),
transition 0.1 L) and facility ingestion is on (Eq. 13). Errors are vs the Eq. (14)-corrected I_d (6.96 / 8.04 / 6.95 A).
Oscillation is reported directly: I_d RMS/mean, peak-to-peak/mean and dominant frequency (DFT of the 1 ms averaging window,
1 kHz resolution). The `quasi_steady` flag (RMS < 50 %) is an internal diagnostic only.

| coil shape | registration | B peak − exit | B_max | I_d error Xe1 / Xe2 / Xe3 | I_d RMS | f_dom |
|---|---|---|---|---|---|---|
| 1.6 kW | L38-hist | −9.8 mm | 186 G | −51 / −51 / −36 % | 96–241 % | 6–11 kHz |
| 1.6 kW | L32-anode | −3.8 mm | 167 G | −31 / −35 / −25 % | 34–185 % | 7–10 kHz |
| 1.6 kW | L32-exit | −9.8 mm | 186 G | −52 / −52 / −43 % | 106–120 % | 7–8 kHz |
| 3.0 kW | L38-hist | −7.6 mm | 178 G | −56 / −53 / −45 % | 310–349 % | 4–9 kHz |
| 3.0 kW | L32-anode | −1.6 mm | 164 G | −41 / −44 / −33 % | 272–317 % | 5–16 kHz |
| 3.0 kW | L32-exit | −7.6 mm | 178 G | −44 / −51 / −38 % | 91–113 % | 7–8 kHz |

**Findings.**
1. Registration matters at fixed transport. L32-anode vs L32-exit shifts the mean I_d by 1.2–1.4 A (~30 %) and moves the
   field peak relative to the exit by 6 mm. Coil shape (1.6 vs 3.0 kW setting) changes oscillation amplitude by up to 3×.
2. No registration and no coil shape gives a quiet discharge with default transport. Every case underpredicts corrected
   I_d by 25–56 % and breathes at 4–16 kHz. The means are averages over limit cycles, so they aren't validation numbers.
3. Circumstantial support for L32-anode: it's the only registration where B at the exit is close to the peak (167 vs
   162.5 G, peak 3.8 mm upstream), matching Brabston's "peak radial B … at the exit plane" and the 2026 paper's "peak …
   near the exit plane". L38-hist and L32-exit put the peak 9.8 mm upstream with B(exit) = 0.88 B_max. Not conclusive:
   Brabston's coil currents (which set the shape) are unknown.
4. Brabston publishes no I_d oscillation data. The only oscillation constraint is qualitative: the coils were set for
   minimum peak-to-peak.

**Upstream.** HallThruster.jl uses `background_pressure_Torr` as Pa for ingestion (and the docstring says Pa) but as Torr
in the pressure-shift anomalous model. The same code is on upstream `main`. Minimal reproducer and draft issue:
`hallthruster_bridge/upstream/` (not filed yet).

**Status.** Gate 3 still FAIL. Transport calibration waits for the geometry answer. When it comes, identify ONE TwoZoneBohm
set (c₁, c₂, transition length) across Xe points, fit against I_d, thrust, anode and current efficiency and the qualitative
oscillation constraint, and hold one Xe point out blind. Freeze it before N₂.

## Validation-record correction: matched comparison modes; hall_map_schema_v1 (2026-09-25)
**Correction.** The registration table in the previous entry ran with facility ingestion ON but scored the errors against
the Eq. (14) *vacuum-corrected* I_d. That crossed the modes. The rule now enforced by the driver: facility ingestion ON
(anode + Eq. 13 flow) is compared with **raw P_d/V_d**; ingestion OFF is compared with the **Eq. (14)-corrected** I_d.
Every case runs in both modes and the driver prints them side by side. The table below replaces the previous one as the
canonical record. Transport is still the default TwoZoneBohm(1/160, 1/16) with a 0.1 L transition.

| coil | registration | I_d error facility (vs raw) Xe1/2/3 | I_d error vacuum (vs corrected) Xe1/2/3 | RMS fac / vac | f_dom |
|---|---|---|---|---|---|
| 1.6 kW | L38-hist | −55.1 / −53.9 / −40.2 % | −49.2 / −53.4 / −44.2 % | 96–241 / 50–107 % | 6–11 kHz |
| 1.6 kW | L32-anode | −37.0 / −39.1 / −29.2 % | −38.1 / −44.9 / −33.6 % | 34–185 / 27–40 % | 6–10 kHz |
| 1.6 kW | L32-exit | −56.2 / −55.4 / −46.3 % | −83.2 / −68.4 / −55.8 % | 106–120 / 72–122 % | 2–8 kHz |
| 3.0 kW | L38-hist | −59.4 / −55.8 / −48.4 % | −56.8 / −61.3 / −53.4 % | 310–349 / 271–326 % | 4–9 kHz |
| 3.0 kW | L32-anode | −46.2 / −47.9 / −37.3 % | −52.4 / −57.9 / −38.8 % | 272–317 / 159–314 % | 5–16 kHz |
| 3.0 kW | L32-exit | −48.4 / −54.3 / −42.2 % | −65.4 / −60.4 / −49.4 % | 91–113 / 103–131 % | 6–8 kHz |

The conclusion is unchanged: no registration reproduces the quiet measured discharge at default transport. L32-anode
(1.6 kW coils) stays closest in both modes: −29 to −39 % vs raw, −34 to −45 % vs corrected. Its vacuum runs are the least
oscillatory (RMS 27–40 %). Geometry first, transport second; c₁, c₂ are not being fitted.

**Project status (Hall).** Solver execution validated; numerical convergence acceptable; facility correction understood
and worked around; historical measured P5 topology available; 2025 geometry and B-field registration unresolved;
anomalous transport not identified; absolute Hall prediction not validated. Gate 3 FAIL.

**hall_map_schema_v1** (`hallthruster_bridge/hall_map_schema_v1.json`). This is the one interchange definition: field
names, units, definitions, required meta (schema, pin, installed commit, reaction set, transport, facility_ingestion,
numerics) and the `sustained` convention. `run_cases.jl` emits the fields named there and attaches `schema_missing` /
`map_ready` to every point. `hall_map.py` derives `REQUIRED_FIELDS` / `REQUIRED_META` from the same file and rejects maps
without `meta.schema`. A test checks that the driver emits exactly the fields marked `computed`. Renames: `ion_current` →
`ion_current_A`, `Id_osc_rel` → `Id_pp_rel`. New fields: `Id_rms_rel`, `Id_f_dominant_Hz`, `current_eff`, `voltage_eff`,
`ion_species_fraction_atomic` (exit ion number flux carried by single-atom species; 1.0 for Xe). Still **not computed:**
`wall_ion_flux_m2s`, `wall_ion_energy_eV`. No point is map-ready until they have a producer.

**Upstream / pin.** Attaching UM-PEPL/HallThruster.jl from this environment wasn't permitted, so the issue
(`hallthruster_bridge/upstream/`) still needs filing by a human. `PINNED.toml` now carries an `upgrade_policy`: an upstream
fix never moves the pin automatically; an upgrade is a model change (rerun P5 in both modes, log, then accept).

## N₂/N reaction data: N ionization built; three tables blocked on source access (2026-09-25)
Scope: build and provenance-check the four missing tables for `propellants/n2_n.toml` only; no P5-N₂ runs or transport
fitting (transport will be the frozen Xe-identified closure).

**Built: `ionization_N.dat`** (e + N(⁴S) → N⁺ + 2e, threshold 14.534 eV). Cross section: Kim & Desclaux, PRA 66, 012708
(2002), BEB, ground state, as tabulated by NIST SRD 107 (80 points, 15 eV – 5 keV, peak 1.40×10⁻²⁰ m² at 97 eV).
Maxwellian-integrated with `abep_sim/rate_tables.py`. The build script (`scripts/build_n_ionization_table.py`) fetches the
NIST table and doesn't commit it, because NIST SRD data are copyrighted. Checks:
- The Kim & Desclaux 30 % ²D / 70 % ⁴S curve agrees with the Brook, Harrison & Smith (1978) beam measurement, whose beam
  contained metastables, to within ~5 % above 17 eV.
- HallThruster.jl's own loader reads the file; k_N/k_N₂ = 0.67–0.83 over ε = 6–255 eV.
- A plain Kim–Rudd BEB evaluation with the NIST orbital constants does **not** reproduce the NIST ⁴S curve (+6 % at 1 keV,
  larger near threshold). Kim & Desclaux use an open-shell treatment not re-implemented here, so the published values are
  used as-is.

The table lives in `hallthruster_bridge/propellants/` and is used only by HallThruster.jl. *(Wording corrected
2026-09-25: an earlier version said `plasma_chem` loads `abep_sim/data/rates/` automatically. It doesn't. It loads a single
hard-coded entry, `("N2", "iz") → rates/ionization_N2_N2+.dat`, and never reads `hallthruster_bridge/propellants/`.)*
**The HallThruster.jl and Python 0-D chemistry databases aren't unified:** the 0-D model still uses its Arrhenius fit for
N ionization. That fit gives 3.12×10⁻¹⁵ m³/s at T_e = 10 eV vs 6.38×10⁻¹⁵ m³/s from this table, i.e. **~2× low**, like the
earlier N₂ finding (next-work item 6). Goldens are unchanged because nothing in the 0-D path changed.

**Blocked: `dissociation_N2.dat`, `excitation_N2.dat`, `elastic_N.dat`.** The primary evaluations (Itikawa, JPCRD 35, 31
(2006); Song et al., JPCRD 52, 023104 (2023); Cosby, JCP 98, 9544 (1993); Wang, Zatsarinny & Bartschat, PRA 89, 062714
(2014)) are paywalled or behind bot challenges (AIP, APS, UCL Discovery 403) from this environment. LXCat is reachable,
but its redistribution policy doesn't authorise third parties (commercial interests in particular) to redistribute its
data, and commercial inclusion needs the database owner's written permission. It also requires the user to accept terms
on download. Not used, pending a decision by the project. Values from memory are not used (rule 6). The driver still
refuses the N₂ cases, now naming these three files.

**Project decision (2026-09-25): no outreach.** No emails or other contact with authors or labs, HPEPL included. The P5 geometry
questions above stay open items, to be resolved only from published sources. The three registration hypotheses (`L38-hist`,
`L32-anode`, `L32-exit`) are carried until published evidence settles them.

## Hall-map schema: wall-ion flux and energy producer (2026-09-25)
`wall_ion_flux_m2s` and `wall_ion_energy_eV` are now computed (`bridge_lib.jl: wall_ion_metrics`). They aren't a new
model: they re-evaluate the solver's own WallSheath expressions (`physics/wall_losses.jl`):
- **Flux:** the per-wall Bohm ion flux loss_scale·h·Σ n_s√(Z_s e T_e/m_s), h = edge-to-centre density ratio.
- **Impact energy:** Z·ϕ_s + T_e/2, where ϕ_s is the solver's space-charge-limited sheath potential with its SEE yield
  and cap.
- **Averaging:** evaluated per saved frame in the averaging window over the channel cells (z ≤ L), then time-averaged
  (flux-weighted for energy). Breathing makes a time-averaged-state evaluation differ.
- **Gaps:** other wall models, and shielded thrusters (wall T_e needs unsaved solver cache), return no value with a stated
  reason. There is no placeholder.

**Check** (`hallthruster_bridge/checks/wall_flux_consistency.jl`, P5 Xe1-L32-anode, 11 frames × 62 channel cells outside
the exit transition): the producer's flux equals the solver's saved electron-wall frequency × Δr·(1−γ)·n_e with a
median difference of 0.23 %. The maximum is 10 %, only where T_e changes steeply within the breathing cycle, with
alternating sign. That's consistent with `nu_wall` and the saved T_e/n_e belonging to different stages of a step
(not verified in the solver source). In the exit transition cells the solver's saved `nu_wall` includes the
wall-transition factor, so those cells are excluded from the check.

**Caveat.** With the default `ion_wall_losses=false` this flux sets the electron wall energy loss but is **not**
removed from the ion fluid. `wall_ion_basis` records this on every point. P5-Xe values at default transport:
2–4×10²⁰ m⁻²s⁻¹ (≈3–6 mA/cm²), 41–61 eV. Every schema field now has a producer, so `map_ready` can be true. Whether a
point is trustworthy still depends on `converged`/`sustained` and on the transport validation, which hasn't happened yet.

## P5-Xe transport identification under competing geometry hypotheses, leave-one-out (2026-09-25)
**Protocol** (project decision; `scripts/identify_p5_transport.py`, worker `hallthruster_bridge/identify_worker.jl`):
- **Hypotheses:** H1 = L38-hist, H2 = L32-anode, H3 = L32-exit (1.6 kW coil shape, B(exit) = 162.5 G). Everything
  except TwoZoneBohm c₁, c₂ and the transition length is identical and fixed: B(z), WallSheath(BNSiO2, 1.0), cathode
  coupling, Eq. (13) ingestion, chemistry, numerics (200 cells, 2 ms, average 1–2 ms).
- **Pre-registered grid** (no optimiser, every point run and logged): c₁ ∈ {1/1000, 1/500, 1/250, 1/160, 1/100, 1/50},
  c₂ ∈ {1/64, 1/32, 1/16, 1/8, 1/4}, L_t/L ∈ {0.05, 0.1, 0.2}, c₁ ≤ c₂. That's 87 combinations × 3 hypotheses ×
  3 points = 783 runs.
- **Calibration data:** facility mode only (ingestion ON). Targets are raw I_d = P_d/V_d (Table 4) and raw stand thrust,
  recovered by inverting Eq. (16) with the paper's ζ_en = 0.8 from the published corrected thrust.
  **Per-point thrust source:** Xe1 72.8 and Xe3 86.8 mN are the range end-points in the Brabston abstract. Xe2 = 83.4 mN is
  read from Fig. 5 (raster image, 2497×934 px). Axes are calibrated from 5 major y ticks and 10 major x ticks
  (residuals < 0.25 mN, < 0.002 kW). The marker centroids reproduce the text values for Xe1/Xe3 (72.85/87.04 mN).
  Their x-positions equal the Eq. (14)-corrected powers I_d,corr·V_d to 0.004 kW, which shows Fig. 5 plots
  ingestion-corrected quantities. Uncertainty ±4.9 mN (Table 5). Raw targets: 82.3 / 93.0 / 95.2 mN.
- **Objective (stated convention):** J = mean over calibration points of (ΔI/I)² + (ΔT/T)².
- **Oscillation:** reported as values; no numeric target (Brabston only state that the coils minimised oscillation).
- **Defensible prior (flag, not filter):** c₁ ≤ c₂ ≤ 1/16 (Bohm).
- **Leave-one-out:** (Xe1,Xe2)→Xe3, (Xe1,Xe3)→Xe2, (Xe2,Xe3)→Xe1, run as post-processing of the same grid.

**All runs:** `hallthruster_bridge/identification/p5_xe_identification_v1_runs.csv` (783 rows; 1 failure, H3/Xe3/c₁=1/1000,
c₂=1/64, L_t=0.1L, retcode failure). Summary: `p5_xe_identification_v1_summary.json`. Vacuum-mode check of the selected
fits: `p5_xe_identification_v1_vacuum_check.csv`.

**Leave-one-out results** (selected by J; errors vs raw facility targets):

| hyp. | selected (c₁, c₂, L_t) per round | same in all rounds | calibration | held-out I_d / thrust | I_d RMS |
|---|---|---|---|---|---|
| H1 L38-hist | (1/50, 1/8, 0.05L), (1/50, 1/4, 0.2L), (1/50, 1/8, 0.2L) | no | ≤ 15.5 % I_d, ≤ 1.7σ T | −6.9 / −18.0 / −1.1 %; 1.7 / −1.4 / 2.7σ | 220–243 % |
| H2 L32-anode | (1/50, 1/8, 0.05L) ×3 | **yes** | ≤ 9.6 % I_d, ≤ 0.3σ T | +4.0 / −5.5 / +9.6 %; 0.3 / −0.2 / 0.0σ | 225–237 % |
| H3 L32-exit | (1/50, 1/4, 0.2L), (1/50, 1/4, 0.1L), (1/50, 1/4, 0.2L) | no | ≤ 10.4 % I_d, ≤ 0.6σ T | −5.8 / −17.5 / +5.4 %; 0.1 / −0.4 / −0.3σ | 134–152 % |

**Classification.**
1. *Fits the calibration points (time-averaged I_d, thrust)?* Yes for all three hypotheses.
2. *Predicts the held-out point?* H2 best (≤ 9.6 % I_d, ≤ 0.3σ thrust, identical parameters in every round). H1 and H3
   miss one point by ~18 % in I_d.
3. *Quiet/sustained discharge?* **No, for every hypothesis.** All selected fits are deep relaxation oscillations (RMS
   134–243 %). Over the whole grid, no combination is below 50 % RMS at all three points under any hypothesis. The
   quietest combinations (max RMS 58 % H1, 90 % H2, 95 % H3) underpredict I_d by 23–70 % and thrust by up to 17σ.
4. *Within defensible bounds?* **No.** Every selected fit has c₁ at the grid maximum (1/50, ~3× the default) and super-Bohm
   c₂ (1/8 or 1/4). The optimum lies at or beyond the pre-registered edge. The grid wasn't extended, because that would
   change the protocol.
5. *Secondary vacuum check* (ingestion OFF vs Eq. 14/16-corrected values): the selected fits carry over worse (I_d −28 % to
   +13 %, thrust up to 3σ, RMS 41–217 %). H2 is the most consistent (+3.6 / −15.7 / +13.4 %).

**Conclusion.** With TwoZoneBohm in the pre-registered bounds and all other physics fixed, **no geometry hypothesis
reproduces the experimentally quiet operating regime**. Mean I_d and thrust can be matched only by breathing solutions
at the grid edge with super-Bohm outer transport. **The geometry is therefore not discriminated.** H2's stable,
predictive leave-one-out behaviour is noted but conditional on an operating regime the experiment didn't show, so it
isn't counted as evidence for L32-anode. The inadequacy sits in the combination "TwoZoneBohm + fixed inputs". The
candidates, none tested yet, are:
- the transport-model family (a two-level Bohm profile may be too coarse for this field topology);
- the assumed coil shape (Peterson 1.6 kW setting, where Brabston's currents are unknown);
- other fixed physics (wall model, anode boundary condition, 1-D limits).

Gate 3 stays FAIL. Carry geometry uncertainty forward; don't freeze a transport closure.

**Wall-life trust (2026-09-25, before merge).** Schema-complete isn't erosion-grade. `hall_map_schema_v1` now requires map
meta `ion_wall_losses` and a per-point `wall_life_trustworthy` = converged ∧ sustained ∧ `ion_wall_losses=true` ∧ both wall
fields present (so WallSheath, unshielded). `HallMap` returns it separately from performance `trustworthy`. It's true
only if the map meta says `ion_wall_losses` is exactly `True` and every surrounding node is wall-life-trustworthy.
Current P5 runs: `map_ready` true, `wall_life_trustworthy` false (`ion_wall_losses=false`).

## Pre-registration: ScaledGaussianBohm identification and stopping rule (2026-09-25, committed before any SGB run)
**Decision (project lead):** TwoZoneBohm is rejected for P5-Xe validation, and its grid won't be widened. The next test
is a controlled transport-family test, with coil shape as a discrete hypothesis only.
- **Hypotheses (6):** 3 registrations (L38-hist, L32-anode, L32-exit) × 2 historical coil shapes (Peterson 2001 1.6 kW
  and 3.0 kW settings). B(z) is exactly as in `cases/p5_xenon.json` / `cases/p5_xenon_coil_sensitivity.json`, with no
  rescaling or reshaping.
- **Family:** HallThruster.jl `ScaledGaussianBohm`, c(z) = a·(1 − b·exp(−½((z − c·L)/(w·L))²)). The profile is fixed after
  the first iterations.
- **Grid:** a ∈ {1/32, 1/16, 1/8}, b ∈ {0.8, 0.9, 0.97}, c ∈ {0.9, 1.0, 1.1} L, w ∈ {0.1, 0.25} L. That's 54 combinations
  × 6 × 3 = 972 runs.
- **Defensible prior (flag):** a ≤ 1/16.
- **Unchanged from the TwoZoneBohm protocol:** facility-mode calibration vs raw I_d and raw thrust, the objective,
  leave-one-out over Xe1–Xe3, the vacuum-mode secondary check on selected fits, and logging of all failed runs.

**Stopping rule.** If ScaledGaussianBohm fails, try only a 3-node MultiLogBohm with node locations fixed in advance and the
three c values fitted. No StepTrough or 6–7-parameter profiles. If neither family simultaneously gives:
- reasonable I_d,
- reasonable thrust,
- successful blind prediction, and
- no deep relaxation/current-collapse regime,

then stop calibrating against P5 and record **"published P5 information is insufficient to identify transport
uniquely"**. That uncertainty is then carried into the Hall response model.

**Pre-registration addendum (before any SGB result):** the fallback 3-node MultiLogBohm has nodes fixed at 0.5 L, 1.0 L
and 1.5 L (scaled to each hypothesis's channel length), with c constant beyond the end nodes. Grid: c_up ∈ {1/160, 1/64,
1/25}, c_exit ∈ {1/800, 1/300, 1/100}, c_plume ∈ {1/32, 1/16, 1/8}, giving 27 combinations × 6 hypotheses × 3 points =
486 runs. Defensible flag: all c ≤ 1/16. It runs only if ScaledGaussianBohm fails the criteria.

## ScaledGaussianBohm identification: results (2026-09-25)
Pre-registered protocol and grid as above. 972 runs, 1 failure (H3b/Xe2, a=1/32, b=0.97, c=1.1L, w=0.25L). Files:
`hallthruster_bridge/identification/p5_xe_identification_sgb_v1_{runs.csv,summary.json}` and the post-hoc analysis
`..._posthoc_quiet_loo.json`.

**Pre-registered leave-one-out (objective ignores oscillation).** Selections are mostly a = 1/16 (defensible) but deep
breathing (RMS 55–380 %). H1a and H3b pick the same set in all rounds. Blind I_d errors are −20 % to +27 %; blind thrust
is within ±3.8σ. One exception: H2a round "hold Xe2" selects a quiet set (a = 1/8, b = 0.97, c = 0.9 L, w = 0.25 L; RMS
2–3 %).

**Quiet solutions exist, unlike TwoZoneBohm.** Every hypothesis has combinations below 50 % RMS at all three points:
22 (H1a), 23 (H1b), 28 (H2a), 28 (H2b), 15 (H3a) and 16 (H3b) of 54. Most sit below 5 %. Almost all need a = 1/8
(super-Bohm, grid edge). The one quiet and defensible set (a = 1/16, b = 0.9, c = 0.9 L, w = 0.25 L; RMS < 0.5 %) exists
only for L32-anode (H2a, H2b): I_d −9 / −19 / −6 %, thrust +4.4 / +2.7 / +2.8σ.

**Post-hoc analysis (not pre-registered):** leave-one-out restricted to sets that are quiet (RMS < 50 %, internal
diagnostic) at the calibration points.

| hyp. | selected | same all rounds | held-out I_d (Xe1/2/3 held out) | held-out thrust | held-out RMS |
|---|---|---|---|---|---|
| H1a L38/1.6 kW | a = 1/16, b = 0.8, c = 0.9 L, w = 0.25 L | yes | −7 / −14 / 0 % | +3.2 / +2.7 / +2.8σ | 28–49 % |
| H1b L38/3.0 kW | mixed (a = 1/8 or 1/16) | no | −7 / −28 / −3 % | +3.8 / −0.4 / +3.1σ | 1–34 % |
| H2a L32-anode/1.6 kW | a = 1/8, b = 0.97, c = 0.9 L, w = 0.25 L | yes | −3 / −13 / +3 % | +3.6 / +2.0 / +2.2σ | 2–3 % |
| H2b L32-anode/3.0 kW | same | yes | −3 / −13 / +3 % | +3.6 / +2.0 / +2.2σ | 2 % |
| H3a L32-exit/1.6 kW | mixed (c = 0.9 or 1.1 L) | no | −4 / −17 / 0 % | +4.2 / +1.1 / +2.6σ | 0–67 % |
| H3b L32-exit/3.0 kW | a = 1/8, b = 0.97, c = 0.9 L, w = 0.25 L | yes | −4 / −14 / +1 % | +4.1 / +2.4 / +2.5σ | 0 % |

**Evaluation against the stopping-rule criteria.**
- *Reasonable I_d:* yes in the quiet regime (blind −3 to −14 %, with Xe2 always worst).
- *No deep relaxation:* achievable, but only with super-Bohm a = 1/8. The one defensible quiet-selected set (H1a) sits at
  28–49 % RMS.
- *Reasonable thrust:* **no.** Every quiet solution under every hypothesis overpredicts raw thrust by +2 to +4.5σ (10–20 mN).
  It's systematic and independent of the I_d fit. Candidate cause (not tested; fixed physics in this exercise): the 1-D
  thrust counts all ion momentum as axial (`apply_thrust_divergence_correction=false`, no plume solve), whereas the stand
  measures axial thrust. Brabston's per-point divergence isn't published numerically, so no correction is applied.
- *Geometry:* still not discriminated. The same quiet set gives near-identical results for H2a, H2b and H3b, and coil
  shape barely matters in the quiet regime.

**Verdict:** ScaledGaussianBohm fails the pre-registered criteria (thrust, defensible bounds), so the pre-registered 3-node
MultiLogBohm runs next. It's a clear improvement on TwoZoneBohm: it shows that a transport trough near the exit can produce
the experimentally quiet regime with blind I_d within ~15 %.

## 3-node MultiLogBohm identification: results; stopping rule triggered (2026-09-25)
Pre-registered nodes 0.5/1.0/1.5 L and grid as above. 486 runs, 5 failures (all at c_up = 1/25 with c_exit = 1/800 or
1/300; logged). Files: `p5_xe_identification_mlb_v1_{runs.csv,summary.json,posthoc_quiet_loo.json}`.
- **Pre-registered leave-one-out:** every hypothesis selects grid-edge sets (c_up = 1/25, c_exit = 1/100, c_plume = 1/16
  or 1/8), all breathing (RMS 41–258 %). Blind I_d −0.2 to −28.6 %.
- **Quiet sets** (all points below 50 % RMS): 3 (H1a), 0 (H1b), 4 (H2a), 2 (H2b), 0 (H3a), 0 (H3b) of 27. Those with RMS
  ≤ 31 % miss I_d by −24 to −51 %. The one quiet set with good I_d (H2a, c_up = 1/25, c_exit = 1/100, c_plume = 1/8;
  RMS 41–48 %, I_d 0 / −11 / +4 %) overpredicts thrust by +2.6 to +4.3σ, the same systematic seen with ScaledGaussianBohm.

**Stopping rule applied.** Neither ScaledGaussianBohm nor the pre-registered 3-node MultiLogBohm simultaneously gives
reasonable I_d, reasonable thrust, successful blind prediction and no deep relaxation within defensible transport.
**Conclusion: published P5 information is insufficient to identify Hall anomalous transport uniquely.**
Calibration against P5 stops. No transport closure is frozen from P5, and P5 geometry (32 vs 38 mm) and coil shape stay
undiscriminated. The Hall response model must carry transport, geometry and coil-shape uncertainty explicitly rather than
a single calibrated closure.

**What the three families did establish** (usable as constraints, not calibration):
1. A two-level Bohm profile cannot produce the reported quiet regime with the measured P5 field under any hypothesis.
2. A transport trough near the exit (ScaledGaussianBohm) *can* produce quiet discharges with blind I_d within ~15 %, but
   only with peak transport at or above Bohm (a = 1/8) in all but one set.
3. **Every quiet solution in every family and hypothesis overpredicts raw thrust by +2 to +4.5σ (10–20 mN).** That's
   systematic and independent of the transport shape. It points at a fixed-physics or output-definition issue, not
   transport. The leading candidate is that the 1-D thrust counts all ion momentum as axial (no divergence correction,
   no plume model), whereas the stand measures axial thrust. **This was not tested** (fixed physics in this exercise), and
   it's the only identified item that could reopen P5 calibration. That would be a separate, pre-registered test.
4. Xe2 is consistently the worst I_d point in every quiet solution. It's also the point whose measured I_d is anomalous
   even after the Eq. (14) correction.

## Pre-registration v2: P5-Xe thrust-observable reconciliation (2026-09-25, committed before any v2 scoring or run)
**Project decision:** the v1 stopping-rule conclusion is **suspended** (not deleted). The v1 records above stay unchanged
for provenance. The v1 comparison scored the 1-D total ion momentum flux against a stand thrust that Brabston's own
efficiency model treats as carrying an off-axis (beam-efficiency) loss. Interim status:
- TwoZoneBohm: rejected for this validation (no quiet solution anywhere, independent of thrust).
- 3-node MultiLogBohm: no demonstrated advantage.
- ScaledGaussianBohm: **unresolved**, pending a divergence-consistent thrust comparison.

**Measured beam efficiency: a discrepancy inside the paper.** Eq. (4) defines Ψ_b = ⟨cos θ⟩²_mv ≈ cos²θ_d, and Eq. (1a)
gives η_T = η_E Φ_P Ψ_b with T = ṁ⟨v⟩⟨cos θ⟩, so the stand's axial thrust = total ion momentum × √Ψ_b. Digitized xenon
values (`hallthruster_bridge/identification/brabston_fig8_fig9_xenon.json`; Fig. 9 axes residual ≤ 0.0002, Fig. 8 ≤ 0.0009):
- **Fig. 9:** Ψ_b = 0.614 ± 0.071, 0.601 ± 0.075, 0.621 ± 0.073; η_E = 0.494 / 0.447 / 0.527; Φ_P = 0.894 / 0.867 / 0.860.
- **Fig. 8:** component η_T = 0.345 / 0.322 / 0.378; thrust η_T = 0.332 / 0.337 / 0.392. The thrust values reproduce
  T_corr²/(2ṁ_a I_d,corr V_d) = 0.330 / 0.346 / 0.395.
- **The discrepancy:** η_E·Φ_P·Ψ_b(Fig. 9) = 0.271 / 0.233 / 0.281, i.e. **27–38 % below** the paper's own component
  η_T (Fig. 8). The paper says the model matches η_T within 3.3 %. Fig. 8 is reproduced (0.346 / 0.301 / 0.357) only if
  the efficiency factor is √(plotted Ψ_b) ≈ 0.78.

Both readings are carried, and **neither may be chosen by fit quality**:
- **A (literal Eq. 4 + Fig. 9):** axial factor f = √Ψ_b = 0.783 / 0.775 / 0.788 (θ_d ≈ 39°).
- **B (consistent with Fig. 8):** Ψ_b = η_T,comp/(η_E Φ_P) = 0.781 / 0.830 / 0.833, so f = 0.884 / 0.911 / 0.913
  (θ_d ≈ 25–28°).
- **Uncertainty:** relative uncertainty of f from the Fig. 9 bars is 5.8–6.2 % (σ_Ψ/2Ψ), in both readings.
- **Facility caveat:** Ψ_b was measured in the facility, where CEX "artificially increases the beam divergence"
  (Brabston), and the same f is applied in both modes.

**Rescoring** (`scripts/rescore_p5_axial_thrust.py`): T_axial,pred = T_1D·f(point). Nothing in the simulations changes.
- **Vacuum mode is primary:** ingestion OFF vs I_d,corr (Eq. 14) and the published T_corr. This needs the ScaledGaussianBohm
  and MultiLogBohm grids re-run with ingestion off (`identify_p5_transport.py run --family sgb|mlb --calmode vacuum`). Same
  pre-registered grids, same families, no new exploration: the v1 grids were facility-mode only.
- **Facility mode is the consistency check:** the existing runs vs raw I_d and raw thrust. Its thrust is less clean,
  because HallThruster.jl injects the ingested flow at the anode, so it doesn't carry Brabston's ζ_en = 0.8 thrust discount.
- **Thrust uncertainty:** σ_T = √(4.9² + (T_axial,pred·rel_err(f))²) mN.
- **Objective:** as in v1, J = mean over calibration points of (ΔI/I)² + (ΔT/T)².
- **Leave-one-out, two pre-registered selections:** (i) all grid points; (ii) points quiet (RMS < 50 %, internal
  diagnostic) at the calibration points.

**Pass criteria** (decision thresholds fixed now, before scoring), per family × hypothesis × reading × mode × selection,
in **all three** rounds:
- held-out |ΔI_d| ≤ 15 %;
- held-out |ΔT| ≤ 2σ_T;
- RMS < 50 % at all three points;
- defensible parameters (ScaledGaussianBohm a ≤ 1/16; MultiLogBohm all c ≤ 1/16). "Passes except defensibility" is
  reported separately.

A verdict is stated only if it holds under both readings A and B; otherwise it's reported as reading-dependent.
HallThruster.jl's plume model stays off, since `solve_plume` would add a model rather than convert an observable.
The TwoZoneBohm rejection doesn't depend on thrust and isn't rescored.

## v2 results: thrust-observable reconciliation (2026-09-25)
Pre-registered protocol above, applied unchanged (thresholds not revisited). New full-grid vacuum-mode runs (ingestion OFF):
ScaledGaussianBohm 972 runs, 0 failed; MultiLogBohm 486 runs, 6 failed (logged). Files:
`p5_xe_identification_{sgb,mlb}_v1_vacuum_runs.csv` and `p5_xe_axial_thrust_v2_rescore.json` (every combination of
family × mode × reading × selection × hypothesis, with per-round held-out errors).

**1. The v1 thrust failure is explained by the observable, under both readings.** With T_axial = T_1D·f, the quiet
ScaledGaussianBohm solutions predict held-out thrust within 2σ almost everywhere, in both modes and under both reading A
(f ≈ 0.78) and reading B (f ≈ 0.89–0.91). The +2 to +4.5σ excess in v1 came from comparing total ion momentum with an axial
stand measurement. **Superseded v1 statement:** "every quiet solution fails on thrust". The v1 run data are unchanged.

**2. Primary (vacuum) verdict: no family passes.**
- **ScaledGaussianBohm** fails now on blind I_d only. Closest case: H2a (L32-anode, 1.6 kW coils), quiet selection. The
  **same defensible set wins all three rounds under both readings** (a = 1/16, b = 0.8, c = 0.9 L, w = 0.25 L). It's quiet
  (RMS 28–30 %) and its blind thrust is within 2σ (A: −0.4 / −1.8 / −1.7σ; B: +1.0 / 0.0 / +0.2σ). Blind I_d is
  −2.8 / **−15.6** / +0.9 %: the Xe2 hold-out misses the pre-registered 15 % threshold by 0.6 points. Other quiet
  selections miss held-out Xe2 by −16 to −25 % or Xe3 by +15 to +26 %, or need super-Bohm a = 1/8.
- **MultiLogBohm (3 nodes):** quiet solutions miss I_d by 17–58 %; in H1a (vacuum, both readings) the set selected on
  the Xe1/Xe2 calibration points has a *failed* blind Xe3 simulation (corrected 2026-09-25, see below). No advantage
  demonstrated, confirmed.

**3. Secondary (facility) check:** two ScaledGaussianBohm passes, H2a under reading A and H1a under reading B (the latter
at 49 % RMS). They don't hold under both readings, so they're **reading-dependent** and don't count as a verdict. Facility
thrust is also less clean, because HallThruster.jl injects the ingested flow at the anode.

**Outcome under the pre-registered rules.** Neither ScaledGaussianBohm nor the 3-node MultiLogBohm meets all criteria in the
primary mode. So the stopping-rule conclusion, *"published P5 information is insufficient to identify Hall transport
uniquely"*, **stands, with its reason corrected**. The limiting observable is no longer thrust (resolved by the beam-efficiency
conversion) but **blind I_d at Xe2**. Xe2 is the setpoint whose measured I_d is anomalous even after Eq. (14): 8.04 A at
250 V versus 6.96 / 6.95 A at 231 / 274 V, at the same flow and field.

**What v2 adds to the record:**
- A near-exit transport trough (ScaledGaussianBohm) at or below Bohm reproduces the quiet regime, thrust within the
  measurement and beam-efficiency uncertainty, and blind I_d within ~16 %, with one parameter set.
- That set is selected only under L32-anode/1.6 kW. It's the only hypothesis where one defensible, quiet set wins every
  round under both readings. That's weak evidence for L32-anode, not a resolution.
- Brabston's Fig. 9 Ψ_b and Fig. 8 component η_T are mutually inconsistent by 27–38 %. The thrust conclusion holds under
  both readings, so it doesn't depend on resolving that.

**Carried forward:** no closure frozen from P5. The Hall response model should carry transport uncertainty. The
ScaledGaussianBohm family near (a = 1/16, b = 0.8, c = 0.9 L, w = 0.25 L) is the best-supported candidate region,
together with the geometry and coil-shape hypotheses and the Ψ_b reading ambiguity.

## Correction: v2 rescoring leave-one-out bookkeeping (2026-09-25, no new simulations)
A post-merge review of `scripts/rescore_p5_axial_thrust.py` found two bookkeeping bugs, not physics bugs; the simulation
campaign is unaffected.
1. **Failed runs were discarded before selection.** This leaks the held-out outcome into model selection: a set that fits
   the calibration points best but whose blind run failed was skipped, and another set could be substituted. Fixed: failed
   rows are kept, only calibration-point success (and quietness, for the quiet selection) controls eligibility, and a
   failed held-out run is recorded as a failed blind prediction (`hold_failed`).
2. **`same_combo` was true when every round had no selection**, because `{None}` has one element. Fixed: true only if
   all three rounds selected a set and the sets are identical.

**Regenerated** `p5_xe_axial_thrust_v2_rescore.json`. 12 of 96 entries change, all MultiLogBohm, and **no pass or
pass-except-defensibility outcome changes**:
- **Blind failures now recorded:** vacuum/quiet/H1a (readings A and B) holding out Xe3, and facility/quiet/H1b (A and B)
  holding out Xe2. The selected sets' blind runs failed, where previously a different set was substituted or nothing was
  selected.
- **`same_combo` true → false:** vacuum/quiet/H1a and the quiet H3a/H3b entries (no selection in any round), in both modes
  and both readings.
- **ScaledGaussianBohm entries are unchanged.** The best vacuum case (H2a, L32-anode/1.6 kW) keeps the same defensible set
  in all rounds under both readings (a = 1/16, b = 0.8, c = 0.9 L, w = 0.25 L): blind I_d −2.78 / −15.56 / +0.92 %, max
  RMS 30.3 %, thrust within 2σ. Facility passes stay reading-dependent (H2a under A, H1a under B).
- **The v2 verdict, Gate 3 and the stopping-rule conclusion are unchanged.**
- The ad-hoc v1 post-hoc quiet analyses (`*_posthoc_quiet_loo.json`) used the same success filter. Re-evaluated with the
  corrected semantics, only MultiLogBohm H1b holding out Xe2 changes (no selection → a set whose blind run failed). The v1
  files are left as recorded; no v1 conclusion changes.

Regression tests: `test_rescore_loo_holdout_failure_is_a_blind_failure` and
`test_rescore_same_combo_requires_actual_selections`. Both fail on the previous script and pass on the fix.

## P5-Xe identification campaign closed (2026-09-25, project decision)
After the corrective rescoring (ppusapati/abep#11), the campaign is closed. It reopens only on genuinely new published
information: the 2025 channel depth, coil currents or measured B(z), per-point divergence, or discharge-current traces.
Final state:
- TwoZoneBohm rejected (no quiet regime anywhere).
- 3-node MultiLogBohm shows no advantage; the corrected bookkeeping exposes genuine blind-run failures.
- ScaledGaussianBohm shows that a near-exit transport trough at or below Bohm reproduces the quiet regime and, with the
  beam-efficiency conversion, the thrust. The best set (a = 1/16, b = 0.8, c = 0.9 L, w = 0.25 L; L32-anode/1.6 kW; same in
  every round under both Ψ_b readings) misses the pre-registered blind-I_d criterion only at Xe2 (−15.56 % vs 15 %).
- Gate 3 stays FAIL and no closure is frozen.

**Next phase:** a Hall uncertainty ensemble (ScaledGaussianBohm region × geometry × coil shape × Ψ_b reading), carried into
Hall maps and the architecture trade. The N₂/N chemistry work continues in parallel.

## Two-layer Hall uncertainty structure (2026-09-26, project decision)
P5-specific ambiguity must not leak into the Vyovrinda spacecraft model. So the Hall uncertainty is split in two:
- **Layer 1, calibration nuisance:** P5 registration, historical coil shape, beam-efficiency reading, facility-ingestion
  interpretation. It's uncertainty in the P5 evidence, and it's marginalized when admitting transport closures. It is
  **never** a Vyovrinda design variable, map axis or architecture-trade dimension. `HallMap` rejects maps that use a layer-1
  variable as an axis, and `hall_ensemble.load_ensemble` rejects members that use one as a transport parameter.
- **Layer 2, transferable:** the credible set of transport closures surviving marginalization. It's an **unweighted**
  scenario set; the loader rejects any other weighting until evidence-based weighting is justified and logged. Each member
  carries `ensemble_member_id`, `transport_family`, `transport_parameters`, `calibration_hypotheses`, `evidence_basis`,
  `applicability_domain` and `validation_status`. Each Hall map names its member in `meta.ensemble_member_id` (now required
  by `hall_map_schema_v1`; no maps existed yet).

**Admission rule: pending.** Census from the existing vacuum-mode runs: in-sample, all three points quiet, thrust within 2σ,
admitted if at least one layer-1 combination supports it.

| I_d tolerance | ScaledGaussianBohm ≤ Bohm | super-Bohm | MultiLogBohm |
|---|---|---|---|
| 15 % | 0 | 0 | 0 |
| 20 % | 1 | 5 | 0 |
| 25 % | 5 | 8 | 0 |

All defensible sets are supported only by L32-anode. Until the rule is chosen, `members` is empty and no Hall map can be
loaded.

**Roadmap fix:** N₂ validation (P5-N₂, ECHT-N₂) runs across the credible Xe-informed ensemble with no retuning per case,
replacing "ONE transport parameter set", which contradicted the closed Xe campaign. N₂ becomes a discrimination
experiment that can shrink the ensemble.

## Credible set empty; SGB screening candidates (2026-09-26, project decision)
**Decisions:**
- No in-sample I_d tolerance for admission. The pre-registered 15 % blind criterion wasn't met; choosing 20 % or 25 %
  because those admit members would turn a failed validation into post-hoc calibration. The tolerance census stays in
  the ensemble file as a record of a *rejected* approach.
- Super-Bohm sets (a > 1/16) are not admissible under current evidence (diagnostic/sensitivity only).
- **The credible transport ensemble is empty.** That's the correct state today.

**Screening candidates**, kept separate from members, so new evidence can test hypotheses. No I_d cutoff is applied. The
criteria, on the vacuum-mode SGB grid:
- all three simulations successful;
- a ≤ 1/16;
- quiet at all three points (RMS < 50 %, internal diagnostic);
- divergence-corrected thrust within 2σ at all three points under at least one layer-1 combination.

Nine sets pass. This reproduces the project lead's independent count.

| id | a, b, c, w | best in-sample max \|ΔI_d\| | supporting layer-1 combinations |
|---|---|---|---|
| sgb-screen-01 | 1/16, 0.8, 0.9 L, 0.25 L | 15.56 % | L32-anode/1.6 kW (A, B) |
| sgb-screen-02 | 1/16, 0.97, 1.0 L, 0.1 L | 20.19 % | L32-anode/1.6 and 3.0 kW (A, B) |
| sgb-screen-03 | 1/16, 0.97, 0.9 L, 0.1 L | 20.22 % | L32-anode/1.6 and 3.0 kW (B) |
| sgb-screen-04 | 1/16, 0.97, 1.1 L, 0.1 L | 23.68 % | L32-anode/1.6 kW (B) |
| sgb-screen-05 | 1/16, 0.9, 1.1 L, 0.25 L | 24.61 % | L32-anode/1.6 and 3.0 kW (A, B) |
| sgb-screen-06 | 1/16, 0.9, 1.0 L, 0.25 L | 25.54 % | L32-anode/1.6 and 3.0 kW (A, B) |
| sgb-screen-07 | 1/16, 0.9, 0.9 L, 0.25 L | 25.92 % | L32-anode/1.6 and 3.0 kW (A, B); **also L38-hist/1.6 and 3.0 kW (B)** |
| sgb-screen-08 | 1/16, 0.97, 0.9 L, 0.25 L | 40.93 % | L32-anode/1.6 and 3.0 kW (B) |
| sgb-screen-09 | 1/16, 0.97, 1.0 L, 0.25 L | 42.01 % | L32-anode/1.6 and 3.0 kW (B) |

Support is L32-anode-dominated; only sgb-screen-07 is also supported by L38-hist. That's why none can be promoted to a
transferable closure on Xe evidence. The I_d column is diagnostic, not an admission criterion. Screening candidates never
produce design Hall maps: `HallMap` loads admitted members only, and a test enforces this.

**Promotion rule:** a candidate is promoted only after predicting new evidence not used to select it, without transport
retuning, within the physical prior. The acceptance criteria are pre-registered after auditing that evidence's
measurements and uncertainties, and before simulating it. Next: complete the N₂/N reaction set, then P5-N₂ as the
no-retuning discrimination experiment.

**Scope rule:** Hall screening/credible-set uncertainty belongs only to the ionization/discharge → acceleration/thrust
block of the RFP architecture:
- atmospheric path: intake → filter → compressor → atmospheric gas chamber → valve;
- Xe path: Xe chamber → valve;
- both paths feed that block.

It must never leak upstream, or into Vyovrinda's own thruster geometry.

## 2026-09-26 — Open-literature N₂/N sources ingested; N₂ dissociation table built

**Sources located (no LXCat):**
- Song et al., J. Phys. Chem. Ref. Data 52, 023104 (2023). The full text is on the NSF Public Access Repository (par.nsf.gov 10526876). It gives numeric recommended tables for dissociation (Table 9) and ionization. For the eight low-lying electronic states it recommends the R-matrix set of Su et al. 2021 (Figs. 11–18). It does not table them.
- Su, Cheng, Zhang & Tennyson, J. Phys. B 54, 115203 (2021), CC BY 4.0. Its supplementary spreadsheets hold per-state excitation cross sections for A, B, W, B′, a, a′, w and C. **They cover threshold to 20 eV only.**
- Song et al., Eur. Phys. J. D 77, 105 (2023), CC BY 4.0. It gives figures only (no tables). Its Fig. 4 shifts the theory curves by −1.5 eV to meet the EEL thresholds. JPCRD Table 8 likewise reports theory thresholds 1.5–1.9 eV above the EEL values.
- Ragimkhanov et al. 2026 (atomic-N elastic): not located by web or arXiv search. Citation or DOI needed.

**Built:** `dissociation_N2.dat` from JPCRD Table 9, which is the Cosby 1993 set (±20 %), via `scripts/build_n2_dissociation_table.py`.
- Explicit choices: σ = 0 below the first point (12 eV), with no threshold curve constructed.
- The hold tail above 200 eV is reported per mean energy: < 1 % up to 45 eV, 14 % at 90 eV.
- Header energy loss is 12.14 eV (the N(²D)+N(⁴S) channel, dominant per Cosby).

`rate_tables.maxwellian_rate` now takes an explicit `tail` (`hold` | `zero`). `hold` is bit-identical to the previous behaviour, so `ionization_N.dat` is unchanged. There is no golden or model change: the bridge tables are not read by the 0-D chemistry.

**Open (owner's decision):** N₂ excitation. The recommended per-state data end at 20 eV, but Maxwellian rates up to T_e ≈ 30 eV need σ well above that. Extending needs a second source, e.g. Johnson et al. 2005 (10–100 eV, measured), Kawaguchi et al. 2021 or Itikawa 2006, or an explicit Born-type extrapolation. That choice is not made here.

## 2026-09-26 — Chemistry validity guard; excitation / atomic-N source decisions

**Merged:** PR #17, the N₂ dissociation table. It was rebased onto main first. The 12.14 eV energy loss is now documented as a representative fixed loss for a channel-summed cross section, with 9.75–13.33 eV carried as model uncertainty.

**Guard (project decision):** no silent chemistry extrapolation.
- `propellants/rate_validity.toml` gives every rate table a validity domain in mean electron energy.
- `bridge_lib.jl` emits `chemistry_trustworthy`, a new `hall_map_schema_v1` field. It is converged ∧ sustained ∧ 1.5 × max T_e over the chemistry-active region (n_e·Σn_n ≥ 1 % of peak) ≤ the lowest limit in the reaction set. It also emits `Te_chem_region_max_eV` and the limiting file's basis.
- `HallMap` performance `trustworthy` now requires it.
- The dissociation limit is 45 eV (T_e = 30 eV) until its cross section is extended.
- Smoke-tested on a shortened Xe1 run: the new fields are populated, and map_ready is unchanged.

**Source decisions (owner):**
- N₂ excitation: eight state-resolved reactions (A, B, W, B′, a, a′, w, C). Su et al. 2021 up to 20 eV, then Johnson et al. 2005 (JGR 110, A11311, doi 10.1029/2005JA011295) from 20 to 100 eV. No renormalization at the join: the 10–20 eV overlap difference is recorded as source uncertainty. No −1.5 eV shift.
- Energy losses are the experimental vertical energies from Su 2021 Table 1 (Oddershede et al.): 7.75, 8.04, 8.88, 9.67, 9.31, 9.92, 10.27 and 11.19 eV. Su's per-state supplementary files carry the cc-pVTZ onsets (7.76, 8.67, … 11.88 eV).
- Above 100 eV: quantify the hold-vs-zero sensitivity at T_e = 10–30 eV first. Tabata et al. 2006 is considered only if the sensitivity is material.
- Atomic-N elastic: momentum-transfer cross section from Ragimkhanov et al., EPJD 80, 69 (2026), doi 10.1140/epjd/s10053-026-01166-3, CC BY 4.0. Wang, Zatsarinny & Bartschat 2014 is the low-energy cross-check. Disagreement in 5–50 eV is carried as uncertainty.

**Access status from this container:**
- Johnson 2005 is free-to-read on Wiley (bronze OA). Ragimkhanov 2026 is CC BY on Springer.
- Both publisher sites answer scripted requests with a JavaScript/bot challenge (HTTP 403 / "Client Challenge"). Using the headless browser would have needed a trust-store change, which was not permitted.
- No repository copy was found: NTRS has no PDF, and OpenAlex lists publisher locations only. So neither table is built yet.

## 2026-09-26 — Chemistry guard tightened (reaction-weighted, per frame); validity audit

This replaces the first version (commit d2009b3). That version used the time-averaged T_e over an n_e·n_n ≥ 1 %-of-peak region. It could miss two things:
- a low-density, high-T_e cell whose rate k_r makes it matter;
- a transient hot frame during breathing.

**Now:**
- For each reaction r, the activity R = n_e·n_target·k_r(3/2 T_e)·dz is summed over every saved frame of the averaging window and every cell.
- f_out,r is the share of that activity at 3/2 T_e above the file's limit. Validation rule: f_out = 0 (≤ 1e-12). No contribution allowance is set; one would have to be pre-registered, e.g. for architecture maps.
- k_r comes from the same 0–255 eV grid and end-clamping that the solver uses.

**New outputs:**
- `chemistry_extrapolated_fraction_max`;
- `chemistry_limiting_rate_file`;
- `chemistry_max_mean_energy_active_eV`;
- `chemistry_unresolved_rate_files`;
- `chemistry_per_reaction`;
- `chemistry_trustworthy`.

**Checks:**
- `checks/chemistry_validity_check.jl` uses synthetic frames with the real dissociation table. The cold case gives 0. A single transient 40 eV frame gives f_out = 0.016. A hot cell at 0.5 % of peak n_e·n_n gives 8.7e-4. The old region cut would have missed both.
- End-to-end N₂ smoke run (N1, 0.5 ms, uncommitted reaction subset without excitation or N elastic): not chemistry-trustworthy, because two tables are unresolved. Dissociation f_out = 0, with a max active mean energy of 35.9 eV (limit 45).
- End-to-end Xe1 smoke run: the built-in path is unchanged.

**Validity audit:**
- A "verify" value can no longer certify trust. Entries are now `verified` or `unresolved`.
- `ionization_N.dat` is verified to 255 eV. The NIST source spans 15–5000 eV, and the held-tail share is 0.0000 % up to 300 eV.
- The HallThruster-shipped `ionization_N2_N2+.dat` and `elastic_N2.dat` are **unresolved**. The package has no cross-section inputs (reactions/CITATIONS.md cites Itikawa 2006 only), and `elastic_N2.dat` ends at 100 eV mean energy, above which the solver holds the last value.
- Consequence: no N₂ run can be chemistry-trustworthy until these two tables are audited or rebuilt from Song et al. JPCRD 2023 Tables 10/5.

**Driver fix found by the N₂ smoke run:** Gaussian-B cases wrote `B_peak_minus_exit_m = NaN`, which is invalid JSON and aborted the output. It now reads 0: the Gaussian profile peaks at the exit plane by construction.

## 2026-09-26 — Reaction set abep-n2n-0.2: N₂ ionization rebuilt from Song et al. JPCRD 2023 Table 10

**Decision (owner):** rebuild the HallThruster-shipped N₂ tables from Song 2023 rather than audit them, because their cross-section inputs are not shipped. The rebuilt tables are new project-owned files. The shipped files stay in the repo for provenance.

**Change:**
- `ionization_N2_song2023.dat` is built from the Table 10 **partial σ(N₂⁺)** column (±5 %, 16–1000 eV) by `scripts/build_n2_ionization_song2023_table.py`. The transcription was checked row by row against the PDF text; the source has no 750 eV row.
- Explicit choices: σ = 0 below 16 eV; held above 1000 eV (tail share 0.96 % at 255 eV, so verified to 255 eV); header 15.58 eV (JPCRD Sec. 3).
- `n2_n.toml` now uses it. The reaction set moves `abep-n2n-0.1` → `abep-n2n-0.2` (`PINNED.toml` `[reaction_set]` version plus history). This is a reaction-set model change. No N₂ run had been scored, so no validated result moves.

**Why partial, not total:** the reaction produces N₂⁺ only. The total column also counts N⁺ + N₂²⁺ and N²⁺, which amounts to +5 % in rate at T_e = 7 eV and +25–31 % at T_e = 30–60 eV. **Known gap:** dissociative ionization (N₂ → N⁺ + N) and double ionization are not in the reaction set. Adding them is a separate owner decision.

**Diagnostic comparison, not used for tuning:** Song σ(N₂⁺) against the shipped HallThruster table. The bridge copy is byte-identical to the package file and to the 0-D model's `abep_sim/data/rates/ionization_N2_N2+.dat`.

| mean energy (eV) | 10 | 30 | 45 | 60 | 90 | 150 | 255 |
|---|---|---|---|---|---|---|---|
| k_Song / k_shipped | 1.000 | 1.000 | 1.000 | 1.000 | 0.997 | 0.975 | 0.903 |

- Up to 60 eV mean energy, the shipped table is reproduced to < 0.1 %. So it was built from the same Lindsay–Mangan / Itikawa partial cross section.
- Above that, the shipped rate is higher by up to 11 %. That points to a different, unknown high-energy tail treatment.
- Consequence for the 0-D chemistry: none. It still reads its own copy; the two chemistry databases stay separate (not unified).

## 2026-09-26 — Reaction set abep-n2n-0.3: N₂ elastic momentum transfer rebuilt from Song et al. JPCRD 2023 Table 5

**Change:**
- `elastic_N2_song2023.dat` is built from Table 5 (elastic **MTCS**, Kawaguchi et al. recommendation, "a few percent"; 40 points, 0.001 eV–10 keV) by `scripts/build_n2_elastic_song2023_table.py`. The transcription was checked row by row against the PDF text.
- It is MTCS, not integral elastic, because HallThruster uses this rate as the electron–neutral momentum-transfer frequency.
- The held tail above 10 keV contributes nil, so the table is verified to 255 eV.
- Table 5 is sparse at 4–31 eV (points at 4.0, 10.9, 21.9, 30.7 eV). The linear-in-E interpolation is ours; log-log would lower the rate by ≈ 2 % (a transformation uncertainty, not applied).
- `n2_n.toml` now uses it. The reaction set moves `abep-n2n-0.2` → `abep-n2n-0.3`. The shipped `elastic_N2.dat` is kept for provenance but is unused.

**Diagnostic, not used for tuning:** rate ratios against the shipped `elastic_N2.dat`.

| mean energy (eV) | 1 | 3 | 10 | 15 | 30 | 45 | 60 | 90 | 100 |
|---|---|---|---|---|---|---|---|---|---|
| Song MTCS / shipped | 1.007 | 1.041 | 0.963 | 0.908 | 0.817 | 0.769 | 0.730 | 0.652 | 0.627 |
| Song integral elastic (Table 4) / shipped | — | 1.10 | 1.20 | 1.26 | 1.39 | 1.50 | 1.58 | 1.66 | 1.66 |

- The shipped table matches neither the Song MTCS nor the Song integral elastic cross section. It lies between them, so its origin remains unknown.
- In the Hall range, electron–N₂ momentum transfer is now 18–27 % lower (mean energy 30–60 eV) than in 0.1/0.2. That is a real change to classical cross-field mobility in N₂ runs. Nothing validated moves: no N₂ run has been scored.

**Smoke test (N1, 0.5 ms):**
- It used the 0.3 set minus the not-yet-built excitation and N-elastic reactions, via an uncommitted temporary config.
- All four tables are verified, and f_out = 0 for every reaction. The limiting file is dissociation: active up to 35.7 eV mean energy against its 45 eV limit. `chemistry_trustworthy` = true.
- **This is not a validation-grade run:**
  - `chemistry_trustworthy` certifies the validity domains of the tables used, not completeness.
  - Completeness is enforced separately: the driver refuses `n2_n.toml` while any listed rate file is missing.
  - The P5-N₂ pre-registration must require the complete reaction-set version.

**Remaining N₂/N gaps:**
- the 8 excitation reactions and N elastic, both blocked on source access;
- dissociative/double ionization, rotational/vibrational excitation (not in the set; owner decision).

## 2026-09-26 — abep-n2n-0.2 + 0.3 merged (PR #19); N₂ reaction-set completeness criterion

**Merged:** PR #19, with the two separate commits (0.2 ionization, 0.3 momentum transfer). The shipped elastic table's origin stays **unresolved**; no origin is inferred for it.

**Completeness decision (owner):** "every file referenced by n2_n.toml exists" is not the same as "physically complete enough for validation". The processes are staged by physical importance:

| tier | processes | rule |
|---|---|---|
| 1 | 8 N₂ electronic-excitation channels; atomic-N momentum transfer | required before P5-N₂ scoring |
| 2 | N₂ vibrational excitation; dissociative ionization (N₂ → N⁺ + N) | must be assessed before the set is called complete; can materially change the electron-energy or species balance |
| 3 | rotational excitation; double ionization | explicit "assessed / not included" list unless a bounding calculation shows a non-negligible contribution |

**Criterion:**
- Every omitted process is bounded by its maximum fractional contribution, over the intended T_e range, to electron energy loss P_e and to species production/destruction S_s.
- Any process above a threshold (likely 1–2 %) is promoted into the model.
- The threshold is pre-registered **before any P5-N₂ fit quality is seen**. `PINNED.toml` stays INCOMPLETE until the audit is done.

**Sequence:** 8 × N₂* excitation → N momentum transfer → omitted-process importance audit → reaction-set completeness decision → P5-N₂ pre-registration.

**Pre-registration (2026-09-26, before any P5-N₂ scoring):** `hallthruster_bridge/prereg/n2_completeness_audit_v1.json`.
- **Domain:** T_e = 2–30 eV (mean energy 3–45 eV). The upper limit is the tightest verified table (dissociation). Vibrational and rotational excitation use T_e = 0.2–30 eV.
- **Rule:** promote if F_P > 0.01 (share of total electron inelastic power) ∨ F_ion > 0.01 (share of total positive-ion production) ∨ F_S_s > 0.05 (share of any modeled species' production or destruction), anywhere in the domain.
- **Denominators:** the best currently available included set. Verdicts made before the 8 excitation and the vibrational channels exist are provisional.
- A test pins these values.

## 2026-09-26 — Omitted-process audit 1 (provisional): N₂ dissociative ionization → PROMOTE

This audit was run under `prereg/n2_completeness_audit_v1` (merged in PR #20 before any P5-N₂ scoring). The script is `scripts/audit_n2_dissociative_ionization.py` and the result is `hallthruster_bridge/audit/n2_dissociative_ionization_v1.json`. It is provisional: the denominators are abep-n2n-0.3 without the excitation and vibrational channels. That over-estimates F_P; F_ion is unaffected.

**Inputs.** JPCRD 2023 Table 10:
- σ(N⁺ + N₂²⁺), 38 points from 30 eV. N₂²⁺ can't be separated from N⁺ by mass, so the column is an upper bound on single dissociative ionization.
- σ(N⁺⁺), 30 points from 70 eV.
- Both were checked row by row against the PDF text.

**Brackets on the dissociative-ionization rate and fractions.**
- Threshold: E_th = D₀(N₂) + IE(N) = 9.75 + 14.534 = 24.284 eV.
- Cross section:
  - *table*: σ = 0 below 30 eV, as published;
  - *envelope*: σ held at its 30 eV value from E_th. This is an over-estimate only, not a threshold shape.
- Energy loss per event: from E_th up to E_th + 16 eV. The 16 eV is kinetic-energy release, twice the largest N⁺ kinetic-energy peak of 8 eV.
- Ions per event: 1 to 2.
- Atomic fraction: n_N/n_N₂ = 0. Atomic N only adds to the denominators, so this maximizes the fractions.

**Results, lower / upper bound:**

| T_e (eV) | 3 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|
| F_P | 0.24 % / 1.2 % | 1.8 / 4.5 % | 8.1 / 15 % | 18 / 31 % | 24 / 40 % |
| F_ion | 0.43 / 2.6 % | 2.6 / 7.8 % | 9.7 / 21 % | 19 / 40 % | 25 / 50 % |

- **Verdict: PROMOTE.** Promotion is already forced by F_ion, which is independent of the still-incomplete excitation/vibrational power denominator. Its lower bound exceeds 1 % from T_e ≈ 4 eV. F_P is provisional and will be recomputed after the reaction set is complete.
- Removing an N₂²⁺ share of about 1 % of total ionization from the column changes the lower-bound F_ion at 30 eV only from 24.7 % to 23.5 %.
- Species-specific shares:
  - F_S(N₂ destruction) up to 14 %.
  - F_S(N production) up to 14 %.
  - Dissociative ionization supplies > 5 % of N⁺ production unless n_N/n_N₂ exceeds x_crit: about 1.6 at T_e = 7.5 eV, 5 at 20 eV and 6.3 at 30 eV.

**Tier-3 side results.**
- N⁺⁺ production crosses F_ion = 1 % at T_e ≥ 25 eV with one ion per event, or ≥ 19.5 eV with two. By the pre-registered rule it is also flagged.
- Implementing it needs an N²⁺ species, since N `max_charge` is currently 1. How to handle that is the owner's call.
- N₂²⁺ has no recommended data: JPCRD says it is about 1 % of total ionization and that measurements disagree. It stays **unresolved**.

**Implementation note for the promotion.** HallThruster.jl supports dissociative ionization through `electron_impact` equations (`PINNED.toml`, molecular_support). The table would come from the same Table 10 column. Two choices for the owner:
1. How to treat 24.28–30 eV: the table as published versus a documented threshold treatment.
2. The header energy loss: threshold versus threshold plus kinetic-energy release.

## 2026-09-26 — Reaction set abep-n2n-0.4: N₂ dissociative ionization added (promoted by audit 1)

**Table.** `scripts/build_n2_dissociative_ionization_table.py` builds from Table 10 σ(N⁺ + N₂²⁺). Owner decisions:
- Nominal: a linear ramp from σ = 0 at E_th = 24.284 eV up to the published 30 eV point.
  - Sensitivity bounds (not tables): zero below 30 eV, and σ(30 eV) held down to E_th.
  - Their rate effect is −42/+75 % at T_e = 3 eV, −4/+4 % at 10 eV, and < 1 % from 20 eV.
- Header energy loss 24.284 eV (the appearance energy). No fixed kinetic-energy add-on.
  - Sensitivity: charging +16 eV of fragment kinetic energy per event would add 1.4 % (T_e 5 eV), 5.1 % (10 eV), 10 % (20 eV) and 13 % (30 eV) to P_e (0.4 set, excitation not yet in).
  - That is material. It is the case for energy-dependent reaction losses if HallThruster ever supports them.
- Held tail above 1000 eV: < 0.76 % of the rate at 255 eV, so verified to 255 eV.

**The N⁺/N₂²⁺ ambiguity is carried explicitly, not resolved silently.**
- **upper** (`n2_n.toml`): the published column.
- **lower** (`n2_n_di_lower.toml`): the column minus 0.01 σ_total. This applies JPCRD Sec. 2.8's "N₂²⁺ ≈ 1 % of total ionization" at all energies (statement-derived, approximate).
- The variant config is generated and differs in exactly one line; a test enforces this.
- Molecular N₂²⁺ remains a separate, **unresolved** channel.

**Smoke test (N1, 0.5 ms, reaction subset without excitation or N elastic).**
- Loads and runs; chemistry_trustworthy; dissociation is still the limiting file (35.3 eV active vs 45).
- The atomic share of exit ion flux rises from 0.42 (0.3) to 0.53 (0.4). This is a chemistry diagnostic, not a fit comparison.

**Hygiene.** Smoke-test case copies now omit `measured`, so the driver computes no P5-N₂ target comparison before the pre-registration.

## 2026-09-26 — Reaction set abep-n2n-0.5: N²⁺ promoted; sequential ionization N⁺ → N²⁺ (Bell et al. 1983)

**Change:**
- N `max_charge` 1 → 2, because audit 1 promoted N²⁺ production: the N⁺⁺ column crosses F_ion = 1 % inside T_e ≤ 30 eV.
- New `ionization_N_Z1plus_to_N_Z2plus.dat`, from Bell, Gilbody, Hughes, Kingston & Smith, JPCRD 12, 891 (1983). Eq. (1) is used with the Table 5 N II parameters, ±10 %.
  - The parameters were read from the page image of the NIST-hosted reprint; the OCR had dropped a sign in the N I row.
  - Formula check: Bell's N I row reproduces NIST Kim & Desclaux (30 % ²D mix, i.e. the Brook beam Bell follow) to 1–5 % from 30 eV to 1 keV.
  - The N II curve peaks at 0.51×10⁻¹⁶ cm² near 118 eV. Header 29.60125 eV (IE(N II), NIST ASD).
- This reaction is structurally required: HallThruster.jl derives species energies only through one-to-one reactions, so N²⁺ cannot load without an N⁺ → N²⁺ (or N → N²⁺) link. It is also the sequential N²⁺ source route. It is included, not only bounded; its importance relative to the direct N₂ → N²⁺ + N route is evaluated when that route is added (0.6).

**Driver fixes found by the 0.5 smoke run:**
- The chemistry guard assumed neutral targets and split equations on a bare "+". `reactant_term` / `reactant_density` now parse `N(+)` / `N(2+)` and read the matching ion density per frame (checked in `checks/chemistry_validity_check.jl`).
- Ion-velocity profile keys are now `profile_ui_<sym>_Z<Z>_ms`. The old `N21+` (N₂, Z = 1) vs `N2+` (N, Z = 2) naming was ambiguous. Historical output files keep the old keys.

**Smoke test (0.5 minus excitation and N elastic).** Loads and runs with an N Z = 2 fluid. All six tables have f_out = 0; chemistry_trustworthy.

**Omitted routes to bound later:** direct N → N²⁺ and N²⁺ → N³⁺ (tier 3).

## 2026-09-26 — Reaction set abep-n2n-0.6: direct N₂ → N²⁺ + N; sequential-route audit

**Change:**
- New `dissociative_ionization_N2_to_N_Z2plus.dat` from Table 10 σ(N⁺⁺), the total N⁺⁺ yield from N₂. The extra N⁺ produced by triple events is not added.
- Same threshold rule as single dissociative ionization: a linear ramp from σ = 0 at E_th = D₀ + IE(N I) + IE(N II) = 53.885 eV to the 70 eV point. Header 53.885 eV.
- Tail 0.95 % at 255 eV, so verified to 255 eV.
- Threshold sensitivity (table/envelope vs ramp): −10/+16 % at T_e = 10 eV, < 2 % from 20 eV.

**Sequential vs direct N²⁺ route.** The route is included, not merely bounded.

| T_e (eV) | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| k_direct (N₂ → N²⁺) [m³/s] | 3.0e-18 | 4.1e-17 | 1.7e-16 | 3.9e-16 | 7.2e-16 |
| k_seq (N⁺ → N²⁺) [m³/s] | 6.7e-16 | 2.4e-15 | 4.6e-15 | 6.9e-15 | 9.2e-15 |
| n_N⁺/n_N₂ where seq = 5 % of direct | 2.2e-4 | 8.7e-4 | 1.8e-3 | 2.9e-3 | 3.9e-3 |
| n_N⁺/n_N₂ where seq = direct | 0.45 % | 1.7 % | 3.6 % | 5.7 % | 7.8 % |

- The sequential route passes the 5 % species criterion at ion-to-N₂ ratios of order 10⁻³.
- Once the ion fraction exceeds a few percent, which is typical of a Hall ionization zone, it is the dominant N²⁺ source.
- Leaving it out would have been a material omission.

**Smoke tests (0.6 minus excitation and N elastic).**
- Both variants run: upper `n2_n.toml` and lower `n2_n_di_lower.toml`.
- f_out = 0 for every table; chemistry_trustworthy.
- Atomic exit-ion-flux share: 0.537 upper vs 0.533 lower. This is a chemistry diagnostic only.

**Still to bound (tier 3):** direct N → N²⁺, and N²⁺ → N³⁺. Molecular N₂²⁺ stays unresolved.

## 2026-09-26 — Omitted-process audit 2: N₂ vibrational excitation → PROMOTE (not yet included)

**Data:** the set JPCRD 2023 recommends, Laporta, Little, Celiberto & Tennyson, PSST 23, 065002 (2014), obtained via arXiv:1402.3814 (green OA). Its IOP supplementary files were downloaded directly.
- They hold Eq. (10) rate fits, κ(T) = κ_max (T_max/T)^{3/2} e^{−T_max/T}, for v = 0 → v_f = 0…58, with level energies from Table II.
- Eq. (10) was read from the rendered page. Note that κ_max is a fit parameter, not the peak: the fit peaks at 0.41 κ_max at T = 2T_max/3.
- Units (10⁻⁹ cm³/s) were confirmed independently: the 0→1 fit reproduces the Maxwellian integral of JPCRD Table 7's recommended σ₀₁ to 1–6 % at T = 0.5–3 eV.
- The Laporta rates are resonant only (integrated to 15 eV) and from v = 0 only, so the vibrational power is a lower bound.

**Denominator:** abep-n2n-0.6 upper inelastic power, plus Su et al. 2021's 8 electronic channels (σ = 0 above 20 eV) with the owner's experimental energy losses. The electronic channels are trusted in the denominator where the Maxwellian flux above 20 eV is ≤ 1 %, i.e. T_e ≤ 3 eV. This is the presently completed denominator, not a complete one: rotational excitation and the remaining omitted channels are not yet bounded.

| T_e (eV) | 0.5 | 1 | 2 | 3 | 5 | 7.5 | 10 | 20 | 30 |
|---|---|---|---|---|---|---|---|---|---|
| P_vib / (P_incl + P_elec) | 1.7e5 | 155 | 2.5 | 0.41 | 0.064 | 0.017 | 0.0071 | 0.0010 | 0.00035 |

- **Verdict: PROMOTION ROBUST.** It exceeds the pre-registered criterion by a large margin over the low-T_e domain, using the presently completed denominator. Final completeness of the reaction set remains pending the remaining omitted-process bounds. Vibrational excitation is the dominant electron energy sink at T_e ≤ 2 eV and exceeds 1 % up to T_e ≈ 9 eV.
- Power by final level: v_f = 1 carries only ~22 %, v_f ≤ 4 about 77 %, and v_f ≤ 10 about 99.9 % (T_e = 1–10 eV). Implementation therefore needs overtones: one fixed-energy excitation reaction per v_f = 1…10, header ε_vf.

**Residual sanity bound** (TCS − elastic ICS − known inelastic, rate space; a diagnostic only). No pass/fail tolerance is applied, since none was pre-registered.
- The residual is **negative** at T_e ≤ 0.3 eV: the datasets are inconsistent there, as expected.
- Σk_vib / k_res is 1.14 at 0.5 eV and 1.01 at 0.7 eV (the residual is a small difference of 10–20 %-uncertain sets), and 0.93 → 0.08 from 1 to 30 eV.
- So the residual cannot serve as a vibrational dataset.

**Data licences:**
- Laporta: IOP copyright. The committed data are 59 transcribed fit-parameter pairs plus 59 level energies (factual data, cited); the supplementary file itself is not committed.
- Su 2021: CC BY 4.0, fetched at run time from IOP (or `--su-dir`).

## 2026-09-26 — Nomenclature: atomic N²⁺ is `N_Z2plus` (owner decision)

Molecular N₂⁺ and atomic N²⁺ now coexist, so "N2+" in names was ambiguous. "N2+" always means molecular N₂⁺. Atomic N²⁺ is written `N_Z2plus`, and atomic N⁺ `N_Z1plus`, in filenames, scripts, comments and metadata. The HallThruster equations such as `N(2+)` were already unambiguous. The molecular dication N₂²⁺ is not modelled.

Renames (the file contents and rates are unchanged; the files were never on main under the old names, and the log entries above were updated to match):
- `ionization_N+_N2+.dat` → `ionization_N_Z1plus_to_N_Z2plus.dat`
- `dissociative_ionization_N2_N2+.dat` → `dissociative_ionization_N2_to_N_Z2plus.dat`
- `scripts/build_n_plus_ionization_table.py` → `scripts/build_n_z1plus_to_z2plus_table.py`
- `scripts/build_n2_to_n2plus_table.py` → `scripts/build_n2_to_n_z2plus_table.py`

## 2026-09-26 — Reaction set abep-n2n-0.7: N₂ vibrational excitation v = 0 → 1…10 (validity limit: owner decision pending)

**Merged:** PR #22 (0.4–0.6, audit 2, nomenclature, wording).

**Change:** ten fixed-energy excitation reactions e + N₂(v=0) → e + N₂(v_f), v_f = 1…10, built by `scripts/build_n2_vibrational_tables.py`.
- **Rates:** Laporta Eq. (10) rate coefficients, used directly (nothing is integrated). The table row at mean energy ε̄ holds k(T_e = ⅔ ε̄). A regression test also checks that the wrong reading, T_e = ε̄, differs.
- **Headers:** ε_vf from Laporta Table II.
- **Why ten:** the omitted v_f = 11…58 tail is at most **0.145 %** of the vibrational power anywhere in T_e = 0.2–30 eV, hence below 0.145 % of P_e and the 1 % criterion. Ten is a result, not a choice.

**Closure uncertainty for P5-N₂ (not a complete vibrational kinetics model):**
- HallThruster does not track vibrational populations, so all N₂ is taken in v = 0.
- There is no stepwise v_i > 0 excitation and no superelastic return; the model represents gross electron cooling.
- Resonant excitation only (Laporta's cross sections integrated to 15 eV); non-resonant excitation is absent.

**Validity domain — needs an owner decision.**
- Laporta state no validated temperature range for the vibrational-excitation fits. Fig. 5b shows the calculated rates up to 50,000 K (4.31 eV) without a fit overlay; only the dissociation fits are compared with calculations (Fig. 7, up to 100 eV).
- Following "use the source's fit domain", the limit carried is **6.47 eV mean energy (T_e = 4.31 eV)**.
- Consequence: in the N1 smoke run (0.7 minus the missing files) 83–86 % of each vibrational channel's activity lies above that limit, so the run is not chemistry-trustworthy. **No P5-N₂ run can be chemistry-trustworthy with this limit.**
- Evidence relevant to extending it:
  1. For the 0→1 channel, the Eq. (10) fit matches an independent Maxwellian integral of JPCRD 2023 Table 7 σ₀₁ (1–5 eV) to within 6 % from T = 0.5 to 30 eV (ratios 0.97–1.06). Below that it degrades: 0.40 at T = 0.2 eV.
  2. Eq. (10)'s T^(−3/2) high-T form is the exact Maxwellian limit for a cross section confined to low energy, which the resonant cross section is.
  3. The same check cannot be made for the overtones, because no cross sections for them are in hand.
- Only the upper limit is guarded. The 0.2–0.5 eV fit degradation matters only below the Hall range.

## 2026-09-26 — Reaction set abep-n2n-0.8: atomic-N momentum transfer (Ragimkhanov 2026; Wang 2014 BSR variant)

**Source access:**
- Ragimkhanov et al., EPJD 80, 69 (2026), CC BY 4.0, was served by Springer as a PDF to a plain, honestly identified client (sha256 47489e8a…). No browser or trust-store change was involved.
- Johnson 2005's Wiley supporting-information file (`jgra18077-sup-0001-t01.txt`) is still behind the Wiley bot challenge (HTTP 403 on all three supplement URL forms). Tier-1 electronic excitation stays open.

**Extraction:**
- The paper states its data are available only graphically. Fig. 1b (electron MTCS, a₀², log-log) is vector artwork.
- The present OPM curve (solid red, 2,040 path points, 1 eV–1 MeV) and the "Wang et al. (B-spline R-matrix)/2014" comparison curve (green dashed, 0.95–128 eV) were extracted from the path coordinates.
- Calibration is on the plot frame (edges = 10⁰/10⁶ eV and 10⁻⁷/10² a₀² ticks). The tick labels centre within 0.03 pt of the frame-derived positions: 0.1 % in E, 0.5 % in σ.
- The points are committed as `propellants/sources/ragimkhanov2026_fig1b_mtcs.csv`, with CC BY attribution.

**Disagreement, carried rather than resolved (owner rule):**

| | 1 eV | 3 | 5 | 10 | 20 | 23 | 30–60 | 100–128 |
|---|---|---|---|---|---|---|---|---|
| σ_OPM / σ_Wang | 0.15 | 0.40 | 0.52 | 0.59 | 0.89 | 1.00 | 1.15–1.19 | 0.80–0.88 |

| T_e (eV) | 2 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|
| k_OPM / k_Wang-variant | 0.36 | 0.56 | 0.74 | 0.90 | 0.96 |

- BSR resolves the low-energy structure (N⁻ resonance region); the optical-potential model does not aim to.
- Nominal `n2_n.toml` uses OPM, the committed primary source.
- Variants `n2_n_nel_wang.toml` and `n2_n_di_lower_nel_wang.toml` (generated) use Wang BSR, spliced to OPM above 128 eV. At T_e = 30 eV about 7 % of the Maxwellian flux lies above 128 eV.
- The Wang curve is a secondary reproduction; its fidelity to the primary PRA numbers is unverified (that paper is closed).

**Smoke test (N1, 0.8 minus the electronic-excitation placeholder).** Nominal and Wang variant both run. Neither is chemistry-trustworthy, solely because of the 0.7 vibrational validity limit, which awaits an owner decision.

**Run matrix implied for P5-N₂:** 2 dissociative-ionization variants × 2 N-elastic variants = 4 chemistry configs per transport candidate.

**Owner decision (2026-09-26), vibrational validity domain.** The 6.47 eV mean-energy limit is removed. It was taken from the highest temperature shown in a figure, not from a boundary the source states. Laporta publish the analytical fits without an upper cutoff, and JPCRD 2023 recommends them as the vibrational-rate representation.
- Project applicability is capped at the pre-registered N₂ domain, T_e ≤ 30 eV (45 eV mean energy).
- This is documented as source-model applicability, **not** experimental validation. 0→1 is independently cross-checked (≤ 6 % to 30 eV); v_f = 2…10 are model-supported only.
- `chemistry_trustworthy` = true means no reaction was evaluated outside its declared chemistry-model domain. It does not mean experimental confirmation.
- The more consequential limitations remain carried as closure uncertainty: v = 0 only, no vibrational population kinetics, no superelastic return.

## 2026-09-26 — PR #23 merged; reaction set abep-n2n-0.9: eight N₂ electronic excitations (n2_n.toml now file-complete)

**Merged:** PR #23 (0.7 + 0.8 + the vibrational applicability correction).

**Data:**
- Su et al. 2021 supplementary files (CC BY), committed unmodified under `propellants/sources/su2021/`.
- Johnson et al. 2005 Table 2 (8-state ICS, 10–100 eV; a¹Π_g also at 200 eV; 10⁻¹⁸ cm² with uncertainties). The owner transcribed it from the Wiley article page and it is committed as `sources/johnson2005_table2_ics.tsv`. The file the article exposes as `…-t01.txt` is Table 1 (a¹Π_g DCS at 200 eV), not the ICS table.
- Yonker & Bailey 2020 could not be located from here, so it is not used.

**Construction** (`scripts/build_n2_electronic_excitation_tables.py`):
- Su below 20 eV; Johnson's points exactly from 20 eV.
- No renormalization and no −1.5 eV shift.
- Headers are the experimental vertical energies (7.75, 8.04, 8.88, 9.67, 9.31, 9.92, 10.27, 11.19 eV).
- Above Johnson's last point: a documented power law σ_last (E/E_last)^−p, with p from the last two points: A 2.29, B 2.87, W 2.25, B′ 2.23, a 1.07, a′ 1.67, w 0.53, C 2.47.
- The triplets fall steeply (towards the E⁻³ exchange limit); the singlets slowly.
- A normalization bug (anchoring at 10 keV instead of the last point) was caught in development; a test now pins the anchoring.

**Diagnostics:**

| state | A | B | W | B′ | a | a′ | w | C |
|---|---|---|---|---|---|---|---|---|
| Su/Johnson step at 20 eV | 1.83 | 1.17 | 1.09 | 1.12 | 0.84 | 1.51 | 1.34 | 2.13 |
| continuation share of rate, T_e 30 eV | 1.5 % | 0.7 | 1.2 | 1.4 | 0.2 | 2.4 | 6.7 | 1.0 |

- Across the 10–20 eV overlap, Su/Johnson ranges from 0.59 to 3.8 (e.g. w¹Δ_u 3.8 at 12.5 eV, W 3.2 at 10 eV). This is genuine evidence disagreement and is recorded, not smoothed.
- At rate level, a Johnson-below-20 eV alternative (ramp from the experimental threshold to Johnson's first point) gives 0.81/0.80/0.81/0.86/0.91/0.94 of the nominal total electronic power at T_e = 2/3/5/10/20/30 eV.
- Carrying that alternative as a chemistry variant is an owner decision; it would double the configs to 8.
- Zero/hold tail bounds on the continuation: within −6.7/+1.2 % (w¹Δ_u widest).

**n2_n.toml is file-complete for the first time:** 26 reactions, the lumped `excitation_N2.dat` placeholder removed.
- Full-set N1 smoke run (0.5 ms, no measured targets): loads, runs and is chemistry-trustworthy. The limiting file is dissociation (36.2 of 45 eV).
- The combined variant `n2_n_di_lower_nel_wang.toml` gives the same verdict.
- `PINNED.toml` stays INCOMPLETE (owner rule). Remaining: the tier-3 bounds (rotational excitation, N → N²⁺ direct, N²⁺ → N³⁺), then re-running audits 1–2 with the complete denominators.

## 2026-09-26 — PR #24 merged; omitted-process audit, final pass on abep-n2n-0.9 (`audit/n2_completeness_final_v1.json`)

**Merged:** PR #24 (0.9). Denominators are built from `n2_n.toml` itself: every N₂-target inelastic reaction, rate times header energy, with x_N = 0.

| process | result | verdict |
|---|---|---|
| dissociative ionization (included 0.4) | final F_P max 17.4 %, F_ion max 19.6 % (T_e ≤ 30 eV) | promoted, final |
| vibrational excitation (included 0.7) | final F_P up to 99.98 % at T_e ≤ 1 eV, > 1 % up to ~9 eV | promoted, final; model-form limits unchanged |
| rotational excitation (tier 3) | gross from j = 0: ceiling bound (10 meV, σ held at its max) 3.5 %; **spectroscopic** (NIST B₀ = 1.98958 cm⁻¹: 0→2 = 1.480 meV, 0→4 = 4.933 meV; σ held at the 10 eV value) **1.13 % max at T_e 1–2 eV** | **PROMOTE (marginal)**. Same gross convention as the vibrational verdict; the net loss (kT_gas ≫ ΔE) would be far smaller. Owner may reverse |
| N²⁺ → N³⁺ (tier 3, Bell N III row) | x_crit (n_N²⁺/n_N₂ for F_ion = 1 %) ≥ 0.25 over T_e ≤ 30 eV; reference state max ratio 1.2×10⁻³; F_ion 4.7×10⁻⁷; F_S(N²⁺ destruction) 2.1×10⁻⁴ | **EXCLUDED** (margin ~200) |
| N → N²⁺ direct (tier 3) | no cross-section source | **UNRESOLVED-BY-SOURCE** (not inferred or scaled) |

- The reference state is the full-set N1 smoke run (0.5 ms, default transport, no measured targets).
- The driver now writes ion density profiles (`profile_ni_<sym>_Z<Z>_m3`).

## 2026-09-26 — Reaction set abep-n2n-0.10: rotational excitation (marginal promotion)

Two excitation reactions, j = 0 → 2 and 0 → 4, built by `scripts/build_n2_rotational_tables.py`:
- Cross sections from JPCRD 2023 Table 6 (0.01–10 eV), held at the 10 eV value above.
- Headers 1.480 meV and 4.933 meV (NIST B₀).
- Gross loss from j = 0 with no superelastic return. This deliberately over-states net rotational cooling, consistent with the vibrational closure.

The full 28-reaction N1 smoke run is chemistry-trustworthy.

This inclusion follows the pre-registered rule literally (gross F_P 1.13 % > 1 %). If the owner decides the net (detailed-balance) loss is the relevant quantity, it is reversible as a documented model change.

## 2026-09-26 — Johnson-low sensitivity branch (sequential design, owner decision)

- `excitation_N2_<state>_johnsonlow.dat` use Johnson 2005 at all energies, with a linear ramp from σ = 0 at the experimental energy to Johnson's first point and the same power-law continuation.
- The generated config `n2_n_exc_johnsonlow.toml` (nominal DI, OPM N elastic) differs from `n2_n.toml` in exactly those eight files; a test enforces this.
- Its N1 smoke run is chemistry-trustworthy.

**Run design:**
- Primary: 4 chemistry configs × 9 transports = 36 runs.
- Johnson-low: × 9 transports = +9 runs.
- Escalation to the full 72 only if the trigger fires. The trigger's definition of "materially" is fixed in the P5-N₂ pre-registration from the audited measurement uncertainties, not a generic number.

## 2026-09-26 — Closure pass (owner decisions): rotational kept; rotational-off branch; status CLOSURE_PENDING; N₂²⁺ envelope; blind state envelope

- **Rotational:** 0.10 stays promoted. The pre-registered F_P is gross; redefining it as net after seeing 1.13 % would be a post-hoc metric change.
  - The generated `n2_n_rot_off.toml` (the two rotational reactions removed; nominal DI, OPM N elastic) is the lower-bound closure.
  - Run design: rotational-off × 9 transports, factorialized only if it changes a validation conclusion.
- **Status:** `audit/n2_completeness_final_v1.json` is marked `CLOSURE_PENDING`. The DI and vibrational fractions are final; the overall completeness verdict is not.
- **Molecular N₂²⁺ envelope** (appearance energy 42.9 eV per the owner's citation of Märk 1975 — not read here, verify):

  | T_e (eV) | 5 | 10 | 20 | 30 |
  |---|---|---|---|---|
  | F_ion, nominal (σ = 1 % of σ_total, JPCRD statement) | 0.04 % | 0.30 % | 0.66 % | 0.79 % |
  | F_ion, upper (0.14×10⁻¹⁶ cm² flat = maximum total double ionization) | 0.34 % | 2.2 % | 4.2 % | 4.8 % |

  - A 40 eV threshold gives an upper bound of 5.1 %.
  - **Bracketed, not excludable by bound.** In ion-count terms the DI chemistry variants already bracket it: the upper variant counts N₂²⁺ events as N⁺, the lower removes them.
  - The primary Märk 1975 (AIP) and Phys. Rev. A 98, 052701 data are not accessible here. JPCRD Fig. 23 is raster.
- **Direct N → N²⁺:** Deutsch, Becker & Märk, PPCF 42, 489 (2000) is bronze OA, but IOP serves only a JavaScript-gated PDF route and an abstract-only landing page to this environment. Still unresolved-by-source.
- **Blind state envelope** (`checks/blind_state_envelope.jl`): 5 P5-N₂ points × 9 SGB candidates × 4 chemistry configs, with measured targets removed and only chemistry-state quantities recorded per saved frame (max n_N²⁺/n_N₂, reaction-weighted F_ion and F_S for N²⁺ → N³⁺).
  - Uses a bound-only Bell N III table in `audit/bound_tables/`.
  - The driver exposes `LAST_SOL` for check scripts; it is never used for scoring.
  - Running.

## 2026-09-26 — Pre-registration addendum 1: ambiguity rule (frozen before the full envelope summary)

`prereg/n2_completeness_audit_v1_addendum1_ambiguity.json` (owner decision):
- upper bound < threshold ⇒ **EXCLUDE**;
- lower bound > threshold ⇒ **PROMOTE** (nominal chemistry);
- lower < threshold < upper ⇒ **PROMOTE AS AN UNCERTAINTY VARIANT**. This means omission has not been shown harmless; it does not assert the upper-envelope physics.
- Bounds are taken over all nuisance choices (operating point, transport, chemistry). A verdict that flips with the nuisance choice is treated as the between-bounds case.
- Disclosure: early partial records had been seen in the session log. No full-envelope summary, maximum or range had been computed.
- On promotion, molecular N₂²⁺ requires both N₂ → N₂²⁺ and N₂⁺ → N₂²⁺, with N₂ `max_charge` = 2 and the species-energy link checked. Direct N → N²⁺ goes into nominal chemistry, with the Hahn–Müller–Savin uncertainty as a sensitivity.

### 2026-09-26 — Blind state envelope complete (5 P5-N₂ points × 9 SGB candidates × 4 chemistry configs; measured targets removed)
180/180 runs succeed; common metrics identical to an independent earlier batch (max rel. diff 6e-16). 100/180 are
`chemistry_trustworthy`. The 20 unsustained runs are sgb-screen-05 at N1–N4 and sgb-screen-09 at N1. The other 60 untrusted
runs are every run of sgb-screen-02/03/04, where `dissociation_N2.dat` activity extends beyond its 45 eV mean-energy limit
(T_e > 30 eV; share ≤ 3.1 % in the 5 reruns of untrusted cases). Omitted-process results (all runs / trusted only are the same
by verdict):
N²⁺→N³⁺ F_ion ≤ 1.3e-6, F_S ≤ 4.9e-4; direct N→N²⁺ (HMS 2017) F_ion 0.47–1.10 % (36/180 > 1 %, flips with candidate/point,
not with chemistry config), F_S(N²⁺ production) 63–85 % in all 180; N₂²⁺ F_ion sequential ≤ 0.25 %, nominal 0.28–0.54 %,
upper 1.26–2.73 % (all 180 > 1 %). Region reruns (argmax cases): N²⁺ channels weighted to T_e ≈ 19–25 eV, z/L ≈ 0.92–1.05,
n_e ≈ 0.4–1.7e18 m⁻³; N₂²⁺ channels T_e ≈ 16–20 eV, z/L ≈ 0.75–0.97. Verdicts under addendum 1 await the owner.
Records: `hallthruster_bridge/audit/blind_state_envelope_v1*.json[l]`.

### 2026-09-26 — Tier-3 closure; reaction set abep-n2n-0.11 COMPLETE_FOR_P5_N2_VALIDATION
Pre-registration addendum 2 (owner): earlier/later envelope run sets are an implementation cross-check, never averaged or
selected; the newest set is authoritative; a verdict-altering discrepancy blocks the rule. (It reached the session after the
v3/older-batch cross-check had been computed: identical, max rel. diff 6e-16; disclosed in the addendum.)
Authoritative v4 envelope (180 runs; adds the two N₂²⁺ routes separately, F_S(N₂⁺ destruction), and every file beyond its
validity limit). Process incident, resolved before any verdict: 72 v4 runs picked up the new 0.11 `n2_n.toml` mid-batch and
were refused by the chemistry guard (no validity entry); they were deleted and rerun from a clean worktree at the 0.10 configs.
All 2520 values common with v3 then agree exactly; no status differs.
Closure table (addendum 1 literally; L = min over runs of the lower bound, U = max over runs of the upper bound):
- direct N → N²⁺ (HMS 2017; no published band): F_S(N²⁺ production) 0.633–0.853 > 0.05 in every run → **PROMOTE** (the rate would
  have to fall ×33 to reverse); F_ion 0.47–1.10 % flips with transport and point, not chemistry. Region: T_e 19.7–24.9 eV, z/L 0.88–1.06.
- N²⁺ → N³⁺ (Bell ±10 %): U F_ion 1.5e-6 (frame max 1.1e-5), F_S 5.4e-4 → **EXCLUDE** (×97 margin). N²⁺/N₂ peaks at T_e 2.0–4.7 eV,
  while the N³⁺-channel activity is weighted to T_e 18.8–25.6 eV, far below its 47.45 eV threshold.
- N₂ → N₂²⁺ (nominal "~1 %" / upper all-double-ionization): F_ion nominal 0.17–0.39 %, upper ≤ 2.58 % → **UNCERTAINTY VARIANT**.
- N₂⁺ → N₂²⁺ (Tabata/Bahati, fit/data 0.86–1.11): F_ion ≤ 0.27 %, F_S(N₂⁺ destruction) ≤ 0.60 % → **EXCLUDE** from nominal; inside
  the N₂²⁺ variant it carries 4.5–55 % of N₂²⁺ production and supplies the energy link, so it is part of the variant.
Verdicts are identical on the 100 chemistry-trustworthy runs alone, and none changes with the chemistry configuration.
abep-n2n-0.11: `N + e -> N(2+) + 3e` (HMS Eqs. (2)+(3); header 44.1354 eV closes 14.534 + 29.601) in nominal; generated
variants `n2_n_ndd_hmslow/high.toml` (×0.5, HMS Sec. 3.7 neutral-O precedent; ×1.3, Sec. 3.19 "~30 %") and
`n2_n_n2dication.toml` (N2 max_charge 2; upper direct + Tabata sequential; on DI-lower so N₂²⁺ is not counted twice; sequential
header 27.32 = 42.9 − 15.58 because HallThruster.jl requires one consistent N₂²⁺ energy — the solver refused 15.58 + 27.9 ≠ 42.9).
Smoke runs (P5-N₂ N3, sgb-screen-01, targets removed) of n2_n, n2_n_n2dication, hmslow, hmshigh: converged, sustained,
chemistry-trustworthy; N₂²⁺ peak 1.3e16 m⁻³ in the variant. Build: `scripts/build_multiply_charged_tables.py` (also rebuilds the
audit bound tables byte-for-byte). Table: `scripts/n2_closure_table.py`. Status COMPLETE_FOR_P5_N2_VALIDATION; N₂ chemistry frozen.
Open for the P5-N₂ pre-registration (owner): all runs of sgb-screen-02/03/04 and 9 of sgb-screen-05 reach T_e > 30 eV, where every
45-eV-capped table (dissociation, electronic, vibrational, rotational) is used beyond its limit (≤ 4.1 % of dissociation activity);
they are not chemistry-trustworthy and cannot be scored as is.

### 2026-09-26 — PR #25 review: historical audits pinned to immutable config snapshots (P1, P2)
Review finding P1: `checks/blind_state_envelope.jl` read the mutable production TOMLs. At 0.11 they contain the promoted HMS
reaction, so a rerun would both count it twice (F_S capped at 0.5) and generate the plasma state with it present.
Review finding P2: `scripts/audit_n2_completeness_final.py` read the mutable `n2_n.toml`. Since 0.10 it contains the rotational
reactions, so `rot_bound()` was added to a denominator that already held rotation.
Fix: immutable snapshots in `hallthruster_bridge/audit/configs/` (0.9 pre-rotation from 32a919a; the four 0.10 pre-HMS configs from
763026a), sha256-pinned together with every rate table they name (`MANIFEST.json`, test). The envelope refuses a config that
already contains an assessed process; the final audit refuses a denominator containing rotation.
Evidence regenerated from the snapshots, not argued indirectly:
- Blind envelope, full 180-run rerun: reproduces the committed authoritative records exactly (5829 values, max rel. diff 0, no
  status, trust or beyond-limit difference); the closure table `n2_closure_verdicts_v1.json` regenerates byte-identical; verdicts
  unchanged. The committed records were valid (produced on the 0.10 TOMLs before promotion), but the PR head could not reproduce them.
- Final tier-2/3 audit: the commits 6c9af2a and 653e074 had silently regenerated `n2_completeness_final_v1.json` on the 0.10
  denominator (rotation counted twice) while still labelled 0.9. Recorded, not replaced silently:
  | quantity | 0.9 (correct; 32a919a and now) | double-counted (6c9af2a, 653e074) |
  |---|---|---|
  | rotational F_P, spectroscopic max | 1.1306 % | 1.1182 % |
  | rotational F_P, ceiling max | 3.528 % | 3.492 % |
  | vibrational F_P max | 99.984 % | 99.126 % |
  | DI F_P max | 17.443 % | 17.440 % |
  All 16 rows now equal the 32a919a rows on every original column; the N₂²⁺ / N²⁺→N³⁺ columns do not involve rotation and are
  unchanged. Every verdict is the same under the frozen thresholds (rotation still 1.13 % > 1 % → promoted).
P5-N₂ run statuses frozen (`prereg/p5_n2_run_status_rule_v1.json`, owner decision): PASS / FAIL_VALIDATION / OUT_OF_DOMAIN /
NUMERICAL_FAILURE. Chemistry-untrustworthy runs are OUT_OF_DOMAIN, not FAIL. A candidate needs scoreable runs at every point under
the four primary chemistry configs; otherwise it is INCONCLUSIVE / not eligible for promotion in this campaign. f_out = 0 is not relaxed.

### 2026-09-26 — P5-N₂ measurement audit (before the validation pre-registration; nothing simulated or scored)
PR #25 merged (4231331); N₂ chemistry frozen (abep-n2n-0.11 COMPLETE_FOR_P5_N2_VALIDATION). Audit of Brabston et al. JPP 2025
(Table 2, Table 5, Figs. 5, 8, 9, 10) with a reproducible digitizer (`scripts/audit_p5_n2_measurements.py`, PDF sha256-checked,
not redistributed; calibration residuals ≤ 0.26 mN / 0.002 kW in Fig. 5 and ≤ 0.0004 in Figs. 8–10; validated on the Fig. 5 Xe
markers, which reproduce the Eq. 14 powers to ≤ 3 W). Values: `identification/brabston_p5_n2_measurement_audit_v1.json`;
classification, findings F1–F7 and open decisions D1–D6: `identification/p5_n2_measurement_audit_findings_v1.json`.
- Admissible targets (independent of any chemistry model): I_d at N1–N5 (raw inferred; Eq. 14 corrected), thrust at N1–N5
  (±2.6 mN; N1/N5 abstract, N2–N4 Fig. 5), E×B species acceleration voltages at N1–N3 (N₂⁺ 166–179 V, N⁺ 210–244 V, ±11.6 V),
  sustained discharge at all five points.
- Not targets: Φ_m,n, η_SP,n, ξ_N (the paper's own Itikawa/Cosby approximation), Isp/η_T (restated), Ω_i,n (unpublished).
- Findings: Fig. 5 N₂ powers ~43 W below Eq. 14 (a plotting offset; Fig. 8 follows Eq. 14); component vs thrust η_T differ
  2/13/19 % at N1/N2/N3, so divergence readings A/B differ up to 11 % in axial factor; no divergence or species data at N4/N5;
  xenon cathode flow 8 % of anode flow unmodelled; 130 G field shape unpublished; `cases/p5_n2.json` must be regenerated like
  the Xe cases before any run.

### 2026-09-26 — P5-N₂ validation pre-registration (owner decisions D1–D6; operational details O1–O5 pending)
Measurement audit merged first as its own PR (#26, 60a0c90): evidence frozen → criteria → results.
`prereg/p5_n2_validation_criteria_v1.json` (owner decisions): primary I_d at N1–N5 (±15 %), thrust at N1–N3 (±5.2 / 5.6 / 5.6 mN;
T_axial = T_1D × f_reading), sustainment at N1–N5; E×B V_a,n non-gating; N4/N5 thrust unscored (no divergence invented);
vacuum primary (admission), facility secondary, never crossed; layer-1 = 3 registrations × 2 coil shapes (scaled to 130 G) × 2
divergence readings, fixed globally across the series and across the four mandatory chemistry configs; admission iff one
layer-1 member passes every primary criterion at every point under every mandatory chemistry. Inputs sha256-pinned.
`prereg/p5_n2_run_status_rule_v1_addendum1_extinction.json`: a numerically valid extinction at an experimentally sustained point
is FAIL_VALIDATION / SUSTAINMENT (reasons CURRENT / THRUST / SUSTAINMENT); amended after the audit and the blind envelope, before
any scoring, disclosed in the file.
Proposed operational details, not frozen until the owner confirms: O1 extinction definition (distinguishes a dead discharge from the
schema's bookkeeping `sustained` flag), O2 status precedence and a sustained-independent chemistry-domain test, O3 member/candidate
verdict aggregation, O4 staged-sensitivity escalation trigger (status/verdict change, or ≥ 7.5 % I_d / ≥ 2.6 mN), O5 model E×B
observable.
`cases/p5_n2.json` regenerated by `scripts/make_p5_n2_cases.py` (30 cases, targets only from the frozen audit); the previous file
is kept as the immutable blind-envelope snapshot `audit/configs/p5_n2_cases_blind_envelope_v1.json` and the envelope now reads
it. Construction check (2 µs runs, targets stripped, field quantities only): all six registration × coil builds succeed; B at the
exit = 130 G, in-channel peak 131–149 G (same exit-scaling convention as Xe).
**Operational rules frozen (owner, same day):** O2, O3, O5 confirmed (O5 adds the standardized residual ΔV_a/11.6 V and the
species' outlet ion flux beside each value); O1 amended to a persistent terminal collapse (final-10 % mean I_d < 0.05 I_d,target
AND ≥ 90 % of final-10 % samples < 0.10 I_d,target, mode-matched target; a low steady current fails CURRENT; the bridge `sustained`
flag is diagnostic only); O4 amended to exact half-tolerances (7.5 % I_d; 2.6 / 2.8 / 2.8 mN) evaluated on vacuum results only
(facility-only differences never escalate). Execution order: the 1080 vacuum runs first (promotion decided from them), then the
1080 facility runs. Final pre-registration hash-locked in `prereg/p5_n2_prereg_lock_v1.json`; no score-bearing run before the
pre-registration PR merges.
**PR #27 review fixes (before merge, before any run):** (1) the molecular-N₂²⁺ branch is compared against its true baseline
`n2_n_di_lower.toml` (it is defined only on DI-lower, since the DI-upper table already counts N₂²⁺ as N⁺; comparing with
`n2_n.toml` would mix two changes), and its only escalation combination is × Wang elastic; (2) all 13 escalation-combination
configs (Johnson-low, rotational-off, HMS ×0.5, HMS ×1.3 × {DI-lower, Wang, DI-lower+Wang}; N₂²⁺ × Wang) are generated now by
`scripts/make_n2_variant_configs.py` and sha256-pinned in the criteria (22 chemistry configs in all), so an escalation never needs
chemistry defined after results. A test checks each combination carries exactly its sensitivity's rate-file change. The hash
lock was regenerated for these fixes before merge.

### 2026-09-26 — P5-N₂ campaign driver and scorer (after the pre-registration merged, #27 → 17a99cd)
`hallthruster_bridge/campaign/p5_n2_campaign.jl` runs candidate × chemistry × case in one mode, refuses to start unless every
file in the pre-registration lock and every pinned chemistry config matches its sha256, records raw observables only (window-mean
I_d, T_1D, the final-10 % I_d samples for O1, per-reaction f_out, outlet ion velocity/flux per species for O5, the bridge's
`sustained` flag as diagnostic) and logs keys and return codes only. `scripts/score_p5_n2_campaign.py` implements the frozen rules
(O2 precedence, O1 terminal collapse, CURRENT 15 %, THRUST N1–N3 T_1D·f_reading within 5.2/5.6/5.6 mN, O3 member/candidate
verdicts with missing runs never passing, O4 triggers, O5 diagnostic), with targets taken from the frozen audit; it was written and
tested on synthetic records before any campaign run existed. Smoke check (2 µs, targets stripped, flagged `smoke`, refused by the
scorer): records complete, 100 samples in the final 10 %.

### 2026-09-26 — Parallel tooling while the P5-N₂ vacuum campaign runs (no campaign value inspected)
- `scripts/audit_p5_n2_campaign_records.py` (fcd6720): structural integrity gate (identity/bookkeeping fields only).
- `scripts/freeze_p5_n2_dataset.py`: gate must PASS → canonical merge of the untouched raw lines sorted by key (duplicates,
  identical or conflicting, refused) → SHA256 → deterministic gzip → manifest binding driver 79d4e12, gate fcd6720, scorer
  10842ce, the pre-registration lock hash, and the code actually used (file sha256 + last commit). Never overwrites.
- `scripts/score_p5_n2_frozen.py`: verifies the dataset hash and lock, runs the frozen scorer unchanged, writes a provenance
  manifest (input SHA, scorer SHA/commit, lock, time, output SHA); refuses to score a dataset twice.
- `scripts/report_p5_n2_campaign.py`: mechanical report (candidate verdicts → 12 layer-1 member verdicts → status/reason counts →
  SIGNED current/thrust residuals → non-gating E×B) and a decision file transcribing the vacuum O3 verdicts.
- `scripts/make_p5_n2_launch_manifests.py` → `hallthruster_bridge/campaign/manifests/`: 19 pre-built manifests (facility 1080;
  5 staged sensitivities and 13 escalation combinations at 270 vacuum runs each) with expected keys, pinned chemistry hashes and
  exact commands; nothing launches automatically. Includes the structural check for those datasets.
- Admission gate: `ensemble/admission_record_schema_v1.json`; `hall_ensemble.load_ensemble()` now requires every admitted member
  to carry an offline-verifiable admission record (decision + score-provenance files with sha256, PROMOTABLE, supported passing
  layer-1 members) and refuses an id listed as both member and screening candidate; `require_admitted()` is the gate for any
  future Hall-map generator (screening candidates never produce design maps).
All tested on synthetic data only.

### 2026-09-26 — Result-pipeline hardening; ECHT-N₂ evidence audit (no simulation)
Pipeline (owner review of a6da974): the freeze and the score-once wrapper refuse to run unless the integrity gate and the scorer
are byte-identical to their content at fcd6720 / 10842ce (checked before any output); the decision file carries
`source_scores_sha256` and the provenance reference, and `hall_ensemble._check_admission()` requires it to equal the provenance
`output_sha256` (raw records → scores → decision → admission is one hash chain); scores and provenance are written to
temporaries and renamed only when both are complete, so an interrupted attempt leaves no official artifact. No scorer logic,
threshold or record changed.
ECHT-N₂ (`hallthruster_bridge/identification/echt_n2/`, published/open sources only; thesis PDF and figures not redistributed,
CC BY-NC-ND): Marchioni & Cappelli JAP 2021 is paywalled (abstract only); Marchioni's 2020 thesis (open) is the only per-point
source: geometry (86 mm, 10 mm channel height, "100 mm OD"), one measured centreline B(z) at 2 A (plateau 4.7–8.6 cm, ~85 G,
12 % below FEMM; the quoted 130 G is FEMM at 3 A), 13 setpoints at 180–220 V with I_d (2 s.f.), argon cathode flow 7–36 % of
the anode flow and chamber pressure, 7 thrust runs 20.6–23.4 mN (fit-only uncertainties, two reductions differing 6–18 %, three
runs flagged unstable). Missing: channel radii, anode position, B at the run currents, cathode coupling, total thrust
uncertainty, plume/divergence, facility correction, anything above 220 V. Conclusion: not an independent scoreable
discriminator without forced assumptions (A1–A11 in the audit); at most a pre-registered supporting check. Flags:
`cases/echt_n2.json` (225–275 V, exit-peaked Gaussian B) is unsupported by any open source, and the "250 V, 24 mN, 690 W"
Marchioni point in the superseded 0-D calibration (above) has no open source. Neither is changed here.
Release manifest: `scripts/make_validation_release.py` (run only after scoring) writes `validation/VALIDATION_RELEASE_v1.json`
binding pre-registration lock → driver commit → dataset SHA → gate/scorer identity → scores SHA → decision → admission records,
after verifying every link (refuses on any break or an existing release). No interpretation beyond copying the decision lists.

### 2026-09-26 — P5-N₂ v1 vacuum campaign: frozen, scored once, released (pre-registered; no retuning)
Chain: pre-registration PR #27 → driver 79d4e12 → 1080 raw vacuum records → integrity gate PASS (fcd6720; 9 × 4 × 30, all
`success`) → record-identity PASS → canonical freeze (sha256 20e926d507598a2ca3d4789929f7e99b179e5fc56c81403286552bbd54097468,
committed before scoring, fdcc4fa) → frozen scorer (byte-identical to 10842ce) run once → scores sha256 87895820…be1bc →
report + bound decision → `validation/VALIDATION_RELEASE_v1.json` (10/10 link checks pass; published atomically).
**Result (mechanical, from the frozen rules): no candidate PROMOTABLE; all nine sgb-screen-01…09 are INCONCLUSIVE / NOT ELIGIBLE.**
No global layer-1 member passes for any candidate; every candidate has members that FAIL (a scoreable validation failure) and
members that are INCONCLUSIVE (no failure among scoreable runs, but runs OUT_OF_DOMAIN). Run-reading statuses: PASS 32,
FAIL_VALIDATION 700 (CURRENT 552, THRUST 308, SUSTAINMENT 260), OUT_OF_DOMAIN 1428 (66 %), NUMERICAL_FAILURE 0.
Signed residuals (descriptive, non-gating): discharge current over-predicted at N2–N5 for most candidates (medians +24 to +31 %
across all runs; sgb-screen-05…09 closer, 08/09 under-predict at N1); axial thrust over-predicted at N2/N3 for 01–04.
E×B (non-gating): model N⁺ acceleration voltage 85–172 V below the measured value; the measured ordering V_a(N⁺) > V_a(N₂⁺) holds
in 0 of 648 model runs. Credible set stays ∅ (gate 3 FAIL). No criteria, chemistry, transport or tolerance changed.
Release follow-up (owner): `make_validation_release.py` now publishes atomically (temporary file → parse/verify → os.replace).

### 2026-09-26 — O4 gating before admission; O4 dataset freeze/score path (owner follow-up on PR #29)
Owner decision: a PROMOTABLE mandatory-vacuum result alone never admits a member or enables design Hall maps; the O4 first stage and
every escalation its trigger requires must be scored and dispositioned first. Enforced offline in `abep_sim/hall_ensemble.py`
(`_check_o4`, called by `_check_admission`, hence by `load_ensemble`/`require_admitted`): admission records now also require
`o4_dispositions_file`/`o4_dispositions_sha256` (amendment to `ensemble/admission_record_schema_v1.json`, made before any admission
record existed) pointing to an `o4_dispositions_v1` record (`ensemble/o4_dispositions_schema_v1.json`) that is bound to the same
mandatory decision, covers every pre-registered staged sensitivity against its baseline, cites scored O4 files (scored against the
same mandatory dataset and scores), carries a trigger value equal to the scored one, includes every pre-registered escalation when
fired, a non-empty owner disposition, and lists the member as cleared. What a disposition concludes stays the owner's decision.
`scripts/score_p5_n2_staged.py`: the fcd6720 gate is pinned to the 1080-run mandatory grid, so O4 datasets are frozen against their
pinned launch manifest (manifest == fresh build; `make_p5_n2_launch_manifests.check`; record identity; canonical sha256; deterministic
gzip) and scored once by the frozen scorer on mandatory + staged records (scorer byte-identical to 10842ce; mandatory candidates and
runs must be reproduced exactly; provenance renamed last). Dry-run controls (scratch, not results): the baseline relabelled as a
sensitivity fires no trigger; +10 % I_d fires it. No scorer, criterion, threshold, chemistry or record changed.

### 2026-09-26 — PR #30 review fixes (presentation and publication only; scores and decision unchanged)
(1) The v1 report's section-2 header carried unescaped `|` inside the member keys, so the rendered Markdown table was
misaligned. `report_p5_n2_campaign.report()` now escapes them. `p5_n2_campaign_v1_vacuum_scores_report.md` was regenerated from the
unchanged scores (sha256 87895820…be1bc); the only change is that header line. The decision file regenerates byte-identical and is not
touched. `VALIDATION_RELEASE_v1.json` was regenerated before merge; the only change is the report sha256 (638a393d… → a83cb68a…),
and all 10 link checks pass. Nothing was rescored.
(2) Evidence publication is now no-replace: release, score-once scores/provenance (frozen and staged), freeze datasets/manifests and
report/decision use a hard link or exclusive creation instead of replacing writes. A concurrent invocation can therefore never
overwrite a published artifact, and a rollback only removes the attempt's own file (inode-checked).

### 2026-09-26 — PR #30 merged; critical path re-ordered after the v1 result (owner decision)
PR #30 merged (daa0e75): the v1 vacuum result, the O4-disposition admission gate and the O4 freeze/score path. The owner's reading of
the result is that v1 could not discriminate, mainly because 1428 of 2160 run-reading evaluations are OUT_OF_DOMAIN and there are no
numerical failures. The fastest legitimate route to the thrust-architecture decision is to attack that cause, not to polish v1.
New critical path: OOD reactions → independent published evidence for a wider validity domain → a v2 N₂ validation pre-registration only
if justified → rerun only what v2 requires → admission. In parallel, a common-boundary Hall-only / RF+Hall / ECR+Hall comparison is
prepared. Rules: never extend a validity limit because the solver reached a higher T_e; v1 stays INCONCLUSIVE permanently; the E×B
diagnostic stays non-gating (physics forensics, no tuning); fixed-time polling is replaced by milestone watchers.
Parallel lanes launched as workflows in isolated worktrees, each checked by two independent adversarial reviewers (evidence lens and
rules/recompute lens) with up to two repair rounds:
- OOD attribution; N₂ domain-extension evidence audit with a DRAFT v2 outline; scoreable-subset forensics; E×B physics forensics.
- RF and ECR source evidence; Hall-only sustainment evidence.
- Common-condition experiment protocol (DRAFT); common bus-power boundary module; comparison harness (refuses while the credible set is
  empty); thermal/life framework.
These run alongside the earlier lanes (CI, ECHT disposition, Hall-map spec, ICD, O/O₂ audit, cathode, wall life, dual-feed, ledgers,
traceability, experiment package), the O4 first stage and the facility campaign.

### 2026-09-26 — O4 first stage 1/5: Johnson-low — trigger FIRED; escalations launched (pre-registered)
`staged_n2_n_exc_johnsonlow` (270 vacuum runs, `n2_n_exc_johnsonlow.toml` against baseline `n2_n.toml`):
- structural gate PASS (270/270, all `success`);
- frozen via `scripts/score_p5_n2_staged.py` (canonical sha256 9332ecdb…fe1eb);
- scored once with the frozen scorer on mandatory + staged records (mandatory scores reproduced exactly); scores sha256 ee55fce1…bc0d.
O4 evaluation (mechanical; `staged_escalation`): **trigger fired**.
- 221 run-level triggers: 96 |ΔT_axial| ≥ half tolerance, 64 |ΔI_d| ≥ 7.5 % of target, 61 status changes.
- Verdict changes when the baseline chemistry is replaced: sgb-screen-09 goes INCONCLUSIVE → FAIL_VALIDATION (members L32-exit|1p6kW|A/B
  go INCONCLUSIVE → FAIL); sgb-screen-08 L38-hist|3p0kW|A/B go FAIL → INCONCLUSIVE.
This is a sensitivity result, not a v1 verdict change: v1 stays as scored, and dispositions are the owner's (ensemble/o4_dispositions_schema_v1.json).
Per the pre-registration, Johnson-low is now run on the other three primary combinations. The escalation manifests are
`escalation_n2_n_exc_johnsonlow_{di_lower,nel_wang,di_lower_nel_wang}`, 3 × 270 runs, executed exactly as pinned. They run concurrently
with the remaining first-stage branches; the driver has no wall-clock limit, so oversubscribing the CPUs changes speed, not results.
Also recorded (owner): decision milestones A/B/C, the two-track structure, and the fan-out rule (CLAUDE.md next-work 3). The
Architecture Decision Acceleration lanes 16–27 and break-even surfaces were launched as dependency-aware workflows.

### 2026-09-26 — Orchestration governance tightened (owner review of the operating model)
The owner found two governance inconsistencies in my operating-model summary and asked for precision fixes. All are now implemented
in `docs/orchestration/`:
- Bundle 1 had an ambiguous dependency on lane 24 ("whatever … by then"). **lane_24_hard_gates is now a hard prerequisite**, because the
  bundle's elimination statements need the gate logic.
- The O4 disposition matrix was not a registered trigger. It is now registered as `T_O4_DISPOSITION_MATRIX`: all 5 first stages scored,
  plus every escalation of a fired first stage scored. The mechanical steps are registered too (`T_O4_SCORE`, `T_O4_ESCALATE`,
  `T_FACILITY_SCORE`), as are the v2 briefs `T_V2_QUESTION_A` / `T_V2_QUESTION_B` and `T_JOHNSONLOW_ESCALATION_ASSESSMENT`.
- Every dependency is now a machine id (lane_NN_*, ds_*, fo_*; break-even = lane_28_break_even). Triggers require the terminal state
  `verified` (both lenses, verified deps), not completion. A tracker test pins these semantics.
- The watcher claim was overstated. Two harness background-shell watchers (byu2qv4f0, bbdjklhst) had died silently: empty output, no
  exit notice, cause not determined. They are replaced by a detached daemon (setsid, PPID 1, PID 27068) that derives state every 60 s
  and appends transitions and READY triggers to a durable event log, plus a harness Monitor on that log (30-min expiry, re-armed).
  PIDs, survival limits and restart semantics are recorded in `runtime_state.json`. No event was lost, because state is re-derived
  rather than event-sourced.
- Other recorded changes: an admissibility rule with per-field metadata for the frozen comparison vector (P_feed/T_feed are
  feed-state pressure/temperature; electrically driven feed loads are inside P_bus); the strict Bundle-1 outcome vocabulary; and the
  separation of v2 Question A and Question B.

### 2026-09-26 — Transactional, idempotent trigger lifecycle (owner rule; governance cleared to continue)
The owner cleared the orchestration layer for continued execution and made one more control binding: trigger execution must be
transactional and idempotent.
- Implemented in `scripts/orchestration/trigger_ledger.py` with the append-only ledger `docs/orchestration/trigger_ledger_v2.jsonl`:
  READY → CLAIMED → LAUNCHED → VERIFIED | FAILED.
- The execution key is deterministic: trigger + dependency-state hash + prereg/config hash.
- The claim is persisted before launch through an exclusive-create claim file. A live claim is never READY again, so a daemon crash
  after launch cannot relaunch.
- LAUNCHED needs checkable evidence. Stale claims and unconfirmed launches raise alerts and are resolved by the operator, never relaunched
  automatically.
- The two firings from before the ledger existed are marked `record_origin=retroactive_reconstruction`, with reconstruction time,
  original time and evidence. The v1 ledger is frozen.
- During the migration a transient READY was announced (incident recorded in `runtime_state.json`). No action was taken, and the claim
  protocol would have refused a second launch.
- The daemon was replaced by v2 (PID 29739), which announces READY on transitions and raises alerts.
- `single-lens-v1` lanes must pass the second lens before becoming decisive evidence for Milestone B or C.
- No broader governance redesign (owner).

### 2026-09-26 — O4 first stage 2/5: rotational-off — trigger FIRED; escalations launched (transactional lifecycle)
`staged_n2_n_rot_off` (270 vacuum runs against `n2_n.toml`):
- structural gate PASS (270/270 success);
- frozen and scored once (mandatory scores reproduced exactly);
- ledger: T_O4_SCORE CLAIMED → LAUNCHED → VERIFIED.
O4 evaluation (mechanical): **trigger fired**.
- 369 run-level triggers: 148 |ΔI_d| ≥ 7.5 %, 141 |ΔT_axial| ≥ half tolerance, 80 status changes.
- Verdict changes with the baseline replaced: sgb-screen-09 goes INCONCLUSIVE → FAIL_VALIDATION (L32-exit|1p6kW|A/B become FAIL); in
  sgb-screen-06 and sgb-screen-08, L32-exit|3p0kW|A/B go INCONCLUSIVE → FAIL.
This is a sensitivity result, not a v1 change. The pinned rot-off escalations (3 × 270) were launched through T_O4_ESCALATE (claim
efb02512…, runner PID 8241, launch evidence = runner log start line).
Also: lane 17 went to operator repair (repair run registered), and the earlier watcher-death diagnosis was corrected in runtime_state.json.

### 2026-09-26 — v2 Question A: owner disposition A-NO (binding)
The verified Question-A brief (fo_v2_domain_question_a) was dispositioned by the owner: **A-NO**. The active N₂ chemistry domain stays
at 45 eV mean energy, and no P5-N₂ v2 is opened now.
Why: the only defensible partial extension (dissociation to 60 eV) does not unblock validation. With rotational excitation capped, at
most 37 of 714 OOD runs are recoverable (≤ 9 per candidate), so a minimal v2 on the same P5 data cannot produce a promotable candidate.
The dissociation→60 eV finding is kept as candidate evidence for a future revision, not as the active domain; it rests on two
reconstructed, not fully independent points.
Binding rules:
1. A limit-only change is a controlled model-domain change.
2. The same P5 measurements scored again are not new evidence for promotion (recorded in `admission_record_schema_v1.json`).
3. Question B is BLOCKED_BY_QUESTION_A_DISPOSITION, enforced in the trigger registry (owner-disposition prerequisite).
Sub-decisions: D-X1 NO, D-X12 NO (retain as support), D-X2 no change, D-X3 NO, D-X4 NO, D-X5 YES (bounded: rotational > 10 eV first,
then electronic, non-resonant vibrational, then dissociation), D-X6..10 deferred, D-X11 n/a. Reopen only on genuinely new published
evidence. O4 (stages 3–5, escalations, disposition matrix) and Bundle 1 continue unchanged.

### 2026-09-26 — O4 first stage complete (5/5 fired); Johnson-low and rot-off escalations scored; 7 further escalations launched
All scored once through the transactional lifecycle, with the mandatory scores reproduced exactly each time. Every trigger fired.
First stages:
- HMS-low: 148 run-level triggers, 2 member changes.
- HMS-high: 120 triggers; sgb-09 goes INCONCLUSIVE → FAIL_VALIDATION.
- N₂²⁺ dication (baseline DI-lower): 532 triggers; sgb-05 and sgb-09 → FAIL_VALIDATION.
Johnson-low escalations:
- nel_wang: 183 triggers.
- di_lower_nel_wang: 212 triggers.
- The earlier di_lower escalation: 209 triggers.
Rot-off escalations:
- di_lower: 390 triggers; sgb-09 → FAIL.
- nel_wang: 362 triggers; sgb-06 and sgb-09 → FAIL.
- di_lower_nel_wang: 353 triggers; sgb-09 → FAIL.
These are sensitivity results; v1 is unchanged. The pinned escalations of HMS-low (3), HMS-high (3) and dication (1) are running.
A container reboot (~19:15–19:35Z) cut off the non-gating facility campaign after 36 of 1080 records; it is not rerun without the owner.

### 2026-09-26 — Facility campaign: owner decision after the reboot
The reboot-interrupted facility attempt (36 of 1080 records, started 19:10:12Z) is preserved unchanged in
`hallthruster_bridge/validation/interrupted/facility_mandatory_attempt1/` (STATUS.json: INCOMPLETE_INFRASTRUCTURE_INTERRUPTION, file sha256).
It is not a numerical failure and not a physics result, and it is never scored or concatenated.
A fresh 1080-record attempt (`facility_mandatory_attempt2`) launches only via `T_FACILITY_RELAUNCH`, after the 7 active O4 escalations
are frozen and scored. It gets fresh execution provenance linked to attempt 1, and `T_FACILITY_SCORE` runs only after its complete
structural audit. Facility stays non-gating; the priority after the escalations is S9/S12.

## 2026-09-27 — A5: Proposal Reference Architecture / Phase-1 Baseline (owner decision)
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json`. It freezes a dual-feed extended-channel
Hall thruster as the proposal reference, **not** the flight architecture. Atmospheric propellant is the primary feed. Xe is used
only for ignition, the shielded LaB6 cathode and time-limited contingency, drawing on one fixed Xe mass ledger. The cathode design
target is 0.10 mg/s; 0.15 mg/s is a test point only. Continuous Xe support of the discharge counts as a Phase-1 failure. The RF
pre-ionizer is interface-ready (its ICD is to be written now) but is not baseline flight hardware; ECR is the alternate.
H-1 Phase 1 picks the branch: A (Hall-only), B (RF+Hall), C (ECR+Hall) or NO_VIABLE_CASE. It sweeps mdot_atm x x_O2 x V_d
and runs Hall-only, then RF, then ECR at each point under common conditions. The discriminators are T/P_bus, sustainment, eta_u
and envelope width. Thrust, power, mass and life figures are allocations or requirements, never predictions. Hall validation
status is unchanged: the credible set remains empty.

## 2026-09-29 — Owner decision pack (147 answers) and A9: Hall + downstream RF-ICP neutralizer

The owner answered all 147 consolidated questions (`docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md`, verbatim;
machine-readable `OD_2026_09_29_owner_answers_147.json`) and created A9
(`OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json`): the primary investigation hypothesis becomes a Hall
discharge with a downstream 13.56 MHz RF ICP neutralizer, with Hall + heated Xe-fed LaB6 C1 as control/fallback. The upstream
pre-ionizer campaign and the parallel RF||Hall v2 / A8 become historical (preserved, not rewritten). No model, frozen data or
golden changed. Eight leftover worktrees were archived (`docs/orchestration/archive/leftover_worktrees_2026_09_29/`) and removed
(row 10). The Takahashi et al. 2024 citation was verified against Crossref (CC BY-NC-ND); its data are not yet extracted.

## 2026-09-30 — A9 integration complete on the execution branch (A9.1, A9.2 incorporated)

A9-01..A9-10 verified and merged on claude/nifty-ramanujan-w68f9z: Hall->ICP prereg framework, A9 bus boundary
(bus_power_boundary_a9_v1, 1 ms-window P_bus gate per A9.1), ICP-neutralizer ICD, C1-vs-ICP uncertainty budget,
Takahashi 2024 extraction + validation inputs, core integration record, A9 mass reconciliation, H2 revisions, A9 Xe
ledger, RFQ packages (quotations only), A9-10 reconciliation (M16 v3, owner-question state v2). Owner A9.1 and A9.2
decisions are recorded as immutable addenda and applied. A9.2 statuses: Hall->ICP INVESTIGATION_HYPOTHESIS; ICP
electron-current capacity PENDING_ICP45; RF power closure PENDING_HARDWARE; local match selected for development; RF
component ratings TBD_AFTER_IMPEDANCE_MAP; 316L REJECTED_AS_CURRENT_BASELINE; final anode material OPEN; anode thermal
closure and coupled H-1/ICP thermal closure UNRESOLVED; C1 CONTROL_FALLBACK. Findings carried to the owner: the v0 mass
allocations are below verified evidence floors for three lines; the C1 reference needs >= 6.87 kg loaded Xe in flight;
the H-1 anode worst case (1190-1292 degC) is incompatible with 316L. No model, frozen data or golden changed; historical
A4-A8 artefacts are byte-identical. Next (owner priorities): P1 ICP electron-source bench (ICP-45), P2 ICP impedance map,
P3 coupled thermal redesign, P4 anode design.

## 2026-09-30 — Checkpoint 3 merged to main (A9)

With the owner's approval, PR #33 (head 4555c78) was merged into main as 20f14d8, after CI passed 6/6 and the A9.2 §11
post-merge checks passed. The merged main reproduces: 2204 passed / 5 skipped / 1 xfailed, golden OK, ci_checks 10/10.
This is the clean post-A9 baseline. Owner sequence: triage the 54 open owner questions, then P1 ICP bench (ICP-45) → P2
impedance map → P3 coupled thermal redesign → P4 anode design. P3/P4 are not closed before P1/P2 data exist, because the
measured ICP/RF electrical behaviour sets the real thermal load. No model, frozen data or golden changed.
Owner-question triage (recorder proposal, not a decision): `docs/budgets/owner_decisions/OWNER_QUESTIONS_TRIAGE_POST_A9.md`
puts each of the 54 OPEN state-v2 questions in exactly one tier: 8 gate the P1 bench, 2 wait for P2 data, 8 set the
P3/P4 thermal rules, 20 are mass/Xe closure, 12 are comparison-campaign design and 4 are governance. There are two
duplicate groups (Xe design-case content; ignition dwells).

## 2026-09-30 — A9.3 post-A9 tier-1 owner decisions; P1 authorized, P2 preparation in parallel

The owner answered the eight tier-1 questions (verbatim `docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md`,
machine-readable `OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json`):
- **First build:** open-tube coaxial ICP only, on a modular carrier that leaves room for a later orificed variant.
- **Ar check:** the "no Hall discharge without ICP" check is an engineering control, never scored.
- **Discharge current:** 8.33 A is the stand design ceiling. The ICP-45 requirement is the registered H-1 maximum
  discharge current, and until it is known P1 reports the I_e capability surface.
- **Isolation:** ~1 kV representative-gas isolation, only where a gas line crosses a potential difference.
- **RF source:** a mains-fed laboratory RF generator for ground use only. P_mains,in is never P_bus evidence; C_e and
  C_e,DC are reported with labelled boundaries.
- **RFQs:** split by supplier speciality. The team prepares them and the owner/procurement dispatches them.
- **Ar flow:** 1–2 Ar flow ranges, not 4; Ar data stay engineering-only.
- **Dedicated ICP feed:** its controller is a quotation option only; G-REUSE stays primary.

Owner-question state v3 records these answers; 46 questions remain OPEN, and v2 is unchanged. Triggers registered:
T_A9_P1_ICP_BENCH, T_A9_P2_IMPEDANCE_PREP (the plasma map needs stable P1 plasma first) and T_A9_RFQ_V2_SPLIT. No model,
frozen data or golden changed.
A9.3 lanes verified and merged on the execution branch:
- **P1 ICP bench** `docs/experiments/hall_icp/p1_icp_bench/`: stages, capability surface, OQ-VI-05 control,
  current-path closure, analysis script, record format.
- **P2 impedance preparation** `docs/experiments/hall_icp/p2_impedance_map/`: reference planes, calibration,
  analysis script; the plasma map needs P1 stable plasma first.
- **RFQ v2** `docs/procurement/rfq_a9_v2/`: six supplier-type packages plus a common interface document; v1 unchanged.

Post-merge: 2321 passed / 5 skipped / 1 xfailed, golden OK, ci_checks 10/10. New owner questions: P1Q-10 (I_e,cap as
a Hall-OFF capacity-extraction measurement), P1Q-13 (H-1 anode/body configuration in Hall-OFF stages), P1Q-14 (ICP
isolation class and hipot voltage), P2Q-05 (optical unlit-verification indicator).

## 2026-09-30 — A9.4 P1/P2 owner decisions applied; checkpoint 4 prepared

The owner answered P1Q-10, P1Q-13, P1Q-14 and P2Q-05 (A9.4, `docs/decisions/OD_2026_09_30_A9_4_*`):
- **P1Q-10:** ICP-45 capacity is measured as discharge-OFF extraction to a dedicated collector, minus a matched RF-OFF
  record. Hall-ON runs count only as NEUTRALIZATION_CONSISTENCY.
- **P1Q-13:** the anode is floating (open circuit by construction), and the H-1 body has a single-point metered ground.
- **P1Q-14:** the ICP circuits join the 350 V class, with a ≥ 525 V design withstand and an initial DWV of 1.05 kV DC for
  60 s. ICP-44 RF insulation stays open.
- **P2Q-05:** a photodiode is required, and plasma states are UNLIT / E_MODE / H_MODE / UNCERTAIN.

The owner also authorized sending the P1_NEEDED RFQs for quotation (no POs) and one merge to main.
fo_a9_4_incorporation applied these to P1, P2 prep and RFQ v2; it was verified in round 1 with three lenses.
ICP-45 stays NOT_EVALUATED until I_d,max,H1 is registered.

Post-merge: 2340 passed / 5 skipped / 1 xfailed, golden OK, ci_checks 10/10. Protected artifacts are unchanged; the diff
vs main is additive. Minors carried: stale PENDING RFQ references in P2, one leftover PROPOSED wording in P1-S4, and the
INS-P2-10 source list, which cites A9.3 but not A9.4.
Checkpoint 4 merged to main as eef8b85 (PR #34), using the A9.4 one-merge authorization. Codex raised two findings on the
P1 reducer; both were fixed in ca36c9e before the merge. Paired capacity records must now match the closure rule's sign
convention, and mixed synthetic/measured candidates are refused. Main reproduces 2342 / 5 / 1, golden OK and 10/10.

## 2026-09-30 — A9.5 / A9.6: implementation-first batch and consolidated verification (execution branch; not on main)

**A9.5 (P1Q-15/16):** the P1 reducer implements the owner's Kirchhoff closure rule and the signed I_e,cap = I_on - I_off.

**A9.6 (implementation-first directive):** every currently authorized item was implemented, and then verified once.
- **Existing packages completed:**
  - P1 bench workflow: G0 through Hall-ON consistency, a campaign driver, fail-closed reducers.
  - P2 impedance framework: Touchstone, SOL, de-embedding, GUM/MC uncertainty, E/H-mode detection, map storage,
    the rating structure.
  - RFQ v2 packages completed.
- **New:**
  - P3 coupled-thermal framework (no thermal PASS) and P4 anode/collector materials framework (no selection).
  - Mass/power v2 and Xe accounting v2.
  - A requirement-verification matrix: 19 rows x 2 configurations, 0 PASS.
  - Owner-question state v4: 95 TBD_OWNER, each with its blocker and dependency.
  - M16 v4: no state change.
- **Cross-lane integration:** 42 interface pairs; circular sha pins removed.

**Consolidated verification:** six dimensions (structural, physics/evidence, electrical, thermal, metrology,
software).
- 32 findings (23 major, 9 minor), repaired in three rounds.
- Follow-up fixes MET-07-R1..R5 close every self-declared route by which the P2 line/match-loss check could turn an
  inconsistent at-power check into a reconstructed P_delivered. One registered protocol per (method, loss model) now
  fixes k, the uncertainties, the check power, the reference load and the application range.

Final checks: 2657 passed / 5 skipped / 1 xfailed, golden OK, ci_checks 10/10, protected artifacts unchanged vs main
eef8b85. No model, frozen dataset or golden changed. Build order: P4, XE, P1, P2, P3, MP, RFQ, RVM, state v4, M16 v4.
Checkpoint 5 merged to main as 98fbbb9 (PR #35) on 2026-10-01 with owner approval (one merge). Fixed before the merge:
- **P3 builder:** its serialization is now platform-independent. CI could not reproduce the outputs because they
  carried machine-precision residuals.
- **P1 readiness (two Codex findings):** duplicate interlock / DWV-path / gas-line ids are refused, and records are
  ordered by parsed UTC timestamp.

Main reproduces 2659 / 5 / 1, golden OK, ci_checks 10/10.

## 2026-10-01 — A9.7 consolidated verification; owner decisions A9.8–A9.11 (groups S1–S4)

A9.7 consolidated verification (wf_ba93b973-628; dimensions structural, physics, optimization, rust, integration,
software): 25 findings (14 blocker/major), repaired in two rounds, 0 blocker/major remaining. Notable repairs: stale
cross-lane PENDING references resolved; H1F-MC-02 coil arrangement no longer FREEZE_CANDIDATE on an assumed basis;
system constraints MET only on evaluated values; design-layer input validation (no silent Maxwell fallback). Post-merge
(d63b113): 2901 passed / 5 skipped / 1 xfailed, golden OK, ci_checks 10/10; no production module, frozen dataset, golden
or decision file changed. Triggers T_A9_7_* VERIFIED.

The 135 open owner questions were sequenced (`docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md`). The owner
answered groups S1 (A9.8, P1 start), S2 (A9.9, production-model changes), S3 (A9.10, later P1 stages) and S4 (A9.11,
P2); records in `docs/decisions/OD_2026_10_01_A9_{8,9,10,11}_*`. Owner-supplied values: k_loss = k_agreement =
k_transition = 2.0. A9.9 authorizes controlled model changes (IntakeSurface recombination, frozen intake surface v2,
rotor strength basis, G-03..G-05 convergence flags, MCC-02/03/05/06/07); none is implemented yet, each will carry its own
entry here.

## 2026-10-01 — Checkpoint 6 merged; owner decisions A9.12–A9.15; application step A9.16 launched

Checkpoint 6 (A9.7 verified design synthesis + decision records A9.8–A9.12) merged to main as b1e5b76 (PR #36) with owner
approval. Before the merge, five Codex review findings were fixed in the design layer (P_bus counts efficiency evidence; T − D
inherits the intake-drag status; non-positive / non-finite densities refused; transient trajectories checked against the
rotor service temperature), each with a regression test; all design builders reproduce unchanged.

All 135 sequenced owner questions are now answered: S5 (A9.12), S6 (A9.13), S7–S10 (A9.14). A9.15 records the owner's
RFP-compliant propellant policy: the official RFP governs propellant capability; the system supports ambient atmospheric
propellant and Xenon propulsion capability; C1 Xe, if any, comes from the selected C1 hardware and is booked inside the system
Xe architecture. It amends the earlier "Xe contingency-only for C1" wording. A9.16 applies the decisions in three sequential
steps (experiment/procurement/budget records; A9.9 production-model changes; A9.13 architecture code).

## 2026-10-01 — A9.16 parallel lanes merged (new files only)

- **Orbit-resolved frozen atmosphere `atmosphere_msis21_orbit_v1`** (CLAUDE.md rule 1 versioned build, authorised by
  A9.13 S6.14; implements A9.14 S9.7/S9.8). NRLMSIS 2.1 via pymsis 0.13.0 over 180/195/215/230 km x latitude x local
  time x longitude x day of year, four ECSS-E-ST-10-04C Rev.1 Table 6-3 solar/geomagnetic scenarios (no interpolation
  between scenarios); 116,736 rows. Log-space interpolation, worst error vs direct MSIS 2.3 % (rho) / 3.2 % (major
  species). Out-of-domain queries raise. Includes frozen design states (179) and a statewise quantifier where an orbit
  average never hides a violation. No winds (NRLMSIS has none; owner question). The orbit-averaged
  `atmosphere_msis21_v1` is unchanged and nothing existing imports the new module. Review fix: late-year (doy 321-365)
  orbit sampling no longer refused.
- **Transitional-regime compressor model** `abep_sim/compressor_transitional.py` (A9.13 S6.8): drag-channel stages,
  open-literature sources in `docs/evidence/compressor_transitional/`; always `CANDIDATE_NOT_ADMITTED`.
- **Optional Rust parity CI** `.github/workflows/rust-parity.yml` (A9.14 S10.4); not a required check.
- **Reference spacecraft drag basis** (A9.13 S6.18), labelled REFERENCE/PARAMETRIC, not the flight spacecraft.
- **Species-resolved sputter-yield evidence register** `docs/evidence/sputter_yields_v1/` (A9.12 S5.13).

## 2026-10-01 — Dedicated performance baseline registered (A9.14 S10.2, A9.17 PERF)

The owner ran the unmodified F0 harness (`scripts/perf/profile_baseline.py`, identical workload spec and parameters) on an
otherwise idle i7-11700K / Windows 11 / Python 3.13 machine (branch `perf/dedicated-baseline-2026-10-01`, commit 72669db).
Registered in `docs/performance/dedicated_baseline_2026_10_01/` as the admission baseline for Rust performance decisions;
the A9.7 shared-CPU baseline is historical only. Reference workloads ran about 2x faster than on the shared machine; with the
S10.1 thresholds unchanged, every judgement is unchanged (uq_modular_run_uq and intake_response_surface_reduced remain
PORT_CANDIDATE, archengine_close_architecture MARGINAL). Four determinism fingerprints differ at <= 1e-4 relative
(platform floating point); they are not physics evidence.
## 2026-10-01 — A9.9 S2.4 (UPSTREAM_ICD-Q7): G-03..G-05 gas-path convergence flags

Owner decision A9.9 S2.4 (`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`, item 4). Production
gas-path solvers now report convergence explicitly; reaching an iteration limit or a bracket endpoint is not convergence.
- G-03 `DragCompressor.run()`: `converged`, `iterations`, `residual` (max_s |Q_leak − Q_recirc| / ṁ_s vs 1e-4),
  `solver_status` CONVERGED / MODEL_NOT_CONVERGED (DIRECT_EVALUATION when `self_consistent=False`); `size_for()` carries
  the selected run's fields (search unchanged).
- G-04 `Reservoir.steady_state()`: `converged`, `iterations`, `residual` (fixed-point step vs 1e-6),
  `balance_residual_rel` (per-species mass balance at the returned state / total inflow), `solver_status`.
- G-05 `size_orifice_for_pressure(..., report=True)`: final pressure and relative residual, `bracketed`/`reachable`
  (p(3e-2 m²) ≤ p_target ≤ p(1e-8 m²)), inner steady-state convergence, `converged` (bracketed ∧ |resid| ≤ 1e-6 ∧ inner
  converged), `solver_status`; the default call still returns the area, and the record is left on `res.orifice_sizing`.
- Callers: `system.evaluate` emits `comp_/res_/orifice_*` convergence fields and `gaspath_status`; a non-converged gas path
  makes `compressor_feasible` False (fail closed). `archengine.gas_path_state` carries `gaspath_status` /
  `gaspath_not_converged`; `close_architecture` refuses gas states with a non-converged compressor-recirculation or
  reservoir fixed point (rule 3; status MODEL_NOT_CONVERGED if no admissible gas state remains) and carries an unmet
  orifice setpoint (a converged reservoir state at the bracket-end area; p_in is that actual pressure) onto the result as
  `gaspath_status` / `evidence_admissible=False`. `arch_compare.UpstreamState.from_gas_path` refuses non-converged states.
Finding while implementing: the orifice setpoint is unbracketed at many default archengine gas states (e.g. area 1.3 m²,
p_level 0.05 Pa — the golden architecture-closure/mission design point: target min(p_target, p_out) ≈ 0.0065 Pa, reservoir
at the 300 cm² bracket end 0.088 Pa; also all p_level 0.02 states). These are now flagged, not refused, so the golden
benchmarks are carried unchanged; whether such results should be refused outright is an owner question.
Golden impact: none (`python -m abep_sim.golden check` OK; converged numerics bit-identical, regression-tested against the
pre-change loops in `tests/test_gaspath_convergence_g03_g05.py`).
Review fix (2026-10-01, findings D-02 / N2): the carry convention above ("flagged, not refused") let an orifice-unreached
or Gaede-out-of-domain gas state win the search and return status 'OK' / feasible True with only `evidence_admissible =
False`, which nothing read. `archengine.close_architecture` now fails closed by evidence class (`GAS_EVIDENCE_CLASSES`,
`gas_evidence_class()`): OK > PARAMETRIC_SENSITIVITY (rotor not qualified, S2.3) > OUT_OF_MODEL_DOMAIN (MCC-02) >
MODEL_NOT_CONVERGED (G-03..G-05, orifice included) > GASPATH_STATUS_NOT_REPORTED (synthetic state without labels). The
nested search ranks by class first and objective second (also in the thermal runner-up fallback), so a non-admissible
state never displaces an admissible one. A winner that is not class OK keeps its raw numbers for diagnostics but returns
`status` = its class, `feasible` False, `closes_constraints` True, `evidence_class` / `evidence_reason` and
`gas_states_by_evidence_class`. `propulsion_map` and `mission5.run_mission_generic` now carry `architecture_status`,
`evidence_class`, `evidence_admissible`. Unreachable p_level grid values (e.g. 0.02 Pa below the ~0.047 Pa floor at
0.7 m²) stay in the default grid but are reported per state and lose to admissible states. Golden impact:
`architecture_closure/ext_hall_2p5kW/status` 'OK' -> 'MODEL_NOT_CONVERGED' (area 1.3 m², p_level 0.05 Pa: orifice
unbracketed, also Gaede OUT_OF_MODEL_DOMAIN); this fix moves no number (the numbers moved by the S2.1 review fix below);
the mission benchmark propagates that labelled diagnostic design. No admissible golden design point exists while no
rotor-strength basis is registered; moving the golden design point is left to the owner. Existing tests changed because
the owner decision changes the behaviour: `tests/test_sim.py::test_archengine_enumeration_and_closure` and
`::test_v12_branches_execute_and_constraints_bind_inside_search` now expect the evidence-class status with feasible False
and check `closes_constraints`; the conditional `if status == "OK"` checks in `tests/test_gaspath_convergence_g03_g05.py`
and `tests/test_compressor_gaede_domain_mcc02.py` are now unconditional. Tests: `tests/test_a99_review_fixes.py`.

## 2026-10-01 — A9.9 S2.5 (F9-OQ-04): MCC-05/06/07 intake_tpmc input validation

Owner decision A9.9 S2.5 (`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`, item 5; findings Rust
parity DIV-01..DIV-04). `abep_sim/intake_tpmc.py` now validates its inputs before any particle is sampled or traced (the
caller's RNG stream is not consumed on refusal); invalid input raises `ValueError`, nothing is clipped or defaulted.
- MCC-05: `trace_channel` `max_hits` and `max_hits_cap` must be positive integers (bool, float, ≤ 0 rejected), so
  `max_hits < 1` no longer loops forever; `unresolved_tol` must be finite and ≥ 0. `max_hits_cap = 0` (previously
  accepted, DIV-04) is now refused by the reference as well; `tests/test_tpmc_backend.py::test_div04_*` updated accordingly.
- MCC-06: `scattering` must be exactly `"maxwell"` or `"cll"` in `trace_channel`, `intake_response` and
  `response_surface`; any other value (including `"Maxwell"`) raises instead of silently tracing Maxwell. The thermal
  back-trace in `clausing_transmission` now selects Maxwell explicitly (`K_BACK_SCATTERING`, same behaviour as before),
  and `intake_response` records it as `K_back_scattering` next to `scattering`.
- MCC-07: accommodation coefficients must be finite and inside [0, 1]: CLL `alpha_n` / `alpha_t` (each defaulting to
  `alpha`, as before) checked in `trace_channel` and again at the `_cll` kernel entry; the Maxwell diffuse fraction
  `alpha` likewise. NaN / ±inf / out-of-range values are rejected, never clipped (the clip in `intake.collection` on the
  frozen-surface path is unchanged and outside this change).
Valid-input numerics are bit-identical (checked against the pre-change module for Maxwell and CLL `intake_response` and
`trace_channel` cases); frozen `intake_surface_v1` untouched. Tests: `tests/test_intake_tpmc_input_validation.py`.
Golden impact: none (`python -m abep_sim.golden check` OK). Downstream: the A9.7 Rust parity records pin the reference
sha256 (`docs/performance/abep_core/parity_prereg_v1.json` / `parity_report_v1.json`), so `scripts/verify_abep_core.py
--check` and two `tests/test_tpmc_backend.py` hash assertions now refuse (NOT_ADMITTED_BUILD) until those records are
re-registered by their owning step; the `abep_sim/design/tpmc_backend.py` DIV-01..04 docstring is now historical.
Review fix (2026-10-01, finding D-09): the owner asked for each S2.5 change to be documented separately; MCC-05,
MCC-06 and MCC-07 now also have their own dated entries at the end of this file (this combined entry is kept as written).
Finding N1 stays open downstream: the A9.7 parity pre-registration pins the `intake_tpmc.py` sha256, so
`scripts/verify_abep_core.py --check` reports NOT_ADMITTED_BUILD and `tests/test_tpmc_backend.py::test_prereg_frozen_values`
/ `::test_report_rederives_and_is_consistent` fail until the parity owner records an addendum / re-registration
(`docs/performance/**` and `abep_core/` are outside this step).

## 2026-10-01 — A9.9 S2.3 + S2.5 MCC-03: registered rotor-strength basis for rotor structural acceptance

Owner decision A9.9 S2.3 (OQ-F3-01) and S2.5 MCC-03 (`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`,
items 3 and 5; A9.13 S6.9; findings F3-02 / MCC-03). New module `abep_sim/rotor_strength.py`: a `RotorStrengthBasis`
record carrying every S2.3 minimum field (material spec, product form, condition, stock section range, design
temperature, statistical allowable basis + citation, yield AND ultimate versus temperature, density from the same
controlled definition, yield/ultimate design factors, max design speed, proof-spin basis or an explicit not-applicable
reason, owner registration). `register_basis()` admits only complete records (no extrapolation of the allowable table,
factors >= 1, Fty <= Ftu, no duplicate ids); `qualify_rotor()` computes margins on both yield and ultimate
(sigma = rho u^2 at the largest tip speed, allowables at the registered design temperature) and fails closed:
no / unregistered / incomplete basis, material mismatch (no transfer) or missing / out-of-range stock section give
`NOT_EVALUATED_MATERIAL_BASIS`; rotor temperature above the basis design temperature gives `NOT_EVALUATED_OUT_OF_DOMAIN`;
negative margins or speed above the registered maximum give `FAIL`. `rotor_ok` is True only for `PASS`.
`REGISTRY` is empty: nothing has been registered. The cited Ti-6Al-4V annealed-plate 50.8–101.6 mm room-temperature
A-basis values (Fty 827 MPa, Ftu 896 MPa; MMPDS-06 quoted by NASA-HDBK-6025 Sec. 3 p. 18) are carried only as
`REFERENCE_RECORDS[...]` with status `INCOMPLETE_REFERENCE_NOT_REGISTERED`, never transferred and never qualifying.
`abep_sim/compressor.py`: `DragCompressor` gains `rotor_strength_basis_id` / `rotor_stock_thickness_m` (set with
`set_rotor_strength_basis()`; deliberately not dataclass fields, so the field-enumerating design-input contracts of
lane 16 / F3 are unchanged — they are qualification evidence, not sizing coefficients); every
`run()` / `size_for()` record carries `rotor_qualification`, `rotor_ok`, margins, `sizing_mode`, `u_max_basis`,
`u_max_legacy_sensitivity_mps` and `rotor_within_legacy_sensitivity_cap`. Without a registered basis the machine is
`sizing_mode = PARAMETRIC_SENSITIVITY`: the tip-speed / rpm cap is the old one (uncited `materials.DB` yield over the
uncited `stress_safety = 2.0`), now explicitly labelled `LEGACY_CONSERVATIVE_SENSITIVITY` (`u_max_legacy_sensitivity()`);
with a registered basis the cap is min(Fty/FS_y, Ftu/FS_u) at the design temperature. `abep_sim/system.py` (gas-path
physics) reports `comp_rotor_qualification`, `comp_rotor_ok`, `comp_sizing_mode`, `comp_u_max_basis`; its
`comp_feasible` already required `rotor_ok`, so every gas-path-physics evaluation now has `chk_compressor_feasible =
False` and therefore `rfp_compliant` / `feasible` / `technical_compliant` False (fail closed) while compressor mass and
power stay computed as a labelled parametric-sensitivity result. No coefficient was retuned.
Behaviour change in an existing test: `tests/test_sim.py::test_compressor_pumping_speed_limit` no longer expects
`rotor_ok` for the CFRP rotor (now `NOT_EVALUATED_MATERIAL_BASIS`, inside the legacy cap), and
`tests/test_feed_envelope.py::test_design_conditional_chain[size_for]` now expects every case refused while the
registry is empty (previously >= 1 OK case; the original assertions still run once a basis is registered). New tests:
`tests/test_rotor_strength_basis.py` (synthetic, labelled test-fixture basis only).
Golden impact: none (`python -m abep_sim.golden check` OK) — the golden gas-path / archengine / mission benchmarks use
compressor mass, power and pressures, not `rotor_ok`, and the sizing cap is numerically unchanged without a basis.
Downstream (owned by other steps): design-synthesis F3 (`module_rotor_ok_uncited_db_yield` now always False),
`scripts/architecture/build_feed_envelope.py` and `docs/architecture_comparison/feed_state_closure` (rotor_ok False is
reported as infeasible), freeze-candidate MCC-03 status.
Review fix (2026-10-01, findings D-03 / N4, D-06 / N5): `archengine.gas_path_state` now carries `comp_sizing_mode`,
`comp_rotor_qualification`, `comp_u_max_basis` (strings); `close_architecture` results report them and, while the rotor
is NOT_EVALUATED_MATERIAL_BASIS, are labelled `status = PARAMETRIC_SENSITIVITY` with feasible False (see the S2.4 review
fix); `arch_compare.UpstreamState.from_gas_path` carries them as labels (real-gas-state fingerprints change; no committed
artifact pins one). `rotor_strength.qualify_rotor` refuses a non-finite, negative or non-numeric tip speed or rpm and
NaN margins with `NOT_EVALUATED_OUT_OF_DOMAIN` (previously NaN gave margins +inf and PASS / rotor_ok True). Not done in
this step (path owned by another step, finding D-05): `abep_sim/design/compressor_synthesis.py` still grants stress
acceptance from `CITED_ALLOWABLES_PA` x `stress_safety` (yield only) instead of `qualify_rotor`. Golden impact: none
from these items.

## 2026-10-01 — A9.9 S2.5 MCC-02: Gaede stage-capacity domain (no silent K clipping)

Owner decision A9.9 S2.5 MCC-02 (`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`, item 5; finding
F3-01; freeze-candidate MCC-02). `DragCompressor._run_once` previously replaced the linear Gaede characteristic
K = K0 - (K0 - 1) Q / (S p) by `max(min(K, K0), 1.0)`, so a stage whose throughput exceeds its capacity S p (K < 1:
the stage cannot pass the flow; no admitted steady state) was silently reported as a valid K = 1 stage.
Now every turbo row and drag stage records, per species, the UNCLIPPED K together with K0, throughput, capacity and
load ratio (`gaede_stages`, `gaede_K_unclipped` {stage: {species: K}}, `gaede_K_unclipped_min`). Any K_unclipped < 1
sets `gaede_domain_ok = False`, `gaede_status = OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY`, lists the offending
`stage:species` in `gaede_out_of_domain`, and marks the clipped value as `K_clipped_diagnostic` with
`gaede_clipped_values_are_diagnostic = True`: the cascade is still continued with K = 1 only so the raw state can be
inspected; p_out / CR / power / leak / mass of such a record are labelled diagnostics, not a compressor result.
In-domain stages propagate the unclipped K itself (bit-identical to before).
Fail closed: `size_for` admits a layout only if it reaches CR_target with every stage/species in domain (an
out-of-domain hit is counted in `n_rejected_out_of_gaede_domain` and the search continues at higher rpm); the unsized
fallback carries its own `gaede_status`. `system.evaluate` (gas-path physics) reports `comp_gaede_*`,
`gaspath_domain_status` (`IN_DOMAIN` / `OUT_OF_MODEL_DOMAIN`) and `gaspath_out_of_domain`, and `comp_feasible`
(hence `chk_compressor_feasible`, `rfp_compliant`, `feasible`) requires the domain. `archengine.gas_path_state` carries
the two domain labels; `close_architecture` keeps the G-05 carry convention (the closure is still computed, as a
labelled diagnostic) but `evidence_admissible` now also requires `gaspath_domain_status == IN_DOMAIN` and the result
reports `gaspath_domain_status` / `gaspath_out_of_domain`; `arch_compare.UpstreamState.from_gas_path` refuses an
out-of-domain state (SpecError), and consumes the labels so in-domain fingerprints are unchanged.
Observed: at the code-default compressor coefficients, the gas states at intake area 0.6 / 0.7 / 0.85 m² are sized
in domain (turbo-only layouts); at area 1.3 m² (all p levels) no layout is in domain and the unsized fallback is
OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY (that state was already `MODEL_NOT_CONVERGED` via orifice sizing, G-05).
No coefficient was retuned. Tests: `tests/test_compressor_gaede_domain_mcc02.py`; no existing test changed.
Golden impact: none (`python -m abep_sim.golden check` OK) — the selected in-domain designs did not change, and the
golden `gas_path/A1.3`, `architecture_closure` and `mission` benchmarks (area 1.3 m²) are now explicitly flagged
diagnostic (`gaspath_domain_status = OUT_OF_MODEL_DOMAIN`, `evidence_admissible = False`) without numerical change.
Downstream (owned by other steps): design-synthesis F3 (`build_f3_compressor.py --check` pins the `compressor.py`
sha256; its `stage_trace` mirror of the clipping is now historical and the production record supplies the unclipped
K directly), F4 / F7-F8 builders and the freeze candidate (MCC-02 status), feed-envelope / feed-state-closure
builders that read compressor records.
Review fix (2026-10-01, findings D-02 / N2): an out-of-domain winning gas state now returns `status =
OUT_OF_MODEL_DOMAIN`, feasible False (no longer 'OK' with only `evidence_admissible = False`), and an in-domain state
always wins over it in the search; see the S2.4 review fix.

## 2026-10-01 — A9.9 S2.1 F1Q-01: IntakeSurface species recombination by physical definitions

Owner decision A9.9 S2.1 (`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`, item 1; finding F1-01
of `docs/design_synthesis/f1_intake/`). `abep_sim.intake_tpmc.IntakeSurface` averaged every species row of the frozen
species-resolved surface by MASS fraction. That is a model-consistency defect: each species row s was built by
`intake_response(species_mass=m_s)` in the MIXTURE build atmosphere, so C_D_row,s = n_b Vz <dp_s> / (1/2 rho_b V^2) is
normalised by the build-mixture q (C_D_row,s = (m_s/m_b) C_D,s), and CR_passive,s = n_plenum,s / n_inf,s is a
number-density ratio. Now (derivation in the class docstring):
C_D = sum_s w_s C_D,s = m_b sum_s (w_s/m_s) C_D_row,s (species-own coefficients on the mixture dynamic pressure);
CR_passive = sum_s x_s CR_s (mole fractions); eta_c = sum_s w_s eta_c,s is the total collected / incident MASS flow
(unchanged by construction) and the species-resolved efficiencies, collected mass/mole fractions are returned in
`out["species"]`; `intake.collection` reports `mdot_collected_species` = eta_c,s w_s mdot_incident (sums to
`mdot_collected`). Mixture K_back is weighted by the plenum effusion flux (x_s CR_s m_s^-1/2). m_b is the frozen
build atmosphere (`frozen_surface_build_atmosphere()`: frozen NRLMSIS 200 km mean, use_msis=False); a test recovers it
from the table's own solid-face identity to < 1e-8. A species-resolved table without m_b is refused (no default).
Pre-fix vs post-fix at the F1-01 node (L/d 10, phi 0.9, alpha 1, theta 0, maxwell, build composition): C_D
2.249551 -> 2.082565 (old/new x1.0802), CR_passive 248.6665 -> 233.4082 (x1.0654), eta_c 0.451111 unchanged — the
F1-01 bias (x1.080 / x1.065) is removed exactly. Over all 240 frozen-grid nodes (both scatterings, build composition) the removed bias is C_D x1.0799-1.0821 and CR_passive x1.036-1.078.
The pre-fix recombination is preserved as historical evidence in `IntakeSurface.call_legacy_mass_weighted` (never used
by the production chain) and pinned in `tests/test_intake_surface_recombination.py`. Frozen `intake_surface_v1.*`
unchanged; no coefficient retuned. The fixed-composition fallback for a call without fractions is unchanged.
Golden impact (regenerated with `python -m abep_sim.golden generate`; old -> new):
intake C_D (all six cases) -7.4 to -7.6 % (e.g. maxwell_a0.8_ld5.0 2.221152 -> 2.054908); eta_c / mdot unchanged.
gas_path A0.7: C_D 2.221152 -> 2.054908, drag_mN 13.1022 -> 12.1216, p_in_Pa 0.0484925 -> 0.0500123,
P_comp_W 16.590 -> 26.054, m_comp_kg 5.2064 -> 6.6652 (lower passive CR -> larger active ratio -> a different discrete
compressor layout is sized), fO_inlet 0.426583 -> 0.416795, fO2_inlet 0.065843 -> 0.075631.
gas_path A1.3: C_D same, drag_mN 24.3327 -> 22.5115, P_comp_W 13.7285 -> 13.4490, p_in_Pa 0.0883003 -> 0.0882068,
fO_inlet / fO2_inlet ~1e-4 relative.
accelerators (gas state from make_gas_fn): ecr_grids T_N 0.0299259 -> 0.0299443, P_acc_W 1456.93 -> 1455.54,
life_h 6310.98 -> 6303.34, chi 0.48956 -> 0.49068; ecr_hall T_N 0.0203156 -> 0.0203223, chi 0.062219 -> 0.062335;
ecr_nozzle T_N 0.00239815 -> 0.00239788, chi 0.198338 -> 0.198687 (all < 0.25 %).
architecture_closure ext_hall_2p5kW: T_over_D_sc 1.73079 -> 1.84456 (+6.6 %, lower intake drag), T_mN 51.10994 ->
51.11012, P_bus_W 2461.33 -> 2461.07, m_system_kg 108.789 -> 108.787, Q_waste_W 752.95 -> 752.67 (status unchanged).
mission: mission_4000h D_mean_mN = T_mean_mN 30.765 -> 28.923, P_bus_mean_W 1765.80 -> 1698.88, P_bus_peak_W
1844.09 -> 1776.57; map_T_N relative changes <= 2e-5. (hall / source_plasma entries differ only at ~1e-16 float noise
from regeneration.) These are historical 0-D/withdrawn-Hall benchmarks: the moved absolute values remain non-quotable
per CLAUDE.md "Superseded / withdrawn".
Downstream (owned by other steps): design-synthesis F1 (F1-01 now FIXED in production; `species_c_d_recombination_bias`
"IntakeSurface_convention" describes the legacy method), F3/F4/F7-F9 and the freeze candidate (MCC/F1 status, any
artifact using `intake.collection` with use_tpmc), `scripts/architecture/build_feed_envelope.py` and the feed-state
closure / feed-envelope artifacts (C_D, drag, passive CR, compressor sizing move). S2.2 (frozen surface v2) follows.
Review fix (2026-10-01, findings D-04 / N3, D-07 / N6): the third S2.1 requirement is now implemented in the chain.
`system.evaluate` builds the compressor / reservoir inflow (gas-path physics) and the thruster inlet composition (both
branches, through `aochem.inlet_composition`) from `intake.collection`'s `mdot_collected_species` (species-resolved
eta_c,s) instead of splitting the total by free-stream mass fractions; the parametric intake (no species rows) keeps the
free-stream split. New outputs `fO_collected`, `fN2_collected`, `fO2_collected`, `collected_composition_basis`. The total
collected flow is unchanged. At 200 km mean, area 0.7 m², alpha 0.8, L/d 5 the collected O mass fraction is 0.440
(free stream 0.461, -4.5 %), N2 0.527 (0.508). `IntakeSurface` on a species-resolved table now refuses a call without
fractions (the hard-coded O 0.45 / N2 0.50 / O2 0.05 fallback is removed) and refuses non-finite, negative, non-numeric
or all-zero fractions (previously zeros/NaN were returned and a negative fraction inflated the outputs);
`uq6.evaluate_full` relied on the removed fallback and now passes the atmosphere's free-stream fractions explicitly.
No coefficient retuned. Golden impact (regenerated with `python -m abep_sim.golden generate`; old -> new):
gas_path A0.7: fO_inlet 0.416795 -> 0.397834, fO2_inlet 0.0756306 -> 0.0755668, p_in_Pa 0.0500123 -> 0.0498443,
P_comp_W 26.0544 -> 26.6473, m_comp_kg 6.66525 -> 6.66722 (C_D, drag, eta_c, mdot unchanged).
gas_path A1.3: fO_inlet 0.400743 -> 0.382565, fO2_inlet 0.0916825 -> 0.0908357, p_in_Pa 0.0882068 -> 0.0877604,
P_comp_W 13.4490 -> 13.4792.
accelerators (gas state from make_gas_fn, composition moves): ecr_grids T_N 0.0299443 -> 0.0300371, P_acc_W 1455.54 ->
1454.33, I_beam_A 1.45325 -> 1.45204, P_hat 0.695243 -> 0.697233, chi 0.490685 -> 0.494153, f_cx 1.34075e-3 ->
1.34047e-3, life_h 6303.34 -> 6278.59; ecr_hall T_N 0.0203223 -> 0.0205279, P_acc_W 913.768 -> 919.722, I_beam_A
1.99867 -> 2.00838, P_neut_W 34.5975 -> 34.5513, chi 0.0623352 -> 0.0622771; ecr_nozzle T_N 2.39788e-3 -> 2.37458e-3,
E_i_eV 23.8464 -> 23.7182, chi 0.198687 -> 0.198143.
architecture_closure ext_hall_2p5kW: T_mN 51.1101 -> 51.2734, T_over_D_sc 1.84456 -> 1.85045, P_bus_W 2461.07 ->
2458.73, P_jet_W 1272.47 -> 1269.04, Q_waste_W 752.670 -> 753.317, A_rad_m2 1.26371 -> 1.26510, CBE_kg 59.6941 ->
59.6647, MEV_kg 69.7345 -> 69.7005, m_system_kg 108.787 -> 108.753, ledger_resid 0 -> 1.8e-16 (round-off, ATOL);
status 'OK' -> 'MODEL_NOT_CONVERGED' (S2.4 review fix).
mission: map_T_N 0.3: 4.57300e-3 -> 4.87754e-3 (+6.7 %), 0.45: 0.0141590 -> 0.0145528, 0.6: 0.0241975 -> 0.0245690,
0.75: 0.0342445 -> 0.0345544, 0.9: 0.0443415 -> 0.0445677, 1.0: 0.0511101 -> 0.0512734, 1.15: 0.0613066 -> 0.0613703,
1.3: 0.0715254 -> 0.0714882, 1.5: 0.0851279 -> 0.0849605; mission_4000h P_bus_mean_W 1698.88 -> 1693.56, P_bus_peak_W
1776.57 -> 1770.63 (D_mean / T_mean / closure unchanged). Withdrawn-Hall benchmarks: values remain non-quotable.
Downstream (owned by other steps; not regenerated here): every artifact built from `system.evaluate` / `gas_path_state`
on the TPMC path (F3/F4/F7-F9, freeze candidate, feed-envelope / feed-state-closure, compressor downselect).

## 2026-10-01 — A9.9 S2.2 F1Q-04: intake surface v2 build specification (build BLOCKED) + v1 fail-closed domain

What: new `abep_sim/intake_surface_v2_spec.py` records the v2 build specification required by owner decision A9.9 S2.2
(species-resolved; Maxwell and CLL as separate scenarios; deterministic order-independent seeds `point_seed`; the
unresolved-particle criterion of `intake_tpmc` plus the gate-5 cross-check tolerance; per-row unresolved/convergence
information; provenance and hashes; direct-TPMC cross-check at build and held-out states; fail closed outside the domain;
v1 retained unchanged; production switch only after verification). Its angular axis is `TBD_AOCS_POINTING_ENVELOPE`
(A9.13 S6.2: v2 must cover the REGISTERED spacecraft/AOCS relative-wind pointing envelope, which is not registered), and
the other axes (atmosphere state, L/d, phi, alpha, n_per_point) carry `TBD_REGISTRATION` — no grid values invented.
`build_intake_surface_v2()` refuses (`BLOCKED_PENDING_AOCS_POINTING_ENVELOPE`). No surface was built; `intake_surface_v1.*`
unchanged.
v1 fail-closed check: `IntakeSurface` already refused (ValueError) any L/d, phi, alpha or theta outside the frozen bounds,
including non-finite inputs; that is recorded, not changed. Behaviour changes (silent substitutions removed):
`intake.collection` no longer evaluates `min(off_axis_deg, 5)` or clips accommodation to [0, 1] before the surface
(finding FE-01; A9.13 S6.2 "never extrapolate silently beyond the frozen angular domain") — out-of-domain pointing or
accommodation now raises; `IntakeSurface` refuses a non-finite interpolated value and a species with non-zero fraction
that is not in the table (previously dropped and renormalised away); `IntakeSurface.domain()` reports the frozen axes and
states that the free-stream state is not a v1 axis. The fixed-composition fallback for a call without fractions is
unchanged (out of scope here). Owner decisions: A9.9 S2.2, A9.13 S6.2. Golden impact: none (`golden check` OK); all
in-domain values bit-identical.
Review fix (2026-10-01, findings D-08, D-09): the intake.collection pointing/accommodation clamp removal (FE-01) now also
has its own dated entry at the end of this file. `mission5.run_phase5` and `mission5.run_mission_generic` no longer pass
`accommodation=min(alpha, 1.0)` for the AO-aged alpha: it goes to the intake unclipped and IntakeSurface refuses an
out-of-domain value (surface_ageing_alpha is a convex blend of alpha0 and alpha_inf, so in-domain values are identical).
Golden impact: none.

## 2026-10-01 — A9.9 S2.5 MCC-05: positive-integer hit budgets in intake_tpmc (separate record)

Owner decision A9.9 S2.5 MCC-05 ("document each change separately"; review finding D-09). Recorded separately from the
combined MCC-05/06/07 entry above, which is kept as written. `intake_tpmc.trace_channel` validates `max_hits` and
`max_hits_cap` as positive integers (bool, float, <= 0 rejected with ValueError) and `unresolved_tol` as finite >= 0
before any particle is sampled, so `max_hits < 1` can no longer loop forever. `max_hits_cap = 0` (the DIV-04 reference
behaviour) is refused by the reference too. Valid-input numerics bit-identical. Golden impact: none.

## 2026-10-01 — A9.9 S2.5 MCC-06: explicit wall-scattering model selection in intake_tpmc (separate record)

Owner decision A9.9 S2.5 MCC-06 (review finding D-09; see the combined entry above). `scattering` must be exactly
"maxwell" or "cll" in `trace_channel`, `intake_response` and `response_surface`; anything else raises instead of tracing
Maxwell silently. The thermal back-trace in `clausing_transmission` selects Maxwell explicitly (`K_BACK_SCATTERING`,
same behaviour as before), recorded as `K_back_scattering`. Valid-input numerics bit-identical. Golden impact: none.

## 2026-10-01 — A9.9 S2.5 MCC-07: CLL / Maxwell accommodation coefficients validated in intake_tpmc (separate record)

Owner decision A9.9 S2.5 MCC-07 (review finding D-09; see the combined entry above). CLL `alpha_n` / `alpha_t` (each
defaulting to `alpha`) and the Maxwell diffuse fraction `alpha` must be finite and inside [0, 1]; NaN, ±inf or
out-of-range values raise in `trace_channel` and again at the `_cll` kernel entry, never clipped. Valid-input numerics
bit-identical. Golden impact: none.

## 2026-10-01 — A9.13 S6.2 / FE-01: intake.collection pointing and accommodation clamp removed (separate record)

Owner decision A9.13 S6.2 ("never extrapolate silently beyond the frozen angular domain"; finding FE-01; review finding
D-09). Recorded separately from the S2.2 entry above, where it was first logged. Until 2026-10-01 `intake.collection`
evaluated the frozen surface at `min(off_axis_deg, 5)` and with accommodation clipped to [0, 1]; both now go to
`IntakeSurface` as given, and anything outside the frozen domain raises. The same applies to the AO-aged accommodation in
`mission5` (review fix D-08). Golden impact: none (all golden states are inside the domain).
## 2026-10-01 — A9.17 DATA_SIZE / ORBIT applied to `atmosphere_msis21_orbit_v1` (storage + labels; content unchanged)

Authority: `docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json` (sha256 9fd77c95…c3ad; verbatim
`OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md`, sha256 540212c0…ba13), decision keys DATA_SIZE and ORBIT.

- **One canonical compressed copy.** The 17.2 MB `atmosphere_msis21_orbit_v1.csv` is replaced by
  `atmosphere_msis21_orbit_v1.csv.gz` (4.6 MB; deterministic gzip: explicit header, MTIME 0, no file name, XFL 2, OS 255,
  raw deflate level 9). The decompressed bytes are identical to the v1 CSV: sha256
  c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164, unchanged, checked byte-for-byte against the
  committed blob. The manifest JSON now records both the uncompressed-CSV sha256 (`sha256`, the dataset identity) and
  the container sha256 (`container.sha256` 71ce01c3…8ace, zlib 1.3). The accessor reads the .gz and verifies both hashes
  on load. `build` writes the .gz. `check` verifies both hashes, re-encodes the CSV, and re-runs the pymsis subset (OK).
  `correct-metadata` repacks a legacy CSV and applies errata E3/E4. No MSIS re-run was needed; the data did not change.
- **Excluded from the installed package.** No installed production module imports `abep_sim.atmosphere_orbit`.
  `pyproject.toml` package-data is now an explicit file list (the frozen orbit-averaged v1 atmosphere, intake surface,
  goldens and rate tables still ship). `exclude-package-data` and `MANIFEST.in exclude` drop `atmosphere_msis21_orbit_v1*`;
  a wheel and an sdist built locally were verified to omit the files. Without the data the accessor raises
  FileNotFoundError naming `abep_sim/data/atmosphere_msis21_orbit_v1.csv.gz`; there is no fallback.
- **Orbit labels.** The mission_env 96.3° / dawn-dusk orbit is labelled `CODE_DEFAULT / PARAMETRIC` (never a requirement
  input; inclination and LTAN TBD from the official mission ICD). This applies to the manifest `orbit_coverage`,
  `mission_env_orbit_assumption`, the `orbit_states` per-state status and the design-state rule and `orbit_basis`. The
  design-states file was regenerated with **label changes only**: the 179 per-state records were kept verbatim, and the
  content hash is pinned in the tests.
- Open (not changed here): (1) the v1 design-state latitude bound (|lat| ≤ 83.75°) comes from the code-default SSO
  family. Inclinations between ~83.75° and ~96.25° reach higher latitudes; the grid covers them, the design-state set
  does not. (2) Per-state `interp_max_rel_err_rho` is null for the 26 interpolated boundary design states, a v1 build
  ordering defect recorded in E4. Both are for the next design-state version.

## 2026-10-01 — A9.17 ORBIT repair (PKG-1): versioned broad-envelope design-state set v2 (v1 files unchanged)

Authority: `docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json` (sha256 9fd77c95…c3ad), decision key
ORBIT ("Keep the atmosphere/design-state envelope broad enough until DRDO, the spacecraft ICD, or the PDR mission
definition supplies the real inclination and LTAN"). Review finding PKG-1: the previous entry relabelled the 83.75° bound,
but the code-default SSO family still set the only design-state envelope.

- New file `abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json`, written by `python -m abep_sim.atmosphere_orbit
  design-states-v2` (deterministic; refuses to overwrite a file with different content).
  - Candidate pool: every doy / longitude / local-time node at every integer latitude −90…90°. All 19 latitude nodes are
    included, poles too. Off-node latitudes use the accessor's own latitude interpolation, and each such state carries its
    recorded interpolation error.
  - The pool does not use `mission_env.sso_inclination_deg`: a test swaps that default and reproduces the file.
  - Same selection rule as v1. The set has 196 states.
  - The envelope now includes the polar extrema, e.g. T max 1824.27 K at −87° (v1: 1820.38 K).
  - Refining the latitude step to 0.25° changes the extrema by ≤ 5.5e-4 relative (recorded in the file). v2 matches or
    exceeds every v1 envelope extremum within that tolerance.
- `load_design_states()` now defaults to v2; `load_design_states("v1")` returns the immutable v1 set. The manifest gains
  `design_states_file_v2` and erratum E5, and `orbit_coverage.design_state_envelope.latitude_status` is RESOLVED. `check`
  reproduces v2 byte for byte (OK).
- Unchanged, and hash-pinned in the tests: the dataset (uncompressed CSV sha256 c0ce282e…6164, container 71ce01c3…8ace)
  and the v1 design-state file (sha256 d8bd369b…a40). The existing `atmosphere_msis21_orbit_v1*` glob keeps v2 out of
  the installed package.

## 2026-10-01 — A9.17 WINDS: atmosphere v2 with HWM14 neutral winds (`atmosphere_msis21_hwm14_orbit_v2`; v1 unchanged)

Authority: `docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json` (sha256 9fd77c95…c3ad). Decision key
WINDS (`AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE`); ORBIT and DATA_SIZE from the same record also apply. Status:
**DESIGN_ENVELOPE_PARAMETRIC**. This is not a mission trajectory.

- **Source.** HWM14 version HWM14.123114 comes from the NRL public repository
  (`https://map.nrl.navy.mil/map/pub/nrl/HWM/HWM14/`). The package is `HWM14_ess224-sup-0002-supinfo.tgz` (sha256
  4de451be…7978), Software S1 of Drob et al. 2015, ESS, doi:10.1002/2014EA000089. The register in `docs/evidence/hwm14/`
  records the sha256 of every file, the CCMC page, the terms found, and why PyPI `pyhwm2014` 1.1 was rejected (no
  coefficient files; built with `numpy.distutils`).
  - The repository redistributes no HWM14 code or data. `fetch-hwm14` downloads the package and verifies every hash.
  - Usage terms are not explicit: the package has no licence text, and the article is CC BY-NC-ND. Recorded as open
    (TERMS_NOT_EXPLICIT, verify).
- **Build validation.** gfortran 13.3.0, default flags. NRL's `checkhwm14` output is text-identical to the shipped
  `Check/gfortran.txt`. Every build and every HWM14-enabled `check` repeats this comparison and refuses on any difference.
- **Content.**
  - (1) Node table on the v1 grid and v1 scenarios. The grid is imported from `atmosphere_orbit`. For each node it stores
    the HWM14 total and quiet meridional/zonal wind, plus the exact HWM14 inputs: iyd, UT seconds, geodetic coordinates
    and ap(2) = the scenario's ECSS Ap held constant as the 3-hour ap (0/15/45/240 → Kp 0/3/4.89/8.35).
  - (2) DWM07 disturbance table on lat 5° × lon 15° × LST 1 h × the 8 v1 doy nodes (681,984 rows). The v1 grid alone gave
    joint errors up to 143 m/s at ECSS short-term high, because DWM07 follows magnetic coordinates. DWM07 varies by
    ≤ 6.7e-4 m/s between 180 and 230 km (measured).
  - Thermodynamic state: v1 through its unchanged accessor, pinned by sha256 c0ce282e…6164. The NRLMSIS table is not
    stored a second time.
- **Measured interpolation error** (1500 random points per scenario vs direct HWM14), max |wind-vector error|: 5.6 / 4.9 /
  7.6 / 14.4 m/s for LT low / moderate / high and ST high. The resulting error in the wind-inclusive relative speed is
  ≤ 13.7 m/s; in the flow angle, ≤ 0.09°.
- **API.**
  - `wind`, `state`: v1 state plus winds. Out-of-domain inputs are refused.
  - `relative_flow`: for a caller-supplied inertial ENU velocity, returns (a) relative speed and angles against the
    co-rotating atmosphere and (b) the same with co-rotation + HWM14 wind.
  - `orbit_states`: the v1 geometry. Inclination and LTAN are required inputs with no defaults, and the co-rotating
    speed reproduces v1 within 1e-6 m/s.
- **Storage.** Two deterministic gzip files (2.4 MB + 8.4 MB) plus a manifest. A rebuild is byte-identical, JSON
  included. The files are excluded from the wheel through `pyproject` `exclude-package-data`.
- **Open items.**
  - `MANIFEST.in` still pulls the 28 KB manifest JSON into the sdist; it needs an `exclude` line, and that file is
    outside this lane.
  - `tests/test_atmosphere_orbit.py::test_not_wired_into_existing_modules` fails, because it forbids any
    `atmosphere_orbit` reference outside v1 and v2 must import v1. The fix is to exempt `atmosphere_orbit_v2.py`; that
    file is outside this lane.
  - `tests/test_packaging.py` hard-codes v1 as the only repository-only dataset, so three of its tests fail:
    `test_package_data_covers_abep_sim_data`, `test_orbit_dataset_excluded_from_distribution` and
    `test_manifest_in_carries_data`, the last because of the new `.gz` suffix under `recursive-include`. The fix is to add
    the v2 glob next to `REPO_ONLY_GLOB` and to `MANIFEST.in`; both files are outside this lane. Built with `python -m
    build`: the wheel contains no v2 data; the sdist contains only the manifest JSON.
  - No wind-specific design-state set exists, because the relative-flow extremes depend on the TBD orbit.

## 2026-10-01 — A9.17 WINDS repair: review findings HWM-2 / HWM-3 fixed (manifest rebuilt; wind tables byte-identical)

Authority: `docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json` (sha256 9fd77c95…c3ad), decision key
WINDS (`AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE`) and DATA_SIZE. These are repairs from the review of the A9.17 WINDS
commit (dcd3ef9). They change text in the module and in the manifest JSON. HWM14 output is unchanged.

- **HWM-3 (misquote).** `NOT_PROVIDED.disturbance_wind_height_dependence` claimed that DWM07 is height-constant only
  above ~225 km and that 180-230 km "lies inside that transition". The README in the NRL package (sha256 14b6e5e4…9b15,
  MODEL LIMITATIONS) says something different. Its exact words: the disturbed part "represents average disturbance winds
  in the upper thermosphere (above 225 km)", and "The disturbance winds are assumed to be constant with height, with a
  smooth artificial cutoff below 125 km". The entry now quotes those phrases verbatim (`DWM07_README_QUOTE`). It states
  that DWM07 is height-constant by construction and that the README describes no transition. It also states that using
  DWM07 unchanged at 180-225 km extrapolates beyond what the source model represents (verify; not quantified). When
  HWM14 is available, a test checks the quotes against the NRL README.
- **HWM-2 (false distribution claim).** The manifest claimed "EXCLUDED (pyproject exclude-package-data + MANIFEST.in
  exclude)", but no such MANIFEST.in exclude exists. The `distribution` record now holds `installed_wheel` (excluded
  through pyproject) and `sdist`. The `sdist` text says the two .csv.gz tables are not carried, and that at this build
  MANIFEST.in had no v2 exclude, so the sdist carried the manifest JSON. A new `distribution_snapshot_at_build` is
  computed from the real pyproject.toml/MANIFEST.in by `distribution_snapshot()`, a pure file inspection. Tests check the
  statement against the snapshot. `check()` adds a note when the packaging files change after the build.
- **Rebuild.** `ABEP_HWM14_DIR=<verified NRL package> python -m abep_sim.atmosphere_orbit_v2 build`. Both .csv.gz
  containers are byte-identical to dcd3ef9 (same uncompressed-CSV sha256 6d9e4f7a…1969 / 040befc5…8609). Only the
  manifest JSON changed. The NRL checkhwm14 output is again text-identical to `Check/gfortran.txt`.
- **HWM-1 (red suite): not fixed in this lane.** The fix needs edits to `tests/test_atmosphere_orbit.py`,
  `tests/test_packaging.py` and `MANIFEST.in`, and all three are outside this lane's allowed paths. Nothing inside the
  allowed paths can fix it legitimately: the brief requires v2 to import the v1 grid, and the data paths are fixed. A
  verified patch was handed to the orchestrator. It exempts `atmosphere_orbit_v2.py` and adds the v2 glob to
  `REPO_ONLY_GLOBS` plus a `MANIFEST.in` exclude line. Do not merge until it is applied. Once that MANIFEST.in line is
  added, the manifest JSON will no longer be in the sdist. The `sdist` statement records the state at build time, so it
  stays true as a record of that build, and `check()` notes the change.
## 2026-10-01 — A9.17 sputter register regenerated under owner screening guardbands

Owner A9.17 (`docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json`, sha256 `9fd77c95…`, decision key
SPUTTER = FREEZE_SPUTTER_SCREEN_1_10_AND_1_25_PROSPECTIVELY). `docs/evidence/sputter_yields_v1/` register v1.1:
E_screen = 1.10 × E_threshold and F_worst = 1.25 are now owner constants in the builder inputs (`screening_guardbands`,
cross-checked against the decision's `owner_supplied_values` and sha256-pinned), replacing the lane-chosen builder
constants of the first build (1d595ad). Those values had been chosen after seeing the data, so the first build's results
are not pre-registered evidence; this regeneration applies the factors prospectively. Screening/down-selection only (the
APID-reproduction screen); never P4 material acceptance, lifetime or qualification (S5.12). Source data unchanged: the
inputs differ from the first build only by the inserted provenance block (a test restores the first-build sha256 by
removing it). Regenerated screening outcomes vs first build: IDENTICAL (4 APID rows, 0 differences); all records,
coverage cells and other checks unchanged. Minor fix: the CHK-MASS-RATIOS caption count is derived from the inputs.

## 2026-10-01 — A9.18 GOLDEN: new admissible converged golden (golden_v2); golden_v1 point kept as non-converged reference

Owner decision A9.18 GOLDEN (`docs/decisions/OD_2026_10_01_A9_18_GOLDEN_AND_BASELINE_OWNER_DECISIONS.md`, item 1:
`NEW_ADMISSIBLE_CONVERGED_GOLDEN; RETAIN_OLD_AS_NONCONVERGED_REGRESSION_REFERENCE`). Why: after A9.9 S2.4/S2.5 the golden_v1
gas-path-dependent cases sit on non-admissible states — architecture_closure / mission at intake area 1.3 m², p_level
0.05 Pa (orifice setpoint unbracketed, G-05; Gaede OUT_OF_MODEL_DOMAIN, MCC-02; status MODEL_NOT_CONVERGED), gas_path
A0.7 / A1.3 at the default 3 × p_min setpoint (orifice unbracketed), and accelerators on `make_gas_fn()(0.7, "nominal")`
(the same unbracketed A0.7 state). A non-converged canonical golden conflicts with the fail-closed convergence policy.
What:
- `abep_sim/golden.py` now reads/writes `abep_sim/data/golden_v2.json` (`GOLDEN_FILE`); `golden_v1.json` is unchanged
  (sha256 1f7fbb62…) and kept as history. CLAUDE.md still names golden_v1.json in rule 1; not edited here (owner's file).
- Regression fixture `cases.nonconverged_reference` (role NONCONVERGED_REFERENCE, expectation EXPECTED_NONCONVERGENCE):
  the golden_v1 gas_path, accelerators, architecture_closure and mission values verbatim (copied from golden_v1.json, not
  recomputed), plus refusal labels. `golden check` recomputes them at the old inputs, compares to 1e-6 and fails if any
  is no longer refused (gas_path MODEL_NOT_CONVERGED / chk_compressor_feasible False; closure and mission status
  MODEL_NOT_CONVERGED, evidence_admissible False, feasible False).
- Selection rule A9.18-SEL-1 FIRST_ADMISSIBLE_IN_DEFAULT_GRID_ORDER: walk the default `close_architecture` gas grid
  (area [0.6, 0.7, 0.85] m² × p_level [0.02, 0.05, 0.1] Pa) in the solver's own loop order (area outer, p_level inner)
  and take the first admissible point. Admissible = inputs pass validation; frozen NRLMSIS + frozen TPMC surface; G-03,
  G-04 converged; G-05 converged and bracketed; Gaede in domain with unclipped K_min >= 1; compressor sized (no unsized
  fallback); rotor inside the labelled legacy cap; and `close_architecture` at that one point closes (status OK or
  PARAMETRIC_SENSITIVITY, closes_constraints, |ledger_resid| < 2 %). Neutral: the grid and order are fixed by the code
  before any result is seen and only pass/fail verdicts are read (no performance optimum, no fit to v1 numbers). Visited:
  0.6/0.02 GASPATH_MODEL_NOT_CONVERGED, 0.6/0.05 and 0.6/0.1 CLOSURE_INFEASIBLE (mission envelope), 0.7/0.02
  GASPATH_MODEL_NOT_CONVERGED, **0.7 m² / 0.05 Pa ADMISSIBLE** (full scan in provenance: 0.7/0.1 and 0.85/0.1 also
  admissible; 0.85/0.02, 0.85/0.05 not converged). Cross-check (not used to choose): the admissible point closest to the
  v1 point (same p_level first, then smallest |Δarea|) is the same point.
- Rotor: no rotor-strength basis is registered, so the new point carries `comp_rotor_qualification =
  NOT_EVALUATED_MATERIAL_BASIS`, `comp_sizing_mode = PARAMETRIC_SENSITIVITY`, closure / mission status and evidence class
  PARAMETRIC_SENSITIVITY, feasible False. A9.9 S2.3 allows exploring a rotor as PARAMETRIC_SENSITIVITY and forbids only a
  qualified rotor_ok; the golden checks reproducibility of a converged numerical state, not qualification, so it carries
  this labelled state (not design evidence).
- New canonical cases at the selected point: `design_point_selection` (rule id, grid, visited verdicts, selected point;
  re-run by check), `gas_path` (`A0.7_p0.05`, values plus G-03..G-05 / MCC-02 / S2.3 labels), `accelerators` (gas state
  `make_gas_fn()(0.7, 0.05)`), `architecture_closure`, `mission` (same architecture, 2.5 kW constraint, spacecraft and
  mission settings as golden_v1; only the gas point changed). atmosphere, intake, source_plasma, hall are unchanged.
- Provenance block: owner decision, previous golden sha256, sha256 of the frozen inputs (atmosphere_msis21_v1.{csv,json},
  intake_surface_v1.{csv,json}), git HEAD at generation + modified paths, python/numpy/pandas/scipy versions, selection
  rule, admissibility criteria, full grid scan, rotor label. Regenerated with `python -m abep_sim.golden generate`;
  `golden check` → OK (runtime about 3.3 min, was about 1 min, because the selection closures and the fixture run too).
Old (golden_v1, non-converged 1.3 m² / 0.05 Pa) -> new (golden_v2, 0.7 m² / 0.05 Pa):
architecture_closure ext_hall_2p5kW: status MODEL_NOT_CONVERGED -> PARAMETRIC_SENSITIVITY, x_Vd 300 -> 325, x_L_ch 0.12
-> 0.20, T_mN 51.273 -> 22.320, P_bus_W 2458.73 -> 1183.34, P_jet_W 1269.04 -> 568.67, T_over_D_sc 1.8505 -> 1.3321,
Q_waste_W 753.32 -> 400.42, A_rad_m2 1.2651 -> 0.5058, A_array_m2 12.204 -> 8.221, CBE_kg 59.665 -> 42.949, MEV_kg
69.700 -> 49.880, m_system_kg 108.753 -> 76.186, ledger_resid 1.8e-16 -> -1.9e-16 (round-off), life_sys_h 28225.4 and
xe_kg 5.616 unchanged.
mission: mission_4000h D_mean_mN = T_mean_mN 28.923 -> 17.490, P_bus_mean_W 1693.56 -> 1014.85, P_bus_peak_W 1770.63 ->
1059.25 (mission_closed True, min_alt 200 km, fired 3996 h, AO fluence unchanged); map_T_N (N) 0.3: 4.8775e-3 ->
1.0745e-3, 0.45: 0.014553 -> 0.005005, 0.6: 0.024569 -> 0.009588, 0.75: 0.034554 -> 0.014331, 0.9: 0.044568 -> 0.019115,
1.0: 0.051273 -> 0.022320, 1.15: 0.061370 -> 0.027151, 1.3: 0.071488 -> 0.032013, 1.5: 0.084960 -> 0.038533.
gas_path A0.7 (default setpoint, unbracketed) -> A0.7_p0.05 (converged): p_in_Pa 0.0498443 -> 0.0500000, fO_inlet
0.397834 -> 0.397816, fO2_inlet 0.0755668 -> 0.0755844, mdot_air_mgps 0.97534260 -> 0.97534259; C_D, eta_c, drag,
P_comp_W 26.647, m_comp_kg 6.667, m_intake_kg unchanged (same sized compressor layout). gas_path A1.3 is now only in the
fixture.
accelerators (gas state 0.7/'nominal' -> 0.7/0.05 Pa; all < 1e-4 relative): ecr_grids T_N 0.03003709 -> 0.03003730,
P_acc_W 1454.333 -> 1454.339, life_h 6278.59 -> 6278.58; ecr_hall T_N 0.02052792 -> 0.02052743, P_acc_W 919.722 ->
919.703; ecr_nozzle T_N 2.374578e-3 -> 2.374599e-3.
These remain historical 0-D / withdrawn-Hall benchmarks (CLAUDE.md "Superseded / withdrawn"): reproducibility references,
not quotable performance. Tests: new `tests/test_golden_a9_18.py`; `tests/test_golden_cli.py` now points at golden_v2.json
(path only). Docs: `docs/ci/CI.md`, `docs/ci/PACKAGING.md` (golden file note). Not changed (other owners):
`docs/traceability/RTM.md` / `build_rtm.py` still cite golden_v1.json as evidence. The dedicated performance-baseline rerun
(A9.18 item 2) waits for the step-3 merge and is not part of this change.
## 2026-10-01 — A9.17 CI repair: portable check mode for the orbit atmosphere (no extra skips; v1 data untouched)

Cause of the red CI (both legs, since the orbit atmosphere landed):
- **pymsis-present leg.** `test_check_mode_reproduces_subset` failed with "812 of 1204 recomputed subset rows differ"
  on every GitHub runner. The wheel is the same here and in CI (pymsis 0.13.0 cp311 PyPI wheel, msis21f .so sha256
  3bf5b39c…). That wheel evaluates NRLMSIS 2.1 in **single precision**: the stored values are exact float32 numbers. It
  also forms reciprocals with `rcpps` plus one Newton step (39 sites, GCC `-mrecip` code). `rcpps` bits depend on the CPU
  implementation (Intel vs AMD), so byte identity at `%.6e` only holds on the build CPU (Intel Xeon). That CPU re-runs
  byte-identically, even with the glibc AVX512/AVX2/FMA dispatch masked.
- **pymsis-absent leg / HWM14.** Three `importorskip("pymsis")` tests and three `pytest.skip` (HWM14 unavailable) tests
  added extra skips, which break rule 9.

Measurement (the tolerance basis). The 1204-row subset was re-run under qemu-x86_64 8.2.2. QEMU's TCG computes `rcpps` as
an exact reciprocal, which gives a second `rcpps` implementation on the identical wheel. Against native Intel, on raw
outputs: max relative difference 7.69e-6 (He/O, 125 float32 ulps); rho/N2/O2/Ar/N ≤ 3.96e-6 (≤ 65 ulps); T_K 0.
960/1204 printed rows differ (CI: 812). This is float32 round-off amplified by the exponential profiles, not a model
difference. Under qemu, the full `check()` with the new criterion returns OK (0 rows beyond tolerance).

Changes (`abep_sim/atmosphere_orbit.py`). The tolerance lives in a code constant, never in the manifest.
- The producer re-run passes when the input columns are byte-identical and every output column is within
  `CHECK_REL_TOL` = 2 × 7.69e-6 + 2 × 5e-7 (the `%.6e` half unit, each side) = 1.638e-5.
- Byte/hash identity is still reported (`producer_rerun.subset_sha256_matches_record`, plus a note), as information.
- `check()` reports the max relative difference per column. A re-run beyond the tolerance is a FAIL; never widen the
  tolerance.
- Without pymsis, `check()` runs every frozen-data check and reports `producer_rerun.status = NOT_RUN` with the reason
  (as v2 does for HWM14).
- `_metadata` no longer imports pymsis. `build()` still requires the recorded version.

Latent issue found and fixed in the same way. `check()` also compared `design_states_v2` byte-for-byte, and the test
compared it with exact `==`. Neither had run in CI before: the branch was gated behind the failing subset, and the absent
leg skipped. `design_states_v2` is pure float64 numpy, but numpy dispatches its SIMD kernels by CPU. With
`NPY_DISABLE_CPU_FEATURES=X86_V4` (AVX2 kernels), 163 floats differ by ≤ 4.19e-16 relative, with identical
structure/ids/labels. Under qemu (baseline-SSE numpy, non-FMA libm), 1299 floats differ by ≤ 1.42e-14. New rule: structure, ids, labels and all non-float values exact; floats within
`DESIGN_V2_REL_TOL` = 1e-12; a note when not byte-identical.

Tests. The pymsis/HWM14-dependent tests in `tests/test_atmosphere_orbit*.py` branch inside the test, following the
existing `test_sim.py` pattern, instead of skipping:
- Dependency present: same comparisons as before.
- Dependency absent: they assert the clean refusal (`NOT_RUN` / `SKIPPED` with the reason, `ImportError` /
  `HWM14Unavailable`) and the frozen-data results.
- New dependency-free tests pin the tolerance constants and exercise the subset and design-v2 comparators.

Unchanged: dataset identity (uncompressed CSV sha256 c0ce282e…6164), every file in `abep_sim/data/`, the v2 wind check
(already tolerance-based).

## 2026-10-01 — A9.14 S10.4: abep_core parity re-registration v2 (reference re-pin after A9.9)

Owner decisions A9.14 S10.4 RUST-OQ-02 (`OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`) and S10.3 RUST-OQ-01
(`PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING`), `docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md`
(json sha256 c6c00b7f...); trigger A9.9 S2.5 MCC-05/06/07 and S2.1 F1Q-01
(`docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md`, json sha256 b6010d9d...). Closes downstream
finding N1 of the S2.5 entry. The A9.9 changes moved the canonical reference `abep_sim/intake_tpmc.py` from sha256
ea0100b9... (v1 pin) to dcddf947..., so the v1 campaign refused (REFUSED_REFERENCE_CHANGED) and `verify_abep_core
--check` / the Rust admission gate reported NOT_ADMITTED_BUILD.
- `docs/performance/abep_core/parity_prereg_v2.json` (sha256 98be24c1...) committed on its own (ce5b445) before any v2
  comparison: workloads, vectors, n, seeds (scoring 20261001), observables, exact invariants and tolerance
  |delta| <= 5 sqrt(se_py^2 + se_rust^2) / aggregate bound 4.0 copied unchanged from v1 (sha256 dd12856b...); only the
  reference pin changes. Records why (A9.9 reference change; step-2 bit-identity of valid-input trace numerics, commit
  153c013) and why the v1 seed is kept (no parameter change, no NOT_ADMITTED verdict to follow).
- `scripts/verify_abep_core.py` and `abep_sim/design/tpmc_backend.py` read v2 (48ce61b, committed before the campaign so
  the recorded wrapper sha256 is final); `parity_prereg_v1.json` / `parity_report_v1.*` are unchanged history.
- Campaign (abep_core rebuilt from the unchanged sources with rustc 1.94.1 / maturin 1.15.0; extension sha256 eb586f03...,
  identical to the v1 build): wall time 110.3 s (K4 69.0 s, K5 34.8 s). Verdicts K1_entry, K2_diffuse, K3_cll, K4_trace,
  K5_clausing all ADMITTED (0 OUTSIDE, 0 DISAGREE_EXACT, every aggregate <= 1.38, every exact invariant held in both
  backends). Informational v1 cross-check: all 4709 stored test numbers equal v1 bitwise for both backends. Measured
  speed-up (informational, shared machine, load ~5): kernel-only W1 7.5x / W2 10.1x; served path W1 8.2x / W2 9.0x.
- ADMITTED keeps its v1 meaning: optional, explicitly selected `backend='rust'` inside the tested parity domain; default
  stays `python`; frozen data, goldens and score-bearing evidence come from the Python reference (A9.14 S10.3).
- Open (outside this lane's paths): `.github/workflows/rust-parity.yml` and `tests/test_rust_ci_workflow.py` still read
  the v1 records (`test_source_status_entry_point` compares the v2 `--source-status` output with the v1 report and fails;
  the workflow's reference-pin step compares against `parity_prereg_v1`). They need re-pointing to v2 by the Rust-CI owner.

## 2026-10-01 — Repair lane production_data_perf: S6.8 pressure domain in system.evaluate, golden Hall-calibration record, v1 W1/down-select history restored

- **PHY-02 (model change, A9.13 S6.8).** `system.evaluate` (wrapped by `archengine.make_gas_fn`) now labels a gas state
  `gaspath_domain_status = NOT_EVALUATED_OUT_OF_DOMAIN` (`gaspath_in_domain` False, `gaspath_out_of_domain` +
  `free_molecular_pressure_limit_0.1Pa`, compressor branch infeasible) when the setpoint `p_target_Pa` or the operating
  reservoir pressure exceeds the 0.1 Pa free-molecular limit (`system.P_FREE_MOLECULAR_LIMIT_PA`, equal to the design-layer
  constants; the reservoir pressure is compared within the orifice solver's own `ORIFICE_P_RTOL`, so a converged 0.1 Pa
  setpoint stays in domain). Before, 0.2 / 0.3 Pa states were `IN_DOMAIN`. New labels `gaspath_p_domain_max_Pa`,
  `gaspath_p_domain_limit_Pa`, `comp_sizing_p_out_Pa`, `comp_sizing_p_out_above_limit`. **Open for the owner:** the
  free-discharge outlet of the compressor sizing search (before the orifice throttles the reservoir to the setpoint) is
  0.1013 Pa at every default-grid point, including the golden point; it is reported, not gated. Gating it would leave the
  A9.18 grid with no admissible point (the golden would have to be re-decided). `golden check` stays OK (grid tops out at 0.1 Pa).
- **PHY-06 (A9.18 item 1).** `golden.HALL_CALIBRATION_DOMAIN` (status `RECORDED_NOT_GATING_OWNER_CONFIRMATION_REQUESTED`)
  states that the withdrawn 0-D Hall calibration envelope is not treated as part of the "registered model domain" for
  golden purposes, and that every closed default-grid point is an extrapolation (selected point 0.667 above the Isp
  envelope). `admissibility()` records `hall_calibration` / `hall_calibration_extrapolation`; the selection case and
  provenance carry them. golden_v2 regenerated (`python -m abep_sim.golden generate`): only these labels and the provenance
  code version are added; every value is unchanged (`check` before regeneration: OK).
- **SW-01.** a403fd7 had overwritten the sha256-pinned `feed_state_closure_v1.json` and `compressor_downselect_v1.json`
  (and their MDs). They are restored byte for byte from a403fd7^ (ff6e15db… / 79f6b28f…); the A9.16 regeneration is now
  `feed_state_closure_v2.json` / `FEED_STATE_CLOSURE_v2.md` and `compressor_downselect_v2.json` /
  `COMPRESSOR_DOWNSELECT_v2.md` (same schema ids). The down-select reads the v2 closure; F3 reads the v2 down-select
  (SRC-DOWNSELECT citation updated); F2 / F4 / F7-F8 / F9 rebuilt for the new input pins only. The immutable H2,
  M16-v2, phase-1 prereg and capability-demo builders are not re-pinned; `s1a_readiness_status_current.json`
  regenerated against the restored v1 (back to the sha M16-v2 pins).
- **SW-03 / PHY-07.** `test_orbit_dataset_excluded_from_distribution` checks imports of `abep_sim.atmosphere_orbit` with
  `ast` instead of a substring; the immutable A9.16 application-matrix token in `upstream_a9_13.py` stays.
- **SW-05.** `profile_baseline.source_drift` now fails a recorded file whose bytes differ from the last recorded
  new sha256; later drift is recorded in chained addenda (`DRIFT_AFTER_A9_18_REPAIR.json`: system.py, golden.py).
- **RVF-05.** `REGISTRATION_ADDENDUM_A9_18.json` supersedes the dedicated baseline's `ADMISSION_BASELINE_PERFORMANCE_ONLY`
  label for current use (`HISTORICAL_FOR_EARLIER_CODE_STATE`, Rust admission blocked until the A9.18 PERF_RERUN) and
  marks the baseline.md "shared machine" sentence as harness boilerplate (Windows CPU load 7 % / 1 %). Measured files untouched.

## 2026-10-02 — A9.19 / A9.20 integration after the A9.16 finalize merge

The three A9.19 / A9.20 lanes re-applied on the A9.16 finalize state (budgets 4cd79e6, RVM 1eb021c, design 56e7327) are
merged with `--no-ff`; every (B) repair is kept (RFP-01 RVM on the v3 artifacts, RVF-01 / PHY-01 domain-gated W1, S6.8
statuses). Integration fixes, all on the A9.19 rule "one Hall + one RF/ICP neutralizer, no conventional hollow cathode,
Xe CONTINGENCY_EMERGENCY, C1 GROUND_ONLY":
- **Hollow-cathode refusal vs the refreshed budgets.** The budgets lane now states the absence of C1 content explicitly
  (AL-07 "no C1 electronics - C1 is ground-only"; AL-08 `c1_branch.state = NO_C1_XE_BRANCH_IN_FLIGHT`, nothing booked).
  The optimizer refused those statements as C1 elements. `a9_19_architecture` adds `C1_DECLARED_ABSENT`: an element is
  only an absence statement when the text left after removing its "no C1 ..." / "C1 is ground-only" clauses carries no
  hollow-cathode marker (or the c1_branch is `NO_C1_*` and books nothing); the refusal re-verifies the label, so booked C1
  content is still refused. Absence statements are reported (`c1_absence_statements`) and keep the check clean.
  The ground reference's C1 floor text now lives in `retired_flight_configuration_history`; the optimizer reads it there
  (`ground_reference_lines`), so the AL-08 two-branch floor that may still embed the C1 cathode Xe branch (0.285 kg,
  budgets recorder flag) stays FLAGGED (`NO_HOLLOW_CATHODE_ELEMENT_LISTED_C1_PROVISIONS_FLAGGED_PENDING_BUDGET_REFRESH`)
  until the owner / quotations re-base AL-08. No number changes.
- **RVM.** The retirement label in Xe v3 is read where the budgets lane writes it
  (`propellant_policy.architecture.retired_flight_configuration`); `na_ground_reference` gets the builder namespace (not
  `sys.modules[__name__]`, which failed under the test loader). The C1 cells of rows whose evidence was a flight-budget
  probe are now `NOT_APPLICABLE_GROUND_REFERENCE` (never compliance evidence); tests read those cells accordingly.
- **Regenerated in dependency order:** RVM -> RFP registration (RVM-28..30 cross-references) -> A9.16 application matrix
  (record locations only) -> M16 v4 -> F7/F8 -> F9 freeze candidate (AFC-SY-XE-01 states the A9.19 Xe role; the A9.15
  "not a contingency" wording is superseded) -> H-1 freeze candidate (M16 v4 pin) -> decision dossier; the F0 performance
  MD re-rendered from its JSON (`--render-md`; live F3 / F7 counts after the S6.8 regeneration; no timing changed).
- **Immutable H2 v1 history restored (SW-02 re-homed).** 46ff2d1 had edited the H2-6 builder (SW-02: `--check` also runs
  `verify_sources`), but `docs/hardware/h2` is immutable H2 v1 history in the A9.10 reconciliation (byte-identical to
  ecdad06). The builder is restored byte for byte; the SW-02 guarantee moves to the CI static check `h2_6_live_sources`
  (`scripts/ci_checks.py`, docs/ci/CI.md), which runs `verify_sources()` on every push (and
  `test_h2_6_diagnostics_fixture::test_consumed_values_match_live_sources` in the suite).

## 2026-10-03 — Single flight configuration everywhere + AG-15 consumes the registered RFP (resumed step)

The step scripted in `docs/orchestration/workflow_scripts/a9-19-single-config-ag15.js` (cfd3d0e) never landed: the session
that launched it ended before its lanes merged. It was re-run from fd91185 as three isolated lanes and integrated here.
- **F9 / AG-15 (lane 3d4f447).** New `docs/architecture/freeze_candidate/ag15_f9.py` reads
  `docs/requirements/rfp_official/rfp_registration_v1.json` and the RVM re-base and checks them against each other (status,
  sha256, clause ids, clause hash, page/clause counts, every clause mapped or programmatic, every RVM origin known). AG-15 is
  now `RFP_REGISTERED_AND_RVM_REBASED_PENDING_OWNER_CLOSURE`: registration and re-base are EVIDENCE_PRESENT; the owner closure
  (re-base acceptance, `requirement_frozen`; 0/22 RFP_CLAUSE rows frozen) remains the explicit condition AG15-RC-01. Never PASS;
  an inconsistent or missing registration refuses the build. Status counts, objectives and gates evaluate only
  `hall_icp_neutralizer`; C1 cells live in a labelled ground-reference/retired history section. `BLOCKED_RFP_NOT_REGISTERED`
  now appears only in the verbatim A9.16 step-1 application text, never in a gate (tested).
- **M16 v4 / owner-question state v5 / application matrix (lane 42453f5, 34aae48).** State v5 records A9.17-A9.21:
  10 rows AMENDED_BY_A9_19 (OQ-A907-07 and MPQ-01 superseded: no C1 flight variant), 1 AMENDED_BY_A9_20, 2 AMENDED_BY_A9_21
  (MQ-05 AL-08 provisional floor; WEB-ACC-2 bid close 05-Oct-2026 17:00), new row RP-A919-01 ANSWERED_BY_A9_21 in part (ICP
  go/no-go gate before LOCK-1 approved, fail-closed; no numerical criterion approved). Earlier statuses kept as
  `pre_a9_17_status`. M16 v4: one flight configuration; C1 only GROUND_ONLY_LAB_REFERENCE; no readiness state changed.
  Matrix: 159 entries (APPLIED 143, PARTIAL 5, BLOCKED 6, NOT_APPLICABLE_TO_ARTIFACTS 3, SUPERSEDED_BY_LATER_DECISION 2);
  AG-15 registration + re-base APPLIED, owner acceptance PENDING_OWNER_ACCEPTANCE. New helper `a9_later_lib.py` pins the
  A9.17-A9.21 records (kept out of `a9_16_lib` so no other builder re-pins).
- **Single-configuration audit (lane 6a69ac5).** Three places still evaluated `hall_c1_reference` as flight: Xe v3 (45 items'
  `applies_to.configs`; C1-GT lines now GROUND_TEST-only with `a9_20_role = GROUND_ONLY_LAB_REFERENCE`, prior scope kept as
  `applies_to_pre_a9_19`), F7/F8 robust gate snapshot (RVM status-count column; I_e unlock text) and mass/power v3 (A9.2 status
  annotated as superseded). AL-08 carries `a9_21_status = PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN` in mass/power v3 and Xe v3
  (value 6.0528 kg unchanged). New `tests/test_single_flight_configuration.py` scans the generated JSONs. Not changed:
  `docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json` (pre-A9.19, sha-pinned by ~17 deliverables;
  accepted by the test only while byte-identical).
- **Integration.** Regenerated in dependency order H-1 freeze candidate (M16 v4 pin) -> F4 (H-1 pin) -> F7/F8 -> F9 ->
  application matrix. Two assertions in `tests/test_decision_application_a9_16.py` that encoded the superseded state were
  updated (AG-15 status; XV2Q-01 now AMENDED_BY_A9_19 with `pre_a9_17_status = AMENDED_BY_A9_15` asserted).
- **Checks:** both CI legs (pymsis absent / present) 3787 passed / 5 skipped / 1 xfailed, rule-9 outcome check passes in
  both; golden OK; ci_checks 11/11. No production physics module, frozen dataset or golden changed.
- **Still open (not this step):** 12 F9 records (2 parameter a9_16 records, the AG-12 gate, F9-OQ-02 and 8 owner-answer
  application rows; corrected in the 2026-10-03 review, was "13 F9 parameters") keep `rfp_citation_status =
  OWNER_STATED_PENDING_RFP_REGISTRATION` (needs per-record clause mapping); A9.21 ICP_GATE / AL08 artifact registration / HW_PROGRAMME re-sequencing.

## 2026-10-03 — A9.21 applied: ICP go/no-go gate, RFP clause citations in F9, AL-08 detection, hardware programme order

- **ICP gate (lane eae96c8).** `GNG-ICP-01`: mandatory ICP go/no-go before LOCK-1 with its own id (AG-01..AG-15 unchanged),
  defined once in `docs/requirements/rvm_a9/a9_21_icp_gate.py`, recorded in the RVM (`owner_approved_gates`) and
  re-evaluated in F9 (`pre_lock1_gates`, `lock1_precondition.lock1_release_reportable = false`). Status NOT_EVALUATED;
  criteria PENDING_OWNER_ACCEPTANCE; RP-A919-01 (a)-(c) kept verbatim as `proposed_criteria_for_owner_review` (never
  evaluated; criteria reusing it are refused). GO only with owner-accepted criteria and sha-pinned MET evidence for each.
- **F9 RFP citations (lane eae96c8).** The F9 records still labelled OWNER_STATED_PENDING_RFP_REGISTRATION (12 records;
  corrected in the 2026-10-03 review, was "10")
  and the two REQUIREMENT_AS_RECORDED parameters cite registered clause ids read from the RVM rows at build time
  (`docs/architecture/freeze_candidate/rfp_citations_f9.py`; `a9_16_lib` untouched). Five links (AG-12 / F9-OQ-02,
  F2-OQ-01, F2-OQ-03) rest on the RFP fact quoted in the owner's answer matching the RVM row text, not on a direct RVM
  citation; recorded as such. The old label is kept as `rfp_citation_status_as_applied`.
- **Hardware programme order (lane 364a5ab).** One record, `docs/experiments/hall_icp/programme/hw_programme_a9_21_v1.json`
  (14 steps listed in owner-item order - binding precedence only through the recorded predecessors - from the verbatim A9.21 items 6-11, predecessors and entry preconditions, each naming its existing
  enforcing rule), consumed and sha-pinned by H-1 and P1-P4. Fail closed: no step startable while a predecessor or a
  registration is missing; no PASS / GO / START_AUTHORISED. H-1 S7.2 waits for every authorised FEMM point; one gas/mode per
  ICP campaign with its own domain id and provenance; P2 map after the frozen in-house V/I calibration + uncertainty
  budget; P4 acceptance exposure after LOCK-2; AG-12 stays NOT_EVALUATED without a measured thrust/feed map. Recorder
  readings RR-01..RR-03 await the owner.
- **Application matrix (8d277df, d8c24d4).** Structural record checks: AL08 APPLIED (A9.21 label on the AL-08 line and
  XV3-IF-02; quotation re-base PENDING_EVIDENCE), ICP_GATE APPLIED (criteria PENDING_OWNER_ACCEPTANCE), HW_PROGRAMME
  APPLIED (hardware runs PENDING_EVIDENCE; RR-01..03 PENDING_OWNER_ACCEPTANCE). Counts: APPLIED 146, PARTIAL 4, BLOCKED 4,
  NOT_APPLICABLE_TO_ARTIFACTS 3, SUPERSEDED_BY_LATER_DECISION 2.
- **Regenerated:** F4 -> F7/F8 -> F9 -> matrix (H-1 pin). Checks: 3830 passed / 5 skipped / 1 xfailed, rule-9 outcome check
  passes, golden OK, ci_checks 11/11. No production physics module, frozen dataset or golden changed.

## 2026-10-03 — M16 v5 (scheduler re-derived from A9.8-A9.21) + review fixes (parallel review/fix model)

Owner instruction 2026-10-03: rapid delivery; review, verification and fixes run in parallel with implementation.
- **M16 v5 (lane c4062e0, 7b5e985).** New `docs/experiments/hall_icp/integration/m16_v5/` re-derives every M16 row's
  blockers from owner answers A9.8-A9.21 (state v5 + pinned later records), the A9.21 programme order and GNG-ICP-01;
  M16 v4 and state v4 byte-identical. 21 rows; readiness unchanged (20 BLOCKED, 1 SUPERSEDED_FOR_PRIMARY_LINE): rule
  R-M16V5-03, a state advances only on a registered measured artifact, never on an authorising answer. 59 blockers removed
  (54 answered owner questions, 5 scheduler items changed), 103 remain (31 hardware run, 26 external input, 25 owner act, 21
  evidence). No named person fabricated. State v5 RP-A919-01 gains `gate_location` (pointer only). Matrix: S9.4 /
  M16-V3-Q-01 re-derivation APPLIED (named persons PENDING_EVIDENCE).
- **Code review fixes (cbd55ab).** Fail-open paths found by the parallel correctness review of fd91185..9d0f851 closed,
  each with a regression test (details in the commit message).
- **Regenerated:** H-1 (state v5 pin) -> F4 -> F7/F8 -> F9 -> matrix. Targeted suites for every touched artifact: 313
  passed; builders --check current; full-suite result recorded with the next integration.

## 2026-10-03 — Review-and-fix of fd91185..9d0f851 (evidence discipline / consistency)

- **Matrix commit citations.** Two cited (commit, artifact) pairs did not contain the claimed change (`git show`):
  A9.19 `abep_sim/design/a9_19_architecture.py` @ 56e7327 (does not touch the file; its FLIGHT_CONFIGURATIONS record came
  in 90f0137) and A9.14 F0-OQ-02 `REGISTRATION.json` @ 61373fd (touches baseline.json / machine.json only; the file came
  in b9b7387). Both re-pointed in `build_a9_16_application_matrix.py`; new test
  `test_matrix_cited_commits_touch_their_artifacts` (every application outside the step-1 lane table). Not fixed: the
  step-1 P3 lane cites `p3_coupled_thermal_v2.json` @ c00f9b5, which changed only the v1 files (v2 first appears in the
  repair commit 1d51554); re-pointing needs the step-1 P3 locator set reworked (several ids are absent from v1).
- **F9 RFP citations.** The F9 record -> RVM row correspondence (`rfp_citations_f9.CORRESPONDENCE`) is the recorder's
  reading, not an owner or RVM re-base mapping; it is now labelled `RECORDER_READING_OWNER_MAY_REVERSE`
  (`rfp_citations.correspondence_status`; `rfp_correspondence_status` on each of the 14 records; the note no longer says
  "mapped as the RVM re-base maps"). Clause ids unchanged.
- **Wording.** Programme / H-1 / P1-P4 companion documents rendered the 14 steps as one `a -> b -> ...` chain although
  ICP-AR-REF, P2-MAP, COUPLED-H1-ICP and H1-THRUST-FEED-MAP have no predecessor in A9.21; now a listing with the
  predecessor rule stated (JSON records unchanged). State v5 MD labels the step-1 "document is not registered" RFP rule
  as history next to "RFP now". HISTORY counts above corrected in place (12 pending F9 records, not 13 / 10).
- No owner decision, frozen dataset, golden, physics module or status changed. Checks: 3834 passed / 5 skipped /
  1 xfailed (4 new regression tests), golden OK, ci_checks 11/11, every rebuilt builder `--check` current.

## 2026-10-03 — RFQ v3: A9.21 AL-08 quotation split + per-package dispatch readiness

- **AL-08 split (lane c6a1194).** RFQ v3 revised in place (v1/v2 stay immutable): new requirement RFQ3-GAS-N05 — every Xe
  storage/flow supplier states mass and attributes separately for tank (GAS-L08), regulator/PMU (GAS-L09), valves (GAS-L11;
  FCU GAS-L10 as a sub-row, recorder flag RF3-FLAG-06), plumbing (new GAS-L18), mounting/thermal (new GAS-L19; both LATER,
  quantity proposed by the supplier) and any C1-specific branch (GAS-L05/L06/L15/O03; ground-only, quoted and booked
  separately, never inside flight AL-08). 6.0528 kg labelled PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (checked against
  mass/power v3 at build time); the 1.5 kg row-54 allocation kept only as history. `al08_quote_split_status` never computes
  or freezes an AL-08 value.
- **Dispatch readiness (A9.21 item 15).** Per package: READY_FOR_OWNER_DISPATCH for RFQ3-RF, -GAS, -VAC, -HALLEL, -MECH,
  -RFMET (NOW lines); RFQ3-THRUST NOT_READY_BLOCKING_TBD (TH-L09 quantity depends on the dispatched P1 line set);
  RFQ3-H1FAB NOT_READY_AWAITING_CONTROLLED_H1_DRAWINGS. `repository_dispatches = false`, `purchase_authorized = false`
  everywhere; the open-item classification is a recorder rule for owner review (RF3-FLAG-07).
- Matrix regenerated (record locations for A9.14 MQ-05 moved inside the RFQ). Affected suites 121 passed; RFQ v3 / RVM /
  state v5 / M16 v5 / H-1 / F9 / matrix --check current.
- **Review follow-ups (2026-10-03, unfixed items of the correctness review cbd55ab).** Matrix: unknown record-check op
  refused; the five HW_PROGRAMME stage applications verify `/a9_21_programme/programme_record_sha256` against the current
  programme record (`pin_pointer`). ICP gate: a criteria item without its own text is refused (never GO). F9 citations: a
  partly mapped record keeps its unmapped questions' reasons (`rfp_citation_partially_unmapped`). `a9_later_lib.verbatim`
  refuses an empty excerpt. Guards only: every output reproduces; regression tests added. Open for the owner: AG-15
  closure is detected by an `ag_15_status` "CLOSED" prefix without an owner-decision citation (format of the owner's
  closure record to be decided).

## 2026-10-03 — Design layer on the frozen design-state set v2 (OD3 / OQ-F4-05); F1Q-02; OQ-F4-04; F9 empty robust set

- **Design states (lane 405296e).** F1-F8 evaluate the 196 required states of `atmosphere_msis21_orbit_v1_design_states_v2`
  (sha256 60073e21...4049; 4 ECSS scenarios x 4 altitudes; per node the median-density nominal state, density / x_O /
  x_N2 / x_O2 / temperature extrema and local-time density peak/trough, plus 10 envelope extrema) plus the h200_f150
  design-case reference. No subsampling (the set designates none); pinned and cross-checked against the dataset
  manifest, fail closed (`DesignStateSetError`). Label `BROAD_ENVELOPE_ALL_INCLINATIONS_ALL_LTAN_NOT_MISSION_ICD` on
  every output (A9.21: inclination / LTAN are not mission truth). The frozen intake surface v1 covers no design state:
  all 23,520 design-state points use direct TPMC with registered seeds (seeded process-pool prefill, bit-identical to
  serial). Superseded five-state results kept as `state_set_history` (ids, output sha256, feasibility counts).
- **Results.** F1 envelope-feasible intakes 48 -> 24 of 144 per scenario (C-DRAG-RFP intake-face drag binding at dense
  ECSS_ST_HIGH 180 km; peak q 0.0335 Pa); F4 all-state frontier 0.0983 -> 0.0130 mg/s (scheduled 0.119 -> 0.0264),
  binding at ECSS_LT_LOW 230 km; no transient-basis chain passes the orbit check (valve saturation / outside the Gaede
  characteristic), offered_to_h1 0; F7 feasible vectors 100,267 -> 4,647, Pareto 22,282 -> 1,279; F8 survivors 843 -> 90,
  all-10-scenario feasible 0: **robust Pareto set empty**. 0.38 mg/s still reached by no member.
- **F1Q-02 (S6.1).** Intake mass is PARAMETRIC_SENSITIVITY / budgeting only (never a CBE, frozen mass or structural
  qualification); sourced structural definition required before LOCK-1; `ao.wet_mass` refuses an unlabelled intake mass.
- **OQ-F4-04 (S6.13).** Owner flow-gap order recorded in F4 / F7; `refuse_feed_requirement_lowering` rejects any
  feed-requirement basis other than performance-derived (0.38 mg/s is ground characterization only); dense-state-only
  operation is SENSITIVITY_ONLY_NOT_BASELINE.
- **F9 (lane d9030ca).** Robust-set parameters (AFC-UP-IN-01/02/03/09, CO-01/02/05/06/08/09, PL-01/02/08; VF-06 for the
  empty offered feed) carry EMPTY_ROBUST_SET_NOT_EVALUATED with null ranges (no crash, no fabricated range); every
  upstream number in F9 text is read from the F1-F8 outputs and checked against their findings (old 0.0983 / 0.119 mg/s
  and similar hard-coded values removed; as-raised owner-question text kept verbatim with `as_raised_numbers` notes). New
  design finding **F9-DF-01** for the owner: under the full registered design-state envelope no robust upstream design
  survives; not a requirement failure and no relaxation proposed (A9.13 S6.13); owner flow-gap order cited. Status stays
  INVESTIGATION_HYPOTHESIS.
- **Integration.** F4 -> F7/F8 rebuilt for the current H-1 pin (pin-only diffs; F4 23 min, F7/F8 40 min single-process),
  then F9 and the matrix. F0 performance MD re-rendered (live F1 direct-run count). Open: the F1 output is now 36.7 MB
  (was 1.9 MB) — storage form is an owner call (A9.17 DATA_SIZE intent: avoid bloating Git history).

## 2026-10-03 — A9.22 G8 stage 2: bus-boundary consumers re-pointed v1 -> v2 (one controlled migration)

- **Decision.** A9.22 item 8 / G8_BUS_BOUNDARY: re-point the pinned consumers of `bus_boundary_a9` in one controlled
  migration, update pins together, keep v1 immutable, verify no physics result changes because the taxonomy changed.
- **Inventory first.** `build_consumer_inventory.py` re-run at the pre-migration head 5b32edc (line numbers had moved
  since stage 1 at 9eb302c; counts unchanged: 138 files, 28 LIVE_REPOINT in 12 families, 3 TRANSITIVE_LIVE,
  9 LIVE_RETAIN_V1_REFERENCE, 68 IMMUTABLE_HISTORY). It now scans the git tree of that fixed commit, so it stays
  reproducible after the migration.
- **Migration (recorded order).** v2 artefact (consumer note only) -> P1 (BUS authority pin v2; historical_reuse keeps a
  v1 pin) -> P2 -> mass/power v3 (module + peak helper import v2; power.boundary_version v2; retired C1 power
  configuration and carried v2 items stay v1) -> Xe v3 (XV2-15 template citation; v2 text kept as source_v2) -> RFQ v3
  (13 sources re-pointed after checking each pointer resolves identically in v2; C1 rows GAS-R26 / HALLEL-R22 / R25 / R29
  stay v1; R14 cites v2 /slots plus v1 /slots for the C1 bench column) -> M16 v5 (own BUS ref; BUS_ITEM_OPEN resolved in
  v2, cross-checked against v1) -> F7/F8 (architecture_optimizer imports v2; assertion now `CONFIGURATIONS ==
  bb.CONFIGURATIONS` and `GROUND_REFERENCE_CONFIGURATIONS == tuple(bb.GROUND_REFERENCE_TEST_METADATA)`) -> RVM (flight
  cells cite v2; C1 ground-reference cells RVM-19 / RVM-20 keep v1; requirement texts / limits untouched, AG-15 freeze
  intact) -> F9 (BUS input v2; every changed pin re-pinned by the rebuild).
- **No physics change.** `STAGE2_MIGRATION.json` (`build_stage2_migration.py`, PRE 5b32edc vs the migration commit,
  read from git) diffs every regenerated JSON field by field and every Markdown line: only PIN_SHA / PATH / LABEL /
  declared PROVENANCE_TEXT / PROVENANCE_ADDED changes, no number changed, appeared or disappeared; v1 family
  byte-identical; every immutable / retained / transitive file byte-identical; each v1 reference left in a re-pointed
  file has a declared retention reason. F7/F8 outputs: string-only edits (module path, two source strings, one gate
  basis) applied to the committed outputs and confirmed byte-identical by a full single-process rebuild.
- **Stays on v1.** Immutable history (RFQ v1/v2, M16 v3/v4, mass/Xe v1/v2, A9-10, core integration, owner brief, ...),
  the bid package anchored at bbc480c, state v5 OQ-A902-xx 'raised in v1' citations, the decision dossier listing.

## 2026-10-03 — A9.22 step 1 (lane w2core): operating inputs as explicit parameters; assessment-layer constraint flags (NO numeric change)
Owner directive A9.22 (layer separation; `docs/decisions/OD_2026_10_03_A9_22_*`): physics never reads RFP / RVM / clause ids;
requirements reach physics only as frozen engineering inputs.
- **Seam.** New `abep_sim/operating_inputs.py`: the one module that supplies defaults for caller-omitted operating inputs
  (MISSION_HOURS, FIRING_HOURS, THRUST_MIN/MAX_mN, P_BUS_MAX_W, MASS_MAX_KG). Today it reads `constants.RFP` (values
  unchanged); the integrator re-points it to `config/mission/mission_scenario_v1.json`.
- **Parameters instead of RFP reads.** `archengine.close_architecture(firing_hours=None)`; `mission5.run_phase5(hours,
  thrust_cap_mN, mission_hours, firing_hours)` and `run_mission_generic(hours, P_bus_max_W)`; `mission_env.array_area_for
  (P_cap_W=None)`; `life.LifeInputs.mission_h / firing_h` defaults from the seam; `uq_modular.evaluate_sample / run_uq
  (firing_hours)` (was a literal 15000.0); `arch_compare.compare_architectures(limits=None)`. None = seam default.
- **Assessment layer.** New `abep_sim/assessment/arch_constraints.py`: archengine output flags (thrust_min_ok, thrust_max_ok,
  mass_ok, life_ok, all_constraints_ok), the DesignConstraints owner preset (`archengine.rfp_preset` delegates), arch_compare
  band/cap flags and limits record, uq_modular success flag, mass plausibility screen and hard-gate evaluation route
  through it. archengine in-loop candidate rejection is unchanged (selection under caller-supplied DesignConstraints).
- **Not edited (pins).** `abep_sim/mass_bom.py` is pinned immutable by the A9.10 reconciliation and the veto layer, and
  `abep_sim/cathode_integration.py` by the aux-bus / veto layer: editing either refuses those builders. mass_bom's
  `build_document` keeps reading the recorded mass limit (its screen is reachable with a caller threshold through
  `assessment.arch_constraints.mass_plausibility_screen`); cathode_integration reads its values from its immutable v1 data
  file, not from `constants.RFP`. `hard_gates.py` reads only the gate matrix (no RFP constant) and is unchanged.
- **Stale label removed.** `spacecraft_reference_drag.RFP_THRUST_BAND` (12-25 mN, unchanged) now carries
  `requirement_status = FROZEN_REQUIREMENTS_SNAPSHOT` with provenance to `docs/requirements/rfp_official/
  rfp_registration_v1.json` (A9.22 G3 freeze); the stale `OWNER_STATED_RFP_NOT_REGISTERED` label and its AG-15 open item are
  gone; the lane document was rebuilt (label/provenance lines and module sha256 only).
- **Verification.** golden check OK (unchanged); ci_checks 11/11; the 34 builders that read these modules were `--check`
  current before and after, except `scripts/architecture/build_decision_dossier.py`, stale by pin only (arch_compare.py
  sha256 in its provenance), left for the integrator to re-pin.

## 2026-10-03 — A9.22 G1 governed baseline change (lane w2core): mission-duration basis 26,280 h
Owner decision A9.22 G1 (`docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json`,
G1_MISSION_LIFE = MISSION_DURATION_26280_H): mission-integrated quantities use 26,280 h; 15,000 h survives only as an
explicitly labelled subsystem firing-life assumption. Intentional model-basis change (CLAUDE.md rules 1-2), applied once.
- **Seam.** `operating_inputs.MISSION_HOURS = MISSION_DURATION_BASIS_H = 26280.0`; `FIRING_HOURS =
  SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H = 15000.0` (label `SUBSYSTEM_FIRING_LIFE_ASSUMPTION`);
  `HISTORICAL_MISSION_HOURS_PRE_A9_22 = 26000.0` exists only to recompute immutable history. `constants.RFP.mission_hours`
  (Phase A lane) is not edited here.
- **Per-site choice.**
  - `archengine.close_architecture` xe_kg (neutralizer Xe integrated over `firing_hours`, default was RFP.mission_hours =
    26,000): **mission basis 26,280 h**. archengine defines no separate duty/firing profile that would legitimately
    reduce the firing time, so the 15,000 h assumption is not used for Xe.
  - `life.LifeInputs.mission_h` (AO fluence of the intake coating, blade/compressor life checks, reliability horizon,
    SPF threshold 1.5 x mission): **26,280 h**. `LifeInputs.firing_h` = 15,000 h, labelled firing-life assumption
    (hall channel / cathode life requirement, R at the firing horizon).
  - `life.reliability`: keys `R_15000h`, `R_26280h`, plus role keys `R_firing` / `R_mission`; `R_26000h` is still emitted
    as R evaluated AT 26,000 h (truthful key, not relabelled) because `system.py` (Phase B lane) still reads
    `eng_R_26000h`; that consumer migrates to `R_mission` in its own lane.
  - `mission5.run_phase5`: propagation `hours` and life `mission_hours` default 26,280 h, `firing_hours` 15,000 h (labelled);
    output reliability keys `R_firing`, `R_mission`, `R_15000h`, `R_26280h` (was `R_15000h`, `R_26000h`).
    `run_mission_generic(hours)` default 26,280 h.
  - Unchanged: `mission_env.array_area_for(years=3.0)` (already 3 years = 26,280 h); `cathode_integration` derived
    statements (immutable v1 data file, LaB6 lane = historical non-flight; a caller may pass hours explicitly);
    `system.py` (`fluence(atm, RFP.mission_hours)`, cathode starts) belongs to the Phase B lane.
- **golden_v2 regenerated** (`python -m abep_sim.golden generate`, then `check` OK). Moved values (all in
  `cases.architecture_closure.ext_hall_2p5kW`, the LaB6-Xe historical closure; neutralizer Xe 0.05 mg/s x 1.2):

  | entry | before (26,000 h) | after (26,280 h) |
  |---|---|---|
  | xe_kg | 5.616 | 5.67648 |
  | CBE_kg | 42.94863073976071 | 43.02504899163571 |
  | MEV_kg | 49.88045491831906 | 49.96406543847815 |
  | m_system_kg | 76.18638222355476 | 76.26999274371386 |
  | firing_hours_for_xe (new label key) | — | 26280.0 |

  Nothing else moved (gas path, accelerators, mission 4000 h case, selection record and all other cases bit-identical;
  provenance.code_version updated). The `nonconverged_reference` fixture recomputes golden_v1 on the pre-A9.22 26,000 h
  basis and still reproduces it verbatim; `golden_v1.json` untouched.

## 2026-10-03 — A9.22 G4 (lane w2core): cathodeless active golden; LaB6 golden = HISTORICAL_NON_FLIGHT_REGRESSION
Owner decision A9.22 G4 (CATHODELESS_ACTIVE_BASELINE): active flight architecture `hall_icp_neutralizer` (Hall accelerator +
downstream RF/ICP electron source / neutralizer; no hollow cathode, no LaB6).
- **Historical label.** The golden closure scenario `hall_internal+hall+lab6_xe` (LaB6 Xe hollow cathode) is now
  `HISTORICAL_NON_FLIGHT_REGRESSION`: `golden.HISTORICAL_NON_FLIGHT_ARCHITECTURE` (the old `GOLDEN_ARCHITECTURE` name is
  gone), `CASE_ROLES` of `architecture_closure` and `mission`, and a `golden_role` / `architecture` label inside both
  stored cases. Values unchanged (still reproduced by `check`); history not rewritten; golden_v1 untouched.
- **Guards.** `golden.require_flight_eligible_case(case, use)` / `golden.load_case(case, use)` raise
  `HistoricalNonFlightError` for any of architecture_closure, architecture_selection, optimisation, rfp_compliance,
  flight_budget, design_decision (only `regression` is allowed). `archengine.FLIGHT_EXCLUDED_NEUTRALIZERS = {lab6_xe}`,
  `require_flight_eligible`, `close_architecture(flight=True)` refuses, `run_all(flight=True)` returns
  `EXCLUDED_HISTORICAL_NON_FLIGHT` / feasible False without closing. Defaults (flight=False) keep research/regression
  behaviour unchanged.
- **New governed case `hall_icp_neutralizer_reference`** (role `GOVERNED_REFERENCE_ACTIVE_ARCHITECTURE_PARTIAL`) at the
  A9.18 golden design point (0.7 m2, 0.05 Pa, 200 km mean): only quantities admitted models compute — air supply mode
  gas path (mdot 0.9753 mg/s, p_in 0.05 Pa, x_O, x_O2, eta_c, C_D, intake drag, P_comp; CONVERGED / IN_DOMAIN, rotor
  NOT_EVALUATED_MATERIAL_BASIS), mission-basis AO exposure (26,280 h: fluence, intake-coating erosion, alpha_end,
  blade-coating and intake lives), intake and compressor mass lines (PARAMETRIC_SENSITIVITY). Everything else is
  `NOT_EVALUATED_NO_ADMITTED_MODEL` with its reason: Hall thrust / discharge (0-D closure withdrawn, credible set empty),
  ICP neutralizer (archengine `rf_cathode` is an air-fed plasma-bridge cathode calibrated to AMPCAT microwave data and
  capped at 0.5 A validated: not an honest model of the 13.56 MHz downstream ICP; ICP-45 NOT_EVALUATED), Xe supply-mode
  flow, P_bus/PPU (bus boundary v2 is A9.22 G8 work), thermal (UNRESOLVED), life, mission closure, and the mass lines
  Hall accelerator / ICP / RF chain / PPU / thermal / Xe load / Xe tank / harness / structure and CBE/MEV totals. No
  number was invented (rule 6) and no propulsion family added (rule 8).
- golden_v2 regenerated: new case and labels only; every numeric value of the existing cases unchanged.

## 2026-10-03 — A9.22 G1 governed baseline change (system.py completion)
Owner decision A9.22 G1 (`docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json`,
G1_MISSION_LIFE = MISSION_DURATION_26280_H), completing the migration logged in the w2core G1 entry above for the last
consumer, `abep_sim/system.py` (Phase B raw closure). Intentional model-basis change (CLAUDE.md rules 1-2), applied once.
- **system.py: no `constants.RFP` read remains.** Every engineering input comes from the seam `abep_sim.operating_inputs`.
  Per site:
  - AO fluence `fluence(atm, mission_h)` and the three erosion depths (Kapton, graphite, silver): mission-integrated ->
    **26,280 h** (was `RFP.mission_hours` = 26,000 h). New key `ao_fluence_basis_h` = 26280.0 states the basis.
  - `LifeInputs(cathode_starts=int(mission_h / 24 * 0.5))`: starts over the mission -> **26,280 h**; `LifeInputs` now also
    receives `mission_h` / `firing_h` explicitly (same values as its seam defaults, so the life models are unchanged).
  - Cathode Xe (`xe_cathode_kg`), Xe-for-T_req (`xe_req_kg`) and the O-exposed life margin (`air_hours`): firing-integrated
    (they flow / wear only while firing) -> **15,000 h kept**, now read as `operating_inputs.FIRING_HOURS` with label
    `SUBSYSTEM_FIRING_LIFE_ASSUMPTION` (value unchanged; the OD allows a defined firing profile to reduce the Xe
    integration time, and the labelled firing-life assumption is that profile here).
  - T_req floor / thrust cap / Xe peak point: `operating_inputs.THRUST_MIN_mN` / `THRUST_MAX_mN` (12 / 25 mN, unchanged).
  - Reliability: new keys `eng_R_mission` (= `life.reliability()["R_mission"]`, R at 26,280 h) and `eng_R_mission_h`
    (26280.0). `eng_R_26000h` is KEPT with its honest meaning (R evaluated at the historical 26,000 h horizon,
    `life.LEGACY_RELIABILITY_HORIZON_H`; value unchanged) for existing readers; it is no longer the mission value.
    `eng_R_15000h` now reads `R_firing` (same number). `uq6.monte_carlo6` reports `eng_R_mission` alongside
    `eng_R_26000h`; `tests/test_sim.py` checks `eng_R_mission`.
- **Moved outputs** (system.evaluate / physics_closure; exact factor 26280/26000 = 1.0107692 on the four linear ones;
  every other output of the 122 identity configurations bit-identical):

  | output | config | before (26,000 h) | after (26,280 h) |
  |---|---|---|---|
  | ao_fluence_mission_m2 | hall_1stage 180 km low (identity row 0) | 3.62306474382429e+27 | 3.662082364142398e+27 |
  | erosion_kapton_um | row 0 | 10869.194231472871 | 10986.247092427195 |
  | erosion_graphite_um | row 0 | 4347.677692589149 | 4394.498836970878 |
  | erosion_silver_um | row 0 | 38042.17981015505 | 38451.86482349518 |
  | ao_fluence_mission_m2 | hall_1stage 200 km mean, engineering path (row 119) | 3.5134220093636966e+27 | 3.5512588617722285e+27 |
  | eng_cathode_starts | rows 119-121 (engineering path) | 541 | 547 |
  | eng_R_mission (new) | row 119 / 120 / 121 | — | 0.3442111919970725 / 2.244652790675135e-12 / 1.4189005597000432e-06 |
  | eng_R_26000h (unchanged, R at 26,000 h) | row 119 / 120 / 121 | 0.35600820959019297 / 5.242294465093805e-12 / 2.1720953464819916e-06 | same |
  | ao_fluence_basis_h, eng_R_mission_h (new) | all / engineering rows | — | 26280.0 |

  Not moved: xe_* masses, m_* / eng_m_* masses, life_limit_h / life_margin, eng_R_15000h, eng_marginal_items (SPF
  threshold already used `LifeInputs.mission_h` = 26,280 h since the w2core G1 change), all assessment flags.
- **golden: `python -m abep_sim.golden check` -> OK without regeneration**; golden_v2 does not carry any system.evaluate
  output that moved, so it was NOT regenerated in this step.
- **Identity fixtures.** `tests/fixtures/evaluate_identity_base_9eb302c.json` is unedited and stays the historical
  no-change proof of Phase B: `tests/test_raw_assessment_split.py` compares against it bit for bit EXCEPT the explicitly
  listed G1 keys (`G1_MOVED_KEYS` = ao_fluence_mission_m2, erosion_kapton_um, erosion_graphite_um, erosion_silver_um,
  eng_cathode_starts; `G1_ADDED_KEYS` = ao_fluence_basis_h, eng_R_mission, eng_R_mission_h), which are checked instead
  against the exact 26280/26000 scaling and the 541 -> 547 start count. A second fixture
  `tests/fixtures/evaluate_identity_g1.json` (generator `tests/fixtures/make_evaluate_identity_fixture_g1.py`, same 122
  configurations, generated once at the G1 completion commit recorded in its `base_commit`) is compared with no
  exclusion and is the reference for future no-change checks.
- **Seams re-pointed to the frozen configuration (values identical).** `abep_sim/operating_inputs.py` reads
  `config/mission/mission_scenario_v1.json` through `abep_sim.configuration.load_operating_inputs` (manifest-checked, fail
  closed; never opens the requirements snapshot); `abep_sim/design/engineering_constraints.py` reads
  `config/requirements/rfp_constraints_v1.json` (+ the mission domain) through `load_engineering_constraints`. Neither
  imports `abep_sim.constants` any more. `scripts/config/build_config.py` records G1 as `APPLIED`: mission scenario
  `mission_hours.value` = 26280 (label `MISSION_DURATION_BASIS`, `g1_migrated_consumers`), `legacy_mission_hours_in_use`
  removed, the 26,000 h kept only as `historical_note` labelled `HISTORICAL_CONSTANT_NOT_CONSUMED` (same label on the
  snapshot's `rfp_constraints_compat.mission_hours`, which must stay 26000 to match the immutable, sha-pinned
  `abep_sim/constants.py`, unedited); new mission-scenario input `wet_mass_limit_kg` (40, from the snapshot) feeds
  `operating_inputs.MASS_MAX_KG`. config/ rebuilt (`--check` OK).
- **Layer separation test** `tests/test_layer_separation_physics.py`: AST import graph (no `abep_sim.assessment` import
  from physics modules outside a frozen, shrink-only allowlist of 13 compatibility / orchestration call sites), no read of
  docs/requirements / docs/decisions (labels allowed), no clause / RVM id used for computation, and a runtime check that
  `system.physics_closure` runs with config/requirements hidden, abep_sim.assessment unimportable and an audit hook on
  open(). To make the runtime check possible `abep_sim/__init__.py` resolves `run_grid` / `summarize` lazily (PEP 562;
  public names unchanged), so importing the package no longer imports the assessment layer.
- Decision dossier re-pinned (`scripts/architecture/build_decision_dossier.py`; arch_compare.py sha and the bus boundary
  v2 schema now present in schemas/interfaces).

## 2026-10-03 — Owner: upstream ICD kept as is; RFQ v3 flag RF3-FLAG-04 resolved

- **Upstream ICD (owner, 2026-10-03: "keep the ICD as is").** `schemas/interfaces/upstream_icd_v1.json` and
  `UPSTREAM_ICD.md` stay byte-identical (their sha256 is pinned by ~10 records, several immutable). After the A9.22
  raw / assessment split the ICD's `abep_sim.system.evaluate` reference is resolved to its raw producer
  `physics_closure` in `tests/test_upstream_icd.py` (`RAW_PRODUCER_OF`), gated by a behavioural delegation test; no
  ICD v1.1 is issued.
- **RFQ v3 RF3-FLAG-04** ("the RFP is owner-held and not yet registered (AG-15)") marked RESOLVED with its history kept:
  the RFP is registered by hash (A9.17 RFP) and AG-15 is closed by the owner (A9.22 G3). RFQ v3 rebuilt (text only);
  no consumer pin moved.
