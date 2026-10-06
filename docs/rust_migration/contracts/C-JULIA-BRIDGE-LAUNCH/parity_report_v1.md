# C-JULIA-BRIDGE-LAUNCH parity report v1

Generated from `parity_report_v1.json` (contract `docs/rust_migration/contracts/C-JULIA-BRIDGE-LAUNCH/parity_prereg_v1.json`, sha256 `aad2eabf8173f85a194eaeaa51b9611adee5958a97abb6deeb9757705d41f836`).

**Verdict: PARITY_PASS. Admission: ADMITTED** (cargo gate pass: 255 tests passed, 2 ignored = registered platform tests PT-01 / PT-02).

## What was compared

The Python reference (`scripts/make_p5_n2_launch_manifests.py` build / check, the committed manifest commands as the runner scripts execute them, `.github/workflows/julia-smoke.yml`, `scripts/ci_checks.py::check_hallthruster_pin`) and `abep-julia-bridge cases` on byte-identical trees. No Julia process was started; the run-record comparison is the registered platform test PT-02 (NOT_RUN here: no Julia in this environment).

* Commit: `d9009d3030139bcc1f0375f5f47d6d788a14f887`.
* Cases: 143; steps compared: 332; cases agreeing: 143; disagreements: none.

## Decision rule

| rule | holds |
|---|---|
| D1_every_step_agrees | True |
| D2_built_manifests_equal_committed | True |
| INV-01_rust_deterministic | True |
| INV-02_shard_partition | True |
| INV-04_allow_list_only | True |
| INV-03_scoring_tree_unchanged | True |
| INV-05_sidecar_field_set | covered by cargo test sidecar_is_exactly_the_hall_physics_boundary_list (cargo gate) |
| cargo_gate | True |

## By group

| group | cases | agree | steps | Python refusal steps |
|---|---|---|---|---|
| MANIFEST | 1 | 1 | 1 | 0 |
| LAUNCH | 60 | 60 | 231 | 0 |
| SHARD | 1 | 1 | 19 | 0 |
| CHECK | 20 | 20 | 20 | 4 |
| PIN | 13 | 13 | 13 | 4 |
| RANDOM | 48 | 48 | 48 | 0 |

## Platform tests

* PT-01: NOT_RUN (no Julia toolchain here; registered in docs/rust_migration/test_register/platform_tests_v1.json)
* PT-02: NOT_RUN (run-record EXACT_BYTES comparison needs the pinned Julia; registered)

## Ledger update requested

* {"component": "C-SCRIPTS_MAKE_P5_N2_LAUNCH_MANIFESTS_PY", "status": "ADMITTED", "authoritative_implementation": "rust: abep_julia_bridge::manifests / jobs / pin / sidecar / launch", "contract": "docs/rust_migration/contracts/C-JULIA-BRIDGE-LAUNCH/parity_prereg_v1.json", "contract_sha256": "aad2eabf8173f85a194eaeaa51b9611adee5958a97abb6deeb9757705d41f836", "report": "docs/rust_migration/contracts/C-JULIA-BRIDGE-LAUNCH/parity_report_v1.json", "note": "run-record EXACT_BYTES (PT-02) pending the pinned Julia toolchain"}
* {"component": "C-SCRIPTS_IDENTIFY_P5_TRANSPORT_PY", "status": "FORMALLY_RETIRED_NOT_PORTED (proposed)", "note": "MIGRATE_OR_FORMALLY_RETIRE; P5-Xe identification CLOSED 2026-09-25; not ported (A9.29 sec. 14); a reopening decision on new published evidence would need its own contract"}
