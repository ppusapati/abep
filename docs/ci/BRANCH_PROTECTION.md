# Branch protection for `main`: required CI checks (specification)

**Owner decision 2026-09-27 (YES):** the CI checks of `.github/workflows/ci.yml` are required before anything merges to
`main`. The settings can only be applied by the repository owner in GitHub *Settings*: the integration used by Claude
cannot read or write the branch-protection or rulesets endpoints. This file is the exact, checkable specification of what
to apply; `tests/test_ci_required_contexts.py` keeps it in step with the workflow (see *Keeping this file honest*).

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

## 2. Settings to apply to `main`

| setting | value | why |
|---|---|---|
| Require a pull request before merging | **on** | every change to `main` passes through a PR, which is where the checks run |
| Required approvals | **0** unless a second maintainer with write access exists | with a single maintainer, GitHub does not let the author approve their own PR, so a non-zero count would block every merge; the checks, not approvals, are the gate decided here |
| Require status checks to pass before merging | **on**, with exactly the three contexts of §1 | the owner decision |
| Require branches to be up to date before merging (classic: "strict") | **on** | a PR must have passed CI on top of the current `main`, not on an older base |
| Do not allow bypassing the above settings / include administrators | **on** (classic); **empty bypass list** (rulesets) | the owner is also the administrator; without this, an admin merge silently skips the gate. If it is ever incompatible with a needed operation, the owner changes it deliberately and records why in docs/HISTORY.md |
| Allow force pushes | **off** (block force pushes) | rewriting `main` would orphan pinned commits that provenance tests resolve with `git show` |
| Allow deletions | **off** (restrict deletions) | same reason |

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
* No other workflow exists today. Any future workflow becomes required only by a new owner decision, recorded here.

## 3. Preconditions (in this order)

1. **The CI workflow must exist on `main`.** Today `ci.yml` lives only on the execution branch
   `claude/nifty-ramanujan-w68f9z` (`main` is `daa0e75`; CLAUDE.md, *Execution baseline*). Merging that branch to `main`
   needs **explicit owner approval**; this specification does not grant or imply it.
2. **CI must have run at least once** so GitHub knows the contexts. The classic UI only suggests checks that have reported
   in this repository recently (about the last week); rulesets likewise list recent checks, and a context typed by hand
   that never reports leaves every PR blocked. The simplest sequence: open the PR that brings `ci.yml` to `main` (the
   `pull_request` trigger runs it on the PR itself), let all three jobs report, then apply protection, then merge.
3. **The three jobs must be green** on the PR before it can merge once protection is on. `docs/ci/CI.md`, *Open points*
   6 and 7, list known reasons the `tests` job may be red; those are fixed by their owning lanes, never by removing a
   required context or relaxing rule 9.
4. `ci.yml` triggers on `pull_request` with no branch or path filter and has no job-level `if:` on the required jobs.
   Keep it so: a path filter or a skipped job can leave a required context unreported (blocked PR) or reported as skipped.
   The test below enforces both.

## 4. Procedure A: classic branch protection

1. GitHub → repository `ppusapati/abep` → **Settings** → **Branches** (under *Code and automation*).
2. **Add branch protection rule** (or **Add classic branch protection rule**, depending on the UI version).
3. **Branch name pattern:** `main`.
4. Tick **Require a pull request before merging**. Set **Require approvals** per §2 (unticked / 0 with a single
   maintainer).
5. Tick **Require status checks to pass before merging**.
   * Tick **Require branches to be up to date before merging**.
   * In **Search for status checks in the last week for this repository**, type and select each of the three contexts of
     §1. For each, set the source to **GitHub Actions** if the selector is offered.
6. Tick **Do not allow bypassing the above settings** (older UIs: **Include administrators**).
7. Under *Rules applied to everyone including administrators*: leave **Allow force pushes** and **Allow deletions**
   **unticked**.
8. **Create** (or **Save changes**).

## 5. Procedure B: repository ruleset (alternative to A; use one, not both)

1. GitHub → **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**.
2. **Ruleset name:** `main: required CI`. **Enforcement status:** **Active**.
3. **Bypass list:** leave **empty** (do not add Repository admin, Maintain or any app).
4. **Target branches** → **Add target** → **Include default branch** (or **Include by pattern** `main`).
5. **Branch rules:**
   * Tick **Restrict deletions**.
   * Tick **Block force pushes**.
   * Tick **Require a pull request before merging**; **Required approvals** per §2.
   * Tick **Require status checks to pass**; tick **Require branches to be up to date before merging**; **Add checks** →
     add each of the three contexts of §1, choosing **GitHub Actions** as the source.
   * Leave the other rules unticked (§2).
6. **Create**.

If both a classic rule and a ruleset apply, GitHub enforces the union; keep only one to avoid two places drifting apart.
UI labels are as of 2026 and may move; the settings in §2 are what matters (**verify** label wording against the current UI).

## 6. Verifying it afterwards

1. **Read back via the API** (owner's own token; the integration cannot do this):
   * classic: `gh api repos/ppusapati/abep/branches/main/protection` →
     `required_status_checks.strict == true`, `required_status_checks.contexts` (or `checks[].context`) equals the three
     contexts of §1 exactly, `enforce_admins.enabled == true`, `allow_force_pushes.enabled == false`,
     `allow_deletions.enabled == false`, `required_pull_request_reviews` present.
   * rulesets: `gh api repos/ppusapati/abep/rules/branches/main` → rules of type `deletion`, `non_fast_forward`,
     `pull_request`, and `required_status_checks` with `strict_required_status_checks_policy: true` and the three
     contexts; `gh api repos/ppusapati/abep/rulesets` shows `enforcement: active` and no `bypass_actors`.
2. **Compare with this file:** the context list read back must equal the `required-status-checks` block above, as a set,
   with no extra and no missing entry.
3. **Behavioural checks:**
   * `git push origin HEAD:main` from a local commit is rejected ("protected branch" / "repository rule violations").
   * `git push --force` to `main` is rejected; deleting `main` in the UI is not offered or is refused.
   * On an open PR, the merge box lists the three checks as **Required**; while any is pending or failing, **Merge** is
     disabled for everyone including the owner (no "bypass" checkbox visible).
   * A PR whose base moved shows **This branch is out-of-date** and needs **Update branch** before it can merge.
4. Record the date and the method (classic or ruleset) in docs/HISTORY.md.

## 7. Keeping this file honest

`tests/test_ci_required_contexts.py` parses `.github/workflows/ci.yml`, expands every job `name:` over its matrix, and
asserts that the result equals the `required-status-checks` block of this file **exactly**. Renaming a job, changing a
matrix value or adding a job therefore fails the test until this file (and then the GitHub setting, per §4/§5) is updated
in the same change, so a rename cannot silently orphan a required check (an orphaned required context blocks every PR as
"Expected — Waiting for status"; a renamed job no longer being required would silently drop the gate). The test also
checks that the manual Julia smoke workflow contributes no required context and that the required jobs run on every
`pull_request` unconditionally.

After any change to the block above, the owner re-applies §4 or §5 and re-runs §6.
