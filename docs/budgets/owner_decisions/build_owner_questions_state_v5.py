"""Owner-question state v5: state v4 + the A9.7 lane questions, with the owner answers A9.8 .. A9.14 and A9.15 applied.

Owner instruction 2026-10-01 'continue implementing them sequentially' (A9.16 step 1, integration lane). State v4 stays
immutable (its committed JSON is pinned by sha256 here; v4 is never rebuilt by this builder). v5 is built as follows:

1. every v4 row is copied; rows that are not TBD_OWNER in v4 are copied unchanged;
2. every v4 TBD_OWNER row answered by an owner decision A9.8 / A9.10 / A9.11 / A9.12 / A9.14 gets the status
   ANSWERED_BY_A9_<n> (v4 status kept in 'v4_status') with the decision pointer, the decision json sha256, the verbatim
   .md path + sha256, the decision code and the verbatim answer section cut from the pinned .md (the .json summary is a
   recorder digest; the verbatim text governs);
3. the six answers amended by A9.15 (RFP-compliant propellant policy: OQ-A907-07, XA9Q-07, MPQ-01, XV2Q-01, XA9Q-05,
   OD6) get AMENDED_BY_A9_15; the A9.15 verbatim bullet governs ('governing_reading'); the A9.13 owner_statements.xenon
   and the A9.14 closing statement that keep 'Xe contingency-only for C1' are listed as superseded statements;
4. the 34 + 2 + 4 A9.7 lane questions rolled up by the F9 freeze candidate (owner_question_rollup) are added as rows
   with their answers (A9.9 S2, A9.13 S6, A9.14 S7 / S10);
5. a question raised since v4 by a lane package and still open (MPV3Q-01, mass/power v3; XV3Q-01, Xe accounting v3 -
   added by the A9.16 repair lane, F11) is added as TBD_OWNER.

6. the later owner decisions A9.17 .. A9.21 (pinned through docs/decisions/application/a9_later_lib.py) are applied
   to the rows they answer, amend or supersede (LATER_ROWS): the row keeps its earlier status in 'pre_a9_17_status'
   and gets AMENDED_BY_A9_19 / AMENDED_BY_A9_20 / AMENDED_BY_A9_21 (or ANSWERED_BY_A9_21 for the recorder proposal
   RP-A919-01, added as a row); every such row carries 'later_owner_decisions' records (pointer + json / md sha256 +
   verbatim excerpt + scope + relation SUPERSEDES / AMENDS / ANSWERS) and a 'later_governing_reading'. Rows that a
   later decision only confirms or whose required external input it states stays TBD (LATER_NOTES) keep their status
   and get the records only. A9.19: one flight configuration hall_icp_neutralizer (one Hall + one RF/ICP neutralizer
   for air and Xe, two supply modes, Xe contingency / emergency, no hollow cathode); A9.20: C1 is a ground-only
   laboratory reference (hall_c1_reference retired as a flight configuration).

A v4 TBD_OWNER row with no owner answer stays TBD_OWNER. Nothing is answered here that the owner did not answer; the
step-1 RFP-cited facts ('RFP(1)') keep rfp_citation_status OWNER_STATED_PENDING_RFP_REGISTRATION as the record of
that state (the RFP has since been registered by hash, A9.17 RFP, and the RVM re-based; AG-15 closure stays the
owner's - see 'rfp_registration_now'). Missing or unexpected ids raise.

stdlib only.

    python docs/budgets/owner_decisions/build_owner_questions_state_v5.py          # write JSON + MD + CSV
    python docs/budgets/owner_decisions/build_owner_questions_state_v5.py --check  # verify outputs are current
"""
import copy
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402
import a9_later_lib as X  # noqa: E402

REL = lambda p: p.relative_to(ROOT).as_posix()
V4 = HERE / "owner_questions_state_v4.json"
V4_SHA = "6ba74803f9577cb63f3e719d176702eb47e05a55a3c054eba926649a5c23bf67"
SEQ_CSV = HERE / "owner_questions_sequenced_v1.csv"
SEQ_MD = HERE / "OWNER_QUESTIONS_SEQUENCED_v1.md"
F9 = ROOT / "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
MP3 = ROOT / "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"
XE3 = ROOT / "docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json"

OUT_JSON = HERE / "owner_questions_state_v5.json"
OUT_MD = HERE / "OWNER_QUESTIONS_STATE_v5.md"
OUT_CSV = HERE / "owner_questions_state_v5.csv"
RVM = ROOT / "docs/requirements/rvm_a9/rvm_a9_v1.json"
RFP_REG = ROOT / "docs/requirements/rfp_official/rfp_registration_v1.json"

# ------------------------------------------------------------------------------------- A9.17 .. A9.21 (later decisions)
# (decision, item, relation, verbatim excerpt (checked against the pinned md), scope). Excerpts are verbatim owner text.
_A919 = X.body("A9.19")
_A920 = X.body("A9.20")
_C1_FALLBACK = "amends/A9 C1 CONTROL_FALLBACK"
_C1_FLIGHT = "amends/A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07"
_A920_C1 = ("A9.20", "answer", "AMENDS", _A920,
            "C1 is a GROUND_ONLY_LAB_REFERENCE (owner chose the recommended 'Ground-only reference' option): it registers "
            "I_d,max,H1,Ar on H-1 and is the C1-vs-ICP bench control; never flight hardware, never in the flight mass / "
            "power / Xe budgets; hall_c1_reference is not a flight configuration")

LATER_ROWS = {
    # ---- A9.19 / A9.20: no C1 flight variant, no C1 fallback, Xe role contingency / emergency, one flight configuration
    "OQ-A907-07": ("A9.19", [
        ("A9.19", _C1_FLIGHT, "SUPERSEDES", _A919, "no C1 flight variant: the flight architecture has no conventional "
         "hollow cathode, so a flight C1 integration is neither developed nor deferred; the A9.14 'defer until selected' "
         "answer and the A9.15 reading of it are history"),
        ("A9.20", "answer", "SUPERSEDES", _A920, _A920_C1[4])]),
    "MPQ-01": ("A9.19", [
        ("A9.19", _C1_FLIGHT, "SUPERSEDES", _A919, "no AL-C1 line and no C1 electronics / C1 Xe branch booking in the "
         "flight architecture (A9.19 amends S8.33); the option-(c) allocation and the A9.15 reading of it are history"),
        ("A9.20", "answer", "SUPERSEDES", _A920, _A920_C1[4])]),
    "XA9Q-07": ("A9.19", [
        ("A9.19", "xenon_role", "AMENDS", _A919, "ROLE of Xe only: Xe is the contingency / emergency supply mode (two "
         "supply modes, separate tanks / paths); the YES on Xe propulsion capability for hall_icp_neutralizer stands"),
        ("A9.20", "answer", "AMENDS", _A920, "'both configurations': hall_c1_reference is no longer a candidate flight "
         "configuration; the Xe capability applies to the one flight configuration hall_icp_neutralizer")]),
    "XV2Q-01": ("A9.19", [
        ("A9.19", "xenon_role", "AMENDS", _A919, "ROLE of Xe only: NOT APPLICABLE stands - the flight configuration is "
         "not Xe-free; Xe is retained as the contingency / emergency supply mode with its own tank / path")]),
    "OD6": ("A9.19", [
        ("A9.19", "amends/A9.15", "AMENDS", _A919, "ROLE of Xe only: the A9.15 clause 'it should not be weakened into a "
         "contingency interpretation' is superseded on the role of Xe (contingency / emergency supply mode); "
         "dual-propellant capability as separate selectable modes with separate storage stands")]),
    "OD5": ("A9.19", [
        ("A9.19", "architecture", "AMENDS", _A919, "the clause 'A C1-selected variant uses its separately qualified "
         "heater/keeper sequence' has no flight application (no conventional hollow cathode); the ICP-first, Hall-second "
         "start sequence with at most three attempts stands"),
        _A920_C1]),
    "OQ-A907-01": ("A9.20", [
        ("A9.20", "answer", "AMENDS", _A920, "the three-dwell C1 ignition booking (1 + 2 retries) applies to the ground "
         "C1 laboratory reference and its test-campaign Xe only; it is never a flight Xe budget line"),
        ("A9.19", "architecture", "AMENDS", _A919, "no conventional hollow cathode in the flight architecture")]),
    "OD-XE-5": ("A9.19", [
        ("A9.19", _C1_FALLBACK, "AMENDS", _A919, "'reference/fallback' -> reference only: C1 is not a flight fallback; "
         "the 15,000 h C1 cathode term applies to no flight element (the ICP neutralizer carries its own life / cycle "
         "requirement, unchanged)"), _A920_C1]),
    "R6-Q1": ("A9.19", [
        ("A9.19", _C1_FALLBACK, "AMENDS", _A919, "'conventional reference/fallback' -> ground reference only; the heated "
         "Xe-fed LaB6 choice stands for the ground C1 reference"), _A920_C1]),
    "OD-M5": ("A9.19", [
        ("A9.19", _C1_FALLBACK, "AMENDS", _A919, "'retain C1 as reference/fallback' -> C1 is retained only as the ground "
         "laboratory reference and is not a flight BOM item; the ICP / RF / collector BOM additions stand"), _A920_C1]),
    "HWQ-09": ("A9.19", [
        ("A9.19", _C1_FALLBACK, "AMENDS", _A919, "'conventional reference/fallback' -> ground reference only; the one "
         "RF/ICP neutralizer is the only flight electron source (no 'if the downstream ICP succeeds' fallback)"),
        _A920_C1]),
    # ---- A9.21
    "MQ-05": ("A9.21", [
        ("A9.21", "AL08", "AMENDS", None, "the 6.05 kg (6.0528 kg MEV) AL-08 figure is a PROVISIONAL planning floor, "
         "not a frozen allocation; the formal AL-08 re-base waits for quotations split into tank, regulator, valves, "
         "plumbing, mounting/thermal and any C1-specific branch (the analog floor may contain about 0.285 kg of C1 "
         "cathode-branch hardware); the complete-Xe-system scope of S8.10 stands")]),
    "WEB-ACC-2": ("A9.21", [
        ("A9.21", "BID_CLOSE", "AMENDS", None, "bid-close part: 05-Oct-2026 17:00 is the operational submission deadline "
         "(DefProc tender 2026_DRDO_788433_1) unless a DefProc corrigendum changes it; the RFP PDF need not contain it. "
         "RFP-number part: see rfp_registered_document (A9.17 RFP registration by hash)")]),
}
_EXCERPT = {("MQ-05", "AL08"): ("2. Xe-hardware floor", {}), ("WEB-ACC-2", "BID_CLOSE"): ("5. Bid close", {})}

LATER_NOTES = {
    # confirmations / external inputs that stay TBD (status unchanged; records only)
    "P1Q-07": [_A920_C1[:2] + ("CONFIRMS", _A920, "C1 stays the ground reference that registers I_d,max,H1,Ar"),
               ("A9.21", "HW_PROGRAMME", "CONFIRMS", ("7. C1 ground reference", {}),
                "H-1 + C1 reference characterization approved; I_d,max,H1,Ar registered before P1-S7")],
    "F5-OQ-01": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("6. H-1 engineering build", {}),
                  "S7.1 FEMM analysis points first (engineering build approved)")],
    "F5-OQ-02": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("6. H-1 engineering build", {}),
                  "S7.2 engineering channel point after S7.1; an engineering freeze candidate, not thrust-optimized")],
    "F9-OQ-02": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("11. Measured H-1 thrust/feed map", {}),
                  "the measured H-1 thrust / feed map is mandatory and drives the AG-12 performance-derived feed "
                  "requirement, followed by the statewise AG-13 T - D >= 0 check")],
    "P1-IT-52": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("8. ICP programme", {}),
                  "stage domains are closed before the registered air/N2 ICP-45 and Xe-mode campaigns start; each "
                  "gas / mode gets its own operating domain and provenance")],
    "P1-IT-55": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("8. ICP programme", {}),
                  "DWV leakage criteria are closed before the ICP campaigns start")],
    "P2Q-07": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("9. P2 impedance map", {}),
                "the P2 impedance map runs after the in-house V/I magnitude / phase calibration and its uncertainty "
                "budget are frozen")],
    "P4-OQ-03": [("A9.21", "HW_PROGRAMME", "CONFIRMS", ("10. Coupled H-1 + ICP", {}),
                  "P4 acceptance thresholds frozen before acceptance-bearing coupon exposure (LOCK-2 rule)")],
    "F1Q-03": [("A9.21", "EXTERNAL_INPUTS", "INPUT_STAYS_TBD",
                "* AOCS pointing envelope: needs the actual spacecraft/AOCS requirement.",
                "the AOCS pointing envelope stays TBD (external input); intake surface v2 stays unbuilt until it is "
                "registered")],
    "OQ-F78-04": [("A9.21", "EXTERNAL_INPUTS", "INPUT_STAYS_TBD",
                   "* Host-spacecraft drag ICD: needs actual spacecraft geometry/attitude/surface data.",
                   "the host-spacecraft drag ICD stays TBD; D_spacecraft and T - D stay NOT_EVALUATED for freeze")],
    "OD3": [("A9.17", "ORBIT", "INPUT_STAYS_TBD", ("2. Inclination / LTAN", {"key": "A9.17"}),
             "96.3 deg / dawn-dusk stays CODE_DEFAULT / PARAMETRIC; the design-state envelope stays broad until the "
             "official inclination / LTAN is supplied"),
            ("A9.21", "EXTERNAL_INPUTS", "INPUT_STAYS_TBD",
             "* Inclination and LTAN: not specified by the RFP; do not use the old code default as mission truth.",
             "inclination / LTAN stay TBD (external input)")],
    "OQ-F4-05": [("A9.17", "WINDS", "CONFIRMS", ("1. Atmospheric winds", {"key": "A9.17"}),
                  "relative flow / wind state: HWM14 atmosphere v2 (v1 immutable); parametric until the orbit is "
                  "registered"),
                 ("A9.17", "ORBIT", "INPUT_STAYS_TBD", ("2. Inclination / LTAN", {"key": "A9.17"}),
                  "orbit-resolved dataset regenerated / narrowed under a new version once the official inclination / "
                  "LTAN is supplied"),
                 ("A9.21", "EXTERNAL_INPUTS", "INPUT_STAYS_TBD",
                  "* Inclination and LTAN: not specified by the RFP; do not use the old code default as mission truth.",
                  "inclination / LTAN stay TBD (external input)")],
    "F0-OQ-02": [("A9.17", "PERF", "CONFIRMS", ("For performance, yes:", {"key": "A9.17", "through": "Decision:"}),
                  "dedicated baseline run on the idle owner machine (2026-10-01)"),
                 ("A9.18", "PERF_RERUN", "CONFIRMS", ("2. Dedicated performance baseline", {"key": "A9.18"}),
                  "the 2026-10-01 run is historical for the earlier code state; the rerun after the step-3 merge is the "
                  "Rust-admission baseline"),
                 ("A9.21", "PERF_RERUN", "CONFIRMS", ("1. Dedicated baseline", {}),
                  "the owner reruns on the exact commit SHA supplied, into a new folder; the previous baseline is kept "
                  "unchanged")],
    "F9-OQ-03": [("A9.17", "RFP", "CONFIRMS", ("4. RFP PDF + dedicated performance baseline", {"key": "A9.17",
                                                                                               "through": "For the RFP"}),
                  "AG-15 registration part: the official RFP is registered by hash with provenance in the public "
                  "repository (PDF in the controlled evidence store) and the RVM is re-based on it; AG-15 closure "
                  "(owner acceptance; requirement_frozen) stays the owner's")],
}
NEW_ROW_ID = "RP-A919-01"
LATER_STATUS_TEXT = {
    "AMENDED_BY_A9_19": "earlier answer amended or superseded by owner decision A9.19 (single Hall + RF/ICP neutralizer "
                        "flight architecture, Xe contingency / emergency, no hollow cathode); see later_owner_decisions "
                        "(the scope of each record names what changes; pre_a9_17_status keeps the earlier status)",
    "AMENDED_BY_A9_20": "earlier answer amended by owner decision A9.20 (C1 ground-only laboratory reference); see "
                        "later_owner_decisions",
    "AMENDED_BY_A9_21": "earlier answer amended by owner decision A9.21 (open items + hardware programme); see "
                        "later_owner_decisions",
    "ANSWERED_BY_A9_21": "answered (in the scope named in status_detail / open_part) by owner decision A9.21",
}

STATUS_OF = {k: "ANSWERED_BY_" + k.replace(".", "_") for k in L.ORDER if k != "A9.15"}
NEW_STATUSES = {s: f"answered by owner decision {k} ({L.LOADED[k]['json']}; verbatim {L.LOADED[k]['md']})"
                for k, s in STATUS_OF.items()}
NEW_STATUSES["AMENDED_BY_A9_15"] = (
    "answered by A9.14 and amended by A9.15, the RFP-compliant propellant policy (" + L.LOADED["A9.15"]["json"] +
    "): the A9.15 verbatim bullet governs; 'Xe contingency-only for C1' readings are superseded")
APPLICATION_STEP = {"A9.9": "PENDING_STEP_2_MODEL_CHANGE (A9.9 production-model changes are a later controlled step)"}

# A9.7 lane questions answered by A9.9 / A9.13 / A9.14 (ids exactly as in the F9 owner_question_rollup)
A97_KIND = "a9_7_lane_question"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _flat(v):
    if isinstance(v, (list, tuple)):
        return "; ".join(_flat(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return "" if v is None else str(v)


def _clip(s, n):
    s = " ".join(_flat(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def load_v4():
    got = _sha(V4)
    if got != V4_SHA:
        raise SystemExit(f"state v4 sha256 {got} != pinned {V4_SHA} (v4 is immutable)")
    return json.loads(V4.read_text(encoding="utf-8"))


def sequenced():
    rows = list(csv.DictReader(SEQ_CSV.open(encoding="utf-8")))
    out = {}
    for r in rows:
        if r["id"] in out:
            raise SystemExit(f"sequenced list: duplicate id {r['id']}")
        out[r["id"]] = r
    return out


def answer_fields(qid: str) -> dict:
    a = L.answer(qid)
    status = "AMENDED_BY_A9_15" if "amended_by" in a else STATUS_OF[a["decision"]]
    f = {"status": status,
         "status_detail": f"ANSWERED ({a['decision']} {a['sequenced_no']}, decision code {a['decision_code']})"
                          + ("; AMENDED (A9.15)" if "amended_by" in a else ""),
         "answer_decision": a["decision"], "sequenced_no": a["sequenced_no"], "decision_code": a["decision_code"],
         "answer_pointer": a["pointer"], "answer_sha256": a["decision_json_sha256"],
         "answer_verbatim_path": a["decision_md"], "answer_verbatim_sha256": a["decision_md_sha256"],
         "answer_excerpt": a["verbatim_excerpt"]}
    if a["rfp_citation_status"]:
        f["rfp_citation_status"] = a["rfp_citation_status"]
    if "amended_by" in a:
        f["amended_by"] = a["amended_by"]
        f["governing_reading"] = {"decision": "A9.15", "pointer": a["amended_by"]["pointer"],
                                  "sha256": a["amended_by"]["decision_json_sha256"],
                                  "text": a["amended_by"]["verbatim_excerpt"]}
    if a["decision"] in APPLICATION_STEP:
        f["application_status"] = APPLICATION_STEP[a["decision"]]
    return f


def _src(src: dict) -> dict:
    # lane packages are mutable: path + pointer / locator only (no sha256: the F9 rollup re-pins them at every build)
    return {k: v for k, v in src.items() if k in ("path", "pointer", "locator")}


def a97_questions(f9: dict) -> list:
    roll = f9["owner_question_rollup"]
    out = []
    for q in roll["a9_7_lane_questions"]:
        out.append({"id": q["id"], "lane": "A9.7 " + q["lane"], "question": q["question"], "source_ref": _src(q["source"])})
    for q in roll["other_existing_open_questions_cited"]:
        out.append({"id": q["id"], "lane": "A9.7 existing ICD", "question": q["question"], "source_ref": _src(q["source"])})
    by_id = {q["id"]: q for q in f9["open_owner_questions"]}
    for qid in roll["new_f9_questions"]:
        q = by_id[qid]
        out.append({"id": qid, "lane": "A9.7 F9", "question": q["question"],
                    "source_ref": {"path": REL(F9), "pointer": f"/open_owner_questions[id={qid}]"},
                    "needed_by": q.get("needed_by")})
    if len(out) != 40 or len({q["id"] for q in out}) != 40:
        raise SystemExit(f"F9 rollup: expected 34 + 2 + 4 = 40 unique A9.7 lane questions, got {len(out)}")
    return out


def superseded_statements():
    a13 = L.LOADED["A9.13"]
    a14 = L.LOADED["A9.14"]
    closing = [ln.strip() for ln in a14["md_text"].splitlines() if ln.startswith("One especially important consistency")]
    if len(closing) != 1:
        raise SystemExit("A9.14 closing Xe statement not found")
    gov = L.a915_governing_statement()
    return [
        {"id": "A9.13 owner_statements.xenon", "path": a13["json"], "sha256": a13["json_sha256"],
         "pointer": f"{a13['json']}#/owner_statements/xenon", "text": a13["doc"]["owner_statements"]["xenon"],
         "superseded_by": {"decision": "A9.15", "path": L.LOADED["A9.15"]["json"],
                           "sha256": L.LOADED["A9.15"]["json_sha256"],
                           "pointer": f"{L.LOADED['A9.15']['json']}#/amendments/A9.13 owner_statements.xenon",
                           "governing_statement": gov}},
        {"id": "A9.14 closing statement (Xe for C1)", "path": a14["md"], "sha256": a14["md_sha256"],
         "pointer": f"{a14['md']} (closing paragraph)", "text": closing[0],
         "superseded_by": {"decision": "A9.15", "path": L.LOADED["A9.15"]["json"],
                           "sha256": L.LOADED["A9.15"]["json_sha256"], "pointer": f"{L.LOADED['A9.15']['json']}#/governing_rule",
                           "governing_statement": gov}},
    ]


def _excerpt(dec, ex, row_id, item):
    if ex is None:
        ex = _EXCERPT[(row_id, item)]
    if isinstance(ex, tuple):
        start, kw = ex
        return X.block(kw.get("key", dec), start, through=kw.get("through", "Decision:"))
    return X.verbatim(dec, ex)


def _records(row_id, spec):
    out = []
    for dec, item, rel, ex, scope in spec:
        out.append(X.record(dec, item, rel, _excerpt(dec, ex, row_id, item), scope))
    return out


def _one_row(rows, qid):
    hits = [r for r in rows if r["id"] == qid]
    if len(hits) != 1:
        raise SystemExit(f"later decisions: {qid} matches {len(hits)} state rows (expected exactly one)")
    return hits[0]


def rfp_registration_now(reg: dict, rvm: dict) -> dict:
    doc = reg["document"]
    if reg["status"] != "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY" or len(doc.get("sha256", "")) != 64:
        raise SystemExit(f"RFP registration status {reg['status']!r} / sha256 not as registered (fail closed)")
    rb = rvm["rfp_rebase"]
    if rb["registration"]["pdf_sha256"] != doc["sha256"]:
        raise SystemExit("RVM re-base registration sha256 != rfp_registration_v1 document sha256")
    return {"registration": {"path": REL(RFP_REG), "status": reg["status"], "rfp_number": doc["rfp_number"],
                             "pdf_sha256": doc["sha256"], "pages": doc["pages"], "n_clauses": len(reg["clauses"]),
                             "pdf_in_repository": doc["committed_to_repository"]},
            "rvm_rebase": {"path": REL(RVM), "id": rb["id"], "ag_15_status": rb["ag_15_status"]},
            "rule": "the step-1 rfp_citation_status OWNER_STATED_PENDING_RFP_REGISTRATION on rows answered by A9.8 .. "
                    "A9.15 records the state when those answers were applied; the RFP is now registered by hash (A9.17 "
                    "RFP) and the RVM re-based on it; AG-15 closure (owner acceptance; requirement_frozen) stays the "
                    "owner's and is not declared here"}


def apply_later(rows: list, rvm: dict, reg: dict) -> dict:
    """Apply A9.17 .. A9.21 to the rows they amend / answer (status change) or confirm (records only)."""
    applied = {"amended": {}, "answered": [], "noted": {}}
    for qid, (status_by, spec) in LATER_ROWS.items():
        r = _one_row(rows, qid)
        recs = _records(qid, spec)
        if not any(x["decision"] == status_by for x in recs):
            raise SystemExit(f"{qid}: status decision {status_by} has no record")
        r["pre_a9_17_status"] = r["status"]
        if r.get("status_detail") is not None:
            r["pre_a9_17_status_detail"] = r["status_detail"]
        r["status"] = "AMENDED_BY_" + status_by.replace(".", "_")
        r["status_detail"] = (r.get("status_detail") or r["pre_a9_17_status"]) + "; " + "; ".join(
            f"{x['relation']} by {x['decision']} {x['item']}" for x in recs)
        r["later_owner_decisions"] = recs
        sup = [x for x in recs if x["relation"] == "SUPERSEDES"]
        r["later_governing_reading"] = {
            "decisions": sorted({x["decision"] for x in recs}),
            "pointers": [x["pointer"] for x in recs],
            "sha256": [x["decision_json_sha256"] for x in recs],
            "text": " | ".join(dict.fromkeys(x["verbatim_excerpt"] for x in recs)),
            "scope": " | ".join(x["scope"] for x in recs)}
        if r.get("governing_reading"):
            r["governing_reading_status"] = ("SUPERSEDED_BY_" if sup else "AMENDED_IN_SCOPE_BY_") + \
                status_by.replace(".", "_")
        applied["amended"][qid] = r["status"]
        if qid == "WEB-ACC-2":
            doc = reg["document"]
            r["rfp_registered_document"] = {
                "rfp_number": doc["rfp_number"], "pdf_sha256": doc["sha256"], "status": reg["status"],
                "source": f"{REL(RFP_REG)} document.rfp_number (A9.17 RFP registration by hash)",
                "bid_close_in_document": next((x for x in doc.get("not_in_document", []) if "closing date" in x),
                                              None)}
    for qid, spec in LATER_NOTES.items():
        r = _one_row(rows, qid)
        if qid in LATER_ROWS:
            raise SystemExit(f"{qid} both amended and noted")
        recs = _records(qid, spec)
        if any(x["relation"] in ("SUPERSEDES", "AMENDS", "ANSWERS") for x in recs):
            raise SystemExit(f"{qid}: a status-changing relation belongs in LATER_ROWS")
        r["later_owner_decisions"] = recs
        if any(x["relation"] == "INPUT_STAYS_TBD" for x in recs):
            r["external_input_status"] = ("TBD_EXTERNAL_INPUT (" + "; ".join(
                f"{x['decision']} {x['item']}" for x in recs if x["relation"] == "INPUT_STAYS_TBD")
                + "): cannot be supplied from current evidence; no code default is mission truth")
        applied["noted"][qid] = sorted({x["relation"] for x in recs})
    # the recorder's ICP go / no-go proposal (RVM, raised after A9.19), answered in part by A9.21 ICP_GATE
    props = [p for p in rvm.get("recorder_proposals_open_for_owner", []) if p["id"] == NEW_ROW_ID]
    if len(props) != 1 or props[0].get("is_owner_decision") is not False:
        raise SystemExit(f"RVM recorder proposal {NEW_ROW_ID} not found exactly once as a non-decision")
    p = props[0]
    rec = X.record("A9.21", "ICP_GATE", "ANSWERS", X.block("A9.21", "4. ICP go/no-go", extra=1),
                   "gate EXISTENCE and PLACEMENT approved (mandatory ICP go / no-go before LOCK-1, fail closed: missing "
                   "evidence -> NOT_EVALUATED, never GO); NO numerical criterion approved")
    a = X.LOADED["A9.21"]
    rows.append({
        "no": len(rows) + 1, "id": NEW_ROW_ID, "kind": "recorder_proposal", "lane": "RVM A9.19 / A9.20 application",
        "source": f"{REL(RVM)} recorder_proposals_open_for_owner[id={NEW_ROW_ID}]",
        "source_ref": {"path": REL(RVM), "locator": f"recorder_proposals_open_for_owner[id={NEW_ROW_ID}]"},
        "question": p["proposal"], "proposed": p["numbers"], "needed_by": "LOCK-1",
        "status": "ANSWERED_BY_A9_21",
        "status_detail": "ANSWERED IN PART (A9.21 ICP_GATE, decision code ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1): the gate "
                         "exists and sits before LOCK-1, fail closed; the proposal's criteria (a) - (c) are NOT approved "
                         "and are preserved for owner review (open_part)",
        "answer_decision": "A9.21", "decision_code": rec["decision_code"], "answer_pointer": rec["pointer"],
        "answer_sha256": a["json_sha256"], "answer_verbatim_path": a["md"], "answer_verbatim_sha256": a["md_sha256"],
        "answer_excerpt": rec["verbatim_excerpt"], "later_owner_decisions": [rec],
        "open_part": {"what": "numerical GO / NO-GO criteria: the recorder proposal text (criteria (a) - (c), no "
                              "numbers) is preserved for the owner's review; nothing is approved or invented here",
                      "preserved_text": p["proposal"], "status": "NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"},
        "dependency": ["OWNER_JUDGMENT"], "blocks": ["BLOCKS_LOCK_1"],
        "classification_basis": "recorder proposal raised with the A9.19 RVM application (no hollow-cathode fallback "
                                "after A9.19; the owner asked 'is it good to remove hollow cathode', A9.20); A9.21 "
                                "approves the gate, not its criteria"})
    applied["answered"].append(NEW_ROW_ID)
    return applied


def later_superseded_statements() -> list:
    a15 = L.LOADED["A9.15"]
    out = []
    for sid, text in (("A9.15 'Xenon is ... not merely a contingency'",
                       "Xenon is therefore an RFP-required system capability, not merely a contingency introduced by "
                       "our internal architecture."),
                      ("A9.15 S9.10 / OD6 bullet", L.a915_amendment_line("OD6"))):
        if text not in a15["md_text"]:
            raise SystemExit(f"A9.15 statement not found verbatim: {text[:60]!r}")
        out.append({"id": sid, "path": a15["md"], "sha256": a15["md_sha256"], "text": text,
                    "superseded_by": {"decision": "A9.19", "path": X.LOADED["A9.19"]["json"],
                                      "sha256": X.LOADED["A9.19"]["json_sha256"],
                                      "pointer": X.pointer("A9.19", "amends/A9.15"),
                                      "recorder_digest": X.digest("A9.19", "amends/A9.15"),
                                      "verbatim_owner_text": X.verbatim("A9.19", "xenon is not a parllel gas its just a "
                                                                                 "contigency and emergency gas")},
                    "scope": "ROLE of Xe only (contingency / emergency supply mode); the RFP-required Xe capability, "
                             "two separate supply modes and the A9.15 governing statement on capability stand"})
    return out


def build():
    v4 = load_v4()
    seq = sequenced()
    f9 = json.loads(F9.read_text(encoding="utf-8"))
    mp3 = json.loads(MP3.read_text(encoding="utf-8"))
    xe3 = json.loads(XE3.read_text(encoding="utf-8"))
    answered_ids = {q for k in L.ORDER if k != "A9.15" for q in L.decision_ids(k)}

    rows = []
    used = set()
    for r4 in v4["rows"]:
        r = copy.deepcopy(r4)
        if r4["status"] == "TBD_OWNER" and r4["id"] in answered_ids:
            if r4["id"] in used:
                raise SystemExit(f"v4 TBD_OWNER id {r4['id']} appears twice")
            used.add(r4["id"])
            s = seq.get(r4["id"])
            if s is None or s["source"] != f"owner_questions_state_v4 row {r4['no']}":
                raise SystemExit(f"{r4['id']}: sequenced list source {s and s['source']} != v4 row {r4['no']}")
            r["v4_status"] = "TBD_OWNER"
            r.update(answer_fields(r4["id"]))
        rows.append(r)
    nxt = len(rows) + 1
    for q in a97_questions(f9):
        if q["id"] not in answered_ids:
            raise SystemExit(f"A9.7 lane question {q['id']} has no owner answer in A9.8 .. A9.14")
        if q["id"] in used:
            raise SystemExit(f"A9.7 lane question {q['id']} already a v4 row")
        used.add(q["id"])
        s = seq.get(q["id"])
        if s is None:
            raise SystemExit(f"{q['id']} missing from the sequenced list")
        row = {"no": nxt, "id": q["id"], "kind": A97_KIND, "lane": q["lane"],
               "source": f"{q['source_ref']['path']} {q['source_ref'].get('pointer') or q['source_ref'].get('locator')}",
               "source_ref": q["source_ref"], "question": q["question"],
               "proposed": s["proposed"], "needed_by": q.get("needed_by") or s["blocks"],
               "rolled_up_by": {"path": REL(F9), "pointer": "/owner_question_rollup"}}
        row.update(answer_fields(q["id"]))
        rows.append(row)
        nxt += 1
    for i, q in enumerate(mp3["open_owner_questions"]):
        if q["status"] != "OPEN":
            continue
        rows.append({"no": nxt, "id": q["id"], "kind": "lane_question", "lane": "mass/power v3 (A9.16 step 1)",
                     "source": f"{REL(MP3)} open_owner_questions[id={q['id']}]",
                     "source_ref": {"path": REL(MP3), "locator": f"open_owner_questions[id={q['id']}]"},
                     "question": q["question"], "proposed": q["proposed"], "needed_by": q["needed_by"],
                     "status": "TBD_OWNER", "status_detail": "TBD_OWNER (raised since v4; no owner answer)",
                     "dependency": ["OWNER_JUDGMENT"], "blocks": ["BLOCKS_LOCK_1"],
                     "classification_basis": "MQ-06 split the row-54 controls/harness line; the controls allocation "
                                             "is a genuine owner allocation (no number invented)"})
        nxt += 1
    # A9.16 repair F11: the A9.15 recorder note flagged the A9.1 HIQ-06 ICP-feed 'contingency' labels to the owner;
    # Xe accounting v3 raises it as XV3Q-01 (no reading chosen) - carried here as TBD_OWNER
    for q in xe3["open_owner_questions"]:
        if q["status"] != "OPEN":
            continue
        rows.append({"no": nxt, "id": q["id"], "kind": "lane_question", "lane": "Xe accounting v3 (A9.16 repair lane)",
                     "source": f"{REL(XE3)} open_owner_questions[id={q['id']}]",
                     "source_ref": {"path": REL(XE3), "locator": f"open_owner_questions[id={q['id']}]"},
                     "question": q["question"], "proposed": q["proposed"], "needed_by": q["needed_by"],
                     "status": "TBD_OWNER", "status_detail": "TBD_OWNER (raised since v4; no owner answer)",
                     "dependency": ["OWNER_JUDGMENT"], "blocks": ["BLOCKS_LOCK_1"],
                     "classification_basis": "the A9.15 recorder note flags the A9.1 HIQ-06 ICP-feed labels to the "
                                             "owner; no owner answer exists, so no reading is chosen (A9.1 basis: "
                                             + q["a9_1_basis_verbatim"] + ")"})
        nxt += 1
    missing = sorted(answered_ids - used)
    if missing:
        raise SystemExit(f"owner answers with no state row: {missing}")
    row_ids = {r["id"] for r in rows}
    if any(i not in row_ids for i in seq):
        raise SystemExit("a sequenced question has no v5 row")
    rvm = json.loads(RVM.read_text(encoding="utf-8"))
    reg = json.loads(RFP_REG.read_text(encoding="utf-8"))
    later = apply_later(rows, rvm, reg)

    counts, tbd_blocks = {}, {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["status"] == "TBD_OWNER":
            for b in r["blocks"]:
                tbd_blocks[b] = tbd_blocks.get(b, 0) + 1
    by_dec = {}
    for r in rows:
        if r.get("v4_status") == "TBD_OWNER" or r.get("kind") == A97_KIND:
            by_dec[r["answer_decision"]] = by_dec.get(r["answer_decision"], 0) + 1
    vocab = dict(v4["status_vocabulary"])
    vocab.update(NEW_STATUSES)
    vocab.update(LATER_STATUS_TEXT)
    later_counts = {}
    for r in rows:
        for x in r.get("later_owner_decisions", []):
            k = (x["decision"], x["relation"])
            later_counts[k] = later_counts.get(k, 0) + 1
    applied_later = [{"id": f"{k} ({X.LOADED[k]['label']})", "decision_json": X.LOADED[k]["json"],
                      "decision_json_sha256": X.LOADED[k]["json_sha256"], "decision_md": X.LOADED[k]["md"],
                      "decision_md_sha256": X.LOADED[k]["md_sha256"],
                      "rows": sorted({r["id"] for r in rows for x in r.get("later_owner_decisions", [])
                                      if x["decision"] == k}),
                      "how_applied": "later_owner_decisions records (pointer, json / md sha256, verbatim excerpt, "
                                     "relation, scope); status AMENDED_BY / ANSWERED_BY only where the relation is "
                                     "SUPERSEDES / AMENDS / ANSWERS"} for k in X.ORDER]
    applied = [{"id": f"{k} ({L.LOADED[k]['label']})", "decision_json": L.LOADED[k]["json"],
                "decision_json_sha256": L.LOADED[k]["json_sha256"], "decision_md": L.LOADED[k]["md"],
                "decision_md_sha256": L.LOADED[k]["md_sha256"],
                "question_ids": L.decision_ids(k) if k != "A9.15" else list(L.A915_AMENDED),
                "how_applied": (f"rows {STATUS_OF[k]} with pointer, json sha256, verbatim md sha256, decision code and "
                                "the verbatim section" if k != "A9.15" else
                                "rows AMENDED_BY_A9_15 with the verbatim A9.15 bullet as governing_reading; A9.13 "
                                "owner_statements.xenon and the A9.14 closing Xe statement listed as superseded")
                + ("; application PENDING_STEP_2_MODEL_CHANGE" if k == "A9.9" else "")}
               for k in L.ORDER]
    return {
        "schema": "owner_questions_state_v5",
        "id": "owner_questions_state_v5",
        "lane": "A9.16 step 1 integration (decision application)",
        "status": "STATE_RECORD_FOR_OWNER (answers come only from the owner)",
        "a9_status": v4["a9_status"],
        "supersedes_for_use": f"{REL(V4)} (kept immutable; pinned)",
        "generated_by": "docs/budgets/owner_decisions/build_owner_questions_state_v5.py",
        "companion_document": REL(OUT_MD), "companion_csv": REL(OUT_CSV),
        "test": "tests/test_owner_questions_state_v5.py",
        "pins": [{"key": "state_v4", "path": REL(V4), "sha256": V4_SHA},
                 {"key": "sequenced_v1_csv", "path": REL(SEQ_CSV), "sha256": _sha(SEQ_CSV)},
                 {"key": "sequenced_v1_md", "path": REL(SEQ_MD), "sha256": _sha(SEQ_MD)}] + L.pins() + X.pins(),
        "referenced_not_pinned": {
            "rule": "mutable lane deliverables: read at build time, ids checked (a missing id raises), never sha-pinned",
            "paths": [REL(F9), REL(MP3), REL(XE3), REL(RVM), REL(RFP_REG)]},
        "status_vocabulary": vocab,
        "status_rule": ("'status' is canonical. A v4 TBD_OWNER row answered by A9.8 .. A9.14 keeps 'v4_status' and gets "
                        "ANSWERED_BY_A9_<n> or, where A9.15 amends the answer, AMENDED_BY_A9_15 (governing_reading = the "
                        "A9.15 bullet). Non-TBD v4 rows are copied unchanged. A9.7 lane questions are rows of kind "
                        "a9_7_lane_question. A row without an owner answer stays TBD_OWNER. A9.17 .. A9.21: a row a "
                        "later decision supersedes / amends / answers gets AMENDED_BY_A9_<n> / ANSWERED_BY_A9_21 with "
                        "pre_a9_17_status kept and later_owner_decisions + later_governing_reading; a row a later "
                        "decision only confirms, or whose external input stays TBD, keeps its status and gets the "
                        "records (external_input_status)."),
        "rfp_rule": L.RFP_PENDING_NOTE,
        "a9_15_governing_statement": L.a915_governing_statement(),
        "a9_15_scope_note": ("A9.15 concerns system propellant capability (ambient atmospheric propellant 180-230 km AND "
                             "Xenon, separate tanks / paths); it does not change the A9.1 ICP gas-mode baseline "
                             "(G-REUSE primary; G-XE a declared ICP-feed variant)"),
        "counts": dict(sorted(counts.items())),
        "tbd_owner_count": counts.get("TBD_OWNER", 0),
        "tbd_owner_blocks": dict(sorted(tbd_blocks.items())),
        "answered_this_step_by_decision": dict(sorted(by_dec.items(), key=lambda kv: L.ORDER.index(kv[0]))),
        "question_groups": v4["question_groups"],
        "superseded_statements": superseded_statements(),
        "superseded_statements_a9_19": later_superseded_statements(),
        "a9_17_21": {
            "decisions": [{"decision": k, "json": X.LOADED[k]["json"], "json_sha256": X.LOADED[k]["json_sha256"],
                           "md": X.LOADED[k]["md"], "md_sha256": X.LOADED[k]["md_sha256"]} for k in X.ORDER],
            "flight_configuration": X.FLIGHT_CONFIGURATION,
            "ground_reference": {X.GROUND_REFERENCE: X.C1_ROLE + " (A9.20): retired as a flight configuration "
                                 "(A9.19); quoted historical question / answer text keeps the name verbatim"},
            "xenon_role_a9_19": X.digest("A9.19", "xenon_role"),
            "rows_status_changed": later["amended"], "rows_answered": later["answered"],
            "rows_with_records_only": later["noted"],
            "records_by_decision_and_relation": {f"{d} {rel}": n for (d, rel), n in sorted(later_counts.items())},
            "relations": X.RELATIONS,
            "items_without_a_state_row": [
                "A9.17 DATA_SIZE, SPUTTER (data-artifact rules; no owner-question row)",
                "A9.18 GOLDEN (golden design point; no owner-question row)",
                "A9.21 H2_6 (H2-6 builder frozen, live-source check in CI; no owner-question row)",
                "A9.21 RFQ_DISPATCH (quotation packages finalized here; dispatch by owner / procurement)"],
            "owner_asked_recorder": "A9.20 verbatim also asks the recorder 'is it good to remove hollow cathode' - "
                                    "not an owner-question row; RP-A919-01 (ICP go / no-go) answers it on the "
                                    "recorder side and A9.21 ICP_GATE approves that gate's existence and placement",
            "open_parts": [{"id": NEW_ROW_ID, "what": "numerical GO / NO-GO criteria not approved (preserved for "
                                                     "owner review)"}]},
        "rfp_registration_now": rfp_registration_now(reg, rvm),
        "owner_answers_applied": applied + applied_later,
        "open_owner_questions": [r["id"] for r in rows if r["status"] == "TBD_OWNER"],
        "open_owner_questions_note": "TBD_OWNER rows: questions with no owner answer yet (raised since v4 or unanswered)",
        "compliance": ["every v4 row present; non-TBD_OWNER v4 rows copied unchanged except the A9.17 .. A9.21 "
                       "overlay (status / status_detail changed, earlier values kept in pre_a9_17_status[_detail], "
                       "later_owner_decisions / later_governing_reading / governing_reading_status / "
                       "external_input_status / rfp_registered_document added)",
                       "every answered row carries decision pointer, json sha256, verbatim md sha256 and a verbatim excerpt",
                       "A9.15 governs every 'Xe contingency-only for C1' reading; A9.19 governs the ROLE of Xe "
                       "(contingency / emergency supply mode; capability retained)",
                       "one flight configuration (hall_icp_neutralizer); C1 a ground-only laboratory reference (A9.20)",
                       "step-1 RFP-cited facts keep OWNER_STATED_PENDING_RFP_REGISTRATION as history (rfp_registration_"
                       "now records the registration); no PASS produced; no answer invented"],
        "rows": rows,
    }


def render_md(doc):
    cell = lambda s: " ".join(_flat(s).split()).replace("|", "\\|")
    rows = doc["rows"]
    out = ["# Owner questions — state v5", "",
           "State v4 plus the A9.7 lane questions, with the owner answers A9.8 .. A9.14 applied, the A9.15 "
           "RFP-compliant propellant policy amendments and the later owner decisions A9.17 .. A9.21 (generated by `"
           + doc["generated_by"] + "`; do not edit by hand).", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + f". **{doc['tbd_owner_count']} TBD_OWNER.**", "",
           "Answered in this step: " + ", ".join(f"{k} {v}" for k, v in doc["answered_this_step_by_decision"].items()) + ".", "",
           "RFP rule (A9.16 step-1 application rule, history; the RFP is now registered by hash - see 'RFP now' "
           "below): " + doc["rfp_rule"] + ".", "",
           "## A9.15 RFP-compliant propellant policy (governing)", "", "> " + doc["a9_15_governing_statement"], "",
           doc["a9_15_scope_note"] + ".", "",
           "| # | ID | A9.14 code | Governing reading (A9.15, verbatim) |", "|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r['decision_code']} | {cell(r['governing_reading']['text'])} |"
            for r in rows if r.get("amended_by", {}).get("decision") == "A9.15"]
    out += ["", "Rows amended by A9.15 and later by A9.19 / A9.20 / A9.21 carry status AMENDED_BY_A9_<n> (see the "
            "A9.17 .. A9.21 section); their A9.15 reading is kept above.", "", "Superseded statements:", ""]
    out += [f"- {s['id']}: \"{cell(s['text'])}\" -> superseded by A9.15 (`{s['superseded_by']['path']}`)"
            for s in doc["superseded_statements"]]
    lt = doc["a9_17_21"]
    reg = doc["rfp_registration_now"]
    out += ["", "## Later owner decisions A9.17 .. A9.21", "",
            f"Flight configuration: **{lt['flight_configuration']}** (one). Ground reference: "
            + "; ".join(f"`{k}` {v}" for k, v in lt["ground_reference"].items()) + ".", "",
            "Xe role (A9.19 digest): " + cell(lt["xenon_role_a9_19"]) + ".", "",
            "RFP now: " + cell(f"{reg['registration']['status']} (RFP {reg['registration']['rfp_number']}, sha256 "
                               f"{reg['registration']['pdf_sha256']}, {reg['registration']['pages']} pages, "
                               f"{reg['registration']['n_clauses']} clauses); RVM re-base "
                               f"{reg['rvm_rebase']['ag_15_status']}") + ".", "",
            "| # | ID | Earlier status | Status | Later decision records (relation: scope) |", "|---|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r.get('pre_a9_17_status', '-')} | {r['status']} | "
            + cell("; ".join(f"{x['decision']} {x['item']} {x['relation']}: {x['scope']}"
                             for x in r["later_owner_decisions"])) + " |"
            for r in rows if r.get("later_owner_decisions")]
    out += ["", "Open part: " + "; ".join(f"{o['id']}: {o['what']}" for o in lt["open_parts"]) + ".", "",
            "Items without a state row: " + "; ".join(lt["items_without_a_state_row"]) + ".", "",
            "Superseded by A9.19 (ROLE of Xe only):", ""]
    out += [f"- {s['id']}: \"{cell(s['text'])}\" -> superseded by A9.19 (`{s['superseded_by']['path']}`; "
            f"{cell(s['scope'])})" for s in doc["superseded_statements_a9_19"]]
    out += ["", "## TBD_OWNER (still open)", "", "| # | ID | Question | Blocks | Needed by |", "|---|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {cell(_clip(r['question'], 260))} | {cell(r['blocks'])} | {cell(r.get('needed_by'))} |"
            for r in rows if r["status"] == "TBD_OWNER"]
    for st in [s for s in doc["status_vocabulary"] if s.startswith("ANSWERED_BY_A9_") and s[-1:] != "_"]:
        sel = [r for r in rows if r["status"] == st and (r.get("v4_status") == "TBD_OWNER" or r.get("kind") == A97_KIND)]
        if not sel:
            continue
        out += ["", f"## {st} ({len(sel)})", "", "| # | ID | Seq | Decision code | Answer (verbatim, clipped) | RFP |",
                "|---|---|---|---|---|---|"]
        out += [f"| {r['no']} | {r['id']} | {r['sequenced_no']} | {r['decision_code']} | "
                f"{cell(_clip(r['answer_excerpt'], 320))} | {cell(r.get('rfp_citation_status') or '')} |" for r in sel]
    out += ["", "## A9.7 lane questions (rows added in v5)", "", "| # | ID | Lane | Status | Source |", "|---|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r['lane']} | {r['status']} | {cell(r['source'])} |" for r in rows
            if r.get("kind") == A97_KIND]
    out += ["", "## Owner answers applied", ""]
    out += [f"- **{a['id']}** `{a['decision_json']}` sha256 `{a['decision_json_sha256']}`: {a['how_applied']}"
            for a in doc["owner_answers_applied"]]
    out += ["", "## Pins", ""] + [f"- `{p['path']}` sha256 `{p['sha256']}`" for p in doc["pins"]]
    out += ["", "Verbatim answers are cut from the pinned .md records; the full text is in the JSON rows "
                "(`answer_excerpt`). No PASS, no winner, no answer invented."]
    return "\n".join(out) + "\n"


def render_csv(doc):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    cols = ["no", "id", "kind", "lane", "source", "v4_status", "status", "status_detail", "sequenced_no", "decision_code",
            "question", "dependency", "blocks", "answer_pointer", "answer_sha256", "answer_verbatim_path",
            "answer_verbatim_sha256", "answer_excerpt", "rfp_citation_status", "governing_reading", "application_status",
            "needed_by", "pre_a9_17_status", "later_owner_decisions", "external_input_status"]
    w.writerow(cols)
    for r in doc["rows"]:
        vals = []
        for c in cols:
            v = r.get(c)
            if c == "governing_reading" and v:
                v = v["text"]
            if c == "later_owner_decisions" and v:
                v = "; ".join(f"{x['decision']} {x['item']} {x['relation']} ({x['pointer']})" for x in v)
            vals.append(_flat(v))
        w.writerow(vals)
    return buf.getvalue()


def outputs(doc=None):
    doc = doc or build()
    return {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc), OUT_CSV: render_csv(doc)}


def main():
    outs = outputs()
    if "--check" in sys.argv:
        stale = [p.name for p, s in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"state v5 outputs stale: {stale}")
        print("owner-question state v5: current")
        return
    for p, s in outs.items():
        p.write_text(s, encoding="utf-8")
    print("wrote state v5: " + json.dumps(json.loads(outs[OUT_JSON])["counts"]))


if __name__ == "__main__":
    main()
