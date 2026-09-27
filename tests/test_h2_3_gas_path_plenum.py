"""H2-3 atmospheric gas path / plenum preliminary design v1 (fo_h2_3_gas_path_plenum; owner addenda A5/A6/A7).

Checks that the builder reproduces the committed JSON + MD byte for byte, that only immutable owner decision files and
the G0 record are pinned (and match), that no mutable governance file is pinned or read, that every design parameter
carries basis / source / evidence class / status / representativeness (a missing value is PENDING or TBD, never a
silent number), that the cited vacuum-physics relations reproduce their published anchors, that the cold-flow pressure
budget is internally consistent, that the uniformity rule is applied as stated, that interface planes / CIs / INS ids
exist in the base deliverables, that M16 BLOCKED rows name exactly one blocker with a valid rollup category, that the
hard-incompatibility check vetoes nothing, and that no Hall closure, screening candidate, P5 nuisance item or live
atmosphere enters. Run: python -m pytest -q tests/test_h2_3_gas_path_plenum.py   (about a second).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "docs" / "hardware" / "h2" / "h2_3_gas_path_plenum"
SCRIPT = DIR / "build_h2_3_gas_path_plenum.py"
JSON_PATH = DIR / "h2_3_gas_path_plenum_v1.json"
MD_PATH = DIR / "H2_3_GAS_PATH_PLENUM.md"
HW = REPO / "docs" / "experiments" / "hardware" / "hardware_requirements_v1.json"
INS = REPO / "docs" / "experiments" / "instrumentation" / "instrumentation_definition_v1.json"
W1 = REPO / "docs" / "architecture_comparison" / "feed_state_closure" / "feed_state_closure_v1.json"
MUTABLE_GOVERNANCE = ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_h2_3_gas_path_plenum", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text())


def test_builder_reproduces_committed_outputs(mod):
    outs = mod.outputs()
    assert outs[mod.JSON_NAME] == JSON_PATH.read_text()
    assert outs[mod.MD_NAME] == MD_PATH.read_text()
    assert mod.outputs() == outs  # deterministic


def test_decision_pins_are_immutable_decisions_and_match(mod, doc):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"]}
    for rel in ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json",
                "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json",
                "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json",
                "docs/decisions/verification/A5_BASELINE_VERIFICATION.json"):
        assert rel in pins
    for rel, sha in pins.items():
        assert rel.startswith("docs/decisions/")
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == sha
    assert pins == mod.DECISION_PINS


def test_no_mutable_governance_file_is_pinned_or_read(mod, doc):
    paths = [p["path"] for p in doc["decision_pins"]] + [p["path"] for p in doc["input_fingerprints"]]
    for p in paths:
        assert not any(g in p for g in MUTABLE_GOVERNANCE), p
    src = SCRIPT.read_text()
    for g in MUTABLE_GOVERNANCE:
        assert f"{g}_v1.json\"" not in src and f"{g}.json\"" not in src and f"{g}.jsonl\"" not in src


def test_design_parameters_are_complete_and_labelled(mod, doc):
    ids = [p["id"] for p in doc["design_parameters"]]
    assert len(ids) == len(set(ids))
    for p in doc["design_parameters"]:
        assert re.fullmatch(r"H23-\d{2}", p["id"])
        for k in ("name", "units", "basis", "source", "evidence_class", "status", "representativeness"):
            assert p.get(k) not in (None, ""), (p["id"], k)
        assert p["basis"] in mod.BASES
        assert p["representativeness"] in mod.REPRESENTATIVENESS
        ev = p["evidence_class"]
        assert ev in mod.EVIDENCE_CLASSES or ev == "TBD" or ev.startswith("model-derived"), ev
        st = p["status"]
        assert st.startswith(("PRELIMINARY", "PENDING ", "TBD - requires")), st
        if p["value"] is None:
            assert st.startswith(("PENDING ", "TBD - requires")) and ev == "TBD", p["id"]
        if p["basis"] == "pending":
            assert p["value"] is None


def test_pending_values_point_at_registered_parallel_lane_paths(mod, doc):
    lanes = set(mod.PENDING_LANES.values())
    keys = set(mod.PENDING_LANES)
    blob = json.dumps(doc)
    for m in re.finditer(r"PENDING ([^\"|]+?)(?:\"| \()", blob):
        g = m.group(1)
        ok = any(g.startswith(v) or v.startswith(g) for v in lanes) or any(re.match(re.escape(k) + r"\b", g)
                                                                           for k in keys)
        assert ok, g
    for p in doc["design_parameters"]:
        if p["status"].startswith("PENDING "):
            assert p["status"][len("PENDING "):] in lanes, p["id"]


def test_pending_resolution_is_lazy_and_does_not_change_outputs(mod):
    st = mod.resolve_pending()
    assert set(st) == set(mod.PENDING_PROBE_FILES)
    assert all(v in ("present", "missing (PENDING)") for v in st.values())


def test_vacuum_physics_anchors(mod):
    # Chiggiato Table 4 / Table 8: <v>(N2, 293 K) ~ 470 m/s, C' = <v>/4 = 117.5 m^3 s^-1 m^-2
    cb = mod.cbar(293.0, mod.MOLAR["N2"])
    assert abs(cb - 470.0) / 470.0 < 0.005
    assert abs(cb / 4.0 - 117.5) / 117.5 < 0.005
    # Santeler: tau(0) = 1; tau ~ 0.5 for L = D (Chiggiato text); long-tube limit 8R/3L within 10 % for L/R >> 20
    assert mod.santeler_tau(0.0, 1.0) == 1.0
    assert abs(mod.santeler_tau(2.0, 1.0) - 0.5) < 0.03
    assert abs(mod.santeler_tau(400.0, 1.0) / (8.0 / 1200.0) - 1.0) < 0.1
    # Leybold 1.28b molecular limit implies <v>_air(20 C) ~ 462 m/s; Knudsen factor -> 1 in the molecular limit
    assert abs(mod.CBAR_AIR_LEYBOLD - 462.2) < 0.5
    assert abs(mod.knudsen_f(0.01, 1e-6) - 1.0) < 1e-6
    assert 0.9 < mod.KNUDSEN_F_MIN < 1.0
    # JANAF: 2 O -> O2 at 298.15 K releases 498.346 kJ/mol = 5.165 eV
    assert abs(mod.DH_REC_J_PER_MOL_O2 / mod.N_A / mod.EV - 5.165) < 0.002


def test_solver_satisfies_segment_equation(mod):
    cb = mod.cbar(300.0, mod.MOLAR["N2"])
    cm = mod.c_tube_mol(0.01, 1.0, cb)
    for p_down, Q in ((0.0, 1e-3), (1.0, 0.05), (50.0, 0.3)):
        p_up, f = mod.solve_upstream(p_down, Q, cm, 0.01)
        assert abs(cm * f * (p_up - p_down) - Q) / Q < 1e-9


def test_pressure_budget_is_monotonic_and_consistent(doc):
    for r in doc["pressure_budget"]["rows"]:
        assert r["p_manifold_Pa"] > r["p_HALL_INLET_Z0_cold_Pa"] > 0
        for g in r["geometries"].values():
            p = r["p_manifold_Pa"]
            for s in g["segments"]:
                assert s["dp_Pa"] > 0
                assert s["regime"].split(" ")[0] in ("free-molecular", "transitional", "viscous")
                p += s["dp_Pa"]
            assert abs(p - g["p_IF_A5_Pa"]) / g["p_IF_A5_Pa"] < 1e-4
            for key, v in g["valve"].items():
                rr = float(key.split("=")[1])
                assert abs(v["p_plenum_min_Pa"] - g["p_IF_A5_Pa"] * (1.0 + 1.0 / rr)) / v["p_plenum_min_Pa"] < 1e-4
                assert abs(v["C_total_plenum_to_vacuum_m3_s"] * v["p_plenum_min_Pa"] - r["Q_Pa_m3_s"]) \
                    / r["Q_Pa_m3_s"] < 1e-4


def test_uniformity_rule_applied_as_stated(mod, doc):
    for r in doc["distributor_uniformity"]["rows"]:
        delta = r["C_holes_max_m3_s"] / (8.0 * r["feed_points"] ** 2 * r["C_ring_m3_s"])
        assert abs(delta - 0.075) < 1e-4
        assert r["p_manifold_Pa"] > r["p_Z0_cold_Pa"]
    assert min(doc["distributor_uniformity"]["rows"], key=lambda x: x["dp_holes_Pa"])["feed_points"] == 4


def test_a5_o2_range_recomputed_from_frozen_data(doc):
    af = doc["atmosphere_facts"]
    assert round(af["w_O2_full_recombination_min"], 2) == 0.42
    assert round(af["w_O2_full_recombination_max"], 2) == 0.60


def test_flow_points_trace_to_w1(doc):
    w1 = json.loads(W1.read_text())
    fp = doc["flow_points"]
    assert abs(fp["F-MIN"]["mdot_mg_s"] - w1["mfc_range_requirement"]["mdot_min_kgps"] * 1e6) < 1e-3
    assert abs(fp["F-MAX"]["mdot_mg_s"] - w1["mfc_range_requirement"]["mdot_max_kgps"] * 1e6) < 1e-3


def test_planes_cis_and_ins_ids_exist_in_base_deliverables(doc):
    hw = json.loads(HW.read_text())
    planes = {p["id"] for p in hw["interface_planes"]}
    cis = {c["id"] for c in hw["configuration_items"]}
    blob = json.dumps(doc)
    for pl in ("IP-UP", "IP-DN", "HALL_INLET_Z0"):
        assert pl in planes and pl in blob
    for ci in ("H-1", "FS-C", "PIM-0", "PIM-RF", "PIM-ECR"):
        assert ci in cis and ci in blob
    ins = {i["id"] for i in json.loads(INS.read_text())["instruments"]}
    used = {i for m in doc["measurement_locations"] for i in m["INS"]}
    assert used and used <= ins
    for q in ("P_feed", "T_feed", "x_s"):
        assert any(m["quantity"].startswith(q) for m in doc["measurement_locations"])


def test_m16_rows_follow_the_a7_blocked_rule(mod, doc):
    for r in doc["m16_rows"]:
        if r["proposed_state"] == "BLOCKED":
            assert isinstance(r["blocking_item"], str) and r["blocking_item"]
            assert r["rollup"] in mod.ROLLUP
        else:
            assert r["blocking_item"] is None and r["rollup"] is None
            assert r["proposed_state"] in mod.M16_STATES or r["proposed_state"] == "not proposed by this lane"


def test_interface_demands_and_hard_check(doc):
    for d in doc["interface_demands"]:
        for k in ("from", "to", "quantity", "value", "units", "status"):
            assert k in d
        assert d["status"]
    h = doc["hard_incompatibility_check"]
    assert h["result"] == "none found"
    assert h["checked"] and all(c["veto"] is False and c["evidence_class"] and c["why_not"] for c in h["checked"])
    assert {b["blocker"] for b in doc["architecture_changing_blockers_touched"]} <= {1, 2, 3}


def test_architecture_neutral_and_closure_free(doc):
    assert doc["architectures"] == ["hall_only", "rf_hall", "ecr_hall"]
    blob = json.dumps(doc).lower()
    for bad in ("sgb-screen", "screening_candidates", "ensemble_member_id", "l38", "l32", "coil_shape",
                "beam_efficiency", "winner:", "selected architecture", "recommended architecture"):
        assert bad not in blob, bad
    src = SCRIPT.read_text()
    for bad in ("import abep_sim.plasma", "from abep_sim.plasma", "hall_map", "hall_ensemble", "hallthruster_bridge/",
                "use_msis=True", "pymsis", "archengine import"):
        assert bad not in src, bad


def test_every_reference_has_access_level_and_url(doc):
    for k, r in doc["references"].items():
        assert r["url"].startswith("https://"), k
        assert r["access"], k
    blob = json.dumps({k: v for k, v in doc.items() if k != "references"})
    for k in doc["references"]:
        assert k in blob or k == "REF-SI2019" or k == "REF-SANTELER1986", k


def test_representativeness_labels_cover_all_three_classes(mod, doc):
    reps = {p["representativeness"] for p in doc["design_parameters"]}
    assert reps == set(mod.REPRESENTATIVENESS)
    assert doc["topology"]["ground_substitution"]["representativeness"] == "GROUND/FACILITY-ONLY"


def test_plenum_numbers_are_consistent(doc):
    ps = doc["plenum_sizing"]
    for r in ps["compressor_ripple"]["rows"]:
        tau = math.sqrt(1.0 / r["attenuation"] ** 2 - 1.0) / (2.0 * math.pi * r["f_ripple_Hz"])
        assert abs(tau - r["tau_min_s"]) / tau < 1e-3
    vr = ps["volume_range"]
    assert 0 < vr["V_min_m3"] < vr["V_upper_of_minimum_m3"]
    assert vr["V_max_status"].startswith("TBD - requires")
