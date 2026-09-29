# S1-readiness gate (fo_s1_readiness_gate)

**Status: DRAFT for owner review.** The eight conditions are the owner's. The gate reads them from the execution-directive
addendum `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json`
(`execution_directive_2026_09_27.S1_readiness_conditions`). That addendum amends the immutable original pivot
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`, and controls C1–C4 live in
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A1_controls.json`. The A3 addendum
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json` is pinned for provenance only: it states that
this gate (N4, `S1_NOT_READY` 0/8) is not modified and that S1a (non-score-bearing engineering qualification) is a
separate gate; its metrology, cathode-temperature, RGA, coverage-factor and instrumentation-version decisions bind the
producers of the S1-C4/S1-C5 artifacts, not this gate's checks. This lane
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
  schedule S1 on its own. Neither does any other single workstream closing. The directive's chain (A2 addendum) is
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
`S1_READY` requires two things. First, the authority must hold. Second, all eight conditions must be `SATISFIED`.

The authority check fails closed. It requires all of the following:
- the four owner decision files (original pivot, A1 controls, A2 execution directive, A3 S1a/instrumentation) are present and byte-identical to
  the sha256 pinned in the spec (`authority.documents`);
- the original is `od_hardware_pivot`, decided by the owner and `APPROVED`;
- each addendum is decided by the owner, names the original in `amends`, and its `amends_sha256` equals the sha256 of the
  original file on disk;
- the eight conditions read from A2 equal the spec's `owner_condition` list verbatim and in order.

The report records every document's pinned and on-disk sha256. If any file is missing or altered, the verdict is
`S1_NOT_READY` whatever the conditions show. Anything else gives `S1_NOT_READY`, and the report lists each unsatisfied condition with:
- its expected path(s)
- the failed checks
- what would satisfy it
- who produces it

Each condition gets one of these states:

| state | meaning |
|---|---|
| `SATISFIED` | the artifact passes every rule |
| `MISSING` | there is no artifact at any expected path |
| `REJECTED_DRAFT` | a `status`, `decision` or `flight_status` field anywhere in the artifact (top level or nested, e.g. one LOCK-1 decision, one hardware item, one feed point) contains DRAFT, PROPOSED or PENDING |
| `INVALID` | the artifact fails one or more rules |
| `AMBIGUOUS` | an artifact exists at more than one candidate location, and the gate never chooses between them |

Availability is `PARTIAL_PRECURSORS_ONLY` when a precursor draft exists. It is shown for orientation only: a precursor
never satisfies a condition.

Rules the gate enforces:
- **No condition is inferred or filled by assumption.** A value starting with `TBD` never counts as present. Dates
  must be real calendar dates (`2026-13-45` is rejected).
- **DRAFT or PROPOSED artifacts never satisfy a condition.** This includes feed points labelled
  `flight_status = PROPOSED_FLIGHT_REPRESENTATIVE` (control C2, A1 addendum): they are precursors only.
  `GROUND_QUALIFICATION_POINT` labels in the W1 closure are precursors too. **A label alone never satisfies S1-C3.** Only
  two records do: (a) an owner-frozen DI-1 record, or (b) an owner-approved (`RELEASED_FOR_S1`, `decided_by=owner`)
  file of `GROUND_QUALIFICATION_POINT` feed points that pins the W1 closure it selects them from.
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
| S1-C3 | DI-1 or explicitly labelled ground-qualification feed points | (a) `docs/architecture_comparison/feed_state_closure/DI1_FROZEN.json` or (b) `.../s1_feed_points.json` | (a) `id=DI-1`, `FROZEN`, owner, W1 closure sha256; every point carries a non-draft `flight_status` (no `PROPOSED_FLIGHT_REPRESENTATIVE` once DI-1 is frozen). (b) `RELEASED_FOR_S1`, owner, LOCK-1 ref, W1 closure sha256 (`source_closure`); every point is `flight_status = GROUND_QUALIFICATION_POINT`. In both (a) and (b) (symmetry PROPOSED; the owner may relax it for DI-1) the record carries `test_points[]`, and every point has {ṁ_s, P_feed, T_feed, x_s}, each with value, unit, source and evidence class. At least one N₂ point is required (S1b is at OP3 on N₂). The W1 closure's labelled points are precursors only | (a) owner freezes DI-1. (b) W1 (fo_feed_state_closure) selects `GROUND_QUALIFICATION_POINT` points and the owner approves and releases them |
| S1-C4 | instrumentation capability demonstrated | `docs/experiments/instrumentation/capability_demonstration_v1.json` | `DEMONSTRATED`; `evidence_basis=calibration_measurement`; `accepted_by=owner`; calibration-plan sha256; covers thrust stand, bus-power metering, I_d, flow, pressure, temperature, B(z), stability, species/divergence. Each entry is `measured`, dated, with raw data sha256 under `docs/experiments/instrumentation/raw/` and a demonstrated uncertainty whose evidence class is `measured` | W4 (fo_instrumentation_definition), measuring per S1-C5; owner accepts |
| S1-C5 | calibration plan frozen | `docs/experiments/instrumentation/calibration_plan_frozen.json` | `FROZEN`; owner; LOCK-1 ref; a procedure, traceability and acceptance rule for every category above | W4 drafts; owner freezes |
| S1-C6 | data custody / blinding plan frozen | `docs/experiments/custody/custody_blinding_plan_frozen.json` | `FROZEN`; owner; LOCK-1 ref; named custodian; `partition_frozen_before_h1_data=true`; non-empty calibration/registration and held-out partitions (C1); raw-data freeze, blinding and release-log rules | W5 (fo_hall_validation_prereg_draft) with the lane 06/25 custody rules; owner designates the custodian and freezes |
| S1-C7 | facility chosen | `docs/decisions/OD_S1_FACILITY.json` | `id=od_s1_facility`; owner; `APPROVED`; LOCK-1 ref (D-12); facility name, Hall-on vacuum facility and thrust stand; `same_for_S1b_and_score_bearing_stages=true` (lane 25 S1b rule) | owner (facility contact is the owner's channel) |
| S1-C8 | safety / operational limits defined | `docs/experiments/hardware/s1_safety_operational_limits.json` | `APPROVED`; `approved_by=owner`; LOCK-1 and facility refs; limits for discharge V/I max, magnet current max, cathode heater/keeper current max, background pressure max, component temperature max and oxidizer gas handling, each with source and exceedance action; ≥ 1 abort condition | W3 with the facility limits and fo_magnet_coil_qualification; owner approves |

## Current status (regenerated after merging 7d37337 (owner addendum A3), W3 9a33979, W4 v1-r2 fe2c05e and AO register v4 91a7989)
**S1_NOT_READY.** The authority holds: all four owner decision files match their pins, and the A1/A2/A3 `amends_sha256`
equal the original's sha256 `5a5adb81…`. All eight conditions are `MISSING`. Every condition has `PARTIAL_PRECURSORS_ONLY`
availability: precursor drafts exist, but they never satisfy a condition. The precursors are:
- **C1:** the W2 LOCK-1 draft and decision brief, and the experiment package (open D-01..D-15).
- **C2:** the W3 hardware requirements register, the lane 17 Hall reference and the lanes 10/19 cathode records.
- **C3:** the W1 feed-state closure. Its points carry `flight_status` labels and status `PROPOSED (candidate-conditional)`,
  so they are precursors only. Also the lane 16 feed envelope, the lane 33 ICD and the lane 14 dual feed.
- **C4:** the W4 instrumentation definition. It is a design, not a demonstration.
- **C5:** the lane 25 experiment draft and the W4 instrumentation definition.
- **C6:** the W5 pre-registration draft and the lane 06 protocol draft.
- **C7:** the experiment package (D-12) and the lane 06 protocol draft.
- **C8:** the W3 hardware register, the lane 20 electrical closure, lane 15 thermal/life and the lane 24 hard gates.

The list follows `s1_readiness_status_current.json`. Regenerate it with
`python scripts/experiments/s1_readiness.py --out docs/experiments/s1_readiness/s1_readiness_status_current.json`.

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
9. The `flight_status` label that feed points carry once DI-1 is frozen. Control C2 only says that
   `PROPOSED_FLIGHT_REPRESENTATIVE` holds until then. The gate requires a non-draft label in the DI-1 record and invents
   no name for it. It also asks whether owner-released S1 points (S1-C3 b) may only be `GROUND_QUALIFICATION_POINT`, as
   proposed here.

Compliance:
- The gate reads no Hall transport closure, screening candidate or withdrawn 0-D number.
- No architecture is ranked or eliminated.
- P5 calibration nuisance is never an item.
- Nothing is registered in the governance files; the orchestrator does that.
