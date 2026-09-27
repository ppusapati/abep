"""Packaging / installability contract (docs/ci/PACKAGING.md, lane H2).

pyproject.toml must (i) require Python >= 3.11 (tomllib, locked environment), (ii) configure setuptools package discovery
explicitly (flat-layout auto-discovery refuses abep_sim + hallthruster_bridge), distributing abep_sim only, and
(iii) ship every file under abep_sim/data (frozen atmosphere, intake surface, goldens, rate tables) as package data.
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


def test_package_data_covers_abep_sim_data(pyproject):
    globs = pyproject["tool"]["setuptools"]["package-data"]["abep_sim"]
    files = _data_files()
    for must in ("data/atmosphere_msis21_v1.json", "data/atmosphere_msis21_v1.csv", "data/intake_surface_v1.json",
                 "data/intake_surface_v1.csv", "data/golden_v1.json", "data/rates/PROVENANCE.md"):
        assert must in files, must
    uncovered = [f for f in files if not any(fnmatch.fnmatchcase(f, g) for g in globs)]
    assert not uncovered, f"abep_sim/data files not declared as package data: {uncovered}"


def test_manifest_in_carries_data():
    with open(os.path.join(ROOT, "MANIFEST.in")) as f:
        lines = [ln.split() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    rec = [ln for ln in lines if ln[:2] == ["recursive-include", "abep_sim/data"]]
    assert rec, "MANIFEST.in must include abep_sim/data for the sdist"
    exts = {os.path.splitext(f)[1] for f in _data_files()}
    assert exts <= {p.lstrip("*") for p in rec[0][2:]}, exts


def test_ci_uses_editable_install_without_pythonpath():
    """CI installs the lock file, then abep_sim editable with --no-deps (keeps the pymsis-absent leg pymsis-free)."""
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
