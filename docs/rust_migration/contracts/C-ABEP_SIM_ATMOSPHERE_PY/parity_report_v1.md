# Parity report v1 - PARITY-C-ABEP_SIM_ATMOSPHERE_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_PY/parity_prereg_v1.json` sha256 `37bcef92084273c587f8cdf852f031e4bca952cc1289b685cf405c85dc14eead`, registered in `481570d54015`.
* Python reference commit `96db5524ec91`; Rust commit `7caaca245775`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905201 (scoring); 1754 vectors; 0 per-test failures.

## Checks

* per_test: pass
* refusal_trees: pass
* determinism: pass
* governing: pass
* all: pass

## Observables

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| atmosphere | status | EXACT_VALUE | 1403 | 0 | 1403 | 0 | 0 | 0 |
| atmosphere | key order | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | rho | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | fO | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | fN2 | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | fO2 | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | T | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | m_mean | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | n | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | flux_kg_m2_s | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | p_ambient_Pa | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | n_O | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | V | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | alt_km | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | solar | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | f107 | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | f107a | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | ap | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | epoch | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | source | EXACT_VALUE | 1393 | 0 | 1393 | 0 | 0 | 0 |
| atmosphere | CONS-A-01 /n m_mean / rho - 1/ (Rust) | ULP_BOUNDED | 1393 | 0 | 1205 | 2.22e-16 | 2.22e-16 | 1 |
| atmosphere | CONS-A-02 /p / (n K_B T) - 1/ (Rust) | ULP_BOUNDED | 1393 | 0 | 1393 | 0 | 0 | 0 |
| orbital_velocity | status | EXACT_VALUE | 350 | 0 | 350 | 0 | 0 | 0 |
| orbital_velocity | V | ULP_BOUNDED | 345 | 0 | 345 | 0 | 0 | 0 |
| msis21_load | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| msis21_load | sha256_16 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| msis21_load | alt_km | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| msis21_load | f107 | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |

## Domain / error parity

15 status-relevant vectors, 0 mismatches.
* DE-A-01 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-02 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-03 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-04 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-05 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-06 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-07 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-08 (atmosphere): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-09 (atmosphere): Python OUT_OF_DOMAIN (KeyError), Rust OUT_OF_DOMAIN - ok
* DE-A-10 (atmosphere): Python OUT_OF_DOMAIN (KeyError), Rust OUT_OF_DOMAIN - ok
* DE-A-11 (orbital_velocity): Python OUT_OF_DOMAIN (ZeroDivisionError), Rust OUT_OF_DOMAIN - ok
* DE-A-12 (orbital_velocity): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-A-13 (orbital_velocity): Python EVALUATED, Rust OUT_OF_DOMAIN, DIV-A-04 - ok
* DE-A-14 (orbital_velocity): Python EVALUATED, Rust OUT_OF_DOMAIN, DIV-A-04 - ok
* DE-A-15 (orbital_velocity): Python EVALUATED, Rust OUT_OF_DOMAIN, DIV-A-04 - ok

| tree | entry | Python | Rust | registered Python | registered Rust | ok |
|---|---|---|---|---|---|---|
| RF-A-01 | msis21_load | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | yes |
| RF-A-01 | atmosphere | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | yes |
| RF-A-02 | msis21_load | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | yes |
| RF-A-02 | atmosphere | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | MODEL_ERROR | yes |
| RF-A-03 | msis21_load | EVALUATED | MODEL_ERROR | EVALUATED | MODEL_ERROR | yes |
| RF-A-03 | atmosphere | EVALUATED | MODEL_ERROR | EVALUATED | MODEL_ERROR | yes |

## Invariants

* Rust two processes byte-identical: True (stdout sha256 `ba6888f29f3f720e...`); Python two evaluations equal: True.
* Governing hashes equal and registered: True.

## Performance (reported, never a criterion)

* PERF-A-01: Python 1.582 s, Rust 0.029 s (median of 3; speed-up 54.2x; Rust = one CLI process including the verified load).

## Notes

* harness: the contracts say the harness is committed 'after this contract and before any comparison'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Recorded as a disclosure, not a change of the contract
* PYTHON_REFERENCE observation (DIV-A-03, CLAUDE.md rule 5): atmosphere() memoizes on round(alt_km, 3) but evaluates at the unrounded altitude, so a later call within 1e-3 km returns the earlier result; the harness clears _MSIS_CACHE before every reference call. For the reference's own governance; not changed here
* PYTHON_REFERENCE observation: when atmosphere_msis21_v1.json is missing, _frozen() stores the CSV before the JSON read fails, so a second call in the same process sees a half-filled cache and raises KeyError instead of FileNotFoundError (both fail closed); the harness evaluates every refusal-tree entry from a fresh reference state, as registered. For the reference's own governance; not changed here

## Ledger update requested

* C-ABEP_SIM_ATMOSPHERE_PY: ADMITTED

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
