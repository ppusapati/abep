# Architecture comparison harness (`arch_compare_v1`)

Module: `abep_sim/arch_compare.py`. Tests: `tests/test_arch_compare.py`.
**Status (2026-09-26): not wired, refuses to run.** The transport ensemble has **zero admitted members**. The credible
set is ∅ and gate 3 is FAIL: in P5-N₂ v1, all nine SGB screening candidates were INCONCLUSIVE / NOT ELIGIBLE. So every
real invocation stops at the first gate with `NoAdmittedMembersError`, as it should:

```
$ python -m abep_sim.arch_compare status
REFUSED (NoAdmittedMembersError): architecture comparison refused: the transport ensemble has zero ADMITTED members ...
```

The harness is ready so that admitted Hall closures can be added later without more architecture-code work. It does not
show ABEP closure, it does not pick an architecture, and it admits no transport closure.

## 1. What it does

It compares the three Hall-accelerated architectures of the RFP chain, `hall_only`, `rf_hall` and `ecr_hall`, on
**one common electrical boundary**. It does this for **every admitted transport-ensemble member**, which is an unweighted
scenario set (CLAUDE.md next-work 1).

```
UpstreamState (computed ONCE; identical for every member and architecture)
  intake -> filter -> compressor -> gas chamber -> valve       (archengine.gas_path_state, or explicit numbers)
        |
        v   per architecture: ArchitectureSpec (member-independent design point, feed, loads, efficiencies)
  Hall-map query q_arch = design values + bound upstream/feed quantities      (same q for every member)
        |
        v   for EVERY admitted member m  (require_admitted(m) first)
  HallMap(m, arch)(q_arch) -> Hall block outputs (thrust, P_d, I_d, anode_eff, trust flags)
        |
        v
  loads = fixed loads (spec) + upstream loads (compressor) + Hall loads (discharge)
  ledger(arch, loads, efficiencies) -> {boundary_version, architecture, P_bus_W, items, residual_W}
        |   gate: |residual| < 2 % of P_bus (reported AND recomputed from items)
        v
  per-member metrics  ->  per-architecture min/max envelopes  +  min/max of paired per-member differences
```

The module is pure orchestration. It computes no physics, it does not import or modify `archengine` at module level
(only `upstream_from_archengine` imports it, lazily), and it leaves `hall_map`, `hall_ensemble` and the goldens alone.

## 2. Rules the harness enforces

| rule | mechanism | refusal |
|---|---|---|
| Admitted members only (CLAUDE.md next-work 1) | `admitted_members()` calls `hall_ensemble.require_admitted` for every member. Every `hall_maps` key and every map's `meta.ensemble_member_id` also goes through `require_admitted`. `HallMap` itself loads admitted ids only | `NoAdmittedMembersError`, `MemberRefusedError` |
| Zero admitted members means no run | refused before anything else is read or computed | `NoAdmittedMembersError` |
| All members, no subset | the `hall_maps` keys must cover every admitted member | `MemberRefusedError` |
| Unweighted scenario set | ensemble `weighting` must be `"unweighted"`. Output has min/max only: no mean, no probability, no weighting, and no field that names one architecture | `HarnessError` |
| Layer-1 calibration nuisance is never an axis | nuisance names are refused as Hall-map axes (`HallMap`), operating-point keys, bindings, feed or upstream quantities | `ScopeViolationError`, `HallMapRefusedError` |
| No upstream leak of Hall-closure uncertainty | `UpstreamState` is immutable, computed once, and fingerprinted (sha256). The fingerprint is re-checked after every member evaluation and recorded in every result. Hall-map output names are refused as upstream or feed quantities. The Hall query, fixed loads, efficiencies and feed are member-independent by construction | `ScopeViolationError` |
| Common electrical boundary | every ledger answer must carry `boundary_version == "bus_power_boundary_v1"`. Items must book exactly the supplied loads. The component set must be identical across members. `hall_only`'s components must be a subset of every other architecture's | `LedgerContractError` |
| Energy-ledger conservation (CLAUDE.md rule 4) | `abs(residual_W)/P_bus_W < 0.02` for the ledger-reported residual **and** for an independent recomputation (`P_bus_W − Σ items.P_bus_W`). `P_bus_W` must be ≥ the delivered load. Both residuals are reported per result | `LedgerResidualError` |
| Source mass closure (rule 4), when declared | `Σ supply = Σ Hall-map mass axes + Σ other sinks` to rounding (relative 1e-9). A spec without a declaration reports `{"declared": false}` | `SpecError` |
| No silent fallback (rule 3) | missing ledger module, wrong boundary version, a map query outside the axes, an untrustworthy point, or a Hall-block bound violated: each is refused or reported with a status, never replaced | see §4 |
| Flight maps only | `meta.facility_ingestion` must be `false` (hall_map_schema_v1: "flight (space) maps must be false") | `HallMapRefusedError` |
| One chemistry basis per comparison | all maps in one run carry the same `meta.reaction_set` | `HallMapRefusedError` |
| Provenance | maps are given as file paths and `HallMap` is built by the harness. Each map's sha256 is recorded, and verified when an index records it. Upstream and specs need a non-empty `source` | `HallMapRefusedError`, `SpecError` |

## 3. Inputs

### 3.1 `UpstreamState` (member-independent)
- `quantities`: finite numbers, read-only after construction. From `UpstreamState.from_gas_path(gas, source)` on an
  `archengine.gas_path_state(...)` dict (`mdot_air` kg/s, `p_in` Pa, `fO`/`fN2`/`fO2`, `comp_power` W, …). Or use
  `upstream_from_archengine(area_m2=…, alpha=…, L_over_d=…, alt_km=…, solar=…, blade_coating_um=…, p_target_Pa=… |
  p_margin_over_pmin=…)`, which has no defaults: the caller names the design point. `comp_power` is the drag-compressor
  electrical input `P_el_W` (`abep_sim/compressor.py`, via `system.evaluate`). This is the load plane the boundary
  defines for `compressor`.
- `labels`: strings, for example the frozen-atmosphere scenario id. Values of any other type are refused, never dropped.
- `drag_N` + `drag_source`: optional spacecraft drag at the same atmospheric state (e.g. `mission_env.spacecraft_drag`).
  Without it, the thrust-minus-drag metrics are simply absent.
- `source`: required provenance string.

### 3.2 `ArchitectureSpec` (one per architecture, member-independent)
| field | meaning |
|---|---|
| `arch` | `hall_only` \| `rf_hall` \| `ecr_hall` |
| `hall_operating_point` | design values of Hall-map axes (e.g. discharge voltage) |
| `hall_axis_bindings` | Hall-map axis → quantity name in `upstream.quantities` or `feed` (e.g. anode mass flow) |
| `feed` | architecture-specific member-independent quantities upstream of the Hall channel: the Xe-path flow, a pre-ionizer output, a cathode flow split. Names must not repeat upstream names |
| `fixed_loads_W` | every ledger component not supplied by the Hall map or the upstream state |
| `efficiencies` | bus-to-load efficiency in (0, 1] for every ledger component. There are no defaults anywhere |
| `hall_load_fields` | ledger component → hall_map_schema_v1 power field (unit W). Default naming `{"hall_discharge": "discharge_power_W"}` |
| `upstream_load_fields` | ledger component → upstream quantity. Default naming `{"compressor": "comp_power"}` |
| `mass_closure` | optional `{"supply": [...], "hall_axes": [...], "other_sinks": [...]}` |
| `source` | provenance of every number in the spec |

Every Hall-map axis must get exactly one value, either a design value or a binding. Extra keys are refused.

### 3.3 Hall maps
`hall_maps = {member_id: {arch: path | {"path", "sha256"}}}`, one `HallMap` per (admitted member, architecture). Maps
built for architectures that are not in the specs are listed in `maps_not_used`. The production input is an index file
(`load_hall_map_index`):

```json
{"schema": "arch_compare_hall_map_index_v1",
 "members": {"<ensemble_member_id>": {
     "admission_decision_sha256": "<decision_sha256 of that member's admission record>",
     "maps": {"hall_only": {"path": "relative/to/index.json", "sha256": "<hex>"},
              "rf_hall":   {"path": "...", "sha256": "..."},
              "ecr_hall":  {"path": "...", "sha256": "..."}}}}}
```

`admission_decision_sha256` has to equal the `decision_sha256` in the member's admission record, which ties the map set
to that admission. Every map sha256 is checked when the map is loaded.

### 3.4 Ledger
`ledger(arch, loads, efficiencies) -> dict`, with exactly these parameter names. When no ledger is injected, the harness
imports `abep_sim.arch_boundary.bus_power_ledger` **at call time** and requires `BOUNDARY_VERSION ==
"bus_power_boundary_v1"`. That module is built in a separate lane and is not in this branch. If it is missing, the
result is `LedgerUnavailableError`, never a substitute. The default component names used here (`hall_discharge`,
`compressor`) follow that boundary. On 2026-09-26 an uncommitted run of this harness against the separate lane's working
copy produced COMPLETE envelopes for all three architectures with synthetic inputs, and a spec with a missing component
was refused. **Re-verify after both are merged.**

### 3.5 Ensemble
Default: `hall_ensemble.load_ensemble()`, which runs the full admission verification: decision/scores sha256 and O4
dispositions. An injected ensemble mapping is for tests only. It is recorded as `ensemble.origin = "injected"` and makes
`production_path` false.

## 4. Outputs

`compare_architectures(...)` returns a JSON-serializable dict. `python -m abep_sim.arch_compare run` writes it and never
overwrites an existing file.

| key | content |
|---|---|
| `members`, `member_set`, `weighting` | all admitted ids; `"unweighted"` |
| `ensemble`, `ledger_resolution`, `production_path` | origin/sha256 of the ensemble and ledger. `production_path` is true only for the frozen ensemble file and the module ledger |
| `upstream` | quantities, labels, source, drag, `fingerprint` |
| `specs`, `hall_queries`, `mass_closure` | the member-independent design inputs and the one Hall query per architecture |
| `results[member][arch]` | `status`, `reason`, `hall_query`, `hall_map` (path, sha256, transport, reaction_set, commit, axes), `upstream_fingerprint`; plus, when OK: `hall` (full `HallMap` output), `trust`, `member_independent_loads_W`, `hall_loads_W`, `efficiencies`, `bus_ledger` (ledger answer, reported and recomputed residual, gate), `metrics`, `rfp_flags` |
| `envelopes[arch]` | `status` COMPLETE/INCOMPLETE, `n_members`, `status_counts`, `not_ok_members`, `metrics.{k}.{min,max}`, `constraint_robustness.{flag}.{n_true, n_members, holds_for_all_members}` |
| `paired_differences["a_minus_b"]` | min/max over members of the per-member difference, same member and same upstream on both sides |
| `ledger_residual_gate_frac`, `rfp_limits` | 0.02 and the RFP limits used for the flags |

Per-point statuses:
- `OK`
- `OUT_OF_MAP_DOMAIN`: the query is outside the map axes; there is no extrapolation.
- `UNTRUSTWORTHY_HALL_POINT`: `HallMap` `trustworthy` is false (unconverged, not sustained, or chemistry outside its
  validity domain). **No numbers are reported** for it.
- `MODEL_ERROR`: non-finite values, thrust < 0, P_d ≤ 0, or `anode_eff` ∉ [0, 1]. The anode jet power T²/(2ṁ_a) =
  `anode_eff`·P_d cannot exceed P_d.

An envelope is COMPLETE only when **every** admitted member is OK. Otherwise it is INCOMPLETE and carries no numbers,
because an envelope over a subset of members is never reported.

Metrics per OK point: `thrust_mN`, `discharge_power_W`, `discharge_current_A`, `anode_eff`, `anode_jet_power_W`, `P_bus_W`,
`thrust_per_P_bus_mN_per_kW`, `bus_to_anode_jet_efficiency`, and with drag also `thrust_minus_drag_mN` and
`thrust_to_drag`. Flags: `thrust_within_rfp_range`, `P_bus_within_rfp_cap`, and `thrust_exceeds_drag`.

## 5. Numbers in the harness and their classes

The harness ships **no physical numbers**: no loads, no efficiencies, no operating points, no geometry. The constants it
does carry are listed here.

| constant | value | class / source |
|---|---|---|
| `LEDGER_RESIDUAL_MAX_FRAC` | 0.02 (strict `<`) | project rule, CLAUDE.md rule 4 ("architecture energy ledger residual < 2 %"). `archengine.close_architecture` rejects `abs(resid) > 0.02`, so it lets exactly 2 % through. The harness follows the rule text |
| RFP thrust range / power cap | `abep_sim.constants.RFP` (thrust 12–25 mN, power 1500 W) | RFP DTDF/06/13516 Part III Para 2 as encoded in `constants.py`. Comparisons are inclusive, the same as `archengine.close_architecture`. CLAUDE.md summarises the power limit as "< 1.5 kW"; the exact-boundary case is the owner's call |
| `MASS_CLOSURE_REL_TOL` | 1e-9 relative | assumed numerical rounding tolerance of this harness, not physics |
| axis-domain tolerance | 1e-12 | same absolute tolerance as `HallMap.__call__` |

Every load and efficiency a caller supplies is **TBD — requires a sourced value per component** (evidence level, quantity
type, uncertainty, applicability; docs/EVIDENCE.md). The spec's `source` string is recorded, but the harness cannot judge
its evidence quality.

## 6. Drop-in procedure (after members are admitted)

1. **Admission record.** A screening candidate becomes a member only through the existing path: it is PROMOTABLE in a
   pre-registered campaign, it has an admission record (`ensemble/admission_record_schema_v1.json`) in
   `transport_ensemble_v0.json`, and it has O4 dispositions (`ensemble/o4_dispositions_schema_v1.json`, checked by
   `hall_ensemble._check_o4`). The harness plays no part in this and cannot bypass it.
   `python -m abep_sim.arch_compare status` must then list the member(s).
2. **Update the tripwire.** `tests/test_arch_compare.py::test_refuses_zero_admitted_members_against_the_real_ensemble`
   asserts that the real credible set is empty. Change it deliberately in the same PR that admits the first member.
3. **Design Hall maps per member.** Generate them with the pinned HallThruster.jl (`hallthruster_bridge/run_cases.jl`),
   one map set per admitted member, on Vyovrinda's own geometry and B(z), for each architecture's inlet condition. Each
   map must be hall_map_schema_v1 complete, carry `meta.ensemble_member_id`, set `facility_ingestion = false`, use one
   reaction set for all maps, and have axes that exclude every layer-1 nuisance variable. `HallMap(path)` must load each
   one against the frozen ensemble.
4. **Index.** Write an `arch_compare_hall_map_index_v1` file (§3.3) with each map's sha256 and each member's
   `admission_decision_sha256`.
5. **Upstream.** Run `python -m abep_sim.arch_compare upstream --area-m2 … --alpha … --L-over-d … --alt-km … --solar … --blade-coating-um … (--p-target-Pa …|--p-margin-over-pmin …) --out upstream.json`
   (about 17 s on this container), or write an `arch_compare_upstream_v1` file with sourced numbers:
   `{"schema": "arch_compare_upstream_v1", "quantities": {...}, "labels": {...}, "source": "...", "drag_N": ..., "drag_source": ...}`.
6. **Specs.** Write an `arch_compare_specs_v1` file: `{"schema": "arch_compare_specs_v1", "specs": [ {ArchitectureSpec fields} ]}`.
   Every load and efficiency needs a source (§5), and the ledger component set must match `bus_power_boundary_v1`.
7. **Ledger.** Make sure `abep_sim/arch_boundary.py` (`BOUNDARY_VERSION = "bus_power_boundary_v1"`) is merged.
8. **Run.** `python -m abep_sim.arch_compare run --specs specs.json --upstream upstream.json --maps index.json --out result.json`.
   Check that `production_path` is true, that every envelope is COMPLETE (otherwise read `not_ok_members`), and that the
   residuals are small. Report envelopes and member robustness only, never one architecture as the answer.
9. **Wiring.** Wiring `archengine`'s Hall branch to `HallMap` (CLAUDE.md next-work 5) is a separate model change: goldens
   move and HISTORY.md is updated. The harness does not need it and does not do it.

## 7. What is still missing

| item | status |
|---|---|
| Admitted transport members | **none**. Credible set ∅; P5-N₂ v1 gave all nine INCONCLUSIVE / NOT ELIGIBLE. O4 staged sensitivities and facility runs are pending, and admission also needs O4 dispositions |
| Design-specific Hall maps (Vyovrinda geometry, B(z)) | none exist. TBD — requires admitted members, and the design geometry and B(z) with sources (CLAUDE.md rule 6) |
| Air (O/O₂/N₂/N) chemistry for intake-delivered mixtures | not available. Only the N₂/N set exists (`abep-n2n-0.11`, `COMPLETE_FOR_P5_N2_VALIDATION`). O₂/O chemistry is next-work 4 ("only if 1–3 succeed"). Until it exists, no air-fed design map can be `chemistry_trustworthy` |
| Pre-ionized inlet condition for `rf_hall` / `ecr_hall` maps | TBD — requires (a) Hall maps generated with a pre-ionized inflow. Whether HallThruster.jl v0.23.1 supports an ion-inflow anode condition is **not established here — verify**. It also requires (b) a pre-ionizer model supplying the member-independent `feed` quantities. `plasma_chem.py` still uses unverified Arrhenius rates (next-work 6), so its output is not report-grade |
| Inlet condition / design identity in map meta | hall_map_schema_v1 has no field declaring the inlet condition (neutral vs pre-ionized) or the design geometry, so the harness cannot check them. It relies on the index's per-architecture assignment. **DRAFT for the owner only** (not implemented, and the schema is outside this lane): add `meta.inlet_condition` and `meta.design_id` in a future schema version |
| Bus-power boundary module | separate lane (`abep_sim/arch_boundary.py`, `bus_power_boundary_v1`); not in this branch |
| Sourced loads and efficiencies | TBD — requires one sourced value per component per architecture (magnet, keeper, heater, flow control, thermal control, housekeeping, RF/ECR source and magnet) |
| Load-dependent converter efficiency | not modelled. Efficiencies are fixed per architecture, so they are the same for every member, even though a discharge-converter efficiency at the member's P_d could differ inside the Hall block (which is in scope). TBD — requires a sourced converter map (e.g. `abep_sim.ppu`) |
| Member-dependent loads other than the Hall-map power fields | not supported in v1. For example, a keeper power that tracks I_d |
| Mass, thermal, life/erosion, mission propagation | not in the harness. Life needs `wall_life_trustworthy` maps. Mass and thermal stay with `archengine` / `mass_bom` / `thermal` |
| Design search | the harness evaluates one fixed design per architecture across all members. A per-member optimum would make the design member-dependent. Robust design search means calling the harness once per candidate design |
| Mass closure | checked only when a spec declares it, because map mass-axis names are not standardized in hall_map_schema_v1 |

## 8. Tests (`tests/test_arch_compare.py`)
All providers in the tests are TEST-ONLY synthetic: ensemble ids `TEST-ONLY-member-*`, Hall maps written to `tmp_path`
and loaded through the real `HallMap`, a bus ledger, loads, efficiencies and upstream numbers. None of them ships with
the module, and a test checks that the module source contains none of them. The tests cover:
- refusal with zero admitted members against the **real** ensemble file (tripwire), via the CLI `status` command, and on
  a synthetic empty set;
- refusal of every screening-candidate id, both as a `hall_maps` key and as a map's `meta.ensemble_member_id`, plus
  unknown ids, maps filed under the wrong member, and missing members;
- a missing or wrong-version ledger module (lazy resolution, no substitute) and the ledger signature;
- envelope min/max over all members recomputed independently, constraint-robustness counts, paired differences, and
  member-independence of the upstream fingerprint, the Hall query and the non-Hall loads;
- no winner, ranking, mean or probability keys in the output;
- UNTRUSTWORTHY and OUT_OF_MAP_DOMAIN points giving INCOMPLETE envelopes with no numbers;
- the ledger residual gate (reported and recomputed), the contract checks, and the boundary version;
- nuisance and upstream-leak guards, facility maps, reaction-set uniformity, axis coverage, and mass closure;
- the index file binding maps to the admission record and to map sha256s.

Run: `python -m pytest -q tests/test_arch_compare.py`. It adds no skips or xfails.
