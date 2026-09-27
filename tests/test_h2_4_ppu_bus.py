"""Tests for the H2-4 PPU and bus allocation deliverable (docs/hardware/h2/h2_4_ppu_bus/).

Only this lane's files are exercised. Nothing here imports or reads a parallel lane (lazy PENDING references only).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(ROOT, "docs", "hardware", "h2", "h2_4_ppu_bus")
BUILDER = os.path.join(LANE, "build_h2_4_ppu_bus.py")
OUT_JSON = os.path.join(LANE, "h2_4_ppu_bus_v1.json")
OUT_MD = os.path.join(LANE, "H2_4_PPU_BUS.md")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_h2_4_ppu_bus", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_builder()


@pytest.fixture(scope="module")
def data():
    with open(OUT_JSON, encoding="utf-8") as f:
        return json.load(f)


def test_outputs_reproduce_byte_for_byte(mod):
    d = mod.build(mod.load_inputs())
    assert open(OUT_JSON, encoding="utf-8").read() == mod.dumps(d)
    assert open(OUT_MD, encoding="utf-8").read() == mod.render_md(d)


def test_decision_pins_are_the_owner_files(data):
    pins = {p["key"]: p for p in data["decision_pins"]}
    assert pins["A5"]["sha256"] == "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"
    assert pins["A6"]["sha256"] == "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"
    assert pins["A7"]["sha256"] == "dae69983d9aeeb4838d9ff973a5f824c973219f8cc528adfb12717c4bb92c925"
    assert pins["G0"]["sha256"] == "4bd0fb4312fba97b18bba92ca0726133947ea6d86327f5e1360ea6af2b163523"


def test_no_mutable_governance_pinned(mod, data):
    banned = ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state")
    for k, (path, _sha, _role) in mod.INPUTS.items():
        assert not any(b in path for b in banned), path
    assert data["compliance"]["pins_mutable_governance"] is False


def test_changed_pin_refuses(mod, monkeypatch):
    bad = dict(mod.INPUTS)
    path, _sha, role = bad["A5"]
    bad["A5"] = (path, "0" * 64, role)
    monkeypatch.setattr(mod, "INPUTS", bad)
    with pytest.raises(mod.H24InputError):
        mod.load_inputs()


def test_missing_input_refuses(mod, monkeypatch):
    bad = dict(mod.INPUTS)
    bad["EC"] = ("docs/does/not/exist.json", "0" * 64, "x")
    monkeypatch.setattr(mod, "INPUTS", bad)
    with pytest.raises(mod.H24InputError):
        mod.load_inputs()


def test_missing_entry_refuses(mod):
    inp = mod.load_inputs()
    broken = copy.deepcopy(inp)
    broken["EC"]["components"]["flow_control"]["entries"] = [
        e for e in broken["EC"]["components"]["flow_control"]["entries"] if e["id"] != "FC-MOOG-I2R"]
    with pytest.raises(mod.H24InputError):
        mod.build(broken)


def test_components_match_boundary_exactly(data):
    from abep_sim import arch_boundary as ab
    assert data["boundary_version"] == ab.BOUNDARY_VERSION == "bus_power_boundary_v1"
    listed = [r["component"] for r in data["load_list"]]
    assert listed == list(ab.ALL_COMPONENTS)
    steady = [r["component"] for r in data["bus_profiles"]["STEADY"]["rows"]]
    assert steady == list(ab.COMMON_COMPONENTS)
    assert data["architectures"] == list(ab.ARCHITECTURES) == ["hall_only", "rf_hall", "ecr_hall"]


def test_every_load_row_is_allocation_or_parameter(data):
    for r in data["load_list"]:
        assert r["kind"] in ("ALLOCATION", "PARAMETER")
    hd = data["load_list"][0]
    assert hd["component"] == "hall_discharge" and hd["kind"] == "ALLOCATION"
    for r in data["load_list"][-3:]:
        assert r["baseline_flight_hardware"] is False


def test_parameter_table_fields(mod, data):
    ids = [p["id"] for p in data["design_parameters"]]
    assert len(ids) == len(set(ids))
    for p in data["design_parameters"]:
        assert re.fullmatch(r"H24-\d\d", p["id"])
        for k in ("name", "value", "units", "basis", "source", "evidence_class", "status", "representativeness",
                  "configuration_items"):
            assert k in p, (p["id"], k)
        assert p["basis"] in mod.BASES
        assert p["representativeness"] in mod.REPRESENTATIVENESS
        assert p["evidence_class"] in mod.EVIDENCE_CLASSES or p["evidence_class"].startswith("TBD - requires")
        assert (p["status"] == "PRELIMINARY" or p["status"].startswith("PENDING docs/")
                or p["status"].startswith("TBD - requires ")), p["id"]
        assert isinstance(p["source"], str) and p["source"]
        if p["value"] is None:
            assert p["status"] != "PRELIMINARY" or p["evidence_class"].startswith("TBD")
        known = {"H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR", "DIV-1"}
        assert set(p["configuration_items"]) <= known, p["id"]


def test_all_three_representativeness_classes_used(data):
    reps = {p["representativeness"] for p in data["design_parameters"]}
    assert reps == {"FLIGHT-REPRESENTATIVE", "H-1 TEST-ARTICLE-ONLY", "GROUND/FACILITY-ONLY"}


def test_allocation_arithmetic(data):
    p = {x["id"]: x for x in data["design_parameters"]}
    assert p["H24-01"]["value"] == 1500.0
    assert p["H24-02"]["value"] == [1300.0, 1350.0]
    assert p["H24-03"]["value"] == [150.0, 200.0]
    eta = p["H24-05"]["value"]
    assert eta == [0.8609, 0.9072]
    env = p["H24-23"]["value"]
    assert math.isclose(env["envelope_high_W"], 60 / 0.6 + 60 / 0.8 + 1.46 / 0.8 + 300.0 + 30 / 0.7, rel_tol=1e-5)
    assert math.isclose(env["permanent_magnet_keeper_off_W"], 1.46 / 0.8 + 300.0 + 30 / 0.7, rel_tol=1e-5)
    lo, hi = p["H24-24"]["value"]
    assert math.isclose(lo, 0.8609 * (1300 - env["envelope_high_W"]), rel_tol=1e-5)
    assert math.isclose(hi, 0.9072 * (1350 - env["permanent_magnet_keeper_off_W"]), rel_tol=1e-5)
    # the discharge allocation stays inside the measured analog supply span (<= 1 kW)
    assert hi <= 1000.0


def test_headroom_grid_formulae(data):
    h = data["margin_table"]["headroom"]
    for r in h["full_grid"]:
        b, a, f = r["B_alloc_W"], r["A_common_W"], r["f_discharge_bus_share"]
        assert math.isclose(r["H_inside_allocation_W"], b * (1 - f) - a, rel_tol=1e-5, abs_tol=1e-3)
        assert math.isclose(r["H_inside_requirement_W"], 1500.0 - f * b - a, rel_tol=1e-5, abs_tol=1e-3)
        assert r["H_inside_requirement_W"] >= r["H_inside_allocation_W"]
    assert "NOT concluded" in h["no_conclusion"]
    assert "owner" in h["readings"]["which_reading"]


def test_three_bus_profiles_present(data):
    bp = data["bus_profiles"]
    assert set(bp) == {"STEADY", "STARTUP", "PEAK"}
    names = [p["name"] for p in bp["STARTUP"]["phases"]]
    order = ["preheat", "keeper ignition", "magnet ramp", "Xe discharge ignition", "transition", "nominal steady"]
    pos = [next(i for i, n in enumerate(names) if o in n) for o in order]
    assert pos == sorted(pos)
    a5 = json.load(open(os.path.join(ROOT, "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_"
                                          "architecture.json"), encoding="utf-8"))
    for p in bp["STARTUP"]["phases"]:
        assert p["a5_mode"] in a5["operating_modes"]["sequence"]
    ids = {x["id"] for x in bp["PEAK"]["overlaps"]}
    assert {"PK-1", "PK-2", "PK-3", "PK-4"} <= ids
    assert len(bp["PEAK"]["inrush"]) >= 4


def test_startup_known_terms_monotone_until_ignition(data):
    ph = {p["id"]: p for p in data["bus_profiles"]["STARTUP"]["phases"]}
    seq = [ph[i]["known_bus_W_upper"] for i in ("SU-1", "SU-2", "SU-3", "SU-4")]
    assert seq == sorted(seq)
    assert seq[-1] < 1500.0


def test_h2_sections_present(data, mod):
    for k in ("interface_demands", "hard_incompatibility_check", "architecture_changing_blockers_touched", "m16_rows",
              "h3_procurement_inputs", "h4_test_inputs", "milestone_statement"):
        assert data[k], k
    for r in data["interface_demands"]:
        assert {"from", "to", "quantity", "value", "units", "status"} <= set(r)
        assert "H2-4" in (r["from"], r["to"])
    assert data["hard_incompatibility_check"]["verdict"] == "none found"
    assert data["hard_incompatibility_check"]["checks"]
    blk = {b["blocker"] for b in data["architecture_changing_blockers_touched"]}
    assert blk == {1, 2, 3}
    for r in data["m16_rows"]:
        assert r["proposed_state"] in mod.M16_STATES
        if r["proposed_state"] == "BLOCKED":
            assert isinstance(r["blocking_item"], str) and r["blocking_item"]
            assert r["rollup"] in mod.ROLLUPS
        else:
            assert "not BLOCKED" in r["blocking_item"]
    assert set(data["milestone_statement"]) == {"A", "B", "C"}


def test_pending_refs_point_to_lane_paths(data, mod):
    s = json.dumps(data)
    for m in re.finditer(r"PENDING (docs/[^\s\"()]+)", s):
        assert any(m.group(1).startswith(v.split(" ")[0]) for v in mod.LANES.values()), m.group(1)


def test_builder_never_reads_parallel_worktrees():
    src = open(BUILDER, encoding="utf-8").read()
    assert ".claude/worktrees" not in src
    assert "import abep_sim" not in src and "from abep_sim" not in src


def test_no_forbidden_content(data):
    s = json.dumps(data).lower()
    assert "winner" not in s.replace("no winner", "").replace("no_winner", "")
    for bad in ("sgb-screen", "plasma_devices.hall", "scaledgaussianbohm", "preferred architecture"):
        assert bad not in s, bad
    # P5 calibration nuisance items are never design variables
    for bad in ("l38", "l32-anode", "beam-efficiency reading"):
        assert bad not in s, bad
    assert data["compliance"]["no_winner"] is True
    assert data["compliance"]["no_hall_closure"] is True


def test_external_sources_have_url_and_sha(data):
    for k, v in data["external_sources"].items():
        assert v["url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{64}", v["sha256_accessed"])
        assert v["access"] == "open"


def test_p_bus_reconstruction_rule(data):
    pr = data["h1_vs_flight"]["P_bus_reconstruction"]
    assert "pre-registered" in pr["eta_source"]
    assert any("wall-plug" in n for n in pr["never"])
    assert any("discharge-only" in n for n in pr["never"])
    assert "PARTIAL_BOUNDARY" in pr["labels"]
