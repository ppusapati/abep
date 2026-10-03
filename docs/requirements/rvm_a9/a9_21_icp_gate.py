"""A9.21 ICP_GATE: the mandatory ICP go / no-go gate before LOCK-1 (owner-approved gate; criteria not approved).

Owner decision A9.21 item 4 (docs/decisions/OD_2026_10_02_A9_21_*; the verbatim .md governs):
    "I approve the existence and placement of a mandatory ICP go/no-go gate before LOCK-1. I would not yet approve any
    numerical criterion that I cannot see in the proposal text. The gate must be fail-closed: if its required evidence
    is missing, the result is `NOT_EVALUATED`, not GO."  Decision: `ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1`.
    "The exact proposed GO/NO-GO criteria should be preserved separately until their text is available for review."

What this module defines (shared by the RVM builder, which registers the gate, and the F9 freeze candidate, which carries
it in its gate machinery and re-evaluates it from the RVM record):
  * GATE_ID 'GNG-ICP-01' - its own id. It is NOT one of AG-01 .. AG-15: their owner approval (A9.13 S6.22 F9-OQ-03,
    AG_01_15_APPROVED_DETERMINING_EVIDENCE) covers exactly those 15 gates; this gate's approval is A9.21 ICP_GATE;
  * placement: before LOCK-1, mandatory; LOCK-1 cannot be reported released while the gate is not GO;
  * criteria: PENDING_OWNER_ACCEPTANCE (no numerical or other GO / NO-GO criterion is approved);
  * proposed_criteria_for_owner_review: the recorder proposal RP-A919-01 (a) - (c), copied verbatim from the A9.19 RVM
    application record (a9_19_rvm.RECORDER_PROPOSALS); it is NEVER evaluated and never used as criteria;
  * evaluate(): fail closed - NOT_EVALUATED unless owner-accepted criteria (an owner decision citation with sha256, not
    the recorder proposal) AND a registered evidence record for every criterion exist; GO only when every criterion
    is MET on registered evidence, NO_GO when any is NOT_MET.

Nothing here invents a value or a criterion; no status is PASS; stdlib only; deterministic.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_APP = str(ROOT / "docs" / "decisions" / "application")
if _APP not in sys.path:
    sys.path.insert(0, _APP)
import a9_later_lib as X  # noqa: E402  (A9.17 .. A9.21 pins; json + verbatim md sha256)

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import a9_19_rvm as A19  # noqa: E402  (the recorder proposal RP-A919-01, A9.19 application record)

GATE_ID = "GNG-ICP-01"
DECISION_KEY, DECISION_ITEM = "A9.21", "ICP_GATE"
DECISION_CODE = "ICP_GO_NO_GO_REQUIRED_BEFORE_LOCK1"
PROPOSAL_ID = "RP-A919-01"
PLACEMENT = "BEFORE_LOCK-1"
LOCK = "LOCK-1"

GO, NO_GO, NOT_EVALUATED = "GO", "NO_GO", "NOT_EVALUATED"
STATUSES = (NOT_EVALUATED, GO, NO_GO)
CRITERIA_PENDING = "PENDING_OWNER_ACCEPTANCE"
CRITERIA_ACCEPTED = "OWNER_ACCEPTED"
PROPOSAL_STATUS = "NOT_APPROVED_PRESERVED_FOR_OWNER_REVIEW"
RESULTS = ("MET", "NOT_MET")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

# verbatim owner text (checked against the pinned .md through a9_later_lib.verbatim; the .md governs)
VERBATIM = {
    "approval": "I approve the existence and placement of a mandatory ICP go/no-go gate before LOCK-1.",
    "no_numbers": "I would not yet approve any numerical criterion that I cannot see in the proposal text.",
    "fail_closed": "The gate must be fail-closed: if its required evidence is missing, the result is `NOT_EVALUATED`, "
                   "not GO.",
    "preserve": "The exact proposed GO/NO-GO criteria should be preserved separately until their text is available for "
                "review.",
}
EXCERPT_START = "4. ICP go/no-go"


class IcpGateError(RuntimeError):
    pass


def _norm(s: str) -> str:
    return " ".join(str(s).split())


def owner_approval() -> dict:
    """The A9.21 ICP_GATE record (pointer + json / md sha256 + verbatim excerpt); fails closed on any change."""
    for tok in VERBATIM.values():
        X.verbatim(DECISION_KEY, tok)
    code = X.decision_code(DECISION_KEY, DECISION_ITEM)
    if code != DECISION_CODE:
        raise IcpGateError(f"A9.21 ICP_GATE decision code {code!r} != {DECISION_CODE!r}")
    d = X.LOADED[DECISION_KEY]
    return {"decision": DECISION_KEY, "item": DECISION_ITEM, "decision_code": code,
            "pointer": X.pointer(DECISION_KEY, DECISION_ITEM), "decision_json": d["json"],
            "decision_json_sha256": d["json_sha256"], "decision_md": d["md"], "decision_md_sha256": d["md_sha256"],
            "verbatim_excerpt": X.block(DECISION_KEY, EXCERPT_START, extra=1),
            "recorder_digest": X.digest(DECISION_KEY, DECISION_ITEM),
            "approved_scope": "EXISTENCE_AND_PLACEMENT_ONLY (no numerical criterion approved)"}


def proposal() -> dict:
    """The recorder proposal RP-A919-01 as recorded in the A9.19 RVM application (exactly one, not a decision)."""
    ps = [p for p in A19.RECORDER_PROPOSALS if p["id"] == PROPOSAL_ID]
    if len(ps) != 1 or ps[0].get("is_owner_decision") is not False or ps[0].get("is_requirement") is not False:
        raise IcpGateError(f"{PROPOSAL_ID}: recorder proposal not found exactly once as a non-decision / non-requirement")
    return ps[0]


def proposed_criteria_for_owner_review() -> dict:
    p = proposal()
    return {"source_proposal": PROPOSAL_ID,
            "source": "docs/requirements/rvm_a9/rvm_a9_v1.json recorder_proposals_open_for_owner[id=" + PROPOSAL_ID
                      + "] (a9_19_rvm.RECORDER_PROPOSALS)",
            "text_verbatim": p["proposal"], "numbers_as_recorded": p["numbers"],
            "status": PROPOSAL_STATUS, "is_criteria": False, "evaluated": False,
            "rule": "preserved verbatim for the owner's review (A9.21: 'preserved separately until their text is "
                    "available for review'); never evaluated, never used as GO / NO-GO criteria; only an owner "
                    "decision can supply criteria"}


def _uses_proposal(criteria: dict) -> bool:
    text = _norm(str(criteria)).lower()
    prop = _norm(proposal()["proposal"]).lower()
    if PROPOSAL_ID.lower() in text or "recorder_proposal" in text or "recorder proposal" in text:
        return True
    items = criteria.get("items") or []
    return any(_norm(i.get("text", "")).lower() and _norm(i.get("text", "")).lower() in prop for i in items
               if isinstance(i, dict))


def evaluate(criteria, evidence) -> dict:
    """Fail-closed evaluation of GNG-ICP-01. Returns {'status', 'reason', ...}; never GO without evidence.

    criteria: None / the string PENDING_OWNER_ACCEPTANCE (today), or an owner-accepted record
              {'status': 'OWNER_ACCEPTED', 'owner_decision': {'path', 'sha256'}, 'items': [{'id', 'text'}, ...]}.
    evidence: list of {'criterion_id', 'result': 'MET' | 'NOT_MET', 'source': {'path', 'sha256'}}.
    """
    if not isinstance(criteria, dict) or criteria.get("status") != CRITERIA_ACCEPTED:
        return {"status": NOT_EVALUATED, "reason": "no owner-accepted GO / NO-GO criterion (criteria "
                                                   + CRITERIA_PENDING + "); fail closed (A9.21)"}
    if _uses_proposal(criteria):
        return {"status": NOT_EVALUATED, "reason": "the recorder proposal " + PROPOSAL_ID + " is preserved for owner "
                                                   "review only and is never GO / NO-GO criteria"}
    dec = criteria.get("owner_decision") or {}
    if not dec.get("path") or not _HEX64.match(str(dec.get("sha256", ""))):
        return {"status": NOT_EVALUATED, "reason": "criteria carry no owner decision citation (path + sha256)"}
    items = criteria.get("items") or []
    ids = [i.get("id") for i in items if isinstance(i, dict)]
    if not ids or len(ids) != len(items) or any(not i for i in ids) or len(set(ids)) != len(ids):
        return {"status": NOT_EVALUATED, "reason": "owner-accepted criteria list empty or ids missing / not unique"}
    by = {}
    for e in evidence or []:
        if not isinstance(e, dict):
            continue
        src = e.get("source") or {}
        if e.get("result") in RESULTS and src.get("path") and _HEX64.match(str(src.get("sha256", ""))):
            by.setdefault(e.get("criterion_id"), []).append(e["result"])
    missing = [i for i in ids if not by.get(i)]
    if missing:
        return {"status": NOT_EVALUATED, "reason": "registered evidence missing for criteria " + ", ".join(missing),
                "missing": missing}
    failed = [i for i in ids if "NOT_MET" in by[i]]
    if failed:
        return {"status": NO_GO, "reason": "criteria not met: " + ", ".join(failed), "not_met": failed}
    return {"status": GO, "reason": "every owner-accepted criterion MET on registered evidence"}


def lock1_release_reportable(gates) -> bool:
    """LOCK-1 may be reported released only when every mandatory pre-LOCK-1 gate is GO (fail closed)."""
    gates = list(gates or [])
    return bool(gates) and all(g.get("status") == GO for g in gates if g.get("mandatory", True))


def gate_record() -> dict:
    """The registered gate (status from evaluate(): NOT_EVALUATED today - no accepted criteria, no evidence)."""
    ev = evaluate(CRITERIA_PENDING, [])
    if ev["status"] != NOT_EVALUATED:
        raise IcpGateError("GNG-ICP-01 evaluated to " + ev["status"] + " without owner-accepted criteria")
    rec = {
        "id": GATE_ID,
        "gate": "ICP go / no-go (mandatory, before LOCK-1) for the single Hall + RF/ICP neutralizer flight "
                "architecture (A9.19: no hollow-cathode fallback)",
        "owner_approved": owner_approval(),
        "mandatory": True,
        "placement": PLACEMENT, "precedes": LOCK,
        "status": ev["status"], "status_reason": ev["reason"],
        "status_vocabulary": list(STATUSES),
        "fail_closed_rule": "missing required evidence -> NOT_EVALUATED, never GO (A9.21); GO only when every "
                            "owner-accepted criterion is MET on registered evidence",
        "criteria": CRITERIA_PENDING,
        "criteria_note": "no GO / NO-GO criterion is approved (A9.21: 'I would not yet approve any numerical criterion "
                         "that I cannot see in the proposal text'); the evaluator refuses the recorder proposal as "
                         "criteria",
        "evidence": [],
        "proposed_criteria_for_owner_review": proposed_criteria_for_owner_review(),
        "lock1_release_reportable": lock1_release_reportable([{"status": ev["status"], "mandatory": True}]),
        "lock1_rule": "LOCK-1 cannot be reported released while this gate is not GO",
        "not_in_ag_series": "own id; not one of AG-01 .. AG-15 (their owner approval A9.13 S6.22 F9-OQ-03 covers only "
                            "those 15 gates); approved by A9.21 ICP_GATE",
        "evaluator": "docs/requirements/rvm_a9/a9_21_icp_gate.py:evaluate (fail closed)",
        "related_rvm_rows": list(proposal()["related_rows"]),
    }
    if rec["lock1_release_reportable"]:
        raise IcpGateError("LOCK-1 reported releasable while GNG-ICP-01 is not GO")
    return rec


# ------------------------------------------------------------------------------------------------ RVM application
RVM_ARTIFACT = "docs/requirements/rvm_a9/rvm_a9_v1.json"
RVM_TEST = "tests/test_rvm_a9.py"


def apply_rvm(doc: dict) -> dict:
    """Register GNG-ICP-01 in the RVM (owner_approved_gates) and record the A9.21 disposition on RP-A919-01.

    The recorder proposal entry stays as recorded by the A9.19 application (its criteria are still open for the owner);
    it gains an 'a9_21_disposition' record only. No RVM row, limit or status changes (the gate is not a requirement row;
    the RFP registration's rvm_mapping is built from the rows and is unaffected)."""
    props = [p for p in doc.get("recorder_proposals_open_for_owner", []) if p["id"] == PROPOSAL_ID]
    if len(props) != 1:
        raise IcpGateError(f"{PROPOSAL_ID} not found exactly once in recorder_proposals_open_for_owner")
    gate = gate_record()
    if _norm(props[0]["proposal"]) != _norm(gate["proposed_criteria_for_owner_review"]["text_verbatim"]):
        raise IcpGateError(f"{PROPOSAL_ID}: preserved text differs from the RVM recorder proposal")
    doc["owner_approved_gates"] = [gate]
    props[0]["a9_21_disposition"] = {
        "decision": X.cite(DECISION_KEY, DECISION_ITEM), "decision_code": DECISION_CODE,
        "gate_part": "APPROVED_BY_OWNER: gate existence and placement (mandatory, before LOCK-1, fail closed); "
                     "registered as " + GATE_ID + " (owner_approved_gates[id=" + GATE_ID + "])",
        "criteria_part": PROPOSAL_STATUS + ": criteria (a) - (c) not approved; preserved verbatim in "
                         "owner_approved_gates[id=" + GATE_ID + "].proposed_criteria_for_owner_review (never "
                         "evaluated)",
        "registered_gate": GATE_ID, "criteria_status": CRITERIA_PENDING,
        "handling_after_a9_21": "the gate is registered (status NOT_EVALUATED); the proposal text is not a criterion; "
                                "the 'handling' field above is the A9.19 record (history)"}
    d = X.LOADED[DECISION_KEY]
    doc["a9_21_owner_answers_applied"] = [{
        "decision": DECISION_KEY, "question_id": DECISION_ITEM, "decision_code": DECISION_CODE,
        "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
        "decision_md_sha256": d["md_sha256"], "artifact": RVM_ARTIFACT,
        "record_ids": ["owner_approved_gates[id=" + GATE_ID + "]", "recorder_proposals_open_for_owner[id="
                       + PROPOSAL_ID + "].a9_21_disposition"],
        "how_applied": "mandatory ICP go / no-go gate " + GATE_ID + " registered before LOCK-1 (own id, not AG-01 .. "
                       "AG-15); status NOT_EVALUATED (fail closed), criteria PENDING_OWNER_ACCEPTANCE; the recorder "
                       "proposal " + PROPOSAL_ID + " (a) - (c) preserved verbatim for owner review, never evaluated",
        "tests": [RVM_TEST, "tests/test_icp_gate_a9_21.py"]}]
    return doc
