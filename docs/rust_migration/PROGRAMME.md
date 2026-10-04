# Rust migration programme v1 (A9.24): zero Python execution dependency

**Status: `PROPOSED_PLAN_POST_BID_FREEZE`. This is a docs/plan record only.** It changes no Python, Rust, CI workflow,
configuration, frozen data or number. It merges only **after** the bid freeze (A9.24 item 9), so the bid source stays
pre-migration.

Governing record: `docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md`, items 1, 2, 6, 7,
8 and 14, read verbatim. Companion JSON: `OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json` (sha256
`fdbb4561ca8dc524e11200750c2c9c497865f8142f1697ae0146d2dae3e5cc3c`; the `.md` record is sha256 `9a2c950b…25b1d7`).
A9.24 supersedes two earlier records:

* the A9.7 computational-language decision ("Do not rewrite the simulator in Rust",
  `OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md`) is `SUPERSEDED_BY_A9_24_ITEM_1`;
* A9.14 S10.3 `PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING` is `SUPERSEDED_PER_COMPONENT_ON_ADMISSION`. Python stays the
  migration reference for a component until that component is admitted. After admission, new production results for it
  come from Rust.

A9.14 S10.4 (`OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`) is not superseded. CI_PLAN.md extends it.

Machine-readable companions in this directory:

| file | content |
|---|---|
| `programme_v1.json` | the end state, lifecycle, rules, bid boundary, the item-14 acceptance checklist and the workspace proposal |
| `component_inventory_v1.json` / `.md` | every active Python execution path (224 components, 442 files, 257,604 lines) |
| `migration_order_v1.json` | waves W0–W20 in item-7 order, with dependency waves and pull-forward needs |
| `parity_contract_template_v1.json` | the per-component pre-registration template, generalised from `parity_prereg_v2` |
| `CI_PLAN.md` | the incremental Rust CI plan (item 8) |

---

## 1. End state

These statements are A9.24 items 1 and 14, verbatim in substance.

* **Rust is authoritative** for physics (except the Hall solver), design-space generation, mission propagation, UQ / Monte
  Carlo orchestration, architecture closure, assessment / compliance, hard gates, configuration loading and hash verification,
  evidence builders, CLI tools, deterministic result generation, and the validation and parity tooling that is now in Python.
* **HallThruster.jl stays the authoritative Hall-discharge solver.** It stays pinned to v0.23.1, commit `bfb3019f…`
  (`hallthruster_bridge/PINNED.toml`, CLAUDE.md rule 7), and Rust drives it through a Rust↔Julia bridge (§ 7).
* **Zero Python execution dependency.** The simulator, tests, builders, evidence generation and assessment need no Python
  interpreter.
* Python source is **not deleted**. Until a component is admitted, its Python code is the migration reference. After
  that, it stays only as immutable history: in Git, under a retired tag, or in a clearly retired directory. Historical
  evidence is never deleted.

```
Rust workspace (abep)                                         Julia (pinned, unchanged)
  atmosphere/orbit · intake/TPMC · compressor/gaspath ·
  chemistry support · mission · power/thermal/mass/life ·
  UQ · design synthesis · assessment/gates ·
  config/provenance · evidence builders · CLI · CI checks
          │  abep-julia-bridge: case JSON → julia --project=hallthruster_bridge … → JSON/JSONL
          └──────────────────────────────────────────────▶  HallThruster.jl v0.23.1 (bridge_lib.jl, run_cases.jl,
                                                            campaign/p5_n2_campaign.jl, identify_worker.jl, checks/*.jl)
```

## 2. Component lifecycle

Each inventory component has exactly one status. Status changes are recorded in a migration-state ledger, proposed as
`docs/rust_migration/migration_state_v1.json` and created by the first implementation PR. Each change also gets a
docs/HISTORY.md entry.

| status | meaning | evidence needed to enter it |
|---|---|---|
| `PYTHON_REFERENCE` | Python is authoritative and is the migration reference | default for every component except Kernel 1 |
| `PREREG_PARITY` | a parity contract from the template is committed **in its own commit before any comparison**. The commit fixes the reference commit and file sha256, the inputs, seeds, observables, tolerances and decision rules | the contract file and its sha256 recorded in the ledger |
| `RUST_IMPL` | the Rust implementation exists in the workspace and passes `cargo test`. It is never served for production | Rust commit and source sha256 |
| `PARITY_PASS` | the scoring execution of the registered contract returns `ADMITTED` for every kernel / observable group | parity report (JSON + MD) committed whatever the verdict |
| `ADMITTED` | Rust is authoritative for the component, and new production results come from Rust (item 1). Results carry `implementation: rust` and the Rust commit | owner-visible HISTORY entry; ledger flip; CI job added (CI_PLAN.md) |
| `PYTHON_RETIRED_FROM_ACTIVE` | no active execution path imports or runs the Python component. The code remains as the reference snapshot or as history | a static check (no import or invocation from active paths) passes |
| `FORMALLY_RETIRED_NOT_PORTED` | the component is retired without a port (item 14 "or has been formally retired"), for example a superseded-version builder whose outputs are immutable history | an explicit owner or lane decision recorded in HISTORY. Its outputs stay byte-identical in Git |
| `NOT_ADMITTED` | a scoring execution failed | the report is kept. Only a code fix plus a **new contract version with fresh scoring seeds** may follow (`no_retuning`) |

`PARITY_PASS` and `ADMITTED` are separate states on purpose. A pass is a numerical fact. Admission makes Rust
authoritative, so it changes the production source. It has its own ledger entry and HISTORY line. The two may share one
commit for small components.

**Kernel 1, the TPMC intake trace kernels K1–K5, is `ADMITTED`** (`abep_core/`, `parity_prereg_v2.json` +
`parity_report_v2.json`, `scripts/verify_abep_core.py`, `abep_sim/design/tpmc_backend.py`). Today `DEFAULT_BACKEND =
"python"` (S10.3). Item 1 says new production results for an admitted component come from Rust. Switching the TPMC default
to Rust changes new TPMC results statistically, not bitwise, because the RNG streams differ by construction. It is therefore
proposed as its own governed post-freeze step (open question RM-OQ-01). The frozen `intake_surface_v1.*` is **not**
regenerated because of that switch (CLAUDE.md rule 1). The rest of `abep_sim/intake_tpmc.py` (`intake_response`,
`response_surface`, `build_frozen_surface`, `IntakeSurface`) stays `PYTHON_REFERENCE` in W1.

## 3. Migration rules (binding for every contract)

The first nine rules are item 1 verbatim. The others are their operational consequences.

1. **No big bang.** Migration goes component by component, or by a tightly coupled group that one contract names. A wave is
   a scheduling unit, never an admission unit.
2. **Exact input parity.** Both implementations consume byte-identical inputs. The contract lists each input file with its
   sha256, plus the frozen datasets, config files and design-state sets.
3. **Exact architecture/config hashes.** Both runs record the same architecture hash, config hash (`config/MANIFEST.json`),
   model-set hash and design-state-set hash. A mismatch voids the comparison.
4. **Deterministic seeds where applicable.** The contract fixes seeds, the seed derivation and a development seed. The scoring
   seed is spent only by a scoring execution, and it is spent once.
5. **Tolerances pre-registered before any comparison.** Each observable gets a tolerance class (§ 5). The contract is committed
   before the first Python-vs-Rust comparison is run.
6. **Output-schema parity.** Field names, units, types, ordering where it carries meaning, and the `schemas/` JSON schemas must
   all match. Generated JSON or CSV used as evidence must be **byte-identical** where the contract says so. That needs a
   Python-compatible float formatter: `repr`-style shortest round trip, `1e-05` exponent form, the `indent=1` layout and
   pandas `to_csv` formatting.
7. **Conservation checks.** Source mass and power balances close exactly, and the architecture energy ledger residual stays
   below 2 % (CLAUDE.md rule 4). These checks run on the Rust outputs themselves, not only as differences from Python.
8. **Domain/error parity.** Out-of-domain and invalid inputs fail in the same way. That covers the error class or status code
   and the message key, plus `sustained=False`, `MODEL_ERROR` and `INFEASIBLE` statuses (CLAUDE.md rule 3). Each documented
   divergence is listed in the contract, as `DIV-01` is in parity v2. Silent fallbacks stay forbidden.
9. **Performance measurement.** Wall-clock and CPU time for both implementations are recorded on one machine in one session.
   **Performance is reported, never a decision criterion.**
10. **Provenance.** Every contract and report records the Python reference commit, the reference file sha256 values, the Rust
    commit, the Rust source sha256 values, the toolchain (`rustc`, Cargo.lock sha256), the Julia version and HallThruster commit
    where relevant, and the thread/BLAS environment.
11. **Never rewrite Python results or goldens to make Rust pass.** `golden_v2.json`, frozen datasets, fixtures and committed
    evidence are the reference. A disagreement is a finding to **investigate**. It is classified as a Rust defect, a Python
    reference defect (which is then fixed under its own governance, with HISTORY, golden regeneration if needed, and a new
    contract version), or a contract defect (which also gets a new contract version). It is never classified as a tolerance
    adjustment.
12. **`no_retuning`.** After a `NOT_ADMITTED` verdict, only a code fix plus a new contract version with fresh scoring seeds
    may follow. The failed report stays on record, and no execution is discarded.
13. **Reference freeze.** A contract binds the reference file sha256. If the Python reference changes, the campaign refuses
    (`REFUSED_REFERENCE_CHANGED`) until a new contract version is registered, as in parity v2.
14. **Layer separation is preserved.** The A9.22 / A9.23 physics, design, programme and assessment separation, and A9.24 items
    3–5 (physics emits `T_available`; assessment evaluates thresholds; HC-05..HC-12 are assessment-only, except HC-09 Option
    1), become **crate dependency rules**. Physics crates cannot depend on `abep-assess`, and `cargo-deny` / a graph test
    enforces that.
15. **Known physics inconsistencies are ported as they are.** A9.24 item 13 says LaB6 paths must not be fixed silently inside
    the migration. `abep_sim/cathode_integration.py` and `abep_sim/plasma_devices.py` reproduce the reference behaviour until
    the item-13 audit classifies them and the owner decides.
16. **Rule-1/2 data stays frozen.** No migration step regenerates `atmosphere_msis21_v1.*`, `intake_surface_v1.*`,
    `golden_v2.json` or `rates/`. Rust reads them byte-for-byte.
17. **Kernel granularity is allowed.** A contract may admit a function subset of a module, as Kernel 1 did. This lets the
    item-7 order go ahead even though several W1–W5 modules import later-wave modules (`migration_order_v1.json`
    `pulled_forward_dependencies_detected`). The module retires from active Python only when all its functions are
    admitted.

## 4. Bid boundary (items 2 and 9)

* The bid technical baseline is the **last fully verified pre-migration commit**: the item-9 bid freeze, which is a new
  freeze and not `bbc480c`. Its SHA is recorded by the item-9 lane in `docs/bid/bid_technical_baseline.json`, and it is
  **PENDING** at this record's base commit. This programme starts only after that SHA is recorded, and this lane merges only
  after it.
* **No partially migrated mixed implementation may silently become the bid source.** Proposed mechanical guard. It is
  implemented by the first migration implementation PR, not here:
  1. **`docs/bid/bid_source_manifest_v1.json`**, generated once at the bid-freeze commit. It contains the commit, the tag and
     the sha256 of every file the bid package cites or executes: `abep_sim/**`, `config/**`, `abep_sim/data/**`, the
     builders and outputs cited by `docs/bid/package/`, and `abep_core/` sources together with `DEFAULT_BACKEND`. It also
     contains the migration state at the freeze: every component `PYTHON_REFERENCE`, Kernel 1 `ADMITTED` as an optional
     backend with the default `python`.
  2. **`migration_state_v1.json`** (§ 2) gets one field per component, `authoritative_implementation`, with the value
     `python` or `rust`.
  3. **CI check `bid_source_guard`**, a new `scripts/ci_checks.py` check while Python CI exists and an `abep ci` subcommand
     afterwards. It fails when **any** of these is true:
     - a file in `docs/bid/package/` is regenerated and its inputs' sha256 values differ from `bid_source_manifest_v1.json`,
       unless an owner re-freeze record names a new manifest;
     - any evidence file cited by the bid package carries `implementation: rust` provenance;
     - `migration_state_v1.json` lists a component as `rust`-authoritative and the bid package's cited source files are not
       the manifest's frozen versions.
  4. **Tag protection.** The bid tag is immutable. The bid package build (`docs/bid/package/build_package.py`) prints and
     checks the manifest commit and refuses to run from any other tree. When ported, it does the same in Rust.
  5. **Rust result provenance.** Every Rust-produced result carries `implementation`, `rust_commit` and `contract_id`, so no
     Rust number enters a Python-era artefact unlabelled.
* An owner re-freeze is the **only** way a post-migration state becomes a bid source.

## 5. Parity classes

| class | applies to | rule |
|---|---|---|
| `EXACT_BYTES` | generated JSON / CSV / MD evidence, manifests, hashes, config outputs | byte-identical files (sha256 equal) |
| `EXACT_VALUE` | integers, strings, enums, statuses, booleans, error codes, schema shape | equal |
| `ULP_BOUNDED` | closed-form floating point arithmetic, and transcendental functions where libm may differ | `|Δ| ≤ k ulp` or a relative bound `≤ r`, with k and r pre-registered per observable. The default proposal is k = 4 and r = 1e-12; the contract decides |
| `SOLVER_TOLERANCE` | iterative solvers (root finding, ODE, optimisation) | convergence status `EXACT_VALUE`; the solution is within a pre-registered abs/rel tolerance tied to the solver tolerance; iteration counts are reported, not scored |
| `STATISTICAL` | RNG-driven results when the streams differ | the `parity_prereg_v2` method: per-test `|Δ| ≤ z·√(se_py² + se_rs²)` with z = 5, an aggregate bias bound, exact invariants, and a no-retuning rule |
| `EXACT_STREAM` | RNG-driven results when Rust ports numpy's bit generator **and** its distribution algorithms (PCG64 / SeedSequence; ziggurat normal and exponential; Lemire integers) | treated as `ULP_BOUNDED` or `EXACT_BYTES`. This is preferred for UQ / Monte Carlo evidence, so goldens and fixtures can be reused without statistical slack. The contract states which class applies |

Kernel 1 used `STATISTICAL` with xoshiro256++, and that admission stands. For W4 (UQ / Monte Carlo) the proposal is
`EXACT_STREAM`, by porting numpy's PCG64 and Generator algorithms into `abep-rng`. The W4 contract decides (RM-OQ-03).

## 6. External-dependency strategy

The full list per component is in `component_inventory_v1.json` (`rust_equivalents_needed`).

* **numpy / scipy.** Rust uses `ndarray` or plain vectors. The scipy routines actually used (`scipy.stats`,
  `scipy.integrate`, `scipy.interpolate`, `scipy.constants`) are **hand-ported to match the reference algorithm**. A
  generic crate is not swapped in, because different algorithms break `ULP_BOUNDED` parity. `scipy.constants` values are
  pinned to scipy 1.17.1.
* **pandas.** Rust uses `csv` + `serde`, with pandas-compatible float formatting where committed CSVs are `EXACT_BYTES`
  references.
* **pymsis / NRLMSIS.** Production reads the **frozen** dataset (`atmosphere_msis21_v1.*`, gate 1), so Rust needs no
  NRLMSIS at runtime. Live MSIS is used only for intentional dataset rebuilds (`python -m abep_sim.atmosphere build`, rule
  1). The options are (a) NRLMSIS 2.1 Fortran through `cc` / FFI as a build-time tool in `abep-atmos` (feature `msis-build`),
  or (b) keeping rebuilds on a retired Python tag, with the rebuild being a rule-1 model change in any case. RM-OQ-02 is the
  owner's choice. HWM14 (`atmosphere_orbit_v2.py`) already runs as a compiled Fortran executable through `subprocess`, and
  Rust keeps that through `std::process::Command`.
* **matplotlib.** Figures are renderings and not evidence. Parity applies to the plotted data series. `plotters` is
  optional.
* **openpyxl / python-docx / pymupdf / PIL / jsonschema / zstandard.** These map to `rust_xlsxwriter` / `calamine`,
  `docx-rs`, `pdfium-render`, `image`, `jsonschema` and `zstd`. Digitisation tools (pymupdf) are build-time tools, and
  their outputs are frozen evidence.
* **pytest.** `cargo test`. CLAUDE.md rule 9 (the expected 5 skipped and 1 strict xfail) needs a mapped Rust equivalent,
  and that mapping is an owner-approved CLAUDE.md revision at end state (RM-OQ-05). This plan does not change CLAUDE.md.

## 7. Rust↔Julia bridge (HallThruster.jl stays authoritative)

**How Python drives Julia today.** It is out of process and file-based. Python never embeds Julia.

| path | mechanism |
|---|---|
| `scripts/identify_p5_transport.py` | writes job chunks as JSON, then `subprocess.Popen(["julia", "--project=hallthruster_bridge", "hallthruster_bridge/identify_worker.jl", jobs.json, results.jsonl])` per worker, `wait()`, and reads JSONL back |
| `scripts/make_p5_n2_launch_manifests.py` | emits exact command lines `julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign.jl <out>/s{i}.jsonl <mode> {i} 4 <chem,…>` into pinned manifests, plus `--check` (the structural gate on the records) |
| `docs/orchestration/runner_scripts/*.sh` | bash runners that launch the manifests' Julia commands and use inline `python -c` for manifest fields and provenance |
| `.github/workflows/julia-smoke.yml` | Python reads `PINNED.toml` / `Manifest.toml`, then `julia … check_pin()`, then the campaign smoke |
| `hallthruster_bridge/run_cases.jl` | the CLI `cases.json → out.json`, with output in the `hall_map_schema_v1.json` field set |
| consumers | `abep_sim/hall_map.py` (derives `REQUIRED_FIELDS` from the schema and rejects any non-pinned commit), `hall_ensemble.py` (`_check_o4` admission gate), `hallmap_registry.py`, `thermal_life.py` (pin check), and the `score_p5_n2_*` / `freeze_p5_n2_dataset.py` / forensics scripts |

Julia enforces its side: `check_pin()`, the pre-registration lock sha256, `rate_validity.toml` coverage and
`chemistry_trustworthy`.

**Proposed Rust equivalent (`abep-julia-bridge` crate):**

1. **Keep the process boundary and the file contract.** Rust writes the same case / job JSON bytes, spawns
   `julia --project=hallthruster_bridge <script>.jl <args>` through `std::process::Command`, and reads JSON / JSONL with
   `serde`. The Julia scripts stay unchanged. Julia sees identical inputs, so its outputs are bitwise identical for the same
   Julia version, thread count and BLAS. That makes bridge parity a **launch-equivalence** check: the same argv, environment
   allow-list and input bytes, then a run-record comparison under `EXACT_BYTES` for deterministic records.
2. **The pin is checked on both sides.** The Rust side parses `PINNED.toml` and `Manifest.toml` and refuses a commit other
   than `bfb3019f…` (today's `hall_map.py` rule). It still calls `check_pin()` in Julia before any run.
3. **Execution provenance per run** (CLAUDE.md, future campaigns): Julia version, HallThruster commit, thread/BLAS
   environment, host, argv and input sha256 values. These go into the run record sidecar.
4. **Schema-typed Hall maps.** `abep-hall` generates its record types from `hall_map_schema_v1.json` at build time
   (`build.rs`). A test checks that the field set equals the schema, as `hall_map.py` does today. The `trustworthy` /
   `wall_life_trustworthy` / `chemistry_trustworthy` and `meta.ensemble_member_id` rules move over unchanged. `HallMap`
   still loads admitted members only (credible set = ∅ today).
5. **Shard orchestration** (today `subprocess.Popen` per worker): Rust worker processes with a resumable JSONL append
   (skip keys already present, as `p5_n2_campaign.jl` does), and a transactional trigger ledger (`trigger_ledger_v2.jsonl`
   semantics).
6. **Not proposed now: in-process embedding** (for example `jlrs`). It would couple the Rust and Julia runtimes, garbage
   collectors and threads, and it would need its own parity contract. The process boundary keeps HallThruster.jl's behaviour
   exactly as validated.
7. **CI.** `julia-smoke.yml` gets a Rust-driven variant. `abep hall pin-check` and `abep hall smoke` replace the inline
   Python, and the Julia steps stay identical (CI_PLAN.md § 4).

## 8. Proposed Cargo workspace layout (proposal only: no crate is created by this record)

```
Cargo.toml                  # NEW workspace root (members = crates/*); abep_core/ stays OUTSIDE the workspace (below)
rust-toolchain.toml         # pinned toolchain (1.94.1 today = parity_report_v2 build_provenance.rustc)
crates/
  abep-types/        units, shared records, error/status enums (MODEL_ERROR, INFEASIBLE, sustained), Python-compatible
                     JSON float formatter, serde schemas generated from schemas/**
  abep-provenance/   sha256, file manifests, config/architecture/model-set/design-state-set hashes, commit capture,
                     bid_source_manifest + migration_state readers, run-record sidecars
  abep-rng/          numpy-compatible PCG64 + SeedSequence + Generator distributions (EXACT_STREAM); re-exports the
                     abep_core xoshiro256++ stream for Kernel 1
  abep-config/       config/** loaders (SOURCES_OF_TRUTH, MANIFEST), operating scenario (A9.24 item 4, independently
                     versioned values), engineering constraints (incl. HC-09 Option 1 generation filter)
  abep-data/         frozen dataset readers: atmosphere_msis21_v1, orbit v1/v2, design-state sets, intake_surface_v1,
                     golden_v2, rates/
  abep-atmos/        atmosphere / orbit wrappers; HWM14 executable wrapper; optional `msis-build` feature (RM-OQ-02)
  abep-intake/       TPMC response layer + F1 intake synthesis; depends on abep_core (Kernel 1) by path
  abep-gaspath/      compressor (+ transitional), filter stage, plenum feed, reservoir, rotor strength, F2-F4 synthesis
  abep-chem/         plasma_chem, rate_tables, aochem; rate-table builders (bin targets)
  abep-mission/      mission_env, mission5, orbit_atm, statewise, transient
  abep-subsystems/   power (ppu, magnet_power, bus boundary), thermal (thermal, thermal_life, radiation, materials,
                     P3 view factors / ray sampling), mass (mass_bom), life, xe_ledger, cathode/ICP libs
  abep-hall/         HallMap / ensemble gate / hallmap registry (schema-typed), 0-D legacy Hall (golden parity only)
  abep-julia-bridge/ HallThruster.jl process bridge (section 7)
  abep-closure/      system closure, archengine, arch_compare, breakeven, programme closure
  abep-design/       design synthesis F1-F8, architecture / robust optimisers, design-state sweep
  abep-uq/           UQ / Monte Carlo driver, Sobol, mission UQ
  abep-assess/       assessment, thresholds, hard gates HC-01..HC-12 (physics crates may NOT depend on it)
  abep-evidence/     evidence-builder framework (byte-exact JSON/CSV/MD/xlsx/docx writers) + one module per builder
  abep-parity/       contract runner: loads a parity contract, runs Rust, compares with the captured Python reference
                     outputs by tolerance class, writes the report; scoring-seed bookkeeping (campaign_history)
  abep-perf/         performance harness (port of scripts/perf/profile_baseline.py)
  abep-cli/          the `abep` binary: sweep, golden check, build <evidence>, hall …, parity …, perf …, ci …
abep_core/                  UNCHANGED standalone crate (Kernel 1). Not a workspace member while its parity v2 record binds
                            abep_core/Cargo.toml, Cargo.lock and src/* sha256: moving it, or folding it into the workspace
                            lockfile, is an UNRECORDED_SOURCE_CHANGE. The workspace consumes it as a path dependency (rlib);
                            a build-equivalence check (K1-K5 outputs on the registered vectors, development seed, bitwise
                            vs the recorded extension) is registered as a parity-contract addendum before production use.
                            Its PyO3 feature (`python`) retires at W20.
```

Dependency rule, mechanically checked:
`types ← provenance ← config/data ← physics crates (atmos, intake, gaspath, chem, mission, subsystems, hall) ← closure/design/uq
← assess ← evidence ← cli`. Physics crates never depend on `abep-assess` or `abep-evidence`. `abep-parity` and `abep-perf`
are dev / tooling crates.

## 9. Order and prioritisation (items 6 and 7)

`migration_order_v1.json` gives the waves:

* W0, TPMC kernel (admitted)
* W1E, enablers pulled forward
* W1, intake / design-state geometry sweep
* W2, compressor / gaspath
* W3, mission propagation
* W4, UQ / Monte Carlo
* W5, P3 ray sampling
* W6–W17: atmosphere / orbit, chemistry, system closure, power, thermal, mass, life, archengine / design, sweep, assessment,
  hard gates, config
* W18, evidence builders and campaign tooling, in sub-batches a–d
* W19, CI / check / parity / perf utilities and tests
* W20, retirement of the PyO3 binding layer

**Profiling orders the waves; it never gates them.** The order is re-ranked once the A9.24 item-6 pre-migration
performance rerun is registered. That rerun is **PENDING**, and the re-ranking is recorded as `migration_order_v2.json`. The
migration does not stop after the six item-7 kernels, because the objective is zero Python.

## 10. End-state acceptance checklist (item 14)

Python counts as eliminated only when **all** of these hold. Each item has a mechanical check (CI_PLAN.md § 5):

| # | criterion (item 14) | proposed mechanical check |
|---|---|---|
| E1 | normal simulator execution requires no Python interpreter | the `abep` CLI end-to-end runs (closure, archengine, mission, UQ) in a container **without** `python3` on PATH |
| E2 | production sweeps require no Python | `abep sweep` reproduces the registered sweep references (`EXACT_BYTES` / class per contract) in the Python-free container |
| E3 | config generation/loading requires no Python | `abep config build --check` reproduces `config/MANIFEST.json` byte-identically, Python-free |
| E4 | assessment/gates require no Python | `abep assess` / hard-gate outputs equal the captured references, Python-free |
| E5 | evidence builders require no Python | every W18 builder is either ADMITTED (`abep build <id> --check` byte-identical) or FORMALLY_RETIRED_NOT_PORTED |
| E6 | normal CI requires no Python for the ABEP simulator | `ci.yml` successor jobs contain no `setup-python`, `python`, `pip` or `pytest` steps (static workflow scan) |
| E7 | every active Python implementation has an admitted Rust replacement or is formally retired | `migration_state_v1.json`: every component is `ADMITTED` + `PYTHON_RETIRED_FROM_ACTIVE`, or `FORMALLY_RETIRED_NOT_PORTED`, and the inventory is re-run at the end-state commit with no new unlisted component |
| E8 | HallThruster.jl integration still works | `abep hall pin-check` + `abep hall smoke` (julia-smoke successor) green; Hall maps still rejected for a non-pinned commit |
| E9 | all required evidence provenance remains intact | every committed evidence file's sha256 is unchanged or superseded by a recorded version; the provenance links (`MANIFEST.json`, prereg locks, audit manifests, validation release) all verify under `abep ci` |
| E10 | (item 14 closing clause) Python remains only as immutable history | the Python sources sit at a retired tag / directory; no active build, test or workflow path references them; historical evidence is not deleted |

## 11. Open questions for the owner (recorded, not decided here)

* **RM-OQ-01.** Kernel 1 is admitted. Under item 1, new production TPMC results should come from Rust. Should
  `DEFAULT_BACKEND` flip to `rust` as its own post-freeze governed step (statistical, not bitwise, change of new TPMC
  results; frozen `intake_surface_v1` unchanged), or wait until W1 admits the response layer? *Proposed default:* flip
  together with the W1 admission.
* **RM-OQ-02.** Live NRLMSIS rebuilds: port as a Fortran-FFI build-time feature, or keep them on a retired Python tag?
  *Proposed default:* the Fortran FFI feature (`msis-build`), because the zero-Python end state also covers builders.
* **RM-OQ-03.** RNG class for W4 UQ / Monte Carlo: `EXACT_STREAM` (port numpy PCG64 + Generator algorithms) or `STATISTICAL`?
  *Proposed default:* `EXACT_STREAM`.
* **RM-OQ-04.** Superseded-version builders and historical-line builders (17 components flagged
  `HISTORICAL_LINE_OR_SUPERSEDED_CANDIDATE`): formally retire instead of port? *Proposed default:* retire, with outputs kept
  byte-identical, because item 14 permits formal retirement.
* **RM-OQ-05.** CLAUDE.md rule 9 (the pytest outcome contract) needs a Rust-era equivalent at end state, and that is an
  owner-approved CLAUDE.md revision.
