export const meta = {
  name: 'a9-6-consolidated-verification',
  description: 'A9.6 sec. 18: one consolidated adversarial verification of the integrated A9.3-A9.6 implementation (six review dimensions), repair of blocker/major findings, re-review',
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

const SCOPE = `SCOPE: everything on branch claude/nifty-ramanujan-w68f9z after main ${MAIN} (the protected post-A9.4 baseline), i.e. git diff ${MAIN}..HEAD. The integrated A9.3-A9.6 implementation: owner decisions A9.5/A9.6 (docs/decisions/OD_2026_09_30_A9_5_*, A9_6_*: READ the A9.6 directive in full - sec. 18 defines this campaign), P1 docs/experiments/hall_icp/p1_icp_bench/, P2 docs/experiments/hall_icp/p2_impedance_map/, P3 docs/experiments/hall_icp/p3_coupled_thermal/, P4 docs/experiments/hall_icp/p4_anode_materials/, mass/power docs/budgets/mass_power_a9_v2/, Xe docs/budgets/xe_accounting_a9_v2/, RFQ v2 docs/procurement/rfq_a9_v2/, RVM docs/requirements/rvm_a9/, owner-question state v4 docs/budgets/owner_decisions/*state_v4*, M16 v4 docs/experiments/hall_icp/integration/m16_v4/, and their tests. Build order when rebuilding: P4, XE, P1, P2, P3, MP, RFQ, then state v4, RVM, M16 v4. Binding rules: CLAUDE.md (rules 1-10, the A9 section), docs/EVIDENCE.md, owner decisions A9 and A9.1-A9.6 (immutable), the ten A9.2 statuses (never PASS), no winner, no Hall performance prediction (credible set empty, P5-N2 v1 INCONCLUSIVE).`

const DIMS = {
  structural: `STRUCTURAL REVIEW: (a) every builder in scope reproduces its outputs (--check) and none writes when asked to check; (b) all JSON parse and every JSON Schema file in scope is a valid schema (install jsonschema into ${SP}/venv_verify_structural if needed: python -m venv + pip; never into the repo); (c) no stale references: grep the scope for 'PENDING ', dangling ids (every cited id of the form P1-*, IDP2-*, P3-*, PR-*, MPV2-*, XV2-*, RF-L*, RFQ2-*, RVM-*, XL-*, state-v4 ids resolves in its target JSON), references to superseded files as current (e.g. the RVM still reading owner-question state v3 while v4 exists - decide whether that is stale); (d) no orphan questions: every open question raised in any package JSON is a row of state v4, and every state-v4 row's source resolves; (e) no circular sha pins (build the pin graph across all builders in scope + everything they pin; report cycles) and no pin of a mutable governance file; (f) immutable historical artifacts unchanged vs main ${MAIN}: owner decisions A4-A9.4, frozen data, hallthruster_bridge, H2 v1, xe_ledger v1/A9, mass_bom v1, mass_a9 v1, M16 v1/v2/v3, owner-question v1/v2/v3 (+ builders), rfq_a9 v1, A9-01..A9-10 deliverables (use git diff --stat ${MAIN}..HEAD -- <paths>).`,
  physics: `PHYSICS / EVIDENCE REVIEW: (a) no unsupported assumption promoted: every numeric value has a source + evidence class or is TBD; nothing labelled measured/validated without an artifact; allocations never presented as CBE; owner-stated values labelled as such; (b) equations dimensionally correct - independently re-derive and re-compute (your own Python under ${SP}/verify_physics/) the key formulas: view factors (spot-check the Howell catalogue formulas used in P3 against the cited source), gray-body radiation exchange, collector energy deposition terms (Goebel & Katz citations: check equation/page), plume interception, reflection coefficient/VSWR/delivered power, SOL calibration and de-embedding cascades in P2, GUM propagation (JCGM 100 clauses cited), Kirchhoff/capacity formulas in P1, Xe tank volumes vs NIST density at 323 K, mass roll-ups; (c) evidence classes correct and literature values not scaled beyond their applicability domain (e.g. Takahashi Ar anchor 70 sccm ~ 2.1 mg/s used only as an engineering anchor; material properties at the right temperature); (d) current/power/mass boundaries correct: P_bus boundary (A9-02, 1 ms window), mains lab generator never in P_bus or the flight BOM, G-REUSE m_Xe,ICP = 0, residual/reserve booked once; (e) spot-check at least 6 external citations actually exist and say what is claimed (WebSearch/WebFetch via ToolSearch; open sources only). Fabricated or mis-attributed citations are BLOCKERS.`,
  electrical: `ELECTRICAL REVIEW: current sign conventions (A9.5: conventional current INTO the registered network positive; every channel transformed), Kirchhoff closure implementation in the P1 reducer (R_I = sum I_k; u_R RSS or covariance; |R_I| <= 3 u_R AND |R_I|/max(|I_e,collector|, I_scale,min) <= 0.02 as fixed owner constants; NOT_EVALUATED_INSTRUMENT when 3 u_R > 0.02 |I_e,collector|; I_scale,min registered, no default; no silently zeroed channel), I_e,cap = I_on - I_off signed (no abs, no clipping, negative kept), grounding (H-1 body single-point metered ground; anode physically disconnected and floating for capacity records; OPEN_CIRCUIT_BY_CONSTRUCTION semantics), isolation (350 V class, >= 525 V design withstand, 1.05 kV DC / 60 s DWV, gas isolators ~1 kV only where potentials are bridged), RF reference planes and matching (generator -> coupler -> 50-ohm line -> local adjustable match -> antenna; forward/reflected on the 50-ohm side; P_forward never P_plasma; delivered power refused when line/match loss unverified), peak-voltage/current calculations on match elements and feedthroughs (re-derive independently for a lossless L/pi/T network example and compare with p2_framework), 8.33 A only as the stand ceiling, ICP-45 NOT_EVALUATED until I_d,max,H1 registered. Run adversarial inputs against the reducers.`,
  thermal: `THERMAL REVIEW (P3 + P4 + A9.2 statuses): ICP obstruction of H-1's view (view-factor calculator, reciprocity/summation, the parametric study labelled PARAMETRIC_STUDY_NOT_A_DESIGN), plume interception (only measured distributions as evidence; test distributions labelled), collector heating (electron/ion energy deposition terms, sheath fall; P3Q-01 probe vs calorimetry kept TBD_OWNER), anode heating and the A9-07 13 W pole warning carried, radiative view and node-network energy balance closure (re-run the H2-5 reproduction check), material limits (P4: T_operating <= T_validated,continuous - 50 K; no invented limits; 316L REJECTED_AS_CURRENT_BASELINE; FINAL_ANODE_MATERIAL OPEN; no selection by melting point), and that NO output anywhere produces a thermal PASS / closure (ICP_COUPLED_THERMAL and ANODE_THERMAL_CLOSURE UNRESOLVED everywhere, incl. RVM and M16 v4). Recompute independently where numbers are shown.`,
  metrology: `METROLOGY REVIEW: uncertainty propagation (P1 u(I_k) components, u_R, u(I_e,cap), margin rule u_I_e/u_I_d_max, P1Q-19 treatment; P2 linear GUM + seeded Monte Carlo agree on a test case; JCGM 100/101 clause citations correct), RF power metrology (coupler directivity/coupling corrections, power-sensor uncertainty, |Gamma| bounds, loss verification at power with coverage factor k TBD), current channels (resolution, zero/offset, RF pickup check), thrust metrology (stand requirements carried: 1 % k=1 target UBQ-01, in-situ SI-traceable calibration rows 115-121 - check RFQ/P1 carry them and nothing claims thrust), gas flow (Ar 1-2 MFC ranges with rate-of-rise/transfer calibration; N2/O2 four overlapping ranges row 123; Xe C1 controllers), photodiode classification (threshold from dark/background, RF-powered known-unlit and known-lit P1 records, frozen before the map; UNCERTAIN rules; LOS loss/saturation invalid; P1 and P2 classifiers agree). Every instrument in P1/P2 maps to an RFQ line or an explicit not-procured disposition.`,
  software: `SOFTWARE REVIEW (adversarial): for every reducer/framework/builder in scope, write and run your own adversarial tests under ${SP}/verify_software/ (never commit them): invalid inputs (wrong types, NaN/inf, negative where impossible, empty lists, duplicate ids), synthetic-data contamination (synthetic mixed with measured anywhere -> refused), missing-data paths (every required field removed one at a time -> refusal or NOT_EVALUATED, never PASS/default), OOD records (OUT_OF_DOMAIN distinct from FAIL, never counted as FAIL), determinism (builders byte-identical across two runs, seeded MC reproducible), no hidden defaults, no network or clock dependence in builds, no writes outside the lane dir, test quality (do the committed tests actually exercise the refusal paths they claim; mutation-style spot checks: flip a comparison in a copy and see a test fail). Also: exactly the expected skip/xfail state is preserved (no new pytest.skip in scope that could fire in CI; CI uses actions/checkout fetch-depth 0).`,
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

const reviewPrompt = (dim, where, extra) => `You are an ADVERSARIAL reviewer in the ABEP A9.6 consolidated verification campaign (owner directive A9.6 sec. 18). Default to finding problems. Work READ-ONLY in ${where}; scratch only under ${SP}/verify_${dim}/. Do not run Julia or the full test suite (other agents do); you may run individual test files and builders' --check. Never touch ${SP}/followon or ${SP}/wt_followon.
${SCOPE}
${DIMS[dim]}
Report only real, evidenced problems (each with the command/computation that proves it). Severity: blocker = wrong physics/evidence fabrication/a PASS or winner that must not exist/rule violation/immutable file changed/broken build; major = wrong number, missing required behaviour, stale or dangling reference, missing refusal path, untested claim; minor = wording/cosmetic. pass=true only if no blocker/major.${extra || ''}`

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
  const rp = await agent(`Repair round ${rounds} of the ABEP A9.6 consolidated verification. ${worktree
      ? `Continue in the existing worktree ${worktree} (cd there; stay on branch ${branch}; do NOT reset).`
      : `You run in an ISOLATED git worktree (your cwd). FIRST: git reset --hard ${HEAD}; confirm git rev-parse HEAD.`}
${SCOPE}
Fix EVERY blocker and major finding below (and the minors where cheap - round 1 only). Rules: never modify owner-decision files, immutable historical artifacts (list in the structural dimension), hallthruster_bridge, abep_sim/data, existing abep_sim modules, CLAUDE.md, docs/HISTORY.md, tests/test_sim.py; never invent numbers or citations (unsourceable -> TBD / 'verify'); never produce a PASS/closure the rules forbid; never answer a genuine owner question (register it in state v4 as TBD_OWNER instead, via its builder). After fixing, rebuild in the order P4, XE, P1, P2, P3, MP, RFQ, state v4, RVM, M16 v4 and run every scope builder's --check and every scope test file (tests/test_p1_icp_bench.py tests/test_p2_impedance_prep.py tests/test_p2_impedance_framework.py tests/test_p3_coupled_thermal.py tests/test_p4_anode_materials.py tests/test_mass_power_a9_v2.py tests/test_xe_accounting_a9_v2.py tests/test_rfq_a9_v2.py tests/test_rvm_a9.py tests/test_owner_questions_state_v4.py tests/test_m16_v4.py tests/test_owner_questions_state_v3.py) and python scripts/ci_checks.py; do not run the full suite. If a finding is wrong, say so with evidence in not_fixed (do not 'fix' correct behaviour). Commit (message ends with the two trailer lines:
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
