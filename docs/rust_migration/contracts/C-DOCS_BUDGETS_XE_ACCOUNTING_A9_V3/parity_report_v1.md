# Parity report v1 - PARITY-C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3-V1

Verdict **ADMITTED** (PARITY_PASS). Contract `docs/rust_migration/contracts/C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3/parity_prereg_v1.json` (sha256 `c3685cb3405474a77b8bd87f3afd9170ec0aa3d3deadebb0e89a611665e1723b`). Python reference `1e2f66d72c01d3d0d413ff85c62de17f528d8f31`; Rust `966a2bf0953b1c3911a9e456cb306ac2e43531bc`.

Scoring seed 255310965: 3590 calls, 3590 pass, 0 fail.

## Per entry point

| entry point | calls | pass | fail |
|---|---|---|---|
| evaluate | 501 | 501 | 0 |
| eval_line | 116 | 116 | 0 |
| book_reserve_and_residual | 622 | 622 | 0 |
| ground_supply | 623 | 623 | 0 |
| case_split_loaded | 1043 | 1043 | 0 |
| ignition_booking_s | 685 | 685 | 0 |

## Invariants

* determinism: pass
* INV-X02_rust: pass
* INV-X03_rust: pass
* INV-X04_rust: pass
* INV-X02_python: pass
* INV-X03_python: pass
* INV-X04_python: pass

## Registered divergences observed

* none

## Performance (reported, not decided on)

* PERF-X01: Python 1.1796 s, Rust 5.6893 s, speed-up 0.207 (Rust: one `abep-mass eval` process evaluating the 500-call list twice incl. JSON I/O; Python: 500 in-process calls (incl. deep copies of the inputs))

## Notes

* Function subset only: the record regeneration (build_doc / render_md) and design_cases are BLOCKED_GOVERNANCE_CONFLICT (contract component.out_of_scope): they emit verbatim C1 provenance / labelled-history strings that the crate-wide principle-6 scan of crates/abep-subsystems (tests/prereg_binding.rs, bound by the NP-THERMAL verification provenance) refuses; an integrator / owner decision is needed before a v2 contract can cover them.
* INV-X02: the X1 split of the 2 / 5 / 10 kg cases reproduces the committed design_cases.loaded_split rows; INV-X03: evaluate on R-X01 reproduces every committed evaluation (all flight and ground totals REFUSED_TBD_INPUTS).

## Ledger update requested

```json
[
 {
  "row": "C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3",
  "partial_admission": {
   "scope": "named function subset X1-X6: case_split_loaded, ignition_booking_s, book_reserve_and_residual, ground_supply, eval_line, evaluate",
   "status": "ADMITTED",
   "parity": "PARITY_PASS",
   "rust_implementation": {
    "crate": "abep-subsystems (abep_subsystems::mass::xe)",
    "paths": [
     "crates/abep-subsystems/src/mass/xe.rs"
    ]
   },
   "contract": {
    "path": "docs/rust_migration/contracts/C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3/parity_prereg_v1.json",
    "id": "PARITY-C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3-V1",
    "sha256": "c3685cb3405474a77b8bd87f3afd9170ec0aa3d3deadebb0e89a611665e1723b"
   },
   "admission_evidence": "docs/rust_migration/contracts/C-DOCS_BUDGETS_XE_ACCOUNTING_A9_V3/parity_report_v1.json"
  },
  "not_in_scope": "build_doc / render_md / design_cases and the remaining builder functions stay PYTHON_REFERENCE: BLOCKED_GOVERNANCE_CONFLICT (principle-6 crate scan); v2 contract after the integrator / owner decision"
 }
]
```
