# 06 - Submission checklist: RFP Part IV(A)-(H) forms and submission controls

Owner ruling A9.27 (`docs/decisions/OD_2026_10_05_A9_27_FINAL_BID_OWNER_RULINGS.md`): OIR-DOC-01 =
**REVIEW_COMPLETE_SUBMISSION_FORM_COMPLETION_PENDING**. The owner has reviewed the RFP pages that the repository does not
transcribe. This sheet maps every Part IV form to its source and to the files of this technical package. It is a
submission-readiness aid, not a physics or architecture gate. Technical source of every number in this package:
`5eee4b8c82a9403b6bb82d5f8d324526f5d6399b` (package / freeze record `docs/bid/bid_technical_baseline_v2.json`).

**What this sheet cannot do.** The repository holds no firm letterhead, signature, certificate, financial statement,
staff list, facility record or uploaded-file list. "Submitted (Yes/No)" therefore stays `OWNER TO FILL` until the owner
assembles the upload set, and the annexure numbers below are a PROPOSED numbering that the owner confirms or replaces when
filling the Part IV(H) Undertaking-cum-Checklist. OIR-DOC-01 closes only when the final submission set has been checked
against these forms and the IV(H) annexure numbers are populated.

## 1. Part IV forms

| Part | Form | Format requirement (RFP) | Content source | Package files that support it | Proposed annexure no. (owner confirms) | Submitted (Yes/No) |
|---|---|---|---|---|---|---|
| IV(A) | Detailed Project Report (DPR) | RFP DPR format | owner assembles the DPR in the RFP format from this package | `02_TECHNICAL_APPROACH.md`, `03_DEVELOPMENT_AND_TEST_PLAN.md`, `04_RISK_REGISTER.md`, `01_COMPLIANCE_MATRIX.md` (and `docx/`) | A-1 (DPR); A-1.1 compliance matrix; A-1.2 technical approach; A-1.3 development and test plan; A-1.4 risk register | OWNER TO FILL |
| IV(B) | Firm Essential Qualification Criteria | RFP format; supporting documents (e.g. CA-certified financial capability) | owner (OIR-ORG-02, OIR-ORG-03) | `05_PROGRAMMATIC_SECTIONS.md` section 6 (lists what is required; holds no firm data) | B-1 .. B-n (one per criterion document) | OWNER TO FILL |
| IV(C) | Technical Capability Evaluation | RFP format | owner (completed projects, present TRL, bench-top demonstration; OIR-ORG-03) | `05_PROGRAMMATIC_SECTIONS.md` section 6; `03_DEVELOPMENT_AND_TEST_PLAN.md` (planned evidence only - no Vyovrinda hardware test result exists in the repository) | C-1 .. C-n | OWNER TO FILL |
| IV(D) | Industry Profile | on firm letterhead where required, with the required supporting annexures | owner | none (firm data) | D-1 (profile); D-1.x supporting annexures | OWNER TO FILL |
| IV(E) | Non-Disclosure Undertaking | on firm letterhead | owner | none | E-1 | OWNER TO FILL |
| IV(F) | Acceptance Letter | on firm letterhead | owner | none | F-1 | OWNER TO FILL |
| IV(G) | Eligibility Certificate | on firm letterhead | owner | none | G-1 | OWNER TO FILL |
| IV(H) | Undertaking-cum-Checklist | RFP format, including Submitted Yes/No and Annexure numbers | owner fills it last, from the actual upload set | this sheet (mapping only) | H-1 | OWNER TO FILL |

## 2. Submission controls (RFP; owner ruling A9.27)

| Control | How this package meets it / what the owner must do |
|---|---|
| Technical and financial bids are separate | This package is the technical bid only; `05_PROGRAMMATIC_SECTIONS.md` section 5 defers all commercial content to the financial bid (OIR-COM-01). |
| Financial bid uses the provided format | Owner: use the RFP-provided financial format only. |
| Prescribed financial-bid format / filename not modified | Owner: keep the prescribed format and filename unchanged. |
| No project cost / price information in the technical bid | This package contains no price, cost estimate or currency amount (checked by `tests/test_bid_package.py`); the RFP payment-milestone percentages are mentioned only as a commercial item deferred to the financial bid. The owner must keep firm documents attached to the technical bid free of price / cost information. |
| Uploads follow the RFP submission requirements | Owner: upload format, naming and size per the RFP instructions. |
| The final Part IV(H) checklist reconciles the annexures actually submitted | Owner: fill IV(H) from the final upload list; every annexure number in IV(H) must exist in the upload set and vice versa. |

## 3. Final file-by-file completeness check (owner, before upload)

- [ ] IV(A) DPR assembled in the RFP format; technical content consistent with `01`-`04` at `5eee4b8` (no edits to numbers).
- [ ] IV(B), IV(C) supporting documents attached and numbered.
- [ ] IV(D) industry profile on letterhead with its annexures.
- [ ] IV(E), IV(F), IV(G) on letterhead, signed.
- [ ] IV(H) Undertaking-cum-Checklist filled: Submitted Yes/No and annexure numbers match the upload set.
- [ ] No price / cost in any technical-bid file; financial bid only in the prescribed format and filename.
- [ ] Internal working files are NOT uploaded (e.g. `docs/bid/OWNER_DECISION_BRIEF_P0_P1.md`, decision records, this repository's audit and history files).
