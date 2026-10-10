"""Build the DBF-1.2 technical annexure (rev 2) - DRAFT_FOR_OWNER_REVIEW.

The DESIGN SOURCE is one pin: annexure_pin_v1.json (DBF-1.2 freeze commit + lock sha256). Every fact is read AT THAT
COMMIT with `git show` (never from the working tree), the DBF-1.2 lock and every file it lists are hash-verified, and the
closure records the annexure quotes are verified against the lock's `pinned_sources`. Any mismatch refuses the build.
The historical bid package (docs/bid/package/, technical source 5eee4b8, package commit 2de86ab) is read only to show
the previous status of each clause; it is never written.

Generates (this directory):
  compliance_matrix_dbf1_2_v1.json   machine-readable clause-by-clause matrix (37 registered clauses)
  A1_COMPLIANCE_MATRIX.md            the human-readable matrix
  README.md, A2_..A4_*.md            rendered from templates/*.md ({{NAME}} placeholders filled from DBF-1.2)
  docx/*.docx                        Word renderings (when python-docx is importable)

Usage: python docs/proposal/technical_annexure_dbf1_2/build_annexure.py [--check] [--no-docx]
  --check  regenerate in memory and fail if a committed Markdown / JSON file differs (docx not compared: python-docx zip
           timestamps are not deterministic)
Nothing here is submitted anywhere; the repository never submits a bid.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import annexure_data as ad  # noqa: E402

PIN_PATH = os.path.join(HERE, "annexure_pin_v1.json")
DBF_DIR = "docs/baseline/DBF-1.2/"
REG = "docs/requirements/rfp_official/rfp_registration_v1.json"
OLD_MATRIX = "docs/bid/package/compliance_matrix_v1.json"
MD_ORDER = ["README.md", "A1_COMPLIANCE_MATRIX.md", "A2_TECHNICAL_DESCRIPTION.md", "A3_VERIFICATION_PLAN.md",
            "A4_RISK_REGISTER.md"]
TEMPLATED = ["README.md", "A2_TECHNICAL_DESCRIPTION.md", "A3_VERIFICATION_PLAN.md", "A4_RISK_REGISTER.md"]
PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_ /\-.]+)\}\}")
FORBIDDEN = ["fully RFP-qualified", "demonstrated compliant", "flight-qualified", "performance validated",
             "final flight design"]


class BuildError(RuntimeError):
    pass


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(commit: str, path: str) -> bytes:
    try:
        return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError as e:
        raise BuildError(f"{path} not readable at {commit[:7]}: {e.stderr.decode().strip()}") from None


class Source:
    """Read-only, hash-verified view of the DBF-1.2 freeze commit."""

    def __init__(self, pin: dict):
        self.commit = pin["dbf1_2"]["commit"]
        lock_b = git_show(self.commit, pin["dbf1_2"]["lock_path"])
        if sha(lock_b) != pin["dbf1_2"]["lock_sha256"]:
            raise BuildError("DBF-1.2 lock sha256 != annexure pin")
        self.lock = json.loads(lock_b)
        self.pinned = dict(self.lock["pinned_sources"])
        for f, h in self.lock["files"].items():
            self.pinned[DBF_DIR + f] = h
        self._cache: dict[str, bytes] = {}

    def raw(self, path: str) -> bytes:
        if path not in self._cache:
            b = git_show(self.commit, path)
            if path in self.pinned and sha(b) != self.pinned[path]:
                raise BuildError(f"{path} sha256 != DBF-1.2 lock")
            self._cache[path] = b
        return self._cache[path]

    def js(self, path: str):
        return json.loads(self.raw(path))


def resolve(doc, locator: str) -> bool:
    """'#/a/b[k=v]/c' -> True when it resolves; non-pointer locators ('whole file', 'section ...') -> True."""
    if not locator.startswith("#/"):
        return True
    cur = doc
    for part in locator[2:].split("/"):
        m = re.match(r"^([^\[]*)(?:\[(\w+)=([^\]]+)\])?$", part)
        key, sk, sv = m.group(1), m.group(2), m.group(3)
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return False
            cur = cur[key]
        if sk:
            hits = [x for x in cur if isinstance(x, dict) and str(x.get(sk)) == sv] if isinstance(cur, list) else []
            if not hits:
                return False
            cur = hits[0]
    return True


# ------------------------------------------------------------------------------------------------ facts
def n(x: float, nd: int) -> str:
    return f"{x:,.{nd}f}"


def facts(src: Source) -> tuple[dict, dict]:
    d = src.js(DBF_DIR + "dbf1_2_v1.json")
    trace = src.js(DBF_DIR + "dbf1_2_requirement_trace_v1.json")
    items = {i["id"]: i for i in d["items"]}
    icf, air, m, p = d["intake_compressor_feed"], d["air_design_point"], d["mass_rollup"], d["power_rollup"]
    cmp_, feed = icf["DBF12-CMP-01"], icf["DBF12-FEED-01"]
    ar, ac = p["air_12mN"]["reference"], p["air_12mN"]["conservative"]
    x14, x15 = p["xe_25mN"]["1450W_design_ceiling_le"], p["xe_25mN"]["1500W_rfp_supremum_lt"]
    th_c = src.js(ad.THERM)["closure"]
    icp_c = src.js(ad.ICP)["closure"]
    therm, icp = th_c["state"], icp_c["state"]
    mat = src.js(ad.MAT)["closure_state"]["state"]
    bz = src.js(ad.BZ)["closure_state"]
    cons = json.loads(git_show(src.commit, ad.CONS))["constraints"]
    lines = m["lines_mev_kg"]
    reg = src.js("docs/baseline/DBF-1/dcr_register_v5.json")  # the register pinned by the DBF-1.2 lock
    open_dcrs = [o["id"] for o in d["lineage"]["open_dcrs_not_applied"]]
    if open_dcrs != ["DCR-DBF1-003"]:
        raise BuildError(f"open DCRs changed: {open_dcrs} (templates describe DCR-DBF1-003 only)")
    d3 = [x for x in reg["dcrs"] if x["id"] == "DCR-DBF1-003"][0]
    T = {
        "SRC": src.commit[:7], "SRC_FULL": src.commit, "LOCK": pin_lock(), "STATUS": d["status"],
        "DATE": d["date"], "PARENT_LOCK": d["lineage"]["parent_lock"]["sha256"],
        "INTAKE_A": n(icf["DBF12-IN-01"]["aperture_m2"], 2), "INTAKE_D": n(icf["DBF12-IN-01"]["equivalent_diameter_m"], 3),
        "LD": n(icf["DBF12-IN-01"]["collimator_L_over_D"], 0), "SEFF": n(icf["DBF12-IN-01"]["S_eff_inlet_m3_s"], 2),
        "CMP_RPM": n(cmp_["rpm"], 0), "CMP_TIP": n(cmp_["tip_speed_m_s"], 0), "CMP_MEV": n(cmp_["governing_mev_kg"], 3),
        "CMP_P": n(cmp_["power_estimate_W"], 1), "CMP_PA": n(cmp_["power_allowance_W"], 0),
        "PLEN_SET": n(feed["setpoint_Pa"], 2), "PLEN_BAND": f"{feed['band_Pa'][0]:.2f}-{feed['band_Pa'][1]:.2f}",
        "PLEN_V": n(feed["volume_L"], 2), "PLEN_22": n(feed["sensitivity_setpoint_22kms_Pa"], 2),
        "AIR_VEFF": n(air["DBF12-AIR-01"]["v_eff_km_s"], 1), "AIR_MDOT": n(air["DBF12-AIR-01"]["hall_feed_mg_s"], 3),
        "AIR_PD": n(air["DBF12-AIR-01"]["P_d_W"], 0), "AIR22_MDOT": n(air["DBF12-AIR-02"]["hall_feed_mg_s"], 3),
        "AIR_MODEL_T": n(p["air_12mN_model_thrust_at_650W"]["value_mN"], 2),
        "AIR_MODEL_LABEL": p["air_12mN_model_thrust_at_650W"]["label"],
        "AIR_REF": n(ar["P_bus_W"], 1), "AIR_CONS": n(ac["P_bus_W"], 1),
        "AIR_REF_M1500": n(ar["margin_to_1500_W"], 1), "AIR_CONS_M1500": n(ac["margin_to_1500_W"], 1),
        "AIR_REF_M1350": n(ar["margin_to_1350_W"], 1), "AIR_CONS_M1350": n(ac["margin_to_1350_W"], 1),
        "AIR_CORNER": n(p["air_12mN_p6_conservative_corner"]["P_bus_W"], 1),
        "XE1450N": n(x14["nominal_ICP_P_d_max_W"], 1), "XE1450R": n(x14["RF_plus_100W_P_d_max_W"], 1),
        "XE1500N": n(x15["nominal_ICP_P_d_max_W"], 1), "XE1500R": n(x15["RF_plus_100W_P_d_max_W"], 1),
        "XE_STATEMENT": p["xe_25mN_statement"], "XE_PARAM_PD": n(p["xe_25mN_parametric"]["P_d_W"], 0),
        "XE_PARAM_LABEL": p["xe_25mN_parametric"]["label"],
        "ETA": f"{p['basis']['discharge_chain_eta']:.6f}", "PXE_ND": n(p["basis"]["PXE_non_discharge_W"], 1),
        "RF100": n(p["basis"]["rf_plus_100W_bus_W"], 1),
        "NONH": n(m["nonharness_kg"], 3), "HAR": n(m["harness_kg"], 3), "DRY": n(m["nominal_dry_kg"], 3),
        "DRY10": n(m["dry_10pct_kg"], 3), "XE_REF": n(m["xe_reference_kg"], 1), "WET": n(m["wet_kg"], 3),
        "HEADROOM": n(m["numerical_headroom_to_40_kg"], 3), "MASS_WORDING": m["bid_wording"],
        "PPU_MEV": n(m["ppu"]["AL-07_governing_mev_kg"], 2), "PPU_CBE": n(m["ppu"]["cbe_kg"], 2),
        "PPU_STATUS": m["ppu"]["status"], "AL08": n(lines["AL-08 Xe hardware (single branch, 2 kg Xe)"], 3),
        "AL09": n(lines["AL-09 controls / FDIR"], 1), "COMPRESSOR_NOTE": m["compressor_booking"]["note"],
        "ICP_MOUNT": m["icp_mount_correction"],
        "H1_D": n(items["DBF1-H1-01"]["value"], 0), "H1_H": n(items["DBF1-H1-02"]["value"], 0),
        "H1_L": n(items["DBF1-H1-03"]["value"], 1),
        "CDA": n(items["DBF12-HOST-01"]["value"]["reference_proposal_sizing_CdA_m2"], 2),
        "DCR3_STATUS": d3["status"], "DCR3_ITEMS": "; ".join(d3["items"]), "DCR3_REASON": d3["physical_or_evidence_reason"],
        "DCR3_ROUTES": "; ".join(d3["routes"]),
        "THERM_STATE": therm, "ICP_STATE": icp, "TH_DCR_NODES": ", ".join(th_c["dcr_nodes"]) or "none",
        "TH_REQ_NODES": ", ".join(th_c["requirement_nodes"]) or "none", "TH_RULE": th_c["rule"],
        "ICP_GNG": icp_c["GNG-ICP-01"], "ICP_IECAP": icp_c["I_e_cap_status"],
        "ICP_CONS": "feasible" if icp_c["conservation_feasible_in_frozen_envelope"] else "NOT feasible", "MAT_STATE": mat, "BZ_STATE": bz,
        "LIFE_H": f"{cons['mission_life_h']['value']:,}", "FIRING_H": f"{cons['firing_life_h']['value']:,}",
    }
    for r in trace["trace"]:
        T["T_" + r["rvm"]] = r["state"]
    return T, {"dbf": d, "trace": trace, "items": items, "risks": src.js(DBF_DIR + "dbf1_2_risk_register_v1.json"),
               "therm": src.js(ad.THERM), "icp": src.js(ad.ICP)}


def pin_lock() -> str:
    return json.load(open(PIN_PATH, encoding="utf-8"))["dbf1_2"]["lock_sha256"]


def render(text: str, T: dict) -> str:
    missing = sorted({k for k in PLACEHOLDER.findall(text) if k not in T})
    if missing:
        raise BuildError(f"unfilled placeholders: {missing}")
    out = PLACEHOLDER.sub(lambda mm: str(T[mm.group(1)]), text)
    if "{{" in out or "}}" in out:
        raise BuildError("placeholder syntax left after rendering")
    return out


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def table(head: list, rows: list) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def fmt_val(v, units="") -> str:
    """Numbers / numeric lists get their units appended; dicts carry the record's units string in brackets."""
    if isinstance(v, float):
        s = f"{v:g}"
    elif isinstance(v, list):
        s = " - ".join(f"{x:g}" for x in v) if all(isinstance(x, (int, float)) for x in v) else ", ".join(map(str, v))
    elif isinstance(v, dict):
        s = "; ".join(f"{k} {fmt_val(x)}" for k, x in v.items())
        return f"{s} [{units}]" if units and units != "-" else s
    else:
        s = str(v)
    numeric = isinstance(v, (int, float)) or (isinstance(v, list) and all(isinstance(x, (int, float)) for x in v))
    return f"{s} {units}" if numeric and units and units != "-" else s


# ------------------------------------------------------------------------------------------------ blocks
def blocks(T: dict, X: dict) -> dict:
    d, items = X["dbf"], X["items"]
    icf, m, p = d["intake_compressor_feed"], d["mass_rollup"], d["power_rollup"]
    B = {}
    rows = []
    for r in icf["DBF12-CMP-02"]["rows"]:
        rows.append([r["row"], r["shaft"], f"{r['r_tip_m']:.3f} / {r['r_hub_m']:.3f}", f"{r['blade_height_mm']:.1f}",
                     f"{r['u_rel_m_s']:.0f}", f"{r['p_in_Pa']:.4f} -> {r['p_out_Pa']:.4f}", f"{r['K']:.2f}",
                     f"{r['Kn_out']:.1f}", r["classification"]])
    h = icf["DBF12-CMP-02"]["holweck"]
    rows.append(["H (Holweck)", "A (drum skin)", "-", f"groove {h.get('groove_depth_mm', '-')}", "-",
                 f"{h['p_in_Pa']:.3f} -> {h['p_out_Pa']:.3f}", "-", f"{h['Kn_out']:.2f}", h["classification"]])
    B["COMPRESSOR_TABLE"] = table(["row", "shaft", "r_tip / r_hub (m)", "blade (mm)", "u_rel (m/s)",
                                   "p_in -> p_out (Pa)", "K", "Kn out", "classification"], rows)
    mrows = [[k, f"{v:.4f}"] for k, v in m["lines_mev_kg"].items()]
    mrows += [["non-harness", T["NONH"]], ["harness (5/95 rule)", T["HAR"]], ["**nominal dry**", f"**{T['DRY']}**"],
              ["+ 10 % system margin", T["DRY10"]], ["+ Xe reference load", T["XE_REF"]],
              ["**preliminary wet (< 40 kg)**", f"**{T['WET']}**"]]
    B["MASS_TABLE"] = table(["line (A9.41 approved v6 roll-up)", "MEV (kg)"], mrows)
    ar, ac = p["air_12mN"]["reference"], p["air_12mN"]["conservative"]
    B["AIR_POWER_TABLE"] = table(
        ["AIR 12 mN case", "P_d (W)", "compressor load (W)", "P_bus discharge (W)", "P_bus other (W)",
         "P_bus compressor (W)", "P_bus total (W)", "margin to 1,350 W", "margin to 1,500 W"],
        [[nm, f"{c['P_d_W']:.0f}", f"{c['compressor_load_W']:.1f}", f"{c['P_bus_discharge_W']:.1f}",
          f"{c['P_bus_non_discharge_excl_compressor_W']:.1f}", f"{c['P_bus_compressor_W']:.1f}", f"{c['P_bus_W']:.1f}",
          f"{c['margin_to_1350_W']:.1f}", f"{c['margin_to_1500_W']:.1f}"]
         for nm, c in (("reference", ar), ("conservative", ac))])
    B["XE_POWER_TABLE"] = table(["Xe 25 mN Hall discharge allocation", "nominal ICP (W)", "+100 W RF (W)"],
                                [["<= 1,450 W design ceiling", f"<= {T['XE1450N']}", f"<= {T['XE1450R']}"],
                                 ["< 1,500 W RFP limit", f"< {T['XE1500N']}", f"< {T['XE1500R']}"]])

    def item_rows(prefixes):
        out = []
        for i in d["items"]:
            s12 = i.get("status_dbf1_2", i["status"])
            if any(i["id"].startswith(px) for px in prefixes) and not s12.startswith("SUPERSEDED"):
                v = fmt_val(i["value"], i.get("units", ""))
                if len(v) > 240:
                    v = v[:200].rsplit(" ", 1)[0] + f" ... (full value: `{DBF_DIR}dbf1_2_v1.json` `#/items[id={i['id']}]`)"
                out.append([i["id"], i["name"], v, i["status"], s12])
        return table(["id", "item", "frozen value", "freeze class", "DBF-1.2 status"], out)

    B["H1_TABLE"] = item_rows(["DBF1-H1-", "DBF1-BZ-"])
    B["ICP_TABLE"] = item_rows(["DBF1-ICP-", "DBF1-RF-"])
    B["MAT_TH_TABLE"] = item_rows(["DBF1-MAT-", "DBF1-TH-"])
    B["PWR_ITEMS_TABLE"] = item_rows(["DBF1-PWR-", "DBF1-MASS-"])
    B["TRACE_TABLE"] = table(["requirement", "RVM", "RFP clauses", "DBF-1.2 items", "DBF-1.2 state", "note"],
                             [[r["requirement"], r["rvm"], ", ".join(r["rfp_clauses"]) or "-",
                               ", ".join(r["dbf1_2_items"]) or "-", r["state"], r["note"]] for r in X["trace"]["trace"]])
    B["RISK_TABLE"] = table(["id", "item", "basis", "verification", "status"],
                            [[r["id"], r["title"], r["basis"], r["verification"], r["status"]]
                             for r in X["risks"]["risks"]])
    mr = [r for r in X["risks"]["risks"] if r["id"] == "MR-DCR001-01"][0]
    B["MR_DRIVERS"] = "\n".join(f"- {x}" for x in mr.get("drivers", []))
    B["MR_MITIGATION"] = "\n".join(f"- {x}" for x in (mr.get("mitigation") if isinstance(mr.get("mitigation"), list)
                                                        else [mr.get("mitigation", "-")]))
    B["VR_PLAN_TABLE"] = table(["DBF-1.2 item", "what is verified", "method (DBF-1.2)", "first closure point (PROPOSED)"],
                               [[r["id"], r["title"], r["verification"], VR_MILESTONE.get(r["id"], "-")]
                                for r in X["risks"]["risks"]])
    missing = sorted(set(r["id"] for r in X["risks"]["risks"]) - set(VR_MILESTONE))
    if missing:
        raise BuildError(f"risk ids without a proposed milestone: {missing}")
    B["DEFICIENCY_TABLE"] = table(["id", "category", "DBF-1.2 status"],
                                  [[b["id"], b["category"], b.get("status", "OPEN")] for b in d["baseline_deficiencies"]])
    return B


VR_MILESTONE = {
    "MR-DCR001-01": "M1 (CBE / quotations) -> M3 / M4 (EM mass measurement)",
    "VR-PPU-01": "M1 (early PPU design / quotation)",
    "VR-XE-01": "M1 (tank quotation, MEOP at 323 K)",
    "VR-CMP-01": "M4 (EM compressor mass)",
    "VR-CMP-02": "M4 (EM compressor characterisation)",
    "VR-CMP-03": "M4 (EM compressor test)",
    "VR-CMP-04": "M4 (EM spin test; clearance design at M1)",
    "VR-FEED-01": "M3 (EM thruster flow-uniformity test)",
    "VR-HALL-01": "M3 (EM thrust on N2 / air, storage input)",
    "VR-HALL-02": "M3 (EM thrust map)",
    "VR-XE-02": "M3 (EM / QM Xe thrust and bus power)",
    "VR-PWR-01": "M3 (measured non-discharge loads on EM)",
    "VR-HAR-01": "M1 (routed harness design)",
    "VR-AL09-01": "M1 / M2 (controller design CBE)",
    "VR-AL10-01": "M1 (structural / thermal CBE)",
    "VR-HOST-01": "M1 (host ICD at PDR)",
    "VR-EMQM-01": "M4 -> M5 (QM ENTEST)",
}


# ------------------------------------------------------------------------------------------------ matrix
def build_matrix(src: Source, T: dict, pin: dict) -> dict:
    reg = {c["id"]: c for c in src.js(REG)["clauses"]}
    hist = pin["historical_bid_package"]
    old = {c["id"]: c["status"] for c in json.loads(git_show(hist["package_commit"], OLD_MATRIX))["clauses"]}
    ids = [c["id"] for c in ad.CLAUSES]
    if ids != list(reg):
        raise BuildError("annexure clauses != registered RFP clauses (order and set)")
    trace_rvms = {r["rvm"] for r in json.loads(src.raw(DBF_DIR + "dbf1_2_requirement_trace_v1.json"))["trace"]}
    clauses, changes = [], []
    for c in ad.CLAUSES:
        if c["status"] not in ad.STATUSES:
            raise BuildError(f"{c['id']}: unknown status {c['status']}")
        for r in c["dbf_trace"]:
            if r not in trace_rvms:
                raise BuildError(f"{c['id']}: {r} not in the DBF-1.2 trace")
        for e in c["evidence"]:
            b = git_show(src.commit, e["path"])
            if e["path"].endswith(".json") and not resolve(json.loads(b), e["locator"]):
                raise BuildError(f"{c['id']}: {e['path']} {e['locator']} does not resolve at {src.commit[:7]}")
        if old[c["id"]] == "COMPLY_PLANNED_WITH_EVIDENCE_PATH" and c["status"] == "COMPLY" or \
                (c["status"] == "COMPLY" and old[c["id"]] != "COMPLY"):
            raise BuildError(f"{c['id']}: raised to COMPLY by regeneration (forbidden by STATUS_RULE)")
        resp = render(c["response"], T)
        clauses.append({"id": c["id"], "page": reg[c["id"]]["page"], "section": reg[c["id"]]["section"],
                        "rfp_text_verbatim": reg[c["id"]]["text"], "status": c["status"],
                        "previous_status_bid_package_2de86ab": old[c["id"]], "dbf1_2_trace": c["dbf_trace"],
                        "response": resp, "evidence_at_dbf1_2": c["evidence"], "owner_input": c["owner_input"]})
        if old[c["id"]] != c["status"]:
            changes.append({"id": c["id"], "from": old[c["id"]], "to": c["status"]})
    counts = {s: sum(1 for c in clauses if c["status"] == s) for s in ad.STATUSES}
    return {"schema": "abep_bid_annexure_compliance_matrix_v2", "id": "compliance_matrix_dbf1_2_v1",
            "status": "DRAFT_FOR_OWNER_REVIEW", "design_source": {"baseline": "DBF-1.2", "commit": src.commit,
                                                                   "lock_sha256": pin["dbf1_2"]["lock_sha256"]},
            "dbf1_2_status": T["STATUS"], "historical_bid_package": hist,
            "generated_by": "docs/proposal/technical_annexure_dbf1_2/build_annexure.py", "status_vocabulary": ad.STATUS_DEFINITIONS,
            "status_rule": ad.STATUS_RULE, "status_counts": counts, "status_changes_vs_bid_package": changes,
            "never_label_as": FORBIDDEN, "clauses": clauses}


def matrix_md(j: dict, T: dict) -> str:
    L = ["# A1 - Compliance matrix (DBF-1.2)", "",
         f"**Status: DRAFT_FOR_OWNER_REVIEW.** Design source: DBF-1.2, freeze commit `{T['SRC']}` (`{T['SRC_FULL']}`), "
         f"lock sha256 `{j['design_source']['lock_sha256']}`. Baseline status: **{T['STATUS']}**. Every evidence path "
         f"is a file at that commit (`git show {T['SRC']}:<path>`).", "",
         "## Status vocabulary", ""]
    L += [f"- **{k}**: {v}" for k, v in j["status_vocabulary"].items()]
    L += ["", f"Status rule: {j['status_rule']}", "", "## Status counts (37 registered clauses)", ""]
    L += [f"- {k}: {v}" for k, v in j["status_counts"].items()]
    L += ["", "## Changes against the 2026-10-05 bid package (`docs/bid/package/`, commit "
              f"`{j['historical_bid_package']['package_commit'][:7]}`)", ""]
    L += [table(["clause", "bid package status", "DBF-1.2 annexure status"],
                [[c["id"], c["from"], c["to"]] for c in j["status_changes_vs_bid_package"]])]
    L += ["", "## Clause-by-clause", ""]
    for c in j["clauses"]:
        L += [f"### {c['id']} - {c['section']} (p. {c['page']})", "", f"> {c['rfp_text_verbatim']}", "",
              f"**Status: {c['status']}** (bid package: {c['previous_status_bid_package_2de86ab']}). "
              f"DBF-1.2 trace: {', '.join(c['dbf1_2_trace']) or 'none'}.", "", c["response"], ""]
        if c["evidence_at_dbf1_2"]:
            L += ["Evidence at " + T["SRC"] + ": " + "; ".join(f"`{e['path']}` `{e['locator']}`"
                                                              for e in c["evidence_at_dbf1_2"]), ""]
        if c["owner_input"]:
            L += ["Owner input: " + ", ".join(c["owner_input"]), ""]
    return "\n".join(L).rstrip() + "\n"


# ------------------------------------------------------------------------------------------------ docx
_INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def _add_inline(par, text):
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            par.add_run(part[1:-1]).font.name = "Consolas"
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
            _add_inline(doc.add_paragraph(style="Intense Quote"), ln[2:])
        elif ln.strip():
            _add_inline(doc.add_paragraph(), ln)
        i += 1
    doc.save(out_path)


# ------------------------------------------------------------------------------------------------ main
def build_all() -> dict:
    pin = json.load(open(PIN_PATH, encoding="utf-8"))
    src = Source(pin)
    T, X = facts(src)
    j = build_matrix(src, T, pin)
    T.update(blocks(T, X))
    T["COUNTS"] = "\n".join(f"- {k}: {v}" for k, v in j["status_counts"].items())
    T["CHANGES"] = "\n".join(f"- {c['id']}: {c['from']} -> {c['to']}" for c in j["status_changes_vs_bid_package"])
    T["STATUS_RULE_TEXT"] = ad.STATUS_RULE
    T["HIST_SRC"] = pin["historical_bid_package"]["technical_source"][:7]
    T["HIST_PKG"] = pin["historical_bid_package"]["package_commit"][:7]
    out = {"compliance_matrix_dbf1_2_v1.json": json.dumps(j, indent=1, ensure_ascii=False) + "\n",
           "A1_COMPLIANCE_MATRIX.md": matrix_md(j, T)}
    for name in TEMPLATED:
        out[name] = render(open(os.path.join(HERE, "templates", name), encoding="utf-8").read(), T)
    for name, text in out.items():
        if not name.endswith(".md"):
            continue  # the JSON carries the never_label_as list itself; its responses are rendered in A1
        for w in FORBIDDEN:
            for mm in re.finditer(re.escape(w), text):
                ctx = re.split(r"[.:]|\n\n", text[max(0, mm.start() - 200):mm.start()])[-1]  # same sentence
                if not re.search(r"(never|not|no|never labelled|neither)[^.]*$", ctx, re.I):
                    raise BuildError(f"{name}: forbidden label '{w}' used affirmatively")
    return out


def main(argv):
    out = build_all()
    if "--check" in argv:
        bad = [k for k, v in out.items()
               if not os.path.exists(os.path.join(HERE, k)) or open(os.path.join(HERE, k), encoding="utf-8").read() != v]
        if bad:
            print("STALE:", bad)
            return 1
        print(f"OK: {len(out)} annexure files current")
        return 0
    for k, v in out.items():
        with open(os.path.join(HERE, k), "w", encoding="utf-8") as f:
            f.write(v)
    print(f"wrote {len(out)} files")
    if "--no-docx" not in argv:
        try:
            import docx  # noqa: F401
        except ImportError:
            print("python-docx not available: docx not generated")
            return 0
        os.makedirs(os.path.join(HERE, "docx"), exist_ok=True)
        for name in MD_ORDER:
            md_to_docx(out[name], os.path.join(HERE, "docx", name[:-3] + ".docx"))
        print("docx generated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
