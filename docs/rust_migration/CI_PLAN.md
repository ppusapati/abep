# Rust CI plan v3.1 (A9.24 item 8; A9.25 message 3; A9.28; A9.29)

**Status: `PLAN_V3_1_A9_29_RULINGS_APPLIED`.** This file is a plan. It changes no workflow: `.github/workflows/ci.yml`,
`rust-parity.yml` and `julia-smoke.yml` are untouched. Each step below lands only with the implementation PR that admits the
subsystem it covers.

* Programme: `PROGRAMME.md`.
* Order: `migration_order_v3_1.json`.
* Inventory: `component_inventory_v3_1.json`.
* Contract template: `parity_contract_template_v3_1.json`.
* Layer work packages and exit criteria: `SIMULATION_COMPLETION_PROGRAMME.md`.

**What changed from v3 (A9.29, 2026-10-05)** (v3 is in Git history at `1236f91`):

* **Rust-era test rule (sec. 9, RM-OQ-05).** Normal active CI runs `cargo test --workspace --locked`, and every active
  test passes. No ordinary active test is silently ignored or skipped. Missing evidence is asserted as the fail-closed
  status, and the empty Hall credible transport set is asserted explicitly. Platform / hardware tests live in a
  registered test class (§ 7). The Python 5 skips / 1 strict xfail are archive-era reproduction metadata.
* **Ground-test isolation (sec. 1).** `GROUND_TEST_PROGRAMME_ONLY` is OWNER_APPROVED. A `cargo metadata` check fails if
  any flight-runtime crate depends on `abep-groundtest` (principle 8, § 8).
* **`bid_source_guard` (sec. 3, RM-OQ-11).** `2de86ab` is the terminal owner-authorized package state; technical source
  `5eee4b8`; lineage `b5849af` → `2de86ab` (§ 3).
* **No DEFAULT_BACKEND flip (sec. 5).** The Rust intake calls `abep_core` directly as a normal Rust library.
  `rust-parity.yml` stays as it is.
* **Frozen atmosphere (sec. 6).** Normal CI verifies the frozen datasets. No HWM14 / NRLMSIS build runs in normal CI, and
  no Fortran FFI is on the critical path (W6 row).
* **RNG streams (sec. 7).** The W4 self-test covers the design / UQ `EXACT_STREAM`; TPMC keeps its statistical contract
  (W4 row).
* **Feed-state closure (sec. 2).** At cutover, normal CI verifies the frozen artifact, hash and schema, unless a successor
  record exists (GT row).
* **End state (secs. 8, 11).** The end-state checks add no `pip` / `virtualenv` / `PyO3` / `maturin`, and the Python
  final-reference archive (§ 5).
* **New-physics jobs (sec. 4).** `NP-ICP-NEUTRALIZER` gets principle-9 jobs, plus the assessment-separation check (W9
  row).

**What v3 changes from v2** (A9.28 messages 1 and 2; v2 is in Git history at `e01716d`):

* **Golden scope.** RM-OQ-06 is OWNER_DECIDED. golden_v1 / v2 are historical, immutable and reproducible from the
  historical Python environment. They are **not** Rust end-state parity cases. The Rust golden check runs the NEW
  active `hall_icp_neutralizer` golden, which is generated only from the admitted active chain (SC-WP-15). While Python
  CI exists, `python -m abep_sim.golden check` keeps running as today. CLAUDE.md rule 2 is unchanged until the separate
  CA-01 commit.
* **The H2-6 source check.** RM-OQ-09 is OWNER_DECIDED. Its check semantics move into the generic Rust provenance
  verifier (SC-WP-12). `ci_checks.py` `h2_6_live_sources` leaves active CI only after the verifier is admitted and
  normal CI is re-pointed.
* **New principles:**
  * 8: ground-test isolation;
  * 9: new-physics verification jobs, with no Python reference;
  * 10: value-status preservation.
* **The A9.28 protected bid record:** `bid_source_guard` protects `5eee4b8` / `2de86ab` (lineage `b5849af` → `2de86ab`).
* **The integration line.** Every Rust job runs on `integration/simulation-complete`. main receives one admitted
  baseline after the 18-item pre-PR checklist (§ 6).

What v2 changed from v1 (v1 is in Git history at `3d705d2`):

* The waves are renumbered to `migration_order_v2.json`.
* CI only ever covers class-A components and extract-and-parity kernels.
* The golden check is scoped to retained physics plus the post-bid active golden.
* A forbidden-identifier check enforces "LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust
  simulator".
* `bid_source_guard` protects the bid pair `5eee4b8` / `b5849af` and `mission_scenario_v2`.
* Class-H retirement gets a static import check.

Authority:

* A9.29 secs. 1-11 (`docs/decisions/OD_2026_10_05_A9_29_RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION.md`).
* A9.28 message 1 secs. 4-6 and message 2 secs. 7, 11-18 (goldens, new physics, H2-6, historical code, active golden,
  zero Python, main-merge policy, completion report).
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
   component is not class A or an extract-and-parity kernel. Two exceptions:
   * a class-G contract passes only with a recorded active-toolchain requirement;
   * a class-T (`GROUND_TEST_PROGRAMME_ONLY`) contract passes only with a migrating owner sub-disposition.
8. **Ground-test isolation (v3, RM-R30; OWNER_APPROVED A9.29 sec. 1).** A crate-graph check fails if any flight-runtime
   crate depends on `abep-groundtest`. The flight-runtime crates are the physics crates, `abep-julia-bridge`,
   `abep-design`, `abep-uq` and `abep-assess`. Class-T tooling (S1 / S1a gates, capability demo, hardware / instrumentation definitions) never runs in
   flight execution. The check reads `cargo metadata` (§ 8).
9. **New-physics verification jobs (v3, RM-R26).** A `NEW_PHYSICS` component, such as `NP-THERMAL-CATHODELESS`, has no
   Python-reference parity job. Its CI instead runs:
   * the preregistered analytic limiting cases;
   * the conservation checks;
   * the domain tests;
   * the independent-verification vectors.

   Each is bound to its prereg sha256. Outputs must carry `validation_status = NOT_VALIDATED` until measured evidence is
   registered. A Python scratch cross-check is never a CI dependency.
10. **Value-status preservation (v3, RM-R27).** For `mass_power_a9_v5` (and any record with provisional inputs), CI checks
    that the Rust output carries AL-07 = 6.0 kg with the committed labels and the A9.28 status
    `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT` / `AFI-02-RA1_OPEN`. Any CBE / measured / frozen label on it fails.
11. **Rust-era test rule (v3.1, RM-R39; A9.29 sec. 9).** § 7 gives the rule. It applies from the first `cargo test` of
    the workspace (ES-1).
12. **Separate RNG stream roles (v3.1, RM-R37; A9.29 sec. 7).** A contract's design / UQ sampling stream and its TPMC
    particle-tracing stream are checked separately (`parity_contract_template_v3_1.json` `rng_stream_roles`). The TPMC
    kernel is never re-registered on the design stream.

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
| golden / reference | captured-reference parity of the component's retained physics. golden_v2 keys may serve as optional development vectors only. `abep golden check` over the NEW active `hall_icp_neutralizer` golden once SC-WP-15 creates it | from SC-WP-15 |
| new-physics verification | principle 9 (analytic cases, conservation, domains, independent verification), bound to the prereg sha256 | NEW_PHYSICS components only |
| Rust-era test rule | § 7: no unregistered `#[ignore]` / skip; registered platform / hardware tests present in the register | always |
| ground-test isolation | principle 8 crate-graph check | always |
| forbidden identifiers | principle 6 | always |
| scoring (dispatch only) | the full pre-registered campaign with the scoring seed, report upload and re-admission gate | `workflow_dispatch` input only |

**Golden scope (v3; RM-OQ-06 OWNER_DECIDED A9.28).**

* **golden_v1 / golden_v2 are historical references.**
  * They are immutable, never deleted and never rewritten.
  * They stay reproducible from the historical Python / reference environment.
  * They are **not** mandatory Rust end-state parity cases.
  * Rust is not required to reproduce the LaB6 / hollow-cathode historical goldens. That covers `architecture_closure`,
    `mission`, `hall`, `source_plasma`, `accelerators`, `design_point_selection`, `nonconverged_reference`, and the
    `hall_1stage`-computed `hall_icp_neutralizer_reference` (AFI-04).
* **Their retained-physics keys may still serve contracts** as optional development vectors: `atmosphere`, `intake`,
  `gas_path`, and the upstream / AO keys of `hall_icp_neutralizer_reference`. The scored reference of every contract
  is the captured Python output of the retained component.
* **While Python CI exists,** `python -m abep_sim.golden check` keeps running unchanged (CLAUDE.md rule 2 as written
  today). The CLAUDE.md update that makes rule 2 apply to the ACTIVE canonical golden set is a separate later commit
  (CA-01). At the end state, the historical cases run only in the separate historical-reproduction job, outside the
  simulator CI.
* **The Rust `abep golden check`** runs the NEW active `hall_icp_neutralizer` golden. That golden is generated only from
  the admitted active Rust chain, under golden-change governance (SC-WP-15). It covers:
  * deterministic input configuration;
  * raw physics;
  * conservation;
  * architecture identity;
  * no conventional hollow cathode;
  * applicable statewise outputs;
  * assessment separation.

  Its values carry the chain's fail-closed statuses as computed. They are never PASS by construction.
* `golden_v2.json` is never regenerated, and no Rust result is ever written into it.

### Wave-specific additions (waves of `migration_order_v3_1.json`)

| wave | extra CI content |
|---|---|
| W0 (Kernel 1) | the existing `rust-parity.yml`, unchanged. A workspace path-dependency use of `abep_core` adds a **build-equivalence** step: K1–K5 on the registered vectors with the development seed, bitwise against the recorded extension, run as a contract addendum. A9.29 secs. 5, 11: `abep-intake` consumes `abep_core` as an rlib without the `python` feature; there is no `DEFAULT_BACKEND` flip job; TPMC keeps its statistical contract (sec. 7) |
| W1E / W1 | frozen-data readers: sha256 of `atmosphere_msis21_v1.*`, `intake_surface_v1.*` and the 196-state design-state set v2 against `config/MANIFEST.json` / the rule-1 provenance. The intake response surface is reproduced against `intake_surface_v1` (statistical or exact class as contracted). The golden_v2 `atmosphere` / `intake` keys only as optional development vectors (RM-OQ-06). W1E also lands `bid_source_guard` (terminal `2de86ab`), the migration-state ledger, the groundtest isolation check (§ 8) and the Rust-era test rule (§ 7) (ES-1). A9.29 sec. 6: deterministic loading, schema / domain checks, hash verification, state selection and the complete 196-state execution from the frozen datasets |
| W2 | gas-path convergence and domain cases: `test_gaspath_convergence_g03_g05.py` and `test_compressor_gaede_domain_mcc02.py` become cargo tests through captured references. `K-GASPATH` / `K-GAS-LIFE` only if an active consumer is confirmed (v3 finding); then a harness-independence check that the Python reference path through `Config("hall_1stage")` reads no card field (RM-R20) |
| W3 | mission propagation: orbit and eclipse invariants, energy balance (`mission_env` only) |
| W4 | F8 / F7: RM-OQ-03 OWNER_DECIDED A9.29 (sec. 7): the `EXACT_STREAM` self-test of the design / UQ sampling stream (numpy PCG64 / SeedSequence / Generator vectors captured from numpy 2.4.4); the TPMC calls inside F8 checked under the admitted Kernel-1 statistical contract, as a separate stream role; the F7 / F8 study outputs, with the empty robust upstream set, as captured references |
| W5 | P3 view factors: reciprocity and enclosure-sum invariants at `RES_VERIFY`; source identity with the profiled function. `NP-THERMAL-CATHODELESS`: principle 9 jobs (no Python reference); a forbidden-identifier scan for any cathode node / `Q_cath` term |
| W6 | the frozen HWM14 orbit v2 wind reader: sha256, schema and domain checks. A9.29 sec. 6: no HWM14 / NRLMSIS build or run in normal CI and no Fortran FFI on the critical path; a later regeneration tool is separately governed |
| W7 | rate-table builders reproduce `abep_sim/data/rates/` and `hallthruster_bridge/propellants/*.dat` byte-identically; `rate_validity.toml` coverage moves from `ci_checks.py` |
| W8 | the Julia bridge (§ 4); O4 / facility pipeline record checks; the `HallMap` pin and schema checks |
| W9 | `NP-ICP-NEUTRALIZER` (A9.29 sec. 4): principle-9 jobs bound to its prereg sha256 (conservation, analytic limiting cases, domain tests per calibrated / uncalibrated mode, the preregistered comparison criteria); a crate-graph check that `abep-icp` never depends on `abep-assess`; a scan that its raw outputs carry no HC-05 / threshold / RFP label; outputs `NOT_VALIDATED` until measured evidence |
| W9–W11 | conservation gate (rule 4) on every closure output. W11 adds the mass roll-up rules (`K-MASS-RULES`) and the `mass_power_a9_v5` generic logic (class A since A9.28) against the committed v4 / v5 records, with the principle-10 value-status check on AL-07. The electrical port excludes the `hall_c1_reference` start-up rule; the forbidden-identifier scan covers `c1_heater` / `c1_keeper` in flight crates |
| W12 | assessment and hard gates: the raw-physics vs assessment split (A9.22; A9.24 items 3–5) is checked as a crate-graph test, so physics crates cannot depend on `abep-assess`. HC-12 stays `NOT_EVALUATED`. HC-05 uses `M_n,LB > 0` and is `NOT_EVALUATED` without uncertainty evidence |
| W13 | `abep config build --check` reproduces `config/**` and `MANIFEST.json` byte-identically. `mission_scenario_v2` is verified against its frozen pin, never rebuilt |
| W15 | per class-A builder, `abep build <id> --check` must give byte-identical committed outputs. Class-H builders get no Rust job |
| W16 | the `scripts/ci_checks.py` checks are ported one by one to `abep ci <check>`. Each is run once against both implementations and must give identical pass / fail on a seeded set of corrupted trees; then the Python check is retired. `h2_6_live_sources` (RM-OQ-09 OWNER_DECIDED A9.28): its semantics are covered by the generic Rust provenance verifier (SC-WP-12: source hashes, provenance, pinned owner decisions, expected values, deterministic source verification; obsolete H2-6 architecture assumptions not ported); the Python check retires from active CI only after the verifier is admitted and CI is re-pointed. The active `hall_icp_neutralizer` golden job (SC-WP-15) |
| GT | class-T ground-test tooling (`abep-groundtest`): per-builder `--check` byte identity for `ACTIVE_GATE_TOOLING` / `ACTIVE_EVIDENCE_TOOLING`; principle 8 isolation. Feed-state closure (A9.29 sec. 2): at cutover, normal CI verifies the successor record, or the frozen reference-evidence manifest (sha256 of every output file, schema validation); its historical builder is not run |
| W17 | the end-state jobs of § 5, including the Python final-reference archive check (A9.29 sec. 8) |

## 3. `bid_source_guard` (PROGRAMME.md § 5; A9.29 sec. 3)

The first implementation PR (ES-1) adds this check: `ci_checks.py --only bid_source_guard`, later
`abep ci bid-source-guard`. It **protects the A9.28 protected bid record, with `2de86ab` as the terminal package state
(RM-OQ-11, OWNER_DECIDED A9.29 sec. 3)**:

* technical source `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b`;
* package / freeze record `2de86abefacbd36ce7516d3cf017f6258bd7e7a2`, named by A9.28 message 2 sec. 1.

The package lineage is `b5849affae22a6709ad217a184f6fe896d15410a`, named by A9.25 message 8 and A9.27, followed by
`2de86ab`. `2de86ab` is the A9.27 package-level post-source bid-text update; it still pins `5eee4b8`, and its
authorising decision record marks `package_level_post_source_allowed`. Both bytes sets are recorded in the manifest.
The guard treats `2de86ab` as the terminal owner-authorized package state. Any later change to the historical bid
package needs a new explicit owner decision and must not silently alter the frozen bid record.

It fails in any of these cases:

* a `docs/bid/**` file differs from its bytes at the terminal package state `2de86ab` (lineage `b5849af` → `2de86ab`),
  and no new explicit owner decision record or re-freeze names the change;
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
| cargo build/test | `cargo build --locked --workspace` + `cargo test --locked --workspace` under the Rust-era test rule (§ 7, A9.29 sec. 9) | E1, E13 |
| deterministic output | double-run bitwise check over all registered vectors and CLI end-to-end runs | E1, E2 |
| Python-reference parity while the reference is active | per-component development parity jobs, removed component by component at `PYTHON_RETIRED_FROM_ACTIVE` | E7 |
| Julia Hall bridge compatibility | `abep hall pin-check` / `smoke` / `schema-check` | E8 |
| conservation | rule-4 gates on the active closure and design outputs | E1 |
| config/hash validation | `abep config build --check`, `abep config verify`, prereg locks, audit `MANIFEST.json`, validation-release links, `bid_source_guard` | E3, E9 |
| schema compatibility | every output validated against `schemas/**`; Hall-map schema | E4, E9 |
| golden/reference cases | `abep golden check` on the active `hall_icp_neutralizer` golden (SC-WP-15) + captured-reference parity for every admitted component; golden_v1 / v2 (unchanged) only in the historical-reproduction job outside the simulator CI (RM-OQ-06, A9.28) | E2, E4, E5 |
| no forbidden Python runtime dependency after final migration | see below | E1, E6, E10 |

**"No forbidden Python runtime dependency" check (end state).** It has six parts.

1. **Python-free runner.** The simulator jobs run in a container image with no `python3` / `python` / `pip` /
   `virtualenv` on PATH (assert `! command -v python3`, and the same for the others; A9.29 sec. 11). They run the `abep`
   CLI end to end over the active chain (the A9.29 sec. 15 chain for `AIR_PRIMARY` and `XE_CONTINGENCY`): design
   synthesis, sweep, golden check, config check, every `abep build --check`, `abep ci` and the Julia smoke.
   HallThruster.jl's own Julia dependencies are allowed. Any Python they might pull in through Julia packages (for
   example PyCall) is checked absent in `Manifest.toml`.
2. **Static scan.**
   * Workflow files for the simulator contain no `setup-python`, `python`, `pip`, `pytest`, `virtualenv` or `maturin`
     steps.
   * Rust sources contain no `Command::new("python…")`.
   * `cargo tree` / `cargo metadata` of the workspace contain no `pyo3` and no `maturin`, because `abep_core` is consumed as
     an rlib and its PyO3 / maturin interface is retired from production at W17 (A9.29 sec. 11, E11).
   * Shell runners under active paths do not invoke Python.
   * The forbidden-identifier scan (§ 1, principle 6) is green.
3. **Retirement completeness (class H / G).**
   * No active build, test or workflow path imports or runs a class-H module or an unrequired class-G module. The check is a
     static import scan against `component_inventory_v3_1.json` and its end-state re-run.
   * Historical reproducibility, such as the historical golden cases, runs only in the separate historical-reference job,
     never in simulator CI (RM-OQ-06, OWNER_DECIDED A9.28).
4. **Ledger completeness.**
   * In `docs/rust_migration/migration_state_v1.json`, every class-A and class-T component is `ADMITTED` +
     `PYTHON_RETIRED_FROM_ACTIVE` or `FORMALLY_RETIRED_NOT_PORTED`.
   * Every class-G / H component is `FORMALLY_RETIRED_NOT_PORTED`, or admitted under a recorded requirement.
   * No class-F component remains.
   * A re-run of the inventory at the end-state commit finds no active Python component outside the Python final-reference
     archive.
5. **Python final-reference archive (A9.29 sec. 8, E12).**
   * The tag `python-final-reference-<date>` and the branch `archive/python-final-reference` exist.
   * `docs/archive/python_final_reference.json` maps every inventory-v3_1 Python component to its Rust replacement or
     formal retirement, then to its parity / admission evidence. Each referenced evidence file exists with its sha256.
   * `docs/archive/PYTHON_FINAL_REFERENCE.md` is generated from it.
   * main has no `archive/python_reference` directory unless an operational need is recorded.
6. **Ground-test isolation (A9.29 sec. 1, E14).** The § 8 check is green.

Until the end state, `ci.yml` (Python) stays the required CI. Rust jobs move from optional to required as § 1, principle 4,
describes. While the Python suite runs, its expected outcome (5 skipped, 1 strict xfail) is unchanged; A9.29 sec. 9 makes
it archive-era reproduction metadata of the Python reference, not the rule for active Rust production.

## 6. Main-merge pre-PR checklist and completion report (A9.28 message 2 secs. 16 and 18)

All CI described here runs on `integration/simulation-complete`. main is not touched incrementally. Before the NEW PR
`integration/simulation-complete → main`, every item of the 18-item pre-PR checklist must be green on the integration
head. The checklist is in `SIMULATION_COMPLETION_PROGRAMME.md` § 8.1, with a mechanical check and an owning work package
per item. In short:

* Rust + HallThruster.jl only, and no active LaB6 / hollow-cathode path;
* the selected-architecture identity invariant, and every retained Python component migrated or explicitly historical;
* clean install, deterministic outputs, conservation, and config / hash integrity;
* the active golden green, the full Rust tests and the Hall interface tests;
* 196-state execution, robust / UQ execution and the assessment separation tests;
* no silent fallbacks, and no requirement parsing in raw physics;
* GitHub CI green, and no uncommitted / generated drift.

The completion report A–N (§ 8.2 there) quotes the CI run ids (item L) and the zero-Python proof (item D, from the E1
/ E6 / E10 checks above). Only then is owner authorization requested. PR #37 is not reused.

## 7. Rust-era test rule (A9.29 sec. 9, RM-OQ-05, RM-R39)

This replaces the Python-era rule (pytest + 5 skips + 1 xfail) for **active production**. The CLAUDE.md update (CA-04)
is performed separately per A9.29 sec. 10.

**Normal active CI.**

* `cargo test --workspace --locked` runs, and every active test PASSES.
* No ordinary active production test is silently ignored or skipped.
* Known missing physical evidence is never a skipped test. The test asserts the correct fail-closed result:
  `NOT_EVALUATED`, `INCOMPLETE_EVIDENCE`, `OUT_OF_DOMAIN` or `MODEL_ERROR`, as applicable. Examples:
  * HC-12 is asserted `NOT_EVALUATED`;
  * HC-05 without `M_n,LB` evidence is asserted `NOT_EVALUATED`;
  * a state outside the frozen grid is asserted `OUT_OF_DOMAIN`;
  * a hash mismatch is asserted `MODEL_ERROR`.
* The empty Hall credible transport set is an expected governed state. A test asserts it explicitly (no admitted member;
  every output that needs Hall performance carries `NOT_EVALUATED` with its reason). It is never an xfail.

**Registered platform / hardware test class.** A test that genuinely cannot run in normal CI (for example one that needs
the Julia toolchain on a specific runner, or bench hardware) is registered, never dropped. Each register entry carries:

* the test id and its crate / path;
* the **reason** it cannot run in normal CI;
* the **owner / evidence basis**;
* the **execution environment**;
* the **required trigger** (for example `workflow_dispatch`, a schedule, or arrival of P1 / P2 bench evidence).

The register is proposed as `docs/rust_migration/test_register/platform_hardware_tests_v1.json`. The ES-1 implementation
PR creates it with the first `cargo test`; the mechanism below is a proposal that PR fixes.

* Registered tests are marked `#[ignore = "REGISTERED_PLATFORM_TEST:<id>"]` (or sit behind one named cargo feature).
* A CI check scans the active crates:
  * every `#[ignore]` carries a `REGISTERED_PLATFORM_TEST:<id>` that exists in the register;
  * every register entry matches a test that still exists, so a registered test never silently leaves the inventory;
  * no other skip pattern is used in active production tests.
* A dispatch / scheduled job runs the registered tests in their environment when the trigger fires, and records the run.

**The historical Python suite.** Its 5 skips / 1 strict xfail stay archive-era reproduction metadata. They are not
carried into the Rust suite as skips or xfails.

## 8. Ground-test isolation check (A9.29 sec. 1, RM-R30)

`GROUND_TEST_PROGRAMME_ONLY` and `abep-groundtest` are OWNER_APPROVED. Their code may be active programme / evidence /
gate tooling, but no flight-runtime crate may depend on it.

* **Check.** `cargo metadata --format-version 1 --locked`. For every flight-runtime crate (the physics crates,
  `abep-julia-bridge`, `abep-design`, `abep-uq` and `abep-assess`), walk the resolved dependency graph. The check fails if
  `abep-groundtest` appears, for any dependency kind.
* **When.** It lands with the workspace (ES-1) and runs on every push. It is trivially green until `abep-groundtest`
  exists.
* **Feed-state closure.** A retained S1 / S1a need for a live feed-state computation is implemented in `abep-groundtest`
  under its own Rust contract (A9.29 sec. 2), so this check also covers it.
