"""Official RFP registration (AG-15, owner A9.13 S6.22): identity of the owner-supplied RFP PDF and a page-referenced
verbatim transcription of its requirement-bearing clauses. The PDF itself is identified by sha256; it is not committed
(public repository; owner A9.17: PDF kept in the controlled project evidence store). Transcribed from the page images on 2026-10-01; 'transcription' is the
evidence class of every text below (human-read from scanned pages, not OCR).

    python docs/requirements/rfp_official/rfp_clauses_v1.py          # write rfp_registration_v1.{json,md}
    python docs/requirements/rfp_official/rfp_clauses_v1.py --check  # outputs current; PDF hash verified if a local copy is given
    python docs/requirements/rfp_official/rfp_clauses_v1.py --check --pdf <path>

The 'rvm_mapping' section (A9.17 RFP: requirement extraction / RVM mapping) is read from the re-based RVM
(docs/requirements/rvm_a9/rvm_a9_v1.json, rfp_rebase); build the RVM first. The clause transcription is never changed by
it (the RVM pins the transcription by sha256 and refuses any change).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "docs" / "requirements" / "rvm_a9"))
import rfp_rebase as RB  # noqa: E402  (A9.22 G3 owner page review: decision pins + verbatim check)
RVM_REL = "docs/requirements/rvm_a9/rvm_a9_v1.json"   # RVM re-base output (built FIRST: build_rvm_a9.py, then this file)
OUT_JSON = HERE / "rfp_registration_v1.json"
OUT_MD = HERE / "RFP_REGISTRATION_v1.md"

DOCUMENT = {
    "title": "Online invitation of bids (two bids system) for grant-in-aid project under Technology Development Fund scheme "
             "titled AIR BREATHING SPACE BASED PROPULSION (ELECTRIC) FOR VLEO",
    "rfp_number": "DTDF/06/13516/DSP/ABEP/X/L/M/01",
    "issuer": "Government of India, Ministry of Defence, DRDO, Directorate of Technology Development Fund (DTDF)",
    "pages": 40,
    "sha256": "a128a419414b571983d46be9b27f7bf2c4279693408399e0b92148f598e5dd00",
    "size_bytes": 20118082,
    "pdf_creation_date_metadata": "2026-09-08T12:10:27Z (pdfinfo CreationDate of the supplied file)",
    "provenance": "PDF uploaded by the owner into the execution session on 2026-10-01 (file name 'RFP.pdf'); original "
                  "distribution channel per the document: DefProc portal (www.defproc.gov.in)",
    "committed_to_repository": False,
    "original_filename_as_received": "RFP.pdf",
    "retrieval": {"source": "owner upload into the execution session (original channel: DefProc portal per the document)",
                  "date": "2026-10-01"},
    "pdf_storage": "controlled project evidence store (owner A9.17 RFP: the binary is not redistributed in the public "
                   "repository; this record carries identity, hash, page count and the requirement extraction)",
    "authority": "authoritative requirement source for propellant capability and all RFP requirements (owner A9.15, A9.17)",
    "not_in_document": ["bid due / closing date (the RFP refers to the tender document on DefProc for important dates, "
                        "Part I note 5); the 05 Oct 2026 date in CLAUDE.md is therefore NOT verified by this file"],
}

# (id, page, section, verbatim text as printed)
CLAUSES = [
    ("RFP-P16-01", 16, "Part III 1(A)i", "1. Development of Air Breathing Electric Propulsion (ABEP) which will work in the VLEO environment. 2. Testing and space qualification of the Air Breathing Electric Propulsion (ABEP)."),
    ("RFP-P16-02", 16, "Part III 1(A)ii Figure 1", "Logical Block Diagram: Intake -> Filter -> Compressor -> Gas Chamber -> Valve -> Thruster (Ionization zone | Acceleration zone) -> Thrust; Xenon Gas -> Valve -> Thruster."),
    ("RFP-P17-01", 17, "Part III Figure 2", "Processing block diagram of EM QM Testing of ABEP System: EM Air Intake System, Compressor storage; EM Power processing unit (PPU); EM Thruster -> EM Integration -> EM Integration Test -> Qualification Model Intake and compressor; Qualification Model Power Electronics; Qualification Model Thruster -> QM Integration Test."),
    ("RFP-P17-02", 17, "Part III 1(A)iii", "List of critical technologies required for the solution: 1. Electric propulsion thruster to Ionize and accelerate N2 and nascent O. 2. Material compatibility to with stand VLEO atmospheric nascent oxygen. 3. Air Intake system design and compressor technology. 4. Test facility to simulate air mixture conditions in VLEO environment."),
    ("RFP-P17-03", 17, "Part III 1(A)iv row 1 Air Intake", "Air intake system captures residual atmospheric particles (mainly atomic oxygen and nitrogen) at VLEO altitudes (< 250 km). Most challenging in total system."),
    ("RFP-P17-04", 17, "Part III 1(A)iv row 2 Compressor and gas Reservoir", "Increases the density of the collected atmospheric gases to a usable level of ionization"),
    ("RFP-P17-05", 17, "Part III 1(A)iv row 3 Thruster", "Capability to ionize N2, atomic oxygen in same thruster and It should have capability to use Xe as propellant, an extra input system to take care any problems on board unforeseen problems."),
    ("RFP-P18-01", 18, "Part III 1(A)iv row 4 Power System Electronics", "Power system electronics shall capable taking power from satellite bus and provide the total ABEP system required voltages and Current requirements."),
    ("RFP-P18-02", 18, "Part III 1(A)iv row 5 Reliability", "The system should have redundancy in Electronics level and sensor level if any."),
    ("RFP-P18-03", 18, "Part III 1(A)iv row 6 Any other Points", "a) Indigenous Content: >60% to mitigate International Traffic in Arm Regulations (ITAR)/ export control restrictions b) Development partner shall be called for a presentation as part of Technical Evaluation to present the technical proposal in detail (design, realization, testing and schedules) to a technical evaluation committee. c) Consortium of different industries (if proposed) should be supported by documentary proof of consortium agreement."),
    ("RFP-P18-04", 18, "Part III 2 Functional Orbit altitude", "180 to 230 km"),
    ("RFP-P18-05", 18, "Part III 2 Air intake Specification", "Shall be decided by air density based on solar activity and altitude"),
    ("RFP-P18-06", 18, "Part III 2 Thrust Requirement", "12 mN to 25 mN (From expected drag to compensate)"),
    ("RFP-P18-07", 18, "Part III 2 Thruster Type", "Hall effect preferable"),
    ("RFP-P18-08", 18, "Part III 2 Propellant for propulsion system", "Compatible for using Ambient air (at the functional orbit altitude of 180-230km) and Xenon as propellant. Two separate propellant tanks for ambient air and xenon."),
    ("RFP-P18-09", 18, "Part III 2 Redundancy", "Must cater to single point failure for electronics."),
    ("RFP-P18-10", 18, "Part III 2 Power", "<1500W"),
    ("RFP-P18-11", 18, "Part III 2 Mass", "< 40kg"),
    ("RFP-P18-12", 18, "Part III 2 Electrical Interface", "MIL-1553B with satellite onboard computer for configuration and for high rate data-logging with data recorder. Discrete interface for thruster operation. Necessary hardware drivers to be part of propulsion system."),
    ("RFP-P19-01", 19, "Part III 2 Life Cycle and Maintainability", "Mission life: 3 years (Approx 26000 hrs). Ignition Time: More than 15000 hrs"),
    ("RFP-P19-02", 19, "Part III 2 Material Specifications", "All materials and processes used in the product realization should be space qualified for Qualified model."),
    ("RFP-P19-03", 19, "Part III 2 Subsystems", "The overall system shall consist of the following sub-systems a. Air Intake and Compressor storage b. Power Supply Electronics c. Thruster"),
    ("RFP-P19-04", 19, "Part III 2 Environment", "The product should qualify the launch vibrations and shock. The product shall qualify atomic oxygen erosion, radiation, thermal and ThermoVac specifications for a VLEO orbit with a mission life of 3 years. Atomic oxygen erosion environment, All parts in Intake, Compressor and Thruster design shall take care of nascent atomic oxygen erosion for lifetime. ENTEST Specifications (The specifications will be provided at the time PDR): The system has to qualify for VLEO environment for a lifetime 03 yrs and for launch loads of PSLV/ SSLV or any other Launch Vehicle decided by DRDO at the time of PDR."),
    ("RFP-P19-05", 19, "Part III 3 Indigenous Content", "The firm should provide a detailed plan for achieving the minimum 75% IC in the project deliverables. Minimum Indigenization Desired: 1. Space Qualified Thruster >80%; 2. Intake system >80%; 3. Compressor and Storage >60%; 4. Power Supply Electronics >70%."),
    ("RFP-P19-06", 19, "Part III 4.1 Testing", "The system performance should be demonstrated by means of following tests: a) Coating materials and surface tests with Atomic Oxygen beam exposure, Erosion yield measurement. b) Creation of rarefied gas with prescribed mg/sec and velocity to test Intake system Erosion process. c) Minimum functional performance testing for EM and QM in integration mode for force calculation, with variable air intake (mg/sec), Isp, Efficiency of the total system etc. d) The test plan document for different tests shall be reviewed/ finalized through an expert committee and approved by PMMG/SPMMG."),
    ("RFP-P20-01", 20, "Part III 4.2-4.3", "4.2 Acceptance Criteria: Deliverable of the project should be matched with parameters given below in Para 2. 4.3 Certification: The Company shall be ISO certified. i. Acceptance/Qualification based on ATP Document. Preparation of ATP document will be carried out based on parameters listed in Para 2 above and will be finalized after DDR/CDR. ii. Testing as per Applicable Standards (MIL / ASTM/ BIS etc) / ESS Specification"),
    ("RFP-P20-02", 20, "Part III 5", "Trial and Performance Evaluation on system, if required: Only ground demonstration in simulated environment and space qualification testing is desired."),
    ("RFP-P20-03", 20, "Part III 6", "Exit criteria / Risk Management: Successful realization of Engineering Model of ABEP system, realization of qualified electric thruster with O and N2 as propellant at milestone 4 can be considered as a partial success of the project."),
    ("RFP-P20-04", 20, "Part III 7 Milestone 1", "Preliminary Design Review-1 (Hardware); PDC T0+09 months; 15%: completion of preliminary design (mechanical and electrical), finalization of BoM; preliminary test plan review; clearance for EM hardware realization. Deliverables: approved PDR document, design documents, CAD & EDA models; preliminary test plan and test facility document."),
    ("RFP-P20-05", 20, "Part III 7 Milestone 2", "Preliminary Design Review-2 (Algorithms and Software and Test plan); T0+12 months; 10%: electric power supply system software preliminary design, FDIR, Telemetry (MATLAB and C); review of test facility readiness. Deliverable: approved GNC design document and codes."),
    ("RFP-P20-06", 20, "Part III 7 Milestone 3 (continues p21)", "Critical Design Review; T0+20 months; 20%: realization of Engineering Models of thruster, power supply electronics; demonstration of functionality of EM hardware with Storage input not with INTAKE; clearance for qualification unit realization except Intake system. Deliverables: EM units power electronics and thruster mechanical and electrical drawings, CAD models; test results documents, test plan documents; simulation models (mechanical and electrical); test software."),
    ("RFP-P21-01", 21, "Part III 7 Milestone 4", "Engineering model Intake system; Qualification model for Power Supply Electronics and Thruster; T0+24 months; 35%: realization of Engineering model Intake System with Compressor and Storage; complete Qualification model PSE and Thruster testing with Storage Atomic reminants. Deliverables: EM Intake with compressor and Storage unit design details, CAD & EDA models, drawings etc; QM PSE, Thruster units design details, CAD & EDA models, drawings etc."),
    ("RFP-P21-02", 21, "Part III 7 Milestone 5", "QM integration and testing Delivery; T0+36 months; 20%: realization of QM Intake system and integration as total QM model ABEP; ENTEST qualification of QM units, documentation and delivery; documentation and final delivery, completion of project closure formalities."),
    ("RFP-P21-03", 21, "Part III 8", "NO Waivers shall be given for PART (IV) (B)."),
    ("RFP-P27-01", 27, "Part IV(B) 3 Infrastructure", "i. Ultra High Vacuum Test Facility for propulsion system testing (In-house/ Consortium/ Sub contract); ii. Low Thrust measurement setup (In-house/ Consortium/ Sub contract)."),
    ("RFP-P27-02", 27, "Part IV(B) 5", "Collaboration with Academia / Research Institute/Experts with specific work share related to following critical technologies of project: i. Material compatibility of Intake and thruster exposed to atmospheric nascent Oxygen (LoI from experts or MoU with institute is to be produced)."),
    ("RFP-P30-01", 30, "Part IV(C) 5 Thrust Measurement System", "Thrust Measurement System capable of measuring micro-Newton level thrust (In house: 10; Consortium: 5; Sub-contract: 0 marks)."),
]

# Page screening (A9.16 repair RFP-07): what was screened on the evaluation / qualification pages and NOT registered as
# a clause, and why. Headings are read from the page images of the registered PDF (2026-10-01); no clause text is
# invented (headings / topics only; marks shown where printed). Part IV(B) carries no waivers (RFP-P21-03), so its
# items are mapped as PROGRAMMATIC_BID_QUALIFICATION, like RFP-P27-02. (page, section, heading as printed, class, why)
PROGRAMMATIC = "PROGRAMMATIC_BID_QUALIFICATION"
EVALUATION = "BID_EVALUATION_CRITERION"
PAGE_SCREENING = [
    (26, "Part IV(B) preamble + Table B(1) notes 1-2", "Firm Essential Qualification Criteria: clause-by-clause "
     "compliance philosophy; COTS catalogue / brochure", PROGRAMMATIC, "bid-submission format, not a system requirement"),
    (26, "Part IV(B) 1", "Financial Capabilities (no negative net worth as on 31st March 2026 / last financial year; "
     "CA-certified document)", PROGRAMMATIC, "financial qualification of the bidder (no waiver, RFP-P21-03)"),
    (26, "Part IV(B) 2", "Details on in-house expertise to handle critical technologies (subsystem/module/components/ "
     "processes): i. complete indigenous realization of an electric propulsion system (space heritage data, indigenous "
     "content >50%); ii. space grade electronics and power system; iii. vacuum technology testing system for space "
     "qualification", PROGRAMMATIC, "experience / heritage qualification of the bidder (no waiver, RFP-P21-03); "
     "no system requirement on the ABEP product"),
    (27, "Part IV(B) 4", "Availability of Experienced Manpower (at least 1 experienced person, > 3 years: i. High "
     "energy Physics; ii. Electric Propulsion; in-house)", PROGRAMMATIC, "staffing qualification of the bidder (no "
     "waiver, RFP-P21-03)"),
    (28, "Part IV(C) preamble", "Technical Capability Evaluation: qualify Part IV(B); maximum 100 marks, minimum 60 to "
     "qualify (Table B2 / Table-E Technical Evaluation Criteria)", EVALUATION, "evaluation procedure, not a system "
     "requirement"),
    (28, "Part IV(C) 1", "Expertise in Design and Development (based on completed projects only) (21 Marks): high "
     "power electronics, space structure and thermal design, high vacuum system", EVALUATION, "bidder track-record "
     "scoring"),
    (28, "Part IV(C) 2", "Initial Indigenous Content for Technologies (14 Marks): electric propulsion IC content and "
     "space grade electronics IC content (>75%: 7 marks; 50-75%: 4 marks)", EVALUATION, "bidder IC scoring; the "
     "project IC requirement is RFP-P19-05 / RFP-P18-03 (RVM-18)"),
    (29, "Part IV(C) 3", "Present TRL available with industry (15 Marks; indigenous electric propulsion system TRL "
     "bands)", EVALUATION, "bidder maturity scoring"),
    (29, "Part IV(C) 4", "Clarity and Quality of Submitted Proposal (25 Marks): a) idea / concept; b) sub-system "
     "details; c) qualification & test plan; d) modeling / simulation / analysis results; e) bench top prototype "
     "demonstration with test results", EVALUATION, "proposal-quality scoring (DPR content), not a system requirement"),
    (30, "Part IV(C) 5 Ultra High Vacuum Chamber", "Development and Test Infrastructure (20 Marks): vacuum chamber for "
     "testing electric propulsion system (in house 10 / consortium 5 / sub-contract 0)", EVALUATION, "scoring of the "
     "infrastructure already required by RFP-P27-01 i (RVM-26 related); the thrust-measurement sub-item is RFP-P30-01"),
    (30, "Part IV(C) 6", "Manpower HR Expertise (relevant to project requirement) (5 Marks): MTech or PhD in plasma "
     "physics and any mechanical engineering discipline with electric propulsion work experience", EVALUATION,
     "staffing scoring"),
    (31, "Part IV(C) Table B3", "Performance based score matrix for DA having already awarded TDF projects (over and "
     "above the evaluation score)", EVALUATION, "past-performance scoring"),
    (22, "Detailed Project Report (pp. 22-25)", "DPR template (bidder-filled: project overview, critical technologies, "
     "approach)", PROGRAMMATIC, "bid-form template (bidder-filled); screened from the PDF text layer only, not "
     "transcribed from the page images"),
    (32, "Industry Profile (pp. 32-33)", "industry profile / firm-type document tables", PROGRAMMATIC,
     "bid-form template; screened from the PDF text layer only, not transcribed from the page images"),
]
PAGES_SCREENED_FOR_CLAUSES = list(range(16, 34))
PAGES_NOT_SCREENED = "pages 1-15 and 34-40 were not screened for requirement-bearing clauses in this record " \
                     "(bid / legal / programmatic front and back matter per the document structure, not verified page " \
                     "by page): status UNSCREENED_PENDING_OWNER_PAGE_REVIEW of the owner-held PDF; nothing is assumed " \
                     "about their content"


def owner_page_review():
    """A9.22 G3 (owner, 2026-10-03): the owner's review disposition of the pages the registration did not screen.
    Owner-stated only: nothing is transcribed from those pages and nothing is recorded about their content beyond the
    owner's statement. Fails closed on any A9.22 hash / identity / verbatim mismatch."""
    try:
        RB.load_a922()
    except RB.RebaseError as e:
        raise SystemExit(f"A9.22 owner page review: {e}")
    return {"pages": "1-15, 34-40",
            "status": "OWNER_REVIEWED_NO_ADDITIONAL_TECHNICAL_PERFORMANCE_REQUIREMENT",
            "owner_statement_verbatim": RB.A922_PAGES_VERBATIM,
            "decision": {"item": RB.A922_ITEM, "code": RB.A922_CODE, "json": RB.A922["json"],
                         "json_sha256": RB.A922["json_sha256"], "md": RB.A922["md"], "md_sha256": RB.A922["md_sha256"],
                         "pointer": RB.A922["json"] + "#/decisions/" + RB.A922_ITEM},
            "evidence_class": "owner statement (A9.22 G3); not a repository screening or transcription",
            "scope": "the owner reviewed the owner-held PDF pages 1-15 and 34-40 and states they introduce no additional "
                     "ABEP technical-performance requirement that alters the RVM technical re-base; the repository does "
                     "not transcribe, screen or characterise those pages (no clause registered from them, nothing "
                     "assumed about their other content)",
            "supersedes_status": "UNSCREENED_PENDING_OWNER_PAGE_REVIEW (pages_not_screened_as_registered)"}


def page_coverage():
    """Coverage record (RFP-07): registered clause pages + screened-out items; fails closed on an unknown class or a
    Part IV(B) item that is neither registered nor screened."""
    reg_sections = {c[2] for c in CLAUSES}
    out = []
    for page, sec, heading, cls, why in PAGE_SCREENING:
        if cls not in (PROGRAMMATIC, EVALUATION):
            raise SystemExit(f"page screening: unknown class {cls}")
        rec = {"page": page, "section": sec, "heading_as_read": heading, "class": cls, "why_not_registered": why}
        if sec.startswith("Part IV(B)"):
            rec["no_waiver"] = "RFP-P21-03 'NO Waivers shall be given for PART (IV) (B)'"
        out.append(rec)
    for item in ("1", "2", "3", "4", "5"):
        sec = f"Part IV(B) {item}"
        registered = any(r.startswith(sec) for r in reg_sections)
        screened = any(r["section"] == sec for r in out)
        if registered == screened:
            raise SystemExit(f"{sec}: must be either registered or screened out (exactly one)")
    return {"pages_with_registered_clauses": sorted({c[1] for c in CLAUSES}),
            "pages_screened_for_clauses": PAGES_SCREENED_FOR_CLAUSES,
            "pages_not_screened_as_registered": PAGES_NOT_SCREENED,
            "owner_page_review": owner_page_review(),
            "screened_out": out,
            "rule": "every Part IV(B) item (no waivers, RFP-P21-03) is either a registered clause (3: RFP-P27-01, "
                    "5: RFP-P27-02) or screened out here as PROGRAMMATIC_BID_QUALIFICATION; Part IV(C) criteria other "
                    "than 5 (thrust measurement, RFP-P30-01) are bid-evaluation scoring"}


# owner-stated 'RFP(1)' facts (A9.13-A9.15) checked against the transcription
OWNER_FACT_CHECK = [
    ("180-230 km operation", "CONFIRMED", ["RFP-P18-04"]),
    ("intake sized by air density based on solar activity and altitude", "CONFIRMED", ["RFP-P18-05"]),
    ("12-25 mN thrust for drag compensation", "CONFIRMED", ["RFP-P18-06"]),
    ("N2 and nascent/atomic O handled by the propulsion system", "CONFIRMED", ["RFP-P17-02", "RFP-P17-05"]),
    ("ambient air AND Xenon propellant capability with two separate tanks", "CONFIRMED", ["RFP-P18-08", "RFP-P16-02"]),
    ("Xe capability required in the thruster", "CONFIRMED_WITH_NOTE", ["RFP-P17-05"],
     "the RFP describes the Xe input literally as 'an extra input system to take care any problems on board unforeseen problems'; the capability is mandatory (A9.15 rule stands); the stated purpose reads as an on-board contingency input - recorded for the owner, no rule changed"),
    ("indigenous content: >60% statement and a more specific minimum 75% project target with subsystem targets", "CONFIRMED", ["RFP-P18-03", "RFP-P19-05"],
     "the subsystem table reads 'Space Qualified Thruster' >80%, 'Intake system' >80%, 'Compressor and Storage' >60%, 'Power Supply Electronics' >70%"),
    ("single-point failure for electronics + redundancy at electronics and sensor level", "CONFIRMED", ["RFP-P18-09", "RFP-P18-02"]),
    ("3-year mission, 'Ignition Time' more than 15,000 h", "CONFIRMED", ["RFP-P19-01"], "mission life printed as '3 years (Approx 26000 hrs)'"),
    ("< 1.5 kW, < 40 kg", "CONFIRMED", ["RFP-P18-10", "RFP-P18-11"], "mass not stated as wet or dry in the RFP"),
    ("Hall preferred", "CONFIRMED", ["RFP-P18-07"]),
]

NEW_REQUIREMENTS_NOT_IN_RVM_CHECK = [
    ("RFP-P18-12", "MIL-1553B interface to the satellite onboard computer + discrete thruster interface + hardware drivers inside the propulsion system"),
    ("RFP-P19-04", "ENTEST: launch vibration/shock (PSLV/SSLV or DRDO-decided LV at PDR), AO erosion, radiation, thermal, ThermoVac for 3 years"),
    ("RFP-P19-06", "test approach: AO-beam coating/erosion-yield tests; rarefied-gas generation at prescribed mg/s and velocity for intake erosion; EM/QM force tests with variable intake mg/s, Isp, total-system efficiency"),
    ("RFP-P20-03", "exit criterion: qualified electric thruster with O and N2 as propellant at milestone 4"),
    ("RFP-P20-06", "milestone 3: EM thruster + PSE demonstrated with storage input (not intake)"),
    ("RFP-P30-01", "micro-newton-level thrust measurement capability (evaluation criterion)"),
]


def rvm_mapping(clause_ids):
    """RVM mapping section (A9.17 RFP: the provenance record carries the requirement extraction / RVM mapping). Read
    from the re-based RVM; the clause transcription above is never changed by it. Fails closed on any unmapped or
    unknown clause."""
    p = ROOT / RVM_REL
    if not p.exists():
        raise SystemExit(f"RVM missing: {RVM_REL} (build docs/requirements/rvm_a9/build_rvm_a9.py first)")
    rvm = json.loads(p.read_text(encoding="utf-8"))
    rb = rvm.get("rfp_rebase")
    if rvm.get("id") != "rvm_a9_v1" or not rb:
        raise SystemExit("RVM has no rfp_rebase section: rebuild the RVM")
    cov = rb["clause_coverage"]
    if [c["clause_id"] for c in cov] != list(clause_ids):
        raise SystemExit("RVM clause coverage does not match the registered clauses")
    for c in cov:
        if not c["rvm_rows"] and "not_system_requirement" not in c:
            raise SystemExit(f"clause {c['clause_id']} is not mapped to an RVM row")
    rows = {r["id"]: r for r in rvm["rows"]}
    return {
        "source": RVM_REL + " rfp_rebase (" + rb["id"] + ")",
        "regenerate": "python docs/requirements/rvm_a9/build_rvm_a9.py && python docs/requirements/rfp_official/rfp_clauses_v1.py",
        "rule": rb["rule"],
        "ag_15_status": rb["ag_15_status"],
        "requirements_snapshot": rb["requirements_snapshot"],
        "ag15_closure": RVM_REL + "#/rfp_rebase/ag15_closure",
        "clauses_sha256": rb["registration"]["clauses_sha256"],
        "clauses": [{"clause_id": c["clause_id"], "rvm_rows": c["rvm_rows"], "related_rvm_rows": c["related_rvm_rows"],
                     **({"not_system_requirement": c["not_system_requirement"]} if "not_system_requirement" in c else {}),
                     **({"partial_programmatic": c["partial_programmatic"]} if "partial_programmatic" in c else {})}
                    for c in cov],
        "rows_not_from_rfp": [{"rvm_row": r["id"], "origin": r["requirement_origin"],
                               "related_clauses": r["related_rfp_clauses"], "title": r["title"]}
                              for r in rvm["rows"] if r["requirement_origin"] != "RFP_CLAUSE"],
        "requirements_to_check_against_rvm_resolution": [
            {"clause_id": cid, "rvm_rows": next(c["rvm_rows"] for c in cov if c["clause_id"] == cid)}
            for cid, _ in NEW_REQUIREMENTS_NOT_IN_RVM_CHECK],
        "discrepancies": [{"id": d["id"], "topic": d["topic"], "rfp_clauses": d["rfp_clauses"],
                           "disposition": d["disposition"]} for d in rb["discrepancies"]],
        "n_rvm_rows": len(rows),
    }


def build():
    return {
        "schema": "rfp_registration_v1",
        "status": "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY",
        "document": DOCUMENT,
        "evidence_class": "transcription (human-read from the scanned page images of the registered PDF)",
        "clauses": [{"id": i, "page": p, "section": s, "text": t} for i, p, s, t in CLAUSES],
        "owner_rfp_fact_check": [dict(zip(("statement", "result", "clause_ids", "note"), r)) for r in OWNER_FACT_CHECK],
        "requirements_to_check_against_rvm": [{"clause_id": c, "summary": s} for c, s in NEW_REQUIREMENTS_NOT_IN_RVM_CHECK],
        "ag_15": "the official RFP is registered with immutable identity (sha256); the RVM is re-based against these "
                 "clauses (rvm_mapping) and AG-15 is closed by the owner (A9.22 G3; closure record "
                 + RVM_REL + " rfp_rebase.ag15_closure): RFP-derived requirements snapshot FROZEN, basis only, not "
                 "compliance",
        "rvm_mapping": rvm_mapping([c[0] for c in CLAUSES]),
        "page_coverage": page_coverage(),
    }


def render_md(d):
    doc = d["document"]
    L = ["# Official RFP registration (v1)", "",
         f"- RFP {doc['rfp_number']}: {doc['title']}",
         f"- Issuer: {doc['issuer']}; {doc['pages']} pages; sha256 `{doc['sha256']}` ({doc['size_bytes']} bytes)",
         f"- Provenance: {doc['provenance']}",
         f"- Status: {d['status']} (the PDF is identified by hash, not committed)",
         f"- Not in the document: {'; '.join(doc['not_in_document'])}", "",
         "## Requirement-bearing clauses (verbatim transcription)", "", "| ID | Page | Section | Text |", "|---|---|---|---|"]
    L += [f"| {c['id']} | {c['page']} | {c['section']} | {c['text']} |" for c in d["clauses"]]
    L += ["", "## Owner-stated RFP facts checked", "", "| Statement | Result | Clauses | Note |", "|---|---|---|---|"]
    L += [f"| {r['statement']} | {r['result']} | {', '.join(r['clause_ids'])} | {r.get('note') or ''} |"
          for r in d["owner_rfp_fact_check"]]
    L += ["", "## Requirements to check against the RVM", ""]
    L += [f"- {r['clause_id']}: {r['summary']}" for r in d["requirements_to_check_against_rvm"]]
    L += ["", d["ag_15"], ""]
    m = d["rvm_mapping"]
    L += ["## RVM mapping (re-base, AG-15)", "", f"Source: `{m['source']}`; regenerate: `{m['regenerate']}`.", "",
          f"Rule: {m['rule']}.", "", f"AG-15: {m['ag_15_status']}.", "",
          "| Clause | RVM rows (derived) | Related rows | Note |", "|---|---|---|---|"]
    for c in m["clauses"]:
        note = "; ".join(x for x in (c.get("not_system_requirement", {}).get("class", ""),
                                     c.get("partial_programmatic", "")) if x)
        L.append(f"| {c['clause_id']} | {', '.join(c['rvm_rows']) or '-'} | {', '.join(c['related_rvm_rows']) or '-'} | "
                 f"{note} |")
    L += ["", "Rows not derived from an RFP clause:", ""]
    L += [f"- {r['rvm_row']} {r['origin']}: {r['title']}" for r in m["rows_not_from_rfp"]]
    L += ["", "Requirements flagged for the RVM check, resolved:", ""]
    L += [f"- {r['clause_id']}: {', '.join(r['rvm_rows'])}" for r in m["requirements_to_check_against_rvm_resolution"]]
    L += ["", "Discrepancies (recorded for the owner / DRDO; see the RVM):", ""]
    L += [f"- {x['id']} {x['topic']} ({', '.join(x['rfp_clauses']) or 'no clause'}): {x['disposition']}"
          for x in m["discrepancies"]]
    pc = d["page_coverage"]
    L += ["", "## Page coverage and screened-out items (A9.16 repair RFP-07)", "",
          f"Pages with registered clauses: {', '.join(str(p) for p in pc['pages_with_registered_clauses'])}. Pages "
          f"screened for clauses: {pc['pages_screened_for_clauses'][0]}-{pc['pages_screened_for_clauses'][-1]}. "
          f"As registered: {pc['pages_not_screened_as_registered']}.", "",
          f"Owner page review (A9.22 G3, `{pc['owner_page_review']['decision']['json']}` sha256 "
          f"`{pc['owner_page_review']['decision']['json_sha256']}`): pages {pc['owner_page_review']['pages']} "
          f"{pc['owner_page_review']['status']} - owner statement, verbatim: \"{pc['owner_page_review']['owner_statement_verbatim']}\" "
          f"({pc['owner_page_review']['scope']}).", "", f"Rule: {pc['rule']}.", "",
          "| Page | Section | Heading (as read) | Class | Why not registered |", "|---|---|---|---|---|"]
    L += [f"| {r['page']} | {r['section']} | {r['heading_as_read']} | {r['class']} | {r['why_not_registered']}"
          + (f" ({r['no_waiver']})" if r.get("no_waiver") else "") + " |" for r in pc["screened_out"]]
    L += [""]
    return "\n".join(L)


def main():
    d = build()
    js = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    md = render_md(d)
    if "--check" in sys.argv:
        stale = [p.name for p, t in ((OUT_JSON, js), (OUT_MD, md)) if not p.exists() or p.read_text(encoding="utf-8") != t]
        if stale:
            raise SystemExit(f"stale: {stale}")
        if "--pdf" in sys.argv:
            pdf = Path(sys.argv[sys.argv.index("--pdf") + 1])
            h = hashlib.sha256(pdf.read_bytes()).hexdigest()
            if h != DOCUMENT["sha256"]:
                raise SystemExit(f"PDF hash mismatch: {h}")
            print("PDF hash verified")
        print("rfp registration v1: current")
        return
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print("written")


if __name__ == "__main__":
    main()
