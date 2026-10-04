# OWNER DECISIONS 2026-10-04 (A9.25) — pre-bid steering, CI portability, item 3, scenario versioning, AFI resolution — verbatim record

Recorded verbatim from the owner's session messages of 2026-10-04 (after the A9.24 record `OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md`). Text extracted programmatically from the session transcript (no retyping); each message carries its UTC timestamp and the sha256 of its exact text. Companion: `OD_2026_10_04_A9_25_pre_bid_owner_decisions.json` (OWNER_DECISION_SUMMARY per topic with implementing commits). Immutable after commit.

---

## Message 1 — STEERING_DIRECTIVE — 2026-10-04T09:08:50Z — text sha256 `8a91a34844a3e142f161bc9d36b24cefe24adc845f4c41a542fcd4c763b87a1c`

````text
ABEP / DRDO PROGRAMME — CURRENT STEERING DIRECTIVE

Before doing any work, read this as the governing direction for the current development phase.

First verify the current HEAD of:

claude/nifty-ramanujan-w68f9z

The last independently audited head was:

4b5563b643aa2103d999484ce4ccf5e2eca040e3

Do not assume that SHA is still current if newer commits exist. Report the actual HEAD before making changes.

The repository has evolved substantially. We are no longer trying to discover a propulsion architecture from a broad multi-family trade.

We have selected the architecture topology to develop.

==================================================
1. PROGRAMME DIRECTION
==================================================

The active flight architecture is:

hall_icp_neutralizer

Architecture:

AMBIENT ATMOSPHERE
    ↓
rarefied-gas intake
    ↓
filter / gas-surface management
    ↓
active compressor
    ↓
plenum / gas chamber / feed control
    ↓
Hall accelerator
    +
downstream 13.56 MHz RF/ICP electron source / neutralizer
    ↓
exhaust

Separate contingency supply:

Xe tank
    ↓
regulation / valve
    ↓
same propulsion system

Flight rules:

- AIR_PRIMARY
- XE_CONTINGENCY / EMERGENCY
- one Hall accelerator
- one downstream RF/ICP electron-source / neutralizer
- no conventional hollow cathode in flight
- no LaB6 flight cathode
- C1 is ground-reference equipment only where explicitly required for laboratory H-1 characterization
- C1 must never enter flight mass, flight power, flight Xe budget or flight architecture closure

Do not reopen the broad propulsion-family trade unless I explicitly ask.

Historical ECR, gridded-ion, magnetic-nozzle, LaB6-Hall, MPD, PIT, thermal-thruster etc. implementations may remain for provenance/regression, but they must not drive the production architecture.

==================================================
2. IMPORTANT TERMINOLOGY
==================================================

The architecture TOPOLOGY is owner-decided.

That does NOT mean the physical flight design has been validated or frozen.

Current status must remain conceptually:

TOPOLOGY:
    DECIDED / FROZEN FOR DEVELOPMENT

PHYSICAL DESIGN:
    INVESTIGATION_HYPOTHESIS
    NOT YET FROZEN_REFERENCE_FLIGHT_ARCHITECTURE

Do not label the architecture PASS or flight-qualified until the determining-evidence gates are actually closed.

==================================================
3. SIMULATION ARCHITECTURE
==================================================

Do not treat the RFP itself as a simulation dependency.

The correct dependency structure is:

requirements / provenance
        ↓
frozen engineering constraints

frozen architecture
+ frozen engineering constraints
+ frozen operating scenario
+ frozen design-state set
+ physics model set
        ↓
RAW PHYSICS RESULTS

raw physics results
+ frozen engineering constraints
        ↓
ASSESSMENT / COMPLIANCE

The physics simulator must NOT:

- parse the RFP;
- inspect RFP clause IDs to decide physics;
- import the RVM to perform physical calculations;
- produce RFP PASS/FAIL inside physical models;
- change physical results merely because a compliance threshold changes.

The RFP is provenance for some engineering constraints.

Example:

physics:
    P_bus = 1370 W

assessment:
    1370 < 1500
    => compliant

not:

physics:
    RFP_power_pass = true

Enforce this layer separation.

==================================================
4. AUTHORITATIVE INPUTS
==================================================

Use one authoritative source of truth per role.

Current intended structure:

config/architecture/hall_icp_neutralizer_v1.json
    = selected architecture topology

config/constraints/engineering_constraints_v1.json
    = frozen engineering / acceptance constraints

config/mission/mission_scenario_v1.json
    = operating choices

config/environment/design_state_set_ref_v1.json
    -> frozen 196-state design-state set

config/hardware/hardware_bounds_v1.json
    = validated / registered hardware bounds

config/model_set/physics_model_set_v1.json
    = model/version definition

Do not create duplicate competing sources of truth.

If equivalent authoritative files already exist, use them.

==================================================
5. OPERATING INPUTS VS REQUIREMENT THRESHOLDS
==================================================

Keep these concepts separate.

Current operating scenario values:

mission_hours = 26280

xe_sizing_thrust_target_mN = 12

commanded_thrust_cap_mN = 25

p_bus_throttling_cap_W = 1500

These are explicit operating/configuration values after freeze.

Their provenance may point to engineering requirements, but they must not dynamically copy values from RFP/RVM records during normal simulation.

Required invariant:

Changing a requirement/compliance threshold:
    may change assessment
    MUST NOT change raw physics.

Changing an operating scenario:
    may change physics
    requires a new scenario/config version.

==================================================
6. CURRENT PHYSICAL REALITY
==================================================

Do not hide the present engineering state.

The current 196-state evaluation found:

ROBUST UPSTREAM SET = EMPTY

That is a legitimate design finding.

Do not:

- relax requirements to recover a robust set;
- silently remove difficult states;
- retune parameters after seeing the result;
- select a favourable subset and call it the mission solution.

The current binding issues include the intake/compressor/feed chain under the broad envelope.

Treat these as engineering problems to resolve using:

- better physical modelling where justified;
- geometry optimisation;
- hardware evidence;
- test data;
- improved component design;
- mission/spacecraft ICD inputs when they become available.

Do not manufacture closure.

==================================================
7. PRIORITY HAS NOW SHIFTED FROM SOFTWARE EXPANSION TO DETERMINING EVIDENCE
==================================================

The critical programme chain is now:

FEMM / magnetic design
    ↓
H-1 engineering article
    ↓
H-1 reference characterization
    ↓
ICP / RF electron-source characterization
    ↓
impedance / matching map
    ↓
coupled Hall + ICP test
    ↓
thermal / materials / AO evidence
    ↓
measured H-1 thrust-vs-feed map
    ↓
statewise upstream feed sufficiency
    ↓
spacecraft T - D closure
    ↓
architecture freeze

Software work should support this chain.

Do not generate large new speculative model families while these determining measurements remain missing.

==================================================
8. H-1
==================================================

H-1 is the engineering Hall article.

Immediate path:

S7.1:
    register authorised FEMM analysis points,
    geometry revisions,
    material properties,
    coils,
    current points,
    boundary conditions,
    solver/version.

Run FEMM.

Then S7.2:

select an engineering channel/design point based on:

- magnetic feasibility;
- thermal margin;
- mass;
- packaging;
- manufacturability;
- programme evidence.

Do not optimize H-1 against unvalidated simulated thrust.

No Hall performance number should be treated as determining until the appropriate validated / measured H-1 evidence exists.

==================================================
9. C1 / LaB6 POLICY
==================================================

Flight architecture:

NO LaB6.
NO conventional hollow cathode.
NO C1 flight fallback.

C1 may exist ONLY as ground-reference laboratory equipment if needed to characterize H-1 independently of the RF/ICP neutralizer.

Audit every active path containing:

LaB6Cathode
lab6_xe
hall_c1_reference
xe_hollow

Classify each occurrence as:

HISTORICAL_REGRESSION

GROUND_REFERENCE

ACTIVE_FLIGHT_INCONSISTENCY

Do NOT port any ACTIVE_FLIGHT_INCONSISTENCY into Rust.

Do not silently change numerical baselines when finding one.

Report active-flight inconsistencies to me before changing them.

==================================================
10. ICP / RF NEUTRALIZER
==================================================

The flight electron-source / neutralizer is RF/ICP.

Primary development sequence remains:

Ar engineering / commissioning reference where appropriate
    ↓
air / N2 development campaign
    ↓
Xe contingency-mode campaign
    ↓
coupled H-1 + ICP

Each campaign/mode must have its own registered:

- operating domain;
- gas mode;
- pressure-match rule;
- calibration basis;
- stable-region criteria;
- uncertainty/provenance.

Do not transfer a demonstrated Ar point directly into flight-air evidence.

==================================================
11. GNG-ICP-01
==================================================

The ICP go/no-go remains fail-closed.

Current approved structure:

C1 — ELECTRON CURRENT CAPACITY

M_n = I_e,cap / I_d,max,H1 - 1

criterion:

M_n,LB > 0

C2 — SYSTEM POWER

A valid operating point must remain within the complete spacecraft-side power limit.

Do not use laboratory mains input as spacecraft bus power.

C3 — IGNITION / RE-IGNITION

Require the registered repeated ignition/re-ignition demonstration for required flight-relevant gas modes.

GO only when all approved criteria are MET.

Missing evidence:

NOT_EVALUATED

not PASS.

==================================================
12. HARD GATES
==================================================

Keep physics outputs separate from acceptance rules.

HC-05 ICP current margin:
ASSESSMENT ONLY

HC-06 thermal margin:
ASSESSMENT / protection rule

HC-07 15,000 h subsystem firing life:
ASSESSMENT ONLY

Mission duration remains:
26,280 h

HC-08:
T_available - D_spacecraft >= 0
ASSESSMENT ONLY

HC-09:
keep current Option 1 generation filter for now.
Do not move to Option 2 without separate owner approval.

HC-10:
ambient + Xe capability
ASSESSMENT ONLY

HC-11:
feed_available - feed_required >= 0
ASSESSMENT ONLY
and feed_required must ultimately come from measured/validated H-1 performance.

HC-12:
H-1 ripple threshold remains NOT_EVALUATED until evidence exists.
Do not invent a value.

==================================================
13. RUST MIGRATION — TARGET END STATE
==================================================

The earlier “do not rewrite in Rust” decision is superseded.

Target end-state:

ZERO active Python execution dependency.

Rust shall eventually own:

- atmosphere/orbit;
- intake / TPMC;
- compressor / gaspath;
- chemistry support outside HallThruster.jl;
- mission propagation;
- power;
- thermal;
- mass;
- lifetime;
- UQ;
- design synthesis;
- architecture closure;
- assessment / hard gates;
- configuration / hashes;
- evidence builders;
- CLI;
- orchestration.

HallThruster.jl remains the authoritative Hall-discharge solver unless separately changed later.

But do NOT do a big-bang rewrite.

==================================================
14. RUST MIGRATION METHOD
==================================================

For each active Python component:

1. identify the exact production Python implementation;

2. classify whether it belongs to the selected architecture or is historical/retired;

3. preregister parity criteria BEFORE comparing Rust;

4. implement Rust;

5. compare:
   - inputs;
   - numerical outputs;
   - conservation;
   - deterministic behaviour;
   - error/domain behaviour;
   - schemas;
   - hashes/provenance where relevant;

6. investigate every disagreement;

7. only after parity/admission:
   Rust becomes authoritative for that component;

8. retire Python from active execution.

Never regenerate or modify reference Python results merely to make Rust pass.

Do not port obsolete multi-architecture or LaB6 flight logic just because it exists in Python.

Kernel 1 TPMC is already admitted under the recorded parity process.

Use the dedicated performance baseline to PRIORITIZE migration.

Performance does not determine whether a component will eventually be migrated; all active Python dependencies must ultimately be removed.

==================================================
15. BID BASELINE VS RUST
==================================================

Do NOT contaminate the bid baseline with substantive Rust migration.

First establish:

FINAL VERIFIED PRE-RUST BID TECHNICAL BASELINE

It should contain all approved architecture/configuration/layer-separation decisions but remain the last completely verified pre-Rust production implementation.

Before freezing, require:

- full test suite;
- Rule-9;
- golden/reference checks;
- CI integrity;
- configuration/hash checks;
- no unexplained numeric changes.

Record the exact commit SHA.

Then begin substantive Rust migration after that freeze.

Do not use bbc480c as the final freeze if a later verified pre-Rust commit supersedes it.

==================================================
16. README / CLAUDE.MD STALENESS
==================================================

The repository still contains top-level text that says:

“Python is authoritative”
and/or
“26,000 h mission”

These are superseded by current decisions.

Do not edit them casually while the bid freeze is still moving.

After the final pre-Rust bid baseline is established, prepare a controlled documentation consistency update so top-level documentation reflects:

mission = 26,280 h

Python = migration reference

Rust = target production implementation

HallThruster.jl = Hall solver

hall_icp_neutralizer = active flight topology

No LaB6 flight cathode

Do not rewrite historical records.

==================================================
17. REPOSITORY / BRANCH SAFETY
==================================================

Do NOT merge PR #37 into main.

Do NOT alter main.

Do NOT delete branches.

The Claude branch is substantially diverged from main and the existing PR is dirty.

Continue only on:

claude/nifty-ramanujan-w68f9z

unless I explicitly authorize another branch.

Do not force-push.

Do not rewrite history.

Preserve immutable evidence and decision records.

==================================================
18. DO NOT EXPAND THE PROGRAMME UNNECESSARILY
==================================================

Do not launch new architecture families.

Do not add speculative physics merely because it is interesting.

Do not add another optimizer unless an identified engineering decision requires it.

Do not add another requirements abstraction if an authoritative one already exists.

Do not keep generating documents that do not advance:

- bid readiness;
- hardware readiness;
- physical validation;
- Rust migration;
- architecture closure.

The repository is already governance-heavy.

From now on prefer:

fewer authoritative artifacts
+
better determining evidence
+
cleaner production code.

==================================================
19. WHAT I WANT YOU TO DO NOW
==================================================

Do NOT immediately start many lanes.

First give me a CURRENT-STATE STEERING REPORT based on the repository as it exists now.

It must contain:

A. CURRENT HEAD
- exact SHA
- CI status
- whether the current head is suitable as the pre-Rust bid-freeze candidate

B. ARCHITECTURE CONSISTENCY AUDIT
- every active code path inconsistent with hall_icp_neutralizer
- especially LaB6 / hollow-cathode / old architecture-selection paths
- classify each as historical, ground-reference, or active-flight inconsistency

C. PHYSICS / ASSESSMENT BOUNDARY
- remaining violations of:
  physics -> raw result
  assessment -> compliance
- exact files/functions
- whether removing each can change numerical physics

D. HARDWARE CRITICAL PATH
- exact first executable task
- exact blocker
- required owner input if any
- required external hardware/software if any

E. RUST MIGRATION INVENTORY
For every active Python production module:
- module/file
- role
- selected-architecture relevance
- retire vs migrate
- dependencies
- proposed Rust crate/module
- parity method
- migration priority

Do not count historical/document-only scripts as active simulator dependencies.

F. BID FREEZE
Identify the exact changes still required before the final pre-Rust bid baseline can be frozen.

G. STOP / CONTINUE
Separate findings into:

CAN DO NOW WITHOUT OWNER DECISION

NEEDS OWNER DECISION

NEEDS REAL-WORLD HARDWARE / EXTERNAL ACTION

DEFER UNTIL AFTER BID

Do not implement anything yet except harmless read-only analysis.

Wait for my approval after presenting this report.

==================================================
20. GOVERNANCE
==================================================

The ABEP / DRDO DEVELOPMENT GOVERNANCE — MASTER RULES remain binding.

Therefore:

- physics first;
- preregister before scoring;
- no post-hoc threshold changes;
- no invented data;
- no invented geometry;
- no invented mission ICD;
- no hidden defaults;
- fail closed;
- preserve provenance;
- preserve hashes;
- preserve immutable evidence;
- conservation remains a gate;
- distinguish measured, validated, derived, parametric and assumed evidence;
- do not convert “not evaluated” into “pass”;
- parallel execution only where dependencies genuinely permit.

If this directive conflicts with an older owner decision, the newer explicit decisions cited here supersede the conflicting portion only.

Everything else remains in force.
````

---

## Message 2 — STEERING_RESPONSE — 2026-10-04T09:15:53Z — text sha256 `e7d6787ab31e15222fbccedd61743820b471cbf95e0bd7d05f1cc3fea939044c`

````text
STEERING RESPONSE / OWNER DECISIONS TO CURRENT-STATE REPORT

I have reviewed the steering report.

Proceed according to the decisions below.

Do not make unrelated changes.

Current expected branch:
claude/nifty-ramanujan-w68f9z

Current reported HEAD:
103d3715b312c41e97a40a8d3c64c472deaa3bee

Before changing anything, confirm that HEAD has not moved.

==================================================
1. CI FLOATING-POINT FAILURE — APPROVED TO FIX
==================================================

Approve fixing tests/test_raw_assessment_split.py.

The current failure is cross-platform last-bit floating-point variation, not a physical-model difference.

Do NOT solve this by using a broad decimal tolerance.

Use a narrowly bounded floating-point identity rule.

For ordinary finite floating-point fields in these raw/assessment identity fixtures:

    abs(actual - reference)
        <= 4 * max(ulp(actual), ulp(reference))

or an equivalent explicitly documented <= 4 ULP comparator.

Requirements:

- integers remain exact;
- booleans remain exact;
- strings/enums remain exact;
- hashes remain exact;
- array shapes remain exact;
- key sets remain exact;
- NaN/inf semantics remain exact and explicit;
- no scientific acceptance threshold changes;
- no model coefficient changes;
- no golden scientific tolerance changes;
- no requirement/gate threshold changes.

This tolerance applies only to portability of numerically equivalent floating-point identity fixtures.

Record why it is required, including an example of the observed 1-ULP/last-bit GitHub-runner difference.

Also investigate the 6-skips-vs-5-skips result.

If the sixth skip is solely because the no-pymsis matrix leg intentionally lacks pymsis, make Rule-9 explicitly aware of the expected matrix-specific count:

with pymsis:
    expected existing baseline skip count

without pymsis:
    baseline + the explicitly identified pymsis-dependent skip

Do not simply allow arbitrary additional skips.

After the repair, require BOTH CI matrix legs to be green.

==================================================
2. ITEMS 3–5 — APPROVED FOR THE PRE-RUST FREEZE
==================================================

Approve merging the already-started implementation of:

Item 3:
separate the 12 mN operating/sizing target from the thrust compliance check.

Item 4:
decouple operating-scenario values from requirement regeneration.

Item 5:
move HC-05/06/07/08/10/11/12 criteria to the correct assessment/protection layer.

Conditions:

- no physics-number change;
- no model-equation change;
- no hidden threshold change;
- full tests pass;
- golden checks pass;
- configuration/hash checks pass;
- CI green.

HC-05 must use the approved uncertainty-aware form when determining evidence exists:

    M_n = I_e,cap / I_d,max,H1 - 1

    criterion:
    M_n,LB > 0

Do not substitute a simple point estimate
I_e,cap - I_d,max > 0
as the final acceptance criterion.

If uncertainty evidence does not yet exist:
    NOT_EVALUATED.

==================================================
3. AFI-01 — C1 MASS INSIDE FLIGHT AL-08
==================================================

APPROVE CORRECTION BEFORE THE BID FREEZE.

The selected flight architecture contains no C1 cathode and no conventional flight cathode.

Therefore C1 cathode-feed hardware must not remain inside the flight AL-08 mass.

Do NOT manually subtract a convenient number.

Trace the actual AL-08 terms and remove only items whose function exists solely for:

- C1;
- hollow-cathode Xe feed;
- C1 heater/keeper/cathode support.

Preserve any hardware genuinely required for:

- Xe contingency anode feed;
- Xe tank;
- regulation;
- isolation;
- flight valve/flow control;
- plumbing/mounting required by the cathodeless flight architecture.

Because this changes the flight mass result:

- preserve mass_power_a9_v3 as historical evidence;
- create the appropriate successor/rebased flight mass record rather than rewriting historical evidence;
- regenerate every directly affected bid/mass output;
- record old and new values and the exact reason for the change.

Do not compensate by arbitrarily reducing another subsystem.

==================================================
4. AFI-02 — PPU 6.0 kg ANALOG
==================================================

DO NOT NUMERICALLY REDUCE IT YET.

The existing 6.0 kg AL-07 value is contaminated by a legacy Hall-PPU analog that included C1 heater/keeper functions, but the repository has no defensible split.

Therefore:

retain 6.0 kg temporarily as a:

    PROVISIONAL_CONSERVATIVE_OWNER/ANALOG FLOOR

and explicitly record:

    CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE;
    REBASE_REQUIRED_FROM_CURRENT_LOAD/CONVERTER CBE.

It must NOT be described as a cathodeless-flight measured value or completed CBE.

Create/open the rebase action.

Do not invent the mass reduction.

==================================================
5. AFI-03 — P3 CATHODE NODE / CONTROL_FALLBACK
==================================================

The old P3/H2 thermal model must not be interpreted as the current flight thermal architecture.

Immediate action before bid:

- remove/correct any active/bid-facing statement that calls C1 a flight CONTROL_FALLBACK;
- state C1 = GROUND_REFERENCE_ONLY;
- explicitly prevent the cathode node from being used as determining flight thermal closure.

Do NOT rewrite historical P3 v2 evidence.

After the bid, create a successor cathodeless flight thermal model if required:

    Hall + RF/ICP neutralizer
    no hollow-cathode thermal node.

P3 v2 may remain historical/reference evidence.

==================================================
6. AFI-04 — GOLDEN USING hall_1stage / LaB6
==================================================

DO NOT rewrite the existing golden immediately before the bid.

Classify the existing LaB6-based golden path as:

    HISTORICAL_REGRESSION_COMPATIBILITY

It must not be used as:

- current flight architecture evidence;
- flight mass evidence;
- flight power evidence;
- architecture closure evidence;
- Rust production architecture definition.

Do not port its LaB6 logic into Rust.

After the bid, add a separately governed active golden/reference case for:

    hall_icp_neutralizer

without deleting the historical golden.

==================================================
7. AFI-05 — RVM-16 “KEEPER”
==================================================

APPROVE CORRECTION BEFORE BID FREEZE.

The current flight architecture has no conventional hollow cathode / keeper.

Correct derived/current-flight wording accordingly.

Use terminology appropriate to the actual architecture, for example:

    anode / RF-ICP electron-source-neutralizer /
    collector / plasma-facing and gas-path materials

Do not modify literal source/RFP text if the original source itself contains a term.

Preserve source wording in provenance and correct only the architecture interpretation / derived requirement wording.

Regenerate affected F9 and bid text.

No numerical status changes are implied by this wording correction.

==================================================
8. ARCHENGINE FLIGHT-GUARD GAP
==================================================

Do NOT spend pre-bid time repairing the entire historical archengine architecture enumerator.

The following old neutralizer/family paths are now historical architecture-trade machinery:

- lab6_xe
- mw_air
- rf_cathode
- ECR-Hall historical combinations
- gridded / nozzle / MPD / PIT / thermal families

For the BID:

ensure none of them is treated as the active flight architecture.

For the POST-BID programme:

retire them from the production dependency graph.

Do not delete historical implementations or evidence.

Do not port them to Rust unless a currently selected architecture actually requires the physics.

==================================================
9. GOLDEN “accelerators” CANONICAL LABEL
==================================================

Do not change the numerical golden immediately before the bid if doing so would force a golden rebaseline.

Record the LaB6-containing accelerator golden as:

    LEGACY / HISTORICAL REGRESSION
    NOT CURRENT FLIGHT CANONICAL

The eventual active canonical architecture golden must be cathodeless hall_icp_neutralizer.

Create that after the bid under the golden-change governance.

==================================================
10. LEGACY PYTHON MODULES
==================================================

APPROVE the retirement classification in section E.

However:

RETIRE != DELETE.

For modules classified historical/multi-family:

- keep source/history;
- remove them eventually from the production execution graph;
- do not port them to Rust;
- do not let the new Rust implementation inherit obsolete architecture merely for parity.

Parity is required only for physics that remains part of the active selected architecture.

Historical simulations remain reproducible from their historical commit/reference environment.

==================================================
11. FEMM — EXECUTION DECISION
==================================================

Use FEMM 4.2 on the Windows machine as the primary S7.1 solver.

Do not switch the authoritative S7.1 run to xFEMM/GetDP/Elmer at this stage.

An alternate solver may later be used as an independent cross-check, but not as a silent replacement.

For FeCo-2V / Hiperco-50-class material:

approve use of a published manufacturer/vendor B-H curve as:

    PROVISIONAL_ANALYSIS_MATERIAL_DATA

until the selected supplier / lot-specific data are available.

It is not qualification evidence.

The final hardware/design record must replace or bound it with supplier/lot evidence.

For the proposed FEMM analysis-point set:

approve the RP-1 anchor + six registered window-corner points for S7.1.

Approve 520–1040 A-turns only as:

    ANALYSIS_SWEEP_POINTS / MODEL EXPLORATION DOMAIN

not:

    hardware-rated operating limits,
    flight current limits,
    qualified coil limits,
    selected operating current.

Every analysis point must carry:

- geometry revision/hash;
- coil definition;
- ampere-turn value;
- material dataset/hash;
- boundary condition;
- mesh/convergence settings;
- FEMM version;
- solver settings.

S7.2 selects an engineering point only after S7.1.

Do not select using unvalidated thrust predictions.

==================================================
12. BID FREEZE SEQUENCE
==================================================

The freeze sequence is now:

STEP 1
Fix the narrow cross-platform CI identity-test issue.

STEP 2
Merge approved items 3–5.

STEP 3
Apply the bid-relevant architecture corrections:

- AFI-01 flight AL-08 rebase;
- AFI-05 keeper wording;
- correct current-flight C1 CONTROL_FALLBACK wording wherever bid-facing.

Do not perform unnecessary legacy refactors.

STEP 4
Regenerate directly affected artifacts.

STEP 5
Run:

- complete pytest suite;
- expected skip/xfail rule;
- golden checks;
- config/hash integrity;
- builders --check;
- CI integrity;
- GitHub CI on both matrix legs.

STEP 6
Only when all are green, create:

    bid_technical_baseline_v2

at the EXACT verified commit SHA.

The bid baseline must record:

- 26,280 h mission basis;
- current Xe mass from the corrected flight architecture;
- corresponding MEV from that same corrected calculation;
- AG-15 closed;
- frozen requirement basis;
- 196-state design-state set;
- empty robust upstream-set finding;
- hall_icp_neutralizer topology;
- no conventional flight cathode;
- AIR_PRIMARY;
- XE_CONTINGENCY;
- physical architecture status = INVESTIGATION_HYPOTHESIS;
- all unresolved performance items as NOT_EVALUATED /
  INCOMPLETE_EVIDENCE as applicable.

Do NOT copy the old 5.676 kg Xe / 49.96 MEV numbers into the new baseline unless they still reproduce after the approved architecture rebase.

The baseline must use regenerated current values, not manually carried numbers.

STEP 7
Regenerate the bid package from that exact SHA.

STEP 8
Record SHA as the immutable bid source even if repository infrastructure prevents creation of a Git tag.

Do not call a non-green SHA the final freeze.

==================================================
13. CURRENT CI
==================================================

At the time of my latest review, CI for 103d3715... had not yet completed.

Therefore do not freeze yet.

If HEAD moves while implementing these approved corrections, the freeze candidate becomes the NEW resulting SHA and must be fully verified again.

==================================================
14. PERFORMANCE BASELINE
==================================================

After the final pre-Rust bid SHA is frozen:

run the dedicated performance rerun on that exact SHA.

Do not use an earlier or later commit.

That run becomes:

    PRE_RUST_REFERENCE_BASELINE

for migration profiling and parity planning.

==================================================
15. RUST MIGRATION
==================================================

All substantive Rust migration remains AFTER the bid freeze.

Kernel 1 remains the admitted exception already completed.

After the freeze:

- use the performance run to order migration;
- migrate active selected-architecture physics only;
- retire historical architecture code instead of blindly porting it;
- preregister parity before each comparison;
- investigate discrepancies rather than retuning reference data.

Target remains:

ZERO PYTHON EXECUTION DEPENDENCY

for the final active simulator/toolchain.

HallThruster.jl remains the Hall solver.

==================================================
16. RFQs / F1 ARCHIVE
==================================================

The six quotation-only RFQ authorizations already recorded remain valid.

No PO / advance / supplier selection is authorized.

The F1 archive remains authorized for external/downloadable evidence storage.

Neither of these should delay the software bid freeze.

==================================================
17. WHAT TO DO NOW
==================================================

Do this sequentially.

Do NOT launch another broad set of lanes.

1. Confirm HEAD.
2. Finish the CI diagnosis/fix under item 1.
3. Show me:
   - exact CI/test change;
   - before/after comparison;
   - proof there is no numerical physics change.
4. Complete/merge items 3–5 after validation.
5. Apply AFI-01 and AFI-05 plus the bid-facing C1 wording correction.
6. Run full validation.
7. Report the exact candidate SHA and regenerated bid-critical numbers.
8. STOP for my final freeze approval.

Do not start the post-bid Rust waves yet.
Do not refactor legacy architecture families yet.
Do not alter main.
Do not merge PR #37.
Do not delete branches.
Do not rewrite history.
````

---

## Message 3 — RUST_PLAN_LAB6_RULE — 2026-10-04T09:45:23Z — text sha256 `f1cc6ef40fcadd76ca3ab9e46c4d4c8386cdbf59b117ca46b4b52192bebcba58`

````text
Correct. Keep the Rust migration-plan branch isolated until after the pre-Rust bid freeze.

Before that plan is ever merged, revise the conflicting LaB6 migration rule.

The old rule:

    "LaB6 paths are ported unchanged pending the audit"

is REJECTED and superseded.

Replace it with:

    "LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust simulator."

Migration classification shall be:

1. ACTIVE SELECTED-ARCHITECTURE PHYSICS
   -> migrate to Rust under preregistered parity/admission.

2. GROUND_REFERENCE-ONLY functionality
   -> migrate only if the future active test/evidence toolchain genuinely requires it;
      never include it in flight architecture execution.

3. HISTORICAL / LEGACY REGRESSION functionality
   -> do not port.
      Preserve its Python implementation and historical commit/evidence for reproducibility.

4. ACTIVE_FLIGHT_INCONSISTENCY
   -> do not port.
      resolve the inconsistency against hall_icp_neutralizer first,
      then migrate only the corrected selected-architecture implementation.

Specifically do NOT port as active flight functionality:

- LaB6Cathode;
- lab6_xe;
- Xe hollow-cathode heater/keeper logic;
- C1 flight-fallback logic;
- legacy Hall cards whose flight topology contains a hollow cathode;
- historical multi-family architecture-selection machinery merely for parity.

The active Rust architecture is:

    hall_icp_neutralizer

with:

    Hall accelerator
    + downstream RF/ICP electron-source / neutralizer
    + AIR_PRIMARY
    + XE_CONTINGENCY
    + no conventional hollow cathode.

Important parity rule:

Parity is required against the authoritative Python implementation of physics
that is RETAINED in the selected architecture.

Parity is NOT a requirement to preserve obsolete architecture errors or retired
hardware topology.

Where useful physical calculations are embedded inside legacy Python modules,
extract and parity-test only those architecture-independent physical kernels.
Do not port the surrounding obsolete LaB6/multi-family architecture logic.

Update the Rust migration inventory and dependency graph accordingly before the
plan is merged.

Do not merge the Rust plan now.

Current order remains:

1. wait for acce885 CI;
2. complete and validate items 3–5;
3. apply the approved pre-bid cathodeless corrections;
4. get full GitHub CI green;
5. establish the exact pre-Rust bid freeze SHA;
6. run the performance baseline on that SHA;
7. only then revise/review/merge the Rust migration plan;
8. then begin substantive Rust waves.

For now, continue waiting on CI and the items 3–5 job. Do not start additional work.
````

---

## Message 4 — CI_PORTABILITY_OPTION_A — 2026-10-04T10:01:02Z — text sha256 `564f7309e666da76556f7539cab7f22fb33dca629d6ba07f9ebed625edcd13b5`

````text
DECISION: APPROVE OPTION A, WITH THE FOLLOWING EXACT FORM.

Do not widen the generic ULP limit to 512 as the primary rule.

The purpose of this test is:

    cross-platform numerical identity of the same physics implementation

not:

    scientific acceptance tolerance.

Use two explicitly different classes of floating-point field.

==================================================
A1. NUMERICAL RESIDUAL / CLOSURE-NOISE FIELDS
==================================================

For quantities that are mathematically expected to be zero and whose remaining
value is floating-point cancellation / solver bookkeeping noise, such as:

    res_balance_residual_rel

do NOT compare ULP distance.

For these fields, use the already-governed residual interpretation:

    abs(value) <= 1e-14

for both the generated and reference values.

The identity test should therefore verify:

    abs(actual) <= 1e-14
    AND
    abs(reference) <= 1e-14

rather than require actual ≈ reference.

This is appropriate because values such as:

    9.07e-17
    3.48e-17

represent two numerically different roundoff residues of the same physically
closed balance.

This does NOT alter the conservation gate.

The actual conservation/closure gate remains independently enforced by its
governing criterion.

Do not silently apply this treatment to arbitrary fields.

Create an explicit allowlist of residual/noise fields.

Initially include only fields demonstrated to have this mathematical meaning.

==================================================
A2. ALL OTHER FINITE FLOATING-POINT RESULT FIELDS
==================================================

For ordinary finite result floats, cross-platform identity may use:

    relative difference <= 1e-13

BUT add a second guard:

    ULP distance <= 512

Both conditions must pass.

Therefore:

    PASS iff
        relative_difference <= 1e-13
        AND
        ulp_distance <= 512

except where actual == reference exactly.

This gives us:

- a relative scale guard;
- a binary floating-point-distance guard;
- protection against accidentally accepting a large discrepancy merely because
  the magnitude of the value is large.

The observed worst cases are currently approximately:

    xe_peak_mgps       ~251 ULP
    xe_aug_kg          ~227 ULP
    relative error     ~2.9e-14

so:

    512 ULP
    and
    1e-13 relative

provide limited portability headroom without becoming a scientific tolerance.

Important correction to the previous wording:

1e-13 is only about 3.4x larger than the currently observed worst relative
difference of 2.9e-14, not 1000x.

Record that correctly.

==================================================
A3. ZERO / NON-FINITE / NON-FLOAT VALUES
==================================================

Keep these strict:

- integer: exact
- boolean: exact
- string / enum: exact
- None/null: exact
- key sets: exact
- key order: exact where order is part of the fixture contract
- array/list shape: exact
- tuple/list distinction: exact
- NaN: only matches NaN where the fixture explicitly expects NaN
- +inf / -inf: exact sign and type
- hashes: exact
- IDs / schema versions: exact

For ordinary non-residual floats:

if one value is exactly zero and the other is not,
do not let a relative tolerance silently accept it.

Require exact zero unless that field is explicitly classified as a residual/noise
field under A1.

==================================================
A4. SAME-MACHINE TEST
==================================================

Preserve the same-process / same-machine identity checks as bit-exact where they
already are bit-exact.

Do not weaken those tests merely because cross-platform CI needs a portability
rule.

So the structure becomes:

same-process identity:
    bit exact

cross-platform fixture identity:
    A1 or A2, depending on explicitly classified field

scientific/golden acceptance:
    unchanged existing scientific criteria

==================================================
A5. TEST THE COMPARATOR ITSELF
==================================================

Add focused tests proving:

1. an observed ~251 ULP / 2.9e-14 relative difference passes;
2. >512 ULP fails even if relative error is below 1e-13;
3. relative error >1e-13 fails even if ULP count is somehow small;
4. residual values such as 9e-17 and 3e-17 both pass because each is <1e-14;
5. a residual value >1e-14 fails;
6. zero vs nonzero ordinary fields fail;
7. integer/bool/string/type differences fail;
8. NaN/inf rules remain exact.

==================================================
A6. NO SCIENTIFIC CHANGE
==================================================

Before merging, prove explicitly that this commit changes only:

- test portability logic;
- dependency locking if still required;
- documentation/history.

It must NOT change:

- raw physics outputs;
- model equations;
- coefficients;
- constraints;
- operating scenario values;
- design states;
- hard-gate thresholds;
- golden reference values;
- requirement status;
- architecture status.

Run both GitHub CI legs.

Required result:

pymsis absent:
    full suite green
    exactly 5 intended skips
    1 strict xfail
    Rule-9 green
    golden green

pymsis present:
    same required rule counts
    full suite green
    Rule-9 green
    golden green

Do not proceed to the bid freeze until BOTH legs are green.

==================================================
ITEMS 3–5
==================================================

Continue waiting for the items 3–5 isolated job.

Do not merge it until:

- this CI portability issue is closed;
- its own diff is reviewed;
- no numerical physics change is demonstrated;
- the full validation suite passes after combining it with the CI fix.

==================================================
RUST PLAN
==================================================

Keep Rust plan branch 3d705d2 isolated.

Do not revise/merge it yet except to preserve the known correction for later:

LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust
simulator.

No additional Rust work starts before the bid freeze and pre-Rust performance
baseline.
````

---

## Message 5 — ITEM3_MODIFIED_3A_AND_COUPLINGS — 2026-10-04T10:46:38Z — text sha256 `d06ca1d6d1f596a2b2443e0d2ea42c907dd3822d4c668443d4cf8421241b88cd`

````text
OWNER RULING — ITEM 3 + REMAINING OPERATING/CONSTRAINT COUPLINGS

1. ITEM 3 — APPROVE MODIFIED 3a

Use separate concepts for:

A. OPERATING TARGET
B. COMPLIANCE MINIMUM

Do not redefine the existing operating-target comparison into a compliance check.

Preserve the existing legacy value for backward compatibility, but stop treating it as the RFP/requirements compliance flag.

Current semantics:

    operating target met:
        T_air >= T_operating_target

For the row with:
    T_operating_target = 20 mN
    T_air = 13.66 mN

this remains:
    False

Add a separate assessment-only compliance flag:

    thrust_air_ge_sustained_min

with:

    thrust_air_ge_sustained_min =
        T_air >= thrust_sustained_min_mN

For that same row:

    13.66 >= 12
    => True

This is the correct result.

--------------------------------------------------
2. IMPORTANT: COMPLIANCE AGGREGATES MUST USE THE NEW FLAG
--------------------------------------------------

The new 12 mN compliance flag must be the one used by:

- RVM-02 mapping;
- RFP/compliance aggregation;
- technical_compliant / rfp_compliant as applicable;
- any hard-check list representing the 12 mN sustained requirement.

The old operating-target flag must NOT remain the compliance gate merely to avoid an assessment-status change.

Therefore some DERIVED ASSESSMENT RESULTS MAY LEGITIMATELY CHANGE.

That is acceptable.

This is a governed ASSESSMENT SEMANTIC CORRECTION, not a physics change.

Before merging, report exactly:

- every row whose new compliance flag differs from the legacy operating-target flag;
- every aggregate assessment result that changes because of it;
- old value;
- new value;
- reason.

Do not change raw physics fixtures.

--------------------------------------------------
3. EXISTING FLAG HANDLING
--------------------------------------------------

For bid compatibility, keep the existing output key temporarily if downstream consumers require it.

But classify/document it explicitly as:

    LEGACY_COMPATIBILITY:
    OPERATING_TARGET_MET

Remove its RVM-02 / requirement semantics.

Preferred explicit new key:

    thrust_air_ge_operating_target

You may either:

A. add this explicit key and keep the old key as a deprecated alias temporarily;

or

B. keep the old key only as the compatibility alias and document its real meaning.

Do not allow two different keys to claim the 12 mN compliance meaning.

The authoritative compliance key is:

    thrust_air_ge_sustained_min

Schema/version documentation must record this governed addition.

--------------------------------------------------
4. FIRING_LIFE_H — YES, DECOUPLE NOW
--------------------------------------------------

Approve moving the PHYSICS/OPERATING firing-duration basis into mission_scenario_v2 as an independent operating-scenario choice:

    firing_hours = 15000 h

with provenance:

    initial_basis = firing_life_h

This is an operating/integration choice used for things such as firing-integrated quantities.

Separately retain:

    HC-07 firing-life acceptance threshold = 15000 h

in:

    config/assessment/gate_thresholds_v1.json

The two happen to be numerically equal today, but they are semantically independent.

Required invariant:

Changing HC-07 threshold alone:
    MUST NOT change raw physics or firing-integrated results.

Changing firing_hours:
    MAY change raw physics / mission-integrated results
    and requires a new scenario version.

This should be included before the bid freeze if it produces no numerical change at the current value.

--------------------------------------------------
5. WET_MASS_MAX_KG — DO NOT MOVE INTO MISSION SCENARIO
--------------------------------------------------

Do NOT make the 40 kg wet-mass limit an operating-scenario input.

It is not a mission operating condition.

It belongs to:

    engineering constraint / assessment

The raw physics of a fixed design should calculate:

    mass = X kg

Assessment decides:

    X < 40 kg ?

If design-synthesis uses 40 kg as a generation/pruning filter, that is a DESIGN-GENERATION constraint, not a raw-physics input.

Therefore:

- keep wet_mass_max_kg in engineering/assessment constraints;
- remove it from the raw-physics operating-input seam where possible;
- do not copy it into mission_scenario_v2.

If a current design-search routine legitimately needs a mass ceiling for generation, keep that dependency explicitly in the DESIGN SYNTHESIS layer and document it.

Changing wet_mass_max_kg must not change raw physics for an already-defined design.

It may change:
    design acceptance,
    candidate filtering,
    Pareto population

but not:
    calculated mass,
    thrust,
    power,
    temperatures,
    flow,
    life.

Do not create a new config file before the bid unless one is actually needed.

--------------------------------------------------
6. ALTITUDE_BAND_KM — DO NOT MOVE INTO MISSION SCENARIO
--------------------------------------------------

Do NOT copy 180–230 km into mission_scenario_v2 as another independent operating choice.

The actual simulation environment is defined by the frozen design-state set:

    vleo_design_states_v2
    196 states

Raw physics consumes the states themselves.

The altitude-band requirement/domain is used to:

- validate the design-state set;
- define/trace the domain;
- assess compliance;
- govern future design-state-set generation.

It should not dynamically control physics after the state set is frozen.

Therefore:

    altitude_band_km
        remains a frozen domain/engineering constraint

while:

    design_states
        are the actual physics input.

Required invariant:

Changing the altitude compliance/domain threshold alone:
    MUST NOT alter raw results for the already frozen 196-state set.

Creating a different environment envelope:
    requires a NEW design-state-set version.

Do not silently regenerate the 196-state set from a changed altitude threshold.

--------------------------------------------------
7. FINAL LAYERING AFTER THIS CHANGE
--------------------------------------------------

The intended separation becomes:

MISSION / OPERATING SCENARIO
    mission_hours = 26280
    firing_hours = 15000
    xe_sizing_thrust_target_mN = 12
    commanded_thrust_cap_mN = 25
    p_bus_throttling_cap_W = 1500

DESIGN-STATE SET
    actual 196 atmosphere/orbit states

RAW PHYSICS
    thrust
    drag
    mass
    power
    thermal
    feed
    life quantities
    etc.

ENGINEERING / ASSESSMENT CONSTRAINTS
    sustained thrust >= 12 mN
    capability requirement
    P_bus < 1500 W
    wet mass < 40 kg
    firing-life threshold
    altitude-domain requirement
    HC gates
    etc.

ASSESSMENT
    compares raw results with constraints

This is the separation we want.

--------------------------------------------------
8. ITEMS 4 AND 5
--------------------------------------------------

Approve items 4 and 5 as described, subject to final combined validation.

Specifically approve:

- mission_scenario_v2;
- fixed scenario values with initial_basis provenance only;
- builder no longer copying them from constraints;
- mission_scenario_v1 preserved byte-identical;
- gate_thresholds_v1;
- HC-05 M_n,LB > 0;
- HC-12 = TBD_PENDING_MEASURED_H1 / NOT_EVALUATED;
- HC-05...HC-12 moved out of design code as described;
- HC-09 generation-filter exception remains under current Option 1.

--------------------------------------------------
9. CI STATUS
--------------------------------------------------

I have independently checked GitHub CI for:

    367f4fb93b1c114c1bcc44e91a82d8f89372567a

It is GREEN.

So the portability issue is closed.

Do not reopen or widen the floating-point tolerance unless new evidence demonstrates a different problem.

--------------------------------------------------
10. NEXT ACTION
--------------------------------------------------

Now:

1. apply this item-3 ruling;
2. apply the firing_hours decoupling;
3. do NOT move wet_mass_max_kg into mission scenario;
4. do NOT move altitude_band_km into mission scenario;
5. merge the validated items 3–5 work only after reviewing the final diff;
6. rerun:
   - full pytest;
   - 5 skips / 1 xfail rule;
   - golden;
   - CI integrity;
   - all affected builders --check;
   - GitHub CI;
7. report:
   - exact resulting SHA;
   - all assessment-only changes caused by item 3;
   - confirmation that raw physics is unchanged.

Then STOP before AFI-01 / AFI-05 / bid-baseline regeneration.
````

---

## Message 6 — ITEM3_PROCEED — 2026-10-04T10:50:24Z — text sha256 `445286d7208fbe214b71afceb79d95ba2d571216ce80a8ad16cdf11219528314`

````text
also Proceed as follows.

1. CURRENT ITEMS 4–5 MERGE

Keep validating local merged head c5078be.

If and only if all of these pass:

- full pytest;
- exactly 5 intended skips;
- exactly 1 strict xfail;
- rule-9;
- golden;
- CI integrity;
- config check;
- all affected builders --check;

then push the items 4–5 merge.

Do not modify it further merely to combine more work into the same commit.

This gives us a clean checkpoint.

==================================================
2. ITEM 3 — OWNER RULING IS MODIFIED 3a
==================================================

Item 3 is APPROVED as modified 3a.

Do NOT redefine the existing operating-target comparison.

Preserve the current legacy result:

    operating target met:
        T_air >= T_operating_target

Example:

    T_operating_target = 20 mN
    T_air = 13.66 mN

=> operating target met = False

Add a NEW assessment-only compliance result:

    thrust_air_ge_sustained_min =
        T_air >= thrust_sustained_min_mN

For the same example:

    13.66 >= 12

=> thrust_air_ge_sustained_min = True

==================================================
3. THE OLD FLAG MUST STOP CLAIMING RVM-02 SEMANTICS
==================================================

The existing `thrust_air_ge_req` result may remain temporarily for compatibility,
but its meaning is:

    LEGACY_COMPATIBILITY / OPERATING_TARGET_MET

It must no longer be treated as the 12 mN compliance check.

Preferred structure:

    thrust_air_ge_operating_target
        = T_air >= operating target

    thrust_air_ge_sustained_min
        = T_air >= sustained minimum constraint

If downstream compatibility requires the old key:

    thrust_air_ge_req

keep it only as a deprecated compatibility alias of:

    thrust_air_ge_operating_target

Do not let both old and new flags claim the same requirement meaning.

==================================================
4. COMPLIANCE AGGREGATES MUST USE THE NEW FLAG
==================================================

RVM-02 and the actual 12 mN compliance aggregation must use:

    thrust_air_ge_sustained_min

Therefore:

- raw physics MUST NOT change;
- legacy operating-target values remain unchanged;
- some assessment/compliance aggregates MAY legitimately change.

That is acceptable.

This is a governed assessment-semantic correction.

Before merge, report every affected row:

- configuration identity;
- T_air;
- operating target;
- sustained minimum;
- old operating-target result;
- new compliance result;
- any aggregate status that changes.

Do not hide assessment changes merely to preserve identity fixtures.

Raw-physics identity fixtures remain unchanged.

Assessment schema/version must explicitly record the new semantic field.

==================================================
5. FIRING HOURS — COMPLETE ITEM-4 SEPARATION NOW
==================================================

Also complete the previously approved firing-hours decoupling before AFI work.

mission_scenario_v2 shall carry:

    firing_hours = 15000

as:

    OPERATING_SCENARIO_CHOICE

with provenance only:

    initial_basis = firing_life_h

This is the firing/integration duration used by physics and mission-integrated quantities.

Separately:

    HC-07 firing-life threshold = 15000 h

remains in:

    config/assessment/gate_thresholds_v1.json

These values happen to be equal today but are semantically independent.

Required test:

changing HC-07 threshold alone:
    changes assessment only
    does NOT change raw physics

changing mission_scenario firing_hours:
    may change firing-integrated physics
    requires a new scenario version

Do not move wet_mass_max_kg into the mission scenario.

Do not move altitude_band_km into the mission scenario.

==================================================
6. VALIDATION AFTER ITEM 3 + FIRING HOURS
==================================================

Implement item 3 and firing_hours as a separate controlled commit after the
items 4–5 checkpoint is pushed.

Then run:

- full pytest;
- exactly 5 skips;
- exactly 1 xfail;
- rule-9;
- golden;
- CI integrity;
- config/hash checks;
- all affected builders --check;
- GitHub CI on all jobs.

Report:

A. exact SHA;
B. proof raw physics is unchanged;
C. list of assessment-only changes from item 3;
D. confirmation that firing_hours is now independent from HC-07;
E. confirmation that wet_mass_max_kg and altitude_band_km remain outside the
   operating scenario.

Push only after all checks are green.

==================================================
7. ONLY THEN START AFI CORRECTIONS
==================================================

After item 3 + firing_hours is pushed and green, proceed to:

- AFI-01:
  remove only C1/hollow-cathode-only hardware from the current flight AL-08
  mass through a successor/rebased mass record;

- AFI-05:
  correct the flight "keeper" wording;

- bid-facing C1 CONTROL_FALLBACK:
  correct to GROUND_REFERENCE_ONLY.

Do not start AFI-01 before item 3/firing-hours separation is complete.

==================================================
8. BID FREEZE ORDER
==================================================

The intended sequence is now:

367f4fb
    CI portability green
        ↓
c5078be
    items 4–5 checkpoint, after validation/push
        ↓
item 3 + firing_hours decoupling
    validated and pushed
        ↓
AFI-01 + AFI-05 + C1 wording correction
        ↓
regenerate affected artifacts
        ↓
full validation / GitHub CI
        ↓
candidate pre-Rust bid SHA
        ↓
owner freeze approval
        ↓
performance baseline
        ↓
Rust migration plan revision and post-bid migration

Do not begin substantive Rust work before this sequence completes.
````

---

## Message 7 — ITEM3_ACCEPTED_SCENARIO_VERSIONING — 2026-10-04T11:15:40Z — text sha256 `dc8575c772a4bcd963de7f545d5661ebfaa9bb9deb915d6cb21fb2e1805e59ce`

````text
OWNER REVIEW — ITEM 3 / FIRING-HOURS WORK ACCEPTED

I accept commit:

46f7060a34200f9c72384c795311fc551f6ea17a

subject to GitHub CI completing green on that exact SHA.

The item-3 semantics are approved:

- thrust_air_ge_operating_target = operating-target comparison;
- thrust_air_ge_sustained_min = authoritative 12 mN compliance comparison;
- legacy thrust_air_ge_req may remain only as a deprecated compatibility alias
  for the operating-target result;
- RVM-02 and hard compliance use thrust_air_ge_sustained_min.

The reported row-112 difference is accepted as a governed assessment-semantic
correction:

T_air = 13.66 mN
operating target = 20 mN -> FALSE
sustained minimum = 12 mN -> TRUE

No raw physics changed.

The firing-hours separation is also approved:

mission_scenario_v2.firing_hours = 15000 h
    = operating/integration choice

HC-07 threshold = 15000 h
    = independent assessment threshold

The demonstrated test that HC-07 can move to 20,000 h without changing raw
physics or firing_hours is exactly the invariant we wanted.

Wet-mass and altitude handling are also approved:

- wet_mass_max_kg remains an engineering/assessment/design-generation
  constraint, not a mission-scenario operating input;
- altitude_band_km remains the frozen domain requirement;
- the actual raw-physics environmental input is the frozen 196-state design
  set.

MISSION SCENARIO VERSIONING RULING:

Accept the current in-place development revision of mission_scenario_v2.

Do NOT create v3 solely to undo this before the bid freeze.

Reason:
- v2 had not yet become the final frozen bid configuration;
- the exact Git history and sha256 preserve the earlier revision;
- no operating numerical value changed;
- the revision is explicitly recorded.

However, once the final pre-Rust bid baseline is frozen:

mission_scenario_v2 becomes immutable.

Any later semantic change to the operating scenario must create:

mission_scenario_v3

rather than modifying v2 in place.

NEXT STEP:

Do nothing further until GitHub CI for 46f7060 is fully green.

When it is green, proceed with the already-approved narrow pre-bid architecture
corrections only:

1. AFI-01
   Rebase flight AL-08 by removing only hardware/function mass that exists
   solely for C1 / conventional hollow-cathode support.

   Preserve:
   - Xe contingency tank;
   - regulation;
   - flight valves;
   - Xe anode/feed functionality required by the selected cathodeless flight
     architecture;
   - required plumbing/mounting.

   Do not subtract an arbitrary mass.

   Create a successor/rebased mass record.
   Do not rewrite historical mass_power_a9_v3.

2. AFI-05
   Remove current-flight "keeper" terminology where it incorrectly implies a
   conventional flight cathode.

   Do not alter verbatim source/RFP text.
   Correct only derived/current-architecture language.

3. C1 CONTROL_FALLBACK wording
   Any current/bid-facing use of C1 as CONTROL_FALLBACK must become:

       GROUND_REFERENCE_ONLY

   C1 must not enter:
   - flight architecture;
   - flight mass;
   - flight power;
   - flight Xe;
   - flight thermal closure;
   - fallback flight configuration.

Do NOT perform AFI-02 numerical PPU reduction now.

Do NOT rewrite historical LaB6 goldens now.

Do NOT refactor archengine or legacy propulsion families now.

Do NOT start Rust work.

After the three approved corrections:

- regenerate all directly affected artifacts;
- run full pytest;
- require exactly 5 skips / 1 xfail;
- run Rule-9;
- run golden;
- run CI integrity;
- run config/hash validation;
- run every affected builder --check;
- run GitHub CI.

Then report before freezing:

A. exact candidate SHA;

B. AFI-01 mass decomposition:
   old AL-08
   each removed C1-only component
   retained Xe-flight components
   new AL-08
   resulting dry/wet mass values;

C. every AFI-05/C1 wording change;

D. all bid-critical numbers that changed;

E. confirmation that no raw propulsion physics changed;

F. final unresolved NOT_EVALUATED / INCOMPLETE_EVIDENCE items.

Then STOP.

Do not create bid_technical_baseline_v2 until I approve that candidate SHA.
````

---

## Message 8 — FINAL_PRE_BID_AFI_RESOLUTION — 2026-10-04T16:31:16Z — text sha256 `a48dfcbb9fa33421bf19ff45fa241070c22a8379a3eb4e887b661fb8ceb93624`

````text
OWNER DECISIONS — FINAL PRE-BID AFI RESOLUTION

I have reviewed candidate:

4c2b3b3e7175f47f08c1c350355772a332073b69

I accept it as the VERIFIED ENGINEERING CANDIDATE.

GitHub CI is green and the reported numerical state is accepted.

It is NOT yet the final technical freeze SHA because AFI-01-S1 and AFI-05-S1
must be converted from pending-owner states into resolved owner decisions.

Apply the following decisions.

==================================================
1. AFI-01-S1 — KEEP THE SECOND LATCH
==================================================

DECISION:

KEEP the second 0.170 kg latch valve.

The flight Xe valve architecture is therefore:

    latch isolation valve #1
        +
    latch isolation valve #2
        +
    one proportional flow-control valve

The two latch valves implement the already-approved:

    dual series isolation on the high-pressure Xe path

Do NOT remove the second latch merely because its historical mass provenance
came from the old cathode-feed branch.

Its FUNCTION in the current architecture is now:

    SECOND SERIES FLIGHT XE ISOLATION VALVE

not:

    C1 / cathode-feed valve.

Therefore current AL-08 remains:

    valves CBE = 0.455 kg
        0.170 latch #1
      + 0.170 latch #2
      + 0.115 PFCV

    AL-08 CBE floor = 4.929 kg

    AL-08 MEV planning floor = 5.9148 kg

Do not use:

    5.7108 kg

because that would leave the flight Xe path below the approved dual-series
isolation architecture.

Update the mass record so the second latch is no longer described operationally
as a cathode-branch component.

Its historical provenance may state that its mass originated from the earlier
two-branch analog, but its CURRENT FUNCTION is flight Xe series isolation.

This distinction is important.

No conventional hollow-cathode hardware remains in flight AL-08.

The removed 0.115 kg PFCV remains removed because that valve existed solely for
cathode-feed metering.

==================================================
2. AFI-05-S1 — DO NOT RE-FREEZE THE RVM-16 BASIS
==================================================

DECISION:

Do NOT alter/re-freeze the A9.22 G3 frozen RVM-16 requirement basis.

Preserve verbatim:

- the frozen RVM-16 title;
- frozen requirement text;
- frozen-basis hash;
- official RFP provenance.

The current-architecture reading is the correct mechanism.

Approve the present current-architecture reading with this clarification:

For hall_icp_neutralizer:

    there is no flight keeper.

Therefore references to the historical flight keeper are not interpreted as
requiring a keeper.

The current materials interpretation is:

    atomic-oxygen / oxygen compatibility applies to the actual
    AO/O-exposed components of the selected architecture, including as
    applicable:

    - anode;
    - RF/ICP electron-source / neutralizer plasma-facing surfaces;
    - collector / bias electrode where applicable;
    - gas-path surfaces;
    - other AO/O-exposed plasma-facing parts.

OWNER CONFIRMATION OF GRAPHITE READING:

Do not use graphite as the CURRENT FLIGHT BASELINE for an O/AO-exposed
plasma-facing or electron-source surface until appropriate erosion /
oxidation coupon evidence supports it.

This is NOT a universal prohibition on graphite everywhere in the system.

Graphite outside the relevant O/AO exposure environment is not excluded by this
decision.

Final materials remain evidence-dependent.

Change the status of the present:

    RECORDER_INTERPRETATION_OWNER_MAY_REVERSE

to an appropriate:

    OWNER_CONFIRMED_CURRENT_ARCHITECTURE_READING

or equivalent repository vocabulary.

Do NOT change requirement compliance status because of this interpretation.

==================================================
3. C1 STATUS
==================================================

The implemented current status is confirmed:

    C1 = GROUND_REFERENCE_ONLY

C1 is NEVER:

- flight hardware;
- a flight fallback;
- a flight electron source;
- flight Xe hardware;
- flight mass;
- flight power;
- flight thermal load;
- flight architecture closure.

Historical CONTROL_FALLBACK text remains only when explicitly labelled
historical/verbatim provenance.

Do not rewrite immutable historical records.

==================================================
4. AFI-03
==================================================

Confirm the implemented handling.

The inherited P3 cathode thermal node is:

    NOT_USABLE_FOR_FLIGHT_THERMAL_CLOSURE

for hall_icp_neutralizer.

Do not rewrite P3 v2 before the bid.

A successor cathodeless thermal model is post-bid work.

==================================================
5. RFQ3-GAS — REVISE, BUT PRESERVE V3
==================================================

Do not overwrite the authorized RFQ v3 historical package.

Create the smallest governed successor revision / addendum permitted by the
repository conventions for RFQ3-GAS.

The active RFQ context must no longer present:

    AL-08 MEV = 6.0528 kg
    AL-08 CBE = 5.044 kg

as the current planning values.

Update current context to:

    AL-08 CBE planning floor = 4.929 kg
    AL-08 MEV planning floor = 5.9148 kg

and explicitly state:

    PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN

because:

- plumbing remains TBD;
- mounting/thermal remains TBD;
- quotations still replace/rebase provisional component floors.

The supplier quotation split itself remains:

- tank;
- regulator;
- two series isolation latches;
- anode/Xe-contingency proportional flow control;
- plumbing;
- mounting/thermal;
- other explicitly classified items.

C1-specific quotation lines remain:

    GROUND_ONLY_LAB_EQUIPMENT

and must never be included in flight AL-08.

Important:

5.9148 kg is an INTERNAL PLANNING FLOOR.

It is NOT a supplier maximum-mass requirement unless separately approved.

Suppliers should state their offered component masses.

If RFQ3-GAS has NOT yet been externally sent:
    dispatch only the revised successor package.

If the old RFQ3-GAS has already been externally sent:
    preserve it and issue the revised information as a controlled addendum.

Do not change the other five authorized RFQ packages merely because GAS has a
new revision.

==================================================
6. BID MASS BASIS — USE MASS_POWER_A9_V4
==================================================

DECISION:

The current bid technical baseline shall use:

    docs/budgets/mass_power_a9_v4

as the active flight mass source.

Do NOT use the old card-closure values:

    Xe = 5.676 kg
    MEV = 49.96 kg

as current hall_icp_neutralizer flight-design numbers.

Those values came from the legacy card-based closure and are not the current
cathodeless flight mass architecture.

Preserve them only as historical/model-regression provenance where required.

==================================================
7. XE LOAD IN THE BID
==================================================

Do NOT select 5.676 kg Xe merely because the legacy simulator produced it.

The current flight Xe load is NOT YET FROZEN.

Carry the existing loaded-Xe cases as SENSITIVITY / PLANNING CASES:

    2 kg
    5 kg
    10 kg

Do not describe any of these as the final selected Xe load.

Use the current v4 planning results:

    nominal dry before system margin:
        33.8101 kg

    20% system margin:
        6.7620 kg

    dry known-line planning mass:
        40.5721 kg

Sensitivity cases:

    + 2 kg Xe:
        42.5721 kg

    + 5 kg Xe:
        45.5721 kg

    + 10 kg Xe:
        50.5721 kg

These remain:

    DOES_NOT_CLOSE

against the current conservative <40 kg wet interpretation.

Do not hide that result.

Also do not describe these values as complete CBE because several lines remain
allocations / analog floors / TBD.

Use terminology such as:

    CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR

where appropriate.

==================================================
8. BID MASS WORDING
==================================================

The bid shall continue to accept the <40 kg requirement as a design target /
requirement.

Do NOT claim that current determining evidence has already demonstrated mass
compliance.

The technical status should remain equivalent to:

    MASS COMPLIANCE:
    INCOMPLETE_EVIDENCE / NOT YET CLOSED

with an active mass-reduction / quote-based rebase task.

Do not convert a provisional overweight internal budget into a false PASS.

Do not relax the requirement.

==================================================
9. AL-07
==================================================

Keep AL-07 at:

    6.0 kg

for this freeze.

Its status remains:

    PROVISIONAL_CONSERVATIVE_ANALOG_FLOOR

with the explicit note that the analog includes legacy functions not present in
the cathodeless architecture.

AFI-02-RA1 remains open.

Do not invent a reduction before a current-load/PPU CBE exists.

==================================================
10. OWNER DECISION RECORDING
==================================================

Record THIS owner decision as a governed owner-decision record before the
technical freeze.

Also record the other explicit 2026-10-04 owner directives required to explain
the current repository state, including:

- Rust target = zero Python active execution dependency;
- LaB6 / conventional hollow-cathode active paths are NOT ported to Rust;
- CI portability comparator decision;
- physics / assessment separation;
- modified item-3 ruling;
- firing-hours / scenario separation;
- mission_scenario_v2 post-freeze immutability rule;
- AFI decisions above.

Do not fabricate "verbatim owner text" from paraphrases.

Where exact owner-message text is available, it may be preserved verbatim.

Where it is not, record:

    OWNER_DECISION_SUMMARY

with provenance to the session / implementing commits.

Historical decisions remain immutable.

==================================================
11. RESOLVE THE CURRENT STOP STATES
==================================================

Update current artifacts so:

AFI-01-S1:
    OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH

AFI-05-S1:
    OWNER_CONFIRMED_CURRENT_ARCHITECTURE_READING

Neither should remain TBD_OWNER / OWNER_MAY_REVERSE.

Do not change numerical physics.

==================================================
12. FREEZE SHA — 4c2b3b3 IS NOT YET THE FINAL SHA
==================================================

I approve:

4c2b3b3e7175f47f08c1c350355772a332073b69

as the VERIFIED PRE-FREEZE ENGINEERING CANDIDATE.

I do NOT approve it as the final technical freeze SHA because the current
records still contain the two pending-owner states being resolved by this
message.

Create a narrow successor commit containing:

- these owner-decision records;
- AFI-01-S1 resolution;
- AFI-05-S1 resolution;
- current mass-record status update;
- current RVM interpretation status update;
- RFQ3-GAS successor revision if it is part of this controlled update;
- no raw-physics changes.

Then run full verification again.

That SUCCESSOR SHA becomes the candidate for:

    FINAL_PRE_RUST_TECHNICAL_SOURCE

==================================================
13. BID PACKAGE ASSEMBLY — TWO-SHA DISCIPLINE
==================================================

Avoid a self-referential freeze-record problem.

Use two clearly distinguished SHAs:

A. TECHNICAL SOURCE SHA

The fully validated successor described above.

This is the commit whose:

- code;
- configs;
- architecture;
- engineering records;
- numerical outputs

define the bid technical source.

B. PACKAGE / FREEZE-RECORD SHA

A later docs/generated-output commit may contain:

- bid_technical_baseline_v2;
- regenerated bid package;
- compliance matrix;
- technical approach;
- risk register;
- baseline manifest.

Those files shall PIN the exact TECHNICAL SOURCE SHA.

The package commit does not silently become a different technical source merely
because generated bid documents were added.

This prevents circular self-hashing.

==================================================
14. REGENERATE THE BID PACKAGE
==================================================

After the TECHNICAL SOURCE SHA is fully green:

create bid_technical_baseline_v2 pinned to that SHA.

Regenerate the bid package from current sources.

The package must no longer carry the old bbc480c mass values.

Update, as applicable:

- compliance matrix;
- technical approach;
- risk register R-07;
- mass tables;
- current architecture wording;
- C1 status;
- RVM/current-reading references.

Current mass source:

    mass_power_a9_v4

Current AL-08:

    5.9148 kg MEV planning floor

Current architecture:

    hall_icp_neutralizer

Current flight cathode:

    NONE

Current C1 role:

    GROUND_REFERENCE_ONLY

Current architecture status:

    INVESTIGATION_HYPOTHESIS

Current robust upstream set:

    EMPTY

Mass:

    NOT CLOSED / INCOMPLETE EVIDENCE

Do not silently convert NOT_EVALUATED or INCOMPLETE_EVIDENCE gates to PASS.

==================================================
15. NETWORK-DEPENDENT BUILDER
==================================================

The pre-existing inability to run:

    build_tables_nist107_o.py

because this container has no network access does NOT by itself block the
freeze if:

- that builder/source was not changed by this work;
- its inputs/hashes are unchanged;
- the failure is the same external-network limitation seen before;
- no generated artifact depending on a newly fetched source is being claimed.

Record it explicitly as:

    NOT_RERUN_NETWORK_UNAVAILABLE
    UNAFFECTED_BY_FREEZE_CHANGES

Do not fabricate or refresh its external data.

==================================================
16. VALIDATION FOR THE TECHNICAL SOURCE SHA
==================================================

After applying only the narrow owner-resolution changes, run:

- full pytest;
- exactly 5 expected skips;
- 1 strict xfail;
- Rule-9;
- golden;
- CI integrity 11/11;
- config/hash checks;
- every affected builder --check;
- F7/F8;
- F9;
- GitHub CI on all jobs.

Confirm:

- no raw physics changed;
- F7/F8 Pareto set unchanged;
- robust set still empty;
- only owner-status / documentation / active mass interpretation changed.

Then report the exact TECHNICAL SOURCE SHA.

STOP for final technical-source approval before generating the final bid package
if anything numerical differs from the values approved above.

If there is no numerical difference and every check is green, you may proceed
to build bid_technical_baseline_v2 and the package pinned to that exact source
SHA.

==================================================
17. PERFORMANCE BASELINE / RUST
==================================================

After the technical source is frozen and the package is complete:

run the dedicated PRE_RUST_REFERENCE_BASELINE on the exact TECHNICAL SOURCE SHA.

Then revise the isolated Rust migration plan so:

LaB6 / conventional hollow-cathode paths are NOT ported into the active Rust
simulator.

Only after that begin post-bid Rust migration.

No substantive Rust work before the bid freeze.
````

