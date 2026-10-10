"""AG-15 (A9.13 S6.22 F9-OQ-03) evaluated from the registered official RFP and the RVM re-base.

Verbatim gate text (A9.13 S6.22): "The official RFP is now available to the project, but before this gate closes it must
be placed/registered in the repository evidence system with immutable provenance/hash and the RVM requirements re-based
against it. The repository may not continue relying only on secondary transcriptions."

A9.17 RFP: the PDF is kept in the controlled project evidence store; the hash / provenance record in the repository
(docs/requirements/rfp_official/rfp_registration_v1.json) is the authoritative record.

This module only READS the registration record, the RVM (docs/requirements/rvm_a9/rvm_a9_v1.json, rfp_rebase) and the
owner decision file the RVM closure record cites. It checks that they are present and mutually consistent (fail closed:
any missing field, hash mismatch, unmapped clause or unknown origin -> REFUSED, never a status that suggests the gate is
satisfied), reports which AG-15 evidence parts are present, and carries what is still needed as explicit remaining
conditions. It never declares PASS and never closes the gate on its own.

Owner closure (A9.22 G3, 2026-10-03; closure-record format = recorder proposal RP-BRIEF-01): AG-15 closes only on the
owner closure record rfp_rebase.ag15_closure. A text prefix ('CLOSED ...') in ag_15_status is never evidence. The record
must cite the pinned owner decision (path + sha256 matching the file on disk, decided_by owner, decision code
AG15_CLOSED_SNAPSHOT_FROZEN at the cited item, json / md verbatim pair consistent), accept the current registration
(PDF and clause-transcription sha256), carry the requirements-basis sha256 that this module recomputes from the current
RVM (and that equals the basis the owner accepted), and list as frozen_rows exactly the RFP_CLAUSE rows, every one with
requirement_frozen = true. Anything else -> REFUSED (an RFP row frozen without a valid record included). Closing AG-15
freezes the requirement basis only: it changes no RVM status and implies no compliance.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REGISTRATION_PATH = "docs/requirements/rfp_official/rfp_registration_v1.json"
RVM_PATH = "docs/requirements/rvm_a9/rvm_a9_v1.json"
REGISTERED_STATUS = "REGISTERED_BY_HASH_PDF_CONTROLLED_EXTERNALLY"
STATUS_EVIDENCE_PRESENT = "RFP_REGISTERED_AND_RVM_REBASED_PENDING_OWNER_CLOSURE"
STATUS_REFUSED = "REFUSED_RFP_REGISTRATION_MISSING_OR_INCONSISTENT"
STATUS_CLOSABLE = "DETERMINING_EVIDENCE_PRESENT_NO_REMAINING_CONDITION"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
# owner closure decision (pinned here independently of the RVM builder; immutable decision files)
CLOSURE_DECISION = {"json": "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json",
                    "json_sha256": "245307aca27b8151d0ef31a6e92f932a95920e604847694481cba6731835dc49",
                    "md": "docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md",
                    "md_sha256": "749999db6926a2cdda85c7aab7677410b290df11fe4a7bac903a8a8fd6fcfc77",
                    "item": "G3_REQUIREMENTS_SNAPSHOT", "code": "AG15_CLOSED_SNAPSHOT_FROZEN"}
CLOSURE_RECORD_CODE = "AG15_CLOSED"
ACCEPTED_BASIS_SHA256 = "1d4a7f0099e937f0c74a8c1be8fc14408b75f211c7990be4672f4eee5f9b66b5"
PAGE_REVIEW_STATUS = "OWNER_REVIEWED_NO_ADDITIONAL_TECHNICAL_PERFORMANCE_REQUIREMENT"
_BASIS_ROW_FIELDS = ("id", "title", "category", "requirement_text", "requirement_basis", "requirement_origin",
                     "rfp_clauses", "related_rfp_clauses", "limit")
_BASIS_REBASE_FIELDS = ("registration", "clause_coverage", "not_system_requirements", "discrepancies")
ROOT = Path(__file__).resolve().parents[3]
S6_22_AG15_VERBATIM = ("The official RFP is now available to the project, but before this gate closes it must be "
                       "placed/registered in the repository evidence system with immutable provenance/hash and the RVM "
                       "requirements re-based against it. The repository may not continue relying only on secondary "
                       "transcriptions.")


def clauses_sha256(clauses: list) -> str:
    """Hash rule recorded in the RVM re-base (registration.clauses_hash_rule)."""
    s = json.dumps(clauses, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def requirements_basis_sha256(rvm: dict) -> str:
    """The requirements-basis content hash (rule recorded in rfp_rebase.ag15_closure.accepted_rvm.basis_hash_rule);
    re-implemented here so the F9 check does not trust the RVM builder."""
    rows = rvm.get("rows") or []
    rb = rvm.get("rfp_rebase") or {}
    basis = {"rfp_clause_rows": [{f: r.get(f) for f in _BASIS_ROW_FIELDS} for r in rows
                                 if r.get("requirement_origin") == "RFP_CLAUSE"],
             "row_origins": {r.get("id"): r.get("requirement_origin") for r in rows}}
    for k in _BASIS_REBASE_FIELDS:
        basis[k] = rb.get(k)
    s = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _file_sha256(root: Path, rel: str):
    p = root / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def owner_closure_errors(rec, rvm: dict, registration: dict, rfp_rows: list, rfp_rows_frozen: list, pdf_sha, c_sha,
                         root: Path) -> list:
    """Errors of the owner closure record (empty list = a valid owner closure). Fail closed on every field."""
    if not isinstance(rec, dict):
        return ["rfp_rebase.ag15_closure is not an object"]
    errors = []
    dec = rec.get("decision") or {}
    want = CLOSURE_DECISION
    for k in ("json", "json_sha256", "md", "md_sha256"):
        if dec.get(k) != want[k]:
            errors.append(f"closure decision.{k} {dec.get(k)!r} != pinned {want[k]!r}")
    if dec.get("item") != want["item"] or dec.get("code") != want["code"]:
        errors.append("closure decision item / code are not the owner's A9.22 G3 AG-15 closure")
    if rec.get("decision_code") != CLOSURE_RECORD_CODE:
        errors.append(f"closure decision_code {rec.get('decision_code')!r} != {CLOSURE_RECORD_CODE!r}")
    for k in ("json", "md"):
        got = _file_sha256(root, want[k])
        if got != want[k + "_sha256"]:
            errors.append(f"owner decision file {want[k]} sha256 {got} != {want[k + '_sha256']} (missing or changed)")
    if not errors:
        d = json.loads((root / want["json"]).read_text(encoding="utf-8"))
        if d.get("decided_by") != "owner":
            errors.append("closure decision is not decided_by owner")
        if d.get("verbatim") != {"path": want["md"], "sha256": want["md_sha256"]}:
            errors.append("closure decision json does not name the pinned verbatim md")
        code = (d.get("decisions") or {}).get(want["item"])
        if not isinstance(code, str) or not code.startswith(want["code"]):
            errors.append(f"closure decision {want['item']} is not {want['code']}")
    acc = rec.get("accepted_registration") or {}
    if acc.get("pdf_sha256") != pdf_sha or acc.get("clauses_sha256") != c_sha:
        errors.append("closure accepted_registration != the current registration (PDF / clause-transcription sha256)")
    ar = rec.get("accepted_rvm") or {}
    basis = requirements_basis_sha256(rvm)
    if ar.get("requirements_basis_sha256") != ACCEPTED_BASIS_SHA256 or basis != ACCEPTED_BASIS_SHA256:
        errors.append(f"requirements basis of the current RVM ({basis}) / of the record "
                      f"({ar.get('requirements_basis_sha256')}) != the basis the owner accepted ({ACCEPTED_BASIS_SHA256})")
    if not _HEX64.match(str(ar.get("pre_closure_file_sha256"))):
        errors.append("closure accepted_rvm.pre_closure_file_sha256 missing or not a sha256")
    if rec.get("frozen_rows") != rfp_rows:
        errors.append("closure frozen_rows != the RFP_CLAUSE rows of the RVM")
    if len(rfp_rows_frozen) != len(rfp_rows):
        errors.append(f"requirement_frozen true on {len(rfp_rows_frozen)} of {len(rfp_rows)} RFP_CLAUSE rows")
    st = (rvm.get("rfp_rebase") or {}).get("ag_15_status")
    if not (isinstance(st, str) and st.startswith("CLOSED") and want["json"] in st and want["json_sha256"] in st):
        errors.append("ag_15_status does not cite the owner closure decision (path + sha256)")
    pr = (registration.get("page_coverage") or {}).get("owner_page_review") or {}
    if pr.get("status") != PAGE_REVIEW_STATUS or (pr.get("decision") or {}).get("json_sha256") != want["json_sha256"] \
            or (rec.get("unscreened_pages") or {}).get("disposition") != PAGE_REVIEW_STATUS:
        errors.append("owner page-review disposition (registration page_coverage.owner_page_review / closure "
                      "unscreened_pages) missing or not the A9.22 one")
    return errors


def _refused(errors: list, file_sha256=None) -> dict:
    return {"status": STATUS_REFUSED, "closes": False, "evidence_sufficient_for_freeze": False,
            "registration_file_sha256": file_sha256, "errors": errors,
            "rule": "fail closed: AG-15 consumes only a present, internally consistent registration and RVM re-base"}


def assess(registration, rvm, registration_file_sha256=None, root=None) -> dict:
    """Derive the AG-15 status from the registration record, the RVM and the owner closure record. Fail closed."""
    root = Path(root) if root is not None else ROOT
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
    # ---- owner closure: only the closure record counts (never a text prefix); fail closed on any inconsistency
    closure = rb.get("ag15_closure")
    if closure is None:
        if rfp_rows_frozen:
            errors.append(f"requirement_frozen true on RFP_CLAUSE rows {rfp_rows_frozen} without an owner closure record")
    elif not errors:
        errors += ["owner closure record: " + e for e in owner_closure_errors(
            closure, rvm, registration, rfp_rows, rfp_rows_frozen, pdf_sha, c_sha, root)]
    if errors:
        return _refused(errors, registration_file_sha256)

    # ---- the evidence parts AG-15 names, and what remains
    ag15_rvm = rb.get("ag_15_status")
    owner_closed = closure is not None
    remaining = []
    if not owner_closed:
        remaining.append({
            "id": "AG15-RC-01",
            "condition": "owner closure of AG-15: owner acceptance of the RVM re-base against the registered RFP and "
                         "requirement_frozen = true on the RFP_CLAUSE rows",
            "state": f"OPEN (RVM re-base ag_15_status: {ag15_rvm!r}; requirement_frozen true on "
                     f"{len(rfp_rows_frozen)} of {len(rfp_rows)} RFP_CLAUSE rows)",
            "source": [RVM_PATH + "#/rfp_rebase/ag_15_status", RVM_PATH + "#/rfp_rebase/ag15_closure"],
            "owner_action": True})
    open_items = []
    pc = registration.get("page_coverage") or {}
    unscreened = pc.get("pages_not_screened") or pc.get("pages_not_screened_as_registered")
    if unscreened and not owner_closed:
        open_items.append({"id": "AG15-OI-01", "item": "registration page coverage",
                           "as_recorded": unscreened, "source": REGISTRATION_PATH + "#/page_coverage"})
    disc = rb.get("discrepancies") or []
    if disc:
        open_items.append({"id": "AG15-OI-02", "item": "RVM re-base discrepancies recorded against the RFP",
                           "state": ("KEPT_AS_RECORDED_AT_OWNER_CLOSURE (A9.22 G3; DRDO clarifications named in the "
                                     "dispositions stay open)") if owner_closed else "RECORDED_FOR_OWNER_REVIEW",
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
    if owner_closed:
        parts["owner_closure_recorded"] = {
            "state": "EVIDENCE_PRESENT",
            "decision": {k: CLOSURE_DECISION[k] for k in ("json", "json_sha256", "md", "md_sha256", "item", "code")},
            "decision_code": closure["decision_code"], "frozen_rows": list(closure["frozen_rows"]),
            "requirements_basis_sha256": ACCEPTED_BASIS_SHA256,
            "accepted_rvm_pre_closure_file_sha256": closure["accepted_rvm"]["pre_closure_file_sha256"],
            "requirements_snapshot": rb.get("requirements_snapshot"),
            "unscreened_pages": closure["unscreened_pages"]["disposition"],
            "discrepancy_dispositions": closure["discrepancy_dispositions"]["status"],
            "what_it_is_not": "the requirement basis is frozen; no RVM status changes and no compliance is implied",
            "source": RVM_PATH + "#/rfp_rebase/ag15_closure"}
    closable = not remaining
    return {"status": STATUS_CLOSABLE if closable else STATUS_EVIDENCE_PRESENT,
            # sufficient only once a valid owner closure record exists in the RVM re-base (never declared here)
            "closes": closable, "evidence_sufficient_for_freeze": closable,
            "registration_file_sha256": registration_file_sha256,
            "gate_text_verbatim": S6_22_AG15_VERBATIM,
            "evidence_parts": parts, "remaining_conditions": remaining,
            "recorded_open_items_for_owner_review": open_items, "errors": []}


def determining_evidence(registration: dict, registration_file_sha256: str, assessment: dict | None = None) -> list:
    """The determining-evidence record handed to a9_16_f9.gate_closes (kind 'requirement'; A9.13 S6.22: the class is
    OFFICIAL_SOURCE_DOCUMENT_REGISTERED). When the assessment carries a valid owner closure, the record names it
    (decision path + sha256): the owner closure is the owner act that closes the gate on that evidence, not a separate
    evidence class."""
    doc = registration["document"]
    rec = {"class": "OFFICIAL_SOURCE_DOCUMENT_REGISTERED", "source": REGISTRATION_PATH,
           "sha256": doc["sha256"], "provenance": doc["provenance"],
           "registration_file_sha256": registration_file_sha256}
    oc = ((assessment or {}).get("evidence_parts") or {}).get("owner_closure_recorded")
    if oc:
        rec["owner_closure"] = {"decision_json": oc["decision"]["json"],
                                "decision_json_sha256": oc["decision"]["json_sha256"],
                                "item": oc["decision"]["item"], "code": oc["decision"]["code"],
                                "record": oc["source"]}
    return [rec]
