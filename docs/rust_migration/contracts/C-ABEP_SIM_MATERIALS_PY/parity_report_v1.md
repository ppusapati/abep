# Parity report PARITY-C-ABEP_SIM_MATERIALS_PY-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_MATERIALS_PY/parity_prereg_v1.json` (sha256 `dd2e51d04ec55776c635f60c5dd7d3cf4dd5646f096a93f9649d755f7f66b46d`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `36f4b3b8bd8f4a902b6ca0a18fd8ace8b38c74a7` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 2911594821; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 2859 |
| registered_calls | 459 |
| randomized_calls | 2400 |
| python_RETURNED | 2843 |
| python_RAISED | 16 |
| calls materials.db | 1 |
| calls materials.gamma_O | 696 |
| calls materials.record | 321 |
| calls materials.see_yield | 746 |
| calls materials.sputter_yield | 752 |
| calls materials.surface_ageing_alpha | 343 |

Mismatches: 0. Largest float distance: 0 ulp over 8468 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-M01 | True | DB names in order, fidelity / source labels kept; violations [] |
| INV-M02 | True | sputter_yield 0.0 at or below Eth; violations [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| KeyError | 1 |
| TypeError | 2 |
| ZeroDivisionError | 9 |
| OverflowError | 4 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-M01 | 0.1475 | 0.006076 | 20000 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_MATERIALS_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "named function subset M0..M5 (Material record and methods, DB rows, surface_ageing_alpha); set_property / table() stay Python reference; inventory WP SC-WP-12 (cross-WP registration by SC-WP-08, to reconcile)",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::materials::db)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
