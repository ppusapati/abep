"""Build the bid technical package (DRAFT_FOR_OWNER_REVIEW) and the generated part of its freeze record.

The TECHNICAL SOURCE is one constant: `bid_technical_source.commit` in docs/bid/bid_technical_baseline_v2.json
(compliance_data.TECHNICAL_SOURCE_SHA). Every fact is read AT THAT COMMIT with `git show` (source_facts.py), never from the
working tree. Generates:
  docs/bid/bid_technical_baseline_v2.json  `facts_read_from_technical_source` (the rest of the record is owner-decided)
  compliance_matrix_v1.json                machine-readable clause-by-clause matrix + gate statuses carried verbatim
  01_COMPLIANCE_MATRIX.md                  the human-readable matrix
  README.md, 02_..05_*.md                  rendered from templates/*.md ({{NAME}} placeholders filled from the source)
  docx/*.docx                              a Word rendering of every package Markdown file (when python-docx is importable)

Switching the technical source: edit the one `commit` line of the v2 record (and fill its verification_record), then run
this script. Usage: python docs/bid/package/build_package.py [--check] [--no-docx]
  --check    regenerate everything in memory and fail if a committed file differs (docx not compared: python-docx zip
             timestamps are not deterministic)
Nothing here is submitted anywhere; the repository never submits a bid.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import compliance_data as cd  # noqa: E402
import source_facts as sf  # noqa: E402

REG_PATH = sf.REG
F9_PATH = sf.F9
MD_ORDER = ["README.md", "01_COMPLIANCE_MATRIX.md", "02_TECHNICAL_APPROACH.md", "03_DEVELOPMENT_AND_TEST_PLAN.md",
            "04_RISK_REGISTER.md", "05_PROGRAMMATIC_SECTIONS.md", "06_SUBMISSION_CHECKLIST.md"]
TEMPLATED = ["README.md", "02_TECHNICAL_APPROACH.md", "03_DEVELOPMENT_AND_TEST_PLAN.md", "04_RISK_REGISTER.md",
             "05_PROGRAMMATIC_SECTIONS.md", "06_SUBMISSION_CHECKLIST.md"]
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


class BuildError(RuntimeError):
    pass


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def render(text: str, T: dict) -> str:
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in T})
    if missing:
        raise BuildError(f"unfilled placeholders: {missing}")
    out = PLACEHOLDER.sub(lambda m: str(T[m.group(1)]), text)
    if "{{" in out or "}}" in out:
        raise BuildError("placeholder syntax left after rendering")
    return out


def kg(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}"


def gkg(x: float) -> str:
    return f"{x:g}"


# ------------------------------------------------------------------------------------------------ text facts
def text_facts(F: dict) -> dict:
    M = F["mass"]
    wet = M["wet"]
    states = sorted({w["state"] for w in wet})
    if len(states) == 1:
        states_txt = f"{states[0]} in all {len(wet)} cases"
    else:
        states_txt = ", ".join(f"{gkg(w['xe_case_kg'])} kg: {w['state']}" for w in wet)
    missing = M["lines_without_value"]
    missing_txt = (f"; {', '.join(missing)} {'has' if len(missing) == 1 else 'have'} no value in this record and "
                   f"{'is' if len(missing) == 1 else 'are'} excluded from the known part") if missing else ""
    lines = {x["line"]: x for x in M["lines"]}
    tgt = cd.MASS_PROPOSAL_TARGET
    tgt_wet = tgt["nominal_dry_max_kg"] * (1 + tgt["system_margin_fraction"]) + tgt["xe_planning_reference_kg"]
    rc = F["rvm_counts"]
    gs = F["gate_status"]
    T = {
        "SRC": F["short"], "SRC_FULL": F["sha"], "BRANCH": BRANCH,
        "RVM_TOTAL": F["rvm_total"], "RVM_NE": rc["NOT_EVALUATED"], "RVM_IE": rc["INCOMPLETE_EVIDENCE"],
        "RVM_PASS": "none" if rc["PASS"] == 0 else str(rc["PASS"]),
        "RVM_CLAUSE_ROWS": F["rvm_rfp_clause_rows"], "RVM_CLAUSE_FROZEN": F["rvm_rfp_clause_rows_frozen"],
        "RVM16_READING": F["rvm16_reading_status"], "RVM06": F["rvm_status"]["RVM-06"],
        "FLIGHT_CATHODE": F["conventional_hollow_cathode"], "SUPPLY_MODES": " + ".join(F["supply_modes"]),
        "ARCH_STATUS": F["architecture_status"], "ICP_FEED": F["icp_feed_primary"], "ICP_FEED_VAR": F["icp_feed_variant"],
        "DS_N": F["design_state_n"], "DS_ID": F["design_state_set_id"], "DS_PATH": F["design_state_set_path"],
        "DS_ORBIT": F["design_state_orbit_basis"],
        "F9DF01": F["f9_df01_status"], "ROBUST_N": F["robust_set_members"], "ROBUST_STATUS": F["robust_set_status"],
        "F7_FRONTIER": f"{F['f7_frontier_mgs']:.4g}", "F7_N038": F["f7_members_reaching_038"],
        "F78_07_RANGE": f"{F['f78_07_compressor_kg'][0]:.2f}-{F['f78_07_compressor_kg'][1]:.2f}",
        "FLOW_GAP_ORDER": "; ".join(f"{r} {lv}" for r, lv in F["flow_gap_order"]),
        "AL02": gkg(lines["AL-02"]["value_kg"]), "AL08": gkg(lines["AL-08"]["value_kg"]),
        "XE_CASES": " / ".join(gkg(w["xe_case_kg"]) for w in wet), "XE_FIRST": gkg(wet[0]["xe_case_kg"]),
        "MASS_RECORD": M["path"], "MASS_ID": M["id"], "MASS_DRY": kg(M["dry_kg"]), "MASS_PCT": M["system_margin_pct"],
        "MASS_NOMINAL": kg(M["nominal_dry_kg"]), "MASS_MARGIN": kg(M["system_margin_kg"]),
        "MASS_NONHARNESS": kg(M["nonharness_kg"]), "MASS_HARNESS": kg(M["harness_kg"]),
        "MASS_WET_LIST": " / ".join(kg(w["wet_kg"]) for w in wet), "MASS_STATES": states_txt,
        "MASS_EXCEED_FIRST": kg(wet[0]["exceedance_kg"]), "MASS_MISSING": missing_txt,
        "MASS_STATUS": cd.MASS_STATUS, "MASS_STATUS_SHORT": cd.MASS_STATUS.replace("MASS ", ""),
        "MASS_ACTIONS": "; ".join(cd.MASS_CLOSURE_ACTIONS),
        "TARGET_TEXT": (f"nominal dry <= {tgt['nominal_dry_max_kg']:.1f} kg with a "
                        f"{tgt['system_margin_fraction'] * 100:.0f} % system margin and the "
                        f"{gkg(tgt['xe_planning_reference_kg'])} kg Xe planning reference -> {tgt_wet:.1f} kg wet"),
        "TARGET_XE": gkg(tgt["xe_planning_reference_kg"]),
        "AG10": gs["AG-10"], "AG11": gs["AG-11"], "AG13": gs["AG-13"], "AG15": gs["AG-15"],
        "GNG": gs["GNG-ICP-01"],
        "PAGE_REVIEW": (f"owner page review {F['page_review_status']} (A9.22 G3: technical-performance requirements only)"
                        if F["page_review_status"] else "no owner page review recorded"),
        "GATES_SUFFICIENT": ", ".join(F["gates_sufficient"]) or "none",
        "GATES_NOT_SUFFICIENT": ", ".join(g["id"] for g in F["gates"] if not g["sufficient"]),
        "MISSION_LIFE_H": f"{F['mission_life_h']:,}", "FIRING_LIFE_H": f"{F['firing_life_h']:,}",
        "CONS_STATUS": f"{F['constraints_set_status']} ({F['constraints_frozen']})",
        "SCENARIO": f"{F['scenario_id']} ({F['scenario_layer']}, {F['scenario_status']})",
        "A926_REF": (f"`{cd.A926}`" if F["a926_at_source"] else
                     "A9.26 record: post-source governing decision, not contained in the technical source - see README, "
                     "'Technical source'"),
    }
    return T


BRANCH = "claude/nifty-ramanujan-w68f9z"


def source_findings(F: dict) -> list[str]:
    """Reasons why the technical source is not (yet) the A9.26-compliant final source (empty = none)."""
    out = []
    if not F["a926_at_source"]:
        out.append("owner decision A9.26 (2026-10-05, bid mass policy) is not contained in the technical source; it is "
                   "pinned as a post-source governing decision in docs/bid/bid_technical_baseline_v2.json")
    M = F["mass"]
    if abs(M["system_margin_fraction"] - cd.A926_BID_SYSTEM_MARGIN_FRACTION) > 1e-9:
        out.append(f"the mass record {M['id']} applies a {M['system_margin_pct']} % system margin, not the A9.26 bid-basis "
                   f"{cd.A926_BID_SYSTEM_MARGIN_FRACTION * 100:.0f} % (its roll-up is shown as recorded)")
    if M["lines_without_value"]:
        out.append(f"the mass record {M['id']} has no value for {', '.join(M['lines_without_value'])} (A9.26 sets AL-09 "
                   f"= 1.0 kg in the mass-policy successor)")
    return out


# ------------------------------------------------------------------------------------------------ evidence
def resolve_evidence(F: dict, src: sf.Source, clause_id: str, evidence: list) -> tuple[list, list]:
    """Substitute the mass record, drop if_at_source records absent at the source, and verify every path / locator."""
    out, post = [], []
    for e in evidence:
        p = F["mass"]["path"] if e["path"] == cd.MASS else e["path"]
        if not src.exists(p):
            if e.get("if_at_source"):
                post.append(p)
                continue
            raise BuildError(f"{clause_id}: {p} absent at {F['short']}")
        loc = e["locator"]
        if p.endswith(".json") and loc.startswith("#/"):
            try:
                sf.resolve(src.json(p), loc[2:].split()[0])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise BuildError(f"{clause_id}: {p} {loc} does not resolve at {F['short']} ({exc})") from exc
        out.append({"path": p, "locator": loc})
    return out, post


def build_json(F: dict, src: sf.Source, T: dict) -> dict:
    reg = src.json(REG_PATH)
    clauses, post = [], set()
    for c in reg["clauses"]:
        d = cd.CLAUSES[c["id"]]
        assert d["status"] in cd.STATUSES, (c["id"], d["status"])
        evid, p = resolve_evidence(F, src, c["id"], d["evidence"])
        post.update(p)
        clauses.append({
            "id": c["id"], "page": c["page"], "section": c["section"], "rfp_text_verbatim": c["text"],
            "status": d["status"], "response": render(d["response"], T), "rvm_rows": d.get("rvm", []),
            "evidence_at_technical_source": evid, "owner_input": d.get("owner_input", []),
        })
    extra = sorted(set(cd.CLAUSES) - {c["id"] for c in reg["clauses"]})
    if extra:
        raise BuildError(f"compliance data for unregistered clauses: {extra}")
    counts = {s: sum(1 for c in clauses if c["status"] == s) for s in cd.STATUSES}
    gates = [{"id": g["id"], "gate": g["gate"], "status_at_technical_source": g["status"],
              "evidence_sufficient_for_freeze": g["sufficient"],
              **({"criteria": g["criteria"]} if g["locator"].startswith("#/pre_lock1") else {}),
              "source": {"path": F9_PATH, "locator": g["locator"]}} for g in F["gates"]]
    M = F["mass"]
    return {
        "schema": "bid_compliance_matrix_v2",
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "tender": "2026_DRDO_788433_1",
        "rfp": "DTDF/06/13516/DSP/ABEP/X/L/M/01",
        "bidder": "Vyovrinda Aerospace",
        "technical_source_commit": F["sha"],
        "freeze_record": cd.BASELINE_V2,
        "historical_freeze_record": cd.BASELINE_V1,
        "generated_by": "docs/bid/package/build_package.py (data: docs/bid/package/compliance_data.py; facts: "
                        "docs/bid/package/source_facts.py)",
        "rule": "every evidence path is a file at the technical source commit; no clause is stated compliant beyond what "
                "that evidence shows; nothing in this file is a test result, PASS or GO",
        "status_vocabulary": {k: render(v, T) for k, v in cd.STATUS_DEFINITIONS.items()},
        "status_counts": counts,
        "clauses": clauses,
        "gates_at_technical_source": gates,
        "mass_presentation": {
            "rule": "A9.26 message 2 section 7 hierarchy; every roll-up number is read from the mass record at the "
                    "technical source; no mass compliance is claimed",
            "requirement": cd.MASS_REQUIREMENT_TEXT,
            "proposal_design_target": dict(cd.MASS_PROPOSAL_TARGET, label="DESIGN TARGET, not evidence; the Xe planning "
                                           "reference is not the selected Xe load"),
            "current_rollup": {"record": M["path"], "locator": M["rollup_locator"], "nominal_dry_kg": M["nominal_dry_kg"],
                               "system_margin_pct": M["system_margin_pct"], "system_margin_kg": M["system_margin_kg"],
                               "dry_kg": M["dry_kg"], "wet": M["wet"], "lines_without_value": M["lines_without_value"],
                               "label": "CURRENT PROVISIONAL PLANNING / EVIDENCE ROLL-UP (not a CBE)"},
            "status": cd.MASS_STATUS,
            "closure_actions": cd.MASS_CLOSURE_ACTIONS,
        },
        "post_source_governing_decisions": sorted(post),
        "source_findings": source_findings(F),
        "owner_inputs": cd.OWNER_INPUTS,
        "resolved_owner_inputs": cd.RESOLVED_OWNER_INPUTS,
        "rfp_pages_not_screened": F["pages_not_screened"],
        "rfp_pages_owner_review": {"status": F["page_review_status"], "owner_statement_verbatim": F["page_review_statement"],
                                   "scope": F["page_review_scope"],
                                   "source": f"{REG_PATH} #/page_coverage/owner_page_review"} if F["page_review_status"] else None,
    }


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def build_md(j: dict, T: dict) -> str:
    S = T["SRC"]
    L = ["# 01 - Clause-by-clause compliance matrix", "",
         "**Status: DRAFT_FOR_OWNER_REVIEW.** Generated by `docs/bid/package/build_package.py` from "
         "`docs/bid/package/compliance_data.py` and the registered RFP clauses at the technical source commit "
         f"`{S}` (`{T['SRC_FULL']}`, pinned by `docs/bid/bid_technical_baseline_v2.json`); do not edit by hand. "
         "Machine-readable: `docs/bid/package/compliance_matrix_v1.json`.", "",
         f"Tender {j['tender']}, RFP {j['rfp']}. Clause text is the repository's verbatim transcription "
         f"(`{REG_PATH}`, 37 clauses, pages 16-21, 27, 30). Every evidence path below is a file at `{S}`; "
         f"read it with `git show {S}:<path>`. Locators are JSON pointers (with `[key=value]` list selection) or "
         "section names.", "",
         f"Statuses never claim more than the evidence shows. At `{S}` no RVM row of the flight configuration is "
         f"PASS ({T['RVM_NE']} NOT_EVALUATED, {T['RVM_IE']} INCOMPLETE_EVIDENCE), the Hall credible transport set is "
         "empty and every absolute 0-D Hall result is withdrawn; this matrix quotes none of them.", "",
         "## Status vocabulary", "", "| status | meaning |", "|---|---|"]
    for s in cd.STATUSES:
        L.append(f"| {s} | {md_escape(j['status_vocabulary'][s])} |")
    L += ["", "## Status counts", "", "| status | clauses |", "|---|---|"]
    for s, n in j["status_counts"].items():
        L.append(f"| {s} | {n} |")
    L.append(f"| total | {sum(j['status_counts'].values())} |")
    L += ["", "## Summary table", "", "| clause | page | section | status | RVM rows |", "|---|---|---|---|---|"]
    for c in j["clauses"]:
        L.append(f"| {c['id']} | {c['page']} | {md_escape(c['section'])} | {c['status']} | "
                 f"{', '.join(c['rvm_rows']) or '-'} |")
    L += ["", "## Clause responses", ""]
    for c in j["clauses"]:
        L += [f"### {c['id']} (p. {c['page']}, {c['section']}) - {c['status']}", "",
              f"> RFP (verbatim transcription): {c['rfp_text_verbatim']}", "",
              f"**Response.** {c['response']}", "", f"**Evidence at {S}:**", ""]
        for e in c["evidence_at_technical_source"]:
            L.append(f"- `{e['path']}` {e['locator']}")
        if c["owner_input"]:
            L += ["", "**Owner input required:** " + ", ".join(c["owner_input"]) + " (checklist in README.md)."]
        L.append("")
    L += ["## Gate statuses at the technical source (carried verbatim)", "",
          f"Source: `{F9_PATH}` at `{S}` (`architecture_gates`, `pre_lock1_gates`). None of these gates is PASS or GO; "
          f"none may be reported as such in the submission. Only {T['GATES_SUFFICIENT']} has evidence sufficient for "
          "freeze (the requirement basis), which is not a compliance result.", "",
          f"| gate | what | status at {S} | sufficient for freeze |", "|---|---|---|---|"]
    for g in j["gates_at_technical_source"]:
        st = g["status_at_technical_source"]
        st = st if len(st) <= 160 else st[:157] + "..."
        L.append(f"| {g['id']} | {md_escape(g['gate'])} | {md_escape(st)} | "
                 f"{str(g['evidence_sufficient_for_freeze']).lower()} |")
    L += ["", "## RFP pages not transcribed by the repository", "", j["rfp_pages_not_screened"] + "."]
    if j["rfp_pages_owner_review"]:
        r = j["rfp_pages_owner_review"]
        L += ["", f"Owner page review (`{REG_PATH}` `#/page_coverage/owner_page_review`): {r['status']} - \"{r['owner_statement_verbatim']}\" "
                  "This covers technical-performance requirements only; the repository does not transcribe those pages."]
    L += ["", "Owner ruling A9.27: the owner has reviewed those pages including the formats; OIR-DOC-01 = "
              "REVIEW_COMPLETE_SUBMISSION_FORM_COMPLETION_PENDING (Part IV(A)-(H) forms and submission controls; "
              "06_SUBMISSION_CHECKLIST.md).", ""]
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ template blocks
def blocks(F: dict, T: dict, j: dict, baseline: dict) -> dict:
    S = T["SRC"]
    M = F["mass"]
    B = {}
    # README: technical source section
    ver = baseline["bid_technical_source"]["verification_record"]
    findings = j["source_findings"]
    banner = []
    if findings:
        banner = ["", f"> **SOURCE NOT YET FINAL FOR THE BID (generated check).** The technical source `{S}` differs "
                      "from the owner's bid basis in the following points; switching the technical source to the "
                      "verified mass-policy successor (one line in `docs/bid/bid_technical_baseline_v2.json`, then "
                      "`python docs/bid/package/build_package.py`) removes this notice:"]
        banner += [f"> - {x}" for x in findings]
    B["SOURCE_SECTION"] = "\n".join([
        f"- **Technical source (bid source): `{T['SRC_FULL']}`** (`{S}`, branch `{BRANCH}`). It is the single constant "
        "`bid_technical_source.commit` of the freeze record `docs/bid/bid_technical_baseline_v2.json` (owner decisions "
        "A9.24 item 9, A9.25 message 8 sections 12-14, A9.26 message 2 sections 5-8); the whole package is generated "
        "from it by `python docs/bid/package/build_package.py`.",
        f"- Verification record of the technical source: {ver}",
        "- **Two-SHA discipline (A9.25 message 8 section 13):** the freeze record and this regenerated package form the "
        "PACKAGE / FREEZE-RECORD commit. They pin the technical source; they are not a technical source. Every technical "
        f"number, status and claim in this package cites a file at `{S}` (read with `git show {S}:<path>`); files "
        "under `docs/bid/` are the package itself.",
        f"- Mass record at the technical source: `{M['path']}` (status {M['status']}).",
        "- History: the v1 freeze record `docs/bid/bid_technical_baseline.json` (historical bbc480c freeze, owner P0 "
        "decision 2026-10-03) is kept unchanged. The owner replaced it as the bid basis (A9.24 item 9: choose B, do not "
        "submit against bbc480c); none of its mass values or its upstream caveat is carried here.",
    ] + banner)
    B["STATUS_COUNTS"] = "\n".join(f"- {s}: {n}" for s, n in j["status_counts"].items())
    used = {}
    for c in j["clauses"]:
        for o in c["owner_input"]:
            used.setdefault(o, []).append(c["id"])
    B["OWNER_CHECKLIST"] = "\n".join(f"- [ ] **{k}** - {v} Clauses: {', '.join(used.get(k, [])) or '-'}."
                                     for k, v in cd.OWNER_INPUTS.items())
    B["RESOLVED_INPUTS"] = "\n".join(f"- [x] {k} - {v}" for k, v in cd.RESOLVED_OWNER_INPUTS.items())
    # 02 section 2.2 subsystem / mass-line table
    groups = [("a. Air intake and compressor storage",
               "intake / filter / duct; compressor + drive; plenum / feed; Xe storage / flow (separate path)",
               ["AL-01", "AL-02", "AL-03", "AL-08"]),
              ("b. Power supply electronics",
               "Hall PPU incl. collector / bias supply; RF generator / matching; controls / valve drivers / flight sensors",
               ["AL-07", "AL-06", "AL-09"]),
              ("c. Thruster", "H-1 head + magnet incl. anode heat-removal hardware; ICP neutralizer incl. collector / "
                              "bias electrode", ["AL-04", "AL-05"]),
              ("(system)", "structure / thermal; harness", ["AL-10", "AL-HAR"])]
    lines = {x["line"]: x for x in M["lines"]}

    def cell(lid):
        x = lines[lid]
        if lid == "AL-HAR":
            return f"AL-HAR {kg(M['harness_kg'], 3)} kg (harness rule, computed in the roll-up; not a routed harness)"
        if x["value_kg"] is None:
            return f"{lid} no value in this record"
        return f"{lid} {gkg(x['value_kg'])} kg ({x['governs']})"
    rows = ["| RFP subsystem | contents | mass lines at the technical source (governing basis) |", "|---|---|---|"]
    for name, contents, lids in groups:
        rows.append(f"| {name} | {contents} | {'; '.join(cell(l) for l in lids)} |")
    B["SUBSYSTEM_MASS_TABLE"] = "\n".join(rows)
    # 02 section 9: the A9.26 mass hierarchy
    tgt = cd.MASS_PROPOSAL_TARGET
    wet_rows = "\n".join(f"| + {gkg(w['xe_case_kg'])} kg Xe (planning / sensitivity case) | {kg(w['wet_kg'])} | "
                         f"{w['state']} vs {w['comparator']} {gkg(w['reference_kg'])} kg "
                         f"(exceeds by {kg(w['exceedance_kg'])} kg) |" for w in M["wet"])
    B["MASS_SECTION"] = "\n".join([
        f"**Status: {cd.MASS_STATUS}.** No mass compliance is claimed. AG-11 at `{S}`: {T['AG11']}; RVM-06 "
        f"(< 40 kg wet): {T['RVM06']}.", "",
        "| level (A9.26 message 2 section 7) | content | label |", "|---|---|---|",
        f"| Requirement | {cd.MASS_REQUIREMENT_TEXT} (owner's conservative wet reading of the RFP '< 40kg'; DISC-02 "
        "recorded for DRDO clarification) | requirement; not relaxed |",
        f"| Proposal design target | {T['TARGET_TEXT']} | DESIGN TARGET (owner decision A9.26), not evidence; the "
        f"{T['TARGET_XE']} kg Xe case is a planning reference, not the selected Xe load |",
        f"| Current provisional planning / evidence roll-up | dry {T['MASS_DRY']} kg after a {T['MASS_PCT']} % system "
        f"margin; wet {T['MASS_WET_LIST']} kg at {T['XE_CASES']} kg Xe | CURRENT PROVISIONAL PLANNING / EVIDENCE FLOOR "
        "(owner allocations and MEV planning floors; no CBE, no measured mass) |",
        f"| Current status | {cd.MASS_STATUS} | AG-11 and RVM-06 as above |", "",
        f"Roll-up as recorded (`{M['path']}` `{M['rollup_locator']}`, reading {M['reading']}; every value read from the "
        "record):", "",
        "| term | kg | note |", "|---|---|---|",
        f"| non-harness lines (known) | {kg(M['nonharness_kg'], 4)} | {T['MASS_MISSING'][2:] or 'every line carries a value'} |",
        f"| harness (rule) | {kg(M['harness_kg'], 4)} | not a routed harness |",
        f"| nominal dry | {kg(M['nominal_dry_kg'], 4)} | |",
        f"| system margin {M['system_margin_pct']} % | {kg(M['system_margin_kg'], 4)} | as recorded in the mass record |",
        f"| dry (after system margin) | {kg(M['dry_kg'], 4)} | |",
        wet_rows, "",
        f"Lines with a CBE: {M['n_lines_with_cbe']}; lines with a measured mass: {M['n_lines_with_measured']}. The "
        f"flight Xe load is NOT FROZEN: {T['XE_CASES']} kg are planning / sensitivity cases, none is the selected load. "
        "Legacy card-closure Xe / MEV values are historical model-regression provenance only and are not quoted.", "",
        "**Mass-closure actions (A9.26 message 2 section 7):**", ""] +
        [f"{i}. {a}" for i, a in enumerate(cd.MASS_CLOSURE_ACTIONS, 1)] +
        ["", "No line is reduced to force closure, no qualified hardware is removed for mass alone and the requirement is "
             "not relaxed (MQ-10; A9.26 message 2 section 4)."])
    # 03 section 2: hardware programme (entry status read)
    what = {
        "H1-S7.1": "FEMM magnetostatics of MC-1 at the authorised analysis points",
        "H1-S7.2": "H-1 engineering channel point (magnetic feasibility, thermal margin, mass, packaging, "
                   "manufacturability; not thrust-optimised)",
        "C1-REF": "H-1 + C1 ground reference characterization (C1 GROUND_REFERENCE_ONLY); registers I_d,max,H1,Ar",
        "ICP-AR-REF": "ICP Ar engineering / commissioning reference (P1 stages)",
        "ICP-45A-P1-S7": "ICP-45 capacity stage on Ar (needs I_d,max,H1,Ar frozen first)",
        "ICP-45N": "registered air / N2 ICP-45 campaign (own domain, provenance, four closures frozen first)",
        "ICP-XE-MODE": "separate registered Xe-mode campaign (contingency supply mode)",
        "P2-MAP": "ICP plasma impedance map, after the in-house V/I magnitude / phase calibration and its uncertainty "
                  "budget are frozen",
        "COUPLED-H1-ICP": "coupled H-1 + ICP operation",
        "P3-THERMAL": "coupled thermal analysis and test",
        "P4-ACCEPTANCE-EXPOSURE": "anode-material acceptance-bearing coupon exposure (LOCK-2 thresholds frozen first)",
        "H1-THRUST-FEED-MAP": "measured H-1 thrust / feed map (mandatory)",
        "AG-12": "performance-derived, statewise feed-state sufficiency",
        "AG-13": "statewise drag compensation T_available(state) - D_spacecraft(state) >= 0",
    }
    rows = [f"| # | step | what | predecessor (basis) | entry status at {S} |", "|---|---|---|---|---|"]
    for i, s in enumerate(F["hw_steps"], 1):
        pred = ", ".join(f"{p} ({b})" for p, b in s["predecessors"]) or "-"
        rows.append(f"| {i} | {s['id']} | {what[s['id']]} | {pred} | {s['status']} |")
    B["HW_TABLE"] = "\n".join(rows)
    # 03 section 3: gates (status read verbatim)
    gmeta = [("GNG-ICP-01", "GNG-ICP-01 ICP go / no-go", "mandatory, before LOCK-1",
              "criteria PENDING_OWNER_ACCEPTANCE (no numerical criterion approved; recorder proposal RP-A919-01 preserved "
              "for review only)"),
             ("AG-04", "ICP-45 (AG-04)", "before relying on ICP capacity", "I_e,cap (discharge-OFF, signed) vs I_d,max,H1"),
             ("AG-05", "AG-05 coupled H-1 / ICP thermal", "before freeze", "P3 (cathodeless successor model post-bid, AFI-03)"),
             ("AG-06", "AG-06 anode thermal", "before freeze", "P3"),
             ("AG-07", "AG-07 anode material", "before freeze", "P4 under LOCK-2"),
             ("AG-10", "AG-10 bus power", "before freeze", "P_bus,1ms,max < 1500 W"),
             ("AG-11", "AG-11 mass", "before freeze", "< 40 kg wet on CBE / measured mass"),
             ("AG-12", "AG-12 feed-state sufficiency", "after the measured thrust / feed map", "statewise"),
             ("AG-13", "AG-13 drag compensation", "after AG-12 and the host drag ICD", "statewise"),
             ("AG-02", "AG-02 Hall credible transport set", "successor held-out validation", "pre-registered successor validation"),
             ("AG-03", "AG-03 Hall-transport validation", "successor held-out validation", "P5-N2 v1 unchanged"),
             ("AG-15", "AG-15 requirement basis", "before freeze", "owner closure of the RVM re-base (requirement basis only)")]
    rows = [f"| gate | placement | status at {S} (verbatim) | criteria | source |", "|---|---|---|---|---|"]
    for gid, name, place, crit in gmeta:
        g = next(x for x in F["gates"] if x["id"] == gid)
        rows.append(f"| {name} | {place} | {md_escape(g['status'])} | {crit} | `{F9_PATH}` `{g['locator']}` |")
    rows.insert(3, f"| LOCK-1 | after D-01..D-15 and GNG-ICP-01 | not releasable (`lock1_release_reportable` false) | "
                   f"owner decisions D-01..D-15 | `{F9_PATH}` `#/lock1_precondition` |")
    B["GATES_TABLE_03"] = "\n".join(rows)
    return B


# ------------------------------------------------------------------------------------------------ freeze record
def baseline_facts(F: dict, src: sf.Source, j: dict) -> dict:
    M = F["mass"]
    gov = []
    for d in cd.GOVERNING_DECISIONS:
        at = src.exists(d["json"]) and src.exists(d["md"])
        rec = {"id": d["id"], "what": d["what"], "json": d["json"], "md": d["md"], "locator": d["locator"],
               "in_technical_source": at}
        if d.get("package_level_post_source_allowed"):
            rec["package_level_post_source_allowed"] = True
        for k in ("json", "md"):
            if at:
                rec[k + "_sha256"] = _sha256(src.text(d[k]).encode("utf-8"))
            else:
                with open(os.path.join(ROOT, d[k]), "rb") as f:
                    rec[k + "_sha256"] = _sha256(f.read())
                rec["provenance"] = "post-source owner decision: committed in the package history, not in the technical source"
        gov.append(rec)
    unresolved = [{"id": g["id"], "status": g["status"]} for g in F["gates"] if not g["sufficient"]]
    return {
        "rule": "generated by docs/bid/package/build_package.py from the technical source (git show); never hand-edited; "
                "nothing here is a PASS, GO or compliance result",
        "technical_source_commit": F["sha"],
        "source_status": ("NOT_FINAL_FOR_BID: " + " | ".join(j["source_findings"])) if j["source_findings"] else
                         "CONSISTENT_WITH_OWNER_BID_BASIS (verification record governs finality)",
        "governing_decisions": gov,
        "ag15": {"status": F["gate_status"]["AG-15"], "evidence_sufficient_for_freeze": "AG-15" in F["gates_sufficient"],
                 "meaning": "requirement basis closed by the owner (A9.22 G3); never a compliance result",
                 "source": f"{sf.F9} #/architecture_gates[id=AG-15]"},
        "mission_basis_h": {"mission_life_h": F["mission_life_h"], "firing_life_h": F["firing_life_h"],
                            "source": f"{sf.CONSTRAINTS} #/constraints/mission_life_h, #/constraints/firing_life_h"},
        "design_state_set": {"id": F["design_state_set_id"], "path": F["design_state_set_path"],
                             "sha256": F["design_state_set_sha256"], "n_required_states": F["design_state_n"],
                             "orbit_basis_label": F["design_state_orbit_basis"], "source": f"{sf.F78} #/design_state_set"},
        "robust_upstream_set": {"status": F["robust_set_status"], "n_members": F["robust_set_members"],
                                "f9_df01_status": F["f9_df01_status"],
                                "requirement_relaxation_proposed": F["f9_df01_relaxation_proposed"],
                                "source": f"{sf.F9} #/upstream_pareto/robust_set, #/design_findings_for_owner[id=F9-DF-01]"},
        "architecture": {"configuration": F["flight_configuration"], "flight_cathode": F["conventional_hollow_cathode"],
                         "supply_modes": F["supply_modes"], "separate_tanks": F["separate_tanks"],
                         "icp_feed_gas": {"primary": F["icp_feed_primary"], "declared_variant": F["icp_feed_variant"]},
                         "c1": F["a925_C1"], "architecture_status": F["architecture_status"],
                         "frozen_reference_flight_architecture": F["frozen_reference_flight_architecture"],
                         "rvm16_current_architecture_reading": F["rvm16_reading_status"],
                         "al08_valves": F["a925_AFI-01-S1"],
                         "source": f"{sf.F9} #/configuration/flight_architecture, #/architecture_status; {sf.A925_JSON} "
                                   "#/owner_decision_summary/C1, /AFI-01-S1; {RVM} RVM-16".replace("{RVM}", sf.RVM)},
        "engineering_constraint_config_separation": {
            "engineering_constraints": f"{sf.CONSTRAINTS}: {F['constraints_set_status']} ({F['constraints_frozen']})",
            "operating_scenario": f"{sf.SCENARIO}: {F['scenario_id']} {F['scenario_layer']} {F['scenario_status']}"},
        "mass": {"record": M["path"], "record_id": M["id"], "record_status": M["status"],
                 "locator": M["rollup_locator"], "system_margin_pct": M["system_margin_pct"],
                 "nominal_dry_kg": M["nominal_dry_kg"], "dry_kg": M["dry_kg"], "wet": M["wet"],
                 "lines_without_value": M["lines_without_value"], "status": cd.MASS_STATUS,
                 "ag11": F["gate_status"]["AG-11"], "rvm06": F["rvm_status"]["RVM-06"],
                 "xe_load": "NOT_FROZEN: " + " / ".join(gkg(w["xe_case_kg"]) for w in M["wet"]) +
                            " kg are planning / sensitivity cases; none is the selected Xe load"},
        "gates": [{"id": g["id"], "status": g["status"], "evidence_sufficient_for_freeze": g["sufficient"]}
                  for g in F["gates"]],
        "unresolved_gates": unresolved,
        "network_builder": {"path": "docs/chemistry/o_o2/v0/build_tables_nist107_o.py",
                            "present_at_source": src.exists("docs/chemistry/o_o2/v0/build_tables_nist107_o.py"),
                            "status": F["a925_network_builder"], "source": f"{sf.A925_JSON} #/owner_decision_summary/network_builder"},
        "legacy_card_closure": {"owner_record_verbatim": F["a925_bid_mass_basis"],
                                "label": "HISTORICAL_MODEL_REGRESSION_ONLY: never current flight Xe / MEV numbers; not "
                                         "quoted in the package",
                                "source": f"{sf.A925_JSON} #/owner_decision_summary/bid_mass_basis"},
    }


def build_baseline(F: dict, src: sf.Source, j: dict) -> dict:
    with open(os.path.join(ROOT, cd.BASELINE_V2), encoding="utf-8") as f:
        b = json.load(f)
    if b["bid_technical_source"]["commit"] != F["sha"]:
        raise BuildError("freeze record commit changed under the build")
    with open(os.path.join(ROOT, cd.BASELINE_V1), "rb") as f:
        v1sha = _sha256(f.read())
    if v1sha != b["supersedes"]["sha256"]:
        raise BuildError(f"historical v1 freeze record changed ({v1sha}); it must stay unchanged")
    b["facts_read_from_technical_source"] = baseline_facts(F, src, j)
    return b


# ------------------------------------------------------------------------------------------------ docx
_INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def _add_inline(par, text):
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1])
            r.font.name = "Consolas"
        else:
            par.add_run(part)


def md_to_docx(md_text: str, out_path: str) -> None:
    import docx  # python-docx
    doc = docx.Document()
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1]):
            rows = [ln]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", r.strip())[1:-1]] for r in rows]
            ncol = max(len(r) for r in cells)
            t = doc.add_table(rows=len(cells), cols=ncol)
            t.style = "Table Grid"
            for ri, r in enumerate(cells):
                for ci in range(ncol):
                    p = t.cell(ri, ci).paragraphs[0]
                    _add_inline(p, r[ci] if ci < len(r) else "")
                    if ri == 0:
                        for run in p.runs:
                            run.bold = True
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            doc.add_heading(m.group(2), level=len(m.group(1)))
        elif re.match(r"^\s*[-*]\s+", ln):
            _add_inline(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*]\s+(\[[ x]\]\s+)?", "", ln))
        elif re.match(r"^\s*\d+\.\s+", ln):
            _add_inline(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+\.\s+", "", ln))
        elif ln.startswith("> "):
            _add_inline(doc.add_paragraph(style="Intense Quote"), re.sub(r"^>\s+(-\s+)?", "", ln))
        elif ln.strip() and not ln.startswith("<!--"):
            _add_inline(doc.add_paragraph(), ln)
        i += 1
    doc.save(out_path)


# ------------------------------------------------------------------------------------------------ main
def build_all() -> dict:
    sha = cd.TECHNICAL_SOURCE_SHA
    src = sf.Source(sha)
    F = sf.facts(sha)
    T = text_facts(F)
    j = build_json(F, src, T)
    baseline = build_baseline(F, src, j)
    T.update(blocks(F, T, j, baseline))
    out = {os.path.join(ROOT, cd.BASELINE_V2): json.dumps(baseline, indent=1, ensure_ascii=False) + "\n",
           os.path.join(HERE, "compliance_matrix_v1.json"): json.dumps(j, indent=1, ensure_ascii=False) + "\n",
           os.path.join(HERE, "01_COMPLIANCE_MATRIX.md"): build_md(j, T)}
    for name in TEMPLATED:
        with open(os.path.join(HERE, "templates", name), encoding="utf-8") as f:
            out[os.path.join(HERE, name)] = render(f.read(), T)
    return out


def main(argv):
    check = "--check" in argv
    targets = build_all()
    if check:
        bad = [p for p, s in targets.items() if not os.path.exists(p) or open(p, encoding="utf-8").read() != s]
        if bad:
            print("STALE:", *bad)
            return 1
        print("OK")
        return 0
    for p, s in targets.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)
    if "--no-docx" not in argv:
        try:
            import docx  # noqa: F401
        except ImportError:
            print("python-docx not available: docx not generated")
            return 0
        os.makedirs(os.path.join(HERE, "docx"), exist_ok=True)
        for name in MD_ORDER:
            md_to_docx(open(os.path.join(HERE, name), encoding="utf-8").read(),
                       os.path.join(HERE, "docx", name[:-3] + ".docx"))
        print("docx generated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
