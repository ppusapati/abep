# ECR evidence on the ecr_hall break-even surfaces (`overlay_ecr_v1`)

**Follow-on:** `fo_ecr_breakeven_overlay` (trigger `T_ECR_OVERLAY`) · **Boundary:** `bus_power_boundary_v1` ·
**Date:** 2026-09-26 · **Status:** conditional inequalities over PROPOSED analysis ranges.

This overlay places the published ECR source evidence on the break-even relations for `ecr_hall` against
`hall_only`, and it includes the interstage transport efficiency in that placement. Everything here is a
**conditional inequality**. It is not a prediction and not a ranking. It names no architecture, takes no hard-gate
decision and makes no comparison with the other pre-ionizer arm. No Hall transport closure, screening candidate or
absolute Hall number is used: the credible set is empty (gate 3), so every Hall-only quantity is an analysis
parameter.

| file | role |
|---|---|
| `overlay_ecr_v1.json` | the overlay: condition tables, every evidence placement with its conversion chain, the region, the measurements that would make each placement definite, the milestone-A statement, self-checks, pinned inputs |
| `build_overlay_ecr.py` | deterministic builder; `--check` rebuilds in memory and byte-compares the JSON and the generated tables below |
| `ECR_BREAKEVEN_OVERLAY.md` | this page (prose by hand; tables G1–G11 generated) |
| `tests/test_overlay_ecr.py` | reproducibility, conversion-chain completeness, boundary name, wording |

Reproduce: `python docs/architecture_comparison/overlays/ecr/build_overlay_ecr.py --check`.

## 0. Milestone support

| milestone | what this delivers | what is still needed to reach it |
|---|---|---|
| **A: conditional selection (supported)** | The owner's break-even condition for `ecr_hall` stated as X / Y / Z over the PROPOSED ranges and the three response cases (§2). Every ECR evidence entry placed against it, with its conversion chain or the missing quantity (§3). The region where `ecr_hall` could pay, and which evidence lies in it (§4). The single measurements that would make each placement definite (§5). The conditional statement and its explicit conditions (§6). | The owner's acceptance of breakeven_v1 assumptions A1–A8, of the declared basis (φ, k) and of the PROPOSED placement rules. |
| B: physics-backed selection | Nothing yet. The same relations accept an admitted closure's Π_H, η_b, η_v and η_u0 per member, which collapses the Hall box to points. | Admitted Hall transport closure(s) for the Vyovrinda geometry; measured α, χ, η_v,S (this collapses the response case); measured end-to-end C_del,bus, or φ, k, η_chain and η_t separately, on N₂/O₂/O at the common feed state. |
| C: proposal/PDR freeze | Nothing. | Mass and life break-even inputs (breakeven_v1 §§7–8, all TBD), thermal closure, startup/cathode and integrated mission closure on the same boundary. |

## 1. Common boundary and notation

**Boundary.** `bus_power_boundary_v1` (`abep_sim/arch_boundary.py`, built by the bus-power boundary lane; referenced,
not imported). P_bus is all DC-bus power drawn by the propulsion string at the bus input terminals. It is **never**
absorbed RF power, source-only power or discharge-only power. The `ecr_hall` source components are `ecr_source` and
`ecr_magnet`. The common components are `hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control,
compressor, thermal_control, housekeeping`. The feed state (ṁ and species) is common and is never changed by this
analysis. Hall-closure uncertainty stays inside the ionization/acceleration block.

| symbol | meaning |
|---|---|
| Π_H = V_d/(η_b η_ppu,d) | Hall-only bus price per Hall beam ampere = P_bus,hall_only[hall_discharge]/I_b0 [bus W/A] |
| O, ω = O/P_bus,hall_only[hall_discharge] | total added bus power of `ecr_hall` (ecr_source + ecr_magnet + common deltas) and its fraction |
| ω_f | the fixed, non-ion-scaling part of ω (ecr_magnet + common deltas). `breakeven.overhead_from_boundary_ledgers` splits two v1 ledgers into generator_W (= ecr_source) and fixed_W. A permanent-magnet `ecr_magnet` is 0 W, passed explicitly |
| X = Δη_u/η_u0 | relative utilization gain; at α = 1 (all three cases) it equals the delivered share I_delivered/I_b0 at equal mix. Cap: X ≤ (1 − η_u0)/η_u0 |
| Y | bus W per ampere **delivered into the Hall beam** at which `ecr_hall` still breaks even |
| C_src,bus | bus W per ampere of ions **leaving the source exit** |
| η_t | interstage transport efficiency: delivered ion current / source-exit ion current (charge-current basis, lane 18) |
| Z = C_src,bus/Y | the minimum η_t a source of cost C_src,bus needs |
| φ, k, η_chain | reported power plane → net microwave power at the coupling input (φ); reported ion basis → source-exit ion current (k); bus → coupling input chain efficiency (η_chain) |

**Response cases** (breakeven_v1; α = 1 in all three; equal delivered and Hall-born mix):

| case | χ | η_v,S | (r, p) = (R_T, R_P) | Y/Π_H at X → 0, ω_f = 0 |
|---|---|---|---|---|
| `add_only` | 0 | η_v | (1, 1) | 1 |
| `cost_offset` | 1 | η_v | (1, η_b) | 2 − η_b |
| `optimistic_bound` | 1 | 1 | (1/√η_v, η_b) | 2/√η_v − η_b (the most favourable corner of the declared box; elimination reference of breakeven_v1) |

Inherited assumptions: breakeven_v1 A1–A8 (`docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md` §3), all
*assumed*.

**Analysis ranges** (PROPOSED, assumed; from breakeven_v1): V_d 150–450 V, η_b 0.5–0.9, η_u0 0.3/0.6/0.9, η_v 0.7–1.0
(optimistic case), ω_f 0–0.2 and η_t 0.1–1. There is one change. The η_ppu,d axis is the envelope of the lane-20
digitized discharge-supply efficiencies (`electrical_closure_data_v1.json`, `hall_discharge.efficiency_evidence`,
NASA SSEP sub-kW breadboard, digitized, level 3). It replaces the single assumed 0.9 of breakeven_v1, and 0.9 lies inside.
That evidence covers 200–500 V outputs, so V_d = 150 V extrapolates the supply data.

## 2. (1) The break-even condition in the owner's form

> **`ecr_hall` breaks even with `hall_only` in bus power on `bus_power_boundary_v1` ONLY IF it delivers a relative
> utilization gain of at least X, at no more than Y bus W per delivered A, and with an interstage transport efficiency
> of at least Z:**
>
> * X_lo(Y, ω_f) ≤ X ≤ min(X_hi(Y, ω_f), (1 − η_u0)/η_u0). Equivalently, for a given total overhead fraction ω:
>   X ≥ X*(ω), the root of (1 − ω)(1 + rX)² = 1 + pX (add_only: X* = ω/(1 − ω)).
> * Y = Π_H · (g_case(X) − ω_f/X), with g_case(X) = (2r − p + r²X)/(1 + rX)² and R = (1 + rX)²/(1 + pX).
> * Z = C_src,bus / Y. Z > 1 means that no η_t pays.

This is a **necessary** condition, not a sufficient one: mass and life break-even (breakeven_v1 §§7–8) are separate
and all their inputs are TBD. The reading of the three quantities:

* **X and Y are one inequality.** The generator share of the overhead is ω_gen = (Y_actual/Π_H)·X. At ω_f = 0 every
  share up to X_hi pays (X_lo = 0), and the payable Y falls as X grows (g is strictly decreasing). A fixed overhead
  ω_f > 0 (an electromagnet, common deltas) lowers Y and makes a minimum share X_lo > 0 necessary. Tables G2 and G3 give
  Y(X, ω_f) and [X_lo, X_hi](Y, ω_f). The JSON holds every case, η_b and η_v combination
  (`breakeven_condition.tables`).
* **Y at the Hall reference.** At ω_f = 0 and X → 0, Y = Π_H (2r − p). G1 gives it at three slices of the PROPOSED
  box: the most favourable corner (the box maximum), the worked reading of `BREAKEVEN_SURFACES.md` (300 V, η_b 0.7,
  η_ppu,d 0.9, η_v 0.9) and the least favourable corner (the box minimum). The build checks that the corners are the box
  extremes for every case. `Y_sup_W_per_A_omega_f_0` in the JSON tabulates Y over V_d, η_b and η_ppu,d. `Y_sup_over_Pi_H`
  gives the supremum over X with a fixed overhead, per η_u0 cap.
* **Z.** G5 gives Z against C_src,bus at the three slices, and at the mid reference for ω_f > 0.
* **η_t does not change the requirement.** X*(ω) and Y do not depend on η_t (breakeven_v1 §5). η_t only converts
  source-exit cost into delivered cost: C_del,bus = C_src,bus/η_t.

## 3. (2) Evidence placements

### 3.1 Conversion chain (every placed entry carries it in `evidence_placements[].conversion_chain`)

```
C_del,bus = C_reported · φ · k / (η_chain · η_t)        [bus W per A delivered into the Hall beam]
```

| step | what is available | evidence |
|---|---|---|
| reported | W/A = eV per singly charged ion (ECR-D025), with the source's own power plane and ion basis | as published (lane 08) |
| φ: power plane → net microwave power at the ABEP coupling input | Plane not stated: φ = 1 is **assumed** (neither bound). A forward plane gives φ ≤ 1 and an absorbed plane gives φ ≥ 1. The JSON carries an illustrative spread from *other* devices, not a bound: coax transmission 0.7778–0.8 (ECR-D016) and coupling 0.78–0.99 (ECR-E030/E031). Incident power with reflected power not subtracted (ECR-D023): φ ≤ 1, a definitional bound. 'Transmitted' at a coupler upstream of ≥ 2 dB of line loss (ECR-D021): φ ≤ 0.631, a sourced bound (ECR-D015). | assumed / model-derived bound |
| k: reported ion basis → source-exit ion current of a gridless pre-ionizer | **TBD** for every entry, taken as k = 1 (assumed). A grid-extracted beam excludes grid interception, which can lower the cost per exit ampere. The pre-ionizer runs at the common feed flow, which changes the cost in an unknown direction. | assumed |
| η_chain: bus → coupling input | Only one system-level value exists: the Hayabusa 4.2 GHz TWT amplifier, (32 + 8) W RF / 110 W DC = 0.3636 (lane 20 `EC-HAYABUSA-TWTA` = lane 08 ECR-D017, inferred, flight heritage). It excludes the feed and isolator. The stage-only values are **upper bounds** on the chain (lane-20 rule): GaN stage PAE 0.64 / drain efficiency 0.729 (`EC-NAKATANI15-GAN`), magnetron tube 0.54 (`EC-KAZAKEVICH24-MAG`), GaN device PAE 0.785 (ECR-E045), and > 0.70 for a 5 W breadboard (ECR-E042). Isolator/feed loss is TBD (`EC-ISOLATOR-FEED`). **No sourced lower bound**, so every bus cost is unbounded above. 0.3636 serves only as the *stated reference chain* of the CLEARLY_BELOW test. | inferred reference; definitional upper bound 1 |
| η_t: source exit → Hall beam | Range 0.1–1, PROPOSED (breakeven_v1 axis). Lane 18 basis: interstage_v1 computes no η_t for any realistic air or Xe case because its junction capture fraction, magnetized cross-field h, dissociative recombination above 1200 K, ion–neutral cross sections and wall recombination are TBD, and it refuses rather than guess. The upper end 1 is its idealized limit: zero-length duct, capture 1 (`test_zero_length_gives_unit_transport_and_no_losses`). A closed junction gives 0 (`test_closed_channel_transmits_nothing`), and the lower end 0.1 is the owner-requested span, not a physical bound. | assumed; endpoint 1 model-derived |

**Ionization floor (strict lower bound).** A bus cost per ampere of ion current cannot be below the lowest first
ionization energy of the feed's species. An ion of charge Z needs Z successive ionization energies, each above the
first, and N⁺ formed from N₂ also needs the positive N₂ dissociation energy. The floors come from the interstage_v1
catalogue (NIST): N₂ feed IE(N) = 14.53413 eV, below IE(N₂) = 15.581 eV; Xe feed 12.1298437 eV; atomic-O feed
13.618055 eV. The air-mixture floor is TBD, because the O₂ ionization energy is TBD in interstage_v1. The floor holds
for every power plane, ion basis, chain and η_t.

### 3.2 Placement rules (PROPOSED for the owner)

These rules use the declared basis: φ as declared, k = 1, and ω_f = 0 (permanent-magnet `ecr_magnet`, zero common
deltas).

* **CLEARLY_ABOVE_BREAKEVEN:** the cost exceeds Y_max of every case at the most favourable Hall corner, with
  η_chain = 1 and η_t = 1. Such an entry cannot pay under any declared case at any η_t in range. When the declared
  value is only an upper bound (ECR-D021, ECR-D023), the test uses the ionization floor, so a high published value
  alone cannot place those entries above break-even.
* **CLEARLY_BELOW_BREAKEVEN:** for at least one stated case c, declared cost / (reference chain × η_t,lo) ≤ Y_min[c] at
  the least favourable Hall corner. Such an entry pays under that case everywhere in the box, at every η_t in range.
* **STRADDLES:** neither of the above. `straddles_on` names every dimension on which pay / no-pay depends somewhere in
  the joint box.
* **NOT_PLACEABLE:** no numeric ion cost on an ion-current basis for an in-scope gas. The missing quantity is named.
* No placement is a hard-gate decision. A CLEARLY_ABOVE entry would only be a milestone-A candidate for the owner's
  hard-gate review, conditional on A1–A8 and the declared basis.

### 3.3 Result

Tables G6 and G7 give the placement of every entry. G6 has the reported value, its power reference, the declared
cost, the bus cost at chain 1 and at the reference chain, and the placement per case. G7 has the minimum η_t at each
slice. In summary:

* **Placed (numeric, in-scope gas).**
  * Xe mode: ECR-D018 (μ20), ECR-D019 (improved μ10), ECR-D023 (Kyushu 10 cm, incident power) and ECR-D021 (ONERA
    gridless). These describe the Xe mode only.
  * Air arm, N₂ component only: ECR-D020 (10 cm N₂ gridded), ECR-E081 (2 cm N₂, experiment) and ECR-E083 (2 cm N₂,
    the source's own model). All three are abstract-only.
  * Every placed entry **STRADDLES**. None is CLEARLY_ABOVE and none is CLEARLY_BELOW (G10 and
    `placement_counts`).
* **Consistency flag on ECR-E081.** Its 596.2 W/A 'ion energy loss' at the recorded 8 W implies a beam current above
  the 12.5 mA maximum that the same abstract reports (ECR-E084). The arithmetic is in
  `evidence_placements[ECR-E081].consistency_check`. So the source's definition of 'ion energy loss', or the input
  power at each point, is not established from the abstract. It is listed as a missing quantity. For the same reason
  no cost is derived for ECR-E084.
* **NOT_PLACEABLE.**
  * ECR-E072: μ10 saturation, no operating power.
  * ECR-E084: see above.
  * ECR-E097: JAXA ABIE on N₂ + atomic O, no microwave power; secondary citation.
  * ECR-E075 and ECR-D022: argon, outside the RFP propellants.
  * The gap row GAP-ECR-O-O2-AIR: **no ECR ion-cost evidence on O₂, atomic O or an N₂/O/O₂ mixture exists**
    (ECR_SOURCE_EVIDENCE.md finding 2).
* **X-side context, not placed.** Four utilization values: ECR-E082 (2 cm N₂), ECR-D030 (10 cm N₂ beam over
  flow-equivalent current, a proxy), ECR-E073 (μ20) and ECR-E092 (ONERA). They would enter X as X = η_t·u_src/η_u0
  when the whole common feed flow passes the source. But they are at the source's own flow and power, so they are
  not placed.
* **Triage.** The JSON accounts for all 165 matrix entries exactly once, in these groups: placed or not placeable;
  bus-chain evidence; fixed-overhead evidence (ECR-E066 steering coils, ECR-E067 coil current without power: the
  main-field electromagnet power is TBD); covered by a derived entry; electron-current (cathode) figures, which are not
  ion costs; other.

## 4. (3) Region of (η_t, C_src,bus) where `ecr_hall` could pay, and the evidence in it

`ecr_hall` can pay in bus power only where C_src,bus ≤ η_t · Y. G8 gives the upper edge of that region for each
case, both for "could pay somewhere in the PROPOSED box" (most favourable corner) and "pays everywhere in the box"
(least favourable corner), at ω_f = 0. A fixed overhead lowers the edge (`Y_sup_over_Pi_H`).

* **Lower edge of η_t.** No source can pay anywhere in the box below η_t = ionization floor / Y_max, whatever its
  chain (G8, second table).
* **Does any published evidence lie in the region?** On the declared basis, yes, but only inside η_t windows (G8,
  third table):
  * With a lossless chain, every numeric entry lies in the could-pay region of every case for η_t above its window
    edge. That includes every N₂ entry.
  * With the reference chain (0.3636), the windows narrow, and several entries leave the add_only region entirely.
  * Only ECR-D018 and ECR-D019 (Xe) would pay **everywhere** in the box, and only with a lossless chain and η_t = 1
    (`region.answer`).
  * No N₂ entry would pay everywhere even then.
  * For O / O₂ / mixtures there is no evidence to place.
* **Structural result.** With the stated reference chain, CLEARLY_BELOW over the full PROPOSED η_t range cannot be
  reached by *any* source, even one at the ionization floor, in any case (`region.structural`). A pay placement over
  the whole box therefore needs a **measured η_t**, not a better source cost alone.

## 5. (4) Measurements that make each placement definite (input to the minimum decisive experiment)

G9 gives the thresholds per entry. In order of how much each one resolves:

1. **End-to-end C_del,bus**: P_bus[ecr_source] divided by the ion current delivered into the Hall channel, on N₂ and
   on an N₂/O₂/O mixture at the common feed state. It subsumes φ, k, η_chain and η_t.
   * Above Y_max of any case (the box maximum), the entry becomes CLEARLY_ABOVE.
   * At or below Y_min[c], it becomes CLEARLY_BELOW for case c.
   * In between, only the Hall reference can decide, which is milestone B.
2. **η_t of the ECR exit state** (lane 18 interstage, same charge-current basis). Below the G9 threshold, the entry
   moves to CLEARLY_ABOVE with any chain. With the reference chain, no η_t ≤ 1 makes any entry CLEARLY_BELOW over
   the whole box ("unreachable" in G9).
3. **η_chain of the candidate flight microwave chain**: DC-DC, driver, amplifier or tube, isolator and feed, at the
   chosen frequency and power (ECR_SOURCE_EVIDENCE.md §6 item 5). It has the same CLEARLY_ABOVE threshold as η_t.
   Measured together with η_t in one bus-to-Hall-channel test, the product decides CLEARLY_BELOW only where G9 shows a
   reachable value. Elsewhere, even a lossless chain with η_t = 1 does not pay at the least favourable Hall corner.
4. **Power plane φ**:
   * forward, reflected and absorbed power at the source flange for ECR-D018, D019, D020, E081 and E083;
   * the reflected power for ECR-D023;
   * the actual coupler-to-thruster loss for ECR-D021 (only "≥ 2 dB" is reported).

   For D021 and D023 this turns the upper bound into a value and enables the tighter CLEARLY_ABOVE threshold shown in
   brackets in G9.
5. **Ion basis k**: the source-exit ion current of a gridless pre-ionizer at the same coupled power and the common
   feed flow.
6. **ECR-E081 / ECR-E084**: the source's definition of 'ion energy loss' and the input power at each point. This
   needs the full text, which was not accessed.
7. **O₂ / atomic O / mixture ion cost**: species-resolved, bus-referenced. Without it the air arm stays NOT_PLACEABLE
   for its O content.
8. **Hall reference and response case**: an admitted closure plus measured α, χ and η_v,S. This is not a single
   measurement. It collapses the PROPOSED box and the three cases, and it requires the credible set, which is
   currently empty.

## 6. (5) Milestone-A statement

**What can be concluded now** (conditional; generated as G10 and in `milestone_A_statement`):

* On the declared basis, no published ECR ion cost rules out a bus-power break-even of `ecr_hall` everywhere in the
  PROPOSED Hall box. The ECR evidence therefore yields no hard-gate candidate on the power criterion.
* No published ECR evidence shows that `ecr_hall` pays in bus power over the whole box and η_t range.
* All seven numeric entries straddle. The dimensions they straddle on are:
  * η_t, which lane 18 cannot compute yet;
  * η_chain, which has no sourced lower bound;
  * the Hall reference, which needs an admitted closure;
  * the response case;
  * the declared basis, φ and k.
* The air arm has N₂-only, abstract-only evidence. It is NOT_PLACEABLE for its O / O₂ content.

**Condition set for milestone A on the bus-power criterion** (necessary, not sufficient). `ecr_hall` can be named
baseline under milestone A only if all of the following are demonstrated:

* (A) C_del,bus ≤ Π_H (g_case(X) − ω_f/X) on an air-representative N₂/O₂/O feed at the common feed state.
* (B) η_t ≥ Z = C_src,bus / Y, on the same charge-current basis.
* (C) X_lo(Y, ω_f) ≤ X ≤ min(X_hi, (1 − η_u0)/η_u0).
* (D) Mass and life break-even (breakeven_v1 §§7–8).

(A)–(C) are evaluated at the admitted Hall reference and the measured response case. This overlay does not name a
baseline.

**Explicit conditions of every statement above:**

* breakeven_v1 A1–A8 accepted by the owner.
* The declared basis: φ as declared, k = 1.
* A Hall reference inside the PROPOSED box.
* η_t in 0.1–1.
* ω_f = 0.
* The reference chain 0.3636, used only for the CLEARLY_BELOW test.

**Not concluded:** no ranking, no hard-gate decision, no architecture named, no comparison with the other pre-ionizer
arm.

## 7. Limitations

* Single-species, singly charged, equal delivered and Hall-born mix (breakeven_v1 A8). A heavier delivered ion into a
  lighter Hall beam raises the payable cost per ampere, and a lighter one lowers it (breakeven_v1 §6.4). N₂ sources that
  deliver N⁺/N₂⁺ mixes are not resolved.
* Y uses the supremum over the delivered share (X → 0) at ω_f = 0 for placement. A real source spends a finite power
  and so delivers a finite X, where the payable cost is lower (G2, and `payable_X_at_mid_reference_chain_1_eta_t_1` per
  entry).
* The η_ppu,d evidence is a 28 V-class breadboard (not flight, not Vyovrinda hardware), and it is extrapolated at
  150 V.
* The reference chain is a 4.2 GHz TWT amplifier specification. The ABEP chain may be higher or lower, at another
  frequency and power.
* The Xe entries are gridded ion thrusters, except for one gridless magnetic-nozzle thruster. None is a pre-ionizer
  feeding a Hall channel.
* The relevance of the evidence to ABEP chamber conditions is TBD until the upstream ICD exists (lane 08,
  regime_match).

## 8. Inputs (read-only, pinned by sha256; resolved from this checkout or from the pinned lane commit)

| key | path | lane / commit |
|---|---|---|
| ecr_evidence_matrix | `docs/evidence/ecr_source/ecr_evidence_matrix.json` | lane_08_ecr_evidence / a85fd59261 |
| breakeven_module | `abep_sim/breakeven.py` | lane_28_break_even / 2ad4c463d7 |
| breakeven_surfaces | `docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json` | lane_28_break_even / 2ad4c463d7 |
| interstage_module | `abep_sim/interstage.py` | lane_18_interstage / 870514285c |
| electrical_closure_data | `docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json` | lane_20_ppu_magnet / f7c226848d |

The pinned modules are executed from their verified bytes under private names. Nothing is copied into this lane's
paths and nothing is imported at module import time. A missing or changed input raises `OverlayInputError`: there is
no silent fallback. Cross-checks against the breakeven_v1 functions are in G11: the stored supremum surfaces,
`supremum_breakeven_delivered_cost`, `required_utilization_gain`, `place_evidence`, `achievable_delivered_share`,
ṁ-invariance and `overhead_from_boundary_ledgers`.

## Generated tables

<!-- BEGIN GENERATED TABLES (build_overlay_ecr.py; do not edit by hand) -->

### G1. Hall reference slices and payable bus cost per delivered ampere Y (omega_f = 0, X -> 0)

| slice | V_d [V] | eta_b | eta_ppu,d | eta_v | Pi_H [W/A] | Y add_only | Y cost_offset | Y optimistic |
|---|---|---|---|---|---|---|---|---|
| most_favourable_corner | 450 | 0.5 | 0.7705 | 0.7 | 1168 | 1168 | 1752 | 2208 |
| mid_reference | 300 | 0.7 | 0.9 | 0.9 | 476.2 | 476.2 | 619 | 670.6 |
| least_favourable_corner | 150 | 0.9 | 0.915 | 1.0 | 182.1 | 182.1 | 200.4 | 200.4 |

Most / least favourable corners are the box maximum / minimum of Y for every case (checked in the build).

### G2. Y/Pi_H against the relative utilization gain X and the fixed overhead omega_f (cost_offset and optimistic at eta_b = 0.7; optimistic at eta_v = 0.9)

**add_only**

| omega_f \ X | 0.01 | 0.02 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 1 | 1.5 | 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.99 | 0.98 | 0.952 | 0.909 | 0.833 | 0.769 | 0.667 | 0.588 | 0.5 | 0.4 | 0.333 |
| 0.01 | -0.0099 | 0.48 | 0.752 | 0.809 | 0.783 | 0.736 | 0.647 | 0.574 | 0.49 | 0.393 | 0.328 |
| 0.02 | -1.01 | -0.0196 | 0.552 | 0.709 | 0.733 | 0.703 | 0.627 | 0.56 | 0.48 | 0.387 | 0.323 |
| 0.05 | -4.01 | -1.52 | -0.0476 | 0.409 | 0.583 | 0.603 | 0.567 | 0.517 | 0.45 | 0.367 | 0.308 |
| 0.1 | -9.01 | -4.02 | -1.05 | -0.0909 | 0.333 | 0.436 | 0.467 | 0.445 | 0.4 | 0.333 | 0.283 |
| 0.2 | -19 | -9.02 | -3.05 | -1.09 | -0.167 | 0.103 | 0.267 | 0.303 | 0.3 | 0.267 | 0.233 |

**cost_offset|eta_b=0.7**

| omega_f \ X | 0.01 | 0.02 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 1 | 1.5 | 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.28 | 1.27 | 1.22 | 1.16 | 1.04 | 0.947 | 0.8 | 0.692 | 0.575 | 0.448 | 0.367 |
| 0.01 | 0.284 | 0.769 | 1.02 | 1.06 | 0.992 | 0.913 | 0.78 | 0.678 | 0.565 | 0.441 | 0.362 |
| 0.02 | -0.716 | 0.269 | 0.824 | 0.957 | 0.942 | 0.88 | 0.76 | 0.663 | 0.555 | 0.435 | 0.357 |
| 0.05 | -3.72 | -1.23 | 0.224 | 0.657 | 0.792 | 0.78 | 0.7 | 0.621 | 0.525 | 0.415 | 0.342 |
| 0.1 | -8.72 | -3.73 | -0.776 | 0.157 | 0.542 | 0.613 | 0.6 | 0.549 | 0.475 | 0.381 | 0.317 |
| 0.2 | -18.7 | -8.73 | -2.78 | -0.843 | 0.0417 | 0.28 | 0.4 | 0.406 | 0.375 | 0.315 | 0.267 |

**optimistic_bound|eta_b=0.7|eta_v=0.9**

| omega_f \ X | 0.01 | 0.02 | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 1 | 1.5 | 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.39 | 1.37 | 1.32 | 1.24 | 1.11 | 1.01 | 0.842 | 0.724 | 0.597 | 0.462 | 0.376 |
| 0.01 | 0.39 | 0.872 | 1.12 | 1.14 | 1.06 | 0.972 | 0.822 | 0.71 | 0.587 | 0.455 | 0.371 |
| 0.02 | -0.61 | 0.372 | 0.921 | 1.04 | 1.01 | 0.939 | 0.802 | 0.695 | 0.577 | 0.448 | 0.366 |
| 0.05 | -3.61 | -1.13 | 0.321 | 0.743 | 0.862 | 0.839 | 0.742 | 0.652 | 0.547 | 0.428 | 0.351 |
| 0.1 | -8.61 | -3.63 | -0.679 | 0.243 | 0.612 | 0.672 | 0.642 | 0.581 | 0.497 | 0.395 | 0.326 |
| 0.2 | -18.6 | -8.63 | -2.68 | -0.757 | 0.112 | 0.339 | 0.442 | 0.438 | 0.397 | 0.328 | 0.276 |

### G3. Minimum and maximum relative gain X that pays at a delivered cost Y = y * Pi_H

Entries are X_lo-X_hi ('0-' = any positive share up to X_hi; '-' = no X pays). Uncapped: compare with the caps below.

**add_only**

| omega_f \ y | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 0.9 | 1 | 1.2 | 1.5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0-9 | 0-4 | 0-2.33 | 0-1 | 0-0.429 | 0-0.111 | - | - | - |
| 0.01 | 0.0113-8.89 | 0.0127-3.94 | 0.0146-2.29 | 0.0209-0.959 | 0.038-0.376 | - | - | - | - |
| 0.02 | 0.0228-8.78 | 0.0258-3.87 | 0.0298-2.24 | 0.0437-0.916 | 0.0931-0.307 | - | - | - | - |
| 0.05 | 0.0592-8.44 | 0.0679-3.68 | 0.0799-2.09 | 0.13-0.77 | - | - | - | - | - |
| 0.1 | 0.127-7.87 | 0.149-3.35 | 0.184-1.82 | - | - | - | - | - | - |
| 0.2 | 0.298-6.7 | 0.382-2.62 | 0.667-1 | - | - | - | - | - | - |

**optimistic_bound|eta_b=0.7|eta_v=0.9**

| omega_f \ y | 0.1 | 0.2 | 0.3 | 0.5 | 0.7 | 0.9 | 1 | 1.2 | 1.5 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0-9.36 | 0-4.35 | 0-2.68 | 0-1.33 | 0-0.748 | 0-0.421 | 0-0.305 | 0-0.131 | - |
| 0.01 | 0.00773-9.25 | 0.00838-4.29 | 0.00916-2.64 | 0.0113-1.3 | 0.0147-0.72 | 0.0213-0.389 | 0.0279-0.268 | - | - |
| 0.02 | 0.0156-9.15 | 0.017-4.24 | 0.0186-2.59 | 0.0231-1.27 | 0.0306-0.69 | 0.047-0.353 | 0.0688-0.217 | - | - |
| 0.05 | 0.0404-8.82 | 0.0442-4.06 | 0.0489-2.47 | 0.0624-1.17 | 0.0895-0.589 | - | - | - | - |
| 0.1 | 0.0859-8.28 | 0.0952-3.76 | 0.107-2.24 | 0.148-0.988 | - | - | - | - | - |
| 0.2 | 0.197-7.18 | 0.227-3.14 | 0.273-1.75 | - | - | - | - | - | - |

### G4. Required relative utilization gain X*(omega) at total overhead fraction omega

| case \ omega | 0.01 | 0.02 | 0.05 | 0.1 | 0.15 | 0.2 | 0.3 | 0.4 | 0.5 |
|---|---|---|---|---|---|---|---|---|---|
| add_only | 0.0101 | 0.0204 | 0.0526 | 0.111 | 0.176 | 0.25 | 0.429 | 0.667 | 1 |
| cost_offset|eta_b=0.5 | 0.00673 | 0.0136 | 0.0349 | 0.0732 | 0.116 | 0.163 | 0.275 | 0.42 | 0.618 |
| cost_offset|eta_b=0.7 | 0.00777 | 0.0157 | 0.0404 | 0.085 | 0.135 | 0.19 | 0.324 | 0.5 | 0.744 |
| cost_offset|eta_b=0.9 | 0.00918 | 0.0185 | 0.0478 | 0.101 | 0.16 | 0.227 | 0.389 | 0.604 | 0.905 |
| optimistic_bound|eta_b=0.7|eta_v=0.9 | 0.00717 | 0.0145 | 0.0373 | 0.0784 | 0.124 | 0.175 | 0.298 | 0.459 | 0.682 |

Caps X <= (1 - eta_u0)/eta_u0: eta_u0=0.3 -> 2.33, eta_u0=0.6 -> 0.667, eta_u0=0.9 -> 0.111.

### G5. Minimum interstage transport efficiency Z = C_src,bus / Y (omega_f = 0)

| slice, case \ C_src,bus [W/A] | 25 | 50 | 100 | 150 | 200 | 300 | 400 | 500 | 600 | 800 | 1000 | 1500 | 2000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| most_favourable_corner, add_only | 0.0214 | 0.0428 | 0.0856 | 0.128 | 0.171 | 0.257 | 0.342 | 0.428 | 0.514 | 0.685 | 0.856 | **>1** | **>1** |
| most_favourable_corner, cost_offset | 0.0143 | 0.0285 | 0.0571 | 0.0856 | 0.114 | 0.171 | 0.228 | 0.285 | 0.342 | 0.457 | 0.571 | 0.856 | **>1** |
| most_favourable_corner, optimistic_bound | 0.0113 | 0.0226 | 0.0453 | 0.0679 | 0.0906 | 0.136 | 0.181 | 0.226 | 0.272 | 0.362 | 0.453 | 0.679 | 0.906 |
| mid_reference, add_only | 0.0525 | 0.105 | 0.21 | 0.315 | 0.42 | 0.63 | 0.84 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| mid_reference, cost_offset | 0.0404 | 0.0808 | 0.162 | 0.242 | 0.323 | 0.485 | 0.646 | 0.808 | 0.969 | **>1** | **>1** | **>1** | **>1** |
| mid_reference, optimistic_bound | 0.0373 | 0.0746 | 0.149 | 0.224 | 0.298 | 0.447 | 0.597 | 0.746 | 0.895 | **>1** | **>1** | **>1** | **>1** |
| least_favourable_corner, add_only | 0.137 | 0.275 | 0.549 | 0.824 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| least_favourable_corner, cost_offset | 0.125 | 0.25 | 0.499 | 0.749 | 0.998 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| least_favourable_corner, optimistic_bound | 0.125 | 0.25 | 0.499 | 0.749 | 0.998 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |

Mid reference with a fixed overhead (eta_u0 = 0.6), optimistic_bound:

| omega_f \ C_src,bus [W/A] | 25 | 50 | 100 | 150 | 200 | 300 | 400 | 500 | 600 | 800 | 1000 | 1500 | 2000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.0373 | 0.0746 | 0.149 | 0.224 | 0.298 | 0.447 | 0.597 | 0.746 | 0.895 | **>1** | **>1** | **>1** | **>1** |
| 0.01 | 0.0457 | 0.0914 | 0.183 | 0.274 | 0.366 | 0.549 | 0.732 | 0.914 | **>1** | **>1** | **>1** | **>1** | **>1** |
| 0.02 | 0.0501 | 0.1 | 0.2 | 0.301 | 0.401 | 0.601 | 0.801 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| 0.05 | 0.0609 | 0.122 | 0.244 | 0.365 | 0.487 | 0.731 | 0.974 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| 0.1 | 0.0779 | 0.156 | 0.312 | 0.467 | 0.623 | 0.935 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |
| 0.2 | 0.118 | 0.236 | 0.471 | 0.707 | 0.942 | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** | **>1** |

### G6. Evidence placements (declared basis)

| entry | mode | reported [W/A] (class, access) | power reference | declared cost [W/A] | bus cost: chain 1 / reference chain [W/A] | placement | per case (add / cost_offset / optimistic) |
|---|---|---|---|---|---|---|---|
| ECR-D018 | xe | 200 (inferred, open) | not stated (forward or absorbed) | 200 (assumed) | 200 / 550.1 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-D019 | xe | 174.4-178 (inferred, open) | not stated (forward or absorbed) | 174.4-178 (assumed) | 174.4-178 / 479.6-489.5 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-D023 | xe | 376.5 (inferred, open) | forward (incident; reflected power not subtracted) | 376.5 (definitional_upper) | 376.5 / 1035 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-D020 | air_N2 | 213.2 (inferred, abstract_only) | not stated (forward or absorbed) | 213.2 (assumed) | 213.2 / 586.4 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-E081 | air_N2 | 596.2 (inferred, abstract_only) | not stated ('input power') | 596.2 (assumed) | 596.2 / 1640 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-E083 | air_N2 | 443.9 (model-derived, abstract_only) | not stated ('input power', model) | 443.9 (assumed) | 443.9 / 1221 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-D021 | xe | 779.8 (inferred, open) | forward side: 'transmitted' (= forward minus reflected) at a directional coupler upstream of >= 2 dB of chain loss | 492.1 (sourced_upper) | 492.1 / 1353 | **STRADDLES** | STRADDLES / STRADDLES / STRADDLES |
| ECR-E072 | xe | 0.15 A | - | - | - | **NOT_PLACEABLE** | missing: microwave power at a stated operating point (the source gives only 'saturates at 0.150 A for microwave powers above 30 W', ECR-E072) |
| ECR-E084 | air_N2 | 0.0125 A | - | - | - | **NOT_PLACEABLE** | missing: the source's definition of 'ion energy loss' and the input power at the maximum-current point (full text not accessed) |
| ECR-E097 | air_N2_O | 0.016 A | - | - | - | **NOT_PLACEABLE** | missing: microwave power (not given in the accessed secondary text) |
| ECR-E075 | out_of_scope_gas | 440 W/A | - | - | - | **NOT_PLACEABLE** | missing: a measurement on an in-scope propellant (N2/O/O2/air mixture or Xe); no Ar-to-air transfer rule is sourced |
| ECR-D022 | out_of_scope_gas | 704.6 W/A | - | - | - | **NOT_PLACEABLE** | missing: a measurement on an in-scope propellant (N2/O/O2/air mixture or Xe) |
| GAP-ECR-O-O2-AIR | air_O_O2 | - | - | - | - | **NOT_PLACEABLE** | missing: any ECR ion-source ion production cost on O2, atomic O or an N2/O/O2 mixture: none exists in the ECR evidence matrix (ECR_SOURCE_EVIDENCE.md finding 2) |

### G7. Minimum eta_t per entry (declared cost; chain 1 / reference chain; '>1' = cannot pay there)

| entry | most add_only | most cost_offset | most optimistic_bound | mid add_only | mid cost_offset | mid optimistic_bound | least add_only | least cost_offset | least optimistic_bound |
|---|---|---|---|---|---|---|---|---|---|
| ECR-D018 | 0.171 / 0.471 | 0.114 / 0.314 | 0.0906 / 0.249 | 0.42 / **>1** | 0.323 / 0.889 | 0.298 / 0.82 | **>1** / **>1** | 0.998 / **>1** | 0.998 / **>1** |
| ECR-D019 | 0.149 / 0.411 | 0.0995 / 0.274 | 0.079 / 0.217 | 0.366 / **>1** | 0.282 / 0.775 | 0.26 / 0.715 | 0.957 / **>1** | 0.87 / **>1** | 0.87 / **>1** |
| ECR-D023 | 0.322 / 0.886 | 0.215 / 0.591 | 0.171 / 0.469 | 0.791 / **>1** | 0.608 / **>1** | 0.561 / **>1** | **>1** / **>1** | **>1** / **>1** | **>1** / **>1** |
| ECR-D020 | 0.183 / 0.502 | 0.122 / 0.335 | 0.0965 / 0.266 | 0.448 / **>1** | 0.344 / 0.947 | 0.318 / 0.874 | **>1** / **>1** | **>1** / **>1** | **>1** / **>1** |
| ECR-E081 | 0.51 / **>1** | 0.34 / 0.936 | 0.27 / 0.743 | **>1** / **>1** | 0.963 / **>1** | 0.889 / **>1** | **>1** / **>1** | **>1** / **>1** | **>1** / **>1** |
| ECR-E083 | 0.38 / **>1** | 0.253 / 0.697 | 0.201 / 0.553 | 0.932 / **>1** | 0.717 / **>1** | 0.662 / **>1** | **>1** / **>1** | **>1** / **>1** | **>1** / **>1** |
| ECR-D021 | 0.421 / **>1** | 0.281 / 0.772 | 0.223 / 0.613 | **>1** / **>1** | 0.795 / **>1** | 0.734 / **>1** | **>1** / **>1** | **>1** / **>1** | **>1** / **>1** |

### G8. Region of (eta_t, C_src,bus) where ecr_hall could pay (omega_f = 0)

Upper edge of C_src,bus [W/A] that could pay somewhere in the box (most favourable corner) / everywhere in the box (least favourable corner).

| eta_t | add_only | cost_offset | optimistic_bound |
|---|---|---|---|
| 0.1 | 116.8 / 18.2 | 175.2 / 20 | 220.8 / 20 |
| 0.2 | 233.6 / 36.4 | 350.4 / 40.1 | 441.6 / 40.1 |
| 0.3 | 350.4 / 54.6 | 525.6 / 60.1 | 662.5 / 60.1 |
| 0.4 | 467.2 / 72.9 | 700.8 / 80.1 | 883.3 / 80.1 |
| 0.5 | 584 / 91.1 | 876.1 / 100.2 | 1104 / 100.2 |
| 0.6 | 700.8 / 109.3 | 1051 / 120.2 | 1325 / 120.2 |
| 0.7 | 817.7 / 127.5 | 1226 / 140.3 | 1546 / 140.3 |
| 0.8 | 934.5 / 145.7 | 1402 / 160.3 | 1767 / 160.3 |
| 0.9 | 1051 / 163.9 | 1577 / 180.3 | 1987 / 180.3 |
| 1 | 1168 / 182.1 | 1752 / 200.4 | 2208 / 200.4 |

Lowest eta_t at which any source of a given feed could pay anywhere in the box (ionization floor / Y_max):

| feed | add_only | cost_offset | optimistic_bound |
|---|---|---|---|
| N2_feed (14.5341 W/A) | 0.0124 | 0.0083 | 0.00658 |
| Xe_feed (12.1298 W/A) | 0.0104 | 0.00692 | 0.00549 |
| O_feed (13.6181 W/A) | 0.0117 | 0.00777 | 0.00617 |

eta_t window per entry inside the could-pay region (chain 1 / reference chain; '-' = outside at every eta_t <= 1):

| entry | add_only | cost_offset | optimistic_bound | pays everywhere at chain 1, eta_t 1 |
|---|---|---|---|---|
| ECR-D018 | >= 0.171 / >= 0.471 | >= 0.114 / >= 0.314 | >= 0.0906 / >= 0.249 | cost_offset, optimistic_bound |
| ECR-D019 | >= 0.149 / >= 0.411 | >= 0.0995 / >= 0.274 | >= 0.079 / >= 0.217 | add_only, cost_offset, optimistic_bound |
| ECR-D023 | >= 0.322 / >= 0.886 | >= 0.215 / >= 0.591 | >= 0.171 / >= 0.469 | no |
| ECR-D020 | >= 0.183 / >= 0.502 | >= 0.122 / >= 0.335 | >= 0.0965 / >= 0.266 | no |
| ECR-E081 | >= 0.51 / - | >= 0.34 / >= 0.936 | >= 0.27 / >= 0.743 | no |
| ECR-E083 | >= 0.38 / - | >= 0.253 / >= 0.697 | >= 0.201 / >= 0.553 | no |
| ECR-D021 | >= 0.421 / - | >= 0.281 / >= 0.772 | >= 0.223 / >= 0.613 | no |

### G9. Single measurements that make a placement definite

| entry | eta_t or eta_chain below -> CLEARLY_ABOVE (once the phi bound is tight) | eta_t at least -> CLEARLY_BELOW with the reference chain (add / cost_offset / optimistic) | eta_chain * eta_t at least -> CLEARLY_BELOW (add / cost_offset / optimistic) | end-to-end C_del,bus above -> ABOVE [W/A] | C_del,bus at or below -> BELOW (add / cost_offset / optimistic) [W/A] |
|---|---|---|---|---|---|
| ECR-D018 | 0.0906 | unreachable / unreachable / unreachable | unreachable / 0.998 / 0.998 | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-D019 | 0.079 | unreachable / unreachable / unreachable | 0.977 / 0.888 / 0.888 | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-D023 | 0.00549 (0.171) | unreachable / unreachable / unreachable | unreachable / unreachable / unreachable | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-D020 | 0.0965 | unreachable / unreachable / unreachable | unreachable / unreachable / unreachable | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-E081 | 0.27 | unreachable / unreachable / unreachable | unreachable / unreachable / unreachable | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-E083 | 0.201 | unreachable / unreachable / unreachable | unreachable / unreachable / unreachable | 2208 | 182.1 / 200.4 / 200.4 |
| ECR-D021 | 0.00549 (0.223) | unreachable / unreachable / unreachable | unreachable / unreachable / unreachable | 2208 | 182.1 / 200.4 / 200.4 |

### G10. Milestone-A statement (generated)

- placements: 0 CLEARLY_ABOVE_BREAKEVEN, 0 CLEARLY_BELOW_BREAKEVEN, 7 STRADDLES, 6 NOT_PLACEABLE (declared basis, PROPOSED rules)
- no published ECR ion cost rules out a bus-power break-even of ecr_hall everywhere in the PROPOSED Hall box: the ECR evidence yields no hard-gate candidate on the power criterion
- no published ECR evidence shows that ecr_hall pays in bus power over the whole PROPOSED box and eta_t range
- the numeric entries straddle on: Hall reference point (PROPOSED box; needs an admitted closure); declared basis (k = 1 assumed; phi assumed); declared basis (k = 1 assumed; phi only upper-bounded); eta_chain (no sourced lower bound); eta_t (lane-18 range); response case (alpha, chi, eta_v_S not measured)
- with the stated reference chain, CLEARLY_BELOW over the full lane-18 eta_t range is out of reach for any source (even at the ionization floor) in every case: a pay placement needs a measured eta_t
- air arm: 3 placeable entries (ECR-D020, ECR-E081, ECR-E083), all N2 and all abstract-only; no ECR ion-cost evidence on O2, atomic O or a mixture exists, so the air arm is NOT_PLACEABLE for its O / O2 content
- Xe mode: 4 placeable entries (ECR-D018, ECR-D019, ECR-D023, ECR-D021); they describe the Xe mode only
- a delivered ion is worth at most Y = Pi_H (2r - p) bus W/A at omega_f = 0; over the PROPOSED box this spans 182.149-1168.07 W/A (add_only), 200.364-1752.11 W/A (cost_offset) and 200.364-2208.19 W/A (optimistic_bound)
- on the declared basis with a lossless chain, every N2 entry lies in the could-pay region of every case inside its eta_t window (region.evidence_in_region)
- entries that would pay everywhere in the box only with a lossless chain and eta_t = 1: ECR-D018, ECR-D019

Condition set: On the bus-power criterion (necessary, not sufficient), ecr_hall can be named baseline under milestone A only if all of the following are demonstrated: (A) an end-to-end bus cost per delivered ampere C_del,bus <= Pi_H (g_case(X) - omega_f/X) on an air-representative N2/O2/O feed at the common feed state; (B) an interstage transport efficiency eta_t >= Z = C_src,bus / Y on the same charge-current basis; (C) a relative utilization gain X with X_lo(Y, omega_f) <= X <= min(X_hi, (1 - eta_u0)/eta_u0); (D) mass and life break-even (breakeven_v1 Secs. 7-8). (A)-(C) are evaluated at the admitted Hall reference and the measured response case. This overlay does not name a baseline.

### G11. Self-checks

- `y_sup_vs_breakeven_surfaces`: pass = True, n = 324
- `y_sup_vs_breakeven_module`: pass = True, n = 162
- `x_star_vs_required_utilization_gain`: pass = True, n = 81
- `eta_t_min_vs_place_evidence`: pass = True, n = 63
- `share_interval_endpoints_and_unimodality`: pass = True
- `achievable_delivered_share_cost_identity`: pass = True
- `mdot_invariance_omega_f_0`: pass = True
- `overhead_from_boundary_ledgers_split`: pass = True
- all pass: True

<!-- END GENERATED TABLES -->
