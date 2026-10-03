"""F9 RFP citations re-based onto the registered RFP clauses (A9.17 RFP registration + RVM re-base; F9-specific).

The A9.16 step-1 application stamped every F9 record that carries an owner answer citing the RFP ('RFP(1)' in the
verbatim answer) with rfp_citation_status = OWNER_STATED_PENDING_RFP_REGISTRATION (a9_16_lib.answer). The official RFP
is now registered by sha256 with a verbatim clause transcription (docs/requirements/rfp_official/rfp_registration_v1.json)
and the RVM is re-based on it (rvm_a9_v1.json rfp_rebase: every RVM row cites the clause ids it derives from).

This module maps each such F9 record to registered clause ids EXACTLY as the RVM re-base maps the corresponding
requirement: the clause ids are the 'rfp_clauses' of the corresponding RVM row(s), read from the RVM at build time
(never typed here). The correspondence F9 record -> RVM row is itself checked against the artifacts (fail closed):
  RVM_REBASE_DECISION   the RVM row's rfp_rebase.decisions cite the same owner question id
  RVM_A9_16_DECISION    the RVM row's a9_16 record cites the same owner question id
  RVM_A9_15_APPLIED     the RVM a9_16_owner_answers_applied A9.15 governing-rule entry names the RVM row
  VERBATIM_FACT         the RFP fact quoted in the owner's verbatim answer occurs in the RVM row's title / requirement
  PARAMETER_FACT        the parameter's quantity occurs in the RVM row's requirement text
  F9_SOURCE_POINTER     the F9 parameter's own source points at the RVM row
A record with no registered correspondence keeps an explicit UNMAPPED_NO_RVM_MAPPED_CLAUSE status with the reason (never
a guessed clause). The step-1 label is kept as rfp_citation_status_as_applied (history), as the RVM does
(a9_16_rvm.registered_rfp_citations). AG-15 is closed by the owner (A9.22 G3): requirement_frozen = true on the RVM
RFP_CLAUSE rows (requirement basis only; no status change, no compliance claim).

Kept out of docs/decisions/application/a9_16_lib.py on purpose: that lib feeds the pins of many builders; this mapping
only re-labels F9 records. stdlib only; deterministic.
"""
from __future__ import annotations

import json

REGISTERED = "REGISTERED_CLAUSE"
UNMAPPED = "UNMAPPED_NO_RVM_MAPPED_CLAUSE"
REGISTRATION_PATH = "docs/requirements/rfp_official/rfp_registration_v1.json"
# the F9 record -> RVM row table (CORRESPONDENCE) is the recorder's, checked against the artifacts; it is not an owner
# mapping and not part of the RVM re-base (review 2026-10-03, evidence discipline)
CORRESPONDENCE_STATUS = "RECORDER_READING_OWNER_MAY_REVERSE"
RVM_PATH = "docs/requirements/rvm_a9/rvm_a9_v1.json"
A915 = "A9.15 governing_rule"

# (F9 record id, owner question id | None) -> [(RVM row, correspondence kind, F9 / owner token, RVM token)]
CORRESPONDENCE = {
    ("AFC-SY-PPU-07", "RVMQ-01"): [("RVM-19", "RVM_REBASE_DECISION", None, None)],
    ("AFC-SY-PPU-07", "OD12"): [("RVM-19", "RVM_REBASE_DECISION", None, None)],
    ("AFC-SY-XE-01", "XA9Q-07"): [("RVM-10", "RVM_A9_16_DECISION", None, None)],
    ("AFC-SY-XE-01", "OD6"): [("RVM-10", "RVM_A9_16_DECISION", None, None)],
    ("AFC-SY-XE-01", A915): [("RVM-10", "RVM_A9_15_APPLIED", None, None)],
    ("AFC-UP-FI-01", "F2-OQ-01"): [("RVM-09", "VERBATIM_FACT", "N2 and nascent/atomic oxygen",
                                    "N2 and nascent (atomic) O")],
    ("AFC-UP-FI-01", "F2-OQ-03"): [("RVM-08", "VERBATIM_FACT", "intake → filter → compressor",
                                    "intake -> filter -> compressor")],
    ("AG-12", "F9-OQ-02"): [("RVM-01", "VERBATIM_FACT", "180–230 km", "180-230 km"),
                            ("RVM-02", "VERBATIM_FACT", "12–25 mN", "12-25 mN")],
    # REQUIREMENT_AS_RECORDED parameters (no owner question; the label itself cites the RFP)
    ("AFC-SY-PWR-01", None): [("RVM-04", "PARAMETER_FACT", "P_bus,1ms,max", "P_bus,1ms,max")],
    ("AFC-SY-MASS-WET", None): [("RVM-06", "F9_SOURCE_POINTER", None, None)],
}
# F9 questions carrying the label -> the F9 record their owner answer applies to
QUESTION_RECORD = {"F9-OQ-02": "AG-12"}
# stale A9.16 step-1 wording on the two parameters whose a9_16 record carried the label (exact text; fail closed)
STALE_TEXT = {
    "AFC-SY-PPU-07": [("basis", "RFP clause owner-stated, pending registration (AG-15)",
                       "RFP clause registered ({clauses}; via {rows}, RVM re-base; AG-15 closed by the owner, A9.22 G3)")],
    "AFC-SY-XE-01": [("basis", "RFP content owner-stated, pending registration (AG-15)",
                      "RFP content registered ({clauses}; via {rows}, RVM re-base; AG-15 closed by the owner, A9.22 G3)")],
}
STALE_ADVANCE = {"AFC-SY-PPU-07": ("official RFP registered (AG-15)",
                                   "AG-15 closed by the owner (A9.22 G3: the official RFP is registered by hash, the "
                                   "RVM re-based and the requirement basis frozen; RVM-19 itself stays NOT_EVALUATED)")}


class RfpCitationError(SystemExit):
    pass


def _norm(s) -> str:
    return " ".join(str(s).split())


def _verify(kind: str, rid: str, row: dict, rvm: dict, qid, tok_f9, tok_rvm, answer_text, param) -> str:
    """Return the evidence string of one correspondence, or raise (fail closed)."""
    if kind == "RVM_REBASE_DECISION":
        txt = " ".join((row.get("rfp_rebase") or {}).get("decisions") or [])
        if f" {qid} (" not in txt:
            raise RfpCitationError(f"{rid}: rfp_rebase.decisions do not cite {qid}")
        return f"{RVM_PATH} {rid} rfp_rebase.decisions cite {qid}"
    if kind == "RVM_A9_16_DECISION":
        txt = " ".join((row.get("a9_16") or {}).get("decisions") or [])
        if f" {qid} (" not in txt:
            raise RfpCitationError(f"{rid}: a9_16.decisions do not cite {qid}")
        return f"{RVM_PATH} {rid} a9_16.decisions cite {qid}"
    if kind == "RVM_A9_15_APPLIED":
        hits = [a for a in rvm.get("a9_16_owner_answers_applied") or []
                if a.get("question_id") == A915 and rid in (a.get("record_ids") or [])]
        if len(hits) != 1:
            raise RfpCitationError(f"{rid}: no A9.15 governing-rule application on the RVM row")
        return f"{RVM_PATH} a9_16_owner_answers_applied ({A915}) names {rid}"
    if kind == "VERBATIM_FACT":
        if _norm(tok_f9) not in _norm(answer_text):
            raise RfpCitationError(f"{qid}: RFP fact {tok_f9!r} not in the owner's verbatim answer")
        if _norm(tok_rvm) not in _norm(row["title"] + " " + row["requirement_text"]):
            raise RfpCitationError(f"{rid}: {tok_rvm!r} not in the RVM row title / requirement text")
        return f"owner verbatim '{tok_f9}' ({qid}) = {RVM_PATH} {rid} '{tok_rvm}'"
    if kind == "PARAMETER_FACT":
        if param is None or _norm(tok_f9) not in _norm(param["name"]):
            raise RfpCitationError(f"{rid}: {tok_f9!r} not in the F9 parameter name")
        if _norm(tok_rvm) not in _norm(row["requirement_text"]):
            raise RfpCitationError(f"{rid}: {tok_rvm!r} not in the RVM requirement text")
        return f"F9 parameter '{tok_f9}' = {RVM_PATH} {rid} requirement '{tok_rvm}'"
    if kind == "F9_SOURCE_POINTER":
        rows = rvm["rows"]
        ptrs = [s.get("pointer", "") for s in (param or {}).get("source", [])
                if isinstance(s, dict) and s.get("path") == RVM_PATH and s.get("pointer", "").startswith("/rows/")]
        ok = [p for p in ptrs if p.split("/")[2].isdigit() and int(p.split("/")[2]) < len(rows)
              and rows[int(p.split("/")[2])]["id"] == rid]
        if not ok:
            raise RfpCitationError(f"{rid}: the F9 parameter source does not point at the RVM row")
        return f"F9 source {RVM_PATH}{ok[0]} = {rid}"
    raise RfpCitationError(f"unknown correspondence kind {kind}")


def mapping(record_id: str, qid, rvm: dict, answer, param=None) -> dict:
    """Clause ids for one (F9 record, owner question): the rfp_clauses of the corresponding RVM row(s)."""
    corr = CORRESPONDENCE.get((record_id, qid))
    if not corr:
        return {"status": UNMAPPED, "reason": f"no RVM row is registered as the requirement {record_id}"
                                              + (f" / {qid}" if qid else "") + " cites; the RVM re-base maps no clause "
                                              "to it (no clause is guessed)"}
    by = {r["id"]: r for r in rvm["rows"]}
    clauses, rows, ev = [], [], []
    for rid, kind, tf, tr in corr:
        row = by.get(rid)
        if row is None:
            raise RfpCitationError(f"{record_id}: RVM row {rid} missing")
        if row.get("requirement_origin") != "RFP_CLAUSE" or not row.get("rfp_clauses"):
            return {"status": UNMAPPED, "reason": f"{rid} is {row.get('requirement_origin')} with no rfp_clauses in "
                                                  "the RVM re-base"}
        text = answer(qid)["verbatim_excerpt"] if kind == "VERBATIM_FACT" else None
        ev.append({"rvm_row": rid, "kind": kind, "evidence": _verify(kind, rid, row, rvm, qid, tf, tr, text, param)})
        rows.append(rid)
        clauses += [c for c in row["rfp_clauses"] if c not in clauses]
    return {"status": REGISTERED, "clauses": clauses, "rows": rows, "correspondence": ev}


def _merge(ms: list) -> dict:
    reg = [m for m in ms if m["status"] == REGISTERED]
    if not reg:
        return ms[0] if ms else {"status": UNMAPPED, "reason": "no owner question mapped"}
    out = {"status": REGISTERED, "clauses": [], "rows": [], "correspondence": []}
    for m in reg:
        out["clauses"] += [c for c in m["clauses"] if c not in out["clauses"]]
        out["rows"] += [r for r in m["rows"] if r not in out["rows"]]
        out["correspondence"] += m["correspondence"]
    # review 2026-10-03: a partly mapped record keeps the reasons of its unmapped questions (never silently dropped)
    unmapped = [m["reason"] for m in ms if m["status"] != REGISTERED]
    if unmapped:
        out["unmapped_reasons"] = unmapped
    return out


def _relabel(rec: dict, m: dict, pending) -> None:
    if pending is not None:
        rec["rfp_citation_status_as_applied"] = pending
    rec["rfp_citation_status"] = m["status"]
    if m["status"] == REGISTERED:
        rec["rfp_clause_ids"] = list(m["clauses"])
        rec["rfp_rvm_rows"] = list(m["rows"])
        rec["rfp_correspondence"] = list(m["correspondence"])
        rec["rfp_citation_note"] = ("registered clause(s) " + ", ".join(m["clauses"]) + " (" + REGISTRATION_PATH
                                    + "), the rfp_clauses the RVM re-base maps for " + ", ".join(m["rows"])
                                    + "; the record -> RVM row correspondence is a " + CORRESPONDENCE_STATUS
                                    + " (" + ", ".join(sorted({c["kind"] for c in m["correspondence"]}))
                                    + "); AG-15 closed by the owner (A9.22 G3): RFP_CLAUSE rows frozen, basis only")
        rec["rfp_correspondence_status"] = CORRESPONDENCE_STATUS
        if m.get("unmapped_reasons"):
            rec["rfp_citation_partially_unmapped"] = list(m["unmapped_reasons"])
    else:
        rec["rfp_citation_unmapped_reason"] = m["reason"]


def apply(doc: dict, rvm: dict, answer, pending: str) -> dict:
    """Re-label every F9 record carrying `pending`; cite registered clauses on REQUIREMENT_AS_RECORDED parameters.
    Fails closed if a correspondence no longer verifies or a pending label survives. Returns a summary record."""
    params = {p["id"]: p for p in doc["parameters"]}
    gates = {g["id"]: g for g in doc["architecture_gates"]}
    out = []

    def rec_map(record_id, qids):
        return _merge([mapping(record_id, q, rvm, answer, params.get(record_id)) for q in qids])

    for pid, p in params.items():                       # a9_16 parameter records (owner answers citing the RFP)
        a = p.get("a9_16") or {}
        if a.get("rfp_citation_status") == pending:
            qids = [q for (r, q) in CORRESPONDENCE if r == pid and q]
            m = rec_map(pid, qids)
            _relabel(a, m, pending)
            out.append({"record": f"parameters[id={pid}].a9_16", "questions": qids, **_summary(m)})
            for field, old, new in STALE_TEXT.get(pid, []):
                if m["status"] != REGISTERED or old not in p[field]:
                    raise RfpCitationError(f"{pid}.{field}: expected step-1 text not found ({old!r})")
                p[field] = p[field].replace(old, new.format(clauses=", ".join(m["clauses"]),
                                                            rows=" / ".join(m["rows"])))
            if pid in STALE_ADVANCE:
                old, new = STALE_ADVANCE[pid]
                if old not in p["evidence_to_advance"]:
                    raise RfpCitationError(f"{pid}.evidence_to_advance: {old!r} not found")
                p["evidence_to_advance"] = [new if x == old else x for x in p["evidence_to_advance"]]
        if p.get("value_label") == "REQUIREMENT_AS_RECORDED":
            m = mapping(pid, None, rvm, answer, p)
            p["rfp_citation"] = {}
            _relabel(p["rfp_citation"], m, None)
            out.append({"record": f"parameters[id={pid}].rfp_citation", "questions": [], **_summary(m)})
    for gid, g in gates.items():                        # gate blocking-evidence records
        b = g.get("blocking_evidence")
        if isinstance(b, dict) and b.get("rfp_citation_status") == pending:
            qids = [q for (r, q) in CORRESPONDENCE if r == gid and q]
            m = rec_map(gid, qids)
            _relabel(b, m, pending)
            out.append({"record": f"architecture_gates[id={gid}].blocking_evidence", "questions": qids, **_summary(m)})
    for q in doc["open_owner_questions"]:               # F9 questions as raised, answered by an RFP-citing answer
        if q.get("rfp_citation_status") == pending:
            rid = QUESTION_RECORD.get(q["id"])
            m = mapping(rid, q["id"], rvm, answer, params.get(rid)) if rid else \
                {"status": UNMAPPED, "reason": f"{q['id']}: no F9 record registered for this question"}
            _relabel(q, m, pending)
            out.append({"record": f"open_owner_questions[id={q['id']}]", "questions": [q["id"]], **_summary(m)})
    for a in doc["a9_16_owner_answers_applied"]:        # owner-answer application rows
        if a.get("rfp_citation_status") == pending:
            m = _merge([mapping(r, a["question_id"], rvm, answer, params.get(r)) for r in a["record_ids"]
                        if (r, a["question_id"]) in CORRESPONDENCE]
                       or [mapping(a["record_ids"][0], a["question_id"], rvm, answer)])
            _relabel(a, m, pending)
            out.append({"record": f"a9_16_owner_answers_applied[question_id={a['question_id']}]",
                        "questions": [a["question_id"]], **_summary(m)})
    left = json.dumps({k: doc[k] for k in ("parameters", "architecture_gates", "open_owner_questions",
                                           "a9_16_owner_answers_applied")}, ensure_ascii=False)
    if '"rfp_citation_status": "' + pending + '"' in left:
        raise RfpCitationError("an " + pending + " citation status survived the F9 re-base")
    return {"rule": "F9 records whose owner answer cites the RFP carry the registered clause ids of the RVM row(s) the "
                    "RVM re-base maps for the corresponding requirement (rfp_citations_f9.CORRESPONDENCE, each "
                    "correspondence verified against the artifacts); the step-1 label is kept as "
                    "rfp_citation_status_as_applied; a record without a registered correspondence is "
                    + UNMAPPED + " with its reason; AG-15 closed by the owner (A9.22 G3)",
            "correspondence_status": CORRESPONDENCE_STATUS + ": the F9 record -> RVM row correspondence "
                                     "(rfp_citations_f9.CORRESPONDENCE) is the recorder's reading, verified against the "
                                     "artifacts (VERBATIM_FACT: the RFP fact quoted in the owner's answer matches the RVM "
                                     "row text); only the clause ids per RVM row come from the RVM re-base; the owner may "
                                     "reverse a correspondence (the AG-15 closure, A9.22 G3, froze the RVM requirement basis, not this "
                                     "correspondence)",
            "registration": REGISTRATION_PATH, "rvm": RVM_PATH + "#/rfp_rebase",
            "statuses": {"REGISTERED_CLAUSE": "registered clause ids, mapped through the RVM re-base",
                         UNMAPPED: "no RVM-mapped clause for the requirement the record cites (reason recorded)"},
            "records": out}


def _summary(m: dict) -> dict:
    if m["status"] == REGISTERED:
        return {"status": REGISTERED, "rfp_clause_ids": m["clauses"], "rvm_rows": m["rows"],
                "correspondence_kinds": sorted({c["kind"] for c in m["correspondence"]})}
    return {"status": m["status"], "reason": m["reason"]}
