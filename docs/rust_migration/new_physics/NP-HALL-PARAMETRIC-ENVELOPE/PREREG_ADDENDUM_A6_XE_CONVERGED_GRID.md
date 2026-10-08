# NP-HALL-PARAMETRIC-ENVELOPE addendum A6 — XE grid at study-converged numerics

`prereg_addendum_a6_xe_converged_grid_v1.json` is authoritative; this page restates it. Status **PREREGISTERED_NOT_RUN**,
label **PARAMETRIC / NOT_VALIDATED**. Registered 2026-10-08 on `20e32bd`, before any A6 run, under coordinator rulings
(A9.34). Lock: `prereg_addendum_a6_xe_converged_grid_lock_v1.json`.

A6 is a new campaign. v1, the frozen v1 XE envelope, A3 and the A3 result (A3_NOT_ADEQUATE: every v1 XE PASS /
NOT_SUSTAINED point NUMERICS_NOT_CONVERGED) stay unchanged.

## Ladder

The bridge exposes cells, dt, duration and averaging start. The solver steps adaptively (CFL-limited), so the step
shrinks with the cell size; dt is the escape-hatch step and is scaled with the cells.

| level | cells | dt | duration |
|---|---|---|---|
| L0 | v1 (0.5 mm) | 5 ns | v1 |
| L1 | 2 × | 2.5 ns | v1 |
| L2 | 4 × | 1.25 ns | v1 |
| L3 (study only) | 8 × | 0.625 ns | v1 |
| LkD, k = 0, 1, 2 | as Lk | as Lk | 2 × v1, average over the second half |

## Study

- 22 cases: one seeded case per hardware configuration (14; seed `NP-HALL-PARAMETRIC-ENVELOPE/A6/v1`, none is an A3
  check case) plus the 8 A3 cases with a failing comparison (mandatory; including the three status flips and the 209 %
  thrust case).
- 154 runs (L0, L1, L2, L3, L0D, L1D, L2D), frozen before scoring, scored once.
- Comparisons G(k) = Lk vs Lk+1 and D(k) = Lk vs LkD, k = 0, 1, 2. Criteria as A3 (status, quiet class, thrust and I_d
  within 2 %), no margin tier. Pass(k) needs every case to pass G(k) and D(k).
- Observed order and a Richardson estimate are reported, never used for the rule.

## Production rule

Production level = the coarsest k in {0, 1, 2} with Pass(k), fixed before any A6 grid run. If none passes: **STOP**, no A6
grid; XE stays NUMERICS_NOT_CONVERGED (a finding).

## Grid

The 2268 v1 XE cases at the production level (only numerics change; nothing dropped or rerun), own case file, Rust launch,
frozen, ingested as a separate version. Run status as v1. Points are labelled NUMERICS_A6_STUDY_CONVERGED_L<k>; EC-NUM
stays (sampled study). The A3 overlay does not apply to A6 records.

## Functional test and classification feed

v1 XE_FUNC (T > 0) counts degenerate discharges (T ~ 1e-18 N). A6 XE tests, applied by the assessment layer only:

- HALL_XE_T12_AT_PBUS: PASS, T ≥ HC-01, P_d + P_nonHall,LB < HC-03.
- HALL_XE_T25_CAPABILITY_AT_PBUS: PASS, T ≥ HC-02, same power test.
- Both on one hardware configuration (as A1 for AIR). HC-01 / HC-02 are the only registered thrust requirements; nothing
  is invented.

Harness v2 with an A6 XE envelope uses these two tests over the A6 points as the XE_CONTINGENCY Hall constraints in place
of HALL_XE_FUNCTIONAL_AT_PBUS; statuses as v1 (closure eligible for SELECT_WITH_EVIDENCE_CONDITIONS with EC-TRANSPORT,
EC-BZ, EC-DIV, EC-NUM, EC-GEOM; non-closure never eligible under the surrogate B(z)); C0..C4 unchanged. The v1 envelope
stays reported without a classification role.
