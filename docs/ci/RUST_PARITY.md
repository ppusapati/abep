# Optional Rust CI: abep_core parity (`.github/workflows/rust-parity.yml`)

## Authority

Owner decisions, A9.14 S7–S10. The verbatim record is `docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md`.
The machine-readable companion is `docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json`, sha256
`c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c`.

* **S10.4, RUST-OQ-02: `OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`.** Normal CI may stay runnable without a Rust
  toolchain. When `abep_core` is built, the parity suite should run. Any change to Rust kernels, bindings or numerical
  logic needs the full pre-registered parity campaign before the kernel stays `ADMITTED`.
* **S10.3, RUST-OQ-01: `PYTHON_CANONICAL_FOR_FROZEN_AND_SCORE_BEARING`.** Frozen datasets, golden/reference rebuilds and
  score-bearing evidence come from the Python reference (`abep_sim/intake_tpmc.py`). An admitted Rust kernel may
  accelerate exploration, CI parity checks and non-authoritative runs only.

The pre-registration is `docs/performance/abep_core/parity_prereg_v1.json` (sha256
`dd12856bc384cb96643ffb5f8cd4fbc7df1c4d1adcc619bd210ddfa26c8102a8`, the value the report records). The record is
`docs/performance/abep_core/parity_report_v1.json` with its `.md`. Both run through `scripts/verify_abep_core.py`
(lane `fo_a9_7_rust_kernels`).

## What runs, and when

`ci.yml` is unchanged and needs no Rust. Its `tests/test_tpmc_backend.py` checks the parity record
(`verify_abep_core.check`) in every run. That includes the source-hash binding, so an unrecorded Rust change already fails
normal CI.

`rust-parity.yml` is **optional**. It is not a required status check: `docs/ci/BRANCH_PROTECTION.md` lists only the three
`ci.yml` contexts. It triggers on:

* `push` to `main` or the execution branch `claude/nifty-ramanujan-w68f9z` (the same branches as `ci.yml`), and
  `pull_request`. Both only when a path below changes.
* `workflow_dispatch`, which runs it by hand.

The paths are `abep_core/**`, `abep_sim/design/tpmc_backend.py`, `abep_sim/intake_tpmc.py` (the reference, which is bound
by the prereg), `scripts/verify_abep_core.py`, `docs/performance/abep_core/**` and the workflow file itself.

One job, `abep_core build + parity (optional)`, runs these steps:

| step | condition | what it does |
|---|---|---|
| source status | always | `verify_abep_core.py --source-status`: each `PROVENANCE_SOURCES` sha256 against `build_provenance.source_sha256`; reference against the prereg |
| reference refusal | reference sha256 ≠ prereg | fails with `REFUSED_REFERENCE_CHANGED`; a changed reference needs `parity_prereg_v2`, so no campaign runs |
| record check | sources match the record | `verify_abep_core.py --check` without the extension: every verdict, count, vector and the MD re-derived; sources bound |
| toolchain | always | `rustup toolchain install 1.94.1 --profile minimal`; must equal `build_provenance.rustc` exactly |
| Rust unit tests | always | `cargo test --release --locked` in `abep_core/` |
| build | always | `maturin==1.15.0` in a scratch venv (`--system-site-packages`), then `maturin develop --release --locked`; never the repository environment |
| parity suite | always (extension built) | `verify_abep_core.py --dev --strict`: the full development comparison with `development_master_seed`. It fails on any per-test, aggregate or invariant disagreement. It is **not scored and not a verdict**, and it admits nothing |
| bitwise reproduction | sources match and the CI binary equals `build_provenance.extension_sha256` | `--check --recompute 3` |
| full campaign | sources differ from the record (a Rust / binding / wrapper change) | `verify_abep_core.py`: the pre-registered scoring campaign (scoring seed 20261001, z = 5, aggregate threshold 4, 593 vectors) |
| upload | the campaign ran (any outcome) | report JSON + MD as artifact `abep_core-parity-report-<run_id>-<attempt>`, kept 90 days |
| re-admission gate | the campaign ran | `--check` with the CI binary, then **fails unless every kernel verdict is `ADMITTED`** |

Nothing in the workflow reads secrets. It has `contents: read` only, and nothing is pushed or committed.

## The two cases

**Sources unchanged** (the record covers this tree). The committed record is re-checked, Rust is built, and the
development parity suite runs.

A Rust binary built on a GitHub runner is not expected to equal the recorded one bitwise. The extension embeds dependency
source paths under `$CARGO_HOME` (for example `/root/.cargo/registry/...` in the recorded build). An identical rebuild was
observed only on the recording machine:

* source tree in a different directory;
* same `$CARGO_HOME`, `rustc` 1.94.1 and maturin 1.15.0;
* the result had the same sha256, `eb586f03…`.

So the bitwise `--recompute` step normally does not run in CI, and the workflow prints a notice instead.
`abep_sim/design/tpmc_backend.py` never serves the CI binary: its admission requires the recorded extension sha256
(`NOT_ADMITTED_BUILD`).

**Sources changed** (any `PROVENANCE_SOURCES` file differs from `build_provenance.source_sha256`). This is the
mandatory-parity case of S10.4. The full pre-registered campaign runs on the CI binary, and the job fails unless it
re-admits every kernel under the pre-registered rule. Even when it re-admits, the kernel is not `ADMITTED` *on the
committed tree* until that report is committed:

* `tpmc_backend` binds admission to the committed report;
* `ci.yml` fails `test_report_rederives_and_is_consistent` until the report matches.

The workflow ends with a warning that says this.

## Rules that bind the CI campaign (from the prereg, not new rules)

* **No execution may be discarded** (`campaign_seeds.development_rule`). A CI scoring execution is an execution of the
  v1 scoring campaign. Its report artifact must be committed to the repository, which appends to `campaign_history`,
  **whatever its verdict**. The artifact is kept for 90 days.
* **No retuning** (`decision_rules.no_retuning`). After a `NOT_ADMITTED` verdict, the only path forward is a code fix plus
  `parity_prereg_v2` with a new `scoring_master_seed`. A second v1 scoring run of the same seed after a failure is not a
  re-admission.
* **Iterate on the development seed.** Before pushing a change under `abep_core/**`, run
  `python scripts/verify_abep_core.py --dev --strict` locally. That way a known-broken change never consumes the v1
  scoring seed. The preferred route is to run the scoring campaign locally (abep_core/README.md) and commit the report
  in the same change. CI then sees matching sources and does not run a second campaign.
* Each push or pull-request event that changes the sources without an updated report starts its own scoring execution.
  The concurrency group (`rust-parity-<ref>`, no cancellation) serialises them per ref. Commit each resulting report.

## Pins and their sources

| pin | value | source | evidence class |
|---|---|---|---|
| Rust toolchain | 1.94.1 | `parity_report_v1.json` `build_provenance.rustc` = `rustc 1.94.1 (e408947bf 2026-03-25)`; the workflow compares the full string | recorded build provenance |
| maturin | 1.15.0 | version installed in the scratch build venv that produced the recorded extension, observed 2026-10-01; **not** recorded in `build_provenance`; `abep_core/README.md` allows `>=1.5,<2` | observed, not recorded |
| Python | 3.11 | `ci.yml` `PYTHON_VERSION`; `build_provenance.python` = 3.11.15; extension tag `cpython-311` | recorded / repository convention |
| Rust crates | `Cargo.lock` | committed lock file, `--locked` on build and test | repository |
| Python deps | `requirements-lock.txt` minus pymsis | as `ci.yml` | repository |
| actions | `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4` | version tags, as `ci.yml` | repository convention |

The toolchain is installed with `rustup`, which the runner image already has, so no third-party toolchain action is
used.

## CI entry points added to `scripts/verify_abep_core.py`

These are non-interactive and add exit codes only. They change no verdict rule, tolerance, seed, observable or vector.

* `--source-status [--github-output FILE]`: prints a JSON status and exits 0. The status covers whether the sources match
  `build_provenance`, whether the reference matches the prereg, and whether the importable extension is the recorded
  binary. With `--github-output` it also appends `key=value` lines for the workflow.
* `--dev --strict`: the full development comparison (no `--only` / `--limit`). It exits 1 when the pre-registered
  kernel rule, applied to development-seed data, does not hold for some kernel. It prints `DEVELOPMENT_SMOKE_OK` or
  `DEVELOPMENT_SMOKE_FAILED` and never prints a verdict word.

## Tests

`tests/test_rust_ci_workflow.py` parses the workflow with PyYAML (locked) and checks:

* triggers and paths;
* the job steps and their conditions;
* the pinned toolchain against the report;
* the absence of secrets and of extra permissions;
* that the workflow is not a required context.

It also exercises the two CLI entry points without a Rust toolchain. It never skips (CLAUDE.md rule 9).

## Open points

* **Edits outside this lane's file list, made to keep CLAUDE.md rule 9 green.**
  `tests/test_ci_required_contexts.py::test_no_other_workflows_unaccounted_for` pinned the workflow set to
  `["ci.yml", "julia-smoke.yml"]`, and `docs/ci/BRANCH_PROTECTION.md` said "No other workflow exists today". Each got a
  one-line or one-bullet change that accounts for `rust-parity.yml` as optional and not required, citing S10.4. No
  required context changed. The integrator should review these two edits.
* The workflow table in `docs/ci/CI.md` does not list `rust-parity.yml` yet. That file is outside this lane; this
  document is the reference.
* This workflow has not run on GitHub yet. Its first run will show the real build time and whether the runner binary
  differs from the recorded one, which is expected.
