"""A9.21 ICP_GATE carried in the F9 freeze-candidate gate machinery (pre-LOCK-1 gates; own ids, not AG-01 .. AG-15).

The gate is registered in the RVM (docs/requirements/rvm_a9/rvm_a9_v1.json owner_approved_gates, built by
docs/requirements/rvm_a9/a9_21_icp_gate.py). F9 reads that record, checks it against the shared definition (same id,
owner approval, placement, criteria status, verbatim proposal text) and RE-EVALUATES it with the same fail-closed
evaluator: status NOT_EVALUATED until owner-accepted criteria and registered evidence exist; never GO without evidence.
The recorder proposal RP-A919-01 (a) - (c) is carried verbatim in 'proposed_criteria_for_owner_review' and never
evaluated. LOCK-1 cannot be reported released while any mandatory pre-LOCK-1 gate is not GO (lock1_precondition), and
the architecture status cannot become a frozen reference while it is not GO.

AG-01 .. AG-15 keep their numbering and their owner approval (A9.13 S6.22 F9-OQ-03 covers exactly those 15); this gate's
approval is A9.21 ICP_GATE. No PASS; no value or criterion invented. stdlib only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_RVM_DIR = str(ROOT / "docs" / "requirements" / "rvm_a9")
if _RVM_DIR not in sys.path:
    sys.path.insert(0, _RVM_DIR)
import a9_21_icp_gate as G  # noqa: E402  (shared gate definition + evaluator)

ARTIFACT = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
TESTS = ["tests/test_icp_gate_a9_21.py", "tests/test_architecture_freeze_candidate.py"]
_CHECKED = ("id", "mandatory", "placement", "precedes", "criteria", "owner_approved", "proposed_criteria_for_owner_review")


def pins() -> dict:
    d = G.X.LOADED[G.DECISION_KEY]
    return {"A921": (d["json"], d["json_sha256"]), "A921_MD": (d["md"], d["md_sha256"])}


def pre_lock1_gates(rvm_gates: list, ref) -> list:
    """F9 records of the owner-approved pre-LOCK-1 gates, re-evaluated from the RVM registration (fail closed)."""
    hits = [(i, g) for i, g in enumerate(rvm_gates or []) if g.get("id") == G.GATE_ID]
    if len(hits) != 1:
        raise SystemExit(f"REFUSED: {G.GATE_ID} not registered exactly once in the RVM owner_approved_gates")
    i, rg = hits[0]
    expect = G.gate_record()
    bad = [k for k in _CHECKED if rg.get(k) != expect[k]]
    if bad:
        raise SystemExit(f"REFUSED: {G.GATE_ID}: RVM registration differs from the shared definition in {bad}")
    ev = G.evaluate(rg["criteria"] if isinstance(rg["criteria"], dict) else None, rg.get("evidence") or [])
    if ev["status"] != rg["status"]:
        raise SystemExit(f"REFUSED: {G.GATE_ID}: RVM status {rg['status']} != re-evaluated {ev['status']}")
    oa = rg["owner_approved"]
    return [{
        "id": G.GATE_ID, "gate": rg["gate"], "kind": "OWNER_APPROVED_PRE_LOCK1_GATE",
        "mandatory": True, "placement": rg["placement"], "precedes": rg["precedes"],
        "current_status": ev["status"], "status_reason": ev["reason"],
        "evidence_sufficient_for_freeze": ev["status"] == G.GO,
        "criteria": rg["criteria"], "evidence": list(rg.get("evidence") or []),
        "fail_closed_rule": rg["fail_closed_rule"],
        "proposed_criteria_for_owner_review": rg["proposed_criteria_for_owner_review"],
        "owner_approved": {"decision": G.X.cite(G.DECISION_KEY, G.DECISION_ITEM), "decision_code": oa["decision_code"],
                           "approved_scope": oa["approved_scope"], "verbatim_excerpt": oa["verbatim_excerpt"]},
        "not_in_ag_series": rg["not_in_ag_series"],
        "evaluator": rg["evaluator"] + " (re-evaluated here from the RVM record)",
        "sources": [ref("RVM", f"/owner_approved_gates/{i}"),
                    {"path": oa["decision_json"], "pointer": f"/decisions/{G.DECISION_ITEM}",
                     "sha256": oa["decision_json_sha256"], "pinned": True,
                     "note": f"A9.21 ICP_GATE (verbatim {oa['decision_md']} sha256 {oa['decision_md_sha256']})"}],
    }]


def lock1_precondition(gates: list) -> dict:
    ok = G.lock1_release_reportable([{"status": g["current_status"], "mandatory": g["mandatory"]} for g in gates])
    return {"lock1_release_reportable": ok,
            "mandatory_pre_lock1_gates": [{"id": g["id"], "status": g["current_status"]} for g in gates],
            "rule": "LOCK-1 cannot be reported released while any mandatory pre-LOCK-1 gate is not GO (A9.21 ICP_GATE: "
                    "fail closed; missing evidence -> NOT_EVALUATED, never GO)",
            "evaluator": "docs/requirements/rvm_a9/a9_21_icp_gate.py:lock1_release_reportable"}


def owner_answers_applied() -> list:
    d = G.X.LOADED[G.DECISION_KEY]
    return [{"decision": G.DECISION_KEY, "question_id": G.DECISION_ITEM, "decision_code": G.DECISION_CODE,
             "decision_json": d["json"], "decision_json_sha256": d["json_sha256"], "decision_md": d["md"],
             "decision_md_sha256": d["md_sha256"], "artifact": ARTIFACT,
             "record_ids": ["pre_lock1_gates[id=" + G.GATE_ID + "]", "lock1_precondition", "architecture_status"],
             "how_applied": "mandatory ICP go / no-go gate " + G.GATE_ID + " carried as a pre-LOCK-1 gate (own id; "
                            "AG-01 .. AG-15 unchanged), re-evaluated from the RVM registration: NOT_EVALUATED, criteria "
                            "PENDING_OWNER_ACCEPTANCE, recorder proposal RP-A919-01 preserved for owner review (never "
                            "evaluated); LOCK-1 release not reportable while it is not GO",
             "tests": list(TESTS)}]
