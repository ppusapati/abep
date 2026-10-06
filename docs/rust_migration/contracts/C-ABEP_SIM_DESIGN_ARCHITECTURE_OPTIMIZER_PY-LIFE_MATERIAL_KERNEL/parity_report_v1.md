# Parity report PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-LIFE_MATERIAL_KERNEL/parity_prereg_v1.json` (sha256 `792cfb404034501998951e2507b77e062b26b141e51b40cf5637459a2e1c2cc6`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `d624358e91dcb8d9705d828769b7c44be14d5bb1` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 491592074; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 316 |
| registered_calls | 16 |
| randomized_calls | 300 |
| python_RETURNED | 308 |
| python_RAISED | 8 |
| calls indicators.life_material | 316 |

Mismatches: 0. Largest float distance: 0 ulp over 18 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-I01 | True | status NOT_EVALUATED, Hall wall-erosion life indicator None / NOT_EVALUATED; violations [] |
| INV-I02 | True | no indicator EVALUATED; violations [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| FileNotFoundError | 2 |
| KeyError | 6 |

Registered divergences (scored against the registered Rust outcome):

* DIV-I01: {'calls': 2, 'rows': [{'case': 'E-I04a', 'python_outcome': 'RETURNED', 'rust_outcome': 'RAISED', 'rust_class': 'NotEvaluatedDependency'}, {'case': 'E-I04b', 'python_outcome': 'RETURNED', 'rust_outcome': 'RAISED', 'rust_class': 'NotEvaluatedDependency'}]}

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-I01 | 0.1983 | 4.647 | 2000 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "partial admission: life_material_indicators without a rotor tip speed (I1); the rotor branch is NOT_EVALUATED in Rust (DIV-I01) until rotor_strength (SC-WP-02) is admitted",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::life::indicators)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
