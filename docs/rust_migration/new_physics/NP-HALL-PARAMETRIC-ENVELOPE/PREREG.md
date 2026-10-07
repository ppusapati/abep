# NP-HALL-PARAMETRIC-ENVELOPE v1 — preregistration (A9.32)

`prereg_v1.json` is authoritative; this page restates it. Status **PREREGISTERED_NOT_RUN**, label **PARAMETRIC /
NOT_VALIDATED**. Registered 2026-10-07 on `8a53b13`, before any HallThruster.jl run on any H-1 case. Hash lock:
`prereg_lock_v1.json`.

## What it is

The case grid, assumptions, run-status rule, output schema and decision rules of the A9.32 HallThruster.jl parametric
feasibility envelope for H-1, and the two-layer reporting and classification rule of the decisive 196-state closure run.
It is not a validation, an admission, a design Hall map or a design selection. The credible Hall transport set stays
EMPTY. HallMap admission and the hall_ensemble logic are unchanged. P5-N2 v1 stays INCONCLUSIVE.

## Grid (4536 cases)

Two families:
- **XE** (XE_CONTINGENCY). Built-in Xe. No validity manifest, so chemistry never makes an Xe run OUT_OF_DOMAIN. Flow
  axis labelled XE_FLOW_FROM_H1_ATM_RANGE.
- **N2_PROXY**. abep-n2n-0.11 nominal, f_out = 0 rule. Diagnostic only.

Each family runs over:
- 7 geometry points: the FEMM-authorised analysis points (ANALYSIS_POINT_NOT_DESIGN_SELECTION).
- 2 B(z) shapes.
- 2 B_peak values: 69.93 G and 268.6 G, the ends of the H1F-BZ-03 band.
- 3 V_d values: 180, 265 and 350 V.
- 3 flows: 0.377, 1.287 and 3.2 mg/s.
- 9 transport candidates: sgb-screen-01..09, as recorded.

Run settings:
- Vacuum mode.
- Numerics follow the P5-N2 settings: 0.5 mm cells, dt 5 ns, duration 2 ms scaled by the domain length, averaging over
  the second half. Labelled NUMERICAL_ADEQUACY_NOT_VERIFIED_FOR_H1.
- The domain ends at the last sourced B datum.

## B(z) gap

H-1 B(z) is **not registered** (H1F-BZ-01 TBD). The family is a labelled **SOURCED_SURROGATE**:
- It uses the two P5 Peterson 2001 shapes.
- Each shape is registered rigidly with its peak at the H-1 exit (H1F-BZ-02) and scaled to the H1F-BZ-03 band ends.
- It is never an H-1 design value.

The rule is asymmetric:
- A Hall closure under the surrogate can support SELECT_WITH_EVIDENCE_CONDITIONS, with the evidence condition EC-BZ.
- A Hall non-closure under the surrogate is recorded, but it cannot support PHYSICALLY_NON_CLOSING. The surrogate is not
  shown to be favorable for H-1, so the result is NOT_DETERMINABLE with the blocker H1_BZ_NOT_REGISTERED.

## AIR

There is no Hall O / O2 chemistry. Atomic O is 5–86 % of the inflow across the required states, so:
- AIR_PRIMARY layer (a) Hall is NOT_EVALUATED (AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED).
- N2_PROXY results go in their own diagnostic block.
- N2 is not a bound in either direction, so N2_PROXY never enters feasibility or classification.

## Favorable but defensible

**Defensible**: every axis is a registered H-1 value or range, or a registered / sourced assumption. Nothing is chosen
after seeing a result.

**Favorable** means:
- Existence over the grid: the maximum over geometry, shape, B_peak, V_d, flow and transport.
- The solver's thrust_N, with no added divergence loss.
- P_bus = P_d + P_nonHall,LB, with PPU efficiency taken as 1.
- No super-Bohm sets, no retuning, no interpolation.

A non-closure claim also needs every axis family to be H-1-registered or demonstrably bounding.

## Run status

| status | condition |
|---|---|
| NUMERICAL_FAILURE | failure, non-converged or non-finite run |
| OUT_OF_DOMAIN | N2 run with f_out > 1e-12 or an unresolved table |
| NOT_SUSTAINED | bridge `sustained` flag false |
| PASS | none of the above |

- Precedence is in that order. Only PASS counts toward feasibility.
- PASS and NOT_SUSTAINED are evaluated physics. OUT_OF_DOMAIN and NUMERICAL_FAILURE are unknowns.
- Any record mismatch (case hash, pin, lock, keys) rejects the whole envelope with MODEL_ERROR.

## Closure and classification

**Hall-specific point tests** (thresholds HC-01, HC-02 and HC-03 from the frozen configuration):

| test | applies to | condition |
|---|---|---|
| T12 | AIR | T ≥ 12 mN |
| T25 | AIR | T ≥ 25 mN |
| XE_FUNC | Xe | PASS and T > 0 |

Every test also needs P_bus,fav < 1500 W.

**Constraint statuses:**
- **CLOSES_IN_ENVELOPE**: some point passes.
- **NON_CLOSING_IN_ENVELOPE**: no point passes, and every point is evaluated physics.
- **NOT_DETERMINABLE_IN_ENVELOPE**: no point passes, and some points are unknowns.
- **NOT_EVALUATED**: no envelope ingested.

Hardware is (geometry, shape). AIR needs T12 and T25 on the same hardware.

**Non-Hall inputs.** Each one is registered as a favorable bound or as an open condition:
- FLOW: OPEN.
- ICP: OPEN.
- P_bus ledger: OPEN. Its lower bound is used inside the point tests.
- T − D: OPEN.
- Mass: OPEN. The planning-value DOES_NOT_CLOSE is reported as information only and is not eligible.
- Thermal: OPEN.
- Life: OPEN.

An open condition never makes a state non-closing.

**Classification procedure:**
- **C0**: the credible set is non-empty → NOT_DETERMINABLE.
- **C1**: no envelope → NOT_DETERMINABLE (HALL_ENVELOPE_NOT_RUN).
- **C2**: any required state of a required mode is eligible-non-closing → **PHYSICALLY_NON_CLOSING**.
- **C3**: every required state of both modes is feasible on one hardware configuration, and the credible set is EMPTY →
  **SELECT_WITH_EVIDENCE_CONDITIONS**, with EC-TRANSPORT, EC-BZ, EC-DIV, EC-NUM, EC-GEOM and the non-Hall evidence.
- **C4**: otherwise **NOT_DETERMINABLE**, with the blocking list and A9.31 sec. 21 categories.

Layer (a) (PARAMETRIC) and layer (b) (admitted only) are reported separately, with separate counts.

**Expected today:** NOT_DETERMINABLE (HALL_ENVELOPE_NOT_RUN). After the runs, the classification stays NOT_DETERMINABLE
while there is no Hall O / O2 chemistry (AIR layer (a)), and while the non-Hall inputs stay open.

## Execution

- Seeds: none (deterministic). Thread and BLAS counts are pinned to 1.
- Each record carries the commit, Julia version, threads / BLAS, host, driver, case-file, case and lock hashes.
- Each shard writes a sidecar.
- Outputs are frozen raw and sha-pinned before ingestion.
- Estimated cost: about 2 min per N2 run (Xe less), about 100–150 CPU-h in total.

## Owner questions

- **OQ-HPE-01**: the asymmetric surrogate rule.
- **OQ-HPE-02**: Hall O / O2 chemistry for AIR.
- **OQ-HPE-03**: the Xe flow.
- **OQ-HPE-04**: sourced non-Hall bounds.
- **OQ-HPE-05**: the execution environment.
- **OQ-HPE-06**: the numerical-settings rule versus RG-04.
