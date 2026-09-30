#!/usr/bin/env python3
"""M16 subsystem maturity matrix v3 (A9-10 refresh, fo_a9_10_integration): deterministic builder.

A NEW version: subsystem_maturity_v1.json / SUBSYSTEM_MATURITY.md and subsystem_maturity_v2.json /
SUBSYSTEM_MATURITY_v2.md (and the v2 builder) stay byte-identical. v3 carries every v2 row by reference (v2 pinned by
sha256; cells not copied) and adds the A9 refresh for the Hall -> downstream 13.56 MHz ICP neutralizer investigation:

  * rows 1-16: the A9 lanes that touch the row (their own m16_impact entries, read from the merged deliverables), ONE
    A9 blocking item per row (row 141: one-blocker rule), its execution state under the accepted scheduler rule
    (row 141), what it waits on (v2 waits_on vocabulary), its latest decision point (row 144) and a functional-role
    owner (row 140: until named engineers exist; no row unowned);
  * row 17 (RF pre-ionization module interface): SUPERSEDED_FOR_PRIMARY_LINE (historical, kept; A9, rows 61-65);
  * new row 18: downstream ICP neutralizer head; new row 19: flight RF chain (RF source DC input, coupler, 50-ohm line,
    LOCAL matching network on / adjacent to the ICP module per A9.2, feedthrough);
  * A9.2 (owner decisions 2026-09-30): new design-blocker rows 20 (H-1 anode material) and 21 (H-1 anode heat-removal
    path), rows 13 / 15 blockers re-pointed to the coupled thermal model / impedance map, and the verbatim A9.2 statuses
    per row (read from the sha256-pinned copy under docs/experiments/hall_icp/integration/a9_2_inputs/).

Every blocking item is copied from a verified A9 deliverable and checked at build time (its text must appear at the
cited place). Selection rule (PROPOSED for the owner under the accepted one-blocker rule): the item named by the most
downstream merged A9 lane for that row (A9-07 > A9-09 > A9-03 > A9-02 > A9-08 > A9-06), else the v2 item.

Usage:  python docs/budgets/subsystem_maturity/build_subsystem_maturity_v3.py [--check]
No prediction, no winner; A9 stays OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REL = "docs/budgets/subsystem_maturity"
# DECLARED SCOPE DEVIATION (recorded in the A9-10 reconciliation record, section scope_deviations): the brief names
# docs/budgets/subsystem_maturity/subsystem_maturity_v3.json, but the historical, immutable H2-7 mechanical BOM builder
# scans docs/budgets/subsystem_maturity/*.json (non-recursive) and pins the sha256 of every file it finds, so ANY new
# JSON there makes the H2-7 v1 --check stale. The v3 JSON therefore lives under an allowed A9-10 path; the builder and
# the companion Markdown are at the names the brief gives. Orchestrator acceptance requested (OQ-A910-04).
JSON_REL = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
MD_REL = REL + "/SUBSYSTEM_MATURITY_v3.md"
SCRIPT_REL = REL + "/build_subsystem_maturity_v3.py"
TEST_REL = "tests/test_subsystem_maturity_v3.py"
V2 = REL + "/subsystem_maturity_v2.json"
PINS = {
    V2: "a82b1acd118b26e89edd4fa467bec778fa410470cca5eb6f684e6553eadaf23c",
    REL + "/subsystem_maturity_v1.json": None,   # recorded (byte identity is checked by the A9-10 record)
    "docs/decisions/OD_2026_09_29_owner_answers_147.json":
        "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1",
    "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json":
        "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json":
        "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json":
        "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    # A9.2 (owner decisions 2026-09-30, A9-07 follow-up): byte-identical pinned copy of
    # docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json (execution-branch commit 19c0040)
    "docs/experiments/hall_icp/integration/a9_2_inputs/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json":
        "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03",
    "docs/experiments/hall_icp/integration/a9_2_inputs/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md":
        "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9",
}
A92_COPY = "docs/experiments/hall_icp/integration/a9_2_inputs/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_REL = "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_SHA = "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03"
ANS = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
XE_A9 = "docs/budgets/" + "xe" + "_ledger_a9/" + "xe" + "_ledger_a9_v1.json"
LANES = {
    "A9-01": "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "A9-02": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "A9-03": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
    "A9-05ev": "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
    "A9-05vi": "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
    "A9-06": "docs/budgets/mass_a9/mass_a9_v1.json",
    "A9-07": "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json",
    "A9-08": XE_A9,
    "A9-09": "docs/procurement/rfq_a9/rfq_a9_v1.json",
}
WAITS_ON_VOCAB = ["owner decision", "H-1 / C-1 measurement (wave H4, PLANNED_NOT_REGISTERED)",
                  "procurement (wave H3, PLANNED_NOT_REGISTERED)", "design work outside every registered scope",
                  "first-hand source verification"]
OWN, H4, H3, DES, SRC = WAITS_ON_VOCAB
ACCOUNTABLE = ("Praveen (accountable system owner, owner row 140)")

# Functional-role owners (row 140: named engineers to be assigned before a row can become READY). PROPOSED roles.
ROLES = {
    1: "atmospheric intake lead", 2: "atmospheric intake lead", 3: "compressor / gas-path lead",
    4: "gas-path lead", 5: "gas-path / flow-control lead", 6: "Xe feed-system lead", 7: "Xe feed-system lead",
    8: "Xe feed-system lead", 9: "Hall thruster (H-1) lead", 10: "magnetic circuit (MC-1) lead",
    11: "electron-source lead (C1 reference / fallback)", 12: "power / PPU lead", 13: "thermal lead",
    14: "controls / FDIR lead", 15: "test and diagnostics lead", 16: "mechanical / structures lead",
    17: "electron-source lead (historical row)", 18: "electron-source lead (ICP neutralizer)",
    19: "power / PPU lead (RF chain)", 20: "Hall thruster (H-1) lead (anode material)",
    21: "thermal lead (H-1 anode heat-removal path)",
}

# One A9 blocking item per row: (lane, locator, text that must appear there, waits_on, latest decision point, a7 cat)
# locator = ("m16", row) -> that lane's m16_impact entry for the row; ("item", id, field) -> an item field
# None -> keep the v2 blocking item (no A9 lane names a blocker for this row).
A9_BLOCKERS = {
    1: None, 2: None, 3: None, 4: None, 5: None,
    6: ("A9-08", ("m16", 6), "the Xe ledger stays REFUSED per configuration (A7 blocker 3 unchanged)", None,
        "architecture closure (A7 blocker 3 unchanged)", None),
    7: ("A9-09", ("m16", 7), "specification gap at the C1 flow range", H3, "LOCK-1 (A9-01 GD-01 interfaces)", None),
    8: ("A9-07", ("m16", 8), "valve selection (A9-09 quotation)", H3, "before HI-S1A (instrument/valve availability)",
        None),
    9: ("A9-07", ("m16", 9), "FEMM of the preliminary MC-1", DES, "before HI-S1 (A9-01 GD-02 / GD-03)", None),
    10: ("A9-07", ("m16", 10), "sourced B_sat(T) and coil qualification", SRC,
         "before HI-LOCK2 (A9-01 GD-11 field tolerance)", None),
    11: ("A9-09", ("m16", 11), "I_d,max of the registered envelope", OWN,
         "LOCK-1 (OQ-A907-02: stand I_d,max registered before LOCK-1)", None),
    12: ("A9-07", ("m16", 12), "breadboard discharge supply (row 113)", H3, "before HI-LOCK2 (A9-01 GD-14)", None),
    13: ("A9-07", ("m16", 13), ("coupled H-1 / ICP thermal model (A9H-TH-01: Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume, ICP view "
         "factors; A9.2 ICP_COUPLED_THERMAL = UNRESOLVED)"), DES,
         "before any thermal closure of hall_icp_neutralizer and before HI-S1 (A9.2 ICP_COUPLED_THERMAL = UNRESOLVED; "
         "score-bearing aborts at limit - 50 K, A9.1 UBQ-06)", None),
    14: ("A9-03", ("m16", 14), "generator interlock interface (quotation)", H3, "before HI-S1A (A4 minimum interlocks)",
         None),
    15: ("A9-07", ("m16", 15), "ICP antenna impedance map (A9.2 P2; RF component ratings TBD_AFTER_IMPEDANCE_MAP)", H4,
         "before the RF component ratings are frozen (A9.2: TBD_AFTER_IMPEDANCE_MAP; trip thresholds after the load "
         "characterization)", None),
    16: ("A9-07", ("m16", 16), "module drawings (ICP-02/04/07)", DES, "before HI-S1 (A9-01 GD-01)", None),
}
NEW_ROWS = [
    {"row": 18, "key": "icp_neutralizer_head", "group": "propulsion",
     "name": "downstream 13.56 MHz RF ICP electron source / neutralizer head (antenna, dielectric, collector/bias "
             "electrode, capped dedicated gas port)",
     "flag": "primary investigation hypothesis (A9), not flight baseline", "baseline_flight_hardware": False,
     "requirement": "A9 governing decision (primary investigation); A9.1 ICP-45 (ICP-45A Ar / ICP-45N N2: I_e,cap >= "
                    "I_d,max before any score-bearing point); ICD ICP-01..ICP-46; G-REUSE primary gas mode (A9.1 "
                    "HIQ-06)",
     "allocation": {"mass": ("A9-06", "AL-05"), "power": "P_ICP,available = 1350 - P_common - P_Hall - P_other,active "
                                                          "(A9.1 OQ-A902-03; A9-02 A902-20)"},
     "interface_items": ["ICP-02", "ICP-04", "ICP-07", "ICP-21", "ICP-26", "ICP-43", "ICP-44", "ICP-45"],
     "evidence": "published analog only (A9-05: Takahashi et al., J. Electr. Propuls. 3:18 (2024), topology precedent; "
                 "never Vyovrinda performance)",
     "procurement": ("A9-09", "RFQ-05"),
     "analysis_test_needed": "ICP-45A (Ar, engineering-only) and ICP-45N (N2) electron-current capacity; ICP-44 RF "
                             "voltage / Paschen rating; ICP-43 total module heat vs the A9-07 IDA7-07 H-1 allowance; "
                             "collector material through the O/AO coupon programme (A9.1 A9-03-collector)",
     "blocker": ("A9-03", ("items_tbd", ["ICP-02", "ICP-04", "ICP-07", "ICP-21", "ICP-44"]),
                 "ICP module design (ICD ICP-02 standoff, ICP-04 aperture, ICP-07 envelope, ICP-21 collector, ICP-44 "
                 "RF voltage rating TBD); no registered lane designs the ICP module", DES,
                 "before HI-S1 (A9-01 GD-01: downstream ICP interfaces frozen)", "hardware-definition blocker")},
    {"row": 19, "key": "flight_rf_chain", "group": "power",
     "name": "flight RF chain: 13.56 MHz RF source (spacecraft-DC input), directional coupler, 50-ohm line, LOCAL "
             "matching network on / immediately adjacent to the ICP module (adjustable for development, A9.2), RF "
             "feedthrough",
     "flag": "primary investigation hypothesis (A9), not flight baseline", "baseline_flight_hardware": False,
     "requirement": "only the RF source DC input crosses the bus boundary (A9-02 A902-19, row 66 / 72); ICP power fits "
                    "P_ICP,available (A9.1 OQ-A902-03); P_bus,1ms,max < 1500 W incl. start-up (A9.1 OQ-A902-01)",
     "allocation": {"mass": ("A9-06", "AL-06"), "power": "inside P_ICP,available (no fixed split, A9.1 OQ-A902-03)"},
     "interface_items": ["ICP-13", "ICP-14", "ICP-15", "ICP-16", "ICP-24"],
     "evidence": "none for a flight unit (laboratory 0-500 W generator is a ground/facility test capability, row 72)",
     "procurement": ("A9-09", "RFQ-04"),
     "analysis_test_needed": "generator DC-input -> forward-power efficiency (A902-21, S1a); ICP impedance map "
                             "Z_antenna = R + jX vs mdot, P_RF, p, gas, Hall operating point (A9.2 P2) before any "
                             "component rating (TBD_AFTER_IMPEDANCE_MAP); RF protection trip thresholds after the load "
                             "characterization (A9.2); flight-representative DC-input RF source scoping",
     "blocker": ("A9-02", ("items_status", ["A902-21"]),
                 "flight-representative DC-input RF source not scoped: A902-21 (generator DC-input -> forward-power "
                 "efficiency) OPEN; the laboratory generator is ground/facility-only (OQ-RFQ-06)", H3,
                 "proposal / flight design freeze (Milestone C); A902-21 value at LOCK-2", "proposal-only "
                 "documentation gap")},
]


_A92 = None


def _a92_statuses() -> dict:
    with open(os.path.join(ROOT, A92_COPY), encoding="utf-8") as f:
        return json.load(f)["decisions"]["a9_10_statuses"]


ANODE_ROWS = [
    {"row": 20, "key": "h1_anode_material", "item": "A9H-ANODE-01",
     "name": "H-1 anode material (design-representative / flight)",
     "blocker_text": "DESIGN BLOCKER: H-1 anode material",
     "requirement": "A9.2: 316L REJECTED_AS_CURRENT_BASELINE for the design-representative / flight anode (engineering / "
                    "shakedown, coupon candidate, low-temperature development only); ANODE_BASELINE = OPEN; no "
                    "refractory metal selected merely for melting point; T_operating <= T_validated,continuous - 50 K "
                    "after the operating temperature is reduced; no new anode temperature limit",
     "analysis": "candidate-material trade (oxygen compatibility, sputtering, electrical behaviour, fabrication, thermal "
                 "conductivity); biased + floating coupons (row 106)",
     "statuses": ["316L flight anode", "final anode material"],
     "latest": "before any design-representative / score-bearing anode is built (A9.2; owner call on the trade)"},
    {"row": 21, "key": "h1_anode_heat_path", "item": "A9H-ANODE-02",
     "name": "H-1 anode heat-removal path",
     "blocker_text": "DESIGN BLOCKER: H-1 anode heat-removal path",
     "requirement": "A9.2: attack the anode as a thermal-design problem first: reduce the actual anode operating "
                    "temperature substantially (backplate conduction, support / feed-tube conduction, heat spreading, "
                    "radiative area, coupling to spacecraft / stand, deposited power fraction; active cooling only if "
                    "passive closure fails)",
     "analysis": "anode thermal redesign in the coupled H-1 / ICP model (A9-07 A9H-ANODE-02, A9H-TH-01)",
     "statuses": ["anode thermal closure"],
     "latest": "before the anode material selection (A9.2 order: heat path first, then material)"},
]
A92_ROW_STATUS = {11: ["C1 conventional reference"], 13: ["coupled H-1/ICP thermal closure"],
                  15: ["RF component ratings"],
                  18: ["Hall->ICP architecture", "ICP electron-current capacity", "ICP RF power closure"],
                  19: ["RF matching architecture", "RF component ratings", "ICP RF power closure"]}
A92_ST = _a92_statuses()


def _sha(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def _row_of(entry: dict):
    for k in ("m16_row", "row"):
        if k in entry:
            return entry[k]
    raise KeyError(f"m16_impact entry without a row: {entry}")


def _how(entry: dict) -> str:
    for k in ("how_touched", "how", "impact", "proposed_procurement_status"):
        if k in entry:
            return str(entry[k])
    return json.dumps(entry)


def build() -> dict:
    pins = []
    for rel, sha in PINS.items():
        got = _sha(rel)
        if sha is not None and got != sha:
            raise RuntimeError(f"pinned input changed: {rel} sha256 {got} != {sha}")
        pins.append({"path": rel, "sha256": got})
    v2 = _load(V2)
    answers = {a["row"]: a for a in _load(ANS)["answers"]}
    for r in (140, 141, 142, 143, 144):
        if not answers[r]["owner_answer_verbatim"]:
            raise RuntimeError(f"owner row {r} empty")
    lanes = {k: _load(v) for k, v in LANES.items()}
    lane_sha = {k: _sha(v) for k, v in LANES.items()}
    touch = {}
    for k, doc in lanes.items():
        for e in doc.get("m16_impact", []):
            touch.setdefault(_row_of(e), []).append({"lane": k, "how": _how(e),
                                                     **({"blocking_item": e["blocking_item"]}
                                                        if "blocking_item" in e else {})})
    rows = []
    for r in v2["rows"]:
        n = r["row"]
        s2 = r["scheduler"]
        base = {"row": n, "key": r["key"], "name": r["name"], "group": r["group"], "flag": r["flag"],
                "baseline_flight_hardware": r["baseline_flight_hardware"],
                "v2_cells": f"{V2}#/rows/{n - 1}/cells (carried by reference, unchanged)",
                "v2_scheduler": {"execution_state": s2["execution_state"], "blocking_item": s2["blocking_item"],
                                 "waits_on": s2["waits_on"], "a7_category": s2["a7_category"]},
                "a9_lanes": touch.get(n, [])}
        if n == 17:
            base["a9_refresh"] = {
                "execution_state": "SUPERSEDED_FOR_PRIMARY_LINE",
                "note": "the RF pre-ionization module interface is historical for the primary line (A9; owner rows "
                        "61-65, 147); kept byte-identical in v1/v2 and not scheduled; its successor rows are 18 (ICP "
                        "neutralizer head) and 19 (flight RF chain)",
                "blocking_item": None, "waits_on": None, "latest_decision_point": None,
                "owner": {"functional_role": ROLES[n], "accountable": ACCOUNTABLE, "named_engineer": None}}
            rows.append(base)
            continue
        spec = A9_BLOCKERS[n]
        if spec is None:
            blk = {"source": "v2 (no A9 lane names a blocker for this row)", "ref": s2["blocking_item"]["ref"],
                   "text": s2["blocking_item"]["text"]}
            waits, latest = s2["waits_on"], (r["cells"]["blocker"].get("first_gate")
                                             or r["cells"]["blocker"].get("beyond"))
            a7 = s2["a7_category"]
        else:
            lane, loc, text, waits, latest, a7 = spec
            ent = [t for t in touch.get(n, []) if t["lane"] == lane]
            found = any(text in json.dumps(t, ensure_ascii=False) for t in ent)
            if not found:
                raise RuntimeError(f"row {n}: blocking item text not found in {lane} m16_impact: {text!r}")
            blk = {"source": f"{lane} {LANES[lane]} m16_impact (row {n})", "text": text}
            waits = waits or s2["waits_on"]
            a7 = a7 or s2["a7_category"]
        if waits not in WAITS_ON_VOCAB:
            raise RuntimeError(f"row {n}: waits_on {waits!r} not in the vocabulary")
        base["a9_refresh"] = {
            "blocking_item": blk, "execution_state": "BLOCKED",
            "worked_by": None,
            "not_worked_reason": "no registered follow-on is scoped to produce this item: A9-01..A9-10 are complete "
                                 "deliverables and the H3 / H4 waves are PLANNED_NOT_REGISTERED (v2 scheduler rule, "
                                 "accepted in row 141)",
            "waits_on": waits, "latest_decision_point": latest, "a7_category": a7,
            "owner": {"functional_role": ROLES[n], "accountable": ACCOUNTABLE, "named_engineer": None,
                      "rule": "row 140: a named responsible engineer is needed before the row can become READY"}}
        rows.append(base)
    icd = {x["id"]: x for x in lanes["A9-03"]["items"]}
    bus = {x["id"]: x for x in lanes["A9-02"]["items"]}
    lines = {x["line"]: x for x in lanes["A9-06"]["line_checks"]}
    pkgs = {p["id"]: p for p in lanes["A9-09"]["packages"]}
    for spec in NEW_ROWS:
        lane, loc, text, waits, latest, a7 = spec["blocker"]
        kind, ids = loc
        for i in ids:
            if kind == "items_tbd":
                it = icd[i]
                if it["value"] is not None:
                    raise RuntimeError(f"row {spec['row']}: {i} is no longer TBD")
            else:
                if not bus[i]["status"].startswith("OPEN"):
                    raise RuntimeError(f"row {spec['row']}: {i} is no longer OPEN")
        ml, al = spec["allocation"]["mass"]
        line = lines[al]
        pk = pkgs[spec["procurement"][1]]
        rows.append({
            "row": spec["row"], "key": spec["key"], "name": spec["name"], "group": spec["group"], "flag": spec["flag"],
            "baseline_flight_hardware": spec["baseline_flight_hardware"], "new_in_v3": True,
            "cells": {
                "requirement": spec["requirement"],
                "allocation": {"mass": {"line": al, "owner_allocation_kg": line["allocation_kg"],
                                        "state": line["state"], "source": f"{LANES[ml]} line_checks[line={al}]",
                                        "evidence_class": "owner-allocation"},
                               "power": spec["allocation"]["power"]},
                "interface_status": {"document": LANES["A9-03"], "document_status": lanes["A9-03"]["status"],
                                     "items": {i: icd[i]["status"] for i in spec["interface_items"]}},
                "preliminary_design": "none (ICD items PROPOSED / TBD; no ICP module design lane registered)",
                "evidence_status": spec["evidence"],
                "procurement_status": {"package": spec["procurement"][1], "file": pk["package_file"],
                                       "status": "RFQ_SPEC_READY_QUOTATION_ONLY (no purchase order; H3 gate)"},
                "analysis_test_needed": spec["analysis_test_needed"]},
            "a9_lanes": touch.get(spec["row"], []),
            "a9_refresh": {"blocking_item": {"source": f"{lane} {LANES[lane]} ({', '.join(ids)})", "text": text},
                           "execution_state": "BLOCKED", "worked_by": None,
                           "not_worked_reason": "no registered follow-on is scoped to produce this item (accepted "
                                                "scheduler rule, row 141)",
                           "waits_on": waits, "latest_decision_point": latest, "a7_category": a7,
                           "owner": {"functional_role": ROLES[spec["row"]], "accountable": ACCOUNTABLE,
                                     "named_engineer": None,
                                     "rule": "row 140: named engineer needed before READY"}}})
    # A9.2 (anode_316L / anode_approach): two design-blocker rows under H-1, blocker copied from A9-07 new_items
    h2a9_items = {x["id"]: x for x in lanes["A9-07"]["new_items"]}
    for spec in ANODE_ROWS:
        it = h2a9_items[spec["item"]]
        if spec["blocker_text"] not in it["name"] or not it["value"].startswith("TBD - requires"):
            raise RuntimeError(f"row {spec['row']}: A9-07 {spec['item']} does not carry the blocker")
        rows.append({
            "row": spec["row"], "key": spec["key"], "name": spec["name"], "group": "propulsion",
            "flag": "design blocker of the H-1 Hall head (A9.2); not flight baseline", "baseline_flight_hardware": False,
            "new_in_v3": True,
            "cells": {"requirement": spec["requirement"], "allocation": {"mass": "inside AL-04 (A9-06 A9B-15, TBD)",
                                                                         "power": "none (passive)"},
                      "interface_status": {"document": LANES["A9-07"], "items": {spec["item"]: it["status"]}},
                      "preliminary_design": "none (ANODE_BASELINE = OPEN)",
                      "evidence_status": "A9-07 uncoupled thermal sensitivity only (anode worst case "
                                         "OPEN_LIMIT_TBD; no validated material limit)",
                      "procurement_status": "none (no anode RFQ implied, A9.2)",
                      "analysis_test_needed": spec["analysis"]},
            "a9_lanes": [{"lane": "A9-07", "how": f"{spec['item']}: {it['name']}"}],
            "a9_2": {"statuses": {k: A92_ST[k] for k in spec["statuses"]}, "source": A92_REL + " (sha256 " + A92_SHA +
                     ") decisions.anode_316L / anode_approach"},
            "a9_refresh": {"blocking_item": {"source": f"A9-07 {LANES['A9-07']} new_items {spec['item']}",
                                             "text": spec["blocker_text"]},
                           "execution_state": "BLOCKED", "worked_by": None,
                           "not_worked_reason": "no registered follow-on is scoped to produce this item (accepted "
                                                "scheduler rule, row 141); recommended next lane P4 (anode design), "
                                                "not launched",
                           "waits_on": DES, "latest_decision_point": spec["latest"], "a7_category": None,
                           "owner": {"functional_role": ROLES[spec["row"]], "accountable": ACCOUNTABLE,
                                     "named_engineer": None, "rule": "row 140: named engineer needed before READY"}}})
    for r in rows:
        extra = A92_ROW_STATUS.get(r["row"])
        if extra:
            r["a9_2"] = dict(r.get("a9_2", {}), statuses=dict(r.get("a9_2", {}).get("statuses", {}),
                                                              **{k: A92_ST[k] for k in extra}),
                             source=A92_REL + " (sha256 " + A92_SHA + ") decisions.a9_10_statuses")
    states = {}
    waits_c = {}
    for r in rows:
        st = r["a9_refresh"]["execution_state"]
        states[st] = states.get(st, 0) + 1
        w = r["a9_refresh"].get("waits_on")
        if w:
            waits_c[w] = waits_c.get(w, 0) + 1
    return {
        "schema": "subsystem_maturity_matrix_v3", "id": "subsystem_maturity_v3",
        "supersedes_for_use": {"path": V2, "sha256": PINS[V2], "note": "v1 and v2 files stay byte-identical"},
        "lane": "fo_a9_10_integration (A9-10 M16 refresh)", "trigger": "T_A9_10_INTEGRATION",
        "authorization": "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json execution.step_3_A9-10 "
                         "('refresh M16'); owner rows 140-144",
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "generated_by": SCRIPT_REL, "companion_document": MD_REL, "test": TEST_REL,
        "file_location": {"json": JSON_REL, "brief_named_path": REL + "/subsystem_maturity_v3.json",
                          "status": "DECLARED_SCOPE_DEVIATION (orchestrator acceptance requested, OQ-A910-04)",
                          "reason": "the immutable H2-7 v1 mechanical BOM builder (docs/hardware/h2/"
                                    "h2_7_mechanical_bom/build_h2_7_mechanical_bom.py, lane_consumption) scans "
                                    + REL + "/*.json non-recursively and pins the sha256 of every file found; a new "
                                    "JSON at the brief-named path makes the H2-7 v1 --check stale (verified), so the "
                                    "JSON lives under an allowed A9-10 path; builder and Markdown keep the "
                                    "brief-named paths"},
        "what_it_is_not": ["not a performance prediction", "not an architecture selection (no winner)",
                           "not a change to v1 / v2", "not an owner decision: blocking-item selection, roles and "
                                                      "latest decision points are PROPOSED"],
        "pins": pins, "lane_deliverables_read": [{"lane": k, "path": v, "sha256": lane_sha[k]}
                                                 for k, v in LANES.items()],
        "scheduler_rule": {"source": f"{V2} scheduler_rule", "status": "ACCEPTED by the owner (row 141: scheduler "
                           "rule, one-blocker rule, non-lane-input guard, per-row blockers, A7 roll-up)",
                           "states": ["READY", "RUNNING", "BLOCKED", "VERIFIED"],
                           "v3_addition": "SUPERSEDED_FOR_PRIMARY_LINE marks a historical row that is not scheduled",
                           "blocking_item_selection_PROPOSED": "the item named by the most downstream merged A9 lane "
                           "for the row (A9-07 > A9-09 > A9-03 > A9-02 > A9-08 > A9-06), else the v2 item"},
        "waits_on_vocabulary": WAITS_ON_VOCAB,
        "owner_rule": {"row": 140, "accountable": ACCOUNTABLE, "rule": "one named responsible engineer per row before "
                       "READY; until then an explicit functional role (PROPOSED here); no row unowned"},
        "rows": rows,
        "rollup": {"execution_states": dict(sorted(states.items())), "waits_on": dict(sorted(waits_c.items()))},
        "a9_2": {"decision": {"path": A92_REL, "sha256": A92_SHA, "pinned_copy": A92_COPY},
                 "statuses": A92_ST,
                 "applied": "rows 13 / 15 blocking items (coupled thermal model, impedance map); row 19 renamed for the "
                            "local match; new design-blocker rows 20 (anode material) and 21 (anode heat-removal path); "
                            "per-row A9.2 statuses (rows 11, 13, 15, 18, 19, 20, 21)",
                 "recommended_next_lanes_not_launched": ["P1 ICP electron-source bench (ICP-45)",
                                                         "P2 ICP impedance map", "P3 coupled thermal redesign",
                                                         "P4 anode design"]},
        "open_owner_questions": [
            {"id": "M16-V3-Q-01", "question": "Accept the PROPOSED A9 blocking item, functional-role owner and latest "
             "decision point of each row (rows 1-16, 18-21), and name the responsible engineers (row 140)?",
             "proposed_answer": "owner call", "needed_by": "before any row can become READY (row 140)"}],
        "compliance": ["v1 / v2 unchanged", "blocking items copied from merged A9 deliverables and checked at build "
                       "time", "mutable governance never pinned", "no winner; no prediction"],
    }


def _c(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_md(d) -> str:
    L = ["# M16 subsystem maturity matrix v3 (A9-10 refresh)", "",
         f"<!-- GENERATED by {SCRIPT_REL} from subsystem_maturity_v3.json; do not edit by hand -->", "",
         f"Status **{d['status']}**; A9 stays **{d['a9_status']}**. Supersedes for use `{d['supersedes_for_use']['path']}` "
         f"(sha256 `{d['supersedes_for_use']['sha256']}`); v1 and v2 unchanged.", "",
         f"Scheduler rule: {d['scheduler_rule']['status']}; {d['scheduler_rule']['v3_addition']}; blocking-item "
         f"selection (PROPOSED): {d['scheduler_rule']['blocking_item_selection_PROPOSED']}.", "",
         f"File location: JSON at `{d['file_location']['json']}` instead of `{d['file_location']['brief_named_path']}` "
         f"- {d['file_location']['status']}: {d['file_location']['reason']}.", "",
         f"Owner rule (row 140): {d['owner_rule']['rule']}; accountable: {d['owner_rule']['accountable']}.", "",
         f"Roll-up: {_c(d['rollup'])}.", "",
         "| row | subsystem | state | A9 blocking item | waits on | latest decision point | owner (functional role) |",
         "|---|---|---|---|---|---|---|"]
    for r in d["rows"]:
        a = r["a9_refresh"]
        b = a.get("blocking_item") or {}
        L.append(f"| {r['row']} | {_c(r['name'])} | {a['execution_state']} | {_c(b.get('text'))} ({_c(b.get('source'))})"
                 f" | {_c(a.get('waits_on'))} | {_c(a.get('latest_decision_point'))} | {_c(a['owner']['functional_role'])} |")
    L += ["", "## A9 lanes touching each row", ""]
    for r in d["rows"]:
        if r["a9_lanes"]:
            L.append(f"* **row {r['row']} {r['key']}**: " + "; ".join(f"{t['lane']}: {_c(t['how'])}" for t in r["a9_lanes"]))
    L += ["", "## New rows", ""]
    for r in d["rows"]:
        if r.get("new_in_v3"):
            L.append(f"### Row {r['row']}: {r['name']}")
            L.append("")
            for k, v in r["cells"].items():
                L.append(f"* **{k}**: {_c(v)}")
            L.append("")
    L += ["## Open owner questions", ""]
    for q in d["open_owner_questions"]:
        L.append(f"* **{q['id']}** {q['question']} Proposed: {q['proposed_answer']}. Needed by {q['needed_by']}.")
    L += ["", "Pins: " + "; ".join(f"`{p['path']}` `{p['sha256']}`" for p in d["pins"])]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    d = build()
    outs = {JSON_REL: json.dumps(d, indent=1, ensure_ascii=False) + "\n", MD_REL: render_md(d)}
    if a.check:
        bad = [rel for rel, t in outs.items() if not os.path.isfile(os.path.join(ROOT, rel))
               or open(os.path.join(ROOT, rel), encoding="utf-8").read() != t]
        print("OK" if not bad else "DRIFT: " + ", ".join(bad))
        return 0 if not bad else 1
    for rel, t in outs.items():
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
            f.write(t)
    print(f"wrote {JSON_REL} and {MD_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
