# OWNER AUTHORIZATION — PUSH + TWO PHYSICS RULINGS (A9.30) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-05 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_05_A9_30_push_authorization_o_o2_chemistry_and_bus_boundary_rulings.json`. Immutable after commit.

---

## Message 1 — PUSH_AUTHORIZATION_O_O2_CHEMISTRY_AND_BUS_BOUNDARY — 2026-10-05T11:17:51.161Z — text sha256 `465f2d95e808f3bef5f4d2488e21112b3dca7b033c72ceb40ddc6c1eb7124618`

````text
OWNER AUTHORIZATION — PUSH + TWO PHYSICS RULINGS

I explicitly authorize pushing the current local:

    integration/simulation-complete

to:

    origin/integration/simulation-complete

subject to the safety conditions below.

==================================================
1. PUSH AUTHORIZATION
==================================================

Permission is granted for:

    git push origin \
      integration/simulation-complete:refs/heads/integration/simulation-complete

Do NOT force push.

Do NOT push main.

Do NOT modify:
    main
    claude/nifty-ramanujan-w68f9z

Do NOT rewrite history.

Before pushing:

1. fetch origin;
2. verify the current remote integration head;
3. verify the remote head is an ancestor of the local integration head.

The independently checked remote head is currently:

    e5528bdd22412014796771b615dc40f2b3bcc2ca

If the remote branch contains commits not present locally:

    STOP;
    reconcile normally;
    validate;
    then push.

Never use --force or --force-with-lease to solve divergence.

After the push:

    git ls-remote origin refs/heads/integration/simulation-complete

and report the exact resulting SHA.

==================================================
2. RUST PLAN V3.1
==================================================

The independently checked remote Rust-plan branch is:

    lane-rustplan-v2
    eb78b4ae82996dcf6c54bbca86930b6471a1a6f0

That is the plan-v3.1 line.

Ensure that exact governed plan, or its clean descendant containing only the
approved v3.1 corrections, is merged into the local integration line before the
next integration push.

Do not reopen another broad planning cycle.

==================================================
3. O / O2 CHEMISTRY — OWNER RULING
==================================================

The old sequencing restriction that deferred O/O2 chemistry must NOT prevent
completion of the selected hall_icp_neutralizer simulator.

AIR_PRIMARY at 180–230 km requires oxygen-capable RF/ICP physics.

Therefore:

    O / O2 chemistry work is AUTHORIZED now
    for the ACTIVE selected RF/ICP neutralizer model.

This authorization is architecture-specific.

It does NOT reopen:
    the old P5 Hall-transport campaign;
    historical plasma_chem.py as an active module;
    old multi-family plasma models.

Do NOT port plasma_chem.py wholesale.

Create a narrow preregistered chemistry contract for the selected RF/ICP model.

Suggested identifier:

    NP-ICP-CHEM-AIR

The minimum active species set should be justified from the registered
180–230 km atmosphere/design states and should include, where materially
present/applicable:

    O
    O2
    N2
    N
    Xe for contingency operation

Do not add species merely for completeness.

For each retained process require:

    source/provenance;
    applicable electron-energy / Te domain;
    uncertainty/evidence class;
    reaction threshold;
    conservation;
    interpolation/extrapolation rule.

Minimum processes needed for a defensible RF/ICP electron-production /
energy-loss model should be registered, including as applicable:

    electron-impact ionization;
    relevant dissociation;
    dominant excitation / inelastic energy-loss channels;
    wall/recombination treatment;
    neutral loss / residence treatment;
    Xe ionization for contingency mode.

Atomic oxygen is especially important for AIR_PRIMARY and must not be replaced
by an N2-only surrogate.

Existing repository rate data may be reused only where:

    provenance is valid;
    physical domain matches;
    the process remains applicable to the new RF/ICP model.

Do not inherit a rate merely because plasma_chem.py used it.

If the available O/O2 evidence is insufficient, the model must expose:

    INCOMPLETE_EVIDENCE

or an uncertainty envelope.

Do NOT fabricate missing coefficients.

==================================================
4. AIR_PRIMARY ADMISSION RULE
==================================================

The predictive RF/ICP model may be developed structurally in parallel, but:

    AIR_PRIMARY predictive admission

must not be claimed until NP-ICP-CHEM-AIR is committed and its required
chemistry set is admitted for the model domain.

Xe-contingency portions may proceed independently where their evidence is
sufficient.

This chemistry gate must not block unrelated lanes:

    provenance/config;
    atmosphere;
    TPMC;
    intake;
    compressor;
    feed;
    Rust infrastructure.

==================================================
5. BUS-POWER BOUNDARY — OWNER RULING
==================================================

For the ACTIVE hall_icp_neutralizer architecture, use:

    bus_power_boundary_a9_v2

as the current architecture-specific bus boundary.

The old:

    bus_power_boundary_v1

is historical / superseded for active flight closure where it carries
conventional cathode heater / keeper assumptions.

Preserve v1 as history.

Do not silently rewrite it.

The active flight bus ledger must contain only actual selected-architecture
loads, including as applicable:

    Hall discharge / anode supply;
    Hall magnet power;
    RF generator;
    matching network;
    RF/ICP neutralizer electrical demand;
    compressor / drive;
    valves / feed-control loads;
    controls / electronics / flight sensors;
    thermal-control electrical loads where applicable;
    startup / transient / concurrent-load cases.

Flight C1 cathode loads:

    NONE

C1 heater / keeper:

    GROUND_REFERENCE_ONLY

and must never enter active flight bus closure.

The 1.5 kW RFP limit remains ASSESSMENT ONLY.

Raw power physics produces the actual load ledger and bus demand.

Assessment separately checks:

    P_bus <= governed requirement

without feeding the threshold back into physics.

==================================================
6. ABEP_CORE HASH PROTECTION
==================================================

The admitted TPMC Rust source is hash-bound by its parity record.

Therefore the finding about cargo fmt is valid.

Until a deliberate new TPMC parity registration is created:

    DO NOT modify admitted abep_core source bytes.

Protect it with a source-hash CI check.

For the new workspace use formatting commands that operate only on intended
workspace members and do not mutate the admitted external/path dependency.

Do NOT run a repository-wide formatter capable of rewriting abep_core.

If abep_core must later become a normal workspace member and any source byte
changes:

    create a new preregistration;
    rerun admission/parity;
    record the new result.

Never preserve a stale admission hash across modified Rust source.

==================================================
7. LOCAL WORK SAFETY
==================================================

Because substantial work is presently local and the execution environment is
temporary:

push validated integration checkpoints frequently.

A checkpoint may be pushed when:

    its preregistration is committed where required;
    affected tests pass;
    governance checks pass;
    it does not corrupt an admitted predecessor.

Do not wait for the entire simulator before preserving days of work remotely.

This does NOT mean merge to main.

The integration branch is specifically the controlled work-in-progress line.

==================================================
8. CONTINUE EXECUTION
==================================================

Continue the parallel lanes.

Do not stop routine execution after the push.

Current priority remains:

A. Rust infrastructure / provenance;
B. frozen atmosphere + 196-state environment;
C. TPMC / intake / upstream;
D. predictive RF/ICP model;
E. cathodeless thermal model.

Then continue through:

    Hall bridge
    spacecraft T-D
    power
    mass
    materials/life
    mission
    F7/F8 + UQ
    assessment
    CLI
    active golden
    zero-Python CI.

==================================================
9. NEXT REPORT
==================================================

Report after the present execution batch with:

A. pushed integration SHA;
B. Rust workspace/crates;
C. config/provenance verifier status;
D. atmosphere/196-state status;
E. TPMC/intake/upstream status;
F. RF/ICP model status, including NP-ICP-CHEM-AIR;
G. cathodeless thermal status;
H. Hall-bridge status if started;
I. tests and CI;
J. unresolved evidence/physics blockers.

Do not stop for routine questions already governed above.
````
