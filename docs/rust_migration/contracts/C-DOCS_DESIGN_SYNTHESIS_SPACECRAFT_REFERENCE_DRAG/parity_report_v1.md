# Parity report v1 - PARITY-C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG/parity_prereg_v1.json` sha256 `2df6586c15981d4750b1b60798480bc5697e5ac654a99b9a1958da57d6d7e9ee`, registered in `ad54447046b2`.
* Python reference commit `fa4fcb3bd21f`; Rust commit `fd03ae079761` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: NOT_APPLICABLE (deterministic builder, no randomized vectors); 12 vectors; 0 per-test failures.

## Checks

* golden: pass
* domain_error: pass
* invariants: pass
* governing: pass
* all: pass

## Domain / error parity

* DE-C-01: Python exit 1  build_json RuntimeError; Rust exit 1 ['RuntimeError: decision record changed: docs/decisions/OD_2026_10_01_A9_13_S6_UPS'] - ok
* DE-C-02: Python exit 1  build_json RuntimeError; Rust exit 1 ['RuntimeError: decision record changed: docs/decisions/OD_2026_10_01_A9_15_rfp_pr'] - ok
* DE-C-03: Python exit 1  build_json FileNotFoundError; Rust exit 1 ['FileNotFoundError: pinned input missing: docs/decisions/OD_2026_10_01_A9_14_S7_S'] - ok
* DE-C-04: Python exit 1 ['CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json'] build_json RETURNED; Rust exit 1 ['RuntimeError: reference module changed: abep_sim/spacecraft_reference_drag.py sh'] - ok
* DE-C-05: Python exit 1  build_json FileNotFoundError; Rust exit 0 ['OK: spacecraft reference drag outputs reproduced'] - ok
* DE-C-06: Python exit 1 ['CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json'] build_json RETURNED; Rust exit 1 ['CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json'] - ok
* DE-C-07: Python exit 1 ['CHECK FAILED (not reproduced): SPACECRAFT_REFERENCE_DRAG.md'] build_json RETURNED; Rust exit 1 ['CHECK FAILED (not reproduced): SPACECRAFT_REFERENCE_DRAG.md'] - ok
* DE-C-08: Python exit 1 ['CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json, SPACECRAFT_REFERENCE_DRAG.md'] build_json RETURNED; Rust exit 1 ['CHECK FAILED (not reproduced): spacecraft_reference_drag_v1.json, SPACECRAFT_REFERENCE_DRAG.md'] - ok
* DE-C-09: Python exit 1  build_json RuntimeError; Rust exit 1 ['RuntimeError: decision record changed: docs/decisions/OD_2026_10_01_A9_13_S6_UPS'] - ok

## Invariants

* INV-C-01: pass
* INV-C-02: pass
* INV-C-03: pass

## Ledger update requested

* C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG: status ADMITTED on PARITY_PASS; authoritative_implementation rust: binary abep-reference-drag-record (crates/abep-mission/src/bin/abep_reference_drag_record.rs), `--check` reproduces the committed v1 record; contract PARITY-C-DOCS_DESIGN_SYNTHESIS_SPACECRAFT_REFERENCE_DRAG-V1; disclosures DIV-C-01 / DIV-C-02

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
