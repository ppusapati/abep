# A2 - Technical description (DBF-1.2)

**Status: DRAFT_FOR_OWNER_REVIEW.** Bidder: Vyovrinda Aerospace. Tender 2026_DRDO_788433_1, RFP
DTDF/06/13516/DSP/ABEP/X/L/M/01 (Part III). Design source: DBF-1.2, freeze commit `45492a8` (`45492a8ef12fba13d262695bbd19f3631e80f355`), lock sha256
`103f4c9a5c0ab61d9d12e989c47e5f4fd713caa6bcbe7c45e9207e2e6ce19ee5`. Every path cited below is a file at that commit (`git show 45492a8:<path>`).

**Baseline status: DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM.** The architecture and design parameters are frozen at preliminary-design level. Measured
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
| Intake | 0.70 m2 aperture intake (equivalent diameter 0.944 m), collimator L/D 20 | DBF12-IN-01 | AL-01 |
| Filter | filter stage (inherited case F4-FIL-T0.9) | DBF1-IN-04 | AL-01 |
| Compressor | integrated contra-rotating molecular compressor (7 rows + Holweck) | DBF12-CMP-01 | AL-02 |
| Gas Chamber | plenum 9.26 L at 5.03 Pa | DBF12-FEED-01 | AL-03 |
| Valve | feed control and H-1 distributor (186 x 3 mm holes, 8 inlets) | DBF12-FEED-02 | AL-03 |
| Xenon Gas -> Valve | single Xe branch, 2.0 kg reference load | DBF12-OPS-02 | AL-08 |
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

- **Intake (DBF12-IN-01, FROZEN):** aperture 0.70 m2, collimator L/D 20, retention design S_eff = 2 C_back
  (2/3 retention), S_eff 11.25 m3/s. Delivered flow is regulated by active compressor / retention control with
  density-aware altitude scheduling (DBF12-IN-02). Exposed frontal drag is not controlled by compressor speed.
- **Compressor (DBF12-CMP-01, FROZEN_ASSUMPTION):**
  - two coaxial counter-rotating shafts, 7 blade rows and a shared Holweck rear section;
  - 8,603 rpm, tip speed 300 m/s, full-aperture front section, no separate finishing pump;
  - governing mass 7.767 kg MEV; power estimate 38.5 W, allowance 77 W.
- **Plenum / feed (DBF12-FEED-01, FROZEN_ASSUMPTION):** setpoint 5.03 Pa (band 4.78-5.28 Pa), volume
  9.26 L. The 22 km/s sensitivity needs 6.12 Pa.
- **H-1 distributor (DBF12-FEED-02):** +/-5 % azimuthal flow uniformity is a preliminary interface requirement, not
  demonstrated (VR-FEED-01).

Pressure-domain classification (DBF12-CMP-02):

| row | shaft | r_tip / r_hub (m) | blade (mm) | u_rel (m/s) | p_in -> p_out (Pa) | K | Kn out | classification |
|---|---|---|---|---|---|---|---|---|
| F1 | A | 0.333 / 0.133 | 199.8 | 210 | 0.0041 -> 0.0044 | 1.05 | 7.8 | ADMITTED_FREE_MOLECULAR |
| F2 | B | 0.333 / 0.200 | 132.7 | 450 | 0.0044 -> 0.0081 | 1.87 | 6.3 | ADMITTED_FREE_MOLECULAR |
| F3 | A | 0.333 / 0.279 | 54.0 | 516 | 0.0081 -> 0.0170 | 2.09 | 7.4 | ADMITTED_FREE_MOLECULAR |
| F4 | B | 0.333 / 0.310 | 23.5 | 565 | 0.0170 -> 0.0396 | 2.33 | 7.3 | ADMITTED_FREE_MOLECULAR |
| F5 | A | 0.333 / 0.323 | 9.6 | 585 | 0.0396 -> 0.0965 | 2.44 | 7.3 | ADMITTED_FREE_MOLECULAR |
| F6 | B | 0.333 / 0.328 | 5.0 | 593 | 0.0965 -> 0.2724 | 2.82 | 5.0 | EM_VERIFICATION_RISK_CROSSES_0.1_Pa |
| B7 | A | 0.333 / 0.328 | 5.0 | 595 | 0.2724 -> 0.7844 | 2.88 | 1.7 | EM_VERIFICATION_RISK_TRANSITIONAL |
| H (Holweck) | A (drum skin) | - | groove 2.0 | - | 0.784 -> 5.027 | - | 0.68 | PRELIMINARY_MOLECULAR_DRAG_DESIGN_WITHIN_Kn_CRITERION_COEFFICIENTS_REQUIRE_VERIFICATION |

F6 crosses 0.1 Pa and B7 is transitional. Both are EM verification risks (VR-CMP-02), not admitted free-molecular
rows. The Holweck coefficients need verification (VR-CMP-03), and rotor growth against running clearance is VR-CMP-04.

## 4. Thruster: H-1 Hall accelerator

| id | item | frozen value | freeze class | DBF-1.2 status |
|---|---|---|---|---|
| DBF1-H1-01 | channel mean diameter d_mean | 70 mm | FROZEN | INHERITED_UNCHANGED |
| DBF1-H1-02 | channel width h | 12 mm | FROZEN | INHERITED_UNCHANGED |
| DBF1-H1-03 | channel length L (HALL_INLET_Z0 to IP-EXIT) | 103.2 mm | FROZEN | INHERITED_UNCHANGED |
| DBF1-H1-04 | derived radii r_in = (d_mean - h) / 2, r_out = (d_mean + h) / 2 | r_in_mm 29; r_out_mm 41; A_channel_mm2 2638.94 [mm; mm^2] | FROZEN | INHERITED_UNCHANGED |
| DBF1-H1-05 | discharge-voltage operating band (operating variable, not a design value) | 180 - 350 V | FROZEN | INHERITED_UNCHANGED |
| DBF1-H1-06 | discharge-power band (H2-1) | 650 - 1350 W | FROZEN | INHERITED_UNCHANGED |
| DBF1-BZ-01 | B_r(z) shape target (design target) | monotonic rise toward the exit, peak at or just downstream of z = L; field near the anode as low as the circuit allows (numeric B_anode/B_peak TBD) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-BZ-02 | peak centreline B_r target band at / near IP-EXIT | 69.93 - 268.6 G | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-BZ-03 | B_peak operating levels used by the simulation | BP-LO 69.93; BP-HI 268.6 [G] | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-BZ-04 | simulation B(z) shape (H-1 FE-derived field) | BZ-H1FE-V1 | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-BZ-05 | MC-1 field capability (necessary design capability) | 403 G | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |

The B(z) closure state is FROZEN FOR EM. The field is FE-derived and verified on benchmarks; it is not measured, and the
measured EM field is verified at M3.

**AIR sizing point (DBF12-AIR-01, FROZEN_ASSUMPTION):**
- 12 mN at v_eff 26.8 km/s, with Hall feed 0.448 mg/s;
- no dedicated ICP flow; discharge allocation P_d 650 W, the lower end of DBF1-H1-06.

The 26.8 km/s basis is PARAMETRIC / NOT_VALIDATED (VR-HALL-01). The 22 km/s sensitivity case needs 0.545
mg/s (DBF12-AIR-02), and the 1.33 mg/s capability point is not supported by DBF-1.2 (DBF12-AIR-03). At 650 W the model
gives 12.54 mN, labelled MODEL-DERIVED / NOT VALIDATED (T = sqrt(2 eta m_dot P_d), eta 0.27, m_dot 0.448 mg/s); never demonstrated thrust.

Hall-transport validation (gate 3) is FAIL, and the credible transport set is empty
(`hallthruster_bridge/ensemble/transport_ensemble_v0.json` `#/members`). Every absolute result of the superseded 0-D Hall
closure stays withdrawn and is not quoted.

## 5. Electron source / neutralizer: downstream RF-ICP

| id | item | frozen value | freeze class | DBF-1.2 status |
|---|---|---|---|---|
| DBF1-RF-01 | RF frequency | 13.56 MHz | FROZEN | INHERITED_UNCHANGED |
| DBF1-RF-02 | RF forward-power operating envelope at the generator / 50-ohm reference plane | 0 - 500 W | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-RF-03 | matching architecture | adjustable local match, on / immediately adjacent to the ICP module (match_colocated = true) | FROZEN | INHERITED_UNCHANGED |
| DBF1-RF-04 | RF component ratings (generator, coupler, coax, match, feedthrough) | >= the DBF1-RF-02 envelope upper end (500 W forward) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-ICP-01 | ICP topology | open-tube coaxial downstream ICP, unmagnetized, CFG-CAP-OFF electron extraction topology per P1-IT-36 when registered | FROZEN | INHERITED_UNCHANGED |
| DBF1-ICP-02 | module geometry vector (L_standoff, r_aperture, r_module, L_module, tau_support) | L_standoff 0.05; r_aperture 0.06; r_module 0.09; L_module 0.15; tau_support 0 [m; -] | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-ICP-03 | NP-ICP v2 volume model | ASSUMED_GEOMETRIC_TUBE (V = pi R^2 L with R = r_aperture 0.06 m, L = L_module 0.15 m) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-ICP-04 | ion-collecting electrode (collector) | C-type electrode on the inner wall of the bore, 0.10 m axial length, axial slit for RF penetration; separately biased and metered, ICP body floating | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-ICP-05 | ICP neutral source / gas routing | G-REUSE (Hall exhaust -> ICP; mdot_ICP,dedicated = 0); capped dedicated port retained; declared variant G-XE | FROZEN | INHERITED_UNCHANGED |
| DBF1-ICP-06 | ICP body / collector isolation class | 350 V | FROZEN | INHERITED_UNCHANGED |
| DBF1-ICP-07 | dielectric bore (vessel) material | borosilicate glass (pyrex class) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |

ICP closure state (`docs/closure/icp/icp_closure_v1.json` `#/closure`): **BLOCKED BY SPECIFIC MISSING EVIDENCE**.
- Conservation in the frozen envelope: feasible.
- Electron-current capacity I_e,cap: INCOMPLETE_EVIDENCE in every mode (model withheld; see model_evaluation_M_A).
- Go / no-go gate GNG-ICP-01: NOT_EVALUATED (criteria PENDING_OWNER_ACCEPTANCE).
- The AIR rate set (NP-ICP-CHEM-AIR) is not yet admitted; the blockers are listed in the record.

The ICP design is frozen, and its capacity is verified on the EM.

## 6. Power (< 1,500 W, RFP-P18-10; A9.43)

P_bus is all electrical power crossing the spacecraft-side DC boundary: discharge, magnets, RF generator, ICP bias,
valves, compressor, controls and thermal. It is not discharge-only power, and there are no flight cathode loads.
The basis is the P6 power ledger (`docs/closure/power/power_ledger_v1.json`) plus the DBF-1.2 compressor:
- discharge chain efficiency 0.850725;
- Xe non-discharge load 420.2 W;
- +100 W RF = +151.1 W at the bus.

| AIR 12 mN case | P_d (W) | compressor load (W) | P_bus discharge (W) | P_bus other (W) | P_bus compressor (W) | P_bus total (W) | margin to 1,350 W | margin to 1,500 W |
|---|---|---|---|---|---|---|---|---|
| reference | 650 | 38.5 | 764.1 | 417.6 | 40.7 | 1222.3 | 127.7 | 277.7 |
| conservative | 650 | 77.0 | 764.1 | 417.6 | 81.5 | 1263.1 | 86.9 | 236.9 |

Under the P6 conservative non-discharge corner the AIR bus is 1,469.9 W. That is below the 1,500 W RFP limit and
above the 1,350 W internal allocation (VR-PWR-01), and it is managed by the RF / altitude schedule until the loads are
measured.

| Xe 25 mN Hall discharge allocation | nominal ICP (W) | +100 W RF (W) |
|---|---|---|
| <= 1,450 W design ceiling | <= 876.1 | <= 747.5 |
| < 1,500 W RFP limit | < 918.6 | < 790.1 |

Xe 25 mN is a design capability requirement. The Hall discharge-power allocation is <= 876 W at the 1,450 W design ceiling under the nominal ICP case and <= 748 W under the +100 W RF sensitivity case. Performance is to be verified on EM/QM hardware. The RP-1 Xe result near 658 W discharge is PARAMETRIC / NOT_VALIDATED (RP-1 Xe A7 runs; feasibility support only, never demonstration).

Power and mass policy items carried from DBF-1.1:

| id | item | frozen value | freeze class | DBF-1.2 status |
|---|---|---|---|---|
| DBF1-PWR-01 | design power allocation (all flight loads at the spacecraft-side DC boundary) | 1350 W | FROZEN | INHERITED_UNCHANGED |
| DBF1-PWR-02 | RFP bus-power gate (assessment only) | 1500 W | FROZEN | INHERITED_UNCHANGED |
| DBF1-PWR-03 | common-load allocation (compressor + flow control + filter/getter + thermal control + housekeeping) | 300 W | FROZEN | INHERITED_UNCHANGED |
| DBF1-PWR-04 | mapping to bus_power_boundary_a9_v2 | boundary bus_power_boundary_a9_v2 (flight configuration hall_icp_neutralizer; flight C1 loads NONE); slots_by_group hall hall_discharge, hall_magnet_inner, hall_magnet_outer, hall_magnet_trim; icp ... (full value: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items[id=DBF1-PWR-04]`) | FROZEN | INHERITED_UNCHANGED |
| DBF1-MASS-01 | system mass-margin policy | 0.1 fraction of nominal dry | FROZEN | INHERITED_UNCHANGED |
| DBF1-MASS-02 | nominal-dry mass target | 34 kg (<=) | FROZEN | INHERITED_UNCHANGED |
| DBF1-MASS-03 | reference Xe load | 2 kg | FROZEN | INHERITED_UNCHANGED |
| DBF1-MASS-04 | wet-mass target at the reference Xe load (arithmetic) | 39.4 kg | FROZEN | INHERITED_UNCHANGED |

## 7. Mass (< 40 kg, RFP-P18-11; A9.41)

| line (A9.41 approved v6 roll-up) | MEV (kg) |
|---|---|
| AL-01 intake | 4.2690 |
| AL-02 compressor | 7.8431 |
| AL-03 plenum/feed | 1.7340 |
| AL-04 Hall head + magnets | 4.2050 |
| AL-05 ICP neutralizer | 1.3430 |
| AL-06 RF generator / match | 1.5000 |
| AL-07 PPU | 5.4600 |
| AL-08 Xe hardware (single branch, 2 kg Xe) | 2.9193 |
| AL-09 controls / FDIR | 1.0000 |
| AL-10 structure / thermal | 2.5000 |
| non-harness | 32.773 |
| harness (5/95 rule) | 1.725 |
| **nominal dry** | **34.498** |
| + 10 % system margin | 37.948 |
| + Xe reference load | 2.0 |
| **preliminary wet (< 40 kg)** | **39.948** |

**Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin.**

- PPU AL-07: 5.46 kg MEV (CBE 4.55 kg), PRELIMINARY CBE / NOT MEASURED / REQUIRES EARLY CONFIRMATION. Reverting to the historical 6.0 kg floor gives
  about 40.57 kg wet (VR-PPU-01).
- 7.767 kg is the governing compressor-design mass (v5 machine). The AL-02 line of the approved v6 roll-up is 7.843 kg because the v6 intake-compressor integration books the shared joint, assembly mount feet and reinforcement in AL-02 and removes the bolted flange pair and duplicate mounts from AL-01 / AL-02 (net -0.284 kg on AL-01 + AL-02 = 12.112 kg); bookkeeping between lines, totals unchanged
- ICP open-frame support / spacer counted once (AL-10, MQ-02); duplicate removed from AL-05 (v6)

## 8. Thermal, materials, life

| id | item | frozen value | freeze class | DBF-1.2 status |
|---|---|---|---|---|
| DBF1-TH-01 | thermal network topology (NP-THERMAL-CATHODELESS 2.0.0) | solved_nodes H1_ANODE, H1_WALL_IN, H1_WALL_OUT, H1_POLE_IN, H1_POLE_OUT, H1_BACKPLATE, H1_COIL_IN, H1_COIL_OUT, H1_COIL_TRIM, N_VESSEL, N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MATCH, N_MOUNT, R_HALL; ... (full value: `docs/baseline/DBF-1.2/dbf1_2_v1.json` `#/items[id=DBF1-TH-01]`) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-TH-02 | spacecraft interface form | SCI-A conductance to a fixed spacecraft temperature at H1_BACKPLATE (isolated mount), N_MOUNT and R_HALL; values from the host thermal ICD | REFERENCE_PENDING_ICD | INHERITED_UNCHANGED |
| DBF1-TH-03 | thermal design margin rule | margin_K 50; heat_load_factor 1.2 [K; -] | FROZEN | INHERITED_UNCHANGED |
| DBF1-MAT-01 | H-1 anode / gas distributor material (primary) | INCONEL alloy 600 (chromia-forming Ni alloy) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-MAT-02 | H-1 anode / gas distributor material (backup) | INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-MAT-03 | ICP ion-collecting electrode material (primary / backup) | primary INCONEL alloy 600 (chromia-forming Ni alloy); backup INCONEL alloy 601 (alumina-forming Ni-Cr-Al alloy) | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |
| DBF1-MAT-04 | H-1 channel wall ceramic (primary / backup) | primary BN-SiO2 (borosil class); backup BN | FROZEN_ASSUMPTION | INHERITED_UNCHANGED |

- **Thermal:** the cathodeless topology is frozen (NP-THERMAL-CATHODELESS 2.0.0), with a 50 K / x1.2 design-margin rule.
  The thermal closure state is **DCR REQUIRED** (`docs/closure/thermal/thermal_closure_v2.json` `#/closure`):
  - DCR nodes: N_MATCH;
  - requirement nodes: H1_ANODE, N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MOUNT, R_HALL;
  - state rule: DCR REQUIRED > FUNDAMENTAL NON-CLOSURE > BLOCKED BY SPECIFIC MISSING EVIDENCE > REFERENCE/ICD DEPENDENT > FROZEN FOR EM > CLOSED.

  The DCR node is the co-located RF match. **DCR-DBF1-003** (REQUESTED_EVALUATION_TO_BE_PREREGISTERED; open, not applied to DBF-1.2): co-located match N_MATCH 147-184 degC in every preregistered hot case vs 60 degC ceiling (margin -124 K), fails at P_fwd = 0 W and at every radiator grid point: conduction from the ICP bracket (docs/closure/thermal/thermal_closure_v2.json sha 06b26333...).
  Routes: R-1 no-DCR: thermal isolation + dedicated radiator for the match (if it closes, DCR-DBF1-003 is withdrawn); R-2 DCR: relocate the match to the generator side.

  No thermal pass is claimed. The thermal design is verified at EM / QM (RVM-17).
- **Materials:** state FROZEN FOR EM. The selections stay frozen, and no gate fails on evidence. The open gates close
  only by coupon / EM tests in the service condition (O / N plasma, atomic O, temperature).
- **Life:** the design basis is mission life >= 26,280 h and > 15,000 h cumulative firing. It is verified by
  wear / endurance tests, and no admissible life analysis exists.

## 9. Redundancy and electrical / data interface

- **Redundancy (RFP-P18-02 / -09):** the DBF-1.2 PPU estimate carries N+1 / redundant electronics. This is verified by
  the electronics FMEA at PDR-1. The sensor-level redundancy concept is an owner decision (OIR-TEC-02).
- **MIL-STD-1553B (RFP-P18-12):**
  - remote terminal to the onboard computer, with discrete lines for thruster operation and drivers inside the system;
  - allocated to AL-09 controls / FDIR (1.0 kg owner allocation, VR-AL09-01);
  - ICD at PDR-2.

## 10. Host-spacecraft interface

IR-HOST-DRAG-01 (DBF12-HOST-01, REFERENCE_PENDING_ICD): the host C_D*A is supplied at PDR and must stay within the
propulsion drag-compensation envelope. Reference proposal sizing is C_D*A = 0.50 m2, for reference sizing only
(VR-HOST-01).

## 11. What this description does not claim

- No measured thrust, Isp, efficiency, power, mass or life; every such value is a design allocation, an estimate or a
  model value with its label.
- No PASS / GO for any gate. Gate 3 is FAIL, the credible Hall transport set is empty and GNG-ICP-01 is NOT_EVALUATED.
- No thermal closure (DCR REQUIRED; DCR-DBF1-003 open for the RF match) and no ICP capacity (BLOCKED BY SPECIFIC MISSING EVIDENCE).
- The approximately 0.052 kg below 40 kg is open mass risk MR-DCR001-01 and not design margin.
