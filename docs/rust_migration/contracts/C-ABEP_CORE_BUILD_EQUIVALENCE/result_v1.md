# abep_core build-equivalence addendum v1 — result: **EQUIVALENT**

Addendum `docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/addendum_v1.json` (sha256 `672baa15b1cab07b912c245d2eadc57a002109a1f9f4e4e5ce1bd9b9c7d38256`), executed 2026-10-05T11:12:26Z at `3ca48e8f6f70b1408de9bce226fe772a251b147d` (dirty: True). Generated from `result_v1.json` by `scripts/rust_migration/run_abep_core_build_equivalence.py`.

| check | held | detail |
|---|---|---|
| EQ-01 abep_core sources = parity_report_v2 | True | 6 files |
| EQ-02 toolchain | True | rustc 1.94.1 (e408947bf 2026-03-25); cargo 1.94.1 (29ea6fb6a 2026-03-24) |
| EQ-03 feature set | True | abep_core features [[]]; forbidden packages [] |
| S0 `cargo test --release` in abep_core | True | test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s; test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s |
| EQ-04 outputs bit-identical to B0 | True | 493 cases |

| build | total sha256 | equal to B0 | differing cases |
|---|---|---|---|
| B0 recorded extension `eb586f0386e793fa…` | `3839b536a4dc4ff0c951f8bda33c238cf2fbc66c82342f2b67a892a36ae6178a` | reference | - |
| B1_workspace_release_standalone_profile | `3839b536a4dc4ff0c951f8bda33c238cf2fbc66c82342f2b67a892a36ae6178a` | True | 0 |
| B2_workspace_debug | `3839b536a4dc4ff0c951f8bda33c238cf2fbc66c82342f2b67a892a36ae6178a` | True | 0 |
| B3_workspace_release | `3839b536a4dc4ff0c951f8bda33c238cf2fbc66c82342f2b67a892a36ae6178a` | True | 0 |

EQUIVALENT means the workspace path-dependency build of abep_core (rlib, no `python` feature) reproduces the admitted Kernel-1 binary bit for bit on the registered cases, so the parity_report_v2 ADMITTED status carries over to that consumption. It admits nothing else and is not physics evidence.
