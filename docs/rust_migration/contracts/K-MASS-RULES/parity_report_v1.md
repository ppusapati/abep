# Parity report v1 - PARITY-K-MASS-RULES-V1

Verdict **ADMITTED** (PARITY_PASS). Contract `docs/rust_migration/contracts/K-MASS-RULES/parity_prereg_v1.json` (sha256 `0e962c03bc01abb9afde184c48c83427c295710310112bb3d23a5e37ac0f302c`). Python reference `1e2f66d72c01d3d0d413ff85c62de17f528d8f31`; Rust `53768f924f03340ac6e6ac99765eb590ddca66e6`.

Scoring seed 3918911878: 8749 calls, 8749 pass, 0 fail.

## Per entry point

| entry point | calls | pass | fail |
|---|---|---|---|
| _unresolved | 633 | 633 | 0 |
| line_mev_value | 1276 | 1276 | 0 |
| rollup | 1021 | 1021 | 0 |
| system_margin | 634 | 634 | 0 |
| harness_row60 | 624 | 624 | 0 |
| closure_state | 852 | 852 | 0 |
| system_margin_bid | 633 | 633 | 0 |
| assert_bid_margin_reading | 531 | 531 | 0 |
| rk | 2015 | 2015 | 0 |
| assert_no_margin_relaxation | 530 | 530 | 0 |

## Invariants

* determinism: pass
* no_pass_rust: pass
* no_pass_python: pass
* INV-K02_rollup_identity_rust_failures: pass
* INV-K02_rollup_identity_python_failures: pass
* VS-K01: pass
* INV-K04: pass

## Registered divergences observed

* DIV-K01 E-K06 cfg C1: Rust matches the registered outcome: True; Python RETURNED
* DIV-K01 E-K06 cfg X: Rust matches the registered outcome: True; Python RETURNED
* DIV-K02 E-K06 AL-C1 None: Rust matches the registered outcome: True; Python RETURNED
* DIV-K02 E-K06 AL-C1 0.5: Rust matches the registered outcome: True; Python RETURNED

## Performance (reported, not decided on)

* PERF-K01: Python 0.5356 s, Rust 2.1159 s, speed-up 0.253 (Rust: one `abep-mass eval` process evaluating the 2000-call list twice (determinism) incl. JSON I/O; Python: 2000 in-process calls)

## Notes

* CPython 3.11 builtin sum() over floats is sequential double addition (3.12+ uses compensated summation); the Rust kernel reproduces the 3.11 reference environment.
* DIV-K01 / DIV-K02: the Rust roll-up refuses a non-flight configuration and any AL-C1 line (C1 GROUND_REFERENCE_ONLY never enters a flight mass roll-up); scored against the registered Rust outcome.
* TypeError messages of malformed inputs differ in wording (class scored only, as registered).

## Ledger update requested

```json
[
 {
  "row": "C-DOCS_BUDGETS_MASS_POWER_A9_V3",
  "kernel": "K-MASS-RULES",
  "partial_admission": {
   "scope": "extract_and_parity_kernel K-MASS-RULES: rk, _kg, line_mev_value, system_margin, harness_row60, closure_state, _unresolved, assert_no_margin_relaxation, rollup (v3 builder) + system_margin_bid, assert_bid_margin_reading (v5 builder)",
   "status": "ADMITTED",
   "parity": "PARITY_PASS",
   "rust_implementation": {
    "crate": "abep-subsystems (abep_subsystems::mass::rules)",
    "paths": [
     "crates/abep-subsystems/src/mass/rules.rs"
    ]
   },
   "contract": {
    "path": "docs/rust_migration/contracts/K-MASS-RULES/parity_prereg_v1.json",
    "id": "PARITY-K-MASS-RULES-V1",
    "sha256": "0e962c03bc01abb9afde184c48c83427c295710310112bb3d23a5e37ac0f302c"
   },
   "admission_evidence": "docs/rust_migration/contracts/K-MASS-RULES/parity_report_v1.json",
   "report_disclosures": "registered divergences DIV-K01 / DIV-K02 (Rust refuses a C1 / non-flight roll-up)"
  },
  "row_status": "unchanged (class H host; the v3 record stays history)",
  "active_consumer": "C-DOCS_BUDGETS_MASS_POWER_A9_V5"
 }
]
```
