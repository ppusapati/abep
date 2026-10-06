# Parity report v1 - PARITY-C-ABEP_SIM_COMPRESSOR_PY-V1

Verdict: **PARITY_FAIL** (NOT_ADMITTED). Generated from `parity_report_v1.json`.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_COMPRESSOR_PY/parity_prereg_v1.json` sha256 `454bc47c2dbd5adf72d29ac0eccad8a32f68be93d67bdd430368908922376020`, registered in `ca0e0ecca518`.
* Python reference commit `e3b7e6712d10`; Rust commit `f79c812025dc`.
* Master seed 731905302 (scoring); 2368 vectors generated; the Rust CLI exited with status 101 before writing any result, so no comparison was made.

## Diagnosis

* `"thread 'main' panicked at crates/abep-gaspath/src/rotor_strength.rs:175:52:"`
* `"finite"`
* panicking_requests: `["C03-R-010 compressor.basis_problems (allowables [['NaN', 6.559e8, 7.476e8], [709.88, 8.596e8, 8.763e8]])", "C03-R-011 compressor.basis_problems (allowables [['NaN', 7.067e8, 7.655e8], [610.54, ...], [757.68, ...]])"]`
* found_by: `"crash diagnosis after the execution: the generated scoring requests were sent to the same Rust binary one request per process (Rust only; no Python comparison, no tolerance evaluated)"`
* python_reference: `"evaluated for every vector before the Rust call (the harness evaluates Python first); its outputs were not captured because the execution aborted"`
* classification: `"RUST_DEFECT"`

## Notes

* single scoring execution with seed 731905302 at commit f79c812 (Rust sources as in 1032b70 / 82448cb); the harness of that commit did not catch a Rust CLI crash, so this report is written from the recorded crash by the harness mode 'record-failed-score' (same provenance fields, sources hashed at f79c812)
* RUST_DEFECT: rotor_strength::basis_problems sorted the allowable temperatures with partial_cmp(...).expect("finite") before checking that every value is finite; a registered C03 mutation (kind 10: a NaN allowable value, here the temperature) made the comparison panic. The reference evaluates sorted(Ts) only in the elif branch after the finiteness check and reports 'allowables contain non-finite or non-positive values'. The development seed produced no NaN temperature, so development comparisons did not reach the path
* follow-up (no_retuning): a code fix (finiteness checked before the ordering test; the CLI records a panic as that request's outcome instead of aborting the run) plus a new contract version v2 with fresh scoring seeds; this report stays
* no tolerance, observable, input set, n or decision rule is changed by the follow-up

## Ledger update requested

* C-ABEP_SIM_COMPRESSOR_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_ROTOR_STRENGTH_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)
* C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY: PARITY_FAILED (stays PYTHON_REFERENCE; a code fix needs a new contract version with a fresh seed)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
