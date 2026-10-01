#!/usr/bin/env python3
"""A9.7 F9 - architecture freeze candidate (lane fo_a9_7_f9_freeze_candidate).

ONE candidate definition of the A9 architecture under investigation (atmospheric path intake -> filter -> compressor
-> plenum / feed -> H-1 Hall -> downstream 13.56 MHz ICP neutralizer; C1 control / fallback) with three sections:
UPSTREAM (intake, filter, compressor, plenum, valves / feed), PROPULSION (H-1 geometry, magnetic circuit, anode
approach, downstream ICP geometry, RF / match architecture, collector) and SYSTEM (PPU topology, power budget, mass
budget, thermal interfaces, control / start sequence, Xe functionality). Every parameter carries
VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE (path + JSON pointer / locator + sha256) | FREEZE_STATUS.

Where an A9.7 lane returns a Pareto set (F1 / F3 / F4 / F7 / F8) the candidate carries the set (robust set from F8
plus the nominal-context Pareto union of F7); no representative point is selected: the selection rule is itself an
owner question (F9-OQ-01). The architecture status is computed from the architecture-level gates and stays
INVESTIGATION_HYPOTHESIS while any gate lacks sufficient evidence (A9.7 F9 freeze rule).

Inputs are read-only. Immutable inputs (owner decisions) are PINNED by sha256: the builder refuses to run when one
changed. Every other input (A9.7 lane outputs, A9 / A9.6 deliverables, production modules cited for model-change
candidates) is CONSUMED: its sha256 at build time is recorded and `--check` reports drift.

What this is not: not a frozen architecture, not a design release, not a selection, no winner, no PASS, no Hall
performance number (the credible Hall set is empty; P5-N2 v1 is INCONCLUSIVE), not wired into abep_sim/archengine.py,
no existing module, frozen dataset or decision is modified, no owner question is answered.

Usage:
    python docs/architecture/freeze_candidate/build_freeze_candidate.py          # write JSON + MD
    python docs/architecture/freeze_candidate/build_freeze_candidate.py --check  # verify both files are current
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LANE_DIR = REPO / "docs" / "architecture" / "freeze_candidate"
JSON_PATH = LANE_DIR / "architecture_freeze_candidate_v1.json"
MD_PATH = LANE_DIR / "ARCHITECTURE_FREEZE_CANDIDATE.md"
REL_SELF = "docs/architecture/freeze_candidate/build_freeze_candidate.py"
REL_TEST = "tests/test_architecture_freeze_candidate.py"
BASE_COMMIT = "7800fe93e53898af1750f1394fdeb07b04e21c57"
DATE = "2026-10-01"
LANE = "fo_a9_7_f9_freeze_candidate"

# --------------------------------------------------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------------------------------------------------
# Immutable inputs (owner decisions are immutable after commit): a mismatch stops the build (fail closed).
PINS = {
    "A97_MD": ("docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md",
               "fb51328d6fe07a6eaf257ef9ef9592cb0c0039ae3e8cf04ef0420007c985b129"),
    "A97": ("docs/decisions/OD_2026_10_01_A9_7_architecture_freeze_design_synthesis.json",
            "3199a670c901967ae4dca930022470b024cac14b263335da0adc3d423c37f372"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03"),
    "A92_MD": ("docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md",
               "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"),
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"),
}
# Mutable / revisable inputs: read-only, sha256 recorded at build time (drift is reported by --check).
CONSUMED = {
    # A9.7 lanes (all merged in the base of this lane)
    "F0": "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json",
    "RUST": "docs/performance/abep_core/parity_report_v1.json",
    "F1": "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json",
    "F2": "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json",
    "F3": "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
    "F3D": "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json",
    "F4": "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json",
    "F5": "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
    "F6": "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json",
    "F78": "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json",
    "F7P": "docs/design_synthesis/f7_f8_optimizer/f7_upstream_pareto_v1.json",
    "F8R": "docs/design_synthesis/f7_f8_optimizer/f8_robust_candidates_v1.json",
    # A9 / A9.x deliverables
    "OQ4": "docs/budgets/owner_decisions/owner_questions_state_v4.json",
    "RVM": "docs/requirements/rvm_a9/rvm_a9_v1.json",
    "MP2": "docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json",
    "M16": "docs/experiments/hall_icp/integration/m16_v4/subsystem_maturity_v4.json",
    "XE2": "docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json",
    "BUS": "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json",
    "ICD": "schemas/interfaces/icp_neutralizer_icd_v1.json",
    "P1": "docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json",
    "P2": "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json",
    "P3": "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v1.json",
    "P4": "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
    "ENS": "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
    "VAL": "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
    "UICD": "docs/interfaces/UPSTREAM_ICD.md",
    # production modules cited by the model-change candidates (read as text, never imported or modified)
    "MOD_TPMC": "abep_sim/intake_tpmc.py",
    "MOD_INTAKE": "abep_sim/intake.py",
    "MOD_COMP": "abep_sim/compressor.py",
    "MOD_RES": "abep_sim/reservoir.py",
}

FREEZE_STATUSES = {
    "FREEZE_CANDIDATE": "owner-given decision, convention, rule or allocation that can enter the architecture reference "
                        "as stated; a candidate, never a frozen value (nothing is frozen by this lane)",
    "OPEN": "a value, window, set or Pareto set exists (derived / analog / parametric / allocation) but it is not yet a "
            "design value; the listed evidence moves it toward FREEZE_CANDIDATE",
    "TBD_AFTER_EVIDENCE": "no admissible value; it needs measurement, analysis or sourced data",
    "TBD_OWNER": "needs an owner decision (the existing or new owner question is cited)",
}
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "requirement-as-recorded")
VALUE_LABELS = {
    "PARETO_SET": "the value is a Pareto set (or a set of Pareto members' values); no member is selected",
    "PARAMETRIC_SENSITIVITY": "computed from uncited code-default coefficients and / or parametric cases (A9.7 F3 / "
                              "F4 / F7 / F8 label); never a design value, a CBE or a requirement",
    "ALLOCATION": "owner allocation (budget), not a CBE and not a measured value",
    "REQUIREMENT_AS_RECORDED": "RFP value as recorded from secondary sources (official RFP not in the repository; "
                               "RVM requirement_frozen = false)",
    "WINDOW": "admissible window or analog envelope, not a design point",
    "RULE": "decision, convention or interface rule",
}
SECTIONS = {
    "UPSTREAM": {"intake": "intake area and geometry", "filter": "filter", "compressor": "compressor topology and "
                 "dimensions", "plenum": "plenum", "valves_feed": "valves / feed"},
    "PROPULSION": {"h1_geometry": "H-1 geometry", "magnetic_circuit": "magnetic circuit", "anode": "anode approach",
                   "icp_geometry": "downstream ICP geometry", "rf_match": "RF / match architecture",
                   "collector": "collector"},
    "SYSTEM": {"ppu": "PPU topology", "power_budget": "power budget", "mass_budget": "mass budget",
               "thermal_interfaces": "thermal interfaces", "control_start": "control / start sequence",
               "xe": "Xe functionality"},
}
# A9.7 F9 bullets (verbatim from the pinned directive) -> subsections
A97_F9_BULLETS = {
    "intake area and geometry;": ("UPSTREAM", "intake"), "filter;": ("UPSTREAM", "filter"),
    "compressor topology and dimensions;": ("UPSTREAM", "compressor"), "plenum;": ("UPSTREAM", "plenum"),
    "valves/feed.": ("UPSTREAM", "valves_feed"), "H-1 geometry;": ("PROPULSION", "h1_geometry"),
    "magnetic circuit;": ("PROPULSION", "magnetic_circuit"), "anode approach;": ("PROPULSION", "anode"),
    "downstream ICP geometry;": ("PROPULSION", "icp_geometry"), "RF/match architecture;": ("PROPULSION", "rf_match"),
    "collector.": ("PROPULSION", "collector"), "PPU topology;": ("SYSTEM", "ppu"),
    "power budget;": ("SYSTEM", "power_budget"), "mass budget;": ("SYSTEM", "mass_budget"),
    "thermal interfaces;": ("SYSTEM", "thermal_interfaces"), "control/start sequence;": ("SYSTEM", "control_start"),
    "Xe functionality.": ("SYSTEM", "xe"),
}
CONFIGURATION = "hall_icp_neutralizer"
FALLBACK_CONFIGURATION = "hall_c1_reference"

_cache: dict = {}
_sha: dict = {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_of(key: str) -> str:
    return PINS[key][0] if key in PINS else CONSUMED[key]


def verify_pins() -> dict:
    out = {}
    for key, (rel, want) in PINS.items():
        p = REPO / rel
        if not p.is_file():
            raise SystemExit(f"REFUSED: pinned input missing: {rel}")
        got = _sha256(p)
        if got != want:
            raise SystemExit(f"REFUSED: pinned input changed: {rel} sha256 {got} != pinned {want}")
        out[key] = {"path": rel, "sha256": want}
    return out


def sha_of(key: str) -> str:
    if key not in _sha:
        p = REPO / path_of(key)
        if not p.is_file():
            raise SystemExit(f"REFUSED: input missing: {path_of(key)}")
        _sha[key] = _sha256(p)
    return _sha[key]


def load(key: str):
    if key not in _cache:
        p = REPO / path_of(key)
        if not p.is_file():
            raise SystemExit(f"REFUSED: input missing: {path_of(key)}")
        _cache[key] = json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else p.read_text(
            encoding="utf-8")
    return _cache[key]


def resolve(doc, pointer: str):
    cur = doc
    if pointer in ("", "/"):
        return cur
    for tok in pointer.lstrip("/").split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(tok)]
        elif isinstance(cur, dict):
            if tok not in cur:
                raise KeyError(f"pointer {pointer}: missing {tok!r}")
            cur = cur[tok]
        else:
            raise KeyError(f"pointer {pointer}: cannot descend into {type(cur).__name__}")
    return cur


def get(key: str, pointer: str):
    return resolve(load(key), pointer)


def ref(key: str, pointer: str = "", note: str | None = None) -> dict:
    """JSON source reference; the pointer must resolve (fail closed)."""
    if pointer:
        resolve(load(key), pointer)
    r = {"path": path_of(key), "pointer": pointer or "/", "sha256": sha_of(key)}
    if key in PINS:
        r["pinned"] = True
    if note:
        r["note"] = note
    return r


def tref(key: str, needle: str, note: str | None = None) -> dict:
    """Text source reference (Markdown / Python); the quoted locator must occur in the file (fail closed)."""
    if needle not in load(key):
        raise SystemExit(f"REFUSED: locator not found in {path_of(key)}: {needle!r}")
    r = {"path": path_of(key), "locator": needle, "sha256": sha_of(key)}
    if key in PINS:
        r["pinned"] = True
    if note:
        r["note"] = note
    return r


def find(key: str, list_pointer: str, field: str, value) -> str:
    lst = get(key, list_pointer)
    hits = [i for i, x in enumerate(lst) if isinstance(x, dict) and x.get(field) == value]
    if len(hits) != 1:
        raise SystemExit(f"REFUSED: {path_of(key)}{list_pointer}: {field}={value!r} found {len(hits)} times")
    return f"{list_pointer}/{hits[0]}"


def find_text(key: str, list_pointer: str, needle: str) -> str:
    lst = get(key, list_pointer)
    hits = [i for i, x in enumerate(lst) if needle in json.dumps(x, ensure_ascii=False)]
    if len(hits) != 1:
        raise SystemExit(f"REFUSED: {path_of(key)}{list_pointer}: {needle!r} found {len(hits)} times")
    return f"{list_pointer}/{hits[0]}"


def cite(key: str, pointer: str, *tokens: str) -> dict:
    """Reference whose resolved text must contain every quoted token (numbers copied from prose fail closed)."""
    txt = json.dumps(get(key, pointer), ensure_ascii=False)
    for t in tokens:
        if t not in txt:
            raise SystemExit(f"REFUSED: {path_of(key)}{pointer} no longer states {t!r}")
    return ref(key, pointer)


def ans(row: int) -> dict:
    return ref("ANS", find("ANS", "/answers", "row", row) + "/owner_answer_verbatim", note=f"owner row {row}")


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


def is_tbd(v) -> bool:
    return isinstance(v, str) and v.startswith("TBD")


# --------------------------------------------------------------------------------------------------------------------
# parameter rows
# --------------------------------------------------------------------------------------------------------------------
def P(rows: list, pid: str, section: str, sub: str, name: str, value, *, units: str, tolerance, ec, sources: list,
      basis: str, fs: str, adv: list | None = None, label: str | None = None, ec_note: str | None = None,
      note: str | None = None, origin: dict | None = None) -> None:
    assert section in SECTIONS and sub in SECTIONS[section], (pid, section, sub)
    assert fs in FREEZE_STATUSES, (pid, fs)
    assert sources, pid
    assert label is None or label in VALUE_LABELS, (pid, label)
    if is_tbd(value):
        assert ec is None, f"{pid}: a TBD value carries no evidence class"
        assert fs != "FREEZE_CANDIDATE", pid
    else:
        assert ec in EVIDENCE_CLASSES, (pid, ec)
    if label in ("PARAMETRIC_SENSITIVITY", "PARETO_SET"):
        assert fs != "FREEZE_CANDIDATE", f"{pid}: a parametric / Pareto value is never a freeze candidate"
    if fs != "FREEZE_CANDIDATE":
        assert adv, f"{pid}: evidence needed to advance must be listed"
    row = {"id": pid, "section": section, "subsection": sub, "name": name, "value": value, "units": units,
           "tolerance": tolerance, "evidence_class": ec}
    if ec_note:
        row["evidence_note"] = ec_note
    if label:
        row["value_label"] = label
    row.update({"source": sources, "basis": basis, "freeze_status": fs, "evidence_to_advance": adv or []})
    if origin:
        row["origin"] = origin
    if note:
        row["note"] = note
    rows.append(row)


T_SET = "n/a (Pareto set; no member selected)"
T_RULE = "n/a (decision / rule)"
T_ALLOC = "n/a (allocation, not a CBE)"
T_PARAM = "n/a (parametric-sensitivity range; no design tolerance exists)"
REP_RULE = "owner rule for a named representative of the Pareto set or for carrying the set to LOCK-1 (F9-OQ-01)"
T12 = "compressor_downselect tests T-1 (turbo ln K0 per row) and T-2 (turbo pumping-speed coefficient) on the " \
      "built rotor (F3 MODE_STRICT blockers C-turbo_kK / C-turbo_kS; F8-05: the delivered flow is most sensitive " \
      "to them)"
ACCOM = "measured gas-surface accommodation of the intake surface state (DI-1.3; F1Q-04 frozen surface v2) " \
        "narrowing the 10 TBD surface scenarios"
FLOWREQ = "owner-defined delivered-flow requirement at the H-1 inlet for the gate UG-FLOW (F9-OQ-02)"
HALL_MAP = "an ADMITTED Hall transport member and a design-specific H-1 map, or measured H-1 performance on the " \
           "delivered feed (hardware pivot Phase 1-3)"


def _parse_design_id(did: str) -> dict:
    cand, filt, comp, v, p = did.split("|")
    m = re.fullmatch(r"A([\d.]+)_Ld([\d.]+)_phi([\d.]+)", cand)
    assert m and v.startswith("V") and p.startswith("P"), did
    return {"design_id": did, "intake": cand, "area_m2": float(m[1]), "L_over_d": float(m[2]), "phi": float(m[3]),
            "filter": filt, "compressor": comp, "V_m3": float(v[1:]), "P_set_Pa": float(p[1:])}


def upstream_sets() -> dict:
    """Robust Pareto set (F8) and the nominal-context Pareto union (F7), recomputed from the F7 / F8 outputs."""
    robust = get("F78", "/robust/robust_pareto_by_P_set")
    members = []
    for pkey, block in robust.items():
        for m in block["members"]:
            d = _parse_design_id(m["design_id"])
            d.update({k: m[k] for k in m if k != "design_id"})
            members.append(d)
    members.sort(key=lambda d: d["design_id"])
    nominal = set()
    rows_by = {}
    cols = get("F7P", "/columns")
    for c in get("F7P", "/contexts"):
        if c["filter"] != "F4-FIL-NONE" or c["wall"] != "WALL-G0":
            continue
        for r in c["rows"]:
            did = f"{r[0]}|{c['filter']}|{r[1]}|V{r[2]:g}|P{c['P_set_Pa']:g}"
            nominal.add(did)
            rows_by.setdefault(did, []).append(dict(zip(cols, r)))
    survivors = {r["design_id"] for r in get("F8R", "/rows")}
    assert survivors == nominal, "F8 survivors must equal the F7 nominal-context Pareto union"
    parsed = [_parse_design_id(d) for d in sorted(nominal)]
    union = {k: sorted({p[k] for p in parsed}) for k in ("area_m2", "L_over_d", "phi", "compressor", "V_m3",
                                                         "P_set_Pa")}
    # per robust member: the F7 per-context extremes of the attributes the F8 table does not carry
    extra = {}
    for m in members:
        rs = rows_by[m["design_id"]]
        extra[m["design_id"]] = {
            "T_comp_max_K": [min(r["T_comp_max_K"] for r in rs), max(r["T_comp_max_K"] for r in rs)],
            "xO_flow": [min(r["xO_flow_min"] for r in rs), max(r["xO_flow_max"] for r in rs)],
            "kn_upper_min": min(r["kn_upper_min"] for r in rs),
        }
    grid = {g["id"]: g for g in get("F3D", "/design_grid")}
    comps = sorted({m["compressor"] for m in members})
    return {"members": members, "n_robust": len(members), "n_nominal_union": len(nominal), "union": union,
            "extra": extra, "compressors": {c: grid[c] for c in comps},
            "n_all_scenario_feasible": {k: v["n_all_scenario_feasible"] for k, v in robust.items()},
            "union_compressors_all_turbo_only": all(grid[c]["N_drag"] == 0 for c in union["compressor"])}


def _hc09_note() -> str:
    cs = [c for c in get("F78", "/system_evaluation/constraint_status_counts") if c[1] == "HC-09"]
    assert cs and all(c[2] == "MET_ON_SUPPLIED_VALUES" for c in cs), "HC-09 status changed in F7"
    return "HC-09 MET_ON_SUPPLIED_VALUES in " + ", ".join(f"{c[0]}: {c[3]}" for c in cs) + " evaluations (F7)"


def _rng(vals) -> list:
    return [sig(min(vals)), sig(max(vals))]


def build_upstream(rows: list, us: dict) -> None:
    S = "UPSTREAM"
    mem = us["members"]
    rob = ref("F78", "/robust/robust_pareto_by_P_set")
    uni = ref("F7P", "/contexts", note="nominal context (filter F4-FIL-NONE, wall WALL-G0) Pareto union over the 10 "
                                       "surface scenarios and every set pressure; equals the F8 survivor set")
    f8_01 = ref("F78", find("F78", "/findings", "id", "F8-01") + "/finding")

    def pset(key):
        return {"kind": "PARETO_SET", "robust_set_values": sorted({m[key] for m in mem}),
                "nominal_pareto_union_values": us["union"][key]}

    # ------------------------------------------------ intake
    P(rows, "AFC-UP-IN-01", S, "intake", "intake frontal (ram) area A", pset("area_m2"), units="m^2",
      tolerance=T_SET, ec="model-derived", label="PARETO_SET",
      ec_note="Pareto membership computed by F7 / F8 from TPMC intake records and parametric compressor / filter / "
              "plenum inputs",
      sources=[rob, uni, f8_01, ref("F1", "/design_space/variables/area_m2")],
      basis="robust set = F8 members feasible in all 10 TBD surface scenarios and non-dominated on worst-case "
            "objectives (P_set 0.01 Pa); union = every F7 nominal-context Pareto member",
      fs="OPEN", adv=[REP_RULE, ACCOM, FLOWREQ, T12, "owner decisions DI-1.1 / DI-1.2 (M16 v4 row 1 blocking item)"])
    P(rows, "AFC-UP-IN-02", S, "intake", "channel aspect ratio L/d", pset("L_over_d"), units="-", tolerance=T_SET,
      ec="model-derived", label="PARETO_SET", sources=[rob, uni, ref("F1", "/design_space/variables/L_over_d")],
      basis="F1 trade (F1-05): L/d trades collection efficiency and off-axis tolerance against passive compression",
      fs="OPEN", adv=[REP_RULE, ACCOM, FLOWREQ])
    P(rows, "AFC-UP-IN-03", S, "intake", "open-area fraction phi", pset("phi"), units="-", tolerance=T_SET,
      ec="model-derived", label="PARETO_SET", sources=[rob, uni, ref("F1", "/design_space/variables/phi")],
      basis="frozen intake-surface nodes 0.8 / 0.9", fs="OPEN",
      adv=[REP_RULE, "honeycomb structural design and manufacturability (F1Q-02)"])
    P(rows, "AFC-UP-IN-04", S, "intake", "channel diameter d", get("F1", "/design_space/variables/d_mm"),
      units="mm", tolerance="n/a (objective-invariant at fixed L/d, F1-02)", ec="model-derived",
      ec_note="free-molecular outputs are d-invariant at fixed L/d; d sets only intake depth L and cell count",
      sources=[ref("F1", find("F1", "/findings", "id", "F1-02") + "/finding"),
               ref("F78", "/design_vector/blocks/0/variables/1")],
      basis="F1-02; F7 collapses d", fs="OPEN",
      adv=["honeycomb structural / manufacturing design (wall thickness, cell count, depth) (F1Q-02)"])
    P(rows, "AFC-UP-IN-05", S, "intake", "honeycomb structure: wall thickness, AO coating (thickness, density), support "
      "fraction, wall material", "TBD - no sourced Vyovrinda structural design; code defaults are a labelled parametric "
      "case only (F1-P-02..05)", units="mm; um; kg m^-3; -", tolerance="TBD", ec=None,
      sources=[ref("F1", find("F1", "/items", "id", "F1-P-02")), ref("F1", find("F1", "/items", "id", "F1-P-05")),
               ref("F1", find("F1", "/open_owner_questions", "id", "F1Q-02") + "/question")],
      basis="F1-P-02..05 TBD; Al 6061-T6 density is cited only if Al 6061 is chosen (F1-P-01)", fs="TBD_OWNER",
      adv=["owner answer to F1Q-02 (sourced design or labelled budgeting assumption)"])
    P(rows, "AFC-UP-IN-06", S, "intake", "gas-surface accommodation alpha and kernel (Maxwell / CLL)",
      "TBD - carried as 10 scenarios (alpha 0, 0.2, 0.5, 0.8, 1 x Maxwell / CLL), never optimised",
      units="-", tolerance="TBD", ec=None,
      sources=[ref("F1", find("F1", "/items", "id", "F1-P-07")), ref("F1", find("F1", "/items", "id", "F1-P-08")),
               ref("F78", find("F78", "/open_owner_questions", "id", "OQ-F78-02") + "/question")],
      basis="no measured accommodation for any Vyovrinda surface", fs="TBD_AFTER_EVIDENCE",
      adv=[ACCOM, "owner answer OQ-F78-02 (robustness scope)"])
    P(rows, "AFC-UP-IN-07", S, "intake", "pointing budget theta (intake axis vs relative wind)",
      "TBD - evaluated at 0 deg and 5 deg (design state only)", units="deg", tolerance="TBD", ec=None,
      sources=[ref("F1", find("F1", "/items", "id", "F1-P-09")),
               ref("F1", find("F1", "/open_owner_questions", "id", "F1Q-03") + "/question"),
               ref("F78", find("F78", "/findings", "id", "F8-03") + "/finding")],
      basis="no AOCS pointing budget in the repository", fs="TBD_OWNER", adv=["owner answer F1Q-03 / AOCS budget"])
    P(rows, "AFC-UP-IN-08", S, "intake", "channel wall / plenum gas temperature T_wall",
      get("F1", find("F1", "/items", "id", "F1-P-06") + "/value"), units="K", tolerance="n/a (code default)",
      ec="assumed", ec_note="code default the frozen TPMC surface was built with (no cited source)",
      sources=[ref("F1", find("F1", "/items", "id", "F1-P-06"))], basis="F1-P-06; UPSTREAM_ICD G-07", fs="OPEN",
      adv=["H2-5 thermal network value for the intake / plenum walls (UPSTREAM_ICD G-07 two-temperature issue)"])
    drag = [m["drag_intake_max_N"] for m in mem]
    P(rows, "AFC-UP-IN-09", S, "intake", "intake-face drag of the robust set (max over orbit states)",
      {"kind": "PARETO_SET", "robust_set_range_N": _rng(drag), "hard_constraint": "HC-09 intake-face drag <= 25 mN "
       "(necessary, not sufficient; MET_ON_SUPPLIED_VALUES for every nominal Pareto evaluation)"},
      units="N", tolerance="TPMC statistical SE ~1e-4 relative (F8-02); the TBD surface scenario dominates",
      ec_note=_hc09_note(),
      ec="model-derived", label="PARETO_SET", sources=[rob, ref("F78", find("F78", "/hard_constraints", "id", "HC-09"))],
      basis="F8 worst case over the 10 scenarios; spacecraft body / array drag excluded (TBD, OQ-F78-04)", fs="OPEN",
      adv=["spacecraft frontal geometry / D_spacecraft (OQ-F78-04)", HALL_MAP + " for T - D (HC-08)"])
    P(rows, "AFC-UP-IN-10", S, "intake", "intake mass m_intake",
      "TBD - structural inputs TBD; the wall area 2 phi A L/d is the mass proxy in F7 / F8", units="kg",
      tolerance="TBD", ec=None,
      sources=[ref("F1", find("F1", "/findings", "id", "F1-09") + "/finding"),
               ref("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-01"))],
      basis="F1-09; AL-01 intake/filter/duct allocation 3.5 kg is a budget, not a CBE", fs="TBD_AFTER_EVIDENCE",
      adv=["F1Q-02 structural basis", "CBE or weighed article (H2-7 H27-01)"])

    # ------------------------------------------------ filter
    P(rows, "AFC-UP-FI-01", S, "filter", "filter concept",
      "TBD - no concept selected; FC-01..FC-07 LISTED_ONLY_NO_SELECTION; FC-00 'none' is a definitional reference "
      "whose admissibility is TBD_OWNER (F2-OQ-03)", units="-", tolerance="TBD", ec=None,
      sources=[ref("F2", "/candidate_concepts"), ref("F2", find("F2", "/open_owner_questions", "id", "F2-OQ-03")),
               ref("F2", find("F2", "/open_owner_questions", "id", "F2-OQ-01"))],
      basis="A9.7 F2: unknown filter parameters stay evidence-labelled", fs="TBD_OWNER",
      adv=["owner answers F2-OQ-01 (protection functions + acceptance) and F2-OQ-03 ('none' admissibility)",
           "evidenced filter records (transmission, capture, conversion, mass) for a concept"],
      note="the F7 / F8 robust set is computed in the filter context F4-FIL-NONE only because the filter's "
           "protection benefit is NOT_EVALUATED (a flow-only comparison would score that TBD benefit as zero); this "
           "is not a filter decision")
    P(rows, "AFC-UP-FI-02", S, "filter", "filter placement (ahead of collimator / intake chamber / compressor inlet)",
      "TBD - owner question F2-OQ-04", units="-", tolerance="TBD", ec=None,
      sources=[ref("F2", find("F2", "/open_owner_questions", "id", "F2-OQ-04"))], basis="F2-OQ-04",
      fs="TBD_OWNER", adv=["owner answer F2-OQ-04"])
    P(rows, "AFC-UP-FI-03", S, "filter", "per-species forward / backflow transmission, capture and O conversion",
      "TBD - every species / direction quantity TBD (F2 items tau_f.*, tau_b.*, capture_*, conversion_*)",
      units="-", tolerance="TBD", ec=None,
      sources=[ref("F2", find("F2", "/items", "id", "tau_f.O")), ref("F2", find("F2", "/items", "id", "tau_b.N2"))],
      basis="F2 interface model; no open-literature ABEP filter numbers located", fs="TBD_AFTER_EVIDENCE",
      adv=["measured or sourced transmission / capture of the selected concept"])
    P(rows, "AFC-UP-FI-04", S, "filter", "free-molecular conductance law of a geometric screen",
      get("F2", find("F2", "/items", "id", "conductance_law") + "/value"), units="m^3 s^-1", tolerance=T_RULE,
      ec="model-derived", ec_note="Livesey / Cole transmission probability (F2 source register)",
      sources=[ref("F2", find("F2", "/items", "id", "conductance_law"))], basis="F2 interface model",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-UP-FI-05", S, "filter", "filter face area and areal mass", "TBD - F2 items face_area_m2, "
      "areal_mass_kg_m2", units="m^2; kg m^-2", tolerance="TBD", ec=None,
      sources=[ref("F2", find("F2", "/items", "id", "face_area_m2")),
               ref("F2", find("F2", "/items", "id", "areal_mass_kg_m2"))],
      basis="no concept", fs="TBD_AFTER_EVIDENCE", adv=["concept selection (AFC-UP-FI-01) and its design"])
    P(rows, "AFC-UP-FI-06", S, "filter", "atomic-oxygen / material applicability", "TBD - INCOMPLETE_EVIDENCE for every "
      "listed concept (no material stated)", units="-", tolerance="TBD", ec=None,
      sources=[ref("F2", "/candidate_concepts/1/ao_applicability"), ans(132)],
      basis="AO coupon / dedicated AO source programme (owner row 132)", fs="TBD_AFTER_EVIDENCE",
      adv=["AO coupon evidence for the selected filter material (row 132)", "P4 APP-FILTER if the owner adds it "
                                                                                 "(F2-OQ-04)"])
    P(rows, "AFC-UP-FI-07", S, "filter", "repository placeholder filter values (open fraction 0.7, transmission 0.6, "
      "0.8 kg/m^2)", "not used in the candidate (PLACEHOLDER_NOT_A_FLIGHT_DESIGN)", units="-", tolerance=T_RULE,
      ec="owner-allocation", ec_note="A9.7 F2 directive: do not silently use the placeholder values as a flight design",
      sources=[ref("F2", "/repository_placeholders/rule"), tref("A97_MD", "Do not silently use the current "
                                                                         "placeholder filter values as a flight design.")],
      basis="A9.7 F2", fs="FREEZE_CANDIDATE", label="RULE")

    # ------------------------------------------------ compressor
    comps = us["compressors"]
    P(rows, "AFC-UP-CO-01", S, "compressor", "compressor topology",
      {"kind": "PARETO_SET", "robust_set": "turbo-molecular rows only (N_drag = 0)",
       "nominal_pareto_union_all_turbo_only": us["union_compressors_all_turbo_only"],
       "drag_stage_designs_feasible": 0},
      units="-", tolerance=T_SET, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      ec_note="drag stages are infeasible because every drag-stage evaluation overloads the Gaede characteristic at "
              "the uncited code-default channel geometry (F3-01), which the production module silently clips "
              "(model-change candidate MCC-02)",
      sources=[cite("F3", find("F3", "/findings", "id", "F3-01") + "/finding", "Feasible drag-stage designs: 0"), uni,
               rob],
      basis="F3 bounded design search; F7 / F8 Pareto", fs="OPEN",
      adv=[T12, "drag-channel geometry evidence (T-1) and disposition of MCC-02 (silent Gaede clipping)",
           "owner answer OQ-F3-03 (regime above 0.1 Pa)"])
    P(rows, "AFC-UP-CO-02", S, "compressor", "compressor design set (F3 design ids)",
      {"kind": "PARETO_SET", "robust_set": {c: {k: comps[c][k] for k in ("N_turbo", "A_turbo_m2", "R_turbo_m",
                                                                         "u_tip_turbo_mps", "rpm", "N_drag",
                                                                         "rotor_material")} for c in comps},
       "nominal_pareto_union_ids": us["union"]["compressor"]},
      units="-; m^2; m; m/s; rpm", tolerance=T_SET, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      sources=[rob, uni, ref("F3D", "/design_grid")], basis="F3 grid decoded from F3 design ids", fs="OPEN",
      adv=[REP_RULE, T12, "hub ratio / blade span definition (OQ-F3-02)"],
      note="R_turbo uses the zero-hub limit sqrt(A/pi) (OQ-F3-02)")
    P(rows, "AFC-UP-CO-03", S, "compressor", "rotor material", "Ti-6Al-4V (only material with a cited allowable in "
      "F3; Al alloys and CFRP excluded until a cited allowable and an AO disposition exist)", units="-",
      tolerance=T_RULE, ec="inferred",
      sources=[ref("F3", "/materials_excluded"), ref("F3", find("F3", "/open_owner_questions", "id", "OQ-F3-04"))],
      basis="F3 evidence rule (ROTOR_MATERIAL_ALLOWABLE_TBD gate)", fs="OPEN",
      adv=["owner answer OQ-F3-04", "owner answer OQ-F3-01 (allowable basis)"])
    P(rows, "AFC-UP-CO-04", S, "compressor", "rotor allowable and stress safety factor",
      {"Fty_A_basis_MPa": 827, "safety_factor": "TBD (module default 2.0 is uncited)",
       "tip_speed_cap_mps_at_SF2": 305.5},
      units="MPa; -; m/s", tolerance=T_RULE, ec="inferred",
      ec_note="Fty cited (MMPDS-06 via NASA-HDBK-6025, room temperature); the safety factor is uncited",
      sources=[cite("F3", find("F3", "/findings", "id", "F3-02") + "/finding", "827 MPa", "305.5 m/s"),
               ref("F3", find("F3", "/open_owner_questions", "id", "OQ-F3-01"))],
      basis="F3-02; model-change candidate MCC-03 (production rotor_ok uses an uncited 880 MPa)", fs="TBD_OWNER",
      adv=["owner answer OQ-F3-01 (factor, product form, temperature)"])
    pc = [m["P_compressor_el_max_W"] for m in mem]
    mc = [m["m_compressor_max_kg"] for m in mem]
    tc = [v for m in mem for v in us["extra"][m["design_id"]]["T_comp_max_K"]]
    xo = [v for m in mem for v in us["extra"][m["design_id"]]["xO_flow"]]
    P(rows, "AFC-UP-CO-05", S, "compressor", "compressor electrical power (robust set, max over states)",
      {"kind": "PARETO_SET", "robust_set_range_W": _rng(pc),
       "nominal_pareto_range_W": get("F78", "/system_evaluation/parametric_P_bus_lower_bound_W_range")},
      units="W", tolerance=T_PARAM, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      ec_note="eta_motor, bearing and control terms are uncited code defaults (F3 efficiency_basis)",
      sources=[rob, ref("F3", "/efficiency_basis"), ref("F78", find("F78", "/findings", "id", "F78-06"))],
      basis="DragCompressor model through F3 / F4 / F7", fs="OPEN",
      adv=["compressor_downselect T-4 (bearing / motor) and a measured drive efficiency", T12])
    P(rows, "AFC-UP-CO-06", S, "compressor", "compressor mass (robust set)",
      {"kind": "PARETO_SET", "robust_set_range_kg": _rng(mc),
       "nominal_pareto_range_kg": get("F78", "/system_evaluation/parametric_m_compressor_kg_range"),
       "AL-02_allocation_kg": get("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-02") +
                                  "/allocation_kg")},
      units="kg", tolerance=T_PARAM, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      sources=[rob, ref("F3", "/mass_basis"), ref("F78", find("F78", "/findings", "id", "F78-07")),
               ref("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-02"))],
      basis="parametric model mass vs owner allocation (neither is a CBE; never merged)", fs="OPEN",
      adv=["compressor_downselect T-7 (rotor / disc mass) and a CBE", "owner re-allocation if a CBE exceeds AL-02"])
    P(rows, "AFC-UP-CO-07", S, "compressor", "compressor outlet / stage pressure domain",
      get("F3", find("F3", "/parameters", "id", "P-MOLECULAR-LIMIT") + "/value"), units="Pa (upper bound)",
      tolerance=T_RULE, ec="inferred", ec_note="free-molecular Gaede characteristic domain (Chiggiato 2013 Sec. 4.1.2)",
      sources=[ref("F3", find("F3", "/parameters", "id", "P-MOLECULAR-LIMIT")),
               ref("F3", find("F3", "/open_owner_questions", "id", "OQ-F3-03"))],
      basis="model evidence domain, not a design value; PROPOSED W1 setpoint 0.2 Pa lies outside it (F3-03)",
      fs="OPEN", adv=["owner answer OQ-F3-03", "T-1 data or an open-literature transitional-regime stage model"])
    P(rows, "AFC-UP-CO-08", S, "compressor", "compressor lumped temperature (robust set)",
      {"kind": "PARETO_SET", "robust_set_range_K": _rng(tc)}, units="K", tolerance=T_PARAM, ec="model-derived",
      label="PARAMETRIC_SENSITIVITY", ec_note="lumped node T = T_sink + losses / conductance (code defaults, T-5)",
      sources=[uni, ref("F3", "/thermal_basis")], basis="F7 nominal-context rows of the robust members", fs="OPEN",
      adv=["H2-5 thermal node of the compressor with a measured conductance (T-5)"])
    P(rows, "AFC-UP-CO-09", S, "compressor", "delivered-flow atomic-O mole fraction (robust set)",
      {"kind": "PARETO_SET", "robust_set_range": _rng(xo)}, units="-", tolerance=T_PARAM, ec="model-derived",
      label="PARAMETRIC_SENSITIVITY", sources=[uni, ref("F3", find("F3", "/findings", "id", "F3-04") + "/finding")],
      basis="the delivered flow keeps the inlet composition; the outlet partial-pressure composition is O-depleted "
            "(F3-04)", fs="OPEN", adv=["measured delivered species state (owner row 102)", T12])

    # ------------------------------------------------ plenum
    P(rows, "AFC-UP-PL-01", S, "plenum", "plenum volume V", pset("V_m3"), units="m^3", tolerance=T_SET,
      ec="model-derived", label="PARETO_SET",
      sources=[rob, uni, ref("F4", find("F4", "/search_variables", "id", "x_plenum.V"))],
      basis="volume trades the mass proxy against shaft-frequency ripple attenuation; the plenum is not an "
            "orbit-scale buffer at <= 0.1 Pa (F4-05)", fs="OPEN",
      adv=[REP_RULE, "H-1 transient tolerances at LOCK-2 (OQ-F4-03, F5 IFD-F4-05)", "plenum mass model (F4-P-16)"])
    P(rows, "AFC-UP-PL-02", S, "plenum", "plenum set pressure P_set", pset("P_set_Pa"), units="Pa", tolerance=T_SET,
      ec="model-derived", label="PARETO_SET",
      sources=[rob, uni, ref("F78", find("F78", "/findings", "id", "F78-03") + "/finding")],
      basis="robust members exist only at P_set 0.01 Pa; all-state-feasible contexts exist for 0.005-0.1 Pa",
      fs="OPEN", adv=["H-1 required inlet pressure (H1F-IN-04)", "owner answer OQ-F4-01 (setpoint policy)",
                      "owner answer OQ-F4-02 (design direction at <= 0.1 Pa)"])
    P(rows, "AFC-UP-PL-03", S, "plenum", "setpoint policy across orbit states (single vs scheduled)",
      "TBD - owner question OQ-F4-01 (single-setpoint frontier 0.1027 mg/s vs scheduled 0.143 mg/s, parametric)",
      units="-", tolerance="TBD", ec=None,
      sources=[ref("F4", find("F4", "/open_owner_questions", "id", "OQ-F4-01"))], basis="F4-01", fs="TBD_OWNER",
      adv=["owner answer OQ-F4-01"])
    P(rows, "AFC-UP-PL-04", S, "plenum", "chain gas temperature (isothermal chain)",
      get("F4", find("F4", "/items", "id", "F4-P-01") + "/value"), units="K", tolerance="n/a (code default)",
      ec="assumed", sources=[ref("F4", find("F4", "/items", "id", "F4-P-01"))], basis="F4-P-01 = F1 T_wall",
      fs="OPEN", adv=["H2-5 thermal network (UPSTREAM_ICD G-07)"])
    P(rows, "AFC-UP-PL-05", S, "plenum", "plenum lining baseline", "inert / low-recombination lining to preserve the "
      "representative atomic-O fraction as far as practical", units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ans(102)], basis="owner row 102", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-UP-PL-06", S, "plenum", "plenum wall O recombination probability gamma",
      "TBD - parametric cases WALL-G0 (0) and WALL-TI64-DB (uncited prior) only", units="-", tolerance="TBD",
      ec=None, sources=[ref("F4", find("F4", "/items", "id", "F4-P-06")),
                        ref("F78", find("F78", "/findings", "id", "F8-04") + "/finding")],
      basis="F4-P-06; owner GP-D03", fs="TBD_AFTER_EVIDENCE",
      adv=["coupon / witness evidence of the selected lining (GP-D03)"],
      note="robust members lose feasibility in most scenarios under WALL-TI64-DB (F8-04)")
    P(rows, "AFC-UP-PL-07", S, "plenum", "plenum external leak area", "TBD - code default 5e-8 m^2 is a parametric case",
      units="m^2", tolerance="TBD", ec=None, sources=[ref("F4", find("F4", "/items", "id", "F4-P-05"))],
      basis="F4-P-05", fs="TBD_AFTER_EVIDENCE", adv=["leak specification / helium leak test of the plenum"])
    wc = [m["mdot_delivered_min_kgps"] * 1e6 for m in mem]
    P(rows, "AFC-UP-PL-08", S, "plenum", "delivered total flow offered by the upstream chain (min over orbit states)",
      {"kind": "PARETO_SET", "robust_set_worst_case_range_mg_s": _rng(wc),
       "all_state_single_setpoint_frontier_mg_s": 0.1027382, "all_state_scheduled_frontier_mg_s": 0.142955,
       "owner_ground_characterization_range_mg_s": get("F78", find("F78", "/items", "id", "F78-P-11") + "/value"),
       "pareto_members_reaching_0.38_mg_s_at_every_state": 0},
      units="mg/s", tolerance=T_PARAM, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      sources=[rob, cite("F78", find("F78", "/findings", "id", "F78-02") + "/finding", "0.1027382",
                         "reaching the owner ground-characterization lower end 0.38 mg/s at every state: 0"),
               cite("F4", find("F4", "/findings", "id", "F4-01") + "/finding", "0.143 mg/s"),
               cite("F4", find("F4", "/findings", "id", "F4-07") + "/finding", "0.142955"), ans(73)],
      basis="F4 / F7 frontiers under parametric inputs; the owner range (row 73) is characterization context, not a "
            "flight requirement", fs="OPEN",
      adv=[FLOWREQ, "owner answer OQ-F4-04 (lever: capture, operating states or feed requirement)", T12, ACCOM])
    P(rows, "AFC-UP-PL-09", S, "plenum", "plenum mass", "TBD - plenum geometry / wall design TBD (F4-P-16)",
      units="kg", tolerance="TBD", ec=None,
      sources=[ref("F4", find("F4", "/items", "id", "F4-P-16")),
               ref("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-03"))],
      basis="AL-03 plenum/feed 1.0 kg is an allocation", fs="TBD_AFTER_EVIDENCE", adv=["plenum design and CBE"])

    # ------------------------------------------------ valves / feed
    P(rows, "AFC-UP-VF-01", S, "valves_feed", "atmospheric metering-valve control law",
      {"law": "PI on plenum pressure (normalized gain Kp, integral time Ti)",
       "Kp_grid": get("F4", find("F4", "/search_variables", "id", "x_plenum.Kp") + "/value"),
       "Ti_grid_s": get("F4", find("F4", "/search_variables", "id", "x_plenum.Ti") + "/value")},
      units="-; s", tolerance=T_SET, ec="model-derived", label="PARETO_SET",
      sources=[ref("F4", find("F4", "/search_variables", "id", "x_plenum.Kp")), ref("F4", "/pareto"),
               ref("M16", find("M16", "/rows", "row", 5) + "/blocking_item")],
      basis="F4 transient Pareto over (Kp, Ti, V, compressor, intake)", fs="OPEN",
      adv=["metering-valve class selection (H3) and released ground-qualification feed points (M16 row 5)",
           "owner answer OQ-F4-03 (transient metric basis)"])
    P(rows, "AFC-UP-VF-02", S, "valves_feed", "metering-valve bandwidth", "TBD - parametric 1 Hz; sensitivity "
      "0.1-10 Hz changed no status (F4-09)", units="Hz", tolerance="TBD", ec=None,
      sources=[ref("F4", find("F4", "/items", "id", "F4-P-08")),
               ref("F4", find("F4", "/findings", "id", "F4-09") + "/finding")],
      basis="F4-P-08", fs="TBD_AFTER_EVIDENCE", adv=["metering-valve class (H3 procurement)"])
    P(rows, "AFC-UP-VF-03", S, "valves_feed", "metering-valve authority", "TBD - parametric 3", units="-",
      tolerance="TBD", ec=None, sources=[ref("F4", find("F4", "/items", "id", "F4-P-09"))], basis="F4-P-09",
      fs="TBD_AFTER_EVIDENCE", adv=["metering-valve sizing"],
      note="larger orbit amplitudes fail mostly by valve saturation at authority 3 (F4-08)")
    cd = get("F4", "/steady/conductance_demand")
    row13 = [c for c in cd if c["mdot_mgps"] == 1.3]
    assert len(row13) == 1
    P(rows, "AFC-UP-VF-04", S, "valves_feed", "downstream feed-path molecular conductance demand at a 0.1 Pa upstream "
      "pressure (valve + line + isolator + distributor + H-1)",
      {"at_1.3_mg_s_N2_m3_s": row13[0]["C_min_m3_s_if_all_N2"],
       "orifice_equivalent_area_N2_m2": row13[0]["orifice_equivalent_area_m2_if_all_N2"],
       "table": "steady.conductance_demand (0.03 / 0.38 / 1.3 / ... mg/s; N2 / O2 / O brackets)"},
      units="m^3/s; m^2", tolerance="n/a (necessary bound)", ec="model-derived",
      sources=[ref("F4", "/steady/conductance_demand"), ref("F4", find("F4", "/findings", "id", "F4-03") + "/finding"),
               ref("F4", find("F4", "/open_owner_questions", "id", "OQ-F4-02"))],
      basis="F4-03: the H2-3 analog IF-A5 pressure 5.74-1216 Pa lies above the compressor domain cap", fs="OPEN",
      adv=["owner answer OQ-F4-02 (design direction)", "frozen H-1 channel and distributor (H1F-IN-04)"])
    P(rows, "AFC-UP-VF-05", S, "valves_feed", "required H-1 inlet state at HALL_INLET_Z0 / IF-A5",
      "TBD - requires the frozen channel and distributor (H1F-IN-04 / IN-05)", units="Pa; mg/s; K; -",
      tolerance="TBD", ec=None,
      sources=[ref("F5", find("F5", "/parameters", "id", "H1F-IN-04")),
               ref("F4", find("F4", "/items", "id", "F4-P-10"))],
      basis="F5 IFD-F4-01..05; F4-P-10", fs="TBD_AFTER_EVIDENCE",
      adv=["H-1 channel design point (H1F-CH-11)", "Phase-1 measured H-1 inlet conductance / pressure"])
    off = get("F4", "/offered_to_h1")
    P(rows, "AFC-UP-VF-06", S, "valves_feed", "feed-state records offered to H-1 (mdot_s, P, T, x_s, transient quality)",
      {"kind": "PARETO_SET", "n_records": len(off), "P_range_Pa": _rng([o["P_Pa"] for o in off]),
       "mdot_total_range_mg_s_design_state": _rng([o["mdot_total_mgps"] for o in off]),
       "T_K": sorted({o["T_K"] for o in off}), "design_state": sorted({o["design_state"] for o in off})},
      units="mg/s; Pa; K; -", tolerance=T_PARAM, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      sources=[ref("F4", "/offered_to_h1")],
      basis="F4 transient Pareto members at the design state h200_f150 (single-state values; the all-state "
            "frontier is AFC-UP-PL-08)", fs="OPEN", adv=["F4 MODE_STRICT blockers closed (F4 strict_mode)", T12])
    P(rows, "AFC-UP-VF-07", S, "valves_feed", "Xe high-pressure path isolation", "dual series isolation on the "
      "high-pressure Xe path plus critical sensing / FDIR redundancy; thruster, ICP neutralizer and full PPU not "
      "duplicated", units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ans(55), ref("MP2", find("MP2", "/bom", "id", "A9B-10"))], basis="owner row 55", fs="FREEZE_CANDIDATE",
      label="RULE", note="RVMQ-01 may re-base the redundancy policy on the official RFP clause")


# --------------------------------------------------------------------------------------------------------------------
F5_GROUP_TO_SUB = {"CH": ("PROPULSION", "h1_geometry"), "IN": ("PROPULSION", "h1_geometry"),
                   "EX": ("PROPULSION", "h1_geometry"), "MC": ("PROPULSION", "magnetic_circuit"),
                   "BZ": ("PROPULSION", "magnetic_circuit"), "CO": ("PROPULSION", "magnetic_circuit"),
                   "AN": ("PROPULSION", "anode"), "TH": ("SYSTEM", "thermal_interfaces")}
F5_MA_TO_SUB = {"H1F-MA-05": "h1_geometry", "H1F-MA-08": "anode"}  # other MA rows: magnetic circuit materials


def build_h1_from_f5(rows: list) -> None:
    """Every F5 parameter enters the candidate unchanged (value, tolerance, class, freeze status), cited by pointer."""
    for i, p in enumerate(get("F5", "/parameters")):
        if p["group"] == "MA":
            sec, sub = "PROPULSION", F5_MA_TO_SUB.get(p["id"], "magnetic_circuit")
        else:
            sec, sub = F5_GROUP_TO_SUB[p["group"]]
        ec = p["evidence_class"]
        adv = list(p.get("evidence_to_freeze_candidate") or [])
        P(rows, "AFC-" + p["id"], sec, sub, p["name"], p["value"], units=p["units"], tolerance=p["tolerance"],
          ec=ec, ec_note=p.get("evidence_note"), sources=[ref("F5", f"/parameters/{i}")], basis=p["basis"],
          fs=p["freeze_status"], adv=adv,
          origin={"lane": "F5 fo_a9_7_f5_h1_freeze_candidate", "id": p["id"], "n_origin_sources": len(p["source"]),
                  "origin_sources": [{k: s[k] for k in ("path", "pointer", "sha256") if k in s} for s in p["source"]]})


def _icd(iid: str) -> dict:
    return get("ICD", find("ICD", "/items", "id", iid))


def build_propulsion_icp(rows: list) -> None:
    S = "PROPULSION"
    # ---------------- downstream ICP geometry (F6 design vector; every bound TBD)
    for i, v in enumerate(get("F6", "/design_vector/variables")):
        sub = "collector" if v["id"] in ("F6-X-10", "F6-X-11", "F6-X-12", "F6-X-13") else "icp_geometry"
        P(rows, "AFC-" + v["id"], S, sub, f"{v['symbol']}: {v['name']}",
          "TBD - bounds TBD; requires " + v["bounds"]["requires"], units=v["units"], tolerance="TBD", ec=None,
          sources=[ref("F6", f"/design_vector/variables/{i}")],
          basis="F6 framework (SEARCH_NOT_RUN: search once P1 / P2 evidence exists, A9.7 F6)", fs="TBD_AFTER_EVIDENCE",
          adv=[v["bounds"]["requires"], "owner answer F6-OQ-02 (bound source) and F6-OQ-03 (bench matrix vs "
                                        "validated model)", "P1 / P2 data on the built geometry"])
    P(rows, "AFC-PR-ICP-01", S, "icp_geometry", "ICP first-build topology and magnetization",
      _icd("ICP-32")["value"] + "; open-tube coaxial first build (A9.3 OQ-VI-03)", units="-", tolerance=T_RULE,
      ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-32")),
                                     ref("F6", "/design_vector/variables/1/name")],
      basis="ICD ICP-32 OWNER_GIVEN", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-ICP-02", S, "icp_geometry", "radiative-view-factor design objective of the ICP assembly",
      "open-frame support, minimum obstruction, annular / open optical path, thermally isolated mounting, "
      "high-emittance outward surfaces, Hall-to-ICP axial spacing; not optimized for compactness alone",
      units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("A92", "/decisions/radiative_view_requirement"), ref("ICD", find("ICD", "/items", "id", "ICP-47"))],
      basis="A9.2 radiative_view_requirement", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-ICP-03", S, "icp_geometry", "kinematic carrier KC-1 (shared datum, H-1 stays bolted)",
      _icd("ICP-06")["value"], units="-", tolerance=T_RULE, ec="assumed", ec_note="PROPOSED concept in the ICD",
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-06"))], basis="ICD ICP-06 PROPOSED", fs="TBD_OWNER",
      adv=["owner acceptance of the ICD (DRAFT_PENDING_OWNER) at LOCK-1"])
    P(rows, "AFC-PR-ICP-04", S, "icp_geometry", "ICP module mass", "TBD - materials, thicknesses, antenna and collector "
      "geometry TBD (F6 mass_relation NOT_EVALUATED)", units="kg", tolerance="TBD", ec=None,
      sources=[ref("F6", "/geometric_screening/mass_relation"), ref("F6", find("F6", "/items", "id", "F6-P-02"))],
      basis="AL-05 ICP neutralizer 2.0 kg is an owner allocation (not a CBE)", fs="TBD_AFTER_EVIDENCE",
      adv=["ICP module drawing (ICD ICP-02/04/07) and CBE"])
    P(rows, "AFC-PR-ICP-05", S, "icp_geometry", "Hall magnetic-field disturbance metric and threshold",
      "TBD - owner question F6-OQ-04", units="-", tolerance="TBD", ec=None,
      sources=[ref("F6", find("F6", "/open_owner_questions", "id", "F6-OQ-04")),
               ref("ICD", find("ICD", "/items", "id", "ICP-31"))],
      basis="F6 objective hall_b_field_disturbance; ICD ICP-31 B(z) scan with the module installed",
      fs="TBD_OWNER", adv=["owner answer F6-OQ-04", "FEMM of MC-1 covering the ICP region (F6-IF-N02)"])

    # ---------------- RF / match architecture
    P(rows, "AFC-PR-RF-01", S, "rf_match", "ICP RF frequency", _icd("ICP-11")["value"], units="MHz",
      tolerance=T_RULE, ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-11")), ans(72)],
      basis="owner row 72; A9 decision", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-RF-02", S, "rf_match", "RF chain and matching-network location", _icd("ICP-13")["value"],
      units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("A92", "/decisions/OQ-A907-11"), ref("ICD", find("ICD", "/items", "id", "ICP-13")),
               ref("A92", "/decisions/a9_10_statuses/RF matching architecture")],
      basis="A9.2 OQ-A907-11: LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT", fs="FREEZE_CANDIDATE", label="RULE",
      note="development-article matching network; the flight matching implementation is AFC-PR-RF-03")
    P(rows, "AFC-PR-RF-03", S, "rf_match", "flight matching implementation (fixed / switched / electronically tuned)",
      "TBD - only after Z_antenna = R + jX is measured vs mdot, P_RF, p, gas composition and Hall operating point",
      units="-", tolerance="TBD", ec=None, sources=[ref("A92", "/decisions/icp_matching_strategy")],
      basis="A9.2 icp_matching_strategy", fs="TBD_AFTER_EVIDENCE", adv=["P2 impedance map (PREPARATION_ONLY_NOT_RUN)"])
    P(rows, "AFC-PR-RF-04", S, "rf_match", "laboratory RF investigation capability", _icd("ICP-12")["value"],
      units="W (delivered / operating)", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("A92", "/decisions/rf_500W"), ref("ICD", find("ICD", "/items", "id", "ICP-12"))],
      basis="A9.2 rf_500W: a laboratory capability, not a component rating and not a power allocation",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-RF-05", S, "rf_match", "RF component ratings (generator forward power, coupler, coax, connectors, "
      "matching elements, feedthroughs, antenna RF voltage / Paschen)", "TBD - TBD_AFTER_IMPEDANCE_MAP",
      units="W; V", tolerance="TBD", ec=None,
      sources=[ref("A92", "/decisions/a9_10_statuses/RF component ratings"),
               ref("ICD", find("ICD", "/items", "id", "ICP-15")), ref("ICD", find("ICD", "/items", "id", "ICP-44"))],
      basis="A9.2 rf_500W / a9_10_statuses", fs="TBD_AFTER_EVIDENCE",
      adv=["P2 impedance map: mismatch envelope characterized (Z_antenna vs operating factors)"])
    P(rows, "AFC-PR-RF-06", S, "rf_match", "RF measurement reference", "forward / reflected power on the generator / "
      "50-ohm side of the local match; P_delivered = P_forward - P_reflected - P_line/match,loss; never P_forward = "
      "P_plasma", units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("A92", "/decisions/rf_measurement_reference")], basis="A9.2", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-RF-07", S, "rf_match", "RF protection and trip thresholds", "TBD - reflected-power monitoring, "
      "mismatch / interlock threshold, arc detection, thermal monitoring and automatic reduction / shutdown are "
      "required; thresholds frozen after antenna / load characterization", units="W; -", tolerance="TBD", ec=None,
      sources=[ref("A92", "/decisions/rf_protection"), ref("ICD", find("ICD", "/items", "id", "ICP-16"))],
      basis="A9.2 rf_protection", fs="TBD_AFTER_EVIDENCE", adv=["P2 load characterization"])
    P(rows, "AFC-PR-RF-08", S, "rf_match", "flight RF source DC-input -> forward-power efficiency",
      "TBD - requires a measured flight-representative DC-input RF source (A902-21)", units="-", tolerance="TBD",
      ec=None, sources=[ref("BUS", find("BUS", "/items", "id", "A902-21")),
                        ref("MP2", "/power/icp_rf_chain/flight_source_efficiency")],
      basis="A9-02 bus boundary", fs="TBD_AFTER_EVIDENCE",
      adv=["measured flight-representative DC-RF source (M16 v4 row 19 blocking item)"])
    P(rows, "AFC-PR-RF-09", S, "rf_match", "ICP RF power closure", get("A92", "/decisions/a9_10_statuses/ICP RF power "
                                                                              "closure"),
      units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("A92", "/decisions/a9_10_statuses/ICP RF power closure"),
               ref("BUS", find("BUS", "/items", "id", "A902-20"))],
      basis="A9.2 status; P_ICP,available = 1350 W - P_common - P_Hall - P_other,active (no fixed split)",
      fs="TBD_AFTER_EVIDENCE", label="RULE",
      adv=["P1 C_e / C_e,DC at the ICP-45 point and a measured flight-representative RF source"],
      note="value is the A9.2 status (PENDING_HARDWARE), not a power value")

    # ---------------- collector
    P(rows, "AFC-PR-CL-01", S, "collector", "electron-extraction collector / bias electrode (V/I range, material)",
      "TBD - V/I range and material are design items; collector never hard-grounded by default", units="V; A",
      tolerance="TBD", ec=None, sources=[ref("ICD", find("ICD", "/items", "id", "ICP-21")), ans(70),
                                         ref("BUS", find("BUS", "/items", "id", "A902-23"))],
      basis="ICD ICP-21; A902-23", fs="TBD_AFTER_EVIDENCE", adv=["ICP module design + P1 bench data"])
    P(rows, "AFC-PR-CL-02", S, "collector", "electron-current capacity I_e,cap vs I_d,max,H1 (ICP-45)",
      "TBD - ICP-45 NOT_EVALUATED (I_d,max,H1 not registered; no P1 data)", units="A", tolerance="TBD", ec=None,
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-45")),
               ref("A92", "/decisions/a9_10_statuses/ICP electron-current capacity"),
               ref("F78", find("F78", "/hard_constraints", "id", "HC-05"))],
      basis="I_e,cap = I_on - I_off (discharge OFF, signed; A9.4 P1Q-10 / A9.5 P1Q-16)", fs="TBD_AFTER_EVIDENCE",
      adv=["registered I_d,max,H1 from measured H-1 operation", "P1 ICP-45A EVALUATED_ENGINEERING_ONLY"])
    P(rows, "AFC-PR-CL-03", S, "collector", "Hall discharge circuit topology and V_d definition",
      _icd("ICP-22")["value"], units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-22")), ref("A91", "/decisions/A9-03-Vd")],
      basis="A9.1 A9-03-Vd", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-CL-04", S, "collector", "ICP body / collector isolation from Hall anode and cathode-common",
      _icd("ICP-23")["value"], units="V (plus margin TBD)", tolerance="margin TBD", ec="owner-allocation",
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-23")), ans(81)],
      basis="owner row 81 (350 V V_d end); margin and test voltage are LOCK-1 items", fs="TBD_OWNER",
      adv=["owner margin / test-voltage decision at LOCK-1 (OQ-RFQV2-06 / CIF-G04)"])
    P(rows, "AFC-PR-CL-05", S, "collector", "ICP body potential", _icd("ICP-20")["value"], units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-20")), ans(70)],
      basis="owner row 70", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-PR-CL-06", S, "collector", "final collector material", get("P4", "/fixed_statuses/"
                                                                                 "FINAL_COLLECTOR_MATERIAL/status"),
      units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("P4", "/fixed_statuses/FINAL_COLLECTOR_MATERIAL")],
      basis="A9.1 A9-03-collector: 316L for Ar engineering reproduction only", fs="TBD_AFTER_EVIDENCE", label="RULE",
      adv=["P4 APP-COLLECTOR coupon programme (O / AO) before N2 / O2 life claims"],
      note="value is the P4 status (OPEN), not a material")
    P(rows, "AFC-PR-CL-07", S, "collector", "ICP source gas (primary mode)", _icd("ICP-26")["value"], units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-26"))],
      basis="A9.1 HIQ-06 (G-REUSE primary)", fs="FREEZE_CANDIDATE", label="RULE")


def build_system(rows: list) -> None:
    S = "SYSTEM"

    def bus(iid):
        return ref("BUS", find("BUS", "/items", "id", iid))

    def busv(iid):
        return get("BUS", find("BUS", "/items", "id", iid) + "/value")

    # ---------------- PPU topology
    P(rows, "AFC-SY-PPU-01", S, "ppu", "internal propulsion bus", busv("A902-11"), units="V (regulated)",
      tolerance=T_RULE, ec="owner-allocation", sources=[bus("A902-11"), ans(111)], basis="owner row 111",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-PPU-02", S, "ppu", "spacecraft-input front-end voltage and efficiency", "TBD - front end kept "
      "configurable until the spacecraft bus is known (A902-12 / A902-13 OPEN)", units="V; -", tolerance="TBD",
      ec=None, sources=[bus("A902-12"), bus("A902-13")], basis="owner row 111", fs="TBD_AFTER_EVIDENCE",
      adv=["spacecraft bus definition", "selected / measured front-end converter"])
    P(rows, "AFC-SY-PPU-03", S, "ppu", "installed power slots (hall_icp_neutralizer)",
      get("MP2", "/power/configurations/hall_icp_neutralizer/installed_slots"), units="-", tolerance=T_RULE,
      ec="owner-allocation", sources=[ref("MP2", "/power/configurations/hall_icp_neutralizer/installed_slots"),
                                      ref("BUS", "/slots")],
      basis="A9-02 slot register; variants not installed: " + ", ".join(
          get("MP2", "/power/configurations/hall_icp_neutralizer/variant_options_not_installed")),
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-PPU-04", S, "ppu", "Hall magnet supplies", busv("A902-31"), units="-", tolerance=T_RULE,
      ec="owner-allocation", sources=[bus("A902-31")], basis="A9-02 A902-31", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-PPU-05", S, "ppu", "RF quantity crossing the bus boundary", busv("A902-19"), units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[bus("A902-19"), ref("MP2", "/power/icp_rf_chain")],
      basis="A9-02 / A9.2", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-PPU-06", S, "ppu", "supply efficiencies per slot", "TBD - one per slot (A902-35 OPEN)", units="-",
      tolerance="TBD", ec=None, sources=[bus("A902-35")], basis="A9-02", fs="TBD_AFTER_EVIDENCE",
      adv=["selected / measured supplies (breadboard discharge supply, row 113)"])
    P(rows, "AFC-SY-PPU-07", S, "ppu", "electronics redundancy policy", "limited redundancy (row 55)", units="-",
      tolerance=T_RULE, ec="owner-allocation",
      sources=[ans(55), ref("RVM", find("RVM", "/open_owner_questions", "id", "RVMQ-01"))],
      basis="owner row 55; RVMQ-01 asks whether an RFP 'no single-point failure' clause re-bases it", fs="TBD_OWNER",
      adv=["official RFP (owner row 1) and owner answer RVMQ-01"])

    # ---------------- power budget
    P(rows, "AFC-SY-PWR-01", S, "power_budget", "RFP bus-power gate P_bus,1ms,max (steady and start-up)",
      busv("A902-01"), units="W (strict <)", tolerance=T_RULE, ec="requirement-as-recorded",
      sources=[bus("A902-01"), bus("A902-03"), ref("MP2", "/power/gate"), ans(108)],
      basis="owner row 108; A9.1 OQ-A902-01 1 ms window", fs="OPEN", label="REQUIREMENT_AS_RECORDED",
      adv=["official RFP wording (owner row 1)"])
    P(rows, "AFC-SY-PWR-02", S, "power_budget", "internal design allocation (ICP fits inside; 1350 -> 1500 W margin "
      "not consumed nominally)", busv("A902-04"), units="W", tolerance=T_ALLOC, ec="owner-allocation",
      sources=[bus("A902-04"), ans(109)], basis="owner row 109", fs="FREEZE_CANDIDATE", label="ALLOCATION")
    P(rows, "AFC-SY-PWR-03", S, "power_budget", "common allocation (compressor, flow control, thermal, housekeeping) "
      "incl. 50 W controls / thermal", {"common_W": busv("A902-07"), "controls_thermal_W": busv("A902-08")},
      units="W", tolerance=T_ALLOC, ec="owner-allocation", sources=[bus("A902-07"), bus("A902-08"), ans(114)],
      basis="owner row 114 (upper design allocation, not a measured load)", fs="FREEZE_CANDIDATE", label="ALLOCATION")
    P(rows, "AFC-SY-PWR-04", S, "power_budget", "Hall + electron-source envelope at the common upper value",
      busv("A902-10"), units="W", tolerance=T_ALLOC, ec="model-derived",
      ec_note="allocation arithmetic 1350 - 300 - 0, not a prediction and not a sub-allocation",
      sources=[bus("A902-10"), bus("A902-20")], basis="A9.1 OQ-A902-03: no fixed Hall / ICP split", fs="OPEN",
      label="ALLOCATION", adv=["registered H-1 envelope and measured ICP power (P1 C_e,DC)"])
    st = get("MP2", "/power/configurations/hall_icp_neutralizer/phases/steady")
    P(rows, "AFC-SY-PWR-05", S, "power_budget", "P_bus ledger (steady)",
      {"ledger_status": st["ledger_status"], "P_bus_W": st["P_bus_W"], "P_bus_lower_bound_W": st["P_bus_lower_bound_W"],
       "tbd_count": st["tbd_count"]},
      units="W", tolerance="TBD", ec="model-derived", ec_note="ledger arithmetic over booked loads; 22 loads TBD",
      sources=[ref("MP2", "/power/configurations/hall_icp_neutralizer/phases/steady"),
               ref("RVM", find("RVM", "/rows", "id", "RVM-04") + "/configurations/hall_icp_neutralizer")],
      basis="mass_power v2 (A9-02 boundary)", fs="TBD_AFTER_EVIDENCE",
      adv=["every installed slot load and efficiency at a registered condition", "conformant 1 ms gate measurement"])
    P(rows, "AFC-SY-PWR-06", S, "power_budget", "compressor bus draw (parametric lower-bound booking)",
      {"kind": "PARETO_SET", "nominal_pareto_range_W": get("F78", "/system_evaluation/"
                                                                  "parametric_P_bus_lower_bound_W_range"),
       "official_ledger": busv("A902-30")},
      units="W", tolerance=T_PARAM, ec="model-derived", label="PARAMETRIC_SENSITIVITY",
      sources=[ref("F78", "/system_evaluation/parametric_P_bus_lower_bound_W_range"), bus("A902-30")],
      basis="F7 parametric ledger vs the official PARTIAL_BOUNDARY ledger (never merged)", fs="OPEN",
      adv=[T12, "measured compressor drive (ICD row 22)"])
    P(rows, "AFC-SY-PWR-07", S, "power_budget", "Hall discharge load", "TBD - requires the registered H-1 envelope "
      "and a measured flight-representative discharge supply (row 113); no Hall closure or 0-D number is used",
      units="W", tolerance="TBD", ec=None, sources=[bus("A902-32")], basis="A9-02", fs="TBD_AFTER_EVIDENCE",
      adv=[HALL_MAP])

    # ---------------- mass budget
    for line in get("MP2", "/lines/hall_icp_neutralizer"):
        ptr = find("MP2", "/lines/hall_icp_neutralizer", "line", line["line"])
        below = line["state"] == "ALLOCATION_BELOW_EVIDENCE_FLOOR"
        mq = {"AL-04": "MQ-03", "AL-07": "MQ-04", "AL-08": "MQ-05"}.get(line["line"])
        if below:
            assert mq, line["line"]
        P(rows, f"AFC-SY-MASS-{line['line']}", S, "mass_budget", f"dry allocation {line['line']} "
          f"{line['owner_name']}", line["allocation_kg"], units="kg", tolerance=T_ALLOC, ec="owner-allocation",
          sources=[ref("MP2", ptr), ans(54)],
          basis=f"owner row 54 v0 dry budget; line state {line['state']}; evidence floor "
                f"{line['evidence_floor_kg']} kg", fs="TBD_OWNER" if below else "OPEN", label="ALLOCATION",
          adv=([f"owner re-allocation ({mq})"] if below else []) + ["CBE or weighed article for every line item"])
    P(rows, "AFC-SY-MASS-WET", S, "mass_budget", "wet propulsion-system mass gate (incl. Xe + tank)",
      get("RVM", find("RVM", "/rows", "id", "RVM-06") + "/limit/value"),
      units="kg (strict <)", tolerance=T_RULE, ec="requirement-as-recorded",
      sources=[ref("RVM", find("RVM", "/rows", "id", "RVM-06")), ref("XE2", find("XE2", "/items", "id", "XV2-38"))],
      basis="RVM-06 (INCOMPLETE_EVIDENCE)", fs="OPEN", label="REQUIREMENT_AS_RECORDED",
      adv=["official RFP wording (owner row 1)"])
    P(rows, "AFC-SY-MASS-INT", S, "mass_budget", "internal design allocations",
      get("RVM", find("RVM", "/rows", "id", "RVM-07") + "/limit/value"), units="kg (wet)",
      tolerance=T_ALLOC, ec="owner-allocation", sources=[ans(53), ref("RVM", find("RVM", "/rows", "id", "RVM-07"))],
      basis="owner row 53 (both evaluated; 40 kg stays the hard limit)", fs="FREEZE_CANDIDATE", label="ALLOCATION")
    ro = [r for r in get("MP2", "/rollups") if r["configuration"] == CONFIGURATION]
    P(rows, "AFC-SY-MASS-ROLL", S, "mass_budget", "dry roll-ups (allocations / with evidence floors) under the open "
      "margin readings", {f"{r['reading']}|{r['basis']}": r["dry_known_kg"] for r in ro}, units="kg (dry, known part)",
      tolerance="n/a (roll-up of allocations and floors; no CBE)", ec="model-derived",
      ec_note="arithmetic over owner allocations and verified evidence floors; all_terms_resolved = false everywhere",
      sources=[ref("MP2", "/rollups"), ref("OQ4", find("OQ4", "/rows", "no", 251) + "/question")],
      basis="mass_power v2 roll-ups; MQ-01 / MQ-02 readings carried side by side", fs="TBD_OWNER",
      adv=["owner answers MQ-01, MQ-02, MQ-10", "CBE for every BOM line"],
      note="under the evidence-floor readings the dry mass alone can exceed 40 kg (MQ-10)")

    # ---------------- thermal interfaces (H-1 thermal rows come from F5 group TH)
    P(rows, "AFC-SY-TH-01", S, "thermal_interfaces", "ICP-module interface temperature margin rule",
      _icd("ICP-37")["value"], units="K (minimum margin) + 20 % heat-load margin", tolerance=T_RULE,
      ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-37")), ans(86)],
      basis="owner rows 86, 131", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-TH-02", S, "thermal_interfaces", "ICP RF-path heat allocation term (RF only, partial)",
      _icd("ICP-36")["value"], units="W", tolerance=T_ALLOC, ec="owner-allocation",
      ec_note="500 W laboratory capability x 1.2 heat-load margin; an allocation term, not a bound on the module heat",
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-36"))], basis="ICD ICP-36 DERIVED_ALLOCATION_TERM",
      fs="OPEN", label="ALLOCATION", adv=["total module heat load ICP-43 from P1 / P2 / Phase-1 data"])
    P(rows, "AFC-SY-TH-03", S, "thermal_interfaces", "total ICP module heat load (RF + discharge path + plume)",
      "TBD - ICD ICP-43", units="W", tolerance="TBD", ec=None,
      sources=[ref("ICD", find("ICD", "/items", "id", "ICP-43")), ref("P3", "/heat_terms")],
      basis="P3 heat terms Q_RF/match, Q_collector, Q_plume, Q_Hall->ICP", fs="TBD_AFTER_EVIDENCE",
      adv=["P1 / P2 heat terms and Phase-1 plume data"])
    P(rows, "AFC-SY-TH-04", S, "thermal_interfaces", "ICP cooling provision", _icd("ICP-38")["value"], units="-",
      tolerance=T_RULE, ec="assumed", ec_note="PROPOSED", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-38")),
                                                                ref("MP2", find("MP2", "/bom", "id", "MPV2-N05"))],
      basis="active cooling only if passive closure fails (A9.2 anode_approach; MPV2-N05 VARIANT_ONLY)",
      fs="TBD_AFTER_EVIDENCE", adv=["coupled thermal closure (P3)"])
    P(rows, "AFC-SY-TH-05", S, "thermal_interfaces", "anode thermal closure status",
      get("P3", "/closure_statuses/ANODE_THERMAL_CLOSURE"), units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ref("P3", "/closure_statuses/ANODE_THERMAL_CLOSURE"),
               ref("A92", "/decisions/a9_10_statuses/anode thermal closure")],
      basis="A9.2 status", fs="TBD_AFTER_EVIDENCE", label="RULE",
      adv=["P3 network solved with the anode heat path (A9.2 sec. 4) and Phase-1 deposited power fraction"],
      note="never reported as PASS")
    P(rows, "AFC-SY-TH-06", S, "thermal_interfaces", "compressor / plenum thermal interface",
      "TBD - compressor lumped node and isothermal 350 K chain are code defaults (F3 thermal_basis, F4-P-01)",
      units="K; W/K", tolerance="TBD", ec=None, sources=[ref("F3", "/thermal_basis"),
                                                         ref("F4", find("F4", "/items", "id", "F4-P-01"))],
      basis="UPSTREAM_ICD G-07", fs="TBD_AFTER_EVIDENCE", adv=["H2-5 thermal network extension to the gas path"])

    # ---------------- control / start sequence
    steps = get("MP2", "/power/configurations/hall_icp_neutralizer/phases/startup/steps")
    P(rows, "AFC-SY-CTL-01", S, "control_start", "start-up sequence (hall_icp_neutralizer)",
      [f"{s['step_id']} {s['name']}" for s in steps], units="-", tolerance=T_RULE, ec="assumed",
      ec_note="PROPOSED sequence template (row 112); sequence_status RULES_NOT_EVALUABLE (no measured transient)",
      sources=[ref("MP2", "/power/configurations/hall_icp_neutralizer/phases/startup"), ans(112), ans(24)],
      basis="A9-02 SEQUENCE_TEMPLATES (PROPOSED)", fs="TBD_OWNER",
      adv=["owner acceptance of the template at LOCK-1", "measured start-up transient record (1 ms gate)"])
    P(rows, "AFC-SY-CTL-02", S, "control_start", "enforced ordering (hall_icp_neutralizer)",
      get("BUS", "/sequencing/enforced_order/hall_icp_neutralizer"), units="-", tolerance=T_RULE,
      ec="owner-allocation", sources=[ref("BUS", "/sequencing/enforced_order/hall_icp_neutralizer")],
      basis="A9.1 SEQ rules", fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-CTL-03", S, "control_start", "peak sequencing rule", busv("A902-42"), units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[bus("A902-42")], basis="A9.1 SEQ-peaks",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-CTL-04", S, "control_start", "plenum pressure control and transient-quality metric basis",
      "TBD - setpoint policy OQ-F4-01 and metric definitions (2 % band, 60 s window, E0..E7 event sequence) "
      "OQ-F4-03", units="-", tolerance="TBD", ec=None,
      sources=[ref("F4", find("F4", "/open_owner_questions", "id", "OQ-F4-03")), ref("F4", "/metric_definitions")],
      basis="F4", fs="TBD_OWNER", adv=["owner answers OQ-F4-01, OQ-F4-03"])
    P(rows, "AFC-SY-CTL-05", S, "control_start", "ICP commands, states and start records", "TBD - ICD ICP-35 (LOCK-1)",
      units="-", tolerance="TBD", ec=None, sources=[ref("ICD", find("ICD", "/items", "id", "ICP-35"))],
      basis="ICD", fs="TBD_AFTER_EVIDENCE", adv=["ICP module design and P1 start data"])
    P(rows, "AFC-SY-CTL-06", S, "control_start", "ICP telemetry list", _icd("ICP-34")["value"], units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[ref("ICD", find("ICD", "/items", "id", "ICP-34"))],
      basis="ICD ICP-34 OWNER_GIVEN", fs="FREEZE_CANDIDATE", label="RULE")

    # ---------------- Xe functionality
    def xe(iid):
        return ref("XE2", find("XE2", "/items", "id", iid))

    def xev(iid):
        return get("XE2", find("XE2", "/items", "id", iid) + "/value")

    P(rows, "AFC-SY-XE-01", S, "xe", "Xe functional scope", "bounded functional Xe-capable operating mode (beyond "
      "bookkeeping); events, duration and flow TBD", units="-", tolerance=T_RULE, ec="owner-allocation",
      sources=[ans(6), xe("XV2-18"), ref("RVM", find("RVM", "/rows", "id", "RVM-10"))],
      basis="owner row 6; RVM-10 NOT_EVALUATED", fs="TBD_AFTER_EVIDENCE", label="RULE",
      adv=["mission mode profile (XV2-18 events / duration / flow)", "demonstrated Xe-capable H-1 operation"])
    P(rows, "AFC-SY-XE-02", S, "xe", "ICP dedicated Xe in the primary gas mode (G-REUSE)", xev("XV2-21"),
      units="mg/s (exact zero)", tolerance=T_RULE, ec="owner-allocation", sources=[xe("XV2-21"),
                                                                              ref("XE2", "/cases/CASE-1")],
      basis="owner decision: Hall exhaust is never counted again as ICP propellant", fs="FREEZE_CANDIDATE",
      label="RULE")
    P(rows, "AFC-SY-XE-03", S, "xe", "Xe design cases for tank / interface sizing", xev("XV2-30"), units="kg",
      tolerance=T_ALLOC, ec="owner-allocation",
      sources=[xe("XV2-30"), ans(48), ref("OQ4", find("OQ4", "/rows", "no", 284) + "/question")],
      basis="owner row 48 (no single mission load frozen); content LOADED vs USABLE is TBD_OWNER", fs="TBD_OWNER",
      label="ALLOCATION", adv=["owner answers OQ-A910-01 / XA9Q-01 / MQ-09"])
    P(rows, "AFC-SY-XE-04", S, "xe", "reserve and residual fractions", {"reserve": xev("XV2-23"),
                                                                        "residual": xev("XV2-24")},
      units="-", tolerance=T_ALLOC, ec="owner-allocation", sources=[xe("XV2-23"), xe("XV2-24")],
      basis="XV2-23 ASSUMED_ENGINEERING_ALLOCATION; XV2-24 OWNER_BASIS", fs="OPEN", label="ALLOCATION",
      adv=["measured mission mode profile (reserve revisit)"])
    P(rows, "AFC-SY-XE-05", S, "xe", "Xe storage temperature for tank sizing", xev("XV2-25"), units="K",
      tolerance=T_RULE, ec="owner-allocation", sources=[xe("XV2-25")], basis="OWNER_BASIS",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-XE-06", S, "xe", "Xe tank MEOP and proof / burst factors", "TBD - XV2-28 / XV2-29", units="MPa; -",
      tolerance="TBD", ec=None, sources=[xe("XV2-28"), xe("XV2-29")], basis="Xe accounting v2",
      fs="TBD_AFTER_EVIDENCE", adv=["tank selection (A9-09 RFQ) and design case content (OQ-A910-01)"])
    P(rows, "AFC-SY-XE-07", S, "xe", "stored-Xe subsystem screening cap (share of 40 kg)", xev("XV2-39"), units="-",
      tolerance=T_RULE, ec="owner-allocation", sources=[xe("XV2-39")], basis="SCREENING_CAP (not an entitlement)",
      fs="FREEZE_CANDIDATE", label="RULE")
    P(rows, "AFC-SY-XE-08", S, "xe", "Xe hardware evidence floor vs AL-08 allocation",
      {"AL-08_allocation_kg": get("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-08") +
                                  "/allocation_kg"),
       "evidence_floor_kg": get("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-08") +
                                "/evidence_floor_kg")},
      units="kg", tolerance=T_ALLOC, ec="model-derived", ec_note="H2-7 analog floor arithmetic (verified)",
      sources=[ref("MP2", find("MP2", "/lines/hall_icp_neutralizer", "line", "AL-08")),
               ref("OQ4", find("OQ4", "/rows", "no", 246) + "/question")],
      basis="mass_power v2 AL-08 ALLOCATION_BELOW_EVIDENCE_FLOOR", fs="TBD_OWNER", adv=["owner answer MQ-05"])


# --------------------------------------------------------------------------------------------------------------------
# architecture-level gates
# --------------------------------------------------------------------------------------------------------------------
def build_gates() -> list:
    gates = []

    def G(gid, name, status, sufficient: bool, blocking, sources, plan):
        assert sufficient is False or status not in ("NOT_EVALUATED", "UNRESOLVED", "OPEN", "EMPTY"), gid
        gates.append({"id": gid, "gate": name, "current_status": status, "evidence_sufficient_for_freeze": sufficient,
                      "blocking_evidence": blocking, "sources": sources, "evidence_plan_steps": plan})

    rvm_rows = []
    for i, r in enumerate(get("RVM", "/rows")):
        cfg = r["configurations"]
        rvm_rows.append({"id": r["id"], "title": r["title"], "requirement_frozen": r["requirement_frozen"],
                         "status": {c: cfg[c]["status"] for c in (CONFIGURATION, FALLBACK_CONFIGURATION)},
                         "rule": cfg[CONFIGURATION]["rule"], "blocking": cfg[CONFIGURATION]["reason"],
                         "source": ref("RVM", f"/rows/{i}/configurations")})
    counts = get("RVM", "/status_counts")
    assert all(counts[c]["PASS"] == 0 for c in counts), "an RVM row is PASS: re-assess AG-01 by hand"
    cstr = "; ".join(c + ": " + ", ".join(f"{k} {v}" for k, v in counts[c].items() if v) for c in counts)
    frozen = sum(r["requirement_frozen"] for r in rvm_rows)
    G("AG-01", f"RVM rows ({len(rvm_rows)} system requirements, both configurations)", cstr, False,
      {"rows": rvm_rows, "summary": f"no row is PASS ({cstr}); requirements frozen: {frozen} of {len(rvm_rows)} "
                                    "(official RFP not in the repository)"},
      [ref("RVM", "/status_counts"), ref("RVM", "/rfp_document_in_repository")],
      ["EP-01", "EP-02", "EP-03", "EP-10", "EP-11", "EP-12", "EP-13"])
    G("AG-02", "Hall credible transport set (admitted members)",
      "EMPTY (members = " + json.dumps(get("ENS", "/members")) + ")", False,
      "no admitted Hall transport closure: no design-specific Hall map exists, so thrust T, T - D, I_d,max, Hall "
      "discharge power and wall life are NOT_EVALUATED for every design vector",
      [ref("ENS", "/members"), ref("F78", "/unlock_evidence/T")], ["EP-02", "EP-10", "EP-11"])
    G("AG-03", "P5-N2 v1 validation outcome", "INCONCLUSIVE (permanent; promotable = "
      + json.dumps(get("VAL", "/decision/promotable")) + ")", False,
      "v1 stays INCONCLUSIVE and is never rewritten; promotion needs genuinely new predictive evidence not used in "
      "selection (held-out hardware data, hardware pivot)", [ref("VAL", "/decision")], ["EP-10"])
    G("AG-04", "ICP-45 electron-current capacity (I_e,cap vs I_d,max,H1)",
      get("A92", "/decisions/a9_10_statuses/ICP electron-current capacity") + "; ICP45 NOT_EVALUATED", False,
      "I_d,max,H1 not registered (needs measured H-1 operation); no P1 data (P1 plan ENGINEERING_TEST_PLAN_DRAFT_NOT_"
      "SCORE_BEARING)", [ref("A92", "/decisions/a9_10_statuses/ICP electron-current capacity"),
                         ref("ICD", find("ICD", "/items", "id", "ICP-45")), ref("P1", "/status"),
                         ref("F78", "/unlock_evidence/I_e_margin")], ["EP-02", "EP-03"])
    G("AG-05", "coupled H-1 / ICP thermal closure",
      get("A92", "/decisions/a9_10_statuses/coupled H-1~1ICP thermal closure"), False,
      "P3 framework inputs TBD: ICP geometry P3-G-01..08, emittances, conductances, Q_RF/match and Q_collector from "
      "P1 / P2, Q_plume from Phase-1; no thermal PASS from a negligible-coupling calculation (A9.2)",
      [ref("P3", "/closure_statuses"), ref("A92", "/decisions/icp_coupled_thermal"),
       ref("F78", "/unlock_evidence/Q_reject")], ["EP-03", "EP-04", "EP-05", "EP-06"])
    G("AG-06", "anode thermal closure", get("A92", "/decisions/a9_10_statuses/anode thermal closure"), False,
      "anode heat-removal path design (A9.2 sec. 4 investigation list) and the measured deposited discharge-power "
      "fraction", [ref("P3", "/closure_statuses/ANODE_THERMAL_CLOSURE"), ref("A92", "/decisions/anode_approach")],
      ["EP-02", "EP-06"])
    G("AG-07", "final anode material", get("A92", "/decisions/a9_10_statuses/final anode material"), False,
      "P4: no candidate has gate-admissible evidence (all gate cells INCOMPLETE_EVIDENCE); 316L "
      "REJECTED_AS_CURRENT_BASELINE", [ref("P4", "/fixed_statuses"), ref("P4", find_text(
          "P4", "/findings", "352 gate cells"))], ["EP-07", "EP-06"])
    G("AG-08", "RF component ratings", get("A92", "/decisions/a9_10_statuses/RF component ratings"), False,
      "P2 impedance map not run (PREPARATION_ONLY_NOT_RUN; waits for the P1 stable region)",
      [ref("A92", "/decisions/a9_10_statuses/RF component ratings"), ref("P2", "/status")], ["EP-03", "EP-04"])
    G("AG-09", "ICP RF power closure", get("A92", "/decisions/a9_10_statuses/ICP RF power closure"), False,
      "measured C_e,DC at the ICP-45 point with a flight-representative DC-input RF source",
      [ref("A92", "/decisions/a9_10_statuses/ICP RF power closure"), ref("BUS", find("BUS", "/items", "id",
                                                                                     "A902-21"))],
      ["EP-03", "EP-04", "EP-13"])
    n_tbd = get("MP2", "/power/configurations/hall_icp_neutralizer/phases/steady/tbd_count")
    G("AG-10", "bus-power closure (P_bus,1ms,max < 1500 W, steady and start-up)",
      get("MP2", "/power/configurations/hall_icp_neutralizer/phases/steady/ledger_status"), False,
      f"{n_tbd} booked loads TBD; no conformant gate measurement", [ref("MP2", "/power/configurations/hall_icp_neutralizer/"
                                                                        "rfp_gate_1ms"),
                                                              ref("F78", "/unlock_evidence/P_bus")],
      ["EP-02", "EP-03", "EP-08", "EP-13"])
    below = [ln["line"] for ln in get("MP2", "/lines/hall_icp_neutralizer")
             if ln["state"] == "ALLOCATION_BELOW_EVIDENCE_FLOOR"]
    G("AG-11", "mass closure (< 40 kg wet)", "INCOMPLETE_EVIDENCE (no CBE; " + " / ".join(below) + " below evidence "
      "floors)", False, "a CBE or measured mass for every BOM line; owner answers MQ-01..MQ-10",
      [ref("RVM", find("RVM", "/rows", "id", "RVM-06") + "/configurations/hall_icp_neutralizer"),
       ref("F78", "/unlock_evidence/m_wet")], ["EP-12"])
    wc = [m["mdot_delivered_min_kgps"] * 1e6 for b in get("F78", "/robust/robust_pareto_by_P_set").values()
          for m in b["members"]]
    n_f3 = len(get("F3", "/strict_mode/blockers"))
    G("AG-12", "upstream delivered-flow closure (UG-FLOW, proposed F9 gate)",
      "NOT_EVALUATED (strict mode); parametric frontier below the owner characterization range", False,
      f"all-state frontier 0.1027382 mg/s (single setpoint) and robust worst case {_rng(wc)} mg/s under parametric "
      "inputs vs 0.38-3.2 mg/s characterization and ~1.3 mg/s nominal sizing (row 73); compressor coefficients "
      f"uncited (F3 MODE_STRICT {n_f3} blockers), accommodation TBD, filter TBD; the delivered-flow requirement "
      "itself is not set (F9-OQ-02)", [ref("F4", "/strict_mode"), cite("F3", "/strict_mode/status", "NOT_EVALUATED"),
                     cite("F78", find("F78", "/findings", "id", "F78-02"), "0.1027382")], ["EP-08", "EP-09", "EP-14"])
    G("AG-13", "drag compensation T - D_spacecraft", "NOT_EVALUATED", False,
      "thrust (AG-02) and spacecraft body / array drag (no spacecraft geometry; OQ-F78-04); whether HC-08 is a hard "
      "constraint is OQ-F78-01", [ref("F78", "/unlock_evidence/D_spacecraft"),
                                  ref("F78", find("F78", "/hard_constraints", "id", "HC-08"))],
      ["EP-11", "EP-15"])
    G("AG-14", "H-1 engineering article", get("F5", "/article_freeze_state"), False,
      "channel design point (H1F-CH-11 TBD_OWNER), FEMM of MC-1, B(z) evidence, anode closure",
      [ref("F5", "/article_freeze_state"), ref("F5", "/freeze_rollup")], ["EP-05", "EP-06", "EP-07"])
    G("AG-15", "requirement basis (official RFP document)", "NOT_IN_REPOSITORY (secondary transcriptions only)",
      False, "owner rows 1-2: obtain the canonical RFP; freeze no interpretation from secondary sources",
      [ref("RVM", "/rfp_document_in_repository"), ans(1)], ["EP-01"])
    return gates


def architecture_status(gates: list) -> str:
    if gates and all(g["evidence_sufficient_for_freeze"] for g in gates):
        return "FROZEN_REFERENCE_FLIGHT_ARCHITECTURE"
    return "INVESTIGATION_HYPOTHESIS"


EVIDENCE_PLAN = [
    ("EP-01", "obtain the official RFP document (owner rows 1-2) and re-base the RVM requirement texts",
     ["AG-15", "AG-01"], [], "owner / legitimate portal route"),
    ("EP-02", "Phase-1 H-1 operation on N2 (hardware pivot): Hall-only sustainment knee; register I_d,max,H1, "
              "deposited anode power fraction and inlet conductance on the built article",
     ["AG-04", "AG-06", "AG-10", "AG-01"], ["EP-05"], "hardware pivot Phase 1 (OD 2026-09-27)"),
    ("EP-03", "P1 ICP bench: ICP-45A discharge-OFF capacity I_e,cap (Ar engineering, then N2), C_e and C_e,DC",
     ["AG-04", "AG-08", "AG-09", "AG-05"], [], "docs/experiments/hall_icp/p1_icp_bench/"),
    ("EP-04", "P2 impedance map Z_antenna = f(P_RF, mdot, p, gas, plasma state) in the P1 stable region; RF ratings "
              "and flight matching implementation", ["AG-08", "AG-09", "AG-05"], ["EP-03"],
     "docs/experiments/hall_icp/p2_impedance_map/"),
    ("EP-05", "FEMM-class magnetostatics of MC-1 at analysis points (F5-OQ-01) and the owner channel design point "
              "(F5-OQ-02); stray field in the ICP region", ["AG-14", "AG-05"], [],
     "docs/hardware/h1_freeze_candidate/ (F5)"),
    ("EP-06", "P3 coupled H-1 / ICP thermal network solved with the ICP geometry, P1 / P2 heat terms and Phase-1 "
              "plume data, including the anode heat path", ["AG-05", "AG-06", "AG-14"], ["EP-02", "EP-03", "EP-04",
                                                                                          "EP-05"],
     "docs/experiments/hall_icp/p3_coupled_thermal/"),
    ("EP-07", "P4 coupon programme (biased + floating, O / AO) for the anode and collector candidates with "
              "pre-registered acceptance", ["AG-07", "AG-14"], ["EP-06"], "docs/experiments/hall_icp/p4_anode_materials/"),
    ("EP-08", "compressor tests T-1 / T-2 (turbo ln K0, pumping speed) and T-4 / T-7 on the built rotor; decision on "
              "the regime above 0.1 Pa (OQ-F3-03)", ["AG-12", "AG-10"], [],
     "docs/architecture_comparison/compressor_downselect/"),
    ("EP-09", "measured intake-surface accommodation (DI-1.3) and, if authorized, frozen intake surface v2 (F1Q-04)",
     ["AG-12"], [], "docs/design_synthesis/f1_intake/ (F1)"),
    ("EP-10", "pre-registered held-out Hall-transport validation on new hardware data (P5-N2 v1 unchanged); admit a "
              "closure only by predictive evidence, then design-specific H-1 maps", ["AG-02", "AG-03"], ["EP-02"],
     "hallthruster_bridge/ (pivot validation prereg)"),
    ("EP-11", "measured H-1 thrust on the delivered feed (thrust stand, Phase 2-3) under P_bus < 1.5 kW",
     ["AG-02", "AG-13", "AG-01"], ["EP-02", "EP-03"], "hardware pivot Phase 3"),
    ("EP-12", "CBE (then weighed articles) for every mass/power v2 BOM line; owner answers MQ-01..MQ-10",
     ["AG-11", "AG-01"], ["EP-05", "EP-06"], "docs/budgets/mass_power_a9_v2/"),
    ("EP-13", "conformant P_bus,1ms,max gate measurement over the start-up sequence and steady state",
     ["AG-10", "AG-09", "AG-01"], ["EP-02", "EP-03", "EP-08"], "A9-02 bus boundary"),
    ("EP-14", "owner sets the delivered-flow requirement at the H-1 inlet (F9-OQ-02) and the lever for the flow gap "
              "(OQ-F4-04)", ["AG-12"], [], "owner"),
    ("EP-15", "spacecraft frontal geometry / drag basis (OQ-F78-04) and the T - D constraint definition (OQ-F78-01)",
     ["AG-13"], [], "owner / spacecraft ICD"),
]


def evidence_plan(gates: list) -> list:
    gids = {g["id"] for g in gates}
    out = []
    for sid, what, closes, deps, vehicle in EVIDENCE_PLAN:
        assert set(closes) <= gids, sid
        out.append({"id": sid, "evidence": what, "addresses_gates": closes, "depends_on": deps, "vehicle": vehicle})
    covered = {g for s in out for g in s["addresses_gates"]}
    assert covered == gids, f"gates without an evidence step: {gids - covered}"
    for g in gates:
        assert set(g["evidence_plan_steps"]) <= {s["id"] for s in out}, g["id"]
    return out


# --------------------------------------------------------------------------------------------------------------------
# model-change candidates (production-model issues found by A9.7 lanes)
# --------------------------------------------------------------------------------------------------------------------
def model_change_candidates() -> list:
    common = {"required": ["owner decision (authorize as a controlled model change, or keep the design-layer "
                           "workaround)", "docs/HISTORY.md entry (CLAUDE.md rules 1-2)",
                           "golden check after implementation; if goldens move, justify, regenerate, log"],
              "status": "MODEL_CHANGE_CANDIDATE_PENDING_OWNER", "implemented_here": False}
    out = [
        {"id": "MCC-01", "finding": "F1-01 intake species recombination",
         "module": "abep_sim/intake_tpmc.py IntakeSurface.__call__ (loaded via abep_sim/intake.py collection)",
         "issue": "species rows are recombined by MASS fraction although each row's C_D is normalised by the mixture "
                  "dynamic pressure and CR_passive is a number-density ratio (mole weighting applies)",
         "magnitude": get("F1", "/species_recombination_bias"),
         "golden_impact": "expected to move goldens (intake C_D / CR enter the production chain; F1Q-01)",
         "owner_question": "F1Q-01 (existing)",
         "sources": [ref("F1", find("F1", "/findings", "id", "F1-01")), ref("F1", "/species_recombination_bias"),
                     tref("MOD_TPMC", "class IntakeSurface:"), tref("MOD_INTAKE", "IntakeSurface(")]},
        {"id": "MCC-02", "finding": "F3-01 silent Gaede clipping",
         "module": "abep_sim/compressor.py DragCompressor._run_once",
         "issue": "K = max(min(K, K0), 1.0) hides an overloaded stage (throughput above S0 p): the module reports "
                  "K = 1 instead of a non-convergence / overload status (CLAUDE.md rule 3: no silent fallbacks)",
         "magnitude": "15552 of 15552 drag-stage design evaluations in F3 have an unclipped K < 1 (F3-01)",
         "golden_impact": "unknown: a status flag alone does not change values; refusing clipped states would move "
                          "any golden that passes through a clipped stage (to be checked at implementation)",
         "owner_question": "F9-OQ-04 (new)",
         "sources": [cite("F3", find("F3", "/findings", "id", "F3-01"), "15552 of 15552"),
                     ref("F3", find("F3", "/gates", "id", "GAEDE_CHARACTERISTIC_CLIPPED_THROUGHPUT_ABOVE_STAGE_"
                                                         "CAPACITY")),
                     tref("MOD_COMP", "K = max(min(K, K0), 1.0)")]},
        {"id": "MCC-03", "finding": "F3-02 uncited rotor allowable",
         "module": "abep_sim/compressor.py DragCompressor.u_max (rotor_ok) with abep_sim/materials.py DB yield",
         "issue": "the module's tip-speed cap uses an uncited DB yield (880 MPa for Ti-6Al-4V) and an uncited safety "
                  "factor 2.0; with the cited A-basis Fty 827 MPa the cap is 305.5 m/s vs the module's 315.2 m/s, so "
                  "size_for can return rotors the F3 search rejects",
         "magnitude": get("F3", find("F3", "/findings", "id", "F3-02") + "/finding"),
         "golden_impact": "possible (size_for results near the cap change); to be checked at implementation",
         "owner_question": "OQ-F3-01 (existing, allowable basis) + F9-OQ-04 (new, model change)",
         "sources": [cite("F3", find("F3", "/findings", "id", "F3-02"), "315.2 m/s", "880 MPa"),
                     tref("MOD_COMP", "stress_safety: float = 2.0"),
                     tref("MOD_COMP", "return math.sqrt(m.yield_MPa * 1e6 / (self.stress_safety * m.density))")]},
        {"id": "MCC-04", "finding": "F4 / UPSTREAM_ICD G-05 orifice sizing bracket",
         "module": "abep_sim/reservoir.py size_orifice_for_pressure",
         "issue": "60-step bisection in [1e-8, 3e-2] m^2 with no residual: an unreachable target returns the bracket "
                  "end with no flag; at low plenum targets the F4 A_eq exceeds 3e-2 m^2 (F4 does not use the routine "
                  "for sizing)",
         "magnitude": get("F4", "/checks/size_orifice_note"),
         "golden_impact": "none if only a convergence flag / residual is added; values unchanged (UPSTREAM_ICD "
                          "sec. 9 Q7)",
         "owner_question": "UPSTREAM_ICD sec. 9 question 7 (existing: convergence flags G-03 to G-05)",
         "sources": [ref("F4", "/checks/size_orifice_note"), tref("UICD", "| G-05 |"),
                     tref("UICD", "7. **Convergence flags (G-03 to G-05).**"),
                     tref("MOD_RES", "def size_orifice_for_pressure(")]},
    ]
    for d in get("RUST", "/documented_divergence"):
        out.append({"id": "MCC-0" + str(4 + int(d["id"][-1])), "finding": f"Rust parity {d['id']}",
                    "module": "abep_sim/intake_tpmc.py trace_channel / _cll (Python reference behaviour)",
                    "issue": d["statement"],
                    "magnitude": "outside the parity comparison set; no admitted kernel result depends on it",
                    "golden_impact": "none expected for valid inputs (input validation only); to be checked",
                    "owner_question": "F9-OQ-04 (new)",
                    "sources": [ref("RUST", find("RUST", "/documented_divergence", "id", d["id"])),
                                tref("MOD_TPMC", "def trace_channel(")]})
    for m in out:
        m.update(common)
    ids = [m["finding"] for m in out]
    for need in ("F1-01", "F3-01", "F3-02", "G-05", "DIV-01", "DIV-02", "DIV-03"):
        assert any(need in f for f in ids), need
    return out


# --------------------------------------------------------------------------------------------------------------------
# owner-question roll-up (never answered here)
# --------------------------------------------------------------------------------------------------------------------
A97_LANE_QUESTION_SOURCES = [
    ("F0", "F0", "/open_owner_questions"), ("F1", "F1", "/open_owner_questions"),
    ("F2", "F2", "/open_owner_questions"), ("F3", "F3", "/open_owner_questions"),
    ("F4", "F4", "/open_owner_questions"), ("F5", "F5", "/open_owner_questions"),
    ("F6", "F6", "/open_owner_questions"), ("F7/F8", "F78", "/open_owner_questions"),
    ("Rust kernels", "RUST", "/open_owner_questions"),
]

F9_QUESTIONS = [
    {"id": "F9-OQ-01",
     "question": "Pareto representative rule for the upstream chain: carry the robust Pareto set (9 members at P_set "
                 "0.01 Pa: intake A 0.25 m^2, L/d 3-5, phi 0.8-0.9; compressor T6-A1-U2-D0-Ti6Al4V; V 0.001-0.1 m^3) "
                 "to LOCK-1 as a set, or name a representative by an explicit rule (e.g. (a) maximum worst-case "
                 "delivered flow, ties by minimum plenum volume; (b) minimum ripple transfer; (c) defer until T-1 / "
                 "T-2 and DI-1.3 narrow the set)? No representative is selected by this lane.",
     "why_new": "A9.7 F9 allows a named representative only by an explicit rule that is itself an owner question",
     "needed_by": "LOCK-1", "status": "TBD_OWNER"},
    {"id": "F9-OQ-02",
     "question": "Set the delivered-flow requirement at the H-1 inlet that the proposed architecture gate AG-12 "
                 "(UG-FLOW) is scored against (owner row 73 gives a sizing flow ~1.3 mg/s and a characterization "
                 "range 0.38-3.2 mg/s, neither a flight requirement): which value, at which orbit states / averaging?",
     "why_new": "no requirement exists; F4 / F7 report a parametric all-state frontier of 0.1027 mg/s and OQ-F4-04 asks "
                "only which lever to study",
     "needed_by": "LOCK-1 (before any upstream freeze)", "status": "TBD_OWNER"},
    {"id": "F9-OQ-03",
     "question": "Approve the architecture-level gate list AG-01..AG-15 and the sufficiency criterion of each "
                 "(e.g. RVM rows PASS by a DETERMINING measurement vs a weaker 'evidence sufficient for freeze') "
                 "that moves the architecture from INVESTIGATION_HYPOTHESIS to FROZEN_REFERENCE_FLIGHT_ARCHITECTURE?",
     "why_new": "A9.7 F9 names the freeze rule but no register defines the gate set or its sufficiency criteria",
     "needed_by": "before Milestone B", "status": "TBD_OWNER"},
    {"id": "F9-OQ-04",
     "question": "Model-change candidates MCC-02 (silent Gaede clipping), MCC-03 (uncited rotor allowable in "
                 "rotor_ok) and MCC-05..MCC-07 (intake_tpmc reference: non-termination for max_hits < 1, silent "
                 "Maxwell fallback for an unknown kernel, NaN / raise for CLL alpha outside [0, 1]): authorize each "
                 "as a controlled model change (golden check, HISTORY entry), or keep the design-layer workarounds?",
     "why_new": "MCC-01 (F1Q-01) and MCC-04 (UPSTREAM_ICD Q7) already have owner questions; these five do not",
     "needed_by": "next production-model revision", "status": "TBD_OWNER"},
]


def owner_rollup() -> dict:
    v4 = []
    for i, r in enumerate(get("OQ4", "/rows")):
        if r["status"] != "TBD_OWNER":
            continue
        v4.append({"no": r["no"], "id": r["id"], "question": r["question"], "blocks": r.get("blocks"),
                   "dependency": r.get("dependency"), "status": r["status"],
                   "source": {"path": path_of("OQ4"), "pointer": f"/rows/{i}", "sha256": sha_of("OQ4")}})
    assert len(v4) == get("OQ4", "/tbd_owner_count"), "state v4 TBD_OWNER count mismatch"
    lanes = []
    for lane, key, ptr in A97_LANE_QUESTION_SOURCES:
        for j, q in enumerate(get(key, ptr)):
            lanes.append({"lane": lane, "id": q["id"], "question": q["question"],
                          "source": {"path": path_of(key), "pointer": f"{ptr}/{j}", "sha256": sha_of(key)}})
    other = [
        {"id": "UPSTREAM_ICD-Q7", "question": "Convergence flags (G-03 to G-05): the owner decides when to add them "
                                              "to the gas-path modules", "source": tref("UICD", "7. **Convergence "
                                                                                                "flags (G-03 to G-05).**")},
        {"id": "UPSTREAM_ICD-Q1", "question": "Filter (G-01): separate element with its own transmission on the "
                                              "production path, or lumped in the intake?",
         "source": tref("UICD", "1. **Filter (G-01).**")},
    ]
    return {"rule": "roll-up only: no question is answered here; state v4 TBD_OWNER rows are listed by their unique "
                    "row number 'no' (ids repeat across register generations)",
            "state_v4_tbd_owner": v4, "state_v4_tbd_owner_count": len(v4),
            "a9_7_lane_questions": lanes, "a9_7_lane_question_count": len(lanes),
            "other_existing_open_questions_cited": other,
            "new_f9_questions": [q["id"] for q in F9_QUESTIONS]}


# --------------------------------------------------------------------------------------------------------------------
def a92_statuses() -> dict:
    js = get("A92", "/decisions/a9_10_statuses")
    md = load("A92_MD")
    sec = md.split("9. A9-10 statuses", 1)[1].split("Do not convert", 1)[0]
    md_rows = {}
    for line in sec.splitlines():
        m = re.fullmatch(r"\|\s*(.+?)\s*\|\s*([A-Z0-9_]+)\s*\|", line.strip())
        if m and m[1] != "Item":
            md_rows[m[1].replace("→", "->")] = m[2]
    assert md_rows == js and len(js) == 10, "A9.2 statuses: Markdown table and JSON disagree"
    for key in ("F5", "F78"):
        carried = get(key, "/standing_facts/a9_2_statuses") if key == "F5" else get(
            key, "/robust/gates_after/a9_2_statuses")
        assert carried == js, f"{key} carries A9.2 statuses that differ from the pinned decision"
    return {"statuses": js, "source": [ref("A92", "/decisions/a9_10_statuses"),
                                       tref("A92_MD", "9. A9-10 statuses")],
            "rule": "verbatim (JSON keys; the Markdown table uses the arrow character for '->'); never converted to "
                    "PASS"}


def interface_demands() -> list:
    d = [
        ("F9-ID-01", "F1 -> F9", "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json (F1-ID-10)",
         "intake rows; none freezable from F1 (alpha, structure, pointing, p_ref TBD)", "CONSUMED"),
        ("F9-ID-02", "F2 -> F9", "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json",
         "filter interface, concept list, placeholder register; every real concept TBD", "CONSUMED"),
        ("F9-ID-03", "F3 -> F9", "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json",
         "compressor design grid, gates, findings F3-01 / F3-02 (model-change candidates MCC-02 / MCC-03)",
         "CONSUMED"),
        ("F9-ID-04", "F4 -> F9", "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json (F4-ID-13)",
         "plenum / valve / feed rows, conductance demand, offered feed-state records, G-05 note", "CONSUMED"),
        ("F9-ID-05", "F5 -> F9", "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json (IFS-F9-01)",
         "77 H-1 parameter rows imported unchanged (value, tolerance, class, freeze status)", "CONSUMED"),
        ("F9-ID-06", "F6 -> F9", "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json (F6-IF-S02)",
         "ICP geometry design-vector rows, all TBD", "CONSUMED"),
        ("F9-ID-07", "F7/F8 -> F9", "docs/design_synthesis/f7_f8_optimizer/ (F78-ID-16)",
         "upstream Pareto union and robust Pareto set; ranking REFUSED_INCOMPLETE; unlock map", "CONSUMED"),
        ("F9-ID-08", "F0 / Rust -> F9", "docs/performance/ (PERFORMANCE_BASELINE_98fbbb9.json, abep_core/parity_report_"
                                        "v1.json)", "owner questions F0-OQ-*, RUST-OQ-*; DIV-01..03 (MCC-05..07)",
         "CONSUMED"),
        ("F9-ID-09", "F9 -> F7/F8", "abep_sim/design/architecture_optimizer.py; robust_optimizer.py",
         "once F9-OQ-01 is answered, the representative rule (if any) is applied by the optimizer layer, not by F9; "
         "once F9-OQ-02 is answered, AG-12 needs a delivered-flow constraint in the upstream evaluation", "DEMANDED"),
        ("F9-ID-10", "F9 -> F4", "abep_sim/design/plenum_feed.py",
         "feed-state records at the H-1 inlet plane HALL_INLET_Z0 (not only IF-A4) once H1F-IN-04 exists", "DEMANDED"),
        ("F9-ID-11", "F9 -> F5", "docs/hardware/h1_freeze_candidate/",
         "exit-face channel OD (H1F-EX-04) and MC-1 stray field in the ICP volume (H1F-EX-05) for the ICP geometry "
         "bounds F6-X-01..04", "DEMANDED"),
        ("F9-ID-12", "F9 -> F6", "abep_sim/design/icp_geometry_synthesis.py",
         "bounds for F6-X-01..17 from the ICP module drawing or the P1 / P2 bench matrix (F6-OQ-02 / 03)", "DEMANDED"),
        ("F9-ID-13", "F9 -> consolidated verification (fo_a9_7_consolidated_verification)",
         "docs/architecture/freeze_candidate/", "verify the candidate table, gate list, roll-up and MCC register",
         "PROVIDED"),
    ]
    return [{"id": i, "direction": dr, "counterpart": c, "content": t, "status": s} for i, dr, c, t, s in d]


def build() -> dict:
    pins = verify_pins()
    us = upstream_sets()
    rows: list = []
    build_upstream(rows, us)
    build_h1_from_f5(rows)
    build_propulsion_icp(rows)
    build_system(rows)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate parameter ids"
    covered = {(r["section"], r["subsection"]) for r in rows}
    bullets_ok = {}
    for bullet, ss in A97_F9_BULLETS.items():
        assert bullet in load("A97_MD"), bullet
        assert ss in covered, ss
        bullets_ok[bullet] = list(ss)
    gates = build_gates()
    status = architecture_status(gates)
    plan = evidence_plan(gates)
    counts = {k: sum(r["freeze_status"] == k for r in rows) for k in FREEZE_STATUSES}
    by_sec = {}
    for r in rows:
        key = f"{r['section']}/{r['subsection']}"
        by_sec.setdefault(key, {k: 0 for k in FREEZE_STATUSES})[r["freeze_status"]] += 1
    rollup = owner_rollup()
    findings = [
        {"id": "F9-01", "evidence_class": "inferred",
         "finding": f"architecture status {status}: {sum(not g['evidence_sufficient_for_freeze'] for g in gates)} of "
                    f"{len(gates)} architecture-level gates lack sufficient evidence (none has it)"},
        {"id": "F9-02", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY inputs)",
         "finding": f"upstream Pareto: robust set {us['n_robust']} members (all at P_set 0.01 Pa, filter context none, "
                    f"compressor {', '.join(us['compressors'])}); nominal-context Pareto union {us['n_nominal_union']} "
                    f"members; carried as sets, no representative selected (F9-OQ-01)"},
        {"id": "F9-03", "evidence_class": "model-derived (PARAMETRIC_SENSITIVITY inputs)",
         "finding": "upstream flow gap: robust worst-case delivered flow "
                    f"{_rng([m['mdot_delivered_min_kgps'] * 1e6 for m in us['members']])} mg/s and all-state "
                    "frontier 0.1027 mg/s vs the owner characterization lower end 0.38 mg/s and nominal sizing ~1.3 "
                    "mg/s (row 73); not a FAIL (strict mode NOT_EVALUATED; requirement not set, F9-OQ-02)"},
        {"id": "F9-04", "evidence_class": "inferred",
         "finding": f"freeze-status roll-up over {len(rows)} parameters: {counts}; every FREEZE_CANDIDATE is an owner "
                    "decision, convention, rule or allocation; no computed performance value is a freeze candidate"},
        {"id": "F9-05", "evidence_class": "inferred",
         "finding": "7 production-model issues registered as model-change candidates (MCC-01..07); none implemented "
                    "here; each needs an owner decision and a HISTORY entry"},
        {"id": "F9-06", "evidence_class": "inferred",
         "finding": f"owner roll-up: {rollup['state_v4_tbd_owner_count']} state v4 TBD_OWNER rows, "
                    f"{rollup['a9_7_lane_question_count']} A9.7 lane questions (F0-F8, Rust), {len(F9_QUESTIONS)} new "
                    "F9 questions; none answered"},
    ]
    doc = {
        "schema": "architecture_freeze_candidate_v1",
        "id": "ARCHITECTURE_FREEZE_CANDIDATE_v1",
        "title": "A9.7 F9 architecture freeze candidate (one candidate definition; INVESTIGATION_HYPOTHESIS)",
        "lane": LANE,
        "directive": {"path": PINS["A97_MD"][0], "json": PINS["A97"][0], "section": "F9 - Architecture Freeze "
                                                                                     "Candidate"},
        "date": DATE,
        "base_commit": BASE_COMMIT,
        "generated_by": REL_SELF,
        "test": REL_TEST,
        "regenerate": f"python {REL_SELF}  (verify: --check)",
        "architecture_status": status,
        "frozen_reference_flight_architecture": status == "FROZEN_REFERENCE_FLIGHT_ARCHITECTURE",
        "freeze_rule": get("A97", "/summary/freeze_rule"),
        "deliverable_status": "FREEZE_CANDIDATE_DEFINITION (not frozen, not a design release, no winner, no PASS)",
        "configuration": {"primary": CONFIGURATION, "control_fallback": FALLBACK_CONFIGURATION,
                          "a9_status": get("A9", "/status"),
                          "rule": "the candidate is defined for the primary configuration; C1 rows that differ are "
                                  "carried by the cited deliverables (RVM / mass_power v2 / bus boundary) as the "
                                  "CONTROL_FALLBACK reference"},
        "what_this_is_not": [
            "not a frozen architecture and not FROZEN_REFERENCE_FLIGHT_ARCHITECTURE",
            "not a selection: Pareto sets are carried, no representative point is chosen (F9-OQ-01)",
            "no Hall performance number: credible Hall set empty, P5-N2 v1 INCONCLUSIVE; withdrawn 0-D results unused",
            "no PASS, no winner; no owner question answered",
            "no existing module, frozen dataset, decision, CLAUDE.md or HISTORY modified; not wired into archengine",
        ],
        "pins": pins,
        "consumed": {k: {"path": v, "sha256": sha_of(k)} for k, v in CONSUMED.items()},
        "freeze_status_vocabulary": FREEZE_STATUSES,
        "evidence_classes": list(EVIDENCE_CLASSES),
        "evidence_class_rule": "evidence_class describes what happened to the number (docs/EVIDENCE.md quantity type, "
                               "plus owner-allocation and requirement-as-recorded); null for a TBD value; qualifiers "
                               "go to evidence_note",
        "value_labels": VALUE_LABELS,
        "sections": SECTIONS,
        "a9_7_f9_coverage": bullets_ok,
        "standing_facts": {
            "credible_hall_set": "EMPTY", "p5_n2_v1": "INCONCLUSIVE", "hall_response_maps": "none admitted",
            "icp45": "NOT_EVALUATED", "p1_p2": "no data", "f7_full_system_ranking":
                get("F78", "/system_evaluation/ranking/hall_icp_neutralizer/status")},
        "a9_2_statuses": a92_statuses(),
        "upstream_pareto": {
            "robust_set": {"rule": get("F78", "/robust/rule"), "members": us["members"],
                           "per_member_f7_extremes": us["extra"], "n_members": us["n_robust"],
                           "n_all_scenario_feasible": us["n_all_scenario_feasible"],
                           "source": ref("F78", "/robust/robust_pareto_by_P_set")},
            "nominal_pareto_union": {"n_members": us["n_nominal_union"], "value_sets": us["union"],
                                     "source": ref("F7P", "/contexts"),
                                     "check": "equals the F8 survivor set (f8_robust_candidates_v1 rows)"},
            "representative": {"status": "TBD_OWNER", "owner_question": "F9-OQ-01", "selected": None},
            "label": "PARAMETRIC_SENSITIVITY",
        },
        "parameters": rows,
        "freeze_rollup": {"counts": counts, "by_subsection": by_sec, "total": len(rows)},
        "architecture_gates": gates,
        "evidence_plan": plan,
        "model_change_candidates": model_change_candidates(),
        "owner_question_rollup": rollup,
        "open_owner_questions": F9_QUESTIONS,
        "interface_demands": interface_demands(),
        "findings": findings,
        "m16_impact": [{"m16_row": None, "state_change": "none - F9 consolidates lane outputs into one candidate "
                                                         "definition; no evidence, requirement or gate status changes; "
                                                         "every M16 v4 row keeps its execution state"}],
        "compliance": {"existing_modules_modified": False, "frozen_data_modified": False,
                       "decisions_modified": False, "wired_into_archengine": False,
                       "tbd_converted_to_assumed_for_optimum": False, "single_optimum_or_winner_declared": False,
                       "pass_declared": False, "owner_question_answered": False, "julia_used": False,
                       "network_used": False, "deterministic": True, "new_pytest_skips": False},
    }
    return doc


# --------------------------------------------------------------------------------------------------------------------
# Markdown (generated from the JSON)
# --------------------------------------------------------------------------------------------------------------------
def _fmt(v, n=150) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def _src(srcs: list) -> str:
    out = []
    for s in srcs:
        loc = s.get("pointer") or s.get("locator", "")
        out.append(f"{s['path']}#{_fmt(loc, 60)}")
    return "; ".join(out)


def render_md(doc: dict) -> str:
    L = [f"# A9.7 F9 - architecture freeze candidate", "",
         f"Generated by `{doc['generated_by']}` from `architecture_freeze_candidate_v1.json` (do not edit by hand; "
         f"`--check` verifies). Base commit `{doc['base_commit']}`.", "",
         f"**Architecture status: {doc['architecture_status']}** (frozen reference flight architecture: "
         f"{str(doc['frozen_reference_flight_architecture']).lower()}). Freeze rule (A9.7): {doc['freeze_rule']}.", "",
         f"Configuration: primary `{doc['configuration']['primary']}`, control / fallback "
         f"`{doc['configuration']['control_fallback']}`. {doc['deliverable_status']}.", "",
         "## What this is not", ""]
    L += [f"- {x}" for x in doc["what_this_is_not"]]
    L += ["", "## A9.2 statuses (verbatim)", "", "| item | status |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in doc["a9_2_statuses"]["statuses"].items()]
    L += ["", "## Architecture-level gates", "",
          "| id | gate | current status | sufficient | evidence steps |", "|---|---|---|---|---|"]
    for g in doc["architecture_gates"]:
        L.append(f"| {g['id']} | {g['gate']} | {_fmt(g['current_status'], 120)} | "
                 f"{str(g['evidence_sufficient_for_freeze']).lower()} | {', '.join(g['evidence_plan_steps'])} |")
    L += ["", "Blocking evidence per gate:", ""]
    for g in doc["architecture_gates"]:
        b = g["blocking_evidence"]
        L.append(f"- **{g['id']}**: {_fmt(b['summary'] if isinstance(b, dict) else b, 400)}")
    rv = doc["architecture_gates"][0]["blocking_evidence"]["rows"]
    L += ["", "RVM rows (AG-01):", "", "| row | title | hall_icp_neutralizer | hall_c1_reference | frozen |",
          "|---|---|---|---|---|"]
    L += [f"| {r['id']} | {r['title']} | {r['status']['hall_icp_neutralizer']} | {r['status']['hall_c1_reference']} "
          f"| {str(r['requirement_frozen']).lower()} |" for r in rv]
    up = doc["upstream_pareto"]
    L += ["", "## Upstream Pareto sets (PARAMETRIC_SENSITIVITY)", "",
          f"Robust set ({up['robust_set']['n_members']} members; rule: {up['robust_set']['rule']}). Representative: "
          f"{up['representative']['status']} ({up['representative']['owner_question']}); none selected.", "",
          "| design id | worst-case delivered flow [mg/s] | intake drag [mN] | P_compressor [W] | m_compressor [kg] "
          "| V [m^3] | ripple transfer |", "|---|---|---|---|---|---|---|"]
    for m in up["robust_set"]["members"]:
        L.append(f"| `{m['design_id'].replace('|', ' / ')}` | {sig(m['mdot_delivered_min_kgps'] * 1e6, 4)} | "
                 f"{sig(m['drag_intake_max_N'] * 1e3, 4)} | {sig(m['P_compressor_el_max_W'], 4)} | "
                 f"{sig(m['m_compressor_max_kg'], 4)} | {m['V_m3']} | {sig(m['ripple_transfer_shaft'], 4)} |")
    vs = up["nominal_pareto_union"]["value_sets"]
    L += ["", f"Nominal-context Pareto union: {up['nominal_pareto_union']['n_members']} members "
              f"({up['nominal_pareto_union']['check']}):", ""]
    L += [f"- {k}: {', '.join(str(x) for x in v)}" for k, v in vs.items()]
    L += ["",
          "## Candidate definition", "",
          f"Freeze-status roll-up ({doc['freeze_rollup']['total']} parameters): "
          f"{_fmt(doc['freeze_rollup']['counts'], 200)}.", ""]
    for sec, subs in doc["sections"].items():
        L += [f"### {sec}", ""]
        for sub, title in subs.items():
            rows = [r for r in doc["parameters"] if r["section"] == sec and r["subsection"] == sub]
            L += [f"#### {title}", "", "| id | parameter | VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS |",
                  "|---|---|---|---|---|---|---|"]
            for r in rows:
                ec = r["evidence_class"] or "-"
                if r.get("value_label"):
                    ec += f" ({r['value_label']})"
                L.append(f"| {r['id']} | {_fmt(r['name'], 90)} | {_fmt(r['value'])} {_fmt(r['units'], 30)} | "
                         f"{_fmt(r['tolerance'], 50)} | {ec} | {_fmt(_src(r['source']), 160)} | {r['freeze_status']} |")
            L.append("")
    L += ["## Model-change candidates (owner decision + HISTORY entry required; none implemented)", "",
          "| id | finding | module | owner question | golden impact |", "|---|---|---|---|---|"]
    for m in doc["model_change_candidates"]:
        L.append(f"| {m['id']} | {m['finding']} | {_fmt(m['module'], 90)} | {m['owner_question']} | "
                 f"{_fmt(m['golden_impact'], 120)} |")
    L += ["", "## Minimal evidence plan (INVESTIGATION_HYPOTHESIS toward a frozen reference)", "",
          "| step | evidence | gates | depends on | vehicle |", "|---|---|---|---|---|"]
    for s in doc["evidence_plan"]:
        L.append(f"| {s['id']} | {_fmt(s['evidence'], 220)} | {', '.join(s['addresses_gates'])} | "
                 f"{', '.join(s['depends_on']) or '-'} | {s['vehicle']} |")
    ro = doc["owner_question_rollup"]
    L += ["", "## Owner-question roll-up (not answered here)", "", ro["rule"] + ".", "",
          f"### New F9 questions", ""]
    L += [f"- **{q['id']}** ({q['needed_by']}): {q['question']}" for q in doc["open_owner_questions"]]
    L += ["", f"### A9.7 lane questions ({ro['a9_7_lane_question_count']})", "", "| lane | id | question |",
          "|---|---|---|"]
    L += [f"| {q['lane']} | {q['id']} | {_fmt(q['question'], 260)} |" for q in ro["a9_7_lane_questions"]]
    L += ["", "Other existing open questions cited: " + "; ".join(
        f"{q['id']}: {q['question']}" for q in ro["other_existing_open_questions_cited"]), "",
          f"### State v4 TBD_OWNER ({ro['state_v4_tbd_owner_count']})", "", "| no | id | blocks | question |",
          "|---|---|---|---|"]
    L += [f"| {q['no']} | {q['id']} | {_fmt(q['blocks'], 40)} | {_fmt(q['question'], 200)} |"
          for q in ro["state_v4_tbd_owner"]]
    L += ["", "## Findings", ""]
    L += [f"- **{f['id']}** ({f['evidence_class']}): {f['finding']}" for f in doc["findings"]]
    L += ["", "## Interface demands", "", "| id | direction | counterpart | content | status |", "|---|---|---|---|---|"]
    L += [f"| {d['id']} | {d['direction']} | {d['counterpart']} | {_fmt(d['content'], 200)} | {d['status']} |"
          for d in doc["interface_demands"]]
    L += ["", "## M16 impact", ""] + [f"- {m['state_change']}" for m in doc["m16_impact"]]
    L += ["", "## Inputs", "", "Pinned (immutable, sha256 verified):", ""]
    L += [f"- `{v['path']}` {v['sha256']}" for v in doc["pins"].values()]
    L += ["", "Consumed (sha256 at build time; drift reported by `--check`):", ""]
    L += [f"- `{v['path']}` {v['sha256']}" for v in doc["consumed"].values()]
    return "\n".join(L) + "\n"


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify the committed JSON and MD are current")
    a = ap.parse_args(argv)
    doc = build()
    js, md = dumps(doc), render_md(doc)
    if a.check:
        bad = [p.name for p, t in ((JSON_PATH, js), (MD_PATH, md))
               if not p.is_file() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("STALE: " + ", ".join(bad) + f" (regenerate: python {REL_SELF})")
            return 1
        print(f"OK: {JSON_PATH.name} and {MD_PATH.name} are current ({doc['architecture_status']}, "
              f"{doc['freeze_rollup']['total']} parameters)")
        return 0
    LANE_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(js, encoding="utf-8")
    MD_PATH.write_text(md, encoding="utf-8")
    print(f"wrote {JSON_PATH.relative_to(REPO)} and {MD_PATH.relative_to(REPO)} ({doc['architecture_status']}, "
          f"{doc['freeze_rollup']['total']} parameters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
