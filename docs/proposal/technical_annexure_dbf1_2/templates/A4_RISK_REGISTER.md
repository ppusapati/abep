# A4 - Risk register (DBF-1.2)

**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `{{SRC}}` (`{{SRC_FULL}}`),
`docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json`. Rule: an open verification item does not unfreeze the preliminary
baseline; it is verified during the funded EM / QM programme (mitigation and closure point in `A3_VERIFICATION_PLAN.md`).

## 1. Open risks and verification items

{{RISK_TABLE}}

## 2. Mass risk MR-DCR001-01

**{{MASS_WORDING}}**

Drivers:

{{MR_DRIVERS}}

Mitigation:

{{MR_MITIGATION}}

## 3. Programme-level risks carried with the baseline

These items are not DBF-1.2 records. They are stated with their governing record.

- **Hall-transport validation (gate 3) FAIL, credible transport set empty.** Air and Xe Hall performance rests on
  design allocations and PARAMETRIC / NOT_VALIDATED model values until the EM measurements (VR-HALL-01, VR-XE-02).
- **ICP neutralizer closure: {{ICP_STATE}}** (`docs/closure/icp/icp_closure_v1.json` `#/closure`). I_e,cap: {{ICP_IECAP}};
  GNG-ICP-01: {{ICP_GNG}}.
- **Thermal closure: {{THERM_STATE}}** (`docs/closure/thermal/thermal_closure_v2.json` `#/closure`). DCR nodes: {{TH_DCR_NODES}};
  requirement nodes: {{TH_REQ_NODES}}.
- **DCR-DBF1-003 (open, not applied to DBF-1.2): {{DCR3_STATUS}}.** Items: {{DCR3_ITEMS}}. Reason: {{DCR3_REASON}}.
  Routes: {{DCR3_ROUTES}}. Both routes are evaluated under one preregistration; if route R-2 is chosen, DBF1-RF-03
  changes through a new baseline version.
- **Milestone-4 exit criterion** (qualified thruster with O and N2, RFP-P20-03) depends on the items above and on
  atomic-O evidence.

## 4. Baseline deficiencies (DBF-1.2 record)

{{DEFICIENCY_TABLE}}
