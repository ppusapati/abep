export const meta = {
  name: 'abep-parallel-lanes',
  description: 'Build independent ABEP work lanes in isolated worktrees; adversarially verify scope, provenance and tests; fix once if needed',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane' },
    { title: 'Verify', detail: 'adversarial scope / provenance / test audit' },
    { title: 'Fix', detail: 'single repair pass on failing lanes' },
    { title: 'Reverify', detail: 're-audit repaired lanes' },
  ],
}

const BASE = args.base
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. Base commit: ${BASE}.

CONTEXT: a pre-registered P5-N2 Hall-thruster validation campaign is RUNNING right now in the background and uses every CPU core. Its raw records live under /tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad/campaign_vac* — NEVER read, list or touch those, and never state or guess any campaign result.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths (listed below). In particular NEVER modify: hallthruster_bridge/prereg/**, hallthruster_bridge/campaign/**, hallthruster_bridge/propellants/**, hallthruster_bridge/audit/**, hallthruster_bridge/ensemble/**, hallthruster_bridge/cases/p5_n2.json, hallthruster_bridge/bridge_lib.jl, hallthruster_bridge/PINNED.toml, scripts/score_p5_n2_campaign.py, scripts/audit_p5_n2_campaign_records.py, scripts/freeze_p5_n2_dataset.py, scripts/score_p5_n2_frozen.py, scripts/report_p5_n2_campaign.py, scripts/make_validation_release.py, abep_sim/data/**, golden data, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py. (The owner integrates HISTORY/CLAUDE entries later.)
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed) or is explicitly "TBD — requires <what>". Anything recalled from memory without a verified source is marked "verify". Published / openly accessible sources only; do not contact any person or lab; no email; do not use LXCat; do not bypass paywalls or bot challenges; never change TLS/trust settings. Cite URLs/DOIs you actually accessed.
3. CPU: do NOT run Julia, do NOT run the full test suite, do NOT run long computations. You may run only your own new test file (python -m pytest -q <your test file>) and quick scripts (< 1 min).
4. Do not change physics, thresholds, frozen data, chemistry or the running campaign. Do not claim demonstrated ABEP closure, an architecture winner, or any transport admission. No retuning suggestions.
5. When done: git add your files and commit in the worktree with a clear message whose last two lines are exactly:
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
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'open_questions_for_owner', 'tests_passed'],
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

const verifyPrompt = (lane, res) => `You are an ADVERSARIAL reviewer. Default to finding problems; pass only if there are no blocker or major issues.
Repository: ABEP-VLEO simulator. Lane "${lane.key} — ${lane.title}" was built in worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}), base ${BASE}. Work read-only in that directory (cd there). Never read or touch /tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad/campaign_vac*. Do NOT run Julia or the full test suite (CPU is reserved for a running campaign).
Lane brief: ${lane.prompt}
ALLOWED paths for this lane: ${lane.allowed.join(', ')}

Check, and report each as an issue if violated:
1. SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD — every changed path must be within the ALLOWED paths; no frozen/forbidden file touched (prereg, campaign, propellants, audit, ensemble, cases/p5_n2.json, bridge_lib.jl, PINNED.toml, frozen scorer/gate/freeze/report/release scripts, abep_sim/data, HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py). Uncommitted leftovers count as issues.
2. PROVENANCE: open the deliverables. Every numeric value must have a source + evidence class, or be marked TBD/verify. Flag invented-looking numbers, unsourced claims, wrong or fabricated citations. Spot-check at least 3 cited sources with WebFetch/WebSearch (DOI/URL resolves, title/authors match, the cited value plausibly appears there if accessible). Flag any claim of a P5-N2 campaign result, architecture winner, transport admission or demonstrated closure (blocker).
3. CORRECTNESS: schemas/JSON/TOML parse; code is consistent with the repository modules it references (names/fields actually exist — grep them); the lane's own test file passes (run only that file).
4. USEFULNESS vs the brief: required deliverables present; open questions are genuine owner decisions.
Return pass=true only if no blocker/major issues remain.`

const fixPrompt = (lane, rv) => `Repair lane "${lane.key} — ${lane.title}" in its existing worktree ${rv.res.worktree_path} (cd there; do NOT create a new worktree; stay on branch ${rv.res.branch}).
${COMMON.split('YOUR LANE:')[0]}
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
An adversarial reviewer reported these issues — fix every blocker and major one (and minors where cheap); if a flagged claim cannot be sourced, mark it TBD/verify or remove it rather than inventing support. If something was changed outside ALLOWED paths, revert it (git checkout ${BASE} -- <path> or delete new files).
ISSUES: ${JSON.stringify(rv.v ? rv.v.issues : [{severity: 'major', description: 'reviewer unavailable: re-check the whole lane against the brief'}])}
Commit the repair as a new commit in the same worktree (same trailer lines). Report as before.`

const lanes = args.lanes
const results = await pipeline(
  lanes,
  lane => agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}`,
    { label: `build:${lane.key}`, phase: 'Build', isolation: 'worktree', schema: RESULT }),
  (res, lane) => res ? agent(verifyPrompt(lane, res), { label: `verify:${lane.key}`, phase: 'Verify', schema: VERDICT })
    .then(v => ({ res, v })) : null,
  (rv, lane) => {
    if (!rv) return null
    if (rv.v && rv.v.pass) return rv
    return agent(fixPrompt(lane, rv), { label: `fix:${lane.key}`, phase: 'Fix', schema: RESULT })
      .then(fx => ({ res: fx || rv.res, v: rv.v, fixed: true }))
  },
  (rv, lane) => {
    if (!rv || !rv.fixed) return rv
    return agent(verifyPrompt(lane, rv.res), { label: `reverify:${lane.key}`, phase: 'Reverify', schema: VERDICT })
      .then(v2 => ({ ...rv, v2 }))
  },
)
return results.map((r, i) => ({ lane: lanes[i].key, ...(r || { failed: true }) }))
