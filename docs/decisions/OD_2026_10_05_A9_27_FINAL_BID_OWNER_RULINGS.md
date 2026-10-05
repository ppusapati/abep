# FINAL BID OWNER RULINGS — DOCUMENT FORMATS AND TWO COMPLIANCE ITEMS (A9.27) — verbatim record

Recorded verbatim from the owner's session message of 2026-10-05 (text extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_05_A9_27_final_bid_owner_rulings.json`. Immutable after commit. Post-source owner decision for the bid package (the technical source 5eee4b8 is not changed).

---

## Message 1 — FINAL_BID_RULINGS — 2026-10-05T05:26:13.889Z — text sha256 `f3af158fe287af92519013cf5e5d3cf5e168f619df6f7eea2c40ef5ba972742d`

````text
FINAL BID OWNER RULINGS — DOCUMENT FORMATS AND TWO COMPLIANCE ITEMS

Protect the frozen bid pair:

TECHNICAL SOURCE:
5eee4b8c82a9403b6bb82d5f8d324526f5d6399b

PACKAGE / FREEZE RECORD:
b5849affae22a6709ad217a184f6fe896d15410a

Do not move the bid technical source to later performance/Rust-planning commits.

==================================================
1. OIR-DOC-01 — REVIEW COMPLETE, FORM COMPLETION STILL REQUIRED
==================================================

I have now independently reviewed the actual RFP pages that the repository had
previously marked unscreened.

Do NOT leave OIR-DOC-01 described as "pages not reviewed".

Change its state to an equivalent of:

    REVIEW_COMPLETE_SUBMISSION_FORM_COMPLETION_PENDING

The actual RFP contains mandatory submission forms/instructions.

Final submission must account for:

Part IV(A)
    Detailed Project Report / DPR

Part IV(B)
    Firm Essential Qualification Criteria

Part IV(C)
    Technical Capability Evaluation

Part IV(D)
    Industry Profile
    on firm's letterhead where required
    with required supporting annexures

Part IV(E)
    Non-Disclosure Undertaking
    on firm letterhead

Part IV(F)
    Acceptance Letter
    on firm letterhead

Part IV(G)
    Eligibility Certificate
    on firm letterhead

Part IV(H)
    Undertaking-cum-Checklist
    including Submitted Yes/No and Annexure numbers.

Also preserve these submission controls from the RFP:

- technical and financial bids are separate;
- financial bid must use the provided format;
- do not modify the prescribed financial-bid format / filename;
- do not put project cost / price information into the technical bid;
- uploaded documents are to follow the RFP submission requirements;
- final Part IV(H) checklist must reconcile the actual annexures submitted.

OIR-DOC-01 closes only when the final submission set has been checked against
these exact forms and the annexure numbers are populated.

This is a submission-readiness item, not a physics/architecture gate.

Do not alter the frozen technical source merely to record this administrative
review unless necessary.

==================================================
2. RFP-P19-03 — UPGRADE TO COMPLY
==================================================

OWNER DECISION:

Set:

    RFP-P19-03 = COMPLY

Basis:

The offered system architecture explicitly contains the three subsystem
categories required by the clause:

1. Air intake + compressor/storage;
2. Power Supply Electronics;
3. Thruster.

This is a property of the offered architecture and can therefore be answered
from the proposal definition itself.

Add an explicit qualification:

    COMPLY here confirms the proposed system composition only.
    It does not claim that the performance, qualification or determining
    evidence of each subsystem has already been completed.

Do not change any engineering gate status because of this.

==================================================
3. RFP-P18-08 — DO NOT UPGRADE THE WHOLE CLAUSE
==================================================

Keep the overall clause as:

    COMPLY_PLANNED_WITH_EVIDENCE_PATH

or the existing equivalent status.

The clause has two separable aspects.

A. SEPARATE PROPELLANT TANKS / PATHS

The offered architecture commits to:

    separate ambient-air and Xe tanks / supply paths

Therefore state in the response:

    COMPLY BY DESIGN — separate tanks / paths are part of the offered architecture.

B. FUNCTIONAL AMBIENT-AIR + Xe CAPABILITY

The system is designed to support both propellants, but determining functional
demonstration is not yet complete.

Therefore state:

    PLANNED / NOT YET DEMONSTRATED

with the existing evidence/test path.

Do NOT make the whole RFP-P18-08 row COMPLY, because that would imply functional
dual-propellant capability has already been demonstrated.

==================================================
4. PERFORMANCE BASELINE / RUST PRIORITIZATION
==================================================

Accept the pre-Rust performance baseline at adce2e9 as POST-FREEZE evidence.

It does not alter the bid technical source.

When revising the Rust migration plan, classification governs BEFORE runtime.

Therefore:

- legacy uq_modular being slow does NOT mean it should automatically be ported;
- legacy archengine being slow does NOT mean it should automatically be ported;
- if they are HISTORICAL / RETIRED, retire them rather than port them;
- extract only architecture-independent kernels still required by the selected
  architecture;
- active intake response-surface work remains a genuine migration/performance
  target.

Use:

    architecture relevance first
    evidence/parity eligibility second
    measured performance third

for migration ordering.

==================================================
5. MPV3Q-01 STALE OWNER-QUESTION RECORD
==================================================

Do not reopen the frozen technical source solely to repair the stale v5
owner-question-state record before submission.

MPV3Q-01 is already resolved by A9.26:

    AL-09 = 1.0 kg
    PROVISIONAL_OWNER_ALLOCATION
    NOT CBE / NOT MEASURED.

If the stale owner-question state is NOT displayed or relied upon by the bid
package, repair it post-bid using a successor record.

If any submitted bid document currently says MPV3Q-01 is still open, STOP and
correct that bid-facing contradiction before submission.

==================================================
6. FINAL SUBMISSION PRIORITY
==================================================

At this point do not perform further architecture or physics work before
submission.

Priority is now:

1. finish exact Part IV(A)-(H) submission-format audit;
2. populate the final annexure/checklist mapping;
3. ensure no price/cost appears in the technical bid where prohibited;
4. apply only the P19-03 and P18-08 response/status rulings above;
5. regenerate/check the package if those bid-text changes require it;
6. perform a final file-by-file submission completeness audit;
7. submit.

Do not disturb the frozen technical source 5eee4b8.
````

