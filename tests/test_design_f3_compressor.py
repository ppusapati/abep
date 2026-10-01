"""A9.7 F3 compressor geometry synthesis: module behaviour (fail-closed gates, strict mode, Pareto) and the committed
study (reproduction, labels, pins). Fast (< 30 s): the committed-study reproduction runs the builder once (~5 s)."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from abep_sim.compressor import DragCompressor
from abep_sim.design import compressor_synthesis as cs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design_synthesis/f3_compressor"
BUILDER = OUT / "build_f3_compressor.py"
JSON_MAIN = OUT / "f3_compressor_synthesis_v1.json"
JSON_DESIGNS = OUT / "f3_compressor_designs_v1.json"
MODULE = ROOT / "abep_sim/design/compressor_synthesis.py"

MD = {"O": 3.0e-7, "N2": 5.0e-7, "O2": 0.7e-7}


def _inlet(p=0.013, label=cs.LABEL_PARAMETRIC, ev="assumed", **kw):
    return cs.InletRecord("t", dict(MD), p, 350.0, label, "test fixture", ev, **kw)


def _design(nt=2, ia=1, u=250.0, nd=0, mat="Ti6Al4V"):
    a = cs.SearchGrid().a_turbo_m2[ia]
    r = cs.r_turbo_from_area(a)
    return {"id": "x", "N_turbo": nt, "A_turbo_m2": a, "R_turbo_m": r, "u_tip_turbo_mps": u,
            "rpm": cs.rpm_from_tip(u, r), "N_drag": nd, "rotor_material": mat}


@pytest.fixture(scope="module")
def main_doc():
    return json.loads(JSON_MAIN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def designs_doc():
    return json.loads(JSON_DESIGNS.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------- module
def test_registry_covers_every_dragcompressor_field():
    names = {f.name for f in dataclasses.fields(DragCompressor)}
    assert names == set(cs.FIELD_ROLES)
    reg = cs.coefficient_registry()
    for r in reg:
        for k in ("id", "value", "units", "basis", "source", "evidence_class", "status"):
            assert k in r
    fixed = [r for r in reg if r["role"] == cs.FIXED]
    assert fixed and all(r["evidence_class"] == "assumed" for r in fixed)


def test_search_variables_cover_the_a9_7_list():
    ids = {v["id"] for v in cs.search_variables()}
    assert {"N_turbo", "A_turbo", "R_turbo", "N_drag", "R_rotor", "RPM", "h", "w", "L", "xi"} <= ids
    for v in cs.search_variables():
        assert v["basis"] and v["source"] and v["status"]
        assert v["status"].startswith(("SEARCHED", "FIXED", "DERIVED"))


def test_inlet_record_validation():
    with pytest.raises(cs.SynthesisInputError):
        cs.InletRecord("t", {"O": 1e-7, "N2": 1e-7}, 0.01, 350.0, cs.LABEL_PARAMETRIC, "s", "assumed")
    with pytest.raises(cs.SynthesisInputError):
        cs.InletRecord("t", dict(MD), 0.01, 350.0, "GUESS", "s", "assumed")
    with pytest.raises(cs.SynthesisInputError):
        cs.InletRecord("t", dict(MD), -1.0, 350.0, cs.LABEL_PARAMETRIC, "s", "assumed")
    ok = _inlet()
    conv = ok.module_partial_pressures()
    _inlet(p_species_Pa=conv)                                     # the module convention is accepted
    bad = dict(conv); bad["O"] *= 1.1; bad["N2"] -= conv["O"] * 0.1
    with pytest.raises(cs.SynthesisInputError):
        _inlet(p_species_Pa=bad)                                  # a different split is refused, never repaired


def test_strict_mode_refuses_with_code_defaults():
    res = cs.synthesize(_inlet(), mode=cs.MODE_STRICT)
    assert res["status"] == cs.ST_NOT_EVALUATED and res["designs"] == [] and res["pareto_ids"] == []
    ids = {b["id"] for b in res["blockers"]}
    assert "INLET" in ids and "C-turbo_kK" in ids and "P-TI64-DENSITY" in ids
    r = cs.evaluate_design(_design(), _inlet(), mode=cs.MODE_STRICT)
    assert r["status"] == cs.ST_NOT_EVALUATED and r["outputs"] is None


def test_strict_mode_runs_once_evidence_is_supplied():
    defaults = cs.module_defaults()
    ev = {f: {"value": defaults[f], "evidence_class": "measured", "source": "test fixture"}
          for f, role in cs.FIELD_ROLES.items() if role[0] == cs.FIXED}
    ev["rotor_density"] = {"value": cs.DB["Ti6Al4V"].density, "evidence_class": "measured", "source": "test fixture"}
    inlet = _inlet(label=cs.LABEL_INTERFACE, ev="model-derived")
    assert cs.strict_blockers(inlet, ev) == []
    grid = cs.SearchGrid(n_turbo=(1, 2), a_turbo_m2=(cs.SearchGrid().a_turbo_m2[2],), n_tip_speeds=3, n_drag=(0,))
    res = cs.synthesize(inlet, mode=cs.MODE_STRICT, grid=grid, coefficient_evidence=ev)
    assert res["status"] == "EVALUATED"
    assert all(r["status"] in (cs.ST_FEASIBLE_STRICT, cs.ST_REJECTED) for r in res["designs"])
    assert res["feasible_ids"]


def test_assumed_inlet_must_be_labelled_parametric():
    with pytest.raises(cs.SynthesisInputError):
        cs.synthesize(_inlet(label=cs.LABEL_INTERFACE, ev="assumed"), mode=cs.MODE_PARAMETRIC,
                      grid=cs.SearchGrid(n_turbo=(1,), n_tip_speeds=2, n_drag=(0,)))


def test_mirror_reproduces_module_cascade():
    inlet = _inlet()
    for d in (_design(nt=1), _design(nt=4, nd=2), _design(nt=6, ia=2, u=200.0, nd=4)):
        comp = cs.build_compressor(d, inlet)
        tr = cs.stage_trace(comp, inlet.p_total_Pa, MD)
        ref = comp._run_once(inlet.p_total_Pa, MD)
        assert tr["p_out_Pa"] == pytest.approx(ref["p_out_Pa"], rel=1e-12)
        assert len(tr["stages"]) == d["N_turbo"] + d["N_drag"]


def test_feasible_design_outputs_and_species():
    r = cs.evaluate_design(_design(nt=2, ia=2, u=150.0), _inlet())
    assert r["status"] == cs.ST_FEASIBLE and not r["reasons"]
    o = r["outputs"]
    for k in ("P_out_Pa", "mdot_delivered_kgps", "x_s_out_partial_pressure", "P_compressor_el_W", "m_compressor_kg",
              "T_compressor_K", "CR_by_species", "x_s_delivered_flow_mole"):
        assert k in o
    assert set(o["mdot_delivered_kgps"]) == set(cs.SPECIES)
    assert o["mdot_delivered_total_kgps"] == pytest.approx(sum(MD.values()), rel=1e-12)
    assert sum(o["x_s_out_partial_pressure"].values()) == pytest.approx(1.0, abs=1e-12)
    assert sum(o["x_s_delivered_flow_mole"].values()) == pytest.approx(1.0, abs=1e-12)
    # heavier species compressed more (ln K ~ sqrt(m)); outlet partial-pressure composition O-depleted
    assert o["CR_by_species"]["O"] < o["CR_by_species"]["N2"] < o["CR_by_species"]["O2"]
    assert o["x_s_out_partial_pressure"]["O"] < o["x_s_delivered_flow_mole"]["O"]
    assert o["P_compressor_el_W"] > 0 and o["m_compressor_kg"] > 0


def test_stress_gate_uses_cited_allowable_and_returns_no_values():
    u_allow = math.sqrt(cs.TI64_FTY_A_BASIS_PA / (DragCompressor.stress_safety * cs.DB["Ti6Al4V"].density))
    r = cs.evaluate_design(_design(u=u_allow * 1.01), _inlet())
    assert cs.R_STRESS in r["reasons"] and r["outputs"] is None and r["status"] == cs.ST_REJECTED
    r2 = cs.evaluate_design(_design(u=u_allow * 0.99, ia=2, nt=1), _inlet())
    assert cs.R_STRESS not in r2["reasons"]


def test_material_without_cited_allowable_is_rejected_and_not_searchable():
    r = cs.evaluate_design(_design(mat="Al6061", u=100.0), _inlet())
    assert cs.R_ALLOWABLE_TBD in r["reasons"] and r["outputs"] is None
    with pytest.raises(cs.SynthesisInputError):
        cs.SearchGrid(materials=("CFRP",))


def test_drag_stage_clipping_is_rejected():
    r = cs.evaluate_design(_design(nt=2, ia=2, u=150.0, nd=2), _inlet())
    assert cs.R_CLIP in r["reasons"] and r["diagnostics"]["K_unclipped_min"] < 1.0


def test_domain_gates():
    r = cs.evaluate_design(_design(), _inlet(p=0.2))
    assert cs.R_INLET_DOMAIN in r["reasons"] and r["outputs"] is None
    r = cs.evaluate_design(_design(nt=6, ia=2, u=290.0), _inlet(p=0.05))
    assert cs.R_DOMAIN_P in r["reasons"] and r["diagnostics"]["p_stage_max_Pa"] > cs.P_MOLECULAR_LIMIT_PA
    kn = cs.drag_knudsen_upper({"O": 0.0, "N2": 0.1, "O2": 0.0}, 350.0, 3e-3)
    lam = cs.K_B * 350.0 / (math.sqrt(2) * 0.1 * 0.43e-18)
    assert kn == pytest.approx(lam / 3e-3, rel=1e-12)


def test_non_convergence_is_rejected_without_values(monkeypatch):
    orig = DragCompressor.run

    def half_converged(self, p, md, self_consistent=True):
        r = orig(self, p, md, self_consistent)
        r["recirculated_kgps"] = {s: v * 3.0 + 1e-3 * md[s] for s, v in r["recirculated_kgps"].items()}
        return r

    monkeypatch.setattr(DragCompressor, "run", half_converged)
    r = cs.evaluate_design(_design(nt=2, ia=2, u=150.0), _inlet())
    assert cs.R_NONCONV in r["reasons"] and r["outputs"] is None


def test_overflow_is_a_model_error():
    ev = {"turbo_kK": {"value": 1e6, "evidence_class": "assumed", "source": "test fixture (sensitivity)"}}
    r = cs.evaluate_design(_design(), _inlet(), coefficient_evidence=ev)
    assert cs.R_MODEL in r["reasons"] and r["outputs"] is None


def test_pareto_front_is_non_dominated_and_complete():
    res = cs.synthesize(_inlet(), grid=cs.SearchGrid(n_drag=(0,)))
    recs = {r["id"]: r for r in res["designs"]}
    front = [recs[i] for i in res["pareto_ids"]]
    assert front
    for a in front:
        assert not any(cs._dominates(b["outputs"], a["outputs"], cs.PRIMARY_OBJECTIVES) for b in front if b is not a)
    for i in set(res["feasible_ids"]) - set(res["pareto_ids"]):
        assert cs.is_dominated_by(recs[i]["outputs"], front)
    assert set(res["pareto_ids"]) <= set(res["pareto_with_S_ids"])


def test_size_for_comparison_does_not_touch_size_for():
    before = cs.module_defaults()
    res = cs.synthesize(_inlet(), grid=cs.SearchGrid(n_drag=(0,)))
    front = [r for r in res["designs"] if r["id"] in res["pareto_ids"]]
    sf = cs.size_for_comparison(_inlet(), 5.0, cs.SearchGrid().a_turbo_m2[1], front)
    assert sf["size_for"]["objective"].startswith("mass + 0.02")
    assert sf["gate_status"] in (cs.ST_FEASIBLE, cs.ST_REJECTED)
    assert cs.module_defaults() == before


# ---------------------------------------------------------------------------------------------- committed study
def test_builder_check_reproduces_committed_outputs():
    p = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True,
                       timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def test_committed_study_labels_and_structure(main_doc):
    d = main_doc
    assert d["schema"] == cs.SCHEMA and d["status"].startswith("PARAMETRIC_SENSITIVITY")
    assert d["strict_mode"]["status"] == cs.ST_NOT_EVALUATED and d["strict_mode"]["blockers"]
    assert d["compliance"]["single_optimum_declared"] is False and d["compliance"]["pass_declared"] is False
    for p in d["parameters"]:
        assert p["source"] and p["evidence_class"] and p["status"]
    dirs = {x["direction"] for x in d["interface_demands"]}
    assert dirs == {"requires", "provides"}
    for x in d["interface_demands"]:
        assert "PENDING" not in x["path"]                              # integration pass: real paths + ids
    assert d["open_owner_questions"] and d["m16_impact"][0]["state_after"] == "BLOCKED"
    assert len(d["cases"]) == 36
    for c in d["cases"]:
        assert c["label"] == cs.LABEL_PARAMETRIC
        assert set(c["pareto_ids"]) <= set(c["pareto_with_S_ids"])
        assert c["n_feasible"] + c["n_rejected"] == c["n_designs"]
        assert len(c["size_for_comparison"]) == 3
    text = JSON_MAIN.read_text(encoding="utf-8")
    assert '"PASS"' not in text and '"WINNER"' not in text


def test_committed_designs_keep_every_rejection(main_doc, designs_doc):
    grid = designs_doc["design_grid"]
    codes = designs_doc["reason_codes"]
    for c in main_doc["cases"]:
        cd = designs_doc["cases"][c["case"]]
        st = cd["status_by_design"]
        assert len(st) == len(grid)
        feas_ids = {f["id"] for f in cd["feasible"]}
        assert feas_ids == {g["id"] for g, s in zip(grid, st) if s == "F"}
        assert set(c["pareto_ids"]) <= feas_ids
        for s in st:
            if s != "F":
                assert s and all(x in codes for x in s.split(","))
        tot = sum(c["inlet"]["mdot_kgps"].values())
        for f in cd["feasible"]:
            assert f["outputs"]["mdot_delivered_total_kgps"] == pytest.approx(tot, rel=1e-8)
            assert f["outputs"]["P_out_Pa"] <= cs.P_MOLECULAR_LIMIT_PA * (1 + 1e-9)
            assert f["diagnostics"]["stress_margin"] >= 0.0


def test_pins_hold(main_doc):
    for p, h in main_doc["pins"].items():
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h, p


def test_hygiene_new_files():
    for p in (MODULE, BUILDER, Path(__file__)):
        t = p.read_text(encoding="utf-8")
        assert "xe" + "_ledger" not in t
    t = Path(__file__).read_text(encoding="utf-8")
    assert "pytest." + "skip" not in t and "mark." + "skip" not in t and "xfa" + "il" not in t
    assert "archengine" not in MODULE.read_text(encoding="utf-8").split('"""', 2)[2]


# ------------------------------------------------------------------------- consolidated verification round 1
def test_nan_or_out_of_domain_coefficient_refused_never_fails_open():
    """SW-02: a NaN safety factor used to make the stress gate fail open (even in strict mode)."""
    ev = {"stress_safety": {"value": float("nan"), "evidence_class": "measured", "source": "x"}}
    with pytest.raises(cs.SynthesisInputError):
        cs.evaluate_design(_design(nt=1, ia=0, u=300.0), _inlet(), coefficient_evidence=ev)
    for f, v in (("h_mm", float("nan")), ("w_mm", -1.0), ("xi", 1.5), ("eta_motor", 0.0), ("L_per_stage_m", 0.0)):
        with pytest.raises(cs.SynthesisInputError):
            cs.validate_coefficient(f, v)
    blk = cs.strict_blockers(_inlet(label=cs.LABEL_INTERFACE, ev="measured"), ev)
    assert any(b["id"] == "C-stress_safety" and b["status"] == "NON_FINITE_OR_OUT_OF_DOMAIN" for b in blk)


@pytest.mark.parametrize("bad", [{"rpm": -9410.76}, {"rpm": 0.0}, {"rpm": float("nan")}, {"N_drag": -3},
                                 {"N_turbo": -2}, {"N_turbo": 1.5}, {"rotor_material": "Unobtainium"},
                                 {"A_turbo_m2": 0.0}, {"R_turbo_m": -0.1}])
def test_invalid_design_vector_refused(bad):
    """SW-03: an invalid design vector is refused with SynthesisInputError (never FEASIBLE, never a bare error)."""
    d = dict(_design(), **bad)
    with pytest.raises(cs.SynthesisInputError):
        cs.evaluate_design(d, _inlet())


def test_stress_gate_written_fail_closed():
    src = MODULE.read_text(encoding="utf-8")
    assert "if not margin >= 0.0:" in src


def test_pareto_front_excludes_non_finite_objectives():
    """OPT-04: a NaN objective never joins the front or knocks out a fully evaluated record."""
    good = {"id": "good", "outputs": {"P_out_Pa": 1.0, "mdot_delivered_total_kgps": 1.0, "P_compressor_el_W": 1.0,
                                      "m_compressor_kg": 1.0}}
    nan_row = {"id": "nan_row", "outputs": {"P_out_Pa": 2.0, "mdot_delivered_total_kgps": float("nan"),
                                            "P_compressor_el_W": 0.5, "m_compressor_kg": 0.5}}
    assert cs.pareto_front([good, nan_row]) == ["good"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -4430.0, "x"])
def test_rotor_density_evidence_must_be_finite_and_positive(bad):
    """PR #36 review: a NaN / non-positive cited density never passes the strict evidence gate."""
    defaults = cs.module_defaults()
    ev = {f: {"value": defaults[f], "evidence_class": "measured", "source": "test fixture"}
          for f, role in cs.FIELD_ROLES.items() if role[0] == cs.FIXED}
    ev["rotor_density"] = {"value": bad, "evidence_class": "measured", "source": "test fixture"}
    inlet = _inlet(label=cs.LABEL_INTERFACE, ev="model-derived")
    b = [x for x in cs.strict_blockers(inlet, ev) if x["id"] == "P-TI64-DENSITY"]
    assert b and b[0]["status"] == "NON_FINITE_OR_OUT_OF_DOMAIN"
