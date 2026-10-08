# NP-HALL-PARAMETRIC-ENVELOPE addendum A8 - M2 closure of the DBF-1 design point

`prereg_addendum_a8_m2_dbf1_v1.json` is authoritative; this page restates it. Status
**PREREGISTERED_BEFORE_M2_EXECUTION**, label **ACTUAL_DESIGN_EVALUATION (DBF-1) / PARAMETRIC / NOT_VALIDATED**.
Registered 2026-10-08 on `8f7e33a` (DBF-1 committed alone), before any A8 code, any DBF-1 quantity on a design state,
any feed-stability evaluation of the DBF-1 design and any M2 execution. Hash lock:
`prereg_addendum_a8_m2_dbf1_lock_v1.json`. v1, A1..A6 and every committed record are not edited. A7 is reserved for the
A9.36 numerics lane.

## What M2 evaluates

The one frozen design (DBF-1, read only from `docs/baseline/DBF-1/dbf1_config_v1.json` through `abep_config::baseline`)
at all 196 states, AIR_PRIMARY and XE_CONTINGENCY, layer (a) and layer (b).

| path | A8 rule |
|---|---|
| P-FLOW-DBF1 (AIR) | admitted F7 steady chain (the A5 rerun path) for the DBF-1 vector in every one of the 10 admitted surface scenarios at every state; covered contexts cross-checked against the committed F7 minimum (A5.1 tolerance); no scenario chosen (unfavourable = min, favourable = max) |
| P-FEED-STABILITY-DBF1 (AIR) | contract-v8 input-only stability class (S / U / R) of the DBF-1 loop (Kp 0.3, Ti 3 s, 1 Hz, authority 3) per in-domain (state, scenario); authoritative: the governed Python reference record (`scripts/m2/dbf1_feed_stability_reference.py`, pinned in the run manifest); Rust `stability_class_events` must agree on every input (R2) or no record |
| P-ICP-DBF1 | NP-ICP v2 per mode with the DBF-1 geometry (ASSUMED_GEOMETRIC_TUBE R 0.06 m, L 0.15 m; vessel, collector, two open ends) registered as assumed / level 7; RF power, potentials, neutral source, edge factor and rate sets stay unregistered; NH-ICP as A2 |
| P-PBUS-DBF1 | A2 ledger with the ICP loads and the DBF-1 compressor draw (min over in-domain scenarios); NH-PBUS as A2; 300 W / 1,350 W / 1,500 W margins as information |
| P-THERMAL / P-MASS / P-LIFE | A2 rules at the DBF-1 topology / policy / materials; LIFE code A8_DBF1_ANODE_MATERIAL_FROZEN_P4_EVIDENCE_INCOMPLETE replaces ANODE_MATERIAL_OPEN |
| P-TD-DBF1 (AIR) | D(s, scenario) = q (C_D A)_RC-DIAMANT + F1 intake-face drag x 0.25 m^2 (admitted reference_drag, separate_term); T_required = D; NH-TD OPEN (T_available NOT_EVALUATED) |
| P-HALL | A9.36: no envelope ingested; every Hall test NOT_EVALUATED, code HALL_NUMERICS_NOT_CONVERGED (MISSING_EVIDENCE; model-numerics) |
| A4 / A5 / layer (b) | unchanged |

## DBF-1 necessary conditions (A8-NH-INTAKE-DBF1, AIR)

L-AREA-DBF1 (0.25 m^2 vs A_req), L-CAP-DBF1 and L-DEL-DBF1 (captured / delivered flow vs mdot_req,in), each at T12,
T25 and TD = D(s, scenario), per scenario. A scenario out of domain or with a U / R loop fails L-DEL. FAILS in every
scenario adds A8-NH-INTAKE-DBF1: NON_CLOSING, never eligible, DESIGN_VARIABLE_LIMIT (A9.35). Otherwise the constraint
stays OPEN (a met necessary condition establishes nothing).

## NH-FLOW for the frozen design

Out of domain in some scenario -> OPEN (A8_DBF1_GAS_PATH_OUT_OF_DOMAIN_IN_SCENARIO); else U in some scenario ->
NON_CLOSING, not eligible (FEED_LOOP_UNSTABLE_EQUILIBRIUM); else OPEN (NO_HALL_CLOSING_POINT). XE unchanged.

## Classification

C0, CA4, C1..C4 verbatim. C1 holds (no converged envelope may be ingested); its blocker reads
HALL_NUMERICS_NOT_CONVERGED. Expected: NOT_DETERMINABLE at C1. No A8 code is ever eligible for PHYSICALLY_NON_CLOSING.
Binding constraint per (state, mode): first eligible non-closure, else first NON_CLOSING, else first OPEN, with its
category; Hall and non-Hall closure reported separately.

## A later converged Hall envelope

An A7 converged RP-1 envelope is an input completion (no DCR): only DBF-1-hardware points (G-RP1, BZ-P5B16, B_peak in
the DBF-1 band, V_d in 180-350 V) enter, under the v1 / A1 / A6 test rules and the A2 joint conditions; it yields a new
run manifest and an M2 record v2. Other hardware needs a DCR.

## Record

`abep-assess-closure --harness v2 --m2-dbf1 ...` writes `docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json`
(schema `abep_assess_m2_dbf1_closure_v1`) after `m2_run_manifest_v1.json` is committed alone. Two runs, byte-identical.
