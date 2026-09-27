# Packaging and installability (lane H2, owner decision 2026-09-27)

Scope: packaging only. No physics, frozen data, goldens, chemistry, pre-registration or campaign record changed; no module
moved; `hallthruster_bridge/` is not packaged. Dependencies are unchanged (see *Owner questions*).

## What changed

| file | change |
|---|---|
| `pyproject.toml` | `requires-python = ">=3.11"` (was `>=3.10`; the code uses `tomllib` and `requirements-lock.txt` — numpy 2.4.4, scipy 1.17.1, pandas 3.0.2 — needs 3.11; CI runs 3.11). Explicit setuptools discovery: `[tool.setuptools.packages.find] include = ["abep_sim", "abep_sim.*"], namespaces = false` (replaces flat-layout auto-discovery, which failed with *"Multiple top-level packages discovered in a flat-layout: ['abep_sim', 'hallthruster_bridge']"*). `[tool.setuptools.package-data] abep_sim = ["data/*.json", "data/*.csv", "data/rates/*.dat", "data/rates/*.md"]`. |
| `MANIFEST.in` | new: sdist carries `abep_sim/data/**` (json, csv, dat, md), README, lock file. |
| `.github/workflows/ci.yml` | both jobs: `python -m pip install --no-deps -e .` after the lock-file install; the `PYTHONPATH: ${{ github.workspace }}` workaround removed. pymsis present/absent legs unchanged. Golden step untouched (lane H3). |
| `scripts/install_and_test.sh` | checks Python >= 3.11 (`PYTHON=` selects the interpreter), lock install, `pip install --no-deps -e .`, `pytest -q tests` (or the pytest args given), then gates on `python -m abep_sim.golden check` printing `OK`. |
| `tests/test_packaging.py` | requires-python >= 3.11; explicit discovery; `setuptools.find_packages` with the configured include finds exactly the `abep_sim*` packages that exist; every file under `abep_sim/data` matches a package-data glob; MANIFEST.in covers the data extensions; CI installs lock then `--no-deps -e .` and sets no `PYTHONPATH`. Pure file inspection, skip-free, < 0.2 s. |

Why `--no-deps` for the editable install: `requirements-lock.txt` is the dependency source of truth, and `pyproject.toml`
still lists `pymsis>=0.13` as a hard dependency; a plain `pip install -e .` in the pymsis-absent leg would re-install
pymsis and defeat gate 1's leg. `pip check` therefore reports "abep-sim 0.1.0 requires pymsis, which is not installed" in a
no-pymsis environment; that is expected until the owner question below is decided.

## What is (and is not) in the distribution

* Package: `abep_sim` only (no subpackages today; `abep_sim.*` is included so a future subpackage is picked up).
  Console script `abep-sim = abep_sim.sweep:main`.
* Package data: all 8 files under `abep_sim/data` — `atmosphere_msis21_v1.{csv,json}`, `intake_surface_v1.{csv,json}`,
  `golden_v1.json`, `rates/{PROVENANCE.md, elastic_N2.dat, ionization_N2_N2+.dat}`. These are located at run time via
  `os.path.dirname(__file__)/data`, so they resolve inside `site-packages` for a wheel install.
* setuptools prints a "Package 'abep_sim.data' is absent from the `packages` configuration" warning when building. It is
  benign here: `abep_sim/data` is a data directory, not an importable package (`namespaces = false`), and the files are
  shipped as package data (verified in the wheel listing below).
* **Repository-coupled modules.** Several `abep_sim` modules read repository resources that are not part of the package,
  located relative to the source tree as `os.path.dirname(os.path.dirname(__file__))` (= repository root):
  `hall_map` (`hallthruster_bridge/hall_map_schema_v1.json`, read **at import**), `hall_ensemble`
  (`hallthruster_bridge/ensemble/transport_ensemble_v0.json`), `thermal_life` (`schemas/thermal_life/*`,
  `hallthruster_bridge/hall_map_schema_v1.json`), `hard_gates` (`docs/architecture_comparison/hard_gates`,
  `schemas/architecture_comparison`), `cathode_integration` (`docs/architecture_comparison/cathode_integration`),
  `mass_bom` and `arch_compare` (repository root). With the editable install these resolve exactly as when running from
  the repository root (the import path is the checkout), so behaviour is identical to the former `PYTHONPATH` setup. In a
  wheel installed outside a checkout, `abep_sim.hall_map` and `abep_sim.arch_compare` (which imports it) fail at import
  with `FileNotFoundError`; the other 43 modules import. The wheel therefore supports the core chain (frozen atmosphere,
  intake, gas path, source plasma, architecture closure, mission, golden check); the Hall-map / architecture-comparison
  layer requires a repository checkout. This is documented, not changed (lane scope).

## Acceptance transcript (2026-09-27, Python 3.11.15, scratch venvs under the session scratchpad, worktree at base fe1b8d1 + this change)

1. **Editable install.** Fresh venv → `pip install -r requirements-lock.txt` → `pip install -e .` (succeeds; previously
   failed with the flat-layout error) → from a directory outside the repo: `import abep_sim` resolves to the checkout's
   `abep_sim/__init__.py`; `abep-sim --help` prints usage. `pip freeze` = the lock versions plus their transitive deps.
2. **Full suite once (editable venv, no PYTHONPATH):** `python -m pytest -q tests` →
   `1170 passed, 5 skipped, 1 xfailed in 569.03s` — rule-9 outcome (5 SUPERSEDED skips in `tests/test_sim.py`, strict xfail
   `test_v16_blind_validation_p5_nitrogen`). `python -m abep_sim.golden check` → `OK`. `git status` afterwards: only the
   files of this change (`*.egg-info` is git-ignored).
3. **Wheel/sdist.** `python -m build` on a clean copy of the tracked tree → `abep_sim-0.1.0-py3-none-any.whl` and
   `abep_sim-0.1.0.tar.gz`. Wheel contents: `abep_sim/*.py` + the 8 data files + dist-info; nothing from
   `hallthruster_bridge/`, `tests/`, `scripts/`. sdist contains `abep_sim/data/**`.
4. **Wheel install (pymsis present).** Fresh venv → lock install → `pip install <wheel>` → from a directory outside the
   repo: `abep_sim` loads from `site-packages`; `importlib.resources.files("abep_sim")/"data"` lists the 5 data files and
   the 3 `rates/` files; frozen atmosphere loads (380 rows; `atmosphere(200 km)` ρ = 2.778e-10 kg/m³);
   `golden.GOLDEN_FILE` is inside `site-packages`; `python -m abep_sim.golden check` → `OK`.
5. **Wheel install (pymsis absent, gate 1).** Fresh venv → lock without the `pymsis` line → `pip install --no-deps
   <wheel>` → same checks; `pymsis importable: False`; `python -m abep_sim.golden check` → `OK`.
6. **`scripts/install_and_test.sh`** run on a clean copy of the tracked tree with `PYTHON=python3.11` and
   `tests/test_packaging.py tests/test_repo_integrity.py` → `18 passed`, golden `OK`. With `PYTHON=python3.10` it stops
   with "abep-sim needs Python >= 3.11 …".

## Owner questions (not changed here)

1. **pymsis as a hard dependency.** `pyproject.toml` lists `pymsis>=0.13` in `dependencies` although gate 1 requires the
   simulator to run without it (the frozen NRLMSIS dataset is the default; live MSIS only when asked), and an
   `[msis]` extra already exists. Recommended: move it to the `[msis]` extra only (`dependencies` without pymsis;
   `pip install -e .[msis]` for live MSIS). Not required for the documented no-pymsis install, which works via the lock
   file + `--no-deps` (CI, `install_and_test.sh`), so it was left unchanged.
2. **Wheel-only use of the Hall-map layer.** Should `hall_map_schema_v1.json` (and the other repository resources above)
   become package data, or should `abep_sim` remain "checkout required" for those modules? Either needs moving or
   duplicating files under `hallthruster_bridge/`/`schemas/`, which is outside this lane.
3. **Stale text outside this lane's allowed paths:** `docs/ci/CI.md` still says "No `pip install -e .`" (§ pymsis matrix)
   and lists the flat-layout failure as open point 1; the `PYTHON_VERSION` comment in `ci.yml` still says pyproject has
   ">= 3.10". Both should be updated by the owner of those sections.
