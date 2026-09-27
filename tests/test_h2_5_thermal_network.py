"""H2-5 thermal network (fo_h2_5_thermal_network): structure, evidence discipline, determinism and solver checks.

Checks docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json (+ the .md) against a fresh run of the committed
deterministic builder, the pinned decision hashes, the required H2 deliverable sections (a)-(h), energy closure of the
steady-state solves, the corner-envelope/LHS consistency, the hard-incompatibility rule and the no-silent-default rule.
Other lanes' in-progress paths are never required (PENDING references only).
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE_DIR = os.path.join(ROOT, "docs", "hardware", "h2", "h2_5_thermal_network")
JSON_PATH = os.path.join(LANE_DIR, "h2_5_thermal_network_v1.json")
MD_PATH = os.path.join(LANE_DIR, "H2_5_THERMAL_NETWORK.md")
SCRIPT = os.path.join(LANE_DIR, "build_h2_5_thermal_network.py")

ARCHS = ["hall_only", "rf_hall", "ecr_hall"]
EVIDENCE = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
BASES = {"requirement", "allocation", "analog", "derived", "assumed", "pending"}
SCOPES = {"FLIGHT_REPRESENTATIVE", "H1_TEST_ARTICLE_ONLY", "GROUND_FACILITY_ONLY"}
M16_STATES = {"READY", "RUNNING", "BLOCKED", "VERIFIED"}
ROLLUPS = {"architecture blocker", "hardware-definition blocker", "procurement blocker", "test-readiness blocker",
           "proposal-only documentation gap"}
W3_IDS = {"H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR", "IP-UP", "IP-DN", "HALL_INLET_Z0"}


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("build_h2_5_thermal_network", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rebuilt(gen):
    return gen.build()


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------------------------------- identity / determinism
def test_identity(doc):
    assert doc["lane"] == "H2_5"
    assert doc["follow_on"] == "fo_h2_5_thermal_network"
    assert doc["trigger"] == "T_H2_5_THERMAL_NETWORK"
    assert doc["architectures"] == ARCHS
    assert doc["status"].startswith("DRAFT")


def test_regeneration_is_identical(doc, rebuilt, gen):
    assert json.loads(json.dumps(rebuilt)) == doc
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == gen.render_md(rebuilt)


def test_pinned_hashes_match_repository(doc):
    for key, pin in doc["pinned_inputs"].items():
        path = os.path.join(ROOT, pin["path"])
        assert os.path.exists(path), key
        assert _sha(path) == pin["sha256"], key
    names = " ".join(p["path"] for p in doc["pinned_inputs"].values())
    for forbidden in ("lane_registry_v1.json", "trigger_registry_v1.json", "runtime_state.json", "trigger_ledger", "fired_triggers"):
        assert forbidden not in names
    for k in ("A5", "A6", "A7", "G0"):
        assert k in doc["pinned_inputs"]


def test_external_sources_are_recorded(doc):
    for sid, s in doc["external_sources"].items():
        assert s["citation"] and s["url"].startswith("https://") and s["access"]
        assert s["sha256"] is None and s.get("sha256_note") or len(s["sha256"]) == 64


# ------------------------------------------------------------------------------------------- (a) design parameters
def test_design_parameter_rows(doc):
    rows = doc["design_parameters"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for r in rows:
        assert r["id"].startswith("H25-")
        assert r["basis"] in BASES and r["evidence_class"] in EVIDENCE and r["scope"] in SCOPES, r["id"]
        assert r["source"] and r["status"] and r["units"] is not None, r["id"]
        if r["value"] is None:
            assert r["status"].startswith(("TBD", "PENDING")), r["id"]
        if r["status"].startswith("PENDING"):
            assert "docs/" in r["status"] or "schemas/" in r["status"], r["id"]


def test_no_forbidden_performance_sources(doc):
    blob = json.dumps(doc["design_parameters"]) + json.dumps(doc["limits"])
    for bad in ("sgb-screen", "plasma_devices", "HallMap", "hall_map", "default_nodes", "screening_candidates"):
        assert bad not in blob, bad
    for nuisance in ("L38", "L32", "registration", "beam-efficiency reading", "coil shape"):
        assert nuisance not in blob, nuisance


def test_discharge_heat_is_parametric_analog(doc):
    pm = {r["key"]: r for r in doc["design_parameters"]}
    for k in ("f_anode", "f_walls", "f_pole"):
        assert pm[k]["basis"] == "analog" and isinstance(pm[k]["value"], list)
        assert 0.0 <= pm[k]["value"][0] < pm[k]["value"][1] < 1.0
    assert pm["P_d_max_W"]["value"] <= pm["P_bus_alloc_W"]["value"][1]
    assert abs(pm["f_anode"]["value"][0] - 257.9 / 12500) < 1e-4       # HERMeS Table 3 correlated anode
    assert abs(pm["f_walls"]["value"][0] - 549.1 / 12500) < 1e-4       # HERMeS Table 3 correlated DC walls
    assert abs(pm["f_anode"]["value"][1] - 30.0 / 180.0) < 1e-4        # Es ~30 eV / V_d,min 180 V


def test_uses_existing_ci_ids(doc):
    blob = json.dumps(doc["configuration_items_used"]) + json.dumps(doc["node_list"])
    for ci in ("H-1", "MC-1", "C-1", "IP-DN", "IP-UP", "HALL_INLET_Z0", "PIM-0"):
        assert ci in blob
    for n in doc["node_list"]:
        assert n["scope"] in SCOPES


def test_required_nodes_present(doc):
    names = " ".join(n["name"] for n in doc["node_list"]).lower()
    for want in ("anode", "inner channel wall", "outer channel wall", "core", "shell", "inner coil", "outer coil",
                 "emitter", "keeper", "cathode body", "pre-ionizer", "ppu", "compressor", "plenum", "mounting"):
        assert want in names, want


# ------------------------------------------------------------------------------------------- physics helpers
def test_view_factor_and_constants(gen):
    L, h = 0.086, 0.010
    vf = gen.slot_view_factors(L, h)
    diag = math.hypot(L, h)
    f_bottom_side = (h + L - diag) / (2 * h)
    assert abs(vf["F_anode_to_exit"] + 2 * f_bottom_side - 1.0) < 1e-12
    assert abs(h * f_bottom_side - L * vf["F_wall_to_exit"]) < 1e-12        # reciprocity
    assert abs(gen.LORENZ_SOMMERFELD - 2.443e-8) < 1e-11
    assert abs(gen.nist_k("OFHC_copper_RRR100", 293.15) - 397) < 5
    with pytest.raises(ValueError):
        gen.nist_k("SS304", 400.0)
    with pytest.raises(ValueError):
        gen.fe_rho_ohm_m(1100.0 + gen.T0C)


def test_missing_input_raises(gen):
    rows = gen.build_parameters()
    pm = gen.param_map(rows)
    fx = gen.fixed_inputs(pm)
    rg = gen.ranges_for("ground", pm)
    x = {k: 0.5 * (lo + hi) for k, (lo, hi) in rg.items()}
    T, info = gen.run(x, fx, "ground", "z93_white_inorganic", 1350.0)
    assert abs(info["load_W"] - info["rejected_W"]) < 1e-6 * info["load_W"]
    bad = dict(x)
    del bad["f_walls"]
    with pytest.raises(ValueError):
        gen.run(bad, fx, "ground", "z93_white_inorganic", 1350.0)
    pm2 = copy.deepcopy(pm)
    pm2["eps_BN"]["value"] = None
    with pytest.raises(ValueError):
        gen.fixed_inputs(pm2)
    geo = dict(x)
    geo["D_core_m"] = 0.08
    with pytest.raises(ValueError):
        gen.run(geo, fx, "ground", "z93_white_inorganic", 1350.0)


def test_heat_monotonic_in_discharge_power(gen):
    rows = gen.build_parameters()
    pm = gen.param_map(rows)
    fx = gen.fixed_inputs(pm)
    x = {k: 0.5 * (lo + hi) for k, (lo, hi) in gen.ranges_for("orbit_hot", pm).items()}
    T1, _ = gen.run(x, fx, "orbit_hot", "sandblasted_stainless", 675.0)
    T2, _ = gen.run(x, fx, "orbit_hot", "sandblasted_stainless", 1350.0)
    for n in gen.NODES:
        assert T2[n] > T1[n]


# ------------------------------------------------------------------------------------------- solve results
def test_energy_closure_and_envelope_consistency(doc):
    for case, fins in doc["solve"]["cases"].items():
        assert set(fins) == {"bare_machined_stainless", "sandblasted_stainless", "z93_white_inorganic"}
        for fin, d in fins.items():
            for pd, env in d["by_P_d_W"].items():
                for n, e in env.items():
                    if n == "Q_mount_W":
                        assert e["min_W"] <= e["nominal_W"] <= e["max_W"]
                        continue
                    assert e["T_min_K"] <= e["T_nominal_K"] <= e["T_max_K"], (case, fin, pd, n)
                    b = e["hot_corner_energy_balance_W"]
                    assert abs(b["load"] - b["rejected_to_boundaries"]) <= 1e-3 + 1e-6 * b["load"]
                    assert e["iron_k_held_at_0C"]["hot_corner"] is False
            lhs = d["lhs_at_P_d_max"]
            for n, st in lhs["nodes"].items():
                assert st["max_sample_above_corner_T_max_K"] <= 1e-6, (case, fin, n)
                assert st["max_sample_below_corner_T_min_K"] <= 1e-6, (case, fin, n)
            assert lhs["Q_mount_W"]["max_sample_above_corner_max"] <= 1e-6


def test_margins_and_hard_incompatibility(doc, gen):
    rows = doc["margins_at_P_d_max"]
    assert rows
    for r in rows:
        assert r["verdict"] in {"PASS_WHOLE_ENVELOPE", "DESIGN_DRIVING", "EXCEEDED_WHOLE_ENVELOPE"}
        assert abs(r["margin_worst_K"] - (r["limit_C"] - r["T_max_C"])) < 0.2
        assert 0.0 <= r["lhs_fraction_above_limit"] <= 1.0
    hic = doc["hard_incompatibility_check"]
    assert hic["checked"] and hic["rule"]
    assert (hic["result"] == "none found") == (hic["findings"] == [])
    assert hic["findings"] == gen.hard_incompatibility(rows)
    synth = [{"case": "ground", "node": "CI", "verdict": "EXCEEDED_WHOLE_ENVELOPE"},
             {"case": "ground", "node": "CI", "verdict": "EXCEEDED_WHOLE_ENVELOPE"}]
    assert gen.hard_incompatibility(synth) == [{"case": "ground", "node": "CI",
                                                 "evidence": "every option exceeds its sourced limit over the whole envelope"}]
    synth[1]["verdict"] = "DESIGN_DRIVING"
    assert gen.hard_incompatibility(synth) == []


def test_limits_are_sourced(doc):
    for l in doc["limits"]:
        assert l["source"] and l["evidence_class"] in EVIDENCE
        if l["value_C"] is None:
            assert l["source"].startswith("TBD") or "TBD" in l["source"]
            assert l["live"] is False


def test_pim_slot_is_common_interface_only(doc):
    pm = {r["key"]: r for r in doc["design_parameters"]}
    assert pm["Q_PIM_W"]["value"] == 0.0 and "PMI-05" in pm["Q_PIM_W"]["status"]
    for case, fins in doc["solve"]["cases"].items():
        for fin, d in fins.items():
            for pd, env in d["by_P_d_W"].items():
                assert env["BP"]["dT_dQ_PIM_K_per_W_nominal"] > 0


# ------------------------------------------------------------------------------------------- (b)-(h)
def test_interface_demands(doc):
    ds = doc["interface_demands"]
    assert ds
    for d in ds:
        for k in ("from", "to", "quantity", "value", "units", "status"):
            assert k in d
    both = {(d["from"].split(" ")[0], d["to"].split(" ")[0]) for d in ds}
    for lane in ("H2-1", "H2-2", "H2-4", "H2-3", "H2-6", "H2-7"):
        assert any(lane in (a, b) for a, b in both), lane


def test_blockers_m16_procurement_tests_milestones(doc):
    assert sorted(b["blocker"] for b in doc["architecture_changing_blockers_touched"]) == [1, 2, 3]
    for m in doc["m16_rows"]:
        assert m["proposed_state"] in M16_STATES
        if m["proposed_state"] == "BLOCKED":
            assert isinstance(m["blocking_item"], str) and m["blocking_item"]
            assert m["rollup_category"] in ROLLUPS
    assert any(m["subsystem"] == "thermal control" for m in doc["m16_rows"])
    assert doc["h3_procurement_inputs"] and doc["h4_test_inputs"]
    assert set(doc["milestone_statement"]) == {"A", "B", "C"}
    assert doc["thermal_life_link"]


def test_no_architecture_winner(doc):
    blob = json.dumps(doc).lower()
    for bad in ("winner", "selected architecture", "recommended architecture", "eliminated_within_tested_envelope"):
        assert bad not in blob.replace("no_winner", ""), bad


def test_markdown_names_every_parameter(doc):
    with open(MD_PATH, encoding="utf-8") as f:
        md = f.read()
    for r in doc["design_parameters"]:
        assert r["id"] in md
    for n in ("H25-Q1", "H25-Q2", "H25-Q3", "H25-Q4"):
        assert n in md
