# ARCHITECTURE FROZEN — DESIGN CLOSURE PROGRAMME (A9.38) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-08 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_08_A9_38_architecture_frozen_design_closure_programme.json`. Immutable after commit.

---

## Message 1 — ARCHITECTURE_FROZEN_DESIGN_CLOSURE — 2026-10-08T13:54:01.208Z — text sha256 `29e3b47d663aa7f22a9b7c5c7ff95cc0ae5240a58f443bdec0edf602d335e89c`

````text
We have now made the owner-level architecture decision.
Architecture is frozen as of 08-Oct-2026. Do not reopen the propulsion architecture trade.
The selected architecture remains:
Atmospheric intake → active compressor/plenum/feed → Hall thruster → 13.56 MHz RF/ICP neutralizer → thrust
with:

* atmospheric species as the primary propellant source,
* Xe only for contingency / commissioning / emergency use,
* electromagnetic Hall magnetic-field generation,
* H1 reference geometry retained,
* 1,350 W internal design allocation and <1,500 W RFP ceiling,
* ≤34 kg nominal-dry target,
* 2 kg reference Xe load.

The purpose of the work now is rapid design closure and documentation readiness, not further architecture selection.
1. Freeze boundary
Treat DBF-1 as the controlled baseline.
Do not change any frozen architectural item merely to improve a result.
Any required physical change must:

1. identify the existing DBF-1 item,
2. state the quantitative reason it cannot remain,
3. be processed as a formal DCR,
4. preserve all immutable historical evidence,
5. preregister the evaluation method before comparing replacements.

Do not introduce alternative propulsion architectures unless evidence establishes a genuine architecture-level impossibility.
2. Items that remain open
Work immediately on the following open/unfrozen closure items.
Priority 1 — Intake/compressor redesign
This is the principal known design deficiency.
Current DBF-1 evidence shows:

* worst-condition delivered flow ≈ 1.43e-9 kg/s,
* corresponding 12 mN conservation-bound requirement ≈ 4.80e-8 kg/s,
* approximately 33.6× short in the worst covered scenario,
* current compressor model ≈10.9 kg against a 5.5 kg allocation,
* no candidate currently establishes robust closure across all admitted surface scenarios.

Open the appropriate DCR and redesign the implementation, while retaining the frozen architectural concept of an atmospheric intake + active compression/plenum/feed system.
Evaluate, at minimum:

* intake aperture/geometry,
* capture efficiency,
* pressure-recovery/compression ratio,
* compressor topology and operating point,
* compressor mass,
* plenum sizing,
* feed-controller operating region,
* dead-head margin,
* delivered mass flow,
* intake drag,
* power requirement,
* robustness across every admitted atmosphere/surface scenario.

Do not optimize only one nominal state.
The selected replacement must be evaluated against the complete governed state/scenario set.
Priority 2 — Hall RP-1 numerical convergence
Close HALL_NUMERICS_NOT_CONVERGED as quickly as possible.
Start with the frozen RP-1/H1 configuration:

* 70 mm mean diameter,
* 12 mm channel height,
* ~103.2 mm channel length,
* frozen Hall topology.

Do not alter geometry just to obtain convergence.
Establish whether the numerical issue is:

* solver/numerical,
* transport-coefficient/model-domain,
* boundary-condition,
* magnetic-field-input,
* operating-point,
* or genuine physical non-closure.

The first deliverable is a converged and reproducible RP-1 result or a rigorous failure report identifying exactly why convergence cannot be established.
Once RP-1 passes the registered convergence demonstration, immediately produce the admitted Hall envelope required by M2.
Priority 3 — H1 magnetic-field closure
Replace the current P5-shape surrogate with the best admissible H1-specific B(z) evidence.
Prefer:

1. FEMM-derived H1 B(z) using the frozen electromagnet geometry, then
2. measured B(z) when hardware becomes available.

Keep surrogate and actual-field results clearly separated.
Do not silently promote the surrogate to validated design evidence.
Priority 4 — RF/ICP neutralizer closure
Keep:

* 13.56 MHz,
* current RF/ICP architecture,
* current frozen geometry/topology unless evidence requires a DCR.

Close the missing inputs required for electron-current-capacity evaluation:

* absorbed RF power/coupling,
* RF→plasma coupling basis,
* electrode/collector potential and bias range,
* edge-factor/source,
* AIR chemistry/rate-set admission,
* Xe chemistry/rate-set admission,
* resulting electron-current capacity,
* neutralization margin relative to Hall beam current.

Finish the AIR chemistry omitted-process audit and state clearly whether any omitted process materially affects the required operating envelope.
Priority 5 — Mass closure
Rebuild the mass roll-up after the upstream redesign.
Target:

* nominal dry ≤34.0 kg,
* wet system <40 kg at the 2 kg reference Xe case,
* preserve the 10% programme margin unless an owner decision changes it.

Separate:

* measured/vendor-backed values,
* engineering estimates,
* floors,
* allocations,
* margins.

Do not claim mass closure from provisional planning numbers.
Priority 6 — Power closure
Complete the actual bus-power ledger.
Retain:

* 1,350 W internal design allocation,
* <1,500 W RFP ceiling.

Close every currently TBD power term.
Provide:

* nominal point,
* 12 mN point,
* 25 mN point,
* worst admitted atmospheric state,
* Xe contingency point where applicable,
* conversion losses,
* control/FDIR loads,
* margin.

Priority 7 — Thermal closure
Complete the frozen-topology thermal analysis.
At minimum check:

* Hall channel,
* anode,
* electromagnets,
* ICP vessel/collector,
* RF electronics,
* compressor/motor,
* PPU,
* radiator/rejection requirement,
* Earth IR/albedo where relevant,
* hot and cold orbital cases.

Do not change the thermal topology unless the present one demonstrably fails; use DCR if a physical architecture change is required.
Priority 8 — Materials closure
Retain the present primary/backup selections for the baseline:

* Inconel 600 primary,
* Inconel 601 backup,
* BN-SiO2 primary channel ceramic,
* BN backup,
* 316L excluded from the flight anode.

Complete the outstanding evidence/gates for:

* atomic oxygen,
* plasma exposure,
* sputtering/erosion,
* deposition,
* thermal cycling,
* electrical behaviour of oxide scale where relevant.

Distinguish qualification evidence from assumptions.
Priority 9 — Host-spacecraft drag interface
Do not redesign the propulsion system around the present 54.5 mN reference-drag maximum.
RC-DIAMANT remains only a reference case pending the actual host-spacecraft ICD.
Instead, derive the propulsion-compatible host constraint needed to keep T_required within the 12–25 mN propulsion envelope.
Produce the required allowable C_D·A envelope versus altitude/state for the spacecraft team.
This should become an ICD requirement/interface constraint, not an arbitrary propulsion redesign.
3. Required execution sequence
Run the work in parallel only where dependencies permit.
The critical path is:
Hall RP-1 convergence
+
intake/compressor DCR redesign
+
AIR chemistry/ICP closure
then:
updated mass + power + thermal closure
then:
M2 rerun against the revised controlled baseline
then:
M3 final architecture closure decision
Do not wait for unrelated documentation work before progressing these three critical lanes.
4. Documentation deadline mindset
We need documentation ready for submission immediately.
Therefore, for every open technical item maintain two outputs:
A. Engineering evidence
Actual calculations, simulations, registrations, test evidence, provenance, hashes and closure records.
B. Submission-safe statement
A concise statement suitable for the technical proposal that:

* satisfies the RFP,
* does not overclaim validation,
* separates design intent from demonstrated evidence,
* avoids turning internal provisional values into contractual acceptance criteria.

Do not delay proposal/document generation merely because all qualification evidence is not complete.
Where final evidence is not available, use controlled wording such as:

* design baseline,
* reference operating point,
* verification by analysis/test,
* to be finalized at PDR/CDR,
* subject to customer spacecraft ICD,
* engineering model verification,
as appropriate.

Do not use TBD/TBC unnecessarily where a defensible design choice can now be stated.
5. Definition of “closed”
An item is not closed merely because a document exists.
For each open item, report one of:

* CLOSED — design + evidence adequate
* FROZEN FOR EM — verification pending
* REFERENCE/ICD DEPENDENT
* DCR REQUIRED
* BLOCKED BY SPECIFIC MISSING EVIDENCE
* FUNDAMENTAL NON-CLOSURE

Every conclusion must identify the governing evidence and repository paths/hashes.
6. Immediate reporting
Start now.
First return a compact closure board containing:
| Item | Current state | Owner lane | Exact blocker | Action underway | Closure criterion | Documentation impact |
Then execute the work.
Prioritize actual closure over narration.
Do not create additional architecture alternatives unless the current selected architecture reaches a demonstrated fundamental impossibility.
The goal is:
one controlled architecture, minimum open technical items, and a submission-ready technical baseline as quickly as physically defensible.
````
