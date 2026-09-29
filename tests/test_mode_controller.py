"""Mode controller: feasible set + reasons + Pareto; no automatic selection; preregistered policy only."""
import hashlib
import json

import pytest

from abep_sim.hall_branch_adapter import POINT_EVIDENCE
from abep_sim.mode_controller import (Candidate, PreregisteredPolicy, TOPOLOGY_STATUS, evaluate_candidates,
                                      proposed_topology)
from abep_sim.parallel_contracts import ContractError, investigation_constraints
from abep_sim.parallel_system import HallCommand, RFCommand
from abep_sim.propellant_router import FlowRequest
from abep_sim.propulsion_modes import InstalledArchitecture, Mode
from tests import parallel_fixtures as F

PAR = InstalledArchitecture("rf_hall_parallel", True)
C = investigation_constraints(tuple(Mode))


def fr(**kw):
    d = dict(rf_atm=0.0, rf_xe=0.0, hall_atm=0.0, hall_xe=0.0, cathode_xe=0.0)
    d.update(kw)
    return FlowRequest(**d)


def cands(P_rf=700.0):
    hall = HallCommand(250.0, 250.0, F.hall_config(), POINT_EVIDENCE, points=(F.hall_point(),))
    return [Candidate("rf", Mode.RF_ATM, fr(rf_atm=1.5e-6), rf=RFCommand(P_rf, F.rf_config())),
            Candidate("boost", Mode.RF_ATM_HALL_XE, fr(rf_atm=1.5e-6, hall_xe=1e-6, cathode_xe=1e-8),
                      rf=RFCommand(P_rf, F.rf_config()), hall=hall),
            Candidate("hall", Mode.HALL_XE, fr(hall_xe=1e-6, cathode_xe=1e-8), hall=hall)]


def run(req_T, **kw):
    args = dict(required_thrust_N=req_T, atm_feed=F.air(1.5e-6), xe_supply=F.XE_SUPPLY, common=F.common_state(),
                constraints=C, available_bus_W=1400.0, branch_available={"rf": True, "hall": True})
    args.update(kw)
    return evaluate_candidates(PAR, cands(), **args)


def test_feasible_set_pareto_and_no_selection():
    r = run(0.001)
    labels = {x["label"] for x in r["feasible"]}
    assert labels == {"rf", "boost", "hall"}
    assert r["selection"] is None and "NONE" in r["selection_rule"]
    assert set(r["pareto_labels"]) <= labels and r["pareto_labels"]
    for x in r["feasible"]:
        assert x["verdict"] == "UNRESOLVED"                 # non-admitted evidence: never FEASIBLE by itself


def test_reasons_power_and_availability():
    r = run(0.001, available_bus_W=500.0)
    reasons = {x["label"]: x for x in r["infeasible"]}
    assert "INFEASIBLE_POWER" in reasons["boost"]["statuses"]
    r2 = run(0.001, branch_available={"rf": True, "hall": False})
    assert {x["label"] for x in r2["infeasible"] if x["status"] == "COMPONENT_UNAVAILABLE"} == {"boost", "hall"}
    with pytest.raises(ContractError):
        run(0.001, branch_available={"rf": True})


def test_thrust_requirement_and_topology_report():
    r = run(0.012)
    assert all(x["label"] != "rf" for x in r["feasible"])   # RF fixture alone is below 12 mN
    t = proposed_topology(r)
    assert t["status"] == TOPOLOGY_STATUS and t["q1_rf_atm_satisfies_required_thrust"] is False


def test_policy_must_be_owner_preregistered(tmp_path):
    rule = tmp_path / "rule.txt"
    rule.write_text("choose the lowest P_bus feasible candidate")
    json.dump({"decided_by": "owner", "preregistered_mode_policy_sha256": "0" * 64}, open(tmp_path / "d.json", "w"))
    pol = PreregisteredPolicy("d.json", "rule.txt", lambda f: min(f, key=lambda x: x["P_total_bus_W"])["label"])
    with pytest.raises(ContractError):
        run(0.001, policy=pol, root=str(tmp_path))
    sha = hashlib.sha256(rule.read_bytes()).hexdigest()
    json.dump({"decided_by": "owner", "preregistered_mode_policy_sha256": sha}, open(tmp_path / "d.json", "w"))
    assert run(0.001, policy=pol, root=str(tmp_path))["selection"] in {"rf", "boost", "hall"}


def test_thermal_limits_unknown_key_and_tbd_heat():
    with pytest.raises(ContractError, match="unknown heat key"):
        run(0.001, thermal_limits_W={"hall:anything": 0.0})
    r = run(0.001, thermal_limits_W={"hall:discharge_heat_W": 1.0})
    hall_like = {x["label"]: x for x in r["infeasible"]}
    assert "INCOMPLETE_EVIDENCE" in hall_like["hall"]["statuses"]
