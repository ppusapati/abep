"""Xe mission ledger v2: causes, contiguity, remaining never increases, duty cycle from history, policies explicit."""
import json
import os

import pytest

from abep_sim import xe_ledger
from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import ContractError, TBD
from abep_sim.propulsion_modes import Mode
from abep_sim.xe_mission_v2 import XeMissionLedger
from tests.parallel_fixtures import q

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                     "schemas/parallel_architecture/xe_mission_v2.schema.json")))


def history(led):
    led.add_interval(0.0, 3600.0, Mode.RF_ATM, {})
    led.add_event(3600.0, "hall_startup", q(0.036e-3, "kg"))
    led.add_interval(3600.0, 600.0, Mode.RF_ATM_HALL_XE, {"hall_xe_anode": 1e-6, "hall_cathode": 1e-7})
    led.add_interval(4200.0, 1800.0, Mode.RF_ATM, {})


def test_causes_and_duty_cycle_from_history():
    led = XeMissionLedger(q(5.0, "kg"))
    history(led)
    s = led.summary(reserve=q(0.1, "1"), residual=q(0.02, "1"))
    validate_against_schema(s, SCHEMA)
    assert s["mission_time_s"] == s["mode_time_sum_s"] == 6000.0
    assert s["hall_time_fraction"] == pytest.approx(0.1)
    assert s["hall_starts"] == 1
    assert s["answers"]["xe_to_hall_anode_kg"] == pytest.approx(6e-4)
    assert s["answers"]["xe_to_cathode_kg"] == pytest.approx(6e-5)
    consumed = 6e-4 + 6e-5 + 0.036e-3
    assert s["xe_consumed_kg"] == pytest.approx(consumed)
    assert s["xe_total_required_kg"] == pytest.approx(consumed * 1.12)
    tr = [r for _, r in led.remaining_trace]
    assert all(b <= a for a, b in zip(tr, tr[1:]))                # remaining never increases


def test_incomplete_policy_and_mode_legality():
    led = XeMissionLedger(None)
    history(led)
    s = led.summary(reserve=TBD("reserve", "owner OD-XE-2"), residual=q(0.0, "kg"))
    assert s["status"] == "INCOMPLETE_EVIDENCE" and s["xe_total_required_kg"] is None
    with pytest.raises(ContractError):
        led.summary(reserve=0.1, residual=q(0.0, "kg"))            # bare number is not a policy
    with pytest.raises(ContractError, match="not possible"):
        XeMissionLedger(None).add_interval(0.0, 10.0, Mode.RF_ATM, {"hall_cathode": 1e-7})
    with pytest.raises(ContractError, match="contiguous"):
        l2 = XeMissionLedger(None)
        l2.add_interval(0.0, 10.0, Mode.OFF, {})
        l2.add_interval(20.0, 10.0, Mode.OFF, {})


def test_depletion_flagged_and_v1_untouched():
    led = XeMissionLedger(q(1e-4, "kg"))
    history(led)
    s = led.summary(reserve=q(0.0, "1"), residual=q(0.0, "1"))
    assert s["status"] == "INFEASIBLE_FLOW" and s["depleted_at_s"] is not None
    assert xe_ledger.LEDGER_VERSION == "xe_ledger_v1"


def test_review_fixes_policies_cathode_times():
    led = XeMissionLedger(q(1.0, "kg"))
    with pytest.raises(ContractError, match="cathode"):
        led.add_interval(0.0, 100.0, Mode.HALL_XE, {"hall_xe_anode": 1e-6})
    led.add_interval(0.0, 100.0, Mode.HALL_XE, {"hall_xe_anode": 9e-3, "hall_cathode": 1e-5})
    with pytest.raises(ContractError, match=">= 0"):
        led.summary(reserve=q(-0.5, "1"), residual=q(0.0, "1"))
    s = led.summary(reserve=q(0.3, "1"), residual=q(0.0, "1"))
    assert s["status"] == "INFEASIBLE_FLOW" and "required total" in s["infeasible_reason"]
    with pytest.raises(ContractError, match="event time"):
        led.add_event(1e9, "hall_startup", q(1e-5, "kg"))
    with pytest.raises(ContractError):
        XeMissionLedger(q(-3.0, "kg"))
