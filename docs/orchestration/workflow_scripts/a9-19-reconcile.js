export const meta = {
  name: 'a9-19-reconcile',
  description: 'Reconcile A9.19/A9.20 edits lost in "take theirs" conflict resolution with the A9.16 finalize repairs: 3 parallel area lanes, then integration + full suite (both CI legs) + quick review',
  phases: [{ title: 'Reconcile' }, { title: 'Integrate' }],
}
// args = { base }
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const TRAILER = `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U`
const RESULT = { type: 'object', properties: { commit: { type: 'string' }, applied: { type: 'array', items: { type: 'string' } },
  blocked: { type: 'array', items: { type: 'string' } }, tests: { type: 'string' } }, required: ['commit', 'applied', 'blocked', 'tests'] }
const common = (base) => `ABEP-VLEO repository (GitHub ppusapati/abep), ISOLATED git worktree (cwd). FIRST: git reset --hard ${base}; confirm git rev-parse HEAD. Read CLAUDE.md.
SITUATION: HEAD merges two independent lines of work that both edited the same files: (A) the A9.19/A9.20 application (owner decisions docs/decisions/OD_2026_10_01_A9_19_* and A9_20_*: flight = one Hall + one RF/ICP neutralizer for air and Xe, two supply modes, Xe contingency/emergency, NO hollow cathode, C1 ground-only lab reference) - lane commits 8f0cd87 (budgets), b5b2ddc (RVM + RFQ v3), baf4791 (design + P1/P2), all on base f55abf6; and (B) the A9.16 finalize regeneration + review repairs (commits 760433a, 71a1e9e, 05a0e92, 46ff2d1, 0562805). Conflicts were resolved by TAKING (B)'s version wholesale for these files, so (A)'s edits in them are LOST: docs/architecture/freeze_candidate/{build_freeze_candidate.py, outputs}; docs/budgets/mass_power_a9_v3/{build_mass_power_a9_v3.py, json}; docs/budgets/xe_accounting_a9_v3/{build_xe_accounting_a9_v3.py, json}; docs/requirements/rvm_a9/{build_rvm_a9.py, RVM_A9.md}; tests/test_mass_power_a9_v3.py, tests/test_rvm_a9.py, tests/test_xe_accounting_a9_v3.py; abep_sim/design/architecture_optimizer.py; abep_sim/design/compressor_synthesis.py; plus generated outputs in docs/architecture_comparison/**, docs/design_synthesis/f3,f4,f7_f8.
TASK: for your area, re-apply (A)'s semantic changes on top of (B)'s current content (use git diff f55abf6 <laneCommit> -- <file> to see (A)'s change, and git diff f55abf6 HEAD -- <file> for the combined state). KEEP every (B) repair (e.g. RFP-01: RVM refs to *_v3 artifacts; RVF-01/PHY-01 domain_gated_run in feed-state closure; S6.8 statuses). Then regenerate your area's generated outputs with their builders (never hand-edit generated JSON/MD) and run your area's tests + builders --check.
RULES: CLAUDE.md rules 1-10; never invent values; never weaken/skip tests; never modify docs/decisions/**, CLAUDE.md, frozen data, immutable history. Touch only your ALLOWED paths. Commit; message ends with exactly:
${TRAILER}
Do NOT push. Never touch ${SP}/followon or ${SP}/wt_followon. Return the structured result.

YOUR AREA: `
const AREAS = [
  { key: 'budgets', prompt: `BUDGETS - lane (A) commit 8f0cd87. ALLOWED: docs/budgets/mass_power_a9_v3/**, docs/budgets/xe_accounting_a9_v3/**, tests/test_mass_power_a9_v3.py, tests/test_xe_accounting_a9_v3.py.` },
  { key: 'reqproc', prompt: `RVM + RFQ - lane (A) commit b5b2ddc. ALLOWED: docs/requirements/rvm_a9/**, docs/procurement/rfq_a9_v3/**, tests/test_rvm_a9.py, tests/test_rfq_a9_v3.py. (B)'s RFP-01 repair re-pointed RVM REFS to mass_power_a9_v3 / xe_accounting_a9_v3 / rfq_a9_v3: keep it, and make the RVM consistent with the A9.19 single flight configuration.` },
  { key: 'design', prompt: `DESIGN - lane (A) commit baf4791. ALLOWED: abep_sim/design/**, docs/architecture/freeze_candidate/**, docs/hardware/h1_freeze_candidate/**, docs/design_synthesis/**, docs/architecture_comparison/**, tests/test_design_*.py, tests/test_architecture_freeze_candidate.py, tests/test_h1_freeze_candidate.py, tests of architecture_comparison artifacts. Regenerate in dependency order (F3 -> F4 -> F7/F8 -> compressor_downselect / feed_state closure -> H-1 -> F9 freeze candidate).` },
]
phase('Reconcile')
const res = await parallel(AREAS.map(a => () => agent(common(args.base) + a.prompt, { label: `reconcile:${a.key}`, phase: 'Reconcile', schema: RESULT, isolation: 'worktree' })))
const cs = res.filter(r => r && r.commit).map(r => r.commit)
phase('Integrate')
const integ = await agent(common(args.base) + `INTEGRATE (ALLOWED: any non-immutable path). git merge --no-ff each of ${cs.join(', ')} (messages end with the trailer). Resolve conflicts in generated files by re-running builders; docs/HISTORY.md keep both sides. Then run EVERY builder --check (git ls-files '*build*.py' except the v1 consolidated-questions builder; python -m abep_sim.golden check; python scripts/ci_checks.py; scripts/verify_abep_core.py --check; scripts/perf/profile_baseline.py --check) and regenerate stale ones in dependency order (budgets -> RVM -> state v5 -> application matrix -> M16; design chain -> F9). Then the FULL suite in both CI legs: (i) normal and (ii) pymsis hidden via a sitecustomize import blocker on PYTHONPATH, each with --junitxml and python scripts/ci_checks.py --pytest-junit <xml>; both must pass rule 9 (all pass, exactly 5 SUPERSEDED skips, 1 strict xfail). Fix any remaining root cause and rerun. Finally verify A9.19 holds end to end: grep that no flight configuration lists hall_c1_reference or a hollow cathode; Xe role CONTINGENCY_EMERGENCY; C1 GROUND_ONLY. Report both rule-9 results.`,
  { label: 'integrate', phase: 'Integrate', schema: RESULT, isolation: 'worktree' })
return { base: args.base, reconcile: res, integ }
