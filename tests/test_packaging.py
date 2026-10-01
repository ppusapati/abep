"""Packaging / installability contract (docs/ci/PACKAGING.md, lane H2).

pyproject.toml must (i) require Python >= 3.11 (tomllib, locked environment), (ii) configure setuptools package discovery
explicitly (flat-layout auto-discovery refuses abep_sim + hallthruster_bridge), distributing abep_sim only, and
(iii) ship every file under abep_sim/data (frozen atmosphere, intake surface, goldens, rate tables) as package data,
except the repository-only orbit-resolved dataset atmosphere_msis21_orbit_v1.* (A9.17 DATA_SIZE,
docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json: kept as repository evidence, excluded from the
installed wheel/sdist; no installed production module imports abep_sim.atmosphere_orbit), and
(iv) keep pymsis out of the hard dependencies: it lives only in the [msis] extra (owner decision 2026-09-27,
fo_repo_decisions_batch; gate 1 runs without it), while requirements-lock.txt stays the pinned dependency source.
Pure file inspection: no build, no install, no network.
"""
from __future__ import annotations

import fnmatch
import os
import tomllib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "abep_sim", "data")


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)


def test_requires_python_311(pyproject):
    spec = pyproject["project"]["requires-python"].replace(" ", "")
    assert spec == ">=3.11", spec


def _req_name(req: str) -> str:
    """Distribution name of a PEP 508 requirement string (normalised: lower case, '_'/'.' -> '-')."""
    import re
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req)
    assert m, req
    return re.sub(r"[-_.]+", "-", m.group(1)).lower()


def test_pymsis_only_in_msis_extra(pyproject):
    """Owner decision 2026-09-27: pymsis is an optional extra ([msis]), never a hard dependency, so a plain
    `pip install -e .` in a pymsis-free environment does not pull it (gate 1: frozen NRLMSIS dataset, no pymsis)."""
    proj = pyproject["project"]
    deps = [_req_name(r) for r in proj["dependencies"]]
    assert "pymsis" not in deps, proj["dependencies"]
    # The other hard dependencies are unchanged by this decision.
    assert sorted(deps) == sorted(["numpy", "pandas", "pyyaml", "matplotlib", "scipy"]), deps
    extras = proj["optional-dependencies"]
    assert [_req_name(r) for r in extras["msis"]] == ["pymsis"], extras["msis"]
    assert all("pymsis" not in [_req_name(r) for r in reqs] for name, reqs in extras.items() if name != "msis"), extras


def test_lock_file_still_pins_pymsis_and_every_hard_dependency(pyproject):
    """requirements-lock.txt remains the dependency source of truth: it pins every hard dependency and pymsis (the
    pymsis-present CI leg installs it from the lock; the absent leg filters the `pymsis` line)."""
    with open(os.path.join(ROOT, "requirements-lock.txt"), encoding="utf-8") as f:
        pinned = {_req_name(ln.split("==")[0]) for ln in (x.split("#")[0].strip() for x in f) if "==" in ln}
    deps = {_req_name(r) for r in pyproject["project"]["dependencies"]}
    assert deps <= pinned, sorted(deps - pinned)
    assert "pymsis" in pinned


def test_explicit_package_discovery(pyproject):
    st = pyproject["tool"]["setuptools"]
    assert "packages" in st, "package discovery must be configured explicitly (no flat-layout auto-discovery)"
    pk = st["packages"]
    if isinstance(pk, list):
        assert pk == ["abep_sim"], pk
    else:
        find = pk["find"]
        assert find.get("namespaces") is False, "abep_sim/data must not become an implicit namespace package"
        assert sorted(find["include"]) == ["abep_sim", "abep_sim.*"], find["include"]
        assert find.get("where", ["."]) == ["."]


def test_discovery_finds_exactly_abep_sim(pyproject):
    """What setuptools will package: abep_sim (+ abep_sim.* subpackages), never hallthruster_bridge/tests/scripts."""
    from setuptools import find_packages
    find = pyproject["tool"]["setuptools"]["packages"]["find"]
    found = find_packages(where=os.path.join(ROOT, find.get("where", ["."])[0]), include=find["include"],
                          exclude=find.get("exclude", ()))
    expected = sorted(
        os.path.relpath(d, ROOT).replace(os.sep, ".")
        for d, _dirs, files in os.walk(os.path.join(ROOT, "abep_sim"))
        if "__init__.py" in files)
    assert sorted(found) == expected, found
    assert expected[0] == "abep_sim"
    assert not any(p.split(".")[0] != "abep_sim" for p in found), found


def _data_files() -> list[str]:
    out = []
    for d, dirs, files in os.walk(DATA_DIR):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for fn in files:
            if fn.endswith((".pyc",)):
                continue
            out.append(os.path.relpath(os.path.join(d, fn), os.path.join(ROOT, "abep_sim")).replace(os.sep, "/"))
    return sorted(out)


# Repository-only data (A9.17 DATA_SIZE): never shipped in the wheel/sdist.
REPO_ONLY_GLOB = "data/atmosphere_msis21_orbit_v1*"
# A9.17 WINDS: the HWM14-wind atmosphere v2 is repository-only too.
REPO_ONLY_GLOB_V2 = "data/atmosphere_msis21_hwm14_orbit_v2*"
REPO_ONLY_GLOBS = (REPO_ONLY_GLOB, REPO_ONLY_GLOB_V2)
# Modules that are the accessors of repository-only data (they may reference atmosphere_orbit).
REPO_ONLY_MODULES = ("atmosphere_orbit.py", "atmosphere_orbit_v2.py")


def _repo_only(f: str) -> bool:
    return any(fnmatch.fnmatchcase(f, g) for g in REPO_ONLY_GLOBS)


def test_package_data_covers_abep_sim_data(pyproject):
    st = pyproject["tool"]["setuptools"]
    globs = st["package-data"]["abep_sim"]
    files = _data_files()
    for must in ("data/atmosphere_msis21_v1.json", "data/atmosphere_msis21_v1.csv", "data/intake_surface_v1.json",
                 "data/intake_surface_v1.csv", "data/golden_v1.json", "data/rates/PROVENANCE.md"):
        assert must in files, must
    uncovered = [f for f in files if not _repo_only(f) and not any(fnmatch.fnmatchcase(f, g) for g in globs)]
    assert not uncovered, f"abep_sim/data files not declared as package data: {uncovered}"


def test_orbit_dataset_excluded_from_distribution(pyproject):
    """A9.17 DATA_SIZE: the orbit-resolved dataset stays repository evidence (one canonical .csv.gz + manifest +
    design states) and is excluded from the installed package; the frozen orbit-averaged v1 files keep shipping."""
    st = pyproject["tool"]["setuptools"]
    globs = st["package-data"]["abep_sim"]
    repo_only = [f for f in _data_files() if _repo_only(f)]
    assert sorted(repo_only) == sorted([
        "data/atmosphere_msis21_orbit_v1.csv.gz", "data/atmosphere_msis21_orbit_v1.json",
        "data/atmosphere_msis21_orbit_v1_design_states.json", "data/atmosphere_msis21_orbit_v1_design_states_v2.json",
        "data/atmosphere_msis21_hwm14_orbit_v2.csv.gz", "data/atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz",
        "data/atmosphere_msis21_hwm14_orbit_v2.json"]), repo_only
    shipped = [f for f in repo_only if any(fnmatch.fnmatchcase(f, g) for g in globs)]
    assert not shipped, f"repository-only files matched by package-data globs: {shipped}"
    with open(os.path.join(ROOT, "MANIFEST.in")) as f:
        lines = [ln.split() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    for g in REPO_ONLY_GLOBS:
        assert g in st["exclude-package-data"]["abep_sim"], g
        assert ["exclude", "abep_sim/" + g] in lines, g
    # runtime need check: no other abep_sim module imports the accessor of the excluded data
    pkg = os.path.join(ROOT, "abep_sim")
    for d, _dirs, fns in os.walk(pkg):
        for fn in fns:
            if fn.endswith(".py") and fn not in REPO_ONLY_MODULES:
                with open(os.path.join(d, fn), encoding="utf-8") as fh:
                    assert "atmosphere_orbit" not in fh.read(), fn


def test_manifest_in_carries_data():
    with open(os.path.join(ROOT, "MANIFEST.in")) as f:
        lines = [ln.split() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rec = [ln for ln in lines if ln[:2] == ["recursive-include", "abep_sim/data"]]
    assert rec, "MANIFEST.in must include abep_sim/data for the sdist"
    exts = {os.path.splitext(f)[1] for f in _data_files() if not _repo_only(f)}
    assert exts <= {p.lstrip("*") for p in rec[0][2:]}, exts


def test_ci_uses_editable_install_without_pythonpath():
    """CI installs the lock file, then abep_sim editable with --no-deps. Since pymsis moved to the [msis] extra, --no-deps is
    no longer what keeps the pymsis-absent leg pymsis-free (a plain `pip install -e .` does not pull it either); it is kept
    so that the lock file stays the only dependency source (docs/ci/PACKAGING.md, owner decision 2026-09-27)."""
    import yaml
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert "PYTHONPATH" not in (doc.get("env") or {})
    for job in ("integrity", "tests"):
        runs = [s.get("run", "") for s in doc["jobs"][job]["steps"]]
        inst = [r for r in runs if "requirements" in r and "pip install" in r]
        assert len(inst) == 1, job
        body = inst[0]
        assert "python -m pip install --no-deps -e ." in body, job
        assert body.index("requirements") < body.index("--no-deps -e ."), job
