# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_FILTER_STAGE_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_FILTER_STAGE_PY/parity_prereg_v1.json` sha256 `a529c7eb687cab7360e25570116ce3816f9cc5444b271bf2be966d570a4425bb`, registered in `6f372234f1ea`.
* Python reference commit `e3b7e6712d10`; Rust commit `82448cb2cce5`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905301 (scoring); 1732 vectors; 0 per-test failures.

## Checks

* per_test: pass
* determinism: pass
* invariants_and_conservation: pass
* materials_equal_db: pass
* threshold_proximity_limit: pass
* all: pass

## Vectors per entry

| entry | n | Python refusals | Rust refusals | not scored at threshold |
|---|---|---|---|---|
| filter.cole | 436 | 7 | 7 | 0 |
| filter.plate | 205 | 4 | 4 | 0 |
| filter.mean_speed | 203 | 2 | 2 | 0 |
| filter.tbd_transport | 4 | 0 | 0 | 0 |
| filter.stage_parameters | 5 | 0 | 0 | 0 |
| filter.apply | 626 | 5 | 5 | 0 |
| filter.backflow | 200 | 0 | 0 | 0 |
| filter.placeholder | 3 | 0 | 0 | 0 |
| filter.construct | 50 | 44 | 44 | 0 |

## Float observables (non-bit-identical leaves only; every scored leaf is in the JSON report)

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|

Scored float leaves: 10836 (10836 bit-identical); EXACT_VALUE leaves: 202571.

## Domain / error parity

62 vectors with a refusal on either side, 0 mismatches.

| entry | Python | Rust | n |
|---|---|---|---|
| filter.apply | FilterStageError | FilterStageError | 5 |
| filter.cole | FilterStageError | FilterStageError | 7 |
| filter.construct | FilterStageError | FilterStageError | 44 |
| filter.mean_speed | KeyError | KeyError | 1 |
| filter.mean_speed | ValueError | ValueError | 1 |
| filter.plate | FilterStageError | FilterStageError | 4 |

## Threshold proximity

0 vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % limit: none.

## Invariants and conservation

* Rust two processes byte-identical: True (stdout sha256 `609831aa0661ca0c...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-F-03: {"ok": true}
* INV-F-04: {"ok": true}
* CONS-F-01: {"n": 40, "n_fail": 0, "max_residual_over_incident": 2.173042348020521e-16, "ok": true}

## Performance (reported, never a criterion)

* PERF-F-01 (600 vectors): Python 0.157 s, Rust 0.311 s (median of 3; speed-up 0.5x; the 600 random F06 apply vectors; Rust = one CLI process incl. JSON).

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring

## Ledger update requested

* C-ABEP_SIM_DESIGN_FILTER_STAGE_PY: ADMITTED

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
