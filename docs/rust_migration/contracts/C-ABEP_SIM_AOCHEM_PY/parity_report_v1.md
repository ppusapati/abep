# Parity report PARITY-C-ABEP_SIM_AOCHEM_PY-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_AOCHEM_PY/parity_prereg_v1.json` (sha256 `b8e47642a6105cb8d10cb1db6f6fcb8cfde76c414a0fa511a62727d4b5e8020e`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `2f99b9fd46b892de25b60a898be15350bb61e124` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 3464391773; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 5547 |
| registered_calls | 3147 |
| randomized_calls | 2400 |
| python_RETURNED | 5453 |
| python_RAISED | 94 |
| calls aochem.ao_flux | 789 |
| calls aochem.erosion_depth_um | 449 |
| calls aochem.fluence | 2303 |
| calls aochem.inlet_composition | 789 |
| calls aochem.material_report | 783 |
| calls aochem.recombination_fraction | 433 |
| calls aochem.tables | 1 |

Mismatches: 0. Largest float distance: 0 ulp over 29417 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-A01 | True | 744 finite inlet_composition results per implementation: |sum out - sum in| <= 1e-14 max(1, sum) and fO <= fO_in for 0 <= survival <= 1; violations py [] rust [] |
| INV-A02 | True | material_report rows in requested order with one fluence; violations py [] rust [] |

## Conservation

| id | pass | detail |
|---|---|---|
| CONS-A01 (Rust) | True | inlet_composition mass split (INV-A01 rule) |
| CONS-A01 (Python, recorded) | True | same rule on the Python outputs |

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| KeyError | 91 |
| ZeroDivisionError | 1 |
| OverflowError | 2 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-A01 | 0.3288 | 0.01579 | 5000 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_AOCHEM_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "named function subset A0..A6 (every function, AOParams and the two numeric tables); MATERIAL_CLASS (descriptive text, no consumer) stays Python reference text, not ported",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::materials::aochem)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
