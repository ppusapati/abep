# P4: RF/ICP neutralizer (submission-safe statement)

**Engineering evidence:** `docs/closure/icp/icp_closure_v1.json` / `.md` (sha256 of the JSON
`3ddf55039b4f682983cfd728ded3bec6bb6e7e1cb73551ccee32521815b1016c`) and registration ICP-CLOSURE-REG-v1 (lock
`5a03e399…`).

**Internal closure state:** BLOCKED BY SPECIFIC MISSING EVIDENCE. The text below is written for the technical proposal.
It states the design baseline and the verification approach. It does not claim a demonstrated electron-current
capacity, and it sets no internal model number as an acceptance criterion.

---

## Proposal text

**Electron source and neutralizer.** The design baseline neutralizes the Hall thruster beam with a cathodeless 13.56 MHz
inductively coupled plasma (RF/ICP) electron source, mounted downstream of the Hall thruster exit. The flight
architecture has no conventional hollow cathode, so the same neutralizer serves both supply modes: atmospheric
propellant (primary) and xenon (contingency / commissioning). The topology follows a published Hall thruster
with a downstream RF/ICP electron source (Takahashi et al., J. Electr. Propuls. 3:18, 2024). That work is a topology
precedent, not a performance basis.

**Design baseline (frozen configuration DBF-1):**
- **Topology.** Open-tube coaxial, unmagnetized ICP. The 120 mm borosilicate (Pyrex-class) discharge bore is 150 mm
  long and leaves a clear passage for the Hall plume.
- **Collector.** A separately biased, metered C-type ion-collecting electrode, 100 mm long, of nickel-chromium alloy
  (Inconel 600 primary, Inconel 601 backup).
- **Isolation.** The ICP body floats on a 350 V isolation class.
- **Gas feed.** The neutralizer reuses the neutral gas leaving the Hall thruster, so it has no dedicated feed. A capped
  dedicated port is retained for the xenon variant.
- **RF chain.** An adjustable local matching network sits at the ICP module. The RF chain is rated for a forward-power
  envelope up to 500 W at the generator reference plane.
- **Power and margin.** The neutralizer loads are carried in the propulsion system's 1,350 W internal design power
  allocation, inside the < 1,500 W bus limit. Its RF power at each operating point is set within that allocation.

**Functional requirement.** At every operating point of the 12–25 mN thrust range, in both supply modes, the
neutralizer supplies an electron current at least equal to the Hall discharge current, with a verified positive margin.

**Design basis and analysis status.**
- Electron-current capacity is evaluated with a preregistered 0-D global (particle and power balance) model of the
  ICP. The model is implemented in the project's Rust simulator with conservation checks and fail-closed evidence
  rules.
- The physical inputs of the frozen design are registered:
  - geometry;
  - electrode configuration and bias range up to the 350 V class;
  - absorbed-power basis;
  - neutral-pressure range;
  - edge-loss model.
- Energy-conservation bounds show that the frozen RF envelope does not, in principle, limit the required electron
  current.
- The achievable capacity depends on the RF-to-plasma power-transfer efficiency of the antenna and plasma and on the
  discharge energy losses. Both are established by measurement, not assumed.
- Final capacity predictions for air and xenon follow the admission of the preregistered plasma-chemistry data sets
  and the bench calibration described below. They will be finalized at PDR.

**Verification approach.** Verification is by analysis and test, in this sequence:
1. **Impedance map.** An RF impedance map of the neutralizer antenna across inductive-mode operating points. It
   measures plasma and antenna resistance, which give the power-transfer efficiency.
2. **Capacity bench test.** Electron-current capacity measured on the neutralizer bench with the Hall discharge off,
   using a dedicated, isolated, instrumented electron collector over the bias range. The test gases are argon
   (engineering), nitrogen, an oxygen-bearing mixture, and xenon.
3. **Coupled test.** A coupled Hall-thruster + neutralizer test that confirms current balance and coupling voltage.
4. **Engineering model verification.** The neutralization margin is formed against the measured Hall discharge
   current with a preregistered uncertainty rule. The ICP go / no-go gate before design lock is fail-closed: it reads
   NOT EVALUATED until its evidence exists.

**Interfaces.** The RF electronics, matching network and collector-bias supply connect at the spacecraft-side DC
boundary of the propulsion power ledger. The neutralizer's thermal loads are carried in the propulsion thermal model.
The magnetic-field environment at the neutralizer, created by the Hall magnetic circuit, is taken from the Hall
thruster field analysis and confirmed by measurement.

---

## Controlled-wording notes (internal; not for the proposal)

- Do not quote an electron-current capacity, an absorbed-power value or a coupling efficiency as a design value. All
  three are NOT_EVALUATED or analog-only today.
- The internal necessary-condition numbers are lower bounds, not predictions and not acceptance criteria:
  - required current: ≥ 0.79 / 1.64 A for air and ≥ 0.39 / 0.81 A for Xe at 12 / 25 mN;
  - conservation P_abs,min: ≤ 20 W.
- The Xe published-analog estimate is a risk indicator, never a commitment: η_p of 0.18–0.73 is needed, against the
  0.1 published anchor. It is the reason the impedance map and the capacity bench come first.
- "Does not, in principle, limit" rests only on energy conservation (B3 / B4 of the closure record). It is not a
  performance claim.
- The open evidence is in `icp_closure_v1.md` sec. 5:
  - rate-set admission;
  - O⁺ / O₂⁺ edge factor;
  - delivered composition;
  - I_d,max,H1;
  - P2 / P1 bench validation;
  - GNG-ICP-01 criteria.
