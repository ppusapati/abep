# NP-HALL-PARAMETRIC-ENVELOPE addendum A5 — M2 intake closure

`prereg_addendum_a5_m2_intake_closure.json` is authoritative; this page restates it. Status
**PREREGISTERED_BEFORE_M2_AND_BEFORE_EVALUATION**, label **ACTUAL_DESIGN_EVALUATION / PARAMETRIC_SENSITIVITY /
NOT_A_PERFORMANCE_PREDICTION**. Registered 2026-10-08 on `54b50d6`, before any A5 code or A5 quantity on any design
state. Hash lock: `prereg_addendum_a5_lock.json`. v1, A1, A2, A4 and every committed record are not edited.

## Why

A9.35 keeps A4-REG-01 open: no maximum intake area is invented or frozen. It carries the A4 result forward (worst-state
12 mN needs ≥ 0.251 m² effective collection area and ≥ 0.048 mg/s at the ideal 1.5 kW). M2 must evaluate the actual
intake geometry, its capture efficiency and the delivered mass flow. A failing current design is DESIGN_VARIABLE_LIMIT
unless a registered spacecraft-envelope bound proves that no permissible intake can close.

## Which design is "actual"

No registered record names a current intake design:
- AFC-UP-IN-01 (freeze candidate): a Pareto set, robust set EMPTY, nominal union {0.25} m², no member selected, OPEN;
- the F8 carried robust set is empty and its representative is REFUSED (A9.13 S6.20);
- F1 is INVESTIGATION_HYPOTHESIS, not a selection;
- H2-7 R01 (intake) is BLOCKED on DI-1.1 / DI-1.2, and config/hardware has no intake.

A5 therefore evaluates every registered design set and names none of them current:

| set | content |
|---|---|
| DS-F1-GRID | F1 grid: A ∈ {0.25 … 1.5} m² × L/d ∈ {3, 5, 10, 20} × φ ∈ {0.8, 0.9} (d collapsed, F1-02): 48 candidates × 10 surface scenarios × 196 states |
| DS-F1-ADMISSIBLE | per scenario, the grid candidates FEASIBLE_AT_STATE at every required state (F1 C-CONV, C-DRAG-RFP); a FROZEN area limit would exclude larger candidates (none registered) |
| DS-F7-PARETO | every member of the admitted F7 Pareto blocks (intake, filter, compressor, V, P_set in its context) |
| DS-F8 | the F8 robust set (EMPTY) and each F7 member's F8 status, reasons carried unchanged |

## Quantities (per design, scenario, state)

- **A_eff = A.** No spacecraft surface ahead of or beside the intake is registered, so the A4 effective collection
  area reduces to the aperture area.
- **ṁ_cap.** The F1 IF-A1 captured flow (direct TPMC, θ = 0) as the admitted F7 chain reads it, with species mass
  fractions.
- **Efficiencies:**
  - η_c = ṁ_cap / (A Σ_{O,N₂,O₂} ρ_i V);
  - η_tot = ṁ_cap / (A Φ_adm);
  - η_vs_bound = ṁ_cap / (A Φ_max).
- **A_cap,eq = ṁ_cap / Φ_max.** The ideal-collector area with the same flow, in the currency of A_req.
- **ṁ_del and x_i of each F7 member.** Taken from the admitted steady chain (intake_side + steady_sweep, one target
  P_set). The plenum / feed values are the admitted reproduction of the governed Python reference.
  - Fail closed: every state must be in domain, and the statewise minimum must equal the committed
    mdot_delivered_min_kgps bit for bit.
- **ṁ_req,in.** A4 K-MDOT-REQ at P_avail + q_max·A(d). It is the binding flow requirement and is favorable to the
  design. The A9.35 value ṁ_req(T, P_avail) (0.048 / 0.208 mg/s) is reported alongside.

## Comparisons (necessary conditions; a pass establishes nothing)

| level | test | designs |
|---|---|---|
| L-AREA | A_eff ≥ A_req(s, T) | DS-F1-ADMISSIBLE |
| L-CAP | ṁ_cap ≥ ṁ_req,in | DS-F1-ADMISSIBLE |
| L-DEL | ṁ_del ≥ ṁ_req,in | failure: every F7 member (FC00 contexts included, favorable); pass: an F8 robust member only |
| L-HALL | information: smallest-flow AIR Hall point passing the test vs best ṁ_cap / ṁ_del; v1 grid floor | never a verdict (A2 NH-FLOW stays the joint condition) |

T12 (12 mN) and T25 (25 mN) are both evaluated per state, as in the v1 / A1 Hall point tests.

## Margins

Multipliers (required / actual, ≤ 1 passes):
- k_area = A_req / A_eff;
- k_acap = A_req / A_cap,eq;
- k_cap = ṁ_req,in / ṁ_cap;
- k_del = ṁ_req,in / ṁ_del.

Per state, k_fav is the best design in the most favorable scenario and k_unfav is the best design in the least
favorable scenario. The worst state is the one with the largest k_fav. Per design, the record gives its worst state
and its number of failing states.

## Statewise

- **FAILS_IN_EVERY_SCENARIO:** no design of the set passes in any scenario (a scenario without designs fails).
- **PASSES_IN_EVERY_SCENARIO:** L-AREA / L-CAP only; information, nothing established.
- **NOT_ESTABLISHED_ROBUST_SET_EMPTY:** L-DEL, while DS-F8 is empty.
- **SCENARIO_DEPENDENT:** otherwise (DI-1.3 evidence).
- **NOT_EVALUATED:** the state's A4 AIR inputs are not evaluated.

Surface scenarios are never chosen (A9.13 S6.16). One-hardware closure per scenario (one design passing at every
required state) is reported, never a cell constraint.

## Classification effect

- A required AIR cell where some level is FAILS_IN_EVERY_SCENARIO for T12 or T25 gains **A5-NH-INTAKE**.
  - It is NON_CLOSING, never eligible either way.
  - Its codes are A5_AREA / CAPTURE / DELIVERED_BELOW_REQUIRED_T12 / _T25, all **DESIGN_VARIABLE_LIMIT**.
- A cell already PHYSICS_NON_CLOSING by an eligible constraint (A4 CA4) stays so. Otherwise it is NOT_DETERMINABLE and
  the A5 codes join its blocker list.
- **Never PHYSICALLY_NON_CLOSING.** The only route by which a registered spacecraft-envelope bound proves that no
  permissible intake can close is A4 CA4 on a FROZEN `intake_effective_collection_area_max_m2`. None is registered
  (A4-REG-01 OPEN), and A5 adds no other route.
- Pass, scenario-dependent, robust-set-empty and not-evaluated verdicts add nothing.
- C0, CA4, C1..C4 are unchanged, and so are A2 NH-FLOW and every A4 verdict. XE is NOT_APPLICABLE (stored Xe).

## Record

- Harness v2 gains A5 additively. The v2 record gains the summary block `intake_closure_a5`.
- Standalone: `abep-assess-closure --harness v2 --intake-closure --out intake_closure_a5_v1.json` (schema
  `abep_assess_intake_closure_a5_v1`).
- Dry run: a new record, `closure_run_m1_dryrun_v2.json`, labelled M1_DRY_RUN_NOT_DECISIVE. v1 stays immutable; it is
  the harness without A5.

## Not

- Not a flight mass-flow requirement (A9.13 S6.21).
- Not a selection (S6.20).
- Not an area limit (A4-REG-01 stays open).
- Not the architecture classification (the coordinator states it in M2).
