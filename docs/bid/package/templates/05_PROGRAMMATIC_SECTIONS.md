# 05 - Programmatic sections (skeletons)

**Status: DRAFT_FOR_OWNER_REVIEW - SKELETON.** The repository is an engineering evidence base. It holds no
organisational, commercial, staffing, facility-ownership, partner or certification facts about Vyovrinda Aerospace. Every
field below that needs such a fact is marked `OWNER_INPUT_REQUIRED` with its checklist id (README.md). Nothing here is
invented: no IC percentage, facility, partner, ISO status, price or staff name.

Technical cross-references point to files at the technical source commit `{{SRC}}` (`{{SRC_FULL}}`, pinned by
`docs/bid/bid_technical_baseline_v2.json`).

## 1. Indigenous content plan (RFP-P19-05, RFP-P18-03 a; Part IV(C) 2)

RFP targets (registered clause text): project >= 75 % IC in the deliverables; space-qualified thruster > 80 %; intake
system > 80 %; compressor and storage > 60 %; power supply electronics > 70 %. RFP-P18-03 a) also states > 60 % "to
mitigate ITAR / export control restrictions" (DISC-03 recorded for DRDO clarification). Repository state: no part is
selected; RFQ v3 (`docs/procurement/rfq_a9_v3/rfq_a9_v3.json`) is COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY and its RFQ3-GAS
successor (`docs/procurement/rfq_a9_v3_gas_rev1/rfq3_gas_rev1.json`) is quotation-only; RVM-18
NOT_EVALUATED.

| subsystem (RFP-P19-05) | BoM lines (mass record {{MASS_ID}}) | RFP minimum | planned IC % | basis of computation | make / buy, origin |
|---|---|---|---|---|---|
| Space-qualified thruster | AL-04 H-1 head + magnet; AL-05 ICP neutralizer | > 80 % | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-02) |
| Intake system | AL-01 intake / filter / duct | > 80 % | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-02) |
| Compressor and storage | AL-02 compressor + drive; AL-03 plenum / feed; AL-08 Xe storage / flow | > 60 % | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-02) |
| Power supply electronics | AL-06 RF generator / matching; AL-07 Hall PPU; AL-09 controls / valve drivers / sensors | > 70 % | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-02) |
| Project total | all | >= 75 % | OWNER_INPUT_REQUIRED (OIR-IC-01) | OWNER_INPUT_REQUIRED (OIR-IC-01) | - |

Indigenization roadmap for imported items and ITAR / export-control exposure: OWNER_INPUT_REQUIRED (OIR-IC-03).

## 2. Facilities and infrastructure (RFP-P27-01, RFP-P30-01; Part IV(C) 5)

| facility | RFP clause | what the repository specifies (requirements only) | ownership: in-house / consortium / sub-contract | documentary proof |
|---|---|---|---|---|
| Ultra-high-vacuum propulsion test facility | RFP-P27-01 i; Part IV(C) 5 | gauge / feed-state measurement requirements (`docs/experiments/hardware/hardware_requirements_v1.json`, `docs/experiments/instrumentation/instrumentation_definition_v1.json`) | OWNER_INPUT_REQUIRED (OIR-FAC-01) | OWNER_INPUT_REQUIRED (OIR-FAC-01) |
| Low-thrust measurement setup | RFP-P27-01 ii | thrust stand INS-01 principle (torsional or inverted pendulum, null-type preferred, in-situ calibration under vacuum) | OWNER_INPUT_REQUIRED (OIR-FAC-02) | OWNER_INPUT_REQUIRED (OIR-FAC-02) |
| Micro-newton thrust measurement system | RFP-P30-01 | none: the planned mN-level stand is not micro-newton evidence (RVM-26, DISC-10) | OWNER_INPUT_REQUIRED (OIR-FAC-02) | OWNER_INPUT_REQUIRED (OIR-FAC-02) |
| VLEO air-mixture simulation and rarefied-gas source (mg/s, velocity) | RFP-P17-02 item 4; RFP-P19-06 b | none in the repository (RVM-22) | OWNER_INPUT_REQUIRED (OIR-FAC-03) | OWNER_INPUT_REQUIRED (OIR-FAC-03) |
| Ground atomic-oxygen exposure | RFP-P19-06 a | AO register v5 requirements (fluence witness, coupons) | OWNER_INPUT_REQUIRED (OIR-FAC-04) | OWNER_INPUT_REQUIRED (OIR-FAC-04) |
| ENTEST (vibration / shock, thermal-vacuum, radiation) | RFP-P19-04 | levels issued by DRDO at PDR (DISC-09) | OWNER_INPUT_REQUIRED (OIR-FAC-01) | OWNER_INPUT_REQUIRED |

## 3. Team, manpower and collaboration (RFP-P27-02; Part IV(B) 4, Part IV(C) 6; RFP-P18-03 b, c)

- Project organisation and roles: OWNER_INPUT_REQUIRED (OIR-ORG-06).
- Experienced manpower (> 3 years: high-energy physics; electric propulsion; in-house) with CVs: OWNER_INPUT_REQUIRED
  (OIR-ORG-06).
- Academic / research partner for AO material compatibility of intake and thruster, specific work share, LoI or MoU
  (RFP-P27-02): OWNER_INPUT_REQUIRED (OIR-COL-01). Candidate work share that the repository already defines (for the
  owner to assign): AO coupon exposure and erosion-yield measurement (AOL-EX-01 / -02), post-test SEM / EDS / XPS, P4
  anode-candidate oxidation data (`docs/experiments/lifetime_ao/ao_lifetime_register_v5.json`,
  `docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json`).
- Consortium (if proposed) with signed agreement: OWNER_INPUT_REQUIRED (OIR-ORG-05).
- Technical-evaluation presentation team: OWNER_INPUT_REQUIRED (OIR-ORG-04).

## 4. Quality, certification and acceptance (RFP-P20-01)

- ISO certification (standard, scope, certificate number, validity): OWNER_INPUT_REQUIRED (OIR-ORG-01).
- ATP: prepared from the Para 2 parameters, finalized after DDR / CDR (RFP-P20-01 i). The RVM
  (`docs/requirements/rvm_a9/rvm_a9_v1.json`) is the traceability source; it is not an ATP.
- Applicable standards (MIL / ASTM / BIS / ESS): to be listed in the ATP; selection OWNER_INPUT_REQUIRED.
- Configuration and evidence control already used by the engineering base: frozen datasets with hashes, pre-registered
  criteria, fail-closed gate statuses, owner decisions recorded verbatim and immutable (`docs/EVIDENCE.md`,
  `docs/decisions/`).

## 5. Cost and commercial

Not part of this technical package. Price breakdown, acceptance of the payment percentages (15 / 10 / 20 / 35 / 20 %)
and all commercial formats: OWNER_INPUT_REQUIRED (OIR-COM-01).

## 6. Company credentials and qualification (Part IV(B) 1, 2; Part IV(C) 1, 3)

| item | RFP reference | content |
|---|---|---|
| Financial capability (no negative net worth, CA-certified) | Part IV(B) 1 | OWNER_INPUT_REQUIRED (OIR-ORG-02) |
| In-house expertise: indigenous EP system realization (space heritage, IC > 50 %), space-grade electronics and power, vacuum test systems | Part IV(B) 2 | OWNER_INPUT_REQUIRED (OIR-ORG-03) |
| Completed projects: high-power electronics, space structure / thermal, high vacuum | Part IV(C) 1 | OWNER_INPUT_REQUIRED (OIR-ORG-03) |
| Present TRL of indigenous EP system | Part IV(C) 3 | OWNER_INPUT_REQUIRED (OIR-ORG-03). Note: the repository holds no hardware test of the proposed system; a TRL claim must rest on the owner's own heritage evidence |
| Bench-top prototype demonstration with test results | Part IV(C) 4 e | OWNER_INPUT_REQUIRED: no Vyovrinda bench test result exists in the repository |
| DPR template (pp. 22-25) and industry profile (pp. 32-33) | screened from the PDF text layer only | OWNER_INPUT_REQUIRED (OIR-DOC-01) |
