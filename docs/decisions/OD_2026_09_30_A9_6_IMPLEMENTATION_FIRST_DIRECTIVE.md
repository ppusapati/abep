# A9 IMPLEMENTATION-FIRST EXECUTION DIRECTIVE (A9.6) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written, including the incomplete
P1Q-16 formula block, which the owner states is definitively I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF with signed
algebraic currents). Machine-readable companion: `OD_2026_09_30_A9_6_implementation_first_directive.json`. Immutable after
commit; later amendments are new addenda.

---

A9 IMPLEMENTATION-FIRST EXECUTION DIRECTIVE
Effective immediately, change the execution strategy for the ABEP repository.
Primary objective
[
\boxed{
\text{IMPLEMENT ALL CURRENTLY AUTHORIZED WORK FIRST}
\rightarrow
\text{VERIFY THE COMPLETE INTEGRATED STATE AFTERWARD}
}
]
Do not stop after every small lane for a full three-lens verification/review cycle.
The purpose now is to complete the architecture, experiment framework, hardware definitions, ledgers, RFQs, analysis code and cross-lane integration so that verification is performed against a stable integrated system, rather than repeatedly verifying intermediate states that are immediately changed by the next lane.
1. Branch policy
Continue all work on the execution branch.
Do not merge anything further into `main` during this implementation-first phase.
Current clean baseline on `main` remains:
`eef8b85`
Treat it as the protected post-A9.4 baseline.
All new implementation remains ahead of that baseline until the consolidated verification campaign is complete.
2. A9.5
Finish the current A9.5 implementation.
Apply:
P1Q-15
Current convention:
[
\boxed{\text{conventional current into the registered network is positive}}
]
Kirchhoff residual:
[
R_I=\sum I_k
]
Combined standard uncertainty:
[
u_R=
\sqrt{\sum u^2(I_k)}
]
or the full covariance form where correlations are known.
Capacity record admission requires both:
[
|R_I|\le3u_R
]
and:
[
\frac{|R_I|}
{\max(|I_{e,\rm collector}|,I_{\rm scale,min})}
\le0.02.
]
`I_scale,min` must be registered from the instrumentation capability; no default.
If:
[
3u_R>0.02|I_{e,\rm collector}|
]
the result is:
`NOT_EVALUATED_INSTRUMENT`
rather than widening the tolerance.
P1Q-16
Confirm definitively:
I_{e,\rm collector,RFON}
I_{e,\rm collector,RFOFF}
}
]
using signed algebraic currents.
No:

* absolute values;
* zero clipping;
* replacement of a negative result;
* Hall-ON record as capacity evidence.

Hall-ON remains:
`NEUTRALIZATION_CONSISTENCY`.
Treat this directive as the definitive clarification of the formula; do not ask again because of formatting loss in an earlier message.
3. Finish the known A9.5 documentation cleanup
Resolve:

1. P1-S4 collector status;
2. A9.4 citation for the photodiode;
3. stale RFQ-v2 `PENDING` references.

These are mechanical consistency changes.
Do not launch another owner-decision cycle for them.
4. After A9.5, continue implementation instead of stopping for verification
Once A9.5 builds locally, continue directly into the remaining ready implementation work.
The team may organize this as A9.6 / A9.7 / A9.x lanes or another clear sequence, but the important rule is:
[
\boxed{\text{DO NOT STOP FOR FULL VERIFICATION AFTER EACH LANE}}
]
Full adversarial verification comes at the end.
5. Implement everything that is already decided
Any question for which an owner decision already exists shall be propagated through all affected artifacts.
This includes, but is not limited to:
Architecture
[
\text{Hall}
\rightarrow
\text{downstream 13.56 MHz ICP neutralizer}
]
with conventional C1 as control/fallback.
ICP gas
Primary:
`G-REUSE`
[
\dot m_{\rm ICP,dedicated}=0
]
Dedicated G-ATM/G-XE remains diagnostic/contingency only.
RF chain
Development architecture:
[
\text{generator}
\rightarrow
\text{50-ohm transmission}
\rightarrow
\text{local adjustable match}
\rightarrow
\text{ICP antenna}
]
Do not return to the long unmatched coax topology.
ICP-45
Capacity measured discharge-OFF.
Hall-ON is consistency evidence.
H-1 electrical state during capacity test

* anode physically disconnected;
* anode floating;
* high-impedance (V_{\rm anode}) measurement;
* H-1 body single-point metered ground;
* all intentional current paths instrumented.

Isolation
ICP body/collector:

* 350 V operating class;
* ≥525 V design-withstand basis;
* initial 1.05 kV DC / 60 s passive-insulation DWV where applicable.

Gas lines crossing isolated potentials follow the representative-gas ~1 kV qualification philosophy.
P2 optical state
Photodiode required.
States:

* `UNLIT`
* `E_MODE`
* `H_MODE`
* `UNCERTAIN`

RF source for P1
Mains-powered 13.56 MHz generator allowed as:
`GROUND/FACILITY_ONLY`.
Never use laboratory mains input as DRDO flight (P_{\rm bus}) evidence.
Ar metrology
One Ar MFC is preferred if adequate.
Two overlapping ranges only if necessary.
No mandatory four-range Ar set.
Collector/anode/thermal status
Keep explicitly:

* `316L_FLIGHT_ANODE = REJECTED_AS_CURRENT_BASELINE`
* `FINAL_ANODE_MATERIAL = OPEN`
* `ANODE_THERMAL_CLOSURE = UNRESOLVED`
* `ICP_COUPLED_THERMAL = UNRESOLVED`
* `RF_COMPONENT_RATINGS = TBD_AFTER_IMPEDANCE_MAP`

Do not manufacture a PASS merely to finish implementation.
6. Implement ready open questions that do not require owner judgment
For the remaining question register:
Automatically implement
Items that are now:

* consequences of an existing owner decision;
* mechanical cross-reference repairs;
* schema propagation;
* status propagation;
* bookkeeping;
* derived formulas;
* builder integration;
* compatibility fixes;
* RFQ line propagation;
* telemetry propagation;
* test-schema propagation.

Do not ask the owner again for these.
7. Do not invent answers to genuinely unresolved owner questions
Where an unresolved item still represents a real architecture/design choice, keep:
`TBD_OWNER`
or the existing equivalent state.
Examples include questions whose answer genuinely depends on:

* P1 measured data;
* P2 impedance measurements;
* H-1 measured discharge current;
* vendor quotations;
* selected material data;
* measured thermal coupling;
* facility capability.

Implementation should support all admissible outcomes without selecting one artificially.
8. Implement the complete P1 workflow now
Complete the repository representation for the whole P1 workflow, including:
P1-G0
Readiness and safety.
RF cold checkout
Dummy load and installed antenna.
ICP ignition
Ar, G-REUSE.
Electron-current surface
[
I_e=
f(
P_{\rm RF},
p,
\dot m,
Z_{\rm ICP},
V_{\rm collector}
)
]
ICP-45 capacity
Discharge-OFF extraction.
RF-OFF paired correction
I_{\rm ON}-I_{\rm OFF}.
]
Current closure
[
R_I=\sum I_k.
]
Stable-region determination
Required for P2 handoff.
Takahashi-like topology control
ICP OFF → attempt Hall start.
ICP ON → repeat.
Engineering-only; not an architecture gate.
Hall-ON neutralization consistency
After capacity demonstration.
Raw data schemas
Must preserve excluded records and exclusion reasons.
9. Implement the entire P2 framework now
Do not wait for real P1 data to finish the software/framework implementation.
Prepare all structures needed to later ingest measured data:

* reference planes;
* VNA calibration;
* directional-coupler measurements;
* V/I RF measurements;
* local match settings;
* S-parameter data;
* antenna impedance;
* delivered-power reconstruction;
* RF line/match loss;
* plasma-state classification;
* photodiode channel;
* E/H-mode transition detection;
* mismatch envelope;
* uncertainty propagation;
* impedance-map storage;
* rating derivation.

Unknown numeric values remain `TBD_AFTER_EVIDENCE`.
10. Implement P3/P4 framework now as well
Do not wait for P1/P2 results to build the framework.
P3 — coupled thermal
Build the data structures and calculations for:
[
Q_{\rm Hall\rightarrow ICP}
]
[
Q_{\rm collector}
]
[
Q_{\rm RF/match}
]
[
Q_{\rm plume}
]
and ICP-induced changes to H-1 radiative view factors.
Inputs that do not yet exist remain TBD.
Do not produce a thermal PASS.
P4 — anode/materials
Build the framework for comparing candidate anode/collector materials using:

* continuous-use temperature;
* oxidation;
* AO compatibility;
* sputtering;
* electrical conductivity;
* thermal conductivity;
* fabrication;
* mass;
* evidence provenance.

Do not select a final material without evidence.
11. Complete mass and power integration
Propagate the current architecture into:

* mass BOM;
* dry/wet allocations;
* RF generator;
* local matching network;
* ICP module;
* harness;
* collector/bias electronics;
* thermal hardware;
* C1 reference hardware;
* Xe hardware;
* gas path.

Keep allocation vs CBE vs measured values distinct.
No assumed allocation becomes a CBE merely because it is in the integrated BOM.
12. Complete Xe accounting
Implement all presently defined cases.
Primary Hall→ICP G-REUSE:
[
m_{\rm Xe,ICP}=0.
]
C1 reference:
book all:

* purge;
* heating/start;
* ignition;
* keeper;
* transition;
* fallback.

Any later G-XE ICP mode must be a separate explicit ledger entry.
Do not double-count residual or reserve terms.
13. Complete RFQ packages
Finish all quotation packages so they are ready to send.
Include:

* RF generator;
* directional coupler;
* power sensors;
* local matching components;
* coax/feedthroughs;
* photodiode/amplifier;
* gas MFCs;
* diagnostics;
* collector/bias supply;
* isolation hardware;
* mechanical ICP fabrication;
* dummy loads;
* calibration items.

Keep:
`P1_NEEDED`
versus:
`LATER`
classification.
Still:
[
\boxed{\text{RFQ only — no purchase order authorization}}
]
14. Complete experiment schemas and reducers
Implement all reducers so they fail closed.
Requirements include:

* missing required data → no PASS;
* mismatched sign convention → excluded;
* missing current path → excluded;
* mixed synthetic/measured evidence → refused;
* invalid RF-ON/RF-OFF pair → excluded;
* unknown (I_{d,\max,H1}) → `NOT_EVALUATED`;
* missing uncertainty → `NOT_EVALUATED`;
* unresolved plasma state → `UNCERTAIN`;
* unverified line loss → no silently reconstructed plasma power;
* OUT_OF_DOMAIN remains distinct from FAIL.

15. Implement the final requirement-verification matrix
Build one system-level table covering every top-level RFP requirement.
At minimum:

* altitude envelope;
* 12 mN minimum;
* 25 mN capability;
* <1.5 kW full bus;
* internal 1.35 kW allocation;
* <40 kg wet;
* atmospheric propellant;
* Xe capability;
* Hall preference;
* 
15,000 h provisional firing basis;
* mission-life basis;
* startup/restart;
* neutralization;
* AO/material compatibility.

Allowed states:

* `PASS`
* `FAIL`
* `NOT_EVALUATED`
* `OUT_OF_DOMAIN`
* `INCOMPLETE_EVIDENCE`
* `NUMERICAL_FAILURE`

Do not turn implementation completeness into requirement compliance.
16. Update M16 after the implementation is complete
Refresh subsystem readiness only after the implementation batch is finished.
A row becomes READY/VERIFIED only under the repository's existing evidence rules.
Do not mark the physical ICP as VERIFIED merely because its software framework is implemented.
17. Testing during implementation
Although full verification is postponed, basic engineering hygiene remains mandatory.
After each meaningful code integration:

* run the directly affected unit tests;
* run builder `--check`;
* ensure syntax/schema validity.

Do not spend time on:

* three independent adversarial reviewers;
* repeated full-repository formal verification;
* repeated checkpoint PRs;
* repeated hash-review campaigns

until the implementation batch is complete.
This avoids unnecessary churn.
18. One final consolidated verification campaign
When all currently implementable work is complete, stop development.
Then run one formal verification programme.
It shall include:
Structural review

* builders reproduce outputs;
* schemas valid;
* no stale references;
* no orphan questions;
* no circular hash mistakes;
* immutable historical artifacts unchanged.

Physics/evidence review

* no unsupported assumptions promoted;
* equations dimensionally correct;
* evidence classes correct;
* literature values not scaled beyond applicability;
* current/power/mass boundaries correct.

Electrical review

* current sign conventions;
* Kirchhoff closure;
* grounding;
* isolation;
* RF reference planes;
* matching;
* peak-voltage/current calculations.

Thermal review

* ICP obstruction;
* plume interception;
* collector heating;
* anode heating;
* radiative view;
* material limits.

Metrology review

* uncertainty propagation;
* RF power;
* current channels;
* thrust;
* gas flow;
* photodiode classification.

Software review

* adversarial tests;
* invalid-input tests;
* synthetic-data contamination tests;
* missing-data tests;
* OOD tests.

Repository-wide checks
Then run:

* complete pytest suite;
* exact expected skipped/xfail state;
* golden benchmarks;
* 10/10 integrity;
* immutable-file comparison;
* full diff review.

Only after this consolidated verification should another checkpoint PR to `main` be proposed.
19. Merge policy
No further merge to `main` is authorized by this directive.
Build everything on the execution branch first.
When implementation is complete and consolidated verification has passed, report:

1. what was implemented;
2. what remains physically unverified;
3. what questions still genuinely need owner decisions;
4. what P1 measurements are needed;
5. what P2 measurements are needed;
6. full test/integrity status;
7. proposed checkpoint PR.

Then request one new merge approval.
20. Immediate instruction
Do not stop after A9.5 asking whether to continue.
After A9.5:
[
\boxed{\text{continue automatically with every ready implementation item}}
]
until one of these occurs:

1. a genuinely new owner decision is unavoidable;
2. implementation would require inventing scientific evidence;
3. implementation would require a purchase/payment/external commitment;
4. a safety-critical ambiguity prevents even framework implementation;
5. all currently implementable work is complete.

Otherwise continue.
The objective of this phase is:
[
\boxed{
\textbf{ONE COMPLETE, INTERNALLY CONSISTENT ABEP IMPLEMENTATION}
}
]
followed by:
[
\boxed{
\textbf{ONE DEEP CONSOLIDATED VERIFICATION}
}
]
