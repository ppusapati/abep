"""Reduced RF model: mass/energy balance, energy bound (MODEL_ERROR, never clipped), non-score-bearing, feeds."""
import pytest

from abep_sim import rf_reduced as R
from abep_sim.parallel_contracts import ContractError, TBD
from tests.parallel_fixtures import CHAMBER, COUPLING, air, nozzle, q, xe


def run(feed, R_m=2.0, P=700.0):
    return R.run(feed, P, CHAMBER, COUPLING, nozzle(R_m), q(0.0, "W"))


def test_atmospheric_point_balances_close_and_is_not_score_bearing():
    o = run(air())
    assert o["model_status"] == "PASS"
    assert abs(o["mass_balance_residual"]) < 1e-6
    assert abs(o["energy_balance_residual"]) < 1e-3
    assert o["score_bearing"] is False and o["validation_status"] == "UNVALIDATED_REDUCED_RF_MODEL"
    assert o["evidence_class"] == "model-derived"
    assert o["P_kinetic_W"] <= o["P_kinetic_max_W"]
    assert o["thrust_N"] <= o["thrust_bound_N"] * (1 + 1e-12)
    assert o["P_jet_W"] <= o["P_absorbed_W"]
    assert all(v >= 0 for v in o["power_partition_W"].values())      # no negative losses


def test_energy_bound_violation_is_model_error_not_clipped():
    o = run(air(), R_m=10.0)
    assert o["model_status"] == "MODEL_ERROR"
    assert isinstance(o["thrust_N"], TBD)
    assert o["P_kinetic_W"] > o["P_kinetic_max_W"]


def test_reflected_power_not_invented():
    o = run(air())
    assert isinstance(o["P_reflected_W"], TBD) and isinstance(o["P_forward_W"], TBD)


def test_reflected_power_consistency_check():
    bad = R.RFCoupling(q(13.56e6, "Hz"), q(0.85, "1"), q(0.8, "1"), q(0.9, "1"), q(200.0, "W"), "t")
    with pytest.raises(ContractError, match="inconsistent"):
        R.run(air(), 700.0, CHAMBER, bad, nozzle(), q(0.0, "W"))
    ok = R.RFCoupling(q(13.56e6, "Hz"), q(0.85, "1"), q(0.8, "1"), q(0.95, "1"), q(20.0, "W"), "t")
    o = R.run(air(), 700.0, CHAMBER, ok, nozzle(), q(0.0, "W"))
    assert o["P_forward_W"] == pytest.approx(665.0) and o["P_reflected_W"] == 20.0


def test_xe_feed_supported_and_burnout_reported():
    o = run(xe())
    assert o["model_status"] == "NOT_SUSTAINED" and "burnout" in o["reason"]
    o2 = run(xe(3e-6), P=150.0)
    assert o2["model_status"] in ("PASS", "MODEL_ERROR", "NOT_SUSTAINED")
    assert o2["mdot_in_kg_s"] == 3e-6


def test_no_hidden_coefficients():
    with pytest.raises(ContractError):
        R.run(air(), 700.0, CHAMBER, R.RFCoupling(q(1e7, "Hz"), TBD("eta", "x"), q(0.8, "1"), TBD("g", "x"),
                                                   TBD("r", "x"), "t"), nozzle(), q(0.0, "W"))
    with pytest.raises(ContractError):
        R.run(air(), 700.0, CHAMBER, COUPLING, nozzle(), 0.0)          # a bare float is not evidence


def test_coupling_record_interface():
    rec = R.RFCouplingRecord(13.56e6, "ant", "mag", 700.0, 650.0, 30.0, TBD("S11", "x"), 500.0, 60.0, 50.0,
                             TBD("Z", "x"), "external EM export (test)", "model-derived")
    assert rec.P_absorbed_W == 500.0
    with pytest.raises(ContractError, match="energy"):
        R.RFCouplingRecord(13.56e6, "ant", "mag", 700.0, 650.0, 30.0, TBD("S11", "x"), 600.0, 60.0, 50.0,
                           TBD("Z", "x"), "t", "model-derived")


def test_analytic_rm_star_and_tight_bound():
    assert R.R_m_star(1.2) == pytest.approx(4.214, abs=2e-3)
    assert R.R_m_star(5 / 3) == pytest.approx(3.95, abs=1e-2)
    rs = R.R_m_star(1.2)
    assert run(air(), R_m=rs * 0.999)["model_status"] == "PASS"
    o = run(air(), R_m=rs * 1.005)                         # a 0.5 % step past R_m* must already fail
    assert o["model_status"] == "MODEL_ERROR"


def test_jet_power_consistent_with_thrust():
    o = run(air())
    assert o["P_jet_W"] == pytest.approx(o["thrust_N"] ** 2 / (2 * o["mdot_ion_kg_s"]))
