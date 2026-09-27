# O4 disposition matrix: review for the owner

Follow-on `fo_o4_disposition_matrix` (trigger `T_O4_DISPOSITION_MATRIX`, kind `owner_decision_brief`). Built at base commit
`bca98651b3` from the official matrix `o4_disposition_matrix_v1.json` in this directory.

**Status: official matrix built, dispositions pending owner.** This document contains evidence only. No disposition is
recommended, and no owner field is pre-filled. The owner records the dispositions in a separate `o4_dispositions_v1` file
(`hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json`). This lane does not write that file.

## What O4 is and what it cannot do

- **O4 is sensitivity evidence.** Each row asks one question: how much do the P5-N2 v1 observables, run statuses and
  provisional verdicts move when one pre-registered chemistry choice is replaced by its staged sensitivity? The frozen
  transports are the same in both runs and nothing is retuned.
- It **cannot alter P5-N2 v1**. v1 stays **INCONCLUSIVE permanently**: all nine screening candidates are INCONCLUSIVE / NOT
  ELIGIBLE, and none is PROMOTABLE (`hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json`).
- The **credible set stays empty**. Nothing in this matrix moves a screening candidate into the credible set. Every
  FAIL_VALIDATION in the tables below is a counterfactual under a sensitivity chemistry. It is not a rejection recorded
  against the v1 result.
- Admission stays gated in two ways. First, `abep_sim/hall_ensemble._check_o4` needs a bound, owner-filled
  `o4_dispositions_v1` file. Second, `_check_admission` needs a PROMOTABLE decision, which in turn needs **genuinely new
  predictive evidence** that was not used in selection (CLAUDE.md; v2 Question A disposition A-NO, rule 2). Recording
  dispositions today enables no admission, because no decision lists a PROMOTABLE candidate.
- A disposition changes no criterion, tolerance, chemistry or transport parameter. The schema rule reads: "no criterion,
  tolerance, chemistry or transport parameter changes as a result of an O4 disposition (no retuning)".

## Milestones

- **Milestone A** (conditional selection): O4 is not needed. The matrix produces no absolute Hall numbers and implies none.
  It never delays hardware preparation (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`).
- **Milestone B** (physics-backed selection): this matrix supports B. It is the evidence behind the O4 dispositions, and
  `_check_o4` requires those dispositions before any Hall transport closure can enter the ensemble. B still needs three
  things: (1) the owner's dispositions recorded and bound to the admission's decision hash; (2) a closure that passes
  genuinely new predictive evidence; (3) the second lens where the operating model requires it.
- **Milestone C** (proposal/PDR freeze): O4 feeds C only through B.

## How the official matrix was produced and checked

| step | result |
|---|---|
| `python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --status` | `missing: []`, `undetermined: []`, `not_required_trigger_not_fired: []`; 18 required = 18 scored (5 first stages + 13 escalations) |
| `python docs/o4/disposition_matrix/build_o4_disposition_matrix.py` | wrote `o4_disposition_matrix_v1.json`; builder logic unchanged |
| `python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --check` | `CHECK OK` (byte-for-byte reproduction) |
| provenance block | `all_checks_passed: true`, 432 checks |

For every one of the 18 scored datasets, the builder checks:
- the raw `.jsonl.gz` and canonical sha256 against the freeze manifest;
- the provenance input/output binding, and the scores sha256 against `output_sha256`;
- that the mode is vacuum;
- that `mandatory_reproduced` is true and the mandatory statistics equal the official v1 scores;
- the binding to the v1 mandatory raw dataset and scores, the frozen scorer sha256 and the pre-registration lock;
- that the baseline and family are the pre-registered ones;
- the chemistry config sha256 against the propellant file.

The frozen scorer then **recomputes `run_level_triggers` and `verdict_changes` exactly**.

Every row binds its own `scores_provenance_file` and `scores_provenance_sha256`. Table 1 shows the first 12 hex digits; the
matrix holds the full value.

Interrupted attempt directories (`hallthruster_bridge/validation/interrupted/**`) are never read. Every access goes
through the builder's guard, which also refuses symlinks. `tests/test_o4_disposition_matrix.py` checks the access log of
an official build.

`o4_dispositions_feed` leaves every owner field empty:
- every `disposition` is `null`;
- `cleared_for_admission` is `[]`;
- `decided_by` and `decided_utc` are `null`;
- `mandatory_decision_sha256` is `null`, and so is every other `*decision_sha256`.

The mandatory decision file's sha256 appears nowhere in the matrix.

Ledger: this lane cannot write `docs/orchestration/trigger_ledger_v2.jsonl` or `fired_triggers.jsonl`. So the
CLAIMED/LAUNCHED/VERIFIED records for `T_O4_DISPOSITION_MATRIX` are left to the orchestrator, under the operating model.

## How to read the tables

- **Row** = one pre-registered staged sensitivity *family* × the primary chemistry *baseline* it is compared against.
  Johnson-low, rotational-off, HMS ×0.5 and HMS ×1.3 run against `n2_n` (first stage) and then `n2_n_di_lower`,
  `n2_n_nel_wang` and `n2_n_di_lower_nel_wang` (escalations). Molecular N₂²⁺ runs against `n2_n_di_lower`, then
  `n2_n_di_lower_nel_wang`. Each row covers 9 screening candidates × 30 cases = 270 vacuum runs.
- **Trigger readings** are counted separately for reading A and reading B (beam-efficiency divergence readings). There
  are three kinds, all from the pre-registered O4 rule:
  - `status`: a run status changes;
  - `dI_d`: |ΔI_d| ≥ 0.075 × I_d,target;
  - `dT`: |ΔT_axial| ≥ 0.5 × T_tolerance (2.6 / 2.8 / 2.8 mN at N1 / N2 / N3).
  A `dT` trigger exists only at N1–N3, because the pre-registration defines thrust tolerances only there.
- **Verdict changes** are counterfactual (`scripts/score_p5_n2_campaign.py` `verdict_change`, frozen). The scorer forms the
  provisional verdicts from the full mandatory vacuum set (all four primary chemistries). It then forms them again with
  only the row's baseline chemistry replaced by the sensitivity. A *member* is one layer-1 P5 calibration-nuisance
  combination: registration, historical coil shape and beam-efficiency reading. These members are not Vyovrinda design
  variables.
- In the v1 decision all nine candidates are `INCONCLUSIVE / NOT ELIGIBLE`. That is the "from" side of every
  candidate-level change.

## Evidence tables (regenerated from the official matrix; do not edit by hand)

<!-- BEGIN GENERATED TABLES: python tests/test_o4_disposition_matrix.py --print-review-tables -->
#### Table 1 - per family x baseline: trigger, run-level trigger counts, verdict changes

| # | family | baseline | stage | trigger_fired | runs with >= 1 trigger / runs | trigger readings status / dI_d / dT | runs with a status change | candidate verdict changes | member verdict changes | scores_provenance sha256 (12) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | n2_n_exc_johnsonlow | n2_n | first_stage | True | 79 / 270 | 61 / 64 / 96 | 31 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 4 | `dc902155f740` |
| 2 | n2_n_exc_johnsonlow | n2_n_di_lower | escalation | True | 72 / 270 | 52 / 68 / 89 | 26 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 6 | `8a1e81095ec4` |
| 3 | n2_n_exc_johnsonlow | n2_n_nel_wang | escalation | True | 62 / 270 | 24 / 76 / 83 | 12 | none | 0 | `a0792fe82c29` |
| 4 | n2_n_exc_johnsonlow | n2_n_di_lower_nel_wang | escalation | True | 78 / 270 | 45 / 78 / 89 | 23 | none | 4 | `07ed37f178af` |
| 5 | n2_n_rot_off | n2_n | first_stage | True | 120 / 270 | 80 / 148 / 141 | 41 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 6 | `d23567cf791e` |
| 6 | n2_n_rot_off | n2_n_di_lower | escalation | True | 128 / 270 | 93 / 150 / 147 | 47 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 6 | `36db0cf05df3` |
| 7 | n2_n_rot_off | n2_n_nel_wang | escalation | True | 114 / 270 | 83 / 142 / 137 | 42 | sgb-screen-06: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION; sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 8 | `ab864d3efd97` |
| 8 | n2_n_rot_off | n2_n_di_lower_nel_wang | escalation | True | 110 / 270 | 88 / 140 / 125 | 45 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 8 | `5a69025c270c` |
| 9 | n2_n_ndd_hmslow | n2_n | first_stage | True | 66 / 270 | 50 / 30 / 68 | 25 | none | 2 | `f806017e6622` |
| 10 | n2_n_ndd_hmslow | n2_n_di_lower | escalation | True | 50 / 270 | 34 / 38 / 54 | 17 | none | 2 | `6c39c96c4cd3` |
| 11 | n2_n_ndd_hmslow | n2_n_nel_wang | escalation | True | 55 / 270 | 40 / 24 / 61 | 20 | none | 2 | `b37f5c3b35ca` |
| 12 | n2_n_ndd_hmslow | n2_n_di_lower_nel_wang | escalation | True | 53 / 270 | 36 / 32 / 59 | 18 | none | 4 | `d0335608c2b3` |
| 13 | n2_n_ndd_hmshigh | n2_n | first_stage | True | 53 / 270 | 38 / 22 / 60 | 19 | sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 4 | `b6180309f62b` |
| 14 | n2_n_ndd_hmshigh | n2_n_di_lower | escalation | True | 51 / 270 | 42 / 22 / 57 | 21 | none | 4 | `392e1142424f` |
| 15 | n2_n_ndd_hmshigh | n2_n_nel_wang | escalation | True | 28 / 270 | 22 / 18 / 38 | 11 | none | 0 | `9a29b7464d1c` |
| 16 | n2_n_ndd_hmshigh | n2_n_di_lower_nel_wang | escalation | True | 34 / 270 | 30 / 16 / 32 | 15 | none | 2 | `750a9d02a1a4` |
| 17 | n2_n_n2dication | n2_n_di_lower | first_stage | True | 188 / 270 | 83 / 214 / 235 | 42 | sgb-screen-05: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION; sgb-screen-09: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 12 | `befaf2a7b58a` |
| 18 | n2_n_n2dication | n2_n_di_lower_nel_wang | escalation | True | 184 / 270 | 69 / 222 / 254 | 35 | sgb-screen-05: INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 14 | `e5468f7cf8d0` |

#### Table 2 - run-level trigger readings by point (status / dI_d / dT; readings A and B counted separately)

| # | family | baseline | N1 | N2 | N3 | N4 | N5 |
|---|---|---|---|---|---|---|---|
| 1 | n2_n_exc_johnsonlow | n2_n | 24 / 20 / 30 | 8 / 12 / 30 | 13 / 14 / 36 | 8 / 8 / 0 | 8 / 10 / 0 |
| 2 | n2_n_exc_johnsonlow | n2_n_di_lower | 14 / 24 / 28 | 8 / 14 / 23 | 10 / 14 / 38 | 12 / 6 / 0 | 8 / 10 / 0 |
| 3 | n2_n_exc_johnsonlow | n2_n_nel_wang | 4 / 18 / 30 | 6 / 18 / 23 | 8 / 18 / 30 | 4 / 14 / 0 | 2 / 8 / 0 |
| 4 | n2_n_exc_johnsonlow | n2_n_di_lower_nel_wang | 12 / 20 / 26 | 6 / 14 / 23 | 11 / 16 / 40 | 8 / 16 / 0 | 8 / 12 / 0 |
| 5 | n2_n_rot_off | n2_n | 20 / 52 / 54 | 14 / 40 / 54 | 10 / 18 / 33 | 20 / 16 / 0 | 16 / 22 / 0 |
| 6 | n2_n_rot_off | n2_n_di_lower | 24 / 44 / 52 | 14 / 40 / 52 | 15 / 26 / 43 | 24 / 18 / 0 | 16 / 22 / 0 |
| 7 | n2_n_rot_off | n2_n_nel_wang | 26 / 50 / 51 | 12 / 40 / 46 | 11 / 18 / 40 | 16 / 18 / 0 | 18 / 16 / 0 |
| 8 | n2_n_rot_off | n2_n_di_lower_nel_wang | 22 / 46 / 48 | 16 / 38 / 42 | 18 / 22 / 35 | 16 / 16 / 0 | 16 / 18 / 0 |
| 9 | n2_n_ndd_hmslow | n2_n | 14 / 6 / 6 | 10 / 6 / 24 | 12 / 4 / 38 | 8 / 6 / 0 | 6 / 8 / 0 |
| 10 | n2_n_ndd_hmslow | n2_n_di_lower | 8 / 4 / 8 | 6 / 10 / 13 | 6 / 12 / 33 | 8 / 6 / 0 | 6 / 6 / 0 |
| 11 | n2_n_ndd_hmslow | n2_n_nel_wang | 14 / 2 / 8 | 8 / 6 / 21 | 14 / 4 / 32 | 2 / 6 / 0 | 2 / 6 / 0 |
| 12 | n2_n_ndd_hmslow | n2_n_di_lower_nel_wang | 8 / 0 / 4 | 12 / 12 / 20 | 12 / 8 / 35 | 0 / 6 / 0 | 4 / 6 / 0 |
| 13 | n2_n_ndd_hmshigh | n2_n | 16 / 4 / 8 | 2 / 6 / 20 | 6 / 4 / 32 | 8 / 4 / 0 | 6 / 4 / 0 |
| 14 | n2_n_ndd_hmshigh | n2_n_di_lower | 8 / 4 / 8 | 12 / 8 / 14 | 12 / 4 / 35 | 6 / 2 / 0 | 4 / 4 / 0 |
| 15 | n2_n_ndd_hmshigh | n2_n_nel_wang | 8 / 6 / 6 | 8 / 4 / 10 | 4 / 6 / 22 | 2 / 2 / 0 | 0 / 0 / 0 |
| 16 | n2_n_ndd_hmshigh | n2_n_di_lower_nel_wang | 8 / 4 / 7 | 6 / 4 / 2 | 8 / 2 / 23 | 6 / 2 / 0 | 2 / 4 / 0 |
| 17 | n2_n_n2dication | n2_n_di_lower | 20 / 34 / 74 | 22 / 42 / 80 | 13 / 50 / 81 | 16 / 46 / 0 | 12 / 42 / 0 |
| 18 | n2_n_n2dication | n2_n_di_lower_nel_wang | 20 / 38 / 84 | 14 / 40 / 85 | 15 / 56 / 85 | 10 / 50 / 0 | 10 / 38 / 0 |

#### Table 3 - status transitions (baseline status -> sensitivity status, number of runs, per reading)

| # | family | baseline | reading A | reading B |
|---|---|---|---|---|
| 1 | n2_n_exc_johnsonlow | n2_n | FAIL_VALIDATION -> OUT_OF_DOMAIN: 9; FAIL_VALIDATION -> PASS: 1; OUT_OF_DOMAIN -> FAIL_VALIDATION: 13; OUT_OF_DOMAIN -> PASS: 3; PASS -> OUT_OF_DOMAIN: 4 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 9; FAIL_VALIDATION -> PASS: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 13; OUT_OF_DOMAIN -> PASS: 3; PASS -> OUT_OF_DOMAIN: 4 |
| 2 | n2_n_exc_johnsonlow | n2_n_di_lower | FAIL_VALIDATION -> OUT_OF_DOMAIN: 9; FAIL_VALIDATION -> PASS: 1; OUT_OF_DOMAIN -> FAIL_VALIDATION: 11; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 3 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 9; FAIL_VALIDATION -> PASS: 1; OUT_OF_DOMAIN -> FAIL_VALIDATION: 11; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 3 |
| 3 | n2_n_exc_johnsonlow | n2_n_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; FAIL_VALIDATION -> PASS: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; FAIL_VALIDATION -> PASS: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 1 |
| 4 | n2_n_exc_johnsonlow | n2_n_di_lower_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; FAIL_VALIDATION -> PASS: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 12; OUT_OF_DOMAIN -> PASS: 1; PASS -> OUT_OF_DOMAIN: 2 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; FAIL_VALIDATION -> PASS: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 12; OUT_OF_DOMAIN -> PASS: 1; PASS -> OUT_OF_DOMAIN: 2 |
| 5 | n2_n_rot_off | n2_n | FAIL_VALIDATION -> OUT_OF_DOMAIN: 18; FAIL_VALIDATION -> PASS: 8; OUT_OF_DOMAIN -> FAIL_VALIDATION: 9; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 5 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 19; FAIL_VALIDATION -> PASS: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 9; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 4 |
| 6 | n2_n_rot_off | n2_n_di_lower | FAIL_VALIDATION -> OUT_OF_DOMAIN: 20; FAIL_VALIDATION -> PASS: 7; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> PASS: 1; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 4 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 21; FAIL_VALIDATION -> PASS: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> PASS: 1; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 3 |
| 7 | n2_n_rot_off | n2_n_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 17; FAIL_VALIDATION -> PASS: 7; OUT_OF_DOMAIN -> FAIL_VALIDATION: 15; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 17; FAIL_VALIDATION -> PASS: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 15; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 |
| 8 | n2_n_rot_off | n2_n_di_lower_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 20; FAIL_VALIDATION -> PASS: 7; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> NUMERICAL_FAILURE: 1; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 2 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 20; FAIL_VALIDATION -> PASS: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> NUMERICAL_FAILURE: 1; PASS -> OUT_OF_DOMAIN: 2 |
| 9 | n2_n_ndd_hmslow | n2_n | FAIL_VALIDATION -> OUT_OF_DOMAIN: 13; OUT_OF_DOMAIN -> FAIL_VALIDATION: 8; OUT_OF_DOMAIN -> PASS: 1; PASS -> OUT_OF_DOMAIN: 3 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 13; OUT_OF_DOMAIN -> FAIL_VALIDATION: 9; PASS -> OUT_OF_DOMAIN: 3 |
| 10 | n2_n_ndd_hmslow | n2_n_di_lower | FAIL_VALIDATION -> OUT_OF_DOMAIN: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 3 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 6; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 3 |
| 11 | n2_n_ndd_hmslow | n2_n_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 14; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 |
| 12 | n2_n_ndd_hmslow | n2_n_di_lower_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 10; OUT_OF_DOMAIN -> FAIL_VALIDATION: 7; PASS -> OUT_OF_DOMAIN: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 10; OUT_OF_DOMAIN -> FAIL_VALIDATION: 7; PASS -> OUT_OF_DOMAIN: 1 |
| 13 | n2_n_ndd_hmshigh | n2_n | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; OUT_OF_DOMAIN -> FAIL_VALIDATION: 8; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 4 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; OUT_OF_DOMAIN -> FAIL_VALIDATION: 8; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 4 |
| 14 | n2_n_ndd_hmshigh | n2_n_di_lower | FAIL_VALIDATION -> OUT_OF_DOMAIN: 8; OUT_OF_DOMAIN -> FAIL_VALIDATION: 9; OUT_OF_DOMAIN -> PASS: 2; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 8; OUT_OF_DOMAIN -> FAIL_VALIDATION: 8; OUT_OF_DOMAIN -> PASS: 3; PASS -> FAIL_VALIDATION: 1; PASS -> OUT_OF_DOMAIN: 1 |
| 15 | n2_n_ndd_hmshigh | n2_n_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 1; PASS -> FAIL_VALIDATION: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 6; OUT_OF_DOMAIN -> PASS: 1; PASS -> FAIL_VALIDATION: 1 |
| 16 | n2_n_ndd_hmshigh | n2_n_di_lower_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 10; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 2; OUT_OF_DOMAIN -> FAIL_VALIDATION: 10; OUT_OF_DOMAIN -> PASS: 2; PASS -> OUT_OF_DOMAIN: 1 |
| 17 | n2_n_n2dication | n2_n_di_lower | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 27; OUT_OF_DOMAIN -> PASS: 7; PASS -> FAIL_VALIDATION: 3; PASS -> OUT_OF_DOMAIN: 2 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 3; OUT_OF_DOMAIN -> FAIL_VALIDATION: 28; OUT_OF_DOMAIN -> PASS: 6; PASS -> FAIL_VALIDATION: 2; PASS -> OUT_OF_DOMAIN: 2 |
| 18 | n2_n_n2dication | n2_n_di_lower_nel_wang | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; OUT_OF_DOMAIN -> FAIL_VALIDATION: 23; OUT_OF_DOMAIN -> NUMERICAL_FAILURE: 1; OUT_OF_DOMAIN -> PASS: 4; PASS -> FAIL_VALIDATION: 2 | FAIL_VALIDATION -> OUT_OF_DOMAIN: 5; OUT_OF_DOMAIN -> FAIL_VALIDATION: 24; OUT_OF_DOMAIN -> NUMERICAL_FAILURE: 1; OUT_OF_DOMAIN -> PASS: 3; PASS -> FAIL_VALIDATION: 1 |

#### Table 4 - candidate-level verdict changes (counterfactual: one mandatory chemistry replaced by the sensitivity)

| candidate | v1 verdict -> counterfactual verdict | rows | family x baseline |
|---|---|---|---|
| sgb-screen-05 | INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 2 | n2_n_n2dication x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-06 | INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 1 | n2_n_rot_off x n2_n_nel_wang |
| sgb-screen-09 | INCONCLUSIVE / NOT ELIGIBLE -> FAIL_VALIDATION | 8 | n2_n_exc_johnsonlow x n2_n; n2_n_exc_johnsonlow x n2_n_di_lower; n2_n_rot_off x n2_n; n2_n_rot_off x n2_n_di_lower; n2_n_rot_off x n2_n_nel_wang; n2_n_rot_off x n2_n_di_lower_nel_wang; n2_n_ndd_hmshigh x n2_n; n2_n_n2dication x n2_n_di_lower |

Candidates with no candidate-level change in any row: sgb-screen-01, sgb-screen-02, sgb-screen-03, sgb-screen-04, sgb-screen-07, sgb-screen-08.
Candidates with no member-level change in any row: sgb-screen-03.

#### Table 5 - member-level verdict changes (member key = P5 registration, historical coil shape, beam-efficiency reading)

| candidate | member (registration, coil) | verdict change | readings | rows | family x baseline |
|---|---|---|---|---|---|
| sgb-screen-01 | L32-exit, 3p0kW | INCONCLUSIVE -> FAIL | A/B | 3 | n2_n_rot_off x n2_n_di_lower_nel_wang; n2_n_n2dication x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-02 | L32-anode, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 5 | n2_n_exc_johnsonlow x n2_n_di_lower_nel_wang; n2_n_ndd_hmshigh x n2_n_di_lower; n2_n_ndd_hmshigh x n2_n_di_lower_nel_wang; n2_n_n2dication x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-04 | L32-exit, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 2 | n2_n_exc_johnsonlow x n2_n_di_lower; n2_n_ndd_hmslow x n2_n_nel_wang |
| sgb-screen-05 | L32-exit, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 2 | n2_n_n2dication x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-05 | L32-exit, 3p0kW | FAIL -> INCONCLUSIVE | A/B | 3 | n2_n_exc_johnsonlow x n2_n_di_lower; n2_n_ndd_hmslow x n2_n_di_lower; n2_n_ndd_hmshigh x n2_n_di_lower |
| sgb-screen-06 | L32-exit, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 1 | n2_n_rot_off x n2_n_nel_wang |
| sgb-screen-06 | L32-exit, 3p0kW | INCONCLUSIVE -> FAIL | A/B | 4 | n2_n_rot_off x n2_n; n2_n_rot_off x n2_n_nel_wang; n2_n_rot_off x n2_n_di_lower_nel_wang; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-07 | L32-exit, 3p0kW | INCONCLUSIVE -> FAIL | A/B | 1 | n2_n_n2dication x n2_n_di_lower |
| sgb-screen-08 | L32-anode, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 2 | n2_n_rot_off x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-08 | L32-exit, 3p0kW | INCONCLUSIVE -> FAIL | A/B | 5 | n2_n_rot_off x n2_n; n2_n_rot_off x n2_n_di_lower; n2_n_rot_off x n2_n_nel_wang; n2_n_rot_off x n2_n_di_lower_nel_wang; n2_n_n2dication x n2_n_di_lower |
| sgb-screen-08 | L38-hist, 3p0kW | FAIL -> INCONCLUSIVE | A/B | 3 | n2_n_exc_johnsonlow x n2_n; n2_n_ndd_hmslow x n2_n; n2_n_ndd_hmshigh x n2_n |
| sgb-screen-09 | L32-exit, 1p6kW | INCONCLUSIVE -> FAIL | A/B | 10 | n2_n_exc_johnsonlow x n2_n; n2_n_exc_johnsonlow x n2_n_di_lower; n2_n_rot_off x n2_n; n2_n_rot_off x n2_n_di_lower; n2_n_rot_off x n2_n_nel_wang; n2_n_rot_off x n2_n_di_lower_nel_wang; n2_n_ndd_hmslow x n2_n_di_lower_nel_wang; n2_n_ndd_hmshigh x n2_n; n2_n_n2dication x n2_n_di_lower; n2_n_n2dication x n2_n_di_lower_nel_wang |
| sgb-screen-09 | L32-exit, 3p0kW | FAIL -> INCONCLUSIVE | A/B | 3 | n2_n_exc_johnsonlow x n2_n_di_lower_nel_wang; n2_n_ndd_hmslow x n2_n_di_lower_nel_wang; n2_n_n2dication x n2_n_di_lower_nel_wang |

Counterfactual verdicts reached in any row: FAIL, FAIL_VALIDATION, INCONCLUSIVE.

#### Table 6 - per family totals over its rows (trigger readings; readings A and B counted separately)

| family | rows | rows with trigger_fired | status | dI_d | dT | status readings crossing OUT_OF_DOMAIN | FAIL_VALIDATION <-> PASS | other status readings | candidates with a candidate-level change | rows with >= 1 member change |
|---|---|---|---|---|---|---|---|---|---|---|
| n2_n_exc_johnsonlow | 4 | 4 | 182 | 286 | 357 | 168 | 14 | 0 | sgb-screen-09 | 3 |
| n2_n_rot_off | 4 | 4 | 344 | 580 | 550 | 286 | 58 | 0 | sgb-screen-06, sgb-screen-09 | 4 |
| n2_n_ndd_hmslow | 4 | 4 | 160 | 124 | 242 | 160 | 0 | 0 | none | 4 |
| n2_n_ndd_hmshigh | 4 | 4 | 132 | 78 | 187 | 128 | 4 | 0 | sgb-screen-09 | 3 |
| n2_n_n2dication | 2 | 2 | 152 | 436 | 489 | 144 | 8 | 0 | sgb-screen-05, sgb-screen-09 | 2 |
| all | 18 | 18 | 970 | 1504 | 1825 | 886 | 84 | 0 | sgb-screen-05, sgb-screen-06, sgb-screen-09 | 16 |

#### Table 7 - verified Johnson-low assessment (`docs/o4/johnsonlow_assessment/johnsonlow_assessment_v1.json`, sha256 `b275e9ef47df`, ledger VERIFIED at `a4f82a1869fe`)

- mode: `TAIL_AND_BOUNDARY_ON_ALL_FOUR`; material_on_every_primary_combination: `True`
- class counts: BASELINE_DEPENDENT_SIGN 2, SIGN_PERSISTS_BELOW_THRESHOLD 12
- observables that persist (|median r| >= 1 on all four): none
- sign consistent below threshold: dI@N1, dI@N2, dI@N3, dI@N4, dI@N5, dI@pooled, dT_A@N1, dT_A@N2, dT_A@pooled, dT_B@N1, dT_B@N2, dT_B@pooled
- baseline-dependent sign: dT_A@N3, dT_B@N3
- status changes on every combination: A `True`, B `True`; verdict changes on every combination: `False`; common to all four: `False`

| baseline | runs with any trigger | runs with a status change | of which across OUT_OF_DOMAIN | pairs dI >= threshold | pairs dT_A >= threshold | pairs dT_B >= threshold | pairs with thrust |
|---|---|---|---|---|---|---|---|
| n2_n | 79 | 31 | 29 | 32 | 47 | 49 | 162 |
| n2_n_di_lower | 72 | 26 | 25 | 34 | 44 | 45 | 162 |
| n2_n_di_lower_nel_wang | 78 | 23 | 20 | 39 | 44 | 45 | 162 |
| n2_n_nel_wang | 62 | 12 | 10 | 38 | 40 | 43 | 162 |

> Assessment summary (quoted): The pre-registered O4 trigger fires on all four primary combinations, but through a minority of runs (individual large deltas and status changes; 84 of 92 status-changed runs cross the OUT_OF_DOMAIN boundary). No observable shows a median shift at or above the O4 threshold on any combination; the median I_d shift is positive on all four at every point; the median shift changes sign with the baseline at dT_A@N3, dT_B@N3.
>
> What this does not mean (quoted): a numerical effect, however large or persistent, is not experimental support for Johnson 2005 over Su 2021 below 20 eV; it measures how much the P5-N2 observables depend on that choice.

#### Table 8 - owner fields of the dispositions feed (all empty in the matrix; filled only in a separate o4_dispositions_v1 file)

| field | covers matrix rows (Table 1 #) | first stage scores_provenance sha256 (12) | escalations bound | value in feed |
|---|---|---|---|---|
| `sensitivities.n2_n_exc_johnsonlow.toml.disposition` | 1, 2, 3, 4 | `dc902155f740` | 3 | null |
| `sensitivities.n2_n_n2dication.toml.disposition` | 17, 18 | `befaf2a7b58a` | 1 | null |
| `sensitivities.n2_n_ndd_hmshigh.toml.disposition` | 13, 14, 15, 16 | `b6180309f62b` | 3 | null |
| `sensitivities.n2_n_ndd_hmslow.toml.disposition` | 9, 10, 11, 12 | `f806017e6622` | 3 | null |
| `sensitivities.n2_n_rot_off.toml.disposition` | 5, 6, 7, 8 | `d23567cf791e` | 3 | null |
| `cleared_for_admission` | all | - | - | [] |
| `decided_by` | all | - | - | null |
| `decided_utc` | all | - | - | null |
| `mandatory_decision_sha256` | all | - | - | null |
<!-- END GENERATED TABLES -->

## Evidence by family (facts from the tables above)

- **Johnson-low electronic excitation (`n2_n_exc_johnsonlow`, rows 1–4).**
  - The trigger fired on all four primary combinations: 62–79 of 270 runs carry a trigger, and 12–31 runs change status.
  - sgb-screen-09 goes INCONCLUSIVE / NOT ELIGIBLE → FAIL_VALIDATION against `n2_n` and `n2_n_di_lower` only.
  - Against `n2_n_nel_wang` there is no verdict change of any kind: the trigger fires through run-level readings only.
  - Table 7 gives the verified assessment. Mode `TAIL_AND_BOUNDARY_ON_ALL_FOUR`: no observable has a median shift at or
    above the O4 threshold on any combination, and 84 of 92 status-changed runs cross the OUT_OF_DOMAIN boundary.
  - Johnson-low remains a sensitivity. v2 Question B, which asks which excitation representation is supportable, is
    blocked by the Question A disposition A-NO (`docs/v2/question_a/QUESTION_A_DISPOSITION.json`).
- **Rotational excitation off (`n2_n_rot_off`, rows 5–8).**
  - This family has the second-largest trigger volume: 110–128 runs per row. It also has the most FAIL_VALIDATION ↔ PASS
    status readings (58 of the 84 over all rows).
  - sgb-screen-09 changes at candidate level in all four rows. sgb-screen-06 changes only against `n2_n_nel_wang`.
  - At member level the changes concentrate on L32-exit members.
  - This branch is the pre-registered lower-bound sensitivity. The owner decided on 2026-09-26 that rotational excitation
    stays on in the nominal set.
- **HMS ×0.5 direct N → N²⁺ (`n2_n_ndd_hmslow`, rows 9–12).**
  - There is no candidate-level change in any row.
  - Each row has 2–4 member-level changes.
  - All 160 status readings in the family cross the OUT_OF_DOMAIN boundary; none is FAIL_VALIDATION ↔ PASS.
- **HMS ×1.3 direct N → N²⁺ (`n2_n_ndd_hmshigh`, rows 13–16).**
  - sgb-screen-09 changes at candidate level only against `n2_n`.
  - Against `n2_n_nel_wang` there is no verdict change of any kind: 28 runs carry a trigger, the lowest count in the matrix.
- **Molecular N₂²⁺ (`n2_n_n2dication`, rows 17–18; defined only on DI-lower).**
  - This family has the largest trigger volume: 188 and 184 of 270 runs, and 436 `dI_d` plus 489 `dT` readings over two
    rows.
  - Candidate-level changes: sgb-screen-05 and sgb-screen-09 against `n2_n_di_lower`, and sgb-screen-05 alone against
    `n2_n_di_lower_nel_wang`.
  - Example (row 18, `n2dication_nel_wang`): sgb-screen-05 goes INCONCLUSIVE / NOT ELIGIBLE → FAIL_VALIDATION. This is a
    counterfactual under a sensitivity chemistry, namely the uncertainty variant N₂²⁺ in place of `n2_n_di_lower_nel_wang`.
    It is not a v1 result, and it does not reject sgb-screen-05. v1 stays INCONCLUSIVE.
  - Row 18 has the most member-level changes (14).

## Cross-family patterns (evidence only)

- **Every row fired.** The trigger fired in 18 of 18 rows, so every escalation the O4 rule requires exists and is scored.
  Table 8 shows the feed binding each of them.
- **Which observables drive the triggers.** Over all rows there are 1825 `dT`, 1504 `dI_d` and 970 `status` trigger
  readings. `dT` appears only at N1–N3. Of the status readings:
  - 886 of 970 involve the OUT_OF_DOMAIN boundary, the non-scoreable status of the run-status rule
    (`hallthruster_bridge/prereg/p5_n2_run_status_rule_v1.json`);
  - 84 are FAIL_VALIDATION ↔ PASS: 67 FAIL_VALIDATION → PASS and 17 PASS → FAIL_VALIDATION, summed over readings A and B;
  - 2 rows show OUT_OF_DOMAIN → NUMERICAL_FAILURE: rows 8 and 18, one run each per reading.
- **Candidate-level changes.**
  - Only three candidates change: sgb-screen-05, sgb-screen-06 and sgb-screen-09. They move only from INCONCLUSIVE / NOT
    ELIGIBLE to FAIL_VALIDATION.
  - sgb-screen-09 changes in 8 of 18 rows across four families; the exception is HMS ×0.5. sgb-screen-05 changes only
    under N₂²⁺. sgb-screen-06 changes only under rotational-off × `n2_n_nel_wang`.
  - No counterfactual verdict in any row reaches PROMOTABLE (candidate) or PASS (member). The verdicts reached are FAIL,
    FAIL_VALIDATION and INCONCLUSIVE.
- **Member-level changes.**
  - Every member change is identical under readings A and B.
  - sgb-screen-03 has no change of any kind in any row.
  - Most changes are INCONCLUSIVE → FAIL, and most of those are on L32-exit members.
  - Three FAIL → INCONCLUSIVE patterns each appear against exactly one baseline, across three families:
    - sgb-screen-05 L32-exit, 3p0kW against `n2_n_di_lower`;
    - sgb-screen-08 L38-hist, 3p0kW against `n2_n`;
    - sgb-screen-09 L32-exit, 3p0kW against `n2_n_di_lower_nel_wang`.
  - These are descriptive regularities of the frozen scores and are not interpreted here.
- **Where the effect depends on the chemistry combination.** In every family except HMS ×0.5, the set of candidate-level
  changes differs between baseline combinations. HMS ×0.5 has an empty set in all four rows. No candidate-level change is common to all rows of a family, except
  sgb-screen-09 under rotational-off and sgb-screen-05 under N₂²⁺.

## Decisions for the owner (not pre-filled, not recommended)

No disposition is recommended here, and no field below has a suggested value.

The dispositions schema defines **no enumerated set of disposition values**. For each sensitivity the only allowed-value
definition is the quoted field description "the owner's recorded disposition (non-empty text)". `_check_o4` accepts any
non-empty string, so the wording of each disposition is entirely the owner's. The owner decides, in a separate
`o4_dispositions_v1` file based on `o4_dispositions_feed`:

| decision | covers rows (Table 1) | schema definition (quoted) |
|---|---|---|
| `sensitivities.n2_n_exc_johnsonlow.toml.disposition` | 1–4 | "the owner's recorded disposition (non-empty text)" |
| `sensitivities.n2_n_rot_off.toml.disposition` | 5–8 | "the owner's recorded disposition (non-empty text)" |
| `sensitivities.n2_n_ndd_hmslow.toml.disposition` | 9–12 | "the owner's recorded disposition (non-empty text)" |
| `sensitivities.n2_n_ndd_hmshigh.toml.disposition` | 13–16 | "the owner's recorded disposition (non-empty text)" |
| `sensitivities.n2_n_n2dication.toml.disposition` | 17–18 | "the owner's recorded disposition (non-empty text)" |
| `cleared_for_admission` | all | "list of ensemble_member_ids the owner clears for admission after the O4 dispositions" |
| `decided_by` | all | "who decided" |
| `decided_utc` | all | "ISO time" |
| `mandatory_decision_sha256` | all | "sha256 of the mandatory-vacuum decision file the admission cites" |

`baseline`, `trigger_fired`, `first_stage` and `escalations` are already in the feed, bound to the scored files. They are
not owner choices. `_check_o4` re-reads `trigger_fired` from the scored files and rejects any mismatch.

The disposition is per sensitivity family, so one text covers all of that family's rows (first stage and escalations).
Per row, the owner needs the facts in Tables 1–5 for those rows. The matrix itself (`owner_disposition: null` in every row
and family) is never edited by hand.

Binding: `mandatory_decision_sha256` must equal the `decision_sha256` of the admission record that cites the dispositions
file. No such admission record can exist today, because no candidate is PROMOTABLE.

## Reproduce

```
python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --status
python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --check
python tests/test_o4_disposition_matrix.py --print-review-tables
python -m pytest -q tests/test_o4_disposition_matrix.py
```
