"""RF map: interpolation inside the domain only; OUT_OF_DOMAIN on every axis; score-bearing needs ADMITTED."""
import json
import os
from dataclasses import replace

import pytest

from abep_sim import rf_registry as reg
from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import TBD
from abep_sim.propulsion_modes import Mode
from abep_sim.rf_branch import ADMITTED_RF_MAP, ScoreBearingError, evaluate
from abep_sim.rf_map import RFMap, RFMapError
from tests import parallel_fixtures as F

ROOT = os.path.join(os.path.dirname(__file__), "..")
MAP_SCHEMA = json.load(open(os.path.join(ROOT, "schemas/parallel_architecture/rf_map_v1.schema.json")))


def cfg(B0=0.04):
    c = F.rf_config()
    return replace(c, nozzle=replace(c.nozzle, B0_T=F.q(B0, "T")))


def admitted_map(tmp_path, **kw):
    root = str(tmp_path)
    F.synthetic_rf_map(os.path.join(root, "map.json"), **kw)
    rd = os.path.join(root, "registry")
    sha = reg.register(rd, root, "map.json")["map_sha256"]
    json.dump({"decided_by": "owner", "admits_rf_map_sha256": sha}, open(os.path.join(root, "dec.json"), "w"))
    reg.admit(rd, root, sha, "dec.json")
    return RFMap(os.path.join(root, "map.json"), rd)


def test_schema_and_interpolation_inside_domain(tmp_path):
    m = admitted_map(tmp_path)
    validate_against_schema(m.doc, MAP_SCHEMA)
    r = evaluate(F.air(1.5e-6), Mode.RF_ATM, 600.0, cfg(0.04), source=ADMITTED_RF_MAP, rf_map=m, score_bearing=True)
    assert r.status.value == "PASS" and r.score_bearing is True
    assert r.thrust_axial_N == pytest.approx(1e-6 * 600 * 1.5 * 1.04)          # exact for a multilinear field
    assert r.P_bus_W == pytest.approx(610.0)


@pytest.mark.parametrize("feed,P,B0,why", [
    (lambda: F.air(2.5e-6), 600.0, 0.04, "mdot"),
    (lambda: F.air(1.5e-6), 900.0, 0.04, "P_dc"),
    (lambda: F.air(1.5e-6), 600.0, 0.10, "B0"),
    (lambda: F.xe(1.5e-6), 600.0, 0.04, "family"),
])
def test_out_of_domain_every_axis(tmp_path, feed, P, B0, why):
    m = admitted_map(tmp_path)
    r = evaluate(feed(), Mode.RF_XE if why == "family" else Mode.RF_ATM, P, cfg(B0), source=ADMITTED_RF_MAP, rf_map=m)
    assert r.status.value == "OUT_OF_DOMAIN" and isinstance(r.thrust_axial_N, TBD)


def test_composition_and_pressure_domain(tmp_path):
    m = admitted_map(tmp_path)
    from abep_sim.parallel_contracts import FeedState
    rich_n = FeedState(1.5e-6, 0.3, 300.0, {"O": 0.0, "O2": 0.0, "N2": 0.7, "N": 0.3, "Xe": 0.0}, "t", "assumed",
                       "u", "a", "v")
    assert evaluate(rich_n, Mode.RF_ATM, 600.0, cfg(), source=ADMITTED_RF_MAP, rf_map=m).status.value == "OUT_OF_DOMAIN"
    hi_p = replace(F.air(1.5e-6), pressure_Pa=5.0)
    assert evaluate(hi_p, Mode.RF_ATM, 600.0, cfg(), source=ADMITTED_RF_MAP, rf_map=m).status.value == "OUT_OF_DOMAIN"


def test_unmeasured_corner_is_out_of_domain(tmp_path):
    m = admitted_map(tmp_path, hole=3)
    r = evaluate(F.air(1.5e-6), Mode.RF_ATM, 600.0, cfg(), source=ADMITTED_RF_MAP, rf_map=m)
    assert r.status.value == "OUT_OF_DOMAIN"


def test_not_admitted_cannot_be_score_bearing(tmp_path):
    root = str(tmp_path)
    F.synthetic_rf_map(os.path.join(root, "map.json"))
    rd = os.path.join(root, "registry")
    reg.register(rd, root, "map.json")
    m = RFMap(os.path.join(root, "map.json"), rd)
    with pytest.raises(ScoreBearingError):
        evaluate(F.air(1.5e-6), Mode.RF_ATM, 600.0, cfg(), source=ADMITTED_RF_MAP, rf_map=m, score_bearing=True)
    r = evaluate(F.air(1.5e-6), Mode.RF_ATM, 600.0, cfg(), source=ADMITTED_RF_MAP, rf_map=m)
    assert r.score_bearing is False and "REGISTERED_NOT_ADMITTED" in r.validation_status


def test_hardware_mismatch_and_bad_document(tmp_path):
    m = admitted_map(tmp_path)
    c = F.rf_config()
    other = replace(c, nozzle=replace(c.nozzle, B0_T=F.q(0.04, "T"), magnetic_geometry_id="other-magnet"))
    assert evaluate(F.air(1.5e-6), Mode.RF_ATM, 600.0, other, source=ADMITTED_RF_MAP,
                    rf_map=m).status.value == "OUT_OF_DOMAIN"
    p = os.path.join(str(tmp_path), "bad.json")
    F.synthetic_rf_map(p)
    d = json.load(open(p)); d["domain"]["P_dc_W"] = [100.0, 800.0]; json.dump(d, open(p, "w"))
    with pytest.raises(RFMapError, match="beyond the measured grid"):
        RFMap(p)
