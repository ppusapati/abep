"""A9.16 step 1 (integration lane): owner decisions applied to the M16 v4 subsystem-maturity record.

  A9.14 M16-V3-Q-01 (S9.4)  the PROPOSED blocking-item / functional-role / decision-point mapping is ACCEPTED; named
                            persons come from the actual project staffing ledger before the corresponding work package
                            starts (none fabricated; the source has no staffing roster); functional-role ownership binds
                            meanwhile. READY still needs a named responsible engineer (R-M16V4-05), so no row becomes READY.
  A9.8 .. A9.15             every owner-question blocker cited from state v4 carries its state v5 status and decision
                            (overlay); the v4 blocker resolution is kept as the historical snapshot (state v4 immutable).
                            Re-deriving the scheduler blocking items from the owner answers is a follow-on (M16 v5).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "docs" / "decisions" / "application"))
import a9_16_lib as L  # noqa: E402

ARTIFACT = "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json"
TEST = "tests/test_m16_v4.py"
V4 = "docs/budgets/owner_decisions/owner_questions_state_v4.json"
V5 = "docs/budgets/owner_decisions/owner_questions_state_v5.json"
# owner-decided statuses in state v5: A9.8 .. A9.14 answers, the A9.15 amendments and the later A9.19 / A9.20 / A9.21
# amendments / answers (each carries later_owner_decisions records in state v5)
DECIDED_PREFIXES = ("ANSWERED_BY_A9_", "AMENDED_BY_A9_")


def v5_index(v5: dict) -> dict:
    out = {}
    for r in v5["rows"]:
        if r.get("v4_status") == "TBD_OWNER" or r.get("kind") == "a9_7_lane_question" or r["status"] == "TBD_OWNER":
            if r["id"] in out:
                raise ValueError(f"state v5: {r['id']} twice among answered / open rows")
            out[r["id"]] = r
    return out


def overlay_blockers(rows: list, idx: dict) -> list:
    answered = set()
    for r in rows:
        items = []
        bi = r.get("blocking_item") or {}
        items += bi.get("items", []) + bi.get("also_open", []) + bi.get("still_open_check", [])
        items += r.get("contributing_blockers", [])
        for b in items:
            if b.get("kind") != "OWNER_QUESTION":
                continue
            v = idx.get(b["id"])
            if v is None:
                raise ValueError(f"owner-question blocker {b['id']} missing from state v5")
            b["state_v5"] = v["status"]
            if v["status"] != "TBD_OWNER":
                b["decision"] = L.cite(b["id"])
                answered.add(b["id"])
            if v.get("later_owner_decisions"):
                b["later_owner_decisions"] = [f"{x['decision']} {x['item']} {x['relation']} ({x['decision_json']} "
                                              f"sha256 {x['decision_json_sha256']})" for x in v["later_owner_decisions"]]
    return sorted(answered)


def reconcile_reading(o: dict, v4: dict, idx5: dict) -> tuple:
    """An RVM reading agrees with the register it names: v4 (status equality) or v5 (OWNER_DECIDED <-> answered)."""
    reg = o.get("current_register")
    if reg == V5:
        r5 = idx5.get(o["id"])
        st = r5["status"] if r5 else None
        ok = st is not None and o["status"] == "OWNER_DECIDED" and st.startswith(DECIDED_PREFIXES)
        return ok, st, V5
    r4 = v4.get(o["id"])
    st = r4["status"] if r4 else None
    return (st is not None and st == o["status"]), st, V4


def apply_owner_role_map(rows: list) -> None:
    a = L.answer("M16-V3-Q-01")
    for r in rows:
        r["owner"]["owner_question"] = ("M16-V3-Q-01 (" + a["decision"] + " " + a["sequenced_no"] + " "
                                        + a["decision_code"] + ": role map accepted; named persons from the project "
                                        "staffing ledger before the work package starts)")
        if r.get("named_engineer") is None and r["owner"].get("named_engineer") is None:
            r["owner"]["named_engineer_status"] = "FROM_STAFFING_LEDGER_BEFORE_WORK_PACKAGE_START (none fabricated)"
        r["latest_decision_point_status"] = "OWNER_ACCEPTED (A9.14 M16-V3-Q-01; carried from v3)"


def owner_answers_applied() -> list:
    return [L.applied_row("M16-V3-Q-01", ARTIFACT, ["rows[*].owner", "rows[*].latest_decision_point_status",
                                                     "M16V4-ID-07"],
                          "role map / blocking items / decision points accepted; named persons only from the staffing "
                          "ledger (R-M16V4-05 unchanged: no READY without a named engineer)", [TEST])]
