# NP-HALL-PARAMETRIC-ENVELOPE addendum A7 — Hall numerical method

`prereg_addendum_a7_hall_numerical_method_v1.json` is authoritative; this page restates it.

- Status **PREREGISTERED_NOT_RUN**, label **PARAMETRIC / NOT_VALIDATED**.
- Registered 2026-10-08 on `87625c9`, before any A7 demonstration or grid run, under A9.36 / A9.37 / A9.38.
- Lock: `prereg_addendum_a7_hall_numerical_method_lock_v1.json`.
- v1, A3, A6 (the A6 STOP stands as history) and every frozen record are unchanged.
- Physics is unchanged: pin, bridge_lib.jl, Xe chemistry, vacuum mode, wall model, boundary conditions, initial
  condition, the 2268 grid points and the nine transports.

## Method (from the Phase 1 diagnosis, `hall_numerics_diagnosis_v1.json`)

**Implementation.**
- Bridge: `hallthruster_bridge/a7_numerics.jl` `a7_record`. It builds the bridge_lib run_case Config; at v1 numerics it
  is bit-identical to run_case.
- Driver: `driver/h1_envelope_a7_driver.jl`.

**Solver settings.** The pinned defaults, written into every case: adaptive, CFL 0.799, min / max dt 1e-10 / 1e-7 s,
max_small_steps 100, reconstruction on, implicit energy 1.0.

**Levels.** Both levels run 4 × the v1 duration and average from 1 × the v1 duration to the end (3 × v1 window), with
4000 saved frames.

| level | cells | dt |
|---|---|---|
| A7-P (production) | 2 × v1 (0.25 mm) | 2.5 ns |
| A7-C (check) | 4 × v1 (0.125 mm) | 1.25 ns |

**Observables.**
- Thrust and I_d: time-means of the per-frame instantaneous values (the vendor regression convention).
- Batch-means SE: 10 batches.
- Half-window means.
- Reported only: Id_rms_rel, the v1 sustained flag, ion current, and the v1 / A6 averaged-state thrust.

## Run status

Precedence order:

| status | condition |
|---|---|
| NUMERICAL_FAILURE | failed, non-converged, non-finite, or a missing observable |
| EXTINCT | mean I_d < 1e-3 e ṁ / m_Xe |
| NOT_SUSTAINED | v1 rule over the window |
| NON_STATIONARY | half-means differ by > 2 % + 2 × 2 SE |
| STATISTICALLY_UNRESOLVED | SE / mean > 2.5 % (T or I_d) |
| PASS | none of the above |

- PASS and NOT_SUSTAINED are evaluated physics. The rest are unknowns: never feasible, never a non-closure.
- The 2.5 % cap sits in the observed gap: resolvable 0.24–1.9 %, unresolved 4.3–5.9 %. A 1 % cap would flip
  resolvable cases between levels by sampling noise.

## Convergence (per case, A7-P vs A7-C)

- **C-STATUS:** same class (PASS, NOT_SUSTAINED or UNKNOWN).
- **C-QUIET:** same quiet class (Id_rms_rel < 0.5).
- **C-T, C-ID:** |X_P − X_C| ≤ 2 % |X_C| + 2 √(SE_P² + SE_C²).

The 2 % term is the A3 / A6 basis. The 2σ term is zero for quiet runs, so quiet cases meet exactly the A3 / A6 rule.

**Case outcomes:**
- CONVERGED_EVALUATED: the classes agree, both are evaluated physics, and every applicable criterion passes.
- PERSISTENT_UNKNOWN: unknown at both levels.
- NOT_CONVERGED: anything else.

## Demonstration subset (42 cases, 84 runs)

- **22 A6 study cases.** All mandatory A3 / A6 failures are included.
- **14 fresh seeded cases.** One per hardware configuration, seed `NP-HALL-PARAMETRIC-ENVELOPE/A7/v1`, excluding the A3
  and A6 sets.
- **6 RP-1 seeded cases** on the DBF-1 hardware (G-RP1, BZ-P5B16). One per B_peak × ṁ level; V_d and transport are
  seeded.
- **RP-1 subset:** every G-RP1 key. 11 cases, 8 of them on BZ-P5B16. It runs first and is scored first.

## Pass rule

For each scope, the outcome is **A7_CONVERGED_SUBSET_DEMONSTRATED** when no case is NOT_CONVERGED and at least one case
is CONVERGED_EVALUATED. Otherwise it is **A7_STOP_NOT_DEMONSTRATED**.

| scope | cases | result file | gates |
|---|---|---|---|
| RP1 | the RP-1 subset | `a7_demonstration_rp1_result_v1.json` | Stage 1 |
| ALL | every case | `a7_demonstration_result_v1.json` | Stage 2 |

- Persistent unknowns do not fail the rule. They are counted, listed and remain unknowns.
- There is no margin tier.
- A STOP means no gated stage is run, and HALL_NUMERICS_NOT_CONVERGED stays.

## Envelope rerun

- **Stage 1.** All 324 G-RP1 cases of the v1 XE grid at A7-P. Frozen and ingested on its own, followed by an interim
  report.
- **Stage 2.** The other 1944 cases at A7-P, the same way.
- **Ingestion.** `abep_hall::envelope_a7::ingest_a7` builds a separate frozen version. Each supplied stage must be
  complete, and the gating result is re-read.
- **Harness v2** (`--envelope-xe-a7-stage1/2`):
  - Uses the A6 tests HALL_XE_T12_AT_PBUS and HALL_XE_T25_CAPABILITY_AT_PBUS on one hardware configuration.
  - EC-NUM cites A7.
  - C0..C4 are unchanged.
  - A labelled dry run per stage. It is not M2.
- **AIR** is not rerun: it is information only (A1), and the cost is not small.
