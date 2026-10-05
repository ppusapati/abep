# Parity report v1 - PARITY-C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_MISSION_ENV_PY-CONSTANTS_KERNEL/parity_prereg_v1.json` sha256 `83cc3513cccbab30b59c7fc4a4bd86e2b79574137755a64035d9786f1911c8e8`, registered in `a838533c14c5`.
* Python reference commit `96db5524ec91`; Rust commit `80ac7c78b025`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905203 (scoring); 439 vectors; 0 per-test failures.

## Checks

* per_test: pass
* refusal_trees: pass
* determinism: pass
* governing: pass
* all: pass

## Observables

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|
| mission_env_constants | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| mission_env_constants | J2 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| mission_env_constants | OMEGA_E (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | status | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | field names and order | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | mass_kg (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | bus_frontal_m2 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | bus_cd (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_area_m2 (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_edge_on | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_thickness_m (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_span_m (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_eff (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_deg_per_yr (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_angle_from_thrust_axis_deg (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | array_distance_m (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | pointing_sigma_deg (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | eps_eff (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | bus_housekeeping_W (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | inc_deg (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | ltan_h (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| spacecraft_defaults | intake_cd_ref (bits) | EXACT_VALUE | 1 | 0 | 1 | 0 | 0 | 0 |
| sso_inclination_deg | status | EXACT_VALUE | 437 | 0 | 437 | 0 | 0 | 0 |
| sso_inclination_deg | inclination_deg | ULP_BOUNDED | 429 | 0 | 429 | 0 | 0 | 0 |

## Domain / error parity

8 status-relevant vectors, 0 mismatches.
* DE-C-01 (sso_inclination_deg): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-C-02 (sso_inclination_deg): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-C-03 (sso_inclination_deg): Python OUT_OF_DOMAIN (ZeroDivisionError), Rust OUT_OF_DOMAIN - ok
* DE-C-04 (sso_inclination_deg): Python OUT_OF_DOMAIN (ValueError), Rust OUT_OF_DOMAIN - ok
* DE-C-05 (sso_inclination_deg): Python OUT_OF_DOMAIN (OverflowError), Rust OUT_OF_DOMAIN - ok
* DE-C-06 (sso_inclination_deg): Python OUT_OF_DOMAIN (ZeroDivisionError), Rust OUT_OF_DOMAIN - ok
* DE-C-07 (sso_inclination_deg): Python OUT_OF_DOMAIN (ZeroDivisionError), Rust OUT_OF_DOMAIN - ok
* DE-C-08 (sso_inclination_deg): Python EVALUATED, Rust OUT_OF_DOMAIN, DIV-C-01 - ok

## Invariants

* Rust two processes byte-identical: True (stdout sha256 `a7fd24ffe7974c07...`); Python two evaluations equal: True.
* Governing hashes equal and registered: True.

## Performance (reported, never a criterion)


## Notes

* harness: the contracts say the harness is committed 'after this contract and before any comparison'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Recorded as a disclosure, not a change of the contract

## Ledger update requested

* C-ABEP_SIM_MISSION_ENV_PY: KERNEL_ADMITTED (RM-R17); module stays PYTHON_REFERENCE

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
