# C-PROVENANCE-VERIFIER parity report v1

Generated from `parity_report_v1.json` (contract `docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_prereg_v1.json`, sha256 `95f06eb3e9e31b3ba0019d4bacccbde6050d4b390dbfae64e5d015b453fb49e6`, registered in `805d0447e52b`).

**Verdict: PARITY_PASS. Admission: ADMITTED** (cargo fmt / clippy / test gate: pass, 32 tests passed, 0 ignored).

## What was compared

The Python checks `prereg_lock`, `audit_manifest`, `hallthruster_pin` and `h2_6_live_sources` (each tree's own
unmodified `scripts/ci_checks.py`, `run_checks`) and the Rust verifier `abep-provenance-verify` ran on the same
trees. For every tree and check, the pass / fail decision and the sorted multiset of failure identities
(kind, file, key) had to be equal.

* Commit: `e848e1d3b5f34cc0e9e860c2cb4280f80034bad0` (Python reference and Rust).
* Trees: 193 (current tree, 24 edge trees, 7 classes x 24 seeded trees, scoring seed 887790081732834691).
* Check decisions compared: 772; trees agreeing: 193.
* Disagreements: none.

## Decision rule

| rule | holds |
|---|---|
| D1 current tree passes in both | True |
| D2 every tree and check agrees | True |
| D3 every class exercised | True |
| INV-01 | True |
| INV-02 | True |
| INV-03 | True |
| INV-04 | True |
| INV-05 | True |
| INV-06 | True |

## By class

| class | trees | agree | Python fails | Rust fails |
|---|---|---|---|---|
| current | 1 | 1 | 0 | 0 |
| edge | 24 | 24 | 22 | 22 |
| CC-01 | 24 | 24 | 24 | 24 |
| CC-02 | 24 | 24 | 24 | 24 |
| CC-03 | 24 | 24 | 24 | 24 |
| CC-04 | 24 | 24 | 24 | 24 |
| CC-05 | 24 | 24 | 24 | 24 |
| CC-06 | 24 | 24 | 24 | 24 |
| CC-07 | 24 | 24 | 17 | 17 |

Failing check decisions (Python, all trees): prereg_lock 60, audit_manifest 52, hallthruster_pin 28, h2_6_live_sources 43.

## Edge trees

| tree | operation | failing checks (identities) | agree |
|---|---|---|---|
| DE-01 | unlink `hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json` | prereg_lock: RAISED/hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json/FILE_MISSING | True |
| DE-02 | json_rewrite `hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json` | prereg_lock: EMPTY_PIN_SET/hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json/files | True |
| DE-03 | json_rewrite `hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json` | prereg_lock: SHA256_MISMATCH/hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json/prereg lock, UNPINNED/hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json/n2_n_unpinned_de03.toml | True |
| DE-04 | json_rewrite `hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json` | prereg_lock: RAISED/KEY_MISSING:cases | True |
| DE-05 | unlink `hallthruster_bridge/audit/configs/MANIFEST.json` | audit_manifest: RAISED/hallthruster_bridge/audit/configs/MANIFEST.json/FILE_MISSING | True |
| DE-06 | json_rewrite `hallthruster_bridge/audit/configs/MANIFEST.json` | audit_manifest: EMPTY_PIN_SET/hallthruster_bridge/audit/configs/MANIFEST.json/configs | True |
| DE-07 | regex_sub `hallthruster_bridge/audit/configs/n2_n_0p9_pre_rotation.toml` | audit_manifest: SET_MISMATCH/hallthruster_bridge/audit/configs/n2_n_0p9_pre_rotation.toml/["de07_unlisted.dat","elastic_N2_song2023.dat"], SHA256_MISMATCH/hallthruster_bridge/audit/configs/n2_n_0p9_pre_rotation.toml/audit snapshot | True |
| DE-08 | truncate_half `hallthruster_bridge/audit/configs/n2_n_0p10_nominal_pre_hms.toml` | audit_manifest: RAISED/DECODE_ERROR | True |
| DE-09 | unlink `hallthruster_bridge/PINNED.toml` | hallthruster_pin: RAISED/hallthruster_bridge/PINNED.toml/FILE_MISSING | True |
| DE-10 | rename_all `hallthruster_bridge/Manifest.toml` | hallthruster_pin: ENTRY_COUNT/hallthruster_bridge/Manifest.toml/deps.HallThruster | True |
| DE-11 | text_replace `hallthruster_bridge/Project.toml` | hallthruster_pin: VALUE_MISMATCH/hallthruster_bridge/Project.toml/compat.HallThruster | True |
| DE-12 | delete_line `hallthruster_bridge/PINNED.toml` | hallthruster_pin: RAISED/KEY_MISSING:version | True |
| DE-13 | unlink `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` | h2_6_live_sources: SOURCE_MISSING/docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json/W1 | True |
| DE-14 | json_rewrite `docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json` | h2_6_live_sources: SOURCE_KEY_MISSING/docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json/mdot_max_kgps | True |
| DE-15 | json_rewrite `docs/experiments/instrumentation/instrumentation_definition_v1.json` | h2_6_live_sources: SOURCE_KEY_MISSING/docs/experiments/instrumentation/instrumentation_definition_v1.json/value | True |
| DE-16 | json_rewrite `docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json` | h2_6_live_sources: VALUE_MISMATCH/docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json/pb_elev_factor | True |
| DE-17 | unlink `abep_sim/constants.py` | h2_6_live_sources: SOURCE_MISSING/abep_sim/constants.py/constants | True |
| DE-18 | text_replace `abep_sim/constants.py` | h2_6_live_sources: VALUE_MISMATCH/abep_sim/constants.py/thrust_min_mN | True |
| DE-19 | text_replace `abep_sim/constants.py` | none | True |
| DE-20 | text_replace `abep_sim/constants.py` | none | True |
| DE-21 | json_rewrite `docs/experiments/instrumentation/instrumentation_definition_v1.json` | h2_6_live_sources: RAISED/VALUE_ERROR | True |
| DE-22 | json_rewrite `docs/experiments/hardware/hardware_requirements_v1.json` | h2_6_live_sources: SHA256_MISMATCH/docs/experiments/hardware/hardware_requirements_v1.json/h2_6 pin, SOURCE_KEY_MISSING/docs/experiments/hardware/hardware_requirements_v1.json/HW-ENV-01 | True |
| DE-23 | json_rewrite `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json` | h2_6_live_sources: SHA256_MISMATCH/docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json/h2_6 pin, VALUE_MISMATCH/docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json/a5_thrust_target_mN | True |
| DE-24 | unlink_then_mkdir `docs/experiments/s1_readiness/s1_readiness_conditions_v1.json` | h2_6_live_sources: RAISED/OTHER:IsADirectoryError | True |

## Provenance

* Reference files: `scripts/ci_checks.py` 7834474ee8a6af11 (match True); `docs/hardware/h2/h2_6_diagnostics_fixture/build_h2_6_diagnostics_fixture.py` 18498a0508eb2d4e (match True).
* Rust: rustc 1.94.1 (e408947bf 2026-03-25); Cargo.lock sha256 `e650eb9ad054b65cf47fdc7c82cc92a6523e43be78b7c41e0e9f8a69963b7e41`; binary sha256 `5c87782717846964c589eed7fa474a642c85cb388d5c0b1ff8c6ea1339c53fdf`; embedded H2-6 spec sha256 `3be115493fd0b3a3c8f880e30576df6ab027b95558a0b5c5db59647a2c84db8c`.
* Harness `docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_harness.py` sha256 `f8c47a49f25ae9eca876e6134218cd20b922c70650d642d50662c4da4ecc2c63`.
* Python 3.11.15, numpy 2.4.4, scipy 1.17.1, pandas 3.0.2; Linux-6.18.44-fc-v70-x86_64-with-glibc2.39; Intel(R) Xeon(R) Processor @ 2.10GHz x 4; thread env {'OMP_NUM_THREADS': 'unset', 'OPENBLAS_NUM_THREADS': 'unset', 'MKL_NUM_THREADS': 'unset'}.
* Forbidden-identifier scan of crates/**: no hit (CI_PLAN.md sec. 1 principle 6 tokens, plus keeper / heater / hollow / cathode case-insensitive).

## Performance (reported, not a criterion)

Per tree: Python median 0.103 s, Rust median 0.0343 s (speed-up 3.0x, process start included); campaign wall 57.3 s.

## Ledger update requested

* component: C-PROVENANCE-VERIFIER (C-SCRIPTS_CI_CHECKS_PY function subset verify_sha_map, check_prereg_lock, check_audit_manifest, check_hallthruster_pin, check_h2_6_live_sources; C-DOCS_HARDWARE_H2_H2_6_DIAGNOSTICS_FIXTURE verify_sources check semantics); status: ADMITTED; authoritative_implementation: rust: abep_provenance::verifier / abep-provenance-verify; contract_sha256: 95f06eb3e9e31b3ba0019d4bacccbde6050d4b390dbfae64e5d015b453fb49e6; report: docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_report_v1.json
* request: ci_checks h2_6_live_sources (and prereg_lock, audit_manifest, hallthruster_pin) MAY be retired from active CI in a separate later step, after normal CI is re-pointed to abep-provenance-verify (SC-WP-12, RM-R29, CI_PLAN.md W16). This report changes no CI workflow and no Python check.
* note: the builder docs/hardware/h2/h2_6_diagnostics_fixture/ stays class G, not ported; the other seven ci_checks checks stay PYTHON_REFERENCE

## What this is not

Not physics validation, not a CI change, not a port of the H2-6 builder. The Python checks stay in active CI
until a separate step re-points CI (SC-WP-12, RM-R29).
