#!/usr/bin/env python3
"""Mass / thermal / life / start-up veto layer (follow-on fo_veto_layer, trigger T_VETO_LAYER), v1.

Question: can mass, thermal rejection, life (firing and mission) or start-up veto any of hall_only, rf_hall, ecr_hall
against the RFP envelope as recorded in this repository (< 40 kg, < 1.5 kW, > 15,000 h firing, 26,000 h mission), and on
what evidence?

This script is the only producer of
    docs/architecture_comparison/veto_layer/veto_layer_v1.json   (validated against veto_layer_v1.schema.json)
    docs/architecture_comparison/veto_layer/VETO_LAYER.md        (generated from the JSON)

    python docs/architecture_comparison/veto_layer/build_veto_layer.py            # write both files
    python docs/architecture_comparison/veto_layer/build_veto_layer.py --check    # byte-for-byte reproduction check

Rules it implements (DRAFT for owner review):
- Every input file is pinned by sha256 and the lane that produced it (PINS). A missing or changed input raises
  InputError; nothing falls back to a default.
- Every number in the output is read from a pinned input file (JSON path recorded) or is simple arithmetic on such
  numbers done here (the relation is recorded). Nothing is typed in from memory.
- Per architecture x dimension the status is
    VETO_CANDIDATE            a failing-side bound exists whose basis the lane-24 hard-gate matrix accepts for FAIL on
                              the mapped criterion (fail_sufficient_bases), and the bound lies on the failing side;
    NO_VETO_WITHIN_EVIDENCE   at least one such verdict-eligible failing-side bound exists and none lies on the failing
                              side (this is NOT a PASS; missing contributors stay listed);
    UNDETERMINED              no verdict-eligible failing-side bound exists; the missing inputs are named with lanes.
  Risk indicators (literature on similar hardware, secondary reports, developer model claims, scale-risk flags) are
  recorded with their evidence class and conditional margins, but they never produce a VETO_CANDIDATE.
- ELIMINATED_WITHIN_TESTED_ENVELOPE is reported ONLY when the lane-24 evaluator (abep_sim.hard_gates.evaluate_all, not
  modified here) returns a binding-gate FAIL for that architecture on the mapped gate. VETO_CANDIDATEs and the risk
  indicators that map onto a lane-24 metric are submitted to that evaluator as hard_gate_evidence_v1 items.
- No Hall transport closure is used (credible set empty, gate 3 FAIL); no screening candidate; no winner; no ranking.
- The valve-outlet feed state (lane_16_feed_envelope) and the compressor bus draw (upstream ICD lane_33_upstream_icd
  offers only a repository model interface; lane_20 keeps the load TBD) are never filled: they appear only as TBD
  blockers.

Pure: standard library plus the in-repository abep_sim.hard_gates (imported lazily, after the pins are checked).
Not wired into archengine; goldens do not move.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_JSON = os.path.join(HERE, "veto_layer_v1.json")
OUT_MD = os.path.join(HERE, "VETO_LAYER.md")
SCHEMA_FILE = os.path.join(HERE, "veto_layer_v1.schema.json")
REL_SELF = "docs/architecture_comparison/veto_layer/build_veto_layer.py"

SCHEMA_ID = "veto_layer_v1"
BASE_COMMIT = "bad6ea0d6b94c343082dbbc5c0740310e0e7726d"
CREATED = "2026-09-26"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")
STATUSES = ("VETO_CANDIDATE", "NO_VETO_WITHIN_EVIDENCE", "UNDETERMINED")
FINAL_ONLY = "ELIMINATED_WITHIN_TESTED_ENVELOPE"
DIMENSIONS = ("mass", "thermal", "life_firing", "life_mission", "startup")


if ROOT not in sys.path:          # the lane-24 evaluator is an in-repository module (imported lazily)
    sys.path.insert(0, ROOT)


class InputError(RuntimeError):
    """A pinned input is missing, changed, or lacks a value this layer reads. Never a fallback."""


# ---------------------------------------------------------------------------------------------------------------------
# Input pins: every file read, with the lane commit that produced it. All are merged at BASE_COMMIT EXCEPT the four
# lane_15_thermal_life files, which are pinned at the lane_15 repair commit 66ff83b (not in BASE_COMMIT, and not recorded
# as verified in the registry or trigger ledger at BASE_COMMIT; see PIN_PROVENANCE_NOTES).
# ---------------------------------------------------------------------------------------------------------------------
_L21 = ("lane_21_mass_bom", "41acbb9e8d43f68925b23d3449b83f28acddd7d1")
_L15 = ("lane_15_thermal_life", "66ff83be5506097025905332b0b28e9e3fe4e19e")   # repair commit, NOT in BASE_COMMIT
_L24 = ("lane_24_hard_gates", "08b9f9bf32a0b34142338b2003f2b2cf02ecaacc")
_L19 = ("lane_19_cathode_integration", "eff15f85c53244556b1a9a9274fb7ffe80e9fa90")
_L20 = ("lane_20_ppu_magnet", "f7c226848d85fedb70c03bae9971be3b2bbde1fe")
_L22 = ("lane_22_scaling", "c43d2d6ebddc244dc02d96ffbe7d52526de905c7")
_L09 = ("lane_09_hall_sustainment", "f458811a5720a20216379dd1f701a54d21faf2b6")
_L07 = ("lane_07_rf_evidence", "336d548042359f8559d0bf50a409a976c0158fc2")
_L08 = ("lane_08_ecr_evidence", "a85fd592618cb15a02f14123659a0698db90df19")
_L32 = ("lane_32_wall_life", "f3c924a791a01f69e1a9165a74b88c1446e203d3")
_L10 = ("lane_10_cathode_dossier", "1b6fc10ab11798dce1e5ed3079cae1210fbb8d2d")
_L33 = ("lane_33_upstream_icd", "ced4aa08c4f19455a7b0c70b50a47d1f8e7727fe")
_REPO = ("repository (not a lane; CLAUDE.md next-work 1)", BASE_COMMIT)

PINS: tuple = (
    ("abep_sim/mass_bom.py", "c785aeb14b789b20a20a796ab86d8acd354760b52ac30827b395a623430e4a39", _L21,
     "mass BOM module (read for provenance; the v1 skeleton result is taken from mass_bom_v1.json)"),
    ("docs/architecture_comparison/mass_bom/mass_bom_v1.json",
     "8ab97ff93f507899508374d4ce8116e7066c31e3fbe2c79300f5b55372ba7313", _L21,
     "items, lower bounds, plausibility screen (G3 FAIL-side feed)"),
    ("docs/architecture_comparison/mass_bom/MASS_BOM.md",
     "e050e2fb445ca613fac970b0a0cf2664a2f021dab381c5cce11b71d9e2a7387e", _L21, "mass accounting rules"),
    ("abep_sim/thermal_life.py", "dce2048233746ecc596866c1d561c8828f820c7960b9778db0d6d66a9c86d83c", _L15,
     "thermal/life framework (no Vyovrinda result exists; read for provenance)"),
    ("abep_sim/thermal.py", "3ad94b716dd78e863ad441a78ffdc7fd3ef38b2764a7aabaace6876a2f1444fb", _REPO,
     "legacy Phase-4 lumped thermal network with uncited dataclass defaults; NOT used as evidence"),
    ("schemas/thermal_life/limits_v1.json", "0df363f76dcb6efcef41bc0a07e1775b6255c2c9d84b185228862958ef827dbb",
     _L15, "sourced / TBD thermal and life limit records"),
    ("schemas/thermal_life/inputs_v1.json", "937e5c643ef6d1b567319ad788915cd8e9f9b6ab78fc8df91454bdb300f0777f",
     _L15, "thermal/life input contract (what each component needs, and from where)"),
    ("docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md",
     "c07c9441505669ee6d4c3fcd3cf54d2e03dc749ea991f99098e64c193d6f134e", _L15, "thermal/life framework document"),
    ("abep_sim/hard_gates.py", "a36fe3c9065291f0fe5be3f17e179d5b691f00c013f7f8ef299fa89db896dda8", _L24,
     "lane-24 evaluator (called, never modified)"),
    ("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json",
     "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f", _L24,
     "gate thresholds, evidence-basis rules, elements"),
    ("schemas/architecture_comparison/hard_gates_v1.schema.json",
     "e5c70c588f3e785720c0d9d01013e5725807b9fd288fa8a1bddf6ba6d86f54ba", _L24, "evidence-item schema"),
    ("docs/architecture_comparison/hard_gates/evidence_register_v1.json",
     "45dfbfb311441aeb7c9c58f5dbb9ffb39c28fa448b85de552c37e8268ff94a3d", _L24,
     "registered hard-gate evidence (source of verdict-eligible bounds)"),
    ("docs/architecture_comparison/hard_gates/hard_gate_status_v1.json",
     "2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527", _L24, "committed hard-gate status"),
    ("abep_sim/cathode_integration.py", "9c8e776b851c112da89b0621a2e1da0dd128ab647229214b81aed19c3e0561b0", _L19,
     "cathode integration module (provenance)"),
    ("docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json",
     "df020bfe3ef87b0fc6f49c56db7e38dc585c4640b5c89dd167d1f18e928dbd6f", _L19,
     "cathode parameters, PROPOSED thresholds, RFP record"),
    ("docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json",
     "a0c8c247d2f87654568da3c01fece2ad562c1ca8e2ba78140813394aed81c125", _L19,
     "derived cathode Xe mass vs RFP, start-up heater energy"),
    ("docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
     "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501", _L20,
     "component load brackets (cathode heater start-up), compressor model status"),
    ("docs/architecture_comparison/scaling/scaling_similarity.json",
     "a604d93f576c4106a819b5679f0562060f0f7d9dc8f7078924d29bfd025644fe", _L22,
     "surface-to-volume / wall-life transfer risk (TR-10)"),
    ("docs/evidence/hall_sustainment/hall_sustainment_matrix.json",
     "76bba594eb1175b2186a8066b38665a2ce5e4cf77487c90f4af2e187a0b82dcc", _L09,
     "air-fed Hall endurance / erosion observations (E07, E09)"),
    ("docs/evidence/rf_source/rf_evidence_matrix.json",
     "5f6d4e0ede8b2e21e45b740c28ac9320e7ddd6cfd70ef05012f85712ae0ac8e8", _L07,
     "RF source thermal / erosion / mass evidence"),
    ("docs/evidence/ecr_source/ecr_evidence_matrix.json",
     "4a65dbeec34f16f048fa515ced3bb959c02a981113e25da89e8bb844337fec88", _L08,
     "ECR source thermal / mass / cathode-exposure evidence"),
    ("abep_sim/hall_ensemble.py", "218f890c8444af1f593396da5051e38d2d093bbb3cb0bc976cc44b01b67df704", _REPO,
     "admitted-member lookup used by the lane-24 evaluator"),
    ("hallthruster_bridge/ensemble/transport_ensemble_v0.json",
     "2d5069a3382ab667362befeeb5a737261f70a279d19cb89ee79cb61ae35ba08b", _REPO,
     "transport ensemble (admitted members: none; read-only)"),
    ("docs/evidence/wall_life/sputter_yield_db_v1.json",
     "315fbd44da2ee16246edb95830be09e0f05b9237cd5ca0a4c86a02a7e25bfffa", _L32,
     "wall-life evidence DB (read for its no-design-life statement; blocker record)"),
    ("docs/evidence/cathode/cathode_evidence_v1.json",
     "050060204e443d5583c307becadaab55a9f213d406ff4454be856bca21249110", _L10,
     "cathode dossier (baseline decision; numeric parameters enter via lane 19)"),
    ("schemas/interfaces/upstream_icd_v1.json",
     "2437d125060f2f24da06ac33b22220483f70b411033c91682cdffb5f01310850", _L33,
     "upstream ICD (compressor electrical-input field status; the bus draw stays TBD)"),
)

# Blocking lanes named in the output. Lanes 10, 32 and 33 are merged at BASE_COMMIT and recorded as two-lens-v2 with the
# second lens passed in docs/orchestration/lane_registry_v1.json at that commit (lane_32 verified_pin f3c924a); their
# files are pinned above and read by external_blockers() only to record WHY they do not decide any cell.
_EXTERNAL_BLOCKERS_STATIC = {
    "lane_32_wall_life": {
        "path": "docs/evidence/wall_life/", "in_base_commit": True, "lane_commit": _L32[1],
        "verification": "two-lens-v2, second lens passed; verified_pin f3c924a (docs/orchestration/lane_registry_v1.json "
                        "at base bad6ea0)",
        "note": "wall erosion / sputter-yield evidence DB; pinned and read here. Not used as a life value because the "
                "DB itself states that no N/O design-life or erosion-rate number can be derived from this version "
                "(quoted in 'read'); it names the evidence a Hall-channel life bound still needs."},
    "lane_33_upstream_icd": {
        "path": "schemas/interfaces/", "in_base_commit": True, "lane_commit": _L33[1],
        "verification": "two-lens-v2, second lens passed (docs/orchestration/lane_registry_v1.json at base bad6ea0)",
        "note": "upstream ICD; pinned and read here. The compressor electrical input field lists a repository model "
                "producer (abep_sim.compressor, model-derived, validity domain D-DRAGCOMP, uncertainty TBD), i.e. a "
                "model interface, not a sourced or measured load; lane_20 electrical closure keeps the compressor load TBD "
                "(its code defaults are unsourced). This layer therefore keeps the compressor bus draw TBD and never "
                "fills it (lane brief)."},
    "lane_10_cathode_dossier": {
        "path": "docs/evidence/cathode/", "in_base_commit": True, "lane_commit": _L10[1],
        "verification": "two-lens-v2, second lens passed, verified commit unchanged (docs/orchestration/"
                        "lane_registry_v1.json at base bad6ea0)",
        "note": "cathode dossier; pinned and read here. Its numeric cathode parameters enter this layer through "
                "lane_19_cathode_integration (which consumes the dossier); the dossier itself is cited for the "
                "baseline decision and the open uncertainty / hardware-test items (U.., G..) named in the cells."},
    "lane_16_feed_envelope": {
        "path": "docs/architecture_comparison/feed_envelope/", "in_base_commit": True, "lane_commit": None,
        "verification": "not read by this layer",
        "note": "valve-outlet feed state is TBD there; never filled here"},
}


PIN_PROVENANCE_NOTES = [
    {"lane": _L15[0], "lane_commit": _L15[1],
     "note": "The four lane_15 files (abep_sim/thermal_life.py, schemas/thermal_life/limits_v1.json, inputs_v1.json, "
             "docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md) are pinned at the lane_15 repair commit 66ff83b (G11 "
             "wall-flux admission gate, on top of 1fb82f3). That commit is NOT in base bad6ea0, and at base neither "
             "docs/orchestration/lane_registry_v1.json nor trigger_ledger_v2.jsonl records it as verified: the "
             "T_VETO_LAYER claim records the verified lane_15 identity as d2325c8da3. Until the lane_15 repair is "
             "verified and merged, this layer does NOT rest on verified lane_15 inputs, and it must be merged only "
             "after that repair (merge order: lane_15 repair, then this layer). The branch carries the lane_15 repair "
             "commits only so that the pins resolve; this lane does not author them. No cell status depends on the "
             "difference from d2325c8da3 (the G11 gate only tightens the hall_discharge wall-flux contract)."},
]


def external_blockers(inputs: dict) -> dict:
    """Blocking-lane records, with the statements read from their pinned files (why none decides a cell)."""
    WL = "docs/evidence/wall_life/sputter_yield_db_v1.json"
    CA = "docs/evidence/cathode/cathode_evidence_v1.json"
    IC = "schemas/interfaces/upstream_icd_v1.json"
    EL = "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json"
    wl, ca, ic, ecl = inputs[WL], inputs[CA], inputs[IC], inputs[EL]
    nodl = _get(wl, ["hard_statements", "no_design_life_from_this_version"], WL)
    _need("No N/O design-life or erosion-rate number is supported" in nodl,
          f"{WL}: expected no-design-life statement changed")
    atm = _get(ca, ["baseline_decision", "atmospheric_gas_fed_cathode_operation"], CA)
    base_c = _get(ca, ["baseline_decision", "system_baseline_cathode"], CA)
    xf = _get(ic, ["$defs", "IF-A3", "properties", "electrical_power_W", "x-field"], IC)
    cp_load = _entry(_get(ecl, ["components", "compressor", "entries"], EL), "CP-LOAD", EL)
    _need(cp_load["evidence_class"] == "tbd", f"{EL}: CP-LOAD is no longer TBD; re-review this layer")
    out = copy.deepcopy(_EXTERNAL_BLOCKERS_STATIC)
    out["lane_32_wall_life"]["read"] = [
        {"file": WL, "path": "hard_statements.no_design_life_from_this_version", "value": nodl}]
    out["lane_10_cathode_dossier"]["read"] = [
        {"file": CA, "path": "baseline_decision.system_baseline_cathode", "value": base_c},
        {"file": CA, "path": "baseline_decision.atmospheric_gas_fed_cathode_operation", "value": atm}]
    out["lane_33_upstream_icd"]["read"] = [
        {"file": IC, "path": "$defs.IF-A3.properties.electrical_power_W.x-field.status", "value": xf["status"]},
        {"file": IC, "path": "$defs.IF-A3.properties.electrical_power_W.x-field.evidence_class_current",
         "value": xf["evidence_class_current"]},
        {"file": IC, "path": "$defs.IF-A3.properties.electrical_power_W.x-field.uncertainty",
         "value": xf["uncertainty"]},
        {"file": EL, "path": "components.compressor.entries[CP-LOAD].evidence_class", "value": cp_load["evidence_class"]},
    ]
    out["lane_16_feed_envelope"]["read"] = []
    return out


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inputs(root: str = ROOT, pins: tuple = PINS) -> dict:
    """Verify every pin and return {relpath: parsed JSON or None (non-JSON files are only hashed)}."""
    out: dict[str, Any] = {}
    problems = []
    for rel, sha, _lane, _role in pins:
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            problems.append(f"missing input {rel}")
            continue
        got = _sha256_file(p)
        if got != sha:
            problems.append(f"changed input {rel}: sha256 {got} != pinned {sha}")
            continue
        if rel.endswith(".json"):
            with open(p, encoding="utf-8") as f:
                out[rel] = json.load(f)
        else:
            out[rel] = None
    if problems:
        raise InputError("veto layer inputs do not match their pins (no fallback):\n  " + "\n  ".join(problems))
    return out


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise InputError(msg)


def _get(obj: Any, path: list, where: str) -> Any:
    cur = obj
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        elif isinstance(cur, list) and isinstance(k, int) and 0 <= k < len(cur):
            cur = cur[k]
        else:
            raise InputError(f"{where}: path {path} not found (at {k!r})")
    return cur


def _entry(entries: list, eid: str, where: str) -> dict:
    hit = [e for e in entries if e.get("id") == eid]
    _need(len(hit) == 1, f"{where}: entry {eid!r} not found exactly once")
    return hit[0]


def _r(x: float, nd: int = 6) -> float:
    """Deterministic rounding of arithmetic done here (significant digits)."""
    if x == 0:
        return 0.0
    return float(f"{x:.{nd}g}")


# ---------------------------------------------------------------------------------------------------------------------
# Lane-24 matrix: criteria each dimension maps onto
# ---------------------------------------------------------------------------------------------------------------------
DIMENSION_CRITERIA = {
    "mass": ["G3.mass_mev"],
    "thermal": ["P1.thermal_margin"],
    "life_firing": ["G4.firing_life", "P2.cathode_life"],
    "life_mission": ["G5.mission_capability"],
    "startup": ["G2.bus_power_max", "P2.start_cycles"],
}
DIMENSION_MODE = {"startup": "startup"}      # the operating mode a start-up bound would be stated in


def criteria_info(matrix: dict) -> dict:
    out = {}
    for g in matrix["gates"]:
        for c in g["criteria"]:
            out[c["id"]] = {"gate": g["id"], "gate_status": g["status"], "binding": g["binding"],
                            "metric": c["metric"], "comparator": c["comparator"], "threshold": c["threshold"],
                            "unit": c["unit"], "criterion_status": c["status"],
                            "counts_for_fail": c["counts_for_fail"],
                            "fail_sufficient_bases": list(c["fail_sufficient_bases"]),
                            "fail_must_cover": c["fail_must_cover"], "envelope": c["envelope"],
                            "elements_semantics": c.get("elements_semantics"),
                            "threshold_source": c["threshold_source"]}
    return out


def mapping_for(dim: str, arch: str, cinfo: dict) -> list:
    rows = []
    for cid in DIMENSION_CRITERIA[dim]:
        _need(cid in cinfo, f"hard-gate matrix lacks criterion {cid}")
        c = cinfo[cid]
        elims = c["binding"] and c["counts_for_fail"] and c["threshold"] is not None
        note = []
        if not c["binding"]:
            note.append(f"gate {c['gate']} is {c['gate_status']} (non-binding): a FAIL is reported as 'would eliminate "
                        "only if the owner adopts this gate', never as an elimination")
        if c["threshold"] is None:
            note.append(f"threshold TBD: {c['threshold_source']}")
        mode = DIMENSION_MODE.get(dim)
        if mode and "operating_modes" in c["fail_must_cover"] and mode not in c["fail_must_cover"]["operating_modes"]:
            elims = False
            note.append(f"fail_must_cover.operating_modes = {c['fail_must_cover']['operating_modes']} excludes "
                        f"'{mode}': a {mode}-only bound cannot FAIL this criterion under matrix v1 (owner reading)")
        els = c["envelope"].get("elements")
        rows.append({"criterion": cid, "gate": c["gate"], "gate_status": c["gate_status"], "binding": c["binding"],
                     "metric": c["metric"], "comparator": c["comparator"], "threshold": c["threshold"],
                     "unit": c["unit"],
                     "elements": (list(els.get("common", [])) + list(els.get(arch, []))) if isinstance(els, dict)
                     else None,
                     "fail_sufficient_bases": c["fail_sufficient_bases"],
                     "can_eliminate_on_this_dimension": bool(elims), "notes": note})
    return rows


# ---------------------------------------------------------------------------------------------------------------------
# Verdict-eligible failing-side bounds (the only thing that can make a VETO_CANDIDATE)
# ---------------------------------------------------------------------------------------------------------------------
def _side(value: dict, crit: dict) -> str | None:
    from abep_sim import hard_gates as hg        # lazy: pins are checked before any import
    return hg._side(value, crit["comparator"], crit["threshold"], False)


def eligible_bounds(dim: str, arch: str, inputs: dict, cinfo: dict) -> list:
    """Failing-side bounds whose basis the lane-24 matrix accepts for FAIL on the mapped criterion."""
    out = []
    register = inputs["docs/architecture_comparison/hard_gates/evidence_register_v1.json"]
    for it in register["items"]:
        if it["criterion"] not in DIMENSION_CRITERIA[dim] or arch not in it["architectures"]:
            continue
        c = cinfo[it["criterion"]]
        if it["basis"] not in c["fail_sufficient_bases"]:
            continue
        side = _side(it["value"], c)
        out.append({"from": "docs/architecture_comparison/hard_gates/evidence_register_v1.json", "id": it["id"],
                    "criterion": it["criterion"], "basis": it["basis"], "value": it["value"],
                    "side": side or "undecided", "evidence_item": it})
    if dim == "mass":
        bom = inputs["docs/architecture_comparison/mass_bom/mass_bom_v1.json"]
        scr = _get(bom, ["plausibility_screen", "architectures", arch], "mass_bom_v1.json")
        # Only a lower bound that the mass BOM itself declares G3 FAIL-side evidence and that exceeds the limit counts.
        # A partial lower bound below the limit shows only the absence of failing-side evidence (items without a
        # lower bound are missing), so it is NOT added: it can never turn a cell into NO_VETO_WITHIN_EVIDENCE.
        if scr["items_with_lower_bound"]:
            lb = scr["cbe_margin_free_lower_bound_kg"]
            thr = cinfo["G3.mass_mev"]["threshold"]
            if scr["verdict"] == "EXCEEDS_LIMIT_MARGIN_FREE" and scr["g3_fail_evidence"] and lb > thr:
                out.append({"from": "docs/architecture_comparison/mass_bom/mass_bom_v1.json",
                            "id": f"mass_bom:{arch}", "criterion": "G3.mass_mev",
                            "basis": "per-item sourced lower bounds (mass_bom screen)",
                            "value": {"kind": "lower_bound", "value": lb}, "side": "fail", "evidence_item": None})
    return out


def classify(bounds: list) -> str:
    if any(b["side"] == "fail" for b in bounds):
        return "VETO_CANDIDATE"
    if bounds:
        return "NO_VETO_WITHIN_EVIDENCE"
    return "UNDETERMINED"


def final_status(status: str, arch: str, criteria: list, lane24: dict) -> str:
    """ELIMINATED_WITHIN_TESTED_ENVELOPE only when the lane-24 evaluator returns a binding-gate FAIL on a mapped gate."""
    res = lane24["architectures"][arch]
    gates = {c["gate"] for c in criteria}
    if status == "VETO_CANDIDATE" and res["eliminated"] and any(e["gate"] in gates for e in res["elimination_basis"]):
        return FINAL_ONLY
    return status


# ---------------------------------------------------------------------------------------------------------------------
# Risk indicators (never verdict-bearing): every number read from a pinned file
# ---------------------------------------------------------------------------------------------------------------------
def risk_indicators(inputs: dict, cinfo: dict) -> list:
    hs = inputs["docs/evidence/hall_sustainment/hall_sustainment_matrix.json"]
    rf = inputs["docs/evidence/rf_source/rf_evidence_matrix.json"]
    ecr = inputs["docs/evidence/ecr_source/ecr_evidence_matrix.json"]
    cdat = inputs["docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json"]
    cder = inputs["docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json"]
    ecl = inputs["docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json"]
    scal = inputs["docs/architecture_comparison/scaling/scaling_similarity.json"]
    mass_lim = cinfo["G3.mass_mev"]["threshold"]
    fire_h = cinfo["G4.firing_life"]["threshold"]
    _need(cdat["rfp"]["mass_max_kg"]["value"] == mass_lim, "cathode data RFP mass limit != hard-gate G3 threshold")
    _need(cdat["rfp"]["firing_h_min"]["value"] == fire_h, "cathode data RFP firing hours != hard-gate G4 threshold")
    HS = "docs/evidence/hall_sustainment/hall_sustainment_matrix.json"
    RF = "docs/evidence/rf_source/rf_evidence_matrix.json"
    EC = "docs/evidence/ecr_source/ecr_evidence_matrix.json"
    CD = "docs/architecture_comparison/cathode_integration/cathode_integration_data_v1.json"
    CV = "docs/architecture_comparison/cathode_integration/cathode_integration_derived_v1.json"
    EL = "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json"
    SC = "docs/architecture_comparison/scaling/scaling_similarity.json"
    out = []

    # --- mass: cathode Xe consumed over the minimum firing (common-mode; straddles the limit)
    flows = _get(cder, ["xe_mass_vs_rfp", "reference_flows"], CV)
    _need(len(flows) > 0, f"{CV}: no reference flows")
    fmin = min(flows, key=lambda r: r["xe_kg_over_min_firing"])
    fmax = max(flows, key=lambda r: r["xe_kg_over_min_firing"])
    wmin = min(r["xe_kg_if_flowing_whole_mission"] for r in flows)
    wmax = max(r["xe_kg_if_flowing_whole_mission"] for r in flows)
    params = cdat["parameters"]
    lvl = sorted({params[r["parameter"]]["evidence_level"] for r in flows})
    out.append({
        "id": "RI-MASS-CATHODE-XE", "dimension": "mass", "scope": "common_mode", "architectures": list(ARCHITECTURES),
        "element": "xenon_chamber_and_xenon_load (cathode Xe share)",
        "statement": "IF the common cathode needs a constant Xe flow in the range of the reference flows (P5 setpoint, "
                     "SITAEL HC1/HC3 design ranges and diode tests), THEN the cathode Xe alone over the RFP minimum "
                     "firing spans the 40 kg limit from well inside it to beyond it (tank, anode Xe and ignition Xe "
                     "excluded).",
        "values": {"cathode_flow_mg_s": [fmin["flow_mg_s"], fmax["flow_mg_s"]],
                   "xe_kg_over_min_firing": [fmin["xe_kg_over_min_firing"], fmax["xe_kg_over_min_firing"]],
                   "xe_kg_if_flowing_whole_mission": [wmin, wmax],
                   "flow_using_whole_limit_mg_s": _get(cder, ["xe_mass_vs_rfp", "flow_consuming_whole_mass_limit_mg_s"],
                                                       CV)},
        "unit": "kg",
        "conditional_margin": {"quantity": "40 kg limit minus cathode Xe over the minimum firing",
                               "range": [_r(mass_lim - fmax["xe_kg_over_min_firing"]),
                                         _r(mass_lim - fmin["xe_kg_over_min_firing"])],
                               "unit": "kg",
                               "cathode_xe_consumption_fraction_of_limit": [
                                   _r(fmin["xe_kg_over_min_firing"] / mass_lim),
                                   _r(fmax["xe_kg_over_min_firing"] / mass_lim)],
                               "consumption_fraction_relation": "cathode Xe over the minimum firing / G3 threshold "
                                                                "(consumption share, not a margin)",
                               "relation": "margin = G3 threshold - xe_kg_over_min_firing (reference-flow extremes)"},
        "direction": "straddles_limit",
        "evidence_class": "inferred (arithmetic on measured / developer-stated flows of other cathodes)",
        "evidence_levels": lvl,
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": CV, "path": "xe_mass_vs_rfp.reference_flows"},
                        {"file": CD, "path": "parameters." + fmin["parameter"]},
                        {"file": CD, "path": "parameters." + fmax["parameter"]}],
        "why_not_verdict_bearing": "flows of other cathodes (P5 setpoint, SITAEL HC1/HC3 diode tests), not a "
                                   "Vyovrinda cathode minimum-flow curve; EVIDENCE.md level 3 is never verdict-bearing "
                                   "(lane-24 basis measurement_similar_hardware); the range straddles the limit",
        "to_become_verdict_bearing": "measured spot-mode minimum flow m_c,min(I_emit) of the selected cathode "
                                     "(measurement_same_hardware or Vyovrinda) with the required firing hours and the "
                                     "owner's Xe-duty interpretation (lane_19_cathode_integration, lane_10 dossier "
                                     "G06/U16, mass_bom OD-M4)",
        "architecture_modulation": "only through I_emit (cathode is common, INV-CATH): TBD, needs an admitted Hall "
                                   "closure or measurement",
    })

    # --- life_firing: Hall channel / anode on O2-bearing air (PPS1350, secondary)
    e07 = _entry(hs["entries"], "E07", HS)
    q_life = [q for q in e07["quantities"] if q["name"] == "ceramic-erosion-compatible lifetime (authors' estimate)"]
    q_ox = [q for q in e07["quantities"] if q["name"] == "steady duration before first flame-out"]
    _need(len(q_life) == 1 and len(q_ox) == 1, f"{HS}: E07 quantities not found")
    lo, hi = q_life[0]["value"]
    out.append({
        "id": "RI-LIFE-HALL-CHANNEL-AIR-EROSION", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "hall_discharge_channel",
        "statement": "A flight-type SPT (PPS1350) on N2/O2 with 10 % Xe was reported (second-hand) with ceramic "
                     "erosion 'compatible with' a lifetime below the RFP firing requirement.",
        "values": {"lifetime_estimate_h": [lo, hi]}, "unit": "h",
        "conditional_margin": {"quantity": "estimated life / RFP firing hours", "range": [_r(lo / fire_h),
                                                                                           _r(hi / fire_h)],
                               "unit": "1", "hours_short": [_r(fire_h - hi), _r(fire_h - lo)],
                               "relation": "ratio = lifetime_estimate_h / G4 threshold"},
        "direction": "toward_exceedance",
        "evidence_class": q_life[0]["evidence_class"], "evidence_levels": [e07["evidence_level"]],
        "lane24_basis": "engineering_estimate",
        "source_refs": [{"file": HS, "path": "entries[E07].quantities[ceramic-erosion-compatible lifetime (authors' "
                                             "estimate)]", "source_id": q_life[0]["source"],
                         "locator": q_life[0]["locator"]}],
        "why_not_verdict_bearing": "authors' extrapolation with method not given, reported second-hand (review, "
                                   "level 5) on different hardware (PPS1350, 10 % Xe in the anode flow); a life "
                                   "extrapolated with an unvalidated wear model is lane-24 basis engineering_estimate "
                                   "(never verdict-bearing); not of architecture scope: wall material, magnetic "
                                   "shielding (E09) and channel design are Vyovrinda design levers",
        "to_become_verdict_bearing": "Vyovrinda-geometry wall-erosion evidence: N/O sputter yields on the wall grade "
                                     "(lane_32_wall_life: no N/O design-life number derivable from DB v1), wall_life_trustworthy maps from an ADMITTED "
                                     "closure (gate 3), or an endurance test of the Vyovrinda channel",
        "architecture_modulation": "pre-ionization may change the ion species/energy mix reaching the walls "
                                   "(interstage, TR-16): TBD; the channel itself is common",
    })
    out.append({
        "id": "RI-LIFE-HALL-ANODE-OXIDATION", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "hall_discharge_channel (anode; element booking is this "
                                                         "layer's reading, verify)",
        "statement": "In the same PPS1350 N2/O2 + 10 % Xe endurance test, severe anode oxidation produced anomalous "
                     "discharge behaviour and a flame-out after about 314 h; further flame-outs followed within 75 h.",
        "values": {"steady_hours_before_first_flameout": q_ox[0]["value"]}, "unit": "h",
        "conditional_margin": {"quantity": "demonstrated steady hours / RFP firing hours",
                               "range": [_r(q_ox[0]["value"] / fire_h), _r(q_ox[0]["value"] / fire_h)], "unit": "1",
                               "relation": "ratio = steady hours before first flame-out / G4 threshold"},
        "direction": "toward_exceedance",
        "evidence_class": q_ox[0]["evidence_class"], "evidence_levels": [e07["evidence_level"]],
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": HS, "path": "entries[E07].quantities[steady duration before first flame-out]",
                         "source_id": q_ox[0]["source"], "locator": q_ox[0]["locator"]},
                        {"file": HS, "path": "entries[E06].observations.erosion"}],
        "lane24_basis_note": "lane 24 has no level-5 basis. measurement_similar_hardware is the closest "
                             "non-verdict basis in kind (a measured observation on other hardware), but its reason "
                             "text ('EVIDENCE.md level 3') overstates this item: the source entry is level 5 "
                             "(second-hand report via a review). Either label is non-verdict-bearing; the outcome "
                             "is unchanged.",
        "why_not_verdict_bearing": "different hardware and anode material, second-hand report (level 5); an anode "
                                   "material/design change is a design lever, so the observation has no architecture "
                                   "scope",
        "to_become_verdict_bearing": "oxidation-resistant anode evidence or an endurance test on O-bearing feed of "
                                     "the Vyovrinda anode (Vyovrinda design release; experiment protocol lane_06)",
        "architecture_modulation": "a pre-ionizer that dissociates O2 changes the atomic-O share reaching the anode: "
                                   "TBD (no model or measurement)",
    })
    e09 = _entry(hs["entries"], "E09", HS)
    out.append({
        "id": "RI-LIFE-HALL-SHIELDED-COUNTER", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "hall_discharge_channel",
        "statement": "Counter-indicator: a magnetically shielded Hall thruster (SITAEL HT5k DM2) on N2/O2 showed "
                     "shielding that 'seems effective' and no critical damage after a cumulative 10 h air test.",
        "values": {"observation": e09["observations"]["erosion"]}, "unit": "n/a",
        "conditional_margin": None, "direction": "away_from_exceedance",
        "evidence_class": e09["evidence_class"], "evidence_levels": [e09["evidence_level"]],
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": HS, "path": "entries[E09].observations.erosion"}],
        "why_not_verdict_bearing": "qualitative, 10 h only, different hardware; shows a design lever exists, which "
                                   "is why E07 has no architecture scope",
        "to_become_verdict_bearing": "Vyovrinda channel endurance / erosion measurement",
        "architecture_modulation": "none known",
    })

    # --- life_firing: cathode exposure to air (common-mode)
    e155 = _entry(ecr["entries"], "ECR-E155", EC)
    out.append({
        "id": "RI-LIFE-CATHODE-AIR-EXPOSURE", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "cathode",
        "statement": "LaB6 hollow cathodes exposed to air showed significant emitter/structure erosion at an air "
                     "fraction in Xe (secondary citation), and a review reports severe erosion/embrittlement of an "
                     "N2-fed HC20h after N2/O2 tests. The baseline cathode is Xe-fed; how much air reaches the emitter "
                     "(plume back-flow, attenuation) is TBD.",
        "values": {"air_fraction_in_xe_with_significant_erosion": e155["value"],
                   "hc20h_observation": e09["observations"]["cathode"]}, "unit": "1",
        "conditional_margin": None, "direction": "toward_exceedance",
        "evidence_class": e155["evidence_class"] + " (as cited, secondary; levels not stated per statement)",
        "evidence_levels": [],
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": EC, "path": "entries[ECR-E155]", "doi_or_url": e155["source"]["doi_or_url"],
                         "locator": e155["source"]["locator"]},
                        {"file": HS, "path": "entries[E09].observations.cathode"}],
        "lane24_basis_note": "measurement_similar_hardware is the closest non-verdict lane-24 basis in kind, but "
                             "its reason text ('EVIDENCE.md level 3') overstates this item: ECR-E155 is a secondary "
                             "citation with no evidence level stated, and the lane-09 E09 cathode observation is a "
                             "review's report. The item is treated as level 5-class (secondary); it is not submitted "
                             "to the evaluator (no lane-24 metric) and is non-verdict-bearing under either label.",
        "why_not_verdict_bearing": "secondary citations on other cathodes and feed compositions; no hours-to-failure; "
                                   "the emitter environment of the Xe-fed baseline is unknown (attenuation TBD)",
        "to_become_verdict_bearing": "emitter partial pressures of O/O2/N2 in the Vyovrinda configuration and a "
                                     "tolerance measurement (lane_10 dossier U03-U05, G02/G03; lane_19)",
        "architecture_modulation": "a pre-ionizer that raises the atomic-O share of the back-flow could differ between "
                                   "architectures: TBD",
    })
    life_dev = params["hc1_hc3_predicted_life_h"]
    out.append({
        "id": "RI-LIFE-CATHODE-DEVELOPER-MODEL", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "cathode",
        "statement": "The SITAEL HC1/HC3 developer model states an emitter-evaporation life higher than 10^4 h; as a "
                     "lower bound below the RFP firing hours it decides nothing.",
        "values": {"predicted_life_lower_bound_h": life_dev["value"]}, "unit": "h",
        "conditional_margin": {"quantity": "stated life lower bound / RFP firing hours",
                               "range": [_r(life_dev["value"] / fire_h), None], "unit": "1",
                               "relation": "lower bound only; upper end open"},
        "direction": "uninformative",
        "evidence_class": life_dev["quantity_type"], "evidence_levels": [life_dev["evidence_level"]],
        "lane24_basis": "engineering_estimate",
        "source_refs": [{"file": CD, "path": "parameters.hc1_hc3_predicted_life_h", "locator": life_dev["locator"]}],
        "why_not_verdict_bearing": "developer model on other cathodes, not life-tested to that duration; a lower "
                                   "bound below the threshold cannot show a failure",
        "to_become_verdict_bearing": "sourced LaB6 evaporation-rate table (thermal_life limit lab6_evaporation_rate "
                                     "TBD), insert mass/area and I_emit of the selected cathode (lane_19, lane_10)",
        "architecture_modulation": "through I_emit only (emitter temperature): TBD",
    })

    # --- life_firing / thermal: surface-to-volume scale risk (common-mode)
    tr10 = _entry(scal["transfer_register"], "TR-10", SC)
    invh = _get(scal, ["comparison", "N2", "S1_anchor_L", "inv_h"], SC)
    out.append({
        "id": "RI-LIFE-SCALE-WALL-FLUX", "dimension": "life_firing", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "hall_discharge_channel",
        "statement": "The sourced sizing rules put the Vyovrinda channel mostly narrower than P5, so the "
                     "surface-to-volume 1/h and wall-loss fraction rise; wall heat flux and erosion life are rated "
                     f"{tr10['transferability']} with risk {tr10['risk']}.",
        "values": {"inv_h_vyovrinda_envelope_per_m": invh["vyovrinda"], "inv_h_p5_per_m": invh["reference"],
                   "worst_ratio_to_p5": invh["worst"]}, "unit": "1/m",
        "conditional_margin": None, "direction": "toward_exceedance",
        "evidence_class": "model-derived (analysis envelope from sourced xenon-derived scaling relations)",
        "evidence_levels": [],
        "lane24_basis": "engineering_estimate",
        "source_refs": [{"file": SC, "path": "transfer_register[TR-10]"},
                        {"file": SC, "path": "comparison.N2.S1_anchor_L.inv_h"}],
        "why_not_verdict_bearing": "a scale-risk flag on an analysis envelope, not a life bound",
        "to_become_verdict_bearing": tr10["evidence_needed"],
        "architecture_modulation": "none (common Hall accelerator)",
    })

    # --- thermal / life / mass: RF-specific
    rf09 = _entry(rf["entries"], "RF-IPG6S-09", RF)
    out.append({
        "id": "RI-THERMAL-RF-PASSIVE-COOLING", "dimension": "thermal", "scope": "architecture_specific",
        "architectures": ["rf_hall"], "element": "rf_source",
        "statement": "The water-cooled IPG6-S RF source absorbed most of its power in the cooling water; downscaling "
                     "with passive cooling is named by the authors as the biggest challenge.",
        "values": {"observation": rf09["value"]}, "unit": "n/a", "conditional_margin": None,
        "direction": "toward_exceedance", "evidence_class": rf09["evidence_class"],
        "evidence_levels": [rf09["evidence_level"]], "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": RF, "path": "entries[RF-IPG6S-09]", "doi_or_url": rf09["source"]["doi_or_url"],
                         "locator": rf09["locator"]}],
        "why_not_verdict_bearing": "qualitative, water-cooled laboratory source at multi-kW class, not a "
                                   "flight-like passively cooled rf_source",
        "to_become_verdict_bearing": "rf_source heat fractions (thermal_life inputs rf_source.*) and the structure "
                                     "limit (thermal_life limit rf_source_structure_limit TBD), from source design or "
                                     "test (lane_07 evidence; rf_hall source design)",
        "architecture_modulation": "rf_hall only",
    })
    rf10 = _entry(rf["entries"], "RF-IPG6S-10", RF)
    rfd = _entry(rf["entries"], "RF-DUPP26-01", RF)
    out.append({
        "id": "RI-LIFE-RF-DIELECTRIC", "dimension": "life_firing", "scope": "architecture_specific",
        "architectures": ["rf_hall"], "element": "rf_source",
        "statement": "The only statements on RF-source erosion are a design claim (no plasma-contacting critical "
                     "components) and a review judgement ('Low' vulnerability); dielectric-tube erosion and O "
                     "recombination over > 15,000 h are not addressed by any accessed measurement.",
        "values": {"design_claim": rf10["value"], "review_judgement": rfd["value"]}, "unit": "n/a",
        "conditional_margin": None, "direction": "uninformative",
        "evidence_class": f"{rf10['evidence_class']} / {rfd['evidence_class']}",
        "evidence_levels": sorted({rf10["evidence_level"], rfd["evidence_level"]}),
        "lane24_basis": "assumption",
        "source_refs": [{"file": RF, "path": "entries[RF-IPG6S-10]"}, {"file": RF, "path": "entries[RF-DUPP26-01]"}],
        "why_not_verdict_bearing": "assumed / review judgement; no erosion rate or test duration",
        "to_become_verdict_bearing": "measured dielectric erosion / contamination of the rf_source on O-bearing feed",
        "architecture_modulation": "rf_hall only",
    })
    rf07 = _entry(rf["entries"], "RF-NO25-07", RF)
    out.append({
        "id": "RI-MASS-RF-HARDWARE-UNKNOWN", "dimension": "mass", "scope": "architecture_specific",
        "architectures": ["rf_hall"], "element": "rf_source (generator, matching, antenna)",
        "statement": "No accessed source states the mass of RF-stage hardware.",
        "values": {"mass_kg": rf07["value"]}, "unit": "kg", "conditional_margin": None,
        "direction": "uninformative", "evidence_class": "none (quantity absent from source)",
        "evidence_levels": [rf07["evidence_level"]], "lane24_basis": None,
        "source_refs": [{"file": RF, "path": "entries[RF-NO25-07]"}],
        "why_not_verdict_bearing": "no value",
        "to_become_verdict_bearing": "supplier-measured masses of the selected RF generator, matching network and "
                                     "antenna (mass_bom items rf_source, rf_generator, rf_matching_network)",
        "architecture_modulation": "rf_hall only",
    })

    # --- thermal / mass: ECR-specific
    e170 = _entry(ecr["entries"], "ECR-E170", EC)
    out.append({
        "id": "RI-THERMAL-ECR-MICROWAVE-LINE", "dimension": "thermal", "scope": "architecture_specific",
        "architectures": ["ecr_hall"], "element": "ecr_source (microwave line and components)",
        "statement": "In an ECR plasma thruster test, heating of cables and microwave components limited the "
                     "transmitted microwave power.",
        "values": {"transmitted_power_limit_W": e170["value"]}, "unit": e170["units"],
        "conditional_margin": None, "direction": "straddles_limit",
        "evidence_class": e170["evidence_class"], "evidence_levels": [],
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": EC, "path": "entries[ECR-E170]", "doi_or_url": e170["source"]["doi_or_url"],
                         "locator": e170["source"]["locator"]}],
        "why_not_verdict_bearing": "a laboratory line limit of another device; whether it binds depends on the "
                                   "required ecr_source power (TBD: interstage lane_18 / bus boundary lane_11) and on "
                                   "the flight microwave chain design; the source matrix gives no evidence level",
        "to_become_verdict_bearing": "ecr_source heat fractions and the structure limit (thermal_life limit "
                                     "ecr_source_structure_limit TBD) for the selected microwave chain",
        "architecture_modulation": "ecr_hall only",
    })
    e043 = _entry(ecr["entries"], "ECR-E043", EC)
    out.append({
        "id": "RI-MASS-ECR-AMPLIFIER-BREADBOARD", "dimension": "mass", "scope": "architecture_specific",
        "architectures": ["ecr_hall"], "element": "ecr_source (microwave source)",
        "statement": "A 5 W 2.45 GHz solid-state amplifier breadboard weighed about 100 g (housing, thermal and PPU "
                     "excluded); it is not a bound on the microwave source the ecr_hall arm needs.",
        "values": {"mass_g": e043["value"], "power_W": e043["conditions"]["power_W"]}, "unit": e043["units"],
        "conditional_margin": None, "direction": "uninformative",
        "evidence_class": e043["evidence_class"], "evidence_levels": [],
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": EC, "path": "entries[ECR-E043]", "doi_or_url": e043["source"]["doi_or_url"],
                         "locator": e043["source"]["locator"]}],
        "why_not_verdict_bearing": "breadboard at a different power level; a mass of one existing part is not a lower "
                                   "bound for every design of the architecture (MASS_BOM.md)",
        "to_become_verdict_bearing": "supplier-measured mass of the selected microwave source, waveguide and ECR "
                                     "magnets (mass_bom items microwave_source, waveguide, ecr_magnets)",
        "architecture_modulation": "ecr_hall only",
    })

    # --- start-up: cathode heater load vs the PROPOSED start-up peak limit (common-mode, partial)
    heaters = [e for e in _get(ecl, ["components", "cathode_heater", "entries"], EL)
               if e.get("role") == "load-bracket" and e.get("units") == "W"]
    vals = []
    val_src = []
    for e in heaters:
        v = e["value"]
        if e["value_kind"] == "number":
            vals.append(v)
            val_src.append((v, e["id"], e["evidence_level"]))
        elif e["value_kind"] == "range":
            vals += [v["min"], v["max"]]
            val_src += [(v["min"], e["id"], e["evidence_level"]), (v["max"], e["id"], e["evidence_level"])]
    _need(bool(vals), f"{EL}: no cathode-heater load brackets in W")
    ext_lo = sorted(x for x in val_src if x[0] == min(vals))
    ext_hi = sorted(x for x in val_src if x[0] == max(vals))

    def _ext(xs: list) -> str:
        return ", ".join(f"{i} (level {lv})" for _v, i, lv in xs)
    peak_lim = _get(cdat, ["proposed_thresholds", "startup_peak_limit"], CD)
    _need(peak_lim["status"] == "PROPOSED", f"{CD}: startup_peak_limit is expected to be PROPOSED")
    energy = [r["energy_Wh"] for r in _get(cder, ["startup_heater_energy"], CV)]
    starts = params["jpl_h6_heater_starts_min"]
    out.append({
        "id": "RI-STARTUP-CATHODE-HEATER", "dimension": "startup", "scope": "common_mode",
        "architectures": list(ARCHITECTURES), "element": "cathode_heater",
        "statement": "Reported LaB6 heater powers at ignition are far below the PROPOSED start-up peak limit; they are "
                     "only one contributor to the start-up peak (discharge ignition, magnets, flow control, "
                     "housekeeping and, in the V2 sequence, the pre-ionizer are TBD). The bracket extremes rest on "
                     f"{_ext(ext_lo)} for {_fmt(min(vals))} W and {_ext(ext_hi)} for {_fmt(max(vals))} W "
                     "(lane_20 electrical_closure entries; evidence levels as recorded there).",
        "values": {"heater_power_W": [min(vals), max(vals)], "energy_per_start_Wh": [_r(min(energy)),
                                                                                      _r(max(energy))],
                   "heater_starts_demonstrated_lower_bound": starts["value"]},
        "unit": "W",
        "conditional_margin": {"quantity": "PROPOSED start-up peak limit minus cathode heater power (heater alone)",
                               "range": [_r(peak_lim["value"] - max(vals)), _r(peak_lim["value"] - min(vals))],
                               "unit": "W", "limit_status": "PROPOSED (owner interpretation of '< 1.5 kW')",
                               "relation": "margin = startup_peak_limit - heater power (bracket extremes)"},
        "direction": "away_from_exceedance",
        "evidence_class": "measured (other LaB6 cathodes, load side)",
        "evidence_levels": sorted({e["evidence_level"] for e in heaters}),
        "lane24_basis": "measurement_similar_hardware",
        "source_refs": [{"file": EL, "path": "components.cathode_heater.entries[" + e["id"] + "]"} for e in heaters]
        + [{"file": CD, "path": "proposed_thresholds.startup_peak_limit"},
           {"file": CV, "path": "startup_heater_energy"},
           {"file": CD, "path": "parameters.jpl_h6_heater_starts_min"}],
        "why_not_verdict_bearing": "other cathodes, load side (not at bus_power_boundary_v1), one contributor of a "
                                   "sum; a heater-only bound is a partial lower bound on the start-up peak",
        "to_become_verdict_bearing": "the full start-up sequence at the bus boundary: discharge-ignition transient "
                                     "(admitted closure or measurement), pre-ionizer schedule V1/V2 (owner), compressor "
                                     "bus draw (lane_33 upstream ICD: model interface only; TBD), and the mission start count (operations "
                                     "concept; P2.start_cycles threshold TBD)",
        "architecture_modulation": "rf_hall / ecr_hall add their source power to the peak only if the pre-ionizer "
                                   "overlaps the heater phase (V2, PROPOSED): TBD",
    })
    _carry_hs_repository_status(out, hs, HS)
    return out


def _hs_repository_status(hs: dict) -> dict:
    """{entry id: repository_status block} for lane-09 entries that carry one (e.g. ECHT-N2 HISTORICAL_UNSUPPORTED)."""
    return {e["id"]: e["repository_status"] for e in hs["entries"] if e.get("repository_status")}


def _carry_hs_repository_status(ris: list, hs: dict, hs_path: str) -> None:
    """Carry a lane-09 entry's repository_status onto every source_ref that cites it (no silent drop)."""
    import re
    st = _hs_repository_status(hs)
    for ri in ris:
        for ref in ri["source_refs"]:
            if ref["file"] != hs_path:
                continue
            m = re.match(r"entries\[([A-Z0-9-]+)\]", ref["path"])
            _need(m is not None, f"{hs_path}: cannot parse cited entry in {ref['path']!r}")
            _entry(hs["entries"], m.group(1), hs_path)
            if m.group(1) in st:
                ref["repository_status"] = st[m.group(1)]["status"]
                ref["repository_status_ref"] = st[m.group(1)]["status_file"]
                _need(ri["lane24_basis"] != "hard_physical_bound",
                      f"{ri['id']}: an entry with repository_status {st[m.group(1)]['status']} cannot be verdict-bearing")


# ---------------------------------------------------------------------------------------------------------------------
# Missing inputs per architecture x dimension (named with the lanes / decisions that unblock them)
# ---------------------------------------------------------------------------------------------------------------------
MASS_ITEM_BLOCKERS = {
    "intake": ["design_release:vyovrinda_intake", "lane_33_upstream_icd"],
    "filter": ["design_release:vyovrinda_filter", "lane_33_upstream_icd"],
    "compressor": ["design_release:vyovrinda_compressor", "lane_33_upstream_icd"],
    "atmospheric_gas_chamber": ["design_release:vyovrinda_gas_chamber", "lane_33_upstream_icd"],
    "atmospheric_valve": ["part_selection:supplier_measured_mass", "lane_33_upstream_icd"],
    "xe_valve_and_flow_control": ["part_selection:supplier_measured_mass"],
    "xe_tank": ["owner_decision:OD-M4 (Xe allocation)", "part_selection:tank"],
    "xe_load": ["owner_decision:OD-M4 (Xe allocation)", "lane_19_cathode_integration (cathode Xe)"],
    "xe_residual": ["owner_decision:OD-M4 (Xe allocation)"],
    "hall_thruster_head": ["design_release:vyovrinda_hall_head (never from a closure)"],
    "hall_magnets": ["design_release:vyovrinda_magnetic_circuit", "lane_20_ppu_magnet (magnet_power)"],
    "cathode": ["lane_10_cathode_dossier", "lane_19_cathode_integration", "part_selection:cathode"],
    "ppu": ["lane_20_ppu_magnet", "part_selection:ppu"],
    "harness": ["all other dry items (5 % allocation of nominal dry mass, OD-M6)"],
    "thermal_hardware": ["lane_15_thermal_life (integrated thermal design)"],
    "structure": ["design_release:configuration_and_launch_loads"],
    "rf_source": ["lane_07_rf_evidence", "design_release:rf_source"],
    "rf_generator": ["part_selection:rf_generator"],
    "rf_matching_network": ["part_selection:rf_matching_network"],
    "ecr_source": ["lane_08_ecr_evidence", "design_release:ecr_source"],
    "microwave_source": ["part_selection:microwave_source"],
    "waveguide": ["part_selection:waveguide"],
    "ecr_magnets": ["design_release:ecr_magnetic_circuit", "lane_20_ppu_magnet (permanent_magnet mass)"],
}
THERMAL_COMPONENTS = {"hall_only": ["hall_discharge", "hall_magnet", "cathode"],
                      "rf_hall": ["hall_discharge", "hall_magnet", "cathode", "rf_source"],
                      "ecr_hall": ["hall_discharge", "hall_magnet", "cathode", "ecr_source", "ecr_magnet"]}
THERMAL_LIMIT_FOR = {"hall_discharge": ["bn_combat_m26"], "cathode": ["cathode_assembly_temperature_limit"],
                     "rf_source": ["rf_source_structure_limit"], "ecr_source": ["ecr_source_structure_limit"],
                     "hall_magnet": [], "ecr_magnet": []}


def wall_flux_gate_status(inputs: dict) -> dict:
    """Checks (from the pinned files, not by assumption) that the lane-15 G11 wall-flux gate is present and that no
    wall-flux input could exist today: the inputs contract carries wall_flux_provenance with its two admissible kinds,
    both wall-flux inputs are TBD, and the transport ensemble has no admitted member. This layer never imports
    abep_sim.thermal_life, never calls hallmap_wall_inputs / check_feasibility and never reads a Hall map or a
    screening-candidate flux, so no wall-flux verdict (heat or erosion life) is produced here."""
    contract = inputs["schemas/thermal_life/inputs_v1.json"]
    ens = inputs["hallthruster_bridge/ensemble/transport_ensemble_v0.json"]
    wfp = _get(contract, ["wall_flux_provenance", "kinds"], "thermal_life inputs contract")
    _need(set(wfp) == {"admitted_hallmap", "measured_hardware"},
          f"thermal_life wall_flux_provenance kinds changed: {sorted(wfp)} (update this layer)")
    cin = _get(contract, ["components", "hall_discharge", "inputs"], "thermal_life inputs contract")
    for f in ("wall_ion_flux_m2s", "wall_ion_energy_eV"):
        _need(str(cin[f].get("now", "")).startswith("TBD"), f"thermal_life input {f} is no longer TBD: update this "
              "layer")
    members = _get(ens, ["members"], "transport ensemble")
    _need(isinstance(members, list) and not members, "transport ensemble has admitted members: update this layer")
    return {"admissible_kinds": sorted(wfp), "admitted_members": 0,
            "statement": "not read and never passed: abep_sim/thermal_life.py (lane 15, G11 gate) accepts wall flux "
                         "only from an admitted ensemble member's wall_life_trustworthy Hall map or from measured "
                         "hardware with an evidence record; the pinned ensemble has 0 admitted members and no hardware "
                         "measurement exists, so both inputs are TBD and every hall_discharge heat / erosion-life cell "
                         "stays UNDETERMINED. This layer does not import thermal_life, does not call "
                         "hallmap_wall_inputs or check_feasibility, and has never used a screening-candidate "
                         "(sgb-screen-*) flux (build check)."}


def missing_inputs(dim: str, arch: str, inputs: dict) -> list:
    out = []
    if dim == "mass":
        bom = inputs["docs/architecture_comparison/mass_bom/mass_bom_v1.json"]
        items = {it["id"]: it for it in bom["items"]}
        scr = bom["plausibility_screen"]["architectures"][arch]
        for iid in scr["items_without_lower_bound"]:
            _need(iid in MASS_ITEM_BLOCKERS, f"mass item {iid} has no blocker mapping in this layer")
            lb = items[iid]["lower_bound"]
            out.append({"input": f"mass_bom item '{iid}': sourced lower bound", "requires": lb["requires"],
                        "blocking": MASS_ITEM_BLOCKERS[iid],
                        "scope": "architecture_specific" if items[iid]["scope"] != "common" else "common_mode"})
        return out
    contract = inputs["schemas/thermal_life/inputs_v1.json"]
    limits = inputs["schemas/thermal_life/limits_v1.json"]["records"]
    if dim == "thermal":
        for comp in THERMAL_COMPONENTS[arch]:
            cin = contract["components"][comp]["inputs"]
            tbd = sorted(k for k, v in cin.items() if str(v.get("now", "")).startswith("TBD"))
            out.append({"input": f"thermal_life component '{comp}': {len(tbd)} TBD inputs ({', '.join(tbd)})",
                        "requires": "; ".join(sorted({cin[k]["from"] for k in tbd})),
                        "blocking": ["lane_11_bus_boundary (component allocations)",
                                     "admitted Hall closure (gate 3; credible set empty)" if comp == "hall_discharge"
                                     else "design_release:" + comp,
                                     "thermal geometry / radiator design (rejection paths)"],
                        "scope": "architecture_specific" if comp in ("rf_source", "ecr_source", "ecr_magnet")
                        else "common_mode"})
            for rid in THERMAL_LIMIT_FOR[comp]:
                rec = limits[rid]
                _need(rec["status"] == "TBD", f"limit {rid} is no longer TBD: update this layer")
                out.append({"input": f"thermal_life limit record '{rid}'", "requires": rec["requires"],
                            "blocking": ["sourced limit (datasheet / dossier)"],
                            "scope": "architecture_specific" if comp in ("rf_source", "ecr_source")
                            else "common_mode"})
        out.append({"input": "valve-outlet feed state (thruster inlet)", "requires": "lane_16 feed envelope value; "
                    "TBD, never filled here", "blocking": ["lane_16_feed_envelope"], "scope": "common_mode"})
        return out
    if dim == "life_firing":
        rec = limits["lab6_evaporation_rate"]
        _need(rec["status"] == "TBD", "limit lab6_evaporation_rate is no longer TBD: update this layer")
        out += [
            {"input": "Hall wall erosion: erodible depth, peak/average flux, volumetric sputter yield of the wall grade "
                      "for the N/O ion mix", "requires": "Vyovrinda channel geometry; sourced N/O yields on BN/BN-SiO2",
             "blocking": ["lane_32_wall_life (DB v1: no N/O design-life number derivable)", "design_release:vyovrinda_channel",
                          "admitted Hall closure (gate 3) for wall_life_trustworthy maps"], "scope": "common_mode"},
            {"input": "Hall magnet insulation life basis", "requires": "thermal-endurance evaluation of the actual EIS "
                      "(iec60085_thermal_classes.life_basis_h TBD) or a coil life test",
             "blocking": ["design_release:vyovrinda_magnetic_circuit"], "scope": "common_mode"},
            {"input": "thermal_life limit record 'lab6_evaporation_rate'", "requires": rec["requires"],
             "blocking": ["lane_10_cathode_dossier", "lane_19_cathode_integration"], "scope": "common_mode"},
            {"input": "cathode insert mass, emitting area, I_emit, emitter O/O2 partial pressure",
             "requires": "selected cathode hardware; I_d from an admitted closure or measurement",
             "blocking": ["lane_19_cathode_integration", "lane_10_cathode_dossier", "admitted Hall closure (gate 3)"],
             "scope": "common_mode"},
            {"input": "compressor and valve firing life", "requires": "compressor / valve design and duty",
             "blocking": ["lane_33_upstream_icd (compressor load TBD)", "design_release:vyovrinda_compressor"],
             "scope": "common_mode"},
        ]
        if arch == "rf_hall":
            out.append({"input": "rf_source life (dielectric erosion, antenna insulation, generator)",
                        "requires": "measured erosion / contamination on O-bearing feed; rf_source_structure_limit",
                        "blocking": ["lane_07_rf_evidence", "design_release:rf_source"],
                        "scope": "architecture_specific"})
        if arch == "ecr_hall":
            out.append({"input": "ecr_source / ecr_magnet life (window/coupler erosion, magnet demagnetization over "
                                 "life)", "requires": "ecr_source_structure_limit; demag and knee fields of the grade",
                        "blocking": ["lane_08_ecr_evidence", "design_release:ecr_source"],
                        "scope": "architecture_specific"})
        return out
    if dim == "life_mission":
        out += [
            {"input": "mission-duration (26,000 h) capability of intake, filter, compressor, gas chambers and valves",
             "requires": "upstream element design and life evidence",
             "blocking": ["lane_33_upstream_icd (compressor load TBD)", "design_release:upstream_elements"],
             "scope": "common_mode"},
            {"input": "Hall thruster, cathode and PPU capability over 26,000 h including non-firing time (storage, "
                      "cycling, cathode flow between firings)",
             "requires": "operations concept (duty cycle, starts); cathode Xe-duty interpretation (mass_bom OD-M7)",
             "blocking": ["lane_19_cathode_integration", "lane_20_ppu_magnet", "owner_decision:operations_concept"],
             "scope": "common_mode"},
        ]
        if arch != "hall_only":
            out.append({"input": f"{'rf_source' if arch == 'rf_hall' else 'ecr_source / ecr_magnet'} capability "
                                 "over 26,000 h", "requires": "source design and life evidence",
                        "blocking": ["lane_07_rf_evidence" if arch == "rf_hall" else "lane_08_ecr_evidence"],
                        "scope": "architecture_specific"})
        return out
    if dim == "startup":
        out += [
            {"input": "hall_discharge ignition transient at the bus boundary", "requires": "measurement or an "
             "admitted closure (credible set empty)", "blocking": ["admitted Hall closure (gate 3)",
                                                                   "lane_06_experiment_protocol (measurement)"],
             "scope": "common_mode"},
            {"input": "compressor bus draw during start-up", "requires": "upstream ICD value; TBD, never filled here",
             "blocking": ["lane_33_upstream_icd (compressor load TBD)"], "scope": "common_mode"},
            {"input": "mission start count and required start-cycle capability",
             "requires": "operations concept; P2.start_cycles and G6.restart_count thresholds (TBD, OD5)",
             "blocking": ["owner_decision:OD5", "lane_10_cathode_dossier (U15/G05)"], "scope": "common_mode"},
            {"input": "interpretation: does '< 1.5 kW' bound start-up transients",
             "requires": "owner decision on the PROPOSED startup_peak_limit (cathode_integration_data_v1.json)",
             "blocking": ["owner_decision:startup_peak_limit"], "scope": "common_mode"},
        ]
        if arch != "hall_only":
            out.append({"input": "pre-ionizer start schedule (V1 after keeper-off / V2 before discharge ignition) and "
                                 "its power", "requires": "owner choice of V1/V2; source power at the boundary",
                        "blocking": ["owner_decision:preionizer_start_schedule", "lane_18_interstage",
                                     "lane_11_bus_boundary"], "scope": "architecture_specific"})
        return out
    raise ValueError(f"unknown dimension {dim}")


# ---------------------------------------------------------------------------------------------------------------------
# Lane-24 evaluator run
# ---------------------------------------------------------------------------------------------------------------------
RI_TO_CRITERION = {   # risk indicators whose quantity IS a lane-24 metric (others have no metric without a derivation)
    "RI-MASS-CATHODE-XE": ("G3.mass_mev", "interval", ["xenon_chamber_and_xenon_load"]),
    "RI-LIFE-HALL-CHANNEL-AIR-EROSION": ("G4.firing_life", "interval", ["hall_discharge_channel"]),
    "RI-LIFE-HALL-ANODE-OXIDATION": ("G4.firing_life", "upper_bound", ["hall_discharge_channel"]),
    "RI-LIFE-CATHODE-DEVELOPER-MODEL": ("P2.cathode_life", "lower_bound", None),
    "RI-STARTUP-CATHODE-HEATER": ("G2.bus_power_max", "interval", ["cathode_heater"]),
}


def _ri_value(ri: dict, kind: str) -> dict:
    v = ri["values"]
    if ri["id"] == "RI-MASS-CATHODE-XE":
        lo, hi = v["xe_kg_over_min_firing"]
    elif ri["id"] == "RI-LIFE-HALL-CHANNEL-AIR-EROSION":
        lo, hi = v["lifetime_estimate_h"]
    elif ri["id"] == "RI-LIFE-HALL-ANODE-OXIDATION":
        return {"kind": "upper_bound", "value": v["steady_hours_before_first_flameout"]}
    elif ri["id"] == "RI-LIFE-CATHODE-DEVELOPER-MODEL":
        return {"kind": "lower_bound", "value": v["predicted_life_lower_bound_h"]}
    elif ri["id"] == "RI-STARTUP-CATHODE-HEATER":
        lo, hi = v["heater_power_W"]
    else:
        raise ValueError(ri["id"])
    _need(kind == "interval", f"{ri['id']}: kind mismatch")
    return {"kind": "interval", "lo": lo, "hi": hi}


_QT = {"measurement_similar_hardware": "measured", "engineering_estimate": "model-derived"}


def evidence_items(ris: list, cinfo: dict) -> list:
    items = []
    for ri in ris:
        if ri["id"] not in RI_TO_CRITERION:
            continue
        cid, kind, elements = RI_TO_CRITERION[ri["id"]]
        _need(bool(ri["evidence_levels"]), f"{ri['id']}: an evidence level is required to submit it to lane 24")
        c = cinfo[cid]
        cond: dict[str, Any] = {}
        if elements is not None:
            cond["elements"] = list(elements)
        if cid == "G2.bus_power_max":
            cond["operating_modes"] = ["startup"]
            cond["notes"] = "load-side heater power of other cathodes; not stated at bus_power_boundary_v1"
        if cid == "P2.cathode_life":
            cond["propellants"] = ["xenon"]
            cond["notes"] = "developer model on Xe-fed cathodes"
        items.append({
            "id": "veto." + ri["id"], "architectures": list(ri["architectures"]), "gate": c["gate"],
            "criterion": cid, "metric": c["metric"], "unit": c["unit"], "value": _ri_value(ri, kind),
            "basis": ri["lane24_basis"], "quantity_type": _QT[ri["lane24_basis"]],
            "evidence_level": max(ri["evidence_levels"]),
            "scope": "point_design", "design_id": "reference hardware in the cited source (not a Vyovrinda design)",
            "conditions": cond, "hall_closure": {"status": "none"},
            "source": "; ".join(f"{s['file']} {s['path']}" for s in ri["source_refs"]),
            "uncertainty": ri["why_not_verdict_bearing"], "applicability_domain": ri["statement"],
            "validation_status": "not validated for Vyovrinda hardware (risk indicator of the veto layer)",
            "transformation_chain": "pinned input file -> " + REL_SELF + " (values read, not retyped)",
            "notes": "submitted by the veto layer as a risk indicator; expected NOT verdict-bearing"
                     + ("; " + ri["lane24_basis_note"] if ri.get("lane24_basis_note") else ""),
        })
    return items


def run_lane24(items: list, inputs: dict) -> dict:
    from abep_sim import hard_gates as hg        # lazy import after pin check
    matrix = inputs["docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"]
    bundle = {"schema": hg.EVIDENCE_SCHEMA, "matrix_version": matrix["matrix_version"], "items": items,
              "note": "veto-layer submission: registered verdict-eligible items (none today) plus risk indicators "
                      "that map onto a lane-24 metric"}
    admitted = hg.admitted_member_ids()
    res = hg.evaluate_all(bundle, admitted_members=admitted)
    gates_of_interest = sorted({g for cids in DIMENSION_CRITERIA.values() for g in
                                (criteria_info(matrix)[c]["gate"] for c in cids)})
    summ = {"evaluator": "abep_sim.hard_gates.evaluate_all (lane_24_hard_gates, unmodified)",
            "matrix_version": res["matrix_version"], "matrix_status": res["matrix_status"],
            "admitted_members": res["admitted_members"], "items_submitted": sorted(it["id"] for it in items),
            "eliminated": res["eliminated"], "not_eliminated": res["not_eliminated"], "architectures": {}}
    for a in ARCHITECTURES:
        r = res["architectures"][a]
        summ["architectures"][a] = {
            "eliminated": r["eliminated"],
            "elimination_basis": r["elimination_basis"],
            "proposed_gate_failures": r["proposed_gate_failures"],
            "gate_verdicts": {g: r["gates"][g]["verdict"] for g in gates_of_interest},
            "items_not_verdict_bearing": [{"id": x["id"], "criterion": x["criterion"], "reasons": x["reasons"]}
                                          for x in r["evidence_not_verdict_bearing"]],
        }
    return summ


# ---------------------------------------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------------------------------------
def build(root: str = ROOT, pins: tuple = PINS) -> dict:
    inputs = load_inputs(root, pins)
    matrix = inputs["docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"]
    _need(tuple(matrix["architectures"]) == ARCHITECTURES, "hard-gate matrix architecture ids changed")
    bom = inputs["docs/architecture_comparison/mass_bom/mass_bom_v1.json"]
    _need(tuple(bom["architecture_ids"]) == ARCHITECTURES, "mass BOM architecture ids changed")
    cinfo = criteria_info(matrix)
    ris = risk_indicators(inputs, cinfo)
    hs_status = _hs_repository_status(inputs["docs/evidence/hall_sustainment/hall_sustainment_matrix.json"])
    _need(len(hs_status) > 0, "lane-09 matrix: expected repository_status entries (ECHT-N2) not found")
    ri_by_dim: dict = {}
    for ri in ris:
        for a in ri["architectures"]:
            ri_by_dim.setdefault((a, ri["dimension"]), []).append(ri["id"])

    cells_pre = {}
    submitted = []
    for a in ARCHITECTURES:
        for d in DIMENSIONS:
            b = eligible_bounds(d, a, inputs, cinfo)
            cells_pre[(a, d)] = b
            submitted += [x["evidence_item"] for x in b if x["side"] == "fail" and x["evidence_item"] is not None]
    items = evidence_items(ris, cinfo)
    seen = {it["id"] for it in items}
    for it in submitted:
        if it["id"] not in seen:
            items.append(copy.deepcopy(it))
            seen.add(it["id"])
    lane24 = run_lane24(items, inputs)

    ri_index = {ri["id"]: ri for ri in ris}
    cells = {}
    for a in ARCHITECTURES:
        cells[a] = {}
        for d in DIMENSIONS:
            crit = mapping_for(d, a, cinfo)
            bounds = cells_pre[(a, d)]
            status = classify(bounds)
            fin = final_status(status, a, crit, lane24)
            rids = sorted(ri_by_dim.get((a, d), []))
            cond_m = [{"risk_indicator": r, **ri_index[r]["conditional_margin"]} for r in rids
                      if ri_index[r]["conditional_margin"] is not None]
            miss = missing_inputs(d, a, inputs)
            cells[a][d] = {
                "status": status, "final_status": fin, "criteria": crit,
                "verdict_eligible_bounds": [{k: v for k, v in x.items() if k != "evidence_item"} for x in bounds],
                "margin": ({"kind": "not_computable",
                            "reason": "no verdict-eligible failing-side bound exists for this architecture and "
                                      "dimension"} if not bounds else
                           {"kind": "bounds", "values": [x["value"] for x in bounds]}),
                "conditional_margins": cond_m, "risk_indicators": rids,
                "risk_directions": sorted({ri_index[r]["direction"] for r in rids}),
                "missing_inputs": miss,
                "common_mode_missing": sum(1 for m in miss if m["scope"] == "common_mode"),
                "architecture_specific_missing": sum(1 for m in miss if m["scope"] == "architecture_specific"),
            }

    veto_candidates = [{"architecture": a, "dimension": d} for a in ARCHITECTURES for d in DIMENSIONS
                       if cells[a][d]["status"] == "VETO_CANDIDATE"]
    eliminated = [{"architecture": a, "dimension": d} for a in ARCHITECTURES for d in DIMENSIONS
                  if cells[a][d]["final_status"] == FINAL_ONLY]
    common = sorted(ri["id"] for ri in ris if ri["scope"] == "common_mode")
    specific = {a: sorted(ri["id"] for ri in ris if ri["scope"] == "architecture_specific" and a in ri["architectures"])
                for a in ARCHITECTURES}
    status_counts = {s: sum(1 for a in ARCHITECTURES for d in DIMENSIONS if cells[a][d]["status"] == s)
                     for s in STATUSES}

    wall_flux_gate = wall_flux_gate_status(inputs)

    return {
        "schema": SCHEMA_ID, "id": "veto_layer_v1", "follow_on": "fo_veto_layer", "trigger": "T_VETO_LAYER",
        "status": "DRAFT_FOR_OWNER_REVIEW", "created": CREATED, "base_commit": BASE_COMMIT,
        "generated_by": f"python {REL_SELF}",
        "question": "Can mass, thermal rejection, life (firing and mission) or start-up veto hall_only, rf_hall or "
                    "ecr_hall against the RFP envelope as recorded (< 40 kg, < 1.5 kW, > 15,000 h firing, 26,000 h "
                    "mission), and on what evidence?",
        "answer": (f"No veto today. {status_counts['UNDETERMINED']} of {len(ARCHITECTURES) * len(DIMENSIONS)} "
                   f"architecture x dimension cells are UNDETERMINED, {status_counts['NO_VETO_WITHIN_EVIDENCE']} are "
                   f"NO_VETO_WITHIN_EVIDENCE and {status_counts['VETO_CANDIDATE']} are VETO_CANDIDATE: no "
                   "verdict-eligible failing-side bound (hard physical bound, Vyovrinda or same-hardware measurement, "
                   "validated closure-independent model) exists for any of them. The lane-24 evaluator eliminated "
                   f"{lane24['eliminated'] or 'nothing'}. Risk indicators exist, mostly common-mode: cathode Xe mass "
                   "straddles the 40 kg limit across reference flows, and air-fed Hall channel / anode life on "
                   "similar hardware points below 15,000 h; neither is verdict-bearing. This is missing evidence, "
                   "not a finding that any architecture fits the envelope. No winner, no ranking."),
        "architectures": list(ARCHITECTURES), "dimensions": list(DIMENSIONS),
        "status_definitions": {
            "VETO_CANDIDATE": "a failing-side bound exists whose basis the lane-24 matrix lists in "
                              "fail_sufficient_bases for the mapped criterion, and it lies on the failing side; it is "
                              "submitted to abep_sim.hard_gates.evaluate_all",
            "NO_VETO_WITHIN_EVIDENCE": "at least one verdict-eligible failing-side bound exists and none lies on the "
                                       "failing side; NOT a PASS (missing contributors stay listed)",
            "UNDETERMINED": "no verdict-eligible failing-side bound exists; missing inputs are named with the lanes / "
                            "decisions that unblock them",
            FINAL_ONLY: "reported only when the lane-24 evaluator returns a binding-gate FAIL for the architecture on "
                        "the mapped gate",
        },
        "status_counts": status_counts,
        "rfp_limits_as_recorded": {cid: {"threshold": cinfo[cid]["threshold"], "comparator": cinfo[cid]["comparator"],
                                         "unit": cinfo[cid]["unit"], "gate_status": cinfo[cid]["gate_status"],
                                         "threshold_source": cinfo[cid]["threshold_source"]}
                                   for cid in sorted({c for v in DIMENSION_CRITERIA.values() for c in v})},
        "inputs": [{"path": rel, "sha256": sha, "lane": lane[0], "lane_commit": lane[1], "role": role}
                   for rel, sha, lane, role in pins],
        "pin_provenance_notes": PIN_PROVENANCE_NOTES,
        "external_blockers": external_blockers(inputs),
        "cells": cells,
        "risk_indicators": ris,
        "common_mode_vs_architecture_specific": {
            "common_mode_risk_indicators": common,
            "architecture_specific_risk_indicators": specific,
            "reading": "A common-mode veto, once demonstrated, would remove all three architectures together: it is a "
                       "programme risk, not a discriminator. The indicators pointing toward exceedance today "
                       "(Hall channel erosion and anode oxidation on O-bearing air, cathode exposure to air, "
                       "channel scale-up of wall flux) sit on the common Hall accelerator and cathode; cathode Xe "
                       "mass straddles the limit and is common-mode unless m_c,min(I_emit) differs between arms. "
                       "Architecture-specific items (rf_source passive cooling, microwave-line heating, pre-ionizer "
                       "hardware mass, dielectric/window life) have no quantitative bound in any pinned input.",
        },
        "lane24_evaluation": lane24,
        "veto_candidates": veto_candidates,
        "eliminated_within_tested_envelope": eliminated,
        "not_used": [
            {"what": "abep_sim/thermal.py Node/ThermalParams defaults (emissivity, areal density, conductances)",
             "why": "uncited dataclass defaults (legacy Phase 4); not evidence"},
            {"what": "abep_sim/mass_bom.py legacy MGA dict and v1.7 sizing functions; earlier repository mass figures "
                     "(withdrawn; not quoted)", "why": "uncited / superseded 0-D Hall closure (MASS_BOM.md, OD-M3)"},
            {"what": "any Hall-closure output (screening candidates sgb-screen-*, withdrawn 0-D closure)",
             "why": "credible set empty (gate 3 FAIL); never a performance, heat or life source"},
            {"what": "lane-09 entries with a repository_status ("
                     + ", ".join(f"{k}: {v['status']}" for k, v in sorted(hs_status.items()))
                     + "; ECHT on pure N2)",
             "why": "not cited by this layer: they are sustainment / operating-window observations, not mass, heat "
                    "rejection, life or start-up evidence. Their status (" + ", ".join(sorted({v["status"] for v in
                    hs_status.values()})) + ", " + ", ".join(sorted({v["status_file"] for v in hs_status.values()}))
                    + ") keeps them non-score-bearing and never a transport discriminator; quoting the published "
                    "sustainment as a level-3 literature measurement stays allowed. Any citing source_ref would carry "
                    "the status (build check)."},
            {"what": "Hall wall ion flux / energy (thermal_life hall_discharge.wall_ion_flux_m2s, wall_ion_energy_eV)",
             "why": wall_flux_gate["statement"]},
            {"what": "compressor bus draw and valve-outlet feed state",
             "why": "the upstream ICD (lane_33) offers only a repository compressor model (evidence class "
                    "model-derived, uncertainty TBD) and lane_20 keeps the compressor load TBD; the lane_16 "
                    "valve-outlet feed state is TBD; neither is filled here"},
        ],
        "milestones": {
            "supports": ["A"],
            "A": "Supported as a negative result with named conditions: no architecture is vetoed on mass, thermal, "
                 "life or start-up, so a conditional selection is not blocked by this layer; each UNDETERMINED cell's "
                 "missing inputs are the conditions that selection must carry (e.g. 'Hall channel and anode life "
                 "> 15,000 h on O-bearing feed, demonstrated'; 'cathode spot-mode minimum Xe flow x firing hours "
                 "within the Xe allocation').",
            "B_needs": "verdict-eligible bounds: sourced per-item mass lower bounds and CBEs (mass BOM), thermal_life "
                       "inputs and TBD limit records filled from design / datasheets, wall-erosion evidence on N/O "
                       "(lane_32) and wall_life_trustworthy maps from an ADMITTED closure, measured cathode minimum "
                       "flow and insert life inputs, the upstream ICD (lane_33) and feed envelope (lane_16) values.",
            "C_needs": "an integrated design whose mass roll-up, heat rejection, life and start-up sequence close "
                       "together at bus_power_boundary_v1, with hardware endurance evidence for the Hall channel, "
                       "anode and cathode on O-bearing feed.",
        },
        "proposed_for_owner": [
            {"id": "VL-P1", "item": "status rule: only bases in the lane-24 fail_sufficient_bases make a "
                                    "VETO_CANDIDATE; literature on similar hardware stays a risk indicator",
             "status": "PROPOSED"},
            {"id": "VL-P2", "item": "start-up peak limit 1500 W (cathode_integration startup_peak_limit, PROPOSED); "
                                    "under matrix v1 a start-up-only bound cannot FAIL G2 (fail_must_cover = steady)",
             "status": "PROPOSED"},
            {"id": "VL-P3", "item": "booking the Hall anode under the G4 element 'hall_discharge_channel'",
             "status": "PROPOSED"},
            {"id": "VL-P4", "item": "thermal vetoes map onto P1 (PROPOSED gate): even a demonstrated thermal FAIL "
                                    "eliminates nothing until the owner adopts P1", "status": "PROPOSED"},
        ],
        "open_questions_for_owner": [
            "Adopt P1 (thermal) and P2 (cathode life / start cycles) as binding, or keep them reporting-only?",
            "Does '< 1.5 kW' bound start-up transients (startup_peak_limit), and should G2 fail_must_cover include "
            "'startup'?",
            "Xe allocation (OD-M4) and whether cathode flow continues between firings (x 26,000/15,000).",
        ],
        "note": "DRAFT for owner review. No winner, no ranking; eliminations only through the lane-24 evaluator. "
                "Thresholds not in the RFP are PROPOSED.",
    }


# ---------------------------------------------------------------------------------------------------------------------
# Rendering and I/O
# ---------------------------------------------------------------------------------------------------------------------
def dump(obj: Any) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def validate(doc: dict, root: str = ROOT) -> None:
    from abep_sim import hard_gates as hg        # re-use lane-24's dependency-free JSON-schema subset validator
    with open(os.path.join(root, "docs", "architecture_comparison", "veto_layer", "veto_layer_v1.schema.json"),
              encoding="utf-8") as f:
        schema = json.load(f)
    hg.check_schema_keywords(schema)
    errs = hg.schema_errors(doc, schema)
    if errs:
        raise ValueError("veto layer JSON does not validate:\n  " + "\n  ".join(errs[:40]))


def _fmt(v: Any) -> str:
    if v is None:
        return "open"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


def render_md(doc: dict) -> str:
    L = []
    w = L.append
    w("# Mass / thermal / life / start-up veto layer v1 (fo_veto_layer)")
    w("")
    w(f"Generated by `{doc['generated_by']}` from [`veto_layer_v1.json`](veto_layer_v1.json) "
      "(schema [`veto_layer_v1.schema.json`](veto_layer_v1.schema.json)). Do not edit by hand; "
      "`--check` reproduces both files byte for byte.")
    w("")
    w(f"**Status:** {doc['status']} ({doc['created']}, base `{doc['base_commit'][:7]}`). "
      f"**Milestone support:** {', '.join(doc['milestones']['supports'])}. Trigger `{doc['trigger']}`.")
    w("")
    w("## Question and answer")
    w("")
    w(doc["question"])
    w("")
    w(f"**Answer.** {doc['answer']}")
    w("")
    w("## Status per architecture and dimension")
    w("")
    w("| architecture | " + " | ".join(doc["dimensions"]) + " |")
    w("|---|" + "---|" * len(doc["dimensions"]))
    for a in doc["architectures"]:
        w(f"| `{a}` | " + " | ".join(doc["cells"][a][d]["final_status"] for d in doc["dimensions"]) + " |")
    w("")
    w("Status rules:")
    for k, v in doc["status_definitions"].items():
        w(f"- `{k}`: {v}.")
    w("")
    w("## Mapping onto the lane-24 hard gates")
    w("")
    w("| dimension | criterion | gate status | requirement | can eliminate on this dimension | notes |")
    w("|---|---|---|---|---|---|")
    for d in doc["dimensions"]:
        for c in doc["cells"]["hall_only"][d]["criteria"]:
            req = f"{c['metric']} {c['comparator']} {_fmt(c['threshold']) if c['threshold'] is not None else 'TBD'} " \
                  f"{c['unit']}"
            w(f"| {d} | {c['criterion']} | {c['gate_status']} | {req} | "
              f"{'yes' if c['can_eliminate_on_this_dimension'] else 'no'} | {'; '.join(c['notes']) or '-'} |")
    w("")
    w("## Risk indicators (never verdict-bearing)")
    w("")
    w("Numbers are read from the pinned inputs; conditional margins hold only under the indicator's premise.")
    w("")
    w("| id | dimension | scope | architectures | direction | conditional margin | evidence class (levels) | "
      "lane-24 basis |")
    w("|---|---|---|---|---|---|---|---|")
    for ri in doc["risk_indicators"]:
        cm = ri["conditional_margin"]
        cms = "-" if cm is None else f"{cm['quantity']}: {_fmt(cm['range'])} {cm['unit']}"
        w(f"| {ri['id']} | {ri['dimension']} | {ri['scope']} | {', '.join(ri['architectures'])} | {ri['direction']} | "
          f"{cms} | {ri['evidence_class']} ({_fmt(ri['evidence_levels']) if ri['evidence_levels'] else 'n/s'}) | "
          f"{ri['lane24_basis'] or '-'} |")
    w("")
    for ri in doc["risk_indicators"]:
        w(f"- **{ri['id']}** ({ri['element']}). {ri['statement']} *Not verdict-bearing:* "
          f"{ri['why_not_verdict_bearing']}. "
          + (f"*Lane-24 basis label:* {ri['lane24_basis_note']} " if ri.get("lane24_basis_note") else "")
          + f"*To become verdict-bearing:* {ri['to_become_verdict_bearing']}. "
          f"*Architecture modulation:* {ri['architecture_modulation']}. Sources: "
          + "; ".join(f"`{s['file']}` {s['path']}"
                      + (f" (repository_status {s['repository_status']})" if s.get("repository_status") else "")
                      for s in ri["source_refs"]) + ".")
    w("")
    w("## Common-mode vs architecture-specific")
    w("")
    cm = doc["common_mode_vs_architecture_specific"]
    w(f"- Common-mode (all three): {', '.join(cm['common_mode_risk_indicators'])}.")
    for a, ids in cm["architecture_specific_risk_indicators"].items():
        w(f"- `{a}`-specific: {', '.join(ids) if ids else 'none'}.")
    w("")
    w(cm["reading"])
    w("")
    w("## Lane-24 evaluator run")
    w("")
    ev = doc["lane24_evaluation"]
    w(f"`{ev['evaluator']}`, matrix {ev['matrix_version']} ({ev['matrix_status']}), admitted members: "
      f"{ev['admitted_members'] or 'none (credible set empty)'}. Items submitted: "
      f"{', '.join(ev['items_submitted']) or 'none'}. Eliminated: {ev['eliminated'] or 'none'}.")
    w("")
    w("| architecture | eliminated | " + " | ".join(sorted(ev["architectures"]["hall_only"]["gate_verdicts"])) + " |")
    w("|---|---|" + "---|" * len(ev["architectures"]["hall_only"]["gate_verdicts"]))
    for a in doc["architectures"]:
        r = ev["architectures"][a]
        w(f"| `{a}` | {r['eliminated']} | " + " | ".join(r["gate_verdicts"][g] for g in sorted(r["gate_verdicts"]))
          + " |")
    w("")
    w("Why each submitted item is not verdict-bearing (evaluator reasons, `hall_only`):")
    w("")
    for x in ev["architectures"]["hall_only"]["items_not_verdict_bearing"]:
        w(f"- `{x['id']}` ({x['criterion']}): " + "; ".join(x["reasons"]))
    w("")
    w("## Missing inputs (what blocks each cell)")
    w("")
    for a in doc["architectures"]:
        w(f"### `{a}`")
        w("")
        w("| dimension | missing input | blocking | scope |")
        w("|---|---|---|---|")
        for d in doc["dimensions"]:
            for m in doc["cells"][a][d]["missing_inputs"]:
                w(f"| {d} | {m['input']} | {', '.join(m['blocking'])} | {m['scope']} |")
        w("")
    w("Blocking lanes named above (verification status as recorded at the base commit; what was read and why it "
      "decides no cell):")
    w("")
    for k, v in doc["external_blockers"].items():
        w(f"- `{k}` (`{v['path']}`, {'in' if v['in_base_commit'] else 'NOT in'} the base commit"
          + (f", lane commit `{v['lane_commit'][:10]}`" if v["lane_commit"] else "")
          + f"; {v['verification']}): {v['note']}"
          + ("" if not v["read"] else " Read: " + "; ".join(f"`{r['file']}` {r['path']} = {r['value']!r}"
                                                             for r in v["read"]) + "."))
    w("")
    w("## Milestones")
    w("")
    w(f"- **A (supported):** {doc['milestones']['A']}")
    w(f"- **B needs:** {doc['milestones']['B_needs']}")
    w(f"- **C needs:** {doc['milestones']['C_needs']}")
    w("")
    w("## PROPOSED for the owner")
    w("")
    for p in doc["proposed_for_owner"]:
        w(f"- {p['id']} ({p['status']}): {p['item']}")
    w("")
    w("Open questions:")
    for q in doc["open_questions_for_owner"]:
        w(f"- {q}")
    w("")
    w("## Not used")
    w("")
    for n in doc["not_used"]:
        w(f"- {n['what']}: {n['why']}")
    w("")
    w("## Inputs (sha256-pinned)")
    w("")
    w("| file | lane | lane commit | sha256 |")
    w("|---|---|---|---|")
    for i in doc["inputs"]:
        w(f"| `{i['path']}` | {i['lane']} | `{i['lane_commit'][:10]}` | `{i['sha256'][:16]}…` |")
    w("")
    w("Pin provenance notes:")
    w("")
    for n in doc["pin_provenance_notes"]:
        w(f"- `{n['lane']}` @ `{n['lane_commit'][:10]}`: {n['note']}")
    w("")
    w(f"_{doc['note']}_")
    return "\n".join(L) + "\n"


def outputs(root: str = ROOT, pins: tuple = PINS) -> dict:
    doc = build(root, pins)
    validate(doc, root)
    return {OUT_JSON: dump(doc), OUT_MD: render_md(doc)}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify the committed files reproduce byte for byte")
    a = ap.parse_args(argv)
    outs = outputs()
    if a.check:
        bad = []
        for p, text in outs.items():
            if not os.path.isfile(p):
                bad.append(f"{os.path.relpath(p, ROOT)} missing")
                continue
            with open(p, encoding="utf-8") as f:
                if f.read() != text:
                    bad.append(f"{os.path.relpath(p, ROOT)} differs from a fresh build")
        if bad:
            print("CHECK FAILED:\n  " + "\n  ".join(bad))
            return 1
        print("OK: veto layer reproduces byte for byte")
        return 0
    for p, text in outs.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
