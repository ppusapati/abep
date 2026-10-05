# Branch protection for `main`: required CI checks (specification)

**Owner decision 2026-09-27 (YES):** the CI checks of `.github/workflows/ci.yml` are required before anything merges to
`main`. The settings can only be applied by the repository owner in GitHub *Settings*: the integration used by Claude
cannot read or write the branch-protection or rulesets endpoints. This file is the exact, checkable specification of what
to apply; `tests/test_ci_required_contexts.py` keeps it in step with the workflow (see *Keeping this file honest*).
**Mechanism (owner decision 2026-09-27): one GitHub repository ruleset, never classic branch protection, never both**
(§2, §4, §5). Status: DRAFT specification for the owner to apply; nothing here is applied by Claude.

This is repository governance only. It changes no physics, frozen data, goldens, chemistry, pre-registration, campaign
record or scientific outcome.

## 1. Required status-check contexts

For a GitHub Actions job, the status-check context GitHub reports is the job's `name:` after expression substitution; a
matrix job produces one context per matrix leg. From `.github/workflows/ci.yml` (verified against the file at `fe1b8d1`):

| job id | `name:` in ci.yml | matrix | context(s) GitHub reports |
|---|---|---|---|
| `integrity` | `Repository integrity (scripts/ci_checks.py)` | none | `Repository integrity (scripts/ci_checks.py)` |
| `tests` | `Tests + golden benchmarks (pymsis ${{ matrix.pymsis }})` | `pymsis: [present, absent]` | `Tests + golden benchmarks (pymsis present)`, `Tests + golden benchmarks (pymsis absent)` |

The required set is exactly these three contexts (machine-read by the test; one context per line, nothing else in the
block):

```required-status-checks
Repository integrity (scripts/ci_checks.py)
Tests + golden benchmarks (pymsis present)
Tests + golden benchmarks (pymsis absent)
```

Notes:

* Enter each context **character for character**, including the parentheses and `scripts/ci_checks.py`. The workflow
  name (`CI`) is not part of the context. Do not add `CI / …`-prefixed variants; the UI shows the workflow name only as
  a label.
* Both matrix legs are required. Requiring only one would let a regression of gate 1 (clean install **without** pymsis,
  frozen atmosphere) or of the pymsis-present path merge unnoticed.
* Where the UI offers a source for the check, choose **GitHub Actions** (not "any source"), so that no other app can post a
  status with the same name and satisfy the requirement.
* The golden CLI exit-status test (`tests/test_golden_cli.py`) stays in the normal `python -m pytest -q tests` run of both
  `tests` legs, with no `slow` marker and no separate job (owner decision 2026-09-27, `fo_repo_decisions_batch`; recorded
  in `docs/ci/PACKAGING.md` D2). It is therefore gated by the two `Tests + golden benchmarks (…)` contexts; no fourth
  context exists for it.

## 2. Settings to apply to `main`

**Owner decision 2026-09-27 (`fo_repo_decisions_batch`, `docs/decisions/OD_HARDWARE_PIVOT_2026_09_27.json` →
`execution_directive_2026_09_27`): the mechanism is a GitHub repository RULESET, not classic branch protection. Never
both.** A classic branch-protection rule on `main` must not exist alongside the ruleset (GitHub enforces the union of
both, so two places would drift apart silently); if one exists, the owner deletes it when creating the ruleset (§4 step 1).

The machine-read summary of the decided settings (checked by `tests/test_ci_required_contexts.py`; `key: value`, one per
line):

```ruleset-decision
mechanism: ruleset
classic_branch_protection: none
enforcement: active
required_approvals: 0
required_status_checks: 3
strict_required_status_checks_policy: true
bypass_actors: none
```

| ruleset rule / field | value | why |
|---|---|---|
| Enforcement status | **Active** | an *Evaluate* or *Disabled* ruleset gates nothing |
| Bypass list | **empty** (no Repository admin, Maintain, team or app) | the owner is also the administrator; a bypass entry lets an admin merge skip the gate silently. If it is ever incompatible with a needed operation, the owner changes it deliberately and records why in docs/HISTORY.md |
| Target | the default branch (`main`) | |
| Require a pull request before merging | **on** | every change to `main` passes through a PR, which is where the checks run |
| Required approvals | **0** while there is one maintainer | owner decision. GitHub does not let the author approve their own PR, so a non-zero count would block every merge with a single maintainer; the checks, not approvals, are the gate. Raising it when a second maintainer with write access exists is a new owner decision, recorded here and in docs/HISTORY.md |
| Require status checks to pass | **on**, with exactly the three contexts of §1, source **GitHub Actions** | owner decision: all three CI contexts required |
| Require branches to be up to date before merging (`strict_required_status_checks_policy`) | **on** | owner decision: a PR must have passed CI on top of the current `main`, not on an older base |
| Block force pushes (`non_fast_forward`) | **on** | rewriting `main` would orphan pinned commits that provenance tests resolve with `git show` |
| Restrict deletions (`deletion`) | **on** | same reason |

Everything else (signed commits, linear history, merge queue, code owners, conversation resolution, deployments) is
**not** part of this decision. Leave it at the current value unless the owner decides otherwise.

### Explicitly NOT required checks

* **Scientific outcomes are never branch-protection checks.** O4 staged-sensitivity scores and dispositions, the facility
  campaign, P5-N₂ validation verdicts, admission records, architecture comparison / Bundle results and milestone
  decisions are evidence governed by pre-registration and the operating model (CLAUDE.md rules 2, 10;
  `docs/orchestration/OPERATING_MODEL.md`). They must never be turned into a pass/fail merge gate, a status, or a check run:
  that would pressure a scientific result to "go green", which is exactly the post-hoc tuning the project forbids.
  What CI gates is the *integrity of the evidence chain* (locks, pins, generated artefacts, admission gate, rule 9,
  goldens), not what the evidence says.
* **The manual Julia smoke workflow is not a required check.** `.github/workflows/julia-smoke.yml` (job
  `HallThruster.jl pinned install + one smoke job`) runs on `workflow_dispatch` only. It never reports on a PR, so
  requiring it would block every merge forever ("Expected — Waiting for status to be reported").
* **The optional Rust parity workflow is not a required check.** `.github/workflows/rust-parity.yml` (job
  `abep_core build + parity (optional)`) runs only when abep_core-related paths change, or by hand. The owner made it
  optional: A9.14 S10.4, RUST-OQ-02 = `OPTIONAL_RUST_CI_MANDATORY_PARITY_ON_RUST_CHANGES`
  (`docs/decisions/OD_2026_10_01_A9_14_S7_S10_OWNER_DECISIONS.md`). Normal CI stays runnable without Rust;
  `docs/ci/RUST_PARITY.md`.
* **The Rust workspace workflow is not a required check yet.** `.github/workflows/rust-workspace.yml` (job
  `Rust workspace (fmt, clippy, cargo test, bid guard, test register, groundtest isolation)`, ES-1) runs on every pull
  request and on pushes to `main` / `integration/simulation-complete`. Under `docs/rust_migration/CI_PLAN.md` v3.1 § 1
  principle 4 (plan structure approved by the owner, A9.29) the Rust jobs become required status checks only when the
  first non-Kernel-1 component is admitted; that PR updates this file.
* No other workflow exists today. Any future workflow becomes required only by a new owner decision, recorded here.

## 3. Preconditions (in this order)

1. **The CI workflow must exist on `main`.** Today `ci.yml` lives only on the execution branch
   `claude/nifty-ramanujan-w68f9z` (`main` is `daa0e75`; CLAUDE.md, *Execution baseline*). Merging that branch to `main`
   needs **explicit owner approval**; this specification does not grant or imply it.
2. **CI must have run at least once** so GitHub knows the contexts. The ruleset check picker lists checks that have
   reported in this repository recently, and a context typed by hand that never reports leaves every PR blocked. The
   simplest sequence: open the PR that brings `ci.yml` to `main` (the `pull_request` trigger runs it on the PR itself),
   let all three jobs report, then create the ruleset (§4), then merge.
3. **The three jobs must be green** on the PR before it can merge once protection is on. `docs/ci/CI.md`, *Open points*
   6 and 7, list known reasons the `tests` job may be red; those are fixed by their owning lanes, never by removing a
   required context or relaxing rule 9.
4. `ci.yml` triggers on `pull_request` with no branch or path filter and has no job-level `if:` on the required jobs.
   Keep it so: a path filter or a skipped job can leave a required context unreported (blocked PR) or reported as skipped.
   The test below enforces both.

## 4. Procedure: repository ruleset (the decided mechanism)

1. **No classic rule.** GitHub → repository `ppusapati/abep` → **Settings** → **Branches**. If a classic branch
   protection rule matching `main` is listed, delete it (the ruleset below replaces it; never keep both).
2. GitHub → **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**.
3. **Ruleset name:** `main: required CI`. **Enforcement status:** **Active**.
4. **Bypass list:** leave **empty** (do not add Repository admin, Maintain, any team or any app).
5. **Target branches** → **Add target** → **Include default branch** (or **Include by pattern** `main`).
6. **Branch rules:**
   * Tick **Restrict deletions**.
   * Tick **Block force pushes**.
   * Tick **Require a pull request before merging**; **Required approvals: 0** (§2).
   * Tick **Require status checks to pass**; tick **Require branches to be up to date before merging**; **Add checks** →
     add each of the three contexts of §1, choosing **GitHub Actions** as the source.
   * Leave the other rules unticked (§2).
7. **Create**.

UI labels are as of 2026 and may move; the settings in §2 are what matters (**verify** label wording against the current UI).

## 5. Classic branch protection: not used

Classic branch protection (**Settings** → **Branches** → *Add branch protection rule*) is **not** used for `main` (owner
decision 2026-09-27). The earlier alternative procedure for it was removed from this file so that there is one
specification only. Re-introducing classic protection, alone or next to the ruleset, needs a new owner decision.

## 6. Verifying it afterwards

1. **Read back via the API** (owner's own token; the integration cannot do this):
   * `gh api repos/ppusapati/abep/rulesets` → exactly one ruleset targeting `main` (`main: required CI`) with
     `enforcement: active`; `gh api repos/ppusapati/abep/rulesets/<id>` → `bypass_actors` empty.
   * `gh api repos/ppusapati/abep/rules/branches/main` → rules of type `deletion`, `non_fast_forward`, `pull_request`
     with `required_approving_review_count: 0`, and `required_status_checks` with
     `strict_required_status_checks_policy: true` and the three contexts of §1.
   * **No classic protection:** `gh api repos/ppusapati/abep/branches/main/protection` returns HTTP 404
     ("Branch not protected"). A 200 means a classic rule exists next to the ruleset: delete it (§4 step 1).
2. **Compare with this file:** the context list read back must equal the `required-status-checks` block of §1, as a set,
   with no extra and no missing entry; the other values must equal the `ruleset-decision` block of §2.
3. **Behavioural checks:**
   * A direct push of a local commit to `main` is rejected ("repository rule violations").
   * A force push to `main` is rejected; deleting `main` in the UI is not offered or is refused.
   * On an open PR, the merge box lists the three checks as **Required**; while any is pending or failing, **Merge** is
     disabled for everyone including the owner (no "bypass" checkbox visible). No approval is requested.
   * A PR whose base moved shows **This branch is out-of-date** and needs **Update branch** before it can merge.
4. Record the date and the method (ruleset) in docs/HISTORY.md.

## 7. Keeping this file honest

`tests/test_ci_required_contexts.py` parses `.github/workflows/ci.yml`, expands every job `name:` over its matrix, and
asserts that the result equals the `required-status-checks` block of this file **exactly**. Renaming a job, changing a
matrix value or adding a job therefore fails the test until this file (and then the GitHub ruleset, per §4) is updated
in the same change, so a rename cannot silently orphan a required check (an orphaned required context blocks every PR as
"Expected — Waiting for status"; a renamed job no longer being required would silently drop the gate). The test also
checks that the manual Julia smoke workflow contributes no required context and that the required jobs run on every
`pull_request` unconditionally.

It also checks the `ruleset-decision` block of §2 (ruleset only, no classic protection, active, 0 approvals, three
required contexts, strict up-to-date policy, no bypass actors) and that no classic-protection procedure is present.

After any change to either block, the owner re-applies §4 and re-runs §6.
