# Packaging and installability (lane H2, owner decision 2026-09-27)

Scope: packaging only. No physics, frozen data, goldens, chemistry, pre-registration or campaign record changed; no module
moved; `hallthruster_bridge/` is not packaged. Dependencies were unchanged by lane H2; the later owner decision moving
`pymsis` to the `[msis]` extra is recorded in *Repository decisions batch (2026-09-27)* below.

## What changed

| file | change |
|---|---|
| `pyproject.toml` | `requires-python = ">=3.11"` (was `>=3.10`; the code uses `tomllib` and `requirements-lock.txt` — numpy 2.4.4, scipy 1.17.1, pandas 3.0.2 — needs 3.11; CI runs 3.11). Explicit setuptools discovery: `[tool.setuptools.packages.find] include = ["abep_sim", "abep_sim.*"], namespaces = false` (replaces flat-layout auto-discovery, which failed with *"Multiple top-level packages discovered in a flat-layout: ['abep_sim', 'hallthruster_bridge']"*). `[tool.setuptools.package-data] abep_sim = ["data/*.json", "data/*.csv", "data/rates/*.dat", "data/rates/*.md"]`. |
| `MANIFEST.in` | new: sdist carries `abep_sim/data/**` (json, csv, dat, md), README, lock file. |
| `.github/workflows/ci.yml` | both jobs: `python -m pip install --no-deps -e .` after the lock-file install; the `PYTHONPATH: ${{ github.workspace }}` workaround removed. pymsis present/absent legs unchanged. Golden step untouched (lane H3). |
| `scripts/install_and_test.sh` | checks Python >= 3.11 (`PYTHON=` selects the interpreter), lock install, `pip install --no-deps -e .`, `pytest -q tests` (or the pytest args given), then gates on `python -m abep_sim.golden check` printing `OK`. |
| `tests/test_packaging.py` | requires-python >= 3.11; explicit discovery; `setuptools.find_packages` with the configured include finds exactly the `abep_sim*` packages that exist; every file under `abep_sim/data` matches a package-data glob; MANIFEST.in covers the data extensions; CI installs lock then `--no-deps -e .` and sets no `PYTHONPATH`. Pure file inspection, skip-free, < 0.2 s. |

Why `--no-deps` for the editable install (as written by lane H2): `requirements-lock.txt` is the dependency source of
truth, and `pyproject.toml` then listed `pymsis>=0.13` as a hard dependency, so a plain `pip install -e .` in the
pymsis-absent leg would have re-installed pymsis. That second reason no longer holds (see the next section); the first
still does.

## What is (and is not) in the distribution

* Package: `abep_sim` only (no subpackages today; `abep_sim.*` is included so a future subpackage is picked up).
  Console script `abep-sim = abep_sim.sweep:main`.
* Package data: all 8 files under `abep_sim/data` — `atmosphere_msis21_v1.{csv,json}`, `intake_surface_v1.{csv,json}`,
  `golden_v1.json`, `rates/{PROVENANCE.md, elastic_N2.dat, ionization_N2_N2+.dat}`. These are located at run time via
  `os.path.dirname(__file__)/data`, so they resolve inside `site-packages` for a wheel install.
  (A9.18, 2026-10-01: `golden_v2.json` was added under the same `data/*.json` glob and is the file `golden check` reads;
  `golden_v1.json` stays shipped, unchanged, as history.)
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

## Repository decisions batch (2026-09-27)

Follow-on `fo_repo_decisions_batch` (trigger `T_PIVOT_REPO_DECISIONS_BATCH`; owner disposition `od_hardware_pivot`,
`docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` → `execution_directive_2026_09_27.new_workstreams`). Repository
governance only: no physics, frozen data, goldens, chemistry, pre-registration or campaign record changed.

### D1. `pymsis` moved to the `[msis]` extra (decided by the owner; implemented here)

| before | after |
|---|---|
| `dependencies = ["numpy", "pandas", "pyyaml", "matplotlib", "scipy", "pymsis>=0.13"]` | `dependencies = ["numpy", "pandas", "pyyaml", "matplotlib", "scipy"]` |
| `msis = ["pymsis"]` | `msis = ["pymsis>=0.13"]` (the version floor moves with it) |

* Live MSIS: `pip install -e ".[msis]"` (or the full lock file, which still pins `pymsis==0.13.0`). The frozen NRLMSIS
  dataset needs no pymsis (gate 1; CLAUDE.md rule 3: live MSIS only when asked).
* `requirements-lock.txt` is **unchanged** and remains the dependency source of truth (pinned versions of every hard
  dependency plus pymsis). `pip check` in a no-pymsis environment is now clean (it previously reported
  "abep-sim 0.1.0 requires pymsis, which is not installed").
* `tests/test_packaging.py`: `test_pymsis_only_in_msis_extra` (pymsis not in `dependencies`, only in `[msis]`; the other
  five hard dependencies unchanged) and `test_lock_file_still_pins_pymsis_and_every_hard_dependency`.

**Is CI's `--no-deps` still needed?** Not for gate 1 any more: without pymsis in `dependencies`, a plain
`pip install -e .` after the lock-minus-pymsis install pulls nothing (transcript below). It is **kept**, and `ci.yml` is
**not edited**, because it still does one job: it guarantees that the lock file is the *only* dependency source, so the
editable install can never resolve, add or upgrade a package the lock does not pin (e.g. if a future `dependencies` entry
is added to `pyproject.toml` without a matching lock line, CI fails at import instead of silently installing an
unpinned version). Editing `ci.yml` is therefore not necessary. `tests/test_packaging.py` keeps asserting the
lock-then-`--no-deps -e .` order. Stale wording left for the owner of those files: the `env:` comment in `ci.yml`
("pyproject.toml still lists pymsis as a hard dependency"), `docs/ci/CI.md` § *Editable install* ("keeps the
pymsis-absent leg free of pymsis") and *Open points* item 1 ("Open: `pymsis` is still a hard dependency"). They are
text only, outside this lane's allowed paths, and do not change behaviour.

**Acceptance check (2026-09-27, Python 3.11.15, fresh venv in the session scratchpad, worktree at base `926ebb0` + this
change):**

1. `pip install -r <requirements-lock.txt without the pymsis line>` → then **`pip install -e .` (plain, without
   `--no-deps`)** → "Installing collected packages: abep-sim" only. `pip freeze` afterwards: numpy 2.4.4, scipy 1.17.1,
   pandas 3.0.2, matplotlib 3.10.8, PyYAML 6.0.3, pytest 9.1.1 (the lock versions) and no pymsis;
   `importlib.util.find_spec("pymsis") is None` → `pymsis importable: False`; `pip check` → "No broken requirements found."
2. `pip install --dry-run -e ".[msis]"` in the same venv → "Would install abep-sim-0.1.0 pymsis-0.13.0" (the extra works).
3. From a directory outside the repository, in that venv: `python -m abep_sim.golden check` → `OK` (exit 0).
4. Tests run by this lane: `python -m pytest -q tests/test_packaging.py tests/test_ci_required_contexts.py
   tests/test_o4_disposition_matrix.py` only. The full suite was **not** re-run by this lane (the CPU is committed to the
   running pre-registered follow-on campaigns; the lane rules forbid it); CI runs it on the PR in both pymsis legs.

### D2. The golden CLI test stays in normal CI (decided by the owner; no change)

`tests/test_golden_cli.py` (exit status of `python -m abep_sim.golden check`: 0 on the unchanged tree, non-zero on a
perturbed copy) stays in the normal `python -m pytest -q tests` run of both `tests` legs. It gets **no** `slow` marker
and is not moved to a separate or optional job; no pytest marker configuration is added. It is therefore covered by the
required contexts `Tests + golden benchmarks (pymsis present|absent)` (`docs/ci/BRANCH_PROTECTION.md`). Nothing in the
repository changes for D2; this paragraph is the record.

### Milestones

These are repository-hygiene decisions. They support all three milestones (A conditional selection, B physics-backed
selection, C proposal/PDR freeze) only indirectly, by keeping gate 1 (clean-install reproducibility) and gate 6 (golden
benchmarks) mechanically enforced; they add no evidence for any architecture and change no milestone status.

## Owner questions (not changed here)

1. *(Decided 2026-09-27, see D1 above: pymsis moved to the `[msis]` extra.)*
2. **Wheel-only use of the Hall-map layer.** Should `hall_map_schema_v1.json` (and the other repository resources above)
   become package data, or should `abep_sim` remain "checkout required" for those modules? Either needs moving or
   duplicating files under `hallthruster_bridge/`/`schemas/`, which is outside this lane.
3. **Stale text outside this lane's allowed paths:** `docs/ci/CI.md` still says "No `pip install -e .`" (§ pymsis matrix)
   and lists the flat-layout failure as open point 1; the `PYTHON_VERSION` comment in `ci.yml` still says pyproject has
   ">= 3.10". Both should be updated by the owner of those sections.
