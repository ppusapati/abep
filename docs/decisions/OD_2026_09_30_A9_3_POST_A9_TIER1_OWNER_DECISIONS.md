# POST-A9 TIER-1 OWNER DECISIONS (A9.3) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written). Machine-readable companion:
`OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

# POST-A9 TIER-1 OWNER DECISIONS  
## Decisions Required to Launch P1 ICP Bench

**Baseline:** `main` at post-A9 checkpoint `20f14d8`  
**Primary architecture under investigation:**

\[
\boxed{
\text{Hall accelerator}
\rightarrow
\text{downstream 13.56 MHz RF/ICP electron source + neutralizer}
}
\]

**Control/fallback:** conventional external Xe-fed heated LaB₆ C1.

These decisions authorize preparation and execution of the P1 ICP bench subject to existing safety/interlock/metrology requirements.

---

## 1. OQ-VI-03 — First ICP build topology

### Decision

**YES — first P1 build shall use the open-tube coaxial downstream ICP topology only.**

Orificed RF plasma cathodes such as the Watanabe/Xu type remain:

- literature comparators;
- electron-current/gas-utilization evidence;
- possible later design branches.

They shall **not** be built as part of P1.

### Reason

P1 has one primary scientific purpose:

\[
\boxed{
\text{Can Professor Umesh/Takahashi-type downstream ICP replace C1?}
}
\]

The Takahashi architecture is fundamentally different from an orificed dedicated-feed RF cathode.

If we simultaneously change:

- downstream geometry;
- extraction geometry;
- gas-feed topology;
- cathode type;
- orifice conductance,

then a successful or failed test would no longer clearly test the architecture Professor Umesh proposed.

Therefore P1 should minimize variables.

### Important provision

Do **not** mechanically design the apparatus so that an orificed version is impossible later.

The P1 carrier/interface should remain modular enough that a future:

`ICP_ORIFICED_VARIANT`

could be installed as an A9.x follow-on without redesigning H-1.

### Status

`OWNER_DECIDED = OPEN_TUBE_COAXIAL_FIRST_BUILD`

---

# 2. OQ-VI-05 — “No Hall discharge without ICP electrons” test

### Decision

**YES — perform it, but classify it as an engineering topology-control test, not a hard architecture PASS/FAIL gate.**

Required sequence on Ar:

1. H-1 gas/magnet conditions established.
2. C1 disconnected/not supplying electrons.
3. ICP RF OFF.
4. Apply the preregistered Hall start attempt inside registered limits.
5. Record whether a sustained Hall discharge exists.
6. Turn ICP ON using the registered procedure.
7. Observe whether Hall discharge becomes sustainable.

Record:

\[
V_d(t)
\]

\[
I_d(t)
\]

\[
I_{e,\rm ICP}(t)
\]

\[
P_{\rm RF,fwd}(t)
\]

\[
P_{\rm RF,refl}(t)
\]

and collector/reference potentials.

### Important interpretation

The desired Takahashi-like observation is:

\[
\text{ICP OFF}
\Rightarrow
\text{no sustained Hall discharge}
\]

followed by:

\[
\text{ICP ON}
\Rightarrow
\text{sustained Hall discharge}.
\]

But **do not preregister “Hall must not run without ICP” as a physics requirement**.

If H-1 unexpectedly sustains some discharge from:

- facility electrons;
- secondary electron emission;
- residual plasma;
- another current path,

that is an important finding requiring current-path diagnosis.

It does not automatically invalidate the ICP architecture.

What must ultimately be demonstrated is that the ICP supplies the required electron current and neutralization function.

### Status

`REQUIRED_ENGINEERING_CONTROL_NON_SCORING`

---

# 3. OQ-A907-02 — ICP-45 maximum discharge current

### Decision

**Do not use 8.33 A as the ICP-45 architecture PASS requirement.**

This requires separating two different quantities.

## A. Bench electrical design ceiling

Register:

\[
\boxed{
I_{d,\rm stand\ ceiling}=8.33~A
}
\]

because:

\[
1500~W/180~V=8.33~A.
\]

This is the **laboratory supply/rating ceiling**.

Use it for:

- conductor sizing;
- current sensor range;
- collector circuit rating;
- feedthrough rating;
- protection;
- DAQ range;
- optional stress-test capability.

It is **not evidence that H-1 requires 8.33 A**.

## B. ICP-45 required electron-current capacity

Define:

\[
\boxed{
I_{e,\rm required}=I_{d,\max,H1}
}
\]

where \(I_{d,\max,H1}\) is the maximum H-1 discharge current within the **registered operating envelope actually relevant to the architecture**.

It must come from measured/registered H-1 operation, not simply from the maximum rating of the laboratory power supply.

ICP-45 ultimately requires:

\[
I_{e,\rm cap}
\ge
I_{d,\max,H1}
\]

with the preregistered one-sided uncertainty margin.

### Why this distinction matters

If the H-1 system requires, for example, substantially less than the supply's absolute 8.33 A capability, forcing the ICP to produce 8.33 A could falsely reject a viable architecture.

Conversely, designing sensors and wiring only around an assumed smaller current could create unsafe hardware.

Therefore:

\[
\boxed{
8.33~A=\text{bench design ceiling}
}
\]

while:

\[
\boxed{
I_{d,\max,H1}=\text{ICP-45 qualification requirement}.
}
\]

### What P1 should do before \(I_{d,\max,H1}\) is frozen

Perform an electron-current capability sweep progressively.

Do not declare PASS simply because 1 A, 2 A, etc. is reached.

Report the achievable surface:

\[
I_e
=
f(P_{\rm RF},p,\dot m,Z_{\rm ICP},V_{\rm collector})
\]

until the actual H-1 requirement is known.

### Flight supply

The present 7.5 A figure associated with:

\[
1350/180
\]

may remain a **power-envelope mathematical bound**, but is not automatically the flight discharge-current requirement either.

### Status

`8.33_A_STAND_CEILING`

and separately:

`ICP45_REQUIRED_CURRENT = H1_REGISTERED_MAX`

---

# 4. ICPQ-06 — ICP gas-line electrical isolation

### Decision

**YES.**

Any ICP gas line crossing a meaningful potential difference shall receive the same representative-pressure/gas isolation philosophy already adopted for the Hall gas isolator.

Development qualification:

\[
\boxed{\sim1~kV\ DC}
\]

at representative:

- pressure;
- gas;
- geometry;
- feedthrough/isolator condition.

Check:

- flashover;
- leakage;
- breakdown;
- surface tracking;
- repeated exposure where appropriate.

### Important qualification

Do **not** unnecessarily insert an isolator into a gas line whose two ends are intentionally maintained at essentially the same floating potential.

The requirement applies when the gas plumbing creates an electrical bridge across isolated potentials.

This distinction prevents adding:

- conductance loss;
- pressure drop;
- mass;
- contamination surfaces

where no isolation function is required.

### Status

`ACCEPT_1KV_CLASS_REPRESENTATIVE_GAS_QUALIFICATION`

---

# 5. OQ-RFQ-06 — mains-powered 13.56 MHz RF generator

### Decision

**YES — use a mains-powered laboratory 13.56 MHz generator for P1.**

Classification:

`GROUND/FACILITY_ONLY`

This is the correct choice for the first physics experiment.

We should not delay the core ICP experiment while building a flight-representative DC RF generator.

### Required measurement

Measure the laboratory source with a proper input power analyzer and record:

\[
P_{\rm mains,in}
\]

as an engineering quantity.

Also measure:

\[
P_{\rm RF,fwd}
\]

\[
P_{\rm RF,refl}
\]

and determine/cross-check delivered RF power.

### Critical boundary rule

Do **not** use:

\[
P_{\rm mains,in}
\]

as evidence that the flight propulsion system satisfies:

\[
P_{\rm bus}<1.5~kW.
\]

The mains generator contains laboratory AC/DC conversion stages that are not the flight electrical architecture.

Therefore maintain two classifications:

### P1 physics question

Can the ICP generate sufficient electrons?

Use the laboratory RF source.

### Flight/system power question

Can a flight-representative DC-input RF chain do it inside the A9 bus boundary?

Requires a later:

`FLIGHT_REPRESENTATIVE_DC_RF_SOURCE`

and measured:

\[
P_{\rm DC,in}
\rightarrow
P_{\rm RF}
\rightarrow
I_e.
\]

### Very useful P1 output

P1 should still calculate:

\[
C_e
=
\frac{P_{\rm RF,delivered}}{I_e}
\]

and preferably:

\[
C_{e,DC}
=
\frac{P_{\rm generator,input}}{I_e}
\]

with the exact boundary clearly labelled.

These will tell us what efficiency a future flight RF generator must achieve.

### Status

`YES_GROUND_ONLY`

---

# 6. OQ-RFQ-07 — who dispatches RFQs and supplier splitting

### Decision

**RFQ packages may and should be split by supplier speciality.**

The technical team/Claude prepares the packages.

**Commercial dispatch authority remains with P9E/Vyovrinda under Praveen's authorization.**

Claude/team shall **not contact suppliers automatically**.

Recommended package separation:

### RF package

- 13.56 MHz generator;
- directional coupler;
- forward/reflected sensors;
- local matching network components;
- RF coax;
- feedthroughs;
- dummy load;
- RF protection/interlocks.

### Gas/metrology package

- Ar/N₂/O₂/Xe MFCs;
- valves;
- pressure instrumentation;
- gas isolators;
- calibration.

### Vacuum/facility package

- chamber interfaces;
- pumping;
- feedthroughs;
- RGA/diagnostic interfaces.

### Hall electrical package

- discharge supply;
- magnet supply;
- isolation;
- sensing.

### Mechanical/ICP fabrication package

- dielectric tube/chamber;
- RF antenna/coil;
- collector;
- carrier;
- machined supports.

### Thrust/metrology package

- stand;
- force calibration;
- DAQ;
- traceability hardware.

### Why split

Different vendors are competent in different technologies.

Sending one enormous RFQ for the complete system would:

- reduce supplier quality;
- reduce quote comparability;
- unnecessarily expose the complete architecture;
- make substitutions harder.

A common top-level interface document should ensure the separate packages remain compatible.

### Status

`TECHNICAL_TEAM_PREPARES / OWNER_OR_PROCUREMENT_DISPATCHES`

---

# 7. OQ-RFQ-02 — four overlapping Ar MFC ranges

### Decision

**NO — do not apply the four-range rule literally to Ar.**

This is where I disagree with the current proposal.

Ar is:

\[
\boxed{\text{engineering-only topology-reproduction gas}}
\]

and does not contribute to DRDO atmospheric compliance.

The four-overlapping-range requirement was adopted because the atmospheric score-bearing flow range has very large turndown and metrology requirements.

There is little value in purchasing four precision Ar MFC ranges merely to reproduce an engineering experiment.

### P1 Ar requirement

Provide sufficient calibrated Ar flow capability to:

1. reproduce the neighborhood of the Takahashi anchor:

\[
70~sccm
\approx
2.1~mg/s
\]

for their experiment;

2. sweep sufficiently above/below that point to establish ignition/current trends;

3. maintain useful flow uncertainty in that engineering window.

### Procurement rule

Start with:

\[
\boxed{\text{one suitable Ar MFC}}
\]

if one controller covers the required P1 sweep with acceptable accuracy.

Use:

\[
\boxed{\text{two overlapping Ar ranges}}
\]

only if one unit cannot cover the engineering sweep adequately.

Do not purchase four merely because the atmospheric gas paths need four.

### Traceability

Use the rate-of-rise/transfer calibration path to verify the Ar controller.

Ar calibration quality should be sufficient for repeatability and interpretation, but Ar data remain:

`ENGINEERING_ONLY_NON_SCORING`

regardless of metrology quality.

### If Ar later becomes more important

If a later programme uses Ar for quantitative model validation rather than topology reproduction, create a new metrology requirement then.

### Status

`AR_MFC_RANGES = 1_OR_2_AS_NEEDED, NOT_4_MANDATORY`

---

# 8. OQ-RFQ-10 — optional ICP dedicated-feed controller

### Decision

**YES — include it in the RFQ as an option line.**

Do **not** buy or install it as part of the primary architecture merely because it has been quoted.

Primary P1/A9 mode remains:

\[
\boxed{G\text{-}REUSE}
\]

meaning:

\[
\text{Hall exhaust}
\rightarrow
\text{ICP}
\]

with:

\[
\dot m_{\rm ICP,dedicated}=0.
\]

However, the physical capped ICP gas port should remain.

Request optional quotations for a controller suitable for later:

- G-ATM;
- G-XE;
- diagnostic gas injection.

### Why having the option is valuable

If G-REUSE produces inadequate plasma, we need to determine whether the failure comes from:

- insufficient neutral density;
- inadequate RF coupling;
- collector/extraction physics;
- residence time;
- geometry.

A controlled small dedicated gas feed is an excellent **diagnostic variable**.

But it must not silently become the baseline solution.

If G-XE/G-ATM is activated:

\[
\dot m_{\rm ICP,dedicated}
\]

must be explicitly booked in the corresponding atmospheric/Xe ledger.

### Status

`QUOTE_OPTION_ONLY`

---

# Consolidated P1 decisions

| Question | Decision |
|---|---|
| OQ-VI-03 | **Open-tube coaxial ICP only for first build** |
| OQ-VI-05 | **Yes; required engineering control, non-gating** |
| OQ-A907-02 | **8.33 A = stand ceiling; ICP-45 requirement = measured registered H-1 maximum** |
| ICPQ-06 | **Yes, ~1 kV representative-gas isolation where potential crossing exists** |
| OQ-RFQ-06 | **Yes, mains RF source for ground P1; not flight P_bus evidence** |
| OQ-RFQ-07 | **Split RFQs; technical team prepares, owner/procurement dispatches** |
| OQ-RFQ-02 | **No mandatory four-range Ar set; 1–2 ranges based on P1 envelope** |
| OQ-RFQ-10 | **Yes as quotation option only** |

---

# Authorization after recording these decisions

After these eight decisions are recorded in a new owner-decision addendum:

## P1

\[
\boxed{\text{AUTHORIZED TO LAUNCH}}
\]

P1 should proceed with:

- open-tube coaxial 13.56 MHz ICP;
- Ar engineering reproduction;
- G-REUSE;
- electron-current extraction characterization;
- RF forward/reflected power;
- collector bias/current;
- pressure/flow;
- temperature;
- stability;
- current-path verification.

## P2

P2 impedance work should begin **in preparation immediately**, because it uses the same RF hardware.

Prepare:

- V/I sensing;
- directional-coupler chain;
- calibration;
- S-parameter/impedance measurement methodology;
- data model.

However, the actual plasma impedance map becomes meaningful only after P1 establishes a stable ICP operating region.

Therefore:

\[
\boxed{
P1\ \text{physics}
\parallel
P2\ \text{instrument preparation}
}
\]

followed by:

\[
\boxed{
P1\ \text{stable plasma}
\rightarrow
P2\ \text{plasma impedance map}.
}
\]

Do not wait for the later mass/Xe/comparison-campaign questions to start the P1 ICP physics bench.
