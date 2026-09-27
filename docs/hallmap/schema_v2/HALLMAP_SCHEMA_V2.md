# Hall-map schema v2: wall-adjacent quantities (DRAFT for owner review)

**Status: DRAFT_FOR_OWNER_REVIEW.** Lane `fo_hallmap_schema_v2_registry`, trigger `T_PIVOT_HALLMAP_SCHEMA_V2_REGISTRY`, owner
disposition `od_hardware_pivot` (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`, `execution_directive_2026_09_27`).
Machine-readable schema: `schemas/hallmap/hall_map_schema_v2.json`. Companion: `HALLMAP_REGISTRY.md` (immutable map registry).
Tests: `tests/test_hallmap_schema_v2_registry.py`.

No map was generated, no simulation was run, and no Julia was executed for this document. The pinned solver source was read
only. `hallthruster_bridge/hall_map_schema_v1.json` is unchanged and stays historically valid. `abep_sim/hall_map.py` is
not modified and still loads v1 maps only.

## 1. What v2 is

v2 = v1 (inherited unchanged, bound by sha256 `f371b43b…`) + wall-adjacent quantities that HallThruster.jl v0.23.1 at the
pinned commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5` **genuinely computes**. A quantity was added only if the solver
computes it, and each added field names the solver variable or function it comes from. Quantities the solver does not
compute are listed as **not supplied** (section 4), together with what would be needed to get them. None was derived
from an unrelated global diagnostic.

**Identity of the source read.** The installed copy `/root/.julia/packages/HallThruster/zHCae` has a recomputed git tree
hash of `7505b3a2a6cfeb6854801de53c6985443aeb8363`. That equals the `git-tree-sha1` that `hallthruster_bridge/Manifest.toml`
records for `repo-rev = bfb3019f…`, version 0.23.1. The sha256 of every solver file read is in the schema
(`solver_basis.files_read_sha256`). This also settles the "identity of the installed copy with the pin: verify" caveat in
`docs/hallmap/HALLMAP_PRODUCTION_SPEC.md` sections 7, 11 and 14 for this copy.

## 2. Milestones

| milestone | contribution | to reach the next one |
|---|---|---|
| A (conditional selection) | not needed: no absolute Hall number is required. This file states which wall quantities a future admitted-member map can and cannot deliver | nothing from this lane blocks A |
| B (physics-backed selection) | not on the B critical path. B needs T / η_u / P_d / I_d from admitted-member maps, which v1 already defines | admitted member (credible set ∅), Vyovrinda geometry/B(z), frozen convergence prereg, O4 dispositions (spec section 2) |
| C (proposal/PDR freeze) | model-side counterparts of `docs/evidence/wall_life/` H7 (near-wall T_e, sheath potential, wall ion flux) and H9 (SEE yield) for the wall heat/erosion chain (`abep_sim/thermal_life.py`) | owner-approved producer change (section 5); `ion_wall_losses` decision (spec open decision 3); a cited sputter-yield model with an incidence-angle treatment from a source other than this solver (NS-1); an admitted member; a second-lens review |

## 3. Added quantities (all `status: not_computed`, since no producer exists yet)

Every value is re-evaluated in **every saved frame** of the averaging window, never on the time-averaged state. The
re-evaluation uses the solver's own functions (`SEE_yield`, `sheath_potential`, `edge_to_center_density_ratio`,
`linear_transition`), applied to the solver's own saved state (`Frame.Tev`, `Frame.ions[*]` n/m/Z) and to the run's
`Config`. This is the same method as the v1 wall fields in `bridge_lib.jl` `wall_ion_metrics`. The solver computes these
values but does **not** save γ_SEE, m_eff or wall_transition in `Frame`.

| field | level | unit | solver variable / function | computed or input |
|---|---|---|---|---|
| `wall_Te_eV` | map field, ion-Bohm-flux-weighted channel mean | eV | `wall_electron_temperature(params, i)` → `cache.Tev[i]` when unshielded; saved as `Frame.Tev` | solver state |
| `wall_see_yield_eff` | map field, flux-weighted | – | `cache.γ_SEE[i] = SEE_yield(material, Tev, 1 − 8.3·√(mₑ/m_eff))` in `freq_electron_wall!` | solver state (re-evaluated) |
| `wall_see_space_charge_limited_fraction` | map field | – | `min(γ_max, …)` branch of `SEE_yield` | solver state (re-evaluated) |
| `wall_sheath_potential_V` | map field, flux-weighted | V | `sheath_potential(Tev, γ, m_eff)` (used in `wall_power_loss!` and in v1 wall energy) | solver state (re-evaluated) |
| `wall_ion_flux_fraction_atomic` | map field | – | per-species Bohm flux `loss_scale·h·n_s·√(Z_s e T_e/m_s)` from `Frame.ions` | solver state (re-evaluated) |
| `wall_ion_flux_fraction_multiply_charged` | map field | – | as above, split by `SpeciesState.Z` | solver state (re-evaluated) |
| `wall_ion_species` | raw record | structured | per ion species: flux, share, impact energy `Z φ_s + T_e/2` | solver state (re-evaluated) |
| `profile_wall_transition` | raw record, per cell | – | `cache.wall_transition = linear_transition(z, L, transition_length, 1, 0)` (`plume.jl`) | input-derived |
| `profile_wall_Te_eV`, `profile_wall_see_yield`, `profile_wall_sheath_potential_V` | raw record, per cell | eV, –, V | as the map fields | solver state |
| `profile_wall_ion_flux_m2s_by_species` | raw record, per cell | m⁻² s⁻¹ | as `wall_ion_species` | solver state (re-evaluated) |
| `profile_ion_wall_removal_m3s_by_species` | raw record, per cell | m⁻³ s⁻¹ | `n_s·νiw`, with `νiw = wall_transition·√(e T_e)·h·loss_scale/Δr·√(Z/m)` (`apply_ion_wall_losses!`) | solver state; only with `ion_wall_losses = true` |

Added meta (inputs copied from the run's `Config`, never retyped): `wall_loss_model` (type, material name, ε*, σ₀,
`loss_scale`), `shielded`, `transition_length_m`, `electron_plume_loss_scale`, and `wall_fields_basis` (a producer
statement like v1 `wall_ion_basis`).

**Availability.** Every wall field requires an unshielded thruster with `WallSheath`. `profile_ion_wall_removal_*`
additionally requires `ion_wall_losses = true`. Otherwise the producer writes the field as absent (never zero) and states
why in `wall_fields_basis`.

**Solver constants, for information only (not new values).** The pinned source defines `BNSiO2` as ε* = 40, σ₀ = 0.54
(`src/physics/wall_losses.jl` lines 114–118, together with Alumina, BoronNitride, SiliconDioxide and SiliconCarbide). It
also defines the space-charge cap coefficient 8.3 (line 186) and h = 0.86/√3 (line 169). The pinned source and its
`docs/src/reference/wall_loss_models.md` give no literature source for the material constants. Evidence class: assumed
(software default); literature origin: verify. A Vyovrinda wall grade other than the solver's materials is a transfer
assumption that must be recorded in `wall_loss_model`.

## 4. Not supplied by the solver (not fields)

| id | quantity | why not | would need |
|---|---|---|---|
| NS-1 | **incidence angle** (mean or distribution) | 1-D axial model with a radial Bohm-flux closure: no radial velocity, no wall geometry in r-z, no angle. `Frame.tan_div_angle` is the **plume** divergence (`plume.jl`), not a wall angle, and must not be used as one | an r-z or kinetic sheath/erosion model, near-wall angle measurements (wall_life H7), or a cited angle treatment for the wall grade (wall_life flag `ANGLE_OUTSIDE_MEASURED`) |
| NS-2 | wall ion energy distribution; axial kinetic-energy share | fluid model: one velocity per species; mean sheath energy only | kinetic/2-D model, RPA/flush probes (H7) |
| NS-3 | neutral, fast-CEX-neutral and excited-state wall impact; quenching | no neutral/excited wall flux; recombined ions only re-enter as the container's ground neutral; no wall term in `deexcitation.jl` | a model change (neutral wall-flux model) |
| NS-4 | wall recombination products | fixed rule (ion → ground neutral of the same fluid container); no wall chemistry. The N/N₂ container grouping for `n2_n.toml` was not re-verified: verify | a cited wall-chemistry model and a solver change |
| NS-5 | inner vs outer wall split | single Δr = r_out − r_in | r-z model or measurements |
| NS-6 | resolved near-wall T_e (radial profile, EEDF) | the wall T_e is the 1-D cell T_e | r-z/kinetic model or probes (H7) |
| NS-7 | every wall field for a **shielded** thruster | the solver uses ghost-cell `cache.Tev[1]` blended by `wall_transition`, but `Frame.Tev[1]` is ghost-averaged, so this is not reproducible from saved frames | solver output of γ_SEE and wall T_e (a pin move, never automatic) or an owner-approved bridge hook; plus spec open decision 4 |
| NS-8 | ion-induced SEE, SEE spectrum, backscatter, SEE change after N/O exposure | `SEE_yield` is an electron-induced fit in T_e only | cited SEE model; H9 measurements |
| NS-9 | wall temperature, sputter yield, erosion rate | not modelled | `thermal_life.py` chain with a cited sputter-yield model |
| NS-10 | the solver's own γ_SEE / m_eff / wall-loss arrays as saved outputs | not in `Frame` | an upstream Frame extension and a pin move |

## 5. Migration (not done here)

Emitting any v2 field needs changes to several parts of the pipeline:

- `hallthruster_bridge/bridge_lib.jl` (`wall_ion_metrics` or a new `wall_v2_metrics`);
- the driver that writes records and maps;
- a v2-aware consumer;
- a consistency check.

Together these are a **controlled model-pipeline change that needs owner approval**. This lane touched no bridge, driver,
campaign, pre-registration, pinned-pipeline file or running job.

- v1 maps stay v1. A v2 map carries every v1 field unchanged, and v1 and v2 maps are never mixed in one map set.
- **PROPOSED consistency check** (owner decision). This extends the identity `checks/wall_flux_consistency.jl` already
  uses for Z = 1 xenon. In cells where wall_transition = 1, the re-evaluated Σ_s Z_s Γ_s / (Δr (1 − γ) n_e) must reproduce
  the solver-saved `Frame.nu_wall`. That identity constrains Γ/(1 − γ) jointly, not γ alone, because the solver has no
  separate saved γ. The only existing tolerance is that check's 1 % median, so the v2 tolerance is left to the owner.
- All v2 values are model-derived outputs, not validated against wall measurements (none exist). They inherit v1's trust
  rules: erosion-grade only when `wall_life_trustworthy`, and never from screening candidates or unadmitted closures
  (C6 in the pivot decision: no 15,000 h extrapolation from an unadmitted closure).

## 6. Findings from reading the pinned source (observations, no change made)

- **F1, identity.** The installed copy matches the pin by git tree hash (section 1).
- **F2, footprint.** The v1 `wall_ion_flux_m2s` averages over the cells with z ≤ L, **unweighted**. The solver's own ion
  removal (`ion_wall_losses = true`) acts on cells `2:last_wall_cell`, **weighted by wall_transition**, which ramps
  linearly from 1 at L − t/2 to 0 at L + t/2 (t = `transition_length`, default 0.1 L). The two footprints therefore differ
  near the exit. v1 is unchanged; v2 adds `profile_wall_transition` and per-cell profiles so a consumer can use either
  footprint explicitly. Owner may want the erosion chain to use the solver footprint.
- **F3, loss_scale default.** The positional constructor `WallSheath(material)` defaults `loss_scale` to **0.15**
  (`wall_losses.jl` line 161). The `Config` default is `WallSheath(BNSiO2, 1.0)`. v2 therefore records `loss_scale` in meta
  from the run's `Config`, so a map built with a different constructor call cannot pass silently.
- **F4, m_eff fallback.** In a zero-ion cell, the solver uses the first isothermal fluid's mass
  (`update_heavy_species_cache!`), while the bridge re-evaluation uses the first entry of `Frame.ions`. That these are
  the same species is not verified here (verify). It matters only in cells with zero ion density.
- **F5, shielded asymmetry.** `apply_ion_wall_losses!` uses `cache.Tev[i]`, while the electron side uses
  `wall_electron_temperature`. For a shielded thruster the ion and electron wall terms therefore use different T_e.
  This is one more reason NS-7 excludes shielded wall fields.
- **F6, documentation versus code.** The solver documentation writes the ion wall loss without the wall_transition weight
  and the wall power as `2T − φ`. The code applies wall_transition and uses `2T + (1 − γ)φ_s`. The code is what runs;
  every v2 definition follows the code.

## 7. Sources

- HallThruster.jl v0.23.1, commit `bfb3019f…`, installed copy read only (files and sha256 in the schema). Upstream
  repository: `https://github.com/UM-PEPL/HallThruster.jl` (as recorded in `PINNED.toml`; not fetched in this lane).
- Repository: `hallthruster_bridge/{PINNED.toml, Manifest.toml, bridge_lib.jl, hall_map_schema_v1.json,
  checks/wall_flux_consistency.jl}`, `docs/hallmap/HALLMAP_PRODUCTION_SPEC.md`, `schemas/hallmap/hallmap_provenance_v1.json`,
  `docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md`, `abep_sim/thermal_life.py`, `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`.
- No external URL was accessed and no person or lab was contacted.
