# BUILD AND FREEZE DBF-1.2 (A9.42) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-10 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_10_A9_42_build_and_freeze_dbf_1_2.json`. Immutable after commit.

---

## Message 1 — BUILD_AND_FREEZE_DBF_1_2 — 2026-10-10T12:47:50.320Z — text sha256 `698c61cb2e3b1f50f4fef82bc5b9a06b3564890599ce11246bf2d8570cf46ef7`

````text
OWNER DIRECTION — BUILD AND FREEZE DBF-1.2 NOW
DCR-DBF1-001 is approved at repository checkpoint:
`6f4e3bb7025ec387143865fb737cbaaa841404fa`
Proceed to build and freeze:
DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM
This is now a baseline-construction and integrity task, not another design exercise.
Do not reopen the intake, compressor, Hall, ICP, mass architecture or operating concept unless the build exposes an actual inconsistency.
1. Governing sources
DBF-1.2 shall consume the approved state from:

* A9.40 — AIR operating concept / host-drag interpretation
* A9.41 — DCR-DBF1-001 approval and mass-risk acceptance
* `dcr001_approval_v1.json`
* `dcr_register_v5.json`
* DCR-001 v5/v6 engineering records
* DBF-1.1 for every unchanged subsystem
* current approved H1 B(z), ICP, material, thermal and power records

Preserve DBF-1 and DBF-1.1 unchanged as immutable history.
DBF-1.2 supersedes DBF-1.1 only as the active integrated preliminary-design baseline.
2. Freeze the approved upstream design exactly
Intake
Freeze:

* physical aperture: 0.70 m²
* equivalent diameter: approximately 0.94 m
* honeycomb / collimator: L/D 20
* atmospheric capture / retention architecture as approved
* delivered-flow regulation by active compressor/retention control
* density-aware altitude scheduling
* exposed frontal drag is NOT controlled by compressor speed

Do not call rotor-speed control “variable frontal area”.
AIR design point
Freeze the guaranteed proposal sizing point as:

* 12 mN AIR
* design/reference `v_eff = 26.8 km/s`
* atmospheric Hall feed ≈ 0.448 mg/s
* ICP dedicated propellant flow = 0
* AIR operation only inside the approved density/altitude window

Carry but do not freeze as guaranteed performance:

* `22 km/s` sensitivity → ≈ 0.545 mg/s
* this case requires approximately 6.1 Pa plenum setpoint
* `1.33 mg/s` AIR capability point is NOT SUPPORTED by DBF-1.2

Do not claim 25 mN atmospheric operation.
The propulsion system retains the overall 12–25 mN capability envelope, with Xe providing contingency / upper-envelope capability according to A9.40.
Compressor
Freeze the approved candidate:

* integrated contra-rotating molecular compressor
* 7 blade rows
* shared Holweck rear section
* two coaxial counter-rotating shafts
* speed approximately 8,603 rpm
* tip speed approximately 300 m/s
* full-aperture front section
* no separate finishing pump

Freeze the governing compressor mass as:
7.767 kg MEV
Freeze conservative compressor power allowance:
77 W
Keep actual component/EM mass and power verification open.
Pressure-domain classification
Preserve explicitly:

* F1–F5: within admitted free-molecular analysis domain
* F6: crosses 0.1 Pa → EM-verification risk
* B7: transitional → EM-verification risk
* Holweck: preliminary molecular-drag design within current Kn-domain criterion, coefficients requiring verification

Do NOT upgrade F6/B7 to validated or admitted.
Plenum/feed
Freeze:

* nominal plenum setpoint: 5.03 Pa
* operating/control band approximately 4.78–5.28 Pa
* volume approximately 9.3 L
* higher setpoint ≈6.1 Pa permitted for the 22 km/s sensitivity point
* high-conductance H1 distributor/manifold concept
* 186 × 3 mm preliminary distributor holes
* ±5% flow-uniformity requirement remains a preliminary H1 interface/design requirement, not demonstrated performance

3. Freeze mass exactly under A9.41
For the active DBF-1.2 proposal baseline use the approved v6 roll-up:

* non-harness: 32.773 kg
* harness: 1.725 kg
* nominal dry: 34.498 kg
* nominal dry + 10% system margin: 37.948 kg
* loaded Xe reference: 2.000 kg
* preliminary wet mass: 39.948 kg

RFP requirement:
<40 kg
The numerical difference of approximately 0.052 kg must NOT be presented as usable design margin.
Carry:
MR-DCR001-01 — OPEN MASS RISK
Approved bid-facing wording:
Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin.
PPU interpretation
For DBF-1.2:

* active AL-07 governing value: 5.460 kg MEV
* basis: approved preliminary cathodeless-H1 PPU component estimate
* status: PRELIMINARY CBE / NOT MEASURED / REQUIRES EARLY CONFIRMATION

The historical 6.0 kg planning floor remains preserved in history and must not be rewritten or deleted.
This DBF-1.2 freeze supersedes that historical planning floor for the active preliminary baseline only.
ICP mount correction
Retain the approved correction removing the duplicate ICP mount/spacer mass.
Do not count that hardware twice between AL-05 and AL-10.
4. Freeze power
Carry the current system power architecture and approved boundaries.
For AIR nominal operation:

* 12 mN AIR bus power approximately 1.16 kW
* conservative sensitivity approximately 1.21 kW
* both below RFP `<1,500 W`

For Xe 25 mN:
freeze it as a design allocation / capability requirement, not demonstrated thrust performance.
Maintain:

* RFP bus ceiling: <1,500 W
* preferred proposal design ceiling: approximately ≤1,450 W
* atmospheric compressor OFF in Xe mode
* Hall discharge allocation consistent with the current RF/ICP sensitivity budget

The existing Xe runs remain:
PARAMETRIC / NOT_VALIDATED
Do not state that 25 mN Xe has already been experimentally demonstrated.
5. Freeze operating concept
Record in DBF-1.2:
AIR mode

* primary nominal propulsion mode
* density-aware altitude scheduling within 180–230 km
* 12 mN preliminary sizing point
* operation only within the admissible AIR density/thrust/drag window

Xe mode

* required secondary capability
* contingency / off-nominal / upper-envelope operation
* used when atmospheric operation does not provide adequate thrust/drag margin

The frozen 196-state set remains a conservative verification dataset.
It is not to be deleted or weakened.
A9.40 governs the interpretation that all 196 states are not mandatory independent AIR propulsion points.
6. Host interface
Freeze:
`IR-HOST-DRAG-01`

* host spacecraft `C_D·A` supplied at PDR
* reference proposal sizing uses 0.50 m²
* actual host must remain within the propulsion drag-compensation envelope

Do not convert the 0.50 m² reference into a universal spacecraft requirement.
7. Carry controlled risks explicitly
DBF-1.2 shall contain an OPEN-RISK / VERIFICATION table including at minimum:

* `MR-DCR001-01` — mass closure / 39.948 kg roll-up
* PPU CBE confirmation
* Xe tank MEOP / burst-factor / quotation
* compressor actual mass
* compressor F6/B7 transitional performance
* Holweck coefficients
* compressor rotor growth / running-clearance verification
* H1 distributor flow uniformity
* air-Hall 26.8 km/s design-performance basis
* 22 km/s sensitivity
* Xe 25 mN power/performance verification
* routed harness mass
* AL-09 control-electronics CBE
* AL-10 structural/thermal CBE
* actual host `C_D·A`
* EM/QM AO, thermal, life and qualification tests

An open verification item does NOT make the preliminary baseline unfrozen.
It means the design is frozen for the proposal while its predicted performance is verified during the funded EM/QM programme.
8. Correct status semantics
The exact baseline status is:
DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM
Do NOT label it:

* fully RFP-qualified;
* demonstrated compliant;
* flight-qualified;
* performance validated;
* final flight design.

Architecture/design parameters are frozen at preliminary-design level.
Measured compliance remains open to EM/QM testing.
9. Baseline lock
Create a proper DBF-1.2 package containing at minimum:

* machine-readable baseline JSON
* human-readable baseline MD
* source/pin manifest
* requirement trace
* mass roll-up
* power roll-up
* AIR/Xe operating-mode definition
* intake/compressor/feed definition
* subsystem references inherited from DBF-1.1
* open-risk / verification register
* DCR provenance
* hash/lock manifest

Every inherited item shall reference its authoritative source rather than duplicating mutable values manually where possible.
Generate deterministic hashes.
Record:

* parent baseline = DBF-1.1
* change authority = approved DCR-DBF1-001
* approval = A9.41
* source checkpoint = `6f4e3bb7025ec387143865fb737cbaaa841404fa`

Once built, DBF-1.2 itself becomes immutable except through a new DCR.
10. Validation before declaring frozen
Run all relevant deterministic baseline checks:

* DBF builder `--check`
* mass arithmetic check
* power arithmetic check
* requirement/RVM trace consistency
* hash/pin integrity
* DCR-register consistency
* baseline-schema validation
* relevant unit tests
* golden/reference checks affected by DBF-1.2
* repository integrity / Rule-9 checks if applicable

Do not alter physics merely to make a check green.
If a check reveals a factual inconsistency, STOP and report it rather than silently modifying the approved design.
11. Do not update the proposal package yet
First freeze DBF-1.2 cleanly.
Do NOT regenerate the final technical annexure or bid package in this step.
After the baseline is frozen, report back:

1. exact DBF-1.2 commit SHA;
2. DBF-1.2 lock/hash;
3. files created;
4. validation/test results;
5. exact frozen architecture summary;
6. frozen mass and power summary;
7. open risks carried;
8. confirmation DBF-1 and DBF-1.1 remain unchanged;
9. confirmation no unapproved physics/design change was introduced.

If all checks pass, report exactly:
DBF-1.2 FROZEN — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM
Then STOP and wait for the next owner direction before regenerating proposal documents.
````
