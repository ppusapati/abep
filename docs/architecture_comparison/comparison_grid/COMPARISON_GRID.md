# Common operating-envelope comparison grid v1 (hall_only / rf_hall / ecr_hall)

**Status: DRAFT_PENDING_OWNER.** Not frozen, not hash-locked, and no comparison may run on it yet (see
[Freeze procedure](#freeze-procedure)).

| file | role |
|---|---|
| `docs/architecture_comparison/comparison_grid/comparison_grid_v1.json` | the grid: axes, levels with provenance, base points, evaluations, rules, freeze blockers, hashes |
| `schemas/architecture_comparison/comparison_grid_v1.schema.json` | structure (draft 2020-12, keyword subset checked by the builder's own validator) |
| `scripts/architecture/build_comparison_grid.py` | deterministic builder (< 1 s, no Julia, no physics computation) |
| `tests/test_comparison_grid.py` | reproduction, schema, fairness, nuisance, TBD propagation, hash, freeze tests |

Grid content sha256 (axes + base points + evaluations + rules, canonical JSON):
`b07cea899853c1cb35dad331646f7309420225ad33efb0ece26349027cea6319`.
Size: **95 base points, 475 evaluations** (hall_only 95, rf_hall 190, ecr_hall 190). All 95 base points are
`PENDING_TBD_LEVELS`, because the feed state at the valve outlet is TBD in the feed envelope.

## What it is, and what it is not

It is the single point set on which the three architectures are compared, fixed **before** any architecture is
evaluated. A later comparison (the harness `abep_sim/arch_compare.py`, or a test campaign under the experiment protocol)
only has to walk the list. No architecture can get favourable points, because the point set is architecture-free.

It is not a result, a ranking, a design point or a Hall prediction. No level was chosen by performance. It does not
use a Hall closure, a screening candidate or a Hall-map output. It is not wired into `archengine`, and the goldens do
not move.

## Structure

A **base point** is (feed mode) × (feed state) × [Xe mixing level, mixed mode only] × (discharge voltage). Each base
point is evaluated for **every** architecture. Only the pre-ionizer source power differs:

| architecture | P_source levels at every base point |
|---|---|
| `hall_only` | `PS0` = 0 W (definition: no pre-ionizer component in `bus_power_boundary_v1`) |
| `rf_hall` | `PS_LO`, `PS_HI`: the same set as `ecr_hall` |
| `ecr_hall` | `PS_LO`, `PS_HI`: the same set as `rf_hall` |

Base points per feed mode: `xe_start` 5 (1 feed level × 5 V_d), `mixed` 45 (9 feed cases × 1 mixing level × 5 V_d),
`atmosphere_dominant` 45 (9 × 5). An evaluation id reads `<mode>/<feed level>/[<mix level>/]<V_d level>/<arch>/<P level>`,
for example `atmosphere_dominant/alt200_mean_orbit_averaged/V250/rf_hall/PS_HI`.

## Axes and how each level was chosen

Every level is SOURCED (copied with its source pointer and evidence class), PROPOSED (not in the RFP; for the
owner), DEFINITION (true by the definition of a mode or an architecture) or TBD (value `null` plus what it requires).
A TBD in a prerequisite stays TBD here: nothing is filled from code defaults or from historical values.

### 1. Feed mode (`feed_mode`): PROPOSED, evidence class assumed

Source: the lane-23 task definition (Xe start, mixed, atmosphere-dominant) for the RFP's air + Xe dual feed
(CLAUDE.md "What this is"; the RFP architecture, in which the atmospheric path and the Xe path both feed the
ionization/discharge block). The mode names are cross-referenced (names only, no values) to the dual-feed control-logic
draft `schemas/controls/dual_feed_state_machine_v1.json`. That draft belongs to another lane and was uncommitted when
it was read on 2026-09-26 (file sha256 `f556f7dcd45c2c8a37a6258c4634e4a074c5e89fc9cb0c969d2aff950518bb52`). The
builder does not read it.

| mode | anode feed | Xe anode mass fraction | feed levels | dual-feed draft states |
|---|---|---|---|---|
| `xe_start` | Xe path only (IF-X2) | 1 (DEFINITION) | `xe_path` | XE_DISCHARGE_IGNITION, WARM_UP, XE_FALLBACK |
| `mixed` | atmospheric case (IF-A5) + Xe (IF-X2) | levels TBD (`XMIX_TBD`) | 9 atmospheric cases × mixing levels | ATMOSPHERE_ADMISSION, MIXED_STABILIZATION, ATMOSPHERE_DOMINANT with trim |
| `atmosphere_dominant` | atmospheric path only (IF-A5); Xe to the cathode only | 0 (PROPOSED node) | 9 atmospheric cases | AIR_ONLY_ANODE_XE_CATHODE, ATMOSPHERE_DOMINANT at zero trim |

The atmosphere-dominant node sits at zero Xe anode trim, so it does not depend on the TBD trim limit. Any non-zero trim
is a `mixed` level (GQ-3). The mixing-fraction levels are TBD: they need a Xe flow-setpoint policy. The feed envelope's
`xe_path.mixed_air_xe_feed` is TBD, and so is ICD G-12. The single placeholder level `XMIX_TBD` is replaced by the
owner's set before freeze.

### 2. Feed state (`feed_state`): structure SOURCED, values TBD

The feed state comes from the feed envelope `docs/architecture_comparison/feed_envelope/feed_envelope_v1.json` (FEED
lane 16, commit `ab27dcc449690606defa09af59725c0ad2eeaab4`, file sha256
`ada3ee720b1b8d60526d3b092492589f62a4144112845b4d813dbc8dc7d5ca02`). It has one level per feed-envelope case: 180 / 200
/ 230 km × atmosphere level low / mean / high (F10.7 = F10.7A 70 / 150 / 230, ap 15, orbit-averaged; the level mapping
is evidence class *assumed* in the feed envelope). There is also one Xe-path level `xe_path` (IF-X2), which is
altitude- and architecture-independent in the feed envelope.

- **Values:** the valve-outlet state at IF-A5 (`mdot_total_kgps`, `mdot_s_kgps`, `p_feed_Pa`, `T_gas_K`, `w_s`, `x_s`)
  is **TBD in all 9 cases** in the feed envelope. The repository documents no design baseline with provenance. The
  grid copies each quantity with its `requires` text and its source pointer. On IF-X2, `mdot_xe_anode_kgps`,
  `mdot_xe_cathode_kgps`, `p_feed_Pa` and `T_gas_K` are TBD. `x_s = w_s = {Xe: 1}` has evidence class *assumed*
  (pure-Xe definition).
- **Context only:** each atmospheric level also carries the IF-A0 free-stream `x_s`, `p_ambient_Pa` and
  `mass_flux_kgpm2ps` of its case (model-derived, frozen NRLMSIS 2.1). They are **not** the feed composition or flow:
  the intake, reservoir and valve change them.
- The feed pressure is not an independent axis. It follows the flow and the hardware conductance of the case, as in
  the feed envelope's single state per case. There is no independent throttle axis; if the owner adds one, it applies
  to all architectures.

### 3. Discharge voltage (`discharge_voltage_V`): PROPOSED, evidence class assumed

The levels are 180, 200, 250, 300 and 305 V: the `proposed_evaluation_set_V` of the Hall accelerator reference
`docs/architecture_comparison/hall_reference/hall_reference_v1.json` (HALLREF lane 17, span rule VR-1, invariance
rule INV-V1). The range is 180–305 V, and 180–350 V (VR-1 with relaxed (c)) is on record as an alternative. The grid
only enumerates this set and does not choose a voltage. The same set applies in every feed mode (GQ-6) and in every
architecture (GR-7).

The lane brief named HALLREF commit `396d27c` (file sha256 `7b0bf1d2b979d0b4fa9cc0790a2119ea29dc2c26e51781b1d3ffd69ca1000225`). While this lane was being built, the HALLREF
lane committed a third repair, `91ebd8a4017eb8609804846603063a25c41405c1` (file sha256
`c60e0adfbef2c6f8dddaa9b7e89cea6b0ce760d3c9777dff5a47c2bfda7cb2e6`). The grid is built from `91ebd8a`, whose worktree
file equals the committed blob. Everything the grid extracts is identical at both commits: evaluation set, range, span
alternatives, power ceiling and boundary components (checked with `extract_hall_reference` on both blobs). The HALLREF
lane was reported `verified=false` at `396d27c`, and `91ebd8a` has no verification record. That is a freeze blocker.

### 4. Pre-ionizer source power (`p_source_W`)

- **Definition (PROPOSED):** P_source is the sum of the DC-bus input power of the architecture-specific components of
  `bus_power_boundary_v1` (`abep_sim/arch_boundary.py`, another lane; components `rf_source` for rf_hall and
  `ecr_source` + `ecr_magnet` for ecr_hall; the builder checks these names against the Hall reference's
  `bus_power_boundary` block). Equal P_source then means equal bus spending on pre-ionization in the two source arms.
  The alternative, generator power only, is GQ-4.
- **Level structure (PROPOSED):** 2 non-zero levels. This follows the XPROT draft parameter
  `preionizer_nonzero_levels_min` = 2 (`docs/architecture_comparison/experiment_protocol/protocol_draft.json`,
  commit `1428265`, PROPOSED, assumed: "needed to see a dose-response").
- **Values: TBD.** They require the owner's pre-ionizer bus-power allocation within `bus_power_boundary_v1`, one value
  per level shared by rf_hall and ecr_hall.
- **Not adopted:** the minimum-decisive-experiment rule P_lo = max(lowest stable source power at that flow, 0.5 P_hi)
  (T-PLO-FRACTION, commit `e0f6be3`). "Lowest stable source power" differs between the RF and ECR sources and between
  flows, so it would give the two source arms different levels.
- **Bound:** 0 < PS_LO < PS_HI < P_bus_max = 1500 W (RFP, copied from the Hall reference `requirements.power_max_W`,
  evidence class assumed; the builder cross-checks it against `abep_sim.constants.RFP.power_max_W`). This applies if
  the RFP ceiling is taken at the `bus_power_boundary_v1` boundary; the bus-boundary lane leaves that question open
  (GQ-7). At a given point the usable headroom is 1500 W minus that point's common loads. Those loads are TBD until the
  ledger and an admitted Hall closure exist. If a level exceeds the headroom, that evaluation is a recorded INFEASIBLE
  result through a hard gate. The point is never removed.

## Rules (in the JSON as GR-1 … GR-8)

1. Every architecture is evaluated at every base point. Applicability depends on feed mode, feed level and mixing
   level only, never on the architecture.
2. No per-architecture cherry-picking. A point where an architecture does not sustain, or is infeasible, is a
   recorded result. Eliminations happen only through explicit hard-gate logic
   (`docs/architecture_comparison/hard_gates/`) with the evidence class that supports them.
3. hall_only is evaluated at P_source = 0 only. rf_hall and ecr_hall use the same non-zero set at every base point.
   Comparisons are paired at the same base point.
4. The feed state is the feed-envelope record, identical for all architectures. Hall-closure outputs never feed back
   into a feed level (no upstream leak).
5. The layer-1 P5 calibration nuisance is never an axis or a level: `p5_registration`, `p5_coil_shape`,
   `beam_efficiency_reading`, `facility_ingestion_interpretation`, read from
   `hallthruster_bridge/ensemble/transport_ensemble_v0.json` and listed in `forbidden_axes`. Layer-2 transport closures
   are scenarios applied by the harness to every point (admitted members only; the set is empty today). They are never
   axes, and screening candidates never produce grid results.
6. TBD propagates. Each base point lists its `tbd_dependencies`, and each evaluation lists anything it adds (the
   P_source level).
7. One discharge-voltage set for all architectures and modes.
8. After freeze the grid is immutable. Any change becomes `comparison_grid_v2`.

## Freeze procedure

1. **DRAFT_PENDING_OWNER** (now). The builder currently lists 26 blockers (`freeze_procedure.blockers`;
   `--freeze-status` prints them).
2. The owner resolves every TBD level (value, source and evidence class) and decides every PROPOSED item (recorded as
   OWNER_DECIDED with a decision reference). The prerequisites must be at an owner-approved revision, and HALLREF must
   be verified.
3. Regenerate: `python scripts/architecture/build_comparison_grid.py --feed-envelope <feed_envelope_v1.json>
   --hall-reference <hall_reference_v1.json> --write`. Then `--freeze-status` must report 0 blockers.
4. **Hash-lock:** `--freeze --owner-decision REF --date YYYY-MM-DD` writes `comparison_grid_v1.lock.json` with the
   grid content sha256, the file sha256, the prerequisite sha256s and the decision reference. The builder refuses this
   while any blocker exists. The lock is committed before any comparison run.
5. Every comparison run records the locked grid hash and refuses a grid whose hash differs from the lock.
6. Later changes become v2 with their own freeze. `--write` refuses to overwrite v1 once the lock exists.

Reproduction: `--check-offline` rebuilds from the JSON's own `inputs` block (no prerequisites needed). `--check`
re-extracts from the prerequisite files, located by option, `$ABEP_FEED_ENVELOPE` / `$ABEP_HALL_REFERENCE`, or the
repository path. If a prerequisite is missing, the builder raises `PrerequisiteMissing`; if its structure changed, it
raises `PrerequisiteInvalid`. It never falls back to a guessed or default set.

## Milestones

- **milestone A (conditional selection): supported (structure).** One architecture-free point set and the fairness
  rules, so each condition in "X is baseline provided A/B/C are demonstrated" can name the base points where it must be
  shown. It needs no Hall number and not Physics Baseline 1.0. To make it a usable A deliverable: owner decisions on
  GQ-1…GQ-7 and on Hall reference Q1; numeric feed levels (feed-envelope design baseline; Xe flow-setpoint policy);
  numeric P_source and mixing levels; freeze and hash-lock.
- **milestone B (physics-backed selection): prerequisite only.** It needs the frozen grid with no TBD. It needs at
  least one ADMITTED transport closure (the credible set is empty today; gate 3 FAIL) with design Hall maps whose axes
  cover every base point without extrapolation. It needs chemistry for every mode's feed (O/O₂ is absent, and
  abep-n2n-0.11 is scoped to P5-N₂ validation), a solver path for pre-ionized inflow (Hall reference Q4), and
  common-boundary ledgers per point.
- **milestone C (proposal/PDR freeze): not supported.** It needs mission weighting of the base points (time fraction
  per altitude, solar level and mode over 26,000 h; start count for `xe_start`; TBD, requires the mission profile),
  orbit-resolved extremes if the owner adds them, and mass, thermal, life, cathode and start-up closures on the same
  frozen points.

## Open questions for the owner

- **GQ-1** Confirm the three feed modes. Is an explicit air-only anode level, distinct from `atmosphere_dominant`,
  wanted?
- **GQ-2** `xe_start` has one feed level, because IF-X2 is altitude-independent. Should start points be repeated per
  altitude and solar level? That would apply to all architectures.
- **GQ-3** Should the atmosphere-dominant node stay at zero Xe trim (proposed), or sit at a non-zero trim limit?
- **GQ-4** Should P_source be the whole arm-specific bus power (proposed) or the generator power only?
- **GQ-5** How many non-zero P_source levels, and which values? Should an "installed, unpowered" control level
  (XPROT SHAM controls; Hall reference Q2) be a grid level or stay in the protocol only?
- **GQ-6** Keep the Hall reference V_d set in `xe_start`, or set a separate Xe-start set that is still common to all
  architectures?
- **GQ-7** Does the RFP 1.5 kW ceiling apply at the `bus_power_boundary_v1` boundary?

## Referenced, not read (other lanes; resolved lazily or by path only)

`abep_sim/arch_boundary.py`, `abep_sim/arch_compare.py`, `docs/architecture_comparison/hard_gates/`,
`docs/architecture_comparison/experiment_protocol/`, `docs/architecture_comparison/minimum_decisive_experiment/`,
`schemas/controls/dual_feed_state_machine_v1.json`, `schemas/interfaces/upstream_icd_v1.json`. None is imported, and
the tests do not require any of them.
