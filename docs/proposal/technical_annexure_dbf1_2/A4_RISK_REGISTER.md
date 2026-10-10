# A4 - Risk register (DBF-1.2)

**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `45492a8` (`45492a8ef12fba13d262695bbd19f3631e80f355`),
`docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json`. Rule: an open verification item does not unfreeze the preliminary
baseline; it is verified during the funded EM / QM programme (mitigation and closure point in `A3_VERIFICATION_PLAN.md`).

## 1. Open risks and verification items

| id | item | basis | verification | status |
|---|---|---|---|---|
| MR-DCR001-01 | mass closure: preliminary roll-up 39.948 kg wet; ~0.052 kg numerical headroom is NOT design margin | A9.41 mass risk | CBE / quotation / EM mass measurement; any mass growth needs a DCR before acceptance | OPEN |
| VR-PPU-01 | AL-07 PPU preliminary CBE 4.55 kg (5.46 kg MEV) confirmation | v6 component estimate, mostly assumed | early PPU design / quotation (RFQ3-HALLEL); revert to 6.0 kg floor gives ~40.57 kg wet | OPEN |
| VR-XE-01 | Xe tank MEOP / burst factor / quotation | XA9-28 / XA9-29 TBD; 1.25 L Ti sphere sized at 150 bar, burst factor 2 | tank quotation with MEOP at 323 K | OPEN |
| VR-CMP-01 | compressor actual mass (7.767 kg MEV governing) | component estimates partly assumed | EM mass measurement | OPEN |
| VR-CMP-02 | compressor F6 / B7 transitional performance | F6 crosses 0.1 Pa, B7 transitional; not admitted | EM compressor characterisation | OPEN |
| VR-CMP-03 | Holweck coefficients | drag-channel form, coefficients uncited | EM test | OPEN |
| VR-CMP-04 | rotor growth / running clearance | drum growth 0.34-0.36 mm vs 0.3 mm running clearance | EM spin test, clearance design | OPEN |
| VR-FEED-01 | H1 distributor flow uniformity (+/-5 %) | preliminary interface requirement | EM flow-uniformity test | OPEN |
| VR-HALL-01 | air-Hall 26.8 km/s design-performance basis | PARAMETRIC / NOT_VALIDATED; Hall credible set empty | EM thrust measurement on N2 / air | OPEN |
| VR-HALL-02 | 22 km/s sensitivity (0.545 mg/s, ~6.1 Pa setpoint) | sensitivity case | EM verification | OPEN |
| VR-XE-02 | Xe 25 mN power / performance | allocation <= 876.1 W (nominal ICP) / <= 747.5 W (+100 W RF) at 1,450 W; ~658 W RP-1 Xe result PARAMETRIC / NOT_VALIDATED | EM / QM thrust and power measurement | OPEN |
| VR-PWR-01 | AIR 12 mN bus under the P6 conservative non-discharge corner | P-12 conservative corner + 77 W compressor allowance = 1469.9 W (below the 1,500 W RFP limit; reference / conservative design values 1222.3 / 1263.1 W) | measured non-discharge loads (RF generator efficiency, ICP, magnets, housekeeping) on EM; corner exceedance managed by RF / altitude schedule | OPEN |
| VR-HAR-01 | routed harness mass | 5/95 rule until routed | routed harness design | OPEN |
| VR-AL09-01 | AL-09 control-electronics CBE | 1.0 kg owner allocation | controller design CBE | OPEN |
| VR-AL10-01 | AL-10 structural / thermal CBE | 2.5 kg owner allocation | structural / thermal design CBE | OPEN |
| VR-HOST-01 | actual host C_D*A | IR-HOST-DRAG-01 reference 0.50 m2 | host ICD at PDR | OPEN |
| VR-EMQM-01 | EM / QM AO, thermal, life and qualification tests | RFP-P19-04 / P19-06 | EM / QM programme | OPEN |

## 2. Mass risk MR-DCR001-01

**Preliminary roll-up ≈39.95 kg wet (<40 kg); approximately 0.05 kg numerical headroom is carried as open mass risk MR-DCR001-01 and shall not be consumed as design margin.**

Drivers:

- AL-07 PPU preliminary CBE 4.55 kg (5.46 kg MEV) largely assumed; reverting to the 6.0 kg floor gives 40.57 kg wet
- AL-08 tank / plumbing / thermal estimates (assumed / model-derived) and Xe MEOP / burst factor TBD (XA9-28 / XA9-29)
- AL-01 / AL-02 integration itemization assumed; compressor component estimates (bearings, motors, drive, lock) assumed
- AL-09 1.0 kg and AL-10 2.5 kg owner allocations not yet CBEs; harness by the 5/95 rule until routed
- the 39.4 kg preferred target is missed by 0.548 kg

Mitigation:

- early AL-07 PPU design / quotation (RFQ3-HALLEL) replacing the preliminary CBE
- AL-08 tank quotation with MEOP at 323 K and burst factor fixed
- compressor EM mass measurement (rotor rows, drums, Holweck band, bearings, motors, drive)
- routed harness replacing the 5/95 rule
- any mass growth triggers a DCR before acceptance; the ranked closure levers stay PPU, Xe hardware, intake structure, structure / thermal

## 3. Programme-level risks carried with the baseline

These items are not DBF-1.2 records. They are stated with their governing record.

- **Hall-transport validation (gate 3) FAIL, credible transport set empty.** Air and Xe Hall performance rests on
  design allocations and PARAMETRIC / NOT_VALIDATED model values until the EM measurements (VR-HALL-01, VR-XE-02).
- **ICP neutralizer closure: BLOCKED BY SPECIFIC MISSING EVIDENCE** (`docs/closure/icp/icp_closure_v1.json` `#/closure`). I_e,cap: INCOMPLETE_EVIDENCE in every mode (model withheld; see model_evaluation_M_A);
  GNG-ICP-01: NOT_EVALUATED (criteria PENDING_OWNER_ACCEPTANCE).
- **Thermal closure: DCR REQUIRED** (`docs/closure/thermal/thermal_closure_v2.json` `#/closure`). DCR nodes: N_MATCH;
  requirement nodes: H1_ANODE, N_ANTENNA, N_COLLECTOR, N_HOUSING, N_MOUNT, R_HALL.
- **DCR-DBF1-003 (open, not applied to DBF-1.2): REQUESTED_EVALUATION_TO_BE_PREREGISTERED.** Items: DBF1-RF-03 (co-located adjustable match); DBF1-TH-01 (N_MATCH node, follows DBF1-RF-03). Reason: co-located match N_MATCH 147-184 degC in every preregistered hot case vs 60 degC ceiling (margin -124 K), fails at P_fwd = 0 W and at every radiator grid point: conduction from the ICP bracket (docs/closure/thermal/thermal_closure_v2.json sha 06b26333...).
  Routes: R-1 no-DCR: thermal isolation + dedicated radiator for the match (if it closes, DCR-DBF1-003 is withdrawn); R-2 DCR: relocate the match to the generator side. Both routes are evaluated under one preregistration; if route R-2 is chosen, DBF1-RF-03
  changes through a new baseline version.
- **Milestone-4 exit criterion** (qualified thruster with O and N2, RFP-P20-03) depends on the items above and on
  atomic-O evidence.

## 4. Baseline deficiencies (DBF-1.2 record)

| id | category | DBF-1.2 status |
|---|---|---|
| DBF1-BD-01 | DESIGN_VARIABLE_LIMIT (A9.35: A4-REG-01 open, no registered envelope bound) | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-02 | DESIGN_VARIABLE_LIMIT | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-03 | DESIGN_VARIABLE_LIMIT | SUPERSEDED_BY_DCR-DBF1-001 |
| DBF1-BD-04 | MISSING_EVIDENCE (no CBE) / DESIGN_VARIABLE_LIMIT (mass-closure actions MCA) | OPEN_AS_MASS_RISK_MR-DCR001-01 |
| DBF1-BD-05 | MISSING_EVIDENCE | CLOSED_BY_DCR-DBF1-002 |
| DBF1-BD-06 | MISSING_EVIDENCE | OPEN |
