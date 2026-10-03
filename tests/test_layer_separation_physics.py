"""A9.22 layer separation (owner decisions 2026-10-03, docs/decisions/OD_2026_10_03_A9_22_*): the physics layer.

Physics modules = every module under abep_sim/ except abep_sim/assessment/** and abep_sim/configuration.py (the
configuration loader is the one place that opens config/requirements/). For them:

1. AST import graph: no import from abep_sim.assessment. The pre-existing compatibility / orchestration call sites
   (legacy merged outputs kept for existing tools per owner item 6, deprecated shims, design-layer optimisers that call
   the assessment gates) are listed EXPLICITLY in ASSESSMENT_IMPORT_ALLOWLIST with their reason; any new import fails,
   and an allowlist entry that no longer exists fails too (the list can only shrink).
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

# (module, enclosing function or "<module>", imported assessment module) -> reason. Frozen at the A9.22 G1 completion;
# may only shrink. Every entry is a compatibility / orchestration call site, never the raw physics closure itself.
ASSESSMENT_IMPORT_ALLOWLIST = {
    ("abep_sim/system.py", "evaluate", "abep_sim.assessment"):
        "legacy merged dict (raw closure + assessment) kept for existing tools (owner item 6); physics_closure is clean",
    ("abep_sim/sweep.py", "<module>", "abep_sim.assessment"):
        "sweep orchestration writes raw + assessment + legacy merged tables",
    ("abep_sim/sweep.py", "main", "abep_sim.assessment"): "sweep CLI writes the requirement-pointer table",
    ("abep_sim/sweep.py", "main", "abep_sim.assessment.closure_checks"): "sweep CLI RVM source label",
    ("abep_sim/arch_compare.py", "<module>", "abep_sim.assessment"): "architecture comparison tool (assessment flags)",
    ("abep_sim/archengine.py", "rfp_preset", "abep_sim.assessment.arch_constraints"):
        "compatibility wrapper: the preset is built by the assessment layer",
    ("abep_sim/archengine.py", "close_architecture", "abep_sim.assessment.arch_constraints"):
        "closure_constraint_flags appended to the architecture result (assessment flags)",
    ("abep_sim/uq_modular.py", "evaluate_sample", "abep_sim.assessment.arch_constraints"): "UQ success flag (assessment)",
    ("abep_sim/design/owner_state.py", "<module>", "abep_sim.assessment.design_gates"): "deprecated re-export shim",
    ("abep_sim/design/upstream_a9_13.py", "__getattr__", "abep_sim.assessment"): "deprecated import shim",
    ("abep_sim/design/plenum_feed.py", "*", "abep_sim.assessment"): "HC-12 ripple assessment (design-layer caller)",
    ("abep_sim/design/architecture_optimizer.py", "*", "abep_sim.assessment"):
        "design-layer optimiser applies the hard-constraint / power-gate assessment",
    ("abep_sim/design/robust_optimizer.py", "*", "abep_sim.assessment"):
        "design-layer robust optimiser applies the assessment gates",
}


def _physics_modules():
    for p in sorted((ROOT / "abep_sim").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("abep_sim/assessment/") or rel == "abep_sim/configuration.py":
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


def _assessment_imports():
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
            hits = sorted({m for m in mods if m == "abep_sim.assessment" or m.startswith("abep_sim.assessment.")},
                          key=len)
            if hits:
                found.add((rel, _enclosing_function(n, par), hits[0], n.lineno))
    return found


def _allowed(rel, fn, mod):
    return (rel, fn, mod) in ASSESSMENT_IMPORT_ALLOWLIST or \
        any(r == rel and f == "*" and mod.startswith(m) for (r, f, m) in ASSESSMENT_IMPORT_ALLOWLIST)


def test_physics_modules_do_not_import_the_assessment_layer():
    found = _assessment_imports()
    bad = sorted(f"{rel}:{ln} ({fn}) imports {mod}" for rel, fn, mod, ln in found if not _allowed(rel, fn, mod))
    assert not bad, "physics module imports abep_sim.assessment outside the frozen compatibility allowlist: " \
                    f"{bad}"
    # the allowlist only shrinks: every entry must still correspond to a real import
    stale = [k for k in ASSESSMENT_IMPORT_ALLOWLIST
             if not any(rel == k[0] and (k[1] in ("*", fn)) and mod.startswith(k[2]) for rel, fn, mod, _ in found)]
    assert not stale, f"allowlist entries without a matching import (remove them): {stale}"


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


def test_requirements_hidden_breaks_only_the_requirements_loaders(tmp_path):
    """Control: the hidden-requirements setup is effective (the requirements-snapshot loaders fail closed there), so
    the physics run above genuinely ran without it; since A9.23 both seams (operating inputs, design engineering
    constraints) read config/constraints and load without the snapshot."""
    cfg_root = tmp_path / "config"
    shutil.copytree(ROOT / "config", cfg_root)
    shutil.rmtree(cfg_root / "requirements")
    from abep_sim import configuration as cfg
    with pytest.raises(cfg.ConfigurationError):
        cfg.load_rfp_constraints_compat(cfg_root)
    with pytest.raises(cfg.ConfigurationError):
        cfg.assessment_configuration(cfg_root)
    assert cfg.load_operating_inputs(cfg_root)["mission_hours"] == 26280.0
    assert cfg.load_engineering_constraints(cfg_root)["power_max_W"] == 1500.0
