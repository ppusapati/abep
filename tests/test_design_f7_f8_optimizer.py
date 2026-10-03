"""A9.7 F7 coupled architecture optimizer + F8 robust optimization: design-vector blocks, upstream evaluation (vs
the scalar F4 reference), Pareto semantics, fail-closed system objectives / constraints, full-system ranking (refusal
today; synthetic-fixture code path), F8 helpers, and the committed study (structure, labels, pins, reproduction of a
committed member). Fast (< 30 s): the full builder is NOT run here; `python
docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py --check` reproduces it."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from abep_sim import bus_boundary_a9_v2 as bb
from abep_sim.design import architecture_optimizer as ao
from abep_sim.design import intake_synthesis as isy
from abep_sim.design import plenum_feed as pf
from abep_sim.design import robust_optimizer as ro
from abep_sim.design import upstream_a9_13 as u13

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design_synthesis/f7_f8_optimizer"
BUILDER = OUT / "build_f7_f8_optimizer.py"
JSON_MAIN = OUT / "f7_f8_optimizer_v1.json"
JSON_PARETO = OUT / "f7_upstream_pareto_v1.json"
JSON_ROBUST = OUT / "f8_robust_candidates_v1.json"
MD = OUT / "F7_F8_OPTIMIZER.md"
SYN = ao.SYN_CLASS


@pytest.fixture(scope="module")
def inp():
    return ao.load_upstream_inputs(ROOT)


@pytest.fixture(scope="module")
def small_ctx(inp):
    cands = ("A0.25_Ld10_phi0.8", "A0.5_Ld20_phi0.8", "A1.5_Ld3_phi0.9")
    # F3 front-union members (A1 = the 0.196 m^2 LI2015 area; the A2 grid bound moved with the W1 S6.8 re-pin)
    # (T6-A1-U2-D0 replaces T6-A1-U1-D0 since A9.14 S9.8 OD3: with every required design state, A0.25_Ld10_phi0.8 is
    # all-state feasible only with the former; the committed nominal cll_a0.8 Pareto set contains that pair)
    comps = ("T3-A1-U2-D0-Ti6Al4V-H0.25", "T6-A1-U2-D0-Ti6Al4V-H0.25")
    return ao.upstream_context(inp, "cll_a0.8", "F4-FIL-NONE", "WALL-G0", candidates=cands, compressors=comps)


@pytest.fixture(scope="module")
def main_doc():
    return json.loads(JSON_MAIN.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------- design vector
def test_design_vector_blocks_fields_and_states():
    blocks = ao.design_vector_blocks(ROOT)
    assert [b["block"] for b in blocks] == list(ao.BLOCK_ORDER)
    for b in blocks:
        assert b["state"] in ao.BLOCK_STATES
        for v in b["variables"]:
            for k in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
                assert k in v, (b["block"], v.get("id"), k)
    by = {b["block"]: b for b in blocks}
    assert by["x_ICP"]["state"] == "NOT_SEARCHABLE_BOUNDS_TBD"
    assert all(v["value"] == {"lo": "TBD", "hi": "TBD"} for v in by["x_ICP"]["variables"])
    assert by["x_Hall"]["state"] == "BOUNDED_NOT_SEARCHED_NO_EVALUABLE_OBJECTIVE"
    f5 = json.loads((ROOT / ao.F5_REL).read_text())["x_hall_design_space"]["definition"]["variables"]
    assert {v["symbol"]: v["value"]["window"] for v in by["x_Hall"]["variables"] if v["symbol"] in f5} == f5
    assert by["x_filter"]["state"] == "CONTEXT_AXIS_NOT_SEARCHED"


def test_hall_admissibility_matches_f5_probes():
    f5 = json.loads((ROOT / ao.F5_REL).read_text())
    for pr in f5["x_hall_design_space"]["probe_evaluations"][:6]:
        r = ao.hall_admissibility(pr["h_mm"], pr["d_mean_mm"], pr["L_mm"], pr["assumptions"], ROOT)
        assert r["status"] == pr["status"] and r["performance"] == "NOT_EVALUATED"


# ------------------------------------------------------------------------------------------------- upstream physics
def test_drag_table_reproduces_f1(inp):
    for view in ("design_case", "envelope"):
        cm = inp.f1["candidate_metrics"][view]["maxwell_a0.5"]
        for row in cm["rows"][::17]:
            d = dict(zip(cm["columns"], row))
            per = [d["area_m2"] * inp.drag_per_area[("maxwell_a0.5", d["L_over_d"], d["phi"], st)][0]
                   for st in (ao.STATES[:1] if view == "design_case" else ao.STATES)]
            assert max(per) == pytest.approx(d["drag_N"], rel=2e-5)


def test_upstream_context_matches_scalar_reference(inp, small_ctx):
    arr = small_ctx["arrays"]
    feas = np.argwhere(small_ctx["feasible"])
    assert len(feas) > 0
    ci, ki, vi, ti = feas[0]
    cand, comp = small_ctx["candidates"][ci], small_ctx["compressors"][ki]
    V, P = small_ctx["volumes"][vi], small_ctx["targets"][ti]
    flows, pels = [], []
    for st in ao.STATES:
        ch = pf.Chain(inp.records[(cand, "cll_a0.8", st)], inp.filters["F4-FIL-NONE"], inp.plants[comp],
                      ao.plenum(V, "WALL-G0"))
        op = pf.steady_operating_point(ch, P)
        assert op["status"] == pf.ST_FEASIBLE
        flows.append(op["offered"]["mdot_total_kgps"])
        pels.append(op["compressor"]["P_el_W"])
    assert arr["mdot_delivered_min_kgps"][ci, ki, vi, ti] == pytest.approx(min(flows), rel=1e-9)
    assert arr["P_compressor_el_max_W"][ci, ki, vi, ti] == pytest.approx(max(pels), rel=1e-9)
    # infeasible vectors carry no objective (fail closed)
    bad = ~small_ctx["feasible"]
    assert bad.any() and np.isnan(arr["mdot_delivered_min_kgps"][bad]).all()
    # the drag-infeasible intake (A1.5 > 25 mN at the dense design states, F1 C-DRAG-RFP) is never feasible
    assert not small_ctx["feasible"][2].any()


def test_ripple_vectorized_matches_plenum_feed(inp, small_ctx):
    feas = np.argwhere(small_ctx["feasible"])
    ci, ki, vi, ti = feas[-1]
    cand, comp = small_ctx["candidates"][ci], small_ctx["compressors"][ki]
    pl = ao.plenum(small_ctx["volumes"][vi], "WALL-G0")
    rec = inp.records[(cand, "cll_a0.8", ao.DESIGN_STATE)]
    ch = pf.Chain(rec, inp.filters["F4-FIL-NONE"], inp.plants[comp], pl)
    a = small_ctx["arrays"]["a_eq_design_m2"][ci, ki, vi, ti]
    ref = pf.ripple_transfer(ch, a, inp.plants[comp].shaft_hz)["transfer_max"]
    assert small_ctx["arrays"]["ripple_transfer_shaft"][ci, ki, vi, ti] == pytest.approx(ref, rel=1e-12)


def test_intake_mass_code_default_is_d_invariant():
    from abep_sim.design import intake_synthesis as isy
    m = [isy.intake_mass(isy.GeometryCandidate(0.5, d, 10.0, 0.9), isy.STRUCTURAL_CODE_DEFAULT)["m_intake_kg"]
         for d in (5.0, 10.0, 20.0)]
    assert m[0] == pytest.approx(m[1]) == pytest.approx(m[2]) == pytest.approx(ao.intake_mass_code_default(0.5, 10.0, 0.9))


# ------------------------------------------------------------------------------------------------- Pareto
def test_pareto_mask_semantics():
    F = np.array([[1.0, 5.0], [2.0, 4.0], [2.0, 4.0], [3.0, 6.0], [np.nan, 0.0], [0.5, 9.0]])
    m = ao.pareto_mask(F, ["max", "min"])
    assert list(m) == [False, True, True, True, False, False]
    rng = np.random.default_rng(3)
    G = rng.random((60, 3))
    mm = ao.pareto_mask(G, ["min", "min", "max"], chunk=7)
    H = G * np.array([1, 1, -1])
    brute = [not any((H[j] <= H[i]).all() and (H[j] < H[i]).any() for j in range(60)) for i in range(60)]
    assert list(mm) == brute
    lay = ao.nondominated_layers(G, ["min", "min", "max"])
    assert set(np.nonzero(lay == 1)[0]) == set(np.nonzero(mm)[0])


def test_context_pareto_members_feasible_and_carry_not_evaluated(small_ctx):
    par = ao.context_pareto(small_ctx)
    n = 0
    for P, b in par.items():
        assert b["n_pareto"] == len(b["members"]) <= b["n_feasible"]
        for m in b["members"]:
            n += 1
            assert m["system_not_evaluated"] == list(ao.SYSTEM_NOT_EVALUATED_CODES)
            assert all(math.isfinite(m[k]) for k in ao.OBJ_KEYS)
    assert n > 0


# ------------------------------------------------------------------------------------------------- system level
def _row(small_ctx):
    par = ao.context_pareto(small_ctx)
    return next(m for b in par.values() for m in b["members"])


def test_system_objectives_refused_today(inp, small_ctx):
    row = _row(small_ctx)
    for cfg in ao.CONFIGURATIONS:
        ev = ao.evaluate_system(row, cfg, design=inp.designs[row["compressor"]])
        assert all(o["status"] == ao.NOT_EVALUATED for o in ev["objectives"].values())
        assert all(o["unlock"] for o in ev["objectives"].values())
        assert ev["system_not_evaluated"] == list(ao.SYSTEM_NOT_EVALUATED_CODES)
        st = {c["id"]: c["status"] for c in ev["constraints"]}
        # intake-face drag <= 25 mN on a parametric value: sensitivity only, never MET (OPT-01)
        assert st.pop("HC-09") == ao.C_MET_PARAMETRIC
        assert set(st.values()) == {ao.C_NOT_EVALUATED}
        pb = ev["objectives"]["P_bus_W"]
        assert pb["official_status"] == "PARTIAL_BOUNDARY" and pb["official_lower_bound_W"] == 0.0
        assert pb["parametric_lower_bound_W"] == pytest.approx(row["P_compressor_el_max_W"])
        assert ao.rank_full_system([ev])["status"] == ao.RANK_REFUSED_INCOMPLETE


def test_constraints_fail_closed_on_nothing():
    cons = ao.evaluate_constraints({})
    assert {c["status"] for c in cons} == {ao.C_NOT_EVALUATED}


def test_evidence_thrust_refused_while_credible_set_empty():
    assert ao.hall_response_status(ROOT)["credible_set"] == "EMPTY"
    o = ao.thrust_minus_drag(0.01, 1e-5, {"value": 0.03, "evidence_class": "measured", "source": "x"},
                             {"value": 0.002, "evidence_class": "measured", "source": "y"}, ROOT)
    assert o["status"] == ao.NOT_EVALUATED and "EMPTY" in o["reason"]
    o = ao.thrust_minus_drag(0.01, 1e-5, {"value": 0.03, "evidence_class": "assumed", "source": "x"},
                             {"value": 0.002, "evidence_class": "assumed", "source": "y"}, ROOT)
    assert o["status"] == ao.PARAMETRIC_ONLY


def _syn_ledgers(config, scale=1.0, measured=False):
    ec = "measured" if measured else "assumed"
    loads = {s: {"P_W": 10.0 * scale, "evidence_class": ec, "source": "SYNTHETIC_TEST_FIXTURE"}
             for s in bb.installed_slots(config)}
    loads["icp_rf_source"]["plane"] = "generator_dc_input"
    effs = {s: {"value": 0.9, "evidence_class": ec, "source": "SYNTHETIC_TEST_FIXTURE", "path": "internal_bus"}
            for s in bb.installed_slots(config)}
    fe = {"value": 0.95, "evidence_class": ec, "source": "SYNTHETIC_TEST_FIXTURE"}
    gm = {"sample_rate_Sa_s": 2e5, "bandwidth_Hz": 5e4, "anti_alias_documented": True, "synchronized": True,
          "source": "SYNTHETIC_TEST_FIXTURE"}
    st = bb.ledger(config, loads, effs, fe, label="SYNTHETIC", power_basis="p_bus_1ms_max", gate_measurement=gm)
    return {"steady": st, "startup": [st], "synthetic": not measured, "source": "SYNTHETIC_TEST_FIXTURE"}


def _syn(v):
    return {"value": v, "evidence_class": SYN, "source": "SYNTHETIC_TEST_FIXTURE"}


TEST_STATES = [{"state_id": "test-s1", "weight": 0.5}, {"state_id": "test-s2", "weight": 0.5}]


class _TestH1Map:
    """A test-only H-1 thrust-versus-feed map (no such validated map exists; the status is set by the caller)."""

    def __init__(self, status):
        self.status = status

    def min_feed_state(self, st, thrust_N, offered):
        return {"mdot_kgps": 1e-7, "P_Pa": 0.01, "T_range_K": (300.0, 400.0), "x_domain_ok": True,
                "ripple_tolerance_frac": 0.05}


def _statewise_records(vs, thrust, drag=0.002, hall_admitted=False):
    """A9.13 S6.15 / S6.21 / S6.17 records for HC-08 / HC-11 / HC-12 from test values of value status ``vs``."""
    rec = lambda v: (lambda st: {"value_N": v, "status": vs, "source": "TEST_FIXTURE", "state_id": st["state_id"]})
    tw = u13.statewise_drag_compensation(TEST_STATES, rec(thrust), rec(drag), hall_admitted=hall_admitted)
    off = lambda st: {"mdot_kgps": 2e-7, "P_Pa": 0.02, "T_K": 350.0, "x_mole": {"O": 0.5, "N2": 0.45, "O2": 0.05},
                      "ripple_frac": 0.01, "status": vs}
    fss = u13.feed_state_sufficiency(TEST_STATES, off, rec(thrust),
                                     _TestH1Map(u13.SYNTHETIC if vs == u13.VALUE_SYNTHETIC else u13.H1_MAP_VALIDATED))
    rip = u13.ripple_feed_quality(0.01, vs, u13.H1Tolerance("ripple", 0.05, vs, "TEST_FIXTURE"))
    return {"statewise_T_minus_D": tw, "feed_state_sufficiency": fss, "ripple_feed_quality": rip}


def _syn_eval(row, thrust, pbus_scale, mwet, design_id, measured_bus=False):
    sup = {"thrust": _syn(thrust), "thrust_capability": _syn(0.03), "spacecraft_drag": _syn(0.002),
           "bus": _syn_ledgers("hall_icp_neutralizer", pbus_scale, measured_bus),
           "m_wet": dict(_syn(mwet), all_terms_resolved=True), "Q_reject": _syn(300.0), "I_e_margin": _syn(1.0),
           "thermal_margin": _syn(60.0), "firing_life": _syn(16000.0), "life_material": _syn(1.0),
           "drag_intake_max": _syn(0.005), "propellant_capability": _syn(1.0),
           **_statewise_records(u13.VALUE_SYNTHETIC, thrust)}
    ev = ao.evaluate_system(row, "hall_icp_neutralizer", supplied=sup)
    ev["design_id"] = design_id
    return ev


def test_full_system_ranking_code_path_with_synthetic_fixtures(small_ctx):
    row = _row(small_ctx)
    a = _syn_eval(row, 0.020, 1.0, 30.0, "SYN-A")
    b = _syn_eval(row, 0.018, 1.2, 31.0, "SYN-B")             # dominated by A
    c = _syn_eval(row, 0.024, 1.5, 29.0, "SYN-C")             # trades with A
    d = _syn_eval(row, 0.010, 1.0, 30.0, "SYN-D")             # violates HC-01 (12 mN) -> excluded
    for ev in (a, b, c, d):
        assert all(o["status"] == ao.SYNTHETIC_ONLY for o in ev["objectives"].values())
    r = ao.rank_full_system([a, b, c, d])
    assert r["status"] == ao.RANK_COMPUTED_SYNTHETIC and r["label"] == ao.SYNTHETIC_ONLY
    assert r["layers"][1] == ["SYN-A", "SYN-C"] and r["layers"][2] == ["SYN-B"]
    assert [e["design_id"] for e in r["excluded"]] == ["SYN-D"] and "HC-01" in r["excluded"][0]["constraints"]
    # mixing synthetic and evidence refuses
    m = _syn_eval(row, 0.020, 1.0, 30.0, "MIX", measured_bus=True)
    assert m["objectives"]["P_bus_W"]["status"] == ao.EVALUATED
    assert ao.rank_full_system([a, m])["status"] == ao.RANK_REFUSED_MIXED
    # one missing objective anywhere refuses the whole ranking (no subset ranking)
    assert ao.rank_full_system([a, ao.evaluate_system(row, "hall_icp_neutralizer")])["status"] == \
        ao.RANK_REFUSED_INCOMPLETE
    assert ao.rank_full_system([d])["status"] == ao.RANK_REFUSED_NO_FEASIBLE


def test_supplied_objective_labels():
    assert ao.supplied_objective("x", {"value": 1.0, "evidence_class": "measured", "source": "s"}, "W")["status"] == \
        ao.EVALUATED
    assert ao.supplied_objective("x", {"value": 1.0, "evidence_class": "model-derived", "source": "s",
                                       "parametric": True}, "W")["status"] == ao.PARAMETRIC_ONLY
    assert ao.supplied_objective("x", {"value": 1.0, "evidence_class": "owner-allocation", "source": "s"},
                                 "W")["status"] == ao.PARAMETRIC_ONLY
    with pytest.raises(ao.OptimizerError):
        ao.supplied_objective("x", {"value": "TBD", "evidence_class": "measured", "source": "s"}, "W")


# ------------------------------------------------------------------------------------------------- F8 helpers
def test_plant_with_overrides_identity_and_effect(inp):
    d = inp.designs["T6-A1-U1-D0-Ti6Al4V-H0.25"]
    p0, p1 = pf.CompressorPlant.from_design(d), ro.plant_with_overrides(d, {})
    assert p0.characteristic() == p1.characteristic() and p0.leak_m3_s == p1.leak_m3_s
    p2 = ro.plant_with_overrides(d, {"turbo_kK": 1.2 * 1.01})
    assert p2.characteristic() != p0.characteristic()
    with pytest.raises(ao.OptimizerError):
        ro.plant_with_overrides(d, {"rpm": 1.0})


def test_perturbed_zero_draw_is_identity(inp):
    st = ao.required_state_ids()[0]
    rec = inp.records[("A0.25_Ld10_phi0.8", "cll_a0.8", st)]
    se = ro.record_se_index(inp.f1)[(10.0, 0.8, "cll_a0.8", st)]
    z = {s: 0.0 for s in ao.SPECIES}
    r2 = ro.perturbed(rec, 0.25, se, z, z)
    assert r2.mdot_fwd_kgps == rec.mdot_fwd_kgps and r2.p_passive_Pa == rec.p_passive_Pa


def test_mc_deterministic_and_theta_node(inp):
    cand = {"design_id": "t", "candidate": "A0.25_Ld10_phi0.8", "compressor": "T3-A1-U2-D0-Ti6Al4V-H0.25",
            "V_m3": 0.001, "P_set_Pa": 0.01, "filter": "F4-FIL-NONE"}
    a = ro.tpmc_monte_carlo(inp, [cand], ["cll_a0.8"], n=4)
    b = ro.tpmc_monte_carlo(inp, [cand], ["cll_a0.8"], n=4)
    assert a == b
    rec = a[("A0.25_Ld10_phi0.8", "F4-FIL-NONE", "T3-A1-U2-D0-Ti6Al4V-H0.25", 0.01)]["cll_a0.8"]
    assert 0.0 <= rec["P_feasible"] <= 1.0 and rec["n"] == 4
    tr = ro.theta_ratio_index(inp.f1)
    assert len(tr) == 10 * 4 * 2 * 3 and all(0 < e <= 1.0 + 1e-9 for e, _ in tr.values())


def test_uq_axes_and_gate_snapshot():
    t = {a["axis"]: a["treatment"] for a in ro.UQ_AXES}
    for k in ("hall_response", "rf_efficiency", "thermal_parameters", "feed_state"):
        assert t[k] == "NOT_EVALUATED"
    assert t["tpmc_statistics"] == "SEEDED_MONTE_CARLO"
    assert t["compressor_performance"] == "LOCAL_ELASTICITY"
    assert [a["axis"] for a in ro.UQ_AXES if a["quantified"]] == ["tpmc_statistics"]
    g = ro.gate_snapshot(ROOT)
    assert g["hall_credible_set"] == "EMPTY" and g["a9_2_statuses"]["ICP electron-current capacity"] == "PENDING_ICP45"


# ------------------------------------------------------------------------------------------------- committed study
def test_committed_structure_and_labels(main_doc):
    d = main_doc
    assert d["status"] == "INVESTIGATION_HYPOTHESIS"
    for k in ("items", "interface_demands", "open_owner_questions", "m16_impact", "design_vector", "findings",
              "architecture_questions", "unlock_evidence", "uq_axes", "robust", "hard_constraints"):
        assert d[k]
    for it in d["items"]:
        for k in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
            assert k in it
    for c in d["compliance"].values():
        assert c in (False, True, 0)
    assert d["compliance"]["tbd_converted_to_assumed_for_optimum"] is False
    for cfg, r in d["system_evaluation"]["ranking"].items():
        assert r["status"] == ao.RANK_REFUSED_INCOMPLETE
    assert d["robust"]["evidence_gates_unchanged"] is True
    assert {q["answer_state"] for q in d["architecture_questions"]} == {"CAN_ANSWER_UNDER_PARAMETRIC_INPUTS",
                                                                        "CANNOT_ANSWER"}
    text = JSON_MAIN.read_text(encoding="utf-8")
    for w in ao.FORBIDDEN_STATUS_WORDS:
        assert f'"status": "{w}' not in text
    assert all(i["direction"] for i in d["interface_demands"])
    assert any("docs/architecture/freeze_candidate/" in i["counterpart"] for i in d["interface_demands"])
    assert not any("PENDING" in i["counterpart"] for i in d["interface_demands"])          # integration pass
    assert any(x.startswith("INT-01") for x in d["limitations"])


def test_committed_pareto_members_and_reproduction(inp):
    p = json.loads(JSON_PARETO.read_text(encoding="utf-8"))
    cols = p["columns"]
    assert p["contexts"] and all(c["system_not_evaluated"] == list(ao.SYSTEM_NOT_EVALUATED_CODES)
                                 for c in p["contexts"])
    ctx = next(c for c in p["contexts"] if c["filter"] == "F4-FIL-NONE" and c["wall"] == "WALL-G0")
    m = dict(zip(cols, ctx["rows"][0]))
    flows = []
    for st in ao.STATES:
        ch = pf.Chain(inp.records[(m["candidate"], ctx["scenario"], st)], inp.filters["F4-FIL-NONE"],
                      inp.plants[m["compressor"]], ao.plenum(m["V_m3"], "WALL-G0"))
        op = pf.steady_operating_point(ch, ctx["P_set_Pa"])
        assert op["status"] == pf.ST_FEASIBLE
        flows.append(op["offered"]["mdot_total_kgps"])
    assert m["mdot_delivered_min_kgps"] == pytest.approx(min(flows), rel=1e-6)
    r = json.loads(JSON_ROBUST.read_text(encoding="utf-8"))
    assert r["rows"] and r["n_mc"] > 0 and len(r["mc_columns"]) == len(next(iter(r["rows"][0]["mc"].values())))


def test_pins_hold(main_doc):
    for p, h in main_doc["pins"].items():
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h, p


def test_md_generated_from_json(main_doc):
    md = MD.read_text(encoding="utf-8")
    assert "Generated by" in md and main_doc["deliverable_status"] in md
    for f in main_doc["findings"]:
        assert f["id"] in md


def test_hygiene_new_files():
    mods = (ROOT / "abep_sim/design/architecture_optimizer.py", ROOT / "abep_sim/design/robust_optimizer.py")
    for p in mods + (BUILDER, Path(__file__)):
        assert "xe" + "_ledger" not in p.read_text(encoding="utf-8")
    t = Path(__file__).read_text(encoding="utf-8")
    assert "pytest." + "skip" not in t and "mark." + "skip" not in t and "xfa" + "il" not in t
    for p in mods:
        code = p.read_text(encoding="utf-8").split('"""', 2)[2]
        assert "archengine" not in code
    for name in (JSON_MAIN, JSON_PARETO, JSON_ROBUST):
        json.loads(name.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------- consolidated verification round 1
def _meas(v):
    return {"value": v, "evidence_class": "measured", "source": "TEST_FIXTURE_NOT_EVIDENCE"}


def test_model_derived_thrust_never_meets_hc01_hc02_while_credible_set_empty(small_ctx):
    """OPT-01: thrust records are routed through the admitted-Hall-member check."""
    row = _row(small_ctx)
    sup = {"thrust": {"value": 0.03, "evidence_class": "model-derived", "source": "x"},
           "thrust_capability": {"value": 0.03, "evidence_class": "model-derived", "source": "x"},
           "firing_life": {"value": 2e4, "evidence_class": "assumed", "source": "x"},
           "thermal_margin": {"value": 80.0, "evidence_class": "assumed", "source": "x"}}
    ev = ao.evaluate_system(row, "hall_icp_neutralizer", supplied=sup)
    st = {c["id"]: c["status"] for c in ev["constraints"]}
    assert st["HC-01"] == st["HC-02"] == ao.C_NOT_EVALUATED
    assert st["HC-06"] == st["HC-07"] == ao.C_MET_PARAMETRIC
    assert ao.C_MET not in st.values()


def _evidence_eval(monkeypatch, row, design_id, cons_rec):
    monkeypatch.setattr(ao, "hall_response_status", lambda repo=ROOT: {
        "admitted_members": ["HYPOTHETICAL"], "credible_set": "NON_EMPTY", "p5_n2_v1_decision": None,
        "sources": []})
    sup = {"thrust": _meas(0.02), "thrust_capability": _meas(0.03), "spacecraft_drag": _meas(0.002),
           "bus": _syn_ledgers("hall_icp_neutralizer", 1.0, measured=True),
           "m_wet": dict(_meas(30.0), all_terms_resolved=True), "Q_reject": _meas(300.0), "I_e_margin": _meas(1.0),
           "thermal_margin": cons_rec(60.0), "firing_life": cons_rec(16000.0), "life_material": _meas(1.0),
           "drag_intake_max": _meas(0.005), "propellant_capability": _meas(1.0),
           **_statewise_records(u13.VALUE_EVIDENCE, 0.02, hall_admitted=True)}
    ev = ao.evaluate_system(row, "hall_icp_neutralizer", supplied=sup)
    ev["design_id"] = design_id
    return ev


def test_assumed_or_synthetic_constraint_values_never_admit_to_evidence_ranking(monkeypatch, small_ctx):
    """OPT-01 / SW-01: HC-06 / HC-07 on assumed values are not met; on synthetic values the ranking refuses MIXED."""
    row = _row(small_ctx)
    a = _evidence_eval(monkeypatch, row, "A", lambda v: {"value": v, "evidence_class": "assumed", "source": "x"})
    st = {c["id"]: c["status"] for c in a["constraints"]}
    assert st["HC-06"] == st["HC-07"] == ao.C_MET_PARAMETRIC
    assert {v for k, v in st.items() if k not in ("HC-06", "HC-07")} == {ao.C_MET}
    r = ao.rank_full_system([a])
    assert r["status"] == ao.RANK_REFUSED_NO_FEASIBLE
    s = _evidence_eval(monkeypatch, row, "S", _syn)
    assert ao.rank_full_system([s])["status"] == ao.RANK_REFUSED_MIXED


def test_ranking_refuses_while_life_material_not_evaluated(monkeypatch, small_ctx):
    """OPT-02: life / material is a ranking gate."""
    row = _row(small_ctx)
    a = _syn_eval(row, 0.020, 1.0, 30.0, "SYN-A")
    a["objectives"]["life_material"] = ao.life_material_indicators()
    r = ao.rank_full_system([a])
    assert r["status"] == ao.RANK_REFUSED_INCOMPLETE and r["missing_counts"] == {"life_material": 1}


def test_ranking_refuses_unlabelled_or_parametric_upstream_objectives(small_ctx):
    """OPT-03: upstream objectives need a status; parametric ones never enter an evidence or synthetic ranking."""
    row = _row(small_ctx)
    a = _syn_eval(row, 0.020, 1.0, 30.0, "SYN-A")
    b = _syn_eval(row, 0.020, 1.0, 30.0, "SYN-B")
    a["upstream"], b["upstream"] = {"P_compressor_el_max_W": 10.0}, {"P_compressor_el_max_W": 5.0}
    r = ao.rank_full_system([a, b], upstream_objectives=["P_compressor_el_max_W"])
    assert r["status"] == ao.RANK_REFUSED_PARAMETRIC_UPSTREAM
    a["upstream"] = {"P_compressor_el_max_W": {"value": 10.0, "status": ao.PARAMETRIC_ONLY}}
    b["upstream"] = {"P_compressor_el_max_W": {"value": 5.0, "status": ao.PARAMETRIC_ONLY}}
    assert ao.rank_full_system([a, b], upstream_objectives=["P_compressor_el_max_W"])["status"] == \
        ao.RANK_REFUSED_PARAMETRIC_UPSTREAM
    a["upstream"] = {"P_compressor_el_max_W": {"value": 10.0, "status": ao.SYNTHETIC_ONLY}}
    b["upstream"] = {"P_compressor_el_max_W": {"value": 5.0, "status": ao.SYNTHETIC_ONLY}}
    r = ao.rank_full_system([a, b], upstream_objectives=["P_compressor_el_max_W"])
    assert r["status"] == ao.RANK_COMPUTED_SYNTHETIC and r["layers"] == {1: ["SYN-B"], 2: ["SYN-A"]}


def test_elasticity_flip_flags_knife_edge_against_nominal(monkeypatch, inp):
    """OPT-06: both perturbations infeasible around a feasible nominal point is a status flip (was silently skipped)."""
    cid = next(iter(inp.designs))
    defaults = pf.cs.module_defaults()
    fixed = [k for k, v in pf.cs.FIELD_ROLES.items() if v[0] == pf.cs.FIXED]

    def fake_eval(states, fc, plant, pl, P, side=None):
        nominal = all(getattr(plant.comp, k) == defaults[k] for k in fixed)
        one = np.array([1.0])
        return {"all_ok": np.array([nominal]), "mdot_min": one, "P_el_max": one, "m_comp_max": one}
    monkeypatch.setattr(ro, "_state_eval", fake_eval)
    sc = next(iter({k[1] for k in inp.records}))
    cand_id = next(k[0] for k in inp.records if k[1] == sc)
    cand = {"compressor": cid, "V_m3": 0.01, "filter": next(iter(inp.filters)), "candidate": cand_id,
            "P_set_Pa": 0.01}
    out = ro.compressor_elasticities(inp, cand, [sc])
    assert out and all(v["status_flip_within_step"] for v in out.values())


def test_hc03_gate_verdict_on_parametric_ledger_never_met():
    """OPT-04: a non-synthetic bus ledger built from assumed loads gives a P_bus PARAMETRIC_SENSITIVITY_ONLY record;
    the A9-02 gate verdict (which ignores evidence class) must not turn HC-03 into MET_ON_SUPPLIED_VALUES."""
    L = _syn_ledgers("hall_icp_neutralizer", 1.0, measured=False)
    L["synthetic"] = False
    ev = ao.evaluate_system({"design_id": "x"}, "hall_icp_neutralizer", supplied={"bus": L})
    hc03 = [c for c in ev["constraints"] if c["id"] == "HC-03"]
    assert len(hc03) == 1
    c = hc03[0]
    assert c["value_status"] == ao.PARAMETRIC_ONLY
    assert c["status"] != ao.C_MET
    assert c["status"] in (ao.C_MET_PARAMETRIC, ao.C_VIOLATED_PARAMETRIC, ao.C_NOT_EVALUATED)
    # direct: a parametric record carrying a PASS verdict maps to the parametric sensitivity status
    out = ao.evaluate_constraints({"P_bus_W": {"status": ao.PARAMETRIC_ONLY, "value": 1000.0, "gate_verdict": "PASS"}})
    hc = [x for x in out if x["id"] == "HC-03"][0]
    assert hc["status"] == ao.C_MET_PARAMETRIC
    out = ao.evaluate_constraints({"P_bus_W": {"status": ao.PARAMETRIC_ONLY, "value": 2000.0, "gate_verdict": "FAIL"}})
    assert [x for x in out if x["id"] == "HC-03"][0]["status"] == ao.C_VIOLATED_PARAMETRIC
    out = ao.evaluate_constraints({"P_bus_W": {"status": ao.EVALUATED, "value": 1000.0, "gate_verdict": "PASS"}})
    assert [x for x in out if x["id"] == "HC-03"][0]["status"] == ao.C_MET


def test_bus_power_counts_efficiency_evidence(monkeypatch):
    """PR #36 review: measured loads with ASSUMED slot or front-end efficiencies never make P_bus EVALUATED."""
    config = "hall_icp_neutralizer"
    gm = {"sample_rate_Sa_s": 2e5, "bandwidth_Hz": 5e4, "anti_alias_documented": True, "synchronized": True,
          "source": "x"}

    def led(eff_ec, fe_ec):
        loads = {s: {"P_W": 10.0, "evidence_class": "measured", "source": "x"} for s in bb.installed_slots(config)}
        loads["icp_rf_source"]["plane"] = "generator_dc_input"
        effs = {s: {"value": 0.9, "evidence_class": eff_ec, "source": "x", "path": "internal_bus"}
                for s in bb.installed_slots(config)}
        st = bb.ledger(config, loads, effs, {"value": 0.95, "evidence_class": fe_ec, "source": "x"},
                       label="T", power_basis="p_bus_1ms_max", gate_measurement=gm)
        return {"steady": st, "startup": [st], "source": "x"}

    assert ao.bus_power(config, None, led("measured", "measured"), ROOT)["status"] == ao.EVALUATED
    assert ao.bus_power(config, None, led("assumed", "measured"), ROOT)["status"] == ao.PARAMETRIC_ONLY
    assert ao.bus_power(config, None, led("measured", "assumed"), ROOT)["status"] == ao.PARAMETRIC_ONLY


def test_thrust_minus_drag_inherits_intake_drag_status(monkeypatch):
    """PR #36 review: with admitted thrust and measured body drag, the F1 (parametric) intake drag keeps T - D
    PARAMETRIC; only a supplied evaluated intake-drag record makes it EVALUATED."""
    monkeypatch.setattr(ao, "hall_response_status", lambda repo=ROOT: {
        "admitted_members": ["HYPOTHETICAL"], "credible_set": "NON_EMPTY", "p5_n2_v1_decision": None,
        "sources": []})
    t, db = _meas(0.03), _meas(0.002)
    assert ao.thrust_minus_drag(0.01, 1e-5, t, db, ROOT)["status"] == ao.PARAMETRIC_ONLY
    o = ao.thrust_minus_drag(0.01, 1e-5, t, db, ROOT, intake_drag=_meas(0.005))
    assert o["status"] == ao.EVALUATED and o["value"] == pytest.approx(0.03 - 0.005 - 0.002)
    assert ao.thrust_minus_drag(0.01, 1e-5, t, db, ROOT, intake_drag=_syn(0.005))["status"] == ao.SYNTHETIC_ONLY


# ------------------------------------------------------------------------- A9.14 S9.8 OD3 / A9.13 S6.1 / S6.13
def test_states_are_the_design_state_set(inp):
    assert ao.STATES == ao.states() == tuple(s.id for s in isy.envelope_states())
    assert ao.STATES[0] == ao.DESIGN_STATE and ao.STATES[1:] == ao.required_state_ids()
    assert len(ao.required_state_ids()) == len(isy.load_design_state_set()["states"])
    assert tuple(inp.f1["coverage_rule"]["orbit_states"]) == ao.STATES
    assert {k[2] for k in inp.records} == set(ao.STATES)
    atm = [a for a in ro.UQ_AXES if a["axis"] == "atmosphere"][0]
    assert atm["members"] == list(ao.STATES) and atm["design_state_set_sha256"] == isy.DESIGN_STATE_SET_SHA256


def test_upstream_context_refuses_a_stale_f1_state_set(inp, monkeypatch):
    full = ao.states()
    monkeypatch.setattr(ao, "states", lambda: full[:5])
    with pytest.raises(RuntimeError):
        ao.load_upstream_inputs(ROOT)


def test_f1q02_intake_mass_is_budgeting_only():
    for bad in ("CBE", "FROZEN_INTAKE_MASS", "STRUCTURAL_QUALIFICATION"):
        with pytest.raises(isy.IntakeMassUseError):
            ao.intake_mass_code_default(0.5, 10.0, 0.9, use=bad)
    with pytest.raises(isy.IntakeMassUseError):                    # an unlabelled intake mass never enters m_wet
        ao.wet_mass("hall_icp_neutralizer", {"AL-01": {"m_intake_parametric_kg": 1.0}})
    rec = ao.intake_mass_budget_record(0.5, 10.0, 0.9)
    o = ao.wet_mass("hall_icp_neutralizer", {"AL-01": rec})
    assert o["status"] == ao.NOT_EVALUATED                         # never a CBE, m_wet stays NOT_EVALUATED
    line = [x for x in o["lines"] if x["line"] == "AL-01"][0]
    assert line["design_parametric"]["f1q02"]["use"] == "BUDGETING_ONLY" and line["cbe_kg"] is None
    blk = {b["block"]: b for b in ao.design_vector_blocks(ROOT)}["x_intake"]
    st = [v for v in blk["variables"] if v["id"] == "x_intake.structure"][0]
    assert st["f1q02"] == isy.f1q02_label()


def test_committed_design_states_flow_gap_and_f1q02(main_doc):
    d = main_doc
    assert d["design_state_set"]["sha256"] == isy.DESIGN_STATE_SET_SHA256
    assert d["orbit_basis_label"] == isy.ORBIT_BASIS_LABEL
    assert d["evaluated_states"]["n"] == len(ao.STATES) and d["evaluated_states"]["n_required"] == len(ao.STATES) - 1
    sg = d["statewise_gate_records"]
    assert sg["n_required_states"] == len(ao.required_state_ids())
    for k in ("AG-13_HC-08", "AG-12_HC-11"):
        assert sg[k]["status"] == ao.C_NOT_EVALUATED and sg[k]["n_required_states"] == sg["n_required_states"]
    assert sg["flight_feed_requirement"]["status"] == "PENDING_EVIDENCE"
    fg = d["flow_gap_owner_order"]
    assert fg == u13.flow_gap_record() and fg["order"][0]["lever"] == "PERFORMANCE_DERIVED_H1_FEED_REQUIREMENT"
    assert d["intake_structural_mass_label"] == isy.f1q02_label()
    assert d["state_set_history"]["superseded_state_set"]["state_ids"] == isy.HISTORY_FIVE_STATE_SET["state_ids"]
    items = {i["id"]: i for i in d["items"]}
    assert items["F78-P-15"]["value"] == "PENDING_EVIDENCE" and items["F78-P-14"]["value"] == isy.DESIGN_STATE_SET_ID
    md = MD.read_text(encoding="utf-8")
    assert "PERFORMANCE_DERIVED_H1_FEED_REQUIREMENT" in md and isy.ORBIT_BASIS_LABEL in md
