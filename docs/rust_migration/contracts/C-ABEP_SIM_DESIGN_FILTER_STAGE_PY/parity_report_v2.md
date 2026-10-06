# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_FILTER_STAGE_PY-V2

Verdict: **PARITY_PASS** (ADMITTED). Generated from the JSON report next to this file.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_FILTER_STAGE_PY/parity_prereg_v2.json` sha256 `7f5f81cae17ada210505571a097b3eb8e27dde867ded288cb40a89c184a3aeca`, registered in `20c19eadbe5e`.
* Python reference commit `e3b7e6712d10`; Rust commit `eb228c88337a`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905311 (scoring); 1732 vectors; 0 per-test failures.

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

Scored float leaves: 10987 (10987 bit-identical); EXACT_VALUE leaves: 205832.

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

* Rust two processes byte-identical: True (stdout sha256 `b7819528a683407b...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-F-03: {"ok": true}
* INV-F-04: {"ok": true}
* CONS-F-01: {"n": 47, "n_fail": 0, "max_residual_over_incident": 2.752420559942319e-16, "ok": true}

## Performance (reported, never a criterion)

* PERF-F-01 (600 vectors): Python 0.172 s, Rust 0.398 s (median of 3; speed-up 0.4x; the 600 random F06 apply vectors; Rust = one CLI process incl. JSON).

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring
* v2 re-binds the build provenance after the shared abep-gaspath source change c3a41fb (compressor RUST_DEFECT fix, CLI panic isolation; filter.rs unchanged); v1 (PARITY_PASS) stays; generators, tolerances and decision rules are those of v1, with fresh seeds

## Ledger update requested

* C-ABEP_SIM_DESIGN_FILTER_STAGE_PY: ADMITTED

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
