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


def synthetic_rf_map(path, *, family="atmospheric", hole=None):
    """A SYNTHETIC map (TEST_FIXTURE): thrust = 1e-6 * P_dc * (mdot/1e-6) * (1 + B0) on a 2x2x2 grid. Not evidence."""
    import itertools, json
    axes = {"mdot_kg_s": [1.0e-6, 2.0e-6], "P_dc_W": [400.0, 800.0], "B0_T": [0.02, 0.06]}
    pts = list(itertools.product(*axes.values()))
    T = [1e-6 * p * (m / 1e-6) * (1 + b) for m, p, b in pts]
    f = {"thrust_N": T, "P_bus_W": [p + 10.0 for _, p, _ in pts], "P_magnet_bus_W": [10.0] * 8,
         "P_forward_W": [0.9 * p for _, p, _ in pts], "P_reflected_W": [0.05 * p for _, p, _ in pts],
         "P_absorbed_W": [0.7 * p for _, p, _ in pts], "Te_eV": [5.0] * 8, "ne_m3": [1e17] * 8,
         "utilization": [0.3] * 8, "Isp_s": [1000.0] * 8, "plume_divergence_deg": [30.0] * 8,
         "stable": [1] * 8, "ignited": [1] * 8}
    if hole is not None:
        f["thrust_N"][hole] = None
    comp = ({"O": [0.0, 0.6], "O2": [0.0, 0.6], "N2": [0.0, 1.0], "N": [0.0, 0.2], "Xe": [0.0, 0.0]}
            if family == "atmospheric" else {"O": [0, 0], "O2": [0, 0], "N2": [0, 0], "N": [0, 0], "Xe": [1, 1]})
    doc = {"meta": {"schema": "rf_map_v1", "map_id": "synthetic-test-map", "propellant_family": family,
                    "frequency_Hz": 13.56e6, "magnetic_geometry_id": "test-magnet", "antenna_geometry_id": "test-antenna",
                    "facility": "none (synthetic)", "test_article": "none (synthetic)",
                    "measurement_method": "synthetic TEST_FIXTURE", "evidence_class": "assumed",
                    "applicability_domain": "unit tests only", "validation_status": "TEST_FIXTURE",
                    "source": "tests/parallel_fixtures.py", "created": "2026-09-29"},
           "axes": axes, "fields": f,
           "uncertainty_1sigma": {"thrust_N": [1e-5] * 8, "P_bus_W": [5.0] * 8},
           "domain": {"mdot_kg_s": [1.0e-6, 2.0e-6], "P_dc_W": [400.0, 800.0], "B0_T": [0.02, 0.06],
                      "pressure_Pa": [0.05, 1.0], "temperature_K": [250.0, 600.0], "composition_mass_fraction": comp}}
    with open(path, "w") as fh:
        json.dump(doc, fh)
    return path
