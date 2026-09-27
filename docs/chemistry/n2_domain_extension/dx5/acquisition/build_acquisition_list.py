"""Build the D-X5 closed-access acquisition list (fo_closed_access_acquisition, trigger T_PIVOT_CLOSED_ACCESS_ACQUISITION).

Deterministic. Reads only committed files:
  docs/chemistry/n2_domain_extension/dx5/acquisition/acquisition_inputs_v1.json  (hand-curated routes/metadata, this lane)
  docs/chemistry/n2_domain_extension/dx5/dx5_evidence_v1.json                    (D-X5 dossier, read-only)
  docs/chemistry/n2_domain_extension/domain_extension_requirements.json          (lane-01 E_req, read-only)
  docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json                               (owner disposition, read-only)
and writes acquisition_list_v1.json and ACQUISITION_LIST.md next to this file.

  python docs/chemistry/n2_domain_extension/dx5/acquisition/build_acquisition_list.py          # write
  python docs/chemistry/n2_domain_extension/dx5/acquisition/build_acquisition_list.py --check  # rebuild and compare

Missing inputs raise (no silent fallbacks). The ranking rubric and the equal-cost assumption are PROPOSED for the owner and
live in the inputs file, not in this code. This list changes no chemistry table, validity limit, pre-registration or v1
result and decides nothing: acquisition is an owner decision, and any use of acquired data is a controlled model-domain
change under QUESTION_A_DISPOSITION.json.
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
REL = {
    "inputs": "docs/chemistry/n2_domain_extension/dx5/acquisition/acquisition_inputs_v1.json",
    "dossier": "docs/chemistry/n2_domain_extension/dx5/dx5_evidence_v1.json",
    "requirements": "docs/chemistry/n2_domain_extension/domain_extension_requirements.json",
    "disposition": "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json",
}
OUT_JSON = os.path.join(HERE, "acquisition_list_v1.json")
OUT_MD = os.path.join(HERE, "ACQUISITION_LIST.md")
GAPS = ("P1", "P2", "P3")
L_KEY, SHARE_KEY = "60", "0.01"
# Hosts that are never acceptable as an acquisition route (checked on every URL in the output; the test repeats it).
SHADOW_PATTERNS = (r"sci-?hub", r"libgen", r"library\.?genesis", r"gen\.lib\.rus", r"z-?lib", r"zlibrary", r"singlelogin",
                   r"annas-?archive", r"booksc\.", r"\b1lib\.", r"\bb-ok\.", r"libstc", r"\bnexus\.", r"bookfi", r"ebookee")


def _load(key):
    path = os.path.join(ROOT, REL[key])
    if not os.path.exists(path):
        raise FileNotFoundError(f"required input missing: {REL[key]}")
    with open(path, "rb") as fh:
        raw = fh.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _get(d, keys, what):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            raise KeyError(f"{what}: missing key {k!r}")
        d = d[k]
    return d


def _require(entry, fields, what):
    for f in fields:
        if f not in entry:
            raise KeyError(f"{what}: missing field {f!r}")


def _urls(obj):
    s = json.dumps(obj)
    return re.findall(r"https?://[^\s\"';,)]+", s)


def build():
    inputs, h_in = _load("inputs")
    dossier, h_do = _load("dossier")
    req, h_rq = _load("requirements")
    od, h_od = _load("disposition")

    od_keys = inputs["owner_disposition"]
    approval = _get(od, od_keys["key"], "owner disposition")
    p4 = _get(od, od_keys["p4_key"], "owner disposition")
    if not str(approval).startswith("APPROVED"):
        raise ValueError("owner disposition does not approve closed-access acquisition")

    # Dossier candidate lists (the scope of this lane) and dossier DOIs.
    cand, dossier_doi = {}, {}
    for g in GAPS:
        pr = _get(dossier, ["priorities", g], "dossier")
        ids = _get(pr, ["legitimate_access_candidates_owner_decision"], f"dossier {g}")
        for i in ids:
            cand[i] = g
        for s in pr["sources"]:
            if s["id"] in ids:
                dossier_doi[s["id"]] = s["doi_or_url"]
    covered = [i for w in inputs["works"] for i in w["dossier_ids"]]
    if sorted(covered) != sorted(cand) or len(set(covered)) != len(covered):
        raise ValueError(f"inputs do not cover the dossier candidates exactly: missing {sorted(set(cand) - set(covered))}, "
                         f"extra {sorted(set(covered) - set(cand))}")

    per_table = _get(req, ["requirements", "per_table"], "requirements")

    def table_limits(table):
        t = _get(per_table, [table], "requirements per_table")
        last = t["source_last_data_point_eV"]
        bl = _get(t, ["by_limit", L_KEY], f"requirements {table}")
        env = bl.get("hold_envelope_E_req_eV") or bl.get("flat_sigma_E_req_eV")
        if env is None:
            raise KeyError(f"no E_req for {table} at L={L_KEY}")
        basis = "hold_envelope_E_req_eV" if bl.get("hold_envelope_E_req_eV") else "flat_sigma_E_req_eV"
        return float(last), float(env[SHARE_KEY]), basis

    rub = inputs["rubric"]["factors_per_work_and_gap"]
    cls_pts, reach_pts = rub["class_points"], rub["reach_points"]
    cost_default = inputs["rubric"]["cost"]["cost_units_default"]
    routes = inputs["publisher_routes"]

    works = []
    for w in inputs["works"]:
        _require(w, ["work_key", "dossier_ids", "doi", "crossref", "publisher_group", "oa_check",
                     "author_deposited_open_version", "targets"], w.get("work_key", "?"))
        for i in w["dossier_ids"]:
            if w["doi"].lower() not in dossier_doi[i].lower():
                raise ValueError(f"{w['work_key']}: DOI {w['doi']} not in dossier record {i}: {dossier_doi[i]}")
            if cand[i] != i.split(":")[0]:
                raise ValueError(f"{i}: gap mismatch")
        cr = w["crossref"]
        _require(cr, ["authors", "title", "journal", "volume", "pages", "year", "publisher", "landing"], w["work_key"])
        pub = routes[w["publisher_group"]]
        scored, value, max_e = [], 0, None
        for t in w["targets"]:
            _require(t, ["gap", "tables", "data_sought", "stated_energy_range_eV", "max_energy_eV", "evidence_class",
                         "class", "sole_located_source", "sole_rationale", "independent_of_current_lineage",
                         "direct_integral_cross_section", "quantity_confirmed", "quantity_confirmed_by"], w["work_key"])
            if t["gap"] not in GAPS:
                raise ValueError(f"{w['work_key']}: gap {t['gap']} outside P1-P3 (P4 is {p4})")
            lim = [table_limits(tb) for tb in t["tables"]]
            last = min(x[0] for x in lim)
            ereq = min(x[1] for x in lim)
            e = t["max_energy_eV"]
            if e is None:
                reach, reach_key = reach_pts["no_known_extension"], "no_known_extension"
            elif e >= ereq:
                reach, reach_key = reach_pts["reaches_E_req_1pct"], "reaches_E_req_1pct"
            elif e > last:
                reach, reach_key = reach_pts["extends_beyond_table_last_point_only"], "extends_beyond_table_last_point_only"
            else:
                reach, reach_key = reach_pts["no_known_extension"], "no_known_extension"
            parts = {
                "class": cls_pts[t["class"]],
                "reach": reach,
                "sole_located_source": rub["sole_located_source_points"] if t["sole_located_source"] else 0,
                "independent_of_current_lineage": rub["independent_of_current_lineage_points"] if t["independent_of_current_lineage"] else 0,
                "no_direct_integral_cross_section": 0 if t["direct_integral_cross_section"] else rub["no_direct_integral_cross_section_penalty"],
                "quantity_not_confirmed": 0 if t["quantity_confirmed"] else rub["quantity_not_confirmed_penalty"],
            }
            raw = sum(parts.values())
            gv = max(rub["per_gap_floor"], raw)
            value += gv
            if e is not None:
                max_e = e if max_e is None else max(max_e, e)
            scored.append(dict(t, table_last_source_point_eV=last, E_req_1pct_L60_eV=round(ereq, 3),
                               E_req_basis=sorted({x[2] for x in lim}), reach_class=reach_key,
                               score_parts=parts, gap_value=gv))
        cost = w.get("cost_units", cost_default)
        works.append({
            "work_key": w["work_key"],
            "dossier_ids": w["dossier_ids"],
            "gaps": sorted({t["gap"] for t in w["targets"]}),
            "citation": f"{cr['authors']}, \"{cr['title']}\", {cr['journal']} {cr['volume']}, {cr['pages']} ({cr['year']})",
            "doi": w["doi"],
            "doi_url": "https://doi.org/" + w["doi"],
            "doi_resolved_via": "Crossref REST API https://api.crossref.org/works/" + w["doi"] + " (2026-09-27)",
            "crossref": cr,
            "publisher": cr["publisher"],
            "publisher_group": w["publisher_group"],
            "oa_check": w["oa_check"],
            "access_routes": [
                {"route": "publisher_purchase", "url": cr["landing"], "detail": pub["purchase_route"],
                 "observation": pub["publisher_page_observation"]},
                {"route": "institutional_subscription", "url": None, "detail": pub["institutional_route"]},
                {"route": "document_delivery", "url": None, "detail": pub["document_delivery_route"]},
                {"route": "author_deposited_open_version", "url": None, "detail": w["author_deposited_open_version"]},
            ],
            "price_per_article": w.get("price_per_article", pub["price_shown"]),
            "cost_units": cost,
            "cost_evidence_class": w.get("cost_evidence_class", "assumed (equal cost per article; no price shown)"),
            "targets": scored,
            "value": value,
            "value_per_cost": round(value / cost, 6),
            "max_stated_energy_eV": max_e,
        })

    works.sort(key=lambda x: (-x["value_per_cost"], -(x["max_stated_energy_eV"] or 0), x["work_key"]))
    for n, w in enumerate(works, 1):
        w["priority"] = n

    groups = {}
    for w in works:
        groups.setdefault(w["publisher_group"], []).append(w["work_key"])

    out = {
        "id": "dx5_closed_access_acquisition_v1",
        "status": "DRAFT_PENDING_OWNER",
        "follow_on": inputs["follow_on"],
        "trigger": inputs["trigger"],
        "owner_disposition": {"id": inputs["owner_disposition"]["id"], "file": REL["disposition"],
                              "dx5_closed_access_sources": approval, "dx5_p4_dissociation": p4},
        "generated_by": "docs/chemistry/n2_domain_extension/dx5/acquisition/build_acquisition_list.py",
        "inputs_sha256": {REL["inputs"]: h_in, REL["dossier"]: h_do, REL["requirements"]: h_rq, REL["disposition"]: h_od},
        "scope_statement": ("Acquisition list only. Lists every closed-access primary the D-X5 dossier named as a legitimate-access "
                            "candidate (P1-P3; P4 stays DEFERRED). Nothing was downloaded from behind a paywall, no access control "
                            "was bypassed and nobody was contacted. This list changes no chemistry table, validity limit, "
                            "pre-registration or v1 result and decides nothing. Question A stays A-NO; reopening it is the owner's "
                            "judgement against the stated condition."),
        "milestones": {
            "supports": ["B"],
            "not_needed_for": "A (conditional selection runs on the od_hardware_pivot common-hardware experiment; this lane never holds it)",
            "supports_statement": ("Milestone B (physics-backed selection) needs a validated chemistry domain; acquiring these works is "
                                   "the only located route to evidence that could materially narrow the P1-P3 domain gaps that keep "
                                   "Question A closed."),
            "next_milestone_needs": [
                "Owner approval of each purchase or library request (budget TBD - requires the owner) and the price read in a browser (replace cost_units / price_per_article in the inputs and rebuild).",
                "Legitimate acquisition, then first-hand transcription of the target tables/figures with evidence class (measured / digitized / model-derived) and stated uncertainty, and an adversarial check as in D-X5.",
                "Owner judgement whether the new evidence materially closes the rotational / electronic / vibrational gaps (reopening condition of Question A).",
                "If reopened: a controlled model-domain change (version, HISTORY, separate pre-registration, rerun); a v2 scored on the same P5-N2 measurements is not new evidence for promotion.",
                "Milestone C is unaffected unless the chemistry domain changes.",
            ],
        },
        "rubric": inputs["rubric"],
        "publisher_routes": routes,
        "document_delivery_routes": inputs["document_delivery_routes"],
        "excluded_route_types": inputs["excluded_route_types"],
        "publisher_groups": groups,
        "works": works,
        "priority_order": [w["work_key"] for w in works],
        "dossier_candidates_covered": sorted(cand),
    }
    for u in _urls(out):
        for p in SHADOW_PATTERNS:
            if re.search(p, u, re.I):
                raise ValueError(f"shadow-library URL in output: {u}")
    return out


def render_md(d):
    L = []
    a = L.append
    a("# D-X5 closed-access acquisition list (DRAFT for owner review)")
    a("")
    a(f"Status **{d['status']}**. Follow-on `{d['follow_on']}`, trigger `{d['trigger']}`, owner disposition "
      f"`{d['owner_disposition']['id']}` (`{d['owner_disposition']['file']}`).")
    a(f"Generated by `{d['generated_by']}` from committed inputs (sha256 in `acquisition_list_v1.json`). Do not edit by hand.")
    a("")
    a(f"- Owner decision quoted: \"{d['owner_disposition']['dx5_closed_access_sources']}\"")
    a(f"- P4 (dissociation): \"{d['owner_disposition']['dx5_p4_dissociation']}\". It is not in this list.")
    a(f"- {d['scope_statement']}")
    a("")
    a("## Milestones")
    m = d["milestones"]
    a(f"- Supports: **{', '.join(m['supports'])}**. {m['supports_statement']}")
    a(f"- Not needed for: {m['not_needed_for']}.")
    a("- To reach the next milestone:")
    for x in m["next_milestone_needs"]:
        a(f"  - {x}")
    a("")
    a("## Priority order (PROPOSED rubric; equal cost assumed because no publisher showed a price)")
    a("")
    a("| # | work | gap(s) | publisher | DOI | max stated E (eV) | value | price shown |")
    a("|---|---|---|---|---|---|---|---|")
    for w in d["works"]:
        a(f"| {w['priority']} | {w['work_key']} | {', '.join(w['gaps'])} | {w['publisher']} | [{w['doi']}]({w['doi_url']}) | "
          f"{w['max_stated_energy_eV'] if w['max_stated_energy_eV'] is not None else 'unknown'} | {w['value']} | "
          f"{'not shown' if str(w['price_per_article']).startswith('not shown') else w['price_per_article']} |")
    a("")
    r = d["rubric"]
    a(f"Rubric status: {r['status']}. Value = {r['value']}; order = {r['order']}.")
    f = r["factors_per_work_and_gap"]
    a(f"Points: class {f['class_points']}; reach {{reaches E_req(1 %, L = 60 eV): {f['reach_points']['reaches_E_req_1pct']}, "
      f"beyond table end only: {f['reach_points']['extends_beyond_table_last_point_only']}, none/unknown: "
      f"{f['reach_points']['no_known_extension']}}}; sole located source +{f['sole_located_source_points']}; independent of the "
      f"current lineage +{f['independent_of_current_lineage_points']}; no direct integral cross section "
      f"{f['no_direct_integral_cross_section_penalty']}; quantity not confirmed {f['quantity_not_confirmed_penalty']}; per-gap "
      f"floor {f['per_gap_floor']}. Cost: {r['cost']['rule']}")
    a(f"Acquisition rule: {r['proposed_acquisition_rule']}")
    a("")
    a("Publisher groups (one institutional route may cover several): " +
      "; ".join(f"{k}: {', '.join(v)}" for k, v in d["publisher_groups"].items()) + ".")
    a("")
    a("## Entries")
    for w in d["works"]:
        a("")
        a(f"### {w['priority']}. {w['work_key']} ({', '.join(w['gaps'])})")
        a(f"- Citation: {w['citation']}")
        a(f"- DOI: [{w['doi']}]({w['doi_url']}); resolved via {w['doi_resolved_via']}")
        a(f"- Publisher: {w['publisher']}; dossier ids: {', '.join('`' + i + '`' for i in w['dossier_ids'])}")
        a(f"- Open-access check: " + "; ".join(f"{k}: {v}" for k, v in w["oa_check"].items()))
        a(f"- Price per article: {w['price_per_article']} (cost units {w['cost_units']}, {w['cost_evidence_class']})")
        a("- Access routes:")
        for rt in w["access_routes"]:
            u = f" <{rt['url']}>" if rt.get("url") else ""
            a(f"  - {rt['route']}{u}: {rt['detail']}")
        for t in w["targets"]:
            a(f"- Gap {t['gap']} - tables {', '.join('`' + x + '`' for x in t['tables'])}")
            a(f"  - Data sought: {t['data_sought']}")
            a(f"  - Stated range: {t['stated_energy_range_eV']} eV; evidence class: {t['evidence_class']}")
            a(f"  - Table last source point {t['table_last_source_point_eV']} eV; lane-01 E_req(1 %, L = 60 eV) "
              f"{t['E_req_1pct_L60_eV']} eV ({', '.join(t['E_req_basis'])}); reach: {t['reach_class']}")
            a(f"  - Sole located source: {t['sole_located_source']} ({t['sole_rationale']}); independent of current lineage: "
              f"{t['independent_of_current_lineage']}; direct ICS: {t['direct_integral_cross_section']}; quantity confirmed: "
              f"{t['quantity_confirmed']} ({t['quantity_confirmed_by']})")
            a(f"  - Score parts {t['score_parts']} -> gap value {t['gap_value']}")
    a("")
    a("## Document-delivery routes")
    for dd in d["document_delivery_routes"]:
        u = f" <{dd['url']}>" if dd.get("url") else ""
        a(f"- {dd['name']}{u}: {dd['observation']} Eligibility: {dd['eligibility']}")
    a("")
    a("## Excluded route types")
    for x in d["excluded_route_types"]:
        a(f"- {x}")
    a("")
    return "\n".join(L)


def main(argv):
    d = build()
    js = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    md = render_md(d)
    if "--check" in argv:
        ok = (open(OUT_JSON, encoding="utf-8").read() == js) and (open(OUT_MD, encoding="utf-8").read() == md)
        print("OK" if ok else "MISMATCH")
        return 0 if ok else 1
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        fh.write(js)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote", os.path.relpath(OUT_JSON, ROOT), os.path.relpath(OUT_MD, ROOT))
    print("priority:", ", ".join(d["priority_order"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
