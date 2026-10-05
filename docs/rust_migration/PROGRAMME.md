# Rust migration programme v3.1 (A9.24 / A9.25 / A9.28 / A9.29): zero Python execution dependency, cathodeless active architecture

**Status: `PLAN_V3_1_A9_29_RULINGS_APPLIED`. This is a docs / plan record only.** It changes no Python, Rust, CI workflow,
configuration, frozen data or number.

## What changed from v3 (A9.29, 2026-10-05)

v3.1 applies the owner's A9.29 rulings on plan v3 (`1236f91`). The governing record is
`docs/decisions/OD_2026_10_05_A9_29_RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION.md`, read in full. The owner approved
the v3 structure and the seventeen work packages, subject only to the rulings. Nothing else changes.

**How the revision was made.** It is built on `lane-rustplan-v2` at `1236f91`, merged (no conflicts) with
`integration/simulation-complete` at `e5528bd`, which adds only the A9.29 record. The v1, v2 and v3 records stay
byte-identical. The v3.1 records are `programme_v3_1.json`, `component_inventory_v3_1.{json,md}`,
`migration_order_v3_1.json`, `parity_contract_template_v3_1.json` and `simulation_completion_programme_v1_1.json`. This
page, `SIMULATION_COMPLETION_PROGRAMME.md` and `CI_PLAN.md` are the current view.

**Merge (sec. 12).** v3.1 merges into `integration/simulation-complete` without another owner review when all of these
hold:

* the v1 / v2 / v3 records are unchanged;
* the v3.1 records are additive and versioned;
* no numerical simulation result changes;
* CI checks are green;
* the inventory has zero unclassified / provisional items;
* RM-OQ-01..12 are closed or converted into execution / evidence tasks.

It never merges into main.

**Rulings applied.** `programme_v3_1.json` `a9_29_rulings_applied` names every place each ruling lands.

* **Sec. 1: fifth class approved.** `GROUND_TEST_PROGRAMME_ONLY` is OWNER_APPROVED and stays separate from
  `ACTIVE_SELECTED_ARCHITECTURE`, `GROUND_REFERENCE_ONLY` and `HISTORICAL_LEGACY_REGRESSION`. `abep-groundtest` is
  approved. No flight-runtime crate may depend on it; a `cargo metadata` check enforces this (E14).
* **Sec. 2: RM-OQ-10, feed-state closure.**
  * A successor feed-qualification record is used if one exists before final cutover.
  * Otherwise the present outputs are frozen as immutable, hash-pinned reference evidence.
  * The historical builder is not ported. It is archive-only at cutover, and normal CI verifies artifact, hash and
    schema.
  * A live S1 / S1a feed-state need becomes a deliberate `abep-groundtest` Rust contract (RM-R33).
* **Sec. 3: RM-OQ-11, bid guard.** `bid_source_guard` protects technical source `5eee4b8` and treats `2de86ab` as the
  terminal package state. The lineage `b5849af` → `2de86ab` is kept. A later change to the bid package needs a new
  explicit owner decision.
* **Sec. 4: RM-OQ-12 closed as `PREDICTIVE_RF_ICP_MODEL_REQUIRED_FOR_SIMULATION_COMPLETE`.**
  * `NP-ICP-NEUTRALIZER` is required new physics in SC-WP-03 (RM-R34). It replaces the v3 conditional
    `NP-ICP-PREDICTIVE-MODEL`.
  * Its minimum scope covers inputs, raw outputs, system coupling, assessment separation, calibrated / uncalibrated
    modes and the validation basis.
  * Raw physics emits `I_e,cap`. `M_n = I_e,cap / I_d,max,H1 − 1` is evaluated only in assessment.
  * There is no wholesale `plasma_chem` port and no LaB6, hollow-cathode, ECR or legacy stage-1 topology.
* **Sec. 5: RM-OQ-01.** The Rust simulator calls the admitted Rust TPMC library directly. The Python wrapper default
  stays `python`. No plan step puts a `DEFAULT_BACKEND` flip to the owner (RM-R35).
* **Sec. 6: RM-OQ-02.** Production reads the frozen, hash-pinned atmosphere / design-state datasets. Rust implements
  loading, schema / domain checks, hash verification, state selection and the 196-state execution. There is no live
  NRLMSIS / HWM14 regeneration and no Fortran FFI (`msis-build`) on the critical path (RM-R36).
* **Sec. 7: RM-OQ-03.** `EXACT_STREAM` applies to the UQ / F8 design-sampling stream only. TPMC particle tracing keeps
  its admitted statistical contract (RM-R37). The v3 template had one stream choice per contract, so
  `parity_contract_template_v3_1.json` registers the two stream roles separately.
* **Sec. 8: RM-OQ-04.** No file moves during migration. At final cutover the tag `python-final-reference-<date>`, the
  branch `archive/python-final-reference`, `docs/archive/PYTHON_FINAL_REFERENCE.md` and
  `docs/archive/python_final_reference.json` are created (RM-R38, E12).
* **Sec. 9: RM-OQ-05.** The Rust-era test rule replaces Python rule 9 for active production (RM-R39, E13, CI_PLAN.md
  § 7).
* **Sec. 10: CLAUDE.md.** CA-01..CA-04 and the language direction are performed separately per A9.29 sec. 10, before
  substantive Rust implementation, in their own governance commit on `integration/simulation-complete`. This record does
  not edit CLAUDE.md (prerequisite P-07).
* **Sec. 11: end-state stack.** Rust simulator + HallThruster.jl + versioned configuration / evidence data. There is no
  production dependency on python, python3, pip, virtualenv, PyO3 or maturin. The `abep_core` PyO3 interface is
  migration tooling; its Rust TPMC becomes a normal Rust library dependency (RM-R40, E11).

**Also recorded from A9.29:**

* the sec. 13 execution lanes A–D (`SIMULATION_COMPLETION_PROGRAMME.md` § 7);
* the sec. 14 speed rules (RM-R41);
* the sec. 15 simulation-complete chain (RM-R42, § 1);
* the sec. 16 first-batch report.

**Owner questions.** None is open. RM-OQ-01..05 and RM-OQ-10..12 are OWNER_DECIDED_A9_29; RM-OQ-06..09 stay
OWNER_DECIDED_A9_28. Each question with remaining work names its execution task (§ 12).

**Inventory.** No component changes class. The feed-state closure's port disposition changes (sec. 2). Every v3
`PROPOSED` classification is recorded as `PLAN_APPROVED_A9_29` in a new field, and the v3 field stays. Unclassified 0
and provisional 0 are computed from the rows. The admission order of the work packages is unchanged.

The v3 text below is revised in place where A9.29 changes it.

## What changed from v2 (A9.28, 2026-10-05)

v3 applies the owner's A9.28 rulings on plan v2 and the simulation completion directive. The governing record is
`docs/decisions/OD_2026_10_05_A9_28_RUST_PLAN_RULINGS_AND_SIMULATION_COMPLETION_DIRECTIVE.md`: message 1 is the
rulings, message 2 the directive, both read in full.

**How the revision was made.** It is built on `lane-rustplan-v2` at `e01716d`, merged (no conflicts) with
`integration/simulation-complete` at `ea1a598`. That branch reconciled main's checkpoints #31-#36 once (record
`docs/integration/main_reconciliation_2026_10_05.json`). After owner review, v3 merges into
`integration/simulation-complete`, **not** into main (msg 1 sec. 8, msg 2 sec. 5). The v2 files (`programme_v2.json`,
`component_inventory_v2.*`, `migration_order_v2.json`, `parity_contract_template_v2.json`) and the v1 files are kept
byte-identical as history. The v3 records are `*_v3.json` / `component_inventory_v3.md`, plus the new
`SIMULATION_COMPLETION_PROGRAMME.md` / `simulation_completion_programme_v1.json`.

**Classifications ruled (msg 1 secs. 2-3; closes RM-OQ-07).**

* `mass_power_a9_v5` is reclassified from class F to `ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT` (class A,
  W11).
  * AL-07 6.0 kg is a `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT`, and `AFI-02-RA1_OPEN` stands.
  * The generic mass-accounting / margin / harness / roll-up logic migrates.
  * The 6.0 kg value is never promoted by migration to CBE, measured mass or frozen flight truth.
* `plasma_chem.py` is a `HISTORICAL_LEGACY_MODULE`. Only architecture-independent kernels are extracted, and only if
  needed. Its `system.py` path is entangled with the legacy cards and `LaB6Cathode`.
* The compressor down-select is `HISTORICAL` / `RETIRE_FROM_ACTIVE_GRAPH`.
* The feed-state closure is `GROUND_TEST_PROGRAMME_ONLY` and `NOT_FLIGHT_RUNTIME`. It is retained until successor
  feed-qualification records exist.
* The capability demo is `GROUND_TEST_PROGRAMME_ONLY` / `ACTIVE_EVIDENCE_TOOLING`.
* Hall sustainment is `REFERENCE_EVIDENCE_ONLY`.
* The hardware / instrumentation experiments are `GROUND_TEST_PROGRAMME_ONLY`.
* S1 / S1a readiness is `GROUND_TEST_PROGRAMME_ONLY` / `ACTIVE_GATE_TOOLING`. Rust equivalents are needed eventually.

**The new owner class `GROUND_TEST_PROGRAMME_ONLY`** (lane GT, crate `abep-groundtest`) is never flight runtime. No
class-F component remains.

**Owner questions decided by A9.28.**

* **RM-OQ-06.** Historical goldens are immutable and reproducible from the historical Python environment. They are not
  Rust parity cases. CLAUDE.md rule 2 applies to the ACTIVE canonical golden set; the CLAUDE.md update is a separate
  later commit. The `hall_icp_neutralizer` golden is created only from the admitted active chain.
* **RM-OQ-08.** The cathodeless thermal model is new physics. It is preregistered, implemented directly in Rust and
  admitted by independent verification, with no synthetic Python reference.
* **RM-OQ-09.** The H2-6 check semantics are ported into a generic Rust provenance verifier. The Python check is
  retired from active CI only after that verifier is admitted.

**New rules RM-R26..R32:**

* new physics;
* value-status preservation;
* historical goldens;
* replace integrity checks, never drop them;
* ground-test isolation;
* fail closed on absent evidence;
* integration discipline.

**New owner questions:** RM-OQ-10..12.

**The A9.28 protected bid record** is technical source `5eee4b8` / package-freeze record `2de86ab` (lineage `b5849af`
→ `2de86ab`).

**The simulation completion programme** (msg 2) has seventeen work packages, one per layer of section 6. It covers:

* each package's method (`EXISTING_PHYSICS_PARITY` / `NEW_PHYSICS` / `NEW_INFRASTRUCTURE_ACCEPTANCE` / audit);
* fail-closed evidence gates and admission criteria;
* the order (architecture relevance, then evidence / admission eligibility, then PRE_RUST runtime);
* the Hall physics boundary;
* the first execution sequence;
* the exit criteria: the main-merge pre-PR checklist (sec. 16), completion report A–N (sec. 18) and the zero-Python
  end state (sec. 13).

**Findings of this revision** (inventory v3):

* `bus_boundary_a9.check_startup_sequence` carries a C1 heater / keeper rule. It is ground reference and is not
  ported into flight crates.
* After RM-OQ-06, `K-GASPATH` / `K-GAS-LIFE` have no active consumer except historical golden cases. They are extracted
  only if an active consumer is confirmed.
* There is no active mission-integration or reliability implementation, so both are new elements.
* The active ICP code is evidence-gated, with no predictive plasma model (RM-OQ-12).

The v2 text below is revised in place where A9.28 changes it.

## v2 basis (A9.24 / A9.25)

The v2 revision was step 7 of the owner's order (A9.25 message 3: "only then revise/review/merge the Rust migration plan").
The earlier steps are done:

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
* The cathode-path audit v1. v2 read it as `git show b8f39b7:docs/audits/a9_24_cathode_path_audit_v1.md`; it is now
  in-tree on the integration branch as `docs/audits/a9_24_cathode_path_audit_v1.md` (merged at `dcab602`). Its classes
  are:
  * HR (historical regression);
  * GR (ground reference);
  * AFI-01..05 (active-flight inconsistency).

  Their states today: AFI-01, -03 and -05 are resolved. AFI-02 is open as a value-status action (AFI-02-RA1; A9.28).
  The owner classified AFI-04 as `HISTORICAL_REGRESSION_COMPATIBILITY`.
* `docs/performance/pre_rust_reference_baseline_5eee4b8/REGISTRATION.json` and `baseline.json` (the ranking).
* **v3:**
  * `docs/decisions/OD_2026_10_05_A9_28_RUST_PLAN_RULINGS_AND_SIMULATION_COMPLETION_DIRECTIVE.md` (md sha256
    `7877bdc9…3fb54c`; json `928e0588…41e2`), messages 1 and 2 in full;
  * `docs/integration/main_reconciliation_2026_10_05.json` (sha256 `2eae9810…5d80`).
* **v3.1:** `docs/decisions/OD_2026_10_05_A9_29_RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION.md` (md sha256
  `5c223f6d…251989`; json `51645f0e…53fc8d`), secs. 1-16 in full.

A9.24 supersedes A9.7's "do not rewrite the simulator in Rust" (`SUPERSEDED_BY_A9_24_ITEM_1`). It also supersedes A9.14
S10.3 `PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING`, per component on admission. A9.14 S10.4
(`OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`) stays in force, and `CI_PLAN.md` extends it.

Machine-readable companions in this directory:

| file | content |
|---|---|
| `programme_v3_1.json` | end state (incl. the A9.29 production stack and the sec. 15 chain), active architecture, lifecycle (incl. the new-physics lifecycle), the five-class rule (class T OWNER_APPROVED A9.29), rules RM-R01..R42, the bid record and guard (terminal `2de86ab`), integration line, item-14 checklist E1–E14, main-merge pre-PR checklist, completion report A–N, workspace, owner questions (none open), execution tasks from the A9.29 rulings, `NP-ICP-NEUTRALIZER` scope |
| `component_inventory_v3_1.json` / `.md` | 227 components (224 Python-file components + 3 non-`.py` paths; 451 Python files), each with class, basis, disposition, wave, owner dispositions (A9.28, A9.29), `classification_confidence_v3_1`, simulation-completion work package, kernels, not-ported parts; new items with no Python reference; `changes_from_v3` |
| `migration_order_v3_1.json` | waves W0–W17 and lanes GR / GT / RET / AFI; the PRE_RUST ranking mapped to them; prerequisites P-01..P-07; critical-path exclusions, parity-class assignments, archive at cutover and `NP-ICP-NEUTRALIZER` placement (A9.29) |
| `parity_contract_template_v3_1.json` | the per-component pre-registration template; v3 plus separate RNG stream roles (A9.29 sec. 7) and the A9.29 new-physics gate |
| `SIMULATION_COMPLETION_PROGRAMME.md` / `simulation_completion_programme_v1_1.json` | the simulation completion programme: seventeen layer work packages (with `NP-ICP-NEUTRALIZER` in SC-WP-03), order, Hall boundary, the A9.29 execution lanes, speed rules, the sec. 15 chain, exit criteria |
| `CI_PLAN.md` | the incremental Rust CI plan (item 8), revised for v3.1 |
| `*_v1.*`, `*_v2.*`, `*_v3.*`, `simulation_completion_programme_v1.json` | v1, v2 and v3, unchanged history |

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
* **The production stack (A9.29 sec. 11)** is the Rust simulator + HallThruster.jl + versioned configuration /
  evidence data. There is no normal production dependency on python, python3, pip, virtualenv, PyO3 or maturin. The
  present `abep_core` PyO3 interface is migration tooling. Its Rust TPMC implementation is retained and becomes a normal
  Rust library dependency. PyO3 / maturin may be retired from production after parity migration is finished.
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
* **Python source is archived, never lost (A9.29 sec. 8, RM-OQ-04).**
  * During migration no Python file moves. Python stays at its current paths where it is the parity reference.
  * At final cutover the immutable tag `python-final-reference-<date>`, the immutable branch
    `archive/python-final-reference`, `docs/archive/PYTHON_FINAL_REFERENCE.md` and
    `docs/archive/python_final_reference.json` are created. The manifest maps each Python source to its Rust replacement
    or formal retirement, then to its parity / admission evidence.
  * After all active components are admitted, Python may be removed from the active main tree. Git history is preserved
    and never rewritten. The archive tag and branch are never deleted.
  * There is no `archive/python_reference` directory in main unless a specific operational need exists.
  * Class-H and class-G Python stays reproducible from its historical commit. Historical evidence is never deleted.
* **The scope of zero Python (A9.28 message 2 sec. 13).** Normal simulation, design sweeps, mission propagation, UQ,
  assessment, gates, configuration / hash handling, the evidence / provenance builders that remain operational, and
  normal CI all run without Python. Python may remain only for archived historical reproduction, after the
  corresponding active Rust components are admitted.
* **Simulation complete (A9.28 message 2 sec. 6; A9.29 sec. 15)** means an admitted active implementation of every
  applicable selected-architecture layer (`SIMULATION_COMPLETION_PROGRAMME.md`). The full chain must run end to end
  under Rust or Rust + HallThruster.jl with zero Python production dependency, for `AIR_PRIMARY` and `XE_CONTINGENCY`:

  atmosphere / orbit → TPMC intake → filter → compressor → plenum / feed → predictive 13.56 MHz RF/ICP neutralizer +
  HallThruster.jl Hall accelerator → coupled thrust / neutralization → spacecraft drag / T − D → power → cathodeless
  thermal → mass → materials / life → mission → robust / UQ → separate assessment / gates.

  The flight conventional hollow cathode is NONE. C1 is ground test / reference only, never flight execution.
  Absent determining hardware evidence stays fail closed (`NOT_EVALUATED` / `INCOMPLETE_EVIDENCE` / `OUT_OF_DOMAIN` /
  `MODEL_ERROR`). Software completion is never a gate PASS (A9.28 msg 2 sec. 14).

## 2. Migration classification (A9.25 message 3; A9.28 message 1)

**LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust simulator.**

Each component in `component_inventory_v3_1.json` has exactly one primary class. A9.28 adds the owner class
`GROUND_TEST_PROGRAMME_ONLY`:

| class | owner rule | where it goes | components | lines |
|---|---|---|---:|---:|
| `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS` | migrate to Rust under pre-registered parity / admission | waves W0–W17 | 132 | 172,695 |
| `GROUND_REFERENCE_ONLY` | migrate only if the future active test / evidence toolchain genuinely requires it; never in flight execution | lane GR (on demand) | 7 | 12,502 |
| `GROUND_TEST_PROGRAMME_ONLY` (A9.28; OWNER_APPROVED A9.29 sec. 1) | ground-test programme tooling; never flight runtime; `ACTIVE_GATE_TOOLING` / `ACTIVE_EVIDENCE_TOOLING` need Rust equivalents eventually; hardware / instrumentation migrate where retained; the feed-state closure uses a successor record, or its outputs are frozen as hash-pinned reference evidence at cutover (A9.29 sec. 2) | lane GT (`abep-groundtest`) | 6 | 7,276 |
| `HISTORICAL_LEGACY_REGRESSION` | do not port; keep the Python implementation and historical commit / evidence for reproducibility | lane RET | 82 | 70,169 |
| `ACTIVE_FLIGHT_INCONSISTENCY` | do not port; resolve against `hall_icp_neutralizer` first, then migrate only the corrected implementation | lane AFI (empty at v3) | 0 | 0 |

**A9.28 owner dispositions (verbatim labels in `owner_disposition_a9_28`).**

| component | v2 → v3 class | owner disposition | v3 port disposition |
|---|---|---|---|
| `docs/budgets/mass_power_a9_v5/` | F → A (W11) | `ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT`; AL-07 `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT`; `AFI-02-RA1_OPEN` | `MIGRATE_GENERIC_LOGIC_PRESERVE_VALUE_STATUS` |
| `abep_sim/plasma_chem.py` | H → H | `HISTORICAL_LEGACY_MODULE`; `EXTRACT_ARCHITECTURE_INDEPENDENT_KERNELS_ONLY_IF_NEEDED` | `NOT_PORTED_EXTRACT_ARCH_INDEPENDENT_KERNELS_ONLY_IF_NEEDED` |
| `docs/architecture_comparison/compressor_downselect/` | H → H | `HISTORICAL`; `RETIRE_FROM_ACTIVE_GRAPH` | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` |
| `docs/architecture_comparison/feed_state_closure/` | H → T | `GROUND_TEST_PROGRAMME_ONLY`; `NOT_FLIGHT_RUNTIME`; `RETAIN_UNTIL_SUCCESSOR_FEED_QUALIFICATION_RECORDS_EXIST` | same (RM-OQ-10) |
| `docs/experiments/capability_demo/` | H → T | `GROUND_TEST_PROGRAMME_ONLY`; `ACTIVE_EVIDENCE_TOOLING`; never flight execution | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |
| `docs/evidence/hall_sustainment/` | A → A | `REFERENCE_EVIDENCE_ONLY`; `NOT_FLIGHT_RUNTIME` | `MIGRATE_OR_FORMALLY_RETIRE` |
| `docs/experiments/hardware/` | A → T | `GROUND_TEST_PROGRAMME_ONLY`; migrate only where the active evidence / toolchain still requires them | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` |
| `docs/experiments/instrumentation/` | A → T | `GROUND_TEST_PROGRAMME_ONLY`; migrate where retained in the active evidence / toolchain | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` |
| `scripts/experiments/s1_readiness.py` | A → T | `GROUND_TEST_PROGRAMME_ONLY`; `ACTIVE_GATE_TOOLING` | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |
| `scripts/experiments/s1a_readiness.py` | A → T | `GROUND_TEST_PROGRAMME_ONLY`; `ACTIVE_GATE_TOOLING` | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |

**A9.29 changes to the classification.**

* No component changes class.
* Class T is OWNER_APPROVED (sec. 1). Its code may be active programme / evidence / gate tooling. No flight-runtime crate
  may depend on `abep-groundtest`.
* The feed-state closure's port disposition becomes `NOT_PORTED_SUCCESSOR_RECORD_OR_FROZEN_REFERENCE_EVIDENCE` (sec. 2,
  RM-OQ-10). The A9.28 row above is kept as history.

**How the classes are read.**

* Class A means "belongs to the active selected architecture" (A9.25 msg 1 sec. 14, step 2). It therefore includes that
  architecture's design, assessment, configuration, evidence and CI toolchain, which A9.24 item 1 makes Rust-owned.
* Class T is the A9.28 owner class for ground-test programme tooling. Retained S1 / S1a / evidence gates are not flight
  physics, but they need Rust equivalents for the zero-Python end state (A9.28 msg 1 sec. 3). They live in
  `abep-groundtest`, and no flight-runtime crate may depend on it (RM-R30).
* Each classification carries its basis (owner record, audit item or repository evidence) and a confidence:
  * established: 61 components;
  * proposed by this lane: 156. In v3.1 they are recorded as `PLAN_APPROVED_A9_29` (field
    `classification_confidence_v3_1`): the owner approved the v3 structure subject only to the rulings. This is not an
    individual ruling on each component;
  * owner-decided by A9.28: 10 (the nine v2 provisional rows plus `mass_power_a9_v5`);
  * provisional: 0.
* Nothing is unclassified. Both counts are computed from the inventory rows.

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
* `plasma_chem.py`, owner-confirmed by A9.28 as a `HISTORICAL_LEGACY_MODULE`;
* the compressor down-select, owner-confirmed by A9.28 as `HISTORICAL`;
* the A5 multi-family comparison builders;
* the superseded record versions;
* the historical A5 upstream pre-ionizer campaign (A9 decision of 2026-09-29).

**What RETIRE means (A9.28 msg 2 sec. 11):**

* not imported by active production execution;
* not required by the normal simulator CLI;
* not required by normal CI, except explicit historical-regression jobs;
* not ported merely for completeness.

Historical modules stay in Git for provenance and reproducibility.

**Parity rule.** Parity is required against the authoritative Python implementation of physics the selected architecture
retains. It is not a requirement to preserve obsolete architecture errors or retired hardware topology.

**Extract-and-parity kernels.** Where a retained physical calculation sits inside a legacy module, only that function subset
is ported and parity-tested:

| kernel | inside | wave | work package | what it is |
|---|---|---|---|---|
| `K-GASPATH` | `abep_sim/system.py` | W2 | SC-WP-02 | the air-mode gas-path closure: collection → compressor → reservoir → orifice, plus AO inlet composition; `p_target_Pa` supplied. **v3: extracted only if an active consumer is confirmed** |
| `K-GAS-LIFE` | `abep_sim/archengine.py` + `abep_sim/life.py` | W2 | SC-WP-08 | the gas-state wrapper with intake / blade AO-coating life (`intake_life`, `blade_life`). **v3: extracted only if an active consumer is confirmed** |
| `K-MASS-RULES` | `docs/budgets/mass_power_a9_v3/` | W11 | SC-WP-07 | the fail-closed mass roll-up rules the v4 / v5 builders import unchanged |
| `K-P3-RAYS` | `docs/experiments/hall_icp/p3_coupled_thermal/` | W5 | SC-WP-06 | P3 ray / view-factor / plume functions, already copied verbatim (cathode-free) into `abep_sim/icp_thermal_lib.py` |
| `K-GOLDEN-COMPARE` | `abep_sim/golden.py` | W16 | SC-WP-15 | the generic golden comparison harness (tooling); in v3 it is the comparator of the new active golden |

**Why K-GASPATH / K-GAS-LIFE are gated (v3 finding).** After RM-OQ-06 their v2 active consumers are historical:

* the golden_v2 `gas_path` case and the `hall_icp_neutralizer_reference` upstream / AO keys;
* class-H `archengine.gas_path_state`.

The active F-chain reaches the compressor and the plenum through `compressor_synthesis` and `plenum_feed`. The SC-WP-02
/ SC-WP-08 contracts decide whether an active consumer exists, as does the active golden's cathode-free upstream entry
(AFI-04). Architecture relevance comes first, so the PRE_RUST rank-4 timing alone does not justify the port.

**Candidate kernels** are listed for eight modules: `thruster`, `thermal`, `ppu`, `radiation`, `mass_bom`, `life`, the
Hall reference and (A9.28) `plasma_chem`. They are architecture-independent functions with no active consumer today,
and they are extracted only when one appears (A9.25 msg 2 sec. 8; A9.28 msg 2 sec. 9). Every extracted kernel needs
provenance, an applicability domain and preregistered parity / verification. No LaB6 dependency may enter the active
chain.

Class-A modules can also contain logic that is not ported:

* `thermal_life.py`: the LaB6 emitter / evaporation, cathode node and RF / ECR source checks;
* `magnet_power.py`: the ECR resonance helper;
* `owner_decisions/`: the superseded v1–v4 question-state builders. The v5 state is stale on MPV3Q-01 (A9.27 sec. 5), so
  its post-bid successor record, not the stale v5, becomes the parity reference;
* `profile_baseline.py`: the legacy workloads.

The ground-reference parts inside class-A records stay `GROUND_REFERENCE_ONLY` and never enter flight execution. Examples:

* the C1 slot of the A9 bus boundary;
* **v3:** the `hall_c1_reference` start-up rule `bus_boundary_a9._heater_rule`, with its `c1_*` slots and peak events;
* the C1-GT Xe lines and the RFQ C1 lines;
* the C1 arm of the Hall→ICP experiments.

**AFI status (cathode audit v1 → today).**

* AFI-01 (the AL-08 C1 cathode-feed branch) is resolved in mass / power v4 / v5. The v3 record is historical evidence.
* **AFI-02 is open as a value-status action (A9.28 msg 1 sec. 2).** `docs/budgets/mass_power_a9_v5/` is no longer class
  F. It is `ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT` (class A, W11), and its generic mass-accounting /
  margin / harness / roll-up logic migrates.
  * AL-07 = 6.0 kg keeps `AL-07_VALUE_STATUS = PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT` and `AFI-02-RA1_OPEN`.
  * The committed record labels stay byte-identical: `PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR`,
    `CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE`,
    `REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE`.
  * The migration never promotes the value to CBE, measured mass or frozen flight truth (RM-R27).
  * AFI-02-RA1 remains the only action that rebases it, and the migration invents no reduction.
* AFI-03 (the P3 v2 cathode node) is resolved by owner labelling. P3 v2 is class H, and its ray kernels are already in
  `icp_thermal_lib`. The cathodeless successor thermal model is new physics, built directly in Rust (RM-OQ-08).
* AFI-04 (the golden computed through `hall_1stage`) is `HISTORICAL_REGRESSION_COMPATIBILITY`. The LaB6 path is not
  ported. The active `hall_icp_neutralizer` golden is generated only from the admitted active Rust chain (RM-OQ-06,
  SC-WP-15).
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
* **v3 findings** (`component_inventory_v3_1.json` `dependency_findings.v3_findings`, with `v3_1_updates`):
  * the C1 heater / keeper start-up rule in `bus_boundary_a9.check_startup_sequence` (ground reference, not ported);
  * `python -m abep_sim` runs the class-H legacy card sweep, so no Python entry point is ported;
  * there is no active mission integration and no active reliability implementation (new elements of SC-WP-09 /
    SC-WP-08);
  * the active ICP code is an evidence-gated framework without a predictive plasma model (RM-OQ-12). A9.29 sec. 4
    makes the predictive model `NP-ICP-NEUTRALIZER` required new physics;
  * `K-GASPATH` / `K-GAS-LIFE` lost their active golden consumer.
  * The Python tree is unchanged since `2de86ab` (`git diff 2de86ab..HEAD -- '*.py'` is empty), so the v2 dependency
    analysis carries over.

## 3. Component lifecycle

Each component has exactly one status. Status changes are recorded in a migration-state ledger, proposed as
`docs/rust_migration/migration_state_v1.json` and created by the first implementation PR (ES-1), with one row per
inventory-v3_1 component. Each change also gets a docs/HISTORY.md entry.

| status | meaning | evidence needed to enter it |
|---|---|---|
| `PYTHON_REFERENCE` | Python is authoritative and is the migration reference (class A) | default for class A, except Kernel 1 |
| `PREREG_PARITY` | a parity contract from template v3 (v2 for history) is committed **in its own commit before any comparison**. The commit fixes the reference commit and file sha256, the inputs, seeds, observables, tolerances, decision rules and the classification gate | the contract file and its sha256 recorded in the ledger |
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

**New physics (A9.28 msg 1 sec. 5; RM-R26)** follows its own lifecycle:

1. **`PREREG_MODEL`.** The preregistration (template v3_1 `new_physics_verification`) is committed in its own commit
   before any Rust code. It covers equations, energy boundaries, nodes, assumptions, domains, conservation criteria,
   analytic limiting cases and the independent evidence / validation cases. A9.29 sec. 13: no implementation before the
   preregistration is committed. Its status goes into the sec. 16 first-batch report (items F / G). A failed
   preregistration condition stops the lane for an owner decision.
2. **`RUST_IMPL`.** The Rust implementation exists.
3. **`VERIFIED`.** The analytic limiting cases, conservation, domain tests and independent verification all pass.
4. **`ADMITTED`.**

* There is no synthetic Python reference. A Python scratch calculation may serve only as an independent,
  non-authoritative cross-check.
* Admitted new-physics outputs carry `validation_status = NOT_VALIDATED` until measured evidence exists. Software
  admission is not a gate PASS.

**Kernel 1, the TPMC intake trace kernels K1–K5, is `ADMITTED`.** Its records are `abep_core/`, `parity_prereg_v2.json` +
`parity_report_v2.json`, `scripts/verify_abep_core.py` and `abep_sim/design/tpmc_backend.py`.

* `DEFAULT_BACKEND = "python"` stays unchanged during migration. It is never changed merely to make Rust look primary
  (RM-OQ-01, OWNER_DECIDED A9.29 sec. 5).
* The Rust simulator calls the admitted Rust TPMC library directly. The backend switch becomes irrelevant at final
  cutover, and no flip step exists.
* TPMC particle tracing keeps its admitted statistical parity contract (A9.29 sec. 7).
* The frozen `intake_surface_v1.*` is never regenerated because of a backend switch (CLAUDE.md rule 1).
* The response layer of `abep_sim/intake_tpmc.py` stays `PYTHON_REFERENCE` until W1.

## 4. Migration rules (binding for every contract)

RM-R01..R14 and R16..R18 are unchanged from v1 (item 1 verbatim, plus their operational consequences). RM-R15 is replaced.
RM-R19..R25 are new in v2. RM-R19, R24 and R25 gain A9.28 sources in v3, and RM-R26..R32 are new in v3. In v3.1,
RM-R24, R26, R28 and R30 gain A9.29 amendments, and RM-R33..R42 are new.

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
19. **Class gate** (five classes since A9.28).
    * A contract may be registered only for a class-A component or an extract-and-parity kernel. A class-T
      (`GROUND_TEST_PROGRAMME_ONLY`) component may also be contracted when its owner sub-disposition migrates it:
      `ACTIVE_GATE_TOOLING` / `ACTIVE_EVIDENCE_TOOLING`, or retained by the active evidence toolchain.
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
24. **The bid record is frozen** (§ 5). A9.28 msg 2 sec. 1 names technical source `5eee4b8` and package / freeze record
    `2de86ab`; the lineage is `b5849af` → `2de86ab`, both pinning `5eee4b8`. Package-level post-source bid-text updates
    happen only under an owner decision record and always pin `5eee4b8`. `mission_scenario_v2` is immutable after the
    freeze; a later change is `mission_scenario_v3`. **A9.29 sec. 3:** `2de86ab` is the terminal owner-authorized
    package state. A later change to the historical bid package needs a new explicit owner decision and never silently
    alters the frozen bid record.
25. **Ordering key** (A9.27 sec. 4; A9.28 msg 1 sec. 7, msg 2 sec. 15):
    * architecture relevance first (the classes);
    * evidence / admission eligibility second;
    * measured performance third.

    A slow legacy workload is retired; it is never ported because it is slow. The `PRE_RUST_REFERENCE_BASELINE` orders
    only active retained components.
26. **New physics** (A9.28 msg 1 sec. 5; msg 2 secs. 8, 10). Genuinely new selected-architecture physics, such as the
    cathodeless thermal model, follows the new-physics lifecycle (§ 3):
    * it is preregistered, implemented directly in Rust and admitted by independent verification;
    * no Python model is written merely to create a parity target;
    * a Python scratch calculation may only be an independent cross-check, never an authoritative active dependency.
27. **Value-status preservation** (A9.28 msg 1 sec. 2). Migration never promotes a provisional / analog / allocation
    input to CBE, measured or frozen truth. `mass_power_a9_v5` AL-07 6.0 kg stays
    `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT` with `AFI-02-RA1_OPEN` until the owner-governed rebase.
28. **Historical goldens** (A9.28 msg 1 secs. 4–5; msg 2 secs. 11–12).
    * golden_v1 / golden_v2, including their LaB6 / hollow-cathode cases, stay immutable and reproducible from their
      historical Python / reference environment.
    * They are not mandatory Rust end-state parity cases. They are not deleted, and not rewritten to match the selected
      architecture.
    * CLAUDE.md rule 2 applies to the ACTIVE canonical golden set. The CLAUDE.md update is a separate later commit, CA-01.
    * The `hall_icp_neutralizer` golden is created only from the admitted active Rust chain.
29. **Replace integrity checks, never drop them** (A9.28 msg 1 sec. 6). A Python check that active CI depends on (the H2-6
    source check) leaves active CI only after:
    * its check semantics are ported, preferably as a generic Rust provenance verifier;
    * the verifier is admitted;
    * CI is re-pointed.

    Obsolete architecture assumptions inside such checks are not ported, and historical evidence stays immutable.
30. **Ground-test isolation** (A9.28 msg 1 sec. 3; OWNER_APPROVED A9.29 sec. 1). Class-T tooling is never flight
    runtime. It lives in `abep-groundtest`, and no flight-runtime crate may depend on it. A `cargo metadata` check
    enforces this. Retained S1 / S1a / evidence gates still need Rust equivalents for the zero-Python end state.
31. **Fail closed on absent evidence** (A9.28 msg 2 secs. 7, 14). Software completion never converts `NOT_EVALUATED` /
    `INCOMPLETE_EVIDENCE` / `OUT_OF_DOMAIN` / `MODEL_ERROR` into PASS, and it never fabricates hardware evidence. The
    credible Hall transport set stays visibly EMPTY until the governed validation admits a member.
32. **Integration discipline** (A9.28 msg 2 secs. 3, 5, 16–18).
    * The plan and the implementation merge into `integration/simulation-complete`.
    * main receives one coherent admitted simulation baseline, through a NEW PR, after the pre-PR checklist and the A–N
      completion report (`SIMULATION_COMPLETION_PROGRAMME.md` § 8).
    * PR #37 is not reused.
33. **Feed-state closure** (A9.29 sec. 2, RM-OQ-10). A successor feed-qualification record is used if one exists before
    final cutover. Otherwise the present outputs are frozen as immutable, hash-pinned reference evidence, and normal CI
    verifies artifact, hash and schema. The historical builder is not ported and is archive-only at cutover. A live
    S1 / S1a feed-state need is implemented deliberately in `abep-groundtest` under its own Rust contract.
34. **Predictive RF/ICP neutralizer** (A9.29 sec. 4, RM-OQ-12). `NP-ICP-NEUTRALIZER` is required new physics.
    * It is preregistered before any implementation, with the minimum scope of sec. 4 (`programme_v3_1.json`
      `np_icp_neutralizer`).
    * Raw RF/ICP physics never carries HC-05 PASS/FAIL, requirement thresholds or RFP compliance labels.
      `M_n = I_e,cap / I_d,max,H1 − 1` is evaluated only in assessment, with the registered uncertainty rule.
    * Coupling efficiency, impedance, extraction efficiency and stable operating regions are never invented to close the
      model. Absent determining bench evidence gives uncertainty / `NOT_EVALUATED`.
    * Calibrated and uncalibrated modes carry explicit provenance and domain.
    * There is no wholesale `plasma_chem` port, no LaB6 / hollow-cathode / ECR / legacy stage-1 topology and no
      synthetic Python reference.
35. **TPMC direct call** (A9.29 sec. 5, RM-OQ-01). The Rust simulator calls the admitted Rust TPMC library directly. The
    Python wrapper default and the Python reference stay unchanged during migration. No plan step puts a
    `DEFAULT_BACKEND` flip to the owner.
36. **Frozen atmosphere** (A9.29 sec. 6, RM-OQ-02). Production uses the frozen, hash-pinned atmosphere / design-state
    datasets. Rust implements deterministic loading, schema / domain checks, hash verification, state selection and the
    196-state execution. No live NRLMSIS / HWM14 regeneration and no Fortran FFI sit on the critical path. A later
    regeneration is a separately governed native tool.
37. **RNG streams** (A9.29 sec. 7, RM-OQ-03). Design / UQ sampling is `EXACT_STREAM` with the registered numpy PCG64
    stream semantics. TPMC particle tracing keeps its admitted statistical contract and is never re-registered on the
    design stream. After Rust is authoritative, new UQ campaigns may use the registered Rust RNG policy. The migration
    parity dataset stays exactly reproducible.
38. **Python archive** (A9.29 sec. 8, RM-OQ-04). § 1 gives the rule.
39. **Rust-era tests** (A9.29 sec. 9, RM-OQ-05). `CI_PLAN.md` § 7 gives the rule. The Python 5 skips / 1 strict xfail
    are archive-era reproduction metadata.
40. **End-state stack** (A9.29 sec. 11). § 1 gives the rule.
41. **Speed without lowering the standard** (A9.29 sec. 14).
    * No new architecture trade, no optional legacy ports, no cosmetic refactors unrelated to the active chain, no
      historical builder migration merely for completeness, no premature performance optimization, and no RFP document
      work in this simulation phase unless the owner asks.
    * Speed never weakens provenance, preregistration, conservation, deterministic behaviour, model-domain checks,
      requirement / physics separation, uncertainty handling or fail-closed evidence semantics.
42. **Simulation complete is the full selected architecture** (A9.29 sec. 15). § 1 gives the chain.

## 5. Bid boundary (A9.24 items 2 and 9; A9.25 message 8 secs. 12–14; A9.27; A9.28 message 2 sec. 1)

**The A9.28 protected bid record** is technical source `5eee4b8c82a9403b6bb82d5f8d324526f5d6399b` with package /
freeze record `2de86abefacbd36ce7516d3cf017f6258bd7e7a2`.

* It is immutable historical evidence.
* Later simulation development never rewrites these records. It never makes a later commit appear to have been the
  submitted technical source.
* A9.25 / A9.27 named `b5849af` as the package / freeze record. `2de86ab` is its owner-authorised package-level
  successor (A9.27), and both pin `5eee4b8`.
* The guard protects the whole lineage `b5849af` → `2de86ab`. **RM-OQ-11 is OWNER_DECIDED A9.29 (sec. 3):** `2de86ab`
  is the terminal owner-authorized package state. A later change to the historical bid package needs a new explicit
  owner decision and must not silently alter the frozen bid record.

The v2 detail follows.

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
`default_rng` (PCG64) streams from stable ids and calls the TPMC kernel. **RM-OQ-03 is OWNER_DECIDED A9.29 (sec. 7):**

* the design / UQ sampling stream is `EXACT_STREAM`, with the registered PCG64 stream semantics in `abep-rng`;
* TPMC particle tracing keeps its admitted statistical contract, also inside F8 (`tpmc_monte_carlo`);
* a contract registers the two stream roles separately (`parity_contract_template_v3_1.json` `rng_stream_roles`);
* after Rust is authoritative, new UQ campaigns may use the registered Rust RNG policy; the migration parity dataset
  stays exactly reproducible.

A contract that fails the classification gate is `REFUSED_CLASSIFICATION`. That is a refusal to register, not a verdict.

## 7. External-dependency strategy

These choices are unchanged from v1, except where A9.29 decides them below. The full list per component is in
`component_inventory_v3_1.json` (`rust_equivalents_needed`, carried from v2; the `pymsis` entry updated for RM-OQ-02).

* **numpy / scipy.** Hand-port the algorithms the reference actually uses (`scipy.stats`, `scipy.integrate`,
  `scipy.interpolate`, `scipy.constants` pinned to scipy 1.17.1). A generic crate is not swapped in where it would change the
  algorithm.
* **pandas.** Rust uses `csv` + `serde`, with pandas-compatible formatting where committed CSVs are `EXACT_BYTES` references.
* **pymsis / NRLMSIS.** Production reads the frozen, hash-pinned dataset, so Rust needs no NRLMSIS at run time. Rebuilds
  are rule-1 model changes. RM-OQ-02 is OWNER_DECIDED A9.29 (sec. 6): no live regeneration and no Fortran FFI on the
  critical path. A later regeneration is a separately governed native tool.
* **HWM14** (`atmosphere_orbit_v2.py`, W6). Production reads the frozen HWM14 orbit v2 wind dataset. The HWM14 build /
  fetch path (gfortran) is a regeneration tool and is not on the critical path (A9.29 sec. 6).
* **matplotlib.** Figures are not evidence; parity applies to the plotted data.
* **openpyxl / python-docx / pymupdf / PIL / jsonschema / zstandard.** These map to `rust_xlsxwriter` / `calamine`,
  `docx-rs`, `pdfium-render`, `image`, `jsonschema` and `zstd`.
* **pytest → `cargo test`.** RM-OQ-05 is OWNER_DECIDED A9.29 (sec. 9): the Rust-era test rule (`CI_PLAN.md` § 7). The
  CLAUDE.md update (CA-04) is performed separately (sec. 10). Of the 162 test files, 64 exercise class H / G / F code and
  stay with the archived Python.

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

**A9.28 message 2 sec. 7** (`SIMULATION_COMPLETION_PROGRAMME.md` § 6; SC-WP-03):

* HallThruster.jl remains authoritative. No Hall physics is rewritten in Rust merely to remove Julia.
* Rust owns orchestration only.
* The interface is deterministic, version-pinned (`PINNED.toml` commit `bfb3019f…`; Julia 1.11.7) and
  provenance-recorded (one sidecar per run).
* The credible transport set is EMPTY. That absence of determining Hall calibration evidence stays visible as
  `NOT_EVALUATED`.
* Screening candidates are never turned into admitted members without the governed validation process.

## 9. Proposed Cargo workspace layout (proposal only: no crate is created by this record)

```
Cargo.toml                  # NEW workspace root (members = crates/*); abep_core/ stays OUTSIDE the workspace
rust-toolchain.toml         # pinned toolchain (1.94.1 = parity_report_v2 build_provenance.rustc)
crates/
  abep-types/        units, shared records, error/status enums, Python-compatible JSON float formatter, schema types
  abep-provenance/   sha256, manifests, config / architecture / model-set / design-state-set hashes, bid_source_manifest +
                     migration_state readers, run-record sidecars, the generic provenance verifier (RM-OQ-09)
  abep-rng/          numpy-compatible PCG64 + SeedSequence + Generator (EXACT_STREAM, design / UQ stream only); the
                     Kernel-1 TPMC stream stays its own registered RNG (A9.29 sec. 7)
  abep-config/       config/** loaders, operating scenario (mission_scenario_v2, immutable), engineering constraints
                     (incl. the HC-09 Option-1 generation filter), gate thresholds
  abep-data/         frozen dataset readers (atmosphere_msis21_v1, orbit v1 / v2, design-state sets, intake_surface_v1,
                     golden_v2, rates/)
  abep-atmos/        atmosphere / orbit (W1E, W1, W6) from the frozen hash-pinned datasets; no `msis-build` Fortran
                     FFI and no HWM14 wrapper on the critical path (RM-OQ-02, A9.29 sec. 6)
  abep-intake/       TPMC response layer + F1 (W1); calls abep_core (Kernel 1) directly as a normal Rust library
                     (RM-OQ-01, A9.29 sec. 5)
  abep-gaspath/      intake collection, compressor, reservoir, rotor strength, AO chemistry, K-GASPATH, K-GAS-LIFE,
                     F2-F4 synthesis, A9.13 upstream rules (W2)
  abep-chem/         rate tables + HallThruster.jl rate-table builders (W7); no 0-D global source model
  abep-mission/      mission_env propagation, statewise, spacecraft reference drag (W1 / W3)
  abep-subsystems/   power (A9 bus boundary v1 / v2 flight configuration, H-1 magnet power; NO C1 heater / keeper rule),
                     thermal (icp_thermal_lib P3 rays, thermal_life Hall-discharge / magnet parts, the NEW cathodeless
                     model written directly in Rust), mass (K-MASS-RULES + the mass_power_a9_v5 generic logic with the
                     AL-07 value status preserved), life / materials, Xe accounting v3; NO cathode library
  abep-hall/         HallMap / ensemble gate / registry (schema-typed); NO 0-D Hall
  abep-julia-bridge/ HallThruster.jl process bridge (section 8)
  abep-icp/          F6 ICP geometry + bench / impedance reducers (W9); NP-ICP-NEUTRALIZER raw physics (A9.29 sec. 4)
  abep-design/       F7 coupled architecture optimizer, F8 robust optimizer (the active UQ driver), A9.19 architecture
                     rules incl. the hollow-cathode refusal guard, H-1 geometry (W1E / W4)
  abep-uq/           seeded scenario sampling used by F8; no uq6 / uq_modular / mission_uq / Sobol port
  abep-assess/       design gates HC-01..HC-12 (HC-12 NOT_EVALUATED until evidence); physics crates may NOT depend on it
  abep-evidence/     byte-exact JSON / CSV / MD / xlsx / docx writers + one module per class-A builder (W15)
  abep-groundtest/   class-T ground-test programme tooling (S1 / S1a gates, capability demo, hardware / instrumentation
                     definitions); no flight-runtime crate may depend on it (RM-R30)
  abep-parity/       contract runner, classification gate, captured-reference comparison, golden comparator
  abep-perf/         performance harness (active workloads only)
  abep-cli/          the `abep` binary (W14): sweep, golden check, build <evidence>, hall …, parity …, perf …, ci …
abep_core/                  UNCHANGED standalone crate (Kernel 1); consumed as a normal Rust library (rlib, path
                            dependency) after a registered build-equivalence addendum; its PyO3 / maturin interface
                            is migration tooling and retires from production at W17 (A9.29 sec. 11)
```

Changes from v1:

* `abep-closure` is dropped, because the legacy system closure, archengine, arch_compare and breakeven are class H;
* `abep-hall` loses the 0-D legacy Hall;
* `abep-subsystems` loses the cathode library;
* `abep-icp` is added;
* `abep-uq` is slimmed.

Changes from v2 (A9.28):

* `abep-groundtest` is added;
* `abep-subsystems::thermal` hosts the new cathodeless model, written directly in Rust;
* `abep-subsystems::power` excludes the C1 start-up rule;
* `abep-provenance` hosts the generic provenance verifier.

Changes from v3 (A9.29):

* `abep-atmos` has no `msis-build` Fortran-FFI feature and no HWM14 wrapper on the critical path (sec. 6);
* `abep-intake` calls `abep_core` directly; no backend switch is ported (secs. 5, 11);
* `abep-rng` serves the design / UQ stream only (sec. 7);
* `abep-groundtest` is OWNER_APPROVED; isolation is checked with `cargo metadata` (sec. 1);
* `abep-icp` hosts `NP-ICP-NEUTRALIZER` raw physics; `M_n` and HC-05 live in `abep-assess` (sec. 4);
* no production crate depends on `pyo3` / `maturin` (sec. 11).

No crate hosts class-H logic. The dependency rule is checked mechanically:

```
types ← provenance ← config / data ← physics crates (atmos, intake, gaspath, chem, mission, subsystems, hall, icp)
      ← design / uq ← assess ← evidence / groundtest ← cli
```

Physics crates never depend on `abep-assess`, `abep-evidence` or `abep-groundtest`. No crate depends on class-H / G /
F code. The groundtest rule is checked with `cargo metadata` (A9.29 sec. 1).

## 10. Order and prioritisation (items 6 and 7; A9.28 msg 1 sec. 7, msg 2 sec. 15; `migration_order_v3_1.json`)

**The `PRE_RUST_REFERENCE_BASELINE` orders the waves; it never gates them.** It was measured on `5eee4b8` and registered at
`adce2e9`, and A9.27 accepts it as post-freeze evidence. All active Python is scheduled for retirement whatever its speed
benefit.

**Ordering key (A9.27 sec. 4; A9.28; RM-R25):**

1. architecture relevance: the classes decide *whether* something is ported;
2. evidence / parity eligibility: a retained-physics reference must exist;
3. measured performance, which only orders what the first two admit.

So a slow legacy workload is retired, never ported because it is slow. The active intake response-surface work stays a genuine
migration and performance target, and F8 robust optimisation is active and may migrate (A9.28 msg 1 sec. 7). The
`SIMULATION_COMPLETION_PROGRAMME.md` § 4 applies the same key to the seventeen layer work packages (admission order).

Its ranking maps onto v2 like this. "Addressable" is interpreter time the baseline counts as removable.

| rank | workload | addressable s | v2 role |
|---:|---|---:|---|
| 1 | `uq_modular_run_uq` | 94.86 | **not a port target** (class H, section E); motivates retirement |
| 2 | `intake_response_surface_reduced` | 88.98 | W1: TPMC response layer on the admitted Kernel 1 |
| 3 | `archengine_close_architecture` | 16.28 | **not a port target** (class H, section E); motivates retirement |
| 4 | `system_evaluate_gas_path` | 2.89 | W2: extracted kernel `K-GASPATH` (v3: only if an active consumer is confirmed) |
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
| W5 | P3 ray sampling: `icp_thermal_lib` (cathode-free); the NEW cathodeless thermal model (`NP-THERMAL-CATHODELESS`) is preregistered here and written directly in Rust (RM-OQ-08); the P3 v2 cathode node is **not** ported | 1 | 509 |
| W6 | atmosphere / orbit wrappers: the frozen HWM14 orbit atmosphere v2 reader; no HWM14 regeneration on the critical path (A9.29 sec. 6) | 1 | 1,180 |
| W7 | chemistry support for HallThruster.jl: rate tables, rate-table builders, closed N2 audits, O / O2 v0, D-X5 | 24 | 4,615 |
| W8 | Hall accelerator interface (HallMap, ensemble gate, registry) + Rust↔Julia bridge + Hall-transport validation / O4 tooling | 27 | 8,383 |
| W9 | ICP neutralizer design (F6, bench / impedance helpers) + H-1 magnet power; `NP-ICP-NEUTRALIZER` implementation after its preregistration (A9.29 sec. 4) | 3 | 1,316 |
| W10 | thermal / life accounting: `thermal_life` (Hall discharge / magnet; LaB6, RF and ECR parts not ported) | 1 | 979 |
| W11 | mass and Xe accounting: Xe accounting v3, `K-MASS-RULES`, `mass_power_a9_v5` generic logic (AL-07 value status preserved, A9.28) | 2 | 2,304 |
| W12 | assessment and hard gates: design gates HC-01..HC-12, F7 / F8 programme runners | 2 | 802 |
| W13 | configuration builders / loaders and hash verification | 1 | 980 |
| W14 | CLI: the new `abep` entry point (no Python entry point is ported) | 0 | 0 |
| W15 | evidence builders of the active chain: a (12) design synthesis / architecture, b (18) A9 hall_icp experiments, interfaces, procurement, evidence registers, c (5) requirements, decisions, owner questions, bid package | 35 | 70,887 |
| W16 | CI / check / parity / performance utilities, the test suite, the provenance-verifier cut-over and the NEW active `hall_icp_neutralizer` golden | 6 | 66,703 |
| W17 | final cutover: retire PyO3 / maturin from production (abep_core stays a normal Rust library) and every remaining Python entry point; static proof that no active path imports class H; the Python final-reference archive (A9.29 secs. 8, 11) | 1 | – |
| lane GR | `GROUND_REFERENCE_ONLY`, on demand (H2-1..H2-7) | 7 | 12,502 |
| lane GT | `GROUND_TEST_PROGRAMME_ONLY` (A9.28; OWNER_APPROVED A9.29): S1 / S1a, capability demo, hardware / instrumentation, feed-state closure (successor record or frozen reference evidence, A9.29 sec. 2) | 6 | 7,276 |
| lane RET | `HISTORICAL_LEGACY_REGRESSION`, not ported; retired from the production graph post-bid | 82 | 70,169 |
| lane AFI | `ACTIVE_FLIGHT_INCONSISTENCY`: empty at v3 (A9.28 reclassified `mass_power_a9_v5`) | 0 | 0 |

`abep_sim/intake_tpmc.py` is counted in both W0 and W1. New items with no Python reference (`NP-*`, `NI-*`) are listed
per wave in `migration_order_v3_1.json`. The work-package admission order is unchanged by A9.29 (justification in
`migration_order_v3_1.json` `work_package_admission_order_v3_1`). These prerequisites come from
`migration_order_v3_1.json`:

| id | prerequisite | what it blocks | state |
|---|---|---|---|
| P-01 | owner review of plan v3 and the merge of plan v3.1 into `integration/simulation-complete` (never into main) | every wave and Rust crate until the merge | OWNER_REVIEWED A9.29; satisfied when v3.1 merges under the sec. 12 conditions |
| P-02 | the active `hall_icp_neutralizer` golden | nothing upstream: it is an output of the admitted active chain (SC-WP-15). W2 parity uses captured Python outputs | RESCOPED_A9_28 |
| P-03 | AFI-02-RA1 | only a change of the AL-07 value or status; it no longer blocks the W11 migration | OPEN_VALUE_STATUS_ACTION |
| P-04 | the `NP-THERMAL-CATHODELESS` preregistration committed (Lane D = ES-4) | the `NP-THERMAL-CATHODELESS` implementation only | OPEN_EXECUTION_TASK |
| P-05 | owner confirmation of the provisional classes | nothing | CLOSED_OWNER_DECIDED_A9_28 |
| P-06 | the `NP-ICP-NEUTRALIZER` preregistration committed (Lane C; RM-OQ-12 OWNER_DECIDED A9.29) | the `NP-ICP-NEUTRALIZER` implementation only | OPEN_EXECUTION_TASK |
| P-07 | the CLAUDE.md governance commit CA-01..CA-04 + language direction (A9.29 sec. 10) | substantive Rust implementation | PERFORMED_SEPARATELY_PER_A9_29_SEC_10 |

The migration does not stop after W5: the objective is zero Python. Classes G and H reach the end state by formal
retirement, not by a port.

## 11. End-state acceptance checklist (item 14)

Python counts as eliminated only when **all** of these hold. Each item has a mechanical check (CI_PLAN.md § 5):

| # | criterion (item 14) | proposed mechanical check |
|---|---|---|
| E1 | normal simulator execution requires no Python interpreter | the `abep` CLI runs the active chain end to end in a container **without** `python` / `python3` / `pip` / `virtualenv` on PATH: the A9.29 sec. 15 chain for `AIR_PRIMARY` and `XE_CONTINGENCY`, F1–F8, mission propagation, F8 robust UQ, assessment / gates and evidence builds. No retired (class-H) path is exercised |
| E2 | production sweeps require no Python | `abep sweep` reproduces the registered design-state-set / F1 / F7 sweep references Python-free. The legacy card sweep is retired, not ported |
| E3 | config generation/loading requires no Python | `abep config build --check` reproduces `config/MANIFEST.json` byte-identically, Python-free |
| E4 | assessment/gates require no Python | `abep assess` / hard-gate (HC-01..HC-12) outputs equal the captured references Python-free; HC-12 stays `NOT_EVALUATED` until evidence exists |
| E5 | evidence builders require no Python | every class-A / class-T builder is either ADMITTED (`abep build <id> --check` byte-identical) or FORMALLY_RETIRED_NOT_PORTED. The feed-state closure is a successor record or frozen hash-pinned reference evidence whose artifact / hash / schema CI verifies (A9.29 sec. 2) |
| E6 | normal CI requires no Python for the ABEP simulator | the simulator CI jobs contain no `setup-python`, `python`, `pip`, `pytest`, `virtualenv` or `maturin` steps (static workflow scan) |
| E7 | every active Python implementation has an admitted Rust replacement or is formally retired | `migration_state_v1.json` is complete: class A ADMITTED + PYTHON_RETIRED_FROM_ACTIVE (or formally retired where its disposition allows); classes G / H FORMALLY_RETIRED_NOT_PORTED (or admitted under a recorded requirement); no class F remains; the inventory re-run at the end-state commit finds no unlisted component |
| E8 | HallThruster.jl integration still works | `abep hall pin-check` + `abep hall smoke` green; Hall maps still rejected for a non-pinned commit |
| E9 | all required evidence provenance remains intact | every committed evidence file's sha256 is unchanged or superseded by a recorded version; provenance links verify under `abep ci` |
| E10 | Python remains only as immutable history | Python only in the archive tag / branch and Git history (A9.29 sec. 8); no active build / test / workflow path references the retired sources (class H and unrequired class G included); historical simulations and historical goldens remain reproducible from their historical commit / reference environment (RM-OQ-06, OWNER_DECIDED A9.28); historical evidence is not deleted |
| E11 | no production dependency on PyO3 / maturin (A9.29 sec. 11) | `cargo metadata` / `cargo tree` of the production workspace contain no `pyo3` or `maturin`; `abep_core` is an rlib without its `python` / `extension-module` features |
| E12 | Python final-reference archive complete (A9.29 sec. 8) | tag `python-final-reference-<date>` and branch `archive/python-final-reference` exist; `docs/archive/python_final_reference.json` maps every inventory-v3_1 Python component to its Rust replacement or formal retirement and its evidence (each file present with its sha256) |
| E13 | Rust-era test rule (A9.29 sec. 9) | `cargo test --workspace --locked` passes every active test; no `#[ignore]` / skip outside the registered platform / hardware test class; fail-closed statuses and the empty Hall credible set are asserted (`CI_PLAN.md` § 7) |
| E14 | ground-test isolation (A9.29 sec. 1) | `cargo metadata`: no flight-runtime crate depends on `abep-groundtest` |

**Programme exit criteria (A9.28 msg 2 secs. 16 and 18).** Two more conditions apply before any final PR to main:

* the main-merge pre-PR checklist (18 items) holds;
* the completion report A–N is delivered.

`SIMULATION_COMPLETION_PROGRAMME.md` § 8 and `programme_v3_1.json` give both, with a mechanical check and an owning
work package per item. A9.29 adds checks to items 1, 3, 4, 8, 10, 12, 13 and 14 (`a9_29_check_additions`). The
simulator is never called complete before the A9.29 sec. 15 chain runs end to end with zero Python production
dependency. "Simulation complete" is never claimed from a test count.

## 12. Owner questions

**Decided by A9.28 (message 1).**

* **RM-OQ-06: OWNER_DECIDED A9.28 (sec. 4).** CLAUDE.md rule 2 applies to the ACTIVE canonical golden set.
  * Historical / withdrawn goldens remain immutable and reproducible from their historical Python / reference
    environment.
  * They are **not** mandatory Rust end-state parity cases. They are not deleted, and not rewritten to match the
    selected architecture.
  * Rust is not required to reproduce the LaB6 / hollow-cathode historical goldens.
  * CLAUDE.md is updated after the bid so the distinction is explicit. That is action CA-01, a separate later commit;
    this record does not edit CLAUDE.md.
  * The new active `hall_icp_neutralizer` golden is created only after the active Rust chain is admitted.
  * Superseded proposed default: a historical-reproducibility job outside the simulator CI. This survives as the
    mechanism for reproducing historical goldens.
* **RM-OQ-07: OWNER_DECIDED A9.28 (secs. 2-3).** The classifications and dispositions are in the § 2 table. The v2
  proposed defaults are superseded where they differ:
  * the feed-state closure and the capability demo are class T, not H;
  * hardware, instrumentation and S1 / S1a are class T, not A;
  * Hall sustainment is `REFERENCE_EVIDENCE_ONLY`;
  * `mass_power_a9_v5` is class A, not F.
* **RM-OQ-08: OWNER_DECIDED A9.28 (sec. 5).** The v2 proposed default ("Python first") is rejected.
  * No new Python cathodeless thermal model is built merely to create a Rust parity target.
  * The model is implemented directly in Rust after preregistration, and admitted by independent verification.
  * A Python scratch calculation may be only an independent cross-check.
  * Migrated existing physics follows Python reference → preregistered parity → Rust admission. New physics follows
    preregistered model → analytic / evidence validation → Rust admission.
  * The active golden is generated only from the admitted active chain.
* **RM-OQ-09: OWNER_DECIDED A9.28 (sec. 6).** The check is not simply retired while active CI depends on it.
  * The CHECK SEMANTICS are ported: source hashes, provenance, pinned owner decisions, expected values and deterministic
    source verification. A generic Rust provenance verifier is preferred, covering H2-6 and similar builders.
  * Obsolete H2-6 architecture assumptions are not ported.
  * Once the verifier is admitted and normal CI is re-pointed, the Python H2-6 source check retires from active CI.
  * Historical H2-6 evidence remains immutable.

**Decided by A9.29.** None is open. Each answer is quoted in `programme_v3_1.json` `open_owner_questions`, with the
execution task that carries the remaining work.

* **RM-OQ-01: OWNER_DECIDED A9.29 (sec. 5).** The historical Python wrapper default is not changed merely to make Rust
  look primary. The Python reference stays unchanged during migration. The standalone Rust simulator calls the admitted
  Rust TPMC library directly. The backend switch becomes irrelevant at final cutover. *Task:* ES-3 (Lane B); no flip
  step.
* **RM-OQ-02: OWNER_DECIDED A9.29 (sec. 6).** Production uses the frozen, hash-pinned atmosphere / design-state
  datasets. Rust implements deterministic loading, schema / domain checks, hash verification, state selection and the
  complete 196-state execution. A live NRLMSIS / HWM14 regeneration facility is not required for the zero-Python
  cutover, and Fortran FFI is not a critical-path dependency. A later regeneration is a separately governed native tool.
  The v2 / v3 proposed default (the `msis-build` FFI feature) is superseded. *Task:* ES-2 (Lane B).
* **RM-OQ-03: OWNER_DECIDED A9.29 (sec. 7).** `EXACT_STREAM` for the parity campaign of the active UQ / F8 sampling,
  with the registered PCG64 stream semantics. It is not applied to the admitted TPMC kernel, which keeps its statistical
  contract. New UQ campaigns after Rust authority may use the registered Rust RNG policy; the migration parity dataset
  stays exactly reproducible. The v3 idea of re-registering Kernel 1 on the design stream is rejected. *Task:* W4 /
  SC-WP-10 contract with separate stream roles.
* **RM-OQ-04: OWNER_DECIDED A9.29 (sec. 8).** No file moves during migration. The Python final-reference archive is
  created at final cutover (§ 1). *Task:* W17 (`NI-PYTHON-FINAL-REFERENCE-ARCHIVE`).
* **RM-OQ-05: OWNER_DECIDED A9.29 (sec. 9).** The Rust-era test rule (`CI_PLAN.md` § 7). The Python 5 skips / 1 strict
  xfail are archive-era metadata. *Task:* SC-WP-16 from the first `cargo test` (ES-1); CA-04 is performed separately.
* **RM-OQ-10: OWNER_DECIDED A9.29 (sec. 2).** Successor record, or frozen hash-pinned reference evidence; the builder is
  archive-only (RM-R33). *Task:* lane GT before final cutover.
* **RM-OQ-11: OWNER_DECIDED A9.29 (sec. 3).** Yes: `2de86ab` is the terminal package state; technical source `5eee4b8`;
  lineage `b5849af` → `2de86ab`. *Task:* ES-1 (`bid_source_guard`).
* **RM-OQ-12: OWNER_DECIDED A9.29 (sec. 4), closed as `PREDICTIVE_RF_ICP_MODEL_REQUIRED_FOR_SIMULATION_COMPLETE`.** The
  v3 proposed default (a predictive model only when an engineering decision needs it) is rejected. *Task:* Lane C
  (`NP-ICP-NEUTRALIZER` preregistration), then SC-WP-03 W9.

**CLAUDE.md actions (A9.29 sec. 10).** They are performed separately per A9.29 sec. 10, before substantive Rust
implementation, in their own governance commit on `integration/simulation-complete`. This record does not edit
CLAUDE.md, and historical decision files are not rewritten.

* **CA-01:** rule 2 applies to ACTIVE canonical goldens; historical goldens are archive / regression history.
* **CA-02:** the execution baseline is `integration/simulation-complete`.
* **CA-03:** stale pre-Rust / pre-bid execution wording is updated.
* **CA-04:** the Rust-era test rule (RM-OQ-05).
* **Language direction:** target simulator = Rust; Hall solver = HallThruster.jl; Python = migration reference until
  admitted, then archive-only.

## 13. Integration line and main-merge policy (A9.28 message 2 secs. 3, 5, 16, 17)

* **`integration/simulation-complete`** is the simulation integration line.
  * It is based on the development line `claude/nifty-ramanujan-w68f9z` at `dcab602`.
  * main's checkpoints #31-#36 were reconciled into it once, with history preserved, a per-file evidence resolution
    and no blanket ours / theirs. The record is `docs/integration/main_reconciliation_2026_10_05.json`.
* **This plan merges into the integration branch.** A9.29 sec. 12 authorizes the v3.1 merge without another owner
  review when its conditions hold. It never merges into main.
* **main receives one coherent admitted simulation baseline** after the 18-item pre-PR checklist and the A–N completion
  report. It arrives through a NEW PR `integration/simulation-complete → main`.
* **PR #37** is not reused or merged. It is eventually closed as `SUPERSEDED_BY_SIMULATION_INTEGRATION`, once the
  integration branch holds all governed history.
* **Divergence.** The integration branch is kept up to date with main, so another large divergence is avoided.
