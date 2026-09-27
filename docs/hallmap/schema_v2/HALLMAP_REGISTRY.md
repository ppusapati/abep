# Immutable Hall-map registry (DRAFT for owner review)

**Status: DRAFT_FOR_OWNER_REVIEW.** Lane `fo_hallmap_schema_v2_registry` (trigger `T_PIVOT_HALLMAP_SCHEMA_V2_REGISTRY`, owner
disposition `od_hardware_pivot`).

- Module: `abep_sim/hallmap_registry.py`. It is pure and not wired into `archengine`, `hall_map` or `thermal_life`.
- Record schema: `schemas/hallmap/hallmap_registry_v1.json`.
- Tests: `tests/test_hallmap_schema_v2_registry.py`. They use temporary synthetic fixtures and a monkeypatched admitted
  ensemble.

**No record exists and none can be created today.** The credible set is ∅ (2026-09-26), so `register()` refuses every
real member id. The screening candidates `sgb-screen-*` are refused by `hall_ensemble.require_admitted` (tested against
the real ensemble file).

## 1. Why

Two open questions in the repository ask for a map registry with file hashes:

- **Lane 15** (`abep_sim/thermal_life.py`, `docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md`, "Known limit"). `check_feasibility`
  cannot reopen the map file, so a hand-written `admitted_hallmap` record that names an admitted id would pass once
  members exist. The registry closes this. `lookup_map_meta(registry_dir, root, map_meta_sha256)` returns the **ACTIVE,
  fully re-verified** registration whose map meta has that canonical sha256. The canonical form is the one
  `thermal_life._canonical_sha256` writes (tested for equality). Wiring the call into `thermal_life` is a separate,
  owner-approved change and is not done here.
- **Lane 35** (`docs/hallmap/HALLMAP_PRODUCTION_SPEC.md` section 10, `x-consistency_rules`). The provenance embedded in a map
  is only as trustworthy as the file that carries it. The registry is an external, append-only anchor: it binds the map
  bytes and everything the map depends on, and it cross-checks the map's own `meta.provenance`.

## 2. Record (one JSON file per record; never edited or deleted)

A `REGISTRATION` binds the following by repository-relative path and sha256:

| block | bound item | check at registration and at every `verify()` |
|---|---|---|
| `map` | map file; `schema_version` (`hall_map_schema_v1`/`v2`); canonical `map_meta_sha256` | re-hash; `meta.schema`, `meta.ensemble_member_id`, `meta.hallthruster_commit` equal the record; `meta.facility_ingestion` false; `meta.provenance` present, `map_set.status = FROZEN`, convergence verdict `PASS`, `PROVENANCE_EQUALITIES` hold |
| `raw_records` | raw-record dataset: bytes sha256 and `sha256_canonical_jsonl` (decompressed for `.gz`, the frozen-dataset convention of `scripts/freeze_p5_n2_dataset.py`) | re-hash both; content sha equals `meta.provenance.raw_records.sha256_canonical_jsonl` |
| `ensemble_member` | admitted member id; ensemble file; ensemble sha256 **at registration** | `hall_ensemble.require_admitted` on the current ensemble (screening and unknown ids refused) |
| `chemistry` | config id + file + sha256 (or `builtin-*` with null file) | re-hash; equals `meta.provenance.chemistry.config_sha256` |
| `hallthruster` | commit; `PINNED.toml` sha256 **at registration** | commit equals the **current** `PINNED.toml` commit |
| `geometry`, `magnetic_field` | Vyovrinda design id + file + sha256 | re-hash; never a P5/ECHT evidence file name (the pattern of `hallmap_provenance_v1.json`) |
| `convergence_prereg` | frozen pre-registration id + file + sha256 | re-hash; never a DRAFT |
| `o4_dispositions` | file + sha256 | re-hash; equals the member's admission `o4_dispositions_file` / `_sha256` |
| `admission_decision` | file + sha256 | re-hash; equals the member's admission `decision_file` / `decision_sha256` |

A `WITHDRAWAL` names an earlier registration and binds an owner decision file by sha256. It is used, for example, when
new evidence eliminates the member. The withdrawn record itself is untouched.

**Immutability mechanics.**

- File name: `records/<seq:06d>_<first 16 hex of the record's sha256>.json`.
- Hash chain: `prev_record_sha256` is the sha256 of the previous record file (null for seq 1).
- Exclusive, atomic create: a fully written temporary file is made read-only and then `os.link`ed to the final name.
  The link fails if the name exists, and an existing sequence number is refused.
- `register()` and `withdraw()` refuse to append to a registry whose chain does not verify.
- The same map file cannot be registered twice.

**Integrity versus currency.** `verify()` never modifies anything and separates two kinds of problem:

- *Integrity problems* always fail `ok`: a bound file has changed or is missing, the chain or a file name is broken, or
  the provenance disagrees.
- *Currency problems* fail `ok` until a `WITHDRAWAL` retires the registration: the pin has moved, or the member is no
  longer admitted with the same decision and O4 record.

The ensemble file and `PINNED.toml` are living files (new members, reaction-set version bumps). Their hashes at
registration are therefore recorded as provenance but not re-hashed. What is re-checked is the admission itself and the
pinned commit. A **mutable** production chemistry TOML that is edited later makes the record fail integrity. That is
intended: register an immutable snapshot, as `hallthruster_bridge/audit/configs/` does for audits.

## 3. Milestones

- **A:** not needed. A conditional selection uses no map.
- **B / C:** this is the provenance precondition for using any admitted-member design map as decisive evidence. B and C
  still need everything in `HALLMAP_PRODUCTION_SPEC.md` section 2, which includes an admitted member (∅ today).
  Registering a map is not admission, not validation and not an architecture ranking. `rf_hall` and `ecr_hall` remain
  outside the map domain (spec section 0).

## 4. PROPOSED for the owner (not decided here)

1. **Registry location.** No location is hard-coded; `registry_dir` is an explicit argument. PROPOSED:
   `hallmaps/registry/`, next to the frozen map sets, and outside `hallthruster_bridge/` so the pinned pipeline is not
   touched.
2. **Who may append** and whether a registration needs a recorded owner decision file of its own. v1 binds the admission
   decision and the O4 dispositions but no separate "freeze this map" decision.
3. **Wiring:** have `thermal_life._check_wall_flux_provenance` call `lookup_map_meta` (closes lane 15's known limit), and
   have a future v2-aware `HallMap` refuse maps that are not ACTIVE in the registry. Both are model-pipeline changes.
4. **Currency policy after a pin move:** withdraw all registrations under the old pin, or keep them as historical with an
   explicit status (the current rule is withdraw).
5. **Registration only for FROZEN map sets with convergence PASS** (as implemented), or also CANDIDATE sets with a
   distinct status.

## 5. What this lane did not do

It did not touch `hallthruster_bridge/**`, the frozen P5-N₂ scripts, `hall_map.py`, `hall_ensemble.py`, `archengine.py`,
`thermal_life.py` or any running campaign. It created no record, map or physical value, and it ran no Julia and no full
test suite.
