# SIMULATION COMPLETION — NEXT BATCH OWNER RULINGS (A9.31) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-06 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_06_A9_31_next_batch_owner_rulings_and_architecture_proof.json`. Immutable after commit.

---

## Message 1 — NEXT_BATCH_OWNER_RULINGS_AND_ARCHITECTURE_PROOF — 2026-10-06T17:32:29.791Z — text sha256 `ab7705efeb0835b9443cebd86018cd5c29bdbc3f29d6f618c147dab1e7dec75a`

````text
SIMULATION COMPLETION — NEXT BATCH OWNER RULINGS

Live checkpoint independently verified:

integration/simulation-complete
d5ace89c685b6ffbe96fc88402147fb68a215200

GitHub Rust workspace CI:
GREEN

Proceed immediately.

Do not wait for another general owner review.

==================================================
1. CLI ACCEPTANCE V1 -> V2
==================================================

APPROVED.

acceptance_v1 remains immutable history.

acceptance_v2 is the active NI-ABEP-CLI acceptance contract because:

- the defect in v1 was identified before any scored v1 acceptance run;
- REF-02 in v1 would have required reporting a false manifest hash;
- v1 was not rewritten;
- v2 was preregistered before its scored run;
- v2 did not remove or weaken a failed scored case.

Keep both records.

Do not rewrite v1.

NI-ABEP-CLI v2 acceptance remains authoritative.

==================================================
2. MATERIALS DATABASE / WORK-PACKAGE LOCATION
==================================================

APPROVE the materials-database admission performed in SC-WP-08.

The work-package allocation is organisational; it does not invalidate an
admission performed under a valid contract.

Do NOT rewrite component_inventory_v3_1.

Instead, migration_state records:

    component admitted during SC-WP-08
    inventory planning owner = SC-WP-12

with the exact parity/admission evidence.

There must be only one authoritative Rust implementation.

==================================================
3. K-GAS-LIFE
==================================================

APPROVE:

    AUDITED_NOT_EXTRACTED

because the audit found no active selected-architecture consumer.

Do NOT port dead code merely for completeness.

If an active consumer appears later:

    STOP that dependency;
    preregister the extracted kernel;
    establish parity / independent verification;
    only then admit it.

==================================================
4. NP-RELIABILITY
==================================================

Do NOT invent the missing flight RBD.

Do NOT select a handbook failure rate merely to close the model.

Proceed with the generic Rust reliability engine under the committed
NP-RELIABILITY preregistration.

Verify it using analytic / synthetic cases for:

- exponential reliability;
- Weibull reliability where registered;
- serial RBD;
- explicit parallel/redundant RBD;
- limiting cases;
- deterministic propagation;
- uncertainty bounds.

For the actual hall_icp_neutralizer flight configuration:

    R_item = INCOMPLETE_EVIDENCE
    R_rbd = NOT_EVALUATED

until a registered flight RBD and sourced parameter records exist.

The structural RBD may only contain topology explicitly supported by the
selected architecture.

Do NOT infer redundancy.

Two series Xe isolation latches are not automatically reliability redundancy;
their failure-mode semantics must be registered before an RBD treats them as
such.

For electronics rates:

    no default MIL-HDBK-217 / FIDES values.

A handbook may later be used only through a governed evidence record containing:

    edition;
    exact locator;
    parts-stress assumptions;
    environment;
    temperature;
    quality class;
    applicability;
    uncertainty;
    evidence level.

NP-RELIABILITY software completion therefore does NOT require an evaluated
flight reliability number.

==================================================
5. PLENUM / FEED TRANSIENT CONTRACT
==================================================

Do NOT leave transient_run / transient_case permanently outside the Rust
migration.

The v2 parity record correctly removed them because the v1 transient contract
was defective.

Create:

    C-ABEP_SIM_DESIGN_PLENUM_FEED_PY
    parity contract v3

before any new scored transient comparison.

Do NOT choose an arbitrary owner tolerance.

Use a preregistered convergence-derived tolerance procedure:

1. freeze an independent development/refinement grid;
2. run both implementations at registered nominal and tightened solver
   tolerances;
3. estimate each implementation's numerical discretisation envelope;
4. freeze that envelope BEFORE the held-out scored vectors are run;
5. score common physical observables at registered physical sample times;
6. cross-implementation difference must lie inside the combined registered
   numerical envelope plus the existing floating residual allowance.

Do NOT score adaptive-solver internals as physics:

    nfev
    internal segment decomposition
    iteration count

unless they are explicitly part of a deterministic algorithm contract.

Still require:

- mass conservation;
- pressure / mass non-negativity;
- valve saturation semantics;
- event ordering;
- final state;
- transient extrema;
- domain/status parity.

This closes the transient-tolerance owner issue without inventing a magic
numeric tolerance.

==================================================
6. INTAKE INTERPOLANT — B2-OF-01
==================================================

Do NOT regenerate or smooth intake_surface_v1.

Do NOT change the admitted Rust interpolation merely to make the surface appear
nicer.

The frozen reference is:

    SciPy / Qhull LinearNDInterpolator semantics

and the Rust port correctly reproduces it.

Therefore B2-OF-01 is accepted as a KNOWN NUMERICAL PROPERTY OF THE FROZEN
REFERENCE, not as physical truth.

For normal raw-physics parity:

    preserve the exact deterministic frozen interpolation.

For SC-WP-10 F7/F8 / UQ:

add a separate numerical-sensitivity diagnostic for a candidate lying exactly
on one of the known degenerate internal faces.

Do not use an arbitrary epsilon.

Determine an exact-face condition from the canonical frozen grid coordinates.

For an exact-face candidate:

    retain the authoritative frozen result;
    additionally compute/report the adjacent-simplex ambiguity envelope where
    feasible;
    classify that envelope as NUMERICAL_INTERPOLATION_SENSITIVITY.

Never retune the optimizer to hide it.

Do not mark a candidate robust merely because one triangulation branch is
favourable.

No effect on the already-admitted default points, whose recorded spreads are
at floating-noise level.

==================================================
7. ICP -> THERMAL INTERFACE
==================================================

OWNER DECISION:

Create matched interface v2.

Do NOT accept the current approximation that sends the entire residual to
B_PPU_RF.

The physically separated quantities already exposed by NP-ICP shall be consumed
at their proper destinations.

Approve the additional ICP thermal keys including:

    reflected RF power;
    line loss;
    matching loss;
    antenna-circuit / coil loss;
    absorbed plasma power;
    collector-bias power;
    collector-bias deposition;
    exported bias power;
    upstream carried-out power;
    downstream carried-out power.

Approve the per-surface convention:

    Q_j = L_j + C_j

subject to the registered sign convention and conservation check.

Thermal mapping:

    RF-source / conversion losses -> B_PPU_RF or appropriate electronics node;
    collector deposition -> N_COLLECTOR;
    upstream plasma/outflow energy -> registered H-1-facing receiver / interface;
    downstream exported power -> EXPORT, not internal heat;
    bias export -> EXPORT;
    only true PPU conversion loss -> PPU heat.

No energy may disappear.

No term may be double-counted.

Preserve IF-ICP-THERMAL-v1 and NP-THERMAL-CATHODELESS v1 as immutable history.

Create versioned v2 records.

==================================================
8. ICP -> BUS INTERFACE
==================================================

Use bus_power_boundary_a9_v2.

Create a matched IF-ICP-BUS-v2 only if needed to make the v2 thermal interface
and active ledger mapping explicit.

Do not reopen the old A5 bus boundary.

Flight conventional cathode heater / keeper:

    NONE.

Raw bus ledger contains physical loads only.

The RFP 1.5 kW value stays in assessment, never raw power physics.

==================================================
9. NP-ICP PF-01 / PF-02 / GAP-01..05
==================================================

Do NOT close these by an owner choosing unsourced physical constants.

Do NOT patch v1 with ad-hoc addenda that merely make the code admissible.

Create:

    NP-ICP-NEUTRALIZER preregistration v2

for the equation / bookkeeping defects:

    PF-01 recombination-factor ambiguity
    PF-02 background inflow without residence/conductance basis
    GAP-01 neutral-energy split
    GAP-02 atom-formation-energy disposal
    GAP-03 CARRIED_OUT partition
    GAP-04 multi-species H-LIEB treatment
    GAP-05 registered-table scan / normalisation acknowledgement

v1 and its reports remain immutable.

v2 must resolve each item from:

    conservation;
    dimensional consistency;
    registered physical source;
    explicit bounding branch;

not from an invented point value.

Where the physics cannot yet identify a unique split:

    use a registered bounding pair / interval,
    or return INCOMPLETE_EVIDENCE.

Do not use 50/50 splits or other convenience assumptions.

INT-16 is APPROVED:

    registered-table T_e scan ends at the highest temperature admitted by all
    required registered tables.

Do not extrapolate beyond table validity.

INT-17 is APPROVED:

    ion formation energy uses the least-energy registered formation route for
    consistency checks, while route identity remains traceable.

INT-18 is APPROVED:

    reused-table source representations live under xs/ with capture id,
    builder/source/table hashes and provenance.

==================================================
10. ICP ASSESSMENT USE
==================================================

OQ-NPICP-02:

A VERIFIED but not bench-validated model-derived I_e,cap does NOT satisfy HC-05.

HC-05 stays:

    NOT_EVALUATED

outside a VALIDATED_BENCH domain cell.

Measured I_e,cap supersedes the model at the measured point.

OQ-NPICP-03:

Do NOT invent a Hall-parameter or gyroradius threshold.

Report:

    omega_ce / nu_m
    r_ce / R

but keep the affected capacity result INCOMPLETE_EVIDENCE until a sourced
criterion is registered.

OQ-NPICP-04:

The existing completeness-audit methodology may be reused as a SCREENING
CONVENTION over the ICP chemistry domain.

Do not automatically transfer a Hall completeness verdict.

Evaluate all ICP process classes over D-CHEM.

An unbounded material omission blocks chemistry admission.

OQ-NPICP-07:

Calibration / validation records must be split before measurement values are
examined.

Use planned record IDs / operating points and a frozen custody list.

Do not randomly split repeated measurements after seeing results.

No CM-CAL result becomes VALIDATED_BENCH until the held-out set passes.

OQ-NPICP-08:

APPROVED through the matched thermal-interface v2 decision above.

OQ-NPICP-09:

Report Debye-length and sheath-width ratios.

Do not create an unsourced hard threshold.

OQ-NPICP-10:

Lawful source acquisition is authorized.

No paywall bypass or fabricated transcription.

OQ-NPICP-11:

For final SIMULATION_COMPLETE, a Hall-ON neutralization coupling contract IS
required.

Preregister the v2 Hall-ON coupling now, but gate numerical execution on an
admitted Hall member.

Until a Hall member exists:

    CFG-FLIGHT-HALL-ON = NOT_EVALUATED.

Do not invent beam/plume parameters.

OQ-NPICP-12:

GEOMETRIC_TUBE is approved as a declared unvalidated modelling assumption for
the preliminary predictive model.

Label it:

    ASSUMED_GEOMETRIC_TUBE

It is not bench validation.

A registered effective volume from diagnostics supersedes it when available.

OQ-NPICP-13:

Freeze P1/P2 calibration and validation sets before the data are inspected.

Report r_u.

Do not invent an informativeness acceptance threshold yet.

OQ-NPICP-14:

For validation:
    measured p_ICP is preferred / determining.

For flight prediction:
    FLOW_BALANCE may supply neutral density only when its upstream conductance
    / feed model is admitted for that domain.

No arbitrary inflow-fraction bound.

OQ-NPICP-15:

Resolved by the matched thermal v2 decision.

==================================================
11. AIR CHEMISTRY OWNER RULINGS
==================================================

OQ-CHEM-01:
APPROVE state-resolved MATERIALITY_BOUND_REQUIRED for He and Ar.
Affected states remain INCOMPLETE_EVIDENCE until bounded.
Do not globally add them to the model merely because they exceed 1 % in a
minority of states.

OQ-CHEM-02:
Require an NO ionization/materiality bound despite the low mole fraction,
because low threshold can make a low-abundance species important.
Until bounded:
    AIR chemistry INCOMPLETE_EVIDENCE.

OQ-CHEM-03:
Keep T_e lower limit = 2 eV.
No low-energy extension without a new evidence/completeness record.

OQ-CHEM-04:
Freeze Stage-E only from registered pressure, absorbed-power and geometry
bounds.
Do not invent the grid.
Until it is registered, density-dependent chemistry admission remains
incomplete.

OQ-CHEM-05:
APPROVE:
    data/chemistry/icp/
    Rust builders in abep-chem.

OQ-CHEM-06:
APPROVE distinct labels:
    abep-icp-air-*
    abep-icp-xe-*

Never use one label for Hall and ICP chemistry definitions.

OQ-CHEM-07:
Do not owner-invent missing O/O2 state accounting.
Resolve OD-3/4/6/7 from sourced process data and conservation.
Where evidence is missing, keep the channel bounded / incomplete.
No silent extrapolation above a verified energy range.

OQ-CHEM-08:
Lawful acquisition of the listed primary sources is AUTHORIZED.

OQ-CHEM-09:
APPROVE conservative [0,1] envelopes for unsourced wall branching /
gamma / beta / quenching variables.
Do not report point values until vessel/material evidence exists.

OQ-CHEM-10:
Mixed Xe/air compositions remain OUT_OF_DOMAIN in v1.
AIR_PRIMARY and XE_CONTINGENCY are separate modes.
A mixed-chemistry v2 is required only if a future transition simulation needs
simultaneous mixed composition.

OQ-CHEM-11:
APPROVE.
EM-O2B uses the full AIR reaction set because atomic O may be generated in the
plasma even when atomic O is absent from the inlet.

OQ-CHEM-12:
APPROVE.
Ion-molecule chemistry is judged by the registered materiality screen.
If promoted, NO / NO+ enter through a versioned chemistry successor.

OQ-CHEM-13:
Prefer primary Xe measurements for the nominal admitted set.
GK2008 may be used as secondary/reference evidence, not as a substitute for an
available primary measurement.

OQ-CHEM-14:
Apply species screening PER COMPOSITION / DESIGN STATE, not globally.

OQ-CHEM-15:
UNBOUNDED_OMISSION blocks chemistry admission.
Do not accept an unevaluable process merely because it is inconvenient.

==================================================
12. NEXT EXECUTION BATCH — AUTHORIZED NOW
==================================================

START IN PARALLEL:

LANE MISSION — SC-WP-09

NP-MISSION-INTEGRATION is NEW_PHYSICS.

Preregister before implementation.

Mission must integrate:

    26,280 h mission duration;
    15,000 h firing-hours scenario independently;
    AIR_PRIMARY;
    XE_CONTINGENCY;
    mode/state schedule;
    atmosphere/design states;
    intake/feed;
    propulsion statuses;
    mass/propellant accounting;
    electrical/thermal quantities where available.

Do not turn NOT_EVALUATED subsystem physics into numeric performance.

Propagate fail-closed statuses.

No blind Xe * mission-duration calculation.

LANE DESIGN/UQ — SC-WP-10

Port active F7/F8 only.

Do NOT port uq6 / uq_modular / legacy architecture families.

Use the previously decided exact PCG64 reference stream for migration parity.

Add the B2-OF-01 numerical interpolation-sensitivity diagnostic described above.

An empty robust set is a valid output.

Do not retune inputs until a robust candidate appears.

LANE ASSESSMENT — SC-WP-11

Port assessment separately from raw physics.

Assessment consumes raw results.

It never modifies them.

Include the governed HC gates and RVM-related engineering assessment needed by
the active simulator.

Missing evidence:
    NOT_EVALUATED / INCOMPLETE_EVIDENCE.

Do not manufacture COMPLY / PASS.

HC-05 follows the validation ruling above.

LANE EVIDENCE — SC-WP-14

May begin in parallel after the public Rust API / schema of each consumed
component is frozen.

Port only builders/evidence tooling that remains active.

Historical builders are not port targets.

==================================================
13. AFTER THIS BATCH
==================================================

When WP-09 / WP-10 / WP-11 and the needed WP-14 pieces are admitted:

start:

    SC-WP-15 active hall_icp_neutralizer golden
    SC-WP-16 zero-Python CI
    SC-WP-17 clean install

Do not create the final active golden before the active end-to-end chain exists.

The final acceptance run must work with:

    no Python interpreter;
    no pip;
    no virtualenv;
    no PyO3 production dependency;
    no maturin production dependency.

HallThruster.jl remains allowed and authoritative for Hall discharge.

==================================================
14. REPORTING / STOP RULE
==================================================

Do not stop routine work merely because a physical datum is absent.

Carry the correct fail-closed status.

Stop only for:

- a true architecture decision;
- a conservation contradiction;
- a preregistration conflict that cannot be resolved conservatively;
- incompatible evidence;
- a model-domain contradiction;
- a requested change to an already scored/admitted contract.

Otherwise continue until the full selected Hall + RF/ICP simulator is running
end to end in Rust + HallThruster.jl.

==================================================
15. PRIMARY OBJECTIVE — ARCHITECTURE PROOF
==================================================

The immediate engineering objective is now:

    DETERMINE WHETHER hall_icp_neutralizer IS THE
    BEST-SUPPORTED FEASIBLE ARCHITECTURE FOR THE RFP.

Do not postpone this conclusion until every software-migration,
documentation, archival or infrastructure task is complete.

The architecture decision must be reached from the physics as soon as the
necessary end-to-end models are executable.

The conclusion must preserve all registered RFP constraints and must never be
manufactured by tuning the model to pass.

==================================================
16. DECISIVE END-TO-END PHYSICS RUN
==================================================

As soon as SC-WP-09, SC-WP-10 and SC-WP-11 are sufficiently functional,
run one controlled end-to-end architecture evaluation over the complete frozen
196-state environment.

For every state evaluate, as applicable:

    atmosphere / species
    density
    orbital velocity
    intake capture
    intake drag
    compressor / plenum / feed state
    atmospheric mass flow delivered
    Hall operating state
    Hall discharge current
    RF/ICP neutralizer electron-current capability
    total propulsion electrical load
    thrust
    spacecraft / intake drag
    T - D
    thermal quantities
    mass state
    propellant use
    mission status
    model-domain status
    uncertainty / evidence status

Do not hide unavailable quantities.

Where a determining model is not admitted:

    report the physical bound / parametric result where legitimate
    AND
    separately report the evidence-qualified status.

Never convert an assumed or parametric result into demonstrated performance.

==================================================
17. RFP CONSTRAINT MATRIX
==================================================

Produce one architecture-closure matrix against the registered RFP constraints.

At minimum include:

    altitude:
        180–230 km

    primary propellant:
        ambient atmospheric gas

    contingency capability:
        Xe

    sustained thrust basis:
        >= 12 mN

    demonstrated / capability target:
        25 mN

    bus power:
        < 1.5 kW

    complete wet mass:
        < 40 kg

    atmospheric + Xe compatibility:
        required

For every requirement give four separate fields:

    RAW PHYSICS RESULT
    UNCERTAINTY / MODEL DOMAIN
    EVIDENCE STATUS
    RFP ASSESSMENT STATUS

Do not mix these layers.

==================================================
18. ARCHITECTURE SUCCESS QUESTIONS
==================================================

The selected architecture is physically credible only if we can answer these
questions.

Q1. FLOW

Can the intake + compressor + feed chain deliver enough usable atmospheric
mass flow over the required states?

Q2. HALL

For that delivered gas state, can the Hall accelerator produce sufficient
thrust within the registered power domain?

Q3. NEUTRALIZATION

Can the downstream RF/ICP system supply the electron current required by the
Hall discharge?

Report:

    I_d
    I_e,cap
    M_n = I_e,cap / I_d - 1

as raw/model quantities where legitimately available.

Do not turn M_n into HC-05 PASS without determining validation evidence.

Q4. NET THRUST

Is:

    T_available - D_total >= 0

over the relevant state envelope?

Also separately assess the RFP thrust requirements.

Q5. POWER

Does the complete selected system remain within the spacecraft bus-power
constraint?

Include:

    Hall
    RF/ICP
    compressor
    feed / valves
    electronics
    thermal-control electrical loads
    startup / simultaneous loads

No conventional flight cathode load.

Q6. MASS

Does complete flight wet mass close below 40 kg?

Use the current governed mass model and uncertainty.

Do not select a favourable Xe load merely to force closure.

Q7. THERMAL / LIFE

Is there any known thermal, AO, erosion or lifetime result that fundamentally
invalidates the architecture?

Missing hardware evidence is not automatically an architecture failure.

Distinguish:

    architecture-infeasible
    from
    evidence-not-yet-available.

==================================================
19. BEST-ARCHITECTURE COMPARISON
==================================================

"Best" must not mean merely "the architecture we selected".

Prepare a compact controlled comparison against the credible alternatives that
have already been investigated.

Do NOT reopen a large architecture-search programme.

Compare at least, where repository evidence supports it:

    A. Hall + conventional cathode
    B. selected Hall + downstream RF/ICP
    C. RF/electrodeless-only propulsion concepts
    D. any other previously retained credible RFP architecture

Use the SAME RFP boundary and the SAME environment assumptions.

Compare only on decision-relevant criteria:

    atmospheric-gas compatibility
    AO / cathode exposure risk
    neutralization feasibility
    thrust capability
    power
    mass
    intake/feed compatibility
    thermal risk
    lifetime risk
    controllability
    development / evidence maturity

Never resurrect a historical model whose absolute result was withdrawn and use
its withdrawn number as evidence.

A historical candidate may be rejected based on a valid physical / architecture
reason preserved in the repository.

==================================================
20. REQUIRED CONCLUSION
==================================================

The end product must state exactly one of the following.

A. ARCHITECTURE PHYSICALLY CLOSES

    hall_icp_neutralizer has a feasible operating region satisfying the
    registered RFP physics constraints within the stated model domain and
    uncertainties.

B. ARCHITECTURE APPEARS FEASIBLE BUT IS NOT YET PROVEN

    physics produces a feasible region, but specific determining evidence /
    validation remains missing.

C. ARCHITECTURE DOES NOT CURRENTLY CLOSE

    identify the exact binding constraint.

D. MODEL CANNOT YET DETERMINE ARCHITECTURE FEASIBILITY

    identify the exact missing model / evidence item.

Do not use vague language.

==================================================
21. IF THE ROBUST SET IS EMPTY
==================================================

If the final 196-state robust set is empty:

DO NOT immediately reject Hall + RF/ICP.

Perform a binding-constraint decomposition.

Identify which constraint removes the last feasible states:

    intake flow
    compressor
    feed
    Hall thrust
    Hall model domain
    ICP neutralization
    bus power
    drag
    thermal
    mass
    mission / Xe
    material / life

Then classify the blocker as:

    FUNDAMENTAL_ARCHITECTURE_LIMIT

or

    DESIGN_VARIABLE_LIMIT

or

    MISSING_EVIDENCE

or

    MODEL_DOMAIN_LIMIT.

Only a FUNDAMENTAL_ARCHITECTURE_LIMIT is sufficient by itself to reject the
architecture.

Do not retune after seeing the result without registering a new design
hypothesis.

==================================================
22. PRIORITY UNTIL ARCHITECTURE CONCLUSION
==================================================

Until sections 16–21 are complete, priority is:

1. mission integration;
2. complete RF/ICP predictive physics needed for AIR_PRIMARY and Xe;
3. Hall / RF coupling;
4. end-to-end power / thermal / mass coupling;
5. F7/F8 robust evaluation;
6. assessment;
7. 196-state architecture-closure run;
8. architecture comparison;
9. final architecture conclusion.

Defer, unless directly blocking this calculation:

    final Python archival work;
    final clean-install packaging;
    cosmetic refactors;
    historical builder ports;
    documentation work;
    final active golden;
    general optimisation of simulator runtime.

After the architecture conclusion is obtained, return to those completion tasks.

==================================================
23. REPORT THE ARCHITECTURE RESULT IMMEDIATELY
==================================================

When the decisive run finishes, report immediately:

A. Does Hall + RF/ICP have a physically feasible region?

B. How many of the 196 states are physically feasible?

C. How many are robust under registered uncertainty?

D. What is the worst-case state?

E. Minimum / maximum:
       thrust
       drag
       T-D
       bus power
       atmospheric mass flow
       ICP electron-current margin
       wet mass

F. Which RFP constraints physically close?

G. Which RFP constraints remain evidence-limited?

H. What is the dominant architecture blocker, if any?

I. Comparison with the credible alternative architectures.

J. Final engineering statement:

       SELECT
       SELECT WITH EVIDENCE CONDITIONS
       DO NOT SELECT
       NOT YET DETERMINABLE

Do not wait for SC-WP-15/16/17 to report this conclusion.
````
