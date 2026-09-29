export const meta = {
  name: 'a6-phase1-prereg',
  description: 'A6 follow-on fo_phase1_prereg_framework (attempt 2, one lane per workflow for parallelism); two-lens verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; all four lanes build simultaneously' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "302e1c94b3bddeb005f17bb189407f2e4641519a", "lanes": [{"key": "PH1PREREG", "title": "fo_phase1_prereg_framework", "allowed": ["docs/experiments/phase1_prereg_framework/**", "tests/test_phase1_prereg_framework.py"], "prompt": "Registered follow-on fo_phase1_prereg_framework (trigger T_A5_PHASE1_PREREG_FRAMEWORK, owner addendum A6). Build the Phase-1 pre-registration FRAMEWORK (structure only, NO numeric pass/fail thresholds). Deliver docs/experiments/phase1_prereg_framework/PHASE1_PREREG_FRAMEWORK.md and phase1_prereg_framework_v1.json. Contents: (1) the frozen list of decision quantities exactly as in A6 (sustainment; T/P_bus; eta_u; operating-envelope width; ignition/restart behaviour; stability/oscillation; absolute thrust compatibility; full bus-power compatibility; no continuous Xe augmentation), each with operational definition, measurement chain (map to the instrumentation v1-r2 INS ids and metrology spec in the base where they exist), units, the uncertainty source, and a threshold field whose value is the literal status 'UNFROZEN - finalized at LOCK-2 from S1/S1b measured capability' plus what S1/S1b quantity it depends on; (2) the gating sequence S1a -> LOCK-1 -> W5 freeze -> S1/S1b -> LOCK-2 -> Phase 1, stating what each step contributes to the thresholds (uncertainty, noise, remount reproducibility, pressure behaviour) and linking to the existing s1a_readiness / s1_readiness / lock1 / capability_demo deliverables; (3) the test-matrix STRUCTURE from A5: mdot_atm x x_O2 x V_d with density near the low-flow knee in the delivered-flow region and across x_O2 0.42-0.60 (cite A5 and the feed_state_closure/hall_sustainment sources), grid levels TBD; (4) the ORDER-BALANCED execution design per the A6 clarification: A5's Hall-only -> RF+Hall -> ECR+Hall is NOT the execution order; specify a counterbalanced scheme (e.g. all 6 permutations of {HW-0, HW-RF, HW-ECR} across blocks, or a Williams-type design balancing first-order carryover), HW-0 reference repeats inserted per block for drift, module exchange via the common pre-ionizer interface (fo_preionizer_module_icd, being built in parallel: reference docs/interfaces/preionizer_module/ by path), randomization seed pre-registered at LOCK-2, and the confounds it controls (chamber conditioning, wall temperature, cathode history, magnet heating, facility drift, contamination, hysteresis) with how each is measured; (5) the case logic A/B/C/NO_VIABLE_CASE from A5 expressed over the decision quantities, with 'no continuous Xe augmentation' as a necessary condition for Case A and 'net system-level benefit at P_bus' for B/C; (6) relation to the Hall-transport v2 prereg draft (docs/validation/hall_transport_v2_prereg/): which Phase-1 data are held-out Hall validation evidence, validation modes never crossed. Test file checks: all 9 decision quantities present, every threshold is UNFROZEN (no numeric acceptance value anywhere), sequence present in order, order-balanced design present with no fixed Hall->RF->ECR order, HW-0 reference repeats present. Milestone statement required. OWNER ADDITIONS: freeze the decision TOPOLOGY now - also include (7) the SAME-CONDITION definition (which feed-state, accelerator, magnet, cathode, facility-pressure and thermal-state variables must match across HW-0/RF/ECR at a point, and the matching tolerance field, UNFROZEN until LOCK-2); (8) MISSING-DATA handling (pre-registered rule for aborted/extinguished/instrument-failed points; extinction is a sustainment observation, not missing data; no post hoc exclusion); (9) DATA-QUALITY rules (instrument health, calibration currency, drift checks against HW-0 references, pressure/background limits as UNFROZEN fields); (10) the REPEATABILITY/REMOUNT procedure (repeat and module remount checks per block, linked to the common pre-ionizer interface item for installation/removal reproducibility); (11) the LOCK-1 / LOCK-2 structure: what is fixed at each lock and what S1/S1b quantities (thrust uncertainty, power uncertainty, remount reproducibility, drift, stability/noise) LOCK-2 converts into numeric boundaries. Pin A5/A6 and the G0 record by sha256."}]}
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
