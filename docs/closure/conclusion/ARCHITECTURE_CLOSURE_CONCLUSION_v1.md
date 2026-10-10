# ABEP hall_icp_neutralizer — Architecture Closure Conclusion v1

Date 2026-10-09 · basis: integration line incl. DBF-1 / DBF-1.1, A4 conservation bounds, M2 v1, P3/P6/P7/P8/P9 closure records,
Hall numerics diagnosis (A9.36) · owner instruction 2026-10-09: wind down process lanes and conclude.
Architecture is owner-frozen (A9.38); this record concludes physics feasibility, it does not reopen the trade.

## 1. Verdict

**The selected architecture is physically closable, but AIR mode cannot cover the full RFP state set with any fixed-geometry
intake. It closes only inside a free-stream flux window, so AIR-mode closure requires an operating-altitude schedule
(altitude raised / lowered with solar activity inside 180–230 km) with Xe covering states outside the window.**

This follows from conservation laws and the registered V_d band alone — independent of chemistry, compressor design and
Hall transport (`docs/closure/conclusion/fixed_intake_window_v1.py`, output `fixed_intake_window_v1.json`):

| quantity | value | basis |
|---|---|---|
| admitted free-stream flux span over the 196 states | 1.86e-07 – 8.59e-06 kg m⁻² s⁻¹ (**×46.3**) | A4 record (sha `5146fe58…`) |
| max exhaust velocity, O⁺ through full V_d,max 350 V | 65.0 km/s | DBF1-H1-05; lightest registered heavy ion, singly charged |
| minimum delivered flow for 12 mN / 25 mN | 0.185 / 0.385 mg/s | T ≤ ṁ·v_ex,max (100 % utilisation) |
| effective intake area needed at the thinnest state for 12 mN | **≥ 0.99 m²** (η_capture = 1) | ṁ / Φ_min |
| capture drag of that same area at the densest state | **≥ 67 mN** (> 25 mN) | D ≥ ṁ_capture·U |
| largest flux span one fixed area can serve (12 mN sustained, capture drag ≤ 25 mN) | **×17.4** (ideal); ≈ ×7–9 with realistic utilisation (estimate) | 25 mN / (U·ṁ_req) |

The state set spans ×46 but a single intake can serve at most ×17 even under ideal assumptions, and every favourable
assumption above (η_capture = 1, all flow ionised to O⁺ at 350 V, no body drag) makes the real window narrower.

## 2. Hall thruster (RP-1, H1 geometry)

The HallThruster.jl non-convergence is resolved in cause: the solver converges on its vendor SPT-100 case; the H1 failures came
from the averaged-state thrust observable on oscillating discharges, a short averaging window, first-order spatial accuracy, and
discharge collapse at high B with low flow (`HALL_NUMERICS_DIAGNOSIS.md`). With the corrected time-mean observable, the partial
RP-1 Xe demonstration (A7, **not scored**, PARAMETRIC / NOT_VALIDATED, credible transport set still empty;
`runs/a7_demo_rp1_partial/`) gives production-vs-check agreement of ~1–3 % on quiet cases and:

| Xe flow | thrust | discharge power | T/P |
|---|---|---|---|
| 0.38 mg/s | 6.4 mN | 156 W | 41 mN/kW |
| 1.29 mg/s | 9.6 – 23.8 mN | 280 – 460 W | 28 – 62 mN/kW |
| 3.2 mg/s | 23 – 48 mN | 440 – 1,040 W | 38 – 76 mN/kW |

19 of 22 runs sustained; the failures are high-B / low-flow discharge collapses. **XE contingency closes 12 mN and
25 mN within the ~911 W discharge ceiling (P6)** on this parametric evidence. AIR Hall performance is not simulated
(O/O₂ chemistry only bounded); it does not change the §1 verdict, which needs no chemistry.

## 3. Item status

| item | state | conclusion |
|---|---|---|
| Architecture | FROZEN (A9.38) | viable; AIR closure needs a density-window operating concept (§1) |
| P1 intake / compressor | DCR REQUIRED | intake sized to the thin end of the chosen window (~1 m² class effective); compressor must deliver ≈ all captured flow (today 3–30 %); compressor mass 10.9 vs 5.5 kg |
| P2 Hall RP-1 | FROZEN FOR EM | cause found; Xe closes on parametric evidence; AIR efficiency is a test item |
| P3 H1 B(z) | FROZEN FOR EM | FE-derived field, DBF-1.1 |
| P4 RF/ICP | BLOCKED (rate sets, RF coupling) | energy allows it; RF coupling efficiency must be measured (bench) |
| P5 mass | DCR REQUIRED | rebuild after the intake / compressor redesign |
| P6 power | CLOSED except Hall operating point | discharge ceiling ≈ 911 W under 1,500 W |
| P7 thermal | DCR REQUIRED (RF match location) | all other nodes pass; anode 512 °C |
| P8 materials | FROZEN FOR EM | no gate fails; EM / coupon tests |
| P9 host drag | REFERENCE/ICD DEPENDENT | allowable host C_D·A envelope registered (IR-HOST-DRAG-01) |

## 4. Decisions needed from the owner

1. **Operating concept:** accept AIR-mode operation inside a free-stream flux window (altitude scheduled with solar activity),
   with Xe for states outside it — or confirm that the RFP requires AIR operation at every 180–230 km / solar-activity
   condition, in which case AIR-mode full-envelope closure is physically excluded for a fixed intake (a variable-geometry
   intake would then be the only route inside the frozen concept).
2. **Intake size and drag ICD:** an intake of ~1 m² class effective area sized to the window's thin end, and the matching
   host-drag allowance.
3. **Air Hall efficiency:** accept literature / EM-test evidence for air-mode Hall efficiency in place of further simulation.
