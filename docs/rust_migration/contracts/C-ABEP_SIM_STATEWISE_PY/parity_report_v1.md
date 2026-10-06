# Parity report v1 - PARITY-C-ABEP_SIM_STATEWISE_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_STATEWISE_PY/parity_prereg_v1.json` sha256 `5a76ef3c1c2c52fa3fcdd72a4ee6d14321a82389f0622713325d45869d90ba4d`, registered in `8aaa37f18503`.
* Python reference commit `fa4fcb3bd21f`; Rust commit `9fe20c24c2d0` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: 2026100642; 432 vectors; 0 per-test failures.

## Checks

* per_test: pass
* domain_error: pass
* invariants: pass
* governing: pass
* all: pass

## Observables

| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|
| statewise_quantifier | outcome | 432 | 0 | 432 | 0 | 0 | 0 |
| statewise_quantifier | copied floats (EXACT_VALUE) | 9093 | 0 | 9093 | 0 | 0 | 0 |
| statewise_quantifier | orbit_average_margin (ULP_BOUNDED) | 57 | 0 | 57 | 0 | 0 | 0 |
| statewise_quantifier | error class / message / status | 14 | 0 | 14 | 0 | 0 | 0 |

## Domain / error parity

* DE-B-01: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-02: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-03: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-04: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-05: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-06: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-07: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-08: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-09: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-10: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-11: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-12: Python RAISED ValueError; Rust RAISED ValueError OUT_OF_DOMAIN - ok
* DE-B-13: Python RAISED TypeError; Rust RAISED TypeError OUT_OF_DOMAIN - ok

## Invariants

* INV-B-01: pass
* INV-B-02: pass
* INV-B-04: pass
* INV-B-03: pass

## Ledger update requested

* C-ABEP_SIM_STATEWISE_PY: status ADMITTED (whole module) on PARITY_PASS; authoritative_implementation rust: abep_mission::statewise::statewise_quantifier; contract PARITY-C-ABEP_SIM_STATEWISE_PY-V1

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
