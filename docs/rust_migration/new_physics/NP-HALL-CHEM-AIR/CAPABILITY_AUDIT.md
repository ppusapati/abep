# NP-HALL-CHEM-AIR — solver capability audit v1 (A9.33 Q2)

`capability_audit_v1.json` is authoritative; this page restates it. Written 2026-10-08 on `b730764`, before the
preregistration. Read from a clone of HallThruster.jl at the pinned commit `bfb3019f…` (v0.23.1; per-file sha256 in the
JSON). No Julia was run. Nothing was patched.

**Question.** Can the pinned solver run a multi-species air feed (N2 + N + O2 + O) in one run?

**Verdict: CAPABLE_WITH_LIMITATIONS. Not a stop condition.**

## What the solver can do

| id | topic | finding |
|---|---|---|
| C-01 | mixtures | `Config.propellants` is a vector. Each species has its own anode flow, inlet velocity and temperature. Zero-flow species are allowed. |
| C-02 | reactions | `propellant_config` supports elastic, lumped excitation and electron-impact reactions. Each reaction has exactly one heavy reactant; products may belong to any configured gas (O2 → O + O, O2 → O⁺ + O). |
| C-03 | charge states | Per-species charge states. Every charge state needs a one-to-one link from its neutral, so O²⁺ needs an O → O²⁺ or O⁺ → O²⁺ table. |
| C-04 | tables | Same table format and 0–255 eV grid as abep-n2n. |
| C-05 | walls / anode | Ions return to the ground neutral of their own gas (O2⁺ → O2). Neutrals have no wall interaction. |
| C-06 | ingestion | Background split by anode number-flow fraction. Not used: the envelope is vacuum mode. |
| C-11 | bridge | `bridge_lib.jl` helpers (chemistry validity, B profile, wall metrics) work for several species unchanged. |

The production N2/N runs already carry two neutral species with cross-species products in one run.

## What it cannot do (limitations)

| id | limitation | handling in the preregistration |
|---|---|---|
| L-01 | No heavy-particle reactions: no ion-molecule, charge transfer, neutral-neutral or three-body reactions, so no N / O cross chemistry and no NO / NO⁺. | Omitted processes. No sourced rate exists in the repository, so they are UNBOUNDED_OMISSION. If one is promoted, AIR is NOT_REPRESENTABLE_IN_PINNED_SOLVER. |
| L-02 | No neutral-surface recombination in the channel (O + wall → ½ O2). | Omitted process bounded by the physical probability envelope [0, 1]. |
| L-03 | Molecular ions neutralize to the parent molecule only. | Structural limitation, recorded. |
| L-04 | Dissociative recombination and attachment are not faithfully representable: they would count as ionizing and the lost electron's energy has no sink. | Omitted processes, bounded by F_e_loss. |
| L-05 | Negative ions trigger hard-coded, uncited sinks (1e-12 m³/s, `heavy_species_update.jl` lines 732 and 735). | O⁻ is never configured. |
| L-06 | O²⁺ needs a one-to-one link that has no repository source. | O max_charge = 1; O²⁺ channels are omitted (tier 3). |
| L-07 | `run_case` feeds only N2 when a propellant config is used. `bridge_lib.jl` is pinned by the v1 envelope. | Additive AIR run function in a new driver file. `bridge_lib.jl` is unchanged. |

Model-form properties common to every family:
- Elastic collisions set the momentum collision frequency only. There is no elastic recoil energy term.
- Excitation is a lumped energy loss.
- There are no ion-neutral collisions.

## Options if a limitation binds

- **O-A (default):** AIR Hall stays NOT_EVALUATED with NOT_REPRESENTABLE_IN_PINNED_SOLVER.
- **O-B:** a labelled single-species O-only (or O2-only) bounding diagnostic, like N2_PROXY. It has no classification effect without an owner ruling.
- **O-C:** an owner-approved solver upgrade. That is a physics-model change under the `PINNED.toml` upgrade policy, never automatic.
