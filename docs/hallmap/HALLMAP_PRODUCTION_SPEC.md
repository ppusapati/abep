# Hall-map production specification (v1, for owner review)

**Status: specification only. No map has been generated and no simulation was run to write this document.**
Producing design Hall maps is **blocked** until all of the following are true:

1. At least one **admitted** transport-ensemble member exists. As of 2026-09-26 the credible set is **empty**
   (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`, `admission_rule_status`; CLAUDE.md gate 3 FAIL).
2. Vyovrinda's **own** thruster geometry and B(z) are in the repository with a source and a sha256. Neither exists as of
   2026-09-26: *TBD, requires a Vyovrinda design release (drawing/document id and revision, plus a magnetic-circuit
   computation or a measured B(z)).*
3. The numerical-convergence pre-registration is frozen by the owner. The draft is
   `docs/hallmap/drafts/hallmap_convergence_prereg_DRAFT.json`, with status `DRAFT_PENDING_OWNER`.

This document changes no physics, threshold, frozen dataset, chemistry, transport or campaign file. It does not claim an
ABEP closure, an architecture winner or any transport admission. Where it proposes something, it says **PROPOSED** and
leaves the decision to the owner.

Companion files:

| file | role |
|---|---|
| `schemas/hallmap/hallmap_provenance_v1.json` | JSON Schema for `meta.provenance` of one map set |
| `docs/hallmap/drafts/hallmap_convergence_prereg_DRAFT.json` | DRAFT numerical-convergence pre-registration (not frozen) |
| `tests/test_hallmap_spec.py` | keeps this spec, the schema and the draft consistent with `abep_sim/hall_map.py` and `abep_sim/hall_ensemble.py` |

## 1. Where the maps sit

The flow is fixed by the project decision of 2026-09-26 (CLAUDE.md "Next work" item 1): P5 evidence ensemble → credible
closure set → **Vyovrinda design-specific Hall maps (own geometry and B(z), one map set per member)** → whole-system UQ
reporting envelopes across members.

- The maps model **only** the ionization/discharge → acceleration/thrust block of the RFP architecture. They never feed
  back into, or take axes from, the intake, filter, compressor, gas chambers or valves. Those blocks supply the
  operating point (flow, composition). The map returns the discharge response.
- The producer is HallThruster.jl, pinned to v0.23.1, commit `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5`
  (`hallthruster_bridge/PINNED.toml`). It runs through `hallthruster_bridge/bridge_lib.jl` `run_case`, the same code path
  used for validation. The consumer is `abep_sim/hall_map.py` `HallMap`.
- A map is a JSON file following `hallthruster_bridge/hall_map_schema_v1.json`, with `meta`, `axes` and `fields`. This
  spec adds one object, `meta.provenance`, validated by `schemas/hallmap/hallmap_provenance_v1.json`. `HallMap` ignores
  unknown meta keys, so this is compatible with the current loader.

## 2. Preconditions checklist (all must hold before the first map run)

| # | precondition | enforced by |
|---|---|---|
| P1 | member id passes `abep_sim.hall_ensemble.require_admitted(member_id)` | generator (must call it before any simulation) and `HallMap` at load (`member_ids`) |
| P2 | `load_ensemble()` succeeds, which verifies the admission record offline (decision and scores-provenance files exist and match their sha256; the member is PROMOTABLE) | `hall_ensemble._check_admission` |
| P3 | the validation release manifest for the admitting campaign exists and its sha256 is recorded | provenance `source_validation` |
| P4 | installed HallThruster.jl equals the pin | bridge `check_pin()`; `HallMap` checks `meta.pinned` |
| P5 | the reaction set is file-complete (every `rate_coeff_file` exists) and every table used is `verified` in `propellants/rate_validity.toml` | bridge `check_reaction_sets`, `chemistry_validity`; provenance `chemistry.rate_files[].validity_status = "verified"` |
| P6 | Vyovrinda geometry and B(z) are versioned, hashed and sourced, and are **not** P5/ECHT evidence files | provenance `geometry`, `magnetic_field` (schema refuses file names that look like P5/ECHT/Brabston/Peterson) |
| P7 | the convergence pre-registration is frozen (not the DRAFT) | provenance `numerics.convergence.prereg_file` (schema refuses a path containing `DRAFT`) |
| P8 | `facility_ingestion = false` (flight maps) | `hall_map_schema_v1` meta; provenance `facility_ingestion: const false` |

## 3. What one map set is

A **map set** is fixed by a tuple of discrete labels. Labels are **never interpolated between**:

`(admitted member) × (chemistry config) × (propellant) × (geometry version) × (B(z) shape version) × (wall model, ion_wall_losses) × (numerics)`

- **Member.** Exactly one per map set (`meta.ensemble_member_id`). Members are an **unweighted** scenario set: maps of
  different members are never averaged, weighted or blended. The architecture trade and UQ run once per member and report
  envelopes (CLAUDE.md item 5).
- **Chemistry config.** PROPOSED: one map set per primary chemistry configuration pinned for P5-N₂ (`n2_n.toml`,
  `n2_n_di_lower.toml`, `n2_n_nel_wang.toml`, `n2_n_di_lower_nel_wang.toml`; `PINNED.toml` `uncertainty_variants`). The
  chemistry spread is carried as a further envelope dimension. Chemistry uncertainty is **not** calibration nuisance: it
  concerns rate data that do transfer to Vyovrinda's thruster. It is still a discrete label, not an axis. Owner decides
  whether the staged sensitivity branches also get map sets.
- **Propellant.** Separate map sets for Xe (built-in HallThruster.jl tables) and N₂ (project reaction set `abep-n2n-0.11`).
  Air mixtures (N₂/O₂/O) are **blocked**: no O/O₂ chemistry exists yet (CLAUDE.md item 4, "only if 1–3 succeed").
- **Geometry and B(z) shape.** Fixed per map set. A geometry revision is a new map set, not an axis. This replaces the
  continuous `L_ch` variable of the superseded 0-D Hall branch in `abep_sim/archengine.py`.
- **Wall setting and numerics.** Fixed per map set and recorded in provenance (section 7 and section 11).

## 4. Grid axes (PROPOSED)

Axis names follow the example in `abep_sim/hall_map.py` (`Vd, mdot_kgps, x_O, ...`). Ranges are **not** given here,
because giving them would mean inventing operating points (CLAUDE.md rule 6).

| axis | unit | meaning | range | source / evidence class |
|---|---|---|---|---|
| `Vd` | V | discharge voltage | TBD, requires the Vyovrinda PPU/anode-supply design range | design input (requirement). The current `archengine._variables` Hall grid (225–325 V) belongs to the superseded 0-D model and is **assumed**, so it must not be reused without owner confirmation |
| `mdot_kgps` | kg/s | anode mass flow of the map's propellant | TBD, requires the intake → compressor → gas-chamber → valve delivered flow over the RFP altitude band (180–230 km, requirement per CLAUDE.md, verify against the RFP text) for air, and the Xe feed design for Xe | model-derived (frozen NRLMSIS + TPMC intake + compressor), computed by a named script in the production PR, not here |
| `B_scale` | – | amplitude multiplier on Vyovrinda's fixed-shape B(z) (`B_ref_T × B_scale`) | TBD, requires the Vyovrinda coil/magnet design range | design input. Applied the way validation applied it (bridge `measured_bfield` B_ref scaling, solver `magnetic_field_scale = 1`), so no code path is used that validation never exercised |
| `x_O`, `x_O2` (mole or mass fractions, basis recorded) | – | intake-delivered composition | **blocked** (no O/O₂ chemistry) | model-derived from the intake chain when it becomes available |

### 4.1 Forbidden axes: calibration nuisance is NEVER a map axis

Layer-1 calibration nuisance is uncertainty in what the P5 experiment **was**. It is marginalized when admitting closures
and is never a Vyovrinda design variable, map axis, map-set label or trade dimension (CLAUDE.md item 1;
`transport_ensemble_v0.json` `calibration_nuisance`). The keys are:

- `p5_registration` (L38-hist / L32-anode / L32-exit)
- `p5_coil_shape` (1p6kW / 3p0kW)
- `beam_efficiency_reading` (A / B), which is also the P5-N₂ divergence reading
- `facility_ingestion_interpretation` (vacuum / facility)

Enforcement has three parts:

- `HallMap.__init__` already raises if any `calibration_nuisance` key is an axis name.
- The provenance schema's `forbidden_axis_names` extends that list with common spellings, facility-only variables
  (`background_pressure_Torr`, `entrainment_area_m2`, `zeta_A`, `zeta_en`, `comparison_mode`), transport parameters
  (member-fixed) and discrete labels (`ensemble_member_id`, `chemistry_variant`, `propellant_config`).
- `passing_layer1_members` of the admission record is copied into provenance **as admission provenance only**.

In practice this means three things. P5 B(z) files are never a design field. P5 beam-efficiency factors A/B are never
applied to design thrust. The facility-ingestion model is never switched on for a design map.

### 4.2 Other non-axes

- **Transport parameters** (`anom_scale`, `barrier_scale`, `center_L`, `width_L`, ...) are fixed by the member and never
  retuned for the design geometry. The ScaledGaussianBohm profile is expressed in channel-length units, so applying it to
  Vyovrinda's channel is a **transfer hypothesis** (section 9).
- **Background pressure / facility state**: flight maps only.
- **Cathode flow**: the bridge models no separate cathode flow. `mdot_kgps` is the anode flow, and the cathode budget
  stays in the architecture engine's neutralizer model.
- **Pre-ionized inflow**: the 1-D maps have no pre-ionization axis (see section 12).

### 4.3 Node placement (PROPOSED)

- Axis values strictly increasing. The grid is complete: every node of the Cartesian product is run, and none is dropped.
- Spacing is chosen before any run. An **interpolation-adequacy check** is PROPOSED: at pre-declared cell midpoints
  (for example the centre of every cell adjacent to the box centre), run the point directly and compare with the
  multilinear interpolant, using the same tolerances as the convergence draft. Owner decides whether this becomes part of
  the frozen pre-registration.

## 5. Interpolation and forbidden extrapolation

What `HallMap` does today (`abep_sim/hall_map.py`):

- Multilinear interpolation (`scipy.interpolate.RegularGridInterpolator`) on the regular grid, applied to every field,
  including the Boolean flags as 0/1.
- **Any query outside an axis range raises** (`"no extrapolation"`), with a tolerance of 1e-12.
- Fields are reshaped in the order of `axes` keys (row-major). The producer must therefore write `axes` as an **ordered**
  object and flatten fields in that order. The provenance repeats the ordered axis list, and the consumer should check
  that they agree (`x-consistency_rules`). This matters for a Julia writer, because a plain `Dict` does not guarantee key
  order.

Forbidden, in addition to that:

| forbidden | why |
|---|---|
| numerical extrapolation beyond the axis box | enforced by `HallMap` |
| interpolating between members, chemistry configs, propellants, geometries, B(z) shapes, wall settings or numerics | discrete labels (section 3). Envelopes are formed downstream from per-set results |
| using a node whose chemistry used a table beyond its validity limit | `chemistry_trustworthy` false, so the query is not `trustworthy` (section 8) |
| filling a failed node with a number | CLAUDE.md item 5 "never fill missing fields with placeholders". PROPOSED convention: a node without solver output stores JSON `null` in every non-flag field (loaded as NaN) and `false` in every flag. Queries touching it then return NaN and `trustworthy = False` |
| using a map for a gas, geometry or B(z) other than its provenance | provenance binding |

**Transport transfer is not numerical extrapolation, but it must be declared.** A design map evaluates an admitted
closure on a thruster it was never validated on. Every map set therefore records the member's validation domain and an
explicit transfer statement in `validity_domain`. The transport form stays at evidence level 7 ("assumed model form",
docs/EVIDENCE.md register) for the design geometry until Vyovrinda hardware data exist. Hardware validation supersedes
the literature-derived closure within its validated domain (CLAUDE.md rule 10).

PROPOSED consumer additions (not implemented; outside this lane):

1. Refuse or flag a query whose surrounding nodes straddle a regime change (quiet vs breathing, `Id_rms_rel` above or
   below the bridge's internal 0.5 diagnostic). An interpolated average of a quiet and a breathing node is not an
   operating point.
2. Check `meta.provenance` against the top-level meta (`x-consistency_rules`).

## 6. Required quantities = `hall_map.REQUIRED_FIELDS`

Every node carries every field of `hall_map_schema_v1` (`abep_sim.hall_map.REQUIRED_FIELDS`, derived from the schema
file). `HallMap` refuses a map missing any of them. The provenance schema's `fields_present` must list exactly this set,
and `tests/test_hallmap_spec.py` checks it.

| field | unit | role in design use |
|---|---|---|
| `thrust_N` | N | performance. 1-D ion momentum flux. The bridge does not enable the solver's divergence correction, and no P5 reading A/B is applied. Vyovrinda plume divergence is *TBD, requires a Vyovrinda plume measurement or a separately justified model* |
| `discharge_current_A` | A | performance (neutralizer current demand) |
| `ion_current_A` | A | performance (beam current) |
| `discharge_power_W` | W | performance (= I_d × V_d, PPU load) |
| `anode_eff` | – | performance (jet power = anode_eff × P_d) |
| `mass_eff` | – | performance (propellant utilization) |
| `current_eff` | – | performance decomposition |
| `voltage_eff` | – | performance decomposition |
| `divergence_eff` | – | performance decomposition (solver-internal; not a plume measurement) |
| `Te_max_eV` | eV | state diagnostic; context for the chemistry domain |
| `ne_max_m3` | m⁻³ | state diagnostic |
| `ion_species_fraction_atomic` | – | exit composition diagnostic (1.0 for Xe) |
| `wall_ion_flux_m2s` | m⁻² s⁻¹ | erosion input, **erosion-grade only if `wall_life_trustworthy`** |
| `wall_ion_energy_eV` | eV | erosion input, same condition |
| `Id_rms_rel` | – | oscillation diagnostic |
| `Id_pp_rel` | – | oscillation diagnostic |
| `Id_f_dominant_Hz` | Hz | oscillation diagnostic (resolution 1/window length) |
| `converged` | bool | node trust flag |
| `sustained` | bool | node trust flag (bookkeeping convention, 1 % of window mean) |
| `wall_life_trustworthy` | bool | erosion trust flag |
| `chemistry_trustworthy` | bool | chemistry-domain trust flag |

Two consequences:

- **Shielded designs cannot be mapped under schema v1.** The wall fields are absent for shielded thrusters or wall
  models other than `WallSheath` (hall_map_schema_v1), and absent fields must not be filled. If Vyovrinda's design is
  magnetically shielded, the owner must first decide on a schema change.
- Per-node raw bridge records (including `chemistry_per_reaction`, `chemistry_unresolved_rate_files` and `wall_ion_basis`)
  are retained next to the map, with a sha256 (`raw_records` in provenance). The chemistry domain can then be audited from
  f_out directly, independent of `sustained`, the same way the P5-N₂ run-status rule O2 does.

## 7. Performance `trustworthy` vs `wall_life_trustworthy`

These are two separate verdicts per query (`HallMap.__call__`):

- **Performance `trustworthy`**: every surrounding grid node `converged`, **and** interpolated `sustained > 0.999`, **and**
  every surrounding node `chemistry_trustworthy`. Only such queries may enter the architecture trade.
- **`wall_life_trustworthy`**: performance-trustworthy, **and** `meta.ion_wall_losses is True`, **and** every surrounding
  node `wall_life_trustworthy`. At node level that means converged ∧ sustained ∧ `ion_wall_losses=true` ∧ `WallSheath` ∧
  unshielded ∧ both wall fields present. Only such queries may feed erosion/lifetime. `map_ready` means schema-complete
  only.

Observations for the owner (no change made):

1. **`ion_wall_losses` is not set by the bridge today.** The solver default in the installed v0.23.1 source is `false`
   (`src/simulation/configuration.jl`, Config keyword default; identity of the installed copy with the pin: verify).
   Validation runs therefore use `false`, so no current map could be erosion-grade. Producing erosion-grade maps means
   setting `ion_wall_losses = true`. That changes the discharge physics relative to the numerics and physics under which
   a member was admitted. **Owner decision needed**, for example: (a) performance map sets at `false` (as admitted) plus
   separate wall-life map sets at `true`, with the performance deltas between them reported; or (b) a consistency check of
   the admission evidence at `true`. The wall model is the solver default `WallSheath(BNSiO2, 1.0)` (`PINNED.toml`
   `defaults_used`). A Vyovrinda wall material different from BNSiO2 is another transfer assumption, recorded in
   `wall.wall_loss_model`.
2. `sustained` is checked on the interpolated value, but `converged` and `chemistry_trustworthy` are checked on **all**
   surrounding nodes. A query on a cell face gives zero weight to some corners, so a non-sustained zero-weight corner does
   not lower the interpolated `sustained`. Owner may want `sustained` checked like the other two (consumer change).
3. For built-in xenon, `chemistry_trustworthy` reduces to converged ∧ sustained. There is no project validity manifest
   for the built-in Xe tables (hall_map_schema_v1). Xe map sets must state this `limitation` in provenance.

## 8. Chemistry-domain requirements (f_out = 0)

- Every rate file of the map set's chemistry config is `verified` in `propellants/rate_validity.toml`. An `unresolved`
  table anywhere means the map set is refused (provenance `validity_status: const "verified"`).
- A node is `chemistry_trustworthy` only if, for **every** reaction, the extrapolated activity share f_out (activity
  n_e·n_target·k_r(3/2 T_e) summed over every saved frame of the averaging window and every cell, from cells above the
  file's mean-energy limit) is ≤ 1e-12. This is evaluated per frame, not on time averages (`hall_map_schema_v1`;
  `checks/chemistry_validity_check.jl`; CLAUDE.md item 5). **f_out = 0 is not relaxed for maps**, and no
  reaction-contribution allowance exists unless one is pre-registered.
- Declared domain of the N₂ set (`PINNED.toml [reaction_set].domain`): T_e 2–30 eV (mean energy 3–45 eV); vibrational
  and rotational excitation audited over T_e 0.2–30 eV. Status `COMPLETE_FOR_P5_N2_VALIDATION`, scoped to P5-N₂
  validation only. Using the set for design maps is a separate owner decision: the status text makes no general
  completeness claim. Nodes whose discharge reaches T_e beyond a capped table's limit are **not** trustworthy. The pre-campaign
  blind closure state envelope already showed this for some screening candidates (CLAUDE.md item 2, "Open for the P5-N₂
  pre-registration"). That is an audit record, not a validation result.
- The chemistry config and its sha256, the rate-validity manifest sha256 and every rate file's sha256 are recorded in
  provenance.
- The saved-frame spacing determines how f_out is sampled. The convergence draft therefore keeps the frame spacing fixed
  when doubling run time (R3, `num_save`).

## 9. Member-ID requirement

- **One map set per admitted member**, carrying `meta.ensemble_member_id`.
- The generator **must** call `abep_sim.hall_ensemble.require_admitted(member_id)` before building any case. This raises
  for screening candidates ("screening candidates never produce design Hall maps") and for unknown ids.
  `HallMap.__init__` repeats the check at load time against `member_ids(load_ensemble())`, so a map of a member later
  eliminated by new evidence stops loading automatically. Its provenance status then becomes `WITHDRAWN`.
- **Screening candidates (`sgb-screen-01..09`) are refused.** An admitted member keeps its id
  (`promoted_from_screening_id == ensemble_member_id`), so the id pattern alone cannot tell them apart. The admission
  record, verified offline by `load_ensemble()` and copied into provenance, is what distinguishes them.
- The member's `transport_parameters` are used exactly as recorded. There is no retuning to the design geometry, and the
  physical prior (`anom_scale` ≤ 1/16, `transport_ensemble_v0.json` `admission_rule`) is inherited.
- `transport_as_run` (the solver's own model string, = `meta.transport`) must describe the same closure as the ensemble
  entry.

## 10. Provenance (`schemas/hallmap/hallmap_provenance_v1.json`)

The provenance object is embedded as `meta.provenance`. It is required in full and has no optional top-level blocks:

| block | content |
|---|---|
| `hall_map_schema` | name `hall_map_schema_v1`, file, sha256 |
| `map_set` | id, status (`CANDIDATE`/`FROZEN`/`WITHDRAWN`), UTC, generator script + git commit + sha256, per-node case file + sha256 |
| `ensemble_member` | member id, family, parameters, solver transport string, ensemble file sha256, **admission record** (all `hall_ensemble.ADMISSION_FIELDS`, including decision sha256) |
| `source_validation` | admitting campaign id, **validation release manifest** file + sha256 (`scripts/make_validation_release.py` output), prereg lock file + sha256, decision sha256 |
| `hallthruster` | package, version, pinned commit, installed commit, sha256 of the full `PINNED.toml` text |
| `chemistry` | project config: reaction-set version and status, chemistry variant, config sha256, rate-validity sha256, every rate file sha256 (all `verified`), f_out tolerance 1e-12, declared domain. Or built-in: version string and limitation |
| `propellant` | gas; composition basis |
| `geometry` | Vyovrinda geometry id, version, file, sha256, source, evidence class, L, r_in, r_out, domain |
| `magnetic_field` | Vyovrinda B(z) id, version, file, sha256, source, evidence class, placement, scale reference, B_ref, fixed shape, scale mechanism |
| `numerics` | grid type and cells, dt, duration, averaging start and window, num_save, timestepping (adaptive, CFL, min/max dt, max_small_steps; passed or solver default), whether they match the admission numerics, **frozen** convergence prereg + sha256 + verdict |
| `wall` | wall model string, `ion_wall_losses`, shielded, `wall_ion_basis` |
| `facility_ingestion` | `false` |
| `axes` | ordered list: name (not a forbidden name), unit, values, bounds source, evidence class |
| `fields_present` | exactly `hall_map.REQUIRED_FIELDS` |
| `observables_basis` | thrust basis; failed-node convention |
| `trust` | the two rules verbatim; node counts |
| `validity_domain` | axis box only; extrapolation forbidden; chemistry domain; member validation domain + source; transfer statement |
| `evidence` | the docs/EVIDENCE.md attributes: level, quantity type (`model-derived`), source, uncertainty, applicability, validation status, transformation chain |
| `raw_records` | per-node bridge records file + canonical sha256; per-reaction chemistry retained |

`x-hall_map_meta_mapping` in the schema maps every key of `hall_map.REQUIRED_META` to a provenance path, and
`x-consistency_rules` lists the equalities a future loader must check. A `FROZEN` map set requires convergence verdict
`PASS` (schema `allOf`). The schema is data only. No validator dependency is added (`jsonschema` is not in
`requirements-lock.txt`), so the test file carries a minimal validator for the keywords the schema uses.

## 11. Numerics and numerical convergence

- **Baseline numerics = admission numerics (PROPOSED).** The P5-N₂ validation fixes 200 cells (EvenGrid), dt 5 ns, 2 ms,
  averaging 1–2 ms (`prereg/p5_n2_validation_criteria_v1.json` `no_retuning`; every case of `cases/p5_n2.json`). Evidence
  class: assumed (numerical setting). A member's admission is conditional on these numerics. Design maps at other
  numerics would evaluate a closure under settings in which it was never tested.
- **Timestepping finding.** The bridge calls `SimParams(grid, dt, duration, verbose=false)` and does not pass `adaptive`,
  `CFL`, `min_dt`, `max_dt` or `num_save`, so the pinned solver defaults apply. In the installed v0.23.1 source these are
  adaptive = true, CFL 0.799, min_dt 1e-10 s, max_dt 1e-7 s, max_small_steps 100, num_save 1000 (`src/simulation/types.jl`;
  identity of the installed copy with the pin: verify; evidence class: assumed, software default). With adaptive stepping
  the step is CFL-limited, and `dt` is only the escape-hatch uniform step (`src/simulation/solution.jl`,
  `heavy_species_update.jl`). A pure **dt → dt/2** refinement can therefore be a no-op. The draft keeps it as requested
  and PROPOSES **CFL → CFL/2** as the effective time-step refinement.
- **Draft pre-registration** (`docs/hallmap/drafts/hallmap_convergence_prereg_DRAFT.json`, `DRAFT_PENDING_OWNER`, not
  frozen, deliberately outside `hallthruster_bridge/prereg/`):
  - Refinements, one factor at a time from the same baseline: 200 → 400 cells; dt → dt/2 (and PROPOSED CFL/2); run time
    2 → 4 ms, with the averaging window and frame spacing handled explicitly.
  - PROPOSED tolerances: I_d 2 % rel; thrust 2 % rel; mass utilization 0.02 abs; wall ion flux and wall ion energy 5 % rel
    at erosion-grade nodes.
  - Categorical invariants: `converged`, `sustained`, `chemistry_trustworthy` (with per-reaction f_out), `wall_life_trustworthy`
    and the quiet/breathing class must not flip.
  - The node-selection rule is fixed before any refined run, and there is no post hoc dropping of nodes.
  - Every tolerance carries its rationale and is explicitly a proposal for the owner.
- CLAUDE.md gate 5 ("numerical convergence: pass") was recorded before this 1-D design-map pipeline existed. This spec
  does not change gate 5 and does not claim that design maps are converged.

## 12. Consumer wiring (`abep_sim/archengine.py`), for the later PR

The present Hall branch (`_propulsion`, `ac.family == "hall"`) calls the **superseded** 0-D `hall_run_coupled`, with the
continuous design variables `Vd` and `L_ch` (`_variables`). When it is rewired to `HallMap`:

| archengine quantity | map source |
|---|---|
| `T_N` | `thrust_N` |
| `P_acc_W` | `discharge_power_W` |
| `I_neut_req_A` (neutralizer current) | `discharge_current_A` |
| `I_beam_A` | `ion_current_A` |
| `P_jet_W` | `anode_eff × discharge_power_W` |
| `res["sustained"]` | `sustained` flag of the query (not a beam-current threshold) |
| `life_items["hall_channel"]` | only from wall fields of a `wall_life_trustworthy` query **and** a cited sputter-yield model (TBD). Otherwise the life item is reported unavailable, never a default |

Rules for the rewired branch:

- A query that is not `trustworthy`, or that is outside the axes, becomes `MODEL_ERROR` / out-of-domain (CLAUDE.md rule 3).
  It is never infeasible-by-default, and it is never silently clamped to the box.
- `L_ch` stops being continuous: geometry is chosen among map sets.
- Architectures that feed a **pre-ionized** flow into the Hall channel (plasma ionizer → Hall) have no map axis for it.
  They are outside the map domain and must be refused, not evaluated with pre-ionization dropped.
- `HALL_OVERRIDES` (the 0-D UQ hook) must not be used to emulate transport members. Member variation comes only from
  loading a different member's map set.
- The trade and UQ run once per admitted member (and per chemistry map set, if the owner adopts section 3). Results are
  envelopes, never one deterministic answer and never a member-weighted mean.

## 13. Open decisions for the owner

1. Chemistry: one map set per primary chemistry config (section 3)? Also for the staged sensitivity branches?
2. Is using `abep-n2n-0.11` (`COMPLETE_FOR_P5_N2_VALIDATION`) for design maps acceptable, given its scope statement?
3. `ion_wall_losses`: separate performance (`false`) and wall-life (`true`) map sets, or a re-check of the admission
   evidence at `true` (section 7)?
4. Shielded Vyovrinda design: needs a schema change before any map (section 6).
5. Failed-node convention (JSON `null` + false flags) (section 5).
6. Regime-straddle refusal and the `sustained` corner check in `HallMap` (sections 5 and 7).
7. Convergence draft decisions D-C1…D-C8 (draft file), and whether the interpolation-adequacy check (section 4.3) is
   pre-registered with it.
8. Axis ranges: sources for the V_d, mdot and B_scale bounds (Vyovrinda design documents; intake-chain script).
9. Producer changes outside this lane: pass `CFL`/`num_save`, report escape-hatch use, write ordered `axes`, emit
   `meta.provenance`.

## 14. Numbers used in this document

Every number here was taken from a repository file or the installed solver source. None is a new physical value.

| value | where from | class |
|---|---|---|
| HallThruster.jl v0.23.1, commit `bfb3019f…` | `hallthruster_bridge/PINNED.toml` | pinned software identity |
| 200 cells, dt 5e-9 s, 2e-3 s, averaging from 1e-3 s | `prereg/p5_n2_validation_criteria_v1.json` `no_retuning`; `cases/p5_n2.json` | assumed (numerical setting) |
| adaptive = true, CFL 0.799, min_dt 1e-10 s, max_dt 1e-7 s, max_small_steps 100, num_save 1000, `ion_wall_losses = false`, `magnetic_field_scale = 1.0` | HallThruster.jl v0.23.1 installed source, `src/simulation/types.jl`, `configuration.jl` (identity with pin: verify) | assumed (software default) |
| `WallSheath(BNSiO2, 1.0)` default wall model | `PINNED.toml` `defaults_used` | assumed (software default) |
| f_out tolerance 1e-12 | `hall_map_schema_v1.json`; CLAUDE.md item 5 | pre-registered rule |
| T_e 2–30 eV (mean energy 3–45 eV); vib/rot T_e 0.2–30 eV | `PINNED.toml [reaction_set].domain` | declared model domain (project decision) |
| `sustained` threshold 1 % of window mean | `hall_map_schema_v1.json` `conventions` | bookkeeping convention |
| quiet diagnostic `Id_rms_rel` < 0.5 | `bridge_lib.jl` (internal diagnostic, "no experimental meaning") | assumed (diagnostic threshold) |
| `anom_scale` ≤ 1/16 | `transport_ensemble_v0.json` `admission_rule` | assumed (physical prior) |
| 15 % I_d tolerance; 5.2–5.6 mN thrust tolerances | `prereg/p5_n2_validation_criteria_v1.json` D3 | pre-registered rule (context only) |
| < 0.2 % and up to 21 % I_d changes at 400 cells / 4 ms | docs/HISTORY.md, 2026-09-25 sections (driver runs, P5 xenon untuned; P5 xenon rerun with measured B(z)) | model-derived |
| 180–230 km, 12–25 mN, < 1.5 kW, 26,000 h, > 15,000 h | CLAUDE.md summary of RFP DTDF/06/13516/DSP/ABEP/X/L/M/01 | requirement (not a simulator input); verify against the RFP text |
| 225–325 V Hall grid | `abep_sim/archengine.py` `_variables` (superseded 0-D) | assumed; not adopted |

Sources accessed for this spec: repository files named above, and the locally installed HallThruster.jl v0.23.1 source
(read, not executed). No external URL was accessed, and no person or lab was contacted.
