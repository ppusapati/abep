export const meta = {
  name: 'hardening-h1-h2-h3-s12prep',
  description: 'Parallel repository hardening (H1 branch-protection spec, H2 packaging, H3 golden CLI) + S12 builder preparation: isolated worktrees, two-lens verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "fe1b8d122a120470ef8bb22c2809e5733bc50081", "lanes": [{"key": "H1", "title": "H1 branch protection specification (repository governance)", "allowed": ["docs/ci/BRANCH_PROTECTION.md", "tests/test_ci_required_contexts.py"], "prompt": "Owner decision 2026-09-27 (YES): require the CI checks before merge to main. The settings themselves can only be applied by the owner in GitHub Settings (the integration cannot read or write the branch-protection endpoint), so this lane produces the exact, checkable specification. Deliver docs/ci/BRANCH_PROTECTION.md: (1) the EXACT required status-check contexts as GitHub will report them, derived from .github/workflows/ci.yml job `name:` fields incl. BOTH matrix legs: 'Repository integrity (scripts/ci_checks.py)', 'Tests + golden benchmarks (pymsis present)', 'Tests + golden benchmarks (pymsis absent)' - verify against the file, do not trust this brief; (2) settings: require a pull request before merging; require status checks to pass with those contexts; require branches to be up to date before merging; do not allow bypassing (incl. administrators, if compatible); block force pushes and deletion of main; (3) a click-by-click procedure for classic branch protection AND the rulesets UI, plus how to verify it afterwards; (4) preconditions: the CI workflow must exist on main (it currently lives only on the execution branch claude/nifty-ramanujan-w68f9z; merging to main requires explicit owner approval) and must have run at least once so GitHub offers the contexts; (5) explicitly: scientific outcomes (O4, facility, architecture) are NEVER branch-protection checks; the manual Julia smoke workflow is not a required check. Test tests/test_ci_required_contexts.py: parses ci.yml and asserts the documented contexts equal the job names x matrix values exactly (so a job rename cannot silently orphan a required check)."}, {"key": "H2", "title": "H2 packaging / installability", "allowed": ["pyproject.toml", "MANIFEST.in", "scripts/install_and_test.sh", "docs/ci/PACKAGING.md", "tests/test_packaging.py", ".github/workflows/ci.yml (ONLY the dependency-installation steps and the PYTHONPATH workaround comment/env; never the golden step, which lane H3 owns)"], "prompt": "Owner decision 2026-09-27 (YES), narrowly scoped to packaging. (1) pyproject.toml: requires-python = \">=3.11\" (tomllib and the locked environment require 3.11; CI already uses 3.11). (2) Configure setuptools package discovery EXPLICITLY instead of flat-layout auto-discovery (which currently fails with 'Multiple top-level packages discovered in a flat-layout: [abep_sim, hallthruster_bridge]'): package abep_sim (and its subpackages if any) with its data files (abep_sim/data/** incl. frozen datasets, goldens, rates) as package data; do NOT move modules, do NOT restructure or package hallthruster_bridge unless something imported by abep_sim at runtime requires it (check imports; if abep_sim imports hallthruster_bridge files at runtime, document how they are located and keep editable-install behaviour identical to running from the repository root). Keep dependencies unchanged EXCEPT report (do not silently change) that pymsis is listed as a hard dependency although gate 1 requires running without it - put the recommended fix (move it to the existing [msis] extra) as an owner question unless it is required to make the documented no-pymsis install work. (3) Acceptance (do it yourself, in scratch venvs under the scratchpad): fresh venv -> pip install -r requirements-lock.txt -> pip install -e . -> import abep_sim -> abep-sim --help (or a safe CLI smoke) -> python -m pytest -q tests (full suite once; expect rule-9 outcome) -> python -m abep_sim.golden check; and separately: python -m build (or pip wheel) -> install the wheel into another fresh venv -> verify abep_sim/data files are present and the frozen atmosphere + golden check load from the installed package (run from a directory outside the repo). (4) CI: switch the install steps to `pip install -e .` (keep the lock-file install first) and remove the PYTHONPATH workaround if the editable install makes it unnecessary; keep the pymsis present/absent legs. (5) scripts/install_and_test.sh must work. (6) tests/test_packaging.py: requires-python >= 3.11; explicit discovery configured; package data declared for abep_sim/data; (optionally, skip-free) a fast check that setuptools discovery finds exactly the intended packages. Document in docs/ci/PACKAGING.md with the acceptance transcript summary."}, {"key": "H3", "title": "H3 golden CLI exit status", "allowed": ["abep_sim/golden.py (ONLY the `if __name__ == \"__main__\"` CLI block; check(), generate() and everything else unchanged)", "tests/test_golden_cli.py", ".github/workflows/ci.yml (ONLY the 'Golden benchmarks' step; never the install steps, which lane H2 owns)", "docs/ci/CI.md (only the golden-step description)"], "prompt": "Owner decision 2026-09-27 (YES). Not a golden change and not a model change: only the CLI's failure signalling. `python -m abep_sim.golden check`: no differences -> print OK -> exit 0; differences -> print the differences -> exit non-zero (use 1; document it). `generate` behaviour unchanged. NEVER regenerate abep_sim/data/golden_v1.json. CI: replace the stdout-parsing golden step with simply `python -m abep_sim.golden check`. Test tests/test_golden_cli.py (subprocess): unchanged tree -> exit 0 and last line OK; a deliberately perturbed golden (a COPY of golden_v1.json with one value changed, pointed to via monkeypatching/an env or module attribute WITHOUT modifying the committed file or adding production configuration knobs beyond what is minimal and documented) -> exit != 0 and the deviation printed. Confirm golden_v1.json is byte-identical before/after."}, {"key": "S12PREP", "title": "S12 preparation: O4 disposition-matrix builder (machinery only)", "allowed": ["docs/o4/disposition_matrix/**", "tests/test_o4_disposition_matrix.py"], "prompt": "Owner instruction 2026-09-27: prepare the S12 builder/verification machinery now; the actual disposition waits for all required escalation scores (T_O4_DISPOSITION_MATRIX, registered follow-on fo_o4_disposition_matrix, is NOT ready and is not claimed by this lane). Build docs/o4/disposition_matrix/build_o4_disposition_matrix.py: reads the O4 rule (hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json, read-only), the dispositions schema hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json (read-only; the matrix must be able to feed an owner o4_dispositions file conforming to it, as enforced by abep_sim/hall_ensemble._check_o4 - read that code), the registry of O4 datasets (docs/orchestration/lane_registry_v1.json datasets: 5 staged first stages + 13 escalations) and every scored dataset's *_scores.json / *_scores_provenance.json under hallthruster_bridge/validation/ (verify sha256 bindings and mandatory reproduction), and the verified Johnson-low assessment docs/o4/johnsonlow_assessment/johnsonlow_assessment_v1.json. Per sensitivity family x baseline combination: trigger_fired, run-level trigger counts by kind and point, verdict changes (member/candidate), status transitions, and an EVIDENCE-ONLY column for the owner's disposition (no disposition is decided by the builder: dispositions are owner decisions). The builder MUST REFUSE to emit the official matrix unless every required dataset is scored (it lists the missing ones - currently the 7 attempt-2 escalations: hmslow x3, hmshigh x3, n2dication_nel_wang); it may emit a clearly marked PREVIEW (never committed as the matrix, never named as a disposition) for testing. Interrupted attempt-1 outputs (hallthruster_bridge/validation/interrupted/**) must never be read (test it). Deliverables: the builder, a schema for the matrix, a README describing the procedure, tests/test_o4_disposition_matrix.py (refusal while datasets are missing; hash verification; interrupted outputs ignored; totals reproduce the scored staged_escalation blocks for the 11 scored datasets; no forbidden wording: promote/validated/admitted). Do NOT commit a matrix file."}]}

const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. Base commit: ${BASE}.
FIRST STEP: your worktree may have been created from main (daa0e75). If \`git rev-parse HEAD\` != ${BASE} and \`git status --porcelain\` is empty, run \`git reset --hard ${BASE}\`.
CONTEXT: this is a REPOSITORY-HARDENING / PREPARATION wave (owner decision 2026-09-27) running in parallel with physics work; it must never change physics, frozen data, goldens (never regenerate abep_sim/data/golden_v1.json), chemistry, pre-registration, campaign records or scientific outcomes. Read CLAUDE.md (rules 1-10). Expected full-suite outcome (rule 9): all pass, exactly 5 skipped, 1 strict xfail.
HARD RULES: modify/create files ONLY under your lane's ALLOWED paths (the brief may narrow a path to specific hunks: obey). Never touch hallthruster_bridge/** or ${SP}/followon / ${SP}/wt_followon (running campaigns). Do not run Julia. CPU is shared with 12 running Julia processes: run your own tests and, where the brief requires, the full suite at most once. No network use beyond what pip needs for installing the locked requirements (requirements-lock.txt), through the configured proxy; never change TLS/trust settings. When done: git add your files and commit in the worktree with a clear message whose last two lines are exactly:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U
Do NOT push. Report the worktree absolute path, branch and commit sha.

YOUR LANE:
`

const RESULT = {
  type: 'object',
  properties: {
    worktree_path: { type: 'string' }, branch: { type: 'string' }, commit: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    key_findings: { type: 'array', items: { type: 'string' } },
    unlocks: { type: 'array', items: { type: 'string' }, description: 'which other lanes/decisions this result enables, eliminates a dependency for, or suggests as a new parallel branch' },
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'key_findings', 'unlocks', 'open_questions_for_owner', 'tests_passed'],
}
const VERDICT = {
  type: 'object',
  properties: {
    pass: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, file: { type: 'string' }, description: { type: 'string' } },
      required: ['severity', 'description'] } },
    checked: { type: 'array', items: { type: 'string' } },
  },
  required: ['pass', 'issues', 'checked'],
}
const LENSES = {
  evidence: `ACCEPTANCE LENS. Re-run the lane's acceptance procedure YOURSELF from scratch (scratch venvs / copies only under ${SP}/verify_<lane>_acceptance/, deleted afterwards; never inside the primary checkout): e.g. a fresh venv + pip install -e . + import + CLI smoke + tests + golden check; a wheel build/install in a separate fresh venv checking that abep_sim/data files are packaged; the golden CLI exit codes on an unchanged tree (0) and on a deliberately perturbed COPY (non-zero); the branch-protection contexts against the real job names. Anything claimed but not reproducible is MAJOR; any change to physics, goldens, frozen data or scientific outcomes is a BLOCKER.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD within ALLOWED paths; no forbidden file touched; no uncommitted leftovers. (b) RECOMPUTE: for headline numbers derived from repository data or equations, write your own independent Python (do not reuse the lane's code) and compare; mismatch beyond rounding is major. (c) CORRECTNESS: JSON/schemas parse and validate; code consistent with the modules/fields it references (grep them); no hidden defaults; refusal paths raise; run ONLY the lane's own test file(s): they must pass and test something meaningful. (d) RULES: scope limited exactly to the brief (no refactors, no module moves, no hallthruster_bridge restructuring); rule-9 outcome preserved; no golden regeneration. (e) USEFULNESS: every required deliverable in the brief present and substantive; the 'unlocks' claims are justified.`,
}
const verifyPrompt = (lane, res, lens) => `You are an ADVERSARIAL reviewer. Default to finding problems; pass only if there are no blocker or major issues under your lens.
Repository: ABEP-VLEO simulator. Lane "${lane.key} — ${lane.title}" was built in worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}), base ${BASE}. Work READ-ONLY there; scratch scripts only under ${SP}/verify_${lane.key}_${lens}/. Never touch ${SP}/followon or ${SP}/wt_followon. Do NOT run Julia or the full test suite.
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
${LENSES[lens]}
Return pass=true only if no blocker/major issues remain.`
const fixPrompt = (lane, res, issues) => `Repair lane "${lane.key} — ${lane.title}" in its existing worktree ${res.worktree_path} (cd there; do NOT create a new worktree; stay on branch ${res.branch}).
${COMMON.split('YOUR LANE:')[0]}
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
Independent adversarial reviewers reported these issues — fix every blocker and major one (minors where cheap). Unsourceable claims: mark TBD/verify or remove. Non-reproducing numbers: find the true value, fix code and text. Revert anything outside ALLOWED paths.
ISSUES: ${JSON.stringify(issues)}
Commit the repair as a new commit in the same worktree (same trailer lines). Report as before.`

async function verifyBoth(lane, res, round) {
  const vs = await parallel(['evidence', 'rules'].map(lens => () =>
    agent(verifyPrompt(lane, res, lens), { label: `verify${round}:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
  const ok = vs.filter(Boolean)
  return { pass: ok.length === 2 && ok.every(v => v.pass), issues: ok.flatMap(v => v.issues || []) }
}

const lanes = ARGS_EMBEDDED.lanes
const laneMap = Object.fromEntries(lanes.map(l => [l.key, l]))
const promises = {}
function runLane(lane) {
  if (promises[lane.key]) return promises[lane.key]
  promises[lane.key] = (async () => {
    const deps = await Promise.all((lane.deps || []).map(k => runLane(laneMap[k])))
    const depText = deps.map((d, i) => d && d.res
      ? `- ${lane.deps[i]}: worktree ${d.res.worktree_path} (branch ${d.res.branch}, commit ${d.res.commit}), verified=${d.pass}; files: ${(d.res.files || []).join(', ')}; summary: ${d.res.summary}`
      : `- ${lane.deps[i]}: FAILED / unavailable — treat its deliverable as missing (TBD) and say so`).join('\n')
    if (deps.length) log(`${lane.key}: prerequisites ${lane.deps.join(', ')} finished — starting`)
    const res = await agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}` +
      (deps.length ? `\nPREREQUISITE LANES (finished; read their deliverables READ-ONLY from their worktrees, build on them, reference them by repository-relative path — they will be merged with yours; never copy them into your paths):\n${depText}` : ''),
      { label: `build:${lane.key}`, phase: 'Build', isolation: 'worktree', schema: RESULT })
    if (!res) return null
    let cur = res, v = await verifyBoth(lane, cur, 1), rounds = 0
    while (!v.pass && rounds < 2) {
      rounds++
      const fx = await agent(fixPrompt(lane, cur, v.issues), { label: `fix${rounds}:${lane.key}`, phase: 'Fix', schema: RESULT })
      if (fx) cur = fx
      v = await verifyBoth(lane, cur, rounds + 1)
    }
    log(`${lane.key}: done (verified=${v.pass}, fix rounds ${rounds}); unlocks: ${(cur.unlocks || []).join('; ').slice(0, 300)}`)
    return { lane: lane.key, res: cur, pass: v.pass, fix_rounds: rounds, open_issues: v.pass ? [] : v.issues }
  })()
  return promises[lane.key]
}
const results = await parallel(lanes.map(l => () => runLane(l)))
return results.map((r, i) => r || { lane: lanes[i].key, failed: true })
