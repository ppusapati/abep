# Parity report v1 - PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract `docs/rust_migration/contracts/C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE/parity_prereg_v1.json` sha256 `f67e2fc8f5edd64cb05c9892907b81549d982d538c91b207220b313ee9f57038`, registered in `5b5d432f6595`.
* Python reference commit `0d8922cfe39b`; Rust commit `b1884ea5417a` (git_dirty: 3 path(s)); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4.
* Scoring seed 2026100612; 2813 vectors; 0 per-test failures; 1804 returned values byte-identical; max ulp (E15) 0; 0 reference refusals outside the registered classes (outcome only, DIV-04 / DIV-R02).

## Calls per entry

* R1: 1
* R2: 641
* R3: 1024
* R4: 408
* R5: 6
* R6: 1
* R7: 525
* R8: 207

## Checks

* per_test: pass
* invariants: pass
* reference_unchanged: pass
* governing_hashes: pass
* all: pass

## Invariants

* INV-R-01 (PASS only on a verified, measured, in-domain covering measurement with a frozen basis): pass
* INV-R-02 (replay reproduces every committed cell and GNG-ICP-01): pass
* INV-R-03 (GO only on accepted criteria with verified citations): pass
* INV-R-04 (RVM proposal text == a9_19_rvm.RECORDER_PROPOSALS[RP-A919-01]): pass
* INV-R-05 (two Rust runs byte-identical): pass

## Notes

* R7 citations are evaluated against identical scratch trees written by each implementation (root = <scratch>/base)

## Ledger update requested

* C-DOCS_REQUIREMENTS_RVM_A9: PARTIAL admission on PARITY_PASS (contract PARITY-C-DOCS_REQUIREMENTS_RVM_A9-RULES_AND_ICP_GATE-V1): rvm_rules.py (whole module) and a9_21_icp_gate.evaluate / lock1_release_reportable -> crates/abep-assess (abep_assess::{rvm, icp_gate}); the RVM document builder (build_rvm_a9.py and its row / application modules) stays PYTHON_REFERENCE; the committed rvm_a9_v1.json is consumed sha256-pinned

Parity is not physics validation, not a gate PASS and not a change of any threshold or frozen record.
