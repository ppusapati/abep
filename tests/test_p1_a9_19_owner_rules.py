"""A9.19 / A9.20 owner decisions applied to the P1 ICP bench (docs/experiments/hall_icp/p1_icp_bench/): C1 only as
GROUND_ONLY_LAB_EQUIPMENT; P1-S6 C1_NOT_INSTALLED logic unchanged; ICP ignition / operation records allow both supply
modes (AIR_PRIMARY N2-family, XE_CONTINGENCY Xe). Every record below is a SYNTHETIC fixture (never data)."""
from __future__ import annotations

import copy
import importlib.util
import json
import os

import pytest

from abep_sim.design import a9_19_architecture as a919

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "docs", "experiments", "hall_icp", "p1_icp_bench")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load(os.path.join(ROOT, "tests", "test_p1_icp_bench.py"), "p1_bench_fixtures_for_a9_19")


@pytest.fixture(scope="module")
def red():
    return _load(os.path.join(DIR, "p1_reducer.py"), "p1_reducer_a9_19")


@pytest.fixture(scope="module")
def doc():
    with open(os.path.join(DIR, "p1_icp_bench_v1.json"), encoding="utf-8") as f:
        return json.load(f)


def test_p1_a9_19_constants_mirror_design_layer(red):
    assert red.SUPPLY_MODES == a919.SUPPLY_MODES
    assert red.C1_LAB_STATUS == a919.GROUND_ONLY_LAB_EQUIPMENT
    assert red.P1_SUPPLY_MODE == a919.BENCH_SUPPLY_MODE
    for mode, names in a919.SUPPLY_MODE_GASES.items():
        assert tuple(red.SUPPLY_MODE_GASES[mode]) == tuple(names)
    assert red.C1_CONFIGURATIONS == ("C1_NOT_INSTALLED", "C1_INSTALLED_DISCONNECTED")      # P1-S6 logic unchanged
    assert red.I_D_MAX_ELECTRON_SOURCE == "C1_CONVENTIONAL_REFERENCE"                    # ground characterization


def test_p1_icp_records_allow_both_supply_modes(red):
    assert red.icp_supply_mode("N2", "AIR_PRIMARY") == "AIR_PRIMARY"
    assert red.icp_supply_mode("Nitrogen") == "AIR_PRIMARY"
    assert red.icp_supply_mode("Xe", "XE_CONTINGENCY") == "XE_CONTINGENCY"
    assert red.icp_supply_mode("Ar", red.P1_SUPPLY_MODE) == red.P1_SUPPLY_MODE
    for gas, mode in (("Xe", "AIR_PRIMARY"), ("N2", "XE_CONTINGENCY"), ("Ar", "AIR_PRIMARY"), ("N2", "XE_PRIMARY")):
        with pytest.raises(red.SupplyModeError):
            red.icp_supply_mode(gas, mode)
    with pytest.raises(red.SupplyModeError):
        red.icp_supply_mode("He")


def test_p1_ignition_and_operating_records_supply_mode(red):
    ign = B.synth_ign("SYNTH-A919-IGN")
    red.validate_ignition(ign)                                        # no supply_mode: unchanged behaviour
    r = copy.deepcopy(ign)
    r["supply_mode"] = red.P1_SUPPLY_MODE
    red.validate_ignition(r)
    r["supply_mode"] = "XE_CONTINGENCY"                               # contradicts Ar
    with pytest.raises(red.SupplyModeError):
        red.validate_ignition(r)
    for gas, mode in (("N2", "AIR_PRIMARY"), ("Xe", "XE_CONTINGENCY")):
        r = copy.deepcopy(ign)
        r.update(gas=gas, supply_mode=mode)
        with pytest.raises(red.P1RecordError, match=mode) as e:       # valid mode, reduced by its own stage
            red.validate_ignition(r)
        assert not isinstance(e.value, red.SupplyModeError)
        assert red.SUPPLY_MODE_STAGE[mode] in str(e.value)
    op = B.synth_op()
    red.validate_operating_point(op)
    o = copy.deepcopy(op)
    o["supply_mode"] = "AIR_PRIMARY"
    with pytest.raises(red.SupplyModeError):
        red.validate_operating_point(o)
    o.update(gas="Xe", supply_mode="XE_CONTINGENCY")
    with pytest.raises(red.P1RecordError, match="XE_CONTINGENCY"):
        red.validate_operating_point(o)


def test_p1_schema_carries_supply_mode(red):
    with open(os.path.join(DIR, "p1_bench_record_schema_v1.json"), encoding="utf-8") as f:
        s = json.dumps(json.load(f))
    for m in ("AIR_PRIMARY", "XE_CONTINGENCY", red.P1_SUPPLY_MODE):
        assert m in s


def test_p1_c1_ground_only_in_package(doc):
    cfg = " ".join(doc["scope"]["configurations"])
    assert "GROUND_ONLY_LAB_EQUIPMENT" in cfg and "GROUND_REFERENCE" in cfg and "CONTROL_FALLBACK" not in cfg
    ifd = {d["id"]: d for d in doc["interface_demands"]}
    assert "GROUND_ONLY_LAB_EQUIPMENT" in ifd["IF-P1-21"]["status"]
    hw = [h for h in doc["hardware_readiness"] if "c1_status" in h]
    assert len(hw) == 1 and hw[0]["c1_status"].startswith("GROUND_ONLY_LAB_EQUIPMENT")
    assert hw[0]["item"].startswith("C1 (hall_c1_reference)")       # text read back by immutable RFQ v2, unchanged
    m16 = {m["row"]: m for m in doc["m16_impact"]}
    assert "GROUND_ONLY_LAB_EQUIPMENT" in m16[11]["impact"]
    inc = doc["a9_19_incorporation"]
    assert inc["c1"]["status"] == "GROUND_ONLY_LAB_EQUIPMENT"
    assert inc["flight_architecture"]["conventional_hollow_cathode"] == "NONE"
    assert inc["icp_feed_gas_baseline"]["primary"] == "G-REUSE"
    assert "C1 GROUND_ONLY_LAB_EQUIPMENT" in inc["statuses"]


def test_p1_owner_answers_applied_cite_a9_19_a9_20(doc):
    rows = [r for r in doc["owner_answers_applied"] if r.get("decision") in ("A9.19", "A9.20")]
    assert {r["decision"] for r in rows} == {"A9.19", "A9.20"}
    for r in rows:
        assert r["decision_json_sha256"] == a919.DECISIONS[r["decision"]]["json_sha256"]
        assert r["decision_md_sha256"] == a919.DECISIONS[r["decision"]]["md_sha256"]
        assert r["how_applied"] and "PASS" not in r["how_applied"]
    pinned = {p["path"] if isinstance(p, dict) else p[0] for p in doc["authority_pins"]}
    for k in ("A9.19", "A9.20"):
        assert a919.DECISIONS[k]["json"] in pinned and a919.DECISIONS[k]["md"] in pinned
