# POWER RECONCILIATION AND DBF-1.2 FREEZE (A9.43) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-10 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_10_A9_43_power_reconciliation_and_dbf_1_2_freeze.json`. Immutable after commit.

---

## Message 1 — RESOLVE_POWER_HOLD_AND_FREEZE_DBF_1_2 — 2026-10-10T13:00:02.998Z — text sha256 `492e9cbcc0c0119b94d331ccb631e715354174ed9caf770a3f2eb76673a3128f`

````text
OWNER DIRECTION — RESOLVE POWER HOLD AND FREEZE DBF-1.2
I confirm the following decisions.
1. AIR discharge-power basis — OPTION A APPROVED
Use:
H1 discharge power = 650 W
for the DBF-1.2 AIR 12 mN design point.
Reason:

* 650 W is the frozen lower bound of DBF1-H1-06;
* 650 W is the existing P6 `P-12` allocation;
* there is no justification to open another DCR merely to lower the H1 frozen operating band so that an earlier power prediction remains unchanged.

Therefore DO NOT use approximately 596–600 W as the governing frozen AIR discharge-power value.
Those values may remain as historical/model-predicted values in DCR-001 records, but they do not govern DBF-1.2.
Do not edit immutable historical DCR records.
Create a new reconciliation record referencing them.
DBF-1.2 AIR power
Using the approved DBF-1.2 compressor:

* AIR 12 mN nominal/reference bus power: approximately 1.22 kW
* AIR conservative bus power: approximately 1.26 kW

Recompute the exact deterministic values from the authoritative P6 ledger plus the DBF-1.2 compressor loads. Do not hard-code my rounded numbers.
Both must remain:

* below the 1,350 W internal design allocation, and
* below the RFP requirement <1,500 W.

The 650 W point is a design allocation/operating point, not measured Hall performance.
If the analytical model predicts approximately 12.5 mN at this point, retain that only as:
MODEL-DERIVED / NOT VALIDATED
Do not freeze “12.5 mN demonstrated thrust”.
The requirement remains the 12 mN AIR design point pending EM verification.
2. Xe 25 mN power arithmetic — corrected values APPROVED
Use the P6 ledger as authoritative.
The earlier DCR-001 v4 arithmetic contained bookkeeping errors and is superseded for the active DBF-1.2 power roll-up.
At the 1,450 W proposal design ceiling, freeze the available Hall discharge allocations as:

* nominal ICP: ≤876.1 W
* ICP with +100 W RF sensitivity: ≤747.5 W

At the RFP <1,500 W boundary:

* nominal ICP: <918.6 W
* ICP with +100 W RF sensitivity: <790.0 W

Recompute exact values from the ledger in the builder and preserve full precision internally.
Use the correct:

* Xe non-discharge load from P6;
* discharge-chain efficiency `0.850725`;
* RF bus conversion from the P6 ledger.

Do not reuse the old:

* 412.5 W non-discharge value;
* 0.855 chain efficiency;
* +129 W bus increment for +100 W RF.

3. Xe 25 mN status
The approximately 658 W RP-1 Xe result remains:
PARAMETRIC / NOT_VALIDATED
It may support feasibility but shall not be used as proof that 25 mN has been demonstrated.
DBF-1.2 shall state:
Xe 25 mN is a design capability requirement. The Hall discharge-power allocation is ≤876 W at the 1,450 W design ceiling under the nominal ICP case and ≤748 W under the +100 W RF sensitivity case. Performance is to be verified on EM/QM hardware.
4. No architecture or mass change
This reconciliation changes power accounting only.
Do not change:

* intake;
* compressor;
* plenum;
* Hall geometry;
* ICP architecture;
* AIR sizing flow;
* operating concept;
* mass roll-up;
* PPU mass;
* Xe hardware mass;
* MR-DCR001-01;
* host interface.

The approved mass remains:

* nominal dry ≈ 34.498 kg
* dry with 10% system margin ≈ 37.948 kg
* +2 kg Xe
* wet ≈ 39.948 kg
* MR-DCR001-01 remains OPEN.

5. Record the reconciliation
Create a new owner/reconciliation decision after A9.42.
Do not rewrite A9.40, A9.41, A9.42 or historical DCR files.
Record explicitly:

1. DBF1-H1-06 650 W lower bound governs the AIR 12 mN freeze;
2. DCR-001 596/600 W figures are historical model predictions and not governing power allocations;
3. corrected Xe allocations use the authoritative P6 ledger;
4. no physical architecture change occurred;
5. no DCR is required because no frozen hardware/design value is being changed — this is reconciliation to the already-frozen power boundary.

6. Resume DBF-1.2 build
The A9.42 stop condition is now resolved.
Proceed with the previously authorized deterministic DBF-1.2 build.
Exact status:
DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM
Run all previously specified integrity checks:

* builder `--check`;
* mass arithmetic;
* power arithmetic;
* RFP/RVM trace;
* source pins/hashes;
* DCR consistency;
* schema;
* affected tests;
* golden/reference integrity;
* Rule-9 / repository integrity where applicable.

If another factual inconsistency is found, stop rather than changing the design silently.
Otherwise freeze DBF-1.2 and report:

1. final commit SHA;
2. lock/hash;
3. files created;
4. exact AIR and Xe power table;
5. frozen mass table;
6. validation results;
7. open risks;
8. confirmation DBF-1 and DBF-1.1 remain unchanged;
9. confirmation that no proposal document was regenerated.

Then report exactly:
DBF-1.2 FROZEN — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM
Then STOP.
````
