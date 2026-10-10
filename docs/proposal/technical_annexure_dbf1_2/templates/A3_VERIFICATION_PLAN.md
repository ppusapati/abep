# A3 - Verification plan (DBF-1.2 on EM / QM)

**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `{{SRC}}` (`{{SRC_FULL}}`). **No calendar date
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

{{VR_PLAN_TABLE}}

## 3. Requirement trace and verification state (DBF-1.2)

{{TRACE_TABLE}}

## 4. Mapping onto the RFP milestones (PROPOSED for owner confirmation)

| RFP milestone | offset / payment | RFP content | DBF-1.2 verification content |
|---|---|---|---|
| M1 PDR-1 (Hardware) | T0+09 months, 15 % | preliminary mechanical / electrical design, BoM, test plan, EM clearance (RFP-P20-04) | DBF-1.2 as the PDR-1 design. Early confirmations: PPU CBE (VR-PPU-01), Xe tank quotation (VR-XE-01), AL-09 / AL-10 CBEs, routed harness (VR-HAR-01) and mass risk MR-DCR001-01 re-assessed. Electronics FMEA (RFP-P18-09), host drag ICD (VR-HOST-01), compressor clearance design, RF-match thermal route (DCR-DBF1-003: isolation + radiator, or match relocation by DCR), test-facility document |
| M2 PDR-2 (Algorithms, Software, Test plan) | T0+12 months, 10 % | PSE software, FDIR, telemetry, facility readiness (RFP-P20-05) | PPU controller software incl. start-up sequencing and FDIR, 1553B / discrete ICD, AL-09 CBE, stand and metrology qualification, pre-registered EM acceptance criteria |
| M3 CDR | T0+20 months, 20 % | EM thruster and EM PSE demonstrated with STORAGE input (RFP-P20-06) | H-1 + ICP EM on stored N2 and Xe. Measured: B(z), thrust / feed map (VR-HALL-01 / -02), distributor uniformity (VR-FEED-01), Xe 25 mN thrust and bus power (VR-XE-02), non-discharge loads (VR-PWR-01), ICP capacity (GNG-ICP-01), EM mass |
| M4 EM intake; QM PSE and thruster | T0+24 months, 35 % | EM intake with compressor and storage; QM PSE and thruster (RFP-P21-01) | EM intake / compressor: mass (VR-CMP-01), F6 / B7 and Holweck characterisation (VR-CMP-02 / -03), spin / clearance test (VR-CMP-04), rarefied-gas intake test (RFP-P19-06 b). QM thruster on N2 and O2-bearing gas, plus AO coupon programme |
| M5 QM integration, ENTEST, delivery | T0+36 months, 20 % | total QM ABEP, ENTEST, delivery (RFP-P21-02) | QM integration, ENTEST (launch vibration / shock, AO, radiation, thermal, ThermoVac), life evidence (VR-EMQM-01); ATP after DDR / CDR |

**Schedule risk to disclose:** the Milestone-4 exit criterion (a qualified thruster with O and N2, RFP-P20-03) depends on
measured air-Hall performance, the ICP AIR closure ({{ICP_STATE}}) and atomic-O evidence that do not exist yet.

## 5. RFP test requirements (RFP-P19-06)

| RFP 4.1 item | plan | owner input |
|---|---|---|
| a) AO-beam coating / surface tests, erosion yield | AO / lifetime register (witness coupons, ground exposure, SEM / EDS / XPS); materials gates EM_VERIFICATION_REQUIRED | AO facility and fluence (OIR-FAC-04) |
| b) rarefied gas with prescribed mg/s and velocity for intake tests | M4 EM intake / compressor test | facility (OIR-FAC-03) |
| c) EM / QM force, variable intake mg/s, Isp, total-system efficiency | thrust stand INS-01, time-resolved bus-power metering; Isp and efficiency from the same measured thrust | stand ownership / resolution (OIR-FAC-02) |
| d) test plan reviewed by an expert committee, approved by PMMG / SPMMG | accepted as process | - |

The planned stand targets the 12-25 mN range and is not evidence of micro-newton capability (RFP-P30-01).
