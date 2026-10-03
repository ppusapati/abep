# Bid technical submission package - DRAFT

**Tender 2026_DRDO_788433_1 - RFP DTDF/06/13516/DSP/ABEP/X/L/M/01, "Air Breathing Space Based Propulsion (Electric) for
VLEO" (DRDO / Directorate of Technology Development Fund). Bidder: Vyovrinda Aerospace. Operational submission deadline
2026-10-05 17:00 (DefProc; owner decision A9.21 BID_CLOSE, unless a corrigendum changes it).**

**Package status: DRAFT_FOR_OWNER_REVIEW.** The repository submits nothing. This package is the technical draft that the
owner reviews, completes (owner-input checklist below) and submits through DefProc. It is not a finished DPR, Part-IV
response or technical proposal in the RFP's own formats.

## Technical source (bid freeze)

- Freeze commit: **`bbc480cd6aacaa40c39eb459a056b942fe996b32`** (`bbc480c`, branch `claude/nifty-ramanujan-w68f9z`, tag name recorded as
  `bid-technical-baseline-2026-10-05`); freeze record `docs/bid/bid_technical_baseline.json` (owner P0 decision
  2026-10-03). Verification recorded at the freeze: full suite 3871 passed / 5 skipped / 1 xfailed, golden OK,
  ci_checks 11/11.
- Every technical number, status and claim in this package cites a file at `bbc480c` (read with
  `git show bbc480c:<path>`). Commits after `bbc480c` are post-freeze engineering work and are not bid sources, except the
  freeze record itself and its post-freeze caveat (quoted verbatim in `04_RISK_REGISTER.md`, R-03).
- Architecture at the freeze: one Hall accelerator (H-1) + one downstream 13.56 MHz RF-ICP electron source /
  neutralizer; ambient air (primary) + Xe (contingency / emergency, A9.19); the C1 hollow cathode is a ground-only
  laboratory reference (A9.20); status INVESTIGATION_HYPOTHESIS. Hall validation (gate 3) is FAIL, the credible transport
  set is empty, and every absolute Hall number of the superseded 0-D closure is withdrawn and not quoted.

## Documents

| file | content | RFP structure served | status |
|---|---|---|---|
| `README.md` | this cover: document list, freeze SHA, owner-input checklist, unscreened-pages note | - | DRAFT_FOR_OWNER_REVIEW |
| `01_COMPLIANCE_MATRIX.md` (+ `compliance_matrix_v1.json`) | clause-by-clause response to all 37 registered clauses with status and evidence path at bbc480c; gate statuses at the freeze | Part III para 1-8 (technical requirements table, logical block diagram RFP-P16-02, EM / QM deliverables RFP-P17-01, milestones RFP-P20-04..P21-02), Part IV(B) 3 / 5 (RFP-P27-01 / -02), Part IV(C) 5 (RFP-P30-01) | DRAFT_FOR_OWNER_REVIEW (generated) |
| `02_TECHNICAL_APPROACH.md` | architecture, block-diagram and subsystem mapping (RFP-P16-02, RFP-P19-03), thruster, ICP neutralizer, propellant handling, PPU from the bus, redundancy, MIL-1553B, mass, thermal / materials / life, validation status | Part III para 1-2 | DRAFT_FOR_OWNER_REVIEW |
| `03_DEVELOPMENT_AND_TEST_PLAN.md` | A9.21 hardware order, gates (GNG-ICP-01 before LOCK-1), proposed mapping onto M1-M5 at the RFP T0 offsets, RFP-P19-06 tests | Part III para 4.1, 7 | DRAFT_FOR_OWNER_REVIEW |
| `04_RISK_REGISTER.md` | top technical risks R-01..R-13 with repository mitigations; post-freeze caveat verbatim (owner decision point) | Part III para 6 | DRAFT_FOR_OWNER_REVIEW |
| `05_PROGRAMMATIC_SECTIONS.md` | skeletons: indigenous-content plan, facilities, team / collaboration, certification, cost / commercial, company credentials | RFP-P18-03, RFP-P19-05, RFP-P20-01, RFP-P27-01 / -02, RFP-P30-01, Part IV(B) / (C) | DRAFT_FOR_OWNER_REVIEW - SKELETON |
| `docx/*.docx` | Word renderings of the six Markdown files above (generated; the Markdown is the source) | - | DRAFT_FOR_OWNER_REVIEW (generated) |
| `compliance_data.py`, `build_package.py` | data source and generator (`python docs/bid/package/build_package.py`; `--check` verifies the generated matrix) | - | tooling |

Test: `tests/test_bid_package.py` (every registered clause in the matrix; every cited evidence path exists at `bbc480c`
and every JSON locator resolves there; no withdrawn Hall result phrase; no PASS / GO for any gate that is not PASS / GO
at the freeze; every owner-input id is in this checklist).

## Compliance-status counts (37 registered clauses)

- COMPLY: 1
- COMPLY_PLANNED_WITH_EVIDENCE_PATH: 16
- PARTIAL: 1
- NOT_YET_DEMONSTRATED: 10
- OWNER_INPUT_REQUIRED: 9

The single COMPLY (RFP-P18-07, "Hall effect preferable") states the offered thruster type only; no Hall performance is
demonstrated.

## RFP pages NOT screened - owner must check

The repository's RFP registration (`docs/requirements/rfp_official/rfp_registration_v1.json`, 40-page PDF registered by
sha256) screened pages 16-33 only. **Pages 1-15 and 34-40 (bid / legal / format front and back matter) were NOT
screened** (status UNSCREENED_PENDING_OWNER_PAGE_REVIEW); nothing is assumed about them. The owner must check those pages
for mandatory formats, annexures, declarations, undertakings, compliance-statement formats and submission instructions,
and must fill the DPR template (pp. 22-25) and the industry profile (pp. 32-33), which were screened from the PDF text
layer only (OIR-DOC-01).

## Owner-input checklist (every OWNER_INPUT_REQUIRED item)

- [ ] **OIR-IC-01** - Indigenous-content plan figures: per-subsystem IC % (thruster, intake, compressor + storage, PSE) and project IC % with the computation basis (RFP-P19-05 / RFP-P18-03 a; Part IV(C) 2 scoring). Clauses: RFP-P18-03, RFP-P19-05.
- [ ] **OIR-IC-02** - Supplier / make-or-buy list with country of origin for every BoM line (RFQ v3 packages are quotation-only; nothing selected). Clauses: RFP-P18-03, RFP-P19-05.
- [ ] **OIR-IC-03** - Indigenization roadmap for any imported item (e.g. Xe tank / regulator, RF components, 1553B core) with ITAR / export-control exposure statement. Clauses: RFP-P19-05.
- [ ] **OIR-ORG-01** - ISO certification: standard, scope, certificate number, validity (RFP-P20-01 4.3). Clauses: RFP-P20-01.
- [ ] **OIR-ORG-02** - Financial capability: CA-certified net-worth document (Part IV(B) 1). Clauses: RFP-P21-03.
- [ ] **OIR-ORG-03** - In-house expertise / heritage evidence: indigenous EP system realization, space-grade electronics, vacuum test systems (Part IV(B) 2; Part IV(C) 1, 3). Clauses: RFP-P21-03.
- [ ] **OIR-ORG-04** - Technical-evaluation presentation: presenters and date availability (RFP-P18-03 b). Clauses: RFP-P18-03.
- [ ] **OIR-ORG-05** - Consortium: whether proposed, members, roles, signed consortium agreement (RFP-P18-03 c). Clauses: RFP-P18-03.
- [ ] **OIR-ORG-06** - Manpower: named staff with > 3 years in high-energy physics and electric propulsion; MTech / PhD profiles (Part IV(B) 4; Part IV(C) 6). Clauses: RFP-P21-03.
- [ ] **OIR-FAC-01** - UHV propulsion test facility: owner / location / pumping speed / base pressure / in-house, consortium or sub-contract status, with documentary proof (RFP-P27-01 i; Part IV(C) 5). Clauses: RFP-P21-03, RFP-P27-01.
- [ ] **OIR-FAC-02** - Thrust measurement system: type, range, resolution (micro-newton capability), calibration record, in-house / consortium / sub-contract (RFP-P27-01 ii, RFP-P30-01). Clauses: RFP-P21-03, RFP-P27-01, RFP-P30-01.
- [ ] **OIR-FAC-03** - Facility to simulate the VLEO air mixture and a rarefied-gas source with prescribed mg/s and velocity for intake-erosion tests (RFP-P17-02 4, RFP-P19-06 b). Clauses: RFP-P17-02, RFP-P19-06.
- [ ] **OIR-FAC-04** - Ground atomic-oxygen exposure facility and target fluence (AOL-OQ-05; RFP-P19-06 a). Clauses: RFP-P19-06.
- [ ] **OIR-COL-01** - Academic / research partner for AO material compatibility, its work share and the LoI / MoU (RFP-P27-02). Clauses: RFP-P21-03, RFP-P27-02.
- [ ] **OIR-TEC-01** - Upstream-closure citation decision (post-freeze caveat): cite the bbc480c F7/F8 numbers as five-state screening results only, or re-freeze at 32c9e63 (bid_technical_baseline.json post_freeze_commits_known_at_freeze.owner_attention). Clauses: RFP-P17-03, RFP-P18-05.
- [ ] **OIR-TEC-02** - Electronics / sensor redundancy concept for single-point-failure tolerance and its mass / power allocation (RFP-P18-02, RFP-P18-09). Clauses: RFP-P18-02, RFP-P18-09.
- [ ] **OIR-TEC-03** - Mission inputs not in the RFP: inclination / LTAN, AOCS pointing envelope, host-spacecraft drag ICD (A9.21 EXTERNAL_INPUTS) - or a statement in the bid that these are requested from DRDO at PDR. Clauses: RFP-P18-04.
- [ ] **OIR-TEC-04** - Spacecraft bus input voltage / power-quality assumptions for the PPU front end (A902-12 TBD). Clauses: RFP-P18-01.
- [ ] **OIR-TEC-05** - Mass-closure position for the bid: how the < 40 kg (wet) exceedance of the MEV planning roll-up is presented and which redesign levers are offered (MQ-10); confirm the wet reading (DISC-02). Clauses: RFP-P18-11.
- [ ] **OIR-TEC-06** - MIL-1553B implementation choice (RT core / transceiver source, bus A/B redundancy) for the offer. Clauses: RFP-P18-12.
- [ ] **OIR-TEC-07** - Reading of the Milestone-2 deliverable 'approved GNC design document and codes' for a propulsion PSE (seek DRDO clarification or state the reading). Clauses: RFP-P20-05.
- [ ] **OIR-TEC-08** - GNG-ICP-01 GO / NO-GO criteria (owner approved existence and placement only; criteria PENDING_OWNER_ACCEPTANCE). Clauses: -.
- [ ] **OIR-SCH-01** - T0 assumption and confirmation that the A9.21 hardware order can be resourced inside the RFP milestone offsets (no dates beyond T0 offsets are stated by this package). Clauses: -.
- [ ] **OIR-RSK-01** - Likelihood / impact rating and risk owner for each technical risk R-01..R-13 (04_RISK_REGISTER.md); the repository holds no risk scoring. Clauses: -.
- [ ] **OIR-COM-01** - Cost / price breakdown, payment-milestone acceptance and all commercial formats (commercial bid; not in this technical package). Clauses: -.
- [ ] **OIR-DOC-01** - Mandatory formats / annexures on RFP pages 1-15 and 34-40 (NOT screened by the repository) and the DPR template pp. 22-25 / industry profile pp. 32-33 (screened from the text layer only). Clauses: -.

Open readings recorded in the evidence base that affect the bid text: AG-15 closure (owner acceptance of the RVM
re-base) and the DRDO clarifications DISC-02 (mass wet / dry), DISC-03 (indigenous content), DISC-05 ("Ignition Time"),
DISC-07 (thrust split), DISC-09 (ENTEST levels) (`docs/requirements/rfp_official/rfp_registration_v1.json`
`#/rvm_mapping`).
