"""RVM re-base on the official RFP (AG-15; owner A9.13 S6.22 F9-OQ-03, A9.17 RFP, A9.15; A9.14 S8.5 / S9.11-S9.13).

The official RFP (DTDF/06/13516/DSP/ABEP/X/L/M/01) is registered in docs/requirements/rfp_official/rfp_registration_v1.json:
document identity + PDF sha256 + a page-referenced verbatim transcription of its requirement-bearing clauses (RFP-Pnn-mm).
This module maps EVERY registered clause to RVM rows and labels every RVM row with its requirement origin:

  RFP_CLAUSE                  the row derives from the cited clause id(s) (verbatim text copied from the registration,
                              a value token of each cited clause is checked; a missing token raises)
  DERIVED_PROJECT_REQUIREMENT the project needs it but no RFP clause states it (e.g. atmospheric off-state ignition,
                              A9.14 S9.12 OD14); related clauses are context only
  OWNER_ALLOCATION            an owner-given internal design allocation, not an RFP gate (e.g. 1.35 kW, 34 / 36 kg,
                              50 W mount heat A9.12 S5.4)

Nothing here sets a status: statuses still come from rvm_rules.assign_status (no PASS without a determining verified
measurement; A9.13 S6.22). requirement_frozen stays false on every RFP row: the transcription is registered, but AG-15 is
closed only by the owner and the interpretation readings below are recorded for DRDO clarification.

stdlib only; deterministic; fail closed (registration identity, PDF hash, clause-transcription hash, clause coverage).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

REG_REL = "docs/requirements/rfp_official/rfp_registration_v1.json"
REG_BUILDER = "docs/requirements/rfp_official/rfp_clauses_v1.py"
RFP_NUMBER = "DTDF/06/13516/DSP/ABEP/X/L/M/01"
PDF_SHA256 = "a128a419414b571983d46be9b27f7bf2c4279693408399e0b92148f598e5dd00"
# sha256 of json.dumps(clauses, ensure_ascii=False, sort_keys=True, separators=(",", ":")): the transcription is
# immutable; the registration record itself is not pinned (it carries the RVM mapping section built from this RVM)
CLAUSES_SHA256 = "fd51a951a1d06ea8bebd39416147686aedb1f596170fb81b6583f4564148a8aa"
REBASE_DATE = "2026-10-01"

ORIGINS = ("RFP_CLAUSE", "DERIVED_PROJECT_REQUIREMENT", "OWNER_ALLOCATION")

# owner decision A9.17 (not in a9_16_lib): path + json sha256 + md sha256 (verbatim governs)
A917 = {"json": "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json",
        "json_sha256": "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad",
        "md": "docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md",
        "md_sha256": "540212c0c8862528e549555244f0fd39f8f9c9272f84dfb450bfef9dc54eba13"}


class RebaseError(RuntimeError):
    pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clauses_sha256(clauses) -> str:
    return hashlib.sha256(json.dumps(clauses, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def load_a917() -> dict:
    for k in ("json", "md"):
        got = _sha(ROOT / A917[k])
        if got != A917[k + "_sha256"]:
            raise RebaseError(f"A9.17 decision changed: {A917[k]} sha256 {got}")
    d = json.loads((ROOT / A917["json"]).read_text(encoding="utf-8"))
    if d["decisions"]["RFP"]["answer"] != "RFP_HASH_PROVENANCE_IN_PUBLIC_REPO_PDF_CONTROLLED_EXTERNALLY":
        raise RebaseError("A9.17 RFP decision code changed")
    return d


def cite_a917() -> str:
    return f"A9.17 RFP ({A917['json']} sha256 {A917['json_sha256']})"


def load_registration(reg_path: Path | None = None) -> dict:
    p = reg_path or (ROOT / REG_REL)
    if not p.exists():
        raise RebaseError(f"RFP registration missing: {REG_REL}")
    d = json.loads(p.read_text(encoding="utf-8"))
    if d.get("schema") != "rfp_registration_v1":
        raise RebaseError("RFP registration schema changed")
    doc = d["document"]
    if doc["rfp_number"] != RFP_NUMBER or doc["sha256"] != PDF_SHA256:
        raise RebaseError("RFP registration identity / PDF sha256 changed")
    got = clauses_sha256(d["clauses"])
    if got != CLAUSES_SHA256:
        raise RebaseError(f"RFP clause transcription changed (sha256 {got}): the transcription is immutable; a new "
                          f"registration version is required")
    return d


def clause_record(reg: dict, cid: str, token: str | None = None) -> dict:
    c = next((x for x in reg["clauses"] if x["id"] == cid), None)
    if c is None:
        raise RebaseError(f"RFP clause {cid} not registered")
    if token is not None and token not in c["text"]:
        raise RebaseError(f"token {token!r} not in RFP clause {cid}")
    return {"kind": "rfp_official_clause", "path": REG_REL, "clause_id": cid, "page": c["page"],
            "section": c["section"], "verbatim": c["text"], "rfp_number": RFP_NUMBER, "pdf_sha256": PDF_SHA256,
            "evidence_class": reg["evidence_class"]}


# ------------------------------------------------------------------------------------------------ row mapping
# row id -> origin, determining clauses [(id, token)], related clauses (context), optional overrides
_REG = "rfp_registered"
REBASE = {
    "RVM-01": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-04", "180 to 230 km"),
                                                 ("RFP-P18-05", "solar activity and altitude")],
                   related=["RFP-P17-03"], category=_REG),
    "RVM-02": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-06", "12 mN to 25 mN")], category=_REG,
                   note="the RFP prints '12 mN to 25 mN (From expected drag to compensate)'; the >= 12 mN sustained / "
                        "25 mN capability split is the owner's engineering reading (row 4), recorded as reading R-THR"),
    "RVM-03": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-06", "25 mN"), ("RFP-P18-10", "<1500W")], category=_REG),
    "RVM-04": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-10", "<1500W"), ("RFP-P18-01", "satellite bus")],
                   category=_REG,
                   note="the RFP prints '<1500W' with no averaging window or transient clause; the 1 ms window is the "
                        "owner's engineering definition (A9.1 OQ-A902-01)"),
    "RVM-05": dict(origin="OWNER_ALLOCATION", related=["RFP-P18-10"]),
    "RVM-06": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-11", "< 40kg")], category=_REG,
                   note="the RFP prints '< 40kg' without stating wet or dry (discrepancy DISC-02); the wet reading "
                        "incl. Xe + tank is the owner's conservative reading (row 5)"),
    "RVM-07": dict(origin="OWNER_ALLOCATION", related=["RFP-P18-11"]),
    "RVM-08": dict(origin="RFP_CLAUSE",
                   clauses=[("RFP-P18-08", "Ambient air"), ("RFP-P16-02", "Intake -> Filter -> Compressor"),
                            ("RFP-P17-03", "Air intake system captures"), ("RFP-P17-04", "density"),
                            ("RFP-P19-03", "Air Intake and Compressor storage")],
                   related=["RFP-P17-02", "RFP-P16-01"], category=_REG),
    "RVM-09": dict(origin="RFP_CLAUSE", clauses=[("RFP-P17-05", "ionize N2, atomic oxygen in same thruster"),
                                                 ("RFP-P17-02", "Ionize and accelerate N2 and nascent O")],
                   related=["RFP-P20-03"], category=_REG,
                   title="Ionise N2 and nascent (atomic) O in the same thruster (RFP-P17-05, RFP-P17-02)",
                   text="The thruster ionizes N2 and atomic oxygen in the same thruster (RFP-P17-05; critical "
                        "technology 1 'Electric propulsion thruster to Ionize and accelerate N2 and nascent O', "
                        "RFP-P17-02). No numeric threshold is printed. N2 + O2 surrogate data are NO_ATOMIC_O and never "
                        "atomic-O evidence; compliance gate CG-N2-AO (A9.14 OD12)."),
    "RVM-10": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-08", "Two separate propellant tanks for ambient air and "
                                                                "xenon"),
                                                 ("RFP-P17-05", "capability to use Xe as propellant"),
                                                 ("RFP-P16-02", "Xenon Gas -> Valve -> Thruster")], category=_REG,
                   note="the RFP describes the Xe input as 'an extra input system to take care any problems on board "
                        "unforeseen problems'; the capability is mandatory (A9.15), the stated purpose is recorded "
                        "(DISC-06), no rule changed"),
    "RVM-11": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-07", "Hall effect preferable")], category=_REG),
    "RVM-12": dict(origin="RFP_CLAUSE", clauses=[("RFP-P19-01", "Ignition Time: More than 15000 hrs")], category=_REG,
                   title="'Ignition Time: More than 15000 hrs' (RFP-P19-01, literal); design basis >= 15,000 h "
                         "cumulative energized operation",
                   text="The RFP prints 'Ignition Time: More than 15000 hrs' (RFP-P19-01; literal wording preserved). "
                        "Design basis: >= 15,000 h cumulative energized operating life (conservative reading pending "
                        "clarification, A9.14 S8.5 OQ-VI-04); restart / cycle count from the frozen mission-mode "
                        "profile (TBD, not invented). C1 carries the 15,000 h cathode basis; the ICP neutralizer "
                        "carries its own >= 15,000 h life basis.",
                   decisions=["OQ-VI-04"]),
    "RVM-13": dict(origin="RFP_CLAUSE", clauses=[("RFP-P19-01", "Mission life: 3 years (Approx 26000 hrs)")],
                   category=_REG,
                   note="the RFP prints '3 years (Approx 26000 hrs)'; 26,280 h (= 3 x 8,760 h) is the owner's "
                        "conservative engineering basis (row 3), recorded as DISC-04"),
    "RVM-14": dict(origin="DERIVED_PROJECT_REQUIREMENT", related=["RFP-P18-12"], category="derived_project",
                   decisions=["OD14"],
                   basis="DERIVED_PROJECT_REQUIREMENT (A9.14 S9.12 OD14: atmospheric off-state ignition / restart is "
                         "not RFP_EXPLICIT) + owner rows 24, 93, 108, 112",
                   note="no RFP ignition / restart clause is registered; the 'Discrete interface for thruster "
                        "operation' (RFP-P18-12) is context only, not an ignition requirement (A9.14 S9.12: do not "
                        "claim DRDO specified an ignition / restart clause)"),
    "RVM-15": dict(origin="DERIVED_PROJECT_REQUIREMENT", related=["RFP-P17-05", "RFP-P18-06"]),
    "RVM-16": dict(origin="RFP_CLAUSE",
                   clauses=[("RFP-P17-02", "Material compatibility"), ("RFP-P19-04", "nascent atomic oxygen erosion"),
                            ("RFP-P19-06", "Atomic Oxygen beam exposure"), ("RFP-P19-02", "space qualified")],
                   related=["RFP-P27-02"], category=_REG,
                   title="Atomic-oxygen / material compatibility (AO-beam test; anode, collector, keeper, gas path)",
                   text="All parts in intake, compressor and thruster take care of nascent atomic-oxygen erosion for "
                        "the lifetime (RFP-P19-04); materials compatible with VLEO nascent oxygen (RFP-P17-02); coating "
                        "and surface tests with atomic-oxygen beam exposure and erosion-yield measurement (RFP-P19-06 "
                        "a); space-qualified materials and processes for the QM (RFP-P19-02). Owner rules carried: "
                        "316L REJECTED_AS_CURRENT_BASELINE for the flight anode; final anode / collector material OPEN "
                        "until coupon evidence; no graphite flight keeper for O / AO exposure; no silver in O / "
                        "AO-wetted gas-path parts."),
    "RVM-17": dict(origin="DERIVED_PROJECT_REQUIREMENT", related=["RFP-P19-04"]),
    "RVM-18": dict(origin="RFP_CLAUSE", clauses=[("RFP-P19-05", "minimum 75% IC"), ("RFP-P18-03", ">60%")],
                   category=_REG, decisions=["OD12"],
                   title="Indigenous content: >= 75 % project, thruster > 80 %, intake > 80 %, compressor / storage "
                         "> 60 %, PSE > 70 % (RFP-P19-05; > 60 % statement RFP-P18-03 recorded)",
                   text="Minimum 75 % indigenous content in the project deliverables with subsystem minima: space "
                        "qualified thruster > 80 %, intake system > 80 %, compressor and storage > 60 %, power supply "
                        "electronics > 70 % (RFP-P19-05); the RFP also prints 'Indigenous Content: >60%' (RFP-P18-03 "
                        "a). The stricter / more specific targets are used internally; the discrepancy is recorded "
                        "for DRDO clarification (DISC-03; A9.14 S9.11 OD12). Compliance gate CG-IC."),
    "RVM-19": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-09", "single point failure for electronics"),
                                                 ("RFP-P18-02", "Electronics level and sensor level")],
                   category=_REG, decisions=["RVMQ-01", "OD12"],
                   title="Electronics: cater to single-point failure (RFP-P18-09); redundancy at electronics and "
                         "sensor level (RFP-P18-02)",
                   text="'Must cater to single point failure for electronics' (RFP-P18-09) and 'redundancy in "
                        "Electronics level and sensor level if any' (RFP-P18-02): redundant / independent critical "
                        "control, power-switching, telemetry and sensor paths where an individual failure would defeat "
                        "the mission / safe state, proven by a single-point-failure / FMEA analysis (compliance gate "
                        "CG-SPF); duplicate thrusters, ICP modules or complete mechanical chains are not required "
                        "(A9.14 S9.13 RVMQ-01); row-55 limited redundancy remains for the physical thruster / ICP "
                        "hardware, never as a waiver of electronics / sensor redundancy."),
    # ---- rows added by the re-base
    "RVM-20": dict(origin="RFP_CLAUSE", clauses=[("RFP-P18-12", "MIL-1553B"), ("RFP-P18-01", "voltages")],
                   category=_REG),
    "RVM-21": dict(origin="RFP_CLAUSE", clauses=[("RFP-P19-04", "ENTEST"), ("RFP-P19-02", "space qualified"),
                                                 ("RFP-P16-01", "space qualification")],
                   related=["RFP-P20-01", "RFP-P21-02"], category=_REG),
    "RVM-22": dict(origin="RFP_CLAUSE", clauses=[("RFP-P19-06", "rarefied gas"), ("RFP-P20-02", "ground "
                                                                                                "demonstration")],
                   related=["RFP-P17-02"], category=_REG),
    "RVM-23": dict(origin="RFP_CLAUSE", clauses=[("RFP-P20-01", "ISO certified")], category=_REG),
    "RVM-24": dict(origin="RFP_CLAUSE", clauses=[("RFP-P20-03", "O and N2 as propellant at milestone 4")],
                   related=["RFP-P21-01"], category=_REG, decisions=["OD12"]),
    "RVM-25": dict(origin="RFP_CLAUSE",
                   clauses=[("RFP-P20-04", "T0+09"), ("RFP-P20-05", "T0+12"), ("RFP-P20-06", "T0+20"),
                            ("RFP-P21-01", "T0+24"), ("RFP-P21-02", "T0+36"), ("RFP-P17-01", "EM Integration Test")],
                   related=["RFP-P16-01"], category=_REG),
    "RVM-26": dict(origin="RFP_CLAUSE", clauses=[("RFP-P30-01", "micro-Newton"), ("RFP-P27-01", "Low Thrust "
                                                                                                 "measurement"),
                                                 ("RFP-P21-03", "NO Waivers")], category=_REG),
    "RVM-27": dict(origin="OWNER_ALLOCATION", related=["RFP-P19-04"], decisions=["OQ-A907-06"]),
}

# clauses that are bid / programmatic qualification, not system requirements (still mapped, never silently dropped)
NOT_SYSTEM_REQUIREMENTS = {
    "RFP-P27-02": ("PROGRAMMATIC_BID_QUALIFICATION", "collaboration with academia / research institute on material "
                   "compatibility with nascent oxygen (LoI / MoU to be produced; Part IV(B), no waivers per RFP-P21-03); "
                   "a bid-qualification item, related technical row RVM-16"),
}
# partial programmatic content inside clauses that are otherwise mapped
PARTIAL_PROGRAMMATIC = {
    "RFP-P18-03": "items b) (technical-evaluation presentation) and c) (consortium agreement proof) are programmatic bid "
                  "items; item a) (indigenous content > 60 %) is mapped to RVM-18",
    "RFP-P20-01": "4.3 'The Company shall be ISO certified' is an organisational requirement carried by RVM-23",
}

# RVM items (a) -> origin and clauses
ITEMS = {
    "RVM-IT-01": ("RFP_CLAUSE", ["RFP-P18-04"]), "RVM-IT-02": ("RFP_CLAUSE", ["RFP-P18-04"]),
    "RVM-IT-03": ("RFP_CLAUSE", ["RFP-P18-06"]), "RVM-IT-04": ("RFP_CLAUSE", ["RFP-P18-06"]),
    "RVM-IT-05": ("DERIVED_PROJECT_REQUIREMENT", ["RFP-P18-06", "RFP-P18-10"]),
    "RVM-IT-06": ("RFP_CLAUSE", ["RFP-P18-10"]),
    "RVM-IT-07": ("DERIVED_PROJECT_REQUIREMENT", ["RFP-P18-10"]),
    "RVM-IT-08": ("OWNER_ALLOCATION", ["RFP-P18-10"]),
    "RVM-IT-09": ("RFP_CLAUSE", ["RFP-P18-11"]),
    "RVM-IT-10": ("OWNER_ALLOCATION", ["RFP-P18-11"]), "RVM-IT-11": ("OWNER_ALLOCATION", ["RFP-P18-11"]),
    "RVM-IT-12": ("OWNER_ALLOCATION", ["RFP-P18-11"]),
    "RVM-IT-13": ("RFP_CLAUSE", ["RFP-P19-01"]), "RVM-IT-14": ("RFP_CLAUSE", ["RFP-P19-01"]),
    "RVM-IT-15": ("DERIVED_PROJECT_REQUIREMENT", []), "RVM-IT-16": ("DERIVED_PROJECT_REQUIREMENT", []),
    "RVM-IT-17": ("RFP_CLAUSE", ["RFP-P19-05"]),
    "RVM-IT-18": ("DERIVED_PROJECT_REQUIREMENT", ["RFP-P19-04"]),
    "RVM-IT-19": ("DERIVED_PROJECT_REQUIREMENT", []),
    "RVM-IT-20": ("RFP_CLAUSE", ["RFP-P19-01"]),
}

COMPLIANCE_GATE_CLAUSES = {"CG-IC": ["RFP-P19-05", "RFP-P18-03"], "CG-SPF": ["RFP-P18-09", "RFP-P18-02"],
                           "CG-N2-AO": ["RFP-P17-05", "RFP-P17-02", "RFP-P20-03"]}


def discrepancies(reg: dict) -> list:
    """RFP-vs-repository discrepancies (recorded, never resolved here)."""
    nid = reg["document"]["not_in_document"]
    if not any("05 Oct 2026" in s for s in nid):
        raise RebaseError("registration no longer records the bid-date absence")
    return [
        {"id": "DISC-01", "topic": "bid due / closing date", "rfp_clauses": [],
         "rfp": "not stated in the registered RFP document (registration document.not_in_document: " + nid[0] + ")",
         "repository": "CLAUDE.md 'bid close 05 Oct 2026'",
         "disposition": "UNVERIFIED_BY_RFP_DOCUMENT - programmatic, not a system requirement (excluded candidate "
                        "PRG-BID); verify on the DefProc tender document; CLAUDE.md is not edited here",
         "owner_or_drdo_action": "owner: confirm the date from the DefProc tender document"},
        {"id": "DISC-02", "topic": "mass wet / dry", "rfp_clauses": ["RFP-P18-11"],
         "rfp": "'< 40kg' - wet or dry not stated", "repository": "RVM-06 / owner row 5: < 40 kg WET incl. Xe + tank; "
                                                                 "CLAUDE.md '< 40 kg'; A9 '< 40 kg (wet)'",
         "disposition": "the wet reading is the conservative owner reading and is retained; recorded for DRDO "
                        "clarification; requirement_frozen stays false",
         "owner_or_drdo_action": "DRDO clarification (wet or dry)"},
        {"id": "DISC-03", "topic": "indigenous content", "rfp_clauses": ["RFP-P18-03", "RFP-P19-05"],
         "rfp": "'Indigenous Content: >60%' (RFP-P18-03 a) vs 'minimum 75% IC in the project deliverables' with "
                "subsystem minima > 80 / > 80 / > 60 / > 70 % (RFP-P19-05)",
         "repository": "RVM-18 (A9.14 S9.11 OD12): stricter / more specific targets used internally",
         "disposition": "recorded for DRDO clarification (A9.14 OD12)", "owner_or_drdo_action": "DRDO clarification"},
        {"id": "DISC-04", "topic": "mission life hours", "rfp_clauses": ["RFP-P19-01"],
         "rfp": "'Mission life: 3 years (Approx 26000 hrs)'",
         "repository": "CLAUDE.md '26,000 h mission'; RVM-13 owner engineering basis >= 26,280 h (row 3)",
         "disposition": "consistent within the RFP's 'Approx'; the 26,280 h basis is conservative and retained",
         "owner_or_drdo_action": "none required"},
        {"id": "DISC-05", "topic": "'Ignition Time' label", "rfp_clauses": ["RFP-P19-01"],
         "rfp": "'Ignition Time: More than 15000 hrs'",
         "repository": "CLAUDE.md '> 15,000 h firing'; RVM-12 >= 15,000 h cumulative energized operation (A9.14 S8.5)",
         "disposition": "literal wording preserved; conservative design basis pending clarification (A9.14 S8.5)",
         "owner_or_drdo_action": "DRDO clarification of 'Ignition Time'"},
        {"id": "DISC-06", "topic": "stated purpose of the Xe input", "rfp_clauses": ["RFP-P17-05", "RFP-P18-08"],
         "rfp": "Xe 'an extra input system to take care any problems on board unforeseen problems'; two separate tanks",
         "repository": "A9.15: Xe capability mandatory, dual-propellant separate modes (RVM-10)",
         "disposition": "capability mandatory (A9.15 stands); stated purpose recorded for the owner; no rule changed",
         "owner_or_drdo_action": "none required (recorded)"},
        {"id": "DISC-07", "topic": "thrust range reading", "rfp_clauses": ["RFP-P18-06"],
         "rfp": "'12 mN to 25 mN (From expected drag to compensate)'",
         "repository": "RVM-02 / RVM-03: >= 12 mN sustained + 25 mN capability (owner row 4 reading)",
         "disposition": "owner engineering reading retained; the RFP gives no split between sustained and capability",
         "owner_or_drdo_action": "none required (recorded)"},
        {"id": "DISC-08", "topic": "ignition / restart", "rfp_clauses": [],
         "rfp": "no ignition / restart clause registered",
         "repository": "RVM-14 start-up / restart (earlier labelled RFP-inferred)",
         "disposition": "DERIVED_PROJECT_REQUIREMENT (A9.14 S9.12 OD14)", "owner_or_drdo_action": "none required"},
        {"id": "DISC-09", "topic": "ENTEST values", "rfp_clauses": ["RFP-P19-04"],
         "rfp": "'ENTEST Specifications (The specifications will be provided at the time PDR)'",
         "repository": "no ENTEST levels in the repository",
         "disposition": "RVM-21 carries no numeric level; levels TBD at PDR (not invented)",
         "owner_or_drdo_action": "DRDO supplies ENTEST specifications at PDR"},
        {"id": "DISC-10", "topic": "test-facility / thrust-measurement capability", "rfp_clauses": ["RFP-P27-01",
                                                                                                    "RFP-P30-01"],
         "rfp": "UHV test facility + low-thrust measurement setup (Part IV(B), no waivers); micro-newton-level thrust "
                "measurement (evaluation criterion)",
         "repository": "torsional thrust stand plan at mN level for RVM-02 (row 115, 1 % target); no micro-newton "
                       "capability record",
         "disposition": "new row RVM-26; the mN-level stand plan is not evidence of micro-newton capability",
         "owner_or_drdo_action": "owner: facility / stand capability evidence (in-house, consortium or sub-contract)"},
    ]


def coverage(reg: dict, rows: list) -> list:
    """clause id -> determining rows / related rows / programmatic class. Raises when a clause is unmapped."""
    out = []
    for c in reg["clauses"]:
        cid = c["id"]
        det = [r["id"] for r in rows if cid in r["rfp_clauses"]]
        rel = [r["id"] for r in rows if cid in r.get("related_rfp_clauses", [])]
        ns = NOT_SYSTEM_REQUIREMENTS.get(cid)
        if not det and not ns:
            raise RebaseError(f"RFP clause {cid} is not mapped to any RVM row (and is not a recorded programmatic item)")
        rec = {"clause_id": cid, "page": c["page"], "section": c["section"], "rvm_rows": det, "related_rvm_rows": rel}
        if ns:
            rec["not_system_requirement"] = {"class": ns[0], "why": ns[1]}
        if cid in PARTIAL_PROGRAMMATIC:
            rec["partial_programmatic"] = PARTIAL_PROGRAMMATIC[cid]
        out.append(rec)
    return out


def apply(doc: dict, reg: dict, secondary_basis: str) -> dict:
    load_a917()
    ids = {c["id"] for c in reg["clauses"]}
    by = {r["id"]: r for r in doc["rows"]}
    if set(by) != set(REBASE):
        raise RebaseError(f"RVM rows and re-base table differ: {sorted(set(by) ^ set(REBASE))}")
    for rid, m in REBASE.items():
        r = by[rid]
        if m["origin"] not in ORIGINS:
            raise RebaseError(f"{rid}: origin {m['origin']}")
        cl = m.get("clauses", [])
        if (m["origin"] == "RFP_CLAUSE") != bool(cl):
            raise RebaseError(f"{rid}: RFP_CLAUSE rows need clauses; other origins carry related clauses only")
        rel = m.get("related", [])
        if not set(rel) <= ids:
            raise RebaseError(f"{rid}: unknown related clause")
        recs = [clause_record(reg, cid, tok) for cid, tok in cl]
        prior = {"category": r["category"], "title": r["title"], "requirement_basis": r["requirement_basis"]}
        if m.get("text"):
            prior["requirement_text"] = r["requirement_text"]
            r["requirement_text"] = m["text"]
        if m.get("title"):
            r["title"] = m["title"]
        if m.get("category"):
            r["category"] = m["category"]
        if m.get("basis"):
            r["requirement_basis"] = m["basis"]
        r["requirement_origin"] = m["origin"]
        r["rfp_clauses"] = [c for c, _ in cl]
        r["related_rfp_clauses"] = list(rel)
        if m["origin"] == "RFP_CLAUSE":
            pb = prior["requirement_basis"]
            rest = pb[len(secondary_basis):] if pb.startswith(secondary_basis) else " (as carried: " + pb + ")"
            r["requirement_basis"] = (f"RFP_CLAUSE {', '.join(r['rfp_clauses'])} (official RFP {RFP_NUMBER}, registered "
                                      f"{REG_REL}, PDF sha256 {PDF_SHA256[:16]}...)" + rest)
        for s in r["sources"]:
            if s["kind"] in ("rfp_secondary_record", "repo_record"):
                s["rebase_role"] = "HISTORICAL_CROSS_REFERENCE_SUPERSEDED_BY_RFP_REGISTRATION"
        r["sources"] = recs + r["sources"]
        r["rfp_rebase"] = {
            "date": REBASE_DATE, "origin": m["origin"],
            "basis": {"RFP_CLAUSE": "derived from the cited registered RFP clause(s)",
                      "DERIVED_PROJECT_REQUIREMENT": "project-derived; no RFP clause states it (related clauses are "
                                                     "context only)",
                      "OWNER_ALLOCATION": "owner-given internal design allocation, not an RFP gate"}[m["origin"]],
            "decisions": [cite_a917(), L.cite("F9-OQ-03")] + [L.cite(q) for q in m.get("decisions", [])],
            "as_carried": prior,
            "requirement_frozen_note": ("stays false: the RFP transcription is registered (AG-15 step) but AG-15 "
                                        "closes only by owner verification; interpretation readings are listed in "
                                        "rfp_rebase.discrepancies") if m["origin"] == "RFP_CLAUSE" else
            "unchanged (" + str(r["requirement_frozen"]) + ")",
        }
        if m.get("note"):
            r["rfp_rebase"]["note"] = m["note"]
        if m["origin"] == "RFP_CLAUSE" and r["requirement_frozen"]:
            raise RebaseError(f"{rid}: an RFP row cannot be frozen before AG-15 closes")
    for it in doc["items"]:
        if it["id"] not in ITEMS:
            raise RebaseError(f"item {it['id']} not mapped")
        o, cs = ITEMS[it["id"]]
        if not set(cs) <= ids:
            raise RebaseError(f"item {it['id']}: unknown clause")
        it["requirement_origin"] = o
        it["rfp_clauses" if o == "RFP_CLAUSE" else "related_rfp_clauses"] = list(cs)
    for g in doc["a9_16_compliance_gates"]:
        g["rfp_clauses"] = list(COMPLIANCE_GATE_CLAUSES[g["id"]])
    cov = coverage(reg, doc["rows"])
    doc["rfp_rebase"] = {
        "id": "rvm_a9_rfp_rebase_v1", "date": REBASE_DATE, "gate": "AG-15 (A9.13 S6.22 F9-OQ-03)",
        "registration": {"path": REG_REL, "builder": REG_BUILDER, "rfp_number": RFP_NUMBER, "pdf_sha256": PDF_SHA256,
                         "pdf_in_repository": False, "clauses_sha256": CLAUSES_SHA256,
                         "clauses_hash_rule": "sha256 of json.dumps(clauses, ensure_ascii=False, sort_keys=True, "
                                              "separators=(',', ':'))",
                         "n_clauses": len(reg["clauses"]), "evidence_class": reg["evidence_class"]},
        "decisions": [L.cite("F9-OQ-03"), cite_a917(),
                      f"A9.15 ({L.LOADED['A9.15']['json']} sha256 {L.LOADED['A9.15']['json_sha256']})",
                      L.cite("OD12"), L.cite("OD14"), L.cite("RVMQ-01"), L.cite("OQ-VI-04"), L.cite("OQ-A907-06")],
        "origins": list(ORIGINS),
        "rule": "every RVM row cites the RFP clause id(s) it derives from or is labelled DERIVED_PROJECT_REQUIREMENT / "
                "OWNER_ALLOCATION; every registered clause maps to at least one row or is a recorded programmatic "
                "item; statuses unchanged by the re-base (rvm_rules; no PASS without determining evidence, A9.13 "
                "S6.22); requirement_frozen stays false on RFP rows until the owner closes AG-15",
        "ag_15_status": "OPEN - RFP registered by hash with verbatim transcription and the RVM re-based; closure is "
                        "the owner's (not declared here)",
        "origin_counts": {o: sum(1 for r in doc["rows"] if r["requirement_origin"] == o) for o in ORIGINS},
        "clause_coverage": cov,
        "not_system_requirements": [{"clause_id": k, "class": v[0], "why": v[1]}
                                    for k, v in NOT_SYSTEM_REQUIREMENTS.items()],
        "discrepancies": discrepancies(reg),
    }
    return doc
