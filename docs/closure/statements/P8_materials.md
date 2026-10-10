# P8 Materials: submission-safe statement

Item P8 (A9.38 Priority 8). Closure state: **FROZEN FOR EM**. Engineering evidence:
`docs/closure/materials/materials_gates_v1.json` / `.md` (lane L-MATERIALS). Design baseline: DBF-1
(`docs/baseline/DBF-1/dbf1_v1.json`, items DBF1-MAT-01..04).

## Proposal text

**Materials design baseline.** The thruster uses one set of flight materials for both supply modes, atmospheric
(primary) and xenon (contingency):

- Hall anode and gas distributor: INCONEL alloy 600, with INCONEL alloy 601 as the backup.
- RF/ICP neutralizer ion-collecting electrode: INCONEL alloy 600, with INCONEL alloy 601 as the backup.
- Hall discharge-channel wall: boron nitride-silica composite (BN-SiO2, an established Hall-thruster wall class), with
  boron nitride as the backup.
- Austenitic stainless steel (316L) is not used for the flight anode. It is kept only for ground engineering tests.

Both alloys are non-magnetic in service, so they do not disturb the Hall magnetic circuit and add no ferromagnetic RF
loss. The primary and backup alloys form different oxide scales (chromia-rich and alumina-bearing), which reduces
common-mode risk.

**Environment basis.** The materials are assessed against the following conditions:

- the mission atomic-oxygen environment at 180-230 km;
- the internal oxygen- and nitrogen-bearing discharge plasma;
- ion sputtering at the electrode and wall sheaths;
- re-deposition of sputtered material;
- orbital and firing thermal cycling over the 26,280 h mission;
- the electrical behaviour of the electrode oxide scale over the 15,000 h firing-life basis.

Each mechanism has a verification method.

**What analysis establishes now.**

- The retained materials sit inside aft-facing openings. Direct ram atomic oxygen reaching them is negligible
  compared with the oxygen carried internally by the propellant. Their oxygen compatibility is therefore governed by
  the internal discharge environment, and it is verified there.
- The nickel-chromium alloys form non-volatile oxides, so they are not expected to recede under atomic oxygen in the
  way polymers and carbon do.
- Ion sputtering of the anode is assessed not to be a life driver, because ions reach the anode only at low energy.
  Engineering-model anode metrology will confirm it.
- The ICP collector's sputter life is set by the energy of the ions striking it. The neutralizer operating point is
  therefore to be specified to keep the collector sheath energy low. Sputter-product deposition on the neutralizer
  dielectric and on the Hall exit insulators is to be controlled by electrode geometry and will be monitored with
  witness samples.

**Verification approach.** Literature gives the material families and their mechanisms. It does not qualify these
materials in this service condition. Qualification evidence will come from a staged programme. Acceptance criteria
are pre-registered before exposure, and every stage carries full traceability.

1. **Coupon screening.** The coupons are electrically loaded:
   - anode coupons collect electrons;
   - collector coupons collect ions under negative bias, with floating controls.

   Exposure is in nitrogen, then oxygen-bearing gas, then atomic oxygen from a dedicated atomic-oxygen source with a
   fluence witness. Each coupon gets in-situ four-wire resistance, oxide metrology and species-resolved ion-beam
   sputter yields of the procured material lots.
2. **Engineering-model (EM) confirmation.** The anode and collector are replaceable, serialized and resistance-
   instrumented. The channel has replaceable exit rings. Witness coupons sit at the exit and in the neutralizer.
   Thermal cycling covers the registered mission cycle count. An EM wear segment runs on nitrogen, a nitrogen-oxygen
   mixture and xenon.
3. **Qualification life evidence.** A full-duration or justified accelerated life test is completed before any
   flight-life claim.

Material temperature limits come from the integrated EM confirmation, with the programme's 50 K thermal margin. Data
sheet ratings are used only for screening. Final material release is to be finalized at CDR, after EM verification.

## Design intent and demonstrated evidence

| aspect | design intent (baseline) | demonstrated today |
|---|---|---|
| material selections | frozen (DBF-1) | manufacturer bulk data (typical); no service-condition data |
| external atomic oxygen | not a driver for internal parts | verified by analysis, on stated attitude and layout assumptions |
| internal O / N plasma, scale conduction | conductive scale retained over the firing life | literature on other devices only; EM verification |
| sputtering / erosion | anode below threshold; collector at low sheath energy; wall life at or above the firing basis | anode by analysis; collector and wall by EM verification |
| deposition | controlled by geometry; monitored | EM witness verification |
| thermal limits / cycling | within material limits with 50 K margin | depends on the thermal closure (P7); EM cycling test |

## Wording rules for this item

- Use "design baseline", "verification by analysis/test", "engineering model verification" and "to be finalized at
  PDR/CDR".
- Do not state that a material is qualified, validated or life-demonstrated.
- Do not quote the internal screening numbers as contractual acceptance criteria. These are the collector
  ion-energy ceiling, the data-sheet temperature ceilings and the analog life indications. Acceptance values are
  frozen in the pre-registered test programme.
