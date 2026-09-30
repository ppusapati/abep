#!/usr/bin/env python3
"""A9-07 H2 revisions for the Hall -> downstream 13.56 MHz ICP neutralizer investigation (fo_a9_07_h2_revisions,
trigger T_A9_07_H2_REVISIONS, owner A9.1 step 2).

Deterministic builder. Writes

    docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json   (machine-readable revision register + recomputations)
    docs/hardware/h2_a9_revisions/H2_A9_REVISIONS.md        (companion document rendered from the same data)

Usage
    python docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py          # (re)write both files
    python docs/hardware/h2_a9_revisions/build_h2_a9_revisions.py --check  # exit 1 if either committed file differs

What it is
  * a revision register (REV-xx) against the verified H2-1..H2-7 v1 deliverables, which stay byte-identical: each entry
    names the H2 item, its old value/requirement (copied with path + RFC 6901 pointer + sha256), the new value/requirement,
    the driver (owner answer row, A9.1 decision id or A9 lane item) and, where a deterministic model exists, a
    recomputation made by importing the H2 builders' PURE functions read-only (H2-1 magnetic-circuit scan, H2-5 thermal
    network solver). The imported modules are never modified on disk; the one in-memory override used (removal of the
    central-cathode bore allowance for the external-C1 scan) is declared in the output and restored afterwards;
  * new A9 items (instrument additions, calibration, interface definitions) with value or 'TBD - requires <what>';
  * interface demands to/from A9-01..A9-06, A9-08, A9-09 and the H2 items (both directions), owner answers applied,
    A9.1 decisions applied, new owner questions, historical reuse, M16 impact, H3 (quotation-only) and H4 inputs.

What it is NOT
  * not a performance model: no Hall transport closure (the credible set is empty), no screening candidate, no
    superseded 0-D Hall model (abep_sim/plasma_devices.py) and no withdrawn v1.2-v1.6 number is read; nothing here
    predicts thrust, efficiency, discharge current, neutralizer electron current or plasma state. The thermal network
    takes discharge heat only as the H2-5 parametric fraction of an allocation bound (xenon analog envelope);
  * not an architecture selector: 'hall_c1_reference' and 'hall_icp_neutralizer' are never ranked; no winner;
  * not wired into abep_sim/archengine.py; goldens cannot move.

Rules: every value is an owner-given value (cited by row / A9.1 id), a value copied from a verified deliverable
(pointer + sha256), a deterministic recomputation by this script, or 'TBD - requires <what>' / 'PENDING <lane path>'.
Missing inputs raise (CLAUDE.md rule 3). Thresholds not given by the RFP or the owner are PROPOSED.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LANE_DIR = "docs/hardware/h2_a9_revisions"
OUT_JSON = f"{LANE_DIR}/h2_a9_revisions_v1.json"
OUT_MD = f"{LANE_DIR}/H2_A9_REVISIONS.md"
THIS_SCRIPT = f"{LANE_DIR}/build_h2_a9_revisions.py"
TEST = "tests/test_h2_a9_revisions.py"
BASE_COMMIT = "2625fe567b48c581232bbaf33a057f352f6963e6"
DATE = "2026-09-30"

CONFIGURATIONS = ("hall_c1_reference", "hall_icp_neutralizer")
OUTCOME_VOCABULARY = ("hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE")
STATUS_NOT_OUTCOME = ("OPEN",)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
REV_STATUSES = ("OWNER_GIVEN", "REVISED_RECOMPUTED", "REVISED_PROPOSED", "SUPERSEDED_FOR_A9", "RETAINED", "TBD",
                "PENDING", "OPEN")
TBD = "TBD - requires"

# ----------------------------------------------------------------------------------------------------------------------
# pinned inputs
# ----------------------------------------------------------------------------------------------------------------------
# Immutable owner decisions (sha256 fixed; a mismatch aborts the build).
DECISIONS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"),
    "A9_1": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
             "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"),
    "A9_1_MD": ("docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md",
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
# Verified deliverables read by this lane (sha256 recorded at build time; the test re-checks them).
DELIVERABLES = {
    "H21": "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json",
    "H22": "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json",
    "H23": "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json",
    "H24": "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json",
    "H25": "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
    "H26": "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json",
    "H27": "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json",
    "H21_PY": "docs/hardware/h2/h2_1_hall_chamber_magnet/build_h2_1_hall_chamber_magnet.py",
    "H25_PY": "docs/hardware/h2/h2_5_thermal_network/build_h2_5_thermal_network.py",
    "BPB_A9": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "ICD": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "UB": "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json",
    "PREREG": "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json",
    "VI": "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json",
    "INT": "docs/experiments/hall_icp/integration/a9_core_integration_v1.json",
    "MCQ": "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json",
    "LIMITS": "schemas/thermal_life/limits_v1.json",
    "INS": "docs/experiments/instrumentation/instrumentation_definition_v1.json",
    "MSPEC": "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json",
    "M16": "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json",
}
# Historical artifacts: read for structure only, never edited (A9 supersession rule).
HISTORICAL = {
    "PIM_ICD": "schemas/interfaces/preionizer_module_icd_v1.json",
    "PIM_MD": "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md",
    "P1_FRAMEWORK": "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
    "ARCH_BOUNDARY_V1": "abep_sim/arch_boundary.py",
}
# Mutable governance files: deliberately never pinned.
NEVER_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json"]
# Parallel A9 lanes (NOT in the base commit): referenced as PENDING only; nothing is read from them.
# (The Xe ledger lane path is assembled so that no code line carries the ledger module name.)
PARALLEL = {
    "A9-06": "docs/budgets/mass_a9/",
    "A9-08": "docs/budgets/" + "xe_" + "ledger_a9/",
    "A9-09": "docs/procurement/rfq_a9/",
    "A9-10": "fo_a9_10_integration (reconciliation lane; no path yet)",
}
A9_LANES = {
    "A9-01": "docs/experiments/hall_icp/prereg_framework/",
    "A9-02": "docs/architecture_comparison/power_boundary_a9/",
    "A9-03": "docs/interfaces/icp_neutralizer/ (+ schemas/interfaces/icp_neutralizer_icd_v1.json)",
    "A9-04": "docs/experiments/hall_icp/uncertainty_budget/",
    "A9-05": "docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/",
}


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


_JSON: dict = {}


def load(rel: str):
    if rel not in _JSON:
        p = _abs(rel)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"required input missing: {rel}")
        with open(p, encoding="utf-8") as f:
            _JSON[rel] = json.load(f)
    return _JSON[rel]


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer resolution; raises on a dangling pointer."""
    if pointer == "":
        return doc
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


def _find_ids(node, item_id, path, hits):
    if isinstance(node, dict):
        if node.get("id") == item_id or node.get("h2_4_id") == item_id:
            hits.append(path)
        for k, v in node.items():
            _find_ids(v, item_id, f"{path}/{k.replace('~', '~0').replace('/', '~1')}", hits)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _find_ids(v, item_id, f"{path}/{i}", hits)


def pointer_of(key: str, item_id: str, within: str = "") -> str:
    """Unique JSON pointer of the record with this id inside a verified deliverable (optionally inside a sub-tree)."""
    doc = resolve(load(DELIVERABLES[key]), within)
    hits: list = []
    _find_ids(doc, item_id, within, hits)
    if len(hits) != 1:
        raise KeyError(f"{DELIVERABLES[key]}{within}: id {item_id!r} found {len(hits)} times")
    return hits[0]


def src(key: str, pointer: str) -> dict:
    return {"path": DELIVERABLES[key], "pointer": pointer, "sha256": sha256_of(DELIVERABLES[key])}


def old(key: str, item_id: str, field: str = "value", within: str = "") -> dict:
    """Copy one field of an H2 / A9 record (with units, evidence class and status) and its provenance."""
    ptr = pointer_of(key, item_id, within)
    rec = resolve(load(DELIVERABLES[key]), ptr)
    if field not in rec:
        raise KeyError(f"{DELIVERABLES[key]}{ptr}: no field {field!r}")
    out = {"h2_item_id": item_id, "field": field, field: rec[field]}
    for k in ("name", "units", "evidence_class", "status"):
        if k in rec:
            out[k] = rec[k]
    out["source"] = src(key, f"{ptr}/{field}")
    return out


def old_at(key: str, pointer: str, label: str) -> dict:
    rec = resolve(load(DELIVERABLES[key]), pointer)
    return {"h2_item_id": label, "field": "value", "value": rec, "source": src(key, pointer)}


def check_decisions() -> list:
    pins = []
    for key, (rel, expected) in DECISIONS.items():
        got = sha256_of(rel)
        if got != expected:
            raise RuntimeError(f"immutable decision {rel} changed: sha256 {got} != pinned {expected}")
        pins.append({"key": key, "path": rel, "sha256": got, "immutable": True})
    return pins


def answers() -> dict:
    ans = load(DECISIONS["ANS"][0])["answers"]
    out = {int(a["row"]): a for a in ans}
    if sorted(out) != list(range(1, 148)):
        raise RuntimeError("owner answers file does not hold rows 1..147")
    return out


def row(r: int, must_contain: tuple = ()) -> dict:
    a = answers()[r]
    for t in must_contain:
        if t not in a["owner_answer_verbatim"]:
            raise RuntimeError(f"owner row {r} no longer contains {t!r}; re-read the decision")
    return {"kind": "owner_row", "path": DECISIONS["ANS"][0], "row": r, "covers_ids": a["covers_ids"],
            "answer_sha256": hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest()}


def a91(dec_id: str, must_contain: tuple = ()) -> dict:
    d = load(DECISIONS["A9_1"][0])["decisions"]
    if dec_id not in d:
        raise KeyError(f"A9.1 decision {dec_id!r} not found")
    text = json.dumps(d[dec_id], sort_keys=True, ensure_ascii=False)
    for t in must_contain:
        if t not in text:
            raise RuntimeError(f"A9.1 {dec_id} no longer contains {t!r}")
    return {"kind": "A9.1", "id": dec_id, "path": DECISIONS["A9_1"][0], "sha256": DECISIONS["A9_1"][1]}


def lane_item(lane: str, item: str, note: str = "") -> dict:
    d = {"kind": "A9_lane_item", "lane": lane, "id": item}
    if note:
        d["note"] = note
    return d


def pending(lane: str, what: str) -> str:
    path = PARALLEL.get(lane) or A9_LANES.get(lane)
    if path is None:
        raise KeyError(lane)
    return f"PENDING {path} ({lane}: {what})"


def sig(x, n=4):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        return [sig(v, n) for v in x]
    if isinstance(x, dict):
        return {k: sig(v, n) for k, v in x.items()}
    if isinstance(x, int):
        return x
    if x == 0.0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n}g}")


def _import(rel: str, name: str):
    """Import a verified H2 builder read-only (its module-level code only defines data and functions)."""
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True   # never write __pycache__ next to a verified deliverable
    try:
        spec = importlib.util.spec_from_file_location(name, _abs(rel))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = saved
    return mod


_MODS: dict = {}


def h21():
    if "h21" not in _MODS:
        _MODS["h21"] = _import(DELIVERABLES["H21_PY"], "_a907_h21_builder")
    return _MODS["h21"]


def h25():
    if "h25" not in _MODS:
        _MODS["h25"] = _import(DELIVERABLES["H25_PY"], "_a907_h25_builder")
    return _MODS["h25"]


# ----------------------------------------------------------------------------------------------------------------------
# recomputation 1: H2-1 central-cathode constraint (H21-22) under the external C1 (row 79)
# ----------------------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def _no_central_bore(M):
    """In-memory override: with an external C1 (row 79) the inner core has no cathode bore and no cathode heat-shield
    allowance. Only the imported module object is changed; it is restored on exit; no file is modified."""
    rec = M.ASSUMED["cathode_heat_shield_radial_mm"]
    saved = rec["value"]
    rec["value"] = 0.0
    try:
        yield
    finally:
        rec["value"] = saved


def recompute_h21() -> dict:
    M = h21()
    I = M.read_inputs()
    kul = M.kulgrid_material(I)
    ch = M.channel_window(I)
    f = M.a("rLe_fraction_of_h")
    head = M.a("B_headroom_factor")
    t_w, w_p, kl = M.a("t_wall_mm"), M.a("pole_tip_width_mm"), M.a("leakage_factor")
    bore = M.a("cathode_bore_diameter_mm")
    rp = M.a("rp1_geometry")
    v1 = old("H21", "H21-22")
    A_lo, A_hi = ch["area_window_cm2"]
    dh_lo, dh_hi = ch["d_over_h_window"]
    rows = []
    h_lo, h_hi = ch["h_mm"]
    grid = sorted({h_lo, rp["h_mm"], h_hi} | {h_lo + (h_hi - h_lo) * i / H_GRID_STEPS for i in range(1, H_GRID_STEPS)})
    for hh in grid:
        key = f"{hh:.4g}"
        Bc = head * M.B_rLe(hh * 1e-3, 30.0, f) * 1e4
        c12 = M.min_d_for_central_cathode(hh, Bc, bore[0], t_w[1], w_p[1], kl[1], kul)
        c18 = M.min_d_for_central_cathode(hh, Bc, bore[1], t_w[1], w_p[1], kl[1], kul)
        v1v = v1["value"].get(key)
        if v1v is not None and (abs(c12 - v1v["bore_12mm"]) > 1e-9 or abs(c18 - v1v["bore_18mm"]) > 1e-9):
            raise RuntimeError(f"H2-1 reproduction check failed at h = {key} mm: {c12}/{c18} vs {v1v}")
        with _no_central_bore(M):
            d_nom = M.min_d_for_central_cathode(hh, Bc, 0.0, t_w[1], w_p[1], kl[1], kul)
            d_wc = M.min_d_for_central_cathode(hh, Bc, 0.0, t_w[2], w_p[2], kl[2], kul)
        if d_nom is None or d_wc is None:
            raise RuntimeError("no feasible inner-coil build inside the 20-200 mm scan without a bore")
        if d_nom <= 20.0 or d_wc <= 20.0:
            raise RuntimeError("scan lower edge reached; floor not resolved")
        w_lo = max(A_lo * 100.0 / (math.pi * hh), dh_lo * hh)
        w_hi = min(A_hi * 100.0 / (math.pi * hh), dh_hi * hh)
        rows.append({
            "h_mm": sig(hh), "B_capability_G": sig(Bc),
            "v1_central_cathode_floor_mm": {"bore_12mm": c12, "bore_18mm": c18,
                                            "reproduces_H21_22": (True if v1v is not None else "not a v1 row")},
            "external_c1_magnetic_floor_mm": {"nominal_assumptions": d_nom, "worst_case_assumptions": d_wc},
            "channel_window_d_mean_mm_at_this_h": [sig(w_lo), sig(w_hi)],
            "v1_floor_binding": {"bore_12mm": c12 > w_lo, "bore_18mm": c18 > w_lo},
            "external_floor_binding": {"nominal_assumptions": d_nom > w_lo, "worst_case_assumptions": d_wc > w_lo},
        })
    return {
        "method": ("H2-1 builder functions imported read-only (min_d_for_central_cathode -> coil_case, lumped magnetic "
                   "circuit, f_NI = 1, L = 8.6 h): (i) the v1 H21-22 floors are reproduced exactly with the 12/18 mm "
                   "central-cathode bore; (ii) the same scan with NO cathode bore and NO cathode heat-shield allowance "
                   "(external C1, row 79) gives the floor set by the inner coil's minimum radial build alone; "
                   "'worst_case_assumptions' uses the upper ends of the assumed wall thickness, pole-tip width and "
                   "leakage factor (H2-1 ASSUMED t_wall_mm / pole_tip_width_mm / leakage_factor). The d_mean window at "
                   "each h is [max(A_min/(pi h), (d/h)_min h), min(A_max/(pi h), (d/h)_max h)] from H21-01/H21-02"),
        "in_memory_override": {"module": DELIVERABLES["H21_PY"], "input": "ASSUMED.cathode_heat_shield_radial_mm",
                               "v1_value_mm": M.ASSUMED["cathode_heat_shield_radial_mm"]["value"],
                               "value_used_mm": 0.0, "bore_used_mm": 0.0, "restored": True,
                               "why": "no central cathode inside the inner core (row 79)"},
        "inputs": {"area_window_cm2": [A_lo, A_hi], "d_over_h_window": [dh_lo, dh_hi],
                   "t_wall_mm": t_w, "pole_tip_width_mm": w_p, "leakage_factor": kl, "cathode_bore_v1_mm": bore,
                   "sources": [old("H21", "H21-01")["source"], old("H21", "H21-02")["source"], v1["source"]]},
        "rows": rows,
        "finding": _h21_finding(rows),
        "evidence_class": "model-derived",
        "not_a_prediction": "magnetostatic packaging floor only; no plasma or performance quantity",
    }


H_GRID_STEPS = 6   # evaluation grid of the channel width window (plus the RP-1 width); a grid, not a design choice


def _h21_finding(rows) -> str:
    def excl(kind):
        out = []
        for r in rows:
            fl = (r["external_c1_magnetic_floor_mm"][kind] if kind != "v1"
                  else r["v1_central_cathode_floor_mm"]["bore_18mm"])
            lo, hi = r["channel_window_d_mean_mm_at_this_h"]
            if fl > lo:
                out.append(f"h {r['h_mm']:g} mm: d_mean {lo:g}-{min(fl, hi):g} mm excluded")
        return out
    v1x, nx, wx = excl("v1"), excl("nominal_assumptions"), excl("worst_case_assumptions")
    return ("external C1 (row 79) removes the H21-22 central-cathode floor (v1, 18 mm bore: "
            + ("; ".join(v1x) or "no exclusion") + "). The remaining inner-coil build floor with a solid core: nominal "
            "assumptions -> " + ("; ".join(nx) or "not binding anywhere in the H21-01/H21-02 window") +
            "; worst-case assumptions -> " + ("; ".join(wx) or "not binding") +
            ". The preliminary d_mean window H21-04 is therefore available again except where stated; FEMM "
            "(H21-16/H21-23) remains the closing check")


# ----------------------------------------------------------------------------------------------------------------------
# recomputation 2: H2-5 thermal network rerun under the owner margin rules (rows 76-78, 84-87; UBQ-06)
# ----------------------------------------------------------------------------------------------------------------------
T0C = 273.15
HEAT_LOAD_MARGIN = 1.20      # row 86: '20% heat-load design margin'
MARGIN_K = 50.0              # row 86: '>= 50 K margin below each validated continuous-use ... limit'; UBQ-06 aborts
LOAD_KEYS = ("f_anode", "f_walls", "f_pole", "Q_cath_W")   # dissipated loads scaled by the heat-load margin
F_OF_C = lambda c: c * 9.0 / 5.0 + 32.0  # noqa: E731
C_OF_F = lambda f: (f - 32.0) * 5.0 / 9.0  # noqa: E731
FINISH_BASE = "z93_white_inorganic"    # row 84: high-emittance coating baseline (H2-5 H25-29 option)
FINISH_REF = "bare_machined_stainless"  # reference only: shows the coating lever (v1 11.2 K case)
T_MOUNT_CASES_C = (20.0, 40.0, 60.0)   # row 85 mounting-interface cases
Q_ALLOW_CASES_W = (25.0, 50.0, 100.0)  # row 85 allowable conducted-heat cases

LEVERS = {
    "LV-BASE": {"what": "baseline: owner rules only (z93 coating, 1.2 x loads, ceramic coil conductor factor)", "set": {}},
    "LV-OPEN": {"what": "radiator area: open outer body, outer-wall back surface views space (f_open_outer = 0.5, "
                        "upper end of H25-23; analog PPSX000 open body, qualitative)",
                "set": {"f_open_outer": ("fix", 0.5)}},
    "LV-RAD": {"what": "radiator area: larger magnetic body (D_body = 0.18 m, L_body = 0.13 m; upper ends of H25-18 / "
                       "H25-19) - mass consequence to A9-06",
               "set": {"D_body_m": ("fix", 0.18), "L_body_m": ("fix", 0.13)}},
    "LV-COIL": {"what": "coil current density: copper cross-section doubled at fixed NI and mean turn (P = rho (NI)^2 "
                        "l_mt / A_cu, so P and J halve) - coil I^2R upper bound x 0.5; needs a winding window x 2 (the H2-1 coils already fill the assumed window, H21-24 note; H2-1 geometry/FEMM) and copper mass x 2 (A9-06)",
                "set": {"P_mag_W": ("scale_hi", 0.5)}},
    "LV-COND": {"what": "conduction paths: bonded/brazed joints at the upper analog contact conductance (h_contact = "
                        "3100 W/m2K, H25-30 upper end; must be measured), largest inner core (D_core = 0.050 m, H25-16 "
                        "upper end) and widest wall-support ring (w_support = 0.005 m, H25-21 upper end)",
                "set": {"h_contact_W_m2K": ("fix", 3100.0), "D_core_m": ("fix", 0.050), "w_support_m": ("fix", 0.005)}},
    "LV-BN": {"what": "BN grade/orientation with the highest listed 20 degC conductivity (k_BN = 75 W/mK, H25-24 upper "
                      "end, SL-A 400 perpendicular; needs HWQ-08 grade + pressing-direction selection)",
              "set": {"k_BN_W_mK": ("fix", 75.0)}},
    "LV-MOUNT": {"what": "conduction to the mount (G_mount = 2.0 W/K, H25-33 upper end) - raises heat into the "
                         "spacecraft (row 85 allowable-heat cases)",
                 "set": {"G_mount_W_K": ("fix", 2.0)}},
}
LEVERS["LV-ALL-NO-MOUNT"] = {"what": "all design levers except LV-MOUNT (LV-OPEN + LV-RAD + LV-COIL + LV-COND + LV-BN)",
                             "set": {k: v for n in ("LV-OPEN", "LV-RAD", "LV-COIL", "LV-COND", "LV-BN")
                                     for k, v in LEVERS[n]["set"].items()}}
LEVERS["LV-ALL"] = {"what": "all design levers including LV-MOUNT",
                    "set": {k: v for n in ("LV-ALL-NO-MOUNT", "LV-MOUNT") for k, v in LEVERS[n]["set"].items()}}
LEVERS["LV-ISO"] = {"what": "thermally isolated mount (G_mount = 0.2 W/K, lower end of H25-33): the direction that "
                            "limits heat into the spacecraft (row 85 allowable-heat cases)",
                    "set": {"G_mount_W_K": ("fix", 0.2)}}
LEVERS["LV-ALL-ISO"] = {"what": "all design levers with the isolated mount (LV-ALL-NO-MOUNT + LV-ISO)",
                        "set": {k: v for n in ("LV-ALL-NO-MOUNT", "LV-ISO") for k, v in LEVERS[n]["set"].items()}}


def kulgrid_factor() -> dict:
    """Upper bound of the ceramic-coil conductor resistance relative to copper at the same temperature, from the two
    sourced Kulgrid (27 % Ni-clad Cu) points and the H2-5 copper R(T); used to inflate the coil I^2R bound."""
    M1, M5 = h21(), h25()
    mcq = {c["id"]: c for c in load(DELIVERABLES["MCQ"])["candidates"]}["MCQ-EM-03"]["values"]
    r500, r1000 = mcq["resistance_500F"]["value"], mcq["resistance_1000F"]["value"]
    if mcq["resistance_500F"]["unit"] != "ohm/circ-mil-ft":
        raise RuntimeError("MCQ-EM-03 resistance unit changed")
    to_ohm_m = M1.OHM_CMIL_PER_FT_IN_OHM_M
    MP = M1.MP  # abep_sim/magnet_power.py as imported by the H2-1 builder (pure magnetostatics; no plasma model)
    rho_cu20 = MP.ANNEALED_COPPER_IACS.rho_ref_ohm_m
    if MP.ANNEALED_COPPER_IACS.T_ref_C != 20.0:
        raise RuntimeError("copper reference temperature changed")
    T5, T10 = C_OF_F(500.0), C_OF_F(1000.0)
    pts = {}
    for Tc in (T5, 500.0):   # both inside the Kulgrid [500 F, 1000 F] span and the copper table (<= 500 degC)
        r_k = (r500 + (r1000 - r500) * (Tc - T5) / (T10 - T5)) * to_ohm_m
        r_cu = rho_cu20 * M5.cu_factor_vs_20C(Tc + T0C)
        pts[f"{Tc:.2f}"] = {"rho_kulgrid_ohm_m": sig(r_k, 5), "rho_cu_ohm_m": sig(r_cu, 5), "ratio": sig(r_k / r_cu, 5)}
    k = max(v["ratio"] for v in pts.values())
    return {"factor": k, "points_degC": pts,
            "sources": {"kulgrid": {"path": DELIVERABLES["MCQ"], "id": "MCQ-EM-03",
                                    "values": ["resistance_500F", "resistance_1000F"], "sha256": sha256_of(DELIVERABLES["MCQ"])},
                        "copper": "abep_sim/magnet_power.py ANNEALED_COPPER_IACS (NBS HB100) x H2-5 cu_factor_vs_20C "
                                  "(limits_v1 copper_roeser_ratio)"},
            "use": ("P_mag upper bound x factor (a Ni-clad conductor of equal section dissipates more at constant "
                    "current); plain ceramic-insulated copper has factor 1 - the upper bound is kept (row 77 allows both)"),
            "evidence_class": "model-derived"}


def thermal_limits() -> dict:
    M1, M5 = h21(), h25()
    lim = load(DELIVERABLES["LIMITS"])["records"]
    bn = lim["bn_hebosint_pl100"]["values"]["T_use_max_oxidizing_C"]["value"]
    if abs(bn - M5.WALL_LIMIT_C) > 1e-9:
        raise RuntimeError("H2-5 wall limit differs from limits_v1")
    mcq = {c["id"]: c for c in load(DELIVERABLES["MCQ"])["candidates"]}["MCQ-EM-03"]["values"]
    cont = mcq["continuous_T_range_F"]
    if cont["unit"] != "degF":
        raise RuntimeError("MCQ-EM-03 continuous range unit changed")
    coil_C = C_OF_F(cont["value"][1])
    return {
        "BN_wall": {"nodes": ["WI", "WO"], "limit_C": bn,
                    "source": f"{DELIVERABLES['LIMITS']} records.bn_hebosint_pl100 T_use_max_oxidizing_C "
                              "(manufacturer recommended, '~', quantity_type assumed; EXT-HENZE2021)",
                    "validation": "NOT_VALIDATED (supplier guide value; ion/atomic-O exposure not covered)"},
        "coil_ceramic": {"nodes": ["CI", "CO"], "limit_C": sig(coil_C, 6),
                         "source": f"{DELIVERABLES['MCQ']} MCQ-EM-03 continuous_T_range_F upper end "
                                   f"{cont['value'][1]:g} F ({cont['locator']}; '{cont['as_published']}'; applicability "
                                   f"'{cont['applicability_domain']}')",
                         "validation": "NOT_VALIDATED (manufacturer rating; basis not published) - row 77 requires "
                                       "representative-gas hipot qualification; lumped coil node, hot-spot offset TBD"},
        "inner_core_FeCo2V": {"nodes": ["PI"], "limit_C": None, "necessary_ceiling_C": M1.MATERIALS["Hiperco_50"]["curie_C"][0],
                              "ceiling_source": f"{DELIVERABLES['H21_PY']} MATERIALS.Hiperco_50.curie_C "
                                                f"({M1.MATERIALS['Hiperco_50']['curie_C'][1]})",
                              "validation": "USE LIMIT TBD - requires sourced B_sat(T) of the FeCo-2V grade (row 76); "
                                            "the Curie point is an absolute ceiling, not a use limit"},
        "outer_iron": {"nodes": ["PO", "BP"], "limit_C": None, "necessary_ceiling_C": M5.CURIE_C,
                       "ceiling_source": f"{DELIVERABLES['H25_PY']} CURIE_C (EXT-NBS-ARMCO1967 p. 288, inferred)",
                       "validation": "USE LIMIT TBD - requires sourced B_sat(T) of the pure-iron grade (row 76)"},
        "anode": {"nodes": ["AN"], "limit_C": None,
                  "validation": "TBD - requires the anode material's oxidation/electrical/creep data (row 87; 316L "
                                "engineering baseline only, row 106)"},
        "cathode_body": {"nodes": ["CB"], "limit_C": None,
                         "validation": "TBD - schemas/thermal_life/limits_v1.json cathode_assembly_temperature_limit is TBD"},
        "rule": {"margin_K": MARGIN_K, "heat_load_margin": HEAT_LOAD_MARGIN,
                 "design_ceiling": "limit - 50 K (row 86); the same value is the score-bearing abort temperature (UBQ-06)"},
    }


def _ranges(pm, case, config, t_mount_C, lever, kfac):
    M5 = h25()
    rg = dict(M5.ranges_for(case, pm))
    for k in LOAD_KEYS:
        lo, hi = rg[k]
        rg[k] = (lo * HEAT_LOAD_MARGIN, hi * HEAT_LOAD_MARGIN)
    lo, hi = rg["P_mag_W"]
    rg["P_mag_W"] = (lo, hi * kfac * HEAT_LOAD_MARGIN)
    if config == "hall_icp_neutralizer":
        # no C1 in the primary A9 architecture (OQ-A902-04); ICP heat into H-1 is reported as influence coefficients
        rg["Q_cath_W"] = (0.0, 0.0)
        rg["A_cath_ext_m2"] = (0.0, 0.0)
    if t_mount_C is not None:
        rg["T_mount_orbit_K"] = (t_mount_C + T0C, t_mount_C + T0C)
    for k, (op, v) in LEVERS[lever]["set"].items():
        if k not in rg:
            raise KeyError(f"lever input {k} not in the H2-5 range set")
        lo, hi = rg[k]
        if op == "fix":
            if not (min(lo, hi) - 1e-12 <= v <= max(lo, hi) + 1e-12):
                raise ValueError(f"lever {lever} sets {k} = {v} outside the H2-5 range {rg[k]} (never invented)")
            rg[k] = (v, v)
        elif op == "scale_hi":
            rg[k] = (lo, hi * v)
        else:
            raise ValueError(op)
    return rg


SOLVE_T0_K = (450.0, 300.0, 600.0, 800.0)   # 450 K = the H2-5 default initial guess; others only on a domain excursion
RETRIES = {"count": 0}


def _run(x, fx, case, finish, P_d):
    """H2-5 run() with an initial-guess retry: if the Newton path of the imported solver leaves the tabulated iron k(T)
    domain (ValueError, no extrapolation) the SAME solver is restarted from another initial temperature; a returned
    state has passed the H2-5 residual and energy-balance checks, so the answer does not depend on the guess."""
    M5 = h25()
    last = None
    for T0 in SOLVE_T0_K:
        try:
            loads, links, bnd, km, coil20 = M5.assemble(x, fx, case, finish, P_d)
            T, info = M5.solve(loads, links, bnd, km, coil20, T0=T0)
            if T0 != SOLVE_T0_K[0]:
                RETRIES["count"] += 1
            out = dict(T)
            out["Q_mount_W"] = x["G_mount_W_K"] * (T["BP"] - x[M5.MOUNT_KEY[case]])
            return out, info
        except (ValueError, RuntimeError, np_linalg_error()) as e:  # noqa: PERF203
            last = e
    raise RuntimeError(f"thermal network did not converge from any initial guess (MODEL_ERROR): {last}")


def _solve_retry(loads, links, bnd, km, coil20):
    M5 = h25()
    last = None
    for T0 in SOLVE_T0_K:
        try:
            T, _ = M5.solve(loads, links, bnd, km, coil20, T0=T0)
            return T
        except (ValueError, RuntimeError, np_linalg_error()) as e:  # noqa: PERF203
            last = e
    raise RuntimeError(f"thermal network did not converge (MODEL_ERROR): {last}")


def np_linalg_error():
    import numpy as np
    return np.linalg.LinAlgError


def _envelope(rg, fx, case, finish, P_d):
    """Same method as H2-5 envelope(): OAT signs at the range midpoints, then per-output adverse corners."""
    M5 = h25()
    nom = {k: 0.5 * (lo + hi) for k, (lo, hi) in rg.items()}
    T_nom, _ = _run(nom, fx, case, finish, P_d)
    sens = {}
    for k, (lo, hi) in rg.items():
        if hi == lo:
            continue
        xl, xh = dict(nom), dict(nom)
        xl[k], xh[k] = lo, hi
        Tl, _ = _run(xl, fx, case, finish, P_d)
        Th, _ = _run(xh, fx, case, finish, P_d)
        sens[k] = {o: Th[o] - Tl[o] for o in M5.OUTS}
    res, corners = {}, {}
    for o in M5.OUTS:
        xmax = {k: (rg[k][1] if (k in sens and sens[k][o] >= 0) else rg[k][0]) for k in rg}
        xmin = {k: (rg[k][0] if (k in sens and sens[k][o] >= 0) else rg[k][1]) for k in rg}
        Tmax, _ = _run(xmax, fx, case, finish, P_d)
        Tmin, _ = _run(xmin, fx, case, finish, P_d)
        dom = sorted(sens, key=lambda k: -abs(sens[k][o]))[:3]
        corners[o] = xmax
        if o == "Q_mount_W":
            res[o] = {"min_W": round(Tmin[o], 1), "nominal_W": round(T_nom[o], 1), "max_W": round(Tmax[o], 1)}
        else:
            res[o] = {"T_min_C": round(Tmin[o] - T0C, 1), "T_nominal_C": round(T_nom[o] - T0C, 1),
                      "T_max_C": round(Tmax[o] - T0C, 1), "dominant_inputs": dom}
    return res, corners


def _verdict(node, e, limits):
    for lk, L in limits.items():
        if lk == "rule" or node not in L["nodes"]:
            continue
        if L["limit_C"] is not None:
            ceil = L["limit_C"] - MARGIN_K
            if e["T_max_C"] <= ceil:
                v = "CLOSES"
            elif e["T_min_C"] > ceil:
                v = "DO_NOT_CLOSE_WHOLE_ENVELOPE"
            else:
                v = "DO_NOT_CLOSE"
            return {"limit_C": L["limit_C"], "design_ceiling_C": sig(ceil, 6),
                    "margin_worst_K": round(L["limit_C"] - e["T_max_C"], 1),
                    "margin_nominal_K": round(L["limit_C"] - e["T_nominal_C"], 1), "verdict": v,
                    "nominal_closes": e["T_nominal_C"] <= ceil}
        if L.get("necessary_ceiling_C") is not None:
            ceil = L["necessary_ceiling_C"] - MARGIN_K
            return {"limit_C": None, "necessary_ceiling_C": L["necessary_ceiling_C"],
                    "necessary_check": "PASS" if e["T_max_C"] <= ceil else "FAIL",
                    "verdict": "OPEN_LIMIT_TBD"}
        return {"limit_C": None, "verdict": "OPEN_LIMIT_TBD"}
    raise KeyError(node)


def _best_row85(icp, n, row85_ok):
    """Lowest worst-case T_max of a node over the lever sets whose corner mount heat stays within the largest row-85
    allowable-heat case, with its margin to the design ceiling (negative = deficit)."""
    cands = []
    for lv, ok in sorted(row85_ok.items()):
        if not ok:
            continue
        recs = [icp[lv][c]["nodes"][n] for c in icp[lv]]
        tmax = max(r["T_max_C"] for r in recs)
        ceil = recs[0].get("design_ceiling_C")
        cands.append({"lever": lv, "worst_T_max_C": tmax,
                      "margin_to_design_ceiling_K": (round(ceil - tmax, 1) if ceil is not None else None)})
    return min(cands, key=lambda c: c["worst_T_max_C"]) if cands else None


def _overall(summary, row85_ok) -> dict:
    live = {n: s for n, s in summary.items() if s["status"] != "OPEN_LIMIT_TBD"}
    joint = [lv for lv in LEVERS if lv != "LV-BASE" and row85_ok.get(lv) and
             all(lv in s["levers_that_close_every_case"] or s["status"] == "CLOSES" for s in live.values())]
    base_ok = all(s["status"] == "CLOSES" for s in live.values()) and row85_ok.get("LV-BASE")
    return {"nodes_with_live_limits": sorted(live),
            "baseline_closes_all_live_nodes_and_row85": bool(base_ok),
            "lever_sets_closing_all_live_nodes_and_row85_100W": joint,
            "status": ("CLOSES" if base_ok else "CLOSES_WITH_LEVERS" if joint else "OPEN"),
            "open_items": ["pole/core and anode use limits TBD (OPEN_LIMIT_TBD)",
                           "supplier limits not validated (every CLOSES is conditional)",
                           "H-1 geometry not frozen (v1 ECHT-analog geometry used)"]}


INFLUENCE_LEVERS = ("LV-BASE", "LV-ALL-NO-MOUNT", "LV-ALL", "LV-ALL-ISO")


def _influence(ck, fx, P_d, limits):
    """dT/dQ for +1 W at PO or BP, re-solved at each node's hot corner; linearised allowance to the design ceiling."""
    M5 = h25()
    infl = {}
    for label, (case, rg, corners) in ck.items():
        per = {}
        for n in ("WI", "WO", "CI", "CO"):
            x = corners[n]
            loads, links, bnd, km, coil20 = M5.assemble(x, fx, case, FINISH_BASE, P_d)
            T0 = _solve_retry(loads, links, bnd, km, coil20)
            d = {}
            for inj in ("PO", "BP"):
                l2 = dict(loads)
                l2[inj] = l2[inj] + 1.0
                T1 = _solve_retry(l2, links, bnd, km, coil20)
                d[inj] = T1[n] - T0[n]
            ceil = [L for k, L in limits.items() if k != "rule" and n in L["nodes"]][0]["limit_C"] - MARGIN_K
            head = ceil - (T0[n] - T0C)
            per[n] = {"dT_dQ_K_per_W": {k: round(v, 4) for k, v in d.items()},
                      "headroom_to_ceiling_K": round(head, 1),
                      "Q_NEU_allowable_W_linearised": {k: (round(head / v, 1) if head > 0 and v > 0 else 0.0)
                                                       for k, v in d.items()}}
        infl[label] = per
    allow = {}
    for inj in ("PO", "BP"):
        allow[inj] = {"min_over_nodes": min(infl[c][n]["Q_NEU_allowable_W_linearised"][inj] for c in infl for n in infl[c])}
        for n in ("WI", "WO", "CI", "CO"):
            allow[inj][n] = min(infl[c][n]["Q_NEU_allowable_W_linearised"][inj] for c in infl)
    return infl, allow


def recompute_thermal() -> dict:
    M5 = h25()
    RETRIES["count"] = 0
    rows = M5.build_parameters()
    v1 = {p["id"]: p for p in load(DELIVERABLES["H25"])["design_parameters"]}
    for r in rows:   # the imported builder code must match the committed, verified v1 JSON
        if r["id"] not in v1 or v1[r["id"]]["value"] != r["value"]:
            raise RuntimeError(f"H2-5 builder parameter {r['id']} differs from the verified v1 JSON")
    pm = M5.param_map(rows)
    fx = M5.fixed_inputs(pm)
    P_d = pm["P_d_max_W"]["value"]
    kf = kulgrid_factor()
    limits = thermal_limits()
    # reproduction check of the v1 11.2 K BN-wall case with the v1 inputs and the imported solver
    rg_v1 = M5.ranges_for("orbit_hot", pm)
    e_v1, _ = _envelope(rg_v1, fx, "orbit_hot", FINISH_REF, P_d)
    v1_marg = [m for m in load(DELIVERABLES["H25"])["margins_at_P_d_max"]
               if m["case"] == "orbit_hot" and m["finish"] == FINISH_REF and m["node"] == "WI"][0]
    if abs(e_v1["WI"]["T_max_C"] - v1_marg["T_max_C"]) > 0.15:   # v1 rounds in K, this lane in degC
        raise RuntimeError("H2-5 v1 BN-wall hot corner not reproduced")
    repro = {"case": "orbit_hot / bare_machined_stainless / WI (v1 rules)", "v1_T_max_C": v1_marg["T_max_C"],
             "v1_margin_worst_K": v1_marg["margin_worst_K"], "reproduced_T_max_C": e_v1["WI"]["T_max_C"],
             "source": src("H25", "/margins_at_P_d_max")}

    cases = [("ground", None)] + [(c, t) for c in ("orbit_hot", "orbit_cold") for t in T_MOUNT_CASES_C]
    nodes = ["AN", "WI", "WO", "PI", "PO", "BP", "CI", "CO"]
    out_cfg = {"hall_icp_neutralizer": {}, "hall_c1_reference": {}}
    corners_keep = {}
    for lever in LEVERS:
        for case, tm in cases:
            label = case if tm is None else f"{case}@T_mount={tm:g}C"
            rg = _ranges(pm, case, "hall_icp_neutralizer", tm, lever, kf["factor"])
            env, corners = _envelope(rg, fx, case, FINISH_BASE, P_d)
            rec = {"nodes": {n: dict(env[n], **_verdict(n, env[n], limits)) for n in nodes}, "Q_mount_W": env["Q_mount_W"]}
            out_cfg["hall_icp_neutralizer"].setdefault(lever, {})[label] = rec
            if lever in INFLUENCE_LEVERS:
                corners_keep.setdefault(lever, {})[label] = (case, rg, corners)
        # coating lever reference: same rules with the bare finish (baseline set only)
    for case, tm in cases:
        label = case if tm is None else f"{case}@T_mount={tm:g}C"
        rg = _ranges(pm, case, "hall_icp_neutralizer", tm, "LV-BASE", kf["factor"])
        env, _ = _envelope(rg, fx, case, FINISH_REF, P_d)
        out_cfg["hall_icp_neutralizer"].setdefault("LV-BASE-BARE-FINISH(reference)", {})[label] = {
            "nodes": {n: dict(env[n], **_verdict(n, env[n], limits)) for n in nodes}, "Q_mount_W": env["Q_mount_W"]}
    # hall_c1_reference is a ground comparison article (OQ-A902-04): ground case, C1 heat coupled as in v1 (bound)
    for lever in ("LV-BASE", "LV-ALL-NO-MOUNT"):
        rg = _ranges(pm, "ground", "hall_c1_reference", None, lever, kf["factor"])
        env, _ = _envelope(rg, fx, "ground", FINISH_BASE, P_d)
        out_cfg["hall_c1_reference"][lever] = {"ground": {
            "nodes": {n: dict(env[n], **_verdict(n, env[n], limits)) for n in nodes + ["CB"]},
            "Q_mount_W": env["Q_mount_W"]}}

    icp = out_cfg["hall_icp_neutralizer"]
    # mount heat vs row 85 allowable conducted heat (orbit cases), every lever set
    mount = {}
    for lever in LEVERS:
        for c, rec in icp[lever].items():
            if not c.startswith("orbit"):
                continue
            q = rec["Q_mount_W"]
            mount.setdefault(lever, {})[c] = {"Q_mount_W": q, "within_allowable_W": {
                f"{a:g}": ("CLOSES" if q["max_W"] <= a else "DO_NOT_CLOSE") for a in Q_ALLOW_CASES_W}}
    row85_ok = {lv: all(v["within_allowable_W"][f"{max(Q_ALLOW_CASES_W):g}"] == "CLOSES" for v in mount[lv].values())
                for lv in mount}
    # closure summary (hall_icp_neutralizer, flight-representative cases)
    summary = {}
    for n in nodes:
        base = [icp["LV-BASE"][c]["nodes"][n] for c in icp["LV-BASE"]]
        vb = {b["verdict"] for b in base}
        closing = [lv for lv in LEVERS if lv != "LV-BASE" and
                   all(icp[lv][c]["nodes"][n]["verdict"] == "CLOSES" for c in icp[lv])]
        single = [lv for lv in closing if not lv.startswith("LV-ALL")]
        if vb == {"OPEN_LIMIT_TBD"}:
            status = "OPEN_LIMIT_TBD"
        elif vb == {"CLOSES"}:
            status = "CLOSES"
        elif single:
            status = "CLOSES_WITH_SINGLE_LEVER"
        elif closing:
            status = "CLOSES_ONLY_WITH_COMBINED_LEVERS"
        else:
            status = "DO_NOT_CLOSE_OPEN"
        worst = max(base, key=lambda b: b["T_max_C"])
        summary[n] = {"status": status, "baseline_worst_T_max_C": worst["T_max_C"],
                      "baseline_worst_margin_K": worst.get("margin_worst_K"),
                      "baseline_nominal_T_C": [min(b["T_nominal_C"] for b in base), max(b["T_nominal_C"] for b in base)],
                      "levers_that_close_every_case": closing,
                      "closing_levers_within_row85_100W": [lv for lv in closing if row85_ok[lv]],
                      "best_row85_compatible": _best_row85(icp, n, row85_ok),
                      "necessary_check": sorted({b.get("necessary_check") for b in base if b.get("necessary_check")})}
    # 11.2 K BN-wall case resolution
    wi = summary["WI"]
    bn_case = {"v1": repro, "rule": "T_max <= 900 - 50 = 850 degC at every bounding corner with 1.2 x heat loads",
               "baseline_worst_T_max_C": wi["baseline_worst_T_max_C"], "baseline_worst_margin_K": wi["baseline_worst_margin_K"],
               "status": ("RESOLVED_BY_BASELINE" if wi["status"] == "CLOSES" else
                          "RESOLVED_WITH_LEVERS" if wi["status"].startswith("CLOSES") else "OPEN"),
               "levers_that_close": wi["levers_that_close_every_case"],
               "closing_levers_within_row85_100W": wi["closing_levers_within_row85_100W"],
               "outer_wall": {"status": summary["WO"]["status"], "baseline_worst_T_max_C": summary["WO"]["baseline_worst_T_max_C"],
                              "levers_that_close": summary["WO"]["levers_that_close_every_case"]}}
    # ICP heat into H-1: influence coefficients at each node's hot corner (baseline) and linearised allowance
    infl_all, allow_all = {}, {}
    for lever_i in INFLUENCE_LEVERS:
        infl_all[lever_i], allow_all[lever_i] = _influence(corners_keep[lever_i], fx, P_d, limits)
    return {
        "method": ("H2-5 builder imported read-only (build_parameters, ranges_for, run/assemble/solve: 9-node steady "
                   "network, Newton solve, energy-balance closure check); this lane re-applies the H2-5 envelope "
                   "method (one-at-a-time signs at the midpoints, then per-output adverse corners; LHS not repeated) "
                   "with the owner rules: dissipated loads (anode/wall/pole fractions of P_d, coil I^2R, cathode) x 1.2 "
                   "(row 86), coil I^2R upper bound also x the ceramic-conductor factor, exterior finish = the "
                   "high-emittance Z-93 option (row 84), EM-only magnetic circuit (row 78: the permanent-magnet rows "
                   "of v1 are dropped), mounting interface at 20/40/60 degC (row 85). Environmental solar/albedo/OLR "
                   "inputs are the v1 hot/cold bounds, not scaled. P_d = the whole 1350 W internal allocation (H25-02 "
                   "bound, conservative under OQ-A902-03). Geometry stays the v1 ECHT-analog set (H25-12..14) - the "
                   "H-1 geometry is not frozen (H2-1 window), a stated limitation"),
        "rule": {"margin_K": MARGIN_K, "heat_load_margin": HEAT_LOAD_MARGIN,
                 "sources": [row(86, ("50 K", "20%")), a91("UBQ-06", ("minus 50 K",))],
                 "closure_test": ("CLOSES when the adverse-corner T_max <= validated limit - 50 K in every evaluated "
                                  "case; limits are the recorded supplier values (NOT_VALIDATED), so a CLOSES verdict "
                                  "is conditional on their validation; never relaxed")},
        "limits": limits,
        "coil_conductor_factor": kf,
        "reproduction_check": repro,
        "cases": [c if t is None else f"{c}@T_mount={t:g}C" for c, t in cases],
        "levers": {k: {"what": v["what"], "set": {kk: list(vv) for kk, vv in v["set"].items()}} for k, v in LEVERS.items()},
        "results": out_cfg,
        "closure_summary_hall_icp_neutralizer": summary,
        "bn_wall_11_2K_case": bn_case,
        "mount_heat_vs_row85": mount,
        "row85_compatible_levers_100W": sorted(lv for lv, ok in row85_ok.items() if ok),
        "overall": _overall(summary, row85_ok),
        "icp_heat_into_h1": {
            "note": ("ICP module heat entering H-1 is TBD (ICP-43 total module heat load, PENDING P_d,max). Influence "
                     "coefficients: +1 W injected at the outer front pole PO (nearest IP-EXIT/IP-NEU) or at the back "
                     "plate BP, re-solved at each node's baseline hot corner; allowance = headroom to the design ceiling "
                     "/ coefficient (linearised, model-derived; 0 where the node does not close). Radiative links "
                     "make the response super-linear, so the allowance is an upper estimate valid for small Q only; "
                     "values of the order of the discharge allocation or above are not meaningful and must be "
                     "re-solved with the actual ICP-43 load"),
            "per_lever_and_case": infl_all,
            "min_allowance_W": allow_all},
        "solver_initial_guess_retries": RETRIES["count"],
        "evidence_class": "model-derived",
        "not_a_prediction": "bounding thermal envelope on allocation bounds and analog heat fractions; no plasma state",
    }


# ----------------------------------------------------------------------------------------------------------------------
# small deterministic derivations
# ----------------------------------------------------------------------------------------------------------------------
def derived_small() -> dict:
    kp = old("H22", "H22-22")          # keeper pulse class [300, 600] V
    v_hi = kp["value"][1]
    icp46 = 1.5 * v_hi                 # A9.1 ICP-46: 1.5 x upper operating pulse
    h24_25 = old("H24", "H24-25")      # V_d range [180, 350] V
    h24_01 = old("H24", "H24-01")      # 1500 W
    h24_27 = old("H24", "H24-27")      # 8.333 A
    alloc = 1350.0                     # row 109 / OQ-A902-07
    s44 = old("H22", "H22-44")         # start-flow controller full scale 1.0 mg/s
    fs = s44["value"]
    xe_n3 = fs * 1e-6 * 120.0 * 3 * 1e3   # g: mdot [kg/s] x 120 s x 3 attempts -> g
    xe_n2 = fs * 1e-6 * 120.0 * 2 * 1e3
    return {
        "icp46_isolation_basis_V": {"value": icp46, "units": "V", "formula": "1.5 x upper keeper pulse 600 V",
                                    "check": "equals the A9.1 ICP-46 900 V basis", "source": [kp["source"], a91("ICP-46", ("900 V",))],
                                    "evidence_class": "owner-allocation"},
        "flight_discharge_output_current_bound_A": {
            "value": sig(alloc / h24_25["value"][0], 5), "units": "A",
            "formula": "internal design allocation 1350 W (row 109, OQ-A902-07) / V_d,min 180 V (H24-25): an upper bound "
                       "of the discharge-supply output current (supply efficiency <= 1, every other load >= 0); not a "
                       "predicted discharge current",
            "source": [row(109, ("1.35 kW",)), a91("OQ-A902-07", ("1350",)), h24_25["source"]],
            "evidence_class": "model-derived"},
        "rfp_bound_current_A": {"value": sig(h24_01["value"] / h24_25["value"][0], 5), "units": "A",
                                "formula": "1500 W (H24-01) / 180 V (H24-25); equals the verified H24-27 lab rating",
                                "check_H24_27": sig(h24_27["value"], 5),
                                "source": [h24_01["source"], h24_25["source"], h24_27["source"]],
                                "evidence_class": "model-derived"},
        "c1_ignition_dwell_xe_bound_g": {
            "value": {"attempts_3_literal": sig(xe_n3, 4), "attempts_2_shorthand": sig(xe_n2, 4)}, "units": "g per start",
            "formula": "start-flow controller full scale (H22-44, 1.0 mg/s Xe, an upper bound of any commanded start "
                       "flow) x 120 s dwell cap (row 93) x attempts (1 + two retries = 3 literal; 2 per the '120 s x 2' "
                       "shorthand; owner question OQ-A907-01)",
            "source": [s44["source"], row(93, ("120 s", "two retries"))],
            "evidence_class": "model-derived",
            "note": "bound on ignition-dwell Xe only; purge/preheat Xe are separate PHASE_TOTAL_FLOW terms (row 42)"},
    }


# ----------------------------------------------------------------------------------------------------------------------
# revision register
# ----------------------------------------------------------------------------------------------------------------------
def R(rid, lane, item, topic, old_, new, units, driver, basis, evidence_class, status, freeze_point,
      recomputation=None, applies_to=CONFIGURATIONS, note=None):
    if status not in REV_STATUSES:
        raise ValueError(f"{rid}: status {status!r}")
    if freeze_point not in FREEZE_POINTS:
        raise ValueError(f"{rid}: freeze point {freeze_point!r}")
    if evidence_class is not None and evidence_class.split()[0] not in EVIDENCE_CLASSES:
        raise ValueError(f"{rid}: evidence class {evidence_class!r}")
    if not driver:
        raise ValueError(f"{rid}: no driver")
    for c in applies_to:
        if c not in CONFIGURATIONS:
            raise ValueError(c)
    d = {"id": rid, "h2_lane": lane, "h2_item": item, "topic": topic, "old": old_, "new": new, "units": units,
         "driver": driver, "recomputation": recomputation, "basis": basis, "evidence_class": evidence_class,
         "status": status, "freeze_point": freeze_point, "applies_to": list(applies_to)}
    if note:
        d["note"] = note
    return d


def revision_register(rc: dict) -> list:
    th = rc["h25_thermal_rerun"]
    h1 = rc["h21_central_bore"]
    ds = rc["small"]
    lim = th["limits"]
    ICPo = ("hall_icp_neutralizer",)
    C1o = ("hall_c1_reference",)
    ext_nom = {r["h_mm"]: r["external_c1_magnetic_floor_mm"] for r in h1["rows"]}
    L = []
    # ---------------------------------------------------------------- (1) external C1: H2-1
    L.append(R("REV-01", "H2-1", "H21-22", "central-cathode floor on the channel mean diameter",
               old("H21", "H21-22"),
               {"requirement": "no central-cathode constraint (external C1 reference, row 79); the only remaining "
                               "inner-core packaging floor is the inner-coil build with a solid core (no bore)",
                "value": ext_nom, "binding_inside_window": not any(
                    r["external_floor_binding"]["nominal_assumptions"] or r["external_floor_binding"]["worst_case_assumptions"]
                    for r in h1["rows"])},
               "mm", [row(79, ("EXTERNAL C1", "mean diameter")), lane_item("A9-03", "ID-12")],
               "H2-1 lumped magnetic-circuit scan re-run read-only without the cathode bore (recomputations.h21_central_bore)",
               "model-derived", "REVISED_RECOMPUTED", "LOCK-1", recomputation="recomputations/h21_central_bore"))
    L.append(R("REV-02", "H2-1", "H21-06", "channel inner-diameter window note",
               old("H21", "H21-06", "note"),
               {"requirement": "lower end NOT further constrained by a central cathode (row 79); window value unchanged",
                "value": old("H21", "H21-06")["value"]},
               "mm", [row(79, ("EXTERNAL C1",))], "row 79 removes the central cathode", "model-derived",
               "REVISED_RECOMPUTED", "LOCK-1", recomputation="recomputations/h21_central_bore"))
    L.append(R("REV-03", "H2-1", "H21-11", "H-1 exit face: downstream/coaxial neutralizer interface (IP-EXIT)",
               old("H21", "H21-11"),
               {"requirement": "IP-EXIT = H-1 exit plane z = L (A9.1 A9-03-planes); the exit face provides the "
                               "datum and keep-out for the downstream/coaxial electron-source module datum IP-NEU on "
                               "KC-1; the Hall head stays neutralizer-agnostic (no C1 bore, no C1 mount on H-1)",
                "value": "IP-EXIT at z = L; IP-NEU at z_NEU = z - L >= 0 (ICP-02, TBD)"},
               "mm", [row(79, ("neutralizer-agnostic",)), a91("A9-03-planes", ("IP-EXIT", "IP-NEU")),
                      lane_item("A9-03", "ICP-01"), lane_item("A9-03", "ICP-02")],
               "A9.1 plane names; historical IP-DN unchanged", "assumed (convention)", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-04", "H2-1", "H21-19", "coil insulation family",
               old("H21", "H21-19"),
               {"requirement": "CERAMIC-insulated copper baseline for the hot/vacuum development coil; no polyimide as "
                               "the primary hot/AO-adjacent solution; Ni-clad (e.g. Kulgrid) allowed only with a "
                               "measured magnetic perturbation; 150 V AC turn rating = minimum procurement screen, "
                               "subject to representative-gas hipot",
                "value": {"continuous_limit_C (supplier, not validated)": lim["coil_ceramic"]["limit_C"],
                          "design_ceiling_C": sig(lim["coil_ceramic"]["limit_C"] - MARGIN_K, 6)}},
               "degC", [row(77, ("CERAMIC", "150 V AC")), row(86, ("50 K",))],
               "MCQ-EM-03 continuous rating (HT Wire, both conductors) minus the row-86 margin", "assumed",
               "OWNER_GIVEN", "NOW"))
    L.append(R("REV-05", "H2-1", "H21-20", "inner core / inner pole material and hot-use limit",
               old("H21", "H21-20"),
               {"requirement": "FeCo-2V inner (Hiperco 50 class) accepted as the H-1 engineering baseline; hot-use "
                               "limit derived from sourced B_sat(T) with >= 50 K margin",
                "value": f"{TBD} sourced B_sat(T) of the selected FeCo-2V grade (necessary ceiling only: Curie "
                         f"{lim['inner_core_FeCo2V']['necessary_ceiling_C']:g} degC - 50 K)"},
               "degC", [row(76, ("FeCo-2V",)), row(86, ("50 K",))], "row 76", "assumed", "OWNER_GIVEN", "LOCK-1"))
    L.append(R("REV-06", "H2-1", "H21-21", "outer core / back plate / outer pole material and hot-use limit",
               old("H21", "H21-21"),
               {"requirement": "pure-iron outer circuit accepted; hot-use limit from sourced B_sat(T) with >= 50 K margin",
                "value": f"{TBD} sourced B_sat(T) of the pure-iron grade (necessary ceiling only: Curie "
                         f"{lim['outer_iron']['necessary_ceiling_C']:g} degC - 50 K)"},
               "degC", [row(76, ("pure-iron outer",)), row(86, ("50 K",))], "row 76", "assumed", "OWNER_GIVEN", "LOCK-1"))
    L.append(R("REV-07", "H2-1", "H21-12", "magnetic topology and pole sets",
               old("H21", "H21-12"),
               {"requirement": "T2 magnetically shielded baseline; the unshielded pole set only as an engineering "
                               "comparison, never silently the score-bearing article; MC-1 electromagnet ONLY (no "
                               "permanent-magnet assistance on H-1)", "value": "T2 + EM-only"},
               "-", [row(74, ("shielded topology T2",)), row(78, ("EM ONLY",))], "rows 74, 78", "assumed",
               "OWNER_GIVEN", "NOW"))
    L.append(R("REV-08", "H2-1", "H21-07", "channel length / width upper bound",
               old("H21", "H21-07"), {"requirement": "L/h <= 12 accepted", "value": 12.0}, "-",
               [row(75, ("12",))], "row 75", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-09", "H2-1", "H21-10", "adjustable-anode development insert",
               old("H21", "H21-10"),
               {"requirement": "allowed only before score-bearing S1; final anode position/geometry frozen before S1 data",
                "value": "pre-S1 only"}, "-", [row(75, ("before score-bearing S1",))], "row 75", "owner-allocation",
               "OWNER_GIVEN", "LOCK-1"))
    L.append(R("REV-10", "H2-1", "H21-15", "design factors (B headroom, working flux, discharge share)",
               old("H21", "H21-15"),
               {"requirement": "B-headroom 1.5, working flux 0.7 B_sat and discharge share >= 0.5 accepted as "
                               "engineering factors until verified", "value": {"B_headroom": 1.5, "B_work/B_sat": 0.7,
                                                                               "discharge_share_min": 0.5}},
               "-", [row(80, ("1.5", "0.7", "0.5"))], "row 80", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-11", "H2-1", "H21-28", "hot-state B reference sensor on MC-1",
               old("H21", "H21-28"),
               {"requirement": "install a hot-state B reference sensor/measurement provision traceable to coil current "
                               "and temperature", "value": "required"}, "-", [row(82, ("hot-state B",))], "row 82",
               "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-12", "H2-1", "H21-01", "channel design flow for neutral-density sizing",
               old("H21", "H21-01"),
               {"requirement": "nominal channel neutral-density sizing around ~1.3 mg/s delivered atmospheric flow; "
                               "operability/thermal characterization from ~0.38 to ~3.2 mg/s; no flight-qualification "
                               "claim before measurement",
                "value": {"nominal_flow_mg_s_approx": 1.3,
                          "H2-1 neutral density at the nearest tabulated flow (design_case_max 1.287 mg/s), m^-3":
                              old_at("H21", "/channel/neutral_density_in_window/design_case_max/n_n_m3", "channel.n_n")["value"]}},
               "mg/s; m^-3", [row(73, ("1.3 mg/s", "0.38", "3.2"))],
               "row 73; density copied from the H2-1 channel table (flow-scaled xenon rule, a hypothesis for air)",
               "model-derived", "OWNER_GIVEN", "LOCK-1"))
    # ---------------------------------------------------------------- (1) external C1: H2-2
    L.append(R("REV-13", "H2-2", "H22-01", "C1 mounting location",
               old("H22", "H22-01"),
               {"requirement": "L-EXTERNAL: C1 is an external reference module on the shared kinematic carrier KC-1 "
                               "(datum IP-C1) of the GROUND comparison article; not installed in the primary A9 flight "
                               "architecture (no combined C1 + ICP flight installation); a flight C1 integration belongs "
                               "to the fallback architecture hall_c1_reference and needs its own closures",
                "value": "L-EXTERNAL (ground article, KC-1)"},
               "-", [row(79, ("EXTERNAL C1",)), row(17, ("downstream electron-source module",)),
                     a91("OQ-A902-04", ("no combined flight C1 + ICP",)), lane_item("A9-03", "ID-14")],
               "row 79 reverses the preliminary L-CENTRAL (H22-OQ-01 / H2-1 Q6)", "owner-allocation", "OWNER_GIVEN",
               "NOW", applies_to=C1o))
    L.append(R("REV-14", "H2-2", "H22-03", "C1 orifice position",
               old("H22", "H22-03"),
               {"requirement": "orifice position (r, z) relative to IP-EXIT, recorded per installation; frozen on the "
                               "interface control drawing", "value": f"{TBD} ICP-05 (LOCK-1)"},
               "mm", [lane_item("A9-03", "ICP-05"), a91("A9-03-planes", ("IP-EXIT",))], "A9-03 ICP-05",
               None, "TBD", "LOCK-1", applies_to=C1o))
    L.append(R("REV-15", "H2-2", "H22-04", "inner-core bore for L-CENTRAL",
               old("H22", "H22-04"), {"requirement": "not applicable (no central cathode)", "value": None},
               "mm", [row(79, ("EXTERNAL C1",))], "row 79", None, "SUPERSEDED_FOR_A9", "NOW", applies_to=C1o))
    L.append(R("REV-16", "H2-2", "H22-05", "C1 service-line routing",
               old("H22", "H22-05"),
               {"requirement": "C1 lines (heater +/-, keeper, cathode common, tube TC, Xe) run in the stand service "
                               "bundle to the C1 module on KC-1; live in hall_c1_reference, matched sham in "
                               "hall_icp_neutralizer; no routing through the H-1 inner core or any pre-ionizer slot",
                "value": "SVC-A9 bundle (see REV-33)"},
               "-", [row(133, ("matched sham",)), row(79, ("EXTERNAL C1",))], "rows 79, 133", "assumed",
               "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-17", "H2-2", "H22-10", "magnetic field at the C1 orifice",
               old("H22", "H22-10"),
               {"requirement": "set by the MC-1 fringe field at the external module position; FEMM + measured map",
                "value": f"{TBD} FEMM of MC-1 (H2-1) and the measured B map at IP-C1 (ID-13)"},
               "G", [row(79, ("EXTERNAL C1",)), lane_item("A9-03", "ID-13")], "external location", None, "TBD",
               "LOCK-1", applies_to=C1o))
    L.append(R("REV-18", "H2-2", "H22-18", "C1 conduction path",
               old("H22", "H22-18"),
               {"requirement": "C1 tube -> module flange -> KC-1 carrier (not the H-1 inner core); C1 radiation onto "
                               "the inner coil is eliminated; the H2-5 C1-to-H-1 coupling is kept only as a "
                               "conservative bound in the hall_c1_reference ground case (recomputations.h25_thermal_rerun)",
                "value": "carrier path"},
               "-", [row(79, ("EXTERNAL C1",))], "row 79", "assumed", "REVISED_PROPOSED", "LOCK-1",
               recomputation="recomputations/h25_thermal_rerun", applies_to=C1o))
    L.append(R("REV-19", "H2-2", "H22-28", "heated vs heaterless C1",
               old("H22", "H22-28"),
               {"requirement": "HEATED Xe-fed LaB6 C1 for the reference/fallback; heater command/power stated at every "
                               "start-up step; until measured, a TBD heater counts as ON at conservative booked power",
                "value": "heated"}, "-",
               [row(49, ("HEATED C1",)), a91("SEQ-heater", ("ON at conservative",))], "row 49; A9.1 SEQ-heater",
               "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1o))
    L.append(R("REV-20", "H2-2", "H22-30", "isolation valves in series on the flight cathode branch",
               old("H22", "H22-30"),
               {"requirement": "two independent isolation valves in series on the flight high-pressure Xe/cathode "
                               "branch (applies to any flight C1/Xe branch; none in the primary A9 ICP flight branch)",
                "value": 2}, "-", [row(90, ("two independent isolation valves",)), row(55, ("dual series isolation",))],
               "rows 55, 90", "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1o))
    L.append(R("REV-21", "H2-2", "H22-22", "keeper pulse ignition capability and its isolation (ICP-46)",
               old("H22", "H22-22"),
               {"requirement": "current-limited pulsed keeper ignition 300-600 V class with interlocks and recorded "
                               "pulse energy; isolation: design basis 900 V (1.5 x 600 V); development hipot 1.0 kV DC "
                               "at representative pressure/gas, no flashover/breakdown, leakage recorded; separate 600 V "
                               "pulse-waveform test; applies to keeper lead, feedthrough, connectors, harness and "
                               "isolation to cathode common / module body / facility ground; does not replace ICP-44; "
                               "flight level only revisable upward without controlled justification",
                "value": {"pulse_V": old("H22", "H22-22")["value"], "design_basis_V": ds["icp46_isolation_basis_V"]["value"],
                          "hipot_V_DC": 1000.0, "pulse_test_V": 600.0}},
               "V", [row(89, ("300–600 V",)), a91("ICP-46", ("900 V", "1.0 kV"))], "A9.1 ICP-46",
               "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1o))
    L.append(R("REV-22", "H2-2", "H22-35", "dielectric break on the cathode Xe line",
               old("H22", "H22-35"),
               {"requirement": "rated for the cathode-common-to-ground potential envelope plus margin; where the break "
                               "shares the keeper feedthrough/harness path it takes the ICP-46 levels; any gas break "
                               "spanning the Paschen region is qualified per the row-105 practice (~1 kV DC at "
                               "representative pressure/gas, segmented/porous geometry)",
                "value": f"{TBD} cathode-common potential envelope (S1a) and the LOCK-1 margin"},
               "V", [row(105, ("1 kV DC", "segmented/porous")), a91("ICP-46", ("900 V",))], "rows 105; A9.1 ICP-46",
               None, "TBD", "LOCK-1", applies_to=C1o))
    L.append(R("REV-23", "H2-2", "H22-09", "keeper / orifice-plate material",
               old("H22", "H22-09"),
               {"requirement": "no graphite as the flight baseline for an O/AO-exposed keeper; screen refractory / "
                               "oxygen-resistant / ceramic-shielded candidates with biased exposure coupons; freeze "
                               "only after erosion/oxidation evidence",
                "value": f"{TBD} biased coupon erosion/oxidation evidence"}, "-",
               [row(94, ("Do not use graphite",))], "row 94", None, "OWNER_GIVEN", "after-evidence", applies_to=C1o))
    L.append(R("REV-24", "H2-2", "H22-47", "flow step for the spot-mode minimum-flow search",
               old("H22", "H22-47"),
               {"requirement": "0.005 mg/s flow-step resolution with pre-registered stopping criteria (rule form LOCK-1)",
                "value": 0.005}, "mg/s", [row(92, ("0.005 mg/s",))], "row 92", "owner-allocation", "OWNER_GIVEN",
               "NOW", applies_to=C1o))
    L.append(R("REV-25", "H2-2", "H22-27", "ignition sequence: dwell bound and Xe booking",
               old("H22", "H22-27"),
               {"requirement": "vendor/design-qualified purge and ignition flow; each ignition dwell capped at 120 s, at "
                               "most two retries (preliminary protocol); final bound frozen before score-bearing C1 "
                               "testing; all Xe booked (PHASE_TOTAL_FLOW)",
                "value": {"dwell_cap_s": 120.0, "max_retries": 2,
                          "xe_bound_g_per_start": ds["c1_ignition_dwell_xe_bound_g"]["value"]}},
               "s; g", [row(93, ("120 s", "two retries")), row(42, ("PHASE_TOTAL_FLOW",))],
               "rows 42, 93; Xe bound derived (recomputations.small)", "model-derived", "OWNER_GIVEN", "LOCK-1",
               recomputation="recomputations/small/c1_ignition_dwell_xe_bound_g", applies_to=C1o))
    L.append(R("REV-26", "H2-2", "H22-52", "cathode MFC resolution and controllers",
               old("H22", "H22-52"),
               {"requirement": "resolution <= 0.0005 mg/s and digital setpoint; two controllers (0.05-0.2 mg/s-class "
                               "steady + separate start/diode-flow controller if 0.6-0.8 mg/s retained); +/-2 % FS "
                               "conservative class in the Xe ledger until S1a shows better; installed zero check per "
                               "block and declared MFC body-temperature band",
                "value": {"resolution_mg_s": 0.0005, "controllers": 2}}, "mg/s",
               [row(98, ("0.0005",)), row(125, ("TWO controllers",)), row(96, ("±2% FS",)), row(97, ("zero check",))],
               "rows 96-98, 125", "owner-allocation", "OWNER_GIVEN", "NOW", applies_to=C1o))
    L.append(R("REV-27", "H2-2", "H22-07", "emitter temperature floor in O-bearing operation",
               old("H22", "H22-07"),
               {"requirement": "1843 K adopted as the conservative experimental floor; not a demonstrated lifetime "
                               "solution", "value": 1843.0}, "K", [row(95, ("1843 K",))], "row 95", "owner-allocation",
               "OWNER_GIVEN", "NOW", applies_to=C1o))
    L.append(R("REV-28", "H2-2", "H22-37", "cathode-common reference to ground",
               old("H22", "H22-37"),
               {"requirement": "isolated, selectable cathode-common/bleeder topology with V/I measurement; value/switching "
                               "chosen after EMC and discharge-stability bench tests",
                "value": f"{TBD} EMC and discharge-stability bench tests"}, "ohm",
               [row(91, ("DO NOT freeze a resistor value",))], "row 91", None, "TBD", "after-evidence", applies_to=C1o))
    # ---------------------------------------------------------------- (2) downstream ICP fixture: H2-6
    L.append(R("REV-29", "H2-6", "H26-40", "configuration-change procedure",
               old("H26", "H26-40", "name"),
               {"requirement": "H-1 stays bolted on the stand; a configuration change exchanges only the DOWNSTREAM "
                               "electron-source module (C1 reference module at IP-C1, ICP module at IP-NEU, or the "
                               "matched mechanical sham) on KC-1 downstream of IP-EXIT; no upstream module; historical "
                               "IP-DN unchanged", "value": True},
               "-", [row(122, ("H-1 remains bolted",)), row(17, ("swap only the downstream electron-source module",)),
                     a91("A9-03-planes", ("IP-DN unchanged",)), lane_item("A9-03", "ICP-06")],
               "rows 17, 122", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-30", "H2-6", "H26-41", "module carrier KC-1 (kinematic seat)",
               old("H26", "H26-41"),
               {"requirement": "3-point exactly-constrained seat with preload on the moving platform, downstream of "
                               "IP-EXIT; seat geometry, preload and torque procedure identical for C1 module, ICP module "
                               "and sham; datum chain IP-EXIT -> KC-1 -> IP-NEU / IP-C1 measured (CMM or gauge) at "
                               "every installation; standoff z_NEU and seat dimensions frozen at LOCK-1",
                "value": {"z_NEU_mm": f"{TBD} ICP-02 (LOCK-1)", "seat_dimensions_mm": f"{TBD} module drawings (ICP-04/07)"}},
               "mm", [row(122, ("kinematic carrier",)), lane_item("A9-03", "ICP-02"), lane_item("A9-03", "ICP-06")],
               "H2-6 concept adapted to a downstream module", "assumed", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-31", "H2-6", "H26-42", "module weight path",
               old("H26", "H26-42"),
               {"requirement": "module weight and assembly torque through KC-1 only; nothing loads the H-1 exit face; "
                               "no gas-seal joint between module and H-1 (G-REUSE: the ICP uses Hall exhaust/residual gas; "
                               "the dedicated ICP gas port stays installed and capped); the Hall-exhaust-to-ICP "
                               "pressure/conductance interface is measured, not sealed",
                "value": "carrier-borne"}, "-",
               [a91("HIQ-06", ("G-REUSE", "capped")), row(63, ("Hall-exhaust-to-ICP",)), lane_item("A9-03", "ICP-27")],
               "HIQ-06; row 63", "assumed", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-32", "H2-6", "H26-43", "moving payload on the stand",
               old("H26", "H26-43"),
               {"requirement": "stand designed for >= 25 kg moving payload; the actual configuration spread (H-1 + MC-1 "
                               "+ module + on-platform services) measured per serial and configuration; uprate/requalify "
                               "rather than trim hardware",
                "value": {"design_payload_min_kg": 25.0, "per_configuration_mass_kg": pending("A9-06", "module masses and CG")}},
               "kg", [row(116, ("25 kg",)), lane_item("A9-03", "ICP-08")], "row 116", "owner-allocation",
               "OWNER_GIVEN", "NOW"))
    L.append(R("REV-33", "H2-6", "H26-FX-03", "service-line bundle with matched shams",
               old("H26", "H26-FX-03", "description"),
               {"requirement": "SVC-A9: every line crossing the stand is present in both configurations. Live in "
                               "hall_icp_neutralizer / sham in hall_c1_reference: flexible 13.56 MHz coax (matched "
                               "routing), collector/bias leads, ICP thermocouples, ICP pressure line, capped ICP gas line, "
                               "MODULE_ID + RF interlock lines. Live in hall_c1_reference / sham in hall_icp_neutralizer: "
                               "C1 heater +/-, keeper (ICP-46 rated), cathode common, tube TC, Xe line. Low-stiffness "
                               "symmetric harp/slack loops; no uncompensated hard RF line across the moving stage; "
                               "per-configuration line tare and residual parasitic force characterized",
                "value": "SVC-A9 inventory"}, "-",
               [row(117, ("flexible RF coax",)), row(133, ("matched sham",)), lane_item("A9-03", "ICP-18"),
                lane_item("A9-03", "ID-19")], "rows 117, 133", "assumed", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-34", "H2-6", "H26-FX-03", "RF matching network location and power reference plane",
               old("H26", "H26-FX-03", "description"),
               {"requirement": "matching network OFF the moving platform; matched flexible RF coax across the stand; "
                               "directional coupler / reference plane AFTER the matching network; calibrated cable-loss "
                               "/ S-parameter correction from the coupler plane to the antenna feed; matched sham coax in "
                               "hall_c1_reference; move the match onto the platform only if S1a shows the off-platform "
                               "chain cannot meet the RF-power uncertainty requirement",
                "value": "off-platform match; coupler after match"}, "-",
               [a91("A9-03-matching", ("off the moving stand platform",)), row(72, ("13.56 MHz",))],
               "A9.1 A9-03 clarification", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-35", "H2-6", "H26-44", "heat load into H-1 + mount + module (stand thermal design bound)",
               old("H26", "H26-44"),
               {"requirement": "score-bearing configurations stay bounded by the 1500 W P_bus gate (row 108); engineering "
                               "characterization with laboratory supplies is bounded by 1.2 x (P_d,max,stand + P_RF,fwd,max "
                               "500 W + coil and bias power) (ICP-43 form, row 86 margin)",
                "value": f"{TBD} P_d,max at the stand (ICP-43 / A9-02 discharge slot)"}, "W",
               [row(108, ("1.5 kW",)), row(72, ("0–500 W",)), row(86, ("20%",)), lane_item("A9-03", "ICP-43")],
               "rows 72, 86, 108", None, "TBD", "LOCK-1"))
    L.append(R("REV-36", "H2-6", "H26-45", "electrical isolation of H-1 and modules from stand/facility ground",
               old("H26", "H26-45"),
               {"requirement": "H-1 isolation rated to 350 V + transient/qualification margin (row 81); ICP body floating "
                               "by default with the collector bias isolated and separately metered (row 70, ICP-20/23); "
                               "C1 keeper circuit to the ICP-46 levels (900 V basis, 1.0 kV DC hipot, 600 V pulse test)",
                "value": {"dc_rating_V": 350.0, "margin": f"{TBD} LOCK-1 isolation margin", "keeper_basis_V": 900.0}},
               "V", [row(81, ("350 V",)), row(70, ("floating",)), a91("ICP-46", ("900 V",))], "rows 70, 81; ICP-46",
               "owner-allocation", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-37", "H2-6", "H26-09", "bus-power channel set",
               old("H26", "H26-09"),
               {"requirement": "one metering channel per bus_power_boundary_a9_v1 slot installed in the configuration "
                               "(incl. 13.56 MHz generator DC input, matching controller, collector/bias, per-coil magnets, "
                               "C1 heater/keeper/common-tie, valves, compressor, thermal, housekeeping) plus the P_bus "
                               "1 ms gate channel (A9H-INS-09)", "value": "A9 slot set"}, "-",
               [a91("OQ-A902-01", ("1 ms",)), row(110, ("Every active load gets a bus slot",))],
               "A9-02 slots; OQ-A902-01", "assumed", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-38", "H2-6", "H26-05", "absolute thrust uncertainty target",
               old("H26", "H26-05"),
               {"requirement": "1 % standard relative uncertainty (k = 1) for a sustained reading, tested at 12 mN with "
                               "maximum representative moving payload and all service lines installed (S1a); gates use "
                               "the pre-registered one-sided treatment; revise only before LOCK-2 from metrology-only "
                               "evidence", "value": {"u_rel_k1": 0.01, "test_point_mN": 12.0}}, "-",
               [row(121, ("1%",)), row(120, ("12 mN",)), a91("UBQ-01", ("k = 1",))], "rows 120-121; UBQ-01",
               "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-39", "H2-6", "H26-16", "exploratory I_d(t) chain",
               old("H26", "H26-16"),
               {"requirement": "exploratory I_d(t) to ~60 MHz if feasible, else declare the measured bandwidth and its "
                               "anti-alias/transfer function; in hall_icp_neutralizer the 13.56 MHz drive and harmonics "
                               "lie inside this band: RF pickup check (ICP-39) and a declared pickup floor precede any use",
                "value": {"band_upper_Hz": 6.0e7}}, "Hz", [row(129, ("60 MHz",)), row(64, ("RF pickup",))],
               "rows 64, 129", "owner-allocation", "REVISED_PROPOSED", "LOCK-1"))
    # ---------------------------------------------------------------- (3) thermal: H2-5
    sm = th["closure_summary_hall_icp_neutralizer"]
    L.append(R("REV-40", "H2-5", "limits (all live nodes)", "thermal design margin rule and aborts",
               old_at("H25", "/limits", "limits"),
               {"requirement": ">= 50 K below each validated continuous-use limit plus 20 % heat-load margin; score-"
                               "bearing temperature aborts at validated limit - 50 K",
                "value": {"margin_K": MARGIN_K, "heat_load_factor": HEAT_LOAD_MARGIN}}, "K; -",
               [row(86, ("50 K", "20%")), a91("UBQ-06", ("minus 50 K",))], "row 86; UBQ-06", "owner-allocation",
               "OWNER_GIVEN", "NOW", recomputation="recomputations/h25_thermal_rerun"))
    L.append(R("REV-41", "H2-5", "H25-29", "exterior finish",
               old("H25", "H25-29"),
               {"requirement": "high-emittance temperature-capable exterior coating on MC-1 as the baseline (Z-93 option "
                               "evaluated); conditional on vacuum/AO/electrical compatibility qualification",
                "value": FINISH_BASE}, "-", [row(84, ("high-emittance",))], "row 84", "measured",
               "OWNER_GIVEN", "LOCK-1", recomputation="recomputations/h25_thermal_rerun"))
    L.append(R("REV-42", "H2-5", "coil limits (IEC 60085 classes / Sm2Co17)", "coil node limit",
               old_at("H25", "/limits/2", "limits[coil classes]"),
               {"requirement": "ceramic-insulated copper coil: supplier continuous rating (not validated) with the >= 50 K "
                               "margin; the permanent-magnet (Sm2Co17) rows are dropped (EM-only MC-1)",
                "value": {"limit_C": lim["coil_ceramic"]["limit_C"],
                          "design_ceiling_C": sig(lim["coil_ceramic"]["limit_C"] - MARGIN_K, 6),
                          "closure_CI": sm["CI"]["status"], "closure_CO": sm["CO"]["status"],
                          "CI_best_row85_compatible": sm["CI"]["best_row85_compatible"]}},
               "degC", [row(77, ("CERAMIC",)), row(78, ("EM ONLY",)), row(86, ("50 K",))], "rows 77, 78, 86",
               "model-derived", ("REVISED_RECOMPUTED" if sm["CI"]["closing_levers_within_row85_100W"] else "OPEN"),
               "after-evidence", recomputation="recomputations/h25_thermal_rerun"))
    L.append(R("REV-43", "H2-5", "H25-08", "coil I^2R bound with a ceramic (possibly Ni-clad) conductor",
               old("H25", "H25-08"),
               {"requirement": "upper bound x conductor factor (Ni-clad vs Cu) x 1.2 heat-load margin",
                "value": {"factor": th["coil_conductor_factor"]["factor"],
                          "P_mag_20C_upper_W_used": sig(old("H25", "H25-08")["value"][1] * th["coil_conductor_factor"]["factor"]
                                                        * HEAT_LOAD_MARGIN, 4)}},
               "W", [row(77, ("Ni-clad",)), row(86, ("20%",))], "MCQ-EM-03 resistance points vs NBS copper",
               "model-derived", "REVISED_RECOMPUTED", "LOCK-1", recomputation="recomputations/h25_thermal_rerun/coil_conductor_factor"))
    L.append(R("REV-44", "H2-5", "PI/PO/BP limits", "pole / core use limit",
               old_at("H25", "/limits/5", "limits[soft-magnetic use limit]"),
               {"requirement": "FeCo-2V inner / pure-iron outer; use limit from sourced B_sat(T) with >= 50 K margin; "
                               "until sourced only the necessary Curie-ceiling check is reported",
                "value": {n: sm[n]["necessary_check"] for n in ("PI", "PO", "BP")}},
               "degC", [row(76, ("FeCo-2V",)), row(86, ("50 K",))], "row 76", "model-derived", "OPEN", "LOCK-1",
               recomputation="recomputations/h25_thermal_rerun"))
    L.append(R("REV-45", "H2-5", "WI/WO (BN wall)", "BN wall closure incl. the v1 11.2 K case",
               old_at("H25", "/design_findings/1", "design_findings F2"),
               {"requirement": "worst-corner T_max <= 850 degC (900 - 50) with 1.2 x heat loads",
                "value": {"status": th["bn_wall_11_2K_case"]["status"],
                          "baseline_worst_T_max_C": th["bn_wall_11_2K_case"]["baseline_worst_T_max_C"],
                          "levers_that_close": th["bn_wall_11_2K_case"]["levers_that_close"],
                          "closing_levers_within_row85_100W":
                              th["bn_wall_11_2K_case"]["closing_levers_within_row85_100W"]}},
               "degC", [row(86, ("11.2 K", "not acceptable"))], "row 86", "model-derived",
               "REVISED_RECOMPUTED" if th["bn_wall_11_2K_case"]["status"] != "OPEN" else "OPEN", "after-evidence",
               recomputation="recomputations/h25_thermal_rerun/bn_wall_11_2K_case"))
    L.append(R("REV-46", "H2-5", "H25-10", "C1 heat into the H-1 environment",
               old("H25", "H25-10"),
               {"requirement": "hall_icp_neutralizer: 0 W (no C1, OQ-A902-04; ICP heat via influence coefficients); "
                               "hall_c1_reference ground article: v1 range x 1.2 through the v1 coupling (conservative "
                               "bound for an external module)",
                "value": {"hall_icp_neutralizer": 0.0,
                          "hall_c1_reference": [sig(v * HEAT_LOAD_MARGIN, 4) for v in old("H25", "H25-10")["value"]]}},
               "W", [a91("OQ-A902-04", ("no combined",)), row(79, ("EXTERNAL C1",)), row(86, ("20%",))],
               "external C1; no flight C1 in A9", "model-derived", "REVISED_RECOMPUTED", "LOCK-1",
               recomputation="recomputations/h25_thermal_rerun"))
    L.append(R("REV-47", "H2-5", "H25-11", "heat entering H-1 from a module slot",
               old("H25", "H25-11"),
               {"requirement": "no upstream pre-ionizer slot (IP-DN passive); the downstream ICP module heat into H-1 "
                               "is TBD (ICP-43) and is bounded here by influence coefficients and a linearised "
                               "allowance at the outer front pole / back plate",
                "value": {"min_allowance_W": th["icp_heat_into_h1"]["min_allowance_W"]}},
               "W", [row(61, ("SUPERSEDED",)), lane_item("A9-03", "ICP-43"), lane_item("A9-03", "ID-26")],
               "rows 61, 109; ICP-43", "model-derived", "REVISED_RECOMPUTED", "LOCK-1",
               recomputation="recomputations/h25_thermal_rerun/icp_heat_into_h1", applies_to=ICPo))
    L.append(R("REV-48", "H2-5", "H25-36", "spacecraft mounting-interface temperature and allowable heat",
               old("H25", "H25-36"),
               {"requirement": "carry 20/40/60 degC mounting-interface cases and 25/50/100 W allowable conducted-heat "
                               "cases; freeze at the spacecraft/PDR interface",
                "value": {"T_mount_C": list(T_MOUNT_CASES_C), "Q_allow_W": list(Q_ALLOW_CASES_W)}},
               "degC; W", [row(85, ("20/40/60", "25/50/100 W"))], "row 85", "owner-allocation", "OWNER_GIVEN",
               "after-evidence", recomputation="recomputations/h25_thermal_rerun/mount_heat_vs_row85"))
    L.append(R("REV-49", "H2-5", "H25-34", "ground radiative sink temperature",
               old("H25", "H25-34"),
               {"requirement": "measure facility wall/cryopanel sink temperature per run; ~300 K only as planning case",
                "value": "measured per run"}, "K", [row(131, ("MEASURE",))], "row 131", "owner-allocation",
               "OWNER_GIVEN", "NOW"))
    L.append(R("REV-50", "H2-5", "AN limit", "anode temperature limit",
               old_at("H25", "/limits/6", "limits[anode]"),
               {"requirement": "no unsourced anode target; allowable from the selected material's oxidation/electrical/"
                               "creep data with >= 50 K margin; 316L engineering baseline only",
                "value": f"{TBD} anode material selection (biased + floating coupons, row 106)"}, "degC",
               [row(87, ("NO unsourced",)), row(106, ("316L",))], "rows 87, 106", None, "TBD", "after-evidence"))
    # ---------------------------------------------------------------- (4) H2-4 supply partition
    L.append(R("REV-51", "H2-4", "H24-04", "bus voltage",
               old("H24", "H24-04"),
               {"requirement": "regulated 100 V internal propulsion bus for the breadboard/PPU architecture; spacecraft "
                               "input front end configurable; 100 V is NOT an RFP spacecraft interface requirement",
                "value": 100.0}, "V", [row(111, ("100 V",))], "row 111", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-52", "H2-4", "OQ-H24-03", "supply partition",
               old("H24", "OQ-H24-03", "question", within="/owner_questions"),
               {"requirement": "Hall discharge; per-coil magnet supplies (inner/outer/trim); ICP 13.56 MHz RF source + "
                               "matching; ICP collector/bias (floating, metered); C1 heater/keeper/common-tie reference "
                               "supplies (hall_c1_reference only); flow/valve (atmospheric, Xe incl. two series "
                               "isolation valves, capped ICP feed - booked only if G-ATM/G-XE); compressor; thermal "
                               "control; housekeeping/controls; reserved DC. Every active load gets a bus slot",
                "value": "bus_power_boundary_a9_v1 slots"}, "-",
               [row(110, ("Every active load gets a bus slot",)), a91("OQ-A902-05", ("G-REUSE",)),
                lane_item("A9-02", "slots")], "row 110; A9-02", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-53", "H2-4", "H24-19", "C1 keeper ignition load",
               old("H24", "H24-19"),
               {"requirement": "current-limited pulsed 300-600 V class ignition (C1 only); its bus draw is a start-up "
                               "transient measured on the 1 ms gate channel (OQ-A902-01) and the pulse energy recorded; "
                               "the DC bracket describes only DC keeper operation after ignition",
                "value": {"dc_bracket_W": old("H24", "H24-19")["value"], "pulse_peak_W": f"{TBD} measured 1 ms-window "
                          "and unaveraged peak on the breadboard keeper supply"}},
               "W", [row(89, ("300–600 V",)), a91("OQ-A902-01", ("1 ms",)), lane_item("A9-02", "H24-19 NEEDS_REVISION")],
               "row 89; A9-02 flag", "inferred", "REVISED_PROPOSED", "LOCK-1", applies_to=C1o))
    L.append(R("REV-54", "H2-4", "H24-26", "flight discharge-supply output current",
               old("H24", "H24-26"),
               {"requirement": "no allocation-derived current (no fixed Hall/ICP split, OQ-A902-03); the flight supply "
                               "output current is bounded above by 1350 W / 180 V; the stand envelope I_d,max used by "
                               "ICP-45 is the registered H-1 discharge-supply envelope (owner/LOCK-1; H24-27 lab rating "
                               "8.33 A is the candidate)",
                "value": {"flight_upper_bound_A": ds["flight_discharge_output_current_bound_A"]["value"],
                          "lab_rating_A_H24_27": ds["rfp_bound_current_A"]["check_H24_27"],
                          "I_d_max_registered": f"{TBD} owner registration of the stand discharge envelope (OQ-A907-02)"}},
               "A", [a91("OQ-A902-03", ("no fixed Hall/ICP split",)), a91("ICP-45", ("I_d,max",)),
                     lane_item("A9-02", "H24-26 NEEDS_REVISION")], "bounds on owner allocations, not predictions",
               "model-derived", "REVISED_RECOMPUTED", "LOCK-1",
               recomputation="recomputations/small/flight_discharge_output_current_bound_A"))
    L.append(R("REV-55", "H2-4", "H24-35", "no single-point failure in electronics",
               old("H24", "H24-35"),
               {"requirement": "LIMITED redundancy: dual series isolation on the high-pressure Xe path plus critical "
                               "sensing/FDIR redundancy; no duplication of thruster, ICP neutralizer or full PPU at this "
                               "stage; revisit after failure-tree evidence; RFP wording still to verify",
                "value": "limited redundancy"}, "-", [row(55, ("LIMITED redundancy",)),
                                                      lane_item("A9-02", "H24-35 CONSTRAINED_BY_OWNER_ANSWER")],
               "row 55", "owner-allocation", "OWNER_GIVEN", "after-evidence"))
    L.append(R("REV-56", "H2-4", "H24-36", "start-up sequencing SEQ-1",
               old("H24", "H24-36"),
               {"requirement": "revised SEQ-1: avoid simultaneous peaks - at most one peak-class load commanded to rise "
                               "per step (baseline; overlap = registered variant needing measured transient evidence); "
                               "C1 heater reduced/disabled only after keeper/discharge are stable (TBD heater = ON at "
                               "conservative power); ICP has no heater; ICP RF ignition and collector bias precede Hall "
                               "ignition in hall_icp_neutralizer (A9-02 templates C-S0..C-S7 / I-S0..I-S6)",
                "value": "A9-02 templates"}, "-",
               [row(112, ("REVISE SEQ-1",)), a91("SEQ-peaks", ("at most one peak-class load",)),
                a91("SEQ-heater", ("ON at conservative",)), lane_item("A9-02", "sequencing")],
               "row 112; A9.1", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-57", "H2-4", "H24-37", "start-up peak rule",
               old("H24", "H24-37"),
               {"requirement": "P_bus,1ms,max = max over t of the 1 ms moving average of P_bus < 1500 W, start-up and "
                               "steady (A9 engineering definition pending RFP wording); >= 20 kHz effective bandwidth, "
                               ">= 100 kSa/s per relevant channel (or a direct bus-power channel), synchronized, "
                               "anti-alias documented, no step-average substitution; unaveraged peak recorded for "
                               "protection only; 100 ms and 1 s averages are diagnostics",
                "value": {"window_ms": 1.0, "limit_W": 1500.0, "bandwidth_Hz_min": 20000.0, "sample_rate_Sps_min": 100000.0}},
               "W; ms; Hz; S/s", [a91("OQ-A902-01", ("1 ms", "20 kHz", "100 kSa/s")), row(108, ("1.5 kW",))],
               "A9.1 OQ-A902-01", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-58", "H2-4", "H24-16", "magnet load slots",
               old("H24", "H24-16"),
               {"requirement": "one current-controlled slot per coil (inner / outer / trim); no permanent-magnet 0 W option "
                               "(EM-only); hot-coil power uses the ceramic-conductor factor (REV-43)",
                "value": "per-coil slots"}, "W", [row(78, ("EM ONLY",)), row(110, ("per-coil magnet",))],
               "rows 78, 110", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-59", "H2-4", "H24-21", "common allocation (compressor, flow control, filter/getter, thermal, housekeeping)",
               old("H24", "H24-21"),
               {"requirement": "300 W common upper design allocation = compressor + atmospheric/Xe/ICP flow-control + "
                               "filter/getter if active + thermal control + housekeeping/controls; the 50 W controls/"
                               "thermal allowance is inside it; housekeeping/thermal routed through the internal bus by "
                               "default (any direct path represented explicitly)",
                "value": {"common_W": 300.0, "controls_thermal_W": 50.0}}, "W",
               [row(114, ("300 W",)), a91("OQ-A902-02", ("300 W",)), a91("OQ-A902-06", ("internal propulsion bus",))],
               "row 114; A9.1", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-60", "H2-4", "H24-24", "Hall discharge allocation vs ICP",
               old("H24", "H24-24"),
               {"requirement": "no fixed Hall/ICP wattage split: P_ICP,available = 1350 - P_common - P_Hall - "
                               "P_other,active at every registered condition; ICP-45 demonstrated within it; the 0-500 W "
                               "lab RF source is a test capability only; 1300 W reported as context/sensitivity",
                "value": "P_ICP,available = 1350 - P_common - P_Hall - P_other,active"}, "W",
               [a91("OQ-A902-03", ("1350",)), a91("OQ-A902-07", ("1300",)), row(109, ("1.35 kW",))],
               "A9.1", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-61", "H2-4", "H24-40", "floating outputs",
               old("H24", "H24-40"),
               {"requirement": "discharge/keeper/heater/magnet outputs floating (retained); add floating ICP body and a "
                               "separately biased, metered collector supply; RF returns separated from the discharge return",
                "value": "floating"}, "-", [row(70, ("floating",)), lane_item("A9-03", "ICP-20")], "row 70",
               "assumed", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-62", "H2-4", "H3-PPU-05", "breadboard discharge supply",
               old("H24", "H3-PPU-05", "item", within="/h3_procurement_inputs"),
               {"requirement": "flight-representative breadboard discharge supply fed from the 100 V internal bus; eta_d "
                               "and transients (incl. the 1 ms gate) measured before LOCK-2; quotation only until H3",
                "value": "breadboard, 100 V input, 180-350 V output"}, "-",
               [row(113, ("breadboard Hall discharge supply",)), row(111, ("100 V",))], "rows 111, 113",
               "owner-allocation", "OWNER_GIVEN", "LOCK-2"))
    # ---------------------------------------------------------------- (5) interfaces
    L.append(R("REV-63", "H2-4", "H24-25", "discharge voltage definition (controlled quantity)",
               old("H24", "H24-25"),
               {"requirement": "primary controlled quantity V_d = V_anode - V_electron-source-reference (C1 cathode "
                               "common in hall_c1_reference; the declared ICP electron-source reference node in "
                               "hall_icp_neutralizer); supply-terminal voltage and every loop drop recorded as secondary; "
                               "discharge-supply compliance = V_d,max + loop drops (loop drops TBD)",
                "value": {"V_d_range_V": old("H24", "H24-25")["value"],
                          "supply_compliance_V": f"{TBD} measured loop drops (series elements, collector sheath, cabling)"}},
               "V", [a91("A9-03-Vd", ("V_anode",)), lane_item("A9-03", "ICP-22")], "A9.1 A9-03 clarification",
               "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-64", "H2-3", "H23-27", "gas isolator rating",
               old("H23", "H23-27"),
               {"requirement": "350 V continuous design; ~1 kV DC withstand qualification at representative pressure/gas "
                               "with segmented/porous geometry as appropriate; no reliance on vacuum creepage across the "
                               "Paschen region (H23-29 range); the same practice for any dedicated ICP gas line (G-ATM/"
                               "G-XE contingency) and the C1 Xe line break",
                "value": {"continuous_V": 350.0, "qualification_V_DC_approx": 1000.0}}, "V",
               [row(105, ("350 V", "1 kV DC", "segmented/porous"))], "row 105", "owner-allocation", "OWNER_GIVEN", "NOW"))
    L.append(R("REV-65", "H2-3", "H23-01", "feed topology: pre-ionizer slot",
               old("H23", "H23-01", "name"),
               {"requirement": "no upstream module in the A9 primary line (the IP-UP..IP-DN segment carries no pre-ionizer "
                               "module; its content is a fixed passive feed segment defined by the H2-3 owner); IF-A3 at "
                               "the compressor outlet flange upstream of V0; silver excluded from O-wetted parts; inert/"
                               "low-recombination lining; both metering strategies carried",
                "value": "no pre-ionizer slot"}, "-",
               [row(61, ("SUPERSEDED",)), row(104, ("IF-A3",)), row(103, ("exclude silver",)), row(102, ("INERT",)),
                row(100, ("CARRY BOTH",))], "rows 61, 100, 102-104", "owner-allocation", "REVISED_PROPOSED", "LOCK-1"))
    L.append(R("REV-66", "H2-1", "interface_planes (IP-DN, HALL_INLET_Z0)", "plane set",
               old_at("H21", "/interface_planes", "interface_planes"),
               {"requirement": "IP-DN and HALL_INLET_Z0 unchanged (historical meaning kept); add IP-EXIT (H-1 exit) and "
                               "IP-NEU (downstream neutralizer datum) per A9.1; IP-C1 and KC-1 per A9-03",
                "value": ["IP-DN", "HALL_INLET_Z0", "IP-EXIT", "IP-NEU", "IP-C1", "KC-1"]}, "-",
               [a91("A9-03-planes", ("IP-EXIT", "IP-NEU", "IP-DN unchanged")), lane_item("A9-03", "ICP-01")],
               "A9.1", "assumed (convention)", "OWNER_GIVEN", "NOW"))
    return L


# ----------------------------------------------------------------------------------------------------------------------
# new A9 items (instrument additions, calibration)
# ----------------------------------------------------------------------------------------------------------------------
def I(iid, name, value, units, basis, source, evidence_class, status, freeze_point, applies_to=CONFIGURATIONS, note=None):
    if freeze_point not in FREEZE_POINTS:
        raise ValueError(iid)
    if evidence_class is not None and evidence_class.split()[0] not in EVIDENCE_CLASSES:
        raise ValueError(iid)
    if value is None:
        raise ValueError(f"{iid}: use an explicit TBD string, never None")
    d = {"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": source,
         "evidence_class": evidence_class, "status": status, "freeze_point": freeze_point, "applies_to": list(applies_to)}
    if note:
        d["note"] = note
    return d


def new_items() -> list:
    ICPo = ("hall_icp_neutralizer",)
    C1o = ("hall_c1_reference",)
    return [
        I("A9H-INS-01", "13.56 MHz directional coupler + forward/reflected power sensors, 0-500 W forward, reference "
                        "plane after the matching network", {"f_MHz": 13.56, "P_fwd_W": [0.0, 500.0]}, "MHz; W",
          "row 72; A9.1 A9-03-matching", [row(72, ("0–500 W",)), a91("A9-03-matching", ("coupler",))],
          "owner-allocation", "OWNER_GIVEN", "NOW", ICPo, "uncertainty u(P_fwd), u(P_refl) PENDING A9-04 (ICP-14)"),
        I("A9H-INS-02", "calorimetric RF cross-check at the load plane (independent, not the sole primary)",
          "normalized agreement statistic with k_x = 2 (frozen at LOCK-1); failure => RF-dependent quantities "
          "EXCLUDED_INSTRUMENT", "-", "row 72; UBQ-04", [row(72, ("Calorimetry",)), a91("UBQ-04", ("k_x = 2",))],
          "owner-allocation", "OWNER_GIVEN", "LOCK-1", ICPo),
        I("A9H-INS-03", "cable-loss / S-parameter characterization of the flexible coax (coupler plane -> antenna feed)",
          f"{TBD} S1a VNA characterization of the installed coax at 13.56 MHz", "dB", "A9.1 A9-03-matching",
          [a91("A9-03-matching", ("S-parameter",))], None, "TBD", "LOCK-2", ICPo),
        I("A9H-INS-04", "floating-rated collector/bias V and I channels", f"{TBD} collector bias range (ICP-21)",
          "V; A", "row 70; ICP-21", [row(70, ("collector bias separately",)), lane_item("A9-03", "ICP-21")], None,
          "TBD", "LOCK-1", ICPo, "isolation to the ICP-23 350 V rating + margin"),
        I("A9H-INS-05", "ground-return (facility-ground) current monitor", "required", "A",
          "A9-04 IF-14 instrument request", [lane_item("A9-04", "IF-14")], "assumed", "PROPOSED", "LOCK-1"),
        I("A9H-INS-06", "ICP telemetry subset (forward/reflected RF, collector/bias V/I, RF source temperature, "
                        "neutralizer health/interlock state)", "required", "-", "row 130",
          [row(130, ("forward/reflected RF power",)), lane_item("A9-03", "ICP-34")], "owner-allocation", "OWNER_GIVEN",
          "NOW", ICPo),
        I("A9H-INS-07", "RGA ~200 amu with differential pumping and species calibration (N2/O2/O fragments, Xe; Ar for "
                        "HI-AR)", {"mass_range_amu_approx": 200.0}, "amu", "row 127; UBQ-08",
          [row(127, ("200 amu",)), a91("UBQ-08", ("RGA",))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        I("A9H-INS-08", "facility sink-temperature sensors (wall/cryopanel), per run", "required", "K", "row 131",
          [row(131, ("MEASURE",))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        I("A9H-INS-09", "P_bus 1 ms gate channel at the spacecraft-DC propulsion boundary",
          {"bandwidth_Hz_min": 20000.0, "sample_rate_Sps_min": 100000.0, "window_ms": 1.0, "synchronized": True,
           "anti_alias_documented": True}, "Hz; S/s; ms", "A9.1 OQ-A902-01",
          [a91("OQ-A902-01", ("20 kHz", "100 kSa/s"))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        I("A9H-INS-10", "V_d measurement: anode and electron-source-reference potentials to ground + supply terminals "
                        "+ each loop drop", "required", "V", "A9.1 A9-03-Vd", [a91("A9-03-Vd", ("loop drops",))],
          "owner-allocation", "OWNER_GIVEN", "NOW"),
        I("A9H-INS-11", "B(z) perturbation / sensitivity scan with the downstream module installed and energized "
                        "(RF-immune mapping check)", f"{TBD} allowable field-change tolerance from measured H-1 sensitivity",
          "G", "row 67", [row(67, ("perturbation",)), lane_item("A9-03", "ICP-31")], None, "TBD", "LOCK-2"),
        I("A9H-INS-12", "C1 Xe flow: two controllers (0.05-0.2 mg/s-class steady; start/diode 0.6-0.8 mg/s if kept); "
                        "own-gas calibration", {"controllers": 2}, "mg/s", "rows 124-125",
          [row(125, ("TWO controllers",)), row(124, ("own-gas",))], "owner-allocation", "OWNER_GIVEN", "NOW", C1o),
        I("A9H-INS-13", "C1 pyrometer view where line of sight exists; tube TC mandatory, never relabelled as emitter",
          "required", "K", "row 128", [row(128, ("pyrometer",))], "owner-allocation", "OWNER_GIVEN", "NOW", C1o),
        I("A9H-CAL-01", "force calibration: in-situ SI-traceable masses/actuator + lever geometry under ISO/IEC 17025/"
                        "NABL traceability, pre/post block, drift and hysteresis recorded", "required", "N",
          "row 119; A9-04 IF-16", [row(119, ("SI-traceable",)), lane_item("A9-04", "IF-16")], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        I("A9H-CAL-02", "RF power sensors and coupler calibration at 13.56 MHz (traceable certificate)",
          f"{TBD} calibration certificate scope at 13.56 MHz", "W", "A9-04 IF-16",
          [lane_item("A9-04", "IF-16"), a91("UBQ-03", ("rectangular",))], None, "TBD", "LOCK-2", ICPo,
          "a manufacturer +/-a bound enters as a/sqrt(3) unless the certificate states otherwise (UBQ-03)"),
        I("A9H-CAL-03", "DC V/I channel calibration (discharge, collector, keeper, magnet, bus)", f"{TBD} certificates",
          "V; A", "A9-04 IF-16", [lane_item("A9-04", "IF-16")], None, "TBD", "LOCK-2"),
        I("A9H-CAL-04", "MFC own-gas calibration: NABL/ISO 17025 primary; in-house rate-of-rise as transfer standard; "
                        "Ar-specific calibration for HI-AR", "required", "mg/s", "rows 124, 126; UBQ-08",
          [row(126, ("NABL/ISO-17025",)), a91("UBQ-08", ("MFC",))], "owner-allocation", "OWNER_GIVEN", "NOW"),
        I("A9H-CAL-05", "pre/post calibration shift: in the budget and as a block-exclusion rule (form LOCK-1, number "
                        "LOCK-2)", f"{TBD} metrology-only calibration evidence (LOCK-2)", "-", "UBQ-05",
          [a91("UBQ-05", ("block-exclusion",))], None, "TBD", "LOCK-2"),
        I("A9H-FIX-01", "torsional thrust stand baseline (in-house engineering stand + qualified partner for score-bearing)",
          "torsional", "-", "rows 115, 118", [row(115, ("TORSIONAL",)), row(118, ("DUAL PATH",))], "owner-allocation",
          "OWNER_GIVEN", "NOW"),
        I("A9H-FIX-02", "exchange checks per C1<->ICP swap: cold/tare, service-line parasitic, B(z) perturbation, "
                        "electrical isolation, RF pickup", ["cold_tare", "service_line_parasitic", "Bz_perturbation",
                                                             "electrical_isolation", "rf_pickup"], "-", "row 64; ICP-39",
          [row(64, ("C1↔ICP",)), lane_item("A9-03", "ICP-39")], "owner-allocation", "OWNER_GIVEN", "LOCK-2"),
    ]


# ----------------------------------------------------------------------------------------------------------------------
# interface demands, owner answers, questions, reuse, M16, H3/H4
# ----------------------------------------------------------------------------------------------------------------------
def interface_demands(rc) -> list:
    th = rc["h25_thermal_rerun"]
    ds = rc["small"]
    lv = th["levers"]
    Dm = []

    def D(did, frm, to, quantity, value, units, status):
        Dm.append({"id": did, "from": frm, "to": to, "quantity": quantity, "value": value, "units": units,
                   "status": status})
    D("IDA7-01", "A9-07", "A9-06 " + PARALLEL["A9-06"], "mass consequences: (a) coil-current-density lever LV-COIL doubles "
      "the copper cross-section (H21-24 copper 1.579 kg at RP-1 f_NI 2 -> about +1.58 kg if adopted); (b) radiator lever "
      "LV-RAD enlarges the MC-1 body to D 0.18 m / L 0.13 m; (c) C1 hardware (module, keeper supply, two series "
      "valves, filter/getter) leaves the primary A9 flight BOM (ground article only); (d) ICP module, RF generator/"
      "matching/feedthrough, collector/bias hardware added (row 59); (e) stand payload >= 25 kg is a ground item",
      {"LV-COIL_copper_delta_kg": old("H21", "H21-24")["value"]["copper_kg"], "LV-RAD": lv["LV-RAD"]["set"]}, "kg; m",
      "OFFERED (lever adoption is an owner/LOCK-1 call)")
    D("IDA7-02", "A9-06 " + PARALLEL["A9-06"], "A9-07", "per-configuration mass and CG on the stand (C1 module, ICP module, "
      "sham, on-platform services) for the >= 25 kg payload check", None, "kg", pending("A9-06", "module masses and CG"))
    D("IDA7-03", "A9-07", "A9-08 " + PARALLEL["A9-08"], "Xe consequences: C1 ignition dwell cap 120 s with at most two "
      "retries (bound per start from the 1.0 mg/s start-controller full scale; attempts 3 literal / 2 shorthand, "
      "OQ-A907-01); G-REUSE gives zero dedicated ICP Xe; C1 Xe only in hall_c1_reference (ground) and any flight "
      "fallback; +/-2 % FS flow class term (row 96)", ds["c1_ignition_dwell_xe_bound_g"]["value"], "g per start",
      "OFFERED")
    D("IDA7-04", "A9-08 " + PARALLEL["A9-08"], "A9-07", "booked C1 purge/preheat/ignition Xe per start and the G-XE "
      "contingency term (if ever installed)", None, "g", pending("A9-08", "Xe per start terms"))
    D("IDA7-05", "A9-07", "A9-09 " + PARALLEL["A9-09"], "RFQ items (quotation only): see h3_inputs", "h3_inputs", "-",
      "OFFERED")
    D("IDA7-06", "A9-09 " + PARALLEL["A9-09"], "A9-07", "quoted data-sheet values (coating temperature capability, "
      "ceramic wire rating at representative gas, coupler/sensor calibration scope, isolator withstand)", None, "-",
      pending("A9-09", "quotations"))
    D("IDA7-07", "A9-07", "A9-03 " + A9_LANES["A9-03"], "H-1 thermal allowance for ICP module heat entering H-1 "
      "(linearised at each node's hot corner, min over cases, per lever set and node; 0 W where the node does not "
      "close): injection at the outer front pole PO / back plate BP",
      th["icp_heat_into_h1"]["min_allowance_W"], "W", "PRELIMINARY (model-derived; closes ID-17 in part)")
    D("IDA7-08", "A9-03 " + A9_LANES["A9-03"], "A9-07", "total ICP module heat load Q_mod and its split into H-1 "
      "(ICP-43)", None, "W", "PENDING docs/architecture_comparison/power_boundary_a9/ (P_d,max; ICP-43)")
    D("IDA7-09", "A9-07", "A9-03 " + A9_LANES["A9-03"], "external C1 removes the central bore (ID-12/ID-14 answered); "
      "IP-EXIT / IP-NEU / IP-C1 / KC-1 adopted in the H2 items", "REV-01, REV-03, REV-13, REV-29..31", "-", "ANSWERED")
    D("IDA7-10", "A9-03 " + A9_LANES["A9-03"], "A9-07", "standoff z_NEU (ICP-02), module envelope and seat dimensions "
      "(ICP-04/07)", None, "mm", "TBD (LOCK-1)")
    D("IDA7-11", "A9-07", "A9-02 " + A9_LANES["A9-02"], "H2-4 revisions adopted: per-coil magnet slots, pulsed keeper "
      "transient measured on the 1 ms channel, flight discharge current bound, 100 V bus", {
          "flight_discharge_current_bound_A": ds["flight_discharge_output_current_bound_A"]["value"]}, "A", "OFFERED")
    D("IDA7-12", "A9-02 " + A9_LANES["A9-02"], "A9-07", "registered I_d,max of the stand discharge slot (ICP-45 sizing) "
      "and per-slot efficiencies on the 100 V bus", None, "A; -", "TBD (owner registration; breadboard eta_d before LOCK-2)")
    D("IDA7-13", "A9-07", "A9-02 " + A9_LANES["A9-02"], "thermal_control load: no active cooling demanded by this lane "
      "(passive levers only); any active cooling would need its own slot (row 66)", 0.0, "W", "PRELIMINARY")
    D("IDA7-14", "A9-07", "A9-04 " + A9_LANES["A9-04"], "instrument additions answering IF-14/IF-16", "A9H-INS-*, A9H-CAL-*",
      "-", "ANSWERED (proposed items)")
    D("IDA7-15", "A9-04 " + A9_LANES["A9-04"], "A9-07", "u(P_fwd), u(P_refl), cable-loss chain uncertainty (ICP-14)",
      None, "W", "PENDING docs/experiments/hall_icp/uncertainty_budget/ (LOCK-2 numbers)")
    D("IDA7-16", "A9-07", "A9-01 " + A9_LANES["A9-01"], "score-bearing temperature aborts = validated limit - 50 K per "
      "node (UBQ-06); abort list for the prereg operating rules", {k: v.get("limit_C") for k, v in th["limits"].items()
                                                                   if k != "rule"}, "degC", "OFFERED")
    D("IDA7-17", "H2-1 docs/hardware/h2/h2_1_hall_chamber_magnet/", "A9-07", "FEMM B(z) incl. fringe field at IP-C1 and "
      "in the ICP volume; frozen channel geometry", None, "G; mm", "TBD - requires FEMM of the preliminary MC-1 (H2-1 "
      "follow-up; not in this lane)")
    D("IDA7-18", "A9-07", "H-1 CI (docs/experiments/hardware/)", "H-1 exit face = IP-EXIT; no C1 on H-1; hot-state B "
      "sensor; EM-only MC-1", "REV-03, REV-07, REV-11", "-", "OFFERED")
    D("IDA7-19", "A9-05 " + A9_LANES["A9-05"], "A9-07", "validation-input list items touching H2 (IF-12..IF-18 of "
      "hall_icp_validation_inputs_v1)", "consumed as requirements, no numbers taken", "-", "CONSUMED")
    return Dm


OWNER_ROWS_APPLIED = {
    5: "wet-mass gate: lever mass consequences forwarded to A9-06 (IDA7-01)",
    17: "configuration change = swap only the downstream electron-source module (REV-29)",
    42: "PHASE_TOTAL_FLOW: all ignition-dwell Xe booked (REV-25, IDA7-03)",
    49: "heated C1 (REV-19)",
    55: "limited redundancy; dual series isolation (REV-20, REV-55)",
    59: "BOM amendment forwarded to A9-06 (IDA7-01)",
    61: "no pre-ionizer slot: H25-11 superseded, feed topology revised (REV-47, REV-65)",
    63: "Hall-exhaust-to-ICP interface measured, not sealed (REV-31)",
    64: "C1<->ICP exchange checks incl. RF pickup (A9H-FIX-02, REV-39)",
    67: "B(z) perturbation scan with the ICP installed/energized (A9H-INS-11)",
    70: "ICP body floating, collector separately biased and metered (REV-36, REV-61, A9H-INS-04)",
    72: "13.56 MHz, 0-500 W coupler chain; calorimetry cross-check (A9H-INS-01/02)",
    73: "~1.3 mg/s nominal channel neutral-density sizing (REV-12)",
    74: "T2 shielded baseline, unshielded set engineering-only (REV-07)",
    75: "L/h <= 12; adjustable anode only pre-S1 (REV-08, REV-09)",
    76: "FeCo-2V inner + pure-iron outer; limits from B_sat(T) (REV-05, REV-06, REV-44)",
    77: "ceramic-insulated copper coil; Ni-clad factor in the thermal rerun (REV-04, REV-42, REV-43)",
    78: "EM-only MC-1: PM rows dropped, per-coil slots (REV-07, REV-42, REV-58)",
    79: "external C1: H21-22 re-derived, H2-2 location moved (REV-01, REV-02, REV-13..REV-18)",
    80: "design factors accepted (REV-10)",
    81: "350 V + margin isolation (REV-36)",
    82: "hot-state B sensor (REV-11)",
    84: "high-emittance coating baseline in the thermal rerun (REV-41)",
    85: "20/40/60 degC mount and 25/50/100 W allowable-heat cases (REV-48)",
    86: ">= 50 K + 20 % heat-load margin rule; 11.2 K case evaluated (REV-40, REV-45)",
    87: "no unsourced anode target (REV-50)",
    89: "pulsed keeper 300-600 V (REV-21, REV-53)",
    90: "two series isolation valves (REV-20)",
    91: "selectable cathode-common/bleeder, value after tests (REV-28)",
    92: "0.005 mg/s flow step (REV-24)",
    93: "120 s dwell cap, at most two retries (REV-25)",
    94: "no graphite keeper for O/AO exposure (REV-23)",
    95: "1843 K floor (REV-27)",
    96: "+/-2 % FS conservative class (REV-26)",
    97: "installed zero check per block (REV-26)",
    98: "resolution <= 0.0005 mg/s, digital setpoint (REV-26)",
    100: "both metering strategies carried (REV-65)",
    102: "inert/low-recombination lining (REV-65)",
    103: "silver excluded (REV-65)",
    104: "IF-A3 at the compressor outlet flange (REV-65)",
    105: "isolator 350 V continuous + ~1 kV DC qualification, segmented/porous (REV-64, REV-22)",
    106: "316L engineering-only anode baseline (REV-50)",
    108: "1.5 kW at the spacecraft-DC boundary incl. start-up (REV-35, REV-57)",
    109: "1.35 kW internal design allocation; ICP inside it (REV-54, REV-60)",
    110: "supply partition adopted with revision (REV-52, REV-58)",
    111: "regulated 100 V internal bus (REV-51)",
    112: "revised SEQ-1 (REV-56)",
    113: "breadboard discharge supply before LOCK-2 (REV-62)",
    114: "300 W common incl. 50 W controls/thermal (REV-59)",
    115: "torsional stand baseline (A9H-FIX-01)",
    116: ">= 25 kg moving payload (REV-32)",
    117: "flexible RF coax, harp/slack routing (REV-33)",
    118: "dual-path stand (A9H-FIX-01)",
    119: "in-situ SI-traceable force calibration (A9H-CAL-01)",
    120: "S1a 12 mN test at max payload with all lines (REV-38)",
    121: "1 % thrust uncertainty target (REV-38)",
    122: "H-1 bolted; kinematic carrier exchanges C1 and ICP modules (REV-29, REV-30)",
    124: "own-gas MFC calibration (A9H-INS-12, A9H-CAL-04)",
    125: "two C1 controllers (REV-26, A9H-INS-12)",
    126: "NABL/ISO 17025 primary flow reference (A9H-CAL-04)",
    127: "RGA ~200 amu (A9H-INS-07)",
    128: "C1 pyrometer view (A9H-INS-13)",
    129: "I_d(t) to ~60 MHz with RF pickup caveat (REV-39)",
    130: "ICP telemetry subset (A9H-INS-06)",
    131: "sink temperature measured per run (REV-49, A9H-INS-08)",
    133: "matched sham service lines in every configuration (REV-16, REV-33)",
}

A91_APPLIED = {
    "HIQ-06": "G-REUSE: no module-to-H-1 gas seal; capped ICP port; no dedicated ICP Xe (REV-31, IDA7-03)",
    "UBQ-01": "1 % thrust target is k = 1 (REV-38)",
    "UBQ-03": "rectangular treatment of manufacturer bounds noted on RF calibration (A9H-CAL-02)",
    "UBQ-04": "coupler vs calorimetry agreement, k_x = 2 at LOCK-1 (A9H-INS-02)",
    "UBQ-05": "calibration shift rule (A9H-CAL-05)",
    "UBQ-06": "temperature aborts at limit - 50 K; design ceiling in the thermal rerun (REV-40, IDA7-16)",
    "UBQ-08": "Ar-specific RGA/MFC calibration (A9H-INS-07, A9H-CAL-04)",
    "OQ-A902-01": "1 ms P_bus gate channel requirements (REV-57, A9H-INS-09, REV-37)",
    "OQ-A902-02": "300 W common allocation composition (REV-59)",
    "OQ-A902-03": "no fixed Hall/ICP split; P_ICP,available formula (REV-54, REV-60)",
    "OQ-A902-04": "no combined flight C1 + ICP: C1 on the ground article only (REV-13, REV-46)",
    "OQ-A902-05": "flow_control_icp_feed booked only for G-ATM/G-XE (REV-52)",
    "OQ-A902-06": "housekeeping/thermal via the internal bus (REV-59)",
    "OQ-A902-07": "1350 W active check, 1300 W context (REV-54, REV-60)",
    "SEQ-heater": "TBD heater ON at conservative power (REV-19, REV-56)",
    "SEQ-peaks": "one peak-class load per step (REV-56)",
    "ICP-45": "I_d,max from the registered stand envelope, not invented (REV-54, OQ-A907-02)",
    "ICP-46": "keeper isolation 900 V basis, 1.0 kV DC hipot, 600 V pulse test (REV-21, REV-36)",
    "A9-03-planes": "IP-EXIT / IP-NEU adopted; IP-DN unchanged (REV-03, REV-29, REV-66)",
    "A9-03-Vd": "V_d = V_anode - V_electron-source-reference (REV-63, A9H-INS-10)",
    "A9-03-matching": "matching network off-platform, coupler after match, S-parameter correction (REV-34, A9H-INS-03)",
    "A9-03-collector": "collector material not frozen; not an H2 item here (noted for A9-09 RFQ as open material)",
}


def owner_answers_applied() -> list:
    return [dict(row(r), how_applied=how) for r, how in sorted(OWNER_ROWS_APPLIED.items())]


def a91_applied() -> list:
    return [dict(a91(k), how_applied=v) for k, v in A91_APPLIED.items()]


def _oq06(th) -> str:
    ci = th["closure_summary_hall_icp_neutralizer"]["CI"]["best_row85_compatible"]
    ok = th["row85_compatible_levers_100W"]
    tail = (f"; with {ci['lever']} the inner coil still has margin {ci['margin_to_design_ceiling_K']:g} K to its design "
            "ceiling" if ci else "")
    return ("Heat conducted into the spacecraft mount exceeds the row-85 allowable-heat cases at the bounding corners "
            "for every evaluated lever set except " + (", ".join(ok) or "none") + " (100 W case only)" + tail +
            ". Pursue a thermally isolated mount with a dedicated thruster radiator as the design direction, and which "
            "row-85 allowable-heat case (25/50/100 W) governs the H-1 design?")


def open_owner_questions(rc) -> list:
    th = rc["h25_thermal_rerun"]
    return [
        {"id": "OQ-A907-01", "question": "Row 93 'cap each ignition dwell at 120 s and allow at most two retries': book "
                                         "3 attempts (1 + 2 retries, literal) or 2 (the '120 s x 2' shorthand used in "
                                         "the A9 backlog) per start in the Xe ledger?",
         "proposed_answer": "3 attempts (literal reading, conservative for Xe booking)",
         "values": rc["small"]["c1_ignition_dwell_xe_bound_g"]["value"]},
        {"id": "OQ-A907-02", "question": "Register the stand discharge-supply envelope I_d,max for ICP-45 (A9.1: from the "
                                         "registered H-1/discharge-supply envelope, not invented)?",
         "proposed_answer": "register the H24-27 laboratory rating 8.33 A (1500 W / 180 V) unless the owner registers a "
                            "narrower stand envelope before LOCK-1; the flight supply bound is 7.5 A (1350 W / 180 V)"},
        {"id": "OQ-A907-03", "question": "Is the >= 50 K rule tested at the bounding corner (all adverse analog inputs "
                                         "together, as done here) or at a nominal point plus a pre-registered "
                                         "uncertainty treatment?",
         "proposed_answer": "bounding corner for design closure now; replace the analog heat-fraction ranges by measured "
                            "Phase-1 deposition data when available (after-evidence), never by relaxing the limit"},
        {"id": "OQ-A907-04", "question": "Ceramic-insulated coil conductor: plain copper or Ni-clad (Kulgrid)? The Ni-clad "
                                         f"conductor raises I^2R by up to x{th['coil_conductor_factor']['factor']:.3g} "
                                         "at equal section and needs a measured magnetic perturbation (row 77)",
         "proposed_answer": "owner call; carry the Ni-clad factor as the conservative bound until the wire is quoted"},
        {"id": "OQ-A907-05", "question": "Accept the supplier continuous ratings (BN 900 degC oxidizing guide value, "
                                         "ceramic wire 1000 F) as PROVISIONAL limits for the >= 50 K rule until "
                                         "qualification tests validate them?",
         "proposed_answer": "yes, provisional; every CLOSES verdict stays conditional on validation"},
        {"id": "OQ-A907-06", "question": _oq06(th),
         "proposed_answer": "owner call (spacecraft/PDR interface); this lane only reports the conflict"},
        {"id": "OQ-A907-07", "question": "Develop a flight C1 integration (external mount on the flight article, two "
                                         "series valves, keeper supply) now for the fallback architecture "
                                         "hall_c1_reference, or defer until C1 is chosen for flight?",
         "proposed_answer": "defer (OQ-A902-04: C1 is not an automatic flight backup; a flight C1 variant needs its own "
                            "closures)"},
    ]


def historical_reuse() -> dict:
    return {
        "reused": [
            {"path": DELIVERABLES["H21_PY"], "sha256": sha256_of(DELIVERABLES["H21_PY"]),
             "what": "pure magnetic-circuit functions (min_d_for_central_cathode, coil_case, channel_window) imported "
                     "read-only for REV-01"},
            {"path": DELIVERABLES["H25_PY"], "sha256": sha256_of(DELIVERABLES["H25_PY"]),
             "what": "9-node thermal network (build_parameters, ranges_for, run/assemble/solve) imported read-only for "
                     "REV-40..REV-47"},
            {"path": DELIVERABLES["H26"], "sha256": sha256_of(DELIVERABLES["H26"]),
             "what": "kinematic carrier concept H26-40..42 and SVC-1 sham principle, re-derived for a downstream module"},
            {"path": HISTORICAL["PIM_ICD"], "sha256": sha256_of(HISTORICAL["PIM_ICD"]),
             "what": "structure only (interface grouping, exchange checks); no value reused"},
        ],
        "not_reused": [
            {"path": HISTORICAL["PIM_ICD"], "sha256": sha256_of(HISTORICAL["PIM_ICD"]),
             "what": "upstream module envelope (ECR-sized), PMI-05 thermal slot, L1-L5 harness (rows 61-63 superseded)"},
            {"path": HISTORICAL["P1_FRAMEWORK"], "sha256": sha256_of(HISTORICAL["P1_FRAMEWORK"]),
             "what": "A5 hall_only / rf_hall / ecr_hall arms and P1DQ quantities (A9 supersession)"},
            {"path": HISTORICAL["ARCH_BOUNDARY_V1"], "sha256": sha256_of(HISTORICAL["ARCH_BOUNDARY_V1"]),
             "what": "bus_power_boundary_v1 slot set (replaced by bus_power_boundary_a9_v1)"},
            {"path": DELIVERABLES["H25"], "sha256": sha256_of(DELIVERABLES["H25"]),
             "what": "v1 permanent-magnet (Sm2Co17) margin rows and IEC 60085 polyimide-family coil classes (rows 77, 78)"},
        ],
        "never_edited": sorted(list(HISTORICAL.values()) + [DELIVERABLES[k] for k in
                                                            ("H21", "H22", "H23", "H24", "H25", "H26", "H27")]),
    }


def m16_impact(rc) -> list:
    sm = rc["h25_thermal_rerun"]["closure_summary_hall_icp_neutralizer"]
    m16 = {r["row"]: r for r in load(DELIVERABLES["M16"])["rows"]}

    def M(r, how, blocking):
        if r not in m16:
            raise KeyError(f"M16 row {r}")
        return {"m16_row": r, "key": m16[r]["key"], "name": m16[r]["name"], "how_touched": how,
                "proposed_state": "BLOCKED", "blocking_item": blocking}
    return [
        M(8, "two series isolation valves on any flight Xe/cathode branch (REV-20)", "valve selection (A9-09 quotation)"),
        M(9, "H21-22 central-cathode floor removed; exit face = IP-EXIT (REV-01..03)", "FEMM of the preliminary MC-1"),
        M(10, "EM-only, FeCo-2V/pure iron, ceramic coil; coil node closure " + sm["CI"]["status"] + " / " + sm["CO"]["status"],
          "sourced B_sat(T) and coil qualification"),
        M(11, "C1 external reference module on KC-1, ground article only (REV-13..28)", "C1 module drawing + ICP-46 hipot"),
        M(12, "100 V bus, per-coil slots, pulsed keeper transient, 1 ms gate channel (REV-51..63)",
          "breadboard discharge supply (row 113)"),
        M(13, "thermal rerun with the owner rules; BN wall " + sm["WI"]["status"] + " (REV-40..50)",
          "measured deposition fractions / sourced BN k(T)"),
        M(15, "instrument additions A9H-INS-01..13, calibrations A9H-CAL-01..05", "quotations (A9-09)"),
        M(16, "KC-1 downstream carrier, >= 25 kg payload, matched shams (REV-29..36)", "module drawings (ICP-02/04/07)"),
    ]


def h3_inputs() -> list:
    q = "QUOTATION ONLY (A9.1: RFQs authorized, purchase orders not; H3 gate controls purchases)"
    items = [
        ("H3-A907-01", "breadboard Hall discharge supply, 100 V input, 180-350 V output (row 113)"),
        ("H3-A907-02", "13.56 MHz RF generator 0-500 W + matching network for off-platform mounting (row 72)"),
        ("H3-A907-03", "13.56 MHz directional coupler + forward/reflected power sensors with calibration (A9H-INS-01)"),
        ("H3-A907-04", "matched flexible RF coax pair (live + sham) for the stand crossing (REV-33)"),
        ("H3-A907-05", "floating collector/bias supply with V/I read-back (A9H-INS-04)"),
        ("H3-A907-06", "P_bus DAQ: >= 20 kHz effective bandwidth, >= 100 kSa/s per channel, synchronized (A9H-INS-09)"),
        ("H3-A907-07", "C1 keeper supply with 300-600 V current-limited pulse ignition + 1 kV DC hipot tester (REV-21)"),
        ("H3-A907-08", "ceramic-insulated magnet wire (plain Cu and Ni-clad options) with representative-gas hipot data "
                       "(REV-04)"),
        ("H3-A907-09", "high-emittance, temperature-capable exterior coating + coupons (REV-41)"),
        ("H3-A907-10", "segmented/porous gas isolator qualified to ~1 kV DC at representative pressure/gas (REV-64)"),
        ("H3-A907-11", "two independent series isolation valves for a C1/Xe branch (REV-20)"),
        ("H3-A907-12", "torsional thrust stand >= 25 kg moving payload + kinematic carrier KC-1 (REV-30, REV-32)"),
        ("H3-A907-13", "RGA ~200 amu with differential pumping (A9H-INS-07)"),
        ("H3-A907-14", "FeCo-2V and pure-iron stock with B_sat(T) data (REV-05, REV-06)"),
    ]
    return [{"id": i, "item": t, "status": q, "to": "A9-09 " + PARALLEL["A9-09"]} for i, t in items]


def h4_inputs(rc) -> list:
    return [
        {"id": "H4-A907-01", "test": "keeper lead/feedthrough/harness 1.0 kV DC hipot at representative pressure/gas "
                                     "+ separate 600 V pulse-waveform test (ICP-46)", "freeze_point": "LOCK-1"},
        {"id": "H4-A907-02", "test": "gas isolator ~1 kV DC withstand across the H23-29 pressure range (row 105)",
         "freeze_point": "LOCK-1"},
        {"id": "H4-A907-03", "test": "S1a thrust-uncertainty acceptance at 12 mN, max payload, all lines (rows 120-121)",
         "freeze_point": "LOCK-2"},
        {"id": "H4-A907-04", "test": "coupler vs calorimetry agreement, k_x = 2 (UBQ-04); coax S-parameter "
                                     "characterization", "freeze_point": "LOCK-2"},
        {"id": "H4-A907-05", "test": "thermal balance test of H-1 with thermocouple map; per-run sink temperature; "
                                     "aborts at limit - 50 K (UBQ-06)", "freeze_point": "LOCK-2"},
        {"id": "H4-A907-06", "test": "B(z) perturbation scan with the downstream module installed/energized (row 67)",
         "freeze_point": "LOCK-2"},
        {"id": "H4-A907-07", "test": "KC-1 installation reproducibility and C1<->ICP exchange checks (ICP-39)",
         "freeze_point": "LOCK-2"},
        {"id": "H4-A907-08", "test": "P_bus 1 ms channel verification (bandwidth, anti-alias, synchronization) on the "
                                     "breadboard supplies", "freeze_point": "LOCK-2"},
        {"id": "H4-A907-09", "test": "coating coupon qualification (vacuum/AO/electrical) and ceramic coil hipot in "
                                     "representative gas (rows 77, 84)", "freeze_point": "after-evidence"},
    ]


def _k9(th) -> str:
    c1 = th["results"]["hall_c1_reference"]
    parts = []
    for lv, rec in c1.items():
        nd = rec["ground"]["nodes"]
        bad = [n for n, e in nd.items() if e["verdict"].startswith("DO_NOT_CLOSE") or e.get("necessary_check") == "FAIL"]
        parts.append(f"{lv}: " + (", ".join(f"{n} {nd[n]['T_max_C']:g} degC" for n in bad) or "all live nodes close"))
    return ("K9 hall_c1_reference ground article (C1 heat coupled into H-1 as the conservative v1 bound; not a flight "
            "item, OQ-A902-04) - nodes not closing or failing the necessary Curie check: " + "; ".join(parts) + ".")


def key_findings(rc) -> list:
    """Plain-language findings computed from the recomputations (no new numbers)."""
    th = rc["h25_thermal_rerun"]
    sm = th["closure_summary_hall_icp_neutralizer"]
    b = th["bn_wall_11_2K_case"]
    ci = sm["CI"]["best_row85_compatible"] or {}
    ds = rc["small"]
    return [
        "K1 " + rc["h21_central_bore"]["finding"] + ".",
        f"K2 thermal, owner rules (>= 50 K below the recorded limits, 1.2 x heat loads, Z-93 finish, ceramic coil, "
        f"EM-only): overall status {th['overall']['status']}. Baseline worst corners: BN inner wall "
        f"{sm['WI']['baseline_worst_T_max_C']:g} degC (ceiling 850), outer wall {sm['WO']['baseline_worst_T_max_C']:g}, "
        f"inner coil {sm['CI']['baseline_worst_T_max_C']:g} (ceiling {th['limits']['coil_ceramic']['limit_C'] - MARGIN_K:g}), "
        f"outer coil {sm['CO']['baseline_worst_T_max_C']:g}.",
        f"K3 the v1 11.2 K BN-wall case is {b['status']}: single levers that close it in every case "
        f"{', '.join(lv for lv in b['levers_that_close'] if not lv.startswith('LV-ALL')) or 'none'}; closing lever sets "
        f"that also keep the corner mount heat within 100 W: {', '.join(b['closing_levers_within_row85_100W']) or 'none'}.",
        f"K4 inner coil CI is the design-driving node: it closes only with {', '.join(sm['CI']['levers_that_close_every_case']) or 'no lever set'}; "
        f"with the only mount-heat-compatible set ({ci.get('lever', 'none')}) its margin to the design ceiling is "
        f"{ci.get('margin_to_design_ceiling_K', 'n/a')} K, so the coil closure stays OPEN (evidence levers: measured "
        "deposition fractions, validated coil rating, FEMM-sized winding window).",
        "K5 heat into the spacecraft mount at the bounding corners exceeds the row-85 allowable-heat cases for every "
        "lever set except " + (", ".join(th["row85_compatible_levers_100W"]) or "none") + " (100 W case only); see OQ-A907-06.",
        f"K6 pole/core and anode limits are TBD (B_sat(T), anode material); necessary Curie checks: PI "
        f"{', '.join(sm['PI']['necessary_check'])}, PO {', '.join(sm['PO']['necessary_check'])}, BP "
        f"{', '.join(sm['BP']['necessary_check'])}.",
        f"K7 ICP-46 keeper isolation basis {ds['icp46_isolation_basis_V']['value']:g} V (1.5 x 600 V), 1.0 kV DC "
        "development hipot, separate 600 V pulse test; flight discharge-supply output current bounded by "
        f"{ds['flight_discharge_output_current_bound_A']['value']:g} A (1350 W / 180 V); stand I_d,max registration is an "
        "owner/LOCK-1 item (OQ-A907-02).",
        "K8 downstream fixture: H-1 bolted; KC-1 carries the C1 module, the ICP module and the sham downstream of IP-EXIT; "
        "matching network off-platform with the coupler plane after the match; matched shams both ways; >= 25 kg stand.",
        _k9(th),
    ]


def hard_incompatibility_check(rc) -> dict:
    res = rc["h25_thermal_rerun"]["results"]["hall_icp_neutralizer"]
    cand = []
    for n in ("WI", "WO", "CI", "CO"):
        if all(res[lv][c]["nodes"][n]["verdict"] == "DO_NOT_CLOSE_WHOLE_ENVELOPE" for lv in res for c in res[lv]):
            cand.append(n)
    return {"verdict": "HARD_INCOMPATIBILITY_CANDIDATE" if cand else "NONE",
            "nodes": cand, "veto_claimed": False,
            "checked": "a node would be a candidate only if even its best corner exceeds the design ceiling in every "
                       "lever set and case; limits are unvalidated supplier values, so no veto is claimed"}


# ----------------------------------------------------------------------------------------------------------------------
# document
# ----------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    pins = check_decisions()
    a9 = load(DECISIONS["A9"][0])
    if a9["status"] != "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE":
        raise RuntimeError("A9 status changed")
    rc = {"h21_central_bore": recompute_h21(), "h25_thermal_rerun": recompute_thermal(), "small": derived_small()}
    reg = revision_register(rc)
    ids = [r["id"] for r in reg]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate REV id")
    doc = {
        "schema": "h2_a9_revisions_v1",
        "id": "h2_a9_revisions_v1",
        "title": "A9-07 H2 revisions: external C1, downstream ICP fixture, 50 K thermal protection, revised interfaces",
        "lane": "fo_a9_07_h2_revisions",
        "trigger": "T_A9_07_H2_REVISIONS",
        "authority": "A9.1 step 2 (docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json execution."
                     "step_2_parallel.A9-07)",
        "status": "PRELIMINARY_DRAFT_FOR_OWNER",
        "a9_status": a9["status"],
        "date": DATE,
        "base_commit": BASE_COMMIT,
        "generated_by": THIS_SCRIPT,
        "companion_document": OUT_MD,
        "test": TEST,
        "configurations": list(CONFIGURATIONS),
        "outcome_vocabulary": list(OUTCOME_VOCABULARY),
        "status_not_outcome": list(STATUS_NOT_OUTCOME),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "freeze_points": list(FREEZE_POINTS),
        "rev_statuses": list(REV_STATUSES),
        "standing_facts": {
            "a9": "investigation hypothesis, not a flight baseline; C1 remains control/fallback",
            "credible_hall_set": "EMPTY (no admitted Hall transport closure)",
            "p5_n2_v1": "INCONCLUSIVE (permanent)",
            "bundle1": "NO_BASELINE_YET",
            "no_winner": "hall_c1_reference and hall_icp_neutralizer are never ranked here",
        },
        "what_this_is_not": [
            "not a performance prediction (no thrust, efficiency, discharge current, electron current or plasma state)",
            "not an architecture selection and not a winner declaration",
            "not a change to any verified H2 v1 file (all stay byte-identical; this is a separate revision register)",
            "not wired into abep_sim/archengine.py",
        ],
        "decision_pins": pins,
        "deliverable_pins": [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in DELIVERABLES.items()],
        "historical_read_only": [{"key": k, "path": p, "sha256": sha256_of(p)} for k, p in HISTORICAL.items()],
        "never_pinned": NEVER_PINNED,
        "parallel_lanes_pending": PARALLEL,
        "recomputations": rc,
        "key_findings": key_findings(rc),
        "revision_register": reg,
        "new_items": new_items(),
        "interface_demands": interface_demands(rc),
        "owner_answers_applied": owner_answers_applied(),
        "a9_1_decisions_applied": a91_applied(),
        "open_owner_questions": open_owner_questions(rc),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(rc),
        "h3_inputs": h3_inputs(),
        "h4_inputs": h4_inputs(rc),
        "hard_incompatibility_check": hard_incompatibility_check(rc),
        "compliance": {
            "no_hall_performance_source": "no transport closure, screening candidate, plasma_devices.py or withdrawn number read",
            "lane_paths": [LANE_DIR + "/", TEST],
            "h2_v1_untouched": "H2-1..H2-7 v1 JSON/MD/builders are only read; builders imported, never written",
            "no_contact": "no persons, labs or suppliers contacted; no web source newly cited",
            "thresholds": "only owner-given (rows / A9.1) or recorded supplier values; levers are PROPOSED; no limit relaxed",
            "no_winner": True,
        },
    }
    return doc


def dump(doc) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def _fmt(v, n=160):
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _drv(ds):
    out = []
    for d in ds:
        if d["kind"] == "owner_row":
            out.append(f"row {d['row']}")
        elif d["kind"] == "A9.1":
            out.append(f"A9.1 {d['id']}")
        else:
            out.append(f"{d['lane']} {d['id']}")
    return ", ".join(out)


def render_md(doc) -> str:
    L = []
    th = doc["recomputations"]["h25_thermal_rerun"]
    h1 = doc["recomputations"]["h21_central_bore"]
    L.append(f"# {doc['title']}\n")
    L.append(f"Generated by `{doc['generated_by']}` from `{OUT_JSON}` (do not edit by hand). Lane `{doc['lane']}`, "
             f"trigger `{doc['trigger']}`, base `{doc['base_commit']}`. Status **{doc['status']}**; A9 status "
             f"`{doc['a9_status']}`.\n")
    L.append("Configurations: `hall_c1_reference`, `hall_icp_neutralizer` (never ranked; no winner). `OPEN` is a status, "
             "not an outcome. Credible Hall set EMPTY; P5-N2 v1 INCONCLUSIVE; Bundle 1 NO_BASELINE_YET.\n")
    L.append("## Key findings\n")
    for k in doc["key_findings"]:
        L.append(f"- {k}")
    L.append("\n## What this is not\n")
    for w in doc["what_this_is_not"]:
        L.append(f"- {w}")
    L.append("\n## Pinned inputs\n")
    L.append("| key | path | sha256 |\n|---|---|---|")
    for p in doc["decision_pins"] + doc["deliverable_pins"]:
        L.append(f"| {p['key']} | `{p['path']}` | `{p['sha256'][:16]}...` |")
    L.append("\nNever pinned (mutable governance): " + ", ".join(f"`{p}`" for p in doc["never_pinned"]) + "\n")
    # recomputations
    L.append("## Recomputation 1 - H2-1 central-cathode floor under the external C1 (row 79)\n")
    L.append(h1["method"] + "\n")
    L.append("| h (mm) | v1 floor bore 12 / 18 mm (mm) | external-C1 floor nominal / worst (mm) | window d_mean at h (mm) | "
             "external floor binding |\n|---|---|---|---|---|")
    for r in h1["rows"]:
        L.append(f"| {r['h_mm']} | {r['v1_central_cathode_floor_mm']['bore_12mm']} / "
                 f"{r['v1_central_cathode_floor_mm']['bore_18mm']} | {r['external_c1_magnetic_floor_mm']['nominal_assumptions']}"
                 f" / {r['external_c1_magnetic_floor_mm']['worst_case_assumptions']} | "
                 f"{r['channel_window_d_mean_mm_at_this_h']} | {r['external_floor_binding']} |")
    L.append(f"\nFinding: {h1['finding']}. In-memory override: `{h1['in_memory_override']['input']}` "
             f"{h1['in_memory_override']['v1_value_mm']} -> 0 mm (restored; no file modified).\n")
    L.append("## Recomputation 2 - H2-5 thermal network under the owner margin rules\n")
    L.append(th["method"] + "\n")
    L.append(f"Rule: {th['rule']['closure_test']}. Coil conductor factor (Ni-clad vs Cu): "
             f"{th['coil_conductor_factor']['factor']}. Reproduction check: v1 {th['reproduction_check']['case']} "
             f"T_max {th['reproduction_check']['v1_T_max_C']} degC reproduced as {th['reproduction_check']['reproduced_T_max_C']} degC.\n")
    L.append("### Limits used\n")
    L.append("| group | nodes | limit (degC) | design ceiling / necessary ceiling | validation |\n|---|---|---|---|---|")
    for k, v in th["limits"].items():
        if k == "rule":
            continue
        ceil = (v["limit_C"] - MARGIN_K) if v.get("limit_C") is not None else (
            f"necessary: {v['necessary_ceiling_C'] - MARGIN_K:g}" if v.get("necessary_ceiling_C") is not None else "-")
        L.append(f"| {k} | {', '.join(v['nodes'])} | {v.get('limit_C')} | {ceil} | {_fmt(v['validation'], 120)} |")
    L.append("\n### Closure summary (hall_icp_neutralizer, flight-representative cases, all levers evaluated)\n")
    L.append("| node | status | baseline worst T_max (degC) | worst margin to limit (K) | baseline nominal (degC) | "
             "levers closing every case | necessary check |\n|---|---|---|---|---|---|---|")
    for n, s in th["closure_summary_hall_icp_neutralizer"].items():
        L.append(f"| {n} | {s['status']} | {s['baseline_worst_T_max_C']} | {s['baseline_worst_margin_K']} | "
                 f"{s['baseline_nominal_T_C']} | {', '.join(s['levers_that_close_every_case']) or '-'} | "
                 f"{', '.join(s['necessary_check']) or '-'} |")
    L.append("\n### Worst-case T_max per lever (degC, max over cases; hall_icp_neutralizer)\n")
    res = th["results"]["hall_icp_neutralizer"]
    nodes = list(th["closure_summary_hall_icp_neutralizer"])
    L.append("| lever | " + " | ".join(nodes) + " |\n|---|" + "---|" * len(nodes))
    for lv, cases in res.items():
        L.append(f"| {lv} | " + " | ".join(str(max(cases[c]["nodes"][n]["T_max_C"] for c in cases)) for n in nodes) + " |")
    L.append("\nLevers:\n")
    for k, v in th["levers"].items():
        L.append(f"- **{k}**: {v['what']}")
    b = th["bn_wall_11_2K_case"]
    L.append(f"\n### The v1 11.2 K BN-wall case\n\nv1: {b['v1']['case']} margin {b['v1']['v1_margin_worst_K']} K. "
             f"New rule: {b['rule']}. Status **{b['status']}** (baseline worst T_max {b['baseline_worst_T_max_C']} degC; "
             f"levers closing: {', '.join(b['levers_that_close']) or 'none'}; outer wall {b['outer_wall']['status']}).\n")
    L.append("### Heat into the spacecraft mount vs row 85 (25/50/100 W)\n")
    L.append("| lever | case | Q_mount min / nominal / max (W) | 25 W | 50 W | 100 W |\n|---|---|---|---|---|---|")
    for lv, cases in th["mount_heat_vs_row85"].items():
        for c, r in cases.items():
            q = r["Q_mount_W"]
            w = r["within_allowable_W"]
            L.append(f"| {lv} | {c} | {q['min_W']} / {q['nominal_W']} / {q['max_W']} | {w['25']} | {w['50']} | {w['100']} |")
    L.append(f"\nICP heat into H-1 (linearised allowance per lever set, min over cases and nodes): {th['icp_heat_into_h1']['min_allowance_W']} W "
             f"(injection at outer front pole PO / back plate BP). {th['icp_heat_into_h1']['note']}\n")
    L.append("### hall_c1_reference ground article (C1 coupled as v1 bound)\n")
    L.append("| lever | node | T_max (degC) | verdict |\n|---|---|---|---|")
    for lv, cases in th["results"]["hall_c1_reference"].items():
        for n, e in cases["ground"]["nodes"].items():
            L.append(f"| {lv} | {n} | {e['T_max_C']} | {e['verdict']} |")
    sm = doc["recomputations"]["small"]
    L.append("\n## Small derivations\n")
    for k, v in sm.items():
        L.append(f"- **{k}**: {_fmt(v['value'], 200)} {v['units']} - {v['formula'] if 'formula' in v else ''}")
    # register
    L.append("\n## (a) Revision register\n")
    L.append("| id | H2 lane / item | topic | old | new | units | driver | evidence | status | freeze |\n"
             "|---|---|---|---|---|---|---|---|---|---|")
    for r in doc["revision_register"]:
        o = r["old"]
        ov = o[o["field"]]
        nv = r["new"].get("requirement", "") + (f" [{_fmt(r['new'].get('value'), 90)}]" if r["new"].get("value") is not None else "")
        L.append(f"| {r['id']} | {r['h2_lane']} {r['h2_item']} | {r['topic']} | {_fmt(ov, 110)} | {_fmt(nv, 260)} | "
                 f"{r['units']} | {_drv(r['driver'])} | {r['evidence_class']} | {r['status']} | {r['freeze_point']} |")
    L.append("\nEach entry's old value carries `path + pointer + sha256` in the JSON (`revision_register[*].old.source`).\n")
    L.append("## (a) New A9 items\n")
    L.append("| id | name | value | units | basis | evidence | status | freeze |\n|---|---|---|---|---|---|---|---|")
    for i in doc["new_items"]:
        L.append(f"| {i['id']} | {_fmt(i['name'], 140)} | {_fmt(i['value'], 90)} | {i['units']} | {i['basis']} | "
                 f"{i['evidence_class']} | {i['status']} | {i['freeze_point']} |")
    L.append("\n## (b) Interface demands\n")
    L.append("| id | from | to | quantity | value | units | status |\n|---|---|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        L.append(f"| {d['id']} | {d['from']} | {d['to']} | {_fmt(d['quantity'], 220)} | {_fmt(d['value'], 90)} | "
                 f"{d['units']} | {d['status']} |")
    L.append("\n## (c) Owner answers applied\n")
    L.append("| row | covers | how applied |\n|---|---|---|")
    for a in doc["owner_answers_applied"]:
        L.append(f"| {a['row']} | {', '.join(a['covers_ids'])} | {a['how_applied']} |")
    L.append("\nA9.1 decisions applied:\n")
    L.append("| id | how applied |\n|---|---|")
    for a in doc["a9_1_decisions_applied"]:
        L.append(f"| {a['id']} | {a['how_applied']} |")
    L.append("\n## (d) Open owner questions (new)\n")
    for q in doc["open_owner_questions"]:
        L.append(f"- **{q['id']}**: {q['question']} Proposed: {q['proposed_answer']}")
    L.append("\n## (e) Historical reuse\n")
    for r in doc["historical_reuse"]["reused"]:
        L.append(f"- reused `{r['path']}` (`{r['sha256'][:16]}...`): {r['what']}")
    for r in doc["historical_reuse"]["not_reused"]:
        L.append(f"- NOT reused `{r['path']}` (`{r['sha256'][:16]}...`): {r['what']}")
    L.append("\n## (f) M16 impact\n")
    L.append("| row | key | how touched | proposed state | blocking item |\n|---|---|---|---|---|")
    for m in doc["m16_impact"]:
        L.append(f"| {m['m16_row']} | {m['key']} | {m['how_touched']} | {m['proposed_state']} | {m['blocking_item']} |")
    L.append("\n## (g) H3 inputs (quotation only) and H4 inputs\n")
    for h in doc["h3_inputs"]:
        L.append(f"- {h['id']}: {h['item']} - {h['status']}")
    for h in doc["h4_inputs"]:
        L.append(f"- {h['id']}: {h['test']} ({h['freeze_point']})")
    hic = doc["hard_incompatibility_check"]
    L.append(f"\n## Hard-incompatibility check\n\nVerdict `{hic['verdict']}` (nodes {hic['nodes']}); veto claimed: "
             f"{hic['veto_claimed']}. {hic['checked']}.\n")
    return "\n".join(L) + "\n"


def outputs() -> dict:
    doc = build()
    return {OUT_JSON: dump(doc), OUT_MD: render_md(doc)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, ROOT)
    outs = outputs()
    if a.check:
        bad = []
        for rel, txt in outs.items():
            p = _abs(rel)
            if not os.path.isfile(p) or open(p, encoding="utf-8").read() != txt:
                bad.append(rel)
        if bad:
            print("out of date: " + ", ".join(bad))
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
