"""Tests for the A9 downstream ICP-neutralizer ICD (fo_a9_03_icp_neutralizer_icd).

Run: python -m pytest -q tests/test_icp_neutralizer_icd.py   (a few seconds; standard library + pytest only).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docs" / "interfaces" / "icp_neutralizer" / "build_icp_neutralizer_icd.py"
JSON_PATH = REPO / "schemas" / "interfaces" / "icp_neutralizer_icd_v1.json"
MD_PATH = REPO / "docs" / "interfaces" / "icp_neutralizer" / "ICP_NEUTRALIZER_ICD.md"

A9_SHA = "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f"
ANS_SHA = "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1"
PACK_SHA = "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976"
BRIEF_ROWS = (17, 46, 62, 63, 64, 67, 69, 70, 71, 72, 79, 83, 86, 116, 117, 122, 130, 133)
EXCHANGE_CHECKS = {"cold_tare", "service_line_parasitic", "Bz_perturbation", "electrical_isolation", "rf_pickup"}


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("_icp_icd_builder_under_test", SCRIPT)
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
    a = builder.outputs()
    b = builder.outputs()
    assert a == b
    assert a[builder.OUT_JSON] == JSON_PATH.read_text(encoding="utf-8")
    assert a[builder.OUT_MD] == MD_PATH.read_text(encoding="utf-8")


def test_immutable_decisions_pinned(doc):
    assert doc["governing_decision"]["sha256"] == A9_SHA == _sha(doc["governing_decision"]["path"])
    assert doc["owner_answers"]["sha256"] == ANS_SHA == _sha(doc["owner_answers"]["path"])
    assert doc["owner_answers"]["verbatim_pack"]["sha256"] == PACK_SHA
    for p in doc["decision_pins"]:
        assert p["sha256"] == _sha(p["path"]), p["path"]
        assert p["immutable"] is True
    keys = {p["key"] for p in doc["decision_pins"]}
    assert {"A9", "ANS", "PACK", "A4", "A5", "A6", "A7"} <= keys


def test_deliverable_and_historical_pins_current(doc):
    for p in doc["deliverable_pins"] + doc["historical_reuse"]["artifacts"]:
        assert p["sha256"] == _sha(p["path"]), p["path"]


def test_mutable_governance_never_pinned(doc):
    pinned = {p["path"] for p in doc["decision_pins"] + doc["deliverable_pins"] + doc["historical_reuse"]["artifacts"]}
    for bad in ("lane_registry", "trigger_registry", "trigger_ledger", "runtime_state", "fired_triggers"):
        assert not any(bad in p for p in pinned), bad


def test_identity_and_vocabulary(doc):
    assert doc["schema"] == "icp_neutralizer_icd_v1"
    assert doc["follow_on"] == "fo_a9_03_icp_neutralizer_icd" and doc["trigger"] == "T_A9_03_ICP_ICD"
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
    assert doc["configurations"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    assert "NO_VIABLE_CASE" in doc["outcome_vocabulary"]
    assert "OPEN" not in doc["outcome_vocabulary"] and doc["status_not_outcome"] == ["OPEN"]
    for old in ("hall_only", "rf_hall", "ecr_hall"):
        assert old not in doc["configurations"] and old not in doc["outcome_vocabulary"]
        for x in doc["items"]:
            assert old not in x["applies_to"]


def test_items_structure(doc):
    items = doc["items"]
    assert [x["id"] for x in items] == [f"ICP-{i:02d}" for i in range(1, len(items) + 1)]
    groups = {x["group"] for x in items}
    assert groups == {"mechanical", "rf", "electrical", "gas_plume", "magnetic", "harness_telemetry", "thermal",
                      "exchange"}
    for x in items:
        for k in ("requirement", "units", "basis", "status", "freeze_point", "verification"):
            assert x[k], (x["id"], k)
        assert x["freeze_point"] in ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
        if x["value"] is None:
            assert x["evidence_class"] is None, x["id"]
            assert x.get("tbd", "").startswith("TBD - requires") or x["status"].startswith("PENDING "), x["id"]
        else:
            assert x["evidence_class"].split()[0] in doc["evidence_classes"], x["id"]
            assert x["sources"], x["id"]
        for a in x["applies_to"]:
            assert a in ("hall_c1_reference", "hall_icp_neutralizer", "sham_module")


def test_owner_given_values_trace_to_rows(doc, answers):
    for x in doc["items"]:
        if x["status"] == "OWNER_GIVEN":
            assert x["owner_rows"], x["id"]
            assert x["evidence_class"] == "owner-allocation", x["id"]
    by = {x["id"]: x for x in doc["items"]}
    assert by["ICP-11"]["value"] == 13.56 and "13.56 MHz" in answers[72]["owner_answer_verbatim"]
    assert by["ICP-12"]["value"] == [0.0, 500.0] and "0–500 W" in answers[72]["owner_answer_verbatim"]
    assert by["ICP-37"]["value"] == 50.0 and "≥50 K" in answers[86]["owner_answer_verbatim"]
    assert by["ICP-28"]["value"] == 2 and "two elevated" in answers[23]["owner_answer_verbatim"]
    assert by["ICP-20"]["value"] == "floating (default)" and "floating" in answers[70]["owner_answer_verbatim"]
    assert by["ICP-32"]["value"].startswith("no dedicated ICP magnet")
    assert "UNMAGNETIZED" in answers[69]["owner_answer_verbatim"]
    assert set(by["ICP-39"]["value"]) == EXCHANGE_CHECKS


def test_rf_only_term_is_arithmetic_and_not_a_module_bound(doc):
    by = {x["id"]: x for x in doc["items"]}
    x = by["ICP-36"]
    assert x["status"] == "DERIVED_BOUND" and x["value"] == pytest.approx(500.0 * 1.2)
    assert "RF-only partial allocation term" in x["basis"] and 72 in x["owner_rows"] and 86 in x["owner_rows"]
    assert "NOT a bound on the total module heat load" in x["requirement"]
    dem = {d["id"]: d for d in doc["interface_demands"]}
    assert dem["ID-16"]["value"] == x["value"] and "RF-only" in dem["ID-16"]["status"]
    assert "NOT a bound on the total" in dem["ID-16"]["quantity"]
    # the total module heat load (discharge-path + plume terms) has no value until P_d,max exists
    t = by["ICP-43"]
    assert t["value"] is None and t["status"].startswith("PENDING ") and "Q_coll" in t["requirement"]
    assert dem["ID-26"]["value"] is None and dem["ID-25"]["value"] is None
    assert "ICP-43" in by["ICP-37"]["requirement"]


def test_rf_voltage_rating_separate_from_dc_isolation(doc):
    by = {x["id"]: x for x in doc["items"]}
    dc = by["ICP-23"]
    assert dc["value"] == 350.0 and dc["evidence_class"] == "owner-allocation (margin TBD)"
    assert "antenna circuit is NOT covered" in dc["requirement"]
    rf = by["ICP-44"]
    assert rf["value"] is None and rf["tbd"].startswith("TBD - requires")
    assert "RF hipot at full forward power" in rf["verification"] and "combined stress" in rf["requirement"]


def test_freeze_points_defined_and_incompatibility_checked(doc):
    fp = doc["freeze_point_definitions"]
    assert set(fp) == set(doc["freeze_points"])
    assert "before LOCK-2" in fp["after-evidence"] and "row 71" in fp["after-evidence"]
    h = doc["hard_incompatibility_check"]
    assert h["verdict"] == "none identified" and h["veto_claimed"] is False and h["checked"]


def test_c1_external_source_pointer_supports_value(doc, builder):
    x = {x["id"]: x for x in doc["items"]}["ICP-05"]
    ext = [s for s in x["sources"] if s.get("id") == "L-EXTERNAL"]
    assert len(ext) == 1
    target = json.loads((REPO / ext[0]["path"]).read_text(encoding="utf-8"))
    assert "outside the outer pole" in builder.resolve(target, ext[0]["pointer"])


def test_cited_rows_exist_and_fingerprints_match(doc, answers):
    applied = {r["row"]: r for r in doc["owner_answers_applied"]}
    for r, rec in applied.items():
        assert 1 <= r <= 147
        assert rec["covers_ids"] == answers[r]["covers_ids"]
        assert rec["answer_sha256"] == hashlib.sha256(
            answers[r]["owner_answer_verbatim"].encode("utf-8")).hexdigest()
        assert rec["how_applied"]
    for x in doc["items"]:
        for r in x["owner_rows"]:
            assert r in applied, (x["id"], r)
        for s in x["sources"]:
            if "row" in s:
                assert s["answer_sha256"] == applied[s["row"]]["answer_sha256"]
    for r in BRIEF_ROWS:
        assert r in applied, r


def test_copied_values_resolve(doc, builder):
    n = 0
    for x in doc["items"]:
        c = x.get("copied_from")
        if not c:
            continue
        n += 1
        src = c["source"]
        assert src["sha256"] == _sha(src["path"])
        target = json.loads((REPO / src["path"]).read_text(encoding="utf-8"))
        assert builder.resolve(target, src["pointer"]) == c["value"], x["id"]
    assert n >= 7


def test_pending_lanes_never_filled(doc):
    lanes = {"A9-01", "A9-02", "A9-04", "A9-05"}
    for d in doc["interface_demands"]:
        if d["from"] in lanes:
            assert d["value"] is None and d["status"].startswith("PENDING "), d["id"]
    for x in doc["items"]:
        if x["status"].startswith("PENDING"):
            assert x["value"] is None, x["id"]


def test_interface_demands_both_directions(doc):
    dem = doc["interface_demands"]
    for peer in ("A9-01", "A9-02", "A9-04", "A9-05", "H2-1", "H2-6", "H2-7"):
        assert any(d["from"] == "A9-03" and d["to"] == peer for d in dem), ("to", peer)
        assert any(d["from"] == peer and d["to"] == "A9-03" for d in dem), ("from", peer)
    for d in dem:
        assert d["units"] and d["status"] and d["quantity"]


def test_brief_topics_covered(doc):
    txt = json.dumps(doc["items"])
    for needle in ("external", "kinematic", "25 kg", "sham", "13.56", "0-500 W", "matching", "feedthrough",
                   "directional coupler", "interlock", "pickup", "floating", "collector", "anode", "bus slot",
                   "gas", "conductance", "background", "B(z)", "unmagnetized".lower(), "MODULE_ID",
                   "reflected", "temperatures", "50 K", "serial", "cold/tare"):
        assert needle.lower() in txt.lower(), needle
    by = {x["id"]: x for x in doc["items"]}
    assert "new serialized unit" in by["ICP-40"]["requirement"]
    assert "never hard-grounded" in by["ICP-21"]["requirement"]


def test_analog_annex_provenance(doc):
    ann = doc["published_analog_annex"]
    src = ann["source"]
    assert src["doi"] == "10.1007/s44205-024-00081-2"
    assert re.fullmatch(r"[0-9a-f]{64}", src["retrieved_pdf_sha256"])
    assert src["label"] == "published analog, reported"
    for e in ann["entries"]:
        assert e["source"] == src["id"] and 1 <= e["page"] <= src["pages"]
        assert e["locator"].startswith("p. ")
        assert e["evidence_class"].split()[0] in doc["evidence_classes"]
        assert e["label"] == "published analog, reported"
        assert "never a Vyovrinda" in e["use"]
    # analog values never become ICD item values
    item_values = json.dumps([x["value"] for x in doc["items"]])
    for bad in ("65.0", "2.1", "0.36", "-100.0"):
        assert bad not in item_values, bad


def test_no_prediction_no_winner(doc):
    s = json.dumps(doc).lower()
    for bad in ("sgb-screen", "screening_candidate", "plasma_devices.py\"", "\"winner\":", "predicted_thrust",
                "thrust_mN\":"):
        assert bad not in s, bad
    assert "no configuration is ranked" in doc["standing_facts"]["no_winner"]


def test_required_sections(doc):
    for k in ("items", "interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_h4_inputs", "published_analog_annex"):
        assert doc[k], k
    for q in doc["open_owner_questions"]:
        assert q["id"].startswith("ICPQ-") and q["question"] and q["proposed_answer"]
    assert doc["historical_reuse"]["never_edited"] is True
    assert doc["historical_reuse"]["reused"] and doc["historical_reuse"]["not_reused"]
    m16 = json.loads((REPO / "docs/budgets/subsystem_maturity/subsystem_maturity_v2.json").read_text(encoding="utf-8"))
    keys = {r["key"]: r["row"] for r in m16["rows"]}
    for m in doc["m16_impact"]:
        assert keys[m["key"]] == m["m16_row"]
        assert m["proposed_state"] != "READY" and m["blocking_item"]


def test_markdown_rendered_from_json(doc):
    md = MD_PATH.read_text(encoding="utf-8")
    assert "generated by docs/interfaces/icp_neutralizer/build_icp_neutralizer_icd.py" in md
    for x in doc["items"]:
        assert f"### {x['id']} " in md
    for q in doc["open_owner_questions"]:
        assert q["id"] in md
    assert A9_SHA in md and ANS_SHA in md


def test_builder_source_hygiene():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import abep_sim" not in src and "from abep_sim" not in src
    assert ".claude/worktrees" not in src
    assert "xe_ledger" not in src
    assert "archengine" not in src.replace("not wired into archengine", "")
    for bad in ("hall_map", "hall_ensemble", "import plasma", "sgb-screen"):
        assert bad not in src, bad


def test_electron_current_capacity_item(doc):
    by = {x["id"]: x for x in doc["items"]}
    x = by["ICP-45"]
    assert x["value"] is None and x["status"].startswith("PENDING") and "I_d,max" in x["status"]
    assert "I_d,max" in x["requirement"] and "Ar (ENGINEERING_ONLY)" in x["verification"]
    assert 109 in x["owner_rows"]
    dem = {d["id"]: d for d in doc["interface_demands"]}
    assert dem["ID-27"]["from"] == "A9-02" and dem["ID-27"]["value"] is None and "SIZING" in dem["ID-27"]["quantity"]
    checked = [c["item"] for c in doc["hard_incompatibility_check"]["checked"]]
    assert any("electron-current capacity" in c for c in checked)
    assert doc["hard_incompatibility_check"]["veto_claimed"] is False


def test_keeper_pulse_rating_separate_from_dc_isolation(doc):
    by = {x["id"]: x for x in doc["items"]}
    k = by["ICP-46"]
    assert k["value"] == 600.0 and 89 in k["owner_rows"] and k["applies_to"] == ["hall_c1_reference"]
    assert "ICP-46" in by["ICP-23"]["requirement"] and "governing" in by["ICP-23"]["basis"]


def test_generator_loss_named_and_demand_order(doc):
    by = {x["id"]: x for x in doc["items"]}
    assert "conversion loss" in by["ICP-43"]["requirement"] and "conversion loss" in by["ICP-24"]["requirement"]
    ids = [d["id"] for d in doc["interface_demands"]]
    assert ids == sorted(ids, key=lambda s: int(s.split("-")[1]))
    assert "body items reference annex ids" in doc["compliance"]["analog_use"]
