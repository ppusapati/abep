# Conservation bounds v1 (NP-HALL-PARAMETRIC-ENVELOPE addendum A4)

`conservation_bounds_v1.json` (schema `abep_assess_conservation_bounds_v1`) is authoritative; this page summarises it.
Label **CONSERVATION_BOUND / FAVORABLE_UPPER_BOUND / NOT_A_PERFORMANCE_PREDICTION**.

- Produced by `abep-assess-closure --harness v2 --conservation-bounds`, run label A4_CONSERVATION_BOUNDS_V1, Rust
  commit `63e9f20`.
- Governed by A4 (`prereg_addendum_a4_conservation_bounds.json` `7cd43c80…`, lock `5a03333e…`, registered in `419393f`
  before any evaluation).
- 196 / 196 required design states EVALUATED. The test `committed_record_is_the_a4_record_of_today` regenerates the
  record byte for byte.

## Result

- **AIR_PRIMARY: NOT_EVALUATED (A4_AREA_LIMIT_NOT_REGISTERED).** No effective-collection-area limit is registered, so
  B-FLOW and the AIR B-THRUST verdicts cannot be decided, in either direction.
  - The harness reads `intake_effective_collection_area_max_m2` in the engineering constraints.
  - Nothing else is a limit or derives one: RFP-P18-05 leaves the intake specification to the bidder, H2-7 HI-05 records
    that no launcher or spacecraft envelope is defined, F1-P-16 is a design grid, OQ-F78-04 is open, and HC-09 bounds a
    drag, not an area.
- **XE_CONTINGENCY: NOT_EVALUATED (XE_FEED_FLOW_NOT_REGISTERED).** XE_FUNC (T > 0) cannot fail a conservation bound,
  so A4 has no XE non-closure route.
- **B-DRAG: not applicable to the RFP thrust requirement.** RFP-P18-06, as registered in RVM-02 / RVM-03, is gross
  thrust (HC-01 / HC-02). B-DRAG bears only on HC-08 (T − D, A9.13 S6.15), which needs the host drag ICD. It is
  information only.
- **Classification: unchanged** (NOT_DETERMINABLE, C1). CA4 did not fire, and A4 added no blocker.

## Key numbers (required states; P_avail = 1500 W, since P_nonHall,LB,eligible = 0 W in both modes)

| quantity | min | max |
|---|---|---|
| Φ_adm = ρV (admitted), kg m⁻² s⁻¹ | 1.857e-7 | 8.593e-6 |
| Φ_max (favorable one-sided flux = ṁ_cap,max per m²), kg m⁻² s⁻¹ | 1.895e-7 | 9.239e-6 |
| Φ_max / Φ_adm | 1.017 | 1.092 |
| U_max (orbit band + co-rotation + wind), m/s | 7911 | 8492 |
| q_max (energy inflow bound), W m⁻² | 46.8 | 2329 |
| ṁ_req(12 mN), kg/s | 4.796e-8 (0.048 mg/s) | same |
| ṁ_req(25 mN), kg/s | 2.082e-7 (0.208 mg/s) | same |
| **A_req(12 mN), m²** | 0.00515 | **0.2511** |
| **A_req(25 mN), m²** | **0.0218** | 1.0634 |
| A_req,0 (electric power only) 12 / 25 mN, m² | 0.00519 / 0.0225 | 0.2530 / 1.0988 |

The worst state for both requirements is `ds2:ECSS_LT_LOW:alt230:lat-84.0000:lst0:lon60:doy184` (Φ_max 1.895e-7,
U_max 7929 m/s). It also has the smallest Φ_adm. The densest state is `ds2:ECSS_ST_HIGH:alt180:lat-73.0000:lst15:lon240:doy1`.

Distribution over the 196 states:
- A_req(12 mN) > 0.05 / 0.1 / 0.25 m² at 34 / 12 / 1 states;
- A_req(25 mN) > 0.25 / 0.5 / 1.0 m² at 26 / 9 / 3 states.

## What would decide AIR non-closure (registration item A4-REG-01)

Register A_eff,max as the engineering constraint `intake_effective_collection_area_max_m2` (m², FROZEN, with its
requirement or owner basis), for example the spacecraft frontal envelope or the launcher envelope DRDO fixes at PDR
(RFP-P19-04). The harness then decides without a code change:
- A_eff,max < **0.2511 m²** means the 12 mN sustained requirement fails at the worst state for any design and any
  chemistry. That is PHYSICALLY_NON_CLOSING via CA4.
- A_eff,max < **0.0218 m²** means the 25 mN capability fails at every state.
- A_eff,max ≥ 0.2511 m²: the bounds hold and establish nothing.

These thresholds already assume η_cap = 1, a lossless thruster (all 1500 W into the jet), a favorable relative speed
and the energy inflow bound. Any real intake or thruster efficiency raises the required area.

## Information (never eligible)

- **I-2: T_max at the F1 design-grid areas**, as the minimum over states. 0.25 m² gives 11.97 mN, which is below
  12 mN at the worst state. 0.5 m² gives 17.0 mN, 1.0 m² gives 24.2 mN and 1.5 m² gives 29.9 mN.
- **I-3: B-THRUST on the F7 delivered-flow frontier** (DESIGN_GRID_INFORMATION_NEVER_ELIGIBLE). The statewise-minimum
  delivered flow, 1.296e-8 kg/s, gives T_max = 6.24 mN. Even the captured flow, 3.084e-8 kg/s, gives only 9.62 mN.
  Both are below 12 mN at 1500 W with a lossless thruster, so no Hall result can make the current F7 frontier member
  sustain 12 mN. Because the F7 grid is not shown bounding (A2), this is not eligible.
- **I-4: the HC-09 bulk-momentum cap** ṁ_cap ≤ 25 mN / U_min is 3.26e-6 to 3.53e-6 kg/s. That is far above ṁ_req, so
  it does not bind.
- **I-5: B-DRAG.** max(T_max − ṁ U_min) ≥ 97.8 mN and ṁ_TD,max ≥ 5.1e-5 kg/s. Captured-momentum drag alone cannot
  make HC-08 fail at the RFP thrust levels.
- **I-6: Xe.** ṁ_req is 0.048 mg/s at 12 mN and 0.208 mg/s at 25 mN at 1500 W. No Xe flow is registered.

## Not

- Not a performance prediction.
- Not a closure.
- Not the architecture classification (the coordinator states it in M2).
- Not a relabelling of any admitted or scored result: F7, the F8 robust set (EMPTY), plenum / feed v8 and the A1
  BOUNDED results are unchanged.
