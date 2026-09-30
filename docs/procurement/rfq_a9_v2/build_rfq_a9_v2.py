#!/usr/bin/env python3
"""Deterministic builder of the A9 RFQ packages v2 (fo_a9_rfq_v2_split, trigger T_A9_RFQ_V2_SPLIT; owner A9.4
incorporated mechanically by fo_a9_4_incorporation, trigger T_A9_4_INCORPORATION; completed for sending by
fo_a9_6_rfq_completion under the owner A9.6 implementation-first directive, sec. 13).

A REVISION of the immutable v1 packages docs/procurement/rfq_a9/ (A9-09). v1 is never edited: every v1 file is pinned by
sha256 below and read as data. v2 splits the quotation specification by supplier speciality into exactly the six owner
families of A9.3 OQ-RFQ-07 plus ONE common top-level interface document, and applies A9.2 and A9.3.

Writes
  docs/procurement/rfq_a9_v2/rfq_a9_v2.json                          machine-readable packages, change log, traceability
  docs/procurement/rfq_a9_v2/RFQ_A9_V2.md                            companion document (rendered from the JSON data)
  docs/procurement/rfq_a9_v2/packages/RFQ2-00_common_interface.md    common top-level interface document
  docs/procurement/rfq_a9_v2/packages/RFQ2-0N_<slug>.md              one sendable package per supplier speciality

Authority (all pinned by sha256; the build refuses to run if any pinned file changed)
  A9, the 147 owner answers (+ verbatim pack), A9.1 .. A9.6 (+ verbatim .md files), A4-A7; cited by row / decision id.
  Owner quotes are checked verbatim against the decision text at build time.
  The MERGED P1 bench and P2 prep packages are read (ids, statuses, P2 instrument specifications) but not pinned: the
  A9.5 / A9.6 lanes refine them concurrently, and the instrument-coverage cross-check raises on any id drift.

Rules implemented here
  * every v1 requirement is carried exactly once into one v2 package with a per-line change record (what changed, why);
  * new lines cite an owner row / A9.1 / A9.2 / A9.3 id or a verified deliverable item located by id at build time;
  * P1 / P2 values are referenced by their merged ids (e.g. P1-M-26, F2, INS-P2-04) and stay TBD with freeze gate P1-G0
    (or the P2 gate) until registered there; nothing is filled here. The A9.6 parallel lanes not in this base (P3, P4,
    mass/power v2, Xe accounting v2) are written 'PENDING <path>' and nothing is read from them;
  * A9.6 sec. 13: every owner item maps to lines; every P1_NEEDED line carries a quote sheet (specification rows with
    value / TBD and freeze gate, acceptance, calibration / traceability, documentation); every merged P1 measurement,
    P1 hardware item and P2 instrument maps to an RFQ line or an explicit not-procured disposition (fail-closed);
  * genuinely open owner questions stay TBD_OWNER with their admissible alternatives side by side;
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
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LANE_DIR = "docs/procurement/rfq_a9_v2"
OUT_JSON = LANE_DIR + "/rfq_a9_v2.json"
OUT_MD = LANE_DIR + "/RFQ_A9_V2.md"
PKG_DIR = LANE_DIR + "/packages"
THIS_SCRIPT = LANE_DIR + "/build_rfq_a9_v2.py"
TEST = "tests/test_rfq_a9_v2.py"
BASE_COMMIT = "ee9dc7db7d11e0b5f1d8b514258778ac1b6030d3"
A94_INC_BASE = "875ed6d0a87202bc92706b28551b0e22eda2014d"   # base of the A9.4 incorporation (fo_a9_4_incorporation)

A96_BASE = "c33b22c78b14cd4d6a51ed9bd5de4e046bc98cae"   # base of the A9.6 RFQ completion (fo_a9_6_rfq_completion)

# Merged, verified P1 / P2 packages. They are READ (ids, statuses, P2 instrument specifications) but NOT pinned: the A9.5 /
# A9.6 P1 and P2 lanes refine them concurrently; any id added, removed or renamed there makes this build raise (coverage
# cross-check), and the consolidated integration pass reconciles both sides.
P1_JSON = "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json"
P2_JSON = "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json"
CURRENT = {"P1": P1_JSON, "P2": P2_JSON}

# Parallel lanes of A9.6 not in this base: referenced as 'PENDING <path>' only; nothing is read from them.
PARALLEL_LANES = {
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/",
    "MASS_POWER": "docs/budgets/mass_power_a9_v2/",
    "XE_ACCOUNTING": "docs/budgets/xe_accounting_a9_v2/",
}

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
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d"),
    "A94_MD": ("docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md",
               "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c"),
    "A95": ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
            "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3"),
    "A95_MD": ("docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md",
               "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327"),
    "A96_MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
               "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634"),
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
    "REG": ("docs/procurement/web_track_v1/source_register_v1.json",
            "e2661a49892b58271f25405ecbcc7d37cc22ba9a85d29fec83a0f72bdc10c77d"),
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


def A94(did: str, quote: str) -> dict:
    """A9.4 owner decision (decisions or execution_decisions) with a quote that must occur verbatim in the A9.4
    verbatim record."""
    doc = load("A94")
    if did in doc["decisions"]:
        ptr = "/decisions/" + did
    elif did in doc["execution_decisions"]:
        ptr = "/execution_decisions/" + did
    else:
        raise KeyError(f"A9.4 decision {did} not found")
    if quote not in load("A94_MD"):
        raise ValueError(f"quote not verbatim in the A9.4 record: {quote!r}")
    return {"type": "a9_4", "key": "A9.4", "id": did, "quote": quote, "path": DECISIONS["A94_MD"][0],
            "pointer": ptr, "json_path": DECISIONS["A94"][0], "sha256": DECISIONS["A94_MD"][1]}


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
    out = {"type": "deliverable_item", "key": key, "path": DELIVERABLES[key][0], "id": did, "pointer": ptr,
           "sha256": DELIVERABLES[key][1]}
    loc = _resolve(load(key), ptr).get("locator")
    if loc:
        out["locator"] = loc
    return out


def V1R(rid: str) -> dict:
    for i, p in enumerate(load("V1_JSON")["packages"]):
        for j, r in enumerate(p["requirements"]):
            if r["id"] == rid:
                return {"type": "v1_requirement", "id": rid, "path": V1["V1_JSON"][0],
                        "pointer": f"/packages/{i}/requirements/{j}", "sha256": V1["V1_JSON"][1]}
    raise KeyError(rid)


def PEND(path: str, what: str) -> dict:
    if path not in PARALLEL_LANES.values():
        raise ValueError(f"PENDING reference to a path that is not a registered parallel lane: {path}")
    return {"type": "pending_lane", "path": path, "what": what,
            "note": "parallel lane not in this base; nothing is read from it"}


def A95(did: str, quote: str) -> dict:
    """A9.5 owner decision with a quote that must occur verbatim in the A9.5 verbatim record."""
    if did not in load("A95")["decisions"]:
        raise KeyError(f"A9.5 decision {did} not found")
    if quote not in load("A95_MD"):
        raise ValueError(f"quote not verbatim in the A9.5 record: {quote!r}")
    return {"type": "a9_5", "key": "A9.5", "id": did, "quote": quote, "path": DECISIONS["A95_MD"][0],
            "pointer": "/decisions/" + did, "json_path": DECISIONS["A95"][0], "sha256": DECISIONS["A95_MD"][1]}


def A96(section: str, quote: str) -> dict:
    """A9.6 owner directive section with a quote that must occur verbatim in the A9.6 verbatim record."""
    md = load("A96_MD")
    if quote not in md:
        raise ValueError(f"quote not verbatim in the A9.6 record: {quote!r}")
    return {"type": "a9_6", "key": "A9.6", "id": section, "quote": quote, "path": DECISIONS["A96_MD"][0],
            "json_path": DECISIONS["A96"][0], "sha256": DECISIONS["A96_MD"][1]}


def current(key: str):
    """Merged P1 / P2 package (read, not pinned; see CURRENT)."""
    ck = "CUR:" + key
    if ck not in _CACHE:
        rel = CURRENT[key]
        if not os.path.isfile(_abs(rel)):
            raise FileNotFoundError(f"merged {key} package missing: {rel}")
        with open(_abs(rel), encoding="utf-8") as fh:
            _CACHE[ck] = json.load(fh)
    return _CACHE[ck]


def _find_all_ids(doc, target: str, ptr: str = "", out=None) -> list:
    out = [] if out is None else out
    if isinstance(doc, dict):
        if doc.get("id") == target:
            out.append(ptr)
        for k, v in doc.items():
            _find_all_ids(v, target, ptr + "/" + str(k).replace("~", "~0").replace("/", "~1"), out)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            _find_all_ids(v, target, ptr + "/" + str(i), out)
    return out


CUR_SCOPES = [  # (package key, id prefix regex, JSON pointer of the list the id is looked up in)
    ("P1", r"^P1-M-\d+$", "/measurements"), ("P1", r"^P1-HW-\d+$", "/hardware_readiness"),
    ("P1", r"^P1-IT-\d+$", "/items"), ("P1", r"^F\d+$", "/run_matrix/factors"),
    ("P2", r"^INS-P2-\d+$", "/instrument_list"),
]


def CUR(key: str, iid: str) -> dict:
    """Item of the merged P1 / P2 package located by a UNIQUE id inside its registered list (CUR_SCOPES); raises if
    absent or ambiguous."""
    scope = [ptr for k, rx, ptr in CUR_SCOPES if k == key and re.match(rx, iid)]
    if len(scope) != 1:
        raise KeyError(f"no registered lookup scope for {key}:{iid}")
    ptrs = [scope[0] + p_ for p_ in _find_all_ids(_resolve(current(key), scope[0]), iid)]
    if len(ptrs) != 1:
        raise KeyError(f"{iid} found {len(ptrs)} times in {CURRENT[key]} (need exactly one)")
    item = _resolve(current(key), ptrs[0])
    return {"type": "current_deliverable", "key": key, "path": CURRENT[key], "id": iid, "pointer": ptrs[0],
            "item_status": item.get("status"), "pinned": False,
            "note": "merged package read at build time; refined concurrently by the A9.5 / A9.6 lanes"}


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
    if t == "a9_4":
        return f"A9.4 {s['id']}"
    if t == "a9_3_record":
        return f"A9.3 record {s['pointer']}"
    if t == "deliverable_item":
        return f"{s['key']}:{s['id']}" + (f" ({s['locator']})" if s.get("locator") else "")
    if t == "deliverable":
        return s.get("key", s.get("path", "deliverable"))
    if t == "v1_requirement":
        return f"v1 {s['id']}"
    if t == "pending_lane":
        return f"PENDING {s['path']}"
    if t == "a9_5":
        return f"A9.5 {s['id']}"
    if t == "a9_6":
        return f"A9.6 {s['id']}"
    if t == "current_deliverable":
        return f"{s['key']}:{s['id']}"
    raise ValueError(t)


# ------------------------------------------------------------------------------------------------------ vocabulary
CONFIGS = ["hall_c1_reference", "hall_icp_neutralizer"]
OUTCOMES = ["hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE"]
EVIDENCE_CLASSES = ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "owner-stated"]
FREEZE_POINTS = ["NOW", "P1-G0", "LOCK-1", "LOCK-2", "after-evidence"]   # P1-G0: P1 bench registration gate
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
        "A9.4 (owner, 2026-09-30, execution_decisions.p1_needed_rfqs): the owner / procurement may SEND the lines tagged "
        "P1_NEEDED to suppliers for quotation - requests for quotation, technical clarification, indicative lead time, "
        "commercial quotation, datasheets/certificates. NOT authorized: purchase orders, advance payments, binding "
        "commitments. Claude / the technical team still never contacts suppliers.",
        "A9.6 (owner, 2026-09-30, sec. 13): RFQ only - no purchase order authorization. Packages completed so that the "
        "P1_NEEDED lines are ready to send; the owner / procurement sends them; Claude never contacts suppliers.",
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
        "TBD - requires the generator's mains input interface (supplier data) and the P1 uncertainty target of P1-M-05 "
        "(frozen at P1-G0)", "W", "A9.3 OQ-RFQ-06",
        [A93("OQ-RFQ-06", "Measure the laboratory source with a proper input power analyzer and record:"),
         A93("OQ-RFQ-06", "as evidence that the flight propulsion system satisfies:"),
         CUR("P1", "P1-M-05"), CUR("P1", "P1-HW-08"), CUR("P2", "INS-P2-11")],
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
        "TBD - requires the P1 bench layout (P1-HW-04; cable run set at P1-G0) and the impedance map (ratings "
        + TBD_RF + ")", "m; W; V", "A9.2 OQ-A907-11 / rf_measurement_reference",
        [A92Q("OQ-A907-11", "The local matching network shall be positioned on, or immediately adjacent to, the ICP "
                            "module"),
         A92("rf_measurement_reference"), CUR("P1", "P1-HW-04")],
        None, "TBD", "P1-G0", "P1_NEEDED",
        change_why="new P1 line: v1 quoted only the live/sham flexible pair for the thrust-stand crossing (LATER)"))
    out.append(R(
        "RFQ2-RF-N06", "RFQ2-RF", "compatibility with the P2 impedance-map instrument preparation",
        "Supplier states whether the coupler/sensor chain and the local match support calibrated complex reflection "
        "measurement (|Gamma| and phase, VSWR) and V/I sensing at the 50-ohm reference plane, and the calibration / "
        "de-embedding data it can supply; P2 instrument preparation uses the same RF hardware.",
        "supplier statement against the merged P2 preparation method (P2 instrument list INS-P2-01..12, "
        "calibration plan, Z_antenna methods); the P2 instrument specifications are quoted in RFQ2-RF-N07..N16", "-",
        "A9.3 authorizations P2; A9.2 rf_measurement_reference; P2 prep package",
        [A93J("/authorizations/P2"), A92("rf_measurement_reference"),
         CUR("P2", "INS-P2-01"), CUR("P2", "INS-P2-02"), CUR("P2", "INS-P2-03"), CUR("P2", "INS-P2-12")],
        None, "COPIED_VERIFIED", "NOW", "P1_NEEDED",
        change_why="new: A9.3 authorizes P2 preparation on the same RF hardware"))
    # ---------------------------------------------------------------- GAS
    out.append(R(
        "RFQ2-GAS-N01", "RFQ2-GAS", "Ar P1 engineering window (Takahashi-anchor neighbourhood)",
        "Calibrated Ar flow that reproduces the neighbourhood of the owner-stated Takahashi anchor 70 sccm "
        "(~2.1 mg/s) and sweeps sufficiently above and below it to establish ignition/current trends, with useful flow "
        "uncertainty inside that window. The sweep bounds are set by the P1 bench plan. Ar data are "
        "ENGINEERING_ONLY_NON_SCORING regardless of metrology quality.",
        {"anchor_sccm": 70.0, "anchor_mgps_owner_stated": 2.1, "anchor_mgps_recorder_check": ar["value_mgps"],
         "sweep_bounds": "TBD - levels above and below the anchor frozen at P1-G0 from the MFC range and refined from "
                         "the P1-S3 ignition map (P1 run_matrix F2)"},
        "sccm (Ar); mg/s", "A9.3 OQ-RFQ-02; published analog anchor EVI TK-31 (Takahashi 2024 p. 3 text)",
        [A93("OQ-RFQ-02", "reproduce the neighborhood of the Takahashi anchor:"),
         A93("OQ-RFQ-02", "sweep sufficiently above/below that point to establish ignition/current trends;"),
         DI("EVI", "TK-31"), CUR("P1", "F2"), CUR("P1", "P1-IT-09"), CUR("P1", "P1-IT-10")],
        "owner-stated", "TBD", "P1-G0", "P1_NEEDED",
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
        {"qualification_V_DC": 1000.0, "count": "TBD - requires the P1 gas schematic and potential map (P1-HW-12, "
                                                 "P1-IT-20; registered at P1-G0)"}, "V (DC); units",
        "A9.3 ICPQ-06; row 105 practice",
        [A93("ICPQ-06", "Any ICP gas line crossing a meaningful potential difference shall receive the same "
                        "representative-pressure/gas isolation philosophy already adopted for the Hall gas isolator."),
         A93("ICPQ-06", "The requirement applies when the gas plumbing creates an electrical bridge across isolated "
                        "potentials."),
         OW(105, "perform ~1 kV DC representative-pressure/gas withstand qualification"),
         CUR("P1", "P1-HW-12"), CUR("P1", "P1-IT-20")],
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
        "TBD - requires the P1 gauge ranges (P1-M-16, P1-M-17; frozen at P1-G0) and facility identification (row 139)",
        "Pa",
        "A9.3 OQ-RFQ-07 gas/metrology family; ICD ICP-34; H2-6 H26-25, H26-30; INS-06, INS-08",
        [A93("OQ-RFQ-07", "pressure instrumentation"), DI("ICD", "ICP-34"), DI("H26", "H26-25"), DI("H26", "H26-30"),
         DI("INS", "INS-06"), DI("INS", "INS-08"),
         A91("UBQ-08", "Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation."),
         CUR("P1", "P1-M-16"), CUR("P1", "P1-M-17"), CUR("P1", "P1-HW-11")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner gas/metrology family names pressure instrumentation (v1 had only a pressure port)"))
    out.append(R(
        "RFQ2-GAS-N07", "RFQ2-GAS", "P1 Ar feed valves",
        "Shut-off/isolation valves of the P1 Ar feed (bottle -> regulator -> MFC -> H-1 anode feed); type and count per "
        "the P1 gas schematic. The two-series-valve rule of row 90 applies to the high-pressure Xe/cathode branch "
        "(carried RFQ-07-R05, LATER).",
        "TBD - requires the P1 gas schematic (Ar feed to the H-1 gas path, P1-HW-15; registered at P1-G0)", "units",
        "A9.3 OQ-RFQ-07 gas/metrology family",
        [A93("OQ-RFQ-07", "valves"), CUR("P1", "P1-HW-15")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
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
        "TBD - requires facility identification (row 139) and the P1 pumping need for the Ar anchor flow (P1-HW-17)",
        "Pa; L/s", "A9.3 OQ-RFQ-07 vacuum/facility family; row 139; row 23",
        [A93("OQ-RFQ-07", "pumping"), OW(139, "use a smaller domestic chamber for engineering-only S1a"),
         OW(23, "use two elevated background-pressure levels for facility-effect characterization"),
         DI("EVI", "TK-34"), CUR("P1", "P1-HW-17")],
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
        "TBD - requires the P1 gas schematic (P1-HW-18; registered at P1-G0)", "units",
        "A9.3 OQ-RFQ-07 vacuum/facility family",
        [A93("OQ-RFQ-07", "feedthroughs"), OW(107, "ADOPT ASTM G93 Level C cleaning for O2 service"),
         CUR("P1", "P1-HW-18")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
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
        "TBD - requires the MC-1 coil design currents and resistances (H2-1) and the P1 magnet states (P1 run_matrix "
        "F6, PROPOSED {OFF, registered H-1 setting(s)}, P1Q-06)", "A; V", "row 110; H2-4 H24-32, H3-PPU-02",
        [OW(110, "per-coil magnet"), DI("H24", "H24-32"), DI("H24", "H3-PPU-02"), CUR("P1", "F6"),
         CUR("P1", "P1-M-24"), CUR("P1", "P1-HW-25"),
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
        {"current_range_A_min": ic, "bandwidth": "TBD - frozen at P1-G0 (P1-M-14 time-resolved channel; P1-M-26)"},
        "A; V; Hz",
        "A9.3 OQ-VI-05; A9.3 OQ-A907-02",
        [A93("OQ-VI-05", "and collector/reference potentials."),
         A93("OQ-VI-05", "classify it as an engineering topology-control test, not a hard architecture PASS/FAIL gate."),
         A93("OQ-A907-02", "current sensor range;"), CUR("P1", "P1-M-14"), CUR("P1", "P1-M-26")],
        "owner-stated", "TBD", "P1-G0", "P1_NEEDED",
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
        "and flow channels, and the optical-emission photodiode channel (RFQ2-THRUST-N03, A9.4 P2Q-05); current "
        "channels ranged to the 8.33 A stand ceiling. Channel count, sample rate and bandwidth follow the P1 plan.",
        {"channels_min": "OQ-VI-05 list + ICP-34 list", "current_range_A_min": ic,
         "sample_rate": "TBD - frozen at P1-G0 (P1-M-26: PROPOSED continuous logging on the common time base INS-18)"},
        "-; A; Sa/s",
        "A9.3 OQ-VI-05, OQ-RFQ-07, OQ-A907-02; ICD ICP-34; INS-18",
        [A93("OQ-VI-05", "Record:"), A93("OQ-RFQ-07", "DAQ"), A93("OQ-A907-02", "DAQ range;"), DI("ICD", "ICP-34"),
         DI("INS", "INS-18"), CUR("P1", "P1-M-26"), CUR("P1", "P1-HW-39"),
         A94("P2Q-05", "Add the photodiode, appropriate optical access/window, amplifier and DAQ channel to the "
                       "P1_NEEDED/P2 preparation instrumentation quote.")],
        "owner-stated", "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner thrust/metrology family names DAQ; v1 had only the P_bus chain (RFQ-06, LATER)"))
    out.append(R(
        "RFQ2-THRUST-N02", "RFQ2-THRUST", "traceability hardware",
        "Calibration references and certificates for the DAQ V/I/T channels, RF power sensors and power analyzer, "
        "with the uncertainty budget and coverage factor stated; ISO/IEC 17025 / NABL scope where the measurand is "
        "score-bearing (RFQ-09-R01 carried).",
        "TBD - requires the channel list (RFQ2-THRUST-N01); certificate rule per P1 measurement: MS-G-01..03 (accredited "
        "scope, SI-traceable chain, GUM uncertainty; P1 measurements metrology_spec)",
        "-", "A9.3 OQ-RFQ-07 thrust/metrology family; row 126",
        [A93("OQ-RFQ-07", "traceability hardware"),
         OW(126, "NABL/ISO-17025 calibration is the primary score-bearing reference."),
         CUR("P1", "P1-HW-41"), CUR("P1", "P1-M-01")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new line: owner thrust/metrology family names traceability hardware"))
    # ---------------------------------------------------------------- A9.4 (fo_a9_4_incorporation)
    pd_quote = ("Add the photodiode, appropriate optical access/window, amplifier and DAQ channel to the P1_NEEDED/P2 "
                "preparation instrumentation quote.")
    out.append(R(
        "RFQ2-THRUST-N03", "RFQ2-THRUST", "optical-emission photodiode + amplifier + DAQ channel (A9.4 P2Q-05)",
        "Quote an optical-emission photodiode with its amplifier and one DAQ channel on the common time base (INS-18), "
        "viewing the ICP source volume through the optical access / window of RFQ2-VAC-N06. It is the REQUIRED "
        "independent plasma ignition / unlit and E-mode / H-mode transition indicator (INS-P2-10), physically "
        "independent of the RF impedance measurement chain; it is logged simultaneously with reflected RF power, antenna "
        "current, collector / current-path response and pressure. Supplier states spectral response, dark current / "
        "noise, linear range and saturation (over-range) level and its indication, amplifier gain settings and "
        "bandwidth. No photodiode threshold is requested or set: the threshold is established from dark / background, "
        "RF-powered known-unlit and known-lit P1 plasma measurements and frozen before the P2 map.",
        {"item": "photodiode + amplifier + 1 DAQ channel (REQUIRED, A9.4 P2Q-05)",
         "spectral_band": "TBD - requires the module optical access and the P1 emission records",
         "gain_bandwidth_saturation": "TBD - requires the P1 dark / unlit / lit emission levels",
         "threshold": "none requested (frozen from P1 records before the P2 map)"},
        "-; V/A; Hz", "A9.4 P2Q-05",
        [A94("P2Q-05", pd_quote),
         A94("P2Q-05", "The photodiode is the required independent optical indicator, while RF/electrical signals "
                       "provide corroboration."),
         A94("P2Q-05", "Do not assign an arbitrary photodiode voltage threshold now."),
         A93("OQ-RFQ-07", "DAQ"), DI("INS", "INS-18"), CUR("P2", "INS-P2-10"), CUR("P1", "P1-M-28")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED",
        note="placed in the thrust/metrology package (owner family 'DAQ'): it is an optical, non-RF diagnostic channel "
             "on the P1 DAQ and must stay independent of the RF impedance chain, so it is not quoted in RFQ2-RF",
        change_why="new line: A9.4 P2Q-05 procurement (photodiode, amplifier, DAQ channel)"))
    out.append(R(
        "RFQ2-VAC-N06", "RFQ2-VAC", "optical access / window for the photodiode (A9.4 P2Q-05)",
        "Chamber viewport (or in-vacuum window) with a line of sight to the ICP source volume for the photodiode of "
        "RFQ2-THRUST-N03; transmission band matched to the photodiode response; the line of sight is preserved by the "
        "module envelope (ICD ICP-07); supplier states the transmission band, flange family (CIF-C02) and the "
        "protection / replacement provision against window coating. Loss of line of sight makes a photodiode record "
        "invalid as unlit evidence (P2 reducer), so the view must be verifiable.",
        "TBD - requires the facility port layout (row 139), the module envelope (ICD ICP-07) and the photodiode "
        "selection (RFQ2-THRUST-N03)", "-; nm; mm", "A9.4 P2Q-05; A9.3 OQ-RFQ-07 vacuum/facility family",
        [A94("P2Q-05", pd_quote), A94("P2Q-05", "Likewise, if the photodiode loses line-of-sight or saturates, the record "
                                                "is not automatically valid."),
         A93("OQ-RFQ-07", "RGA/diagnostic interfaces"), DI("ICD", "ICP-07")],
        None, "OWNER_GIVEN", "NOW", "P1_NEEDED",
        note="item OWNER_GIVEN (A9.4); dimensions / band TBD",
        change_why="new line: A9.4 P2Q-05 procurement (optical access / window)"))
    dwv_sources = [
        A94("P1Q-14", "Extend the existing:"),
        A94("P1Q-14", "corresponding to a 1.5× design margin."),
        A94("P1Q-14", "This is a minimum design basis, not the qualification-test voltage."),
        A94("P1Q-14", "1.05~kV~DC"), A94("P1Q-14", "60~s"),
        A94("P1Q-14", "where component ratings permit."),
        A94("P1Q-14", "This decision does not close ICP-44."),
    ]
    out.append(R(
        "RFQ2-HALLEL-N04", "RFQ2-HALLEL", "ICP body / collector isolation: 350 V class, >= 525 V design withstand, "
        "1.05 kV / 60 s initial DWV (A9.4 P1Q-14)",
        "Isolation of the ICP body / collector circuits relative to the Hall anode, the H-1 body/common, facility ground "
        "and other isolated circuits (where those potential differences can physically occur) is designed to the 350 V "
        "operating class with V_design,withstand >= 525 V (1.5 x; a minimum design basis, not the test voltage). Passive "
        "insulation paths and feedthrough assemblies are qualified at 1.05 kV DC for 60 s where component ratings "
        "permit (current-limited, sensitive electronics disconnected where necessary, leakage recorded, in the relevant "
        "insulation configuration, before first HV/RF operation), plus representative-pressure/gas testing of "
        "Paschen-risk paths; the supplier states each item's rated withstand and whether it permits the 1.05 kV / 60 s "
        "test, and supplies the DWV record or certificate where performed. The test is not repeated before each "
        "campaign (later reverification at a lower controlled level, TBD). The owner cites ECSS high-voltage practice "
        "without a standard / clause id (owner-stated; verify). RF insulation of the antenna / matching network "
        "(ICD ICP-44: RF peak voltage, RF current, RF creepage/clearance, combined RF + DC stress, vacuum/gas breakdown) "
        "is NOT covered and stays OPEN; the ~1 kV representative-gas qualification of ICP gas lines (A9.3 ICPQ-06, "
        "RFQ2-GAS-N04) is a separate requirement.",
        {"V_operating_max_V": 350.0, "V_design_withstand_min_V": 525.0, "initial_DWV_V_DC": 1050.0,
         "initial_DWV_duration_s": 60.0, "leakage_acceptance": "TBD - requires the item ratings (not owner-given)",
         "later_reverification": "TBD - owner-registered lower controlled level / procedure",
         "ICP_44_rf_insulation": "OPEN"},
        "V; s", "A9.4 P1Q-14; row 81; ICD ICP-23",
        dwv_sources + [OW(81, "rate H-1, C1 reference, discharge supply, isolation and diagnostics to the relaxed 350 V "
                              "end plus appropriate transient/qualification margin"),
                       DI("ICD", "ICP-23"), DI("ICD", "ICP-44")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        note="the ECSS reference is owner-stated (A9.4 recorder_flags[1]: standard and clause not identified - verify)",
        change_why="new: A9.4 P1Q-14 (ICP_350V_CLASS / 1.05kV_INITIAL_DWV)"))
    out.append(R(
        "RFQ2-VAC-N07", "RFQ2-VAC", "electrical feedthrough assemblies on ICP body / collector circuits: >= 525 V design "
        "withstand, 1.05 kV DC / 60 s DWV where ratings permit (A9.4 P1Q-14)",
        "Electrical feedthrough assemblies that carry ICP body / collector circuits (or isolate them from the H-1 anode, "
        "H-1 body/common or facility ground) have a design withstand >= 525 V and are DWV-tested at 1.05 kV DC for 60 s "
        "where their ratings permit (current-limited, leakage recorded); the supplier states the rated withstand per "
        "pin / assembly and supplies the test record or certificate where performed. RF feedthroughs stay under ICD "
        "ICP-44 (OPEN) and RFQ2-RF.",
        {"V_design_withstand_min_V": 525.0, "DWV_V_DC": 1050.0, "DWV_duration_s": 60.0,
         "leakage_acceptance": "TBD - requires the feedthrough ratings (not owner-given)"},
        "V; s", "A9.4 P1Q-14",
        dwv_sources[:6] + [A94("P1Q-14", "passive insulation paths and feedthrough assemblies"),
                           A93("OQ-RFQ-07", "feedthroughs")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        change_why="new: A9.4 P1Q-14 applied to the feedthrough lines"))
    return out


# ------------------------------------------------------------------ A9.6 RFQ completion (fo_a9_6_rfq_completion)
# P2 preparation instruments quoted from the merged P2 package: P2 id -> (v2 requirement id, RFQ line ids)
P2_REQ_MAP = [
    ("INS-P2-01", "RFQ2-RF-N07", ["RF-L12"]),
    ("INS-P2-02", "RFQ2-RF-N08", ["RF-L02"]),
    ("INS-P2-03", "RFQ2-RF-N09", ["RF-L03"]),
    ("INS-P2-04", "RFQ2-RF-N10", ["RF-L13"]),
    ("INS-P2-05", "RFQ2-RF-N11", ["RF-L14"]),
    ("INS-P2-06", "RFQ2-RF-N12", ["RF-L15"]),
    ("INS-P2-07", "RFQ2-RF-N13", ["RF-L09", "RF-L16"]),
    ("INS-P2-08", "RFQ2-RF-N14", ["RF-L17", "RF-L06"]),
    ("INS-P2-09", "RFQ2-RF-N15", ["RF-L18"]),
    ("INS-P2-12", "RFQ2-RF-N16", ["RF-L19"]),
]

P2Q02_PLACEMENT = {
    "package": "RFQ2-RF", "status": "TBD_OWNER",
    "question": "P2Q-02 (open question of the P2 preparation package: RF package or a separate RF-metrology package)",
    "alternatives": ["RFQ2-RF (owner RF family of A9.3 OQ-RFQ-07; current placement)",
                     "separate RF-metrology package under RFQ2-CIF (P2 lane proposal; different supplier speciality)"],
    "rule": "the line is self-contained (own requirement, quote sheet and CIF interfaces), so it moves verbatim to a "
            "separate package if the owner so decides; no placement is selected here",
}


def p2_spec_requirements() -> list:
    """One requirement per P2 preparation instrument that has no dedicated v2 requirement yet. The specification rows are
    COPIED verbatim from the merged P2 package (read, not pinned; see CURRENT); nothing is filled or narrowed here."""
    p2 = {x["id"]: x for x in current("P2")["instrument_list"]}
    out = []
    for iid, rid, lines in P2_REQ_MAP:
        if iid not in p2:
            raise KeyError(f"P2 instrument {iid} not found in {P2_JSON}")
        x = p2[iid]
        if not x.get("required_specs"):
            raise ValueError(f"P2 instrument {iid} carries no required_specs")
        out.append(R(
            rid, "RFQ2-RF", "P2 preparation instrument " + iid + ": " + x["name"],
            "Quote " + x["name"] + " to the P2 instrument-preparation specification rows below (copied verbatim from "
            "the merged P2 package, " + iid + "). The supplier states the offered value of every row with its "
            "calibration basis and uncertainty. Any power-, voltage- or current-bearing rating is quoted as a "
            "capability range or scalable option (" + TBD_RF + "; A9.2 rf_500W). Rows marked TBD are frozen at the gate "
            "named in the row and are not fixed by this RFQ. Quoted for lines " + ", ".join(lines) + ".",
            {"p2_required_specs_copied": copy.deepcopy(x["required_specs"])},
            x["units"], "P2 prep " + iid + " (A9.3 authorizations P2: instrument preparation starts immediately)",
            [CUR("P2", iid), A93J("/authorizations/P2"),
             A92Q("rf_500W", "It is not a sufficient component rating by itself.")],
            x["evidence_class"], x["status"], x["freeze_point"], "P1_NEEDED",
            note="dispatch-first because A9.3 starts P2 instrument preparation immediately in parallel with P1; package "
                 "placement TBD_OWNER (P2Q-02)",
            change_why="A9.6 RFQ completion: P2 instrument " + iid + " mapped to an RFQ line"))
    return out


def a96_requirements() -> list:
    ic = stand_ceiling_A()
    q14 = [A94("P1Q-14", "corresponding to a 1.5× design margin."), A94("P1Q-14", "1.05~kV~DC"),
           A94("P1Q-14", "60~s"), A94("P1Q-14", "where component ratings permit."),
           A96("5", "350 V operating class;"), A96("5", "≥525 V design-withstand basis;"),
           A96("5", "initial 1.05 kV DC / 60 s passive-insulation DWV where applicable.")]
    closure_quotes = [A95("P1Q-15", "calibration uncertainty;"), A95("P1Q-15", "zero/offset uncertainty;"),
                      A95("P1Q-15", "resolution;"), A95("P1Q-15", "repeatability where applicable;"),
                      A95("P1Q-15", "any registered RF-pickup contribution."),
                      A95("P1Q-15", "is a small registered denominator floor based on instrument capability"),
                      A95("P1Q-15", "Do not silently set an unavailable current channel to zero.")]
    out = []
    # ---------------------------------------------------------------- RF
    out.append(R(
        "RFQ2-RF-N17", "RFQ2-RF", "RF frequency and harmonic content (P1-M-06)",
        "Measurement of the generator frequency and harmonic content into the matched load during the P1-S1 cold "
        "checkout (P1-M-06). Quote a frequency counter / spectrum analyzer ONLY if the VNA of RF-L13 does not offer a "
        "receiver/spectrum mode covering N_h x 13.56 MHz (the supplier of RF-L13 states whether it does). Harmonic "
        "order N_h is TBD (UB-RF-06, LOCK-2).",
        {"frequency_MHz": 13.56, "harmonic_order_N_h": "TBD - requires the UB-RF-06 allocation (LOCK-2)",
         "item": "0 or 1 (option; not needed if RF-L13 offers a receiver/spectrum mode)"},
        "MHz; dBc", "P1-M-06; P2 INS-P2-04 (receiver/spectrum mode if available); row 72",
        [CUR("P1", "P1-M-06"), CUR("P2", "INS-P2-04"), DI("UB", "UB-RF-06"),
         OW(72, "13.56 MHz")],
        "owner-allocation", "OWNER_GIVEN", "LOCK-2", "P1_NEEDED",
        note="13.56 MHz is the owner frequency (row 72); the item is an option line because the VNA may cover it",
        change_why="A9.6 RFQ completion: P1-M-06 had no RFQ line"))
    # ---------------------------------------------------------------- GAS
    out.append(R(
        "RFQ2-GAS-N08", "RFQ2-GAS", "rate-of-rise / transfer calibration volume for the Ar controller",
        "Calibration volume with a reference pressure transducer (and temperature sensing) for the rate-of-rise / "
        "transfer verification of the Ar MFC (A9.3 OQ-RFQ-02; P1-HW-10). Volume, transducer range and uncertainty follow "
        "the UB-F-07 allocation; the supplier states the volume uncertainty and the transducer calibration basis. The "
        "facility may already hold such a volume; dispatch is the owner's call.",
        "TBD - requires the UB-F-07 allocation (volume, transducer range and uncertainty)", "m^3; Pa; K",
        "A9.3 OQ-RFQ-02; UB-F-07; P1-HW-10",
        [A93("OQ-RFQ-02", "Use the rate-of-rise/transfer calibration path to verify the Ar controller."),
         DI("UB", "UB-F-07"), CUR("P1", "P1-HW-10")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        change_why="A9.6 RFQ completion: P1-HW-10 had no dedicated RFQ line"))
    # ---------------------------------------------------------------- HALL ELECTRICAL
    out.append(R(
        "RFQ2-HALLEL-N05", "RFQ2-HALLEL", "ICP collector / bias supply: isolation class, current capability, metering",
        "The floating ICP collector / bias supply (HE-L03) has output isolation for the 350 V operating class with a "
        "design withstand >= 525 V and permits the 1.05 kV DC / 60 s initial DWV of the passive insulation where its "
        "ratings permit (A9.4 P1Q-14; supplier states); its current path (supply, leads, sensing, protection) is sized "
        "to the 8.33 A stand ceiling (A9.3 OQ-A907-02). Bias-voltage range TBD (A902-23; P1-IT-18). V/I readback: "
        "signed bipolar current reading with the uncertainty components of RFQ2-HALLEL-N08 stated. The supply rating is "
        "never the ICP-45 requirement (I_e,required = I_d,max,H1, registered).",
        {"V_operating_class_V": 350.0, "V_design_withstand_min_V": 525.0,
         "initial_DWV": {"V_DC": 1050.0, "duration_s": 60.0, "applies": "where component ratings permit"},
         "current_capability_A_min": ic, "bias_voltage_range": "TBD - requires A902-23 / P1-IT-18",
         "readback_uncertainty": "TBD - supplier states per RFQ2-HALLEL-N08"},
        "V; s; A", "A9.4 P1Q-14; A9.3 OQ-A907-02; A9.6 sec. 5; P1-IT-18, P1-IT-21, P1-IT-43",
        q14 + [A93("OQ-A907-02", "collector circuit rating;"), CUR("P1", "P1-IT-18"), CUR("P1", "P1-IT-21"),
               CUR("P1", "P1-IT-43"), CUR("P1", "P1-HW-26")],
        "owner-stated", "OWNER_GIVEN", "P1-G0", "P1_NEEDED",
        note="bias range and readback uncertainty stay TBD; only the isolation class and the current sizing rule are "
             "owner-given",
        change_why="A9.6 RFQ completion: collector/bias supply line carries the A9.4 P1Q-14 isolation class explicitly"))
    out.append(R(
        "RFQ2-HALLEL-N06", "RFQ2-HALLEL", "H-1 body single-point metered ground-current monitor (A9.4 P1Q-13)",
        "A ground-current monitor in the ONLY deliberate H-1 body / magnetic-circuit connection to facility ground "
        "(H-1 body -> monitor -> facility ground), logged continuously during ICP capacity measurements on the common "
        "time base; plus chamber / facility return-current monitoring where measurable (P1-M-13). The bench must have no "
        "second unintended chassis / stand / coax / shield grounding path (a wiring requirement of the bench, stated so "
        "that the supplier offers an isolated readout that does not create one). The current-carrying path of the monitor "
        "(conductor, shunt or sensor) is sized to the 8.33 A stand ceiling (A9.3 OQ-A907-02 rule for current-carrying "
        "bench items); the measuring range and resolution may be narrower and are chosen so that the registered "
        "I_scale,min and u_R of RFQ2-HALLEL-N08 can be met (supplier states over-range survivability). Signed "
        "bipolar reading.",
        {"monitored_path": "H-1 body / magnetic circuit -> monitor -> facility ground (single deliberate path)",
         "logging": "continuous during ICP capacity measurements (common time base INS-18)",
         "current_path_rating_A_min": ic,
         "range_resolution": "TBD - requires the registered I_scale,min and channel uncertainty (A9.5 P1Q-15; frozen "
                             "before the first ICP45_CAPACITY record)",
         "facility_return_monitors": "TBD - count per the P1 return-path map (P1-M-13; where measurable)"},
        "A", "A9.4 P1Q-13; A9.6 sec. 5; A9.5 P1Q-15; P1-M-29, P1-M-13, P1-HW-28",
        [A94("P1Q-13", "one deliberate facility-ground connection only, through an instrumented/metered return."),
         A94("P1Q-13", "No second unintended chassis/stand/coax/shield grounding path is permitted."),
         A94("P1Q-13", "continuously during ICP capacity measurements."),
         A94("P1Q-13", "chamber/facility return current where measurable."),
         A96("5", "H-1 body single-point metered ground;"), A96("5", "all intentional current paths instrumented."),
         A93("OQ-A907-02", "current sensor range;"),
         CUR("P1", "P1-M-29"), CUR("P1", "P1-M-13"), CUR("P1", "P1-HW-28"), DI("UB", "UB-N-04")] + closure_quotes[5:],
        "owner-stated", "OWNER_GIVEN", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        note="closes OQ-RFQV2-07 (explicit line) as a mechanical RFQ-line propagation of A9.4 P1Q-13 (A9.6 sec. 6); "
             "whether an existing laboratory instrument meeting this line is used instead remains the owner's dispatch "
             "choice",
        change_why="A9.6 RFQ completion: A9.4 P1Q-13 ground-current monitor made an explicit P1_NEEDED line"))
    out.append(R(
        "RFQ2-HALLEL-N07", "RFQ2-HALLEL", "H-1 anode physical disconnect means and high-impedance isolated V_anode channel",
        "(i) A means to PHYSICALLY disconnect the discharge-supply output from the H-1 anode (switch / contactor / "
        "removable link; supplier proposes) so that in every ICP45_CAPACITY record the anode is open-circuit by "
        "construction and floating - commanding the supply to zero while its output stays attached is not acceptable; "
        "the disconnect state is recorded on the DAQ (hall_discharge_state, P1-IT-40). Current path sized to the 8.33 A "
        "stand ceiling; voltage class 350 V (row 81) with the transient/qualification margin TBD_OWNER (OQ-RFQV2-06). "
        "(ii) A high-impedance, isolated V_anode measurement channel (and the V_ref channel for V_d, P1-HW-31), usable "
        "with the anode floating; the supplier states the input impedance and isolation so that the channel's own "
        "leakage can be bounded inside u_R (A9.5 P1Q-15). No input-impedance number is set here.",
        {"disconnect": "physical disconnection of the discharge-supply output from the anode (supplier proposes the "
                       "means)",
         "disconnect_current_rating_A_min": ic,
         "voltage_class": {"V_upper_before_margin": 350.0, "margin": "TBD_OWNER (row 81; OQ-RFQV2-06)"},
         "V_anode_channel": "high-impedance, isolated; input impedance TBD - supplier states (leakage bounded in u_R)",
         "anode_terminal_class": "OPEN_CIRCUIT_BY_CONSTRUCTION in ICP45_CAPACITY records (A9.4 P1Q-13)"},
        "A; V; ohm", "A9.4 P1Q-13; A9.6 sec. 5; row 81; P1-IT-39, P1-M-15, P1-HW-24, P1-HW-31",
        [A94("P1Q-13", "physically disconnected from the discharge supply and left floating"),
         A94("P1Q-13", "Do not merely command the power supply to zero while leaving its output electrically attached."),
         A94("P1Q-13", "with a high-impedance isolated measurement channel."),
         A94("P1Q-13", "`OPEN_CIRCUIT_BY_CONSTRUCTION`"),
         A96("5", "anode physically disconnected;"), A96("5", "anode floating;"),
         A96("5", "high-impedance (V_{\\rm anode}) measurement;"),
         OW(81, "rate H-1, C1 reference, discharge supply, isolation and diagnostics to the relaxed 350 V end plus "
                "appropriate transient/qualification margin"),
         CUR("P1", "P1-IT-39"), CUR("P1", "P1-IT-40"), CUR("P1", "P1-M-15"), CUR("P1", "P1-HW-24"),
         CUR("P1", "P1-HW-31"), DI("UB", "UB-N-02")],
        "owner-stated", "OWNER_GIVEN", "LOCK-1", "P1_NEEDED", applies_to=CONFIGS,
        note="closes OQ-RFQV2-07 for the V_anode channel (mechanical propagation of A9.4 P1Q-13, A9.6 sec. 6); the "
             "voltage margin stays with OQ-RFQV2-06",
        change_why="A9.6 RFQ completion: A9.4 P1Q-13 anode disconnect + V_anode channel made explicit P1_NEEDED lines"))
    out.append(R(
        "RFQ2-HALLEL-N08", "RFQ2-HALLEL", "current-closure metrology of every current channel of the ICP-45 network "
        "(A9.5 P1Q-15)",
        "Every current channel that crosses the registered isolated-network boundary in an ICP45_CAPACITY record "
        "(dedicated electron collector, H-1 body return, anode (floating; potential recorded), facility / chamber "
        "return, ICP body, and any other intentional terminal) is quoted with, per channel: calibration uncertainty; "
        "zero/offset uncertainty; resolution; repeatability where applicable; susceptibility to 13.56 MHz RF pickup (so "
        "that a registered RF-pickup contribution can be assigned). Readings are signed (bipolar) and the polarity is "
        "documented so that each channel can be transformed into the registered convention (conventional current INTO "
        "the defined isolated network positive). These values let the owner register I_scale,min from the "
        "instrumentation capability and form u_R; the closure limits (|R_I| <= 3 u_R and |R_I| / max(|I_e,collector|, "
        "I_scale,min) <= 0.02) are applied by the P1 reducer to measured records, not as supplier acceptance criteria. "
        "If the quoted instruments give 3 u_R > 0.02 |I_e,collector| the point is NOT_EVALUATED_INSTRUMENT (the "
        "tolerance is never widened); no channel may be silently set to zero.",
        {"per_channel_supplier_states": ["calibration uncertainty", "zero/offset uncertainty", "resolution",
                                         "repeatability where applicable", "13.56 MHz RF-pickup susceptibility"],
         "polarity": "signed bipolar; documented polarity (transform to the registered convention)",
         "I_scale_min": "TBD - registered from the instrumentation capability (A9.5 P1Q-15; no default)",
         "closure_rule_context": {"statistical": "|R_I| <= 3 u_R", "fractional": 0.02,
                                  "inadequate_instrument": "NOT_EVALUATED_INSTRUMENT"}},
        "A", "A9.5 P1Q-15; A9.6 sec. 2; A9.4 P1Q-13; P1-IT-42, P1-IT-47",
        closure_quotes + [
            A95("P1Q-15", "conventional current INTO the defined isolated electrical network is positive"),
            A95("P1Q-15", "`NOT_EVALUATED_INSTRUMENT`"), A95("P1Q-15", "an intentional return path is unmeasured;"),
            A96("2", "`I_scale,min` must be registered from the instrumentation capability; no default."),
            CUR("P1", "P1-IT-42"), CUR("P1", "P1-IT-47"), DI("UB", "UB-N-03")],
        "owner-stated", "OWNER_GIVEN", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        note="the 0.02 fraction and the 3 u_R statistic are owner-stated (A9.5) and quoted only to explain why the "
             "uncertainty components are required; I_scale,min itself is not set here",
        change_why="A9.6 RFQ completion: A9.5 P1Q-15 requires per-channel uncertainty components the quotations must "
                   "state"))
    out.append(R(
        "RFQ2-HALLEL-N09", "RFQ2-HALLEL", "OPTION: current-limited DC dielectric-withstand tester (>= 1.05 kV)",
        "Current-limited DC dielectric-withstand tester able to apply at least 1.05 kV DC for 60 s with leakage-current "
        "read-out, for the initial in-house DWV of the assembled ICP body / collector insulation configuration (A9.4 "
        "P1Q-14; P1-HW-30). OPTION LINE: needed only if the owner's answer to OQ-RFQV2-08 includes an in-house bench "
        "DWV (TBD_OWNER); leakage read-out resolution TBD - requires the item ratings.",
        {"V_DC_min": 1050.0, "duration_s": 60.0, "current_limited": True, "leakage_readout": "required",
         "leakage_resolution": "TBD - requires the item ratings (not owner-given)", "need": "TBD_OWNER (OQ-RFQV2-08)"},
        "V; s; A", "A9.4 P1Q-14; P1-HW-30",
        [A94("P1Q-14", "1.05~kV~DC"), A94("P1Q-14", "60~s"), CUR("P1", "P1-HW-30"), CUR("P1", "P1-IT-44")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        note="option line: the two admissible DWV routes of OQ-RFQV2-08 (supplier certificate / in-house bench) are both "
             "kept; nothing is selected",
        change_why="A9.6 RFQ completion: P1-HW-30 had no RFQ line"))
    # ---------------------------------------------------------------- MECH
    out.append(R(
        "RFQ2-MECH-N05", "RFQ2-MECH", "OPTION: P1-S4 dedicated electron-collecting target (topology A)",
        "If topology A is registered at P1-G0 (P1-IT-36; P1Q-09), a dedicated, isolated, instrumented "
        "electron-collecting electrode: isolated plate, support, position datum and feedthrough lead, isolated to the "
        "ICP body / collector class of CIF-G07 (350 V operating, >= 525 V design withstand, 1.05 kV DC / 60 s DWV where "
        "ratings permit). Geometry and material TBD at P1-G0; the flight collector material is not frozen.",
        {"geometry": "TBD - requires registration at P1-G0 (P1-IT-36)",
         "isolation": "CIF-G07 class (A9.4 P1Q-14)",
         "material": "TBD - requires P1-IT-36 registration (flight collector material not frozen)",
         "need": "only if topology A is registered (option line)"},
        "mm; V", "A9.4 P1Q-10, P1Q-14; P1-IT-36, P1-HW-36, P1-M-27",
        [A94("P1Q-10", "electrons extracted to a dedicated, isolated, instrumented electron-collecting electrode;"),
         A94("P1Q-14", "1.05~kV~DC"), CUR("P1", "P1-IT-36"), CUR("P1", "P1-HW-36"), CUR("P1", "P1-M-27"),
         PEND(PARALLEL_LANES["P4"], "collector / anode candidate-material framework")],
        None, "TBD", "P1-G0", "P1_NEEDED",
        change_why="A9.6 RFQ completion: P1-HW-36 had no RFQ line"))
    # ---------------------------------------------------------------- THRUST / METROLOGY
    out.append(R(
        "RFQ2-THRUST-N04", "RFQ2-THRUST", "calibration services and certificates for the P1 instruments",
        "Calibration of every P1 instrument with a calibrated measurand (P1 measurement list, metrology_spec) that is "
        "not delivered with a valid certificate by its supplier: certificate per MS-G-01..03 (accredited scope, "
        "SI-traceable chain, GUM uncertainty with coverage factor), stating for current channels the A9.5 components "
        "(calibration, zero/offset, resolution, repeatability); 13.56 MHz calibration of RF power sensors and coupler "
        "(coupling factor, directivity); gauges calibrated for Ar. Whether the Ar MFC needs an accredited certificate or "
        "the maker's Ar certificate plus the rate-of-rise/transfer verification is TBD_OWNER (OQ-RFQV2-01).",
        {"certificate_rule": "MS-G-01..03 per P1 measurement metrology_spec",
         "current_channel_components": ["calibration uncertainty", "zero/offset uncertainty", "resolution",
                                        "repeatability where applicable"],
         "Ar_MFC_certificate": "TBD_OWNER (OQ-RFQV2-01)",
         "instrument_list": "every P1_NEEDED line with a calibrated measurand (instrument_coverage)"},
        "-", "P1 measurements metrology_spec (MS-G-01..03); row 126; A9.5 P1Q-15; A9.3 OQ-RFQ-02",
        [CUR("P1", "P1-M-01"), CUR("P1", "P1-HW-41"),
         OW(126, "NABL/ISO-17025 calibration is the primary score-bearing reference."),
         A95("P1Q-15", "calibration uncertainty;"), A95("P1Q-15", "zero/offset uncertainty;"),
         A93("OQ-RFQ-07", "traceability hardware")],
        "owner-stated", "OWNER_GIVEN", "NOW", "P1_NEEDED", applies_to=CONFIGS,
        note="calibration SERVICES line; certificates delivered with an instrument satisfy it for that instrument",
        change_why="A9.6 RFQ completion: owner sec. 13 names calibration items"))
    out.append(R(
        "RFQ2-THRUST-N05", "RFQ2-THRUST", "event and state channels on the common time base",
        "Digital event / state inputs on the common time base (INS-18) for: ignition / extinction events (P1-M-23; "
        "INS-10), interlock state and trip events (P1-M-25), hall_discharge_state and the anode-disconnect state "
        "(P1-IT-40; RFQ2-HALLEL-N07), and the local-match setting id (P1-M-09). Channel count and time resolution are "
        "frozen at P1-G0.",
        {"channels": ["ignition/extinction events", "interlock state/trips", "hall_discharge_state",
                      "anode disconnect state", "match_setting_id"],
         "count_and_time_resolution": "TBD - frozen at P1-G0 (P1-M-26)"},
        "-; s", "P1-M-09, P1-M-23, P1-M-25, P1-M-26, P1-IT-40; INS-10, INS-18",
        [CUR("P1", "P1-M-23"), CUR("P1", "P1-M-25"), CUR("P1", "P1-M-09"), CUR("P1", "P1-M-26"),
         CUR("P1", "P1-IT-40"), DI("INS", "INS-10"), DI("INS", "INS-18"), A93("OQ-RFQ-07", "DAQ")],
        None, "TBD", "P1-G0", "P1_NEEDED", applies_to=CONFIGS,
        change_why="A9.6 RFQ completion: P1 event / state records mapped to DAQ inputs"))
    return out + p2_spec_requirements()


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
                           "value": "TBD - sweep bounds frozen at P1-G0 (P1 run_matrix F2); anchor 70 sccm ~ 2.1 mg/s "
                                    "owner-stated",
                           "status": "TBD", "freeze_point": "P1-G0", "evidence_class": "owner-stated",
                           "add_sources": [A93("OQ-RFQ-02", "Start with:"), CUR("P1", "F2")]})
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
        m[f"RFQ-03-R{i:02d}"] = ("RFQ2-VAC", "P1_NEEDED", C_U, SPLIT + "; A9.6 RFQ completion: dispatch LATER -> "
                                 "P1_NEEDED because the merged P1 bench lists the RGA as REQUIRED in P1-S2..S7 (P1-M-20, "
                                 "P1-HW-19); text unchanged", None)
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
def L(lid, item, qty, basis, dispatch, covers=(), reqs=(), option=False, v1_ref=None, change="NEW", why=None,
      placement=None):
    out = {"id": lid, "item": item, "qty": qty, "basis": basis, "dispatch": dispatch, "option_line": option,
           "covers_owner_items": list(covers), "requirements": list(reqs), "v1_ref": v1_ref,
           "change": {"type": change, "why": why}}
    if placement is not None:
        out["placement"] = copy.deepcopy(placement)
    return out


def line_items() -> dict:
    p1 = "TBD - quantity per the P1 bench plan (registered at P1-G0)"
    rf = {
        "RFQ2-RF": [
            L("RF-L01", "13.56 MHz laboratory RF generator, mains-powered, GROUND/FACILITY_ONLY; forward-power options "
                        "quoted as capability ranges (rating " + TBD_RF + ")", 1, "row 72; row 8; A9.3 OQ-RFQ-06",
              "P1_NEEDED", ["13.56 MHz generator"], ["RFQ-04-R01", "RFQ-04-R02", "RFQ-04-R03", "RFQ-04-R04",
                                                    "RFQ-04-R05", "RFQ2-RF-N01"],
              v1_ref="RFQ-04 quantities[0]", change="CARRIED_MODIFIED",
              why="ground-only classification and capability-range quoting (A9.3 OQ-RFQ-06, A9.2 rf_500W)"),
            L("RF-L02", "dual directional coupler on the generator / 50-ohm side of the local match", 1, "row 72; A9.2",
              "P1_NEEDED", ["directional coupler"], ["RFQ-04-R08", "RFQ-04-R09", "RFQ2-RF-N08"],
              v1_ref="RFQ-04 quantities[2]",
              change="CARRIED_MODIFIED", why="v1 quoted coupler + sensors as one line; split to match the owner list"),
            L("RF-L03", "forward/reflected power sensors calibrated at 13.56 MHz", "1 set", "row 72", "P1_NEEDED",
              ["forward/reflected sensors"], ["RFQ-04-R08", "RFQ-04-R09", "RFQ2-RF-N06", "RFQ2-RF-N09"],
              v1_ref="RFQ-04 quantities[2]",
              change="CARRIED_MODIFIED", why="split from the v1 coupler line"),
            L("RF-L04", "adjustable local matching network components for on-module mounting (development article)", 1,
              "row 8; A9.2 OQ-A907-11 / icp_matching_strategy", "P1_NEEDED", ["local matching network components"],
              ["RFQ-04-R06", "RFQ-04-R07", "RFQ-04-R17"], v1_ref="RFQ-04 quantities[1]", change="CARRIED_UNCHANGED"),
            L("RF-L05", "50-ohm RF coax generator -> coupler -> local match (P1 bench)", p1, "A9.2 OQ-A907-11",
              "P1_NEEDED", ["RF coax"], ["RFQ2-RF-N05"], why="new P1 line"),
            L("RF-L06", "flexible RF coax, identical live + sham pair for the thrust-stand crossing", 2,
              "rows 117, 133", "LATER", ["RF coax"], ["RFQ-04-R11", "RFQ2-RF-N14"], v1_ref="RFQ-04 quantities[5]",
              change="CARRIED_UNCHANGED"),
            L("RF-L07", "vacuum RF feedthrough (ratings as capability ranges, " + TBD_RF + ")",
              "TBD - requires module drawings (ICD ICP-15) + spare (OQ-RFQ-01, OPEN)", "row 8", "P1_NEEDED",
              ["feedthroughs"], ["RFQ-04-R12"], v1_ref="RFQ-04 quantities[4]", change="CARRIED_MODIFIED",
              why="capability-range quoting (A9.2 rf_500W)"),
            L("RF-L08", "50-ohm RF dummy load (rating >= selected generator option; " + TBD_RF + ")", 1,
              "ICD ICP-14 / ICP-17", "P1_NEEDED", ["dummy load"], ["RFQ2-RF-N04"], why="new explicit line"),
            L("RF-L09", "calorimetric cross-check load (P2 INS-P2-07 (a) 50-ohm calorimetric load)", 1,
              "row 72; A9.1 UBQ-04", "P1_NEEDED", [], ["RFQ-04-R10", "RFQ2-RF-N13"],
              v1_ref="RFQ-04 quantities[3]", change="CARRIED_UNCHANGED"),
            L("RF-L10", "RF protection / interlock functions: reflected-power monitoring, mismatch interlock, arc "
                        "detection where feasible, thermal monitoring, automatic reduction/shutdown (thresholds after "
                        "characterization)", "1 set (integral or separate; supplier states)", "A9.2 rf_protection; "
                                                                                          "ICD ICP-16",
              "P1_NEEDED", ["RF protection/interlocks"], ["RFQ-04-R03", "RFQ-04-R16"], why="made an explicit line"),
            L("RF-L11", "input power analyzer on the laboratory generator mains input (P_mains,in)", 1,
              "A9.3 OQ-RFQ-06", "P1_NEEDED", [], ["RFQ2-RF-N02", "RFQ2-RF-N03"], why="required by A9.3 OQ-RFQ-06"),
            # ---- A9.6: P2 preparation / P1 RF metrology (placement TBD_OWNER, P2Q-02)
            L("RF-L12", "V/I probe (complex V and I, phase-resolved) at the antenna-terminal reference plane RP-VI "
                        "(P2 INS-P2-01)", 1, "P2 INS-P2-01; A9.3 authorizations P2", "P1_NEEDED", [],
              ["RFQ2-RF-N07", "RFQ2-RF-N06"], why="A9.6 RFQ completion: P2 instrument INS-P2-01", placement=P2Q02_PLACEMENT),
            L("RF-L13", "vector network analyser, one-port and two-port, receiver/spectrum mode if available "
                        "(P2 INS-P2-04; P1 two-port / cold-antenna characterization)", 1,
              "P2 INS-P2-04; P1-HW-07", "P1_NEEDED", [], ["RFQ2-RF-N10"],
              why="A9.6 RFQ completion: P2 instrument INS-P2-04", placement=P2Q02_PLACEMENT),
            L("RF-L14", "calibration kits: coaxial SOL/SOLT with standard data + antenna-terminal fixture standards "
                        "(P2 INS-P2-05)", "1 set (connector family TBD - requires the selected coax / feedthrough, "
                                         "ICD ICP-15)", "P2 INS-P2-05", "P1_NEEDED", [], ["RFQ2-RF-N11"],
              why="A9.6 RFQ completion: P2 instrument INS-P2-05 (calibration item)", placement=P2Q02_PLACEMENT),
            L("RF-L15", "fixed attenuators for sensor / VNA protection and coupling-arm padding (P2 INS-P2-06)",
              "1 set (values TBD - requires the coupler coupling factor and the generator selection)", "P2 INS-P2-06",
              "P1_NEEDED", [], ["RFQ2-RF-N12"], why="A9.6 RFQ completion: P2 instrument INS-P2-06",
              placement=P2Q02_PLACEMENT),
            L("RF-L16", "antenna-simulator dummy load of VNA-known low-R / high-X impedance (P2 INS-P2-07 (b))", 1,
              "P2 INS-P2-07", "P1_NEEDED", [], ["RFQ2-RF-N13"],
              why="A9.6 RFQ completion: P2 instrument INS-P2-07 (b) (dummy load)", placement=P2Q02_PLACEMENT),
            L("RF-L17", "phase-stable VNA test cables (P2 INS-P2-08; the stand-crossing pair is RF-L06)", "1 set",
              "P2 INS-P2-08", "P1_NEEDED", [], ["RFQ2-RF-N14"],
              why="A9.6 RFQ completion: P2 instrument INS-P2-08", placement=P2Q02_PLACEMENT),
            L("RF-L18", "antenna RF current probe (Rogowski / current transformer) (P2 INS-P2-09; P1-M-07)", 1,
              "P2 INS-P2-09; P1-M-07", "P1_NEEDED", [], ["RFQ2-RF-N15"],
              why="A9.6 RFQ completion: P2 instrument INS-P2-09", placement=P2Q02_PLACEMENT),
            L("RF-L19", "match-element position read-out / encoders on the local match (P2 INS-P2-12; P1-M-09)",
              "1 per adjustable match element (count TBD - requires the local-match design, RF-L04)",
              "P2 INS-P2-12; P1-M-09", "P1_NEEDED", ["local matching network components"],
              ["RFQ2-RF-N16", "RFQ-04-R07"], why="A9.6 RFQ completion: P2 instrument INS-P2-12",
              placement=P2Q02_PLACEMENT),
            L("RF-O01", "OPTION: frequency counter / spectrum analyzer for f_RF and harmonics (P1-M-06) - only if RF-L13 "
                        "has no receiver/spectrum mode", "0 or 1 (option line)", "P1-M-06; row 72", "P1_NEEDED", [],
              ["RFQ2-RF-N17"], option=True, why="A9.6 RFQ completion: P1-M-06", placement=P2Q02_PLACEMENT),
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
              "TBD - requires the P1 gas schematic (P1-HW-12; P1-G0)", "row 105; H2-3 H23-27", "P1_NEEDED",
              ["gas isolators"], ["RFQ2-GAS-N05"], why="owner family item; P1 runs H-1 on Ar"),
            L("GAS-L14", "ICP gas-line isolator - only where a line bridges isolated potentials (none for the capped "
                         "G-REUSE port)", "TBD - requires the P1 potential map (P1-HW-12, P1-IT-20; P1-G0)",
              "A9.3 ICPQ-06", "P1_NEEDED", ["gas isolators"], ["RFQ2-GAS-N04"], why="A9.3 ICPQ-06"),
            L("GAS-L15", "Xe-line dielectric break (C1 branch)", "TBD - requires the C1 circuit potentials",
              "H2-2 H3-C1-04", "LATER", ["gas isolators"], ["RFQ-08-R12"], change="CARRIED_UNCHANGED",
              v1_ref="RFQ-08-R12 (requirement; no v1 quantity line)"),
            L("GAS-L16", "calibration: own-gas certificate per device and gas; Ar via rate-of-rise/transfer "
                         "verification; NABL/ISO-17025 for score-bearing N2/O2/Xe", "per device",
              "rows 124, 126; A9.3 OQ-RFQ-02", "P1_NEEDED", ["calibration"],
              ["RFQ-02-R18", "RFQ2-GAS-N03"], why="owner family item made explicit"),
            L("GAS-L17", "rate-of-rise / transfer calibration volume with reference pressure transducer (Ar controller "
                         "verification; P1-HW-10)", "1 (TBD - requires the UB-F-07 allocation; the facility may hold one)",
              "A9.3 OQ-RFQ-02; UB-F-07", "P1_NEEDED", ["calibration"], ["RFQ2-GAS-N08", "RFQ2-GAS-N03"],
              why="A9.6 RFQ completion: P1-HW-10 (calibration item)"),
        ],
        "RFQ2-VAC": [
            L("VAC-L01", "chamber interface flanges / adapter plates / internal mounting", "TBD - requires facility "
              "identification (row 139)", "A9.3 OQ-RFQ-07", "P1_NEEDED", ["chamber interfaces"], ["RFQ2-VAC-N01"],
              why="owner family item"),
            L("VAC-L02", "pumping (only where the identified facility lacks it)", "TBD - requires facility "
              "identification (row 139)", "A9.3 OQ-RFQ-07", "P1_NEEDED", ["pumping"], ["RFQ2-VAC-N02"],
              why="owner family item"),
            L("VAC-L03", "electrical vacuum feedthroughs (discharge, collector/bias, magnet, sensing) rated >= 8.33 A; "
                         "ICP body / collector assemblies >= 525 V design withstand, 1.05 kV DC / 60 s DWV where "
                         "ratings permit (A9.4 P1Q-14)",
              p1, "A9.3 OQ-A907-02; row 81; A9.4 P1Q-14", "P1_NEEDED", ["feedthroughs"],
              ["RFQ2-VAC-N03", "RFQ2-VAC-N07"], why="owner family item; A9.4 P1Q-14 DWV / design withstand added"),
            L("VAC-L04", "gas feedthroughs", p1, "A9.3 OQ-RFQ-07", "P1_NEEDED", ["feedthroughs"], ["RFQ2-VAC-N04"],
              why="owner family item"),
            L("VAC-L05", "RGA head + electronics + differentially pumped sampling system (~200 amu)", 1, "row 127; P1-M-20",
              "P1_NEEDED", ["RGA/diagnostic interfaces"], [f"RFQ-03-R0{i}" for i in range(1, 8)],
              v1_ref="RFQ-03 quantities[0]", change="CARRIED_MODIFIED",
              why="A9.6 RFQ completion: dispatch LATER -> P1_NEEDED because the merged P1 bench lists the RGA as "
                  "REQUIRED in P1-S2..S7 (P1-M-20, P1-HW-19); item text and requirements unchanged"),
            L("VAC-L06", "RGA / diagnostic port provisions", "TBD - requires facility layout (ICD ICP-07)",
              "A9.3 OQ-RFQ-07; INS-22", "LATER", ["RGA/diagnostic interfaces"], ["RFQ2-VAC-N05"],
              why="owner family item"),
            L("VAC-L07", "optical access / viewport or window with line of sight to the ICP source volume for the "
                         "photodiode (A9.4 P2Q-05)", 1, "A9.4 P2Q-05", "P1_NEEDED", ["RGA/diagnostic interfaces"],
              ["RFQ2-VAC-N06"], why="A9.4 P2Q-05 procurement: optical access / window (a chamber / diagnostic "
                                    "interface item, hence the vacuum/facility package)"),
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
            L("HE-L03", "floating ICP collector/bias supply with signed V/I readback: output isolation 350 V class, "
                        ">= 525 V design withstand, 1.05 kV DC / 60 s DWV where ratings permit (A9.4 P1Q-14); current "
                        "capability to the 8.33 A stand ceiling; bias range TBD (A902-23)", 1,
              "row 70; ICD ICP-21; A9.3 OQ-A907-02; A9.4 P1Q-14", "P1_NEEDED", [],
              ["RFQ-05-R07", "RFQ2-HALLEL-N01", "RFQ2-HALLEL-N04", "RFQ2-HALLEL-N05", "RFQ2-HALLEL-N08"],
              v1_ref="RFQ-05 quantities[4]", change="CARRIED_MODIFIED",
              why="moved from v1 RFQ-05; stand-ceiling sizing; A9.6: A9.4 P1Q-14 isolation class and A9.5 readback "
                  "metrology made explicit on the line"),
            L("HE-L04", "isolation hardware for the discharge and collector/bias circuits (350 V class, incl. the ICP "
                        "body / collector circuits per A9.4 P1Q-14: >= 525 V design withstand; 1.05 kV DC / 60 s initial "
                        "DWV of passive insulation paths where ratings permit)", p1,
              "row 81; ICD ICP-23; A9.4 P1Q-14", "P1_NEEDED", ["isolation"], ["RFQ-05-R08", "RFQ2-HALLEL-N04"],
              why="owner family item; A9.4 P1Q-14 DWV / design withstand added"),
            L("HE-L05", "discharge and collector V/I sensing (current ranges >= 8.33 A)", p1,
              "A9.3 OQ-VI-05, OQ-A907-02", "P1_NEEDED", ["sensing"], ["RFQ2-HALLEL-N03", "RFQ2-HALLEL-N08"],
              why="owner family item; A9.6: A9.5 closure metrology"),
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
            # ---- A9.6: A9.4 P1Q-13 / A9.5 P1Q-15 bench electrical lines
            L("HE-L15", "H-1 body single-point metered ground-current monitor (continuous I_body->ground) + chamber / "
                        "facility return-current monitor(s) where measurable (A9.4 P1Q-13)",
              "1 H-1 body monitor + facility / chamber return monitor(s) (count TBD - requires the P1 return-path map, "
              "P1-M-13; P1-G0)", "A9.4 P1Q-13; P1-M-29, P1-M-13", "P1_NEEDED", ["sensing"],
              ["RFQ2-HALLEL-N06", "RFQ2-HALLEL-N08", "RFQ2-HALLEL-N01"],
              why="A9.6 RFQ completion: A9.4 P1Q-13 (closes OQ-RFQV2-07 by mechanical propagation)"),
            L("HE-L16", "high-impedance isolated V_anode channel + V_ref channel for V_d (A9.4 P1Q-13; P1-M-15)",
              "1 V_anode + 1 V_ref", "A9.4 P1Q-13; P1-M-15, P1-HW-31", "P1_NEEDED", ["sensing"],
              ["RFQ2-HALLEL-N07", "RFQ2-HALLEL-N08"],
              why="A9.6 RFQ completion: A9.4 P1Q-13 (closes OQ-RFQV2-07 by mechanical propagation)"),
            L("HE-L17", "H-1 anode physical disconnect means (discharge-supply output physically disconnected; state "
                        "recorded on the DAQ) (A9.4 P1Q-13; P1-HW-24)", 1, "A9.4 P1Q-13; P1-IT-39, P1-HW-24",
              "P1_NEEDED", ["isolation"], ["RFQ2-HALLEL-N07"],
              why="A9.6 RFQ completion: A9.4 P1Q-13 anode OPEN_CIRCUIT_BY_CONSTRUCTION"),
            L("HE-L18", "floating-rated V/I channels for the ICP body (V_body, I_body) and the P1-S4 electron-collecting "
                        "electrode (current + divider) (P1-M-12, P1-M-27)",
              "TBD - per the registered P1-S4 topology (P1-IT-36; P1-G0)", "A9.4 P1Q-10, P1Q-13; P1-M-12, P1-M-27",
              "P1_NEEDED", ["sensing"], ["RFQ2-HALLEL-N08", "RFQ2-HALLEL-N04"],
              why="A9.6 RFQ completion: P1-M-12 / P1-M-27 channels"),
            L("HE-O02", "OPTION: current-limited DC dielectric-withstand tester >= 1.05 kV with leakage read-out "
                        "(P1-HW-30)", "0 or 1 (option line; TBD_OWNER OQ-RFQV2-08)", "A9.4 P1Q-14; P1-HW-30",
              "P1_NEEDED", ["isolation"], ["RFQ2-HALLEL-N09"], option=True,
              why="A9.6 RFQ completion: P1-HW-30 (both DWV routes of OQ-RFQV2-08 kept)"),
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
            L("ME-O01", "OPTION: P1-S4 dedicated electron-collecting target (isolated plate, support, position datum, "
                        "feedthrough lead) - only if topology A is registered (P1-IT-36)",
              "0 or 1 (option line; geometry TBD at P1-G0)", "A9.4 P1Q-10; P1-HW-36", "P1_NEEDED", ["collector"],
              ["RFQ2-MECH-N05"], option=True, why="A9.6 RFQ completion: P1-HW-36"),
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
              1, "A9.3 OQ-VI-05, OQ-RFQ-07", "P1_NEEDED", ["DAQ"], ["RFQ2-THRUST-N01", "RFQ2-THRUST-N05"],
              why="owner family item; A9.6: event / state channels"),
            L("TH-L05", "temperature sensors for the ICP-34 temperature channels", p1, "ICD ICP-34", "P1_NEEDED",
              ["DAQ"], ["RFQ2-THRUST-N01"], why="P1 temperature channels (A9.3 P1 authorization lists temperature)"),
            L("TH-L06", "traceability hardware: calibration references / certificates for DAQ V/I/T channels, RF "
                        "power sensors and the power analyzer", p1, "A9.3 OQ-RFQ-07; row 126", "P1_NEEDED",
              ["traceability hardware"], ["RFQ2-THRUST-N02", "RFQ-09-R01"], why="owner family item"),
            L("TH-L07", "optical-emission photodiode + amplifier (REQUIRED ignition / unlit and E/H indicator, INS-P2-10; "
                        "A9.4 P2Q-05)", "1 set", "A9.4 P2Q-05", "P1_NEEDED", ["DAQ"], ["RFQ2-THRUST-N03"],
              why="A9.4 P2Q-05 procurement: photodiode + amplifier on the P1 DAQ (optical, non-RF diagnostic kept "
                  "independent of the RF chain, hence not RFQ2-RF)"),
            L("TH-L08", "DAQ channel for the photodiode on the common time base, simultaneous with P_refl, antenna "
                        "current, collector / current-path and pressure channels (A9.4 P2Q-05)", 1, "A9.4 P2Q-05; INS-18",
              "P1_NEEDED", ["DAQ"], ["RFQ2-THRUST-N03", "RFQ2-THRUST-N01"],
              why="A9.4 P2Q-05 procurement: DAQ channel"),
            L("TH-L09", "calibration services / certificates for the P1 instruments not delivered with a valid "
                        "certificate (MS-G-01..03; A9.5 current-channel components)",
              "per instrument (TBD - requires the dispatched P1 line set)", "P1 metrology_spec; row 126; A9.5 P1Q-15",
              "P1_NEEDED", ["traceability hardware"], ["RFQ2-THRUST-N04", "RFQ-09-R01"],
              why="A9.6 RFQ completion: owner sec. 13 'calibration items'"),
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
    {"id": "NIR-06", "item": "H-1 fabrication (H2-1 CI H-1 with MC-1; H2-3 gas path / anode plenum), needed from P1-S3",
     "package_when_issued": "TBD_OWNER (OQ-RFQV2-10: separate fabrication RFQ, RFQ2-MECH extension, or in-house)",
     "why": "outside the six owner RFQ families (A9.3 OQ-RFQ-07 lists ICP fabrication only); no route is selected here",
     "source": "A9.3 OQ-RFQ-07; P1-HW-15, P1-HW-22 (merged P1 package)"},
]



# ------------------------------------------------------------------------ per-line quote sheets (A9.6 RFQ completion)
NA_CAL = "n/a - no calibrated measurand (dimensional / material / functional item)"
P2_ACC = "supplier states the offered value of every copied P2 specification row; incoming verification with RF-L13 / " \
         "RF-L14 where the P2 calibration plan applies"
LINE_QA = {
    # ---- RF
    "RF-L01": (["factory test report: forward power over the quoted capability range into 50 ohm at 13.56 MHz",
                "each protection feature demonstrated (RF-L10); trip thresholds set after characterization"],
               ["internal meters indicative only; P_RF is measured by RF-L02 / RF-L03 at RP-RF-50"],
               ["capability-range / scalable-option table (A9.2 rf_500W)",
                "mains input interface (phases, voltage, frequency) for RF-L11",
                "remote-control, interlock and data interfaces"]),
    "RF-L02": (["coupling factor and directivity at 13.56 MHz verified on delivery (certificate or RF-L13 / RF-L14 check)"],
               ["13.56 MHz coupling-factor and directivity certificate with uncertainty (RFQ2-THRUST-N04)"],
               ["power capability range; connector family (CIF-C01); vector (phase) output yes/no (P2 INS-P2-02)"]),
    "RF-L03": (["zero and linearity check against the certificate"],
               ["traceable 13.56 MHz certificate with uncertainty and coverage factor (P2 INS-P2-03)"],
               ["range / linearity, zeroing procedure, DAQ interface on the common time base (CIF-T01)"]),
    "RF-L04": (["tuning range demonstrated on the antenna-simulator load (RF-L16) and the dummy load; no rating is "
                "accepted before the impedance map"],
               ["n/a - element positions are read by RF-L19"],
               ["matching-element V / I capability ranges (A9.2 rf_500W)", "mounting interface to ME-L08"]),
    "RF-L05": (["insertion and return loss at 13.56 MHz measured with RF-L13 before first use"],
               ["two-port data recorded as the line-loss characterization (P1-M-03; validity rule P1-IT-41)"],
               ["cable type, length, connector family (CIF-C01), power capability range"]),
    "RF-L07": (["vacuum leak check; two-port S-parameters at 13.56 MHz with RF-L13"],
               ["enters the P1-M-03 line / match-loss characterization"],
               ["voltage / current capability ranges; flange family (CIF-C02); RF insulation data (ICD ICP-44 OPEN)"]),
    "RF-L08": (["return loss at 13.56 MHz; power capability not less than the selected generator option (rule)"],
               ["13.56 MHz impedance record (certificate or RF-L13 measurement)"],
               ["power capability range; cooling needs"]),
    "RF-L09": (["calorimetric cross-check against RF-L02 / RF-L03 at the labelled boundaries (H4-RFQ2-06; agreement "
                "factor per P1-IT-24)"],
               ["calorimeter flow and temperature channels traceable (RFQ2-THRUST-N04)"],
               ["calorimetric method and uncertainty budget; 50-ohm return loss"]),
    "RF-L10": (["functional test of each feature (A9.2 rf_protection); thresholds set after characterization"],
               ["reflected-power trip reading checked against RF-L03"],
               ["adjustable range of each threshold; interlock I/O list (ICD ICP-16)"]),
    "RF-L11": (["accuracy verification against its certificate on delivery"],
               ["certificate with uncertainty and coverage factor (MS-G-01..03)"],
               ["wiring configurations for the generator mains input; data interface (CIF-T01)"]),
    "RF-L12": ([P2_ACC, "phase verification traceable through RF-L13 / RF-L14 (P2 calibration plan)"],
               ["13.56 MHz V, I and phase calibration; accredited scope or in-house VNA-traceable procedure TBD_OWNER "
                "(P2Q-07)"],
               ["V / I / phase uncertainty, mounting and vacuum / thermal compatibility (P2 INS-P2-01)"]),
    "RF-L13": ([P2_ACC], ["calibration certificate of the analyser (MS-G-01..03)"],
               ["frequency span, port power / input protection, receiver / spectrum mode yes/no (P2 INS-P2-04)"]),
    "RF-L14": ([P2_ACC], ["standard-definition data of every standard; fixture-standard characterization"],
               ["connector family; fixture standards for the antenna terminal (P2 INS-P2-05)"]),
    "RF-L15": ([P2_ACC], ["13.56 MHz S-parameter data per attenuator"],
               ["attenuation values and power capability (P2 INS-P2-06)"]),
    "RF-L16": ([P2_ACC], ["VNA-measured impedance record at 13.56 MHz (never taken from the analog)"],
               ["impedance and power capability (P2 INS-P2-07 (b))"]),
    "RF-L17": ([P2_ACC], ["phase stability versus flexure / temperature data"],
               ["cable type, length, connector family (P2 INS-P2-08)"]),
    "RF-L18": ([P2_ACC], ["13.56 MHz transfer-impedance / sensitivity certificate"],
               ["current range and mounting (P2 INS-P2-09)"]),
    "RF-L19": (["position repeatability demonstrated over the element travel"],
               ["n/a - position read-out; resolution stated (P2 INS-P2-12)"],
               ["resolution and interface to the DAQ (match_setting_id, P1-M-09)"]),
    "RF-O01": (["frequency and harmonic readings verified against RF-L13 where both exist"],
               ["calibration certificate (MS-G-01..03)"], ["frequency span and dynamic range"]),
    # ---- GAS
    "GAS-L01": (["rate-of-rise / transfer verification with GAS-L17 (A9.3 OQ-RFQ-02)"],
                ["maker's Ar-specific certificate; accredited certificate TBD_OWNER (OQ-RFQV2-01)"],
                ["full-scale range, accuracy, sccm reference conditions (CIF-U02), Ar calibration basis"]),
    "GAS-O01": (["as GAS-L01 (only if the second range is taken)"], ["as GAS-L01"],
                ["overlap with GAS-L01 range stated"]),
    "GAS-L07": (["helium leak test record; open / close function"], [NA_CAL],
                ["valve type, seat material, leak rate, fitting family (CIF-C03)"]),
    "GAS-L12": (["gauges cross-checked at a common pressure"],
                ["Ar calibration or gas-correction basis with uncertainty (A9.1 UBQ-08)"],
                ["range, gauge type, placement per H26-30"]),
    "GAS-L13": (["~1 kV DC representative-pressure / gas withstand record (Ar for P1): flashover, leakage, breakdown, "
                 "surface tracking (row 105)"],
                ["test-voltage and leakage instruments traceable"],
                ["350 V continuous rating; geometry; p d range (H23-27, H23-29)"]),
    "GAS-L14": (["~1 kV DC representative-gas withstand record, only for a line that bridges isolated potentials "
                 "(A9.3 ICPQ-06); none for the capped G-REUSE port"],
                ["test-voltage and leakage instruments traceable"], ["geometry and rating per bridged potential"]),
    "GAS-L16": (["certificate per device and gas present before the first P1 run"],
                ["own-gas certificates; NABL / ISO-17025 for score-bearing N2 / O2 / Xe (row 126); Ar via rate-of-rise / "
                 "transfer (A9.3 OQ-RFQ-02)"],
                ["certificate list per device"]),
    "GAS-L17": (["volume determination record with uncertainty"],
                ["reference-transducer certificate (MS-G-01..03)"],
                ["volume, transducer range, temperature sensing; UB-F-07 contribution"]),
    # ---- VAC
    "VAC-L01": (["fit check against the facility port drawings"], [NA_CAL], ["flange family per port (CIF-C02); drawings"]),
    "VAC-L02": (["base pressure and Ar throughput at the P1 flow recorded (no acceptance number set here)"],
                ["pressure read by Ar-calibrated gauges (GAS-L12)"], ["Ar pumping speed, base pressure, interface flange"]),
    "VAC-L03": (["vacuum leak check; DWV 1.05 kV DC / 60 s record for ICP body / collector assemblies where ratings "
                 "permit (A9.4 P1Q-14)"],
                ["DWV and leakage instruments traceable"],
                ["current (>= 8.33 A) and voltage rating per pin; rated withstand per assembly"]),
    "VAC-L04": (["helium leak check"], [NA_CAL], ["fitting family (CIF-C03); O2 cleaning where O2 later passes (row 107)"]),
    "VAC-L05": (["mass-scale and Ar sensitivity check"], ["Ar-specific sensitivity calibration (A9.1 UBQ-08)"],
                ["mass range ~200 amu, differential pumping, data interface (CIF-T01)"]),
    "VAC-L07": (["line of sight to the ICP source volume verified at installation (A9.4 P2Q-05)"],
                ["transmission-band data"], ["transmission band, flange family, coating protection / replacement"]),
    # ---- HALLEL
    "HE-L01": (["output V / I verified over 0-350 V and to the 8.33 A stand ceiling into a load; floating isolation"],
               ["V / I readback certificate"], ["ratings, isolation, remote-control and interlock I/O"]),
    "HE-L02": (["current regulation verified per coil with 4-wire remote sense"],
               ["current readback certificate (P1-M-24)"], ["current / voltage ratings against MC-1 (TBD); floating output"]),
    "HE-L03": (["rated withstand >= 525 V stated; 1.05 kV DC / 60 s DWV where ratings permit (A9.4 P1Q-14)",
                "signed readback polarity demonstrated"],
               ["V / I readback certificate with calibration, zero/offset, resolution, repeatability (A9.5 P1Q-15)"],
               ["offered bias range (A902-23 TBD); current capability >= 8.33 A"]),
    "HE-L04": (["initial DWV 1.05 kV DC / 60 s of passive insulation paths where ratings permit, leakage recorded "
                "(A9.4 P1Q-14)"],
               ["leakage measurement traceable"], ["rated withstand per item (>= 525 V)"]),
    "HE-L05": (["channel audit (H4-RFQ2-05); RF pickup check RF-on / plasma-off (P1-M-22)"],
               ["certificate with the A9.5 current-channel components"], ["range, bandwidth, isolation"]),
    "HE-L15": (["installation check that the monitor is the only deliberate H-1 body ground path (A9.4 P1Q-13)",
                "signed polarity demonstrated"],
               ["certificate with the A9.5 current-channel components"],
               ["range, resolution, over-range survivability, isolated readout"]),
    "HE-L16": (["input impedance and isolation verified; reading taken with the anode floating"],
               ["divider-ratio certificate"], ["input impedance, isolation voltage, leakage bound"]),
    "HE-L17": (["open-state insulation resistance across the open disconnect recorded; state indication on the DAQ"],
               ["n/a - state device (state input verified in the DAQ channel audit)"],
               ["voltage / current ratings; whether rated for switching under load (supplier states)"]),
    "HE-L18": (["channel audit; RF pickup check"], ["certificate with the A9.5 current-channel components"],
               ["isolation class (CIF-G07); ranges"]),
    "HE-O02": (["output voltage and current limit verified"], ["voltage and leakage-current certificate"],
               ["maximum voltage, current limit, leakage resolution"]),
    # ---- MECH
    "ME-L01": (["dimensional inspection against the LOCK-1 drawings; material certificate"], [NA_CAL],
               ["material and continuous-use temperature with basis (RFQ2-MECH-N04; ICP_COUPLED_THERMAL UNRESOLVED)"]),
    "ME-L02": (["dimensional inspection; cold antenna impedance recorded with RF-L13 after installation (record only)"],
               [NA_CAL], ["conductor material; RF insulation data (ICD ICP-44 OPEN)"]),
    "ME-L03": (["dimensional inspection; material certificate (316L for Ar engineering only)"], [NA_CAL],
               ["material certificate; flight collector material not frozen"]),
    "ME-L05": (["fit check on KC-1 / H-1 mount; modular exchange provision demonstrated"], [NA_CAL],
               ["interface drawing with the ICP_ORIFICED_VARIANT exchange provision"]),
    "ME-L06": (["dimensional inspection; non-ferromagnetic certificate inside the MC-1 exclusion zone (ICD ICP-32)"],
               [NA_CAL], ["surface finish / emittance data where offered (radiative-view objective)"]),
    "ME-L07": (["capped dedicated gas port leak-tight; pressure port present"], [NA_CAL],
               ["MODULE_ID provision; port drawings"]),
    "ME-L08": (["fit check with RF-L04"], [NA_CAL], ["mounting drawing"]),
    "ME-O01": (["dimensional inspection; isolation per CIF-G07 where ratings permit"], [NA_CAL],
               ["material certificate; position-datum drawing"]),
    # ---- THRUST / METROLOGY
    "TH-L04": (["channel audit against RFQ2-THRUST-N01 / N05 and ICD ICP-34 (H4-RFQ2-05)"],
               ["per-channel certificate (MS-G-01..03)"],
               ["channel count, sample rate, isolation, common time-base synchronization (INS-18)"]),
    "TH-L05": (["continuity and room-temperature check"], ["sensor certificates (INS-17)"],
               ["type, range, vacuum compatibility; recorded only (ICP_COUPLED_THERMAL UNRESOLVED)"]),
    "TH-L06": (["certificate validity of each reference"], ["reference-standard certificates"], ["reference list"]),
    "TH-L07": (["dark offset recorded; saturation / over-range indication demonstrated (A9.4 P2Q-05); no threshold set"],
               ["maker's spectral-response / responsivity data (no threshold)"],
               ["spectral response, dark current / noise, linear range, saturation level, gain / bandwidth"]),
    "TH-L08": (["channel on the common time base; saturation flag recorded"], ["channel certificate"],
               ["input range and sample rate"]),
    "TH-L09": (["certificates delivered before the first P1 run"], ["MS-G-01..03 per instrument"],
               ["certificate list per instrument with the A9.5 components for current channels"]),
}


def attach_quote_sheets(items: dict, reqs: list) -> None:
    """Per-line quote sheet: specification rows derived from the line's requirements (value / TBD + freeze gate),
    acceptance, calibration/traceability and documentation. P1_NEEDED lines must carry explicit entries."""
    by = {r["id"]: r for r in reqs}
    by.update({r["v1_id"]: r for r in reqs if r["v1_id"]})
    order = {f: i for i, f in enumerate(FREEZE_POINTS)}
    known = set()
    for pk, lits in items.items():
        for li in lits:
            known.add(li["id"])
            spec = []
            for rid in li["requirements"]:
                r = by[rid]
                spec.append({"requirement": r["id"], "v1_id": r["v1_id"], "title": r["title"], "value": r["value"],
                             "units": r["units"], "freeze_point": r["freeze_point"], "status": r["status"]})
            gate = max((s_["freeze_point"] for s_ in spec), key=lambda f: order[f]) if spec else None
            qa = LINE_QA.get(li["id"])
            if li["dispatch"] == "P1_NEEDED":
                if qa is None or not all(qa):
                    raise ValueError(f"P1_NEEDED line {li['id']} lacks acceptance / calibration / documentation")
                if not spec:
                    raise ValueError(f"P1_NEEDED line {li['id']} has no specification requirement")
            li["quote_sheet"] = {
                "spec": spec, "freeze_gate": gate,
                "acceptance": list(qa[0]) if qa else ["package-level acceptance list (carried v1)"],
                "calibration_traceability": list(qa[1]) if qa else ["package-level calibration list (carried v1)"],
                "documentation": list(qa[2]) if qa else ["package-level documentation list (carried v1)"],
                "send_state": ("READY_TO_SEND_FOR_QUOTATION (owner / procurement; A9.4); purchase order NOT authorized"
                               if li["dispatch"] == "P1_NEEDED" else
                               "LATER (sent with the later campaign set); purchase order NOT authorized"),
            }
    stale = set(LINE_QA) - known
    if stale:
        raise KeyError(f"quote sheets for unknown lines: {sorted(stale)}")


# ------------------------------------------------------------------ instrument coverage cross-check (A9.6 sec. 13)
NOT_PROCURED = {
    "NP-FACILITY": {"disposition": "FACILITY_PROVIDED_NOT_PROCURED",
                    "why": "the P1 chamber is the identified domestic engineering chamber (row 139); its interfaces and "
                           "any missing pumping are RFQ lines VAC-L01 / VAC-L02 (OQ-RFQV2-02 open)"},
    "NP-H1-BUILD": {"disposition": "NOT_PROCURED_IN_THIS_RFQ_REVISION",
                    "why": "H-1 (H2-1 CI H-1, MC-1) and its Ar gas path / anode plenum (H2-3) are H-1 design / build "
                           "items outside the six owner RFQ families; procurement route TBD_OWNER (OQ-RFQV2-10; NIR-06)"},
}

# P1 measurement id -> RFQ lines (or a NOT_PROCURED key)
P1_MEAS_COVERAGE = {
    "P1-M-01": ["RF-L02", "RF-L03"], "P1-M-02": ["RF-L02", "RF-L03"],
    "P1-M-03": ["RF-L13", "RF-L14", "RF-L17", "RF-L08", "RF-L09"], "P1-M-04": ["RF-L09"], "P1-M-05": ["RF-L11"],
    "P1-M-06": ["RF-O01", "RF-L13"], "P1-M-07": ["RF-L18"], "P1-M-08": ["RF-L13", "RF-L12", "RF-L14"],
    "P1-M-09": ["RF-L19", "RF-L04", "TH-L04"], "P1-M-10": ["HE-L03", "HE-L05"], "P1-M-11": ["HE-L05", "HE-L03"],
    "P1-M-12": ["HE-L18"], "P1-M-13": ["HE-L15"], "P1-M-14": ["HE-L05", "HE-L01"], "P1-M-15": ["HE-L16"],
    "P1-M-16": ["GAS-L12"], "P1-M-17": ["GAS-L12", "ME-L07"], "P1-M-18": ["GAS-L01", "GAS-O01"],
    "P1-M-19": ["GAS-O02"], "P1-M-20": ["VAC-L05"], "P1-M-21": ["TH-L05"], "P1-M-22": ["TH-L04", "HE-L05"],
    "P1-M-23": ["TH-L04"], "P1-M-24": ["HE-L02", "TH-L04"], "P1-M-25": ["RF-L10", "TH-L04"], "P1-M-26": ["TH-L04"],
    "P1-M-27": ["HE-L18", "ME-O01"], "P1-M-28": ["TH-L07", "TH-L08", "VAC-L07"], "P1-M-29": ["HE-L15"],
}
P1_HW_COVERAGE = {
    "P1-HW-01": ["RF-L01"], "P1-HW-02": ["RF-L02", "RF-L03"], "P1-HW-03": ["RF-L04", "ME-L08", "RF-L19"],
    "P1-HW-04": ["RF-L05", "RF-L07"], "P1-HW-05": ["RF-L08", "RF-L09"], "P1-HW-06": ["RF-L10"],
    "P1-HW-07": ["RF-L13", "RF-L14", "RF-L15", "RF-L17"], "P1-HW-08": ["RF-L11"], "P1-HW-09": ["GAS-L01", "GAS-O01"],
    "P1-HW-10": ["GAS-L17"], "P1-HW-11": ["GAS-L12"], "P1-HW-12": ["GAS-L13", "GAS-L14"], "P1-HW-13": ["GAS-O02"],
    "P1-HW-14": ["ME-L07"], "P1-HW-15": "NP-H1-BUILD", "P1-HW-16": "NP-FACILITY", "P1-HW-17": ["VAC-L02"],
    "P1-HW-18": ["VAC-L03", "VAC-L04", "RF-L07"], "P1-HW-19": ["VAC-L05"], "P1-HW-20": ["VAC-L07"],
    "P1-HW-21": ["ME-L07", "GAS-L12"], "P1-HW-22": "NP-H1-BUILD", "P1-HW-23": ["HE-L01", "HE-L05"],
    "P1-HW-24": ["HE-L16", "HE-L17"], "P1-HW-25": ["HE-L02"], "P1-HW-26": ["HE-L03"], "P1-HW-27": ["HE-L18", "ME-O01"],
    "P1-HW-28": ["HE-L15"], "P1-HW-29": ["HE-L04"], "P1-HW-30": ["HE-O02"], "P1-HW-31": ["HE-L16"],
    "P1-HW-32": ["HE-L10", "HE-L11", "HE-L12"], "P1-HW-33": ["ME-L01"], "P1-HW-34": ["ME-L02"], "P1-HW-35": ["ME-L03"],
    "P1-HW-36": ["ME-O01"], "P1-HW-37": ["ME-L05"], "P1-HW-38": ["ME-L06"], "P1-HW-39": ["TH-L04"],
    "P1-HW-40": ["TH-L07", "TH-L08"], "P1-HW-41": ["TH-L06", "TH-L09"], "P1-HW-42": ["TH-L01"],
}
P1_HW_NOTES = {
    "P1-HW-32": "C1 stays CONTROL_FALLBACK and LATER; whether C1 hardware must be physically present (disconnected) in "
                "P1-S6 is TBD_OWNER (OQ-RFQV2-09)",
    "P1-HW-42": "thrust stand LATER: not required for P1-S0..S6 (only if P1-S7 is run on the stand)",
}
P2_INS_COVERAGE = {
    "INS-P2-01": ["RF-L12"], "INS-P2-02": ["RF-L02"], "INS-P2-03": ["RF-L03"], "INS-P2-04": ["RF-L13"],
    "INS-P2-05": ["RF-L14"], "INS-P2-06": ["RF-L15"], "INS-P2-07": ["RF-L09", "RF-L16", "RF-L08"],
    "INS-P2-08": ["RF-L17", "RF-L06"], "INS-P2-09": ["RF-L18"], "INS-P2-10": ["TH-L07", "TH-L08", "VAC-L07"],
    "INS-P2-11": ["RF-L11"], "INS-P2-12": ["RF-L19"],
}


def instrument_coverage(pkgs: list) -> dict:
    """Every P1 measurement, P1 hardware item and P2 instrument id of the MERGED P1 / P2 packages maps to RFQ lines or to
    an explicit not-procured disposition; raises on any unmapped, stale or unknown id (fail-closed)."""
    lines = {li["id"]: (p["id"], li) for p in pkgs for li in p["line_items"]}
    p1 = current("P1")
    p2 = current("P2")
    specs = [("p1_measurements", "P1", {m["id"]: m for m in p1["measurements"]}, P1_MEAS_COVERAGE,
              lambda m: m["quantity"], lambda m: m["status"]),
             ("p1_hardware", "P1", {m["id"]: m for m in p1["hardware_readiness"]}, P1_HW_COVERAGE,
              lambda m: m["item"], lambda m: None),
             ("p2_instruments", "P2", {m["id"]: m for m in p2["instrument_list"]}, P2_INS_COVERAGE,
              lambda m: m["name"], lambda m: m["status"])]
    out = {"rule": "every id of the merged P1 measurement list, P1 hardware-readiness list and P2 instrument list maps "
                   "to at least one RFQ v2 line or to an explicit not-procured disposition; a REQUIRED P1 measurement "
                   "maps to at least one P1_NEEDED line (or a not-procured disposition); every P2 preparation "
                   "instrument maps to at least one P1_NEEDED line (A9.3: P2 preparation starts immediately)",
           "inputs": [{"key": k, "path": CURRENT[k], "pinned": False,
                       "note": "read at build time; refined concurrently by the A9.5 / A9.6 P1 and P2 lanes; any id "
                               "change makes this build raise until the map is reconciled"} for k in ("P1", "P2")],
           "not_procured_dispositions": NOT_PROCURED}
    for name, key, src, cov, qf, sf in specs:
        missing = sorted(set(src) - set(cov))
        stale = sorted(set(cov) - set(src))
        if missing or stale:
            raise KeyError(f"{name}: unmapped ids {missing}; mapped ids absent from {CURRENT[key]}: {stale}")
        rows = []
        for iid in sorted(src):
            target = cov[iid]
            row = {"id": iid, "what": qf(src[iid]), "status_in_source": sf(src[iid])}
            if isinstance(target, str):
                if target not in NOT_PROCURED:
                    raise KeyError(f"{iid}: unknown disposition {target}")
                row.update({"rfq_lines": [], "disposition": target})
            else:
                if not target:
                    raise ValueError(f"{iid}: empty line list")
                ls = []
                for lid in target:
                    if lid not in lines:
                        raise KeyError(f"{iid}: unknown RFQ line {lid}")
                    ls.append({"line": lid, "package": lines[lid][0], "dispatch": lines[lid][1]["dispatch"]})
                row.update({"rfq_lines": ls, "disposition": "RFQ_LINE"})
                p1n = any(x["dispatch"] == "P1_NEEDED" for x in ls)
                if name == "p1_measurements" and str(row["status_in_source"]).startswith("REQUIRED") and not p1n:
                    raise ValueError(f"REQUIRED P1 measurement {iid} maps to no P1_NEEDED line")
                if name == "p2_instruments" and not p1n:
                    raise ValueError(f"P2 preparation instrument {iid} maps to no P1_NEEDED line")
            if iid in P1_HW_NOTES:
                row["note"] = P1_HW_NOTES[iid]
            rows.append(row)
        out[name] = rows
    return out


def a96_sec13_items() -> list:
    """Owner item list of A9.6 sec. 13, parsed verbatim ('* <item>;' bullets between 'Include:' and 'Keep:')."""
    lines = load("A96_MD").splitlines()
    start = lines.index("13. Complete RFQ packages")
    inc = lines.index("Include:", start)
    items = []
    for ln in lines[inc + 1:]:
        if ln.startswith("Keep:"):
            break
        if ln.startswith("* "):
            items.append(ln[2:].rstrip().rstrip(";").rstrip("."))
    if not items:
        raise ValueError("A9.6 sec. 13 item list not found")
    return items


A96_SEC13_COVERAGE = {
    "RF generator": ["RF-L01", "RF-L11"],
    "directional coupler": ["RF-L02"],
    "power sensors": ["RF-L03"],
    "local matching components": ["RF-L04", "RF-L19", "ME-L08"],
    "coax/feedthroughs": ["RF-L05", "RF-L06", "RF-L07", "RF-L17", "VAC-L03", "VAC-L04"],
    "photodiode/amplifier": ["TH-L07", "TH-L08", "VAC-L07"],
    "gas MFCs": ["GAS-L01", "GAS-O01", "GAS-L02", "GAS-L03", "GAS-L04", "GAS-L05", "GAS-L06", "GAS-O02"],
    "diagnostics": ["RF-L12", "RF-L13", "RF-L18", "RF-O01", "HE-L05", "HE-L15", "HE-L16", "HE-L18", "GAS-L12",
                    "VAC-L05", "TH-L04", "TH-L05"],
    "collector/bias supply": ["HE-L03"],
    "isolation hardware": ["HE-L04", "HE-L17", "HE-O02", "GAS-L13", "GAS-L14", "GAS-L15", "HE-L13"],
    "mechanical ICP fabrication": ["ME-L01", "ME-L02", "ME-L03", "ME-L05", "ME-L06", "ME-L07", "ME-L08", "ME-O01"],
    "dummy loads": ["RF-L08", "RF-L09", "RF-L16"],
    "calibration items": ["RF-L14", "RF-L15", "GAS-L16", "GAS-L17", "TH-L02", "TH-L06", "TH-L09"],
}


def a96_sec13_coverage(pkgs: list) -> list:
    lines = {li["id"]: (p["id"], li) for p in pkgs for li in p["line_items"]}
    owner = a96_sec13_items()
    if sorted(owner) != sorted(A96_SEC13_COVERAGE):
        raise KeyError(f"A9.6 sec. 13 items {owner} != coverage keys {sorted(A96_SEC13_COVERAGE)}")
    out = []
    for it in owner:
        ls = A96_SEC13_COVERAGE[it]
        for lid in ls:
            if lid not in lines:
                raise KeyError(f"A9.6 sec. 13 '{it}': unknown line {lid}")
        out.append({"owner_item": it, "lines": [{"line": lid, "package": lines[lid][0],
                                                 "dispatch": lines[lid][1]["dispatch"]} for lid in ls],
                    "p1_needed_present": any(lines[lid][1]["dispatch"] == "P1_NEEDED" for lid in ls)})
    return out


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
         "value": "TBD - requires the P1 gas schematic (P1-HW-15, P1-HW-18; registered at P1-G0); O2-wetted fittings "
                  "ASTM G93 Level C, no silver (rows 107, 103)", "status": "TBD", "freeze_point": "P1-G0",
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
        {"id": "CIF-G07", "group": "potentials_grounding", "title": "ICP body / collector isolation class (A9.4 P1Q-14)",
         "value": {"V_operating_max_V": 350.0, "V_design_withstand_min_V": 525.0, "initial_DWV_V_DC": 1050.0,
                   "initial_DWV_duration_s": 60.0,
                   "applies_to": "ICP body / collector circuits vs Hall anode, H-1 body/common, facility ground and "
                                 "other isolated circuits, where those potential differences can physically occur",
                   "rf_insulation_ICP_44": "OPEN (not covered)"},
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.4 P1Q-14; row 81; ICD ICP-23",
         "evidence_class": "owner-stated",
         "note": "the ECSS high-voltage reference is owner-stated without standard / clause (verify); leakage acceptance "
                 "and later reverification level TBD; distinct from CIF-G05 (gas lines, A9.3 ICPQ-06)"},
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
        {"id": "CIF-E03", "group": "electrical", "title": "current sign convention of the ICP-45 network (A9.5 P1Q-15)",
         "value": "conventional current INTO the defined isolated electrical network is positive; every current channel "
                  "is delivered as a signed reading with documented polarity so it can be transformed into this "
                  "convention; no channel is silently set to zero",
         "status": "OWNER_GIVEN", "freeze_point": "NOW", "source": "A9.5 P1Q-15; A9.6 sec. 2",
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
         "RP-RF-50; RP-MAINS", "W; -", "OWNER_GIVEN (quantities); rates TBD at P1-G0 (P1-M-26)", "A9.3 OQ-RFQ-06; ICD ICP-34",
         "P1_NEEDED"),
        ("X-05", "RFQ2-RF", "RFQ2-HALLEL", "RF interlock permissives incl. collector/bias supply state and discharge "
         "supply state", "-", "-", "TBD (trip values from measured S1a behaviour)", "ICD ICP-16; A9.2 rf_protection",
         "P1_NEEDED"),
        ("X-06", "RFQ2-GAS", "RFQ2-VAC", "gas feedthroughs and gauge ports on the chamber", "CIF-C02; CIF-C03",
         "Pa; -", "TBD - P1 gas schematic (P1-HW-18; P1-G0)", "RFQ2-VAC-N04; RFQ2-GAS-N06", "P1_NEEDED"),
        ("X-07", "RFQ2-GAS", "RFQ2-MECH", "capped ICP dedicated gas port and pressure port; isolator only if a line "
         "bridges isolated potentials", "N-BODY; N-FG", "V; Pa", "OWNER_GIVEN (capped port); count TBD at P1-G0 (P1-HW-12)",
         "RFQ-05-R09; A9.3 ICPQ-06, OQ-RFQ-10", "P1_NEEDED"),
        ("X-08", "RFQ2-GAS", "RFQ2-HALLEL", "Hall anode gas isolator between N-FG and N-ANODE", "N-ANODE; N-FG", "V",
         "OWNER_GIVEN (350 V continuous; ~1 kV DC qualification)", "row 105; RFQ2-GAS-N05", "P1_NEEDED"),
        ("X-09", "RFQ2-GAS", "RFQ2-THRUST", "MFC setpoint/readback and gauge signals into the DAQ; harp crossing on "
         "the stand (LATER)", "CIF-T01", "mg/s; Pa", "TBD at P1-G0 (rates; P1-M-26)", "RFQ2-THRUST-N01; row 117", "P1_NEEDED"),
        ("X-10", "RFQ2-HALLEL", "RFQ2-VAC", "electrical feedthroughs for discharge, collector/bias, magnet and sensing",
         "N-ANODE; N-ICPREF; N-FG", "A; V", "OWNER_GIVEN (8.33 A ceiling; 350 V + margin TBD)",
         "A9.3 OQ-A907-02; row 81; RFQ2-VAC-N03", "P1_NEEDED"),
        ("X-11", "RFQ2-HALLEL", "RFQ2-MECH", "collector lead and body-potential sense on the ICP module",
         "N-ICPREF; N-BODY", "A; V", "TBD (collector V/I range A902-23); isolation OWNER_GIVEN (CIF-G07: 350 V class, "
         ">= 525 V design withstand, 1.05 kV DC / 60 s initial DWV; A9.4 P1Q-14)", "ICD ICP-20, ICP-21; A9.4 P1Q-14",
         "P1_NEEDED"),
        ("X-12", "RFQ2-HALLEL", "RFQ2-THRUST", "V_d(t), I_d(t), I_e,ICP(t), potentials into the DAQ; P_bus 1 ms chain "
         "synchronization (LATER)", "CIF-G02; CIF-T01", "V; A", "OWNER_GIVEN (quantities); rates TBD at P1-G0 (P1-M-26)",
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
        ("X-17", "RFQ2-VAC", "RFQ2-THRUST", "photodiode viewport / window line of sight -> photodiode + amplifier -> "
         "DAQ channel (A9.4 P2Q-05)", "CIF-C02; CIF-T01", "V; nm", "OWNER_GIVEN (items); band / gain TBD",
         "A9.4 P2Q-05; RFQ2-VAC-N06; RFQ2-THRUST-N03", "P1_NEEDED"),
        ("X-18", "RFQ2-HALLEL", "RFQ2-VAC", "H-1 body single-point return lead through an electrical feedthrough to the "
         "ground-current monitor; no second grounding path via stand / coax shields / chassis", "N-FG; H-1 body",
         "A", "OWNER_GIVEN (single metered path); ranges TBD (I_scale,min)", "A9.4 P1Q-13; RFQ2-HALLEL-N06",
         "P1_NEEDED"),
        ("X-19", "RFQ2-RF", "RFQ2-THRUST", "V/I probe, antenna current probe, match-position read-out and RF "
         "metrology signals into the DAQ on the common time base", "RP-VI; CIF-T01", "V; A; -",
         "TBD at P1-G0 (rates; P1-M-26)", "P2 INS-P2-01, INS-P2-09, INS-P2-12; RFQ2-THRUST-N05", "P1_NEEDED"),
        ("X-20", "RFQ2-HALLEL", "RFQ2-THRUST", "signed current channels (collector, H-1 body return, ICP body, "
         "facility return), V_anode / V_ref and the anode-disconnect state into the DAQ", "CIF-E03; CIF-T01", "A; V; -",
         "OWNER_GIVEN (sign convention, channels); ranges TBD (I_scale,min)", "A9.5 P1Q-15; A9.4 P1Q-13",
         "P1_NEEDED"),
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
    "RFQ2-VAC": {"documentation": ["feedthrough current (>= 8.33 A stand ceiling) and voltage ratings per pin",
                                   "rated withstand per ICP body / collector feedthrough assembly (>= 525 V) and whether "
                                   "it permits the 1.05 kV DC / 60 s DWV; DWV record or certificate where performed "
                                   "(A9.4 P1Q-14)",
                                   "viewport / window transmission band and flange family (A9.4 P2Q-05)"]},
    "RFQ2-HALLEL": {"acceptance": ["initial DWV record of the ICP body / collector passive insulation paths: 1.05 kV DC, "
                                   "60 s, current-limited, leakage recorded, before first HV/RF operation, where "
                                   "component ratings permit; not repeated before each campaign (A9.4 P1Q-14)"],
                    "documentation": ["current capability of every supply/sensor relative to the 8.33 A stand ceiling "
                                      "(A9.3 OQ-A907-02)",
                                      "rated design withstand (>= 525 V) of each ICP body / collector isolation item "
                                      "(A9.4 P1Q-14)"]},
    "RFQ2-MECH": {"acceptance": ["open-tube coaxial geometry per the LOCK-1 drawings (A9.3 OQ-VI-03)"],
                  "documentation": ["carrier interface drawing showing the modular exchange provision (A9.3 OQ-VI-03)"]},
    "RFQ2-THRUST": {"acceptance": ["DAQ channel audit against RFQ2-THRUST-N01 / ICD ICP-34 before first P1 run",
                                   "photodiode channel check: dark offset recorded and the saturation / over-range "
                                   "indication demonstrated on the DAQ (A9.4 P2Q-05); no threshold set at acceptance"]},
}

COMMON_SUPPLIER_MUST_STATE_V2 = [
    "per line: compliance (COMPLIANT / DEVIATION with justification / NOT OFFERED); option lines quoted separately",
    "per interface id of RFQ2-CIF touched by the quoted item: compliance and the offered connector/flange family",
]


_URL_RE = re.compile(r"https?://[^\s,;)]+")


def reference_provenance(x: dict) -> dict:
    """URL and access date shown for a carried v1 reference entry. The carried v1 fields are kept verbatim; where v1
    recorded '-', the value is taken from the pinned web-track source register (URL extracted from the register's
    citation string, access date from its 'accessed' field). Nothing is invented: absent values stay 'not recorded'."""
    reg = {s_["id"]: (i, s_) for i, s_ in enumerate(load("REG")["sources"])}
    ids = [t.strip() for t in x["source_id"].split(";")]
    url, url_basis = x.get("url"), "v1 reference entry 'url'"
    acc, acc_basis = x.get("accessed"), "v1 reference entry 'accessed'"
    if url in (None, "", "-"):
        found = []
        for sid in ids:
            if sid not in reg:
                raise KeyError(f"reference source {sid} not in the web-track source register")
            i, rs = reg[sid]
            found += [u for u in ([rs["url"]] if rs.get("url") else _URL_RE.findall(rs["citation"])) if u not in found]
        url = " | ".join(found) if found else "not recorded (non-web source: " + x["citation"] + ")"
        url_basis = ("web-track source register " + DELIVERABLES["REG"][0] + "#/sources/"
                     + ",".join(str(reg[sid][0]) for sid in ids) + " (URL taken from the register citation string)")
    if acc in (None, "", "-"):
        dates = []
        for sid in ids:
            d = reg[sid][1].get("accessed")
            if d and d not in dates:
                dates.append(d)
        acc = " | ".join(dates) if dates else "not recorded"
        acc_basis = ("web-track source register " + DELIVERABLES["REG"][0] + "#/sources/"
                     + ",".join(str(reg[sid][0]) for sid in ids) + " 'accessed'")
    return {"url": url, "url_basis": url_basis, "accessed": acc, "accessed_basis": acc_basis,
            "access_mode": x.get("access", "-")}


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
            e["provenance_display"] = reference_provenance(x)
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
        {"id": "CL-12", "change": "A9.4 incorporation: photodiode + amplifier (TH-L07) and DAQ channel (TH-L08) in the "
                                  "thrust/metrology package, optical access / window (VAC-L07) in the vacuum/facility "
                                  "package, all P1_NEEDED; requirements RFQ2-THRUST-N03, RFQ2-VAC-N06; interface X-17",
         "source": "A9.4 P2Q-05"},
        {"id": "CL-13", "change": "A9.4 incorporation: ICP body / collector isolation 350 V class, >= 525 V design "
                                  "withstand, 1.05 kV DC / 60 s initial DWV added to the isolation (HE-L04, "
                                  "RFQ2-HALLEL-N04) and feedthrough (VAC-L03, RFQ2-VAC-N07) lines; CIF-G07; ICP-44 RF "
                                  "insulation stays OPEN", "source": "A9.4 P1Q-14"},
        {"id": "CL-14", "change": "A9.4 incorporation: owner / procurement authorized to SEND the P1_NEEDED packages for "
                                  "quotation (RFQ, clarification, indicative lead time, commercial quotation, datasheets "
                                  "/ certificates); no purchase orders, advance payments or binding commitments; no "
                                  "supplier contact by Claude / the team (banner, dispatch_authority, H3 gate)",
         "source": "A9.4 execution_decisions.p1_needed_rfqs"},
        {"id": "CL-15", "change": "A9.6 RFQ completion: RF metrology lines RF-L12..RF-L19 and option RF-O01 (V/I probe, "
                                  "VNA, calibration kits, attenuators, antenna-simulator load, phase-stable cables, "
                                  "antenna current probe, match-position read-out, frequency / harmonic option), each "
                                  "with the P2 specification rows copied (RFQ2-RF-N07..N17); placement TBD_OWNER (P2Q-02)",
         "source": "A9.6 sec. 13; A9.3 authorizations P2"},
        {"id": "CL-16", "change": "A9.6 RFQ completion: A9.4 P1Q-13 lines HE-L15 (H-1 body single-point metered "
                                  "ground-current monitor + facility return), HE-L16 (high-impedance isolated V_anode / "
                                  "V_ref), HE-L17 (anode physical disconnect), HE-L18 (ICP body and electrode channels); "
                                  "A9.5 closure metrology RFQ2-HALLEL-N08; CIF-E03, X-18..X-20; OQ-RFQV2-07 closed",
         "source": "A9.6 sec. 5, 6, 13; A9.4 P1Q-13; A9.5 P1Q-15"},
        {"id": "CL-17", "change": "A9.6 RFQ completion: collector / bias supply HE-L03 carries the 350 V class, >= 525 V "
                                  "design withstand and 1.05 kV / 60 s DWV (RFQ2-HALLEL-N05); DWV tester option HE-O02 "
                                  "(OQ-RFQV2-08 kept open); electron-collecting target option ME-O01 (RFQ2-MECH-N05)",
         "source": "A9.6 sec. 5, 13; A9.4 P1Q-10, P1Q-14"},
        {"id": "CL-18", "change": "A9.6 RFQ completion: calibration items - rate-of-rise / transfer calibration volume "
                                  "GAS-L17 (RFQ2-GAS-N08) and calibration services TH-L09 (RFQ2-THRUST-N04); event / "
                                  "state DAQ inputs RFQ2-THRUST-N05",
         "source": "A9.6 sec. 13"},
        {"id": "CL-19", "change": "A9.6 RFQ completion: RGA line VAC-L05 and RFQ-03 requirements re-tagged LATER -> "
                                  "P1_NEEDED because the merged P1 bench lists the RGA as REQUIRED in P1-S2..S7 "
                                  "(P1-M-20, P1-HW-19); text unchanged",
         "source": "A9.6 sec. 13 (keep P1_NEEDED vs LATER); merged P1 bench"},
        {"id": "CL-20", "change": "A9.6 RFQ completion: per-line quote sheets (specification rows from the line's "
                                  "requirements with value / TBD and freeze gate, acceptance, calibration / traceability, "
                                  "documentation, send state); every P1_NEEDED line carries explicit entries",
         "source": "A9.6 sec. 13 ('ready to send')"},
        {"id": "CL-21", "change": "A9.6 RFQ completion: instrument coverage cross-check - every merged P1 measurement, P1 "
                                  "hardware item and P2 instrument id maps to an RFQ line or an explicit not-procured "
                                  "disposition (facility-provided chamber; H-1 build items NIR-06 / OQ-RFQV2-10)",
         "source": "A9.6 sec. 13; fo_a9_6_rfq_completion"},
        {"id": "CL-22", "change": "A9.6 sec. 3 cleanup: stale 'PENDING <P1 / P2 lane>' references replaced by the merged "
                                  "P1 / P2 ids (values stay TBD, freeze gate P1-G0 where P1 registers them); PENDING is "
                                  "now used only for the A9.6 parallel lanes not in this base (P3, P4, mass/power, Xe)",
         "source": "A9.6 sec. 3"},
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
    ids: dict = {"a9_1": {}, "a9_2": {}, "a9_3": {}, "a9_4": {}, "a9_5": {}, "a9_6": {}}
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
    structural = {"OQ-RFQ-07": set(PKG_IDS) | {"RFQ2-CIF"}}
    a93 = [{"id": k, "status": load("A93")["decisions"][k]["status"], "how_applied": a93_how[k],
            "applied_in": sorted(ids["a9_3"].get(k, set()) | structural.get(k, set()))} for k in a93_how]
    a94_doc = load("A94")
    a94_how = {
        "P2Q-05": "photodiode + amplifier + DAQ channel (TH-L07, TH-L08; RFQ2-THRUST-N03) and optical access / window "
                  "(VAC-L07; RFQ2-VAC-N06) added as P1_NEEDED lines; RFQ2-THRUST-N01 channel list extended; X-17",
        "P1Q-14": "RFQ2-HALLEL-N04, RFQ2-VAC-N07, CIF-G07; HE-L04 and VAC-L03 carry the >= 525 V design withstand and "
                  "the 1.05 kV DC / 60 s initial DWV; ICP-44 RF insulation OPEN",
        "p1_needed_rfqs": "P1_NEEDED packages may be sent for quotation by the owner / procurement (banner, "
                          "dispatch_authority.a9_4_quotation_dispatch, H3 gate); no PO / advance payment / binding "
                          "commitment; no supplier contact by Claude / the team",
        "P1Q-13": "A9.6 RFQ completion: H-1 body single-point metered ground-current monitor (HE-L15, "
                  "RFQ2-HALLEL-N06), high-impedance isolated V_anode / V_ref channel (HE-L16) and anode physical "
                  "disconnect means (HE-L17, RFQ2-HALLEL-N07); CIF X-18; closes OQ-RFQV2-07",
        "P1Q-10": "A9.6 RFQ completion: dedicated, isolated, instrumented electron-collecting electrode as option line "
                  "ME-O01 (RFQ2-MECH-N05) and its channels HE-L18",
    }
    structural_94 = {"p1_needed_rfqs": set(PKG_IDS) | {"RFQ2-CIF"}}
    a94 = []
    for k, how in a94_how.items():
        src = a94_doc["decisions"].get(k) or {"status": "AUTHORIZED (execution decision)"}
        a94.append({"id": k, "status": src.get("status", "AUTHORIZED (execution decision)"), "how_applied": how,
                    "applied_in": sorted(ids["a9_4"].get(k, set()) | structural_94.get(k, set())),
                    "path": DECISIONS["A94"][0], "sha256": DECISIONS["A94"][1]})
    a95 = [{"id": k, "status": load("A95")["decisions"][k].get("status", "OWNER_DECIDED"),
            "how_applied": how, "applied_in": sorted(ids["a9_5"].get(k, set())),
            "path": DECISIONS["A95"][0], "sha256": DECISIONS["A95"][1]} for k, how in (
        ("P1Q-15", "per-channel uncertainty components, signed readings, I_scale,min registration input and the "
                   "sign convention requested from suppliers (RFQ2-HALLEL-N08, CIF-E03, X-20); certificates with the "
                   "components (RFQ2-THRUST-N04)"),
        ("P1Q-16", "no RFQ line: the signed capacity formula is applied by the P1 reducer; the RFQ requests signed "
                   "bipolar current readings so that no absolute value or clipping is needed (RFQ2-HALLEL-N08)"))]
    a96 = [{"id": "sec. " + k, "how_applied": how, "applied_in": sorted(ids["a9_6"].get(k, set())),
            "path": DECISIONS["A96_MD"][0], "sha256": DECISIONS["A96_MD"][1]} for k, how in (
        ("13", "packages completed for sending: every owner sec. 13 item mapped to lines (a9_6_sec13_coverage); "
               "P1_NEEDED / LATER kept; per-line quote sheets; P1 / P2 instrument coverage cross-check; RFQ only - no "
               "purchase order authorization"),
        ("5", "isolation class, anode disconnect / floating / high-impedance V_anode, single-point metered ground, all "
              "intentional current paths instrumented (RFQ2-HALLEL-N05..N07)"),
        ("2", "I_scale,min registered from the instrumentation capability; no default (RFQ2-HALLEL-N08)"),
        ("3", "stale 'PENDING <P1 / P2 lane>' references of this package replaced by references to the merged P1 / "
              "P2 ids"),
        ("6", "RFQ line propagation implemented without a new owner question (OQ-RFQV2-07 closed)"))]
    return {"owner_rows": row_list,
            "a9_6": a96,
            "a9_5": a95,
            "a9_4": a94,
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
        {"id": "OQ-RFQV2-06", "question": "A9.4 P1Q-14 sets >= 525 V design withstand and a 1.05 kV DC / 60 s initial "
                                          "DWV for the ICP body / collector circuits. Does the same basis also close the "
                                          "row-81 'transient/qualification margin' (CIF-G04, still TBD) for the H-1 "
                                          "anode / discharge-supply isolation and feedthroughs?",
         "proposed_answer": "owner call; PROPOSED: yes (same 350 V class, same 1.5 x design / ~3 x initial DWV "
                            "basis)", "needed_by": "P1 RFQ dispatch of RFQ2-HALLEL / RFQ2-VAC"},
        {"id": "OQ-RFQV2-08", "question": "Who performs the 1.05 kV DC / 60 s initial DWV (A9.4 P1Q-14): supplier "
                                          "factory test with certificate, the in-house bench with a current-limited "
                                          "tester (not quoted in v2), or both?",
         "proposed_answer": "owner call; PROPOSED: supplier certificate where the item rating permits plus the in-house "
                            "bench DWV of the assembled insulation configuration before first HV/RF operation",
         "needed_by": "P1 RFQ dispatch of RFQ2-HALLEL / RFQ2-VAC"},
        {"id": "OQ-RFQV2-09", "question": "The merged P1 bench (P1-HW-32) has C1 present on its own module but "
                                          "DISCONNECTED in P1-S6. Must C1 hardware (HE-L10 cathode, HE-L11 heater supply, "
                                          "HE-L12 keeper supply; LATER) be advanced to P1_NEEDED for that, or may P1-S6 "
                                          "run with C1 absent (trivially supplying no electrons)?",
         "proposed_answer": "owner call; both admissible outcomes kept (C1 lines stay LATER until answered)",
         "needed_by": "P1-S6 preparation (dispatch of RFQ2-HALLEL C1 lines)"},
        {"id": "OQ-RFQV2-10", "question": "H-1 (H2-1 CI H-1 with MC-1) and its Ar gas path / anode plenum (H2-3) are "
                                          "needed from P1-S3 (P1-HW-15, P1-HW-22) but belong to none of the six owner RFQ "
                                          "families. Issue a separate H-1 fabrication RFQ, extend RFQ2-MECH, or "
                                          "fabricate in-house?",
         "proposed_answer": "owner call; no route selected (NIR-06)",
         "needed_by": "before P1-S3"},
    ]
    closed = [
        {"id": "OQ-RFQV2-07", "state": "CLOSED_BY_A9_6_MECHANICAL_PROPAGATION",
         "how": "A9.6 sec. 6 lists RFQ line propagation as automatic; the A9.4 P1Q-13 monitor and V_anode channel are "
                "explicit P1_NEEDED lines HE-L15 / HE-L16 / HE-L17 (RFQ2-HALLEL-N06, N07). Using existing laboratory "
                "instruments that meet these lines instead of sending them remains the owner's dispatch choice.",
         "source": "A9.6 sec. 6 and sec. 13; A9.4 P1Q-13"},
    ]
    carried_from_lanes = [
        {"id": "P2Q-02", "lane_file": P2_JSON, "state": "OPEN (P2 preparation package)",
         "handling": "RF-metrology lines RF-L12..RF-L19 and RF-O01 carry placement TBD_OWNER with both alternatives "
                     "(RFQ2-RF / separate RF-metrology package); not answered here"},
        {"id": "P2Q-07", "lane_file": P2_JSON, "state": "OPEN (P2 preparation package)",
         "handling": "RF-L12 calibration route: accredited scope or in-house VNA-traceable procedure TBD_OWNER; not "
                     "answered here"},
    ]
    return {"new": new, "closed_since_previous_revision": closed, "carried_open_from_lanes": carried_from_lanes,
            "carried_open_from_v1": carried, "v1_questions_answered_since": answered,
            "state_file": DELIVERABLES["OQS3"][0], "state_sha256": DELIVERABLES["OQS3"][1],
            "rule": "no OPEN owner question of state v3 is answered by this lane"}


def interface_demands() -> list:
    return [
        {"id": "IFD-01", "from": "P1 bench " + P1_JSON + " (merged)", "to": "RFQ2-GAS, RFQ2-VAC, RFQ2-HALLEL, "
                                                                          "RFQ2-THRUST",
         "quantity": "Ar sweep bounds (F2); gas schematic (P1-HW-12, P1-HW-15, P1-HW-18); gauge ranges (P1-M-16/17); DAQ "
                     "sample rate / bandwidth (P1-M-26); magnet states (F6); P1-S4 topology (P1-IT-36); I_scale,min "
                     "(A9.5)", "units": "sccm; Pa; Sa/s; A",
         "status": "OPEN - values TBD at P1-G0 (ids referenced; nothing filled)"},
        {"id": "IFD-02", "from": "RFQ2-RF, RFQ2-GAS, RFQ2-HALLEL, RFQ2-THRUST (quotations)", "to": "P1 bench " + P1_JSON,
         "quantity": "offered capability ranges, calibration uncertainties (A9.5 components), interfaces",
         "units": "W; mg/s; A; -", "status": "OPEN (after quotations)"},
        {"id": "IFD-03", "from": "P2 prep " + P2_JSON + " (merged)", "to": "RFQ2-RF",
         "quantity": "instrument specifications INS-P2-01..12 (copied into RFQ2-RF-N07..N16); package placement P2Q-02",
         "units": "-", "status": "COPIED (P2 lane refines concurrently; placement TBD_OWNER P2Q-02)"},
        {"id": "IFD-13", "from": "RFQ v2 instrument_coverage", "to": "P1 bench and P2 prep packages (their "
                                                                   "rfq_v2_package / rfq_v2_line fields)",
         "quantity": "RFQ v2 line id per P1 measurement, P1 hardware item and P2 instrument (replaces their stale pending "
                     "reference to this package)", "units": "-",
         "status": "OFFERED (reconciled by the A9.5 / A9.6 P1 and P2 lanes and the consolidated integration pass)"},
        {"id": "IFD-14", "from": "RFQ2-* (supplier datasheets: masses, input powers)",
         "to": "PENDING " + PARALLEL_LANES["MASS_POWER"], "quantity": "quoted masses and input powers of "
                                                                     "flight-representative options",
         "units": "kg; W", "status": "OPEN (after quotations; nothing read from the lane)"},
        {"id": "IFD-15", "from": "RFQ2-GAS GAS-O02 (if ever activated) and the C1 Xe lines (LATER)",
         "to": "PENDING " + PARALLEL_LANES["XE_ACCOUNTING"], "quantity": "mdot_ICP,dedicated (0 in G-REUSE); C1 Xe "
                                                                        "controller ranges", "units": "mg/s",
         "status": "RULE (G-REUSE books 0; nothing read from the lane)"},
        {"id": "IFD-16", "from": "RFQ2-MECH (ICP material continuous-use temperature data, RFQ2-MECH-N04)",
         "to": "PENDING " + PARALLEL_LANES["P3"], "quantity": "material limits for the coupled thermal framework",
         "units": "K", "status": "OPEN (ICP_COUPLED_THERMAL UNRESOLVED; never PASS)"},
        {"id": "IFD-17", "from": "PENDING " + PARALLEL_LANES["P4"], "to": "RFQ2-MECH (ME-L03, ME-L04, ME-O01)",
         "quantity": "collector / electrode candidate materials (no anode RFQ: FINAL_ANODE_MATERIAL OPEN)", "units": "-",
         "status": "PENDING (nothing read from the lane)"},
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
        (12, "RFQ2-HALLEL, RFQ2-RF", "laboratory discharge/magnet/collector supplies (P1), H-1 body ground-current "
                                     "monitor, V_anode channel and anode disconnect (A9.4 P1Q-13; P1), breadboard "
                                     "supplies (LATER), laboratory RF generator (P1, ground only)"),
        (13, "RFQ2-MECH", "ICP material temperature data; ICP_COUPLED_THERMAL stays UNRESOLVED (no PASS); coupled "
                          "thermal framework PENDING docs/experiments/hall_icp/p3_coupled_thermal/"),
        (15, "RFQ2-GAS, RFQ2-THRUST, RFQ2-VAC, RFQ2-RF", "P1 DAQ incl. event / state inputs, gauges, Ar MFC and "
                                                         "calibration volume, RF metrology (V/I probe, VNA, kits, "
                                                         "current probe; placement P2Q-02), power analyzer, "
                                                         "photodiode + amplifier + DAQ channel and its optical access "
                                                         "(A9.4 P2Q-05), RGA, calibration services (P1); stand "
                                                         "(LATER)"),
        (16, "RFQ2-MECH, RFQ2-THRUST", "modular ICP carrier and supports (P1); stand/KC-1 (LATER)"),
        (18, "RFQ2-MECH, RFQ2-HALLEL, RFQ2-GAS", "open-tube coaxial ICP head parts, collector/bias supply, capped port "
                                                "(P1)"),
        (19, "RFQ2-RF", "development RF chain with local match (P1, ground only); the flight DC-input RF source is not "
                        "in this revision (NIR-01); ratings TBD_AFTER_IMPEDANCE_MAP"),
        (20, "none", "no anode RFQ (A9.2 ANODE_BASELINE OPEN; NIR-03); materials framework PENDING "
                     "docs/experiments/hall_icp/p4_anode_materials/"),
        (21, "none", "no anode heat-path RFQ (design blocker)"),
    ]
    out = []
    for row, pk, how in spec:
        r = rows[row]
        status = ("NO_RFQ (design blocker; A9.2)" if pk == "none" else
                  "RFQ_V2_SPEC_READY_QUOTATION_ONLY (P1_NEEDED subset authorized by A9.4 to be sent for quotation by "
                  "the owner / procurement; no purchase order, advance payment or binding commitment; H3 gate)")
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
        "h3_procurement_gate": {"state": "QUOTATION PACKAGES v2 READY FOR OWNER DISPATCH (P1 subset first); P1_NEEDED "
                                         "PACKAGES AUTHORIZED FOR QUOTATION DISPATCH BY THE OWNER / PROCUREMENT (A9.4); "
                                         "PURCHASE ORDERS, ADVANCE PAYMENTS AND BINDING COMMITMENTS NOT AUTHORIZED",
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
            {"id": "H4-RFQ2-07", "test": "initial DWV 1.05 kV DC / 60 s of ICP body / collector passive insulation paths "
                                         "and feedthrough assemblies before first HV/RF operation (where ratings permit)",
             "source": "A9.4 P1Q-14"},
            {"id": "H4-RFQ2-08", "test": "photodiode dark offset, line of sight and saturation indication on the DAQ",
             "source": "A9.4 P2Q-05"},
            {"id": "H4-RFQ2-09", "test": "single-path check of the H-1 body ground (monitor is the only deliberate path) "
                                         "and anode open-state / V_anode channel verification before the first "
                                         "ICP45_CAPACITY block", "source": "A9.4 P1Q-13"},
            {"id": "H4-RFQ2-10", "test": "per-channel uncertainty components (calibration, zero/offset, resolution, "
                                         "repeatability, RF pickup) of every ICP-45 current channel on file, so that "
                                         "I_scale,min can be registered; no tolerance is widened",
             "source": "A9.5 P1Q-15"},
            {"id": "H4-RFQ2-11", "test": "RF metrology incoming verification: VNA with kit, attenuators, V/I probe phase, "
                                         "antenna-simulator load impedance record (P2 calibration plan)",
             "source": "A9.3 authorizations P2; P2 prep package"},
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
            "web-track source register (docs/procurement/web_track_v1/source_register_v1.json, pinned by sha256): "
            "URL and access date only, for carried reference entries whose v1 record holds '-' (basis per entry in "
            "provenance_display); no datum is taken from it",
            "v1 do-not-purchase banner wording (extended by the A9.3 dispatch statement)",
            "the verified RFQ v2 (fo_a9_rfq_v2_split + fo_a9_4_incorporation) as the base of the A9.6 completion: every "
            "earlier id kept; additions and re-tags recorded in change_log CL-15..CL-22",
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
    reqs = carried_requirements() + new_requirements() + a96_requirements()
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
    attach_quote_sheets(items, reqs)
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
        "status": "COMPLETED_FOR_OWNER_DISPATCH_QUOTATION_ONLY (A9.6 sec. 13; consolidated verification pending)",
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
            "a9_4_quotation_dispatch": {
                "authorized": ["requests for quotation", "technical clarification", "indicative lead time",
                               "commercial quotation", "datasheets/certificates"],
                "not_authorized": ["purchase orders", "advance payments", "binding commitments"],
                "scope": "packages / lines tagged P1_NEEDED; packages stay split by speciality",
                "sent_by": "owner / procurement (P9E/Vyovrinda); Claude / the technical team never contacts suppliers",
                "sources": [A94("p1_needed_rfqs", "The P1-needed RFQ packages may now be sent to suppliers for "
                                                  "quotation."),
                            A94("p1_needed_rfqs", "It does not authorize:"),
                            A94("p1_needed_rfqs", "Supplier packages may remain split by speciality as already "
                                                  "decided.")]},
        },
        "a9_6_completion": {
            "follow_on": "fo_a9_6_rfq_completion", "lane": "A9_6_RFQ", "base_commit": A96_BASE,
            "directive": {"path": DECISIONS["A96_MD"][0], "sha256": DECISIONS["A96_MD"][1],
                          "json": DECISIONS["A96"][0], "json_sha256": DECISIONS["A96"][1]},
            "a9_5": {"path": DECISIONS["A95_MD"][0], "sha256": DECISIONS["A95_MD"][1]},
            "rule": "implementation-first (A9.6): packages completed for sending; verification deferred to the "
                    "consolidated campaign; earlier ids kept, additions and re-tags in change_log CL-15..CL-22",
            "rfq_only_quote": A96("13", "RFQ only — no purchase order authorization"),
            "ready_to_send_quote": A96("13", "Finish all quotation packages so they are ready to send."),
            "p1_later_quote": A96("13", "`P1_NEEDED`"),
        },
        "decision_pins": [{"key": k, "path": v[0], "sha256": v[1], "immutable": True} for k, v in DECISIONS.items()],
        "deliverable_pins": [{"key": k, "path": v[0], "sha256": v[1]} for k, v in DELIVERABLES.items()],
        "never_pinned": NEVER_PINNED,
        "a9_4_incorporation": {
            "follow_on": "fo_a9_4_incorporation", "trigger": "T_A9_4_INCORPORATION", "base_commit": A94_INC_BASE,
            "decision": {"path": DECISIONS["A94"][0], "sha256": DECISIONS["A94"][1]},
            "verbatim": {"path": DECISIONS["A94_MD"][0], "sha256": DECISIONS["A94_MD"][1]},
            "rule": "applied mechanically (owner step 2): only what A9.4 decides changed; ids and verified content "
                    "otherwise kept",
            "applied": ["P2Q-05 (photodiode, optical access / window, amplifier, DAQ channel)",
                        "P1Q-14 (>= 525 V design withstand; 1.05 kV DC / 60 s initial DWV on isolation / feedthrough "
                        "lines)", "execution_decisions.p1_needed_rfqs (P1_NEEDED quotation dispatch)"],
            "placement": "photodiode + amplifier + DAQ channel -> RFQ2-THRUST (owner family 'DAQ'; an optical, non-RF "
                         "diagnostic that must stay independent of the RF impedance chain); optical access / window -> "
                         "RFQ2-VAC (owner family 'RGA/diagnostic interfaces': a chamber port item)"},
        "pending_parallel_lanes": {**PARALLEL_LANES,
                                   "rule": "A9.6 parallel lanes not in this base: referenced as PENDING <path> only; "
                                           "nothing is read from them"},
        "merged_lanes_read": {"P1": P1_JSON, "P2": P2_JSON,
                              "rule": "read (ids, statuses, P2 instrument specifications) but not pinned: refined "
                                      "concurrently by the A9.5 / A9.6 lanes; the instrument-coverage cross-check raises "
                                      "on any id drift"},
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
        "a9_6_sec13_coverage": a96_sec13_coverage(pkgs),
        "instrument_coverage": instrument_coverage(pkgs),
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
            "no_open_owner_question_answered": "genuinely open questions (OQ-RFQV2-01..06, 08..10; P2Q-02, P2Q-07; "
                                               "v1 carried) stay TBD_OWNER with their admissible alternatives",
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
             ("requirements", lambda x: ", ".join(x["requirements"])),
             ("freeze gate", lambda x: x["quote_sheet"]["freeze_gate"]), ("v1", lambda x: x["v1_ref"]),
             ("change", lambda x: x["change"]["type"])]


def render_quote_sheets(p: dict) -> list:
    out = ["", "## Line quote sheets (A9.6 sec. 13: ready to send; RFQ only - no purchase order authorization)", ""]
    for li in p["line_items"]:
        qs = li["quote_sheet"]
        out.append(f"### {li['id']} - {li['item']}")
        out.append("")
        out.append(f"- dispatch: {li['dispatch']}" + (" (OPTION LINE)" if li["option_line"] else "") +
                   f"; quantity: {_fmt(li['qty'])}; freeze gate: {_fmt(qs['freeze_gate'])}; {qs['send_state']}")
        if li.get("placement"):
            pl = li["placement"]
            out.append(f"- package placement {pl['status']} ({pl['question']}): alternatives "
                       f"{' | '.join(pl['alternatives'])}; {pl['rule']}")
        out.append("- specification (from the line's requirements; values, TBD and freeze gates as recorded):")
        for sp in qs["spec"]:
            out.append(f"  - {sp['requirement']}" + (f" ({sp['v1_id']})" if sp["v1_id"] else "") +
                       f" {sp['title']}: {_fmt(sp['value'])} [{_fmt(sp['units'])}]; freeze {sp['freeze_point']}; "
                       f"status {sp['status']}")
        if not qs["spec"]:
            out.append("  - (no requirement attached; LATER line carried from v1)")
        for fld, head in (("acceptance", "acceptance"), ("calibration_traceability", "calibration / traceability"),
                          ("documentation", "documentation")):
            out.append(f"- {head}: " + "; ".join(qs[fld]))
        out.append("")
    return out


def _fmt_datum(v) -> str:
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False, sort_keys=True) + "`"
    return str(v).replace("|", "/")


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
    L_ += render_quote_sheets(p)
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
            pv = x["provenance_display"]
            L_.append(f"- {x['source_id']}: {_fmt_datum(x['datum'])} - {x['note']}. Source: {x['citation']}; "
                      f"URL {pv['url']}; accessed {pv['accessed']}; access: {pv['access_mode']}. Recorded at "
                      f"`{x['path']}#{x['pointer']}` _({x['carried_from']})_.")
        L_.append("")
        L_.append("Reference data are not requirements, not a selection and not a supplier ranking. Where v1 recorded "
                  "no URL/access date, they are taken from the pinned web-track source register (basis recorded per "
                  "entry in the JSON as provenance_display).")
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
                              ("units", lambda x: x.get("units", "in value keys / text")),
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
    inc = d["a9_4_incorporation"]
    L_ += ["", f"A9.4 incorporation ({inc['follow_on']}, trigger {inc['trigger']}, base `{inc['base_commit']}`): "
               f"{inc['rule']}. Applied: {'; '.join(inc['applied'])}. Placement: {inc['placement']}."]
    qd = d["dispatch_authority"]["a9_4_quotation_dispatch"]
    L_ += ["", f"A9.4 quotation dispatch: authorized - {', '.join(qd['authorized'])}; NOT authorized - "
               f"{', '.join(qd['not_authorized'])}; scope {qd['scope']}; sent by {qd['sent_by']}."]
    c6 = d["a9_6_completion"]
    L_ += ["", f"A9.6 completion ({c6['follow_on']}, base `{c6['base_commit']}`; directive `{c6['directive']['path']}` "
               f"sha256 `{c6['directive']['sha256']}`): {c6['rule']}. Owner: \"{c6['rfq_only_quote']['quote']}\"."]
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
    L_ += ["", "## A9.6 sec. 13 owner items -> lines", ""]
    L_ += _table(d["a9_6_sec13_coverage"], [("owner item (verbatim)", lambda x: x["owner_item"]),
                                           ("lines", lambda x: ", ".join(f"{y['line']} ({y['dispatch']})"
                                                                         for y in x["lines"]))])
    ic_ = d["instrument_coverage"]
    L_ += ["", "## P1 / P2 instrument coverage cross-check", "", ic_["rule"] + ".", ""]
    for inp in ic_["inputs"]:
        L_.append(f"- input {inp['key']}: `{inp['path']}` (pinned: {inp['pinned']}; {inp['note']})")
    for k, v in ic_["not_procured_dispositions"].items():
        L_.append(f"- {k}: {v['disposition']} - {v['why']}")
    for sec, head in (("p1_measurements", "P1 measurements"), ("p1_hardware", "P1 hardware readiness"),
                      ("p2_instruments", "P2 instruments")):
        L_ += ["", f"### {head}", ""]
        L_ += _table(ic_[sec], [("id", lambda x: x["id"]), ("what", lambda x: x["what"]),
                                ("status in source", lambda x: x["status_in_source"]),
                                ("RFQ lines / disposition",
                                 lambda x: ", ".join(f"{y['line']} ({y['package']}, {y['dispatch']})"
                                                     for y in x["rfq_lines"]) or x["disposition"]),
                                ("note", lambda x: x.get("note", ""))])
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
    L_ += ["", "## (c) Owner answers applied", "", "### A9.6 (" + d["a9_6_completion"]["directive"]["path"] + ")", ""]
    L_ += _table(oa["a9_6"], [("id", lambda x: x["id"]), ("how applied", lambda x: x["how_applied"]),
                              ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "### A9.5 (" + d["a9_6_completion"]["a9_5"]["path"] + ")", ""]
    L_ += _table(oa["a9_5"], [("id", lambda x: x["id"]), ("status", lambda x: x["status"]),
                              ("how applied", lambda x: x["how_applied"]),
                              ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "### A9.4 (" + d["a9_4_incorporation"]["decision"]["path"] +
           ", sha256 `" + d["a9_4_incorporation"]["decision"]["sha256"] + "`)", ""]
    L_ += _table(oa["a9_4"], [("id", lambda x: x["id"]), ("status", lambda x: x["status"]),
                              ("how applied", lambda x: x["how_applied"]),
                              ("applied in", lambda x: ", ".join(x["applied_in"]))])
    L_ += ["", "### A9.3", ""]
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
    L_ += ["", "Closed since the previous revision:"]
    L_ += [f"- {x['id']}: {x['state']} - {x['how']}" for x in oq["closed_since_previous_revision"]]
    L_ += ["", "Carried OPEN from the P1 / P2 lanes (TBD_OWNER; not answered here):"]
    L_ += [f"- {x['id']} ({x['state']}): {x['handling']}" for x in oq["carried_open_from_lanes"]]
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
