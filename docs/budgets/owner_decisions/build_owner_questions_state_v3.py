"""Owner-question state v3: state v2 plus the owner's A9.3 post-A9 tier-1 answers (2026-09-30).

v2 stays immutable (it is pinned by the A9-10 records). v3 copies every v2 row, sets the eight tier-1 rows answered in
docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json to ANSWERED_BY_A9_3 with a pointer and an excerpt,
and changes nothing else. Missing or unexpected ids raise.

    python docs/budgets/owner_decisions/build_owner_questions_state_v3.py          # write
    python docs/budgets/owner_decisions/build_owner_questions_state_v3.py --check  # verify outputs are current
"""
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
V2 = HERE / "owner_questions_state_v2.json"
A93 = ROOT / "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json"
A93_MD = ROOT / "docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md"
OUT_JSON = HERE / "owner_questions_state_v3.json"
OUT_MD = HERE / "OWNER_QUESTIONS_STATE_v3.md"
OUT_CSV = HERE / "owner_questions_state_v3.csv"
NEW_STATUS = "ANSWERED_BY_A9_3"


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    a93 = json.loads(A93.read_text(encoding="utf-8"))
    if a93["decision"] != "A9_3_POST_A9_TIER1_DECISIONS_RECORDED":
        raise SystemExit("state v3: A9.3 decision file has an unexpected decision value")
    if a93["verbatim"]["sha256"] != _sha(A93_MD):
        raise SystemExit("state v3: A9.3 verbatim record does not match its pinned sha256")
    answers = a93["decisions"]
    rows, seen = [], set()
    for r in v2["rows"]:
        r = dict(r)
        if r["id"] in answers:
            if r["status"] != "OPEN":
                raise SystemExit(f"state v3: {r['id']} is not OPEN in v2")
            a = answers[r["id"]]
            status = a["status"] if isinstance(a["status"], str) else "; ".join(a["status"])
            r.update(status=NEW_STATUS, status_detail="ANSWERED (A9.3)",
                     answer_pointer=f"docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json decisions.{r['id']}",
                     answer_sha256=_sha(A93), answer_excerpt=f"{status} :: {a['summary'] if 'summary' in a else a.get('icp45_requirement', '')}")
            seen.add(r["id"])
        rows.append(r)
    missing = sorted(set(answers) - seen)
    if missing:
        raise SystemExit(f"state v3: A9.3 answers ids not found in v2: {missing}")
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    vocab = dict(v2["status_vocabulary"])
    vocab[NEW_STATUS] = "lane question answered by an A9.3 decision (post-A9 tier-1, 2026-09-30)"
    detail = dict(v2["status_detail_vocabulary"])
    detail["ANSWERED (A9.3)"] = "A9.3 post-A9 tier-1 decision (binding); status ANSWERED_BY_A9_3"
    return {
        "schema": "owner_questions_state_v3", "id": "owner_questions_state_v3",
        "status": v2["status"],
        "supersedes_for_use": "docs/budgets/owner_decisions/owner_questions_state_v2.json (kept immutable)",
        "pins": {"state_v2": {"path": "docs/budgets/owner_decisions/owner_questions_state_v2.json", "sha256": _sha(V2)},
                 "a9_3_decision": {"path": "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json", "sha256": _sha(A93)},
                 "a9_3_verbatim": {"path": "docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md", "sha256": _sha(A93_MD)}},
        "status_vocabulary": vocab, "status_detail_vocabulary": detail, "status_rule": v2["status_rule"],
        "counts": dict(sorted(counts.items())), "open_count": counts.get("OPEN", 0),
        "compliance": ["only the eight A9.3 answers change status; every other v2 row is copied unchanged",
                       "answers come only from the owner decision file", "no winner declared"],
        "rows": rows,
    }


def render_md(doc):
    cell = lambda s: " ".join(str(s).split()).replace("|", "\\|")
    out = ["# Owner questions — state v3", "",
           f"State v2 plus the owner's A9.3 post-A9 tier-1 answers (2026-09-30). Counts: "
           + ", ".join(f"{k} {v}" for k, v in doc["counts"].items()) + f". **{doc['open_count']} OPEN.**", "",
           "## Answered by A9.3", "", "| # | ID | Question | Answer (excerpt) |", "|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {cell(r['question'])} | {cell(r['answer_excerpt'])} |" for r in doc["rows"] if r["status"] == NEW_STATUS]
    out += ["", "## Still OPEN", "", "| # | ID | Question | Proposed | Needed by |", "|---|---|---|---|---|"]
    out += [f"| {r['no']} | {r['id']} | {cell(r['question'])} | {cell(r.get('proposed', ''))} | {cell(r.get('needed_by', ''))} |"
            for r in doc["rows"] if r["status"] == "OPEN"]
    return "\n".join(out) + "\n"


def render_csv(doc):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    cols = ["no", "id", "source", "status", "status_detail", "question", "answer_pointer", "answer_excerpt", "proposed", "needed_by"]
    w.writerow(cols)
    for r in doc["rows"]:
        w.writerow([r.get(c, "") for c in cols])
    return buf.getvalue()


def main():
    doc = build()
    outputs = {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc), OUT_CSV: render_csv(doc)}
    if "--check" in sys.argv:
        stale = [p.name for p, s in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"state v3 outputs stale: {stale}")
        print("owner-question state v3: current")
        return
    for p, s in outputs.items():
        p.write_text(s, encoding="utf-8")
    print(f"wrote state v3: {doc['counts']}")


if __name__ == "__main__":
    main()
