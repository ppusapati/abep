# NP-HALL-PARAMETRIC-ENVELOPE addendum A3 — numerics adequacy (RG-04)

`prereg_addendum_a3_numerics_v1.json` is authoritative; this page restates it. Status **PREREGISTERED_NOT_RUN**, label
**PARAMETRIC / NOT_VALIDATED**. Registered 2026-10-08 on `64a078e`, before any v1 grid case beyond the listed smoke runs
and before any refined run. Hash lock: `prereg_addendum_a3_numerics_lock_v1.json`. v1 is not edited.

## What it adds

A grid-adequacy check of the v1 scaled numerics (0.5 mm cells, dt 5 ns, 2 ms scaled by the domain length, average over the
second half) and the consequence of its outcome. The v1 grid, its numerics, run-status rule, raw records and
classification procedure are unchanged. No grid case is ever rerun at refined numerics as a replacement.

Scope: **XE** now. **AIR** (addendum A1) by reference, when it runs. **N2_PROXY** not covered (diagnostic only).

## Check set (17 cases per family, seed `NP-HALL-PARAMETRIC-ENVELOPE/A3/v1`)

- 16 corners: the shortest and longest domain (G-AMINDHMAX-LH8603, 266 cells; G-AMAXDHMIN-LH12, 546 cells) × B_peak
  {LO, HI} × V_d {180, 350} × mdot {LO, HI}.
- 1 centre: G-RP1 (median cell count), VD-265, MF-MID, B_peak by seed.
- B(z) shape and transport per selection by seed: sha256 of a fixed text, first 8 bytes big-endian, mod n.
- The 17 XE keys are listed in the JSON; the Rust generator recomputes them and must match. No smoke case is in the set.

## Refinements (one factor at a time against the same baseline R0)

- **R0**: the v1 case unchanged.
- **R1 grid**: 2 × cells. Under the solver's adaptive stepping (default `adaptive = true`, CFL 0.799, checked on the
  installed pinned package) this also refines the CFL-limited time step. A dt-only refinement is not run: dt only sets the
  escape-hatch step.
- **R3 duration**: 2 × duration, average from the v1 duration (same 50 % discard). num_save stays 1000.

51 runs per family, through the pinned `run_case`, vacuum mode, threads / BLAS 1.

## Criteria (per case and refinement, against R0)

| id | rule |
|---|---|
| C-STATUS | v1 run status identical (a missing refined run is NUMERICAL_FAILURE) |
| C-QUIET | quiet class (Id_rms_rel < 0.5) identical when both runs are numerically valid |
| C-T | R0 PASS: relative thrust change ≤ 2 % |
| C-ID | R0 PASS: relative I_d change ≤ 2 % (P_d = I_d V_d inherits it) |

Tolerances from the hallmap convergence draft (2 %), fixed before any refined run. δ_T, δ_I = the largest C-T / C-ID
relative change over the family's check set.

## Outcome and consequence

| outcome | condition | consequence |
|---|---|---|
| A3_ADEQUATE | every criterion passes | v1 numerics stand; label NUMERICS_A3_ADEQUATE_ON_CHECK_SET; EC-NUM stays (sampled check) |
| A3_ADEQUATE_WITH_NUMERICAL_MARGIN | no status / quiet flip, δ_T and δ_I ≤ 10 %, some C-T / C-ID fail | a Hall point test counts only if it also passes with T(1 − δ_T) and P_d(1 + δ_I); a nominal-only pass is NUMERICS_NOT_CONVERGED (unknown) |
| A3_NOT_ADEQUATE | any status / quiet flip, or δ > 10 % | every PASS and NOT_SUSTAINED point of the family is NUMERICS_NOT_CONVERGED: an unknown, never feasible, never an evaluated non-closure; Hall tests NOT_DETERMINABLE_IN_ENVELOPE (MISSING_EVIDENCE) |
| A3_NOT_RUN | no committed result | v1 rules unchanged |

A consumer that does not implement the overlay reports NOT_DETERMINABLE_IN_ENVELOPE (A3_OVERLAY_NOT_IMPLEMENTED) for a
family whose outcome is not A3_ADEQUATE. A3 never makes a point feasible that v1 does not and never changes a frozen
record.

## Execution

Rust-generated A3 case file (byte-reproducible), A3 driver (pin, locks, inputs, case file checked), Rust launch with
sidecars (3 shards), freeze before scoring, one Rust scoring pass, result committed whatever the outcome. The R0 records
are compared with the frozen grid records of the same keys as a report-only determinism diagnostic.
