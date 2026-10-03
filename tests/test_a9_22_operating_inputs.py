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
    assert (OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, OI.P_BUS_MAX_W, OI.MASS_MAX_KG) == \
        (RFP.thrust_min_mN, RFP.thrust_max_mN, RFP.power_max_W, RFP.mass_max_kg)
    assert set(OI.as_dict()) >= {"mission_hours", "firing_hours", "source"}


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
        (OI.P_BUS_MAX_W, OI.MASS_MAX_KG, OI.THRUST_MIN_mN, OI.THRUST_MAX_mN, OI.FIRING_HOURS)
    c = design_constraints(P_bus_max_W=2500.0, m_max_kg=None)
    assert c.P_bus_max_W == 2500.0 and c.m_max_kg == OI.MASS_MAX_KG   # None means "seam default" here


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
    assert mass_plausibility_screen(per, threshold_kg=OI.MASS_MAX_KG, system_margin_fraction=sm) == \
        mass_bom.plausibility_screen(per, threshold_kg=OI.MASS_MAX_KG, system_margin_fraction=sm)


def test_hard_gates_routed_through_assessment():
    from abep_sim import hard_gates
    from abep_sim.assessment import arch_constraints as AC
    assert callable(AC.evaluate_hard_gates) and callable(AC.evaluate_all_hard_gates)
    assert callable(hard_gates.evaluate) and callable(hard_gates.evaluate_all)
