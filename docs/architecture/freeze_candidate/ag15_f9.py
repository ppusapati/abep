"""AG-15 (A9.13 S6.22 F9-OQ-03) evaluated from the registered official RFP and the RVM re-base.

Verbatim gate text (A9.13 S6.22): "The official RFP is now available to the project, but before this gate closes it must
be placed/registered in the repository evidence system with immutable provenance/hash and the RVM requirements re-based
against it. The repository may not continue relying only on secondary transcriptions."

A9.17 RFP: the PDF is kept in the controlled project evidence store; the hash / provenance record in the repository
(docs/requirements/rfp_official/rfp_registration_v1.json) is the authoritative record.

This module only READS the registration record and the RVM (docs/requirements/rvm_a9/rvm_a9_v1.json, rfp_rebase).
It checks that both are present and mutually consistent (fail closed: any missing field, hash mismatch, unmapped clause
or unknown origin -> REFUSED, never a status that suggests the gate is satisfied), reports which AG-15 evidence parts
are present, and carries what is still needed as explicit remaining conditions. It never declares PASS and never
closes the gate on its own: the RVM re-base records that AG-15 closure is the owner's and keeps requirement_frozen = false
on RFP rows until then.
"""
from __future__ import annotations

import hashlib
import json
import re

REGISTRATION_PATH = "docs/requirements/rfp_official/rfp_registration_v1.json"
RVM_PATH = "docs/requirements/rvm_a9/rvm_a9_v1.json"
REGISTERED_STATUS = "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY"
STATUS_EVIDENCE_PRESENT = "RFP_REGISTERED_AND_RVM_REBASED_PENDING_OWNER_CLOSURE"
STATUS_REFUSED = "REFUSED_RFP_REGISTRATION_MISSING_OR_INCONSISTENT"
STATUS_CLOSABLE = "DETERMINING_EVIDENCE_PRESENT_NO_REMAINING_CONDITION"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
S6_22_AG15_VERBATIM = ("The official RFP is now available to the project, but before this gate closes it must be "
                       "placed/registered in the repository evidence system with immutable provenance/hash and the RVM "
                       "requirements re-based against it. The repository may not continue relying only on secondary "
                       "transcriptions.")


def clauses_sha256(clauses: list) -> str:
    """Hash rule recorded in the RVM re-base (registration.clauses_hash_rule)."""
    s = json.dumps(clauses, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _refused(errors: list, file_sha256=None) -> dict:
    return {"status": STATUS_REFUSED, "closes": False, "evidence_sufficient_for_freeze": False,
            "registration_file_sha256": file_sha256, "errors": errors,
            "rule": "fail closed: AG-15 consumes only a present, internally consistent registration and RVM re-base"}


def assess(registration, rvm, registration_file_sha256=None) -> dict:
    """Derive the AG-15 status from the registration record and the RVM. Fail closed."""
    errors = []
    if not isinstance(registration, dict):
        return _refused(["registration record missing or not a JSON object (" + REGISTRATION_PATH + ")"],
                        registration_file_sha256)
    if not isinstance(rvm, dict) or not isinstance(rvm.get("rfp_rebase"), dict):
        return _refused(["RVM re-base missing (" + RVM_PATH + " /rfp_rebase)"], registration_file_sha256)
    if registration_file_sha256 is not None and not _HEX64.match(str(registration_file_sha256)):
        errors.append("registration file sha256 is not a sha256")

    # ---- registration identity
    doc = registration.get("document") or {}
    if registration.get("status") != REGISTERED_STATUS:
        errors.append(f"registration status {registration.get('status')!r} != {REGISTERED_STATUS!r}")
    pdf_sha = doc.get("sha256")
    if not isinstance(pdf_sha, str) or not _HEX64.match(pdf_sha):
        errors.append("document.sha256 missing or not a sha256")
    pages = doc.get("pages")
    if not isinstance(pages, int) or isinstance(pages, bool) or pages <= 0:
        errors.append("document.pages missing or not a positive integer")
    for f in ("rfp_number", "provenance", "retrieval"):
        if not doc.get(f):
            errors.append(f"document.{f} missing")
    clauses = registration.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        errors.append("clauses missing or empty")
        clauses = []
    ids = [c.get("id") for c in clauses if isinstance(c, dict)]
    if len(ids) != len(clauses) or any(not i for i in ids) or len(set(ids)) != len(ids):
        errors.append("clause ids missing or not unique")
    c_sha = clauses_sha256(clauses) if clauses else None

    # ---- RVM re-base consistency with the registration
    rb = rvm["rfp_rebase"]
    reg = rb.get("registration") or {}
    if reg.get("path") != REGISTRATION_PATH:
        errors.append(f"RVM re-base registration.path {reg.get('path')!r} != {REGISTRATION_PATH!r}")
    if reg.get("pdf_sha256") != pdf_sha:
        errors.append("RVM re-base pdf_sha256 != registered document sha256")
    if reg.get("rfp_number") != doc.get("rfp_number"):
        errors.append("RVM re-base rfp_number != registered rfp_number")
    if reg.get("clauses_sha256") != c_sha:
        errors.append("RVM re-base clauses_sha256 != sha256 of the registered clauses")
    mapping = registration.get("rvm_mapping") or {}
    if mapping.get("clauses_sha256") != c_sha:
        errors.append("registration rvm_mapping.clauses_sha256 != sha256 of the registered clauses")
    if reg.get("n_clauses") != len(clauses):
        errors.append(f"RVM re-base n_clauses {reg.get('n_clauses')!r} != {len(clauses)} registered clauses")

    rows = rvm.get("rows") or []
    row_ids = {r.get("id") for r in rows}
    origins = set(rb.get("origins") or [])
    cov = rb.get("clause_coverage") or []
    cov_by = {c.get("clause_id"): c for c in cov}
    if len(cov_by) != len(cov):
        errors.append("RVM clause_coverage has duplicate clause ids")
    mapped, programmatic, unmapped = [], [], []
    for cid in ids:
        c = cov_by.get(cid)
        if c is None:
            unmapped.append(cid)
            continue
        if not set(c.get("rvm_rows") or []) <= row_ids:
            errors.append(f"{cid}: coverage cites RVM rows that do not exist")
        if c.get("rvm_rows"):
            mapped.append(cid)
        elif (c.get("not_system_requirement") or {}).get("class"):
            programmatic.append(cid)
        else:
            unmapped.append(cid)
    extra = sorted(set(cov_by) - set(ids))
    if unmapped:
        errors.append(f"registered clauses not mapped to an RVM row nor recorded as programmatic: {unmapped}")
    if extra:
        errors.append(f"RVM clause_coverage cites unregistered clauses: {extra}")

    origin_counts, rfp_rows, rfp_rows_frozen = {}, [], []
    for r in rows:
        o = r.get("requirement_origin")
        if o not in origins:
            errors.append(f"{r.get('id')}: requirement_origin {o!r} not in the re-base origins")
            continue
        origin_counts[o] = origin_counts.get(o, 0) + 1
        if o == "RFP_CLAUSE":
            rfp_rows.append(r.get("id"))
            cited = r.get("rfp_clauses") or []
            if not cited or not set(cited) <= set(ids):
                errors.append(f"{r.get('id')}: RFP_CLAUSE row without registered clause ids")
            if r.get("requirement_frozen") is True:
                rfp_rows_frozen.append(r.get("id"))
        for s in r.get("sources") or []:
            if isinstance(s, dict) and s.get("kind") == "rfp_official_clause" and s.get("pdf_sha256") != pdf_sha:
                errors.append(f"{r.get('id')}: rfp_official_clause source pdf_sha256 != registered sha256")
    if rb.get("origin_counts") != origin_counts:
        errors.append("RVM re-base origin_counts missing or disagree with the rows")
    if not rfp_rows:
        errors.append("no RVM row has requirement_origin RFP_CLAUSE: the RVM is not re-based on the registered RFP")
    if errors:
        return _refused(errors, registration_file_sha256)

    # ---- the evidence parts AG-15 names, and what remains
    ag15_rvm = rb.get("ag_15_status")
    owner_closed = isinstance(ag15_rvm, str) and ag15_rvm.startswith("CLOSED")
    remaining = []
    if not owner_closed or len(rfp_rows_frozen) != len(rfp_rows):
        remaining.append({
            "id": "AG15-RC-01",
            "condition": "owner closure of AG-15: owner acceptance of the RVM re-base against the registered RFP and "
                         "requirement_frozen = true on the RFP_CLAUSE rows",
            "state": f"OPEN (RVM re-base ag_15_status: {ag15_rvm!r}; requirement_frozen true on "
                     f"{len(rfp_rows_frozen)} of {len(rfp_rows)} RFP_CLAUSE rows)",
            "source": [RVM_PATH + "#/rfp_rebase/ag_15_status", RVM_PATH + "#/rfp_rebase/rule"],
            "owner_action": True})
    open_items = []
    pc = registration.get("page_coverage") or {}
    if pc.get("pages_not_screened"):
        open_items.append({"id": "AG15-OI-01", "item": "registration page coverage",
                           "as_recorded": pc["pages_not_screened"],
                           "source": REGISTRATION_PATH + "#/page_coverage/pages_not_screened"})
    disc = rb.get("discrepancies") or []
    if disc:
        open_items.append({"id": "AG15-OI-02", "item": "RVM re-base discrepancies recorded against the RFP",
                           "as_recorded": [{"id": d.get("id"), "topic": d.get("topic"),
                                            "disposition": d.get("disposition")} for d in disc],
                           "source": RVM_PATH + "#/rfp_rebase/discrepancies"})
    parts = {
        "official_rfp_registered_with_immutable_provenance_hash": {
            "state": "EVIDENCE_PRESENT",
            "status": registration["status"], "rfp_number": doc["rfp_number"], "pdf_sha256": pdf_sha,
            "pages": pages, "n_registered_clauses": len(clauses), "clauses_sha256": c_sha,
            "pdf_in_repository": bool(doc.get("committed_to_repository")),
            "pdf_storage": doc.get("pdf_storage"),
            "evidence_class": registration.get("evidence_class"),
            "source": REGISTRATION_PATH + "#/document"},
        "rvm_requirements_rebased_against_it": {
            "state": "EVIDENCE_PRESENT",
            "rebase_id": rb.get("id"), "rvm_status": rvm.get("status"),
            "clauses_mapped_to_rvm_rows": len(mapped), "clauses_recorded_programmatic": programmatic,
            "clauses_unmapped": [], "origin_counts": origin_counts, "rvm_rows": len(rows),
            "source": RVM_PATH + "#/rfp_rebase/clause_coverage"},
        "not_relying_only_on_secondary_transcriptions": {
            "state": "EVIDENCE_PRESENT",
            "note": "RFP_CLAUSE rows cite registered clause ids; secondary records are kept as historical cross-"
                    "references", "source": RVM_PATH + "#/rows"},
    }
    closable = not remaining
    return {"status": STATUS_CLOSABLE if closable else STATUS_EVIDENCE_PRESENT,
            # sufficient only once the owner's closure is recorded in the RVM re-base (never declared here)
            "closes": closable, "evidence_sufficient_for_freeze": closable,
            "registration_file_sha256": registration_file_sha256,
            "gate_text_verbatim": S6_22_AG15_VERBATIM,
            "evidence_parts": parts, "remaining_conditions": remaining,
            "recorded_open_items_for_owner_review": open_items, "errors": []}


def determining_evidence(registration: dict, registration_file_sha256: str) -> list:
    """The determining-evidence record handed to a9_16_f9.gate_closes (kind 'requirement')."""
    doc = registration["document"]
    return [{"class": "OFFICIAL_SOURCE_DOCUMENT_REGISTERED", "source": REGISTRATION_PATH,
             "sha256": doc["sha256"], "provenance": doc["provenance"],
             "registration_file_sha256": registration_file_sha256}]
