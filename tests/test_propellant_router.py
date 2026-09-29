"""v2 propellant router: conservation, over-allocation, negative flow, mode legality, cathode booking."""
import pytest

from abep_sim.parallel_contracts import ContractError, InfeasibleError, Status
from abep_sim.propellant_router import FlowRequest, XeSupply, route
from abep_sim.propulsion_modes import IllegalModeError, InstalledArchitecture, Mode
from tests.test_parallel_contracts import air

XE = XeSupply(max_flow_kg_s=2.0e-6, remaining_kg=5.0, pressure_Pa=2e5, temperature_K=293.0, source="test",
              evidence_class="assumed", uncertainty="test", applicability_domain="unit test",
              validation_status="TEST_FIXTURE")
PAR = InstalledArchitecture("rf_hall_parallel", xe_system_installed=True)


def req(**kw):
    d = dict(rf_atm=0.0, rf_xe=0.0, hall_atm=0.0, hall_xe=0.0, cathode_xe=0.0)
    d.update(kw)
    return FlowRequest(**d)


def test_atmospheric_conservation_split():
    r = route(air(3.0e-6), XE, Mode.RF_ATM_HALL_ATM, req(rf_atm=2.0e-6, hall_atm=0.5e-6, cathode_xe=1e-7), PAR)
    assert r.rf_feed.mdot_total_kg_s + r.hall_feed.mdot_total_kg_s + r.unallocated_atm_kg_s == pytest.approx(3.0e-6,
                                                                                                           rel=1e-15)
    assert abs(r.atm_balance_residual_kg_s) < 1e-20
    assert dict(r.rf_feed.mass_fractions) == dict(air().mass_fractions)       # no implicit species separation


def test_xe_conservation_with_cathode_booked_separately():
    r = route(air(3.0e-6), XE, Mode.RF_ATM_HALL_XE, req(rf_atm=3.0e-6, hall_xe=1.0e-6, cathode_xe=1.0e-7), PAR)
    assert r.hall_feed.is_pure_xe()
    assert r.cathode_xe_kg_s == 1.0e-7
    assert r.hall_feed.mdot_total_kg_s + r.cathode_xe_kg_s + r.unallocated_xe_kg_s == pytest.approx(2.0e-6, rel=1e-15)
    assert r.unallocated_atm_kg_s == 0.0


def test_over_allocation_fails():
    with pytest.raises(InfeasibleError) as e:
        route(air(3.0e-6), XE, Mode.RF_ATM_HALL_ATM, req(rf_atm=2.5e-6, hall_atm=1.0e-6, cathode_xe=1e-7), PAR)
    assert e.value.status is Status.INFEASIBLE_FLOW
    with pytest.raises(InfeasibleError):
        route(air(3.0e-6), XE, Mode.HALL_XE, req(hall_xe=2.0e-6, cathode_xe=1e-7), PAR)
    empty = XeSupply(2e-6, 0.0, 2e5, 293, "t", "assumed", "u", "a", "v")
    with pytest.raises(InfeasibleError, match="exhausted"):
        route(None, empty, Mode.HALL_XE, req(hall_xe=1e-7, cathode_xe=1e-8), PAR)


def test_negative_flow_fails():
    with pytest.raises(ContractError):
        req(rf_atm=-1e-9)


def test_mode_legality():
    with pytest.raises(IllegalModeError):                     # RF_ATM cannot consume Xe
        route(air(), XE, Mode.RF_ATM, req(rf_atm=1e-6, rf_xe=1e-7), PAR)
    with pytest.raises(IllegalModeError):                     # HALL_XE cannot take an atmospheric anode flow
        route(air(), XE, Mode.HALL_XE, req(hall_atm=1e-6, hall_xe=1e-7, cathode_xe=1e-8), PAR)
    with pytest.raises(IllegalModeError, match="cathode"):    # RF_ATM_HALL_XE must book the cathode
        route(air(), XE, Mode.RF_ATM_HALL_XE, req(rf_atm=1e-6, hall_xe=1e-7), PAR)
    rf_only = InstalledArchitecture("rf_only", xe_system_installed=False)
    with pytest.raises(IllegalModeError):
        route(air(), None, Mode.RF_XE, req(rf_xe=1e-7), rf_only)


def test_no_xe_system_and_xe_in_atmospheric_feed():
    with pytest.raises(InfeasibleError):
        route(air(), None, Mode.HALL_XE, req(hall_xe=1e-7, cathode_xe=1e-8))
    with pytest.raises(ContractError, match="contains Xe"):
        route(air(fractions={"Xe": 0.1, "N2": 0.4}), XE, Mode.RF_ATM, req(rf_atm=1e-7))


def test_off_mode_routes_nothing():
    r = route(air(3e-6), XE, Mode.OFF, req(), PAR)
    assert r.rf_feed is None and r.hall_feed is None
    assert r.unallocated_atm_kg_s == 3e-6 and r.unallocated_xe_kg_s == 2e-6
