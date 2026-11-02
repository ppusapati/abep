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
- **Thermal closure: {{THERM_STATE}}** (`docs/closure/thermal/dcr003_evaluation_v3.json` `#/p7_closure_state`, post-freeze
  record at `{{PF_COMMIT}}`). DCR nodes: {{TH_DCR_NODES}} (at the freeze: {{TH_DCR_NODES_FREEZE}}, state
  {{THERM_STATE_FREEZE}}); requirement nodes: {{TH_REQ_NODES}}. The heat into the host ({{Q_SC}} W against the provisional
  {{Q_SC_ALLOC}} W allocation) is the open interface item.
- **DCR-DBF1-003: {{DCR3_STATUS}}** (open at the DBF-1.2 freeze as {{DCR3_FREEZE_STATUS}}). Items: {{DCR3_ITEMS}}.
  Reason it was opened: {{DCR3_REASON}}. Outcome: {{DCR3_OUTCOME}}. Residual risk: the RF-match margin ({{MATCH_MARGIN}} K
  inside the 50 K rule) rests on assumed standoff and lead conductances and a PARAMETRIC / NOT_VALIDATED model; it is
  verified by measured standoff conductance, lead RF loss and EM thermal balance (RVM-17).
- **Milestone-4 exit criterion** (qualified thruster with O and N2, RFP-P20-03) depends on the items above and on
  atomic-O evidence.

## 4. Baseline deficiencies (DBF-1.2 record)

{{DEFICIENCY_TABLE}}
