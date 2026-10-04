"""A9.22 G8 stages 1 and 2: bus_power_boundary_a9_v2 (abep_sim/bus_boundary_a9_v2.py + power_boundary_a9_v2/), the
consumer inventory and the stage-2 migration record (STAGE2_MIGRATION.json).

v1 stays byte-identical; v2 differs from v1 only in the configuration taxonomy (hall_icp_neutralizer only; C1 as
ground-reference / test metadata); a v2 ledger / gate / allocation / start-up result equals v1's except the label.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import types

import pytest

from abep_sim import bus_boundary_a9 as B1
from abep_sim import bus_boundary_a9_v2 as B2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE = os.path.join(ROOT, "docs", "architecture_comparison", "power_boundary_a9_v2")
V2_JSON = os.path.join(LANE, "bus_power_boundary_a9_v2.json")
V2_SCHEMA = os.path.join(ROOT, "schemas", "interfaces", "bus_power_boundary_a9_v2.json")
V1_JSON = os.path.join(ROOT, "docs", "architecture_comparison", "power_boundary_a9", "bus_power_boundary_a9_v1.json")
ICP, C1 = "hall_icp_neutralizer", "hall_c1_reference"
V1_SHAS = {
    "abep_sim/bus_boundary_a9.py": "7b23dbd23d39bd576691f877c0b32b64c14e83e796b2da9a662f0639319c878a",
    "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json":
        "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6",
    "docs/architecture_comparison/power_boundary_a9/build_bus_power_boundary_a9.py":
        "d5c8130ff0f7bea66d9eb82f552f96ebea0eac7f9514fd097bd120ad7397c482",
    "docs/architecture_comparison/power_boundary_a9/BUS_POWER_BOUNDARY_A9.md":
        "bc2c761720ad39a3e7c21a17937ff44a87059d4b5f3b3aadcee64cb323b0a5d0",
    "schemas/interfaces/bus_power_boundary_a9_v1.json":
        "64238d1526d8ce6bf3ca6b45f385f8948e6dcf916e4f2140cbcb6c46d2c7aa09",
}


def _mod(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------------ v1 immutable
@pytest.mark.parametrize("rel", sorted(V1_SHAS))
def test_v1_family_byte_identical(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == V1_SHAS[rel]


# ------------------------------------------------------------------------------------------------ module
def test_v2_taxonomy_is_icp_only():
    assert B2.BOUNDARY_VERSION == "bus_power_boundary_a9_v2"
    assert B2.CONFIGURATIONS == (ICP,)
    for t in (B2.BASE_SLOTS, B2.VARIANT_OPTIONS, B2.ENFORCED_ORDER, B2.SEQUENCE_TEMPLATES):
        assert set(t) == {ICP} and t[ICP] == getattr(B1, [k for k in B2.TAXONOMY_NAMES
                                                         if getattr(B2, k) is t][0])[ICP]
    assert C1 not in B2.CONFIGURATIONS
    gm = B2.GROUND_REFERENCE_TEST_METADATA[C1]
    assert gm["role"] == "GROUND_ONLY_LAB_REFERENCE" and gm["flight_bus_configuration"] is False
    assert gm["base_slots_as_in_v1"] == B1.BASE_SLOTS[C1]
    with pytest.raises(B2.BoundaryA9Error, match="unknown configuration"):
        B2.installed_slots(C1)


def test_every_other_v1_name_is_identical():
    own = set(B2.TAXONOMY_NAMES) | {"BOUNDARY_VERSION"}
    for n, v in vars(B1).items():
        if n.startswith("__") or n in own:
            continue
        if isinstance(v, types.FunctionType):
            w = getattr(B2, n)
            assert w is not v and w.__globals__ is vars(B2), n
            assert w.__code__.co_code == v.__code__.co_code, n        # same bytecode
            ca = [c.replace(B1.BOUNDARY_VERSION, B2.BOUNDARY_VERSION) if isinstance(c, str) else
                  (None if isinstance(c, types.CodeType) else c) for c in v.__code__.co_consts]
            cb = [None if isinstance(c, types.CodeType) else c for c in w.__code__.co_consts]
            assert ca == cb, n
        else:
            assert getattr(B2, n) is v, n


def _synthetic(slots, scale=1.0):
    loads = {s: {"P_W": 10.0 * scale, "evidence_class": "measured", "source": "SYNTHETIC"} for s in slots}
    effs = {s: {"value": 0.9, "evidence_class": "assumed", "source": "SYNTHETIC", "path": "internal_bus"} for s in slots}
    return _plane(loads), effs


def _plane(loads):
    if "icp_rf_source" in loads:
        loads["icp_rf_source"]["plane"] = "generator_dc_input"
    return loads


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k != "boundary_version"}
    if isinstance(o, list):
        return [_strip(x) for x in o]
    return o


GM = {"sample_rate_Sa_s": 2e5, "bandwidth_Hz": 5e4, "anti_alias_documented": True, "synchronized": True,
      "source": "SYNTHETIC"}


@pytest.mark.parametrize("variant", [(), ("active_cooling",), ("icp_assist_magnet", "flow_control_icp_feed")])
@pytest.mark.parametrize("scale", [1.0, 30.0])
def test_no_physics_change_ledger_gate_allocations(variant, scale):
    fe = {"value": 0.95, "evidence_class": "assumed", "source": "SYNTHETIC"}
    loads, effs = _synthetic(B1.installed_slots(ICP, variant), scale)
    l1 = B1.ledger(ICP, loads, effs, fe, variant, "x", "p_bus_1ms_max", GM)
    l2 = B2.ledger(ICP, loads, effs, fe, variant, "x", "p_bus_1ms_max", GM)
    assert l1["boundary_version"] == "bus_power_boundary_a9_v1" and l2["boundary_version"] == B2.BOUNDARY_VERSION
    assert _strip(l1) == _strip(l2)
    assert B1.rfp_power_gate(l1, [l1]) == B2.rfp_power_gate(l2, [l2])
    assert B1.allocation_checks(l1) == B2.allocation_checks(l2)
    assert B1.icp_power_allocation_check(l1) == B2.icp_power_allocation_check(l2)
    with pytest.raises(B2.BoundaryA9Error):          # ledgers are not interchangeable across versions
        B2.allocation_checks(l1)


def test_no_physics_change_tbd_and_startup():
    fe = {"value": "TBD", "tbd_requires": "x"}
    slots = B1.installed_slots(ICP)
    loads = _plane({s: {"P_W": "TBD", "tbd_requires": "x"} for s in slots})
    effs = {s: {"value": "TBD", "tbd_requires": "x", "path": "internal_bus"} for s in slots}
    assert _strip(B1.ledger(ICP, loads, effs, fe)) == _strip(B2.ledger(ICP, loads, effs, fe))
    steps = []
    for i, st in enumerate(B1.SEQUENCE_TEMPLATES[ICP]):
        on = {s for t in B1.SEQUENCE_TEMPLATES[ICP][:i + 1] for s in t["on"]}
        ld = _plane({s: {"P_W": 10.0 if s in on else 0.0, "evidence_class": "measured", "source": "S"} for s in slots})
        ef = {s: {"value": 0.9, "evidence_class": "measured", "source": "S", "path": "internal_bus"} for s in slots}
        steps.append({"step_id": st["step_id"], "event": st["event"], "loads": ld, "efficiencies": ef,
                      "power_basis": "p_bus_1ms_max", "gate_measurement": GM,
                      **({"phase": "steady"} if st.get("phase") else {})})
    fe = {"value": 0.95, "evidence_class": "measured", "source": "S"}
    r1, r2 = B1.check_startup_sequence(ICP, steps, fe), B2.check_startup_sequence(ICP, steps, fe)
    assert _strip(r1) == _strip(r2) and r2["boundary_version"] == B2.BOUNDARY_VERSION
    assert B1.p_bus_1ms_max([100.0] * 200, 1e5, 2e4, True, True) == B2.p_bus_1ms_max([100.0] * 200, 1e5, 2e4, True, True)
    assert B1.rf_power_planes(100, 80, 5, 70, 1) == B2.rf_power_planes(100, 80, 5, 70, 1)


# ------------------------------------------------------------------------------------------------ artefact
def test_builder_reproduces_outputs():
    assert _mod("build_v2", "docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py"
                ).main(["--check"]) == 0


def _all_values(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _all_values(v)
    elif isinstance(o, list):
        for v in o:
            yield from _all_values(v)
    else:
        yield o


def test_v2_equals_v1_except_taxonomy():
    bld = _mod("build_v2b", "docs/architecture_comparison/power_boundary_a9_v2/build_bus_power_boundary_a9_v2.py")
    v1, v2 = _load(V1_JSON), _load(V2_JSON)
    stripped = {k: v for k, v in v2.items() if k not in ("v1_to_v2_diff",)}
    entries = bld.classify(bld.diff(v1, stripped), bld.DOC_CLASSES, "doc")    # raises on an undeclared change
    classes = {e["class"] for e in entries}
    assert classes <= {"IDENTITY", "TAXONOMY", "PROVENANCE_ADDED"}
    # all content-bearing differences are taxonomy; identity ones are labels/provenance only
    for e in entries:
        if e["class"] == "IDENTITY":
            assert e["path"] in ("/id", "/boundary_version", "/module", "/schema_file", "/generated_by",
                                 "/regenerate", "/date", "/base_commit", "/compliance/a9_v1_boundary_byte_identical") \
                or e["path"].startswith("/compliance/allowed_paths/")
    # carried sections identical
    for k in ("items", "rf_power_planes", "bus_architecture", "gates_and_allocations", "interface_demands",
              "h2_4_revision_flags", "owner_answers_applied", "open_owner_questions", "historical_reuse",
              "m16_impact", "h3_inputs", "h4_inputs", "a9_10_reconciliation", "decision_pins", "pinned_inputs"):
        assert v2[k] == v1[k], k
    s1 = copy.deepcopy(v1["slots"])
    for s in s1:
        s["configurations"].pop(C1)
    assert v2["slots"] == s1
    assert v2["sequencing"]["templates_PROPOSED"] == {ICP: v1["sequencing"]["templates_PROPOSED"][ICP]}
    assert v2["sequencing"]["rules"] == v1["sequencing"]["rules"]


def test_no_c1_in_v2_configuration_lists():
    v2, s2 = _load(V2_JSON), _load(V2_SCHEMA)
    assert v2["configurations"] == [ICP] and list(v2["variant_options"]) == [ICP]
    assert all(list(s["configurations"]) == [ICP] for s in v2["slots"])
    assert list(v2["sequencing"]["enforced_order"]) == [ICP]
    assert list(v2["sequencing"]["templates_PROPOSED"]) == [ICP]
    assert s2["properties"]["configuration"]["enum"] == [ICP]
    assert list(s2["x-bus-power-boundary-a9"]["installed_slots"]) == [ICP]
    gm = v2["ground_reference_test_metadata"][C1]
    assert gm["role"] == "GROUND_ONLY_LAB_REFERENCE" and gm["flight_bus_configuration"] is False
    assert gm["slot_installation_as_in_v1"] == {s["slot"]: s["configurations"][C1] for s in _load(V1_JSON)["slots"]}
    # C1 named as a value only inside ground-reference metadata or the recorded v1 history of the diff
    outside = {k: v for k, v in v2.items() if k not in ("ground_reference_test_metadata", "v1_to_v2_diff",
                                                        "schema_v1_to_v2_diff")}
    assert C1 not in [x for x in _all_values({k: outside[k] for k in ("configurations", "variant_options", "slots",
                                                                       "sequencing")})]


def test_schema_v2_validates_icp_ledger_input():
    import jsonschema  # locked (requirements-lock.txt): a missing dep fails, never adds a skip (rule 9)
    s2 = _load(V2_SCHEMA)
    slots = B2.installed_slots(ICP)
    loads, effs = _synthetic(slots)
    inst = {"boundary_version": B2.BOUNDARY_VERSION, "configuration": ICP, "variant": [], "loads": loads,
            "efficiencies": effs, "front_end": {"value": 0.95, "evidence_class": "assumed", "source": "x"}}
    jsonschema.validate(inst, s2)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(dict(inst, configuration=C1), s2)


def test_consumer_inventory_reproduces_and_counts():
    inv = _load(os.path.join(LANE, "CONSUMER_INVENTORY.json"))
    st = {c["status"] for c in inv["consumers"]}
    assert st <= set(inv["statuses"])
    assert inv["counts"]["files"] == len(inv["consumers"])
    for c in inv["consumers"]:
        assert c["hits"] and all(h["line"] >= 1 for h in c["hits"])
    paths = {c["path"]: c["status"] for c in inv["consumers"]}
    assert paths["abep_sim/design/architecture_optimizer.py"] == "LIVE_REPOINT"
    assert paths["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"] == "IMMUTABLE_HISTORY"
    assert paths["abep_sim/bus_boundary_a9.py"] == "SELF_V1"


# ------------------------------------------------------------------------------------------------ stage 2 (migration)
def test_stage2_migration_record():
    """A9.22 G8 stage 2: every LIVE_REPOINT consumer re-pointed in one migration; no number moved (field by field)."""
    inv = _load(os.path.join(LANE, "CONSUMER_INVENTORY.json"))
    rec = _load(os.path.join(LANE, "STAGE2_MIGRATION.json"))
    assert rec["pre_commit"] == inv["base_commit"]
    assert inv["counts"]["files_by_status"]["LIVE_REPOINT"] == 28
    assert rec["verdict"].startswith("NO_PHYSICS_RESULT_CHANGED")
    assert not set(rec["class_totals"]) & {"NUMERIC_CHANGE", "UNEXPLAINED"}
    live = {c["path"] for c in inv["consumers"] if c["status"] == "LIVE_REPOINT"}
    assert {r["path"] for r in rec["repointed_consumers"]} == live
    assert all(r["sha256_before"] != r["sha256_after"] for r in rec["repointed_consumers"])
    assert {p["path"]: p["sha256"] for p in rec["v1_family_byte_identical"]} == V1_SHAS
    for o in rec["outputs"]:
        if o["kind"] == "markdown":
            assert o["numbers_in_changed_lines_identical"] is True, o["path"]
        else:
            assert all(c["class"] in ("PIN_SHA", "PATH", "LABEL", "PROVENANCE_TEXT", "PROVENANCE_ADDED")
                       for c in o["changes"]), o["path"]
    assert all(r["retained_because"] for r in rec["remaining_v1_references"])


def test_stage2_flight_consumers_use_v2_and_c1_stays_v1():
    mp = _load(os.path.join(ROOT, "docs", "budgets", "mass_power_a9_v3", "mass_power_a9_v3.json"))
    p = mp["power"]
    assert (p["boundary_version"], p["module"]) == ("bus_power_boundary_a9_v2", "abep_sim/bus_boundary_a9_v2.py")
    assert set(p["configurations"]) == {ICP}
    h = p["retired_flight_configuration_history"]
    assert h["boundary_version"] == "bus_power_boundary_a9_v1" and set(h["configurations"]) == {C1}
    from abep_sim.design import architecture_optimizer as ao
    assert ao.bb is B2 and tuple(ao.CONFIGURATIONS) == B2.CONFIGURATIONS
    assert ao.GROUND_REFERENCE_CONFIGURATIONS == tuple(B2.GROUND_REFERENCE_TEST_METADATA)
    rvm = _load(os.path.join(ROOT, "docs", "requirements", "rvm_a9", "rvm_a9_v1.json"))
    n = 0
    for r in rvm["rows"]:
        for cfg, cell in r["configurations"].items():
            for a in cell.get("artifacts", []):
                if "power_boundary_a9" in a.get("path", ""):
                    n += 1
                    want = "power_boundary_a9_v2/" if cfg == ICP else "power_boundary_a9/"
                    assert want in a["path"], (r["id"], cfg, a["path"])
    assert n == 7                        # 5 flight cells on v2, 2 C1 ground-reference cells (RVM-19 / RVM-20) on v1
