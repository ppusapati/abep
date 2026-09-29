"""Shared v2 test fixtures. Every value here is a TEST FIXTURE ('assumed', validation_status TEST_FIXTURE): chosen to
exercise code paths, never evidence about any RF or Hall hardware."""
from abep_sim import rf_reduced as R
from abep_sim.parallel_contracts import FeedState, Quantity, TBD, pure_xe_feed
from abep_sim.propellant_router import XeSupply
from abep_sim.rf_branch import RFBranchConfig


def q(v, unit):
    return Quantity(v, unit, "assumed", "test fixture", "n/a", "unit test only", "TEST_FIXTURE")


def air(mdot=1.5e-6):
    return FeedState(mdot, 0.3, 300.0, {"O": 0.3, "O2": 0.2, "N2": 0.5, "N": 0.0, "Xe": 0.0}, "test fixture",
                     "assumed", "n/a", "unit test only", "TEST_FIXTURE")


def xe(mdot=0.3e-6):
    return pure_xe_feed(mdot, pressure_Pa=0.1, temperature_K=300.0, source="test fixture", evidence_class_="assumed",
                        uncertainty="n/a", applicability_domain="unit test only", validation_status="TEST_FIXTURE")


XE_SUPPLY = XeSupply(max_flow_kg_s=2.0e-6, remaining_kg=5.0, pressure_Pa=2e5, temperature_K=293.0,
                     source="test fixture", evidence_class="assumed", uncertainty="n/a",
                     applicability_domain="unit test only", validation_status="TEST_FIXTURE")

CHAMBER = R.RFChamberSpec(q(3e-4, "m^3"), q(0.03, "m^2"), q(3e-3, "m^2"), q(500.0, "K"), q(0.4, "1"), q(0.3, "1"),
                          q(0.7, "1"), "test-chamber")
COUPLING = R.RFCoupling(q(13.56e6, "Hz"), q(0.85, "1"), q(0.8, "1"), TBD("eta_generator", "test"),
                        TBD("P_reflected_W", "test"), "test-antenna")


def nozzle(R_m=2.0):
    return R.RFNozzleSpec(q(1.2, "1"), q(R_m, "1"), q(0.05, "T"), "test-magnet", "test fixture",
                          R.REFERENCE_DETACHMENT, R.REFERENCE_DIVERGENCE)


def rf_config(R_m=2.0):
    return RFBranchConfig(CHAMBER, COUPLING, nozzle(R_m), q(0.0, "W"), q(1.0, "1"), (1.0, 0.0, 0.0),
                          TBD("startup_energy_J", "test"), TBD("startup_time_s", "test"))
