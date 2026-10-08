# NP-HALL-PARAMETRIC-ENVELOPE addendum A2 — M1 closure-harness physics paths

`prereg_addendum_a2_m1_closure_paths.json` is authoritative; this page restates it. Status **PREREGISTERED_BEFORE_M2**,
label **PARAMETRIC / NOT_VALIDATED**. Registered 2026-10-08 on `64a078e`, before any M2 execution. Hash lock:
`prereg_addendum_a2_lock.json`. v1 and its files are unchanged. A1 (AIR family, lane-hall-chem-air) is consumed by its own
rules; A3 is reserved for the Hall-run numerics check.

## What changes

- Harness v2 (record schema `abep_assess_hall_parametric_closure_v2`). The v1 non-Hall inputs are now produced by
  evaluated physics paths, per (state, mode). v1 refused an evaluated non-Hall input; v2 evaluates it under the rules below.
- v1 `non_hall_at_closing_points` becomes operational: a non-Hall input that is evaluable is checked at each Hall closing
  point (joint point conditions).
- P_nonHall,LB of the v1 point tests becomes the per-(state, mode) lower bound of the assembled layer (a) ledger. It has
  the same definition family (TBD load → 0 W, TBD efficiency → 1) and is 0 W today, as in v1.
- An M1 readiness listing names every required path.

## What does not change

- The v1 grid, run status, favorable envelope, point-test thresholds, B(z) asymmetry, numerics and transport set.
- The A1 AIR rules.
- C0..C4 and the A9.32 rules.
- Layer (b), the credible set (EMPTY), the pin, and every admitted or scored record. That includes F7, F8 (robust set
  EMPTY) and plenum / feed v8 (PARITY_FAIL).

## Paths

| path | producer | closes (eligible) | non-closure eligible | today |
|---|---|---|---|---|
| P-ENV | mission run hook (abep_atmos) | n/a | n/a | EVALUATED, 196 states |
| P-HALL-XE | v1 envelope ingestion | v1 rules | v1 rules | HALL_ENVELOPE_NOT_RUN |
| P-HALL-AIR | A1 AIR family (A1 ingestion) | A1 rules | never (A1) | AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED |
| P-FLOW (NH-FLOW) | F7 / F8 admitted chain | a robust member with a stable feed loop delivers ≥ the closing point's mdot | never (DESIGN_VARIABLE_LIMIT) | GAS_PATH_ROBUST_SET_EMPTY (AIR); XE_FEED_FLOW_NOT_REGISTERED (XE) |
| P-FEED-STABILITY | contract-v8 typed status | part of P-FLOW | UNSTABLE_EQUILIBRIUM is a finding | not evaluated (no robust hardware, no controller) |
| P-ICP (NH-ICP) | NP-ICP v2 (IMPLEMENTED_UNVERIFIED) | I_e,cap,fav ≥ I_d at a closing point | never | ICP_CAPACITY_NOT_EVALUATED |
| P-CPL | CPL-HALL-ON-v1 at envelope points; M_n; HC-05 | never closes | never | NOT_EVALUATED |
| P-PBUS (NH-PBUS) | layer (a) ledger, bus_power_boundary_a9_v2 | complete ledger < HC-03 | admitted / verified loads alone ≥ HC-03 | BUS_LEDGER_NOT_COMPLETE (TBD list) |
| P-THERMAL (NH-THERMAL) | thermal 2.0.0 | CONVERGED, margin ≥ HC-06 | never | THERMAL_LOADS_NOT_EVALUATED |
| P-MASS (NH-MASS) | mass v5 objective | evaluated CBE < HC-04 | evaluated CBE lower bound ≥ HC-04 | MASS_INCOMPLETE_EVIDENCE |
| P-LIFE (NH-LIFE) | life kernels | evaluated life ≥ HC-07 | never | LIFE_NOT_EVALUATED |
| P-TD (NH-TD, AIR) | mission drag_body_N | needs the host drag ICD | never | HOST_SPACECRAFT_DRAG_ICD_ABSENT |
| P-LAYER-B | admitted components only | v1 | v1 | NOT_EVALUATED |

Gas path, one hardware across all states:
- A flight upstream hardware is one F7 design vector. Its statewise quantifier is the minimum delivered flow over the
  states.
- The admissible hardware is the F8 robust set, carried unchanged (A9.13 S6.16: no favourable surface scenario is
  chosen).
- Robust set EMPTY means NH-FLOW is OPEN at every AIR state, with the F8 decomposition reported as a binding finding.
- Plenum / feed values come from the governed Python reference capture inside the admitted F7 outputs. A later per-state
  evaluation uses the Python reference, or Rust cross-checked against it on every input (R2).

T − D: HC-08 needs the host-spacecraft drag ICD. The 12 mN and 25 mN thrust requirements are evaluable on their own by
the Hall point tests, and the record says so separately.

## Joint point conditions and classification

- A state and mode is PHYSICS_FEASIBLE only if every required constraint closes eligibly and one hardware has, for every
  Hall test, a point that also meets every point-evaluated non-Hall input (ICP, flow).
- If every constraint closes but no such point exists, the result is JOINT_CLOSING_POINT_ABSENT. A point-evaluated input
  with no Hall closing point to evaluate at is OPEN (NO_HALL_CLOSING_POINT).
- C0..C4 are applied verbatim. C3 adds the evidence conditions EC-FLOW, EC-ICP, EC-PBUS, EC-THERMAL, EC-MASS, EC-LIFE
  and EC-TD.

## Readiness

| status | meaning |
|---|---|
| CONSUMED | the harness reads the producer today |
| AWAITING_INPUT | the consumer is implemented and synthetically tested; the input does not exist yet |
| BLOCKED | the harness cannot consume the path |

M1 exit item: no required path is BLOCKED. Command: `abep-assess-closure --readiness`.

## Today expected

C1: NOT_DETERMINABLE. HALL_ENVELOPE_NOT_RUN comes first, then the AIR chemistry blocker, GAS_PATH_ROBUST_SET_EMPTY and
the open non-Hall codes.
