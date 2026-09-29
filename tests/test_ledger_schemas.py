"""Engineering ledger schemas v1 (schemas/ledgers/, docs/ledgers/LEDGERS.md).

Static checks only: the schemas parse, every term of the archengine energy ledger maps to a ledger field, every code
reference resolves, the bus ledger carries residual-closure rules whose tolerance is read from the archengine gate, and
the crosswalk onto bus_power_boundary_v1 is consistent (each converter loss owned once, pooled losses never boundary
items). Cross-lane checks (abep_sim.arch_boundary REQUIRED_COMPONENTS, abep_sim.thermal_life THERMAL_COMPONENTS, the
mass_bom_v1 catalog) run when those modules are present and skip otherwise; nothing is imported at collection time.
No simulation.
"""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas" / "ledgers"
DOC = ROOT / "docs" / "ledgers" / "LEDGERS.md"
ARCH = ROOT / "abep_sim" / "archengine.py"
SIX = ("performance", "power", "mass", "rejected_heat", "life", "uncertainty")
REQUESTED = ("intake", "filter", "compressor", "buffer", "valves", "xe_tank", "cathode", "magnets", "preionizer",
             "hall_discharge", "ppu", "thermal_control", "avionics")


def _load(name):
    return json.loads((SCHEMAS / name).read_text())


@pytest.fixture(scope="module")
def sub():
    return _load("subsystem_ledger_v1.json")


@pytest.fixture(scope="module")
def bus():
    return _load("bus_power_ledger_v1.json")


@pytest.fixture(scope="module")
def th():
    return _load("thermal_rejection_ledger_v1.json")


def _close_architecture_node():
    tree = ast.parse(ARCH.read_text())
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "close_architecture")


def _archengine_ledger_keys():
    fn = _close_architecture_node()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ledger" for t in n.targets):
            assert isinstance(n.value, ast.Dict)
            return {k.value for k in n.value.keys}
    raise AssertionError("archengine close_architecture has no 'ledger' dict")


def _archengine_converter_names():
    names = set()
    for path in (ARCH, ROOT / "abep_sim" / "ppu.py"):
        for n in ast.walk(ast.parse(path.read_text())):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "Converter" and n.args \
                    and isinstance(n.args[0], ast.Constant):
                names.add(n.args[0].value)
    return names


def test_schemas_parse_and_identify(sub, bus, th):
    assert sub["schema"] == "subsystem_ledger_v1"
    assert bus["schema"] == "bus_power_ledger_v1"
    assert th["schema"] == "thermal_rejection_ledger_v1"


def test_every_subsystem_has_six_blocks(sub):
    subs = sub["subsystems"]
    for s in REQUESTED:
        assert s in subs, s
    assert set(SIX) <= set(sub["quantities"])
    for sid, s in subs.items():
        assert s["hall_transport_ensemble_role"] in sub["hall_transport_ensemble_roles"], sid
        for b in SIX:
            assert b in s and "status" in s[b], (sid, b)


def test_upstream_roles_follow_scope_rule(sub):
    subs = sub["subsystems"]
    for s in ("intake", "filter", "compressor", "buffer", "valves", "xe_tank"):
        assert subs[s]["hall_transport_ensemble_role"] == "forbidden_upstream", s
        drivers = subs[s]["uncertainty"].get("drivers", [])
        assert not any("hall_ensemble" in d.get("ref", "") or "transport" in d.get("name", "") for d in drivers), s
    assert subs["hall_discharge"]["hall_transport_ensemble_role"] == "carrier"


def test_every_archengine_energy_ledger_term_maps(sub, bus, th):
    keys = _archengine_ledger_keys()
    assert keys, "empty archengine ledger"
    mapped = sub["archengine_energy_ledger_map"]["terms"]
    assert set(mapped) == keys, (set(mapped) ^ keys)
    bus_ids = {t["id"] for t in bus["terms"]}
    bus_covered = set().union(*(t["archengine_energy_ledger_terms"] for t in bus["terms"]))
    for k in keys:
        assert k in bus_covered, k
        assert set(mapped[k]["bus_terms"]) <= bus_ids, k
        assert set(mapped[k]["subsystems"]) <= set(sub["subsystems"]), k
    # every subsystem-level bus_terms / energy-ledger reference is defined
    for sid, s in sub["subsystems"].items():
        assert set(s["power"].get("bus_terms", [])) <= bus_ids, sid
        assert set(s["rejected_heat"].get("archengine_energy_ledger_terms", [])) <= keys, sid


def test_every_ppu_converter_maps_to_a_bus_term(bus):
    covered = set().union(*(t["ppu_converters"] for t in bus["terms"]))
    missing = _archengine_converter_names() - covered
    assert not missing, missing


def _archengine_resid_gate():
    """The numeric tolerance of 'if abs(resid) > <tol>' inside close_architecture (read from the code, not assumed)."""
    fn = _close_architecture_node()
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Call) and getattr(n.left.func, "id", None) == "abs" \
                and n.left.args and isinstance(n.left.args[0], ast.Name) and n.left.args[0].id == "resid" \
                and isinstance(n.ops[0], ast.Gt) and isinstance(n.comparators[0], ast.Constant):
            return float(n.comparators[0].value)
    raise AssertionError("no 'abs(resid) > tol' gate in archengine close_architecture")


def test_bus_ledger_has_residual_closure_rule(bus):
    c = bus["closure"]
    dv = c["decomposition_view"]
    assert "P_bus_W" in dv["identity"] and "P_PPU_losses" in dv["identity"]
    assert "resid" in dv["residual"]
    # same tolerance as the archengine gate, read from the code
    assert dv["gate_rel_tol"] == _archengine_resid_gate()
    src = ARCH.read_text()
    assert "resid = (P_bus - sum(ledger.values())) / P_bus" in src
    # the decomposition identity lists every load-plane and loss term of the schema exactly once
    for t in bus["terms"]:
        assert dv["identity"].count(t["id"]) == 1, t["id"]
        assert t["plane"] in ("load", "loss"), t["id"]
    # the boundary view is delegated to arch_boundary and uses an absolute residual
    bv = c["boundary_view"]
    assert "residual_W" in bv["residual"] and "arch_boundary" in bv["producer"]
    assert {"CLOSED_ALL_TERMS", "CLOSED_MODELED_TERMS_ONLY", "NOT_EVALUABLE", "OPEN"} <= set(c["completeness"]["values"])
    for t in bus["terms"]:
        assert t["status"] in ("computed", "partial", "superseded", "TBD"), t["id"]
        if t["status"] == "TBD":
            assert t["origin"].startswith("TBD — requires"), t["id"]
        if t["status"] == "superseded":
            assert t.get("superseded_by"), t["id"]


# ------------------------------------------------------------------ crosswalk to bus_power_boundary_v1 (lane_11)
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
BOOKINGS = ("load", "outside_boundary_v1", "unattributed", "distributed_into_component_efficiency")


def test_crosswalk_is_internally_consistent(bus, sub):
    cw = bus["boundary_crosswalk"]
    comps = cw["components"]
    arch = bus["architectures"]
    assert tuple(arch["ids"]) == ARCHS
    # every architecture's boundary component list is covered by the crosswalk and names only crosswalk components
    for a in ARCHS:
        assert set(arch[a]["boundary_components"]) <= set(comps), a
        assert set(arch[a]["preionizer_components"]) <= set(arch[a]["boundary_components"]), a
        for c in arch[a]["boundary_components"]:
            assert a in comps[c]["architectures"], (a, c)
    assert set().union(*(set(arch[a]["boundary_components"]) for a in ARCHS)) == set(comps)
    assert arch["hall_only"]["preionizer_components"] == []
    # terms <-> components agree in both directions; pooled losses are never boundary components
    terms = {t["id"]: t for t in bus["terms"]}
    for t in terms.values():
        assert t["boundary_booking"] in BOOKINGS, t["id"]
        if t["boundary_booking"] == "load":
            assert t["boundary_components"], t["id"]
        else:
            assert t["boundary_components"] == [], t["id"]
            assert t["id"] in cw["not_on_boundary"], t["id"]
        for c in t["boundary_components"]:
            assert t["id"] in comps[c]["load_terms"], (t["id"], c)
    for c, rec in comps.items():
        for tid in rec["load_terms"]:
            assert c in terms[tid]["boundary_components"], (c, tid)
    assert terms["P_PPU_losses"]["boundary_booking"] == "distributed_into_component_efficiency"
    assert terms["P_harness_losses"]["boundary_booking"] == "distributed_into_component_efficiency"
    # A1: each ppu converter has at most one boundary owner (each converter loss is booked once)
    owners = {}
    for c, rec in comps.items():
        for k in rec["ppu_converters"]:
            assert k not in owners, (k, owners.get(k), c)
            owners[k] = c
    # converters without an owner are exactly those of unattributed / outside terms
    unowned = _archengine_converter_names() - set(owners)
    allowed = set().union(*(set(t["ppu_converters"]) for t in terms.values()
                            if t["boundary_booking"] in ("unattributed", "outside_boundary_v1")))
    assert unowned <= allowed, unowned - allowed
    # every per-architecture term exists and a pre-ionizer term appears only where a pre-ionizer exists
    for a in ARCHS:
        assert set(arch[a]["decomposition_terms"]) <= set(terms), a
        assert ("P_preionizer" in arch[a]["decomposition_terms"]) == bool(arch[a]["preionizer_components"]), a
    # subsystem-level mapping carries every boundary component of every architecture
    for a in ARCHS:
        carried = set()
        for sid, s in sub["subsystems"].items():
            m = s["execution_branch_mapping"]
            carried |= set(m["boundary_components"].get(a, []))
            assert set(m["boundary_components"]) <= set(m["architectures"]), sid
        assert carried == set(arch[a]["boundary_components"]), (a, carried ^ set(arch[a]["boundary_components"]))
    pre = sub["subsystems"]["preionizer"]["execution_branch_mapping"]
    assert pre["architectures"] == ["rf_hall", "ecr_hall"]
    assert pre["boundary_components"]["rf_hall"] == ["rf_source"]
    assert pre["boundary_components"]["ecr_hall"] == ["ecr_source"]


def _module_file(mod: str) -> Path:
    return ROOT / (mod.replace(".", "/") + ".py")


def test_crosswalk_covers_arch_boundary_required_components(bus):
    """Against the real module (lane_11_bus_boundary) when present; skipped in a checkout that predates it."""
    if not _module_file("abep_sim.arch_boundary").exists():
        pytest.skip("abep_sim/arch_boundary.py not present in this checkout (resolved lazily)")
    import importlib
    ab = importlib.import_module("abep_sim.arch_boundary")
    assert ab.BOUNDARY_VERSION == bus["boundary_crosswalk"]["boundary_version"]
    assert tuple(ab.ARCHITECTURES) == ARCHS
    comps = bus["boundary_crosswalk"]["components"]
    for a in ARCHS:
        req = tuple(ab.REQUIRED_COMPONENTS[a])
        assert tuple(bus["architectures"][a]["boundary_components"]) == req, a
        assert tuple(bus["architectures"][a]["preionizer_components"]) == tuple(ab.PREIONIZER_COMPONENTS[a]), a
        for c in req:
            assert c in comps and a in comps[c]["architectures"], (a, c)
    assert set(comps) == set(ab.ALL_COMPONENTS)


def _module_constant(path: Path, name: str):
    for n in ast.parse(path.read_text()).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(f"{name} not found in {path}")


def test_thermal_life_components_map_once(th, sub):
    p = _module_file("abep_sim.thermal_life")
    tl_schema = th["thermal_life_crosswalk"]["components"]
    for c, rec in tl_schema.items():
        assert rec["subsystem"] in sub["subsystems"], c
        assert c in sub["subsystems"][rec["subsystem"]]["execution_branch_mapping"]["thermal_life_components"], c
    mapped = [c for s in sub["subsystems"].values() for c in s["execution_branch_mapping"]["thermal_life_components"]]
    assert len(mapped) == len(set(mapped)) and set(mapped) == set(tl_schema)
    if not p.exists():
        pytest.skip("abep_sim/thermal_life.py not present in this checkout (resolved lazily)")
    assert set(_module_constant(p, "THERMAL_COMPONENTS")) == set(tl_schema)


def test_mass_bom_v1_items_map_to_subsystems(sub):
    p = _module_file("abep_sim.mass_bom")
    if not p.exists():
        pytest.skip("abep_sim/mass_bom.py not present")
    mapped = {i for s in sub["subsystems"].values() for i in s["execution_branch_mapping"]["mass_bom_v1_items"]}
    ids = set()
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_item" and n.args \
                and isinstance(n.args[0], ast.Constant):
            ids.add(n.args[0].value)
    if not ids:
        pytest.skip("mass_bom_v1 catalog (lane_21_mass_bom) not present in this checkout")
    assert ids == mapped, ids ^ mapped


def test_execution_branch_refs_resolve(bus):
    """Dotted references to modules of lanes merged after this lane's base; each module is checked only when its
    lane version marker is defined (an older checkout of the same file is skipped, not failed)."""
    cw = bus["boundary_crosswalk"]
    refs, markers = cw["execution_branch_refs"], cw["execution_branch_markers"]
    checked = 0
    for r in refs:
        mod, name = r.rsplit(".", 1)
        p = _module_file(mod)
        if not p.exists() or markers[mod] not in _defined_names(p):
            continue
        assert name in _defined_names(p), r
        checked += 1
    if not checked:
        pytest.skip("none of the execution-branch modules is present in this checkout")


def test_architecture_ids_milestones_and_draft_markers(sub, bus, th):
    doc = DOC.read_text()
    for a in ARCHS:
        assert f"`{a}`" in doc, a
        for f in ("subsystem_ledger_v1.json", "bus_power_ledger_v1.json", "thermal_rejection_ledger_v1.json"):
            assert a in (SCHEMAS / f).read_text(), (a, f)
    for d in (sub, bus, th):
        assert d["status"].startswith("DRAFT — PROPOSED"), d["schema"]
        assert set(d["milestones"]["supports"]) <= {"A", "B", "C"} and {"A", "B", "C"} <= set(d["milestones"])
    assert "**Milestones.**" in doc and "DRAFT — PROPOSED" in doc
    # the stale 'boundary not in the tree' claim is gone
    assert "is not in the tree" not in doc and "not present in the tree" not in json.dumps(bus)
    assert "P_avionics" not in doc + json.dumps(bus) + json.dumps(sub)


def test_thermal_ledger_nodes_match_code_and_close(th, sub):
    tree = ast.parse((ROOT / "abep_sim" / "thermal.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "default_nodes")
    nodes = {c.args[0].value for c in ast.walk(fn) if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "Node"}
    nm = th["node_map"]
    assert nodes <= set(nm), nodes - set(nm)
    for sid, s in sub["subsystems"].items():
        assert set(s["rejected_heat"].get("thermal_nodes", [])) <= nodes, sid
    cl = th["closure"]["electrical_to_thermal"]
    assert "0.02" in cl["gate"] and "resid_th" in cl["residual"]


_REF = re.compile(r"((?:abep_sim|scripts)/[\w/]+\.py):([A-Za-z_][\w.]*)")


def _defined_names(path: Path):
    names = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            names.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    return names


def test_code_references_resolve():
    text = "".join((SCHEMAS / f).read_text() for f in
                   ("subsystem_ledger_v1.json", "bus_power_ledger_v1.json", "thermal_rejection_ledger_v1.json"))
    text += DOC.read_text()
    refs = set(_REF.findall(text))
    assert refs
    cache = {}
    for f, q in refs:
        p = ROOT / f
        assert p.exists(), f
        names = cache.setdefault(f, _defined_names(p))
        for part in q.split("."):
            assert part in names, f"{f}:{q}"


def test_gap_ids_are_registered():
    doc = DOC.read_text()
    registered = set(re.findall(r"^\| (G\d+) \|", doc, flags=re.M))
    used = set()
    for f in ("subsystem_ledger_v1.json", "bus_power_ledger_v1.json", "thermal_rejection_ledger_v1.json"):
        used |= set(re.findall(r"\bG\d+\b", (SCHEMAS / f).read_text()))
    assert used <= registered, used - registered


def test_schemas_carry_no_subsystem_values():
    """Schema files define fields; any 'value' key must be null (numbers belong to instances with evidence)."""
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "value":
                    assert v is None or isinstance(v, str)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for f in ("subsystem_ledger_v1.json", "bus_power_ledger_v1.json", "thermal_rejection_ledger_v1.json"):
        walk(_load(f))
