"""A9-01 Hall -> downstream RF-ICP neutralizer pre-registration framework (docs/experiments/hall_icp/prereg_framework/).

Checks: byte-for-byte reproduction from sha256-pinned inputs (tamper and missing input detected; mutable governance never
pinned; historical artifacts unchanged); exact configuration ids and outcome vocabulary (OPEN is a status); stage map order
and evidence discipline (Ar engineering-only, AO separate, held-out freeze before any Hall-on reading, score-bearing only
after LOCK-2); decision quantities with the NOT SET margin literal and known instrument ids; no numeric leaf in the
decision/design sections; owner-given numbers cited by row with an evidence class; every cited row applied verbatim;
order-balance combinatorics on synthetic seeds; required sections (a)-(g). Pure file checks; no simulator, no Julia.
"""
from __future__ import annotations

import functools
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "experiments" / "hall_icp" / "prereg_framework"
BUILDER = DIR / "build_hall_icp_prereg_framework.py"
A9_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
A9_SHA = "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"
ANS_REL = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
ANS_SHA = "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"
C1, ICP = "hall_c1_reference", "hall_icp_neutralizer"
SYNTH_SEED_1 = "0" * 63 + "1"
SYNTH_SEED_2 = "f" * 64


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_module("_test_hall_icp_prereg_builder", BUILDER)


@functools.lru_cache(maxsize=None)
def _doc() -> dict:
    return json.loads((DIR / "hall_icp_prereg_framework_v1.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _md() -> str:
    return (DIR / "HALL_ICP_PREREG_FRAMEWORK.md").read_text(encoding="utf-8")


def _numeric_leaves(o, path=""):
    if isinstance(o, bool):
        return []
    if isinstance(o, (int, float)):
        return [path]
    if isinstance(o, dict):
        return [p for k, v in o.items() for p in _numeric_leaves(v, f"{path}/{k}")]
    if isinstance(o, list):
        return [p for i, v in enumerate(o) for p in _numeric_leaves(v, f"{path}[{i}]")]
    return []


def test_reproduces_byte_for_byte():
    js, md = B.render(ROOT)
    assert js == (DIR / "hall_icp_prereg_framework_v1.json").read_text(encoding="utf-8")
    assert md == _md()


def test_pins_governing_decision_and_answers():
    assert B.PINNED[A9_REL] == A9_SHA and B.PINNED[ANS_REL] == ANS_SHA
    d = _doc()
    assert d["owner_decision"] == {"path": A9_REL, "sha256": A9_SHA,
                                   "status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"}
    assert d["owner_answers"]["sha256"] == ANS_SHA
    for rel, sha in B.PINNED.items():
        assert B.sha256_file(ROOT / rel) == sha, rel


def test_tamper_and_missing_detected(monkeypatch):
    bad = dict(B.PINNED)
    bad[A9_REL] = "0" * 64
    monkeypatch.setattr(B, "PINNED", bad)
    with pytest.raises(B.InputChanged):
        B.build_doc(ROOT)
    with pytest.raises(B.InputChanged):
        B.verify_pins(ROOT, {"docs/decisions/does_not_exist.json": "0" * 64})


def test_mutable_governance_never_pinned():
    for rel in B.PINNED:
        for banned in ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state"):
            assert banned not in rel
    listed = {r["path"] for r in _doc()["referenced_not_pinned"]}
    assert "docs/orchestration/runtime_state.json" in listed


def test_historical_artifacts_listed_and_unchanged():
    hr = _doc()["historical_reuse"]
    paths = {a["path"] for a in hr["artifacts"]}
    for p in ("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
              "docs/experiments/phase1_prereg_framework/build_phase1_prereg_framework.py",
              "docs/interfaces/preionizer_module/PREIONIZER_MODULE_ICD.md",
              "docs/architecture_comparison/lock1/lock1_decision_brief_v1.json"):
        assert p in paths
    for a in hr["artifacts"]:
        assert B.sha256_file(ROOT / a["path"]) == a["sha256"] == B.PINNED[a["path"]]
    nr = " ".join(x["what"] for x in hr["not_reused"])
    for tok in ("hall_only / rf_hall / ecr_hall", "dwell matching", "common module envelope", "REF-MERGED"):
        assert tok in nr


def test_configuration_ids_and_outcomes():
    d = _doc()
    assert [c["id"] for c in d["configurations"]["configurations"]] == [C1, ICP]
    dt = d["decision_topology"]
    assert dt["outcomes"] == [C1, ICP, "NO_VIABLE_CASE"]
    assert "OPEN" in dt["statuses"] and "OPEN" not in dt["outcomes"]
    assert "row 38" in dt["open_is_status_not_outcome"]
    assert {r["outcome"] for r in dt["rules"]} == set(dt["outcomes"])
    assert dt["current_status"].startswith("NOT_EVALUATED")
    for bad in ("hall_only", "rf_hall", "ecr_hall"):
        assert bad not in dt["outcomes"]
    ca = d["configurations"]["common_article"]
    assert "row 20" in ca["hall_head"] and "row 122" in ca["carrier"] and "row 133" in ca["service_lines"]


def test_stage_map_order_and_evidence_discipline():
    st = _doc()["stage_map"]
    ids = [s["id"] for s in st]
    assert [s["order"] for s in st] == list(range(1, len(st) + 1))
    for need in ("HI-ENG", "HI-S1A", "HI-HOLDOUT-A", "HI-AR", "HI-LOCK1", "HI-HOLDOUT-B", "HI-S1", "HI-S1B", "HI-LOCK2",
                 "HI-CMP", "HI-PB", "HI-ABS", "HI-AO"):
        assert need in ids
    pos = {i: n for n, i in enumerate(ids)}
    assert pos["HI-S1A"] < pos["HI-LOCK1"] < pos["HI-HOLDOUT-B"] < pos["HI-S1"] < pos["HI-S1B"] < pos["HI-LOCK2"] < pos["HI-CMP"]
    hallon = [s["id"] for s in st if s["id"] in ("HI-AR", "HI-S1", "HI-S1B", "HI-CMP", "HI-PB", "HI-ABS")]
    assert all(pos["HI-HOLDOUT-A"] < pos[h] for h in hallon)
    by = {s["id"]: s for s in st}
    assert {s["id"] for s in st if s["score_bearing"]} == {"HI-CMP", "HI-ABS"}
    assert all(pos[s] > pos["HI-LOCK2"] for s in ("HI-CMP", "HI-ABS"))
    assert by["HI-AR"]["can_produce"] == ["ENGINEERING_ONLY_NON_SCORING"] and by["HI-AR"]["gases"] == ["Ar"]
    assert "SCORE_BEARING_MEASURED" in by["HI-AR"]["cannot_produce"]
    assert by["HI-AO"]["can_produce"] == ["MATERIALS_LIFE_AO"]
    assert "MATERIALS_LIFE_AO" in by["HI-CMP"]["cannot_produce"]
    assert "NO_ATOMIC_O" in " ".join(by["HI-CMP"]["gases"])
    assert "row 20" in by["HI-ENG"]["what"] and "surrogate" in by["HI-ENG"]["hardware"]
    for s in st:
        assert s["hardware"] == "-" or "surrogate" in s["hardware"] or "D-09-A" in s["hardware"] or s["id"] == "HI-AO" or s["id"] == "HI-S1A"
        for c in s["can_produce"]:
            assert c in _doc()["terminology"]["stage_evidence_classes"]
    assert "rows 4, 27" in by["HI-ABS"]["what"] or ("row 4" in by["HI-ABS"]["what"] and "row 108" in by["HI-ABS"]["what"])
    assert "row 109" in by["HI-ABS"]["what"]


def test_decision_quantities():
    d = _doc()
    dqs = d["decision_quantities"]
    ids = [q["id"] for q in dqs]
    assert len(ids) == len(set(ids)) and all(i.startswith("DQ-HI-") for i in ids)
    ins = {x["id"] for x in json.loads((ROOT / B.INS_REL).read_text(encoding="utf-8"))["instruments"]}
    roles = {q["id"]: q["role"] for q in dqs}
    for need in ("DQ-HI-SUST", "DQ-HI-ECAP", "DQ-HI-VCPL", "DQ-HI-TABS", "DQ-HI-PBUS", "DQ-HI-STAB", "DQ-HI-SAFE", "DQ-HI-IGN"):
        assert roles[need] == "HARD_GATE"
    for need in ("DQ-HI-DXE", "DQ-HI-DPBUS", "DQ-HI-DMASS", "DQ-HI-TPBUS", "DQ-HI-RESTART", "DQ-HI-LIFE"):
        assert roles[need] == "PARETO_REPORTED"
    assert roles["DQ-HI-KNEE"] == "DESCRIPTIVE_OUTPUT" and roles["DQ-HI-ETAU"] == "CONDITIONAL"
    for q in dqs:
        assert q["margin"] == B.MARGIN_NOT_SET
        assert q["measurement_chain_uncertainty_owner"].startswith("PENDING docs/experiments/hall_icp/uncertainty_budget/")
        assert q["freeze_points"] == {"definition_form": "LOCK-1", "margin_value": "LOCK-2"}
        assert q["units"] and q["operational_definition"]
        for c in q["measurement_chain"]:
            if c.startswith("INS-"):
                assert c.split()[0] in ins
    dt = d["decision_topology"]
    assert set(dt["hard_gates"]) == {i for i, r in roles.items() if r == "HARD_GATE"}
    assert "row 37" in dt["net_benefit_form"] and "no weighted scalar" in dt["net_benefit_form"]


def test_no_numeric_leaf_in_decision_and_design_sections():
    d = _doc()
    for k in ("decision_topology", "decision_quantities", "design_rules", "missing_data", "data_quality", "same_condition",
              "module_exchange", "stage_map", "gate_deadlines", "held_out_validation", "open_owner_questions",
              "interface_demands"):
        assert [p for p in _numeric_leaves(d[k]) if not p.endswith("/order")] == [], k
    txt = json.dumps({k: d[k] for k in ("decision_quantities", "decision_topology", "design_rules")})
    assert not re.search(r"[<>]=?\s*\d+(\.\d+)?\s*%", txt.replace(">= 50 K", ""))


def test_items_table():
    items = _doc()["items"]
    assert len({i["id"] for i in items}) == len(items)
    for it in items:
        for f in ("id", "name", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"):
            assert f in it, (it["id"], f)
        assert it["evidence_class"] in B.EVIDENCE_CLASSES
        assert it["freeze_point"] in B.FREEZE_POINTS
        if isinstance(it["value"], str) and it["value"].startswith("TBD"):
            assert it["value"].startswith("TBD - requires ")
            assert it["evidence_class"] == "none (TBD)"
        else:
            assert it["evidence_class"] == "owner-allocation"
            assert re.search(r"\brows? \d+", it["source"]), it["id"]
    by = {i["id"]: i for i in items}
    assert by["ITM-01"]["value"] == 13.56 and by["ITM-01"]["source"] == "row 72"
    assert by["ITM-08"]["check"]["computed"].startswith("50/3") and by["ITM-08"]["check"]["rounded_2dp"] == "16.67"
    for tbd in ("ITM-30", "ITM-31", "ITM-32", "ITM-33"):
        assert by[tbd]["freeze_point"] == "LOCK-2" and by[tbd]["status"] == "NOT SET"


def test_every_cited_row_is_applied_verbatim():
    d = _doc()
    answers = {r["row"]: r for r in json.loads((ROOT / ANS_REL).read_text(encoding="utf-8"))["answers"]}
    applied = {a["row"]: a for a in d["owner_answers_applied"]}
    for row, a in applied.items():
        assert a["owner_answer_verbatim"] == answers[row]["owner_answer_verbatim"]
        assert a["applied_as"]
    rest = {k: v for k, v in d.items() if k != "owner_answers_applied"}
    txt = json.dumps(rest, ensure_ascii=False)
    cited = set()
    for m in re.finditer(r"\brows? (\d+(?:, \d+)*)", txt):
        cited.update(int(x) for x in m.group(1).split(", "))
    missing = sorted(cited - set(applied))
    assert not missing, missing
    assert all(1 <= r <= 147 for r in cited)


def test_order_balance_and_assignment():
    seqs = B.sequence_set()
    assert sorted(map(tuple, seqs)) == [(C1, ICP), (ICP, C1)]
    assert all(B.balance_report(seqs).values())
    assert B.minimum_blocks(3, seqs) == 6
    ed = _doc()["execution_design"]
    assert ed["min_blocks_if_interpretation_accepted"]["value"] == 6
    assert ed["min_complete_replicate_sets"]["source"] == "row 19"
    with pytest.raises(ValueError):
        B.assign_sequences(5, SYNTH_SEED_1, seqs)
    with pytest.raises(ValueError):
        B.assign_sequences(6, "not-a-seed", seqs)
    a1 = B.assign_sequences(6, SYNTH_SEED_1, seqs)
    assert a1 == B.assign_sequences(6, SYNTH_SEED_1, seqs)
    for r in (1, 2, 3):
        got = sorted(tuple(x["order"]) for x in a1 if x["replicate_set"] == r)
        assert got == sorted(map(tuple, seqs))
    a2 = B.assign_sequences(6, SYNTH_SEED_2, seqs)
    assert [x["block"] for x in a2] == list(range(1, 7))
    rc = B.reference_carryover(seqs, C1)
    assert rc["by_module_on_carrier"][ICP] == {C1: 2}


def test_design_rules_cite_owner_rows():
    rules = {r["id"]: r for r in _doc()["design_rules"]}
    want = {"DR-02": "row 19", "DR-03": "row 30", "DR-04": "row 31", "DR-05": "row 39", "DR-06": "row 41",
            "DR-07": "row 24", "DR-08": "row 23", "DR-09": "row 25", "DR-10": "row 35", "DR-11": "row 32",
            "DR-12": "row 40", "DR-13": "row 36", "DR-16": "row 133"}
    for k, v in want.items():
        assert rules[k]["source"] == v
    md = {m["id"]: m for m in _doc()["missing_data"]}
    assert md["MD-HI-10"]["classification"].startswith("NOT_TESTED")
    assert any(m["reuses"].startswith("MD-0") for m in md.values())
    rr = {r["id"]: r for r in _doc()["module_exchange"]}
    assert "row 33" in rr["RR-HI-07"]["rule"] and "row 40" in rr["RR-HI-05"]["rule"]


def test_required_sections_and_pending_lanes():
    d = _doc()
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_h4_inputs"):
        assert d[k], k
    dirs = {x["direction"] for x in d["interface_demands"]}
    for lane in ("A9-02", "A9-03", "A9-04"):
        assert any(f"to {lane}" in x for x in dirs) and any(f"from {lane}" in x for x in dirs)
    m16 = {r["row"]: r["key"] for r in json.loads((ROOT / B.M16_REL).read_text(encoding="utf-8"))["rows"]}
    for m in d["m16_impact"]:
        assert m16[m["row"]] == m["key"]
    for q in d["open_owner_questions"]:
        assert q["proposed_answer"]
    txt = json.dumps(d)
    for p in ("PENDING docs/architecture_comparison/power_boundary_a9/", "PENDING docs/interfaces/icp_neutralizer/",
              "PENDING docs/experiments/hall_icp/uncertainty_budget/", "PENDING docs/evidence/icp_neutralizer/"):
        assert p in txt
    for s in ("## (a)", "## (b)", "## (c)", "## (d)", "## (e)", "## (f)", "## (g)"):
        assert s in _md()


def test_no_winner_no_prediction_no_forbidden_code():
    txt = json.dumps(_doc()).lower()
    for banned in ("best architecture", "recommended architecture", "sgb-screen", "ensemble_member_id", "conditional_baseline("):
        assert banned not in txt
    for m in re.finditer(r"winner", txt):
        ctx = txt[max(0, m.start() - 40):m.start()]
        assert "never" in ctx or "no " in ctx or ctx.endswith("no_")
    for path in (BUILDER, Path(__file__)):
        code = path.read_text(encoding="utf-8")
        pkg = "abep" + "_sim"
        assert f"import {pkg}" not in code and f"from {pkg}" not in code
        assert "xe" + "_ledger" not in code
