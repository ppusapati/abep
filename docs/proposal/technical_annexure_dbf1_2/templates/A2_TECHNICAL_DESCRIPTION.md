# A2 - Technical description (DBF-1.2)

**Status: DRAFT_FOR_OWNER_REVIEW.** Bidder: Vyovrinda Aerospace. Tender 2026_DRDO_788433_1, RFP
DTDF/06/13516/DSP/ABEP/X/L/M/01 (Part III). Design source: DBF-1.2, freeze commit `{{SRC}}` (`{{SRC_FULL}}`), lock sha256
`{{LOCK}}`. Every path cited below is a file at that commit (`git show {{SRC}}:<path>`).

**Baseline status: {{STATUS}}.** The architecture and design parameters are frozen at preliminary-design level. Measured
compliance is verified during the funded EM / QM programme, and open verification items do not unfreeze the baseline.
This description is never to be read as fully RFP-qualified. It does not claim the design is demonstrated compliant,
flight-qualified, performance validated or a final flight design.

**Quantity labels (CLAUDE.md rule 10, `docs/EVIDENCE.md`).** Every value carries the DBF-1.2 status of its item:
- *FROZEN*: the design value.
- *FROZEN_ASSUMPTION*: the selected engineering assumption, with incomplete evidence.
- *REFERENCE_PENDING_ICD*: stands in for a customer interface.
- *INHERITED_UNCHANGED*: carried from DBF-1.1.

No Vyovrinda hardware has been built or measured. Every performance figure is a design allocation or a model value, and
is labelled as such.

## 1. Architecture

Flight architecture `hall_icp_neutralizer` (owner decisions A9.19, A9.20; physics architecture closed, conclusion v2
`docs/closure/conclusion/ARCHITECTURE_CLOSURE_CONCLUSION_v2.md`):

- **atmospheric path:** intake -> active molecular compressor -> plenum / feed -> H-1 Hall accelerator;
- **one H-1 Hall accelerator:** ionization and acceleration zones in one annular channel;
- **one downstream 13.56 MHz RF-ICP electron source / neutralizer**, cathodeless, serving both supply modes. It replaces
  the hollow cathode of a conventional Hall thruster. C1 (LaB6 hollow cathode) is ground reference only: it is never
  flight hardware, fallback, mass, power or a thermal load;
- **two supply modes:** AIR (primary nominal) and Xe (required secondary), with separate storage.

### 1.1 Mapping onto the RFP logical block diagram (RFP-P16-02)

| RFP block (Figure 1) | DBF-1.2 element | DBF-1.2 item | mass line |
|---|---|---|---|
| Intake | {{INTAKE_A}} m2 aperture intake (equivalent diameter {{INTAKE_D}} m), collimator L/D {{LD}} | DBF12-IN-01 | AL-01 |
| Filter | filter stage (inherited case F4-FIL-T0.9) | DBF1-IN-04 | AL-01 |
| Compressor | integrated contra-rotating molecular compressor (7 rows + Holweck) | DBF12-CMP-01 | AL-02 |
| Gas Chamber | plenum {{PLEN_V}} L at {{PLEN_SET}} Pa | DBF12-FEED-01 | AL-03 |
| Valve | feed control and H-1 distributor (186 x 3 mm holes, 8 inlets) | DBF12-FEED-02 | AL-03 |
| Xenon Gas -> Valve | single Xe branch, {{XE_REF}} kg reference load | DBF12-OPS-02 | AL-08 |
| Thruster (ionization + acceleration) | H-1 Hall accelerator, MC-1 electromagnet, FE-derived B(z) | DBF1-H1-01..06, DBF1-BZ-01..05 | AL-04 |
| (added, outside Figure 1) | downstream RF-ICP neutralizer + RF generator / local match | DBF1-ICP-01..07, DBF1-RF-01..04 | AL-05, AL-06 |
| Power system electronics (RFP-P18-01) | PPU, controls / FDIR / 1553B | DBF1-PWR-04 | AL-07, AL-09 |

The ICP neutralizer is an addition to the RFP diagram, which shows no electron source. No RFP requirement is changed
by it.

## 2. Operating modes (A9.40)

- **DBF12-OPS-01 AIR, primary nominal:** density-aware altitude scheduling within 180-230 km at the 12 mN sizing point,
  only inside the admissible AIR density / thrust / drag window.
- **DBF12-OPS-02 Xe, required secondary:** contingency, off-nominal and upper-envelope operation (25 mN capability) with
  the atmospheric compressor OFF. It is used when AIR does not give adequate thrust / drag margin.
- **DBF12-OPS-03:** the 196-state set is a conservative verification dataset, not 196 mandatory independent AIR
  propulsion points.

Physics basis (conclusion v2 sec. 2): a single fixed intake cannot span the complete conservative atmospheric-state set.
The intake is therefore sized from air density, solar activity and altitude, with active retention control and altitude
scheduling (RFP-P18-05).

## 3. Intake, compressor and plenum / feed (DCR-DBF1-001)

- **Intake (DBF12-IN-01, FROZEN):** aperture {{INTAKE_A}} m2, collimator L/D {{LD}}, retention design S_eff = 2 C_back
  (2/3 retention), S_eff {{SEFF}} m3/s. Delivered flow is regulated by active compressor / retention control with
  density-aware altitude scheduling (DBF12-IN-02). Exposed frontal drag is not controlled by compressor speed.
- **Compressor (DBF12-CMP-01, FROZEN_ASSUMPTION):**
  - two coaxial counter-rotating shafts, 7 blade rows and a shared Holweck rear section;
  - {{CMP_RPM}} rpm, tip speed {{CMP_TIP}} m/s, full-aperture front section, no separate finishing pump;
  - governing mass {{CMP_MEV}} kg MEV; power estimate {{CMP_P}} W, allowance {{CMP_PA}} W.
- **Plenum / feed (DBF12-FEED-01, FROZEN_ASSUMPTION):** setpoint {{PLEN_SET}} Pa (band {{PLEN_BAND}} Pa), volume
  {{PLEN_V}} L. The 22 km/s sensitivity needs {{PLEN_22}} Pa.
- **H-1 distributor (DBF12-FEED-02):** +/-5 % azimuthal flow uniformity is a preliminary interface requirement, not
  demonstrated (VR-FEED-01).

Pressure-domain classification (DBF12-CMP-02):

{{COMPRESSOR_TABLE}}

F6 crosses 0.1 Pa and B7 is transitional. Both are EM verification risks (VR-CMP-02), not admitted free-molecular
rows. The Holweck coefficients need verification (VR-CMP-03), and rotor growth against running clearance is VR-CMP-04.

## 4. Thruster: H-1 Hall accelerator

{{H1_TABLE}}

The B(z) closure state is {{BZ_STATE}}. The field is FE-derived and verified on benchmarks; it is not measured, and the
measured EM field is verified at M3.

**AIR sizing point (DBF12-AIR-01, FROZEN_ASSUMPTION):**
- 12 mN at v_eff {{AIR_VEFF}} km/s, with Hall feed {{AIR_MDOT}} mg/s;
- no dedicated ICP flow; discharge allocation P_d {{AIR_PD}} W, the lower end of DBF1-H1-06.

The {{AIR_VEFF}} km/s basis is PARAMETRIC / NOT_VALIDATED (VR-HALL-01). The 22 km/s sensitivity case needs {{AIR22_MDOT}}
mg/s (DBF12-AIR-02), and the 1.33 mg/s capability point is not supported by DBF-1.2 (DBF12-AIR-03). At 650 W the model
gives {{AIR_MODEL_T}} mN, labelled {{AIR_MODEL_LABEL}}.

Hall-transport validation (gate 3) is FAIL, and the credible transport set is empty
(`hallthruster_bridge/ensemble/transport_ensemble_v0.json` `#/members`). Every absolute result of the superseded 0-D Hall
closure stays withdrawn and is not quoted.

## 5. Electron source / neutralizer: downstream RF-ICP

{{ICP_TABLE}}

ICP closure state (`docs/closure/icp/icp_closure_v1.json` `#/closure`): **{{ICP_STATE}}**.
- Conservation in the frozen envelope: {{ICP_CONS}}.
- Electron-current capacity I_e,cap: {{ICP_IECAP}}.
- Go / no-go gate GNG-ICP-01: {{ICP_GNG}}.
- The AIR rate set (NP-ICP-CHEM-AIR) is not yet admitted; the blockers are listed in the record.

The ICP design is frozen, and its capacity is verified on the EM.

## 6. Power (< 1,500 W, RFP-P18-10; A9.43)

P_bus is all electrical power crossing the spacecraft-side DC boundary: discharge, magnets, RF generator, ICP bias,
valves, compressor, controls and thermal. It is not discharge-only power, and there are no flight cathode loads.
The basis is the P6 power ledger (`docs/closure/power/power_ledger_v1.json`) plus the DBF-1.2 compressor:
- discharge chain efficiency {{ETA}};
- Xe non-discharge load {{PXE_ND}} W;
- +100 W RF = +{{RF100}} W at the bus.

{{AIR_POWER_TABLE}}

Under the P6 conservative non-discharge corner the AIR bus is {{AIR_CORNER}} W. That is below the 1,500 W RFP limit and
above the 1,350 W internal allocation (VR-PWR-01), and it is managed by the RF / altitude schedule until the loads are
measured.

{{XE_POWER_TABLE}}

{{XE_STATEMENT}} The RP-1 Xe result near {{XE_PARAM_PD}} W discharge is {{XE_PARAM_LABEL}}.

Power and mass policy items carried from DBF-1.1:

{{PWR_ITEMS_TABLE}}

## 7. Mass (< 40 kg, RFP-P18-11; A9.41)

{{MASS_TABLE}}

**{{MASS_WORDING}}**

- PPU AL-07: {{PPU_MEV}} kg MEV (CBE {{PPU_CBE}} kg), {{PPU_STATUS}}. Reverting to the historical 6.0 kg floor gives
  about 40.57 kg wet (VR-PPU-01).
- {{COMPRESSOR_NOTE}}
- {{ICP_MOUNT}}

## 8. Thermal, materials, life

{{MAT_TH_TABLE}}

- **Thermal:** the cathodeless topology is frozen (NP-THERMAL-CATHODELESS 2.0.0), with a 50 K / x1.2 design-margin rule.
  The thermal closure state is **{{THERM_STATE}}** (`docs/closure/thermal/thermal_closure_v2.json` `#/closure`):
  - DCR nodes: {{TH_DCR_NODES}};
  - requirement nodes: {{TH_REQ_NODES}};
  - state rule: {{TH_RULE}}.

  The DCR node is the co-located RF match. **DCR-DBF1-003** ({{DCR3_STATUS}}; open, not applied to DBF-1.2): {{DCR3_REASON}}.
  Routes: {{DCR3_ROUTES}}.

  No thermal pass is claimed. The thermal design is verified at EM / QM (RVM-17).
- **Materials:** state {{MAT_STATE}}. The selections stay frozen, and no gate fails on evidence. The open gates close
  only by coupon / EM tests in the service condition (O / N plasma, atomic O, temperature).
- **Life:** the design basis is mission life >= {{LIFE_H}} h and > {{FIRING_H}} h cumulative firing. It is verified by
  wear / endurance tests, and no admissible life analysis exists.

## 9. Redundancy and electrical / data interface

- **Redundancy (RFP-P18-02 / -09):** the DBF-1.2 PPU estimate carries N+1 / redundant electronics. This is verified by
  the electronics FMEA at PDR-1. The sensor-level redundancy concept is an owner decision (OIR-TEC-02).
- **MIL-STD-1553B (RFP-P18-12):**
  - remote terminal to the onboard computer, with discrete lines for thruster operation and drivers inside the system;
  - allocated to AL-09 controls / FDIR ({{AL09}} kg owner allocation, VR-AL09-01);
  - ICD at PDR-2.

## 10. Host-spacecraft interface

IR-HOST-DRAG-01 (DBF12-HOST-01, REFERENCE_PENDING_ICD): the host C_D*A is supplied at PDR and must stay within the
propulsion drag-compensation envelope. Reference proposal sizing is C_D*A = {{CDA}} m2, for reference sizing only
(VR-HOST-01).

## 11. What this description does not claim

- No measured thrust, Isp, efficiency, power, mass or life; every such value is a design allocation, an estimate or a
  model value with its label.
- No PASS / GO for any gate. Gate 3 is FAIL, the credible Hall transport set is empty and GNG-ICP-01 is NOT_EVALUATED.
- No thermal closure ({{THERM_STATE}}; DCR-DBF1-003 open for the RF match) and no ICP capacity ({{ICP_STATE}}).
- The approximately {{HEADROOM}} kg below 40 kg is open mass risk MR-DCR001-01 and not design margin.
