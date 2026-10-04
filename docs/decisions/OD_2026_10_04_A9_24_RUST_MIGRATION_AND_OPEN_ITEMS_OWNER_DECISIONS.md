# OWNER DECISIONS — RUST MIGRATION AND REMAINING OPEN ITEMS (A9.24) — verbatim record, 2026-10-04

Recorded verbatim from the owner's message of 2026-10-04 (session chat). Companion:
`OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json`. Immutable after commit.

---

OWNER DECISIONS — RUST MIGRATION AND REMAINING OPEN ITEMS

1. RUST / PYTHON DIRECTION — REVISED OWNER DECISION

I am reversing the earlier A9.7 decision that said “Do not rewrite the simulator in Rust.”

NEW OWNER DECISION:

The target end-state is to ELIMINATE PYTHON as an active execution dependency from the ABEP simulation/toolchain.

Rust shall become the authoritative implementation for:
- physics modules, except the Hall solver noted below;
- design-space generation;
- mission propagation;
- UQ / Monte Carlo orchestration;
- architecture closure;
- assessment / compliance;
- hard gates;
- configuration loading / hash verification;
- evidence builders;
- CLI tools;
- deterministic result generation;
- validation/parity tooling currently implemented in Python.

HallThruster.jl remains the authoritative Hall-discharge solver unless separately replaced later.

Therefore the target architecture is:

```
Rust
  ├─ atmosphere / orbit
  ├─ intake / TPMC
  ├─ compressor / gaspath
  ├─ chemistry support
  ├─ mission propagation
  ├─ power / thermal / mass / life
  ├─ UQ
  ├─ design synthesis
  ├─ assessment / gates
  ├─ config / provenance
  └─ orchestration
          │
          └── HallThruster.jl
                authoritative Hall solver
```

NO Python shall remain required to run the final simulator, tests, builders, evidence generation or assessment.

However:

DO NOT delete Python immediately.

The existing Python implementation becomes the MIGRATION REFERENCE implementation until each Rust replacement has passed its preregistered parity/admission test.

Historical Python commits remain immutable Git history.

For each component:

```
PYTHON REFERENCE
       ↓
preregistered parity contract
       ↓
RUST IMPLEMENTATION
       ↓
parity PASS
       ↓
Rust becomes authoritative for that component
       ↓
Python component retired from active execution
```

Never rewrite a Python result or golden simply to make Rust pass.

Any disagreement must be investigated.

Kernel 1 TPMC intake remains admitted because its v2 parity test already passed.

The previous A9.7 prohibition on a Rust rewrite is therefore SUPERSEDED by this owner decision.

Do not interpret this as permission for an uncontrolled big-bang rewrite.

Migrate subsystem-by-subsystem with:
- exact input parity;
- exact architecture/config hashes;
- deterministic seeds where applicable;
- tolerances preregistered before comparison;
- output-schema parity;
- conservation checks;
- domain/error parity;
- performance measurement;
- provenance of the Python reference commit and Rust commit.

After a component is admitted, new production results for that component shall come from Rust.

--------------------------------------------------
2. BID VS RUST MIGRATION
--------------------------------------------------

Do NOT try to complete the entire Python-to-Rust migration before bid submission.

The bid technical baseline shall use the last completely verified pre-migration implementation.

Rust migration is a post-freeze engineering programme.

No partially migrated mixed implementation may silently become the bid source.

--------------------------------------------------
3. THRUST-FLOOR COUPLING
--------------------------------------------------

Separate the OPERATING TARGET from the COMPLIANCE CHECK.

Physics/design may use:

12 mN

as the frozen operating/sizing target where an operating target is physically required, for example Xe sizing.

That is an INPUT.

But the question:

T_available >= 12 mN ?

is ASSESSMENT ONLY.

Therefore:

```
physics:
    consumes thrust_target_mN = 12 where required for sizing/control

physics output:
    T_available

assessment:
    T_available >= thrust_sustained_min_mN
```

Do not make the raw physics solver emit a requirement PASS/FAIL.

Preserve present numerical results.

--------------------------------------------------
4. OPERATING CHOICES CURRENTLY COPIED FROM CONSTRAINTS
--------------------------------------------------

DECOUPLE THEM.

The frozen operating scenario must contain explicit frozen engineering choices.

Current values remain:

```
xe_sizing_thrust_target_mN = 12
commanded_thrust_cap_mN = 25
p_bus_throttling_cap_W = 1500
mission_hours = 26280
```

But these must NOT automatically change merely because a requirement/compliance threshold changes later.

Record provenance such as:

initial_basis = engineering constraint X

but make the operating-scenario value an independently versioned configuration value after freeze.

Required invariant:

Changing a compliance threshold alone:
    MAY change assessment result
    MUST NOT change raw physics.

Changing an operating scenario:
    MAY change raw physics
    requires a new scenario/config version.

Do not dynamically copy requirement values into physics inputs on every config regeneration.

--------------------------------------------------
5. HC-05 THROUGH HC-12
--------------------------------------------------

Disposition:

HC-05 — ICP electron-current margin
ASSESSMENT ONLY.

Criterion:
M_n,LB > 0

Physics produces currents and uncertainties.
Assessment evaluates the criterion.

HC-06 — thermal margin
ASSESSMENT / PROTECTION POLICY.

50 K remains the current registered protection/acceptance margin.

Physics produces temperatures / heat loads.
Hardware bounds contain validated temperature limits.
Assessment/protection logic applies the 50 K margin.

Do not embed the 50 K value in thermal equations.

HC-07 — firing life
ASSESSMENT ONLY.

Current threshold:
15,000 h subsystem firing-life basis.

Physics/life model produces predicted/measured life quantities.
Assessment performs the comparison.

Mission duration remains separately 26,280 h.

HC-08 — statewise thrust-minus-drag
ASSESSMENT ONLY.

Criterion:

T_available - D_spacecraft >= 0

Physics calculates T and D independently.

HC-09 — intake drag generation limit
KEEP CURRENT OPTION 1 FOR NOW.

25 mN remains a DESIGN-GENERATION FILTER for the current F1-F8 pipeline.

It comes from the frozen engineering configuration, not RFP parsing.

Also report it in assessment.

Do not move it to assessment-only until C-DRAG-RFP Option 2 is separately approved.

HC-10 — propellant capability
ASSESSMENT ONLY.

Ambient atmospheric mode + Xe contingency capability are evaluated as architecture/capability evidence.

No physics equation should contain this boolean requirement.

HC-11 — feed-state sufficiency
ASSESSMENT ONLY.

The threshold remains:

feed_available - feed_required >= 0

or the currently registered equivalent formulation.

Feed requirement must come from the measured/validated H-1 performance basis when available.

Do not reduce the requirement to match the presently achievable feed.

HC-12 — H-1 ripple
ASSESSMENT ONLY.

Threshold remains TBD until measured H-1 evidence establishes the permissible ripple basis.

No default shall be invented.

Until frozen:
HC-12 = NOT_EVALUATED

--------------------------------------------------
6. PERFORMANCE RERUN
--------------------------------------------------

APPROVED.

Run the dedicated performance baseline on the final verified PRE-RUST-MIGRATION reference commit.

Requirements:

- exact commit SHA recorded;
- new output directory;
- never overwrite the old baseline;
- same machine where practical;
- machine/environment manifest before and after;
- wall-clock and per-stage profiles;
- CPU/RAM utilisation where available;
- deterministic inputs;
- hashes of produced evidence.

This baseline becomes the profiling/reference input for Rust migration prioritisation.

After it is registered, do not require “profiling evidence before every Rust kernel” as a reason to prevent the migration programme.

Instead use the baseline to ORDER the migration.

All Python components are ultimately scheduled for retirement even if some have little speed benefit, because the new objective is removal of the Python runtime, not merely acceleration.

--------------------------------------------------
7. KERNEL MIGRATION ORDER
--------------------------------------------------

Use performance/profile evidence to prioritize, but migrate the whole active Python stack.

Initial order:

1. TPMC intake
   already ported/admitted

2. intake/design-state geometry sweep

3. compressor design search / gaspath

4. mission propagation

5. UQ / Monte Carlo driver

6. P3 ray sampling

Then continue through all remaining active Python execution paths, including:

- atmosphere/orbit wrappers
- chemistry/support calculations
- system closure
- power
- thermal
- mass
- lifetime
- architecture engine
- sweep generation
- assessment
- hard gates
- configuration loaders
- evidence builders
- CI/check utilities required for the simulator.

Do not stop after six kernels simply because those were the original performance candidates.

The target is ZERO Python execution dependency.

--------------------------------------------------
8. RUST CI
--------------------------------------------------

Update rust-parity CI from v1 to the current v2 TPMC parity record.

After that, extend Rust CI incrementally for every admitted subsystem.

CI should ultimately test:

- cargo build/test;
- deterministic output;
- Python-reference parity while Python reference remains active;
- Julia Hall bridge compatibility;
- conservation;
- config/hash validation;
- schema compatibility;
- golden/reference cases;
- no forbidden Python runtime dependency after final migration.

Do not change Kernel 1 physics while updating CI.

--------------------------------------------------
9. BID BASIS — CHOOSE B
--------------------------------------------------

Choose B.

Do not submit against bbc480c.

Create a new bid freeze at the exact latest commit that includes the approved no-numeric-change programme/config separation work and passes:

- full tests;
- Rule-9;
- golden/reference checks;
- CI integrity;
- configuration/hash checks.

This bid freeze must be BEFORE substantive Rust migration changes.

It must include the current recorded facts, including:

- AG-15 closed;
- 26,280 h mission basis;
- frozen 196-state design-state set;
- empty robust upstream set finding;
- hall_icp_neutralizer cathodeless flight architecture;
- frozen engineering-constraint/config separation.

Record the exact SHA.

Do not wait for the full Rust rewrite before freezing the bid.

--------------------------------------------------
10. RFQ DISPATCH
--------------------------------------------------

AUTHORIZED FOR QUOTATION ONLY for:

RFQ3-RF
RFQ3-GAS
RFQ3-VAC
RFQ3-HALLEL
RFQ3-MECH
RFQ3-RFMET

This permits:
- quotation;
- technical clarification;
- datasheets;
- capability information;
- mass/power information;
- lead time.

It does NOT authorize:
- purchase order;
- advance payment;
- supplier selection;
- binding commitment.

Do not dispatch:

RFQ3-THRUST
until its blocking quantity issue is resolved.

Do not dispatch:

RFQ3-H1FAB
until controlled H-1 drawings exist.

--------------------------------------------------
11. F1 36.7 MB ARCHIVE
--------------------------------------------------

AUTHORIZED TO KEEP AND UPLOAD.

Store the complete archive as a downloadable evidence artefact, preferably a GitHub Release asset or equivalent controlled evidence store.

Do NOT store the 36.7 MB generated archive as an ordinary Git blob.

Repository should contain:

- archive filename;
- SHA-256;
- byte size;
- complete file manifest;
- per-file hashes;
- generating commit;
- architecture/config hash;
- design-state-set hash;
- model-set hash;
- generation command;
- evidence classification;
- release/download reference.

Verify the uploaded/downloaded archive hash against the original before treating the upload as authoritative.

--------------------------------------------------
12. C-DRAG-RFP OPTION 2
--------------------------------------------------

NOT APPROVED NOW.

Keep Option 1 during the bid baseline.

Option 2 remains a separately governed post-bid semantic change because it changes generated populations, Pareto sets and robust counts.

--------------------------------------------------
13. IMPORTANT CATHODE CORRECTION
--------------------------------------------------

The active flight architecture is:

hall_icp_neutralizer

It is cathodeless/electrodeless.

There shall be no:
- LaB6 flight cathode;
- conventional hollow cathode;
- C1 flight fallback.

C1 is ground-reference hardware only where specifically required for laboratory H-1 characterization.

Also audit the active simulator code because any active flight physics path that still instantiates LaB6Cathode is inconsistent with the current flight architecture.

Do NOT silently fix it inside the Rust migration.

First identify every such path and classify it as:

HISTORICAL_REGRESSION
GROUND_REFERENCE
ACTIVE_FLIGHT_INCONSISTENCY

Report ACTIVE_FLIGHT_INCONSISTENCY paths to me before altering their numerical baseline.

--------------------------------------------------
14. END-STATE ACCEPTANCE
--------------------------------------------------

Python is considered eliminated only when:

- normal simulator execution requires no Python interpreter;
- production sweeps require no Python;
- config generation/loading requires no Python;
- assessment/gates require no Python;
- evidence builders require no Python;
- normal CI requires no Python for the ABEP simulator;
- every active Python implementation has an admitted Rust replacement or has been formally retired;
- HallThruster.jl integration still works;
- all required evidence provenance remains intact.

At that point, Python source may remain only as immutable historical/reference material in Git history or a clearly retired directory/tag.

Do not delete historical evidence.
