# OWNER DECISIONS 2026-10-05 (A9.28) — Rust plan v2 rulings and the simulation completion directive — verbatim record

Recorded verbatim from the owner's session messages of 2026-10-05 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_05_A9_28_rust_plan_rulings_and_simulation_completion_directive.json`. Immutable after commit.

---

## Message 1 — RUST_PLAN_V2_RULINGS — 2026-10-05T08:02:07.588Z — text sha256 `4987b0d204583e7569154cf33f8b4d52c578667f600fc785fd1aef42b8c16d57`

````text
RUST PLAN V2 — PRESERVATION AND OWNER RULINGS

1. PRESERVE THE PLAN NOW

Push the existing local branch:

    lane-rustplan-v2

to origin at exactly:

    e01716d

Do NOT merge it.

Do NOT force-push.

Do NOT touch:
    main
    claude/nifty-ramanujan-w68f9z
    technical source 5eee4b8
    package/freeze record 2de86ab

After push, verify the remote branch SHA is exactly e01716d.

The purpose of this push is preservation and review only.

No Rust implementation work starts yet.

==================================================
2. MASS_POWER_A9_V5 CLASSIFICATION
==================================================

Do NOT classify the whole mass_power_a9_v5 artifact as:

    ACTIVE_FLIGHT_INCONSISTENCY

Reclassify it as:

    ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT

with:

    AL-07_VALUE_STATUS =
    PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT
    AFI-02-RA1_OPEN

The generic mass-accounting / margin / harness / roll-up logic is active and
may eventually migrate to Rust.

The 6.0 kg AL-07 value must NOT be promoted by migration into:
    CBE
    measured mass
    frozen flight truth.

AFI-02 remains the action that rebases that input.

==================================================
3. PROVISIONAL CLASSIFICATIONS
==================================================

Use the following dispositions.

plasma_chem.py:
    HISTORICAL_LEGACY_MODULE
    EXTRACT_ARCHITECTURE_INDEPENDENT_KERNELS_ONLY_IF_NEEDED

Reason:
its current system.py execution path is entangled with legacy cards and
LaB6Cathode.

Do not port the complete module.

compressor down-select:
    HISTORICAL
    RETIRE_FROM_ACTIVE_GRAPH

feed-state closure:
    GROUND_TEST_PROGRAMME_ONLY
    NOT_FLIGHT_RUNTIME
    RETAIN_UNTIL_SUCCESSOR_FEED_QUALIFICATION_RECORDS_EXIST

capability demonstration:
    GROUND_TEST_PROGRAMME_ONLY
    ACTIVE_EVIDENCE_TOOLING
    never flight execution

Hall sustainment evidence:
    REFERENCE_EVIDENCE_ONLY
    NOT_FLIGHT_RUNTIME

hardware experiments:
    GROUND_TEST_PROGRAMME_ONLY
    migrate only where the active evidence/toolchain still requires them

instrumentation experiments:
    GROUND_TEST_PROGRAMME_ONLY
    migrate where retained in the active evidence/toolchain

S1 readiness:
    GROUND_TEST_PROGRAMME_ONLY
    ACTIVE_GATE_TOOLING

S1a readiness:
    GROUND_TEST_PROGRAMME_ONLY
    ACTIVE_GATE_TOOLING

Because the target is ZERO PYTHON ACTIVE EXECUTION DEPENDENCY, retained
S1/S1a/evidence gates eventually need Rust equivalents even though they are not
flight physics.

==================================================
4. RM-OQ-06 — HISTORICAL GOLDENS
==================================================

CLAUDE.md Rule 2 applies to the ACTIVE canonical golden set.

Historical / withdrawn goldens:

- remain immutable;
- remain reproducible from their historical Python/reference environment;
- are NOT mandatory Rust end-state parity cases;
- are NOT deleted;
- are NOT rewritten to match the selected architecture.

Do not require Rust to reproduce LaB6 / hollow-cathode historical goldens.

After the bid, update CLAUDE.md so this distinction is explicit.

Create a new active canonical golden for:

    hall_icp_neutralizer

only after the active Rust chain has been admitted.

==================================================
5. RM-OQ-08 — NEW ACTIVE GOLDEN AND THERMAL MODEL
==================================================

Do NOT build a new Python cathodeless thermal model merely to create a Rust
parity target.

The cathodeless thermal model is new selected-architecture physics.

Implement it directly in Rust after preregistering:

- equations;
- energy boundaries;
- node definitions;
- assumptions;
- model domains;
- conservation criteria;
- analytic limiting cases;
- independent evidence/validation cases.

Admission is by independent verification, not synthetic Python parity.

A Python scratch calculation may be used only as an independent cross-check and
must not become an authoritative active dependency.

For migrated existing physics:
    Python reference -> preregistered parity -> Rust admission.

For genuinely new physics:
    preregistered model -> analytic/evidence validation -> Rust admission.

The new hall_icp_neutralizer golden is generated only from the admitted active
chain.

==================================================
6. RM-OQ-09 — H2-6 SOURCE CHECK
==================================================

Do NOT simply retire the integrity check while active CI still depends on it.

Port / replace the CHECK SEMANTICS:

- source hashes;
- provenance;
- pinned owner decisions;
- expected values;
- deterministic source verification.

Prefer a generic Rust provenance verifier if it can cover H2-6 and similar
builders.

Do NOT blindly port obsolete H2-6 architecture assumptions.

Once the Rust verifier is admitted and normal CI is re-pointed:

    retire the Python H2-6 source-check from active CI.

Historical H2-6 evidence remains immutable.

==================================================
7. MIGRATION PRIORITY RULE
==================================================

Preserve:

    architecture relevance FIRST
    evidence / admission eligibility SECOND
    measured runtime THIRD

Therefore:

- uq_modular being slow does not make it a port target if retired;
- archengine being slow does not make it a port target if retired;
- intake response-surface work remains a real active migration target;
- F8 robust optimization is active and may migrate;
- historical code is retired, not ported for performance reasons.

==================================================
8. NO MERGE YET
==================================================

After pushing lane-rustplan-v2:

STOP Rust-plan work until the branch can be reviewed against the repository.

Do not merge e01716d yet.

Submission readiness remains higher priority than post-bid migration work.
````

---

## Message 2 — SIMULATION_COMPLETION_DIRECTIVE — 2026-10-05T08:25:35.800Z — text sha256 `a2d8586c894892ace84c95af8bb60188a0daee8e83689f6090f24c3c62a0b688`

````text
ABEP SIMULATION COMPLETION DIRECTIVE
POST-BID ENGINEERING PRIORITY

We are now stopping RFP-form / Part-IV work.

The priority is:

    COMPLETE THE ABEP SIMULATOR
    THEN INTEGRATE IT CLEANLY INTO MAIN.

Do not work on tender forms, annexure numbering or submission documents unless
the owner explicitly returns to that work.

==================================================
1. PROTECTED BID RECORD
==================================================

The bid freeze remains immutable historical evidence:

TECHNICAL SOURCE:
5eee4b8c82a9403b6bb82d5f8d324526f5d6399b

PACKAGE / FREEZE RECORD:
2de86abefacbd36ce7516d3cf017f6258bd7e7a2

Later simulation development must never rewrite these records or make a later
commit appear to have been the submitted technical source.

==================================================
2. CURRENT REPOSITORY STATE
==================================================

Verify live state before doing anything.

Last independently checked:

main:
b1e5b761a40f82ca225dc412d17a87585653d4ff

development branch:
claude/nifty-ramanujan-w68f9z
dcab60234a3252ff699fe774f05e0fa39d02b4ae

Rust-plan preservation branch:
lane-rustplan-v2
e01716d05256b9f68bda8187318ae5ee04fe03b0

Current main/development relationship:
development is approximately 266 commits ahead and 6 commits behind main.

PR #37 is DIRTY / NON-MERGEABLE.

Do NOT merge PR #37.

Do NOT modify main directly.

==================================================
3. CREATE A SIMULATION INTEGRATION LINE
==================================================

Create a dedicated integration branch for completing the simulator.

Suggested name:

    integration/simulation-complete

Base it from the current authoritative development state, not from an obsolete
bid snapshot.

Then integrate the six main-only checkpoint commits into this branch.

Do not use a blanket "ours" or "theirs" conflict strategy.

For every conflict:
- identify which side represents the later governed implementation;
- preserve immutable historical evidence;
- preserve current architecture/configuration decisions;
- document any semantic resolution.

main remains untouched until the complete simulator is admitted.

==================================================
4. ACTIVE ARCHITECTURE
==================================================

The only active flight simulation architecture is:

    hall_icp_neutralizer

Flight topology:

    rarefied atmospheric intake
        ->
    filter
        ->
    compressor
        ->
    plenum / feed
        ->
    Hall accelerator
        +
    downstream 13.56 MHz RF/ICP electron-source / neutralizer

Propellant modes:

    AIR_PRIMARY
    XE_CONTINGENCY

Flight conventional hollow cathode:

    NONE

C1:

    GROUND_REFERENCE_ONLY

Do not reopen broad architecture-family selection.

Do not port obsolete architecture families merely because Python contains them.

==================================================
5. IMPLEMENT THE RUST-PLAN OWNER RULINGS FIRST
==================================================

Resume lane-rustplan-v2 only now.

Record the owner's later rulings verbatim and revise the plan on top of e01716d.

Required classifications include:

mass_power_a9_v5:
    ACTIVE_SELECTED_ARCHITECTURE_ENGINEERING_ASSESSMENT

AL-07 6.0 kg:
    PROVISIONAL_LEGACY_DERIVED_ANALOG_INPUT
    AFI-02-RA1_OPEN

plasma_chem module:
    HISTORICAL_LEGACY_MODULE
    extract only architecture-independent kernels that the selected architecture
    actually needs.

compressor down-select:
    HISTORICAL / RETIRE

feed-state closure:
    GROUND_TEST_PROGRAMME_ONLY

capability demo:
    GROUND_TEST_PROGRAMME_ONLY / ACTIVE_EVIDENCE_TOOLING

Hall sustainment audit:
    REFERENCE_EVIDENCE_ONLY

hardware / instrumentation experiments:
    GROUND_TEST_PROGRAMME_ONLY

S1 / S1a readiness:
    ACTIVE_GROUND_GATE_TOOLING

Historical LaB6 / hollow-cathode functionality is NOT ported into active Rust.

After review, merge the corrected PLAN into the simulation integration branch,
not directly into main.

==================================================
6. DEFINITION OF "SIMULATION COMPLETE"
==================================================

Software completion requires an admitted active implementation of all applicable
selected-architecture layers:

environment:
    atmosphere
    orbit / design states

upstream:
    intake TPMC
    filter
    compressor
    plenum
    feed dynamics

propulsion:
    atmospheric / Xe gas state
    active RF/ICP physics
    HallThruster.jl bridge
    Hall acceleration
    electron neutralization
    coupled thrust / flow

spacecraft interaction:
    intake drag
    reference spacecraft drag interface
    statewise T-D

electrical:
    PPU/load model
    RF generator/matching
    bus-power accounting
    startup/concurrent-load behaviour

thermal:
    NEW cathodeless Hall + RF/ICP thermal model

mass:
    selected-flight architecture mass accounting
    margin/accounting rules
    Xe sensitivity

materials/life:
    AO exposure
    erosion
    firing/mission life quantities
    applicable reliability quantities

mission:
    state propagation
    mission integration

uncertainty/design:
    active F7/F8 design synthesis
    robust optimization
    UQ for the selected architecture

assessment:
    requirements-independent raw physics
    separate requirement assessment
    HC gates
    RVM mapping where needed by engineering assessment

infrastructure:
    configuration/hash/provenance
    deterministic CLI
    builders/evidence generation that remains active
    active canonical golden
    CI
    clean-install reproducibility.

==================================================
7. HALL PHYSICS
==================================================

HallThruster.jl remains authoritative for Hall discharge physics.

Do not rewrite Hall physics in Rust merely to remove Julia.

Rust shall own orchestration and the rest of the active simulator.

The Rust/Julia interface must be deterministic, version-pinned and provenance
recorded.

Credible Hall transport set currently remains empty.

Therefore absence of determining Hall calibration evidence must remain visible.

Never turn screening candidates into admitted members without the governed
validation process.

==================================================
8. NEW CATHODELESS THERMAL MODEL
==================================================

Do not port the old P3 cathode-node thermal model.

Create the selected-architecture thermal model directly in Rust.

Before implementation preregister:

- nodes;
- equations;
- heat sources;
- radiative/conductive boundaries;
- spacecraft interface;
- RF/ICP waste heat;
- Hall waste heat;
- assumptions;
- domains;
- conservation checks;
- analytic limiting cases;
- evidence/validation plan.

Admission is by independent verification.

Python parity is NOT required for genuinely new physics.

==================================================
9. ACTIVE RF/ICP PHYSICS
==================================================

Do not blindly port plasma_chem.py.

Audit its architecture-independent physical kernels.

Extract only what is valid for the selected RF/ICP electron-source / neutralizer.

For every retained kernel:

- establish provenance;
- define applicability domain;
- preregister parity/verification;
- port/admit independently.

No LaB6 dependency may enter the new active chain.

==================================================
10. PYTHON -> RUST MIGRATION RULE
==================================================

For retained existing physics:

    Python reference
        ->
    preregister parity
        ->
    Rust implementation
        ->
    parity / conservation / domain tests
        ->
    admission
        ->
    remove Python from active execution path.

Never modify the Python reference merely to make Rust pass.

For genuinely new physics:

    preregister model
        ->
    implement Rust
        ->
    analytic / independent evidence verification
        ->
    admission.

Do not create fake Python reference implementations solely for parity.

==================================================
11. HISTORICAL CODE
==================================================

Historical modules remain in Git for provenance and reproducibility.

RETIRE means:

    not imported by active production execution;
    not required by normal simulator CLI;
    not required by normal CI except explicit historical-regression jobs;
    not ported merely for completeness.

Do NOT delete historical evidence.

Do NOT make active Rust reproduce obsolete LaB6 architecture goldens.

==================================================
12. ACTIVE GOLDEN
==================================================

Historical golden_v1/v2 stay immutable historical references.

After enough of the active Rust chain is admitted, create a new canonical:

    hall_icp_neutralizer

golden.

The active golden must cover:

- deterministic input configuration;
- raw physics;
- conservation;
- architecture identity;
- no conventional hollow cathode;
- applicable statewise outputs;
- assessment separation.

Do not create it until the active implementation is sufficiently admitted.

==================================================
13. ZERO-PYTHON END STATE
==================================================

The final production simulator target remains:

    ZERO PYTHON ACTIVE EXECUTION DEPENDENCY

This includes normal:

- simulation;
- design sweeps;
- mission propagation;
- UQ;
- assessment;
- gates;
- configuration/hash handling;
- evidence/provenance builders that remain operational;
- normal CI.

Python may remain for:

    archived historical reproduction only

after the corresponding active Rust components are admitted.

==================================================
14. HARDWARE EVIDENCE IS NOT SOFTWARE
==================================================

Do not wait for unavailable hardware evidence to finish software architecture.

But do not fabricate it.

Where determining evidence is absent, the complete simulator must fail closed:

    NOT_EVALUATED
    INCOMPLETE_EVIDENCE
    OUT_OF_DOMAIN
    MODEL_ERROR

as appropriate.

Examples include:
- measured H-1 map;
- ICP capacity evidence;
- host-spacecraft drag ICD;
- material test evidence;
- measured RF impedance;
- measured thermal validation.

"Software complete" does NOT mean those gates become PASS.

==================================================
15. MIGRATION ORDER
==================================================

Use:

    architecture relevance
        first
    evidence/admission eligibility
        second
    measured performance
        third.

Do not port uq_modular or legacy archengine because they are slow.

Retire them if historical.

Use the PRE_RUST baseline to prioritize only active retained components.

==================================================
16. MAIN MERGE POLICY
==================================================

DO NOT merge into main incrementally while the simulator is half migrated.

main should receive one coherent admitted simulation baseline.

Before any final PR to main require:

- all active production execution uses Rust + HallThruster.jl only;
- no active LaB6/hollow-cathode path;
- selected architecture identity invariant;
- all retained Python components either migrated or explicitly historical;
- clean install;
- deterministic outputs;
- conservation checks;
- config/hash integrity;
- active golden green;
- full Rust tests;
- Hall interface tests;
- 196-state execution;
- robust/UQ execution;
- assessment separation tests;
- no silent fallbacks;
- no requirement parsing in raw physics;
- GitHub CI green;
- no uncommitted/generated drift.

Then create a NEW PR:

    integration/simulation-complete -> main

Do not reuse PR #37.

PR #37 should eventually be closed as:

    SUPERSEDED_BY_SIMULATION_INTEGRATION

after the new integration branch contains all required governed history.

==================================================
17. MAIN DIVERGENCE
==================================================

The six main-only commits are historical integration checkpoints #31-#36.

Do not discard them.

Before final simulator development gets far ahead, merge/reconcile main into the
simulation integration branch once, preserving:

- their historical commits;
- newer governed implementations from the development line;
- provenance.

After that, keep the integration branch up to date and avoid creating another
large divergence.

==================================================
18. COMPLETION REPORT
==================================================

Do not claim "simulation complete" based only on test count.

At completion report:

A. exact integration SHA;
B. execution dependency graph;
C. active-language inventory;
D. proof normal execution has zero Python dependency;
E. HallThruster.jl integration and pin;
F. selected-architecture invariant proof;
G. active golden result;
H. full 196-state result;
I. robust/UQ result;
J. unresolved hardware-evidence gates;
K. clean-install result;
L. CI result;
M. comparison against the frozen bid technical source;
N. exact main-merge plan.

Only then request owner authorization to merge the completed simulator into main.
````

