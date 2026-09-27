export const meta = {
  name: 'a6-xe-ledger',
  description: 'A6 follow-on fo_xe_system_ledger (attempt 2, one lane per workflow for parallelism); two-lens verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; all four lanes build simultaneously' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "302e1c94b3bddeb005f17bb189407f2e4641519a", "lanes": [{"key": "XELEDGER", "title": "fo_xe_system_ledger", "allowed": ["abep_sim/xe_ledger.py", "docs/budgets/xe_ledger/**", "tests/test_xe_ledger.py"], "prompt": "Registered follow-on fo_xe_system_ledger (trigger T_A5_XE_LEDGER, owner addendum A6). Build a PARAMETRIC Xe mass and stored-Xe subsystem ledger. New pure module abep_sim/xe_ledger.py (not wired into archengine; no hidden defaults; every input explicit; missing inputs raise) implementing exactly: m_cathode = mdot_cathode * t_firing; m_startup = N_starts * t_startup * mdot_startup; m_transition = N_transitions * t_transition * mdot_transition; m_fallback = t_fallback_max * mdot_fallback; m_reserve = explicit policy term (define the allowed policy forms, e.g. fraction of the sum of the other terms OR absolute mass, the owner chooses; never folded into another category); m_Xe_total = sum of the five; and the stored-Xe SUBSYSTEM mass m_Xe_subsystem = m_Xe + m_tank + m_regulator + m_valves + m_plumbing + m_mounting/thermal (the owner decides on THIS, not propellant alone) with m_tank from an explicit tank model input (tankage fraction or tank mass as input with source; do not invent). Report the subsystem mass against the 40 kg requirement AND the A5 34-36 kg design allocation, as a share, never as a prediction. The only fixed design term is the cathode per A5: 0.10 mg/s over 15,000 firing hours = 5.4 kg (recompute and show; 0.15 mg/s = 8.1 kg as the A5 experimental upper test point only). N_starts, t_startup, mdot_startup, N_transitions, t_transition, mdot_transition, t_fallback_max, mdot_fallback, reserve policy and all hardware masses are PARAMETERS: status TBD - requires H-1/C-1 measurement or procurement selection; where published analogue data exist in the base (e.g. docs/evidence/cathode, docs/evidence/hall_sustainment Xe start-then-transition entries, lane 19 cathode integration, lane 21 mass_bom, veto layer RI-MASS-CATHODE-XE) you may give ILLUSTRATIVE sensitivity ranges clearly labelled analogue/illustrative with their source and evidence class, never as the allocation. Deliver: docs/budgets/xe_ledger/XE_LEDGER.md, a machine-readable docs/budgets/xe_ledger/xe_ledger_v1.json (parameter table with units, status, source, what closes it; the cathode term computed; sensitivity surfaces, e.g. the maximum allowable t_fallback_max or N_starts before the stored-Xe subsystem breaches a stated share of the mass allocation, as functions of the TBD parameters), a deterministic builder script there, and the tests. Explicitly respect A6 not_authorized: no total Xe mass frozen, no startup/transition/fallback point values frozen. Milestone statement required. Provide named SCENARIOS (e.g. cathode-only minimum, nominal-restart, heavy-restart, fallback-limited) as explicit parameter sets labelled scenario/illustrative with the source of each assumption; startup, transition and fallback stay symbolic or scenario-based until H-1/C-1 measure them. Pin A5/A6 and the G0 record by sha256."}]}
const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. FIRST run: git reset --hard ${BASE} (the worktree is created from main, which lacks the governance and decision files) and confirm with: git rev-parse HEAD. Base commit: ${BASE}.

CONTEXT (read CLAUDE.md in your worktree first):
- RFP envelope (DRDO TDF, CLAUDE.md): 180-230 km, 12-25 mN, < 1.5 kW, < 40 kg, 26,000 h mission, > 15,000 h firing, Hall preferred, air + Xe.
- OWNER DECISIONS YOU WORK UNDER (read both first; cite them by path AND sha256, they are immutable): A5 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json (Proposal Reference Architecture / Phase-1 Baseline: dual-feed extended-channel Hall, atmospheric primary feed, Xe only for ignition + shielded Xe-fed LaB6 cathode + time-limited contingency, RF pre-ionizer interface reserved (not baseline flight hardware), ECR alternate; H-1 Phase 1 decides the branch A hall_only / B rf_hall / C ecr_hall / NO_VIABLE_CASE) and A6 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json (your authorization, the 'not_authorized' list and the execution-order clarification). Bundle 1 stays NO_BASELINE_YET; the credible Hall set is EMPTY; A5 numbers are ALLOCATIONS or REQUIREMENTS, never predictions.
- Architecture branch ids used exactly: 'hall_only', 'rf_hall', 'ecr_hall'. Never declare a winner.
- PINNING: pin only immutable inputs (decision files, verified deliverables, snapshots) by sha256; NEVER pin mutable governance files (lane_registry_v1.json, trigger_registry_v1.json, trigger ledger, runtime_state.json).
- Shared naming contracts (use exactly): bus-power boundary module abep_sim/arch_boundary.py (BOUNDARY_VERSION 'bus_power_boundary_v1'; components hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping, rf_source (rf_hall), ecr_source and ecr_magnet (ecr_hall); ledger(arch, loads, efficiencies)); comparison harness abep_sim/arch_compare.py; thermal/life abep_sim/thermal_life.py; evidence matrices docs/evidence/rf_source/, docs/evidence/ecr_source/, docs/evidence/hall_sustainment/, docs/evidence/cathode/, docs/evidence/wall_life/; experiment protocol docs/architecture_comparison/experiment_protocol/; upstream ICD schemas/interfaces/; ledgers schemas/ledgers/; Hall-map spec docs/hallmap/. These all exist in your base (merged and verified); also: docs/experiments/hardware/ (H-1/C-1 hardware definition), docs/experiments/instrumentation/, docs/experiments/s1a_readiness/, docs/experiments/s1_readiness/, docs/experiments/capability_demo/, docs/experiments/magnet_coil/, docs/experiments/lifetime_ao/, docs/architecture_comparison/{lock1,mass_bom,interstage,cathode_integration,feed_state_closure,compressor_downselect,aux_bus,power_boundary,veto_layer,experiment_package,hard_gates}/, docs/interfaces/UPSTREAM_ICD.md, docs/evidence/{rf_source,ecr_source,cathode,hall_sustainment}/, docs/milestones/bundle1/bundle1_v5.json.
- NEVER read, list or touch ${SP}/followon or ${SP}/wt_followon.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths. NEVER modify: hallthruster_bridge/** (prereg, campaign, propellants, audit, ensemble, validation, cases, bridge_lib.jl, PINNED.toml), the frozen P5-N2 pipeline scripts (scripts/score_p5_n2_*.py, scripts/audit_p5_n2_campaign_records.py, scripts/freeze_p5_n2_dataset.py, scripts/report_p5_n2_campaign.py, scripts/make_validation_release.py, scripts/make_p5_n2_launch_manifests.py), existing abep_sim modules (archengine.py, hall_map.py, hall_ensemble.py, intake*.py, compressor.py, reservoir.py, atmosphere.py, plasma_*.py, golden.py, ...), abep_sim/data/**, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py. New modules are pure and NOT wired into archengine (wiring would be a model change; goldens must not move).
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page/table numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed) or is explicitly "TBD — requires <what>". Computed values come from a committed deterministic script. No default physical/efficiency values hidden in code: inputs are explicit, missing inputs raise (CLAUDE.md rule 3, no silent fallbacks). Thresholds that are not in the RFP are PROPOSED for the owner.
3. Sources: published / openly accessible only; no contact with persons or labs; no email; no LXCat; no paywall/bot-challenge bypass (abstract-only labelled); never change TLS/trust settings. Cite DOIs/URLs actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch). From memory => "verify".
4. CPU: do NOT run Julia, do NOT run the full test suite, no computation > 1 min. Run only your own new test file(s).
5. Never use screening candidates or unadmitted Hall closures as performance sources; no retuning; never declare an architecture winner; eliminations only via explicit hard-gate logic with the evidence class that supports them. P5 calibration nuisance (registration, coil shape, divergence reading, facility interpretation) is never a design variable or grid axis. Hall-closure uncertainty never leaks upstream into intake/compressor/gas chambers/valves.
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
  evidence: `EVIDENCE LENS. (a) Every numeric value traces to a repository input file (open it and confirm, at least 10 spot checks) or to a cited open source (spot-check at least 4 with WebSearch/WebFetch, loaded via ToolSearch; fabricated or mis-attributed citations are BLOCKERS). (b) Values without source/evidence class, hidden defaults or invented numbers are MAJOR. (c) Any absolute Hall performance number, screening candidate used as performance, filled valve-outlet feed state or compressor draw, winner claim, or elimination not produced by lane 24's evaluator is a BLOCKER. (d) Physics/units of any derivation checked; wrong physics is MAJOR.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD within ALLOWED paths; no forbidden file touched; no uncommitted leftovers. (b) RECOMPUTE: for headline numbers derived from repository data or equations, write your own independent Python (do not reuse the lane's code) and compare; mismatch beyond rounding is major. (c) CORRECTNESS: JSON/schemas parse and validate; code consistent with the modules/fields it references (grep them); no hidden defaults; refusal paths raise; run ONLY the lane's own test file(s): they must pass and test something meaningful. (d) RULES: the three architecture ids used exactly; eliminations only via the lane-24 gate logic; missing inputs TBD/UNDETERMINED (never fabricated); every required deliverable of the brief present; milestone A/B/C statement present; no winner, no retuning. (e) USEFULNESS: every required deliverable in the brief present and substantive; the 'unlocks' claims are justified.`,
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
