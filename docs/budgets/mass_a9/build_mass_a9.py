#!/usr/bin/env python3
"""Deterministic builder of the A9 mass reconciliation (fo_a9_06_mass_reconciliation, trigger T_A9_06_MASS_RECONCILIATION).

Writes
  docs/budgets/mass_a9/mass_a9_v1.json   (machine-readable deliverable)
  docs/budgets/mass_a9/MASS_A9.md        (companion document, rendered from the same data)

Governing owner decisions (immutable, sha256-pinned below; a mismatch aborts the build):
  A9    docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json
  147   docs/decisions/OD_2026_09_29_owner_answers_147.json (+ verbatim pack .md); cited by row number, every cited
        row's verbatim answer is fingerprinted and the quoted fragments are checked against it
  A9.1  docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json (+ verbatim .md); cited by decision id

What it does
  1. A9 flight BOM item list (row 59, A9.1 OQ-A902-04): new ICP-neutralizer / RF / collector-bias items, pre-ionizer-only
     items removed from the A9 BOM (historical mass_bom v1 and H2-7 v1 untouched), C1-specific items dropped from the
     primary flight BOM and kept as ground reference/control or fallback-variant items.
  2. Owner v0 dry allocations (row 54) side by side with verified evidence per line, state per line
     (CONSISTENT / ALLOCATION_BELOW_EVIDENCE_FLOOR / ALLOCATION_UNVERIFIABLE_TBD) with the arithmetic. Owner allocations
     are never changed here; conflicts become owner questions with minimal re-allocation options and their consequence.
  3. Wet-mass closure against < 40 kg wet (row 5) and the 34 / 36 kg internal allocations (row 53) for the Xe load
     design cases 2 / 5 / 10 kg (row 48) under declared readings of the margin rules (rows 52, 57, 60). The 2 % Xe
     residual is booked once in the A9 Xe ledger (row 45) and imported here as PENDING; it is never computed here.
  4. H2-7 v1 interface demands re-evaluated for A9; (5) interface demands to/from A9-07, A9-08, A9-09, A9-10 and H2/H-1.

Rules implemented here
  * every number is an owner-given value (row), a value COPIED from a verified deliverable (path + RFC 6901 JSON pointer
    + sha256, re-checked at build time), deterministic arithmetic on those, or null with 'TBD - requires <what>';
  * parallel A9 lanes (A9-07, A9-08, A9-09) are written 'PENDING <lane path>' and never read;
  * no Hall transport closure, screening candidate, superseded 0-D Hall model or withdrawn number is read; nothing here
    predicts thrust, efficiency, discharge current, neutralizer electron current or plasma state;
  * missing inputs raise (CLAUDE.md rule 3); analog masses are masses of OTHER hardware, not predictions or bounds.

Usage
  python docs/budgets/mass_a9/build_mass_a9.py          # write both files
  python docs/budgets/mass_a9/build_mass_a9.py --check  # exit 1 if either file differs from a fresh build

Standard library only. Pure: reads repository files and writes the two outputs; not wired into archengine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LANE_DIR = "docs/budgets/mass_a9"
OUT_JSON = f"{LANE_DIR}/mass_a9_v1.json"
OUT_MD = f"{LANE_DIR}/MASS_A9.md"
THIS_SCRIPT = f"{LANE_DIR}/build_mass_a9.py"
TEST = "tests/test_mass_a9.py"
BASE_COMMIT = "2625fe567b48c581232bbaf33a057f352f6963e6"

CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
OUTCOME_VOCABULARY = ("hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE")
STATUS_NOT_OUTCOME = ("OPEN",)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
LINE_STATES = ("CONSISTENT", "ALLOCATION_BELOW_EVIDENCE_FLOOR", "ALLOCATION_UNVERIFIABLE_TBD")
CLOSURE_STATES = ("CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE")
TBD = "TBD - requires"

# ----------------------------------------------------------------------------------------------------------------------
# pinned inputs
# ----------------------------------------------------------------------------------------------------------------------
# Immutable owner decisions: expected sha256 fixed here; a mismatch aborts the build.
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"),
    "A91_MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
               "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e"),
    "A4": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
           "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925"),
}
# Verified deliverables this lane copies values from. mass_bom v1 and H2-7 v1 must stay byte-identical (lane brief), so
# their sha256 is fixed; the H2-1 / H2-4 values are copied by pointer and re-checked against the fixed sha256 as well.
PINNED_DELIVERABLES = {
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d"),
    "H24": ("docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
            "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef"),
    "H27": ("docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
            "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630"),
    "MBOM": ("docs/architecture_comparison/mass_bom/mass_bom_v1.json",
             "8ab97ff93f507899508374d4ce8116e7066c31e3fbe2c79300f5b55372ba7313"),
    "MBOM_MD": ("docs/architecture_comparison/mass_bom/MASS_BOM.md",
                "e050e2fb445ca613fac970b0a0cf2664a2f021dab381c5cce11b71d9e2a7387e"),
}
# Verified deliverables read for structure/ids only (sha256 recorded at build time; the test re-checks them).
READ_DELIVERABLES = {
    "H22": "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
    "H23": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
    "H25": "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
    "H26": "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
    "M16": "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
    "BUS_A9": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "ICD_A9": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "PREREG_A9": "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "INT_A9": "docs/experiments/hall_icp/integration/a9_core_integration_v1.json",
}
# Historical artifacts: read for reuse decisions only, never edited.
HISTORICAL = {
    "MBOM": "docs/architecture_comparison/mass_bom/mass_bom_v1.json",
    "MBOM_MD": "docs/architecture_comparison/mass_bom/MASS_BOM.md",
    "H27": "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
    "PIM_JSON": "schemas/interfaces/preionizer_module_icd_v1.json",
    "LEGACY_MGA_PY": "abep_sim/mass_bom.py",
}
# Mutable governance files: referenced by path only, never pinned.
NEVER_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/fired_triggers.jsonl",
    "docs/orchestration/trigger_ledger_v2.jsonl",
    "docs/orchestration/runtime_state.json",
]
# Parallel A9 lanes (not in the base commit): PENDING only, nothing is read from them.
XE_A9 = "docs/budgets/" + "xe" + "_ledger_a9/"
A9_LANES = {
    "A9-07": "docs/hardware/h2_a9_revisions/",
    "A9-08": XE_A9,
    "A9-09": "docs/procurement/rfq_a9/",
    "A9-10": "A9-10 reconciliation lane (no path yet)",
}
XE_V1_DIR = "docs/budgets/" + "xe" + "_ledger/"


def pending(lane: str) -> str:
    return f"PENDING {A9_LANES[lane]} ({lane})"


# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------
def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel)


def sha256_of(rel: str) -> str:
    p = _abs(rel)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"required input missing: {rel}")
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_CACHE: dict = {}


def load(rel: str):
    if rel not in _CACHE:
        p = _abs(rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"required input missing: {rel}")
        with open(p, encoding="utf-8") as f:
            _CACHE[rel] = json.load(f)
    return _CACHE[rel]


def resolve(doc, pointer: str):
    cur = doc
    for tok in pointer.lstrip("/").split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        else:
            if tok not in cur:
                raise KeyError(f"pointer {pointer}: missing '{tok}'")
            cur = cur[tok]
    return cur


def check_pins() -> list:
    pins = []
    for key, (rel, expected) in list(DECISIONS.items()) + list(PINNED_DELIVERABLES.items()):
        got = sha256_of(rel)
        if got != expected:
            raise RuntimeError(f"pinned input {rel} changed: sha256 {got} != pinned {expected}")
        pins.append({"key": key, "path": rel, "sha256": got,
                     "kind": "owner decision (immutable)" if key in DECISIONS else "verified deliverable (byte-identical)"})
    return pins


def answers_by_row() -> dict:
    d = load(DECISIONS["ANS"][0])
    return {int(a["row"]): a for a in d["answers"]}


def answer_fingerprint(row: int) -> str:
    return hashlib.sha256(answers_by_row()[row]["owner_answer_verbatim"].encode("utf-8")).hexdigest()


def require_text(row: int, text: str) -> None:
    verb = answers_by_row()[row]["owner_answer_verbatim"]
    if text not in verb:
        raise RuntimeError(f"owner answer row {row} no longer contains the quoted fragment {text!r}")


def a91(dec_id: str):
    d = load(DECISIONS["A91"][0])["decisions"]
    if dec_id not in d:
        raise KeyError(f"A9.1 decision {dec_id} missing")
    return d[dec_id]


def row_src(*rows: int) -> list:
    ans = answers_by_row()
    return [{"path": DECISIONS["ANS"][0], "row": r, "covers_ids": ans[r]["covers_ids"],
             "answer_sha256": answer_fingerprint(r)} for r in rows]


def a91_src(*ids: str) -> list:
    for i in ids:
        a91(i)
    return [{"path": DECISIONS["A91"][0], "sha256": DECISIONS["A91"][1], "decision": i} for i in ids]


def index_of(lst: list, key: str, val: str) -> int:
    for i, x in enumerate(lst):
        if x.get(key) == val:
            return i
    raise KeyError(f"{key}={val} not found")


def copied(dkey: str, pointer: str, expected) -> dict:
    """Copy a value from a pinned verified deliverable by JSON pointer and assert it equals the expected value."""
    rel = PINNED_DELIVERABLES[dkey][0]
    val = resolve(load(rel), pointer)
    if val != expected:
        raise RuntimeError(f"{rel}{pointer} = {val!r}, expected {expected!r} (verified input changed)")
    return {"value": val, "path": rel, "pointer": pointer, "sha256": PINNED_DELIVERABLES[dkey][1]}


def dp_ptr(dkey: str, pid: str, sub: str = "value") -> str:
    lst = load(PINNED_DELIVERABLES[dkey][0])["design_parameters"]
    return f"/design_parameters/{index_of(lst, 'id', pid)}/{sub}"


def r6(x: float) -> float:
    return round(float(x) + 0.0, 6)


# ----------------------------------------------------------------------------------------------------------------------
# owner-given parameters (rows) and their fragment checks
# ----------------------------------------------------------------------------------------------------------------------
ALLOCATIONS = [  # (line id, owner name, kg, verbatim fragment in row 54)
    ("AL-01", "intake/filter/duct", 3.5, "intake/filter/duct 3.5 kg"),
    ("AL-02", "compressor+drive", 5.5, "compressor+drive 5.5"),
    ("AL-03", "plenum/feed", 1.0, "plenum/feed 1.0"),
    ("AL-04", "Hall head+magnet", 3.0, "Hall head+magnet 3.0"),
    ("AL-05", "ICP neutralizer", 2.0, "ICP neutralizer 2.0"),
    ("AL-06", "RF generator/matching", 1.5, "RF generator/matching 1.5"),
    ("AL-07", "Hall PPU", 2.5, "Hall PPU 2.5"),
    ("AL-08", "Xe hardware", 1.5, "Xe hardware 1.5"),
    ("AL-09", "controls/harness", 1.0, "controls/harness 1.0"),
    ("AL-10", "structure/thermal", 2.5, "structure/thermal 2.5"),
]
ALLOC_SUM_KG = 24.0
DRY_RESERVE_KG = 4.0
DRY_TARGET_KG = 28.0
SYSTEM_MARGIN = 0.20     # row 52
EQUIPMENT_MGA = 0.20     # row 57 (default for new/unselected hardware)
HARNESS_FRACTION = 0.05  # row 60
WET_LIMIT_KG = 40.0      # row 5 (strict: < 40 kg wet)
INTERNAL_ALLOCS_KG = (34.0, 36.0)  # row 53
XE_CASES_KG = (2.0, 5.0, 10.0)     # row 48
XE_SCREEN_SHARE = 0.25             # row 44 (screening cap, not an entitlement)


def check_owner_fragments() -> None:
    for _lid, _name, _kg, frag in ALLOCATIONS:
        require_text(54, frag)
    for frag in ("28 kg dry target", "Sum 24 kg", "4 kg dry development reserve", "These are allocations, not CBEs"):
        require_text(54, frag)
    require_text(52, "20% internal development/system margin")
    require_text(52, "<40 kg wet")
    require_text(57, "ECSS-D-like 20% equipment margin")
    require_text(60, "5% of nominal dry mass")
    require_text(53, "34 kg and 36 kg")
    require_text(48, "2 kg / 5 kg / 10 kg")
    require_text(45, "Never add a second residual in the BOM")
    require_text(44, "0.25 only as a screening cap")
    require_text(5, "INCLUDES Xe + tank")
    require_text(56, "NASA SBIR 2 kg PPU")
    require_text(59, "add downstream ICP neutralizer, RF generator/matching/feedthrough and collector/bias hardware")
    require_text(59, "Remove pre-ionizer-only items from the new architecture BOM, not from historical v1")
    require_text(46, "no continuous C1-Xe cathode term")
    require_text(47, "add separate ICP-neutralizer/RF-electronics BOM items")
    require_text(51, "not required for an ICP-only flight branch")
    require_text(55, "dual series isolation on the high-pressure Xe path")
    require_text(6, "bounded functional Xe mode")
    require_text(58, "RETIRE only from the new v2/A9 path")
    if abs(sum(a[2] for a in ALLOCATIONS) - ALLOC_SUM_KG) > 1e-12:
        raise RuntimeError("row 54 allocation lines no longer sum to 24 kg")
    if abs(ALLOC_SUM_KG + DRY_RESERVE_KG - DRY_TARGET_KG) > 1e-12:
        raise RuntimeError("row 54 allocation + reserve != dry target")
    if "no combined flight C1 + ICP installation" not in a91("OQ-A902-04"):
        raise RuntimeError("A9.1 OQ-A902-04 text changed")
    a9 = load(DECISIONS["A9"][0])
    flags = " ".join(f["issue"] for f in a9["recorder_consistency_flags_for_owner"])
    for frag in ("3.504 kg", "6.1 kg", "combined analog 4.54-12.77 kg"):
        if frag not in flags:
            raise RuntimeError(f"A9 recorder flag fragment {frag!r} missing")


# ----------------------------------------------------------------------------------------------------------------------
# verified evidence (copied by pointer)
# ----------------------------------------------------------------------------------------------------------------------
def evidence() -> dict:
    h27 = load(PINNED_DELIVERABLES["H27"][0])
    ev = {}
    ev["mc1_iron"] = copied("H21", dp_ptr("H21", "H21-24") + "/iron_kg", 1.925)
    ev["mc1_copper"] = copied("H21", dp_ptr("H21", "H21-24") + "/copper_kg", 1.579)
    ev["mc1_status"] = copied("H21", dp_ptr("H21", "H21-24", "status"),
                              "PRELIMINARY (excludes channel ceramics, anode, structure; PENDING "
                              "docs/hardware/h2/h2_7_mechanical_bom/)")
    ev["mc1_class"] = copied("H21", dp_ptr("H21", "H21-24", "evidence_class"), "model-derived")
    ev["ppu_h24"] = copied("H24", dp_ptr("H24", "H24-34"), 6.1)
    ev["ppu_h24_class"] = copied("H24", dp_ptr("H24", "H24-34", "evidence_class"), "measured")
    ev["h27_hall"] = copied("H27", dp_ptr("H27", "H27-14"), [2.6, 6.3])
    ev["h27_ppu"] = copied("H27", dp_ptr("H27", "H27-18"), [2.0, 10.9])
    ev["h27_tank"] = copied("H27", dp_ptr("H27", "H27-09"), [3.5, 6.3])
    ev["h27_reg"] = copied("H27", dp_ptr("H27", "H27-11"), [0.974, 5.9])
    ev["h27_valves"] = copied("H27", dp_ptr("H27", "H27-12"), 0.57)
    ev["h27_cath"] = copied("H27", dp_ptr("H27", "H27-16"), [0.2, 0.3])
    ev["h27_xe_cath_term"] = copied("H27", dp_ptr("H27", "H27-06"), 5.4)
    i11 = index_of(h27["interface_demands"], "id", "ID-11")
    ev["h27_id11"] = copied("H27", f"/interface_demands/{i11}/range", [5.044, 12.77])
    ev["an_nasa"] = copied("H27", "/analog_data/AN-NASA-LM-PPU-TARGET/value", 2.0)
    ev["an_nasa_class"] = copied("H27", "/analog_data/AN-NASA-LM-PPU-TARGET/evidence_class", "assumed")
    ev["an_sets"] = copied("H27", "/analog_data/AN-SETS-PPU/value", 5.0)
    ev["an_sets_class"] = copied("H27", "/analog_data/AN-SETS-PPU/evidence_class", "measured")
    ev["an_tas"] = copied("H27", "/analog_data/AN-TAS-PPUMK1-MASS/value", 10.9)
    ev["an_latch_g"] = copied("H27", "/analog_data/AN-MOOG-LATCH-18/value", 170.0)
    ev["an_pfcv_g"] = copied("H27", "/analog_data/AN-MOOG-PFCV/value", 115.0)
    ev["an_xfc_g"] = copied("H27", "/analog_data/AN-MOOG-XFC/value", 974.0)
    ev["an_tank_class"] = copied("H27", "/analog_data/AN-MT-XSXTA/evidence_class", "assumed")
    ev["mbom_mga_d"] = copied("MBOM", "/margin_policy/maturity_categories/ecss_d_new_or_major_modification/mga", 0.2)
    ev["mbom_sys"] = copied("MBOM", "/system_margin/proposed_fraction", 0.2)
    # internal consistency of the copied H2-7 numbers (arithmetic, not new evidence)
    if abs(ev["h27_tank"]["value"][0] + ev["h27_reg"]["value"][0] + ev["h27_valves"]["value"]
           - ev["h27_id11"]["value"][0]) > 1e-9:
        raise RuntimeError("H2-7 ID-11 low end no longer equals tank + regulator + valves low ends")
    if abs(2 * (ev["an_latch_g"]["value"] + ev["an_pfcv_g"]["value"]) / 1000.0 - ev["h27_valves"]["value"]) > 1e-9:
        raise RuntimeError("H2-7 valve set no longer equals 2 x (latch + PFCV)")
    return ev


# ----------------------------------------------------------------------------------------------------------------------
# (1) A9 flight BOM item list
# ----------------------------------------------------------------------------------------------------------------------
def bom_items(ev: dict) -> dict:
    mbom = load(PINNED_DELIVERABLES["MBOM"][0])
    mbom_ids = {it["id"] for it in mbom["items"]}
    h27 = load(PINNED_DELIVERABLES["H27"][0])
    h27_lines = {li["id"] for r in h27["rows"] for li in r["line_items"]}
    bus = load(READ_DELIVERABLES["BUS_A9"])
    slots = {s["slot"]: s for s in bus["slots"]}
    m16 = {r["row"]: r["key"] for r in load(READ_DELIVERABLES["M16"])["rows"]}

    def B(bid, name, group, bom_status, *, predecessor_mbom=None, predecessor_h27=(), allocation_line=None,
          allocation_mapping="OWNER_LINE", power_slots=(), m16_row=None, flight_status, value=None, units="kg",
          evidence_class=None, basis, status, freeze_point, owner_rows=(), a91_ids=(), note=""):
        if predecessor_mbom is not None and predecessor_mbom not in mbom_ids:
            raise KeyError(f"{bid}: mass_bom v1 item {predecessor_mbom} unknown")
        for li in predecessor_h27:
            if li not in h27_lines:
                raise KeyError(f"{bid}: H2-7 line {li} unknown")
        for s in power_slots:
            if s not in slots:
                raise KeyError(f"{bid}: A9 bus slot {s} unknown")
        if m16_row is not None and m16_row not in m16:
            raise KeyError(f"{bid}: M16 row {m16_row} unknown")
        if evidence_class is not None and evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(evidence_class)
        if freeze_point not in FREEZE_POINTS:
            raise ValueError(freeze_point)
        if value is None and not (status.startswith(TBD) or status.startswith("PENDING") or bom_status in
                                  ("REMOVED_PREIONIZER_ONLY", "VARIANT_ONLY",
                                                                  "DROPPED_FROM_FLIGHT_A9")):
            raise ValueError(f"{bid}: null value needs a TBD/PENDING status")
        return {"id": bid, "name": name, "group": group, "bom_status": bom_status,
                "predecessor_mass_bom_v1": predecessor_mbom, "predecessor_h2_7_lines": list(predecessor_h27),
                "allocation_line": allocation_line, "allocation_mapping": allocation_mapping,
                "power_slots_a9": list(power_slots), "m16_row": m16_row,
                "m16_key": m16.get(m16_row) if m16_row else None, "flight_status": flight_status,
                "value": value, "units": units, "evidence_class": evidence_class, "basis": basis, "status": status,
                "freeze_point": freeze_point, "owner_rows": list(owner_rows), "a9_1_decisions": list(a91_ids),
                "note": note}

    FR = "FLIGHT (primary A9 architecture hall_icp_neutralizer)"
    tbd_design = "TBD - requires a Vyovrinda design or selected-part (supplier-measured) mass"
    flight = [
        B("A9B-01", "intake (atmospheric collector / collimator)", "atmospheric", "RETAINED",
          predecessor_mbom="intake", predecessor_h27=["R01.m_intake"], allocation_line="AL-01", m16_row=1,
          flight_status=FR, basis="TBD", status=f"{TBD} Vyovrinda intake geometry and sourced material density, "
          "or a measured mass (H2-7 H27-01)", freeze_point="after-evidence", owner_rows=[54, 59]),
        B("A9B-02", "protective / filter stage", "atmospheric", "RETAINED", predecessor_mbom="filter",
          predecessor_h27=["R02.m_filter"], allocation_line="AL-01", m16_row=2, flight_status=FR, basis="TBD",
          status=f"{TBD} a filter concept and geometry or a measured mass (H2-7 H27-02)",
          freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-03", "atmospheric duct intake -> compressor", "atmospheric", "NEW_LINE_NAMED_BY_ALLOCATION",
          allocation_line="AL-01", m16_row=1, flight_status=FR, basis="TBD",
          status=f"{TBD} duct routing/length and wall material (not a separate line in mass_bom v1 / H2-7; named "
          "by the row-54 allocation 'intake/filter/duct')", freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-04", "compressor incl. motor/drive and isolation valve", "atmospheric", "RETAINED",
          predecessor_mbom="compressor", predecessor_h27=["R03.m_compressor"], allocation_line="AL-02",
          power_slots=["compressor"], m16_row=3, flight_status=FR, basis="TBD",
          status=f"{TBD} compressor concept freeze (DI-1.4) and an ABEP-scale design or breadboard mass (H2-7 H27-03)",
          freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-05", "buffer / plenum vessel (atmospheric gas chamber)", "atmospheric", "RETAINED",
          predecessor_mbom="atmospheric_gas_chamber", predecessor_h27=["R04.m_plenum"], allocation_line="AL-03",
          m16_row=4, flight_status=FR, basis="TBD",
          status=f"{TBD} plenum volume, pressure and wall material (H2-3 volume range only; no mass)",
          freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-06", "atmospheric metering + isolation valves and feed line to H-1", "atmospheric", "RETAINED",
          predecessor_mbom="atmospheric_valve", predecessor_h27=["R05.m_atm_valve"], allocation_line="AL-03",
          power_slots=["flow_control_atmospheric"], m16_row=5, flight_status=FR, basis="TBD",
          status=f"{TBD} a low-pressure atmospheric metering valve concept (H2-7 H27-05)",
          freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-07", "Xe tank (stored-Xe subsystem; bounded Xe-capable mode, row 6)", "xe", "RETAINED",
          predecessor_mbom="xe_tank", predecessor_h27=["R06.m_tank"], allocation_line="AL-08", m16_row=6,
          flight_status=FR, value=ev["h27_tank"]["value"], evidence_class="inferred",
          basis="analog planning range copied from H2-7 H27-09 (MT Aerospace XS-XTA '<= 3.5 kg' catalogue value, "
          "evidence class assumed, under development; S-XTA 40 l predicted 6.3 kg); not a Vyovrinda CBE",
          status=f"PRELIMINARY (analog); tank sizing per Xe case at 323 K (row 50) {pending('A9-08')}",
          freeze_point="after-evidence", owner_rows=[6, 48, 50, 54],
          note="the flight Xe system stays because row 6 requires a demonstrated bounded Xe-capable mode"),
        B("A9B-08", "Xe tank mounting and thermal hardware", "xe", "RETAINED",
          predecessor_h27=["R06.m_mounting_thermal"], allocation_line="AL-08",
          allocation_mapping="PROPOSED_MAPPING (MQ-07)", m16_row=6, flight_status=FR, basis="TBD",
          status=f"{TBD} tank selection, launch loads and tank thermal design", freeze_point="after-evidence",
          owner_rows=[54], note="A6 counts mounting/thermal inside the stored-Xe subsystem; mapped to AL-08 as a proposal"),
        B("A9B-09", "Xe pressure regulator", "xe", "RETAINED", predecessor_mbom="xe_valve_and_flow_control",
          predecessor_h27=["R07.m_regulator"], allocation_line="AL-08", power_slots=["flow_control_xe"], m16_row=7,
          flight_status=FR, value=ev["h27_reg"]["value"], evidence_class="inferred",
          basis="analog planning range copied from H2-7 H27-11 (Moog XFC 0.974 kg .. ArianeGroup XRFS 5.9 kg)",
          status="PRELIMINARY (analog)", freeze_point="after-evidence", owner_rows=[47, 54]),
        B("A9B-10", "Xe high-pressure path: two independent series isolation valves (row 55)", "xe",
          "CARRIED_REVISED", predecessor_mbom="xe_valve_and_flow_control", predecessor_h27=["R08.m_valves"],
          allocation_line="AL-08", power_slots=["flow_control_xe"], m16_row=8, flight_status=FR,
          value=r6(2 * ev["an_latch_g"]["value"] / 1000.0), evidence_class="inferred",
          basis="arithmetic 2 x 170 g (Moog 1/8 inch latching isolation valve, H2-7 AN-MOOG-LATCH-18) = 0.34 kg; "
          "a PROPOSED A9 reading of row 55 (H2-7 carried one latch per branch, single string)",
          status=f"PROPOSED; valve set {pending('A9-07')} (H2-3 revision)", freeze_point="LOCK-1",
          owner_rows=[55, 90]),
        B("A9B-11", "Xe anode-feed proportional flow control (bounded Xe mode / Xe reference to the Hall anode)",
          "xe", "CARRIED_REVISED", predecessor_mbom="xe_valve_and_flow_control", predecessor_h27=["R08.m_valves"],
          allocation_line="AL-08", power_slots=["flow_control_xe"], m16_row=8, flight_status=FR,
          value=r6(ev["an_pfcv_g"]["value"] / 1000.0), evidence_class="inferred",
          basis="Moog 51E339 PFCV 115 g (H2-7 AN-MOOG-PFCV); one branch only in A9 (the C1 cathode-feed branch "
          "drops out of flight, OQ-A902-04)", status=f"PROPOSED; {pending('A9-07')} (H2-3 revision)",
          freeze_point="LOCK-1", owner_rows=[6, 54], a91_ids=["OQ-A902-04"]),
        B("A9B-12", "Xe plumbing, filters, fittings, pressure transducers", "xe", "RETAINED",
          predecessor_h27=["R08.m_plumbing"], allocation_line="AL-08", m16_row=8, flight_status=FR, basis="TBD",
          status=f"{TBD} Xe line routing, lengths and component selection ({pending('A9-07')})",
          freeze_point="after-evidence", owner_rows=[54]),
        B("A9B-13", "Xe propellant load (design case)", "xe_propellant", "RETAINED_AS_DESIGN_CASES",
          predecessor_mbom="xe_load", predecessor_h27=["R06.m_Xe_other"], allocation_line=None,
          allocation_mapping="WET_TERM (outside the 28 kg dry target)", m16_row=6, flight_status=FR,
          value=list(XE_CASES_KG), evidence_class="owner-allocation",
          basis="row 48: explicit 2 / 5 / 10 kg design cases; no single mission load is frozen",
          status=f"OWNER_GIVEN (cases); booked terms and reserve content {pending('A9-08')}", freeze_point="after-evidence",
          owner_rows=[43, 48], note="the H2-7 fixed C1 cathode term R06.m_Xe_cathode (5.4 kg) is NOT carried in "
          "the primary A9 flight BOM (row 46, OQ-A902-04); it belongs to the C1 fallback variant only"),
        B("A9B-14", "Xe residual (unusable) - imported once from the A9 Xe ledger", "xe_propellant", "IMPORTED",
          predecessor_mbom="xe_residual", predecessor_h27=["R06.m_Xe_residual"], allocation_line=None,
          allocation_mapping="WET_TERM (imported total; never computed here)", m16_row=6, flight_status=FR,
          basis="row 45: booked once in the Xe ledger and imported into the mass BOM; never a second residual here",
          status=pending("A9-08"), freeze_point="after-evidence", owner_rows=[45]),
        B("A9B-15", "Hall head: channel walls, anode / gas distributor, body, fasteners", "hall", "RETAINED",
          predecessor_mbom="hall_thruster_head", predecessor_h27=["R09.m_hall_head_incl_mc"], allocation_line="AL-04",
          power_slots=["hall_discharge"], m16_row=9, flight_status=FR, basis="TBD",
          status=f"{TBD} H-1 channel/anode/body design masses (H2-1 H21-24 excludes them; {pending('A9-07')})",
          freeze_point="after-evidence", owner_rows=[54, 79, 106],
          note="flight H-1 is neutralizer-agnostic (row 79); no central C1 bore/mount in flight"),
        B("A9B-16", "magnetic circuit MC-1: FeCo-2V inner / pure-iron outer, ceramic-insulated Cu coils",
          "hall", "RETAINED", predecessor_mbom="hall_magnets", predecessor_h27=["R10.m_magnetic_circuit"],
          allocation_line="AL-04", power_slots=["hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim"],
          m16_row=10, flight_status=FR,
          value=r6(ev["mc1_iron"]["value"] + ev["mc1_copper"]["value"]), evidence_class="model-derived",
          basis="H2-1 H21-24 iron 1.925 kg + copper 1.579 kg = 3.504 kg (RP-1, f_NI 2; magnetic parts only; "
          "coils fill the assumed winding window, minimum-I^2R design)",
          status=f"PRELIMINARY; ceramic-insulated coil (row 77) and hot-state B sensor (row 82) revision "
          f"{pending('A9-07')}", freeze_point="after-evidence", owner_rows=[54, 76, 77, 80, 82]),
        B("A9B-17", "ICP neutralizer head: dielectric discharge tube/chamber, RF antenna/coil, antenna shield, "
          "floating body, IP-NEU mount, capped dedicated gas port", "icp", "NEW_A9", allocation_line="AL-05",
          m16_row=None, flight_status=FR, basis="TBD",
          status=f"{TBD} a flight ICP-neutralizer design (A9-03 ICD ICP-02/04/07/19/20) or a measured module mass; "
          "no mass analog accessed", freeze_point="after-evidence", owner_rows=[59, 61, 69, 70],
          a91_ids=["HIQ-06", "OQ-A902-05"],
          note="unmagnetized in v1 (row 69); the capped dedicated ICP gas port stays in the ICD (OQ-A902-05)"),
        B("A9B-18", "electron-extraction collector / bias electrode hardware (electrode, isolators, leads)", "icp",
          "NEW_A9", allocation_line="AL-05", allocation_mapping="PROPOSED_MAPPING (MQ-07)", m16_row=None,
          flight_status=FR, basis="TBD",
          status=f"{TBD} collector design; flight collector material not frozen (A9-03 collector clarification: "
          "O/AO coupon programme)", freeze_point="after-evidence", owner_rows=[59, 70, 106],
          a91_ids=["A9-03-collector"]),
        B("A9B-19", "flight 13.56 MHz RF generator (power amplifier / supply)", "icp", "NEW_A9",
          allocation_line="AL-06", power_slots=["icp_rf_source"], m16_row=12, flight_status=FR, basis="TBD",
          status=f"{TBD} a flight RF generator design or supplier data; the laboratory 0-500 W generator (row 72) "
          "is a test capability only (OQ-A902-03), never a flight mass", freeze_point="after-evidence",
          owner_rows=[47, 59, 72], a91_ids=["OQ-A902-03"],
          note="new item, NOT a remap of the historical pre-ionizer rf_generator (row 47)"),
        B("A9B-20", "flight RF matching network", "icp", "NEW_A9", allocation_line="AL-06",
          power_slots=["icp_matching_network"], m16_row=12, flight_status=FR, basis="TBD",
          status=f"{TBD} a flight matching-network design or supplier data", freeze_point="after-evidence",
          owner_rows=[59], a91_ids=["A9-03-matching"]),
        B("A9B-21", "RF feedthrough and coax / transmission line to the ICP antenna", "icp", "NEW_A9",
          allocation_line="AL-06", allocation_mapping="PROPOSED_MAPPING (MQ-07)", m16_row=12, flight_status=FR,
          basis="TBD", status=f"{TBD} flight RF routing length and feedthrough selection", freeze_point="after-evidence",
          owner_rows=[59]),
        B("A9B-22", "collector / bias supply (floating, V/I readback)", "icp", "NEW_A9", allocation_line="AL-07",
          allocation_mapping="PROPOSED_MAPPING (MQ-07)", power_slots=["icp_collector_bias"], m16_row=12,
          flight_status=FR, basis="TBD", status=f"{TBD} bias-supply requirement (electron-extraction interface, "
          "ICP-21/ICP-24) and a design", freeze_point="after-evidence", owner_rows=[59, 70, 110]),
        B("A9B-25", "Hall PPU: discharge supply + per-coil magnet supplies (row 110 partition)", "power", "CARRIED_REVISED",
          predecessor_mbom="ppu", predecessor_h27=["R12.m_ppu"], allocation_line="AL-07",
          power_slots=["hall_discharge", "hall_magnet_inner", "hall_magnet_outer", "hall_magnet_trim"], m16_row=12,
          flight_status=FR, basis="TBD",
          status=f"{TBD} a flight PPU design/CBE (H2-4 revision for the A9 partition and 100 V internal bus, rows "
          f"110-111; {pending('A9-07')}); analog evidence in line_checks AL-07", freeze_point="after-evidence",
          owner_rows=[54, 56, 110, 111],
          note="C1 heater/keeper/common-tie supplies leave the flight PPU scope (bus slots NOT_INSTALLED in "
          "hall_icp_neutralizer; OQ-A902-04)"),
        B("A9B-26", "flow/valve drivers, housekeeping electronics, reserved DC port", "control", "CARRIED_REVISED",
          predecessor_mbom="ppu", predecessor_h27=["R14.m_control_fdir"], allocation_line="AL-09",
          allocation_mapping="PROPOSED_MAPPING (MQ-07)",
          power_slots=["flow_control_atmospheric", "flow_control_xe", "housekeeping_controls", "reserved_dc_port"],
          m16_row=14, flight_status=FR, basis="TBD", status=f"{TBD} controller/driver design (inside the PPU analog "
          "in H2-7 v1)", freeze_point="after-evidence", owner_rows=[110]),
        B("A9B-27", "control / FDIR electronics", "control", "RETAINED", predecessor_mbom="ppu",
          predecessor_h27=["R14.m_control_fdir"], allocation_line="AL-09", power_slots=["housekeeping_controls"],
          m16_row=14, flight_status=FR, basis="TBD", status=f"{TBD} a controller design (H2-4 split)",
          freeze_point="after-evidence", owner_rows=[54, 55]),
        B("A9B-28", "harness", "control", "RETAINED", predecessor_mbom="harness", predecessor_h27=["SYS-H.m_harness"],
          allocation_line="AL-09", m16_row=None, flight_status=FR, basis="owner policy row 60 until a routed harness exists",
          status=f"{TBD} a routed harness design; until then 5 % of nominal dry mass (row 60; policy check in "
          "policy_checks PC-01)", freeze_point="after-evidence", owner_rows=[60]),
        B("A9B-29", "flight sensors / telemetry subset (ICP telemetry added, C1 telemetry TM-03 dropped)", "control",
          "CARRIED_REVISED", predecessor_h27=["R15.m_flight_sensors"], allocation_line="AL-09",
          allocation_mapping="PROPOSED_MAPPING (MQ-07)", m16_row=15, flight_status=FR, basis="TBD",
          status=f"{TBD} flight sensor selection (row 62 ICP list: module ID, RF fwd/refl, interlock, collector V/I, "
          "temperatures, command/telemetry)", freeze_point="after-evidence", owner_rows=[62]),
        B("A9B-30", "thermal-control hardware (radiators, heaters, MLI, heat paths)", "structure_thermal", "RETAINED",
          predecessor_mbom="thermal_hardware", predecessor_h27=["R13.m_thermal"], allocation_line="AL-10",
          power_slots=["thermal_control"], m16_row=13, flight_status=FR, basis="TBD",
          status=f"{TBD} the revised thermal network (>= 50 K margin + 20 % heat-load margin, row 86; "
          f"{pending('A9-07')}) and the ICP module heat load (ICD ICP-43)", freeze_point="after-evidence",
          owner_rows=[54, 86]),
        B("A9B-31", "propulsion-module structure, brackets, spacecraft interface, downstream coaxial ICP mount",
          "structure_thermal", "CARRIED_REVISED", predecessor_mbom="structure", predecessor_h27=["R16.m_structure"],
          allocation_line="AL-10", m16_row=16, flight_status=FR, basis="TBD",
          status=f"{TBD} spacecraft configuration, launch loads and a structural design", freeze_point="after-evidence",
          owner_rows=[54, 79]),
    ]
    variants = [
        B("A9B-23", "ICP gas-feed flow control (flow_control_icp_feed)", "icp", "VARIANT_ONLY",
          allocation_line=None, allocation_mapping="VARIANT (booked only when G-ATM or G-XE is installed/used)",
          power_slots=["flow_control_icp_feed"], flight_status="VARIANT ONLY (G-ATM / G-XE)", basis="A9.1 OQ-A902-05",
          status="not in the primary G-REUSE flight BOM (m_ICP,dedicated = 0, HIQ-06_accounting)",
          freeze_point="LOCK-1", a91_ids=["HIQ-06", "OQ-A902-05"]),
        B("A9B-24", "ICP assist magnet", "icp", "VARIANT_ONLY", allocation_line=None,
          allocation_mapping="VARIANT (new controlled variant with booked mass/power)", power_slots=["icp_assist_magnet"],
          flight_status="VARIANT ONLY", basis="row 69", status="not in the v1 / A9 first build (unmagnetized ICP)",
          freeze_point="after-evidence", owner_rows=[69]),
    ]
    removed_preionizer = []
    for i, (mid, why) in enumerate([
            ("rf_source", "upstream RF pre-ionization source"), ("rf_generator", "pre-ionizer RF generator"),
            ("rf_matching_network", "pre-ionizer matching network"), ("ecr_source", "ECR pre-ionization source"),
            ("microwave_source", "ECR microwave source"), ("waveguide", "ECR transmission line"),
            ("ecr_magnets", "ECR resonance magnets")], start=1):
        removed_preionizer.append(B(f"A9B-R0{i}", f"{why} (mass_bom v1 item '{mid}')", "removed", "REMOVED_PREIONIZER_ONLY",
                                    predecessor_mbom=mid, flight_status="REMOVED from the A9 BOM (kept in historical v1)",
                                    basis="row 59; A9 supersession", status="removed from the A9 BOM only",
                                    freeze_point="NOW", owner_rows=[59, 61]))
    removed_preionizer.append(B("A9B-R08", "reserved RF pre-ionizer interface provision at IP-UP/IP-DN (H2-7 R17)",
                                "removed", "REMOVED_PREIONIZER_ONLY", predecessor_h27=["R17.m_interface_provision"],
                                m16_row=17, flight_status="REMOVED from the A9 BOM (kept in historical H2-7 v1)",
                                basis="rows 59, 61; A9.1 A9-03-planes (IP-DN historical, unchanged)",
                                status="removed from the A9 BOM only", freeze_point="NOW", owner_rows=[59, 61],
                                a91_ids=["A9-03-planes"]))
    GR = "GROUND REFERENCE / CONTROL (hall_c1_reference module on KC-1) and C1 fallback variant only"
    c1_dropped = [
        B("A9B-C01", "C1 heated Xe-fed LaB6 hollow cathode unit (heater, keeper)", "c1", "DROPPED_FROM_FLIGHT_A9",
          predecessor_mbom="cathode", predecessor_h27=["R11.m_cathode_unit"], m16_row=11, flight_status=GR,
          value=ev["h27_cath"]["value"], evidence_class="inferred",
          basis="H2-7 H27-16 analog (BHT-600 / BHT-1500 cathodes); ground/fallback context only",
          status="not in the primary A9 flight BOM (OQ-A902-04)", freeze_point="NOW", owner_rows=[49, 79, 88],
          a91_ids=["OQ-A902-04"]),
        B("A9B-C02", "C1 shield / O-isolation / mount", "c1", "DROPPED_FROM_FLIGHT_A9", predecessor_mbom="cathode",
          predecessor_h27=["R11.m_cathode_shield_mount"], m16_row=11, flight_status=GR, basis="TBD",
          status=f"{TBD} external C1 module design (ground article; {pending('A9-07')})", freeze_point="NOW",
          owner_rows=[79], a91_ids=["OQ-A902-04"]),
        B("A9B-C03", "C1 heater / keeper (300-600 V pulsed ignition) / cathode-common tie supplies", "c1",
          "DROPPED_FROM_FLIGHT_A9", predecessor_mbom="ppu", predecessor_h27=["R12.m_ppu"],
          power_slots=["c1_heater", "c1_keeper", "c1_common_tie"], m16_row=12, flight_status=GR, basis="TBD",
          status="not in the flight PPU scope of hall_icp_neutralizer (A9 bus slots NOT_INSTALLED); ground "
          "reference supplies on the C1 module (ICD ICP-25, ICP-46)", freeze_point="NOW", owner_rows=[89, 91, 110],
          a91_ids=["OQ-A902-04", "ICP-46"]),
        B("A9B-C04", "C1 cathode Xe-feed branch (branch latch + PFCV of the H2-7 two-branch set; two series "
          "isolation valves on the flight cathode branch, row 90)", "c1", "DROPPED_FROM_FLIGHT_A9",
          predecessor_mbom="xe_valve_and_flow_control", predecessor_h27=["R08.m_valves"], m16_row=8, flight_status=GR,
          value=r6((ev["an_latch_g"]["value"] + ev["an_pfcv_g"]["value"]) / 1000.0), evidence_class="inferred",
          basis="one branch of H2-7 H27-12 = 170 g + 115 g = 0.285 kg (analog parts)",
          status="not in the primary A9 flight BOM (OQ-A902-04)", freeze_point="NOW", owner_rows=[90],
          a91_ids=["OQ-A902-04"]),
        B("A9B-C05", "Xe cathode-line filter/getter (<= 17 W class)", "c1", "DROPPED_FROM_FLIGHT_A9",
          power_slots=["filter_getter"], m16_row=8, flight_status=GR, basis="row 51",
          status=f"{TBD} vendor/spec verification (only if the C1/Xe branch is flown); not required for an "
          "ICP-only flight branch", freeze_point="NOW", owner_rows=[51]),
        B("A9B-C06", "C1 cathode Xe design term (0.10 mg/s x 15,000 h)", "c1", "DROPPED_FROM_FLIGHT_A9",
          predecessor_h27=["R06.m_Xe_cathode"], m16_row=6, flight_status=GR, value=ev["h27_xe_cath_term"]["value"],
          evidence_class="assumed", basis="H2-7 H27-06 (A5 allocation, not a demonstrated flow)",
          status="C1 fallback/reference term only (row 46: the ICP architecture has no continuous C1-Xe term); "
          f"booking {pending('A9-08')}", freeze_point="NOW", owner_rows=[46], a91_ids=["OQ-A902-04"]),
        B("A9B-C07", "C1 keeper/heater flight telemetry (H2-7 TM-03)", "c1", "DROPPED_FROM_FLIGHT_A9",
          predecessor_h27=["R15.m_flight_sensors"], m16_row=15, flight_status=GR, basis="OQ-A902-04",
          status="dropped from the flight telemetry list; the ground C1 module keeps its own instrumentation",
          freeze_point="NOW", a91_ids=["OQ-A902-04"]),
    ]
    ground_only = [
        {"id": "GA-01", "item": "C1 reference module (external C1, row 79) on the kinematic carrier KC-1",
         "rule": "ground/test article; measured mass/CG per serial and configuration (ICD ICP-08, row 116)"},
        {"id": "GA-02", "item": "laboratory ICP module, 13.56 MHz 0-500 W lab RF generator, matching network off the "
         "moving platform (A9.1 A9-03-matching), directional coupler",
         "rule": "test capability only (row 72, OQ-A902-03); no flight mass"},
        {"id": "GA-03", "item": "matched sham service lines and mechanical shams (rows 63, 133)",
         "rule": "stand parasitics only; weighed for the stand payload, never flight mass"},
        {"id": "GA-04", "item": "H-1 ground diagnostics and fixture FX-01..FX-10 (H2-6)",
         "rule": "excluded from the flight mass model (H2-6 -> H2-7 demand, re-confirmed for A9)"},
    ]
    for it in flight:
        if it["allocation_line"] is None and not it["allocation_mapping"].startswith("WET_TERM"):
            raise ValueError(f"{it['id']}: flight item without an allocation line")
    return {"flight": flight, "variant_only": variants, "removed_preionizer_only": removed_preionizer,
            "c1_dropped_from_flight": c1_dropped, "ground_article_only": ground_only,
            "c1_slots_check": {s: slots[s]["configurations"]["hall_icp_neutralizer"]
                               for s in ("c1_heater", "c1_keeper", "c1_common_tie", "filter_getter")}}


# ----------------------------------------------------------------------------------------------------------------------
# (2) allocation vs evidence per line
# ----------------------------------------------------------------------------------------------------------------------
def line_checks(ev: dict, bom: dict) -> list:
    by_line: dict = {}
    for it in bom["flight"]:
        if it["allocation_line"]:
            by_line.setdefault(it["allocation_line"], []).append(it["id"])
    mc1 = r6(ev["mc1_iron"]["value"] + ev["mc1_copper"]["value"])
    ppu_floor = min(ev["an_sets"]["value"], ev["ppu_h24"]["value"], ev["an_tas"]["value"])
    xe_floor = ev["h27_id11"]["value"][0]
    floors = {
        "AL-04": {"floor_kg": mc1, "floor_is_partial": True,
                  "constituents": [{"what": "MC-1 iron (H2-1 H21-24)", "kg": ev["mc1_iron"]["value"],
                                    "evidence_class": "model-derived", "source": ev["mc1_iron"]},
                                   {"what": "MC-1 copper (H2-1 H21-24)", "kg": ev["mc1_copper"]["value"],
                                    "evidence_class": "model-derived", "source": ev["mc1_copper"]},
                                   {"what": "channel ceramics, anode/distributor, body, fasteners", "kg": None,
                                    "status": f"{TBD} H-1 design masses ({pending('A9-07')})"}],
                  "arithmetic": f"floor = 1.925 + 1.579 = {mc1} kg (magnetic parts only) > allocation 3.0 kg; "
                                f"gap at CBE = {r6(mc1 - 3.0)} kg; at row-57 MEV (x1.2) = {r6(mc1 * 1.2)} kg, gap "
                                f"{r6(mc1 * 1.2 - 3.0)} kg",
                  "context": {"h2_7_analog_range_kg": ev["h27_hall"]["value"],
                              "note": "Busek BHT-600 2.6 kg / BHT-1500 6.3 kg thrusters incl. magnetic circuit "
                                      "(H2-7 H27-14): masses of other hardware; the Vyovrinda preliminary design "
                                      "(H21-24) governs the floor", "source": ev["h27_hall"]},
                  "floor_note": "current verified Vyovrinda preliminary design point (RP-1, f_NI 2), not a physical "
                                "lower bound: a smaller winding window trades copper mass for coil power (H21-24 note)"},
        "AL-07": {"floor_kg": ppu_floor, "floor_is_partial": False,
                  "constituents": [{"what": "lowest row-56-admissible measured PPU analog (SETS PPU, 100-500 W, "
                                            "secondary listing, verify)", "kg": ev["an_sets"]["value"],
                                    "evidence_class": "measured", "source": ev["an_sets"]}],
                  "arithmetic": f"floor = min(SETS 5.0, NG EM1 6.1, TAS Mk1 10.9) = {ppu_floor} kg > allocation "
                                f"2.5 kg; gap {r6(ppu_floor - 2.5)} kg (vs the H2-4 analog 6.1 kg: gap "
                                f"{r6(ev['ppu_h24']['value'] - 2.5)} kg). Widest scope-matched basket: Hall PPU 2.5 + "
                                f"controls/harness 1.0 = 3.5 kg < 5.0 kg, still below; adding RF generator/matching 1.5 kg (a "
                                "function the analogs do not contain) gives 5.0 kg, equal to the lowest analog and "
                                "below the H2-4 6.1 kg",
                  "context": {"h2_4_analog_kg": ev["ppu_h24"]["value"], "h2_4_source": ev["ppu_h24"],
                              "h2_7_range_kg": ev["h27_ppu"]["value"], "h2_7_source": ev["h27_ppu"],
                              "excluded": {"value_kg": ev["an_nasa"]["value"], "source": ev["an_nasa"],
                                           "why": "NASA SBIR 2 kg is a development TARGET (evidence class assumed); "
                                                  "row 56: aspirational/screening only, never a CBE -> the "
                                                  "row-56-compliant H2-7 range is 5.0-10.9 kg"},
                              "scope_note": "analog PPUs include functions the A9 split books elsewhere (cathode "
                                            "heater/keeper supply, valve drivers, microcontroller) and lack the ICP "
                                            "RF supply; the state holds under the widest allocation basket"},
                  "floor_note": "masses of other PPUs (planning analogs), not physical lower bounds"},
        "AL-08": {"floor_kg": xe_floor, "floor_is_partial": True,
                  "constituents": [{"what": "Xe tank low end (H2-7 H27-09; XS-XTA '<= 3.5 kg' catalogue, class "
                                            "assumed)", "kg": ev["h27_tank"]["value"][0], "evidence_class": "inferred",
                                    "source": ev["h27_tank"]},
                                   {"what": "Xe regulator low end (Moog XFC, H2-7 H27-11)",
                                    "kg": ev["h27_reg"]["value"][0], "evidence_class": "inferred",
                                    "source": ev["h27_reg"]},
                                   {"what": "Xe valves (H2-7 H27-12, 2 x (latch + PFCV))",
                                    "kg": ev["h27_valves"]["value"], "evidence_class": "inferred",
                                    "source": ev["h27_valves"]},
                                   {"what": "plumbing, mounting/thermal", "kg": None,
                                    "status": f"{TBD} Xe routing and tank mounting design ({pending('A9-07')})"}],
                  "arithmetic": f"floor = 3.5 + 0.974 + 0.57 = {xe_floor} kg (= H2-7 ID-11 low end) > allocation "
                                f"1.5 kg; gap {r6(xe_floor - 1.5)} kg. Without any tank: 0.974 + 0.57 = "
                                f"{r6(0.974 + 0.57)} kg > 1.5 kg. A9 single-branch reading (A9B-10/11: 0.34 + 0.115 "
                                f"kg): 3.5 + 0.974 + 0.455 = {r6(3.5 + 0.974 + 0.455)} kg > 1.5 kg; without tank "
                                f"{r6(0.974 + 0.455)} kg, leaving {r6(1.5 - 0.974 - 0.455)} kg for tank, plumbing and "
                                "mounting",
                  "context": {"h2_7_id11_range_kg": ev["h27_id11"]["value"], "source": ev["h27_id11"],
                              "recorder_discrepancy": "the A9 decision's recorder flag quotes 'combined analog "
                                                      "4.54-12.77 kg'; H2-7 ID-11 gives 5.044-12.77 kg (3.5 + 0.974 "
                                                      "+ 0.57). The verified H2-7 value is used; the A9 file is "
                                                      "immutable (MQ-08)"},
                  "floor_note": "analog planning low end (other hardware), not a physical lower bound; the tank "
                                "low end is a catalogue '<=' figure for a family under development"},
    }
    out = []
    for lid, name, kg, _frag in ALLOCATIONS:
        f = floors.get(lid)
        if f is None:
            state = "ALLOCATION_UNVERIFIABLE_TBD"
            arithmetic = "no verified evidence value exists for any constituent; comparison not possible"
        elif f["floor_kg"] > kg:
            state = "ALLOCATION_BELOW_EVIDENCE_FLOOR"
            arithmetic = f["arithmetic"]
        elif f["floor_is_partial"]:
            state = "ALLOCATION_UNVERIFIABLE_TBD"
            arithmetic = f["arithmetic"]
        else:
            state = "CONSISTENT"
            arithmetic = f["arithmetic"]
        rec = {"line": lid, "owner_name": name, "allocation_kg": kg, "evidence_class": "owner-allocation",
               "allocation_source": row_src(54), "bom_items": by_line.get(lid, []),
               "evidence_floor_kg": f["floor_kg"] if f else None,
               "floor_is_partial": f["floor_is_partial"] if f else None,
               "gap_at_cbe_kg": r6(f["floor_kg"] - kg) if f and f["floor_kg"] > kg else None,
               "gap_at_row57_mev_kg": r6(f["floor_kg"] * (1 + EQUIPMENT_MGA) - kg) if f and f["floor_kg"] > kg else None,
               "state": state, "arithmetic": arithmetic,
               "evidence": {k: v for k, v in f.items() if k not in ("floor_kg", "floor_is_partial", "arithmetic")}
               if f else {"status": f"{TBD} a design or selected-part mass for "
                                    f"{', '.join(by_line.get(lid, []))}"},
               "owner_allocation_changed_here": False}
        if lid == "AL-09":
            rec["policy_check"] = "PC-01 (row 60 harness policy vs this line)"
        out.append(rec)
    return out


def policy_checks() -> list:
    rest = ALLOC_SUM_KG - 1.0
    k = HARNESS_FRACTION / (1 - HARNESS_FRACTION)
    h_mev = r6(k * rest)
    h_cbe = r6(k * rest * (1 + EQUIPMENT_MGA))
    return [
        {"id": "PC-01", "rule": "row 60 harness = 5 % of nominal dry mass (nominal dry incl. harness; H2-7 v1 "
                                "convention harness = f/(1-f) x other nominal dry)", "owner_rows": [54, 60],
         "arithmetic": {"other_lines_kg": rest, "f_over_1_minus_f": r6(k),
                        "harness_if_allocations_are_mev_level_kg": h_mev,
                        "harness_if_allocations_are_cbe_level_with_row57_kg": h_cbe,
                        "controls_harness_allocation_kg": 1.0},
         "finding": f"POLICY_CONFLICT: the policy harness alone ({h_mev} kg or {h_cbe} kg) exceeds the whole "
                    "'controls/harness 1.0 kg' line before any controls mass (MQ-06)"},
        {"id": "PC-02", "rule": "row 52 20 % internal system margin on nominal dry vs the row 54 4 kg dry "
                                "development reserve", "owner_rows": [52, 54],
         "arithmetic": {"row52_margin_on_24kg_kg": r6(SYSTEM_MARGIN * ALLOC_SUM_KG),
                        "row54_reserve_kg": DRY_RESERVE_KG,
                        "shortfall_if_reserve_is_the_row52_margin_kg": r6(SYSTEM_MARGIN * ALLOC_SUM_KG - DRY_RESERVE_KG),
                        "reserve_as_fraction_of_allocated": r6(DRY_RESERVE_KG / ALLOC_SUM_KG),
                        "allocated_that_28kg_supports_at_20pct_kg": r6(DRY_TARGET_KG / (1 + SYSTEM_MARGIN))},
         "finding": "INTERPRETATION_OPEN: 4.0 kg = 16.7 % of 24 kg; if the reserve is meant to be the row-52 "
                    "margin it is 0.8 kg short (MQ-02); if additive, the dry target is 28 + 4.8 = 32.8 kg"},
    ]


# ----------------------------------------------------------------------------------------------------------------------
# (3) wet-mass closure
# ----------------------------------------------------------------------------------------------------------------------
READINGS = {
    "R0": "OWNER_V0_AS_STATED: dry = 24 kg allocations + 4 kg dry development reserve = 28 kg dry target; no further "
          "margin (the owner's v0 budget read literally)",
    "R1": "ALLOCATIONS_MEV_LEVEL: each allocation already contains its row-57 equipment margin; harness = max(1.0 kg "
          "line, row-60 policy) with the 1.0 kg line leniently taken as all harness; row-52 20 % system margin on "
          "nominal dry REPLACES the 4 kg reserve",
    "R2": "ALLOCATIONS_CBE_LEVEL (primary policy reading of rows 52/57/60): row-57 20 % MGA on every non-harness line "
          "(unselected parts); harness = max(1.0 kg line, row-60 policy), MGA 0; row-52 20 % system margin on nominal "
          "dry REPLACES the 4 kg reserve",
    "R0E": "R0 with the three evidence floors substituted (AL-04 3.504, AL-07 5.0, AL-08 5.044 kg CBE)",
    "R1E": "R1 with the three evidence floors substituted (floors are CBE-level -> x1.2 row-57 to be MEV-level)",
    "R2E": "R2 with the three evidence floors substituted",
    "R3": "EVIDENCE_LINES_ONLY: only the three evidence floors with rows 57/60/52 applied (harness by the row-60 "
          "rule on them); the seven lines without evidence (incl. controls/harness) are EXCLUDED (partial sum, not a "
          "total)",
}
PRIMARY_READING = "R2"


def reading_dry(reading: str, floors: dict) -> dict:
    alloc = {lid: kg for lid, _n, kg, _f in ALLOCATIONS}
    sub = reading.endswith("E")
    vals = dict(alloc)
    if sub:
        for lid, fl in floors.items():
            vals[lid] = fl
    k = HARNESS_FRACTION / (1 - HARNESS_FRACTION)
    if reading in ("R0", "R0E"):
        dry = sum(vals.values()) + DRY_RESERVE_KG
        return {"nonharness_nominal_kg": None, "harness_kg": None, "nominal_dry_kg": None, "system_margin_kg": None,
                "dry_kg": r6(dry), "reserve_kg": DRY_RESERVE_KG}
    if reading == "R3":
        nonh = sum(floors[l] * (1 + EQUIPMENT_MGA) for l in floors)
        harness = k * nonh
    else:
        nonh = 0.0
        for lid, v in vals.items():
            if lid == "AL-09":
                continue
            is_floor = sub and lid in floors
            if reading.startswith("R1"):
                nonh += v * (1 + EQUIPMENT_MGA) if is_floor else v
            else:
                nonh += v * (1 + EQUIPMENT_MGA)
        harness = max(vals["AL-09"], k * nonh)
    nominal = nonh + harness
    sysm = SYSTEM_MARGIN * nominal
    return {"nonharness_nominal_kg": r6(nonh), "harness_kg": r6(harness), "nominal_dry_kg": r6(nominal),
            "system_margin_kg": r6(sysm), "dry_kg": r6(nominal + sysm), "reserve_kg": 0.0}


def closure(line_recs: list) -> dict:
    floors = {r["line"]: r["evidence_floor_kg"] for r in line_recs
              if r["state"] == "ALLOCATION_BELOW_EVIDENCE_FLOOR"}
    tbd_lines = [r["line"] for r in line_recs if r["state"] != "ALLOCATION_BELOW_EVIDENCE_FLOOR"]
    refs = [("INTERNAL_34", INTERNAL_ALLOCS_KG[0], "<=", [53]), ("INTERNAL_36", INTERNAL_ALLOCS_KG[1], "<=", [53]),
            ("HARD_40_WET", WET_LIMIT_KG, "<", [5, 52])]
    residual_status = pending("A9-08")
    readings = {}
    cells = []
    for rid, text in READINGS.items():
        d = reading_dry(rid, floors)
        readings[rid] = {"definition": text, **d}
        if rid in ("R0", "R1", "R2"):
            unresolved = ["every dry line is an owner allocation, not a CBE (row 54)"] + [
                f"{l} allocation below its evidence floor (conflict, MQ-03..MQ-05)" for l in sorted(floors)]
        elif rid == "R3":
            unresolved = [f"{l} EXCLUDED (no evidence)" for l in tbd_lines] + [
                "AL-04 channel/anode/body TBD", "AL-08 plumbing/mounting TBD"]
        else:
            unresolved = [f"{l} at owner allocation (no evidence)" for l in tbd_lines] + [
                "AL-04 channel/anode/body TBD", "AL-08 plumbing/mounting TBD"]
        unresolved.append(f"Xe residual (row 45) {residual_status}")
        for xe in XE_CASES_KG:
            wet_known = r6(d["dry_kg"] + xe)
            for ref_id, ref_kg, cmp, rows in refs:
                exceeded = wet_known > ref_kg if cmp == "<=" else wet_known >= ref_kg
                if exceeded:
                    state = "DOES_NOT_CLOSE"
                    why = (f"known part {wet_known} kg {'>' if cmp == '<=' else '>='} {ref_kg} kg; the pending terms "
                           "are non-negative, so no pending value can restore closure")
                else:
                    state = "NOT_EVALUABLE"
                    why = (f"known part {wet_known} kg leaves {r6(ref_kg - wet_known)} kg; closure needs the imported "
                           "residual and the unresolved lines")
                cells.append({"reading": rid, "xe_case_kg": xe, "reference": ref_id, "reference_kg": ref_kg,
                              "comparator": f"wet {cmp} {ref_kg} kg", "owner_rows": rows, "dry_kg": d["dry_kg"],
                              "wet_known_kg": wet_known, "residual_kg": None, "residual_status": residual_status,
                              "headroom_for_pending_kg": None if exceeded else r6(ref_kg - wet_known),
                              "state": state, "why": why, "unresolved": unresolved})
    return {"readings": readings, "primary_reading": PRIMARY_READING, "cells": cells,
            "floors_substituted_kg": floors,
            "residual": {"value_kg": None, "status": residual_status,
                         "rule": "row 45: booked once in the A9 Xe ledger, imported here; never computed or added "
                                 "a second time in this BOM"},
            "xe_case_content": f"treated as the loaded Xe excluding the residual; whether the row-43 20 % reserve is "
                               f"inside the case value is {pending('A9-08')} (MQ-09)",
            "comparator_note": "34/36 kg are internal allocations (<=, row 53); 40 kg wet is strict (<, row 5). "
                               "CLOSES requires every term resolved; no cell can reach CLOSES while the residual "
                               "import is pending"}


def required_reduction(floors: dict) -> list:
    """Reduction of the six evidence-free allocation lines (AL-09 held at the row-60 rule) needed so that the policy readings fit each reference
    (known part only; deterministic bisection on a uniform scale factor of those lines)."""
    alloc = {lid: kg for lid, _n, kg, _f in ALLOCATIONS}
    others = [l for l in alloc if l not in floors and l != "AL-09"]
    base_other = sum(alloc[l] for l in others)
    k = HARNESS_FRACTION / (1 - HARNESS_FRACTION)

    def dry_at(rid: str, scale: float) -> float:
        nonh = 0.0
        for lid, v in alloc.items():
            if lid == "AL-09":
                continue
            if lid in floors:
                nonh += floors[lid] * (1 + EQUIPMENT_MGA)
            elif rid == "R1E":
                nonh += v * scale
            else:
                nonh += v * scale * (1 + EQUIPMENT_MGA)
        harness = max(alloc["AL-09"], k * nonh)
        return (nonh + harness) * (1 + SYSTEM_MARGIN)

    def fits(rid, scale, target, strict):
        d = dry_at(rid, scale)
        return d < target if strict else d <= target

    out = []
    for rid in ("R1E", "R2E"):
        for xe in XE_CASES_KG:
            for ref_id, ref_kg, strict in (("INTERNAL_34", INTERNAL_ALLOCS_KG[0], False),
                                           ("INTERNAL_36", INTERNAL_ALLOCS_KG[1], False),
                                           ("HARD_40_WET", WET_LIMIT_KG, True)):
                target = ref_kg - xe
                if fits(rid, 1.0, target, strict):
                    need, feasible = 0.0, True
                elif not fits(rid, 0.0, target, strict):
                    need, feasible = None, False
                else:
                    lo, hi = 0.0, 1.0  # fits at lo, not at hi
                    for _ in range(80):
                        mid = (lo + hi) / 2
                        if fits(rid, mid, target, strict):
                            lo = mid
                        else:
                            hi = mid
                    need, feasible = base_other * (1 - lo), True
                out.append({"reading": rid, "xe_case_kg": xe, "reference": ref_id, "other_lines": others,
                            "other_lines_allocated_kg": base_other,
                            "reduction_needed_kg": None if need is None else r6(need),
                            "feasible_by_reducing_other_lines": feasible,
                            "note": "known part only (the pending residual adds to the need); an owner option, "
                                    "not a change"})
    return out


def reallocation_options(line_recs: list) -> dict:
    below = [r for r in line_recs if r["state"] == "ALLOCATION_BELOW_EVIDENCE_FLOOR"]
    gap = r6(sum(r["gap_at_cbe_kg"] for r in below))
    gap_alt = r6(gap - 5.0 + 6.1)
    per_line = []
    for r in below:
        g = r["gap_at_cbe_kg"]
        per_line.append({
            "line": r["line"], "gap_at_cbe_kg": g, "gap_at_row57_mev_kg": r["gap_at_row57_mev_kg"],
            "options": [
                {"id": f"{r['line']}-O1", "option": "move dry development reserve into this line (CBE-level gap)",
                 "consequence": f"reserve {DRY_RESERVE_KG} -> {r6(DRY_RESERVE_KG - g)} kg if applied alone"},
                {"id": f"{r['line']}-O2", "option": "raise the dry target within 40 kg wet by the gap",
                 "consequence": f"dry target {DRY_TARGET_KG} -> {r6(DRY_TARGET_KG + g)} kg if applied alone"},
                {"id": f"{r['line']}-O3", "option": "reduce evidence-free lines by the gap (owner picks which)",
                 "consequence": "moves unverified risk to lines with no evidence either way"},
                {"id": f"{r['line']}-O4", "option": "keep the allocation as a design-to target and carry the gap "
                                                   "as a recorded risk",
                 "consequence": "allocation stays below the verified evidence floor; closure readings R*E apply"},
            ]})
    combined = {
        "total_gap_at_cbe_kg": gap, "total_gap_with_h2_4_ppu_6p1_kg": gap_alt, "reserve_kg": DRY_RESERVE_KG,
        "reserve_alone_sufficient": gap <= DRY_RESERVE_KG,
        "after_reserve_remaining_gap_kg": r6(max(0.0, gap - DRY_RESERVE_KG)),
        "option_B_raise_target_keep_reserve": {
            "dry_target_kg": r6(DRY_TARGET_KG + gap),
            "wet_known_by_case_kg": {str(x): r6(DRY_TARGET_KG + gap + x) for x in XE_CASES_KG},
            "max_xe_before_residual_for_40_kg": r6(WET_LIMIT_KG - DRY_TARGET_KG - gap)},
        "option_C_consume_reserve_then_raise": {
            "dry_target_kg": r6(DRY_TARGET_KG + max(0.0, gap - DRY_RESERVE_KG)), "reserve_after_kg": 0.0,
            "wet_known_by_case_kg": {str(x): r6(DRY_TARGET_KG + max(0.0, gap - DRY_RESERVE_KG) + x)
                                     for x in XE_CASES_KG},
            "consequence": "no dry development reserve left; conflicts with the row-52 20 % internal margin"},
        "note": "R0 frame (owner v0 literal); under rows 52/57/60 see closure readings R1E/R2E and required_reduction",
    }
    return {"per_line": per_line, "combined": combined}


def xe_screen(line_recs: list) -> list:
    al08 = next(r for r in line_recs if r["line"] == "AL-08")
    out = []
    for ref_id, ref_kg in (("INTERNAL_34", 34.0), ("INTERNAL_36", 36.0), ("HARD_40_WET", 40.0)):
        cap = r6(XE_SCREEN_SHARE * ref_kg)
        for xe in XE_CASES_KG:
            for basis, hw in (("allocation", al08["allocation_kg"]), ("evidence_floor", al08["evidence_floor_kg"])):
                v = r6(hw + xe)
                out.append({"reference": ref_id, "cap_kg": cap, "xe_case_kg": xe, "hardware_basis": basis,
                            "hardware_kg": hw, "stored_xe_known_kg": v,
                            "screen": "SCREEN_FLAG" if v > cap else "SCREEN_OK_KNOWN_PART",
                            "note": "row 44: screening cap only, not an entitlement and not a gate; residual pending"})
    return out


# ----------------------------------------------------------------------------------------------------------------------
# (4) H2-7 demands re-evaluated, (5) interface demands
# ----------------------------------------------------------------------------------------------------------------------
H27_REEVAL = {
    "ID-01": ("still applies: H-1 head and MC-1 masses separately; A9 adds the ceramic-coil (row 77) and hot-state B "
              "sensor (row 82) revisions; the MC-1 floor 3.504 kg already exceeds AL-04 3.0 kg", "A9-07", "OPEN"),
    "ID-02": ("still applies; envelope now without a central C1 bore (row 79) and with the downstream coaxial ICP "
              "interface (IP-EXIT / IP-NEU)", "A9-07", "OPEN"),
    "ID-03": ("flight: NOT APPLICABLE (C1 not co-installed, OQ-A902-04); ground: C1 module mass/CG for the stand "
              "(ICD ICP-08)", "A9-07", "RE-SCOPED_TO_GROUND"),
    "ID-04": ("still applies with the A9 Xe valve set: one Hall-anode Xe branch + dual series HP isolation (row 55); "
              "cathode branch removed from flight", "A9-07", "OPEN"),
    "ID-05": ("answered in part: plenum/feed allocation AL-03 1.0 kg (row 54) is now an owner allocation; plenum "
              "mass TBD", "A9-07", "ALLOCATION_GIVEN"),
    "ID-06": ("still applies; PPU scope = Hall discharge + magnet supplies (+ proposed collector/bias supply); C1 "
              "supplies removed; 2.0 kg low end not usable (row 56) -> row-56-compliant range 5.0-10.9 kg vs AL-07 "
              "2.5 kg", "A9-07", "CONFLICT_FLAGGED"),
    "ID-07": ("still applies; thermal hardware now sized for >= 50 K margin + 20 % heat-load margin (row 86) and the "
              "ICP module heat (ICD ICP-43); allocation AL-10 2.5 kg shared with structure", "A9-07", "OPEN"),
    "ID-08": ("still applies; flight telemetry adds ICP channels (row 62) and drops TM-03 (C1)", "A9-07", "OPEN"),
    "ID-09": ("re-scoped: stand payload per configuration (H-1 + MC-1 + C1 module or ICP module + shams), >= 25 kg "
              "design (row 116)", "A9-07", "RE-SCOPED_TO_GROUND"),
    "ID-10": ("SUPERSEDED for A9: the pre-ionizer module interface is historical (row 61); replaced by the ICP ICD "
              "demands ID-22 / ID-23", "A9-10", "SUPERSEDED"),
    "ID-11": ("still applies; analog range 5.044-12.77 kg vs AL-08 1.5 kg; tank per Xe case at 323 K (row 50)",
              "A9-08", "CONFLICT_FLAGGED"),
    "ID-12": ("re-scoped: no single m_Xe_total; 2 / 5 / 10 kg design cases (row 48); residual total imported once "
              "(row 45); C1 cathode term not in flight A9 (row 46)", "A9-08", "PENDING"),
    "ID-13": ("still applies; as-built masses now include the C1 module, the ICP module and the shams, weighed "
              "separately (S1a)", "A9-07", "OPEN"),
    "ID-14": ("still applies; M16 impact in m16_impact, refresh by A9-10", "A9-10", "OPEN"),
}
INCOMING_REEVAL = {
    "H2-1": ("ADOPTED here as the AL-04 evidence floor (3.504 kg magnetic parts)", "ADOPTED"),
    "H2-2": ("C1 analog masses (SITAEL HC1 30 g / HC3 50 g, without cables) now ground/fallback context only; not "
             "flight mass in A9", "RE-SCOPED_TO_GROUND"),
    "H2-3": ("plenum volume range noted (no mass); plenum mass stays TBD under AL-03", "NOTED"),
    "H2-4": ("ADOPTED here as AL-07 context (6.1 kg NG EM1 PPU); floor uses the lowest row-56-admissible analog "
             "(5.0 kg)", "ADOPTED"),
    "H2-5": ("body envelope / mount heat: pending the A9-07 thermal revision (row 86)", "PENDING"),
    "H2-6": ("fixture items stay excluded from the flight mass model (GA-04)", "ADOPTED"),
}


def h27_demands_reevaluated() -> dict:
    h27 = load(PINNED_DELIVERABLES["H27"][0])
    out = []
    for d in h27["interface_demands"]:
        if d["id"] not in H27_REEVAL:
            raise KeyError(f"H2-7 demand {d['id']} not re-evaluated")
        disp, lane, st = H27_REEVAL[d["id"]]
        out.append({"h2_7_id": d["id"], "from": d["from"], "to": d["to"], "quantity_v1": d["quantity"],
                    "range_v1": d.get("range"), "units": d["units"], "a9_disposition": disp,
                    "routed_to": f"{lane} {A9_LANES[lane]}", "a9_status": st})
    inc = []
    for dem in h27["lane_consumption"]["demands"]:
        lane = dem["lane"]
        if lane not in INCOMING_REEVAL:
            raise KeyError(f"incoming H2-7 demand from {lane} not re-evaluated")
        disp, st = INCOMING_REEVAL[lane]
        inc.append({"from_lane": lane, "quantity_v1": dem["demand"]["quantity"], "units": dem["demand"]["units"],
                    "value_v1": dem["demand"]["value"], "a9_disposition": disp, "a9_status": st})
    return {"outgoing_from_h2_7_v1": out, "incoming_to_h2_7_v1": inc}


def interface_demands() -> list:
    def d(did, frm, to, quantity, value, units, status):
        return {"id": did, "from": frm, "to": to, "quantity": quantity, "value": value, "units": units,
                "status": status}
    A7, A8, A9L, A10 = (f"A9-07 {A9_LANES['A9-07']}", f"A9-08 {A9_LANES['A9-08']}", f"A9-09 {A9_LANES['A9-09']}",
                        "A9-10")
    ME = f"A9-06 {LANE_DIR}/"
    return [
        d("MA9-ID-01", ME, A7, "MC-1 mass after the ceramic-insulated coil (row 77), FeCo-2V / pure-iron (row 76) "
          "and hot-state B sensor provision (row 82) revisions; H-1 channel/anode/body masses (closes AL-04)", None,
          "kg", pending("A9-07")),
        d("MA9-ID-02", ME, A7, "confirmation that flight H-1 carries no central C1 bore/mount (external C1 on the "
          "ground article only, row 79) and the resulting mass change", None, "kg", pending("A9-07")),
        d("MA9-ID-03", ME, A7, "mass effect of any anode/collector coating or O-resistant material choice (rows 106, "
          "132; A9-03 collector clarification)", None, "kg", f"{TBD} coupon programme results"),
        d("MA9-ID-04", ME, A7, "A9 Xe valve set: one Hall-anode branch + dual series HP isolation (row 55), cathode "
          "branch removed; PROPOSED analog reading 0.455 kg (A9B-10 + A9B-11)", 0.455, "kg", "PROPOSED"),
        d("MA9-ID-05", ME, A7, "flight PPU scope for the A9 partition (row 110) and 100 V internal bus (row 111), "
          "without C1 supplies: mass/CBE (closes AL-07)", None, "kg", pending("A9-07")),
        d("MA9-ID-06", ME, A7, "thermal hardware mass for >= 50 K margin + 20 % heat-load margin (row 86) incl. the "
          "ICP module heat (ICP-43) (AL-10)", None, "kg", pending("A9-07")),
        d("MA9-ID-07", A7, ME, "revised H2-1/H2-4/H2-5/H2-3 masses with basis and evidence class", None, "kg",
          pending("A9-07")),
        d("MA9-ID-08", ME, A8, "Xe residual total (row 45) for import into the mass BOM (booked once there)", None,
          "kg", pending("A9-08")),
        d("MA9-ID-09", ME, A8, "content of the 2 / 5 / 10 kg design cases: loaded Xe incl. or excl. the row-43 20 % "
          "reserve; C1 cathode term outside the flight cases (row 46)", None, "kg", pending("A9-08")),
        d("MA9-ID-10", ME, A8, "tank volume and mass per Xe case sized at 323 K with verified EOS and MEOP/safety "
          "factors (row 50) (closes A9B-07)", None, "kg / l", pending("A9-08")),
        d("MA9-ID-11", ME, A8, "G-XE variant Xe (HIQ-06) booked separately; primary G-REUSE m_Xe,ICP = 0", 0.0, "kg",
          "OWNER_GIVEN (A9.1 HIQ-06_accounting)"),
        d("MA9-ID-12", ME, A8, "Xe hardware allocation conflict (AL-08 1.5 kg vs 5.044 kg analog floor) and row-44 "
          "screening results (xe_screen)", [1.5, 5.044], "kg", "CONFLICT_FLAGGED (MQ-05)"),
        d("MA9-ID-13", ME, A9L, "RFQ mass ceilings = owner v0 allocations per line: ICP head (+ collector if MQ-07 "
          "accepted) <= 2.0 kg; flight RF generator + matching (+ feedthrough if MQ-07) <= 1.5 kg combined; "
          "compressor + drive <= 5.5 kg; the lab 0-500 W RF generator and ground items carry no flight ceiling",
          {"AL-05": 2.0, "AL-06": 1.5, "AL-02": 5.5}, "kg", "PROPOSED (ceiling reading CBE vs MEV: MQ-01)"),
        d("MA9-ID-14", ME, A9L, "RFQ items whose ceiling is below the verified evidence floor: Hall PPU (AL-07 2.5 "
          "kg vs 5.0 kg), Xe tank/regulator/valves (AL-08 1.5 kg vs 5.044 kg), H-1/MC-1 (AL-04 3.0 kg vs 3.504 kg); "
          "state the allocation and request the supplier's mass, do not present the ceiling as feasible",
          {"AL-04": [3.0, 3.504], "AL-07": [2.5, 5.0], "AL-08": [1.5, 5.044]}, "kg",
          "BLOCKED_BY_OWNER_QUESTIONS (MQ-03..MQ-05)"),
        d("MA9-ID-15", ME, A9L, "thrust-stand moving payload capacity (not a ceiling): >= 25 kg (row 116)", 25.0, "kg",
          "OWNER_GIVEN (row 116)"),
        d("MA9-ID-16", ME, A10, "M16 allocation-column update, new M16 rows for the ICP neutralizer and the flight RF "
          "chain, pre-ionizer interface row superseded (m16_impact)", None, "-", "PROPOSED"),
        d("MA9-ID-17", ME, A10, "recorder discrepancy: A9 flag 4.54-12.77 kg vs H2-7 ID-11 5.044-12.77 kg", [4.54, 5.044],
          "kg", "PROPOSED (MQ-08)"),
        d("MA9-ID-18", ME, A10, "re-run this closure after A9-07 / A9-08 merge (builder --check reproduces)", None, "-",
          "PENDING"),
        d("MA9-ID-19", ME, "A9-01 docs/experiments/hall_icp/prereg_framework/ (DQ-HI-DMASS)", "item-delta set of "
          "hall_icp_neutralizer vs the C1 fallback flight variant: ICP adds A9B-17..A9B-22; C1 variant adds "
          "A9B-C01..A9B-C06; masses TBD", None, "kg", "PROPOSED"),
        d("MA9-ID-20", ME, "A9-03 schemas/interfaces/icp_neutralizer_icd_v1.json (ID-22 / ID-23)", "ICD ID-22 (new BOM "
          "lines) answered by the A9 flight BOM; ID-23 flight allocations vs evidence answered by line_checks; "
          "module masses/CG per serial stay TBD (S1a)", None, "kg", "ANSWERED_IN_PART"),
        d("MA9-ID-21", "A9-02 docs/architecture_comparison/power_boundary_a9/", ME, "bus slots used to map BOM items; "
          "C1 slots NOT_INSTALLED in hall_icp_neutralizer (consistent with OQ-A902-04)", None, "-", "USED"),
        d("MA9-ID-22", ME, "H-1 / MC-1 / C-1 (hardware_requirements_v1; S1a HW-ENV-08)", "as-built masses of H-1, "
          "MC-1, the C1 module, the ICP module and shams, weighed separately", None, "kg", f"{TBD} S1a"),
    ]


# ----------------------------------------------------------------------------------------------------------------------
# (c) owner answers, (d) questions, (e) historical reuse, (f) M16, (g) H3/H4
# ----------------------------------------------------------------------------------------------------------------------
APPLIED = {
    5: "40 kg is a WET gate incl. Xe + tank: closure adds the Xe cases and the imported residual to the dry mass",
    6: "flight Xe system retained (tank, regulator, isolation, anode-feed control) for the bounded Xe-capable mode",
    43: "20 % Xe reserve belongs to the Xe ledger; case content asked of A9-08 (MA9-ID-09)",
    44: "stored-Xe screening at 0.25 x reference reported as SCREEN_FLAG / SCREEN_OK_KNOWN_PART, never a gate",
    45: "residual imported once from A9-08 (PENDING); never computed here",
    46: "C1 cathode Xe term (5.4 kg) not carried in the primary A9 flight BOM; C1 fallback variant only",
    47: "ICP / RF electronics are separate new items (A9B-17..22), not mapped into the old cathode line",
    48: "closure evaluated for 2 / 5 / 10 kg Xe design cases; no single load frozen",
    50: "tank sizing at 323 K demanded from A9-08 (MA9-ID-10)",
    51: "filter/getter dropped from the ICP-only flight branch (A9B-C05)",
    52: "20 % internal system margin applied in readings R1/R2/R*E/R3; 40 kg wet kept hard",
    53: "34 kg and 36 kg internal allocations both evaluated",
    54: "owner v0 dry allocations tabulated as OWNER_ALLOCATION (never CBEs) and compared line by line with evidence",
    55: "dual series isolation on the HP Xe path (A9B-10); no duplicated thruster / ICP / PPU",
    56: "NASA SBIR 2 kg PPU excluded from the AL-07 evidence floor",
    57: "ECSS-D-like 20 % equipment margin on unselected parts (R2 on allocations; floors in R1E/R2E/R3)",
    58: "legacy uncited MGA in abep_sim/mass_bom.py not used on the A9 path (preserved, untouched)",
    59: "A9 BOM: ICP neutralizer, RF generator/matching/feedthrough, collector/bias added; pre-ionizer items removed "
        "from the A9 BOM only",
    60: "harness 5 % of nominal dry until a routed harness exists; conflict with the 1.0 kg line flagged (PC-01)",
    61: "pre-ionizer interface provision removed (A9B-R08); dedicated downstream ICP interface instead",
    62: "ICP telemetry added to the flight sensor item (A9B-29)",
    69: "ICP assist magnet variant-only (A9B-24)",
    72: "lab 0-500 W RF generator is ground capability only, no flight mass",
    76: "MC-1 material baseline noted on A9B-16",
    77: "ceramic-insulated coil revision demanded from A9-07 (MA9-ID-01)",
    79: "external C1 on the ground article only; flight H-1 neutralizer-agnostic",
    86: ">= 50 K margin drives the thermal hardware item (A9B-30, MA9-ID-06)",
    90: "cathode-branch series isolation drops with the C1 branch (A9B-C04)",
    110: "PPU partition used to scope AL-07 and the collector/bias supply (A9B-22)",
    116: ">= 25 kg stand payload passed to A9-09 as a capacity (MA9-ID-15)",
    133: "shams are ground items, excluded from flight mass (GA-03)",
}


def owner_answers_applied() -> list:
    ans = answers_by_row()
    return [{"row": r, "covers_ids": ans[r]["covers_ids"], "answer_sha256": answer_fingerprint(r), "how_applied": h}
            for r, h in sorted(APPLIED.items())]


def a91_applied() -> list:
    items = {
        "OQ-A902-04": "C1 not co-installed in the primary A9 flight BOM; C1 items dropped from flight (A9B-C01..C07)",
        "OQ-A902-05": "ICP feed flow control booked only in G-ATM / G-XE (A9B-23); capped port stays (A9B-17)",
        "HIQ-06": "G-REUSE primary: no dedicated ICP gas hardware or Xe in the primary BOM",
        "OQ-A902-03": "lab 0-500 W RF is a test capability only",
        "A9-03-matching": "matching network off the moving platform (ground); flight matching network is A9B-20",
        "A9-03-collector": "flight collector material not frozen (A9B-18)",
        "A9-03-planes": "IP-DN historical and unchanged; IP-EXIT / IP-NEU used for the ICP mount",
        "ICP-46": "C1 keeper pulse isolation is a C1-module (ground) item in A9",
    }
    return [{"decision": k, "source": a91_src(k)[0], "how_applied": v} for k, v in items.items()]


def open_owner_questions(line_recs: list, opts: dict, reductions: list) -> list:
    g = {r["line"]: r for r in line_recs}
    red = {(x["reading"], x["xe_case_kg"], x["reference"]): x["reduction_needed_kg"] for x in reductions}
    return [
        {"id": "MQ-01", "question": "Are the row-54 allocations MEV-level line budgets (row-57 equipment margin "
         "inside) or CBE-level budgets (row-57 margin on top)? RFQ ceilings and closure depend on it.",
         "proposed_answer": "owner call; consequence: CBE-level (R2) gives a dry mass of "
         f"{reading_dry('R2', {})['dry_kg']} kg before any evidence conflict, MEV-level (R1) "
         f"{reading_dry('R1', {})['dry_kg']} kg; the owner v0 literal (R0) 28 kg"},
        {"id": "MQ-02", "question": "Is the 4 kg dry development reserve (row 54) the row-52 20 % internal system "
         "margin, or additional to it?", "proposed_answer": "treat it as the realization of row 52 and raise it to "
         "4.8 kg (20 % of 24 kg), i.e. dry target 28.8 kg, OR keep 28 kg and cut allocations to 23.333 kg; owner call"},
        {"id": "MQ-03", "question": f"AL-04 Hall head+magnet 3.0 kg is below the verified MC-1 magnetic-parts floor "
         f"3.504 kg (gap {g['AL-04']['gap_at_cbe_kg']} kg at CBE). Which re-allocation?",
         "proposed_answer": "minimal: move 0.504 kg (0.504 + channel/anode/body once known) from the dry reserve "
         "(AL-04-O1), and ask A9-07 for the winding-window mass/power trade before freezing; consequence: reserve "
         "3.496 kg"},
        {"id": "MQ-04", "question": f"AL-07 Hall PPU 2.5 kg is below every row-56-admissible measured PPU analog "
         f"(lowest 5.0 kg; H2-4 6.1 kg). Which re-allocation?", "proposed_answer": "owner call; minimal options: "
         "AL-07-O1..O4; note moving 2.5 kg from reserve leaves 1.5 kg, and the combined three-line gap "
         f"({opts['combined']['total_gap_at_cbe_kg']} kg) exceeds the 4 kg reserve"},
        {"id": "MQ-05", "question": f"AL-08 Xe hardware 1.5 kg is below the H2-7 analog floor 5.044 kg (regulator + "
         "valves alone 1.544 kg). Which re-allocation, and does AL-08 include tank mounting/thermal and plumbing?",
         "proposed_answer": "owner call; proposed scope: AL-08 = A6 stored-Xe hardware (tank, regulator, valves, "
         "plumbing, mounting/thermal); raise to >= the A9-08 tank result + regulator + valves"},
        {"id": "MQ-06", "question": "Row 60 harness (5 % of nominal dry) alone is 1.21-1.45 kg, above the whole "
         "'controls/harness 1.0 kg' line. Split the line into controls and harness?",
         "proposed_answer": "YES: harness by row-60 policy as its own line; controls as a separate allocation"},
        {"id": "MQ-07", "question": "Map the A9 items that row 54 does not name: collector/bias electrode (AL-05?), "
         "collector/bias supply (AL-07?), RF feedthrough/coax (AL-06?), flight sensors and valve drivers (AL-09?), "
         "Xe tank mounting/thermal and plumbing (AL-08?).", "proposed_answer": "accept the PROPOSED_MAPPING entries "
         "in the A9 flight BOM"},
        {"id": "MQ-08", "question": "The A9 recorder flag quotes the combined Xe analog as 4.54-12.77 kg; H2-7 ID-11 "
         "gives 5.044-12.77 kg. Record the H2-7 value as governing in the A9-10 reconciliation?",
         "proposed_answer": "YES (the A9 file stays immutable; the verified H2-7 arithmetic is 3.5 + 0.974 + 0.57)"},
        {"id": "MQ-09", "question": "Do the 2 / 5 / 10 kg Xe design cases (row 48) include the row-43 20 % reserve, "
         "with the row-45 residual on top?", "proposed_answer": "YES: case = loaded usable Xe incl. reserve; residual "
         "imported on top from A9-08"},
        {"id": "MQ-10", "question": "Under the primary policy reading with the three evidence floors (R2E) the dry "
         "mass alone exceeds 40 kg. Accept that closure requires reducing the six evidence-free lines "
         "AL-01/02/03/05/06/10 (harness line held at the row-60 rule; e.g. by "
         f"{red[('R2E', 2.0, 'HARD_40_WET')]} kg at Xe 2 kg against 40 kg), or revisit the margin reading?",
         "proposed_answer": "owner call; no allocation is changed by this lane"},
    ]


def historical_reuse() -> dict:
    return {
        "artifacts": [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in HISTORICAL.items()],
        "reused": [
            "mass_bom v1: MEV definition (CBE x (1 + MGA) + system margin + propellant), ESA margin-policy source, "
            "item ids as predecessors of the A9 items",
            "H2-7 v1: line-item ids, analog planning values (copied by pointer), harness convention f/(1-f), "
            "interface demands ID-01..ID-14 and incoming demands (re-evaluated for A9)",
            "pre-ionizer ICD: only as the source of the removed interface-provision line (A9B-R08)",
        ],
        "not_reused": [
            "mass_bom v1 items rf_source / rf_generator / rf_matching_network / ecr_* (pre-ionizer only, row 59)",
            "H2-7 R17 reserved pre-ionizer interface provision (row 61)",
            "H2-7 R06.m_Xe_cathode 5.4 kg and R06.m_Xe_residual 0.108 kg (C1 term not in flight A9, row 46; residual "
            "booked once in the A9 Xe ledger, row 45)",
            "H2-7 NASA SBIR 2 kg PPU low end (row 56)",
            "legacy uncited MGA dict in abep_sim/mass_bom.py (row 58)",
            "H2-7 A5 34-36 kg allocation roll-up as a result (re-evaluated here against the owner v0 allocations)",
        ],
        "never_edited": "all listed artifacts are read only; mass_bom v1 and H2-7 v1 sha256 are fixed in this builder",
    }


def m16_impact() -> list:
    m16 = {r["row"]: r for r in load(READ_DELIVERABLES["M16"])["rows"]}
    rows = [
        (1, "AL-01", "allocation column: OWNER_ALLOCATION v0 (3.5 kg shared with filter/duct); state UNVERIFIABLE_TBD"),
        (2, "AL-01", "allocation column: shared AL-01; state UNVERIFIABLE_TBD"),
        (3, "AL-02", "allocation column: OWNER_ALLOCATION v0 5.5 kg; state UNVERIFIABLE_TBD"),
        (4, "AL-03", "allocation column: shared AL-03 1.0 kg; state UNVERIFIABLE_TBD"),
        (5, "AL-03", "allocation column: shared AL-03 1.0 kg; state UNVERIFIABLE_TBD"),
        (6, "AL-08", "allocation BELOW evidence floor (shared AL-08); Xe load as 2/5/10 kg cases; C1 term out of flight"),
        (7, "AL-08", "allocation BELOW evidence floor (shared AL-08)"),
        (8, "AL-08", "cathode-feed branch removed from flight; dual series HP isolation (row 55)"),
        (9, "AL-04", "allocation BELOW evidence floor (shared AL-04); no central C1 bore in flight"),
        (10, "AL-04", "allocation BELOW evidence floor: MC-1 3.504 kg > 3.0 kg"),
        (11, None, "flight C1 removed from the primary A9 BOM (OQ-A902-04); row becomes ground reference / fallback"),
        (12, "AL-07", "allocation BELOW evidence floor; ICP RF generator/matching/bias join this row or a new row"),
        (13, "AL-10", "allocation shared AL-10 2.5 kg; >= 50 K margin drives mass; UNVERIFIABLE_TBD"),
        (14, "AL-09", "allocation shared AL-09; harness policy conflict PC-01"),
        (15, "AL-09", "ICP telemetry added, TM-03 dropped; PROPOSED mapping to AL-09"),
        (16, "AL-10", "allocation shared AL-10; downstream coaxial ICP mount added"),
        (17, None, "SUPERSEDED for A9 (pre-ionizer interface removed from the A9 BOM); propose new rows 'ICP "
                   "neutralizer head' (AL-05) and 'flight RF chain' (AL-06) to A9-10"),
    ]
    return [{"m16_row": r, "key": m16[r]["key"], "name": m16[r]["name"], "allocation_line": al, "how_touched": h,
             "refresh_owner": "A9-10"} for r, al, h in rows]


def h3_h4_inputs() -> dict:
    return {
        "h3_quotation_mass_fields": [
            {"item": "flight-representative ICP neutralizer head", "ceiling": "AL-05 2.0 kg (reading MQ-01)"},
            {"item": "flight RF generator + matching network (+ feedthrough if MQ-07)", "ceiling": "AL-06 1.5 kg combined"},
            {"item": "Hall PPU (discharge + magnet supplies)", "ceiling": "AL-07 2.5 kg - BLOCKED by MQ-04 (below floor)"},
            {"item": "Xe tank / regulator / valves", "ceiling": "AL-08 1.5 kg - BLOCKED by MQ-05 (below floor)"},
            {"item": "compressor + drive", "ceiling": "AL-02 5.5 kg"},
            {"item": "thrust stand", "ceiling": "capacity >= 25 kg moving payload (row 116), not a ceiling"},
        ],
        "h4_measurements": [
            {"stage": "S1a", "measure": "weigh H-1, MC-1, C1 module, ICP module, shams separately (ID-13 / ICD ICP-08)"},
            {"stage": "S1a", "measure": "stand payload and CG per configuration against >= 25 kg (row 116)"},
            {"stage": "after-evidence", "measure": "replace allocations by CBEs line by line and re-run --check"},
        ],
    }


# ----------------------------------------------------------------------------------------------------------------------
# items table (a)
# ----------------------------------------------------------------------------------------------------------------------
def items_table(ev: dict, line_recs: list) -> list:
    out = []

    def I(iid, name, value, units, basis, source, evidence_class, status, freeze_point):
        if evidence_class is not None and evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(evidence_class)
        if freeze_point not in FREEZE_POINTS:
            raise ValueError(freeze_point)
        out.append({"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
                    "evidence_class": evidence_class, "status": status, "freeze_point": freeze_point})

    for lid, name, kg, _f in ALLOCATIONS:
        I(f"MA-{lid}", f"owner v0 dry allocation: {name}", kg, "kg", "row 54", row_src(54), "owner-allocation",
          "OWNER_ALLOCATION (not a CBE)", "NOW")
    I("MA-SUM", "sum of owner v0 dry allocations", ALLOC_SUM_KG, "kg", "row 54", row_src(54), "owner-allocation",
      "OWNER_ALLOCATION", "NOW")
    I("MA-RES", "dry development reserve", DRY_RESERVE_KG, "kg", "row 54", row_src(54), "owner-allocation",
      "OWNER_ALLOCATION", "NOW")
    I("MA-TGT", "dry target", DRY_TARGET_KG, "kg", "row 54", row_src(54), "owner-allocation", "OWNER_ALLOCATION", "NOW")
    I("MP-01", "hard wet-system mass limit (strict)", WET_LIMIT_KG, "kg", "rows 5, 52", row_src(5, 52), None,
      "OWNER_GIVEN (RFP as recorded; verify against the official RFP)", "NOW")
    I("MP-02", "internal design allocations", list(INTERNAL_ALLOCS_KG), "kg", "row 53", row_src(53), None,
      "OWNER_GIVEN", "NOW")
    I("MP-03", "internal system margin (fraction of nominal dry)", SYSTEM_MARGIN, "-", "row 52", row_src(52), None,
      "OWNER_GIVEN", "NOW")
    I("MP-04", "default equipment margin for new/unselected parts", EQUIPMENT_MGA, "-", "row 57", row_src(57), None,
      "OWNER_GIVEN", "NOW")
    I("MP-05", "harness allocation (fraction of nominal dry) until a routed harness exists", HARNESS_FRACTION, "-",
      "row 60", row_src(60), None, "OWNER_GIVEN", "NOW")
    I("MP-06", "Xe load design cases", list(XE_CASES_KG), "kg", "row 48", row_src(48), "owner-allocation",
      "OWNER_GIVEN (no single load frozen)", "after-evidence")
    I("MP-07", "stored-Xe screening share of the mass reference", XE_SCREEN_SHARE, "-", "row 44", row_src(44), None,
      "OWNER_GIVEN (screening cap, not an entitlement)", "NOW")
    I("MP-08", "Xe residual (unusable) total", None, "kg", "row 45: imported once", row_src(45), None,
      pending("A9-08"), "after-evidence")
    I("ME-01", "MC-1 iron + copper mass (RP-1, f_NI 2)", r6(ev["mc1_iron"]["value"] + ev["mc1_copper"]["value"]), "kg",
      "copied H2-1 H21-24 (sum)", [ev["mc1_iron"], ev["mc1_copper"]], "model-derived", "PRELIMINARY", "after-evidence")
    I("ME-02", "PPU analog mass (NG 1 kW EM1)", ev["ppu_h24"]["value"], "kg", "copied H2-4 H24-34",
      [ev["ppu_h24"]], "measured", "SOURCED (other hardware)", "after-evidence")
    I("ME-03", "PPU analog mass (SETS, 100-500 W; secondary listing, verify)", ev["an_sets"]["value"], "kg",
      "copied H2-7 AN-SETS-PPU", [ev["an_sets"]], "measured", "SOURCED (other hardware)", "after-evidence")
    I("ME-04", "PPU analog mass (TAS PPU Mk1 incl. TSU)", ev["an_tas"]["value"], "kg", "copied H2-7 AN-TAS-PPUMK1-MASS",
      [ev["an_tas"]], "measured", "SOURCED (other hardware)", "after-evidence")
    I("ME-05", "NASA SBIR PPU development target (EXCLUDED as evidence, row 56)", ev["an_nasa"]["value"], "kg",
      "copied H2-7 AN-NASA-LM-PPU-TARGET", [ev["an_nasa"]], "assumed", "EXCLUDED_AS_CBE (row 56)", "NOW")
    I("ME-06", "Xe tank + regulator + valves analog planning range (H2-7 ID-11)", ev["h27_id11"]["value"], "kg",
      "copied H2-7 ID-11", [ev["h27_id11"]], "inferred", "PRELIMINARY (analog)", "after-evidence")
    I("ME-07", "Hall thruster incl. magnetic circuit analog range (H2-7 H27-14)", ev["h27_hall"]["value"], "kg",
      "copied H2-7 H27-14", [ev["h27_hall"]], "inferred", "PRELIMINARY (analog; context)", "after-evidence")
    for r in line_recs:
        I(f"MS-{r['line']}", f"line state {r['owner_name']}", r["state"], "-", "line_checks", ["line_checks"], None,
          "DERIVED", "after-evidence")
    return out


# ----------------------------------------------------------------------------------------------------------------------
# build + render
# ----------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    pins = check_pins()
    check_owner_fragments()
    ev = evidence()
    bom = bom_items(ev)
    lines = line_checks(ev, bom)
    clo = closure(lines)
    reds = required_reduction(clo["floors_substituted_kg"])
    opts = reallocation_options(lines)
    read_pins = [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in READ_DELIVERABLES.items()]
    prereg = load(READ_DELIVERABLES["PREREG_A9"])
    if "DQ-HI-DMASS" not in json.dumps(prereg):
        raise KeyError("DQ-HI-DMASS missing from the A9-01 framework")
    icd = load(READ_DELIVERABLES["ICD_A9"])
    icd_ids = {x["id"] for x in icd["interface_demands"]}
    for need in ("ID-22", "ID-23"):
        if need not in icd_ids:
            raise KeyError(f"ICD demand {need} missing")
    return {
        "schema": "mass_a9_v1",
        "id": "fo_a9_06_mass_reconciliation_v1",
        "lane": "fo_a9_06_mass_reconciliation",
        "trigger": "T_A9_06_MASS_RECONCILIATION",
        "owner_step": "A9.1 step 2 (A9-06)",
        "title": "A9 mass reconciliation: A9 flight BOM, owner v0 dry allocations vs verified evidence, wet closure",
        "status": "DRAFT_PENDING_OWNER",
        "a9_status": load(DECISIONS["A9"][0])["status"],
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": TEST,
        "configurations": list(CONFIGURATIONS),
        "outcome_vocabulary": list(OUTCOME_VOCABULARY),
        "status_not_outcome": list(STATUS_NOT_OUTCOME),
        "line_states": list(LINE_STATES),
        "closure_states": list(CLOSURE_STATES),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "freeze_points": list(FREEZE_POINTS),
        "what_this_is_not": [
            "not a performance prediction (no thrust, efficiency, discharge current, electron current or plasma state)",
            "not a CBE of Vyovrinda hardware: owner allocations are allocations; analog masses are other hardware",
            "not an architecture selection: no winner between hall_c1_reference and hall_icp_neutralizer; A9 stays "
            "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE; Bundle 1 NO_BASELINE_YET",
            "not a change of any owner allocation; not a frozen Xe load; not a residual booking",
        ],
        "governing_decision": {"path": DECISIONS["A9"][0], "sha256": DECISIONS["A9"][1]},
        "owner_answers": {"path": DECISIONS["ANS"][0], "sha256": DECISIONS["ANS"][1],
                          "verbatim_pack": {"path": DECISIONS["PACK"][0], "sha256": DECISIONS["PACK"][1]}},
        "a9_1_followup": {"path": DECISIONS["A91"][0], "sha256": DECISIONS["A91"][1],
                          "verbatim": {"path": DECISIONS["A91_MD"][0], "sha256": DECISIONS["A91_MD"][1]}},
        "pins": pins,
        "read_deliverables": read_pins,
        "never_pinned": NEVER_PINNED,
        "pending_lanes": A9_LANES,
        "items": items_table(ev, lines),
        "a9_flight_bom": bom,
        "line_checks": lines,
        "policy_checks": policy_checks(),
        "reallocation_options": opts,
        "wet_closure": clo,
        "required_reduction_of_evidence_free_lines": reds,
        "xe_screen_row44": xe_screen(lines),
        "h2_7_demands_reevaluated": h27_demands_reevaluated(),
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(),
        "a9_1_decisions_applied": a91_applied(),
        "open_owner_questions": open_owner_questions(lines, opts, reds),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4_inputs(),
        "compliance": {
            "no_hall_performance_source": "no Hall transport closure, screening candidate, abep_sim/plasma_devices.py "
                                          "or withdrawn v1.2-v1.6 number is read",
            "no_new_numbers": "every number is owner-given (row), copied by pointer from a pinned verified deliverable, "
                              "or deterministic arithmetic on those",
            "residual_once": "the Xe residual is never computed here (row 45)",
            "allocations_unchanged": "no owner allocation is modified; conflicts are owner questions MQ-01..MQ-10",
            "pure": "standard-library builder; not wired into archengine; no frozen data, goldens or modules touched",
            "no_contact": "no supplier, lab or author contact; no web access needed by this lane",
        },
    }


def _fmt(v) -> str:
    if v is None:
        return "TBD"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return ", ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return str(v)


def render_md(doc: dict) -> str:
    L = []
    a = L.append
    a("# A9 mass reconciliation (A9-06)")
    a("")
    a(f"Generated by `{doc['generated_by']}` from `{OUT_JSON}` (do not edit by hand; `--check` verifies). "
      f"Status `{doc['status']}`; A9 status `{doc['a9_status']}`. Base commit `{doc['base_commit']}`.")
    a("")
    a("**What this is not:** " + "; ".join(doc["what_this_is_not"]) + ".")
    a("")
    a("## Pinned decisions and inputs")
    a("")
    a("| key | path | sha256 | kind |")
    a("|---|---|---|---|")
    for p in doc["pins"]:
        a(f"| {p['key']} | `{p['path']}` | `{p['sha256']}` | {p['kind']} |")
    a("")
    a("Read for ids/structure (sha256 at build): " + "; ".join(f"`{p['path']}` `{p['sha256'][:12]}`"
                                                             for p in doc["read_deliverables"]) + ".")
    a("Never pinned (mutable governance): " + ", ".join(f"`{p}`" for p in doc["never_pinned"]) + ".")
    a("")
    a("## (a) Items / parameters")
    a("")
    a("| id | name | value | units | basis | evidence class | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        a(f"| {it['id']} | {it['name']} | {_fmt(it['value'])} | {it['units']} | {it['basis']} | "
          f"{it['evidence_class'] or '-'} | {it['status']} | {it['freeze_point']} |")
    a("")
    a("## (1) A9 flight BOM (row 59, A9.1 OQ-A902-04)")
    a("")
    bom = doc["a9_flight_bom"]
    for sect, title in (("flight", "Flight items (primary A9 architecture `hall_icp_neutralizer`)"),
                        ("variant_only", "Variant-only items (not in the primary flight BOM)"),
                        ("removed_preionizer_only", "Removed from the A9 BOM (pre-ionizer only; historical v1 unchanged)"),
                        ("c1_dropped_from_flight", "C1-specific items dropped from the primary flight BOM "
                                                   "(ground reference/control `hall_c1_reference`, fallback variant)")):
        a(f"### {title}")
        a("")
        a("| id | item | BOM status | allocation line | predecessor (mass_bom v1 / H2-7) | A9 bus slots | M16 | value | "
          "evidence class | status | freeze |")
        a("|---|---|---|---|---|---|---|---|---|---|---|")
        for it in bom[sect]:
            pred = " / ".join(x for x in [it["predecessor_mass_bom_v1"] or "", ", ".join(it["predecessor_h2_7_lines"])] if x)
            al = it["allocation_line"] or "-"
            if it["allocation_mapping"] != "OWNER_LINE":
                al += f" ({it['allocation_mapping']})"
            a(f"| {it['id']} | {it['name']} | {it['bom_status']} | {al} | {pred or '-'} | "
              f"{', '.join(it['power_slots_a9']) or '-'} | {it['m16_row'] or '-'} | {_fmt(it['value'])} | "
              f"{it['evidence_class'] or '-'} | {it['status']} | {it['freeze_point']} |")
        a("")
    a("### Ground-article-only items (never flight mass)")
    a("")
    for g in bom["ground_article_only"]:
        a(f"* **{g['id']}** {g['item']}: {g['rule']}")
    a("")
    a("A9 bus-boundary C1 slots in `hall_icp_neutralizer`: " + _fmt(bom["c1_slots_check"]) + ".")
    a("")
    a("## (2) Owner v0 dry allocations vs verified evidence")
    a("")
    a("| line | owner allocation (kg, OWNER_ALLOCATION) | evidence floor (kg) | partial | gap CBE (kg) | gap row-57 MEV "
      "(kg) | state |")
    a("|---|---|---|---|---|---|---|")
    for r in doc["line_checks"]:
        a(f"| {r['line']} {r['owner_name']} | {r['allocation_kg']:g} | {_fmt(r['evidence_floor_kg'])} | "
          f"{_fmt(r['floor_is_partial'])} | {_fmt(r['gap_at_cbe_kg'])} | {_fmt(r['gap_at_row57_mev_kg'])} | "
          f"**{r['state']}** |")
    a("")
    for r in doc["line_checks"]:
        a(f"* **{r['line']}** ({', '.join(r['bom_items'])}): {r['arithmetic']}.")
    a("")
    a("State rule: floor = sum of verified evidence over the resolved constituents (TBD constituents add >= 0). "
      "Floor > allocation -> ALLOCATION_BELOW_EVIDENCE_FLOOR (robust); floor <= allocation with TBD constituents or no "
      "evidence -> ALLOCATION_UNVERIFIABLE_TBD; all constituents resolved and floor <= allocation -> CONSISTENT. "
      "Floors are masses of other hardware or a preliminary Vyovrinda design point, not physical lower bounds.")
    a("")
    a("### Policy checks")
    a("")
    for p in doc["policy_checks"]:
        a(f"* **{p['id']}** {p['rule']}: {_fmt(p['arithmetic'])}. {p['finding']}")
    a("")
    a("### Minimal re-allocation options (the owner decides; nothing is changed here)")
    a("")
    for pl in doc["reallocation_options"]["per_line"]:
        a(f"* **{pl['line']}** gap {pl['gap_at_cbe_kg']:g} kg (CBE), {pl['gap_at_row57_mev_kg']:g} kg (row-57 MEV): " +
          "; ".join(f"{o['id']} {o['option']} -> {o['consequence']}" for o in pl["options"]))
    c = doc["reallocation_options"]["combined"]
    a(f"* **combined:** {_fmt({k: v for k, v in c.items() if not isinstance(v, dict)})}")
    a(f"  * option B (raise target, keep reserve): {_fmt(c['option_B_raise_target_keep_reserve'])}")
    a(f"  * option C (consume reserve, then raise): {_fmt(c['option_C_consume_reserve_then_raise'])}")
    a("")
    a("## (3) Wet-mass closure (< 40 kg wet, row 5; 34 / 36 kg internal, row 53; Xe cases row 48)")
    a("")
    clo = doc["wet_closure"]
    a(f"Primary reading: **{clo['primary_reading']}**. Residual: {clo['residual']['status']} "
      f"({clo['residual']['rule']}). {clo['xe_case_content']}. {clo['comparator_note']}.")
    a("")
    a("| reading | definition | dry (kg) |")
    a("|---|---|---|")
    for rid, rd in clo["readings"].items():
        a(f"| {rid} | {rd['definition']} | {rd['dry_kg']:g} |")
    a("")
    a("| reading | Xe case (kg) | wet known (kg) | vs 34 | vs 36 | vs 40 (strict) |")
    a("|---|---|---|---|---|---|")
    cells = {(x["reading"], x["xe_case_kg"], x["reference"]): x for x in clo["cells"]}
    for rid in clo["readings"]:
        for xe in XE_CASES_KG:
            row = [cells[(rid, xe, r)] for r in ("INTERNAL_34", "INTERNAL_36", "HARD_40_WET")]

            def st(x):
                return x["state"] + (f" (headroom {x['headroom_for_pending_kg']:g})"
                                     if x["headroom_for_pending_kg"] is not None else "")
            a(f"| {rid} | {xe:g} | {row[0]['wet_known_kg']:g} | {st(row[0])} | {st(row[1])} | {st(row[2])} |")
    a("")
    a("Unresolved per reading: " + "; ".join(
        f"{rid}: " + ", ".join(cells[(rid, 2.0, 'HARD_40_WET')]["unresolved"]) for rid in clo["readings"]) + ".")
    a("")
    a("### Reduction of the evidence-free lines needed under the policy readings with evidence floors")
    a("")
    tot = doc["required_reduction_of_evidence_free_lines"][0]["other_lines_allocated_kg"]
    a(f"Evidence-free lines scaled uniformly: "
      f"{', '.join(doc['required_reduction_of_evidence_free_lines'][0]['other_lines'])} ({tot:g} kg allocated); the "
      "controls/harness line keeps the row-60 harness rule. Known part only; an owner option, not a change.")
    a("")
    a(f"| reading | Xe case (kg) | reference | reduction needed (kg, of {tot:g} kg) | feasible |")
    a("|---|---|---|---|---|")
    for x in doc["required_reduction_of_evidence_free_lines"]:
        a(f"| {x['reading']} | {x['xe_case_kg']:g} | {x['reference']} | {_fmt(x['reduction_needed_kg'])} | "
          f"{x['feasible_by_reducing_other_lines']} |")
    a("")
    a("### Row 44 stored-Xe screening (screening cap only)")
    a("")
    a("| reference | cap (kg) | Xe case | hardware basis | stored Xe known (kg) | screen |")
    a("|---|---|---|---|---|---|")
    for x in doc["xe_screen_row44"]:
        a(f"| {x['reference']} | {x['cap_kg']:g} | {x['xe_case_kg']:g} | {x['hardware_basis']} | "
          f"{x['stored_xe_known_kg']:g} | {x['screen']} |")
    a("")
    a("## (4) H2-7 v1 interface demands re-evaluated for A9")
    a("")
    a("| H2-7 id | v1 quantity | A9 disposition | routed to | A9 status |")
    a("|---|---|---|---|---|")
    for x in doc["h2_7_demands_reevaluated"]["outgoing_from_h2_7_v1"]:
        a(f"| {x['h2_7_id']} | {x['quantity_v1']} | {x['a9_disposition']} | {x['routed_to']} | {x['a9_status']} |")
    a("")
    a("| incoming from | v1 quantity | A9 disposition | A9 status |")
    a("|---|---|---|---|")
    for x in doc["h2_7_demands_reevaluated"]["incoming_to_h2_7_v1"]:
        a(f"| {x['from_lane']} | {x['quantity_v1']} | {x['a9_disposition']} | {x['a9_status']} |")
    a("")
    a("## (b) Interface demands")
    a("")
    a("| id | from | to | quantity | value | units | status |")
    a("|---|---|---|---|---|---|---|")
    for x in doc["interface_demands"]:
        a(f"| {x['id']} | {x['from']} | {x['to']} | {x['quantity']} | {_fmt(x['value'])} | {x['units']} | "
          f"{x['status']} |")
    a("")
    a("## (c) Owner answers applied")
    a("")
    a(f"Owner answers `{doc['owner_answers']['path']}` sha256 `{doc['owner_answers']['sha256']}` (verbatim pack "
      f"`{doc['owner_answers']['verbatim_pack']['path']}` sha256 `{doc['owner_answers']['verbatim_pack']['sha256']}`); "
      f"governing decision `{doc['governing_decision']['path']}` sha256 `{doc['governing_decision']['sha256']}`.")
    a("")
    a("| row | covers | answer sha256 | how applied |")
    a("|---|---|---|---|")
    for x in doc["owner_answers_applied"]:
        a(f"| {x['row']} | {', '.join(x['covers_ids'])} | `{x['answer_sha256'][:16]}` | {x['how_applied']} |")
    a("")
    a(f"A9.1 follow-up decisions `{doc['a9_1_followup']['path']}` sha256 `{doc['a9_1_followup']['sha256']}` "
      f"(verbatim `{doc['a9_1_followup']['verbatim']['path']}` sha256 `{doc['a9_1_followup']['verbatim']['sha256']}`):")
    a("")
    for x in doc["a9_1_decisions_applied"]:
        a(f"* **{x['decision']}**: {x['how_applied']}")
    a("")
    a("## (d) Open owner questions (new)")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"* **{q['id']}** {q['question']} *Proposed:* {q['proposed_answer']}")
    a("")
    a("## (e) Historical reuse")
    a("")
    for h in doc["historical_reuse"]["artifacts"]:
        a(f"* `{h['path']}` sha256 `{h['sha256']}` (read only)")
    a("")
    a("Reused: " + "; ".join(doc["historical_reuse"]["reused"]) + ".")
    a("")
    a("Not reused: " + "; ".join(doc["historical_reuse"]["not_reused"]) + ".")
    a("")
    a("## (f) M16 impact")
    a("")
    a("| M16 row | key | allocation line | how touched |")
    a("|---|---|---|---|")
    for x in doc["m16_impact"]:
        a(f"| {x['m16_row']} | {x['key']} | {x['allocation_line'] or '-'} | {x['how_touched']} |")
    a("")
    a("## (g) H3 / H4 inputs")
    a("")
    for x in doc["h3_h4_inputs"]["h3_quotation_mass_fields"]:
        a(f"* H3 (quotation only): {x['item']} - {x['ceiling']}")
    for x in doc["h3_h4_inputs"]["h4_measurements"]:
        a(f"* H4 {x['stage']}: {x['measure']}")
    a("")
    a("## Compliance")
    a("")
    for k, v in doc["compliance"].items():
        a(f"* {k}: {v}")
    a("")
    return "\n".join(L)


def outputs() -> dict:
    doc = build()
    js = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    return {OUT_JSON: js, OUT_MD: render_md(doc)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed outputs differ from a fresh build")
    args = ap.parse_args(argv)
    outs = outputs()
    if args.check:
        bad = []
        for rel, txt in outs.items():
            p = _abs(rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt:
                bad.append(rel)
        if bad:
            print("OUT OF DATE: " + ", ".join(bad))
            return 1
        print("OK")
        return 0
    for rel, txt in outs.items():
        with open(_abs(rel), "w", encoding="utf-8") as f:
            f.write(txt)
    print("wrote " + ", ".join(outs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
