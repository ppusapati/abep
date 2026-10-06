# Parity report C-ABEP_SIM_MAGNET_POWER_PY v1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_MAGNET_POWER_PY/parity_prereg_v1.json` (sha256 `d89bd3fd92666e7745d0c7d3a60533eafd3c72ea36bb3c1aa6ff808c5685d25f`)
* Python reference commit `fa4fcb3bd21fec8c07a26fe264e1045d5a6bec73`; reference files unchanged at scoring: True
* Rust commit `5ccff78db74906dad94e37157cad1e0261edf99d` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 2805729329; harness `scripts/rust_migration/parity_magnet_power_v1.py` sha256 `81b7bb935d0afcc384103e88355f4ce4dc177821405b3283f2372b019debcea9`

## Calls

| item | value |
|---|---|
| calls_total | 1469 |
| registered_calls | 99 |
| randomized_calls | 1370 |
| python_RETURNED | 1031 |
| python_RAISED | 438 |
| calls magnet.ampere_turns | 212 |
| calls magnet.awg_diameter_m | 92 |
| calls magnet.coil_design | 209 |
| calls magnet.coil_power_continuous_W | 159 |
| calls magnet.constants | 1 |
| calls magnet.electromagnet | 205 |
| calls magnet.material | 14 |
| calls magnet.permanent_magnet | 209 |
| calls magnet.remanence_at_T | 107 |
| calls magnet.resistance_factor | 128 |
| calls magnet.segment | 7 |
| calls magnet.wire_resistance_ohm | 126 |

Mismatches: 0. Largest float distance: 0 ulp over 6750 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| determinism | True | Rust outputs of two separate processes byte-identical |
| INV-B02 | True | electromagnet / permanent_magnet records model-derived, magnet_power_v1 (both); violations [] |
| INV-B03 | True | permanent_magnet P_load_W exactly 0.0 (both); violations [] |
| INV-B04 | True | ANNEALED_COPPER_IACS equals the module object (both); violations [] |

## Conservation

| id | pass | detail |
|---|---|---|
| CONS-B1 (Rust) | True | 275 coils: |P - I V| <= 1e-12 P; violations [] |
| CONS-B2 (Rust) | True | N I = NI of the circuit; violations [] |
| CONS-B3 (Rust) | True | 340 circuits: NI = mmf_gap + mmf_core, mmf_core = sum of segments, phi_core = k phi_gap; violations [] |
| CONS-B1 (Python, recorded) | True | 275 coils: |P - I V| <= 1e-12 P; violations [] |
| CONS-B2 (Python, recorded) | True | N I = NI of the circuit; violations [] |
| CONS-B3 (Python, recorded) | True | 340 circuits: NI = mmf_gap + mmf_core, mmf_core = sum of segments, phi_core = k phi_gap; violations [] |

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| ValueError | 437 |
| AttributeError | 1 |

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-B01 | 0.8617 | 0.02888 | 10000 evaluations; Rust timed inside power_eval (no process start) |

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_MAGNET_POWER_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "named function subset (RM-R17): every function and constant of abep_sim/magnet_power.py except ecr_resonance_field_T (not ported: historical ECR family)",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power::magnet)",
  "python": "ecr_resonance_field_T stays in the module as history (inventory not_ported_parts); the module retires from active execution with this admission"
 }
]
```

## What this is not

* not physics validation: parity shows the Rust code reproduces the Python reference
* not an H-1 coil design: every geometry, fill factor and temperature is a caller input
* not a promotion of any provisional input (RM-R27)
* not a gate PASS (RM-R31)
