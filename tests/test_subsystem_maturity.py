"""Checks for the M16 subsystem maturity matrix (docs/budgets/subsystem_maturity/, fo_subsystem_maturity_matrix).

The parallel lanes' deliverables (pre-ionizer ICD, Xe ledger, Phase-1 framework) are NOT required: comparisons strip the
lazily probed parallel-lane state, and the probe itself is tested on a temporary directory.
"""
import copy
import hashlib
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "budgets", "subsystem_maturity")
JSON_PATH = os.path.join(DIR, "subsystem_maturity_v1.json")
MD_PATH = os.path.join(DIR, "SUBSYSTEM_MATURITY.md")
A4 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4_owner_decisions.json"
A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
G0 = "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"
COLUMNS = ["requirement", "allocation", "interface_status", "preliminary_design", "evidence_status", "procurement_status",
           "analysis_test_needed", "blocker", "owner"]
ALLOCATION_SOURCES = (A5, A4, "docs/architecture_comparison/mass_bom/", "docs/architecture_comparison/power_boundary/",
                      "docs/architecture_comparison/aux_bus/")
CATEGORIES = {"propulsion physics", "cathode-Xe", "mass", "thermal", "compressor", "unresolved interface", "procurement"}
GATES = ["S1a", "LOCK-1", "W5 freeze", "S1/S1b", "LOCK-2", "Phase 1"]


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


def _strip_parallel(d):
    d = copy.deepcopy(d)
    d.pop("parallel_lanes", None)
    for r in d["rows"]:
        r.pop("depends_on_parallel_lanes", None)
        docs = r["cells"]["interface_status"]["documents"]
        for v in docs.get("parallel", {}).values():
            v.pop("state", None)
    return d


def test_committed_json_reproduces(doc, built):
    assert _strip_parallel(doc) == _strip_parallel(built), "stale: run build_subsystem_maturity.py --write"


def test_committed_markdown_reproduces(built):
    if any(v["state"] != "PENDING_PARALLEL_LANE" for v in built["parallel_lanes"].values()):
        pytest.skip("a parallel lane deliverable is present; the Markdown shows the build-time probe state")
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == B.render_md(built)


def test_pins_match_files(doc):
    pins = doc["pins"]["sha256"]
    assert set(pins) == {A4, A5, A6, G0}
    for rel, h in pins.items():
        assert _sha(rel) == h
    g0 = json.load(open(os.path.join(ROOT, G0), encoding="utf-8"))
    assert g0["a5_sha256"] == pins[A5] and g0["verdict"] == "CLEAN"
    assert doc["g0_record"]["sha256"] == pins[G0]
    for forbidden in ("lane_registry_v1.json", "trigger_registry_v1.json", "trigger_ledger", "runtime_state.json", "fired_triggers"):
        assert not any(forbidden in k for k in pins)
        assert not any(forbidden in k for k in doc["inputs_read_sha256"])


def test_seventeen_rows_and_a5_names(doc):
    a5 = json.load(open(os.path.join(ROOT, A5), encoding="utf-8"))["architecture"]
    expected = a5["atmospheric_branch"] + a5["xe_branch"] + a5["propulsion"] + a5["support"]
    assert len(expected) == 16 == a5["baseline_subsystem_count"]
    rows = doc["rows"]
    assert len(rows) == 17
    assert [r["name"] for r in rows[:16]] == expected
    assert [len(a5[g]) for g in ("atmospheric_branch", "xe_branch", "propulsion", "support")] == [5, 3, 3, 5]
    assert all(r["baseline_flight_hardware"] for r in rows[:16])
    last = rows[16]
    assert last["name"] == a5["reserved_interface"]["name"]
    assert last["baseline_flight_hardware"] is False
    assert last["flag"] == "reserved, not baseline flight hardware"
    assert [r["row"] for r in rows] == list(range(1, 18))


def test_nine_columns_in_order(doc):
    assert doc["columns"] == COLUMNS
    for r in doc["rows"]:
        assert list(r["cells"].keys()) == COLUMNS


def _sources(cell):
    s = list(cell.get("sources", []))
    s += [it["source"] for it in cell.get("items", [])]
    s += [e["source"] for e in cell.get("entries", [])]
    return [x for x in s if x]


def test_every_cell_sourced_or_explicit_placeholder(doc):
    for r in doc["rows"]:
        for col in COLUMNS:
            c = r["cells"][col]
            if col == "owner":
                continue
            if col == "interface_status":
                assert c["documents"], (r["name"], col)
                continue
            assert _sources(c), (r["name"], col)


def test_owner_never_invented(doc):
    for r in doc["rows"]:
        o = r["cells"]["owner"]
        assert o["value"] == "OWNER_TO_ASSIGN"
        assert "no accountable party" in o["basis"]


def test_allocations_only_from_allowed_sources(doc):
    for r in doc["rows"]:
        a = r["cells"]["allocation"]
        if not a["entries"]:
            assert a["status"] == "TO_BE_ALLOCATED", r["name"]
        for e in a["entries"]:
            assert e["source"].startswith(ALLOCATION_SOURCES), (r["name"], e["source"])
            for k in ("quantity", "value", "status", "evidence_class"):
                assert e[k]
    # rows with no recorded allocation must say so
    by = {r["key"]: r for r in doc["rows"]}
    for key in ("intake", "filter", "buffer_plenum", "xe_tank", "xe_regulator", "magnetic_circuit", "thermal_control",
                "control_fdir", "sensors_diagnostics", "preionizer_interface"):
        assert by[key]["cells"]["allocation"]["status"] == "TO_BE_ALLOCATED", key
    assert by["compressor"]["cells"]["allocation"]["entries"][0]["value"] == "300 W"


def test_procurement_only_as_recorded(doc):
    allowed_prefix = ("UNKNOWN - owner to confirm", "IN_PROCUREMENT_PLANNING", "APPROVED_FOR_PROCUREMENT")
    for r in doc["rows"]:
        p = r["cells"]["procurement_status"]
        assert p["status"].startswith(allowed_prefix), r["name"]
        if not p["status"].startswith("UNKNOWN"):
            assert any(s.startswith(A4) for s in p["sources"]), r["name"]


def test_interface_status_vocabulary_and_parallel_refs(doc):
    by = {r["key"]: r for r in doc["rows"]}
    for r in doc["rows"]:
        assert r["cells"]["interface_status"]["status"] in {"FROZEN", "PARTIAL", "OPEN"}
    for key in ("preionizer_interface", "hall_chamber", "magnetic_circuit"):
        par = by[key]["cells"]["interface_status"]["documents"]["parallel"]
        assert "fo_preionizer_module_icd" in par
    for key in ("xe_tank", "xe_regulator", "xe_metering"):
        assert "fo_xe_system_ledger" in by[key]["depends_on_parallel_lanes"], key
    for key in ("hall_chamber", "preionizer_interface", "ppu"):
        assert "fo_phase1_prereg_framework" in by[key]["depends_on_parallel_lanes"], key


def test_blockers(doc):
    for r in doc["rows"]:
        b = r["cells"]["blocker"]
        assert b["category"] in CATEGORIES
        assert list(b["blocks_gates"]) == GATES
        assert b["item"]
        if b["first_gate"] is None:
            assert b["beyond"] in ("PHASE1_BRANCH_DECISION", "FLIGHT_DESIGN_FREEZE")
            assert not any(b["blocks_gates"].values())
        else:
            i = GATES.index(b["first_gate"])
            assert [b["blocks_gates"][g] for g in GATES] == [k >= i for k in range(len(GATES))]
    ro = doc["blocker_rollup"]
    assert set(ro["rows_per_category"]) == CATEGORIES
    assert sum(v["count"] for v in ro["rows_per_category"].values()) == 17
    assert ro["answer"]["architecture_branch_decision"].startswith("blocked by propulsion physics")


def test_risk_mapping(doc):
    for r in doc["rows"]:
        ranks = [m["rank"] for m in r["a5_risk_mapping"]]
        assert ranks and all(k in (1, 2, 3, 4) for k in ranks), r["name"]
        for m in r["a5_risk_mapping"]:
            assert m["role"].startswith(("primary", "contributing"))
    rr = doc["blocker_rollup"]["risk_rollup"]
    assert set(rr) == {"1", "2", "3", "4"}
    assert all(v["primary_rows"] for v in rr.values())


def test_milestone_and_neutrality(doc):
    m = doc["milestone"]
    assert m["supports"] == ["A"] and "NO_BASELINE_YET" in m["statement"]
    assert doc["base_status_snapshot"]["bundle1_outcome"] == "NO_BASELINE_YET"
    assert doc["architecture_branch_ids"] == ["hall_only", "rf_hall", "ecr_hall"]
    text = json.dumps(doc)
    assert "sgb-screen-0" not in text
    assert "winner" not in text.replace("no winner", "").replace("No winner", "").replace("no_winner", "")


def test_unknown_reference_raises():
    reg = B.Registry(ROOT)
    assert reg.resolve("HW:HW-C1-01")["state"]
    for bad in ("HW:HW-ZZ-99", "INS:INS-99", "S1A:S1A-C9", "LOCK1:D-99", "RTM:RFP-NOPE", "PAR:fo_unknown", "XX:1"):
        with pytest.raises(KeyError):
            reg.resolve(bad)


def test_parallel_probe_lazy(tmp_path):
    st = B.probe_parallel(str(tmp_path))
    assert set(st) == {"fo_preionizer_module_icd", "fo_xe_system_ledger", "fo_phase1_prereg_framework"}
    assert all(v["state"] == "PENDING_PARALLEL_LANE" and v["files"] == [] for v in st.values())
    d = tmp_path / "docs" / "budgets" / "xe_ledger"
    d.mkdir(parents=True)
    (d / "x.json").write_text('{"status": "DRAFT"}', encoding="utf-8")
    st = B.probe_parallel(str(tmp_path))
    x = st["fo_xe_system_ledger"]
    assert x["state"] == "PRESENT_NOT_YET_INTEGRATED"
    assert x["files"][0]["path"] == "docs/budgets/xe_ledger/x.json" and x["files"][0]["status_field"] == "DRAFT"
    assert st["fo_preionizer_module_icd"]["state"] == "PENDING_PARALLEL_LANE"


def test_missing_pins_refuse(tmp_path):
    with pytest.raises(FileNotFoundError):
        B.verify_pins(str(tmp_path))
