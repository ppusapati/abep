# A9.3 P1/P2 OWNER DECISIONS (A9.4) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written, including the incomplete
"Define:" formula under P1Q-10). The owner titled it "A9.3 OWNER DECISIONS — P1 / P2"; it is filed as addendum A9.4 because
A9.3 is already the post-A9 tier-1 record. Machine-readable companion: `OD_2026_09_30_A9_4_p1_p2_owner_decisions.json`.
Immutable after commit; later amendments are new addenda.

---

A9.3 OWNER DECISIONS — P1 / P2
These decisions apply to the verified A9.3 work at execution-branch commit `3f857d8`.
P1Q-10 — Definition of ICP-45 electron-current capacity
Decision: YES — adopt the discharge-OFF extraction definition
ICP-45 capacity shall be measured with:

* Hall discharge supply OFF and electrically disconnected from the H-1 anode;
* ICP operating;
* electrons extracted to a dedicated, isolated, instrumented electron-collecting electrode;
* gas, magnetic field, pressure and geometry corresponding to the registered H-1 operating condition;
* matched RF-OFF measurements used to quantify facility/background electron current.

Define:
I_{e,\mathrm{collector,RFON}}
I_{e,\mathrm{collector,RFOFF}}
]
subject to current-path closure and the registered uncertainty treatment.
The qualification condition remains:
[
\boxed{
I_{e,\mathrm{cap}}
\ge
I_{d,\max,H1}
}
]
with the preregistered one-sided lower confidence bound on:
[
M_n=
\frac{I_{e,\mathrm{cap}}}
{I_{d,\max,H1}}-1
]
remaining above zero.
Why
With the Hall discharge ON:
[
I_{e,\rm ICP}\approx I_d
]
because the Hall anode itself closes the discharge circuit.
Such a measurement proves:
the ICP can supply the current demanded by that particular Hall operating point.
It does not prove:
the ICP has additional electron-current capacity available.
Therefore Hall-ON measurements shall be retained only as:
`NEUTRALIZATION_CONSISTENCY`
and never as:
`ICP45_CAPACITY`.
Hall-ON follow-up
After discharge-OFF capacity has been shown, repeat the corresponding Hall-ON point and verify:

* Hall discharge sustainment;
* current closure;
* neutralization behaviour;
* stability;
* collector/reference potentials;
* RF power.

That establishes that the separately demonstrated capacity can actually operate in the real Hall loop.
Status: `OWNER_DECIDED — CAPACITY_EXTRACTION_FORM`
P1Q-13 — H-1 electrical configuration during discharge-OFF capacity testing
Anode
Decision
The H-1 anode shall be:
[
\boxed{\text{physically disconnected from the discharge supply and left floating}}
]
during ICP-45 discharge-OFF capacity measurements.
Do not merely command the power supply to zero while leaving its output electrically attached.
Record:
[
V_{\rm anode}
]
with a high-impedance isolated measurement channel.
The anode terminal shall be classified:
`OPEN_CIRCUIT_BY_CONSTRUCTION`.
Why
A connected but OFF discharge supply can provide:

* leakage current;
* EMI/RF return paths;
* clamp paths;
* measurement-system grounds.

Any of those could create an unrecognized electron sink and corrupt (I_{e,\rm cap}).
H-1 body / magnetic circuit grounding
Decision
For the P1 bench, the H-1 body/magnetic circuit shall have one deliberate facility-ground connection only, through an instrumented/metered return.
Conceptually:
[
\text{H-1 body}
\rightarrow
\boxed{\text{ground-current monitor}}
\rightarrow
\text{facility ground}.
]
No second unintended chassis/stand/coax/shield grounding path is permitted.
Measure:
[
I_{\rm body\rightarrow ground}
]
continuously during ICP capacity measurements.
Also monitor:

* ICP body potential;
* H-1 anode potential;
* dedicated electron collector potential/current;
* chamber/facility return current where measurable.

Current-closure requirement
For each ICP-45 point, evaluate a Kirchhoff residual such as:
[
I_{\rm collector}
+
I_{\rm body}
+
I_{\rm anode}
+
I_{\rm facility}
+
I_{\rm ICP,body}
\approx 0
]
using the registered sign convention.
A large unexplained residual invalidates that capacity point.
Important distinction
The dedicated electron-collector current is the capacity measurand.
Current disappearing into:

* H-1 body;
* facility ground;
* chamber;
* floating anode;
* unintended cable shields

does not count as usable ICP electron capacity.
Diagnostic variant
A metered-return anode configuration may later be run as a separately registered diagnostic.
It shall not replace the floating-anode baseline merely because it produces a larger measured current.
Status: `OWNER_DECIDED — ANODE_FLOATING / BODY_SINGLE_POINT_METERED_GROUND`
P1Q-14 — ICP body / collector isolation class
Decision: YES
Extend the existing:
[
350~V
]
operating isolation class to the ICP body/collector circuits relative to:

* Hall anode;
* H-1 body/common;
* facility ground;
* other isolated circuits,

where those potential differences can physically occur.
This is a deliberate A9 extension of the earlier H-1 isolation requirement.
Design margin
Use:
[
V_{\rm operating,max}=350~V
]
and require at least:
[
\boxed{
V_{\rm design,withstand}\ge525~V
}
]
corresponding to a 1.5× design margin.
This is a minimum design basis, not the qualification-test voltage.
Initial bench dielectric withstand qualification
For passive insulation paths and feedthrough assemblies:
[
\boxed{
V_{\rm test}=1.05~kV~DC
}
]
for:
[
\boxed{60~s}
]
where component ratings permit.
This corresponds approximately to 3× the 350 V nominal operating class and follows the Level-2-style dielectric-withstand guidance in ECSS high-voltage engineering practice.
Perform it:

* current-limited;
* with sensitive electronics disconnected where necessary;
* with leakage recorded;
* under the relevant insulation configuration;
* before first HV/RF operation.

Also perform representative-pressure/gas testing for paths exposed to the Paschen-risk region.
Do not repeatedly hipot unnecessarily
High-voltage proof testing itself can age insulation.
Therefore the ~1.05 kV test is a qualification-style check, not something repeated before every test campaign.
Subsequent acceptance/reverification should use an appropriately lower controlled level/procedure unless a fault or hardware modification requires requalification. ECSS high-voltage guidance distinguishes roughly 3× nominal qualification-style and 2× nominal lower-level testing, and cautions against excessive repeated dielectric stressing.
Separate RF insulation
This decision does not close ICP-44.
The ICP antenna/matching network still needs separate qualification for:

* RF peak voltage;
* RF current;
* RF creepage/clearance;
* combined RF + DC stress;
* vacuum/gas breakdown.

Status: `OWNER_DECIDED — ICP_350V_CLASS / 1.05kV_INITIAL_DWV`
P2Q-05 — Optical photodiode for plasma-state verification
Decision: YES — add the photodiode
Add the optical-emission photodiode as:

1. an independent plasma ignition/unlit indicator; and
2. an E-mode/H-mode transition indicator during P2.

This is valuable because it is physically independent of the RF impedance measurement chain.
Powered-unlit record rule
A P2:
`COLD_ANTENNA_POWERED_UNLIT`
record is valid only when the optical channel demonstrates that the plasma did not ignite.
The photodiode threshold shall be established from:

* dark/background measurements;
* RF-powered known-unlit measurements;
* known-lit P1 plasma measurements.

The threshold must be frozen before the P2 map.
Do not assign an arbitrary photodiode voltage threshold now.
Photodiode should not be the only information used
For additional robustness, record simultaneously:

* photodiode intensity;
* reflected RF power;
* antenna current;
* collector/current-path response;
* pressure.

If the optical signal says UNLIT but electrical behaviour indicates an ignition/mode transition, classify the state:
`UNCERTAIN`
rather than forcing it to `UNLIT`.
Likewise, if the photodiode loses line-of-sight or saturates, the record is not automatically valid.
P2 state classification
Use:

* `UNLIT`
* `E_MODE`
* `H_MODE`
* `UNCERTAIN`

The photodiode is the required independent optical indicator, while RF/electrical signals provide corroboration.
Procurement
Add the photodiode, appropriate optical access/window, amplifier and DAQ channel to the P1_NEEDED/P2 preparation instrumentation quote.
Status: `OWNER_DECIDED — PHOTODIODE_REQUIRED`
Additional execution decisions
P1_NEEDED RFQs
Authorized
The P1-needed RFQ packages may now be sent to suppliers for quotation.
Authorization covers:

* requests for quotation;
* technical clarification;
* indicative lead time;
* commercial quotation;
* datasheets/certificates.

It does not authorize:

* purchase orders;
* advance payments;
* binding commitments.

Supplier packages may remain split by speciality as already decided.
H-1 start limits and (I_{d,\max,H1})
Do not assign (I_{d,\max,H1}) from the 8.33 A laboratory supply rating.
Retain:
[
8.33~A
]
only as the bench electrical-design ceiling.
The actual:
[
I_{d,\max,H1}
]
must be established from the registered H-1 operating envelope and measured H-1 behaviour.
Until then:
[
ICP45 = NOT_EVALUATED
]
rather than PASS or FAIL.
The P1 current-capability surface can still be generated before this number is frozen.
Merge authorization
I authorize one merge only of the A9.3 execution branch into `main`, subject to the following sequence:

1. record P1Q-10, P1Q-13, P1Q-14 and P2Q-05 in a new owner-decision addendum;
2. update the P1/P2 generated artifacts mechanically;
3. do not modify prior owner-decision files;
4. run the complete repository suite;
5. require:
   * all tests green;
   * exactly the expected skipped/xfail state;
   * golden benchmarks OK;
   * integrity 10/10;
   * protected historical artifacts unchanged;
6. review the final diff.

If those checks remain green, the A9.3 branch is approved for merge to `main`.
This approval does not extend to any later merge.
