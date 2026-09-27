# S1-readiness gate (fo_s1_readiness_gate)

**Status: DRAFT for owner review.** The eight conditions are the owner's
(`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`, `execution_directive_2026_09_27.S1_readiness_conditions`). This lane
proposes the artifact paths, required fields, accepted status values and coverage sets that make each condition
machine-checkable. The owner may change any of them. Nothing here is decided, pre-registered or locked. The gate carries no
physical, efficiency or RFP threshold value.

| file | role |
|---|---|
| `s1_readiness_conditions_v1.json` | spec: the eight conditions, the artifact(s) that can satisfy each, the machine-checkable rules, precursors and producers |
| `../../../scripts/experiments/s1_readiness.py` | the gate. It is pure and read-only (it writes only with `--out`), deterministic, and imports only the standard library |
| `s1_readiness_status_current.json` | report generated from the repository at this lane's base commit (`926ebb0`): **S1_NOT_READY, 0/8 satisfied, 8 missing** |
| `../../../tests/test_s1_readiness.py` | tests: all missing → NOT_READY with 8 items; DRAFT/PROPOSED rejected; synthetic complete fixture → READY; deterministic |

```
python scripts/experiments/s1_readiness.py                      # print report; exit 0 = S1_READY, 1 = S1_NOT_READY, 2 = spec error
python scripts/experiments/s1_readiness.py --out docs/experiments/s1_readiness/s1_readiness_status_current.json
python scripts/experiments/s1_readiness.py --check docs/experiments/s1_readiness/s1_readiness_status_current.json
```

## How S1 gets scheduled
- **S1 is scheduled only when this gate returns `S1_READY`.** W2 finishing, or the LOCK-1 brief being written, does not
  schedule S1 on its own. Neither does any other single workstream closing. The directive's chain is
  W1 + W2 + W3 + W4 + W5 → owner review → LOCK-1 → S1 qualification → measured uncertainty/calibration → LOCK-2 →
  score-bearing common-condition experiment. The convergence point (controls addendum) is DI-1 feed state + LOCK-1 + H-1/C-1
  hardware + instrument capability. The gate makes that convergence explicit and checkable.
- **S1 is qualification, not architecture selection.** Per the directive's `S1_purpose`, S1 shows that the stand, feed
  system, H-1, cathode, power measurement, magnetic configuration and diagnostics are reproducible enough for the paired
  test. Phase 1 then locates the Hall-only N₂ sustainment knee and characterises ignition/extinction, and that result places
  the RF/ECR comparisons. S1 data are not score-bearing (lane 25 `s1_plan`). No architecture (`hall_only`, `rf_hall`,
  `ecr_hall`) is ranked, preferred or eliminated by S1 or by this gate.
- **What LOCK-2 freezes afterwards** (directive `LOCK2`): only what real facility performance can determine:
  - achieved thrust and power uncertainty
  - repeatability and drift
  - the block count, if the pre-registered rule allows it
  - calibration constants
  - facility corrections

  LOCK-2 may only add S1 values and what the LOCK-1 rules compute from them, without discretion. Any change to a LOCK-1
  item voids LOCK-1 (lane 25 `preregistration.locks[1]`). S1 architecture-comparison outcomes never change decision
  thresholds. Score-bearing data taken before LOCK-2 are excluded.
- **Data rule:** no experimental data is used for model promotion until the W5 pre-registration is frozen. Controls C1
  also requires the calibration/held-out partition to be frozen before any H-1 data exist. S1 produces the first H-1 data,
  so condition S1-C6 needs that partition.

## Gate semantics
`S1_READY` requires two things: the owner disposition `od_hardware_pivot` is present and `APPROVED`, and all eight
conditions are `SATISFIED`. Anything else gives `S1_NOT_READY`, and the report lists each unsatisfied condition with:
- its expected path(s)
- the failed checks
- what would satisfy it
- who produces it

Each condition gets one of these states:

| state | meaning |
|---|---|
| `SATISFIED` | the artifact passes every rule |
| `MISSING` | there is no artifact at any expected path |
| `REJECTED_DRAFT` | a `status` or `decision` field anywhere in the artifact (top level or nested, e.g. one LOCK-1 decision, one hardware item, one feed point) contains DRAFT, PROPOSED or PENDING |
| `INVALID` | the artifact fails one or more rules |
| `AMBIGUOUS` | an artifact exists at more than one candidate location, and the gate never chooses between them |

Availability is `PARTIAL_PRECURSORS_ONLY` when a precursor draft exists. It is shown for orientation only: a precursor
never satisfies a condition.

Rules the gate enforces:
- **No condition is inferred or filled by assumption.** A value starting with `TBD` never counts as present. Dates
  must be real calendar dates (`2026-13-45` is rejected).
- **DRAFT or PROPOSED artifacts never satisfy a condition.** The per-point flight-status label `PROPOSED_FLIGHT_REPRESENTATIVE`
  (controls C2) is accepted as a label on a feed point. The document that carries those points must still be released by
  the owner.
- **Every reference is a `{path, sha256}` pair, re-hashed on disk.** Paths must be repository-relative, and nothing outside
  the repository is read.
- **Chained records must reference the uniquely located, signed LOCK-1** (`artifact_of`). These are the configuration
  freeze, the feed points, the calibration plan, the custody plan, the facility choice and the safety limits. The capability
  demonstration must reference the frozen calibration plan, and the safety limits must reference the facility choice.
- **A design analysis is never a demonstration.** S1-C4 requires `evidence_basis = calibration_measurement`, per-instrument
  `evidence_class = measured`, a `demonstrated_uncertainty` whose own `evidence_class` is `measured`, and committed raw
  calibration data (sha256) under the PROPOSED raw-data directory `docs/experiments/instrumentation/raw/`. A plan, the
  capability record itself or any other document is never accepted as raw data.
- **LOCK-1 choices are option ids.** Each D-01..D-15 `owner_choice` must be an option id of that decision (`D-NN-X`, the
  form used in `experiment_package_v1.json`). Free text, `PENDING`, `OPEN` or `PROPOSED` never count.

## The eight conditions → evidence artifacts (all paths and file names PROPOSED)
| id | owner condition | expected artifact | key machine checks | producer |
|---|---|---|---|---|
| S1-C1 | LOCK-1 signed by the owner | `LOCK1.json` at the owner's D-05 location, one of: `docs/architecture_comparison/{experiment_protocol,minimum_decisive_experiment,experiment_package}/prereg/`, `docs/architecture_comparison/lock1/` | `status=SIGNED`, `locked=true`, `decided_by=owner`, `decided_utc`, `decision_source` = sha256 of `docs/architecture_comparison/lock1/lock1_decision_brief_v1.json`, D-01..D-15 `owner_choice` = an option id `D-NN-X` of that decision, location = D-05 choice. D-05-D (`lock1/`) is not an option of `experiment_package_v1` D-05; it is PROPOSED from the planned W2 brief and needs owner confirmation | owner signs, using the W2 brief (fo_lock1_decision_brief). `LOCK1_DRAFT.json` never counts |
| S1-C2 | H-1/C-1 configuration frozen sufficiently for qualification | `docs/experiments/hardware/configuration_freeze_H1_C1.json` | `FROZEN_FOR_QUALIFICATION`; owner; LOCK-1 ref; `requirements_basis` = W3 register sha256; items H-1, C-1, MC-1 each `FROZEN` with serial/part id and configuration record | W3 (fo_hardware_definition) after delivery; owner approves |
| S1-C3 | DI-1 or explicitly labelled ground-qualification feed points | (a) `docs/architecture_comparison/feed_state_closure/DI1_FROZEN.json` or (b) `.../s1_feed_points.json` | (a) `id=DI-1`, `FROZEN`, owner, W1 closure sha256. (b) `RELEASED_FOR_S1`, owner, LOCK-1 ref. In both (a) and (b) (symmetry PROPOSED; the owner may relax it for DI-1) the record carries `test_points[]`; every point is labelled `PROPOSED_FLIGHT_REPRESENTATIVE` or `GROUND_QUALIFICATION_POINT` and has {ṁ_s, P_feed, T_feed, x_s}, each with value, unit, source and evidence class. At least one N₂ point (S1b is at OP3 on N₂) | (a) owner freezes DI-1. (b) W1 (fo_feed_state_closure) selects the points and the owner releases them |
| S1-C4 | instrumentation capability demonstrated | `docs/experiments/instrumentation/capability_demonstration_v1.json` | `DEMONSTRATED`; `evidence_basis=calibration_measurement`; `accepted_by=owner`; calibration-plan sha256; covers thrust stand, bus-power metering, I_d, flow, pressure, temperature, B(z), stability, species/divergence. Each entry is `measured`, dated, with raw data sha256 under `docs/experiments/instrumentation/raw/` and a demonstrated uncertainty whose evidence class is `measured` | W4 (fo_instrumentation_definition), measuring per S1-C5; owner accepts |
| S1-C5 | calibration plan frozen | `docs/experiments/instrumentation/calibration_plan_frozen.json` | `FROZEN`; owner; LOCK-1 ref; a procedure, traceability and acceptance rule for every category above | W4 drafts; owner freezes |
| S1-C6 | data custody / blinding plan frozen | `docs/experiments/custody/custody_blinding_plan_frozen.json` | `FROZEN`; owner; LOCK-1 ref; named custodian; `partition_frozen_before_h1_data=true`; non-empty calibration/registration and held-out partitions (C1); raw-data freeze, blinding and release-log rules | W5 (fo_hall_validation_prereg_draft) with the lane 06/25 custody rules; owner designates the custodian and freezes |
| S1-C7 | facility chosen | `docs/decisions/OD_S1_FACILITY.json` | `id=od_s1_facility`; owner; `APPROVED`; LOCK-1 ref (D-12); facility name, Hall-on vacuum facility and thrust stand; `same_for_S1b_and_score_bearing_stages=true` (lane 25 S1b rule) | owner (facility contact is the owner's channel) |
| S1-C8 | safety / operational limits defined | `docs/experiments/hardware/s1_safety_operational_limits.json` | `APPROVED`; `approved_by=owner`; LOCK-1 and facility refs; limits for discharge V/I max, magnet current max, cathode heater/keeper current max, background pressure max, component temperature max and oxidizer gas handling, each with source and exceedance action; ≥ 1 abort condition | W3 with the facility limits and fo_magnet_coil_qualification; owner approves |

## Current status (generated at base `926ebb0`)
**S1_NOT_READY.** All eight conditions are `MISSING`. Precursor drafts in the repository give partial availability for
C1, C2, C3, C5, C6, C7 and C8:
- the lane 25/06 drafts and the experiment package (open D-01..D-15, D-12)
- the verified inputs: lane 17 Hall reference, lanes 10/19 cathode, lane 16 feed envelope, lane 33 ICD, lane 14 dual feed,
  lane 20 electrical closure, lane 15 thermal/life, lane 24 hard gates

C4 has no precursor at the base. The W1–W5 drafts (feed-state closure, LOCK-1 brief, hardware definition, instrumentation
definition, validation pre-registration) are being produced in parallel and are referenced by planned path. Once merged
they appear as precursors, but they still never satisfy a condition. The authority `od_hardware_pivot` is `APPROVED`.

## Milestones
- **Supports A:** only as a scheduling precondition. The conditions of a conditional selection get demonstrated in the
  controlled experiment after S1 → LOCK-2. The gate selects nothing.
- **Supports B:** S1 is the qualification that makes the later common-condition readings and the W5 held-out validation
  evidence admissible.
- **To reach B:** S1 must be executed and LOCK-2 filed; Phase 1–3 data must exist; the W5 pre-registration must be frozen
  and scored; and a Hall transport closure must be admitted (the credible set is empty today and gate 3 is FAIL).
- **To reach C:** mass, power, thermal, life (no 15,000 h extrapolation from an unadmitted closure, C6), startup, cathode
  and mission closure must be integrated.

## Open items for the owner (all PROPOSED)
1. The artifact paths and file names above. The S1-C6 location in particular has no owning workstream yet.
2. The accepted status strings: `SIGNED`, `FROZEN_FOR_QUALIFICATION`, `FROZEN`, `RELEASED_FOR_S1`, `DEMONSTRATED`,
   `APPROVED`.
3. The required instrument set for S1-C4/C5 and the minimum safety-limit set for S1-C8. S1-C4/C5 currently require the
   full W4 list from the disposition, including stability/oscillations and species/divergence. That may be stricter than
   S1 needs: lane 25 `s1_plan` names only M1, M2, M3, M9, M10 and M11 for S1a/S1b.
4. Whether LOCK-1 must also record P-01..P-04 (W2 draft pivot items). The gate currently requires D-01..D-15 only.
5. Whether D-05-D (`docs/architecture_comparison/lock1/`) is a valid LOCK-1 location. It is not among the D-05 options
   of `experiment_package_v1.json` (A–C only).
6. Whether the frozen DI-1 record (S1-C3 alternative a) must carry the labelled S1 feed points, as proposed here, like
   alternative (b).
7. The raw-data directory `docs/experiments/instrumentation/raw/` for S1-C4 and the option-id form `D-NN-X` for
   LOCK-1 choices.
8. Alignment of the signed-LOCK-1 fields (`decided_by`, `decided_utc`, `decision_source`) with the `signature` block of
   the W2 draft.

Compliance:
- The gate reads no Hall transport closure, screening candidate or withdrawn 0-D number.
- No architecture is ranked or eliminated.
- P5 calibration nuisance is never an item.
- Nothing is registered in the governance files; the orchestrator does that.
