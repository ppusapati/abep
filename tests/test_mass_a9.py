"""Tests for the A9 mass reconciliation (fo_a9_06_mass_reconciliation).

Run: python -m pytest -q tests/test_mass_a9.py   (a few seconds; standard library + pytest only).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "budgets" / "mass_a9"
SCRIPT = LANE / "build_mass_a9.py"
JSON_PATH = LANE / "mass_a9_v1.json"
MD_PATH = LANE / "MASS_A9.md"

A9_SHA = "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"
ANS_SHA = "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"
PACK_SHA = "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"
A91_SHA = "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4"
A91_MD_SHA = "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e"
MBOM_SHA = "8ab97ff93f507899508374d4ce8116e7066c31e3fbe2c79300f5b55372ba7313"
H27_SHA = "d1813e153af37ebd45cb2ead964ead6c53c756d1a82f93ea89346a83168d0630"
ROW54 = {"AL-01": 3.5, "AL-02": 5.5, "AL-03": 1.0, "AL-04": 3.0, "AL-05": 2.0, "AL-06": 1.5, "AL-07": 2.5,
         "AL-08": 1.5, "AL-09": 1.0, "AL-10": 2.5}
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"}


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _ptr(doc, pointer):
    cur = doc
    for tok in pointer.lstrip("/").split("/"):
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("_mass_a9_builder_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def answers():
    d = json.loads((REPO / "docs/decisions/OD_2026_09_29_owner_answers_147.json").read_text(encoding="utf-8"))
    return {int(a["row"]): a for a in d["answers"]}


def test_builder_check_passes():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_build_is_deterministic(builder):
    assert builder.outputs() == builder.outputs()


def test_immutable_pins_unchanged(doc):
    expected = {
        "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json": A9_SHA,
        "docs/decisions/OD_2026_09_29_owner_answers_147.json": ANS_SHA,
        "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md": PACK_SHA,
        "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json": A91_SHA,
        "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md": A91_MD_SHA,
        "docs/architecture_comparison/mass_bom/mass_bom_v1.json": MBOM_SHA,
        "docs/hardware/h2/h2_7_mechanical_bom/h2_7_mechanical_bom_v1.json": H27_SHA,
    }
    pins = {p["path"]: p["sha256"] for p in doc["pins"]}
    for rel, sha in expected.items():
        assert pins[rel] == sha, rel
        assert _sha(rel) == sha, f"{rel} changed on disk"
    for p in doc["pins"] + doc["read_deliverables"]:
        assert _sha(p["path"]) == p["sha256"], p["path"]
    assert doc["governing_decision"]["sha256"] == A9_SHA
    assert doc["a9_1_followup"]["sha256"] == A91_SHA and doc["a9_1_followup"]["verbatim"]["sha256"] == A91_MD_SHA


def test_governance_files_never_pinned(doc):
    pinned = {p["path"] for p in doc["pins"] + doc["read_deliverables"]}
    for g in ("lane_registry_v1.json", "trigger_registry_v1.json", "fired_triggers.jsonl", "trigger_ledger_v2.jsonl",
              "runtime_state.json"):
        assert not any(g in p for p in pinned), g


def test_copied_values_resolve_to_their_sources(doc):
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            if {"path", "pointer", "sha256", "value"} <= set(o):
                src = json.loads((REPO / o["path"]).read_text(encoding="utf-8"))
                assert _ptr(src, o["pointer"]) == o["value"], (o["path"], o["pointer"])
                assert _sha(o["path"]) == o["sha256"]
                n += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(doc)
    assert n >= 10


def test_owner_allocations_unchanged_and_labelled(doc, answers):
    verb = answers[54]["owner_answer_verbatim"]
    assert "28 kg dry target" in verb and "Sum 24 kg" in verb and "4 kg dry development reserve" in verb
    lines = {r["line"]: r for r in doc["line_checks"]}
    assert {k: v["allocation_kg"] for k, v in lines.items()} == ROW54
    assert abs(sum(ROW54.values()) - 24.0) < 1e-12
    for r in doc["line_checks"]:
        assert r["evidence_class"] == "owner-allocation"
        assert r["owner_allocation_changed_here"] is False
    items = {i["id"]: i for i in doc["items"]}
    for lid, kg in ROW54.items():
        assert items[f"MA-{lid}"]["value"] == kg
        assert items[f"MA-{lid}"]["status"].startswith("OWNER_ALLOCATION")
    assert items["MA-RES"]["value"] == 4.0 and items["MA-TGT"]["value"] == 28.0


def test_line_states_and_arithmetic(doc):
    lines = {r["line"]: r for r in doc["line_checks"]}
    below = {k for k, r in lines.items() if r["state"] == "ALLOCATION_BELOW_EVIDENCE_FLOOR"}
    assert below == {"AL-04", "AL-07", "AL-08"}
    for k, r in lines.items():
        assert r["state"] in ("CONSISTENT", "ALLOCATION_BELOW_EVIDENCE_FLOOR", "ALLOCATION_UNVERIFIABLE_TBD")
        if k not in below:
            assert r["state"] == "ALLOCATION_UNVERIFIABLE_TBD" and r["evidence_floor_kg"] is None
    assert lines["AL-04"]["evidence_floor_kg"] == pytest.approx(1.925 + 1.579)
    assert lines["AL-04"]["gap_at_cbe_kg"] == pytest.approx(0.504)
    assert lines["AL-07"]["evidence_floor_kg"] == pytest.approx(5.0)
    assert lines["AL-08"]["evidence_floor_kg"] == pytest.approx(3.5 + 0.974 + 0.57)
    for k in below:
        r = lines[k]
        assert r["evidence_floor_kg"] > r["allocation_kg"]
        assert r["gap_at_row57_mev_kg"] == pytest.approx(r["evidence_floor_kg"] * 1.2 - r["allocation_kg"])


def test_row56_nasa_target_excluded_from_ppu_floor(doc):
    ppu = next(r for r in doc["line_checks"] if r["line"] == "AL-07")
    assert ppu["evidence_floor_kg"] > 2.0
    ex = ppu["evidence"]["context"]["excluded"]
    assert ex["value_kg"] == 2.0 and "row 56" in ex["why"]
    items = {i["id"]: i for i in doc["items"]}
    assert items["ME-05"]["status"].startswith("EXCLUDED_AS_CBE")


def test_recorder_discrepancy_recorded(doc):
    q = {x["id"]: x for x in doc["open_owner_questions"]}
    assert "4.54" in q["MQ-08"]["question"] and "5.044" in q["MQ-08"]["question"]


def test_flight_bom_a9_amendment(doc):
    bom = doc["a9_flight_bom"]
    flight_ids = {i["id"] for i in bom["flight"]}
    names = " ".join(i["name"] for i in bom["flight"]).lower()
    for must in ("icp neutralizer head", "rf generator", "matching network", "feedthrough", "collector"):
        assert must in names, must
    removed = {i["predecessor_mass_bom_v1"] for i in bom["removed_preionizer_only"] if i["predecessor_mass_bom_v1"]}
    assert removed == {"rf_source", "rf_generator", "rf_matching_network", "ecr_source", "microwave_source",
                       "waveguide", "ecr_magnets"}
    for i in bom["flight"]:
        assert i["predecessor_mass_bom_v1"] not in removed
        assert "R17.m_interface_provision" not in i["predecessor_h2_7_lines"]
        assert i["predecessor_mass_bom_v1"] != "cathode"
        assert not set(i["power_slots_a9"]) & {"c1_heater", "c1_keeper", "c1_common_tie", "filter_getter"}
        assert i["allocation_line"] in ROW54 or i["allocation_mapping"].startswith("WET_TERM")
        assert i["evidence_class"] is None or i["evidence_class"] in EVIDENCE_CLASSES
        assert i["freeze_point"] in ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
    c1 = bom["c1_dropped_from_flight"]
    assert {i["id"] for i in c1}.isdisjoint(flight_ids)
    assert any(i["predecessor_mass_bom_v1"] == "cathode" for i in c1)
    assert all(v == "NOT_INSTALLED" for v in bom["c1_slots_check"].values())
    assert {i["bom_status"] for i in bom["variant_only"]} == {"VARIANT_ONLY"}
    assert set(doc["configurations"]) == {"hall_c1_reference", "hall_icp_neutralizer"}
    assert "NO_VIABLE_CASE" in doc["outcome_vocabulary"] and doc["status_not_outcome"] == ["OPEN"]


def test_flight_xe_system_retained(doc):
    flight = doc["a9_flight_bom"]["flight"]
    preds = {i["predecessor_mass_bom_v1"] for i in flight}
    assert {"xe_tank", "xe_valve_and_flow_control", "xe_load", "xe_residual"} <= preds


def test_residual_is_imported_never_computed(doc):
    clo = doc["wet_closure"]
    assert clo["residual"]["value_kg"] is None
    assert clo["residual"]["status"].startswith("PENDING docs/budgets/") and "_a9/" in clo["residual"]["status"]
    for c in clo["cells"]:
        assert c["residual_kg"] is None
        assert c["wet_known_kg"] == pytest.approx(c["dry_kg"] + c["xe_case_kg"])
    res = next(i for i in doc["a9_flight_bom"]["flight"] if i["id"] == "A9B-14")
    assert res["value"] is None and res["status"].startswith("PENDING")


def test_closure_matrix(doc):
    clo = doc["wet_closure"]
    cells = clo["cells"]
    assert len(cells) == len(clo["readings"]) * 3 * 3
    assert {c["xe_case_kg"] for c in cells} == {2.0, 5.0, 10.0}
    assert {c["reference_kg"] for c in cells} == {34.0, 36.0, 40.0}
    for c in cells:
        assert c["state"] in ("CLOSES", "DOES_NOT_CLOSE", "NOT_EVALUABLE")
        assert c["state"] != "CLOSES"  # the residual import is pending
        if c["reference"] == "HARD_40_WET":
            assert (c["state"] == "DOES_NOT_CLOSE") == (c["wet_known_kg"] >= 40.0)
        else:
            assert (c["state"] == "DOES_NOT_CLOSE") == (c["wet_known_kg"] > c["reference_kg"])
        if c["state"] == "NOT_EVALUABLE":
            assert c["headroom_for_pending_kg"] > 0 and c["unresolved"]
    r = clo["readings"]
    assert r["R0"]["dry_kg"] == pytest.approx(28.0)
    k = 0.05 / 0.95
    r2 = 1.2 * (23 * 1.2 + k * 23 * 1.2)
    assert r["R2"]["dry_kg"] == pytest.approx(r2, abs=1e-6)
    r2e_nonh = (16.0 + 3.504 + 5.0 + 5.044) * 1.2
    assert r["R2E"]["dry_kg"] == pytest.approx(1.2 * r2e_nonh / 0.95, abs=1e-6)
    assert r["R2E"]["dry_kg"] > 40.0
    assert clo["primary_reading"] == "R2"


def test_required_reduction_consistent(doc, builder):
    floors = doc["wet_closure"]["floors_substituted_kg"]
    for x in doc["required_reduction_of_evidence_free_lines"]:
        if x["reduction_needed_kg"] is None:
            continue
        assert 0.0 <= x["reduction_needed_kg"] <= x["other_lines_allocated_kg"]
    x = next(x for x in doc["required_reduction_of_evidence_free_lines"]
             if x["reading"] == "R2E" and x["xe_case_kg"] == 2.0 and x["reference"] == "HARD_40_WET")
    closed = 16.0 - (38.0 * 0.95 / 1.44 - sum(floors.values()))
    assert x["reduction_needed_kg"] == pytest.approx(closed, abs=1e-5)


def test_xe_screen_is_not_a_gate(doc):
    for x in doc["xe_screen_row44"]:
        assert x["screen"] in ("SCREEN_FLAG", "SCREEN_OK_KNOWN_PART")
        assert x["cap_kg"] == pytest.approx(0.25 * {"INTERNAL_34": 34, "INTERNAL_36": 36, "HARD_40_WET": 40}[x["reference"]])
        assert "not a gate" in x["note"]


def test_required_sections(doc):
    for key in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
                "m16_impact", "h3_h4_inputs", "a9_flight_bom", "line_checks", "wet_closure",
                "h2_7_demands_reevaluated"):
        assert doc[key], key
    for it in doc["items"]:
        assert {"id", "value", "units", "basis", "source", "evidence_class", "status", "freeze_point"} <= set(it)
        assert it["freeze_point"] in ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
        assert it["evidence_class"] is None or it["evidence_class"] in EVIDENCE_CLASSES
        if it["value"] is None:
            assert it["status"].startswith(("TBD - requires", "PENDING"))
    for q in doc["open_owner_questions"]:
        assert q["proposed_answer"]
    lanes = " ".join(d["to"] + " " + d["from"] for d in doc["interface_demands"])
    for lane in ("A9-07 docs/hardware/h2_a9_revisions/", "A9-09 docs/procurement/rfq_a9/", "A9-10"):
        assert lane in lanes
    assert "docs/budgets/" in lanes and "_ledger_a9/" in lanes
    h27_ids = {d["h2_7_id"] for d in doc["h2_7_demands_reevaluated"]["outgoing_from_h2_7_v1"]}
    assert h27_ids == {f"ID-{i:02d}" for i in range(1, 15)}
    assert {m["m16_row"] for m in doc["m16_impact"]} == set(range(1, 18))


def test_owner_rows_resolve_and_fingerprints_match(doc, answers):
    for x in doc["owner_answers_applied"]:
        a = answers[x["row"]]
        assert x["covers_ids"] == a["covers_ids"]
        assert x["answer_sha256"] == hashlib.sha256(a["owner_answer_verbatim"].encode("utf-8")).hexdigest()
    rows = {x["row"] for x in doc["owner_answers_applied"]}
    assert {5, 6, 45, 48, 52, 53, 54, 56, 57, 59, 60} <= rows
    a91 = json.loads((REPO / "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json").read_text())["decisions"]
    for x in doc["a9_1_decisions_applied"]:
        assert x["decision"] in a91


def test_markdown_matches_json(doc):
    md = MD_PATH.read_text(encoding="utf-8")
    for r in doc["line_checks"]:
        assert r["line"] in md and r["state"] in md
    for q in doc["open_owner_questions"]:
        assert q["id"] in md
    for d in doc["interface_demands"]:
        assert d["id"] in md
    assert A9_SHA in md and ANS_SHA in md and A91_SHA in md


def test_builder_source_hygiene():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import abep_sim" not in src and "from abep_sim" not in src
    assert ".claude/worktrees" not in src
    assert "xe" + "_ledger" not in src
    assert "archengine" not in src.replace("not wired into archengine", "")
    for bad in ("hall_map", "hall_ensemble", "import plasma", "sgb-screen", "plasma_devices import"):
        assert bad not in src, bad
    test_src = Path(__file__).read_text(encoding="utf-8")
    assert "xe" + "_ledger" not in test_src.replace('"xe" + "_ledger"', "")


def test_no_winner_language(doc):
    txt = json.dumps(doc).lower()
    for bad in ("winner is", "wins", "preferred architecture", "recommended architecture"):
        assert bad not in txt, bad
