# Parity report v1 - PARITY-C-DOCS_BUDGETS_MASS_POWER_A9_V5-V1

Verdict **ADMITTED** (PARITY_PASS). Contract `docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_prereg_v1.json` (sha256 `3ca4edef06b9f79242e6638db21cf59d609639f8a7ad466108c4538344876ad0`). Python reference `1e2f66d72c01d3d0d413ff85c62de17f528d8f31`; Rust `9fbd35088bb22e651409d697e7e0d6c785e57d94`.

Scoring seed 2307932994: 1729 calls, 1729 pass, 0 fail.

## Per entry point

| entry point | calls | pass | fail |
|---|---|---|---|
| build_doc_v5 | 9 | 9 | 0 |
| a9_26_message2 | 6 | 6 | 0 |
| rollup_v5 | 618 | 618 | 0 |
| unresolved_v5 | 430 | 430 | 0 |
| set_al09 | 329 | 329 | 0 |
| wet_mass | 330 | 330 | 0 |
| wet_mass_pinned | 7 | 7 | 0 |

## Invariants

* determinism: pass
* no_pass_rust: pass
* no_pass_python: pass
* INV-V01: pass
* INV-V02: pass
* INV-V03: pass
* INV-V04: pass
* INV-V06: pass
* VS-01: pass
* CONS-V01_record: pass

## E1 record bytes

* JSON sha256 python / rust / committed: `3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a` / `3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a` / `3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a`
* Markdown sha256 python / rust / committed: `50b4867e7e60e132db01e2213a2d3a87ab1ffdd5ca2f0fcf60a8ec3ae57e875e` / `50b4867e7e60e132db01e2213a2d3a87ab1ffdd5ca2f0fcf60a8ec3ae57e875e` / `50b4867e7e60e132db01e2213a2d3a87ab1ffdd5ca2f0fcf60a8ec3ae57e875e`
* pass: True

## Registered divergences observed

* DIV-V03 DIV-V03 RT-01: Rust matches the registered outcome: True; Python RAISED
* DIV-V03 DIV-V03 RT-02: Rust matches the registered outcome: True; Python RAISED
* DIV-V03 DIV-V03 RT-03: Rust matches the registered outcome: True; Python RAISED
* DIV-V03 DIV-V03 RT-04: Rust matches the registered outcome: True; Python RAISED
* DIV-V03 DIV-V03 RT-05: Rust matches the registered outcome: True; Python RAISED
* DIV-V03 DIV-V03 RT-06: Rust matches the registered outcome: True; Python RETURNED
* DIV-V01 E-V02 cfg C1: Rust matches the registered outcome: True; Python RETURNED
* DIV-V02 E-V02 AL-C1: Rust matches the registered outcome: True; Python RETURNED

## Performance (reported, not decided on)

* PERF-V01: Python 0.6833 s, Rust 0.2043 s, speed-up 3.344 (Rust: one `abep-mass eval` process building the record 20 times, twice; Python: 20 in-process render() calls)

## Notes

* E1: the Rust build reproduces the committed frozen record (5eee4b8) byte for byte from its six pinned inputs; the record files are only read, never written.
* Owner arithmetic (A9.26 sec. 3) reproduced exactly: dry 38.34901052 kg; HARD_40_WET wet 40.34901052 / 43.34901052 / 48.34901052 kg at 2 / 5 / 10 kg loaded Xe, each DOES_NOT_CLOSE; MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED.
* VS-01: AL-07 stays 6.0 kg MEV_PLANNING_FLOOR with its committed labels; A9.28 status PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT / AFI-02-RA1_OPEN read from the sha256-verified A9.28 record.
* Cutover: the v5 PINS include the v3 / v4 builder .py files (sha256 only); when the Python tree is archived the Rust builder needs them kept as archived evidence or a successor pin set (new contract version).
* crates/abep-subsystems/src/lib.rs and Cargo.toml changed (mass module, flate2 dev-dependency): the NP-THERMAL-CATHODELESS verification report's recorded sha256 of those two files needs re-recording.

## Ledger update requested

```json
[
 {
  "row": "C-DOCS_BUDGETS_MASS_POWER_A9_V5",
  "transition": {
   "from": "PYTHON_REFERENCE",
   "to": "ADMITTED"
  },
  "scope": "the whole builder (build_doc / render_md with verify_pins, a9_26_message2, rollup_v5, unresolved_v5, set_al09); main() is replaced by `abep-mass build-v5 / check-v5`",
  "authoritative_implementation": {
   "kind": "rust",
   "crate": "abep-subsystems (abep_subsystems::mass::v5)",
   "paths": [
    "crates/abep-subsystems/src/mass/v5.rs",
    "crates/abep-subsystems/src/mass/rules.rs"
   ]
  },
  "contract": {
   "path": "docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_prereg_v1.json",
   "id": "PARITY-C-DOCS_BUDGETS_MASS_POWER_A9_V5-V1",
   "sha256": "3ca4edef06b9f79242e6638db21cf59d609639f8a7ad466108c4538344876ad0"
  },
  "admission_evidence": "docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_report_v1.json",
  "value_status": "AL-07 6.0 kg PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT / AFI-02-RA1_OPEN preserved (VS-01); never promoted to CBE / measured / frozen truth",
  "report_disclosures": "DIV-V01 / DIV-V02 (C1 / non-flight roll-up refused), DIV-V03 (production wet-mass read verifies the record sha256); cutover pin note"
 },
 {
  "row": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY",
  "partial_admission": {
   "scope": "wet_mass (with _obj, supplied_objective and intake_synthesis.require_f1q02_label)",
   "status": "ADMITTED",
   "parity": "PARITY_PASS",
   "rust_implementation": {
    "crate": "abep-subsystems (abep_subsystems::mass::wet_mass)",
    "paths": [
     "crates/abep-subsystems/src/mass/wet_mass.rs"
    ]
   },
   "contract": {
    "path": "docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_prereg_v1.json",
    "id": "PARITY-C-DOCS_BUDGETS_MASS_POWER_A9_V5-V1",
    "sha256": "3ca4edef06b9f79242e6638db21cf59d609639f8a7ad466108c4538344876ad0"
   },
   "admission_evidence": "docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_report_v1.json"
  }
 }
]
```
