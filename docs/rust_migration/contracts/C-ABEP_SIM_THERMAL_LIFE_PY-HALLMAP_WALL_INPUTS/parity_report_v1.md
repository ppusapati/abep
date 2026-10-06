# Parity report PARITY-C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS-V1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_THERMAL_LIFE_PY-HALLMAP_WALL_INPUTS/parity_prereg_v1.json` (sha256 `7a2ec2f434db368879d4e4d3ab87372f191ebc2c4f146da8a22c6be03d94c1f2`)
* Python reference commit `e462e35ed0ce6092f47e1d1b05119501cf4d7eb6`; reference files unchanged at scoring: True
* Rust commit `4592e8f84556d98e586459842c37fe60b0a4dcca` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 1657292530; harness `scripts/rust_migration/parity_life_v1.py` sha256 `506f2aafc24743e39cd9df8bfcfe8da6ad1d05a543cceb6f9dd35f7317634f4f`

## Calls

| item | value |
|---|---|
| calls_total | 2363 |
| registered_calls | 63 |
| randomized_calls | 2300 |
| python_RETURNED | 725 |
| python_RAISED | 1638 |
| calls hallwall.hallmap_wall_inputs | 2363 |

Mismatches: 0. Largest float distance: 0 ulp over 2900 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-DET | True | Rust outputs of two separate processes byte-identical |
| INV-W01 | True | 310 REAL-ensemble calls (credible set EMPTY): every call RAISED ValueError in both, no Hall wall-flux input formed, Hall-erosion life NOT_EVALUATED; violations [] |
| INV-W02 | True | returned records model-derived with trusted wall provenance; violations [] |

## Conservation

Not applicable (contract conservation_checks.applicable false).

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| ValueError | 1607 |
| TypeError | 30 |
| KeyError | 1 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-W01 | 0.6563 | 0.2174 | 5000 evaluations; Rust timed inside life_eval (no process start) |

## Findings

* aborted scoring execution recorded in campaign_history: harness defect: the randomized generator deleted an already-deleted point field (KeyError 'discharge_power_W' in hw_calls.draw) while building the call list; no Python reference call and no Rust call was executed. Fixed by pop(f, None), which consumes no random draw, so every other generated input is unchanged; scoring then ran once

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_THERMAL_LIFE_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "partial admission: hallmap_wall_inputs (W1); the other thermal_life functions are SC-WP-06's",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::life::hall_wall)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, evidence record, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): literature-class priors stay priors
* not a gate PASS and not a life verdict: absent determining evidence stays NOT_EVALUATED / INCOMPLETE_EVIDENCE / OUT_OF_DOMAIN / MODEL_ERROR (RM-R31); no 15,000 h / 26,280 h comparison is made in raw physics (SC-WP-11)
