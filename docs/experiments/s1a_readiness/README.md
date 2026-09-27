# S1a engineering-readiness gate (fo_s1a_engineering_gate)

**Status: DRAFT for owner review.** The gate answers one question from owner addendum A3
(`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A3_s1a_and_instrumentation.json`, `next_execution.S1a_engineering_gate`):

> *Can we safely and usefully begin non-score-bearing engineering qualification?*

The S1a scope is the owner's. The gate reads it verbatim from A3 and checks every condition's clause against that text.
The artifact paths, file names, required fields, accepted status strings, coverage sets and the data-firewall class
lists are proposed by this lane (PROPOSED), and the owner may change any of them. Nothing here is decided,
pre-registered or locked. The gate carries no physical, efficiency, safety-limit or RFP value.

| file | role |
|---|---|
| `s1a_readiness_conditions_v1.json` | spec: the authority pins, the A3 owner text, the six conditions, the artifact(s) that can satisfy each one, the machine-checkable rules, precursors and producers |
| `../../../scripts/experiments/s1a_readiness.py` | the gate. It is pure and read-only (it writes only with `--out`), deterministic, and uses the standard library only. It does not import or read the N4 gate |
| `s1a_readiness_status_current.json` | report generated from this lane's repository state: **S1A_NOT_READY, 0/6 satisfied, 6 missing, firewall MISSING (fail closed)** |
| `../../../tests/test_s1a_readiness.py` | tests: DRAFT rejected, firewall missing → not ready (fail closed), synthetic complete fixture → ready, deterministic, authority fails closed |

```
python scripts/experiments/s1a_readiness.py            # print report; exit 0 = S1A_READY, 1 = S1A_NOT_READY, 2 = spec error
python scripts/experiments/s1a_readiness.py --out docs/experiments/s1a_readiness/s1a_readiness_status_current.json
python scripts/experiments/s1a_readiness.py --check docs/experiments/s1a_readiness/s1a_readiness_status_current.json
python -m pytest -q tests/test_s1a_readiness.py
```

The report records the sha256 of every precursor it finds. **Regenerate it after any merge that adds or changes a
precursor**, for example `docs/experiments/capability_demo/capability_demo_prep_v1.json` from fo_capability_demo_prep,
which is absent in this lane's tree. Otherwise `--check` and `test_repository_today_not_ready_and_report_reproduces`
report DIFFERS.

## What S1a is, and how it relates to N4 and to W4
- **S1a vs N4.** N4 is the S1-readiness gate (`scripts/experiments/s1_readiness.py`, `docs/experiments/s1_readiness/`,
  fo_s1_readiness_gate). It decides whether S1 can be scheduled after LOCK-1. S1 means the lane 25 S1a no-plasma
  calibration plus the S1b Hall-on re-mount qualification. N4 **is not modified** and stays `S1_NOT_READY` 0/8.
  S1a is the separate engineering path that the owner opened in A3:
  - it may begin **before LOCK-1**, so no S1a artifact references LOCK-1;
  - it **never takes a Hall-on H-1 reading**; the first one is S1b under N4;
  - it is **never score-bearing**;
  - `S1A_READY` **never satisfies an N4 condition**.

  Two N4 artifacts are accepted as alternatives here, because an owner release for S1 also covers S1a: the S1 feed
  points (S1-C3 b) and the S1 facility choice (S1-C7). This gate does not check their LOCK-1 references; N4 does.
- **S1a vs W4's capability demonstration** (fo_capability_demo_prep, `docs/experiments/capability_demo/`). W4 prepares
  procedures CD-01..CD-07 and the record format for the N4 S1-C4 measured-capability artifact. Once this gate returns
  `S1A_READY`, those demonstrations may run on actual hardware as non-score-bearing engineering qualification.
  Their results become S1-C4 evidence only when the owner accepts them against a frozen S1-C5 calibration plan, and that
  step belongs to N4. The frozen S1a procedures (S1A-C4) are the natural candidate for that plan. The N4 S1-C5 file is
  still a separate artifact: it references LOCK-1 and has a different category set.
- **S1a vs W5** (`docs/validation/hall_transport_v2_prereg/`). S1a produces the first H-1 data: geometry metrology and
  B(z) at coil currents. Control C1 (A1) requires the calibration/registration vs held-out partition before any H-1 data
  exist. The data firewall S1A-FW enforces this for S1a.

## Gate semantics
`S1A_READY` requires two things. First, the authority must hold. Second, all six conditions must be `SATISFIED`,
including the mandatory firewall S1A-FW.

**Authority (fail closed):**
- the four owner decision files (original pivot, A1, A2, A3) are byte-identical to the sha256 pinned in the spec
  (the same pins as N4);
- the original is `APPROVED` and decided by the owner;
- each addendum names the original in `amends`, and its `amends_sha256` equals the original's sha256 on disk;
- A3 `next_execution.S1a_engineering_gate` equals the spec's `owner_text` verbatim;
- every condition's `owner_clause` is a verbatim part of that text;
- three supporting quotes are verbatim parts of their fields: A3 `near_cathode_rga`, the A2 `data_rule` and A1
  `C1_W5_partition`.

**Firewall (fail closed):** if S1A-FW is not `SATISFIED` (missing, draft, invalid or ambiguous), the verdict is
`S1A_NOT_READY` whatever else holds. The report's `firewall.fail_closed` is then `true`. Every calibration procedure
must also declare an `s1a_data_class` that is one of the firewall's allowed classes (rule `member_of_artifact`). That
check fails closed too, so S1A-C4 cannot be satisfied without a satisfied firewall.

**States:**

| state | meaning |
|---|---|
| `SATISFIED` | the artifact passes every rule |
| `MISSING` | no artifact at any expected path |
| `REJECTED_DRAFT` | a `status`, `decision` or `flight_status` field anywhere in the artifact contains DRAFT, PROPOSED or PENDING |
| `INVALID` | the artifact fails one or more listed rules |
| `AMBIGUOUS` | the artifact is found at several candidate locations; the gate never chooses |

**Rules:**
- A value starting with `TBD` never counts as present.
- Dates must be real calendar dates.
- Every reference is a repository-relative `{path, sha256}` pair, and the gate re-hashes the file on disk.
- Nothing outside the repository is read.
- Precursors are shown for orientation only and never satisfy a condition.

## The six conditions → evidence artifacts (all paths, file names and tokens PROPOSED)
| id | owner clause (A3, verbatim) | expected artifact | key machine checks | producer |
|---|---|---|---|---|
| S1A-C1 | "the hardware needed for calibration/shakedown" | `docs/experiments/hardware/s1a_engineering_hardware_record.json` | `IDENTIFIED_FOR_S1A`; recorded_by / recorded_utc; `accepted_by=owner`; W3 register sha256. Items H-1, MC-1, FS-C, PS-C, SVC-1, INS-01, -02, -04..-09, -17, -18 are each `AVAILABLE`, with serial/part id, a configuration record and `configuration_state` ∈ {`RECORDED_NOT_FROZEN`, `FROZEN_FOR_QUALIFICATION`}. H-1 need not be frozen, but it must be recorded | W3 + experiment team; owner accepts |
| S1A-C2 | "safe operational limits" | `docs/experiments/hardware/s1a_safety_operational_limits.json` | `APPROVED`, `approved_by=owner`; facility ref (S1A-C5 artifact). Limit domains: electrical, vacuum, thermal, gas. Required quantities: magnet current, supply voltage, cathode heater current, background pressure, component temperature, coil winding temperature, feed pressure, oxidizer (O₂) gas handling. Each limit carries limit, source and action on exceedance. Required interlocks: IL-VACUUM, IL-HALL-DISCHARGE-INHIBIT, IL-OXIDIZER-ISOLATION, IL-EMERGENCY-STOP, each with function and verification. At least one abort condition with trigger and action | W3 with the facility's limits and fo_magnet_coil_qualification; owner approves |
| S1A-C3 | "released ground-qualification feed points" | (a) `docs/architecture_comparison/feed_state_closure/s1a_feed_points.json` or (b) N4's `.../s1_feed_points.json` | (a) `RELEASED_FOR_S1A`, owner, W1 closure sha256, `use_restriction = COLD_FLOW_CALIBRATION_NO_HALL_DISCHARGE`; every point `flight_status = GROUND_QUALIFICATION_POINT`, with `source_point_id` (the W1 id) and {ṁ_s, P_feed, T_feed, x_s}, each carrying value, unit, source and evidence class; at least one N₂ point. (b) `RELEASED_FOR_S1` with the same point rules. A label in the W1 closure alone never counts | W1 selects; owner releases |
| S1A-C4 | "frozen calibration procedures" | `docs/experiments/instrumentation/s1a_calibration_procedures_frozen.json` | `FROZEN`, owner, firewall ref (S1A-FW artifact). Categories: thrust_stand, power_channels, mass_flow_controllers, magnetic_field_Bz, daq_time_base, temperature_channels. Each has procedure id, procedure, traceability, acceptance rule and an `s1a_data_class` the firewall allows. The temperature procedure carries `cathode_temperature_labelling` (A3: the tube thermocouple is never labelled emitter temperature) | W4 (CD-01..CD-07 candidates) drafts; owner freezes |
| S1A-C5 | "an engineering facility" | (a) `docs/decisions/OD_S1A_FACILITY.json` or (b) N4's `docs/decisions/OD_S1_FACILITY.json` | (a) `id=od_s1a_facility`, owner, `APPROVED`; facility name, vacuum facility, safety-responsible role; `same_as_hall_on_facility` recorded as a boolean. It is not required to be true, but S1a calibrations from another facility do not carry into LOCK-2 | owner |
| S1A-FW | "it explicitly forbids held-out H-1 physics outputs from leaking into W5" | `docs/experiments/custody/s1a_data_firewall_frozen.json` | see below | W5 with the custodian; owner designates the custodian and freezes |

### The data firewall S1A-FW (mandatory, fail closed)
Required content of the owner-frozen artifact:
- **Identity and basis:**
  - `id=s1a_data_firewall`, `FROZEN`, owner, `decided_utc`;
  - `w5_basis` = sha256 of the W5 document under `docs/validation/hall_transport_v2_prereg/` whose classes it
    implements. A later W5 change breaks the pin and the gate fails closed until the firewall is re-frozen;
  - the owner-designated `data_custodian`, never a physics-track modeller (W5 roles).
- **`h1_hall_discharge_in_s1a = FORBIDDEN`.** W5 classes no Hall-on reading as S1a calibration or registration. Its only
  pre-LOCK-2 Hall-on data are the S1b dispersion statistics, and S1b falls under N4. Interlock IL-HALL-DISCHARGE-INHIBIT
  (S1A-C2) enforces this physically.
- **Allowed classes** (each with a definition and a release rule): CALIBRATION, NOISE, DRIFT, REPEATABILITY,
  REINSTALLATION (no-plasma CD-02a only; the Hall-on re-mount CD-02b is S1b), CHANNEL_PERFORMANCE, QUALITATIVE_RGA and
  FACILITY_BACKGROUND. QUALITATIVE_RGA must carry `no_dose_or_lifetime_claim = true`, per the A3 rule that an
  uncalibrated S1a RGA is qualitative only.
- **Registration inputs measured in S1a:** REG-GEOM, REG-BZ and REG-FEED. Each has a `release_condition`: per W5 K1/K2,
  the custodian releases them to the physics track only after LOCK-H1. A B(z)-vs-magnetic-circuit comparison is a
  magnetics check, never transport-validation evidence (W5 VO-BZ).
- **Forbidden or embargoed** (treatment `FORBIDDEN_IN_S1A` or `EMBARGOED_CUSTODY_ONLY`, each with a consequence):
  - the W5 observables VO-ID (I_d), VO-T (thrust), VO-IGNEXT (sustainment/extinction), VO-OSC, VO-SPECIES, VO-IEDF (ion
    energy), VO-DIV (divergence) and VO-TENE (T_e/n_e);
  - the embargoed HW-0 derived quantities HW0-PBUS-HALL-ON, HW0-RARCH and HW0-KNEE;
  - the catch-all H1-ANY-HALL-OPERATING-POINT.
- **Rules:** `custody_rule`, `outputs_seen_rule`, `repository_rule`, `breach_response` and `release_log`.
  - Under the W5 `publication_rule.automatic_flag` and `leak_rule`, any exposure of an embargoed value outside the
    custody circle before PF-1 is hash-frozen automatically flags every affected F1/F2/F3/F6 condition `OUTPUTS_SEEN`.
    The result is `TARGET_NOT_ADMISSIBLE_OUTPUTS_SEEN`, which makes the candidate INCONCLUSIVE, not FAIL.
  - W5 defines no automatic flag for a registration input released before LOCK-H1. Such a release breaks W5 K1, and
    the PROPOSED response is an owner disposition.

The feed points released for S1a include Phase-1 knee-ladder points, which are W5 held-out family F1. In S1a they are
cold-flow calibration setpoints only (`use_restriction`), and no discharge is run at them.

## Current status (this lane's tree: 7d37337 + S1GATE 0b8aa34)
**S1A_NOT_READY, 0/6, firewall MISSING → fail closed.** The authority holds: all four pins match and the A3 text
matches verbatim. All six conditions are `MISSING` with `PARTIAL_PRECURSORS_ONLY`. The precursors are drafts that never
satisfy a condition:
- **C1:** the W3 register and the W4 instrumentation definition v1-r2.
- **C2:** the W3 register, the magnet/coil qualification basis, the lane 20 electrical closure and the lane 24 hard
  gates.
- **C3:** the W1 closure (32 GROUND_QUALIFICATION_POINT labels, all `PROPOSED (candidate-conditional)`, with
  T_feed_ground TBD under DI-1.10) and the lane 16 feed envelope.
- **C4:** the W4 definition and the lane 25 `s1_plan.S1a_no_plasma`. The fo_capability_demo_prep record is absent from
  this tree.
- **C5:** the experiment package (D-12) and the lane 06 protocol draft.
- **FW:** the W5 pre-registration DRAFT.

## Milestones
- **Supports A** only as a schedule enabler. Starting engineering qualification early shortens the path to
  S1 → LOCK-2 → the controlled HW-0 / HW-RF / HW-ECR experiment, where the conditions of a conditional selection get
  demonstrated. The gate selects, ranks and eliminates nothing.
- **To reach B:** N4 must return `S1_READY`; S1 must be executed and LOCK-2 filed; Phase 1–3 data must exist; W5 must be
  frozen and scored; and a Hall transport closure must be admitted (the credible set is empty and gate 3 is FAIL).
- **To reach C:** mass, power, thermal, life (no 15,000 h extrapolation from an unadmitted closure), startup, cathode and
  mission closure must be integrated.

## Open items for the owner (all PROPOSED)
1. The artifact paths, file names and status tokens: `IDENTIFIED_FOR_S1A`, `AVAILABLE`, `RECORDED_NOT_FROZEN`,
   `RELEASED_FOR_S1A`, `COLD_FLOW_CALIBRATION_NO_HALL_DISCHARGE`, `FROZEN`, `APPROVED`, `FORBIDDEN_IN_S1A`,
   `EMBARGOED_CUSTODY_ONLY`. In particular, `docs/experiments/custody/` has no owning workstream yet.
2. The required hardware set of S1A-C1:
   - whether C-1 is required, which it would be if S1a includes the W3 "S1a (diode)" checkout of HW-C1-02;
   - whether RGA, PIM-* (configuration-specific B(z) maps) and INS-03 (RF/microwave load plane) are required.
3. The minimum limit, interlock and abort set of S1A-C2, including whether RF/microwave dummy-load exposure limits are
   needed in S1a.
4. Whether C-1 diode / keeper operation belongs in S1a. If it does, the owner must say which allowed data class covers
   it. It is not an H-1 Hall operating point, but cathode-to-ground potential during Hall operation is a W5 VP-10
   registration candidate.
5. The allowed and forbidden class lists and the catch-all definition "any H-1 anode discharge (H-1 anode, C-1 and MC-1
   energized together)".
6. The response to a registration input released before LOCK-H1. W5 defines no automatic flag for it; this lane
   PROPOSES an owner disposition.
7. Whether installation/reinstallation (CD-02a) must be a required S1A-C4 category. It is optional here.
8. Whether the S1a facility must equal the Hall-on facility. It is recorded here, not required.

Compliance:
- The gate reads no Hall transport closure, screening candidate or withdrawn 0-D number.
- No architecture (`hall_only`, `rf_hall`, `ecr_hall`) is ranked or eliminated.
- P5 calibration nuisance is never an item.
- N4 is neither read nor modified.
- Nothing is registered in the governance files; the orchestrator does that.
