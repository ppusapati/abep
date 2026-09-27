"""W2 LOCK-1 decision brief (fo_lock1_decision_brief): reproducibility, completeness of D-01..D-15, and that the
draft is never marked locked. Pure: no Julia, no other lane's worktree, only committed repository files."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs" / "architecture_comparison" / "lock1"
BUILDER = HERE / "build_lock1_brief.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("_test_lock1_builder", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


@pytest.fixture(scope="module")
def outputs(builder):
    return builder.outputs()


@pytest.fixture(scope="module")
def brief():
    return json.loads((HERE / "lock1_decision_brief_v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def draft():
    return json.loads((HERE / "LOCK1_DRAFT.json").read_text(encoding="utf-8"))


def test_build_reproduces_committed_files(outputs):
    for path, text in outputs.items():
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8") == text, f"{path.name} does not reproduce (run the builder)"


def test_every_decision_has_options_consequences_and_proposed_recommendation(brief):
    ids = [d["id"] for d in brief["decisions"]]
    assert ids == [f"D-{i:02d}" for i in range(1, 16)]
    for d in brief["decisions"]:
        assert d["question"].strip(), d["id"]
        assert len(d["options"]) >= 2, d["id"]
        opt_ids = {o["id"] for o in d["options"]}
        assert len(opt_ids) == len(d["options"]), d["id"]
        for o in d["options"]:
            assert o["id"].startswith(d["id"] + "-"), o["id"]
            assert o["consequences"], f"{o['id']} has no consequences"
        rec = d["recommendation"]
        assert rec["status"] == "PROPOSED", d["id"]
        assert rec["option"] in opt_ids, d["id"]
        assert rec["rationale"].strip(), d["id"]
        assert d["depends_on"], d["id"]
        assert d["status"] == "OPEN_OWNER_DECISION", d["id"]
        assert d["owner_choice"] is None, d["id"]


def test_pivot_items_open_and_proposed(brief):
    ids = [p["id"] for p in brief["pivot_items"]]
    assert ids == ["P-01", "P-02", "P-03", "P-04"]
    for p in brief["pivot_items"]:
        assert len(p["options"]) >= 2 and all(o["consequences"] for o in p["options"])
        assert p["recommendation"]["status"] == "PROPOSED"
        assert p["owner_choice"] is None
    # the RFP reading (lane-24 OD1) is the owner's: no recommendation
    assert brief["pivot_items"][3]["recommendation"]["option"] is None


def test_nothing_is_marked_locked(builder, brief, draft):
    for doc in (brief, draft):
        assert doc["status"] == "DRAFT_PENDING_OWNER_SIGNATURE"
        assert doc["locked"] is False
        assert builder.lock_violations(doc) == []
    assert all(v is None for v in draft["signature"].values())
    assert all(d["owner_choice"] is None for d in draft["decisions"] + draft["pivot_items"])
    text = json.dumps(draft) + json.dumps(brief)
    assert not re.search(r'"status":\s*"(LOCKED|SIGNED|REGISTERED)"', text)
    assert not re.search(r'"locked":\s*true', text)


def test_draft_points_to_brief_by_sha(draft):
    import hashlib
    raw = (HERE / "lock1_decision_brief_v1.json").read_bytes()
    assert draft["decision_source"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert [d["id"] for d in draft["decisions"]] == [f"D-{i:02d}" for i in range(1, 16)]


def test_numbers_carry_unit_evidence_source(builder, brief):
    assert builder.numeric_leaf_errors(brief) == []


def test_absolute_gate_consistent_with_rfp_and_lane24(brief):
    g = brief["absolute_thrust_gate"]
    assert g["status"] == "PROPOSED"
    assert g["limits"]["thrust_min"]["value"] == 12
    assert g["limits"]["thrust_max"]["value"] == 25
    assert g["limits"]["power_max"]["value"] == 1500
    c = g["consistency_with_lane24"]
    assert c["G1.thrust_floor"]["comparator"] == ">="
    assert c["G2.bus_power_max"]["comparator"] == "<"
    assert "measurement_similar_hardware" not in c["G1.thrust_floor"]["pass_sufficient_bases"]
    # one-sided coverage factor decreases with dof and ends at the normal quantile
    k = [v["value"] for v in g["parameters"]["k1"].values()]
    assert k == sorted(k, reverse=True) and abs(k[-1] - 1.6448536) < 1e-6
    # requirement table: larger margin -> larger allowed uncertainty
    fl = g["uncertainty_requirement"]["thrust_floor_12mN"]
    col = "nu=inf (Type B dominated)"
    vals = [fl[m][col]["u_c_max_abs"]["value"] for m in ("margin=0.05", "margin=0.1", "margin=0.2")]
    assert vals == sorted(vals)


def test_phases_keep_paired_design_and_define_extinction(brief):
    ph = brief["phases"]
    p2 = ph["phase_2"]["paired_randomised_structure"]
    assert any("seeded" in s for s in p2) and any("bracketed" in s for s in p2)
    assert any("even n" in s for s in p2)
    ex = ph["phase_1"]["extinction"]
    assert ex["threshold_id"] == "THR-EXTINCTION"
    assert ph["phase_3"]["relation_to_R_arch"].startswith("none")


def test_s1_to_lock2_maps_measurements_to_parameters(brief):
    rows = brief["s1_to_lock2"]["rows"]
    sets = " ".join(r["sets_lock2_parameter"] for r in rows)
    for key in ("u_inst", "u_Tscale", "u_src", "ext_window", "T-SETTLE"):
        assert key in sets, key
    assert all(r["stage"].startswith("S1") for r in rows)


def test_milestones_and_no_winner(brief):
    m = brief["milestones"]
    assert m["supports"] == ["A"] and m["to_reach_B"] and m["to_reach_C"]
    text = json.dumps(brief)
    for arch in ("hall_only", "rf_hall", "ecr_hall"):
        assert arch in text
    assert not re.search(r"\bwinner\s+is\b|\bbest\s+architecture\b", text, flags=re.I)
