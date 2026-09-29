"""bus_power_boundary_v2: component coverage, conservation, inactive components, TBD handling, v1 untouched."""
import hashlib
import json
import os

import pytest

from abep_sim import arch_boundary
from abep_sim.bus_power_v2 import (COMMON, HALL, RF, REQUIRED_COMPONENTS, allocation_report, ledger)
from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import ContractError, Quantity, TBD
from abep_sim.propulsion_modes import ArchitectureKind, IllegalModeError, InstalledArchitecture, Mode, mode_spec

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEMA = json.load(open(os.path.join(ROOT, "schemas/parallel_architecture/bus_power_v2.schema.json")))
PAR = InstalledArchitecture("rf_hall_parallel", True)
RFO = InstalledArchitecture("rf_only", False)
HO = InstalledArchitecture("hall_only", True)


def point(arch, mode, active_load=10.0, eta=0.9):
    spec = mode_spec(mode)
    on = {"common": True, "rf": spec.rf_enabled, "hall": spec.hall_enabled}
    loads, effs = {}, {}
    for c in REQUIRED_COMPONENTS[arch.kind]:
        b = "common" if c in COMMON else ("rf" if c in RF else "hall")
        loads[c], effs[c] = (active_load, eta) if on[b] else (0.0, 1.0)
    if not arch.xe_system_installed:
        loads["xe_flow_control"], effs["xe_flow_control"] = 0.0, 1.0
    return loads, effs


def test_exact_component_universe():
    assert set(REQUIRED_COMPONENTS[ArchitectureKind.RF_HALL_PARALLEL]) == set(COMMON + RF + HALL) == {
        "compressor", "atmospheric_flow_control", "xe_flow_control", "thermal_control", "housekeeping",
        "rf_source", "rf_magnet", "hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater"}
    loads, effs = point(PAR, Mode.RF_ATM)
    loads.pop("rf_magnet")
    with pytest.raises(ContractError, match="missing"):
        ledger(PAR, Mode.RF_ATM, loads, effs)


@pytest.mark.parametrize("arch", [RFO, HO, PAR])
def test_conservation_every_mode(arch):
    for m in arch.allowed_modes():
        loads, effs = point(arch, m)
        r = ledger(arch, m, loads, effs)
        validate_against_schema(r, SCHEMA)
        expect = sum(loads[c] / effs[c] for c in loads)
        assert r["P_bus_W"] == pytest.approx(expect, rel=1e-14)
        assert abs(r["residual_W"]) <= 1e-12 * max(expect, 1)


def test_inactive_components_consume_nothing_hidden():
    loads, effs = point(PAR, Mode.RF_ATM)
    loads["hall_discharge"] = 5.0
    with pytest.raises(IllegalModeError, match="hidden power"):
        ledger(PAR, Mode.RF_ATM, loads, effs)
    loads, effs = point(PAR, Mode.HALL_XE)
    effs["rf_source"] = 0.5
    with pytest.raises(IllegalModeError):
        ledger(PAR, Mode.HALL_XE, loads, effs)


def test_tbd_makes_incomplete_not_zero():
    loads, effs = point(PAR, Mode.RF_ATM_HALL_XE)
    loads["compressor"] = TBD("compressor power", "C1 primary evidence / DI-1.4")
    r = ledger(PAR, Mode.RF_ATM_HALL_XE, loads, effs)
    validate_against_schema(r, SCHEMA)
    assert r["status"] == "INCOMPLETE_EVIDENCE" and r["P_bus_W"] is None
    assert r["missing_evidence"] == ["compressor"]
    assert r["P_bus_known_lower_bound_W"] > 0


def test_quantity_evidence_carried():
    loads, effs = point(RFO, Mode.RF_ATM)
    effs["rf_source"] = Quantity(0.7, "1", "assumed", "screening", "+-0.1", "13.56 MHz class", "UNVALIDATED")
    r = ledger(RFO, Mode.RF_ATM, loads, effs)
    it = next(i for i in r["items"] if i["component"] == "rf_source")
    assert it["efficiency_evidence"]["quantity_type"] == "assumed"


def test_bad_values_and_allocation_report():
    loads, effs = point(RFO, Mode.RF_ATM)
    effs["rf_source"] = 1.2
    with pytest.raises(ContractError):
        ledger(RFO, Mode.RF_ATM, loads, effs)
    loads, effs = point(PAR, Mode.RF_ATM_HALL_XE, active_load=100.0, eta=1.0)
    rep = allocation_report(ledger(PAR, Mode.RF_ATM_HALL_XE, loads, effs))
    assert rep["status"] == "PROPOSED_ENGINEERING_ALLOCATION"
    assert rep["total"]["P_bus_W"] == pytest.approx(1100.0)


def test_v1_boundary_untouched():
    assert arch_boundary.BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert arch_boundary.ARCHITECTURES == ("hall_only", "rf_hall", "ecr_hall")
    assert "rf_magnet" not in arch_boundary.ALL_COMPONENTS


def test_xe_flow_control_zero_without_xe_system():
    loads, effs = point(RFO, Mode.RF_ATM)
    loads["xe_flow_control"] = 50.0
    with pytest.raises(IllegalModeError, match="no Xe system"):
        ledger(RFO, Mode.RF_ATM, loads, effs)
