# FINAL OWNER RULINGS — RUST PLAN V3.1 AND START AUTHORIZATION (A9.29) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-05 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_05_A9_29_rust_plan_v3_1_rulings_and_start_authorization.json`. Immutable after commit.

---

## Message 1 — RUST_PLAN_V3_1_RULINGS_AND_START_AUTHORIZATION — 2026-10-05T10:04:26.573Z — text sha256 `7e8a48d1f6e7c28713ff016b498b784d5f6fc201ee8c1a44392d88345cbd3f00`

````text
FINAL OWNER RULINGS — RUST PLAN V3.1 AND START AUTHORIZATION

I have reviewed Rust plan v3 at:

1236f911b326b308ec9019d7e3561a34b478c449

The overall structure and the 17-work-package simulation-completion programme
are APPROVED, subject only to the rulings below.

Do not start another broad planning cycle.

Apply these as one narrow v3.1 plan update, validate the plan, merge it into:

    integration/simulation-complete

and immediately begin the authorized execution sequence.

main remains untouched.

==================================================
1. FIFTH CLASS — APPROVED
==================================================

Approve the migration class:

    GROUND_TEST_PROGRAMME_ONLY

Keep it separate from:

    ACTIVE_SELECTED_ARCHITECTURE
    GROUND_REFERENCE_ONLY
    HISTORICAL_LEGACY_REGRESSION

Its code may be active programme/evidence/gate tooling, but:

    no flight-runtime crate may depend on it.

The `abep-groundtest` isolation concept is approved.

==================================================
2. RM-OQ-10 — FEED-STATE CLOSURE
==================================================

OWNER DECISION:

If a successor feed-qualification record exists before final cutover:
    use that successor.

If no successor exists:
    freeze the present feed-state closure outputs as immutable,
    hash-pinned REFERENCE EVIDENCE.

Do NOT port the historical Python builder merely to preserve reconstruction.

At zero-Python cutover:

    normal CI verifies the frozen artifact/hash/schema;
    the historical Python builder is archive-only.

If retained S1/S1a tooling needs a live feed-state computation, that requirement
must be implemented deliberately in abep-groundtest under its own Rust contract,
not by silently keeping the old Python builder alive.

Close RM-OQ-10 accordingly.

==================================================
3. RM-OQ-11 — BID PACKAGE GUARD
==================================================

OWNER DECISION:

Yes.

Terminal protected package state:

    2de86abefacbd36ce7516d3cf017f6258bd7e7a2

Protected technical source:

    5eee4b8c82a9403b6bb82d5f8d324526f5d6399b

Preserve package lineage:

    b5849af -> 2de86ab

The guard should treat 2de86ab as the terminal owner-authorized package state.

Any later change to the historical bid package requires a new explicit owner
decision and must not silently alter the frozen bid record.

Close RM-OQ-11.

==================================================
4. RM-OQ-12 — PREDICTIVE RF/ICP MODEL IS REQUIRED
==================================================

Reject the proposed default that a predictive RF/ICP model is optional.

OWNER DECISION:

A predictive RF/ICP electron-source / neutralizer model IS REQUIRED for:

    SIMULATION_COMPLETE

Reason:

The selected flight architecture is:

    hall_icp_neutralizer

and therefore both the Hall accelerator and the RF/ICP electron-source /
neutralizer need a predictive system model.

An evidence-gated P1/P2 framework alone is not a complete simulation of the
selected architecture.

This model is NEW PHYSICS.

Do NOT port plasma_chem.py wholesale.

Do NOT inherit LaB6, hollow-cathode, ECR or legacy stage-1 topology.

Create a new preregistered model specifically for the selected downstream
13.56 MHz RF/ICP electron-source / neutralizer.

Minimum model scope must include, where physically defensible:

INPUTS
    - gas/feed state from the active upstream chain;
    - atmospheric species relevant to the registered environment;
    - Xe contingency mode;
    - 13.56 MHz operating frequency;
    - RF electrical input / absorbed-power representation;
    - geometry / effective plasma volume;
    - pressure / neutral density;
    - thermal boundary inputs;
    - registered uncertainty / evidence classes.

RAW PHYSICS OUTPUTS
    - absorbed RF/plasma power;
    - electron temperature or equivalent registered plasma state;
    - electron density;
    - species-resolved ionization / dissociation quantities where included;
    - electron production / extraction capacity;
    - electron current available for neutralization;
    - plasma / RF loss partition;
    - neutralizer heat deposition;
    - applicable coupling / impedance quantities;
    - domain / convergence status.

SYSTEM COUPLING
    - couple RF/ICP electron-current capability to Hall discharge-current demand;
    - couple RF/ICP electrical demand into bus power;
    - couple RF/ICP losses into the cathodeless thermal model;
    - couple gas consumption into the feed / mission model.

ASSESSMENT SEPARATION

Raw RF/ICP physics MUST NOT contain:

    HC-05 PASS/FAIL
    requirement thresholds
    RFP compliance labels.

Raw output provides quantities such as:

    I_e,cap

Assessment separately evaluates:

    M_n = I_e,cap / I_d,max,H1 - 1

with the registered uncertainty rule.

If determining bench evidence is absent, output uncertainty / NOT_EVALUATED
appropriately.

Do not invent coupling efficiency, impedance, extraction efficiency or stable
operating regions merely to close the model.

The model may have calibrated and uncalibrated modes, but provenance and domain
must be explicit.

VALIDATION

Admission must use:

    - conservation;
    - analytic limiting cases;
    - applicable published evidence;
    - P1/P2 hardware evidence when available;
    - preregistered comparison criteria.

No synthetic Python reference is required.

Close RM-OQ-12 as:

    PREDICTIVE_RF_ICP_MODEL_REQUIRED_FOR_SIMULATION_COMPLETE

==================================================
5. RM-OQ-01 — TPMC BACKEND
==================================================

Do NOT change the historical Python wrapper's default merely to make Rust look
primary.

Keep the Python reference unchanged during migration.

The standalone Rust simulator shall call the admitted Rust TPMC library
DIRECTLY.

Therefore the end state is not:

    Python wrapper -> backend="rust"

It is:

    Rust simulator -> Rust TPMC library.

The Python backend switch becomes irrelevant at final cutover.

Close RM-OQ-01 with this disposition.

==================================================
6. RM-OQ-02 — ATMOSPHERE REBUILD
==================================================

Normal production simulation shall use the frozen, hash-pinned atmosphere /
design-state datasets.

Rust must implement:

    deterministic loading;
    schema/domain checking;
    hash verification;
    state selection;
    the complete 196-state execution.

A live NRLMSIS/HWM14 regeneration facility is NOT required for the initial
zero-Python production cutover.

Do not make Fortran FFI a critical-path dependency merely for regeneration.

If atmosphere regeneration is needed later, implement a separately governed
native regeneration tool against the authoritative upstream model.

The existing frozen data remain the production source until deliberately
replaced by a new versioned evidence artifact.

Close RM-OQ-02 accordingly.

==================================================
7. RM-OQ-03 — UQ RNG
==================================================

Use:

    EXACT_STREAM

for the Python-reference -> Rust parity campaign of the active UQ / F8 sampling
where the Python reference uses numpy PCG64.

Implement the registered PCG64 stream semantics required to reproduce the
reference samples.

This decision applies to the UQ/design orchestration stream.

Do NOT incorrectly apply it to the admitted TPMC kernel, whose Rust stochastic
implementation already uses its separately registered RNG/statistical parity
contract.

Required distinction:

    design/UQ sampling:
        exact registered stream parity

    TPMC particle tracing:
        existing admitted stochastic/statistical parity contract.

After Rust becomes authoritative, future new UQ campaigns may use the registered
Rust RNG policy, but the migration parity dataset must remain exactly
reproducible.

Close RM-OQ-03.

==================================================
8. RM-OQ-04 — PYTHON RETIREMENT / ARCHIVE
==================================================

Do NOT move Python files into a retired directory during migration.

During migration:

    Python remains at current paths where required as a parity reference.

At final cutover create:

    immutable tag:
        python-final-reference-<date>

    immutable archival branch:
        archive/python-final-reference

plus:

    docs/archive/PYTHON_FINAL_REFERENCE.md
    docs/archive/python_final_reference.json

The archive manifest must map:

    Python source
        ->
    Rust replacement / formal retirement
        ->
    parity / admission evidence.

After all active components are admitted:

    Python may be removed from the ACTIVE main tree.

Preserve Git history.

Do not rewrite history.

Do not delete the archive tag/branch.

Do not keep an archive/python_reference directory in current main unless there
is a specific operational need; the Git tag/branch is the preferred archive.

Close RM-OQ-04.

==================================================
9. RM-OQ-05 — RUST-ERA TEST RULE
==================================================

Replace the Python-era rule:

    pytest + 5 skips + 1 xfail

for ACTIVE production with the following Rust-era rule:

NORMAL ACTIVE CI:

    cargo test --workspace --locked
        all active tests PASS

No ordinary active production test may be silently ignored/skipped.

Known missing physical evidence is NOT represented as a skipped test.

Instead tests assert the correct fail-closed result:

    NOT_EVALUATED
    INCOMPLETE_EVIDENCE
    OUT_OF_DOMAIN
    MODEL_ERROR

as applicable.

The empty Hall credible transport set is an expected governed state and should
be asserted explicitly, not represented as an xfail.

Platform/hardware tests that genuinely cannot run in normal CI must have a
separate registered test class with:

    reason
    owner/evidence basis
    execution environment
    required trigger

and may not silently disappear from the test inventory.

Historical Python:

    5 skips / 1 strict xfail

remains archive-era reproduction metadata only.

Close RM-OQ-05 and update CLAUDE.md accordingly.

==================================================
10. CLAUDE.MD GOVERNANCE UPDATE
==================================================

Before substantive Rust implementation, perform the narrow current-governance
update:

CA-01:
    rule 2 applies to ACTIVE canonical goldens;
    historical goldens are archive/regression history.

CA-02:
    execution baseline is integration/simulation-complete.

CA-03:
    update stale pre-Rust / pre-bid execution wording.

CA-04:
    apply the Rust-era test rule above.

Also update the language direction so current work clearly states:

    target simulator = Rust
    Hall solver = HallThruster.jl
    Python = migration reference until admitted, then archive-only.

Do not rewrite historical decision files.

==================================================
11. PYTHON ARCHIVE / RUST-PRIMARY END STATE
==================================================

Add the language-cutover rules already approved by the owner to plan v3.1.

Final production stack:

    Rust simulator
        +
    HallThruster.jl
        +
    versioned configuration / evidence data

No normal production dependency on:

    python
    python3
    pip
    virtualenv
    PyO3
    maturin.

The present abep_core PyO3 interface is migration tooling.

Its underlying Rust TPMC implementation is retained and becomes a normal Rust
library dependency.

PyO3/maturin may be retired from production after parity migration is finished.

==================================================
12. PLAN MERGE AUTHORIZATION
==================================================

Apply only the decisions above to produce plan v3.1.

Requirements:

- v1 / v2 / v3 historical records remain unchanged;
- new v3.1 records are additive/versioned;
- no numerical simulation result changes in the plan commit;
- CI checks remain green;
- component inventory has zero unclassified/provisional items;
- all open RM-OQ-01..12 are closed or explicitly converted into execution
  evidence tasks.

If those conditions hold:

    merge plan v3.1 into integration/simulation-complete

without stopping for another owner review.

Do NOT merge into main.

==================================================
13. IMMEDIATE EXECUTION — START AFTER PLAN MERGE
==================================================

Once plan v3.1 is merged, start implementation immediately.

Use parallel lanes only where dependencies permit.

LANE A — INFRASTRUCTURE / PROVENANCE

Start ES-1:

- Cargo workspace;
- pinned Rust toolchain;
- config/provenance foundation;
- migration ledger;
- bid-source guard;
- generic Rust provenance verifier;
- active architecture invariant.

LANE B — ENVIRONMENT / UPSTREAM

Start ES-2 and then ES-3:

- frozen atmosphere / 196-state reader;
- orbit/design-state handling;
- admitted TPMC Rust library integration;
- intake response;
- filter;
- compressor;
- plenum/feed.

LANE C — NEW PROPULSION PHYSICS PREREGISTRATION

In parallel, preregister:

    NP-ICP-NEUTRALIZER

for the predictive 13.56 MHz RF/ICP neutralizer model defined above.

No implementation before its preregistration is committed.

LANE D — NEW THERMAL PHYSICS PREREGISTRATION

In parallel, execute ES-4:

    NP-THERMAL-CATHODELESS

preregister the Hall + RF/ICP cathodeless thermal model.

No implementation before preregistration.

==================================================
14. SPEED WITHOUT LOWERING THE STANDARD
==================================================

The working RFP deadline is 12 October 2026.

We need the simulation completed as soon as practicable.

Therefore:

- no new architecture trade;
- no optional legacy ports;
- no cosmetic refactors unrelated to the active chain;
- no historical builder migration merely for completeness;
- no premature performance optimization;
- no RFP document work during this simulation phase unless explicitly
  requested by the owner.

But speed MUST NOT weaken:

- provenance;
- preregistration;
- conservation;
- deterministic behaviour;
- model-domain checks;
- requirement/physics separation;
- uncertainty handling;
- fail-closed evidence semantics.

==================================================
15. SIMULATION-COMPLETE MEANS THE FULL SELECTED ARCHITECTURE
==================================================

The final software-complete active chain must include:

    atmosphere/orbit
      ->
    TPMC intake
      ->
    filter
      ->
    compressor
      ->
    plenum/feed
      ->
    predictive 13.56 MHz RF/ICP neutralizer
      +
    HallThruster.jl Hall accelerator
      ->
    coupled thrust/neutralization
      ->
    spacecraft drag / T-D
      ->
    power
      ->
    cathodeless thermal
      ->
    mass
      ->
    materials/life
      ->
    mission
      ->
    robust/UQ
      ->
    separate assessment/gates.

AIR_PRIMARY and XE_CONTINGENCY must both be represented.

Conventional flight hollow cathode:

    NONE.

C1:

    GROUND_TEST / REFERENCE ONLY,
    never flight execution.

Do not call the simulator complete until this chain runs end-to-end under Rust
or Rust + HallThruster.jl with zero Python production dependency.

==================================================
16. REPORT AFTER FIRST EXECUTION BATCH
==================================================

After plan merge and the first parallel execution batch, report:

A. exact integration SHA;
B. Cargo workspace/crates created;
C. provenance/config status;
D. environment/196-state status;
E. TPMC/upstream status;
F. NP-ICP preregistration status;
G. NP-THERMAL preregistration status;
H. tests/CI;
I. any blocker requiring an owner decision.

Do not stop merely to report routine progress.

Stop only for:

- a genuine owner decision;
- evidence conflict;
- model-domain conflict;
- failed preregistration condition;
- physics inconsistency;
- governance conflict.
````

