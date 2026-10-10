# Parity report PARITY-C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS/parity_prereg_v1.json` (sha256 `c10e00bb56fc2e7fd5caf42b4a0bd74b4deb090543ad9aeda04e4a1faee94b51`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `be028abd0e1b205501e4d77f6de10cac9a1ced53` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 2743347364; harness `scripts/rust_migration/parity_life_v1.py` sha256 `74924f5cb13550ae3beead868a029fc19841739626036a73b7178dc89cc32375`

## Calls

| item | value |
|---|---|
| calls_total | 4583 |
| registered_calls | 583 |
| randomized_calls | 4000 |
| python_RETURNED | 4217 |
| python_RAISED | 366 |
| calls sputter.apid_fit | 1100 |
| calls sputter.yamamura_tawara | 3483 |

Mismatches: 0. Largest float distance: 0 ulp over 7446 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-S01 | True | keys Y, Eth_eV, below_threshold; Y == 0.0 exactly when below_threshold; violations [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| ValueError | 363 |
| ZeroDivisionError | 3 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-S01 | 0.2818 | 0.016 | 20000 evaluations; Rust timed inside life_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "partial admission: kernels yamamura_tawara and apid_fit (S1 / S2); the register builder stays Python reference",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::materials::sputter)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
