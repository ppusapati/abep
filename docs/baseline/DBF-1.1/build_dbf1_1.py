"""DBF-1.1: the first approved successor of DBF-1 (DCR-DBF1-002, coordinator ruling under A9.34; A9.38 P3).

DBF-1.1 = DBF-1 with exactly one change of value: DBF1-BZ-04 (simulation B(z) shape) BZ-P5B16 -> BZ-H1FE-V1, the FE-derived
H-1 field of the frozen electromagnet (hallthruster_bridge/bfield/h1_fe_v1/). DBF1-BD-05 is closed by it (a measured
map stays an engineering-model verification item). Every other item, rule and deficiency is copied unchanged from the
sha256-verified DBF-1 files, which are never edited.

Usage: python3 docs/baseline/DBF-1.1/build_dbf1_1.py            write the DBF-1.1 files
       python3 docs/baseline/DBF-1.1/build_dbf1_1.py --check    regenerate in memory, compare byte for byte
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
REL_OUT = "docs/baseline/DBF-1.1"
FILES = {"json": "dbf1_1_v1.json", "md": "DBF1_1_v1.md", "config": "dbf1_1_config_v1.json", "lock": "dbf1_1_lock_v1.json"}

# Parent baseline (immutable) and the change record, pinned.
PINS = {
    "dbf1_lock": ("docs/baseline/DBF-1/dbf1_lock_v1.json", "517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907"),
    "dbf1": ("docs/baseline/DBF-1/dbf1_v1.json", "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f"),
    "dbf1_config": ("docs/baseline/DBF-1/dbf1_config_v1.json", "5bd76159fb9761b5c47619fb42217f05c24841d7009067ac71dcedf731759864"),
    "dcr_process": ("docs/baseline/DBF-1/DCR_PROCESS.md", "14f05a7b64968acf9b2a3bc53e5ff33bc83b4304ad284d58f35f27fcc5a04a91"),
    "dcr_request": ("docs/baseline/DCR-002/dcr002_request_v1.json", "ab55635ac29e2900e4baa459bfbaae9e4334412066bebc1cc03f77f765fcfca9"),
    "dcr_approval": ("docs/baseline/DCR-002/dcr002_approval_v1.json", "1718ac8061720959ea52e66e18723c23c3ece8d8c44fcfa41249d4f852c9bb55"),
    "dcr_register": ("docs/baseline/DBF-1/dcr_register_v3.json", "db4f3fee53047e43319e3c382479fedff4dcc06700b973e78ecdf5445db0313b"),
    "fe_record": ("docs/hardware/h1_bz/h1_bz_fe_v1.json", "4da00b551e6d0776cd31d6ccdfba383fd7bfb9ffc9def21bcf8a59b92a4cfd42"),
    "fe_prereg": ("docs/hardware/h1_bz/h1_bz_fe_prereg_v4.json", "98fab01d030918e9385fce417a085e580e7c355973e9adf4bcab0e05b5434e9e"),
    "bz_manifest": ("hallthruster_bridge/bfield/h1_fe_v1/MANIFEST.json", "c797e679613e20948f0f24174db0c95bf0645592e6969363cc661bf1ab2be946"),
}
BZ_DIR = "hallthruster_bridge/bfield/h1_fe_v1"
# DBF-1.1 B(z) profiles: nominal at the two registered operating levels (DBF1-BZ-03) and the shape-uncertainty envelope.
PROFILES = {
    "nominal": {"BP-LO": "h1_fe_v1_Br_centerline_nominal_BP-LO.csv", "BP-HI": "h1_fe_v1_Br_centerline_nominal_BP-HI.csv"},
    "envelope": {"CORNER-A": "h1_fe_v1_Br_centerline_envelope_maxFWHM_CORNER-A_BP-HI.csv",
                 "CORNER-B": "h1_fe_v1_Br_centerline_envelope_minFWHM_CORNER-B_BP-HI.csv"},
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


def profiles(manifest: dict) -> dict:
    out = {}
    for role, d in PROFILES.items():
        out[role] = {}
        for k, f in d.items():
            m = manifest["files"].get(f)
            if m is None:
                raise SystemExit(f"REFUSED: {f} not in {PINS['bz_manifest'][0]}")
            got = sha_bytes((ROOT / BZ_DIR / f).read_bytes())
            if got != m["sha256"]:
                raise SystemExit(f"REFUSED: {BZ_DIR}/{f} sha256 {got} != manifest {m['sha256']}")
            out[role][k] = {"file": f"{BZ_DIR}/{f}", "sha256": got, "variant": m["variant"], "level": m["level"],
                            "NI_total_A": m["NI_total_A"], "B_peak_G": m["B_peak_G"], "mesh_level": m["mesh_level"]}
    return out


def build():
    lock = js("dbf1_lock")
    for k, f in (("dbf1", "dbf1_v1.json"), ("dbf1_config", "dbf1_config_v1.json")):
        if lock["files"][f] != PINS[k][1]:
            raise SystemExit(f"REFUSED: DBF-1 lock files.{f} != pinned")
    parent, pcfg = js("dbf1"), js("dbf1_config")
    appr, req, fe, man = js("dcr_approval"), js("dcr_request"), js("fe_record"), js("bz_manifest")
    if appr["dcr"] != "DCR-DBF1-002" or appr["request"]["sha256"] != PINS["dcr_request"][1]:
        raise SystemExit("REFUSED: the approval does not name the pinned DCR-DBF1-002 request")
    if fe["field_outcome"] != "FE_DERIVED_VERIFIED" or man["field_outcome"] != "FE_DERIVED_VERIFIED":
        raise SystemExit("REFUSED: the FE field is not FE_DERIVED_VERIFIED")
    prof = profiles(man)
    env = fe["uncertainty_envelope"]["BP-HI"]
    ex = fe["exact_levels_nominal_L3"]
    lineage = {
        "parent": "DBF-1", "parent_lock": src("dbf1_lock"), "parent_record": src("dbf1"),
        "dcr": "DCR-DBF1-002", "dcr_request": src("dcr_request"), "dcr_approval": src("dcr_approval"),
        "dcr_register": src("dcr_register"),
        "approval_authority": appr["authority"],
        "approval_conditions": appr["conditions"],
        "rule": "DBF-1 and every record computed on it stay immutable history; DBF-1.1 changes DBF1-BZ-04 only (plus the closure of DBF1-BD-05 it implies); surrogate and FE-field Hall records are never pooled",
    }

    doc = copy.deepcopy(parent)
    doc["id"] = "DBF-1.1"
    doc["version"] = "1.1"
    doc["title"] = "DBF-1.1 Design Baseline Freeze 1.1 - hall_icp_neutralizer (DCR-DBF1-002: FE-derived H-1 B(z))"
    doc["date"] = "2026-10-09"
    doc["lineage"] = lineage
    doc["authority_rule"] = ("this JSON is authoritative; DBF1_1_v1.md restates it; dbf1_1_config_v1.json is the machine-readable "
                             "subset the closure harness reads through abep-config (abep_config::baseline::load_dbf1_1), "
                             "pinned by dbf1_1_lock_v1.json")
    doc["hardware_configuration"] = dict(parent["hardware_configuration"], bz_shape_id="BZ-H1FE-V1",
                                         meaning="the envelope hardware configuration (geometry, bz_shape) of DBF-1.1; B_peak, "
                                                 "V_d and mdot are operating variables")
    doc["generated_by"] = f"{REL_OUT}/build_dbf1_1.py"
    n_changed = 0
    for it in doc["items"]:
        if it["id"] != "DBF1-BZ-04":
            continue
        n_changed += 1
        old = {k: it[k] for k in ("value", "evidence_class", "quantity_type", "evidence_level", "uncertainty", "status", "label")}
        it.clear()
        it.update({
            "id": "DBF1-BZ-04",
            "group": "MAGNETIC_TARGET",
            "name": "simulation B(z) shape (H-1 FE-derived field)",
            "value": "BZ-H1FE-V1",
            "units": "-",
            "profiles": prof,
            "sources": [src("fe_record"), src("fe_prereg"), src("bz_manifest"), src("dcr_request"), src("dcr_approval")],
            "evidence_class": "FE-derived (scikit-fem 10.0.2 axisymmetric nonlinear magnetostatics of the registered MC-1 circuit; FEMM-class per A9.14 F5-OQ-01); not measured, not FEMM",
            "quantity_type": "model-derived",
            "evidence_level": "6",
            "uncertainty": ("shape envelope over the registered assumption ranges (wall thickness, pole thickness, coil placement, "
                            f"B-H bracket; prereg v4): FWHM {env['FWHM_mm']['min']:.4g}-{env['FWHM_mm']['max']:.4g} mm "
                            f"(nominal {env['FWHM_mm']['nominal']:.4g}), z_peak - L {env['z_peak_minus_L_mm']['min']:.3g} to "
                            f"{env['z_peak_minus_L_mm']['max']:.3g} mm, B_anode/B_peak {env['B_anode_over_B_peak']['min']:.2g} "
                            f"to {env['B_anode_over_B_peak']['max']:.2g}; shape bounds = CORNER-A / CORNER-B profiles; not "
                            "covered: shielded pole contour (H1F-MC-05), hot B-H, procured-lot B-H; measured B(z) = EM "
                            "verification item"),
            "status": "FROZEN_ASSUMPTION",
            "rationale": (f"DCR-DBF1-002 approved (coordinator ruling, A9.34): the verified, mesh-converged H-1 FE field replaces "
                          "the P5-shape surrogate (evidence-class upgrade, BD-05); nominal profiles at the DBF1-BZ-03 levels "
                          f"BP-LO ({ex['BP-LO']['NI_A']:.4g} A-turns) and BP-HI ({ex['BP-HI']['NI_A']:.4g} A-turns)"),
            "label": "H1_FE_DERIVED_NOT_MEASURED",
            "registration": ("rigid, no shift: B_profile = {file, align: 'anode', z_ref_in_file_mm: 0.0, scale_to: 'max'}, "
                             "B_ref_T = B_peak_G x 1e-4; the file z is the H-1 z (z = 0 anode face, IP-EXIT at 103.2 mm)"),
            "use_condition": "a Hall run citing this field needs a new NP-HALL-PARAMETRIC-ENVELOPE addendum committed before the run (approval condition)",
            "superseded_value": dict(old, baseline="DBF-1"),
        })
    if n_changed != 1:
        raise SystemExit("REFUSED: DBF1-BZ-04 not found exactly once")
    n_bd = 0
    for d in doc["baseline_deficiencies"]:
        if d["id"] == "DBF1-BD-05":
            n_bd += 1
            d["status"] = "CLOSED_BY_DCR-DBF1-002"
            d["closure"] = {"by": "DCR-DBF1-002 (DBF1-BZ-04 = BZ-H1FE-V1, FE-derived H-1 field)",
                            "evidence": [src("fe_record"), src("dcr_approval")],
                            "residual": "a measured H-1 map remains an engineering-model verification item (H1F-EX-08, H1F-MC-09); the FE field covers the pre-shielding flat-pole circuit only"}
    if n_bd != 1:
        raise SystemExit("REFUSED: DBF1-BD-05 not found exactly once")
    doc["change_control"] = dict(parent["change_control"], register=PINS["dcr_register"][0],
                                 rule=parent["change_control"]["rule"] + "; DBF-1.1 is the successor created by the approved "
                                      "DCR-DBF1-002 and is under the same DCR process")

    cfg = copy.deepcopy(pcfg)
    cfg["id"] = "dbf1_1_config_v1"
    cfg["baseline"] = "DBF-1.1"
    cfg["authoritative_record"] = f"{REL_OUT}/{FILES['json']}"
    cfg["note"] = ("machine-readable subset of dbf1_1_v1.json read by the closure harness (abep_config::baseline::load_dbf1_1); "
                   "identical to dbf1_config_v1.json except h1.bz_shape_id / h1.bz_profiles (DBF1-BZ-04) and the open "
                   "deficiency list (DBF1-BD-05 closed)")
    cfg["h1"]["bz_shape_id"] = "BZ-H1FE-V1"
    cfg["h1"]["bz_profiles"] = {role: {k: {"file": v["file"], "sha256": v["sha256"], "NI_total_A": v["NI_total_A"]}
                                       for k, v in d.items()} for role, d in prof.items()}
    cfg["baseline_deficiencies"] = [x for x in pcfg["baseline_deficiencies"] if x != "DBF1-BD-05"]
    cfg["closed_deficiencies"] = ["DBF1-BD-05"]
    cfg["lineage"] = {"parent": "DBF-1", "parent_lock_sha256": PINS["dbf1_lock"][1], "dcr": "DCR-DBF1-002",
                      "dcr_approval_sha256": PINS["dcr_approval"][1]}
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
         "(read through `abep_config::baseline::load_dbf1_1`). Hash lock: `dbf1_1_lock_v1.json`. Change control: "
         "`docs/baseline/DBF-1/DCR_PROCESS.md`.", "",
         "## Lineage", "",
         f"- parent: DBF-1, lock `{lin['parent_lock']['sha256']}` (immutable; never edited)",
         f"- change: {lin['dcr']}, request `{lin['dcr_request']['path']}` (`{lin['dcr_request']['sha256']}`), approval "
         f"`{lin['dcr_approval']['path']}` (`{lin['dcr_approval']['sha256']}`), register `{lin['dcr_register']['path']}`",
         f"- authority: {lin['approval_authority']}",
         "- only change of value: DBF1-BZ-04 `BZ-P5B16` -> `BZ-H1FE-V1`; DBF1-BD-05 closed; every other item, selection "
         "rule and deficiency equals DBF-1", "",
         "Approval conditions:", ""]
    L += [f"- {c}" for c in lin["approval_conditions"]]
    L += ["", f"Hardware configuration (envelope terms): geometry `{doc['hardware_configuration']['geometry_id']}`, "
              f"B shape `{doc['hardware_configuration']['bz_shape_id']}`.", "", "## DBF1-BZ-04 (changed)", ""]
    bz = next(it for it in doc["items"] if it["id"] == "DBF1-BZ-04")
    L += [f"- value `{bz['value']}` ({bz['label']}); evidence: {bz['evidence_class']}",
          f"- uncertainty: {bz['uncertainty']}", f"- registration: {bz['registration']}", f"- use: {bz['use_condition']}",
          f"- superseded DBF-1 value: `{bz['superseded_value']['value']}` ({bz['superseded_value']['label']})", "",
          "| role | id | file | sha256 | NI total [A-turns] | B_peak [G] |", "|---|---|---|---|---|---|"]
    for role, d in bz["profiles"].items():
        for k, v in d.items():
            L.append(f"| {role} | {k} | `{v['file']}` | `{v['sha256']}` | {v['NI_total_A']:.4g} | {v['B_peak_G']:.4g} |")
    L += ["", "## Frozen items", "", "| id | item | value | units | evidence (class / type / level) | status |",
          "|---|---|---|---|---|---|"]
    for it in doc["items"]:
        L.append(f"| {it['id']} | {fmt(it['name'])} | {fmt(it['value'])} | {fmt(it['units'])} | "
                 f"{fmt(it['evidence_class'])} / {it['quantity_type']} / {it['evidence_level']} | {it['status']} |")
    L += ["", "Sources, uncertainty and rationale of every item are in the JSON.", "", "## Baseline deficiencies", "",
          "| id | items | category | status |", "|---|---|---|---|"]
    for d in doc["baseline_deficiencies"]:
        L.append(f"| {d['id']} | {', '.join(d['items'])} | {d['category']} | {d.get('status', 'OPEN')} |")
    L += ["", "## Not", ""] + [f"- {x}" for x in doc["not"]]
    return ("\n".join(L) + "\n").encode("utf-8")


def outputs() -> dict:
    doc, cfg = build()
    out = {FILES["json"]: dumps(doc), FILES["md"]: render_md(doc), FILES["config"]: dumps(cfg)}
    lock = {"id": "dbf1_1_lock_v1", "baseline": "DBF-1.1", "locked": "2026-10-09",
            "note": "sha256 of the DBF-1.1 files (successor of DBF-1 by the approved DCR-DBF1-002); any change after this "
                    "lock is a DCR with a new baseline version, never an edit",
            "files_relative_to": REL_OUT + "/",
            "files": {k: sha_bytes(v) for k, v in sorted(list(out.items()) + [("build_dbf1_1.py", Path(__file__).read_bytes())])},
            "lineage": {"parent_lock": PINS["dbf1_lock"][0], "parent_lock_sha256": PINS["dbf1_lock"][1],
                        "dcr": "DCR-DBF1-002", "dcr_approval": PINS["dcr_approval"][0],
                        "dcr_approval_sha256": PINS["dcr_approval"][1]},
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
        print(f"OK: {len(out)} DBF-1.1 files current")
        return 0
    for k, v in out.items():
        (OUT / k).write_bytes(v)
    print(f"wrote {len(out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
