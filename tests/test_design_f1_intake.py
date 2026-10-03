"""A9.7 F1 intake geometry synthesis (abep_sim/design/intake_synthesis.py; docs/design_synthesis/f1_intake/).
Tiny grids only (< 30 s). The committed study is checked structurally; its full rebuild is the builder's --check."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from abep_sim.constants import M_SPECIES
from abep_sim.design import intake_synthesis as F1
from abep_sim.intake_tpmc import IntakeGeometry, intake_response

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/design_synthesis/f1_intake"
BUILDER = OUT / "build_f1_intake.py"


def _builder():
    spec = importlib.util.spec_from_file_location("f1_builder", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _labelled(label: str):
    """The required design state carrying ``label`` (e.g. the envelope density maximum); exactly one."""
    st = [s for s in F1.required_states() if label in s.labels]
    assert len(st) == 1, label
    return st[0]


DENSEST = _labelled("ENVELOPE_MAX_rho_kg_m3")
RAREST = _labelled("ENVELOPE_MIN_rho_kg_m3")
HOTTEST = _labelled("ENVELOPE_MAX_T_K")

TINY = F1.StudySpec(areas_m2=(0.5, 1.0, 2.0), d_mm=(5.0, 10.0), L_over_d=(3.0, 20.0), phi=(0.9,), alphas=(0.5, 1.0),
                    kernels=("maxwell",), states=(F1.DESIGN_STATE, DENSEST), n_direct=300,
                    cd_calibration_nodes=((3.0, 1.0, "N2"),), cd_calibration_replicates=3,
                    surface_check_nodes=((3.0, 0.9, 1.0, "N2"),))


@pytest.fixture(scope="module")
def tiny():
    return F1.run_study(TINY)


def test_phi_reconstruction_matches_intake_response():
    st = RAREST
    ev = F1.Evaluator(n_direct=300, force_direct=True, cd_rel_sd_at_n=(0.01, 300))
    for phi, th in ((0.8, 0.0), (0.9, 5.0)):
        p = ev.point(st, 5.0, phi, 0.5, th, "maxwell", "O")
        seed = ev.direct_core(st, 5.0, 0.5, th, "maxwell", "O")["seed"]
        r = intake_response(IntakeGeometry(L_over_d=5.0, phi=phi), st.atm(), 0.5, th, n=300, seed=seed,
                            scattering="maxwell", species_mass=M_SPECIES["O"])
        assert p.source == "DIRECT_TPMC"
        for a, b in ((p.eta_c, r["eta_c"]), (p.C_D_row, r["C_D"]), (p.K_back, r["K_back"]), (p.CR_passive, r["CR_passive"])):
            assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15)


def test_mass_formula_matches_intake_tpmc_and_nominal_is_tbd():
    c = F1.GeometryCandidate(0.5, 10.0, 10.0, 0.85)
    r = intake_response(IntakeGeometry(area_m2=0.5, d_mm=10.0, L_over_d=10.0, phi=0.85), F1.DESIGN_STATE.atm(), 1.0, n=50,
                        seed=1)
    m = F1.intake_mass(c, F1.STRUCTURAL_CODE_DEFAULT)
    assert math.isclose(m["m_intake_kg"], r["mass_kg"], rel_tol=1e-12)
    assert m["status"] == "PARAMETRIC_SENSITIVITY_CASE"
    nom = F1.intake_mass(c, F1.STRUCTURAL_NOMINAL)
    assert nom["m_intake_kg"] is None and nom["status"] == "TBD"
    assert "wall_thickness_mm" in nom["missing"] and "wall_density_kg_m3" not in nom["missing"]
    # d-independence of the geometric wall area
    assert math.isclose(F1.GeometryCandidate(0.5, 3.0, 10.0, 0.85).wall_area_m2, c.wall_area_m2)


def test_d_invariance_of_tpmc_outputs():
    atm = F1.DESIGN_STATE.atm()
    a = intake_response(IntakeGeometry(d_mm=10.0, L_over_d=5.0), atm, 0.8, 2.0, n=400, seed=3, species_mass=M_SPECIES["N2"])
    b = intake_response(IntakeGeometry(d_mm=5.0, L_over_d=5.0), atm, 0.8, 2.0, n=400, seed=3, species_mass=M_SPECIES["N2"])
    for k in ("eta_c", "K_back", "CR_passive", "C_D"):
        assert math.isclose(a[k], b[k], rel_tol=0.02), k


def test_surface_used_only_at_exact_node_and_build_state():
    assert F1.surface_node("maxwell", "O", 7.0, 0.9, 1.0, 0.0) is None
    assert F1.surface_node("maxwell", "O", 10.0, 0.9, 1.0, 0.0) is not None
    assert F1.surface_covers(F1.DESIGN_STATE, "maxwell", "O", 10.0, 0.9, 1.0, 0.0)
    assert not F1.surface_covers(F1.OrbitState(180.0, 70.0), "maxwell", "O", 10.0, 0.9, 1.0, 0.0)
    # a design state of the orbit-resolved set is never covered (NOT_COVERED -> direct TPMC; never extrapolated)
    assert not any(F1.surface_covers(st, "maxwell", "O", 10.0, 0.9, 1.0, 0.0) for st in F1.required_states())
    assert not F1.surface_covers(F1.DESIGN_STATE, "maxwell", "O", 10.0, 0.9, 0.9, 0.0)
    ev = F1.Evaluator(n_direct=200, cd_rel_sd_at_n=(0.01, 200))
    p = ev.point(F1.DESIGN_STATE, 10.0, 0.9, 1.0, 0.0, "cll", "N2")
    assert p.source == "FROZEN_SURFACE" and ev.direct_runs == 0
    row = F1.surface_node("cll", "N2", 10.0, 0.9, 1.0, 0.0)
    assert p.eta_c == row["eta_c"] and p.CR_passive == row["CR_passive"]
    q = ev.point(F1.DESIGN_STATE, 7.0, 0.9, 1.0, 0.0, "cll", "N2")      # off-node -> direct, never interpolated
    assert q.source == "DIRECT_TPMC" and ev.direct_runs == 1
    # species C_D normalisation (finding F1-01)
    assert math.isclose(p.C_D_species, p.C_D_row * p.m_mean_run_kg / M_SPECIES["N2"], rel_tol=1e-12)


def test_frozen_atmosphere_guard(monkeypatch):
    monkeypatch.setattr(F1, "atmosphere", lambda *a, **k: {"source": "NRLMSIS 2.1 (pymsis), orbit-averaged"})
    with pytest.raises(RuntimeError):
        F1.OrbitState(200.0, 150.0).atm()


def _row(cid, **v):
    base = {"candidate": cid, "feasible": True}
    for k, s, e in F1.OBJECTIVES:
        base[k] = v.get(k, 1.0)
        if e:
            base[e] = v.get(e, 0.0)
    base.update({k: x for k, x in v.items() if k == "feasible"})
    return base


def test_pareto_filter_semantics():
    rows = [
        _row("a", mdot_captured_kgps=2.0),                                   # dominates b
        _row("b", mdot_captured_kgps=1.0),
        _row("c", mdot_captured_kgps=1.0, drag_N=0.5),                      # trade vs a
        _row("d", mdot_captured_kgps=1.0, drag_N=0.5),                      # tie with c
        _row("e", mdot_captured_kgps=0.99, drag_N=0.5, mdot_captured_se_kgps=0.1),   # dominated by c only within noise
        _row("f", mdot_captured_kgps=99.0, feasible=False),                 # infeasible never ranked / never dominates
    ]
    st = F1.pareto_filter(rows)
    assert st == {"a": "NONDOMINATED", "b": "DOMINATED", "c": "NONDOMINATED", "d": "NONDOMINATED",
                  "e": "NONDOMINATED_WITHIN_NOISE", "f": "INFEASIBLE"}


def test_tiny_study(tiny):
    res = tiny
    for vname in ("design_case", "envelope"):
        for sid, v in res["views"][vname].items():
            assert v["pareto_set_invariant_under_p_ref_sweep"] is True
            assert sum(v["counts"].values()) == len(TINY.candidates())
            # d variants tie: groups collapse d
            for g in v["nondominated_groups_d_collapsed"]:
                assert g["d_mm"] == sorted(TINY.d_mm)
    rows = res["candidate_rows"]["envelope"]["maxwell_a1"]
    # A = 2 m^2 at the envelope density maximum must exceed the 25 mN RFP bound -> fail closed with a reason
    big = [r for r in rows if r["area_m2"] == 2.0]
    assert big and all(not r["feasible"] and any("C-DRAG-RFP" in x for x in r["infeasible_reasons"]) for r in big)
    assert all(r["pareto_status"] == "INFEASIBLE" for r in big)
    srcs = {r["source"] for r in res["species_rows"]}
    assert srcs == {"FROZEN_SURFACE", "DIRECT_TPMC"}
    assert all(r["state_id"] == F1.DESIGN_STATE.id for r in res["species_rows"] if r["source"] == "FROZEN_SURFACE")
    # objectives: no scalar score anywhere
    assert not any("score" in k for k in rows[0])


def test_fail_closed_on_nonconverged_tpmc(monkeypatch):
    real = F1.intake_response

    def bad(*a, **k):
        r = real(*a, **k)
        r["converged"] = False
        r["unresolved_fraction"] = 0.5
        return r
    monkeypatch.setattr(F1, "intake_response", bad)
    spec = F1.StudySpec(areas_m2=(0.5,), d_mm=(10.0,), L_over_d=(3.0,), phi=(0.9,), alphas=(0.8, 1.0), kernels=("maxwell",),
                        states=(F1.DESIGN_STATE, HOTTEST), n_direct=100,
                        cd_calibration_nodes=((3.0, 1.0, "N2"),), cd_calibration_replicates=2,
                        surface_check_nodes=((3.0, 0.9, 1.0, "N2"),))
    res = F1.run_study(spec)
    env = res["candidate_rows"]["envelope"]["maxwell_a1"][0]
    assert not env["feasible"] and any("MODEL_ERROR" in x for x in env["infeasible_reasons"])
    assert env["pareto_status"] == "INFEASIBLE"
    rec = [r for r in res["if_a1_unit_area"] if r["state"] == HOTTEST.id][0]
    assert rec["status"] == "MODEL_ERROR"


def test_if_a1_record_for_filter_stage():
    ev = F1.Evaluator(n_direct=200, cd_rel_sd_at_n=(0.01, 200))
    c = F1.GeometryCandidate(0.8, 10.0, 10.0, 0.9)
    rec = F1.if_a1_record(ev, c, F1.DESIGN_STATE, F1.Scenario(0.8, "maxwell"))
    assert set(rec["species"]) == set(F1.SPECIES)
    assert math.isclose(sum(v["mdot_fwd_kgps"] for v in rec["species"].values()), rec["mdot_fwd_total_kgps"], rel_tol=1e-12)
    assert math.isclose(sum(v["x_mole_passive"] for v in rec["species"].values()), 1.0, rel_tol=1e-12)
    assert math.isclose(sum(v["p_passive_Pa"] for v in rec["species"].values()), rec["p_passive_total_Pa"], rel_tol=1e-12)
    assert all(v["T_K"] == F1.T_WALL_K for v in rec["species"].values())
    # net-flow law and burden helpers
    assert F1.net_flow_fraction(0.0, 1.0) == 1.0 and F1.net_flow_fraction(1.0, 1.0) == 0.0
    assert F1.compressor_burden(0.2, 0.01) == pytest.approx(20.0)


def test_committed_outputs_consistent():
    doc = json.loads((OUT / "f1_intake_synthesis_v1.json").read_text())
    b = _builder()
    assert (OUT / "F1_INTAKE_SYNTHESIS.md").read_text() == b.render_md(doc)
    for k in ("items", "interface_demands", "open_owner_questions", "m16_impact", "pareto", "candidate_metrics",
              "species_table", "if_a1_interface", "findings", "pins", "compliance"):
        assert k in doc, k
    assert doc["status"] == "INVESTIGATION_HYPOTHESIS"
    for p in doc["pins"]:
        assert hashlib.sha256((REPO / p["path"]).read_bytes()).hexdigest() == p["sha256"], p["path"]
    for it in doc["items"]:
        assert {"id", "value", "units", "basis", "source", "evidence_class", "status"} <= set(it)
        assert it["evidence_class"] in b.EVIDENCE_CLASSES
        if it["value"] == "TBD":
            assert it["status"] == "TBD"
    c = doc["compliance"]
    assert not c["single_optimum_or_winner_declared"] and not c["pass_declared"] and not c["surface_extrapolated"]
    assert not c["tbd_converted_to_assumed_for_optimum"]
    for vw in doc["pareto"].values():
        for v in vw.values():
            assert v["pareto_set_invariant_under_p_ref_sweep"] is True
    tab = doc["species_table"]
    i_src, i_state = tab["columns"].index("source"), tab["columns"].index("state_id")
    assert all(r[i_state] == F1.DESIGN_STATE.id for r in tab["rows"] if r[i_src] == "FROZEN_SURFACE")
    assert any(d["counterpart"].startswith("abep_sim/design/filter_stage.py") for d in doc["interface_demands"])
    assert not any("PENDING" in d["counterpart"] for d in doc["interface_demands"])     # integration pass
    # A9.14 S9.8 OD3: the committed study evaluated the design-case reference + EVERY required design state (no subset)
    cr = doc["coverage_rule"]
    assert cr["orbit_states"] == [s.id for s in F1.envelope_states()]
    assert cr["orbit_states"][0] == F1.DESIGN_STATE.id and len(cr["orbit_states"]) == 1 + len(F1.required_states())
    ds = cr["design_state_set"]
    assert ds["sha256"] == F1.DESIGN_STATE_SET_SHA256 and ds["n_required_states"] == len(F1.required_states())
    assert ds["subset_used"] is False and ds["orbit_basis_label"] == F1.ORBIT_BASIS_LABEL
    assert doc["orbit_basis_label"] == F1.ORBIT_BASIS_LABEL
    assert len(cr["design_states"]["rows"]) == len(F1.required_states())
    assert {r["state"] for r in doc["if_a1_interface"]["records_per_unit_area"]} == set(cr["orbit_states"])
    assert set(tab["rows"][i][i_state] for i in range(len(tab["rows"]))) == set(cr["orbit_states"])
    # design states are never covered by the frozen surface
    assert all(r[i_src] == "DIRECT_TPMC" for r in tab["rows"] if r[i_state] != F1.DESIGN_STATE.id)
    # history of the superseded five-state set is kept as a labelled record
    assert doc["state_set_history"]["superseded_state_set"]["state_ids"] == F1.HISTORY_FIVE_STATE_SET["state_ids"]
    # A9.13 S6.1 / F1Q-02: the intake structural mass is a budgeting sensitivity only
    lab = doc["intake_structural_mass_label"]
    assert lab["label"] == "PARAMETRIC_SENSITIVITY" and lab["use"] == "BUDGETING_ONLY"
    assert set(lab["not"]) == {"CBE", "FROZEN_INTAKE_MASS", "STRUCTURAL_QUALIFICATION"}
    assert lab["lock1_condition"] == "SOURCED_STRUCTURAL_DEFINITION_REQUIRED_BEFORE_LOCK_1"
    f9 = [f for f in doc["findings"] if f["id"] == "F1-09"][0]
    assert f9["f1q02"] == lab


def test_lane_files_hygiene():
    files = [REPO / "abep_sim/design/intake_synthesis.py", BUILDER, Path(__file__)]
    needle = "xe_" + "ledger"
    for f in files:
        assert needle not in f.read_text()
    imports = [ln for ln in (REPO / "abep_sim/design/intake_synthesis.py").read_text().splitlines()
               if ln.startswith(("import ", "from "))]
    assert not any(x in ln for ln in imports for x in ("filter_stage", "compressor_synthesis", "archengine"))


# ------------------------------------------------------------------------- consolidated verification round 1
@pytest.mark.parametrize("args", [(-5.0, 0.9, 1.0, 0.0, "maxwell", "N2"), (10.0, 1.5, 1.0, 0.0, "maxwell", "N2"),
                                  (10.0, -0.2, 1.0, 0.0, "maxwell", "N2"), (10.0, 0.9, 1.7, 0.0, "maxwell", "N2"),
                                  (10.0, 0.9, -0.3, 0.0, "maxwell", "N2"), (10.0, 0.9, 1.0, 95.0, "maxwell", "N2"),
                                  (10.0, 0.9, 1.0, float("nan"), "maxwell", "N2"),
                                  (10.0, 0.9, 1.0, 0.0, "specular", "N2"), (10.0, 0.9, 1.0, 0.0, "maxwell", "Ar")])
def test_evaluator_refuses_out_of_domain_inputs(args):
    """SW-04: no TPMC is run and no number returned outside the evaluator domain (no silent Maxwell fallback)."""
    ev = F1.Evaluator(n_direct=50)
    L, phi, alpha, theta, kern, sp = args
    with pytest.raises(F1.IntakeInputError):
        ev.point(F1.DESIGN_STATE, L, phi, alpha, theta, kern, sp)
    assert ev.direct_runs == 0


@pytest.mark.parametrize("bad", [(-0.5, 5.0, 10.0, 0.9), (0.5, 0.0, 10.0, 0.9), (0.5, 5.0, -1.0, 0.9),
                                 (0.5, 5.0, 10.0, 1.2), (0.5, 5.0, 10.0, 0.0)])
def test_geometry_candidate_refuses_invalid(bad):
    with pytest.raises(F1.IntakeInputError):
        F1.GeometryCandidate(*bad)


def test_cache_keys_are_exact_states():
    """SW-05 (CLAUDE.md rule 5): a 200.4 km state never shares a cache entry or seed with the 200 km design state."""
    s = F1.OrbitState(200.4, 150.0)
    assert s.id != F1.DESIGN_STATE.id and s.key != F1.DESIGN_STATE.key
    assert F1.DESIGN_STATE.id == "h200_f150"
    ev = F1.Evaluator(n_direct=50)
    a = ev.atm(s)
    b = ev.atm(F1.DESIGN_STATE)
    assert a is not b and a["rho"] != b["rho"]


def test_pareto_filter_non_finite_row_not_evaluated():
    """OPT-04: a NaN objective is NOT_EVALUATED and never dominates a fully evaluated row."""
    st = F1.pareto_filter([_row("good"), _row("nan_row", mdot_captured_kgps=2.0, drag_N=float("nan"))])
    assert st == {"good": "NONDOMINATED", "nan_row": "NOT_EVALUATED_NON_FINITE_OBJECTIVE"}


# ------------------------------------------------------------------------- A9.14 S9.8 OD3 design-state set
def test_design_state_set_pinned_and_complete():
    d = F1.load_design_state_set()
    raw = (REPO / F1.DESIGN_STATE_SET_REL).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == F1.DESIGN_STATE_SET_SHA256
    req = F1.required_states()
    assert len(req) == d["n_states"] == 196 and all(s.required for s in req)
    env = F1.envelope_states()
    assert env[0] is F1.DESIGN_STATE and env[1:] == req          # reference first, then every required state, no subset
    labels = {lab.split("[")[0] for s in req for lab in s.labels}
    assert {"NOMINAL_MEDIAN_RHO", "MAX_rho_kg_m3", "MIN_rho_kg_m3", "MAX_T_K", "MIN_T_K", "LST_PEAK",
            "LST_TROUGH", "ENVELOPE_MAX_rho_kg_m3"} <= labels
    assert F1.ENVELOPE_STATES == env and F1.REQUIRED_STATES == req


def test_design_state_atmosphere_record():
    from abep_sim.atmosphere import orbital_velocity
    st = DENSEST
    a = st.atm()
    assert math.isclose(a["fO"] + a["fN2"] + a["fO2"], 1.0, rel_tol=1e-12)
    assert a["rho"] == st.rho_kg_m3 and a["T"] == st.T_K and a["V"] == orbital_velocity(st.alt_km)
    assert a["orbit_basis"] == F1.ORBIT_BASIS_LABEL and F1.DESIGN_STATE_SET_SHA256 in a["source"]
    assert st.key != F1.DESIGN_STATE.key and st.id.startswith("ds2:")
    assert F1.state_alt_km(st.id) == st.alt_km and F1.state_role(st.id) == "REQUIRED_DESIGN_STATE"
    assert F1.state_role(F1.DESIGN_STATE.id) == "DESIGN_CASE_REFERENCE_POINT"
    with pytest.raises(F1.IntakeInputError):
        F1.state_alt_km("h180_f230")                            # superseded corner: not an evaluated state any more


def _isolated_data_dir(tmp_path, monkeypatch, mutate=None, drop=None):
    for name in (Path(F1.DESIGN_STATE_SET_REL).name, Path(F1.DESIGN_STATE_MANIFEST_REL).name):
        if name == drop:
            continue
        b = (REPO / "abep_sim/data" / name).read_bytes()
        if mutate and name == mutate[0]:
            b = mutate[1](b)
        (tmp_path / name).write_bytes(b)
    monkeypatch.setattr(F1, "DATA_DIR", str(tmp_path))
    F1.load_design_state_set.cache_clear()
    F1.required_states.cache_clear()
    F1.state_index.cache_clear()


@pytest.mark.parametrize("case", ["missing_set", "missing_manifest", "altered_set"])
def test_design_state_set_fails_closed(tmp_path, monkeypatch, case):
    name = Path(F1.DESIGN_STATE_SET_REL).name
    try:
        if case == "missing_set":
            _isolated_data_dir(tmp_path, monkeypatch, drop=name)
        elif case == "missing_manifest":
            _isolated_data_dir(tmp_path, monkeypatch, drop=Path(F1.DESIGN_STATE_MANIFEST_REL).name)
        else:
            _isolated_data_dir(tmp_path, monkeypatch, mutate=(name, lambda b: b.replace(b'"alt_km": 180.0', b'"alt_km": 181.0', 1)))
        with pytest.raises(F1.DesignStateSetError):
            F1.required_states()
        with pytest.raises(F1.DesignStateSetError):
            F1.StudySpec()                                       # no fallback state set for the study either
    finally:
        monkeypatch.undo()
        F1.load_design_state_set.cache_clear()
        F1.required_states.cache_clear()
        F1.state_index.cache_clear()
    assert len(F1.required_states()) == 196


def test_prefill_matches_serial_direct_runs():
    pts = [(st, ld, al, 0.0, k, sp) for st in (DENSEST, RAREST) for ld in (3.0,) for al in (0.0, 1.0)
           for k in ("maxwell", "cll") for sp in ("O", "N2")]
    a = F1.Evaluator(n_direct=80)
    n = a.prefill_direct(pts, workers=2)
    b = F1.Evaluator(n_direct=80)
    for p_ in pts:
        ra, rb = a.direct_core(*p_), b.direct_core(*p_)
        assert ra["seed"] == rb["seed"]
        assert all(ra["r"][k] == rb["r"][k] for k in ("eta_c", "C_D", "K_back", "CR_passive", "unresolved_fraction"))
    assert n == len(pts) == a.direct_runs == b.direct_runs
    assert a.prefill_direct(pts, workers=2) == 0                 # cached points are never re-run


def test_f1q02_intake_mass_budgeting_only():
    c = F1.GeometryCandidate(0.5, 10.0, 10.0, 0.9)
    m = F1.intake_mass(c, F1.STRUCTURAL_CODE_DEFAULT)
    assert m["f1q02"] == F1.f1q02_label() and m["f1q02"]["use"] == "BUDGETING_ONLY"
    for bad in ("CBE", "FROZEN_INTAKE_MASS", "STRUCTURAL_QUALIFICATION", "anything"):
        with pytest.raises(F1.IntakeMassUseError):
            F1.intake_mass(c, F1.STRUCTURAL_CODE_DEFAULT, use=bad)
    F1.require_f1q02_label(m)
    for rec in ({"m_intake_kg": 1.0}, {"f1q02": dict(F1.f1q02_label(), use="CBE")}, None):
        with pytest.raises(F1.IntakeMassUseError):
            F1.require_f1q02_label(rec)
