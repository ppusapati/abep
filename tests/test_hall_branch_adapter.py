"""Hall adapter: no physics duplicated; unadmitted/screening closures refused; HALL_ATM vs HALL_XE; score rules."""
import json
import os

import pytest

from abep_sim.hall_branch_adapter import (POINT_EVIDENCE, TRANSPORT_CLOSURE, HallEvidenceError, evaluate)
from abep_sim.hall_ensemble import load_ensemble, member_ids, screening_ids
from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import TBD
from abep_sim.propulsion_modes import IllegalModeError, Mode
from tests import parallel_fixtures as F

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                     "schemas/parallel_architecture/branch_result_v1.schema.json")))


def ev(feed, mode, **kw):
    kw.setdefault("source", POINT_EVIDENCE)
    return evaluate(feed, mode, 1e-8, 250.0, 250.0, F.hall_config(), **kw)


def test_unadmitted_and_screening_closures_refused_in_every_use():
    ens = load_ensemble()
    assert member_ids(ens) == set()                       # credible set is empty (frozen project state)
    sid = sorted(screening_ids(ens))[0]
    for sb in (False, True):
        with pytest.raises(HallEvidenceError, match="SCREENING"):
            ev(F.air(1e-6), Mode.HALL_ATM, source=TRANSPORT_CLOSURE, member_id=sid, score_bearing=sb)
    with pytest.raises(HallEvidenceError, match="not an admitted"):
        ev(F.xe(1e-6), Mode.HALL_XE, source=TRANSPORT_CLOSURE, member_id="made-up-closure", score_bearing=True)


def test_hall_xe_point_evidence_analog_not_score_bearing():
    r = ev(F.xe(1e-6), Mode.HALL_XE, points=(F.hall_point(),))
    validate_against_schema(r.to_dict(), SCHEMA)
    assert r.status.value == "PASS" and r.thrust_axial_N == pytest.approx(0.015)
    assert r.validation_status == "ANALOG_NOT_SCORE_BEARING" and r.score_bearing is False
    assert r.mdot_xe_kg_s == 1e-6 and r.mdot_atm_kg_s == 0.0 and r.mdot_cathode_xe_kg_s == 1e-8
    assert r.P_bus_W == pytest.approx(250 / 0.93 + 20 / 0.8 + 10 / 0.8)
    with pytest.raises(HallEvidenceError, match="analog"):
        ev(F.xe(1e-6), Mode.HALL_XE, points=(F.hall_point(),), score_bearing=True)


def test_out_of_domain_no_interpolation():
    r = ev(F.xe(1.5e-6), Mode.HALL_XE, points=(F.hall_point(),))
    assert r.status.value == "OUT_OF_DOMAIN" and isinstance(r.thrust_axial_N, TBD)


def test_atm_and_xe_distinct():
    with pytest.raises(IllegalModeError):
        ev(F.air(1e-6), Mode.HALL_XE, points=(F.hall_point(),))
    with pytest.raises(IllegalModeError):
        ev(F.xe(1e-6), Mode.HALL_ATM, points=(F.hall_point(),))
    r = ev(F.air(1e-6), Mode.HALL_ATM, points=(F.hall_point(),))       # an Xe point never covers an air feed
    assert r.status.value == "OUT_OF_DOMAIN"
    with pytest.raises(IllegalModeError, match="cathode"):
        evaluate(F.xe(1e-6), Mode.HALL_XE, 0.0, 250.0, 250.0, F.hall_config(), source=POINT_EVIDENCE,
                 points=(F.hall_point(),))


def test_vyovrinda_point_score_bearing_only_with_owner_admission(tmp_path):
    p = F.hall_point(hardware="vyovrinda:H-1")
    with pytest.raises(HallEvidenceError, match="not admitted"):
        ev(F.xe(1e-6), Mode.HALL_XE, points=(p,), score_bearing=True)
    json.dump({"decided_by": "owner", "admits_hall_evidence_sha256": p.canonical_sha256()},
              open(tmp_path / "adm.json", "w"))
    r = ev(F.xe(1e-6), Mode.HALL_XE, points=(p,), score_bearing=True, admission_file="adm.json", root=str(tmp_path))
    assert r.score_bearing is True and r.validation_status == "ADMITTED_VYOVRINDA_EVIDENCE"


def test_overlapping_points_refused():
    a, b = F.hall_point(), F.hall_point()
    with pytest.raises(HallEvidenceError, match="ambiguous"):
        ev(F.xe(1e-6), Mode.HALL_XE, points=(a, b))


def test_point_supplies_its_own_performance_numbers():
    lo = evaluate(F.xe(0.9e-6), Mode.HALL_XE, 1e-8, 240.0, 250.0, F.hall_config(), source=POINT_EVIDENCE,
                  points=(F.hall_point(),))
    hi = evaluate(F.xe(1.1e-6), Mode.HALL_XE, 1e-8, 260.0, 250.0, F.hall_config(), source=POINT_EVIDENCE,
                  points=(F.hall_point(),))
    assert lo.Isp_s == hi.Isp_s and lo.P_bus_W == hi.P_bus_W          # no hold-against-query distortion
    assert hi.provenance["query_offset_from_point"]["P_discharge_rel"] == pytest.approx(0.04)


def test_admission_recorded_and_confined(tmp_path):
    p = F.hall_point(hardware="vyovrinda:H-1")
    json.dump({"decided_by": "owner", "admits_hall_evidence_sha256": p.canonical_sha256()},
              open(tmp_path / "adm.json", "w"))
    r = ev(F.xe(1e-6), Mode.HALL_XE, points=(p,), score_bearing=True, admission_file="adm.json", root=str(tmp_path))
    adm = r.provenance["admission"]
    assert adm["decision_file"] == "adm.json" and len(adm["decision_sha256"]) == 64
    sub = tmp_path / "sub"; sub.mkdir()
    with pytest.raises(HallEvidenceError, match="outside"):
        ev(F.xe(1e-6), Mode.HALL_XE, points=(p,), admission_file="../adm.json", root=str(sub))


def test_out_of_domain_consistent_and_heat_tbd():
    r = ev(F.xe(1.5e-6), Mode.HALL_XE, points=(F.hall_point(),), score_bearing=True)
    assert r.status.value == "OUT_OF_DOMAIN" and r.score_bearing is False
    r = ev(F.xe(1e-6), Mode.HALL_XE, points=(F.hall_point(),))
    assert isinstance(r.heat_loads_W["discharge_heat_W"], TBD)
