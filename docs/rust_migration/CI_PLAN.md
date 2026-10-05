# Rust CI plan v2 (A9.24 item 8; A9.25 message 3)

**Status: `PROPOSED_PLAN_V2_FOR_OWNER_REVIEW`.** This file is a plan. It changes no workflow: `.github/workflows/ci.yml`,
`rust-parity.yml` and `julia-smoke.yml` are untouched. Each step below lands only with the implementation PR that admits the
subsystem it covers. Programme: `PROGRAMME.md`. Order: `migration_order_v2.json`. Inventory: `component_inventory_v2.json`.

What v2 changes from v1 (v1 is in Git history at `3d705d2`):

* The waves are renumbered to `migration_order_v2.json`.
* CI only ever covers class-A components and extract-and-parity kernels.
* The golden check is scoped to retained physics plus the post-bid active golden.
* A forbidden-identifier check enforces "LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust
  simulator".
* `bid_source_guard` protects the bid pair `5eee4b8` / `b5849af` and `mission_scenario_v2`.
* Class-H retirement gets a static import check.

Authority:

* A9.24 item 8, verbatim in substance: "Update rust-parity CI from v1 to the current v2 TPMC parity record. After that,
  extend Rust CI incrementally for every admitted subsystem." The item also lists the final CI contents and says "Do not
  change Kernel 1 physics while updating CI".
* A9.25 message 3, which sets the four classes and says parity applies only to retained selected-architecture physics.
* A9.14 S10.4 `OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`, which stays in force (`docs/ci/RUST_PARITY.md`).

## 0. Done: v1 → v2 re-point

`rust-parity.yml` already reads `parity_prereg_v2.json` / `parity_report_v2.json`. The re-point is commit `6e5465a`
(docs/HISTORY.md, "2026-10-04 — Optional Rust CI re-pointed to the parity v2 records"). `tests/test_rust_ci_workflow.py` checks
that the v1 records are immutable. Kernel 1 physics was not changed. No further action is needed for this part of item 8.

## 1. Principles

1. **Incremental.** Each admitted component adds its own CI job, or its own step group in a Rust workflow, in the same PR that
   flips it to `ADMITTED`. Nothing is added for components that are not admitted yet, except the shared `cargo build` /
   `cargo test` once a workspace exists.
2. **Fail closed on unrecorded changes** (RUSTCI-1, generalised).
   * For each admitted component, CI compares the Rust provenance sources with `build_provenance.source_sha256` in its parity
     report. A difference fails with `UNRECORDED_SOURCE_CHANGE` unless a new contract version is scored.
   * Push and PR runs **never spend a scoring seed**.
   * Scoring runs only through `workflow_dispatch` with an explicit input, in one global concurrency group per contract, and
     is never cancelled.
3. **Reference binding.** While the Python reference is active, CI refuses a changed reference file with
   `REFUSED_REFERENCE_CHANGED`, as `rust-parity.yml` does today.
4. **Normal CI needs no optional toolchain until that toolchain is required.** Today `ci.yml` needs no Rust (S10.4). Once the
   first non-Kernel-1 component is admitted, the Rust jobs become **required** status checks. That PR also updates
   `docs/ci/BRANCH_PROTECTION.md`.
5. **CI never rewrites references.** Golden, fixture and captured-reference checks are read-only. The working-tree-unchanged
   guard in `ci.yml` is kept, and every Rust job gets the same guard.
6. **No obsolete architecture in the Rust tree (new, RM-R23).** A forbidden-identifier scan of `crates/**` fails on any of:
   * `LaB6Cathode`, `lab6_xe`, `cathode_life`, `XE_CATHODE`, `hall_1stage`;
   * `mw_air`, `rf_cathode`;
   * `keeper` / `heater` used as a load or component name;
   * `CONTROL_FALLBACK`;
   * the archengine family names.

   Two places are allow-listed. One is the refusal-guard vocabulary of the A9.19 architecture rules (`abep-design`), which must
   *recognise* hollow-cathode text in order to refuse it. The other is quoted provenance strings in labelled history fields.
   Any new occurrence fails.
7. **Classification gate (new, RM-R19).** `abep parity check` refuses (`REFUSED_CLASSIFICATION`) any contract whose
   component is not class A or an extract-and-parity kernel. A class-G contract passes only with a recorded active-toolchain
   requirement.

## 2. Per-admitted-component CI increment (template)

The new workflow is `rust-ci.yml`, or one job per wave, appended when a component is admitted. Every admitted component gets
these steps:

| step | what it does | phase |
|---|---|---|
| toolchain pin | `rustup toolchain install` the version in `rust-toolchain.toml`, which must equal the contract report's `build_provenance.rustc` | always |
| `cargo build --locked --workspace` | builds the component | always |
| `cargo test --locked -p <crate>` | unit tests, including the contract's domain/error parity cases (`DE-xx`) | always |
| determinism | runs the registered vectors twice with the development seed, and with the same input in two processes (`--threads 1` and default); outputs must be bitwise identical | always |
| record check | `abep parity check <contract>`: re-derives the report's verdicts, counts and MD from its JSON, binds source sha256 values, applies the classification gate, refuses an unrecorded change | always |
| Python-reference parity (development) | while the Python reference is active, runs the contract's comparison with `development_master_seed`; **not scored and not a verdict** | while the component is not `PYTHON_RETIRED_FROM_ACTIVE` |
| captured-reference parity | compares Rust outputs with `contracts/<id>/reference_outputs/` (sha256 manifest) under the contract's tolerance classes, so parity stays checked after Python is retired | always after admission |
| conservation | the contract's `CONS-xx` checks on the Rust outputs | when applicable |
| config/hash | `abep config verify`: `config/MANIFEST.json`, the architecture, model-set and design-state-set hashes equal the contract's `governing_hashes` | when applicable |
| schema | Rust outputs validate against the named `schemas/**`; record types match the schema field sets | when applicable |
| golden / reference | `abep golden check` over the golden cases the component's retained physics reproduces (see below), against the **unchanged** `golden_v2.json`, and over the post-bid active `hall_icp_neutralizer` golden once it exists (P-02) | from the wave that admits the golden's dependencies |
| forbidden identifiers | principle 6 | always |
| scoring (dispatch only) | the full pre-registered campaign with the scoring seed, report upload and re-admission gate | `workflow_dispatch` input only |

**Golden scope (v2).**

* **The Rust golden check reproduces:**
  * `atmosphere` (W1E);
  * `intake` (W1);
  * `gas_path` (W2, `K-GASPATH`);
  * the upstream / AO keys of `hall_icp_neutralizer_reference` (W2, `K-GASPATH` + `K-GAS-LIFE`);
  * the gas-path refusal part of `nonconverged_reference` (W2 domain/error parity).
* **The historical cases are not reproduced by Rust:** `architecture_closure`, `mission`, `hall`, `source_plasma`,
  `accelerators`, `design_point_selection` and the rest of `nonconverged_reference`.
  * They are class H / AFI-04 `HISTORICAL_REGRESSION_COMPATIBILITY`.
  * The owner labels `accelerators` LEGACY / NOT CURRENT FLIGHT CANONICAL.
  * While Python CI exists, they stay checked by `python -m abep_sim.golden check` (CLAUDE.md rule 2).
  * At the end state they are reproduced from the historical reference environment (RM-OQ-06).
* `golden_v2.json` is never regenerated, and no Rust result is ever written into it.

### Wave-specific additions (waves of `migration_order_v2.json`)

| wave | extra CI content |
|---|---|
| W0 (Kernel 1) | the existing `rust-parity.yml`, unchanged. A workspace path-dependency use of `abep_core` adds a **build-equivalence** step: K1–K5 on the registered vectors with the development seed, bitwise against the recorded extension, run as a contract addendum |
| W1E / W1 | frozen-data readers: sha256 of `atmosphere_msis21_v1.*`, `intake_surface_v1.*` and the 196-state design-state set v2 against `config/MANIFEST.json` / the rule-1 provenance. The intake response surface is reproduced against `intake_surface_v1` (statistical or exact class as contracted). The `atmosphere` and `intake` golden cases |
| W2 | gas-path convergence and domain cases: `test_gaspath_convergence_g03_g05.py` and `test_compressor_gaede_domain_mcc02.py` become cargo tests through captured references. `K-GASPATH` and `K-GAS-LIFE` golden keys. A harness-independence check that the Python reference path through `Config("hall_1stage")` reads no card field (RM-R20) |
| W3 | mission propagation: orbit and eclipse invariants, energy balance (`mission_env` only) |
| W4 | F8 / F7: the RNG self-test of the class chosen in RM-OQ-03 (for `EXACT_STREAM`, numpy PCG64 / SeedSequence vectors captured from numpy 2.4.4); the F7 / F8 study outputs, with the empty robust upstream set, as captured references |
| W5 | P3 view factors: reciprocity and enclosure-sum invariants at `RES_VERIFY`; source identity with the profiled function |
| W6 | HWM14 executable build and run smoke (the existing Fortran path, now launched by Rust) |
| W7 | rate-table builders reproduce `abep_sim/data/rates/` and `hallthruster_bridge/propellants/*.dat` byte-identically; `rate_validity.toml` coverage moves from `ci_checks.py` |
| W8 | the Julia bridge (§ 4); O4 / facility pipeline record checks; the `HallMap` pin and schema checks |
| W9–W11 | conservation gate (rule 4) on every closure output. W11 adds the mass roll-up rules (`K-MASS-RULES`) against the committed v4 / v5 records. The **class-F** mass record (`mass_power_a9_v5`) gets **no Rust CI** until AFI-02-RA1 creates its corrected successor |
| W12 | assessment and hard gates: the raw-physics vs assessment split (A9.22; A9.24 items 3–5) is checked as a crate-graph test, so physics crates cannot depend on `abep-assess`. HC-12 stays `NOT_EVALUATED`. HC-05 uses `M_n,LB > 0` and is `NOT_EVALUATED` without uncertainty evidence |
| W13 | `abep config build --check` reproduces `config/**` and `MANIFEST.json` byte-identically. `mission_scenario_v2` is verified against its frozen pin, never rebuilt |
| W15 | per class-A builder, `abep build <id> --check` must give byte-identical committed outputs. Class-H builders get no Rust job |
| W16 | the `scripts/ci_checks.py` checks are ported one by one to `abep ci <check>`. Each is run once against both implementations and must give identical pass / fail on a seeded set of corrupted trees; then the Python check is retired. `h2_6_live_sources` depends on the class-G H2-6 builder: RM-OQ-09 decides whether `verify_sources()` is ported or the check retires |
| W17 | the end-state jobs of § 5 |

## 3. `bid_source_guard` (PROGRAMME.md § 5)

The first implementation PR adds this check: `ci_checks.py --only bid_source_guard`, later `abep ci bid-source-guard`. It
**protects the pair**:

* technical source `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b`;
* package / freeze record `b5849affae22a6709ad217a184f6fe896d15410a`.

The pair is named by A9.25 message 8 and again by A9.27. The package lineage after the freeze record is recorded in the
manifest. Today that is `2de86ab` (A9.27): a package-level post-source bid-text update that still pins `5eee4b8`, whose
authorising decision record marks `package_level_post_source_allowed`.

It fails in any of these cases:

* a `docs/bid/**` file differs from its bytes in the recorded package lineage (`b5849af`, then `2de86ab`), and no new owner
  decision record or re-freeze names it;
* `docs/bid/bid_technical_baseline_v2.json` does not pin `5eee4b8` as `bid_technical_source.commit`;
* a bid-cited file read with `git show 5eee4b8:<path>` differs from `docs/bid/bid_source_manifest_v1.json`;
* the package builder is run against a tree other than the technical source;
* `config/mission/mission_scenario_v2.json` differs from its frozen sha256 `885b1f70a1a44389e088837fd37bb79390b63132e3c81f17923103b2f9b5fc49`.
  A semantic change must be a new `mission_scenario_v3`, and v2 stays byte-identical;
* bid-cited evidence carries `implementation: rust`.

It runs in normal CI.

## 4. Julia bridge compatibility (W8)

* **Now.** `julia-smoke.yml` runs Python for pin extraction, then Julia `check_pin()`, then the campaign smoke.
* **After W8** (the `abep-julia-bridge` admission), a Rust-driven job replaces the inline Python:
  * `abep hall pin-check` parses `PINNED.toml` / `Manifest.toml`. It checks that the commit is `bfb3019f…` and that the Julia
    version equals the manifest's, then calls Julia `check_pin()`.
  * `abep hall smoke` runs the same campaign smoke command through the Rust launcher. Launch equivalence must hold against the
    Python-launched job (argv, env allow-list, input bytes), and the run records must be byte-identical for as long as both
    jobs exist.
  * `abep hall schema-check` checks that the Hall-map record types equal the `hall_map_schema_v1.json` field set, and that a
    non-pinned commit is rejected.
  * Every run writes an execution-provenance sidecar (Julia version, HallThruster commit, threads / BLAS).
* The Julia steps themselves are unchanged. The pin is never moved automatically (`PINNED.toml` `upgrade_policy`).
* The executed campaign runner scripts (`docs/orchestration/runner_scripts/*.sh`) are class H and get no Rust job.

## 5. Final CI (end state, item 8 list → item 14 checks)

| item-8 requirement | final CI job | item-14 link |
|---|---|---|
| cargo build/test | `cargo build --locked --workspace` + `cargo test --locked --workspace`, including the Rust equivalent of the rule-9 outcome contract (RM-OQ-05) | E1 |
| deterministic output | double-run bitwise check over all registered vectors and CLI end-to-end runs | E1, E2 |
| Python-reference parity while the reference is active | per-component development parity jobs, removed component by component at `PYTHON_RETIRED_FROM_ACTIVE` | E7 |
| Julia Hall bridge compatibility | `abep hall pin-check` / `smoke` / `schema-check` | E8 |
| conservation | rule-4 gates on the active closure and design outputs | E1 |
| config/hash validation | `abep config build --check`, `abep config verify`, prereg locks, audit `MANIFEST.json`, validation-release links, `bid_source_guard` | E3, E9 |
| schema compatibility | every output validated against `schemas/**`; Hall-map schema | E4, E9 |
| golden/reference cases | `abep golden check` (unchanged `golden_v2.json`, retained-physics cases) + the active `hall_icp_neutralizer` golden + captured-reference parity for every admitted component | E2, E4, E5 |
| no forbidden Python runtime dependency after final migration | see below | E1, E6, E10 |

**"No forbidden Python runtime dependency" check (end state).** It has four parts.

1. **Python-free runner.** The simulator jobs run in a container image with no `python3` / `python` / `pip` on PATH (assert
   `! command -v python3`). They run the `abep` CLI end to end over the active chain: design synthesis, sweep, golden check,
   config check, every `abep build --check`, `abep ci` and the Julia smoke. HallThruster.jl's own Julia dependencies are
   allowed. Any Python they might pull in through Julia packages (for example PyCall) is checked absent in `Manifest.toml`.
2. **Static scan.**
   * Workflow files for the simulator contain no `setup-python`, `python`, `pip` or `pytest` steps.
   * Rust sources contain no `Command::new("python…")`.
   * `cargo tree` of the workspace contains no `pyo3`, because `abep_core`'s `python` feature is retired at W17.
   * Shell runners under active paths do not invoke Python.
   * The forbidden-identifier scan (§ 1, principle 6) is green.
3. **Retirement completeness (class H / G).**
   * No active build, test or workflow path imports or runs a class-H module or an unrequired class-G module. The check is a
     static import scan against `component_inventory_v2.json` and its end-state re-run.
   * Historical reproducibility, such as the historical golden cases, runs only in the separate historical-reference job,
     never in simulator CI (RM-OQ-06).
4. **Ledger completeness.**
   * In `docs/rust_migration/migration_state_v1.json`, every class-A component is `ADMITTED` + `PYTHON_RETIRED_FROM_ACTIVE`
     or `FORMALLY_RETIRED_NOT_PORTED`.
   * Every class-G / H component is `FORMALLY_RETIRED_NOT_PORTED`, or admitted under a recorded requirement.
   * No class-F component remains.
   * A re-run of the inventory at the end-state commit finds no active Python component outside the retired tag or directory.

Until the end state, `ci.yml` (Python) stays the required CI. Rust jobs move from optional to required as § 1, principle 4,
describes.
