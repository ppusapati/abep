"""Tests for the auxiliary / DC-bus power comparison (fo_aux_bus_comparison, aux_bus_comparison_v1).

Only this lane's files are exercised: docs/architecture_comparison/aux_bus/ (build script, JSON, schema, Markdown).
The build is pure and takes about one second; nothing here runs a simulation.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUX = os.path.join(ROOT, "docs", "architecture_comparison", "aux_bus")
SCRIPT = os.path.join(AUX, "build_aux_bus.py")
JSON_PATH = os.path.join(AUX, "aux_bus_comparison_v1.json")
MD_PATH = os.path.join(AUX, "AUX_BUS_COMPARISON.md")
SCHEMA_PATH = os.path.join(AUX, "aux_bus_comparison_v1.schema.json")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_aux_bus", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def ab():
    from abep_sim import arch_boundary
    return arch_boundary


def test_check_reproduces_byte_for_byte(builder):
    assert builder.main(["--check"]) == 0


def test_json_validates_against_schema(doc):
    from abep_sim import hard_gates as hg
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    hg.check_schema_keywords(schema)
    assert hg.schema_errors(doc, schema) == []


def test_schema_rejects_a_ledger_without_refusal(doc):
    from abep_sim import hard_gates as hg
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    bad = json.loads(json.dumps(doc))
    del bad["ledgers"][0]["boundary_refusal"]
    assert hg.schema_errors(bad, schema)


def test_inputs_are_pinned_and_verified(builder, doc):
    table = builder.verify_inputs()
    assert {r["key"] for r in table} == set(builder.INPUTS)
    for r in table:
        assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"])
        assert r["lane"]
    assert doc["inputs"] == table
    lanes = {r["lane"] for r in table}
    assert {"lane_11_bus_boundary", "lane_19_cathode_integration", "lane_20_ppu_magnet", "lane_24_hard_gates"} <= lanes


def test_changed_input_raises(builder, monkeypatch):
    key = "electrical_closure_data"
    rel, lane, commit, _sha, role = builder.INPUTS[key]
    patched = dict(builder.INPUTS)
    patched[key] = (rel, lane, commit, "0" * 64, role)
    monkeypatch.setattr(builder, "INPUTS", patched)
    with pytest.raises(builder.AuxBusInputError, match="sha256"):
        builder.verify_inputs()


def test_missing_input_raises(builder, monkeypatch):
    key = "cathode_data"
    _rel, lane, commit, sha, role = builder.INPUTS[key]
    patched = dict(builder.INPUTS)
    patched[key] = ("docs/architecture_comparison/does_not_exist.json", lane, commit, sha, role)
    monkeypatch.setattr(builder, "INPUTS", patched)
    with pytest.raises(builder.AuxBusInputError, match="missing input"):
        builder.verify_inputs()


def test_missing_module_is_a_clear_error(builder):
    with pytest.raises(builder.AuxBusInputError, match="could not be imported"):
        builder._import("abep_sim.no_such_boundary_module")


def test_component_sets_match_boundary(doc, ab):
    assert doc["boundary_version"] == ab.BOUNDARY_VERSION == "bus_power_boundary_v1"
    for arch in ab.ARCHITECTURES:
        assert doc["components_by_architecture"][arch] == list(ab.REQUIRED_COMPONENTS[arch])
        for c in ab.REQUIRED_COMPONENTS[arch]:
            assert arch in doc["components"][c]["in_architectures"]
            for mode in ("steady", "startup"):
                m = doc["components"][c]["modes"][mode]
                assert {"load", "efficiency", "bus_draw", "loss"} <= set(m)
    assert set(doc["components"]) == set(ab.ALL_COMPONENTS)


def test_every_ledger_went_through_bus_power_ledger(doc, ab):
    """Each recorded refusal is the boundary's own message for exactly the sourced inputs that were passed."""
    assert len(doc["ledgers"]) == 6
    for led in doc["ledgers"]:
        if led["status"] == "EVALUATED":
            pytest.fail("no ledger should be evaluable with today's evidence")
        loads, effs = {}, {}
        for c in led["sourced_components_passed"]:
            m = doc["components"][c]["modes"][led["mode"]]
            loads[c] = m["load"]["P_load_W"]
            effs[c] = m["efficiency"]["value"]
        with pytest.raises(ValueError) as exc:
            ab.bus_power_ledger(led["architecture"], loads, effs)
        assert str(exc.value) == led["boundary_refusal"]
        assert set(led["sourced_components_passed"]) | set(led["blocking_components"]) == \
            set(ab.REQUIRED_COMPONENTS[led["architecture"]])
    assert doc["ledger_summary"] == {"attempted": 6, "evaluated": 0, "not_evaluable": 6}


def test_no_absolute_hall_number(doc):
    for mode in ("steady", "startup"):
        assert doc["components"]["hall_discharge"]["modes"][mode]["load"]["status"] == "TBD"
    text = json.dumps(doc)
    # screening candidates appear only in the 'not used' statement, never as a source
    assert text.count("sgb-screen") == 1
    assert any("sgb-screen" in s for s in doc["not_used"])


def test_compressor_and_feed_state_never_filled(doc):
    for mode in ("steady", "startup"):
        m = doc["components"]["compressor"]["modes"][mode]
        assert m["load"]["status"] == "TBD" and m["efficiency"]["status"] == "TBD"
        assert m["bus_draw"]["status"] == "TBD"
        assert "lane_33" in m["load"]["blocking"]
    text = json.dumps(doc)
    for key in ('"P_feed', '"T_feed', '"feed_state"'):
        assert key not in text


def test_values_trace_to_lane20_and_lane19_inputs(doc):
    with open(os.path.join(ROOT, "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json")) as f:
        ec = json.load(f)
    hd_ids = ec["components"]["hall_discharge"]["efficiency_evidence"]
    effs28 = [pt["efficiency"] for e in ec["components"]["hall_discharge"]["entries"]
              if e["id"] in hd_ids and e["id"].endswith("-28Vin") for pt in e["value"]]
    eff = doc["components"]["hall_discharge"]["modes"]["steady"]["efficiency"]
    assert eff["range"] == [min(effs28), max(effs28)]
    assert len(doc["components"]["hall_discharge"]["measured_supply_points_28V"]) == len(effs28)
    for r in doc["components"]["hall_discharge"]["measured_supply_points_28V"]:
        assert r["P_bus_W"] == pytest.approx(r["P_load_W"] / r["efficiency"], rel=1e-5)
        assert r["aux_allowance_below_1500W_W"] == pytest.approx(1500.0 - r["P_bus_W"], abs=1e-2)
    fc = [e for e in ec["components"]["flow_control"]["entries"] if e["id"] == "FC-MOOG-I2R"][0]
    assert doc["components"]["flow_control"]["modes"]["steady"]["load"]["per_energized_xe_pfcv_W"] == \
        [fc["value"]["min"], fc["value"]["max"]]
    heater = doc["components"]["cathode_heater"]["modes"]["startup"]["load"]["range_W"]
    assert heater == [45.0, 305.0]   # CH-PEDRINI17-HC1 (45) ... CH-MONTERO24 (305)
    rf = doc["components"]["rf_source"]["modes"]["steady"]["efficiency"]["range"]
    assert rf == [0.6, 0.92]
    assert doc["components"]["ecr_source"]["modes"]["steady"]["efficiency"]["reference_chain"] == 0.3636


def test_ionization_floor_from_ecr_overlay(doc):
    with open(os.path.join(ROOT, "docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json")) as f:
        ov = json.load(f)
    floors = doc["components"]["rf_source"]["modes"]["steady"]["load"]["lower_bound"]["floors"]
    for k, v in ov["ionization_floor"]["values"].items():
        assert floors[k]["W_per_A"] == v["value_W_per_A"]
    assert "TBD" in doc["components"]["rf_source"]["modes"]["steady"]["load"]["lower_bound"]["air_mixture_feed"]


def test_steady_zero_options_are_conditional(doc):
    h = doc["components"]["cathode_heater"]["modes"]["steady"]
    assert h["load"]["status"] == "ZERO_CONDITIONAL" and "condition" in h["load"]
    for c in ("hall_magnet", "ecr_magnet", "cathode_keeper"):
        opts = doc["components"][c]["modes"]["steady"]["load"]["options"]
        assert any(o.get("status") == "TBD" or o.get("status") == "BRACKET" for o in opts)


def test_differential_classification(doc, ab):
    classes = set(doc["differential"]["classes"])
    for arch in ("rf_hall", "ecr_hall"):
        arm = doc["differential"]["arms"][f"{arch}-hall_only"]
        assert set(arm["terms"]) == set(ab.REQUIRED_COMPONENTS[arch])
        assert {t["class"] for t in arm["terms"].values()} <= classes
        specific = {c for c, t in arm["terms"].items() if t["class"] == "ARCH_SPECIFIC"}
        assert specific == set(ab.PREIONIZER_COMPONENTS[arch])
        assert arm["cancels"] == ["cathode_heater", "compressor"]
        assert arm["terms"]["hall_discharge"]["class"] == "NOT_COMMON"
        assert arm["terms"]["housekeeping"]["class"] == "NOT_COMMON"
        assert set(arm["cancels"]) | set(arm["cancels_conditionally"]) | set(arm["does_not_cancel"]) == \
            set(ab.REQUIRED_COMPONENTS[arch])


def test_headroom_is_symbolic_with_rfp_limit(doc):
    hr = doc["headroom"]
    assert hr["limit_W"] == 1500 and hr["limit_status"] == "RFP_AS_RECORDED"
    assert "P_d" in hr["inequalities"]["general"] and "A_arch" in hr["inequalities"]["general"]
    assert hr["numeric_headroom"].startswith("TBD")


def test_hard_gates_no_elimination(doc):
    from abep_sim import hard_gates as hg
    res = hg.evaluate_all([])
    assert doc["hard_gates"]["eliminated"] == res["eliminated"] == []
    assert doc["hard_gates"]["evidence_submitted"] == []
    for a in ("hall_only", "rf_hall", "ecr_hall"):
        assert doc["hard_gates"]["G2_bus_power_verdicts"][a] == \
            res["architectures"][a]["gates"]["G2_bus_power"]["verdict"] == "UNDETERMINED"


def test_startup_peak_limit_is_proposed(doc):
    assert doc["startup"]["peak_limit"]["status"] == "PROPOSED"
    assert set(doc["startup"]["variants"]) == {"rf_hall", "ecr_hall"}


def test_milestones_and_draft_status(doc, md):
    assert doc["milestones"]["supports"] == ["A"]
    assert doc["milestones"]["to_reach_B"] and doc["milestones"]["to_reach_C"]
    assert doc["status"].startswith("DRAFT")
    assert "DRAFT" in md


FORBIDDEN = [r"\bwinner\s+is\b", r"\bis\s+the\s+winner\b", r"\bwins\b", r"\bbest\s+architecture\b", r"\bsuperior\b",
             r"\boutperform", r"\brecommended\s+architecture\b", r"\bpreferred\s+architecture\s+is\b",
             r"\bselected\s+as\s+(the\s+)?baseline\b"]


def test_no_ranking_language(doc, md):
    text = md + json.dumps(doc)
    for pat in FORBIDDEN:
        assert not re.search(pat, text, flags=re.IGNORECASE), pat


def test_tbd_register_covers_every_tbd_component(doc, ab):
    reg = {t["component"] for t in doc["tbd_register"]}
    for c in ab.ALL_COMPONENTS:
        assert c in reg, c
