"""Tests for the F6 downstream ICP geometry synthesis (abep_sim/design/icp_geometry_synthesis.py, builder and outputs in
docs/design_synthesis/f6_icp_geometry/; owner directive A9.7 F6, lane fo_a9_7_f6_icp_geometry).

Checks: byte-for-byte reproduction of the committed JSON / MD; decision pins; design-vector validation and hard
constraints (fail closed); every objective refuses without evidence (real P1 reducer, real P3 library); the
fail-closed Pareto filter (refusal, fixed required set, context check, non-dominance arithmetic); the search refuses
TBD / unlabelled assumed bounds; the view-factor engine against the Howell C-52 closed form; screening content and
labels; no PASS / winner. Numeric fixtures are SYNTHETIC_TEST_DATA_NOT_EVIDENCE.
Run: python -m pytest -q tests/test_design_f6_icp_geometry.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "design_synthesis" / "f6_icp_geometry"
BUILDER = LANE / "build_f6_icp_geometry.py"
OUT_JSON = LANE / "f6_icp_geometry_v1.json"
OUT_MD = LANE / "F6_ICP_GEOMETRY.md"
MODULE = REPO / "abep_sim" / "design" / "icp_geometry_synthesis.py"
SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"

from abep_sim.design import icp_geometry_synthesis as F  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def builder():
    return _load("f6_builder_under_test", BUILDER)


@pytest.fixture(scope="module")
def outputs(builder):
    return builder.outputs()


@pytest.fixture(scope="module")
def doc():
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def h1_assumed():
    return F.h1_record_from_p3(json.loads((REPO / F.P3_JSON_REL).read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def h1_syn(h1_assumed):
    return dict(h1_assumed, evidence_class=SYN, source="test fixture (P3 evaluation values relabelled synthetic)")


def env(**kw):
    x = {"geometry_id": "SYN-G1", "L_standoff": 0.05, "r_aperture": 0.06, "r_module": 0.09, "L_module": 0.15,
         "tau_support": 0.0}
    x.update(kw)
    return x


# ------------------------------------------------------------------------------------------ reproduction / pins
def test_outputs_reproduced_byte_for_byte(outputs):
    assert outputs["f6_icp_geometry_v1.json"] == OUT_JSON.read_text(encoding="utf-8")
    assert outputs["F6_ICP_GEOMETRY.md"] == OUT_MD.read_text(encoding="utf-8")


def test_decision_pins_match(doc):
    for p in doc["decision_pins"]:
        assert hashlib.sha256((REPO / p["path"]).read_bytes()).hexdigest() == p["sha256"]
        assert p["path"].startswith("docs/decisions/")


def test_md_generated_from_json(builder, doc):
    assert builder.render_md(doc) == OUT_MD.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------ design vector
def test_design_vector_ids_and_tbd_bounds():
    ids = [v["id"] for v in F.DESIGN_VARIABLES]
    assert ids == [f"F6-X-{i:02d}" for i in range(1, 18)]
    syms = {v["symbol"] for v in F.DESIGN_VARIABLES}
    assert {"L_standoff", "r_aperture", "r_module", "L_module"} <= syms
    for v in F.DESIGN_VARIABLES:
        assert v["bounds"]["lo"] == "TBD" and v["bounds"]["hi"] == "TBD" and v["bounds"]["evidence_class"] is None
        assert v["bounds"]["requires"]


def test_validate_refuses_malformed():
    with pytest.raises(F.F6Error):
        F.validate_design_vector({"L_standoff": 0.1})
    with pytest.raises(F.F6Error):
        F.validate_design_vector(env(bogus=1.0))
    with pytest.raises(F.F6Error):
        F.validate_design_vector(env(L_module=float("nan")))
    vals, tbd = F.validate_design_vector(env(N_ant="TBD - antenna design"))
    assert "N_ant" in tbd and "N_ant" not in vals


@pytest.mark.parametrize("bad", [
    dict(r_module=0.05), dict(L_standoff=0.0), dict(tau_support=1.0), dict(N_ant=2.5),
    dict(r_ant=0.07, d_ant=0.03), dict(L_ant=0.2), dict(r_coll_in=0.02, r_coll_out=0.01),
    dict(r_coll_in=0.0, r_coll_out=0.1), dict(z_coll=0.14, t_coll=0.02), dict(t_bore=0.02, t_outer=0.01),
    dict(t_up=0.1, t_down=0.06)])
def test_hard_constraints_fail_closed(bad):
    with pytest.raises(F.GeometryConstraintError):
        F.validate_design_vector(env(**bad))
    e = F.evaluate(env(**bad))
    assert e["status"] == "INFEASIBLE" and e["objectives"] is None and e["rankable"] is False


# ------------------------------------------------------------------------------------------ objectives refuse
def test_every_objective_refuses_without_evidence():
    e = F.evaluate(env())
    assert tuple(e["objectives"]) == F.REQUIRED_OBJECTIVES and len(F.REQUIRED_OBJECTIVES) == 8
    for name, o in e["objectives"].items():
        assert o["rankable"] is False and o["value"] is None, name
    assert e["objectives"]["rf_match_loss_fraction"]["status"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert e["objectives"]["hall_b_field_disturbance"]["status"] == "TBD"
    assert e["objectives"]["hall_b_field_disturbance"]["needs"]
    assert e["rankable"] is False


def test_capacity_from_real_p1_reducer_is_not_evaluated():
    p1 = F.p1_reducer().icp45a_evaluate([], registration=None)
    assert p1["status"] == "NOT_EVALUATED"
    o = F.capacity_objective(p1, None, "SYN-G1")
    assert o["status"] == "NOT_EVALUATED" and o["value"] is None
    with pytest.raises(F.F6Error):
        F.capacity_objective({"status": "PASS"}, None, "SYN-G1")
    syn = {"status": "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", "I_e_cap_A": 1.0}
    with pytest.raises(F.F6Error):
        F.capacity_objective(syn, {"geometry_id": "OTHER", "source": "t"}, "SYN-G1")
    assert F.capacity_objective(syn, {"geometry_id": "SYN-G1", "source": "t"}, "SYN-G1")["status"] == F.SYNTHETIC


def test_rf_power_refuses_upper_bound_and_bus():
    cap = {"status": "NOT_EVALUATED"}
    b = {"geometry_id": "SYN-G1", "source": "t", "p1_record_id": "R1"}
    o = F.rf_power_objective({"P_delivered_kind": "P_RF_DELIVERED_UPPER_BOUND_LOSS_NOT_MEASURED",
                              "P_delivered_W": 1.0}, b, "SYN-G1", cap)
    assert o["status"] == "NOT_EVALUATED"
    with pytest.raises(F.F6Error):
        F.rf_power_objective({"P_bus_W": 1.0, "P_delivered_kind": "P_RF_DELIVERED"}, b, "SYN-G1", cap)
    o = F.rf_power_objective({"P_delivered_kind": "P_RF_DELIVERED", "P_delivered_W": 1.0}, b, "SYN-G1", cap)
    assert o["status"] == "NOT_EVALUATED"      # capacity not evaluated at this record


def test_rf_matching_needs_valid_p2_map():
    assert F.rf_matching_objective(None, None, "SYN-G1")["status"] == "TBD_AFTER_IMPEDANCE_MAP"
    with pytest.raises(Exception):
        F.rf_matching_objective({"schema": "p2_impedance_map_v1"}, {"geometry_id": "SYN-G1", "source": "t"}, "SYN-G1")


def test_b_field_record_rules():
    b = {"geometry_id": "SYN-G1", "source": "t"}
    with pytest.raises(F.F6Error):
        F.b_field_objective({"value": 0.01, "units": "-", "evidence_class": "model-derived", "source": "x"}, b,
                            "SYN-G1")
    with pytest.raises(F.F6Error):
        F.b_field_objective({"value": 0.01, "units": "-", "evidence_class": "assumed", "source": "x"}, b, "SYN-G1")
    o = F.b_field_objective({"value": 0.01, "units": "-", "evidence_class": SYN, "source": "x"}, b, "SYN-G1")
    assert o["status"] == F.SYNTHETIC and not o["rankable"]


def test_plume_only_measured_distribution(h1_assumed, h1_syn):
    vals, tbd = F.validate_design_vector(env())
    assert F.plume_objective(vals, tbd, h1_assumed, None)["status"] == "NOT_EVALUATED"
    cone = [(0.0, 0.0), (30.0, 1.0)]
    rec = {"value": cone, "units": "deg; -", "evidence_class": "assumed", "source": "test cone"}
    assert F.plume_objective(vals, tbd, h1_assumed, rec)["status"] == "NOT_EVALUATED"
    rec_syn = dict(rec, evidence_class=SYN)
    near = F.plume_objective(vals, tbd, h1_syn, rec_syn)
    far_vals, _ = F.validate_design_vector(env(L_standoff=1.0))
    far = F.plume_objective(far_vals, tbd, h1_syn, rec_syn)
    assert near["status"] == F.SYNTHETIC and not near["rankable"]
    assert 0.0 <= far["value"] < near["value"] <= 1.0
    assert abs(near["value"] + near["f_escape"] - 1.0) < 1e-9


def test_collector_heating_rules():
    assert F.collector_objective(None, None, "SYN-G1")["status"] == "NOT_EVALUATED"
    b = {"geometry_id": "SYN-G1", "source": "t"}
    lib = F.p3_lib()
    inp = {k: lib.q(v, u, SYN, "t") for k, v, u in (("I_electron_collected_A", 0.1, "A"),
                                                    ("I_ion_collected_A", 0.01, "A"), ("T_e_eV", 3.0, "eV"),
                                                    ("V_plasma_V", 10.0, "V"), ("V_surface_V", 0.0, "V"))}
    inp["surface_energy_terms"] = {"value": "EXCLUDED", "source": "t"}
    o = F.collector_objective(inp, b, "SYN-G1")
    assert o["status"] == F.SYNTHETIC and o["value"] == pytest.approx(0.1 * 6.0 + 0.01 * (1.5 + 10.0))
    del inp["T_e_eV"]
    assert F.collector_objective(inp, b, "SYN-G1")["status"] == "NOT_EVALUATED"


def test_mass_geometry_times_density():
    full = env(N_ant=2, r_ant=0.07, L_ant=0.05, d_ant=0.004, r_coll_in=0.02, r_coll_out=0.05, z_coll=0.1,
               t_coll=0.002, t_bore=0.002, t_outer=0.002, t_up=0.003, t_down=0.003, tau_support=0.5)
    vals, _ = F.validate_design_vector(full)
    o = F.mass_objective(vals, None)
    assert o["status"] == "NOT_EVALUATED" and set(o["missing_density"]) == set(F.MASS_COMPONENTS)
    rho = {c: {"value": 1000.0, "units": "kg/m3", "evidence_class": SYN, "source": "t"} for c in F.MASS_COMPONENTS}
    o = F.mass_objective(vals, rho)
    ra, rm, L = 0.06, 0.09, 0.15
    shells = 0.5 * (2 * math.pi * ra * L * 0.002 + 2 * math.pi * rm * L * 0.002 + math.pi * (rm ** 2 - ra ** 2) * 0.006)
    ant = 2 * 2 * math.pi * 0.07 * math.pi * 0.004 ** 2 / 4
    coll = math.pi * (0.05 ** 2 - 0.02 ** 2) * 0.002
    assert o["status"] == F.SYNTHETIC and o["value"] == pytest.approx(1000.0 * (shells + ant + coll))
    rho_mixed = dict(rho, antenna={"value": 8030.0, "units": "kg/m3", "evidence_class": "measured", "source": "x"})
    with pytest.raises(F.F6Error):
        F.mass_objective(vals, rho_mixed)
    with pytest.raises(F.F6Error):
        F.mass_objective(vals, dict(rho, antenna={"value": 8.0, "units": "g/cm3", "evidence_class": SYN,
                                                  "source": "x"}))


def test_geometric_status_mapping():
    assert F.geometric_status("assumed") == F.EVALUATED_GEOMETRIC_CONDITIONAL
    assert F.geometric_status(SYN) == F.SYNTHETIC
    assert F.geometric_status("measured") == F.EVALUATED_GEOMETRIC
    with pytest.raises(F.F6Error):
        F.geometric_status("guess")


# ------------------------------------------------------------------------------------------ Pareto / search
def test_pareto_refuses_today_and_fixed_required_set(h1_assumed):
    assert list(inspect.signature(F.pareto_filter).parameters) == ["evaluations"]
    e = F.evaluate(env(), {"h1_front_geometry": h1_assumed})
    p = F.pareto_filter([e])
    assert p["status"] == "REFUSED_INCOMPLETE" and p["pareto_set"] is None
    assert set(p["missing"]["SYN-G1"]) == set(F.REQUIRED_OBJECTIVES)   # view factor conditional too
    e2 = F.evaluate(env(geometry_id="SYN-G2"), {})
    with pytest.raises(F.F6Error):
        F.pareto_filter([e, e2])
    inf = F.evaluate(env(r_module=0.01))
    assert F.pareto_filter([inf])["status"] == "REFUSED_NO_FEASIBLE_CANDIDATE"
    with pytest.raises(F.F6Error):
        F.pareto_filter([])


def _complete(gid, values):
    objs = {k: {"status": F.EVALUATED, "value": v, "rankable": True} for k, v in zip(F.REQUIRED_OBJECTIVES, values)}
    return {"geometry_id": gid, "status": "EVALUATED_VECTOR", "objectives": objs, "context_fingerprint": "SYN"}


def test_pareto_arithmetic_on_synthetic_vectors():
    a = _complete("SYN-A", [2, 0.1, 0.1, 100, 0.0, 0.01, 5, 1.0])
    b = _complete("SYN-B", [1, 0.1, 0.1, 100, 0.0, 0.01, 5, 1.0])     # dominated by A (less current)
    c = _complete("SYN-C", [1, 0.1, 0.1, 50, 0.0, 0.01, 5, 1.0])      # trade-off vs A (less RF power)
    p = F.pareto_filter([a, b, c])
    assert p["status"] == "PARETO_SET_COMPUTED_NOT_A_SELECTION" and p["pareto_set"] == ["SYN-A", "SYN-C"]
    b["objectives"]["module_mass"]["rankable"] = False
    assert F.pareto_filter([a, b, c])["status"] == "REFUSED_INCOMPLETE"
    assert F.nondominated([[1, 1], [1, 1]], ["minimize", "minimize"]) == [0, 1]
    with pytest.raises(F.F6Error):
        F.nondominated([[1]], ["best"])


def test_search_refuses_tbd_and_unlabelled_assumed_bounds():
    with pytest.raises(F.SearchRefused):
        F.search({}, 3)
    bounds = {s: {"lo": 0.01, "hi": 0.02, "units": v["units"], "evidence_class": "assumed", "source": "t"}
              for s, v in F.VAR_BY_SYMBOL.items()}
    with pytest.raises(F.SearchRefused):
        F.search(bounds, 3)
    bounds["L_standoff"] = {"lo": "TBD", "hi": "TBD", "units": "m", "evidence_class": None, "source": ""}
    with pytest.raises(F.SearchRefused):
        F.search(bounds, 3)


# ------------------------------------------------------------------------------------------ view-factor engine
def test_view_factor_aperture_to_icp_face_matches_howell_c52(h1_assumed):
    """The H-1 exit annulus and the ICP upstream face are parallel coaxial annuli with nothing in between."""
    lib = F.p3_lib()
    g = h1_assumed["value"]
    vals, _ = F.validate_design_vector(env())
    vf = lib.view_factors([lib.h1_body(g), F.icp_body(vals)], F.RES_SCREEN, emitters=["H1.aperture"])
    exact = lib.vf_annulus_to_parallel_coaxial_annulus(g["R_i"], g["R_o"], 0.06, 0.09, 0.05)
    assert vf["F"]["H1.aperture"]["ICP.up"] == pytest.approx(exact, abs=0.01)


def test_obstruction_decreases_with_standoff(h1_assumed):
    v = []
    for L in (0.025, 0.05, 0.1, 0.2):
        vals, tbd = F.validate_design_vector(env(L_standoff=L))
        v.append(F.vf_objective(vals, tbd, h1_assumed)["value"])
    assert all(a > b for a, b in zip(v, v[1:]))


# ------------------------------------------------------------------------------------------ outputs content
def test_screening_labels_and_states(doc):
    gs = doc["geometric_screening"]
    assert gs["label"] == "GEOMETRIC_SCREENING_NOT_A_DESIGN"
    assert gs["h1_geometry"]["evidence_class"] == "assumed"
    assert len(gs["rows"]) == 96
    for r in gs["rows"]:
        assert r["vf_status"] == "EVALUATED_GEOMETRIC_CONDITIONAL" and r["module_mass_status"] == "NOT_EVALUATED"
        assert r["al05_mean_areal_density_ceiling_kg_m2"] > 0
    assert gs["convergence_check"]["status"] == "WITHIN_NUMERICAL_TOLERANCE"
    assert doc["current_objective_state"]["pareto_demonstration"]["status"] == "REFUSED_INCOMPLETE"
    assert doc["current_objective_state"]["search_demonstration"]["status"] == "REFUSED"
    assert doc["architecture_status"] == "INVESTIGATION_HYPOTHESIS"


def test_items_evidence_discipline(doc):
    for it in doc["items"]:
        assert {"id", "value", "units", "basis", "source", "evidence_class", "status"} <= set(it)
        if it["status"] == "TBD":
            assert it["value"] == "TBD" and it["evidence_class"] is None
        else:
            assert it["source"]
    al = [i for i in doc["items"] if i["id"] == "F6-P-02"][0]
    assert al["evidence_class"] == "owner-allocation"
    oq = [q["id"] for q in doc["open_owner_questions"]]
    assert oq == ["F6-OQ-01", "F6-OQ-02", "F6-OQ-03", "F6-OQ-04"]
    assert all(m["proposed_change"] == "none" for m in doc["m16_impact"])
    assert doc["interface_demands"]["f6_needs"] and doc["interface_demands"]["f6_supplies"]


def test_no_pass_no_winner_no_forbidden_tokens():
    for p in (OUT_JSON, OUT_MD, MODULE, BUILDER):
        t = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in t
    for p in (OUT_JSON, OUT_MD):
        t = p.read_text(encoding="utf-8")
        assert '"PASS"' not in t and '"status": "PASS' not in t and '"winner"' not in t and "SELECTED_DESIGN" not in t
