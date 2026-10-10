# DCR-001 evaluation method (preregistration v1)

`dcr001_eval_prereg_v1.json` is authoritative; this page restates it. Status **PREREGISTERED_BEFORE_EVALUATION**,
label ACTUAL_DESIGN_EVALUATION / PARAMETRIC / NOT_VALIDATED. Hash lock: `dcr001_eval_prereg_lock_v1.json`, committed
alone before any replacement design is compared. DCR: DCR-DBF1-001 (`docs/baseline/DBF-1/dcr_register_v2.json`).

## Concept retained

Atmospheric intake -> filter -> active compressor (turbo rows / Gaede drag stages of the admitted DragCompressor
family) -> plenum -> pressure-regulated feed -> H-1. Only implementation parameters of registered models vary.

## Design space DS-DCR001

| variable | values |
|---|---|
| intake area | 0.20-0.60 m^2 in 0.01 steps, plus 0.75, 1.0, 1.25, 1.5 (45) |
| L/d, phi | {3, 5, 10, 20} x {0.8, 0.9} (F1 nodes, never interpolated; d collapsed) |
| filter | F4-FIL-T0.9 / T0.7 / T0.5 / PLACEHOLDER (FC00 none excluded) |
| compressor | every F3 grid design without the inlet-independent gate codes R1 / R2 / R3 |
| plenum V | 0.001, 0.01, 0.1 m^3 (WALL-G0) |
| P_set | 0.002 ... 0.1 Pa (six values; model domain <= 0.1 Pa) |
| controller | Kp {0.3, 3} x Ti {0.3, 3} s, 1 Hz, authority 3 |

Every criterion is evaluated at all 196 required states x all 10 admitted surface scenarios.

## Criteria

- **C-FLOW-T12**: delivered flow >= A4 K-MDOT-REQ(12 mN, P_avail + q_max A) at every state and scenario.
- **C-FLOW-T25**: in every scenario at least one state reaches the 25 mN necessary flow (A4 existence).
- **C-DOMAIN**: no dead-head, Gaede K in [1, K0], pressures <= 0.1 Pa, feed Kn, thermal, bisection; dead-head margin > 0.
- **C-STAB**: feed-loop class S everywhere (Rust screen; governed Python reference + Rust agreement on the selection).
- **C-DRAG**: intake-face drag <= 25 mN (HC-09).
- **C-POWER**: compressor electrical power <= 250 W (300 W common allocation minus the 50 W controls / thermal allowance).
- **C-MASS**: compressor model mass <= 5.5 kg (AL-02).

Compressor coefficients: code defaults frozen as engineering assumptions (assumed, level 7) with bands; cited relations
bound or cross-check kS, kK, xi and eta. Robustness: 8 unfavourable corners; closure only at nominal is
CONDITIONAL_ON_COMPRESSOR_COEFFICIENTS.

## Selection and non-closure

Admissible designs: robust first, then the robust worst-state flow ratio (0.05 bins), compressor mass, intake wall
area, higher P_set, drag, power, V, controller order, id. If none is admissible: the best design minimises failed
non-flow criteria, then maximises the worst-state flow ratio; its residual shortfall per criterion is reported and the
result is DESIGN_VARIABLE_LIMIT within DS-DCR001. FUNDAMENTAL NON-CLOSURE needs a registered bound; A4-REG-01 stays
open, so this evaluation cannot conclude it.

## Resolution

DBF-1.1 (new files, new lock). DCR status APPROVED_BY_COORDINATOR_PENDING_OWNER_NOTE only for an admissible selection,
else CLOSED_WITH_RESIDUAL_DEFICIENCY. P1 closure state by the registered mapping.
