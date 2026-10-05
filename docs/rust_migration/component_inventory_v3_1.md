# Rust migration - component inventory v3.1 (A9.29 owner rulings applied)

**Status: `PLAN_V3_1_A9_29_RULINGS_APPLIED`.** Docs / plan only. Machine-readable: `component_inventory_v3_1.json` (authoritative; this page is a rendering). v1, v2 and v3 (`component_inventory_v1.*`, `component_inventory_v2.*`, `component_inventory_v3.*`) are kept unchanged as history. Programme: `PROGRAMME.md`; order: `migration_order_v3_1.json`; layer work packages: `SIMULATION_COMPLETION_PROGRAMME.md`. Inventoried at `2de86abefacb`; re-verified on this revision: the Python tree is unchanged since then (`git diff 2de86ab..HEAD -- '*.py'` is empty), so paths, files and line counts carry over from v2. Re-checked at v3.1: still empty.

Governing records: as v2, plus `docs/decisions/OD_2026_10_05_A9_29_RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION.md` (A9.29: secs. 1-11 rulings; sec. 12 merge condition "zero unclassified / provisional items"), plus `docs/decisions/OD_2026_10_05_A9_28_RUST_PLAN_RULINGS_AND_SIMULATION_COMPLETION_DIRECTIVE.md` (message 1 secs. 2-6: classifications, goldens, new physics, H2-6; message 2: architecture, completion definition, RF/ICP kernels, historical code, active golden, zero Python) and the cathode-path audit, now in-tree at `docs/audits/a9_24_cathode_path_audit_v1.md`.

## What A9.29 changed (v3.1)

No component changes class. No component id is added or removed (227 in v3, 227 in v3.1).

| component | change | ruling |
|---|---|---|
| class `GROUND_TEST_PROGRAMME_ONLY` (6 components) | `OWNER_APPROVED_A9_29`; `abep-groundtest` isolation approved; no flight-runtime crate may depend on it (cargo metadata check) | sec. 1 |
| `docs/architecture_comparison/feed_state_closure/` | port disposition `RETAIN_UNTIL_SUCCESSOR_FEED_QUALIFICATION_RECORDS_EXIST` -> `NOT_PORTED_SUCCESSOR_RECORD_OR_FROZEN_REFERENCE_EVIDENCE`: successor record if one exists before final cutover, otherwise frozen hash-pinned reference evidence verified by CI; builder archive-only | sec. 2 (RM-OQ-10) |
| `abep_sim/design/tpmc_backend.py` | `DEFAULT_BACKEND` stays `python`; not ported; formally retired at cutover (the Rust simulator calls the Rust TPMC library directly) | sec. 5 (RM-OQ-01) |
| `abep_sim/intake_tpmc.py` | TPMC keeps the admitted Kernel-1 statistical contract; direct library call | secs. 5, 7 |
| `abep_sim/design/robust_optimizer.py` | design / UQ sampling stream `EXACT_STREAM`; its TPMC calls keep the Kernel-1 contract | sec. 7 (RM-OQ-03) |
| `abep_sim/atmosphere.py`, `atmosphere_orbit.py`, `atmosphere_orbit_v2.py`, `orbit_atm.py`, `tests` | `pymsis` mapping decided: frozen hash-pinned data only, no live regeneration, no Fortran FFI on the critical path | sec. 6 (RM-OQ-02) |
| `tests` | Rust-era test rule; the Python 5 skips / 1 strict xfail are archive-era metadata | sec. 9 (RM-OQ-05) |
| `abep_core PyO3 / maturin binding layer` | migration tooling; retired from production after parity migration; the Rust TPMC stays a normal Rust library | sec. 11 |
| all components | new field `classification_confidence_v3_1`: `PROPOSED` -> `PLAN_APPROVED_A9_29`; others unchanged | sec. 12 / preamble |

* **`PLAN_APPROVED_A9_29`** marks a v3 `PROPOSED` classification carried unchanged into the plan structure the owner
  approved in A9.29 ("The overall structure ... APPROVED, subject only to the rulings below"). It is not an individual
  owner ruling on the component. The v3 field `classification_confidence` is kept unchanged on every row.
* **New items with no Python reference.** `NP-ICP-PREDICTIVE-MODEL` (v3, conditional) is replaced by
  `NP-ICP-NEUTRALIZER` (required, sec. 4). Added: `NI-GROUNDTEST-ISOLATION-CHECK` (sec. 1), `NI-PLATFORM-TEST-REGISTER`
  (sec. 9), `NI-FEED-STATE-REFERENCE-EVIDENCE` (sec. 2, conditional) and `NI-PYTHON-FINAL-REFERENCE-ARCHIVE` (sec. 8).
* Every changed row is listed in `changes_from_v3` of the JSON.

## What A9.28 changed (v3)

| component | v2 class / wave | v3 class / wave | owner disposition (A9.28, verbatim) | v3 port disposition |
|---|---|---|---|---|
| `abep_sim/plasma_chem.py` | HISTORICAL_LEGACY_REGRESSION / RET | HISTORICAL_LEGACY_REGRESSION / RET | HISTORICAL_LEGACY_MODULE; EXTRACT_ARCHITECTURE_INDEPENDENT_KERNELS_ONLY_IF_NEEDED | `NOT_PORTED_EXTRACT_ARCH_INDEPENDENT_KERNELS_ONLY_IF_NEEDED` |
| `docs/architecture_comparison/compressor_downselect/` | HISTORICAL_LEGACY_REGRESSION / RET | HISTORICAL_LEGACY_REGRESSION / RET | HISTORICAL; RETIRE_FROM_ACTIVE_GRAPH | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` |
| `docs/architecture_comparison/feed_state_closure/` | HISTORICAL_LEGACY_REGRESSION / RET | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; NOT_FLIGHT_RUNTIME; RETAIN_UNTIL_SUCCESSOR_FEED_QUALIFICATION_RECORDS_EXIST | `RETAIN_UNTIL_SUCCESSOR_FEED_QUALIFICATION_RECORDS_EXIST` |
| `docs/evidence/hall_sustainment/` | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | REFERENCE_EVIDENCE_ONLY; NOT_FLIGHT_RUNTIME | `MIGRATE_OR_FORMALLY_RETIRE` |
| `docs/experiments/capability_demo/` | HISTORICAL_LEGACY_REGRESSION / RET | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; ACTIVE_EVIDENCE_TOOLING; never flight execution | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |
| `docs/experiments/hardware/` | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; migrate only where the active evidence/toolchain still requires them | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` |
| `docs/experiments/instrumentation/` | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; migrate where retained in the active evidence/toolchain | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` |
| `scripts/experiments/s1_readiness.py` | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; ACTIVE_GATE_TOOLING | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |
| `scripts/experiments/s1a_readiness.py` | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W15b | GROUND_TEST_PROGRAMME_ONLY / GT | GROUND_TEST_PROGRAMME_ONLY; ACTIVE_GATE_TOOLING | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` |
| `docs/budgets/mass_power_a9_v5/` | ACTIVE_FLIGHT_INCONSISTENCY / AFI | ACTIVE_SELECTED_ARCHITECTURE_PHYSICS / W11 | ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT; AL-07_VALUE_STATUS = PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT; AFI-02-RA1_OPEN | `MIGRATE_GENERIC_LOGIC_PRESERVE_VALUE_STATUS` |

* **`mass_power_a9_v5`** is no longer class F. It is the selected architecture's engineering assessment (class A, wave W11). Its generic mass-accounting / margin / harness / roll-up logic migrates. AL-07 = 6.0 kg stays `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT` with `AFI-02-RA1_OPEN`; the migration never promotes it to CBE, measured mass or frozen flight truth. The committed record labels (`PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR`, ...) are reproduced byte-exactly.
* **`GROUND_TEST_PROGRAMME_ONLY`** is the owner's class for ground-test programme tooling (lane GT, crate `abep-groundtest`). It is never flight runtime. S1 / S1a (`ACTIVE_GATE_TOOLING`) and the capability demo (`ACTIVE_EVIDENCE_TOOLING`) need Rust equivalents for the zero-Python end state.
* **Hall sustainment** stays class A as `REFERENCE_EVIDENCE_ONLY` / `NOT_FLIGHT_RUNTIME` evidence tooling (`MIGRATE_OR_FORMALLY_RETIRE`).
* **`plasma_chem.py`** is a `HISTORICAL_LEGACY_MODULE`: not ported; its architecture-independent kernels are audited (SC-WP-03) and extracted only if the selected RF/ICP neutralizer needs them.
* No component is class F any more; the class stays in the vocabulary.

## Summary

* Python files: **451** (287 outside `tests/`); 262,642 physical lines (199,171 outside `tests/`).
* Components: **227** (224 Python-file components and 3 non-`.py` paths).
* Unclassified: **0**. Provisional: **0** (computed from the rows: no `migration_class` outside the vocabulary; no `classification_confidence_v3_1` that is provisional or proposed).
* Classification confidence v3.1: established **61**, owner-decided A9.28 **10**, plan-approved A9.29 **156**.

| class | components | lines |
|---|---:|---:|
| `ACTIVE_SELECTED_ARCHITECTURE_PHYSICS` | 132 | 172,695 |
| `GROUND_REFERENCE_ONLY` | 7 | 12,502 |
| `GROUND_TEST_PROGRAMME_ONLY` (OWNER_APPROVED_A9_29) | 6 | 7,276 |
| `HISTORICAL_LEGACY_REGRESSION` | 82 | 70,169 |
| `ACTIVE_FLIGHT_INCONSISTENCY` | 0 | 0 |
| **total** | 227 | |

| port disposition | components |
|---|---:|
| `ADMITTED_KERNEL_PLUS_MIGRATE_REMAINDER` | 1 |
| `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` | 3 |
| `MIGRATE_GENERIC_LOGIC_PRESERVE_VALUE_STATUS` | 1 |
| `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 7 |
| `MIGRATE_OR_FORMALLY_RETIRE` | 18 |
| `MIGRATE_UNDER_PREREG_PARITY` | 109 |
| `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` | 2 |
| `NOT_PORTED_EXTRACT_ARCH_INDEPENDENT_KERNELS_ONLY_IF_NEEDED` | 1 |
| `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | 81 |
| `NOT_PORTED_SUCCESSOR_RECORD_OR_FROZEN_REFERENCE_EVIDENCE` | 1 |
| `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | 3 |

| simulation-completion work package | components |
|---|---:|
| SC-WP-01 | 3 |
| SC-WP-02 | 11 |
| SC-WP-03 | 55 |
| SC-WP-04 | 3 |
| SC-WP-05 | 6 |
| SC-WP-06 | 2 |
| SC-WP-07 | 2 |
| SC-WP-08 | 4 |
| SC-WP-09 | 1 |
| SC-WP-10 | 3 |
| SC-WP-11 | 3 |
| SC-WP-12 | 7 |
| SC-WP-14 | 31 |
| SC-WP-16 | 7 |

SC-WP-13 (CLI), SC-WP-15 (active golden, plus the `K-GOLDEN-COMPARE` kernel) and SC-WP-17 (clean install) own no Python component: they are new infrastructure.

## Extract-and-parity kernels

| kernel | work package | active consumer (v3) |
|---|---|---|
| `K-GASPATH` | SC-WP-02 | v3: golden gas_path and the upstream keys of hall_icp_neutralizer_reference; archengine.gas_path_state; profiled workload system_evaluate_gas_path (PRE_RUST rank 4) - the golden_v2 consumers are historical (RM-OQ-06) and archengine is class H, so the kernel is extracted only if an active consumer is confirmed (SC-WP-02 / SC-WP-08 / the active golden's cathode-free upstream entry, AFI-04) |
| `K-GAS-LIFE` | SC-WP-08 | v3: golden hall_icp_neutralizer_reference ao_exposure_mission block - the golden_v2 consumers are historical (RM-OQ-06) and archengine is class H, so the kernel is extracted only if an active consumer is confirmed (SC-WP-02 / SC-WP-08 / the active golden's cathode-free upstream entry, AFI-04) |
| `K-MASS-RULES` | SC-WP-07 | mass_power_a9_v5 (class A since A9.28: generic logic migrates with the AL-07 value status preserved) and the F7/F8 wet-mass objective |
| `K-P3-RAYS` | SC-WP-06 | ALREADY EXTRACTED verbatim into abep_sim/icp_thermal_lib.py (source-identity test tests/test_design_layer_separation.py); the port target is icp_thermal_lib (W5) |
| `K-GOLDEN-COMPARE` | SC-WP-15 | the Rust comparator of the NEW active hall_icp_neutralizer golden (SC-WP-15); golden_v2 historical cases are NOT Rust end-state parity cases (RM-OQ-06, A9.28) |

## New items with no Python reference

| id | method | work package | wave | what |
|---|---|---|---|---|
| `NP-THERMAL-CATHODELESS` | NEW_PHYSICS | SC-WP-06 | W5 -> W10 | cathodeless Hall + RF/ICP coupled thermal model, preregistered then implemented directly in Rust (RM-OQ-08 OWNER_DECIDED A9.28); A9.29 Lane D: no implementation before the preregistration is committed |
| `NP-MISSION-INTEGRATION` | NEW_PHYSICS | SC-WP-09 | W3 | selected-architecture mission integration over mission_scenario_v2 |
| `NP-ICP-NEUTRALIZER` | NEW_PHYSICS | SC-WP-03 | prereg at plan merge (Lane C) -> W9 | predictive 13.56 MHz RF/ICP electron-source / neutralizer system model, REQUIRED for SIMULATION_COMPLETE (RM-OQ-12 OWNER_DECIDED_A9_29 sec. 4); raw physics only, M_n / HC-05 in assessment; replaces the v3 conditional `NP-ICP-PREDICTIVE-MODEL` |
| `NP-RELIABILITY` | NEW_PHYSICS | SC-WP-08 | W10 | applicable reliability quantities - only if not covered by audited candidate kernels |
| `NI-ABEP-CLI` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-13 | W14 | the deterministic `abep` binary |
| `NI-ACTIVE-GOLDEN` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-15 | W16 | active canonical hall_icp_neutralizer golden, generated only from the admitted active chain |
| `NI-ZERO-PYTHON-CI` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-16 | W17 | Python-free simulator CI |
| `NI-CLEAN-INSTALL` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-17 | W17 | clean-install acceptance |
| `NI-BID-SOURCE-GUARD` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-12 | W1E | bid_source_manifest_v1 + bid_source_guard (technical source 5eee4b8; terminal package state 2de86ab; lineage b5849af -> 2de86ab; RM-OQ-11 OWNER_DECIDED_A9_29) |
| `NI-MIGRATION-STATE-LEDGER` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-12 | W1E | docs/rust_migration/migration_state_v1.json (one row per inventory-v3_1 component) |
| `NI-GROUNDTEST-ISOLATION-CHECK` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-12 | W1E | cargo metadata check: no flight-runtime crate depends on abep-groundtest (A9.29 sec. 1) |
| `NI-PLATFORM-TEST-REGISTER` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-16 | W1E -> W16 | registered platform / hardware test class: reason, owner / evidence basis, execution environment, required trigger (A9.29 sec. 9) |
| `NI-FEED-STATE-REFERENCE-EVIDENCE` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-14 | GT | only if no successor feed-qualification record exists before final cutover: hash-pinned reference-evidence manifest + CI artifact / hash / schema check (A9.29 sec. 2) |
| `NI-PYTHON-FINAL-REFERENCE-ARCHIVE` | NEW_INFRASTRUCTURE_ACCEPTANCE | SC-WP-16 | W17 | tag python-final-reference-<date>, branch archive/python-final-reference, docs/archive/PYTHON_FINAL_REFERENCE.md + python_final_reference.json (A9.29 sec. 8) |

## v3 dependency findings

* `K-GASPATH / K-GAS-LIFE`: after RM-OQ-06 their v2 active consumers are historical golden_v2 cases (gas_path, hall_icp_neutralizer_reference upstream / AO keys) and class-H archengine.gas_path_state; the active F-chain reaches the compressor / plenum through compressor_synthesis and plenum_feed, not through system.physics_closure. **Resolution:** kept in the inventory as extract-and-parity kernels with v3_status EXTRACT_ONLY_IF_AN_ACTIVE_CONSUMER_IS_CONFIRMED; the SC-WP-02 / SC-WP-08 contracts (or the active golden's cathode-free upstream entry, AFI-04) decide; architecture relevance first, so the PRE_RUST rank-4 timing alone does not justify the port.
* `abep_sim/bus_boundary_a9.py`: check_startup_sequence applies the C1 heater rule (_heater_rule) when the c1_heater slot is installed (hall_c1_reference configuration); the flight configuration hall_icp_neutralizer has no such slot. **Resolution:** port the flight-configuration start-up / concurrent-load logic only; the C1 rule and c1_* slots are GROUND_REFERENCE_ONLY (SC-WP-05).
* `abep_sim/__main__.py`: `python -m abep_sim` runs abep_sim/programme/sweep.py (class H legacy card sweep). **Resolution:** no Python entry point is ported; the `abep` CLI is new infrastructure (SC-WP-13).
* `mission integration`: no active selected-architecture mission integration exists (mission5 / archengine driver are class H). **Resolution:** NEW_PHYSICS element of SC-WP-09.
* `reliability`: no active selected-architecture reliability implementation exists (life.reliability is inside class-H life.py). **Resolution:** audited candidate kernel or preregistered NEW_PHYSICS element of SC-WP-08.
* `active RF/ICP physics`: the active ICP code is an evidence-gated framework (no predictive plasma model); plasma_chem.py is the only global plasma model and is a class-H legacy module. **Resolution:** kernel audit (SC-WP-03); a predictive ICP model would be NEW_PHYSICS - scope is RM-OQ-12. **v3.1 update:** RM-OQ-12 is OWNER_DECIDED_A9_29 (sec. 4): the predictive model is required; it is `NP-ICP-NEUTRALIZER` (SC-WP-03), preregistered first.
* **v3.1 update** (`abep_sim/design/tpmc_backend.py` / abep_core PyO3): A9.29 secs. 5 and 11: the Rust simulator calls the Rust TPMC library directly; the backend switch and the PyO3 / maturin layer are migration tooling, retired at the end state.

## GROUND_TEST_PROGRAMME_ONLY (lane GT; OWNER_APPROVED_A9_29)

A9.29 sec. 1: approved as a separate class; its code may be active programme / evidence / gate tooling; no flight-runtime crate may depend on `abep-groundtest`.

| id | component | disposition | lines | notes |
|---|---|---|---:|---|
| C-DOCS_ARCHITECTURE_COMPARISON_FEED_STATE_CLOSURE | `docs/architecture_comparison/feed_state_closure/` | `NOT_PORTED_SUCCESSOR_RECORD_OR_FROZEN_REFERENCE_EVIDENCE` | 1518 | RM-OQ-10 OWNER_DECIDED_A9_29 (sec. 2): successor record if one exists before final cutover; otherwise the present outputs frozen as immutable hash-pinned reference evidence (CI verifies artifact / hash / schema); the historical builder is not ported and is archive-only; a live S1 / S1a need is a deliberate abep-groundtest Rust contract |
| C-DOCS_EXPERIMENTS_CAPABILITY_DEMO | `docs/experiments/capability_demo/` | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` | 2080 | its HW-RF / HW-ECR pre-ionizer arms are historical upstream-campaign content (A9 decision 2026-09-29); the contract's classification gate lists them as excluded_legacy_paths unless the owner states the active evidence toolchain retains them |
| C-DOCS_EXPERIMENTS_HARDWARE | `docs/experiments/hardware/` | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` | 266 |  |
| C-DOCS_EXPERIMENTS_INSTRUMENTATION | `docs/experiments/instrumentation/` | `MIGRATE_WHERE_RETAINED_IN_ACTIVE_EVIDENCE_TOOLCHAIN` | 2006 |  |
| C-SCRIPTS_EXPERIMENTS_S1_READINESS_PY | `scripts/experiments/s1_readiness.py` | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` | 632 |  |
| C-SCRIPTS_EXPERIMENTS_S1A_READINESS_PY | `scripts/experiments/s1a_readiness.py` | `MIGRATE_ACTIVE_GROUND_TEST_TOOLING` | 774 |  |

## GROUND_REFERENCE_ONLY (lane GR)

| id | component | disposition | lines | notes |
|---|---|---|---:|---|
| C-DOCS_HARDWARE_H2_H2_1_HALL_CHAMBER_MAGNET | `docs/hardware/h2/h2_1_hall_chamber_magnet/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 1649 |  |
| C-DOCS_HARDWARE_H2_H2_2_CATHODE_INTEGRATION | `docs/hardware/h2/h2_2_cathode_integration/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 1775 |  |
| C-DOCS_HARDWARE_H2_H2_3_GAS_PATH_PLENUM | `docs/hardware/h2/h2_3_gas_path_plenum/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 2147 |  |
| C-DOCS_HARDWARE_H2_H2_4_PPU_BUS | `docs/hardware/h2/h2_4_ppu_bus/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 1663 |  |
| C-DOCS_HARDWARE_H2_H2_5_THERMAL_NETWORK | `docs/hardware/h2/h2_5_thermal_network/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 1434 |  |
| C-DOCS_HARDWARE_H2_H2_6_DIAGNOSTICS_FIXTURE | `docs/hardware/h2/h2_6_diagnostics_fixture/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 2286 | RM-OQ-09 OWNER_DECIDED A9.28: scripts/ci_checks.py check h2_6_live_sources loads this builder's verify_sources(); its CHECK SEMANTICS (source hashes, provenance, pinned owner decisions, expected values, deterministic source verification) are re-implemented by the generic Rust provenance verifier (SC-WP-12); obsolete H2-6 architecture assumptions are not ported; the builder itself stays class G and is not ported; the Python check leaves active CI only after the verifier is admitted and normal CI is re-pointed; H2-6 evidence stays immutable |
| C-DOCS_HARDWARE_H2_H2_7_MECHANICAL_BOM | `docs/hardware/h2/h2_7_mechanical_bom/` | `MIGRATE_ONLY_IF_ACTIVE_TOOLCHAIN_REQUIRES` | 1548 |  |

## HISTORICAL_LEGACY_REGRESSION (lane RET: not ported)

RETIRE != DELETE (A9.28 msg 2 sec. 11): not imported by active production execution, not required by the normal simulator CLI, not required by normal CI except explicit historical-regression jobs, not ported merely for completeness.

| id | component | conf. | disposition | kernels extracted / candidates |
|---|---|---|---|---|
| C-ABEP_SIM_PACKAGE_ENTRY_POINTS | `abep_sim/(package entry points)` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_ARCH_BOUNDARY_PY | `abep_sim/arch_boundary.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_ARCH_COMPARE_PY | `abep_sim/arch_compare.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_ARCHENGINE_PY | `abep_sim/archengine.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-GAS-LIFE` |
| C-ABEP_SIM_ASSESSMENT_ARCH_CONSTRAINTS_PY | `abep_sim/assessment/arch_constraints.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_ASSESSMENT_CLOSURE_CHECKS_PY | `abep_sim/assessment/closure_checks.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_BREAKEVEN_PY | `abep_sim/breakeven.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_CATHODE_INTEGRATION_PY | `abep_sim/cathode_integration.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_COMPRESSOR_TRANSITIONAL_PY | `abep_sim/compressor_transitional.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_CONVERGENCE_PY | `abep_sim/convergence.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_EXPLORER_PY | `abep_sim/explorer.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_GOLDEN_PY | `abep_sim/golden.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-GOLDEN-COMPARE` |
| C-ABEP_SIM_HALL1D_PY | `abep_sim/hall1d.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_HARD_GATES_PY | `abep_sim/hard_gates.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_INTERSTAGE_PY | `abep_sim/interstage.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_LIFE_PY | `abep_sim/life.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-GAS-LIFE` |
| C-ABEP_SIM_MASS_BOM_PY | `abep_sim/mass_bom.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: xe_tank, thin_wall_sphere_min_mass_kg, reservoir_vessel, structure_mass, hall_magnetic_circuit, hall_channel_mass (geometry / pressure-vessel sizing) |
| C-ABEP_SIM_MISSION5_PY | `abep_sim/mission5.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_MISSION_UQ_PY | `abep_sim/mission_uq.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_ORBIT_ATM_PY | `abep_sim/orbit_atm.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_PLASMA_CHEM_PY | `abep_sim/plasma_chem.py` | O | `NOT_PORTED_EXTRACT_ARCH_INDEPENDENT_KERNELS_ONLY_IF_NEEDED` | candidates: k_rate (cross-section-table branch only; the Arrhenius fits are unverified, CLAUDE.md next-work 6); Bohm wall flux / effusion conductance / particle-power balance structure of solve_global (Lieberman and Lichtenberg ch. 10); eps_c (Lieberman-style fit; unverified, needs provenance) |
| C-ABEP_SIM_PLASMA_DEVICES_PY | `abep_sim/plasma_devices.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_PPU_PY | `abep_sim/ppu.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: Converter switching-loss efficiency map (no keeper / heater / stage-1 loads) |
| C-ABEP_SIM_PROGRAMME_ARCH_COMPARE_PY | `abep_sim/programme/arch_compare.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_PROGRAMME_CLOSURE_PY | `abep_sim/programme/closure.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_PROGRAMME_SWEEP_PY | `abep_sim/programme/sweep.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_PROGRAMME_UQ_MODULAR_PY | `abep_sim/programme/uq_modular.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_RADIATION_PY | `abep_sim/radiation.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: RadEnv TID dose-depth, shielding_mass, uv_contamination_ageing, debris_puncture (literature-class parameterisations) |
| C-ABEP_SIM_SIZING_PY | `abep_sim/sizing.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_SYSTEM_PY | `abep_sim/system.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-GASPATH` |
| C-ABEP_SIM_THERMAL_PY | `abep_sim/thermal.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: aero_heating_W_m2 (ram aerodynamic heating); solve_network / size_radiator (generic steady lumped network) - only if the post-bid cathodeless successor thermal model (AFI-03) needs them |
| C-ABEP_SIM_THRESHOLDS_PY | `abep_sim/thresholds.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_THRUSTER_PY | `abep_sim/thruster.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: species_flows (air species split from the atmosphere record); per-species ideal electrostatic relations I_b, v_s, T (the performance() core without the card) |
| C-ABEP_SIM_TRANSIENT_PY | `abep_sim/transient.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_UNCERTAINTY_PY | `abep_sim/uncertainty.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_UQ6_PY | `abep_sim/uq6.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_UQ_MODULAR_PY | `abep_sim/uq_modular.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_VALIDATION_PY | `abep_sim/validation.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-ABEP_SIM_XE_LEDGER_PY | `abep_sim/xe_ledger.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_AUX_BUS | `docs/architecture_comparison/aux_bus/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_CATHODE_INTEGRATION | `docs/architecture_comparison/cathode_integration/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_COMPRESSOR_DOWNSELECT | `docs/architecture_comparison/compressor_downselect/` | O | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_ELECTRICAL_CLOSURE_TOOLS | `docs/architecture_comparison/electrical_closure/tools/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PACKAGE | `docs/architecture_comparison/experiment_package/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_EXPERIMENT_PROTOCOL | `docs/architecture_comparison/experiment_protocol/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_FAILURE_TREE | `docs/architecture_comparison/failure_tree/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_HALL_REFERENCE | `docs/architecture_comparison/hall_reference/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | candidates: voltage_envelope ideal-beam relations |
| C-DOCS_ARCHITECTURE_COMPARISON_LOCK1 | `docs/architecture_comparison/lock1/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_MINIMUM_DECISIVE_EXPERIMENT | `docs/architecture_comparison/minimum_decisive_experiment/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_ECR | `docs/architecture_comparison/overlays/ecr/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_HALL_SUSTAINMENT | `docs/architecture_comparison/overlays/hall_sustainment/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_OVERLAYS_RF | `docs/architecture_comparison/overlays/rf/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_TOOLS | `docs/architecture_comparison/power_boundary/tools/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9 | `docs/architecture_comparison/power_boundary_a9/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ARCHITECTURE_COMPARISON_VETO_LAYER | `docs/architecture_comparison/veto_layer/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_MASS_A9 | `docs/budgets/mass_a9/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V2 | `docs/budgets/mass_power_a9_v2/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V3 | `docs/budgets/mass_power_a9_v3/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-MASS-RULES` |
| C-DOCS_BUDGETS_SUBSYSTEM_MATURITY | `docs/budgets/subsystem_maturity/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V2 | `docs/budgets/xe_accounting_a9_v2/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_XE_LEDGER | `docs/budgets/xe_ledger/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_XE_LEDGER_A9 | `docs/budgets/xe_ledger_a9/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_EVIDENCE_COMPRESSOR_TRANSITIONAL | `docs/evidence/compressor_transitional/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_EVIDENCE_ECR_SOURCE | `docs/evidence/ecr_source/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_EVIDENCE_RF_SOURCE | `docs/evidence/rf_source/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V4 | `docs/experiments/hall_icp/integration/m16_v4/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_EXPERIMENTS_HALL_ICP_P3_COUPLED_THERMAL | `docs/experiments/hall_icp/p3_coupled_thermal/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | `K-P3-RAYS` |
| C-DOCS_EXPERIMENTS_PHASE1_PREREG_FRAMEWORK | `docs/experiments/phase1_prereg_framework/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_INTERFACES_PREIONIZER_MODULE | `docs/interfaces/preionizer_module/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_MILESTONES_BUNDLE1 | `docs/milestones/bundle1/` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_PROCUREMENT_RFQ_A9 | `docs/procurement/rfq_a9/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_PROCUREMENT_RFQ_A9_V2 | `docs/procurement/rfq_a9_v2/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_TRACEABILITY | `docs/traceability/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_BREAKEVEN_SURFACES_PY | `scripts/architecture/build_breakeven_surfaces.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_COMPARISON_GRID_PY | `scripts/architecture/build_comparison_grid.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_DECISION_DOSSIER_PY | `scripts/architecture/build_decision_dossier.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_ARCHITECTURE_BUILD_FEED_ENVELOPE_PY | `scripts/architecture/build_feed_envelope.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_ARCHITECTURE_SCALING_SIMILARITY_PY | `scripts/architecture/scaling_similarity.py` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-SCRIPTS_CONFIG_BUILD_RESULT_SCHEMAS_PY | `scripts/config/build_result_schemas.py` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-TESTS_FIXTURES | `tests/fixtures` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_BUDGETS_MASS_POWER_A9_V4 | `docs/budgets/mass_power_a9_v4/` | E | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |
| C-DOCS_ORCHESTRATION_RUNNER_SCRIPTS_SH_INLINE_PYTHON | `docs/orchestration/runner_scripts/*.sh (inline python)` | A | `NOT_PORTED_RETIRE_FROM_ACTIVE_GRAPH` | - |

Confidence (v3.1, `classification_confidence_v3_1`): E = established, O = owner-decided A9.28, A = plan-approved A9.29 (a v3 proposed classification, shown as P in v3, inside the structure the owner approved). No row is provisional.

## ACTIVE_SELECTED_ARCHITECTURE_PHYSICS (waves)

| id | component | wave v3 | work package | disposition | conf. | lines |
|---|---|---|---|---|---|---:|
| C-ABEP_SIM_AOCHEM_PY | `abep_sim/aochem.py` | W2 | SC-WP-08 | `MIGRATE_UNDER_PREREG_PARITY` | A | 113 |
| C-ABEP_SIM_ASSESSMENT_DESIGN_GATES_PY | `abep_sim/assessment/design_gates.py` | W12 | SC-WP-11 | `MIGRATE_UNDER_PREREG_PARITY` | A | 506 |
| C-ABEP_SIM_ATMOSPHERE_PY | `abep_sim/atmosphere.py` | W1E | SC-WP-01 | `MIGRATE_UNDER_PREREG_PARITY` | A | 171 |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_PY | `abep_sim/atmosphere_orbit.py` | W1 | SC-WP-01 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1479 |
| C-ABEP_SIM_ATMOSPHERE_ORBIT_V2_PY | `abep_sim/atmosphere_orbit_v2.py` | W6 | SC-WP-01 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1180 |
| C-ABEP_SIM_BUS_BOUNDARY_A9_PY | `abep_sim/bus_boundary_a9.py` | W4 | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 956 |
| C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY | `abep_sim/bus_boundary_a9_v2.py` | W4 | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 122 |
| C-ABEP_SIM_COMPRESSOR_PY | `abep_sim/compressor.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 317 |
| C-ABEP_SIM_CONFIGURATION_PY | `abep_sim/configuration.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 480 |
| C-ABEP_SIM_CONSTANTS_PY | `abep_sim/constants.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 37 |
| C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY | `abep_sim/design/a9_19_architecture.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 293 |
| C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY | `abep_sim/design/architecture_optimizer.py` | W4 | SC-WP-10 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1262 |
| C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY | `abep_sim/design/compressor_synthesis.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 995 |
| C-ABEP_SIM_DESIGN_ENGINEERING_CONSTRAINTS_PY | `abep_sim/design/engineering_constraints.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 82 |
| C-ABEP_SIM_DESIGN_FILTER_STAGE_PY | `abep_sim/design/filter_stage.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1065 |
| C-ABEP_SIM_DESIGN_ICP_GEOMETRY_SYNTHESIS_PY | `abep_sim/design/icp_geometry_synthesis.py` | W9 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 806 |
| C-ABEP_SIM_DESIGN_INTAKE_SYNTHESIS_PY | `abep_sim/design/intake_synthesis.py` | W1 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1598 |
| C-ABEP_SIM_DESIGN_PLENUM_FEED_PY | `abep_sim/design/plenum_feed.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1511 |
| C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY | `abep_sim/design/robust_optimizer.py` | W4 | SC-WP-10 | `MIGRATE_UNDER_PREREG_PARITY` | A | 453 |
| C-ABEP_SIM_DESIGN_TPMC_BACKEND_PY | `abep_sim/design/tpmc_backend.py` | W16 | SC-WP-16 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | A | 313 |
| C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY | `abep_sim/design/upstream_a9_13.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 818 |
| C-ABEP_SIM_H1_GEOMETRY_PY | `abep_sim/h1_geometry.py` | W4 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 64 |
| C-ABEP_SIM_HALL_ENSEMBLE_PY | `abep_sim/hall_ensemble.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 168 |
| C-ABEP_SIM_HALL_MAP_PY | `abep_sim/hall_map.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 99 |
| C-ABEP_SIM_HALLMAP_REGISTRY_PY | `abep_sim/hallmap_registry.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 572 |
| C-ABEP_SIM_ICP_BENCH_LIB_PY | `abep_sim/icp_bench_lib.py` | W9 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 174 |
| C-ABEP_SIM_ICP_THERMAL_LIB_PY | `abep_sim/icp_thermal_lib.py` | W5 | SC-WP-06 | `MIGRATE_UNDER_PREREG_PARITY` | A | 509 |
| C-ABEP_SIM_INTAKE_PY | `abep_sim/intake.py` | W1 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 130 |
| C-ABEP_SIM_INTAKE_SURFACE_V2_SPEC_PY | `abep_sim/intake_surface_v2_spec.py` | W1 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 189 |
| C-ABEP_SIM_INTAKE_TPMC_PY | `abep_sim/intake_tpmc.py` | W0+W1 | SC-WP-02 | `ADMITTED_KERNEL_PLUS_MIGRATE_REMAINDER` | E | 475 |
| C-ABEP_SIM_MAGNET_POWER_PY | `abep_sim/magnet_power.py` | W9 | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 336 |
| C-ABEP_SIM_MATERIALS_PY | `abep_sim/materials.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 104 |
| C-ABEP_SIM_MISSION_ENV_PY | `abep_sim/mission_env.py` | W3 | SC-WP-09 | `MIGRATE_UNDER_PREREG_PARITY` | A | 173 |
| C-ABEP_SIM_OPERATING_INPUTS_PY | `abep_sim/operating_inputs.py` | W1E | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 53 |
| C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY | `abep_sim/programme/design_synthesis.py` | W12 | SC-WP-10 | `MIGRATE_UNDER_PREREG_PARITY` | A | 296 |
| C-ABEP_SIM_RATE_TABLES_PY | `abep_sim/rate_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 66 |
| C-ABEP_SIM_RESERVOIR_PY | `abep_sim/reservoir.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 180 |
| C-ABEP_SIM_ROTOR_STRENGTH_PY | `abep_sim/rotor_strength.py` | W2 | SC-WP-02 | `MIGRATE_UNDER_PREREG_PARITY` | A | 281 |
| C-ABEP_SIM_SPACECRAFT_REFERENCE_DRAG_PY | `abep_sim/spacecraft_reference_drag.py` | W1 | SC-WP-04 | `MIGRATE_UNDER_PREREG_PARITY` | A | 560 |
| C-ABEP_SIM_STATEWISE_PY | `abep_sim/statewise.py` | W1 | SC-WP-04 | `MIGRATE_UNDER_PREREG_PARITY` | A | 76 |
| C-ABEP_SIM_THERMAL_LIFE_PY | `abep_sim/thermal_life.py` | W10 | SC-WP-06 | `MIGRATE_UNDER_PREREG_PARITY` | A | 979 |
| C-DOCS_ARCHITECTURE_FREEZE_CANDIDATE | `docs/architecture/freeze_candidate/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 3602 |
| C-DOCS_ARCHITECTURE_COMPARISON_POWER_BOUNDARY_A9_V2 | `docs/architecture_comparison/power_boundary_a9_v2/` | W15a | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1501 |
| C-DOCS_BID_PACKAGE | `docs/bid/package/` | W15c | SC-WP-14 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 1506 |
| C-DOCS_BUDGETS_OWNER_DECISIONS | `docs/budgets/owner_decisions/` | W15c | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 3844 |
| C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3 | `docs/budgets/xe_accounting_a9_v3/` | W11 | SC-WP-07 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1430 |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5 | `docs/chemistry/n2_domain_extension/dx5/` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 509 |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_ACQUISITION | `docs/chemistry/n2_domain_extension/dx5/acquisition/` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 335 |
| C-DOCS_CHEMISTRY_N2_DOMAIN_EXTENSION_DX5_CURATION | `docs/chemistry/n2_domain_extension/dx5/curation/` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 224 |
| C-DOCS_CHEMISTRY_O_O2_V0 | `docs/chemistry/o_o2/v0/` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 710 |
| C-DOCS_DECISIONS_APPLICATION | `docs/decisions/application/` | W15c | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1824 |
| C-DOCS_DESIGN_SYNTHESIS_F1_INTAKE | `docs/design_synthesis/f1_intake/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 821 |
| C-DOCS_DESIGN_SYNTHESIS_F2_FILTER | `docs/design_synthesis/f2_filter/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 708 |
| C-DOCS_DESIGN_SYNTHESIS_F3_COMPRESSOR | `docs/design_synthesis/f3_compressor/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 561 |
| C-DOCS_DESIGN_SYNTHESIS_F4_PLENUM | `docs/design_synthesis/f4_plenum/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1423 |
| C-DOCS_DESIGN_SYNTHESIS_F6_ICP_GEOMETRY | `docs/design_synthesis/f6_icp_geometry/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 607 |
| C-DOCS_DESIGN_SYNTHESIS_F7_F8_OPTIMIZER | `docs/design_synthesis/f7_f8_optimizer/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 810 |
| C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG | `docs/design_synthesis/spacecraft_reference_drag/` | W15a | SC-WP-04 | `MIGRATE_UNDER_PREREG_PARITY` | A | 157 |
| C-DOCS_EVIDENCE_HALL_SUSTAINMENT | `docs/evidence/hall_sustainment/` | W15b | SC-WP-14 | `MIGRATE_OR_FORMALLY_RETIRE` | O | 1531 |
| C-DOCS_EVIDENCE_ICP_NEUTRALIZER | `docs/evidence/icp_neutralizer/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1222 |
| C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1 | `docs/evidence/sputter_yields_v1/` | W15b | SC-WP-08 | `MIGRATE_UNDER_PREREG_PARITY` | A | 864 |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION | `docs/experiments/hall_icp/integration/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 6623 |
| C-DOCS_EXPERIMENTS_HALL_ICP_INTEGRATION_M16_V5 | `docs/experiments/hall_icp/integration/m16_v5/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1135 |
| C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH | `docs/experiments/hall_icp/p1_icp_bench/` | W15b | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 8197 |
| C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP | `docs/experiments/hall_icp/p2_impedance_map/` | W15b | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 6539 |
| C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS | `docs/experiments/hall_icp/p4_anode_materials/` | W15b | SC-WP-08 | `MIGRATE_UNDER_PREREG_PARITY` | A | 2800 |
| C-DOCS_EXPERIMENTS_HALL_ICP_PREREG_FRAMEWORK | `docs/experiments/hall_icp/prereg_framework/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1171 |
| C-DOCS_EXPERIMENTS_HALL_ICP_PROGRAMME | `docs/experiments/hall_icp/programme/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 882 |
| C-DOCS_EXPERIMENTS_HALL_ICP_UNCERTAINTY_BUDGET | `docs/experiments/hall_icp/uncertainty_budget/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1899 |
| C-DOCS_EXPERIMENTS_HALL_ICP_VALIDATION_INPUTS | `docs/experiments/hall_icp/validation_inputs/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 945 |
| C-DOCS_EXPERIMENTS_LIFETIME_AO | `docs/experiments/lifetime_ao/` | W15b | SC-WP-08 | `MIGRATE_UNDER_PREREG_PARITY` | A | 2558 |
| C-DOCS_EXPERIMENTS_MAGNET_COIL | `docs/experiments/magnet_coil/` | W15b | SC-WP-05 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1283 |
| C-DOCS_HARDWARE_H1_FREEZE_CANDIDATE | `docs/hardware/h1_freeze_candidate/` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1875 |
| C-DOCS_HARDWARE_H2_A9_REVISIONS | `docs/hardware/h2_a9_revisions/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 3493 |
| C-DOCS_INTERFACES_ICP_NEUTRALIZER | `docs/interfaces/icp_neutralizer/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1550 |
| C-DOCS_O4_DISPOSITION_MATRIX | `docs/o4/disposition_matrix/` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 667 |
| C-DOCS_O4_JOHNSONLOW_ASSESSMENT | `docs/o4/johnsonlow_assessment/` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 739 |
| C-DOCS_PROCUREMENT_RFQ_A9_V3 | `docs/procurement/rfq_a9_v3/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 3334 |
| C-DOCS_REQUIREMENTS_RFP_OFFICIAL | `docs/requirements/rfp_official/` | W15c | SC-WP-11 | `MIGRATE_UNDER_PREREG_PARITY` | A | 351 |
| C-DOCS_REQUIREMENTS_RVM_A9 | `docs/requirements/rvm_a9/` | W15c | SC-WP-11 | `MIGRATE_UNDER_PREREG_PARITY` | A | 4172 |
| C-DOCS_V2_QUESTION_A | `docs/v2/question_a/` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 751 |
| C-DOCS_VALIDATION_HALL_TRANSPORT_V2_PREREG | `docs/validation/hall_transport_v2_prereg/` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 72 |
| C-SCRIPTS_AUDIT_N2_COMPLETENESS_FINAL_PY | `scripts/audit_n2_completeness_final.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 210 |
| C-SCRIPTS_AUDIT_N2_DISSOCIATIVE_IONIZATION_PY | `scripts/audit_n2_dissociative_ionization.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 126 |
| C-SCRIPTS_AUDIT_N2_VIBRATIONAL_EXCITATION_PY | `scripts/audit_n2_vibrational_excitation.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 183 |
| C-SCRIPTS_AUDIT_P5_N2_CAMPAIGN_RECORDS_PY | `scripts/audit_p5_n2_campaign_records.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 61 |
| C-SCRIPTS_AUDIT_P5_N2_MEASUREMENTS_PY | `scripts/audit_p5_n2_measurements.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 187 |
| C-SCRIPTS_BUILD_MULTIPLY_CHARGED_TABLES_PY | `scripts/build_multiply_charged_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 156 |
| C-SCRIPTS_BUILD_N2_DISSOCIATION_TABLE_PY | `scripts/build_n2_dissociation_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 65 |
| C-SCRIPTS_BUILD_N2_DISSOCIATIVE_IONIZATION_TABLE_PY | `scripts/build_n2_dissociative_ionization_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 97 |
| C-SCRIPTS_BUILD_N2_ELASTIC_SONG2023_TABLE_PY | `scripts/build_n2_elastic_song2023_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 78 |
| C-SCRIPTS_BUILD_N2_ELECTRONIC_EXCITATION_TABLES_PY | `scripts/build_n2_electronic_excitation_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 147 |
| C-SCRIPTS_BUILD_N2_IONIZATION_SONG2023_TABLE_PY | `scripts/build_n2_ionization_song2023_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 69 |
| C-SCRIPTS_BUILD_N2_ROTATIONAL_TABLES_PY | `scripts/build_n2_rotational_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 42 |
| C-SCRIPTS_BUILD_N2_TO_N_Z2PLUS_TABLE_PY | `scripts/build_n2_to_n_z2plus_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 62 |
| C-SCRIPTS_BUILD_N2_VIBRATIONAL_TABLES_PY | `scripts/build_n2_vibrational_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 74 |
| C-SCRIPTS_BUILD_N_ELASTIC_TABLES_PY | `scripts/build_n_elastic_tables.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 125 |
| C-SCRIPTS_BUILD_N_IONIZATION_TABLE_PY | `scripts/build_n_ionization_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 66 |
| C-SCRIPTS_BUILD_N_Z1PLUS_TO_Z2PLUS_TABLE_PY | `scripts/build_n_z1plus_to_z2plus_table.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 66 |
| C-SCRIPTS_CHEMISTRY_N2_DOMAIN_EXTENSION_REQUIREMENTS_PY | `scripts/chemistry/n2_domain_extension_requirements.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 892 |
| C-SCRIPTS_CI_CHECKS_PY | `scripts/ci_checks.py` | W16 | SC-WP-16 | `MIGRATE_UNDER_PREREG_PARITY` | A | 566 |
| C-SCRIPTS_CONFIG_BUILD_CONFIG_PY | `scripts/config/build_config.py` | W13 | SC-WP-12 | `MIGRATE_UNDER_PREREG_PARITY` | A | 980 |
| C-SCRIPTS_DIGITIZE_P5_BFIELD_PY | `scripts/digitize_p5_bfield.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 59 |
| C-SCRIPTS_EVIDENCE_EVIDENCE_ARCHIVE_PY | `scripts/evidence/evidence_archive.py` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 124 |
| C-SCRIPTS_EVIDENCE_F1_ARCHIVE_PY | `scripts/evidence/f1_archive.py` | W15a | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 504 |
| C-SCRIPTS_FORENSICS_P5_N2_V1_EXB_PHYSICS_PY | `scripts/forensics/p5_n2_v1_exb_physics.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 604 |
| C-SCRIPTS_FORENSICS_P5_N2_V1_OOD_ATTRIBUTION_PY | `scripts/forensics/p5_n2_v1_ood_attribution.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 994 |
| C-SCRIPTS_FORENSICS_P5_N2_V1_SCOREABLE_SUBSET_PY | `scripts/forensics/p5_n2_v1_scoreable_subset.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 1386 |
| C-SCRIPTS_FREEZE_P5_N2_DATASET_PY | `scripts/freeze_p5_n2_dataset.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 141 |
| C-SCRIPTS_IDENTIFY_P5_TRANSPORT_PY | `scripts/identify_p5_transport.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 256 |
| C-SCRIPTS_MAKE_N2_VARIANT_CONFIGS_PY | `scripts/make_n2_variant_configs.py` | W7 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 98 |
| C-SCRIPTS_MAKE_P5_N2_CASES_PY | `scripts/make_p5_n2_cases.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 68 |
| C-SCRIPTS_MAKE_P5_N2_LAUNCH_MANIFESTS_PY | `scripts/make_p5_n2_launch_manifests.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 80 |
| C-SCRIPTS_MAKE_P5_XENON_CASES_PY | `scripts/make_p5_xenon_cases.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 68 |
| C-SCRIPTS_MAKE_VALIDATION_RELEASE_PY | `scripts/make_validation_release.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 106 |
| C-SCRIPTS_N2_CLOSURE_TABLE_PY | `scripts/n2_closure_table.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 136 |
| C-SCRIPTS_ORCHESTRATION_LANE_STATUS_PY | `scripts/orchestration/lane_status.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 303 |
| C-SCRIPTS_ORCHESTRATION_O4_SCORE_DATASET_PY | `scripts/orchestration/o4_score_dataset.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 51 |
| C-SCRIPTS_ORCHESTRATION_TRIGGER_LEDGER_PY | `scripts/orchestration/trigger_ledger.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 167 |
| C-SCRIPTS_PERF_PROFILE_BASELINE_PY | `scripts/perf/profile_baseline.py` | W16 | SC-WP-16 | `MIGRATE_UNDER_PREREG_PARITY` | A | 1328 |
| C-SCRIPTS_REPORT_P5_N2_CAMPAIGN_PY | `scripts/report_p5_n2_campaign.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 144 |
| C-SCRIPTS_RESCORE_P5_AXIAL_THRUST_PY | `scripts/rescore_p5_axial_thrust.py` | W8 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 141 |
| C-SCRIPTS_SCORE_P5_N2_CAMPAIGN_PY | `scripts/score_p5_n2_campaign.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 235 |
| C-SCRIPTS_SCORE_P5_N2_FROZEN_PY | `scripts/score_p5_n2_frozen.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 95 |
| C-SCRIPTS_SCORE_P5_N2_STAGED_PY | `scripts/score_p5_n2_staged.py` | W8 | SC-WP-03 | `MIGRATE_UNDER_PREREG_PARITY` | A | 169 |
| C-SCRIPTS_SUMMARIZE_BLIND_ENVELOPE_PY | `scripts/summarize_blind_envelope.py` | W7 | SC-WP-03 | `MIGRATE_OR_FORMALLY_RETIRE` | A | 79 |
| C-SCRIPTS_VERIFY_ABEP_CORE_PY | `scripts/verify_abep_core.py` | W16 | SC-WP-16 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | A | 1189 |
| C-TESTS | `tests` | W16 | SC-WP-16 | `MIGRATE_UNDER_PREREG_PARITY` | A | 63307 |
| C-DOCS_BUDGETS_MASS_POWER_A9_V5 | `docs/budgets/mass_power_a9_v5/` | W11 | SC-WP-07 | `MIGRATE_GENERIC_LOGIC_PRESERVE_VALUE_STATUS` | O | 874 |
| C-DOCS_PROCUREMENT_RFQ_A9_V3_GAS_REV1 | `docs/procurement/rfq_a9_v3_gas_rev1/` | W15b | SC-WP-14 | `MIGRATE_UNDER_PREREG_PARITY` | A | 471 |
| C-GITHUB_WORKFLOWS_YML_INLINE_PYTHON | `.github/workflows/*.yml (inline python)` | W16 | SC-WP-16 | `MIGRATE_UNDER_PREREG_PARITY` | A | - |
| C-ABEP_CORE_PYO3_MATURIN_BINDING_LAYER | `abep_core PyO3 / maturin binding layer` | W17 | SC-WP-16 | `RETIRE_AT_END_STATE_MIGRATION_TOOLING` | E | - |

## Cathode-audit AFI items at v3

| item | status | v3 consequence |
|---|---|---|
| AFI-01 | RESOLVED in mass / power v4 / v5 | v3 record historical (class H); its rule functions are `K-MASS-RULES` |
| AFI-02 | **OPEN as a value-status action** (AFI-02-RA1) | `mass_power_a9_v5` is class A (A9.28); AL-07 keeps 6.0 kg as `PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT`; the migration never rebases or promotes it |
| AFI-03 | RESOLVED by owner labelling | P3 v2 class H; the cathodeless thermal model is NEW_PHYSICS directly in Rust (RM-OQ-08) |
| AFI-04 | `HISTORICAL_REGRESSION_COMPATIBILITY` | historical goldens are not Rust parity cases (RM-OQ-06); the active golden comes from the admitted Rust chain |
| AFI-05 | RESOLVED | RVM builder class A (SC-WP-11) |

A9.29 changes no AFI item.
