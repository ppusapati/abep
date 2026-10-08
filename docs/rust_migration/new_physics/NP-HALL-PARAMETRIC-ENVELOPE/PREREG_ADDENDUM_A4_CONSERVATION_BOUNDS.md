# NP-HALL-PARAMETRIC-ENVELOPE addendum A4 — conservation bounds

`prereg_addendum_a4_conservation_bounds.json` is authoritative; this page restates it. Status
**PREREGISTERED_BEFORE_EVALUATION**, label **CONSERVATION_BOUND / FAVORABLE_UPPER_BOUND / NOT_A_PERFORMANCE_PREDICTION**.
Registered 2026-10-08 on `ae51650`, before any A4 quantity was computed on any design state. Hash lock:
`prereg_addendum_a4_lock.json`. v1, A1, A2 and every committed record are not edited.

## Why

The M1 dry run leaves AIR_PRIMARY NOT_DETERMINABLE in both directions:
- the F7 / F8 gas-path non-closure is not eligible (design grid not shown bounding, compressor coefficients
  PARAMETRIC_SENSITIVITY; A2 P-FLOW);
- the AIR Hall chemistry is only BOUNDED (A1).

A4 registers bounds that hold for any design and any chemistry. If such a bound fails, it can decide non-closure.

## Rules

- Only conservation of mass, momentum and energy plus registered inputs. No chemistry, no transport, no design grid,
  and every efficiency at its favorable value 1.
- A bound that passes establishes nothing.
- Physics / assessment separation: the kernels (`abep_mission::conservation_bounds`) compute raw quantities and read no
  threshold. HC-01, HC-02 and HC-03 are read through abep-config and compared in abep-assess.
- Fail closed: a missing input gives NOT_EVALUATED, never a pass.

## Kernels

| id | quantity | form |
|---|---|---|
| K-U | U_max(s), U_min(s) | vis-viva at the state's WGS84 geocentric radius, apoapsis up to the band top (h_max from RVM-01), J2 allowance 3 J2 (a/r)², never below the admitted V; plus co-rotation Ω_E (N + h) cos φ in magnitude (inclination TBD); plus the HWM14 v2 horizontal wind and its interpolation error |
| K-PHI | Φ_max(s) | Σ_i ρ_i U_max [1 + e^(−S_i²) / (2√π S_i)], species O, N2, O2 and the unspeciated remainder carried as atomic H |
| K-Q | q_max(s) | drifting-Maxwellian translational energy flux (erf → 1), internal ≤ 2 k_B T / m per particle, plus Φ_max ε_x,max (ε_x,max = D0(H2) / 2 m_H = 2.22 eV/u) |
| K-TMAX | T_max(ṁ, P) | √(2 ṁ P) + P / c (Cauchy–Schwarz on the far-field exhaust; radiation momentum ≤ P / c) |
| K-MDOT-REQ | ṁ_req(T, P) | (T − P/c)² / (2P) |
| K-AREQ | A_req(s, T, P0) | smallest A with T_max(Φ_max A, P0 + q_max A) ≥ T; closed-form positive root |
| K-DCAP | D_cap | ṁ_cap U (bulk) |

The free-stream speed bound is conditional on the admitted environment (ENVIRONMENT_AS_ADMITTED). The vertical wind is
not registered; it enters |v_rel| only in quadrature.

## Bounds

- **B-FLOW.** ṁ_jet ≤ ṁ_del ≤ ṁ_cap ≤ Φ_max(s) · A_eff,max · 1.
  - In AIR_PRIMARY the exhaust carries only delivered atmosphere (RVM-02, RVM-28 / RVM-29, A9.19; ICP feed G-REUSE).
  - A_eff is the effective collection area: the normal-projected area of every surface whose incident flux can reach
    the intake, weighted by its incident flux relative to normal incidence. A registered limit must bound it in that
    sense.
- **B-THRUST.** T ≤ T_max(Φ_max A_eff,max, P_avail + q_max A_eff,max), with P_avail = HC-03 − P_nonHall,LB,eligible
  (A2 ledger, ADMITTED / VERIFIED loads only).
  - Reported per state: ṁ_req and A_req for 12 mN and 25 mN, with A_req,0 = ṁ_req / Φ_max.
- **B-DRAG.** D_spacecraft ≥ ṁ_cap U_min.
  - The requirement form comes from the registered text. RFP-P18-06 prints "12 mN to 25 mN (From expected drag to
    compensate)". The frozen snapshot carries it as RVM-02 / RVM-03 thrust thresholds (HC-01 / HC-02, gross thrust).
  - The net form T − D ≥ 0 is the separate owner constraint A9.13 S6.15 (HC-08), which needs the host drag ICD.
  - B-DRAG therefore applies to HC-08 only. It is information only, never eligible: the captured subset's mean axial
    speed has no registered lower bound, and HC-08 stays OPEN.

## Inputs today

- **A_eff,max is not registered.** The harness reads the engineering constraint `intake_effective_collection_area_max_m2`;
  it does not exist. Nothing else in the repository is a limit or derives one:
  - RFP-P18-05 leaves the intake specification to the bidder;
  - H2-7 HI-05 records that no launcher or spacecraft envelope is defined;
  - F1-P-16 (0.25–1.5 m²) is an assumed design grid;
  - OQ-F78-04 (spacecraft frontal geometry) is open;
  - HC-09 bounds a drag, not an area.
- **Xe:** no flow or storage limit is registered (XV2-17 / XV2-18, OQ-HPE-03).

## Modes

- **AIR_PRIMARY:** B-FLOW, B-THRUST and B-DRAG (information).
- **XE_CONTINGENCY:** B-THRUST only. It is NOT_EVALUATED without a registered Xe limit, and ṁ_req is reported. XE_FUNC
  (T > 0) cannot fail a conservation bound, so A4 has no XE non-closure route.

## Statewise

The admitted quantifier `abep_mission::statewise::statewise_quantifier` is used, with margin = A_eff,max − A_req(s).
- **T12 (sustained):** the bound fails at every failing required state.
- **T25 (capability):** A4 uses existence. The bound fails only if no required state passes. The v1 / A1 per-state
  T25 Hall test is unchanged.

## Classification effect

- **Eligible non-closure:** at a required AIR state, iff A_eff,max is FROZEN, every input is EVALUATED and the
  statewise rule fails (T_max(s) < T_req).
  - Code A4_CONSERVATION_BOUND_NON_CLOSING (FUNDAMENTAL_ARCHITECTURE_LIMIT); constraint A4-B-FLOW-THRUST.
- **Supersession (A4 bound only):**
  - A1's "AIR non-closure never eligible";
  - A2's P-HALL-AIR and P-FLOW (AIR) "never eligible".

  Their reasons (surrogate B(z), composition corners, nominal chemistry, non-bounding design grid, uncited compressor
  coefficients) do not apply to a bound that uses none of them. Every other A1 / A2 rule stays in force.
- **Procedure:** C0, then **CA4** (an eligible A4 non-closure at a required AIR state → PHYSICALLY_NON_CLOSING), then
  C1..C4 unchanged. CA4 precedes C1 because the bound needs no Hall envelope.
- **Pass or NOT_EVALUATED:** nothing changes. No blocker, no evidence condition, no SELECT.
- **Expected today:** NOT_EVALUATED (A4_AREA_LIMIT_NOT_REGISTERED), no CA4, the classification stays C1. The deliverable
  is A_req(s) for 12 / 25 mN and the registration item A_eff,max.

## Information (never eligible)

- I-1: Φ_adm = ρV and Φ_max / Φ_adm.
- I-2: T_max at the F1 design-grid areas.
- I-3: B-THRUST on the F7 frontier's delivered and captured flows.
- I-4: the HC-09 bulk-momentum flow cap.
- I-5: B-DRAG ṁ_TD,max and (T_max − D_cap)_max.
- I-6: Xe ṁ_req.

## Record

- Harness v2 gains the A4 evaluation additively, and the v2 record gains a summary block `conservation_bounds_a4`.
- The standalone record is `abep-assess-closure --harness v2 --conservation-bounds --out conservation_bounds_v1.json`
  (schema `abep_assess_conservation_bounds_v1`). It is deterministic and has units, provenance and status on every
  field.
