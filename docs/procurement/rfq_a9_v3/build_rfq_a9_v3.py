#!/usr/bin/env python3
"""Deterministic builder of the A9 RFQ packages v3 (A9.16 owner-decision application, RFQ lane).

A REVISION of the immutable v2 packages docs/procurement/rfq_a9_v2/ (which itself revises the immutable v1 packages).
v2 is never edited: every v2 file is pinned by sha256 below and the v2 JSON is read as data. v3 = v2 + the recorded owner
decisions A9.8 / A9.10 / A9.11 / A9.14 / A9.15 (2026-10-01) applied line by line, each change carrying a per-requirement /
per-line change record (change_v3) that names the decision file, its json sha256 and the question id.

Writes
  docs/procurement/rfq_a9_v3/rfq_a9_v3.json                          machine-readable packages, change log, traceability
  docs/procurement/rfq_a9_v3/RFQ_A9_V3.md                            companion document (rendered from the JSON data)
  docs/procurement/rfq_a9_v3/packages/RFQ3-00_common_interface.md    common top-level interface document
  docs/procurement/rfq_a9_v3/packages/RFQ3-0N_<slug>.md              one sendable package per supplier speciality

What v3 changes (owner decisions; the verbatim .md of each decision governs, quotes are checked verbatim at build time)
  * A9.8 P2Q-02      new separate RF-metrology package RFQ3-RFMET under the common interface specification;
  * A9.10 OQ-RFQV2-10 new separate H-1 build-to-print fabrication package RFQ3-H1FAB (design authority in-house);
  * A9.8 OQ-RFQV2-01..06, 08; A9.10 OQ-RFQV2-09; A9.11 P2Q-07; A9.14 OQ-RFQ-01/03/04/08/09, XA9Q-06, OQ-A907-04;
    A9.14 XA9Q-07 / XA9Q-05 as amended by A9.15 (RFP-compliant propellant policy: Xe is an RFP-required system
    capability, never a C1 contingency; C1 Xe only if a selected C1 requires it, booked inside the system Xe architecture);
  * decisions that change RFQ lines directly although not named in the lane list: A9.8 P1Q-09 (dedicated isolated
    electron-collecting target becomes a required line), A9.8 P3Q-01 (Langmuir-probe cross-check line), A9.8 P1-IT-55
    (per-path DWV leakage limit), A9.14 P1Q-17 (700 V DC / 60 s triggered reverification), A9.14 F5-OQ-04 (released
    H-1 drawing basis of the FLIGHT H-1 at LOCK-1; the P1 engineering article is quoted against a P9e-controlled
    drawing set, A9.10 OQ-RFQV2-10 - A9.16 repair F4). A9.1 ICP gas-mode baseline (G-REUSE primary; G-XE a declared ICP-feed variant) is unchanged.
  * A9.19 / A9.20 (in place): single flight architecture; C1 lines GROUND_ONLY_LAB_EQUIPMENT.
  * A9.21 (in place; v3 is not declared immutable): item 2 AL08 - Xe storage / flow quotation split RFQ3-GAS-N05 (tank,
    regulator, valves, plumbing, mounting/thermal, the C1-specific branch separate and ground-only, never in the flight
    AL-08), quote-request lines GAS-L18 / GAS-L19 with supplier-proposed quantities, AL-08 mass context = provisional
    planning floor (older allocation kept as labelled history); item 15 RFQ_DISPATCH - per-package dispatch-readiness
    record and checklist (READY_FOR_OWNER_DISPATCH / NOT_READY_* / LATER_NOT_IN_CURRENT_DISPATCH); the repository never
    dispatches and no purchase is ever authorized here.

Rules implemented here
  * requirement and line ids are stable across revisions (v2 ids kept); new v3 ids carry the RFQ3- prefix; package ids
    are renamed RFQ2-* -> RFQ3-* outside historical records (a rename is not counted as a content change);
  * numbers deferred by the owner to a later registration stay TBD with their freeze gate; fail-closed rule functions
    (external pumping acceptance, combined load, magnet-supply substitution, DWV evidence, V/I calibration route,
    Xe-MFC range, MEOP basis, Option-B path, coil-wire variant, Xe capability scope, ICP Xe getter, H-1 drawing send
    state) return NOT_* / G0_NOT_EVALUATED_TBD / REFUSED_* states and never invent a number;
  * no price, supplier name, ranking, supplier contact, purchase order or PASS (RF ratings TBD_AFTER_IMPEDANCE_MAP;
    ICP_COUPLED_THERMAL UNRESOLVED; anode OPEN; ICP capacity PENDING_ICP45);
  * missing inputs raise (CLAUDE.md rule 3).

Usage
  python docs/procurement/rfq_a9_v3/build_rfq_a9_v3.py          # write all outputs
  python docs/procurement/rfq_a9_v3/build_rfq_a9_v3.py --check  # exit 1 if any output differs from a fresh build

Standard library only. Pure (reads repository files, writes only its own outputs); not wired into archengine.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LANE_DIR = "docs/procurement/rfq_a9_v3"
OUT_JSON = LANE_DIR + "/rfq_a9_v3.json"
OUT_MD = LANE_DIR + "/RFQ_A9_V3.md"
PKG_DIR = LANE_DIR + "/packages"
THIS_SCRIPT = LANE_DIR + "/build_rfq_a9_v3.py"
TEST = "tests/test_rfq_a9_v3.py"
BASE_COMMIT = "673c058c4dd0a52633470e1c4593ab41f99f7665"

# ----------------------------------------------------------------------------------------------- immutable v2 inputs
V2 = {
    "V2_JSON": ("docs/procurement/rfq_a9_v2/rfq_a9_v2.json",
                "6960f2927ece5a171d851bc10bc2314e99ef448b1e6f7d5ba84b93d2226795cb"),
    "V2_MD": ("docs/procurement/rfq_a9_v2/RFQ_A9_V2.md",
              "80b9cbd08d0366336950f3496b92a28b9c8c40d7ab17af3c3cc2d9e7452ac01c"),
    "V2_BUILDER": ("docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py",
                   "4aa6ce0dfbc1698e27c2b737fb2f1c7f3efb55efc08969a4de22484acedb8964"),
    "V2_CIF": ("docs/procurement/rfq_a9_v2/packages/RFQ2-00_common_interface.md",
               "215dd3877630967cefd1ce0c66b9c34210add073a5f2aeed4a777b7e13852b3e"),
    "V2_RF": ("docs/procurement/rfq_a9_v2/packages/RFQ2-01_rf.md",
              "c58def9f12aded97ac7cacb641515f057a4a25647ef236cf2df3a386c5952078"),
    "V2_GAS": ("docs/procurement/rfq_a9_v2/packages/RFQ2-02_gas_metrology.md",
               "8894054fc44a9ec17c2fafe545ead59a00251ce255ad43b256b5502f756f55df"),
    "V2_VAC": ("docs/procurement/rfq_a9_v2/packages/RFQ2-03_vacuum_facility.md",
               "03ba2ace53cdfcd5ed188e04976d684469c42fafb26d0f5387e7b7ecd80acdd9"),
    "V2_HALLEL": ("docs/procurement/rfq_a9_v2/packages/RFQ2-04_hall_electrical.md",
                  "a2fe92052d5d1e038f05d23d743f3f20c386963ba0ddbe936d10f442093c668b"),
    "V2_MECH": ("docs/procurement/rfq_a9_v2/packages/RFQ2-05_mechanical_icp_fabrication.md",
                "f1a5ca5b18cd507fc263508f6fda1b2b7560cf0f4e6f35b14ee8b80a9dc51a5c"),
    "V2_THRUST": ("docs/procurement/rfq_a9_v2/packages/RFQ2-06_thrust_metrology.md",
                  "3195c493f9819750068a8cc76792746f009adb2e30978ed957671c9332c41099"),
}

# ------------------------------------------------------------------------------------- owner decisions (immutable)
DECISIONS = {
    "A9.8": {"json": "docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json",
             "json_sha256": "e96b8bc0a27f5fbc03d48d36db6e470dfc60c4960d6ba02cdaac8871752b537f",
             "md": "docs/decisions/OD_2026_10_01_A9_8_S1_P1_START_OWNER_DECISIONS.md",
             "md_sha256": "8e770d0edf056a0402f6ec8c86a2a2feec169ab971fae788c7a9a620211e1aa0"},
    "A9.10": {"json": "docs/decisions/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json",
              "json_sha256": "3a99f16dd957f533b6b7afb7539d27be132fae386148e1683e417db0ede26544",
              "md": "docs/decisions/OD_2026_10_01_A9_10_S3_P1_LATER_STAGE_OWNER_DECISIONS.md",
              "md_sha256": "6845f54a97192eaa934cc67d5f415c94e317707c97411353aa2325bf5f9b0491"},
    "A9.11": {"json": "docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json",
              "json_sha256": "d8baf59a5b92739698e29d893e89a30995559ee7167814c096dc24599679156c",
              "md": "docs/decisions/OD_2026_10_01_A9_11_S4_P2_OWNER_DECISIONS.md",
              "md_sha256": "4a9fd171abc6a63266a34e6a7c4cb25c4d67ed16615715e158902a57f7071a41"},
    "A9.14": {"json": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
              "json_sha256": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
              "md": "docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md",
              "md_sha256": "2a61c761120863c4b5821043ab78b6f9b28227584f7d83cb48ecd6598ed0af07"},
    "A9.15": {"json": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "md": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "md_sha256": "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903"},
    # A9.19 (flight architecture: one Hall + one RF/ICP neutralizer, no conventional hollow cathode, Xe = contingency /
    # emergency supply mode; amends A9.15 on the ROLE of Xe) and A9.20 (C1 = ground-only laboratory reference)
    "A9.19": {"json": "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "json_sha256": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              "md": "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "md_sha256": "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749"},
    "A9.20": {"json": "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "json_sha256": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              "md": "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "md_sha256": "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c"},
    # A9.21 (2026-10-02): item 2 AL08 (6.05 kg provisional; quotations split tank / regulator / valves / plumbing /
    # mounting-thermal / any C1-specific branch before the re-base) and item 15 RFQ_DISPATCH (packages finalized here;
    # owner / procurement sends them)
    "A9.21": {"json": "docs/decisions/OD_2026_10_02_A9_21_open_items_and_hardware_programme_owner_decisions.json",
              "json_sha256": "78766d3adaaa6d38730ce82607a1cd0a03ae34186c911d4189e2fd9251db6549",
              "md": "docs/decisions/OD_2026_10_02_A9_21_OPEN_ITEMS_AND_HARDWARE_PROGRAMME_OWNER_DECISIONS.md",
              "md_sha256": "01f7796aa2ae03d7bc0319b191f004e0a1ba0214c2c982f34554ca52cf531440"},
}
# owner decisions whose json 'decisions' table maps a key to a plain answer string (no per-question record)
STRING_DECISION_KEYS = ("A9.21",)
# single-record owner decisions (no per-question 'decisions' table in their json): the allowed record keys
SINGLE_RECORD_KEYS = {"A9.19": ("architecture", "xenon_role", "amends"), "A9.20": ("answer",)}
STATE_V4 = "docs/budgets/owner_decisions/owner_questions_state_v4.json"   # read for ids only; never pinned (mutable)
NEVER_PINNED_V3 = [STATE_V4 + " (owner-question state; refreshed by the integration lane)",
                   "docs/orchestration/* (mutable governance)"]

# ---------------------------------------------------------------------------------------------------- vocabulary
CONFIGS = ["hall_c1_reference", "hall_icp_neutralizer"]
FREEZE_POINTS = ["NOW", "P1-G0", "LOCK-1", "LOCK-2", "after-evidence"]
STATUSES = ["OWNER_GIVEN", "COPIED_VERIFIED", "DERIVED", "PROPOSED", "TBD", "PENDING", "REFERENCE_ONLY",
            "SUPERSEDED_NOT_QUOTED"]
DISPATCH = ["P1_NEEDED", "LATER"]
CHANGE_TYPES_V3 = ["CARRIED_UNCHANGED", "CARRIED_MODIFIED", "MOVED_PACKAGE", "MOVED_PACKAGE_MODIFIED",
                   "SUPERSEDED_NOT_QUOTED", "NEW"]
EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "owner-stated"]
NEVER_PASS = ("RF component ratings TBD_AFTER_IMPEDANCE_MAP; ICP_COUPLED_THERMAL UNRESOLVED; anode material OPEN; "
              "ICP electron-current capacity PENDING_ICP45 (ICP45 NOT_EVALUATED until I_d,max,H1 is registered)")
SEND_P1 = "READY_TO_SEND_FOR_QUOTATION (owner / procurement; A9.4); purchase order NOT authorized"
SEND_LATER = "LATER (sent with the later campaign set); purchase order NOT authorized"
SEND_XE_INDICATIVE = ("INDICATIVE_QUOTATION_NOW (A9.14 OQ-RFQ-03; range options, range NOT frozen); purchase order NOT "
                      "authorized")
SEND_H1FAB = ("SEND_ONLY_WITH_CONTROLLED_H1_DRAWINGS (P1 engineering article: drawing ID, revision, content hash under "
              "P9e / Vyovrinda configuration control, A9.10 OQ-RFQV2-10; the LOCK-1 release of A9.14 F5-OQ-04 is the "
              "basis of the FLIGHT H-1, not a precondition for quoting P1 hardware); quotation / specification only "
              "(A9.10 OQ-RFQV2-10); purchase order NOT authorized")
H1_ARTICLES = ("P1_ENGINEERING", "FLIGHT")
H1_CONFIGURATION_CONTROL = "P9E_CONFIGURATION_CONTROLLED"

PKG_RENAME = {"RFQ2-RF": "RFQ3-RF", "RFQ2-GAS": "RFQ3-GAS", "RFQ2-VAC": "RFQ3-VAC", "RFQ2-HALLEL": "RFQ3-HALLEL",
              "RFQ2-MECH": "RFQ3-MECH", "RFQ2-THRUST": "RFQ3-THRUST", "RFQ2-CIF": "RFQ3-CIF"}
_PKG_RE = re.compile(r"RFQ2-(RF|GAS|VAC|HALLEL|MECH|THRUST|CIF)(?![-\w])")
NEW_PACKAGES = {
    "RFQ3-RFMET": {"number": "07", "slug": "rf_metrology", "owner_family": "RF-metrology package"},
    "RFQ3-H1FAB": {"number": "08", "slug": "h1_fabrication",
                   "owner_family": "H-1 fabrication (build-to-print) package"},
}
PKG_ORDER = ["RFQ3-RF", "RFQ3-GAS", "RFQ3-VAC", "RFQ3-HALLEL", "RFQ3-MECH", "RFQ3-THRUST", "RFQ3-RFMET", "RFQ3-H1FAB"]
# P2Q-02: the owner's listed RF measurement equipment moves to RFQ3-RFMET (RF-O01 is measurement equipment that only
# stands in for RF-L13's spectrum mode, so it follows RF-L13); RF-L19 (match-element encoders) is part of the local
# matching hardware and RF-L11 (power analyser) stays under RF per OQ-RFQV2-04 - recorder reconciliation, flagged.
RFMET_LINES = ["RF-L12", "RF-L13", "RF-L14", "RF-L15", "RF-L16", "RF-L17", "RF-L18", "RF-O01"]
RFMET_REQS = ["RFQ2-RF-N07", "RFQ2-RF-N10", "RFQ2-RF-N11", "RFQ2-RF-N12", "RFQ2-RF-N14", "RFQ2-RF-N15",
              "RFQ2-RF-N17"]
SKIP_RENAME_KEYS = {"sources", "source", "source_quote", "change", "v1_snapshot", "p2_required_specs_copied",
                    "reference_data", "xref", "requirement_before_a9_2", "value_before_a9_2", "before_v3"}


# -------------------------------------------------------------------------------------------------------- helpers
def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel)


def _sha_file(rel: str) -> str:
    with open(_abs(rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify_pins() -> None:
    bad = [f"{p} (expected {s[:12]}, got {_sha_file(p)[:12]})" for p, s in V2.values() if _sha_file(p) != s]
    for k, d in DECISIONS.items():
        for f in ("json", "md"):
            if _sha_file(d[f]) != d[f + "_sha256"]:
                bad.append(f"{k} {d[f]}")
    if bad:
        raise RuntimeError("pinned inputs changed (immutable history): " + "; ".join(bad))


def _load(rel: str):
    with open(_abs(rel), encoding="utf-8") as fh:
        return json.load(fh)


def _norm(s: str) -> str:
    return " ".join(s.split())


_DEC_CACHE: dict = {}


def _decision(key: str):
    if key not in _DEC_CACHE:
        d = DECISIONS[key]
        with open(_abs(d["md"]), encoding="utf-8") as fh:
            _DEC_CACHE[key] = (_load(d["json"]), _norm(fh.read()))
    return _DEC_CACHE[key]


def OD(key: str, qid: str, quote: str) -> dict:
    """Source record of one owner decision: the quote must occur verbatim in the decision's .md (whitespace-normalized)
    and the question id must be recorded OWNER_DECIDED in its json (A9.15: an amendment key or the governing rule)."""
    js, md = _decision(key)
    if _norm(quote) not in md:
        raise ValueError(f"{key} {qid}: quote not found verbatim in {DECISIONS[key]['md']}: {quote[:80]!r}")
    if key == "A9.15":
        if qid != "governing_rule" and qid not in js["amendments"]:
            raise KeyError(f"A9.15 has no amendment {qid}")
        seq, ans = None, ("RFP_COMPLIANT_PROPELLANT_POLICY" if qid == "governing_rule" else js["amendments"][qid])
    elif key in STRING_DECISION_KEYS:
        ans = js.get("decisions", {}).get(qid)
        if not isinstance(ans, str) or js.get("decided_by") != "owner":
            raise KeyError(f"{key} has no owner decision {qid}")
        seq = None
    elif key in SINGLE_RECORD_KEYS:
        if qid not in SINGLE_RECORD_KEYS[key] or qid not in js:
            raise KeyError(f"{key} has no record {qid}")
        if js.get("decided_by") != "owner":
            raise KeyError(f"{key} is not an owner decision")
        seq, ans = None, js["decision"]
    else:
        rec = js["decisions"].get(qid)
        if rec is None or rec.get("status") != "OWNER_DECIDED":
            raise KeyError(f"{key} {qid} is not an OWNER_DECIDED entry of {DECISIONS[key]['json']}")
        seq, ans = rec.get("sequenced_no"), rec.get("answer")
    return {"type": "owner_decision", "key": key, "id": qid, "sequenced_no": seq, "answer": ans, "quote": quote,
            "path": DECISIONS[key]["md"], "md_sha256": DECISIONS[key]["md_sha256"],
            "json_path": DECISIONS[key]["json"], "json_sha256": DECISIONS[key]["json_sha256"]}


def label(s: dict) -> str:
    t = s["type"]
    simple = {"a9_1": "A9.1", "a9_2": "A9.2", "a9_3": "A9.3", "a9_4": "A9.4", "a9_5": "A9.5", "a9_6": "A9.6"}
    if t in simple:
        return f"{simple[t]} {s['id']}"
    if t == "owner_row":
        return f"row {s['row']}"
    if t == "owner_decision":
        return f"{s['key']} {s['id']}"
    if t == "a9_3_record":
        return f"A9.3 record {s['pointer']}"
    if t == "deliverable_item":
        return f"{s['key']}:{s['id']}" + (f" ({s['locator']})" if s.get("locator") else "")
    if t == "deliverable":
        return s.get("key", s.get("path", "deliverable"))
    if t == "v1_requirement":
        return f"v1 {s['id']}"
    if t == "v2_requirement":
        return f"v2 {s['id']}"
    if t == "pending_lane":
        return f"PENDING {s['path']}"
    if t == "merged_lane":
        return f"{s['key']}:{', '.join(s['ids'])} ({s['path']})"
    if t == "current_deliverable":
        return f"{s['key']}:{s['id']}"
    raise ValueError(t)


def _rename(o, key=None):
    if key in SKIP_RENAME_KEYS:
        return o
    if isinstance(o, dict):
        return {k: _rename(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [_rename(v, key) for v in o]
    if isinstance(o, str):
        return _PKG_RE.sub(lambda m: PKG_RENAME[m.group(0)], o)
    return o


def _decisions_of(srcs: list) -> list:
    out = []
    for s in srcs:
        d = {"key": s["key"], "id": s["id"], "json_path": s["json_path"], "json_sha256": s["json_sha256"]}
        if d not in out:
            out.append(d)
    return out


# ============================================================================== fail-closed rule functions (owner)
PUMPING_FIELDS = ("pumping_speed", "pressure_range", "gas_compatibility", "instrumentation", "interface_conductance")


def external_pumping_acceptance(record) -> dict:
    """A9.8 OQ-RFQV2-02: an external facility (e.g. the owner-named IIST) replaces the quoted P1 pumping train only after
    pumping speed, pressure range, gas compatibility, instrumentation and conductance at the P1 interface are documented
    AND verified. Anything less keeps pumping a required quoted infrastructure item."""
    missing = [f for f in PUMPING_FIELDS
               if not (isinstance(record, dict) and isinstance(record.get(f), dict)
                       and record[f].get("documented") is True and record[f].get("verified") is True
                       and record[f].get("evidence"))]
    if missing:
        return {"state": "NOT_ACCEPTED_UNVERIFIED", "missing": missing,
                "consequence": "pumping remains a required infrastructure item quoted in VAC-L02"}
    return {"state": "EXTERNAL_FACILITY_ACCEPTED_VERIFIED", "missing": [],
            "consequence": "the verified facility pumping may replace VAC-L02 (owner dispatch choice)"}


def combined_load_functions(cert) -> dict:
    """A9.8 OQ-RFQV2-03: one 50-ohm calorimetric dummy load may serve RF-L08 and RF-L09 only if the supplier separately
    certifies (a) the RF load function (rating, return loss at 13.56 MHz) and (b) the calorimetric method, calibration
    and uncertainty; each acceptance function is verified separately."""
    c = cert if isinstance(cert, dict) else {}
    rf = c.get("rf_load", {}) or {}
    cal = c.get("calorimetric", {}) or {}
    rf_ok = bool(rf.get("rating_certified")) and bool(rf.get("return_loss_13p56MHz_certified"))
    cal_ok = all(bool(cal.get(k)) for k in ("method_documented", "calibration_certified", "uncertainty_stated"))
    out = {"RF-L08": "RF_LOAD_FUNCTION_SEPARATELY_CERTIFIED" if rf_ok else "NOT_CERTIFIED_FOR_RF_LOAD_FUNCTION",
           "RF-L09": "CALORIMETRIC_FUNCTION_SEPARATELY_CERTIFIED" if cal_ok else
           "NOT_CERTIFIED_FOR_CALORIMETRIC_FUNCTION"}
    out["one_device_serves_both"] = rf_ok and cal_ok
    out["state"] = ("ONE_DEVICE_SERVES_RF_L08_AND_RF_L09" if rf_ok and cal_ok else
                    "SEPARATE_DEVICE_REQUIRED_FOR_UNCERTIFIED_FUNCTION")
    return out


MAGNET_SUPPLY_FEATURES = ("current_controlled", "floating_where_required", "four_wire_remote_sense",
                          "records_current_and_voltage")


def magnet_supply_substitution(existing, mc1_ratings_registered: bool) -> dict:
    """A9.8 OQ-RFQV2-05: a laboratory magnet supply may replace the quoted HE-L02 channel(s) only once identified and
    verified against the feature list AND the MC-1-coil-design V/I ratings (which do not exist yet -> fail closed)."""
    if not mc1_ratings_registered:
        return {"state": "NOT_EVALUATED_MC1_RATINGS_TBD", "consequence": "quoted HE-L02 channel(s) retained"}
    e = existing if isinstance(existing, dict) else {}
    missing = [f for f in MAGNET_SUPPLY_FEATURES if e.get(f) is not True]
    if e.get("ratings_verified_against_mc1") is not True:
        missing.append("ratings_verified_against_mc1")
    if missing:
        return {"state": "QUOTED_UNIT_RETAINED", "missing": missing, "consequence": "quoted HE-L02 channel(s) retained"}
    return {"state": "VERIFIED_EXISTING_SUPPLY_MAY_REPLACE_QUOTED_UNIT", "missing": []}


DWV_V_DC = 1050.0          # A9.4 P1Q-14 / A9.8 OQ-RFQV2-06, -08 (owner)
DWV_DURATION_S = 60.0      # idem
REVERIFY_V_DC = 700.0      # A9.14 P1Q-17 (owner development acceptance level; triggered only)
DWV_RECORD_FIELDS = ("test_voltage_V", "duration_s", "leakage_current_A", "pressure_gas_condition",
                     "insulation_path_id", "configuration", "observations")
DWV_FAILURE_OBSERVATIONS = ("flashover", "breakdown", "tracking", "disruptive discharge", "protective trip")


def dwv_path_status(rec) -> dict:
    """A9.8 OQ-RFQV2-08 + P1-IT-55: per insulation path, supplier DWV certificate where the rating permits AND an in-house
    current-limited 1.05 kV DC / 60 s DWV of the assembled configuration before first HV/RF, with a pre-registered
    per-path leakage limit from documented hardware qualification. No documented basis -> G0_NOT_EVALUATED_TBD."""
    r = rec if isinstance(rec, dict) else {}
    lim = r.get("leakage_limit") or {}
    if not lim.get("documented_basis") or lim.get("value_A") is None:
        return {"state": "G0_NOT_EVALUATED_TBD", "why": "no documented allowable leakage / insulation-resistance basis "
                                                       "for this path; no generic limit is invented (P1-IT-55)"}
    if lim.get("registered_before_test") is not True:
        return {"state": "INADMISSIBLE_LIMIT_NOT_PREREGISTERED", "why": "the limit must be registered before the test"}
    if r.get("supplier_rating_permits_test") is True and not r.get("supplier_certificate"):
        return {"state": "SUPPLIER_CERTIFICATE_REQUIRED", "why": "the rating permits the 1.05 kV / 60 s factory test"}
    if r.get("in_house_assembled_test") is not True:
        return {"state": "ASSEMBLED_DWV_REQUIRED", "why": "supplier testing does not replace the assembled-system test"}
    missing = [f for f in DWV_RECORD_FIELDS if r.get(f) in (None, "", [])]
    if missing:
        return {"state": "INCOMPLETE_RECORD", "missing": missing}
    if float(r["test_voltage_V"]) < DWV_V_DC or float(r["duration_s"]) < DWV_DURATION_S:
        return {"state": "BELOW_REQUIRED_DWV_LEVEL"}
    obs = " ".join(r["observations"]).lower() if isinstance(r["observations"], list) else str(r["observations"]).lower()
    if any(w in obs for w in DWV_FAILURE_OBSERVATIONS if not ("no " + w) in obs):
        return {"state": "DWV_FAILED", "why": "flashover / breakdown / tracking / disruptive discharge / trip observed"}
    if float(r["leakage_current_A"]) >= float(lim["value_A"]):
        return {"state": "DWV_FAILED", "why": "leakage not below the pre-registered per-path limit"}
    return {"state": "DWV_ACCEPTANCE_EVIDENCE_COMPLETE",
            "note": "measured leakage feeds the P1Q-20 / P1-IT-49 zero-offset/leakage uncertainty"}


VI_IN_HOUSE_MIN_CONTENT = (
    "vna_and_cal_kit_certificates", "complex_vi_gain_13p56MHz", "short_open_known_load_checks",
    "precision_50ohm_reference", "vna_characterized_reactive_reference", "rp_vi_to_rp_ant_fixture",
    "pre_post_calibration_checks", "temperature_and_phase_drift", "repeatability",
    "uncertainty_magnitude_and_relative_phase", "configuration_ids_raw_data_hashes")


def vi_calibration_route(rec) -> dict:
    """A9.11 P2Q-07: accredited (ISO/IEC 17025 / NABL) scope where available; otherwise an in-house VNA-traceable
    calibration with the owner's minimum content, followed by CAL-P2-15 at-power validation; labelled in-house, never
    as accredited; inadequate uncertainty -> NOT_EVALUATED_INSTRUMENT (never reduced administratively)."""
    r = rec if isinstance(rec, dict) else {}
    if r.get("accredited_scope_available") is True:
        if r.get("accredited_certificate"):
            return {"state": "ACCREDITED_CERTIFICATE", "label": "accredited-laboratory certificate"}
        return {"state": "ACCREDITED_CERTIFICATE_REQUIRED"}
    missing = [k for k in VI_IN_HOUSE_MIN_CONTENT if not r.get(k)]
    if missing:
        return {"state": "INCOMPLETE_IN_HOUSE_CALIBRATION", "missing": missing}
    if r.get("uncertainty_adequate") is not True:
        return {"state": "NOT_EVALUATED_INSTRUMENT", "why": "uncertainty inadequate for the impedance discrimination"}
    if not r.get("cal_p2_15_at_power_validation"):
        return {"state": "PENDING_CAL_P2_15_AT_POWER_VALIDATION"}
    return {"state": "IN_HOUSE_TRACEABLE_CALIBRATION",
            "label": "in-house traceable calibration (NOT an accredited-laboratory certificate)"}


def xe_mfc_range_state(xe_reference_point_registered: bool) -> str:
    """A9.14 OQ-RFQ-03: indicative quotes with range options now; range frozen only after the Xe reference point is
    registered."""
    return ("RANGE_MAY_BE_FROZEN_FROM_REGISTERED_REFERENCE_POINT" if xe_reference_point_registered is True else
            "RANGE_OPTIONS_QUOTED_NOT_FROZEN")


RETIRED_MEOP_PLACEHOLDER_BAR = 75.0   # H2-7 H27-34 PROPOSED >= 75 bar (293.15 K check); retired by A9.14 XA9Q-06


def meop_basis_state(proposal) -> dict:
    """A9.14 OQ-RFQ-09 / XA9Q-06: suppliers propose MEOP and design/proof factors against the 323 K design cases; the
    basis is selected only after comparing compliant certified solutions; the 75-bar placeholder is retired."""
    p = proposal if isinstance(proposal, dict) else {}
    if p.get("basis") == "placeholder" or p.get("source") == "H27-34":
        return {"state": "REFUSED_RETIRED_PLACEHOLDER", "why": "the 75-bar placeholder is retired (XA9Q-06)"}
    need = ("supplier_proposed", "design_case_323K", "compliant_certified", "compared_against_other_quotations")
    missing = [k for k in need if p.get(k) is not True]
    if missing:
        return {"state": "NOT_SELECTED_PENDING_COMPLIANT_QUOTATIONS", "missing": missing}
    return {"state": "MEOP_BASIS_SELECTABLE_BY_OWNER", "note": "selection remains an owner act"}


def stand_procurement_paths(paths) -> dict:
    """A9.14 OQ-RFQ-08: the Option-B complete-stand quote is a comparator, never the sole procurement path."""
    s = set(paths or [])
    unknown = s - {"OPTION_A_CRITICAL_PARTS", "OPTION_B_COMPLETE_STAND"}
    if unknown:
        raise ValueError(f"unknown stand procurement path(s): {sorted(unknown)}")
    if s == {"OPTION_B_COMPLETE_STAND"}:
        return {"state": "REFUSED_OPTION_B_NEVER_SOLE_PATH"}
    if "OPTION_A_CRITICAL_PARTS" not in s:
        return {"state": "REFUSED_NO_PROCUREMENT_PATH"}
    return {"state": "ADMISSIBLE", "comparator": "OPTION_B_COMPLETE_STAND" in s}


COIL_WIRE_BASELINE = "plain_ceramic_insulated_copper"
COIL_WIRE_CONTINGENCY = ("ni_clad", "kulgrid")
COIL_WIRE_TRIGGERS = ("oxidation", "supplier_availability", "manufacturing")


def coil_wire_variant(variant: str, trigger=None, evidence=None) -> dict:
    """A9.14 OQ-A907-04: plain ceramic-insulated copper is the baseline; Ni-clad / Kulgrid only as a contingency demanded
    by oxidation, supplier availability or manufacturing, with measured resistance and magnetic perturbation evidence."""
    if variant == COIL_WIRE_BASELINE:
        return {"state": "BASELINE"}
    if variant not in COIL_WIRE_CONTINGENCY:
        return {"state": "NOT_IN_SPECIFICATION"}
    e = evidence if isinstance(evidence, dict) else {}
    if trigger not in COIL_WIRE_TRIGGERS:
        return {"state": "CONTINGENCY_NOT_TRIGGERED"}
    missing = [k for k in ("measured_resistance", "magnetic_perturbation") if not e.get(k)]
    if missing:
        return {"state": "CONTINGENCY_NOT_ADMISSIBLE_EVIDENCE_MISSING", "missing": missing}
    return {"state": "CONTINGENCY_ADMISSIBLE"}


SYSTEM_XE_LINES = ["GAS-L04", "GAS-L08", "GAS-L09", "GAS-L10", "GAS-L11"]
C1_XE_LINES = ["GAS-L05", "GAS-L06", "GAS-L15"]


def xe_capability_scope(configuration: str, c1_selected: bool = False, c1_requires_xe: bool = False) -> dict:
    """A9.15 (amending A9.14 XA9Q-07 / MPQ-01): the RFP-required system Xe propulsion capability (separate Xe tank and
    flow control) is in scope for every configuration incl. hall_icp_neutralizer; C1 Xe lines are added only if a
    selected C1 requires Xe, booked inside the system Xe architecture; C1 absence never removes system Xe."""
    if configuration not in CONFIGS:
        raise ValueError(f"unknown configuration {configuration!r}")
    c1 = bool(c1_selected) and bool(c1_requires_xe)
    return {"system_xe_capability": True, "system_xe_lines": list(SYSTEM_XE_LINES),
            "c1_xe_lines": list(C1_XE_LINES) if c1 else [],
            "c1_xe_booking": ("outside the flight AL-08: separate ground-only laboratory booking (A9.19 / A9.20 / "
                              "A9.21 AL08); A9.15 history reading, superseded: inside the system Xe architecture "
                              "(AL-08 / Xe accounting)" if c1 else "none (no C1 Xe consumption invented)"),
            "basis": "A9.15 governing_rule"}


def icp_xe_getter_requirement(g_xe_variant_declared: bool, spec=None) -> dict:
    """A9.14 XA9Q-05 as amended by A9.15: no default getter/filter on the G-XE ICP path; whether one is needed is an
    engineering / vendor requirement from the selected ICP / material / process or Xe purity specification - never a
    policy choice. C1 getter requirements stay separate (C1-specific, AL-C1)."""
    if g_xe_variant_declared is not True:
        return {"state": "NOT_APPLICABLE_G_XE_VARIANT_NOT_DECLARED"}
    s = spec if isinstance(spec, dict) else {}
    if not s.get("evidence"):
        return {"state": "NOT_INCLUDED_BY_DEFAULT_PENDING_ENGINEERING_SPEC"}
    if s.get("demonstrates_need") is True:
        return {"state": "REQUIRED_BY_ENGINEERING_SPEC", "evidence": s["evidence"]}
    return {"state": "NOT_REQUIRED_BY_ENGINEERING_SPEC", "evidence": s["evidence"]}


_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def h1_fab_send_state(drawing, article="P1_ENGINEERING") -> dict:
    """A9.10 OQ-RFQV2-10: the build-to-print package for the P1 H-1 article is sent for quotation only with a drawing
    set under P9e / Vyovrinda configuration control (drawing ID, revision, content hash; configuration_control =
    P9E_CONFIGURATION_CONTROLLED) and no OPEN / TBD item on the quoted parts. A9.14 F5-OQ-04 (LOCK-1 release basis)
    applies to the FLIGHT H-1 only: article = FLIGHT additionally needs release = LOCK-1. A9.16 repair F4: S3.10 sets
    no LOCK-1 gate for quoting the P1 engineering hardware (recorder reading, for the owner to confirm)."""
    if article not in H1_ARTICLES:
        raise ValueError(f"article {article!r} not in {H1_ARTICLES}")
    d = drawing if isinstance(drawing, dict) else {}
    blockers = [k for k in ("drawing_id", "revision") if not d.get(k)]
    if not _SHA_RE.match(str(d.get("content_sha256", ""))):
        blockers.append("content_sha256")
    if d.get("configuration_control") != H1_CONFIGURATION_CONTROL:
        blockers.append("configuration_control (must be %s)" % H1_CONFIGURATION_CONTROL)
    if d.get("open_items"):
        oi = d["open_items"]
        blockers.append("open_items: " + (oi if isinstance(oi, str) else ", ".join(map(str, oi))))
    if article == "FLIGHT" and d.get("release") != "LOCK-1":
        blockers.append("release (the flight H-1 needs the LOCK-1 release, A9.14 F5-OQ-04)")
    if blockers:
        return {"state": "NOT_SENDABLE_DRAWING_NOT_CONTROLLED" if article == "P1_ENGINEERING"
                else "NOT_SENDABLE_DRAWING_NOT_RELEASED", "article": article, "blockers": blockers}
    return {"state": "READY_TO_SEND_FOR_QUOTATION_BUILD_TO_PRINT", "article": article, "blockers": [],
            "note": "quotation only; no purchase order"}


# =============================================================================================== application layer
class Ctx:
    def __init__(self, doc):
        self.doc = doc
        self.pk = {p["id"]: p for p in doc["packages"]}
        self.applied: dict = {}   # (key, qid) -> {"source":..., "applied_in": set()}

    # lookups
    def line(self, lid):
        for p in self.doc["packages"]:
            for li in p["line_items"]:
                if li["id"] == lid:
                    return p, li
        raise KeyError(lid)

    def req(self, rid):
        for p in self.doc["packages"]:
            for r in p["requirements"]:
                if r["id"] == rid or r["v1_id"] == rid:
                    return p, r
        raise KeyError(rid)

    def _note(self, srcs, where):
        for s in srcs:
            e = self.applied.setdefault((s["key"], s["id"]), {"source": s, "applied_in": set()})
            e["applied_in"].add(where)

    # requirements
    def modify_req(self, rid, srcs, why, **fields):
        _p, r = self.req(rid)
        before = r.setdefault("before_v3", {})
        for k, v in fields.items():
            if k not in before:
                before[k] = copy.deepcopy(r.get(k))
            r[k] = v
        r["sources"] = r["sources"] + [s for s in srcs if s not in r["sources"]]
        ch = r["change_v3"]
        ch["type"] = "MOVED_PACKAGE_MODIFIED" if ch["type"].startswith("MOVED") else "CARRIED_MODIFIED"
        ch["why"] = (ch["why"] + "; " if ch.get("why") else "") + why
        ch["decisions"] += [d for d in _decisions_of(srcs) if d not in ch["decisions"]]
        self._note(srcs, r["id"])
        return r

    def new_req(self, pkg, rid, title, requirement, value, units, srcs, evidence_class, status, freeze, dispatch,
                applies_to=None, note=None, why=None):
        if status not in STATUSES or freeze not in FREEZE_POINTS or dispatch not in DISPATCH:
            raise ValueError(f"{rid}: bad vocabulary")
        if evidence_class is not None and evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"{rid}: bad evidence class {evidence_class}")
        r = {"id": rid, "package": pkg, "v1_id": None, "title": title, "requirement": requirement, "value": value,
             "units": units, "basis": "; ".join(dict.fromkeys(f"{s['key']} {s['id']}" for s in srcs)), "sources": list(srcs),
             "evidence_class": evidence_class, "status": status, "freeze_point": freeze,
             "applies_to": list(applies_to or CONFIGS), "note": note, "dispatch": dispatch,
             "change": {"type": "NEW", "v1_package": None, "why": "new in v3 (see change_v3)"},
             "change_v3": {"type": "NEW", "why": why or "new in v3", "decisions": _decisions_of(srcs)}}
        self.pk[pkg]["requirements"].append(r)
        self._note(srcs, rid)
        return r

    # lines
    def modify_line(self, lid, srcs, why, add_reqs=(), qa=None, qs_replace=None, **fields):
        _p, li = self.line(lid)
        if qs_replace:
            li.setdefault("qs_replace_v3", {}).update(qs_replace)
        before = li.setdefault("before_v3", {})
        for k, v in fields.items():
            if k not in before:
                before[k] = copy.deepcopy(li.get(k))
            li[k] = v
        for rid in add_reqs:
            if rid not in li["requirements"]:
                li["requirements"].append(rid)
        if qa:
            li.setdefault("qa_v3", {"acceptance": [], "calibration_traceability": [], "documentation": []})
            for k, v in qa.items():
                li["qa_v3"][k] += [x for x in v if x not in li["qa_v3"][k]]
        ch = li["change_v3"]
        ch["type"] = "MOVED_PACKAGE_MODIFIED" if ch["type"].startswith("MOVED") else "CARRIED_MODIFIED"
        ch["why"] = (ch["why"] + "; " if ch.get("why") else "") + why
        ch["decisions"] += [d for d in _decisions_of(srcs) if d not in ch["decisions"]]
        self._note(srcs, li["id"])
        return li

    def new_line(self, pkg, lid, item, qty, basis, dispatch, reqs, srcs, why, covers=(), option=False, qa=None,
                 **extra):
        li = {"id": lid, "item": item, "qty": qty, "basis": basis, "dispatch": dispatch, "option_line": option,
              "covers_owner_items": list(covers), "requirements": list(reqs), "v1_ref": None,
              "change": {"type": "NEW", "why": "new in v3 (see change_v3)"},
              "change_v3": {"type": "NEW", "why": why, "decisions": _decisions_of(srcs)}}
        li.update(extra)
        if qa:
            li["qa_v3"] = {"acceptance": list(qa.get("acceptance", [])),
                           "calibration_traceability": list(qa.get("calibration_traceability", [])),
                           "documentation": list(qa.get("documentation", []))}
        self.pk[pkg]["line_items"].append(li)
        self._note(srcs, lid)
        return li

    def supersede_line(self, lid, by, srcs, why):
        p, li = self.line(lid)
        p["line_items"].remove(li)
        self.doc["superseded_lines_v3"].append({"id": lid, "package": p["id"], "superseded_by": by, "why": why,
                                                "decisions": _decisions_of(srcs), "v2_line": li})
        self._note(srcs, lid)

    def move_line(self, lid, to_pkg, srcs, why):
        p, li = self.line(lid)
        p["line_items"].remove(li)
        self.pk[to_pkg]["line_items"].append(li)
        li["change_v3"] = {"type": "MOVED_PACKAGE", "moved_from": p["id"], "why": why,
                           "decisions": _decisions_of(srcs)}
        self._note(srcs, lid)

    def move_req(self, rid, to_pkg, srcs, why):
        p, r = self.req(rid)
        p["requirements"].remove(r)
        r["package"] = to_pkg
        self.pk[to_pkg]["requirements"].append(r)
        r["change_v3"] = {"type": "MOVED_PACKAGE", "moved_from": p["id"], "why": why,
                          "decisions": _decisions_of(srcs)}
        self._note(srcs, rid)


# --------------------------------------------------------------------------------------- the owner decisions (data)
def S():
    """All owner-decision source records used by v3 (verbatim quotes checked against each decision .md)."""
    return {
        "P2Q-02": OD("A9.8", "P2Q-02", "Put the V/I probe, VNA, calibration kits, fixed attenuators, antenna-simulator "
                     "load, antenna current probe, phase-stable VNA cables and associated calibration accessories in a "
                     "dedicated RF-metrology package under the common interface specification."),
        "P2Q-02b": OD("A9.8", "P2Q-02", "This preserves supplier specialisation and prevents the RF source vendor from "
                      "implicitly defining the measurement chain used to validate its own equipment."),
        "OQ-RFQV2-01": OD("A9.8", "OQ-RFQV2-01", "Accept the manufacturer's Ar-specific calibration certificate plus our "
                          "in-house rate-of-rise/transfer verification for the P1 Ar engineering campaign. An ISO/IEC "
                          "17025/NABL certificate is desirable but not mandatory because Ar is being used here for "
                          "engineering/non-scoring development. Score-bearing gas/flow measurements remain subject to "
                          "their stricter traceability requirements."),
        "OQ-RFQV2-02": OD("A9.8", "OQ-RFQV2-02", "RFQ2-VAC shall include the P1 pumping train/pumping capability in the "
                          "quotation scope. We have no registered, qualified existing pumping system on which the P1 "
                          "campaign can presently rely."),
        "OQ-RFQV2-02b": OD("A9.8", "OQ-RFQV2-02", "it can be accepted only after its pumping speed, pressure range, gas "
                           "compatibility, instrumentation and conductance at the P1 interface have been documented and "
                           "verified. Until then the project shall treat pumping as a required infrastructure item."),
        "OQ-RFQV2-03": OD("A9.8", "OQ-RFQV2-03", "One physical 50-ohm calorimetric RF dummy load may serve both "
                          "purposes, provided the supplier separately certifies/documentes:"),
        "OQ-RFQV2-03b": OD("A9.8", "OQ-RFQV2-03", "The same device may therefore be RF-L08/RF-L09 functionally, but the "
                           "two acceptance functions remain separately verified in the evidence record."),
        "OQ-RFQV2-04": OD("A9.8", "OQ-RFQV2-04", "No architecture meaning should be inferred from the "
                          "procurement-package boundary."),
        "OQ-RFQV2-05": OD("A9.8", "OQ-RFQV2-05", "They shall be current-controlled, floating where required, with "
                          "4-wire remote voltage sensing and recorded current/voltage, with final V/I ratings following "
                          "the MC-1 coil design. If a suitable laboratory supply is subsequently identified and verified "
                          "against these requirements, it may replace the quoted unit."),
        "OQ-RFQV2-05b": OD("A9.8", "OQ-RFQV2-05", "Include HE-L02/the required MC-1 laboratory magnet supply "
                           "channel(s) in the P1 quotation package."),
        "OQ-RFQV2-06": OD("A9.8", "OQ-RFQV2-06", "Apply the same 350 V operating-class isolation basis, ≥525 V design "
                          "withstand and 1.05 kV DC / 60 s initial DWV to the H-1 anode/discharge-supply isolation and "
                          "feedthrough paths that can experience the corresponding potential difference."),
        "OQ-RFQV2-06b": OD("A9.8", "OQ-RFQV2-06", "It does not close RF antenna/matching-network insulation, "
                           "Paschen-risk gas paths or combined RF+DC stress; those remain separately qualified."),
        "OQ-RFQV2-08": OD("A9.8", "OQ-RFQV2-08", "Require a supplier/factory DWV certificate wherever the "
                          "component/feedthrough rating permits the 1.05 kV / 60 s test, and then perform an in-house "
                          "current-limited 1.05 kV DC / 60 s DWV test on the assembled insulation configuration before "
                          "first HV/RF operation."),
        "OQ-RFQV2-08b": OD("A9.8", "OQ-RFQV2-08", "Record test voltage, duration, leakage current, pressure/gas "
                           "condition where relevant, insulation path ID, configuration and pass/fail observations. "
                           "Supplier testing does not replace the assembled-system test because assembly, cabling, "
                           "feedthrough installation and grounding can create new failure paths."),
        "P1-IT-55": OD("A9.8", "P1-IT-55", "If an insulation path has no documented allowable leakage/insulation-"
                       "resistance basis from its selected hardware, that path remains `G0_NOT_EVALUATED_TBD`; it shall "
                       "not be declared qualified by inventing a generic leakage-current limit."),
        "P1Q-09": OD("A9.8", "P1Q-09", "The grounded chamber wall shall not be used as the electron collector, including "
                     "for the comparable P1-S4 engineering-surface records."),
        "P1Q-09b": OD("A9.8", "P1Q-09", "Final diameter, axial distance and support dimensions shall be taken from the "
                      "actual ICP module drawing and registered at P1-G0; do not invent dimensions before the module "
                      "geometry exists. 316L is acceptable for the Ar engineering article only; this does not freeze the "
                      "flight collector material."),
        "P3Q-01": OD("A9.8", "P3Q-01", "Add a Langmuir-probe diagnostic near the collector for the Ar P1 development "
                     "campaign to estimate electron temperature and plasma potential and provide an independent "
                     "sheath-model cross-check."),
        "P3Q-01b": OD("A9.8", "P3Q-01", "they must not contaminate an ICP45 capacity record unless probe perturbation "
                      "has first been shown negligible."),
        "OQ-RFQV2-09": OD("A9.10", "OQ-RFQV2-09", "Therefore HE-L10, HE-L11 and HE-L12 do not need to be advanced to "
                          "P1_NEEDED for P1-S6."),
        "OQ-RFQV2-09b": OD("A9.10", "OQ-RFQV2-09", "Its procurement/readiness shall therefore be scheduled against that "
                           "characterization gate, not against P1-S6."),
        "OQ-RFQV2-10": OD("A9.10", "OQ-RFQV2-10", "Create a dedicated H-1 fabrication/build-to-print RFQ package "
                          "covering the H2-1/H2-3 hardware required for the P1 article, including as applicable:"),
        "OQ-RFQV2-10b": OD("A9.10", "OQ-RFQV2-10", "Precision machining, ceramic fabrication, winding or other "
                           "specialist manufacturing may be outsourced through this separate RFQ as build-to-print "
                           "work."),
        "OQ-RFQV2-10c": OD("A9.10", "OQ-RFQV2-10", "As with the existing RFQs, this initially authorizes "
                           "quotation/specification activity only, not an automatic purchase order."),
        "OQ-RFQV2-10d": OD("A9.10", "OQ-RFQV2-10", "Do not place H-1 fabrication inside the ICP mechanical RFQ."),
        "P2Q-07": OD("A9.11", "P2Q-07", "If no ISO/IEC 17025/NABL laboratory is available with an appropriate scope for "
                     "the required V/I-probe magnitude and relative-phase calibration at 13.56 MHz, an in-house "
                     "calibration is acceptable."),
        "P2Q-07b": OD("A9.11", "P2Q-07", "The record shall be identified as an in-house traceable calibration, not "
                      "represented as an accredited-laboratory certificate."),
        "P2Q-07c": OD("A9.11", "P2Q-07", "If the resulting uncertainty is inadequate for the required impedance "
                      "discrimination, the affected measurement is `NOT_EVALUATED_INSTRUMENT`; the uncertainty shall "
                      "not be reduced administratively."),
        "OQ-RFQ-01": OD("A9.14", "OQ-RFQ-01", "SPARES: one spare set of stand flexures; one spare of each breakable ICP "
                        "dielectric/feedthrough item; for C1, one development unit + one spare only if the C1 campaign "
                        "is activated; a sacrificial O/AO unit only where the planned test is destructive."),
        "OQ-RFQ-03": OD("A9.14", "OQ-RFQ-03", "GET INDICATIVE Xe-MFC QUOTES NOW. Request sufficient range options to "
                        "cover the prospective reference/C1 envelope; freeze the range only after the actual Xe "
                        "reference point is registered."),
        "OQ-RFQ-04": OD("A9.14", "OQ-RFQ-04", "DO NOT FREEZE 0.6–0.8 mg/s AS A REQUIREMENT. Quote the second/start "
                        "controller as an option capable of that provisional region, but final start/diode flow comes "
                        "from the selected C1 vendor procedure and characterization."),
        "OQ-RFQ-08": OD("A9.14", "OQ-RFQ-08", "YES, REQUEST OPTION-B COMPLETE-STAND COMPARISON QUOTE. It is a "
                        "commercial/architecture comparator, never the sole procurement path."),
        "OQ-RFQ-09": OD("A9.14", "OQ-RFQ-09", "LET SUPPLIERS PROPOSE MEOP AND DESIGN/PROOF FACTORS. Give them the 323 K "
                        "design cases and required usable/loaded quantities; then select the basis after comparing "
                        "compliant certified solutions."),
        "XA9Q-06": OD("A9.14", "XA9Q-06", "YES, RETIRE THE 75-bar PLACEHOLDER. Request tank/regulator solutions against "
                      "the 323 K volume/pressure cases. Select MEOP only from the actual design case, supplier "
                      "qualification basis and applicable pressure-vessel practice."),
        "XA9Q-01": OD("A9.14", "XA9Q-01", "2/5/10 kg ARE LOADED-Xe CASES. Reserve and residual are carved out within "
                      "each total loaded mass."),
        "OQ-A907-04": OD("A9.14", "OQ-A907-04", "PLAIN CERAMIC-INSULATED COPPER IS THE BASELINE. Ni-clad/Kulgrid remains "
                         "a contingency variant only if oxidation, supplier availability or manufacturing demands it; "
                         "if used it requires measured resistance and magnetic perturbation evidence."),
        "XA9Q-07": OD("A9.14", "XA9Q-07", "YES, Xe CAPABILITY APPLIES TO `hall_icp_neutralizer`. The RFP requires "
                      "compatibility with both ambient air and Xenon and explicitly mentions separate ambient-air and "
                      "Xe propellant storage."),
        "XA9Q-05": OD("A9.14", "XA9Q-05", "NO DEFAULT FILTER/GETTER FOR G-XE ICP. Add one only if the selected "
                      "ICP/material/process or Xe purity specification demonstrates the need. C1 getter requirements "
                      "remain separate."),
        "MQ-05": OD("A9.14", "MQ-05", "AL-08 INCLUDES THE COMPLETE Xe STORAGE/FLOW HARDWARE. Scope includes Xe tank, "
                    "regulator, valves, plumbing, mounting and thermal hardware. The current 5.044 kg incomplete CBE "
                    "floor implies 6.0528 kg MEV planning floor; quotations/design replace this value."),
        "MPQ-01": OD("A9.14", "MPQ-01", "create a separate AL-C1 only for the cathode module, shield/mount and any "
                     "C1-specific getter/filter."),
        "P1Q-17": OD("A9.14", "P1Q-17", "REVERIFICATION = 700 V DC / 60 s."),
        "P1Q-17b": OD("A9.14", "P1Q-17", "This is not a routine pre-run test: use after repair, insulation-path "
                      "modification, suspected fault or other defined requalification trigger."),
        "OQ-RFQV2-10e": OD("A9.10", "OQ-RFQV2-10", "configuration control"),
        "F5-OQ-04": OD("A9.14", "F5-OQ-04", "The released H-1 design must have drawing ID, revision and content hash. "
                       "No OPEN item is silently promoted merely because surrounding geometry is frozen."),
        "F5-OQ-03": OD("A9.14", "F5-OQ-03", "This is only a necessary ceiling, not the usable operating-temperature "
                       "limit"),
        "A915-RULE": OD("A9.15", "governing_rule", "The official RFP is the sole governing basis for propellant "
                        "capability. The system shall support both ambient atmospheric propellant and Xenon. "
                        "C1-specific Xe requirements, if any, are derived from the selected C1 hardware and integrated "
                        "into that RFP-compliant Xe architecture; no independent policy shall restrict or override the "
                        "RFP."),
        "A915-CAP": OD("A9.15", "governing_rule", "Xenon is therefore an RFP-required system capability, not merely a "
                       "contingency introduced by our internal architecture."),
        "A915-C1": OD("A9.15", "governing_rule", "If the selected C1 implementation requires Xenon, its Xe requirement "
                      "shall be included in the system Xe architecture and accounting. If C1 does not require Xe, no "
                      "separate C1 Xe consumption shall be invented."),
        "A915-PRES": OD("A9.15", "governing_rule", "The presence or absence of C1 shall not remove the system-level "
                        "Xenon capability required by the RFP."),
        "A915-TANKS": OD("A9.15", "governing_rule", "It further requires the propulsion system to be compatible with "
                         "both ambient air at 180–230 km and Xenon, with two separate propellant tanks for ambient air "
                         "and Xenon."),
        "A915-XA9Q-07": OD("A9.15", "XA9Q-07", "S8.21 / XA9Q-07: YES — Xe capability applies to the "
                           "`hall_icp_neutralizer` flight configuration because the RFP requires it."),
        "A915-XA9Q-05": OD("A9.15", "XA9Q-05", "S9.3 / XA9Q-05: whether the ICP Xe path needs a getter/filter remains "
                           "an engineering/vendor requirement, not a policy choice."),
        "A915-MPQ-01": OD("A9.15", "MPQ-01", "S8.33 / MPQ-01: if C1 is selected and requires Xe, its C1-specific branch "
                          "is booked within the RFP-compliant Xe system; do not assume or exclude C1 Xe in advance."),
        "A915-OQ-A907-07": OD("A9.15", "OQ-A907-07", "S8.17 / OQ-A907-07: C1 flight integration may still be deferred "
                              "until C1 is selected, but not because Xe is contingency-only."),
        # ---- A9.19 / A9.20 (2026-10-01; the verbatim .md governs)
        "A919-ARCH": OD("A9.19", "architecture", "One Hall accelerator. One RF/ICP electron-source/neutralizer. Two "
                        "propellant supply modes. No conventional hollow cathode."),
        "A919-CATHODELESS": OD("A9.19", "architecture", "our thruster architecture should be cathode/electrodless for "
                               "both the atmosphere gases and xenon"),
        "A919-XE": OD("A9.19", "xenon_role", "xenon is not a parllel gas its just a contigency and emergency gas"),
        "A919-C1MASS": OD("A9.19", "amends", "check C1 mass"),
        "A920-GROUND": OD("A9.20", "answer", "Ground-only reference (Recommended)"),
        "A920-ANS": OD("A9.20", "answer", "will go with your recommended"),
        "A920-ROLE": OD("A9.20", "answer", "It's currently planned for the H-1 baseline characterization that "
                        "registers I_d,max,H1 (your S3.5) and as the control in the C1-vs-ICP bench comparison."),
        "P1Q-07-S35": OD("A9.10", "P1Q-07", "REGISTER `I_d,max,H1` FROM A DEDICATED H-1 CHARACTERIZATION WITH THE "
                         "CONVENTIONAL C1 REFERENCE SOURCE."),
    }


H1FAB_SCOPE = ["Hall channel/body components", "anode and anode distributor/plenum", "gas-path interfaces",
               "ceramic/insulating components", "MC-1 magnetic-circuit mechanical parts",
               "coil formers and winding requirements", "thermal/mechanical mounting interfaces",
               "feedthrough/interface provisions", "dimensional inspection and material certification"]
H1FAB_IN_HOUSE = ["H-1 design authority", "magnetic design", "channel/anode design", "interface definition",
                  "configuration control", "final assembly/integration", "instrumentation", "acceptance testing"]
RFMET_SCOPE = ["V/I probe", "VNA", "calibration kits", "fixed attenuators", "antenna-simulator load",
               "antenna current probe", "phase-stable VNA cables", "associated calibration accessories"]
RFMET_COVER = {"RF-L12": ["V/I probe"], "RF-L13": ["VNA"], "RF-L14": ["calibration kits"],
               "RF-L15": ["fixed attenuators"], "RF-L16": ["antenna-simulator load"],
               "RF-L17": ["phase-stable VNA cables"], "RF-L18": ["antenna current probe"], "RF-O01": []}


def _scope_verbatim_check() -> None:
    _js, md = _decision("A9.10")
    for x in H1FAB_SCOPE + H1FAB_IN_HOUSE:
        if _norm(x) not in md:
            raise ValueError(f"H-1 fabrication scope item not verbatim in A9.10: {x!r}")
    _js, md8 = _decision("A9.8")
    for x in RFMET_SCOPE:
        if _norm(x) not in md8:
            raise ValueError(f"RF-metrology scope item not verbatim in A9.8: {x!r}")


def apply_decisions(c: Ctx, s: dict) -> None:
    TBD_P1G0 = "P1-G0"

    # ---------------------------------------------------------------- A9.8 P2Q-02: separate RF-metrology package
    for rid in RFMET_REQS:
        c.move_req(rid, "RFQ3-RFMET", [s["P2Q-02"]], "P2Q-02: RF measurement equipment in a dedicated RF-metrology "
                                                    "package, separate from RF generation / matching")
    for lid in RFMET_LINES:
        c.move_line(lid, "RFQ3-RFMET", [s["P2Q-02"], s["P2Q-02b"]],
                    "P2Q-02: moved verbatim from RFQ2-RF to the dedicated RF-metrology package")
        _p, li = c.line(lid)
        li["covers_owner_items"] = list(RFMET_COVER[lid])
        if "placement" in li:
            li["placement"] = {"package": "RFQ3-RFMET", "status": "OWNER_DECIDED", "question": "A9.8 P2Q-02",
                               "alternatives": ["RFQ3-RFMET (selected by the owner)"],
                               "rule": "owner decision applied; no architecture meaning (A9.8 OQ-RFQV2-04)"}
    for lid in ("RF-L19",):
        _p, li = c.line(lid)
        li["placement"] = {"package": "RFQ3-RF", "status": "OWNER_DECIDED_BY_INTERPRETATION",
                           "question": "A9.8 P2Q-02 / OQ-RFQV2-04",
                           "alternatives": ["RFQ3-RF (local-matching hardware; recorder reading)"],
                           "rule": "match-element encoders are part of the local matching network (generation / "
                                   "matching hardware), not of the owner's listed measurement equipment; recorder flag "
                                   "RF3-FLAG-01"}
        li["change_v3"]["why"] = "placement resolved by reading P2Q-02 (stays with the local match)"
        li["change_v3"]["type"] = "CARRIED_MODIFIED"
        li["change_v3"]["decisions"] = _decisions_of([s["P2Q-02"]])
        c._note([s["P2Q-02"]], lid)
    c.new_req("RFQ3-RFMET", "RFQ3-RFMET-N01", "RF-metrology package independence",
              "The RF measurement chain (V/I probe, VNA, calibration kits, fixed attenuators, antenna-simulator load, "
              "antenna current probe, phase-stable VNA cables and the associated calibration accessories) is quoted in "
              "this dedicated package under the common interface specification RFQ3-CIF, separate from the RF "
              "generation / matching package RFQ3-RF, so that the RF source vendor does not define the measurement "
              "chain used to validate its own equipment. Interfaces (reference planes RP-RF-50 / RP-VI / RP-ANT, "
              "connector family CIF-C01, time base CIF-T01) are governed by RFQ3-CIF.",
              "separate RF-metrology package under RFQ3-CIF", "-", [s["P2Q-02"], s["P2Q-02b"]], "owner-stated",
              "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.8 P2Q-02")
    c.new_req("RFQ3-RFMET", "RFQ3-RFMET-N02", "V/I-probe magnitude and relative-phase calibration route",
              "The V/I probe (RF-L12) is calibrated for complex V/I gain and relative phase at 13.56 MHz under an "
              "ISO/IEC 17025 / NABL accredited scope where such a scope is available. If no accredited scope exists, "
              "an in-house calibration traceable through the calibrated VNA (RF-L13) and calibration kit (RF-L14) is "
              "acceptable with at least: VNA and kit certificates / traceability; complex V/I gain calibration at "
              "13.56 MHz; short/open/known-load checks at low level; a precision 50-ohm reference; at least one "
              "VNA-characterized reactive reference; RP-VI -> RP-ANT fixture characterization (or verified "
              "coincidence of the planes); pre/post checks; probe/cable temperature and phase-drift contribution; "
              "repeatability; full magnitude AND relative-phase uncertainty propagation; configuration ids, raw data "
              "and hashes. It is followed by the CAL-P2-15 at-power validation (calorimetric 50-ohm load and "
              "VNA-known antenna-simulator load). Such a record is labelled an in-house traceable calibration, never "
              "an accredited certificate; inadequate uncertainty -> NOT_EVALUATED_INSTRUMENT (never reduced "
              "administratively). Supplier states whether it holds / can supply an accredited 13.56 MHz V/I magnitude "
              "and phase scope and which calibration data it delivers to support the in-house route.",
              {"route_1": "accredited ISO/IEC 17025 / NABL scope where available",
               "route_2": "in-house VNA-traceable (minimum content per A9.11 P2Q-07) + CAL-P2-15 at-power validation",
               "label_route_2": "in-house traceable calibration (not accredited)",
               "inadequate_uncertainty": "NOT_EVALUATED_INSTRUMENT",
               "relative_phase_uncertainty": "explicit; never inferred from magnitude calibration"},
              "-", [s["P2Q-07"], s["P2Q-07b"], s["P2Q-07c"]], "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
              why="A9.11 P2Q-07")
    vi_qa = {"acceptance": ["V/I calibration route per RFQ3-RFMET-N02: accredited certificate where an accredited "
                            "13.56 MHz magnitude/phase scope exists, otherwise the in-house traceable record (minimum "
                            "content of A9.11 P2Q-07) followed by CAL-P2-15; inadequate uncertainty -> "
                            "NOT_EVALUATED_INSTRUMENT"],
             "calibration_traceability": ["in-house route traceable through the RF-L13 VNA and RF-L14 calibration-kit "
                                          "certificates; labelled in-house traceable, not accredited (A9.11 P2Q-07)"],
             "documentation": ["supplier statement of any accredited V/I magnitude/relative-phase scope at 13.56 MHz "
                               "and of the calibration data delivered with the probe"]}
    c.modify_line("RF-L12", [s["P2Q-07"], s["P2Q-07b"], s["P2Q-07c"]], "A9.11 P2Q-07 calibration route",
                  add_reqs=["RFQ3-RFMET-N02"], qa=vi_qa)
    for lid in ("RF-L13", "RF-L14"):
        c.modify_line(lid, [s["P2Q-07"]], "A9.11 P2Q-07: traceability anchor of the in-house V/I calibration route",
                      add_reqs=["RFQ3-RFMET-N02"])
    for lid in RFMET_LINES:
        _p, li = c.line(lid)
        if "RFQ3-RFMET-N01" not in li["requirements"]:
            li["requirements"].insert(0, "RFQ3-RFMET-N01")
    c.new_line("RFQ3-RFMET", "RFM-L01",
               "associated calibration accessories for the RF-metrology chain (as required by the offered VNA, "
               "calibration kits and V/I-probe calibration procedure; supplier lists them)",
               "1 set (content TBD - requires the offered VNA / kit / probe and the connector family CIF-C01)",
               "A9.8 P2Q-02", "P1_NEEDED", ["RFQ3-RFMET-N01", "RFQ3-RFMET-N02"], [s["P2Q-02"]],
               "A9.8 P2Q-02: owner-listed 'associated calibration accessories'",
               covers=["associated calibration accessories", "calibration kits"],
               qa={"acceptance": ["accessory list complete against the offered VNA, kit and V/I calibration procedure; "
                                  "every accessory with a calibration-relevant parameter carries its certificate"],
                   "calibration_traceability": ["certificates for accessories that enter the calibration chain "
                                                "(traceable to the RF-L13 / RF-L14 chain)"],
                   "documentation": ["accessory list with part numbers and the calibration step each one serves"]})

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-01: Ar MFC certificate
    c.new_req("RFQ3-GAS", "RFQ3-GAS-N01", "P1 Ar MFC calibration acceptance (engineering, non-scoring)",
              "For the P1 Ar engineering campaign the Ar MFC(s) are accepted on the manufacturer's Ar-specific "
              "calibration certificate plus the in-house rate-of-rise / transfer verification (GAS-L17). An ISO/IEC "
              "17025 / NABL certificate is desirable but NOT mandatory for the P1 Ar path. Score-bearing gas / flow "
              "measurements (N2, O2-bearing, Xe) keep the stricter traceability of RFQ2-GAS-R18.",
              {"mandatory": ["maker's Ar-specific calibration certificate",
                             "in-house rate-of-rise / transfer verification"],
               "desirable_not_mandatory": "ISO/IEC 17025 / NABL certificate (P1 Ar only)",
               "score_bearing_flows": "RFQ2-GAS-R18 unchanged (accredited certificate per device and gas)"},
              "-", [s["OQ-RFQV2-01"]], "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
              applies_to=["hall_c1_reference", "hall_icp_neutralizer"], why="A9.8 OQ-RFQV2-01")
    ar_qa = {"acceptance": ["maker's Ar-specific calibration certificate delivered with the unit (mandatory); in-house "
                            "rate-of-rise / transfer verification on GAS-L17 before first P1 use (mandatory); an "
                            "ISO/IEC 17025 / NABL certificate is desirable, not mandatory, for the P1 Ar path "
                            "(A9.8 OQ-RFQV2-01)"]}
    for lid in ("GAS-L01", "GAS-O01"):
        c.modify_line(lid, [s["OQ-RFQV2-01"]], "A9.8 OQ-RFQV2-01 certificate acceptance", add_reqs=["RFQ3-GAS-N01"],
                      qa=ar_qa)
    c.modify_line("GAS-L16", [s["OQ-RFQV2-01"]], "A9.8 OQ-RFQV2-01: P1 Ar acceptance stated explicitly",
                  add_reqs=["RFQ3-GAS-N01"],
                  item="calibration: own-gas certificate per device and gas; P1 Ar: maker's Ar-specific certificate + "
                       "in-house rate-of-rise/transfer verification (ISO-17025/NABL desirable, not mandatory); "
                       "NABL/ISO-17025 for score-bearing N2/O2/Xe")

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-02: pumping is quoted
    c.modify_req("RFQ2-VAC-N02", [s["OQ-RFQV2-02"], s["OQ-RFQV2-02b"]], "A9.8 OQ-RFQV2-02: pumping quoted, not assumed",
                 title="P1 pumping train (required infrastructure; quoted)",
                 requirement="The P1 pumping train / pumping capability is in the quotation scope: no registered, "
                             "qualified existing pumping system is available on which the P1 campaign can rely. Pumping "
                             "speed, pressure range, gas compatibility (Ar for P1; later N2 / O2-bearing / Xe), "
                             "instrumentation and conductance at the P1 interface are stated by the supplier; the "
                             "required values follow the P1 pumping need for the Ar anchor flow and the stage operating "
                             "domains registered before each stage (A9.8 P1-IT-52) - no number is fixed here. An "
                             "external facility replaces this line only under RFQ3-VAC-N01.",
                 value={"scope": "P1 pumping train quoted (required infrastructure item)",
                        "performance": "TBD - requires the P1 pumping need for the Ar anchor flow (P1-HW-17) and the "
                                       "registered P1 stage domains (P1-IT-52); supplier states speed, range, gas "
                                       "compatibility, instrumentation and interface conductance",
                        "external_facility": "only after documented verification (RFQ3-VAC-N01)"},
                 note="A9.8 OQ-RFQV2-02: do not assume pumping exists")
    c.new_req("RFQ3-VAC", "RFQ3-VAC-N01", "external facility pumping acceptance (fail-closed)",
              "An external test facility (the owner names IIST as an example) may provide the chamber and pumping train "
              "only after its pumping speed, pressure range, gas compatibility, instrumentation and conductance at the "
              "P1 interface have been documented and verified; until then pumping is a required infrastructure item "
              "quoted in VAC-L02 (rule function external_pumping_acceptance).",
              {"required_documented_and_verified": list(PUMPING_FIELDS),
               "default_state": "NOT_ACCEPTED_UNVERIFIED"}, "-", [s["OQ-RFQV2-02b"]], "owner-stated", "OWNER_GIVEN",
              "NOW", "P1_NEEDED", why="A9.8 OQ-RFQV2-02")
    c.modify_line("VAC-L02", [s["OQ-RFQV2-02"], s["OQ-RFQV2-02b"]], "A9.8 OQ-RFQV2-02",
                  add_reqs=["RFQ3-VAC-N01"],
                  item="P1 pumping train / pumping capability (required infrastructure item; quoted - no registered, "
                       "qualified existing pumping system)",
                  qty="1 P1 pumping train (configuration proposed by the supplier; performance TBD - requires P1-HW-17 "
                      "and the registered stage domains)",
                  qa={"acceptance": ["pumping speed, pressure range, gas compatibility, instrumentation and interface "
                                     "conductance demonstrated and documented at the P1 interface (A9.8 OQ-RFQV2-02); "
                                     "an external facility is accepted only under RFQ3-VAC-N01"]})

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-03: combined load
    c.new_req("RFQ3-RF", "RFQ3-RF-N01", "one 50-ohm calorimetric dummy load may serve RF-L08 and RF-L09",
              "One physical 50-ohm calorimetric RF dummy load may serve both the dummy-load (RF-L08) and the "
              "calorimetric cross-check (RF-L09) functions, provided the supplier separately certifies / documents "
              "(a) its RF load function and rating / return loss at 13.56 MHz and (b) its calorimetric measurement "
              "method, calibration and uncertainty. The two acceptance functions remain separately verified in the "
              "evidence record (rule function combined_load_functions); ratings stay TBD_AFTER_IMPEDANCE_MAP.",
              {"rf_load_function": "rating + return loss at 13.56 MHz certified separately",
               "calorimetric_function": "method + calibration + uncertainty certified separately",
               "rating": "TBD_AFTER_IMPEDANCE_MAP"}, "-", [s["OQ-RFQV2-03"], s["OQ-RFQV2-03b"]], "owner-stated",
              "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.8 OQ-RFQV2-03")
    for lid in ("RF-L08", "RF-L09"):
        c.modify_line(lid, [s["OQ-RFQV2-03"], s["OQ-RFQV2-03b"]], "A9.8 OQ-RFQV2-03 combined-device rule",
                      add_reqs=["RFQ3-RF-N01"],
                      qa={"acceptance": ["if one physical device serves RF-L08 and RF-L09: RF load function (rating, "
                                         "return loss at 13.56 MHz) and calorimetric function (method, calibration, "
                                         "uncertainty) each certified and verified separately (A9.8 OQ-RFQV2-03)"]})
    c.modify_line("RF-L09", [s["OQ-RFQV2-03"]], "A9.8 OQ-RFQV2-03",
                  qty="1 (may be the same physical device as RF-L08 under RFQ3-RF-N01)")

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-04: placement accepted
    c.modify_line("RF-L11", [s["OQ-RFQV2-04"]], "A9.8 OQ-RFQV2-04: power analyser stays under RF (allocation accepted; "
                                               "no architecture meaning)")
    c.modify_line("GAS-L08", [s["OQ-RFQV2-04"]], "A9.8 OQ-RFQV2-04: Xe tank/PMU/FCU under gas/metrology accepted")
    c.modify_line("HE-L03", [s["OQ-RFQV2-04"]], "A9.8 OQ-RFQV2-04: collector/bias supply under Hall electrical "
                                               "accepted")

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-05: magnet supply in P1 set
    c.modify_req("RFQ2-HALLEL-N02", [s["OQ-RFQV2-05"], s["OQ-RFQV2-05b"]], "A9.8 OQ-RFQV2-05",
                 title="H-1 / MC-1 laboratory magnet supply channel(s) (P1 quotation set)",
                 requirement="Laboratory magnet supply channel(s) for the MC-1 coil(s): current-controlled, floating "
                             "where required, 4-wire remote voltage sensing, recorded current and voltage (DAQ), own "
                             "bus slot. Final V/I ratings follow the MC-1 coil design (not fixed here). Included in the "
                             "P1 quotation set because no existing laboratory magnet supply is assumed; a suitable "
                             "laboratory supply identified later and verified against these requirements may replace "
                             "the quoted unit (rule function magnet_supply_substitution). Quotation / specification "
                             "only, not authorization to purchase.",
                 value={"control": "current-controlled", "output": "floating where required",
                        "sensing": "4-wire remote voltage sense", "records": "current and voltage",
                        "V_I_ratings": "TBD - requires the MC-1 coil design currents and resistances (H2-1)",
                        "substitution": "verified existing supply may replace the quoted unit"},
                 status="TBD", freeze_point="LOCK-1")
    c.modify_line("HE-L02", [s["OQ-RFQV2-05"], s["OQ-RFQV2-05b"]], "A9.8 OQ-RFQV2-05: in the P1 quotation set",
                  item="H-1 / MC-1 laboratory magnet supply channel(s): current-controlled, floating where required, "
                       "4-wire remote sense, recorded I/V (ratings from the MC-1 coil design)",
                  qty="TBD - one channel per MC-1 coil (count and V/I ratings require the MC-1 coil design, H2-1)",
                  qa={"acceptance": ["current regulation, floating isolation (where required), 4-wire sense and I/V "
                                     "recording demonstrated; ratings checked against the MC-1 coil design once "
                                     "registered (A9.8 OQ-RFQV2-05)"]})

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-06 (+ P1Q-17, P1-IT-55)
    reverify = {"V_DC": REVERIFY_V_DC, "duration_s": 60.0, "mode": "current-limited controlled DC test at "
                "representative pressure/gas; triggered only (after repair, insulation-path modification, suspected "
                "fault or other defined requalification trigger); not a routine pre-run test (A9.14 P1Q-17)"}
    leak = ("per-path numerical limit pre-registered before the test from the most restrictive documented "
            "component / feedthrough / insulator qualification or supplier acceptance specification incl. "
            "assembled-system measurement uncertainty; no documented basis -> G0_NOT_EVALUATED_TBD (A9.8 P1-IT-55)")
    c.new_req("RFQ3-HALLEL", "RFQ3-HALLEL-N01",
              "H-1 anode / discharge-supply isolation and feedthrough paths: 350 V class, >= 525 V, 1.05 kV DC / 60 s",
              "The H-1 anode / discharge-supply isolation and feedthrough paths that can experience the corresponding "
              "potential difference are designed to the 350 V operating class with a design withstand >= 525 V and are "
              "qualified with a 1.05 kV DC / 60 s initial DWV (current-limited, leakage recorded) - the same basis as "
              "the ICP body / collector circuits (CIF-G07). This closes the row-81 transient / qualification margin "
              "for that DC isolation class only. RF antenna / matching-network insulation (ICD ICP-44), Paschen-risk "
              "gas paths (incl. the ~1 kV representative-gas isolator qualification RFQ2-GAS-N04 / N05) and combined "
              "RF + DC stress remain separately qualified (OPEN).",
              {"V_operating_class_V": 350.0, "V_design_withstand_min_V": 525.0, "initial_DWV_V_DC": DWV_V_DC,
               "initial_DWV_duration_s": DWV_DURATION_S, "leakage_acceptance": leak,
               "triggered_reverification": reverify,
               "not_covered": ["RF antenna / matching-network insulation (ICP-44)", "Paschen-risk gas paths",
                               "combined RF + DC stress"]},
              "V; s", [s["OQ-RFQV2-06"], s["OQ-RFQV2-06b"], s["P1Q-17"], s["P1Q-17b"], s["P1-IT-55"]],
              "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.8 OQ-RFQV2-06 (+ A9.14 P1Q-17, A9.8 P1-IT-55)")
    for lid in ("HE-L01", "HE-L04"):
        c.modify_line(lid, [s["OQ-RFQV2-06"]], "A9.8 OQ-RFQV2-06 isolation class", add_reqs=["RFQ3-HALLEL-N01"])
    c.modify_line("VAC-L03", [s["OQ-RFQV2-06"]], "A9.8 OQ-RFQV2-06 isolation class for anode / discharge feedthroughs",
                  add_reqs=["RFQ3-HALLEL-N01"])
    c.modify_req("RFQ2-VAC-N03", [s["OQ-RFQV2-06"], s["OQ-RFQV2-06b"]],
                 "A9.8 OQ-RFQV2-06 closes the row-81 margin for the DC isolation class",
                 requirement="Current-carrying feedthrough pins sized to the 8.33 A stand ceiling (bench design "
                             "ceiling, not an H-1 requirement); H-1 anode / discharge feedthrough paths that can see "
                             "the corresponding potential difference: 350 V operating class, design withstand >= 525 V, "
                             "1.05 kV DC / 60 s initial DWV (RFQ3-HALLEL-N01). RF feedthroughs are in RFQ3-RF "
                             "(RFQ-04-R12 carried); RF / Paschen / combined RF + DC stress remain separately qualified.",
                 value={"current_A_min_rating": 8.333333, "voltage_V_operating_class": 350.0,
                        "V_design_withstand_min_V": 525.0, "initial_DWV_V_DC": DWV_V_DC,
                        "initial_DWV_duration_s": DWV_DURATION_S, "leakage_acceptance": leak})
    for rid in ("RFQ2-VAC-N07",):
        _p, r = c.req(rid)
        v = copy.deepcopy(r["value"])
        v["leakage_acceptance"] = leak
        c.modify_req(rid, [s["P1-IT-55"]], "A9.8 P1-IT-55 per-path leakage limit", value=v)
    _p, r = c.req("RFQ2-HALLEL-N04")
    v = copy.deepcopy(r["value"])
    v["leakage_acceptance"] = leak
    v["later_reverification"] = reverify
    c.modify_req("RFQ2-HALLEL-N04", [s["P1-IT-55"], s["P1Q-17"], s["P1Q-17b"]],
                 "A9.8 P1-IT-55 leakage rule; A9.14 P1Q-17 triggered 700 V DC / 60 s reverification", value=v)

    # ---------------------------------------------------------------- A9.8 OQ-RFQV2-08: supplier + in-house DWV
    c.new_req("RFQ3-HALLEL", "RFQ3-HALLEL-N02", "DWV evidence route: supplier certificate AND in-house assembled DWV",
              "A supplier / factory DWV certificate is required wherever the component / feedthrough rating permits "
              "the 1.05 kV / 60 s test; in addition an in-house current-limited 1.05 kV DC / 60 s DWV is performed on "
              "the assembled insulation configuration before first HV/RF operation (sensitive electronics may be "
              "disconnected). Supplier testing never replaces the assembled-system test. Each record carries: test "
              "voltage, duration, leakage current, pressure / gas condition where relevant, insulation path id, "
              "configuration and pass / fail observations; the leakage limit is the per-path pre-registered limit "
              "(P1-IT-55; no documented basis -> G0_NOT_EVALUATED_TBD); the measured leakage feeds P1Q-20 / P1-IT-49 "
              "(rule function dwv_path_status).",
              {"supplier_certificate": "where the item rating permits 1.05 kV DC / 60 s",
               "in_house_assembled_DWV": {"V_DC": DWV_V_DC, "duration_s": DWV_DURATION_S, "current_limited": True,
                                          "when": "before first HV/RF operation"},
               "record_fields": list(DWV_RECORD_FIELDS), "leakage_acceptance": leak},
              "V; s; A", [s["OQ-RFQV2-08"], s["OQ-RFQV2-08b"], s["P1-IT-55"]], "owner-stated", "OWNER_GIVEN", "NOW",
              "P1_NEEDED", why="A9.8 OQ-RFQV2-08 (+ P1-IT-55)")
    c.modify_req("RFQ2-HALLEL-N09", [s["OQ-RFQV2-08"], s["P1Q-17"]],
                 "A9.8 OQ-RFQV2-08: in-house assembled DWV is required -> the tester is a required line (HE-L19)",
                 title="current-limited DC dielectric-withstand tester (>= 1.05 kV; 700 V reverification)",
                 requirement="Current-limited DC dielectric-withstand tester able to apply at least 1.05 kV DC for 60 s "
                             "with leakage-current read-out, for the required in-house DWV of the assembled insulation "
                             "configuration before first HV/RF operation (A9.8 OQ-RFQV2-08), and the triggered "
                             "700 V DC / 60 s reverification (A9.14 P1Q-17). Leakage read-out resolution follows the "
                             "per-path pre-registered limits (P1-IT-55).",
                 value={"V_DC_min": DWV_V_DC, "duration_s": DWV_DURATION_S, "reverification_V_DC": REVERIFY_V_DC,
                        "current_limited": True, "leakage_readout": "required",
                        "leakage_resolution": "TBD - requires the per-path pre-registered leakage limits (P1-IT-55)",
                        "need": "REQUIRED (A9.8 OQ-RFQV2-08: in-house assembled DWV)"},
                 note="A9.8 OQ-RFQV2-08 removes the option status (both supplier certificate and in-house test)")
    c.new_line("RFQ3-HALLEL", "HE-L19",
               "current-limited DC dielectric-withstand tester >= 1.05 kV DC / 60 s with leakage read-out (also the "
               "700 V DC / 60 s triggered reverification) (P1-HW-30)",
               1, "A9.8 OQ-RFQV2-08; A9.14 P1Q-17; P1-HW-30", "P1_NEEDED", ["RFQ2-HALLEL-N09", "RFQ3-HALLEL-N02"],
               [s["OQ-RFQV2-08"], s["P1Q-17"]], "A9.8 OQ-RFQV2-08: the in-house assembled DWV is required",
               covers=["isolation"],
               qa={"acceptance": ["output voltage and timer verified at 1.05 kV and 700 V; current limit and leakage "
                                  "read-out verified against a reference resistor"],
                   "calibration_traceability": ["voltage and leakage-current read-out calibration certificate "
                                                "(traceable); uncertainty stated for the leakage read-out"],
                   "documentation": ["operating manual; current-limit settings; data export of voltage, time and "
                                     "leakage for the RFQ3-HALLEL-N02 record fields"]})
    c.supersede_line("HE-O02", "HE-L19", [s["OQ-RFQV2-08"]],
                     "A9.8 OQ-RFQV2-08 requires the in-house assembled DWV, so the tester is no longer an option line")
    dwv_qa = {"acceptance": ["supplier / factory DWV certificate (1.05 kV DC / 60 s) wherever the item rating permits; "
                             "the in-house assembled DWV before first HV/RF operation is performed in addition "
                             "(A9.8 OQ-RFQV2-08)"],
              "documentation": ["per item: rated withstand, whether the rating permits 1.05 kV / 60 s, documented "
                                "allowable leakage / insulation resistance (basis of the per-path limit, P1-IT-55)"]}
    for lid in ("HE-L04", "VAC-L03"):
        c.modify_line(lid, [s["OQ-RFQV2-08"], s["P1-IT-55"]], "A9.8 OQ-RFQV2-08 DWV evidence route",
                      add_reqs=["RFQ3-HALLEL-N02"], qa=dwv_qa)

    # ---------------------------------------------------------------- A9.10 OQ-RFQV2-09: C1 stays LATER
    c1_gate = {"gate": "H-1 reference characterization with the conventional C1 (A9.10 P1Q-07; before the Ar "
                       "I_d,max,H1 registration and P1-S7)",
               "p1_s6": "C1 may be physically absent (C1_NOT_INSTALLED); not needed for P1-S6",
               "c1_campaign": "development unit + spare only if the C1 campaign is activated (A9.14 OQ-RFQ-01)"}
    for lid in ("HE-L10", "HE-L11", "HE-L12"):
        c.modify_line(lid, [s["OQ-RFQV2-09"], s["OQ-RFQV2-09b"]],
                      "A9.10 OQ-RFQV2-09: stays LATER; scheduled against the H-1 reference characterization gate",
                      dispatch_gate=c1_gate)
    c.modify_line("HE-L10", [s["OQ-RFQ-01"]], "A9.14 OQ-RFQ-01 C1 spares conditional",
                  qty="1 development unit + 1 spare - only if the C1 campaign is activated (A9.14 OQ-RFQ-01)")
    c.modify_line("HE-O01", [s["OQ-RFQ-01"]], "A9.14 OQ-RFQ-01 sacrificial unit conditional",
                  qty="0 or 1 (option line) - only where the planned O/AO test is destructive (A9.14 OQ-RFQ-01)")

    # ---------------------------------------------------------------- A9.10 OQ-RFQV2-10: separate H-1 fabrication RFQ
    h1src = [s["OQ-RFQV2-10"], s["OQ-RFQV2-10b"], s["OQ-RFQV2-10c"], s["OQ-RFQV2-10d"]]
    c.new_req("RFQ3-H1FAB", "RFQ3-H1FAB-N01", "build-to-print scope and in-house design authority",
              "Build-to-print fabrication of the H2-1 / H2-3 hardware required for the P1 H-1 article (precision "
              "machining, ceramic fabrication, winding or other specialist manufacturing), separate from the ICP "
              "mechanical package RFQ3-MECH. The supplier fabricates to the controlled drawings only; H-1 design "
              "authority, magnetic design, channel / anode design, interface definition, configuration control, final "
              "assembly / integration, instrumentation and acceptance testing remain in-house (P9e / Vyovrinda). No "
              "supplier design input changes a drawing without an in-house drawing revision.",
              {"scope_verbatim": list(H1FAB_SCOPE), "retained_in_house_verbatim": list(H1FAB_IN_HOUSE),
               "work_type": "build-to-print"}, "-", h1src, "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
              why="A9.10 OQ-RFQV2-10")
    c.new_req("RFQ3-H1FAB", "RFQ3-H1FAB-N02", "controlled H-1 drawing set of the P1 engineering article (send "
              "precondition)",
              "The package is sent for quotation only with the drawing set of the P1 engineering H-1 article under "
              "P9e / Vyovrinda configuration control: drawing id, revision and content hash for every part; an item "
              "marked OPEN / TBD / TBD_AFTER_EVIDENCE on a quoted part blocks sending and is never silently promoted "
              "(rule function h1_fab_send_state, article P1_ENGINEERING). The LOCK-1 release basis of A9.14 F5-OQ-04 "
              "(F5 ENGINEERING_FREEZE_CANDIDATE -> LOCK-1) governs the FLIGHT H-1 drawing release, not the quotation of "
              "the P1 engineering hardware.",
              {"drawing_id": "TBD - registered from the P9e configuration-controlled P1 engineering drawing set",
               "revision": "TBD", "content_sha256": "TBD", "configuration_control": H1_CONFIGURATION_CONTROL,
               "open_items": "blockers for the quoted parts",
               "flight_h1_release_basis": "LOCK-1 release (drawing id, revision, content hash; every OPEN / TBD item "
                                          "an explicit blocker; A9.14 F5-OQ-04) - the flight H-1 only",
               "reading": "A9.16 repair F4 recorder reading for the owner to confirm: A9.10 S3.10 creates the package "
                          "for 'the H2-1/H2-3 hardware required for the P1 article' and keeps configuration control "
                          "in-house; it sets no LOCK-1 gate, so a LOCK-1 release is not required to quote the P1 "
                          "engineering article"},
              "-", [s["OQ-RFQV2-10"], s["OQ-RFQV2-10e"], s["F5-OQ-04"]], None, "TBD", "P1-G0", "P1_NEEDED",
              why="A9.10 OQ-RFQV2-10 (controlled P1 engineering drawing set; A9.14 F5-OQ-04 kept for the flight H-1; "
                  "A9.16 repair F4)")
    c.new_req("RFQ3-H1FAB", "RFQ3-H1FAB-N03", "coil winding wire",
              "Coil windings use plain ceramic-insulated copper (baseline). Ni-clad / Kulgrid wire is a contingency "
              "variant only (option line H1-O01), used only if oxidation, supplier availability or manufacturing demands "
              "it, and then only with measured resistance and magnetic-perturbation evidence (rule function "
              "coil_wire_variant). Conductor size, turns, insulation class and winding geometry per the controlled "
              "MC-1 drawing.",
              {"baseline": "plain ceramic-insulated copper", "contingency": "Ni-clad / Kulgrid (H1-O01)",
               "contingency_triggers": list(COIL_WIRE_TRIGGERS),
               "contingency_evidence": ["measured resistance", "magnetic perturbation"],
               "winding_data": "TBD - requires the controlled MC-1 drawing"}, "-", [s["OQ-A907-04"]], "owner-stated",
              "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.14 OQ-A907-04")
    c.new_req("RFQ3-H1FAB", "RFQ3-H1FAB-N04", "materials, dimensional inspection and material certification",
              "Every part is made from the material and to the tolerances of its controlled drawing, with a material "
              "certificate per part / heat lot and a dimensional inspection report against the drawing. Material "
              "choices are design-authority items: the H-1 anode material is OPEN and 316L is REJECTED_AS_CURRENT_"
              "BASELINE for the design-representative / flight anode (A9.2) - the supplier proposes no substitute. For "
              "magnetic-circuit iron the supplier delivers the grade certificate and any temperature-dependent "
              "magnetic data it holds; the design authority uses 754 degC only as a necessary ceiling pending grade "
              "data (A9.14 F5-OQ-03), never as an operating limit or acceptance value. Ceramic / insulating parts on the "
              "anode / discharge path meet RFQ3-HALLEL-N01 as installed. No thermal PASS is inferred from any "
              "supplier statement (anode and coupled thermal closure UNRESOLVED).",
              {"material": "per controlled drawing", "anode_material": "OPEN (A9.2); 316L REJECTED_AS_CURRENT_BASELINE",
               "certificates": "per part / heat lot", "inspection": "dimensional report vs drawing tolerances",
               "thermal": "UNRESOLVED (never PASS)"}, "-", [s["OQ-RFQV2-10"], s["F5-OQ-03"]], "owner-stated",
              "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.10 OQ-RFQV2-10 (+ A9.14 F5-OQ-03)")
    h1_qty = "TBD - per the controlled P1 engineering drawing set (RFQ3-H1FAB-N02)"
    h1_lines = [
        ("H1-L01", "Hall channel / body components (build-to-print)", ["Hall channel/body components"], []),
        ("H1-L02", "anode and anode distributor / plenum (build-to-print; material per controlled drawing - anode "
                   "material OPEN)", ["anode and anode distributor/plenum"], []),
        ("H1-L03", "gas-path interfaces of the H-1 Ar feed to the anode plenum (fittings / ports per drawing; the "
                   "anode gas isolator is GAS-L13)", ["gas-path interfaces"], []),
        ("H1-L04", "ceramic / insulating components (per drawing; anode / discharge-path insulators meet RFQ3-HALLEL-N01)",
         ["ceramic/insulating components"], ["RFQ3-HALLEL-N01"]),
        ("H1-L05", "MC-1 magnetic-circuit mechanical parts (per drawing)",
         ["MC-1 magnetic-circuit mechanical parts"], []),
        ("H1-L06", "coil formers and windings (plain ceramic-insulated copper baseline)",
         ["coil formers and winding requirements"], ["RFQ3-H1FAB-N03"]),
        ("H1-L07", "thermal / mechanical mounting interfaces (per drawing; interface definition in-house)",
         ["thermal/mechanical mounting interfaces"], []),
        ("H1-L08", "feedthrough / interface provisions on the H-1 article (per drawing)",
         ["feedthrough/interface provisions"], ["RFQ3-HALLEL-N01"]),
        ("H1-L09", "dimensional inspection reports and material certificates for every H1-L01..L08 part",
         ["dimensional inspection and material certification"], []),
    ]
    h1_qa = {"acceptance": ["incoming inspection in-house against the controlled drawing (dimensions, material "
                            "certificate, visual); acceptance testing of the assembled H-1 stays in-house"],
             "calibration_traceability": ["supplier inspection instruments calibrated (certificate reference on the "
                                          "inspection report)"],
             "documentation": ["material certificates, dimensional inspection report, drawing id / revision / hash "
                               "fabricated to, non-conformance reports"]}
    for lid, item, cov, extra in h1_lines:
        c.new_line("RFQ3-H1FAB", lid, item, h1_qty, "A9.10 OQ-RFQV2-10; H2-1 / H2-3", "P1_NEEDED",
                   ["RFQ3-H1FAB-N01", "RFQ3-H1FAB-N02", "RFQ3-H1FAB-N04"] + extra, h1src,
                   "A9.10 OQ-RFQV2-10: separate H-1 build-to-print package", covers=cov, qa=h1_qa)
    c.new_line("RFQ3-H1FAB", "H1-O01", "OPTION: Ni-clad / Kulgrid coil wire (contingency variant only)",
               "0 or 1 (option line; contingency only)", "A9.14 OQ-A907-04", "P1_NEEDED",
               ["RFQ3-H1FAB-N01", "RFQ3-H1FAB-N02", "RFQ3-H1FAB-N03"], [s["OQ-A907-04"]],
               "A9.14 OQ-A907-04: contingency option only", covers=["coil formers and winding requirements"],
               option=True,
               qa={"acceptance": ["used only on a recorded trigger (oxidation / supplier availability / manufacturing) "
                                  "with measured resistance and magnetic-perturbation evidence"],
                   "calibration_traceability": ["resistance measurement traceable; magnetic-perturbation measurement "
                                                "method stated"],
                   "documentation": ["wire datasheet, cladding / insulation data, resistance per length"]})

    # ---------------------------------------------------------------- A9.14 OQ-RFQ-01: spares
    c.new_req("RFQ3-MECH", "RFQ3-MECH-N01", "ICP spares rule",
              "One spare of each breakable ICP dielectric / feedthrough item is quoted with the item (dielectric source "
              "tube / chamber, ICP RF feedthrough, ICP body / collector feedthrough assemblies). No other spare is "
              "assumed.", {"rule": "one spare of each breakable ICP dielectric / feedthrough item"}, "-",
              [s["OQ-RFQ-01"]], "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", why="A9.14 OQ-RFQ-01")
    c.modify_line("ME-L01", [s["OQ-RFQ-01"]], "A9.14 OQ-RFQ-01", add_reqs=["RFQ3-MECH-N01"],
                  qty="TBD - requires module drawings; + 1 spare of each breakable dielectric item (A9.14 OQ-RFQ-01)")
    c.modify_line("RF-L07", [s["OQ-RFQ-01"]], "A9.14 OQ-RFQ-01", add_reqs=["RFQ3-MECH-N01"],
                  qty="TBD - requires module drawings (ICD ICP-15); + 1 spare (A9.14 OQ-RFQ-01)")
    c.new_req("RFQ3-THRUST", "RFQ3-THRUST-N02", "stand spares",
              "One spare set of stand flexures.", {"flexure_spare_sets": 1}, "set", [s["OQ-RFQ-01"]], "owner-stated",
              "OWNER_GIVEN", "NOW", "LATER", why="A9.14 OQ-RFQ-01")
    c.modify_line("TH-L03", [s["OQ-RFQ-01"]], "A9.14 OQ-RFQ-01", add_reqs=["RFQ3-THRUST-N02"],
                  item="spare flexure pivots (one spare set of stand flexures)", qty="1 spare set")

    # ---------------------------------------------------------------- A9.14 OQ-RFQ-08: Option-B comparator
    c.new_req("RFQ3-THRUST", "RFQ3-THRUST-N01", "Option-B complete-stand comparison quotation",
              "Request an Option-B complete open-design stand quotation as a commercial / architecture comparator. It "
              "is never the sole procurement path: the Option-A critical-part path (TH-L01) remains quoted (rule "
              "function stand_procurement_paths).", {"option_b": "comparison quote", "sole_path": False}, "-",
              [s["OQ-RFQ-08"]], "owner-stated", "OWNER_GIVEN", "NOW", "LATER", why="A9.14 OQ-RFQ-08")
    c.modify_line("TH-O01", [s["OQ-RFQ-08"]], "A9.14 OQ-RFQ-08: comparison quote requested",
                  add_reqs=["RFQ3-THRUST-N01"],
                  qty="1 comparison quotation (option line; never the sole procurement path)",
                  item="OPTION: complete open-design torsional stand (Option B) - comparison quotation only; Option A "
                       "(TH-L01) remains the procurement path")

    # ---------------------------------------------------------------- A9.14 OQ-RFQ-03: Xe MFC indicative quotes
    _p, r = c.req("RFQ-02-R07")
    c.modify_req("RFQ-02-R07", [s["OQ-RFQ-03"], s["A915-CAP"]], "A9.14 OQ-RFQ-03 indicative quotes now; A9.15",
                 title="Xe anode path (RFP-required system Xe propulsion capability; reference / health check)",
                 requirement="Xe anode-path flow control for the RFP-required Xe propulsion capability and the bounded "
                             "Xe reference / health check at the start of each installation (before N2 and any "
                             "O2-bearing exposure). Indicative quotations are requested now with range options that "
                             "cover the prospective reference / C1 envelope; the range is frozen only after the actual "
                             "Xe reference point is registered (rule function xe_mfc_range_state).",
                 value={"quotation": "indicative, now, with range options",
                        "range": "TBD - frozen only after the Xe reference point is registered (A9-01; XE_REFERENCE "
                                 "term)", "range_state": "RANGE_OPTIONS_QUOTED_NOT_FROZEN"},
                 freeze_point="after-evidence")
    c.modify_line("GAS-L04", [s["OQ-RFQ-03"], s["A915-CAP"]], "A9.14 OQ-RFQ-03; A9.15 system Xe capability",
                  item="Xe anode-path MFC(s) (RFP-required system Xe propulsion capability; reference / health check) - "
                       "indicative quotation with range options",
                  qty="range options (supplier proposes ranges covering the prospective reference / C1 envelope); "
                      "count frozen with the range after the Xe reference point is registered",
                  quotation_timing="INDICATIVE_QUOTE_NOW")

    # ---------------------------------------------------------------- A9.14 OQ-RFQ-04: C1 start controller option
    c.modify_req("RFQ-02-R11", [s["OQ-RFQ-04"], s["A915-C1"]], "A9.14 OQ-RFQ-04: option, region not frozen",
                 title="C1 start/diode-flow controller - OPTION (provisional region, not frozen)",
                 requirement="Quote the second / start controller as an OPTION capable of the provisional 0.6-0.8 mg/s "
                             "region. 0.6-0.8 mg/s is NOT a frozen requirement: the final start / diode flow comes from "
                             "the selected C1 vendor procedure and characterization; any C1 Xe is booked inside the "
                             "system Xe architecture only if a selected C1 requires it (A9.15).",
                 value={"provisional_region_mgps": [0.6, 0.8], "frozen": False,
                        "final": "TBD - from the selected C1 vendor procedure and characterization"},
                 freeze_point="after-evidence")
    c.modify_line("GAS-L06", [s["OQ-RFQ-04"]], "A9.14 OQ-RFQ-04: option line",
                  option_line=True, qty="0 or 1 (option line; provisional 0.6-0.8 mg/s region, not frozen)",
                  item="OPTION: C1 start/diode-flow Xe controller (capable of the provisional 0.6-0.8 mg/s region; "
                       "final flow from the selected C1 vendor procedure)")

    # ---------------------------------------------------------------- A9.14 OQ-RFQ-09 / XA9Q-06: MEOP by supplier
    _p, r = c.req("RFQ-07-R04")
    v = copy.deepcopy(r["value"])
    axis = v.pop("V_min_323K_l_by_case_and_MEOP_axis")
    retired = {case: {"75bar": vals["75bar"]} for case, vals in axis.items()}
    v["V_min_323K_l_by_case_sensitivity_axis"] = {case: {k: x for k, x in vals.items() if k != "75bar"}
                                                  for case, vals in axis.items()}
    v["retired_placeholder_points"] = {"values_L": retired, "state": "RETIRED (A9.14 XA9Q-06; H2-7 H27-34 "
                                                                      "PROPOSED >= 75 bar placeholder)"}
    v["MEOP"] = ("TBD - proposed by each supplier (MEOP and design / proof factors) against the 323 K design cases; "
                 "the basis is selected only after comparing compliant certified solutions (A9.14 OQ-RFQ-09, XA9Q-06); "
                 "the pressures above are a sensitivity axis, not a MEOP choice")
    v["case_reading"] = "LOADED Xe incl. reserve and residual (A9.14 XA9Q-01)"
    c.modify_req("RFQ-07-R04", [s["OQ-RFQ-09"], s["XA9Q-06"], s["XA9Q-01"]],
                 "A9.14 OQ-RFQ-09 / XA9Q-06: supplier-proposed MEOP; 75-bar placeholder retired",
                 requirement="Tank internal volume, MEOP and design / proof factors per case are PROPOSED BY THE "
                             "SUPPLIER against the 323 K design cases and the required usable / loaded quantities "
                             "(2 / 5 / 10 kg loaded Xe incl. reserve and residual); the MEOP basis is selected only "
                             "after comparing compliant certified solutions, from the actual design case, supplier "
                             "qualification basis and applicable pressure-vessel practice. The 75-bar placeholder is "
                             "retired (rule function meop_basis_state).", value=v)
    c.new_req("RFQ3-GAS", "RFQ3-GAS-N02", "MEOP and design / proof factors proposed by the supplier",
              "Each tank / regulator quotation states its proposed MEOP, design and proof factors and qualification "
              "basis for each 323 K design case; no MEOP is prescribed by this RFQ; the 75-bar placeholder is not a "
              "basis.", {"MEOP": "supplier-proposed per case", "selection": "after comparing compliant certified "
                         "solutions", "retired_placeholder_bar": RETIRED_MEOP_PLACEHOLDER_BAR},
              "bar; -", [s["OQ-RFQ-09"], s["XA9Q-06"]], "owner-stated", "OWNER_GIVEN", "NOW", "LATER",
              why="A9.14 OQ-RFQ-09, XA9Q-06")

    # ---------------------------------------------------------------- A9.14 XA9Q-07 + A9.15: system Xe capability
    xe_src = [s["A915-RULE"], s["A915-CAP"], s["A915-C1"], s["A915-PRES"], s["A915-TANKS"], s["A915-XA9Q-07"],
              s["XA9Q-07"]]
    c.new_req("RFQ3-GAS", "RFQ3-GAS-N03", "RFP-compliant propellant policy: system Xe propulsion capability",
              "The official RFP is the sole governing basis for propellant capability: the system supports both ambient "
              "atmospheric propellant (180-230 km) and Xenon propulsion capability, with separate ambient-air and Xe "
              "propellant tanks / paths. The Xe storage and flow-control hardware quoted here (Xe tank GAS-L08, PMU "
              "GAS-L09, FCU GAS-L10, series isolation valves GAS-L11, anode-path MFC GAS-L04) is the RFP-required "
              "system Xe capability and is in scope for BOTH configurations, including hall_icp_neutralizer; it is not "
              "a C1 contingency. C1 is an internal architecture element: C1 Xe hardware (GAS-L05, GAS-L06, GAS-L15) is "
              "quoted only for a selected C1 that requires Xe and is then booked inside the system Xe architecture "
              "(AL-08 / Xe accounting); no C1 Xe is invented or excluded in advance; the presence or absence of C1 never "
              "removes the system Xe capability (rule function xe_capability_scope). The ICP gas-mode baseline of A9.1 "
              "(G-REUSE primary, m_Xe,ICP = 0; G-XE a declared ICP-feed variant) is unchanged.",
              {"system_xe_lines": list(SYSTEM_XE_LINES), "c1_xe_lines_conditional": list(C1_XE_LINES),
               "applies_to": list(CONFIGS), "separate_tanks": "ambient air and Xenon (RFP; ambient-air storage is not "
                                                              "in this RFQ revision, NIR-07)",
               "icp_gas_mode": "unchanged (A9.1: G-REUSE primary)"}, "-", xe_src, "owner-stated", "OWNER_GIVEN",
              "NOW", "LATER", why="A9.14 XA9Q-07 as amended by A9.15")
    c.modify_req("RFQ-07-R09", xe_src + [s["A915-OQ-A907-07"]], "A9.15: Xe hardware is the RFP-required system capability, not C1 ground-only",
                 title="C1 not co-installed as a flight backup; Xe hardware = RFP system Xe capability",
                 requirement="The primary A9 flight architecture does not carry C1 and the ICP together (flight C1 "
                             "integration is deferred until C1 is selected - not because Xe is contingency-only, A9.15 "
                             "OQ-A907-07). The Xe storage / flow hardware quoted here provides the RFP-required system "
                             "Xe propulsion capability for every configuration including hall_icp_neutralizer "
                             "(RFQ3-GAS-N03); C1 Xe is added only for a selected C1 that requires it, inside the system "
                             "Xe architecture.",
                 value="no combined C1 + ICP flight installation; system Xe capability in both configurations")
    c.modify_req("RFQ-07-R06", [s["A915-CAP"], s["A915-C1"], s["A915-MPQ-01"]],
                 "A9.15: PMU/FCU range covers the system Xe propulsion flows; C1 flows only if a selected C1 needs Xe",
                 requirement="Controllable flow covering the RFP-required system Xe propulsion operating flows and the "
                             "bounded Xe reference flows; the C1 steady (0.05-0.2 mg/s class) and provisional start "
                             "(0.6-0.8 mg/s, not frozen) flows only if a selected C1 requires Xe, booked inside the "
                             "system Xe architecture; all Xe booked (purge, preheat, ignition, keeper, transition, "
                             "fallback where applicable).",
                 value="TBD - requires the registered Xe propulsion / reference operating point(s) and, only for a "
                       "selected C1 requiring Xe, the C1 operating point (LOCK-1)")
    for lid in SYSTEM_XE_LINES:
        if lid == "GAS-L04":
            c.modify_line(lid, xe_src[:2], "A9.15 system Xe capability", add_reqs=["RFQ3-GAS-N03"])
            continue
        c.modify_line(lid, [s["A915-CAP"], s["A915-XA9Q-07"]], "A9.15 system Xe capability (both configurations)",
                      add_reqs=["RFQ3-GAS-N03"])
    c.modify_line("GAS-L08", [s["OQ-RFQ-09"], s["XA9Q-06"], s["A915-TANKS"]], "A9.14 OQ-RFQ-09 / XA9Q-06; A9.15",
                  add_reqs=["RFQ3-GAS-N02"],
                  item="Xe tank, separate from the ambient-air storage (RFP-required system Xe propulsion capability; "
                       "one quote line per 2/5/10 kg loaded-Xe case; MEOP and design/proof factors proposed by the "
                       "supplier at 323 K)",
                  qa={"acceptance": ["proof / burst and leak test data at the supplier-proposed MEOP and factors; "
                                     "the MEOP basis is selected only after comparing compliant certified quotations "
                                     "(A9.14 OQ-RFQ-09, XA9Q-06)"],
                      "documentation": ["per 323 K design case: internal volume, proposed MEOP, design / proof factors, "
                                        "qualification basis and applicable pressure-vessel practice"]})
    c.modify_line("GAS-L09", [s["XA9Q-06"]], "A9.14 XA9Q-06: regulator solutions against the 323 K cases",
                  add_reqs=["RFQ3-GAS-N02"])
    for lid in C1_XE_LINES:
        c.modify_line(lid, [s["A915-C1"], s["A915-MPQ-01"]],
                      "A9.15: C1 Xe only for a selected C1 that requires Xe, booked inside the system Xe architecture",
                      add_reqs=["RFQ3-GAS-N03"], c1_xe_condition="quoted for a selected C1 that requires Xe; booked "
                                                                 "inside the system Xe architecture (AL-08)")

    _p, r = c.req("RFQ-07-R10")
    v = copy.deepcopy(r["value"])
    if "re-allocation is owner question MQ-05" not in v.get("note", ""):
        raise ValueError("RFQ-07-R10: unexpected v2 value")
    v["note"] = ("A9.14 MQ-05 (OWNER_DECIDED): AL-08 includes the complete Xe storage / flow hardware (tank, regulator, "
                 "valves, plumbing, mounting, thermal); the 5.044 kg incomplete CBE floor implies a 6.0528 kg MEV "
                 "planning floor; quotations / design replace this value; supplier states mass per case")
    v["AL-08_MEV_planning_floor_kg"] = 6.0528
    c.modify_req("RFQ-07-R10", [s["MQ-05"]], "A9.14 MQ-05 AL-08 scope and MEV planning floor", value=v)

    # ---------------------------------------------------------------- A9.14 XA9Q-05 + A9.15: ICP Xe getter
    g_src = [s["XA9Q-05"], s["A915-XA9Q-05"], s["MPQ-01"]]
    c.new_req("RFQ3-GAS", "RFQ3-GAS-N04", "ICP Xe-path getter / filter: engineering / vendor requirement",
              "No getter / filter is included by default on the ICP Xe path (the declared G-XE ICP-feed variant). "
              "Whether one is needed is an engineering / vendor requirement determined by the selected ICP / material / "
              "process or the Xe purity specification - not a policy choice (rule function icp_xe_getter_requirement). "
              "C1 getter / filter requirements stay separate and C1-specific (AL-C1, only for a selected C1).",
              {"default": "none", "decided_by": "engineering / vendor specification evidence",
               "c1_getter": "separate, C1-specific (AL-C1)"}, "-", g_src, "owner-stated", "OWNER_GIVEN", "NOW", "LATER",
              applies_to=["hall_icp_neutralizer"], why="A9.14 XA9Q-05 as amended by A9.15")
    c.modify_req("RFQ-07-R08", g_src, "A9.15 / XA9Q-05: C1-specific getter, separate from the ICP Xe path",
                 title="filter/getter (C1-specific branch only)",
                 requirement="C1-specific filter/getter (only for a selected C1 that requires it; mass on AL-C1): "
                             "include it with an explicit <= 17 W-class load only after vendor/spec verification; account "
                             "mass and pressure drop. An ICP Xe-path getter is a separate engineering / vendor "
                             "requirement (RFQ3-GAS-N04).")
    c.modify_line("GAS-O03", g_src, "A9.15 / XA9Q-05", add_reqs=["RFQ3-GAS-N04"],
                  item="OPTION: filter/getter (C1-specific branch, only for a selected C1 that requires it)")
    c.modify_line("GAS-O02", [s["XA9Q-05"], s["A915-XA9Q-05"]], "A9.15 / XA9Q-05: ICP Xe-path getter is engineering",
                  add_reqs=["RFQ3-GAS-N04"])

    # ---------------------------------------------------------------- A9.8 P1Q-09: dedicated target required
    c.modify_req("RFQ2-MECH-N05", [s["P1Q-09"], s["P1Q-09b"]], "A9.8 P1Q-09: dedicated isolated target required",
                 title="dedicated isolated electron-collecting target (ICP45_CAPACITY and P1-S4 records)",
                 requirement="A dedicated, isolated, instrumented electron-collecting target for both ICP45_CAPACITY and "
                             "the comparable P1-S4 engineering-surface records: planar / annular, centred on the ICP "
                             "axis, perpendicular to it, immediately downstream of the ICP outlet on a mechanically "
                             "registered / adjustable axial datum, with support and feedthrough lead, isolated to the "
                             "CIF-G07 class. Diameter, axial distance and support dimensions come from the actual ICP "
                             "module drawing and are registered at P1-G0 (no dimension is invented here). 316L is "
                             "acceptable for the Ar engineering article only; the flight collector material is not "
                             "frozen. The grounded chamber wall is never used as the electron collector.",
                 value={"geometry": "TBD - from the ICP module drawing, registered at P1-G0",
                        "isolation": "CIF-G07 class (A9.4 P1Q-14)",
                        "material": "316L acceptable for the Ar engineering article only (flight material not frozen)",
                        "chamber_wall_as_collector": "never"},
                 freeze_point=TBD_P1G0)
    c.new_line("RFQ3-MECH", "ME-L09",
               "dedicated isolated instrumented electron-collecting target (planar / annular, on the ICP axis, "
               "immediately downstream, registered adjustable axial datum, support + feedthrough lead) (P1-HW-36)",
               "1 (geometry from the ICP module drawing, registered at P1-G0) + 1 spare isolator set per RFQ3-MECH-N01",
               "A9.8 P1Q-09; P1-HW-36", "P1_NEEDED", ["RFQ2-MECH-N05", "RFQ3-MECH-N01"], [s["P1Q-09"], s["P1Q-09b"]],
               "A9.8 P1Q-09: the dedicated target is required (chamber wall never the collector)", covers=["collector"],
               qa={"acceptance": ["dimensions per the registered P1-G0 drawing; isolation verified to the CIF-G07 class "
                                  "(DWV per RFQ3-HALLEL-N02); axial datum repeatability recorded"],
                   "calibration_traceability": ["n/a - no calibrated measurand (the collector current channel is "
                                                "HE-L18)"],
                   "documentation": ["drawing id / revision / hash; material certificate (316L for Ar engineering "
                                     "only); isolation test record"]})
    c.supersede_line("ME-O01", "ME-L09", [s["P1Q-09"]],
                     "A9.8 P1Q-09 makes the dedicated isolated target mandatory; no longer an option line")

    # ---------------------------------------------------------------- A9.8 P3Q-01: Langmuir-probe cross-check
    c.new_req("RFQ3-THRUST", "RFQ3-THRUST-N03", "Langmuir-probe diagnostic near the collector (cross-check)",
              "A Langmuir-probe diagnostic near the collector for the Ar P1 development campaign (electron temperature "
              "and plasma potential; independent sheath-model cross-check). Collector calorimetry stays the primary "
              "Q_collector evidence. Probe measurements are taken preferably in matched diagnostic runs and never "
              "contaminate an ICP45 capacity record unless probe perturbation has first been shown negligible. Probe "
              "geometry, position and bias sweep range: TBD - registered at P1-G0 from the ICP module drawing.",
              {"role": "independent cross-check (calorimetry primary)", "geometry_position_bias": "TBD - P1-G0",
               "icp45_records": "excluded unless perturbation shown negligible"}, "-", [s["P3Q-01"], s["P3Q-01b"]],
              "owner-stated", "TBD", "P1-G0", "P1_NEEDED", applies_to=["hall_icp_neutralizer"], why="A9.8 P3Q-01")
    c.new_line("RFQ3-THRUST", "TH-L10",
               "Langmuir probe + sweep electronics near the collector (Ar P1 development cross-check; P1-M-30)",
               "1 (geometry / position TBD - registered at P1-G0)", "A9.8 P3Q-01; P1-M-30", "P1_NEEDED",
               ["RFQ3-THRUST-N03"], [s["P3Q-01"], s["P3Q-01b"]], "A9.8 P3Q-01: probe cross-check selected",
               qa={"acceptance": ["probe I-V sweep demonstrated on the common time base; perturbation test plan before "
                                  "any use in ICP45 records"],
                   "calibration_traceability": ["sweep voltage and probe current channels calibrated (traceable)"],
                   "documentation": ["probe geometry, materials, sweep range, analysis method for T_e and plasma "
                                     "potential"]})


def apply_stale_text_fixes(c: Ctx, s: dict) -> None:
    """Text in v2 that names a now-decided owner question as TBD_OWNER is rewritten to the decision (fail closed if the
    v2 text is not found, so a silent no-op is impossible)."""
    tbd_note = ("dispatch-first because A9.3 starts P2 instrument preparation immediately in parallel with P1; package "
                "placement TBD_OWNER (P2Q-02)")
    for rid in ["RFQ2-RF-N07", "RFQ2-RF-N08", "RFQ2-RF-N09", "RFQ2-RF-N10", "RFQ2-RF-N11", "RFQ2-RF-N12",
                "RFQ2-RF-N13", "RFQ2-RF-N14", "RFQ2-RF-N15", "RFQ2-RF-N16"]:
        _p, r = c.req(rid)
        if r["note"] != tbd_note:
            raise ValueError(f"{rid}: unexpected v2 note")
        c.modify_req(rid, [s["P2Q-02"]], "A9.8 P2Q-02 placement decided",
                     note="dispatch-first because A9.3 starts P2 instrument preparation immediately in parallel with "
                          "P1; package placement OWNER_DECIDED (A9.8 P2Q-02): " + _p["id"])
    c.modify_line("GAS-L01", [s["OQ-RFQV2-01"]], "A9.8 OQ-RFQV2-01",
                  qs_replace={"maker's Ar-specific certificate; accredited certificate TBD_OWNER (OQ-RFQV2-01)":
                              "maker's Ar-specific certificate + in-house rate-of-rise / transfer verification "
                              "(mandatory); ISO/IEC 17025 / NABL desirable, not mandatory, for P1 Ar (A9.8 OQ-RFQV2-01)"})
    c.modify_line("RF-L12", [s["P2Q-07"]], "A9.11 P2Q-07",
                  qs_replace={"13.56 MHz V, I and phase calibration; accredited scope or in-house VNA-traceable "
                              "procedure TBD_OWNER (P2Q-07)":
                              "13.56 MHz V, I and phase calibration; accredited scope where available, otherwise the "
                              "in-house VNA-traceable procedure of RFQ3-RFMET-N02 (A9.11 P2Q-07)"})
    _p, r = c.req("RFQ2-THRUST-N04")
    v = copy.deepcopy(r["value"])
    if v.get("Ar_MFC_certificate") != "TBD_OWNER (OQ-RFQV2-01)":
        raise ValueError("RFQ2-THRUST-N04: unexpected v2 value")
    v["Ar_MFC_certificate"] = ("maker's Ar-specific certificate + in-house rate-of-rise / transfer verification; "
                               "ISO/IEC 17025 / NABL desirable, not mandatory (A9.8 OQ-RFQV2-01; RFQ3-GAS-N01)")
    old = ("Whether the Ar MFC needs an accredited certificate or the maker's Ar certificate plus the rate-of-rise/"
           "transfer verification is TBD_OWNER (OQ-RFQV2-01).")
    if old not in r["requirement"]:
        raise ValueError("RFQ2-THRUST-N04: unexpected v2 text")
    c.modify_req("RFQ2-THRUST-N04", [s["OQ-RFQV2-01"]], "A9.8 OQ-RFQV2-01", value=v,
                 requirement=r["requirement"].replace(old, "The P1 Ar MFC is accepted on the maker's Ar-specific "
                                                           "certificate plus the in-house rate-of-rise / transfer "
                                                           "verification; an accredited certificate is desirable, not "
                                                           "mandatory (A9.8 OQ-RFQV2-01; RFQ3-GAS-N01)."))
    _p, r = c.req("RFQ2-HALLEL-N07")
    v = copy.deepcopy(r["value"])
    if v["voltage_class"].get("margin") != "TBD_OWNER (row 81; OQ-RFQV2-06)":
        raise ValueError("RFQ2-HALLEL-N07: unexpected v2 value")
    v["voltage_class"] = {"V_operating_class_V": 350.0, "V_design_withstand_min_V": 525.0,
                          "initial_DWV_V_DC": DWV_V_DC, "initial_DWV_duration_s": DWV_DURATION_S,
                          "basis": "A9.8 OQ-RFQV2-06 (RFQ3-HALLEL-N01)"}
    old = "the transient/qualification margin TBD_OWNER (OQ-RFQV2-06)"
    if old not in r["requirement"]:
        raise ValueError("RFQ2-HALLEL-N07: unexpected v2 text")
    c.modify_req("RFQ2-HALLEL-N07", [s["OQ-RFQV2-06"]], "A9.8 OQ-RFQV2-06 closes the margin for this DC class",
                 value=v, requirement=r["requirement"].replace(old, ">= 525 V design withstand and 1.05 kV DC / 60 s "
                                                                    "initial DWV (A9.8 OQ-RFQV2-06; RFQ3-HALLEL-N01)"),
                 note="closes OQ-RFQV2-07 for the V_anode channel (mechanical propagation of A9.4 P1Q-13, A9.6 sec. 6); "
                      "the voltage margin is closed by A9.8 OQ-RFQV2-06")


# ============================================================== A9.19 / A9.20: flight architecture, Xe role, C1 role
GROUND_ONLY = "GROUND_ONLY_LAB_EQUIPMENT"
C1_GROUND_LINES = ["HE-L10", "HE-L11", "HE-L12"]
C1_GROUND_ROLE = ("GROUND_ONLY_LAB_EQUIPMENT (A9.20): heated Xe-fed LaB6 C1 laboratory reference for (i) the dedicated "
                  "H-1 reference characterization that registers I_d,max,H1,Ar independently of the ICP (A9.10 S3.5 "
                  "P1Q-07) and (ii) the bench control in the C1-vs-ICP comparison; never flight hardware, never in the "
                  "flight mass / power / Xe budgets (A9.19 / A9.20)")
FLIGHT_ARCHITECTURE_A919 = ("one Hall accelerator + one RF/ICP electron-source/neutralizer (cathodeless / electrodeless) "
                            "serving both atmospheric gases and Xe; two propellant supply modes with separate tanks / "
                            "paths: ambient atmospheric propellant (primary) and Xe (contingency / emergency supply "
                            "mode; capability retained as the RFP requires); no conventional hollow cathode (A9.19)")
CONFIGURATION_ROLES = {
    "hall_icp_neutralizer": "FLIGHT ARCHITECTURE (A9.19): " + FLIGHT_ARCHITECTURE_A919,
    "hall_c1_reference": "GROUND_ONLY_LABORATORY_REFERENCE (A9.20): not a candidate flight configuration (A9.19); kept "
                         "only as the labelled ground / laboratory reference for the H-1 reference characterization "
                         "(A9.10 S3.5) and the C1-vs-ICP bench comparison",
}


FLIGHT_CONFIGS = ("hall_icp_neutralizer",)   # A9.19 / A9.20: the only flight configuration


def c1_equipment_class(line_id: str) -> str:
    """A9.19 / A9.20: every C1 line (cathode, heater, keeper, C1 Xe branch, C1 getter option) is ground-only laboratory
    equipment; no C1 line is flight hardware. Unknown ids raise (fail closed)."""
    if line_id in C1_GROUND_LINES or line_id in C1_XE_LINES or line_id == "GAS-O03":
        return GROUND_ONLY
    raise KeyError(f"{line_id} is not a C1 line")


def _amend_new_req(c: Ctx, rid: str, srcs: list, why: str, **fields) -> dict:
    """Amend a requirement that is NEW in v3 (keeps change_v3 type NEW; records the pre-A9.19 text)."""
    _p, r = c.req(rid)
    if r["change_v3"]["type"] != "NEW":
        raise ValueError(f"{rid}: not a v3-new requirement")
    before = r.setdefault("before_a9_19", {})
    for k, v in fields.items():
        if k not in before:
            before[k] = copy.deepcopy(r.get(k))
        r[k] = v
    r["sources"] = r["sources"] + [x for x in srcs if x not in r["sources"]]
    ch = r["change_v3"]
    ch["why"] = ch["why"] + "; " + why
    ch["decisions"] += [d for d in _decisions_of(srcs) if d not in ch["decisions"]]
    c._note(srcs, rid)
    return r


def apply_a9_19_20(c: Ctx, s: dict) -> None:
    """A9.19 (flight architecture; Xe = contingency / emergency supply mode; no flight C1) and A9.20 (C1 = ground-only
    laboratory reference). Quotation / specification only; no number is added or changed."""
    arch = [s["A919-ARCH"], s["A919-CATHODELESS"]]
    xe = [s["A919-XE"]]
    ground = [s["A920-GROUND"], s["A920-ANS"], s["A920-ROLE"], s["P1Q-07-S35"]]
    # ---- C1 cathode / heater / keeper: ground-only laboratory equipment
    items = {"HE-L10": "heated Xe-fed LaB6 hollow cathode C1 - GROUND-ONLY laboratory reference (not flight hardware; "
                       "A9.19 / A9.20)",
             "HE-L11": "C1 heater supply - GROUND-ONLY laboratory equipment (A9.20)",
             "HE-L12": "C1 pulsed keeper supply (300-600 V class) - GROUND-ONLY laboratory equipment (A9.20)"}
    for lid in C1_GROUND_LINES:
        _p, li = c.line(lid)
        gate = dict(li["dispatch_gate"])
        gate["role"] = C1_GROUND_ROLE
        gate["flight"] = "NONE: the flight architecture has no conventional hollow cathode (A9.19)"
        c.modify_line(lid, arch + ground, "A9.19 / A9.20: C1 is GROUND_ONLY_LAB_EQUIPMENT (H-1 reference "
                                          "characterization, A9.10 S3.5; C1-vs-ICP bench control); never flight",
                      item=items[lid], dispatch_gate=gate, equipment_class=c1_equipment_class(lid))
    # ---- C1 Xe branch (GAS-L05 / L06 / L15) and C1 getter option
    for lid in C1_XE_LINES:
        c.modify_line(lid, ground + [s["A919-C1MASS"]],
                      "A9.19 / A9.20: C1 Xe branch = ground-only laboratory equipment; never in the flight Xe "
                      "accounting",
                      equipment_class=c1_equipment_class(lid),
                      c1_xe_condition="GROUND_ONLY_LAB_EQUIPMENT: Xe branch of the ground-only C1 laboratory reference "
                                      "(H-1 reference characterization, A9.10 S3.5; C1-vs-ICP bench control); quoted "
                                      "for the selected C1 that requires Xe; its Xe is laboratory test-campaign Xe, "
                                      "never flight Xe accounting (A9.19 / A9.20)")
    c.modify_line("GAS-O03", ground, "A9.20: C1 getter option = ground-only C1 laboratory branch",
                  equipment_class=c1_equipment_class("GAS-O03"),
                  item="OPTION: filter/getter (ground-only C1 laboratory Xe branch, only for a selected C1 that "
                       "requires it; not flight hardware)")
    # ---- C1 requirements: remove flight-C1 wording
    _p, r19 = c.req("RFQ2-HALLEL-R19")
    old = "as the conventional reference/control/fallback (not the primary flight neutralizer if the ICP succeeds)"
    if old not in r19["requirement"]:
        raise ValueError("RFQ2-HALLEL-R19: unexpected text")
    c.modify_req("RFQ2-HALLEL-R19", arch + ground, "A9.19 / A9.20: C1 ground-only laboratory reference, never flight",
                 requirement=r19["requirement"].replace(
                     old, "as the GROUND-ONLY laboratory reference (A9.20): H-1 reference characterization registering "
                          "I_d,max,H1,Ar independently of the ICP (A9.10 S3.5 P1Q-07) and bench control in the "
                          "C1-vs-ICP comparison; never flight hardware - the flight architecture has no conventional "
                          "hollow cathode (A9.19)"))
    c.modify_req("RFQ-07-R09", arch + xe + ground,
                 "A9.19 / A9.20: no flight C1; C1 ground-only; Xe = contingency / emergency supply mode",
                 title="No C1 in the flight architecture; Xe hardware = RFP system Xe capability (contingency / "
                       "emergency supply mode)",
                 requirement="The flight architecture is " + FLIGHT_ARCHITECTURE_A919 + ". C1 is not flight hardware "
                             "in any form (no flight C1, no flight backup); it is GROUND_ONLY_LAB_EQUIPMENT for the H-1 "
                             "reference characterization (A9.10 S3.5) and the C1-vs-ICP bench control (A9.20). The Xe "
                             "storage / flow hardware quoted here provides the RFP-required system Xe capability of "
                             "hall_icp_neutralizer (RFQ3-GAS-N03); C1 Xe hardware (GAS-L05 / L06 / L15) is ground-only "
                             "laboratory equipment and never enters the flight Xe accounting.",
                 value="no C1 in the flight architecture; system Xe capability (contingency / emergency supply mode) "
                       "with its own tank / path")
    c.modify_req("RFQ-07-R06", ground, "A9.20: C1 flows belong to the ground-only C1 laboratory branch",
                 requirement="Controllable flow covering the RFP-required system Xe propulsion operating flows (Xe "
                             "contingency / emergency supply mode, A9.19) and the bounded Xe reference flows; the C1 "
                             "steady (0.05-0.2 mg/s class) and provisional start (0.6-0.8 mg/s, not frozen) flows only "
                             "for the ground-only C1 laboratory branch (A9.20) when the selected C1 requires Xe, booked "
                             "as laboratory test-campaign Xe, never flight Xe; all Xe booked (purge, preheat, ignition, "
                             "keeper, transition where applicable).",
                 value="TBD - requires the registered Xe propulsion / reference operating point(s) and, for the "
                       "ground-only C1 laboratory branch only, the C1 operating point")
    c.modify_req("RFQ-07-R08", ground, "A9.20: C1 getter on the ground-only C1 laboratory branch; no flight AL-C1",
                 title="filter/getter (ground-only C1 laboratory branch only)",
                 requirement="C1-specific filter/getter for the ground-only C1 laboratory Xe branch (A9.20), only for a "
                             "selected C1 that requires it: include it with an explicit <= 17 W-class load only after "
                             "vendor/spec verification; account mass and pressure drop as laboratory equipment (no "
                             "flight AL-C1: the flight architecture has no conventional hollow cathode, A9.19). An ICP "
                             "Xe-path getter is a separate engineering / vendor requirement (RFQ3-GAS-N04).")
    _p, r11 = c.req("RFQ-02-R11")
    c.modify_req("RFQ-02-R11", ground, "A9.20: C1 start controller = ground-only laboratory option",
                 requirement=r11["requirement"] + " The controller belongs to the ground-only C1 laboratory branch "
                                                  "(A9.20); it is never flight hardware and its Xe is never flight Xe.")
    # ---- v3-new requirements carrying A9.15 wording on the role of Xe / C1
    _p, n03 = c.req("RFQ3-GAS-N03")
    old = ("it is not a C1 contingency. C1 is an internal architecture element: C1 Xe hardware (GAS-L05, GAS-L06, "
           "GAS-L15) is quoted only for a selected C1 that requires Xe and is then booked inside the system Xe "
           "architecture (AL-08 / Xe accounting); no C1 Xe is invented or excluded in advance; the presence or absence "
           "of C1 never removes the system Xe capability (rule function xe_capability_scope).")
    if old not in n03["requirement"]:
        raise ValueError("RFQ3-GAS-N03: unexpected text")
    old_scope = "is in scope for BOTH configurations, including hall_icp_neutralizer;"
    if old_scope not in n03["requirement"]:
        raise ValueError("RFQ3-GAS-N03: unexpected scope text")
    v = copy.deepcopy(n03["value"])
    v["xe_role"] = "CONTINGENCY_AND_EMERGENCY supply mode (A9.19); capability retained (RFP-P17-05, RFP-P18-08)"
    # RV19-07: the RFP flight Xe capability applies to the flight configuration only (A9.19 / A9.20);
    # hall_c1_reference stays only under configuration_roles as GROUND_ONLY
    v["applies_to"] = list(FLIGHT_CONFIGS)
    v["c1_xe_lines_ground_only"] = v.pop("c1_xe_lines_conditional")
    v["configuration_roles"] = dict(CONFIGURATION_ROLES)
    _amend_new_req(c, "RFQ3-GAS-N03", arch + xe + ground, "A9.19: Xe = contingency / emergency supply mode; A9.20: C1 "
                                                          "Xe lines ground-only",
                   applies_to=list(FLIGHT_CONFIGS),
                   requirement=n03["requirement"].replace(
                       old_scope, "is in scope for the flight configuration hall_icp_neutralizer (A9.19; "
                                  "hall_c1_reference is a ground-only laboratory reference, A9.20);").replace(
                       old, "it is not a C1 contingency. A9.19: Xe is the contingency / emergency supply mode of the "
                            "single Hall + RF/ICP neutralizer flight architecture (not a parallel co-equal propellant); "
                            "its capability, separate tank / path and flow control stay required. C1 is GROUND-ONLY "
                            "laboratory equipment (A9.20): the C1 Xe hardware (GAS-L05, GAS-L06, GAS-L15) is quoted "
                            "only for the ground C1 laboratory branch and never enters the flight Xe accounting; the "
                            "presence or absence of C1 never removes the system Xe capability (rule function "
                            "xe_capability_scope)."),
                   value=v)
    _p, n04 = c.req("RFQ3-GAS-N04")
    old = "C1 getter / filter requirements stay separate and C1-specific (AL-C1, only for a selected C1)."
    if old not in n04["requirement"]:
        raise ValueError("RFQ3-GAS-N04: unexpected text")
    v = copy.deepcopy(n04["value"])
    v["c1_getter"] = "separate, C1-specific, ground-only C1 laboratory branch (A9.20; no flight AL-C1, A9.19)"
    _amend_new_req(c, "RFQ3-GAS-N04", ground, "A9.20: C1 getter ground-only",
                   requirement=n04["requirement"].replace(
                       old, "C1 getter / filter requirements stay separate and C1-specific on the ground-only C1 "
                            "laboratory branch (A9.20; no flight AL-C1, A9.19)."), value=v)
    # ---- new requirement: classification of the C1 lines
    c.new_req("RFQ3-HALLEL", "RFQ3-HALLEL-N03", "C1 = GROUND_ONLY_LAB_EQUIPMENT (no flight C1)",
              "Every C1 line in these packages - cathode HE-L10, heater supply HE-L11, keeper supply HE-L12, the C1 Xe "
              "branch GAS-L05 / GAS-L06 / GAS-L15 and the C1 getter option GAS-O03 - is quoted as ground-only "
              "laboratory equipment for (i) the dedicated H-1 reference characterization that registers "
              "I_d,max,H1,Ar independently of the ICP (A9.10 S3.5 P1Q-07) and (ii) the bench control in the "
              "C1-vs-ICP comparison. No C1 line is flight hardware, a flight fallback or a flight-qualification item; "
              "none enters the flight mass / power / Xe budgets. The flight architecture is " + FLIGHT_ARCHITECTURE_A919
              + ". Supplier space-qualification data for C1 are not requested by this revision.",
              {"equipment_class": GROUND_ONLY, "lines": C1_GROUND_LINES + C1_XE_LINES + ["GAS-O03"],
               "uses": ["H-1 reference characterization (A9.10 S3.5 P1Q-07)", "C1-vs-ICP bench control"],
               "flight": "NONE (A9.19)", "rule_function": "c1_equipment_class"},
              "-", arch + ground, "owner-stated", "OWNER_GIVEN", "NOW", "LATER",
              applies_to=["hall_c1_reference"], why="A9.19 / A9.20")
    for lid in C1_GROUND_LINES:
        c.modify_line(lid, ground, "A9.20 classification requirement", add_reqs=["RFQ3-HALLEL-N03"])


# ------------------------------------------------------------------------------- A9.21 AL08 split + RFQ dispatch
MASS_POWER_V3 = "docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json"   # read as data (budgets lane; never pinned)
AL08_PROVISIONAL = "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN"
AL08_FLOOR_KG = 6.0528       # A9.14 MQ-05 MEV planning floor (owner: "6.05 kg"); A9.21: provisional only, not frozen
AL08_CBE_FLOOR_KG = 5.044    # incomplete CBE floor (mass / power v3 AL-08 floor constituents)
AL08_ROW54_KG = 1.5          # owner row-54 allocation: HISTORY (superseded by A9.14 MQ-05, then A9.21)
AL08_SPLIT_ATTRIBUTES = ["mass", "envelope", "power", "lead time", "qualification / heritage status",
                         "compliance per requirement id (COMPLIANT / DEVIATION / NOT OFFERED)",
                         "datasheets / certificates"]
AL08_FLIGHT = ("FLIGHT_AL08 (RFP-required system Xe capability; AL-08 provisional, re-based only after these split "
               "quotations)")
AL08_C1 = ("GROUND_ONLY_LAB_EQUIPMENT - quoted as a separate offer section and booked separately as laboratory "
           "equipment; NEVER inside the flight AL-08 (A9.19 / A9.20 / A9.21)")
AL08_SPLIT = [
    {"category": "tank", "lines": ["GAS-L08"], "booking": AL08_FLIGHT,
     "note": "Xe tank (one quote line per loaded-Xe design case, RFQ2-GAS-R20)"},
    {"category": "regulator", "lines": ["GAS-L09"], "booking": AL08_FLIGHT, "note": "low-flow PMU (regulator)"},
    {"category": "valves", "lines": ["GAS-L11", "GAS-L10"], "booking": AL08_FLIGHT,
     "note": "Xe isolation valves (series pair, GAS-L11); the low-flow FCU (GAS-L10) is stated as its own sub-row "
             "inside this category (recorder mapping RF3-FLAG-06: the mass / power v3 AL-08 floor books the "
             "flow-control valves under valves; the owner may re-map)"},
    {"category": "plumbing", "lines": ["GAS-L18"], "booking": AL08_FLIGHT,
     "note": "new quote-request line; scope and quantity proposed by the supplier"},
    {"category": "mounting/thermal", "lines": ["GAS-L19"], "booking": AL08_FLIGHT,
     "note": "new quote-request line; scope and quantity proposed by the supplier"},
    {"category": "C1-specific branch", "lines": C1_XE_LINES + ["GAS-O03"], "booking": AL08_C1,
     "note": "C1 Xe branch of the ground-only C1 laboratory reference (A9.20); any C1-branch plumbing, fittings or "
             "mounting a supplier offers are stated here, never inside the flight plumbing or mounting/thermal lines"},
]
AL08_CATEGORIES = [x["category"] for x in AL08_SPLIT]
AL08_FLIGHT_CATEGORIES = [x["category"] for x in AL08_SPLIT if x["booking"] == AL08_FLIGHT]
AL08_NEW_LINES = ("GAS-L18", "GAS-L19")
AL08_OUTSIDE_SPLIT = {
    "GAS-L04": "Xe anode-path MFC(s) (laboratory flow metrology; indicative quotation now, A9.14 OQ-RFQ-03): not one of "
               "the A9.21 split categories; its mass is stated on its own line; whether it belongs to AL-08 is not "
               "decided here (RF3-FLAG-06)"}


def _positive_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def al08_quote_split_status(quotes) -> dict:
    """A9.21 AL08: decide whether a set of Xe storage / flow quotations carries the owner's split. `quotes` maps a
    split category to {"mass_kg": number, "lines": [...], "booking": ...}. Fail closed: a missing flight category or a
    missing mass blocks the re-base input; any C1 line quoted inside a flight category, or a C1 branch booked into the
    flight AL-08, is refused. The C1-specific branch must be stated separately (a mass, or "NONE" when no C1 Xe
    hardware is offered). Never computes or freezes an AL-08 value: the re-base itself is an owner decision."""
    q = quotes if isinstance(quotes, dict) else {}
    unknown = sorted(set(q) - set(AL08_CATEGORIES))
    if unknown:
        raise KeyError(f"unknown AL-08 split categories: {unknown}")
    c1_lines = set(C1_XE_LINES + ["GAS-O03"])
    for cat in AL08_FLIGHT_CATEGORIES:
        if c1_lines & set((q.get(cat) or {}).get("lines", [])):
            return {"state": "REFUSED_C1_HARDWARE_INSIDE_FLIGHT_AL08", "category": cat}
    c1 = q.get("C1-specific branch")
    if isinstance(c1, dict) and str(c1.get("booking", "")).startswith("FLIGHT_AL08"):
        return {"state": "REFUSED_C1_HARDWARE_INSIDE_FLIGHT_AL08", "category": "C1-specific branch"}
    missing = [cat for cat in AL08_FLIGHT_CATEGORIES if not _positive_number((q.get(cat) or {}).get("mass_kg"))]
    if not isinstance(c1, dict) or not (c1.get("mass_kg") == "NONE" or _positive_number(c1.get("mass_kg"))):
        missing.append("C1-specific branch")
    if missing:
        return {"state": "NOT_REBASEABLE_SPLIT_INCOMPLETE", "missing": missing}
    return {"state": "SPLIT_COMPLETE_REBASE_IS_OWNER_DECISION", "al08_status": AL08_PROVISIONAL,
            "note": "the split is complete; the formal AL-08 re-base is an owner decision (A9.21) - no value is "
                    "computed or frozen here"}


def _check_mass_power_al08() -> dict:
    """Read the budgets lane's AL-08 record as data and fail closed if it no longer carries what this RFQ states."""
    mp = _load(MASS_POWER_V3)
    rec = [x for x in mp["lines"]["hall_icp_neutralizer"] if x.get("line") == "AL-08"]
    if len(rec) != 1:
        raise ValueError("mass / power v3: AL-08 record missing or duplicated")
    r = rec[0]
    bad = [k for k, ok in (("owner_mev_planning_floor_kg", r.get("owner_mev_planning_floor_kg") == AL08_FLOOR_KG),
                           ("evidence_floor_cbe_kg", r.get("evidence_floor_cbe_kg") == AL08_CBE_FLOOR_KG),
                           ("row54_allocation_kg", r.get("row54_allocation_kg") == AL08_ROW54_KG),
                           ("a9_21_status", str(r.get("a9_21_status", "")).startswith(AL08_PROVISIONAL)),
                           ("c1_branch.in_AL08", (r.get("c1_branch") or {}).get("in_AL08") is False)) if not ok]
    if bad:
        raise ValueError("mass / power v3 AL-08 record changed (re-base the RFQ mass context): " + ", ".join(bad))
    return r


def s_a9_21() -> dict:
    return {
        "A921-AL08-FLOOR": OD("A9.21", "AL08", "Xe-hardware floor: wait for quotations before formally rebasing AL-08. "
                              "Keep 6.05 kg only as a provisional planning floor, not a frozen allocation."),
        "A921-AL08-C1": OD("A9.21", "AL08", "The reason is important: that analog-derived figure may contain about "
                           "0.285 kg of C1 cathode-branch hardware, while the RFP-required Xe propulsion system and any "
                           "C1-specific Xe hardware must be accounted separately."),
        "A921-AL08-SPLIT": OD("A9.21", "AL08", "Quotations should split tank, regulator, valves, plumbing, "
                              "mounting/thermal, and any C1-specific branch before the final re-base."),
        "A921-DISPATCH": OD("A9.21", "RFQ_DISPATCH", "For 15, I cannot dispatch supplier RFQs from this chat "
                            "environment. The quotation packages can be finalized here, but you/procurement must "
                            "actually send them."),
    }


def apply_a9_21(c: Ctx, s: dict) -> None:
    """A9.21 item 2 (AL08): the Xe storage / flow quotation is split into tank, regulator, valves, plumbing,
    mounting/thermal and any C1-specific branch (ground-only, separate, never in the flight AL-08); the 6.0528 kg AL-08
    MEV planning floor is provisional, re-based only after the split quotations. Quotation / specification only."""
    _check_mass_power_al08()
    al = [s["A921-AL08-FLOOR"], s["A921-AL08-C1"], s["A921-AL08-SPLIT"]]
    ground = [s["A920-GROUND"], s["A920-ANS"]]
    attrs = ", ".join(AL08_SPLIT_ATTRIBUTES)
    c.new_req("RFQ3-GAS", "RFQ3-GAS-N05", "Xe storage / flow quotation split (A9.21 AL08)",
              "Every supplier responding to the Xe storage / flow hardware lines states " + attrs + " SEPARATELY for "
              "each of these categories: tank (GAS-L08); regulator (low-flow PMU, GAS-L09); valves (isolation valves "
              "in series, GAS-L11, with the low-flow FCU GAS-L10 as its own sub-row); plumbing (GAS-L18); "
              "mounting/thermal (GAS-L19); and any C1-specific branch hardware (GAS-L05, GAS-L06, GAS-L15, GAS-O03). "
              "A category the supplier does not offer is stated NOT OFFERED, never folded into another category. The "
              "C1-specific branch is ground-only laboratory equipment (A9.20): it is quoted as a separate offer "
              "section and booked separately, never inside the flight AL-08 (A9.19 / A9.20 / A9.21). No combined "
              "mass for the Xe system replaces the per-category statement. The AL-08 MEV planning floor is "
              "provisional (A9.21) and is formally re-based only after these split quotations (rule function "
              "al08_quote_split_status); the quotations are re-base inputs, never a re-base by themselves.",
              {"categories": [{"category": x["category"], "lines": list(x["lines"]), "booking": x["booking"],
                               "note": x["note"]} for x in AL08_SPLIT],
               "attributes_per_category": list(AL08_SPLIT_ATTRIBUTES),
               "not_offered_rule": "state NOT OFFERED per category; never fold one category into another",
               "c1_branch": "separate offer section; GROUND_ONLY_LAB_EQUIPMENT; never inside the flight AL-08",
               "outside_split_categories": dict(AL08_OUTSIDE_SPLIT),
               "al08_status": AL08_PROVISIONAL + " (A9.21)",
               "rule_function": "al08_quote_split_status"},
              "-", al + ground, "owner-stated", "OWNER_GIVEN", "NOW", "LATER", applies_to=list(FLIGHT_CONFIGS),
              why="A9.21 AL08: quotation split before the AL-08 re-base")
    for cat in AL08_SPLIT:
        for lid in cat["lines"]:
            if lid in AL08_NEW_LINES:
                continue
            c.modify_line(lid, al if cat["booking"] == AL08_FLIGHT else al + ground,
                          "A9.21 AL08: quoted as split category '" + cat["category"] + "'",
                          add_reqs=["RFQ3-GAS-N05"], al08_split_category=cat["category"],
                          al08_booking=cat["booking"],
                          qa={"documentation": ["A9.21 AL08 split category '" + cat["category"] + "': " + attrs +
                                                " stated separately for this category (RFQ3-GAS-N05)"]})
    for lid, cat, item in (
            ("GAS-L18", "plumbing", "Xe storage / flow plumbing (tubing, fittings and joints between the quoted Xe "
                                    "tank, regulator, valves and the Hall anode-feed interface) - scope proposed by the "
                                    "supplier against its offered Xe architecture; RFP-required system Xe capability"),
            ("GAS-L19", "mounting/thermal", "Xe storage / flow mounting and thermal hardware for the quoted Xe items "
                                            "(tank mounting and the thermal hardware the offered architecture needs) - "
                                            "scope proposed by the supplier; RFP-required system Xe capability")):
        c.new_line("RFQ3-GAS", lid, item,
                   "TBD - supplier proposes (no quantity is specified by this RFQ; requires the Xe routing and tank "
                   "mounting design: mass / power v3 AL-08 floor constituent 'plumbing, mounting/thermal' is TBD)",
                   "A9.21 AL08 (split category '" + cat + "'); A9.14 MQ-05 (AL-08 scope includes plumbing, mounting "
                   "and thermal hardware)", "LATER", ["RFQ3-GAS-N05", "RFQ-07-R10", "RFQ3-GAS-N03"],
                   al + [s["MQ-05"]], "A9.21 AL08: quote-request line for a split category that had no line",
                   al08_split_category=cat, al08_booking=AL08_FLIGHT,
                   qa={"acceptance": ["offer itemized as its own A9.21 split category; no quantity is invented by "
                                      "this RFQ (supplier proposes scope and quantity against its offered architecture)"],
                       "calibration_traceability": ["no line-specific calibration (package-level list applies)"],
                       "documentation": ["A9.21 AL08 split category '" + cat + "': " + attrs + " stated separately "
                                         "for this category (RFQ3-GAS-N05)"]})
    # ---- AL-08 mass context: provisional planning floor; the older allocation kept only as labelled history
    _p, r = c.req("RFQ-07-R10")
    v = copy.deepcopy(r["value"])
    if v.get("AL-08_MEV_planning_floor_kg") != AL08_FLOOR_KG or v.get("AL-08_owner_allocation_kg") != AL08_ROW54_KG:
        raise ValueError("RFQ-07-R10: unexpected value before A9.21")
    new = {"AL-08_MEV_planning_floor_kg": AL08_FLOOR_KG,
           "AL-08_status": AL08_PROVISIONAL + " (A9.21 KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08): "
                           "provisional planning floor, NOT a frozen allocation; formally re-based only after the "
                           "split quotations (RFQ3-GAS-N05: tank, regulator, valves, plumbing, mounting/thermal, any "
                           "C1-specific branch)",
           "AL-08_evidence_floor_cbe_kg": AL08_CBE_FLOOR_KG,
           "evidence_floor_state": "INCOMPLETE (plumbing, mounting/thermal TBD in the floor constituents)",
           "c1_branch": "NOT in the flight AL-08 (A9.19 / A9.20); the owner notes the analog-derived figure may "
                        "contain about 0.285 kg of C1 cathode-branch hardware, which the split quotations separate "
                        "(A9.21)",
           "note": "A9.14 MQ-05 (OWNER_DECIDED): AL-08 includes the complete Xe storage / flow hardware (tank, "
                   "regulator, valves, plumbing, mounting, thermal); A9.21: the 6.0528 kg MEV planning floor is kept "
                   "only as a provisional planning floor; quotations / design replace it at the owner's re-base; "
                   "supplier states mass per split category and per case",
           "source": MASS_POWER_V3 + " lines[hall_icp_neutralizer][line=AL-08] (owner_mev_planning_floor_kg, "
                     "evidence_floor_cbe_kg, a9_21_status, c1_branch; checked at build time)",
           "history": {"label": "HISTORY - not current",
                       "AL-08_owner_allocation_kg_row54": AL08_ROW54_KG,
                       "state_before_a9_14_mq05": v.get("state"),
                       "superseded_by": "A9.14 MQ-05 (6.0528 kg MEV planning floor), made provisional by A9.21",
                       "source_before_a9_21": v.get("source")}}
    c.modify_req("RFQ-07-R10", al, "A9.21 AL08: 6.0528 kg = provisional planning floor (not frozen), re-based only "
                                   "after the split quotations; row-54 1.5 kg allocation kept only as labelled history",
                 value=new, title="mass context (AL-08 provisional planning floor, A9.21)")


# --------------------------------------------------------------------------------- dispatch readiness (A9.21 item 15)
READINESS = {
    "READY_FOR_OWNER_DISPATCH": "finalized in the repository for an owner / procurement request for quotation; the "
                                "repository never sends it and purchase NOT authorized",
    "NOT_READY_BLOCKING_TBD": "a NOW line has an open item that must be closed before the request can be sent",
    "NOT_READY_AWAITING_CONTROLLED_H1_DRAWINGS": "the build-to-print lines may be sent only with the P9e "
                                                 "configuration-controlled drawing set (A9.10 OQ-RFQV2-10)",
    "NOT_READY_CHECKLIST_INCOMPLETE": "a package checklist item is not met",
    "LATER_NOT_IN_CURRENT_DISPATCH": "owner dispatch tag LATER: sent with the later campaign set, not now",
}
OPEN_ITEM_CLASSES = {
    "SUPPLIER_TO_ANSWER": "the request asks the supplier to state / propose it; it does not block sending",
    "DEFERRED_TO_FREEZE_GATE": "an owner-deferred value frozen at its later gate from the procured / calibrated "
                               "hardware (A9.8 P1-IT-52: no numbers invented now); the supplier quotes capability "
                               "ranges; A9.4 / A9.6 allow P1_NEEDED lines to be sent for quotation; not blocking",
    "BLOCKING_SEND": "must be closed before the line can be sent (freeze point NOW and not a supplier answer, or an "
                     "unmet send precondition such as the controlled H-1 drawing set)",
}
_SUPPLIER_RE = re.compile(r"supplier (statement|data|states|proposes|propos|lists)|proposed by (each|the) supplier|"
                          r"supplier-proposed|range options|requires the offered", re.I)
_GATE_RE = re.compile(r"(?<![\w-])(P1-G0|LOCK-1|LOCK-2)(?![\w-])")
# quantity texts that name a document whose registration gate is recorded on another requirement (read from data)
QTY_GATE_REFS = {"requires module drawings": "RFQ2-MECH-N03"}   # 'TBD - requires the LOCK-1 module drawings'


def quantity_gate(qty: str, line_gate, reqs: dict):
    """Gate at which a TBD quantity is registered: a gate named in the quantity text, else the gate of the requirement
    that records the named document (QTY_GATE_REFS), else the line's quote-sheet gate; None when no gate is known."""
    m = _GATE_RE.findall(str(qty))
    if m:
        return max(m, key=FREEZE_POINTS.index)
    for k, rid in QTY_GATE_REFS.items():
        if k in str(qty):
            return reqs[rid]["freeze_point"]
    return line_gate


def classify_open_item(value, freeze_point: str, send_precondition_unmet: bool = False) -> str:
    """Fail-closed classification of one TBD / PENDING item of a line (recorder rule RF3-FLAG-07, for owner review)."""
    if freeze_point not in FREEZE_POINTS:
        raise ValueError(f"unknown freeze point {freeze_point!r}")
    if send_precondition_unmet:
        return "BLOCKING_SEND"
    if _SUPPLIER_RE.search(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)):
        return "SUPPLIER_TO_ANSWER"
    if freeze_point == "NOW":
        return "BLOCKING_SEND"
    return "DEFERRED_TO_FREEZE_GATE"


def line_readiness(pkg_id: str, li: dict, h1_drawing=None, reqs=None) -> dict:
    qs = li["quote_sheet"]
    now = li["dispatch"] == "P1_NEEDED" or qs["send_state"] == SEND_XE_INDICATIVE
    h1 = h1_fab_send_state(h1_drawing) if pkg_id == "RFQ3-H1FAB" else None
    h1_block = h1 is not None and h1["state"] != "READY_TO_SEND_FOR_QUOTATION_BUILD_TO_PRINT"
    gate = quantity_gate(li["qty"], qs["freeze_gate"], reqs or {}) or "NOW"   # unknown gate: fail closed
    items = []
    for sp in qs["spec"]:
        if sp["status"] in ("TBD", "PENDING"):
            pre = h1_block and sp["requirement"] == "RFQ3-H1FAB-N02"
            items.append({"item": sp["requirement"], "kind": "requirement", "freeze_point": sp["freeze_point"],
                          "class": classify_open_item(sp["value"], sp["freeze_point"], pre)})
    if "TBD" in str(li["qty"]):
        items.append({"item": "quantity", "kind": "quantity", "freeze_point": gate,
                      "class": classify_open_item(li["qty"], gate, h1_block)})
    blocking = [x["item"] for x in items if x["class"] == "BLOCKING_SEND"]
    if not now:
        state = "LATER_NOT_IN_CURRENT_DISPATCH"
        reason = "dispatch tag LATER (" + qs["send_state"] + ")"
        if li.get("dispatch_gate"):
            reason += "; gate: " + str(li["dispatch_gate"].get("gate", li["dispatch_gate"]))
        if li.get("al08_split_category"):
            reason += ("; A9.21: AL-08 split category '" + li["al08_split_category"] + "' - the AL-08 re-base waits "
                       "for these quotations; sending the line earlier is an owner call (RF3-FLAG-07)")
    elif h1_block:
        state, reason = "NOT_READY_AWAITING_CONTROLLED_H1_DRAWINGS", "h1_fab_send_state blockers: " + \
            ", ".join(h1["blockers"])
    elif blocking:
        state, reason = "NOT_READY_BLOCKING_TBD", "blocking: " + ", ".join(blocking)
    elif qs["send_state"] not in (SEND_P1, SEND_XE_INDICATIVE):
        state, reason = "NOT_READY_CHECKLIST_INCOMPLETE", "send state is not an owner-authorised send state"
    else:
        state, reason = "READY_FOR_OWNER_DISPATCH", "owner-authorised send state; no blocking open item"
    if state == "READY_FOR_OWNER_DISPATCH" and blocking:
        raise AssertionError(f"{li['id']}: readiness claimed with a blocking open item")
    return {"line": li["id"], "set": "NOW" if now else "LATER", "dispatch_tag": li["dispatch"],
            "option_line": li["option_line"], "send_state": qs["send_state"], "readiness": state, "reason": reason,
            "open_items": items, "blocking_open_items": blocking,
            "supplier_to_answer": [x["item"] for x in items if x["class"] == "SUPPLIER_TO_ANSWER"],
            "deferred_to_freeze_gate": [x["item"] for x in items if x["class"] == "DEFERRED_TO_FREEZE_GATE"]}


def package_readiness(now: list, checks: list) -> str:
    """Package NOW-subset readiness; never READY with a blocking open item on a NOW line (fail closed)."""
    if any(x["blocking_open_items"] for x in now):
        if any(x["readiness"] == "NOT_READY_AWAITING_CONTROLLED_H1_DRAWINGS" for x in now):
            return "NOT_READY_AWAITING_CONTROLLED_H1_DRAWINGS"
        return "NOT_READY_BLOCKING_TBD"
    if not now or not all(x["readiness"] == "READY_FOR_OWNER_DISPATCH" for x in now):
        return "NOT_READY_CHECKLIST_INCOMPLETE"
    if not all(c_["ok"] for c_ in checks):
        return "NOT_READY_CHECKLIST_INCOMPLETE"
    return "READY_FOR_OWNER_DISPATCH"


def compute_dispatch_readiness(doc: dict, s: dict) -> None:
    cif_txt = render_cif(doc["common_interface"])
    cif = {"id": doc["common_interface"]["id"], "revision": "v3", "file": doc["common_interface"]["package_file"],
           "rendered_sha256": hashlib.sha256(cif_txt.encode("utf-8")).hexdigest()}
    reqs = {r["id"]: r for p in doc["packages"] for r in p["requirements"]}
    h1_drawing = reqs["RFQ3-H1FAB-N02"]["value"]
    order = list(dict.fromkeys(x["package"] for x in doc["p1_dispatch_first"]))
    rows = []
    for p in doc["packages"]:
        lr = [line_readiness(p["id"], li, h1_drawing, reqs) for li in p["line_items"]]
        now = [x for x in lr if x["set"] == "NOW"]
        later = [x for x in lr if x["set"] == "LATER"]
        checks = [
            {"check": "banner states DO NOT PURCHASE - quotation / specification only",
             "ok": p["banner"][0].startswith("DO NOT PURCHASE")},
            {"check": "cites the common interface document " + cif["id"] + " (" + cif["file"] + ")",
             "ok": any(cif["id"] in b for b in p["banner"])},
            {"check": "has NOW lines (P1_NEEDED or indicative quotation now)", "ok": bool(now)},
            {"check": "every P1_NEEDED line has a complete quote sheet (spec, acceptance, calibration, documentation)",
             "ok": all(bool(li["quote_sheet"]["spec"] and li["quote_sheet"]["acceptance"]
                            and li["quote_sheet"]["calibration_traceability"] and li["quote_sheet"]["documentation"])
                       for li in p["line_items"] if li["dispatch"] == "P1_NEEDED")},
            {"check": "every NOW line is in an owner-authorised send state with no unmet send precondition",
             "ok": all(x["readiness"] == "READY_FOR_OWNER_DISPATCH" for x in now)},
            {"check": "no NOW line has a blocking open item", "ok": not any(x["blocking_open_items"] for x in now)},
            {"check": "no price, supplier name, ranking or purchase authorization (compliance record)",
             "ok": bool(doc["compliance"]["no_prices"] and doc["compliance"]["no_supplier_ranking"]
                        and doc["compliance"]["no_purchase_order"] and doc["compliance"]["no_supplier_names_invented"])},
        ]
        state = package_readiness(now, checks)
        rec = {"package": p["id"], "package_file": p["package_file"], "common_interface": dict(cif),
               "p1_first_order": order.index(p["id"]) + 1 if p["id"] in order else None,
               "now_subset": {"readiness": state, "lines": [x["line"] for x in now],
                              "supplier_to_answer": sorted({i for x in now for i in x["supplier_to_answer"]}),
                              "deferred_to_freeze_gate": sorted({i for x in now for i in x["deferred_to_freeze_gate"]}),
                              "blocking": sorted({i for x in now for i in x["blocking_open_items"]})},
               "later_subset": {"readiness": "LATER_NOT_IN_CURRENT_DISPATCH" if later else None,
                                "lines": [x["line"] for x in later],
                                "reason": ("owner dispatch tag LATER: sent with the later campaign set; per-line "
                                           "reasons in lines[]") if later else None},
               "checklist": checks, "lines": lr,
               "dispatched_by_repository": False, "purchase_authorized": False,
               "owner_action": "owner / procurement sends the request for quotation outside the repository and keeps "
                               "the dispatch record outside it (A9.21 item 15); no purchase order"}
        p["dispatch_readiness"] = rec
        rows.append(rec)
    rows.sort(key=lambda r: (r["p1_first_order"] is None, r["p1_first_order"] or 0))
    doc["dispatch_readiness_a9_21"] = {
        "decision": s["A921-DISPATCH"], "repository_dispatches": False, "purchase_authorized": False,
        "dispatch_record": "NONE_IN_REPOSITORY (the repository and Claude never contact a supplier; dispatch is an "
                           "owner / procurement act, A9.21 item 15)",
        "status_vocabulary": dict(READINESS), "open_item_classes": dict(OPEN_ITEM_CLASSES),
        "order_rule": "P1-first order of p1_dispatch_first (packages in first-appearance order)",
        "common_interface": cif,
        "rule": "a package's NOW subset is READY_FOR_OWNER_DISPATCH only if every NOW line is in an owner-authorised "
                "send state with no BLOCKING_SEND open item; readiness is never claimed with a blocking TBD; the "
                "classification of open items is a recorder rule for owner review (RF3-FLAG-07)",
        "packages": [{"package": r["package"], "p1_first_order": r["p1_first_order"],
                      "now_readiness": r["now_subset"]["readiness"], "now_lines": r["now_subset"]["lines"],
                      "later_readiness": r["later_subset"]["readiness"], "later_lines": r["later_subset"]["lines"],
                      "blocking": r["now_subset"]["blocking"],
                      "common_interface": r["common_interface"]["id"] + " " + r["common_interface"]["revision"]}
                     for r in rows]}


def patch_interface_demands(doc, s) -> None:
    fixes = {
        "IFD-03": {"to": "RFQ3-RFMET (and RFQ3-RF for RF-N06 / N08 / N09 / N13 / N16)",
                   "status": "DEFINED (copied; package placement OWNER_DECIDED: RFQ3-RFMET, A9.8 P2Q-02)",
                   "decisions": [s["P2Q-02"]]},
        "IFD-17": {"to": "RFQ3-MECH (ME-L03, ME-L04, ME-L09)",
                   "status": "DEFINED (RFQ3-MECH ME-L03, ME-L04, dedicated target ME-L09 (A9.8 P1Q-09); coupon "
                             "shortlist TBD_OWNER P4 IT-17; AO-source hardware NOT_IN_THIS_REVISION NIR-05)",
                   "decisions": [s["P1Q-09"]]},
        "IFD-18": {"to": "RFQ3-THRUST, RFQ3-VAC, RFQ3-HALLEL (TH-L07, TH-L08, VAC-L07, VAC-L03, HE-L04, HE-L19)",
                   "status": "DEFINED (TH-L07, TH-L08, VAC-L07, VAC-L03, HE-L04 and the required DWV tester HE-L19 "
                             "(A9.8 OQ-RFQV2-08); quotation only)",
                   "decisions": [s["OQ-RFQV2-08"]]},
        "IFD-19": {"to": "RFQ3-GAS (Xe lines GAS-L04, GAS-L08..L11; C1 Xe lines conditional)",
                   "status": "DEFINED FOR QUOTATION, LATER (Xe tank / PMU / FCU / valves = RFP-required system Xe "
                             "capability for both configurations (A9.15); MEOP supplier-proposed (A9.14 OQ-RFQ-09); "
                             "Xe = contingency / emergency supply mode (A9.19); C1 Xe lines = ground-only C1 "
                             "laboratory branch, never flight (A9.20); no flight C1 at all (A9.19, NIR-04); GAS-O02 "
                             "option only; RFQ only, no purchase)",
                   "decisions": [s["A915-RULE"], s["OQ-RFQ-09"], s["A919-XE"], s["A920-GROUND"]]},
    }
    seen = set()
    for x in doc["interface_demands"]:
        f = fixes.get(x["id"])
        if not f:
            continue
        seen.add(x["id"])
        x["before_v3"] = {"to": x["to"], "status": x["status"]}
        x["to"], x["status"] = f["to"], f["status"]
        x["change_v3"] = {"type": "CARRIED_MODIFIED", "decisions": _decisions_of(f["decisions"])}
    if seen != set(fixes):
        raise KeyError(f"interface demands not found: {sorted(set(fixes) - seen)}")
    for row in doc["m16_impact"]:
        row["how_touched"] = row["how_touched"].replace("placement P2Q-02", "RFQ3-RFMET per A9.8 P2Q-02")
    for e in doc["instrument_coverage"]["p1_hardware"]:
        if e["id"] == "P1-HW-32":
            e["note"] = ("C1 is GROUND_ONLY_LAB_EQUIPMENT (A9.20; no longer a flight control / fallback, A9.19) and "
                         "LATER; P1-S6 may run with C1 physically absent "
                         "(C1_NOT_INSTALLED); C1 readiness is scheduled against the H-1 reference characterization "
                         "gate (A9.10 OQ-RFQV2-09)")


# ------------------------------------------------------------------------------------------------- build pipeline
def _rebuild_quote_sheets(doc) -> None:
    by = {}
    for p in doc["packages"]:
        for r in p["requirements"]:
            by[r["id"]] = r
            if r["v1_id"]:
                by[r["v1_id"]] = r
    order = {f: i for i, f in enumerate(FREEZE_POINTS)}
    for p in doc["packages"]:
        for li in p["line_items"]:
            spec = []
            for rid in li["requirements"]:
                r = by[rid]   # KeyError = unknown requirement (fail closed)
                spec.append({"requirement": r["id"], "v1_id": r["v1_id"], "title": r["title"], "value": r["value"],
                             "units": r["units"], "freeze_point": r["freeze_point"], "status": r["status"]})
            gate = max((x["freeze_point"] for x in spec), key=lambda f: order[f]) if spec else None
            old = li.get("quote_sheet") or {"acceptance": ["package-level acceptance list (carried v1)"],
                                            "calibration_traceability": ["package-level calibration list (carried v1)"],
                                            "documentation": ["package-level documentation list (carried v1)"]}
            qs = {"spec": spec, "freeze_gate": gate}
            extra = li.pop("qa_v3", None) or {}
            repl = li.pop("qs_replace_v3", None) or {}
            used = {x for f in ("acceptance", "calibration_traceability", "documentation") for x in old[f]}
            if set(repl) - used:
                raise KeyError(f"{li['id']}: quote-sheet text to replace not found: {sorted(set(repl) - used)}")
            old = {f: [repl.get(x, x) for x in old[f]]
                   for f in ("acceptance", "calibration_traceability", "documentation")}
            for f in ("acceptance", "calibration_traceability", "documentation"):
                base = [x for x in old[f] if not x.startswith("package-level")] if extra.get(f) else list(old[f])
                qs[f] = base + [x for x in extra.get(f, []) if x not in base]
            if li["dispatch"] == "P1_NEEDED":
                if not spec or not all(qs[f] for f in ("acceptance", "calibration_traceability", "documentation")):
                    raise ValueError(f"P1_NEEDED line {li['id']} lacks a complete quote sheet")
            if p["id"] == "RFQ3-H1FAB":
                qs["send_state"] = SEND_H1FAB
            elif li.get("quotation_timing") == "INDICATIVE_QUOTE_NOW":
                qs["send_state"] = SEND_XE_INDICATIVE
            else:
                qs["send_state"] = SEND_P1 if li["dispatch"] == "P1_NEEDED" else SEND_LATER
            li["quote_sheet"] = qs


def _banner() -> list:
    return [
        "DO NOT PURCHASE - QUOTATION / SPECIFICATION ONLY. Purchase orders, advance payments and binding commitments "
        "are NOT authorized by this package (owner row 8; A9.1 A9-09 procurement restriction; A9.3, A9.4, A9.6 "
        "unchanged; A9.8 OQ-RFQV2-05 and A9.10 OQ-RFQV2-10: quotation / specification only).",
        "Prepared by the technical team (A9.3 OQ-RFQ-07). Commercial dispatch authority remains with P9E/Vyovrinda "
        "under Praveen's authorization. No automatic supplier contact: neither this repository nor Claude contacts any "
        "supplier; dispatch, if any, is an owner/procurement act.",
        "Compatibility: this is one of eight supplier-speciality packages (the six owner families of A9.3 OQ-RFQ-07 + "
        "the RF-metrology package of A9.8 P2Q-02 + the H-1 build-to-print package of A9.10 OQ-RFQV2-10) kept "
        "compatible by the common top-level interface document RFQ3-CIF (packages/RFQ3-00_common_interface.md). "
        "No architecture meaning is inferred from a package boundary (A9.8 OQ-RFQV2-04).",
        "No prices are recorded; no supplier is named, ranked or selected; catalogue data appear only as REFERENCE with "
        "the citation/URL and access record of the web track.",
        "A9 status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE: no configuration is a winner; no "
        "thrust, efficiency, discharge current, ICP electron current, impedance or plasma state is predicted. Never "
        "PASS: " + NEVER_PASS + ".",
        "RFP-compliant propellant policy (A9.15): the official RFP governs propellant capability - the system supports "
        "both ambient atmospheric propellant (180-230 km) and Xenon propulsion capability with separate tanks/paths; Xe "
        "is an RFP-required system capability, not a C1 contingency; C1 Xe only if a selected C1 requires it, booked "
        "inside the system Xe architecture. The A9.1 ICP gas-mode baseline (G-REUSE primary) is unchanged.",
        "Flight architecture (A9.19, amending A9.15 on the ROLE of Xe): one Hall accelerator + one RF/ICP "
        "electron-source/neutralizer (cathodeless / electrodeless) for both atmospheric gases and Xe; two propellant "
        "supply modes with separate tanks / paths - ambient atmospheric propellant (primary) and Xe (contingency / "
        "emergency supply mode; the RFP-required Xe capability is retained); no conventional hollow cathode. C1 "
        "(A9.20) is GROUND_ONLY_LAB_EQUIPMENT for the H-1 reference characterization (A9.10 S3.5) and the C1-vs-ICP "
        "bench control: no C1 line in these packages is flight hardware or enters a flight mass / power / Xe budget.",
        "A9.4 / A9.6: the owner / procurement may SEND the lines tagged P1_NEEDED for quotation (requests for "
        "quotation, technical clarification, indicative lead time, commercial quotation, datasheets/certificates). The "
        "H-1 build-to-print package for the P1 article is sent only with the P9e configuration-controlled drawing set "
        "(drawing id, revision, content hash; A9.10 OQ-RFQV2-10); the LOCK-1 release (A9.14 F5-OQ-04) is the flight H-1 "
        "basis.",
    ]


OWNER_SCOPE_RF_NOTE = ("RF generation / matching only after A9.8 P2Q-02; the owner-listed RF measurement equipment is in "
                       "RFQ3-RFMET")


def build() -> dict:
    verify_pins()
    _scope_verbatim_check()
    v2 = _load(V2["V2_JSON"][0])
    if v2.get("schema") != "rfq_a9_v2":
        raise ValueError("unexpected v2 schema")
    doc = copy.deepcopy(v2)
    # ---- rename package ids outside historical records; tag every carried record
    v2_ids = [p["id"] for p in doc["packages"]]
    for p in doc["packages"]:
        for r in p["requirements"]:
            r["change_v3"] = {"type": "CARRIED_UNCHANGED", "why": None, "decisions": []}
        for li in p["line_items"]:
            li["change_v3"] = {"type": "CARRIED_UNCHANGED", "why": None, "decisions": []}
    doc["packages"] = _rename(doc["packages"])
    for p, v2id in zip(doc["packages"], v2_ids):
        p["v2_package"] = v2id
        p["id"] = PKG_RENAME[v2id]
        for r in p["requirements"]:
            r["package"] = p["id"]
    doc["common_interface"] = _rename(doc["common_interface"])
    doc["common_interface"]["id"] = "RFQ3-CIF"
    for pid, meta in NEW_PACKAGES.items():
        doc["packages"].append({"id": pid, "v2_package": None, "number": meta["number"], "slug": meta["slug"],
                                "owner_family": meta["owner_family"], "line_items": [], "requirements": [],
                                "v1_packages_folded_in": [], "acceptance": [], "calibration_traceability": [],
                                "documentation": [], "reference_data": [], "reference_data_use": "-",
                                "supplier_must_state": [], "cif_interfaces": []})
    doc["superseded_lines_v3"] = []
    c = Ctx(doc)
    src = S()
    src.update(s_a9_21())
    apply_decisions(c, src)
    apply_stale_text_fixes(c, src)
    apply_a9_19_20(c, src)
    apply_a9_21(c, src)
    doc["packages"].sort(key=lambda p: PKG_ORDER.index(p["id"]))
    _rebuild_quote_sheets(doc)
    _finish_packages(doc, src)
    _common_interface(doc, src)
    _top_level(doc, v2, c, src)
    return doc


def _finish_packages(doc, s) -> None:
    common_must = [x for x in doc["packages"][0]["supplier_must_state"] if x["carried_from"] is None]
    for p in doc["packages"]:
        p["banner"] = _banner()
        p["package_file"] = f"{PKG_DIR}/RFQ3-{p['number']}_{p['slug']}.md"
        if p["id"] == "RFQ3-RFMET":
            p["owner_minimum_scope_verbatim"] = list(RFMET_SCOPE)
            p["owner_minimum_scope_source"] = {"key": "A9.8", "id": "P2Q-02", "quote": s["P2Q-02"]["quote"]}
            p["v1_packages_folded_in"] = []
            p["acceptance"] = [{"text": "every instrument delivered with its calibration certificate / data and stated "
                                        "uncertainty at 13.56 MHz; V/I-probe route per RFQ3-RFMET-N02", "carried_from": None},
                               {"text": "incoming verification per the P2 calibration plan (VNA with kit, attenuators, "
                                        "V/I probe phase, antenna-simulator load impedance record)", "carried_from": None}]
            p["calibration_traceability"] = [{"text": "VNA and calibration-kit certificates traceable (ISO/IEC 17025 / "
                                                      "NABL where available); V/I probe accredited scope where "
                                                      "available, else in-house traceable (A9.11 P2Q-07)",
                                              "carried_from": None}]
            p["documentation"] = [{"text": "datasheets, calibration certificates / standard data, uncertainty budgets, "
                                           "connector family per CIF-C01", "carried_from": None}]
            p["supplier_must_state"] = copy.deepcopy(common_must) + [
                {"text": "independence: the offered measurement chain is not supplied as part of an RF generator / "
                         "matching offer (A9.8 P2Q-02)", "carried_from": None}]
            p["cif_interfaces"] = sorted({x for x in doc["packages"][0]["cif_interfaces"]})
        elif p["id"] == "RFQ3-H1FAB":
            p["owner_minimum_scope_verbatim"] = list(H1FAB_SCOPE)
            p["owner_minimum_scope_source"] = {"key": "A9.10", "id": "OQ-RFQV2-10",
                                               "quote": s["OQ-RFQV2-10"]["quote"]}
            p["retained_in_house_verbatim"] = list(H1FAB_IN_HOUSE)
            p["acceptance"] = [{"text": "in-house incoming inspection against the controlled drawing; acceptance testing "
                                        "of the assembled H-1 is in-house (A9.10 OQ-RFQV2-10)", "carried_from": None}]
            p["calibration_traceability"] = [{"text": "supplier inspection instruments under calibration; certificate "
                                                      "references on every inspection report", "carried_from": None}]
            p["documentation"] = [{"text": "material certificates, dimensional inspection reports, drawing id / "
                                           "revision / hash fabricated to, non-conformance reports", "carried_from": None}]
            p["supplier_must_state"] = copy.deepcopy(common_must) + [
                {"text": "build-to-print confirmation: no design change without an in-house drawing revision",
                 "carried_from": None}]
            p["cif_interfaces"] = []
        else:
            p["owner_minimum_scope_verbatim"] = p["owner_minimum_scope_verbatim"]
        lits = p["line_items"]
        cov = {oi: [li["id"] for li in lits if oi in li["covers_owner_items"]] for oi in p["owner_minimum_scope_verbatim"]}
        missing = [k for k, v in cov.items() if not v]
        if missing:
            raise ValueError(f"{p['id']}: owner minimum-scope items not covered: {missing}")
        p["owner_minimum_scope_coverage"] = cov
        p["p1_needed_line_items"] = [li["id"] for li in lits if li["dispatch"] == "P1_NEEDED"]
        p["later_line_items"] = [li["id"] for li in lits if li["dispatch"] == "LATER"]
        p["open_specification_items"] = [{"id": r["id"], "v1_id": r["v1_id"], "title": r["title"],
                                          "value": r["value"], "freeze_point": r["freeze_point"],
                                          "dispatch": r["dispatch"]}
                                         for r in p["requirements"] if r["status"] in ("TBD", "PENDING")]
        own = {r["id"] for r in p["requirements"]} | {r["v1_id"] for r in p["requirements"] if r["v1_id"]}
        p["cross_package_requirements"] = sorted({rid for li in lits for rid in li["requirements"] if rid not in own})
    rf = next(p for p in doc["packages"] if p["id"] == "RFQ3-RF")
    rf["scope_note_v3"] = OWNER_SCOPE_RF_NOTE


def _common_interface(doc, s) -> None:
    ci = doc["common_interface"]
    ci["title"] = "RFQ v3 common top-level interface document"
    ci["banner"] = _banner()
    ci["package_file"] = f"{PKG_DIR}/RFQ3-00_common_interface.md"
    for x in ci["items"]:
        if x["id"] == "CIF-G04":
            x["before_v3"] = {"value": x["value"], "status": x["status"], "freeze_point": x["freeze_point"]}
            x["value"] = {"V_operating_class_V": 350.0, "V_design_withstand_min_V": 525.0,
                          "initial_DWV_V_DC": DWV_V_DC, "initial_DWV_duration_s": DWV_DURATION_S,
                          "applies_to": "H-1 anode / discharge-supply isolation and feedthrough paths that can "
                                        "experience the corresponding potential difference",
                          "triggered_reverification": "700 V DC / 60 s (A9.14 P1Q-17)",
                          "not_covered": "RF antenna / matching-network insulation, Paschen-risk gas paths, combined "
                                         "RF + DC stress (separately qualified)"}
            x["status"] = "OWNER_GIVEN"
            x["freeze_point"] = "NOW"
            x["source"] = x["source"] + "; A9.8 OQ-RFQV2-06 (closes the row-81 margin for this DC class); A9.14 P1Q-17"
            x["change_v3"] = {"type": "CARRIED_MODIFIED", "decisions": _decisions_of([s["OQ-RFQV2-06"], s["P1Q-17"]])}
        elif x["id"] == "CIF-S01":
            x["before_v3"] = {"value": copy.deepcopy(x["value"])}
            x["value"] = dict(x["value"])
            x["value"]["Xe"] = ("RFP-required system Xe propulsion capability (separate Xe tank / path; both "
                                "configurations); reference / health check; C1 Xe only if a selected C1 requires it, "
                                "inside the system Xe architecture (A9.15); A9.19: Xe is the contingency / emergency "
                                "supply mode (capability retained); A9.20: C1 Xe = ground-only C1 laboratory branch, "
                                "never flight Xe")
            x["value"]["ambient air"] = "RFP-required ambient atmospheric propellant (180-230 km), separate tank / path"
            x["source"] = x["source"] + "; A9.15 governing_rule"
            x["change_v3"] = {"type": "CARRIED_MODIFIED", "decisions": _decisions_of([s["A915-RULE"]])}
        elif x["id"] == "CIF-S02":
            x["change_v3"] = {"type": "CARRIED_UNCHANGED", "decisions": [],
                              "note": "A9.15 does not change the A9.1 ICP gas-mode baseline"}
        else:
            x.setdefault("change_v3", {"type": "CARRIED_UNCHANGED", "decisions": []})
    ci["package_policy_v3"] = {
        "packages": PKG_ORDER, "rule": "six owner families (A9.3 OQ-RFQ-07) + RF-metrology (A9.8 P2Q-02) + H-1 "
                                       "build-to-print (A9.10 OQ-RFQV2-10); no architecture meaning in any boundary "
                                       "(A9.8 OQ-RFQV2-04)",
        "rfmet_interfaces": "RFQ3-RFMET uses the RF reference planes (CIF-P02, RP-VI / RP-ANT), connectors (CIF-C01) "
                            "and the common time base (CIF-T01) of this document"}


def _line_index(doc) -> dict:
    return {li["id"]: (p["id"], li) for p in doc["packages"] for li in p["line_items"]}


def _remap_lines(entries, idx, superseded) -> None:
    for e in entries:
        new = []
        for x in e.get("rfq_lines", e.get("lines", [])):
            lid = superseded.get(x["line"], x["line"])
            pk, li = idx[lid]
            new.append({"line": lid, "package": pk, "dispatch": li["dispatch"]})
        if "rfq_lines" in e:
            e["rfq_lines"] = new
        else:
            e["lines"] = new


def _top_level(doc, v2, c: Ctx, s) -> None:
    doc["schema"] = "rfq_a9_v3"
    doc["id"] = "RFQ_A9_V3"
    doc["title"] = ("A9 RFQ packages v3 - owner decisions A9.8 / A9.10 / A9.11 / A9.14 / A9.15 applied "
                    "(quotations only; no purchase orders)")
    doc["revision_of"] = {"id": "RFQ_A9_V2", "path": "docs/procurement/rfq_a9_v2/", "json": V2["V2_JSON"][0],
                          "json_sha256": V2["V2_JSON"][1],
                          "rule": "v2 (and v1) are immutable and never edited; v3 is a new revision under a new path"}
    doc["lane"] = "A9_16_RFQ_V3"
    doc["follow_on"] = "A9.16 step 1 (owner instruction 2026-10-01: apply the recorded decisions sequentially)"
    doc["trigger"] = "A9.16_DECISION_APPLICATION"
    doc["status"] = ("COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.16 owner-decision application; integration lane "
                     "re-pins and re-verifies cross-lane ids)")
    doc["base_commit"] = BASE_COMMIT
    doc["generated_by"] = THIS_SCRIPT
    doc["companion_document"] = OUT_MD
    doc["test"] = TEST
    doc["banner"] = _banner()
    doc["change_types_v3"] = CHANGE_TYPES_V3
    doc["decision_pins_v3"] = [{"key": k, "path": d[f], "sha256": d[f + "_sha256"], "immutable": True}
                               for k, d in DECISIONS.items() for f in ("json", "md")]
    doc["v2_pins"] = [{"key": k, "path": v[0], "sha256": v[1]} for k, v in V2.items()]
    doc["never_pinned_v3"] = NEVER_PINNED_V3
    doc["rfp_propellant_policy"] = {
        "decision": DECISIONS["A9.15"]["json"], "json_sha256": DECISIONS["A9.15"]["json_sha256"],
        "governing_rule": s["A915-RULE"]["quote"],
        "applied": ["RFQ3-GAS-N03 (system Xe capability, both configurations)", "RFQ2-GAS-R27 / R24 rewritten",
                    "GAS-L04 / L08..L11 tagged system Xe", "C1 Xe lines conditional (GAS-L05 / L06 / L15)",
                    "RFQ3-GAS-N04 (ICP Xe getter = engineering requirement)", "CIF-S01 Xe / ambient-air labels"],
        "unchanged": "A9.1 ICP gas-mode baseline: G-REUSE primary (m_Xe,ICP = 0), G-XE a declared ICP-feed variant",
        "rule_function": "xe_capability_scope",
        "a9_19_xe_role": {
            "decision": DECISIONS["A9.19"]["json"], "json_sha256": DECISIONS["A9.19"]["json_sha256"],
            "verbatim": DECISIONS["A9.19"]["md"], "md_sha256": DECISIONS["A9.19"]["md_sha256"],
            "owner_text": [s["A919-XE"]["quote"], s["A919-ARCH"]["quote"]],
            "role": "Xe = CONTINGENCY / EMERGENCY supply mode (not a parallel co-equal propellant); Xe capability, "
                    "separate tank / path and flow control stay required (RFP-P17-05, RFP-P18-08)",
            "flight_architecture": FLIGHT_ARCHITECTURE_A919,
            "rfq3_gas_n03_applies_to": list(FLIGHT_CONFIGS),
            "rfq3_gas_n03_scope_note": "the RFP flight Xe capability applies to the flight configuration only "
                                       "(A9.19 / A9.20); hall_c1_reference is listed only under configuration_roles "
                                       "as GROUND_ONLY (the A9.15 both-configuration scope is kept in before_a9_19)",
            "amends": "A9.15 on the ROLE of Xe only (capability unchanged)"},
        "a9_20_c1_role": {
            "decision": DECISIONS["A9.20"]["json"], "json_sha256": DECISIONS["A9.20"]["json_sha256"],
            "verbatim": DECISIONS["A9.20"]["md"], "md_sha256": DECISIONS["A9.20"]["md_sha256"],
            "role": C1_GROUND_ROLE, "lines": C1_GROUND_LINES + C1_XE_LINES + ["GAS-O03"],
            "requirement": "RFQ3-HALLEL-N03", "rule_function": "c1_equipment_class"}}
    sup = {x["id"]: x["superseded_by"] for x in doc["superseded_lines_v3"]}
    idx = _line_index(doc)
    # not in this revision
    nir = []
    for x in doc["not_in_this_revision"]:
        x = copy.deepcopy(x)
        if x["id"] == "NIR-04":
            x["before_a9_19"] = {"item": x["item"], "package_when_issued": x["package_when_issued"]}
            x["item"] = "flight C1 integration hardware - NONE: there is no flight C1 (A9.19)"
            x["package_when_issued"] = ("never (A9.19: the flight architecture has no conventional hollow cathode; "
                                        "A9.20: C1 is ground-only laboratory equipment)")
            x["why"] = ("A9.19 (amending A9.14 S8.33 MPQ-01 / S8.17 OQ-A907-07 and the A9 C1 CONTROL_FALLBACK): the "
                        "flight architecture is one Hall accelerator + one RF/ICP electron-source/neutralizer with no "
                        "conventional hollow cathode, so no flight C1 hardware is ever specified; A9.20: C1 is "
                        "GROUND_ONLY_LAB_EQUIPMENT quoted on HE-L10..L12 and the C1 Xe branch (RFQ3-HALLEL-N03)")
            x["source"] = ("A9.19 (" + DECISIONS["A9.19"]["json"] + " sha256 " + DECISIONS["A9.19"]["json_sha256"]
                           + "); A9.20 (" + DECISIONS["A9.20"]["json"] + " sha256 " + DECISIONS["A9.20"]["json_sha256"]
                           + "); history: A9.14 OQ-A907-07; A9.15 OQ-A907-07")
        if x["id"] == "NIR-06":
            x["state_v3"] = "RESOLVED_BY_A9_10_OQ_RFQV2_10 (RFQ3-H1FAB issued in this revision)"
            continue_list = doc.setdefault("resolved_not_in_previous_revision", [])
            continue_list.append(x)
            continue
        nir.append(x)
    nir.append({"id": "NIR-07", "item": "ambient-air propellant storage / atmospheric feed path (intake -> compressor -> "
                                        "atmospheric gas chamber -> valve) flight hardware",
                "package_when_issued": "separate upstream-architecture RFQ (not this revision)",
                "why": "A9.15: the RFP requires separate ambient-air and Xe tanks; the atmospheric path belongs to the "
                       "upstream architecture lanes (A9.13), not to these bench RFQ packages; no ambient-air storage "
                       "item is specified here", "source": "A9.15 governing_rule"})
    doc["not_in_this_revision"] = _rename(nir)
    # instrument coverage
    ic = doc["instrument_coverage"]
    ic["rule"] = ("v2 snapshot of the merged P1 / P2 id lists, remapped to v3 lines; the integration lane re-verifies "
                  "against the A9.16-updated P1 / P2 lanes (ids only, nothing filled)")
    for sec in ("p1_measurements", "p1_hardware", "p2_instruments"):
        _remap_lines(ic[sec], idx, sup)
        for e in ic[sec]:
            if e["id"] == "P1-M-30":
                e["rfq_lines"] = [{"line": "TH-L10", "package": "RFQ3-THRUST", "dispatch": "P1_NEEDED"}]
                e["disposition"] = "RFQ_LINE"
                e["note"] = "A9.8 P3Q-01 (probe cross-check selected)"
            if e["id"] in ("P1-HW-15", "P1-HW-22"):
                lines = ["H1-L01", "H1-L02", "H1-L03", "H1-L04", "H1-L05", "H1-L06", "H1-L07", "H1-L08", "H1-L09"] \
                    if e["id"] == "P1-HW-22" else ["H1-L02", "H1-L03"]
                e["rfq_lines"] = [{"line": x, "package": "RFQ3-H1FAB", "dispatch": "P1_NEEDED"} for x in lines]
                e["disposition"] = "RFQ_LINE"
                e["note"] = "A9.10 OQ-RFQV2-10 (build-to-print; design, integration and acceptance in-house)"
            if e["id"] == "P1-HW-16":
                e["note"] = "chamber facility-provided; pumping quoted in VAC-L02 (A9.8 OQ-RFQV2-02)"
    npd = ic["not_procured_dispositions"]
    npd["NP-FACILITY"] = {"disposition": "FACILITY_PROVIDED_NOT_PROCURED",
                          "why": "the P1 chamber is facility-provided; its interfaces are VAC-L01; pumping is a "
                                 "required quoted item VAC-L02 (A9.8 OQ-RFQV2-02); an external facility's pumping "
                                 "counts only after verification (RFQ3-VAC-N01)"}
    npd["NP-H1-BUILD"] = {"disposition": "RESOLVED_TO_RFQ_LINES",
                          "why": "A9.10 OQ-RFQV2-10: H-1 fabrication is the separate build-to-print package RFQ3-H1FAB"}
    npd["NP-CONDITIONAL-P3Q01"] = {"disposition": "RESOLVED_TO_RFQ_LINES",
                                   "why": "A9.8 P3Q-01: Langmuir-probe cross-check selected (TH-L10)"}
    _remap_lines(doc["a9_6_sec13_coverage"], idx, sup)
    # dispatch-first list
    doc["p1_dispatch_first"] = [{"package": p["id"], "line_item": li["id"], "item": li["item"], "qty": li["qty"],
                                 "option_line": li["option_line"], "send_state": li["quote_sheet"]["send_state"]}
                                for p in doc["packages"] for li in p["line_items"] if li["dispatch"] == "P1_NEEDED"]
    # rename-only sections
    for k in ("interface_demands", "m16_impact"):
        doc[k] = _rename(doc[k])
    for row in doc["m16_impact"]:
        row["proposed_procurement_status"] = row["proposed_procurement_status"].replace("RFQ_V2_", "RFQ_V3_")
        row["note"] = "proposal only; carried from v2 (package ids renamed); M16 is not edited by this lane"
    patch_interface_demands(doc, s)
    # change log
    reqs = [r for p in doc["packages"] for r in p["requirements"]]
    lines = [li for p in doc["packages"] for li in p["line_items"]]
    doc["change_log_v1_to_v2"] = doc.pop("change_log")
    per_req = [{"id": r["id"], "package": r["package"], "change": r["change_v3"]["type"],
                "why": r["change_v3"]["why"], "decisions": [f"{d['key']} {d['id']}" for d in r["change_v3"]["decisions"]],
                "dispatch": r["dispatch"]} for r in reqs]
    per_line = [{"id": li["id"], "package": idx[li["id"]][0], "change": li["change_v3"]["type"],
                 "why": li["change_v3"]["why"],
                 "decisions": [f"{d['key']} {d['id']}" for d in li["change_v3"]["decisions"]],
                 "dispatch": li["dispatch"], "option_line": li["option_line"]} for li in lines]
    counts = {}
    for x in per_req + per_line:
        counts[x["change"]] = counts.get(x["change"], 0) + 1
    counts["SUPERSEDED_LINES"] = len(doc["superseded_lines_v3"])
    doc["change_log"] = {
        "package_level": [
            {"id": "CL3-01", "change": "package ids RFQ2-* renamed RFQ3-*; requirement and line ids kept stable",
             "source": "this revision"},
            {"id": "CL3-02", "change": "new RF-metrology package RFQ3-RFMET (lines " + ", ".join(RFMET_LINES) +
                                       " moved from RF; RFM-L01 calibration accessories)", "source": "A9.8 P2Q-02"},
            {"id": "CL3-03", "change": "new H-1 build-to-print package RFQ3-H1FAB (H1-L01..L09, H1-O01)",
             "source": "A9.10 OQ-RFQV2-10; A9.14 OQ-A907-04, F5-OQ-04"},
            {"id": "CL3-04", "change": "HE-O02 -> required HE-L19 (in-house assembled DWV); ME-O01 -> required ME-L09 "
                                       "(dedicated target)", "source": "A9.8 OQ-RFQV2-08, P1Q-09"},
            {"id": "CL3-05", "change": "Xe hardware tagged as the RFP-required system Xe capability (both "
                                       "configurations); C1 Xe conditional; ICP Xe getter = engineering requirement",
             "source": "A9.14 XA9Q-07, XA9Q-05 as amended by A9.15"},
            {"id": "CL3-06", "change": "tank MEOP supplier-proposed at 323 K; 75-bar placeholder retired; Xe MFC "
                                       "indicative quotes now; C1 start controller an option; Option-B comparator; spares",
             "source": "A9.14 OQ-RFQ-09, XA9Q-06, OQ-RFQ-03, OQ-RFQ-04, OQ-RFQ-08, OQ-RFQ-01"},
            {"id": "CL3-07", "change": "Ar MFC certificate rule; pumping quoted; combined calorimetric load; magnet "
                                       "supply in P1 set; anode/discharge isolation class; DWV evidence route; C1 lines "
                                       "gated on the H-1 reference characterization; V/I calibration route",
             "source": "A9.8 OQ-RFQV2-01..06, 08; A9.10 OQ-RFQV2-09; A9.11 P2Q-07"},
            {"id": "CL3-08", "change": "Langmuir-probe cross-check line TH-L10", "source": "A9.8 P3Q-01"},
            {"id": "CL3-09", "change": "C1 lines HE-L10 / L11 / L12, the C1 Xe branch GAS-L05 / L06 / L15 and the C1 "
                                       "getter option GAS-O03 reclassified GROUND_ONLY_LAB_EQUIPMENT (new RFQ3-HALLEL-N03; "
                                       "H-1 reference characterization A9.10 S3.5 and C1-vs-ICP bench control); flight-C1 "
                                       "wording removed (RFQ-07-R09 / R08 / R06, RFQ-08-R01, NIR-04, IFD-19, P1-HW-32); "
                                       "Xe = contingency / emergency supply mode (RFQ3-GAS-N03)",
             "source": "A9.19 architecture / xenon_role; A9.20 answer; A9.10 P1Q-07"},
            {"id": "CL3-10", "change": "Xe storage / flow quotation split RFQ3-GAS-N05 (tank, regulator, valves, plumbing, "
                                       "mounting/thermal, C1-specific branch separate and ground-only); new quote-request "
                                       "lines GAS-L18 (plumbing) and GAS-L19 (mounting/thermal) with supplier-proposed "
                                       "quantities; AL-08 mass context = provisional planning floor, row-54 allocation "
                                       "kept as labelled history", "source": "A9.21 AL08"},
            {"id": "CL3-11", "change": "per-package dispatch-readiness record and checklist (READY_FOR_OWNER_DISPATCH / "
                                       "NOT_READY_* / LATER_NOT_IN_CURRENT_DISPATCH); the repository never dispatches; "
                                       "purchase NOT authorized", "source": "A9.21 RFQ_DISPATCH (item 15)"},
        ],
        "per_requirement": per_req, "per_line_item": per_line, "counts": dict(sorted(counts.items()))}
    v2tm = {x["requirement"]: x for x in v2["traceability_matrix"]}
    tm = []
    for r in reqs:
        base = v2tm.get(r["id"])
        srcs = list(base["sources"]) if base else []
        for x in r["sources"]:
            lb = label(x)
            if lb not in srcs:
                srcs.append(lb)
        tm.append({"requirement": r["id"], "v1_id": r["v1_id"], "package": r["package"], "title": r["title"],
                   "sources": srcs, "status": r["status"], "freeze_point": r["freeze_point"], "dispatch": r["dispatch"],
                   "change": r["change_v3"]["type"]})
    doc["traceability_matrix"] = tm
    # owner answers applied (v3 entries per decision question) + v2 history kept
    entries = {}
    for (key, qid), e in sorted(c.applied.items()):
        src = e["source"]
        js = _decision(key)[0]
        rec = js["decisions"].get(qid) if key not in ("A9.15",) + tuple(SINGLE_RECORD_KEYS) + \
            STRING_DECISION_KEYS else None
        entries.setdefault(key.replace(".", "_").lower(), []).append({
            "decision_key": key, "question_id": qid,
            "sequenced_no": rec.get("sequenced_no") if rec else None,
            "answer": rec.get("answer") if rec else src["answer"],
            "amended_by": rec.get("amended_by") if rec else None,
            "decision_json": DECISIONS[key]["json"], "json_sha256": DECISIONS[key]["json_sha256"],
            "verbatim_md": DECISIONS[key]["md"], "md_sha256": DECISIONS[key]["md_sha256"],
            "citation": f"{key} {qid} ({DECISIONS[key]['json']} sha256 {DECISIONS[key]['json_sha256']})",
            "applied_in": sorted(e["applied_in"])})
    oaa = {"rule_v3": "one entry per applied (decision, question id); applied_in lists every v3 requirement / line / "
                      "CIF item whose change_v3 cites it; the verbatim .md governs over the json summary"}
    oaa.update({k: entries[k] for k in sorted(entries)})
    oaa["v2_history"] = v2["owner_answers_applied"]
    # CIF items and interface demands cite decisions as well
    for x in doc["common_interface"]["items"] + doc["interface_demands"]:
        for d in x.get("change_v3", {}).get("decisions", []):
            for e in oaa[d["key"].replace(".", "_").lower()]:
                if e["question_id"] == d["id"] and x["id"] not in e["applied_in"]:
                    e["applied_in"] = sorted(e["applied_in"] + [x["id"]])
    doc["owner_answers_applied"] = oaa
    # open owner questions
    oq = v2["open_owner_questions"]
    closed = []
    qmap = {"OQ-RFQV2-01": "A9.8", "OQ-RFQV2-02": "A9.8", "OQ-RFQV2-03": "A9.8", "OQ-RFQV2-04": "A9.8",
            "OQ-RFQV2-05": "A9.8", "OQ-RFQV2-06": "A9.8", "OQ-RFQV2-08": "A9.8", "OQ-RFQV2-09": "A9.10",
            "OQ-RFQV2-10": "A9.10", "P2Q-02": "A9.8", "P2Q-07": "A9.11", "OQ-RFQ-01": "A9.14", "OQ-RFQ-03": "A9.14",
            "OQ-RFQ-04": "A9.14", "OQ-RFQ-08": "A9.14", "OQ-RFQ-09": "A9.14"}
    asked = [x["id"] for x in oq["new"]] + [x["id"] for x in oq["carried_open_from_lanes"]] + \
        [x["id"] for x in oq["carried_open_from_v1"]]
    for qid in asked:
        key = qmap[qid]   # KeyError = an open v2 question this revision does not account for
        rec = _decision(key)[0]["decisions"][qid]
        closed.append({"id": qid, "state": "OWNER_DECIDED", "answer": rec["answer"], "decision": key,
                       "decision_json": DECISIONS[key]["json"], "json_sha256": DECISIONS[key]["json_sha256"],
                       "how": "applied in v3 (see owner_answers_applied)"})
    doc["open_owner_questions"] = {
        "new": [], "closed_since_previous_revision": closed,
        "closed_in_v2": oq["closed_since_previous_revision"],
        "carried_open_from_lanes": [], "carried_open_from_v1": [],
        "v1_questions_answered_since": oq["v1_questions_answered_since"],
        "state_file": STATE_V4, "rule": "every question left open by v2 is OWNER_DECIDED in A9.8 / A9.10 / A9.11 / "
                                         "A9.14 and applied here; no new owner question is raised (recorder flags "
                                         "below are interpretations for the owner's review, not questions)"}
    doc["recorder_flags_v3"] = [
        {"id": "RF3-FLAG-01", "flag": "A9.8 OQ-RFQV2-04 accepts 'power analyser and RF metrology under RF' while the "
                                      "same addendum's P2Q-02 creates a separate RF-metrology package; v3 applies P2Q-02 "
                                      "to the owner-listed measurement equipment (plus RF-O01, which stands in for the "
                                      "VNA spectrum mode) and keeps the power analyser RF-L11 and the match encoders "
                                      "RF-L19 under RF"},
        {"id": "RF3-FLAG-02", "flag": "decisions applied beyond the lane list because they change RFQ lines directly: "
                                      "A9.8 P1Q-09 (ME-L09), P3Q-01 (TH-L10), P1-IT-55 (leakage rule), A9.14 P1Q-17 "
                                      "(700 V reverification), F5-OQ-04 (H-1 drawing release), F5-OQ-03 (754 degC "
                                      "context), XA9Q-01 (loaded cases), MPQ-01 (AL-C1 getter), MQ-05 (AL-08 scope "
                                      "and 6.0528 kg MEV planning floor in the Xe-hardware mass context)"},
        {"id": "RF3-FLAG-03", "flag": "instrument coverage is the v2 snapshot remapped to v3 lines; re-verification "
                                      "against the A9.16-updated P1 / P2 lanes and the cross-lane pairs is for the "
                                      "integration lane; cross-lane statuses carried from v2 that name other lanes' "
                                      "questions (e.g. IFD-14 MQ-01, IFD-17 P4 IT-17) are not restated here"},
        {"id": "RF3-FLAG-04", "flag": "the RFP (RFP(1)) is owner-held and not yet registered in the repository "
                                      "(AG-15); A9.15 content is applied as owner-stated"},
        {"id": "RF3-FLAG-05", "flag": "A9.20: the owner chose the recommended ground-only option and in the same message "
                                      "asked 'is it good to remove hollow cathode' - recorded for the owner, not "
                                      "answered here; A9.19 'check C1 mass' is a mass / budget-lane request (C1 is now "
                                      "outside every flight budget), not an RFQ line change"},
        {"id": "RF3-FLAG-06", "flag": "A9.21 AL08 split mapping (recorder reading for the owner): the low-flow FCU "
                                      "GAS-L10 is stated as a sub-row of 'valves' (the mass / power v3 AL-08 floor books "
                                      "the flow-control valves under valves); the laboratory Xe MFC GAS-L04 is not one "
                                      "of the owner's split categories and is quoted on its own line; the owner may "
                                      "re-map either"},
        {"id": "RF3-FLAG-07", "flag": "A9.21 item 15 dispatch readiness: the classification of open items "
                                      "(SUPPLIER_TO_ANSWER / DEFERRED_TO_FREEZE_GATE / BLOCKING_SEND, rule function "
                                      "classify_open_item) is a recorder rule for owner review; the Xe storage / flow "
                                      "lines whose split quotations the AL-08 re-base waits for keep their owner dispatch "
                                      "tag LATER - sending them earlier is an owner call"},
    ]
    doc["merged_cross_lane"] = dict(doc["merged_cross_lane"])
    doc["merged_cross_lane"]["rule_v3"] = ("v2 cross-lane pairs carried as a snapshot; v3 does not run the xlane check "
                                           "(counterpart lanes cite RFQ v2); re-pairing is the integration lane's job")
    doc["historical_reuse"] = dict(doc["historical_reuse"])
    doc["historical_reuse"]["v2_pins"] = doc["v2_pins"]
    # H3 / H4
    h = doc["h3_h4_inputs"]
    h["h3_procurement_gate"] = {
        "state": "QUOTATION PACKAGES v3 READY FOR OWNER DISPATCH (P1 subset first; H-1 build-to-print only with the "
                 "P9e configuration-controlled P1 drawing set); PURCHASE ORDERS, ADVANCE PAYMENTS AND BINDING COMMITMENTS NOT AUTHORIZED",
        "purchase_gate": "H3 procurement gate + frozen A9 interfaces (owner row 8; A9.1 A9-09 procurement restriction)",
        "packages": [{"id": p["id"], "owner_family": p["owner_family"], "p1_needed_line_items": p["p1_needed_line_items"],
                      "open_items_blocking_po": [o["id"] for o in p["open_specification_items"]]}
                     for p in doc["packages"]]}
    h["h4_tests"] = _rename(h["h4_tests"]) + [
        {"id": "H4-RFQ3-01", "test": "in-house current-limited 1.05 kV DC / 60 s DWV of the assembled insulation "
                                     "configuration per insulation path, with pre-registered per-path leakage limits",
         "source": "A9.8 OQ-RFQV2-08, P1-IT-55"},
        {"id": "H4-RFQ3-02", "test": "external-facility pumping verification (speed, range, gas compatibility, "
                                     "instrumentation, interface conductance) before it may replace VAC-L02",
         "source": "A9.8 OQ-RFQV2-02"},
        {"id": "H4-RFQ3-03", "test": "separate verification of the RF-load and calorimetric functions of a combined "
                                     "load", "source": "A9.8 OQ-RFQV2-03"},
        {"id": "H4-RFQ3-04", "test": "V/I-probe magnitude / relative-phase calibration (accredited or in-house "
                                     "traceable) followed by CAL-P2-15", "source": "A9.11 P2Q-07"},
        {"id": "H4-RFQ3-05", "test": "incoming inspection of H-1 build-to-print parts against the controlled drawing",
         "source": "A9.10 OQ-RFQV2-10"},
    ]
    doc["standing_facts"] = dict(doc["standing_facts"])
    doc["standing_facts"]["rfp_propellant_policy"] = "A9.15: ambient air (180-230 km) + Xenon, separate tanks; Xe is " \
                                                     "an RFP-required system capability; A9.19: Xe is the " \
                                                     "contingency / emergency supply mode, no conventional hollow " \
                                                     "cathode in the flight architecture; A9.20: C1 ground-only"
    doc["standing_facts"]["c1_role_a9_20"] = ("GROUND_ONLY_LAB_EQUIPMENT (A9.20); the carried A9.2 status "
                                              "'C1 conventional reference: CONTROL_FALLBACK' is history - A9.19 removes "
                                              "C1 as a flight fallback (hall_c1_reference is not a flight configuration)")
    doc["compliance"] = {
        "lane_paths": ["docs/procurement/rfq_a9_v3/**", TEST],
        "v2_untouched": "all v2 files pinned by sha256 and verified at every build",
        "no_purchase_order": True, "no_supplier_contact": True, "no_supplier_ranking": True, "no_prices": True,
        "no_supplier_names_invented": True,
        "deferred_numbers": "every owner-deferred number stays TBD with its freeze gate; fail-closed rule functions",
        "pure": "standard library; not wired into archengine; goldens unaffected", "never_pass": NEVER_PASS}
    for k in ("a9_4_incorporation", "a9_6_completion", "pending_parallel_lanes", "decision_pins", "deliverable_pins",
              "never_pinned", "merged_lanes_read", "dispatch_authority", "derived", "configurations",
              "outcome_vocabulary", "status_not_outcome", "evidence_classes", "freeze_points", "requirement_statuses",
              "dispatch_tags", "change_types"):
        if k in doc:
            doc.setdefault("carried_from_v2", {})[k] = doc.pop(k)
    doc["vocabulary"] = {"configurations": CONFIGS, "configuration_roles_a9_19_20": dict(CONFIGURATION_ROLES),
                         "equipment_classes": [GROUND_ONLY], "freeze_points": FREEZE_POINTS, "requirement_statuses": STATUSES,
                         "dispatch_tags": DISPATCH, "change_types_v3": CHANGE_TYPES_V3,
                         "evidence_classes": EVIDENCE_CLASSES}
    doc["al08_quotation_split_a9_21"] = {
        "decision": [s["A921-AL08-FLOOR"], s["A921-AL08-C1"], s["A921-AL08-SPLIT"]],
        "requirement": "RFQ3-GAS-N05", "mass_context": "RFQ2-GAS-R28 (RFQ-07-R10)",
        "categories": copy.deepcopy(AL08_SPLIT), "attributes_per_category": list(AL08_SPLIT_ATTRIBUTES),
        "new_quote_request_lines": list(AL08_NEW_LINES), "outside_split_categories": dict(AL08_OUTSIDE_SPLIT),
        "al08_status": AL08_PROVISIONAL, "al08_mev_planning_floor_kg": AL08_FLOOR_KG,
        "rebase": "formal AL-08 re-base only after the split quotations; an owner decision (A9.21); this RFQ never "
                  "re-bases or freezes AL-08 (rule function al08_quote_split_status)",
        "c1_branch": AL08_C1, "budgets_record_checked": MASS_POWER_V3}
    compute_dispatch_readiness(doc, s)
    order = ["schema", "id", "title", "revision_of", "lane", "follow_on", "trigger", "status", "a9_status", "base_commit",
             "generated_by", "companion_document", "test", "banner", "rfp_propellant_policy", "vocabulary",
             "decision_pins_v3", "v2_pins", "never_pinned_v3", "standing_facts", "common_interface", "packages",
             "superseded_lines_v3", "p1_dispatch_first", "dispatch_readiness_a9_21", "al08_quotation_split_a9_21",
             "a9_6_sec13_coverage", "instrument_coverage",
             "not_in_this_revision", "resolved_not_in_previous_revision", "change_log", "traceability_matrix",
             "interface_demands", "owner_answers_applied", "open_owner_questions", "recorder_flags_v3",
             "historical_reuse", "m16_impact", "h3_h4_inputs", "merged_cross_lane", "compliance", "change_types_v3",
             "change_log_v1_to_v2", "carried_from_v2"]
    rest = [k for k in doc if k not in order]
    if rest:
        raise KeyError(f"unordered top-level keys: {rest}")
    snapshot = {k: doc[k] for k in order if k in doc}
    doc.clear()
    doc.update(snapshot)


# ------------------------------------------------------------------------------------------------------- rendering
def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _cell(v) -> str:
    return _fmt(v).replace("|", "\\|").replace("\n", " ")


def _table(rows: list, cols: list) -> list:
    out = ["| " + " | ".join(col[0] for col in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(col[1](r)) for col in cols) + " |")
    return out


def _decs(x) -> str:
    return ", ".join(f"{d['key']} {d['id']}" for d in x["change_v3"]["decisions"]) or "-"


REQ_COLS = [("id", lambda r: r["id"]), ("v1 id", lambda r: r["v1_id"]), ("title", lambda r: r["title"]),
            ("value", lambda r: r["value"]), ("units", lambda r: r["units"]),
            ("sources", lambda r: "; ".join(sorted({label(s) for s in r["sources"]}))),
            ("evidence", lambda r: r["evidence_class"]), ("status", lambda r: r["status"]),
            ("freeze", lambda r: r["freeze_point"]), ("dispatch", lambda r: r["dispatch"]),
            ("v3 change", lambda r: r["change_v3"]["type"]), ("v3 decisions", _decs)]
ITEM_COLS = [("id", lambda x: x["id"]), ("item", lambda x: x["item"]), ("qty", lambda x: x["qty"]),
             ("basis", lambda x: x["basis"]), ("dispatch", lambda x: x["dispatch"]),
             ("option", lambda x: "OPTION" if x["option_line"] else ""),
             ("requirements", lambda x: ", ".join(x["requirements"])),
             ("freeze gate", lambda x: x["quote_sheet"]["freeze_gate"]),
             ("v3 change", lambda x: x["change_v3"]["type"]), ("v3 decisions", _decs)]


def render_package(p: dict) -> str:
    L_ = [f"# {p['id']} - {p['owner_family']}", "", "> **" + p["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in p["banner"][1:]]
    L_ += ["", f"Generated by `{THIS_SCRIPT}` from `{OUT_JSON}`; do not edit by hand. Revision of the immutable v2 "
               f"packages (`docs/procurement/rfq_a9_v2/`" +
           (f", v2 package {p['v2_package']})." if p.get("v2_package") else "; new package in v3)."), ""]
    if p.get("scope_note_v3"):
        L_ += [f"Scope note: {p['scope_note_v3']}.", ""]
    if p.get("owner_minimum_scope_source"):
        sq = p["owner_minimum_scope_source"]
        L_ += [f"Owner basis ({sq['key']} {sq['id']}): \"{sq['quote']}\"", ""]
    if p.get("retained_in_house_verbatim"):
        L_ += ["Retained in-house (A9.10 OQ-RFQV2-10): " + "; ".join(p["retained_in_house_verbatim"]) + ".", ""]
    L_ += ["## Owner minimum scope and coverage", ""]
    L_ += _table([{"k": k, "v": v} for k, v in p["owner_minimum_scope_coverage"].items()],
                 [("owner item", lambda x: x["k"]), ("line items", lambda x: ", ".join(x["v"]))])
    L_ += ["", "## Line items (P1_NEEDED lines can be dispatched first)", ""]
    L_ += _table(p["line_items"], ITEM_COLS)
    L_ += ["", "## Line quote sheets (RFQ only - no purchase order authorization)", ""]
    for li in p["line_items"]:
        qs = li["quote_sheet"]
        L_ += [f"### {li['id']} - {li['item']}", "",
               f"- dispatch: {li['dispatch']}" + (" (OPTION LINE)" if li["option_line"] else "") +
               f"; quantity: {_fmt(li['qty'])}; freeze gate: {_fmt(qs['freeze_gate'])}; {qs['send_state']}"]
        if li.get("dispatch_gate"):
            L_.append(f"- dispatch gate: {_fmt(li['dispatch_gate'])}")
        if li.get("c1_xe_condition"):
            L_.append(f"- C1 Xe condition: {li['c1_xe_condition']}")
        if li.get("al08_split_category"):
            L_.append(f"- A9.21 AL-08 quotation split category: {li['al08_split_category']} - {li['al08_booking']}")
        if li.get("placement"):
            pl = li["placement"]
            L_.append(f"- package placement {pl['status']} ({pl['question']}): {pl['rule']}")
        if li["change_v3"]["type"] != "CARRIED_UNCHANGED":
            L_.append(f"- v3 change ({li['change_v3']['type']}): {li['change_v3']['why']}")
        L_.append("- specification:")
        for sp in qs["spec"]:
            L_.append(f"  - {sp['requirement']}" + (f" ({sp['v1_id']})" if sp["v1_id"] else "") +
                      f" {sp['title']}: {_fmt(sp['value'])} [{_fmt(sp['units'])}]; freeze {sp['freeze_point']}; "
                      f"status {sp['status']}")
        if not qs["spec"]:
            L_.append("  - (no requirement attached; LATER line carried from v1)")
        for fld, head in (("acceptance", "acceptance"), ("calibration_traceability", "calibration / traceability"),
                          ("documentation", "documentation")):
            L_.append(f"- {head}: " + "; ".join(qs[fld]))
        L_.append("")
    L_ += ["## Requirements", ""]
    L_ += _table(p["requirements"], REQ_COLS)
    L_ += ["", "### Requirement text", ""]
    for r in p["requirements"]:
        L_.append(f"- **{r['id']}** ({r['v1_id'] or 'new'}; {r['dispatch']}): {r['requirement']}")
        if r.get("note"):
            L_.append(f"  - note: {r['note']}")
        if r["change_v3"]["type"] != "CARRIED_UNCHANGED":
            L_.append(f"  - v3 change ({r['change_v3']['type']}): {r['change_v3']['why']}")
    if p["cross_package_requirements"]:
        L_ += ["", "## Cross-package requirements cited by this package's lines", "",
               ", ".join(p["cross_package_requirements"]) + " (full text in the owning package; values are copied into "
                                                           "the line quote sheets above)."]
    if p.get("not_in_this_revision"):
        L_ += ["", "## Not in this revision", ""]
        for x in p["not_in_this_revision"]:
            L_.append(f"- **{x['id']}** {x['item']} - {x['why']}")
    for fld, head in (("acceptance", "Acceptance"), ("calibration_traceability", "Calibration and traceability"),
                      ("documentation", "Deliverable documentation"), ("supplier_must_state", "Supplier must state")):
        L_ += ["", f"## {head}", ""]
        for x in p[fld]:
            L_.append(f"- {x['text']}" + (f" _({x['carried_from']})_" if x["carried_from"] else ""))
    L_ += ["", "## Common-interface ids touched", "", ", ".join(p["cif_interfaces"]) or "-"]
    if p["reference_data"]:
        L_ += ["", "## Reference data (" + p["reference_data_use"] + ")", ""]
        for x in p["reference_data"]:
            pv = x["provenance_display"]
            L_.append(f"- {x['source_id']}: {_fmt(x['datum'])} - {x['note']}. Source: {x['citation']}; URL {pv['url']}; "
                      f"accessed {pv['accessed']}; access: {pv['access_mode']} _({x['carried_from']})_.")
        L_.append("")
        L_.append("Reference data are not requirements, not a selection and not a supplier ranking.")
    rd = p["dispatch_readiness"]
    L_ += ["", "## Dispatch readiness checklist (A9.21 item 15)", "",
           f"NOW subset: **{rd['now_subset']['readiness']}**; LATER subset: {rd['later_subset']['readiness'] or '-'}. "
           f"Dispatched by the repository: {rd['dispatched_by_repository']}; purchase authorized: "
           f"{rd['purchase_authorized']}. Common interface cited: {rd['common_interface']['id']} "
           f"{rd['common_interface']['revision']} (`{rd['common_interface']['file']}`, rendered sha256 "
           f"`{rd['common_interface']['rendered_sha256']}`). Owner action: {rd['owner_action']}.", ""]
    L_ += [f"- [{'x' if c_['ok'] else ' '}] {c_['check']}" for c_ in rd["checklist"]]
    L_ += [""]
    L_ += _table(rd["lines"], [("line", lambda x: x["line"]), ("set", lambda x: x["set"]),
                               ("readiness", lambda x: x["readiness"]),
                               ("supplier answers", lambda x: ", ".join(x["supplier_to_answer"]) or "-"),
                               ("deferred to gate", lambda x: ", ".join(x["deferred_to_freeze_gate"]) or "-"),
                               ("blocking", lambda x: ", ".join(x["blocking_open_items"]) or "-"),
                               ("reason", lambda x: x["reason"]), ("send state", lambda x: x["send_state"])])
    L_ += ["", "## Open specification items", ""]
    L_ += _table(p["open_specification_items"], [("id", lambda x: x["id"]), ("v1", lambda x: x["v1_id"]),
                                                 ("title", lambda x: x["title"]), ("value", lambda x: x["value"]),
                                                 ("freeze", lambda x: x["freeze_point"]),
                                                 ("dispatch", lambda x: x["dispatch"])])
    return "\n".join(L_) + "\n"


def render_cif(ci: dict) -> str:
    L_ = [f"# {ci['id']} - {ci['title']}", "", "> **" + ci["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in ci["banner"][1:]]
    L_ += ["", ci["purpose"], "", f"Package policy: {ci['package_policy_v3']['rule']}. "
                                  f"{ci['package_policy_v3']['rfmet_interfaces']}.", "", "## Shared items", ""]
    L_ += _table(ci["items"], [("id", lambda x: x["id"]), ("group", lambda x: x["group"]),
                               ("title", lambda x: x["title"]), ("value", lambda x: x["value"]),
                               ("status", lambda x: x["status"]), ("freeze", lambda x: x["freeze_point"]),
                               ("source", lambda x: x["source"]),
                               ("v3 change", lambda x: x["change_v3"]["type"])])
    L_ += ["", "## Cross-package interface matrix", ""]
    L_ += _table(ci["interface_matrix"], [("id", lambda x: x["id"]), ("between", lambda x: " <-> ".join(x["between"])),
                                          ("what", lambda x: x["what"]), ("reference", lambda x: x["reference"]),
                                          ("units", lambda x: x["units"]), ("status", lambda x: x["status"]),
                                          ("source", lambda x: x["source"]), ("dispatch", lambda x: x["dispatch"])])
    return "\n".join(L_) + "\n"


def render_main(d: dict) -> str:
    L_ = [f"# {d['title']}", "", "> **" + d["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in d["banner"][1:]]
    L_ += ["", f"Lane {d['lane']} ({d['follow_on']}); status {d['status']}; base commit `{d['base_commit']}`. Generated "
               f"by `{d['generated_by']}` (`--check` reproduces it); test `{d['test']}`.", "",
           f"Revision of the immutable v2 packages `{d['revision_of']['path']}` (json sha256 "
           f"`{d['revision_of']['json_sha256']}`); v2 and v1 are never edited.", "",
           "## RFP-compliant propellant policy (A9.15)", "", f"> {d['rfp_propellant_policy']['governing_rule']}", "",
           "Applied: " + "; ".join(d["rfp_propellant_policy"]["applied"]) + ". Unchanged: " +
           d["rfp_propellant_policy"]["unchanged"] + ".", "", "## Packages", ""]
    L_ += _table(d["packages"], [("package", lambda p: p["id"]), ("family", lambda p: p["owner_family"]),
                                 ("v2 package", lambda p: p["v2_package"] or "new"),
                                 ("file", lambda p: p["package_file"]),
                                 ("P1 lines", lambda p: len(p["p1_needed_line_items"])),
                                 ("LATER lines", lambda p: len(p["later_line_items"])),
                                 ("requirements", lambda p: len(p["requirements"]))])
    L_ += ["", f"Common interface document: `{d['common_interface']['package_file']}`.", "",
           "## Superseded lines", ""]
    L_ += _table(d["superseded_lines_v3"], [("line", lambda x: x["id"]), ("package", lambda x: x["package"]),
                                            ("superseded by", lambda x: x["superseded_by"]),
                                            ("why", lambda x: x["why"])])
    L_ += ["", "## P1 dispatch-first list", ""]
    L_ += _table(d["p1_dispatch_first"], [("package", lambda x: x["package"]), ("line", lambda x: x["line_item"]),
                                          ("item", lambda x: x["item"]), ("qty", lambda x: x["qty"]),
                                          ("option", lambda x: "OPTION" if x["option_line"] else ""),
                                          ("send state", lambda x: x["send_state"])])
    dr = d["dispatch_readiness_a9_21"]
    L_ += ["", "## Dispatch readiness (A9.21 item 15)", "",
           f"> Owner (A9.21 RFQ_DISPATCH): \"{dr['decision']['quote']}\"", "",
           f"Repository dispatches: **{dr['repository_dispatches']}**; purchase authorized: "
           f"**{dr['purchase_authorized']}**; dispatch record: {dr['dispatch_record']}.", "",
           f"Rule: {dr['rule']}. Order: {dr['order_rule']}. Common interface: {dr['common_interface']['id']} "
           f"{dr['common_interface']['revision']} (`{dr['common_interface']['file']}`, rendered sha256 "
           f"`{dr['common_interface']['rendered_sha256']}`).", ""]
    L_ += _table(dr["packages"], [("order", lambda x: x["p1_first_order"]), ("package", lambda x: x["package"]),
                                  ("NOW readiness", lambda x: x["now_readiness"]),
                                  ("NOW lines", lambda x: len(x["now_lines"])),
                                  ("blocking", lambda x: ", ".join(x["blocking"]) or "-"),
                                  ("LATER", lambda x: x["later_readiness"] or "-"),
                                  ("LATER lines", lambda x: len(x["later_lines"])),
                                  ("CIF", lambda x: x["common_interface"])])
    L_ += ["", "Status vocabulary:", ""] + [f"- `{k}`: {v}" for k, v in dr["status_vocabulary"].items()]
    L_ += ["", "Open-item classes:", ""] + [f"- `{k}`: {v}" for k, v in dr["open_item_classes"].items()]
    sp = d["al08_quotation_split_a9_21"]
    L_ += ["", "## Xe storage / flow quotation split and AL-08 (A9.21 AL08)", ""]
    L_ += [f"> Owner (A9.21 AL08): \"{x['quote']}\"" for x in sp["decision"]]
    L_ += ["", f"AL-08 status: **{sp['al08_status']}** - {sp['al08_mev_planning_floor_kg']:g} kg MEV planning floor is "
               f"provisional, not frozen; {sp['rebase']}. Requirement {sp['requirement']}; mass context "
               f"{sp['mass_context']}.", ""]
    L_ += _table(sp["categories"], [("category", lambda x: x["category"]), ("lines", lambda x: ", ".join(x["lines"])),
                                    ("booking", lambda x: x["booking"]), ("note", lambda x: x["note"])])
    L_ += ["", "Per category the supplier states: " + "; ".join(sp["attributes_per_category"]) + ".", ""]
    L_ += [f"- outside the split: {k} - {v}" for k, v in sp["outside_split_categories"].items()]
    L_ += ["", "## Owner answers applied (v3)", "", d["owner_answers_applied"]["rule_v3"], ""]
    rows = [e for k, v in d["owner_answers_applied"].items() if k.startswith("a9_") for e in v]
    L_ += _table(rows, [("decision", lambda x: x["decision_key"]), ("question", lambda x: x["question_id"]),
                        ("seq", lambda x: x["sequenced_no"]), ("answer", lambda x: x["answer"]),
                        ("json sha256", lambda x: x["json_sha256"]), ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "(v2 owner-answer history is carried in the JSON under owner_answers_applied.v2_history.)", "",
           "## Owner questions", "", d["open_owner_questions"]["rule"], ""]
    L_ += _table(d["open_owner_questions"]["closed_since_previous_revision"],
                 [("id", lambda x: x["id"]), ("state", lambda x: x["state"]), ("answer", lambda x: x["answer"]),
                  ("decision", lambda x: x["decision"])])
    L_ += ["", "## Recorder flags", ""] + [f"- {x['id']}: {x['flag']}" for x in d["recorder_flags_v3"]]
    L_ += ["", "## Not in this revision", ""]
    for x in d["not_in_this_revision"]:
        L_.append(f"- **{x['id']}** {x['item']} - {x['why']}")
    for x in d.get("resolved_not_in_previous_revision", []):
        L_.append(f"- ~~{x['id']}~~ {x['item']} - {x['state_v3']}")
    L_ += ["", "## Change log (v2 -> v3)", ""]
    L_ += _table(d["change_log"]["package_level"], [("id", lambda x: x["id"]), ("change", lambda x: x["change"]),
                                                    ("source", lambda x: x["source"])])
    L_ += ["", "Counts: " + _fmt(d["change_log"]["counts"]), ""]
    changed = [x for x in d["change_log"]["per_requirement"] + d["change_log"]["per_line_item"]
               if x["change"] != "CARRIED_UNCHANGED"]
    L_ += _table(changed, [("id", lambda x: x["id"]), ("package", lambda x: x["package"]),
                           ("change", lambda x: x["change"]), ("decisions", lambda x: ", ".join(x["decisions"])),
                           ("why", lambda x: x["why"])])
    L_ += ["", "## Traceability matrix (requirement -> source)", ""]
    L_ += _table(d["traceability_matrix"], [("requirement", lambda x: x["requirement"]),
                                            ("v1", lambda x: x["v1_id"]), ("package", lambda x: x["package"]),
                                            ("sources", lambda x: "; ".join(x["sources"])),
                                            ("status", lambda x: x["status"]), ("freeze", lambda x: x["freeze_point"]),
                                            ("dispatch", lambda x: x["dispatch"]), ("change", lambda x: x["change"])])
    ic = d["instrument_coverage"]
    L_ += ["", "## P1 / P2 instrument coverage", "", ic["rule"] + ".", ""]
    for k, v in ic["not_procured_dispositions"].items():
        L_.append(f"- {k}: {v['disposition']} - {v['why']}")
    for sec in ("p1_measurements", "p1_hardware", "p2_instruments"):
        L_ += ["", f"### {sec}", ""]
        L_ += _table(ic[sec], [("id", lambda x: x["id"]), ("what", lambda x: x["what"]),
                               ("RFQ lines / disposition",
                                lambda x: ", ".join(f"{y['line']} ({y['package']}, {y['dispatch']})"
                                                    for y in x["rfq_lines"]) or x["disposition"])])
    h = d["h3_h4_inputs"]
    L_ += ["", "## H3 / H4 inputs", "", f"H3 gate: {h['h3_procurement_gate']['state']}; "
                                        f"{h['h3_procurement_gate']['purchase_gate']}.", ""]
    L_ += _table(h["h3_procurement_gate"]["packages"], [("package", lambda x: x["id"]),
                                                        ("P1 lines", lambda x: ", ".join(x["p1_needed_line_items"])),
                                                        ("open items blocking PO",
                                                         lambda x: ", ".join(x["open_items_blocking_po"]))])
    L_ += [""] + _table(h["h4_tests"], [("id", lambda x: x["id"]), ("test", lambda x: x["test"]),
                                        ("source", lambda x: x["source"])])
    L_ += ["", "## Pins", ""]
    L_ += _table(d["decision_pins_v3"] + d["v2_pins"], [("key", lambda x: x["key"]), ("path", lambda x: x["path"]),
                                                        ("sha256", lambda x: x["sha256"])])
    L_ += ["", "Never pinned: " + "; ".join(d["never_pinned_v3"])]
    return "\n".join(L_) + "\n"


def outputs(doc: dict) -> dict:
    files = {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_main(doc),
             doc["common_interface"]["package_file"]: render_cif(doc["common_interface"])}
    for p in doc["packages"]:
        files[p["package_file"]] = render_package(p)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are up to date; write nothing")
    args = ap.parse_args(argv)
    files = outputs(build())
    if args.check:
        bad = []
        for rel, txt in files.items():
            p = _abs(rel)
            if not os.path.isfile(p):
                bad.append(rel + " (missing)")
                continue
            with open(p, encoding="utf-8") as fh:
                if fh.read() != txt:
                    bad.append(rel)
        extra = sorted(set(os.listdir(_abs(PKG_DIR))) - {os.path.basename(k) for k in files if k.startswith(PKG_DIR)}) \
            if os.path.isdir(_abs(PKG_DIR)) else []
        bad += [f"{PKG_DIR}/{x} (stale extra file)" for x in extra]
        if bad:
            print("STALE: " + ", ".join(bad))
            return 1
        print(f"OK: {len(files)} outputs reproduce")
        return 0
    os.makedirs(_abs(PKG_DIR), exist_ok=True)
    for rel, txt in files.items():
        with open(_abs(rel), "w", encoding="utf-8") as fh:
            fh.write(txt)
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
