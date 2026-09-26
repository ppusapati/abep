# Break-even surfaces (breakeven_v1): how to read them

These are **surfaces over analysis ranges, not predictions.** No Hall closure, no screening candidate and no absolute
Hall number was used, and nothing here ranks the architectures (**no winner**). This page mainly supports
**milestone A**: it rules regions out early and states the conditions an arm must demonstrate. What milestones B and C
still need is listed in `BREAKEVEN_DERIVATION.md` §0.

Regenerate:

```
python scripts/architecture/build_breakeven_surfaces.py            # JSON + figures (CSV if matplotlib is missing)
python scripts/architecture/build_breakeven_surfaces.py --check    # rebuild in memory, byte-compare with the committed JSON
```

The build refuses to write if any self-check fails. `tests/test_breakeven.py` checks that the committed JSON carries
the sha256 of the current `abep_sim/breakeven.py` and that all self-checks pass.

## Files

| file | content |
|---|---|
| `breakeven_surfaces_v1.json` | Inputs, each with source/status; the universal (dimensionless) and dimensional surfaces; self-checks; milestone statement; mass/life inequality structure (no surfaces, inputs TBD); provenance (module sha256). |
| `fig_required_gain_universal.png` | Δη_u*/η_u0 against ω for add-only and cost-offset (η_b 0.5/0.7/0.9), with the utilization caps. |
| `fig_breakeven_ion_cost.png` | Maximum payable source cost C_src* = η_t · C_del*,0 against η_t, for V_d 150/300/450 V; add-only and optimistic bound. |
| `fig_required_gain_by_species.png` | Δη_u* against overhead O [W] for N₂⁺/O⁺/O₂⁺/Xe⁺. One slice: 300 V, 1 mg/s, η_u0 0.6, η_b 0.7. |
| `fig_source_cost_map_N2.png` | Map of C_src*(O, η_t) for N₂⁺, same slice, three cases. |
| `breakeven_evidence_overlay_prelim_v1.json`, `fig_evidence_overlay_prelim.png` | **PRELIMINARY** overlay of published ion costs, read-only from unmerged evidence lanes (see the last section). |

## Analysis ranges (all PROPOSED: assumed, not design values)

| axis | values | basis |
|---|---|---|
| overhead O (read as "P_source") | 0–500 W | span requested by the owner. The surfaces depend on the **total** bus overhead O, so read the axis at O (§ per architecture below). |
| η_transport | 0.1–1 | span requested by the owner |
| V_d | 150–450 V | brackets the P5-N₂ setpoints, 231.9–278.6 V (Brabston et al., JPP 2025, doi:10.2514/1.B39623, Table 2; measured, level 3). Those setpoints are context only: P5 is a 3–5 kW thruster, outside the RFP class. |
| ṁ | 0.1–5 mg/s | The definitional floor is T_min²/(2 P_max) = 0.048 mg/s (RFP 12 mN, 1.5 kW, η_a ≤ 1). The top of the range corresponds to η_a ≈ 4 % at 25 mN and 1.5 kW. `hall_reference_table` flags every Hall-only reference point whose discharge bus power exceeds the 1.5 kW RFP cap. |
| η_u0 | 0.3, 0.6, 0.9 | NASA-173Mv2 Xe (Hofer & Gallimore AIAA-2004-3602 abstract; reconstructed, level 3) is context only |
| η_b | 0.5, 0.7, 0.9 | as above |
| η_v | 0.9 dimensional; 0.7–1.0 for the optimistic case | add-only and cost-offset do not depend on it (self-check 3) |
| γ, η_ppu,d | 0.9, 0.9 | γ affects no break-even quantity. η_ppu,d enters only as V_d/η_ppu,d. |
| species | N₂⁺, O⁺, O₂⁺, Xe⁺ (single species, singly charged) | masses from CIAAW Abridged Standard Atomic Weights 2024 (https://www.ciaaw.org/abridged-atomic-weights.htm). These are analysis mixes, not predicted beam compositions. |

## Three cases (response parameters, `BREAKEVEN_DERIVATION.md` §3)

* **add_only** (α = 1, χ = 0): delivered ions add to the beam and each one costs the full Hall price V_d/η_b.
* **cost_offset** (α = 1, χ = 1): delivered ions also avoid the Hall's per-ion electron-current overhead.
* **optimistic_bound** (α = 1, χ = 1, η_v,S = 1): the most favourable corner of the declared box, at equal mix. This
  is the **elimination reference**.

## How to read

1. **Compute the overhead of the arm at the common boundary.** The overhead is:

   ```
   O = P_bus[rf_source]                    (+ Δ common components)    for rf_hall
   O = P_bus[ecr_source] + P_bus[ecr_magnet] (+ Δ common components)  for ecr_hall
   ```

   Here Δ common is arm minus hall_only for every common component except `hall_discharge`. Two
   `bus_power_boundary_v1` ledgers can be passed to `breakeven.overhead_from_boundary_ledgers`.
2. **Universal surface (any Hall point).** Compute ω = O / P_d,bus0, where P_d,bus0 = V_d I_b0/(η_b η_ppu,d) is the
   Hall-only discharge bus power. `universal.delta_eta_u_star_over_eta_u0[case|η_u0|η_b|η_v]` gives the required
   relative gain on the ω grid. For add-only it is exactly ω/(1 − ω), for every η_b, η_v, γ and species. A `null`, or
   a curve ending at a cap line in the figure, means no break-even: ω ≥ 1, or the required gain would push η_u above 1.
   `universal.V_d_ratio_at_breakeven` gives the V_d the arm must run at, which is assumption A2.
3. **Dimensional surface.** `dimensional.delta_eta_u_star[species][V_d][ṁ][η_u0][η_b][case][P_source]` gives Δη_u*
   directly. The `index_order` key lists the axis order. This is the **same** number for both comparison conventions:
   * equal thrust: a bus-power saving ≥ 0;
   * equal bus power: a thrust gain ≥ 0.

   The two conventions share one break-even locus. Away from it they differ, so evaluate
   `breakeven.evaluate_arm` for the size of the saving or of the gain.
4. **Ion-cost surface.** At a Hall point, a source can pay only if its bus cost per ampere of ions *produced*,
   C_src, is at or below C_src* = η_t · C_del*, where:
   * with no fixed overhead, C_del*,0 = Π_H · `marginal_C_del_star_over_Pi_H` and Π_H = V_d/(η_b η_ppu,d);
   * with a fixed (non-ion-scaling) overhead ω_f P_d,bus0, such as an ECR electromagnet, the supremum over the spend
     is `sup_C_del_star_over_Pi_H_with_fixed_overhead`. A value ≤ 0 means no source cost pays.

   Marginal values at equal mix (from the JSON):

   | case | C_del*,0 |
   |---|---|
   | add-only | 1.0 Π_H |
   | cost-offset | (2 − η_b) Π_H |
   | optimistic, η_b = 0.7 | 1.30 Π_H (η_v = 1.0) to 1.69 Π_H (η_v = 0.7) |

   **Worked reading** (analysis values only): N₂⁺, V_d = 300 V, η_b = 0.7, η_ppu,d = 0.9. Then Π_H = 476.2 W/A and the
   optimistic C_del*,0 = 1.408 Π_H = 670.6 W/A at η_v = 0.9.
   * At η_t = 0.5 a source must produce ions for **≤ 335 bus W/A**, or it cannot pay in power at that point, whatever
     its size.
   * An electromagnet that takes 5 % of P_d,bus0 lowers the supremum from 1.408 to 0.862 Π_H in the optimistic case
     at η_u0 = 0.6.
5. **Place a published or measured ion cost.** Use `breakeven.place_evidence`:
   1. Convert the cost to bus W/A with `bus_referred_source_cost`. The power reference is `absorbed`, `forward` or
      `bus`, a cost in eV/ion is divided by the mean charge, and every chain efficiency is explicit.
   2. Pair it with η_t on the **same ion basis** (produced / source exit / extracted → accelerated in the Hall beam).
   3. Tag both values `Evidenced`, with evidence class and source.

   The result is one of three statuses, plus the payable delivered-share interval and η_t,min:
   * `CANNOT_BREAK_EVEN_IN_MODEL_FAMILY` (C_del above the optimistic supremum). This is a milestone-A elimination
     candidate, conditional on assumptions A1–A8.
   * `BREAKS_EVEN_ONLY_IN_LIMIT`.
   * `BREAK_EVEN_POSSIBLE`.
6. **Supply side.** A given generator power achieves δ_s = η_t P_gen/(C_src ṁ ρ) (`achievable_delivered_share`). It
   breaks even when α δ_s ≥ Δη_u*.

## Per architecture

* **rf_hall:** C_src is the `rf_source` cost. Everything else in O is fixed overhead.
* **ecr_hall:** C_src is the `ecr_source` cost. `ecr_magnet` (0 W explicitly for permanent magnets) and the common
  deltas are fixed overhead. They lower the payable cost through the `..._with_fixed_overhead` surface.

The algebra is identical for both. The architectures differ only through their ledger lines and their evidence.

## What the surfaces say (analysis statements, conditional on A1–A8)

* **Requirement sets.** A pre-ionizer must deliver ions at a bus cost comparable to the Hall's own per-beam-ampere
  price, V_d/(η_b η_ppu,d), divided by η_t.
  * In the add-only case the payable delivered cost equals that price exactly. Only the offsets χ, α and η_v,S raise
    it, and the equal-mix optimistic corner raises it by at most a factor (2/√η_v − η_b).
  * Low η_t scales the payable source cost down linearly.
  * Fixed overheads lower it further.
* **Required gain.** It grows as ω/(1 − ω) in the add-only case. Small Hall-only discharge powers (low ṁ, low V_d)
  make a fixed source power a large ω. Example: 0.1 mg/s N₂ at 300 V, with η_u0 = 0.6 and η_b = 0.7, gives
  P_d,bus0 ≈ 98 W, so 50 W of overhead is ω ≈ 0.51.
  * On the grid, 50 W has no break-even in any case for η_b ≥ 0.7 at every η_u0, nor anywhere at η_u0 = 0.9.
  * Where it does break even, the required Δη_u* is 0.20–0.46 in absolute terms.
* **Not an elimination of rf_hall or ecr_hall.** No such statement is made here. That needs sourced C_src and η_t on
  the same ion basis for the air species, and the owner's acceptance of A1–A8.

## PRELIMINARY evidence overlay (`breakeven_evidence_overlay_prelim_v1.json`)

**Provenance of the overlay.**
* Generated with `--evidence-matrix`. It reads the RF and ECR evidence matrices **read-only** from the unmerged
  worktrees of their lanes (repo paths `docs/evidence/rf_source/rf_evidence_matrix.json`, sha256 `5f6d4e0e…`, and
  `docs/evidence/ecr_source/ecr_evidence_matrix.json`, sha256 `4a65dbee…`, both recorded in the file).
* It must be regenerated after those lanes merge.
* Selection is by explicit rule: unit W/A, an ion or beam current basis (not an electron current), a stated gas, and a
  numeric value. The evidence class and level are carried per point, as given by the evidence lanes.

**Points placed** (values as published; evidence class from the matrices):
* **Air species:** RF-NO25-D1 (50:50 N₂/O₂, 207–1600 W/A, inferred, preprint) and ECR-E081/E083/D020 (N₂; all three sources
  are abstract-only, and E083 is model-derived).
* **Noble gases:** ECR-D018/D019/D021/D023 (Xe) and ECR-E075/D022 (Ar). These do not describe the air arm.

**Placement rule.** Points are placed on the source's own power reference and ion basis. Two conversions are still
TBD:
* referring the power to the bus can only **raise** the cost;
* moving from a grid-extracted ion basis to ions leaving a gridless pre-ionizer can **lower** it.

Until both are sourced, `eta_t_needed_as_reported` is neither an upper nor a lower bound. The overlay is
**indicative only**: no elimination and no architecture conclusion is drawn from it.
