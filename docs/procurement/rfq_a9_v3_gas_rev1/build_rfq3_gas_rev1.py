#!/usr/bin/env python3
"""RFQ3-GAS rev1: the GAS-only governed successor revision of the authorized RFQ v3 gas/metrology package.

Owner basis: A9.25 message 8 FINAL_PRE_BID_AFI_RESOLUTION, section 5 'RFQ3-GAS - REVISE, BUT PRESERVE V3'
(docs/decisions/OD_2026_10_04_A9_25_PRE_BID_OWNER_DECISIONS.md, verbatim text sha256 a48dfcbb...). The authorized RFQ v3
package (docs/procurement/rfq_a9_v3/) is NOT overwritten: its JSON, companion, builder, the RFQ3-GAS package text and its
cover note are pinned by sha256 and read as DATA; the other five authorized packages (RF, VAC, HALLEL, MECH, RFMET) and
their cover notes are pinned and recorded UNCHANGED.

rev1 = the v3 RFQ3-GAS package text with exactly these controlled substitutions (each must match its expected count,
fail closed):
  * the RFQ2-GAS-R28 (RFQ-07-R10) mass-context value: the v3 'AL-08 MEV 6.0528 kg / CBE 5.044 kg' current context is
    replaced by the current AL-08 planning context read from docs/budgets/mass_power_a9_v4 (CBE planning floor 4.929 kg,
    MEV planning floor 5.9148 kg, PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN; plumbing and mounting/thermal TBD; quotations
    replace / re-base the provisional floors); 5.9148 kg is an INTERNAL planning floor, NOT a supplier maximum-mass
    requirement (suppliers state their offered component masses); the v3 values are kept only as labelled history;
  * the v3 change note of RFQ2-GAS-R28 is labelled history;
  * the carried 'high-pressure Xe/cathode branch' wording (RFQ2-GAS-R23 / RFQ2-GAS-N07) carries a rev1 reading: the
    flight high-pressure Xe path (dual series isolation, owner row 55); no cathode branch exists in flight;
  * title / provenance line and a 'Revision rev1' section (quotation split, C1 lines GROUND_ONLY_LAB_EQUIPMENT never in
    flight AL-08, dispatch rule).
Nothing else changes: lines, quantities, requirements, quotation-only terms (no PO / advance / selection / commitment).

Dispatch (A9.25 message 8 section 5): the dispatch status of the v3 RFQ3-GAS package is unknown to the repository (its
record is AUTHORIZED_PENDING_OWNER_SEND; the repository never sends). If v3 has NOT been sent externally, the owner
dispatches only this successor package; if it HAS been sent, v3 is preserved and this revision is issued as the controlled
addendum (dispatch/RFQ3-GAS_REV1_ADDENDUM.md).

    python docs/procurement/rfq_a9_v3_gas_rev1/build_rfq3_gas_rev1.py          # (re)write outputs
    python docs/procurement/rfq_a9_v3_gas_rev1/build_rfq3_gas_rev1.py --check  # exit 1 unless reproduced byte for byte

Standard library only; deterministic; well under a second; not wired into archengine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE_REL = "docs/procurement/rfq_a9_v3_gas_rev1"
SCRIPT_REL = LANE_REL + "/build_rfq3_gas_rev1.py"
JSON_REL = LANE_REL + "/rfq3_gas_rev1.json"
MD_REL = LANE_REL + "/RFQ3_GAS_REV1.md"
PKG_REL = LANE_REL + "/packages/RFQ3-02_gas_metrology_rev1.md"
COVER_REL = LANE_REL + "/dispatch/RFQ3-GAS_REV1_COVER.md"
ADDENDUM_REL = LANE_REL + "/dispatch/RFQ3-GAS_REV1_ADDENDUM.md"
TEST_REL = "tests/test_rfq3_gas_rev1.py"
SCHEMA_ID = "rfq3_gas_rev1"
DATE = "2026-10-04"
BASE_COMMIT = "9c5fee0440e0ee26963826381582ca6c8e7772ff"

V3 = "docs/procurement/rfq_a9_v3"
PINS = {
    "V3_JSON": (V3 + "/rfq_a9_v3.json", "2252523956cd8b281fb33cae2d18fe38028b8b43ad3e5e424cceafed35bef300"),
    "V3_MD": (V3 + "/RFQ_A9_V3.md", "6c99fac775820fea23e5f8f5bed75000792cc42e5e45f31f3c70b315bfd299b1"),
    "V3_BUILDER": (V3 + "/build_rfq_a9_v3.py", "cfa874903c83cca3cb09d416ab990f219bc225b2d515a599f1965963d79db57f"),
    "V3_CIF": (V3 + "/packages/RFQ3-00_common_interface.md",
               "e4b2f647151fa40b0a8a6b90b9068cb8b08690c106d1e1d8a616e08e7e76d311"),
    "V3_GAS_PKG": (V3 + "/packages/RFQ3-02_gas_metrology.md",
                   "1078e0e95087682ddeed79e074507bec53ed03f287bd4936f12b9760ecbc4935"),
    "V3_GAS_COVER": (V3 + "/dispatch/RFQ3-GAS_COVER.md",
                     "29c2c81dd9bc2fef0f406cf10b81b320fba6f6292a0956ab05472da7121cb5f2"),
    "A9_25_MD": ("docs/decisions/OD_2026_10_04_A9_25_PRE_BID_OWNER_DECISIONS.md",
                 "159ea2049e3cc05ce7a18b3e6bbdf6fee97c168a74f23fd2359cfef3a1d26106"),
    "A9_25_JSON": ("docs/decisions/OD_2026_10_04_A9_25_pre_bid_owner_decisions.json",
                   "c05fcc45de0194e60ef30b93aa91294c54a7762d129dac69e933e9a679679385"),
}
# the other five A9.24-authorized packages: recorded UNCHANGED (pinned; A9.25 message 8 section 5)
UNCHANGED = {
    "RFQ3-RF": ((V3 + "/packages/RFQ3-01_rf.md", "0ae15107fb05d70acba5e4204d47f1d388ed867de17694f77e7426d76b89224f"),
                (V3 + "/dispatch/RFQ3-RF_COVER.md", "0de9b3f0fc074ded3cb44c829320fc569738dfa6410ffaed79b35343eba803e8")),
    "RFQ3-VAC": ((V3 + "/packages/RFQ3-03_vacuum_facility.md",
                  "c4b19a5c2ade1660def4e8e744d6c497e0d46109c002ef5afd0f6b7b6d76efc6"),
                 (V3 + "/dispatch/RFQ3-VAC_COVER.md",
                  "28ee0bb3cd3acf534d440b682b148578f4c2e2eecee8c0d8aaa661720296613a")),
    "RFQ3-HALLEL": ((V3 + "/packages/RFQ3-04_hall_electrical.md",
                     "d7f8af8fbd8676d9726c8470edfe4dea6543a63d8ef7da91f4f614dc9b6c6a48"),
                    (V3 + "/dispatch/RFQ3-HALLEL_COVER.md",
                     "6d338597b67a998da12ea46d75e6233b37c9a8a3a5f1f86e3f0a36799a1bd24b")),
    "RFQ3-MECH": ((V3 + "/packages/RFQ3-05_mechanical_icp_fabrication.md",
                   "9e21f9f70bc102b157616aeae643c6a0fce954687ab61018627de8a37b29ad0e"),
                  (V3 + "/dispatch/RFQ3-MECH_COVER.md",
                   "d76b5c22324e246f5d7bbdc38089c1e4400f9a9d2e4f57c1f88da91c77ef2c60")),
    "RFQ3-RFMET": ((V3 + "/packages/RFQ3-07_rf_metrology.md",
                    "cd06ae7c20e2fcb1458b40b1e6864527f74c651e78dddd3d9c74fd2e9552dd0c"),
                   (V3 + "/dispatch/RFQ3-RFMET_COVER.md",
                    "f210b473aa0f7cb0a28f13918757928c2f438e53e5c5b99c3e1614789552603d")),
}
MP4 = "docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json"     # read as data (active flight mass source; A9.25 s6)
MP4_EXPECTED = {"evidence_floor_cbe_kg": 4.929, "mev_kg": 5.9148}  # cross-check (A9.25 message 8 section 5)
V3_EXPECTED = {"AL-08_MEV_planning_floor_kg": 6.0528, "AL-08_evidence_floor_cbe_kg": 5.044}
AL08_PROVISIONAL = "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN"
M8 = {"n": 8, "key": "FINAL_PRE_BID_AFI_RESOLUTION",
      "text_sha256": "a48dfcbb9fa33421bf19ff45fa241070c22a8379a3eb4e887b661fb8ceb93624"}
M8_TOKENS = ("Do not overwrite the authorized RFQ v3 historical package",
             "AL-08 CBE planning floor = 4.929 kg", "AL-08 MEV planning floor = 5.9148 kg",
             "PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN", "5.9148 kg is an INTERNAL PLANNING FLOOR",
             "It is NOT a supplier maximum-mass requirement unless separately approved",
             "Suppliers should state their offered component masses", "two series isolation latches",
             "anode/Xe-contingency proportional flow control", "GROUND_ONLY_LAB_EQUIPMENT",
             "dispatch only the revised successor package", "issue the revised information as a controlled addendum",
             "Do not change the other five authorized RFQ packages")
NOT_AUTHORIZED = ["purchase order", "advance payment", "supplier selection", "binding commitment"]
DISPATCH = {
    "v3_rfq3_gas_dispatch_status": "UNKNOWN_TO_REPOSITORY (v3 record: AUTHORIZED_PENDING_OWNER_SEND; the repository "
                                   "never sends and holds no external dispatch record)",
    "rev1_dispatch_status": "AUTHORIZED_PENDING_OWNER_SEND (quotation only; A9.24 item 10 authorization of RFQ3-GAS, "
                            "revised per A9.25 message 8 section 5); nothing sent from the repository",
    "if_v3_not_sent": "the owner dispatches ONLY this successor package (packages/RFQ3-02_gas_metrology_rev1.md with "
                      "dispatch/RFQ3-GAS_REV1_COVER.md); the v3 RFQ3-GAS package is then not sent",
    "if_v3_already_sent": "v3 is preserved as sent; this revision is issued to the same recipients as the controlled "
                          "addendum dispatch/RFQ3-GAS_REV1_ADDENDUM.md (it supersedes the v3 AL-08 mass context only)",
    "other_packages": "RFQ3-RF / RFQ3-VAC / RFQ3-HALLEL / RFQ3-MECH / RFQ3-RFMET unchanged (v3 files pinned)",
    "quotation_only": "unchanged: quotation, technical clarification, datasheets, capability information, mass/power "
                      "information, lead time; NOT authorized: " + ", ".join(NOT_AUTHORIZED)}
# quotation split (owner wording, A9.25 message 8 section 5) mapped to the v3 lines (recorder mapping, RF3-FLAG-06
# carried: the owner may re-map)
SPLIT = [
    ("tank", ["GAS-L08"], "FLIGHT_AL08"),
    ("regulator", ["GAS-L09"], "FLIGHT_AL08"),
    ("two series isolation latches", ["GAS-L11"], "FLIGHT_AL08"),
    ("anode / Xe-contingency proportional flow control", ["GAS-L10"], "FLIGHT_AL08"),
    ("plumbing", ["GAS-L18"], "FLIGHT_AL08"),
    ("mounting/thermal", ["GAS-L19"], "FLIGHT_AL08"),
    ("other explicitly classified items", ["GAS-L04"], "CLASSIFIED_PER_LINE (v3 AL08_OUTSIDE_SPLIT: Xe anode-path "
                                                       "MFC(s), mass stated on its own line; AL-08 membership not "
                                                       "decided here)"),
    ("C1-specific lines", ["GAS-L05", "GAS-L06", "GAS-L15", "GAS-O03"], "GROUND_ONLY_LAB_EQUIPMENT (never in flight "
                                                                         "AL-08; separate offer section)"),
]
R23_OLD = "high-pressure Xe/cathode branch"
R23_NEW = ("high-pressure Xe/cathode branch [rev1 reading: the flight high-pressure Xe path - two series isolation "
           "latches, owner row 55; no cathode branch exists in flight (A9.19 / A9.20; A9.25 message 8)]")


class Rev1Error(RuntimeError):
    """A pinned input changed, a source value moved or a substitution did not match its expected count."""


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _text(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def verify_pins() -> None:
    bad = [p for p, s in list(PINS.values()) + [x for v in UNCHANGED.values() for x in v] if _sha(p) != s]
    if bad:
        raise Rev1Error("pinned inputs changed: " + ", ".join(bad))


def message8() -> dict:
    md = _text(PINS["A9_25_MD"][0])
    head = f"## Message {M8['n']} — {M8['key']} — "
    if md.count(head) != 1:
        raise Rev1Error("A9.25 message 8 heading not found exactly once")
    text = md.split(head, 1)[1].split("````text\n", 1)[1].split("\n````", 1)[0]
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != M8["text_sha256"]:
        raise Rev1Error("A9.25 message 8 verbatim text does not reproduce its recorded sha256")
    flat = " ".join(text.split())
    missing = [t for t in M8_TOKENS if t not in flat]
    if missing:
        raise Rev1Error(f"A9.25 message 8 tokens missing: {missing}")
    sec5 = text.split("5. RFQ3-GAS — REVISE, BUT PRESERVE V3", 1)[1].split("6. BID MASS BASIS", 1)[0]
    sec5 = "\n".join(ln for ln in sec5.splitlines() if not set(ln.strip()) <= {"="}).strip()
    return {"decision": "A9.25", "message": M8["n"], "key": M8["key"], "section": 5,
            "text_sha256": M8["text_sha256"], "md": PINS["A9_25_MD"][0], "md_sha256": PINS["A9_25_MD"][1],
            "json": PINS["A9_25_JSON"][0], "json_sha256": PINS["A9_25_JSON"][1], "section_5_verbatim": sec5}


def v3_r28() -> dict:
    d = json.loads(_text(PINS["V3_JSON"][0]))
    gas = [p for p in d["packages"] if p["id"] == "RFQ3-GAS"]
    if len(gas) != 1 or gas[0]["package_file"] != PINS["V3_GAS_PKG"][0]:
        raise Rev1Error("v3 RFQ3-GAS package record not found")
    r = [x for x in gas[0]["requirements"] if x["id"] == "RFQ2-GAS-R28"]
    if len(r) != 1 or r[0]["v1_id"] != "RFQ-07-R10":
        raise Rev1Error("v3 RFQ2-GAS-R28 (RFQ-07-R10) not found exactly once")
    v = r[0]["value"]
    if {k: v.get(k) for k in V3_EXPECTED} != V3_EXPECTED:
        raise Rev1Error("v3 RFQ2-GAS-R28 is not the 6.0528 / 5.044 kg context this revision supersedes")
    auth = d["dispatch_authorization_a9_24"]["decision"][0]["answer"]
    if "RFQ3-GAS" not in auth["AUTHORIZED_FOR_QUOTATION_ONLY"] or auth["not_authorized"] != NOT_AUTHORIZED:
        raise Rev1Error("v3 A9.24 dispatch authorization changed")
    return {"req": r[0], "authorized": list(auth["AUTHORIZED_FOR_QUOTATION_ONLY"])}


def mp4_al08() -> dict:
    d = json.loads(_text(MP4))
    ln = [x for x in d["lines"]["hall_icp_neutralizer"] if x["line"] == "AL-08"]
    if len(ln) != 1:
        raise Rev1Error("mass_power_a9_v4 AL-08 not found exactly once")
    a = ln[0]
    got = {"evidence_floor_cbe_kg": a["evidence_floor_cbe_kg"], "mev_kg": a["value"]["value_kg"]}
    if got != MP4_EXPECTED or a["value"]["governs"] != "MEV_PLANNING_FLOOR":
        raise Rev1Error(f"mass_power_a9_v4 AL-08 changed: {got}")
    if not str(a.get("a9_21_status", "")).startswith(AL08_PROVISIONAL):
        raise Rev1Error("mass_power_a9_v4 AL-08 is no longer a provisional planning floor")
    if not str(a.get("c1_hardware_in_flight_al08", "")).startswith("NONE"):
        raise Rev1Error("mass_power_a9_v4 AL-08 does not state that no C1 hardware remains in flight AL-08")
    tbd = [c["what"] for c in a["floor_constituents"] if c["kg"] is None]
    if not tbd:
        raise Rev1Error("mass_power_a9_v4 AL-08: plumbing / mounting-thermal no longer TBD (re-check the RFQ context)")
    afi = d["afi_corrections"]["AFI-01"]
    res = [s for s in afi["resolved_stop_items"] if s["id"] == "AFI-01-S1"]
    if afi["stop_items"] or len(res) != 1 or res[0]["state"] != "OWNER_DECIDED_KEEP_SECOND_SERIES_LATCH":
        raise Rev1Error("mass_power_a9_v4 AFI-01-S1 is not the owner-resolved keep-second-latch state")
    valves = [c for c in a["floor_constituents"] if c.get("parts")]
    if len(valves) != 1 or [p["kg"] for p in valves[0]["parts"]] != [0.17, 0.115, 0.17]:
        raise Rev1Error("mass_power_a9_v4 AL-08 valve set is not latch #1 + PFCV + latch #2")
    return {"cbe_kg": got["evidence_floor_cbe_kg"], "mev_kg": got["mev_kg"], "valves_kg": valves[0]["kg"],
            "tbd": tbd, "sha256": _sha(MP4)}


def new_r28_value(old: dict, al: dict) -> dict:
    return {
        "AL-08_CBE_planning_floor_kg": al["cbe_kg"],
        "AL-08_MEV_planning_floor_kg": al["mev_kg"],
        "AL-08_status": AL08_PROVISIONAL + " (A9.21; A9.25 message 8 section 5): CURRENT provisional planning / evidence "
                        "floor, NOT frozen and NOT a complete CBE - plumbing remains TBD; mounting/thermal remains TBD; "
                        "quotations still replace / re-base the provisional component floors",
        "internal_planning_floor": f"{al['mev_kg']:g} kg is an INTERNAL planning floor; it is NOT a supplier "
                                   "maximum-mass requirement (none is approved); suppliers state their offered component "
                                   "masses per split category",
        "valve_planning_basis": f"valves {al['valves_kg']:g} kg = two series isolation latches (0.170 + 0.170 kg analog, "
                                "dual series isolation on the high-pressure Xe path, owner row 55) + one anode / "
                                "Xe-contingency proportional flow-control valve (0.115 kg analog); planning analogs only, "
                                "replaced by the quoted masses",
        "c1_lines": "GROUND_ONLY_LAB_EQUIPMENT: C1-specific lines (GAS-L05, GAS-L06, GAS-L15, GAS-O03) are quoted as a "
                    "separate offer section and are NEVER included in flight AL-08; no conventional hollow-cathode "
                    "hardware is in flight AL-08 (A9.25 message 8 section 1)",
        "note": "A9.14 MQ-05 (OWNER_DECIDED): AL-08 includes the complete Xe storage / flow hardware (tank, regulator, "
                "valves, plumbing, mounting, thermal); supplier states mass per split category and per case",
        "source": f"{MP4} lines[hall_icp_neutralizer][line=AL-08] (evidence_floor_cbe_kg, value, a9_21_status, "
                  "c1_hardware_in_flight_al08; AFI-01-S1 resolved; checked at build time)",
        "history": {"label": "HISTORY - RFQ v3 AL-08 context, not current (superseded by RFQ3-GAS rev1, A9.25 message "
                             "8 section 5)",
                    "v3_AL-08_MEV_planning_floor_kg": old["AL-08_MEV_planning_floor_kg"],
                    "v3_AL-08_evidence_floor_cbe_kg": old["AL-08_evidence_floor_cbe_kg"],
                    "v3_source": old["source"],
                    "v3_c1_branch_note": old["c1_branch"] + " - resolved: cathode-feed PFCV removed and the second latch "
                                         "is the second series flight Xe isolation valve (mass_power_a9_v4 AFI-01; A9.25 "
                                         "message 8)",
                    "AL-08_owner_allocation_kg_row54": old["history"]["AL-08_owner_allocation_kg_row54"]}}


def _sub(text: str, old: str, new: str, count: int, what: str, log: list) -> str:
    n = text.count(old)
    if n != count:
        raise Rev1Error(f"substitution '{what}': expected {count} occurrence(s), found {n}")
    log.append({"what": what, "count": n})
    return text.replace(old, new)


def rev1_section(m8: dict, al: dict) -> list:
    L = ["## Revision rev1 (A9.25 message 8 section 5) - read first", "",
         f"This is **RFQ3-GAS rev1**, the GAS-only successor of the authorized RFQ3-GAS v3 package "
         f"(`{PINS['V3_GAS_PKG'][0]}`, sha256 `{PINS['V3_GAS_PKG'][1]}`, preserved unchanged). Everything below this "
         "section is the v3 text with the controlled rev1 substitutions listed in "
         f"`{JSON_REL}`; no line, quantity or other requirement changes.", "",
         "**Current AL-08 planning context** (replaces the v3 'AL-08 MEV 6.0528 kg / CBE 5.044 kg' context, now HISTORY):",
         "",
         f"- AL-08 CBE planning floor = **{al['cbe_kg']:g} kg**; AL-08 MEV planning floor = **{al['mev_kg']:g} kg** "
         f"(source `{MP4}`).",
         f"- Status **{AL08_PROVISIONAL}**: plumbing remains TBD; mounting/thermal remains TBD; quotations still "
         "replace / re-base the provisional component floors.",
         f"- **{al['mev_kg']:g} kg is an INTERNAL planning floor. It is NOT a supplier maximum-mass requirement.** "
         "Suppliers state their offered component masses.", "",
         "**Supplier quotation split** (state mass, envelope, power, lead time, qualification / heritage status, "
         "compliance per requirement id and datasheets SEPARATELY per category; NOT OFFERED where not offered):", ""]
    L += [f"- {cat}: {', '.join(lines)} - {booking}" for cat, lines, booking in SPLIT]
    L += ["", "C1-specific quotation lines remain **GROUND_ONLY_LAB_EQUIPMENT** and are never included in flight AL-08.",
          "Carried wording 'high-pressure Xe/cathode branch' (RFQ2-GAS-R23 / RFQ2-GAS-N07) is read as the flight "
          "high-pressure Xe path (two series isolation latches, owner row 55); no cathode branch exists in flight.", "",
          "**Dispatch** (" + DISPATCH["v3_rfq3_gas_dispatch_status"] + "): if RFQ3-GAS v3 has NOT been sent externally, "
          "the owner dispatches only this successor package; if it HAS been sent, v3 is preserved and this revision is "
          "issued as the controlled addendum `" + ADDENDUM_REL + "`. The other five authorized packages are unchanged.",
          "", "**QUOTATION ONLY - NO PURCHASE, NO COMMITMENT** (not authorized: " + ", ".join(NOT_AUTHORIZED) + ").",
          ""]
    return L


def build_package(m8: dict, al: dict, r28: dict, log: list) -> str:
    t = _text(PINS["V3_GAS_PKG"][0])
    old_v = r28["value"]
    t = _sub(t, json.dumps(old_v, ensure_ascii=False), json.dumps(new_r28_value(old_v, al), ensure_ascii=False), 4,
             "RFQ2-GAS-R28 mass-context value (v3 AL-08 6.0528 / 5.044 kg -> mass_power_a9_v4 4.929 / 5.9148 kg)", log)
    why = r28["change_v3"]["why"]
    t = _sub(t, why, why + "; rev1 (A9.25 message 8 section 5): this v3 context (6.0528 / 5.044 kg) is HISTORY - the "
                     "current AL-08 context is the rev1 RFQ2-GAS-R28 value", 1,
             "RFQ2-GAS-R28 v3 change note labelled history", log)
    t = _sub(t, R23_OLD, R23_NEW, 2, "'Xe/cathode branch' wording (RFQ2-GAS-R23 / RFQ2-GAS-N07) given the rev1 reading",
             log)
    t = _sub(t, "# RFQ3-GAS - Gas/metrology package\n",
             "# RFQ3-GAS rev1 - Gas/metrology package (successor revision of RFQ3-GAS v3)\n", 1, "title", log)
    gen_old = (f"Generated by `{PINS['V3_BUILDER'][0]}` from `{PINS['V3_JSON'][0]}`; do not edit by hand. Revision of "
               "the immutable v2 packages (`docs/procurement/rfq_a9_v2/`, v2 package RFQ2-GAS).\n")
    gen_new = (f"Generated by `{SCRIPT_REL}` from the pinned RFQ3-GAS v3 text (`{PINS['V3_GAS_PKG'][0]}`) with the "
               f"controlled rev1 substitutions recorded in `{JSON_REL}`; do not edit by hand. v3 lineage: revision of the "
               "immutable v2 packages (`docs/procurement/rfq_a9_v2/`, v2 package RFQ2-GAS).\n\n"
               + "\n".join(rev1_section(m8, al)))
    t = _sub(t, gen_old, gen_new, 1, "provenance line + 'Revision rev1' section", log)
    # fail closed: the v3 values may survive only inside explicitly labelled history
    for tok in ("6.0528", "5.044"):
        for ln in t.splitlines():
            if tok in ln and "HISTORY" not in ln:
                raise Rev1Error(f"v3 value {tok} appears outside labelled history: {ln[:120]}")
    return t


def build_cover(log: list) -> str:
    t = _text(PINS["V3_GAS_COVER"][0])
    t = _sub(t, "# Request for quotation - cover note - RFQ3-GAS (Gas/metrology package)\n",
             "# Request for quotation - cover note - RFQ3-GAS rev1 (Gas/metrology package, successor revision)\n", 1,
             "cover title", log)
    t = _sub(t, f"Generated by `{PINS['V3_BUILDER'][0]}` from `{PINS['V3_JSON'][0]}`; do not edit by hand.\n",
             f"Generated by `{SCRIPT_REL}` from the pinned RFQ3-GAS v3 cover note (`{PINS['V3_GAS_COVER'][0]}`) with "
             f"the controlled rev1 substitutions recorded in `{JSON_REL}`; do not edit by hand.\n\n"
             "**Revision rev1 (A9.25 message 8 section 5).** Dispatch rule: if RFQ3-GAS v3 has NOT been sent "
             "externally, send only this successor (rev1) package; if v3 HAS been sent, v3 stays as sent and the "
             f"controlled addendum `{ADDENDUM_REL}` is issued instead of this cover note. The repository does not know "
             "whether v3 was sent (v3 record: AUTHORIZED_PENDING_OWNER_SEND).\n", 1, "cover provenance + dispatch rule",
             log)
    t = _sub(t, "- RFQ reference: RFQ3-GAS (package revision v3)\n",
             "- RFQ reference: RFQ3-GAS (package revision rev1, successor of v3)\n", 1, "cover RFQ reference", log)
    t = _sub(t, f"package RFQ3-GAS (`{PINS['V3_GAS_PKG'][0]}`)", f"package RFQ3-GAS rev1 (`{PKG_REL}`)", 1,
             "cover package path", log)
    return t


def build_addendum(m8: dict, al: dict, pkg_sha: str) -> str:
    L = ["# Controlled addendum - RFQ3-GAS rev1 to RFQ3-GAS v3 (Gas/metrology package)", "",
         f"Generated by `{SCRIPT_REL}`; do not edit by hand. Issued ONLY if RFQ3-GAS v3 has already been sent "
         "externally (A9.25 message 8 section 5); otherwise the successor package itself is sent and this addendum is "
         "not used.", "",
         "**QUOTATION ONLY - NO PURCHASE, NO COMMITMENT.** Not authorized: " + ", ".join(NOT_AUTHORIZED) + ".", "",
         f"Applies to: RFQ3-GAS v3 (`{PINS['V3_GAS_PKG'][0]}`, sha256 `{PINS['V3_GAS_PKG'][1]}`), which remains valid "
         "except as stated here. Full successor text: "
         f"`{PKG_REL}` (sha256 `{pkg_sha}`).", "",
         "## 1. AL-08 mass context (supersedes RFQ2-GAS-R28 / RFQ-07-R10 of v3)", "",
         f"- The v3 values AL-08 MEV 6.0528 kg / CBE 5.044 kg are withdrawn as current planning values (history only).",
         f"- Current: AL-08 CBE planning floor = {al['cbe_kg']:g} kg; AL-08 MEV planning floor = {al['mev_kg']:g} kg; "
         f"{AL08_PROVISIONAL} (plumbing TBD; mounting/thermal TBD; quotations replace / re-base provisional "
         "component floors).",
         f"- {al['mev_kg']:g} kg is an INTERNAL planning floor, NOT a supplier maximum-mass requirement. Please state "
         "the offered mass of every component.", "",
         "## 2. Quotation split (unchanged in substance; restated)", ""]
    L += [f"- {cat}: {', '.join(lines)} - {booking}" for cat, lines, booking in SPLIT]
    L += ["", "C1-specific lines remain GROUND_ONLY_LAB_EQUIPMENT (separate offer section) and are never part of the "
              "flight Xe hardware (AL-08).", "",
          "## 3. Wording clarification", "",
          "Where RFQ2-GAS-R23 / RFQ2-GAS-N07 say 'high-pressure Xe/cathode branch', read: the flight high-pressure Xe "
          "path with two independent isolation latches in series (owner row 55). There is no cathode branch in the "
          "flight system.", "",
          "## 4. Unchanged", "",
          "All lines, quantities, other requirements, response items and the quotation-only terms of RFQ3-GAS v3 are "
          "unchanged. The other packages (RFQ3-RF, RFQ3-VAC, RFQ3-HALLEL, RFQ3-MECH, RFQ3-RFMET) are unchanged.", "",
          "## Addressing (owner to complete before sending)", "",
          "- To: OWNER TO FILL (the recipients of RFQ3-GAS v3)", "- RFQ reference: RFQ3-GAS rev1 addendum to v3",
          "- Date sent: OWNER TO FILL", ""]
    return "\n".join(L)


def build() -> dict:
    verify_pins()
    m8 = message8()
    r = v3_r28()
    al = mp4_al08()
    log: list = []
    pkg = build_package(m8, al, r["req"], log)
    cover = build_cover(log)
    pkg_sha = hashlib.sha256(pkg.encode("utf-8")).hexdigest()
    add = build_addendum(m8, al, pkg_sha)
    doc = {
        "schema": SCHEMA_ID, "id": "RFQ3_GAS_REV1", "date": DATE, "base_commit": BASE_COMMIT,
        "title": "RFQ3-GAS rev1: GAS-only successor revision of the authorized RFQ v3 gas/metrology package (A9.25 "
                 "message 8 section 5); v3 preserved",
        "status": "AUTHORIZED_PENDING_OWNER_SEND (quotation only; successor of RFQ3-GAS v3)",
        "generated_by": SCRIPT_REL, "companion_document": MD_REL, "test": TEST_REL,
        "decided_by": {k: v for k, v in m8.items() if k != "section_5_verbatim"},
        "owner_section_5_verbatim": m8["section_5_verbatim"],
        "revision_of": {"package": "RFQ3-GAS", "v3_rule": "v3 (authorized RFQ package, A9.24 item 10) is NEVER "
                        "overwritten; read as pinned data",
                        "pins": {k: {"path": p, "sha256": s} for k, (p, s) in PINS.items() if k.startswith("V3_")}},
        "outputs": {"package": PKG_REL, "package_sha256": pkg_sha,
                    "cover_note": COVER_REL, "cover_note_sha256": hashlib.sha256(cover.encode()).hexdigest(),
                    "addendum": ADDENDUM_REL, "addendum_sha256": hashlib.sha256(add.encode()).hexdigest()},
        "current_al08_context": {"AL-08_CBE_planning_floor_kg": al["cbe_kg"], "AL-08_MEV_planning_floor_kg": al["mev_kg"],
                                 "status": AL08_PROVISIONAL, "tbd_floor_constituents": al["tbd"],
                                 "internal_planning_floor_not_supplier_requirement": True,
                                 "source": MP4, "source_sha256_at_build": al["sha256"]},
        "superseded_v3_context": {"AL-08_MEV_planning_floor_kg": V3_EXPECTED["AL-08_MEV_planning_floor_kg"],
                                  "AL-08_evidence_floor_cbe_kg": V3_EXPECTED["AL-08_evidence_floor_cbe_kg"],
                                  "label": "HISTORY - not current"},
        "rfq2_gas_r28_rev1_value": new_r28_value(r["req"]["value"], al),
        "quotation_split": [{"category": c, "lines": ls, "booking": b} for c, ls, b in SPLIT],
        "split_mapping_note": "recorder mapping of the owner's split wording onto the v3 lines (RF3-FLAG-06 carried; "
                              "the owner may re-map); GAS-L11 = series pair (qty 2); GAS-L10 = low-flow FCU",
        "c1_lines": {"lines": SPLIT[-1][1], "status": "GROUND_ONLY_LAB_EQUIPMENT", "in_flight_al08": False},
        "dispatch": DISPATCH,
        "authorized_v3_packages": r["authorized"],
        "unchanged_packages": {k: {"package": p[0], "package_sha256": p[1], "cover_note": c[0], "cover_sha256": c[1],
                                   "state": "UNCHANGED"} for k, (p, c) in UNCHANGED.items()},
        "substitutions": log,
        "no_new_numbers": "every number is read from pinned v3 data or mass_power_a9_v4 (cross-checked against A9.25 "
                          "message 8); no price, supplier, PO or selection",
    }
    md = render_md(doc)
    return {JSON_REL: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", MD_REL: md, PKG_REL: pkg,
            COVER_REL: cover, ADDENDUM_REL: add}


def render_md(d: dict) -> str:
    c = d["current_al08_context"]
    L = ["# RFQ3-GAS rev1 - revision record", "",
         f"Generated by `{d['generated_by']}` (do not edit by hand; `--check` verifies). Status `{d['status']}`. Owner "
         f"basis: {d['decided_by']['decision']} message {d['decided_by']['message']} {d['decided_by']['key']} section 5 "
         f"(`{d['decided_by']['md']}`, text sha256 `{d['decided_by']['text_sha256'][:12]}...`). Base commit "
         f"`{d['base_commit']}`. Test `{d['test']}`.", "",
         "RFQ v3 (`docs/procurement/rfq_a9_v3/`) is preserved unchanged; this revision touches RFQ3-GAS only.", "",
         "## Outputs", ""]
    o = d["outputs"]
    L += [f"- successor package `{o['package']}` (sha256 `{o['package_sha256']}`)",
          f"- successor cover note `{o['cover_note']}`",
          f"- controlled addendum (only if v3 was already sent) `{o['addendum']}`", "",
          "## Current AL-08 context", "",
          f"CBE planning floor {c['AL-08_CBE_planning_floor_kg']:g} kg, MEV planning floor "
          f"{c['AL-08_MEV_planning_floor_kg']:g} kg, `{c['status']}` (TBD: {'; '.join(c['tbd_floor_constituents'])}); "
          "internal planning floor, NOT a supplier maximum-mass requirement. Superseded v3 context (history): "
          f"{d['superseded_v3_context']['AL-08_MEV_planning_floor_kg']:g} / "
          f"{d['superseded_v3_context']['AL-08_evidence_floor_cbe_kg']:g} kg.", "",
          "## Quotation split", ""]
    L += [f"- {s['category']}: {', '.join(s['lines'])} - {s['booking']}" for s in d["quotation_split"]]
    L += ["", d["split_mapping_note"] + ".", "", "## Dispatch", ""]
    L += [f"- {k}: {v}" for k, v in d["dispatch"].items()]
    L += ["", "## Unchanged packages", ""]
    L += [f"- {k}: `{v['package']}` (sha256 `{v['package_sha256'][:12]}...`), cover `{v['cover_note']}` - {v['state']}"
          for k, v in d["unchanged_packages"].items()]
    L += ["", "## Controlled substitutions (v3 -> rev1)", ""]
    L += [f"- {s['what']} (x{s['count']})" for s in d["substitutions"]]
    L += ["", "## Owner section 5 (verbatim)", "", "````text", d["owner_section_5_verbatim"], "````", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are up to date; write nothing")
    args = ap.parse_args(argv)
    out = build()
    if args.check:
        bad = [p for p, t in out.items() if not (REPO / p).exists() or (REPO / p).read_text(encoding="utf-8") != t]
        if bad:
            print("STALE: " + ", ".join(bad))
            return 1
        print(f"OK: {len(out)} outputs reproduce")
        return 0
    for p, t in out.items():
        (REPO / p).parent.mkdir(parents=True, exist_ok=True)
        (REPO / p).write_text(t, encoding="utf-8")
    print(f"wrote {len(out)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
