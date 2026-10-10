"""A9.22 layer separation (owner decisions 2026-10-03): physics / mission modules take operating inputs as explicit
parameters; defaults come only from abep_sim.operating_inputs; evaluation-only constraint checks route through
abep_sim.assessment.arch_constraints."""
import ast
import os

import pytest

from abep_sim import operating_inputs as OI
from abep_sim.constants import RFP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEAM_CONSUMERS = ("archengine", "mission5", "mission_env", "life", "arch_compare", "uq_modular")


def _names(mod):
    tree = ast.parse(open(os.path.join(ROOT, "abep_sim", f"{mod}.py")).read())
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}


@pytest.mark.parametrize("mod", SEAM_CONSUMERS)
def test_no_direct_rfp_in_physics_modules(mod):
    assert "RFP" not in _names(mod), f"abep_sim/{mod}.py reads RFP directly; use abep_sim.operating_inputs"


def test_operating_inputs_seam_values():
    assert OI.FIRING_HOURS == RFP.ignition_hours
    assert (OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, OI.P_BUS_MAX_W) == \
        (RFP.thrust_min_mN, RFP.thrust_max_mN, RFP.power_max_W)
    # owner ruling 2026-10-04: the wet-mass limit is an engineering / assessment constraint, not an operating input
    assert not hasattr(OI, "MASS_MAX_KG") and "mass_max_kg" not in OI.as_dict()
    assert set(OI.as_dict()) >= {"mission_hours", "firing_hours", "source"}


def test_seams_read_the_frozen_config_with_identical_values():
    """A9.22 re-point / A9.23: operating_inputs <- config/mission + config/constraints; engineering_constraints <-
    config/constraints only (neither reads the requirements snapshot). Values identical to the pre-re-point values."""
    from abep_sim import configuration as cfg
    from abep_sim.design import engineering_constraints as ec
    v = cfg.load_operating_inputs()
    assert (OI.MISSION_HOURS, OI.FIRING_HOURS, OI.HISTORICAL_MISSION_HOURS_PRE_A9_22) == (26280.0, 15000.0, 26000.0)
    assert (OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, OI.P_BUS_MAX_W) == (12.0, 25.0, 1500.0)
    assert set(v) == {"mission_hours", "historical_mission_hours", "firing_hours", "firing_hours_label",
                      "thrust_min_mN", "thrust_max_mN", "P_bus_max_W", "source"}   # no wet mass / altitude band
    assert OI.FIRING_HOURS_LABEL == "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"
    assert v["mission_hours"] == OI.MISSION_HOURS and OI.SOURCE.startswith("config/mission/mission_scenario_v2.json")
    for x in (OI.MISSION_HOURS, OI.FIRING_HOURS, OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, OI.P_BUS_MAX_W):
        assert type(x) is float
    assert ec.SOURCE.startswith("config/constraints/engineering_constraints_v1.json")
    for rel in (("operating_inputs.py",), ("design", "engineering_constraints.py")):
        tree = ast.parse(open(os.path.join(ROOT, "abep_sim", *rel)).read())
        mods = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(m.endswith("constants") for m in mods), rel          # no constants.RFP read any more
        assert any(m.endswith("configuration") for m in mods), rel


def test_operating_inputs_fail_closed(tmp_path, monkeypatch):
    import json
    import shutil
    from abep_sim import configuration as cfg
    root = tmp_path / "config"
    shutil.copytree(os.path.join(ROOT, "config"), root)
    rel = cfg.MISSION_REL
    d = json.loads((root / rel).read_text())
    d["inputs"]["mission_hours"]["g1_status"] = "PENDING"
    (root / rel).write_text(json.dumps(d))
    with pytest.raises(cfg.ConfigurationError):          # sha256 differs from MANIFEST
        cfg.load_operating_inputs(root)
    import hashlib
    man = json.loads((root / cfg.MANIFEST_REL).read_text())
    man["files"][rel]["sha256"] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    (root / cfg.MANIFEST_REL).write_text(json.dumps(man))
    with pytest.raises(cfg.ConfigurationError, match="does not match its pin"):      # A9.24 item 4: code-side pin
        cfg.load_operating_inputs(root)
    monkeypatch.setitem(cfg.OPERATING_SCENARIO_PIN, "sha256", hashlib.sha256((root / rel).read_bytes()).hexdigest())
    with pytest.raises(cfg.ConfigurationError, match="APPLIED"):
        cfg.load_operating_inputs(root)


def test_life_inputs_defaults_from_seam():
    from abep_sim.life import LifeInputs
    li = LifeInputs()
    assert li.mission_h == OI.MISSION_HOURS and li.firing_h == OI.FIRING_HOURS


def test_rfp_preset_built_by_assessment_layer():
    from abep_sim.archengine import rfp_preset
    from abep_sim.assessment.arch_constraints import design_constraints
    a, b = rfp_preset(), design_constraints()
    assert a == b
    assert (a.P_bus_max_W, a.m_max_kg, a.T_min_mN, a.T_max_mN, a.life_min_h) == \
        (OI.P_BUS_MAX_W, 40.0, OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, 15000.0)
    from abep_sim.configuration import load_engineering_constraints, load_gate_thresholds
    assert a.m_max_kg == load_engineering_constraints()["mass_max_kg"]          # engineering constraint
    assert a.life_min_h == load_gate_thresholds()["limits"]["HC-07"]            # HC-07 threshold, not OI.FIRING_HOURS
    c = design_constraints(P_bus_max_W=2500.0, m_max_kg=None)
    assert c.P_bus_max_W == 2500.0 and c.m_max_kg == 40.0   # None means "constraint default" here


def test_closure_constraint_flags():
    from abep_sim.archengine import DesignConstraints
    from abep_sim.assessment.arch_constraints import closure_constraint_flags
    f = closure_constraint_flags(20.0, 39.0, 16000.0, DesignConstraints(1500.0, 40.0, 12.0, 25.0, 15000.0))
    assert f == {"thrust_min_ok": True, "thrust_max_ok": True, "mass_ok": True, "life_ok": True, "all_constraints_ok": True}
    f = closure_constraint_flags(30.0, 41.0, 10.0, DesignConstraints(1500.0, 40.0, 12.0, 25.0, 15000.0))
    assert f == {"thrust_min_ok": True, "thrust_max_ok": False, "mass_ok": False, "life_ok": False, "all_constraints_ok": False}
    assert all(closure_constraint_flags(1e9, 1e9, 0.0, DesignConstraints()).values())   # None = no limit


def test_band_cap_flags_caller_limits():
    from abep_sim.assessment.arch_constraints import band_cap_flags, default_limits
    assert band_cap_flags(20.0, 1400.0, default_limits()) == {"thrust_within_rfp_range": True, "P_bus_within_rfp_cap": True}
    assert band_cap_flags(20.0, 1400.0, {"thrust_min_mN": 21.0, "thrust_max_mN": 30.0, "power_max_W": 1000.0}) == \
        {"thrust_within_rfp_range": False, "P_bus_within_rfp_cap": False}


def test_uq_success_flag():
    from abep_sim.assessment.arch_constraints import uq_success
    assert uq_success(1.0, 15000.0, 15000.0) and not uq_success(1.0, 14999.0, 15000.0) and not uq_success(0.99, 1e9, 1.0)


def test_mass_screen_routed_through_assessment():
    # abep_sim/mass_bom.py is pinned immutable by downstream lanes (a9_10 reconciliation, veto layer); the screen is
    # reached with a caller-supplied threshold through the assessment layer.
    from abep_sim import mass_bom
    from abep_sim.assessment.arch_constraints import mass_plausibility_screen
    per = {a: mass_bom.architecture_items(a) for a in mass_bom.ARCHITECTURES}
    sm = mass_bom.SYSTEM_MARGIN["proposed_fraction"]
    from abep_sim.configuration import load_engineering_constraints
    m_max = load_engineering_constraints()["mass_max_kg"]
    assert mass_plausibility_screen(per, threshold_kg=m_max, system_margin_fraction=sm) == \
        mass_bom.plausibility_screen(per, threshold_kg=m_max, system_margin_fraction=sm)


def test_hard_gates_routed_through_assessment():
    from abep_sim import hard_gates
    from abep_sim.assessment import arch_constraints as AC
    assert callable(AC.evaluate_hard_gates) and callable(AC.evaluate_all_hard_gates)
    assert callable(hard_gates.evaluate) and callable(hard_gates.evaluate_all)


# ---------------------------------------------------------------------------------- A9.22 G1 governed baseline change
def test_g1_mission_duration_basis():
    assert OI.MISSION_HOURS == OI.MISSION_DURATION_BASIS_H == 26280.0
    assert OI.FIRING_HOURS == OI.SUBSYSTEM_FIRING_LIFE_ASSUMPTION_H == 15000.0
    assert OI.FIRING_HOURS_LABEL == "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"
    assert OI.HISTORICAL_MISSION_HOURS_PRE_A9_22 == 26000.0


def test_g1_life_and_reliability_keys():
    from abep_sim.life import LifeInputs, reliability, intake_life
    li = LifeInputs()
    assert (li.mission_h, li.firing_h) == (26280.0, 15000.0)
    r = reliability(li, {"x": 1e5})
    assert r["R_mission"] == r["R_26280h"] and r["R_firing"] == r["R_15000h"]
    assert r["R_26000h"] > r["R_26280h"]                       # legacy horizon key is R at 26,000 h, not relabelled
    f = intake_life(LifeInputs(ao_flux_ram_m2_s=1e19))["ao_fluence_m2"]
    assert f == pytest.approx(1e19 * 26280.0 * 3600.0, rel=1e-12)


def test_g1_defaults_are_seam_values():
    import inspect
    from abep_sim import archengine, mission5
    assert inspect.signature(archengine.close_architecture).parameters["firing_hours"].default is None
    for fn in (mission5.run_phase5, mission5.run_mission_generic):
        assert inspect.signature(fn).parameters["hours"].default is None


def test_g1_golden_xe_on_mission_basis():
    import json
    g = json.load(open(os.path.join(ROOT, "abep_sim", "data", "golden_v2.json")))
    c = g["cases"]["architecture_closure"]["ext_hall_2p5kW"]
    assert c["firing_hours_for_xe"] == 26280.0
    assert c["xe_kg"] == pytest.approx(0.05e-6 * 26280.0 * 3600.0 * 1.2, rel=1e-12)
    # the golden_v1 fixture keeps the pre-A9.22 basis verbatim
    v = g["cases"]["nonconverged_reference"]["values"]["architecture_closure"]["ext_hall_2p5kW"]
    assert v["xe_kg"] == pytest.approx(0.05e-6 * 26000.0 * 3600.0 * 1.2, rel=1e-12)


# ---------------------------------------------------------------------------------- A9.22 G4 cathodeless golden
def test_g4_historical_lab6_golden_cases_refused_for_flight_uses():
    from abep_sim import golden as G
    for case in ("architecture_closure", "mission"):
        assert G.CASE_ROLES[case] == "HISTORICAL_NON_FLIGHT_REGRESSION"
        for use in G.FLIGHT_USES:
            with pytest.raises(G.HistoricalNonFlightError):
                G.load_case(case, use)
        assert G.load_case(case, "regression")["golden_role"] == "HISTORICAL_NON_FLIGHT_REGRESSION"
    with pytest.raises(ValueError):
        G.require_flight_eligible_case("architecture_closure", "whatever")
    G.require_flight_eligible_case("hall_icp_neutralizer_reference", "flight_budget")     # active case: allowed
    assert G.HISTORICAL_NON_FLIGHT_ARCHITECTURE == "hall_internal+hall+lab6_xe"
    assert not hasattr(G, "GOLDEN_ARCHITECTURE")


def test_g4_archengine_refuses_lab6_for_flight():
    from abep_sim import archengine as AE
    A = {AE.arch_name(x): x for x in AE.enumerate_architectures()}
    lab6 = A["hall_internal+hall+lab6_xe"]
    assert not AE.flight_eligible(lab6) and AE.flight_eligible(A["hall_internal+hall+rf_cathode"])
    with pytest.raises(AE.FlightIneligibleArchitectureError):
        AE.close_architecture(lab6, lambda *a: {}, None, flight=True)
    df = AE.run_all(lambda *a: {}, None, archs=[lab6], flight=True)
    assert list(df.status) == ["EXCLUDED_HISTORICAL_NON_FLIGHT"] and not bool(df.feasible.iloc[0])


def test_g4_hall_icp_reference_case_content():
    import json
    g = json.load(open(os.path.join(ROOT, "abep_sim", "data", "golden_v2.json")))
    c = g["cases"]["hall_icp_neutralizer_reference"]
    assert c["architecture"] == "hall_icp_neutralizer"
    assert "none" in c["composition"]["hollow_cathode"]
    assert "lab6" not in json.dumps(c).lower().replace("no lab6", "")
    assert c["operating_basis"]["mission_hours"] == 26280.0
    assert c["supply_modes"]["air"]["gaspath_status"] == "CONVERGED"
    assert c["supply_modes"]["xe"]["status"] == "NOT_EVALUATED_NO_ADMITTED_MODEL"
    assert c["ao_exposure_mission"]["ao_fluence_m2"] == pytest.approx(
        c["ao_exposure_mission"]["ao_flux_ram_m2_s"] * 26280.0 * 3600.0, rel=1e-12)
    assert c["mass_ledger"]["totals"]["MEV_kg"] == "NOT_EVALUATED_NO_ADMITTED_MODEL"
    for k in ("hall_accelerator", "icp_neutralizer", "xe_load", "ppu", "thermal"):
        assert c["mass_ledger"][k]["status"] == "NOT_EVALUATED_NO_ADMITTED_MODEL"
    for k in ("hall_discharge_thrust_power", "icp_neutralizer", "p_bus_and_ppu", "thermal", "life", "mission_closure"):
        assert c["not_evaluated"][k]["status"] == "NOT_EVALUATED_NO_ADMITTED_MODEL" and c["not_evaluated"][k]["reason"]
    # no fabricated performance numbers anywhere in the case
    flat = json.dumps(c)
    for key in ("T_mN", "P_bus_W", "thrust_mN", "xe_kg", "I_d_A"):
        assert key not in flat
    # same gas state as the canonical gas_path case
    gp = g["cases"]["gas_path"]["A0.7_p0.05"]
    assert c["supply_modes"]["air"]["mdot_air_mgps"] == gp["mdot_air_mgps"]
    assert c["mass_ledger"]["compressor"]["cbe_kg"] == gp["m_comp_kg"]
