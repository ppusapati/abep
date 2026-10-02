"""A9.19 / A9.20 owner decisions applied to P2 (docs/experiments/hall_icp/p2_impedance_map/): the one ICP is mapped for
both supply modes (AIR_PRIMARY N2-family, XE_CONTINGENCY Xe); C1 only GROUND_ONLY_LAB_EQUIPMENT. Records are the
SYNTHETIC fixtures of tests/test_p2_impedance_prep.py (never data)."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from abep_sim.design import a9_19_architecture as a919

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "experiments" / "hall_icp" / "p2_impedance_map"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


T = _load("p2_prep_fixtures_for_a9_19", REPO / "tests" / "test_p2_impedance_prep.py")


@pytest.fixture(scope="module")
def red():
    return _load("p2_reducer_a9_19", LANE / "p2_impedance_reducer.py")


@pytest.fixture(scope="module")
def case(red):
    return T.case.__wrapped__(red) if hasattr(T.case, "__wrapped__") else T.case(red)


@pytest.fixture(scope="module")
def d():
    return json.loads((LANE / "p2_impedance_prep_v1.json").read_text(encoding="utf-8"))


def test_p2_constants_mirror_design_layer(red):
    assert red.SUPPLY_MODES == a919.SUPPLY_MODES
    assert red.BENCH_SUPPLY_MODE == a919.BENCH_SUPPLY_MODE
    assert red.C1_LAB_STATUS == a919.GROUND_ONLY_LAB_EQUIPMENT
    assert red.TAG_XE in red.EVIDENCE_TAGS
    assert {red.supply_mode_of_tag(t) for t in red.EVIDENCE_TAGS} == {"AIR_PRIMARY", "XE_CONTINGENCY",
                                                                       a919.BENCH_SUPPLY_MODE, None}
    with pytest.raises(red.RecordError):
        red.supply_mode_of_tag("NOT_A_TAG")


def test_p2_records_both_supply_modes(red, case):
    cal, rec = case
    out = {}
    for gas in ("N2", "Xe", "xenon", "O2"):
        r = copy.deepcopy(rec)
        r["factors"]["gas"] = gas
        out[gas] = red.reduce_record(r, {"SYN": cal})["evidence_tag"]
    assert out["N2"] == red.TAG_N2 and red.supply_mode_of_tag(out["N2"]) == "AIR_PRIMARY"
    assert out["Xe"] == out["xenon"] == red.TAG_XE and red.supply_mode_of_tag(out["Xe"]) == "XE_CONTINGENCY"
    assert red.supply_mode_of_tag(out["O2"]) == "AIR_PRIMARY"
    # declared supply mode must agree with the gas
    r = copy.deepcopy(rec)
    r["factors"].update(gas="Xe", supply_mode="XE_CONTINGENCY")
    assert red.reduce_record(r, {"SYN": cal})["evidence_tag"] == red.TAG_XE
    r["factors"]["supply_mode"] = "AIR_PRIMARY"
    with pytest.raises(red.RecordError, match="A9.19"):
        red.reduce_record(r, {"SYN": cal})
    r = copy.deepcopy(rec)
    r["factors"].update(gas="N2", supply_mode="XE_CONTINGENCY")
    with pytest.raises(red.RecordError):
        red.reduce_record(r, {"SYN": cal})
    # an envelope never mixes supply-mode tags (unchanged rule)
    a, b = copy.deepcopy(rec), copy.deepcopy(rec)
    a["factors"]["gas"], b["factors"]["gas"] = "N2", "Xe"
    oa, ob = red.reduce_record(a, {"SYN": cal}), red.reduce_record(b, {"SYN": cal})
    with pytest.raises(red.RecordError):
        red.mismatch_envelope([oa, ob], ["DUMMY_LOAD"])


def test_p2_package_records_a9_19(d):
    inc = d["a9_19_incorporation"]
    assert inc["c1"] == {"status": "GROUND_ONLY_LAB_EQUIPMENT", "p2_operates_c1": False}
    assert inc["flight_architecture"]["conventional_hollow_cathode"] == "NONE"
    assert inc["icp_feed_gas_baseline"]["primary"] == "G-REUSE"
    assert "XE_CONTINGENCY" in inc["evidence_tag_supply_modes"].values()
    rows = [o for o in d["owner_answers_applied"] if isinstance(o["ref"], dict)
            and o["ref"].get("decision") in ("A9.19", "A9.20")]
    assert {o["ref"]["decision"] for o in rows} == {"A9.19", "A9.20"}
    for o in rows:
        assert o["ref"]["json_sha256"] == a919.DECISIONS[o["ref"]["decision"]]["json_sha256"]
        assert o["ref"]["md_sha256"] == a919.DECISIONS[o["ref"]["decision"]]["md_sha256"]
        assert "PASS" not in o["how"]
    pins = {p["path"] for p in d["decision_pins"]}
    for k in ("A9.19", "A9.20"):
        assert a919.DECISIONS[k]["json"] in pins and a919.DECISIONS[k]["md"] in pins
