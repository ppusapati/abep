# LAYER-SEPARATION OWNER DECISIONS (A9.22) — verbatim record, 2026-10-03

Recorded verbatim from the owner's message of 2026-10-03 (session chat), answering items G1-G9 of the
requirements / configuration / physics / assessment separation audit (same session). The owner's architecture-separation
instruction of the same day (four-layer separation, no-physics-change rule, simulation input contract, staged migration)
is the governing directive; this record carries the owner's answers. Machine-readable companion:
`OD_2026_10_03_A9_22_layer_separation_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

1. Mission-life basis — use 26,280 h.
Freeze 26,280 h as the authoritative mission-duration basis for mission-integrated calculations.
Replace active uses of 26,000 h with 26,280 h through a governed migration.
Keep 15,000 h only where it represents an explicitly separate thruster/subsystem firing-life assumption, not as the mission duration.
Therefore:

* mission duration = `26,280 h`
* mission-integrated Xe accounting = `26,280 h` unless a separately defined duty/firing profile legitimately reduces actual firing time
* AO fluence / life exposure = `26,280 h`
* mission-integrated quantities use the same basis
* `15,000 h` must be explicitly labelled as a subsystem firing/life assumption if retained

Do not silently change golden results. Update affected Xe mass, MEV, fluence and regression outputs under a separately recorded governed baseline change.
2. C-DRAG-RFP — choose Option 1 now.
Keep `C-DRAG-RFP` as a generation filter sourced from the frozen engineering-constraints snapshot.
This preserves current numerical/design-space results.
Do not yet switch to generating all designs and applying drag ≤ 25 mN only during assessment.
Record Option 2 as a later semantic/model-pipeline change requiring separate approval because it changes F1–F8 Pareto populations and robustness counts even though the underlying physics equations remain unchanged.
3. Requirements snapshot — close AG-15 and freeze it.
AG-15 is approved for closure.
The previously unscreened RFP pages have now been reviewed and do not introduce an additional ABEP technical-performance requirement that alters the current RVM technical re-base.
Set the RFP-derived requirements snapshot to:
`FROZEN`
and set `requirement_frozen = true` for the applicable RFP-clause rows.
This freezes the requirements basis only.
It does not mean the architecture has demonstrated compliance. Individual RVM rows retain their existing evidence/status values until determining evidence exists.
4. Golden architecture — cathodeless architecture only for the active baseline.
The active flight architecture is:
`hall_icp_neutralizer`
using:

* Hall accelerator
* RF/ICP electron-source / neutralizer
* no conventional hollow cathode
* no LaB6 cathode in the flight architecture

Do not create or use an active golden architecture-closure case based on a LaB6/Xe hollow cathode.
Create a new governed golden/reference case for:
`hall_icp_neutralizer`
Existing LaB6 golden data, if already committed and required for immutable history, may remain only as:
`HISTORICAL_NON_FLIGHT_REGRESSION`
It must not participate in:

* architecture closure
* architecture selection
* optimization
* current RFP compliance
* flight mass/power/Xe budgets
* current design decisions

Do not rewrite historical evidence merely to remove it from Git history.
5. RFP altitude band — retain 180–230 km as the simulation/domain envelope.
Keep the 180–230 km check.
Represent it as a frozen mission/design-state domain constraint, not as a runtime dependency on the RFP.
The physics/design-state loader should consume something such as:
`mission_domain.altitude_km = [180, 230]`
with provenance back to the requirements snapshot.
The physics code must not parse or query RFP clauses.
6. IC and “Hall preferable” metrics — move to assessment.
Remove integration-compatibility and `hall_preferred` decision metrics from the raw physics-card responsibility.
Raw physics outputs should contain physical/design quantities only.
Move:

* IC metrics
* architecture-preference flags
* RFP/compliance classifications

into the assessment layer.
Preserve them in merged/final assessment outputs where compatibility with existing tools is needed.
If removal changes the raw-output schema, create an explicit schema-version increment rather than pretending the schema is unchanged.
Numerical physics results must remain unchanged.
7. Dead / always-true logic — remove it.
Remove:

* `ignition_req_met ... or True`
* unused `Budgets.duty_cycle`
* unused `RFP` import in `sizing`

Do not keep `ignition_req_met` as a raw physics field merely for historical compatibility.
If downstream tooling still expects it, reconstruct it in the assessment/compatibility layer from the appropriate real ignition evidence.
Removal must not alter physics calculations.
If any numerical physics output changes, stop and report the cause.
8. `bus_boundary_a9` — create v2.
Keep the existing `bus_boundary_a9` immutable as historical v1.
Create:
`bus_boundary_a9_v2`
reflecting the current active flight architecture:
`hall_icp_neutralizer`
Do not carry `hall_c1_reference` as a candidate flight configuration in v2.
If C1 remains in the programme, represent it only as ground-reference/test metadata, not a flight bus configuration.
Re-point the 17–27 pinned consumers in one controlled migration.
Requirements for the migration:

* list every consumer before changing anything
* update pins/hashes together
* run all affected tests
* keep v1 immutable
* verify that no physics result changes merely because the configuration taxonomy changed

9. 36.7 MB F1 output — KEEP IT, but do not put the raw generated file into ordinary Git history.
Preserve the complete F1 output.
It must remain downloadable and reproducible.
Preferred storage:
GitHub Release asset or controlled project evidence storage.
Git LFS is also acceptable if we deliberately want it associated directly with the repository.
Do not commit the 36.7 MB generated output as an ordinary Git blob unless there is a specific reason to do so.
Normal Git storage would work technically, but every committed revision remains in history and progressively increases clone/fetch size.
For the F1 evidence package, create a deterministic archive, preferably:
`F1_<run-id>.tar.zst`
Store with it:

* full archive SHA-256
* archive byte size
* generating Git commit SHA
* architecture ID/hash
* design-state-set ID/hash
* input-manifest hash
* model-set/version identifiers
* numerical-method/version identifiers
* command used to generate it
* generated timestamp
* deterministic file manifest with per-file SHA-256
* result/evidence classification

Commit to Git only:

* the manifest
* hashes
* compact summaries
* essential derived tables/plots where appropriate
* the external/release artefact identifier

The full 36.7 MB archive must remain retrievable for independent reproduction/audit.
If GitHub Release assets are used, preferably attach the F1 evidence bundle to a versioned/tagged engineering evidence release rather than mixing it with source files.
Do not delete the original F1 result after archiving until the archive has been hash-verified byte-for-byte.
One refinement to item 4: we are eliminating LaB₆ from the active flight architecture and active golden baseline. That does not automatically require deleting an old committed LaB₆ regression artefact; keeping it labelled historical preserves provenance without letting it influence the cathodeless programme.
