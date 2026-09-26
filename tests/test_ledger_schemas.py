"""Engineering ledger schemas v1 (schemas/ledgers/, docs/ledgers/LEDGERS.md).

Static checks only: the schemas parse, every term of the archengine energy ledger maps to a ledger field, every code
reference resolves, and the bus ledger carries a residual-closure rule matching the archengine gate. No simulation.
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


def test_bus_ledger_has_residual_closure_rule(bus):
    c = bus["closure"]
    assert "identity" in c and "P_bus_W" in c["identity"]
    assert "resid" in c["residual"]
    assert "0.02" in c["gate"]
    assert {"CLOSED_ALL_TERMS", "CLOSED_MODELED_TERMS_ONLY", "NOT_EVALUABLE", "OPEN"} <= set(c["completeness"]["values"])
    # same tolerance as the archengine gate
    src = ARCH.read_text()
    assert "resid = (P_bus - sum(ledger.values())) / P_bus" in src
    assert "if abs(resid) > 0.02" in src
    for t in bus["terms"]:
        assert t["status"] in ("computed", "partial", "superseded", "TBD"), t["id"]
        if t["status"] == "TBD":
            assert t["origin"].startswith("TBD — requires"), t["id"]
        if t["status"] == "superseded":
            assert t.get("superseded_by"), t["id"]


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
