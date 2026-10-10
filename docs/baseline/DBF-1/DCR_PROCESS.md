# DBF-1 design change control (DCR process)

Governing decision: A9.37 (`docs/decisions/OD_2026_10_08_A9_37_DBF_1_DESIGN_BASELINE_FREEZE.md`), verbatim rule:

> After DBF-1, no design value may change merely to improve M2 performance. Any change requires a formal DCR
> identifying the physical/evidence reason before rerun.

## What is under change control

Every item of `dbf1_v1.json` (`items[].id` = `DBF1-*`): its value, units, status, evidence class and uncertainty. The
selection rules (`selection_rules[]`) and the machine-readable subset `dbf1_config_v1.json` are under the same control.
`dbf1_lock_v1.json` pins all of them; a changed file without an approved DCR is refused by the harness (fail closed).

## What is not a design change (no DCR)

- **Input completion.** Supplying converged Hall envelope data (the A9.36 numerics investigation, then a registered
  envelope rerun under its own addendum) is an input completion, not a design change (A9.37 recorder note). The same
  holds for registered evidence that completes an input without changing a frozen value (a measured property of the
  frozen anode material, an admitted rate set). A host ICD that replaces a REFERENCE_PENDING_ICD value changes a frozen
  value and is therefore a DCR (below).
- **Reporting.** New sensitivities, new reports and additional quantities computed at the frozen design.

## What needs a DCR

- Any change of a frozen value, a selection rule or a selected candidate.
- Replacing a `REFERENCE_PENDING_ICD` value by the customer / host ICD (the reason is the ICD itself).
- Promoting a `FROZEN_ASSUMPTION` to a different value because new evidence contradicts it.

## A DCR record

A DCR is a JSON entry in a new register version (`dcr_register_v2.json`, ... ; `dcr_register_v1.json` is the empty
register at the freeze and is never edited). Required fields:

| field | content |
|---|---|
| `id` | `DCR-DBF1-NNN` |
| `date`, `requested_by`, `approved_by`, `approval_record` | approval is an owner decision record (or a coordinator ruling the owner has delegated), committed before any rerun |
| `items` | the `DBF1-*` ids changed, each with old value and new value |
| `physical_or_evidence_reason` | the physical / evidence reason, with sources (path + sha256, or citation + locator). "Improves M2 performance" is never a reason |
| `results_seen_before_request` | every M2 / M3 result the requester had seen (so the reason can be audited for post-hoc tuning) |
| `impact` | the items, addenda, run manifests and records affected; which M2 records become history |
| `new_baseline` | the new baseline version (DBF-1.1, DBF-2, ...) with its own files and lock |

## Rules

1. A DCR is approved and committed **before** any rerun that uses the changed value.
2. The previous baseline, its lock and every record computed on it stay immutable history.
3. A rerun after a DCR is a new run manifest pinning the new baseline lock; earlier M2 records are never rewritten.
4. Speed never weakens provenance, preregistration, conservation, determinism, model-domain checks or fail-closed
   evidence semantics (A9.29 sec. 14).
