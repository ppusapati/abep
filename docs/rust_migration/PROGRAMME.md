# Rust migration programme v2 (A9.24 / A9.25): zero Python execution dependency, cathodeless active architecture

**Status: `PROPOSED_PLAN_V2_FOR_OWNER_REVIEW`. This is a docs / plan record only.** It changes no Python, Rust, CI workflow,
configuration, frozen data or number.

This revision is step 7 of the owner's order (A9.25 message 3: "only then revise/review/merge the Rust migration plan"). The
earlier steps are done:

* bid technical source `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b`;
* package / freeze record `b5849affae22a6709ad217a184f6fe896d15410a`;
* `PRE_RUST_REFERENCE_BASELINE` registered at `adce2e9` (`docs/performance/pre_rust_reference_baseline_5eee4b8/`). A9.27
  accepts it as post-freeze evidence.

This lane is based on the execution branch at `2de86ab`, the A9.27 package-level bid-text commit. That commit leaves the
technical source unchanged and names the same pair. Substantive Rust waves (step 8) start only after the owner reviews and
merges this plan.

**What changed from v1.** v1 is kept unchanged as history (`programme_v1.json`, `component_inventory_v1.*`,
`migration_order_v1.json`, `parity_contract_template_v1.json`).

* **The v1 rule "known physics inconsistencies are ported as they are" (RM-R15), which the owner records as "LaB6 paths
  are ported unchanged pending the audit", is REJECTED and replaced.** The new rule: **LaB6 / conventional hollow-cathode paths are
  NOT ported into the active Rust simulator** (A9.25 message 3).
* Every inventoried component now has one of the owner's four migration classes (§ 2). Parity is required only against
  retained selected-architecture physics.
* The waves are re-ordered on the registered `PRE_RUST_REFERENCE_BASELINE` (§ 10). The ordering key is the one A9.27 sec. 4
  sets: architecture relevance first, evidence / parity eligibility second, measured performance third. Legacy profiled
  workloads are not port targets.
* The bid boundary is now the concrete pair `5eee4b8` / `b5849af`, and `mission_scenario_v2` is immutable (§ 5).

Governing records, read verbatim:

* `docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md`, items 1, 2, 6, 7, 8, 9, 13 and 14
  (md sha256 `9a2c950b…25b1d7`, json `fdbb4561…5cc3c`).
* `docs/decisions/OD_2026_10_04_A9_25_PRE_BID_OWNER_DECISIONS.md` (md `159ea204…6106`, json `c05fcc45…9385`):
  * message 1, secs. 9, 13, 14, 15 and 18;
  * message 2, secs. 4, 5, 6, 8, 9, 10, 14 and 15;
  * message 3 (the LaB6 rule), in full;
  * message 8, secs. 4, 12–14 and 17.
* `docs/decisions/OD_2026_10_05_A9_27_FINAL_BID_OWNER_RULINGS.md`:
  * the preamble: protect the frozen bid pair, and do not move the technical source to later performance / Rust-planning
    commits;
  * sec. 4: classification governs before runtime. A slow legacy `uq_modular` or `archengine` is retired, not ported; only
    architecture-independent kernels still required are extracted; active intake response-surface work remains a genuine
    target;
  * sec. 5: the stale owner-question state v5 (MPV3Q-01) is repaired post-bid by a successor record.
* The cathode-path audit v1, `git show b8f39b7:docs/audits/a9_24_cathode_path_audit_v1.md`. It is on branch
  `lane-a924-cathode` and is not merged into the execution branch. Its classes are HR (historical regression), GR (ground
  reference) and AFI-01..05 (active-flight inconsistency). AFI-01, -03 and -05 are now resolved, AFI-02 is open, and the owner
  classified AFI-04 as `HISTORICAL_REGRESSION_COMPATIBILITY`.
* `docs/performance/pre_rust_reference_baseline_5eee4b8/REGISTRATION.json` and `baseline.json` (the ranking).

A9.24 supersedes A9.7's "do not rewrite the simulator in Rust" (`SUPERSEDED_BY_A9_24_ITEM_1`). It also supersedes A9.14
S10.3 `PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING`, per component on admission. A9.14 S10.4
(`OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`) stays in force, and `CI_PLAN.md` extends it.

Machine-readable companions in this directory:

| file | content |
|---|---|
| `programme_v2.json` | end state, active architecture, lifecycle, the four-class rule, rules RM-R01..R25, the bid pair and guard, item-14 checklist, workspace, owner questions |
| `component_inventory_v2.json` / `.md` | 227 components (224 Python-file components + 3 non-`.py` paths; 451 Python files), each with class, basis, disposition, wave, kernels, not-ported parts |
| `migration_order_v2.json` | waves W0–W17 and lanes GR / RET / AFI; the PRE_RUST ranking mapped to them; prerequisites P-01..P-05 |
| `parity_contract_template_v2.json` | the per-component pre-registration template; v1 plus a classification gate |
| `CI_PLAN.md` | the incremental Rust CI plan (item 8), revised for v2 |
| `*_v1.*` | v1, unchanged history |

---

## 1. End state

These statements are A9.24 items 1 and 14, verbatim in substance.

* **Rust is authoritative** for:
  * physics, except the Hall solver;
  * design-space generation and mission propagation;
  * UQ / Monte Carlo orchestration;
  * architecture closure, assessment / compliance and hard gates;
  * configuration loading and hash verification;
  * evidence builders, CLI tools and deterministic result generation;
  * the validation and parity tooling that is now in Python.
* **HallThruster.jl stays the authoritative Hall-discharge solver.** It stays pinned to v0.23.1, commit `bfb3019f…`
  (`hallthruster_bridge/PINNED.toml`, CLAUDE.md rule 7), and Rust drives it through a process bridge (§ 8).
* **Zero Python execution dependency.** The simulator, tests, builders, evidence generation and assessment need no Python
  interpreter.
* **The active Rust architecture is `hall_icp_neutralizer`** (`config/architecture/hall_icp_neutralizer_v1.json`):
  * a Hall accelerator;
  * a downstream RF/ICP electron source / neutralizer;
  * `AIR_PRIMARY` and `XE_CONTINGENCY`;
  * no conventional hollow cathode.

  C1 is `GROUND_REFERENCE_ONLY` laboratory hardware. It is never flight hardware, a fallback, an electron source, Xe, mass,
  power, a thermal load or part of the closure.
* **Python source is not deleted.** Until a class-A component is admitted, its Python code is the migration reference. After
  that, it stays only as immutable history: in Git, under a retired tag, or in a clearly retired directory. Class-H and class-G
  Python is kept the same way and stays reproducible from its historical commit. Historical evidence is never deleted.

## 2. Migration classification (A9.25 message 3)

**LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust simulator.**

Each component in `component_inventory_v2.json` has exactly one primary class:

| class | owner rule | where it goes | components | lines |
|---|---|---|---:|---:|
| `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS` | migrate to Rust under pre-registered parity / admission | waves W0–W17 | 135 | 175,499 |
| `GROUND_REFERENCE_ONLY` | migrate only if the future active test / evidence toolchain genuinely requires it; never in flight execution | lane GR (on demand) | 7 | 12,502 |
| `HISTORICAL_LEGACY_REGRESSION` | do not port; keep the Python implementation and historical commit / evidence for reproducibility | lane RET | 84 | 73,767 |
| `ACTIVE_FLIGHT_INCONSISTENCY` | do not port; resolve against `hall_icp_neutralizer` first, then migrate only the corrected implementation | lane AFI | 1 | 874 |

**How the classes are read.**

* Class A means "belongs to the active selected architecture" (A9.25 msg 1 sec. 14, step 2). It therefore includes that
  architecture's design, assessment, configuration, evidence and CI toolchain, which A9.24 item 1 makes Rust-owned.
* Each classification carries its basis (owner record, audit item or repository evidence) and a confidence:
  * established: 62 components;
  * proposed by this lane: 156;
  * provisional, with owner confirmation requested: 9 (RM-OQ-07).
* Nothing is unclassified.

**Not ported as active flight functionality, wherever it sits:**

* `LaB6Cathode`;
* `lab6_xe`;
* Xe hollow-cathode heater / keeper logic;
* C1 flight-fallback logic;
* legacy Hall cards whose flight topology contains a hollow cathode;
* historical multi-family architecture-selection machinery that would be kept only for parity. That covers the archengine
  families `mw_air`, `rf_cathode`, ECR-Hall, gridded, nozzle, MPD, PIT and thermal.

**Owner-approved section E (A9.25 msg 2 sec. 10): retire, not port.** RETIRE != DELETE. The modules are:

* thruster CARDS;
* `plasma_devices` and `cathode_integration`;
* `archengine`, `arch_compare`, `breakeven` and `interstage`;
* `hall1d` and `compressor_transitional`;
* `sizing`, `thresholds` and `uncertainty`;
* `uq6`, `uq_modular` and `mission_uq`;
* `convergence` and `explorer`.

They are class H in the inventory. So are other modules whose only consumers are the superseded legacy chain:

* `system.py` (the card closure) and its programme / assessment wrappers;
* `golden.py` (AFI-04);
* `life`, `mass_bom`, `ppu`, `thermal`, `transient`, `mission5`, `radiation`, `orbit_atm`, `validation`, `xe_ledger`,
  `arch_boundary` and `hard_gates`;
* the A5 multi-family comparison builders;
* the superseded record versions;
* the historical A5 upstream pre-ionizer campaign (A9 decision of 2026-09-29).

**Parity rule.** Parity is required against the authoritative Python implementation of physics the selected architecture
retains. It is not a requirement to preserve obsolete architecture errors or retired hardware topology.

**Extract-and-parity kernels.** Where a retained physical calculation sits inside a legacy module, only that function subset
is ported and parity-tested:

| kernel | inside | wave | what it is |
|---|---|---|---|
| `K-GASPATH` | `abep_sim/system.py` | W2 | the air-mode gas-path closure: collection → compressor → reservoir → orifice, plus AO inlet composition; `p_target_Pa` supplied |
| `K-GAS-LIFE` | `abep_sim/archengine.py` + `abep_sim/life.py` | W2 | the gas-state wrapper with intake / blade AO-coating life (`intake_life`, `blade_life`) |
| `K-MASS-RULES` | `docs/budgets/mass_power_a9_v3/` | W11 | the fail-closed mass roll-up rules the v4 / v5 builders import unchanged |
| `K-P3-RAYS` | `docs/experiments/hall_icp/p3_coupled_thermal/` | W5 | P3 ray / view-factor / plume functions, already copied verbatim (cathode-free) into `abep_sim/icp_thermal_lib.py` |
| `K-GOLDEN-COMPARE` | `abep_sim/golden.py` | W16 | the generic golden comparison harness (tooling) |

**Candidate kernels** are listed for seven more modules: `thruster`, `thermal`, `ppu`, `radiation`, `mass_bom`, `life` and the
Hall reference. They are architecture-independent functions with no active consumer today, and they are extracted only when
one appears (A9.25 msg 2 sec. 8).

Class-A modules can also contain logic that is not ported:

* `thermal_life.py`: the LaB6 emitter / evaporation, cathode node and RF / ECR source checks;
* `magnet_power.py`: the ECR resonance helper;
* `owner_decisions/`: the superseded v1–v4 question-state builders. The v5 state is stale on MPV3Q-01 (A9.27 sec. 5), so
  its post-bid successor record, not the stale v5, becomes the parity reference;
* `profile_baseline.py`: the legacy workloads.

The ground-reference parts inside class-A records stay `GROUND_REFERENCE_ONLY` and never enter flight execution. Examples are
the C1 slot of the A9 bus boundary, the C1-GT Xe lines, the RFQ C1 lines and the C1 arm of the Hall→ICP experiments.

**AFI status (cathode audit v1 → today).**

* AFI-01 (the AL-08 C1 cathode-feed branch) is resolved in mass / power v4 / v5. The v3 record is historical evidence.
* **AFI-02 is open.** AL-07 = 6.0 kg is a `PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR` that contains legacy C1 functions;
  AFI-02-RA1 is the re-base action. So `docs/budgets/mass_power_a9_v5/` is the single class-F component. It is not ported
  until the re-base, and the migration invents no reduction.
* AFI-03 (the P3 v2 cathode node) is resolved by owner labelling. P3 v2 is class H, and its ray kernels are already in
  `icp_thermal_lib`.
* AFI-04 (the golden computed through `hall_1stage`) is `HISTORICAL_REGRESSION_COMPATIBILITY`. The LaB6 path is not ported, and
  an active `hall_icp_neutralizer` golden is created post-bid (P-02).
* AFI-05 (the RVM-16 keeper wording) is resolved.

**Dependency findings** (runtime imports and dynamic loads, re-derived at `2de86ab`).

* No class-A simulator or design module loads a class-H / G / F module at run time. The F1–F8 chain is already cathode-free.
* There are two tooling exceptions:
  * `scripts/ci_checks.py` loads the class-G H2-6 builder for check `h2_6_live_sources` (RM-OQ-09);
  * `scripts/perf/profile_baseline.py` times the legacy workloads, which are not ported.
* There are two pull-forwards:
  * `mission_env` constants for `atmosphere_orbit` (W1);
  * the experiment-only P1 reducer for `icp_bench_lib` (W9).
* Of the 162 test files, 98 import only class-A modules and 64 exercise class H / G / F code. The second group stays with the
  retired Python.

## 3. Component lifecycle

Each component has exactly one status. Status changes are recorded in a migration-state ledger, proposed as
`docs/rust_migration/migration_state_v1.json` and created by the first implementation PR, with one row per inventory-v2
component. Each change also gets a docs/HISTORY.md entry.

| status | meaning | evidence needed to enter it |
|---|---|---|
| `PYTHON_REFERENCE` | Python is authoritative and is the migration reference (class A) | default for class A, except Kernel 1 |
| `PREREG_PARITY` | a parity contract from template v2 is committed **in its own commit before any comparison**. The commit fixes the reference commit and file sha256, the inputs, seeds, observables, tolerances, decision rules and the classification gate | the contract file and its sha256 recorded in the ledger |
| `RUST_IMPL` | the Rust implementation exists and passes `cargo test`. It is never served for production | Rust commit and source sha256 |
| `PARITY_PASS` | the scoring execution returns `ADMITTED` for every kernel / observable group | parity report (JSON + MD) committed whatever the verdict |
| `ADMITTED` | Rust is authoritative, and new production results come from Rust (item 1). Results carry `implementation: rust` and the Rust commit | owner-visible HISTORY entry; ledger flip; CI job added (CI_PLAN.md) |
| `PYTHON_RETIRED_FROM_ACTIVE` | no active execution path imports or runs the Python component. The code remains as the reference snapshot or as history | a static check (no import or invocation from active paths) passes |
| `FORMALLY_RETIRED_NOT_PORTED` | retired without a port (item 14 "or has been formally retired"): class H, unrequired class G, or a class-A component with disposition `MIGRATE_OR_FORMALLY_RETIRE` | an explicit owner or lane decision in HISTORY, plus the static check. Outputs stay byte-identical in Git |
| `NOT_ADMITTED` | a scoring execution failed | the report is kept. Only a code fix plus a **new contract version with fresh scoring seeds** may follow |
| `GROUND_REFERENCE_ON_DEMAND` | class G, waiting. It moves to `PREREG_PARITY` only with a recorded requirement of the active test / evidence toolchain | the inventory row |
| `NOT_PORTED_RETIREMENT_PENDING` | class H, still in the production import graph until its post-bid retirement | the inventory row |
| `NOT_PORTED_BLOCKED_ACTIVE_FLIGHT_INCONSISTENCY` | class F. Its resolution creates a corrected successor, which then follows the class-A path | the inventory row |

`PARITY_PASS` and `ADMITTED` are separate states on purpose. A pass is a numerical fact; admission makes Rust authoritative.

**Kernel 1, the TPMC intake trace kernels K1–K5, is `ADMITTED`.** Its records are `abep_core/`, `parity_prereg_v2.json` +
`parity_report_v2.json`, `scripts/verify_abep_core.py` and `abep_sim/design/tpmc_backend.py`.

* `DEFAULT_BACKEND = "python"` is unchanged (RM-OQ-01).
* The frozen `intake_surface_v1.*` is never regenerated because of a backend switch (CLAUDE.md rule 1).
* The response layer of `abep_sim/intake_tpmc.py` stays `PYTHON_REFERENCE` until W1.

## 4. Migration rules (binding for every contract)

RM-R01..R14 and R16..R18 are unchanged from v1 (item 1 verbatim, plus their operational consequences). RM-R15 is replaced.
RM-R19..R25 are new.

1. **No big bang.** Migration goes component by component, or by a tightly coupled group that one contract names. A wave is
   a scheduling unit, never an admission unit.
2. **Exact input parity.** Both implementations consume byte-identical inputs, each with its sha256.
3. **Exact architecture/config hashes.** Both runs record the same architecture hash, config hash (`config/MANIFEST.json`),
   model-set hash and design-state-set hash. A mismatch voids the comparison.
4. **Deterministic seeds where applicable.** Development seed vs scoring seed; the scoring seed is spent once.
5. **Tolerances pre-registered before any comparison**, per observable, by parity class (§ 6).
6. **Output-schema parity.** Byte-identical evidence where the contract says `EXACT_BYTES`; this needs a Python-compatible
   JSON / CSV float formatter.
7. **Conservation checks** on the Rust outputs themselves: source mass and power balances are exact, and the energy-ledger
   residual is below 2 % (CLAUDE.md rule 4).
8. **Domain/error parity.** Out-of-domain and invalid inputs fail the same way, including `sustained=False`, `MODEL_ERROR` and
   `INFEASIBLE` (CLAUDE.md rule 3). No silent fallbacks.
9. **Performance measurement.** It is recorded on one machine in one session, and it is **never a decision criterion**.
10. **Provenance.** Each run records:
    * the Python reference commit and file sha256;
    * the Rust commit and source sha256;
    * the toolchain and the Cargo.lock sha256;
    * Julia / HallThruster where relevant;
    * the thread / BLAS environment.
11. **Never rewrite Python results or goldens to make Rust pass.** A disagreement is investigated and classified as one of:
    * a Rust defect;
    * a Python reference defect, fixed under its own governance;
    * a contract defect, which needs a new contract version.

    It is never resolved by changing a tolerance.
12. **`no_retuning`.** After `NOT_ADMITTED`, only a code fix plus a new contract version with fresh scoring seeds may follow.
13. **Reference freeze.** A changed reference refuses scoring (`REFUSED_REFERENCE_CHANGED`) until a new contract version exists.
14. **Layer separation becomes crate dependency rules.** Physics crates never depend on `abep-assess` or `abep-evidence`
    (A9.22 / A9.23; A9.24 items 3–5: physics emits `T_available`, and assessment evaluates thresholds).
15. **REPLACED (A9.25 msg 3).** LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust simulator. The
    rejected v1 rule ("known physics inconsistencies are ported as they are", that is, "LaB6 paths are ported unchanged pending
    the audit") is recorded in `programme_v2.json` as `REJECTED_AND_SUPERSEDED`.
16. **Rule-1/2 data stays frozen.** No migration step regenerates `atmosphere_msis21_v1.*`, `intake_surface_v1.*`,
    `golden_v2.json` or `rates/`.
17. **Kernel granularity is allowed.** A contract may admit a function subset of a module. For class-H modules this is the
    only way anything inside them is ported (§ 2 kernels).
18. **After admission**, new production results for the component come from Rust.
19. **Four-class gate.**
    * A contract may be registered only for a class-A component or an extract-and-parity kernel.
    * Class G needs a recorded active-toolchain requirement first.
    * Class H is never contracted.
    * Class F is contracted only as its corrected successor.
20. **Parity only on retained physics.** Where the Python harness must traverse a legacy path to reach a retained kernel, the
    contract shows that path cannot influence the scored observables. For example, `K-GASPATH` is reached through
    `Config("hall_1stage")`, whose card fields are never read on the gas path (audit AFI-04).
21. **RETIRE != DELETE.**
    * Class H keeps its source, history and evidence, and leaves the production execution graph post-bid.
    * Historical simulations stay reproducible from their historical commit / reference environment.
    * No historical record or golden is rewritten.
22. **Resolve AFI before porting.** An active-flight inconsistency is resolved against `hall_icp_neutralizer` by its own
    owner-governed change. The migration never alters a numerical baseline and never invents a value (A9.24 item 13).
23. **No inheritance of obsolete architecture.** No Rust crate depends on, re-implements or carries a class-H / G / F path, and
    there is no legacy crate. A forbidden-identifier scan enforces this (CI_PLAN.md § 1, principle 6).
24. **The bid pair is frozen** (§ 5). Package-level post-source bid-text updates, such as A9.27 / `2de86ab`, happen only under
    an owner decision record and always pin `5eee4b8`. `mission_scenario_v2` is immutable after the freeze; a later change is
    `mission_scenario_v3`.
25. **Ordering key** (A9.27 sec. 4): architecture relevance first (the four classes), evidence / parity eligibility second,
    measured performance third. A slow legacy workload is retired; it is never ported because it is slow.

## 5. Bid boundary (A9.24 items 2 and 9; A9.25 message 8 secs. 12–14; A9.27)

* **Technical source SHA:** `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b`. Its code, configs, architecture, engineering records
  and numerical outputs define the bid. It was verified by:
  * GitHub CI run 37263814635, green on all jobs;
  * full pytest: 5 skipped, 1 strict xfail;
  * Rule-9, ci_checks 11/11, golden, `config --check` and the affected builders.
* **Package / freeze-record SHA:** `b5849affae22a6709ad217a184f6fe896d15410a`.
  * It holds `docs/bid/bid_technical_baseline_v2.json` (sha256 `987a0d4e…60d1d`) and the regenerated package.
  * Both pin the technical source; every package fact is read with `git show 5eee4b8:<path>`.
  * The package commit does not become a technical source.
  * Python files differ from the technical source only in `docs/bid/package/{build_package,compliance_data,source_facts}.py`
    and `tests/test_bid_package.py`.
  * A9.27 ("Protect the frozen bid pair") names this pair again.
* **Package lineage after the freeze record:** `2de86abefacbd36ce7516d3cf017f6258bd7e7a2` (A9.27 final bid rulings).
  * It is a package-level post-source update of the bid text only: RFP-P19-03, the RFP-P18-08 split, OIR-DOC-01 and the
    Part IV(A)–(H) submission checklist.
  * It still pins `5eee4b8`, and its `bid_technical_baseline_v2.json` marks A9.27 `package_level_post_source_allowed`,
    `in_technical_source: false`.
  * It is not a new technical source.
* **`config/mission/mission_scenario_v2.json`** (sha256 `885b1f70…5fc49`, identical at `5eee4b8` and at `2de86ab`) is
  **immutable after the freeze**. A later semantic change is `mission_scenario_v3`, with its own pin (A9.25 owner decision
  summary, `mission_scenario_v2_versioning`).
* The technical-source sha256 values of `config/MANIFEST.json`, the physics model set, the engineering constraints, the gate
  thresholds, the architecture config, `golden_v2.json` and the 196-state design-state set are recorded in `programme_v2.json`
  (`bid_boundary.other_pinned_at_technical_source`). They are unchanged at `2de86ab`.
* **The `bid_source_guard` proposal protects the pair.** The first implementation PR implements it; this record does not.
  1. **`docs/bid/bid_source_manifest_v1.json`**, generated once. It holds:
     * the sha256 of every file at `5eee4b8` that the package cites or executes;
     * the sha256 of every `docs/bid/**` file at `b5849af`, and at each owner-authorised package-level post-source commit
       (`2de86ab`), with the authorising decision record;
     * the `mission_scenario_v2` sha256;
     * the migration state at the freeze: every component Python-authoritative, and Kernel 1 admitted as an optional backend
       with default `python`.
  2. **CI check `bid_source_guard`**: a `scripts/ci_checks.py` check while Python CI exists, then `abep ci bid-source-guard`.
     It fails when any of these is true:
     * a `docs/bid/**` file differs from its bytes in the recorded package lineage (`b5849af`, then `2de86ab`), and no new
       owner decision record or re-freeze exists;
     * `bid_technical_baseline_v2.json` does not pin `5eee4b8`;
     * the package builder runs against anything other than `git show 5eee4b8:<path>`;
     * a bid-cited technical-source file differs from the manifest;
     * `mission_scenario_v2.json` changes;
     * bid-cited evidence carries `implementation: rust`.
  3. The pair is recorded as immutable SHAs even where repository infrastructure prevents a tag (A9.25 msg 2 sec. 12, step 8).
  4. Every Rust-produced result carries `implementation`, `rust_commit` and `contract_id`.
* An owner re-freeze that names a new technical source and package is the **only** way a post-migration state becomes a bid
  source.

## 6. Parity classes

| class | applies to | rule |
|---|---|---|
| `EXACT_BYTES` | generated JSON / CSV / MD evidence, manifests, hashes, config outputs | byte-identical files (sha256 equal) |
| `EXACT_VALUE` | integers, strings, enums, statuses, booleans, error codes, schema shape | equal |
| `ULP_BOUNDED` | closed-form floating point arithmetic, and transcendental functions where libm may differ | `|Δ| ≤ k ulp` or a relative bound `≤ r`, pre-registered per observable. The proposed default is k = 4, r = 1e-12 |
| `SOLVER_TOLERANCE` | iterative solvers | convergence status `EXACT_VALUE`; solution within a pre-registered tolerance tied to the solver's own; iteration counts reported, not scored |
| `STATISTICAL` | RNG-driven results when the streams differ | the `parity_prereg_v2` method: per-test `|Δ| ≤ z·√(se_py² + se_rs²)` with z = 5, an aggregate bound, exact invariants, no retuning |
| `EXACT_STREAM` | RNG-driven results when Rust ports numpy's bit generator and distribution algorithms | then `ULP_BOUNDED` or `EXACT_BYTES` |

Kernel 1 used `STATISTICAL` with xoshiro256++, and that admission stands. W4 is the F8 robust optimizer. It draws numpy
`default_rng` (PCG64) streams from stable ids and calls the TPMC kernel, so its parity class is RM-OQ-03.

A contract that fails the classification gate is `REFUSED_CLASSIFICATION`. That is a refusal to register, not a verdict.

## 7. External-dependency strategy

These choices are unchanged from v1. The full list per component is in `component_inventory_v2.json`
(`rust_equivalents_needed`).

* **numpy / scipy.** Hand-port the algorithms the reference actually uses (`scipy.stats`, `scipy.integrate`,
  `scipy.interpolate`, `scipy.constants` pinned to scipy 1.17.1). A generic crate is not swapped in where it would change the
  algorithm.
* **pandas.** Rust uses `csv` + `serde`, with pandas-compatible formatting where committed CSVs are `EXACT_BYTES` references.
* **pymsis / NRLMSIS.** Production reads the frozen dataset, so Rust needs no NRLMSIS at run time. Rebuilds are rule-1 model
  changes (RM-OQ-02).
* **HWM14** (`atmosphere_orbit_v2.py`, W6) stays a compiled Fortran executable launched with `std::process::Command`.
* **matplotlib.** Figures are not evidence; parity applies to the plotted data.
* **openpyxl / python-docx / pymupdf / PIL / jsonschema / zstandard.** These map to `rust_xlsxwriter` / `calamine`,
  `docx-rs`, `pdfium-render`, `image`, `jsonschema` and `zstd`.
* **pytest → `cargo test`.** The rule-9 equivalent needs an owner-approved CLAUDE.md revision (RM-OQ-05). Of the 162 test files,
  64 exercise class H / G / F code and stay with the retired Python.

## 8. Rust↔Julia bridge (HallThruster.jl stays authoritative)

This section is unchanged from v1 § 7. Python drives Julia out of process today, file-based:

* `identify_p5_transport.py` uses `subprocess.Popen`;
* the launch manifests are executed by `docs/orchestration/runner_scripts/*.sh`;
* `julia-smoke.yml`;
* `run_cases.jl`.

The consumers are `hall_map.py`, `hall_ensemble.py`, `hallmap_registry.py`, `thermal_life.py` and the score / freeze /
forensics scripts. The proposed `abep-julia-bridge` crate works as follows:

* it keeps the process boundary and the JSON / JSONL contract, so the Julia scripts are unchanged;
* bridge parity is a launch-equivalence check: argv, environment allow-list and input bytes, plus `EXACT_BYTES` run records;
* the pin is checked on both sides (`PINNED.toml` / `Manifest.toml` in Rust, `check_pin()` in Julia);
* each run gets an execution-provenance sidecar;
* Hall-map types are generated from `hall_map_schema_v1.json`;
* `HallMap` still loads admitted members only, and the credible set is ∅ today;
* there is no in-process embedding.

In v2 the bridge is admitted in **W8**, together with the Hall-transport validation / O4 tooling. In v1 it was W18a. The
executed campaign runner scripts are class H and are not ported.

## 9. Proposed Cargo workspace layout (proposal only: no crate is created by this record)

```
Cargo.toml                  # NEW workspace root (members = crates/*); abep_core/ stays OUTSIDE the workspace
rust-toolchain.toml         # pinned toolchain (1.94.1 = parity_report_v2 build_provenance.rustc)
crates/
  abep-types/        units, shared records, error/status enums, Python-compatible JSON float formatter, schema types
  abep-provenance/   sha256, manifests, config / architecture / model-set / design-state-set hashes, bid_source_manifest +
                     migration_state readers, run-record sidecars
  abep-rng/          numpy-compatible PCG64 + SeedSequence + Generator (EXACT_STREAM); re-exports the Kernel-1 stream
  abep-config/       config/** loaders, operating scenario (mission_scenario_v2, immutable), engineering constraints
                     (incl. the HC-09 Option-1 generation filter), gate thresholds
  abep-data/         frozen dataset readers (atmosphere_msis21_v1, orbit v1 / v2, design-state sets, intake_surface_v1,
                     golden_v2, rates/)
  abep-atmos/        atmosphere / orbit (W1E, W1, W6); HWM14 executable wrapper; optional `msis-build` (RM-OQ-02)
  abep-intake/       TPMC response layer + F1 (W1); depends on abep_core (Kernel 1) by path
  abep-gaspath/      intake collection, compressor, reservoir, rotor strength, AO chemistry, K-GASPATH, K-GAS-LIFE,
                     F2-F4 synthesis, A9.13 upstream rules (W2)
  abep-chem/         rate tables + HallThruster.jl rate-table builders (W7); no 0-D global source model
  abep-mission/      mission_env propagation, statewise, spacecraft reference drag (W1 / W3)
  abep-subsystems/   power (A9 bus boundary v1 / v2, H-1 magnet power), thermal (icp_thermal_lib P3 rays, thermal_life
                     Hall-discharge / magnet parts, the post-bid cathodeless successor model), mass (K-MASS-RULES + the
                     AFI-02-resolved successor), Xe accounting v3; NO cathode library
  abep-hall/         HallMap / ensemble gate / registry (schema-typed); NO 0-D Hall
  abep-julia-bridge/ HallThruster.jl process bridge (section 8)
  abep-icp/          F6 ICP geometry + bench / impedance reducers (W9)
  abep-design/       F7 coupled architecture optimizer, F8 robust optimizer (the active UQ driver), A9.19 architecture
                     rules incl. the hollow-cathode refusal guard, H-1 geometry (W1E / W4)
  abep-uq/           seeded scenario sampling used by F8; no uq6 / uq_modular / mission_uq / Sobol port
  abep-assess/       design gates HC-01..HC-12 (HC-12 NOT_EVALUATED until evidence); physics crates may NOT depend on it
  abep-evidence/     byte-exact JSON / CSV / MD / xlsx / docx writers + one module per class-A builder (W15)
  abep-parity/       contract runner, classification gate, captured-reference comparison, golden comparator
  abep-perf/         performance harness (active workloads only)
  abep-cli/          the `abep` binary (W14): sweep, golden check, build <evidence>, hall …, parity …, perf …, ci …
abep_core/                  UNCHANGED standalone crate (Kernel 1); consumed as a path dependency after a registered
                            build-equivalence addendum; its PyO3 feature retires at W17
```

Changes from v1:

* `abep-closure` is dropped, because the legacy system closure, archengine, arch_compare and breakeven are class H;
* `abep-hall` loses the 0-D legacy Hall;
* `abep-subsystems` loses the cathode library;
* `abep-icp` is added;
* `abep-uq` is slimmed.

No crate hosts class-H logic. The dependency rule is checked mechanically:

```
types ← provenance ← config / data ← physics crates (atmos, intake, gaspath, chem, mission, subsystems, hall, icp)
      ← design / uq ← assess ← evidence ← cli
```

Physics crates never depend on `abep-assess` or `abep-evidence`, and no crate depends on class-H / G / F code.

## 10. Order and prioritisation (items 6 and 7; `migration_order_v2.json`)

**The `PRE_RUST_REFERENCE_BASELINE` orders the waves; it never gates them.** It was measured on `5eee4b8` and registered at
`adce2e9`, and A9.27 accepts it as post-freeze evidence. All active Python is scheduled for retirement whatever its speed
benefit.

**Ordering key (A9.27 sec. 4; RM-R25):**

1. architecture relevance: the four classes decide *whether* something is ported;
2. evidence / parity eligibility: a retained-physics reference must exist;
3. measured performance, which only orders what the first two admit.

So a slow legacy workload is retired, never ported because it is slow. The active intake response-surface work stays a genuine
migration and performance target.

Its ranking maps onto v2 like this. "Addressable" is interpreter time the baseline counts as removable.

| rank | workload | addressable s | v2 role |
|---:|---|---:|---|
| 1 | `uq_modular_run_uq` | 94.86 | **not a port target** (class H, section E); motivates retirement |
| 2 | `intake_response_surface_reduced` | 88.98 | W1: TPMC response layer on the admitted Kernel 1 |
| 3 | `archengine_close_architecture` | 16.28 | **not a port target** (class H, section E); motivates retirement |
| 4 | `system_evaluate_gas_path` | 2.89 | W2: extracted kernel `K-GASPATH` |
| 5 | `mission_run_generic` | 2.14 | W3: `mission_env.propagate` only (the mission5 / archengine-map driver is class H) |
| 6 | `compressor_size_for` | 1.91 | W2 |
| 7 | `uq6_robust_design` | 1.26 | **not a port target** (class H, section E); the active UQ driver is F8 (W4), which is not in the baseline's fixed workload set |
| 8 | `p3_view_factors_verify` | 0.04 | W5: `icp_thermal_lib` (source-identical to the profiled P3 function) |

112.40 s of the 208.36 s addressable total sits on retired paths. Among the port targets the ranking is:

* W1: 88.98 s;
* W2: 4.80 s;
* W3: 2.14 s;
* W5: 0.04 s.

W4 is unprofiled and keeps its item-7 place. **This is exactly the owner's item-7 initial order, so no item-7 wave moves.**
W6–W17 are unprofiled and keep the item-7 list order.

| wave | scope | components | lines |
|---|---|---:|---:|
| W0 | TPMC intake kernel (Kernel 1), **ADMITTED** | 1 | 475 |
| W1E | enablers pulled forward: constants, materials, configuration, operating inputs, engineering constraints, frozen atmosphere reader, A9.19 architecture rules | 7 | 1,220 |
| W1 | intake / design-state geometry sweep: TPMC response layer, intake, intake surface v2 spec, F1, atmosphere_orbit (design-state producer), statewise, spacecraft reference drag | 7 | 4,507 |
| W2 | compressor design search / gas path: compressor, reservoir, rotor strength, AO chemistry, F2, F3, F4, A9.13 upstream + `K-GASPATH`, `K-GAS-LIFE` | 8 | 5,280 |
| W3 | mission propagation: `mission_env` | 1 | 173 |
| W4 | UQ / Monte Carlo driver = the **active F8 robust optimizer** (not uq6 / uq_modular), with F7, H-1 geometry and the A9 bus boundary v1 / v2 pulled forward | 5 | 2,857 |
| W5 | P3 ray sampling: `icp_thermal_lib` (cathode-free); the post-bid cathodeless successor thermal model joins when it exists; the P3 v2 cathode node is **not** ported | 1 | 509 |
| W6 | atmosphere / orbit wrappers: HWM14 orbit atmosphere v2 | 1 | 1,180 |
| W7 | chemistry support for HallThruster.jl: rate tables, rate-table builders, closed N2 audits, O / O2 v0, D-X5 | 24 | 4,615 |
| W8 | Hall accelerator interface (HallMap, ensemble gate, registry) + Rust↔Julia bridge + Hall-transport validation / O4 tooling | 27 | 8,383 |
| W9 | ICP neutralizer design (F6, bench / impedance helpers) + H-1 magnet power | 3 | 1,316 |
| W10 | thermal / life accounting: `thermal_life` (Hall discharge / magnet; LaB6, RF and ECR parts not ported) | 1 | 979 |
| W11 | mass and Xe accounting: Xe accounting v3, `K-MASS-RULES`; the mass record successor after AFI-02-RA1 | 1 | 1,430 |
| W12 | assessment and hard gates: design gates HC-01..HC-12, F7 / F8 programme runners | 2 | 802 |
| W13 | configuration builders / loaders and hash verification | 1 | 980 |
| W14 | CLI: the new `abep` entry point (no Python entry point is ported) | 0 | 0 |
| W15 | evidence builders of the active chain: a (12) design synthesis / architecture, b (22) A9 hall_icp experiments, hardware, interfaces, procurement, evidence registers, c (5) requirements, decisions, owner questions, bid package | 39 | 74,565 |
| W16 | CI / check / parity / performance utilities and the test suite | 6 | 66,703 |
| W17 | final: retire the abep_core PyO3 binding layer and every remaining Python entry point; static proof that no active path imports class H | 1 | – |
| lane GR | `GROUND_REFERENCE_ONLY`, on demand (H2-1..H2-7) | 7 | 12,502 |
| lane RET | `HISTORICAL_LEGACY_REGRESSION`, not ported; retired from the production graph post-bid | 84 | 73,767 |
| lane AFI | `ACTIVE_FLIGHT_INCONSISTENCY`: `mass_power_a9_v5` until AFI-02-RA1 | 1 | 874 |

`abep_sim/intake_tpmc.py` is counted in both W0 and W1. These prerequisites come from `migration_order_v2.json`:

| id | prerequisite | what it blocks |
|---|---|---|
| P-01 | owner review and merge of this plan | every wave |
| P-02 | the post-bid, separately governed **active `hall_icp_neutralizer` golden** (A9.25 msg 2 secs. 6 and 9) | the Rust golden check, and the preferred parity reference of `K-GASPATH` / `K-GAS-LIFE`. W2 may proceed against captured Python outputs |
| P-03 | AFI-02-RA1 | the mass record successor in W11 |
| P-04 | the cathodeless successor thermal model, if required | only its own W5 contract |
| P-05 | owner confirmation of the provisional classes | nothing scheduled |

The migration does not stop after W5: the objective is zero Python. Classes G and H reach the end state by formal
retirement, not by a port.

## 11. End-state acceptance checklist (item 14)

Python counts as eliminated only when **all** of these hold. Each item has a mechanical check (CI_PLAN.md § 5):

| # | criterion (item 14) | proposed mechanical check |
|---|---|---|
| E1 | normal simulator execution requires no Python interpreter | the `abep` CLI runs the active chain end to end in a container **without** `python3` on PATH: F1–F8, mission propagation, F8 robust UQ, assessment / gates and evidence builds. No retired (class-H) path is exercised |
| E2 | production sweeps require no Python | `abep sweep` reproduces the registered design-state-set / F1 / F7 sweep references Python-free. The legacy card sweep is retired, not ported |
| E3 | config generation/loading requires no Python | `abep config build --check` reproduces `config/MANIFEST.json` byte-identically, Python-free |
| E4 | assessment/gates require no Python | `abep assess` / hard-gate (HC-01..HC-12) outputs equal the captured references Python-free; HC-12 stays `NOT_EVALUATED` until evidence exists |
| E5 | evidence builders require no Python | every class-A builder is either ADMITTED (`abep build <id> --check` byte-identical) or FORMALLY_RETIRED_NOT_PORTED |
| E6 | normal CI requires no Python for the ABEP simulator | the simulator CI jobs contain no `setup-python`, `python`, `pip` or `pytest` steps (static workflow scan) |
| E7 | every active Python implementation has an admitted Rust replacement or is formally retired | `migration_state_v1.json` is complete: class A ADMITTED + PYTHON_RETIRED_FROM_ACTIVE (or formally retired where its disposition allows); classes G / H FORMALLY_RETIRED_NOT_PORTED (or admitted under a recorded requirement); no class F remains; the inventory re-run at the end-state commit finds no unlisted component |
| E8 | HallThruster.jl integration still works | `abep hall pin-check` + `abep hall smoke` green; Hall maps still rejected for a non-pinned commit |
| E9 | all required evidence provenance remains intact | every committed evidence file's sha256 is unchanged or superseded by a recorded version; provenance links verify under `abep ci` |
| E10 | Python remains only as immutable history | no active build / test / workflow path references the retired sources (class H and unrequired class G included); historical simulations remain reproducible from their historical commit / reference environment (RM-OQ-06); historical evidence is not deleted |

## 12. Open questions for the owner (recorded, not decided here)

* **RM-OQ-01.** Flip `tpmc_backend.DEFAULT_BACKEND` to `rust` as its own post-freeze step, or together with the W1 admission?
  *Proposed default:* together with W1; the frozen `intake_surface_v1` is unchanged.
* **RM-OQ-02.** Live NRLMSIS (and HWM14) rebuilds: a Fortran-FFI build-time feature, or a retired Python tag? *Proposed default:*
  the FFI feature.
* **RM-OQ-03.** Parity class for W4, the F8 robust optimizer, given its numpy PCG64 streams and its TPMC calls into Kernel 1. The
  options are `EXACT_STREAM` (port PCG64 + Generator, with Kernel 1 re-registered on that stream) or `STATISTICAL`. *Proposed
  default:* `EXACT_STREAM`.
* **RM-OQ-04 (revised).** v1's question (retire the 17 historical candidates) is answered for class H by A9.25 msg 2 sec. 10 and
  msg 3. What remains is the mechanics: a retired tag, a retired directory, or both, and when class H leaves the production
  import graph. *Proposed default:* a retired tag plus labelling in a governed, role-bearing model set, with no file move before
  the active golden (P-02) exists.
* **RM-OQ-05.** The Rust-era equivalent of CLAUDE.md rule 9 (5 skipped, 1 strict xfail), as an owner-approved CLAUDE.md revision.
* **RM-OQ-06 (new).** CLAUDE.md rule 2 at the end state for the historical golden_v2 cases that the Rust golden check does not
  reproduce: `architecture_closure`, `mission`, `hall`, `source_plasma`, `accelerators`, `nonconverged_reference` and
  `design_point_selection`. *Proposed default:* a historical-reproducibility job on the retired Python, outside the simulator
  CI.
* **RM-OQ-07 (new).** Confirm the 9 provisional classifications:
  * `abep_sim/plasma_chem.py` → H. It is not on the section-E list, but every consumer is legacy;
  * `compressor_downselect/` → H;
  * `feed_state_closure/` → H;
  * `capability_demo/` → H;
  * `evidence/hall_sustainment/` → A;
  * `experiments/hardware/` → A;
  * `experiments/instrumentation/` → A;
  * `scripts/experiments/s1_readiness.py` → A;
  * `scripts/experiments/s1a_readiness.py` → A.

  All nine are pivot-era or mixed-consumer items.
* **RM-OQ-08 (new).** The active golden (P-02) and the cathodeless successor thermal model (P-04) have no Python reference yet.
  Author them in Python first and then migrate, or author them directly in Rust under their own validation and golden
  governance? *Proposed default:* Python first.
* **RM-OQ-09 (new).** The CI check `h2_6_live_sources` loads the class-G H2-6 builder. Port its `verify_sources()` as a class-G
  migration the active CI genuinely requires, or retire the check with the H2 v1 history? *Proposed default:* port
  `verify_sources()` only.
