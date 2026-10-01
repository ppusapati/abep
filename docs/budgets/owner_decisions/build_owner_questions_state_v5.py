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
5. a question raised since v4 by a lane package and still open (MPV3Q-01, mass/power v3) is added as TBD_OWNER.

A v4 TBD_OWNER row with no owner answer stays TBD_OWNER. Nothing is answered here that the owner did not answer; every
RFP-cited fact ('RFP(1)') is OWNER_STATED_PENDING_RFP_REGISTRATION (AG-15). Missing or unexpected ids raise.

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

REL = lambda p: p.relative_to(ROOT).as_posix()
V4 = HERE / "owner_questions_state_v4.json"
V4_SHA = "6ba74803f9577cb63f3e719d176702eb47e05a55a3c054eba926649a5c23bf67"
SEQ_CSV = HERE / "owner_questions_sequenced_v1.csv"
SEQ_MD = HERE / "OWNER_QUESTIONS_SEQUENCED_v1.md"
F9 = ROOT / "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
MP3 = ROOT / "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"

OUT_JSON = HERE / "owner_questions_state_v5.json"
OUT_MD = HERE / "OWNER_QUESTIONS_STATE_v5.md"
OUT_CSV = HERE / "owner_questions_state_v5.csv"

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


def build():
    v4 = load_v4()
    seq = sequenced()
    f9 = json.loads(F9.read_text(encoding="utf-8"))
    mp3 = json.loads(MP3.read_text(encoding="utf-8"))
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
    missing = sorted(answered_ids - used)
    if missing:
        raise SystemExit(f"owner answers with no state row: {missing}")
    row_ids = {r["id"] for r in rows}
    if any(i not in row_ids for i in seq):
        raise SystemExit("a sequenced question has no v5 row")

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
                 {"key": "sequenced_v1_md", "path": REL(SEQ_MD), "sha256": _sha(SEQ_MD)}] + L.pins(),
        "referenced_not_pinned": {
            "rule": "mutable lane deliverables: read at build time, ids checked (a missing id raises), never sha-pinned",
            "paths": [REL(F9), REL(MP3)]},
        "status_vocabulary": vocab,
        "status_rule": ("'status' is canonical. A v4 TBD_OWNER row answered by A9.8 .. A9.14 keeps 'v4_status' and gets "
                        "ANSWERED_BY_A9_<n> or, where A9.15 amends the answer, AMENDED_BY_A9_15 (governing_reading = the "
                        "A9.15 bullet). Non-TBD v4 rows are copied unchanged. A9.7 lane questions are rows of kind "
                        "a9_7_lane_question. A row without an owner answer stays TBD_OWNER."),
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
        "owner_answers_applied": applied,
        "open_owner_questions": [r["id"] for r in rows if r["status"] == "TBD_OWNER"],
        "open_owner_questions_note": "TBD_OWNER rows: questions with no owner answer yet (raised since v4 or unanswered)",
        "compliance": ["every v4 row present; non-TBD_OWNER v4 rows copied unchanged",
                       "every answered row carries decision pointer, json sha256, verbatim md sha256 and a verbatim excerpt",
                       "A9.15 governs every 'Xe contingency-only for C1' reading",
                       "RFP-cited facts are OWNER_STATED_PENDING_RFP_REGISTRATION; no PASS produced; no answer invented"],
        "rows": rows,
    }


def render_md(doc):
    cell = lambda s: " ".join(_flat(s).split()).replace("|", "\\|")
    rows = doc["rows"]
    out = ["# Owner questions — state v5", "",
           "State v4 plus the A9.7 lane questions, with the owner answers A9.8 .. A9.14 applied and the A9.15 "
           "RFP-compliant propellant policy amendments (generated by `" + doc["generated_by"] + "`; do not edit by hand).", "",
           "Counts: " + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + f". **{doc['tbd_owner_count']} TBD_OWNER.**", "",
           "Answered in this step: " + ", ".join(f"{k} {v}" for k, v in doc["answered_this_step_by_decision"].items()) + ".", "",
           "RFP rule: " + doc["rfp_rule"] + ".", "",
           "## A9.15 RFP-compliant propellant policy (governing)", "", "> " + doc["a9_15_governing_statement"], "",
           doc["a9_15_scope_note"] + ".", "",
           "| # | ID | A9.14 code | Governing reading (A9.15, verbatim) |", "|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {r['decision_code']} | {cell(r['governing_reading']['text'])} |"
            for r in rows if r["status"] == "AMENDED_BY_A9_15"]
    out += ["", "Superseded statements:", ""]
    out += [f"- {s['id']}: \"{cell(s['text'])}\" -> superseded by A9.15 (`{s['superseded_by']['path']}`)"
            for s in doc["superseded_statements"]]
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
            "needed_by"]
    w.writerow(cols)
    for r in doc["rows"]:
        vals = []
        for c in cols:
            v = r.get(c)
            if c == "governing_reading" and v:
                v = v["text"]
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
