"""Generate the derived values, the per-architecture 'what evidence to acquire next' ranking and the generated
sections of FAILURE_TREES.md from the authored failure_trees_v1.json.

    python docs/architecture_comparison/failure_tree/derive_failure_tree.py          # rewrite generated parts
    python docs/architecture_comparison/failure_tree/derive_failure_tree.py --check  # exit 1 if anything is stale

Pure and deterministic: no network, no randomness, no Hall model. Physical constants come from scipy.constants
(CODATA) and the RFP numbers from abep_sim/constants.py; every other input is written below next to its source id
(see the 'sources' list in the JSON). Outputs are rounded to 6 significant figures so that a CODATA revision in a
later scipy does not change them. The ranking rule is the one stated in the JSON ('ranking_rule'); this script only
counts, it applies no weights.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
JSON_PATH = HERE / "failure_trees_v1.json"
MD_PATH = HERE / "FAILURE_TREES.md"
GENERATOR = "docs/architecture_comparison/failure_tree/derive_failure_tree.py"
COST_RANK = {"literature": 0, "analysis": 1, "measurement": 2}
ARCHS = ("hall_only", "rf_hall", "ecr_hall")


def _sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


def derived_values() -> dict:
    """Every number here is arithmetic on a stated input; each input names its source."""
    import scipy.constants as sc
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from abep_sim.constants import RFP, AMU, M_SPECIES

    m_e, e, eps0 = sc.m_e, sc.e, sc.epsilon_0

    def b_ecr(f):  # resonance: e|B|/m_e = 2 pi f
        return 2 * math.pi * f * m_e / e

    def n_cut(f):  # cutoff: omega_p = 2 pi f
        return eps0 * m_e * (2 * math.pi * f) ** 2 / e ** 2

    def rel(a, b):
        return _sig((a - b) / b, 4)

    vals = []
    for f, fid, fsrc, stated in [
        (2.45e9, "2.45GHZ", "S-TISAEV2023A (2.45 GHz microwave cathode) and S-FOSTER2006 (first-generation HiPEP)",
         {"B": (0.0875, "S-TISAEV2023A pdf p. 4: 87.5 mT"), "n": (7.4e16, "S-TISAEV2023A pdf p. 4: 7.4e16 m^-3")}),
        (5.8e9, "5.8GHZ", "S-DIAMANT2009 (critical density quoted at 5.8 GHz)",
         {"n": (4e17, "S-DIAMANT2009 Sec. V pdf p. 4: 4x10^17 m^-3")}),
        (5.85e9, "5.85GHZ", "S-FOSTER2006 (second-generation HiPEP)", {}),
    ]:
        B, n = b_ecr(f), n_cut(f)
        if fid != "5.8GHZ":
            vals.append({"id": f"D-ECR-B-{fid}", "quantity": "ECR resonance field |B| = 2 pi f m_e / e",
                         "value": _sig(B), "unit": "T", "evidence_class": "model-derived",
                         "inputs": {"f_Hz": f, "frequency_source": fsrc, "constants": "scipy.constants m_e, e"},
                         "cross_check": ({"source_stated": stated["B"][0], "where": stated["B"][1], "rel_diff": rel(B, stated["B"][0])}
                                         if "B" in stated else None),
                         "note": "Frequency is one used by the cited source, not a Vyovrinda design value."})
        vals.append({"id": f"D-ECR-NC-{fid}", "quantity": "Cutoff (critical) electron density n_c = epsilon_0 m_e (2 pi f)^2 / e^2",
                     "value": _sig(n), "unit": "m^-3", "evidence_class": "model-derived",
                     "inputs": {"f_Hz": f, "frequency_source": fsrc, "constants": "scipy.constants epsilon_0, m_e, e"},
                     "cross_check": ({"source_stated": stated["n"][0], "where": stated["n"][1], "rel_diff": rel(n, stated["n"][0])}
                                     if "n" in stated else None),
                     "note": "Low-field-side O/X-mode cutoff; right-hand waves launched from the high-field side can propagate above it."})

    b245 = b_ecr(2.45e9)
    for gid, bg, where in [("P5N2", 130.0, "hallthruster_bridge/cases/p5_n2.json source field: 'peak radial B 130 G' (Brabston 2025 Table 2)"),
                           ("P5XE", 162.5, "hallthruster_bridge/cases/p5_xenon.json source field: 'peak radial B 162.5 G' (Brabston 2025 Table 4)")]:
        vals.append({"id": f"D-RATIO-BECR-{gid}", "quantity": "Ratio of the 2.45 GHz ECR resonance field to the P5 peak radial field",
                     "value": _sig(b245 / (bg * 1e-4), 4), "unit": "1", "evidence_class": "model-derived",
                     "inputs": {"B_ecr_T": _sig(b245), "B_hall_peak_G": bg, "B_hall_source": "S-BRABSTON2025 via " + where},
                     "cross_check": None,
                     "note": "Illustrative scale only: P5 is a 5-kW-class literature thruster, not the Vyovrinda Hall circuit."})

    fire_h = RFP.ignition_hours
    vals.append({"id": "D-XE-PER-0.1MGPS-15000H", "quantity": "Xe mass consumed per 0.1 mg/s of cathode flow over the RFP firing hours",
                 "value": _sig(0.1e-6 * fire_h * 3600.0), "unit": "kg", "evidence_class": "model-derived",
                 "inputs": {"mdot_mg_s": 0.1, "firing_hours": fire_h, "firing_hours_source": "abep_sim/constants.py RFP.ignition_hours"},
                 "cross_check": None,
                 "note": "Per-unit sensitivity (scales linearly with cathode flow); not an operating point."})

    # Source-consistency check of S-DIAMANT2009 'about 8 kg' (0.5 sccm Xe, 5 years).
    t_std, p_std = sc.zero_Celsius, sc.atm          # sccm reference: 0 C, 1 atm (assumed; the source does not state it)
    m_xe_kg_mol = M_SPECIES["Xe"] / AMU * 1e-3      # abep_sim/constants.py (131.3 u)
    mol_s = 0.5 * 1e-6 * p_std / (sc.R * t_std) / 60.0
    years_h = 5 * 365.25 * 24                      # Julian years (assumed)
    m_kg = mol_s * m_xe_kg_mol * years_h * 3600.0
    vals.append({"id": "D-XE-DIAMANT-CHECK", "quantity": "Xe mass for 0.5 sccm continuous cathode flow over 5 years (reproduces the source's estimate)",
                 "value": _sig(m_kg), "unit": "kg", "evidence_class": "model-derived",
                 "inputs": {"flow_sccm": 0.5, "years": 5, "sccm_reference": "273.15 K, 101325 Pa (assumed; not stated by the source)",
                            "year_length_h": 8766.0, "Xe_molar_mass_kg_mol": _sig(m_xe_kg_mol), "flow_source": "S-DIAMANT2009 Sec. V pdf p. 4"},
                 "cross_check": {"source_stated": 8.0, "where": "S-DIAMANT2009 Sec. V pdf p. 4: 'about 8 kg'", "rel_diff": rel(m_kg, 8.0)},
                 "note": "Checks the source's arithmetic only; 0.5 sccm is the source's notional flow, not a Vyovrinda value."})

    vals.append({"id": "D-RFP-FIRING-FRACTION", "quantity": "Firing hours / mission hours",
                 "value": _sig(RFP.ignition_hours / RFP.mission_hours, 4), "unit": "1", "evidence_class": "model-derived",
                 "inputs": {"firing_hours": RFP.ignition_hours, "mission_hours": RFP.mission_hours,
                            "source": "abep_sim/constants.py RFP.ignition_hours, RFP.mission_hours"},
                 "cross_check": None,
                 "note": "Below 1, so the thruster is off for part of the mission and must restart; the restart count is TBD (owner)."})
    return {"generated_by": GENERATOR,
            "constants": {"source": "scipy.constants (CODATA) for m_e, e, epsilon_0, R, zero_Celsius, atm; abep_sim/constants.py for RFP, AMU, M_SPECIES",
                          "rounding": "6 significant figures (ratios and fractions 4)"},
            "values": vals}


def rank(doc: dict) -> dict:
    gate_order = [g["id"] for g in doc["hard_gates"]]
    actions = doc["actions"]
    out = {}
    for arch in ARCHS:
        nodes = [n for n in doc["nodes"] if arch in n["architectures"] and n["decision_state"] == "open"]
        ranked, blocked = [], []
        for a in actions:
            by = {"decides": [], "contributes": [], "informs": []}
            for n in nodes:
                for na in n["actions"]:
                    if na["action"] == a["id"]:
                        by[na["effect"]].append(n["id"])
            touched = by["decides"] + by["contributes"] + by["informs"]
            if not touched:
                continue
            if a["blocked_by"]:
                blocked.append({"action": a["id"], "blocked_by": list(a["blocked_by"]),
                                "nodes_touched": [n["id"] for n in nodes if n["id"] in touched]})
                continue
            gset = {g for n in nodes if n["id"] in by["decides"] for g in n["decision_quantity"]["gates"]}
            ranked.append({"action": a["id"], "kind": a["kind"], "n_decides": len(by["decides"]),
                           "n_gates_decided": len(gset), "n_contributes": len(by["contributes"]),
                           "n_informs": len(by["informs"]), "gates_decided": [g for g in gate_order if g in gset],
                           "nodes_decided": by["decides"], "nodes_contributed": by["contributes"],
                           "nodes_informed": by["informs"]})
        ranked.sort(key=lambda r: (-r["n_decides"], -r["n_gates_decided"], -r["n_contributes"], -r["n_informs"],
                                   COST_RANK[r["kind"]], r["action"]))
        for i, r in enumerate(ranked, 1):
            r_ordered = {"rank": i}
            r_ordered.update(r)
            ranked[i - 1] = r_ordered
        out[arch] = {"n_nodes": len(nodes), "ranked": ranked, "blocked": blocked}
    return {"generated_by": GENERATOR, "rule_id": doc["ranking_rule"]["id"], "per_architecture": out}


def status_counts(doc: dict, arch: str) -> dict:
    c = {"supported": 0, "contradicted": 0, "unknown": 0}
    for n in doc["nodes"]:
        if arch in n["architectures"]:
            c[n["evidence_status"]] += 1
    return c


def md_sections(doc: dict) -> dict:
    classes = {c["id"]: c for c in doc["failure_classes"]}
    titles = {a["id"]: a["title"] for a in doc["actions"]}
    sec = {}
    lines = []
    for arch in ARCHS:
        c = status_counts(doc, arch)
        nodes = [n for n in doc["nodes"] if arch in n["architectures"]]
        lines.append(f"### `{arch}` ({len(nodes)} nodes: {c['supported']} supported, {c['contradicted']} contradicted, "
                     f"{c['unknown']} unknown; all decision_state = open)")
        lines.append("")
        lines.append("| class | node | failure path | evidence status | gates | cheapest resolution | resolve by | analysis needs admitted Hall closure |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for fc in doc["failure_classes"]:
            if arch not in fc["applies_to"]:
                continue
            for n in nodes:
                if n["failure_class"] != fc["id"]:
                    continue
                cond = " (conditional)" if n.get("condition") else ""
                lines.append(f"| {classes[fc['id']]['name']} | {n['id']} | {n['title']}{cond} | {n['evidence_status']} | "
                             f"{', '.join(n['decision_quantity']['gates'])} | {' + '.join(n['cheapest_resolution'])} | "
                             f"{n['resolve_by_milestone']} | {'yes' if n['analysis_requires_admitted_hall_closure'] else 'no'} |")
        lines.append("")
    sec["trees"] = "\n".join(lines).rstrip() + "\n"

    lines = []
    for arch in ARCHS:
        r = doc["ranked_next_evidence"]["per_architecture"][arch]
        lines.append(f"### `{arch}` ({r['n_nodes']} open nodes)")
        lines.append("")
        lines.append("| rank | action | kind | decides | gates decided | contributes | informs |")
        lines.append("|---|---|---|---|---|---|---|")
        for x in r["ranked"]:
            lines.append(f"| {x['rank']} | {x['action']} ({titles[x['action']]}) | {x['kind']} | {x['n_decides']} | "
                         f"{x['n_gates_decided']} ({', '.join(x['gates_decided']) or '-'}) | {x['n_contributes']} | {x['n_informs']} |")
        for b in r["blocked"]:
            lines.append(f"| blocked | {b['action']} ({titles[b['action']]}) | not ranked | - | - | - | touches {len(b['nodes_touched'])} |")
        lines.append("")
    sec["ranking"] = "\n".join(lines).rstrip() + "\n"

    lines = ["| id | quantity | value | unit | cross-check |", "|---|---|---|---|---|"]
    for v in doc["derived_values"]["values"]:
        cc = v.get("cross_check")
        ccs = f"{cc['source_stated']} ({cc['where']}); rel. diff {cc['rel_diff']}" if cc else "-"
        lines.append(f"| {v['id']} | {v['quantity']} | {v['value']} | {v['unit']} | {ccs} |")
    sec["derived"] = "\n".join(lines) + "\n"
    return sec


def build(doc: dict) -> tuple[str, dict]:
    doc = json.loads(json.dumps(doc))
    doc["derived_values"] = derived_values()
    doc["ranked_next_evidence"] = rank(doc)
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n", md_sections(doc)


def splice(md: str, sections: dict) -> str:
    for name, body in sections.items():
        b, e = f"<!-- BEGIN GENERATED:{name} -->", f"<!-- END GENERATED:{name} -->"
        i, j = md.index(b), md.index(e)
        md = md[: i + len(b)] + "\n" + body + md[j:]
    return md


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the JSON or the Markdown generated sections are stale")
    a = ap.parse_args(argv)
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    new_json, sections = build(doc)
    md = MD_PATH.read_text(encoding="utf-8")
    new_md = splice(md, sections)
    if a.check:
        stale = [p.name for p, old, new in ((JSON_PATH, JSON_PATH.read_text(encoding="utf-8"), new_json), (MD_PATH, md, new_md)) if old != new]
        if stale:
            print("stale:", ", ".join(stale), "- run", GENERATOR)
            return 1
        print("failure tree generated sections up to date")
        return 0
    JSON_PATH.write_text(new_json, encoding="utf-8")
    MD_PATH.write_text(new_md, encoding="utf-8")
    print("wrote", JSON_PATH.relative_to(ROOT), "and", MD_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
