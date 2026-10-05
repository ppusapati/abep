# Parity report v1 - PARITY-C-ABEP_SIM_CONSTANTS_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_CONSTANTS_PY/parity_prereg_v1.json` sha256 `1f7bef49973b985fad3fd9dcb86e63e272e3c438765f89c7e137bbfe479492c0`, registered in `12df46135339`.
* Python reference commit `96db5524ec91`; Rust commit `7f43b4f2407d`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 0 (scoring); 1 vectors; 0 per-test failures.

## Checks

* per_test: pass
* refusal_trees: pass
* determinism: pass
* governing: pass
* all: pass

## Observables

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| constants | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | G0 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | E_CHARGE (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | AMU (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | K_B (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | MU_EARTH (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | R_EARTH (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | M_O (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | M_N2 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | M_O2 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | M_XE (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | DE-B-01 species He | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| constants | INV-B-02 species keys | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |

## Domain / error parity

0 status-relevant vectors, 0 mismatches.

## Invariants

* Rust two processes byte-identical: True (stdout sha256 `f4acf50378e2b4b8...`); Python two evaluations equal: True.
* Governing hashes equal and registered: True.

## Performance (reported, never a criterion)


## Notes

* harness: the contracts say the harness is committed 'after this contract and before any comparison'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Recorded as a disclosure, not a change of the contract

## Ledger update requested

* C-ABEP_SIM_CONSTANTS_PY: ADMITTED

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
