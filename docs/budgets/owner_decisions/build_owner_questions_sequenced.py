"""Sequenced owner-question list (2026-10-01): every open owner question - state v4 TBD_OWNER rows plus the A9.7 lane
questions rolled up in the F9 freeze candidate - in one numbered order for the owner to answer one by one. Read-only
over its inputs; answers are recorded later as new owner-decision addenda.

    python docs/budgets/owner_decisions/build_owner_questions_sequenced.py          # write
    python docs/budgets/owner_decisions/build_owner_questions_sequenced.py --check  # verify outputs are current
"""
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V4 = ROOT / "docs/budgets/owner_decisions/owner_questions_state_v4.json"
F9 = ROOT / "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
OUT_MD = ROOT / "docs/budgets/owner_decisions/OWNER_QUESTIONS_SEQUENCED_v1.md"
OUT_CSV = ROOT / "docs/budgets/owner_decisions/owner_questions_sequenced_v1.csv"
DEC = ROOT / "docs/decisions"

GROUPS = [
    ("S1", "Blocks the start of P1 (answer first)"),
    ("S2", "Production-model change decisions (move goldens / need a HISTORY entry)"),
    ("S3", "Blocks a later P1 stage"),
    ("S4", "Blocks P2"),
    ("S5", "Blocks P3 / P4"),
    ("S6", "Upstream architecture (intake, filter, compressor, plenum, system optimizer, freeze candidate)"),
    ("S7", "H-1 and downstream-ICP design"),
    ("S8", "Blocks LOCK-1"),
    ("S9", "Nothing immediate"),
    ("S10", "Tooling / performance / Rust"),
]
BLOCK_GROUP = {"BLOCKS_P1_START": "S1", "BLOCKS_P1_LATER_STAGE": "S3", "BLOCKS_P2": "S4", "BLOCKS_P3_P4": "S5",
               "BLOCKS_LOCK_1": "S8", "NOTHING_IMMEDIATE": "S9"}
ORDER = [g for g, _ in GROUPS]
A97_GROUP = {"F1Q-01": "S2", "F1Q-04": "S2", "OQ-F3-01": "S2", "F9-OQ-04": "S2", "UPSTREAM_ICD-Q7": "S2",
             "F0-OQ-01": "S10", "F0-OQ-02": "S10", "RUST-OQ-01": "S10", "RUST-OQ-02": "S10"}
A97_DEFAULT = {"F5": "S7", "F6": "S7"}


def _text(x):
    return " ".join(str(x or "").split())


def answers():
    """Owner answers recorded in decision addenda that cite this list (decisions[id].sequenced_no)."""
    out = {}
    for p in sorted(DEC.glob("OD_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for qid, v in (d.get("decisions") or {}).items():
            if isinstance(v, dict) and "sequenced_no" in v:
                out[qid] = "%s (%s)" % (v["answer"], p.name)
                if v.get("amended_by"):
                    out[qid] += " [amended by %s]" % Path(v["amended_by"]).name
    return out


def build():
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    roll = json.loads(F9.read_text(encoding="utf-8"))["owner_question_rollup"]
    f9_new = {q["id"]: q for q in json.loads(F9.read_text(encoding="utf-8")).get("open_owner_questions", [])
              if isinstance(q, dict) and "id" in q}
    rows = []
    for r in v4["rows"]:
        if r["status"] != "TBD_OWNER":
            continue
        b = r.get("blocks") or ["NOTHING_IMMEDIATE"]
        b = b if isinstance(b, list) else [b]
        g = min((BLOCK_GROUP.get(x, "S9") for x in b), key=ORDER.index)
        rows.append({"group": g, "id": r["id"], "question": _text(r["question"]), "proposed": _text(r.get("proposed")),
                     "blocks": ", ".join(b), "source": "owner_questions_state_v4 row %s" % r.get("no")})
    lane_qs = list(roll["a9_7_lane_questions"]) + list(roll["other_existing_open_questions_cited"])
    for qid in roll["new_f9_questions"]:
        q = f9_new.get(qid, {"id": qid, "question": qid})
        lane_qs.append(dict(q, lane="F9"))
    for q in lane_qs:
        lane = q.get("lane", "")
        g = A97_GROUP.get(q["id"]) or A97_DEFAULT.get(lane, "S6")
        rows.append({"group": g, "id": q["id"], "question": _text(q.get("question")),
                     "proposed": _text(q.get("proposed", "")), "blocks": "",
                     "source": "A9.7 %s" % (lane or "existing ICD")})
    rows.sort(key=lambda x: (ORDER.index(x["group"])))
    ans = answers()
    for r in rows:
        r["answered"] = ans.get(r["id"], "")
    seq = {}
    for r in rows:
        seq[r["group"]] = seq.get(r["group"], 0) + 1
        r["seq"] = "%s.%d" % (r["group"], seq[r["group"]])
    return rows


def render(rows):
    cell = lambda s: _text(s).replace("|", "\\|")
    n = len(rows)
    out = ["# Open owner questions - sequenced list (v1)", "",
           f"{n} open questions, numbered in the order to answer them: the {len([r for r in rows if r['group'] == 'S1'])}"
           " that block the start of P1 first. Sources: owner-question state v4 (TBD_OWNER rows) and the A9.7 lane "
           "questions rolled up in the F9 freeze candidate. Answer by number (e.g. 'S1.3: ...'); answers are recorded as "
           "a new owner-decision addendum. 'Proposed' is the recorder's proposal where one exists, never an answer.", "",
           "| Group | Topic | Count | Answered |", "|---|---|---|---|"]
    for g, t in GROUPS:
        sub = [r for r in rows if r["group"] == g]
        out.append(f"| {g} | {t} | {len(sub)} | {len([r for r in sub if r['answered']])} |")
    for g, t in GROUPS:
        sub = [r for r in rows if r["group"] == g]
        if not sub:
            continue
        out += ["", f"## {g} - {t}", "", "| # | ID | Question | Proposed | Source | Owner answer |", "|---|---|---|---|---|---|"]
        out += [f"| {r['seq']} | {r['id']} | {cell(r['question'])} | {cell(r['proposed'])} | {cell(r['source'])} | "
                f"{cell(r['answered']) or 'OPEN'} |"
                for r in sub]
    return "\n".join(out) + "\n"


def render_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["seq", "group", "id", "question", "proposed", "blocks", "source", "owner_answer"])
    for r in rows:
        w.writerow([r["seq"], r["group"], r["id"], r["question"], r["proposed"], r["blocks"], r["source"], r["answered"]])
    return buf.getvalue()


def main():
    rows = build()
    outs = {OUT_MD: render(rows), OUT_CSV: render_csv(rows)}
    if "--check" in sys.argv:
        bad = [p.name for p, t in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            raise SystemExit("stale: %s" % bad)
        print("owner-question sequenced list: current (%d questions)" % len(rows))
        return
    for p, t in outs.items():
        p.write_text(t, encoding="utf-8")
    print("wrote %d questions" % len(rows))


if __name__ == "__main__":
    main()
