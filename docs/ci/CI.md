# Continuous integration: what it enforces and why

CI turns the repository's evidence discipline (CLAUDE.md rules, [docs/EVIDENCE.md](../EVIDENCE.md)) into checks that a
reviewer does not have to repeat by hand. It **verifies**. It never regenerates frozen data, never changes physics,
thresholds or chemistry, never runs the Hall solver on a push or pull request, and never reads campaign records.

**Milestones.** This is infrastructure, not a performance deliverable. It supports Milestones A, B and C only by keeping
the evidence chain those milestones rely on verifiable (locks, pins, generated artefacts, admission gate, goldens, rule 9).
It adds no evidence for any architecture. To serve as a merge gate for B/C evidence, the owner has to make the three CI
contexts required checks on `main` (exact names and procedure: `docs/ci/BRANCH_PROTECTION.md`).

| workflow | trigger | what it runs |
|---|---|---|
| `.github/workflows/ci.yml` | `pull_request`, `push` to `main` or to the pinned execution branch `claude/nifty-ramanujan-w68f9z` | job **integrity**: `python scripts/ci_checks.py`; job **tests** (pymsis present / absent): `python -m pytest -q tests`, the rule-9 outcome check, `python -m abep_sim.golden check` |
| `.github/workflows/julia-smoke.yml` | `workflow_dispatch` only (manual, with a confirmation box) | pinned HallThruster.jl install and **one** `P5N2_SMOKE=1` construction job; never score-bearing |

To make CI a merge gate, the repository owner has to mark the three status contexts (`Repository integrity
(scripts/ci_checks.py)`, `Tests + golden benchmarks (pymsis present)`, `Tests + golden benchmarks (pymsis absent)`) as
required on `main`; `docs/ci/BRANCH_PROTECTION.md` gives the procedure and `tests/test_ci_required_contexts.py` keeps the
names in sync with `ci.yml`. Nothing in this repository can apply the setting.

## The evidence chain and where CI checks it

```
published source ── measurement audit ──┐
                                        ├─ pre-registration (criteria + run-status rule + addendum) ── LOCK (sha256)
transport screening candidates ─────────┤
case set (generated) ───────────────────┘
chemistry: n2_n.toml ── generated variants ── rate tables (generated / cited) ── rate_validity.toml
audit snapshots (immutable) ── MANIFEST (sha256 of snapshots and every rate table they use)
launch manifests (generated: expected keys, chemistry sha256, driver sha256, lock sha256)
   ── campaign records ── frozen dataset ── scores ── decision ── admission record ── ensemble member ── Hall maps
```

CI covers every link **before** a run: the inputs a score-bearing run may use. The links after a run (freeze, score,
report, release) are checked by their own scripts on real data, which does not live in the repository. CI does not run
them and never looks at `hallthruster_bridge/out/` or any campaign output.

## `scripts/ci_checks.py`: static integrity (seconds, writes nothing)

Each check returns a list of problems (empty means pass) and a one-line note that says what was verified, so a pass is
never silent about its scope. The exit code is 1 if any check fails, and a check that raises counts as a failure, not a skip.

| check | what it verifies | rule it enforces |
|---|---|---|
| `parse_json_toml` | Every `*.json` and `*.toml` parses. A duplicate JSON key is an error, because Python would otherwise silently keep the last value. Every non-empty line of every `*.jsonl` evidence ledger (`docs/orchestration/fired_triggers.jsonl`, `trigger_ledger_v2.jsonl`, the audit record files) must be one JSON object. `*.jsonl` under `hallthruster_bridge/validation/` are campaign run records and are not read; the validation release pipeline binds them. Pruned: `.git`, `hallthruster_bridge/out` (raw run output), gitignored `results/`, and local environments and caches (`.venv`, `__pycache__`, `.claude`, …). | integrity of every data file |
| `prereg_lock` | Every file listed in `prereg/p5_n2_prereg_lock_v1.json` matches its sha256. The inputs pinned by `p5_n2_validation_criteria_v1.json` (measurement audit, case set, transport candidates, all 22 chemistry configs) match theirs. These are the same refusal conditions the campaign driver applies at start-up, so CI fails wherever the driver would refuse. | pre-registration: "any change after this lock is a new, dated addendum, never an edit" |
| `audit_manifest` | Each immutable audit snapshot in `audit/configs/` matches its sha256. The set of rate files it names equals the MANIFEST list, and every one of those rate tables matches its pinned sha256. The case-file snapshot also matches. | historical audits read immutable snapshots (PR #25 review) |
| `hallthruster_pin` | The `PINNED.toml` commit, version and repository equal the `HallThruster` entry of `Manifest.toml` (repo-rev, version, repo-url). The `Project.toml` compat is `=<version>`. | rule 7 (pin; upgrade policy: never moved automatically) |
| `rate_validity_coverage` | Every rate file named by any propellant config exists and has a `rate_validity.toml` entry: `verified` with a numeric limit, or `unresolved`. | "no silent chemistry extrapolation: missing = driver error" |
| `variant_configs` | `scripts/make_n2_variant_configs.py` (all `VARIANTS`, including the escalation combinations) reproduces every committed variant TOML byte for byte. No file marked `GENERATED VARIANT` lacks a generator entry. | variants can never drift from `n2_n.toml` |
| `p5_n2_cases` | `scripts/make_p5_n2_cases.py` reproduces `cases/p5_n2.json` byte for byte. | the case set is generated, and sha256-pinned in the criteria |
| `launch_manifests` | `scripts/make_p5_n2_launch_manifests.py` `build()` reproduces every `campaign/manifests/*.json` byte for byte, and no committed manifest is an orphan. The manifests embed the driver and lock sha256, so this also catches an edited campaign driver or lock. | nothing about a follow-on run is decided after results |
| `multiply_charged_tables` | `scripts/build_multiply_charged_tables.py` reproduces every table it owns (`propellants/` and `audit/bound_tables/`) byte for byte, plus each `.source` provenance file. This is the comparison its `--check` mode makes, plus `.source`, without a temporary directory. | rule 6 (tables carry their source) |
| `ensemble_gate` | `abep_sim.hall_ensemble.load_ensemble()` loads the transport ensemble. `require_admitted` refuses every screening candidate (with the SCREENING reason) and an unknown id, and no id is both admitted and screening. The admission-record verification lives in `load_ensemble` itself and is reused. | screening candidates never produce design Hall maps |

**Fresh generation without writing.** Each generator runs through its own `__main__` write path with default arguments
inside `WriteCapture`. There, `builtins.open` and `io.open` in a writing mode return in-memory buffers, directory creation
is a no-op, every move, remove or copy call raises, and no bytecode is cached. The captured bytes are then compared with
the committed files. So the check exercises exactly the code a maintainer would run to regenerate, including its
`__main__` block, and leaves the tree untouched. `tests/test_repo_integrity.py` proves that no file is created, that
modification times are unchanged, and that append and remove are refused.

**Why byte for byte.** The pre-registration lock and the criteria pin sha256 of bytes, not of parsed content, and so do
the launch manifests. A reformatted file with identical content would still break the lock. The failure message tells the
two cases apart: "parsed content equal: formatting only" or "content differs".

Separate mode: `python scripts/ci_checks.py --pytest-junit <report.xml>` checks **CLAUDE.md rule 9** against a pytest JUnit
report. It requires no failure or error, exactly 5 skips whose reason starts with `SUPERSEDED` (the retired 0-D Hall
calibration), and exactly one xfail, `test_v16_blind_validation_p5_nitrogen` (strict, so an unexpected pass is already a
pytest failure). A new skip, for example a test silently disabled when a dependency is missing, fails CI. The expected
values are the constants `EXPECTED_SKIPPED`, `EXPECTED_SKIP_REASON_PREFIX` and `EXPECTED_XFAIL`, and change only together
with an owner-logged change of rule 9.

**Rule 9 needs full git history.** Several provenance tests from later lanes (for example `tests/test_bundle1.py`,
`tests/test_echt_status.py` and `tests/test_v2_question_a_brief.py`) resolve pinned lane or base commits with `git show`
and skip when those objects are missing. In a shallow clone, which is the `actions/checkout` default (depth 1), the suite
therefore reports extra, non-SUPERSEDED skips. The second-lens review observed 5 + 3 = 8 skips in a single-commit copy of
`e15f66f`. So both CI jobs check out with `fetch-depth: 0`, and `--pytest-junit` also fails with an explicit "shallow
clone" reason when the repository is shallow or is not a git repository. The failure is not attributed to the tests.

**Coupling (owner).** `EXPECTED_SKIPPED = 5` is a hard count. A future lane that adds a legitimate, environment-dependent
skip (for example on an unreachable pinned input or a status condition) will turn CI red. That is intended, because rule 9
says 5. But the owner has to decide either to amend rule 9 or to make such tests fail instead of skip. The gate must not
be relaxed silently.

Other options: `--list` names the checks, and `--only a,b` runs a subset (exit code 2 for an unknown name).

## `ci.yml` in detail

* **Python 3.11.** `requirements-lock.txt` is installed exactly. The scripts need `tomllib` (standard library since Python
  3.11, PEP 680), and the pinned numpy / scipy / pandas releases need ≥ 3.11 (from memory, **verify** against their release
  notes). The local reference environment for this work was Python 3.11.15.
* **pymsis matrix.** The `present` leg installs the full lock. The `absent` leg installs the lock without the `pymsis` line
  and asserts that `pymsis` is not importable. Both legs run the tests and the golden check. This is gate 1 ("runs with
  pymsis absent"): the frozen NRLMSIS dataset is the default, and live MSIS is used only when asked.
* **Editable install.** After the lock-file install, both jobs run `python -m pip install --no-deps -e .` (explicit package
  discovery; owner decision 2026-09-27; `docs/ci/PACKAGING.md`). `--no-deps` keeps the lock file as the dependency source and
  keeps the pymsis-absent leg free of pymsis.
* **Golden gate.** `python -m abep_sim.golden check` prints `OK` and exits 0 when nothing moved; otherwise it prints one
  line per deviation and exits 1 (owner decision 2026-09-27; `tests/test_golden_cli.py`). CI runs it as a plain step and
  gates on the exit code (rule 2). A moved golden is a model change and must be
  justified, regenerated and logged. CI never regenerates goldens.
* **Clean tree.** After each job, `git status --porcelain` must be empty, so tests, goldens and checks must not rewrite
  committed files. Gitignored caches are allowed.
* **Full history** (`fetch-depth: 0`) in both jobs, for the rule-9 reason above.
* **Triggers.** `push` runs on `main` and on the pinned execution branch `claude/nifty-ramanujan-w68f9z`, because CLAUDE.md
  says nobody executes from `main` until that branch merges. Other branches are checked through their pull requests.
* `permissions: contents: read`. Superseded pull-request runs are cancelled.

## `julia-smoke.yml`: optional construction-only smoke (manual)

This workflow shows that the pinned solver installs and that the campaign driver can **construct** a P5-N2 run from the
pre-registered inputs. It does not validate anything and cannot produce a score.

To trigger it: GitHub → Actions → "Julia construction smoke (manual, never score-bearing)" → Run workflow → tick the
confirmation box. It never runs on a push or pull request, and the job is skipped unless the box is ticked.

1. `ci_checks.py --only hallthruster_pin,prereg_lock`, then the Julia version, commit and package version are read from
   `hallthruster_bridge/Manifest.toml` / `PINNED.toml` (Julia 1.11.7, HallThruster.jl 0.23.1 @
   `bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5` at the base of this work).
2. Install: `julia --project=hallthruster_bridge -e 'using Pkg; Pkg.instantiate()'` installs exactly the committed
   `Manifest.toml` (same repo-rev, git tree hash verified, no re-resolution). Locally the one-time route is
   `julia hallthruster_bridge/setup.jl`, which runs `Pkg.add(url = …, rev = <pinned commit>)`. CI uses `instantiate` so that
   the committed Manifest is what gets tested. `check_pin()` from `bridge_lib.jl` must return the pinned commit, and the
   checkout must be unchanged afterwards.
3. Smoke run, exactly one job, with `P5N2_SMOKE=1`:
   `julia --project=hallthruster_bridge hallthruster_bridge/campaign/p5_n2_campaign.jl "$RUNNER_TEMP/p5n2_smoke/smoke.jsonl" vacuum 0 <N> n2_n.toml`,
   where N = screening candidates × cases. With N shards, shard 0 is exactly the first job. The driver itself refuses to
   start unless every locked file and pinned chemistry config matches its sha256.
4. Why it is never score-bearing:
   * `P5N2_SMOKE=1` means 2 µs of simulated time, measured targets stripped from the case, and `"smoke": true` on the
     record. `scripts/score_p5_n2_campaign.py` asserts that no smoke record is scored. The structural gates
     (`scripts/audit_p5_n2_campaign_records.py`, `make_p5_n2_launch_manifests.check`) require `smoke == false`.
   * The record is written under `$RUNNER_TEMP`, outside the checkout. A step asserts exactly one record, `smoke == true`
     and no target field (`measured`, `Id_target_A`, `T_target_N`, `*_err_*`, …). Only the run key and return code are
     printed, the same log discipline as the driver. The record is never uploaded as an artifact and is deleted at the end
     (`if: always()`).
   * The job fails if the checkout changed.

Nobody has run this workflow yet; it was written without running Julia (see *Open points*).

## Running locally

```
python scripts/ci_checks.py                       # all static checks
python scripts/ci_checks.py --only prereg_lock    # one check
python -m pytest -q tests/test_repo_integrity.py  # the checks' own tests (tamper tests run on copies in tmp_path)
```

Measured on 2026-09-26 in this worktree at base `efc4a4e` (Python 3.11.15): `ci_checks.py` took 2.8 s wall, all 10 checks
passing (55 JSON + 32 TOML parsed; 6 locked files; 22 pinned chemistry configs; 5 audit snapshots; 21 variants; 30 cases;
19 launch manifests; 10 tables + 10 `.source`; 0 admitted members, 9 screening candidates refused). `test_repo_integrity.py`
took 3.3 s, 11 passed. Re-measured on 2026-09-26 during the second-lens repair. On an export of the current execution-branch
commit `e15f66f`: 2.7 s wall, 10/10 checks passing, with 162 JSON + 32 TOML + 4 JSONL files parsed and the other counts
unchanged. In the lane worktree, `test_repo_integrity.py` ran 12 tests, all passing, in 3.5 s. These counts grow as lanes
add files; they are dated, not constants. The full suite and the golden check were **not** run for this work, because of the CPU budget while
the P5-N2 campaign is running, so their CI runtime is unknown (timeout 90 min).

## When a check fails

* **Lock / pin mismatch** (`prereg_lock`, `audit_manifest`): a locked or pinned input changed. Restore it. A real change
  to a pre-registered input is a new, dated addendum, never an edit of a locked file, and the owner decides it.
* **Generated artefact differs** (`variant_configs`, `p5_n2_cases`, `launch_manifests`, `multiply_charged_tables`): either
  the committed file was edited by hand (regenerate it with the named script) or the generator changed. A change to the
  generated content is a model or pre-registration change: it needs its own justification, any lock or pin consequences,
  and a docs/HISTORY.md entry. An orphan means a committed file that no generator produces.
* **`hallthruster_pin`**: the pin moved or the Manifest was re-resolved. Upgrades follow the `PINNED.toml` upgrade_policy
  and are never automatic.
* **`ensemble_gate`**: a screening candidate would be treated as admitted, or the ensemble does not load. Admission needs
  an offline-verifiable admission record (`hall_ensemble._check_admission`).
* **Rule-9 outcome**: a test was newly skipped, the strict xfail changed, or the skip reasons changed. Never "fix" the
  superseded tests by re-tuning.
* **Golden**: a model change (rule 2), not something to regenerate so that CI passes.

## Open points for the owner

1. Resolved 2026-09-27 (owner decision): explicit setuptools package discovery with `abep_sim/data` as package data;
   `pip install -e .` and a wheel install both work (`docs/ci/PACKAGING.md`). Resolved 2026-09-27 (owner decision): `pymsis`
   is only in the `[msis]` extra, so a plain install no longer pulls it (gate 1); CI keeps `--no-deps` so the lock file stays
   the single dependency source.
2. Resolved 2026-09-27 (owner decision): `requires-python >= 3.11`.
3. Resolved 2026-09-27 (owner decision): `python -m abep_sim.golden check` now exits 1 on deviations, and CI gates on
   the exit code instead of parsing the output text.
4. Actions are pinned by major tag (`actions/checkout@v4`, `actions/setup-python@v5`, `julia-actions/setup-julia@v2`).
   Pinning them to commit SHAs is an option for supply-chain hardening.
5. The smoke workflow has never been run. Its first manual run may surface environment issues (Julia registry access,
   precompile time).
6. **The rule-9 gate has never been exercised against the real full suite.** The full suite was not run for this lane
   because of the CPU budget. The first CI run is also the first check of the 5-skip / 1-xfail outcome with full history.
7. **Reported by the second-lens review, not re-run by this lane:** at `e15f66f`, `tests/test_bundle1.py` fails two tests
   (the JSON-equality assertion and `test_check_mode_cli`) even with full history, because
   `docs/milestones/bundle1/bundle1_v1.json` / `BUNDLE1.md` are not reproduced. The review attributes this to the lane_09
   repair note. It is outside this lane, but the `tests` job will be red on it until the owning lane regenerates or
   repairs Bundle 1.
8. The `EXPECTED_SKIPPED` coupling point described under *Separate mode*.
