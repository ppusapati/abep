# A3 - Verification plan (DBF-1.2 on EM / QM)

**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `45492a8` (`45492a8ef12fba13d262695bbd19f3631e80f355`). **No calendar date
is stated.** Times are the RFP's own T0 offsets and payment percentages (RFP-P20-04 .. RFP-P21-02). T0 is not set.

DBF-1.2 is a preliminary design baseline that conforms by design and allocation, and compliance is verified on EM / QM
hardware. Each open item below is verified without unfreezing the baseline. A verification outcome that would change a
frozen value is handled as a DCR (`docs/baseline/DBF-1/DCR_PROCESS.md`), never as an edit.

## 1. Principles

1. **Hardware decides performance.** Thrust, power, mass and life compliance come from measurements on Vyovrinda EM / QM
   hardware, never from the simulator (`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json`).
2. **Fail-closed.** Missing evidence is NOT_EVALUATED / INCOMPLETE_EVIDENCE, never PASS or GO.
3. **Pre-registration.** Acceptance criteria are frozen before the data scored against them.
4. **Evidence order by gas:**
   1. Ar (engineering only);
   2. N2;
   3. O2-bearing (labelled NO_ATOMIC_O);
   4. the atomic-O life programme.
5. **Baseline control.** Mass growth, power growth or any change to a frozen item needs an approved DCR before
   acceptance.

## 2. Verification of the DBF-1.2 open items

The "first closure point" column is this annexure's PROPOSED mapping, for the owner to confirm; the method column is the
DBF-1.2 record.

| DBF-1.2 item | what is verified | method (DBF-1.2) | first closure point (PROPOSED) |
|---|---|---|---|
| MR-DCR001-01 | mass closure: preliminary roll-up 39.948 kg wet; ~0.052 kg numerical headroom is NOT design margin | CBE / quotation / EM mass measurement; any mass growth needs a DCR before acceptance | M1 (CBE / quotations) -> M3 / M4 (EM mass measurement) |
| VR-PPU-01 | AL-07 PPU preliminary CBE 4.55 kg (5.46 kg MEV) confirmation | early PPU design / quotation (RFQ3-HALLEL); revert to 6.0 kg floor gives ~40.57 kg wet | M1 (early PPU design / quotation) |
| VR-XE-01 | Xe tank MEOP / burst factor / quotation | tank quotation with MEOP at 323 K | M1 (tank quotation, MEOP at 323 K) |
| VR-CMP-01 | compressor actual mass (7.767 kg MEV governing) | EM mass measurement | M4 (EM compressor mass) |
| VR-CMP-02 | compressor F6 / B7 transitional performance | EM compressor characterisation | M4 (EM compressor characterisation) |
| VR-CMP-03 | Holweck coefficients | EM test | M4 (EM compressor test) |
| VR-CMP-04 | rotor growth / running clearance | EM spin test, clearance design | M4 (EM spin test; clearance design at M1) |
| VR-FEED-01 | H1 distributor flow uniformity (+/-5 %) | EM flow-uniformity test | M3 (EM thruster flow-uniformity test) |
| VR-HALL-01 | air-Hall 26.8 km/s design-performance basis | EM thrust measurement on N2 / air | M3 (EM thrust on N2 / air, storage input) |
| VR-HALL-02 | 22 km/s sensitivity (0.545 mg/s, ~6.1 Pa setpoint) | EM verification | M3 (EM thrust map) |
| VR-XE-02 | Xe 25 mN power / performance | EM / QM thrust and power measurement | M3 (EM / QM Xe thrust and bus power) |
| VR-PWR-01 | AIR 12 mN bus under the P6 conservative non-discharge corner | measured non-discharge loads (RF generator efficiency, ICP, magnets, housekeeping) on EM; corner exceedance managed by RF / altitude schedule | M3 (measured non-discharge loads on EM) |
| VR-HAR-01 | routed harness mass | routed harness design | M1 (routed harness design) |
| VR-AL09-01 | AL-09 control-electronics CBE | controller design CBE | M1 / M2 (controller design CBE) |
| VR-AL10-01 | AL-10 structural / thermal CBE | structural / thermal design CBE | M1 (structural / thermal CBE) |
| VR-HOST-01 | actual host C_D*A | host ICD at PDR | M1 (host ICD at PDR) |
| VR-EMQM-01 | EM / QM AO, thermal, life and qualification tests | EM / QM programme | M4 -> M5 (QM ENTEST) |

## 3. Requirement trace and verification state (DBF-1.2)

| requirement | RVM | RFP clauses | DBF-1.2 items | DBF-1.2 state | note |
|---|---|---|---|---|---|
| altitude 180-230 km | RVM-01 | RFP-P18-08 | DBF12-OPS-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM | density-aware altitude scheduling |
| >= 12 mN sustained atmospheric | RVM-02 | RFP-P18-06 | DBF12-AIR-01, DBF12-PWR-05 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM | 12 mN at P_d 650 W inside the AIR window; not demonstrated |
| 25 mN capability | RVM-03 | RFP-P18-06 | DBF12-OPS-02, DBF12-PWR-06 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM | Xe mode (A9.40); Xe use booked; not atmospheric |
| P_bus < 1500 W | RVM-04 | RFP-P18-10 | DBF12-PWR-05, DBF12-PWR-06 | CONFORMING_BY_DESIGN_ALLOCATION / VERIFY_EM_QM | AIR 1222.3 / 1263.1 W; Xe 25 mN at <= 1450 W design ceiling |
| internal 1350 W allocation | RVM-05 | - | DBF1-PWR-01, DBF12-PWR-05 | WITHIN_ALLOCATION (AIR nominal) | Xe 25 mN capability uses the 1350-1450 W band (non-nominal, A9.40) |
| mass < 40 kg | RVM-06 | RFP-P18-11 | DBF12-MASS-05 | CONFORMING_BY_PRELIMINARY_ROLLUP / OPEN_MASS_RISK | 39.948 kg wet; MR-DCR001-01 |
| internal 34 / 36 kg allocation | RVM-07 | - | DBF1-MASS-02, DBF12-MASS-05 | TARGET_NOT_MET (nominal dry 34.498 kg) | DBF1-BD-04 open as mass risk |
| atmospheric propellant | RVM-08 | RFP-P18-08, RFP-P17-03, RFP-P17-04 | DBF12-IN-01, DBF12-CMP-01, DBF12-FEED-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM | intake + compressor + plenum / feed |
| Xe capability, two separate tanks | RVM-10 / RVM-29 | RFP-P18-08, RFP-P17-05 | DBF12-OPS-02 | CONFORMING_BY_DESIGN | AL-08 Xe branch 2 kg reference |
| Hall preferred | RVM-11 | RFP-P18-07 | DBF1-H1-01 | CONFORMING_BY_DESIGN | H1 inherited unchanged |
| neutralization (cathodeless) | RVM-15 / RVM-28 | - | DBF1-ICP-01 | CONFORMING_BY_DESIGN / VERIFY_EM_QM | ICP inherited unchanged |
| AO material compatibility | RVM-16 | RFP-P19-04 | DBF1-MAT-01 | VERIFY_EM_QM | materials inherited |
| thermal closure | RVM-17 | - | DBF1-TH-01 | VERIFY_EM_QM | thermal inherited; anode / coupled thermal UNRESOLVED |
| electronics redundancy (no SPF) | RVM-19 | RFP-P18-09, RFP-P18-02 | DBF12-MASS-05 | CONFORMING_BY_DESIGN (PPU N+1) / VERIFY_FMEA | v6 PPU CBE carries N+1 / redundant electronics |
| MIL-1553B interface | RVM-20 | RFP-P18-12 | - | ALLOCATED_TO_AL-09 | controls allocation |
| environmental qualification | RVM-21 | RFP-P19-04 | - | VERIFY_EM_QM | EM / QM programme |
| mission life / firing hours | RVM-12 / RVM-13 | - | - | VERIFY_EM_QM | life tests |

## 4. Mapping onto the RFP milestones (PROPOSED for owner confirmation)

| RFP milestone | offset / payment | RFP content | DBF-1.2 verification content |
|---|---|---|---|
| M1 PDR-1 (Hardware) | T0+09 months, 15 % | preliminary mechanical / electrical design, BoM, test plan, EM clearance (RFP-P20-04) | DBF-1.2 as the PDR-1 design. Early confirmations: PPU CBE (VR-PPU-01), Xe tank quotation (VR-XE-01), AL-09 / AL-10 CBEs, routed harness (VR-HAR-01) and mass risk MR-DCR001-01 re-assessed. Electronics FMEA (RFP-P18-09), host drag ICD (VR-HOST-01), compressor clearance design, RF-match thermal route (DCR-DBF1-003: isolation + radiator, or match relocation by DCR), test-facility document |
| M2 PDR-2 (Algorithms, Software, Test plan) | T0+12 months, 10 % | PSE software, FDIR, telemetry, facility readiness (RFP-P20-05) | PPU controller software incl. start-up sequencing and FDIR, 1553B / discrete ICD, AL-09 CBE, stand and metrology qualification, pre-registered EM acceptance criteria |
| M3 CDR | T0+20 months, 20 % | EM thruster and EM PSE demonstrated with STORAGE input (RFP-P20-06) | H-1 + ICP EM on stored N2 and Xe. Measured: B(z), thrust / feed map (VR-HALL-01 / -02), distributor uniformity (VR-FEED-01), Xe 25 mN thrust and bus power (VR-XE-02), non-discharge loads (VR-PWR-01), ICP capacity (GNG-ICP-01), EM mass |
| M4 EM intake; QM PSE and thruster | T0+24 months, 35 % | EM intake with compressor and storage; QM PSE and thruster (RFP-P21-01) | EM intake / compressor: mass (VR-CMP-01), F6 / B7 and Holweck characterisation (VR-CMP-02 / -03), spin / clearance test (VR-CMP-04), rarefied-gas intake test (RFP-P19-06 b). QM thruster on N2 and O2-bearing gas, plus AO coupon programme |
| M5 QM integration, ENTEST, delivery | T0+36 months, 20 % | total QM ABEP, ENTEST, delivery (RFP-P21-02) | QM integration, ENTEST (launch vibration / shock, AO, radiation, thermal, ThermoVac), life evidence (VR-EMQM-01); ATP after DDR / CDR |

**Schedule risk to disclose:** the Milestone-4 exit criterion (a qualified thruster with O and N2, RFP-P20-03) depends on
measured air-Hall performance, the ICP AIR closure (BLOCKED BY SPECIFIC MISSING EVIDENCE) and atomic-O evidence that do not exist yet.

## 5. RFP test requirements (RFP-P19-06)

| RFP 4.1 item | plan | owner input |
|---|---|---|
| a) AO-beam coating / surface tests, erosion yield | AO / lifetime register (witness coupons, ground exposure, SEM / EDS / XPS); materials gates EM_VERIFICATION_REQUIRED | AO facility and fluence (OIR-FAC-04) |
| b) rarefied gas with prescribed mg/s and velocity for intake tests | M4 EM intake / compressor test | facility (OIR-FAC-03) |
| c) EM / QM force, variable intake mg/s, Isp, total-system efficiency | thrust stand INS-01, time-resolved bus-power metering; Isp and efficiency from the same measured thrust | stand ownership / resolution (OIR-FAC-02) |
| d) test plan reviewed by an expert committee, approved by PMMG / SPMMG | accepted as process | - |

The planned stand targets the 12-25 mN range and is not evidence of micro-newton capability (RFP-P30-01).
