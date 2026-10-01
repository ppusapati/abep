export const meta = {
  name: 'a9-7-consolidated-verification',
  description: 'A9.7: one consolidated adversarial verification of the design-synthesis batch F0-F9 + Rust kernels (six review dimensions), repair of blocker/major findings, re-review',
  phases: [
    { title: 'Review', detail: 'six independent dimensions, read-only' },
    { title: 'Repair', detail: 'one repair agent per round in an isolated worktree' },
    { title: 'Re-review', detail: 'dimensions with open findings re-check the repaired head' },
  ],
}

// args = { head: '<sha of the integrated execution branch>', main: 'eef8b85...' }
const HEAD = args.head
const MAIN = args.main
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'

const SCOPE = `SCOPE: everything on branch claude/nifty-ramanujan-w68f9z after main ${MAIN} (the protected post-checkpoint-5 baseline), i.e. git diff ${MAIN}..HEAD: the A9.7 architecture-freeze design-synthesis batch. READ the A9.7 directive in full (docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md + JSON recorder_notes). Components: F0 docs/performance/ + scripts/perf/; F1 abep_sim/design/intake_synthesis.py + docs/design_synthesis/f1_intake/; F2 abep_sim/design/filter_stage.py + docs/design_synthesis/f2_filter/; F3 abep_sim/design/compressor_synthesis.py + docs/design_synthesis/f3_compressor/; F4 abep_sim/design/plenum_feed.py + docs/design_synthesis/f4_plenum/; F5 docs/hardware/h1_freeze_candidate/; F6 abep_sim/design/icp_geometry_synthesis.py + docs/design_synthesis/f6_icp_geometry/; F7/F8 abep_sim/design/architecture_optimizer.py, robust_optimizer.py + docs/design_synthesis/f7_f8_optimizer/; F9 docs/architecture/freeze_candidate/; Rust abep_core/ + abep_sim/design/tpmc_backend.py + scripts/verify_abep_core.py + docs/performance/abep_core/; and their tests. Binding rules: CLAUDE.md rules 1-10 and the A9 section, docs/EVIDENCE.md, owner decisions A9-A9.7 (immutable), A9.7 specifics (Python authoritative; Rust kernels only with pre-registered parity, switchable, never authoritative; never convert TBD to an assumed value to obtain an optimum; hard constraints fail closed; Pareto sets not single optima; optimisation never changes evidence-gate status; architecture stays INVESTIGATION_HYPOTHESIS), the ten A9.2 statuses (never PASS), no winner, no Hall performance prediction (credible set empty, P5-N2 v1 INCONCLUSIVE), existing abep_sim modules unmodified and goldens unmoved, exactly 5 pytest skips repo-wide.`

const DIMS = {
  structural: `STRUCTURAL REVIEW: every builder in scope reproduces its outputs (--check) and none writes when checking; JSON parses and schemas valid; no stale 'PENDING' references to lanes that are now merged (F1-F9, Rust) - each cross-lane reference resolves to a real id/record; no circular sha pins and no pin of mutable governance files; no orphan owner questions (every new F0-F9/Rust question appears in the F9 roll-up with its source); existing abep_sim modules, hallthruster_bridge, abep_sim/data, decisions and all pre-A9.7 deliverables byte-identical to ${MAIN} (git diff --stat ${MAIN}..HEAD -- <paths>); large generated JSON files deterministic; abep_core/ does not break 'pip install --no-deps -e .' and the Rust target/ dir is not committed.`,
  physics: `PHYSICS / EVIDENCE REVIEW: independently re-derive and recompute (own Python under ${SP}/verify_physics/) the key physics: F1 TPMC-derived eta_c, C_D (reference area convention), K_back, CR_passive and the species recombination finding F1-01 (is the claimed production-convention error real and correctly quantified?), intake mass model; F2 filter conservation and the Livesey/Cole conductance if used; F3 compressor Gaede characteristic, the silent K clipping finding F3-01, rotor tip-speed / stress allowable (cited Ti-6Al-4V A-basis 827 MPa? verify the source), species-resolved outlet composition; F4 plenum mass balance, orifice molecular conductance, time constants, the 0.1 Pa domain cap propagation and the 0.38 mg/s flow-deficit finding; F5 magnetic-circuit lumped values and windows vs H2-1; F6 view factors; F7 mass/power bookkeeping (allocation vs CBE vs model never added); spot-check >= 6 external citations exist and say what is claimed (WebSearch/WebFetch via ToolSearch). Every TBD stays TBD in searches (no assumed values driving an optimum); PARAMETRIC_SENSITIVITY labels present wherever uncited coefficients drive numbers. Fabricated or mis-attributed citations are BLOCKERS.`,
  optimization: `OPTIMIZATION / DECISION-LOGIC REVIEW: Pareto filters correct (non-dominance with stated objective directions; ties; NaN/NOT_EVALUATED handling) in F1, F3, F4, F6, F7, F8; no single optimum silently selected anywhere (including F9's representative choices); hard constraints fail closed (an un-evaluable constraint is never satisfied); full-system ranking refuses while objectives are NOT_EVALUATED; robust filter never changes an evidence-gate status; synthetic fixtures never mix with real records; F9 freeze statuses consistent with the lanes (no FREEZE_CANDIDATE without evidence; status INVESTIGATION_HYPOTHESIS; FROZEN_REFERENCE_FLIGHT_ARCHITECTURE nowhere asserted). Write adversarial inputs to try to make an optimizer rank or pass with TBD/NOT_EVALUATED inputs.`,
  rust: `RUST / NUMERICS REVIEW: abep_core vs intake_tpmc.py semantic parity (read both line by line: entry sampling, diffuse/CLL kernels, tie rules, hit budget, outputs/dtypes); the parity pre-registration was committed BEFORE the scoring campaign (check git history order and that scoring used the pre-registered seed/tolerances unchanged); the verdict recomputes from the stored report (scripts/verify_abep_core.py --check, and --check --recompute on a subset if a build is available: build with maturin in ${SP}/venv_rust if needed); the backend switch never falls back silently; Python remains default and authoritative; DIV-01..03 documented; F0 profiling methodology sound (measurement vs contention, the port judgement basis).`,
  integration: `INTEGRATION REVIEW: interfaces between F1 -> F2 -> F3 -> F4 -> H-1 (F5) -> F7 and F6 -> F7 are consistent in units, species sets, conventions (partial pressure vs number flow; per-species mdot; p_passive) and status semantics; F4 reproduces Reservoir / DragCompressor exactly where claimed; the F7 design vector bounds match each lane; F9 parameter records trace to the lane outputs (spot-check >= 20 parameters: VALUE | TOLERANCE | EVIDENCE_CLASS | SOURCE | FREEZE_STATUS); owner-question roll-up complete; production-model issues (F1-01, F3-01, F3-02, G-05, DIV-01..03) correctly described.`,
  software: `SOFTWARE REVIEW (adversarial): write and run your own adversarial tests under ${SP}/verify_software/ (never commit them) against every new module in abep_sim/design/: invalid inputs (NaN/inf/negative/empty/wrong types), missing-data paths (each required field removed -> refusal or NOT_EVALUATED, never a number or PASS), out-of-domain inputs (refused, never extrapolated), determinism (builders byte-identical across two runs; seeded MC reproducible), no hidden defaults, no network/clock dependence, no writes outside lane dirs; test quality (do committed tests exercise the refusal paths; mutation-style spot checks); exactly 5 pytest skips repo-wide preserved (no new pytest.skip that could fire in CI with fetch-depth 0 and without abep_core built).`,
}

const FINDINGS = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
      file: { type: 'string' }, description: { type: 'string' }, evidence: { type: 'string', description: 'command/output or computation proving it' },
      fix_hint: { type: 'string' } }, required: ['severity', 'file', 'description', 'evidence'] } },
    checked: { type: 'array', items: { type: 'string' } },
    pass: { type: 'boolean' },
  },
  required: ['findings', 'checked', 'pass'],
}
const REPAIR = {
  type: 'object',
  properties: {
    worktree_path: { type: 'string' }, branch: { type: 'string' }, commit: { type: 'string' },
    fixed: { type: 'array', items: { type: 'string' } }, not_fixed: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string' } }, required: ['id', 'reason'] } },
    new_owner_questions: { type: 'array', items: { type: 'string' } },
    checks_run: { type: 'string' }, checks_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'fixed', 'not_fixed', 'checks_passed'],
}

const reviewPrompt = (dim, where, extra) => `You are an ADVERSARIAL reviewer in the ABEP A9.7 consolidated verification campaign (owner directives A9.6 sec. 18 and A9.7). Default to finding problems. Work READ-ONLY in ${where}; scratch only under ${SP}/verify_${dim}/. Do not run Julia or the full test suite (other agents do); you may run individual test files and builders' --check. Never touch ${SP}/followon or ${SP}/wt_followon.
${SCOPE}
${DIMS[dim]}
Report only real, evidenced problems (each with the command/computation that proves it). Severity: blocker = wrong physics/evidence fabrication/a PASS, freeze or winner that must not exist/rule violation/immutable file changed/broken build; major = wrong number, missing required behaviour, stale or dangling reference, missing refusal path, untested claim; minor = wording/cosmetic. pass=true only if no blocker/major.${extra || ''}`

phase('Review')
const where0 = `/home/user/abep at commit ${HEAD} (branch claude/nifty-ramanujan-w68f9z; do not modify, do not checkout other commits there - use 'git show'/'git diff' or a scratch 'git worktree add --detach ${SP}/ro_<dim> ${HEAD}' if you need a clean tree, and remove it afterwards)`
let reviews = await parallel(Object.keys(DIMS).map(dim => () =>
  agent(reviewPrompt(dim, where0), { label: `review:${dim}`, phase: 'Review', schema: FINDINGS }).then(r => ({ dim, r }))))
reviews = reviews.filter(Boolean)
const all = reviews.flatMap(x => (x.r?.findings || []).map((f, i) => ({ ...f, dim: x.dim, id: f.id || `${x.dim}-${i + 1}` })))
log(`review: ${all.length} findings (${all.filter(f => f.severity !== 'minor').length} blocker/major)`)

let open = all.filter(f => f.severity !== 'minor')
const minors = all.filter(f => f.severity === 'minor')
let repairs = [], rounds = 0, reReviews = [], worktree = null, branch = null, head = HEAD
while ((open.length || (rounds === 0 && minors.length)) && rounds < 3) {
  rounds++
  phase('Repair')
  const rp = await agent(`Repair round ${rounds} of the ABEP A9.7 consolidated verification. ${worktree
      ? `Continue in the existing worktree ${worktree} (cd there; stay on branch ${branch}; do NOT reset).`
      : `You run in an ISOLATED git worktree (your cwd). FIRST: git reset --hard ${HEAD}; confirm git rev-parse HEAD.`}
${SCOPE}
Fix EVERY blocker and major finding below (and the minors where cheap - round 1 only). Rules: never modify owner-decision files, immutable historical artifacts (list in the structural dimension), hallthruster_bridge, abep_sim/data, existing abep_sim modules, CLAUDE.md, docs/HISTORY.md, tests/test_sim.py; never invent numbers or citations (unsourceable -> TBD / 'verify'); never produce a PASS/closure the rules forbid; never answer a genuine owner question (register it in state v4 as TBD_OWNER instead, via its builder). After fixing, rebuild affected builders in dependency order (F2, F1, F3, F4, F5, F6, F7/F8, F9; perf baseline only with --check unless its sources changed) and run every scope builder's --check and every scope test file (tests/test_perf_baseline.py tests/test_design_f1_intake.py tests/test_design_f2_filter.py tests/test_design_f3_compressor.py tests/test_design_f4_plenum.py tests/test_h1_freeze_candidate.py tests/test_design_f6_icp_geometry.py tests/test_design_f7_f8_optimizer.py tests/test_architecture_freeze_candidate.py tests/test_tpmc_backend.py) plus scripts/verify_abep_core.py --check and python scripts/ci_checks.py; do not run the full suite. If a finding is wrong, say so with evidence in not_fixed (do not 'fix' correct behaviour). Commit (message ends with the two trailer lines:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U
). Do not push.
FINDINGS: ${JSON.stringify(rounds === 1 ? [...open, ...minors] : open)}`,
    worktree ? { label: `repair${rounds}`, phase: 'Repair', schema: REPAIR } : { label: `repair${rounds}`, phase: 'Repair', schema: REPAIR, isolation: 'worktree' })
  if (!rp) break
  repairs.push(rp)
  worktree = rp.worktree_path; branch = rp.branch; head = rp.commit
  const dims = [...new Set(open.map(f => f.dim))]
  if (!dims.length) break
  phase('Re-review')
  const rr = await parallel(dims.map(dim => () =>
    agent(reviewPrompt(dim, `the repaired worktree ${worktree} at commit ${head}`,
      `\nFOCUS: first confirm or refute each of these previously reported findings for your dimension (state FIXED / NOT_FIXED / WRONG_FINDING with evidence in 'checked'); then look for regressions introduced by the repair. Report remaining or new blocker/major issues only. Previous findings: ${JSON.stringify(open.filter(f => f.dim === dim))}. Repair notes (not_fixed with reasons): ${JSON.stringify(rp.not_fixed || [])}`),
      { label: `rereview${rounds}:${dim}`, phase: 'Re-review', schema: FINDINGS }).then(r => ({ dim, r }))))
  reReviews.push(rr.filter(Boolean))
  open = rr.filter(Boolean).flatMap(x => (x.r?.findings || []).filter(f => f.severity !== 'minor').map((f, i) => ({ ...f, dim: x.dim, id: f.id || `${x.dim}-r${rounds}-${i + 1}` })))
  log(`round ${rounds}: ${open.length} blocker/major remain`)
}
return { head: HEAD, final_head: head, worktree, branch, rounds, initial_findings: all, remaining_blocker_major: open,
  repairs, reviews: reviews.map(x => ({ dim: x.dim, pass: x.r?.pass, n: (x.r?.findings || []).length, checked: x.r?.checked })) }
