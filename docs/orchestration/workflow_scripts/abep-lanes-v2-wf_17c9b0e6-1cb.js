export const meta = {
  name: 'abep-lanes-v2',
  description: 'Build ABEP work lanes in isolated worktrees; two-lens adversarial verification (evidence + rules/recompute); up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const BASE = args.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. Base commit: ${BASE} (main after PR #30).

CONTEXT (read CLAUDE.md in your worktree first):
- The pre-registered P5-N2 v1 vacuum validation is FINAL: all 9 SGB screening candidates INCONCLUSIVE / NOT ELIGIBLE (not rejected); 1428 of 2160 run x reading evaluations OUT_OF_DOMAIN (chemistry tables used beyond their validity limit), 700 FAIL_VALIDATION, 32 PASS, 0 NUMERICAL_FAILURE; credible set = empty; gate 3 FAIL. Frozen files: hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz (1080 records), ..._scores.json (official per-run statuses), ..._scores_report.md, ..._scores_decision.json, VALIDATION_RELEASE_v1.json. The v1 outcome is PERMANENT and is never rewritten.
- Pre-registered follow-on runs (O4 staged sensitivities, then 1080 facility runs) are RUNNING in the background on every CPU core under ${SP}/followon and ${SP}/wt_followon — NEVER read, list, modify or touch those paths.
- Earlier non-gating forensic notes (unreviewed unless stated) may exist read-only under ${SP}/forensics/ — you may read them as cross-checks, never as authority; recompute anything you report.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths (listed below). NEVER modify: hallthruster_bridge/prereg/**, hallthruster_bridge/campaign/**, hallthruster_bridge/propellants/** (incl. rate_validity.toml), hallthruster_bridge/audit/**, hallthruster_bridge/ensemble/**, hallthruster_bridge/validation/**, hallthruster_bridge/cases/**, bridge_lib.jl, PINNED.toml, the frozen scorer/gate/freeze/report/release/staged scripts (scripts/score_p5_n2_*.py, scripts/audit_p5_n2_campaign_records.py, scripts/freeze_p5_n2_dataset.py, scripts/report_p5_n2_campaign.py, scripts/make_validation_release.py, scripts/make_p5_n2_launch_manifests.py), abep_sim/archengine.py, abep_sim/hall_ensemble.py, abep_sim/hall_map.py, abep_sim/data/**, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py.
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page/table numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed) or is explicitly "TBD — requires <what>". Numbers computed from repository data must be produced by a script you commit (deterministic, re-runnable).
3. Sources: published / openly accessible only; do not contact any person or lab; no email; do not use LXCat; do not bypass paywalls or bot challenges (abstract-only access must be labelled as such); never change TLS/trust settings. Cite DOIs/URLs you actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch). Anything from memory is marked "verify". The ECHT thesis (CC BY-NC-ND) is never redistributed; cite numbers only.
4. CPU: do NOT run Julia, do NOT run the full test suite, do NOT run long computations (> 1 min). Run only your own new test file (python -m pytest -q <your test file>) and quick scripts.
5. No retuning of any transport/chemistry parameter, no proposal to change criteria/tolerances/limits of v1, no re-scoring or re-labelling of any v1 run (read official statuses from the scores file), no "would pass if", no words like "best candidate"/"recommended candidate"/"promote" for screening candidates. Do not claim demonstrated ABEP closure, an architecture winner, or any transport admission. Never extend a rate-table validity limit merely because the solver reached a higher T_e; any extension needs independent published evidence and is a DRAFT for the owner only.
6. When done: git add your files and commit in the worktree with a clear message whose last two lines are exactly:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U
Do NOT push. Report the worktree absolute path (pwd), branch name (git rev-parse --abbrev-ref HEAD) and commit sha.

YOUR LANE:
`

const RESULT = {
  type: 'object',
  properties: {
    worktree_path: { type: 'string' }, branch: { type: 'string' }, commit: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    key_findings: { type: 'array', items: { type: 'string' } },
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'key_findings', 'open_questions_for_owner', 'tests_passed'],
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
  evidence: `EVIDENCE LENS. Open every deliverable. (a) Spot-check at least 6 cited sources with WebSearch/WebFetch (load via ToolSearch): the DOI/URL resolves, title/authors/year match, and the cited value/range plausibly appears there when accessible (abstract-only must be labelled). Fabricated or mis-attributed citations are BLOCKERS. (b) Every numeric value has a source + evidence class or is TBD/verify; invented-looking numbers are major. (c) Values taken from repository files: open those files and confirm they match. (d) Any claim of a v1 result change, transport admission/promotion, architecture winner, demonstrated closure, or a validity-limit extension presented as decided is a BLOCKER.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD — every changed path within ALLOWED paths; no forbidden file touched; no uncommitted leftovers (git status). (b) RECOMPUTE: for every headline number derived from repository data, write your own short independent Python (do NOT reuse the lane's script) against the frozen inputs and compare; any mismatch beyond rounding is major. (c) CORRECTNESS: JSON/TOML parse; code is consistent with the repository modules/fields it references (grep them); run ONLY the lane's own test file; it must pass and must actually test something meaningful. (d) RULES: no retuning suggestions, no v1 re-scoring/re-labelling, no forbidden wording ("best/recommended candidate", "promote", "would pass if"), DRAFT/proposal markers present where the brief demands them, v1 described as permanent. (e) USEFULNESS: every required deliverable in the brief is present and substantive.`,
}
const verifyPrompt = (lane, res, lens) => `You are an ADVERSARIAL reviewer. Default to finding problems; pass only if there are no blocker or major issues under your lens.
Repository: ABEP-VLEO simulator. Lane "${lane.key} — ${lane.title}" was built in worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}), base ${BASE}. Work READ-ONLY in that directory (cd there); write any scratch scripts only under ${SP}/verify_${lane.key}_${lens}/. Never read or touch ${SP}/followon or ${SP}/wt_followon. Do NOT run Julia or the full test suite.
Lane brief: ${lane.prompt}
ALLOWED paths for this lane: ${lane.allowed.join(', ')}
${LENSES[lens]}
Return pass=true only if no blocker/major issues remain.`

const fixPrompt = (lane, res, issues) => `Repair lane "${lane.key} — ${lane.title}" in its existing worktree ${res.worktree_path} (cd there; do NOT create a new worktree; stay on branch ${res.branch}).
${COMMON.split('YOUR LANE:')[0]}
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
Independent adversarial reviewers reported these issues — fix every blocker and major one (and minors where cheap). If a flagged claim cannot be sourced, mark it TBD/verify or remove it rather than inventing support. If a number did not reproduce, find the true value and fix the script and text. If something was changed outside ALLOWED paths, revert it (git checkout ${BASE} -- <path> or delete new files).
ISSUES: ${JSON.stringify(issues)}
Commit the repair as a new commit in the same worktree (same trailer lines). Report as before.`

async function verifyBoth(lane, res, round) {
  const vs = await parallel(['evidence', 'rules'].map(lens => () =>
    agent(verifyPrompt(lane, res, lens), { label: `verify${round}:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
  const ok = vs.filter(Boolean)
  const issues = ok.flatMap(v => v.issues || [])
  return { pass: ok.length === 2 && ok.every(v => v.pass), issues, verdicts: ok }
}

const lanes = args.lanes
const results = await pipeline(
  lanes,
  lane => agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}`,
    { label: `build:${lane.key}`, phase: 'Build', isolation: 'worktree', schema: RESULT }),
  async (res, lane) => {
    if (!res) return null
    let cur = res, v = await verifyBoth(lane, cur, 1), rounds = 0
    while (!v.pass && rounds < 2) {
      rounds++
      const fx = await agent(fixPrompt(lane, cur, v.issues), { label: `fix${rounds}:${lane.key}`, phase: 'Fix', schema: RESULT })
      if (fx) cur = fx
      v = await verifyBoth(lane, cur, rounds + 1)
    }
    return { res: cur, pass: v.pass, fix_rounds: rounds, open_issues: v.pass ? [] : v.issues }
  },
)
return results.map((r, i) => ({ lane: lanes[i].key, ...(r || { failed: true }) }))
