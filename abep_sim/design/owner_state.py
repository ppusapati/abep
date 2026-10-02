"""Owner-question answer state for the design-synthesis lane records (review finding RVF-02).

The F-lane builders raised owner questions (F1Q-*, F2-OQ-*, OQ-F3-*, ...) as TBD_OWNER. The owner has since answered
them (A9.9, A9.13; recorded in docs/budgets/owner_decisions/owner_questions_state_v5.json). A regenerated lane record
must print each question's current answered status and decision code instead of the as-raised TBD_OWNER, and keep the
as-raised status as history. This module reads the v5 state read-only; it never fabricates an answer: an id absent
from v5, or present only as TBD_OWNER, stays TBD_OWNER.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OQ5_REL = "docs/budgets/owner_decisions/owner_questions_state_v5.json"
TBD_OWNER = "TBD_OWNER"
_CODE = re.compile(r"decision code ([A-Z0-9_]+)")
_DEC = re.compile(r"\((A9\.\d+ S[\d.]+)")


@lru_cache(maxsize=4)
def _rows(repo: str) -> dict:
    doc = json.loads((Path(repo) / OQ5_REL).read_text())
    out: dict[str, dict] = {}
    for r in doc["rows"]:
        prev = out.get(r["id"])
        # an answered row wins over a TBD_OWNER row of the same id (split questions carry both)
        if prev is None or (prev["status"] == TBD_OWNER and r["status"] != TBD_OWNER):
            out[r["id"]] = r
    return out


def owner_state(qid: str, repo: Path = REPO) -> dict:
    """{id, status, answered, decision, decision_code, status_detail, source} for one owner question."""
    r = _rows(str(repo)).get(qid)
    if r is None or r["status"] == TBD_OWNER:
        return {"id": qid, "status": TBD_OWNER, "answered": False, "decision": None, "decision_code": None,
                "status_detail": TBD_OWNER if r is None else r.get("status_detail", TBD_OWNER),
                "source": f"{OQ5_REL} rows[id={qid}]" + ("" if r is not None else " (absent)")}
    detail = r.get("status_detail") or r["status"]
    code = _CODE.search(detail)
    dec = _DEC.search(detail)
    return {"id": qid, "status": r["status"], "answered": True, "decision": dec.group(1) if dec else None,
            "decision_code": code.group(1) if code else None, "status_detail": detail,
            "source": f"{OQ5_REL} rows[id={qid}]"}


def status_label(qid: str, repo: Path = REPO) -> str:
    """Short label for record text: 'ANSWERED A9.13 S6.4 CATALYTIC_NOT_BASELINE' or 'TBD_OWNER'."""
    s = owner_state(qid, repo)
    if not s["answered"]:
        return TBD_OWNER
    return " ".join(x for x in ("ANSWERED", s["decision"], s["decision_code"]) if x)


def apply_to_questions(questions: list[dict], repo: Path = REPO) -> list[dict]:
    """Lane open-question list with the as-raised status kept as history and the current v5 state applied."""
    out = []
    for q in questions:
        s = owner_state(q["id"], repo)
        out.append({**q, "status_as_raised": q.get("status", TBD_OWNER), "status": s["status_detail"]
                    if s["answered"] else TBD_OWNER, "owner_decision": s["decision"],
                    "decision_code": s["decision_code"], "owner_state_source": s["source"]})
    return out
