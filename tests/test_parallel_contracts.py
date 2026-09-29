"""v2 core contracts: Quantity/TBD, FeedState, Status taxonomy, SystemConstraints, mode table, schemas."""
import json
import os

import pytest

from abep_sim.mass_bom import validate_against_schema
from abep_sim.parallel_contracts import (FRACTION_SUM_TOL, SPECIES, ContractError, FeedState, Limit, Quantity, Status,
                                         SystemConstraints, TBD, investigation_constraints, pure_xe_feed, value_of)
from abep_sim.propulsion_modes import (ArchitectureKind, IllegalModeError, InstalledArchitecture, MODE_TABLE, Mode,
                                       mode_spec)

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEMAS = os.path.join(ROOT, "schemas", "parallel_architecture")


def schema(name):
    return json.load(open(os.path.join(SCHEMAS, name + ".schema.json")))


def air(mdot=3.0e-6, **kw):
    fr = {"O": 0.3, "O2": 0.2, "N2": 0.5, "N": 0.0, "Xe": 0.0}
    fr.update(kw.pop("fractions", {}))
    args = dict(pressure_Pa=0.2, temperature_K=300.0, source="test fixture", evidence_class="assumed",
                uncertainty="test", applicability_domain="unit test", validation_status="TEST_FIXTURE")
    args.update(kw)
    return FeedState(mdot, args["pressure_Pa"], args["temperature_K"], fr, args["source"], args["evidence_class"],
                     args["uncertainty"], args["applicability_domain"], args["validation_status"])


def test_feedstate_valid_and_schema():
    f = air()
    assert abs(sum(f.species_mdot_kg_s().values()) - f.mdot_total_kg_s) < 1e-20
    validate_against_schema(f.to_dict(), schema("feed_state_v1"))
    with pytest.raises(TypeError):
        f.mass_fractions["O"] = 0.9            # immutable


def test_feedstate_rejects_hidden_default_composition():
    with pytest.raises(ContractError, match="no hidden default"):
        FeedState(1e-6, 0.1, 300, {"N2": 1.0}, "s", "assumed", "u", "a", "v")


def test_feedstate_rejects_negative_and_bad_sum():
    with pytest.raises(ContractError, match="negative"):
        air(fractions={"O": -0.1, "N2": 0.9, "O2": 0.2})
    with pytest.raises(ContractError, match="sum to"):
        air(fractions={"O": 0.3, "O2": 0.2, "N2": 0.4})
    air(fractions={"O": 0.3 + FRACTION_SUM_TOL / 2, "O2": 0.2, "N2": 0.5})     # inside the explicit tolerance
    with pytest.raises(ContractError):
        air(mdot=-1e-9)
    with pytest.raises(ContractError):
        air(evidence_class="guess")


def test_pure_xe_feed_is_explicit():
    x = pure_xe_feed(1e-7, pressure_Pa=2e5, temperature_K=293, source="s", evidence_class_="assumed",
                     uncertainty="u", applicability_domain="a", validation_status="v")
    assert x.is_pure_xe() and not x.has_atmospheric()
    assert set(x.mass_fractions) == set(SPECIES)


def test_quantity_and_tbd():
    q = Quantity(0.5, "1", "assumed", "src", "+-0.1", "domain", "UNVALIDATED")
    assert value_of(q, "q", "1") == 0.5
    with pytest.raises(ContractError, match="TBD"):
        value_of(TBD("S11", "RF coupling measurement"), "S11")
    with pytest.raises(ContractError):
        value_of(0.8, "bare float is not evidence")
    with pytest.raises(ContractError):
        Quantity(0.8, "1", "assumed", "", "u", "d", "v")


def test_status_taxonomy_distinct():
    assert Status.OUT_OF_DOMAIN != Status.FAIL_VALIDATION
    assert {s.value for s in Status} >= {"PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE",
                                          "INCOMPLETE_EVIDENCE", "INFEASIBLE_POWER", "INFEASIBLE_FLOW",
                                          "INFEASIBLE_THERMAL", "INFEASIBLE_MASS"}


def test_constraints_keep_rfp_and_allocations_distinct():
    c = investigation_constraints(tuple(Mode))
    assert c.power_hard_max_W.origin == "RFP_REQUIREMENT"
    assert c.power_design_max_W.origin == "PROPOSED_ENGINEERING_ALLOCATION"
    assert not c.power_hard_ok(1500.0) and c.power_hard_ok(1499.9)      # RFP '< 1.5 kW'
    assert "unverified" in c.firing_life_h.verification_status
    bad = Limit(1350.0, "W", "max", "PROPOSED_ENGINEERING_ALLOCATION", "s", "v")
    with pytest.raises(ContractError):
        SystemConstraints(c.thrust_min_N, c.thrust_max_N, bad, c.power_design_max_W, c.mass_hard_max_kg,
                          c.mass_design_max_kg, c.firing_life_h, c.mission_life_h, (Mode.RF_ATM,))


def test_mode_table_exactly_seven_and_schema():
    assert [m.value for m in Mode] == ["OFF", "RF_ATM", "RF_XE", "HALL_ATM", "HALL_XE", "RF_ATM_HALL_ATM",
                                       "RF_ATM_HALL_XE"]
    for m, s in MODE_TABLE.items():
        validate_against_schema(s.to_dict(), schema("operating_mode_v1"))
        if s.hall_enabled:
            assert s.hall_cathode_required          # the Hall branch always books its Xe-fed cathode
    assert not mode_spec("RF_ATM").rf_xe_allowed
    assert not mode_spec("HALL_XE").hall_atm_allowed
    with pytest.raises(IllegalModeError):
        mode_spec("RF_HALL_AUTO_HYBRID")


def test_installed_architecture():
    rf = InstalledArchitecture(ArchitectureKind.RF_ONLY, xe_system_installed=False)
    assert Mode.RF_XE not in rf.allowed_modes() and Mode.RF_ATM in rf.allowed_modes()
    with pytest.raises(IllegalModeError):
        rf.check_mode(Mode.HALL_XE)
    with pytest.raises(ContractError):
        InstalledArchitecture("hall_only", xe_system_installed=False)
    with pytest.raises(ContractError):
        InstalledArchitecture("rf_hall", xe_system_installed=True)          # the v1 id is not a v2 architecture
    p = InstalledArchitecture("rf_hall_parallel", xe_system_installed=True)
    assert set(p.allowed_modes()) == set(Mode)
    for a in (rf, p, InstalledArchitecture("hall_only", True)):
        validate_against_schema(a.to_dict(), schema("architecture_v2"))
