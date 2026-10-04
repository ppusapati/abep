#!/usr/bin/env python3
"""A9.24 AFI-01 mass + power integration v4 (mass_power_a9_v4) - a SUCCESSOR of the immutable mass / power v3.

Lane: A9.24 item 13 follow-on, owner-approved narrow pre-bid corrections (owner messages 2026-10-04, relayed by the
orchestrating session; the read-only cathode-path audit is docs/audits/a9_24_cathode_path_audit_v1.md on branch
lane-a924-cathode, commit b8f39b7, items AFI-01 / AFI-02 / AFI-05). Deterministic; standard library only; no Julia;
well under a second.

v3 (docs/budgets/mass_power_a9_v3/) is pinned by sha256 and read as DATA (its JSON) and as CODE (its builder, imported
only for the unchanged fail-closed rule functions line_mev_value / rollup / system_margin / harness_row60 /
closure_state); v3 is never edited. v4 = v3 with exactly these changes:

  * AFI-01 (AL-08 cathode-feed re-base): the AL-08 planning floor (A9.14 MQ-05: 5.044 kg CBE floor = H2-7 H27-09 tank
    3.5 + H27-11 regulator 0.974 + H27-12 valves 0.57 kg) embeds the H2-7 two-branch Xe metering set (H27-31: 2
    branches, A5 'Xe metering (splits to ignition/transition feed and cathode feed)'; H27-32: latch + PFCV per branch,
    single string). Under hall_icp_neutralizer (A9.19: no conventional hollow cathode; A9.20: C1 ground-only; ICP feed
    G-REUSE, m_Xe,ICP = 0, own flow_control_icp_feed line) the cathode-feed branch has no flight function. Removed: the
    cathode-branch proportional flow-control valve (AN-MOOG-PFCV, 115 g; the A9 flight BOM keeps ONE PFCV, A9B-11, 'one
    branch only in A9 (the C1 cathode-feed branch drops out of flight, OQ-A902-04)'). NOT removed (STOP item, owner
    call): the cathode-branch latch (AN-MOOG-LATCH-18, 170 g): owner row 55 (H27-Q4, the H2-7 single-string question)
    requires 'dual series isolation on the high-pressure Xe path', the current A9 flight BOM books two series latches
    (A9B-10, 0.34 kg) and F9 carries AFC-UP-VF-07 as FREEZE_CANDIDATE, so without the second latch the floor would fall
    below the A9 flight valve set (0.455 kg, mass_a9 MA9-ID-04). Result: valves 0.57 -> 0.455 kg, AL-08 CBE floor
    5.044 -> 4.929 kg, MEV planning floor 6.0528 -> 5.9148 kg (x 1.20, row 57 / MQ-05 rule unchanged). Tank, regulator,
    plumbing and mounting/thermal (TBD, pending) are unchanged. The floor stays a PROVISIONAL planning floor
    (quotations / design replace it; A9.21).
  * the dry / wet roll-ups are recomputed exactly as v3 (v3 rollup(): MEV reading, harness row 60 = 0.05/0.95 x the
    non-harness known part, 20 % system margin on the CURRENT pre-margin sum (MQ-02), no reserve, LOADED Xe cases
    2 / 5 / 10 kg with the residual inside (MQ-09), references HARD_40_WET < 40, INTERNAL_34 / 36 <=, no margin
    relaxation (MQ-10)); the v3 roll-up is first reproduced bit for bit from the v3 lines (identity check).
  * AFI-02 (label only, no number): AL-07 keeps the owner's 6.0 kg MEV planning floor (MQ-04, 5.0 kg SETS PPU analog)
    and is labelled PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR / CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_
    ARCHITECTURE / REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE with an open re-base action.
  * C1 status wording: the current statuses read C1 = GROUND_REFERENCE_ONLY; the A9.2 'CONTROL_FALLBACK' is kept only
    as a labelled historical quote.

Nothing else changes: every other line, the retired C1 history column, BOM, power, Xe import and owner citations are
v3's (copied from the pinned JSON).

    python docs/budgets/mass_power_a9_v4/build_mass_power_a9_v4.py          # (re)write JSON and Markdown
    python docs/budgets/mass_power_a9_v4/build_mass_power_a9_v4.py --check  # exit 1 unless reproduced byte for byte
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LANE_REL = "docs/budgets/mass_power_a9_v4"
SCRIPT_REL = LANE_REL + "/build_mass_power_a9_v4.py"
JSON_NAME = "mass_power_a9_v4.json"
MD_NAME = "MASS_POWER_A9_V4.md"
TEST_REL = "tests/test_mass_power_a9_v4.py"
SCHEMA_ID = "mass_power_a9_v4"
BASE_COMMIT = "46f7060a34200f9c72384c795311fc551f6ea17a"
DATE = "2026-10-04"
FLIGHT = "hall_icp_neutralizer"

# immutable inputs (read as data / code, never edited)
PINS = {
    "V3_JSON": ("docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json",
                "96764681d13d05f2f566ec04417049c65f1116955ba91870a7d3a713c0d5098a"),
    "V3_MD": ("docs/budgets/mass_power_a9_v3/MASS_POWER_A9_V3.md",
              "ad663ece1a3b0cfde70c88b4df7ab6c647502cb300a7bb68d369df1bd94cade3"),
    "V3_BUILDER": ("docs/budgets/mass_power_a9_v3/build_mass_power_a9_v3.py",
                   "b1df7537456d5334e8b051bb6ed9bca9626933497b3b52e916c9997338e6a572"),
    "H2_7": ("docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
             "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630"),
    "MASS_A9": ("docs/budgets/mass_a9/mass_a9_v1.json",
                "071b03fb634c6b25ef422e7ec81006d337e6c333b80133240bdea32999a4f7d4"),
    "ANSWERS_147": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
                    "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "A9_19": ("docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16"),
    "A9_20": ("docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6"),
    "A9_24_MD": ("docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md", None),
}
AUDIT = {"path": "docs/audits/a9_24_cathode_path_audit_v1.md", "commit": "b8f39b7", "branch": "lane-a924-cathode",
         "items": ["AFI-01", "AFI-02", "AFI-05"],
         "note": "read-only audit (not on this branch); cited by commit, never read by this builder"}
AUTHORIZATION = {
    "source": "owner messages 2026-10-04 (owner-approved narrow pre-bid corrections: AFI-01 AL-08 re-base, AFI-05 "
              "RVM-16 wording, C1 CONTROL_FALLBACK wording; AL-07 6.0 kg analog NOT reduced, label only)",
    "record_status": "OWNER_MESSAGE_RELAYED_BY_ORCHESTRATING_SESSION_NOT_IN_REPOSITORY (no verbatim decision file "
                     "exists in the repository for these messages; the governing standing records are A9.19, A9.20, "
                     "A9.21 AL08 and A9.24 item 13)",
    "supersedes_for_al08": "A9.21 KEEP_6_05KG_PROVISIONAL_WAIT_FOR_QUOTES_TO_REBASE_AL08 is applied only to the "
                           "cathode-branch part identified from the repository (the floor stays provisional; quotations "
                           "still re-base the rest)"}

# AFI-01 re-base (masses are read from the pinned H2-7 analog data; never typed here)
LATCH, PFCV = "AN-MOOG-LATCH-18", "AN-MOOG-PFCV"
OLD_VALVES = {"what": "Xe valves (H2-7 H27-12, 2 x (latch + PFCV))", "kg": 0.57}
OLD = {"floor_cbe_kg": 5.044, "mev_kg": 6.0528}
EXPECTED_NEW = {"valves_kg": 0.455, "floor_cbe_kg": 4.929, "mev_kg": 5.9148}     # cross-check of the arithmetic
STOP_LATCH_ALT = {"valves_kg": 0.285, "floor_cbe_kg": 4.759, "mev_kg": 5.7108}   # NOT applied (owner call)

C1_CURRENT = ("GROUND_REFERENCE_ONLY (A9.20 C1_GROUND_ONLY_LABORATORY_REFERENCE; A9.24 item 13: no C1 flight "
              "fallback; C1 never enters flight architecture, mass, power, Xe, thermal closure or a fallback flight "
              "configuration)")
AL07_LABELS = ["PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR",
               "CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE",
               "REBASE_REQUIRED_FROM_CURRENT_LOAD_CONVERTER_CBE"]


class PinError(RuntimeError):
    """A pinned immutable input does not match its recorded sha256."""


class RebaseError(ValueError):
    """The re-base arithmetic, a source value or the v3 identity check does not hold (fail closed)."""


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def verify_pins() -> None:
    bad = [f"{p} (expected {s[:12]}, got {_sha(p)[:12]})" for p, s in PINS.values() if s and _sha(p) != s]
    if bad:
        raise PinError("pinned immutable inputs changed: " + "; ".join(bad))


def _load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def v3_module():
    spec = importlib.util.spec_from_file_location("build_mass_power_a9_v3_pinned", REPO / PINS["V3_BUILDER"][0])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _answer(rows: dict, n: int, token: str) -> dict:
    r = rows[n]
    if token not in r["owner_answer_verbatim"]:
        raise RebaseError(f"owner row {n}: token {token!r} not in the verbatim answer")
    return {"row": n, "covers_ids": r["covers_ids"], "owner_answer_verbatim": r["owner_answer_verbatim"],
            "path": PINS["ANSWERS_147"][0], "sha256": PINS["ANSWERS_147"][1]}


def sources() -> dict:
    """Every source value the re-base uses, read from pinned files and checked (fail closed)."""
    h27 = _load(PINS["H2_7"][0])
    an = h27["analog_data"]
    params = {p["id"]: p for p in h27["design_parameters"]}
    for pid, want in (("H27-12", 0.57), ("H27-31", 2), ("H27-32", 2)):
        if params[pid]["value"] != want:
            raise RebaseError(f"H2-7 {pid} = {params[pid]['value']!r}, expected {want}")
    if "cathode feed" not in params["H27-31"]["source"][0]:
        raise RebaseError("H2-7 H27-31 no longer names the cathode-feed branch")
    g = {k: an[k]["value"] / 1000.0 for k in (LATCH, PFCV)}
    if any(an[k]["unit"] != "g" for k in (LATCH, PFCV)) or g != {LATCH: 0.17, PFCV: 0.115}:
        raise RebaseError(f"H2-7 valve analogs changed: {g}")
    ma9 = _load(PINS["MASS_A9"][0])
    fl = {x["id"]: x for x in ma9["a9_flight_bom"]["flight"]}
    c1 = {x["id"]: x for x in ma9["a9_flight_bom"]["c1_dropped_from_flight"]}
    ida = {x["id"]: x for x in ma9["interface_demands"]}
    if (fl["A9B-10"]["value"], fl["A9B-11"]["value"], c1["A9B-C04"]["value"], ida["MA9-ID-04"]["value"]) != \
            (0.34, 0.115, 0.285, 0.455):
        raise RebaseError("mass_a9 A9B-10 / A9B-11 / A9B-C04 / MA9-ID-04 values changed")
    rows = {r["row"]: r for r in _load(PINS["ANSWERS_147"][0])["answers"]}
    a919 = _load(PINS["A9_19"][0])
    a920 = _load(PINS["A9_20"][0])
    md24 = " ".join((REPO / PINS["A9_24_MD"][0]).read_text(encoding="utf-8").split())
    for tok in ("hall_icp_neutralizer", "C1 flight fallback", "conventional hollow cathode"):
        if tok not in md24:
            raise RebaseError(f"A9.24 item 13 token {tok!r} missing")
    return {
        "latch_kg": g[LATCH], "pfcv_kg": g[PFCV], "h27": params, "analogs": {k: an[k] for k in (LATCH, PFCV)},
        "A9B-10": fl["A9B-10"], "A9B-11": fl["A9B-11"], "A9B-C04": c1["A9B-C04"], "MA9-ID-04": ida["MA9-ID-04"],
        "row55": _answer(rows, 55, "dual series isolation on the high-pressure Xe path"),
        "row90": _answer(rows, 90, "two independent isolation valves in series"),
        "a9_19_architecture": a919["architecture"], "a9_20_answer": a920["answer"],
    }


def rk(x):
    return float(f"{x:.10g}")


def _split_and_refs(v3: dict):
    roll = next(r for r in v3["rollups"] if r["configuration"] == FLIGHT)
    split, refs = {}, []
    for w in roll["wet"]:
        split[w["xe_case_kg"]] = {"loaded_kg": w["xe_loaded_kg"], "residual_kg": w["residual_inside_case_kg"]}
        ref = (w["reference"], w["reference_kg"], w["comparator"] == "<")
        if ref not in refs:
            refs.append(ref)
    return split, refs, roll


def rebase_al08(line: dict, src: dict, m) -> tuple[dict, dict]:
    """AFI-01: new AL-08 flight line + the full old -> new record."""
    if line["line"] != "AL-08" or line["evidence_floor_cbe_kg"] != OLD["floor_cbe_kg"] or \
            line["value"]["value_kg"] != OLD["mev_kg"]:
        raise RebaseError("v3 AL-08 is not the 5.044 / 6.0528 kg record this re-base was derived from")
    cons = line["floor_constituents"]
    idx = [i for i, c in enumerate(cons) if c["what"] == OLD_VALVES["what"] and c["kg"] == OLD_VALVES["kg"]]
    if len(idx) != 1:
        raise RebaseError("v3 AL-08 valve constituent not found exactly once")
    latch, pfcv = src["latch_kg"], src["pfcv_kg"]
    if rk(2 * (latch + pfcv)) != OLD_VALVES["kg"]:
        raise RebaseError("H2-7 H27-12 = 2 x (latch + PFCV) no longer reproduces 0.57 kg")
    kept = [
        {"what": "Xe isolation latch, anode / Xe-contingency feed branch (H2-7 H27-12 branch 1; AN-MOOG-LATCH-18)",
         "kg": latch, "evidence_class": "inferred", "status": "RETAINED (flight function: Xe contingency / emergency "
         "feed to the Hall anode, A9.19; A9B-10)", "source_ids": ["H27-12", "H27-31", LATCH, "A9B-10"]},
        {"what": "Xe proportional flow-control valve, anode / Xe-contingency feed branch (H2-7 H27-12 branch 1; "
                 "AN-MOOG-PFCV)", "kg": pfcv, "evidence_class": "inferred",
         "status": "RETAINED (A9B-11 'Xe anode-feed proportional flow control'; one PFCV in the A9 flight BOM)",
         "source_ids": ["H27-12", "H27-31", PFCV, "A9B-11"]},
        {"what": "Xe isolation latch from the H2-7 cathode-feed branch, retained as the second series isolation valve "
                 "on the high-pressure Xe path (AN-MOOG-LATCH-18)", "kg": latch, "evidence_class": "inferred",
         "status": "RETAINED_PENDING_OWNER (STOP item AFI-01-S1: H2-7 placed it on the cathode branch, but owner row "
                   "55 requires dual series isolation on the high-pressure Xe path and the A9 flight BOM books two "
                   "series latches, A9B-10; removing it is an owner call)",
         "source_ids": ["H27-12", "H27-31", "H27-32", LATCH, "A9B-10", "row 55", "AFC-UP-VF-07"]},
    ]
    removed = [{"what": "Xe proportional flow-control valve of the H2-7 cathode-feed branch (AN-MOOG-PFCV)",
                "kg": pfcv, "evidence_class": "inferred", "source_ids": ["H27-12", "H27-31", PFCV, "A9B-C04"],
                "reason": "exists solely to meter Xe to the conventional hollow cathode (H2-7 H27-31: 'Xe metering "
                          "(splits to ignition/transition feed and cathode feed)'); no flight function in "
                          "hall_icp_neutralizer (A9.19: no conventional hollow cathode; A9.20: C1 ground-only; ICP feed "
                          "G-REUSE m_Xe,ICP = 0 with its own flow_control_icp_feed line); the A9 flight BOM already "
                          "keeps one PFCV only (A9B-11, OQ-A902-04)"}]
    valves = rk(sum(c["kg"] for c in kept))
    other = [c for i, c in enumerate(cons) if i != idx[0]]
    floor = rk(sum(c["kg"] for c in other if c["kg"] is not None) + valves)
    mev = m.line_mev_value(line["row54_allocation_kg"], None, floor)
    new_vals = {"valves_kg": valves, "floor_cbe_kg": floor, "mev_kg": mev["value_kg"]}
    if new_vals != EXPECTED_NEW:
        raise RebaseError(f"re-base arithmetic {new_vals} != {EXPECTED_NEW}")
    if mev["governs"] != "MEV_PLANNING_FLOOR":
        raise RebaseError("AL-08 MEV is no longer governed by the planning floor")
    new = copy.deepcopy(line)
    new_cons = copy.deepcopy(other)
    new_cons[idx[0]:idx[0]] = [{"what": "Xe valves (re-based, mass_power_a9_v4 AFI-01): retained set "
                                        "1 x latch + 1 x PFCV (anode / Xe-contingency feed) + 1 x latch (second series "
                                        "HP isolation, pending owner)", "kg": valves, "evidence_class": "inferred",
                                "status": None, "parts": kept}]
    tank, reg = (c["kg"] for c in other[:2])
    new.update(
        evidence_floor_cbe_kg=floor, floor_constituents=new_cons,
        floor_arithmetic=(f"floor = {tank:g} + {reg:g} + {valves:g} = {floor:g} kg (v4 AFI-01: H2-7 H27-12 0.57 kg "
                          f"minus the cathode-feed PFCV {pfcv:g} kg) > allocation {line['row54_allocation_kg']:g} kg; "
                          f"plumbing, mounting/thermal TBD (pending). v3 arithmetic (history): "
                          + line["floor_arithmetic"]),
        owner_mev_planning_floor_kg=None,
        owner_mev_planning_floor_kg_v3=OLD["mev_kg"],
        rebase_rule=("complete Xe storage/flow hardware (MQ-05 scope unchanged); MEV planning floor = 1.20 x the "
                     f"re-based {floor:g} kg CBE floor = {mev['value_kg']:g} kg (v3: owner-stated 6.0528 kg from "
                     "5.044 kg); quotations/design replace it"),
        a9_21_status=("PROVISIONAL_PLANNING_FLOOR_NOT_FROZEN (A9.21 AL08): the AL-08 MEV planning floor stays a "
                      "provisional planning floor, not a frozen allocation; v4 removes only the C1 cathode-feed PFCV "
                      "identified from the repository (AFI-01, owner messages 2026-10-04); quotations still split tank, "
                      "regulator, valves, plumbing and mounting/thermal before the final re-base"),
        value=mev,
        evidence_class_of_value=("MEV planning floor = 1.20 x re-based analog floor (not a CBE); constituent classes "
                                 "inferred"))
    new["owner_answers_applied"] = line["owner_answers_applied"] + [
        f"owner row 55 ({PINS['ANSWERS_147'][0]} sha256 {PINS['ANSWERS_147'][1][:12]})",
        "AFI-01 owner-approved re-base (owner messages 2026-10-04; record status "
        "OWNER_MESSAGE_RELAYED_BY_ORCHESTRATING_SESSION_NOT_IN_REPOSITORY)"]
    record = {
        "id": "AFI-01", "line": "AL-08", "configuration": FLIGHT,
        "old": {"valves_kg": OLD_VALVES["kg"], "floor_cbe_kg": OLD["floor_cbe_kg"], "mev_kg": OLD["mev_kg"],
                "valve_basis": "H2-7 H27-12 = H27-31 (2 branches) x H27-32 (latch + PFCV) = 2 x (0.170 + 0.115) kg"},
        "new": new_vals,
        "delta": {"cbe_kg": rk(floor - OLD["floor_cbe_kg"]), "mev_kg": rk(mev["value_kg"] - OLD["mev_kg"])},
        "al08_terms_v3": [{"what": c["what"], "kg": c["kg"], "evidence_class": c["evidence_class"],
                           "status": c["status"]} for c in cons],
        "removed": removed, "retained_valves": kept,
        "retained_unchanged": ["Xe tank low end 3.5 kg (H27-09)", "Xe regulator low end 0.974 kg (H27-11)",
                               "plumbing, mounting/thermal (TBD, pending; H27-10 / H27-13)"],
        "c1_only_items_found": ["cathode-feed PFCV 0.115 kg (removed)"],
        "c1_only_items_beyond_expected": [],
        "stop_items": [{
            "id": "AFI-01-S1", "item": "cathode-feed-branch isolation latch (AN-MOOG-LATCH-18, 0.170 kg)",
            "state": "RETAINED_PENDING_OWNER",
            "why": "the expected removal (one latch + one PFCV = 0.285 kg, A9B-C04) would leave a single latch on the "
                   "high-pressure Xe path; owner row 55 (H27-Q4, the question that the H2-7 single-string set H27-32 "
                   "left open) requires 'dual series isolation on the high-pressure Xe path', the A9 flight BOM books "
                   "two series latches (A9B-10, 0.34 kg) plus one PFCV (A9B-11) = 0.455 kg (MA9-ID-04), and F9 "
                   "AFC-UP-VF-07 carries that rule as FREEZE_CANDIDATE. Whether the H2-7 cathode-branch latch is "
                   "C1-only (then a row-55 second latch must be booked instead: same 0.455 kg) or removed outright is "
                   "an owner call, not made here",
            "if_owner_removes": dict(STOP_LATCH_ALT, note="AL-08 CBE 4.759 kg, MEV 5.7108 kg (the 0.285 kg reading); "
                                                          "the valve set would then be below the A9 flight valve set "
                                                          "0.455 kg required by row 55")}],
        "sources": {"H27": {k: {"value": src["h27"][k]["value"], "name": src["h27"][k]["name"],
                                "source": src["h27"][k]["source"]} for k in ("H27-12", "H27-31", "H27-32")},
                    "analogs": {k: {"value_g": v["value"], "device": v["device"], "source": v["source"],
                                    "locator": v["locator"]} for k, v in src["analogs"].items()},
                    "mass_a9": {k: {"name": src[k]["name"], "value_kg": src[k]["value"],
                                    "status": src[k].get("status")} for k in ("A9B-10", "A9B-11", "A9B-C04")},
                    "MA9-ID-04": {"quantity": src["MA9-ID-04"]["quantity"], "value_kg": src["MA9-ID-04"]["value"]},
                    "owner_row_55": src["row55"], "owner_row_90": src["row90"],
                    "a9_19_architecture": src["a9_19_architecture"], "a9_20_answer": src["a9_20_answer"]},
        "authorization": AUTHORIZATION, "audit": AUDIT,
    }
    return new, record


def label_al07(line: dict) -> dict:
    """AFI-02: label only; the owner's 6.0 kg MEV planning floor (MQ-04) is NOT reduced."""
    if line["line"] != "AL-07" or line["value"]["value_kg"] != 6.0:
        raise RebaseError("v3 AL-07 is not the 6.0 kg owner MEV planning floor")
    new = copy.deepcopy(line)
    new["afi_02_labels"] = list(AL07_LABELS)
    new["afi_02_status"] = (
        "PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR: the 6.0 kg MEV planning floor (A9.14 MQ-04: 5.0 kg lowest "
        "admissible Hall-thruster PPU analog, SETS) is kept unchanged (owner 2026-10-04: do not reduce); the analog "
        "scope CONTAINS_LEGACY_FUNCTIONS_NOT_PRESENT_IN_CURRENT_FLIGHT_ARCHITECTURE (conventional-cathode heater / "
        "keeper supplies; v2: 'the C1 supplies (A9B-C03) sit inside the AL-07 PPU analogs') and omits the RF "
        "generator / matching that hall_icp_neutralizer needs (booked on AL-06); REBASE_REQUIRED_FROM_CURRENT_LOAD_"
        "CONVERTER_CBE (flight PPU CBE x 1.20 from the current load / converter list, MQ-04 'replace')")
    new["open_rebase_action"] = {"id": "AFI-02-RA1", "state": "OPEN",
                                 "action": "re-base AL-07 on the current hall_icp_neutralizer load / converter CBE "
                                           "(or a cathodeless PPU quotation, RFQ3-HALLEL); until then the 6.0 kg owner "
                                           "floor governs", "owner": "owner / PPU design", "number_changed": False}
    return new


def build_doc() -> dict:
    verify_pins()
    v3 = _load(PINS["V3_JSON"][0])
    m = v3_module()
    src = sources()
    split, refs, roll_v3 = _split_and_refs(v3)
    lines_v3 = v3["lines"][FLIGHT]
    # identity: the pinned v3 functions reproduce the committed v3 flight roll-up from the committed v3 lines
    again = m.rollup(FLIGHT, copy.deepcopy(lines_v3), split, refs)
    if {k: v for k, v in again.items() if k != "note"} != {k: v for k, v in roll_v3.items() if k != "note"}:
        raise RebaseError("v3 roll-up identity check failed: v3 rollup() does not reproduce the committed v3 roll-up")
    lines = []
    record = None
    for ln in lines_v3:
        if ln["line"] == "AL-08":
            ln, record = rebase_al08(ln, src, m)
        elif ln["line"] == "AL-07":
            ln = label_al07(ln)
        lines.append(ln)
    roll = m.rollup(FLIGHT, copy.deepcopy(lines), split, refs)
    roll["note"] = roll_v3["note"] + "; v4: AL-08 re-based (AFI-01)"

    d = copy.deepcopy(v3)
    hard = {str(w["xe_case_kg"]): w for w in roll["wet"] if w["reference"] == "HARD_40_WET"}
    hard_v3 = {str(w["xe_case_kg"]): w for w in roll_v3["wet"] if w["reference"] == "HARD_40_WET"}
    changes = [{"quantity": "AL-08 CBE floor (kg)", "old": OLD["floor_cbe_kg"], "new": record["new"]["floor_cbe_kg"]},
               {"quantity": "AL-08 MEV planning floor (kg)", "old": OLD["mev_kg"], "new": record["new"]["mev_kg"]}]
    for k in ("nonharness_known_kg", "harness_kg", "nominal_dry_known_kg", "system_margin_kg", "dry_known_kg"):
        changes.append({"quantity": k, "old": roll_v3[k], "new": roll[k]})
    for c in sorted(hard, key=float):
        changes.append({"quantity": f"wet_known_kg at {c} kg loaded Xe (HARD_40_WET)", "old": hard_v3[c]["wet_known_kg"],
                        "new": hard[c]["wet_known_kg"], "state_old": hard_v3[c]["state"], "state_new": hard[c]["state"]})
    for w_old, w_new in zip(roll_v3["wet"], roll["wet"]):
        for k in ("exceedance_kg", "margin_to_reference_kg"):
            if k in w_old or k in w_new:
                changes.append({"quantity": f"{k} ({w_new['reference']}, {w_new['xe_case_kg']:g} kg Xe)",
                                "old": w_old.get(k), "new": w_new.get(k), "state_old": w_old["state"],
                                "state_new": w_new["state"]})
        ro, rn = w_old.get("redesign_need") or {}, w_new.get("redesign_need") or {}
        if ro or rn:
            changes.append({"quantity": f"non-harness nominal reduction needed ({w_new['reference']}, "
                                        f"{w_new['xe_case_kg']:g} kg Xe)",
                            "old": ro.get("nonharness_nominal_reduction_kg_at_least"),
                            "new": rn.get("nonharness_nominal_reduction_kg_at_least")})
    st = v3["statuses"]
    statuses = {
        "current_statuses": dict(st["a9_2_statuses"], **{"C1 conventional reference": C1_CURRENT}),
        "a9_2_statuses": st["a9_2_statuses"],
        "a9_2_statuses_label": "HISTORICAL_QUOTE (A9.2, 2026-09-30, verbatim): superseded for C1 by A9.19 / A9.20 / "
                               "A9.24 item 13; never a current status (current: current_statuses)",
        "a9_6_fixed_statuses": st["a9_6_fixed_statuses"], "rule": st["rule"],
        "a9_19_20_supersessions": {"C1 conventional reference": C1_CURRENT}}
    items_v4 = [{"id": "MPV4-01", "name": "AL-08 MEV planning floor (complete Xe storage/flow hardware), re-based "
                 "AFI-01", "value": record["new"]["mev_kg"], "units": "kg",
                 "evidence_class": f"planning floor (1.20 x inferred {record['new']['floor_cbe_kg']:g} kg)",
                 "source": ["A9.14 MQ-05 (rule)", "AFI-01 (owner messages 2026-10-04)"],
                 "status": "PLANNING_FLOOR_NOT_CBE (provisional, A9.21)", "replaces": "MPV3-04 (6.0528 kg)"}]
    d.update({
        "schema": SCHEMA_ID, "id": SCHEMA_ID, "lane": "a9_24_afi_pre_bid_corrections",
        "directive": "owner messages 2026-10-04: narrow pre-bid corrections AFI-01 (AL-08 cathode-feed re-base), AFI-02 "
                     "(AL-07 label only), C1 status wording (A9.24 item 13)",
        "title": "A9 mass + power integration v4: v3 with the AL-08 cathode-feed PFCV removed (AFI-01), the AL-07 "
                 "analog-floor label (AFI-02) and C1 = GROUND_REFERENCE_ONLY; roll-ups recomputed exactly as v3",
        "status": "DRAFT_AFI_CORRECTIONS_APPLIED_PENDING_INTEGRATION_VERIFICATION",
        "date": DATE, "base_commit": BASE_COMMIT, "generated_by": SCRIPT_REL,
        "companion_document": f"{LANE_REL}/{MD_NAME}", "test": TEST_REL,
        "revision_of": {"path": PINS["V3_JSON"][0], "sha256": PINS["V3_JSON"][1], "md": PINS["V3_MD"][0],
                        "md_sha256": PINS["V3_MD"][1], "builder": PINS["V3_BUILDER"][0],
                        "builder_sha256": PINS["V3_BUILDER"][1],
                        "rule": "v3 immutable history: read as data (JSON) and code (rule functions), never edited",
                        "v3_revision_of": v3["revision_of"]},
        "statuses": statuses,
        "items_v4": items_v4,
        "lines": {FLIGHT: lines},
        "rollups": [roll],
        "flight_rollup_vs_40kg": [{
            "configuration": FLIGHT, "dry_known_kg": roll["dry_known_kg"],
            "wet_known_kg_by_loaded_case": {c: w["wet_known_kg"] for c, w in hard.items()},
            "hard_40_wet_state_by_loaded_case": {c: w["state"] for c, w in hard.items()},
            "numerically_unchanged_vs_v3": False,
            "v3": {"dry_known_kg": roll_v3["dry_known_kg"],
                   "wet_known_kg_by_loaded_case": {c: w["wet_known_kg"] for c, w in hard_v3.items()}},
            "basis": "v3 rollup() on the v3 lines with AL-08 re-based (AFI-01); every other line is v3's"}],
        "afi_corrections": {"AFI-01": record, "AFI-02": {"line": "AL-07", "labels": AL07_LABELS,
                                                         "number_changed": False,
                                                         "open_rebase_action": "AFI-02-RA1"},
                            "C1_STATUS": {"current": C1_CURRENT, "a9_2_historical_quote": "CONTROL_FALLBACK"},
                            "changes_old_new": changes,
                            "unchanged": "every other line value, the retired C1 history column, BOM, power, Xe "
                                         "import, budget reference and owner citations (copied from pinned v3)"},
        "c1_mass_check": dict(v3["c1_mass_check"],
                              flight_v4="v4 removes the cathode-feed PFCV (0.115 kg CBE) from the AL-08 floor; the "
                                        "cathode-branch latch (0.170 kg) is retained pending owner (row 55 dual series "
                                        "isolation; AFI-01-S1)",
                              flight_numbers_effect="v4: see afi_corrections.changes_old_new (v3 text above is "
                                                    "history)"),
        "recorder_flags": v3["recorder_flags"] + [
            "AFI-01 (v4): the v3 recorder flag on the H2-7 two-branch valve set is answered for the PFCV only; the "
            "cathode-branch latch is the open stop item AFI-01-S1 (owner call)",
            "AFI-02 (v4): AL-07 6.0 kg owner analog floor kept; label PROVISIONAL_CONSERVATIVE_OWNER_ANALOG_FLOOR + "
            "open re-base action AFI-02-RA1"],
    })
    d["open_register_status"] = dict(v3["open_register_status"],
                                     **{"MQ-08": "DERIVED (owner_questions_state_v4; v4: H2-7 arithmetic minus the "
                                                 "cathode-feed PFCV, AFI-01)",
                                        "AFI-01-S1": "OPEN (owner)", "AFI-02-RA1": "OPEN"})
    d["compliance"] = dict(v3["compliance"],
                           no_new_numbers="every number is copied from pinned v3 / H2-7 / mass_a9 or is deterministic "
                                          "arithmetic on those (v3 rule functions)",
                           pure="not wired into archengine; no frozen data, goldens, abep_sim module or v3 file touched")
    return d


# ------------------------------------------------------------------------------------------------ markdown
def _cell(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(headers: list, rows: list) -> list:
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + \
        ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows] + [""]


def render_md(d: dict) -> str:
    a = d["afi_corrections"]["AFI-01"]
    L = ["# A9 mass + power integration v4 (A9.24 AFI pre-bid corrections)", "",
         f"Generated by `{d['generated_by']}` from `{LANE_REL}/{JSON_NAME}` (do not edit by hand; `--check` verifies). "
         f"Status `{d['status']}`. Base commit `{d['base_commit']}`. Successor of `{d['revision_of']['path']}` "
         f"(sha256 `{d['revision_of']['sha256']}`, immutable; every section not listed here is v3's). Test "
         f"`{d['test']}`.", "",
         f"Authorization: {AUTHORIZATION['source']}. Record status `{AUTHORIZATION['record_status']}`.", "",
         "## AFI-01: AL-08 cathode-feed re-base", "",
         "v3 AL-08 terms (CBE floor 5.044 kg, MEV 6.0528 kg):", ""]
    L += _table(["term", "kg", "evidence class", "status"],
                [[t["what"], t["kg"], t["evidence_class"], t["status"]] for t in a["al08_terms_v3"]])
    L += ["Removed:", ""]
    L += _table(["item", "kg (CBE)", "source ids", "reason"],
                [[r["what"], r["kg"], ", ".join(r["source_ids"]), r["reason"]] for r in a["removed"]])
    L += ["Retained valves:", ""]
    L += _table(["item", "kg (CBE)", "source ids", "status"],
                [[r["what"], r["kg"], ", ".join(r["source_ids"]), r["status"]] for r in a["retained_valves"]])
    L += [f"Retained unchanged: {'; '.join(a['retained_unchanged'])}.", "",
          f"New: valves {a['new']['valves_kg']:g} kg, AL-08 CBE floor {a['new']['floor_cbe_kg']:g} kg, MEV planning "
          f"floor {a['new']['mev_kg']:g} kg (delta CBE {a['delta']['cbe_kg']:g} kg, MEV {a['delta']['mev_kg']:g} kg).",
          ""]
    for s in a["stop_items"]:
        L += [f"**STOP item {s['id']}** ({s['state']}): {s['item']}. {s['why']}. If the owner removes it: "
              f"{s['if_owner_removes']['note']}.", ""]
    L += ["## Old -> new (flight configuration `hall_icp_neutralizer`)", ""]
    L += _table(["quantity", "old (v3)", "new (v4)", "state old", "state new"],
                [[c["quantity"], c["old"], c["new"], c.get("state_old"), c.get("state_new")]
                 for c in d["afi_corrections"]["changes_old_new"]])
    L += ["## Lines - `hall_icp_neutralizer`", ""]
    L += _table(["line", "name", "row-54 alloc", "evidence floor (CBE level)", "value used (MEV)", "governs"],
                [[r["line"], r["name"], r["row54_allocation_kg"], r["evidence_floor_cbe_kg"], r["value"]["value_kg"],
                  r["value"]["governs"]] for r in d["lines"][FLIGHT]])
    for r in d["lines"][FLIGHT]:
        if r.get("a9_21_status"):
            L += [f"* **{r['line']}** (A9.21): {r['a9_21_status']}"]
        if r.get("afi_02_status"):
            L += [f"* **{r['line']}** (AFI-02): {r['afi_02_status']}; open action {r['open_rebase_action']['id']}: "
                  f"{r['open_rebase_action']['action']}"]
    L += [""]
    for r in d["rollups"]:
        L += [f"## Evidence-based dry / wet totals vs 40 kg - `{r['configuration']}`", "", r["note"] + ".", "",
              f"non-harness known {r['nonharness_known_kg']:g} kg + harness {r['harness_kg']:g} kg = nominal "
              f"{r['nominal_dry_known_kg']:g} kg; + 20 % system margin {r['system_margin_kg']:g} kg = **dry known "
              f"{r['dry_known_kg']:g} kg** (reserve 0). Lines without a value: {', '.join(r['lines_without_value'])}.",
              ""]
        L += _table(["loaded Xe kg", "residual inside", "wet known kg", "reference", "state", "exceedance kg",
                     "non-harness nominal reduction needed (kg, at least)"],
                    [[w["xe_case_kg"], w["residual_inside_case_kg"], w["wet_known_kg"],
                      f"{w['reference']} ({w['comparator']} {w['reference_kg']:g})", w["state"], w.get("exceedance_kg"),
                      (w.get("redesign_need") or {}).get("nonharness_nominal_reduction_kg_at_least")] for w in r["wet"]])
        L += ["TBD / unresolved terms:", ""] + [f"* {t}" for t in r["tbd"]] + [""]
    L += ["MQ-10: the margin reading is not relaxed; closure requires reducing actual subsystem CBE through redesign, "
          "integration or lighter qualified parts.", "",
          "## Current statuses (C1 = GROUND_REFERENCE_ONLY)", ""]
    L += _table(["item", "current status"], [[k, v] for k, v in d["statuses"]["current_statuses"].items()])
    L += [f"{d['statuses']['a9_2_statuses_label']}: "
          + "; ".join(f"{k} = {v}" for k, v in d["statuses"]["a9_2_statuses"].items()) + ".", "",
          "## Recorder flags", ""] + [f"* {f}" for f in d["recorder_flags"]] + [""]
    return "\n".join(L)


def render():
    doc = build_doc()
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n", render_md(doc))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify outputs are up to date; write nothing")
    args = ap.parse_args(argv)
    js, md = render()
    files = {HERE / JSON_NAME: js, HERE / MD_NAME: md}
    if args.check:
        bad = [p.name for p, t in files.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("STALE: " + ", ".join(bad))
            return 1
        print(f"OK: {len(files)} outputs reproduce")
        return 0
    for p, t in files.items():
        p.write_text(t, encoding="utf-8")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
