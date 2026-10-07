# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/parity_prereg_v1.json` sha256 `06559c1a23b64b8b4d96e8a6abd5c0560039f36c36cf48022d1613462667efaf`, registered in `b70623d71daf`.
* Python reference commit `ba8adc3b7b3b`; Rust commit `ba8adc3b7b3b` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: 1006202620; study grid: full ({'candidates': None, 'compressors': None, 'n_mc': 100}; picks [10, 16, 28, 32, 41, 77]).

## Results

| entry | n | failures | float leaves | bit-identical | max ulp | Python raised | Rust raised |
|---|---|---|---|---|---|---|---|
| study_f8 | 1 | 0 | 5512 | 5472 | 256.0 | - | - |
| f8:rng.stream | 303 | 0 | 24240 | 24240 | 0.0 | 0 | 0 |
| f8:stable_seed | 680 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f8:draw_sha | 480 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f8:np_percentile | 301 | 0 | 301 | 301 | 0.0 | 0 | 0 |
| f8:perturbed | 2000 | 0 | 12000 | 12000 | 0.0 | 0 | 0 |
| f8:record_se_index | 1 | 0 | 3054 | 3054 | 0.0 | 0 | 0 |
| f8:theta_ratio_index | 1 | 0 | 960 | 960 | 0.0 | 0 | 0 |
| f8:fixed_coefficients | 1 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f8:plant_with_overrides | 32 | 0 | 240 | 240 | 0.0 | 2 | 2 |
| f8:state_eval | 40 | 0 | 160 | 160 | 0.0 | 0 | 0 |
| f8:tpmc_monte_carlo | 41 | 0 | 2048 | 2041 | 2.0 | 0 | 0 |
| f8:design_gate_snapshot | 1 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f8:uq_axes | 1 | 0 | 0 | 0 | 0.0 | 0 | 0 |

## Invariants

* INV-F8-01 gates unchanged: {'python': True, 'rust': True}
* INV-F8-02 robust set reported: {'python_n_members': 0, 'rust_n_members': 0}
* INV-F8-04 no representative: {'python': True, 'rust': True}
* INV-F7-01 members feasible: True

## Performance (reported, never a criterion)

* rust_study_wall_s: 3351.0278257789996
* rust_f7_s: 3251.639060666
* rust_f8_s: 98.114271085
* python_f7_cpu_s: 2353.220883291
* python_f8_cpu_s: 121.8194331640002

## Campaign history

* execution: scoring (aborted before any comparison); utc: 2026-10-06T18:44Z .. 2026-10-06T20:26Z; rust_commit: 0311af2; what_happened: the Rust study computed all 100 F7 contexts, but three context-bin writes (ctx_028 and ctx_029 at 18:53Z, ctx_078 at 19:24Z) left zero-byte files on the shared scratch volume (transient out-of-space / I/O failure); the CLI's write check then returned a RAISED HarnessError outcome (its message was not captured). The harness did not check the study outcome, ran the Python study, and stopped with FileNotFoundError on contexts.json at the first line of compare_contexts, before any comparison; results_seen: none (no comparison computed; no report written; the randomized vectors were never generated); fix: harness only, no random draw consumed: the study directory is cleared before each run, a free-space floor is checked before the study, and the study outcome is checked (a CLI HarnessError aborts before the Python study and is logged here; a contract-class RAISED is scored as a failure). The Rust source is unchanged (same commit)
* execution: scoring; utc: 2026-10-07T17:25:47Z; host: vm; rust_commit: ba8adc3b7b3bf9c4a0594a42bed3c609638353a5; verdict_basis: this execution

## Ledger update requested

* C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY: partial_admissions += the registered function subset (contract PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1) -> abep-uq (F8), abep-rng (numpy stream semantics), status ADMITTED on PARITY_PASS; the module's other functions keep their recorded status
* NI / infrastructure: abep-rng registered numpy PCG64 / SeedSequence / Generator.standard_normal stream (EXACT_STREAM, A9.29 sec. 7) admitted with this contract

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
