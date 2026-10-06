# Parity report PARITY-C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-DOCS_EXPERIMENTS_LIFETIME_AO-AO_REGISTER_KERNELS/parity_prereg_v1.json` (sha256 `bf4c3aa9b4264a70f081e1ad2ed022a00afac1eda1361199fdc908a5b6799fbc`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `e7ed70807e61c28d86320cc0c403e47ebe536775` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 1412763212; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 410 |
| registered_calls | 10 |
| randomized_calls | 400 |
| python_RETURNED | 118 |
| python_RAISED | 292 |
| calls aoreg.environment | 108 |
| calls aoreg.index | 302 |

Mismatches: 0. Largest float distance: 0 ulp over 24767 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-L01 | True | R-L01 equals the committed register v5 derived.ao_environment (both); differences [] |
| INV-L02 | True | R-L03 equals the committed register v5 derived.wall_sputter_index (both); differences [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| RuntimeError | 277 |
| ValueError | 1 |
| KeyError | 14 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-L01 | 0.05885 | 0.01497 | 20 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-DOCS_EXPERIMENTS_LIFETIME_AO",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "partial admission: kernels compute_ao_environment and compute_wall_sputter_index (L1 / L2); the register builder stays Python reference",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::life::ao_register)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
