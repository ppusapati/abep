# RF source evidence on the rf_hall break-even surfaces (`overlay_rf_v1`)

| item | value |
|---|---|
| follow-on | `fo_rf_breakeven_overlay` (trigger `T_RF_OVERLAY`) |
| architecture / reference | `rf_hall` against `hall_only` |
| common boundary | `bus_power_boundary_v1` |
| files | `overlay_rf_v1.json` (authoritative for every number), this page, `build_overlay_rf.py` (deterministic; `--check` reproduces both), `tests/test_overlay_rf.py` |
| status | DRAFT for owner review, 2026-09-26. **Conditional inequalities**, not predictions. |
| milestone support | **A** (conditional selection). B and C: not yet, see §0. |

**What this is.** The accessed RF-source evidence placed on the break-even surfaces of `breakeven_v1`, with the
interstage transport efficiency η_t included. The result is a set of inequalities that `rf_hall` must satisfy, and the
position of each evidence entry relative to them.

**What this is not.** It names no winner and ranks nothing. It sets nothing aside: setting an architecture aside is done
only by hard gates, and nothing here is a hard gate. It does not discuss the other pre-ionized arm. It uses no Hall
transport closure, no screening candidate (`sgb-screen-*`) and no withdrawn 0-D Hall number. The credible closure set is
empty (gate 3 FAIL), so every Hall-side quantity is a **PROPOSED analysis value**. Nothing is retuned. P5 calibration
nuisance (registration, coil shape, divergence reading, facility interpretation) is not an input, an axis or a design
variable. The feed state ṁ is fixed by the common feed: nothing here reaches upstream into the intake, filter,
compressor, gas chambers or valves. The script is pure and is not wired into `archengine`, so the goldens do not move.

## 0. Milestone support

| milestone | what this overlay delivers | what is still needed |
|---|---|---|
| **A: conditional selection** | The statement "rf_hall can be the baseline only if it demonstrates X, Y and Z at the Vyovrinda Hall reference point", with X, Y and Z computable now over PROPOSED ranges for the three response cases, and the placement of every accessed RF evidence entry against them (G0, G6). | The owner's acceptance of the PROPOSED box, the placement definitions and the model-family assumptions A1–A8 (BREAKEVEN_DERIVATION.md §3). |
| B: physics-backed selection | The interface only: every function takes an admitted closure's η_u0, η_b, η_v and V_d without change. | Admitted Hall transport closure(s) for the Vyovrinda geometry; a measured delivered-ion bus cost of an RF stage on air/N₂ at the ICD inlet state; a measured η_t; the measured response (α, χ, η_v,S, delivered mix); antenna/matching coupling on air. |
| C: proposal/PDR freeze | Nothing. | Mass (power-system and thrust sensitivities, RF hardware), source and Hall life, thermal (`abep_sim/thermal_life.py`), start-up, cathode and mission closure, all on the same boundary. |

## 1. Inputs (read-only, sha256-pinned)

| input | repository path | lane, branch, commit | used for |
|---|---|---|---|
| break-even module | `abep_sim/breakeven.py` (`breakeven_v1`) | lane 28, `worktree-wf_15f0f2f8-8d4-1`, `2ad4c463d7` | every surface value (loaded by path, not copied) |
| break-even derivation | `docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md` | lane 28, same | closed forms used as self-checks; assumptions A1–A8 |
| RF evidence matrix | `docs/evidence/rf_source/rf_evidence_matrix.json` | lane 07, `worktree-wf_2bcadd98-5ff-1`, `336d548042` | evidence entries, values, classes, levels, conditions |
| interstage module | `abep_sim/interstage.py` (`interstage_v1`) | lane 18, `worktree-wf_15f0f2f8-8d4-2`, `870514285c` | η_t basis (text checks only; not executed) |
| interstage model | `docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md` | lane 18, same | η_t definition, validity and TBD list |
| electrical closure | `docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json` | lane 20, `worktree-wf_15f0f2f8-8d4-3`, `f7c226848d` | η_ppu,d evidence range; bus → coil-feed chain of `rf_source` |
| constants | `abep_sim/constants.py` | base checkout | e, u, nominal masses (as used by the RF evidence lane) |

The script looks for each file by its repository path: first in this checkout, then under `--input-root` (or
`ABEP_OVERLAY_INPUT_ROOTS`), then in the sibling git worktrees. It accepts a file only if its sha256 equals the pin, so
the result does not depend on where the file was found. A missing or different file raises `OverlayInputError` with the
places searched (no silent fallback, CLAUDE.md rule 3). After the input lanes merge, the files are found in this
checkout. Moving to a newer input means changing its pin deliberately and regenerating.

This lane accessed no external source itself. Every source below is cited as recorded, with its access label, by the
input lane named.

## 2. Common boundary and quantities

* **P_bus** is all DC-bus power of an arm: the sum over the `bus_power_boundary_v1` components (`hall_discharge,
  hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping`, plus
  `rf_source` for `rf_hall`). The comparison is **never** made on plasma-absorbed RF power, on source-only power or on
  discharge-only power. Absorbed or forward RF power enters only after conversion to the bus (§5).
* **C_src** = P_bus[rf_source] / I_src: bus W per ampere of ions leaving the RF stage.
* **η_t** = I_delivered / I_src: ion **current** delivered into the Hall channel over ion current leaving the source
  (lane 18, INTERSTAGE_MODEL.md §2 and §8). It pairs with costs in W/A.
* **C_del** = C_src / η_t: bus W per ampere of ions delivered into the Hall beam.
* **Π_H** = V_d / (η_b η_ppu,d): the Hall's own bus price per beam ampere.
* **ω** = O / P_d,bus0, with O = P_bus[rf_source] + Σ (common-component deltas, arm − hall_only) and P_d,bus0 the
  Hall-only discharge bus power. **ω_f** is the part of ω that does not scale with delivered ions.

Three response cases (BREAKEVEN_SURFACES.md), all assumed parameters until a coupled test measures them:

| case | α | χ | η_v,S | meaning |
|---|---|---|---|---|
| `add_only` | 1 | 0 | η_v | delivered ions add to the beam; each costs the full Hall price V_d/η_b |
| `cost_offset` | 1 | 1 | η_v | delivered ions also avoid the Hall's per-ion electron-current overhead |
| `optimistic_bound` | 1 | 1 | 1 | most favourable corner of the declared box α, χ ∈ [0, 1], η_v,S ∈ [η_v, 1] at equal mix |

`add_only` is the least favourable of the three, but it is not a lower bound on the response. Delivered ions that
displace Hall-born ions (α < 1) lower the payable cost further (condition C4 in G0).

## 3. The break-even condition

In the form the owner asked for:

> At a Hall reference point h and response case k, **RF+Hall becomes preferable to direct Hall ONLY IF** it delivers
> at least **X** (relative utilization gain x = Δη_u/η_u0; with α = 1 this is the delivered-ion share δ_s/η_u0), at no
> more than **Y** bus W per delivered ampere, through an interstage whose transport efficiency is at least **Z**.

This is the power side on `bus_power_boundary_v1`. It is **necessary, not sufficient**: mass, life, thermal and start-up
are separate conditions (milestone C).

| symbol | relation (breakeven_v1, equal delivered and Hall-born mix) | table |
|---|---|---|
| **Y** | Y_k(h) = c_k Π_H with c_add = 1, c_cost = 2 − η_b, c_opt = 2/√η_v − η_b. With no fixed overhead the supremum over the delivered share equals this marginal value. A fixed overhead ω_f lowers it to c_sup(ω_f) Π_H. | G1, G4 |
| **X** | X_k(ω) = x* with R(x*)(1 − ω) = 1, R(x) = (1 + n x)²/(1 + d x), n = √(η_v,S/η_v), d = η_b[1 + (1 − χ)(1/η_b − 1)]. `add_only`: X = ω/(1 − ω). No break-even if x* > (1 − η_u0)/η_u0. | G2 |
| **Z** | Z = C_src / Y_k(h). Below it the source cannot pay at h under k, whatever its size. | G5 |
| one inequality | F(x) = (1 + n x)²(1 − ω_f − c x) − (1 + d x) ≥ 0 with c = C_src/(η_t Π_H). For a given delivered cost it gives the payable interval [x_lo, x_hi] of the gain. | G3 |

X, Y and Z are three views of that one inequality. X does not depend on η_t. η_t links the source cost to the delivered
cost (Z) and fixes what a given source power achieves (`achievable_delivered_share`).

The script takes every surface value from `breakeven.py` (`marginal_breakeven_delivered_cost`,
`supremum_breakeven_delivered_cost`, `required_utilization_gain`, `place_evidence`). Its self-checks evaluate the closed
forms of BREAKEVEN_DERIVATION.md §5–6 independently. They also run two `bus_power_boundary_v1`-format ledgers through
`overhead_from_boundary_ledgers`, `achievable_delivered_share` and `evaluate_arm` and require agreement with the coupled
inequality. The build refuses to write if any self-check fails.

## 4. PROPOSED analysis ranges

| axis | values | basis |
|---|---|---|
| V_d | 150–450 V | breakeven_v1 analysis range (PROPOSED) |
| η_b | 0.5, 0.7, 0.9 | breakeven_v1 analysis range (PROPOSED) |
| η_u0 | 0.3, 0.6, 0.9 | enters only through the utilization cap (PROPOSED) |
| η_v | 0.7–1.0 | enters only `optimistic_bound` (PROPOSED) |
| η_ppu,d | evidence range (G1 header) | electrical closure HD-RH24-* (Rhodes et al., IEPC-2024-331 slides; digitized, level 3): 200–1000 W output, 250/400 V output, 24–34 V bus. V_d = 150 V is below the measured output range. |
| η_t | 0.1–1 | lane 18 (§ G11): the upper end is the source-free-duct limit; 0.1 is the lower end of the owner-requested span, not a physical bound |
| ω, ω_f, c | grids in the JSON | analysis grids |
| species | equal delivered and Hall-born mix (A8) | per-ampere results do not depend on species at equal mix; a heavier delivered ion into a lighter Hall beam raises Y (BREAKEVEN_DERIVATION.md §6.4) |

## 5. Placement rules

1. Each entry is converted to **C_src**, bus W per A of ions leaving the RF stage. Every **sourced** conversion is
   applied. Every **missing** conversion is replaced by its physical bound (an efficiency in (0, 1]; an ion-basis factor
   in (0, 1]). So [lo, hi] is a **bound under the stated conditions**, not an estimate. The last step divides by η_t to
   give C_del.
2. The payable condition is C_src ≤ η_t · Y_k(h). The **declared box** is V_d, η_b and η_v over their ranges, η_ppu,d
   over its evidence range, η_t over 0.1–1, and ω_f = 0 (the most favourable; fixed overheads only lower Y).
3. Statuses:
   * **CLEARLY_ABOVE_BREAKEVEN**: lo > η_t,max · Y_max(`optimistic_bound`). It cannot pay under any declared case, at any
     declared Hall point, at any η_t in range.
   * **CLEARLY_BELOW**: hi ≤ η_t,min · Y_min(k) for the stated case k. It pays (for small delivered shares) at every
     declared Hall point and every η_t in range, under at least that case.
   * **STRADDLES**: neither. The per-slice table (G8) and the η_t thresholds (G6) show where it can and cannot pay.
   * **NOT_PLACEABLE**: no ion-current basis can be formed. The missing quantity is named (G9).
4. The JSON also shows, for each unit, where it would sit if every missing conversion were exactly 1
   (`conditional_placement_if_missing_factors_equal_1`). That is **not** a placement and not a bound.

These definitions are PROPOSED (they are not in the RFP). The robust form of CLEARLY_BELOW cannot be met while η_t is
known only down to 0.1 (open question 2 in G12).

## 6. What was placed

* **U-RF-NO25-air-gridded** (Schwertheim et al., IEPC-2025-378, Research Square preprint, doi:10.21203/rs.3.rs-9039885/v1;
  open, per lane 07). This is the only accessed measurement of RF power against ion current on an air mixture. The power
  is the RF-generator DC input from the unregulated bus, so the power reference is **bus**. The ion basis is the
  grid-extracted beam of a gridded RF ion engine. Referring it to ions leaving a gridless pre-ionizer can only lower the
  cost at the same discharge state, but removing the grids changes neutral confinement, so the upper bound is
  conditional on that transfer. Only ranges are reported, so the interval is a corner bound.
* **U-RF-ZHOU24-*** (Zhou, Taccogna, Fajardo, Ahedo, Propulsion and Power Research 13(4) 2024,
  doi:10.1016/j.jppr.2024.10.001, read as arXiv:2407.19322; open, per lane 07). These are model points (level 6):
  prescribed power deposition and Xe-fitted anomalous transport reused for air. The power reference is **absorbed**.
  The chain adds the beam species split (singly charged ions assumed; bounded by all-molecular and all-atomic beams), the
  antenna/plasma coupling (missing, so C_src is unbounded above) and the bus → coil-feed efficiency. That efficiency has
  a sourced range: 0.92 nominal bus → RF-generator output (Schwertheim et al., stage-only, hence an upper bound on the
  chain) and 0.60–0.70 RF-generator DC input → coil feed (Volkmar, Geile, Hannemann, JPP 2018, doi:10.2514/1.B36868,
  authors' preprint; Xe, low flow), both via lane 20. Matching and cable loss on air is TBD (`RF-MATCH-LOSS`).
* **Not placeable:** RF cathode electron currents, power fractions without an ion current, a density-ratio ionization
  fraction, secondary performance tables, an unmeasured ionization degree, and one non-RF heritage entry (G9).
* The remaining matrix topics are listed in the JSON (`other_rf_matrix_topics`) with their role here: coupling and
  generator entries are chain evidence, magnetic-field entries are fixed-load evidence, and the rest is context for
  milestone C.

Numbers, chains and placements are in G6–G9. The η_ppu,d values are also from lane 20 (Rhodes, Benavides, Pinero,
IEPC-2024-331, NASA NTRS 20240006846).

## 7. The region where rf_hall could pay

R_k(h) = {(η_t, C_src): C_src ≤ η_t · Y_k(h)}. Its **outer envelope** (some declared point and case can pay) is
C_src ≤ η_t · Y_max(`optimistic_bound`). Its **inner envelope** (every declared point pays, under `add_only`) is
C_src ≤ η_t · Y_min(`add_only`). Both are lines through the origin in the (η_t, C_src) plane (G5). No RF source has a
measured η_t, so no evidence entry is a point in that plane: each is a C_src interval swept over the η_t range. The
answer to "does any published evidence lie in the region" is generated in G5 and G0.

## 8. Single decisive measurements

The one measurement that places any RF stage by itself is the delivered-ion bus cost C_del = P_bus[rf_source] /
I_delivered, measured on an RF stage plus interstage on air/N₂ at the ICD inlet state. It combines C_src and η_t, and
the thresholds that make it definite are in G10. Per unit, G10 lists the single quantities (ion extraction fraction,
antenna coupling on air, species/charge split, η_t) that would move each STRADDLES or NOT_PLACEABLE entry to a definite
placement. They feed the minimum decisive experiment.

## 9. Regenerate

```
python docs/architecture_comparison/overlays/rf/build_overlay_rf.py            # JSON + generated block below
python docs/architecture_comparison/overlays/rf/build_overlay_rf.py --check    # rebuild in memory, byte-compare
python -m pytest -q tests/test_overlay_rf.py
```

Before the input lanes merge, the inputs are found in the sibling worktrees (or pass `--input-root DIR`). The tests that
rebuild the overlay skip, with the reason, when the pinned inputs cannot be found. The checks on the committed files
always run.

## 10. Generated tables

<!-- BEGIN GENERATED by build_overlay_rf.py: do not edit by hand -->

Everything between these markers is written by `build_overlay_rf.py` from `overlay_rf_v1.json`. Hall-side values are PROPOSED analysis values, not predictions.

### G0. Milestone-A statement (conditional)

Supports milestone **A**. What can be concluded now:

* The power-side break-even of rf_hall against hall_only on bus_power_boundary_v1 is the closed-form inequality set X, Y, Z of breakeven_condition; it is computable at any Hall reference point without an absolute Hall prediction.
* Over the declared box the payable bus cost per delivered ampere lies between 182.1 W/A (add_only, least favourable point) and 2208 W/A (optimistic_bound, most favourable point).
* No accessed RF evidence entry is CLEARLY_ABOVE_BREAKEVEN (0) or CLEARLY_BELOW (0); 7 placeable units straddle and 11 entries are NOT_PLACEABLE. The power break-even therefore gives no basis to set rf_hall aside and no basis to expect it to pay.
* With eta_t known only to lie in [0.1, 1], CLEARLY_BELOW needs C_src <= 0.1 * Y_min = 18.21 bus W/A under add_only; 0 of 7 placeable units have an upper bound of C_src at or below it. eta_t is the decisive unknown on the transport side, the antenna/matching coupling on air on the source side.
* In the per-slice tables 5 placeable units sit above break-even even at eta_t = 1 in 16 (unit, V_d, eta_b, case) combinations, all at V_d = 150 V (the lowest Hall price per beam ampere Pi_H = V_d/(eta_b eta_ppu,d) of the box). Those rest on the lower bound of C_src, which is conditional on singly charged beams and on level-6 model points; they are slice statements, not placements.

rf_hall can be the baseline only if **all** of the following are demonstrated:

* C1 (Y): demonstrated delivered-ion bus cost C_del = P_bus[rf_source]/I_delivered <= Y(h, k) at the Vyovrinda Hall reference point h under the demonstrated response case k, reduced for fixed overheads (Y_sup_fixed_overhead_normalized)
* C2 (Z): demonstrated eta_t >= C_src/Y(h, k) on the ion-current basis
* C3 (X): demonstrated relative utilization gain x >= X(omega) at the operated rf_source bus power, within the cap x <= (1 - eta_u0)/eta_u0 and inside the coupled interval [x_lo, x_hi]
* C4: the response (alpha, chi, eta_v,S, delivered mix) demonstrated in a coupled RF + Hall test. add_only is the least favourable of the three declared cases, but it is not a bound: delivered ions that displace Hall-born ions (alpha < 1) lower Y further (alpha = 0, chi = 0 gives Y = 0)
* C5: a complete bus_power_boundary_v1 ledger for both arms at the same operating mode (all common-component deltas explicit)
* C6: mass, life, thermal and start-up conditions (milestone C) are additional and not assessed here

Not concluded: no winner, no ranking, no statement that rf_hall is or is not worth its power, no comparison with the other pre-ionized arm.

To reach B: admitted Hall transport closure(s) for the Vyovrinda geometry (eta_u0, eta_b, eta_v, V_d per credible-set member) replacing the PROPOSED box; measured delivered-ion bus cost of an RF stage on air/N2 at the ICD inlet state; measured eta_t; measured response (alpha, chi, eta_v,S, delivered mix); matching/antenna coupling on air.

To reach C: mass (s_P, s_T, RF hardware), life (source mechanisms), thermal (thermal_life.py), start-up, cathode, mission closure on the same boundary.

### G1. Y: largest payable bus W per delivered ampere (no fixed overhead)

Min–max over η_ppu,d [0.7705, 0.915] (and η_v 0.7–1.0 for optimistic_bound).

| V_d [V] | η_b | add_only | cost_offset | optimistic_bound |
|---|---|---|---|---|
| 150 | 0.5 | 327.9–389.4 | 491.8–584 | 491.8–736.1 |
| 150 | 0.7 | 234.2–278.1 | 304.4–361.5 | 304.4–470.1 |
| 150 | 0.9 | 182.1–216.3 | 200.4–237.9 | 200.4–322.4 |
| 200 | 0.5 | 437.2–519.1 | 655.7–778.7 | 655.7–981.4 |
| 200 | 0.7 | 312.3–370.8 | 405.9–482.1 | 405.9–626.9 |
| 200 | 0.9 | 242.9–288.4 | 267.2–317.3 | 267.2–429.9 |
| 250 | 0.5 | 546.4–648.9 | 819.7–973.4 | 819.7–1227 |
| 250 | 0.7 | 390.3–463.5 | 507.4–602.6 | 507.4–783.6 |
| 250 | 0.9 | 303.6–360.5 | 333.9–396.6 | 333.9–537.3 |
| 300 | 0.5 | 655.7–778.7 | 983.6–1168 | 983.6–1472 |
| 300 | 0.7 | 468.4–556.2 | 608.9–723.1 | 608.9–940.3 |
| 300 | 0.9 | 364.3–432.6 | 400.7–475.9 | 400.7–644.8 |
| 350 | 0.5 | 765–908.5 | 1148–1363 | 1148–1717 |
| 350 | 0.7 | 546.4–648.9 | 710.4–843.6 | 710.4–1097 |
| 350 | 0.9 | 425–504.7 | 467.5–555.2 | 467.5–752.3 |
| 400 | 0.5 | 874.3–1038 | 1311–1557 | 1311–1963 |
| 400 | 0.7 | 624.5–741.6 | 811.9–964.1 | 811.9–1254 |
| 400 | 0.9 | 485.7–576.8 | 534.3–634.5 | 534.3–859.7 |
| 450 | 0.5 | 983.6–1168 | 1475–1752 | 1475–2208 |
| 450 | 0.7 | 702.6–834.3 | 913.3–1085 | 913.3–1410 |
| 450 | 0.9 | 546.4–648.9 | 601.1–713.8 | 601.1–967.2 |

Declared-box extremes: add_only 182.1–1168 W/A; cost_offset 200.4–1752 W/A; optimistic_bound 200.4–2208 W/A.

### G2. X: required relative utilization gain x* = Δη_u*/η_u0 against the total overhead fraction ω

ω = (P_bus[rf_source] + Σ common-component deltas)/P_d,bus0. With α = 1 the delivered-ion share equals the gain: δ_s* = Δη_u* = x*·η_u0.

| ω | add_only | cost_offset (η_b 0.5) | cost_offset (η_b 0.7) | cost_offset (η_b 0.9) | optimistic_bound (η_b 0.7, η_v 0.7) | optimistic_bound (η_b 0.7, η_v 1.0) |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.05 | 0.05263 | 0.03489 | 0.04038 | 0.04783 | 0.031 | 0.04038 |
| 0.1 | 0.1111 | 0.07321 | 0.085 | 0.1009 | 0.06514 | 0.085 |
| 0.2 | 0.25 (cap: η_u0 0.9) | 0.1626 (cap: η_u0 0.9) | 0.1901 (cap: η_u0 0.9) | 0.2269 (cap: η_u0 0.9) | 0.1451 (cap: η_u0 0.9) | 0.1901 (cap: η_u0 0.9) |
| 0.25 | 0.3333 (cap: η_u0 0.9) | 0.2152 (cap: η_u0 0.9) | 0.2527 (cap: η_u0 0.9) | 0.3024 (cap: η_u0 0.9) | 0.1925 (cap: η_u0 0.9) | 0.2527 (cap: η_u0 0.9) |
| 0.3 | 0.4286 (cap: η_u0 0.9) | 0.2747 (cap: η_u0 0.9) | 0.3238 (cap: η_u0 0.9) | 0.3886 (cap: η_u0 0.9) | 0.246 (cap: η_u0 0.9) | 0.3238 (cap: η_u0 0.9) |
| 0.4 | 0.6667 (cap: η_u0 0.9) | 0.4201 (cap: η_u0 0.9) | 0.5 (cap: η_u0 0.9) | 0.6039 (cap: η_u0 0.9) | 0.378 (cap: η_u0 0.9) | 0.5 (cap: η_u0 0.9) |
| 0.5 | 1 (cap: η_u0 0.6, 0.9) | 0.618 (cap: η_u0 0.9) | 0.744 (cap: η_u0 0.6, 0.9) | 0.905 (cap: η_u0 0.6, 0.9) | 0.559 (cap: η_u0 0.9) | 0.744 (cap: η_u0 0.6, 0.9) |
| 0.6 | 1.5 (cap: η_u0 0.6, 0.9) | 0.9059 (cap: η_u0 0.6, 0.9) | 1.106 (cap: η_u0 0.6, 0.9) | 1.356 (cap: η_u0 0.6, 0.9) | 0.8248 (cap: η_u0 0.6, 0.9) | 1.106 (cap: η_u0 0.6, 0.9) |
| 0.7 | 2.333 (cap: η_u0 0.6, 0.9) | 1.37 (cap: η_u0 0.6, 0.9) | 1.703 (cap: η_u0 0.6, 0.9) | 2.107 (cap: η_u0 0.6, 0.9) | 1.258 (cap: η_u0 0.6, 0.9) | 1.703 (cap: η_u0 0.6, 0.9) |
| 0.75 | 3 (cap: η_u0 0.3, 0.6, 0.9) | 1.732 (cap: η_u0 0.6, 0.9) | 2.178 (cap: η_u0 0.6, 0.9) | 2.708 (cap: η_u0 0.3, 0.6, 0.9) | 1.6 (cap: η_u0 0.6, 0.9) | 2.178 (cap: η_u0 0.6, 0.9) |
| 0.8 | 4 (cap: η_u0 0.3, 0.6, 0.9) | 2.266 (cap: η_u0 0.6, 0.9) | 2.886 (cap: η_u0 0.3, 0.6, 0.9) | 3.608 (cap: η_u0 0.3, 0.6, 0.9) | 2.106 (cap: η_u0 0.6, 0.9) | 2.886 (cap: η_u0 0.3, 0.6, 0.9) |
| 0.85 | 5.667 (cap: η_u0 0.3, 0.6, 0.9) | 3.139 (cap: η_u0 0.3, 0.6, 0.9) | 4.062 (cap: η_u0 0.3, 0.6, 0.9) | 5.109 (cap: η_u0 0.3, 0.6, 0.9) | 2.942 (cap: η_u0 0.3, 0.6, 0.9) | 4.062 (cap: η_u0 0.3, 0.6, 0.9) |
| 0.9 | 9 (cap: η_u0 0.3, 0.6, 0.9) | 4.854 (cap: η_u0 0.3, 0.6, 0.9) | 6.405 (cap: η_u0 0.3, 0.6, 0.9) | 8.11 (cap: η_u0 0.3, 0.6, 0.9) | 4.597 (cap: η_u0 0.3, 0.6, 0.9) | 6.405 (cap: η_u0 0.3, 0.6, 0.9) |

"cap: η_u0 …" = x* exceeds (1 − η_u0)/η_u0 for those η_u0: no break-even there. Full grid in the JSON (`tables.X_required_relative_gain`).

### G3. Coupled X–Y: payable relative-gain interval [x_lo, x_hi] for a delivered cost c·Π_H

Uncapped; apply x ≤ (1 − η_u0)/η_u0 = 2.333 (eta_u0=0.3), 0.6667 (eta_u0=0.6), 0.1111 (eta_u0=0.9). '—' = no payable gain.

| c = C_del/Π_H | ω_f | add_only | cost_offset (η_b 0.7) | optimistic_bound (η_b 0.7, η_v 0.9) |
|---|---|---|---|---|
| 0.2 | 0.0 | 0–4 | 0–4.284 | 0–4.352 |
| 0.5 | 0.0 | 0–1 | 0–1.265 | 0–1.331 |
| 0.8 | 0.0 | 0–0.25 | 0–0.5 | 0–0.5646 |
| 1.0 | 0.0 | — | 0–0.2416 | 0–0.3054 |
| 1.2 | 0.0 | — | 0–0.06752 | 0–0.1307 |
| 1.5 | 0.0 | — | — | — |
| 0.2 | 0.05 | 0.0679–3.682 | 0.04872–3.988 | 0.04423–4.061 |
| 0.5 | 0.05 | 0.1298–0.7702 | 0.07207–1.095 | 0.06245–1.171 |
| 0.8 | 0.05 | — | — | 0.1209–0.3832 |
| 1.0 | 0.05 | — | — | — |
| 1.2 | 0.05 | — | — | — |
| 1.5 | 0.05 | — | — | — |

### G4. Fixed overhead lowers Y: c_sup(ω_f) = Y_sup/Π_H (η_u0 = 0.6)

| ω_f | add_only | cost_offset (η_b 0.7) | optimistic_bound (η_b 0.7, η_v 0.9) |
|---|---|---|---|
| 0 | 1 | 1.3 | 1.408 |
| 0.01 | 0.81 | 1.059 | 1.148 |
| 0.02 | 0.7372 | 0.9661 | 1.048 |
| 0.05 | 0.6028 | 0.794 | 0.8624 |
| 0.1 | 0.4675 | 0.6197 | 0.6739 |
| 0.2 | 0.3 | 0.409 | 0.4458 |

A value ≤ 0 means no source cost pays. ω_f collects the non-ion-scaling loads (common-component deltas, generator standby, any RF magnet booked in rf_source); all are TBD.

### G5. Z and the payable region: largest payable source cost C_src,max = η_t·Y [bus W per A of source-exit ions]

| η_t | outer envelope (some declared point, optimistic_bound) | inner envelope (every declared point, add_only) | add_only @300 V, η_b 0.7 | cost_offset @300 V, η_b 0.7 | optimistic_bound @300 V, η_b 0.7 |
|---|---|---|---|---|---|
| 0.1 | 220.8 | 18.21 | 46.84–55.62 | 60.89–72.31 | 60.89–94.03 |
| 0.2 | 441.6 | 36.43 | 93.68–111.2 | 121.8–144.6 | 121.8–188.1 |
| 0.3 | 662.5 | 54.64 | 140.5–166.9 | 182.7–216.9 | 182.7–282.1 |
| 0.4 | 883.3 | 72.86 | 187.4–222.5 | 243.6–289.2 | 243.6–376.1 |
| 0.5 | 1104 | 91.07 | 234.2–278.1 | 304.4–361.5 | 304.4–470.1 |
| 0.6 | 1325 | 109.3 | 281–333.7 | 365.3–433.9 | 365.3–564.2 |
| 0.7 | 1546 | 127.5 | 327.9–389.4 | 426.2–506.2 | 426.2–658.2 |
| 0.8 | 1767 | 145.7 | 374.7–445 | 487.1–578.5 | 487.1–752.2 |
| 0.9 | 1987 | 163.9 | 421.5–500.6 | 548–650.8 | 548–846.2 |
| 1.0 | 2208 | 182.1 | 468.4–556.2 | 608.9–723.1 | 608.9–940.3 |

Z = C_src/Y: a source of cost C_src needs η_t ≥ C_src/Y (JSON `tables.Z_min_eta_t`). No accessed RF evidence entry lies inside the inner region (where rf_hall would pay at every declared Hall point, under add_only, at every eta_t in range). 7 of 7 placeable units intersect the outer region (they could pay somewhere in the declared box for a high enough eta_t). No RF source has a measured eta_t, so no entry is a located point in the (eta_t, C_src) plane: each is a C_src interval swept over the eta_t range.

### G6. Evidence placements

| unit | entries | reported | power reference | C_src bound [bus W/A exit ions] | C_del bound [bus W/A delivered] | placement | η_t below which CLEARLY_ABOVE | η_t for CLEARLY_BELOW (add_only) |
|---|---|---|---|---|---|---|---|---|
| U-RF-NO25-air-gridded | RF-NO25-D1, RF-NO25-02, RF-NO25-09, RF-NO25-01 | 206.7–1600 W/A | bus | (0, 1600] | (0, 16000] | **STRADDLES** | none (C_src lower bound → 0) | 8.784 (> 1: unreachable) |
| U-RF-ZHOU24-N2-1500W | RF-ZHOU24-D1, RF-ZHOU24-05, RF-ZHOU24-06 | 435.3 eV per injected molecule | absorbed | [288.5, unbounded) | [288.5, unbounded) | **STRADDLES** | 0.1307 | none (C_src unbounded above) |
| U-RF-ZHOU24-N2-2000W | RF-ZHOU24-D2, RF-ZHOU24-07, RF-ZHOU24-01, RF-ZHOU24-08 | 580.4 eV per injected molecule | absorbed | [325.2, unbounded) | [325.2, unbounded) | **STRADDLES** | 0.1473 | none (C_src unbounded above) |
| U-RF-ZHOU24-N2-1400W-eta_u75 | RF-ZHOU24-03 | 406.3 eV per injected molecule | absorbed | [294.4, unbounded) | [294.4, unbounded) | **STRADDLES** | 0.1333 | none (C_src unbounded above) |
| U-RF-ZHOU24-O-1500W | RF-ZHOU24-D3, RF-ZHOU24-09, RF-ZHOU24-10 | 248.7 eV per injected atom | absorbed | [278.7, unbounded) | [278.7, unbounded) | **STRADDLES** | 0.1262 | none (C_src unbounded above) |
| U-RF-ZHOU24-O-700W-eta_u75 | RF-ZHOU24-04 | 116.1 eV per injected atom | absorbed | [168.2, unbounded) | [168.2, unbounded) | **STRADDLES** | 0.07619 | none (C_src unbounded above) |
| U-RF-ZHOU24-O2-1500W | RF-ZHOU24-11 | 497.5 eV per injected molecule | absorbed | [278.7, unbounded) | [278.7, unbounded) | **STRADDLES** | 0.1262 | none (C_src unbounded above) |

Evidence class of every placement: model-derived (this overlay on breakeven_v1), conditional on A1–A8 of BREAKEVEN_DERIVATION.md §3 and on every chain condition below.

### G7. Conversion chains to bus W per delivered ampere

Units with an identical chain share one table; the unit-specific numbers are in G6 and in the JSON.

**U-RF-NO25-air-gridded** (gas 50:50 N2/O2 by volume; power reference `bus`: RF-generator DC input drawn from the unregulated 26-32 V bus (RF-NO25-01: 'from the unregulated bus to RF'); in bus_power_boundary_v1 this is P_bus[rf_source] when the RF generator is fed directly from the propulsion DC bus)

| step | status | factor | direction, formula, missing quantity or note |
|---|---|---|---|
| power reference -> P_bus[rf_source] | sourced | 1–1 |  |
| ion basis: extracted beam A -> A of ions leaving a gridless source exit | missing | 0–1 | can only LOWER the cost (multiply by I_beam/I_exit <= 1) at the SAME discharge state; ion extraction fraction I_beam/I_exit (effective screen-grid ion transparency) at the reported set points; also whether the gridded discharge regime transfers to a pre-ionizer regime (regime_match 'partial'): removing the grids changes neutral confinement, so the same RFG power need not give the same discharge state. The upper bound hi is conditional on that transfer |
| set-point pairing | missing | 1–1 | narrows the interval, no shift; per-set-point (P_RFG, I_beam) pairs; only ranges are in the text (source Fig. 14 or data needed; the corner bound spans the whole interval) |
| A of source-exit ions -> A of ions delivered into the Hall channel (divide by eta_t, ion-current basis) | missing (no measured or model-derived air value; PROPOSED range) | 1–10 | eta_t of the interstage on air (lane 18 inputs: dissociative-recombination rates valid at the interstage T_e, junction ion capture, magnetized wall flux, source exit state) |

C_src bound conditional on: the gridded discharge state transfers to the gridless pre-ionizer (hi); the RF generator is fed directly from the propulsion DC bus (otherwise divide by a bus -> RFG converter efficiency <= 1, which raises hi).

**U-RF-ZHOU24-N2-1500W, U-RF-ZHOU24-N2-2000W, U-RF-ZHOU24-N2-1400W-eta_u75, U-RF-ZHOU24-O2-1500W** (gas N2; O2; power reference `absorbed`: plasma-absorbed power P_a prescribed in the HYPHEN simulation (before any RF-chain loss); Xe-fitted anomalous transport reused for air (RF-ZHOU24-14, level 6))

| step | status | factor | direction, formula, missing quantity or note |
|---|---|---|---|
| absorbed energy per injected particle -> absorbed W per A of beam ions | inferred (our arithmetic on model-derived set points) | — | P_a / (eta_u * mdot / m_ion * e), singly charged ions; the beam species split is not given per case: bounded by the all-molecular and all-atomic singly charged beams; beam species and charge-state split (Z = 1 is ASSUMED; multiply charged ions would lower the W per A; verify in the source) |
| absorbed -> net RF at the coil feed (divide by antenna coupling eta_ant = P_abs/P_coil) | missing | 1–unbounded | can only RAISE the cost (eta_ant <= 1); antenna/plasma coupling on air at the operating point (forward, reflected, matching-network and antenna loss; RF_SOURCE_EVIDENCE.md section 4 item 3) |
| coil feed -> P_bus[rf_source] (divide by eta_rf_source, bus -> coil feed) | sourced (evidence range, applicability-limited) | 1.087–1.667 | matching-network and cable loss on air across the ABEP flow range (electrical_closure RF-MATCH-LOSS: TBD) |
| fixed rf_source loads | not applied (conservative for the lower bound) | — | the model has an applied field (B = 0.12 T, a model input). If an electromagnet produces it (not stated in the matrix entries; verify in the source), its power is not in P_a. bus_power_boundary_v1 has no RF magnet component, so it would be booked inside rf_source as a non-ion-scaling (fixed) load, which LOWERS the payable cost (Y_sup_fixed_overhead_normalized); leaving it out keeps the lower bound of C_src valid |
| A of source-exit ions -> A of ions delivered into the Hall channel (divide by eta_t, ion-current basis) | missing (no measured or model-derived air value; PROPOSED range) | 1–10 | eta_t of the interstage on air (lane 18 inputs: dissociative-recombination rates valid at the interstage T_e, junction ion capture, magnetized wall flux, source exit state) |

C_src bound conditional on: singly charged beam ions (Z = 1 ASSUMED; a multiply charged share would lower lo, by at most a factor Z); the model point itself (level 6; prescribed power deposition, Xe-fitted transport reused for air).

**U-RF-ZHOU24-O-1500W, U-RF-ZHOU24-O-700W-eta_u75** (gas O; power reference `absorbed`: plasma-absorbed power P_a prescribed in the HYPHEN simulation (before any RF-chain loss); Xe-fitted anomalous transport reused for air (RF-ZHOU24-14, level 6))

| step | status | factor | direction, formula, missing quantity or note |
|---|---|---|---|
| absorbed energy per injected particle -> absorbed W per A of beam ions | inferred (our arithmetic on model-derived set points) | — | P_a / (eta_u * mdot / m_ion * e), singly charged ions; single atomic ion species; beam species and charge-state split (Z = 1 is ASSUMED; multiply charged ions would lower the W per A; verify in the source) |
| absorbed -> net RF at the coil feed (divide by antenna coupling eta_ant = P_abs/P_coil) | missing | 1–unbounded | can only RAISE the cost (eta_ant <= 1); antenna/plasma coupling on air at the operating point (forward, reflected, matching-network and antenna loss; RF_SOURCE_EVIDENCE.md section 4 item 3) |
| coil feed -> P_bus[rf_source] (divide by eta_rf_source, bus -> coil feed) | sourced (evidence range, applicability-limited) | 1.087–1.667 | matching-network and cable loss on air across the ABEP flow range (electrical_closure RF-MATCH-LOSS: TBD) |
| fixed rf_source loads | not applied (conservative for the lower bound) | — | the model has an applied field (B = 0.12 T, a model input). If an electromagnet produces it (not stated in the matrix entries; verify in the source), its power is not in P_a. bus_power_boundary_v1 has no RF magnet component, so it would be booked inside rf_source as a non-ion-scaling (fixed) load, which LOWERS the payable cost (Y_sup_fixed_overhead_normalized); leaving it out keeps the lower bound of C_src valid |
| A of source-exit ions -> A of ions delivered into the Hall channel (divide by eta_t, ion-current basis) | missing (no measured or model-derived air value; PROPOSED range) | 1–10 | eta_t of the interstage on air (lane 18 inputs: dissociative-recombination rates valid at the interstage T_e, junction ion capture, magnetized wall flux, source exit state) |

C_src bound conditional on: singly charged beam ions (Z = 1 ASSUMED; a multiply charged share would lower lo, by at most a factor Z); the model point itself (level 6; prescribed power deposition, Xe-fitted transport reused for air).

### G8. Per-slice placement (A = cannot pay even at η_t = 1, S = straddles, B = pays everywhere in the slice)

| unit | case | 150 V, η_b 0.5 | 150 V, η_b 0.7 | 150 V, η_b 0.9 | 300 V, η_b 0.5 | 300 V, η_b 0.7 | 300 V, η_b 0.9 | 450 V, η_b 0.5 | 450 V, η_b 0.7 | 450 V, η_b 0.9 |
|---|---|---|---|---|---|---|---|---|---|---|
| U-RF-NO25-air-gridded | add_only | S | S | S | S | S | S | S | S | S |
| U-RF-NO25-air-gridded | cost_offset | S | S | S | S | S | S | S | S | S |
| U-RF-NO25-air-gridded | optimistic_bound | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1500W | add_only | S | A | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1500W | cost_offset | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1500W | optimistic_bound | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-2000W | add_only | S | A | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-2000W | cost_offset | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-2000W | optimistic_bound | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1400W-eta_u75 | add_only | S | A | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1400W-eta_u75 | cost_offset | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-N2-1400W-eta_u75 | optimistic_bound | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-O-1500W | add_only | S | A | A | S | S | S | S | S | S |
| U-RF-ZHOU24-O-1500W | cost_offset | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-O-1500W | optimistic_bound | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-O-700W-eta_u75 | add_only | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-O-700W-eta_u75 | cost_offset | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-O-700W-eta_u75 | optimistic_bound | S | S | S | S | S | S | S | S | S |
| U-RF-ZHOU24-O2-1500W | add_only | S | A | A | S | S | S | S | S | S |
| U-RF-ZHOU24-O2-1500W | cost_offset | S | S | A | S | S | S | S | S | S |
| U-RF-ZHOU24-O2-1500W | optimistic_bound | S | S | S | S | S | S | S | S | S |

### G9. NOT_PLACEABLE entries

| entry | evidence class / level | why | missing quantity |
|---|---|---|---|
| RF-NO25-03 | measured / 3 | electron current extracted from an RF plasma cathode, not ion production | ion current leaving the cathode plasma (or its ion production rate) per bus W |
| RF-NO25-D2 | inferred / 3 | bus W per A of extracted ELECTRON current (cathode), not an ion production cost | ion current leaving the cathode plasma per bus W |
| RF-ZHOU24-06 | model-derived / 6 | share of absorbed power in inelastic collisions; the set point is placed as U-RF-ZHOU24-N2-1500W | an ion current (a power fraction carries none); the same set point is placed through its eta_u |
| RF-ZHOU24-08 | model-derived / 6 | share of absorbed power in inelastic collisions; the set point is placed as U-RF-ZHOU24-N2-2000W | an ion current (a power fraction carries none); the same set point is placed through its eta_u |
| RF-ZHOU24-10 | model-derived / 6 | share of absorbed power in inelastic collisions; the set point is placed as U-RF-ZHOU24-O-1500W | an ion current (a power fraction carries none); the same set point is placed through its eta_u |
| RF-ZHOU24-02 | model-derived / 6 | absorbed power at the model's maximum thrust efficiency on atomic O (1250 W, 1 mg/s) | propellant utilization eta_u (or beam current) at that set point |
| RF-IPG6S-08 | TBD (not measured) / 3 | ionization degree of the IPG6-S air/O2 plasma was not measured (value TBD in the source) | ion current or ionization fraction with the flow and power at the bus |
| RF-SCHU24-D2 | inferred / 3 | ionization fraction n_e/n_n of an 80/20 N2/O2 ICP at 10 Pa, 800 W: a density ratio, no ion outflow | ion current leaving the source (or wall ion-loss flux) at a stated bus power; the generator/matchbox losses are not separated either (RF-SCHU24-05) |
| RF-TAKA22-05 | measured / 5 | thrust efficiency of the Michigan RF plasma thruster as re-tabulated (secondary; gas not stated) | ion beam current or mass utilization and the gas; primary not accessed |
| RF-DUPP26-02 | assumed / 5 | review-table thrust-to-power range (assumed; not supported by an accessed primary) | any measured ion current per power |
| RF-SITA19-02 | measured / 3 | RAM-EP thrust of a double-stage device whose ionization stage the performance model powers by a discharge voltage; no RF source is described (RF-SITA19-01) | an RF-source quantity (this entry is outside the RF evidence scope) |

### G10. Single measurements that would give a definite placement

* **Common, decisive by itself:** delivered-ion bus cost C_del = P_bus[rf_source] / I_delivered, with I_delivered the ion current entering the Hall channel from an RF stage + interstage on air/N2 at the ICD inlet state (one measurement that combines C_src and eta_t). C_del > 2208 W/A → CLEARLY_ABOVE_BREAKEVEN; C_del ≤ 182.1 W/A → CLEARLY_BELOW (add_only); in between: placement depends on the Hall reference point and response case: needs milestone-B quantities (admitted closure; measured alpha, chi, eta_v,S).
* **U-RF-NO25-air-gridded** (STRADDLES): per-set-point (P_RFG, I_beam) pairs from the source's Fig. 14 or data (narrows 206.7-1600 W/A); ion extraction fraction I_beam/I_exit of that source (effective screen-grid ion transparency), which turns the extracted-beam cost into a source-exit cost; eta_t of the Vyovrinda interstage (lane 18 inputs: DR rates valid at the interstage T_e, junction capture, magnetized wall flux); or, decisive by itself: C_del measured on a gridless RF stage + interstage (decisive_measurement_common).
* **U-RF-ZHOU24-N2-1500W** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (N2+/N+, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **U-RF-ZHOU24-N2-2000W** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (N2+/N+, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **U-RF-ZHOU24-N2-1400W-eta_u75** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (N2+/N+, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **U-RF-ZHOU24-O-1500W** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (O+ and any O2+ from wall recombination, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **U-RF-ZHOU24-O-700W-eta_u75** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (O+ and any O2+ from wall recombination, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **U-RF-ZHOU24-O2-1500W** (STRADDLES): antenna/plasma coupling eta_ant and matching/cable loss on air at the operating point (the only step that leaves C_src unbounded above); beam species/charge split of the source exit (O2+/O+, multiply charged fraction); a measurement replacing the model (level 6): bus W and exit ion current of an RF stage on the same gas; eta_t of the Vyovrinda interstage.
* **NOT_PLACEABLE (RF-NO25-03, RF-NO25-D2, RF-ZHOU24-06, RF-ZHOU24-08, RF-ZHOU24-10, RF-ZHOU24-02, RF-IPG6S-08, RF-SCHU24-D2, RF-TAKA22-05, RF-DUPP26-02):** bus W (RF-generator DC input) and the ion current leaving the RF stage on air/N₂ at the ICD inlet state, at the same set point. RF-SITA19-02 is outside the RF evidence scope.

### G11. Interstage transport efficiency η_t (lane 18)

* Model: `interstage_v1`. Range used: 0.1–1.0 (PROPOSED analysis range (assumed; not a prediction, not a design value; owner to confirm)).
* Air value: TBD - interstage_v1 refuses every realistic air case: the only sourced N2+/O2+ dissociative-recombination rates are valid below 1200 K (0.103 eV), far below the interstage T_e; the junction ion-capture fraction, a magnetized wall-flux closure, N/O wall recombination and the RF source exit state are also TBD (INTERSTAGE_MODEL.md sections 1, 6 and 9).
* Upper end: eta_t <= 1 on the ion-current basis for a source-free duct (breakeven_v1 accepts 0 < eta_t <= 1; in-duct ionization, eta_t > 1, is refused there). interstage_v1's strong_axial_B_no_radial_loss closure (h = 0, Lieberman short course slide 53) with junction capture 1 is the idealized upper limit on duct transmission, not a prediction.
* Lower end: 0.1 is the lower end of the owner-requested analysis span (breakeven_v1 ETA_T); it is NOT a physical bound. eta_t below 0.1 only moves every placement towards CLEARLY_ABOVE_BREAKEVEN.
* Ion basis: eta_t = ion CURRENT delivered into the Hall channel / ion current leaving the source; it pairs with costs in W per A (INTERSTAGE_MODEL.md section 8); a cost per ion COUNT pairs with eta_transport_particle.

### G12. Open questions for the owner

1. Accept the PROPOSED analysis box (V_d 150-450 V, eta_b 0.5-0.9, eta_v 0.7-1.0, eta_t 0.1-1) and the use of the electrical_closure discharge-supply evidence range for eta_ppu,d?
2. Accept the robust placement definitions (CLEARLY_BELOW over the whole declared box and eta_t range)? With eta_t unmeasured down to 0.1 it cannot be met by any RF source cost above 0.1 * Y_min.
3. bus_power_boundary_v1 has no RF magnet component: a B-assisted RF stage would book its magnet inside rf_source (fixed load). Confirm, or add a component in a v2 boundary.
4. Is the RF generator fed directly from the propulsion DC bus (as in the NewOrbit source)? Otherwise a bus -> RFG converter efficiency enters every chain.
5. (electrical_closure) Which boundary does the RFP '< 1.5 kW' refer to (propulsion bus input or other)? (also raised by the boundary lane)
6. (electrical_closure) Target bus voltage: the only sub-kW discharge-supply efficiency data found is 24-34 V (28 V class).

Placement counts: CLEARLY_ABOVE_BREAKEVEN 0, CLEARLY_BELOW 0, STRADDLES 7, NOT_PLACEABLE 11. Self-checks: c_norm_matches_closed_form_and_supremum pass, case_ordering_add_le_cost_le_optimistic pass, add_only_X_equals_omega_over_1_minus_omega pass, coupled_interval_endpoints_are_roots pass, add_only_coupled_interval_matches_quadratic pass, R_of_x_matches_breakeven_efficiency_ratio pass, coupled_solver_matches_place_evidence pass, ledger_supply_side_matches_coupled_inequality pass, every_cost_topic_entry_placed_or_not_placeable pass, Y_band_consistent_with_place_evidence pass.

<!-- END GENERATED -->
