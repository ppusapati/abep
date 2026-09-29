# Parallel RF ∥ Hall architecture investigation (v2)

**Status: architecture-investigation infrastructure, not a flight-baseline update.** The owner decision A5
(RF → Hall pre-ionization) is unchanged. A draft hypothesis record is kept at
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A8_parallel_rf_hall_investigation.json`, with status
`DRAFT_ARCHITECTURE_HYPOTHESIS_NOT_OWNER_FROZEN`; it is not an owner decision. Every v1 artifact is untouched and
still valid for the earlier architecture: `bus_power_boundary_v1`, `mass_bom_v1`, `xe_ledger_v1`, the golden
datasets, the Hall ensemble and P5-N₂ v1.

## The question v2 exists to answer

1. Can RF atmospheric propulsion cover the normal VLEO mission on its own?
2. If so, what additional mission coverage does Hall provide?
3. Is that increment worth Hall's installed mass, power, Xe and life cost?

v2 never declares a winner. It returns `FEASIBLE`, `INFEASIBLE`, `UNRESOLVED`, `OUT_OF_DOMAIN` or
`INCOMPLETE_EVIDENCE`, plus Pareto metrics. There is no `BEST_ARCHITECTURE`.

## Installed architecture vs operating mode

- **Installed architecture** (`propulsion_modes.InstalledArchitecture`) is one of `rf_only`, `hall_only` or
  `rf_hall_parallel`, and records whether a Xe system is installed. It fixes the installed dry mass:
  M = M_common + M_RF + M_Hall + M_Xe-system + M_Xe, the same in every mode.
- **Operating mode** (`propulsion_modes.Mode`) is exactly one of seven: `OFF`, `RF_ATM`, `RF_XE`, `HALL_ATM`,
  `HALL_XE`, `RF_ATM_HALL_ATM`, `RF_ATM_HALL_XE`. It sets power, flow allocation, Xe use, heat, operating hours and
  cycles.
- There are no automatic hybrid modes. Illegal combinations raise `IllegalModeError`.
- The v2 ids never reuse v1's `rf_hall`.

## Pipeline for one operating point (`parallel_system.evaluate`)

`propellant_router` → `rf_branch` (reduced model, or admitted RF map) → `hall_branch_adapter` (admitted closure,
or point evidence) → thrust vector sum → `bus_power_v2` ledger → propellant totals → heat and life bookkeeping →
status and verdict.

## Modules

| Module | Role |
|---|---|
| `parallel_contracts` | Quantity/TBD evidence primitives, FeedState, Status taxonomy, BranchResult, SystemConstraints |
| `propulsion_modes` | mode table, installed architectures |
| `propellant_router` | mass-conserving split; Knudsen regime classifier |
| `bus_power_v2` | bus_power_boundary_v2 and PROPOSED allocations |
| `rf_reduced`, `rf_branch` | reduced RF chain (never score-bearing); RF branch wrapper |
| `rf_map`, `rf_registry` | admitted RF response maps (sha-locked, append-only, owner admission) |
| `hall_branch_adapter` | Hall through the common contract; no Hall physics |
| `parallel_system` | evaluator for one operating point |
| `xe_mission_v2`, `mass_bom_v2` | Xe by cause from the mode history; installed-mass BOM |
| `mode_controller` | feasible set, reasons, Pareto; no automatic selection |
| `mission_parallel` | mission loop with mode history, battery, hours, starts; coverage |
| `golden_parallel` | software-regression vectors (not validation) |

Schemas are in `schemas/parallel_architecture/`. Baseline P0: `BASELINE_P0.json`.

## Status taxonomy (never converted)

`PASS`, `FAIL_VALIDATION`, `OUT_OF_DOMAIN`, `NUMERICAL_FAILURE`, `INCOMPLETE_EVIDENCE`, `INFEASIBLE_POWER`,
`INFEASIBLE_FLOW`, `INFEASIBLE_THERMAL`, `INFEASIBLE_MASS`, plus `NOT_SUSTAINED` (the model finds no discharge)
and `MODEL_ERROR` (the model violated a physical bound; the result is withheld).

## Verdict discipline

- A point is `FEASIBLE` only when it passes **and** every active branch is score-bearing, meaning admitted
  evidence.
- A passing point from the reduced RF model or from analog Hall evidence is `UNRESOLVED`.
- A command above the RFP power limit is `INFEASIBLE`.

## Deferred (Phase 2 and later)

- `thermal_transient_v2.py` (spec §34), the lumped transient network. `thermal_life_v1` is untouched.
- High-fidelity DSMC, electromagnetic and PIC data. Only interfaces exist today: `rf_reduced.RFCouplingRecord`,
  the `rf_registry` pattern and `propellant_router.flow_regime`.
