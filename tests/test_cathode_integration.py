"""Tests for abep_sim.cathode_integration (CATHINT lane 19).

Hand calculations, current conservation, refusal paths and validation of the sourced data file. Every number that is
not read from the data file is a test input for the arithmetic only (labelled 'assumed'), never a project value.
Runs in a few seconds; needs no other lane's files (the bus-boundary module is faked where it is exercised).
"""
import copy
import dataclasses
import inspect
import json
import math
import os
import subprocess
import sys
import types

import pytest

from abep_sim import cathode_integration as ci
from abep_sim.constants import RFP, E_CHARGE, K_B, AMU

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(REPO, "docs", "architecture_comparison", "cathode_integration")
SRC = "test arithmetic input (not a project value)"


def S(v, unit, ev="assumed"):
    return ci.Sourced(v, unit, SRC, ev)


@pytest.fixture(scope="module")
def data():
    return ci.load_data()


# ------------------------------------------------------------------------------------------------ hand calculations

def test_richardson_hand_calc():
    # J = A T^2 exp(-e phi/(k T)) at T = 1900 K, A = 29 A/cm2/K2, phi = 2.67 eV:
    # e phi/(k T) = 2.67 / (8.617333262e-5 * 1900) = 16.30743 ; 29 * 1900^2 * exp(-16.30743) = 8.66344 A/cm2
    assert ci.richardson_current_density_A_cm2(1900.0, 29.0, 2.67, 0.0) == pytest.approx(8.663444389, rel=1e-8)


def test_richardson_linear_work_function_equals_modified_constant():
    # phi = phi0 + alpha T is the same as a constant phi0 with D = A exp(-e alpha/k) (Goebel & Katz Eq. 6.3-3)
    A, phi0, alpha = 120.0, 2.66, 1.23e-4
    D = A * math.exp(-E_CHARGE * alpha / K_B)
    for T in (1500.0, 1800.0, 2100.0):
        assert ci.richardson_current_density_A_cm2(T, A, phi0, alpha) == pytest.approx(
            ci.richardson_current_density_A_cm2(T, D, phi0, 0.0), rel=1e-12)
    assert D == pytest.approx(28.79, abs=0.01)     # close to Lafferty's D = 29 (Table 6-1 consistency)


def test_emitter_temperature_inverts_richardson():
    for J in (0.5, 5.0, 10.0, 20.0):
        T = ci.emitter_temperature_K(J, 29.0, 2.67, 0.0, T_min_K=300.0, T_max_K=4000.0)
        assert ci.richardson_current_density_A_cm2(T, 29.0, 2.67, 0.0) == pytest.approx(J, rel=1e-8)


def test_lafferty_evaporation_hand_calc():
    # W = 10^(13 - 36850/1900) / sqrt(1900) = 10^(-6.394737) / 43.589 = 9.24456e-9 g/cm2/s
    assert ci.lafferty_evaporation_rate_g_cm2_s(1900.0, 36850.0, 13.0) == pytest.approx(9.24456238e-9, rel=1e-8)


def test_life_hand_calc():
    W = ci.lafferty_evaporation_rate_g_cm2_s(1900.0, 36850.0, 13.0)
    life = ci.evaporation_limited_life_h(1900.0, 36850.0, 13.0, 4.0, 0.1, 0.5)
    assert life == pytest.approx(4.0 * 0.1 / (W * 0.5) / 3600.0, rel=1e-12)
    # hotter evaporates faster
    assert ci.evaporation_limited_life_h(1950.0, 36850.0, 13.0, 4.0, 0.1, 0.5) < life


def test_discharge_current_envelope_hand_calc():
    # T = 25 mN, mdot = 1.5 mg/s: P_jet >= T^2/(2 mdot) = 6.25e-4/3e-6 = 208.333 W
    b = ci.discharge_current_bounds_A(0.025, 1.5e-6, 300.0, 10.0, 1200.0)
    assert b["P_jet_min_W"] == pytest.approx(208.3333333, rel=1e-9)
    assert b["I_d_lower_A"] == pytest.approx((208.3333333 - 10.0) / 300.0, rel=1e-8)
    assert b["I_d_upper_A"] == pytest.approx(4.0)
    assert b["feasible"]
    # other power larger than the jet minimum: the lower bound clips at zero
    assert ci.discharge_current_bounds_A(0.025, 1.5e-6, 300.0, 500.0, 1200.0)["I_d_lower_A"] == 0.0


def test_xe_mass_hand_calc():
    m = ci.mission_cathode_xe_kg(0.44, 15000.0, 100.0, 1.0, 600.0, 0.1, 11000.0)
    assert m["firing_kg"] == pytest.approx(0.44 * 15000 * 3600 / 1e6)        # 23.76 kg
    assert m["firing_kg"] == pytest.approx(23.76)
    assert m["ignition_kg"] == pytest.approx(1.0 * 600 * 100 / 1e6)          # 0.06 kg
    assert m["standby_kg"] == pytest.approx(0.1 * 11000 * 3600 / 1e6)        # 3.96 kg
    assert m["total_kg"] == pytest.approx(23.76 + 0.06 + 3.96)
    assert ci.max_cathode_flow_for_mass_mg_s(40.0, 15000.0) == pytest.approx(40e6 / (15000 * 3600))


def test_flux_equivalent_pressure_roundtrip():
    # a Maxwellian gas at p, T has one-sided flux n v_mean/4 (Goebel & Katz Eq. 3.4-12); invert back to p
    m, T, p = 16.0 * AMU, 300.0, 1.0e-3
    n = p / (K_B * T)
    flux = 0.25 * n * math.sqrt(8.0 * K_B * T / (math.pi * m))
    assert ci.flux_equivalent_pressure_Pa(flux, m, T) == pytest.approx(p, rel=1e-12)
    assert ci.ram_number_flux_m2_s(2.0e15, 7.8e3) == pytest.approx(1.56e19)
    assert ci.required_attenuation(1e-5, 1e-6) == pytest.approx(10.0)


def test_sccm_conversion(data):
    k = ci.parameter_value(data, "xe_mg_s_per_sccm")
    assert ci.mg_s_to_sccm(0.0983009, k) == pytest.approx(1.0)


# ------------------------------------------------------------------------------------------------ current continuity

def test_current_budget_hand_example():
    c = ci.electron_current_budget(3.0, 2.1, 0.5, 0.2)
    assert c["I_emit_A"] == pytest.approx(3.7)
    assert c["I_plume_neutralization_A"] == pytest.approx(2.1)
    assert c["I_emit_minus_neutralization_A"] == pytest.approx(1.6)
    assert c["current_utilization_Ib_over_Id"] == pytest.approx(0.7)
    assert c["kirchhoff_residual_A"] == 0.0


@pytest.mark.parametrize("I_d,I_b,I_k,I_x", [(1.0, 0.7, 0.0, 0.0), (4.2, 3.9, 0.0, 0.0), (2.5, 1.0, 1.5, 0.0),
                                             (3.0, 2.9, 0.0, 0.4), (3.0, 3.2, 0.0, 0.4), (5.0, 0.0, 2.0, -1.0)])
def test_current_conservation(I_d, I_b, I_k, I_x):
    c = ci.electron_current_budget(I_d, I_b, I_k, I_x)
    # sum of conventional currents into the plasma: anode + keeper + interstage - cathode, plume net zero
    assert I_d + I_k + I_x - c["I_emit_A"] + (-I_b + I_b) == pytest.approx(0.0, abs=1e-15)
    assert c["I_emit_A"] - c["I_plume_neutralization_A"] - c["I_keeper_A"] >= -1e-15


def test_neutralization_is_inside_discharge_current():
    c = ci.electron_current_budget(3.0, 2.4, 0.0, 0.0)
    assert c["I_emit_A"] == 3.0                    # not I_d + I_beam = 5.4


def test_beam_above_net_emission_refused():
    with pytest.raises(ci.CathodeIntegrationError, match="current-free"):
        ci.electron_current_budget(2.0, 2.5, 1.0, 0.0)     # keeper current cannot neutralize the beam
    with pytest.raises(ci.CathodeIntegrationError):
        ci.electron_current_budget(1.0, 0.5, 0.0, -1.5)    # non-positive emission


# ------------------------------------------------------------------------------------------------ poisoning screen

def test_o2_screen_against_data_points(data):
    ep = ci.poisoning_evidence_points(data)
    assert ci.oxygen_poisoning_screen(5e-5, 1900.0, ep)["status"] == "WITHIN_REPORTED_NO_DEGRADATION"
    assert ci.oxygen_poisoning_screen(2e-5, 1700.0, ep)["status"] == "IN_REPORTED_DEGRADATION_RANGE"
    assert ci.oxygen_poisoning_screen(5e-6, 1750.0, ep)["status"] == "WITHIN_REPORTED_NO_DEGRADATION"
    assert ci.oxygen_poisoning_screen(5e-5, 1750.0, ep)["status"] == "NO_EVIDENCE_AT_THIS_STATE"
    assert ci.oxygen_poisoning_screen(1e-6, 1700.0, ep)["status"] == "NO_EVIDENCE_AT_THIS_STATE"
    assert ci.oxygen_poisoning_screen(1e-3, 1900.0, ep)["status"] == "NO_EVIDENCE_AT_THIS_STATE"


def test_o2_screen_refusals():
    with pytest.raises(ci.CathodeIntegrationError):
        ci.oxygen_poisoning_screen(1e-5, 1800.0, ())
    with pytest.raises(ci.CathodeIntegrationError):
        ci.oxygen_poisoning_screen(1e-5, 1800.0, ({"id": "x", "kind": "maybe", "T_K": {"op": ">=", "value": 1},
                                                  "p_O2_Torr": {"op": "<=", "value": 1}},))
    with pytest.raises(ci.CathodeIntegrationError):
        ci.oxygen_poisoning_screen(1e-5, 1800.0, ({"id": "x", "kind": "no_degradation", "T_K": {"op": "~", "value": 1},
                                                  "p_O2_Torr": {"op": "<=", "value": 1}},))


# ------------------------------------------------------------------------------------------------ scenario evaluation

def _phases(arch, preion_seed):
    pre = {"rf_hall": {"rf_source": S(80.0, "W")}, "ecr_hall": {"ecr_magnet": S(20.0, "W"), "ecr_source": S(80.0, "W")},
           "hall_only": {}}[arch]
    ph = [ci.StartupPhase("preheat", S(600.0, "s"), {"cathode_heater": S(45.0, "W"), "housekeeping": S(5.0, "W")}),
          ci.StartupPhase("cathode_ignition", S(60.0, "s"), {"cathode_heater": S(45.0, "W"), "cathode_keeper": S(30.0, "W"),
                                                           "flow_control": S(2.0, "W"), "housekeeping": S(5.0, "W"),
                                                           **(pre if preion_seed else {})}),
          ci.StartupPhase("discharge_ignition", S(30.0, "s"), {"hall_discharge": S(900.0, "W"), "hall_magnet": S(40.0, "W"),
                                                             "cathode_keeper": S(30.0, "W"), "flow_control": S(2.0, "W"),
                                                             "housekeeping": S(5.0, "W")})]
    if not preion_seed and pre:
        ph.append(ci.StartupPhase("preionizer_on", S(30.0, "s"), {"hall_discharge": S(900.0, "W"), "hall_magnet": S(40.0, "W"),
                                                                "flow_control": S(2.0, "W"), "housekeeping": S(5.0, "W"),
                                                                **pre}))
    return tuple(ph)


def _inputs(data, arch, *, I_d=3.0, I_b=2.2, topology="floating", I_x=None, keeper_on=False, basis="conditional_scenario",
            member=None, ev="assumed", envelope=True, preion_seed=False, flow=0.3):
    ic = None if arch == "hall_only" else ci.InterstageCircuit(topology, I_x, "test declaration")
    keeper = ci.KeeperState("on", S(0.5, "A"), S(12.0, "V")) if keeper_on else ci.KeeperState("off_floating", None, None)
    env = (ci.CurrentEnvelopeInputs(S(0.020, "N"), S(1.3e-6, "kg/s"), S(300.0, "V"), S(100.0, "W"), S(1200.0, "W"))
           if envelope else ci.TBD("requires thrust, total mass flow, V_d and power split"))
    return ci.CathodeIntegrationInputs(
        operating_point=ci.DischargeOperatingPoint(S(I_d, "A", ev), S(I_b, "A", ev), basis, member),
        interstage=ic, keeper=keeper, heater_steady_W=S(0.0, "W"),
        flow=ci.CathodeFlowSpec("fixed_mg_s", S(flow, "mg/s"), None),
        mission=ci.MissionUsage(S(26000.0, "h"), S(15000.0, "h"), S(15000.0, "h"), S(500.0, "1"), S(0.6, "mg/s"),
                                S(600.0, "s"), S(0.0, "mg/s"), S(0.0, "h")),
        emitter=ci.EmitterSpec(
            S(1.0, "cm2"),
            ci.parameter_sourced(data, "lab6_richardson_A_lafferty", "measured"),
            ci.parameter_sourced(data, "lab6_work_function_lafferty_iepc2017", "measured"),
            S(0.0, "eV/K", "model-derived"),
            ci.parameter_sourced(data, "lab6_evaporation_B_lafferty", "measured"),
            ci.parameter_sourced(data, "lab6_evaporation_C_lafferty", "measured"),
            S(4.0, "g/cm3"), S(0.1, "cm"), S(0.0, "1"), S(50.0, "K")),
        startup=_phases(arch, preion_seed),
        envelope=env,
        poisoning=ci.PoisoningInputs(ci.TBD("requires emitter-region partial pressure (shielding model or test)"),
                                     S(100.0, "K"), ("O", "N2"), ci.poisoning_evidence_points(data)))


@pytest.mark.parametrize("arch", ci.ARCHITECTURES)
def test_evaluate_architecture_outputs(data, arch):
    r = ci.evaluate_architecture(arch, _inputs(data, arch))
    assert r["architecture"] == arch and r["boundary_version"] == ci.BOUNDARY_VERSION
    assert r["electron_current"]["I_emit_A"] == pytest.approx(3.0)
    assert r["xe"]["firing_kg"] == pytest.approx(0.3 * 15000 * 3600 / 1e6)
    assert r["xe"]["ignition_kg"] == pytest.approx(0.6 * 600 * 500 / 1e6)
    assert set(r["boundary_loads_steady_W"]) == set(ci.CATHODE_BOUNDARY_COMPONENTS)
    assert r["boundary_loads_steady_W"] == {"cathode_keeper": 0.0, "cathode_heater": 0.0}
    em = r["emitter"]
    assert em["J_A_cm2"] == pytest.approx(3.0)
    assert ci.richardson_current_density_A_cm2(em["T_uniform_K"], 29.0, 2.67, 0.0) == pytest.approx(3.0, rel=1e-8)
    assert em["T_evaporation_K"] == pytest.approx(em["T_uniform_K"] + 50.0)
    assert em["life_h"] == pytest.approx(ci.evaporation_limited_life_h(em["T_evaporation_K"], 36850.0, 13.0, 4.0, 0.1, 0.0))
    assert r["poisoning"]["O2"]["status"] == "TBD"
    assert r["poisoning"]["O"]["status"] == "NO_QUANTITATIVE_EVIDENCE"
    assert r["milestone_support"] == ["A"] and r["absolute_performance_claim"] is False
    assert "operating_point.I_d_A" in r["evidence"]["assumed_inputs"]
    assert "poisoning.p_O2_equiv_at_emitter_Torr" in r["evidence"]["tbd_inputs"]


def test_startup_transient_hand_calc(data):
    r = ci.evaluate_architecture("hall_only", _inputs(data, "hall_only"))["startup"]
    # preheat 50 W x 600 s, ignition 82 W x 60 s, discharge 977 W x 30 s
    assert r["peak_W"] == pytest.approx(977.0) and r["peak_phase"] == "discharge_ignition"
    assert r["energy_Wh"] == pytest.approx((50 * 600 + 82 * 60 + 977 * 30) / 3600)
    assert r["cathode_energy_Wh"] == pytest.approx((45 * 600 + 45 * 60 + 30 * 60 + 30 * 30) / 3600)
    assert r["duration_s"] == pytest.approx(690.0)


def test_preionizer_overlap_changes_startup_peak_only_when_scheduled_so(data):
    after = ci.evaluate_architecture("ecr_hall", _inputs(data, "ecr_hall", preion_seed=False))["startup"]
    seed = ci.evaluate_architecture("ecr_hall", _inputs(data, "ecr_hall", preion_seed=True))["startup"]
    assert after["peak_W"] == pytest.approx(977.0 - 30.0 + 100.0)      # keeper off, pre-ionizer on with discharge
    assert seed["profile"][1]["total_W"] == pytest.approx(82.0 + 100.0)  # heater + pre-ionizer overlap


def test_keeper_on_adds_emission_and_power(data):
    r = ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", keeper_on=True))
    assert r["electron_current"]["I_emit_A"] == pytest.approx(3.5)
    assert r["boundary_loads_steady_W"]["cathode_keeper"] == pytest.approx(6.0)


def test_separately_biased_interstage_current(data):
    r = ci.evaluate_architecture("rf_hall", _inputs(data, "rf_hall", topology="separately_biased", I_x=S(0.4, "A")))
    assert r["electron_current"]["I_emit_A"] == pytest.approx(3.4)
    assert r["electron_current"]["I_interstage_A"] == pytest.approx(0.4)


def test_hardware_measurement_supports_milestone_B_only_without_gaps(data):
    inp = _inputs(data, "hall_only", basis="hardware_measurement", ev="measured")
    r = ci.evaluate_architecture("hall_only", inp)
    assert r["absolute_performance_claim"] is True
    assert r["milestone_support"] == ["A"]        # assumed inputs and poisoning gaps remain


def test_compare_architectures_never_ranks(data):
    res = {a: ci.evaluate_architecture(a, _inputs(data, a)) for a in ci.ARCHITECTURES}
    c = ci.compare_architectures(res, rel_tol=0.01, xe_budget_kg=S(10.0, "kg"), bus_power_limit_W=S(1500.0, "W"),
                                 dominance_fraction=S(0.25, "1"))
    assert c["ranking"] is None and c["conditional"] is True
    assert not c["differs"]["I_emit_A"] and not c["differs"]["cathode_xe_total_kg"]
    assert c["differs"]["startup_peak_W"]
    assert c["common_mode_flags"] == ["cathode_xe_could_dominate_xe_budget"]      # 16.2 + 0.18 kg > 2.5 kg everywhere
    assert any("common-mode" in s for s in c["statements"])
    with pytest.raises(ci.CathodeIntegrationError):
        ci.compare_architectures({"rf_hall": res["hall_only"]}, rel_tol=0.01, xe_budget_kg=S(10.0, "kg"),
                                 bus_power_limit_W=S(1500.0, "W"), dominance_fraction=S(0.25, "1"))


def test_envelope_tbd_is_reported_not_invented(data):
    r = ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", envelope=False))
    assert "TBD" in r["discharge_current_envelope"]


# ------------------------------------------------------------------------------------------------ refusal paths

def test_refusals_architecture_and_interstage(data):
    with pytest.raises(ci.CathodeIntegrationError, match="unknown architecture"):
        ci.evaluate_architecture("gridded", _inputs(data, "hall_only"))
    inp = _inputs(data, "rf_hall")
    with pytest.raises(ci.CathodeIntegrationError, match="hall_only has no pre-ionizer"):
        ci.evaluate_architecture("hall_only", inp.__class__(**{**inp.__dict__, "startup": _phases("hall_only", False)}))
    with pytest.raises(ci.CathodeIntegrationError, match="declared explicitly"):
        ci.evaluate_architecture("rf_hall", inp.__class__(**{**inp.__dict__, "interstage": None}))
    with pytest.raises(ci.CathodeIntegrationError, match="Kirchhoff"):
        ci.evaluate_architecture("rf_hall", _inputs(data, "rf_hall", topology="floating", I_x=S(0.1, "A")))
    with pytest.raises(ci.CathodeIntegrationError, match="missing input"):
        ci.evaluate_architecture("ecr_hall", _inputs(data, "ecr_hall", topology="separately_biased", I_x=None))
    with pytest.raises(ci.CathodeIntegrationError, match="topology"):
        ci.evaluate_architecture("ecr_hall", _inputs(data, "ecr_hall", topology="grounded"))


def test_refusals_hall_performance_sources(data):
    with pytest.raises(ci.CathodeIntegrationError, match="SCREENING"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", basis="admitted_closure", member="sgb-screen-01"))
    with pytest.raises(ci.CathodeIntegrationError, match="not an admitted"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", basis="admitted_closure", member="made-up-01"))
    with pytest.raises(ci.CathodeIntegrationError, match="needs closure_member_id"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", basis="admitted_closure", member=None))
    with pytest.raises(ci.CathodeIntegrationError, match="screening candidates never"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", member="sgb-screen-01"))
    with pytest.raises(ci.CathodeIntegrationError, match="must be 'measured'"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", basis="hardware_measurement", ev="assumed"))
    with pytest.raises(ci.CathodeIntegrationError, match="basis"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", basis="hall1d_estimate"))


def test_refusals_envelope_and_mission(data):
    with pytest.raises(ci.CathodeIntegrationError, match="outside the conservation/power envelope"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", I_d=0.1, I_b=0.05))   # lower bound 0.179 A
    with pytest.raises(ci.CathodeIntegrationError, match="outside the conservation/power envelope"):
        ci.evaluate_architecture("hall_only", _inputs(data, "hall_only", I_d=4.5, I_b=3.0))
    inp = _inputs(data, "hall_only")
    m = inp.mission
    bad = ci.MissionUsage(m.mission_h, S(20000.0, "h"), m.required_firing_h, m.starts, m.ignition_flow_mg_s,
                          m.ignition_duration_s, S(0.1, "mg/s"), S(7000.0, "h"))
    with pytest.raises(ci.CathodeIntegrationError, match="exceeds mission_h"):
        ci.evaluate_architecture("hall_only", inp.__class__(**{**inp.__dict__, "mission": bad}))


def test_refusals_inputs(data):
    with pytest.raises(ci.CathodeIntegrationError):
        ci.Sourced(1.0, "A", SRC, "guessed")
    with pytest.raises(ci.CathodeIntegrationError):
        ci.Sourced(float("nan"), "A", SRC, "assumed")
    with pytest.raises(ci.CathodeIntegrationError):
        ci.Sourced(1.0, "A", "  ", "assumed")
    with pytest.raises(ci.CathodeIntegrationError):
        ci.TBD("")
    with pytest.raises(TypeError):
        ci.KeeperState("on", S(1.0, "A"))          # every field is required: no defaults
    inp = _inputs(data, "hall_only")
    with pytest.raises(ci.CathodeIntegrationError, match="unit"):
        ci.evaluate_architecture("hall_only", inp.__class__(**{**inp.__dict__, "heater_steady_W": S(0.0, "kW")}))
    with pytest.raises(ci.CathodeIntegrationError, match="TBD"):
        ci.evaluate_architecture("hall_only", inp.__class__(**{**inp.__dict__, "heater_steady_W": ci.TBD("requires test")}))
    with pytest.raises(ci.CathodeIntegrationError, match="missing input"):
        ci.evaluate_architecture("hall_only", inp.__class__(**{**inp.__dict__, "keeper": ci.KeeperState("on", None, None)}))
    with pytest.raises(ci.CathodeIntegrationError, match="ambiguous"):
        ci.evaluate_architecture("hall_only", inp.__class__(
            **{**inp.__dict__, "keeper": ci.KeeperState("off_floating", S(1.0, "A"), None)}))
    with pytest.raises(ci.CathodeIntegrationError, match="anode"):
        ci.cathode_xe_flow_mg_s("fraction_of_anode_flow", 0.08, None)
    with pytest.raises(ci.CathodeIntegrationError):
        ci.cathode_xe_flow_mg_s("per_ampere", 0.1, None)
    with pytest.raises(ci.CathodeIntegrationError, match="redeposition"):
        ci.evaporation_limited_life_h(1900.0, 36850.0, 13.0, 4.0, 0.1, 1.0)
    with pytest.raises(ci.CathodeIntegrationError, match="needs more than"):
        ci.emitter_temperature_K(1e6, 29.0, 2.67, 0.0, T_min_K=300.0, T_max_K=4000.0)
    with pytest.raises(ci.CathodeIntegrationError):
        ci.richardson_current_density_A_cm2(-5.0, 29.0, 2.67, 0.0)


def test_refusals_startup(data):
    ok = _phases("rf_hall", False)
    with pytest.raises(ci.CathodeIntegrationError, match="not on the rf_hall boundary"):
        ci.startup_transient("rf_hall", ok + (ci.StartupPhase("x", S(1.0, "s"), {"ecr_magnet": S(1.0, "W")}),))
    with pytest.raises(ci.CathodeIntegrationError, match="never powers its pre-ionizer"):
        ci.startup_transient("rf_hall", _phases("hall_only", False))
    with pytest.raises(ci.CathodeIntegrationError, match="not on the hall_only boundary"):
        ci.startup_transient("hall_only", ok)
    with pytest.raises(ci.CathodeIntegrationError, match="duplicated"):
        ci.startup_transient("hall_only", _phases("hall_only", False) + (_phases("hall_only", False)[0],))
    with pytest.raises(ci.CathodeIntegrationError, match="no phases"):
        ci.startup_transient("hall_only", ())
    with pytest.raises(ci.CathodeIntegrationError, match="declares no loads"):
        ci.startup_transient("hall_only", (ci.StartupPhase("idle", S(1.0, "s"), {}),))


def _other_loads(arch):
    return {c: 1.0 for c in ci.boundary_components(arch) if c not in ci.CATHODE_BOUNDARY_COMPONENTS}


CATH = {"cathode_keeper": 6.0, "cathode_heater": 0.0}


def test_boundary_ledger_is_lazy_and_refuses_when_absent(monkeypatch):
    real = ci.importlib.import_module

    def missing(name, *a, **k):
        if name == ci.BOUNDARY_MODULE:
            raise ImportError("absent")
        return real(name, *a, **k)
    monkeypatch.setattr(ci.importlib, "import_module", missing)
    with pytest.raises(ci.CathodeIntegrationError, match="not present"):
        ci.to_boundary_ledger("hall_only", CATH, _other_loads("hall_only"), {})


def test_boundary_ledger_contract_checks_and_call(monkeypatch):
    fake = types.ModuleType(ci.BOUNDARY_MODULE)
    fake.BOUNDARY_VERSION = "bus_power_boundary_v0"
    fake.bus_power_ledger = lambda arch, loads, eff: {"arch": arch, "loads": loads, "eff": eff}
    monkeypatch.setitem(sys.modules, ci.BOUNDARY_MODULE, fake)
    with pytest.raises(ci.CathodeIntegrationError, match="expected 'bus_power_boundary_v1'"):
        ci.to_boundary_ledger("hall_only", CATH, _other_loads("hall_only"), {})
    fake.BOUNDARY_VERSION = ci.BOUNDARY_VERSION
    out = ci.to_boundary_ledger("ecr_hall", CATH, _other_loads("ecr_hall"), {"cathode_keeper": 0.9})
    assert out["arch"] == "ecr_hall" and set(out["loads"]) == set(ci.boundary_components("ecr_hall"))
    assert out["loads"]["cathode_keeper"] == 6.0
    fake.ledger = lambda arch, loads, eff: "contract-name ledger preferred"
    assert ci.to_boundary_ledger("hall_only", CATH, _other_loads("hall_only"), {}) == "contract-name ledger preferred"
    with pytest.raises(ci.CathodeIntegrationError, match="exactly"):
        ci.to_boundary_ledger("hall_only", {"cathode_keeper": 1.0}, _other_loads("hall_only"), {})
    with pytest.raises(ci.CathodeIntegrationError, match="double booking"):
        ci.to_boundary_ledger("hall_only", CATH, {**_other_loads("hall_only"), "cathode_heater": 1.0}, {})
    with pytest.raises(ci.CathodeIntegrationError, match="outside the hall_only boundary"):
        ci.to_boundary_ledger("hall_only", CATH, {**_other_loads("hall_only"), "rf_source": 1.0}, {})
    with pytest.raises(ci.CathodeIntegrationError, match="missing"):
        ci.to_boundary_ledger("rf_hall", CATH, _other_loads("hall_only"), {})
    del fake.ledger, fake.bus_power_ledger
    with pytest.raises(ci.CathodeIntegrationError, match="none of the ledger functions"):
        ci.to_boundary_ledger("hall_only", CATH, _other_loads("hall_only"), {})


def test_cathode_dossier_is_resolved_lazily(tmp_path):
    with pytest.raises(ci.CathodeIntegrationError, match="not present"):
        ci.cathode_dossier_path(str(tmp_path))
    (tmp_path / "docs" / "evidence" / "cathode").mkdir(parents=True)
    assert ci.cathode_dossier_path(str(tmp_path)).endswith(os.path.join("docs", "evidence", "cathode"))


# ------------------------------------------------------------------------------------------------ purity / contract

def test_import_does_not_pull_other_lanes_or_hall_modules():
    code = ("import sys, abep_sim.cathode_integration; "
            "print(int('abep_sim.arch_boundary' in sys.modules), int('abep_sim.hall_ensemble' in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["0", "0"]


def test_not_wired_into_archengine():
    with open(os.path.join(REPO, "abep_sim", "archengine.py")) as fh:
        assert "cathode_integration" not in fh.read()


def test_no_hidden_numeric_defaults():
    allowed = {"path", "repo_root", "index"}
    for name, fn in inspect.getmembers(ci, inspect.isfunction):
        if fn.__module__ != ci.__name__ or name.startswith("_"):     # private range helpers: None = unbounded
            continue
        for p in inspect.signature(fn).parameters.values():
            if p.default is not inspect.Parameter.empty:
                assert p.name in allowed and p.default is None, f"{name}({p.name}={p.default!r})"
    for cls in (ci.Sourced, ci.DischargeOperatingPoint, ci.InterstageCircuit, ci.KeeperState, ci.CathodeFlowSpec,
                ci.MissionUsage, ci.EmitterSpec, ci.StartupPhase, ci.CurrentEnvelopeInputs, ci.PoisoningInputs,
                ci.CathodeIntegrationInputs):
        for f in dataclasses.fields(cls):
            assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING, \
                f"{cls.__name__}.{f.name} has a default"


def test_contract_names():
    assert ci.ARCHITECTURES == ("hall_only", "rf_hall", "ecr_hall")
    assert ci.BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert ci.CATHODE_BOUNDARY_COMPONENTS == ("cathode_keeper", "cathode_heater")
    assert set(ci.boundary_components("hall_only")) == {"hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater",
                                                        "flow_control", "compressor", "thermal_control", "housekeeping"}
    assert set(ci.boundary_components("rf_hall")) - set(ci.boundary_components("hall_only")) == {"rf_source"}
    assert set(ci.boundary_components("ecr_hall")) - set(ci.boundary_components("hall_only")) == {"ecr_source", "ecr_magnet"}


# ------------------------------------------------------------------------------------------------ sourced data file

def test_data_file_is_valid_and_sourced(data):
    assert ci.validate_data(data) == []
    srcs = data["sources"]
    for pid, p in data["parameters"].items():
        s = srcs[p["source_id"]]
        assert s["access"] in ("open_full_text", "repo_frozen", "lane_derivation"), pid
        if s["access"] == "open_full_text":
            assert len(s["sha256"]) == 64 and s["url"].startswith("https://")
        assert p["locator"].strip() and p["transformation_chain"].strip()
    for sid, s in srcs.items():
        if s["access"] in ("not_accessed", "metadata_only"):
            assert s.get("used_for_values") is False, sid


def test_data_file_refuses_values_from_unread_sources(data):
    d = copy.deepcopy(data)
    d["parameters"]["xe_mg_s_per_sccm"]["source_id"] = "lafferty_1951"
    assert any("not read" in e for e in ci.validate_data(d))
    d = copy.deepcopy(data)
    d["parameters"]["xe_mg_s_per_sccm"]["value"] = "about 0.1"
    assert any("TBD" in e for e in ci.validate_data(d))
    d = copy.deepcopy(data)
    d["proposed_thresholds"]["life_margin_min"]["status"] = "FINAL"
    assert any("PROPOSED" in e for e in ci.validate_data(d))
    d = copy.deepcopy(data)
    d["parameters"]["poisoning_flux_equivalence_T_ref_K"]["quantity_type"] = "measured"
    assert any("lane value" in e for e in ci.validate_data(d))
    d = copy.deepcopy(data)
    d["relations"]["richardson_dushman"]["function"] = "does_not_exist"
    assert any("not defined" in e for e in ci.validate_data(d))


def test_data_file_rfp_matches_repo_constants(data):
    r = data["rfp"]
    assert r["firing_h_min"]["value"] == RFP.ignition_hours
    assert r["mission_h"]["value"] == RFP.mission_hours
    assert r["mass_max_kg"]["value"] == RFP.mass_max_kg
    assert r["power_max_W"]["value"] == RFP.power_max_W
    assert (r["thrust_min_mN"]["value"], r["thrust_max_mN"]["value"]) == (RFP.thrust_min_mN, RFP.thrust_max_mN)
    assert r["altitude_km"]["value"] == [RFP.alt_min_km, RFP.alt_max_km]


def test_data_file_consistency_checks(data):
    # the Lafferty constants reproduce the source statement 'over 10 A/cm2 at 1650 C'
    T = ci.parameter_value(data, "lab6_10Acm2_temperature_statement_C") + 273.15
    assert ci.richardson_current_density_A_cm2(T, 29.0, ci.parameter_value(data, "lab6_work_function_lafferty_iepc2017"),
                                               0.0) > 10.0
    # both work-function readings of Lafferty are carried, and differ by the recorded 0.01 eV
    assert ci.parameter_value(data, "lab6_work_function_lafferty_iepc2017") - \
        ci.parameter_value(data, "lab6_work_function_lafferty_gk") == pytest.approx(0.01)
    with pytest.raises(ci.CathodeIntegrationError):
        ci.parameter_sourced(data, "lab6_evaporation_B_lafferty", "digitized")   # evidence class must match the record


def test_derived_file_reproduces(data):
    sys.path.insert(0, LANE)
    try:
        import derive_cathode_integration_v1 as der
    finally:
        sys.path.remove(LANE)
    with open(os.path.join(LANE, "cathode_integration_derived_v1.json")) as fh:
        committed = fh.read()
    assert der.dumps(der.build()) == committed
    d = json.loads(committed)
    x = d["xe_mass_vs_rfp"]
    assert x["flow_consuming_whole_mass_limit_mg_s"] == pytest.approx(40e6 / (15000 * 3600))
    p5 = [r for r in x["reference_flows"] if r["parameter"] == "p5_cathode_xe_flow_mg_s"][0]
    assert p5["xe_kg_over_min_firing"] == pytest.approx(23.76)
    assert d["emitter_relations"]["consistency_check"]["consistent_with_over_10_A_cm2"] is True
