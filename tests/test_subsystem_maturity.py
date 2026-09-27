"""Checks for the M16 subsystem maturity matrix v2 / A7 scheduler (docs/budgets/subsystem_maturity/;
fo_subsystem_maturity_matrix + fo_a6_integration_refresh).

v1 (subsystem_maturity_v1.json / SUBSYSTEM_MATURITY.md) is history: it must stay byte-identical. v2 is rebuilt by the
builder and must reproduce exactly.
"""
import hashlib
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "budgets", "subsystem_maturity")
JSON_PATH = os.path.join(DIR, "subsystem_maturity_v2.json")
MD_PATH = os.path.join(DIR, "SUBSYSTEM_MATURITY_v2.md")
V1_JSON = "docs/budgets/subsystem_maturity/subsystem_maturity_v1.json"
V1_MD = "docs/budgets/subsystem_maturity/SUBSYSTEM_MATURITY.md"
V1_SHA = {V1_JSON: "20114a8074f9d616c0358b7dd5f874abfb569ce2f6ae4354a0d49b15aa646770",
          V1_MD: "22a65512029b67836edc167f3740ede10fbd9c03d7132d0cdf8fcd495acac51a"}
A4 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"
A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A7 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json"
G0 = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
COLUMNS = ["requirement", "allocation", "interface_status", "preliminary_design", "evidence_status", "procurement_status",
           "analysis_test_needed", "blocker", "owner"]
ALLOCATION_SOURCES = (A5, A4, "docs/architecture_comparison/mass_bom/", "docs/architecture_comparison/power_boundary/",
                      "docs/architecture_comparison/aux_bus/")
TECH = {"propulsion physics", "cathode-Xe", "mass", "thermal", "compressor", "unresolved interface", "procurement"}
A7_CATS = ["architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
           "proposal-only documentation gap"]
STATES = ["READY", "RUNNING", "BLOCKED", "VERIFIED"]
GATES = ["S1a", "LOCK-1", "W5 freeze", "S1/S1b", "LOCK-2", "Phase 1"]
H2 = ["fo_h2_1_hall_chamber_magnet", "fo_h2_2_cathode_integration", "fo_h2_3_gas_path_plenum", "fo_h2_4_ppu_bus",
      "fo_h2_5_thermal_network", "fo_h2_6_diagnostics_fixture", "fo_h2_7_mechanical_bom"]
FORBIDDEN = ("lane_registry_v1.json", "trigger_registry_v1.json", "trigger_ledger", "runtime_state.json", "fired_triggers",
             "workflow_scripts")


def _builder():
    spec = importlib.util.spec_from_file_location("build_subsystem_maturity", os.path.join(DIR, "build_subsystem_maturity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _builder()


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def built():
    return B.build(ROOT)


def _sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def test_committed_v2_json_and_markdown_reproduce(doc, built):
    assert doc == built, "stale: run build_subsystem_maturity.py --write"
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == B.render_md(built)
    assert B.OUT_JSON == "subsystem_maturity_v2.json" and B.OUT_MD == "SUBSYSTEM_MATURITY_v2.md"


def test_v1_kept_byte_identical_as_history(doc):
    for rel, h in V1_SHA.items():
        assert _sha(rel) == h, f"{rel} changed: v1 is history and must stay byte-identical"
    assert doc["supersedes"]["files"] == V1_SHA


def test_pins_match_files_and_no_mutable_governance_pinned(doc):
    pins = doc["pins"]["sha256"]
    assert set(pins) == {A4, A5, A6, A7, G0}
    for rel, h in list(pins.items()) + list(doc["deliverable_pins"]["sha256"].items()):
        assert _sha(rel) == h, rel
    a7 = _load(A7)
    assert a7["follows_sha256"] == [pins[A5], pins[A6]]
    g0 = _load(G0)
    assert g0["a5_sha256"] == pins[A5] and g0["verdict"] == "CLEAN"
    hashed = list(pins) + list(doc["deliverable_pins"]["sha256"]) + list(doc["inputs_read_sha256"])
    for forbidden in FORBIDDEN:
        assert not any(forbidden in k for k in hashed), forbidden
    assert "lane_registry_v1" not in json.dumps(doc["deliverable_pins"]) + json.dumps(doc["pins"])


def test_four_merged_deliverables_pinned(doc):
    dp = doc["deliverable_pins"]["sha256"]
    for rel in ("schemas/interfaces/preionizer_module_icd_v1.json", "docs/budgets/xe_ledger/xe_ledger_v1.json",
                "abep_sim/xe_ledger.py", "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json",
                V1_JSON, V1_MD):
        assert rel in dp
    assert set(doc["integrated_deliverables"]) == {"fo_preionizer_module_icd", "fo_xe_system_ledger",
                                                   "fo_phase1_prereg_framework", "fo_subsystem_maturity_matrix (v1, history)"}


def test_no_pending_parallel_lane_cells_left(doc):
    text = json.dumps(doc) + open(MD_PATH, encoding="utf-8").read()
    for s in ("PENDING_PARALLEL_LANE", "PRESENT_NOT_YET_INTEGRATED", "pending parallel lane", "PAR:"):
        assert s not in text, s
    for r in doc["rows"]:
        assert "parallel" not in r["cells"]["interface_status"]["documents"]


def test_seventeen_rows_and_a5_names(doc):
    a5 = _load(A5)["architecture"]
    expected = a5["atmospheric_branch"] + a5["xe_branch"] + a5["propulsion"] + a5["support"]
    assert len(expected) == 16 == a5["baseline_subsystem_count"]
    rows = doc["rows"]
    assert len(rows) == 17
    assert [r["name"] for r in rows[:16]] == expected
    assert rows[16]["name"] == a5["reserved_interface"]["name"] and rows[16]["baseline_flight_hardware"] is False
    assert [r["row"] for r in rows] == list(range(1, 18))
    for r in rows:
        assert list(r["cells"].keys()) == COLUMNS


def test_integration_content(doc):
    by = {r["key"]: r for r in doc["rows"]}
    icd = _load("schemas/interfaces/preionizer_module_icd_v1.json")["x-preionizer-module-icd"]
    pim = by["preionizer_interface"]["cells"]["interface_status"]["documents"]["preionizer_icd"]
    assert list(pim["items"]) == [it["id"] for it in icd["common_items"]]
    assert pim["document_status"] == icd["status"]
    for it in icd["common_items"]:
        cnt = {}
        for q in it["quantities"]:
            cnt[q["status"]] = cnt.get(q["status"], 0) + 1
        assert pim["items"][it["id"]]["quantity_status_counts"] == {k: cnt[k] for k in sorted(cnt)}
    xe = _load("docs/budgets/xe_ledger/xe_ledger_v1.json")
    for key in ("xe_tank", "xe_regulator", "xe_metering"):
        assert "fo_xe_system_ledger" in by[key]["integrated_deliverables"], key
    tank = by["xe_tank"]["scheduler"]["blocking_item"]
    assert tank["ref"] == "XELEDGER:refused" and "refused=True" in tank["state"] and f"n_missing={xe['ledger_state']['n_missing']}" in tank["state"]
    p1 = _load("docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json")
    assert set(doc["phase1_decision_quantities"]["items"]) == {q["id"] for q in p1["decision_quantities"]}
    for key in ("hall_chamber", "ppu", "control_fdir", "preionizer_interface", "xe_metering"):
        assert "fo_phase1_prereg_framework" in by[key]["integrated_deliverables"], key
    assert "P1R:R-05" in by["hall_chamber"]["integrated_deliverables"]["fo_phase1_prereg_framework"]
    assert "P1R:R-06" in by["preionizer_interface"]["integrated_deliverables"]["fo_phase1_prereg_framework"]


def test_scheduler_states_and_one_blocker(doc):
    reg_follow = {x["id"] for x in _load("docs/orchestration/lane_registry_v1.json")["follow_ons"]}
    for r in doc["rows"]:
        s = r["scheduler"]
        assert s["execution_state"] in STATES
        assert isinstance(s["blocking_item"]["ref"], str) and s["blocking_item"]["ref"].count(":") >= 1
        assert s["blocking_item"]["text"] == r["cells"]["blocker"]["item"]
        if s["execution_state"] == "BLOCKED":
            assert s["worked_by"] is None and s["waits_on"] and s["not_worked_reason"]
        if s["execution_state"] == "RUNNING":
            lane = s["worked_by"]["lane"]
            assert lane in H2 and lane in reg_follow and lane in s["h2_lanes"]["matures"]
            assert s["worked_by"]["scope_quote"]
        assert s["execution_state"] != "VERIFIED" or r["cells"]["interface_status"]["status"] == "FROZEN"
    rows = doc["blocker_rollup"]["execution_states"]["rows"]
    assert list(rows) == STATES and sum(v["count"] for v in rows.values()) == 17
    assert rows["VERIFIED"]["count"] == 0  # nothing is owner-frozen with S1a/S1 evidence recorded


def test_a7_categories_and_rule(doc):
    ro = doc["blocker_rollup"]["a7_categories"]
    assert list(ro["rows"]) == A7_CATS
    assert sum(v["count"] for v in ro["rows"].values()) == 17
    for r in doc["rows"]:
        s, b = r["scheduler"], r["cells"]["blocker"]
        assert s["technical_category"] in TECH and s["technical_category"] == b["category"]
        if s["architecture_changing"]["is_a7_architecture_changing_blocker"]:
            want = "architecture blocker"
        elif b["first_gate"] is None:
            want = "proposal-only documentation gap"
            assert b["beyond"] == "FLIGHT_DESIGN_FREEZE"
        else:
            want = s["a7_category"]
            assert want in ("hardware-definition blocker", "procurement blocker", "test-readiness blocker")
        assert s["a7_category"] == want, r["name"]
        assert list(b["blocks_gates"]) == GATES


def test_architecture_changing_flags(doc):
    a7 = _load(A7)
    by = {r["key"]: r for r in doc["rows"]}
    assert by["hall_chamber"]["scheduler"]["architecture_changing"]["a7_blocker"] == 1
    assert by["xe_tank"]["scheduler"]["architecture_changing"]["a7_blocker"] == 3
    for k, v in doc["a7_architecture_changing_blockers"].items():
        assert a7["architecture_changing_blockers"][int(k) - 1] == f"{k} {v}"
    for r in doc["rows"]:
        ac = r["scheduler"]["architecture_changing"]
        if r["key"] not in ("hall_chamber", "xe_tank"):
            assert ac["is_a7_architecture_changing_blocker"] is False and ac["veto_mode"].startswith("not one of the A7")
        assert all(x in (1, 2, 3) for x in ac["feeds_a7_blockers"])


def test_h2_lane_map(doc):
    a7 = _load(A7)
    h2_titles = next(w for w in a7["waves"] if w["wave"] == "H2 hardware")["lanes"]
    m = doc["blocker_rollup"]["h2_lane_map"]
    assert list(m) == H2
    keys = {r["key"] for r in doc["rows"]}
    for lane, v in m.items():
        assert v["a7_title"] in h2_titles and v["registered"] is True
        assert v["matures"] and set(v["matures"]) <= keys and set(v["contributes"]) <= keys
        script = v["scope_source"].split(" ")[0]
        txt = open(os.path.join(ROOT, script), encoding="utf-8").read()
        for q in v["matures"].values():
            assert q["scope_quote"] in txt


def test_reconciliation_list(doc):
    rc = {x["id"]: x for x in doc["reconciliation"]}
    for i in range(1, 11):
        assert f"RC-{i:02d}" in rc
    assert rc["RC-01"]["owning_lanes"] == ["lane_19_cathode_integration"] and "verified_at_build" in rc["RC-01"]
    assert rc["RC-02"]["owning_lanes"] == ["lane_15_thermal_life"] and "verified_at_build" in rc["RC-02"]
    assert rc["RC-05"]["owning_lanes"] == ["fo_capability_demo_prep"] and "verified_at_build" in rc["RC-05"]
    assert rc["RC-08"]["status"].startswith("RESOLVED_IN_V2")
    for x in doc["reconciliation"]:
        assert x["owning_lanes"] and x["status"] in ("OPEN_NOT_FIXED_HERE",) or x["id"] == "RC-08"
    assert "RC-R-14" in rc


def test_every_cell_sourced_owner_and_allocation_rules(doc):
    for r in doc["rows"]:
        assert r["cells"]["owner"]["value"] == "OWNER_TO_ASSIGN"
        a = r["cells"]["allocation"]
        if not a["entries"]:
            assert a["status"] == "TO_BE_ALLOCATED", r["name"]
        for e in a["entries"]:
            assert e["source"].startswith(ALLOCATION_SOURCES), (r["name"], e["source"])
        for col in COLUMNS:
            c = r["cells"][col]
            if col in ("owner", "interface_status"):
                continue
            srcs = list(c.get("sources", [])) + [it["source"] for it in c.get("items", [])] + [e["source"] for e in c.get("entries", [])]
            assert srcs, (r["name"], col)
        p = r["cells"]["procurement_status"]["status"]
        assert p.startswith(("UNKNOWN - owner to confirm", "IN_PROCUREMENT_PLANNING", "APPROVED_FOR_PROCUREMENT"))


def test_milestone_and_neutrality(doc):
    m = doc["milestone"]
    assert m["supports"] == ["A"] and "NO_BASELINE_YET" in m["statement"]
    assert doc["base_status_snapshot"]["bundle1_outcome"] == "NO_BASELINE_YET"
    assert doc["architecture_branch_ids"] == ["hall_only", "rf_hall", "ecr_hall"]
    text = json.dumps(doc)
    assert "sgb-screen-0" not in text
    assert "winner" not in text.replace("no winner", "").replace("No winner", "").replace("no_winner", "")
    assert [q["id"] for q in doc["open_owner_questions"]] == ["M16-Q-01", "M16-Q-02", "M16-Q-03", "M16-Q-04"]


def test_unknown_reference_raises():
    reg = B.Registry(ROOT)
    assert reg.resolve("HW:HW-C1-01")["state"]
    assert reg.resolve("PMQTY:PMI-01.interface_dimensions")["state"].startswith("TBD")
    assert reg.resolve("XEP:t_startup")["state"].startswith("TBD")
    assert reg.resolve("P1DQ:P1DQ-ENVW")["state"].startswith("threshold: UNFROZEN")
    for bad in ("HW:HW-ZZ-99", "INS:INS-99", "S1A:S1A-C9", "LOCK1:D-99", "RTM:RFP-NOPE", "PMI:PMI-99", "PMQ:PMQ-99",
                "PMQTY:PMI-01.nope", "XEP:nope", "XEOD:OD-XE-99", "P1DQ:P1DQ-ENV", "P1R:R-99", "H2:fo_h2_9_x",
                "AUXTBD:hall_discharge#nope", "PAR:fo_xe_system_ledger", "XX:1"):
        with pytest.raises(KeyError):
            reg.resolve(bad)


def test_missing_pins_refuse(tmp_path):
    with pytest.raises(FileNotFoundError):
        B.verify_pins(str(tmp_path))
