"""Mass BOM v2: installed mass independent of mode; partial refusal; screening labels; targets vs requirement."""
import json
import os

import pytest

from abep_sim import mass_bom
from abep_sim.mass_bom import validate_against_schema
from abep_sim.mass_bom_v2 import installed_items, loaded_xe_from_ledger, rollup
from abep_sim.parallel_contracts import ContractError, Quantity, investigation_constraints
from abep_sim.propulsion_modes import InstalledArchitecture, Mode

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                     "schemas/parallel_architecture/mass_bom_v2.schema.json")))
PAR = InstalledArchitecture("rf_hall_parallel", True)
C = investigation_constraints(tuple(Mode))


def screening(v):
    return Quantity(v, "kg", "assumed", "test fixture", "n/a", "unit test", "ASSUMED_SCREENING_VALUE (TEST_FIXTURE)")


def full_cbe(arch, v=1.0):
    return {it["id"]: screening(v) for it in installed_items(arch)}


def test_installed_sets_and_mode_independence():
    ids = {a: {it["id"] for it in installed_items(InstalledArchitecture(a, x))}
           for a, x in (("rf_only", False), ("hall_only", True), ("rf_hall_parallel", True))}
    assert "rf_generator" in ids["rf_only"] and "lab6_cathode" not in ids["rf_only"]
    assert "xe_tank" not in ids["rf_only"] and "xe_tank" in ids["hall_only"]
    assert ids["rf_hall_parallel"] == ids["rf_only"] | ids["hall_only"]
    import inspect
    assert "mode" not in inspect.signature(rollup).parameters          # installed mass has no mode input


def test_partial_refused_unless_allowed():
    with pytest.raises(ContractError, match="refused"):
        rollup(PAR, {}, system_margin_fraction=0.2)
    r = rollup(PAR, {"rf_generator": screening(2.0)}, system_margin_fraction=0.2, allow_partial=True)
    validate_against_schema(r, SCHEMA)
    assert r["complete"] is False and r["mev_kg"] is None and "NOT an architecture MEV" in r["note"]


def test_complete_rollup_and_checks():
    cbe = full_cbe(PAR, 1.0)
    r = rollup(PAR, cbe, system_margin_fraction=0.2, constraints=C)
    validate_against_schema(r, SCHEMA)
    n_dry = len([i for i in installed_items(PAR) if i["mass_class"] == "dry"])
    assert r["propellant_kg"] == 1.0 and r["mev_kg"] > r["dry_mev_kg"]
    assert r["checks"]["design_dry_target"]["target_kg"] == 28.0
    heavy = rollup(PAR, full_cbe(PAR, 5.0), system_margin_fraction=0.2, constraints=C)
    assert heavy["status"] == "INFEASIBLE_MASS"
    assert n_dry > 20


def test_unlabelled_assumption_refused_and_ledger_link():
    bad = Quantity(1.0, "kg", "assumed", "x", "u", "a", "UNVALIDATED")
    with pytest.raises(ContractError, match="ASSUMED_SCREENING_VALUE"):
        rollup(PAR, {"xe_tank": bad}, system_margin_fraction=0.2, allow_partial=True)
    assert loaded_xe_from_ledger({"xe_total_required_kg": None}, source="t").__class__.__name__ == "TBD"
    assert mass_bom.BOM_VERSION == "mass_bom_v1"
