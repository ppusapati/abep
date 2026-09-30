#!/usr/bin/env python3
"""Deterministic builder of the A9 RFQ / quotation specification packages (fo_a9_09_rfq_packages, trigger T_A9_09_RFQ_PACKAGES).

Writes
  docs/procurement/rfq_a9/rfq_a9_v1.json              (machine-readable packages + traceability matrix)
  docs/procurement/rfq_a9/RFQ_A9.md                   (companion document, rendered from the same data)
  docs/procurement/rfq_a9/packages/RFQ-NN_<slug>.md    (one sendable specification per item family, same data)

Authority
  * A9 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json) and the owner's 147 answers
    (docs/decisions/OD_2026_09_29_owner_answers_147.json + verbatim pack) - cited by row number;
  * A9.1 follow-up owner decisions (docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json + verbatim .md) - cited
    by decision id. A9.1 authorizes RFQs/quotations and does NOT authorize purchase orders; interfaces and the H3
    procurement gate control purchases. Every package therefore carries a DO-NOT-PURCHASE banner.
  All five files are pinned by sha256 below; the build refuses to run if any changed.

Rules implemented here
  * every owner-given value is cited by row / A9.1 id and the quoted words are checked verbatim against the decision file;
  * every value copied from a verified deliverable is read from that file at build time (never retyped) and the file's
    sha256 is recorded;
  * catalogue/datasheet data appear only as REFERENCE data read from the web-track source register (URL + access date as
    recorded there); no supplier is ranked, contacted or selected, and no price is written anywhere;
  * computed values are deterministic arithmetic on cited inputs (evidence class model-derived);
  * values owned by parallel A9 lanes (A9-06 mass, A9-07 H2 revisions, A9-08 Xe ledger update) are written
    'PENDING <lane path>' and never filled; nothing is read from them;
  * no Hall transport closure, screening candidate, superseded 0-D Hall model or withdrawn number is read; nothing here
    predicts thrust, efficiency, discharge current, neutralizer electron current or plasma state;
  * missing inputs raise (CLAUDE.md rule 3).

Usage
  python docs/procurement/rfq_a9/build_rfq_a9.py          # write all outputs
  python docs/procurement/rfq_a9/build_rfq_a9.py --check  # exit 1 if any output differs from a fresh build

Standard library only. Pure (reads repository files, writes only its own outputs); not wired into archengine.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ---- A9-10 reconciliation overlay (fo_a9_10_integration): declared, machine-checked changes applied after the build
import importlib.util as _a910_ilu  # noqa: E402
_A910_SPEC = _a910_ilu.spec_from_file_location(
    "a9_10_overlay", str(ROOT) + "/docs/experiments/hall_icp/integration/a9_10_overlay.py")
A910 = _a910_ilu.module_from_spec(_A910_SPEC)
_A910_SPEC.loader.exec_module(A910)

LANE_DIR = "docs/procurement/rfq_a9"
OUT_JSON = LANE_DIR + "/rfq_a9_v1.json"
OUT_MD = LANE_DIR + "/RFQ_A9.md"
PKG_DIR = LANE_DIR + "/packages"
THIS_SCRIPT = LANE_DIR + "/build_rfq_a9.py"
TEST = "tests/test_rfq_a9.py"
BASE_COMMIT = "2625fe567b48c581232bbaf33a057f352f6963e6"

CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
BOTH = list(CONFIGURATIONS)
C1 = ["hall_c1_reference"]
ICP = ["hall_icp_neutralizer"]
OUTCOME_VOCABULARY = ("hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE")
STATUS_NOT_OUTCOME = ("OPEN",)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
STATUSES = ("OWNER_GIVEN", "COPIED_VERIFIED", "DERIVED", "PROPOSED", "TBD", "PENDING", "REFERENCE_ONLY")
TBD = "TBD - requires"
PENDING = "PENDING "
PURCHASE_GATE = "H3 procurement gate + frozen A9 interfaces (owner row 8; A9.1 'A9-09 procurement restriction')"
BANNER = ("DO NOT PURCHASE - QUOTATION / SPECIFICATION ONLY. A9.1 authorizes RFQs/quotations; purchase orders are NOT "
          "authorized by this package or by the closure of the RFQ lane. Interfaces and the H3 procurement gate control "
          "purchases (owner row 8; A9.1 A9-09 procurement restriction). This package is dispatched, if at all, by the owner; "
          "the repository lane never contacts a supplier.")

# ----------------------------------------------------------------------------------------------------------------------
# pinned inputs
# ----------------------------------------------------------------------------------------------------------------------
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


def _xe_budget_json() -> str:
    """The verified (A6) Xe ledger JSON under docs/budgets/ (the un-suffixed lane dir; parallel '_a9' drafts excluded)."""
    hits = sorted(os.path.relpath(p, ROOT).replace(os.sep, "/")
                  for p in glob.glob(os.path.join(ROOT, "docs", "budgets", "xe_*", "*_v1.json"))
                  if not os.path.basename(os.path.dirname(p)).endswith("_a9"))
    if len(hits) != 1:
        raise FileNotFoundError(f"expected exactly one verified Xe ledger JSON under docs/budgets/, found {hits}")
    return hits[0]


# Verified deliverables read by this lane (sha256 recorded at build time). Mutable governance files are NOT pinned.
DELIVERABLES = {
    "ICD": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "BUS": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "UB": "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
    "PRE": "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "EVI": "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
    "VIN": "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
    "INT": "docs/experiments/hall_icp/integration/a9_core_integration_v1.json",
    "H22": "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
    "H23": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
    "H24": "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
    "H26": "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
    "H27": "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
    "INS": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
    "MS": "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
    "CD": "docs/experiments/capability_demo/capability_demo_prep_v1.json",
    "M16": "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
    "XE": None,  # resolved by _xe_budget_json()
    "R4": "docs/procurement/web_track_v1/threads/R4_instrumentation.json",
    "R5": "docs/procurement/web_track_v1/threads/R5_facilities.json",
    "R6": "docs/procurement/web_track_v1/threads/R6_xe_inputs.json",
    "R7": "docs/procurement/web_track_v1/threads/R7_thrust_stand.json",
    "REG": "docs/procurement/web_track_v1/source_register_v1.json",
}
NEVER_PINNED = [
    "docs/orchestration/lane_registry_v1.json",
    "docs/orchestration/trigger_registry_v1.json",
    "docs/orchestration/trigger_ledger_v2.jsonl (and fired_triggers.jsonl)",
    "docs/orchestration/runtime_state.json",
]
# Historical artifacts: read for structure only, never edited, not used for the primary line.
HISTORICAL = {
    "PIM_MD": "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md",
    "PIM_JSON": "schemas/interfaces/preionizer_module_icd_v1.json",
    "P1F": "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
    "LOCK1": "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json",
    "ARCHB": "abep_sim/arch_boundary.py",
}
# Parallel A9 lanes (NOT in the base commit): PENDING only, nothing read.
LANE_PATHS = LANE_DIR + "/rfq_a9_lane_paths_v1.json"
with open(os.path.join(ROOT, LANE_PATHS), encoding="utf-8") as _f:
    A9_PARALLEL = dict(json.load(_f)["pending_parallel_lanes"])
if sorted(A9_PARALLEL) != ["A9-06", "A9-07", "A9-08"]:
    raise RuntimeError("lane-path file must list exactly A9-06, A9-07, A9-08")
A9_MERGED = {
    "A9-01": "docs/experiments/hall_icp/prereg_framework/",
    "A9-02": "docs/architecture_comparison/power_boundary_a9/ + abep_sim/bus_boundary_a9.py",
    "A9-03": "docs/interfaces/icp_neutralizer/ + schemas/interfaces/icp_neutralizer_icd_v1.json",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/",
    "A9-05": "docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/",
}
M16_ROWS_TOUCHED = (6, 7, 8, 11, 12, 13, 15, 16, 17)


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
            _CACHE[rel] = json.load(f) if rel.endswith(".json") else f.read()
    return _CACHE[rel]


def dpath(key: str) -> str:
    if key == "XE":
        return _xe_budget_json()
    if key in DELIVERABLES:
        return DELIVERABLES[key]
    raise KeyError(f"unknown deliverable key {key!r}")


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer; raises on a dangling pointer."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        elif isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(f"pointer {pointer!r}: key {tok!r} not found")
            cur = cur[tok]
        else:
            raise KeyError(f"pointer {pointer!r}: cannot descend")
    return cur


def find_id(doc, ident: str, keys=("id", "slot"), must_have: str | None = None):
    """Exactly one dict in the document whose id (or slot) equals ident (and, if given, carries the field must_have);
    returns (json pointer, dict)."""
    hits = []

    def walk(node, ptr):
        if isinstance(node, dict):
            if any(node.get(k) == ident for k in keys) and (must_have is None or must_have in node):
                hits.append((ptr, node))
            for k, v in node.items():
                walk(v, ptr + "/" + str(k).replace("~", "~0").replace("/", "~1"))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{ptr}/{i}")

    walk(doc, "")
    if len(hits) != 1:
        raise KeyError(f"expected exactly one entry with id {ident!r}, found {len(hits)}")
    return hits[0]


def check_decisions() -> list:
    pins = []
    for key, (rel, expected) in DECISIONS.items():
        got = sha256_of(rel)
        if got != expected:
            raise RuntimeError(f"immutable decision {rel} changed: sha256 {got} != pinned {expected}")
        pins.append({"key": key, "path": rel, "sha256": got, "immutable": True})
    a91 = load(DECISIONS["A91"][0])
    if a91["verbatim"]["sha256"] != DECISIONS["A91_MD"][1]:
        raise RuntimeError("A9.1 JSON does not reference the pinned verbatim record")
    return pins


_ANSWERS: dict = {}


def answers() -> dict:
    if not _ANSWERS:
        for a in load(DECISIONS["ANS"][0])["answers"]:
            _ANSWERS[a["row"]] = a
        if len(_ANSWERS) != 147:
            raise RuntimeError("owner answers file does not hold 147 rows")
    return _ANSWERS


def _ans_sha(row: int) -> str:
    return hashlib.sha256(answers()[row]["owner_answer_verbatim"].encode("utf-8")).hexdigest()


def OW(row: int, quote: str) -> dict:
    """Owner answer row citation; the quote must occur verbatim in the recorded answer."""
    a = answers().get(row)
    if a is None:
        raise KeyError(f"owner row {row} not found")
    if quote not in a["owner_answer_verbatim"]:
        raise ValueError(f"row {row}: quote not verbatim: {quote!r}")
    return {"type": "owner_row", "row": row, "covers_ids": a["covers_ids"], "quote": quote,
            "answer_sha256": _ans_sha(row), "path": DECISIONS["ANS"][0]}


def A91(ident: str, quote: str) -> dict:
    """A9.1 decision citation; id must exist in the JSON record, quote must occur verbatim in the verbatim .md."""
    rec = load(DECISIONS["A91"][0])
    ids = set(rec["decisions"]) | {"A9-09"}
    if ident not in ids:
        raise KeyError(f"A9.1 decision id {ident!r} not found")
    if ident == "A9-09" and "A9-09" not in rec["execution"]["step_2_parallel"]:
        raise KeyError("A9.1 execution step 2 does not list A9-09")
    md = load(DECISIONS["A91_MD"][0])
    if quote not in md:
        raise ValueError(f"A9.1 {ident}: quote not verbatim: {quote!r}")
    return {"type": "a9_1", "id": ident, "quote": quote, "path": DECISIONS["A91_MD"][0]}


def IT(key: str, ident: str, field: str | None = None, root: str = "") -> tuple:
    """Deliverable item citation (by id, searched below the JSON pointer root); returns (source dict, copied field value
    or the item)."""
    rel = dpath(key)
    ptr, node = find_id(resolve(load(rel), root), ident, must_have=field)
    ptr = root + ptr
    val = node if field is None else node[field]
    return {"type": "deliverable_item", "key": key, "path": rel, "id": ident, "pointer": ptr}, val


def DOC(key: str, pointer: str = "") -> tuple:
    rel = dpath(key)
    val = resolve(load(rel), pointer)
    return {"type": "deliverable", "key": key, "path": rel, "pointer": pointer}, val


def PEND(lane: str, what: str) -> str:
    return f"PENDING {A9_PARALLEL[lane]} ({lane}: {what})"


def src_only(t: tuple) -> dict:
    return t[0]


# ----------------------------------------------------------------------------------------------------------------------
# reference catalogue / published data (web-track register; reference only, never a selection)
# ----------------------------------------------------------------------------------------------------------------------
def _thread_source(thread: str, source_id: str) -> dict:
    tdoc = load(dpath(thread))
    for s in tdoc["source_register"]:
        if s["id"] == source_id:
            return s
    raise KeyError(f"{thread}: source {source_id} not in the thread register")


def CAT(thread: str, pointer: str, note: str, source_id: str | None = None) -> dict:
    """Reference datum read from a web-track thread at a JSON pointer, with the thread's own source record."""
    rel = dpath(thread)
    val = resolve(load(rel), pointer)
    sid = source_id or (val.get("source_id") if isinstance(val, dict) else None)
    if sid is None:
        raise KeyError(f"{thread}{pointer}: no source_id")
    srcs = [_thread_source(thread, x.strip()) for x in sid.split(";")]

    def cat(field_names):
        vals = []
        for s in srcs:
            v = next((s.get(f) for f in field_names if s.get(f)), None)
            vals.append(str(v) if v is not None else "-")
        return " | ".join(vals)

    return {
        "thread": thread, "path": rel, "pointer": pointer, "datum": val, "source_id": sid,
        "citation": cat(("citation", "description")),
        "url": cat(("url", "url_or_path")),
        "accessed": cat(("accessed",)),
        "access": cat(("access", "access_level")),
        "use": "REFERENCE ONLY - published/catalogue datum as recorded by the web track; not a requirement, not a "
               "selection, not a supplier ranking, not Vyovrinda performance",
        "note": note,
    }


# ----------------------------------------------------------------------------------------------------------------------
# requirement records
# ----------------------------------------------------------------------------------------------------------------------
def R(rid: str, title: str, requirement: str, value, units: str, basis: str, sources: list, evidence_class,
      status: str, freeze_point: str, applies_to=None, note: str | None = None) -> dict:
    return {"id": rid, "title": title, "requirement": requirement, "value": value, "units": units, "basis": basis,
            "sources": sources, "evidence_class": evidence_class, "status": status, "freeze_point": freeze_point,
            "applies_to": applies_to if applies_to is not None else BOTH, "note": note}


def is_open(value) -> bool:
    return isinstance(value, str) and (value.startswith(TBD) or value.startswith(PENDING))


# ----------------------------------------------------------------------------------------------------------------------
# derived arithmetic (deterministic, cited inputs)
# ----------------------------------------------------------------------------------------------------------------------
G_N = 9.80665  # standard acceleration of gravity, conventional value (3rd CGPM 1901; verify against the BIPM SI Brochure)


def derived() -> dict:
    out = {}
    # thrust: 1 % (k = 1) at the 12 mN acceptance point; calibration masses equivalent to 12 and 25 mN at g_n
    ub_t01 = IT("UB", "UB-T-01", "value")[1]
    ub_t02 = IT("UB", "UB-T-02", "value")[1]
    OW(27, "25 mN")
    out["u_T_standard_at_acceptance_point_mN"] = {
        "value": round(ub_t01 / 100.0 * ub_t02, 6), "units": "mN (k = 1)",
        "formula": "u_T = 0.01 x 12 mN (UB-T-01 x UB-T-02; row 121, UBQ-01)", "evidence_class": "model-derived"}
    out["calibration_mass_equivalent_g"] = {
        "value": {f"{F:g} mN": round(F * 1e-3 / G_N * 1e3, 6) for F in (ub_t02, 25.0)}, "units": "g",
        "formula": "m = F / g_n with g_n = 9.80665 m s^-2 (conventional; verify)", "evidence_class": "model-derived",
        "note": "context for the calibration-mass set of RFQ-01; 25 mN from rows 4/27"}
    # P_bus 1 ms window
    A91("OQ-A902-01", "sample rate \u2265100 kSa/s")
    fs = 100e3
    out["samples_per_1ms_window_at_min_rate"] = {
        "value": int(round(fs * 1e-3)), "units": "samples",
        "formula": "100 kSa/s x 1 ms (A9.1 OQ-A902-01)", "evidence_class": "model-derived"}
    out["nyquist_at_min_rate_kHz"] = {
        "value": fs / 2 / 1e3, "units": "kHz",
        "formula": "100 kSa/s / 2; consistency with the >= 20 kHz effective bandwidth (A9.1 OQ-A902-01)",
        "evidence_class": "model-derived"}
    # keeper isolation basis check (owner numbers verified verbatim in the A9.1 record)
    A91("ICP-46", "upper operating pulse: 600 V;")
    A91("ICP-46", "minimum design isolation basis: 900 V (1.5\u00d7 upper operating pulse);")
    out["keeper_isolation_basis_ratio"] = {
        "value": round(900.0 / 600.0, 6), "units": "-",
        "formula": "900 V / 600 V (A9.1 ICP-46: '1.5x upper operating pulse')", "evidence_class": "model-derived"}
    # MFC ranges: per-range span needed for 4 ranges vs the PROPOSED 20 % FS floor
    n2 = IT("H26", "H26-18", "value")[1]
    o2 = IT("H26", "H26-19", "value")[1]
    minfrac = IT("CD", "CD-P-MFC-MINFRAC", "value", root="/proposed_thresholds")[1]
    OW(73, "from ~0.38 mg/s through ~3.2 mg/s")  # verifies the owner words behind the two numbers below
    lo73, hi73 = 0.38, 3.2  # row 73 operability/thermal characterization envelope (owner words '~0.38' .. '~3.2' mg/s)
    per = {}
    for name, lo, hi in (("N2 (H26-18)", n2["min_mgps"], n2["max_mgps"]), ("O2 (H26-19)", o2["min_mgps"], o2["max_mgps"]),
                         ("atmospheric total, row 73 envelope", lo73, hi73)):
        per[name] = {"min_mgps": lo, "max_mgps": hi, "turndown": round(hi / lo, 6),
                     "per_range_span_for_4_ranges": round((hi / lo) ** 0.25, 6),
                     "fits_20pct_floor": (hi / lo) ** 0.25 <= 1.0 / minfrac}
    out["mfc_four_range_check"] = {
        "value": per, "units": "-",
        "formula": "span per range = turndown^(1/4) for 4 geometrically spaced overlapping ranges; floor 1/CD-P-MFC-MINFRAC",
        "evidence_class": "model-derived",
        "note": "CD-P-MFC-MINFRAC = %s is PROPOSED (not owner-given); the final full-scale ladder freezes with the LOCK-1 "
                "condition grid (row 31)" % minfrac}
    # C1 Xe controllers in sccm (MFC reference conventions differ: supplier must name its own)
    conv = DOC("R4", "/unit_conversions/mg_s_per_sccm/Xe")[1]
    out["c1_xe_points_sccm"] = {
        "value": {f"{m:g} mg/s": round(m / conv, 4) for m in (0.0005, 0.005, 0.05, 0.2, 0.6, 0.8)},
        "units": "sccm Xe (0 degC, 101325 Pa basis of the R4 conversion)",
        "formula": "sccm = (mg/s) / %s (R4 unit_conversions, MKS gas density basis)" % conv, "evidence_class": "model-derived"}
    OW(92, "ADOPT 0.005 mg/s flow-step resolution")
    OW(98, "ADOPT resolution \u22640.0005 mg/s")
    out["c1_resolution_vs_search_step"] = {
        "value": round(0.005 / 0.0005, 6), "units": "steps of resolution per search step",
        "formula": "row 92 step 0.005 mg/s / row 98 resolution 0.0005 mg/s", "evidence_class": "model-derived"}
    # Xe tank indicative internal volume (propellant only) at 323.15 K from the NIST reference EOS values recorded in R6
    r6 = load(dpath("R6"))
    idx = [i for i, h in enumerate(r6["hardware_mass_data"]) if h["item"] == "Xe density (supercritical)"]
    if len(idx) != 1:
        raise KeyError("R6: Xe density entry not unique")
    rho = r6["hardware_mass_data"][idx[0]]["values"]["323.15K"]
    vols = {}
    OW(48, "Run explicit 2 kg / 5 kg / 10 kg design cases")
    for m in (2.0, 5.0, 10.0):
        vols[f"{m:g} kg"] = {p: round(m / rho[p], 4) for p in sorted(rho)}
    out["xe_tank_indicative_volume_L"] = {
        "value": vols, "units": "L (= kg / (g cm^-3))",
        "formula": "V = m_case / rho(323.15 K, p); rho from R6 /hardware_mass_data[%d] (NIST WebBook SRD 69)" % idx[0],
        "evidence_class": "model-derived",
        "note": "propellant volume only: excludes the 2 % residual (row 45), the 20 % reserve (row 43), ullage, MEOP and "
                "safety factors (row 50) - final tank ranges PENDING " + A9_PARALLEL["A9-08"] + " (A9-08)"}
    # bus-slot channel counts per configuration from the A9-02 slot list
    slots = load(dpath("BUS"))["slots"]
    counts = {}
    for c in CONFIGURATIONS:
        counts[c] = {"INSTALLED": sorted(s["slot"] for s in slots if s["configurations"][c] == "INSTALLED"),
                     "VARIANT_ONLY": sorted(s["slot"] for s in slots if s["configurations"][c] == "VARIANT_ONLY")}
        counts[c]["n_installed"] = len(counts[c]["INSTALLED"])
    out["p_bus_channel_slots"] = {
        "value": counts, "units": "bus slots (one synchronized V and I channel pair each)",
        "formula": "slots with status INSTALLED / VARIANT_ONLY in bus_power_boundary_a9_v1.json", "evidence_class": "model-derived"}
    return out


# ----------------------------------------------------------------------------------------------------------------------
# packages
# ----------------------------------------------------------------------------------------------------------------------
def pkg_thrust_stand(D) -> dict:
    t00s, t00 = IT("UB", "UB-T-00", "value")
    t01s, t01 = IT("UB", "UB-T-01", "value")
    t02s, t02 = IT("UB", "UB-T-02", "value")
    t03s, t03 = IT("UB", "UB-T-03", "value")
    reqs = [
        R("RFQ-01-R01", "measurement principle", "Torsional thrust balance (baseline). An alternate principle is quotable only "
          "if it meets the same uncertainty, payload, thermal/RF service-line and reinstallation requirements.", t00, "-",
          "owner answer", [OW(115, "TORSIONAL baseline. An alternate stand is allowed only if it meets the same uncertainty, "
                                  "payload, thermal/RF service-line and reinstallation requirements."), t00s],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R02", "procurement path", "Dual path: quote critical parts (and design support) for an in-house engineering "
          "torsional stand for development/S1a; a complete stand is quotable only as an open-design, fully documented unit "
          "with raw-data access (no black box). Independent score-bearing measurements use a qualified partner/facility "
          "(RFQ-09).", "dual path", "-", "owner answer",
          [OW(118, "DUAL PATH"), OW(118, "Do not depend on a single purchased black-box stand.")], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R03", "moving payload capacity (minimum)", "Design for at least this moving payload; the actual configuration "
          "spread (H-1 + MC-1 + C1 reference module or ICP module or sham on KC-1, with on-platform services) is "
          "characterized. If the flight-representative test article exceeds it, the stand is uprated/requalified before "
          "procurement (no hardware trimming to fit).", t03, "kg", "owner answer; copied from A9-04 UB-T-03",
          [OW(116, "Design for at least 25 kg moving payload"), t03s], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R04", "mass per configuration on the platform", "Supplier designs to R03; the per-configuration mass and CG "
          "enter at LOCK-1 (ICD ICP-08).", PEND("A9-06", "module masses and CG per configuration") , "kg",
          "pending lane", [src_only(IT("ICD", "ICP-08"))], None, "PENDING", "LOCK-1"),
        R("RFQ-01-R05", "thrust uncertainty design/acceptance target", "Standard relative uncertainty (k = 1) of a sustained "
          "thrust reading at the acceptance point; absolute PASS/FAIL gates use the preregistered one-sided treatment. Not "
          "a k = 2 expanded value. Revisable only before LOCK-2 from metrology-only calibration evidence, never after "
          "propulsion results.", t01, "% of reading (k = 1)", "owner answer; copied from A9-04 UB-T-01",
          [OW(121, "KEEP 1% as the design/acceptance target for now."),
           A91("UBQ-01", "The 1% thrust target is standard relative uncertainty, k = 1, for a sustained reading."), t01s],
          "owner-allocation", "OWNER_GIVEN", "LOCK-2"),
        R("RFQ-01-R06", "acceptance test point", "Preregistered S1a thrust-uncertainty acceptance test at this thrust with "
          "the maximum representative moving payload and all service lines (live + sham) installed.", t02, "mN",
          "owner answer; copied from A9-04 UB-T-02",
          [OW(120, "preregister the S1a thrust-uncertainty acceptance test at 12 mN with maximum representative moving "
                   "payload and all service lines installed"), t02s], "owner-allocation", "OWNER_GIVEN", "LOCK-1"),
        R("RFQ-01-R07", "standard uncertainty at the acceptance point", "Arithmetic consequence of R05 x R06 for the supplier's "
          "design budget (k = 1).", D["u_T_standard_at_acceptance_point_mN"]["value"], "mN (k = 1)",
          D["u_T_standard_at_acceptance_point_mN"]["formula"], [t01s, t02s], "model-derived", "DERIVED", "LOCK-2"),
        R("RFQ-01-R08", "calibrated span", "Calibrated span must include the 25 mN system-capability point; the span upper "
          "end is fixed at LOCK-2 from measured capability.", ">= 25 (upper end TBD - requires LOCK-2 measured capability)",
          "mN", "owner answers (25 mN capability)",
          [OW(27, "demonstrate 25 mN capability inside the same full spacecraft-DC propulsion boundary with P_bus <1.5 kW"),
           OW(4, "plan for ≥12 mN sustained atmospheric operation"), src_only(IT("H26", "H26-02"))],
          "owner-allocation", "OWNER_GIVEN", "LOCK-2",
          note="H26-02 (25.418 mN, model-derived from the historical A5 framework) is context only"),
        R("RFQ-01-R09", "in-situ SI-traceable force calibration", "In-situ force calibration with SI-traceable masses and/or a "
          "force actuator and measured lever geometry, verified under ISO/IEC 17025 / NABL traceability; calibration before "
          "and after every block with drift and hysteresis recorded.", "in-situ, SI-traceable, pre/post block", "-",
          "owner answer",
          [OW(119, "Use in-situ force calibration with SI-traceable masses/force actuator and lever geometry, verified under "
                   "relevant ISO/IEC 17025/NABL traceability. Calibrate pre/post block and record drift/hysteresis."),
           src_only(IT("UB", "UB-T-04")), src_only(IT("UB", "UB-T-05"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R10", "calibration-shift treatment", "Pre/post calibration shift enters the uncertainty budget and a "
          "block-exclusion rule (rule form LOCK-1, numerical limit LOCK-2 from metrology-only evidence); supplier states "
          "expected shift and hysteresis with evidence.", TBD + " LOCK-2 metrology-only calibration evidence (UBQ-05)", "relative",
          "A9.1", [A91("UBQ-05", "Pre/post calibration shift enters the uncertainty budget and also has a block-exclusion rule."),
                   src_only(IT("UB", "UB-T-07"))], None, "TBD", "LOCK-2"),
        R("RFQ-01-R11", "service-line crossing", "Gas and electrical services cross the moving stage in low-stiffness symmetric "
          "harp/slack loops; RF crosses as flexible coax with matched sham routing; no uncompensated hard RF line across the "
          "moving stage; residual parasitic force characterized. Matched sham lines are present in every compared "
          "configuration.", "harp/slack loops + flexible RF coax + matched shams", "-", "owner answers",
          [OW(117, "Use low-stiffness symmetric harp/slack-loop routing for gas/electrical services and flexible RF coax with "
                   "matched sham routing. Avoid an uncompensated hard RF line across the moving stage; characterize "
                   "residual parasitic force."),
           OW(133, "matched sham service lines in every compared configuration"), src_only(IT("ICD", "ICP-18")),
           src_only(IT("UB", "UB-T-09"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R12", "matching network off the platform", "Baseline: the RF matching network is OFF the moving platform "
          "(flexible matched coax crosses the stage, see RFQ-04); the stand must accept one live and one sham RF coax.",
          "off-platform", "-", "A9.1 clarification",
          [A91("A9-03-matching", "Baseline: off the moving thrust-stand platform."), src_only(IT("ICD", "ICP-13"))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-01-R13", "module-exchange interface", "H-1 stays bolted to the platform; the kinematic carrier KC-1 exchanges the "
          "C1 reference module, the ICP module and the mechanical sham with repeatable datum control; supplier provides the "
          "platform mounting interface for KC-1.", PEND("A9-07", "KC-1 / downstream ICP fixture drawings"), "-",
          "owner answer; pending fixture revision",
          [OW(122, "H-1 remains bolted"), src_only(IT("ICD", "ICP-06"))], None, "PENDING", "LOCK-1"),
        R("RFQ-01-R14", "RF / electrostatic pickup immunity", "Supplier states the displacement-sensor and actuator principle and "
          "its susceptibility to 13.56 MHz fields (0-500 W source, RFQ-04); verified at S1a with the ICP energized and the "
          "Hall off.", TBD + " the S1a RF-pickup check (UB-T-11)", "mN", "A9-04",
          [src_only(IT("UB", "UB-T-11")), OW(72, "13.56 MHz.")], None, "TBD", "LOCK-2"),
        R("RFQ-01-R15", "thermal drift", "Stand thermal control / drift compensation against the combined H-1 + downstream-module "
          "heat load; supplier states the drift model and the thermal provisions.", TBD + " S1b thermal time constants and the "
          "total ICP module heat load (ICD ICP-43)", "mN", "A9-04 / A9-03",
          [src_only(IT("UB", "UB-T-10")), src_only(IT("ICD", "ICP-43"))], None, "TBD", "LOCK-2"),
        R("RFQ-01-R16", "non-ferromagnetic construction near H-1", "No ferromagnetic parts inside the MC-1 exclusion zone "
          "(B(z) traceability).", "non-ferromagnetic in the MC-1 exclusion zone", "-", "A9-03 / H2-6",
          [src_only(IT("ICD", "ICP-32")), src_only(DOC("H26", "/h3_procurement_inputs/0"))], "owner-allocation", "COPIED_VERIFIED",
          "NOW", note="evidence class: requirement copied from the verified ICD/H2-6 text, not a measured property"),
        R("RFQ-01-R17", "read-out resolution and noise floor", "Supplier states resolution and noise at the dwell averaging time.",
          TBD + " S1a noise floor at the dwell averaging time (UB-T-13)", "mN", "A9-04",
          [src_only(IT("UB", "UB-T-13")), src_only(IT("H26", "H26-04"))], None, "TBD", "LOCK-2",
          note="H26-04 derived from the historical A5 framework is context only"),
        R("RFQ-01-R18", "vacuum chamber / facility interface", "Supplier states the chamber interface (footprint, feedthroughs, "
          "leveling, vibration isolation); the S1a chamber is a smaller domestic chamber where appropriate.",
          TBD + " facility identification (row 139; RFQ-09)", "-", "owner answer",
          [OW(139, "use a smaller domestic chamber for engineering-only S1a where appropriate")], None, "TBD", "after-evidence"),
    ]
    return {
        "id": "RFQ-01", "slug": "thrust_stand", "family": "torsional thrust stand or its critical parts",
        "serves": BOTH, "m16_rows": [15, 16],
        "scope": ("Torsional thrust balance for the H-1 + downstream electron-source test article (in-house engineering stand "
                  "per the dual path), or its critical parts: flexure pivots, rotating beam, displacement sensor, in-situ "
                  "calibrator (SI-traceable masses and/or force actuator with measured lever arm), damping, leveling, thermal "
                  "control, service-line harp and the KC-1 platform interface."),
        "quantities": [
            {"item": "critical-part set for one in-house torsional stand (Option A)", "qty": 1, "basis": "row 118"},
            {"item": "complete open-design torsional stand (Option B, comparison quote only)", "qty": "0 or 1 (owner call OQ-RFQ-08)",
             "basis": "row 118 (no single black-box dependence)"},
            {"item": "calibration mass set / force actuator with certificate", "qty": 1, "basis": "row 119"},
            {"item": "spare flexure pivots", "qty": TBD + " owner call (OQ-RFQ-01)", "basis": "-"},
        ],
        "requirements": reqs,
        "acceptance": [
            "S1a preregistered acceptance test at 12 mN with the maximum representative moving payload and all live + sham "
            "lines installed (row 120); pass criterion = standard relative uncertainty <= 1 % (k = 1) (row 121, UBQ-01)",
            "factory/site calibration series with pre/post shift and hysteresis reported with raw data (row 119, UBQ-05)",
            "service-line parasitic force with live and sham lines characterized (row 117, row 133)",
            "the 1 % target is never relaxed after propulsion results (row 121)",
        ],
        "calibration_traceability": [
            "force standard traceable to SI via an ISO/IEC 17025 / NABL-accredited scope covering the measurand (row 119; "
            "metrology spec MS-G-01, MS-G-02)",
            "GUM uncertainty budget with coverage factor stated (MS-G-03); a manufacturer +/-x bound without stated "
            "distribution is treated as rectangular, u = a/sqrt(3) (UBQ-03)",
            "lever-arm ratio measured traceably (UB-T-05)",
        ],
        "documentation": [
            "design drawings and material list (incl. magnetic properties near H-1)",
            "calibration certificates with uncertainty budget, coverage factor and raw calibration data (machine-readable)",
            "drift / hysteresis / thermal characterization report and method",
            "installation, leveling, service-line routing and sham-line instructions",
            "declared susceptibility to 13.56 MHz RF fields and the test method used",
        ],
        "reference_data": [
            CAT("R7", "/designs/1", "thrust-band analog (5-20 mN, 0.9 kg); secondary citation"),
            CAT("R7", "/designs/6", "torsional balance used for a Hall and an ECR thruster (3-20 mN); abstract only"),
            CAT("R7", "/designs/10", "heavy-payload (40 kg) double inverted pendulum with cable harp; facility-declared"),
            CAT("R4", "/items/10/options/3/key_specs/1", "E2 mass MPE as recorded by the metrology spec"),
        ],
    }


def pkg_mfc(D) -> dict:
    f00s, f00 = IT("UB", "UB-F-00", "value")
    f01s, f01 = IT("UB", "UB-F-01", "value")
    f02s, f02 = IT("UB", "UB-F-02", "value")
    f03s, f03 = IT("UB", "UB-F-03", "value")
    f04s, f04 = IT("UB", "UB-F-04", "value")
    f05s, f05 = IT("UB", "UB-F-05", "value")
    n2s, n2 = IT("H26", "H26-18", "value")
    o2s, o2 = IT("H26", "H26-19", "value")
    reqs = [
        R("RFQ-02-R01", "measurement principle (pure-gas paths)", "Thermal mass-flow controllers calibrated on their own gas "
          "(no gas-correction-factor or property-library conversion as the primary score-bearing standard); mixtures are "
          "verified through a traceable transfer / rate-of-rise method.", f00, "-", "owner answer; copied from A9-04 UB-F-00",
          [OW(124, "THERMAL own-gas-calibrated MFCs as the primary pure-gas approach."),
           OW(124, "do not use a property-library DP estimate as the primary score-bearing flow standard"), f00s],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-02-R02", "overlapping ranges per pure-gas path", "Four overlapping full-scale ranges per pure-gas path (N2, O2, "
          "Ar; see OQ-RFQ-02 for Ar).", f01, "ranges", "owner answer; copied from A9-04 UB-F-01",
          [OW(123, "Use 4 overlapping ranges per pure-gas path for quotation/specification; quotations only until H3 approval."),
           f01s], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-02-R03", "N2 path envelope", "Four ranges together cover this envelope (PRELIMINARY, model-derived in H2-6); the "
          "owner's H-1 operability/thermal characterization span is ~0.38-~3.2 mg/s delivered atmospheric flow (row 73).",
          n2, "mg/s", "copied from H2-6 H26-18", [n2s, OW(73, "requiring operability/thermal characterization from ~0.38 mg/s "
                                                              "through ~3.2 mg/s")],
          "model-derived", "COPIED_VERIFIED", "LOCK-1", note="final FS ladder frozen with the LOCK-1 condition grid (row 31)"),
        R("RFQ-02-R04", "O2 path envelope", "Four ranges together cover this envelope (PRELIMINARY, model-derived in H2-6).", o2,
          "mg/s", "copied from H2-6 H26-19", [o2s], "model-derived", "COPIED_VERIFIED", "LOCK-1"),
        R("RFQ-02-R05", "four-range feasibility check", "Arithmetic check that four geometric ranges can hold every point at "
          "or above the PROPOSED 20 % FS floor (CD-P-MFC-MINFRAC, not owner-given).", D["mfc_four_range_check"]["value"], "-",
          D["mfc_four_range_check"]["formula"], [n2s, o2s, src_only(IT("CD", "CD-P-MFC-MINFRAC", root="/proposed_thresholds"))], "model-derived",
          "DERIVED", "LOCK-1"),
        R("RFQ-02-R06", "Ar path (engineering-only HI-AR)", "Ar-specific MFC calibration is required for HI-AR engineering "
          "interpretation; Ar remains engineering-only. Range TBD.", TBD + " the HI-AR flow plan (A9-01 stage HI-AR)",
          "mg/s", "A9.1",
          [A91("UBQ-08", "Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation."),
           OW(36, "Use an Ar engineering-only replication first")], None, "TBD", "LOCK-1",
          note="the Takahashi 2024 Ar flow is analog context only and is not scaled"),
        R("RFQ-02-R07", "Xe anode path for the bounded Xe reference/health check", "Xe reference/health check at the start of "
          "each installation (before N2 and any O2-bearing exposure); range TBD.",
          TBD + " the registered Xe reference/health-check point (A9-01) and " + PEND("A9-08", "XE_REFERENCE term"), "mg/s",
          "A9.1 / owner answer",
          [A91("HIQ-03", "Put the bounded Xe reference/health check at the beginning of the installation"),
           OW(26, "perform a Xe health/reference check and bounded Xe peak points if permitted by the RFP")], None, "TBD",
          "LOCK-1"),
        R("RFQ-02-R08", "C1 steady-flow Xe controller class", "One high-accuracy C1 steady-flow controller of this class.", f02,
          "mg/s", "owner answer; copied from A9-04 UB-F-02",
          [OW(125, "TWO controllers — one high-accuracy 0.05–0.2 mg/s-class C1 steady-flow controller"), f02s],
          "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-02-R09", "C1 low-flow resolution and setpoint", "Readout and setpoint resolution at or below this value; digital "
          "setpoint.", f04, "mg/s", "owner answer; copied from A9-04 UB-F-04",
          [OW(98, "ADOPT resolution ≤0.0005 mg/s and digital setpoint for the low-flow cathode MFC."), f04s],
          "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-02-R10", "C1 spot-mode search step", "The controller must realize the 0.005 mg/s search step (10 resolution steps "
          "per search step).", D["c1_resolution_vs_search_step"]["value"], "resolution steps per search step",
          D["c1_resolution_vs_search_step"]["formula"],
          [OW(92, "ADOPT 0.005 mg/s flow-step resolution"), f04s], "model-derived", "DERIVED", "LOCK-1", applies_to=C1),
        R("RFQ-02-R11", "C1 start/diode-flow controller", "Separate start/diode-flow controller covering this range, if the "
          "0.6-0.8 mg/s start flow is retained (OQ-RFQ-04).", f03, "mg/s", "owner answer; copied from A9-04 UB-F-03",
          [OW(125, "a separate start/diode-flow controller if 0.6–0.8 mg/s is retained"), f03s], "owner-allocation",
          "OWNER_GIVEN", "LOCK-1", applies_to=C1),
        R("RFQ-02-R12", "C1 Xe points in the supplier's units", "Conversion for the supplier; the supplier names its own "
          "reference conditions and sccm convention (real/ideal gas, reference temperature).", D["c1_xe_points_sccm"]["value"],
          D["c1_xe_points_sccm"]["units"], D["c1_xe_points_sccm"]["formula"],
          [src_only(DOC("R4", "/unit_conversions")), src_only(IT("H22", "H3-C1-02"))], "model-derived", "DERIVED", "NOW",
          applies_to=C1),
        R("RFQ-02-R13", "C1 Xe accuracy class carried until S1a", "The conservative +/-2 % FS class is the Xe-ledger basis "
          "until S1a demonstrates a better calibrated class on Xe; the supplier states its Xe-calibrated accuracy at the C1 "
          "range (the RFQ does not accept a GCF-derived Xe statement).", f05, "% FS (+/-)", "owner answer; copied from A9-04 UB-F-05",
          [OW(96, "ACCEPT the conservative ±2% FS class"), f05s], "owner-allocation", "OWNER_GIVEN", "LOCK-2",
          applies_to=C1),
        R("RFQ-02-R14", "installed zero check and body-temperature band", "Each device supports an installed zero check per block "
          "(zero command/readback with upstream isolation) and states its body-temperature band and zero/span temperature "
          "coefficients; a body temperature output or a TC mounting point is provided.", "zero check per block + declared band",
          "-", "owner answer",
          [OW(97, "ADOPT installed zero check per block and a declared MFC body-temperature band."),
           src_only(IT("UB", "UB-F-08")), src_only(IT("UB", "UB-F-09"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-02-R15", "O2 service", "O2-wetted controllers and lines cleaned to ASTM G93 Level C; no silver in O2/AO-wetted "
          "parts; wetted materials and seals declared.", "ASTM G93 Level C; no silver", "-", "owner answers",
          [OW(107, "ADOPT ASTM G93 Level C cleaning for O2 service"),
           OW(103, "exclude silver from oxygen/AO-wetted gas-path parts")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-02-R16", "ICP dedicated gas-port controller (contingency only)", "Primary ICP gas mode is G-REUSE (no dedicated "
          "ICP feed, m_dot_ICP,dedicated = 0); a controller for the capped dedicated port is an OPTIONAL line item for the "
          "G-ATM / G-XE contingency variants only; no dedicated Xe to make the ICP work.",
          TBD + " a declared G-ATM/G-XE variant (ICD ICP-26)", "mg/s", "A9.1",
          [A91("HIQ-06", "The dedicated ICP gas port remains installed and capped so G-ATM and G-XE can be tested as separately "
                         "declared contingency variants."),
           A91("HIQ-06", "No dedicated Xe is introduced merely to make the ICP work."), src_only(IT("ICD", "ICP-26"))],
          None, "TBD", "LOCK-1", applies_to=ICP),
        R("RFQ-02-R17", "vacuum-side construction", "Vacuum-rated outlet, metal seals preferred, helium leak specification stated; "
          "attitude sensitivity stated (installation orientation of the test).", "stated by supplier", "-",
          "copied requirement list of H2-2 H3-C1-02", [src_only(IT("H22", "H3-C1-02"))], "owner-allocation",
          "COPIED_VERIFIED", "NOW", note="evidence class: requirement text copied from the verified H2-2 procurement input"),
        R("RFQ-02-R18", "score-bearing flow reference", "Each controller is delivered with a NABL / ISO-17025 calibration "
          "(primary score-bearing reference); the in-house rate-of-rise system is only a transfer/verification standard.",
          "NABL / ISO-17025 certificate per device and gas", "-", "owner answer",
          [OW(126, "NABL/ISO-17025 calibration is the primary score-bearing reference."),
           OW(126, "The in-house rate-of-rise system is acceptable as a transfer/verification standard"),
           src_only(IT("UB", "UB-F-06")), src_only(IT("UB", "UB-F-07"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
    ]
    return {
        "id": "RFQ-02", "slug": "mass_flow_controllers", "family": "mass-flow controllers (thermal, own-gas-calibrated)",
        "serves": BOTH, "m16_rows": [8, 15],
        "scope": ("Laboratory thermal MFCs for the pure-gas atmospheric-surrogate paths (N2, O2; Ar engineering-only), the Xe "
                  "reference path, and two C1 Xe controllers (steady and start/diode); optional contingency controller for "
                  "the capped ICP gas port. Ground/facility equipment; not flight hardware."),
        "quantities": [
            {"item": "N2 path MFCs (four overlapping ranges)", "qty": 4, "basis": "row 123"},
            {"item": "O2 path MFCs (four overlapping ranges), O2-cleaned", "qty": 4, "basis": "rows 123, 107"},
            {"item": "Ar path MFCs (engineering-only)", "qty": "4 (OQ-RFQ-02)", "basis": "row 123 literal; UBQ-08"},
            {"item": "Xe reference-path MFC(s)", "qty": TBD + " the Xe reference point range (OQ-RFQ-03)", "basis": "HIQ-03; row 26"},
            {"item": "C1 steady-flow Xe controller (0.05-0.2 mg/s class)", "qty": 1, "basis": "row 125"},
            {"item": "C1 start/diode-flow Xe controller (0.6-0.8 mg/s)", "qty": "1 if retained (OQ-RFQ-04)", "basis": "row 125"},
            {"item": "ICP capped-port controller (G-ATM/G-XE contingency)", "qty": "optional (OQ-RFQ-10)", "basis": "HIQ-06"},
        ],
        "requirements": reqs,
        "acceptance": [
            "own-gas calibration certificate per device and per gas at the stated reference conditions (row 124, row 126)",
            "installed zero check demonstrated at the test orientation (row 97)",
            "C1 controller: resolution and digital setpoint demonstrated at <= 0.0005 mg/s steps (row 98)",
            "S1a verification against the in-house rate-of-rise transfer standard (row 126; UB-F-07)",
        ],
        "calibration_traceability": [
            "NABL / ISO-17025 calibration is the primary score-bearing flow reference; the in-house rate-of-rise system is a "
            "transfer/verification standard only (row 126; UB-F-06, UB-F-07)",
            "certificate states the distribution/coverage factor; a bare +/-x bound is treated as rectangular (UBQ-03)",
            "Ar calibration specific to Ar (UBQ-08); Xe calibration on Xe (H2-2 H3-C1-02)",
        ],
        "documentation": [
            "calibration certificates (per gas, per device) with uncertainty budget and raw points",
            "reference conditions / sccm convention named explicitly",
            "zero and span temperature coefficients, attitude sensitivity, body-temperature band",
            "wetted-material and seal list; O2 cleaning certificate (ASTM G93 Level C) where applicable",
            "digital interface description (setpoint/readback resolution)",
        ],
        "reference_data": [
            CAT("R4", "/items/0/options/0/key_specs/0", "thermal MFC accuracy class as recorded"),
            CAT("R4", "/items/0/options/0/key_specs/2", "thermal MFC turndown as recorded"),
            CAT("R4", "/items/0/options/0/key_specs/4", "zero/span temperature sensitivity as recorded"),
            CAT("R4", "/items/1/options/0/key_specs/0", "low-range DP MFC accuracy on a property-library gas (not own-gas)"),
        ],
    }


def pkg_rga(D) -> dict:
    b02s, b02 = IT("UB", "UB-B-02", "value")
    reqs = [
        R("RFQ-03-R01", "mass range", "Approximately 200 amu; 300 amu is not required unless later diagnostics require heavier "
          "species.", b02, "amu", "owner answer; copied from A9-04 UB-B-02",
          [OW(127, "include an approximately 200 amu RGA with differential pumping and species calibration for N2/O2/O-related "
                   "fragments and Xe"),
           OW(127, "300 amu is unnecessary unless later diagnostics require heavier species."), b02s], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        R("RFQ-03-R02", "differential pumping", "Differentially pumped sampling so the analyser operates within its pressure "
          "limit at the facility base pressure and at two elevated background-pressure levels.", "differentially pumped", "-",
          "owner answers", [OW(127, "with differential pumping"), OW(23, "use two elevated background-pressure levels")],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-03-R03", "sampling pressure range", "Inlet pressure span of the sampling system.",
          TBD + " the facility base pressure, the two elevated p_b levels and T-PB-MAX (row 23; UB-B-01)", "Pa",
          "owner answer / A9-04", [OW(23, "Freeze T-PB-MAX only after the low-flow knee and facility capability are known."),
                                   src_only(IT("UB", "UB-B-01"))], None, "TBD", "after-evidence"),
        R("RFQ-03-R04", "species calibration", "Species calibration for N2, O2, O-related fragments and Xe; Ar-specific "
          "calibration for HI-AR engineering interpretation; supplier states the calibration method and the gas sensitivity "
          "factors basis.", "N2, O2, O-fragments, Xe, Ar", "-", "owner answer / A9.1",
          [OW(127, "species calibration for N2/O2/O-related fragments and Xe"),
           A91("UBQ-08", "Ar-specific gauge/MFC/RGA calibration is required for HI-AR engineering interpretation."),
           src_only(IT("UB", "UB-B-04"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-03-R05", "O2 compatibility of the ion source", "Supplier states filament/ion-source material and its behaviour in "
          "O2-bearing gas (the O2-bearing stage is labelled NO_ATOMIC_O).", TBD + " supplier statement", "-",
          "A9 evidence order", [src_only(IT("ICD", "ICP-30"))], None, "TBD", "LOCK-1"),
        R("RFQ-03-R06", "sampling points", "Chamber sampling point and a near-C1 sampling point option (INS-22 analog).",
          TBD + " facility layout and module envelopes (ICD ICP-07)", "-", "instrumentation definition",
          [src_only(IT("INS", "INS-11")), src_only(IT("INS", "INS-22")), src_only(IT("ICD", "ICP-07"))], None, "TBD", "LOCK-1"),
        R("RFQ-03-R07", "detector and minimum detectable partial pressure", "Supplier states detector options and minimum "
          "detectable partial pressure per species at the sampling inlet.", TBD + " supplier statement", "Pa", "-",
          [src_only(DOC("R4", "/items/9"))], None, "TBD", "LOCK-1"),
    ]
    return {
        "id": "RFQ-03", "slug": "rga", "family": "residual gas analyser (~200 amu) with differential pumping",
        "serves": BOTH, "m16_rows": [15],
        "scope": "Quadrupole RGA ~200 amu with a differentially pumped sampling system, species calibration and data interface.",
        "quantities": [{"item": "RGA head + electronics + differentially pumped sampling system", "qty": 1, "basis": "row 127"}],
        "requirements": reqs,
        "acceptance": ["species calibration demonstrated for N2, O2, O-fragments, Xe and Ar (row 127, UBQ-08)",
                       "operation at base and both elevated p_b levels demonstrated on the facility (row 23)"],
        "calibration_traceability": ["calibration traceable to a pressure standard; method and uncertainty stated (UB-B-04)",
                                     "bare +/-x bounds treated as rectangular (UBQ-03)"],
        "documentation": ["calibration report per species with raw spectra", "sampling-system conductance and pressure-drop data",
                          "ion-source material list and O2 compatibility statement", "software/data export format"],
        "reference_data": [CAT("R4", "/items/9/options/0/key_specs/0", "mass range of an open-ion-source RGA class (snippet; verify)"),
                           CAT("R4", "/items/9/options/0/key_specs/2", "max operating pressure without differential pumping "
                                                                      "(snippet; verify)")],
    }


def pkg_rf(D) -> dict:
    rf0s, rf0 = IT("UB", "UB-RF-00", "value")
    rf1s, rf1 = IT("UB", "UB-RF-01", "value")
    reqs = [
        R("RFQ-04-R01", "frequency", "13.56 MHz.", rf0, "MHz", "owner answer; copied from A9-04 UB-RF-00",
          [OW(72, "13.56 MHz."), rf0s, src_only(IT("ICD", "ICP-11"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-04-R02", "laboratory forward-power capability", "Generator and inline measurement chain sized for this forward "
          "power range initially. This is a TEST CAPABILITY, not a flight allocation: the flight ICP must fit inside "
          "P_ICP,available = 1350 W - P_common - P_Hall - P_other,active at every registered condition.", rf1, "W",
          "owner answer; copied from A9-04 UB-RF-01",
          [OW(72, "Size laboratory RF source and inline measurement chain for 0–500 W forward power initially"),
           A91("OQ-A902-03", "The laboratory 0–500 W RF source is a test capability, not permission for the flight "
                             "architecture to consume 500 W."),
           OW(109, "Its power must fit inside the internal ~1.35 kW design allocation"), rf1s], "owner-allocation",
          "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-04-R03", "generator interlock and telemetry", "Hardware interlock input (RF inhibited unless permissives are "
          "true), reflected-power trip, remote forward/reflected readout and state telemetry.", "interlock + fwd/refl telemetry",
          "-", "owner answers / A9-03",
          [OW(62, "New ICP harness must include module ID, RF forward/reflected power, RF interlock, collector/bias V/I, "
                  "temperatures and command/telemetry"), OW(130, "add ICP-specific telemetry"), src_only(IT("ICD", "ICP-16")),
           src_only(IT("ICD", "ICP-34"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-04-R04", "generator input power and metering", "Supplier states the input power interface (AC mains or DC) and "
          "allows input-power metering. The quantity crossing the A9 bus boundary is the RF source's DC input; a mains-fed "
          "laboratory generator is GROUND/FACILITY-ONLY and its efficiency is not the flight slot efficiency.",
          TBD + " owner answer to OQ-RFQ-06 and A902-21 (generator DC-input -> forward-power efficiency, LOCK-2)", "W",
          "A9-02", [src_only(IT("BUS", "A902-19")), src_only(IT("BUS", "A902-21"))], None, "TBD", "LOCK-2", applies_to=ICP),
        R("RFQ-04-R05", "output spectrum and stability", "Supplier states harmonic content into a matched load and frequency "
          "stability.", TBD + " S1a spectrum of the source output into the matched load (UB-RF-06)", "relative",
          "A9-04", [src_only(IT("UB", "UB-RF-06"))], None, "TBD", "LOCK-2", applies_to=ICP),
        R("RFQ-04-R06", "matching network location", "Baseline OFF the moving thrust-stand platform, with matched flexible RF "
          "coax across the stage, calibrated cable-loss/S-parameter correction and matched sham routing in the C1 "
          "configuration; on-platform only if S1a proves the off-platform chain cannot meet the RF-power uncertainty.",
          "off-platform", "-", "A9.1 clarification",
          [A91("A9-03-matching", "Baseline: off the moving thrust-stand platform."),
           A91("A9-03-matching", "calibrated cable-loss/S-parameter correction;"),
           A91("A9-03-matching", "matched sham routing in the C1 configuration.")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-04-R07", "matching network rating and control", "Rated for the full laboratory forward power at 13.56 MHz under "
          "the measured reflected-power condition; manual or auto-tuned; any DC draw (tuning actuators/controller) metered as "
          "its own bus slot.", TBD + " A902-22 matching-network DC draw and ICD ICP-15 ratings", "W", "A9-02 / A9-03",
          [src_only(IT("BUS", "A902-22")), src_only(IT("ICD", "ICP-15")), OW(110, "Every active load gets a bus slot.")],
          None, "TBD", "LOCK-1", applies_to=ICP),
        R("RFQ-04-R08", "directional coupler reference plane", "Directional coupler with forward and reflected sensors at a "
          "declared reference plane AFTER the matching network; calibrated at 13.56 MHz over 0-500 W forward; coupling "
          "factor, directivity and sensor linearity certified.", "after the matching network", "-", "owner answer / A9.1",
          [OW(72, "with directional-coupler forward/reflected measurements"),
           A91("A9-03-matching", "directional coupler/reference plane after the matching network;"),
           src_only(IT("UB", "UB-RF-02")), src_only(IT("UB", "UB-RF-03")), src_only(IT("UB", "UB-RF-04"))],
          "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-04-R09", "coupler/sensor uncertainty", "Supplier states coupling-factor, directivity and sensor-calibration "
          "uncertainty at 13.56 MHz with coverage factor.", TBD + " coupler and sensor certificates (UB-RF-02..04)", "relative",
          "A9-04", [src_only(IT("UB", "UB-RF-02")), src_only(IT("UB", "UB-RF-03")), src_only(IT("UB", "UB-RF-04"))], None,
          "TBD", "LOCK-2", applies_to=ICP),
        R("RFQ-04-R10", "calorimetric cross-check", "An independent calorimetric load/method cross-checks the coupler chain; "
          "agreement statistic with k_x = 2 frozen at LOCK-1; on failure RF-dependent quantities are EXCLUDED_INSTRUMENT. "
          "Calorimetry is never the sole primary RF power measurement.", "independent cross-check (k_x = 2 at LOCK-1)", "-",
          "owner answer / A9.1",
          [OW(72, "Calorimetry is an independent cross-check, not the sole primary power measurement."),
           A91("UBQ-04", "Accept the normalized agreement statistic but freeze k_x = 2 at LOCK-1."),
           src_only(IT("UB", "UB-RF-08"))], "owner-allocation", "OWNER_GIVEN", "LOCK-1", applies_to=ICP),
        R("RFQ-04-R11", "flexible matched coax (live + sham)", "Flexible, low-stiffness RF coax for the stand crossing, supplied as "
          "an identical live/sham pair with S-parameters; no uncompensated hard line across the moving stage.",
          "flexible, matched pair", "-", "owner answers",
          [OW(117, "flexible RF coax with matched sham routing"), OW(133, "matched sham service lines in every compared "
                                                                      "configuration"), src_only(IT("ICD", "ICP-18"))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-04-R12", "vacuum RF feedthroughs", "Rated for the full laboratory forward power at 13.56 MHz under the measured "
          "reflected condition, with RF-voltage, creepage/clearance and Paschen rating and combined RF + DC stress "
          "qualification (ICP-44; not replaced by the C1 keeper hipot).", TBD + " ICD ICP-15 and ICP-44 ratings (LOCK-1)",
          "V (peak RF), W", "A9-03 / A9.1",
          [src_only(IT("ICD", "ICP-15")), src_only(IT("ICD", "ICP-44")),
           A91("ICP-46", "It does not replace ICP-44 RF insulation/combined RF+DC stress qualification.")], None, "TBD",
          "LOCK-1", applies_to=ICP),
        R("RFQ-04-R13", "RF pickup / EMC", "Supplier states conducted/radiated emission data of generator and matching network; "
          "S1a measures pickup on all channels with a dummy load and with the ICP energized.",
          TBD + " S1a pickup test (ICD ICP-17)", "V, A, dB", "A9-03", [src_only(IT("ICD", "ICP-17"))], None, "TBD", "LOCK-2"),
        R("RFQ-04-R14", "flight allocation context", "Not a lab requirement: the flight-representative RF generator/matching is "
          "allocated mass in the owner's v0 dry budget (allocation, not a CBE); the supplier states mass for any "
          "flight-representative option.", PEND("A9-06", "RF generator/matching mass reconciliation"), "kg",
          "owner answer (allocation context)", [OW(54, "RF generator/matching 1.5")], None, "PENDING", "after-evidence",
          applies_to=ICP),
    ]
    return {
        "id": "RFQ-04", "slug": "rf_chain", "family": "13.56 MHz RF generator, matching network, coupler/sensors, feedthroughs, "
                                                    "flexible matched coax",
        "serves": BOTH, "m16_rows": [12, 15, 17],
        "scope": ("Laboratory 13.56 MHz RF generator (0-500 W forward test capability), off-platform matching network, "
                  "calibrated dual directional coupler with forward/reflected sensors at the reference plane after the "
                  "matching network, calorimetric cross-check load, vacuum RF feedthroughs, and an identical live/sham pair "
                  "of flexible coax for the stand crossing."),
        "quantities": [
            {"item": "13.56 MHz generator, 0-500 W forward", "qty": 1, "basis": "row 72; row 8"},
            {"item": "matching network (manual or auto)", "qty": 1, "basis": "row 8; A9-03-matching"},
            {"item": "dual directional coupler + forward/reflected sensors (calibrated at 13.56 MHz)", "qty": 1, "basis": "row 72"},
            {"item": "calorimetric cross-check load", "qty": 1, "basis": "row 72; UBQ-04"},
            {"item": "vacuum RF feedthrough", "qty": TBD + " module drawings (ICD ICP-15) + spare (OQ-RFQ-01)", "basis": "row 8"},
            {"item": "flexible RF coax, identical live + sham pair", "qty": 2, "basis": "rows 117, 133"},
        ],
        "requirements": reqs,
        "acceptance": [
            "coupler/sensor calibration certificates at 13.56 MHz over 0-500 W forward (row 72)",
            "coupler vs calorimetry agreement with k_x = 2 (UBQ-04); failure -> EXCLUDED_INSTRUMENT",
            "feedthrough RF + DC stress qualification (ICP-44)",
            "interlock function test (RF inhibited on each permissive false) (ICP-16)",
        ],
        "calibration_traceability": [
            "RF power traceable via ISO/IEC 17025 / NABL scope covering 13.56 MHz and the power range (A4 force/DC/RF "
            "traceability; metrology spec MS-G-01)",
            "cable-loss / S-parameter calibration of the live coax and the matching-network loss chain (A9.1; UB-RF-05)",
            "bare +/-x bounds treated as rectangular (UBQ-03)",
        ],
        "documentation": [
            "generator datasheet incl. input power interface, efficiency, harmonics, interlock and telemetry interfaces",
            "matching-network schematic/ratings and tuning-actuator power",
            "coupler/sensor certificates with uncertainty budgets",
            "feedthrough RF/DC ratings and qualification data",
            "coax S-parameters (live and sham) and bend-stiffness data",
        ],
        "reference_data": [
            CAT("R4", "/items/6/options/0/key_specs/0", "frequency range recorded for an inline HF/VHF sensor class: the "
                                                         "recorded lower edge (25 MHz) lies above 13.56 MHz (snippet; verify)"),
            CAT("R4", "/items/6/options/1/key_specs/1", "element-based wattmeter frequency coverage (snippet; verify)"),
        ],
        "reference_data_gap": ("no 13.56 MHz generator, matching-network or RF-feedthrough catalogue datasheet was accessed by "
                               "this lane; the supplier datasheet is a required deliverable of the quotation"),
    }


def pkg_icp_source(D) -> dict:
    reqs = [
        R("RFQ-05-R01", "unmagnetized ICP (v1)", "No dedicated magnet in the first build; magnetic assistance is a separate "
          "controlled variant.", "unmagnetized", "-", "owner answer",
          [OW(69, "UNMAGNETIZED 13.56 MHz ICP for v1/A9 first build."), src_only(IT("ICD", "ICP-32"))], "owner-allocation",
          "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-05-R02", "floating dielectric/body", "ICP dielectric and module body float unless the validated circuit requires "
          "otherwise; body potentials measurable.", "floating (default)", "-", "owner answer",
          [OW(70, "Keep the ICP dielectric/body floating unless the validated circuit requires otherwise"),
           src_only(IT("ICD", "ICP-20"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-05-R03", "collector material (NOT frozen)", "Flight collector material is not frozen. 316L may be quoted for Ar "
          "engineering reproduction only; candidate materials go through the O2/AO coupon programme before N2/O2 life "
          "claims. Quote 316L plus coupon-grade samples of supplier-proposed oxygen-resistant candidates.",
          "316L (Ar engineering only) + candidate coupons", "-", "A9.1 clarification",
          [A91("A9-03-collector", "Do not freeze flight collector material yet."),
           A91("A9-03-collector", "316L may be used for Ar engineering reproduction if necessary."),
           OW(106, "Test both biased and floating coupons across the shortlisted O-resistant candidates")],
          "owner-allocation", "OWNER_GIVEN", "after-evidence", applies_to=ICP),
        R("RFQ-05-R04", "dielectric source vessel material", "Supplier proposes the dielectric (tube/window) material with its "
          "validated continuous-use temperature limit and RF loss data; the design keeps >= 50 K below that limit plus a 20 % "
          "heat-load margin, and score-bearing aborts sit at limit - 50 K.", TBD + " ICP module design (ICD ICP-37, ICP-43)",
          "K", "owner answer / A9.1",
          [OW(86, "Require ≥50 K margin below each validated continuous-use material/insulation temperature limit plus "
                  "20% heat-load design margin."),
           A91("UBQ-06", "temperature aborts occur at validated continuous-use limit minus 50 K"),
           src_only(IT("ICD", "ICP-37"))], None, "TBD", "LOCK-1", applies_to=ICP),
        R("RFQ-05-R05", "antenna and shielding", "RF antenna (coil) with insulation and a grounded or declared-potential cover so "
          "no parasitic discharge forms outside the source; cooling passive by default (active cooling only with a booked "
          "bus slot and matched sham lines).", TBD + " ICD ICP-19 and ICP-38 design", "-", "A9-03",
          [src_only(IT("ICD", "ICP-19")), src_only(IT("ICD", "ICP-38")), OW(66, "active cooling if used")], None, "TBD",
          "LOCK-1", applies_to=ICP),
        R("RFQ-05-R06", "geometry (standoff, aperture, envelope)", "Axial standoff from IP-EXIT to IP-NEU, clear aperture for "
          "the Hall plume and module envelope/keep-outs.", TBD + " ICD ICP-02, ICP-04, ICP-07 (LOCK-1)", "mm", "A9-03",
          [src_only(IT("ICD", "ICP-02")), src_only(IT("ICD", "ICP-04")), src_only(IT("ICD", "ICP-07")),
           A91("A9-03-planes", "IP-NEU = downstream neutralizer datum.")], None, "TBD", "LOCK-1", applies_to=ICP,
          note="the Takahashi 2024 analog geometry is topology context only and is never scaled to H-1"),
        R("RFQ-05-R07", "collector/bias supply (floating)", "Floating collector/bias supply with V and I readback on "
          "floating-rated channels; current rating must reach the registered I_d,max (ICP-45 entry condition I_e,cap >= "
          "I_d,max demonstrated on Ar (ICP-45A) and N2 (ICP-45N)). I_d,max comes from the registered H-1/discharge-supply "
          "envelope and is not invented here.", TBD + " A902-23 collector/bias V and I range and the registered I_d,max "
          "(ICD ICP-45)", "V, A", "A9.1 / A9-02 / A9-03",
          [A91("ICP-45", "I_d,max comes from the actual registered H-1/discharge-supply envelope; do not invent it to unblock "
                         "ICP sizing."),
           A91("ICP-45", "The published ~1 A / 200 W Takahashi point remains context only."),
           src_only(IT("BUS", "A902-23")), src_only(IT("ICD", "ICP-21")), src_only(IT("ICD", "ICP-45"))], None, "TBD",
          "LOCK-1", applies_to=ICP),
        R("RFQ-05-R08", "isolation of the collector/bias circuit", "Isolated from the Hall anode, C1 cathode-common and facility "
          "ground, rated to the relaxed 350 V V_d end plus transient/qualification margin (margin TBD).", 350.0, "V",
          "owner answer (margin TBD)",
          [OW(81, "rate H-1, C1 reference, discharge supply, isolation and diagnostics to the relaxed 350 V end plus "
                  "appropriate transient/qualification margin"), src_only(IT("ICD", "ICP-23"))], "owner-allocation",
          "OWNER_GIVEN", "LOCK-1", applies_to=ICP),
        R("RFQ-05-R09", "capped dedicated gas port and pressure port", "Dedicated ICP gas port installed and capped (G-REUSE "
          "primary); a pressure port in the source volume for the Hall-exhaust-to-ICP pressure/conductance interface.",
          "capped port + pressure port", "-", "A9.1 / owner answer",
          [A91("HIQ-06", "The dedicated ICP gas port remains installed and capped so G-ATM and G-XE can be tested as separately "
                         "declared contingency variants."),
           OW(63, "Define and measure the downstream Hall-exhaust-to-ICP pressure/conductance interface"),
           src_only(IT("ICD", "ICP-27"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-05-R10", "MODULE_ID and serialization", "MODULE_ID line; repaired/replaced score-bearing modules become new "
          "serialized units.", "MODULE_ID + serial", "-", "owner answers",
          [OW(62, "module ID"), OW(83, "repaired/replaced H-1, C1 or ICP score-bearing module becomes a new serialized unit"),
           src_only(IT("ICD", "ICP-33"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-05-R11", "O2 service and materials", "O2-wetted parts cleaned to ASTM G93 Level C; no silver in O2/AO-wetted parts; "
          "all materials declared (the O2-bearing stage is NO_ATOMIC_O; AO life is a separate programme).",
          "ASTM G93 Level C; no silver", "-", "owner answers",
          [OW(107, "ADOPT ASTM G93 Level C cleaning for O2 service"),
           OW(103, "exclude silver from oxygen/AO-wetted gas-path parts"),
           OW(132, "ADD a dedicated AO source for separate materials/lifetime qualification.")], "owner-allocation",
          "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-05-R12", "flight allocation context", "Owner v0 dry allocation for the ICP neutralizer (allocation, not a CBE); "
          "supplier states the mass of the quoted parts.", PEND("A9-06", "ICP neutralizer mass reconciliation"), "kg",
          "owner answer (allocation context)", [OW(54, "ICP neutralizer 2.0")], None, "PENDING", "after-evidence",
          applies_to=ICP),
    ]
    return {
        "id": "RFQ-05", "slug": "icp_source_components", "family": "ICP source-chamber components and collector/bias supply",
        "serves": ICP, "m16_rows": [13, 16, 17],
        "scope": ("Components for the downstream 13.56 MHz ICP electron-source module (engineering build for Ar reproduction, "
                  "then N2): dielectric source vessel, RF antenna with shield, electron-extraction collector (material NOT "
                  "frozen), module body with capped gas port and pressure port, MODULE_ID provision, and a floating "
                  "collector/bias supply with V/I readback. Build-to-print quotations follow the LOCK-1 module drawings."),
        "quantities": [
            {"item": "dielectric source vessel", "qty": TBD + " module drawings + spare (OQ-RFQ-01)", "basis": "row 8"},
            {"item": "RF antenna + shield", "qty": TBD + " module drawings", "basis": "row 8"},
            {"item": "collector, 316L (Ar engineering only)", "qty": TBD + " module drawings", "basis": "A9-03-collector"},
            {"item": "coupon samples of candidate collector materials (biased + floating coupons)", "qty": TBD + " coupon plan",
             "basis": "row 106; A9-03-collector"},
            {"item": "floating collector/bias supply with V/I readback", "qty": 1, "basis": "row 70; ICP-21"},
        ],
        "requirements": reqs,
        "acceptance": [
            "dimensional inspection against LOCK-1 drawings; material certificates",
            "isolation test of the collector/bias circuit (350 V + TBD margin)",
            "ICP-45A (Ar) then ICP-45N (N2) electron-current capacity demonstrations are TEST-CAMPAIGN entry conditions, not "
            "supplier acceptance tests; the supplier provides the hardware only",
        ],
        "calibration_traceability": [
            "collector/bias V and I channels calibrated at the operating common-mode potential (UB-N-01, UB-N-02)",
        ],
        "documentation": ["material certificates (dielectric, collector, antenna, insulators)", "O2 cleaning certificate",
                          "continuous-use temperature limit and its basis for every material", "drawings and as-built dimensions"],
        "reference_data": [],
        "reference_data_gap": ("no ICP component catalogue data were accessed by this lane; the published Takahashi 2024 "
                               "analog (A9-05, docs/evidence/icp_neutralizer/) is topology context only and is not quoted as a "
                               "specification"),
    }


def pkg_power(D) -> dict:
    ppu05s, ppu05 = IT("H24", "H3-PPU-05")
    ppu01s, ppu01 = IT("H24", "H3-PPU-01")
    busv_s, busv = IT("BUS", "A902-11", "value")
    reqs = [
        R("RFQ-06-R01", "flight-representative breadboard Hall discharge supply", "Procure/build a flight-representative "
          "breadboard discharge supply so eta_d and transient behaviour are measured before LOCK-2.",
          "flight-representative breadboard", "-", "owner answer",
          [OW(113, "procure/build a flight-representative breadboard Hall discharge supply so eta_d and transient behavior are "
                   "measured before LOCK-2"), ppu05s, src_only(IT("BUS", "H3-A902-08"))], "owner-allocation", "OWNER_GIVEN",
          "NOW"),
        R("RFQ-06-R02", "breadboard input: regulated internal propulsion bus", "Input from the regulated internal propulsion bus "
          "of the breadboard/PPU architecture (not an RFP spacecraft interface requirement); spacecraft-input front end "
          "configurable. Supersedes the 28 V-class input in H2-4 H3-PPU-05 for A9 (flag to A9-07).", busv, "V",
          "owner answer; copied from A9-02 A902-11",
          [OW(111, "REGULATED 100 V internal propulsion bus for the breadboard/PPU architecture"),
           OW(111, "Do not claim 100 V is an RFP spacecraft interface requirement."), busv_s], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R03", "discharge output voltage rating", "Rated to the relaxed 350 V end plus transient/qualification margin; "
          "lower end and power rating per the registered H-1 envelope.", 350.0, "V (upper; margin TBD)", "owner answer",
          [OW(81, "rate H-1, C1 reference, discharge supply, isolation and diagnostics to the relaxed 350 V end plus "
                  "appropriate transient/qualification margin"), src_only(IT("UB", "UB-I-06"))], "owner-allocation",
          "OWNER_GIVEN", "LOCK-1"),
        R("RFQ-06-R04", "discharge output power / current rating", "Output power and current ratings follow the Hall discharge "
          "load and I_d,max of the registered H-1 envelope; the H2-4 PROPOSED '<= 1 kW' is context only.",
          TBD + " A902-32 Hall discharge load and the registered I_d,max (ICD ICP-45)", "W, A", "A9-02",
          [src_only(IT("BUS", "A902-32")), src_only(IT("ICD", "ICP-45")), ppu05s], None, "TBD", "LOCK-1"),
        R("RFQ-06-R05", "controlled V_d definition support", "The supply and its sense lines support the controlled quantity "
          "V_d = V_anode - V_electron-source-reference (not merely the terminal setting); terminal voltage and loop drops "
          "recorded as secondary quantities.", "V_d = V_anode - V_ref(electron source)", "-", "A9.1 clarification",
          [A91("A9-03-Vd", "not merely the discharge-supply terminal setting."), src_only(IT("ICD", "ICP-22"))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R06", "laboratory discharge supply (ground only)", "Laboratory discharge supply per H2-4 H3-PPU-01 (floating "
          "output, programmable current limit and ramp, arc/extinction recovery) - GROUND/FACILITY-ONLY.",
          ppu01["spec_level_to_order"], "V, A", "copied from H2-4 H3-PPU-01", [ppu01s], "model-derived", "COPIED_VERIFIED",
          "LOCK-1", note="8.33 A is the H2-4 minimum rating, not I_d,max; transient margin TBD (S1)"),
        R("RFQ-06-R07", "P_bus gate quantity: 1 ms window", "The measurement chain computes P_bus,1ms,max = max over t of the "
          "1 ms sliding mean of P_bus at the spacecraft-DC propulsion boundary; requirement < 1500 W for start-up and steady "
          "state unless the official RFP later states a transient exception.", "P_bus,1ms,max < 1500", "W",
          "A9.1 (A9 engineering definition pending RFP wording)",
          [A91("OQ-A902-01", "P_{\\rm bus,1ms,max}<1500~W"),
           OW(108, "apply <1.5 kW at the spacecraft-DC propulsion-system boundary"), src_only(IT("BUS", "A902-03"))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R08", "channel bandwidth", "Effective measurement bandwidth of every relevant channel.", ">= 20", "kHz",
          "A9.1", [A91("OQ-A902-01", "effective measurement bandwidth ≥20 kHz")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R09", "sample rate", "Per relevant channel, or an equivalent direct spacecraft-bus power channel.", ">= 100",
          "kSa/s", "A9.1",
          [A91("OQ-A902-01", "sample rate ≥100 kSa/s per relevant channel or an equivalent direct spacecraft-bus power "
                             "channel")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R10", "samples per 1 ms window and Nyquist check", "Arithmetic consequences of R08/R09.",
          {"samples_per_window": D["samples_per_1ms_window_at_min_rate"]["value"],
           "nyquist_kHz": D["nyquist_at_min_rate_kHz"]["value"]}, "samples / kHz",
          D["samples_per_1ms_window_at_min_rate"]["formula"] + "; " + D["nyquist_at_min_rate_kHz"]["formula"],
          [A91("OQ-A902-01", "effective measurement bandwidth ≥20 kHz")], "model-derived", "DERIVED", "NOW"),
        R("RFQ-06-R11", "synchronization, anti-alias, no step-average", "All required channels synchronized on a common time "
          "base; anti-alias filtering documented; no step-average substituted for the 1 ms gate; the unaveraged sampled peak "
          "recorded separately (protection analysis only); 100 ms and 1 s averages reported as diagnostics.",
          "synchronized; AA documented; peak + 100 ms + 1 s recorded", "-", "A9.1",
          [A91("OQ-A902-01", "all required channels synchronized"), A91("OQ-A902-01", "anti-alias filtering documented"),
           A91("OQ-A902-01", "no step-average may be substituted for this gate."),
           A91("OQ-A902-01", "Also record the unaveraged sampled peak separately"),
           A91("OQ-A902-01", "Report 100 ms and 1 s averages as diagnostic/energy metrics")], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        R("RFQ-06-R12", "channel list = A9 bus slots", "One synchronized V and I channel pair per INSTALLED A9 bus slot of the "
          "configuration under test (VARIANT_ONLY slots as options); 4-wire voltage sensing, calibrated shunts or zero-flux "
          "transducers; floating-rated channels where the slot floats (collector/bias).", D["p_bus_channel_slots"]["value"],
          "slots", D["p_bus_channel_slots"]["formula"],
          [src_only(DOC("BUS", "/slots")), OW(110, "Every active load gets a bus slot."), src_only(IT("H24", "H3-PPU-04")),
           src_only(IT("UB", "UB-N-01"))], "model-derived", "DERIVED", "LOCK-1"),
        R("RFQ-06-R13", "per-channel calibration uncertainty", "Supplier states DC V, I and power uncertainty per range with "
          "coverage factor.", TBD + " calibration certificates (UB-P-02, UB-P-03) and A902-36", "relative", "A9-04 / A9-02",
          [src_only(IT("UB", "UB-P-02")), src_only(IT("UB", "UB-P-03")), src_only(IT("BUS", "A902-36"))], None, "TBD", "LOCK-2"),
        R("RFQ-06-R14", "C1 heater booking during start-up", "The chain records heater power at every start-up step; until "
          "measured, the bus ledger books a TBD heater as ON at conservative/worst-case power (never a PASS by assuming it off).",
          "heater logged each step", "-", "A9.1", [A91("SEQ-heater", "TBD heater = ON at conservative/worst-case booked power")],
          "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-06-R15", "wide-band I_d(t) chain", "Exploratory discharge-current chain to ~60 MHz if feasible; otherwise the "
          "measured bandwidth and its anti-alias/transfer function are declared.", IT("UB", "UB-I-00", "value")[1], "MHz",
          "owner answer; copied from A9-04 UB-I-00",
          [OW(129, "Use the exploratory I_d(t) chain to ~60 MHz if feasible"), src_only(IT("UB", "UB-I-00"))],
          "owner-allocation", "OWNER_GIVEN", "LOCK-2"),
        R("RFQ-06-R16", "regulated 100 V internal-bus breadboard supply", "Regulated internal-bus supply with a configurable "
          "spacecraft-input front end; front-end efficiency measured.", TBD + " A902-12 spacecraft input voltage and A902-13 "
          "front-end efficiency", "V, -", "A9-02", [src_only(IT("BUS", "H3-A902-07")), src_only(IT("BUS", "A902-12")),
                                                     src_only(IT("BUS", "A902-13"))], None, "TBD", "after-evidence"),
    ]
    return {
        "id": "RFQ-06", "slug": "discharge_supply_and_pbus_chain", "family": "flight-representative breadboard Hall discharge "
                                                                            "supply and the P_bus 1 ms measurement chain",
        "serves": BOTH, "m16_rows": [12, 15],
        "scope": ("(a) Flight-representative breadboard Hall discharge supply on the regulated 100 V internal propulsion bus; "
                  "(b) laboratory discharge supply (ground only); (c) regulated 100 V internal-bus breadboard supply with a "
                  "configurable front end; (d) synchronized P_bus measurement chain (V and I per A9 bus slot, >= 20 kHz "
                  "effective bandwidth, >= 100 kSa/s) computing P_bus,1ms,max; (e) exploratory wide-band I_d(t) chain."),
        "quantities": [
            {"item": "flight-representative breadboard discharge supply", "qty": 1, "basis": "row 113"},
            {"item": "laboratory discharge supply (ground only)", "qty": 1, "basis": "H2-4 H3-PPU-01"},
            {"item": "regulated 100 V internal-bus breadboard supply", "qty": 1, "basis": "row 111; H3-A902-07"},
            {"item": "synchronized V/I channel pairs", "qty": "max n_installed over configurations + variant options (R12)",
             "basis": "A9-02 slots"},
            {"item": "wide-band I_d(t) probe + digitizer", "qty": 1, "basis": "row 129"},
        ],
        "requirements": reqs,
        "acceptance": [
            "eta_d and start-up transient behaviour of the breadboard supply measured before LOCK-2 (row 113)",
            "end-to-end P_bus,1ms,max computation verified on a known transient (bandwidth >= 20 kHz, >= 100 kSa/s, "
            "synchronized channels, anti-alias documented) (A9.1 OQ-A902-01)",
            "channel calibration certificates per range (UB-P-02, UB-P-03)",
        ],
        "calibration_traceability": [
            "DC V/I/power traceable through an ISO/IEC 17025 / NABL scope (A4 force/DC/RF traceability; MS-G-01)",
            "bare +/-x bounds treated as rectangular (UBQ-03)",
        ],
        "documentation": [
            "breadboard schematics, efficiency measurement method and results vs load",
            "transient/inrush test report", "channel list with ranges, bandwidth, anti-alias filters and timing skew",
            "calibration certificates with uncertainty budgets",
        ],
        "reference_data": [
            CAT("R4", "/items/5/options/0/key_specs/0", "DC active-power accuracy of a precision power analyser class"),
            CAT("R4", "/items/5/options/0/key_specs/4", "simultaneous V/I sampling capability of that class"),
        ],
    }


def pkg_xe_feed(D) -> dict:
    reqs = [
        R("RFQ-07-R01", "tank sizing temperature and EOS", "Size at the stated maximum storage temperature of 323 K using a "
          "verified Xe EOS and MEOP/safety factors; room-temperature density is not a sizing basis.", 323.0, "K",
          "owner answer",
          [OW(50, "Size at the stated maximum storage temperature of 323 K, using a verified Xe EOS and MEOP/safety factors.")],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-07-R02", "Xe load design cases", "Quote per case (no single mission Xe load is frozen).", [2.0, 5.0, 10.0], "kg",
          "owner answer", [OW(48, "Run explicit 2 kg / 5 kg / 10 kg design cases for tank/interface sizing")],
          "owner-allocation", "OWNER_GIVEN", "after-evidence"),
        R("RFQ-07-R03", "indicative propellant volume per case at 323.15 K", "Arithmetic from the NIST reference EOS values "
          "recorded in R6; propellant only (excludes residual, reserve, ullage, MEOP margin).",
          D["xe_tank_indicative_volume_L"]["value"], "L", D["xe_tank_indicative_volume_L"]["formula"],
          [src_only(DOC("R6", "/hardware_mass_data")), OW(48, "Run explicit 2 kg / 5 kg / 10 kg design cases"),
           OW(50, "323 K")], "model-derived", "DERIVED", "after-evidence", note=D["xe_tank_indicative_volume_L"]["note"]),
        R("RFQ-07-R04", "tank volume class, MEOP and final ranges", "Tank internal volume, MEOP and safety factors per case.",
          PEND("A9-08", "final tank ranges incl. residual (row 45) and reserve (row 43)"), "L, bar", "pending lane",
          [OW(45, "book the 2% unusable/residual Xe once in the Xe ledger"),
           OW(43, "Use a separate reserve term equal to 20% of planned non-reserve mission Xe"),
           OW(8, "request quotations for Xe tank/PMU/FCU/MFCs/thrust stand")], None, "PENDING", "after-evidence",
          note="the 5-20 L class is the wording of the row 8 question (not an owner value); the indicative propellant "
               "volumes of R03 fall partly below 5 L (2 kg case); the final range follows A9-08"),
        R("RFQ-07-R05", "two isolation valves in series", "Two independent isolation valves in series on the flight "
          "high-pressure Xe/cathode branch (limited redundancy: dual series isolation plus critical sensing/FDIR).",
          2, "valves in series", "owner answers",
          [OW(90, "two independent isolation valves in series on the flight high-pressure Xe/cathode branch"),
           OW(55, "dual series isolation on the high-pressure Xe path")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-07-R06", "low-flow PMU/FCU flow range", "Controllable flow covering the C1 steady range (0.05-0.2 mg/s class) and, "
          "if retained, start/diode flows 0.6-0.8 mg/s, plus the bounded Xe reference flows; all Xe booked (purge, preheat, "
          "ignition, keeper, transition, fallback).", TBD + " the C1 operating point (LOCK-1) and the Xe reference point",
          "mg/s", "owner answers / H2-7",
          [OW(125, "one high-accuracy 0.05–0.2 mg/s-class C1 steady-flow controller"),
           OW(42, "book all Xe during purge, preheat, ignition"), src_only(IT("H27", "H3-03")),
           src_only(IT("H27", "H3-02"))], None, "TBD", "LOCK-1",
          note="the recorded published flow-control analogs (R6) sit at 3-23 mg/s, far above the C1 range: specification gap"),
        R("RFQ-07-R07", "no ICP Xe term in the primary mode", "The primary G-REUSE ICP mode has m_Xe,ICP = 0; no Xe feed is "
          "specified for the ICP; a G-XE contingency is a separate declared variant booked in the Xe ledger.", 0.0,
          "mg/s (ICP Xe, G-REUSE)", "A9.1",
          [A91("HIQ-06", "No dedicated Xe is introduced merely to make the ICP work."), A91("A9-09", "m_{\\rm Xe,ICP}=0")],
          "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=ICP),
        R("RFQ-07-R08", "filter/getter (C1/Xe branch only)", "Include the filter/getter with an explicit <= 17 W-class load only "
          "after vendor/spec verification; account mass and pressure drop; not required for an ICP-only flight branch.",
          TBD + " vendor/spec verification (A902-29)", "W", "owner answer",
          [OW(51, "include the filter/getter with explicit ≤17 W-class load only after vendor/spec verification"),
           src_only(IT("BUS", "A902-29"))], None, "TBD", "after-evidence", applies_to=C1),
        R("RFQ-07-R09", "C1 not co-installed as a flight backup", "The primary A9 flight architecture does not carry C1 and the "
          "ICP together; C1 Xe hardware quoted here serves the ground comparison/control/fallback architecture.",
          "no combined C1 + ICP flight installation", "-", "A9.1",
          [A91("OQ-A902-04", "NO for the primary A9 flight architecture.")], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-07-R10", "mass context", "Owner v0 dry allocation for Xe hardware (allocation, not a CBE; A9 recorder flag: below "
          "the H2-7 analog range); the 40 kg gate is wet (Xe + tank included).", PEND("A9-06", "Xe hardware mass reconciliation"),
          "kg", "owner answers (allocation context)", [OW(54, "Xe hardware 1.5"), OW(5, "INCLUDES Xe + tank")], None,
          "PENDING", "after-evidence"),
        R("RFQ-07-R11", "cleanliness and materials", "Xe-service cleanliness class and wetted materials declared; metal seals.",
          TBD + " H2-3 / A9-07 cleanliness class", "-", "H2-2", [src_only(IT("H22", "H3-C1-04"))], None, "TBD", "LOCK-1"),
    ]
    return {
        "id": "RFQ-07", "slug": "xe_feed", "family": "Xe tank (5-20 L class), low-flow PMU/FCU, two series isolation valves",
        "serves": BOTH, "m16_rows": [6, 7, 8],
        "scope": ("Xe storage tank quoted per 2/5/10 kg design case sized at 323 K; low-flow pressure-management and "
                  "flow-control units covering the C1 and Xe-reference flows; two independent isolation valves in series on "
                  "the high-pressure Xe/cathode branch; optional filter/getter for the C1/Xe branch."),
        "quantities": [
            {"item": "Xe tank (one quote line per 2/5/10 kg case)", "qty": "3 quote lines", "basis": "row 48"},
            {"item": "low-flow PMU (regulator)", "qty": 1, "basis": "row 8"},
            {"item": "low-flow FCU", "qty": 1, "basis": "row 8"},
            {"item": "isolation valves (series pair)", "qty": 2, "basis": "row 90"},
            {"item": "filter/getter (C1/Xe branch)", "qty": "optional", "basis": "row 51"},
        ],
        "requirements": reqs,
        "acceptance": ["proof/burst and leak test data at the quoted MEOP", "flow-control demonstration at the C1 range on Xe",
                       "valve internal/external leakage and cycle-life data"],
        "calibration_traceability": ["pressure and flow sensors calibrated with certificates (NABL / ISO-17025 where score-bearing, "
                                     "row 126)"],
        "documentation": ["tank design data: internal volume, MEOP, safety factors, mass, envelope, mounting, qualification status",
                          "PMU/FCU flow range, resolution, leakage, power, mass", "valve MEOP, leakage, cycle life, power, mass"],
        "reference_data": [
            CAT("R6", "/hardware_mass_data/0", "NIST WebBook Xe densities used for the indicative volume arithmetic",
                source_id="NIST_WEBBOOK_XE"),
            CAT("R6", "/hardware_mass_data/1", "smallest located Xe tank family (under development)", source_id="MTA_XS_XTA"),
            CAT("R6", "/hardware_mass_data/5", "integrated flow control unit mass (flow range far above C1)",
                source_id="MOOG_XFC"),
        ],
    }


def pkg_c1(D) -> dict:
    n09s, n09 = IT("UB", "UB-N-09", "value")
    reqs = [
        R("RFQ-08-R01", "heated Xe-fed LaB6 hollow cathode", "Heated Xe-fed LaB6 hollow cathode as the conventional "
          "reference/control/fallback (not the primary flight neutralizer if the ICP succeeds), sized to the measured/derived "
          "current demand; quote unit + spare.", "heated Xe-fed LaB6", "-", "owner answers",
          [OW(49, "HEATED C1"), OW(88, "heated Xe-fed LaB6 hollow cathode sized to the measured/derived current demand"),
           src_only(IT("H22", "H3-C1-01"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-08-R02", "emission-current rating", "Emission range covering the registered discharge current demand plus keeper "
          "(not invented here).", TBD + " the registered I_d,max (ICD ICP-45) and keeper current (LOCK-1)", "A",
          "owner answer / A9.1",
          [OW(88, "sized to the measured/derived current demand"),
           A91("ICP-45", "I_d,max comes from the actual registered H-1/discharge-supply envelope; do not invent it to unblock "
                         "ICP sizing.")], None, "TBD", "LOCK-1", applies_to=C1),
        R("RFQ-08-R03", "external location and module interface", "External C1 on the C1 reference module seated on KC-1 (H-1 "
          "mean diameter not constrained).", "external (L-EXTERNAL)", "-", "owner answer",
          [OW(79, "EXTERNAL C1 reference."), src_only(IT("ICD", "ICP-05"))], "owner-allocation", "OWNER_GIVEN", "NOW",
          applies_to=C1),
        R("RFQ-08-R04", "pulsed keeper ignition supply", "Current-limited pulsed keeper ignition capability in the 300-600 V "
          "class with interlocks and recorded pulse energy.", n09, "V", "owner answer; copied from A9-04 UB-N-09",
          [OW(89, "provide current-limited pulsed keeper ignition capability in the 300–600 V class for C1 "
                  "development/reference testing, with interlocks and recorded pulse energy"), n09s,
           src_only(IT("BUS", "A902-25"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-08-R05", "keeper-pulse isolation design basis", "Keeper lead, feedthrough, connectors, harness and their "
          "isolation to cathode common / module body / facility ground: upper operating pulse 600 V, minimum design isolation "
          "basis 900 V (1.5x the upper operating pulse). Flight level may be revised upward only, never downward after "
          "test results without controlled justification.", {"upper_operating_pulse_V": 600.0, "design_isolation_basis_V": 900.0,
                                                                "ratio": D["keeper_isolation_basis_ratio"]["value"]}, "V",
          "A9.1 ICP-46",
          [A91("ICP-46", "upper operating pulse: 600 V;"),
           A91("ICP-46", "minimum design isolation basis: 900 V (1.5× upper operating pulse);"),
           src_only(IT("ICD", "ICP-46"))], "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1),
        R("RFQ-08-R06", "keeper-circuit hipot and pulse tests", "Qualification/hipot 1.0 kV DC at representative pressure/gas for "
          "the initial H-1/C1 development hardware; no flashover/breakdown; leakage recorded; separate actual 600 V "
          "pulse-waveform test. Does not replace the ICP-44 RF insulation qualification.", 1.0, "kV DC", "A9.1 ICP-46",
          [A91("ICP-46", "qualification/hipot test: 1.0 kV DC at representative pressure/gas for the initial H-1/C1 development "
                         "hardware;"),
           A91("ICP-46", "no flashover/breakdown;"), A91("ICP-46", "leakage recorded;"),
           A91("ICP-46", "separately perform the actual 600 V pulse-waveform test.")], "owner-allocation", "OWNER_GIVEN",
          "NOW", applies_to=C1),
        R("RFQ-08-R07", "heater supply", "Current-regulated heater supply; heater command/power stated at every start-up step; "
          "until measured the bus ledger books the heater ON at conservative/worst-case power.",
          TBD + " A902-26/A902-27 heater power (supplier data + measurement)", "W", "A9.1 / A9-02",
          [A91("SEQ-heater", "TBD heater = ON at conservative/worst-case booked power"), src_only(IT("BUS", "A902-26")),
           src_only(IT("BUS", "A902-27"))], None, "TBD", "after-evidence", applies_to=C1),
        R("RFQ-08-R08", "purge / ignition flow and dwell", "Vendor/design-qualified purge and ignition flow; each ignition dwell "
          "capped at 120 s with at most two retries (preliminary); all Xe booked.",
          IT("UB", "UB-F-11", "value")[1], "s / retries", "owner answer; copied from A9-04 UB-F-11",
          [OW(93, "cap each ignition dwell at 120 s and allow at most two retries in the preliminary protocol"),
           src_only(IT("UB", "UB-F-11"))], "owner-allocation", "OWNER_GIVEN", "LOCK-2", applies_to=C1),
        R("RFQ-08-R09", "keeper material", "Supplier states keeper material; graphite is not the flight baseline for an "
          "O/AO-exposed keeper; quote oxygen-resistant or ceramic-shielded alternatives for biased coupon screening.",
          "non-graphite alternatives quoted", "-", "owner answer",
          [OW(94, "Do not use graphite as the flight baseline for an O/AO-exposed keeper.")], "owner-allocation",
          "OWNER_GIVEN", "after-evidence", applies_to=C1),
        R("RFQ-08-R10", "temperature instrumentation provisions", "Mandatory cathode-tube thermocouple point and a pyrometer view "
          "of the emitter where line of sight exists (tube temperature never relabelled as emitter temperature); the O-bearing "
          "experimental emitter floor is 1843 K (not a demonstrated lifetime solution).", 1843.0, "K (O-bearing floor)",
          "owner answers",
          [OW(128, "keep the tube thermocouple mandatory and never relabel tube temperature as emitter temperature"),
           OW(95, "ADOPT 1843 K as the conservative C1 O-bearing experimental floor")], "owner-allocation", "OWNER_GIVEN",
          "NOW", applies_to=C1),
        R("RFQ-08-R11", "cathode-common / bleeder network", "Isolated, selectable cathode-common/bleeder topology with voltage and "
          "current measurement; no resistor value frozen.", TBD + " EMC and discharge-stability bench tests (A902-28)",
          "ohm", "owner answer",
          [OW(91, "Use an isolated, selectable cathode-common/bleeder topology with voltage/current measurement"),
           src_only(IT("BUS", "H3-A902-06")), src_only(IT("BUS", "A902-28"))], None, "TBD", "after-evidence", applies_to=C1),
        R("RFQ-08-R12", "Xe-line dielectric break", "Voltage rating of the cathode-branch dielectric break.",
          TBD + " the C1 circuit potentials (H2-2 H3-C1-04: 'break voltage PENDING H2-4') and " +
          PEND("A9-07", "H2-2/H2-4 revision"), "V", "H2-2", [src_only(IT("H22", "H3-C1-04"))], None, "PENDING", "LOCK-1",
          applies_to=C1),
    ]
    return {
        "id": "RFQ-08", "slug": "c1_cathode_and_keeper", "family": "C1 heated LaB6 hollow cathode + pulsed keeper supply "
                                                                   "(300-600 V) with ICP-46 isolation",
        "serves": C1, "m16_rows": [11, 12],
        "scope": ("Heated Xe-fed LaB6 hollow cathode (unit + spare) for the hall_c1_reference control/fallback configuration, "
                  "its heater supply, a current-limited pulsed keeper ignition supply (300-600 V class) with interlocks and "
                  "pulse-energy recording, the keeper-circuit isolation hardware qualified per ICP-46, and a selectable "
                  "cathode-common/bleeder network."),
        "quantities": [
            {"item": "heated LaB6 hollow cathode", "qty": "1 + 1 spare", "basis": "row 49; H2-2 H3-C1-01"},
            {"item": "sacrificial unit for destructive O-exposure", "qty": "0 or 1 (owner call, OQ-RFQ-01)", "basis": "H2-2 H3-C1-01"},
            {"item": "heater supply", "qty": 1, "basis": "H2-4 H3-PPU-03"},
            {"item": "pulsed keeper supply (300-600 V class)", "qty": 1, "basis": "row 89"},
            {"item": "keeper feedthrough + connectors + harness set (ICP-46)", "qty": TBD + " module drawings", "basis": "ICP-46"},
            {"item": "selectable cathode-common/bleeder network", "qty": 1, "basis": "row 91"},
        ],
        "requirements": reqs,
        "acceptance": ["1.0 kV DC hipot at representative pressure/gas, no flashover, leakage recorded; separate 600 V pulse "
                       "waveform test (ICP-46)",
                       "heater/keeper ignition demonstration on Xe within 120 s x at most 2 retries (row 93)",
                       "pulse energy recording verified (row 89)"],
        "calibration_traceability": ["heater, keeper and common-tie V/I channels calibrated with certificates (UB-N-08)"],
        "documentation": ["cathode datasheet: emission range, heater power/time, keeper ignition voltage, spot-mode minimum flow vs "
                          "current on Xe, materials (keeper/orifice/insulator), mass/envelope",
                          "keeper supply schematic, current limit, interlocks, pulse-energy measurement",
                          "hipot and pulse-waveform test reports"],
        "reference_data": [],
        "reference_data_gap": ("the published LaB6 cathode references are listed in H2-2 H3-C1-01 (reference only); no cathode "
                               "catalogue datum is re-quoted here"),
    }


def pkg_services(D) -> dict:
    r5 = load(dpath("R5"))
    fac = [{"name": f["name"], "country": f["country"], "capability_categories": f["capability_categories"]}
           for f in r5["facilities"]]
    reqs = [
        R("RFQ-09-R01", "calibration services (information list)", "Accredited calibration needed for: force/mass and lever "
          "(RFQ-01), MFC per gas N2/O2/Ar/Xe (RFQ-02), DC V/I/power (RFQ-06), RF power at 13.56 MHz (RFQ-04), vacuum gauges per "
          "gas and RGA species (RFQ-03), thermocouples.", "ISO/IEC 17025 scope covering each measurand", "-",
          "owner answers / metrology spec",
          [OW(126, "NABL/ISO-17025 calibration is the primary score-bearing reference."), OW(119, "ISO/IEC 17025/NABL"),
           src_only(IT("MS", "MS-G-01"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-09-R02", "S1a chamber and score-bearing facility", "Smaller domestic chamber for engineering-only S1a where "
          "appropriate; one qualified facility for score-bearing stages meeting the registered facility requirements; two "
          "elevated background-pressure levels.", "domestic S1a chamber + one qualified facility", "-", "owner answers",
          [OW(139, "use a smaller domestic chamber for engineering-only S1a where appropriate"),
           OW(23, "use two elevated background-pressure levels")], "owner-allocation", "OWNER_GIVEN", "after-evidence"),
        R("RFQ-09-R03", "ISRO/LPSC facility specifications", "OWNER ACTION through official channels before T-PB-MAX is frozen; "
          "not a lane action.", "owner action", "-", "owner answer",
          [OW(137, "request ISRO/LPSC facility specifications now through official channels before T-PB-MAX is frozen.")],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-09-R04", "foreign facilities", "Foreign score-bearing data admissible only with written TDF/export/IP/data-custody "
          "approval and compatible raw-data access; domestic preferred.", "conditional", "-", "owner answer",
          [OW(136, "foreign score-bearing data are admissible only with written TDF/export/IP/data-custody approval")],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-09-R05", "surface analysis lab", "Accredited lab for quantitative score-bearing XPS/EDS where the scope supports "
          "the elements (metrology spec MS-M-03/04).", "accredited XPS/EDS", "-", "owner answer",
          [OW(138, "Accredited lab for quantitative score-bearing XPS/EDS"), src_only(IT("MS", "MS-M-04"))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        R("RFQ-09-R06", "atomic-O source", "Dedicated AO source for the separate materials/lifetime programme (never the N2+O2 "
          "NO_ATOMIC_O surrogate).", TBD + " the AO programme definition", "-", "owner answer",
          [OW(132, "ADD a dedicated AO source for separate materials/lifetime qualification.")], None, "TBD", "after-evidence"),
    ]
    return {
        "id": "RFQ-09", "slug": "facility_calibration_services", "family": "facility and calibration services (information only)",
        "serves": BOTH, "m16_rows": [15],
        "information_only": True,
        "scope": ("INFORMATION ONLY - no quotation is requested by this package. Lists the facility, calibration and metrology "
                  "services the RFQ-01..08 acceptance and traceability clauses depend on, and the facilities recorded by the "
                  "web track (file order, not a ranking; nobody contacted). Requests to ISRO/LPSC are owner actions."),
        "quantities": [],
        "facilities_recorded_R5": {"source": {"path": dpath("R5"), "pointer": "/facilities"}, "entries": fac,
                                   "note": "file order as recorded; not a ranking, not a selection, no contact"},
        "requirements": reqs,
        "acceptance": ["n/a (information only)"],
        "calibration_traceability": ["metrology spec MS-G-01..MS-G-08 apply to every accredited service"],
        "documentation": ["scope documents and accreditation certificates covering each measurand (MS-G-01)"],
        "reference_data": [],
    }


# ----------------------------------------------------------------------------------------------------------------------
# lane-level sections
# ----------------------------------------------------------------------------------------------------------------------
def interface_demands() -> list:
    rows = [
        ("IF-RFQ-01", "A9-06 " + A9_PARALLEL["A9-06"], "RFQ-01", "module masses and CG per configuration on the stand", "kg", "PENDING"),
        ("IF-RFQ-02", "RFQ-01/04/05/07/08 (supplier datasheets)", "A9-06 " + A9_PARALLEL["A9-06"],
         "quoted masses of flight-representative options (RF generator/matching, ICP parts, Xe hardware, C1)", "kg",
         "OPEN (after quotations)"),
        ("IF-RFQ-03", "A9-07 " + A9_PARALLEL["A9-07"], "RFQ-01, RFQ-05, RFQ-08", "KC-1 / downstream ICP fixture drawings, "
         "external C1 mount, >= 50 K thermal protection", "mm, K", "PENDING"),
        ("IF-RFQ-04", "RFQ-06", "A9-07 " + A9_PARALLEL["A9-07"], "H2-4 H3-PPU-05 breadboard input: 28 V class -> regulated "
         "100 V internal bus (row 111) - revision flag", "V", "FLAG"),
        ("IF-RFQ-05", "A9-08 " + A9_PARALLEL["A9-08"], "RFQ-07", "final tank ranges per 2/5/10 kg case incl. residual/reserve, "
         "MEOP; XE_REFERENCE flow; G-XE contingency term", "L, bar, mg/s", "PENDING"),
        ("IF-RFQ-06", "RFQ-02, RFQ-07", "A9-08 " + A9_PARALLEL["A9-08"], "C1 MFC accuracy class (+/-2 % FS until S1a, row 96) "
         "and controller ranges used for the Xe-ledger flow term", "% FS, mg/s", "OWNER_GIVEN"),
        ("IF-RFQ-07", "A9-02 docs/architecture_comparison/power_boundary_a9/", "RFQ-05, RFQ-06, RFQ-08", "I_d,max of the "
         "registered envelope; P_d; collector/bias range (A902-23); matching-network draw (A902-22); heater power", "A, W, V", "OPEN"),
        ("IF-RFQ-08", "RFQ-06", "A9-02 / A9-04", "measured channel uncertainties, bandwidth, sample rate, timing skew for "
         "P_bus,1ms,max (UB-P-02..07, A902-36)", "relative, kHz, kSa/s", "OPEN (after S1a)"),
        ("IF-RFQ-09", "A9-03 schemas/interfaces/icp_neutralizer_icd_v1.json", "RFQ-04, RFQ-05", "ICP-02/04/07 geometry, "
         "ICP-15/44 RF ratings, ICP-16 interlock, ICP-21 collector, ICP-27 pressure port", "mm, V, W", "OPEN (LOCK-1)"),
        ("IF-RFQ-10", "RFQ-04", "A9-04 docs/experiments/hall_icp/uncertainty_budget/", "coupler/sensor certificates at "
         "13.56 MHz, cable S-parameters, calorimetric method", "relative", "OPEN (after quotations)"),
        ("IF-RFQ-11", "A9-01 docs/experiments/hall_icp/prereg_framework/", "RFQ-02, RFQ-03", "HI-AR flow plan (Ar ranges) and "
         "the Xe reference/health-check point", "mg/s", "OPEN (LOCK-1)"),
        ("IF-RFQ-12", "H2-2 H3-C1-01..04", "RFQ-02, RFQ-07, RFQ-08", "C1 procurement inputs reused (flow classes, cathode "
         "data, valves/break)", "-", "COPIED_VERIFIED"),
        ("IF-RFQ-13", "RFQ-01..08", "A9-10 / M16", "procurement_status column updates (quotation packages ready; POs blocked)",
         "-", "PROPOSED"),
    ]
    return [{"id": r[0], "from": r[1], "to": r[2], "quantity": r[3], "units": r[4], "status": r[5]} for r in rows]


def open_owner_questions() -> list:
    q = [
        ("OQ-RFQ-01", "Spare quantities (stand flexures, ICP dielectric/feedthrough spares, C1 sacrificial O-exposure unit)?",
         "owner call; proposed: one spare per consumable/breakable item, C1 unit + one spare, sacrificial unit only if the "
         "destructive O-exposure test is planned"),
        ("OQ-RFQ-02", "Apply row 123 (4 overlapping ranges) literally to the engineering-only Ar path?",
         "proposed: YES (row 123 says 'per pure-gas path'); owner may reduce because Ar is engineering-only"),
        ("OQ-RFQ-03", "Quote the Xe reference-path MFC now with its range TBD, or after A9-01 registers the Xe reference point?",
         "proposed: request indicative quotations now over the C1 + reference envelope; freeze at LOCK-1"),
        ("OQ-RFQ-04", "Is the 0.6-0.8 mg/s C1 start/diode flow retained (row 125 'if ... retained')?",
         "proposed: quote the second controller as an option line; decide with the C1 vendor start procedure"),
        ("OQ-RFQ-05", "Confirm the breadboard discharge supply input = regulated 100 V internal bus (row 111), superseding H2-4 "
                      "H3-PPU-05 '28 V class' for A9?", "proposed: YES; A9-07 records the H2-4 revision"),
        ("OQ-RFQ-06", "Is a mains-fed laboratory 13.56 MHz generator acceptable for the ground campaign given that A902-19 books "
                      "the RF source's DC input at the bus boundary?",
         "proposed: YES as GROUND/FACILITY-ONLY with input metered; the flight-representative DC-input RF source is a later "
         "separate RFQ once A902-21 is scoped"),
        ("OQ-RFQ-07", "Who dispatches the RFQs and may packages be split per supplier type?",
         "owner call (the lane never contacts suppliers)"),
        ("OQ-RFQ-08", "Request an Option B (complete open-design stand) comparison quote at all under row 118?",
         "proposed: YES as comparison only, never as the sole path"),
        ("OQ-RFQ-09", "State a MEOP basis in the tank RFQ or let suppliers propose?",
         "proposed: suppliers propose MEOP/safety factors per case; final basis PENDING A9-08"),
        ("OQ-RFQ-10", "Include the optional ICP capped-port controller (G-ATM/G-XE contingency) in RFQ-02 now?",
         "proposed: YES as an optional line; no purchase unless a contingency variant is declared"),
    ]
    return [{"id": a, "question": b, "proposed_answer": c} for a, b, c in q]


def owner_answers_applied(pkgs: list) -> list:
    use: dict = {}
    for p in pkgs:
        for r in p["requirements"]:
            for s in r["sources"]:
                if s["type"] == "owner_row":
                    use.setdefault(s["row"], set()).add(r["id"])
    extra = {8: "quotations only; purchase-order ban carried in every banner; RF/ICP items added to the RFQ set",
             7: "no access bypasses; catalogue data only from the lawful web-track register",
             37: "no supplier/configuration scoring or ranking; NET_BENEFIT = hard gates + Pareto (standing facts)",
             38: "OPEN carried as a status, never an outcome (status_not_outcome)"}
    out = []
    for row in sorted(set(use) | set(extra)):
        a = answers()[row]
        how = "applied in " + ", ".join(sorted(use.get(row, set()))) if row in use else ""
        if row in extra:
            how = (how + "; " if how else "") + extra[row]
        out.append({"row": row, "covers_ids": a["covers_ids"], "answer_sha256": _ans_sha(row), "how_applied": how})
    return out


def a91_applied(pkgs: list) -> list:
    use: dict = {}
    for p in pkgs:
        for r in p["requirements"]:
            for s in r["sources"]:
                if s["type"] == "a9_1":
                    use.setdefault(s["id"], set()).add(r["id"])
    use.setdefault("A9-09", set()).add("all packages (banner)")
    return [{"id": k, "applied_in": sorted(v)} for k, v in sorted(use.items())]


def historical_reuse() -> dict:
    arts = [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in HISTORICAL.items()]
    return {
        "artifacts": arts,
        "reused": [
            "web-track R4/R5/R6/R7 catalogue and published records (verified inputs, not historical) as REFERENCE data only",
            "H2-2/H2-4/H2-6/H2-7 h3_procurement_inputs item lists (verified inputs) as the starting item structure",
        ],
        "not_reused": [
            "pre-ionizer module ICD (PIM_MD/PIM_JSON): RF/ECR pre-ionizer sizing, PMR/PME frequency options and the upstream "
            "blank are superseded for the primary line (rows 61-65); nothing copied",
            "A5 Phase-1 prereg framework (P1F): old hall_only/rf_hall/ecr_hall thresholds; H26-02/H26-04 derived from it appear "
            "only as labelled context",
            "LOCK-1 drafts (LOCK1): D-01..D-04 historical values not carried",
            "abep_sim/arch_boundary.py (bus_power_boundary_v1): not used; the A9 boundary (abep_sim/bus_boundary_a9.py) governs",
            "A8 / parallel RF||Hall v2 branch: not read",
        ],
        "never_edited": sorted(HISTORICAL.values()),
    }


def m16_impact() -> list:
    rows = load(dpath("M16"))["rows"]
    by = {r["row"]: r for r in rows}
    how = {
        6: ("RFQ-07", "tank quotations per 2/5/10 kg case at 323 K", "PENDING A9-08 final ranges"),
        7: ("RFQ-07", "low-flow PMU quotation", "specification gap at the C1 flow range"),
        8: ("RFQ-02, RFQ-07", "C1 steady + start/diode controllers, FCU", "C1 operating point (LOCK-1)"),
        11: ("RFQ-08", "heated LaB6 C1 + keeper supply (ICP-46 isolation)", "I_d,max of the registered envelope"),
        12: ("RFQ-04, RFQ-06, RFQ-08", "breadboard discharge supply, 100 V bus supply, RF generator, keeper/heater supplies",
             "A9-02 slot powers (A902-22/23/26/27/32)"),
        13: ("RFQ-05", "ICP dielectric/antenna materials with >= 50 K margin", "ICP module heat load (ICP-43)"),
        15: ("RFQ-01, RFQ-02, RFQ-03, RFQ-04, RFQ-06, RFQ-09", "stand, MFCs, RGA, RF metrology, P_bus 1 ms chain, calibration",
             "facility identification; LOCK-1 drawings"),
        16: ("RFQ-01, RFQ-05", "stand platform / KC-1 interface; ICP module parts", "PENDING A9-07 fixture drawings"),
        17: ("RFQ-04, RFQ-05", "row superseded for the primary line; RF/ICP items quoted under the downstream ICP ICD",
             "A9-10 row rename (governance)"),
    }
    out = []
    for n in M16_ROWS_TOUCHED:
        pk, what, block = how[n]
        out.append({"m16_row": n, "key": by[n]["key"], "name": by[n]["name"], "column": "procurement_status",
                    "packages": pk, "how_touched": what,
                    "proposed_procurement_status": "RFQ_SPEC_READY_QUOTATION_ONLY (no purchase order; H3 gate)",
                    "blocking_item": block})
    return out


def h3_h4_inputs(pkgs: list) -> dict:
    return {
        "h3_procurement_gate": {
            "state": "QUOTATION PACKAGES READY FOR OWNER DISPATCH; PURCHASE ORDERS NOT AUTHORIZED",
            "purchase_gate": PURCHASE_GATE,
            "packages": [{"id": p["id"], "family": p["family"],
                          "open_items_blocking_po": [r["id"] for r in p["requirements"] if is_open(r["value"])]}
                         for p in pkgs],
        },
        "h4_tests": [
            {"test": "S1a thrust-stand acceptance at 12 mN, max payload, all lines", "package": "RFQ-01", "rows": [120, 121]},
            {"test": "MFC own-gas calibration verification + installed zero check", "package": "RFQ-02", "rows": [97, 124, 126]},
            {"test": "RGA species calibration incl. Ar", "package": "RFQ-03", "rows": [127], "a9_1": ["UBQ-08"]},
            {"test": "coupler vs calorimetry at 13.56 MHz (k_x = 2)", "package": "RFQ-04", "rows": [72], "a9_1": ["UBQ-04"]},
            {"test": "ICP-45A (Ar) / ICP-45N (N2) electron-current capacity - campaign entry condition using RFQ-04/05 hardware",
             "package": "RFQ-04, RFQ-05", "a9_1": ["ICP-45"]},
            {"test": "breadboard eta_d and transient; P_bus,1ms,max chain verification", "package": "RFQ-06", "rows": [113],
             "a9_1": ["OQ-A902-01"]},
            {"test": "keeper circuit 1.0 kV DC hipot + 600 V pulse-waveform test", "package": "RFQ-08", "a9_1": ["ICP-46"]},
        ],
    }


def traceability(pkgs: list) -> dict:
    rows, rev = [], {}
    for p in pkgs:
        for r in p["requirements"]:
            labels = []
            for s in r["sources"]:
                if s["type"] == "owner_row":
                    lab = f"row {s['row']}"
                elif s["type"] == "a9_1":
                    lab = f"A9.1 {s['id']}"
                elif s["type"] == "deliverable_item":
                    lab = f"{s['key']}:{s['id']}"
                else:
                    lab = f"{s['key']}:{s['pointer'] or '/'}"
                labels.append(lab)
                rev.setdefault(lab, []).append(r["id"])
            rows.append({"requirement": r["id"], "package": p["id"], "title": r["title"], "sources": labels,
                         "status": r["status"], "freeze_point": r["freeze_point"]})
    return {"requirement_to_source": rows,
            "source_to_requirements": {k: sorted(set(v)) for k, v in sorted(rev.items())}}


# ----------------------------------------------------------------------------------------------------------------------
# assembly + validation
# ----------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    pins = check_decisions()
    dpins = []
    for k in DELIVERABLES:
        rel = dpath(k)
        dpins.append({"key": k, "path": rel, "sha256": sha256_of(rel)})
    D = derived()
    pkgs = [pkg_thrust_stand(D), pkg_mfc(D), pkg_rga(D), pkg_rf(D), pkg_icp_source(D), pkg_power(D), pkg_xe_feed(D),
            pkg_c1(D), pkg_services(D)]
    for p in pkgs:
        p["banner"] = BANNER
        p["purchase_gate"] = PURCHASE_GATE
        p["open_specification_items"] = [{"id": r["id"], "title": r["title"], "value": r["value"],
                                          "freeze_point": r["freeze_point"]} for r in p["requirements"] if is_open(r["value"])]
        p["supplier_must_state"] = [
            "compliance per requirement id (COMPLIANT / DEVIATION with justification / NOT OFFERED)",
            "datasheets and certificates named in 'documentation'",
            "lead time and qualification/heritage status",
            "mass, envelope and power of every quoted item",
            "commercial terms go to the owner outside this repository (no prices are recorded here)",
        ]
        p["package_file"] = f"{PKG_DIR}/{p['id']}_{p['slug']}.md"
    doc = {
        "schema": "rfq_a9_v1",
        "id": "RFQ_A9_V1",
        "title": "A9 RFQ / quotation specification packages (quotations only; no purchase orders)",
        "lane": "A9-09",
        "follow_on": "fo_a9_09_rfq_packages",
        "trigger": "T_A9_09_RFQ_PACKAGES",
        "status": "DRAFT_FOR_OWNER_DISPATCH_QUOTATION_ONLY",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE",
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": TEST,
        "banner": BANNER,
        "purchase_gate": PURCHASE_GATE,
        "decision_pins": pins,
        "deliverable_pins": dpins,
        "never_pinned": NEVER_PINNED,
        "standing_facts": {
            "credible_hall_set": "EMPTY (no admitted Hall closure)",
            "p5_n2_v1": "INCONCLUSIVE (permanent)",
            "bundle1": "NO_BASELINE_YET",
            "no_prediction": "no thrust, efficiency, discharge current, electron current or plasma state is predicted; "
                             "published analog data are context only",
            "no_winner": "no configuration is declared a winner; NET_BENEFIT = hard gates + Pareto (row 37; HIQ-05)",
            "full_system_gates": "25 mN, P_bus < 1.5 kW (spacecraft-DC boundary incl. start-up, row 108), < 40 kg wet (row 5)",
            "no_contact": "no supplier, person or lab contacted; no email; no account created; no price recorded",
        },
        "configurations": list(CONFIGURATIONS),
        "outcome_vocabulary": list(OUTCOME_VOCABULARY),
        "status_not_outcome": list(STATUS_NOT_OUTCOME),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "freeze_points": list(FREEZE_POINTS),
        "requirement_statuses": list(STATUSES),
        "derived": D,
        "packages": pkgs,
        "traceability_matrix": traceability(pkgs),
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(pkgs),
        "a9_1_decisions_applied": a91_applied(pkgs),
        "open_owner_questions": open_owner_questions(),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4_inputs(pkgs),
        "pending_lanes": {k: v for k, v in A9_PARALLEL.items()},
        "merged_a9_lanes_consumed": A9_MERGED,
        "compliance": {
            "lane_paths": [LANE_DIR + "/**", TEST],
            "no_purchase_order": True,
            "no_supplier_contact": True,
            "no_supplier_ranking": True,
            "no_prices": True,
            "no_hall_performance_source": "no Hall closure, screening candidate, plasma_devices model or withdrawn number read",
            "pure": "standard library; not wired into archengine; goldens unaffected",
            "thresholds": "only owner-given (row / A9.1) values or verified-deliverable copies; anything else TBD/PENDING/"
                          "PROPOSED",
        },
    }
    validate(doc)
    return doc


def validate(doc: dict) -> None:
    seen = set()
    for p in doc["packages"]:
        if "DO NOT PURCHASE" not in p["banner"]:
            raise ValueError(f"{p['id']}: banner missing")
        for r in p["requirements"]:
            if r["id"] in seen:
                raise ValueError(f"duplicate requirement id {r['id']}")
            seen.add(r["id"])
            if not r["id"].startswith(p["id"] + "-R"):
                raise ValueError(f"{r['id']} not in {p['id']}")
            if not r["sources"]:
                raise ValueError(f"{r['id']}: no source")
            if r["status"] not in STATUSES:
                raise ValueError(f"{r['id']}: bad status {r['status']}")
            if r["freeze_point"] not in FREEZE_POINTS:
                raise ValueError(f"{r['id']}: bad freeze point")
            if any(c not in CONFIGURATIONS for c in r["applies_to"]):
                raise ValueError(f"{r['id']}: bad configuration id")
            if is_open(r["value"]):
                if r["status"] not in ("TBD", "PENDING"):
                    raise ValueError(f"{r['id']}: open value but status {r['status']}")
                if r["evidence_class"] is not None:
                    raise ValueError(f"{r['id']}: open value carries an evidence class")
                if r["value"].startswith(PENDING) and not any(v in r["value"] for v in A9_PARALLEL.values()):
                    raise ValueError(f"{r['id']}: PENDING without a lane path")
            else:
                if r["evidence_class"] not in EVIDENCE_CLASSES:
                    raise ValueError(f"{r['id']}: evidence class {r['evidence_class']!r}")
                if r["status"] in ("TBD", "PENDING"):
                    raise ValueError(f"{r['id']}: status {r['status']} with a value")
            if r["status"] == "OWNER_GIVEN" and not any(s["type"] in ("owner_row", "a9_1") for s in r["sources"]):
                raise ValueError(f"{r['id']}: OWNER_GIVEN without an owner citation")
    blob = json.dumps(doc, ensure_ascii=False).lower()
    for banned in ("winner:", '"price"', '"cost"', "purchase order authorized", "plasma_devices.py"):
        if banned in blob:
            raise ValueError(f"banned content: {banned}")


# ----------------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------------
def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False, sort_keys=True) + "`"
    return str(v).replace("|", "/")


def _src_label(s: dict) -> str:
    if s["type"] == "owner_row":
        return f"row {s['row']}"
    if s["type"] == "a9_1":
        return f"A9.1 {s['id']}"
    if s["type"] == "deliverable_item":
        return f"{s['id']} ({s['path']})"
    return f"{s['path']}#{s['pointer']}"


def _req_table(reqs: list) -> list:
    L = ["| id | title | value | units | status | freeze | evidence class | sources |", "|---|---|---|---|---|---|---|---|"]
    for r in reqs:
        L.append(f"| {r['id']} | {r['title']} | {_fmt(r['value'])} | {r['units']} | {r['status']} | {r['freeze_point']} | "
                 f"{r['evidence_class'] or '-'} | {'; '.join(_src_label(s) for s in r['sources'])} |")
    return L


def render_package(p: dict) -> str:
    L = [f"# {p['id']} - {p['family']}", "",
         f"> **{p['banner']}**", "",
         f"Purchase gate: {p['purchase_gate']}. Serves: {', '.join(p['serves'])}. Generated by `{THIS_SCRIPT}` from "
         f"`{OUT_JSON}` - do not edit by hand.", "", "## Scope", "", p["scope"], ""]
    if p["quantities"]:
        L += ["## Quantities", "", "| item | qty | basis |", "|---|---|---|"]
        L += [f"| {q['item']} | {_fmt(q['qty'])} | {q['basis']} |" for q in p["quantities"]]
        L.append("")
    L += ["## Technical requirements (traced)", ""] + _req_table(p["requirements"]) + [""]
    notes = [r for r in p["requirements"] if r["note"]]
    if notes:
        L += ["Notes:", ""] + [f"- {r['id']}: {r['note']}" for r in notes] + [""]
    L += ["Requirement text:", ""] + [f"- **{r['id']}** {r['requirement']}" for r in p["requirements"]] + [""]
    L += ["## Acceptance", ""] + [f"- {a}" for a in p["acceptance"]] + [""]
    L += ["## Calibration and traceability", ""] + [f"- {a}" for a in p["calibration_traceability"]] + [""]
    L += ["## Deliverable documentation", ""] + [f"- {a}" for a in p["documentation"]] + [""]
    L += ["## Open specification items (TBD / PENDING with the gate that freezes them)", ""]
    if p["open_specification_items"]:
        L += [f"- {o['id']} {o['title']}: {o['value']} - freezes at **{o['freeze_point']}**" for o in p["open_specification_items"]]
    else:
        L.append("- none")
    L += ["", "## The supplier's response must state", ""] + [f"- {a}" for a in p["supplier_must_state"]] + [""]
    if p.get("facilities_recorded_R5"):
        f = p["facilities_recorded_R5"]
        L += ["## Facilities recorded by the web track (information only; file order, not a ranking)", ""]
        L += [f"- {e['name']} ({e['country']}): {', '.join(e['capability_categories'])}" for e in f["entries"]]
        L += ["", f"Source: `{f['source']['path']}#{f['source']['pointer']}`. {f['note']}.", ""]
    L += ["## Reference data (published / catalogue; reference only)", ""]
    if p["reference_data"]:
        for c in p["reference_data"]:
            L.append(f"- {c['source_id']}: {_fmt(c['datum'])} - {c['note']}. Source: {c['citation']}; URL {c['url'] or '-'}; "
                     f"accessed {c['accessed']}; access: {c['access']}. Recorded at `{c['path']}#{c['pointer']}`.")
    else:
        L.append("- none quoted")
    if p.get("reference_data_gap"):
        L.append(f"- gap: {p['reference_data_gap']}")
    L += ["", "Reference data are not requirements, not a selection and not a supplier ranking.", ""]
    return "\n".join(L)


def render_md(doc: dict) -> str:
    L = ["# A9 RFQ / quotation specification packages (A9-09)", "",
         f"> **{doc['banner']}**", "",
         f"Status `{doc['status']}`; A9 status `{doc['a9_status']}`. Lane {doc['lane']} ({doc['follow_on']}, trigger "
         f"{doc['trigger']}), base commit `{doc['base_commit']}`. Generated by `{doc['generated_by']}` from `{OUT_JSON}`; "
         f"rebuild with `python {THIS_SCRIPT}` and verify with `--check`.", "",
         "Standing facts: " + "; ".join(f"{k}: {v}" for k, v in doc["standing_facts"].items()) + ".", "",
         "Configurations: `hall_c1_reference`, `hall_icp_neutralizer`. Outcome vocabulary: "
         + ", ".join(f"`{o}`" for o in doc["outcome_vocabulary"]) + "; `OPEN` is a status, not an outcome (row 38).", "",
         "## Pinned decisions (immutable)", "", "| key | path | sha256 |", "|---|---|---|"]
    L += [f"| {p['key']} | `{p['path']}` | `{p['sha256']}` |" for p in doc["decision_pins"]]
    L += ["", "## Verified deliverables read (sha256 at build)", "", "| key | path | sha256 |", "|---|---|---|"]
    L += [f"| {p['key']} | `{p['path']}` | `{p['sha256']}` |" for p in doc["deliverable_pins"]]
    L += ["", "Never pinned (mutable governance): " + ", ".join(f"`{x}`" for x in doc["never_pinned"]) + ".", ""]
    L += ["## Packages", "", "| id | family | serves | requirements | open items | file |", "|---|---|---|---|---|---|"]
    for p in doc["packages"]:
        L.append(f"| {p['id']} | {p['family']} | {', '.join(p['serves'])} | {len(p['requirements'])} | "
                 f"{len(p['open_specification_items'])} | `{p['package_file']}` |")
    L += ["", "## (a) Items / parameters (all packages)", ""]
    for p in doc["packages"]:
        L += [f"### {p['id']} - {p['family']}", ""] + _req_table(p["requirements"]) + [""]
    L += ["## Derived values (deterministic arithmetic on cited inputs)", "", "| key | value | units | formula |",
          "|---|---|---|---|"]
    L += [f"| {k} | {_fmt(v['value'])} | {v['units']} | {v['formula']} |" for k, v in doc["derived"].items()]
    L += ["", "## Traceability matrix (requirement -> source)", "", "| requirement | package | sources | status | freeze |",
          "|---|---|---|---|---|"]
    L += [f"| {t['requirement']} | {t['package']} | {'; '.join(t['sources'])} | {t['status']} | {t['freeze_point']} |"
          for t in doc["traceability_matrix"]["requirement_to_source"]]
    L += ["", "## (b) Interface demands", "", "| id | from | to | quantity | units | status |", "|---|---|---|---|---|---|"]
    L += [f"| {d['id']} | {d['from']} | {d['to']} | {d['quantity']} | {d['units']} | {d['status']} |"
          for d in doc["interface_demands"]]
    L += ["", "## (c) Owner answers applied", "", "| row | covers | how applied |", "|---|---|---|"]
    L += [f"| {a['row']} | {', '.join(a['covers_ids'])} | {a['how_applied']} |" for a in doc["owner_answers_applied"]]
    L += ["", "A9.1 decisions applied:", ""]
    L += [f"- {a['id']}: {', '.join(a['applied_in'])}" for a in doc["a9_1_decisions_applied"]]
    L += ["", "## (d) Open owner questions (new)", "", "| id | question | proposed answer |", "|---|---|---|"]
    L += [f"| {q['id']} | {q['question']} | {q['proposed_answer']} |" for q in doc["open_owner_questions"]]
    h = doc["historical_reuse"]
    L += ["", "## (e) Historical reuse", "", "| key | path | sha256 |", "|---|---|---|"]
    L += [f"| {a['key']} | `{a['path']}` | `{a['sha256']}` |" for a in h["artifacts"]]
    L += ["", "Reused:", ""] + [f"- {x}" for x in h["reused"]] + ["", "Deliberately not reused:", ""]
    L += [f"- {x}" for x in h["not_reused"]] + [""]
    L += ["## (f) M16 impact (proposed; M16 is refreshed by A9-10)", "",
          "| row | key | packages | how touched | proposed procurement_status | blocking item |", "|---|---|---|---|---|---|"]
    L += [f"| {m['m16_row']} | {m['key']} | {m['packages']} | {m['how_touched']} | {m['proposed_procurement_status']} | "
          f"{m['blocking_item']} |" for m in doc["m16_impact"]]
    hh = doc["h3_h4_inputs"]
    L += ["", "## (g) H3 / H4 inputs", "", f"H3 procurement gate: **{hh['h3_procurement_gate']['state']}**. "
          f"Purchase gate: {hh['h3_procurement_gate']['purchase_gate']}.", "", "| package | open items blocking a PO |",
          "|---|---|"]
    L += [f"| {p['id']} | {', '.join(p['open_items_blocking_po']) or '-'} |" for p in hh["h3_procurement_gate"]["packages"]]
    L += ["", "H4 tests enabled by the quoted hardware:", ""]
    L += [f"- {t['test']} ({t['package']})" for t in hh["h4_tests"]]
    L += ["", "## Pending lanes (nothing read from them)", ""]
    L += [f"- {k}: `{v}`" for k, v in doc["pending_lanes"].items()]
    L += ["", "## Compliance", ""] + [f"- {k}: {v}" for k, v in doc["compliance"].items()] + [""]
    return "\n".join(L)


def outputs(doc: dict) -> dict:
    out = {OUT_JSON: json.dumps(doc, indent=1, ensure_ascii=False) + "\n", OUT_MD: render_md(doc)}
    for p in doc["packages"]:
        out[p["package_file"]] = render_package(p)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if any output differs from a fresh build")
    args = ap.parse_args(argv)
    out = outputs(build())
    if args.check:
        bad = []
        for rel, text in out.items():
            p = _abs(rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != text:
                bad.append(rel)
        existing = sorted(os.path.relpath(p, ROOT).replace(os.sep, "/")
                          for p in glob.glob(os.path.join(ROOT, PKG_DIR, "*.md")))
        stale = [e for e in existing if e not in out]
        if bad or stale:
            print("OUT OF DATE: " + ", ".join(bad + [f"stale {s}" for s in stale]))
            return 1
        print(f"OK: {len(out)} outputs up to date")
        return 0
    os.makedirs(_abs(PKG_DIR), exist_ok=True)
    for rel, text in out.items():
        with open(_abs(rel), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"wrote {len(out)} files")
    return 0


# ---- A9-10 reconciliation overlay hooks (fo_a9_10_integration) ------------------------------------------------------
_a910_build_core = build


def build():
    """Verified lane build followed by the declared A9-10 changes; package-level changes are applied first so that the
    derived package lists (open specification items, traceability, h3/h4 inputs) are rebuilt from them."""
    doc = A910.copy.deepcopy(_a910_build_core())
    A910.apply("A9-09", doc, only_prefix="/packages", attach=False, copy_doc=False)
    for p in doc["packages"]:
        p["open_specification_items"] = [{"id": r["id"], "title": r["title"], "value": r["value"],
                                          "freeze_point": r["freeze_point"]} for r in p["requirements"]
                                         if is_open(r["value"])]
    doc["traceability_matrix"] = traceability(doc["packages"])
    doc["h3_h4_inputs"] = h3_h4_inputs(doc["packages"])
    A910.apply("A9-09", doc, exclude_prefix="/packages", copy_doc=False)
    validate(doc)
    return doc


_a910_md_core = render_md


def render_md(doc):
    """Lane Markdown followed by the A9-10 reconciliation section generated from the same JSON."""
    return _a910_md_core(doc).rstrip("\n") + "\n" + "\n".join(A910.md_section(doc)) + "\n"


if __name__ == "__main__":
    sys.exit(main())
