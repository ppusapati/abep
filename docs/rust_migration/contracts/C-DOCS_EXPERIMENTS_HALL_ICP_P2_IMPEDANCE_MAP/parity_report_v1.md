# Parity report C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP v1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP/parity_prereg_v1.json` (sha256 `3486ec4db53a5cd574368743366403708866434a1b7b2851d5934a66bc13e3ea`)
* Python reference commit `fa4fcb3bd21fec8c07a26fe264e1045d5a6bec73`; reference files unchanged at scoring: True
* Rust commit `4e10db6ffc3e515c596f0a078d5cbc8d8c47acd2` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 3315226577; harness `scripts/rust_migration/parity_rf_match_v1.py` sha256 `a48f7a69c12c7d1892dbfd06c459450c9021be9bc5a453bbfa6524d346f3a08d`

## Calls

| item | value |
|---|---|
| calls_total | 1081 |
| registered_calls | 121 |
| randomized_calls | 960 |
| python_RETURNED | 898 |
| python_RAISED | 183 |
| calls rf.abcd_to_s | 61 |
| calls rf.cascade | 1 |
| calls rf.correct_reflection | 62 |
| calls rf.cx | 6 |
| calls rf.deembed_load | 2 |
| calls rf.dissipated_fraction_matched | 104 |
| calls rf.fixture_to_plane | 2 |
| calls rf.gamma_from_z | 63 |
| calls rf.gamma_mag_from_powers | 64 |
| calls rf.ladder_abcd | 109 |
| calls rf.line_peak_stress | 4 |
| calls rf.p_bus_from_generator_input | 5 |
| calls rf.parse_touchstone | 105 |
| calls rf.s_to_abcd | 62 |
| calls rf.sol_correct | 64 |
| calls rf.sol_error_terms | 71 |
| calls rf.transfer_efficiency | 62 |
| calls rf.vi_power_and_impedance | 106 |
| calls rf.vswr | 64 |
| calls rf.z_from_gamma | 62 |
| calls rf.z_in | 2 |

Mismatches: 0. Largest float distance: 0 ulp over 5612 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| determinism | True | Rust outputs of two separate processes byte-identical |
| INV-C02 | True | 10 evaluations (both): p_bus_from_generator_input always PMainsNotPBusError; violations [] |
| INV-C03 | True | 2 evaluations (both): ladder_abcd([]) is the identity ((1, 0), (0, 0), (0, 0), (1, 0)); violations [] |

## Conservation

| id | pass | detail |
|---|---|---|
| CONS-C1 (Rust) | True | 104 ladders: max |AD - BC - 1| = 2.27e-13 (tolerance 1e-9); violations [] |
| CONS-C2 (Rust) | True | 81 unclipped matched two-ports: max |f + |S11|^2 + |S21|^2 - 1| = 2.22e-16 (tolerance 1e-12); violations [] |
| CONS-C1 (Python, recorded) | True | 104 ladders: max |AD - BC - 1| = 2.27e-13 (tolerance 1e-9); violations [] |
| CONS-C2 (Python, recorded) | True | 81 unclipped matched two-ports: max |f + |S11|^2 + |S21|^2 - 1| = 2.22e-16 (tolerance 1e-12); violations [] |
| CONS-C3 (Rust) | True | 24 standards of 8 exactly determined noise-free SOL calls: max |corrected - actual| = 3.38e-16 (tolerance 1e-9); violations [] |

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| TouchstoneError | 35 |
| TypeError | 1 |
| CalibrationSolveError | 6 |
| FrameworkError | 28 |
| RecordError | 100 |
| KeyError | 4 |
| ZeroDivisionError | 3 |
| ValueError | 1 |
| PMainsNotPBusError | 5 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-C01 | 0.6193 | 0.04641 | 10000 evaluations; Rust timed inside power_eval (no process start) |
| PERF-C02 | 0.8809 | 0.06102 | 10000 evaluations; Rust timed inside power_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-DOCS_EXPERIMENTS_HALL_ICP_P2_IMPEDANCE_MAP",
  "status": "PARTIAL_ADMISSION",
  "parity": "PARITY_PASS",
  "scope": "named function subset (RM-R17): p2_framework.py parse_touchstone, sol_error_terms, sol_correct, ladder_abcd, dissipated_fraction_matched, vi_power_and_impedance; p2_impedance_reducer.py cx, gamma_from_z, z_from_gamma, vswr, gamma_mag_from_powers, s_to_abcd, abcd_to_s, cascade, z_in, deembed_load, transfer_efficiency, correct_reflection, fixture_to_plane, line_peak_stress",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::{cplx, rf_match})",
  "python": "verify_line_match_loss and every other function of the P2 package stay PYTHON_REFERENCE (contract component.out_of_scope)"
 },
 {
  "component": "C-DOCS_EXPERIMENTS_HALL_ICP_P1_ICP_BENCH",
  "status": "PARTIAL_ADMISSION",
  "parity": "PARITY_PASS",
  "scope": "p1_reducer.p_bus_from_generator_input only (the P_mains refusal); the row stays SC-WP-03",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::rf_match::p_bus_from_generator_input)"
 }
]
```

## What this is not

* not physics validation and not an impedance prediction: every network, impedance and reading is a caller input
* not an RF component rating (RF_COMPONENT_RATINGS stays TBD_AFTER_IMPEDANCE_MAP)
* not a promotion of any provisional input (RM-R27)
* not a gate PASS (RM-R31)
