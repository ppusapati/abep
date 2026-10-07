# NP-THERMAL-CATHODELESS 2.0.0 — verification report v2

Human-readable companion of `verification_report_model_v2_v2.json`; the JSON governs. Report v1 stays immutable.

| item | value |
|---|---|
| verdict | **VERIFIED** (`admission_rule_v2` met) |
| admission | NOT_ADMITTED_YET: ADM-04 steps outstanding (ledger flip, a named CI step bound to the v2 prereg sha256, this HISTORY entry) |
| validation status | **NOT_VALIDATED** |
| commits | `a18ceb5`, `2f4b7fc`, `6a4f961`, `7d4bddb` |
| tests | workspace 507 passed, 0 failed, 2 ignored (PT-01 / PT-02) |

**Correction to v1:** v1 withheld VERIFIED "pending the producer's verification". `admission_rule_v2` reads: VERIFIED needs AL-01..AL-11 (AL-10 v2), every CONS criterion incl. CONS-I3, FT-01..FT-23, DET, IV-01 / IV-02 and the producer key-table hash. It has no producer-status condition.

## Criteria

| criterion | 2.0.0 result | where |
|---|---|---|
| AL-01..AL-04, AL-07..AL-09, AL-11, AL-05, AL-06 | met through `run_case_v2` | `tests/thermal_v2_inherited.rs` (the v1 case builders under the 2.0.0 switch) |
| AL-10 v2 | met | `tests/thermal_v2.rs` |
| CONS-S1/S2, CONS-T1..T3 | met in every converged 2.0.0 run | solver gates |
| CONS-I1 (IFH-3/4, IFI2-03..08), CONS-I2, CONS-I3 | met | `tests/thermal_v2.rs`, smoke case |
| CONS-L1 | met (deferred in v1; now evaluated by the system ledger) | LC-18; `crates/abep-mission/tests/coupling_smoke_v2.rs` (mismatch 0.0 W, relative residual 1.4e-16) |
| FT-01..FT-12, FT-14..FT-18 | met through `run_case_v2` | `tests/thermal_v2_inherited.rs` |
| FT-13, FT-19..FT-23 | met | `tests/thermal_v2.rs` |
| DET-01..DET-03 | met in 2.0.0 (DET-03 with the v2 provenance) | `tests/thermal_v2_inherited.rs` |
| IV-01 | met (non-authoritative scratch) | see below |
| IV-02 | met through `run_case_v2` | `tests/thermal_v2_inherited.rs` |
| IV-03 | not performed (allowed) | no lawful copy of the text |
| producer key-table hash | met | `GovernedContextV2`, adapter, consumer |

**Inherited VS-NET cases in 2.0.0:**
- the registered AL-10 v2 record replaces the retired IF-ICP-THERMAL-v1 record (`inherited_to_v2`), carrying the v1 record's case fields and evidence class;
- withheld keys keep their status (and any value they carry), and NON_FIRING registers zeros;
- the node declarations and PART.f_up come from the registered transformation.

The registered inputs themselves are unchanged.

## IV-01 (Python scratch, never a CI dependency; scripts outside the repository as in v1)

- **Analytic cases:** the v1 IV-01 numbers carry over unchanged, because the IV-01 dump is identical under 1.0.0 and 2.0.0 (asserted by a test).
- **VS-NET 2.0.0 node sources:** rebuilt independently from the registered records and the prereg v2 deposition table. They are identical to Rust (0.0 W difference).
- **Steady state:** an independent nonlinear Gauss-Seidel solve agrees within 5.9e-11 / 6.5e-11 K (co-located / not). Energy totals agree to 2.5e-13 / 2.7e-13 relative.
- **Transient (3000 s from 250 K):** Radau at rtol 1e-10 against Rust at dt 0.1 s gives 0.009 K ≤ 1e-2 K; ΔH agrees exactly. At the 5 s verification step the first-order implicit-Euler global error is 0.35 K. That is not an implementation difference: it scales with dt, and the per-step CONS-T2 criterion is met.

## Adapter (producer → consumer)

`crates/abep-subsystems/src/thermal/icp_v2_adapter.rs` maps by the locked key table:
- **Status:** CONVERGED → EVALUATED; withheld statuses are kept; any other status is refused.
- **Keys:** every table key exactly once; duplicated, renamed or dropped keys are refused, and each key row must equal its locked row.
- **Evidence:** SYNTHETIC for a SYNTHETIC producer record, otherwise model-derived; validation status NOT_VALIDATED.
- **TK-06 split:** the producer's echoed split is returned for comparison with the consumer's registered split.

## Scope

Software verification only (ADM-05). Flight and bench ICP heat stays refused while NP-ICP model_version 2 is not admitted (NP_ICP_NEUTRALIZER_NOT_ADMITTED). The real-configuration f_up and TK-06 split stay TBD; none is invented. CFG-FLIGHT-HALL-ON stays NOT_EVALUATED.
