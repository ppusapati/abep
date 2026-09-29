"""Parallel evaluator: RF-only, Hall-only, RF+Hall; vector combination; conservation; verdict discipline."""
import pytest

from abep_sim.hall_branch_adapter import POINT_EVIDENCE
from abep_sim.parallel_contracts import TBD, investigation_constraints
from abep_sim.parallel_system import HallCommand, RFCommand, evaluate
from abep_sim.propellant_router import FlowRequest
from abep_sim.propulsion_modes import InstalledArchitecture, Mode
from tests import parallel_fixtures as F

C = investigation_constraints(tuple(Mode))
PAR = InstalledArchitecture("rf_hall_parallel", True)
RFO = InstalledArchitecture("rf_only", False)
HO = InstalledArchitecture("hall_only", True)


def req(**kw):
    d = dict(rf_atm=0.0, rf_xe=0.0, hall_atm=0.0, hall_xe=0.0, cathode_xe=0.0)
    d.update(kw)
    return FlowRequest(**d)


def hall_cmd(P=250.0):
    return HallCommand(P, 250.0, F.hall_config(), POINT_EVIDENCE, points=(F.hall_point(),))


def test_rf_only_point():
    o = evaluate(RFO, Mode.RF_ATM, atm_feed=F.air(1.5e-6), xe_supply=None, request=req(rf_atm=1.5e-6),
                 rf=RFCommand(700.0, F.rf_config()), hall=None, common=F.common_state(xe_installed=False), constraints=C,
                 required_thrust_N=0.012)
    assert o["status"] == "PASS" and o["T_H_N"] == 0.0
    assert o["T_total_axial_N"] == pytest.approx(o["T_RF_N"])
    assert o["P_total_bus_W"] == pytest.approx(700.0 + (150 + 5 + 20 + 25) / 0.9)
    assert abs(o["power_balance_residual_W"]) < 1e-9
    assert o["verdict"] in ("UNRESOLVED", "INFEASIBLE") and o["verdict"] != "FEASIBLE"   # reduced model only


def test_hall_only_point():
    o = evaluate(HO, Mode.HALL_XE, atm_feed=None, xe_supply=F.XE_SUPPLY, request=req(hall_xe=1e-6, cathode_xe=1e-8),
                 rf=None, hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=0.012)
    assert o["status"] == "PASS" and o["T_RF_N"] == 0.0
    assert o["mdot_xe_total_kg_s"] == pytest.approx(1e-6 + 1e-8)
    assert o["verdict"] == "UNRESOLVED"                       # analog evidence is never decisive


def test_parallel_rf_atm_hall_xe_combines_vectors_and_books_cathode():
    o = evaluate(PAR, Mode.RF_ATM_HALL_XE, atm_feed=F.air(1.5e-6), xe_supply=F.XE_SUPPLY,
                 request=req(rf_atm=1.5e-6, hall_xe=1e-6, cathode_xe=1e-8), rf=RFCommand(700.0, F.rf_config()),
                 hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=0.012)
    assert o["T_total_axial_N"] == pytest.approx(o["T_RF_N"] + o["T_H_N"])
    assert o["mdot_atm_total_kg_s"] == 1.5e-6 and o["mdot_xe_total_kg_s"] == pytest.approx(1.01e-6)
    rf_bus, h_bus = o["P_RF_bus_W"], o["P_H_bus_W"]
    assert o["P_total_bus_W"] == pytest.approx(rf_bus + h_bus + o["P_common_bus_W"])


def test_power_hard_limit_reported_as_infeasible_power():
    o = evaluate(PAR, Mode.RF_ATM_HALL_XE, atm_feed=F.air(1.5e-6), xe_supply=F.XE_SUPPLY,
                 request=req(rf_atm=1.5e-6, hall_xe=1e-6, cathode_xe=1e-8), rf=RFCommand(1300.0, F.rf_config()),
                 hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=0.001)
    assert "INFEASIBLE_POWER" in o["statuses"] and o["verdict"] == "INFEASIBLE"


def test_flow_over_allocation_is_infeasible_flow():
    o = evaluate(PAR, Mode.RF_ATM_HALL_ATM, atm_feed=F.air(1.5e-6), xe_supply=F.XE_SUPPLY,
                 request=req(rf_atm=1.2e-6, hall_atm=0.5e-6, cathode_xe=1e-8), rf=RFCommand(700.0, F.rf_config()),
                 hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=0.012)
    assert o["status"] == "INFEASIBLE_FLOW" and o["verdict"] == "INFEASIBLE"


def test_out_of_domain_and_incomplete_are_not_converted():
    o = evaluate(HO, Mode.HALL_XE, atm_feed=None, xe_supply=F.XE_SUPPLY, request=req(hall_xe=1.5e-6, cathode_xe=1e-8),
                 rf=None, hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=0.012)
    assert o["status"] == "OUT_OF_DOMAIN" and o["verdict"] == "OUT_OF_DOMAIN"
    assert isinstance(o["T_total_axial_N"], TBD)
    cs = F.common_state(compressor=TBD("compressor", "C1 evidence"), xe_installed=False)
    o = evaluate(RFO, Mode.RF_ATM, atm_feed=F.air(1.5e-6), xe_supply=None, request=req(rf_atm=1.5e-6),
                 rf=RFCommand(700.0, F.rf_config()), hall=None, common=cs, constraints=C, required_thrust_N=0.001)
    assert o["status"] == "INCOMPLETE_EVIDENCE" and o["P_total_bus_W"] is None
    assert o["verdict"] == "INCOMPLETE_EVIDENCE"


def test_negative_thrust_request_refused_and_max_flagged():
    from abep_sim.parallel_contracts import ContractError
    with pytest.raises(ContractError):
        evaluate(HO, Mode.HALL_XE, atm_feed=None, xe_supply=F.XE_SUPPLY, request=req(hall_xe=1e-6, cathode_xe=1e-8),
                 rf=None, hall=hall_cmd(), common=F.common_state(), constraints=C, required_thrust_N=-1.0)
    big = F.hall_point(thrust=0.2)
    o = evaluate(HO, Mode.HALL_XE, atm_feed=None, xe_supply=F.XE_SUPPLY, request=req(hall_xe=1e-6, cathode_xe=1e-8),
                 rf=None, hall=HallCommand(250.0, 250.0, F.hall_config(), POINT_EVIDENCE, points=(big,)),
                 common=F.common_state(), constraints=C, required_thrust_N=0.012)
    assert o["flags"] and "OD1" in o["flags"][0]
