#!/usr/bin/env python3
"""Deterministic builder of the A9 RFQ packages v2 (fo_a9_rfq_v2_split, trigger T_A9_RFQ_V2_SPLIT).

A REVISION of the immutable v1 packages docs/procurement/rfq_a9/ (A9-09). v1 is never edited: every v1 file is pinned by
sha256 below and read as data. v2 splits the quotation specification by supplier speciality into exactly the six owner
families of A9.3 OQ-RFQ-07 plus ONE common top-level interface document, and applies A9.2 and A9.3.

Writes
  docs/procurement/rfq_a9_v2/rfq_a9_v2.json                          machine-readable packages, change log, traceability
  docs/procurement/rfq_a9_v2/RFQ_A9_V2.md                            companion document (rendered from the JSON data)
  docs/procurement/rfq_a9_v2/packages/RFQ2-00_common_interface.md    common top-level interface document
  docs/procurement/rfq_a9_v2/packages/RFQ2-0N_<slug>.md              one sendable package per supplier speciality

Authority (all pinned by sha256; the build refuses to run if any pinned file changed)
  A9, the 147 owner answers (+ verbatim pack), A9.1, A9.2, A9.3 (+ verbatim .md files), A4-A7; cited by row / decision id.
  Owner quotes are checked verbatim against the decision text at build time.

Rules implemented here
  * every v1 requirement is carried exactly once into one v2 package with a per-line change record (what changed, why);
  * new lines cite an owner row / A9.1 / A9.2 / A9.3 id or a verified deliverable item located by id at build time;
  * values of the parallel lanes P1 (docs/experiments/hall_icp/p1_icp_bench/) and P2 prep
    (docs/experiments/hall_icp/p2_impedance_map/) are written 'PENDING <path>' and never filled; nothing is read from them;
  * no price, supplier ranking, supplier contact, winner, performance prediction or Hall-closure source; RF component
    ratings stay TBD_AFTER_IMPEDANCE_MAP; ICP thermal and anode items are never PASS;
  * computed values are deterministic arithmetic on cited inputs (evidence class model-derived);
  * missing inputs raise (CLAUDE.md rule 3).

Usage
  python docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py          # write all outputs
  python docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py --check  # exit 1 if any output differs from a fresh build

Standard library only. Pure (reads repository files, writes only its own outputs); not wired into archengine.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LANE_DIR = "docs/procurement/rfq_a9_v2"
OUT_JSON = LANE_DIR + "/rfq_a9_v2.json"
OUT_MD = LANE_DIR + "/RFQ_A9_V2.md"
PKG_DIR = LANE_DIR + "/packages"
THIS_SCRIPT = LANE_DIR + "/build_rfq_a9_v2.py"
TEST = "tests/test_rfq_a9_v2.py"
BASE_COMMIT = "ee9dc7db7d11e0b5f1d8b514258778ac1b6030d3"

P1_LANE = "docs/experiments/hall_icp/p1_icp_bench/"
P2_LANE = "docs/experiments/hall_icp/p2_impedance_map/"

# ------------------------------------------------------------------------------------------------------------- pins
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
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03"),
    "A92_MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
               "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b"),
    "A93_MD": ("docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md",
               "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411"),
    "A4": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json",
           "beec91f9eca3ca0257c5ee88dcd193c87481660b9368b65c6d10b3b3bdae23b4"),
    "A5": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
           "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"),
    "A6": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
           "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"),
    "A7": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
           "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925"),
}

V1 = {
    "V1_JSON": ("docs/procurement/rfq_a9/rfq_a9_v1.json",
                "d2e654cf49d89b8f84a65e5bf7626517a37c02d0a4a0de97f128c3155ef4a84b"),
    "V1_MD": ("docs/procurement/rfq_a9/RFQ_A9.md",
              "9d83c0f98f8365d8b758824382d6dea4d2f388ae0a10be2fa6367a252ef77334"),
    "V1_BUILDER": ("docs/procurement/rfq_a9/build_rfq_a9.py",
                   "955862af1381dacabc0b1f22b5a51c182383c9b38ed6bb12359a9f93fed62bef"),
    "V1_LANE_PATHS": ("docs/procurement/rfq_a9/rfq_a9_lane_paths_v1.json",
                      "c9364a68f94ca504c1053e49092d28fc3830e97bae94e67d242c2de2c20a2892"),
    "V1_RFQ-01": ("docs/procurement/rfq_a9/packages/RFQ-01_thrust_stand.md",
                  "ec2a0de8016826e565e6187cb1423c7ade0cb0ec37358edb8bb703e9253b825f"),
    "V1_RFQ-02": ("docs/procurement/rfq_a9/packages/RFQ-02_mass_flow_controllers.md",
                  "24274ed3cf06dc37ecd4357bd3593b665696fa1407f5215c557e38d9e14084df"),
    "V1_RFQ-03": ("docs/procurement/rfq_a9/packages/RFQ-03_rga.md",
                  "056e7f4fbfd929c1fa5e3ddf0c3de255b9c537eea045a428c0cb63ec7416a0fb"),
    "V1_RFQ-04": ("docs/procurement/rfq_a9/packages/RFQ-04_rf_chain.md",
                  "0ea196f72e8da254e50787c4f58bdb665939f770028a0013a9f9bc57b0b0e9a4"),
    "V1_RFQ-05": ("docs/procurement/rfq_a9/packages/RFQ-05_icp_source_components.md",
                  "a45c6a3541433e47128e3b4757cd11ecce2887ab1913c61a76106fedce1cbbfc"),
    "V1_RFQ-06": ("docs/procurement/rfq_a9/packages/RFQ-06_discharge_supply_and_pbus_chain.md",
                  "96174a8c252c579c6bdc06397cce12851650bd03461dacc695725c3851b6e1be"),
    "V1_RFQ-07": ("docs/procurement/rfq_a9/packages/RFQ-07_xe_feed.md",
                  "0cb761cf61ab0bdc39267df5e38ef4a03a32fc2e35484366829a0a80077e03a3"),
    "V1_RFQ-08": ("docs/procurement/rfq_a9/packages/RFQ-08_c1_cathode_and_keeper.md",
                  "1ed268debbfb7238f61526d26a4d30e9d5f1917ee4798bcae85131da322f9b46"),
    "V1_RFQ-09": ("docs/procurement/rfq_a9/packages/RFQ-09_facility_calibration_services.md",
                  "38ee7b75555e55be944edf90cc7f79c5f07d9fe9e585375f7690766aa4a9ea7b"),
}

DELIVERABLES = {
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json",
            "8ec092f284505e7a538d17f568c0d9d763155f9a2ce4541223ddd114169a452c"),
    "EVI": ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
            "092e4ca8e1827dd2e9558058a204f46510f2633316ce188e7126b697ec6d0b53"),
    "UB": ("docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
           "c6567e6d0bbc008bedd5b9c14a9716f117144ab6952b9c498f7b0c75e02a624d"),
    "BUS": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
            "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6"),
    "INS": ("docs/experiments/instrumentation/instrumentation_definition_v1.json",
            "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96"),
    "H21": ("docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
            "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d"),
    "H23": ("docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
            "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b"),
    "H24": ("docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
            "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef"),
    "H26": ("docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
            "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56"),
    "M16V3": ("docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json",
              "636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2"),
    "OQS3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
             "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2"),
}

NEVER_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/trigger_ledger_v2.jsonl (and fired_triggers.jsonl)",
    "docs/orchestration/runtime_state.json",
]

ALL_PINS = {}
ALL_PINS.update(DECISIONS)
ALL_PINS.update(V1)
ALL_PINS.update(DELIVERABLES)

_CACHE: dict = {}


def _abs(rel: str) -> str:
    return os.path.join(ROOT, rel)


def _sha_file(rel: str) -> str:
    with open(_abs(rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify_pins() -> None:
    for key, (rel, sha) in ALL_PINS.items():
        if not os.path.isfile(_abs(rel)):
            raise FileNotFoundError(f"pinned input {key} missing: {rel}")
        got = _sha_file(rel)
        if got != sha:
            raise RuntimeError(f"pinned input {key} changed: {rel} sha256 {got} != {sha}")


def load(key: str):
    if key not in _CACHE:
        rel = ALL_PINS[key][0]
        with open(_abs(rel), encoding="utf-8") as fh:
            _CACHE[key] = json.load(fh) if rel.endswith(".json") else fh.read()
    return _CACHE[key]


def answers() -> dict:
    return {a["row"]: a for a in load("ANS")["answers"]}


# ---------------------------------------------------------------------------------------------------------- sources
def OW(row: int, quote: str) -> dict:
    """Owner answer row citation; the quote must occur verbatim in the recorded answer."""
    a = answers().get(row)
    if a is None:
        raise KeyError(f"owner row {row} not found")
    if quote not in a["owner_answer_verbatim"]:
        raise ValueError(f"quote not verbatim in owner row {row}: {quote!r}")
    return {"type": "owner_row", "row": row, "covers_ids": a["covers_ids"], "quote": quote,
            "answer_sha256": hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest(),
            "path": DECISIONS["ANS"][0]}


def A91(did: str, quote: str) -> dict:
    md = load("A91_MD")
    if did not in md:
        raise KeyError(f"A9.1 id {did} not in the verbatim record")
    if quote not in md:
        raise ValueError(f"quote not verbatim in A9.1: {quote!r}")
    return {"type": "a9_1", "id": did, "quote": quote, "path": DECISIONS["A91_MD"][0]}


def A92(did: str) -> dict:
    d = load("A92")["decisions"]
    if did not in d:
        raise KeyError(f"A9.2 decision {did} not found")
    return {"type": "a9_2", "key": "A9.2", "id": did, "path": DECISIONS["A92"][0], "pointer": "/decisions/" + did,
            "sha256": DECISIONS["A92"][1]}


def A92Q(did: str, quote: str) -> dict:
    s = A92(did)
    if quote not in load("A92_MD"):
        raise ValueError(f"quote not verbatim in A9.2: {quote!r}")
    s["quote"] = quote
    s["quote_path"] = DECISIONS["A92_MD"][0]
    return s


def A93(did: str, quote: str) -> dict:
    d = load("A93")["decisions"]
    if did not in d:
        raise KeyError(f"A9.3 decision {did} not found")
    if quote not in load("A93_MD"):
        raise ValueError(f"quote not verbatim in the A9.3 record: {quote!r}")
    return {"type": "a9_3", "key": "A9.3", "id": did, "quote": quote, "path": DECISIONS["A93_MD"][0],
            "pointer": "/decisions/" + did, "json_path": DECISIONS["A93"][0], "sha256": DECISIONS["A93_MD"][1]}


def A93J(pointer: str) -> dict:
    """A9.3 machine-readable field (recorder text), resolved by JSON pointer."""
    val = _resolve(load("A93"), pointer)
    return {"type": "a9_3_record", "key": "A9.3", "pointer": pointer, "value": val, "path": DECISIONS["A93"][0],
            "sha256": DECISIONS["A93"][1]}


def _resolve(doc, pointer: str):
    cur = doc
    for raw in pointer[1:].split("/") if pointer else []:
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def _find_id(doc, target: str, ptr: str = ""):
    if isinstance(doc, dict):
        if doc.get("id") == target:
            return ptr
        for k, v in doc.items():
            r = _find_id(v, target, ptr + "/" + str(k).replace("~", "~0").replace("/", "~1"))
            if r is not None:
                return r
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            r = _find_id(v, target, ptr + "/" + str(i))
            if r is not None:
                return r
    return None


def DI(key: str, did: str) -> dict:
    """Deliverable item located by id (first occurrence in document order); raises if absent."""
    ptr = _find_id(load(key), did)
    if ptr is None:
        raise KeyError(f"{did} not found in {key} ({DELIVERABLES[key][0]})")
    return {"type": "deliverable_item", "key": key, "path": DELIVERABLES[key][0], "id": did, "pointer": ptr,
            "sha256": DELIVERABLES[key][1]}


def V1R(rid: str) -> dict:
    for i, p in enumerate(load("V1_JSON")["packages"]):
        for j, r in enumerate(p["requirements"]):
            if r["id"] == rid:
                return {"type": "v1_requirement", "id": rid, "path": V1["V1_JSON"][0],
                        "pointer": f"/packages/{i}/requirements/{j}", "sha256": V1["V1_JSON"][1]}
    raise KeyError(rid)


def PEND(path: str, what: str) -> dict:
    return {"type": "pending_lane", "path": path, "what": what,
            "note": "parallel lane not in this base; nothing is read from it"}


def label(s: dict) -> str:
    t = s["type"]
    if t == "owner_row":
        return f"row {s['row']}"
    if t == "a9_1":
        return f"A9.1 {s['id']}"
    if t == "a9_2":
        return f"A9.2 {s['id']}"
    if t == "a9_3":
        return f"A9.3 {s['id']}"
    if t == "a9_3_record":
        return f"A9.3 record {s['pointer']}"
    if t == "deliverable_item":
        return f"{s['key']}:{s['id']}"
    if t == "deliverable":
        return s.get("key", s.get("path", "deliverable"))
    if t == "v1_requirement":
        return f"v1 {s['id']}"
    if t == "pending_lane":
        return f"PENDING {s['path']}"
    raise ValueError(t)


# ------------------------------------------------------------------------------------------------------ vocabulary
CONFIGS = ["hall_c1_reference", "hall_icp_neutralizer"]
OUTCOMES = ["hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE"]
EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "owner-stated"]
FREEZE_POINTS = ["NOW", "LOCK-1", "LOCK-2", "after-evidence"]
STATUSES = ["OWNER_GIVEN", "COPIED_VERIFIED", "DERIVED", "PROPOSED", "TBD", "PENDING", "REFERENCE_ONLY",
            "SUPERSEDED_NOT_QUOTED"]
DISPATCH = ["P1_NEEDED", "LATER"]
CHANGE_TYPES = ["CARRIED_UNCHANGED", "CARRIED_MODIFIED", "SUPERSEDED_NOT_QUOTED", "NEW"]
TBD_RF = "TBD_AFTER_IMPEDANCE_MAP"
STAND_CEILING_W = 1500.0   # A9.3 OQ-A907-02 (owner-stated numerator)
STAND_CEILING_V = 180.0    # A9.3 OQ-A907-02 (owner-stated denominator)

PACKAGES = [
    # id, slug, owner family heading (verbatim in A9.3 md), primary v1 packages
    ("RFQ2-RF", "01", "rf", "RF package", ["RFQ-04"]),
    ("RFQ2-GAS", "02", "gas_metrology", "Gas/metrology package", ["RFQ-02", "RFQ-07"]),
    ("RFQ2-VAC", "03", "vacuum_facility", "Vacuum/facility package", ["RFQ-03", "RFQ-09"]),
    ("RFQ2-HALLEL", "04", "hall_electrical", "Hall electrical package", ["RFQ-06", "RFQ-08"]),
    ("RFQ2-MECH", "05", "mechanical_icp_fabrication", "Mechanical/ICP fabrication package", ["RFQ-05"]),
    ("RFQ2-THRUST", "06", "thrust_metrology", "Thrust/metrology package", ["RFQ-01"]),
]
PKG_IDS = [p[0] for p in PACKAGES]
CIF_ID = "RFQ2-CIF"


def owner_family_items(heading: str) -> list:
    """Owner item list for one family, parsed verbatim from the A9.3 record (bullets under '### <heading>')."""
    lines = load("A93_MD").splitlines()
    try:
        start = lines.index("### " + heading)
    except ValueError as exc:
        raise KeyError(f"A9.3 family heading not found: {heading}") from exc
    items = []
    for ln in lines[start + 1:]:
        if ln.startswith("#"):
            break
        if ln.startswith("- "):
            items.append(ln[2:].rstrip().rstrip(";").rstrip("."))
    if not items:
        raise ValueError(f"no items under {heading}")
    return items


def banner_lines() -> list:
    return [
        "DO NOT PURCHASE - QUOTATION / SPECIFICATION ONLY. Purchase orders are NOT authorized by this package (owner "
        "row 8: quotations only, no purchase order until H3/A9 interfaces are frozen; A9.1 A9-09 procurement "
        "restriction; A9.3 unchanged: no purchase orders).",
        "Prepared by the technical team (A9.3 OQ-RFQ-07). Commercial dispatch authority remains with P9E/Vyovrinda "
        "under Praveen's authorization. No automatic supplier contact: neither this repository nor Claude contacts any "
        "supplier; dispatch, if any, is an owner/procurement act.",
        "Compatibility: this is one of six supplier-speciality packages kept compatible by the common top-level "
        "interface document RFQ2-CIF (packages/RFQ2-00_common_interface.md). Shared interface ids, reference planes, "
        "connectors/flanges, potentials/grounding, gas species and units are defined there and govern over local "
        "wording.",
        "No prices are recorded; no supplier is ranked or selected; catalogue data appear only as REFERENCE with the "
        "citation/URL and access record of the web track.",
        "A9 status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE: no configuration is a winner; no "
        "thrust, efficiency, discharge current, ICP electron current, impedance or plasma state is predicted.",
    ]


# ------------------------------------------------------------------------------------------------ new requirements
def R(rid, pkg, title, requirement, value, units, basis, sources, evidence_class, status, freeze, dispatch,
      applies_to=("hall_icp_neutralizer",), note=None, change_why=None):
    return {"id": rid, "package": pkg, "v1_id": None, "title": title, "requirement": requirement, "value": value,
            "units": units, "basis": basis, "sources": sources, "evidence_class": evidence_class, "status": status,
            "freeze_point": freeze, "dispatch": dispatch, "applies_to": list(applies_to), "note": note,
            "change": {"type": "NEW", "v1_package": None, "why": change_why}}


def stand_ceiling_A() -> float:
    return round(STAND_CEILING_W / STAND_CEILING_V, 6)


def ar_mgps_check() -> dict:
    """Recorder arithmetic check of the owner-stated 70 sccm Ar ~ 2.1 mg/s (constants as written in the A9.3 record)."""
    flag = load("A93")["recorder_flags"][1]
    for token in ("70 sccm", "7.436e-7", "39.948"):
        if token not in flag:
            raise ValueError(f"A9.3 recorder flag no longer carries {token}")
    mol_per_s_per_sccm = 7.436e-7
    molar_mass_g = 39.948
    mgps = 70.0 * mol_per_s_per_sccm * molar_mass_g * 1000.0
    return {"value_mgps": round(mgps, 4), "formula": "70 sccm x 7.436e-7 mol/s/sccm x 39.948 g/mol x 1000 mg/g",
            "evidence_class": "model-derived",
            "source": "A9.3 recorder_flags[1] (constants as recorded; 'verify' the sccm reference-condition basis "
                      "with the supplier's stated convention)",
            "consistent_with_owner_stated_2p1": abs(mgps - 2.1) / 2.1 < 0.02}


def new_requirements() -> list:
    ic = stand_ceiling_A()
    ar = ar_mgps_check()
    out = []
    # ---------------------------------------------------------------- RF
    out.append(R(
        "RFQ2-RF-N01", "RFQ2-RF", "quotation format: capability ranges / scalable options, never a single 500 W rating",
        "Quote the generator, directional coupler, sensors, coax, connectors, local matching elements (incl. their "
        "voltage and current), RF feedthroughs and dummy load as CAPABILITY RANGES or SCALABLE OPTIONS (e.g. a family of "
        "power classes or a documented upgrade path), with the ratings of each option stated. 0-500 W is a laboratory "
        "delivered/operating investigation capability, NOT a component rating; component ratings are selected only "
        "after the mismatch envelope is characterized (impedance map, P2).",
        TBD_RF, "W; V; A", "A9.2 rf_500W",
        [A92Q("rf_500W", "It is not a sufficient component rating by itself."),
         A92Q("rf_500W", "RF generator, coupler, coax, connectors, matching elements and feedthroughs shall be "
                         "selected only after the expected mismatch envelope is characterized."),
         DI("ICD", "ICP-15")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        note="the rating itself is TBD_AFTER_IMPEDANCE_MAP (freeze after-evidence); only the quoting rule is frozen now",
        change_why="A9.2 rf_500W: v1 carried the rule inside R02/R07/R12/R17; v2 states it once as a package-level "
                   "quotation rule and forbids single-rating quotes"))
    out.append(R(
        "RFQ2-RF-N02", "RFQ2-RF", "input power analyzer on the laboratory generator (P_mains,in)",
        "Quote a power analyzer that measures the mains input power P_mains,in of the laboratory 13.56 MHz generator as "
        "an engineering quantity, synchronized with P_RF,fwd and P_RF,refl. Supplier states measurement uncertainty, "
        "phase/wiring configurations and the generator's mains input interface it must accept. P_mains,in is GROUND/"
        "FACILITY_ONLY and is never evidence for P_bus < 1.5 kW.",
        "TBD - requires the generator's mains input interface (supplier data) and the P1 uncertainty target (PENDING "
        + P1_LANE + ")", "W", "A9.3 OQ-RFQ-06",
        [A93("OQ-RFQ-06", "Measure the laboratory source with a proper input power analyzer and record:"),
         A93("OQ-RFQ-06", "as evidence that the flight propulsion system satisfies:"),
         PEND(P1_LANE, "P1 uncertainty target for P_mains,in")],
        None, "TBD", "NOW", "P1_NEEDED",
        note="line item required by A9.3 OQ-RFQ-06; its accuracy class freezes with the P1 bench plan",
        change_why="new line required by A9.3 OQ-RFQ-06 (v1 R04 only asked the supplier to allow input metering)"))
    out.append(R(
        "RFQ2-RF-N03", "RFQ2-RF", "boundary labels of the P1 RF-cost quantities",
        "The data interface of generator, coupler/sensors and power analyzer must allow the P1 quantities "
        "C_e = P_RF,delivered / I_e and C_e,DC = P_generator,input / I_e to be formed with each boundary labelled "
        "(RP-RF-50 for P_RF; RP-MAINS for P_generator,input; see RFQ2-CIF). No value is predicted or requested.",
        "labels only (no value)", "-", "A9.3 OQ-RFQ-06",
        [A93("OQ-RFQ-06", "P1 should still calculate:"), A93("OQ-RFQ-06", "with the exact boundary clearly labelled.")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        change_why="new: A9.3 OQ-RFQ-06 P1 outputs"))
    out.append(R(
        "RFQ2-RF-N04", "RFQ2-RF", "50-ohm RF dummy load",
        "A 50-ohm RF dummy load for generator/coupler-chain characterization, S1a pickup tests (generator into a dummy "
        "load) and characterization of losses between the load plane and the antenna. Its power rating is not less "
        "than the forward-power rating of the selected generator option (rule); the numeric rating follows the "
        "generator selection and is TBD_AFTER_IMPEDANCE_MAP. The supplier may offer a calorimetric dummy load that also "
        "serves the calorimetric cross-check (RFQ-04-R10 carried), stating both functions separately.",
        TBD_RF, "W", "ICD ICP-14 / ICP-17 (dummy-load characterization and pickup tests); rating rule A9.2 rf_500W",
        [DI("ICD", "ICP-14"), DI("ICD", "ICP-17"), DI("UB", "UB-RF-06"), A92("rf_500W")],
        None, "PROPOSED", "after-evidence", "P1_NEEDED",
        note="item PROPOSED from the ICD test requirements; no owner-given rating exists",
        change_why="new explicit line: v1 had only the calorimetric cross-check load; the owner's RF family list "
                   "(A9.3 OQ-RFQ-07) names a dummy load"))
    out.append(R(
        "RFQ2-RF-N05", "RFQ2-RF", "P1 50-ohm line generator -> coupler -> local match",
        "Controlled 50-ohm coax from the generator through the directional coupler to the local matching network on / "
        "immediately adjacent to the ICP module; forward/reflected measured on this 50-ohm side. Length, connector "
        "family and ratings: TBD_AFTER_IMPEDANCE_MAP and the P1 bench layout.",
        "TBD - requires the P1 bench layout (PENDING " + P1_LANE + ") and the impedance map (ratings "
        + TBD_RF + ")", "m; W; V", "A9.2 OQ-A907-11 / rf_measurement_reference",
        [A92Q("OQ-A907-11", "The local matching network shall be positioned on, or immediately adjacent to, the ICP "
                            "module"),
         A92("rf_measurement_reference"), PEND(P1_LANE, "P1 bench layout (cable run)")],
        None, "PENDING", "NOW", "P1_NEEDED",
        change_why="new P1 line: v1 quoted only the live/sham flexible pair for the thrust-stand crossing (LATER)"))
    out.append(R(
        "RFQ2-RF-N06", "RFQ2-RF", "compatibility with the P2 impedance-map instrument preparation",
        "Supplier states whether the coupler/sensor chain and the local match support calibrated complex reflection "
        "measurement (|Gamma| and phase, VSWR) and V/I sensing at the 50-ohm reference plane, and the calibration / "
        "de-embedding data it can supply; P2 instrument preparation uses the same RF hardware.",
        "TBD - requires the P2 instrument-preparation method (PENDING " + P2_LANE + ")", "-",
        "A9.3 authorizations P2; A9.2 rf_measurement_reference",
        [A93J("/authorizations/P2"), A92("rf_measurement_reference"),
         PEND(P2_LANE, "V/I sensing, coupler chain, calibration and S-parameter methodology")],
        None, "PENDING", "NOW", "P1_NEEDED",
        change_why="new: A9.3 authorizes P2 preparation on the same RF hardware"))
    # ---------------------------------------------------------------- GAS
    out.append(R(
        "RFQ2-GAS-N01", "RFQ2-GAS", "Ar P1 engineering window (Takahashi-anchor neighbourhood)",
        "Calibrated Ar flow that reproduces the neighbourhood of the owner-stated Takahashi anchor 70 sccm "
        "(~2.1 mg/s) and sweeps sufficiently above and below it to establish ignition/current trends, with useful flow "
        "uncertainty inside that window. The sweep bounds are set by the P1 bench plan. Ar data are "
        "ENGINEERING_ONLY_NON_SCORING regardless of metrology quality.",
        {"anchor_sccm": 70.0, "anchor_mgps_owner_stated": 2.1, "anchor_mgps_recorder_check": ar["value_mgps"],
         "sweep_bounds": "PENDING " + P1_LANE},
        "sccm (Ar); mg/s", "A9.3 OQ-RFQ-02; published analog anchor EVI TK-31 (Takahashi 2024 p. 3 text)",
        [A93("OQ-RFQ-02", "reproduce the neighborhood of the Takahashi anchor:"),
         A93("OQ-RFQ-02", "sweep sufficiently above/below that point to establish ignition/current trends;"),
         DI("EVI", "TK-31"), PEND(P1_LANE, "Ar sweep bounds")],
        "owner-stated", "PENDING", "NOW", "P1_NEEDED",
        note="70 sccm is a published-analog operating point (evidence class of TK-31: published analog, measured by the "
             "authors) used only as a flow-range anchor, never as Vyovrinda performance; the shared HET+ICP flow is "
             "not separable (TK-31 note)",
        change_why="A9.3 OQ-RFQ-02 replaces the v1 HI-AR TBD (RFQ-02-R06)"))
    out.append(R(
        "RFQ2-GAS-N02", "RFQ2-GAS", "Ar MFC count: one suitable unit; second overlapping range only if needed",
        "Quote ONE suitable Ar MFC that covers the P1 sweep with acceptable accuracy. Quote a second, overlapping-range "
        "Ar MFC ONLY as an option line, to be taken only if one unit cannot cover the engineering sweep adequately. "
        "The row-123 four-overlapping-range rule does NOT apply to Ar; it stays for the atmospheric score-bearing N2 "
        "and O2 paths.",
        {"base_units": 1, "option_units": "0 or 1", "four_range_rule_for_Ar": False}, "units", "A9.3 OQ-RFQ-02",
        [A93("OQ-RFQ-02", "Do not purchase four merely because the atmospheric gas paths need four."),
         A93("OQ-RFQ-02", "only if one unit cannot cover the engineering sweep adequately.")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="A9.3 OQ-RFQ-02 answered v1 OQ-RFQ-02 NO: v1 quantity '4 (OQ-RFQ-02)' is replaced"))
    out.append(R(
        "RFQ2-GAS-N03", "RFQ2-GAS", "Ar calibration and traceability path",
        "Ar-specific calibration of the Ar MFC(s) and gauges; verification through the rate-of-rise/transfer "
        "calibration path. Ar data remain ENGINEERING_ONLY_NON_SCORING regardless of metrology quality; a later "
        "quantitative Ar programme needs a new metrology requirement.",
        "Ar-specific calibration + rate-of-rise/transfer verification", "-", "A9.3 OQ-RFQ-02; A9.1 UBQ-08",
        [A93("OQ-RFQ-02", "Use the rate-of-rise/transfer calibration path to verify the Ar controller."),
         A91("UBQ-08", "Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation.")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        change_why="A9.3 OQ-RFQ-02 traceability clause"))
    out.append(R(
        "RFQ2-GAS-N04", "RFQ2-GAS", "ICP gas-line isolator (only where a line bridges isolated potentials)",
        "Any ICP gas line that crosses a meaningful potential difference gets the Hall gas-isolator philosophy: "
        "development qualification at ~1 kV DC at representative pressure, gas, geometry and feedthrough/isolator "
        "condition, checking flashover, leakage, breakdown, surface tracking and repeated exposure where appropriate. "
        "No isolator is inserted in a gas line whose two ends are intentionally held at essentially the same floating "
        "potential. In G-REUSE the ICP port is capped (no ICP gas line); the count follows the P1 potential map.",
        {"qualification_V_DC": 1000.0, "count": "PENDING " + P1_LANE}, "V (DC); units",
        "A9.3 ICPQ-06; row 105 practice",
        [A93("ICPQ-06", "Any ICP gas line crossing a meaningful potential difference shall receive the same "
                        "representative-pressure/gas isolation philosophy already adopted for the Hall gas isolator."),
         A93("ICPQ-06", "The requirement applies when the gas plumbing creates an electrical bridge across isolated "
                        "potentials."),
         OW(105, "perform ~1 kV DC representative-pressure/gas withstand qualification"),
         PEND(P1_LANE, "P1 gas schematic and potential map")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        note="'~1 kV' is the owner's approximate class; the exact test voltage and margin freeze with the H-1 isolation "
             "margin (owner item, row 81 'appropriate transient/qualification margin')",
        change_why="new: A9.3 ICPQ-06"))
    out.append(R(
        "RFQ2-GAS-N05", "RFQ2-GAS", "Hall anode gas isolator (voltage break) for the H-1 Ar runs",
        "Gas isolator between the grounded feed and the H-1 anode potential: designed for 350 V continuous operation, "
        "~1 kV DC representative-pressure/gas withstand qualification (Ar for P1), segmented/porous geometry as "
        "appropriate; compliance is not argued from vacuum creepage across the Paschen region. Position and p d range "
        "as H2-3 H23-27 / H23-29.",
        {"continuous_V": 350.0, "qualification_V_DC": 1000.0}, "V", "row 105; H2-3 H23-27, H23-29",
        [OW(105, "Design the gas isolator for 350 V continuous operation"),
         OW(105, "Do not rely on simple vacuum creepage assumptions across the Paschen region."),
         DI("H23", "H23-27"), DI("H23", "H23-29")],
        "owner-allocation", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        note="P1 runs H-1 on Ar (G-REUSE; A9.3 OQ-VI-05 sequence), so the anode isolator is a P1 item",
        change_why="new line: v1 quoted only the C1 Xe-line dielectric break; the owner gas family names gas isolators"))
    out.append(R(
        "RFQ2-GAS-N06", "RFQ2-GAS", "pressure instrumentation",
        "Gauges for (i) feed/manifold pressure (H26-25, INS-06), (ii) the ICP source-volume pressure p_icp through the "
        "module pressure port (ICP-34) and (iii) chamber background pressure p_b with the placement/reading rule of "
        "H26-30 (INS-08); Ar-specific calibration for P1. Ranges and gauge types follow the P1 bench plan and the "
        "facility.",
        "TBD - requires the P1 bench plan (PENDING " + P1_LANE + ") and facility identification (row 139)", "Pa",
        "A9.3 OQ-RFQ-07 gas/metrology family; ICD ICP-34; H2-6 H26-25, H26-30; INS-06, INS-08",
        [A93("OQ-RFQ-07", "pressure instrumentation"), DI("ICD", "ICP-34"), DI("H26", "H26-25"), DI("H26", "H26-30"),
         DI("INS", "INS-06"), DI("INS", "INS-08"),
         A91("UBQ-08", "Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation."),
         PEND(P1_LANE, "pressure ranges")],
        None, "PENDING", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner gas/metrology family names pressure instrumentation (v1 had only a pressure port)"))
    out.append(R(
        "RFQ2-GAS-N07", "RFQ2-GAS", "P1 Ar feed valves",
        "Shut-off/isolation valves of the P1 Ar feed (bottle -> regulator -> MFC -> H-1 anode feed); type and count per "
        "the P1 gas schematic. The two-series-valve rule of row 90 applies to the high-pressure Xe/cathode branch "
        "(carried RFQ-07-R05, LATER).",
        "TBD - requires the P1 gas schematic (PENDING " + P1_LANE + ")", "units", "A9.3 OQ-RFQ-07 gas/metrology family",
        [A93("OQ-RFQ-07", "valves"), PEND(P1_LANE, "P1 gas schematic")],
        None, "PENDING", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner gas/metrology family names valves"))
    # ---------------------------------------------------------------- VAC
    out.append(R(
        "RFQ2-VAC-N01", "RFQ2-VAC", "chamber interfaces (flanges / adapter plates / internal mounting)",
        "Interface hardware between the facility chamber and (i) the P1 ICP bench incl. H-1 and the ICP module carrier, "
        "(ii) later the thrust stand. Flange families and sizes are recorded once in RFQ2-CIF when the facility is "
        "identified.",
        "TBD - requires facility identification (row 139) and the module envelope (ICD ICP-07)", "mm",
        "A9.3 OQ-RFQ-07 vacuum/facility family; row 139; ICD ICP-07",
        [A93("OQ-RFQ-07", "chamber interfaces"), OW(139, "use a smaller domestic chamber for engineering-only S1a"),
         DI("ICD", "ICP-07")],
        None, "TBD", "after-evidence", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner vacuum/facility family names chamber interfaces"))
    out.append(R(
        "RFQ2-VAC-N02", "RFQ2-VAC", "pumping",
        "Pumping capability for the P1 Ar bench and later campaigns, quoted only where the identified facility lacks "
        "it; the required throughput/base pressure follow the facility identification and the P1 plan (the published "
        "analog's facility is context only, EVI TK-32..TK-34).",
        "TBD - requires facility identification (row 139) and the P1 bench plan (PENDING " + P1_LANE + ")",
        "Pa; L/s", "A9.3 OQ-RFQ-07 vacuum/facility family; row 139; row 23",
        [A93("OQ-RFQ-07", "pumping"), OW(139, "use a smaller domestic chamber for engineering-only S1a"),
         OW(23, "use two elevated background-pressure levels for facility-effect characterization"),
         DI("EVI", "TK-34"), PEND(P1_LANE, "P1 flow/pressure plan")],
        None, "TBD", "after-evidence", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner vacuum/facility family names pumping"))
    out.append(R(
        "RFQ2-VAC-N03", "RFQ2-VAC", "electrical vacuum feedthroughs (discharge, collector/bias, magnet, sensing)",
        "Current-carrying feedthrough pins sized to the 8.33 A stand ceiling (bench design ceiling, not an H-1 "
        "requirement); voltage rating to the 350 V end plus the transient/qualification margin (margin TBD, owner "
        "item). RF feedthroughs are in RFQ2-RF (RFQ-04-R12 carried).",
        {"current_A_min_rating": ic, "voltage_V_upper_before_margin": 350.0, "margin": "TBD - requires the owner's "
         "H-1 isolation margin (row 81)"}, "A; V", "A9.3 OQ-A907-02; row 81",
        [A93("OQ-A907-02", "feedthrough rating;"), A93("OQ-A907-02", "It is **not evidence that H-1 requires 8.33 A**."),
         OW(81, "rate H-1, C1 reference, discharge supply, isolation and diagnostics to the relaxed 350 V end plus "
                "appropriate transient/qualification margin")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new: owner vacuum/facility family names feedthroughs; A9.3 OQ-A907-02 sizing"))
    out.append(R(
        "RFQ2-VAC-N04", "RFQ2-VAC", "gas feedthroughs",
        "Vacuum gas feedthroughs for the P1 Ar feed and later N2/O2/Xe feeds; O2 service per row 107 where O2-bearing "
        "gas passes (LATER use). Count per the P1 gas schematic.",
        "TBD - requires the P1 gas schematic (PENDING " + P1_LANE + ")", "units",
        "A9.3 OQ-RFQ-07 vacuum/facility family",
        [A93("OQ-RFQ-07", "feedthroughs"), OW(107, "ADOPT ASTM G93 Level C cleaning for O2 service"),
         PEND(P1_LANE, "P1 gas schematic")],
        None, "PENDING", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner vacuum/facility family names feedthroughs"))
    out.append(R(
        "RFQ2-VAC-N05", "RFQ2-VAC", "RGA / diagnostic interface provisions on the chamber",
        "Port provisions for the differentially pumped RGA sampling system (carried RFQ-03) and the near-cathode / "
        "downstream sampling points (INS-22), plus diagnostic lines of sight preserved by the module envelope "
        "(ICP-07).",
        "TBD - requires facility layout and module envelopes (ICD ICP-07)", "-",
        "A9.3 OQ-RFQ-07 vacuum/facility family; INS-22; ICD ICP-07",
        [A93("OQ-RFQ-07", "RGA/diagnostic interfaces"), DI("INS", "INS-22"), DI("ICD", "ICP-07")],
        None, "TBD", "LOCK-1", "LATER", applies_to=CONFIGS,
        change_why="new line: owner vacuum/facility family names RGA/diagnostic interfaces"))
    # ---------------------------------------------------------------- HALL ELECTRICAL
    out.append(R(
        "RFQ2-HALLEL-N01", "RFQ2-HALLEL", "8.33 A stand ceiling for every current-carrying item",
        "Conductors, current-sensor ranges, the collector circuit, feedthroughs, protection, DAQ ranges and an optional "
        "stress-test capability are sized to I_d,stand ceiling = 1500 W / 180 V. This is the laboratory supply/rating "
        "ceiling, NOT an H-1 requirement and NOT the ICP-45 pass requirement: I_e,required = I_d,max,H1 (registered "
        "H-1 maximum, PENDING measurement/registration); P1 never declares PASS because 1 A, 2 A, ... is reached.",
        ic, "A", "A9.3 OQ-A907-02",
        [A93("OQ-A907-02", "1500~W/180~V=8.33~A."), A93("OQ-A907-02", "conductor sizing;"),
         A93("OQ-A907-02", "current sensor range;"), A93("OQ-A907-02", "collector circuit rating;"),
         A93("OQ-A907-02", "DAQ range;"), A93("OQ-A907-02", "Do not declare PASS simply because 1 A, 2 A, etc. is "
                                                            "reached."),
         DI("H24", "H24-27")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        note="value computed by this builder as 1500/180 (A9.3 numbers); copied H2-4 H24-27 carries the same bound",
        change_why="new: A9.3 OQ-A907-02 separates the stand ceiling from the ICP-45 requirement"))
    out.append(R(
        "RFQ2-HALLEL-N02", "RFQ2-HALLEL", "H-1 magnet supplies (per coil)",
        "One current-controlled magnet supply per MC-1 coil with 4-wire remote voltage sense and its own bus slot; "
        "floating output. Current/voltage ratings follow the MC-1 coil design.",
        "TBD - requires the MC-1 coil design currents and resistances (H2-1) and the P1 magnet setpoints (PENDING "
        + P1_LANE + ")", "A; V", "row 110; H2-4 H24-32, H3-PPU-02",
        [OW(110, "per-coil magnet"), DI("H24", "H24-32"), DI("H24", "H3-PPU-02"),
         A93("OQ-RFQ-07", "magnet supply"), A93("OQ-VI-05", "H-1 gas/magnet conditions established.")],
        None, "TBD", "LOCK-1", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner Hall electrical family names magnet supply; the P1 OQ-VI-05 sequence needs H-1 magnet "
                   "conditions"))
    out.append(R(
        "RFQ2-HALLEL-N03", "RFQ2-HALLEL", "sensing for the OQ-VI-05 topology-control records",
        "Isolated V/I sensing sufficient to record V_d(t), I_d(t), I_e,ICP(t) and collector/reference potentials during "
        "the Ar topology-control sequence (C1 disconnected, ICP RF off -> Hall start attempt -> ICP on); current ranges "
        "to the 8.33 A stand ceiling. Bandwidth and sample rate follow the P1 plan. The test is a REQUIRED ENGINEERING "
        "CONTROL, NON-SCORING; 'Hall must not run without ICP' is not a requirement.",
        {"current_range_A_min": ic, "bandwidth": "PENDING " + P1_LANE}, "A; V; Hz",
        "A9.3 OQ-VI-05; A9.3 OQ-A907-02",
        [A93("OQ-VI-05", "and collector/reference potentials."),
         A93("OQ-VI-05", "classify it as an engineering topology-control test, not a hard architecture PASS/FAIL gate."),
         A93("OQ-A907-02", "current sensor range;"), PEND(P1_LANE, "P1 bandwidth/sample-rate plan")],
        "owner-stated", "PENDING", "NOW", "P1_NEEDED",
        change_why="new: A9.3 OQ-VI-05 recorded quantities"))
    # ---------------------------------------------------------------- MECH
    out.append(R(
        "RFQ2-MECH-N01", "RFQ2-MECH", "first build topology: open-tube coaxial downstream ICP only",
        "Quote the open-tube coaxial downstream ICP only. Orificed RF plasma cathodes (Watanabe/Xu type) are NOT "
        "quoted in this revision (literature comparators / possible later branches).",
        "OPEN_TUBE_COAXIAL_FIRST_BUILD", "-", "A9.3 OQ-VI-03",
        [A93("OQ-VI-03", "first P1 build shall use the open-tube coaxial downstream ICP topology only."),
         A93("OQ-VI-03", "They shall **not** be built as part of P1.")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        change_why="new: A9.3 OQ-VI-03"))
    out.append(R(
        "RFQ2-MECH-N02", "RFQ2-MECH", "modular carrier / interface (future ICP_ORIFICED_VARIANT)",
        "The ICP module carrier and its interface to the H-1 mount stay modular so that a future ICP_ORIFICED_VARIANT "
        "can be installed as an A9.x follow-on without redesigning H-1 (the variant itself is not quoted).",
        "modular carrier", "-", "A9.3 OQ-VI-03 provision; ICD ICP-06 (KC-1 concept, PROPOSED)",
        [A93("OQ-VI-03", "could be installed as an A9.x follow-on without redesigning H-1."), DI("ICD", "ICP-06")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        change_why="new: A9.3 OQ-VI-03 provision; owner fabrication family names carrier"))
    out.append(R(
        "RFQ2-MECH-N03", "RFQ2-MECH", "machined supports: radiative-view-factor objective",
        "Supports and carrier follow the A9.2 radiative-view objective: open-frame support, minimum necessary "
        "downstream obstruction, annular/open optical path, thermally isolated mounting, high-emittance outward "
        "surfaces, suitable Hall-to-ICP axial spacing; not optimized for compactness alone. Non-ferromagnetic inside "
        "the MC-1 exclusion zone (ICP-32).",
        "TBD - requires the LOCK-1 module drawings (ICD ICP-47 geometry, ICP-02, ICP-07)", "mm",
        "A9.2 radiative_view_requirement; ICD ICP-47, ICP-32",
        [A92("radiative_view_requirement"), DI("ICD", "ICP-47"), DI("ICD", "ICP-32"),
         A93("OQ-RFQ-07", "machined supports")],
        None, "TBD", "LOCK-1", "P1_NEEDED",
        change_why="new line: owner fabrication family names machined supports"))
    out.append(R(
        "RFQ2-MECH-N04", "RFQ2-MECH", "ICP thermal data (coupled thermal closure UNRESOLVED)",
        "Every quoted ICP material/part states its continuous-use temperature limit and basis. ICP_COUPLED_THERMAL is "
        "UNRESOLVED: no supplier statement or uncoupled calculation is accepted as a thermal PASS; the >= 50 K margin "
        "rule (ICP-37) is checked only in the coupled model.",
        "UNRESOLVED", "K", "A9.2 icp_coupled_thermal; ICD ICP-37",
        [A92("icp_coupled_thermal"), DI("ICD", "ICP-37")],
        None, "TBD", "after-evidence", "P1_NEEDED",
        note="status value is UNRESOLVED by owner decision (A9.2 a9_10_statuses); never PASS",
        change_why="A9.2 statuses restated per package (v1 carried them in the RF/ICP lines)"))
    # ---------------------------------------------------------------- THRUST / METROLOGY
    out.append(R(
        "RFQ2-THRUST-N01", "RFQ2-THRUST", "P1 DAQ channel list and time base",
        "Synchronized acquisition on one common time base of at least: V_d(t), I_d(t), I_e,ICP(t), P_RF,fwd(t), "
        "P_RF,refl(t), collector/reference potentials (A9.3 OQ-VI-05), the ICD ICP-34 list (P_fwd, P_refl, RF "
        "interlock state, V_coll, I_coll, V_body, ICP temperatures, p_icp, flow), P_mains,in (RFQ2-RF-N02), pressure "
        "and flow channels; current channels ranged to the 8.33 A stand ceiling. Channel count, sample rate and "
        "bandwidth follow the P1 plan.",
        {"channels_min": "OQ-VI-05 list + ICP-34 list", "current_range_A_min": ic,
         "sample_rate": "PENDING " + P1_LANE}, "-; A; Sa/s",
        "A9.3 OQ-VI-05, OQ-RFQ-07, OQ-A907-02; ICD ICP-34; INS-18",
        [A93("OQ-VI-05", "Record:"), A93("OQ-RFQ-07", "DAQ"), A93("OQ-A907-02", "DAQ range;"), DI("ICD", "ICP-34"),
         DI("INS", "INS-18"), PEND(P1_LANE, "DAQ channel count, sample rate, bandwidth")],
        "owner-stated", "PENDING", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner thrust/metrology family names DAQ; v1 had only the P_bus chain (RFQ-06, LATER)"))
    out.append(R(
        "RFQ2-THRUST-N02", "RFQ2-THRUST", "traceability hardware",
        "Calibration references and certificates for the DAQ V/I/T channels, RF power sensors and power analyzer, "
        "with the uncertainty budget and coverage factor stated; ISO/IEC 17025 / NABL scope where the measurand is "
        "score-bearing (RFQ-09-R01 carried).",
        "TBD - requires the channel list (RFQ2-THRUST-N01) and the P1 uncertainty targets (PENDING " + P1_LANE + ")",
        "-", "A9.3 OQ-RFQ-07 thrust/metrology family; row 126",
        [A93("OQ-RFQ-07", "traceability hardware"),
         OW(126, "NABL/ISO-17025 calibration is the primary score-bearing reference."),
         PEND(P1_LANE, "P1 uncertainty targets")],
        None, "PENDING", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner thrust/metrology family names traceability hardware"))
    return out


# ---------------------------------------------------------------------------------- v1 -> v2 requirement mapping
# v1 id -> (v2 package, dispatch, change type, why, overrides)
C_U, C_M, C_S = "CARRIED_UNCHANGED", "CARRIED_MODIFIED", "SUPERSEDED_NOT_QUOTED"
SPLIT = "re-packaged by supplier speciality (A9.3 OQ-RFQ-07)"


def v1_mapping() -> dict:
    ic = stand_ceiling_A()
    m = {}
    for i in range(1, 19):
        m[f"RFQ-01-R{i:02d}"] = ("RFQ2-THRUST", "LATER", C_U, SPLIT + "; thrust stand = comparison campaign", None)
    # --------------------------------------------------------------- RFQ-02 MFCs
    m["RFQ-02-R01"] = ("RFQ2-GAS", "P1_NEEDED", C_U, SPLIT + "; applies to the P1 Ar MFC too", None)
    m["RFQ-02-R02"] = ("RFQ2-GAS", "LATER", C_M, "A9.3 OQ-RFQ-02: four overlapping ranges stay for the atmospheric "
                       "score-bearing N2/O2 paths only; Ar excepted", {
                           "requirement": "Four overlapping ranges per atmospheric score-bearing pure-gas path (N2, O2) "
                                          "for quotation/specification (row 123). NOT applied to the engineering-only Ar "
                                          "path (A9.3 OQ-RFQ-02: one Ar MFC, or two overlapping ranges only if one "
                                          "cannot cover the P1 sweep; RFQ2-GAS-N02).",
                           "add_sources": [A93("OQ-RFQ-02", "do not apply the four-range rule literally to Ar.")],
                           "applies_to_note": "N2, O2 paths"})
    for rid in ("RFQ-02-R03", "RFQ-02-R04", "RFQ-02-R05", "RFQ-02-R07", "RFQ-02-R08", "RFQ-02-R09", "RFQ-02-R10",
                "RFQ-02-R11", "RFQ-02-R12", "RFQ-02-R13", "RFQ-02-R15"):
        m[rid] = ("RFQ2-GAS", "LATER", C_U, SPLIT + "; N2/O2/Xe/C1 paths are LATER", None)
    m["RFQ-02-R06"] = ("RFQ2-GAS", "P1_NEEDED", C_M, "A9.3 OQ-RFQ-02 answers the Ar path: Takahashi-anchor window, one "
                       "MFC (second range as option only), rate-of-rise/transfer verification", {
                           "requirement": "Ar path (engineering-only, ENGINEERING_ONLY_NON_SCORING): see RFQ2-GAS-N01 "
                                          "(window around the owner-stated 70 sccm ~ 2.1 mg/s anchor, sweep above/below), "
                                          "RFQ2-GAS-N02 (one suitable Ar MFC; second overlapping range only as option "
                                          "line) and RFQ2-GAS-N03 (Ar-specific calibration, rate-of-rise/transfer "
                                          "verification).",
                           "value": "PENDING " + P1_LANE + " (sweep bounds); anchor 70 sccm ~ 2.1 mg/s owner-stated",
                           "status": "PENDING", "freeze_point": "NOW", "evidence_class": "owner-stated",
                           "add_sources": [A93("OQ-RFQ-02", "Start with:"), PEND(P1_LANE, "Ar sweep bounds")]})
    m["RFQ-02-R14"] = ("RFQ2-GAS", "P1_NEEDED", C_U, SPLIT + "; applies to the P1 Ar MFC too", None)
    m["RFQ-02-R16"] = ("RFQ2-GAS", "LATER", C_M, "A9.3 OQ-RFQ-10: quotation OPTION LINE only (G-ATM, G-XE, diagnostic "
                       "injection); primary mode G-REUSE; capped port retained; booked in the ledger if activated", {
                           "title": "ICP dedicated-feed controller - OPTION LINE ONLY",
                           "requirement": "Optional quotation for a controller suitable for later G-ATM, G-XE or "
                                          "diagnostic gas injection into the capped ICP gas port. It is NOT bought or "
                                          "installed as part of the primary architecture merely because it is quoted: "
                                          "the primary P1/A9 mode is G-REUSE (Hall exhaust -> ICP, mdot_ICP,dedicated = "
                                          "0); the physical capped ICP gas port remains. If G-XE/G-ATM is ever activated, "
                                          "mdot_ICP,dedicated is explicitly booked in the corresponding atmospheric/Xe "
                                          "ledger; a dedicated feed is a diagnostic variable and never silently the "
                                          "baseline.",
                           "value": "TBD - requires a declared G-ATM/G-XE/diagnostic-injection variant (ICD ICP-26)",
                           "add_sources": [A93("OQ-RFQ-10", "include it in the RFQ as an option line."),
                                           A93("OQ-RFQ-10", "must be explicitly booked in the corresponding "
                                                            "atmospheric/Xe ledger."),
                                           A93("OQ-RFQ-10", "However, the physical capped ICP gas port should remain.")],
                           "option_line": True})
    m["RFQ-02-R17"] = ("RFQ2-GAS", "P1_NEEDED", C_U, SPLIT + "; applies to the P1 Ar MFC too", None)
    m["RFQ-02-R18"] = ("RFQ2-GAS", "LATER", C_M, "scope clarified: row 126 accredited reference applies to the "
                       "score-bearing N2/O2/Xe paths; Ar is non-scoring and follows A9.3 OQ-RFQ-02 traceability", {
                           "note": "applies to score-bearing flows (N2, O2, Xe); the Ar path is ENGINEERING_ONLY_"
                                   "NON_SCORING and is verified per RFQ2-GAS-N03 (A9.3 OQ-RFQ-02)",
                           "add_sources": [A93("OQ-RFQ-02", "regardless of metrology quality.")]})
    # --------------------------------------------------------------- RFQ-03 RGA
    for i in range(1, 8):
        m[f"RFQ-03-R{i:02d}"] = ("RFQ2-VAC", "LATER", C_U, SPLIT + "; RGA is not in the P1 minimum list", None)
    # --------------------------------------------------------------- RFQ-04 RF chain
    for rid in ("RFQ-04-R01", "RFQ-04-R03", "RFQ-04-R05", "RFQ-04-R06", "RFQ-04-R08", "RFQ-04-R09", "RFQ-04-R10",
                "RFQ-04-R13"):
        m[rid] = ("RFQ2-RF", "P1_NEEDED", C_U, SPLIT + "; already A9.2-consistent in v1 (A9-10 reconciliation)", None)
    quote_rule = " Quote as capability ranges / scalable options with the rating of each option stated, never as a " \
                 "single 500 W rating (RFQ2-RF-N01; A9.2 rf_500W)."
    m["RFQ-04-R02"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.2 rf_500W quoting consequence made explicit; A9.3 OQ-RFQ-06 "
                       "ground-only generator", {"requirement_append": quote_rule,
                                                 "add_sources": [A92Q("rf_500W", "It is not a sufficient component "
                                                                                 "rating by itself.")]})
    m["RFQ-04-R04"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.3 OQ-RFQ-06 answers v1 OQ-RFQ-06: mains-fed laboratory generator "
                       "accepted as GROUND/FACILITY_ONLY with a power-analyzer line; P_mains,in never P_bus evidence; "
                       "the flight-representative DC-input RF source is a later separate RFQ (not in this revision)", {
                           "title": "generator input: mains-fed laboratory source, GROUND/FACILITY_ONLY",
                           "requirement": "A mains-powered laboratory 13.56 MHz generator is used for P1 and classified "
                                          "GROUND/FACILITY_ONLY. Its mains input P_mains,in is measured with the power "
                                          "analyzer of RFQ2-RF-N02 as an engineering quantity; P_RF,fwd and P_RF,refl "
                                          "are measured and delivered RF power is determined/cross-checked. P_mains,in "
                                          "is never evidence that the flight propulsion system satisfies P_bus < 1.5 kW "
                                          "(the generator's AC/DC stages are not the flight electrical architecture). "
                                          "The FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (P_DC,in -> P_RF -> I_e) is a later "
                                          "separate RFQ and is NOT in this revision.",
                           "value": "GROUND/FACILITY_ONLY mains-fed generator + input power analyzer",
                           "units": "-", "status": "OWNER_GIVEN", "freeze_point": "NOW",
                           "evidence_class": "owner-stated",
                           "add_sources": [A93("OQ-RFQ-06", "use a mains-powered laboratory 13.56 MHz generator for P1."),
                                           A93("OQ-RFQ-06", "`GROUND/FACILITY_ONLY`"),
                                           A93("OQ-RFQ-06", "`FLIGHT_REPRESENTATIVE_DC_RF_SOURCE`")]})
    m["RFQ-04-R07"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.2 rf_500W: local-match ratings requested as capability ranges",
                       {"requirement_append": quote_rule, "add_sources": [A92("icp_matching_strategy")]})
    m["RFQ-04-R11"] = ("RFQ2-RF", "LATER", C_U, SPLIT + "; the live/sham pair serves the thrust-stand crossing "
                       "(comparison campaign); the P1 50-ohm line is RFQ2-RF-N05", None)
    m["RFQ-04-R12"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.2 rf_500W: feedthrough ratings requested as capability ranges",
                       {"requirement_append": quote_rule, "add_sources": [A92("rf_500W")]})
    m["RFQ-04-R14"] = ("RFQ2-RF", "LATER", C_U, SPLIT + "; flight-allocation context only", None)
    m["RFQ-04-R15"] = ("RFQ2-RF", "LATER", C_S, "superseded by A9.2 (adjustable local match for the development "
                       "article; flight implementation only after the impedance map); v1 already marked it "
                       "SUPERSEDED_BY_A9_2; not quoted in v2", {"status": "SUPERSEDED_NOT_QUOTED"})
    m["RFQ-04-R16"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.2 rf_protection: the required protection FEATURES are frozen "
                       "now; only the trip thresholds wait for characterization", {
                           "requirement": "The RF source/chain includes: reflected-power monitoring; a mismatch/"
                                          "interlock threshold; arc detection where feasible; thermal monitoring; "
                                          "automatic RF reduction/shutdown. Exact reflected-power and VSWR trip "
                                          "thresholds are set after the ICP antenna/load characterization, never "
                                          "invented now; supplier states the adjustable range of each threshold.",
                           "value": {"features": ["reflected-power monitoring", "mismatch/interlock threshold",
                                                  "arc detection where feasible", "thermal monitoring",
                                                  "automatic RF reduction/shutdown"],
                                     "thresholds": "TBD - set after the ICP antenna/load characterization "
                                                   "(A9.2 rf_protection)"},
                           "status": "OWNER_GIVEN", "freeze_point": "NOW", "evidence_class": "owner-stated",
                           "threshold_freeze_point": "after-evidence",
                           "add_sources": [A92Q("rf_protection", "reflected-power monitoring;"),
                                           A92Q("rf_protection", "arc detection where feasible;"),
                                           A92Q("rf_protection", "automatic RF reduction/shutdown."),
                                           A92Q("rf_protection", "Exact reflected-power and VSWR trip thresholds shall "
                                                                 "be frozen after the ICP antenna/load characterization, "
                                                                 "not invented now.")]})
    m["RFQ-04-R17"] = ("RFQ2-RF", "P1_NEEDED", C_M, "A9.2 rf_500W: matching-element V/I requested as capability ranges",
                       {"requirement_append": quote_rule, "add_sources": [A92("rf_500W")]})
    # --------------------------------------------------------------- RFQ-05 ICP components
    for rid in ("RFQ-05-R01", "RFQ-05-R02", "RFQ-05-R03", "RFQ-05-R04", "RFQ-05-R05", "RFQ-05-R06", "RFQ-05-R09",
                "RFQ-05-R10", "RFQ-05-R13"):
        m[rid] = ("RFQ2-MECH", "P1_NEEDED", C_U, SPLIT + "; ICP fabrication items are P1", None)
    m["RFQ-05-R11"] = ("RFQ2-MECH", "LATER", C_U, SPLIT + "; O2 service is for the O2-bearing stage", None)
    m["RFQ-05-R12"] = ("RFQ2-MECH", "LATER", C_U, SPLIT + "; flight-allocation context only", None)
    m["RFQ-05-R07"] = ("RFQ2-HALLEL", "P1_NEEDED", C_M, "moved to the Hall electrical package (floating DC supply "
                       "vendors); A9.3 OQ-A907-02: collector circuit rated to the 8.33 A stand ceiling; the ICP-45 "
                       "requirement is the registered H-1 maximum, not the supply rating", {
                           "requirement_append": " Collector-circuit current capability (supply, leads, sensing, "
                                                 "protection) is sized to the 8.33 A stand ceiling (RFQ2-HALLEL-N01); "
                                                 "that ceiling is not the ICP-45 requirement, which is I_e,cap >= "
                                                 "I_d,max,H1 with the preregistered one-sided margin (A9.3 OQ-A907-02). "
                                                 "Bias-voltage range stays TBD (A902-23).",
                           "value": {"current_capability_A_min": ic,
                                     "bias_voltage": "TBD - requires A902-23 collector/bias V range",
                                     "icp45_requirement": "I_d,max,H1 - PENDING registered H-1 operation "
                                                          "(ICP45_REQUIRED_CURRENT = H1_REGISTERED_MAX)"},
                           "status": "PENDING",
                           "add_sources": [A93("OQ-A907-02", "collector circuit rating;"),
                                           A93("OQ-A907-02", "It must come from measured/registered H-1 operation, not "
                                                             "simply from the maximum rating of the laboratory power "
                                                             "supply.")]})
    m["RFQ-05-R08"] = ("RFQ2-HALLEL", "P1_NEEDED", C_U, SPLIT + "; collector-circuit isolation is a Hall-electrical "
                       "isolation item", None)
    # --------------------------------------------------------------- RFQ-06 supplies and P_bus chain
    for rid in ("RFQ-06-R01", "RFQ-06-R02", "RFQ-06-R07", "RFQ-06-R08", "RFQ-06-R09", "RFQ-06-R10", "RFQ-06-R11",
                "RFQ-06-R12", "RFQ-06-R13", "RFQ-06-R14", "RFQ-06-R15", "RFQ-06-R16"):
        m[rid] = ("RFQ2-HALLEL", "LATER", C_U, SPLIT + "; breadboard / P_bus chain / wide-band chain serve the "
                  "comparison campaign", None)
    m["RFQ-06-R03"] = ("RFQ2-HALLEL", "P1_NEEDED", C_U, SPLIT + "; applies to the laboratory supply used in P1", None)
    m["RFQ-06-R05"] = ("RFQ2-HALLEL", "P1_NEEDED", C_U, SPLIT + "; V_d definition needed for the P1 records", None)
    m["RFQ-06-R04"] = ("RFQ2-HALLEL", "LATER", C_M, "A9.3 OQ-A907-02 note added: the breadboard current rating is "
                       "not set from the 8.33 A stand ceiling nor used as the H-1 requirement", {
                           "note": "A9.3 OQ-A907-02: 8.33 A is the bench ceiling, not an H-1 requirement; I_d,max,H1 "
                                   "comes from registered H-1 operation; 7.5 A (1350/180) may remain a power-envelope "
                                   "bound only",
                           "add_sources": [A93("OQ-A907-02", "may remain a **power-envelope mathematical bound**, but is "
                                                             "not automatically the flight discharge-current "
                                                             "requirement either.")]})
    m["RFQ-06-R06"] = ("RFQ2-HALLEL", "P1_NEEDED", C_M, "A9.3 OQ-A907-02: the 8.33 A laboratory rating is now "
                       "owner-classified as the stand design ceiling", {
                           "note": "8.33 A = I_d,stand ceiling (A9.3 OQ-A907-02): laboratory supply/rating ceiling, not "
                                   "evidence that H-1 requires 8.33 A",
                           "add_sources": [A93("OQ-A907-02", "because:"),
                                           A93("OQ-A907-02", "This is the **laboratory supply/rating ceiling**.")]})
    # --------------------------------------------------------------- RFQ-07 Xe feed
    for i in range(1, 12):
        m[f"RFQ-07-R{i:02d}"] = ("RFQ2-GAS", "LATER", C_U, SPLIT + "; Xe path is LATER", None)
    # --------------------------------------------------------------- RFQ-08 C1
    for i in range(1, 12):
        m[f"RFQ-08-R{i:02d}"] = ("RFQ2-HALLEL", "LATER", C_U, SPLIT + "; C1 control/fallback is not needed for P1 (C1 "
                                 "disconnected in the OQ-VI-05 sequence)", None)
    m["RFQ-08-R12"] = ("RFQ2-GAS", "LATER", C_U, SPLIT + "; the Xe-line dielectric break is a gas isolator", None)
    # --------------------------------------------------------------- RFQ-09 information only
    m["RFQ-09-R01"] = ("RFQ2-THRUST", "P1_NEEDED", C_U, SPLIT + "; accredited calibration services underpin the P1 "
                       "traceability hardware (information only)", None)
    m["RFQ-09-R02"] = ("RFQ2-VAC", "P1_NEEDED", C_U, SPLIT + "; the domestic S1a/engineering chamber hosts P1 "
                       "(information only)", None)
    for rid in ("RFQ-09-R03", "RFQ-09-R04", "RFQ-09-R05", "RFQ-09-R06"):
        m[rid] = ("RFQ2-VAC", "LATER", C_U, SPLIT + " (information only)", None)
    return m


def carried_requirements() -> list:
    v1 = load("V1_JSON")
    mapping = v1_mapping()
    seen = set()
    out = []
    counters: dict = {}
    for p in v1["packages"]:
        for r in p["requirements"]:
            rid = r["id"]
            if rid not in mapping:
                raise KeyError(f"v1 requirement {rid} has no v2 mapping")
            seen.add(rid)
            pkg, dispatch, ctype, why, ov = mapping[rid]
            rec = copy.deepcopy(r)
            counters[pkg] = counters.get(pkg, 0) + 1
            new = {"id": f"{pkg}-R{counters[pkg]:02d}", "package": pkg, "v1_id": rid}
            new.update({k: v for k, v in rec.items() if k != "id"})
            new["sources"] = list(rec["sources"]) + [V1R(rid)]
            new["dispatch"] = dispatch
            new["change"] = {"type": ctype, "v1_package": p["id"], "why": why}
            if ov:
                snap = {}
                for fld in ("title", "requirement", "value", "units", "status", "freeze_point", "evidence_class",
                            "note"):
                    if fld in ov:
                        snap["v1_" + fld] = rec.get(fld)
                        new[fld] = ov[fld]
                if "requirement_append" in ov:
                    snap["v1_requirement"] = rec.get("requirement")
                    new["requirement"] = rec["requirement"] + ov["requirement_append"]
                for extra in ("threshold_freeze_point", "option_line", "applies_to_note"):
                    if extra in ov:
                        new[extra] = ov[extra]
                new["sources"] = new["sources"] + list(ov.get("add_sources", []))
                new["change"]["v1_snapshot"] = snap
            if ctype == C_S:
                new["quote_requested"] = False
            out.append(new)
    extra = set(mapping) - seen
    if extra:
        raise KeyError(f"mapping names unknown v1 requirements: {sorted(extra)}")
    return out


# ------------------------------------------------------------------------------------------------------ line items
def L(lid, item, qty, basis, dispatch, covers=(), reqs=(), option=False, v1_ref=None, change="NEW", why=None):
    return {"id": lid, "item": item, "qty": qty, "basis": basis, "dispatch": dispatch, "option_line": option,
            "covers_owner_items": list(covers), "requirements": list(reqs), "v1_ref": v1_ref,
            "change": {"type": change, "why": why}}


def line_items() -> dict:
    p1 = "TBD - requires the P1 bench plan (PENDING " + P1_LANE + ")"
    rf = {
        "RFQ2-RF": [
            L("RF-L01", "13.56 MHz laboratory RF generator, mains-powered, GROUND/FACILITY_ONLY; forward-power options "
                        "quoted as capability ranges (rating " + TBD_RF + ")", 1, "row 72; row 8; A9.3 OQ-RFQ-06",
              "P1_NEEDED", ["13.56 MHz generator"], ["RFQ-04-R01", "RFQ-04-R02", "RFQ-04-R03", "RFQ-04-R04",
                                                    "RFQ-04-R05", "RFQ2-RF-N01"],
              v1_ref="RFQ-04 quantities[0]", change="CARRIED_MODIFIED",
              why="ground-only classification and capability-range quoting (A9.3 OQ-RFQ-06, A9.2 rf_500W)"),
            L("RF-L02", "dual directional coupler on the generator / 50-ohm side of the local match", 1, "row 72; A9.2",
              "P1_NEEDED", ["directional coupler"], ["RFQ-04-R08", "RFQ-04-R09"], v1_ref="RFQ-04 quantities[2]",
              change="CARRIED_MODIFIED", why="v1 quoted coupler + sensors as one line; split to match the owner list"),
            L("RF-L03", "forward/reflected power sensors calibrated at 13.56 MHz", "1 set", "row 72", "P1_NEEDED",
              ["forward/reflected sensors"], ["RFQ-04-R08", "RFQ-04-R09", "RFQ2-RF-N06"], v1_ref="RFQ-04 quantities[2]",
              change="CARRIED_MODIFIED", why="split from the v1 coupler line"),
            L("RF-L04", "adjustable local matching network components for on-module mounting (development article)", 1,
              "row 8; A9.2 OQ-A907-11 / icp_matching_strategy", "P1_NEEDED", ["local matching network components"],
              ["RFQ-04-R06", "RFQ-04-R07", "RFQ-04-R17"], v1_ref="RFQ-04 quantities[1]", change="CARRIED_UNCHANGED"),
            L("RF-L05", "50-ohm RF coax generator -> coupler -> local match (P1 bench)", p1, "A9.2 OQ-A907-11",
              "P1_NEEDED", ["RF coax"], ["RFQ2-RF-N05"], why="new P1 line"),
            L("RF-L06", "flexible RF coax, identical live + sham pair for the thrust-stand crossing", 2,
              "rows 117, 133", "LATER", ["RF coax"], ["RFQ-04-R11"], v1_ref="RFQ-04 quantities[5]",
              change="CARRIED_UNCHANGED"),
            L("RF-L07", "vacuum RF feedthrough (ratings as capability ranges, " + TBD_RF + ")",
              "TBD - requires module drawings (ICD ICP-15) + spare (OQ-RFQ-01, OPEN)", "row 8", "P1_NEEDED",
              ["feedthroughs"], ["RFQ-04-R12"], v1_ref="RFQ-04 quantities[4]", change="CARRIED_MODIFIED",
              why="capability-range quoting (A9.2 rf_500W)"),
            L("RF-L08", "50-ohm RF dummy load (rating >= selected generator option; " + TBD_RF + ")", 1,
              "ICD ICP-14 / ICP-17", "P1_NEEDED", ["dummy load"], ["RFQ2-RF-N04"], why="new explicit line"),
            L("RF-L09", "calorimetric cross-check load", 1, "row 72; A9.1 UBQ-04", "P1_NEEDED", [], ["RFQ-04-R10"],
              v1_ref="RFQ-04 quantities[3]", change="CARRIED_UNCHANGED"),
            L("RF-L10", "RF protection / interlock functions: reflected-power monitoring, mismatch interlock, arc "
                        "detection where feasible, thermal monitoring, automatic reduction/shutdown (thresholds after "
                        "characterization)", "1 set (integral or separate; supplier states)", "A9.2 rf_protection; "
                                                                                          "ICD ICP-16",
              "P1_NEEDED", ["RF protection/interlocks"], ["RFQ-04-R03", "RFQ-04-R16"], why="made an explicit line"),
            L("RF-L11", "input power analyzer on the laboratory generator mains input (P_mains,in)", 1,
              "A9.3 OQ-RFQ-06", "P1_NEEDED", [], ["RFQ2-RF-N02", "RFQ2-RF-N03"], why="required by A9.3 OQ-RFQ-06"),
        ],
        "RFQ2-GAS": [
            L("GAS-L01", "Ar MFC (thermal, Ar-calibrated) covering the P1 window around 70 sccm", 1,
              "A9.3 OQ-RFQ-02", "P1_NEEDED", ["Ar/N₂/O₂/Xe MFCs", "calibration"],
              ["RFQ-02-R01", "RFQ-02-R06", "RFQ-02-R14", "RFQ-02-R17", "RFQ2-GAS-N01", "RFQ2-GAS-N02",
               "RFQ2-GAS-N03"], v1_ref="RFQ-02 quantities[2]", change="CARRIED_MODIFIED",
              why="v1 '4 (OQ-RFQ-02)' -> 1 (A9.3 OQ-RFQ-02)"),
            L("GAS-O01", "OPTION: second, overlapping-range Ar MFC - only if one unit cannot cover the P1 sweep",
              "0 or 1 (option line)", "A9.3 OQ-RFQ-02", "P1_NEEDED", ["Ar/N₂/O₂/Xe MFCs"], ["RFQ2-GAS-N02"],
              option=True, why="A9.3 OQ-RFQ-02"),
            L("GAS-L02", "N2 path MFCs, four overlapping ranges", 4, "row 123", "LATER", ["Ar/N₂/O₂/Xe MFCs"],
              ["RFQ-02-R02", "RFQ-02-R03", "RFQ-02-R05", "RFQ-02-R18"], v1_ref="RFQ-02 quantities[0]",
              change="CARRIED_UNCHANGED"),
            L("GAS-L03", "O2 path MFCs, four overlapping ranges, O2-cleaned", 4, "rows 123, 107", "LATER",
              ["Ar/N₂/O₂/Xe MFCs"], ["RFQ-02-R02", "RFQ-02-R04", "RFQ-02-R15", "RFQ-02-R18"],
              v1_ref="RFQ-02 quantities[1]", change="CARRIED_UNCHANGED"),
            L("GAS-L04", "Xe reference-path MFC(s)", "TBD - requires the Xe reference point range (OQ-RFQ-03, OPEN)",
              "A9.1 HIQ-03; row 26", "LATER", ["Ar/N₂/O₂/Xe MFCs"], ["RFQ-02-R07"], v1_ref="RFQ-02 quantities[3]",
              change="CARRIED_UNCHANGED"),
            L("GAS-L05", "C1 steady-flow Xe controller (0.05-0.2 mg/s class)", 1, "row 125", "LATER",
              ["Ar/N₂/O₂/Xe MFCs"], ["RFQ-02-R08", "RFQ-02-R09", "RFQ-02-R10", "RFQ-02-R12", "RFQ-02-R13"],
              v1_ref="RFQ-02 quantities[4]", change="CARRIED_UNCHANGED"),
            L("GAS-L06", "C1 start/diode-flow Xe controller (0.6-0.8 mg/s)", "1 if retained (OQ-RFQ-04, OPEN)",
              "row 125", "LATER", ["Ar/N₂/O₂/Xe MFCs"], ["RFQ-02-R11"], v1_ref="RFQ-02 quantities[5]",
              change="CARRIED_UNCHANGED"),
            L("GAS-O02", "OPTION: ICP dedicated-feed controller (G-ATM / G-XE / diagnostic injection) - quotation "
                         "option only; primary mode G-REUSE", "0 or 1 (option line)", "A9.3 OQ-RFQ-10", "LATER",
              ["Ar/N₂/O₂/Xe MFCs"], ["RFQ-02-R16"], option=True, v1_ref="RFQ-02 quantities[6]",
              change="CARRIED_MODIFIED", why="A9.3 OQ-RFQ-10: QUOTE_OPTION_ONLY"),
            L("GAS-L07", "P1 Ar feed shut-off / isolation valves", p1, "A9.3 OQ-RFQ-07", "P1_NEEDED", ["valves"],
              ["RFQ2-GAS-N07"], why="owner family item"),
            L("GAS-L08", "Xe tank (one quote line per 2/5/10 kg case)", "3 quote lines", "row 48", "LATER", [],
              ["RFQ-07-R01", "RFQ-07-R02", "RFQ-07-R03", "RFQ-07-R04", "RFQ-07-R10", "RFQ-07-R11"],
              v1_ref="RFQ-07 quantities[0]", change="CARRIED_UNCHANGED"),
            L("GAS-L09", "low-flow PMU (regulator)", 1, "row 8", "LATER", ["valves"], ["RFQ-07-R06"],
              v1_ref="RFQ-07 quantities[1]", change="CARRIED_UNCHANGED"),
            L("GAS-L10", "low-flow FCU", 1, "row 8", "LATER", ["valves"], ["RFQ-07-R06", "RFQ-07-R07"],
              v1_ref="RFQ-07 quantities[2]", change="CARRIED_UNCHANGED"),
            L("GAS-L11", "Xe isolation valves (series pair)", 2, "row 90", "LATER", ["valves"],
              ["RFQ-07-R05", "RFQ-07-R09"], v1_ref="RFQ-07 quantities[3]", change="CARRIED_UNCHANGED"),
            L("GAS-O03", "OPTION: filter/getter (C1/Xe branch)", "optional", "row 51", "LATER", [], ["RFQ-07-R08"],
              option=True, v1_ref="RFQ-07 quantities[4]", change="CARRIED_UNCHANGED"),
            L("GAS-L12", "pressure instrumentation: feed/manifold, ICP source-volume and chamber background gauges "
                         "(Ar-calibrated for P1)", p1, "A9.3 OQ-RFQ-07; ICD ICP-34; H2-6", "P1_NEEDED",
              ["pressure instrumentation"], ["RFQ2-GAS-N06"], why="owner family item"),
            L("GAS-L13", "Hall anode gas isolator (350 V continuous; ~1 kV DC representative-gas qualification)",
              "TBD - requires the P1 gas schematic (PENDING " + P1_LANE + ")", "row 105; H2-3 H23-27", "P1_NEEDED",
              ["gas isolators"], ["RFQ2-GAS-N05"], why="owner family item; P1 runs H-1 on Ar"),
            L("GAS-L14", "ICP gas-line isolator - only where a line bridges isolated potentials (none for the capped "
                         "G-REUSE port)", "TBD - requires the P1 potential map (PENDING " + P1_LANE + ")",
              "A9.3 ICPQ-06", "P1_NEEDED", ["gas isolators"], ["RFQ2-GAS-N04"], why="A9.3 ICPQ-06"),
            L("GAS-L15", "Xe-line dielectric break (C1 branch)", "TBD - requires the C1 circuit potentials",
              "H2-2 H3-C1-04", "LATER", ["gas isolators"], ["RFQ-08-R12"], change="CARRIED_UNCHANGED",
              v1_ref="RFQ-08-R12 (requirement; no v1 quantity line)"),
            L("GAS-L16", "calibration: own-gas certificate per device and gas; Ar via rate-of-rise/transfer "
                         "verification; NABL/ISO-17025 for score-bearing N2/O2/Xe", "per device",
              "rows 124, 126; A9.3 OQ-RFQ-02", "P1_NEEDED", ["calibration"],
              ["RFQ-02-R18", "RFQ2-GAS-N03"], why="owner family item made explicit"),
        ],
        "RFQ2-VAC": [
            L("VAC-L01", "chamber interface flanges / adapter plates / internal mounting", "TBD - requires facility "
              "identification (row 139)", "A9.3 OQ-RFQ-07", "P1_NEEDED", ["chamber interfaces"], ["RFQ2-VAC-N01"],
              why="owner family item"),
            L("VAC-L02", "pumping (only where the identified facility lacks it)", "TBD - requires facility "
              "identification (row 139)", "A9.3 OQ-RFQ-07", "P1_NEEDED", ["pumping"], ["RFQ2-VAC-N02"],
              why="owner family item"),
            L("VAC-L03", "electrical vacuum feedthroughs (discharge, collector/bias, magnet, sensing) rated >= 8.33 A",
              p1, "A9.3 OQ-A907-02; row 81", "P1_NEEDED", ["feedthroughs"], ["RFQ2-VAC-N03"], why="owner family item"),
            L("VAC-L04", "gas feedthroughs", p1, "A9.3 OQ-RFQ-07", "P1_NEEDED", ["feedthroughs"], ["RFQ2-VAC-N04"],
              why="owner family item"),
            L("VAC-L05", "RGA head + electronics + differentially pumped sampling system (~200 amu)", 1, "row 127",
              "LATER", ["RGA/diagnostic interfaces"], [f"RFQ-03-R0{i}" for i in range(1, 8)],
              v1_ref="RFQ-03 quantities[0]", change="CARRIED_UNCHANGED"),
            L("VAC-L06", "RGA / diagnostic port provisions", "TBD - requires facility layout (ICD ICP-07)",
              "A9.3 OQ-RFQ-07; INS-22", "LATER", ["RGA/diagnostic interfaces"], ["RFQ2-VAC-N05"],
              why="owner family item"),
        ],
        "RFQ2-HALLEL": [
            L("HE-L01", "H-1 laboratory discharge supply (ground only), floating, 0-350 V, current rating >= 8.33 A "
                        "stand ceiling", 1, "H2-4 H3-PPU-01; row 81; A9.3 OQ-A907-02", "P1_NEEDED",
              ["discharge supply"], ["RFQ-06-R03", "RFQ-06-R05", "RFQ-06-R06", "RFQ2-HALLEL-N01"],
              v1_ref="RFQ-06 quantities[1]", change="CARRIED_MODIFIED",
              why="8.33 A classified as stand ceiling (A9.3 OQ-A907-02); dispatched with P1"),
            L("HE-L02", "H-1 magnet supplies, one per coil, current control, 4-wire remote sense",
              "TBD - one per MC-1 coil (H2-1)", "row 110; H2-4 H3-PPU-02", "P1_NEEDED", ["magnet supply"],
              ["RFQ2-HALLEL-N02"], why="owner family item"),
            L("HE-L03", "floating ICP collector/bias supply with V/I readback (current capability to the 8.33 A stand "
                        "ceiling)", 1, "row 70; ICD ICP-21; A9.3 OQ-A907-02", "P1_NEEDED", [],
              ["RFQ-05-R07", "RFQ2-HALLEL-N01"], v1_ref="RFQ-05 quantities[4]", change="CARRIED_MODIFIED",
              why="moved from v1 RFQ-05; stand-ceiling sizing"),
            L("HE-L04", "isolation hardware for the discharge and collector/bias circuits (350 V + margin)", p1,
              "row 81; ICD ICP-23", "P1_NEEDED", ["isolation"], ["RFQ-05-R08"], why="owner family item"),
            L("HE-L05", "discharge and collector V/I sensing (current ranges >= 8.33 A)", p1,
              "A9.3 OQ-VI-05, OQ-A907-02", "P1_NEEDED", ["sensing"], ["RFQ2-HALLEL-N03"], why="owner family item"),
            L("HE-L06", "flight-representative breadboard Hall discharge supply", 1, "row 113", "LATER",
              ["discharge supply"], ["RFQ-06-R01", "RFQ-06-R02", "RFQ-06-R04"], v1_ref="RFQ-06 quantities[0]",
              change="CARRIED_UNCHANGED"),
            L("HE-L07", "regulated 100 V internal-bus breadboard supply", 1, "row 111", "LATER", [], ["RFQ-06-R16"],
              v1_ref="RFQ-06 quantities[2]", change="CARRIED_UNCHANGED"),
            L("HE-L08", "synchronized V/I channel pairs for the P_bus 1 ms chain",
              "max n_installed over configurations + variant options", "A9-02 slots", "LATER", ["sensing"],
              ["RFQ-06-R07", "RFQ-06-R08", "RFQ-06-R09", "RFQ-06-R10", "RFQ-06-R11", "RFQ-06-R12", "RFQ-06-R13"],
              v1_ref="RFQ-06 quantities[3]", change="CARRIED_UNCHANGED"),
            L("HE-L09", "wide-band I_d(t) probe + digitizer", 1, "row 129", "LATER", ["sensing"], ["RFQ-06-R15"],
              v1_ref="RFQ-06 quantities[4]", change="CARRIED_UNCHANGED"),
            L("HE-L10", "heated LaB6 hollow cathode (C1 control/fallback)", "1 + 1 spare", "row 49; H2-2 H3-C1-01",
              "LATER", [], ["RFQ-08-R01", "RFQ-08-R02", "RFQ-08-R03", "RFQ-08-R08", "RFQ-08-R09", "RFQ-08-R10"],
              v1_ref="RFQ-08 quantities[0]", change="CARRIED_UNCHANGED"),
            L("HE-O01", "OPTION: C1 sacrificial unit for destructive O-exposure", "0 or 1 (owner call OQ-RFQ-01, OPEN)",
              "H2-2 H3-C1-01", "LATER", [], ["RFQ-08-R01"], option=True, v1_ref="RFQ-08 quantities[1]",
              change="CARRIED_UNCHANGED"),
            L("HE-L11", "C1 heater supply", 1, "H2-4 H3-PPU-03", "LATER", [], ["RFQ-08-R07", "RFQ-06-R14"],
              v1_ref="RFQ-08 quantities[2]", change="CARRIED_UNCHANGED"),
            L("HE-L12", "C1 pulsed keeper supply (300-600 V class)", 1, "row 89", "LATER", [], ["RFQ-08-R04"],
              v1_ref="RFQ-08 quantities[3]", change="CARRIED_UNCHANGED"),
            L("HE-L13", "keeper feedthrough + connectors + harness set (ICP-46 isolation)", "TBD - requires module "
              "drawings", "A9.1 ICP-46", "LATER", ["isolation"], ["RFQ-08-R05", "RFQ-08-R06"],
              v1_ref="RFQ-08 quantities[4]", change="CARRIED_UNCHANGED"),
            L("HE-L14", "selectable cathode-common/bleeder network", 1, "row 91", "LATER", [], ["RFQ-08-R11"],
              v1_ref="RFQ-08 quantities[5]", change="CARRIED_UNCHANGED"),
        ],
        "RFQ2-MECH": [
            L("ME-L01", "dielectric source tube/chamber (open-tube coaxial)", "TBD - requires module drawings + spare "
              "(OQ-RFQ-01, OPEN)", "row 8; A9.3 OQ-VI-03", "P1_NEEDED", ["dielectric tube/chamber"],
              ["RFQ-05-R04", "RFQ2-MECH-N01", "RFQ2-MECH-N04"], v1_ref="RFQ-05 quantities[0]",
              change="CARRIED_MODIFIED", why="open-tube coaxial only (A9.3 OQ-VI-03)"),
            L("ME-L02", "RF antenna/coil + shield", "TBD - requires module drawings", "row 8", "P1_NEEDED",
              ["RF antenna/coil"], ["RFQ-05-R05"], v1_ref="RFQ-05 quantities[1]", change="CARRIED_UNCHANGED"),
            L("ME-L03", "electron-extraction collector, 316L (Ar engineering only; material not frozen)",
              "TBD - requires module drawings", "A9.1 A9-03-collector", "P1_NEEDED", ["collector"], ["RFQ-05-R03"],
              v1_ref="RFQ-05 quantities[2]", change="CARRIED_UNCHANGED"),
            L("ME-L04", "collector candidate-material coupons (biased + floating)", "TBD - requires coupon plan",
              "row 106", "LATER", ["collector"], ["RFQ-05-R03"], v1_ref="RFQ-05 quantities[3]",
              change="CARRIED_UNCHANGED"),
            L("ME-L05", "ICP module carrier (modular; future ICP_ORIFICED_VARIANT installable without H-1 redesign)",
              1, "A9.3 OQ-VI-03", "P1_NEEDED", ["carrier"], ["RFQ2-MECH-N02", "RFQ-05-R06"],
              why="owner family item"),
            L("ME-L06", "machined supports (open-frame; radiative-view objective; non-ferromagnetic near H-1)",
              "TBD - requires module drawings", "A9.2 radiative_view_requirement", "P1_NEEDED", ["machined supports"],
              ["RFQ2-MECH-N03"], why="owner family item"),
            L("ME-L07", "module body with capped dedicated gas port + pressure port and MODULE_ID provision",
              "TBD - requires module drawings", "A9.1 HIQ-06; rows 62, 63", "P1_NEEDED", [],
              ["RFQ-05-R01", "RFQ-05-R02", "RFQ-05-R09", "RFQ-05-R10"], why="made an explicit line"),
            L("ME-L08", "on-module mounting provision for the local matching network", 1, "A9.2 OQ-A907-11",
              "P1_NEEDED", [], ["RFQ-05-R13"], why="made an explicit line"),
        ],
        "RFQ2-THRUST": [
            L("TH-L01", "critical-part set for one in-house torsional stand (Option A)", 1, "row 118", "LATER",
              ["stand"], [f"RFQ-01-R{i:02d}" for i in range(1, 19)], v1_ref="RFQ-01 quantities[0]",
              change="CARRIED_UNCHANGED"),
            L("TH-O01", "OPTION: complete open-design torsional stand (Option B, comparison quote only)",
              "0 or 1 (owner call OQ-RFQ-08, OPEN)", "row 118", "LATER", ["stand"], ["RFQ-01-R02"], option=True,
              v1_ref="RFQ-01 quantities[1]", change="CARRIED_UNCHANGED"),
            L("TH-L02", "calibration mass set / force actuator with certificate", 1, "row 119", "LATER",
              ["force calibration"], ["RFQ-01-R09", "RFQ-01-R10"], v1_ref="RFQ-01 quantities[2]",
              change="CARRIED_UNCHANGED"),
            L("TH-L03", "spare flexure pivots", "TBD - requires owner call (OQ-RFQ-01, OPEN)", "-", "LATER", ["stand"],
              [], v1_ref="RFQ-01 quantities[3]", change="CARRIED_UNCHANGED"),
            L("TH-L04", "P1 DAQ: synchronized acquisition of the OQ-VI-05 / ICP-34 channel list on a common time base",
              1, "A9.3 OQ-VI-05, OQ-RFQ-07", "P1_NEEDED", ["DAQ"], ["RFQ2-THRUST-N01"], why="owner family item"),
            L("TH-L05", "temperature sensors for the ICP-34 temperature channels", p1, "ICD ICP-34", "P1_NEEDED",
              ["DAQ"], ["RFQ2-THRUST-N01"], why="P1 temperature channels (A9.3 P1 authorization lists temperature)"),
            L("TH-L06", "traceability hardware: calibration references / certificates for DAQ V/I/T channels, RF "
                        "power sensors and the power analyzer", p1, "A9.3 OQ-RFQ-07; row 126", "P1_NEEDED",
              ["traceability hardware"], ["RFQ2-THRUST-N02", "RFQ-09-R01"], why="owner family item"),
        ],
    }
    return rf


NOT_IN_THIS_REVISION = [
    {"id": "NIR-01", "item": "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE (spacecraft-DC-input 13.56 MHz RF source; measured "
                             "P_DC,in -> P_RF -> I_e)", "package_when_issued": "RFQ2-RF (later separate RFQ)",
     "why": "A9.3 OQ-RFQ-06: the flight/system power question needs a later separate RFQ; not in this revision",
     "source": "A9.3 OQ-RFQ-06"},
    {"id": "NIR-02", "item": "ICP_ORIFICED_VARIANT (orificed RF plasma cathode, Watanabe/Xu type)",
     "package_when_issued": "RFQ2-MECH / RFQ2-RF (A9.x follow-on)",
     "why": "A9.3 OQ-VI-03: not built in P1; the carrier stays modular (RFQ2-MECH-N02)", "source": "A9.3 OQ-VI-03"},
    {"id": "NIR-03", "item": "H-1 anode material / refractory candidates",
     "package_when_issued": "none (design blocker, not a procurement item)",
     "why": "A9.2: ANODE_BASELINE = OPEN; 316L REJECTED_AS_CURRENT_BASELINE for the design-representative/flight anode; "
            "no material is selected, so no anode RFQ is issued", "source": "A9.2 anode_316L, anode_approach"},
    {"id": "NIR-04", "item": "flight C1 integration hardware",
     "package_when_issued": "RFQ2-HALLEL (only if C1 is chosen for flight)",
     "why": "owner question OQ-A907-07 is OPEN (state v3); not answered here", "source": "owner_questions_state_v3"},
    {"id": "NIR-05", "item": "atomic-O source / AO life programme hardware", "package_when_issued": "separate programme",
     "why": "A9 evidence order: separate atomic-O life programme; RFQ-09-R06 stays TBD", "source": "A9; row 132"},
]


# --------------------------------------------------------------------------------------------- common interface
def common_interface() -> dict:
    ic = stand_ceiling_A()
    items = [
        {"id": "CIF-U01", "group": "units", "title": "unit system",
         "value": "SI; flow in mg/s with sccm quoted only with its reference conditions; pressure Pa (Torr only with "
                  "the Pa value); power W; RF frequency MHz; voltage V; current A; temperature K (degC only with the K "
                  "value); mass kg; force mN; length mm",
         "status": "PROPOSED", "freeze_point": "NOW", "source": "v1 conventions (RFQ-02-R12 sccm basis; "
                                                                "documentation 'sccm convention named explicitly')",
         "evidence_class": None},
        {"id": "CIF-U02", "group": "units", "title": "sccm reference conditions",
         "value": "every quoted sccm figure names its reference temperature and pressure; v1/R4 conversions use 0 degC, "
                  "101325 Pa; A9.3 recorder arithmetic uses 7.436e-7 mol/s per sccm (verify against the supplier's "
                  "convention)", "status": "COPIED_VERIFIED", "freeze_point": "NOW",
         "source": "v1 RFQ-02-R12 units; A9.3 recorder_flags[1]", "evidence_class": "model-derived"},
        {"id": "CIF-P01", "group": "reference_planes", "title": "mechanical planes",
         "value": "IP-EXIT (H-1 channel exit plane), IP-NEU (upstream datum face of the downstream ICP module), IP-C1 "
                  "(external C1 module datum), KC-1 (kinematic carrier seat); historical IP-DN unchanged and not used",
         "status": "OWNER_GIVEN", "freeze_point": "LOCK-1", "source": "ICD ICP-01; A9.1 A9-03-planes",
         "evidence_class": "owner-allocation", "dimensions": "TBD - requires LOCK-1 drawings (ICP-02, ICP-05, ICP-07)"},
        {"id": "CIF-P02", "group": "reference_planes", "title": "RF measurement reference plane RP-RF-50",
         "value": "forward/reflected power measured on the generator / 50-ohm side of the local matching network; "
                  "retain P_forward, P_reflected, |Gamma|, VSWR and where possible P_delivered = P_forward - "
                  "P_reflected - P_line/match,loss; never assume P_forward = P_plasma",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.2 rf_measurement_reference; ICD ICP-14",
         "evidence_class": "owner-stated"},
        {"id": "CIF-P03", "group": "reference_planes", "title": "RF chain topology",
         "value": "RF generator -> directional coupler -> 50-ohm transmission line -> LOCAL matching network on / "
                  "immediately adjacent to the ICP module -> ICP antenna (v1 off-platform match superseded)",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.2 OQ-A907-11; ICD ICP-13",
         "evidence_class": "owner-stated"},
        {"id": "CIF-P04", "group": "reference_planes", "title": "power boundaries RP-MAINS and RP-BUS",
         "value": "RP-MAINS = mains input terminals of the laboratory RF generator (P_mains,in; GROUND/FACILITY_ONLY); "
                  "RP-BUS = spacecraft-side DC boundary of A9-02 (P_bus). A quantity measured at RP-MAINS is never "
                  "reported at RP-BUS",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.3 OQ-RFQ-06; A9-02 bus boundary; row 108",
         "evidence_class": "owner-stated"},
        {"id": "CIF-C01", "group": "connectors_flanges", "title": "RF connectors and line impedance",
         "value": "50-ohm line and connectors between generator, coupler and local match; connector family and ratings "
                  "TBD_AFTER_IMPEDANCE_MAP; one family recorded here for all RF packages once selected",
         "status": "TBD", "freeze_point": "after-evidence", "source": "A9.2 rf_500W; ICD ICP-15",
         "evidence_class": None},
        {"id": "CIF-C02", "group": "connectors_flanges", "title": "vacuum flanges and feedthrough ports",
         "value": "TBD - requires facility identification (row 139); each package states its offered flange family; "
                  "the single selected family per port is recorded here before any purchase",
         "status": "TBD", "freeze_point": "after-evidence", "source": "row 139", "evidence_class": None},
        {"id": "CIF-C03", "group": "connectors_flanges", "title": "gas fittings",
         "value": "TBD - requires the P1 gas schematic (PENDING " + P1_LANE + "); O2-wetted fittings ASTM G93 Level C, "
                  "no silver (rows 107, 103)", "status": "PENDING", "freeze_point": "NOW",
         "source": "rows 107, 103; P1 lane", "evidence_class": None},
        {"id": "CIF-C04", "group": "connectors_flanges", "title": "DC power / signal connectors",
         "value": "TBD - requires the harness definition (ICD ICP-34, ICP-35); current-carrying contacts rated to the "
                  "8.33 A stand ceiling", "status": "TBD", "freeze_point": "LOCK-1",
         "source": "ICD ICP-34; A9.3 OQ-A907-02", "evidence_class": None},
        {"id": "CIF-G01", "group": "potentials_grounding", "title": "potential nodes",
         "value": {"N-FG": "facility ground", "N-ANODE": "H-1 anode", "N-CC": "C1 cathode common (hall_c1_reference)",
                   "N-ICPREF": "ICP electron-source reference / collector node (hall_icp_neutralizer)",
                   "N-BODY": "ICP dielectric/body (floating by default)", "N-RF": "antenna circuit (RF)"},
         "status": "PROPOSED", "freeze_point": "LOCK-1", "source": "ICD ICP-20, ICP-21, ICP-22, ICP-44",
         "evidence_class": None, "note": "node names are organizational labels of this document"},
        {"id": "CIF-G02", "group": "potentials_grounding", "title": "V_d definition",
         "value": "V_d = V_anode - V_electron-source-reference; supply-terminal voltage and loop drops recorded",
         "status": "OWNER_GIVEN", "freeze_point": "LOCK-1", "source": "A9.1 A9-03-Vd; ICD ICP-22",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-G03", "group": "potentials_grounding", "title": "ICP body and collector",
         "value": "ICP dielectric/body floating unless the validated circuit requires otherwise; collector bias "
                  "controlled and measured separately; never hard-grounded by default",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "row 70; ICD ICP-20, ICP-21",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-G04", "group": "potentials_grounding", "title": "DC isolation class",
         "value": {"V_upper_before_margin": 350.0, "margin": "TBD - owner item (row 81)"},
         "status": "OWNER_GIVEN", "freeze_point": "LOCK-1", "source": "row 81; ICD ICP-23",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-G05", "group": "potentials_grounding", "title": "gas isolation across potentials",
         "value": {"hall_isolator_continuous_V": 350.0, "qualification_V_DC": 1000.0,
                   "rule": "isolator only where a gas line bridges isolated potentials; none between ends held at "
                           "essentially the same floating potential"},
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "row 105; A9.3 ICPQ-06",
         "evidence_class": "owner-stated",
         "note": "owner wording is '~1 kV DC' (a class, not a precise value); exact test voltage and margin freeze with "
                 "the H-1 isolation margin (row 81)"},
        {"id": "CIF-G06", "group": "potentials_grounding", "title": "C1 keeper pulse isolation",
         "value": {"upper_operating_pulse_V": 600.0, "design_isolation_basis_V": 900.0, "hipot_kV_DC": 1.0},
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.1 ICP-46 (carried RFQ-08-R05/R06)",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-E01", "group": "electrical", "title": "stand current ceiling",
         "value": ic, "units": "A", "status": "OWNER_GIVEN", "freeze_point": "NOW",
         "source": "A9.3 OQ-A907-02 (1500 W / 180 V; bench ceiling, not an H-1 requirement)",
         "evidence_class": "owner-stated"},
        {"id": "CIF-E02", "group": "electrical", "title": "RF frequency and investigation capability",
         "value": {"frequency_MHz": 13.56, "delivered_operating_capability_W": [0.0, 500.0],
                   "component_ratings": TBD_RF},
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "row 72; A9.2 rf_500W",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-S01", "group": "gas_species", "title": "species and labels",
         "value": {"Ar": "ENGINEERING_ONLY_NON_SCORING (topology reproduction; P1)", "N2": "score-bearing (LATER)",
                   "O2-bearing": "label NO_ATOMIC_O; ASTM G93 Level C (LATER)", "Xe": "reference / C1 path (LATER)",
                   "atomic O": "separate life programme (not in this revision)"},
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9 evidence order; row 36; ICD ICP-30; row 107",
         "evidence_class": "owner-allocation"},
        {"id": "CIF-S02", "group": "gas_species", "title": "ICP gas mode",
         "value": "G-REUSE primary (mdot_ICP,dedicated = 0); capped dedicated port retained; G-ATM / G-XE / diagnostic "
                  "injection only as declared variants, booked in the corresponding atmospheric/Xe ledger if activated",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.1 HIQ-06; A9.3 OQ-RFQ-10; ICD ICP-26",
         "evidence_class": "owner-stated"},
        {"id": "CIF-T01", "group": "time_data", "title": "common time base",
         "value": "every package's data interface time-stamps against the DAQ common time base (INS-18)",
         "status": "COPIED_VERIFIED", "freeze_point": "LOCK-1", "source": "INS-18", "evidence_class": None},
    ]
    matrix = [
        ("X-01", "RFQ2-RF", "RFQ2-MECH", "local match mounted on / immediately adjacent to the ICP module; antenna "
         "connection", "IP-NEU; N-RF", "mm; V (RF peak)", "TBD_AFTER_IMPEDANCE_MAP (ratings); LOCK-1 (mounting)",
         "A9.2 OQ-A907-11; RFQ-04-R17; RFQ-05-R13", "P1_NEEDED"),
        ("X-02", "RFQ2-RF", "RFQ2-VAC", "RF vacuum feedthrough on a chamber port", "CIF-C02", "W; V",
         "TBD_AFTER_IMPEDANCE_MAP", "RFQ-04-R12; ICD ICP-15", "P1_NEEDED"),
        ("X-03", "RFQ2-RF", "RFQ2-THRUST", "flexible live + sham coax crossing the stand", "KC-1", "-",
         "OWNER_GIVEN (rows 117, 133)", "RFQ-04-R11", "LATER"),
        ("X-04", "RFQ2-RF", "RFQ2-THRUST", "P_fwd, P_refl, |Gamma|, interlock state, P_mains,in into the DAQ",
         "RP-RF-50; RP-MAINS", "W; -", "OWNER_GIVEN (quantities); rates PENDING P1", "A9.3 OQ-RFQ-06; ICD ICP-34",
         "P1_NEEDED"),
        ("X-05", "RFQ2-RF", "RFQ2-HALLEL", "RF interlock permissives incl. collector/bias supply state and discharge "
         "supply state", "-", "-", "TBD (trip values from measured S1a behaviour)", "ICD ICP-16; A9.2 rf_protection",
         "P1_NEEDED"),
        ("X-06", "RFQ2-GAS", "RFQ2-VAC", "gas feedthroughs and gauge ports on the chamber", "CIF-C02; CIF-C03",
         "Pa; -", "PENDING P1 gas schematic", "RFQ2-VAC-N04; RFQ2-GAS-N06", "P1_NEEDED"),
        ("X-07", "RFQ2-GAS", "RFQ2-MECH", "capped ICP dedicated gas port and pressure port; isolator only if a line "
         "bridges isolated potentials", "N-BODY; N-FG", "V; Pa", "OWNER_GIVEN (capped port); count PENDING P1",
         "RFQ-05-R09; A9.3 ICPQ-06, OQ-RFQ-10", "P1_NEEDED"),
        ("X-08", "RFQ2-GAS", "RFQ2-HALLEL", "Hall anode gas isolator between N-FG and N-ANODE", "N-ANODE; N-FG", "V",
         "OWNER_GIVEN (350 V continuous; ~1 kV DC qualification)", "row 105; RFQ2-GAS-N05", "P1_NEEDED"),
        ("X-09", "RFQ2-GAS", "RFQ2-THRUST", "MFC setpoint/readback and gauge signals into the DAQ; harp crossing on "
         "the stand (LATER)", "CIF-T01", "mg/s; Pa", "PENDING P1 (rates)", "RFQ2-THRUST-N01; row 117", "P1_NEEDED"),
        ("X-10", "RFQ2-HALLEL", "RFQ2-VAC", "electrical feedthroughs for discharge, collector/bias, magnet and sensing",
         "N-ANODE; N-ICPREF; N-FG", "A; V", "OWNER_GIVEN (8.33 A ceiling; 350 V + margin TBD)",
         "A9.3 OQ-A907-02; row 81; RFQ2-VAC-N03", "P1_NEEDED"),
        ("X-11", "RFQ2-HALLEL", "RFQ2-MECH", "collector lead and body-potential sense on the ICP module",
         "N-ICPREF; N-BODY", "A; V", "TBD (collector V/I range A902-23)", "ICD ICP-20, ICP-21", "P1_NEEDED"),
        ("X-12", "RFQ2-HALLEL", "RFQ2-THRUST", "V_d(t), I_d(t), I_e,ICP(t), potentials into the DAQ; P_bus 1 ms chain "
         "synchronization (LATER)", "CIF-G02; CIF-T01", "V; A", "OWNER_GIVEN (quantities); rates PENDING P1",
         "A9.3 OQ-VI-05; A9.1 OQ-A902-01", "P1_NEEDED"),
        ("X-13", "RFQ2-MECH", "RFQ2-THRUST", "ICP module carrier on KC-1 of the stand; module mass/CG", "KC-1; IP-NEU",
         "kg; mm", "TBD (ICD ICP-06, ICP-08; LOCK-1)", "RFQ-01-R04, R13", "LATER"),
        ("X-14", "RFQ2-MECH", "RFQ2-VAC", "P1 mounting of H-1 + ICP carrier inside the chamber; envelope and keep-outs",
         "IP-EXIT; IP-NEU", "mm", "TBD (ICD ICP-07; facility)", "RFQ2-VAC-N01; RFQ2-MECH-N02", "P1_NEEDED"),
        ("X-15", "RFQ2-VAC", "RFQ2-THRUST", "thrust stand in the chamber (mounting, services, background pressure)",
         "CIF-C02", "Pa; mm", "TBD (facility identification, row 139)", "RFQ-01-R18", "LATER"),
        ("X-16", "RFQ2-MECH", "RFQ2-RF", "antenna/coil drawing <-> local-match output and RF feedthrough in-vacuum "
         "leads (combined DC+RF stress)", "N-RF; N-BODY", "V (RF peak); mm (creepage)", "TBD (ICD ICP-44)",
         "ICD ICP-44", "P1_NEEDED"),
    ]
    mat = [{"id": a, "between": [b, c], "what": d, "reference": e, "units": f, "status": g, "source": h,
            "dispatch": i} for a, b, c, d, e, f, g, h, i in matrix]
    for row in mat:
        for pk in row["between"]:
            if pk not in PKG_IDS:
                raise KeyError(pk)
    return {"id": CIF_ID, "title": "RFQ v2 common top-level interface document",
            "purpose": "keeps the six supplier-speciality packages compatible: shared interface ids, reference planes, "
                       "connectors/flanges, potentials/grounding, gas species, units and the cross-package interface "
                       "matrix. It governs over local package wording; any change is a new revision of this document.",
            "source_quote": A93("OQ-RFQ-07", "A common top-level interface document should ensure the separate "
                                             "packages remain compatible."),
            "banner": banner_lines(), "items": items, "interface_matrix": mat,
            "package_file": PKG_DIR + "/RFQ2-00_common_interface.md"}


# ------------------------------------------------------------------------------------------------- package assembly
V1_FIELD_OVERRIDES = {
    # (v1 package, field, index) -> v2 package (default: primary package of the v1 package)
    ("RFQ-05", "acceptance", 1): "RFQ2-HALLEL",
    ("RFQ-05", "calibration_traceability", 0): "RFQ2-HALLEL",
    ("RFQ-09", "calibration_traceability", 0): "RFQ2-THRUST",
    ("RFQ-09", "documentation", 0): "RFQ2-THRUST",
}

V2_ADDITIONS = {
    "RFQ2-RF": {
        "acceptance": ["dummy-load characterization of generator + coupler chain and pickup test with the generator "
                       "into the dummy load (ICD ICP-14, ICP-17)",
                       "functional test of each required protection feature (A9.2 rf_protection); trip thresholds set "
                       "after characterization, never invented at acceptance",
                       "power-analyzer calibration certificate with uncertainty and coverage factor stated"],
        "documentation": ["capability-range / scalable-option table with the ratings of each option (A9.2 rf_500W)",
                          "mains input interface of the generator (phases, voltage, frequency) for the power analyzer"],
    },
    "RFQ2-GAS": {
        "acceptance": ["Ar MFC verified by the rate-of-rise/transfer calibration path (A9.3 OQ-RFQ-02)",
                       "~1 kV DC representative-pressure/gas withstand of every isolator that bridges isolated "
                       "potentials: flashover, leakage, breakdown, surface tracking, repeated exposure where "
                       "appropriate (row 105; A9.3 ICPQ-06)"],
        "documentation": ["statement whether one Ar unit covers the P1 sweep, or the second overlapping range option "
                          "is needed (A9.3 OQ-RFQ-02)"],
    },
    "RFQ2-VAC": {"documentation": ["feedthrough current (>= 8.33 A stand ceiling) and voltage ratings per pin"]},
    "RFQ2-HALLEL": {"documentation": ["current capability of every supply/sensor relative to the 8.33 A stand ceiling "
                                      "(A9.3 OQ-A907-02)"]},
    "RFQ2-MECH": {"acceptance": ["open-tube coaxial geometry per the LOCK-1 drawings (A9.3 OQ-VI-03)"],
                  "documentation": ["carrier interface drawing showing the modular exchange provision (A9.3 OQ-VI-03)"]},
    "RFQ2-THRUST": {"acceptance": ["DAQ channel audit against RFQ2-THRUST-N01 / ICD ICP-34 before first P1 run"]},
}

COMMON_SUPPLIER_MUST_STATE_V2 = [
    "per line: compliance (COMPLIANT / DEVIATION with justification / NOT OFFERED); option lines quoted separately",
    "per interface id of RFQ2-CIF touched by the quoted item: compliance and the offered connector/flange family",
]


def assemble_packages(reqs: list, items: dict) -> list:
    v1 = {p["id"]: p for p in load("V1_JSON")["packages"]}
    primary = {v1id: pk for pk, _n, _s, _h, v1s in PACKAGES for v1id in v1s}
    carried = {pk: {"acceptance": [], "calibration_traceability": [], "documentation": [], "reference_data": [],
                    "supplier_must_state": []} for pk in PKG_IDS}
    for v1id, p in v1.items():
        for fld in ("acceptance", "calibration_traceability", "documentation"):
            for i, x in enumerate(p[fld]):
                if x.startswith("n/a"):
                    continue
                pk = V1_FIELD_OVERRIDES.get((v1id, fld, i), primary[v1id])
                carried[pk][fld].append({"text": x, "carried_from": f"v1 {v1id} {fld}[{i}]"})
        for i, x in enumerate(p["reference_data"]):
            e = copy.deepcopy(x)
            e["carried_from"] = f"v1 {v1id} reference_data[{i}]"
            carried[primary[v1id]]["reference_data"].append(e)
        for x in p["supplier_must_state"]:
            lst = carried[primary[v1id]]["supplier_must_state"]
            if x not in [y["text"] for y in lst]:
                lst.append({"text": x, "carried_from": f"v1 {v1id}"})
    out = []
    for pk, num, slug, heading, v1s in PACKAGES:
        owner_items = owner_family_items(heading)
        lits = items[pk]
        coverage = {oi: [li["id"] for li in lits if oi in li["covers_owner_items"]] for oi in owner_items}
        for li in lits:
            for oi in li["covers_owner_items"]:
                if oi not in owner_items:
                    raise KeyError(f"{li['id']} covers unknown owner item {oi!r} of {heading}")
        missing = [k for k, v in coverage.items() if not v]
        if missing:
            raise ValueError(f"{pk}: owner minimum-scope items not covered: {missing}")
        preqs = [r for r in reqs if r["package"] == pk]
        known = {r["id"] for r in reqs} | {r["v1_id"] for r in reqs if r["v1_id"]}
        for li in lits:
            for rid in li["requirements"]:
                if rid not in known:
                    raise KeyError(f"{li['id']} names unknown requirement {rid}")
        add = V2_ADDITIONS.get(pk, {})
        pkg = {
            "id": pk, "number": num, "slug": slug, "owner_family": heading,
            "owner_minimum_scope_verbatim": owner_items, "owner_minimum_scope_coverage": coverage,
            "v1_packages_folded_in": sorted({r["change"]["v1_package"] for r in preqs if r["change"]["v1_package"]}),
            "banner": banner_lines(),
            "line_items": lits,
            "requirements": preqs,
            "p1_needed_line_items": [li["id"] for li in lits if li["dispatch"] == "P1_NEEDED"],
            "later_line_items": [li["id"] for li in lits if li["dispatch"] == "LATER"],
            "acceptance": carried[pk]["acceptance"] + [{"text": t, "carried_from": None} for t in
                                                       add.get("acceptance", [])],
            "calibration_traceability": carried[pk]["calibration_traceability"],
            "documentation": carried[pk]["documentation"] + [{"text": t, "carried_from": None} for t in
                                                             add.get("documentation", [])],
            "reference_data": carried[pk]["reference_data"],
            "reference_data_use": "REFERENCE ONLY - published/catalogue data as recorded by the web track (citation/"
                                  "URL and access record as recorded there); not a requirement, selection or ranking",
            "supplier_must_state": carried[pk]["supplier_must_state"] + [{"text": t, "carried_from": None} for t in
                                                                         COMMON_SUPPLIER_MUST_STATE_V2],
            "open_specification_items": [{"id": r["id"], "v1_id": r["v1_id"], "title": r["title"],
                                          "value": r["value"], "freeze_point": r["freeze_point"],
                                          "dispatch": r["dispatch"]}
                                         for r in preqs if r["status"] in ("TBD", "PENDING")],
            "cif_interfaces": [x["id"] for x in common_interface()["interface_matrix"] if pk in x["between"]],
            "package_file": f"{PKG_DIR}/RFQ2-{num}_{slug}.md",
        }
        if pk == "RFQ2-VAC":
            pkg["facilities_recorded_R5"] = copy.deepcopy(v1["RFQ-09"]["facilities_recorded_R5"])
            pkg["facilities_note"] = "file order, not a ranking; nobody contacted; requests to ISRO/LPSC are owner " \
                                     "actions (carried RFQ-09-R03)"
        if pk == "RFQ2-RF":
            pkg["not_in_this_revision"] = [x for x in NOT_IN_THIS_REVISION if x["id"] == "NIR-01"]
        if pk == "RFQ2-MECH":
            pkg["not_in_this_revision"] = [x for x in NOT_IN_THIS_REVISION if x["id"] in ("NIR-02", "NIR-03")]
        out.append(pkg)
    return out


# ------------------------------------------------------------------------------------------------ top-level sections
def change_log(reqs: list, pkgs: list) -> dict:
    per_line = [{"v2_id": r["id"], "v1_id": r["v1_id"], "v1_package": r["change"]["v1_package"],
                 "v2_package": r["package"], "change": r["change"]["type"], "why": r["change"]["why"],
                 "dispatch": r["dispatch"]} for r in reqs]
    per_item = [{"v2_id": li["id"], "v2_package": p["id"], "v1_ref": li["v1_ref"], "change": li["change"]["type"],
                 "why": li["change"]["why"], "dispatch": li["dispatch"], "option_line": li["option_line"]}
                for p in pkgs for li in p["line_items"]]
    package_level = [
        {"id": "CL-01", "change": "nine v1 item families (RFQ-01..09) -> six supplier-speciality packages + one common "
                                  "interface document", "source": "A9.3 OQ-RFQ-07"},
        {"id": "CL-02", "change": "every package header states: technical team prepares; commercial dispatch authority "
                                  "P9E/Vyovrinda under Praveen's authorization; no automatic supplier contact",
         "source": "A9.3 OQ-RFQ-07"},
        {"id": "CL-03", "change": "every line tagged P1_NEEDED or LATER so the owner can dispatch P1 items first",
         "source": "A9.3 authorizations P1 (P1 not waiting for later questions)"},
        {"id": "CL-04", "change": "mains-fed laboratory generator GROUND/FACILITY_ONLY + input power analyzer line; "
                                  "flight-representative DC-input RF source listed as not in this revision",
         "source": "A9.3 OQ-RFQ-06"},
        {"id": "CL-05", "change": "Ar: one MFC (second overlapping range as option line only), rate-of-rise/transfer "
                                  "verification, ENGINEERING_ONLY_NON_SCORING; four ranges only for N2/O2",
         "source": "A9.3 OQ-RFQ-02"},
        {"id": "CL-06", "change": "ICP dedicated-feed controller quoted as option line only; G-REUSE primary; capped "
                                  "port kept; booking rule if activated", "source": "A9.3 OQ-RFQ-10"},
        {"id": "CL-07", "change": "local match on / immediately adjacent to the ICP module; RF component ratings "
                                  "TBD_AFTER_IMPEDANCE_MAP quoted as capability ranges; protection features listed; "
                                  "explicit RF dummy load", "source": "A9.2 OQ-A907-11, rf_500W, rf_protection"},
        {"id": "CL-08", "change": "ICP gas-line isolators ~1 kV DC representative-gas qualification only where a line "
                                  "bridges isolated potentials; Hall anode gas isolator made a P1 line",
         "source": "A9.3 ICPQ-06; row 105"},
        {"id": "CL-09", "change": "current-carrying items sized to the 8.33 A stand ceiling (bench ceiling, not an H-1 "
                                  "requirement; ICP-45 requirement = registered H-1 maximum)",
         "source": "A9.3 OQ-A907-02"},
        {"id": "CL-10", "change": "open-tube coaxial ICP only; modular carrier for a future ICP_ORIFICED_VARIANT",
         "source": "A9.3 OQ-VI-03"},
        {"id": "CL-11", "change": "P1 DAQ / sensing lines for the OQ-VI-05 topology-control records (non-scoring)",
         "source": "A9.3 OQ-VI-05"},
    ]
    counts = {}
    for r in reqs:
        counts[r["change"]["type"]] = counts.get(r["change"]["type"], 0) + 1
    return {"package_level": package_level, "per_requirement": per_line, "per_line_item": per_item,
            "counts": dict(sorted(counts.items()))}


def traceability(reqs: list) -> list:
    return [{"requirement": r["id"], "v1_id": r["v1_id"], "package": r["package"], "title": r["title"],
             "sources": sorted({label(s) for s in r["sources"]}), "status": r["status"],
             "freeze_point": r["freeze_point"], "dispatch": r["dispatch"], "change": r["change"]["type"]}
            for r in reqs]


def owner_answers_applied(reqs: list) -> dict:
    rows: dict = {}
    ids: dict = {"a9_1": {}, "a9_2": {}, "a9_3": {}}
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "owner_row":
                rows.setdefault(s["row"], set()).add(r["id"])
            elif s["type"] in ids:
                ids[s["type"]].setdefault(s["id"], set()).add(r["id"])
    ans = answers()
    row_list = [{"row": k, "covers_ids": ans[k]["covers_ids"],
                 "answer_sha256": hashlib.sha256(ans[k]["owner_answer_verbatim"].encode("utf-8")).hexdigest(),
                 "how_applied": "applied in " + ", ".join(sorted(v))} for k, v in sorted(rows.items())]
    a93_how = {
        "OQ-RFQ-07": "six supplier-speciality packages with the owner item lists verbatim as minimum scope + RFQ2-CIF; "
                     "dispatch statement in every package header",
        "OQ-RFQ-06": "RFQ-04-R04 modified; power analyzer RFQ2-RF-N02; boundary labels RFQ2-RF-N03; NIR-01",
        "OQ-RFQ-02": "Ar window/count/traceability RFQ2-GAS-N01..N03; RFQ-02-R02/R06/R18 modified",
        "OQ-RFQ-10": "RFQ-02-R16 modified to an option line (GAS-O02)",
        "ICPQ-06": "RFQ2-GAS-N04; CIF-G05",
        "OQ-A907-02": "RFQ2-HALLEL-N01, RFQ2-VAC-N03, RFQ-05-R07/RFQ-06-R04/R06 modified; CIF-E01",
        "OQ-VI-03": "RFQ2-MECH-N01/N02; NIR-02",
        "OQ-VI-05": "RFQ2-HALLEL-N03; RFQ2-THRUST-N01",
    }
    a93 = [{"id": k, "status": load("A93")["decisions"][k]["status"], "how_applied": a93_how[k],
            "applied_in": sorted(ids["a9_3"].get(k, set()))} for k in a93_how]
    return {"owner_rows": row_list,
            "a9_1": [{"id": k, "applied_in": sorted(v)} for k, v in sorted(ids["a9_1"].items())],
            "a9_2": [{"id": k, "applied_in": sorted(v)} for k, v in sorted(ids["a9_2"].items())],
            "a9_3": a93}


def open_owner_questions() -> dict:
    state = {q["id"]: q for q in load("OQS3")["rows"]}
    carried = []
    for qid in ("OQ-RFQ-01", "OQ-RFQ-03", "OQ-RFQ-04", "OQ-RFQ-08", "OQ-RFQ-09"):
        q = state[qid]
        carried.append({"id": qid, "question": q["question"], "state_v3_status": q["status"],
                        "note": "carried unchanged from v1; not answered here"})
    answered = []
    for qid in ("OQ-RFQ-02", "OQ-RFQ-05", "OQ-RFQ-06", "OQ-RFQ-07", "OQ-RFQ-10"):
        q = state[qid]
        answered.append({"id": qid, "state_v3_status": q["status"], "answer_pointer": q.get("answer_pointer")})
    new = [
        {"id": "OQ-RFQV2-01", "question": "Must the Ar MFC certificate be ISO/IEC 17025 / NABL-accredited, or is the "
                                          "maker's Ar calibration plus the in-house rate-of-rise/transfer verification "
                                          "sufficient (Ar is ENGINEERING_ONLY_NON_SCORING; row 126 governs "
                                          "score-bearing flow)?",
         "proposed_answer": "maker's Ar-specific certificate + rate-of-rise/transfer verification; accredited "
                            "certificate optional (owner call)", "needed_by": "P1 RFQ dispatch"},
        {"id": "OQ-RFQV2-02", "question": "Does the domestic engineering chamber for P1 (row 139) already provide "
                                          "pumping, or must RFQ2-VAC request pumping quotations?",
         "proposed_answer": "owner call (facility identification)", "needed_by": "P1 RFQ dispatch"},
        {"id": "OQ-RFQV2-03", "question": "May one calorimetric dummy load serve both the dummy-load and the "
                                          "calorimetric cross-check functions?",
         "proposed_answer": "allowed if the supplier certifies both functions separately; owner call",
         "needed_by": "P1 RFQ dispatch"},
        {"id": "OQ-RFQV2-04", "question": "Package placement of items outside the owner's six item lists: collector/"
                                          "bias supply and C1 cathode/keeper/heater in Hall electrical; Xe tank/PMU/FCU "
                                          "in gas/metrology; power analyzer in RF; RFQ-09 information in vacuum/facility "
                                          "and thrust/metrology. Accept?",
         "proposed_answer": "YES (supplier speciality: DC supplies / gas hardware / RF metrology)",
         "needed_by": "dispatch of the affected package"},
        {"id": "OQ-RFQV2-05", "question": "Is an existing laboratory magnet supply available for the P1 H-1 runs, "
                                          "or is HE-L02 dispatched with the P1 set?",
         "proposed_answer": "owner call", "needed_by": "P1 RFQ dispatch"},
    ]
    return {"new": new, "carried_open_from_v1": carried, "v1_questions_answered_since": answered,
            "state_file": DELIVERABLES["OQS3"][0], "state_sha256": DELIVERABLES["OQS3"][1],
            "rule": "no OPEN owner question of state v3 is answered by this lane"}


def interface_demands() -> list:
    return [
        {"id": "IFD-01", "from": "P1 lane " + P1_LANE, "to": "RFQ2-GAS, RFQ2-VAC, RFQ2-HALLEL, RFQ2-THRUST",
         "quantity": "Ar sweep bounds; gas schematic (valves, isolators, feedthroughs); pressure ranges; DAQ channel "
                     "count/sample rate/bandwidth; magnet setpoints; uncertainty targets", "units": "sccm; Pa; Sa/s; A",
         "status": "PENDING " + P1_LANE},
        {"id": "IFD-02", "from": "RFQ2-RF, RFQ2-GAS, RFQ2-HALLEL, RFQ2-THRUST (quotations)", "to": "P1 lane " + P1_LANE,
         "quantity": "offered capability ranges, calibration uncertainties, interfaces", "units": "W; mg/s; A; -",
         "status": "OPEN (after quotations)"},
        {"id": "IFD-03", "from": "P2 prep lane " + P2_LANE, "to": "RFQ2-RF",
         "quantity": "V/I sensing, coupler chain, calibration/de-embedding and S-parameter method requirements",
         "units": "-", "status": "PENDING " + P2_LANE},
        {"id": "IFD-04", "from": "P2 impedance map (after P1 stable plasma)", "to": "RFQ2-RF, RFQ2-VAC, CIF-C01",
         "quantity": "Z_antenna = R + jX envelope -> component ratings (generator, coupler, coax, connectors, matching "
                     "elements, feedthroughs, dummy load)", "units": "ohm; W; V; A",
         "status": "TBD_AFTER_IMPEDANCE_MAP"},
        {"id": "IFD-05", "from": "H2-1 (docs/hardware/h2/h2_1_hall_chamber_magnet/)", "to": "RFQ2-HALLEL",
         "quantity": "MC-1 coil count, currents and resistances for the magnet supplies", "units": "A; ohm",
         "status": "OPEN (H2-1 PRELIMINARY)"},
        {"id": "IFD-06", "from": "H2-3 (H23-27, H23-29)", "to": "RFQ2-GAS", "quantity": "isolator position and p d range",
         "units": "Pa; Torr cm", "status": "COPIED (PRELIMINARY)"},
        {"id": "IFD-07", "from": "H2-4 (H24-27, H24-32, H3-PPU-01/02)", "to": "RFQ2-HALLEL",
         "quantity": "laboratory supply partition and ratings", "units": "A; V", "status": "COPIED"},
        {"id": "IFD-08", "from": "RFQ2-* (supplier datasheets)", "to": "A9-06 docs/budgets/mass_a9/",
         "quantity": "quoted masses of flight-representative options", "units": "kg", "status": "OPEN (after "
                                                                                             "quotations)"},
        {"id": "IFD-09", "from": "RFQ2-GAS GAS-O02 (if a dedicated-feed variant is ever activated)",
         "to": "A9-08 Xe booking / atmospheric flow booking",
         "quantity": "mdot_ICP,dedicated", "units": "mg/s",
         "status": "NOT ACTIVE (G-REUSE primary; A9.3 OQ-RFQ-10 booking rule)"},
        {"id": "IFD-10", "from": "A9-03 ICD (ICP-07, ICP-15, ICP-43, ICP-44, ICP-45, ICP-47)",
         "to": "RFQ2-MECH, RFQ2-RF, RFQ2-HALLEL", "quantity": "envelope, RF ratings, heat load, antenna voltage, I_d,max,H1, "
                                                             "view-factor geometry", "units": "mm; W; V; A",
         "status": "TBD (LOCK-1 / after-evidence)"},
        {"id": "IFD-11", "from": "facility identification (row 139)", "to": "RFQ2-VAC, CIF-C02",
         "quantity": "chamber ports, flange families, pumping", "units": "mm; L/s", "status": "OPEN (owner action)"},
        {"id": "IFD-12", "from": "RFQ2-*", "to": "M16 v3 rows 6-8, 11-13, 15, 16, 18, 19",
         "quantity": "procurement status proposal", "units": "-", "status": "PROPOSED (see m16_impact)"},
    ]


def m16_impact() -> list:
    rows = {r["row"]: r for r in load("M16V3")["rows"]}
    spec = [
        (6, "RFQ2-GAS", "Xe tank quote lines (LATER)"), (7, "RFQ2-GAS", "low-flow PMU (LATER)"),
        (8, "RFQ2-GAS", "C1 controllers, FCU, Xe reference MFC (LATER)"),
        (11, "RFQ2-HALLEL", "C1 cathode + keeper/heater supplies (LATER)"),
        (12, "RFQ2-HALLEL, RFQ2-RF", "laboratory discharge/magnet/collector supplies (P1), breadboard supplies (LATER), "
                                     "laboratory RF generator (P1, ground only)"),
        (13, "RFQ2-MECH", "ICP material temperature data; ICP_COUPLED_THERMAL stays UNRESOLVED (no PASS)"),
        (15, "RFQ2-GAS, RFQ2-THRUST, RFQ2-VAC, RFQ2-RF", "P1 DAQ, gauges, Ar MFC, RF metrology, power analyzer (P1); "
                                                         "stand, RGA (LATER)"),
        (16, "RFQ2-MECH, RFQ2-THRUST", "modular ICP carrier and supports (P1); stand/KC-1 (LATER)"),
        (18, "RFQ2-MECH, RFQ2-HALLEL, RFQ2-GAS", "open-tube coaxial ICP head parts, collector/bias supply, capped port "
                                                "(P1)"),
        (19, "RFQ2-RF", "development RF chain with local match (P1, ground only); the flight DC-input RF source is not "
                        "in this revision (NIR-01); ratings TBD_AFTER_IMPEDANCE_MAP"),
        (20, "none", "no anode RFQ (A9.2 ANODE_BASELINE OPEN; NIR-03)"),
        (21, "none", "no anode heat-path RFQ (design blocker)"),
    ]
    out = []
    for row, pk, how in spec:
        r = rows[row]
        status = ("NO_RFQ (design blocker; A9.2)" if pk == "none" else
                  "RFQ_V2_SPEC_READY_QUOTATION_ONLY (P1 subset dispatchable first by the owner; no purchase order; "
                  "H3 gate)")
        out.append({"m16_row": row, "key": r["key"], "name": r["name"], "packages": pk, "how_touched": how,
                    "proposed_procurement_status": status,
                    "note": "proposal only; M16 v3 is not edited by this lane"})
    return out


def h3_h4_inputs(pkgs: list) -> dict:
    gate = []
    for p in pkgs:
        gate.append({"id": p["id"], "owner_family": p["owner_family"],
                     "p1_needed_line_items": p["p1_needed_line_items"],
                     "open_items_blocking_po": [o["id"] for o in p["open_specification_items"]]})
    return {
        "h3_procurement_gate": {"state": "QUOTATION PACKAGES v2 READY FOR OWNER DISPATCH (P1 subset first); PURCHASE "
                                         "ORDERS NOT AUTHORIZED",
                                "purchase_gate": "H3 procurement gate + frozen A9 interfaces (owner row 8; A9.1 A9-09 "
                                                 "procurement restriction)",
                                "packages": gate},
        "h4_tests": [
            {"id": "H4-RFQ2-01", "test": "~1 kV DC representative-pressure/gas withstand of each gas isolator bridging "
                                         "isolated potentials (Ar for P1)", "source": "row 105; A9.3 ICPQ-06"},
            {"id": "H4-RFQ2-02", "test": "RF chain characterization into the dummy load; pickup on all channels",
             "source": "ICD ICP-14, ICP-17"},
            {"id": "H4-RFQ2-03", "test": "RF protection functions (each feature) with thresholds set after "
                                         "characterization", "source": "A9.2 rf_protection"},
            {"id": "H4-RFQ2-04", "test": "Ar MFC rate-of-rise/transfer verification", "source": "A9.3 OQ-RFQ-02"},
            {"id": "H4-RFQ2-05", "test": "DAQ channel audit (OQ-VI-05 + ICP-34 list) before the first P1 run",
             "source": "A9.3 OQ-VI-05; ICD ICP-34"},
            {"id": "H4-RFQ2-06", "test": "power-analyzer / coupler / calorimetric cross-check at the labelled "
                                         "boundaries RP-MAINS and RP-RF-50", "source": "A9.3 OQ-RFQ-06; row 72"},
        ],
    }


def historical_reuse() -> dict:
    return {
        "v1_pins": [{"key": k, "path": v[0], "sha256": v[1]} for k, v in V1.items()],
        "reused": [
            "every v1 requirement record (text, value, units, sources, status, freeze point, A9.2 annotations) carried "
            "into exactly one v2 package; modifications recorded with a v1 snapshot",
            "v1 quantity lines as the starting line-item structure (v1_ref per line item)",
            "v1 acceptance, calibration/traceability, documentation and supplier-must-state lists (tagged carried_from)",
            "v1 reference_data (web-track catalogue records, REFERENCE ONLY) and the R5 facility list (file order)",
            "v1 do-not-purchase banner wording (extended by the A9.3 dispatch statement)",
        ],
        "not_reused": [
            "the nine-family package split (replaced by the six owner families + RFQ2-CIF, A9.3 OQ-RFQ-07)",
            "the four-range Ar quantity '4 (OQ-RFQ-02)' (A9.3 OQ-RFQ-02)",
            "RFQ-04-R15 optional fixed pre-match (superseded by A9.2; SUPERSEDED_NOT_QUOTED)",
            "the pre-A9.2 off-platform match text (kept only in v1 history fields)",
            "v1 open questions OQ-RFQ-02/06/07/10 as open (answered by A9.3); OQ-RFQ-05 (answered by row 111)",
            "the v1 builder code (not imported; v1 is read as data only)",
        ],
        "historical_not_used": [
            "upstream RF/ECR pre-ionizer campaign (A5 Phase-1 topology, phase1_prereg_framework_v1, PMQ-01..05, LOCK-1 "
            "D-01..D-04): historical per A9; nothing reused",
        ],
    }


def build() -> dict:
    verify_pins()
    reqs = carried_requirements() + new_requirements()
    ids = [r["id"] for r in reqs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate requirement ids")
    for r in reqs:
        if r["dispatch"] not in DISPATCH:
            raise ValueError(r["id"])
        if r["freeze_point"] not in FREEZE_POINTS:
            raise ValueError(f"{r['id']} freeze point {r['freeze_point']}")
        if r["status"] not in STATUSES:
            raise ValueError(f"{r['id']} status {r['status']}")
        if r["evidence_class"] is not None and r["evidence_class"] not in EVIDENCE_CLASSES:
            raise ValueError(f"{r['id']} evidence class {r['evidence_class']}")
    items = line_items()
    pkgs = assemble_packages(reqs, items)
    cif = common_interface()
    p1_first = [{"package": p["id"], "line_item": li["id"], "item": li["item"], "qty": li["qty"],
                 "option_line": li["option_line"]} for p in pkgs for li in p["line_items"]
                if li["dispatch"] == "P1_NEEDED"]
    doc = {
        "schema": "rfq_a9_v2",
        "id": "RFQ_A9_V2",
        "title": "A9 RFQ packages v2 - split by supplier speciality (quotations only; no purchase orders)",
        "revision_of": {"id": "RFQ_A9_V1", "lane": "A9-09", "path": "docs/procurement/rfq_a9/",
                        "json": V1["V1_JSON"][0], "json_sha256": V1["V1_JSON"][1],
                        "rule": "v1 is immutable and never edited; v2 is a new revision under a new path"},
        "lane": "A9_RFQV2",
        "follow_on": "fo_a9_rfq_v2_split",
        "trigger": "T_A9_RFQ_V2_SPLIT",
        "status": "DRAFT_FOR_OWNER_DISPATCH_QUOTATION_ONLY",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": TEST,
        "banner": banner_lines(),
        "dispatch_authority": {
            "prepares": "technical team (repository lane)",
            "dispatches": "P9E/Vyovrinda under Praveen's authorization (commercial dispatch authority)",
            "supplier_contact": "none by the repository or Claude; no automatic supplier contact",
            "source": A93("OQ-RFQ-07", "Claude/team shall **not contact suppliers automatically**."),
        },
        "decision_pins": [{"key": k, "path": v[0], "sha256": v[1], "immutable": True} for k, v in DECISIONS.items()],
        "deliverable_pins": [{"key": k, "path": v[0], "sha256": v[1]} for k, v in DELIVERABLES.items()],
        "never_pinned": NEVER_PINNED,
        "pending_parallel_lanes": {"P1": P1_LANE, "P2_prep": P2_LANE,
                                   "rule": "PENDING values are never filled; nothing is read from these paths"},
        "standing_facts": {
            "credible_hall_set": "EMPTY (no admitted Hall closure)",
            "p5_n2_v1": "INCONCLUSIVE (permanent)",
            "no_prediction": "no thrust, efficiency, discharge current, ICP electron current, impedance or plasma state "
                             "is predicted; published analog data are context only",
            "no_winner": "no configuration is declared a winner",
            "a9_2_statuses": load("A92")["decisions"]["a9_10_statuses"],
            "full_system_gates": "25 mN, P_bus < 1.5 kW, < 40 kg wet are full-system gates (A9)",
        },
        "configurations": CONFIGS,
        "outcome_vocabulary": OUTCOMES,
        "status_not_outcome": ["OPEN"],
        "evidence_classes": EVIDENCE_CLASSES,
        "freeze_points": FREEZE_POINTS,
        "requirement_statuses": STATUSES,
        "dispatch_tags": DISPATCH,
        "change_types": CHANGE_TYPES,
        "derived": {
            "stand_ceiling_A": {"value": stand_ceiling_A(), "units": "A", "formula": "1500 W / 180 V (A9.3 OQ-A907-02)",
                                "evidence_class": "owner-stated"},
            "ar_anchor_check": ar_mgps_check(),
        },
        "common_interface": cif,
        "packages": pkgs,
        "p1_dispatch_first": p1_first,
        "not_in_this_revision": NOT_IN_THIS_REVISION,
        "change_log": change_log(reqs, pkgs),
        "traceability_matrix": traceability(reqs),
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(reqs),
        "open_owner_questions": open_owner_questions(),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4_inputs(pkgs),
        "compliance": {
            "lane_paths": ["docs/procurement/rfq_a9_v2/**", "tests/test_rfq_a9_v2.py"],
            "no_purchase_order": True, "no_supplier_contact": True, "no_supplier_ranking": True, "no_prices": True,
            "v1_untouched": "all v1 files pinned by sha256 and verified at every build",
            "pure": "standard library; not wired into archengine; goldens unaffected",
            "never_pass": "RF component ratings TBD_AFTER_IMPEDANCE_MAP; ICP_COUPLED_THERMAL UNRESOLVED; anode OPEN",
        },
    }
    return doc


# ------------------------------------------------------------------------------------------------------- markdown
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
    out = ["| " + " | ".join(c[0] for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(c[1](r)) for c in cols) + " |")
    return out


REQ_COLS = [("id", lambda r: r["id"]), ("v1 id", lambda r: r["v1_id"]), ("title", lambda r: r["title"]),
            ("value", lambda r: r["value"]), ("units", lambda r: r["units"]),
            ("sources", lambda r: "; ".join(sorted({label(s) for s in r["sources"]}))),
            ("evidence", lambda r: r["evidence_class"]), ("status", lambda r: r["status"]),
            ("freeze", lambda r: r["freeze_point"]), ("dispatch", lambda r: r["dispatch"]),
            ("change", lambda r: r["change"]["type"])]
ITEM_COLS = [("id", lambda x: x["id"]), ("item", lambda x: x["item"]), ("qty", lambda x: x["qty"]),
             ("basis", lambda x: x["basis"]), ("dispatch", lambda x: x["dispatch"]),
             ("option", lambda x: "OPTION" if x["option_line"] else ""),
             ("requirements", lambda x: ", ".join(x["requirements"])), ("v1", lambda x: x["v1_ref"]),
             ("change", lambda x: x["change"]["type"])]


def render_package(p: dict) -> str:
    L_ = [f"# {p['id']} - {p['owner_family']}", "", "> **" + p["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in p["banner"][1:]]
    L_ += ["", f"Generated by `{THIS_SCRIPT}` from `{OUT_JSON}`; do not edit by hand. Revision of the immutable v1 "
               f"packages (`docs/procurement/rfq_a9/`, v1 families folded in: {', '.join(p['v1_packages_folded_in'])}).",
           "", "## Owner minimum scope (A9.3 OQ-RFQ-07, verbatim) and coverage", ""]
    L_ += _table([{"k": k, "v": v} for k, v in p["owner_minimum_scope_coverage"].items()],
                 [("owner item", lambda x: x["k"]), ("line items", lambda x: ", ".join(x["v"]))])
    L_ += ["", "## Line items (P1_NEEDED lines can be dispatched first)", ""]
    L_ += _table(p["line_items"], ITEM_COLS)
    L_ += ["", "## Requirements (a)", ""]
    L_ += _table(p["requirements"], REQ_COLS)
    L_ += ["", "### Requirement text", ""]
    for r in p["requirements"]:
        extra = " (NOT QUOTED)" if r.get("quote_requested") is False else ""
        L_.append(f"- **{r['id']}** ({r['v1_id'] or 'new'}; {r['dispatch']}){extra}: {r['requirement']}")
        if r.get("note"):
            L_.append(f"  - note: {r['note']}")
        L_.append(f"  - change ({r['change']['type']}): {r['change']['why']}")
    if p.get("not_in_this_revision"):
        L_ += ["", "## Not in this revision", ""]
        for x in p["not_in_this_revision"]:
            L_.append(f"- **{x['id']}** {x['item']} - {x['why']}")
    for fld, head in (("acceptance", "Acceptance"), ("calibration_traceability", "Calibration and traceability"),
                      ("documentation", "Deliverable documentation"), ("supplier_must_state", "Supplier must state")):
        L_ += ["", f"## {head}", ""]
        for x in p[fld]:
            L_.append(f"- {x['text']}" + (f" _({x['carried_from']})_" if x["carried_from"] else " _(v2)_"))
    L_ += ["", "## Common-interface ids touched", "", ", ".join(p["cif_interfaces"]) or "-"]
    if p["reference_data"]:
        L_ += ["", "## Reference data (" + p["reference_data_use"] + ")", ""]
        for x in p["reference_data"]:
            d = x.get("datum", {})
            L_.append(f"- {d.get('quantity', '-')}: {d.get('value', '-')} - {x.get('citation', '-')} "
                      f"({x.get('access', '-')}; {x['carried_from']})")
    if p.get("facilities_recorded_R5"):
        L_ += ["", "## Facilities recorded by the web track (" + p["facilities_note"] + ")", ""]
        for e in p["facilities_recorded_R5"]["entries"]:
            L_.append(f"- {e['name']} ({e['country']})")
    L_ += ["", "## Open specification items", ""]
    L_ += _table(p["open_specification_items"], [("id", lambda x: x["id"]), ("v1", lambda x: x["v1_id"]),
                                                 ("title", lambda x: x["title"]), ("value", lambda x: x["value"]),
                                                 ("freeze", lambda x: x["freeze_point"]),
                                                 ("dispatch", lambda x: x["dispatch"])])
    return "\n".join(L_) + "\n"


def render_cif(c: dict) -> str:
    L_ = [f"# {c['id']} - {c['title']}", "", "> **" + c["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in c["banner"][1:]]
    L_ += ["", c["purpose"], "", f"Owner basis (A9.3 OQ-RFQ-07): \"{c['source_quote']['quote']}\"", "",
           "## Shared items", ""]
    L_ += _table(c["items"], [("id", lambda x: x["id"]), ("group", lambda x: x["group"]),
                              ("title", lambda x: x["title"]), ("value", lambda x: x["value"]),
                              ("status", lambda x: x["status"]), ("freeze", lambda x: x["freeze_point"]),
                              ("source", lambda x: x["source"])])
    L_ += ["", "## Cross-package interface matrix", ""]
    L_ += _table(c["interface_matrix"], [("id", lambda x: x["id"]), ("between", lambda x: " <-> ".join(x["between"])),
                                         ("what", lambda x: x["what"]), ("reference", lambda x: x["reference"]),
                                         ("units", lambda x: x["units"]), ("status", lambda x: x["status"]),
                                         ("source", lambda x: x["source"]), ("dispatch", lambda x: x["dispatch"])])
    return "\n".join(L_) + "\n"


def render_main(d: dict) -> str:
    L_ = [f"# {d['title']}", "", "> **" + d["banner"][0] + "**", ">"]
    L_ += ["> " + b for b in d["banner"][1:]]
    L_ += ["", f"Lane {d['lane']} ({d['follow_on']}, trigger {d['trigger']}); status {d['status']}; A9 status "
               f"{d['a9_status']}; base commit `{d['base_commit']}`. Generated by `{d['generated_by']}` "
               f"(`--check` reproduces it); test `{d['test']}`.", "",
           f"Revision of the immutable v1 packages `{d['revision_of']['path']}` (json sha256 "
           f"`{d['revision_of']['json_sha256']}`); v1 is never edited.", "",
           "## Packages", ""]
    L_ += _table(d["packages"], [("package", lambda p: p["id"]), ("owner family", lambda p: p["owner_family"]),
                                 ("file", lambda p: p["package_file"]),
                                 ("v1 folded in", lambda p: ", ".join(p["v1_packages_folded_in"])),
                                 ("P1 lines", lambda p: len(p["p1_needed_line_items"])),
                                 ("LATER lines", lambda p: len(p["later_line_items"])),
                                 ("requirements", lambda p: len(p["requirements"]))])
    L_ += ["", f"Common interface document: `{d['common_interface']['package_file']}`.", "",
           "## P1 dispatch-first list", ""]
    L_ += _table(d["p1_dispatch_first"], [("package", lambda x: x["package"]), ("line", lambda x: x["line_item"]),
                                          ("item", lambda x: x["item"]), ("qty", lambda x: x["qty"]),
                                          ("option", lambda x: "OPTION" if x["option_line"] else "")])
    L_ += ["", "## Not in this revision", ""]
    for x in d["not_in_this_revision"]:
        L_.append(f"- **{x['id']}** {x['item']} - {x['why']}")
    L_ += ["", "## Derived values", ""]
    for k, v in d["derived"].items():
        L_.append(f"- {k}: {_fmt(v)}")
    L_ += ["", "## v1 -> v2 change log", ""]
    L_ += _table(d["change_log"]["package_level"], [("id", lambda x: x["id"]), ("change", lambda x: x["change"]),
                                                    ("source", lambda x: x["source"])])
    L_ += ["", "Counts: " + _fmt(d["change_log"]["counts"]), ""]
    L_ += _table(d["change_log"]["per_requirement"], [("v2", lambda x: x["v2_id"]), ("v1", lambda x: x["v1_id"]),
                                                      ("from", lambda x: x["v1_package"]),
                                                      ("to", lambda x: x["v2_package"]),
                                                      ("change", lambda x: x["change"]), ("why", lambda x: x["why"]),
                                                      ("dispatch", lambda x: x["dispatch"])])
    L_ += ["", "## (a) Traceability matrix (requirement -> source)", ""]
    L_ += _table(d["traceability_matrix"], [("requirement", lambda x: x["requirement"]),
                                            ("v1", lambda x: x["v1_id"]), ("package", lambda x: x["package"]),
                                            ("sources", lambda x: "; ".join(x["sources"])),
                                            ("status", lambda x: x["status"]), ("freeze", lambda x: x["freeze_point"]),
                                            ("dispatch", lambda x: x["dispatch"])])
    L_ += ["", "## (b) Interface demands", ""]
    L_ += _table(d["interface_demands"], [("id", lambda x: x["id"]), ("from", lambda x: x["from"]),
                                          ("to", lambda x: x["to"]), ("quantity", lambda x: x["quantity"]),
                                          ("units", lambda x: x["units"]), ("status", lambda x: x["status"])])
    oa = d["owner_answers_applied"]
    L_ += ["", "## (c) Owner answers applied", "", "### A9.3", ""]
    L_ += _table(oa["a9_3"], [("id", lambda x: x["id"]), ("status", lambda x: x["status"]),
                              ("how applied", lambda x: x["how_applied"])])
    L_ += ["", "### A9.2", ""]
    L_ += _table(oa["a9_2"], [("id", lambda x: x["id"]), ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "### A9.1", ""]
    L_ += _table(oa["a9_1"], [("id", lambda x: x["id"]), ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "### Owner rows (147 answers)", ""]
    L_ += _table(oa["owner_rows"], [("row", lambda x: x["row"]), ("covers", lambda x: ", ".join(x["covers_ids"])),
                                    ("how applied", lambda x: x["how_applied"])])
    oq = d["open_owner_questions"]
    L_ += ["", "## (d) Open owner questions (new)", ""]
    L_ += _table(oq["new"], [("id", lambda x: x["id"]), ("question", lambda x: x["question"]),
                             ("proposed", lambda x: x["proposed_answer"]), ("needed by", lambda x: x["needed_by"])])
    L_ += ["", "Carried OPEN from v1 (not answered here): " + ", ".join(x["id"] for x in oq["carried_open_from_v1"]),
           "", "Answered since v1: " + ", ".join(f"{x['id']} ({x['state_v3_status']})"
                                                for x in oq["v1_questions_answered_since"]),
           "", "## (e) Historical reuse", ""]
    L_ += _table(d["historical_reuse"]["v1_pins"], [("key", lambda x: x["key"]), ("path", lambda x: x["path"]),
                                                    ("sha256", lambda x: x["sha256"])])
    L_ += ["", "Reused:"] + ["- " + x for x in d["historical_reuse"]["reused"]]
    L_ += ["", "Not reused:"] + ["- " + x for x in d["historical_reuse"]["not_reused"]]
    L_ += ["", "Historical, not used:"] + ["- " + x for x in d["historical_reuse"]["historical_not_used"]]
    L_ += ["", "## (f) M16 v3 impact (proposal only)", ""]
    L_ += _table(d["m16_impact"], [("row", lambda x: x["m16_row"]), ("key", lambda x: x["key"]),
                                   ("packages", lambda x: x["packages"]), ("how", lambda x: x["how_touched"]),
                                   ("proposed status", lambda x: x["proposed_procurement_status"])])
    h = d["h3_h4_inputs"]
    L_ += ["", "## (g) H3 / H4 inputs", "", f"H3 gate: {h['h3_procurement_gate']['state']}; "
                                            f"{h['h3_procurement_gate']['purchase_gate']}.", ""]
    L_ += _table(h["h3_procurement_gate"]["packages"], [("package", lambda x: x["id"]),
                                                        ("P1 lines", lambda x: ", ".join(x["p1_needed_line_items"])),
                                                        ("open items blocking PO",
                                                         lambda x: ", ".join(x["open_items_blocking_po"]))])
    L_ += [""]
    L_ += _table(h["h4_tests"], [("id", lambda x: x["id"]), ("test", lambda x: x["test"]),
                                 ("source", lambda x: x["source"])])
    L_ += ["", "## Pins", ""]
    L_ += _table(d["decision_pins"] + d["deliverable_pins"], [("key", lambda x: x["key"]),
                                                              ("path", lambda x: x["path"]),
                                                              ("sha256", lambda x: x["sha256"])])
    L_ += ["", "Never pinned (mutable governance): " + "; ".join(d["never_pinned"])]
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
