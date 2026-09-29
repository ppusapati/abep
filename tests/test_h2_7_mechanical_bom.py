"""H2-7 mechanical envelope / evolving mass model (fo_h2_7_mechanical_bom; owner addendum A7).

Checks: the builder reproduces the committed JSON + MD byte for byte; owner decisions and verified inputs are pinned by
sha256 (a changed pinned file makes the builder raise) and mutable governance files are never pinned; the 16 A5
subsystem names are carried exactly, plus the reserved pre-ionizer interface; RF/ECR modules sit only in the contingency
block; the cathode Xe term is the only fixed Xe design term (5.4 kg; 8.1 kg at 0.15 mg/s); every CBE is sourced, derived
or TBD, with a valid evidence class; the roll-up arithmetic recomputes independently; lazy parallel-lane consumption
works when lanes are absent and adopts only contract-conforming demands; no architecture is selected; no Hall closure /
P5 nuisance key appears. The parallel lanes are NOT required. Run: python -m pytest -q tests/test_h2_7_mechanical_bom.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "hardware" / "h2" / "h2_7_mechanical_bom"
SCRIPT = DIR / "build_h2_7_mechanical_bom.py"
JSON_PATH = DIR / "h2_7_mechanical_bom_v1.json"
MD_PATH = DIR / "H2_7_MECHANICAL_BOM.md"

A5_NAMES = ["intake", "protective/filter stage", "compressor", "buffer/plenum", "atmospheric metering valve",
            "Xe tank", "Xe regulator", "Xe metering (splits to ignition/transition feed and cathode feed)",
            "extended-channel Hall discharge chamber/accelerator", "magnetic circuit",
            "shielded Xe-fed LaB6 hollow cathode", "PPU/power distribution", "thermal control", "control/FDIR",
            "sensors/diagnostics", "mechanical/structural interfaces"]
DECISION_SHA = {
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json":
        "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json":
        "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180",
    "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json":
        "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925",
    "docs/decisions/verification/A5_BASELINE_VERIFICATION.json":
        "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523",
}
EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
FLIGHT = {"FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"}


def _load():
    spec = importlib.util.spec_from_file_location("build_h2_7_mechanical_bom", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def B():
    return _load()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text())


def _lines(doc):
    return {li["id"]: (r, li) for r in doc["rows"] for li in r["line_items"]}


# ------------------------------------------------------------------------------------------------ reproducibility
def test_builder_reproduces_committed_files(B, doc):
    fresh = B.build_document(REPO)
    rec = {k: v["state"] for k, v in doc["lane_consumption"]["lanes"].items()}
    now = {k: v["state"] for k, v in fresh["lane_consumption"]["lanes"].items()}
    assert rec == now, ("parallel-lane state changed since the committed build (%s -> %s): regenerate with python "
                        "docs/hardware/h2/h2_7_mechanical_bom/build_h2_7_mechanical_bom.py" % (rec, now))
    assert B.dump(fresh) == JSON_PATH.read_text()
    assert B.render_md(fresh) == MD_PATH.read_text()
    assert B.dump(B.build_document(REPO)) == B.dump(fresh)  # deterministic


def test_decisions_pinned_and_governance_not_pinned(doc):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"] + doc["input_pins"]}
    for path, sha in DECISION_SHA.items():
        assert pins[path] == sha
    for path, sha in pins.items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == sha, path
    for p in pins:
        assert not any(g in p for g in ("lane_registry", "trigger_registry", "fired_triggers", "trigger_ledger",
                                        "runtime_state"))


def test_changed_pinned_input_raises(B, tmp_path):
    for key, (rel, _, _) in B.PINS.items():
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dst)
    B.build_document(tmp_path, lane_root=tmp_path)  # a faithful copy builds
    a5 = tmp_path / B.PINS["A5"][0]
    a5.write_bytes(a5.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed"):
        B.build_document(tmp_path, lane_root=tmp_path)
    a5.unlink()
    with pytest.raises(FileNotFoundError):
        B.build_document(tmp_path, lane_root=tmp_path)


# ------------------------------------------------------------------------------------------------ structure
def test_a5_rows_exact_and_reserved_interface(doc):
    main = [r for r in doc["rows"] if r["row_id"].startswith("R") and not r.get("reserved_interface")]
    assert [r["a5_subsystem"] for r in main] == A5_NAMES
    res = [r for r in doc["rows"] if r.get("reserved_interface")]
    assert len(res) == 1 and "pre-ionization module interface" in res[0]["a5_subsystem"]
    assert "NO module hardware" in res[0]["line_items"][0]["name"]
    for r in doc["rows"]:
        assert r["flight_status"] in FLIGHT
        assert r["h1_counterpart"]["status"] in FLIGHT


def test_contingency_modules_outside_baseline(doc):
    cm = {c["architecture"]: c for c in doc["contingency_modules"]}
    assert set(cm) == {"rf_hall", "ecr_hall"}
    assert all(c["in_baseline_total"] is False and c["cbe"] is None for c in cm.values())
    baseline_items = {i for r in doc["rows"] for i in r["mass_bom_items"]}
    assert not baseline_items & {"rf_source", "rf_generator", "rf_matching_network", "ecr_source",
                                 "microwave_source", "waveguide", "ecr_magnets"}


def test_architecture_ids_and_no_winner(doc):
    assert doc["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    text = (JSON_PATH.read_text() + MD_PATH.read_text()).lower()
    for bad in ("winner is", "selected architecture:", "recommended architecture", "baseline architecture is"):
        assert bad not in text
    assert doc["hard_incompatibility_check"]["architecture_veto"] is False


def test_required_sections(doc):
    for k in ("design_parameters", "interface_demands", "hard_incompatibility_check",
              "architecture_changing_blockers_touched", "m16_rows", "h3_procurement_inputs", "h4_test_inputs",
              "milestones", "mechanical_envelope", "xe_subsystem", "rollup", "diagnostics", "lane_consumption"):
        assert doc[k], k
    for p in doc["design_parameters"]:
        assert p["id"].startswith("H27-")
        assert set(p) >= {"name", "value", "units", "basis", "source", "evidence_class", "status", "flight_status"}
        assert p["flight_status"] in FLIGHT
        assert p["basis"] in {"requirement", "allocation", "analog", "derived", "assumed", "pending", "TBD"} or \
            p["basis"].startswith("preliminary geometry from")
        if p["value"] is None:
            assert p["status"].startswith("TBD") or "PENDING" in p["status"]
        else:
            assert p["evidence_class"] in EVIDENCE
    ids = [p["id"] for p in doc["design_parameters"]]
    assert len(ids) == len(set(ids))
    for d in doc["interface_demands"]:
        assert set(d) >= {"from", "to", "quantity", "units", "status"}
    assert [b["blocker"] for b in doc["architecture_changing_blockers_touched"]] == [1, 2, 3]
    assert set(doc["milestones"]) >= {"A", "B", "C"}


def test_m16_rows(doc):
    rows = doc["m16_rows"]
    assert [m["a5_subsystem"] for m in rows[:16]] == A5_NAMES and len(rows) == 17
    for m in rows:
        assert m["proposed_state"] in {"READY", "RUNNING", "BLOCKED", "VERIFIED"}
        if m["proposed_state"] == "BLOCKED":
            assert isinstance(m["blocking_item"], str) and m["blocking_item"]
            assert m["rollup_category"] in {"architecture blocker", "hardware-definition blocker",
                                            "procurement blocker", "test-readiness blocker",
                                            "proposal-only documentation gap"}
        else:
            assert "blocking_item" not in m


# ------------------------------------------------------------------------------------------------ evidence
def test_every_cbe_sourced_or_tbd(doc):
    for lid, (r, li) in _lines(doc).items():
        ln = li["resolved"]
        if ln["low"] is None:
            assert ln["status"].startswith("TBD"), lid
            continue
        assert ln["evidence_class"] in EVIDENCE, lid
        assert 0 <= ln["low"] <= ln["high"], lid
        assert ln["basis"] in {"analog", "derived", "allocation"} or ln["basis"].startswith("preliminary geometry")
        if ln["basis"] == "analog" and not ln.get("included_in"):
            assert ln["analogs"], lid


def test_analogs_cited(doc):
    for aid, a in doc["analog_data"].items():
        assert a["evidence_class"] in EVIDENCE, aid
        assert a["source"] in doc["sources"], aid
        assert a["locator"]
    for sid, s in doc["sources"].items():
        assert s["citation"] and s["access"]


def test_analog_ranges_match_analog_data(doc, B):
    L = _lines(doc)
    assert [L["R09.m_hall_head_incl_mc"][1]["resolved"][k] for k in ("low", "high")] == [2.6, 6.3]
    assert [L["R11.m_cathode_unit"][1]["resolved"][k] for k in ("low", "high")] == [0.2, 0.3]
    assert [L["R12.m_ppu"][1]["resolved"][k] for k in ("low", "high")] == [2.0, 10.9]
    assert [L["R06.m_tank"][1]["resolved"][k] for k in ("low", "high")] == [3.5, 6.3]
    assert [L["R07.m_regulator"][1]["resolved"][k] for k in ("low", "high")] == [0.974, 5.9]
    assert L["R08.m_valves"][1]["resolved"]["low"] == pytest.approx(2 * (0.170 + 0.115))
    assert doc["analog_data"]["AN-NASA-LM-PPU-TARGET"]["evidence_class"] == "assumed"  # target, not demonstrated


def test_xe_fixed_term_only(doc):
    L = _lines(doc)
    fixed = [lid for lid, (_, li) in L.items() if li["resolved"]["basis"] == "allocation"]
    assert fixed == ["R06.m_Xe_cathode"]
    assert L["R06.m_Xe_cathode"][1]["resolved"]["low"] == pytest.approx(5.4)
    assert L["R06.m_Xe_other"][1]["resolved"]["low"] is None  # A6: not freezable
    x = doc["xe_subsystem"]
    assert x["sensitivities"]["upper_test_point_0p15"]["m_cathode_kg"] == pytest.approx(8.1)
    assert x["sensitivities"]["design_life_target"]["m_cathode_kg"] == pytest.approx(6.48)
    terms = {t["term"].split(" ")[0] for t in x["terms"]}
    assert terms >= {"m_Xe", "m_tank", "m_regulator", "m_valves", "m_plumbing", "m_mounting/thermal"}
    assert x["linked_ledger"]["path"] == "docs/budgets/xe_ledger/xe_ledger_v1.json"


def test_diagnostics_split(doc):
    ex = doc["diagnostics"]["h1_ground_diagnostics_EXCLUDED"]
    assert [i["id"] for i in ex] == [f"INS-{n:02d}" for n in range(1, 25)]
    assert all(i["in_flight_mass_model"] is False for i in ex)
    assert doc["diagnostics"]["flight_telemetry_subset_IN"]


# ------------------------------------------------------------------------------------------------ roll-up
def test_rollup_recomputes(doc):
    mp = doc["margin_policy_reused"]
    L = _lines(doc)
    for case in ("low", "high"):
        dry = sum(li["resolved"][case] * (1 + li["resolved"]["mga"]) for _, li in L.values()
                  if li["resolved"][case] is not None and li["mass_class"] == "dry" and li["id"] != "SYS-H.m_harness")
        prop = sum(li["resolved"][case] for _, li in L.values()
                   if li["resolved"][case] is not None and li["mass_class"] == "propellant")
        h = mp["harness_fraction"] / (1 - mp["harness_fraction"]) * dry
        mev = (dry + h) * (1 + mp["system_margin_proposed"]) + prop
        q = doc["rollup"]["cases"]["proposed_20pct"][case]
        assert q["mev_known_lines_kg"] == pytest.approx(mev, abs=1e-5)
        assert q["complete"] is False and q["n_tbd_lines"] > 0
    for c in doc["rollup"]["allocation_checks"]:
        assert c["remaining_kg"] == pytest.approx(c["reference_kg"] - c["mev_known_lines_kg"], abs=1e-5)
    assert {c["reference_kg"] for c in doc["rollup"]["allocation_checks"]} == {34.0, 36.0, 40.0}
    assert doc["rollup"]["sourced_floor_kg"] == pytest.approx(5.4 * 1.02)
    assert "alt_10pct" in doc["rollup"]["cases"]


def test_no_forbidden_content(doc):
    s = JSON_PATH.read_text()
    for k in ("sgb-screen-0", "ensemble_member_id", "\"p5_registration\"", "\"coil_shape\""):
        assert k not in s
    src = SCRIPT.read_text()
    assert "import abep_sim" not in src and "from abep_sim" not in src


# ------------------------------------------------------------------------------------------------ lazy lanes
def test_lanes_absent_is_pending(B, tmp_path):
    d = B.build_document(REPO, lane_root=tmp_path)
    assert all(v["state"] == "ABSENT" and v["status"].startswith("PENDING") for v in d["lane_consumption"]["lanes"].values())
    assert d["lane_consumption"]["adopted_line_items"] == []


def test_lane_demand_adoption_contract(B, tmp_path):
    lane = tmp_path / "docs" / "hardware" / "h2" / "h2_4_ppu_bus"
    lane.mkdir(parents=True)
    demands = [
        {"from": "H2-4", "to": "H2-7", "h2_7_line_item": "R12.m_ppu", "quantity": "PPU mass", "units": "kg",
         "range": [4.0, 6.0], "status": "PRELIMINARY", "evidence_class": "model-derived",
         "basis": "test fixture (not evidence)"},
        {"from": "H2-4", "to": "H2-7", "h2_7_line_item": "R13.m_thermal", "units": "kg", "value": 1.0,
         "status": "PENDING something", "evidence_class": "assumed", "basis": "x"},
        {"from": "H2-4", "to": "H2-7", "quantity": "no line item", "units": "kg", "value": 1.0, "status": "PRELIMINARY",
         "evidence_class": "assumed", "basis": "x"},
        {"from": "H2-4", "to": "H2-3", "h2_7_line_item": "R13.m_thermal", "units": "kg", "value": 1.0,
         "status": "PRELIMINARY", "evidence_class": "assumed", "basis": "x"},
    ]
    (lane / "h2_4_ppu_bus_v1.json").write_text(json.dumps({"interface_demands": demands}))
    d = B.build_document(REPO, lane_root=tmp_path)
    lc = d["lane_consumption"]
    assert lc["lanes"]["H2-4"]["state"] == "PRESENT" and lc["lanes"]["H2-4"]["n_demands_to_h2_7"] == 3
    assert lc["adopted_line_items"] == ["R12.m_ppu"]
    ln = _lines(d)["R12.m_ppu"][1]["resolved"]
    assert (ln["low"], ln["high"], ln["evidence_class"]) == (4.0, 6.0, "model-derived")
    assert ln["superseded_analog"]["low"] == 2.0
    assert [x["adopted"] for x in lc["demands"]] == [True, False, False]
    # the committed-file writer refuses a preview root
    assert B.main(["--lane-root", str(tmp_path)]) == 2
