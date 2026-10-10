# Parity report — C-ABEP_SIM_CONFIGURATION_PY v1

**Verdict: ADMITTED (PARITY_PASS)** under the preregistered decision rules of
`parity_prereg_v1.json` (sha256 `69cf94488ada482c50eb31e7f205a89be073e585eacd7859be76c28da594b236`, committed in `d7b51d8`).

Scope: the configuration loaders of `abep_sim/configuration.py` and the `config/**` builder
`scripts/config/build_config.py` (coupled group), ported to `crates/abep-config`.

| item | value |
|---|---|
| Python reference | `96db552`; reference files unchanged at scoring |
| Rust source at scoring | `b249a58` (crate commit `e26c18f`), worktree clean: True |
| toolchain | rustc 1.94.1 (e408947bf 2026-03-25); Cargo.lock `d67b12076a5126a9…` |
| environment | Python 3.11.15, numpy 2.4.4 (unused by the component) |
| scoring seed | 8251946031 (run once, 2026-10-05T13:32:47Z) |
| pinned inputs | 112 files, all unchanged |

## Results

| campaign part | cases | calls / files | mismatches |
|---|---|---|---|
| loaders (EXACT_VALUE) | 306 (63 deterministic, 3 environment, 240 seeded) | 8874 calls | 0 |
| build (EXACT_BYTES / EXACT_VALUE) | 23 | build_all + --check per case | 0 |
| W13 `abep-config build --check` on the repository | 1 | `OK: 12 config files current` (exit 0) | 0 |

Python outcomes over the loader calls: 7759 returned, 1115 raised
(AttributeError 13, ConfigurationError 712, JSONDecodeError 329, KeyError 22, StopIteration 2, TypeError 30, UnicodeDecodeError 7). Every class is reproduced, and every
ConfigurationError / BuildError text is identical character for character.

## Invariants

| id | pass | statement |
|---|---|---|
| INV-01 | True | Rust eval twice byte-identical (loaders, build); Python results twice identical |
| INV-02 | True | L-D58 load_operating_inputs and L-D57 physics_configuration RETURNED in both implementations |
| INV-03 | True | Rust scenario pin == ast.literal_eval(configuration.OPERATING_SCENARIO_PIN) |
| INV-04 | True | Rust builder constants (decision pins, scenario v1 pin, RVM pins, HW_ENTRIES, DATA_FILES, RESULT_SCHEMAS, file names, README) == Python builder constants |
| INV-05 | True | no string value PASS / FAIL / PASSED / FAILED in the computed loader outputs on the reference tree (verdict-free loaders) |

Conservation: not applicable (no mass / power / energy balance). Documented divergences DIV-01..DIV-05: none exercised.

## Performance (reported, not a criterion)

| workload | Python median s | Rust median s | speed-up |
|---|---|---|---|
| PERF-CFG-01 | 0.5719 | 0.0728 | 7.85 |
| PERF-CFG-02 | 0.0019 | 0.0037 | 0.52 |

PERF-CFG-02 Rust time includes starting the `abep-config eval` process.

## Captured reference outputs

`reference_outputs/` (manifest sha256 `a4bf868d4987cfeaa829d855eeaebf4e4da6c794830977a4c0bbd44c1c4867c7`): the seeded case file, per-case sha256 of the Python results (paths
normalised to `<WORK>` / `<REPO>`), the full Python results on the reference tree (L-D00) and of every build case.

## Ledger update requested

- `C-ABEP_SIM_CONFIGURATION_PY` → ADMITTED (PARITY_PASS); authoritative implementation `crates/abep-config`.
- `C-SCRIPTS_CONFIG_BUILD_CONFIG_PY` → ADMITTED (PARITY_PASS); `abep-config build --check`.
- `C-ABEP_SIM_OPERATING_INPUTS_PY`, `C-ABEP_SIM_DESIGN_ENGINEERING_CONSTRAINTS_PY`, `C-ABEP_SIM_CONSTANTS_PY`: unchanged
  (own contracts).

Admission is software parity, not physics validation and not a gate PASS.
