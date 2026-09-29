export const meta = {
  name: 'a6-integration-refresh-reverify',
  description: 'Re-verify fo_a6_integration_refresh repair 3 (219a290, operator repair of the last verify3 major): evidence + rules lenses',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; all four lanes build simultaneously' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "eb974b155f16414781518b8e366439b83182cff9", "lanes": [{"key": "REFRESH", "title": "fo_a6_integration_refresh", "allowed": ["docs/budgets/subsystem_maturity/**", "tests/test_subsystem_maturity.py", "docs/budgets/owner_decisions/**", "tests/test_owner_decision_register.py"], "prompt": "Registered follow-on fo_a6_integration_refresh (trigger T_A6_INTEGRATION_REFRESH, owner addendum A7 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json - read it, pin by sha256). All four A6 lanes are now MERGED in your base: docs/interfaces/preionizer_module/ + schemas/interfaces/preionizer_module_icd_v1.json, abep_sim/xe_ledger.py + docs/budgets/xe_ledger/, docs/experiments/phase1_prereg_framework/, docs/budgets/subsystem_maturity/ (M16; its builder --check currently reports STALE only because the three other lanes are now present). TASK 1 - M16 INTEGRATION + SCHEDULER (revise docs/budgets/subsystem_maturity/ builder, JSON, MD, tests; bump to v2 files subsystem_maturity_v2.json / SUBSYSTEM_MATURITY_v2.md, keep v1 byte-identical as history): (a) replace every PENDING_PARALLEL_LANE / PRESENT_NOT_YET_INTEGRATED cell with the actual content of the merged deliverables (interface status from PMI items and their status/closes_at; Xe rows from xe_ledger_v1.json parameters, ledger refusal state and blockers; Phase-1 rows from the framework's decision quantities / S1b gaps), pinning each by sha256; (b) add the A7 SCHEDULER columns: execution_state in {READY, RUNNING, BLOCKED, VERIFIED} with a stated deterministic rule (e.g. VERIFIED only when the row's governing deliverables are owner-frozen and its S1a/S1 evidence is recorded; RUNNING when a registered H2 lane (fo_h2_1..7 in docs/orchestration/lane_registry_v1.json - READ it, never pin it) is assigned to the row; BLOCKED when a named blocking item exists and no lane is working it; READY otherwise), every BLOCKED row points to EXACTLY ONE blocking evidence/interface item; (c) rollup by the A7 five categories: architecture blocker / hardware-definition blocker / procurement blocker / test-readiness blocker / proposal-only documentation gap (keep the v1 technical categories as a secondary field); (d) flag per row whether its blocker is one of the A7 three ARCHITECTURE-CHANGING blockers (1 Hall-only sustainment at the actual feed state, 2 incremental RF/ECR benefit at full P_bus, 3 Xe/cathode closure) or can only veto via a hard incompatibility; (e) map each H2 lane (fo_h2_1_hall_chamber_magnet ... fo_h2_7_mechanical_bom, titles from A7) to the rows it matures; (f) carry the cross-lane inconsistencies the merged lanes flagged (e.g. cathode_integration PREIONIZER_COMPONENTS['ecr_hall'] omits ecr_magnet; thermal_life covers only permanent-magnet ecr_magnet; metrology spec file status vs A4) as a reconciliation list with the owning lane - do NOT fix them. TASK 2 - CONSOLIDATED OWNER DECISION REGISTER: docs/budgets/owner_decisions/owner_decision_register_v1.json + OWNER_DECISION_REGISTER.md + deterministic builder + tests/test_owner_decision_register.py, collecting VERBATIM (by id, with source path + JSON pointer + sha256) every open owner decision from the four merged lanes: Xe ledger OD-XE-1..8, Phase-1 framework reconciliation_items R-01..R-14 and its open_owner_decisions, pre-ionizer ICD PMQ-01..07 (plus the HWQ items it relays), M16 open questions; for each: needed_by (NOW / before H2 freeze / LOCK-1 / LOCK-2 / later) as stated by the source or 'UNSTATED', whether it can change a budget or an A7 architecture-changing blocker (with the reason), the source's proposal verbatim, and a status field OPEN. Do not add recommendations of your own beyond marking which items the sources call architecture- or budget-relevant. No owner decision is taken here. Milestone statement required."}]}
const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). NOTE: for THIS lane all four A6 deliverables ARE merged in your base (ignore any statement that they are parallel/not present). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. FIRST run: git reset --hard ${BASE} (the worktree is created from main, which lacks the governance and decision files) and confirm with: git rev-parse HEAD. Base commit: ${BASE}.

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

const lane = ARGS_EMBEDDED.lanes[0]
const res = { worktree_path: '/home/user/abep/.claude/worktrees/wf_e5dad84b-737-1', branch: 'worktree-wf_e5dad84b-737-1',
  commit: '219a290' }
const extra = ' NOTE: this commit (219a290) is an operator repair on top of ad5b73e fixing the verify3 rules-lens major: the only RUNNING row (buffer_plenum) did not meet the partial_scope rule; it is now BLOCKED with partial_scope H2-3, and the builder refuses worked_by without a produces_all_quote equal to the full requires text. Review the WHOLE lane at this commit, including that repair.'
const lensList = ['evidence', 'rules']
const vs = await parallel(lensList.map(lens => () =>
  agent(verifyPrompt(lane, res, lens) + extra, { label: `verify4:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
const ok = vs.filter(Boolean)
return { pass: ok.length === 2 && ok.every(v => v.pass), verdicts: ok }
