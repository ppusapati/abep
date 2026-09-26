"""Tests for the architecture mass BOM skeleton v1 (abep_sim/mass_bom.py, section 'Architecture mass BOM skeleton').

All masses below are synthetic TEST FIXTURES used only to check arithmetic and refusal logic; they are not estimates of
any component and must never be quoted.
"""
import copy
import json
import math
from pathlib import Path

import pytest

from abep_sim import mass_bom as mb

ROOT = Path(__file__).resolve().parents[1]
FIX = "test fixture (synthetic, not a mass estimate)"


def _sourced(kg):
    return {"basis": "sourced_value", "value_kg": kg, "source": FIX, "evidence_class": "assumed",
            "uncertainty": "n/a (fixture)", "applicability": "unit test only"}


def _item(iid, kg=None, cat="ecss_d_new_or_major_modification", mass_class="dry", scope="common", cbe=None, lb=None):
    return {"id": iid, "name": iid, "scope": scope, "rfp_block": "test", "gate_element": "structure_test",
            "power_boundary_components": [], "mass_class": mass_class, "hall_related": False,
            "maturity": {"category": cat, "status": "PROPOSED", "rationale": "fixture"},
            "cbe": cbe if cbe is not None else (_sourced(kg) if kg is not None else {"basis": "TBD", "requires": "x"}),
            "lower_bound": lb or {"basis": "none", "requires": "fixture"}, "notes": ""}


def _frac(v):
    return {"value": v, "unit": "1", "source": FIX, "evidence_class": "assumed"}


def _filled(arch, kg=1.0):
    """Real catalog of `arch` with every TBD CBE replaced by a synthetic sourced value."""
    items = mb.architecture_items(arch)
    for it in items:
        if it["cbe"]["basis"] == "TBD":
            it["cbe"] = _sourced(kg)
    return items


# ------------------------------------------------------------------------------------------------ roll-up arithmetic
def test_rollup_arithmetic_and_mga_application():
    items = [_item("a", 10.0, "ecss_d_new_or_major_modification"),
             _item("b", 5.0, "ecss_c_minor_modification"),
             _item("c", 2.0, "ecss_ab_off_the_shelf"),
             _item("harness", cat="policy_allocation_nominal",
                   cbe={"basis": "scaling_relation", "relation": "fraction_of_nominal_dry", "fraction": _frac(0.05)}),
             _item("xe", 4.0, "propellant_not_equipment", mass_class="propellant"),
             _item("xe_res", cat="propellant_not_equipment", mass_class="propellant",
                   cbe={"basis": "scaling_relation", "relation": "fraction_of_item", "of_item": "xe",
                        "fraction": _frac(0.02)})]
    r = mb.rollup(items, system_margin_fraction=0.2)
    assert r["complete"] and r["n_missing"] == 0
    nom_other = 10 * 1.20 + 5 * 1.10 + 2 * 1.05
    harness = 0.05 / 0.95 * nom_other
    nom_dry = nom_other + harness
    lines = {ln["id"]: ln for ln in r["lines"]}
    assert lines["a"]["mga"] == 0.20 and lines["b"]["mga"] == 0.10 and lines["c"]["mga"] == 0.05
    assert math.isclose(lines["a"]["nominal_kg"], 12.0)
    assert math.isclose(lines["harness"]["cbe_kg"], harness)
    assert math.isclose(lines["harness"]["nominal_kg"] / nom_dry, 0.05)          # ESA R-M1-7 share
    assert math.isclose(lines["xe_res"]["cbe_kg"], 0.08)
    assert math.isclose(r["cbe_dry_kg"], 17.0 + harness)
    assert math.isclose(r["nominal_dry_kg"], nom_dry)
    assert math.isclose(r["mga_kg"], nom_dry - (17.0 + harness))
    assert math.isclose(r["system_margin_kg"], 0.2 * nom_dry)
    assert math.isclose(r["propellant_kg"], 4.08)
    assert math.isclose(r["mev_kg"], nom_dry * 1.2 + 4.08)                       # propellant: no MGA, no system margin
    r10 = mb.rollup(items, system_margin_fraction=0.2, g3_margin_floor=0.10)
    exp = 10 * 1.2 + 5 * 1.1 + 2 * 1.1 + harness * 1.1 + 4.08 * 1.1
    assert math.isclose(r10["g3_bounding_mass_kg"], exp)


def test_mga_table_is_esa_policy():
    cats = mb.MATURITY_CATEGORIES
    assert (cats["ecss_ab_off_the_shelf"]["mga"], cats["ecss_c_minor_modification"]["mga"],
            cats["ecss_d_new_or_major_modification"]["mga"]) == (0.05, 0.10, 0.20)
    for c in cats.values():
        assert c["source"] == "ESA_MARGIN_2012" and c["evidence_class"] in mb.EVIDENCE_CLASSES
    src = mb.MASS_BOM_SOURCES["ESA_MARGIN_2012"]
    assert src["url"].startswith("https://sci.esa.int/") and len(src["sha256_as_fetched"]) == 64
    assert mb.SYSTEM_MARGIN["status"] == "PROPOSED"


def test_system_margin_has_no_default_and_is_validated():
    items = [_item("a", 1.0)]
    with pytest.raises(TypeError):
        mb.rollup(items)                                                          # no hidden default
    for bad in (-0.1, 1.0, float("nan"), True):
        with pytest.raises(ValueError):
            mb.rollup(items, system_margin_fraction=bad)


def test_complete_rollup_on_real_catalog_with_fixture_values():
    for arch in mb.ARCHITECTURES:
        r = mb.rollup(_filled(arch), system_margin_fraction=0.2)
        assert r["complete"] and r["mev_kg"] > r["cbe_total_kg"]
        h = next(ln for ln in r["lines"] if ln["id"] == "harness")
        assert math.isclose(h["nominal_kg"] / r["nominal_dry_kg"], 0.05)


# ------------------------------------------------------------------------------------------------ refusal with TBD
def test_refusal_when_items_are_tbd():
    for arch in mb.ARCHITECTURES:
        items = mb.architecture_items(arch)
        with pytest.raises(ValueError, match="roll-up refused") as e:
            mb.rollup(items, system_margin_fraction=0.2)
        tbd = [it["id"] for it in items if it["cbe"]["basis"] == "TBD"]
        assert tbd and all(i in str(e.value) for i in tbd)
        p = mb.rollup(items, system_margin_fraction=0.2, allow_partial=True)
        assert p["complete"] is False and p["mev_kg"] is None
        missing = {m["id"] for m in p["missing_items"]}
        assert set(tbd) <= missing and {"xe_residual", "harness"} <= missing        # dependants are missing too
        assert "NOT an MEV" in p["partial_note"]


def test_single_tbd_or_tbd_maturity_refuses():
    items = _filled("hall_only")
    items[0]["cbe"] = {"basis": "TBD", "requires": "fixture"}
    with pytest.raises(ValueError, match=items[0]["id"]):
        mb.rollup(items, system_margin_fraction=0.2)
    items = _filled("hall_only")
    items[0]["maturity"]["category"] = "TBD"
    with pytest.raises(ValueError, match="maturity category TBD"):
        mb.rollup(items, system_margin_fraction=0.2)


def test_unsourced_values_are_rejected():
    it = _item("a", 1.0)
    del it["cbe"]["source"]
    with pytest.raises(ValueError):
        mb.check_item(it)
    it = _item("a", 1.0)
    it["cbe"]["evidence_class"] = "guess"
    with pytest.raises(ValueError):
        mb.check_item(it)
    it = _item("a", cbe={"basis": "scaling_relation", "relation": "fraction_of_nominal_dry",
                         "fraction": {"value": 0.05, "unit": "1"}})
    with pytest.raises(ValueError, match="missing 'source'"):
        mb.check_item(it)


def test_hall_closure_and_calibration_nuisance_are_rejected():
    it = _item("hall_thruster_head", 1.0)
    it["cbe"]["hall_closure_id"] = "sgb-screen-01"
    with pytest.raises(ValueError, match="Hall-closure"):
        mb.check_item(it)
    it = _item("hall_magnets", 1.0)
    it["cbe"]["depends_on_hall_closure"] = True
    with pytest.raises(ValueError, match="Hall-closure"):
        mb.check_item(it)
    it = _item("hall_magnets", 1.0)
    it["notes_inputs"] = {"coil_shape": "1.6 kW"}
    with pytest.raises(ValueError, match="calibration nuisance"):
        mb.check_item(it)


# ------------------------------------------------------------------------------------------------ architectures
def test_identical_common_items_across_architectures():
    per = {a: mb.architecture_items(a) for a in mb.ARCHITECTURES}
    common = [[it for it in per[a] if it["scope"] == "common"] for a in mb.ARCHITECTURES]
    assert common[0] == common[1] == common[2] and len(common[0]) > 0
    spec = {a: {it["id"] for it in per[a] if it["scope"] != "common"} for a in mb.ARCHITECTURES}
    assert spec == {"hall_only": set(), "rf_hall": {"rf_source", "rf_generator", "rf_matching_network"},
                    "ecr_hall": {"ecr_source", "microwave_source", "waveguide", "ecr_magnets"}}
    required_common = {"intake", "filter", "compressor", "atmospheric_gas_chamber", "atmospheric_valve",
                       "xe_valve_and_flow_control", "xe_tank", "xe_load", "hall_thruster_head", "hall_magnets",
                       "cathode", "ppu", "harness", "thermal_hardware", "structure"}
    assert required_common <= {it["id"] for it in common[0]}
    ids = [it["id"] for it in mb.bom_catalog()]
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError):
        mb.architecture_items("grids_only")
    # copies are independent: mutating one architecture's list never leaks into another
    per["rf_hall"][0]["name"] = "mutated"
    assert mb.architecture_items("hall_only")[0]["name"] != "mutated"


def test_hall_items_have_no_closure_derived_mass():
    for it in mb.bom_catalog():
        if it["hall_related"]:
            assert it["cbe"]["basis"] == "TBD" and "closure" in it["notes"]


# ------------------------------------------------------------------------------------------------ plausibility screen
def test_screen_on_committed_catalog_reports_unavailable_bounds():
    per = {a: mb.architecture_items(a) for a in mb.ARCHITECTURES}
    s = mb.plausibility_screen(per, threshold_kg=40.0, system_margin_fraction=0.2)
    assert s["any_architecture_excluded"] is False
    for r in s["architectures"].values():
        assert r["verdict"] == "LOWER_BOUNDS_UNAVAILABLE" and r["cbe_margin_free_lower_bound_kg"] == 0.0


def _lb(kg, basis="measurement_same_hardware"):
    return {"basis": "sourced_value", "value_kg": kg, "source": FIX, "evidence_class": "measured",
            "gate_basis": basis, "scope_justification": "fixture"}


def test_screen_verdicts_and_strict_threshold():
    def run(kgs, cat="ecss_d_new_or_major_modification", mass_class="dry"):
        items = [_item(f"i{k}", cat=cat, mass_class=mass_class, lb=_lb(v)) for k, v in enumerate(kgs)]
        return mb.plausibility_screen({"rf_hall": items}, threshold_kg=40.0,
                                      system_margin_fraction=0.2)["architectures"]["rf_hall"]
    at_limit = run([30.0, 10.0], cat="propellant_not_equipment", mass_class="propellant")
    assert at_limit["verdict"] == "NOT_EXCLUDED_FULL_COVERAGE"                    # equality decides nothing
    assert run([30.0, 10.0])["verdict"] == "EXCEEDS_LIMIT_MEV_ONLY"               # 40 x 1.2 x 1.2 > 40, margin-free = 40
    over = run([30.0, 10.5])
    assert over["verdict"] == "EXCEEDS_LIMIT_MARGIN_FREE" and over["g3_fail_evidence"]
    assert over["g3_flags"] == ["mass_margin_free_lower_bound"]
    mev_only = run([30.0])                                                        # 30 x 1.2 x 1.2 = 43.2 > 40
    assert math.isclose(mev_only["mev_lower_bound_kg"], 43.2)
    assert mev_only["verdict"] == "EXCEEDS_LIMIT_MEV_ONLY" and not mev_only["g3_fail_evidence"]
    items = [_item("a", lb=_lb(5.0)), _item("b")]
    r = mb.plausibility_screen({"hall_only": items}, threshold_kg=40.0, system_margin_fraction=0.2)
    assert r["architectures"]["hall_only"]["verdict"] == "NOT_EXCLUDED_PARTIAL_COVERAGE"
    assert r["architectures"]["hall_only"]["items_without_lower_bound"] == ["b"]


def test_thin_wall_sphere_bound():
    p, bf, s, rho, V = 1.0e7, 1.5, 9.0e8, 4.4e3, 0.01                            # fixture numbers
    r = (3 * V / (4 * math.pi)) ** (1 / 3)
    t = bf * p * r / (2 * s)
    assert math.isclose(mb.thin_wall_sphere_min_mass_kg(p, bf, s, rho, V), 4 * math.pi * r ** 2 * t * rho)
    with pytest.raises(ValueError):
        mb.thin_wall_sphere_min_mass_kg(p, 0.9, s, rho, V)
    q = lambda v, u: {"value": v, "unit": u, "source": FIX, "evidence_class": "assumed"}  # noqa: E731
    it = _item("xe_tank", lb={"basis": "thin_wall_sphere_membrane", "gate_basis": "hard_physical_bound",
                              "scope_justification": "fixture",
                              "inputs": {"p_meop_Pa": q(p, "Pa"), "burst_factor": q(bf, "1"),
                                         "sigma_ult_Pa": q(s, "Pa"), "rho_wall_kg_m3": q(rho, "kg/m3"),
                                         "volume_m3": q(V, "m3")}})
    res = mb.plausibility_screen({"hall_only": [it]}, threshold_kg=40.0, system_margin_fraction=0.2)
    lbv = res["architectures"]["hall_only"]["items_with_lower_bound"][0]["lower_bound_kg"]
    assert math.isclose(lbv, 1.5 * bf * p * V * rho / s)
    del it["lower_bound"]["inputs"]["volume_m3"]
    with pytest.raises(ValueError):
        mb.check_item(it)


# ------------------------------------------------------------------------------------------------ document + schema
def _schema():
    return json.loads((ROOT / mb.BOM_SCHEMA_PATH).read_text(encoding="utf-8"))


def test_committed_document_reproduces_and_validates():
    text = (ROOT / mb.BOM_DOC_PATH).read_text(encoding="utf-8")
    assert text == mb.document_text(), "run `python -m abep_sim.mass_bom build`"
    doc = json.loads(text)
    mb.validate_against_schema(doc, _schema())
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.validate(doc, _schema())
    for a in mb.ARCHITECTURES:
        assert doc["rollups"][a]["strict"]["status"] == "REFUSED"
    assert doc["milestones"]["supports"] == ["A"]


def test_schema_rejects_bad_documents():
    doc = mb.build_document()
    schema = _schema()
    bad = copy.deepcopy(doc)
    bad["items"][0]["cbe"] = {"basis": "sourced_value", "value_kg": 1.0}          # no source / evidence class
    with pytest.raises(ValueError):
        mb.validate_against_schema(bad, schema)
    bad = copy.deepcopy(doc)
    bad["plausibility_screen"]["architectures"]["hall_only"]["verdict"] = "WINNER"
    with pytest.raises(ValueError):
        mb.validate_against_schema(bad, schema)
    bad = copy.deepcopy(doc)
    bad["system_margin"]["status"] = "FINAL"
    with pytest.raises(ValueError):
        mb.validate_against_schema(bad, schema)


def test_legacy_api_is_untouched():
    # archengine.py / system.py import these; the skeleton must not change them (goldens must not move).
    for name in ("xe_tank", "reservoir_vessel", "hall_magnetic_circuit", "hall_channel_mass", "structure_mass",
                 "build_bom", "BOMLine", "MGA"):
        assert hasattr(mb, name)
    assert set(mb.MGA) == {"new", "modified", "existing", "calculated"}


def test_power_boundary_coverage_if_available():
    try:
        from abep_sim import arch_boundary  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="bus_power_boundary_v1"):
            mb.check_power_boundary_coverage()
        return
    res = mb.check_power_boundary_coverage()
    for a in mb.ARCHITECTURES:
        assert res["architectures"][a] == {"uncovered": [], "unknown": []}
