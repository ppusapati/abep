# Parity report PARITY-C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS-SCREENING_KERNELS/parity_prereg_v1.json` (sha256 `d0560bcd619e11e09bfb1667d9065934ae6b38275146c759ac3b83bad5a98809`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `c1062357197b5fdbb2086d9394cdd0fb8d69bcfe` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 308060130; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 5492 |
| registered_calls | 492 |
| randomized_calls | 5000 |
| python_RETURNED | 4394 |
| python_RAISED | 1098 |
| calls p4.candidate_screening_state | 546 |
| calls p4.evaluate_gate | 4443 |
| calls p4.final_material_status | 103 |
| calls p4.property_evidenced | 200 |
| calls p4.requirement_evidenced | 200 |

Mismatches: 0. Largest float distance: 0 ulp over 0 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-P01 | True | no PASS / SELECTED / WINNER / QUALIFIED value; violations [] |
| INV-P02 | True | 352 R-P01 cells, every outcome INCOMPLETE_EVIDENCE; violations [] |
| INV-P03 | True | final_material_status OPEN; violations [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| ScreeningError | 1097 |
| AttributeError | 1 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-P01 | 0.2799 | 0.005139 | 17600 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-DOCS_EXPERIMENTS_HALL_ICP_P4_ANODE_MATERIALS",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "partial admission: evaluate_gate (with p4_a9_16_rules.validation_stage_record), candidate_screening_state, final_material_status, requirement_evidenced, property_evidenced (P1..P5); the builder and the other rule functions stay Python reference",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::life::p4)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
