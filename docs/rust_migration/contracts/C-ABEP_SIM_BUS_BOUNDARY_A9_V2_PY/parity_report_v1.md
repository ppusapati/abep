# Parity report C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY v1

Generated from `parity_report_v1.json`. Verdict: **ADMITTED** (parity PARITY_PASS).

* Contract: `docs/rust_migration/contracts/C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY/parity_prereg_v1.json` (sha256 `d3336303a8f4d62ec146706b3f85f2abaffe6c053238910af3cf4c97c1bf75f6`)
* Python reference commit `fa4fcb3bd21fec8c07a26fe264e1045d5a6bec73`; reference files unchanged at scoring: True
* Rust commit `b35420c69e3a59f79005a80d4272dc0e0e2bcaec` (tree dirty: False), rustc 1.94.1 (e408947bf 2026-03-25)
* Scoring seed 3254949622; harness `scripts/rust_migration/parity_bus_boundary_v1.py` sha256 `d762396e69705c5438755874cf577d7f9c386646146653ba057d88de19d7c18a`

## Calls

| item | value |
|---|---|
| calls_total | 1999 |
| registered_calls | 259 |
| randomized_calls | 1740 |
| python_RETURNED | 1839 |
| python_RAISED | 160 |
| calls installed_slots | 7 |
| calls ledger | 494 |
| calls p_bus_1ms_max | 61 |
| calls rf_power_planes | 216 |
| calls allocation_checks | 431 |
| calls icp_power_allocation_check | 432 |
| calls check_startup_sequence | 175 |
| calls official_ledger | 11 |
| calls bus_power | 172 |

Mismatches: 0. Largest float distance: 0 ulp over 43064 floats.

## Invariants

| id | pass | detail |
|---|---|---|
| INV-A01 | True | restriction inert on 1996 calls without ground-reference input; violations [] |
| INV-A02 | True | 1740 removed group-'c1' rows, every one the registered NOT_INSTALLED zero row; violations [] |
| INV-A03 | True | Rust outputs of two separate processes byte-identical |
| INV-A04 | True | cargo test -p abep-subsystems --test power flight_taxonomy_equals_the_boundary_record (part of the scored tree's test run, see test_run) |
| INV-A05 | True | cargo test -p abep-subsystems --test power rfp_gate_is_not_in_the_physics_crate |
| INV-A06 | True | cargo test -p abep-subsystems --test prereg_binding forbidden_identifier_scan_of_this_crate |
| INV-A07 | True | no restricted-reference E7 / E9 refusal raised inside rfp_power_gate other than the two structural input refusals named in DIV-A04; violations [] |

## Conservation

| id | pass | detail |
|---|---|---|
| CONS-A1/CONS-A2 (Rust) | True | 148 COMPLETE Rust ledgers; violations [] |
| CONS-A1/CONS-A2 (Python, recorded) | True | violations [] |
| CONS-L1 | True | SYS-01 EVALUATED (expected EVALUATED, r 0.0036738751195189534); SYS-02 MODEL_ERROR (expected MODEL_ERROR, r 0.04300144880078532); SYS-03 NOT_EVALUATED (expected NOT_EVALUATED, r None); SYS-04 NOT_EVALUATED (expected NOT_EVALUATED, r None); SYS-05 MODEL_ERROR (expected MODEL_ERROR, r None); SYS-06 INCOMPLETE_EVIDENCE (expected INCOMPLETE_EVIDENCE, r None); SYS-07 NOT_EVALUATED (expected NOT_EVALUATED, r None); SYS-08 MODEL_ERROR (expected MODEL_ERROR, r None); SYS-01b (not registered) EVALUATED (expected EVALUATED, r 0.0) |

## Domain and error parity

| class | Python RAISED calls |
|---|---|
| BoundaryA9Error | 155 |
| OverflowError | 1 |
| KeyError | 4 |

Registered divergences observed:

* DIV-A02: 3
* DIV-A03: 1
* DIV-A04: 3

## Performance (reported, not a decision criterion)

| workload | Python s | Rust s | note |
|---|---|---|---|
| PERF-A01 | 0.3884 | 0.04788 | 1000 evaluations; Rust timed inside power_eval (no process start) |
| PERF-A02 | 0.7872 | 0.02783 | 10 evaluations; Rust timed inside power_eval (no process start) |

## Findings

* CONS-L1 SYS-01 as registered (LS-01 thermal_control 0.0 W) closes with a -3.0 W mismatch on the THERMAL_CONTROL account because VS-NET deposits Q_thermal_control_W = 3.0 W; r = 0.37 % < 2 % (EVALUATED, the registered status). The contract text's 'r of order 1e-15' assumed no thermal control in VS-NET; the registered case is unchanged. SYS-01b (not registered, LS-01 with 3.0 W) closes to rounding; SYS-02's residual is 37 W (r 4.3 %, MODEL_ERROR as registered) for the same reason
* IF-ICP-BUS-v1 plane finding (contract rust_only_registered_interfaces): the NP-ICP producer's P_icp_bus_W is a supply-input sum for the bias slot and a load-plane value for the RF and match slots, while NP-THERMAL IK-07 calls it the demand at the spacecraft DC boundary; alignment is for the owner / NP-ICP lane (IF-ICP-BUS-v2 / IF-ICP-THERMAL-v2)
* INV-A07 exception set read as the two structural input refusals named in DIV-A04 (non-empty start-up sequence; 'not a bus_power_boundary_a9_v2 ledger'), the second scored with the reference text

## Ledger update requested

```json
[
 {
  "component": "C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY",
  "status": "ADMITTED",
  "parity": "PARITY_PASS",
  "scope": "whole module for the flight configuration except rfp_power_gate (abep-assess, SC-WP-11) and GROUND_REFERENCE_TEST_METADATA (GROUND_REFERENCE_ONLY): installed_slots, ledger, p_bus_1ms_max, rf_power_planes, allocation_checks, icp_power_allocation_check, check_startup_sequence (without the transient_gate field)",
  "authoritative_implementation": "rust: crates/abep-subsystems (abep_subsystems::power)",
  "python": "rfp_power_gate stays PYTHON_REFERENCE until abep-assess admits it (SC-WP-11)"
 },
 {
  "component": "C-ABEP_SIM_BUS_BOUNDARY_A9_PY",
  "status": "PARTIAL_ADMISSION",
  "scope": "the v1 functions as rebound by v2 for hall_icp_neutralizer (same code objects); the v1 boundary module itself (bus_power_boundary_a9_v1, hall_c1_reference) is immutable history and is not ported for the active line (A9.30 sec. 5)"
 },
 {
  "component": "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY",
  "status": "PARTIAL_ADMISSION",
  "scope": "official_ledger only (row stays SC-WP-10)"
 },
 {
  "component": "C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY",
  "status": "PARTIAL_ADMISSION",
  "scope": "bus_power without its gate_verdict field (row stays SC-WP-10; the gate verdict is SC-WP-11)"
 }
]
```

## What this is not

* not physics evidence or validation: parity shows the Rust code reproduces the Python reference, not that either is right
* not a change of any frozen dataset, golden, threshold or requirement
* not authority before admission: until ADMITTED the Python reference is authoritative
* not a promotion of any provisional input (RM-R27): every TBD load / efficiency of the official ledger stays TBD with its mass/power v5 text
* not a gate PASS: the official flight ledger stays PARTIAL_BOUNDARY, the bus demand NOT_EVALUATED, CONS-L1 INCOMPLETE_EVIDENCE for flight (RM-R31)
* not an RFP power-gate implementation (abep-assess, SC-WP-11)
