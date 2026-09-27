"""H-1 Phase-1 pre-registration FRAMEWORK (fo_phase1_prereg_framework; docs/experiments/phase1_prereg_framework/).

Checks: byte-for-byte reproduction from sha256-pinned inputs (A5, A6 and the G0 record pinned; mutable governance never
pinned; tamper detected); all nine A6 decision quantities present with operational definition, measurement chain,
units, uncertainty source and a threshold whose value is the UNFROZEN literal; no numeric acceptance value anywhere (no
numeric JSON leaf, every threshold / tolerance / limit field is the literal, no comparator-number pattern, no
number-with-unit in the decision sections); gating sequence S1a -> LOCK-1 -> W5 freeze -> S1/S1b -> LOCK-2 -> Phase 1 in
order; order-balanced design (Williams set = all six permutations, position and first-order carryover balance, A5
naming order not the execution order); HW-0 reference repeats in every block; case logic A / B / C / NO_VIABLE_CASE with
no continuous Xe as a necessary condition of A and net P_bus benefit for B / C; same-condition, missing-data,
data-quality, remount and lock sections; milestone statement; INS / MS / S1 ids exist in the pinned inputs; bus
components match abep_sim/arch_boundary.py. Pure file checks plus one combinatorial function on synthetic seeds; no
simulator run, no Julia.
"""
from __future__ import annotations

import functools
import importlib.util
import itertools
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "experiments" / "phase1_prereg_framework"
UNFROZEN = "UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability"
CONFIGS = ("hall_only", "rf_hall", "ecr_hall")
A5_SHA = "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"
A6_SHA = "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"
G0_SHA = "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523"
A5_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0_REL = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
A6_NAMES = ["sustainment", "T/P_bus", "eta_u", "operating-envelope width", "ignition/restart behaviour",
            "stability/oscillation", "absolute thrust compatibility", "full bus-power compatibility",
            "no continuous Xe augmentation"]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_module("_test_phase1_prereg_builder", DIR / "build_phase1_prereg_framework.py")


@functools.lru_cache(maxsize=None)
def _doc() -> dict:
    return json.loads((DIR / "phase1_prereg_framework_v1.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _md() -> str:
    return (DIR / "PHASE1_PREREG_FRAMEWORK.md").read_text(encoding="utf-8")


def _walk(obj, path="$"):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")


# ------------------------------------------------------------------------------------------------ build / pins
def test_reproduces_byte_for_byte():
    outs = B.build_all()
    assert {p.relative_to(ROOT).as_posix() for p in outs} == {B.JSON_REL, B.MD_REL}
    for p, s in outs.items():
        assert p.read_text(encoding="utf-8") == s, p
    assert B.main(["--check"]) == 0


def test_outputs_only_in_allowed_paths():
    for p in B.build_all():
        assert p.relative_to(ROOT).as_posix().startswith("docs/experiments/phase1_prereg_framework/")


def test_a5_a6_g0_pinned_by_sha256():
    pins = {p["path"]: p["sha256"] for p in _doc()["pinned_inputs"]}
    assert pins[A5_REL] == A5_SHA
    assert pins[A6_REL] == A6_SHA
    assert pins[G0_REL] == G0_SHA
    assert B.PINNED[A5_REL] == A5_SHA and B.PINNED[A6_REL] == A6_SHA and B.PINNED[G0_REL] == G0_SHA
    g0 = json.loads((ROOT / G0_REL).read_text(encoding="utf-8"))
    assert g0["verdict"] == "CLEAN" and g0["a5_sha256"] == A5_SHA


def test_pins_verify_and_governance_never_pinned():
    assert B.verify_inputs() == B.PINNED
    pinned = {p["path"] for p in _doc()["pinned_inputs"]}
    for rel in ("docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/runtime_state.json"):
        assert rel not in pinned and rel not in B.PINNED
    assert not any(p.startswith("docs/orchestration/") for p in pinned)
    assert not any(p.startswith(B.PREIONIZER_ICD_PATH) for p in pinned)


def test_tampered_or_missing_input_raises(tmp_path):
    for rel in B.PINNED:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    old = B.ROOT
    try:
        B.ROOT = tmp_path
        assert B.verify_inputs() == B.PINNED
        with open(tmp_path / A6_REL, "a", encoding="utf-8") as f:
            f.write(" ")
        with pytest.raises(B.InputChanged):
            B.verify_inputs()
        shutil.copyfile(ROOT / A6_REL, tmp_path / A6_REL)
        (tmp_path / G0_REL).unlink()
        with pytest.raises(B.InputChanged):
            B.verify_inputs()
    finally:
        B.ROOT = old


# ------------------------------------------------------------------------------------------ decision quantities
def test_all_nine_a6_decision_quantities_present_in_order():
    a6 = json.loads((ROOT / A6_REL).read_text(encoding="utf-8"))
    text = a6["authorized_now"]["fo_phase1_prereg_framework"]
    for name in A6_NAMES:
        assert name in text
    dqs = _doc()["decision_quantities"]
    assert [q["a6_name"] for q in dqs] == A6_NAMES
    assert len({q["id"] for q in dqs}) == 9
    for q in dqs:
        assert q["operational_definition"].strip() and q["units"].strip()
        assert q["measurement_chain"] and all(re.fullmatch(r"INS-\d\d", c["ins_id"]) for c in q["measurement_chain"])
        assert any(c["role"] == "DECISIVE" for c in q["measurement_chain"])
        assert q["uncertainty_sources"]
        assert q["threshold"] == UNFROZEN
        assert q["threshold_depends_on"]
        assert all(d["stage"] in ("S1a", "S1b") and d["quantity"] and d["source"] for d in q["threshold_depends_on"])
        assert any(d["stage"] == "S1b" for d in q["threshold_depends_on"])


def test_every_threshold_tolerance_limit_is_unfrozen_literal():
    keys = {"threshold", "matching_tolerance", "limit", "re_run_cap"}
    seen = 0
    for path, v in _walk(_doc()):
        key = path.rsplit(".", 1)[-1]
        if key in keys:
            assert v == UNFROZEN, path
            seen += 1
    assert seen >= 9 + len(_doc()["same_condition"]["variables"]) + len(_doc()["data_quality"])
    assert _doc()["threshold_status_literal"] == UNFROZEN


def test_no_numeric_acceptance_value_anywhere():
    for path, v in _walk(_doc()):
        assert isinstance(v, (dict, list, str, bool)) or v is None, f"numeric leaf at {path}"
    comparator = re.compile(r"(<=|>=|≤|≥|<|>)\s*~?\s*\d")
    assert not comparator.search(_md())
    assert not comparator.search((DIR / "phase1_prereg_framework_v1.json").read_text(encoding="utf-8"))
    unit_num = re.compile(r"(?<![\w.\-])\d+(\.\d+)?(\s*-\s*\d+(\.\d+)?)?\s*(mN|kW|W|mg/s|mg|kg|%|Torr|Pa|V|A|eV|Hz|s|h)\b")
    d = _doc()
    for section in ("decision_quantities", "same_condition", "missing_data", "data_quality", "repeatability_remount",
                    "case_logic", "locks", "execution_design", "gating_sequence"):
        for path, v in _walk(d[section], section):
            if isinstance(v, str):
                assert not unit_num.search(v), (path, v)


# ---------------------------------------------------------------------------------------------- gating sequence
def test_gating_sequence_in_order_and_linked():
    seq = _doc()["gating_sequence"]
    assert [s["step"] for s in seq] == ["S1a", "LOCK-1", "W5 freeze", "S1/S1b", "LOCK-2", "Phase 1"]
    assert [s["score_bearing"] for s in seq] == [False] * 5 + [True]
    deliverables = " ".join(" ".join(s["deliverables"]) for s in seq)
    for rel in ("docs/experiments/s1a_readiness/", "docs/experiments/s1_readiness/",
                "docs/architecture_comparison/lock1/", "docs/experiments/capability_demo/",
                "docs/validation/hall_transport_v2_prereg/"):
        assert rel in deliverables
        assert (ROOT / rel).is_dir()
    s1 = next(s for s in seq if s["step"] == "S1/S1b")
    joined = " ".join(s1["contributes_to_thresholds"])
    for word in ("thrust uncertainty", "power uncertainty", "remount reproducibility", "noise", "pressure behaviour"):
        assert word in joined
    assert "S1a -> LOCK-1 -> W5 freeze -> S1/S1b -> LOCK-2 -> Phase 1" in _md()


# ------------------------------------------------------------------------------------------------ test matrix
def test_test_matrix_structure_from_a5():
    t = _doc()["test_matrix_structure"]
    assert [f["symbol"] for f in t["factors"]] == ["m_dot_atm", "x_O2", "V_d"]
    assert all(f["levels"].startswith("TBD") for f in t["factors"])
    prov = " ".join(p["what"] + " " + p["underlying"] for p in t["density_rule"]["provenance"])
    assert "0.42-0.60" in prov and "H_RAM" in prov
    a5 = json.loads((ROOT / A5_REL).read_text(encoding="utf-8"))
    assert "0.42-0.60" in a5["phase1_branch_decision"]["test_matrix"]
    assert any("P5 calibration nuisance" in x for x in t["never_axes"])


# -------------------------------------------------------------------------------------- order-balanced design
def test_order_balanced_design_is_williams_and_not_a5_order():
    e = _doc()["execution_design"]
    assert e["a5_naming_order_is_execution_order"] is False
    orders = [tuple(s["order"]) for s in e["sequences"]]
    assert set(orders) == set(itertools.permutations(CONFIGS)) and len(orders) == 6
    assert len(set(orders)) > 1
    assert orders.count(tuple(B.A5_NAMING_ORDER)) == 1
    pos = {}
    carry = {}
    for s in orders:
        for i, c in enumerate(s):
            pos[(i, c)] = pos.get((i, c), 0) + 1
        for a, b in zip(s, s[1:]):
            carry[(a, b)] = carry.get((a, b), 0) + 1
    assert len(set(pos.values())) == 1 and len(pos) == 9
    assert len(set(carry.values())) == 1 and len(carry) == 6 and all(a != b for a, b in carry)
    assert "NOT the score-bearing execution order" in e["clarification"]
    assert "LOCK-2" in e["randomization"]["seed"]
    assert B.PREIONIZER_ICD_PATH in e["module_exchange"]["interface_reference"]
    confounds = " ".join(c["confound"] for c in e["confounds"])
    for word in ("chamber conditioning", "wall", "cathode history", "magnet heating", "drift", "contamination",
                 "hysteresis"):
        assert word in confounds
    assert all(c["measured_by"] for c in e["confounds"])


def test_williams_construction_and_seeded_assignment_on_synthetic_seeds():
    assert B.is_position_balanced(B.SEQUENCES, CONFIGS) and B.is_carryover_balanced(B.SEQUENCES, CONFIGS)
    four = B.williams_sequences(("a", "b", "c", "d"))  # even count: one square suffices
    assert len(four) == 4 and B.is_carryover_balanced(four, ("a", "b", "c", "d"))
    synthetic_seed = "00deadbeef"  # clearly synthetic test seed, not a registration value
    sched = B.assign_sequences(12, synthetic_seed)
    assert sched == B.assign_sequences(12, synthetic_seed)
    assert sorted(sched) == sorted(list(B.SEQUENCES) * 2)
    assert sorted(B.assign_sequences(12, "0badc0de")) == sorted(sched)  # any seed keeps complete replicates
    with pytest.raises(ValueError):
        B.assign_sequences(4, synthetic_seed)
    with pytest.raises(ValueError):
        B.assign_sequences(6, "not-hex")
    with pytest.raises(ValueError):
        B.assign_sequences(0, synthetic_seed)


def test_hw0_reference_repeats_in_every_block():
    e = _doc()["execution_design"]
    tpl = e["block_template"]
    assert tpl[0]["slot"] == "HW0-REF-OPEN" and tpl[0]["configuration"] == "hall_only"
    assert tpl[-1]["slot"] == "HW0-REF-CLOSE" and tpl[-1]["configuration"] == "hall_only"
    assert [s["scored_for_branch_decision"] for s in tpl] == [False, True, True, True, False]
    h = e["hw0_reference_repeats"]
    assert h["present_in_every_block"] is True and h["configuration"] == "hall_only"
    assert any("DQR-03" in u for u in h["use"])


# ------------------------------------------------------------------------------------------------- case logic
def test_case_logic_outcomes_and_necessary_conditions():
    cl = _doc()["case_logic"]
    assert cl["outcomes"] == ["A", "B", "C", "NO_VIABLE_CASE"]
    assert cl["branch_of_outcome"] == {"A": "hall_only", "B": "rf_hall", "C": "ecr_hall", "NO_VIABLE_CASE": None}
    a5 = json.loads((ROOT / A5_REL).read_text(encoding="utf-8"))
    assert set(cl["a5_case_ids"].values()) == set(a5["phase1_branch_decision"]["cases"])
    rules = {r["outcome"]: r for r in cl["rules"]}
    assert "P1DQ-NOXE" in rules["A"]["necessary"]
    assert any("P1DQ-NOXE" in x for x in cl["definitions"]["PASS(X)"]["all_of"])
    for k in ("B", "C"):
        assert any("net system-level benefit at P_bus" in x for x in rules[k]["necessary"])
        assert "COMMON_BOUNDARY_CRITERION" in rules[k]["condition"]
    assert "NET_BENEFIT" in cl["definitions"]["COMMON_BOUNDARY_CRITERION(X)"]
    assert "bus_power_boundary_v1" in cl["definitions"]["NET_BENEFIT(X)"]
    assert "no case is forced to win" in rules["NO_VIABLE_CASE"]["necessary"]
    assert cl["current_outcome"].startswith("NOT_EVALUATED")
    assert "never an execution order" in cl["evaluation_precedence"]


def test_no_winner_and_bundle1_unchanged():
    d = _doc()
    assert d["context"]["bundle1_outcome"] == "NO_BASELINE_YET"
    assert d["context"]["credible_hall_set"].startswith("EMPTY")
    assert d["score_bearing"] is False and d["measurements_existing"] is False and d["not_locked"] is True
    text = json.dumps(d).lower()
    for bad in ("selected_branch", "winner is", "preferred architecture is", "eliminated:"):
        assert bad not in text


# ---------------------------------------------------------------------- same condition / missing data / quality
def test_same_condition_covers_required_groups():
    sc = _doc()["same_condition"]
    groups = {v["group"] for v in sc["variables"]}
    for g in ("feed state", "accelerator", "magnet", "cathode", "facility pressure", "thermal state"):
        assert g in groups
    assert all(v["matching_tolerance"] == UNFROZEN and v["tolerance_depends_on"] for v in sc["variables"])
    assert all(v["role"] in sc["roles"] for v in sc["variables"])
    assert sc["outcomes_not_matched"]


def test_missing_data_extinction_is_observation_and_no_post_hoc_exclusion():
    md = {r["id"]: r for r in _doc()["missing_data"]}
    assert "uncommanded extinction" in md["MD-01"]["event"]
    assert md["MD-01"]["classification"].startswith("OBSERVATION")
    assert "never missing data" in md["MD-01"]["rule"]
    assert any("NO POST HOC EXCLUSION" == r["classification"] for r in md.values())
    events = " ".join(r["event"] for r in md.values())
    for word in ("abort", "instrument failure", "extinction"):
        assert word in events


def test_data_quality_rules_present():
    dq = _doc()["data_quality"]
    checks = " ".join(r["check"] for r in dq)
    for word in ("instrument health", "calibration currency", "HW-0 reference", "background pressure"):
        assert word in checks
    assert all(r["limit"] == UNFROZEN and r["limit_depends_on"] and r["consequence"] for r in dq)


def test_repeatability_remount_and_locks():
    rr = {r["id"]: r for r in _doc()["repeatability_remount"]}
    assert "installation/removal reproducibility" in rr["RR-02"]["interface_items"]
    assert rr["RR-02"]["interface_reference"] == B.PREIONIZER_ICD_PATH
    lk = _doc()["locks"]
    conv = " ".join(r["s1_quantity"] for r in lk["lock2_converts"])
    for word in ("thrust uncertainty", "power uncertainty", "remount reproducibility", "drift", "stability / noise"):
        assert word in conv
    assert lk["lock1_fixes"] and "without discretion" in lk["rule"]


def test_relation_to_w5_and_modes_never_crossed():
    w = _doc()["relation_to_w5"]
    assert {f["family"] for f in w["held_out_from_phase1"]} == {"F1", "F2", "F3"}
    assert any("never crossed" in m for m in w["modes_never_crossed"])
    w5 = json.loads((ROOT / B.W5_REL).read_text(encoding="utf-8"))
    fams = {f["id"] for f in w5["condition_families"]["families"]}
    assert {f["family"] for f in w["held_out_from_phase1"] + w["not_held_out"]} <= fams


def test_milestone_statement():
    m = _doc()["milestones"]
    assert m["supports"] == "A" and "milestone A" in m["statement"]
    assert set(m["three_questions"]) == {"conditional_selection_now", "blocks_physics_backed_selection",
                                         "could_overturn"}
    assert "## 1. Milestone statement" in _md()
    fv = _doc()["frozen_vs_proposed"]
    assert any("nine decision quantities" in x for x in fv["owner_frozen"])
    assert "PROPOSED" in fv["proposed_topology"] and "UNFROZEN" in fv["unfrozen_numbers"]


# ---------------------------------------------------------------------------------------------- cross-checks
def test_referenced_ids_exist_in_pinned_inputs():
    text = json.dumps(_doc())
    ins = json.loads((ROOT / B.INS_REL).read_text(encoding="utf-8"))
    ins_ids = {i["id"] for i in ins["instruments"]} | {p["id"] for p in ins["procedures"]}
    for m in set(re.findall(r"\bINS-(?:P-)?\d\d\b", text)):
        assert m in ins_ids, m
    ms = json.loads((ROOT / B.MS_REL).read_text(encoding="utf-8"))
    ms_ids = {g["id"] for g in ms["general_requirements"]} | {x["id"] for x in ms["measurands"]}
    for m in set(re.findall(r"\bMS-[GM]-\d\d\b", text)):
        assert m in ms_ids, m
    lock1 = json.loads((ROOT / B.LOCK1_REL).read_text(encoding="utf-8"))
    rows = {r["id"] for r in lock1["s1_to_lock2"]["rows"]}
    for m in set(re.findall(r"\bS1-(?:0\d|1\d)\b", text)):
        assert m in rows, m


def test_bus_components_match_arch_boundary():
    ab = _load_module("_test_phase1_arch_boundary", ROOT / "abep_sim" / "arch_boundary.py")
    assert ab.BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert tuple(B.BUS_COMMON) == tuple(ab.COMMON_COMPONENTS)
    assert {k: tuple(v) for k, v in B.BUS_PREION.items()} == {k: tuple(v) for k, v in ab.PREIONIZER_COMPONENTS.items()}
    pbus = next(q for q in _doc()["decision_quantities"] if q["id"] == "P1DQ-PBUS")
    for comp in ab.ALL_COMPONENTS:
        assert comp in pbus["operational_definition"]
