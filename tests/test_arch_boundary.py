"""Tests for abep_sim.arch_boundary (bus_power_boundary_v1): conservation, refusals, identical common components, no defaults.

All loads/efficiencies below are synthetic test fixtures chosen for exact arithmetic; they are not data and must never
be read as evidence (evidence for callers lives in docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md).
"""
import ast
import inspect
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from abep_sim import arch_boundary as ab
from abep_sim.arch_boundary import (ARCHITECTURES, BOUNDARY_VERSION, COMMON_COMPONENTS, PREIONIZER_COMPONENTS,
                                    REQUIRED_COMPONENTS, bus_power_ledger)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "architecture_comparison" / "bus_power_boundary_v1.json"
DOC = ROOT / "docs" / "architecture_comparison" / "power_boundary" / "BUS_POWER_BOUNDARY.md"


def _fixture(arch, load=10.0, eta=0.5):
    comps = REQUIRED_COMPONENTS[arch]
    return {c: load for c in comps}, {c: eta for c in comps}


# ------------------------------------------------------------------ contract constants
def test_contract_constants():
    assert BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert ARCHITECTURES == ("hall_only", "rf_hall", "ecr_hall")
    assert isinstance(REQUIRED_COMPONENTS, dict) and set(REQUIRED_COMPONENTS) == set(ARCHITECTURES)
    for arch in ARCHITECTURES:
        comps = REQUIRED_COMPONENTS[arch]
        assert isinstance(comps, tuple) and all(isinstance(c, str) for c in comps)
        assert len(set(comps)) == len(comps)
    assert set(ab.COMPONENT_DEFINITIONS) == set(ab.ALL_COMPONENTS)


def test_common_components_identical_across_architectures():
    common = ("hall_discharge", "hall_magnet", "cathode_keeper", "cathode_heater",
              "flow_control", "compressor", "thermal_control", "housekeeping")
    assert COMMON_COMPONENTS == common
    for arch in ARCHITECTURES:
        assert REQUIRED_COMPONENTS[arch][:len(common)] == common
        assert REQUIRED_COMPONENTS[arch][len(common):] == PREIONIZER_COMPONENTS[arch]
    assert PREIONIZER_COMPONENTS == {"hall_only": (), "rf_hall": ("rf_source",), "ecr_hall": ("ecr_source", "ecr_magnet")}
    # the pre-ionizer components of one architecture never appear in another
    assert not set(PREIONIZER_COMPONENTS["rf_hall"]) & set(REQUIRED_COMPONENTS["ecr_hall"])
    assert not set(PREIONIZER_COMPONENTS["ecr_hall"]) & set(REQUIRED_COMPONENTS["rf_hall"])
    assert set(REQUIRED_COMPONENTS["hall_only"]) == set(common)


# ------------------------------------------------------------------ conservation
def test_exact_small_example():
    loads, effs = _fixture("hall_only", 10.0, 0.5)
    led = bus_power_ledger("hall_only", loads, effs)
    assert set(led) == {"boundary_version", "architecture", "P_bus_W", "items", "residual_W"}
    assert led["boundary_version"] == BOUNDARY_VERSION and led["architecture"] == "hall_only"
    assert [it["component"] for it in led["items"]] == list(REQUIRED_COMPONENTS["hall_only"])
    for it in led["items"]:
        assert set(it) == {"component", "P_load_W", "efficiency", "P_bus_W", "P_loss_W"}
        assert it["P_bus_W"] == 20.0 and it["P_loss_W"] == 10.0
    assert led["P_bus_W"] == 160.0 and led["residual_W"] == 0.0


@pytest.mark.parametrize("arch", ARCHITECTURES)
@pytest.mark.parametrize("seed", range(6))
def test_conservation_residual_near_zero(arch, seed):
    comps = REQUIRED_COMPONENTS[arch]
    # deterministic, varied fixtures covering efficiency 1, tiny efficiencies and large/small loads
    loads = {c: [0.0, 1e-9, 3.7, 812.25, 1.4e4, 0.3][(i + seed) % 6] for i, c in enumerate(comps)}
    effs = {c: [1.0, 0.93, 0.61, 1e-3, 0.5, 0.999999][(2 * i + seed) % 6] for i, c in enumerate(comps)}
    led = bus_power_ledger(arch, loads, effs)
    source_total = math.fsum(it["P_bus_W"] for it in led["items"])
    assert abs(led["residual_W"]) <= 1e-12 * max(source_total, 1.0)
    assert led["P_bus_W"] == pytest.approx(source_total, rel=1e-12, abs=1e-12)
    for it in led["items"]:
        assert it["P_bus_W"] == loads[it["component"]] / effs[it["component"]]
        assert it["P_loss_W"] >= 0.0
        assert it["P_load_W"] + it["P_loss_W"] == pytest.approx(it["P_bus_W"], rel=1e-15, abs=0.0)
    # destination side == delivered + converted to heat, independently summed
    delivered = math.fsum(loads.values())
    lost = math.fsum(it["P_loss_W"] for it in led["items"])
    assert led["P_bus_W"] == pytest.approx(delivered + lost, rel=1e-15)


def test_preionizer_power_is_on_the_bus():
    """The same common loads cost more bus power once a pre-ionizer draws power: nothing is discharge-only."""
    base_l, base_e = _fixture("hall_only", 50.0, 0.8)
    hall = bus_power_ledger("hall_only", base_l, base_e)
    for arch in ("rf_hall", "ecr_hall"):
        loads = dict(base_l); effs = dict(base_e)
        for c in PREIONIZER_COMPONENTS[arch]:
            loads[c] = 40.0; effs[c] = 0.5
        led = bus_power_ledger(arch, loads, effs)
        assert led["P_bus_W"] == pytest.approx(hall["P_bus_W"] + 80.0 * len(PREIONIZER_COMPONENTS[arch]))
        common_items = [it for it in led["items"] if it["component"] in COMMON_COMPONENTS]
        assert common_items == hall["items"]


def test_ecr_permanent_magnet_explicit_zero():
    loads, effs = _fixture("ecr_hall", 10.0, 0.9)
    loads["ecr_magnet"] = 0.0; effs["ecr_magnet"] = 1.0
    led = bus_power_ledger("ecr_hall", loads, effs)
    mag = [it for it in led["items"] if it["component"] == "ecr_magnet"][0]
    assert mag["P_bus_W"] == 0.0 and mag["P_loss_W"] == 0.0


def test_accepts_int_fraction_and_normalises_negative_zero():
    loads, effs = _fixture("rf_hall", 3, 1)
    loads["rf_source"] = Fraction(1, 3); effs["rf_source"] = Fraction(1, 2)
    loads["hall_magnet"] = -0.0
    led = bus_power_ledger("rf_hall", loads, effs)
    rf = [it for it in led["items"] if it["component"] == "rf_source"][0]
    assert rf["P_bus_W"] == pytest.approx(2.0 / 3.0)
    mag = [it for it in led["items"] if it["component"] == "hall_magnet"][0]
    assert math.copysign(1.0, mag["P_load_W"]) == 1.0
    assert all(isinstance(it[k], float) for it in led["items"] for k in ("P_load_W", "efficiency", "P_bus_W", "P_loss_W"))


def test_inputs_not_mutated():
    loads, effs = _fixture("ecr_hall")
    l0, e0 = dict(loads), dict(effs)
    bus_power_ledger("ecr_hall", loads, effs)
    assert loads == l0 and effs == e0


# ------------------------------------------------------------------ refusals
@pytest.mark.parametrize("arch", ["hall", "HALL_ONLY", "rf+hall", "", None, 3, ("hall_only",)])
def test_unknown_architecture(arch):
    loads, effs = _fixture("hall_only")
    with pytest.raises(ValueError):
        bus_power_ledger(arch, loads, effs)


@pytest.mark.parametrize("arch", ARCHITECTURES)
def test_missing_component_load(arch):
    for comp in REQUIRED_COMPONENTS[arch]:
        loads, effs = _fixture(arch)
        del loads[comp]
        with pytest.raises(ValueError, match="missing"):
            bus_power_ledger(arch, loads, effs)


@pytest.mark.parametrize("arch", ARCHITECTURES)
def test_missing_efficiency(arch):
    for comp in REQUIRED_COMPONENTS[arch]:
        loads, effs = _fixture(arch)
        del effs[comp]
        with pytest.raises(ValueError, match="missing"):
            bus_power_ledger(arch, loads, effs)


@pytest.mark.parametrize("arch,extra", [("hall_only", "rf_source"), ("hall_only", "ecr_source"), ("hall_only", "ecr_magnet"),
                                        ("rf_hall", "ecr_source"), ("rf_hall", "ecr_magnet"), ("ecr_hall", "rf_source"),
                                        ("hall_only", "neutralizer"), ("ecr_hall", "discharge")])
def test_extra_component_refused_in_loads_and_efficiencies(arch, extra):
    loads, effs = _fixture(arch)
    with pytest.raises(ValueError, match="extra"):
        bus_power_ledger(arch, {**loads, extra: 1.0}, effs)
    with pytest.raises(ValueError, match="extra"):
        bus_power_ledger(arch, loads, {**effs, extra: 0.9})


@pytest.mark.parametrize("eta", [0.0, -0.1, 1.0000001, 2.0, float("nan"), float("inf"), -float("inf"), True, False, "0.9", None, [0.9]])
def test_bad_efficiency(eta):
    loads, effs = _fixture("ecr_hall")
    effs["ecr_source"] = eta
    with pytest.raises(ValueError):
        bus_power_ledger("ecr_hall", loads, effs)


@pytest.mark.parametrize("load", [-1e-12, -5.0, float("nan"), float("inf"), -float("inf"), True, "10", None, complex(1, 0)])
def test_bad_load(load):
    loads, effs = _fixture("rf_hall")
    loads["hall_discharge"] = load
    with pytest.raises(ValueError):
        bus_power_ledger("rf_hall", loads, effs)


def test_bus_draw_overflow_refused():
    loads, effs = _fixture("hall_only")
    loads["hall_discharge"] = 1e308; effs["hall_discharge"] = 1e-3
    with pytest.raises(ValueError, match="overflow"):
        bus_power_ledger("hall_only", loads, effs)
    loads, effs = _fixture("hall_only", 1.7e308, 1.0)
    with pytest.raises(ValueError, match="overflow"):
        bus_power_ledger("hall_only", loads, effs)


@pytest.mark.parametrize("bad", [None, [("hall_discharge", 1.0)], 5.0, "loads"])
def test_non_mapping_inputs(bad):
    loads, effs = _fixture("hall_only")
    with pytest.raises(ValueError):
        bus_power_ledger("hall_only", bad, effs)
    with pytest.raises(ValueError):
        bus_power_ledger("hall_only", loads, bad)


def test_runtime_modification_of_boundary_refused():
    saved = REQUIRED_COMPONENTS["rf_hall"]
    try:
        REQUIRED_COMPONENTS["rf_hall"] = COMMON_COMPONENTS          # would silently drop the RF source
        loads, effs = _fixture("hall_only")
        with pytest.raises(RuntimeError, match="frozen"):
            bus_power_ledger("rf_hall", loads, effs)
    finally:
        REQUIRED_COMPONENTS["rf_hall"] = saved
    bus_power_ledger("rf_hall", *_fixture("rf_hall"))


# ------------------------------------------------------------------ no defaults, purity
def test_no_default_arguments_or_values():
    sig = inspect.signature(bus_power_ledger)
    assert list(sig.parameters) == ["arch", "loads", "efficiencies"]
    assert all(p.default is inspect.Parameter.empty for p in sig.parameters.values())
    with pytest.raises(TypeError):
        bus_power_ledger("hall_only", _fixture("hall_only")[0])          # efficiencies cannot be omitted
    with pytest.raises(ValueError, match="missing"):
        bus_power_ledger("hall_only", _fixture("hall_only")[0], {})      # nor defaulted per component
    loads, effs = _fixture("ecr_hall")
    del loads["ecr_magnet"]; del effs["ecr_magnet"]                       # permanent magnet must be explicit
    with pytest.raises(ValueError, match="missing"):
        bus_power_ledger("ecr_hall", loads, effs)
    # no public numeric constants (efficiency or load defaults) anywhere in the module
    for name, value in vars(ab).items():
        if name.startswith("_"):
            continue
        assert not (isinstance(value, (int, float)) and not isinstance(value, bool)), name
        if isinstance(value, dict):
            for v in value.values():
                assert isinstance(v, (tuple, str)), name


def test_module_is_pure_stdlib():
    tree = ast.parse(Path(ab.__file__).read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative imports: the boundary module must not depend on simulator modules"
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "math", "numbers", "collections"}, mods


# ------------------------------------------------------------------ schema and documentation
_ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs", "$comment"}


def _validate(inst, sch, root, path="$"):
    """Minimal JSON-Schema (2020-12 subset) validator; raises on keywords it does not implement, so a schema change
    cannot silently weaken this test. Returns a list of error strings."""
    errs = []
    for k in sch:
        if k in _ANNOTATIONS or k.startswith("x-"):
            continue
        if k not in {"$ref", "type", "enum", "const", "required", "properties", "additionalProperties", "prefixItems",
                     "items", "minItems", "maxItems", "minimum", "exclusiveMinimum", "maximum", "oneOf", "allOf"}:
            raise AssertionError(f"validator does not implement keyword {k!r}")
    if "$ref" in sch:
        node = root
        for part in sch["$ref"].lstrip("#/").split("/"):
            node = node[part]
        errs += _validate(inst, node, root, path)
    t = sch.get("type")
    if t == "object" and not isinstance(inst, dict):
        return errs + [f"{path}: not an object"]
    if t == "array" and not isinstance(inst, list):
        return errs + [f"{path}: not an array"]
    if t == "number" and (isinstance(inst, bool) or not isinstance(inst, (int, float))):
        return errs + [f"{path}: not a number"]
    if "enum" in sch and inst not in sch["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if "const" in sch and inst != sch["const"]:
        errs.append(f"{path}: {inst!r} != const {sch['const']!r}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in sch and not inst >= sch["minimum"]:
            errs.append(f"{path}: below minimum")
        if "exclusiveMinimum" in sch and not inst > sch["exclusiveMinimum"]:
            errs.append(f"{path}: not above exclusiveMinimum")
        if "maximum" in sch and not inst <= sch["maximum"]:
            errs.append(f"{path}: above maximum")
    if isinstance(inst, dict):
        for r in sch.get("required", []):
            if r not in inst:
                errs.append(f"{path}: missing {r!r}")
        props = sch.get("properties", {})
        for key, val in inst.items():
            if key in props:
                errs += _validate(val, props[key], root, f"{path}.{key}")
            elif sch.get("additionalProperties") is False:
                errs.append(f"{path}: additional property {key!r}")
    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            errs.append(f"{path}: too few items")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            errs.append(f"{path}: too many items")
        pre = sch.get("prefixItems", [])
        for i, val in enumerate(inst):
            if i < len(pre):
                errs += _validate(val, pre[i], root, f"{path}[{i}]")
            elif sch.get("items") is False:
                errs.append(f"{path}[{i}]: items beyond prefixItems not allowed")
    for sub in sch.get("allOf", []):
        errs += _validate(inst, sub, root, path)
    if "oneOf" in sch:
        n_ok = sum(1 for sub in sch["oneOf"] if not _validate(inst, sub, root, path))
        if n_ok != 1:
            errs.append(f"{path}: matches {n_ok} oneOf branches (need exactly 1)")
    return errs


def test_schema_matches_module():
    s = json.loads(SCHEMA.read_text())
    d = s["$defs"]
    assert s["x-boundary_version"] == BOUNDARY_VERSION
    assert tuple(s["x-common_components"]) == COMMON_COMPONENTS
    assert {a: tuple(v) for a, v in s["x-preionizer_components"].items()} == PREIONIZER_COMPONENTS
    assert tuple(d["architecture"]["enum"]) == ARCHITECTURES
    assert tuple(d["component"]["enum"]) == ab.ALL_COMPONENTS
    assert d["efficiency"]["exclusiveMinimum"] == 0 and d["efficiency"]["maximum"] == 1
    assert d["load_W"]["minimum"] == 0
    for arch in ARCHITECTURES:
        req = list(REQUIRED_COMPONENTS[arch])
        assert d[f"loads_{arch}"]["required"] == req and d[f"efficiencies_{arch}"]["required"] == req
        pre = d[f"ledger_{arch}"]["properties"]["items"]["prefixItems"]
        assert [p["allOf"][1]["properties"]["component"]["const"] for p in pre] == req
        assert set(d[f"ledger_{arch}"]["required"]) == {"boundary_version", "architecture", "P_bus_W", "items", "residual_W"}


@pytest.mark.parametrize("arch", ARCHITECTURES)
def test_ledger_and_inputs_validate_against_schema(arch):
    s = json.loads(SCHEMA.read_text())
    loads, effs = _fixture(arch, 12.5, 0.8)
    led = bus_power_ledger(arch, loads, effs)
    doc = {"inputs": {"architecture": arch, "loads": loads, "efficiencies": effs}, "ledger": led}
    assert _validate(json.loads(json.dumps(doc)), s, s) == []
    # negative controls: the schema must reject what the module refuses
    other = [a for a in ARCHITECTURES if a != arch][0]
    bad_arch = json.loads(json.dumps(doc)); bad_arch["ledger"]["architecture"] = other
    assert _validate(bad_arch, s, s)
    bad_eff = json.loads(json.dumps(doc)); bad_eff["inputs"]["efficiencies"]["hall_discharge"] = 0
    assert _validate(bad_eff, s, s)
    missing = json.loads(json.dumps(doc)); del missing["inputs"]["loads"]["housekeeping"]
    assert _validate(missing, s, s)
    extra_item = json.loads(json.dumps(doc)); extra_item["ledger"]["items"].append(dict(extra_item["ledger"]["items"][0]))
    assert _validate(extra_item, s, s)
    swapped = json.loads(json.dumps(doc)); it = swapped["ledger"]["items"]; it[0], it[1] = it[1], it[0]
    assert _validate(swapped, s, s)


def test_boundary_document_covers_every_component():
    text = DOC.read_text()
    assert BOUNDARY_VERSION in text
    for comp in ab.ALL_COMPONENTS:
        assert f"`{comp}`" in text, comp
    for arch in ARCHITECTURES:
        assert f"`{arch}`" in text, arch
    assert "DISCREPANCY AUDIT" in text
