# Rust CI plan v1 (A9.24 item 8)

**Status: `PROPOSED_PLAN_POST_BID_FREEZE`.** This file is a plan. It changes no workflow. `.github/workflows/ci.yml`,
`rust-parity.yml` and `julia-smoke.yml` are untouched. Each step below lands only with the implementation PR that admits the
subsystem it covers. Programme: `PROGRAMME.md`. Order: `migration_order_v1.json`.

Authority:

* A9.24 item 8, verbatim in substance. "Update rust-parity CI from v1 to the current v2 TPMC parity record. After that,
  extend Rust CI incrementally for every admitted subsystem." The item also lists the final CI contents and says "Do not
  change Kernel 1 physics while updating CI".
* A9.14 S10.4 `OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`, which stays in force (`docs/ci/RUST_PARITY.md`).

## 0. Done: v1 → v2 re-point

`rust-parity.yml` already reads `parity_prereg_v2.json` / `parity_report_v2.json` (commit `6e5465a`; docs/HISTORY.md
"2026-10-04 — Optional Rust CI re-pointed to the parity v2 records"). `tests/test_rust_ci_workflow.py` checks that the
v1 records are immutable. Kernel 1 physics was not changed. No further action is needed for this part of item 8.

## 1. Principles

1. **Incremental.** Each admitted component adds its own CI job, or its own step group in a Rust workflow, in the same PR
   that flips it to `ADMITTED`. Nothing is added for components that are not admitted yet, except the shared `cargo build`
   / `cargo test` once a workspace exists.
2. **Fail-closed on unrecorded changes** (RUSTCI-1, generalised). For each admitted component, CI compares the Rust
   provenance sources with its parity report's `build_provenance.source_sha256`. A difference fails with
   `UNRECORDED_SOURCE_CHANGE` unless a new contract version is scored. Push and PR runs **never spend a scoring seed**.
   Scoring runs only through `workflow_dispatch` with an explicit input, in one global concurrency group per contract, and
   is never cancelled.
3. **Reference binding.** While the Python reference is active, CI refuses a changed reference file with
   `REFUSED_REFERENCE_CHANGED`, as `rust-parity.yml` does today.
4. **Normal CI never depends on an optional toolchain until that toolchain is required.** Today `ci.yml` needs no Rust (S10.4).
   Once the first non-Kernel-1 component is admitted, Rust becomes authoritative for production results and the Rust jobs
   become **required** status checks. That change needs a `docs/ci/BRANCH_PROTECTION.md` update in that PR.
5. **CI never rewrites references.** Golden, fixture and captured-reference checks are read-only. The working-tree-unchanged
   guard in `ci.yml` is kept, and every Rust job gets the same guard.

## 2. Per-admitted-subsystem CI increment (template)

The new workflow is `rust-ci.yml`, or one job per wave, appended when a component is admitted. Every admitted component
gets these steps:

| step | what it does | phase |
|---|---|---|
| toolchain pin | `rustup toolchain install` the version in `rust-toolchain.toml`, which must equal the contract report's `build_provenance.rustc` | always |
| `cargo build --locked --workspace` | builds the component | always |
| `cargo test --locked -p <crate>` | unit tests, including the domain/error parity cases in the contract (`DE-xx`) | always |
| determinism | runs the component's registered vectors twice with the development seed, and with the same input in two processes (`--threads 1` and default). Outputs must be bitwise identical (INV "deterministic seeding" in the template) | always |
| record check | `abep parity check <contract>`: re-derives the committed report's verdicts, counts and MD from its JSON, binds source sha256 values, and refuses an unrecorded change | always |
| Python-reference parity (development) | while the Python reference is active, runs the contract's comparison with `development_master_seed`. It is **not scored and not a verdict**, like `verify_abep_core.py --dev --strict` | while `PYTHON_REFERENCE` is not retired |
| captured-reference parity | compares Rust outputs with `contracts/<id>/reference_outputs/` (sha256 manifest) under the contract's tolerance classes. This is how parity stays checked after Python is retired | always after admission |
| conservation | the contract's `CONS-xx` checks on the Rust outputs | when applicable |
| config/hash | `abep config verify` checks that `config/MANIFEST.json` and the architecture, model-set and design-state-set hashes the component reads equal the contract's `governing_hashes` | when applicable |
| schema | Rust outputs validate against the `schemas/**` files named in the contract, and the record types match the schema field sets | when applicable |
| golden/reference | for golden-backed components, `abep golden check`, the Rust port of `python -m abep_sim.golden check`, must print OK against the **unchanged** `golden_v2.json` | from the wave that admits the golden's dependencies |
| scoring (dispatch only) | the full pre-registered campaign with the scoring seed, report upload, and a re-admission gate | `workflow_dispatch` input only |

### Wave-specific additions

| wave | extra CI content |
|---|---|
| W0 (Kernel 1) | the existing `rust-parity.yml`, unchanged. A workspace path-dependency use of `abep_core` adds a **build-equivalence** step: K1–K5 on the registered vectors with the development seed, bitwise against the recorded extension, run as a contract addendum |
| W1E / W1 | frozen-data readers: sha256 of `atmosphere_msis21_v1.*`, `intake_surface_v1.*` and the design-state sets checked against `config/MANIFEST.json` / the rule-1 provenance. The intake response surface is reproduced against `intake_surface_v1` (statistical or exact class as contracted) |
| W2 | gaspath convergence and domain cases (the existing `test_gaspath_convergence_g03_g05.py` and `test_compressor_gaede_domain_mcc02.py` become cargo tests through captured references) |
| W3 | mission propagation: orbit and eclipse invariants, energy balance |
| W4 | UQ: `EXACT_STREAM` RNG self-test (numpy PCG64 / SeedSequence vectors captured from numpy 2.4.4); paired-UQ fixtures `evaluate_identity_*` |
| W5 | P3 view factors: reciprocity and enclosure-sum invariants at `RES_VERIFY` |
| W6 | HWM14 executable build and run smoke (the existing Fortran path, now launched by Rust) |
| W7 | rate-table builders reproduce `abep_sim/data/rates/` and `hallthruster_bridge/propellants/*.dat` byte-identically. `rate_validity.toml` coverage moves from `ci_checks.py` |
| W8–W13 | conservation gate (rule 4) on every closure output; `golden check` coverage grows with each admitted dependency |
| W15–W16 | assessment and hard gates: the raw-physics vs assessment split (A9.22 / A9.24 items 3–5) is checked as a crate-graph test, so physics crates cannot depend on `abep-assess`. HC-12 stays `NOT_EVALUATED` |
| W17 | `abep config build --check` reproduces `config/**` and `MANIFEST.json` byte-identically (replacing `scripts/config/build_config.py` checks) |
| W18 | per builder, `abep build <id> --check` must give byte-identical committed outputs. W18a adds the Julia bridge (§ 4) |
| W19 | the `scripts/ci_checks.py` checks ported one by one to `abep ci <check>`, each run once against both implementations and required to give identical pass/fail results on a seeded set of corrupted trees (contract), then the Python check retired |

## 3. `bid_source_guard` (PROGRAMME.md § 4)

The first implementation PR adds a check, `ci_checks.py --only bid_source_guard` and later `abep ci bid-source-guard`. It
fails in three cases:

* bid-package inputs differ from `docs/bid/bid_source_manifest_v1.json` without an owner re-freeze record;
* bid-cited evidence carries `implementation: rust`;
* a Rust-authoritative component's files are cited by the bid package other than at the frozen versions.

It runs in normal CI.

## 4. Julia bridge compatibility

* **Now.** `julia-smoke.yml` runs Python for pin extraction, then Julia `check_pin()`, then the campaign smoke.
* **After W18a** (the `abep-julia-bridge` admission), a Rust-driven job replaces the inline Python:
  - `abep hall pin-check` parses `PINNED.toml` / `Manifest.toml`. It checks that the commit is `bfb3019f…` and that the
    Julia version equals the manifest's, then calls Julia `check_pin()`.
  - `abep hall smoke` runs the same campaign smoke command through the Rust launcher. The run records must be byte-identical
    to the records from the Python-launched job for the same inputs (launch equivalence: argv, env allow-list, input bytes),
    as long as both jobs exist.
  - `abep hall schema-check` checks that the Hall-map record types equal the `hall_map_schema_v1.json` field set, and that a
    non-pinned commit is rejected.
  - Every run writes an execution-provenance sidecar (Julia version, HallThruster commit, threads/BLAS).
* The Julia steps themselves (`Pkg.instantiate`, the pinned manifest) do not change. The pin is never moved automatically
  (`PINNED.toml` `upgrade_policy`).

## 5. Final CI (end state, item 8 list → item 14 checks)

| item-8 requirement | final CI job | item-14 link |
|---|---|---|
| cargo build/test | `cargo build --locked --workspace` + `cargo test --locked --workspace` (incl. the Rust equivalent of the rule-9 outcome contract, RM-OQ-05) | E1 |
| deterministic output | double-run bitwise check over all registered vectors and CLI end-to-end runs | E1, E2 |
| Python-reference parity while the reference is active | per-component development parity jobs, removed component by component at `PYTHON_RETIRED_FROM_ACTIVE` | E7 |
| Julia Hall bridge compatibility | `abep hall pin-check` / `smoke` / `schema-check` | E8 |
| conservation | rule-4 gates on closure, archengine and source outputs | E1 |
| config/hash validation | `abep config build --check`, `abep config verify`, prereg locks, audit `MANIFEST.json`, validation release links | E3, E9 |
| schema compatibility | every output validated against `schemas/**`; Hall-map schema | E4, E9 |
| golden/reference cases | `abep golden check` (unchanged `golden_v2.json`) plus captured-reference parity for every admitted component | E2, E4, E5 |
| no forbidden Python runtime dependency after final migration | see below | E1, E6, E10 |

**"No forbidden Python runtime dependency" check (end state).** It has three parts.

1. **Python-free runner.** The simulator jobs run in a container image with no `python3` / `python` / `pip` on PATH
   (assert `! command -v python3`). They run the `abep` CLI end to end: closure, sweep, golden check, config check, every
   `abep build --check`, `abep ci` and the Julia smoke. HallThruster.jl's own Julia dependencies are allowed. Any Python they
   might pull in through Julia packages (for example PyCall) is checked absent in `Manifest.toml`.
2. **Static scan.** Workflow files for the simulator contain no `setup-python`, `python`, `pip` or `pytest` steps. Rust
   sources contain no `Command::new("python…")`. The default `cargo tree` of the workspace contains no `pyo3`, because
   `abep_core`'s `python` feature is retired at W20. Shell runners under active paths do not invoke Python.
3. **Ledger completeness.** `docs/rust_migration/migration_state_v1.json` has every inventory component as `ADMITTED` +
   `PYTHON_RETIRED_FROM_ACTIVE` or `FORMALLY_RETIRED_NOT_PORTED`. A re-run of the inventory at the end-state commit finds no
   active Python component outside the retired tag or directory.

Until the end state, `ci.yml` (Python) stays the required CI. Rust jobs move from optional to required as § 1.4 describes.
