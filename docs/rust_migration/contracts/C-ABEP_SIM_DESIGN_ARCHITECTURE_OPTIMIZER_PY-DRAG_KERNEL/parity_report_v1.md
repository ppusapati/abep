# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL/parity_prereg_v1.json` sha256 `8f20c1966c9f4227c184ac3133fc6d20c3dd1f2e1d551105ee8d7fe07e29b85f`, registered in `827094844df6`.
* Python reference commit `fa4fcb3bd21f`; Rust commit `17e0e8d633da` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: 2026100644; 1686 vectors; 0 per-test failures.

## Checks

* per_test: pass
* domain_error: pass
* invariants: pass
* governing: pass
* all: pass

## Observables

| entry | observable | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|
| drag_table | outcome | 1 | 0 | 1 | 0 | 0 | 0 |
| drag_table | copied floats (EXACT_VALUE) | 31520 | 0 | 31520 | 0 | 0 | 0 |
| drag_table | */D_per_area_N_m2 (ULP_BOUNDED) | 15760 | 0 | 15760 | 0 | 0 | 0 |
| drag_table | */SE_per_area_N_m2 (ULP_BOUNDED) | 15760 | 0 | 15760 | 0 | 0 | 0 |
| hall_response_status | outcome | 5 | 0 | 5 | 0 | 0 | 0 |
| supplied_objective | outcome | 411 | 0 | 411 | 0 | 0 | 0 |
| supplied_objective | copied floats (EXACT_VALUE) | 398 | 0 | 398 | 0 | 0 | 0 |
| supplied_objective | error class / message / status | 10 | 0 | 10 | 0 | 0 | 0 |
| thrust_minus_drag | outcome | 1268 | 0 | 1268 | 0 | 0 | 0 |
| thrust_minus_drag | copied floats (EXACT_VALUE) | 1871 | 0 | 1871 | 0 | 0 | 0 |
| thrust_minus_drag | value (ULP_BOUNDED) | 622 | 0 | 622 | 0 | 0 | 0 |
| thrust_minus_drag | drag_total_N (ULP_BOUNDED) | 622 | 0 | 622 | 0 | 0 | 0 |
| thrust_minus_drag | error class / message / status | 5 | 0 | 5 | 0 | 0 | 0 |
| statewise_t_minus_d | outcome | 1 | 0 | 1 | 0 | 0 | 0 |
| statewise_t_minus_d | */objectives/*/partial/D_intake_N (ULP_BOUNDED) | 5880 | 0 | 5880 | 0 | 0 | 0 |

## Domain / error parity

* DE-D-01: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-02: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-03: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-04: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-05: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-06: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-07: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-08: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-09: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-10: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-14: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-15: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-16: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-17: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-18: Python RAISED OptimizerError; Rust RAISED OptimizerError OUT_OF_DOMAIN - ok
* DE-D-11: Python RETURNED ; Rust RAISED MODEL_ERROR (DIV-D-01) - ok
* DE-D-12: Python RAISED FileNotFoundError; Rust RAISED MODEL_ERROR (FileNotFoundError -> MODEL_ERROR (I/O)) - ok
* DE-D-13: Python RETURNED ; Rust RAISED MODEL_ERROR (DIV-D-01) - ok

## Invariants

* INV-D-01: pass
* INV-D-02: pass
* INV-D-03: pass
* INV-D-05: pass
* INV-D-04: pass

## Performance (reported, never a criterion)

* DT python median s (cold process incl. imports): 0.780025554000531
* DT rust median s (cold process incl. load + sha256): 0.20497701699969184
* speed-up: 3.8054293374837416

## Ledger update requested

* C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY: partial_admissions += named function subset (RM-R17) drag_table, hall_response_status, supplied_objective, _obj, thrust_minus_drag -> abep-mission (abep_mission::intake_drag, abep_mission::objective) plus the Rust statewise T - D record abep_mission::statewise_td, status ADMITTED on PARITY_PASS; module stays PYTHON_REFERENCE; contract PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1; disclosures DIV-D-01 (pinned governed inputs), findings F-D-01 / F-D-02

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
