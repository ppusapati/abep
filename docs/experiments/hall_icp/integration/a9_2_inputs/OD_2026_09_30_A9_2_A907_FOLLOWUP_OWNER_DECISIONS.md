# A9-07 FOLLOW-UP OWNER DECISIONS (A9.2) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written). Machine-readable companion:
`OD_2026_09_30_A9_2_a907_followup_owner_decisions.json`. Immutable after commit; later amendments are new addenda.

---

A9-07 FOLLOW-UP OWNER DECISIONS

These decisions apply after verification of A9-07 and shall be incorporated by A9-10. They do not alter historical A4–A8 evidence.

1. OQ-A907-11 — RF matching architecture

Decision: move the impedance-matching function electrically close to the ICP antenna.

The configuration:

[
\text{matching network}
\rightarrow
\text{long unmatched flexible coax}
\rightarrow
\text{ICP antenna}
]

shall not remain the A9 baseline.

The A9 RF chain shall instead be arranged conceptually as:

[
\text{RF generator}
\rightarrow
\text{directional coupler}
\rightarrow
\text{50-(\Omega) transmission line}
\rightarrow
\boxed{\text{local matching network}}
\rightarrow
\text{ICP antenna}.
]

The local matching network shall be positioned on, or immediately adjacent to, the ICP module so that the long flexible coax on the thrust stand remains approximately a controlled 50-(\Omega) line rather than carrying the full antenna mismatch.

Measurement reference

Forward and reflected RF power shall be measured on the generator/50-(\Omega) side of the local matching network.

The quantities to retain are:

[
P_{\rm forward}
]

[
P_{\rm reflected}
]

[
|\Gamma|
]

[
VSWR
]

and, where possible,

[
P_{\rm delivered}

P_{\rm forward}-P_{\rm reflected}-P_{\rm line/match,loss}.
]

Do not assume:

[
P_{\rm forward}=P_{\rm plasma}.
]

500 W interpretation

The existing 0–500 W figure remains a laboratory delivered/operating investigation capability.

It is not a sufficient component rating by itself.

RF generator, coupler, coax, connectors, matching elements and feedthroughs shall be selected only after the expected mismatch envelope is characterized.

The A9-07 sensitivity result:

[
VSWR\approx5.2
]

and approximately:

[
P_{\rm forward}\approx925~W
]

for a nominal 500 W delivered case demonstrates why rating the chain merely for 500 W is unacceptable.

Protection

The RF source shall include:

* reflected-power monitoring;
* mismatch/interlock threshold;
* arc detection where feasible;
* thermal monitoring;
* automatic RF reduction/shutdown.

Exact reflected-power and VSWR trip thresholds shall be frozen after the ICP antenna/load characterization, not invented now.

⸻

2. ICP matching strategy

A9 shall investigate an adjustable local matching network for the development article.

The flight design may later become:

* a fixed network;
* switched network;
* electronically tuned network;
* another minimized flight-compatible implementation,

but only after the operating impedance envelope is measured.

Do not prematurely optimize the flight matching network before measuring:

[
Z_{\rm antenna}

R+jX
]

versus:

[
\dot m,\quad
P_{\rm RF},\quad
p,\quad
\text{gas composition},\quad
\text{Hall operating point}.
]

⸻

3. Anode material — 316L status

The present result is sufficient to make one decision:

[
\boxed{\text{316L is no longer the flight/design baseline for the H-1 anode.}}
]

316L may remain:

* an engineering/shakedown material;
* a coupon candidate;
* a low-temperature development component,

but not the design-representative score-bearing anode if the current thermal envelope applies.

A predicted anode range around:

[
1190{-}1292^\circ{\rm C}
]

with a required:

[
50~{\rm K}
]

thermal margin is incompatible with treating 316L as a credible final material.

However:

[
\boxed{\text{do not select tungsten, molybdenum, platinum, etc. yet}}
]

merely because they have higher melting points.

Oxygen compatibility, sputtering, electrical behaviour, fabrication and thermal conductivity must all be considered.

⸻

4. Anode problem shall be attacked as a thermal-design problem first

A9-10 shall mark:

ANODE_BASELINE = OPEN

and create/retain a design blocker for both:

1. anode material, and
2. anode heat-removal path.

The team shall investigate:

* stronger anode-to-backplate conduction;
* anode support/feed-tube conduction;
* geometric heat spreading;
* radiative area;
* thermal coupling to the spacecraft/stand;
* deposited discharge-power fraction;
* refractory/oxidation-resistant material candidates;
* optional active cooling only if passive closure fails.

The objective is not:

find a metal that survives 1292 °C.

The preferred objective is:

[
\boxed{\text{reduce the actual anode operating temperature substantially}}
]

and then select a material with:

[
T_{\rm operating}
\le
T_{\rm validated,continuous}

50~K.
]

No new arbitrary anode temperature limit shall be invented.

⸻

5. Coupled ICP/H-1 thermal model

The current ICP thermal result shall not be recorded as a thermal PASS.

A9-10 shall explicitly mark:

ICP_COUPLED_THERMAL = UNRESOLVED

until the thermal model includes all of:

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

and the geometric effect of the ICP assembly on H-1 radiation.

In particular, the downstream ICP can:

* obstruct H-1's radiative view;
* radiate back toward the Hall head;
* conduct heat through the carrier;
* intercept plume energy.

Therefore a thermal calculation that assumes negligible ICP coupling cannot be used to close A9.

⸻

6. Radiative-view requirement

The mechanical design of the ICP shall include a radiative-view-factor objective.

The team shall investigate geometries such as:

* open-frame ICP support;
* minimum necessary downstream obstruction;
* annular/open optical path;
* thermally isolated mounting;
* high-emittance outward-facing surfaces;
* suitable Hall-to-ICP axial spacing.

Do not optimize geometry merely for compactness.

The ICP must not solve the cathode problem by creating an unacceptable Hall-head thermal problem.

⸻

7. 13 W pole allowance finding

The reported case where one pole has only approximately:

[
13~W
]

of additional thermal allowance shall be treated as a design-driving warning.

It is not sufficient evidence by itself to reject A9.

But it means the following assumption is prohibited:

"ICP thermal interaction is small enough to ignore."

A coupled view-factor/conduction calculation is required before thermal closure.

⸻

8. Coil-mass correction

Record the correction explicitly.

Approximately:

[
0.14~{\rm kg}
]

is the copper quantity associated with the particular 60 W / fixed ampere-turn sensitivity basis.

It is not the total MC-1 coil mass.

The approximately:

[
1.58~{\rm kg}
]

figure may remain the current estimated copper mass of the complete coil geometry where that is what the H2-1 sizing calculation produces.

The two quantities shall never again be described as alternative estimates of the same physical mass.

A9-06 mass closure shall use only the clearly defined complete hardware mass.

⸻

9. A9-10 statuses

A9-10 shall carry at least these explicit statuses:

| Item | Status |
|---|---|
| Hall→ICP architecture | INVESTIGATION_HYPOTHESIS |
| ICP electron-current capacity | PENDING_ICP45 |
| ICP RF power closure | PENDING_HARDWARE |
| RF matching architecture | LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT |
| RF component ratings | TBD_AFTER_IMPEDANCE_MAP |
| 316L flight anode | REJECTED_AS_CURRENT_BASELINE |
| final anode material | OPEN |
| anode thermal closure | UNRESOLVED |
| coupled H-1/ICP thermal closure | UNRESOLVED |
| C1 conventional reference | CONTROL_FALLBACK |

Do not convert any of these open items into PASS merely to close A9-10.

⸻

10. A9-10 may continue

These findings do not require stopping A9-10.

A9-10 may complete its reconciliation work, but it shall incorporate the above statuses and blockers.

The purpose of A9-10 is to make the unresolved engineering state explicit, not to force closure.

⸻

11. Draft PR #33

Keep PR #33 DRAFT.

Do not merge to main merely because:

* CI is green;
* A9-01…09 are verified;
* A9-10 passes its reviewers.

After A9-10 merges into the execution branch:

1. run the full suite;
2. run golden checks;
3. run integrity checks;
4. verify historical immutable hashes;
5. review the complete A9 diff;
6. confirm A9-10 correctly records the unresolved RF/anode/thermal blockers.

Only then convert PR #33 from draft to ready for final merge review.

⸻

12. Immediate post-A9 technical priorities

After A9-10, the next engineering work should prioritize:

Priority 1 — ICP electron-source bench

Measure:

[
I_e(P_{\rm RF},Z,p,\dot m,\text{gas})
]

and prove ICP-45.

Priority 2 — ICP impedance map

Measure:

[
Z_{\rm antenna}

f(P_{\rm RF},\dot m,p,\text{gas},\text{plasma state})
]

to size the matching network and RF chain.

Priority 3 — coupled thermal redesign

Recalculate H-1 with actual downstream ICP geometry/view factors.

Priority 4 — anode design

Improve the conductive/radiative path and run the candidate-material trade.

These four pieces determine whether Hall→ICP progresses from:

INVESTIGATION_HYPOTHESIS

toward a genuine architecture baseline.
