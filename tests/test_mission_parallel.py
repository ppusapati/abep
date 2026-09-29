"""Mission integration: complete mode history, Xe never increases, hours/starts explicit, time closure, coverage."""
import pytest

from abep_sim.hall_branch_adapter import POINT_EVIDENCE
from abep_sim.mission_parallel import MissionInputs, coverage, run
from abep_sim.mode_controller import Candidate
from abep_sim.parallel_contracts import TBD, investigation_constraints
from abep_sim.parallel_system import HallCommand, RFCommand
from abep_sim.propellant_router import FlowRequest
from abep_sim.propulsion_modes import InstalledArchitecture, Mode
from tests import parallel_fixtures as F

PAR = InstalledArchitecture("rf_hall_parallel", True)
C = investigation_constraints(tuple(Mode))
HALL = HallCommand(250.0, 250.0, F.hall_config(), POINT_EVIDENCE, points=(F.hall_point(),))
RF_ONLY = Candidate("rf", Mode.RF_ATM, FlowRequest(1.5e-6, 0, 0, 0, 0), rf=RFCommand(700.0, F.rf_config()))
BOOST = Candidate("boost", Mode.RF_ATM_HALL_XE, FlowRequest(1.5e-6, 0, 0, 1e-6, 1e-8),
                  rf=RFCommand(700.0, F.rf_config()), hall=HALL)


def inputs(policy, hall_start=F.q(3.6e-5, "kg")):
    return MissionInputs(
        spacecraft_mass_kg=F.q(150.0, "kg"), inclination_deg=F.q(96.0, "deg"), raan0_deg=F.q(0.0, "deg"),
        epoch_day=F.q(80.0, "day"), alt0_km=200.0,
        atmosphere_fn=lambda alt, t: {"rho": 3e-10},
        intake_fn=lambda atm: F.air(1.5e-6),
        drag_fn=lambda alt, t, atm: 0.010,
        required_thrust_fn=lambda D, alt, t: D,
        array_power_fn=lambda t, alt, beta, fe: 1600.0,
        spacecraft_bus_power_W=F.q(100.0, "W"), battery_capacity_J=F.q(3.6e6, "J"),
        battery_initial_J=F.q(3.6e6, "J"), policy_fn=policy, hall_start_xe_kg=hall_start,
        rf_start_xe_kg=TBD("rf start Xe", "n/a"), reentry_floor_km=150.0)


def alternating(state):
    return BOOST if int(state["t_s"] // 600) % 2 else RF_ONLY


def test_history_hours_starts_and_xe_monotone():
    r = run(PAR, inputs(alternating), xe_supply=F.XE_SUPPLY, xe_loaded_kg=F.q(5.0, "kg"), common=F.common_state(),
            constraints=C, duration_s=3600.0, dt_s=300.0)
    h = r["history"]
    assert r["completed"] and len(h) == 12
    assert sum(x["dt_s"] for x in h) == pytest.approx(3600.0) == r["mission_time_s"]
    xs = [x["xe_remaining_kg"] for x in h]
    assert all(b <= a for a, b in zip(xs, xs[1:]))                    # remaining Xe never increases
    assert r["starts"]["hall"] == 3 and r["starts"]["rf"] == 1        # explicit start counts
    assert r["hall_duty_fraction"] == pytest.approx(0.5)
    assert r["component_hours"]["rf_source"] == pytest.approx(1.0)
    assert r["component_hours"]["hall_discharge"] == pytest.approx(0.5)
    s = r["xe_mission"].summary(reserve=F.q(0.0, "1"), residual=F.q(0.0, "1"))
    assert s["mode_time_sum_s"] == pytest.approx(3600.0) and s["hall_starts"] == 3
    assert r["score_bearing"] is False and "hypothesis" in r["note"]
    for k in ("time", "alt_km", "rho_kg_m3", "composition", "drag_N", "available_atm_mdot_kg_s", "mode",
              "P_RF_bus_W", "P_H_bus_W", "P_common_bus_W", "P_total_bus_W", "T_RF_N", "T_H_N", "T_total_N",
              "xe_rate_kg_s", "xe_remaining_kg", "hall_starts", "rf_starts", "heat_loads_W", "power_margin_W"):
        assert k == "time" or k in h[0]


def test_tbd_start_mass_is_reported_not_zeroed():
    r = run(PAR, inputs(alternating, hall_start=TBD("hall start Xe", "C-1/H-1 measurement")),
            xe_supply=F.XE_SUPPLY, xe_loaded_kg=None, common=F.common_state(), constraints=C,
            duration_s=1800.0, dt_s=300.0)
    assert len(r["unbooked_start_events"]) == r["starts"]["hall"] > 0


def test_stop_on_unavailable_thrust():
    ood = Candidate("ood", Mode.RF_ATM_HALL_XE, FlowRequest(1.5e-6, 0, 0, 1.8e-6, 1e-8),
                    rf=RFCommand(700.0, F.rf_config()), hall=HALL)
    r = run(PAR, inputs(lambda s: ood), xe_supply=F.XE_SUPPLY, xe_loaded_kg=None, common=F.common_state(),
            constraints=C, duration_s=900.0, dt_s=300.0)
    assert not r["completed"] and "OUT_OF_DOMAIN" in r["stop"]["reason"]


def test_coverage_fractions():
    conds = [0.001, 0.005, 0.02]
    ev = lambda T: (lambda c: {"mode_feasible": T(c), "verdict": "UNRESOLVED"})
    cov = coverage(conds, ev(lambda c: c < 0.004), ev(lambda c: c < 0.01))
    assert cov["rf_alone_closes"] == pytest.approx(1 / 3) and cov["rf_plus_hall_closes"] == pytest.approx(1 / 3)
    assert cov["neither_closes"] == pytest.approx(1 / 3) and cov["closing_on_admitted_evidence"] == 0
