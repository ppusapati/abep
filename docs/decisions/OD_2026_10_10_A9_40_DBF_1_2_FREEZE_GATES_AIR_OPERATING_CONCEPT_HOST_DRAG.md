# DBF-1.2 FREEZE GATES, AIR OPERATING CONCEPT, HOST-DRAG INTERFACE (A9.40) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-10 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_10_A9_40_dbf_1_2_freeze_gates_air_operating_concept_host_drag.json`. Immutable after commit.

---

## Message 1 — DBF_1_2_FREEZE_GATES — 2026-10-10T11:08:07.676Z — text sha256 `56585c4060018fd204232eeff32db83c43a3d1a99e00f18cc1fa2b6e0bd3380d`

````text
To freeze **DBF-1.2 as an RFP-compliant preliminary design**, we should not do more broad simulation. We need to close **four specific design gates** and then freeze the baseline.

The present DCR-001 work is not there yet. It correctly says the conservative wet mass is **45.9 kg**, while the optimistic target is **37.8 kg**; the latter depends on unproven mass reductions. Pasted markdown Also, the conservative Hall case needs about **0.80 m²**, while the proposed intake is 0.70 m². Pasted markdown

### 1. Close mass for real

This is the biggest blocker.

We need one **component-level preliminary BOM**, not just targets, for:

- intake;
- compressor + motor + bearings + housing + controller;
- plenum/feed;
- H1 Hall head/magnets;
- ICP;
- RF electronics/match;
- PPU;
- Xe tank/regulator/valves/plumbing;
- structure/thermal;
- harness;
- selected Xe load.

Then calculate:

**nominal dry + 10% margin + selected Xe load < 40 kg.**

The current “6 kg compressor”, “3.5 kg Xe hardware” and “5.3 kg PPU” cannot simply be declared true. They need either component calculations, CAD-derived preliminary masses, supplier/catalogue evidence, or reasonable analog-based engineering estimates with traceability.

My preferred goal would be approximately:

**≤33.5–34.0 kg nominal dry → ≤37.4 kg with 10% → +2 kg Xe = ≤39.4 kg wet.**

That gives some actual margin instead of sitting at 39.99 kg.

---

### 2. Close power with real margin below 1500 W

There is an important issue here: the corrected calculation currently gives **25 mN at exactly 1500 W**. Pasted markdown

The RFP says:

**<1500 W**

not ≤1500 W.

So exactly 1500 W is not a compliant design point.

We need to establish one 25 mN capability point—probably **Xe mode**, where the atmospheric compressor is switched off—at something like:

**≤1,450 W spacecraft-side bus power**

so we have approximately 50 W design margin.

For nominal 12 mN air mode, remaining around 1.15 kW is fine.

Thus we need only a small deterministic power reroll:

**AIR 12 mN**
- compressor ON;
- ICP ON;
- Hall;
- magnets;
- valves/controls.

**Xe 25 mN**
- atmospheric compressor OFF;
- Xe path ON;
- Hall;
- ICP;
- magnets;
- controls.

If Xe 25 mN closes below 1.5 kW, we don't need to force 25 mN atmospheric operation at every atmospheric state.

---

### 3. Freeze the air-operating philosophy correctly

We need one formal owner/RVM decision before DBF-1.2.

The RFP itself says the intake specification is to be determined according to **air density, solar activity and altitude**, and the operating altitude is **180–230 km**.

Our design therefore should formally say:

> **Nominal AIR operation uses density-aware altitude scheduling within 180–230 km. Xe is the required secondary/contingency mode for conditions in which atmospheric operation cannot meet the necessary thrust/drag margin.**

This matters because our internal old RVM wording is stricter—it effectively treats every one of the 196 atmosphere states as if AIR must independently satisfy the hard requirement.

We must not silently discard that rule.

Record an explicit requirement-interpretation decision saying:

- the 196 states remain a **conservative verification/design set**;
- they are not 196 mandatory independent AIR operating points;
- AIR uses an admissible density/altitude window;
- states outside that AIR window invoke the RFP-required Xe capability.

Then the short-term-high exception is not hidden or treated as a failure.

---

### 4. Freeze one host-spacecraft drag interface

Right now host drag is still an unknown ICD input.

The corrected design says the allowable host \(C_DA\) is strongly dependent on Hall performance: about **0.20 m² conservatively**, ~0.56 m² at the design case, and ~0.48 m² for the ST-high all-state point. Pasted markdown

For DBF-1.2, don't pretend we know the future DRDO spacecraft.

Freeze it as an **interface requirement**, for example:

> **IR-HOST-DRAG-01: Host-spacecraft aerodynamic \(C_DA\) shall be provided at PDR and shall remain within the propulsion-system drag-compensation envelope. Reference proposal sizing uses \(C_DA = 0.50\,m²\).**

Then show the altitude/operating schedule corresponding to that reference.

Don't make RC-DIAMANT or some literature spacecraft the actual design host.

---

## One additional technical decision: 0.70 or 0.80 m²?

I would **retain 0.70 m² for the proposal**, rather than immediately increase it to 0.80 m².

Why? The 0.80 m² requirement comes from deliberately conservative **22 km/s** assumed Hall performance. Increasing aperture also increases free-molecular drag, so simply making the intake bigger is not a free solution.

Instead freeze:

**0.70 m² physical aperture as preliminary design**, with:

- ~26.8 km/s as the design/reference air-Hall operating basis;
- 22 km/s as sensitivity/risk case;
- EM performance verification after award;
- altitude/Xe contingency when AIR thrust/drag margin is insufficient.

That is cleaner than redesigning the intake around an unverified pessimistic Hall assumption.

---

## When can we actually say DBF-1.2 is frozen?

Once these four statements are true:

| Gate | Required result |
|---|---|
| **Mass** | preliminary component roll-up **<40 kg wet**, preferably ≤39.4 kg |
| **Power** | 12 mN AIR and 25 mN capability mode **<1500 W**, with real margin |
| **Operating concept** | AIR density-window + altitude scheduling + Xe contingency formally mapped to RFP/RVM |
| **Host interface** | reference \(C_DA\) and host-drag ICD requirement frozen |

Then we can approve DCR-001 and build:

> **DBF-1.2 — RFP-COMPLIANT PRELIMINARY DESIGN BASELINE / EM VERIFICATION OPEN**

That wording is important. It means the **design complies by specification and allocation**, not that thrust, life, RF coupling, AO resistance, etc. have already been demonstrated. Those are expressly part of the EM/QM development programme.

I would **not require Hall full simulation, DSMC, compressor-map testing, ICP bench testing or AO life testing before DBF-1.2 freeze**. Those belong after award.

The immediate next job should therefore be **mass + 25 mN Xe power closure**, because those are the two numerical blockers we can actually resolve now.
````
