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
