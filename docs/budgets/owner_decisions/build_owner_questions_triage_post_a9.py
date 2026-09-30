"""Post-A9 triage of the OPEN owner questions (owner sequence 2026-09-30).

Reads owner_questions_state_v2.json (read-only, sha256-pinned) and assigns every OPEN row to exactly one tier by what it
blocks in the owner's post-A9 sequence: P1 ICP bench -> P2 impedance map -> P3 coupled thermal -> P4 anode, with mass/Xe
closure, comparison-campaign design and governance alongside. The tier is a recorder's ordering proposal, not a decision;
no question is answered here and the state v2 file is not changed.

    python docs/budgets/owner_decisions/build_owner_questions_triage_post_a9.py          # write
    python docs/budgets/owner_decisions/build_owner_questions_triage_post_a9.py --check  # verify outputs are current
"""
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "owner_questions_state_v2.json"
OUT_JSON = HERE / "owner_questions_triage_post_a9_v1.json"
OUT_MD = HERE / "OWNER_QUESTIONS_TRIAGE_POST_A9.md"
OUT_CSV = HERE / "owner_questions_triage_post_a9_v1.csv"

TIERS = [
    ("T1_P1_ICP_BENCH", "Answer first: gates the P1 ICP electron-source bench (ICP-45)", [
        ("OQ-VI-03", "fixes the topology of the article the bench builds"),
        ("OQ-VI-05", "decides whether the Ar engineering-only topology check is part of the bench"),
        ("OQ-A907-02", "ICP-45 needs a registered I_d,max"),
        ("ICPQ-06", "isolation practice for any ICP gas line crossing a potential difference on the bench"),
        ("OQ-RFQ-06", "the bench needs a 13.56 MHz generator; a mains-fed laboratory unit is the proposed ground source"),
        ("OQ-RFQ-07", "no bench hardware can be quoted until the owner decides who dispatches the RFQs"),
        ("OQ-RFQ-02", "Ar-path flow-controller ranges for the engineering-only bench gas"),
        ("OQ-RFQ-10", "optional ICP capped-port controller in the bench gas RFQ"),
    ]),
    ("T2_AFTER_P2_IMPEDANCE_MAP", "Answer after P2 data: the question itself depends on the measured impedance envelope", [
        ("ICPQ-10", "total ICP heat-load bound uses P_fwd,max from the characterized mismatch envelope"),
        ("ICPQ-11", "k_RF applies to V_ant,peak at the characterized mismatch envelope"),
    ]),
    ("T3_P3_P4_THERMAL_ANODE_RULES", "Answer before P3/P4 start; closure still waits for P1/P2 data", [
        ("OQ-A910-06", "interim 600 W RF-path heat allocation until P2 re-derives ICP-36"),
        ("OQ-A907-03", "where the >= 50 K rule is tested (bounding corner vs nominal + prereg uncertainty)"),
        ("OQ-A907-05", "provisional supplier continuous ratings as limits for the >= 50 K rule"),
        ("OQ-A907-09", "scope of the row-86 20 % heat-load margin (dissipated only vs all loads)"),
        ("OQ-A907-10", "treatment of the heuristic worst-case search in thermal verdicts"),
        ("OQ-A907-04", "coil conductor (plain Cu vs Ni-clad) sets coil I^2R in the thermal model"),
        ("OQ-A907-06", "spacecraft-mount conducted-heat interface at the searched corners"),
        ("OQ-A907-08", "exterior coating temperature limit on the Hall body"),
    ]),
    ("T4_MASS_XE_CLOSURE", "LOCK-1 mass and Xe closure; does not gate P1-P4", [
        ("XA9Q-01", "row-48 Xe cases: loaded vs usable (duplicate group DUP-XE-CASE)"),
        ("OQ-A910-01", "one reading to govern both the Xe ledger and the mass BOM (DUP-XE-CASE)"),
        ("MQ-09", "row-48 cases incl. reserve, residual on top (DUP-XE-CASE)"),
        ("XA9Q-02", "per-start ignition dwells 3 vs 2 (duplicate group DUP-DWELL)"),
        ("OQ-A907-01", "ignition attempts 3 vs 2 (DUP-DWELL)"),
        ("XA9Q-03", "row-96 flow-class term booking"),
        ("XA9Q-04", "ground-test Xe supply margin"),
        ("XA9Q-06", "retire the 75 bar MEOP proposal in favour of a quotation-based MEOP"),
        ("XA9Q-07", "row-6 Xe mode applies to the hall_icp_neutralizer flight configuration"),
        ("OQ-RFQ-09", "MEOP basis in the tank RFQ"),
        ("MQ-01", "row-54 allocations MEV vs CBE level"),
        ("MQ-02", "4 kg reserve vs row-52 20 % margin"),
        ("MQ-03", "Hall head+magnet allocation below the 3.504 kg floor"),
        ("MQ-04", "Hall PPU allocation below the 5.0 kg analog floor"),
        ("MQ-05", "Xe hardware allocation below the 5.044 kg floor"),
        ("MQ-06", "split controls and harness"),
        ("MQ-07", "map the A9 items row 54 does not name"),
        ("MQ-08", "H2-7 Xe analog value governs"),
        ("MQ-10", "dry mass > 40 kg under the evidence floors: closure path"),
        ("OQ-A907-07", "flight C1 integration now or deferred"),
    ]),
    ("T5_COMPARISON_CAMPAIGN_DESIGN", "LOCK-1 C1-vs-ICP comparison campaign design; after P1 shows the ICP is viable", [
        ("ICPQ-03", "both downstream modules on the moving platform"),
        ("ICPQ-08", "B(z) mapping rule with RF energized"),
        ("ICPQ-09", "plume interception reported inside the system boundary"),
        ("OQ-A910-05", "matched sham must present the local-match service-line parasitics"),
        ("OQ-A910-03", "peak-sampled ledger admissible for the 1.5 kW gate"),
        ("OQ-A910-02", "assign producing stage and decision quantity to 98 validation-input fields"),
        ("OQ-VI-04", "ICP-neutralizer lifetime and cycle requirement"),
        ("OQ-RFQ-01", "spare quantities"),
        ("OQ-RFQ-03", "Xe reference-path MFC quoted now or after the reference point is registered"),
        ("OQ-RFQ-04", "C1 start/diode flow retained"),
        ("OQ-RFQ-08", "Option B open-design stand comparison quote"),
        ("XA9Q-05", "G-XE ICP feed filter/getter (after evidence)"),
    ]),
    ("T6_GOVERNANCE", "Record-keeping; answerable any time", [
        ("OQ-A910-04", "M16 v3 JSON location (already on main at the proposed path since checkpoint 3)"),
        ("M16-V3-Q-01", "M16 v3 blocking items, role owners, responsible engineers"),
        ("OQ-INT-01", "relation of the A9-04 UB-DQ ids to the A9-01 DQ-HI ids"),
        ("OQ-INT-02", "in-file sha256 pins between A9 deliverables"),
    ]),
]

DUPLICATES = {
    "DUP-XE-CASE": ["XA9Q-01", "OQ-A910-01", "MQ-09"],
    "DUP-DWELL": ["XA9Q-02", "OQ-A907-01"],
}


def build():
    raw = STATE.read_bytes()
    state = json.loads(raw)
    open_rows = {r["id"]: r for r in state["rows"] if r["status"] == "OPEN"}
    assigned = [qid for _, _, items in TIERS for qid, _ in items]
    if len(assigned) != len(set(assigned)):
        raise SystemExit("triage: a question is assigned to more than one tier")
    if set(assigned) != set(open_rows):
        raise SystemExit(f"triage: tiers do not cover the OPEN set exactly; missing {sorted(set(open_rows) - set(assigned))}, "
                         f"not open {sorted(set(assigned) - set(open_rows))}")
    for group in DUPLICATES.values():
        if not set(group) <= set(assigned):
            raise SystemExit(f"triage: duplicate group names an unassigned id {group}")
    dup_of = {q: g for g, qs in DUPLICATES.items() for q in qs}
    tiers = []
    for tid, title, items in TIERS:
        tiers.append({"tier": tid, "title": title, "questions": [{
            "id": qid, "no": open_rows[qid]["no"], "lane": open_rows[qid].get("lane", ""),
            "question": open_rows[qid]["question"], "proposed": open_rows[qid].get("proposed", ""),
            "needed_by_as_recorded": open_rows[qid].get("needed_by", ""), "why_this_tier": why,
            "duplicate_group": dup_of.get(qid, ""),
        } for qid, why in items]})
    return {
        "schema": "abep.owner_questions_triage.v1",
        "id": "owner_questions_triage_post_a9_v1",
        "status": "RECORDER_PROPOSAL_NOT_A_DECISION",
        "basis": "owner sequence 2026-09-30: merge PR #33 -> clean post-A9 baseline (main 20f14d8) -> triage owner questions -> "
                 "P1 ICP bench -> P2 impedance map -> P3 coupled thermal redesign -> P4 anode design; P1/P2 data precede any "
                 "P3/P4 closure",
        "source": {"path": "docs/budgets/owner_decisions/owner_questions_state_v2.json",
                   "sha256": hashlib.sha256(raw).hexdigest(), "open_count": len(open_rows)},
        "rule": "every OPEN row of state v2 is in exactly one tier; nothing is answered or changed here; answers are recorded as "
                "new owner-decision addenda and applied through a state v3",
        "duplicate_groups": DUPLICATES,
        "counts": {t["tier"]: len(t["questions"]) for t in tiers},
        "tiers": tiers,
    }


def render_md(doc):
    out = ["# Open owner questions — post-A9 triage (v1)", "",
           "Recorder's proposal, **not a decision**. This file orders the "
           f"{doc['source']['open_count']} OPEN questions of `owner_questions_state_v2.json` "
           f"(sha256 `{doc['source']['sha256'][:12]}…`) by what they block in the owner's post-A9 sequence: "
           "P1 ICP bench → P2 impedance map → P3 coupled thermal → P4 anode. It answers nothing, and state v2 is unchanged.", "",
           "Duplicate groups (one answer should settle each group): "
           + "; ".join(f"**{g}** = {', '.join(qs)}" for g, qs in doc["duplicate_groups"].items()) + ".", "",
           "| Tier | Count |", "|---|---|"]
    out += [f"| {t['title']} | {len(t['questions'])} |" for t in doc["tiers"]]
    for t in doc["tiers"]:
        out += ["", f"## {t['title']}", "", "| # | ID | Question | Proposed (as recorded) | Why this tier |", "|---|---|---|---|---|"]
        for q in t["questions"]:
            cell = lambda s: " ".join(str(s).split()).replace("|", "\\|")
            dup = f" ({q['duplicate_group']})" if q["duplicate_group"] else ""
            out.append(f"| {q['no']} | {q['id']}{dup} | {cell(q['question'])} | {cell(q['proposed'])} | {cell(q['why_this_tier'])} |")
    return "\n".join(out) + "\n"


def render_csv(doc):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["tier", "no", "id", "lane", "duplicate_group", "question", "proposed", "needed_by_as_recorded", "why_this_tier"])
    for t in doc["tiers"]:
        for q in t["questions"]:
            w.writerow([t["tier"], q["no"], q["id"], q["lane"], q["duplicate_group"], q["question"], q["proposed"],
                        q["needed_by_as_recorded"], q["why_this_tier"]])
    return buf.getvalue()


def main():
    doc = build()
    outputs = {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc), OUT_CSV: render_csv(doc)}
    if "--check" in sys.argv:
        stale = [p.name for p, s in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != s]
        if stale:
            raise SystemExit(f"triage outputs stale: {stale}")
        print("owner-question triage: current")
        return
    for p, s in outputs.items():
        p.write_text(s, encoding="utf-8")
    print(f"wrote triage: {doc['counts']}")


if __name__ == "__main__":
    main()
