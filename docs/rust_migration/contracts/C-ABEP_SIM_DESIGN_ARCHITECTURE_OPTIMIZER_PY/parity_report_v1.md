# Parity report v1 - PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-V1

Verdict: **PARITY_PASS** (ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/parity_prereg_v1.json` sha256 `920d11fc0f80cc72992307fef5b4975b34d9b8f4a8b0470d6e3a84395d1f199f`, registered in `7ccbeb9ef96f`.
* Python reference commit `ba8adc3b7b3b`; Rust commit `ba8adc3b7b3b` (git_dirty: none); rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Scoring seed: 1006202610; study grid: full ({'candidates': None, 'compressors': None, 'n_mc': 100}; picks [10, 16, 28, 32, 41, 77]).

## Results

| entry | n | failures | float leaves | bit-identical | max ulp | Python raised | Rust raised |
|---|---|---|---|---|---|---|---|
| study_contexts | 100 | 0 | 0 | 0 | 0.0 | - | - |
| study_pareto | 1 | 0 | 23622 | 23401 | 24.0 | - | - |
| f7:inputs.summary | 1 | 0 | 144 | 144 | 0.0 | 0 | 0 |
| f7:inputs.records | 1 | 0 | 22000 | 22000 | 0.0 | 0 | 0 |
| f7:upstream_context | 44 | 0 | 43529 | 43525 | 28.0 | 3 | 3 |
| f7:context_pareto | 40 | 0 | 151 | 147 | 28.0 | 0 | 0 |
| f7:pareto_mask | 301 | 0 | 0 | 0 | 0.0 | 1 | 1 |
| f7:nondominated_layers | 101 | 0 | 0 | 0 | 0.0 | 1 | 1 |
| f7:design_id | 2 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:context_id | 2 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:wall_gamma | 3 | 0 | 2 | 2 | 0.0 | 1 | 1 |
| f7:plenum | 6 | 0 | 12 | 12 | 0.0 | 2 | 2 |
| f7:context_role | 5 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:higher_pressure_branch | 2 | 0 | 3 | 3 | 0.0 | 1 | 1 |
| f7:rank_precheck | 60 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:require_all_admitted_scenarios | 120 | 0 | 0 | 0 | 0.0 | 83 | 83 |
| f7:robust_over_scenarios | 120 | 0 | 0 | 0 | 0.0 | 8 | 8 |
| f7:design_vector_blocks | 1 | 0 | 111 | 111 | 0.0 | 0 | 0 |
| f7:architecture_questions | 1 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:flight_configuration_elements | 3 | 0 | 7 | 7 | 0.0 | 2 | 2 |
| f7:heat_rejection | 20 | 0 | 19 | 19 | 0.0 | 0 | 0 |
| f7:electron_margin | 2 | 0 | 2 | 2 | 0.0 | 0 | 0 |
| f7:hall_gated_thrust | 4 | 0 | 1 | 1 | 0.0 | 0 | 0 |
| f7:tpmc_backend_policy | 1 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| f7:is_conditional_c1_text | 60 | 0 | 0 | 0 | 0.0 | 0 | 0 |

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

* C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY: partial_admissions += the registered function subset (contract PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-V1) -> abep-design (+ the abep-uq harness binary), status ADMITTED on PARITY_PASS; the module's other functions keep their recorded status
* C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY: partial admission of context_pareto (design part) and the rank_full_system refusal stages under the same contract; evaluate_system / gate verdicts stay with the assessment port (SC-WP-11)
* C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: partial admission of require_all_admitted_scenarios and robust_over_scenarios (SC-WP-10 elements) under the same contract

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
