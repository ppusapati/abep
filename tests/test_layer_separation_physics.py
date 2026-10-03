"""A9.22 layer separation (owner decisions 2026-10-03, docs/decisions/OD_2026_10_03_A9_22_*): the physics layer.

Physics modules = every module under abep_sim/ except abep_sim/assessment/**, abep_sim/programme/** (the
programme-runner layer, which combines physics and assessment) and abep_sim/configuration.py (the configuration loader
is the one place that opens config/requirements/). For them:

1. AST import graph: no import from abep_sim.assessment. The remaining compatibility call sites are listed EXPLICITLY
   in ASSESSMENT_IMPORT_ALLOWLIST with their reason; any new import fails, and an allowlist entry that no longer exists
   fails too (the list can only shrink). The orchestration that combined physics and assessment (legacy merged record,
   sweep, closure / UQ / comparison flags, F7/F8 design-gate runners, deprecated shims) moved to abep_sim/programme/.
   Because a programme module imports the assessment layer, a physics import of abep_sim.programme is a TRANSITIVE
   assessment dependency: those edges are listed the same way in PROGRAMME_IMPORT_ALLOWLIST (can only shrink).
2. No read of docs/requirements/** or docs/decisions/**: a forbidden path (string constant, or a module name bound to
   one) inside a reader call (open / read_text / json.load / Path / ...) fails. The same strings used purely as
   provenance labels (assigned to a constant, placed in a dict / tuple / f-string) are allowed.
3. No RFP clause id / RVM row id used for computation: a clause / row id (or a name bound to one) inside a comparison,
   as a subscript key, or as the key of .get() / .index() / .count() / .startswith() fails; ids as labels are allowed.
4. Runtime: system.physics_closure (the raw-physics entry) runs, on the parametric, gas-path, plasma and engineering
   paths, in a fresh interpreter whose config root has NO requirements/ directory, with abep_sim.assessment made
   unimportable and an audit hook that fails on any open() under docs/requirements, docs/decisions or
   config/requirements; its output carries no assessment keys.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATH_PREFIXES = ("docs/requirements/", "docs/decisions/")
FORBIDDEN_SEGMENT_PAIRS = (("docs", "requirements"), ("docs", "decisions"))
READERS = {"open", "read_json", "_read_json", "read_text", "read_bytes", "load", "loads", "Path", "load_json",
           "spec_from_file_location", "SourceFileLoader", "exec_module", "glob", "rglob", "iterdir", "listdir", "walk"}
CLAUSE_RE = re.compile(r"\b(RFP-P\d+-\d+|RVM-\d+)\b")
LOOKUP_METHODS = {"get", "index", "count", "startswith", "endswith", "pop", "setdefault"}

# (module, enclosing function or "<module>", imported assessment module) -> reason. Frozen at the A9.22 G1 completion
# with 13 entries; shrunk to 1 by the programme-layer split (abep_sim/programme/). May only shrink.
ASSESSMENT_IMPORT_ALLOWLIST = {
    ("abep_sim/archengine.py", "rfp_preset", "abep_sim.assessment.arch_constraints"):
        "compatibility wrapper (one lazy delegation, no computation): the owner-constraint preset is built by the "
        "assessment layer (arch_constraints.design_constraints). `def rfp_preset` must stay in archengine.py because "
        "docs/traceability/rtm_v1.json references abep_sim/archengine.py::rfp_preset (tests/test_traceability.py "
        "resolves it) and the RTM is sha256-pinned by the immutable subsystem maturity v1/v2 records",
}

# Physics -> programme-layer import edges (transitive assessment dependencies; module-level or lazy). May only shrink.
PROGRAMME_IMPORT_ALLOWLIST = {
    ("abep_sim/system.py", "evaluate", "abep_sim.programme.closure"):
        "compatibility entry delegating to programme.closure.evaluate: the immutable upstream ICD v1 names "
        "abep_sim.system.evaluate (byte-pinned by H2-3 v1 / subsystem maturity records) and rtm_v1 references "
        "abep_sim/system.py::evaluate; tests/fixtures/make_evaluate_identity_fixture*.py call it by path",
    ("abep_sim/__init__.py", "__getattr__", "abep_sim.programme.closure"):
        "lazy package-level public name abep_sim.evaluate (unchanged public API)",
    ("abep_sim/__init__.py", "__getattr__", "abep_sim.programme"):
        "lazy package-level public names abep_sim.run_grid / summarize (sweep, unchanged public API)",
    ("abep_sim/__main__.py", "<module>", "abep_sim.programme.sweep"): "CLI `python -m abep_sim` = the sweep CLI",
    ("abep_sim/arch_compare.py", "main", "abep_sim.programme.arch_compare"):
        "documented CLI `python -m abep_sim.arch_compare run` (HARNESS.md) writes the full comparison record",
    ("abep_sim/sizing.py", "<module>", "abep_sim.programme.closure"):
        "legacy sizing study: reads the merged record's rfp_compliant / abep_closed / chk_* flags",
    ("abep_sim/thresholds.py", "<module>", "abep_sim.programme.closure"):
        "legacy PDR-1 threshold study: P(technical_closed) from the merged record",
    ("abep_sim/uncertainty.py", "<module>", "abep_sim.programme.closure"):
        "legacy UQ study: P(rfp_compliant / abep_closed / technical_*) and ic_thruster from the merged record",
    ("abep_sim/uq6.py", "<module>", "abep_sim.programme.closure"):
        "legacy phase-6 UQ: technical_compliant from the merged record (mission_ok_rom)",
    ("abep_sim/mission_uq.py", "<module>", "abep_sim.programme.closure"):
        "legacy mission UQ: chk_thrust_air_ge_req from the merged record",
}


def _physics_modules():
    for p in sorted((ROOT / "abep_sim").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("abep_sim/assessment/", "abep_sim/programme/")) or rel == "abep_sim/configuration.py":
            continue
        yield rel, ast.parse(p.read_text(encoding="utf-8"))


def _package(rel: str) -> list[str]:
    return rel[:-3].split("/")[:-1]        # abep_sim/design/x.py -> ["abep_sim", "design"]


def _resolve(rel: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    base = _package(rel)[: len(_package(rel)) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _parents(tree):
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    return par


def _enclosing_function(node, par) -> str:
    while node in par:
        node = par[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<module>"


def _layer_imports(pkg: str):
    found = set()
    for rel, tree in _physics_modules():
        par = _parents(tree)
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.ImportFrom):
                m = _resolve(rel, n)
                mods = [m] + [f"{m}.{a.name}" for a in n.names]
            elif isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            hits = sorted({m for m in mods if m == pkg or m.startswith(pkg + ".")}, key=len)
            if hits:
                found.add((rel, _enclosing_function(n, par), hits[0], n.lineno))
    return found


def _assessment_imports():
    return _layer_imports("abep_sim.assessment")


def _allowed(rel, fn, mod, allowlist=None):
    allowlist = ASSESSMENT_IMPORT_ALLOWLIST if allowlist is None else allowlist
    return (rel, fn, mod) in allowlist or \
        any(r == rel and f == "*" and mod.startswith(m) for (r, f, m) in allowlist)


def _check_layer(pkg, allowlist, what):
    found = _layer_imports(pkg)
    bad = sorted(f"{rel}:{ln} ({fn}) imports {mod}" for rel, fn, mod, ln in found
                 if not _allowed(rel, fn, mod, allowlist))
    assert not bad, f"physics module imports {pkg} outside the frozen {what} allowlist: {bad}"
    # the allowlist only shrinks: every entry must still correspond to a real import
    stale = [k for k in allowlist
             if not any(rel == k[0] and (k[1] in ("*", fn)) and mod.startswith(k[2]) for rel, fn, mod, _ in found)]
    assert not stale, f"allowlist entries without a matching import (remove them): {stale}"


def test_physics_modules_do_not_import_the_assessment_layer():
    _check_layer("abep_sim.assessment", ASSESSMENT_IMPORT_ALLOWLIST, "compatibility")
    assert len(ASSESSMENT_IMPORT_ALLOWLIST) <= 1                  # shrunk from 13 by the programme-layer split


def test_physics_modules_import_the_programme_layer_only_through_listed_edges():
    """abep_sim.programme imports the assessment layer, so a physics -> programme import is a transitive assessment
    dependency; only the listed compatibility / legacy-study edges exist, and the design layer has none."""
    _check_layer("abep_sim.programme", PROGRAMME_IMPORT_ALLOWLIST, "programme-edge")
    assert not [k for k in PROGRAMME_IMPORT_ALLOWLIST if k[0].startswith("abep_sim/design/")]
    assert not [k for k in ASSESSMENT_IMPORT_ALLOWLIST if k[0].startswith("abep_sim/design/")]


def test_programme_layer_is_not_imported_at_module_level_by_physics_closure_modules():
    """The raw physics path (system, archengine, mission5, golden, uq_modular) carries no module-level programme
    import; system.evaluate's delegation is lazy (function level)."""
    for rel in ("abep_sim/system.py", "abep_sim/archengine.py", "abep_sim/mission5.py", "abep_sim/golden.py",
                "abep_sim/uq_modular.py", "abep_sim/arch_compare.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for n in tree.body:
            if isinstance(n, ast.ImportFrom):
                assert not _resolve(rel, n).startswith(("abep_sim.programme", "abep_sim.assessment")), (rel, n.lineno)


def test_raw_physics_entry_module_imports_no_assessment_at_module_level():
    tree = ast.parse((ROOT / "abep_sim/system.py").read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.ImportFrom):
            assert not _resolve("abep_sim/system.py", n).startswith("abep_sim.assessment")
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "physics_closure")
    for n in ast.walk(fn):
        if isinstance(n, ast.ImportFrom):
            assert not _resolve("abep_sim/system.py", n).startswith("abep_sim.assessment"), n.lineno


def _forbidden_str(v) -> bool:
    return isinstance(v, str) and v.lstrip("./").startswith(FORBIDDEN_PATH_PREFIXES)


def _forbidden_names(tree) -> set[str]:
    """Module-level names bound to a forbidden path string (provenance labels; reading through them is forbidden)."""
    out = set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and _forbidden_str(n.value.value):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        if isinstance(n, ast.AnnAssign) and isinstance(n.value, ast.Constant) and _forbidden_str(n.value.value) \
                and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return out


def _call_name(node: ast.Call):
    f = node.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)


def test_physics_modules_never_read_requirements_or_decisions():
    bad = []
    for rel, tree in _physics_modules():
        names = _forbidden_names(tree)
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and _call_name(n) in READERS):
                continue
            consts = [x.value for x in ast.walk(n) if isinstance(x, ast.Constant) and isinstance(x.value, str)]
            hit = any(_forbidden_str(c) for c in consts) or \
                any(isinstance(x, ast.Name) and x.id in names for x in ast.walk(n)) or \
                any(a in consts and b in consts for a, b in FORBIDDEN_SEGMENT_PAIRS)
            if hit:
                bad.append(f"{rel}:{n.lineno}")
    assert not bad, f"physics module reads docs/requirements or docs/decisions: {sorted(set(bad))}"


def test_provenance_labels_remain_allowed():
    """The checker must not flag label-only uses (guards against an over-broad rule)."""
    src = ('REG = "docs/requirements/rfp_official/rfp_registration_v1.json"\n'
           'META = {"source": REG, "decision": "docs/decisions/OD_x.json", "clause": "RFP-P18-06"}\n')
    tree = ast.parse(src)
    assert _forbidden_names(tree) == {"REG"}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) in READERS]
    assert not _clause_computation_uses("x.py", tree)
    bad = ast.parse('import json\nREG = "docs/requirements/a.json"\nd = json.load(open(REG))\n'
                    'k = d["RVM-04"]\nif x == "RFP-P18-06": pass\n')
    assert {n.lineno for n in ast.walk(bad) if isinstance(n, ast.Call) and _call_name(n) in READERS} == {3}
    assert len(_clause_computation_uses("x.py", bad)) == 2


def _clause_names(tree) -> set[str]:
    out = set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) \
                and CLAUSE_RE.search(n.value.value):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    return out


def _clause_computation_uses(rel, tree):
    par = _parents(tree)
    names = _clause_names(tree)
    bad = []
    for n in ast.walk(tree):
        is_id = (isinstance(n, ast.Constant) and isinstance(n.value, str) and CLAUSE_RE.search(n.value)) or \
            (isinstance(n, ast.Name) and n.id in names and isinstance(n.ctx, ast.Load))
        if not is_id:
            continue
        p = par.get(n)
        if isinstance(p, ast.Compare) or (isinstance(p, ast.Subscript) and p.slice is n) or \
                (isinstance(p, ast.Call) and n in p.args and isinstance(p.func, ast.Attribute)
                 and p.func.attr in LOOKUP_METHODS):
            bad.append(f"{rel}:{n.lineno}")
    return bad


def test_physics_modules_do_not_compute_with_clause_ids():
    bad = []
    for rel, tree in _physics_modules():
        bad += _clause_computation_uses(rel, tree)
    assert not bad, f"RFP clause / RVM row id used for computation in a physics module: {bad}"


# ------------------------------------------------------------------------------------------------ runtime check
RUNNER = r'''
import builtins, importlib.abc, json, os, sys
sys.path.insert(0, sys.argv[1])
BAD = ("/docs/requirements/", "/docs/decisions/", "/config/requirements/")
opened = []

def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0]).replace(os.sep, "/")
        if any(b in p for b in BAD):
            raise PermissionError(f"physics layer opened {p}")

sys.addaudithook(hook)

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "abep_sim.assessment" or name.startswith("abep_sim.assessment."):
            raise ImportError(f"physics layer imported {name}")
        return None

sys.meta_path.insert(0, Block())
from abep_sim.intake import IntakeParams, CompressorParams
from abep_sim.system import Config, physics_closure
tp = {"accommodation": 0.8, "use_tpmc": True, "L_over_d": 5}
cfgs = [
    Config("hall_1stage", 200, "mean", IntakeParams(area_m2=1.5), CompressorParams(ratio=500), vd_V=250),
    Config("hall_ecr", 200, "mean", IntakeParams(area_m2=0.5, **tp), CompressorParams(ratio=2000), vd_V=300,
           gaspath_physics=True),
    Config("hall_1stage", 200, "mean", IntakeParams(area_m2=0.7, **tp), CompressorParams(ratio=2000), vd_V=275,
           gaspath_physics=True, plasma_physics=True, engineering_physics=True, hall_L_m=0.20, hall_shielding=0.03,
           hall_wall_mm=6.0, blade_coating_um=50, xe_aug_hours=500),
]
out = []
for c in cfgs:
    r = physics_closure(c)
    out.append({"keys": sorted(r), "ao_fluence_basis_h": r["ao_fluence_basis_h"], "schema": r["raw_schema_version"],
                "eng_R_mission_h": r.get("eng_R_mission_h")})
assert not any(m == "abep_sim.assessment" or m.startswith("abep_sim.assessment.") for m in sys.modules)
assert "abep_sim.configuration" in sys.modules
print(json.dumps(out))
'''


def test_physics_closure_runs_with_requirements_hidden(tmp_path):
    cfg_root = tmp_path / "config"
    shutil.copytree(ROOT / "config", cfg_root)
    shutil.rmtree(cfg_root / "requirements")
    assert not (cfg_root / "requirements").exists()
    script = tmp_path / "run_physics.py"
    script.write_text(RUNNER, encoding="utf-8")
    env = {**os.environ, "ABEP_CONFIG_ROOT": str(cfg_root), "MPLBACKEND": "Agg"}
    res = subprocess.run([sys.executable, str(script), str(ROOT)], cwd=tmp_path, env=env, capture_output=True,
                         text=True, timeout=900)
    assert res.returncode == 0, res.stderr[-3000:]
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert len(out) == 3
    from abep_sim.assessment import FORBIDDEN_RAW_PREFIXES, FORBIDDEN_RAW_KEYS
    for r in out:
        assert r["schema"] == "raw_closure_v2" and r["ao_fluence_basis_h"] == 26280.0
        assert not [k for k in r["keys"] if k.startswith(FORBIDDEN_RAW_PREFIXES) or k in FORBIDDEN_RAW_KEYS]
    assert out[2]["eng_R_mission_h"] == 26280.0


def test_requirements_hidden_breaks_the_design_constraint_seam(tmp_path):
    """Control: the hidden-requirements setup is effective (the design seam, which does read the snapshot, fails
    closed there), so the physics run above genuinely ran without it."""
    cfg_root = tmp_path / "config"
    shutil.copytree(ROOT / "config", cfg_root)
    shutil.rmtree(cfg_root / "requirements")
    from abep_sim import configuration as cfg
    with pytest.raises(cfg.ConfigurationError):
        cfg.load_engineering_constraints(cfg_root)
    assert cfg.load_operating_inputs(cfg_root)["mission_hours"] == 26280.0
