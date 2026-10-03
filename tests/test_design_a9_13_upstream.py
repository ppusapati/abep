"""A9.16 step 3, design layer: owner decisions A9.13 S6.3-S6.21 (+ A9.9 S2.3 / MCC-03, A9.14 S9.7, A9.15, A9.17)
implemented in abep_sim/design (filter_stage, compressor_synthesis, plenum_feed, architecture_optimizer,
robust_optimizer, upstream_a9_13). Every number in the fixtures below is a TEST value (SYNTHETIC_TEST_DATA_NOT_EVIDENCE
or a declared parametric case), never design evidence. Fast (< 30 s)."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from abep_sim import rotor_strength as rs
from abep_sim.design import architecture_optimizer as ao
from abep_sim.design import compressor_synthesis as cs
from abep_sim.design import filter_stage as fs
from abep_sim.design import intake_synthesis as isy
from abep_sim.design import plenum_feed as pf
from abep_sim.design import robust_optimizer as ro
from abep_sim.design import upstream_a9_13 as u13

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "abep_sim/design"
SPECIES = ("O", "N2", "O2")
MD = {"O": 3.0e-7, "N2": 5.0e-7, "O2": 0.7e-7}


# ================================================================================================= fixtures
@pytest.fixture(scope="module")
def recs():
    r = pf.load_f1_records(pf.load_f1(ROOT), [0.5], scenarios=["maxwell_a1"])
    return {(x.candidate, x.scenario, x.state): x for x in r}


@pytest.fixture(scope="module")
def grid():
    d3 = json.loads((ROOT / "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json").read_text())
    return {x["id"]: x for x in d3["design_grid"]}


def _plant(grid, i="T6-A1-U2-D0-Ti6Al4V"):
    return pf.CompressorPlant.from_design(grid[i])


def _pl(V=1e-2):
    return pf.Plenum(V, 0.0, "WALL-G0", pf.RES_DEFAULTS["leak_area_m2"])


def _inlet(p=0.013, label=cs.LABEL_PARAMETRIC, ev="assumed"):
    return cs.InletRecord("t", dict(MD), p, 350.0, label, "test fixture", ev)


# Fixed unit-test turbo areas (the F3 grid areas before the A9.13 S6.8 W1 domain gate re-pinned the data-derived
# A_INLET_MIN_B025_RANGE_M2; review findings RVF-01 / PHY-01). The unit tests below exercise the module on a fixed
# geometry; they must not move when the W1-derived search grid moves. SearchGrid() itself is tested separately.
FIXTURE_A_TURBO_M2 = (0.1128299365, math.pi * 0.25 ** 2, 0.2369348826)


def _design(nt=2, ia=2, u=150.0, nd=0, mat="Ti6Al4V", nu=0.0):
    a = FIXTURE_A_TURBO_M2[ia]
    r = cs.r_turbo_from_area(a, nu)
    return {"id": "x", "N_turbo": nt, "A_turbo_m2": a, "R_turbo_m": r, "u_tip_turbo_mps": u,
            "rpm": cs.rpm_from_tip(u, r), "N_drag": nd, "rotor_material": mat, **cs.hub_geometry(a, nu)}


def _syn_basis(material, bid):
    return rs.RotorStrengthBasis(
        basis_id=bid, materials_db_key=material, material_spec=u13.SYNTHETIC, product_form="synthetic",
        condition="synthetic", section_thickness_range_m=(0.01, 0.1), design_temperature_K=1000.0,
        allowable_basis="synthetic", allowable_source=u13.SYNTHETIC,
        allowables=(rs.AllowablePoint(200.0, 2.0e8, 3.0e8), rs.AllowablePoint(1000.0, 2.0e8, 3.0e8)),
        density_kg_m3=cs.DB[material].density, density_source=u13.SYNTHETIC, factor_yield=1.25, factor_ultimate=1.5,
        factors_source=u13.SYNTHETIC, max_design_speed_rpm=1.0e6, proof_spin_basis="synthetic",
        registration=u13.SYNTHETIC)


def _unit_inlet(**kw):
    one = {s: 1.0e-7 for s in SPECIES}
    return fs.InletState(mdot_forward_kgps=one, mdot_back_incident_kgps={s: 0.0 for s in SPECIES},
                         back_incident_basis="test: zero backflow stated", T_gas_K=350.0, incidence="diffuse_thermal",
                         knudsen_number=10.0, label="PARAMETRIC_SENSITIVITY", provenance="test fixture", **kw)


def _lossfree_case(stage, tau=0.8):
    ov = {"face_area_m2": 0.1, "areal_mass_kg_m2": 1.0}
    for s in stage.transport:
        ov.update({f"tau_f.{s}": tau, f"tau_b.{s}": tau, f"alpha_conductance.{s}": tau, f"capture_f.{s}": 0.0,
                   f"capture_b.{s}": 0.0, f"conversion_f.{s}": 0.0, f"conversion_b.{s}": 0.0})
    return fs.SensitivityCase("SC-T", "PARAMETRIC_SENSITIVITY test", ov, "test", regime_assumption="free_molecular")


# ================================================================================================= decisions / RFP
def test_decision_records_and_rfp_clauses_are_pinned():
    assert all(u13.verify_decision_records(ROOT).values())
    reg = json.loads((ROOT / u13.RFP_REGISTRATION).read_text())
    ids = {c["id"] for c in reg["clauses"]}
    assert set(u13.RFP_CLAUSES.values()) <= ids
    for c in ao.HARD_CONSTRAINTS:
        for cid in (c.get("rfp") or "").replace(";", " ").split():
            if cid.startswith("RFP-"):
                assert cid in ids, (c["id"], cid)


# ================================================================================================= S6.3-S6.6 / S6.19 filter
def test_filter_is_separate_element_with_species_resolved_records():
    stage = fs.FilterStage.tbd("T-1", "FC-TEST")
    assert stage.role == fs.ROLE_BASELINE
    res = stage.apply(_unit_inlet(), _lossfree_case(stage))
    assert res.status == "NUMERIC"
    assert res.interfaces["upstream_interface"].startswith("IF-A1")
    assert res.interfaces["downstream_interface"].startswith("IF-A2")
    assert res.validity_flags["folded_into_intake_efficiency"] is False
    tr = res.species_transmission()
    for s in SPECIES:
        assert tr["species"][s]["forward_transmission"] == pytest.approx(0.8)
        assert tr["species"][s]["reverse_transmission"] == pytest.approx(0.8)
        assert tr["species"][s]["conductance_m3_s"] > 0 and "delta_p_Pa" in tr["species"][s]
    assert res.validity_flags["o_conversion_fraction"] == {"forward": 0.0, "reverse": 0.0}
    assert res.retained_inventory["propellant_capture_rate_kgps"] == 0.0
    assert res.retained_inventory["capacity_kg"]["status"] == "TBD"
    assert res.material_state["application"].startswith("APP-FILTER")
    assert res.thermal_load["status"] == "NOT_EVALUATED"           # no incident power, accommodation TBD
    assert res.admissible_as_baseline is False                     # acceptance pre-registration pending
    rec = res.to_f3_record()
    assert rec["filter_role"] == fs.ROLE_BASELINE and rec["validity_flags"]["species_resolved"] is True
    inv = fs.retained_inventory_kg(res, 3600.0)
    assert inv["retained_kg"] == 0.0 and inv["capacity_margin_kg"].startswith("NOT_EVALUATED")
    # refused stage still exposes its records (fail closed)
    ref = stage.apply(_unit_inlet())
    assert ref.status == "REFUSED_TBD" and ref.species_transmission()["status"] == "NOT_EVALUATED"
    assert ref.retained_inventory["propellant_capture_status"] == "NOT_EVALUATED"


def test_filter_thermal_load_bound_only_with_usable_evidence():
    acc = fs.EV(0.9, "-", "EVIDENCED", "measured", "test fixture (not evidence)", "test")
    stage = fs.FilterStage(**{**fs.FilterStage.tbd("T-2", "FC-TEST").__dict__, "energy_accommodation": acc})
    inlet = _unit_inlet(incident_power_W={s: 0.1 for s in SPECIES}, incident_power_source="test fixture")
    res = stage.apply(inlet, _lossfree_case(stage))
    assert res.thermal_load["status"] == "UPPER_BOUND_GAS_TRANSFER"
    assert res.thermal_load["absorbed_upper_bound_W"] == pytest.approx(0.9 * 0.3)


def test_fc00_is_reference_bound_only_and_catalytic_is_research_variant():
    none = fs.FilterStage.none()
    assert none.role == fs.ROLE_REFERENCE_BOUND
    r = none.apply(_unit_inlet())
    assert r.validity_flags["reference_bound_only"] and r.admissible_as_baseline is False
    with pytest.raises(fs.FilterStageError):            # an element can never carry the reference-bound role
        fs.FilterStage.tbd("T-3", "FC-X", role=fs.ROLE_REFERENCE_BOUND)
    cat = fs.FilterStage.catalytic_research_variant("T-4", "FC-CAT")
    rc = cat.apply(_unit_inlet())
    assert rc.role == fs.ROLE_CATALYTIC_RESEARCH and rc.validity_flags["research_variant_only"]
    assert set(rc.validity_flags["research_variant_evidence_missing"]) == set(fs.CATALYTIC_VARIANT_EVIDENCE)
    assert rc.admissible_as_baseline is False
    with pytest.raises(fs.FilterStageError):
        fs.FilterStage(**{**fs.FilterStage.tbd("T-5", "FC-X").__dict__,
                          "research_variant_evidence": (("species-conversion measurement", "ref"),)})
    # baseline protection targets: particulates / debris; O, wear products and ions are not credited
    assert fs.BASELINE_PROTECTION_TARGETS == ("particulates_debris",)
    assert "atomic_oxygen_to_downstream_surfaces" in fs.NOT_CREDITED_TARGETS


def test_plenum_and_optimizer_carry_filter_roles():
    assert pf.filter_none().reference_bound_only
    assert all(not f.reference_bound_only for f in pf.element_filter_cases())
    assert {f.case_id for f in pf.filter_cases()} - {f.case_id for f in pf.element_filter_cases()} == {"F4-FIL-NONE"}
    assert ao.context_role(pf.filter_none()) == "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE"
    assert ro.NOMINAL_FILTER_ROLE == "REFERENCE_BOUND_FC00_NOT_ADMISSIBLE"


# ================================================================================================= S6.7 hub ratio
def test_hub_ratio_and_blade_span_are_explicit_design_variables():
    a = 0.2
    for nu in cs.HUB_RATIO_PARAMETRIC:
        g = cs.hub_geometry(a, nu)
        r = cs.r_turbo_from_area(a, nu)
        assert math.pi * (r ** 2 - g["R_hub_m"] ** 2) == pytest.approx(a, rel=1e-12)
        assert g["blade_span_m"] == pytest.approx(r - g["R_hub_m"], rel=1e-12)
        assert g["hub_geometry_status"] == (cs.HUB_ZERO_BOUND if nu == 0 else cs.HUB_PARAMETRIC)
    assert cs.r_turbo_from_area(a) == pytest.approx(math.sqrt(a / math.pi))
    ids = [d["id"] for d in cs.SearchGrid(n_turbo=(1,), n_drag=(0,), n_tip_speeds=2).designs()]
    assert any(i.endswith("-H0.5") for i in ids) and any("-H" not in i for i in ids)
    sv = {v["id"]: v for v in cs.search_variables()}
    assert "PARAMETRIC_SENSITIVITY" in sv["hub_ratio"]["status"] and "TBD" in sv["hub_ratio"]["status"]
    d = _design(nu=0.5)
    with pytest.raises(cs.SynthesisInputError):
        cs.validate_design(dict(d, R_turbo_m=d["R_turbo_m"] * 1.1))   # inconsistent geometry refused, not repaired
    with pytest.raises(cs.SynthesisInputError):
        cs.SearchGrid(hub_ratios=(1.0,))


# ================================================================================================= S6.8 / S6.11 domain
def test_above_0p1_pa_is_not_evaluated_out_of_domain_end_to_end(recs, grid):
    r = cs.evaluate_design(_design(), _inlet(p=0.2))
    assert r["status"] == cs.ST_NOT_EVALUATED_OOD and r["outputs"] is None
    assert r["architecture_point_status"] == u13.NOT_EVALUATED_OOD
    res = cs.synthesize(_inlet(p=0.2), grid=cs.SearchGrid(n_turbo=(1,), n_drag=(0,), n_tip_speeds=2))
    assert res["domain"]["design_direction"] == u13.DD_HIGHER_PRESSURE and not res["feasible_ids"]
    it = recs[("A0.5_Ld10_phi0.9", "maxwell_a1", "h200_f150")]
    op = pf.steady_operating_point(pf.Chain(it, pf.filter_none(), _plant(grid), _pl()), 0.2)
    assert op["status"] == u13.NOT_EVALUATED_OOD == pf.ST_OOD and op["offered"] is None
    hp = ao.higher_pressure_branch()
    assert all(h["domain_status"] == u13.NOT_EVALUATED_OOD and h["role"] == "PRIMARY_DESIGN_DIRECTION" for h in hp)
    assert u13.classify_pressure_target(0.05)["role"] == "SENSITIVITY_FALLBACK_STUDY_NOT_PRIMARY"
    assert u13.pressure_domain_status(float("nan")) == u13.NOT_EVALUATED_OOD


def test_transitional_candidate_is_never_consumed():
    from abep_sim import compressor_transitional as ct
    assert u13.TRANSITIONAL_MODEL["evidence_status"] == ct.EVIDENCE_STATUS
    assert u13.P_FREE_MOLECULAR_LIMIT_PA == cs.P_MOLECULAR_LIMIT_PA == ct.P_FREE_MOLECULAR_LIMIT_PA
    for p in DESIGN.glob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "compressor_transitional" not in (node.module or ""), p
                assert all(a.name != "compressor_transitional" for a in node.names), p
            if isinstance(node, ast.Import):
                assert all("compressor_transitional" not in a.name for a in node.names), p
    with pytest.raises(u13.A913RuleError):
        u13.refuse_candidate_evidence({"evidence_status": ct.EVIDENCE_STATUS})


# ================================================================================================= S6.9 / D-05 rotor gate
def test_rotor_acceptance_only_through_registered_basis():
    r = cs.evaluate_design(_design(u=200.0), _inlet())   # ia=2: the fixed 0.237 m^2 fixture area
    assert r["status"] == cs.ST_FEASIBLE
    assert r["diagnostics"]["stress_case"] == cs.STRESS_CASE_LEGACY            # labelled legacy sensitivity
    assert r["rotor_structural_acceptance"] == rs.Q_NOT_EVALUATED_MATERIAL_BASIS
    assert r["outputs"]["rotor_structural_acceptance"] == rs.Q_NOT_EVALUATED_MATERIAL_BASIS
    r = cs.evaluate_design(_design(), _inlet(label=cs.LABEL_INTERFACE, ev="measured"), cs.MODE_STRICT)
    assert r["status"] == cs.ST_NOT_EVALUATED_MATERIAL_BASIS


def test_aluminium_and_cfrp_readmitted_only_through_basis_and_ao_records():
    for m in ("Al6061", "CFRP"):
        assert cs.material_admission(m)["status"] == cs.ST_NOT_EVALUATED_MATERIAL_BASIS
        with pytest.raises(cs.SynthesisInputError):
            cs.SearchGrid(materials=(m,))
    b = _syn_basis("Al6061", "SYN-AL-BASIS")
    rs.register_basis(b)
    try:
        assert cs.material_admission("Al6061")["status"] == cs.ST_NOT_EVALUATED_MATERIAL_BASIS   # AO record missing
        assert cs.material_admission("Al6061", {"ao_disposition": "test"})["status"] == "ADMITTED_VIA_REGISTERED_BASIS"
        cs.SearchGrid(materials=("Al6061",))                       # searchable once a registered basis exists
        d = dict(_design(mat="Al6061", nu=0.5), rotor_strength_basis_id=b.basis_id, rotor_stock_thickness_m=0.05)
        r = cs.evaluate_design(d, _inlet())               # registered basis but no AO disposition: not admitted
        assert r["status"] == cs.ST_NOT_EVALUATED_MATERIAL_BASIS and cs.R_READMISSION_RECORDS in r["reasons"]
        assert r["rotor_structural_acceptance"] == rs.Q_NOT_EVALUATED_MATERIAL_BASIS and r["outputs"] is None
        d["material_extra_basis"] = {"ao_disposition": "test record (not evidence)"}
        r = cs.evaluate_design(d, _inlet())
        assert r["diagnostics"]["stress_case"] == cs.STRESS_CASE_REGISTERED
        assert r["rotor_structural_acceptance"] in (rs.Q_PASS, rs.Q_FAIL)
        fast = dict(d, u_tip_turbo_mps=490.0, rpm=cs.rpm_from_tip(490.0, d["R_turbo_m"]))
        rf = cs.evaluate_design(fast, _inlet())
        assert rf["rotor_structural_acceptance"] == rs.Q_FAIL and cs.R_ROTOR_QUAL_FAIL in rf["reasons"]
        assert rf["status"] == cs.ST_REJECTED
    finally:
        rs.unregister_basis(b.basis_id)
    assert set(cs.READMITTED_MATERIALS["CFRP"]) >= {"laminate_definition", "directional_allowables",
                                                    "ao_disposition"}


def test_life_indicator_labels_legacy_stress_case():
    lm = ao.life_material_indicators({"u_tip_turbo_mps": 300.0, "rotor_material": "Ti6Al4V", "rpm": 10000.0})
    rot = lm["indicators"][0]["value"]
    assert rot["stress_case"] == "LEGACY_PARAMETRIC_SENSITIVITY"
    assert rot["rotor_qualification"] == rs.Q_NOT_EVALUATED_MATERIAL_BASIS


# ================================================================================================= S6.10 schedule
def test_schedule_uses_controller_available_state_only():
    with pytest.raises(u13.A913RuleError):
        u13.ScheduleInput("rho_kg_m3", "onboard_measurement", "x")             # environment truth
    with pytest.raises(u13.A913RuleError):
        u13.ScheduleInput("est:rho_kg_m3", "onboard_measurement", "x")
    est = u13.ScheduleInput("est:rho_kg_m3", "onboard_estimate", "test estimator")
    with pytest.raises(u13.A913RuleError):
        u13.controller_view({"rho_kg_m3": 1.0}, [pf.NAV_ALTITUDE_INPUT], {"nav:alt_km": "rho_kg_m3"})
    assert u13.controller_view({"rho_kg_m3": 1e-10}, [est], {"est:rho_kg_m3": "rho_kg_m3"}) == {"est:rho_kg_m3": 1e-10}
    sch = u13.SetpointSchedule("S", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.02), (230.0, 0.01)),
                               "PARAMETRIC_SENSITIVITY test schedule", "test")
    assert sch.status == u13.SCHEDULE_STATUS and u13.CONTROL_MODES[sch.mode] == "BASELINE_CONTROL_MODE"
    assert sch.setpoint({"nav:alt_km": 205.0})["setpoint_Pa"] == pytest.approx(0.015)
    assert sch.setpoint({"nav:alt_km": 240.0})["status"] == u13.NOT_EVALUATED_OOD   # no extrapolation
    with pytest.raises(u13.A913RuleError):
        sch.setpoint({"nav:alt_km": 205.0, "x_O": 0.5})
    with pytest.raises(u13.A913RuleError):
        u13.SetpointSchedule("S", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.02),), "PARAMETRIC_SENSITIVITY", "t",
                             status="FROZEN")
    with pytest.raises(u13.A913RuleError):
        u13.SetpointSchedule("S", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.02),), "unlabelled", "t")
    hi = u13.SetpointSchedule("H", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.5), (230.0, 0.3)),
                              "PARAMETRIC_SENSITIVITY higher-pressure", "test")
    assert hi.setpoint({"nav:alt_km": 200.0})["domain"]["domain_status"] == u13.NOT_EVALUATED_OOD


def test_scheduled_baseline_and_fixed_fallback_over_orbit_states(recs, grid):
    # nominal (median-density) design states of the nominal mission scenario at 180 / 230 km around the reference
    nom = {s.alt_km: s.id for s in isy.required_states()
           if any(lab == f"NOMINAL_MEDIAN_RHO[ECSS_LT_MODERATE,{s.alt_km:g}km]" for lab in s.labels)}
    states = [recs[("A0.5_Ld10_phi0.9", "maxwell_a1", s)] for s in (nom[180.0], "h200_f150", nom[230.0])]
    sch = u13.SetpointSchedule("S", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.02), (230.0, 0.01)),
                               "PARAMETRIC_SENSITIVITY test schedule", "test")
    fx = u13.FixedSetpoint(0.01, "PARAMETRIC_SENSITIVITY", "test")
    cmp_ = pf.compare_control_modes(pf.filter_none(), _plant(grid), _pl(), states, sch, fx)
    base, ref = cmp_["baseline"], cmp_["fallback_reference"]
    assert base["mode_role"] == "BASELINE_CONTROL_MODE"
    assert ref["mode_role"] == "FALLBACK_DEGRADED_MODE_AND_COMPARISON_REFERENCE"
    assert [r["setpoint"]["setpoint_Pa"] for r in base["rows"]] == pytest.approx([0.02, 0.016, 0.01])
    assert all(set(r["controller_state"]) == {"nav:alt_km"} for r in base["rows"])
    for row in base["rows"]:
        op = pf.steady_operating_point(pf.Chain(states[[s.state for s in states].index(row["state"])],
                                                pf.filter_none(), _plant(grid), _pl()), row["setpoint"]["setpoint_Pa"])
        assert row["status"] == op["status"]
    hi = u13.SetpointSchedule("H", pf.NAV_ALTITUDE_INPUT, ((180.0, 0.5), (230.0, 0.3)), "PARAMETRIC_SENSITIVITY", "t")
    out = pf.scheduled_operation(pf.filter_none(), _plant(grid), _pl(), states, hi)
    assert {r["status"] for r in out["rows"]} == {u13.NOT_EVALUATED_OOD} and out["n_feasible"] == 0
    assert all(r["offered"] is None for r in out["rows"])


# ================================================================================================= S6.12 / S6.17 feed quality
def test_transient_framework_provisional_and_h1_governs_when_tighter():
    assert pf.TRANSIENT_FRAMEWORK["status"].startswith("PROVISIONAL")
    assert pf.TRANSIENT_FRAMEWORK["settling_band_frac"] == pf.SETTLE_BAND == 0.02
    tbd = u13.governing_band("pressure", 0.02, u13.h1_tolerance_tbd("pressure"))
    assert tbd["acceptance_status"] == u13.NOT_EVALUATED and tbd["acceptance_limit_frac"] is None
    tight = u13.governing_band("pressure", 0.02, u13.H1Tolerance("pressure", 0.005, u13.VALUE_SYNTHETIC, "test"))
    assert tight["governing"] == "H1_MEASURED_TOLERANCE" and tight["engineering_target_frac"] == 0.005
    loose = u13.governing_band("pressure", 0.02, u13.H1Tolerance("pressure", 0.05, u13.VALUE_SYNTHETIC, "test"))
    assert loose["acceptance_limit_frac"] == 0.05 and loose["engineering_target_frac"] == 0.02
    fq = pf.feed_quality({"objectives": {"peak_deviation_max": 0.01, "ripple_transfer_shaft": 0.3}})
    assert fq["ripple"]["status"] == u13.C_NOT_EVALUATED and fq["pressure_peak_deviation"]["status"] == u13.NOT_EVALUATED
    fq = pf.feed_quality({"objectives": {"peak_deviation_max": 0.01, "ripple_transfer_shaft": 0.3}},
                         {"ripple": u13.H1Tolerance("ripple", 0.1, u13.VALUE_EVIDENCE, "test")})
    assert fq["ripple"]["status"] == u13.C_VIOLATED_PARAMETRIC               # model ripple: parametric only


def test_ripple_is_a_constraint_not_an_objective():
    assert "ripple_transfer_shaft" not in ao.OBJ_KEYS and "ripple_transfer_shaft" not in pf.OBJECTIVES
    hc12 = [c for c in ao.evaluate_constraints({}) if c["id"] == "HC-12"][0]
    assert hc12["status"] == ao.C_NOT_EVALUATED
    with pytest.raises(u13.A913RuleError):
        u13.pareto_s6_17([], weights={"drag_N": 1.0})


def test_system_pareto_constraints_first_no_scalar():
    obj = lambda m, d: {"worst_state_margin": m, "drag_N": d, "P_upstream_W": 10.0, "mass_kg": 1.0,
                        "volume_m3": 0.01, "Q_reject_W": 5.0}
    rows = [{"id": "A", "objectives": obj(1.0, 0.01), "constraints": {"HC-08": u13.C_MET}},
            {"id": "B", "objectives": obj(0.5, 0.02), "constraints": {"HC-08": u13.C_MET}},
            {"id": "C", "objectives": obj(2.0, 0.03), "constraints": {"HC-08": u13.C_NOT_EVALUATED}},
            {"id": "D", "objectives": obj(9.0, 0.001), "constraints": {"HC-08": u13.C_VIOLATED}},
            {"id": "E", "objectives": dict(obj(1.0, 0.01), Q_reject_W=None), "constraints": {}}]
    p = ao.system_pareto(rows)
    assert p["members"] == ["A", "C"] and p["excluded_violating"][0]["id"] == "D"
    assert p["status"] == "CONDITIONAL_ON_NOT_EVALUATED_CONSTRAINTS" and p["conditional_on"] == ["HC-08"]
    assert p["not_ranked_incomplete_objectives"][0]["id"] == "E"


# ================================================================================================= S6.15 AG-13
def _rec(v, st):
    return lambda s: {"value_N": v(s) if callable(v) else v, "status": st, "source": "test", "state_id": s["state_id"]}


def test_ag13_statewise_never_hidden_by_average():
    states = [{"state_id": "a", "weight": 0.5}, {"state_id": "b", "weight": 0.5}]
    thrust = _rec(lambda s: 0.020 if s["state_id"] == "a" else 0.010, u13.VALUE_SYNTHETIC)
    r = u13.statewise_drag_compensation(states, thrust, _rec(0.012, u13.VALUE_SYNTHETIC), hall_admitted=False)
    assert r["orbit_average_margin_N"] > 0 and r["average_hides_violation"]
    assert r["status"] == u13.C_VIOLATED_SYNTHETIC and r["worst_state"]["state_id"] == "b"
    hc = [c for c in ao.evaluate_constraints({"statewise_T_minus_D": r}) if c["id"] == "HC-08"][0]
    assert hc["status"] == ao.C_VIOLATED and hc["value_status"] == ao.SYNTHETIC_ONLY
    # a parametric thrust prediction without an admitted Hall member is refused
    r = u13.statewise_drag_compensation(states, _rec(0.03, u13.VALUE_PARAMETRIC), _rec(0.01, u13.VALUE_EVIDENCE),
                                        hall_admitted=False)
    assert r["status"] == u13.C_NOT_EVALUATED and r["thrust_refused_no_admitted_hall_member"] == ["a", "b"]
    with pytest.raises(u13.A913RuleError):            # thrust and drag paired at different states
        u13.statewise_drag_compensation(states, lambda s: {"value_N": 1, "status": u13.VALUE_SYNTHETIC,
                                                           "state_id": "zz"}, _rec(0.01, u13.VALUE_SYNTHETIC), False)
    # a single T - D value never closes HC-08
    assert [c for c in ao.evaluate_constraints({"T_minus_D_spacecraft_N": {"status": ao.EVALUATED, "value": 1.0}})
            if c["id"] == "HC-08"][0]["status"] == ao.C_NOT_EVALUATED


def test_ag13_reference_drag_on_orbit_resolved_states_is_reference_only():
    from abep_sim.atmosphere_orbit import orbit_states
    states = orbit_states(200.0, 96.0, 6.0, "ECSS_LT_MODERATE", 100, 0.0, 8)
    drag = u13.reference_drag_fn("RC-ROMANO2018", intake_projected_area_m2=1.0, intake_cd=2.0,
                                 intake_source="test (F1 owns intake drag)", intake_accounting="contained_in_reference")
    r = u13.statewise_drag_compensation(states, _rec(0.5, u13.VALUE_SYNTHETIC), drag, hall_admitted=False)
    assert r["value_status"] == u13.VALUE_SYNTHETIC                 # weakest link: synthetic thrust
    r = u13.statewise_drag_compensation(states, _rec(0.5, u13.VALUE_EVIDENCE), drag, hall_admitted=True)
    assert r["value_status"] == u13.VALUE_REFERENCE and r["status"] == u13.C_MET_PARAMETRIC   # never MET
    assert len(r["statewise"]) == 8 and r["orbit_average_margin_N"] is not None
    hc = [c for c in ao.evaluate_constraints({"statewise_T_minus_D": r}) if c["id"] == "HC-08"][0]
    assert hc["status"] == ao.C_MET_PARAMETRIC


# ================================================================================================= S6.21 AG-12
def test_ag12_feed_state_sufficiency_not_evaluated_without_validated_map():
    states = [{"state_id": "a"}]
    off = lambda s: {"mdot_kgps": 1e-7, "P_Pa": 0.01, "T_K": 350.0, "x_mole": {}, "ripple_frac": 0.0,
                     "status": u13.VALUE_PARAMETRIC}
    r = u13.feed_state_sufficiency(states, off, None)
    assert r["status"] == u13.C_NOT_EVALUATED and "validated H-1" in r["reason"]
    with pytest.raises(u13.A913RuleError):
        u13.feed_state_sufficiency(states, off, None, fixed_mass_flow_gate=0.38e-6)
    cov = u13.characterization_coverage(0.1e-6)
    assert cov["position"] == "BELOW_COVERAGE" and cov["role"] == "CHARACTERIZATION_COVERAGE_NOT_A_REQUIREMENT"
    assert [c for c in ao.evaluate_constraints({}) if c["id"] == "HC-11"][0]["status"] == ao.C_NOT_EVALUATED
    q = {x["id"]: x for x in ao.architecture_questions()}
    assert q["AQ-02b"]["answer_state"] == "CANNOT_ANSWER" and "COVERAGE" in q["AQ-02"]["question"]


def test_ag12_with_a_test_map_is_statewise():
    class M:
        status = u13.SYNTHETIC

        def min_feed_state(self, st, thrust, off):
            return {"mdot_kgps": 1e-7 * (2 if st["state_id"] == "b" else 1), "P_Pa": 0.01, "T_range_K": (300, 400),
                    "x_domain_ok": True, "ripple_tolerance_frac": 0.05}
    states = [{"state_id": "a", "weight": 0.5}, {"state_id": "b", "weight": 0.5}]
    off = lambda s: {"mdot_kgps": 1.5e-7, "P_Pa": 0.02, "T_K": 350.0, "x_mole": {"O": 1.0}, "ripple_frac": 0.01,
                     "status": u13.VALUE_SYNTHETIC}
    r = u13.feed_state_sufficiency(states, off, _rec(0.015, u13.VALUE_SYNTHETIC), M())
    assert r["status"] == u13.C_VIOLATED_SYNTHETIC and r["worst_state"]["state_id"] == "b"
    assert r["field_margins"]["a"]["mdot"] == pytest.approx(0.5)


# ================================================================================================= S6.16 / S6.20
def test_all_admitted_surface_scenarios_required():
    adm = ["maxwell_a1", "cll_a0.8", "cll_a0.5"]
    assert u13.require_all_admitted_scenarios(adm, adm)["status"] == "ALL_ADMITTED_SCENARIOS_COVERED"
    with pytest.raises(u13.A913RuleError):
        u13.require_all_admitted_scenarios(["maxwell_a1"], adm)
    with pytest.raises(u13.A913RuleError):
        u13.require_all_admitted_scenarios(["maxwell_a1"], adm, {"preregistration_id": "P", "measurement_source": "m",
                                                                 "mapping": "x", "admitted_range": "y",
                                                                 "evidence_status": u13.VALUE_PARAMETRIC})
    n = u13.require_all_admitted_scenarios(["maxwell_a1"], adm, {"preregistration_id": "P", "measurement_source": "m",
                                                                 "mapping": "x", "admitted_range": "y",
                                                                 "evidence_status": u13.VALUE_EVIDENCE})
    assert n["narrowed"] and n["preserved_as_sensitivity"] == ["cll_a0.5", "cll_a0.8"]
    ctxs = {(sc, "F4-FIL-NONE", "WALL-G0"): None for sc in adm}
    with pytest.raises(u13.A913RuleError):
        ro.scenario_robustness([], ctxs, ["maxwell_a1"])
    assert u13.robust_over_scenarios({"maxwell_a1": True, "cll_a0.8": False, "cll_a0.5": True}, adm)[
        "robust_feasible"] is False


def test_robust_pareto_set_is_carried_without_representative():
    robust = {0.01: {"members": [{"design_id": "B"}, {"design_id": "A"}]}, 0.02: {"members": [{"design_id": "A"}]}}
    st = ro.carried_robust_set(robust, "2026-10-01.1", "test")
    assert st.members == ("A", "B") and st.to_dict()["representative"].startswith("NONE")
    with pytest.raises(u13.RepresentativeSelectionRefused):
        st.representative()
    ref = st.engineering_reference("A", "single-point thermal study")
    assert ref["label"] == "ENGINEERING_REFERENCE_NOT_THE_FROZEN_ARCHITECTURE"
    assert len(st.pending_triggers()) == len(u13.REGENERATION_TRIGGERS)
    with pytest.raises(u13.A913RuleError):
        u13.RobustParetoSet("S", "1", ("A",), (), "SELECTED set", "p")


# ================================================================================================= A9.15 propellants
def test_dual_propellant_paths_with_separate_tanks():
    ok = u13.propellant_paths_check(ao.MODELLED_PROPELLANT_PATHS)
    assert ok["structure"] == "TWO_SEPARATE_PATHS_DECLARED" and ok["status"] == u13.C_NOT_EVALUATED
    for bad in ({"air": list(u13.AIR_PATH)},
                {"air": list(u13.AIR_PATH), "xe": ["xe_tank", "atmospheric_gas_chamber", "valve"]},
                {"air": ["intake", "compressor", "atmospheric_gas_chamber", "valve"], "xe": list(u13.XE_PATH)},
                {"air": ["intake", "compressor", "filter", "atmospheric_gas_chamber"], "xe": list(u13.XE_PATH)}):
        with pytest.raises(u13.A913RuleError):
            u13.propellant_paths_check(bad)
    hc10 = [c for c in ao.evaluate_constraints({}) if c["id"] == "HC-10"][0]
    assert hc10["status"] == ao.C_NOT_EVALUATED and "RFP-P18-08" in hc10["rfp"]
