# Parity report v1 - PARITY-C-ABEP_SIM_COMPRESSOR_PY-V2

Verdict: **PARITY_PASS** (ADMITTED). Generated from the JSON report next to this file.

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_COMPRESSOR_PY/parity_prereg_v2.json` sha256 `01b1c133f359d23455241ce9818a3b77c3f2883072ce4a2ff1da32378199f07b`, registered in `08b83ab3472b`.
* Python reference commit `e3b7e6712d10`; Rust commit `0b28a7cd7678`; rustc 1.94.1 (e408947bf 2026-03-25).
* Environment: Python 3.11.15, numpy 2.4.4, scipy 1.17.1, scipy-openblas 0.3.31.188.0, Intel(R) Xeon(R) Processor @ 2.10GHz.
* Master seed 731905312 (scoring); 2368 vectors; 0 per-test failures.

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
| compressor.run | 304 | 3 | 3 | 0 |
| compressor.size_for | 24 | 0 | 0 | 0 |
| compressor.basis_problems | 200 | 0 | 0 | 0 |
| compressor.allowables_at | 100 | 0 | 0 | 0 |
| compressor.tip_speed_allowable | 60 | 0 | 0 | 0 |
| compressor.qualify_rotor | 311 | 0 | 0 | 0 |
| compressor.register_basis | 4 | 2 | 2 | 0 |
| compressor.inlet_record | 111 | 11 | 11 | 0 |
| compressor.search_grid | 25 | 4 | 4 | 0 |
| compressor.r_turbo_from_area | 34 | 0 | 0 | 0 |
| compressor.hub_geometry | 33 | 0 | 0 | 0 |
| compressor.rpm_from_tip | 33 | 0 | 0 | 0 |
| compressor.material_admission | 163 | 1 | 1 | 0 |
| compressor.validate_design | 109 | 9 | 9 | 0 |
| compressor.validate_coefficient | 121 | 98 | 98 | 0 |
| compressor.strict_blockers | 60 | 0 | 0 | 0 |
| compressor.evaluate_design | 402 | 1 | 1 | 0 |
| compressor.stage_trace | 100 | 0 | 0 | 0 |
| compressor.drag_knudsen | 100 | 0 | 0 | 0 |
| compressor.pareto_front | 50 | 0 | 0 | 0 |
| compressor.synthesize | 8 | 1 | 1 | 0 |
| compressor.size_for_comparison | 4 | 0 | 0 | 0 |
| compressor.constants | 1 | 0 | 0 | 0 |
| compressor.ledger_slot | 11 | 0 | 0 | 0 |

## Float observables (non-bit-identical leaves only; every scored leaf is in the JSON report)

| entry | observable | class | n | fail | bit-identical | max abs diff | max rel diff | max ulp |
|---|---|---|---|---|---|---|---|---|

Scored float leaves: 239189 (239189 bit-identical); EXACT_VALUE leaves: 346886.

Reported, not scored:

* compressor.run iterations: n 301, max abs diff 0, max rel diff 0
* compressor.size_for iterations: n 24, max abs diff 0, max rel diff 0

## Domain / error parity

130 vectors with a refusal on either side, 0 mismatches.

| entry | Python | Rust | n |
|---|---|---|---|
| compressor.evaluate_design | SynthesisInputError | SynthesisInputError | 1 |
| compressor.inlet_record | SynthesisInputError | SynthesisInputError | 11 |
| compressor.material_admission | SynthesisInputError | SynthesisInputError | 1 |
| compressor.register_basis | ValueError | ValueError | 2 |
| compressor.run | KeyError | KeyError | 1 |
| compressor.run | OverflowError | OverflowError | 2 |
| compressor.search_grid | SynthesisInputError | SynthesisInputError | 4 |
| compressor.synthesize | SynthesisInputError | SynthesisInputError | 1 |
| compressor.validate_coefficient | SynthesisInputError | SynthesisInputError | 98 |
| compressor.validate_design | SynthesisInputError | SynthesisInputError | 9 |

## Threshold proximity

0 vectors NOT_SCORED_AT_THRESHOLD; entries over the 1 % limit: none.

## Invariants and conservation

* Rust two processes byte-identical: True (stdout sha256 `425edb213e6cf37e...`); Python two evaluations equal: True.
* materials_equal_db (INV-C-05 / DIV-P-03): true
* INV-C-02: {"ok": true}
* INV-C-04: {"ok": true}
* CONS-C-01: {"n": 248, "n_fail": 0, "ok": true}
* CONS-C-02: {"n": 288, "n_fail": 0, "max_residual_rel": 1.8055253878303546e-16, "ok": true}

## Performance (reported, never a criterion)

* PERF-C-01 (1 vectors): Python 0.416 s, Rust 0.398 s (median of 3; speed-up 1.0x; synthesize() with the default grid (2160 designs), one inlet).
* PERF-C-02 (24 vectors): Python 0.074 s, Rust 0.055 s (median of 3; speed-up 1.3x; the 24 C02 size_for vectors).

## Notes

* harness: the contract says the harness is committed 'after this contract and before the scoring run'. It was developed with development-seed comparisons (never scored, no report) and committed before the single scoring run; every scored generator, tolerance and decision rule is the registered one. Leaf classification (copied floats = non-zero Python floats that occur among the vector's inputs, EXACT_VALUE; every other float the entry's class; in the transient entries only the leaves copied by construction) is fixed in the harness docstring
* spec_formats.coeffs: DragCompressor has 27 dataclass fields (v1 said 30; corrected in v2); the vectors carry all 27 plus rotor_strength_basis_id and rotor_stock_thickness_m
* vector counts: C01 carries the golden defaults vector plus the three registered edges (E-C-01..03) next to the 300 random vectors; C06 carries all 11 listed E-C-04 edges (the count '+ 10' of the contract under-counts the listed items); every listed vector is scored
* C22 compares the compressor slot of architecture_optimizer.official_ledger ('hall_icp_neutralizer'): P_W, evidence_class, source and the ledger label; the slot status is NOT_EVALUATED in both (row 22 not supplied, INV-C-03)
* v2 follows the NOT_ADMITTED v1 execution (RUST_DEFECT: the Rust CLI panicked in rotor_strength::basis_problems on a NaN allowable temperature; fix c3a41fb); generators, tolerances and decision rules are those of v1, with fresh seeds. The CLI now records a panic as the request's outcome (error_class RUST_PANIC, never equal to a Python class)

## Ledger update requested

* C-ABEP_SIM_COMPRESSOR_PY: ADMITTED
* C-ABEP_SIM_ROTOR_STRENGTH_PY: ADMITTED
* C-ABEP_SIM_DESIGN_COMPRESSOR_SYNTHESIS_PY: ADMITTED (computational subset, RM-R17)
* SC-WP-02 gate 'compressor load (ICD row 22) not supplied': PORTED (NOT_EVALUATED slot; architecture_optimizer.official_ledger compressor branch only)

Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.
