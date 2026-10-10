"""DBF-1.2: the successor of DBF-1.1 proposed by the DCR-DBF1-001 resolution (A9.39 item 3; variable effective capture).

DBF-1.2 = DBF-1.1 with the upstream items DBF1-IN-01/02/04/05/06/07/08 replaced by the DCR-DBF1-001 selection and three
new items: DBF1-IN-09 (variable-capture mechanism), DBF1-OP-01 (AIR operating free-stream-flux window) and DBF1-OP-02
(altitude schedule). DBF1-BD-01/02/03 carry the resolution's dispositions. Every other item, rule and deficiency is copied
unchanged from the sha256-verified DBF-1.1 files, which are never edited (nor are DBF-1's).

Usage: python3 docs/baseline/DBF-1.2/build_dbf1_2.py            write the DBF-1.2 files
       python3 docs/baseline/DBF-1.2/build_dbf1_2.py --check    regenerate in memory, compare byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REL_OUT = "docs/baseline/DBF-1.2"
FILES = {"json": "dbf1_2_v1.json", "md": "DBF1_2_v1.md", "config": "dbf1_2_config_v1.json", "lock": "dbf1_2_lock_v1.json"}

PINS = {
    "dbf1_1_lock": ("docs/baseline/DBF-1.1/dbf1_1_lock_v1.json", "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8"),
    "dbf1_1": ("docs/baseline/DBF-1.1/dbf1_1_v1.json", "b8daa5bd5bb18b4fc92d6f65b0d93d0e70b33cd80d0f222cb9957ced3075c22b"),
    "dbf1_1_config": ("docs/baseline/DBF-1.1/dbf1_1_config_v1.json", "f16e07ba5b0c80e724dd53bb8d8a9b02298d8fb20ddac85a4f49ee799949d092"),
    "dcr_process": ("docs/baseline/DBF-1/DCR_PROCESS.md", "14f05a7b64968acf9b2a3bc53e5ff33bc83b4304ad284d58f35f27fcc5a04a91"),
    "prereg_v3": ("docs/baseline/DCR-001/dcr001_eval_prereg_v3.json", "c79ea6c110f46799c5c3aaab1b091519d13ee2bf7b7c03112236de05f8c4dbb9"),
    "resolution": ("docs/baseline/DCR-001/dcr001_resolution_v1.json", "RESOLUTION_SHA256"),
    "record": ("docs/baseline/DCR-001/dcr001_window_record_v1.json", "RECORD_SHA256"),
    "a9_39": ("docs/decisions/OD_2026_10_09_A9_39_ARCHITECTURE_CLOSED_OWNER_DECISIONS.md",
              "7c3880c3f2b5dedefcd66c0c8fbe0362b3aa199099183ec3d65c020bf48f2949"),
}


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_pinned(key: str) -> bytes:
    rel, want = PINS[key]
    b = (ROOT / rel).read_bytes()
    if sha_bytes(b) != want:
        raise SystemExit(f"REFUSED: {rel} sha256 {sha_bytes(b)} != pinned {want}")
    return b


def js(key: str):
    return json.loads(read_pinned(key))


def src(key: str, pointer: str | None = None) -> dict:
    d = {"path": PINS[key][0], "sha256": PINS[key][1]}
    if pointer:
        d["pointer"] = pointer
    return d


def item(base: dict, **kw) -> dict:
    out = {k: base[k] for k in ("id", "group")} if base else {}
    out.update(kw)
    return out


def build():
    lock = js("dbf1_1_lock")
    for k, f in (("dbf1_1", "dbf1_1_v1.json"), ("dbf1_1_config", "dbf1_1_config_v1.json")):
        if lock["files"][f] != PINS[k][1]:
            raise SystemExit(f"REFUSED: DBF-1.1 lock files.{f} != pinned")
    parent, pcfg, res = js("dbf1_1"), js("dbf1_1_config"), js("resolution")
    read_pinned("record")
    read_pinned("prereg_v3")
    if res["evidence"]["record"]["sha256"] != PINS["record"][1] or res["proposed_baseline"]["id"] != "DBF-1.2":
        raise SystemExit("REFUSED: the resolution does not name the pinned record / DBF-1.2")
    pb, r = res["proposed_baseline"], res["result"]
    up, vc, win = pb["config_upstream"], pb["variable_capture"], pb["operating_window"]
    ev = [src("resolution"), src("record"), src("prereg_v3")]
    label = r["selection_label"]
    unc_coef = ("compressor coefficients assumed (level 7) with bands; " +
                ("window holds at every unfavourable corner" if label == "ADMISSIBLE_ROBUST" else
                 "window holds at nominal coefficients; the unfavourable corners reduce it (record corners_screen)"))
    lineage = {
        "parent": "DBF-1.1", "parent_lock": src("dbf1_1_lock"), "parent_record": src("dbf1_1"),
        "dcr": "DCR-DBF1-001", "dcr_resolution": src("resolution"), "dcr_record": src("record"),
        "dcr_method": src("prereg_v3"), "authority": src("a9_39"),
        "rule": "DBF-1 and DBF-1.1 and every record computed on them stay immutable history; DBF-1.2 changes the upstream "
                "implementation (DBF1-IN-*) and adds the operating window / altitude schedule items only",
    }
    doc = copy.deepcopy(parent)
    doc["id"] = "DBF-1.2"
    doc["version"] = "1.2"
    doc["title"] = ("DBF-1.2 Design Baseline Freeze 1.2 - hall_icp_neutralizer (DCR-DBF1-001: variable-effective-capture "
                    "intake, AIR operating window and altitude schedule)")
    doc["date"] = "2026-10-09"
    doc["lineage"] = lineage
    doc["authority_rule"] = ("this JSON is authoritative; DBF1_2_v1.md restates it; dbf1_2_config_v1.json is the machine-readable "
                             "subset read through abep-config (abep_config::baseline::load_dbf1_2), pinned by dbf1_2_lock_v1.json")
    doc["generated_by"] = f"{REL_OUT}/build_dbf1_2.py"
    comp = r["compressor"]
    new = {
        "DBF1-IN-01": dict(name="upstream design vector (variable-capture intake, filter, compressor, plenum, P_set)",
                           value=f"{up['design_id']}", units="-", sources=ev, evidence_class="design selection (DCR-001 v3 ranking)",
                           quantity_type="model-derived", evidence_level="6", uncertainty=unc_coef,
                           status="FROZEN_FOR_EM", rationale=f"DCR-DBF1-001 resolution: {label}"),
        "DBF1-IN-02": dict(name="intake geometry (physical maximum aperture, segments, F1 channel node; d collapsed)",
                           value={"A_max_m2": up["area_m2"], "N_segments": vc["N_segments"], "L_over_d": up["L_over_d"],
                                  "phi": up["phi"], "candidate": up["candidate"],
                                  "channel_diameter": r["intake_geometry"]["channel_diameter"],
                                  "intake_wall_area_m2": r["intake_geometry"]["wall_area_2_phi_Amax_Ld_m2"]},
                           units="m^2; -; -; -", sources=ev + [{"path": "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1_core.json",
                                                                "sha256": "d397cb9348d06eafbe2e7cc3ee9ca035f97e8f423d63df8f42286ce75bc20854"}],
                           evidence_class="model-derived (F1 TPMC ROM, 10 admitted surface scenarios)", quantity_type="model-derived",
                           evidence_level="6", uncertainty="TPMC statistical SE; surface accommodation TBD (DI-1.3); structure TBD (F1Q-02)",
                           status="FROZEN_FOR_EM", rationale="DCR-DBF1-001 v3 selection"),
        "DBF1-IN-04": dict(name="filter case", value=up["filter"], units="-", sources=ev,
                           evidence_class="parametric sensitivity (architecture-context filter case)", quantity_type="assumed",
                           evidence_level="7", uncertainty="filter material / geometry TBD", status="FROZEN_ASSUMPTION",
                           rationale="DCR-DBF1-001 v3 selection"),
        "DBF1-IN-05": dict(name="compressor design (F3 design grid) and frozen coefficients",
                           value={"id": comp["id"], "f3_grid_index": comp["f3_grid_index"], **comp["design"],
                                  "coefficients": "DragCompressor code defaults frozen as engineering assumptions (assumed, level 7) "
                                                  "with the DCR-001 v1 bands and 8 unfavourable corners"},
                           units="-", sources=ev + [{"path": "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json",
                                                     "sha256": "74a52aa749e1d071f76957e4f9ef4929c9d8ab302b183da3c5a5d9ba8d6d6923",
                                                     "pointer": f"/design_grid/{comp['f3_grid_index']}"}],
                           evidence_class="model-derived (F3 DragCompressor family, coefficients assumed level 7)",
                           quantity_type="model-derived", evidence_level="6", uncertainty=unc_coef, status="FROZEN_FOR_EM",
                           rationale=f"DCR-DBF1-001 v3 selection; model mass {comp['m_model_max_kg']:.4g} kg, P_el <= {comp['P_el_max_W']:.4g} W"),
        "DBF1-IN-06": dict(name="plenum volume / wall / target pressure",
                           value={"V_m3": up["V_m3"], "wall_case": up["wall"], "P_set_Pa": up["P_set_Pa"]},
                           units="m^3; -; Pa", sources=ev, evidence_class="parametric design value", quantity_type="assumed",
                           evidence_level="7", uncertainty="wall case WALL-G0 (inert-lining bound)", status="FROZEN_ASSUMPTION",
                           rationale="DCR-DBF1-001 v3 selection"),
        "DBF1-IN-07": dict(name="feed-loop controller (normalized PI on plenum pressure)", value=up["controller"],
                           units="-; s; Hz; -", sources=ev, evidence_class="definition / parametric", quantity_type="assumed",
                           evidence_level="7", uncertainty="registered grid only", status="FROZEN_ASSUMPTION",
                           rationale="first (V, controller) in the registered order with class S at every window operating point"),
        "DBF1-IN-08": dict(name="window performance of the frozen design (DCR-001 v3 record)",
                           value={"worst_sustained_flow_ratio": r["delivered_flow"]["worst_sustained_flow_ratio"],
                                  "D_tot_max_N": r["drag"]["D_tot_max_N"], "P_compressor_el_max_W": comp["P_el_max_W"],
                                  "m_compressor_max_kg": comp["m_model_max_kg"],
                                  "x_O_delivered_min_max": r["delivered_flow"]["x_O_delivered_min_max"],
                                  "capture_efficiency_min_max_by_scenario": r["capture_efficiency_min_max_by_scenario"]},
                           units="-; N; W; kg; -; -", sources=ev, evidence_class="model-derived", quantity_type="model-derived",
                           evidence_level="6", uncertainty=unc_coef, status="COMPUTED_NOT_CHOSEN",
                           rationale="replaces the F7 values of DBF-1 / DBF-1.1"),
    }
    added = [
        {"id": "DBF1-IN-09", "group": "INTAKE_COMPRESSOR", "name": "variable-effective-capture mechanism",
         "value": vc, "units": "-; -; m^2; m^2; -; -", "sources": ev,
         "evidence_class": "design selection; closed-segment drag analytic bound (specular normal plate, verify)",
         "quantity_type": "model-derived", "evidence_level": "6",
         "uncertainty": "actuation, sealing and closed-segment drag to be verified on the EM", "status": "FROZEN_FOR_EM",
         "rationale": "A9.39 item 3; simplest evaluated mechanism attaining the best coverage (DCR-001 v3 mechanism rule)"},
        {"id": "DBF1-OP-01", "group": "OPERATING_CONCEPT", "name": "AIR operating free-stream-flux window",
         "value": {k: win[k] for k in ("flux_coordinate", "Phi_lo_kg_m2_s", "Phi_hi_kg_m2_s", "ratio", "Phi_adm_A4_at_ends")},
         "units": "-; kg m^-2 s^-1; kg m^-2 s^-1; -; kg m^-2 s^-1", "sources": ev,
         "evidence_class": "model-derived (admitted chain; conservation necessary condition for flow)",
         "quantity_type": "model-derived", "evidence_level": "6",
         "uncertainty": "TPMC scenario set carried (all 10 at every state); Hall efficiency not included (EM item)",
         "status": "FROZEN_FOR_EM", "rationale": "A9.39 items 2 / 3"},
        {"id": "DBF1-OP-02", "group": "OPERATING_CONCEPT", "name": "altitude schedule per registered solar / atmospheric condition",
         "value": {"admissible_altitude_nodes_km": win["altitude_schedule"], "uncovered_conditions": win["uncovered_conditions"]},
         "units": "km", "sources": ev, "evidence_class": "model-derived", "quantity_type": "model-derived",
         "evidence_level": "6", "uncertainty": "node resolution (180 / 195 / 215 / 230 km); interpolation is information only",
         "status": "FROZEN_FOR_EM", "rationale": "A9.39 item 2: altitude scheduled inside 180-230 km with solar activity"},
    ]
    n = 0
    items = []
    for it in doc["items"]:
        if it["id"] in new:
            n += 1
            nv = new[it["id"]]
            items.append({"id": it["id"], "group": it["group"], **nv,
                          "superseded_value": {"value": it["value"], "baseline": "DBF-1.1"}})
        else:
            items.append(it)
        if it["id"] == "DBF1-IN-08":
            items.extend(added)
    if n != len(new):
        raise SystemExit("REFUSED: not every changed item found exactly once")
    doc["items"] = items
    for d in doc["baseline_deficiencies"]:
        if d["id"] in pb["deficiency_updates"]:
            d["status"] = pb["deficiency_updates"][d["id"]]
            d["closure"] = {"by": "DCR-DBF1-001 (resolution v1)", "evidence": ev}
    if res.get("mass_transfer_request"):
        doc["mass_transfer_request"] = res["mass_transfer_request"]
    doc["change_control"] = dict(parent["change_control"],
                                 rule=parent["change_control"]["rule"] + "; DBF-1.2 is the successor proposed by the "
                                      "DCR-DBF1-001 resolution and is under the same DCR process")

    cfg = copy.deepcopy(pcfg)
    cfg["id"] = "dbf1_2_config_v1"
    cfg["baseline"] = "DBF-1.2"
    cfg["authoritative_record"] = f"{REL_OUT}/{FILES['json']}"
    cfg["note"] = ("machine-readable subset of dbf1_2_v1.json read by abep_config::baseline::load_dbf1_2; identical to "
                   "dbf1_1_config_v1.json except upstream (DBF1-IN-01..07), variable_capture (DBF1-IN-09), operating_window "
                   "(DBF1-OP-01 / 02), the deficiency lists and the lineage")
    scen = cfg["upstream"]["scenarios"]
    cfg["upstream"] = dict(up, scenarios=scen, items=[f"DBF1-IN-0{k}" for k in range(1, 8)] + ["DBF1-IN-09"])
    cfg["variable_capture"] = vc
    cfg["operating_window"] = win
    closed = [k for k, v in pb["deficiency_updates"].items() if v.startswith("CLOSED")]
    cfg["baseline_deficiencies"] = [x for x in pcfg["baseline_deficiencies"] if x not in pb["deficiency_updates"]]
    cfg["closed_deficiencies"] = pcfg["closed_deficiencies"] + closed
    cfg["transferred_deficiencies"] = [k for k, v in pb["deficiency_updates"].items() if not v.startswith("CLOSED")]
    cfg["lineage"] = {"parent": "DBF-1.1", "parent_lock_sha256": PINS["dbf1_1_lock"][1], "dcr": "DCR-DBF1-001",
                      "dcr_resolution_sha256": PINS["resolution"][1]}
    return doc, cfg


def dumps(o) -> bytes:
    return (json.dumps(o, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def fmt(v) -> str:
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    s = s.replace("|", "\\|")
    return s if len(s) <= 160 else s[:157] + "..."


def render_md(doc) -> bytes:
    lin = doc["lineage"]
    L = [f"# {doc['title']}", "",
         f"Authoritative record: `{FILES['json']}` (this page restates it). Machine-readable subset: `{FILES['config']}` "
         "(read through `abep_config::baseline::load_dbf1_2`). Hash lock: `dbf1_2_lock_v1.json`. Change control: "
         "`docs/baseline/DBF-1/DCR_PROCESS.md`.", "",
         "## Lineage", "",
         f"- parent: DBF-1.1, lock `{lin['parent_lock']['sha256']}` (immutable; never edited); DBF-1 unchanged history",
         f"- change: {lin['dcr']}, resolution `{lin['dcr_resolution']['path']}` (`{lin['dcr_resolution']['sha256']}`), record "
         f"`{lin['dcr_record']['path']}`, method `{lin['dcr_method']['path']}`",
         f"- authority: `{lin['authority']['path']}` (A9.39 item 3)", "",
         "## Changed and added items", ""]
    for it in doc["items"]:
        if it["id"].startswith(("DBF1-IN-0", "DBF1-OP-")) and it["id"] != "DBF1-IN-03":
            L.append(f"- **{it['id']}** {it['name']}: {fmt(it['value'])} ({it['status']})")
    L += ["", "## Frozen items", "", "| id | item | value | units | evidence (class / type / level) | status |",
          "|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {fmt(it['name'])} | {fmt(it['value'])} | {fmt(it['units'])} | "
                 f"{fmt(it['evidence_class'])} / {it['quantity_type']} / {it['evidence_level']} | {it['status']} |")
    L += ["", "## Baseline deficiencies", "", "| id | items | category | status |", "|---|---|---|---|"]
    for d in doc["baseline_deficiencies"]:
        L.append(f"| {d['id']} | {', '.join(d['items'])} | {d['category']} | {fmt(d.get('status', 'OPEN'))} |")
    if doc.get("mass_transfer_request"):
        m = doc["mass_transfer_request"]
        L += ["", f"Mass-transfer request {m['id']}: {m['transfer_kg']:.4g} kg above {m['line']} ({m['allocation_kg']} kg) "
                  f"to the roll-up; status {m['status']}."]
    L += ["", "## Not", ""] + [f"- {x}" for x in doc["not"]]
    return ("\n".join(L) + "\n").encode("utf-8")


def outputs() -> dict:
    doc, cfg = build()
    out = {FILES["json"]: dumps(doc), FILES["md"]: render_md(doc), FILES["config"]: dumps(cfg)}
    lock = {"id": "dbf1_2_lock_v1", "baseline": "DBF-1.2", "locked": "2026-10-09",
            "note": "sha256 of the DBF-1.2 files (successor of DBF-1.1 proposed by the DCR-DBF1-001 resolution); any change "
                    "after this lock is a DCR with a new baseline version, never an edit",
            "files_relative_to": REL_OUT + "/",
            "files": {k: sha_bytes(v) for k, v in sorted(list(out.items()) + [("build_dbf1_2.py", Path(__file__).read_bytes())])},
            "lineage": {"parent_lock": PINS["dbf1_1_lock"][0], "parent_lock_sha256": PINS["dbf1_1_lock"][1],
                        "dcr": "DCR-DBF1-001", "dcr_resolution": PINS["resolution"][0],
                        "dcr_resolution_sha256": PINS["resolution"][1]},
            "pinned_sources": {PINS[k][0]: PINS[k][1] for k in sorted(PINS)},
            "pinned_profiles": {v["file"]: v["sha256"] for d in json.loads(out[FILES["config"]])["h1"]["bz_profiles"].values()
                                for v in d.values()}}
    out[FILES["lock"]] = dumps(lock)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    out = outputs()
    if a.check:
        stale = [k for k, v in out.items() if not (OUT / k).is_file() or (OUT / k).read_bytes() != v]
        if stale:
            print(f"STALE: {stale}")
            return 1
        print(f"OK: {len(out)} DBF-1.2 files current")
        return 0
    for k, v in out.items():
        (OUT / k).write_bytes(v)
    print(f"wrote {len(out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
