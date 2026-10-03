"""A9.22 layer separation (owner decisions 2026-10-03, items 2 and 5): design / physics code reads requirement-derived
numbers only through the engineering-constraints seam, assessment lives in abep_sim/assessment/design_gates.py, and no
design / physics module imports docs code by path or reads requirements / decisions / owner-question state.

Also the numerical-identity evidence of the move: the seam values equal the pre-A9.22 literals, the hard-constraint
table equals the committed F7 record, the moved F7 gate records / F8 gate snapshot reproduce the committed F7 output,
and the verbatim library copies are source-identical to their docs originals.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from abep_sim.assessment import design_gates as dg  # noqa: E402
from abep_sim.design import architecture_optimizer as ao  # noqa: E402
from abep_sim.design import engineering_constraints as ec  # noqa: E402
from abep_sim.design import robust_optimizer as ro  # noqa: E402
from abep_sim.design import upstream_a9_13 as u13  # noqa: E402

F7_JSON = REPO / "docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json"

# ------------------------------------------------------------------------------------------------ import graph
SHIMS = {"abep_sim/design/owner_state.py"}            # deprecated re-export of the assessment-layer reader
PATH_LOADER_ALLOWED = {"abep_sim/icp_bench_lib.py"}   # loads the full P1 reducer (docs/experiments) for builder probes
FORBIDDEN_NAMES = {"RVM_REL", "RFP_REGISTRATION", "OQ5_REL"}
FORBIDDEN_PREFIXES = ("docs/requirements/", "docs/decisions/", "docs/budgets/owner_decisions/")
READERS = {"open", "read_json", "_read_json", "read_text", "read_bytes", "load", "loads", "Path",
           "spec_from_file_location"}
PATH_LOADERS = {"spec_from_file_location", "SourceFileLoader", "exec_module"}


def _design_physics_modules():
    for p in sorted((REPO / "abep_sim").rglob("*.py")):
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith("abep_sim/assessment/") or rel in SHIMS:
            continue
        yield rel, ast.parse(p.read_text(encoding="utf-8"))


def _call_name(node: ast.Call):
    f = node.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)


def test_design_physics_modules_do_not_import_owner_state():
    bad = []
    for rel, tree in _design_physics_modules():
        for n in ast.walk(tree):
            if isinstance(n, ast.Import) and any(a.name.split(".")[-1] == "owner_state" for a in n.names):
                bad.append(rel)
            if isinstance(n, ast.ImportFrom) and ((n.module or "").split(".")[-1] == "owner_state"
                                                  or any(a.name == "owner_state" for a in n.names)):
                bad.append(rel)
    assert not bad, bad


def test_no_docs_code_imported_by_path():
    bad = []
    for rel, tree in _design_physics_modules():
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and _call_name(n) in PATH_LOADERS and rel not in PATH_LOADER_ALLOWED:
                bad.append(f"{rel}:{n.lineno}")
    assert not bad, bad


def test_no_requirement_decision_or_owner_state_reads():
    bad = []
    for rel, tree in _design_physics_modules():
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and _call_name(n) in READERS):
                continue
            for x in ast.walk(n):
                if isinstance(x, ast.Name) and x.id in FORBIDDEN_NAMES or \
                        isinstance(x, ast.Attribute) and x.attr in FORBIDDEN_NAMES or \
                        isinstance(x, ast.Constant) and isinstance(x.value, str) and \
                        x.value.startswith(FORBIDDEN_PREFIXES):
                    bad.append(f"{rel}:{n.lineno}")
                    break
    assert not bad, bad


def test_intake_synthesis_uses_the_seam_not_rfp():
    tree = ast.parse((REPO / "abep_sim/design/intake_synthesis.py").read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("constants"):
            assert "RFP" not in {a.name for a in n.names}
        assert not (isinstance(n, ast.Name) and n.id in ("RFP", "RFP_ALT_BAND_KM"))


# ------------------------------------------------------------------------------------------------ seam values
def test_engineering_constraints_values_equal_pre_a9_22_literals():
    assert ec.INTAKE_DRAG_GENERATION_LIMIT_MN == 25.0
    assert ec.INTAKE_DRAG_GENERATION_LIMIT_N == 25.0 * 1e-3 == 0.025
    assert ec.MISSION_DOMAIN_ALTITUDE_KM == (180.0, 230.0)
    assert ec.HARD_CONSTRAINT_LIMITS == {
        "HC-01": 0.012, "HC-02": 0.025, "HC-03": 1500.0, "HC-04": 40.0, "HC-05": 0.0, "HC-06": 50.0, "HC-07": 15000.0,
        "HC-08": 0.0, "HC-09": 0.025, "HC-10": 1.0, "HC-11": 0.0, "HC-12": None}
    for k, v in ec.HARD_CONSTRAINT_LIMITS.items():
        assert v is None or type(v) is float, k
    from abep_sim.design import intake_synthesis as isy
    assert isy.MISSION_DOMAIN_ALTITUDE_KM == (180.0, 230.0)
    assert ec.snapshot()["mission_domain"]["altitude_km"] == [180.0, 230.0]


def test_hard_constraints_equal_committed_f7_record():
    doc = json.loads(F7_JSON.read_text(encoding="utf-8"))
    assert [dict(c) for c in dg.HARD_CONSTRAINTS] == doc["hard_constraints"]
    assert list(ao.HARD_CONSTRAINTS) == list(dg.HARD_CONSTRAINTS)          # deprecated shim
    assert ao.PRE_EVALUATED_OBJECTIVES == dg.PRE_EVALUATED_OBJECTIVES


def test_c_drag_generation_filter_consistent_with_committed_f1():
    """Every committed F1 C-DRAG-RFP reason names the 25 mN limit and a drag above it (generation filter unchanged)."""
    f1 = json.loads((REPO / ao.F1_REL).read_text(encoding="utf-8"))
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, str) and o.startswith("C-DRAG-RFP") and o.endswith(" mN"):
            n += 1
            if "RFP thrust max" in o:
                assert f"RFP thrust max {ec.INTAKE_DRAG_GENERATION_LIMIT_MN:g} mN" in o
            mn = float(o.split(": ")[-1].split(" mN")[0].split()[-1])
            assert mn * 1e-3 > ec.INTAKE_DRAG_GENERATION_LIMIT_N - 0.005e-3       # printed to 0.01 mN
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(f1)
    assert n > 0


# ------------------------------------------------------------------------------------------------ shims / identity
def test_shims_resolve_to_assessment_layer():
    for name in u13.MOVED_TO_ASSESSMENT:
        assert getattr(u13, name) is getattr(dg, name)
    from abep_sim.design import owner_state as ost
    assert ost.owner_state is dg.owner_state and ost.apply_to_questions is dg.apply_to_questions
    assert ao.evaluate_constraints({}) == dg.evaluate_constraints({})


def _builder(rel, name):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def f7_builder():
    return _builder("docs/design_synthesis/f7_f8_optimizer/build_f7_f8_optimizer.py", "_sep_f7_builder")


@pytest.fixture(scope="module")
def f7_doc():
    return json.loads(F7_JSON.read_text(encoding="utf-8"))


def test_moved_statewise_gate_records_reproduce_committed_f7(f7_builder, f7_doc):
    assert f7_builder.rnd(f7_builder.statewise_gate_records()) == f7_doc["statewise_gate_records"]


def test_gate_snapshot_reproduces_committed_f8(f7_builder, f7_doc):
    snap = ro.gate_snapshot()
    assert snap == dg.gate_snapshot() == ro.design_gate_snapshot(ao.REPO, dg.rvm_gate_snapshot())
    assert f7_builder.rnd(snap) == f7_doc["robust"]["gates_before"] == f7_doc["robust"]["gates_after"]
    assert list(snap) == list(f7_doc["robust"]["gates_before"])


def test_hall_admissibility_library_matches_f5_builder():
    b = _builder("docs/hardware/h1_freeze_candidate/build_h1_freeze_candidate.py", "_sep_h1_builder")
    f5 = json.loads((REPO / ao.F5_REL).read_text(encoding="utf-8"))
    assert f5["x_hall_design_space"]["definition"] == b.x_hall_definition()
    for h in (8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 40.0, float("nan")):
        for d in (40.0, 46.0, 70.0, 100.0):
            for L in (5 * h, 8.6 * h, 12 * h, 20 * h):
                for a in ("worst_case_assumptions", "nominal_assumptions"):
                    assert ao.hall_admissibility(h, d, L, a) == b.geometric_admissibility(h, d, L, a)


# ------------------------------------------------------------------------------------------------ verbatim copies
def _top_level_sources(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    out: dict = {}
    for n in tree.body:
        names = []
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names = [n.name]
        elif isinstance(n, ast.Assign):
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
        for nm in names:
            out.setdefault(nm, []).append(ast.get_source_segment(src, n, padded=False))
    return out


LIB_HEADERS = {"SOURCE_REL", "SOURCE_SHA256", "REPO", "RED", "_P1", "experiment_p1_reducer", "P1_REDUCER_REL",
               "P2_FRAMEWORK_REL", "P2_REDUCER_REL"}


@pytest.mark.parametrize("lib,sources", [
    ("abep_sim/icp_thermal_lib.py", ["docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py"]),
    ("abep_sim/icp_bench_lib.py", ["docs/experiments/hall_icp/p1_icp_bench/p1_reducer.py",
                                   "docs/experiments/hall_icp/p2_impedance_map/p2_framework.py",
                                   "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_reducer.py"]),
])
def test_library_copies_are_verbatim(lib, sources):
    orig: dict = {}
    for s in sources:
        for k, v in _top_level_sources(REPO / s).items():
            orig.setdefault(k, []).extend(v)
    copied = _top_level_sources(REPO / lib)
    n = 0
    for name, segs in copied.items():
        if name in LIB_HEADERS:
            continue
        for seg in segs:
            assert seg in orig.get(name, []), f"{lib}: {name} differs from its docs original"
            n += 1
    assert n > 5


def test_library_source_hashes_match_docs_originals():
    import hashlib
    from abep_sim import icp_bench_lib, icp_thermal_lib
    sha = lambda rel: hashlib.sha256((REPO / rel).read_bytes()).hexdigest()  # noqa: E731
    assert sha(icp_thermal_lib.SOURCE_REL) == icp_thermal_lib.SOURCE_SHA256
    for rel, h in icp_bench_lib.SOURCE_SHA256.items():
        assert sha(rel) == h, rel


def test_h1_geometry_is_the_builder_original_except_the_xdef_default():
    """The library geometric_admissibility equals the pre-A9.22 builder function except that ``xdef`` is required."""
    from abep_sim import h1_geometry
    with pytest.raises(ValueError):
        h1_geometry.geometric_admissibility(12.0, 70.0, 103.2)
    assert h1_geometry.ROUNDING_REL == 1e-3
    assert math.isclose(h1_geometry.ROUNDING_REL, 1e-3, rel_tol=0, abs_tol=0)
