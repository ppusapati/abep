# O4 disposition matrix — builder and procedure (S12 machinery)

**Status: machinery only.** The official matrix does not exist yet and is not committed here. Trigger
`T_O4_DISPOSITION_MATRIX` (follow-on `fo_o4_disposition_matrix`) is **not ready**: 7 required escalation datasets from
attempt 2 are not yet scored (`hmslow` × 3, `hmshigh` × 3, `n2dication_nel_wang`). This lane does not claim that trigger.

## What the matrix is

It is an evidence table for the owner. It has one row per pre-registered O4 staged-sensitivity family × the baseline it is
compared against (`prereg/p5_n2_validation_criteria_v1.json` → `staged_sensitivities`):

| family | first stage vs | escalation combinations |
|---|---|---|
| `n2_n_exc_johnsonlow.toml` | `n2_n.toml` | `di_lower`, `nel_wang`, `di_lower_nel_wang` |
| `n2_n_rot_off.toml` | `n2_n.toml` | `di_lower`, `nel_wang`, `di_lower_nel_wang` |
| `n2_n_ndd_hmslow.toml` | `n2_n.toml` | `di_lower`, `nel_wang`, `di_lower_nel_wang` |
| `n2_n_ndd_hmshigh.toml` | `n2_n.toml` | `di_lower`, `nel_wang`, `di_lower_nel_wang` |
| `n2_n_n2dication.toml` | `n2_n_di_lower.toml` | `di_lower_nel_wang` |

Each row is read only from the frozen scored dataset. It gives:

- `trigger_fired`;
- run-level trigger counts: by kind (status / ΔI_d / ΔT), by point N1–N5 and by reading A/B;
- status transitions;
- member and candidate verdict changes (the last O4 clause);
- an **evidence-only** column (`evidence_only_for_owner`). The Johnson-low rows add the result of the verified Johnson-low
  assessment.

Every `owner_disposition` is `null`. **The builder decides no disposition.** Dispositions are owner decisions, recorded in
an `o4_dispositions_v1` file (`hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json`) and checked offline by
`abep_sim/hall_ensemble._check_o4`.

The official matrix also carries `o4_dispositions_feed`, a skeleton that conforms to `o4_dispositions_v1`:
- baselines, first-stage and escalation `scores_provenance_file`/`sha256` (paths relative to `hallthruster_bridge/`) and
  the scored `trigger_fired`;
- every owner field left empty (`disposition: null`, `cleared_for_admission: []`, `decided_by`/`decided_utc: null`).

`_check_o4` rejects the feed as emitted. It passes only once the owner has filled those fields and bound
`mandatory_decision_sha256` to the decision that the citing record uses.

The layout of the matrix is in `o4_disposition_matrix_schema_v1.json`.

## Procedure

1. **Status.** `python docs/o4/disposition_matrix/build_o4_disposition_matrix.py --status` prints the required, scored,
   missing and undetermined dataset ids. "Required" means the 5 first stages, plus every escalation of a first stage whose
   scored trigger fired. An escalation is "undetermined" while its first stage is unscored.
2. **Wait.** Wait until `missing` and `undetermined` are both empty, which means each attempt-2 escalation has been scored
   once through the standard `scripts/score_p5_n2_staged.py freeze|score` pipeline. Until then the official build exits
   with code 2 and lists the missing ids (`MatrixRefused`).
3. **Build.** `T_O4_DISPOSITION_MATRIX` must then be claimed through the ledger under the operating model. After that,
   `python docs/o4/disposition_matrix/build_o4_disposition_matrix.py` writes `o4_disposition_matrix_v1.json`.
   `--check` confirms that the file reproduces byte for byte.
4. **Owner.** The owner reads the matrix, writes the dispositions into a separate `o4_dispositions_v1` file based on the
   feed, and records who decided and when. The matrix itself is never edited by hand.

For testing only, `--preview --out PATH` writes a **PREVIEW** over whatever is scored (schema
`o4_evidence_matrix_preview_v1`, `"PREVIEW": true`, no dispositions feed). A preview is never committed as the matrix. The
builder refuses a preview filename that contains "disposition", and it refuses the official path.

## Verification performed on every scored dataset (any failure raises; there is no fallback)

- The raw `.jsonl.gz` sha256 and its canonical sha256 match the freeze manifest.
- The provenance input and output name these exact files, and the scores sha256 equals `output_sha256`.
- Mode is vacuum. `mandatory_reproduced` is true, and the mandatory statistics in the O4 scores equal the official v1
  scores.
- The dataset is bound to the v1 mandatory raw dataset and scores, the frozen scorer sha256 and the pre-registration lock.
- The baseline and family are the pre-registered ones. The chemistry config sha256 equals the propellant file.
- `o4_trigger_fired` equals the scored block.
- The frozen scorer (imported only after its sha256 matches) **recomputes `run_level_triggers` and `verdict_changes`
  exactly**.
- The registry cross-checks hold: the lane-registry O4 datasets equal the pre-registered configurations (5 + 13), and the
  `T_O4_DISPOSITION_MATRIX` prerequisites equal the 5 first stages.
- The Johnson-low assessment has a VERIFIED ledger event, its own checks all passed, and its four dataset hashes are
  identical to the ones verified here.

**Interrupted outputs are never read.** Every file access goes through a guard. The guard refuses
`hallthruster_bridge/validation/interrupted/**`, including through symlinks. The builder never lists a directory; each path
is constructed from the registry. Facility results are not read (O4: facility-only differences never trigger escalation).

## Scope

This is evidence for the O4 gate on admission of the ionization/discharge → acceleration/thrust block. It does not:
- change any criterion, tolerance, chemistry, transport parameter, pre-registration or campaign record;
- rewrite the v1 outcome (INCONCLUSIVE for all nine screening candidates, credible set ∅);
- put any screening candidate into the credible set.

Tests: `tests/test_o4_disposition_matrix.py`.
