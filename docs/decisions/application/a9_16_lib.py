"""A9.16 decision-application helpers (integration lane): pinned owner decisions A9.8 .. A9.15 and verbatim excerpts.

The owner decision files under docs/decisions/ are immutable records. This module pins each machine-readable companion
(.json) and its verbatim record (.md) by sha256 and refuses to run when either differs (fail closed). It never edits a
decision file. Excerpts are cut verbatim from the pinned .md (the .json 'summary' is a recorder digest; the verbatim text
governs). A9.15 (RFP-compliant propellant policy) amends A9.13 owner_statements.xenon and A9.14 S8.17 / S8.21 / S8.33 /
S8.35 / S9.3 / S9.10: wherever an older text reads 'Xe contingency-only for C1', A9.15 governs (``governing``).

stdlib only. Imported by the A9.16 integration builders (state v5, application matrix, H-1 / F9 / F6 / RVM / M16).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEC = "docs/decisions"

# key -> (json, json sha256, md, md sha256, group label)
DECISIONS = {
    "A9.8": (f"{DEC}/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json",
             "e96b8bc0a27f5fbc03d48d36db6e470dfc60c4960d6ba02cdaac8871752b537f",
             f"{DEC}/OD_2026_10_01_A9_8_S1_P1_START_OWNER_DECISIONS.md",
             "8e770d0edf056a0402f6ec8c86a2a2feec169ab971fae788c7a9a620211e1aa0", "S1 (blocks P1 start)"),
    "A9.9": (f"{DEC}/OD_2026_10_01_A9_9_s2_model_change_owner_decisions.json",
             "b6010d9d2856ab21b15d49e477ade8246b9d6e90d4dfa1cc07c4468c10a1e47b",
             f"{DEC}/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md", None, "S2 (production-model change)"),
    "A9.10": (f"{DEC}/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json",
              "3a99f16dd957f533b6b7afb7539d27be132fae386148e1683e417db0ede26544",
              f"{DEC}/OD_2026_10_01_A9_10_S3_P1_LATER_STAGE_OWNER_DECISIONS.md", None, "S3 (later P1 stage)"),
    "A9.11": (f"{DEC}/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json",
              "d8baf59a5b92739698e29d893e89a30995559ee7167814c096dc24599679156c",
              f"{DEC}/OD_2026_10_01_A9_11_S4_P2_OWNER_DECISIONS.md", None, "S4 (blocks P2)"),
    "A9.12": (f"{DEC}/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json",
              "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d",
              f"{DEC}/OD_2026_10_01_A9_12_S5_P3_P4_OWNER_DECISIONS.md", None, "S5 (blocks P3 / P4)"),
    "A9.13": (f"{DEC}/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
              "9afaca459efe27556033d836814f71bd03203711627899f3ffc494567d763b23",
              f"{DEC}/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md", None, "S6 (upstream architecture)"),
    "A9.14": (f"{DEC}/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              f"{DEC}/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md", None, "S7-S10"),
    "A9.15": (f"{DEC}/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              f"{DEC}/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903", "RFP-compliant propellant policy"),
}
ORDER = tuple(DECISIONS)
A915_AMENDED = ("OQ-A907-07", "XA9Q-07", "MPQ-01", "XV2Q-01", "XA9Q-05", "OD6")
RFP_PENDING = "OWNER_STATED_PENDING_RFP_REGISTRATION"
RFP_PENDING_NOTE = ("'RFP(1)' cites the official RFP held by the owner; the document is not registered in the repository "
                    "(AG-15), so every RFP-cited fact is OWNER_STATED_PENDING_RFP_REGISTRATION")
_HEADER = re.compile(r"^\s*(\d+)\.\s+S(\d+\.\d+)\s+—\s+([A-Za-z0-9_\-]+)\s+—\s*(.*)$")
_TRAILER = re.compile(r"^(S\d+ — |That closes|One especially|A particularly important|Also, the official RFP|"
                      r"what do you do)")


def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _load():
    out = {}
    for key, (jp, jsha, mp, msha, label) in DECISIONS.items():
        got = sha256_file(jp)
        if got != jsha:
            raise SystemExit(f"{key}: decision json {jp} sha256 {got} != pinned {jsha} (decision files are immutable)")
        doc = json.loads((ROOT / jp).read_text(encoding="utf-8"))
        vmd = doc["verbatim"]
        if vmd["path"] != mp:
            raise SystemExit(f"{key}: verbatim path {vmd['path']} != {mp}")
        if msha is not None and vmd["sha256"] != msha:
            raise SystemExit(f"{key}: verbatim sha256 in json {vmd['sha256']} != pinned {msha}")
        md_sha = sha256_file(mp)
        if md_sha != vmd["sha256"]:
            raise SystemExit(f"{key}: verbatim {mp} sha256 {md_sha} != json record {vmd['sha256']}")
        out[key] = {"json": jp, "json_sha256": jsha, "md": mp, "md_sha256": md_sha, "label": label, "doc": doc,
                    "md_text": (ROOT / mp).read_text(encoding="utf-8")}
    return out


LOADED = _load()


def pins() -> list:
    """Pin rows (json and verbatim md of every decision) for an artifact's pins section."""
    rows = []
    for key in ORDER:
        d = LOADED[key]
        rows.append({"key": f"{key}_json", "path": d["json"], "sha256": d["json_sha256"]})
        rows.append({"key": f"{key}_md", "path": d["md"], "sha256": d["md_sha256"]})
    return rows


def _sections(md_text: str) -> dict:
    body = md_text.split("\n---\n", 1)[1]
    secs, cur = {}, None
    for line in body.splitlines():
        m = _HEADER.match(line)
        if m:
            cur = m.group(3)
            if cur in secs:
                raise SystemExit(f"duplicate verbatim section {cur}")
            secs[cur] = {"sequenced_no": "S" + m.group(2), "lines": [line.strip()]}
            continue
        if cur is None:
            continue
        if _TRAILER.match(line.strip()):
            cur = None
            continue
        secs[cur]["lines"].append(line.rstrip())
    return {k: {"sequenced_no": v["sequenced_no"], "text": "\n".join(v["lines"]).strip()} for k, v in secs.items()}


SECTIONS = {key: (_sections(LOADED[key]["md_text"]) if key != "A9.15" else {}) for key in ORDER}


def decision_ids(key: str) -> list:
    return list(LOADED[key]["doc"].get("decisions", {}) or {})


def decision_key_of(qid: str) -> str:
    hits = [k for k in ORDER if qid in (LOADED[k]["doc"].get("decisions") or {})]
    if len(hits) != 1:
        raise SystemExit(f"question id {qid}: found in {hits} (expected exactly one A9.8..A9.14 decision)")
    return hits[0]


def verbatim(key: str, qid: str) -> str:
    sec = SECTIONS[key].get(qid)
    if sec is None:
        raise SystemExit(f"{key}: no verbatim section for {qid}")
    dec = LOADED[key]["doc"]["decisions"][qid]
    if sec["sequenced_no"] != dec["sequenced_no"]:
        raise SystemExit(f"{key} {qid}: verbatim S-number {sec['sequenced_no']} != json {dec['sequenced_no']}")
    return sec["text"]


def a915_amendment_line(qid: str) -> str:
    """Verbatim A9.15 bullet amending an A9.14 answer (owner text)."""
    for line in LOADED["A9.15"]["md_text"].splitlines():
        if line.startswith("* S") and f"/ {qid}:" in line:
            return line[2:].strip()
    raise SystemExit(f"A9.15: no verbatim amendment line for {qid}")


def a915_governing_statement() -> str:
    text = LOADED["A9.15"]["md_text"]
    marker = "And the statement I made earlier should be replaced with:\n"
    stmt = text.split(marker, 1)[1].splitlines()[0].strip()
    if not stmt.startswith("The official RFP is the sole governing basis for propellant capability."):
        raise SystemExit("A9.15 governing statement not found in the verbatim md")
    return stmt


def cites_rfp(text: str) -> bool:
    return "RFP(1)" in text


def answer(qid: str) -> dict:
    """Pointer + sha256 + verbatim excerpt of the owner answer to one question id (A9.15 governs where it amends)."""
    key = decision_key_of(qid)
    d = LOADED[key]
    dec = d["doc"]["decisions"][qid]
    text = verbatim(key, qid)
    out = {"decision": key, "decision_json": d["json"], "decision_json_sha256": d["json_sha256"],
           "decision_md": d["md"], "decision_md_sha256": d["md_sha256"], "question_id": qid,
           "sequenced_no": dec["sequenced_no"], "decision_code": dec["answer"],
           "pointer": f"{d['json']}#/decisions/{qid}", "verbatim_excerpt": text,
           "rfp_citation_status": RFP_PENDING if cites_rfp(text) else None}
    if qid in A915_AMENDED:
        a = LOADED["A9.15"]
        line = a915_amendment_line(qid)
        out["amended_by"] = {"decision": "A9.15", "decision_json": a["json"], "decision_json_sha256": a["json_sha256"],
                             "decision_md": a["md"], "decision_md_sha256": a["md_sha256"],
                             "pointer": f"{a['json']}#/amendments/{qid}", "verbatim_excerpt": line,
                             "governs": True, "rfp_citation_status": RFP_PENDING}
        out["rfp_citation_status"] = RFP_PENDING
    return out


def governing(qid: str) -> dict:
    """The governing reading of a question: the A9.15 amendment where one exists, else the original answer."""
    a = answer(qid)
    if "amended_by" in a:
        return {"decision": "A9.15", "pointer": a["amended_by"]["pointer"], "sha256": a["amended_by"]["decision_json_sha256"],
                "text": a["amended_by"]["verbatim_excerpt"]}
    return {"decision": a["decision"], "pointer": a["pointer"], "sha256": a["decision_json_sha256"],
            "text": a["verbatim_excerpt"]}


def cite(qid: str) -> str:
    """Citation string 'A9.14 F5-OQ-03 (<json> sha256 <sha>)' (+ 'amended by A9.15 ...')."""
    a = answer(qid)
    s = f"{a['decision']} {qid} ({a['decision_json']} sha256 {a['decision_json_sha256']})"
    if "amended_by" in a:
        s += f"; amended by A9.15 ({a['amended_by']['decision_json']} sha256 {a['amended_by']['decision_json_sha256']})"
    return s


def applied_row(qid: str, artifact: str, record_ids, how_applied: str, tests=None) -> dict:
    """One 'owner_answers_applied' entry: decision path + json sha256 + question id + decision code + application."""
    a = answer(qid)
    row = {"decision": a["decision"], "question_id": qid, "sequenced_no": a["sequenced_no"],
           "decision_code": a["decision_code"], "decision_json": a["decision_json"],
           "decision_json_sha256": a["decision_json_sha256"], "decision_md": a["decision_md"],
           "decision_md_sha256": a["decision_md_sha256"], "artifact": artifact,
           "record_ids": list(record_ids) if isinstance(record_ids, (list, tuple)) else [record_ids],
           "how_applied": how_applied, "tests": list(tests or [])}
    if "amended_by" in a:
        row["amended_by"] = {k: a["amended_by"][k] for k in ("decision", "decision_json", "decision_json_sha256",
                                                             "pointer", "verbatim_excerpt")}
    if a["rfp_citation_status"]:
        row["rfp_citation_status"] = a["rfp_citation_status"]
    return row


def a915_row(artifact: str, record_ids, how_applied: str, tests=None) -> dict:
    a = LOADED["A9.15"]
    return {"decision": "A9.15", "question_id": "A9.15 governing_rule", "decision_code": a["doc"]["decision"],
            "decision_json": a["json"], "decision_json_sha256": a["json_sha256"], "decision_md": a["md"],
            "decision_md_sha256": a["md_sha256"], "artifact": artifact,
            "record_ids": list(record_ids) if isinstance(record_ids, (list, tuple)) else [record_ids],
            "how_applied": how_applied, "tests": list(tests or []), "rfp_citation_status": RFP_PENDING}


def has_xe_contingency_wording(text: str) -> bool:
    """True when a text limits Xe to a C1 contingency (the wording A9.15 supersedes)."""
    t = " ".join(text.lower().split())
    return bool(re.search(r"(?<!not because )xe (remains |stays |is )?contingency[- ]only", t))
