"""RF branch: BranchResult contract, reduced model never score-bearing, mode/feed legality."""
import json
import os

import pytest

from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import TBD
from abep_sim.propulsion_modes import IllegalModeError, Mode
from abep_sim.rf_branch import ScoreBearingError, evaluate
from tests.parallel_fixtures import air, rf_config, xe

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                     "schemas/parallel_architecture/branch_result_v1.schema.json")))


def test_rf_atm_branch_result():
    r = evaluate(air(), Mode.RF_ATM, 700.0, rf_config())
    validate_against_schema(r.to_dict(), SCHEMA)
    assert r.status.value == "PASS" and r.score_bearing is False
    assert r.thrust_axial_N > 0 and r.thrust_vector_N[1:] == (0.0, 0.0)
    assert r.P_bus_W == pytest.approx(700.0)
    assert r.mdot_xe_kg_s == 0.0 and r.mdot_cathode_xe_kg_s == 0.0
    assert isinstance(r.startup_energy_J, TBD)


def test_reduced_model_cannot_be_score_bearing():
    with pytest.raises(ScoreBearingError):
        evaluate(air(), Mode.RF_ATM, 700.0, rf_config(), score_bearing=True)


def test_feed_mode_legality():
    with pytest.raises(IllegalModeError):
        evaluate(xe(), Mode.RF_ATM, 700.0, rf_config())
    with pytest.raises(IllegalModeError):
        evaluate(air(), Mode.RF_XE, 700.0, rf_config())
    with pytest.raises(IllegalModeError):
        evaluate(air(), Mode.HALL_XE, 700.0, rf_config())


def test_model_error_propagates_as_tbd_thrust():
    r = evaluate(air(), Mode.RF_ATM, 700.0, rf_config(R_m=10.0))
    validate_against_schema(r.to_dict(), SCHEMA)
    assert r.status.value == "MODEL_ERROR" and isinstance(r.thrust_axial_N, TBD)
