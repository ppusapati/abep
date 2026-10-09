# ARCHITECTURE CLOSED — OWNER DECISIONS (A9.39) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-09 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_09_A9_39_architecture_closed_owner_decisions.json`. Immutable after commit.

---

## Message 1 — ARCHITECTURE_CLOSED — 2026-10-09T17:36:26.270Z — text sha256 `7f1e35d3b3999f955bb58ea3b73d9a6189b3b2063fe6324fc2a53de66da13459`

````text
Please record the following as the owner decisions that close the architecture.
1. DCR-DBF1-002 — APPROVED
I ratify replacement of the P5 B(z) surrogate by the H1-specific FE-derived magnetic field.
DBF-1 remains immutable historical baseline.
DBF-1.1 becomes the governing analysis baseline.
The FE result remains explicitly FE-DERIVED / NOT MEASURED. Engineering-model B(z) measurement is the verification-by-test item.
Do not retune the FE field to improve Hall performance.
2. Operating concept — APPROVED WITH CLARIFICATION
The nominal ABEP mission concept is:
ambient-air primary propulsion with atmospheric-density-aware altitude scheduling inside the RFP functional orbit range of 180–230 km.
The registered RFP states:

* functional orbit altitude: 180–230 km;
* air-intake specification shall be decided by air density based on solar activity and altitude;
* thrust requirement: 12–25 mN;
* compatibility with ambient air and Xe.

Therefore do not treat the internal 196-state Cartesian atmosphere set as meaning the spacecraft must operate at every altitude under every atmosphere extreme with one unchanged operating point.
It remains a conservative verification/design-state set.
Define an AIR operating density/free-stream-flux window and select/schedule altitude within 180–230 km according to solar activity / atmospheric density so the propulsion system remains inside that window.
Xe remains the RFP-required secondary capability for commissioning, restart, contingency, off-nominal operation and unforeseen onboard conditions.
Do not make routine Xe consumption the nominal solution for every state outside an arbitrarily fixed altitude/density combination.
3. Intake architecture — VARIABLE EFFECTIVE CAPTURE
Do not freeze a fixed 1 m² intake merely from the ideal thinnest-state bound.
The ~0.99 m² result is a physics lower bound for 12 mN at the single thinnest registered state under ideal assumptions. The same fixed area causes excessive drag at the densest states.
Therefore DCR-001 shall now evaluate a:
density-adaptive / variable-effective-capture intake + active compressor/plenum/feed architecture.
The implementation may achieve variable effective capture using the most defensible mechanism found by the trade: controlled aperture, bypass/spillage, variable throat/conductance, shutters/vanes or equivalent.
Do not introduce complexity without necessity.
DCR-001 shall determine:

* physical maximum aperture,
* effective capture-area modulation range,
* intake geometry,
* capture efficiency,
* drag,
* compressor point,
* pressure ratio,
* plenum,
* delivered flow,
* mass,
* power,
* and the corresponding admissible free-stream density/flux window.

The sizing requirement is no longer “close all ×46 atmospheric states at one fixed geometry.”
The requirement is to establish a physically defensible atmospheric operating window and altitude schedule covering the RFP 180–230 km functional range as atmosphere/solar activity changes.
4. Hall AIR efficiency — NOT AN ARCHITECTURE BLOCKER
Do not keep architecture closure open waiting for Hall AIR simulation.
Architecture closure is accepted from the conservation analysis plus the selected operating concept.
Atmospheric Hall efficiency/performance shall ultimately be verified on the Engineering Model.
Literature may support design estimates but shall never be represented as measured or demonstrated H1 performance.
However, prepare one small reproducible local-run package for me to execute on my local system.
Use DBF-1.1 with the FE B(z).
Select only the minimum decisive RP-1 atmospheric cases required to establish a preliminary operating map — approximately 6–12 cases, not another 196-state campaign.
The package shall output for every case:

* atmospheric composition,
* mass flow,
* Vd,
* Id,
* discharge power,
* magnetic-field operating point,
* thrust using true time-mean thrust,
* Isp,
* efficiency,
* oscillation statistics,
* convergence metrics,
* runtime,
* failure/collapse reason where applicable.

Include a single command/script to execute the entire package locally and generate one result file that I can return to you.
5. Final architecture status
Record the architecture as:
PHYSICS ARCHITECTURE CLOSED — DETAILED DESIGN / EM VERIFICATION OPEN
Frozen architecture:
Atmospheric variable-effective-capture intake
→ active compressor / plenum / feed
→ H1 Hall accelerator
→ 13.56 MHz RF/ICP neutralizer
→ thrust
Operating modes:

* Ambient O/N₂: primary
* Xe: required secondary / contingency capability

System requirements remain:

* functional orbit 180–230 km,
* thrust capability 12–25 mN,
* full system power <1,500 W,
* internal design target 1,350 W,
* total system mass <40 kg,
* internal nominal-dry target 34 kg.

Do not reopen the propulsion architecture unless subsequent evidence shows a fundamental physical impossibility.
6. Documentation
Update the Architecture Closure Conclusion so it does NOT state, without qualification, that “air mode cannot cover the full RFP envelope.”
Instead state:
A single fixed intake cannot span the complete conservative registered atmospheric-state set. The selected ABEP therefore uses density-aware operating-point/altitude management within the RFP 180–230 km functional-altitude range, with intake effective capture sized/modulated according to atmospheric density and solar activity, consistent with the RFP intake requirement.
Clearly separate:

* RFP requirement,
* internal conservative 196-state verification set,
* design operating window,
* EM verification items.

Now stop further architecture exploration.
Proceed only with:

1. DCR-001 intake/compressor finalization;
2. minimal local Hall AIR run package;
3. ICP bench-design closure;
4. mass/power/thermal roll-up;
5. submission documents.
````
